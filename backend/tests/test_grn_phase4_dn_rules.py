"""GRN Fase 4 — uji unit aturan murni `dn_rules` (masukan = JSON `read`, kasus dari Lampiran C)."""
import sys

sys.path.insert(0, "/app/backend")
from services import dn_rules as R  # noqa: E402

PAT = R.DEFAULT_PO_PATTERNS


def q(text, unit, role, basis=None):
    p = R.parse_doc_number(text)
    item = {"qty_text": text, "qty": p["value"], "unit": unit, "role": role, "weight_basis": basis}
    item.update({"value": p["value"], "candidates": p["candidates"], "status": R.qty_status(item, p)})
    return item


def test_parse_numbers_s07_two_formats():
    assert R.parse_doc_number("2,186.00")["value"] == 2186
    assert R.parse_doc_number("19,00")["value"] == 19
    assert R.parse_doc_number("1.657,00")["value"] == 1657
    assert R.parse_doc_number("1.202.500")["value"] == 1202500


def test_parse_ambiguous_thousands_vs_decimal():
    p = R.parse_doc_number("1.250")
    assert p["ambiguous"] and sorted(p["candidates"]) == [1.25, 1250]
    assert R.parse_doc_number("12,500")["ambiguous"]
    assert R.parse_doc_number("1.250", "id")["value"] == 1250      # profil supplier: koma desimal
    assert R.parse_doc_number("1.250", "en")["value"] == 1.25


def test_s06_overwritten_digit_resolved_by_total():
    # 123.05 + 295.35 + (600.9 | 606.9) = 1019.30 → hanya 600.9 cocok
    assert R.resolve_by_total([[123.05], [295.35], [600.9, 606.9]], 1019.30) == [123.05, 295.35, 600.9]
    assert R.resolve_by_total([[1.25, 1250]], None) is None


def test_s12_greige_never_declared_and_unclear_skipped():
    qs = [q("1.657,00", "m", "greige_length"), q("404,29", "kg", "unclear"), q("31", "pcs", "delivered_count"),
          q("1.824,00", "yd", "delivered_length")]
    d = R.pick_declared(qs, "yard")
    assert d["qty"] == 1824 and d["unit"] == "yard" and d["rolls"] == 31 and d["weight_kg"] is None


def test_s11_kg_yard_roll_net():
    qs = [q("179.28", "kg", "delivered_weight", "net"), q("1,130.00", "yd", "delivered_length"),
          q("10.00", "roll", "delivered_count")]
    d = R.pick_declared(qs, "yard")
    assert (d["qty"], d["rolls"], d["weight_kg"], d["weight_basis"]) == (1130, 10, 179.28, "net")
    d_kg = R.pick_declared(qs, "kg")
    assert d_kg["qty"] == 179.28 and d_kg["unit"] == "kg"


def test_ambiguous_number_blocks():
    d = R.pick_declared([q("1.250", "yd", "delivered_length")], "yard")
    assert d["qty"] is None and d["qty_parse"] == "ambiguous"


def test_po_patterns_client_vs_supplier_numbers():
    assert R.po_cores(["PO.7460/CST/0726"], PAT) == ["7460"]
    assert R.po_cores(["PO/AML/2607-0272"], PAT) == []                        # S03: nomor milik supplier
    assert R.po_cores(["SPS/02/2606/1103/1458/VI/26/7403/CST/0626"], PAT) == ["7403"]   # S11: terselip
    pos = [{"id": "a", "po_number": "KSC/PO-07460"}, {"id": "b", "po_number": "KSC/PO-07461"}]
    assert R.match_po(["PO.7460/CST/0726"], pos, PAT)["po_id"] == "a"
    assert R.match_po(["KSC/PO-07461"], pos, PAT) == {"status": "exact", "po_id": "b", "candidates": ["b"]}
    two = pos + [{"id": "c", "po_number": "SBY/PO-7460"}]
    m = R.match_po(["7460/CST/0726"], two, PAT)
    assert m["status"] == "ambiguous" and m["po_id"] == "" and set(m["candidates"]) == {"a", "c"}


def test_line_matching_rules():
    tasks = [{"id": "t1", "product_id": "p1", "product_name": "Odeza Twill Navy"},
             {"id": "t2", "product_id": "p2", "product_name": "Chinno Cotton Cream"}]
    items = [{"product_id": "p2", "supplier_sku": "M14505"}]
    assert R.match_line({"item_code": "M14505"}, tasks, items)["task_id"] == "t2"
    assert R.match_line({"description": "ODEZA TWILL NAVY"}, tasks, [])["status"] == "probable"
    assert R.match_line({"description": "KAIN LAIN"}, tasks[:1], [])["method"] == "single_line"
    assert R.match_line({"description": "KAIN LAIN"}, tasks, [])["task_id"] == ""


def test_totals_and_name_checks():
    lines = [{"quantities": [{"unit": "kg", "role": "delivered_weight", "value": 781.34}]}]
    assert R.check_totals(lines, [{"qty_text": "783,48", "qty": None, "unit": "kg"}])[0]["printed"] == 783.48
    assert not R.name_mismatch("PT. GUCCI RATU TEXTILE INDUSTRY", ["Guccitex", "PT Gucci Ratu Textile Industry"])
    assert R.name_mismatch("PT MAJU JAYA", ["Cirebon Craft"])
    assert not R.name_mismatch("", ["x"])
    assert not R.name_mismatch("CIPTA SANDANG TEXTILLE", ["Cipta Sandang Textile"], 0.7)   # S12 salah eja
