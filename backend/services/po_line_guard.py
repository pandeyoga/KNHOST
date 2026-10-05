"""KN-B15 — satu produk hanya boleh muncul di SATU baris PO (semua jalur: buat PO, PR→PO, amandemen).

Tugas penerimaan dibuat per produk dan `items.$.received_qty` mengunci baris pertama, sehingga baris
kembar membuat penerimaan & HPP mendarat di baris yang salah.
"""
from typing import Iterable


def duplicate_line_message(product_ids: Iterable[str]) -> str:
    """Pesan tolak bila ada produk kembar; string kosong bila aman."""
    pids = list(product_ids)
    dups = sorted({p for p in pids if pids.count(p) > 1})
    if not dups:
        return ""
    return ("Produk yang sama muncul di lebih dari satu baris PO — gabungkan kuantitasnya "
            f"menjadi satu baris: {', '.join(dups)}")
