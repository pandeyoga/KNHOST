"""LN-091/LN-092 — kebijakan penyelesaian retur (asumsi configurable sambil menunggu KLR-01/02/06/07/10).

Cutloss & diskon hanya SIMULASI selama mode = pending (LN-092-T03: tidak dibuka dengan default sendiri).
"""
from typing import Any, Dict, List

from services.return_policy_service import return_assumptions

CUT_PARTS = {
    "pending": "Belum diputuskan (KLR-01)",
    "defect_only": "Customer mengembalikan HANYA bagian cacat",
    "defect_plus_shorter": "Bagian cacat + sisi baik yang lebih pendek dikembalikan",
    "whole_roll": "Seluruh roll dikembalikan",
}
VALUE_BASIS = {"pending": "Belum diputuskan (KLR-02)", "line_price": "Harga jual per satuan pada SO",
               "net_after_discount": "Harga neto setelah diskon baris"}


def cutloss_split(length: float, d_from: float, d_to: float, part: str) -> Dict[str, float]:
    """Contoh resmi: 120 yd, cacat yd 46–60 → baik 45 (1–45) & 60 (61–120), cacat 15."""
    if not (1 <= d_from <= d_to <= length):
        raise ValueError("Rentang cacat harus di dalam panjang roll")
    defect = d_to - d_from + 1
    left, right = d_from - 1, length - d_to
    if part == "defect_only":
        returned = defect
    elif part == "defect_plus_shorter":
        returned = defect + min(left, right)
    else:
        returned = length
    keeps = length - returned
    good_back = returned - defect
    return {"length": length, "defect_qty": defect, "good_left": left, "good_right": right,
            "customer_keeps": keeps, "returned_qty": returned, "restock_good_qty": good_back, "waste_qty": defect,
            "compensation_qty": returned, "reconciles": abs(keeps + good_back + defect - length) < 1e-9}


async def simulate_cutloss(p: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    a = await return_assumptions(entity_id)
    part, basis = a.get("cutloss_return_part", "pending"), a.get("cutloss_value_basis", "pending")
    scenarios: List[Dict[str, Any]] = []
    for code in ("defect_only", "defect_plus_shorter", "whole_roll"):
        s = cutloss_split(p["roll_length"], p["defect_from"], p["defect_to"], code)
        scenarios.append({"code": code, "label": CUT_PARTS[code], **s,
                          "compensation_value": round(s["compensation_qty"] * p["unit_price"], 2)})
    final = part != "pending" and basis != "pending"
    return {"scenarios": scenarios, "selected": part if part != "pending" else None,
            "value_basis": basis, "value_basis_label": VALUE_BASIS.get(basis, basis), "final": final,
            "posting_locked": True,
            "note": ("Simulasi berdasarkan ASUMSI yang dikonfigurasi; posting cutloss tetap dikunci sampai owner "
                     "memutuskan KLR-01/KLR-02.") if final else
                    "KLR-01/KLR-02 belum diputuskan — semua skenario ditampilkan berdampingan, tidak ada yang dipilih."}


async def simulate_discount(p: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    a = await return_assumptions(entity_id)
    mode = a.get("discount_mode", "pending")
    value = round(p["qty_affected"] * p["unit_price"] * p["pct"] / 100, 2)
    return {"discount_value": value, "stock_movement": 0, "mode": mode,
            "requires_exception": mode == "pending",
            "note": "Barang tetap di customer: stok gudang tidak bertambah. Selama KLR-06/07 pending, penyelesaian "
                    "'nego' wajib pengecualian QC yang disetujui + foto bukti."}


def split_credit(gross: float, open_amount: float, bill_first: bool) -> Dict[str, float]:
    """LN-091-T01 — kredit 30, tagihan 20 → potong tagihan 20, sisa 10 untuk refund/saldo."""
    ar = round(min(gross, max(open_amount, 0.0)), 2) if bill_first else 0.0
    return {"ar_part": ar, "excess": round(gross - ar, 2)}
