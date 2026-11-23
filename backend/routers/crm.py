"""CRM / Sales Force router (KN_17 CRM-lite).

Customer 360, reassign, credit override, collection worklist/followups,
sales KPI/leaderboard/commission, incentive schemes (KM-T5: target sales lewat `/api/incentive/targets`).
All derived data via services. Row-level scoping enforced (sales -> own customers).
"""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request, Query
from pymongo import ReturnDocument
from db import db
from dependencies import has_permission, require_any_permission, require_permission, current_user, audit
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID
from schemas import (
    CustomerReassign, SalesIncentiveCreate,
    CreditOverrideCreate, CreditOverrideDecision, CollectionFollowupCreate,
)
from services.customer_service import (
    customer_360, compute_customer_credit, can_access_customer, can_collect_customer, can_view_credit, collection_worklist,
    collection_reminders,
)
from services.sales_force_service import sales_kpi, compute_commission, leaderboard, commission_history
from services import credit_override_service as cos   # CR-T3 — izin kredit
from services import gl_service
from entity_scope import entity_ctx, guard_doc, resolve_list_scope
from ai_card_context import card_field
# PR-T4 — cakupan data & kategori kerja dari sifat peran (bukan nama peran).
from role_registry import roles_in_category
from services.data_scope import in_clause, own_scoped, owner_ids, owns

router = APIRouter(prefix="/api")


# ── Sales users (untuk dropdown assignment) ──────────────────────────────────
@router.get("/sales-users")
async def list_sales_users(request: Request, entity_id: str = None) -> List[Dict[str, Any]]:
    """Daftar sales untuk dropdown penugasan.

    FASE E-8 (E8.5) — IKUT BADAN USAHA. Sebelum ini endpoint mengembalikan SELURUH
    sales seluruh grup, sehingga dropdown "Sales penanggung jawab" di CV Kanda Suka
    menawarkan sales PT Kain Suka Cita — dan target/insentif bisa tertempel pada orang
    dari buku yang salah. Penyaringan memakai `allowed_entity_ids` (mekanisme penugasan
    yang sudah ada) supaya sales ber-penugasan 2 badan usaha tetap muncul di keduanya.

    PR-T3 (S4) — dulu cukup login (Sopir membaca nama & email semua sales). Kini salah satu izin layar pemakainya
    (pelanggan, pesanan, pengawasan tim sales).
    """
    await require_any_permission(request, [("customer", "view"), ("order", "view"), ("sales_force", "view")],
                                 detail="Anda belum punya akses untuk melihat daftar sales. Minta Admin menambahkan "
                                        "akses 'Pelanggan & CRM' atau 'Pesanan Penjualan'.")
    ctx = await entity_ctx(request)
    ids = ([entity_id] if entity_id and entity_id != "all"
           else list(ctx.allowed_entity_ids) if (entity_id == "all"
                                                 or getattr(ctx, "view_all", False))
           else [ctx.active_entity_id])
    ids = [i for i in ids if i in ctx.allowed_entity_ids] or list(ctx.allowed_entity_ids)
    # KM-T5 — daftar = `incentive_targets.sales_roster` tiap PT (akun aktif berperan acuan / berkategori sales yang
    # ditugaskan di PT itu — satu daftar dengan Meja Insentif, papan peringkat, dan akrual).
    from services.incentive_targets import sales_roster
    roster = set()
    for e in ids:
        roster |= {u["id"] for u in await sales_roster(e) if u.get("active")}
    rows = await db.users.find(
        {"id": {"$in": sorted(roster)}},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "home_entity_id": 1}
    ).sort("name", 1).to_list(None)
    return [safe_doc(r) for r in rows]


# ── Customer 360 ─────────────────────────────────────────────────────────────
@router.get("/customers/{customer_id}/360")
async def get_customer_360(customer_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "customer", "view")
    data = await customer_360(customer_id)
    if not data:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    if not await can_access_customer(actor, data):
        raise HTTPException(status_code=403, detail="Customer ini bukan milik Anda")
    # MN-T3 (K-18) — kartu pelanggan: `sections_allowed` + angka kredit/piutang dikosongkan bila izinnya tidak dipegang.
    from services.party_card import customer_card
    return await customer_card(data, actor)


