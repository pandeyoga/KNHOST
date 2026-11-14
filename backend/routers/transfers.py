"""Warehouse Transfer router: multi-warehouse transfer workflow with approval."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, Query, Response
from pymongo import ReturnDocument
from db import db
from services import approval_policy_service as _aps   # KP-T4 — satu tabel kebijakan persetujuan
from services import dual_qty_service as _dual  # FASE U — dua satuan (roll + ukuran)
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc, next_doc_number
from schemas import (TransferCreate, TransferApprove, TransferReject, TransferStatusUpdate,
                     TransferReceiveIn, TransferExceptionIn, TransferExceptionResolveIn)
from services import transfer_receipt_service as trs   # P03 — transfer terkait SO + penerimaan aktual
from entity_scope import entity_ctx, resolve_scope_ids
from services import line_scope              # FASE L — pagar & penyaring lini produk
from services.roll_service import (
    execute_ownership_transfer, release_transfer_rolls,
    resolve_stock_owner, reserve_rolls_for_wh_transfer, dispatch_wh_transfer_rolls,
    release_wh_transfer_rolls, transfer_held_rolls,
)
from services import gl_service

router = APIRouter(prefix="/api")


# P16 — transisi OPERASIONAL saja lewat POST /status. Approve/reject/cancel punya
# endpoint sendiri (izin terpisah + pelepasan roll), jadi tidak boleh lewat jalur ini.
STATUS_TRANSITIONS = {
    "approved": ["picking"],
    "picking": ["staging"],
    "staging": ["dispatched"],
    "dispatched": ["completed"],
}
_DEDICATED_STATUS_ROUTES = {
    "cancelled": "DELETE /api/transfers/{id}?reason=…",
    "approved": "POST /api/transfers/{id}/approve",
    "rejected": "POST /api/transfers/{id}/reject",
}


def _validate_status_transition(current: str, new: str) -> bool:
    """Check if status transition is valid."""
    return new in STATUS_TRANSITIONS.get(current, [])


# ─── FASE E-0 (E0.8b / L13-L14) — cakupan entitas untuk transfer gudang ──────
# Sebelumnya SELURUH endpoint `/api/transfers*` tidak punya cakupan entitas sama
# sekali: gudang PT Kain Suka Cita bisa membuka `TRF-00003` dengan konteks CV Kanda
# Suka (HTTP 200), dan `warehouse_transfers` tak terdaftar di `SCOPED_COLLECTIONS`.
#
# Aturan khusus (transfer bisa ANTAR-entitas, jadi bukan filter satu field):
#   * transfer INTRA-entitas  → terlihat hanya oleh entitas `entity_id`.
#   * transfer ANTAR-entitas  → terlihat oleh **kedua** entitas
#                               (`source_entity_id` ATAU `dest_entity_id` ∈ allowed),
#     tetapi hanya entitas ASAL yang boleh menyetujui pengiriman dan entitas
#     TUJUAN yang boleh menerima (dijaga `_assert_transfer_side`).

def _transfer_scope_clause(ids):
    """Klausa Mongo: transfer yang boleh DILIHAT oleh daftar entitas `ids`."""
    return {"$or": [
        {"entity_id": {"$in": list(ids)}},
        {"source_entity_id": {"$in": list(ids)}},
        {"dest_entity_id": {"$in": list(ids)}},
    ]}


def _transfer_entities(transfer):
    """Entitas yang terlibat pada satu transfer (intra & antar-entitas)."""
    out = {transfer.get("entity_id"), transfer.get("source_entity_id"),
           transfer.get("dest_entity_id")}
    return {e for e in out if e}


async def _guard_transfer(request: Request, transfer_id: str, side: str = "any"):
    """Ambil transfer + tegakkan cakupan entitas. 404 bila di luar entitas yang boleh.

    `side="source"` → hanya entitas ASAL (menyetujui/mengirim/membatalkan).
    `side="dest"`   → hanya entitas TUJUAN (menerima).
    """
    ctx = await entity_ctx(request)
    ids = set(resolve_scope_ids(ctx))
    transfer = await db.warehouse_transfers.find_one({"id": transfer_id}, {"_id": 0})
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer tidak ditemukan")
    if not (_transfer_entities(transfer) & ids):
        raise HTTPException(status_code=404, detail="Transfer tidak ditemukan untuk entitas ini")
    if transfer.get("transfer_kind") == "inter_entity" and side in ("source", "dest"):
        need = transfer.get("source_entity_id") if side == "source" else transfer.get("dest_entity_id")
        if need and need not in ids:
            label = "asal" if side == "source" else "tujuan"
            raise HTTPException(
                status_code=403,
                detail=f"Hanya entitas {label} transfer ini yang boleh melakukan aksi tersebut.")
    # FIX-1 (B2a STM-IN-02, B3a SCP-2) — pagar LOKASI di detail & setiap aksi transfer. Dulu tidak ada sama sekali:
    # petugas Rancamalang menerima transfer di WH-JKT (200, roll mendarat di Jakarta). Sisi aksi: asal untuk
    # setujui/tolak/kirim/batal, tujuan untuk terima/pengecualian; baca = salah satu sisi di lokasi tugas.
    from services import location_scope
    if side == "source":
        await location_scope.assert_doc_side(ctx.user, transfer, "source_warehouse_id", "mengirim transfer dari gudang ini")
    elif side == "dest":
        await location_scope.assert_doc_side(ctx.user, transfer, "dest_warehouse_id", "menerima transfer di gudang ini")
    elif not location_scope.doc_in_scope("warehouse_transfers", transfer, ctx.warehouse_ids):
        raise HTTPException(status_code=404, detail="Data di luar lokasi tugas Anda")
    return transfer, ctx


@router.get("/transfers")
async def list_transfers(
    request: Request,
    response: Response,
    status: Optional[str] = Query(None),
    warehouse_id: Optional[str] = Query(None),
    transfer_kind: Optional[str] = Query(None),
    line: str = Query("", description="FASE L — penyaring lini (koma untuk multi)"),
    sales_order_id: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None, description="FIX-1 — saringan PT (bawaan: semua PT yang ditugaskan)"),
    limit: int = Query(200, description="FIX-5 — 1–500 (bawaan 200)"),
    skip: int = Query(0, description="FIX-5 — geser halaman"),
) -> List[Dict[str, Any]]:
    """List all transfers with optional filtering by status, warehouse, or transfer_kind.
    FIX-5 (B3b LST-01) — `skip`/`limit` + `X-Total-Count`/`X-Truncated` (dulu 200 terbaru dipotong diam-diam)."""
    actor = await require_permission(request, "transfer", "view")
    ctx = await entity_ctx(request)
    # FIX-1 (K-B1-02, B3a SCP-2) — daftar transfer per GEDUNG dalam lokasi kerja (asal ATAU tujuan; dulu tanpa
    # lokasi sama sekali: petugas Soreang melihat 15 transfer termasuk Jakarta) dan lintas PT yang ditugaskan
    # (`entity_id` = saringan PT eksplisit). Gedung data uji tidak ikut tampilan "semua lokasi".
    from services import location_scope
    if entity_id and entity_id != "all":
        if entity_id not in ctx.allowed_entity_ids:
            raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
        _ent_ids = [entity_id]
    else:
        _ent_ids = list(ctx.allowed_entity_ids)
    query_filter = location_scope.narrow_view(
        "warehouse_transfers", dict(_transfer_scope_clause(_ent_ids)), await location_scope.view_for(ctx))
    if sales_order_id:
        query_filter["sales_order_id"] = sales_order_id
    if status:
        query_filter["status"] = status
    if transfer_kind:
        # record lama tanpa field → dianggap intra_entity
        if transfer_kind == "intra_entity":
            query_filter["transfer_kind"] = {"$ne": "inter_entity"}
        else:
            query_filter["transfer_kind"] = transfer_kind
    if warehouse_id:
        query_filter = {"$and": [query_filter, {"$or": [
            {"source_warehouse_id": warehouse_id},
            {"dest_warehouse_id": warehouse_id},
        ]}]}
    
    from pagination import clamp_limit, window_headers, window_meta
    lim, sk = clamp_limit(limit, 200, 500), clamp_limit(skip, 0, 10 ** 6, minimum=0)
    _tq = line_scope.narrow(query_filter, actor, line, field=line_scope.LINES_FIELD)
    transfers = await db.warehouse_transfers.find(_tq, {"_id": 0}).sort("created_at", -1).skip(sk).to_list(lim)
    response.headers.update(window_headers(window_meta(
        await db.warehouse_transfers.count_documents(_tq), len(transfers), sk, lim)))
    
    # Enrich with warehouse/entity names and product details
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    entities = {e["id"]: e for e in await db.business_entities.find({}, {"_id": 0}).to_list(100)}
    
    def _ent_name(eid):
        e = entities.get(eid, {})
        return e.get("short_name") or e.get("legal_name") or (eid or "")
    
    for transfer in transfers:
        transfer["transfer_kind"] = transfer.get("transfer_kind", "intra_entity")
        transfer["work_entity_id"] = transfer.get("entity_id") or transfer.get("source_entity_id") or ""
        transfer["work_entity_name"] = _ent_name(transfer["work_entity_id"])
        transfer["source_warehouse_name"] = warehouses.get(transfer.get("source_warehouse_id"), {}).get("name", "")
        transfer["dest_warehouse_name"] = warehouses.get(transfer.get("dest_warehouse_id"), {}).get("name", "")
        transfer["source_entity_name"] = _ent_name(transfer.get("source_entity_id"))
        transfer["dest_entity_name"] = _ent_name(transfer.get("dest_entity_id"))
        for item in transfer.get("items", []):
            prod = products.get(item["product_id"], {})
            item.setdefault("sku", prod.get("sku", ""))
            item.setdefault("product_name", prod.get("name", ""))
    
    return transfers


@router.post("/transfers")
async def create_transfer(payload: TransferCreate, request: Request) -> Dict[str, Any]:
    """
    Create a new warehouse transfer.
    
    Default status: waiting_approval
    Requires permission: transfer.create
    """
    actor = await require_permission(request, "transfer", "create")
    
    # Validate warehouses exist
    source_wh = await db.warehouses.find_one({"id": payload.source_warehouse_id}, {"_id": 0})
    dest_wh = await db.warehouses.find_one({"id": payload.dest_warehouse_id}, {"_id": 0})
    
    if not source_wh:
        raise HTTPException(status_code=404, detail="Source warehouse tidak ditemukan")
    if not dest_wh:
        raise HTTPException(status_code=404, detail="Destination warehouse tidak ditemukan")
    if payload.source_warehouse_id == payload.dest_warehouse_id:
        raise HTTPException(status_code=400, detail="Source dan destination warehouse harus berbeda")
    # FIX-1 (STM-IN-02) — petugas berpagar hanya MENGIRIM dari gudang di lokasi tugasnya (tujuan boleh lokasi lain).
    from services import location_scope
    await location_scope.assert_warehouse(actor, payload.source_warehouse_id, "mengirim transfer dari gudang ini")

    # Validate products and items
    if not payload.items or len(payload.items) == 0:
        raise HTTPException(status_code=400, detail="Items tidak boleh kosong")

    ctx = await entity_ctx(request)
    prefer_owner = payload.owner_entity_id or (
        "" if getattr(ctx, "view_all", False) else (ctx.active_entity_id or "")
    )
    # E4.1 — transfer internal: KEDUA gudang harus boleh dipakai badan usaha ini.
    # (Jembatan gudang ANTAR badan usaha = tugas gudang transaksi Antar-PT / retur antar-PT — di sana gudang lawan memang
    #  sah. Rute lama `POST /api/transfers/inter-company` ditutup PK-30.)
    from services import warehouse_scope_service as whscope
    await whscope.assert_usable(payload.source_warehouse_id,
                               prefer_owner or ctx.active_entity_id,
                               action="mengambil barang dari sini",
                               field_label="Gudang asal", allow_inactive=True)
    await whscope.assert_usable(payload.dest_warehouse_id,
                               prefer_owner or ctx.active_entity_id,
                               action="mengirim barang ke sini",
                               field_label="Gudang tujuan")

    transfer_id = new_id("trn")
    # FASE E-1 (E1.7) — nomor dokumen PER BADAN USAHA. Sebelum ini semua transfer
    # memakai satu deret grup ("TRF-00001") sehingga dua badan usaha berebut nomor
    # yang sama dan nomornya melompat-lompat di mata pengguna.
    code = await next_doc_number("warehouse_transfers", "code", "TRF-",
                                 entity_id=prefer_owner or ctx.active_entity_id or None)

    so_id = (payload.sales_order_id or "").strip()
    so_doc = await trs.validate_so_link(so_id, "") if so_id else None

    # Roll-as-SSOT (KN_15 §9): reservasi roll di gudang sumber SAAT create (kunci stok).
    items_out: List[Dict[str, Any]] = []
    try:
        for item in payload.items:
            prod = await db.products.find_one({"id": item.product_id}, {"_id": 0})
            if not prod:
                raise HTTPException(status_code=404, detail=f"Product {item.product_id} tidak ditemukan")
            if item.qty <= 0 and not item.roll_ids:
                raise HTTPException(status_code=400, detail="Pilih roll yang akan dipindah.")
            # P03 IMP-26 — roll yang sudah berkomitmen ke SO ikut TANPA reservasi kedua.
            committed: List[Dict[str, Any]] = []
            if so_doc and item.roll_ids:
                committed = await db.inventory_rolls.find(
                    {"id": {"$in": list(item.roll_ids)}, "reserved_ref.id": so_id, "status": {"$in": ["reserved", "committed"]}},  # Cek UI UAT v3 (S10) — roll SO terkonfirmasi berstatus "committed"; dulu hanya "reserved" → transfer pemenuhan SO tak pernah bisa dipakai.
                    {"_id": 0, "id": 1, "owner_entity_id": 1}).to_list(len(item.roll_ids))
            committed_ids = [r["id"] for r in committed]
            rest = [rid for rid in (item.roll_ids or []) if rid not in committed_ids]
            if committed:
                owner = committed[0]["owner_entity_id"]
                await trs.validate_so_link(so_id, owner)
            else:
                owner = await resolve_stock_owner(item.product_id, payload.source_warehouse_id, prefer_owner,
                                                  allowed_owners=list(ctx.allowed_entity_ids or []))
            reserved: List[Dict[str, Any]] = []
            if committed_ids:
                reserved += await trs.attach_committed_rolls(transfer_id, so_id, committed_ids,
                                                             payload.source_warehouse_id, item.product_id)
            if rest or not item.roll_ids:
                reserved += await reserve_rolls_for_wh_transfer(
                    item.product_id, payload.source_warehouse_id, owner, float(item.qty), transfer_id,
                    roll_ids=rest,
                )
            # P02 DEV-G04 — gudang tujuan wajib lolos rules gudang (AND) untuk SETIAP roll yang dipindah
            from services import placement_rules as _pr
            for _r in reserved:
                _wv = await _pr.warehouse_violations(dest_wh, _r, prod)
                if _wv:
                    raise HTTPException(status_code=400, detail=f"Roll {_r.get('roll_no')}: {_wv[0]}")
            # Satuan SELALU dari master produk (aturan gudang: tidak ada ketik manual satuan).
            item.unit = prod.get("base_unit") or prod.get("unit") or "meter"
            if item.roll_ids:
                item.qty = round(sum(float(r.get("length_remaining", 0) or 0) for r in reserved), 2)
            roll_refs = [{
                "roll_id": r["id"], "roll_no": r.get("roll_no"), "lot": r.get("lot"),
                "length": float(r.get("length_remaining", 0) or 0),
                **({"committed_so": so_id} if r["id"] in committed_ids else {}),
            } for r in reserved]
            lots = sorted({r.get("lot") for r in reserved if r.get("lot")})
            item_doc = item.model_dump()
            item_doc.update({
                "owner_entity_id": owner, "sku": prod.get("sku", ""),
                "product_name": prod.get("name", ""), "lots": lots, "rolls": roll_refs,
                # FASE L — snapshot lini kerja MD (dipakai penyaring layar Transfer).
                "line_code": str(prod.get("line_code") or "").strip().lower(),
                # FASE U — jumlah roll DIHITUNG dari roll yang benar-benar direservasi.
                **(await _dual.stamp(item, rolls=len(roll_refs))),
            })
            items_out.append(item_doc)
        transfer = _build_transfer_doc(transfer_id, code, payload, prefer_owner, ctx, items_out)
        transfer["requested_by_id"] = actor.get("id", "")   # KF-T6 — pengaju andal (nama dari isian bisa apa saja)
        if so_doc:
            transfer.update({"sales_order_id": so_id, "sales_order_number": so_doc.get("number", ""),
                             "sales_order_customer": so_doc.get("customer_name", "")})
        await db.warehouse_transfers.insert_one(transfer)
        if so_doc:
            await db.sales_orders.update_one({"id": so_id}, {"$addToSet": {"linked_transfer_ids": transfer_id}})
    except Exception:
        await release_wh_transfer_rolls(transfer_id)   # kompensasi saga: reservasi parsial dilepas
        raise

    await audit(actor["name"], "transfer_created", "transfer", transfer["id"],
                {"code": code, "items": len(items_out)})
    
    return safe_doc(transfer)


def _build_transfer_doc(transfer_id, code, payload, prefer_owner, ctx, items_out) -> Dict[str, Any]:
    return {
        "id": transfer_id,
        "code": code,
        "transfer_kind": "intra_entity",
        # FASE E-0 (L14) — stempel entitas WAJIB agar transfer intra tidak terbaca
        # oleh entitas lain (registry `SCOPED_COLLECTIONS`).
        "entity_id": prefer_owner or ctx.active_entity_id,
        "source_warehouse_id": payload.source_warehouse_id,
        "dest_warehouse_id": payload.dest_warehouse_id,
        "status": "waiting_approval",
        "items": items_out,
        "line_codes": line_scope.codes_from_items(items_out),   # FASE L
        "notes": payload.notes,
        "requested_by": payload.requested_by,
        "approved_by": None,
        "approved_at": None,
        "rejected_by": None,
        "rejected_at": None,
        "rejected_reason": None,
        "created_at": now_iso(),
        "updated_at": now_iso()
    }


#: PK-30 (IC-09) — jalur transfer antar-PT harga pokok dari kasir ditutup; jalur resmi = Permintaan Internal / Antar-PT.
PESAN_JALUR_LAMA_DITUTUP = ("Transfer antar-PT lewat jalur ini sudah ditutup. Buat Permintaan Internal dari keranjang, "
                            "atau transaksi di menu Antar-PT.")
PESAN_TRANSFER_LAMA = ("Transfer antar-PT ini dibuat lewat jalur lama yang sudah ditutup. Tolak transfer ini, lalu buat "
                       "Permintaan Internal atau transaksi Antar-PT.")


@router.post("/transfers/inter-company")
async def create_inter_company_transfer(request: Request) -> Dict[str, Any]:
    """PK-30 (IC-09) — DITUTUP. Dulu kasir memindah stok antar-PT di sini (izin `order.create`) tanpa harga & tanpa
    dokumen antar-PT; saat disetujui terbit jurnal harga pokok 1-1250/2-1250 di luar layar Saldo Antar-PT. Kini selalu
    410 sesudah pemeriksaan izin; tidak menulis apa pun (isi permintaan diabaikan, roll tidak direservasi)."""
    await require_permission(request, "order", "create")
    raise HTTPException(status_code=410, detail=PESAN_JALUR_LAMA_DITUTUP)


@router.get("/transfers/so-options")
async def transfer_so_options(request: Request, source_warehouse_id: str = Query(...)) -> List[Dict[str, Any]]:
    """P03 IMP-26 — SO yang punya roll berkomitmen di gudang asal (untuk transfer pemenuhan SO)."""
    await require_permission(request, "transfer", "create")
    ctx = await entity_ctx(request)
    return await trs.so_options(source_warehouse_id, [] if getattr(ctx, "view_all", False) else list(resolve_scope_ids(ctx)))


@router.get("/transfers/so-rolls")
async def transfer_so_rolls(request: Request, sales_order_id: str = Query(...),
                            source_warehouse_id: str = Query(...)) -> List[Dict[str, Any]]:
    await require_permission(request, "transfer", "create")
    ctx = await entity_ctx(request)
    so = await db.sales_orders.find_one({"id": sales_order_id}, {"_id": 0, "entity_id": 1})
    if not so or (not getattr(ctx, "view_all", False) and so.get("entity_id") not in set(resolve_scope_ids(ctx))):
        raise HTTPException(status_code=404, detail="SO tidak ditemukan untuk entitas ini")
    return await trs.so_rolls(sales_order_id, source_warehouse_id)


@router.get("/transfers/{transfer_id}/receipt")
async def transfer_receipt(transfer_id: str, request: Request) -> Dict[str, Any]:
    """P03 IMP-27 — status per roll (dari dokumen roll), exception, riwayat penerimaan, bin tujuan."""
    await require_permission(request, "transfer", "view")
    t, _ = await _guard_transfer(request, transfer_id)
    return await trs.summary(t)


@router.post("/transfers/{transfer_id}/receive")
async def transfer_receive(transfer_id: str, payload: TransferReceiveIn, request: Request) -> Dict[str, Any]:
    """P03 IMP-27 — terima roll AKTUAL (parsial boleh, retry aman). Aturan tujuan dievaluasi ulang."""
    actor = await require_permission(request, "transfer", "update")
    t, _ = await _guard_transfer(request, transfer_id, side="dest")
    out = await trs.receive(t, payload, actor)
    await audit(actor["name"], "transfer_received", "transfer", transfer_id,
                {"results": [{k: r.get(k) for k in ("roll_no", "result")} for r in out["results"]],
                 "status": out["transfer_status"], "rule_exception": payload.rule_exception_reason or None})
    return out


@router.post("/transfers/{transfer_id}/exceptions")
async def transfer_report_exception(transfer_id: str, payload: TransferExceptionIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "transfer", "update")
    t, _ = await _guard_transfer(request, transfer_id, side="dest")
    out = await trs.report(t, payload, actor)
    await audit(actor["name"], "transfer_exception_reported", "transfer", transfer_id,
                {"kind": payload.kind, "roll_id": payload.roll_id, "reason": payload.reason})
    return out


@router.post("/transfers/{transfer_id}/exceptions/{exc_id}/resolve")
async def transfer_resolve_exception(transfer_id: str, exc_id: str, payload: TransferExceptionResolveIn,
                                     request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "transfer", "update")
    t, _ = await _guard_transfer(request, transfer_id)
    out = await trs.resolve(t, exc_id, payload, actor)
    await audit(actor["name"], "transfer_exception_resolved", "transfer", transfer_id,
                {"exception_id": exc_id, "action": payload.action, "reason": payload.reason})
    return out


@router.get("/transfers/{transfer_id}")
async def get_transfer_detail(transfer_id: str, request: Request) -> Dict[str, Any]:
    """Get detailed transfer information."""
    await require_permission(request, "transfer", "view")
    _t, _ctx = await _guard_transfer(request, transfer_id)   # FASE E-0 (L13)
    transfer = safe_doc(_t)
    if transfer.get("transfer_kind") == "inter_entity" and transfer.get("status") == "waiting_approval":
        transfer["dest_rule_check"] = await trs.interco_violations(_t)
    
    # Enrich with warehouse and product details
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    
    transfer["source_warehouse_name"] = warehouses.get(transfer["source_warehouse_id"], {}).get("name", "")
    transfer["dest_warehouse_name"] = warehouses.get(transfer["dest_warehouse_id"], {}).get("name", "")
    
    for item in transfer.get("items", []):
        prod = products.get(item["product_id"], {})
        item["sku"] = prod.get("sku", "")
        item["product_name"] = prod.get("name", "")
    
    return transfer


@router.post("/transfers/{transfer_id}/approve")
async def approve_transfer(transfer_id: str, payload: TransferApprove, request: Request) -> Dict[str, Any]:
    """
    Approve a transfer.
    
    Status: waiting_approval → approved
    Requires permission: transfer.approve
    """
    actor = await require_permission(request, "transfer", "approve")
    transfer, _ctx = await _guard_transfer(request, transfer_id, side="source")  # FASE E-0 (L13)
    await _aps.guard_door("transfer", actor, doc=transfer)   # KP-T4 — Aturan Persetujuan
    if transfer["status"] != "waiting_approval":
        raise HTTPException(status_code=400, detail=f"Transfer tidak bisa diapprove (status: {transfer['status']})")
    # KF-T6 — pengaju ≠ penyetuju dari `kontrol.transfer_gudang.*` (bawaan satu orang). Dokumen lama hanya menyimpan
    # nama pengaju (`requested_by`) → pembanding nama.
    from services import dual_control as _dc
    await _dc.tolak_bila_pelaku_sama("transfer_gudang", transfer, actor, transfer.get("entity_id", ""),
                                     pengaju=[transfer.get("requested_by_id"), transfer.get("requested_by")])
    # P02 sisa — antar badan usaha: gudang tempat barang berada wajib boleh dipakai PEMILIK BARU + lolos rules.
    rule_exc = None
    if transfer.get("transfer_kind") == "inter_entity":
        viol = await trs.interco_violations(transfer)
        if viol:
            reason = (payload.rule_exception_reason or "").strip()
            if not reason:
                raise HTTPException(status_code=409, detail={
                    "code": "INTERCO_DEST_RULES", "violations": viol[:20],
                    "message": (f"{len(viol)} roll melanggar aturan gudang untuk pemilik baru: {viol[0]['violations'][0]} "
                                "Pindahkan dulu ke gudang yang boleh, atau supervisor memberi pengecualian beralasan.")})
            from services import placement_rules as _pr
            await _pr.assert_supervisor(actor, "memberi pengecualian aturan gudang")
            if len(reason) < 5:
                raise HTTPException(status_code=400, detail="Alasan pengecualian minimal 5 karakter.")
            rule_exc = {"by": actor["name"], "reason": reason, "at": now_iso(), "violations": viol[:20]}
    if transfer.get("transfer_kind") == "inter_entity":
        # PK-37 (K-03) — PERIKSA periode buku hari ini untuk KEDUA PT sebelum kepemilikan roll pindah (jurnal M-3).
        from services.book_date import periksa_periode_dokumen_409
        await periksa_periode_dokumen_409([transfer.get("source_entity_id") or "", transfer.get("dest_entity_id") or ""],
                                          None, jenis="transfer antar-PT")
        # PK-30 (IC-09) — transfer antar-PT tanpa dokumen antar-PT (jalur kasir lama) tidak bisa disetujui lagi; tolak &
        # batal tetap bekerja (melepas roll).
        if not transfer.get("interco_pair_id") and not transfer.get("interco_return_pair_id"):
            raise HTTPException(status_code=409, detail=PESAN_TRANSFER_LAMA)
    interco_pre: Dict[str, Any] = {}
    if transfer.get("transfer_kind") == "inter_entity" and transfer.get("interco_pair_id"):
        # PK-30 (IC-02) — PERIKSA panjang roll aktual (mode `tolak`) + jurnal penyesuaian, HPP, dan penerimaan di KEDUA
        # PT sebelum kepemilikan roll pindah. Gagal → 409, tidak ada yang tertulis.
        from services import interco_service as _ics
        from services.twin_journal import TwinJournalError
        try:
            interco_pre = await _ics.precheck_warehouse_task(transfer)
        except (_ics.IntercoError, TwinJournalError, gl_service.ClosedPeriodError,
                gl_service.JournalValidationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    # T-01 Opsi B (INV-ATOMIC-01) — klaim sebelum kepemilikan roll pindah + jurnal diposting.
    from services import atomic_claim as _saga
    await _saga.claim("warehouse_transfers", transfer_id, "transfer_approve",
                      precondition={"status": "waiting_approval"}, actor=actor["name"])
    
    # Sub-fase 1.5 — inter-company: APPROVE = pindahkan kepemilikan B→E (S3, 1 langkah) → status completed.
    if transfer.get("transfer_kind") == "inter_entity":
        result = await execute_ownership_transfer(transfer)
        interco_pair_id = transfer.get("interco_pair_id")
        interco_return_pair_id = transfer.get("interco_return_pair_id")
        if interco_return_pair_id:
            # FASE G-6b — perpindahan BALIK milik RETUR antar-PT. Sama seperti arah
            # jualnya: jurnal at-cost M-3 DILEWATI (nota retur sudah memposting
            # pembalikan piutang/utang), roll dinilai ulang KEMBALI ke harga
            # perolehan asli penjual agar GL 1-1300 == subledger.
            from services import interco_return_service as _icret
            bridge = await _icret.on_return_task_executed(transfer, actor["name"])
            je_result = {
                "posted": False,
                "skipped_reason": (
                    "Jurnal sudah diposting oleh retur antar-PT "
                    f"{transfer.get('interco_return_number') or interco_return_pair_id} "
                    "(FASE G-6b). Memposting at-cost M-3 lagi akan menggandakan "
                    "pembalikan IC-AR/IC-AP & persediaan."),
                "interco_return_pair_id": interco_return_pair_id,
                "revalued_rolls": bridge.get("revalued_rolls", 0),
                "returned_cost": bridge.get("returned_cost", 0),
                "interco_status": bridge.get("status", ""),
            }
        else:
            # FASE G-6 — perpindahan fisik milik transaksi JUAL-BELI antar-PT (transfer tanpa tautan antar-PT sudah
            # ditolak di atas — PK-30). Jurnal at-cost M-3 SENGAJA DILEWATI: jurnal harga jual (IC-AR/Pendapatan di
            # penjual, Persediaan/IC-AP di pembeli) sudah diposting saat transaksi dikonfirmasi. PK-30: dokumen &
            # jurnalnya lebih dulu disesuaikan ke panjang roll aktual (`interco_pre`).
            from services import interco_service as _ics
            bridge = await _ics.on_warehouse_task_executed(transfer, actor["name"],
                                                           actual=interco_pre.get("actual"))
            je_result = {
                "posted": False,
                "skipped_reason": (
                    "Jurnal sudah diposting oleh transaksi antar-PT "
                    f"{transfer.get('interco_number') or interco_pair_id} (FASE G-6, harga jual). "
                    "Memposting at-cost M-3 lagi akan menggandakan IC-AR/IC-AP & persediaan."),
                "interco_pair_id": interco_pair_id,
                "revalued_rolls": bridge.get("revalued_rolls", 0),
                "interco_status": bridge.get("status", ""),
                "length_adjustment": (bridge.get("length_adjustment") or {}).get("length_adjustment"),
            }
        updated = await db.warehouse_transfers.find_one_and_update(
            {"id": transfer_id},
            _saga.finish_set({"status": "completed", "approved_by": payload.approved_by,
                      "approved_at": now_iso(), "ownership_moved": result, "rule_exception": rule_exc,
                      "je_intercompany": je_result, "updated_at": now_iso()}),
            projection={"_id": 0}, return_document=ReturnDocument.AFTER,
        )
        await audit(actor["name"], "inter_company_transfer_executed", "transfer", transfer_id,
                    {"approved_by": payload.approved_by, **result,
                     "je_posted": je_result.get("posted"),
                     "je_total": je_result.get("total", 0),
                     "je_pair_id": je_result.get("pair_id", "")})
        return safe_doc(updated)

    updated = await db.warehouse_transfers.find_one_and_update(
        {"id": transfer_id},
        _saga.finish_set({
                "status": "approved",
                "approved_by": payload.approved_by,
                "approved_at": now_iso(),
                "updated_at": now_iso()
        }),
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "transfer_approved", "transfer", transfer_id, {"approved_by": payload.approved_by})
    
    return safe_doc(updated)


@router.post("/transfers/{transfer_id}/reject")
async def reject_transfer(transfer_id: str, payload: TransferReject, request: Request) -> Dict[str, Any]:
    """
    Reject a transfer.
    
    Status: waiting_approval → rejected
    Requires permission: transfer.reject
    """
    actor = await require_permission(request, "transfer", "reject")
    transfer, _ctx = await _guard_transfer(request, transfer_id, side="source")  # FASE E-0 (L13)
    if transfer["status"] != "waiting_approval":
        raise HTTPException(status_code=400, detail=f"Transfer tidak bisa direject (status: {transfer['status']})")
    from services import atomic_claim as _saga
    await _saga.claim("warehouse_transfers", transfer_id, "transfer_reject",
                      precondition={"status": "waiting_approval"}, actor=actor["name"])
    
    # Sub-fase 1.5 — inter-company: lepas reservasi roll di entitas sumber.
    if transfer.get("transfer_kind") == "inter_entity":
        await release_transfer_rolls(transfer_id)
    else:
        # Intra-entity: lepas roll yang direservasi saat create → available lagi di gudang asal.
        await release_wh_transfer_rolls(transfer_id)

    updated = await db.warehouse_transfers.find_one_and_update(
        {"id": transfer_id},
        _saga.finish_set({
                "status": "rejected",
                "rejected_by": payload.rejected_by,
                "rejected_at": now_iso(),
                "rejected_reason": payload.reason,
                "updated_at": now_iso()
        }),
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "transfer_rejected", "transfer", transfer_id, {"rejected_by": payload.rejected_by, "reason": payload.reason})
    
    return safe_doc(updated)


@router.post("/transfers/{transfer_id}/status")
async def update_transfer_status(transfer_id: str, payload: TransferStatusUpdate, request: Request) -> Dict[str, Any]:
    """
    Update transfer status (workflow progression).
    
    Valid transitions:
    - approved → picking
    - picking → staging
    - staging → dispatched
    - dispatched → completed
    Batal/setujui/tolak TIDAK lewat sini (lihat _DEDICATED_STATUS_ROUTES).
    
    Inventory impact:
    - dispatched: reduce source warehouse on_hand, increase in_transit
    - completed: reduce source in_transit, increase dest on_hand
    """
    actor = await require_permission(request, "transfer", "update")
    if payload.status in _DEDICATED_STATUS_ROUTES:
        raise HTTPException(
            status_code=400,
            detail=(f"Status '{payload.status}' tidak bisa diubah lewat jalur status. "
                    f"Gunakan {_DEDICATED_STATUS_ROUTES[payload.status]} agar izin dan stok roll tertangani."),
        )
    # FASE E-0 (L13) — status berjalan di sisi yang berhak: `completed` (terima barang)
    # milik entitas TUJUAN, sisanya milik entitas ASAL.
    _side = "dest" if payload.status == "completed" else "source"
    transfer, _ctx = await _guard_transfer(request, transfer_id, side=_side)
    current_status = transfer["status"]
    new_status = payload.status
    
    # Validate transition
    if not _validate_status_transition(current_status, new_status):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition: {current_status} → {new_status}"
        )
    # P03 IMP-27 — "Selesai" BUKAN jalan pintas menerima semua roll: terima per roll lewat /receive.
    if new_status == "completed" and transfer.get("transfer_kind") != "inter_entity":
        left = await transfer_held_rolls(transfer_id, ["in_transit_transfer"])
        if left:
            raise HTTPException(status_code=409, detail={
                "code": "TRANSFER_RECEIPT_REQUIRED",
                "message": f"{len(left)} roll masih dalam perjalanan. Terima roll yang benar-benar tiba lewat 'Terima per roll'; "
                           "roll yang tidak tiba dicatat sebagai exception."})
    from services import registration_freeze as _rfz   # PREP-B K-OPN-03 — area beku pendaftaran awal
    await _rfz.assert_transfer_movable(transfer, "in" if new_status == "completed" else "out")
    # T-01 Opsi B (INV-ATOMIC-01) — klaim sebelum roll dipindah (dispatch/receive).
    from services import atomic_claim as _saga
    await _saga.claim("warehouse_transfers", transfer_id, f"transfer_status:{new_status}",
                      precondition={"status": current_status}, actor=actor["name"])
    
    # Roll-as-SSOT (KN_15 §9 / KN_16 §7) — transfer antar-gudang memindahkan ROLL,
    # BUKAN $inc balance. Balance selalu di-rebuild dari rolls oleh roll_service.
    if transfer.get("transfer_kind") != "inter_entity":
        if new_status == "dispatched":
            # reserved → in_transit_transfer (keluar dari gudang sumber; komitmen SO tetap)
            await dispatch_wh_transfer_rolls(transfer_id, source_document=f"transfer_{transfer['code']}")
    
    # Update transfer status
    updated = await db.warehouse_transfers.find_one_and_update(
        {"id": transfer_id},
        _saga.finish_set({
                "status": new_status,
                "updated_at": now_iso()
        }),
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(
        actor["name"],
        "transfer_status_changed",
        "transfer",
        transfer_id,
        {"from": current_status, "to": new_status, "updated_by": payload.updated_by}
    )
    
    return safe_doc(updated)


@router.delete("/transfers/{transfer_id}")
async def cancel_transfer(transfer_id: str, request: Request,
                          reason: str = Query("", max_length=500)) -> Dict[str, Any]:
    """
    Cancel a transfer (soft delete via status change).
    
    Can only cancel if status is not completed, rejected, or already cancelled.
    Requires permission: transfer.cancel

    FASE P5 — `reason` (opsional di API, WAJIB di layar): pembatalan transfer melepas
    roll yang tertahan, jadi keputusannya berdampak stok dan harus bisa
    dipertanggungjawabkan. Layar selalu mengirimkannya; API dibuat opsional supaya
    pemanggil lama (POC isolasi E-0) tidak berubah artinya. Alasannya BENAR-BENAR
    disimpan (`cancelled_reason` + audit log) — menanyakan alasan lalu membuangnya
    hanya membuat pengguna mengarang jawaban.
    """
    actor = await require_permission(request, "transfer", "cancel")
    transfer, _ctx = await _guard_transfer(request, transfer_id, side="source")  # FASE E-0 (L13)
    if transfer["status"] in ["completed", "rejected", "cancelled", "returned", "returning"]:
        raise HTTPException(status_code=400, detail=f"Transfer tidak bisa dibatalkan (status: {transfer['status']})")
    if transfer["status"] == "partially_received":
        raise HTTPException(status_code=400, detail=(
            "Sebagian roll sudah diterima di tujuan — transfer tidak bisa dibatalkan. Catat roll yang tidak tiba "
            "sebagai exception lalu supervisor mengembalikannya ke gudang asal."))
    if transfer["status"] in ("dispatched", "in_transit", "shipped") and transfer.get("transfer_kind") != "inter_entity":
        # FIX-3b (FLW-OUT-11, keputusan K-B2b-03) — batal saat barang DI JALAN: roll TIDAK langsung tersedia di asal
        # (masih di truk). Transfer → `returning`; roll tetap `in_transit_transfer` sampai DIPINDAI/diterima kembali di
        # gudang asal ("Terima per roll" pada transfer ini) — baru `available`/komitmen SO di asal. Status akhir
        # `cancelled` (basis `returned_to_source`) sesudah semua roll kembali.
        from input_rules import require_reason
        why = require_reason(reason, label="Alasan batal transfer di jalan")
        from services import status_history as _sh
        updated = await db.warehouse_transfers.find_one_and_update(
            {"id": transfer_id, "status": transfer["status"], "saga_lock": {"$exists": False}},
            {"$set": {"status": "returning", "return_requested": {"by": actor["name"], "at": now_iso(), "reason": why,
                                                                  "from_status": transfer["status"]},
                      "updated_at": now_iso()},
             "$push": {"status_history": _sh.entry("returning", user=actor["name"], note=why, action="cancel_in_transit")}},
            projection={"_id": 0}, return_document=ReturnDocument.AFTER)
        if not updated:
            raise HTTPException(status_code=409, detail="Transfer baru saja berubah status — muat ulang.")
        await audit(actor["name"], "transfer_cancel_in_transit", "transfer", transfer_id, {"reason": why}, reason=why)
        return safe_doc(updated)
    # INV-ATOMIC-01 — klaim transfer (status masih hidup) SEBELUM roll dilepas: dua pembatalan
    # bersamaan / bersaing dengan approve tidak boleh melepas roll dua kali.
    from services import atomic_claim as _saga
    await _saga.claim("warehouse_transfers", transfer_id, "transfer_cancel",
                      precondition={"status": {"$nin": ["completed", "rejected", "cancelled"]}}, actor=actor["name"])

    # Lepas roll yang tertahan (reserved ATAU in_transit_transfer) → available di gudang asal.
    if transfer.get("transfer_kind") == "inter_entity":
        await release_transfer_rolls(transfer_id)
    else:
        await release_wh_transfer_rolls(transfer_id)

    updated = await db.warehouse_transfers.find_one_and_update(
        {"id": transfer_id},
        _saga.finish_set({
            "status": "cancelled",
            "cancelled_by": actor["name"],
            "cancelled_at": now_iso(),
            "cancelled_reason": (reason or "").strip(),
            "updated_at": now_iso()
        }),
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "transfer_cancelled", "transfer", transfer_id,
                {"reason": (reason or "").strip()})
    
    return safe_doc(updated)
