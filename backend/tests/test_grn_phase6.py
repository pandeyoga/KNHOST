"""GRN Fase 6 (packing list → daftar roll diharapkan) + nama/warna VERSI SUPPLIER di OCR + selisih di tagihan.

Membuktikan: nama barang & warna di SJ dicocokkan ke produk KN lewat Katalog Supplier (`supplier_items`) dan warna
supplier yang tersinkron ke produk (`products.supplier_colors`); packing list jadi roll diharapkan (angka disembunyikan
dari penghitung buta sampai diukur), roll diukur ditautkan & dibandingkan, selisih packing list masuk rekonsiliasi
(bukan pemblokir); simpan baris ke Katalog Supplier (tawaran); endpoint selisih SJ vs hitung untuk layar tagihan.
"""
import sys

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
import test_grn_phase2 as _p2  # noqa: E402
import test_grn_phase4_read as _p4  # noqa: E402
from services import dn_rules as R  # noqa: E402
from services.goods_receipt_service import roll_check  # noqa: E402
from test_grn_phase2 import BASE, _ok  # noqa: E402

admin, wh, mdb, env, ocr = _p2.admin, _p2.wh, _p2.mdb, _p2.env, _p4.ocr


# ── unit murni: nama & warna versi supplier ─────────────────────────────────────
TASKS = [
    {"id": "t_navy", "product_id": "p_navy", "product_name": "Katun Toyobo Biru Dongker",
     "supplier_names": ["COTTON COMBED 30S"], "internal_color": "Biru Dongker",
     "supplier_colors": [{"supplier_color_name": "NAVY 07", "supplier_color_code": "NV-07"}]},
    {"id": "t_red", "product_id": "p_red", "product_name": "Katun Toyobo Merah Cabe",
     "supplier_names": ["COTTON COMBED 30S"], "internal_color": "Merah Cabe",
     "supplier_colors": [{"supplier_color_name": "RED 12", "supplier_color_code": "RD-12"}]},
    {"id": "t_batik", "product_id": "p_batik", "product_name": "Batik Mega Mendung Premium",
     "supplier_names": ["Batik Cap Mega Mendung Premium"], "internal_color": "", "supplier_colors": []},
]


def test_supplier_color_name_decides_between_same_supplier_item():
    m = R.match_line({"description": "COTTON COMBED 30S", "color": "NAVY 07"}, TASKS, [])
    assert m["status"] == "probable" and m["task_id"] == "t_navy", m
    assert m["via"]["name_via"] == "supplier_name" and m["via"]["color_via"] in ("supplier_color", "supplier_color_code")


def test_supplier_color_code_inside_color_text():
    m = R.match_line({"description": "COTTON COMBED 30S", "color": "COL RD-12"}, TASKS, [])
    assert m["task_id"] == "t_red" and m["via"]["color_via"] == "supplier_color_code"


def test_item_code_can_be_supplier_color_code():
    m = R.match_line({"item_code": "NV 07", "description": "?"}, TASKS, [])
    assert m["status"] == "exact" and m["method"] == "supplier_color_code" and m["task_id"] == "t_navy"


def test_supplier_item_name_not_internal_name():
    m = R.match_line({"description": "BATIK CAP MEGA MENDUNG PREM", "color": None}, TASKS, [])
    assert m["task_id"] == "t_batik" and m["via"]["name_via"] == "supplier_name"


def test_supplier_sku_code_match_reports_supplier_name():
    items = [{"product_id": "p_batik", "supplier_sku": "CBN-MEGA-PREM", "supplier_item_name": "Batik Cap Mega Mendung Premium"}]
    m = R.match_line({"item_code": "cbn mega prem"}, TASKS, items)
    assert m["method"] == "item_code" and m["task_id"] == "t_batik" and m["via"]["name"] == "Batik Cap Mega Mendung Premium"


def test_without_color_same_supplier_name_stays_ambiguous():
    m = R.match_line({"description": "COTTON COMBED 30S", "color": None}, TASKS, [])
    assert m["status"] == "ambiguous" and m["task_id"] == ""     # manusia yang memilih — tidak menebak


# ── unit murni: packing list ──────────────────────────────────────────────────
def test_assign_packing_groups_by_lot_hint_and_lost():
    lines = [{"line_no": 1, "read": {"description": "BATIK MEGA", "lot": "L1"}},
             {"line_no": 2, "read": {"description": "LURIK SOLO", "lot": ""}},
             {"line_no": 3, "is_non_stock": True, "read": {"description": "HANGER"}}]
    groups = [{"lot": "l1", "item_hint": "", "rolls": [{"length": 10, "length_unit": "yd"}]},
              {"lot": None, "item_hint": "LURIK SOLO 40", "rolls": [{"length": 40}, {"length": 41}]},
              {"lot": None, "item_hint": "ZZZ", "rolls": [{"length": 1}]}]
    out, lost = R.assign_packing_groups(lines, groups)
    assert [r["seq"] for r in out[2]] == [1, 2] and out[1][0]["lot"] == "l1" and lost == [2]