# ── Reassign salesperson (Manager/Admin, teraudit) ───────────────────────────
@router.post("/customers/{customer_id}/reassign")
async def reassign_customer(customer_id: str, payload: CustomerReassign, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "sales_force", "assign")
    before = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0, "assigned_sales_id": 1,
                                                                          "entity_id": 1, "sales_team": 1}))
    if not before:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    # KM-T1 (PR-UX-04) — sales tujuan = akun dari SATU penentu daftar sales (`incentive_targets.sales_roster`, PT
    # pelanggan): akun aktif berperan — atau berperan acuan / berkategori kerja — sales yang ditugaskan di PT itu.
    from services.incentive_targets import is_sales_account, sales_roster
    eid = before.get("entity_id") or ""
    if eid and eid != "all":
        ok = payload.assigned_sales_id in {s["id"] for s in await sales_roster(eid) if s.get("active")}
    else:
        ok = await is_sales_account(payload.assigned_sales_id)
    sales = await db.users.find_one({"id": payload.assigned_sales_id, "status": "active"}, {"_id": 0}) if ok else None
    if not sales:
        raise HTTPException(status_code=400, detail="Salesperson tujuan tidak valid")
    # KM-06 — pesanan baru mewarisi `sales_team` pelanggan lebih dulu (`resolve_customer_sales_team`): anggota `pic`
    # ikut diganti (pendamping tetap — ASUMSI unit), supaya pesanan sesudah serah-terima milik sales baru.
    team = [dict(m) for m in (before.get("sales_team") or [])]
    if team:
        pic = next((m for m in team if m.get("role") == "pic"), None) or team[0]
        dup = [m for m in team if m is not pic and m.get("sales_id") == sales["id"]]
        for m in dup:   # sales tujuan sudah pendamping → digabung ke PIC (Σ porsi tetap)
            pic["split_pct"] = round(float(pic.get("split_pct") or 0) + float(m.get("split_pct") or 0), 4)
            team.remove(m)
        pic.update({"sales_id": sales["id"], "name": sales.get("name", "")})
    updated = await db.customers.find_one_and_update(
        {"id": customer_id},
        {"$set": {"assigned_sales_id": sales["id"], "assigned_sales_name": sales["name"],
                  "sales_pic": sales["name"], "updated_at": now_iso(), **({"sales_team": team} if team else {})}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER,
    )
    await audit(actor["name"], "customer_reassigned", "customer", customer_id,
                {"from": before.get("assigned_sales_id"), "to": sales["id"], "reason": payload.reason,
                 **({"sales_team_before": before.get("sales_team"), "sales_team_after": team} if team else {})})
    return safe_doc(updated)


# ── Izin kredit (KN_17 5.2 / S37; CR-T3 — `services/credit_override_service.py`) ─────────────────────────────
PESAN_IZIN_LIHAT = ("Anda belum punya akses untuk melihat izin kredit. Minta Admin menambahkan akses "
                    "'Pengawasan Tim Sales & Kredit'.")
PESAN_IZIN_AJU = ("Anda belum punya akses untuk mengajukan izin kredit. Minta Admin menambahkan akses "
                  "'Pengawasan Tim Sales & Kredit'.")


@router.post("/customers/{customer_id}/credit-override")
async def request_credit_override(customer_id: str, payload: CreditOverrideCreate, request: Request) -> Dict[str, Any]:
    """CR-T3 — ajukan izin kredit (`credit_override.create`, dulu `order.create`): `scope` pesanan · pelanggan,
    `order_id` wajib bila pesanan, `reason_code` wajib, nominal > 0 (PK-45). PT = PT yang diminta (N1)."""
    actor = await require_permission(request, "credit_override", "create", detail=PESAN_IZIN_AJU)
    customer = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0}))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    if not await can_access_customer(actor, customer):
        raise HTTPException(status_code=403, detail="Customer ini bukan milik Anda")
    if float(payload.amount or 0) <= 0:   # PK-45 (CR-04) — nominal 0 dulu berarti "tanpa batas"
        raise HTTPException(status_code=400, detail=cos.PESAN_NOMINAL)
    from entity_scope import resolve_requested_entity
    eid = resolve_requested_entity(await entity_ctx(request), payload.entity_id or customer.get("entity_id") or "")
    order = None
    if (payload.scope or "pelanggan") == "pesanan":
        order = safe_doc(await db.sales_orders.find_one({"id": payload.order_id or "__tanpa__"}, {"_id": 0}))
        if not order or order.get("customer_id") != customer_id:
            raise HTTPException(status_code=400, detail=cos.PESAN_ORDER)
        await guard_doc(request, "sales_orders", order, strict=False)   # N2 — pesanan milik PT yang sama
        eid = order.get("entity_id") or eid
    return await cos.create(customer, eid, scope=payload.scope or "pelanggan", amount=payload.amount,
                            reason_code=payload.reason_code, note=payload.reason, actor=actor, order=order,
                            evidence_url=payload.evidence_url, rejection_id=payload.rejection_id)


