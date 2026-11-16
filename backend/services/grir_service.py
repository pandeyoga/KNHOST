"""PK-28 (IV-03) — daftar sisa GR/IR per PO (Hutang › GR/IR) dan kliring sisa yang tidak akan tertagih.
MP-T4b (K-82) — ditambah baris per SPK makloon: jasa diterima yang faktur mitranya belum dicocokkan.

Sumber angka: jurnal buku besar akun GR/IR (`vendor_bill_service.grir_by_po`), bukan ringkasan PO. Kliring mengikuti
kontrak posting `02_STANDAR.md` §1: PERIKSA (tanpa tulisan) → NIAT (`purchase_orders.grir_clearings[]` ber-`pending`,
bersyarat) → JURNAL lewat pintu tahan-gagal (`posting_registry.durable_grir_clearing`) → status di unsur kliringnya.
"""
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import DEFAULT_ENTITY_ID, new_id, now_iso
from db import db

#: Status PO yang boleh dikliring: penerimaan dan penagihan PO sudah berakhir.
CLEARABLE_PO_STATUSES = ("completed", "closed_short", "cancelled")
#: Faktur PO yang belum diposting menahan kliring (sisa GR/IR masih akan berubah).
OPEN_BILL_STATUSES = ("draft", "pending_approval")
BUCKETS = ("0-30", "31-60", "61-90", ">90")
EPS = 0.005
MAPPING_KEY = "pembelian.selisih_harga"
MAPPING_LABEL = "Selisih harga pembelian"
MSG_MAPPING = (f'Akun "{MAPPING_LABEL}" belum diatur untuk PT ini. '
               "Isi di Pengaturan › Keuangan & Pajak › Pemetaan Akun.")

#: Label status PO untuk pesan dan layar (kode mentah tidak tampil, `02` L1).
PO_STATUS_LABEL = {
    "draft": "draf", "waiting_approval": "menunggu persetujuan", "approved": "disetujui", "pending": "menunggu barang",
    "receiving": "sedang diterima", "partial": "terima sebagian", "completed": "selesai",
    "closed_short": "ditutup-kurang", "cancelled": "dibatalkan", "rejected": "ditolak",
}


def po_status_label(status: str) -> str:
    return PO_STATUS_LABEL.get(status or "", (status or "—").replace("_", " "))


def bucket_of(age_days: int) -> str:
    if age_days <= 30:
        return "0-30"
    if age_days <= 60:
        return "31-60"
    if age_days <= 90:
        return "61-90"
    return ">90"


def _age(last: str, today: str) -> int:
    try:
        return max((date.fromisoformat(today[:10]) - date.fromisoformat(str(last)[:10])).days, 0)
    except (TypeError, ValueError):
        return 0


async def mapping_ready(entity_id: str) -> bool:
    from services.gl_mapping_service import account_for
    return bool(await account_for(MAPPING_KEY, entity_id))


async def _open_bills(po_ids: List[str]) -> Dict[str, str]:
    """{po_id: nomor faktur pertama yang belum diposting}."""
    out: Dict[str, str] = {}
    async for b in db.vendor_bills.find({"po_id": {"$in": po_ids}, "status": {"$in": list(OPEN_BILL_STATUSES)}},
                                        {"_id": 0, "po_id": 1, "bill_number": 1, "id": 1}).sort("bill_number", 1):
        out.setdefault(b["po_id"], b.get("bill_number") or b.get("id") or "")
    return out


async def _unposted_variance(po_ids: List[str]) -> Dict[str, float]:
    """Σ selisih harga faktur yang MASIH di GR/IR (akun selisih belum dipetakan saat faktur dijurnal), per PO."""
    out: Dict[str, float] = {}
    async for b in db.vendor_bills.find({"po_id": {"$in": po_ids}, "status": {"$in": ["posted", "paid"]},
                                         "gl_status": "posted", "price_variance_posted": False},
                                        {"_id": 0, "po_id": 1, "price_variance_amount": 1}):
        out[b["po_id"]] = round(out.get(b["po_id"], 0.0) + float(b.get("price_variance_amount") or 0), 2)
    return out