def test_roll_check_links_and_converts_units():
    exp = [{"seq": 1, "length": 100, "length_unit": "m"}, {"seq": 2, "length": 50, "length_unit": "yd"},
           {"seq": 3, "length": 50, "length_unit": "yd"}]
    rows, rc = roll_check(exp, [{"id": "r1", "expected_seq": 1, "length": 109.36},
                                {"id": "r2", "expected_seq": 2, "length": 47}, {"id": "r9", "length": 5}], "yard")
    assert rows[0]["status"] == "counted" and rows[0]["diff"] == 0.0     # 100 m = 109,36 yd
    assert rc["missing"] == [3] and rc["extra"] == 1 and rc["diffs"] == [{"seq": 2, "expected": 50.0, "measured": 47.0, "diff": -3.0}]


# ── integrasi: packing list di OCR → hitung → rekonsiliasi → tagihan ──────────
def test_packing_list_expected_rolls_blind_count_and_bill_variance(admin, wh, mdb, env, ocr):
    _, clone = env
    t = clone(park_seed=True)
    mdb.purchase_orders.update_one({"id": t["po_id"]}, {"$set": {"po_number": "KSC/PO-00014"}})
    ocr({"receiving.ocr_model_primary": "mock-sj_packing", "receiving.ocr_extract_packing_list": True})
    try:
        g = _p4._grn_with_photo(admin, mdb, t)
        g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/read", json={"expected_version": g["version"]}))
    finally:
        ocr({"receiving.ocr_extract_packing_list": False})
    ln = g["lines"][0]
    assert ln["target"]["task_id"] == t["id"] and [r["length"] for r in ln["expected_rolls"]] == [85, 83, 82]
    assert any("HANGER" in w for w in g["extraction"]["warnings"])          # kelompok tanpa pasangan → peringatan
    # koreksi packing list oleh manusia (roll 3 ternyata 82,5) — sekaligus menandai baris dicek
    rolls = [{"length": 85, "length_unit": "yd", "lot": "PL-77"}, {"length": 83, "length_unit": "yd", "lot": "PL-77"},
             {"length": 82.5, "length_unit": "yd", "lot": "PL-77"}]
    g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/lines/1", json={"expected_version": g["version"], "expected_rolls": rolls}))
    assert g["lines"][0]["expected_rolls"][2]["length"] == 82.5 and g["lines"][0]["verified"] is True
    g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": "SJ-MOCK-PACK"}))
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))
    # hitung buta: panjang roll packing list tidak terlihat sebelum diukur
    b = _ok(wh.get(f"{BASE}/goods-receipts/{g['id']}"))
    assert b["blind"] and "length" not in b["lines"][0]["expected_rolls"][0] and b["lines"][0]["expected_rolls"][0]["lot"] == "PL-77"
    r1 = _ok(wh.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/rolls", json={"length": 85, "lot": "PL-77", "expected_seq": 1}))
    assert r1["roll"]["grn_expected_seq"] == 1
    assert wh.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/rolls",
                   json={"length": 85, "lot": "PL-77", "expected_seq": 1}).status_code == 409   # sudah diukur
    _ok(wh.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/rolls", json={"length": 80, "lot": "PL-77", "expected_seq": 2}))
    b = _ok(wh.get(f"{BASE}/goods-receipts/{g['id']}"))
    e1 = b["lines"][0]["expected_rolls"][0]
    assert e1["status"] == "counted" and e1["length"] == 85 and e1["measured"] == 85        # tampil setelah diukur
    assert "length" not in b["lines"][0]["expected_rolls"][2]
    g = _ok(admin.get(f"{BASE}/goods-receipts/{g['id']}"))
    rc = g["lines"][0]["roll_check"]
    assert rc["missing"] == [3] and rc["diffs"][0]["seq"] == 2
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": g["version"]}))
    pl = [d for d in g["discrepancies"] if d["kind"] == "packing_list_mismatch"]
    assert pl and pl[0]["blocking"] is False and "#3" in pl[0]["detail"]
    # selisih SJ vs hitung untuk layar tagihan: hanya GRN tertutup
    v = _ok(admin.get(f"{BASE}/goods-receipts/doc-variance", params={"po_id": t["po_id"]}))
    assert all(r["grn_id"] != g["id"] for r in v["rows"])   # GRN & roll uji dibersihkan fixture env


def test_doc_variance_requires_ref_and_save_catalog_rules(admin, mdb, env):
    assert admin.get(f"{BASE}/goods-receipts/doc-variance").status_code == 400
    _, clone = env
    t = clone(park_seed=True)
    g, _dn = _p2._grn_review(admin, mdb, t, qty=10, rolls=1)
    before = set(mdb.supplier_items.distinct("id"))
    try:
        r = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/save-catalog",
                           json={"expected_version": g["version"], "supplier_sku": "TEST_SJ-KODE-1",
                                 "supplier_item_name": "TEST_ NAMA VERSI SUPPLIER"}))
        assert r["existing"] is False and r["item"]["product_id"] == t["product_id"]
        assert r["item"]["supplier_item_name"] == "TEST_ NAMA VERSI SUPPLIER"
        again = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/save-catalog",
                               json={"expected_version": g["version"], "supplier_sku": "TEST_SJ-KODE-1"}))
        assert again["existing"] is True
    finally:
        mdb.supplier_items.delete_many({"id": {"$nin": list(before)}})
        g = _ok(admin.get(f"{BASE}/goods-receipts/{g['id']}"))
        _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/cancel", json={"expected_version": g["version"], "reason": "TEST_ batal"}))