@router.get("/credit-override-reasons")
async def list_credit_override_reasons(request: Request) -> List[Dict[str, Any]]:
    """CR-T3 — pilihan "Alasan" pop-up izin kredit (master alasan, `applies_to` memuat `credit_override`)."""
    await require_any_permission(request, [("credit_override", "create"), ("credit_override", "view")],
                                 detail=PESAN_IZIN_LIHAT)
    return await cos.reasons()


async def _cakupan_izin(actor: Dict[str, Any], query: Dict[str, Any]) -> Dict[str, Any]:
    """PR-T4 — cakupan data peran: pengguna "milik sendiri/tim" melihat izin yang ia ajukan atau milik pelanggannya."""
    if own_scoped(actor):
        from services.customer_service import scope_query
        cids = await db.customers.distinct("id", scope_query(actor, {}))
        ands = list(query.pop("$and", []) or [])
        ands.append({"$or": [{"requested_by_id": in_clause(await owner_ids(actor))}, {"customer_id": {"$in": cids}}]})
        query["$and"] = ands
    return query


@router.get("/credit-overrides")
async def list_credit_overrides(request: Request, status: str = None, scope: str = None, valid: str = None,
                                customer_id: str = None) -> List[Dict[str, Any]]:
    """CR-T3 — `credit_override.view` (dulu `customer.view`); saringan `status`, `scope` (pesanan · pelanggan),
    `valid=1` (disetujui, belum kedaluwarsa, bersisa), `customer_id`; cakupan PT (PK-45) dan pelanggan (PR-T4)."""
    actor = await require_permission(request, "credit_override", "view", detail=PESAN_IZIN_LIHAT)
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if customer_id:
        query["customer_id"] = customer_id
    query = await _cakupan_izin(actor, query)
    query = resolve_list_scope("credit_overrides", query, await entity_ctx(request))   # PK-45 (CR-04) — per PT
    rows = [cos.tampil(r) for r in await db.credit_overrides.find(query, {"_id": 0}).sort("created_at", -1)
            .to_list(200)]
    if scope in cos.LINGKUP:
        rows = [r for r in rows if r["scope"] == scope]
    if str(valid or "").lower() in ("1", "true", "ya"):
        rows = [r for r in rows if r["usable"]]
    from services.credit_profile_service import ringkas_pt
    pt = {e["id"]: e for e in await ringkas_pt({r.get("entity_id") for r in rows})}
    for r in rows:   # N5 — konfirmasi layar menyebut PT (bukan id teknis)
        e = pt.get(r.get("entity_id")) or {}
        r["entity_name"] = e.get("short_name") or e.get("legal_name") or ""
    return rows