async def list_grir(entity_id: str, *, status: str = "terbuka", bucket: str = "", q: str = "", page: int = 1,
                    page_size: int = 50) -> Dict[str, Any]:
    from services.book_date import tanggal_buku
    from services.doc_refs_service import link_of
    from services.vendor_bill_service import MKO_KEY, grir_by_po, grir_ledger_balance
    today = tanggal_buku()
    by_po = await grir_by_po(entity_id)
    unlinked = float((by_po.pop("", None) or {}).get("balance") or 0)
    by_mko = {k[len(MKO_KEY):]: by_po.pop(k) for k in [k for k in by_po if k.startswith(MKO_KEY)]}
    ids = sorted(by_po)
    pos: Dict[str, Dict[str, Any]] = {}
    async for po in db.purchase_orders.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "po_number": 1,
                                                                   "supplier_name": 1, "status": 1, "entity_id": 1}):
        pos[po["id"]] = po
    for pid in [p for p in ids if p not in pos]:   # PO sumber sudah tidak ada → tidak bisa dihubungkan
        unlinked += float(by_po.pop(pid)["balance"] or 0)
    open_bills = await _open_bills(list(by_po))
    unposted = await _unposted_variance(list(by_po))
    ready = await mapping_ready(entity_id)
    rows: List[Dict[str, Any]] = []
    for pid, g in by_po.items():
        po = pos[pid]
        last = g["last_receipt_at"] or g["last_activity_at"]
        age = _age(last, today)
        bal = g["balance"]
        rows.append({
            "po_id": pid, "po_number": po.get("po_number") or pid, "supplier_name": po.get("supplier_name") or "",
            "po_status": po.get("status") or "", "po_status_label": po_status_label(po.get("status") or ""),
            "received_value": g["received_value"], "billed_value": g["billed_value"],
            "returned_value": g["returned_value"], "cleared_value": g["cleared_value"], "balance": bal,
            "last_receipt_at": g["last_receipt_at"], "age_days": age, "bucket": bucket_of(age),
            "unposted_variance": unposted.get(pid, 0.0), "open_bill_number": open_bills.get(pid, ""),
            "can_clear": bool(ready and abs(bal) > EPS and po.get("status") in CLEARABLE_PO_STATUSES
                              and pid not in open_bills),
            "link": link_of("purchase_order", po), "kind": "po", "doc_id": pid,
            "doc_number": po.get("po_number") or pid,
        })
    mko_rows, mko_unlinked = await _makloon_rows(by_mko, today, link_of)
    rows += mko_rows
    unlinked += mko_unlinked
    total_balance = round(sum(r["balance"] for r in rows), 2)
    shown = [r for r in rows if status == "semua" or abs(r["balance"]) > EPS]
    if bucket:
        shown = [r for r in shown if r["bucket"] == bucket]
    needle = (q or "").strip().lower()
    if needle:
        shown = [r for r in shown if needle in r["doc_number"].lower() or needle in r["supplier_name"].lower()]
    shown.sort(key=lambda r: (-r["age_days"], r["doc_number"]))
    start = (page - 1) * page_size
    return {
        "entity_id": entity_id, "items": shown[start:start + page_size], "total": len(shown), "page": page,
        "page_size": page_size, "total_balance": total_balance,
        "filtered_balance": round(sum(r["balance"] for r in shown), 2),
        "ledger_balance": await grir_ledger_balance(entity_id), "unlinked_balance": round(unlinked, 2),
        "mapping_ready": ready, "as_of": today,
    }


MKO_STATUS_LABEL = {"draft": "draf", "in_process": "diproses", "partially_received": "diterima sebagian",
                    "completed": "selesai", "cancelled": "dibatalkan"}
#: Petunjuk tindakan baris SPK makloon (sisa GR/IR jasa diselesaikan dengan mencocokkan faktur mitra, bukan kliring).
MKO_HINT = "Cocokkan faktur di rincian SPK"


async def _makloon_rows(by_mko: Dict[str, Dict[str, Any]], today: str, link_of) -> tuple:
    """MP-T4b (K-82) — baris GR/IR jasa makloon per SPK: nilai jasa diterima, sudah difakturkan, dipotong klaim/susut,
    sisa, umur sejak terima terakhir, tagihan yang masih menunggu faktur. SPK yang sudah tidak ada → tak terhubung."""
    if not by_mko:
        return [], 0.0
    orders = {o["id"]: o async for o in db.makloon_orders.find(
        {"id": {"$in": sorted(by_mko)}}, {"_id": 0, "id": 1, "mko_number": 1, "status": 1, "steps.makloon_name": 1})}
    waiting: Dict[str, List[str]] = {}
    async for b in db.vendor_bills.find({"makloon_order_id": {"$in": sorted(orders)}, "status": "awaiting_invoice"},
                                        {"_id": 0, "makloon_order_id": 1, "bill_number": 1}).sort("bill_number", 1):
        waiting.setdefault(b["makloon_order_id"], []).append(b.get("bill_number") or "")
    rows: List[Dict[str, Any]] = []
    unlinked = 0.0
    for mid, g in by_mko.items():
        o = orders.get(mid)
        if not o:
            unlinked += float(g["balance"] or 0)
            continue
        partners = list(dict.fromkeys(s.get("makloon_name") for s in o.get("steps") or [] if s.get("makloon_name")))
        age = _age(g["last_receipt_at"] or g["last_activity_at"], today)
        rows.append({
            "kind": "makloon", "doc_id": mid, "doc_number": o.get("mko_number") or mid,
            "po_id": "", "po_number": "", "supplier_name": ", ".join(partners),
            "po_status": o.get("status") or "",
            "po_status_label": "Makloon · " + MKO_STATUS_LABEL.get(o.get("status") or "", o.get("status") or "—"),
            "received_value": g["received_value"], "billed_value": g["billed_value"],
            "returned_value": g["returned_value"], "cleared_value": g["cleared_value"], "balance": g["balance"],
            "last_receipt_at": g["last_receipt_at"], "age_days": age, "bucket": bucket_of(age),
            "unposted_variance": 0.0, "open_bill_number": "", "awaiting_bills": waiting.get(mid, []),
            "can_clear": False, "action_hint": MKO_HINT if waiting.get(mid) else "",
            "link": link_of("makloon_order", o),
        })
    return rows, round(unlinked, 2)


