"""PK-28 (IV-03) — harga neto satu baris PO: SATU hitungan untuk nilai penerimaan barang (Dr Persediaan / Cr GR/IR)
dan nilai GR/IR yang dihapus faktur pemasok (`vendor_bills.grir_amount`).

Dipindahkan apa adanya dari penyelesaian penerimaan (`inbound_complete_service`, KN-A09): `line_total ÷ quantity` bila
`line_total` ada, selain itu `price × (1 − discount_percent/100)`; lalu dikali `(1 − order_discount_percent/100)` (diskon
kepala PO dibagi rata ke tiap baris); dibulatkan 4 desimal. Satuannya = satuan baris PO.
"""
from typing import Any, Dict, Optional

from services.vendor_bill_service import po_line_id


def _line_of(po: Dict[str, Any], product_id: str, line_id: str) -> Optional[Dict[str, Any]]:
    items = po.get("items") or []
    if line_id:
        hit = next((it for i, it in enumerate(items) if po_line_id(it, i) == line_id), None)
        if hit is not None:
            return hit
    if product_id:
        return next((it for it in items if it.get("product_id") == product_id), None)
    return None


def po_line_net_unit_price(po: Dict[str, Any], *, product_id: str = "", line_id: str = "") -> float:
    """Harga neto per satuan baris PO. Baris dicari lewat `line_id` (id baris PO, FN-02), lalu produk pertama yang
    cocok (perilaku penerimaan lama). Baris tidak ada → 0 (pemanggil memakai cadangannya sendiri)."""
    it = _line_of(po or {}, product_id, line_id)
    if it is None:
        return 0.0
    q = float(it.get("quantity", it.get("qty", 0)) or 0)
    lt = it.get("line_total")
    if lt is not None and q > 0:
        price = float(lt or 0) / q
    else:
        price = float(it.get("price", 0) or 0) * (1 - float(it.get("discount_percent", 0) or 0) / 100.0)
    hdr = float((po or {}).get("order_discount_percent", 0) or 0)
    if hdr > 0:
        price *= (1 - hdr / 100.0)
    return round(price, 4)