@router.get("/credit-gate-rejections")
async def list_credit_gate_rejections(request: Request, status: str = Query(""), customer_id: str = Query(""),
                                      page: int = Query(1, ge=1),
                                      page_size: int = Query(25, ge=1, le=100)) -> Dict[str, Any]:
    """CR-T3 — pesanan yang ditolak gerbang kredit saat dibuat, terbaru dulu, berhalaman, PT aktif. Pemegang
    `credit_override.view` melihat cakupan datanya; pembuat pesanan (tanpa izin itu) selalu melihat penolakannya sendiri."""
    actor = await require_any_permission(request, [("credit_override", "view"), ("order", "create")],
                                         detail=PESAN_IZIN_LIHAT)
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if customer_id:
        q["customer_id"] = customer_id
    if not await has_permission(actor, "credit_override", "view"):
        q["actor_id"] = actor.get("id")
    elif own_scoped(actor):
        from services.customer_service import scope_query
        cids = await db.customers.distinct("id", scope_query(actor, {}))
        q["$or"] = [{"actor_id": actor.get("id")}, {"customer_id": {"$in": cids}}]
    q = resolve_list_scope("credit_gate_rejections", q, await entity_ctx(request))
    total = await db.credit_gate_rejections.count_documents(q)
    rows = await db.credit_gate_rejections.find(q, {"_id": 0, "payload_snapshot": 0}).sort("created_at", -1) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return {"items": [safe_doc(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/credit-gate-rejections/{rejection_id}")
async def get_credit_gate_rejection(rejection_id: str, request: Request) -> Dict[str, Any]:
    """CR-T3 — rincian penolakan, termasuk `payload_snapshot` (isi permintaan pesanan)."""
    actor = await require_any_permission(request, [("credit_override", "view"), ("order", "create")],
                                         detail=PESAN_IZIN_LIHAT)
    doc = await db.credit_gate_rejections.find_one({"id": rejection_id}, {"_id": 0})
    if doc and doc.get("actor_id") != actor.get("id"):
        boleh = await has_permission(actor, "credit_override", "view")
        if boleh and own_scoped(actor):
            cust = await db.customers.find_one({"id": doc.get("customer_id")}, {"_id": 0}) or {}
            boleh = await can_access_customer(actor, cust)
        if not boleh:
            doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="Penolakan gerbang kredit tidak ditemukan")
    await guard_doc(request, "credit_gate_rejections", doc, strict=False)
    return safe_doc(doc)


@router.get("/credit-overrides/{override_id}")
async def get_credit_override(override_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "credit_override", "view", detail=PESAN_IZIN_LIHAT)
    doc = await db.credit_overrides.find_one({"id": override_id}, {"_id": 0})
    if doc and own_scoped(actor) and not await owns(actor, doc.get("requested_by_id")):
        cust = await db.customers.find_one({"id": doc.get("customer_id")}, {"_id": 0}) or {}
        if not await can_access_customer(actor, cust):
            doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="Izin kredit tidak ditemukan")
    await guard_doc(request, "credit_overrides", doc, strict=False)   # PK-45 (CR-04) — PT lain → 404
    return cos.tampil(doc)


@router.post("/credit-overrides/{override_id}/decision")
async def decide_credit_override(override_id: str, payload: CreditOverrideDecision, request: Request) -> Dict[str, Any]:
    """CR-T3 — `credit_override.approve` + Aturan Persetujuan (`credit_override`, nominal izin) + kontrol dua orang
    (`kontrol.lewat_batas_kredit.*`); sudah diputus/kedaluwarsa → 409. Disetujui: masa berlaku, sisa, pesanan yang
    ditahan pelanggan itu diperiksa ulang."""
    actor = await require_permission(request, "credit_override", "approve")
    if payload.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision harus approve|reject")
    # PK-45 (CR-04) — PT dokumen diadu dengan penugasan pemutus sebelum keputusan ditulis.
    co = await db.credit_overrides.find_one({"id": override_id}, {"_id": 0})
    await guard_doc(request, "credit_overrides", co, strict=False, not_found="Izin kredit tidak ditemukan")
    return cos.tampil(await cos.decide(override_id, payload.decision, payload.reason, actor))


# ── Collection worklist + follow-up (KN_17 7 / S39) ──────────────────────────
@router.get("/collection-worklist")
async def get_collection_worklist(request: Request, sales_id: str = None, entity_id: str = None) -> List[Dict[str, Any]]:
    actor = await require_permission(request, "order", "view")
    return await collection_worklist(actor, sales_id=sales_id, entity_id=entity_id)


@router.get("/customers/{customer_id}/credit-status")
async def get_credit_status(customer_id: str, request: Request, amount: float = 0, term_code: str = "",
                            entity_id: str = "") -> Dict[str, Any]:
    """Pratinjau gerbang kredit (tanpa memakai izin) untuk layar buat pesanan. CR-T3 — field lama dipertahankan, ditambah
    `gate` (hasil `credit_gate.evaluate` titik `pesanan_dibuat`, PT pesanan: `entity_id` → PT pelanggan → PT aktif)."""
    actor = await require_permission(request, "order", "view")
    customer = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0}))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    # INV-ENTITY-01 (KN-079-IDOR-CREDIT-STATUS P1): konsisten dgn /360 — cegah bocor kredit/AR lintas-PT.
    if not can_view_credit(actor, customer):
        raise HTTPException(status_code=403, detail="Customer ini bukan milik Anda")
    from entity_scope import resolve_requested_entity
    from services import credit_gate as cg
    ctx = await entity_ctx(request)
    eid = resolve_requested_entity(ctx, entity_id) if entity_id else (customer.get("entity_id") or ctx.active_entity_id)
    gate = await cg.evaluate(customer_id=customer_id, entity_id=eid, checkpoint=cg.PESANAN_DIBUAT,
                             order_amount=float(amount or 0), term_code=term_code, actor=actor)
    raw = gate.get("raw_result") or cg.LOLOS
    return {
        "level": {"tahan": "blocked", "tolak": "blocked", "peringatan": "warning"}.get(raw, "ok"),
        "blocked": gate["result"] in (cg.TAHAN, cg.TOLAK),
        "allowed_after_override": gate["result"] == cg.LOLOS and bool(gate.get("override")),
        "reasons": [r["message"] for r in gate.get("reasons") or []],
        "credit": await compute_customer_credit(customer, eid), "projected_ar": (gate.get("exposure") or {}).get("total", 0),
        "has_approved_override": bool(gate.get("override")),
        "gate": gate,
    }


