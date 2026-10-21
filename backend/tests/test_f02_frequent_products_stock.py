"""F-02 (uji pra-UAT 2026-10-21) — strip "Sering dibeli" di Kasir menulis "0 roll tersedia".

Reproduksi: `GET /api/sales-orders/frequent-products` mengembalikan dokumen produk mentah tanpa `roll_count`/stok →
kartu checkout (CheckoutItemCard) menampilkan 0 roll padahal stok ada. Kini memakai helper stok yang sama dengan
katalog Kasir (`sales_stock_service.apply_global`) sehingga angkanya sama dengan katalog.
Jalankan: cd /app/backend && python -m pytest tests/test_f02_frequent_products_stock.py -p no:randomly -n 0 -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402

CUST = "cust_toko_kain"


def test_sering_dibeli_membawa_stok_sama_dengan_katalog():
    api = base.Api("sales@kainnusantara.id")
    c, freq = api.call("GET", "/sales-orders/frequent-products", params={"customer_id": CUST, "limit": 24})
    assert c == 200 and freq, freq
    c, dash = api.call("GET", "/dashboard")
    assert c == 200, dash
    cat = {p["id"]: p for p in dash["products"]}
    with_stock = [p for p in freq if p["id"] in cat and int(cat[p["id"]].get("roll_count") or 0) > 0]
    assert with_stock, "data acuan: pelanggan ini pernah membeli produk yang masih berstok"
    for p in with_stock:
        assert "roll_count" in p, p.get("id")                                  # dulu: tidak ada → "0 roll"
        assert int(p["roll_count"]) == int(cat[p["id"]]["roll_count"]), (p["id"], p["roll_count"], cat[p["id"]]["roll_count"])
        assert abs(float(p.get("available_qty") or 0) - float(cat[p["id"]].get("available_qty") or 0)) < 0.05
