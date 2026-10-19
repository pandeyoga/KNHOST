"""LN-091/LN-092 — kebijakan penyelesaian retur (owner 2026-10-19: KLR-01/02/06/07/10).

Cutloss: customer menerima potongan baik, kompensasi HANYA qty cacat × harga transaksi awal.
Diskon: nominal rupiah per item untuk qty cacat, boleh tanpa barang kembali; nilai diputus Finance.
"""
from typing import Any, Dict


def cutloss_split(length: float, d_from: float, d_to: float) -> Dict[str, Any]:
    """Contoh resmi: 120 yd, cacat yd 46–60 → customer menerima 2 potong baik (45 & 60), kompensasi 15 yd."""
    if not (1 <= d_from <= d_to <= length):
        raise ValueError("Rentang cacat harus di dalam panjang roll")
    defect = d_to - d_from + 1
    pieces = [x for x in (d_from - 1, length - d_to) if x > 0]
    return {"length": length, "defect_qty": defect, "customer_pieces": pieces, "customer_keeps": length - defect,
            "compensation_qty": defect, "reconciles": abs(sum(pieces) + defect - length) < 1e-9}


async def simulate_cutloss(p: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    s = cutloss_split(p["roll_length"], p["defect_from"], p["defect_to"])
    return {**s, "unit_price": p["unit_price"], "compensation_value": round(s["compensation_qty"] * p["unit_price"], 2),
            "final": True, "rule": "KLR-01/KLR-02",
            "note": "Customer menerima potongan baik; kompensasi = qty cacat × harga transaksi awal (neto). "
                    "Qty cacat dicatat MD dalam yard saat QC; produk kg dikonversi otomatis."}


async def simulate_discount(p: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    return {"discount_value": round(float(p["amount"]), 2), "qty_affected": p["qty_affected"], "stock_movement": 0,
            "final": True, "rule": "KLR-06/KLR-07",
            "note": "Nominal rupiah per item untuk qty cacat; boleh tanpa barang kembali (bukti foto/video). "
                    "Nilai akhir diputus Finance."}


def split_credit(gross: float, open_amount: float, bill_first: bool) -> Dict[str, float]:
    """LN-091-T01 — kredit 30, tagihan 20 → potong tagihan 20, sisa 10 untuk refund/saldo."""
    ar = round(min(gross, max(open_amount, 0.0)), 2) if bill_first else 0.0
    return {"ar_part": ar, "excess": round(gross - ar, 2)}