# ── Collection reminders (KN_17 §7 / 4b) ─────────────────────────────────────
@router.get("/collection-reminders")
async def get_collection_reminders(request: Request, days_ahead: int = 7, sales_id: str = None, entity_id: str = None) -> List[Dict[str, Any]]:
    actor = await require_permission(request, "order", "view")
    return await collection_reminders(actor, days_ahead=days_ahead, sales_id=sales_id, entity_id=entity_id)


@router.post("/collection-reminders/mark")
async def mark_reminder(payload: CollectionFollowupCreate, request: Request) -> Dict[str, Any]:
    """Tandai 'sudah diingatkan' (mencatat follow-up outcome=reminded)."""
    actor = await require_permission(request, "order", "update")
    customer = safe_doc(await db.customers.find_one({"id": payload.customer_id}, {"_id": 0}))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    if not await can_collect_customer(actor, customer):
        raise HTTPException(status_code=403, detail="Customer ini bukan milik Anda")
    doc = {
        "id": new_id("cfu"), "customer_id": payload.customer_id, "customer_name": customer.get("name", ""),
        "order_id": payload.order_id, "note": payload.note or "Pengingat penagihan dikirim",
        "outcome": "reminded", "next_action_date": payload.next_action_date,
        "entity_id": customer.get("entity_id", DEFAULT_ENTITY_ID),
        "created_by": actor["name"], "created_by_id": actor["id"], "created_at": now_iso(),
        **card_field(),   # AG-T3 — dari kartu tindakan asisten yang disetujui
    }
    await db.collection_followups.insert_one(dict(doc))
    await audit(actor["name"], "collection_reminded", "collection_followup", doc["id"], doc)
    return safe_doc(doc)


@router.post("/customers/{customer_id}/followups")
async def add_followup(customer_id: str, payload: CollectionFollowupCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "order", "update")
    customer = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0}))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    if not await can_collect_customer(actor, customer):
        raise HTTPException(status_code=403, detail="Customer ini bukan milik Anda")
    from services.credit_desk_service import promise_fields   # CR-T5 — janji bayar bertanggal & bernominal
    janji = promise_fields(payload.outcome, payload.promise_date, payload.promise_amount)
    doc = {
        "id": new_id("cfu"),
        "customer_id": customer_id,
        "customer_name": customer.get("name", ""),
        "order_id": payload.order_id,
        "note": payload.note,
        "outcome": payload.outcome,
        "next_action_date": payload.next_action_date,
        **janji,
        "entity_id": customer.get("entity_id", DEFAULT_ENTITY_ID),
        "created_by": actor["name"],
        "created_by_id": actor["id"],
        "created_at": now_iso(),
        **card_field(),   # AG-T3 — dari kartu tindakan asisten yang disetujui
    }
    await db.collection_followups.insert_one(dict(doc))
    await audit(actor["name"], "collection_followup_added", "collection_followup", doc["id"], doc)
    return safe_doc(doc)


