"""Lapor Bayar CBD & DP (LB-T1) — kerangka layanan laporan bayar pelanggan.

Laporan bayar = sales/admin sales memberi tahu Finance bahwa pelanggan sudah membayar (bukti terlampir). Finance menerima
(lewat `ar_receipt_service.create_receipt`, satu-satunya pintu kas) atau menolak. Modul ini sengaja kecil: konstanta
status, penomoran, dan bentuk tampil. Pembuatan laporan (Tugas 3) dan keputusan terima/tolak (Tugas 4) ditambahkan di sini.
"""
from __future__ import annotations

from datetime import date
import math
from typing import Any, Dict, List

from fastapi import HTTPException

from core_utils import new_id, next_doc_number, now_iso
from db import db
from services import status_history

MENUNGGU = "menunggu"
DITERIMA = "diterima"
DITOLAK = "ditolak"

#: Isian internal yang tidak pernah dikirim ke layar (kunci idempotensi dan klaim atomik).
_INTERNAL = ("_id", "idem_key", "claim")


async def next_number(entity_id: str) -> str:
    """Nomor laporan `LB-…` lewat penomoran baku dokumen (format & cara per PT dari tabel Penomoran Dokumen)."""
    return await next_doc_number("payment_reports", "number", "LB-", entity_id=entity_id)


def tampil(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Salinan dokumen untuk layar: tanpa `_id`, isian internal, dan `storage_path` lampiran (jalur penyimpanan tidak
    pernah keluar; berkas diambil lewat rute unduh yang berpagar)."""
    out = {k: v for k, v in (doc or {}).items() if k not in _INTERNAL}
    lampiran = [{k: v for k, v in a.items() if k != "storage_path"}
                for a in (out.get("attachments") or []) if not a.get("is_deleted")]
    out["attachments"] = lampiran
    out["attachment_count"] = len(lampiran)
    return out


async def _perlu_bayar(order: Dict[str, Any]) -> bool:
    """Pesanan sedang menunggu bayar: tahan aktif, atau gerbang bayar masih menunjukkan kekurangan (mis. DP sudah masuk,
    pelunasan sebelum surat jalan belum). Keduanya dari `pay_hold_service` / `dispatch_payment_gate` — tanpa hitungan
    kedua."""
    from services import dispatch_payment_gate as gate
    from services import pay_hold_service as phs
    if order.get("pay_hold") or await phs.blocked(order):
        return True
    st = await gate.evaluate(order)
    return bool(st.get("applies")) and float(st.get("shortfall") or 0) > 0


async def create_report(order: Dict[str, Any], payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Buat laporan bayar `menunggu` untuk satu pesanan. Semua pemeriksaan DI SINI sebelum menulis apa pun; galat berkalimat
    (HTTPException). Pagar PT/pemilik/izin milik router."""
    from services import payment_method_service as pms
    from services.bank_account_change_service import daftar_penerima
    from services.customer_service import DEAD_STATUSES

    entity_id = order.get("entity_id") or ""
    if order.get("status") in DEAD_STATUSES:
        raise HTTPException(status_code=409, detail="Pesanan ini sudah tidak aktif")
    if not await _perlu_bayar(order):
        raise HTTPException(status_code=409, detail="Pesanan ini tidak menunggu bayar")
    try:
        amount = float(payload.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if not math.isfinite(amount) or amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari nol")
    try:
        tgl = date.fromisoformat(str(payload.get("transfer_date") or "")[:10]).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Tanggal transfer tidak sah (format YYYY-MM-DD)") from None
    # cara bayar: dari master PT, bukan tunai (uang tunai tidak punya bukti transfer; masuk lewat kasir/kas)
    kode = await pms.kode_400(entity_id, str(payload.get("method") or ""), arah="masuk")
    if await pms.is_cash(entity_id, kode):
        raise HTTPException(status_code=400, detail="Lapor bayar hanya untuk pembayaran non-tunai")
    rekening = next((a for a in await daftar_penerima(entity_id, kode) if a["id"] == payload.get("account_id")), None)
    if not rekening:
        raise HTTPException(status_code=400, detail="Rekening tujuan bukan rekening penerimaan PT pesanan ini")
    if await db.payment_reports.find_one({"order_id": order["id"], "status": MENUNGGU, "amount": amount,
                                          "transfer_date": tgl}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Laporan yang sama masih menunggu dicek")
    now = now_iso()
    doc = {
        "id": new_id("lb"), "number": await next_number(entity_id), "entity_id": entity_id,
        "order_id": order["id"], "order_number": order.get("number", ""),
        "customer_id": order.get("customer_id", ""), "customer_name": order.get("customer_name", ""),
        "amount": amount, "transfer_date": tgl, "method": kode,
        "account_id": rekening["id"], "account_name": rekening.get("name", ""),
        "reference_no": str(payload.get("reference_no") or "").strip()[:100],
        "note": str(payload.get("note") or "").strip()[:500],
        "status": MENUNGGU, "attachments": [],
        "created_by": actor.get("id", ""), "created_by_name": actor.get("name", ""),
        "created_at": now, "updated_at": now,
        "status_history": [status_history.entry(MENUNGGU, user=actor.get("name", ""), note="Laporan dibuat")],
    }
    await db.payment_reports.insert_one(dict(doc))
    await _beritahu_finance(doc)
    return tampil(doc)


async def _beritahu_finance(doc: Dict[str, Any]) -> None:
    """Notifikasi `lapor_bayar_masuk` ke pemegang izin `payment_report.decide` di PT pesanan (satu per orang)."""
    from services import notification_service as ns
    from core_utils import rupiah
    await ns.create_addressed(
        permission=("payment_report", "decide"), notif_type="lapor_bayar_masuk",
        title=f"Lapor bayar masuk — {doc['order_number']}",
        body=f"{doc['customer_name']} melaporkan bayar {rupiah(doc['amount'])} ({doc['number']}). Cek bukti dan putuskan.",
        severity="info", link=f"/?view=orders&id={doc['order_id']}", entity_id=doc["entity_id"] or None,
        ref=doc["id"])


async def add_attachment(report: Dict[str, Any], att: Dict[str, Any]) -> Dict[str, Any]:
    """Tambah lampiran ke laporan yang masih `menunggu` (klaim atomik pada status). Kembalian = lampiran tanpa jalur
    penyimpanan."""
    res = await db.payment_reports.update_one(
        {"id": report["id"], "status": MENUNGGU},
        {"$push": {"attachments": att}, "$set": {"updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=409, detail="Laporan sudah diputus; lampiran tidak bisa ditambah")
    return {k: v for k, v in att.items() if k != "storage_path"}


async def list_for_order(order_id: str) -> List[Dict[str, Any]]:
    rows = await db.payment_reports.find({"order_id": order_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [tampil(r) for r in rows]