async def clear(po: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Kliring sisa GR/IR satu PO (PERIKSA → NIAT → JURNAL). `po` sudah lolos `guard_doc` di router."""
    from services import gl_service as gl, posting_registry as preg
    from services.vendor_bill_service import grir_by_po
    po_id, num = po["id"], po.get("po_number") or po["id"]
    eid = po.get("entity_id") or DEFAULT_ENTITY_ID
    # 1. PERIKSA — tanpa tulisan apa pun
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Alasan kliring wajib diisi (minimal 5 huruf).")
    if po.get("status") not in CLEARABLE_PO_STATUSES:
        raise HTTPException(status_code=409, detail=(
            f"PO {num} masih berjalan (status {po_status_label(po.get('status') or '')}). Kliring GR/IR hanya untuk PO "
            "yang sudah selesai, ditutup-kurang, atau dibatalkan."))
    bill = (await _open_bills([po_id])).get(po_id)
    if bill is not None:
        raise HTTPException(status_code=409, detail=(
            f"Masih ada faktur pemasok untuk PO {num} yang belum diposting ({bill}). Selesaikan dulu."))
    if any(c.get("gl_status") == "failed" for c in po.get("grir_clearings") or []):
        # Unsur yang jurnalnya gagal belum mengubah buku besar: kliring baru sekarang = jurnal ganda saat diulang.
        raise HTTPException(status_code=409, detail=(
            f"Kliring GR/IR sebelumnya untuk PO {num} belum terjurnal. Ulang dari Tutup Buku › Posting Gagal dulu."))
    if any(c.get("gl_status") == "pending" for c in po.get("grir_clearings") or []):
        raise HTTPException(status_code=409, detail=f"Kliring GR/IR PO {num} sedang diproses. Muat ulang.")
    n_awal = len(po.get("grir_clearings") or [])
    balance = float(((await grir_by_po(eid, po_id)).get(po_id) or {}).get("balance") or 0)
    if abs(balance) <= EPS:
        raise HTTPException(status_code=409, detail=f"Sisa GR/IR PO {num} sudah nol.")
    if not await mapping_ready(eid):
        raise HTTPException(status_code=409, detail=MSG_MAPPING)
    try:
        await gl.preflight_posting(eid, "")
    except gl.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # 2. NIAT — bersyarat: tidak ada kliring lain yang `pending`/`failed` dan larik tidak berubah sejak saldo dibaca
    seq = n_awal + 1
    clearing = {"id": new_id("grirc"), "seq": seq, "amount": round(abs(balance), 2),
                "direction": "debit_grir" if balance > 0 else "kredit_grir", "reason": reason,
                "by": actor.get("name", ""), "by_id": actor.get("id", ""), "at": now_iso(),
                "gl_status": "pending", "gl_error": "", "journal_entry_id": ""}
    res = await db.purchase_orders.update_one(
        {"id": po_id, "grir_clearings.gl_status": {"$nin": ["pending", "failed"]},
         f"grir_clearings.{n_awal}": {"$exists": False}},
        {"$push": {"grir_clearings": clearing}, "$set": {"updated_at": now_iso()}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail=f"Kliring GR/IR PO {num} sedang diproses. Muat ulang.")
    # 3. JURNAL — satu pintu tahan-gagal; gagal → 200 + `gl_status="failed"` (tampil di Posting Gagal)
    jr = await preg.durable_grir_clearing({**po, "entity_id": eid}, clearing)
    from dependencies import audit
    await audit(actor.get("name", ""), "grir_cleared", "purchase_order", po_id,
                {"po_number": num, "seq": seq, "amount": clearing["amount"], "direction": clearing["direction"],
                 "reason": reason, "gl_status": jr["gl_status"]})
    after = float(((await grir_by_po(eid, po_id)).get(po_id) or {}).get("balance") or 0)
    return {"po_id": po_id, "po_number": num,
            "clearing": {**clearing, "gl_status": jr["gl_status"], "gl_error": jr["gl_error"],
                         "journal_entry_id": jr["journal_entry_id"]},
            "balance": round(after, 2)}


async def grir_balance_of(po: Dict[str, Any]) -> Optional[float]:
    """Sisa GR/IR satu PO (dipakai rekonsiliasi tutup-kurang)."""
    from services.vendor_bill_service import grir_by_po
    eid = po.get("entity_id") or DEFAULT_ENTITY_ID
    return round(float(((await grir_by_po(eid, po["id"])).get(po["id"]) or {}).get("balance") or 0), 2)