# ── Sales KPI / leaderboard / commission ─────────────────────────────────────
async def _target_sales_query(actor: Dict[str, Any], sales_id: str = None):
    """PR-T3 (S3) + PR-T4 — saringan `sales_id` daftar target & skema insentif (aturan yang sama dengan KPI/komisi):
    pemegang `sales_force.view` melihat semua atau sales yang dipilih; peran bercakupan data bukan "semua" → dirinya
    atau anggota timnya; pemegang `order.view_sales_kpi` (dulu daftar nama peran pengawas) melihat semua atau sales yang
    dipilih; selain itu hanya miliknya sendiri. Kosong = tanpa saringan sales."""
    if await has_permission(actor, "sales_force", "view"):
        return sales_id or ""
    if own_scoped(actor):
        ids = await owner_ids(actor) or []
        return sales_id if sales_id and sales_id in ids else in_clause(ids)
    if await has_permission(actor, "order", "view_sales_kpi"):
        return sales_id or ""
    return actor["id"]


async def _kpi_scope(request: Request, sales_id: str, entity_id: str) -> tuple:
    """Tanya KN F0.4 — izin + validasi entitas untuk KPI/komisi sales."""
    actor = await require_permission(request, "order", "view")
    ctx = await entity_ctx(request)
    if entity_id == "all":
        # KN-E38 — "all" = TANPA saring entitas, jadi hanya sah bila pengguna memang berhak atas SEMUA PT.
        every = set(await db.business_entities.distinct("id"))
        if not (ctx.is_cross_entity or ctx.can_view_combined) or (every - set(ctx.allowed_entity_ids or [])):
            entity_id = ctx.active_entity_id
    elif entity_id:
        if not ctx.can_access(entity_id):
            raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
    else:
        entity_id = ctx.active_entity_id
    # KN-E38 — KPI/komisi sales lain hanya untuk yang berwenang. PR-T4: cakupan data bukan "semua" → dirinya atau
    # anggota timnya; selain itu butuh izin `order.view_sales_kpi` (dulu daftar nama peran admin/manajer/admin sales/
    # finance). Permintaan yang tidak berwenang = KPI dirinya (perilaku lama, bukan 403).
    if own_scoped(actor):
        if sales_id not in (await owner_ids(actor) or []):
            sales_id = actor["id"]
    elif not sales_id or not await has_permission(actor, "order", "view_sales_kpi"):
        sales_id = actor["id"]
    return sales_id, entity_id


@router.get("/sales/kpi")
async def get_sales_kpi(request: Request, sales_id: str = None, period: str = None, entity_id: str = None) -> Dict[str, Any]:
    sales_id, entity_id = await _kpi_scope(request, sales_id, entity_id)
    return await sales_kpi(sales_id, period=period, entity_id=entity_id)


@router.get("/sales/leaderboard")
async def get_leaderboard(request: Request, period: str = None, entity_id: str = None) -> List[Dict[str, Any]]:
    await require_permission(request, "sales_force", "view")
    ctx = await entity_ctx(request)
    if not entity_id:   # angka papan peringkat mengikuti badan usaha aktif (sama dengan AR Aging)
        entity_id = "all" if ctx.view_all else ctx.active_entity_id
    return await leaderboard(period=period, entity_id=entity_id)


@router.get("/sales/order-dashboard")
async def get_order_dashboard(request: Request, sales_id: str = None, entity_id: str = None) -> Dict[str, Any]:
    """Dasbor Pesanan HP — sales selalu data miliknya sendiri (sales_id diabaikan)."""
    from services.sales_order_dashboard import order_dashboard
    sid, entity_id = await _kpi_scope(request, sales_id, entity_id)
    return await order_dashboard(sid, entity_id)


@router.get("/sales/my-rank")
async def get_my_rank(request: Request, period: str = None, entity_id: str = None) -> Dict[str, Any]:
    """Peringkat SAYA (posisi dari N) tanpa membuka angka rekan sales — untuk layar HP sales."""
    sales_id, entity_id = await _kpi_scope(request, None, entity_id)
    rows = await leaderboard(period=period, entity_id=entity_id)
    mine = next((r for r in rows if r.get("sales_id") == sales_id), None)
    return {"period": period, "rank": mine.get("rank") if mine else None, "total": len(rows),
            "total_sales": float(mine.get("total_sales") or 0) if mine else 0.0}


