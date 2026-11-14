"""Customer/CRM service (KN_17 CRM-lite).

Derivasi kredit (AR/overdue/status), Customer 360, dan row-level scoping.
SSOT tunggal `customers`. KPI & kredit = DERIVED dari sales_orders/payments/price_approvals.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from db import db
from core_utils import safe_doc, DEFAULT_ENTITY_ID, rupiah, to_cents, from_cents
# PR-T6 — lintas PT dari himpunan HIDUP `CROSS_ENTITY_ROLES` (pengaturan per peran), bukan daftar nama admin/manager.
from role_registry import CROSS_ENTITY_ROLES
from services.data_scope import in_clause, own_scoped, owner_ids, owner_ids_now   # PR-T4 — cakupan data peran

# KF-T7 (CR-03) — ambang kontrol kredit (KN_17 §5.2) dulu dua salinan konstanta di sini dan di `ar_aging_service`
# (80 % plafon → peringatan; telat terlama > 14 hari → diblokir). Kini pengaturan `ar.credit_warning_pct` dan
# `ar.overdue_block_days` per PT, dibaca SATU fungsi (`credit_thresholds`). CR-T1 — fungsi itu dibaca
# `credit_profile_service.effective` (ditimpa profil kredit pelanggan per PT); status = `credit_profile_service.status_from`.
NON_AR_METHODS = {"kontan", "tunai", "cash"}
DEAD_STATUSES = {"cancelled", "draft", "expired", "rejected"}


# ─── SALES REVAMP V2 — Sales team (PIC + co-sales + split) di level CUSTOMER ───
async def group_sales_max(entity_id: Optional[str]) -> int:
    """KF-T7 — maksimum anggota tim sales per pelanggan/pesanan (`sales.group_sales_max_members`, per PT; dulu
    konstanta 2). Dipanggil pemanggil asinkron lalu dikirim ke `apply_group_sales_rule`."""
    from services.nilai_pengaturan import nilai
    return int(await nilai("sales.group_sales_max_members", entity_id))


def apply_group_sales_rule(members: List[Dict[str, Any]], max_members: int) -> None:
    """K-5 (feedback klien 2026-09) — group sales maksimal `max_members` orang (KF-T7: pengaturan
    `sales.group_sales_max_members`, bawaan 2); bila split tidak diisi (semua 0) dibagi rata otomatis
    (2 orang → 50-50, 1 orang → 100)."""
    if len(members) > max_members:
        raise HTTPException(status_code=400, detail=f"Group sales maksimal {max_members} orang "
                                                    f"(1 PIC + {max(max_members - 1, 0)} co-sales).")
    if members and all(m["split_pct"] <= 0 for m in members):
        share = round(100.0 / len(members), 2)
        for m in members:
            m["split_pct"] = share
        members[-1]["split_pct"] = round(100.0 - share * (len(members) - 1), 2)


def normalize_sales_team(raw: Any, assigned_sales_id: str = "", assigned_sales_name: str = "", *,
                         max_members: int) -> List[Dict[str, Any]]:
    """Validasi + normalisasi tim sales customer/order (join/group sales).

    - PIC.sales_id = kunci kepemilikan (== assigned_sales_id).
    - Kosong + ada assigned_sales_id → PIC tunggal 100%.
    - Bila diisi: tepat 1 PIC, Σ split_pct == 100 (toleransi 0.01), tak duplikat, tiap split > 0.
    """
    members: List[Dict[str, Any]] = []
    for m in (raw or []):
        d = m.model_dump() if hasattr(m, "model_dump") else dict(m)
        sid = (d.get("sales_id") or "").strip()
        if not sid:
            continue
        members.append({
            "sales_id": sid,
            "name": (d.get("name") or "").strip(),
            "role": "pic" if d.get("role") == "pic" else "co",
            "split_pct": round(float(d.get("split_pct") or 0), 2),
        })
    if not members:
        if assigned_sales_id:
            return [{"sales_id": assigned_sales_id, "name": assigned_sales_name or "", "role": "pic", "split_pct": 100.0}]
        return []
    apply_group_sales_rule(members, max_members)
    ids = [m["sales_id"] for m in members]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Anggota sales tim tidak boleh duplikat.")
    if any(m["split_pct"] <= 0 for m in members):
        raise HTTPException(status_code=400, detail="Setiap anggota sales tim harus punya split insentif > 0%.")
    pic_members = [m for m in members if m["role"] == "pic"]
    if len(pic_members) == 0:
        members[0]["role"] = "pic"
    elif len(pic_members) > 1:
        raise HTTPException(status_code=400, detail="Sales tim harus punya tepat 1 PIC (penanggung jawab).")
    total = round(sum(m["split_pct"] for m in members), 2)
    if abs(total - 100.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"Total split insentif harus 100% (saat ini {total}%).")
    return members


def pic_of(team: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for m in (team or []):
        if m.get("role") == "pic":
            return m
    return (team or [None])[0]


def resolve_customer_sales_team(customer: Dict[str, Any]) -> List[Dict[str, Any]]:
    """SO mewarisi tim sales dari customer; fallback PIC tunggal dari assigned_sales_id."""
    team = customer.get("sales_team") or []
    if team:
        return team
    aid = customer.get("assigned_sales_id") or ""
    if aid:
        return [{"sales_id": aid, "name": customer.get("assigned_sales_name") or "", "role": "pic", "split_pct": 100.0}]
    return []


async def resolve_team_names(team: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Isi `name` tiap anggota dari koleksi users (bila kosong)."""
    out = []
    for m in (team or []):
        nm = m.get("name") or ""
        if not nm and m.get("sales_id"):
            u = await db.users.find_one({"id": m["sales_id"]}, {"_id": 0, "name": 1})
            nm = (u or {}).get("name", "")
        out.append({**m, "name": nm})
    return out


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        try:
            dt = datetime.strptime(str(value)[:10], "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None


def _order_grand_total(o: Dict[str, Any]) -> float:
    """NILAI TAGIHAN pesanan = grand total + Σ tagihan tambahan nota debit (`extra_billing_lines[].gross`, PK-32 · K-14).
    Satu-satunya pembaca nilai tagihan untuk sisa tagihan, status bayar, alokasi, dan umur piutang; `grand_total` dan
    `items[]` pesanan sendiri tidak pernah diubah nota."""
    base = float(o.get("grand_total", o.get("total_amount", 0)) or 0)
    extra = sum(float(x.get("gross") or 0) for x in (o.get("extra_billing_lines") or []) if isinstance(x, dict))
    return round(base + extra, 2) if extra else base


def _order_paid(o: Dict[str, Any]) -> float:
    return sum(float(p.get("amount", 0) or 0) for p in (o.get("payments") or []))


def order_payment_method(o: Dict[str, Any]) -> str:
    """SSOT tunggal deteksi metode bayar order (P3-7).

    Selalu cek `payment_profile_method` DAN `payment_term_code` agar konsisten di
    credit engine, collection worklist, dan AR receipt (hindari drift NON_AR).
    """
    return str((o.get("payment_profile_method") or o.get("payment_term_code") or "")).lower()


def _term_days(customer: Dict[str, Any], order: Dict[str, Any],
               terms: Optional[Dict[Any, Optional[int]]] = None) -> int:
    """Termin snapshot SO menang; G3 D4-FIN-02 — termin 0 (tunai/COD) tetap 0, bukan jadi 30.

    F-16 — bila `terms` (peta `(kode, entitas) → net_days` dari `report_basis.peta_termin`) diberikan, kode termin SO
    (CBD = 0, NET30 = 30, DP50 = 14, …) dipakai SEBELUM profil pelanggan: SO CBD tidak lagi tampil
    "30 hari lagi" hanya karena profil pelanggannya NET30."""
    pp = customer.get("payment_profile") or {}
    if order.get("payment_term_days") not in (None, ""):
        try:
            return max(0, int(order["payment_term_days"]))
        except (TypeError, ValueError):
            pass
    code = order.get("payment_term_code") or ""
    if terms is not None and code:
        nd = terms.get((code, order.get("entity_id") or ""))
        if nd is not None:
            return max(0, int(nd))
    if pp.get("term_days") not in (None, ""):
        try:
            return max(0, int(pp["term_days"]))
        except (TypeError, ValueError):
            pass
    return 30


async def credit_thresholds(entity_id: Optional[str],
                            cache: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """KF-T7 (CR-03) — SATU-SATUNYA pembaca dua ambang kredit untuk PT `entity_id`:
    `{"block_days": ar.overdue_block_days, "warning_ratio": ar.credit_warning_pct ÷ 100}`. CR-T1 — dibaca
    `credit_profile_service.effective` (nilai bawaan PT; profil kredit pelanggan boleh menimpa hari blokir), yang
    hasilnya dipakai `status_from` (kartu pelanggan, pemeriksaan kredit pesanan, umur piutang, beranda).
    `cache` (opsional, per panggilan daftar) = satu kali baca per PT."""
    key = entity_id if entity_id and entity_id != "all" else ""
    if cache is not None and key in cache:
        return cache[key]
    from services.nilai_pengaturan import nilai
    out = {"block_days": int(await nilai("ar.overdue_block_days", key)),
           "warning_ratio": round(float(await nilai("ar.credit_warning_pct", key)) / 100.0, 6)}
    if cache is not None:
        cache[key] = out
    return out


async def compute_customer_credit(customer: Dict[str, Any], entity_id: Optional[str] = None,
                                  cache: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """AR outstanding, overdue, dan status kredit (active|warning|blocked).
    `entity_id` (opsional) membatasi AR ke SO badan usaha itu (KPI per entitas = AR Aging).
    CR-T1 — plafon, hari blokir, dan blokir manual dari profil kredit (pelanggan, PT) yang BERLAKU
    (`credit_profile_service.effective`; PT = `entity_id`, atau PT pemilik data pelanggan bila tidak diberikan), status
    dari `credit_profile_service.status_from`. `cache` (opsional, `credit_profile_service.cache_baru()`) = pemanggil daftar
    membaca ambang & plafon bawaan sekali per PT."""
    from services import credit_profile_service as cps
    pt = entity_id if entity_id and entity_id != "all" else (customer.get("entity_id") or "")
    eff = await cps.effective(customer["id"], pt, customer=customer, cache=cache)
    cid = customer["id"]
    credit_limit = float(eff["credit_limit"] or 0)
    # PK-41 (RP-01, RP-03) — kursor tanpa batas (dulu 2.000 pesanan), status mati & pesanan lunas disaring di kueri;
    # jatuh tempo, lewat tempo, dan telat terlama dari BARIS TAGIHAN TERKIRIM (per surat jalan, `report_basis`), bukan
    # seluruh sisa pesanan pada jatuh tempo surat jalan pertama. Bagian yang belum dikirim tidak pernah telat.
    oq: Dict[str, Any] = {"customer_id": cid, "status": {"$nin": sorted(DEAD_STATUSES)},
                          "payment_status": {"$ne": "paid"}}
    if entity_id and entity_id != "all":
        oq["entity_id"] = entity_id
    orders = [o async for o in db.sales_orders.find(oq, {"_id": 0})]
    from services import report_basis as rb
    from services.book_date import tanggal_buku
    lines_by_order = await rb.baris_tagihan(orders, {cid: customer}, per=tanggal_buku())
    ar = ledger = overdue = 0   # sen bulat (`02` D5)
    max_overdue_days = 0
    open_orders = 0
    for rows in lines_by_order.values():
        if not rows:
            continue
        open_orders += 1
        sm = rb.ringkas_baris(rows)
        ar += to_cents(sm["total"])
        ledger += to_cents(sm["ar_ledger"])
        # Keputusan pemilik K-01 (26 Okt) — "lewat tempo" = definisi layar Piutang (`ar_aging_service`) & daftar tagih
        # (`collection_worklist`): mulai 1 hari PENUH setelah jatuh tempo (`report_basis.hari_antara`, tanggal WIB).
        overdue += to_cents(sm["overdue"])
        max_overdue_days = max(max_overdue_days, sm["oldest_days"])
    ar, ledger, overdue = from_cents(ar), from_cents(ledger), from_cents(overdue)
    # CR-T1 — blokir manual kini di profil kredit (dulu `customers.status == "blocked"`); telat > 0 hari ⇔ overdue > 0
    status = cps.status_from(eff, ar, max_overdue_days)
    return {
        "credit_limit": credit_limit,
        "ar_outstanding": ar,
        "ar_ledger": ledger,
        "exposure": from_cents(to_cents(ar) - to_cents(ledger)),
        "overdue_amount": overdue,
        "max_overdue_days": max_overdue_days,
        "open_orders": open_orders,
        "available_credit": round(max(credit_limit - ar, 0), 2) if credit_limit > 0 else None,
        "deposit_balance": round(float(customer.get("deposit_balance", 0) or 0), 2),
        "status": status,
        # CR-T1 (L6) — asal nilai yang dipakai mesin: kartu pelanggan & pemeriksaan kredit pesanan menuliskannya.
        "limit_source": eff["limit_source"], "profile_entity_id": eff["entity_id"],
        "overdue_block_days": eff["overdue_block_days"], "block_days_source": eff["block_days_source"],
        "warning_ratio": eff["warning_ratio"], "credit_status_manual": eff["credit_status"],
        "block_reason": eff["block_reason"],
    }


async def enrich_customer(customer: Dict[str, Any], with_credit: bool = True) -> Dict[str, Any]:
    """Tambah assigned_sales_name + ringkasan kredit ke dokumen customer."""
    c = safe_doc(customer)
    if c.get("assigned_sales_id") and not c.get("assigned_sales_name"):
        u = await db.users.find_one({"id": c["assigned_sales_id"]}, {"_id": 0, "name": 1})
        c["assigned_sales_name"] = (u or {}).get("name", "")
    if with_credit:
        c["credit"] = await compute_customer_credit(c)
    return c


async def check_credit_for_order(customer: Dict[str, Any], new_amount: float) -> Dict[str, Any]:
    """Gate kredit saat buat SO (KN_17 §5.2). allowed=False bila blocked.
    CR-T1 — plafon & rasio peringatan dari profil kredit yang berlaku (PT pemilik data pelanggan; PT pesanan = CR-T3)."""
    credit = await compute_customer_credit(customer)
    limit = credit["credit_limit"]
    projected = credit["ar_outstanding"] + float(new_amount or 0)
    blocked = credit["status"] == "blocked" or (limit > 0 and projected > limit)
    warn = (not blocked) and (
        credit["status"] == "warning" or (limit > 0 and projected >= credit["warning_ratio"] * limit)
        or credit["overdue_amount"] > 0
    )
    reasons = []
    if limit > 0 and projected > limit:
        reasons.append(f"Proyeksi AR {rupiah(projected)} melebihi limit {rupiah(limit)}")
    if credit["overdue_amount"] > 0:
        reasons.append(f"Ada tunggakan jatuh tempo {rupiah(credit['overdue_amount'])} ({credit['max_overdue_days']} hari)")
    if credit.get("credit_status_manual") == "blokir_manual":
        alasan = credit.get("block_reason") or ""
        reasons.append("Pelanggan diblokir manual" + (f": {alasan}" if alasan else ""))
    return {
        "allowed": not blocked,
        "level": "blocked" if blocked else ("warning" if warn else "ok"),
        "credit": credit,
        "projected_ar": round(projected, 2),
        "reasons": reasons,
    }


# SO yang tidak dihitung sebagai pesanan/omzet pelanggan (riwayat tetap menampilkannya).
DEAD_ORDER_STATUSES = ("cancelled", "expired")


async def customer_360(customer_id: str) -> Optional[Dict[str, Any]]:
    """Profil lengkap + riwayat order/dokumen/special price + kredit."""
    customer = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0}))
    if not customer:
        return None
    customer = await enrich_customer(customer, with_credit=True)
    orders = await db.sales_orders.find(
        {"customer_id": customer_id},
        {"_id": 0, "id": 1, "number": 1, "status": 1, "payment_status": 1,
         "grand_total": 1, "total_amount": 1, "created_at": 1, "sales_name": 1, "payments": 1,
         "extra_billing_lines": 1},   # PK-32 — nilai tagihan
    ).sort("created_at", -1).to_list(100)
    order_history = []
    for o in orders:
        order_history.append({
            "id": o.get("id"), "number": o.get("number"), "status": o.get("status"),
            "payment_status": o.get("payment_status"), "grand_total": _order_grand_total(o),
            "paid": _order_paid(o), "created_at": o.get("created_at"), "sales_name": o.get("sales_name", ""),
        })
    docs = await db.generated_documents.find(
        {"customer_id": customer_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    if not docs:  # fallback: dokumen tertaut via order
        oids = [o.get("id") for o in orders]
        if oids:
            docs = await db.generated_documents.find(
                {"order_id": {"$in": oids}}, {"_id": 0}
            ).sort("created_at", -1).to_list(100)
    special_prices = await db.price_approvals.find(
        {"customer_id": customer_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    followups = await db.collection_followups.find(
        {"customer_id": customer_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    overrides = await db.credit_overrides.find(
        {"customer_id": customer_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    # §3-C — riwayat sample yang pernah dipotong untuk pelanggan ini (baris SO ber-is_sample)
    sample_orders = await db.sales_orders.find(
        {"customer_id": customer_id, "has_sample": True},
        {"_id": 0, "id": 1, "number": 1, "status": 1, "items": 1, "created_at": 1}
    ).sort("created_at", -1).to_list(100)
    samples = [{"id": o["id"], "number": o.get("number"), "product_name": it.get("product_name"), "sku": it.get("sku"),
                "length": it.get("base_quantity") or it.get("quantity"), "unit": it.get("base_unit") or it.get("unit"),
                "amount": it.get("line_total") or it.get("subtotal"), "status": it.get("sample_cut_status") or o.get("status"),
                "child_roll_no": it.get("child_roll_no"), "created_at": o.get("created_at"), "cut_at": it.get("cut_at")}
               for o in sample_orders for it in o.get("items", []) if it.get("is_sample")]
    # Sesi 16 — kwitansi penerimaan pelanggan (HP sales: tab Kwitansi)
    payments = await db.ar_receipts.find(
        {"customer_id": customer_id, "status": {"$ne": "void"}},
        {"_id": 0, "id": 1, "number": 1, "amount": 1, "method": 1, "receipt_date": 1, "created_at": 1, "notes": 1}
    ).sort("created_at", -1).to_list(50)
    # UAT 24 Okt (audit UI tahap 2) — G2-08: jumlah pesanan & LTV dulu ikut menghitung SO batal/kedaluwarsa
    # ("1 order · LTV Rp 224.573" untuk pelanggan yang satu-satunya pesanannya dibatalkan). Riwayat tetap utuh.
    live_orders = [o for o in order_history if o.get("status") not in DEAD_ORDER_STATUSES]
    return {
        **customer,
        "payments": payments,
        "order_history": order_history,
        "document_history": [safe_doc(d) for d in docs],
        "special_price_history": [safe_doc(s) for s in special_prices],
        "collection_followups": [safe_doc(f) for f in followups],
        "credit_overrides": [safe_doc(o) for o in overrides],
        "sample_history": [safe_doc(s) for s in samples],
        "stats": {
            "total_orders": len(live_orders),
            "lifetime_value": round(sum(o["grand_total"] for o in live_orders), 2),
            "cancelled_orders": len(order_history) - len(live_orders),
            "samples_cut": sum(1 for s in samples if s.get("status") == "done"),
        },
    }


def own_customer_clause(user: Dict[str, Any]) -> Dict[str, Any]:
    """Pelanggan "milik" sales: PIC (`assigned_sales_id`), anggota tim sales, atau pelanggan umum/walk-in PT
    (`shared_walk_in`, keputusan pemilik P14-K2 24 Okt: satu per PT, boleh dipakai semua sales).
    PR-T4 — pemilik = `owner_ids` pengguna (cakupan "tim" ikut memuat anggota timnya)."""
    v = in_clause(owner_ids_now(user) or [(user or {}).get("id") or "__tanpa_pemilik__"])
    return {"$or": [{"assigned_sales_id": v}, {"sales_team.sales_id": v}, {"shared_walk_in": True}]}


def scope_query(user: Dict[str, Any], base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Row-level scoping (KN_17 §4, E8.10): cakupan data bukan "semua" (bawaan Sales) → hanya pelanggan
    miliknya/timnya (+ walk-in PT). PR-T4: dibaca dari sifat peran `data_scope`."""
    q = dict(base or {})
    if user and own_scoped(user):
        ands = list(q.pop("$and", []) or [])
        ands.append(own_customer_clause(user))
        q["$and"] = ands
    return q


async def can_access_customer(user: Dict[str, Any], customer: Dict[str, Any]) -> bool:
    if not user or not customer:
        return False
    role = user.get("role")
    # Peran lintas PT (bawaan: Admin & Manajer; diatur per peran) → oversight semua entitas.
    if role in CROSS_ENTITY_ROLES:
        return True
    # INV-ENTITY-01 (KN-076-IDOR-READ-SUBRES P0): isolasi lintas-entitas untuk role ter-scope.
    # Dokumen customer di luar entitas yang diizinkan aktor → TOLAK, walau assigned_sales_id cocok
    # (seed bisa meng-assign sales ke customer entitas lain — tetap tak boleh diakses lintas-PT).
    if not _entity_allowed(user, customer):
        return False
    if own_scoped(user):   # PR-T4 — cakupan data peran (bawaan Sales: milik sendiri)
        ids = await owner_ids(user) or []
        return (customer.get("assigned_sales_id") in ids or bool(customer.get("shared_walk_in"))
                or any(m.get("sales_id") in ids for m in customer.get("sales_team") or []))
    return True


def _entity_allowed(user: Dict[str, Any], customer: Dict[str, Any]) -> bool:
    ent = customer.get("entity_id")
    allowed = user.get("allowed_entity_ids") or (
        [user.get("home_entity_id")] if user.get("home_entity_id") else []
    )
    return not (ent and allowed and ent not in allowed)


async def can_collect_customer(user: Dict[str, Any], customer: Dict[str, Any]) -> bool:
    """Penagihan: pelanggan milik sales ATAU pelanggan yang pernah ia pesankan (pesanan buatannya)."""
    if await can_access_customer(user, customer):
        return True
    if not own_scoped(user) or not _entity_allowed(user, customer):
        return False
    ids = await owner_ids(user) or [user.get("id")]
    return bool(await db.sales_orders.find_one({"customer_id": customer.get("id"), "sales_id": in_clause(ids)},
                                               {"_id": 1}))


def can_view_credit(user: Dict[str, Any], customer: Dict[str, Any]) -> bool:
    """Status kredit saat checkout: sales boleh melihat pelanggan mana pun yang bisa ia pesankan (entitas sama)."""
    if user.get("role") in CROSS_ENTITY_ROLES:   # PR-T6
        return True
    return _entity_allowed(user, customer)


async def collection_worklist(
    user: Dict[str, Any], sales_id: Optional[str] = None, entity_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Daftar tagihan (order outstanding) untuk follow-up penagihan (KN_17 paragraf 7)."""
    cust_filter: Dict[str, Any] = {}
    # PR-T4 — cakupan data peran: pemilik = `owner_ids` (bawaan Sales: dirinya; "tim": + anggota timnya).
    own = (await owner_ids(user) or None) if own_scoped(user) else None
    own_sales = in_clause(own) if own else None
    if own_sales:
        # Pelanggan miliknya DITAMBAH pelanggan dari pesanan yang ia buat sendiri.
        own_cids = await db.sales_orders.distinct("customer_id", {"sales_id": own_sales})
        cust_filter["$or"] = [{"assigned_sales_id": own_sales}, {"id": {"$in": own_cids}}]
    elif sales_id:
        cust_filter["assigned_sales_id"] = sales_id
    if entity_id and entity_id != "all":
        cust_filter["entity_id"] = entity_id
    # PK-41 (RP-01) — pelanggan & pesanan dibaca dengan kursor tanpa batas (dulu 3.000 / 8.000).
    customers = [c async for c in db.customers.find(
        cust_filter, {"_id": 0, "id": 1, "name": 1, "assigned_sales_id": 1, "payment_profile": 1})]
    cmap = {c["id"]: c for c in customers}
    cust_ids = list(cmap.keys())
    rows: List[Dict[str, Any]] = []
    if not cust_ids:
        return rows
    assigned_ids = [c["id"] for c in customers if not own or c.get("assigned_sales_id") in own]
    oq: Dict[str, Any] = {"customer_id": {"$in": cust_ids}}
    if own_sales:
        oq = {"$or": [{"customer_id": {"$in": assigned_ids}}, {"customer_id": {"$in": cust_ids}, "sales_id": own_sales}]}
    oq = {"$and": [oq, {"status": {"$nin": sorted(DEAD_STATUSES)}, "payment_status": {"$ne": "paid"}}]}
    orders = [o async for o in db.sales_orders.find(
        oq,
        {"_id": 0, "id": 1, "number": 1, "customer_id": 1, "customer_name": 1,
         "status": 1, "payment_status": 1, "grand_total": 1, "total_amount": 1, "extra_billing_lines": 1,
         "payments": 1, "created_at": 1, "sales_name": 1, "payment_term_code": 1,
         "payment_term_days": 1, "payment_profile_method": 1, "entity_id": 1})]
    # PK-41 (RP-03) — yang ditagih = BARIS TERKIRIM (per surat jalan) yang masih bersisa: jatuh tempo = jatuh tempo
    # tertua, `days_late` = telat terlama, `outstanding` = sisa bagian terkirim; bagian belum dikirim (`exposure`) belum
    # punya jatuh tempo (F-16) dan tidak ditagih.
    from services import report_basis as rb
    from services.book_date import tanggal_buku
    lines_by_order = await rb.baris_tagihan(orders, cmap, per=tanggal_buku())
    for o in orders:
        sm = rb.ringkas_baris(lines_by_order.get(o["id"]) or [])
        if sm["due_date"] is None:
            continue   # F-16 — belum dikirim: belum punya jatuh tempo (bukan "30 hari lagi")
        c = cmap.get(o["customer_id"], {})
        rows.append({
            "order_id": o.get("id"), "order_number": o.get("number"),
            "customer_id": o.get("customer_id"), "customer_name": o.get("customer_name"),
            "assigned_sales_id": c.get("assigned_sales_id", ""),
            "outstanding": sm["ar_ledger"],
            "exposure": sm["exposure"],
            "due_date": sm["due_date"],
            "days_late": sm["max_days"],
            "overdue": sm["max_days"] > 0,
            "sales_name": o.get("sales_name", ""),
            "via_own_order": bool(own_sales and c.get("assigned_sales_id") != own_sales),
        })
    rows.sort(key=lambda r: r["days_late"], reverse=True)
    return rows


async def evaluate_credit_gate(customer: Dict[str, Any], amount: float) -> Dict[str, Any]:
    """Gate kredit saat buat SO (KN_17 S37 / pilihan owner 1b+2a).

    blocked + tanpa override approved -> tolak. blocked + override approved (cukup nilainya)
    -> boleh lanjut (override akan dikonsumsi). warning -> boleh lanjut (flag).
    """
    gate = await check_credit_for_order(customer, amount)
    override = None
    if not gate["allowed"]:
        ov = await db.credit_overrides.find_one(
            {"customer_id": customer["id"], "status": "approved", "consumed": {"$ne": True}},
            {"_id": 0}, sort=[("decided_at", -1)],
        )
        if ov:
            amt = float(ov.get("amount") or 0)
            if amt <= 0 or float(amount or 0) <= amt + 1e-6:
                override = ov
    return {
        "level": gate["level"],                       # ok | warning | blocked
        "blocked": not gate["allowed"],
        "allowed_after_override": bool(override),
        "reasons": gate["reasons"],
        "credit": gate["credit"],
        "projected_ar": gate["projected_ar"],
        "override": override,
    }


async def collection_reminders(
    user: Dict[str, Any], days_ahead: int = 7, sales_id: Optional[str] = None, entity_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Reminder penagihan (KN_17 §7 / 4b): overdue + akan jatuh tempo <= days_ahead, + flag reminded."""
    rows = await collection_worklist(user, sales_id=sales_id, entity_id=entity_id)
    span = abs(int(days_ahead or 0))
    sel = [r for r in rows if r["days_late"] >= -span]
    if not sel:
        return []
    order_ids = [r["order_id"] for r in sel]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    fus = await db.collection_followups.find(
        {"order_id": {"$in": order_ids}, "outcome": "reminded", "created_at": {"$gte": cutoff}},
        {"_id": 0, "order_id": 1},
    ).to_list(4000)
    reminded = {f["order_id"] for f in fus}
    for r in sel:
        r["reminded"] = r["order_id"] in reminded
        r["due_soon"] = (not r["overdue"]) and r["days_late"] >= -span
    sel.sort(key=lambda r: r["days_late"], reverse=True)
    return sel
