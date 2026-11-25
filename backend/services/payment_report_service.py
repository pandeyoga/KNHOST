"""Lapor Bayar CBD & DP (LB-T1) — kerangka layanan laporan bayar pelanggan.

Laporan bayar = sales/admin sales memberi tahu Finance bahwa pelanggan sudah membayar (bukti terlampir). Finance menerima
(lewat `ar_receipt_service.create_receipt`, satu-satunya pintu kas) atau menolak. Modul ini sengaja kecil: konstanta
status, penomoran, dan bentuk tampil. Pembuatan laporan (Tugas 3) dan keputusan terima/tolak (Tugas 4) ditambahkan di sini.
"""
from __future__ import annotations

from typing import Any, Dict

from core_utils import next_doc_number

MENUNGGU = "menunggu"
DITERIMA = "diterima"
DITOLAK = "ditolak"

#: Isian internal yang tidak pernah dikirim ke layar (kunci idempotensi dan klaim atomik).
_INTERNAL = ("_id", "idem_key", "claim")


async def next_number(entity_id: str) -> str:
    """Nomor laporan `LB-…` lewat penomoran baku dokumen (format & cara per PT dari tabel Penomoran Dokumen)."""
    return await next_doc_number("payment_reports", "number", "LB-", entity_id=entity_id)


def tampil(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Salinan dokumen untuk layar: tanpa `_id` dan isian internal."""
    return {k: v for k, v in (doc or {}).items() if k not in _INTERNAL}
