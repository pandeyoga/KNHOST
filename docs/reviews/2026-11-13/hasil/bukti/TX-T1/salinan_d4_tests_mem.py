import uuid
import pytest
pytestmark = pytest.mark.anyio
def _tag():
    return uuid.uuid4().hex[:6]


async def test_zz_needs_app(aplikasi):
    pass


async def _priced_order(monkeypatch, *, mode="excluded", nl=True, tag=""):
    """SO sintetis yang dihitung MESIN HARGA ASLI (`compute_order_pricing`) — hanya setelan pajak yang dipatok."""
    from services import config_service as cs

    async def fake_settings(entity_id=None):
        return {"tax": {"ppn_rate": 12.0, "ppn_mode": mode, "is_pkp": True, "dpp_nilai_lain": nl},
                "sales": {"allow_item_discount": True, "allow_order_discount": True}}
    monkeypatch.setattr(cs, "get_effective_settings", fake_settings)
    # TX-T1 — aturan pajak kini dibaca satu pintu `tax_config_service.tax_settings` (bukan dokumen pengaturan gabungan):
    # setelan pajak yang dipatok sama, faktor & pembulatan = bawaan (11/12, per dokumen, dua desimal).
    from services import tax_config_service as tcs

    async def fake_tax(entity_id, at=None):
        return {"ppn_rate": 12.0, "dpp_nilai_lain": nl, "ppn_mode": mode, "dpp_pembilang": 11, "dpp_penyebut": 12,
                "pembulatan_tingkat": "dokumen", "pembulatan_satuan": "dua_desimal", "is_pkp": True, "berlaku_pada": ""}
    monkeypatch.setattr(tcs, "tax_settings", fake_tax)
    raw = [{"product_id": f"TEST_D4_p1_{tag}", "product_name": "Kain uji A", "sku": "UJI-A", "unit": "yard",
            "price": 10000, "quantity": 100, "discount_percent": 10},
           {"product_id": f"TEST_D4_p2_{tag}", "product_name": "Kain uji B", "sku": "UJI-B", "unit": "yard",
            "price": 5000, "quantity": 40}]
    priced = await (cs.compute_order_pricing(raw, f"TEST_D4_ent_{tag}", order_discount_percent=5))
    return {"id": f"TEST_D4_so_{tag}", "number": f"TEST-D4-{tag}", "entity_id": f"TEST_D4_ent_{tag}",
            "customer_name": "Toko Uji D4", "status": "reserved", **priced}


async def test_k03_preview_totals_excluded_nilai_lain(monkeypatch):
    from services import so_verify_service as sv
    order = await _priced_order(monkeypatch, tag=_tag())
    t = (await sv.order_preview(order))["totals"]
    # Bruto 1.000.000 + 200.000; diskon barang 100.000 + diskon pesanan 5% × 1.100.000 = 55.000.
    assert t["gross_subtotal"] == 1_200_000.0
    assert t["discount_total"] == 155_000.0
    assert t["net_subtotal"] == 1_045_000.0
    assert round(t["gross_subtotal"] - t["discount_total"], 2) == t["net_subtotal"]          # Subtotal − Diskon = DPP
    assert t["dpp_nilai_lain"] is True and t["ppn_mode"] == "excluded"
    assert t["dpp"] == round(1_045_000 * 11 / 12, 2)                                          # DPP nilai lain (11/12)
    assert t["ppn_amount"] == round(t["dpp"] * 0.12, 2)                                       # PPN 12% × DPP nilai lain
    assert round(t["net_subtotal"] + t["ppn_amount"], 2) == t["grand_total"]                  # DPP + PPN = Total
    # Bukti cacat lama: "Subtotal" (= net) − "Diskon" + PPN ≠ Total → diskon dibaca terpotong dua kali.
    old_reading = t["net_subtotal"] - t["discount_total"] + t["ppn_amount"]
    assert abs(old_reading - t["grand_total"]) == t["discount_total"]


async def test_k03_preview_totals_included_and_legacy(monkeypatch):
    from services import so_verify_service as sv
    order = await _priced_order(monkeypatch, mode="included", nl=False, tag=_tag())
    t = (await sv.order_preview(order))["totals"]
    assert t["ppn_mode"] == "included" and t["dpp_nilai_lain"] is False
    # Harga sudah termasuk PPN: bruto − diskon = Total; DPP (harga sebelum PPN) + PPN = Total.
    assert round(t["gross_subtotal"] - t["discount_total"], 2) == t["grand_total"]
    assert round((t["grand_total"] - t["ppn_amount"]) + t["ppn_amount"], 2) == t["grand_total"]
    assert t["ppn_amount"] > 0
    # Dokumen lama tanpa bendera dpp_nilai_lain / tanpa total bruto: None (layar mengenali sendiri) & bruto = net + diskon.
    legacy = {k: v for k, v in order.items() if k not in ("dpp_nilai_lain", "total_amount")}
    tl = (await sv.order_preview(legacy))["totals"]
    assert tl["dpp_nilai_lain"] is None
    assert tl["gross_subtotal"] == round(tl["net_subtotal"] + tl["discount_total"], 2)