PESAN_TANPA_KOMISI = "PT ini tidak memakai komisi otomatis. Lihat Capaian & Insentif."


async def _tolak_tanpa_komisi(entity_id: str) -> None:
    """KM-T5 — komisi otomatis hanya untuk PT yang sakelar insentifnya (`hr.payroll_commission_mode`) bukan `sheet` /
    `off` → selain itu 409. "Semua PT": ditolak bila SEMUA PT sudah tidak memakai komisi otomatis."""
    from services import incentive_payroll as ipay
    ents = ([entity_id] if entity_id and entity_id != "all"
            else [e["id"] async for e in db.business_entities.find({}, {"_id": 0, "id": 1}) if e.get("id")])
    if ents and all([await ipay.mode_pt(e) in ipay.TANPA_MESIN for e in ents]):
        raise HTTPException(status_code=409, detail=PESAN_TANPA_KOMISI)


@router.get("/sales/commission")
async def get_commission(request: Request, sales_id: str = None, period: str = Query(...), entity_id: str = None) -> Dict[str, Any]:
    sales_id, entity_id = await _kpi_scope(request, sales_id, entity_id)
    await _tolak_tanpa_komisi(entity_id)
    return await compute_commission(sales_id, period, entity_id=entity_id)


@router.get("/sales/commission-history")
async def get_commission_history(request: Request, sales_id: str = None, period_type: str = "month",
                                 anchor: str = None, count: int = 6, entity_id: str = None) -> List[Dict[str, Any]]:
    sales_id, entity_id = await _kpi_scope(request, sales_id, entity_id)   # KN-E38 — izin + entitas
    await _tolak_tanpa_komisi(entity_id)
    count = max(1, min(int(count or 6), 12))
    return await commission_history(sales_id, period_type=period_type, anchor=anchor, count=count, entity_id=entity_id)


# ── Insentif → GL (F0-E: akrual beban insentif per-entitas, Model 1) ─────────
@router.get("/sales/incentive/gl-status")
async def get_incentive_gl_status(request: Request, period: str = Query(...),
                                  entity_id: str = None) -> Dict[str, Any]:
    """Status akrual insentif untuk (entitas aktif|param, periode)."""
    await require_permission(request, "sales_force", "view")
    ctx = await entity_ctx(request)
    eid = entity_id or ctx.active_entity_id
    if eid == "all" or eid not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=400, detail="Pilih entitas spesifik untuk status akrual insentif.")
    out = await gl_service.incentive_accrual_status(eid, period)
    # KM-T5 — sakelar PT + angka yang akan dibukukan (konfirmasi "Bukukan akrual komisi {bulan}" menyebut nominalnya).
    from services import incentive_payroll as ipay
    out["mode"] = await ipay.mode_pt(eid)
    out["estimate"] = (await gl_service.incentive_accrual_estimate(eid, period)
                       if ipay.akru(out["mode"]) else 0.0)
    return out


@router.post("/sales/incentive/post-gl")
async def post_incentive_gl(request: Request, period: str = Query(...),
                            entity_id: str = None) -> Dict[str, Any]:
    """Posting akrual beban insentif penjualan (entitas, periode) ke buku GL entitas.

    Dr Beban Insentif Penjualan / Cr Hutang Insentif Penjualan. Idempotent.
    """
    actor = await require_permission(request, "sales_force", "post")
    ctx = await entity_ctx(request)
    eid = entity_id or ctx.active_entity_id
    if eid == "all" or eid not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=400, detail="Pilih entitas spesifik (bukan 'Semua') untuk posting insentif ke GL.")
    # PK-22 (FY-08) — akrual terpisah hanya untuk PT ber-mode `accrue_then_settle`; mode lain mengakui beban saat gaji
    # diposting, jadi akrual manual = beban ganda. Tanggal buku = jurnal periodik (`gl.tanggal_jurnal_periodik`, K-13).
    from services import incentive_payroll as ipay
    from services import periodic_posting
    from services.config_resolver import value_of
    if not ipay.akru(await value_of("hr.payroll_commission_mode", {"entity_id": eid})):
        raise HTTPException(status_code=409, detail="PT ini mengakui beban insentif saat gaji diposting, jadi akrual "
                                                    "terpisah tidak dipakai.")
    try:
        tgl = await periodic_posting.journal_date(eid, period)
        entry = await gl_service.post_incentive_accrual(eid, period, created_by=actor.get("name", "system"), date=tgl)
    except gl_service.ClosedPeriodError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    status = await gl_service.incentive_accrual_status(eid, period)
    if entry:
        await audit(actor["name"], "incentive_accrual", "journal_entry",
                    status.get("journal_id", ""), status,
                    f"Insentif {period} entitas {eid} = {status.get('amount')}")
        verb = "Koreksi akrual" if entry.get("source_type") == "incentive_accrual_adj" else "Akrual"
        return {"created": True, "message": f"{verb} insentif {period} diposting (JE {entry.get('number')}).", **status}
    # Sudah pernah diposting (idempotent) atau total 0
    if status.get("posted"):
        return {"created": False, "message": "Akrual insentif periode ini sudah pernah diposting.", **status}
    return {"created": False, "message": "Tidak ada insentif untuk diposting pada periode ini (total 0).", **status}


