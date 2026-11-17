"""Bagian D — Buku Besar & Jejak Dokumen (F16): satu pesanan latihan yang SUDAH lengkap jejaknya.

F16 tidak mencatat apa pun: peserta menelusuri jurnal yang lahir dari transaksi nyata. Supaya tidak bergantung pada
urutan skenario lain (F02 memakai `a_dasar:so_lunas` dan harus tetap BELUM dibayar), prep ini membuat SO tersendiri:
SO dibuat sales → disahkan → diambil → dikirim → diterima (surat jalan + jurnal pendapatan & HPP), lalu DILUNASI penuh
oleh akun Finance peserta sendiri lewat `POST /ar-receipts` (kwitansi → transaksi kas → jurnal penerimaan).
Semua lewat endpoint resmi; database hanya DIBACA untuk mengisi Kartu Peserta (nomor kwitansi & jurnal).
"""
from typing import Any, Dict, List

from db import db

from .a_dasar import _so_terkirim
from .konteks import KSC, LatihCtx, Peserta


async def _jurnal_dari(source_type: str, source_id: str) -> List[Dict[str, Any]]:
    return await db.journal_entries.find({"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}},
                                         {"_id": 0, "id": 1, "number": 1, "total_debit": 1}).to_list(20)


async def so_jejak(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F16 — SO terkirim & LUNAS (dibayar akun Finance peserta): jejak SO → surat jalan → kwitansi → kas → jurnal."""
    so = await _so_terkirim(lc, p, "so_jejak", "woven")
    total = round(float(so["total"]), 2)
    so_doc = await lc.so(so["so_id"])
    fin = await lc.peserta_user(p)
    rc = await fin.post("/ar-receipts", {
        "customer_id": so_doc["customer_id"], "amount": total, "method": "transfer", "entity_id": KSC,
        "notes": f"Pelunasan latihan jejak dokumen peserta {p.kode}",
        "allocations": [{"order_id": so["so_id"], "amount": total}]}, entity=KSC)
    rc_id = rc.get("id") or (rc.get("receipt") or {}).get("id")
    rc_doc = await db.ar_receipts.find_one({"id": rc_id}, {"_id": 0}) if rc_id else None
    if not rc_doc:   # bentuk respons berbeda → cari kwitansi terbaru yang dialokasikan ke SO ini
        rc_doc = await db.ar_receipts.find_one({"allocations.order_id": so["so_id"], "status": {"$ne": "void"}},
                                               {"_id": 0}, sort=[("created_at", -1)])
    await lc.tag("ar_receipts", rc_doc["id"], p, "so_jejak")
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": rc_doc["id"]},
                                              {"_id": 0, "id": 1, "number": 1})
    je_kas = await _jurnal_dari("cash_transaction", kas["id"]) if kas else []
    sj = await db.shipments.find({"order_id": so["so_id"]}, {"_id": 0, "id": 1, "shipment_no": 1, "number": 1}).to_list(10)
    je_kirim: List[Dict[str, Any]] = []
    for s in sj:
        for st in ("shipment_revenue", "shipment_cogs"):
            je_kirim += await _jurnal_dari(st, s["id"])
    so_doc = await lc.so(so["so_id"])
    return {"so": so["so"], "so_id": so["so_id"], "total": total, "status": so_doc.get("status"),
            "pembayaran": so_doc.get("payment_status"),
            "kwitansi": rc_doc.get("number"), "kwitansi_id": rc_doc["id"],
            "kas": (kas or {}).get("number", ""), "jurnal_terima": ", ".join(j["number"] for j in je_kas),
            "surat_jalan": ", ".join(s.get("shipment_no") or s.get("number") or "" for s in sj),
            "jurnal_kirim": ", ".join(j["number"] for j in je_kirim)}


PREPS = [("so_jejak", so_jejak)]