# ── Sales targets ────────────────────────────────────────────────────────────
_S3_DITOLAK = ("Anda belum punya akses untuk melihat target dan skema insentif sales. Minta Admin menambahkan akses "
               "'Pesanan Penjualan'.")


# KM-T5 — `GET`/`POST /api/sales-targets` (layar lama "Set Target" & editor skema) DIHAPUS: pencarian
# `rg "sales-targets" frontend/src` tanpa pemanggil sesudah layar lama dihapus; target dibaca & diubah lewat
# `GET`/`PUT /api/incentive/targets` (Meja Insentif › Target & Aturan, KM-T1).


# ── Sales incentive schemes ──────────────────────────────────────────────────
@router.get("/sales-incentives")
async def list_incentives(request: Request, sales_id: str = None, period: str = None,
                          entity_id: str = None) -> List[Dict[str, Any]]:
    """FASE E-0 (L6) — insentif sales WAJIB ter-scope entitas (insentif = beban entitas). PR-T3 (S3) — seperti
    daftar target."""
    actor = await require_permission(request, "order", "view", detail=_S3_DITOLAK)
    ctx = await entity_ctx(request)
    query: Dict[str, Any] = {}
    sq = await _target_sales_query(actor, sales_id)
    if sq:
        query["sales_id"] = sq
    if period:
        query["period"] = period
    query = resolve_list_scope("sales_incentives", query, ctx, entity_id)
    return await db.sales_incentives.find(query, {"_id": 0}).sort("period", -1).to_list(200)


@router.post("/sales-incentives")
async def create_incentive(payload: SalesIncentiveCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "sales_force", "update")
    ctx = await entity_ctx(request)
    sales = await db.users.find_one({"id": payload.sales_id, "role": {"$in": roles_in_category("sales")}},
                                    {"_id": 0, "name": 1, "home_entity_id": 1})
    if not sales:
        raise HTTPException(status_code=400, detail="Salesperson tidak valid")
    doc = {
        "id": new_id("sinc"),
        "sales_id": payload.sales_id,
        "sales_name": sales.get("name", ""),
        # FASE E-0 (L12) — entitas insentif = entitas HOME salesnya.
        "entity_id": (sales.get("home_entity_id") or payload.entity_id
                      or ctx.active_entity_id or DEFAULT_ENTITY_ID),
        "period": payload.period,
        "basis": payload.basis,
        "tiers": [t.model_dump() for t in payload.tiers],
        "bonus_new_customer": float(payload.bonus_new_customer or 0),
        "bonus_focus_product": float(payload.bonus_focus_product or 0),
        "notes": payload.notes,
        "status": "draft",
        "created_by": actor["name"],
        "created_at": now_iso(),
    }
    await db.sales_incentives.update_one(
        {"sales_id": payload.sales_id, "period": payload.period},
        {"$set": {k: v for k, v in doc.items() if k != "id"},
         "$setOnInsert": {"id": doc["id"]}},
        upsert=True,
    )
    saved = safe_doc(await db.sales_incentives.find_one({"sales_id": payload.sales_id, "period": payload.period}, {"_id": 0}))
    await audit(actor["name"], "sales_incentive_set", "sales_incentive", saved["id"], saved)
    return saved
