"""GRN Fase 5 (makloon) + profil SJ otomatis + validasi manual hasil OCR.

Membuktikan: OCR = usulan (kepala & baris wajib dicek sebelum hitung, koreksi tercatat), SJ makloon terpetakan ke
langkah MKO (nomor MKO), baris BS → barang sisa bila langkah punya produk sisa, penutupan memposting receive_step
dengan supplier_dn + berat roll + barang sisa, dan profil mitra belajar format angka / nama lain / pemetaan barang.
"""
import io
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
import test_grn_phase2 as _p2  # noqa: E402
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402
from services import dn_rules as R  # noqa: E402
from services import supplier_dn_profile_service as P  # noqa: E402
from test_grn_phase2 import BASE, _ok  # noqa: E402

admin, mdb = _p2.admin, _p2.mdb
MKO, MAK = "mko_e7566f649bf7", "mak_seed_tenun"
CFG_ON = {"receiving.ocr_enabled": True, "receiving.ocr_model_primary": "mock-sj_makloon",
          "receiving.ocr_second_reader_mode": "off"}
CFG_OFF = {"receiving.ocr_enabled": False, "receiving.ocr_model_primary": "gpt-6-sol",
           "receiving.ocr_second_reader_mode": "on_doubt"}


# ── unit murni ────────────────────────────────────────────────────────────────
def test_infer_locale_and_desc_key():
    assert R.infer_locale("1.250,00") == "id" and R.infer_locale("2,186.00") == "en"
    assert R.infer_locale("19,00") == "id" and R.infer_locale("12.5") == "en"
    assert R.infer_locale("1.250") == "" and R.infer_locale("21") == ""
    assert R.desc_key({"item_code": "kp.e1"}) == "code:KP_E1"
    assert R.desc_key({"description": "Kain  Grey, Katun", "color": "Putih"}) == "desc:kain grey katun putih"


def test_match_line_uses_learned_profile_first():
    tasks = [{"id": "t1", "product_id": "p1", "product_name": "Batik A"},
             {"id": "t2", "product_id": "p2", "product_name": "Batik B"}]
    read = {"description": "ZX-99 KAIN ANEH", "color": None}
    assert R.match_line(read, tasks, [])["status"] == "ambiguous"
    m = R.match_line(read, tasks, [], {R.desc_key(read): {"product_id": "p2"}})
    assert m["status"] == "exact" and m["method"] == "profile" and m["task_id"] == "t2"


def test_profile_locale_evidence_alias_and_items():
    grn = {"partner_name": "Cirebon Craft", "dn": {"supplier_name_printed": "PT MEGA JAYA TEKSTIL"}, "lines": [
        {"verified": True, "decision": "accept", "declared": {"qty": 1250},
         "target": {"product_id": "p1", "product_name": "Batik"},
         "read": {"source": "ocr", "description": "BATIK MEGA", "quantities": [
             {"qty_text": "1.250", "role": "delivered_length"}, {"qty_text": "2,00", "role": "delivered_count"}]}},
        {"verified": False, "decision": "accept", "read": {"source": "ocr", "quantities": [{"qty_text": "3.5"}]}}]}
    assert P._locale_evidence(grn) == {"id": 2, "en": 0}      # baris belum dicek tidak dihitung
    assert P._decide_locale({"id": 2, "en": 0}) == "id" and P._decide_locale({"id": 3, "en": 2}) == "unknown"
    assert P._alias_to_add({"aliases": []}, grn) == "PT MEGA JAYA TEKSTIL"
    assert P._alias_to_add({"aliases": ["PT MEGA JAYA TEKSTIL"]}, grn) == ""
    assert P._item_learnings(grn) == {"desc:batik mega": {"product_id": "p1", "product_name": "Batik", "text": "BATIK MEGA"}}
    assert P.active_locale({"number_locale": "id", "confirmed_count": 2}) == "unknown"
    assert P.active_locale({"number_locale": "id", "confirmed_count": 3}) == "id"
    assert P.active_locale({"number_locale": "en", "locale_locked": True}) == "en"


# ── alur makloon penuh ───────────────────────────────────────────────────────
@pytest.fixture()
def mk_env(mdb):
    if mdb.makloon_orders.find_one({"id": MKO, "steps.0.status": "issued"}) is None:
        pytest.skip("seed MKO-00002 langkah 1 tidak issued")
    full = snapshot_stock(["inventory_rolls", "inventory_balances", "number_sequences", "makloon_orders",
                           "inventory_lots", "supplier_dn_profiles"])
    assert full.get("__enabled__")
    ids = snapshot_new_ids(["inventory_movements", "journal_entries", "vendor_bills", "goods_receipts", "notifications",
                            "audit_logs", "doc_refs", "ai_usage_log", "inventory_lots"])
    yield
    _cfg(_p2._login("admin@kainnusantara.id"), CFG_OFF)
    purge_new_ids(ids)
    restore_stock(full)


def _cfg(s, values):
    items = [{"key": k, "value": v, "scope_type": "global", "reason": "TEST_ uji fase 5"} for k, v in values.items()]
    _ok(s.put(f"{BASE}/config/values", json={"items": items}))


def _photo():
    buf = io.BytesIO()
    Image.new("RGB", (1200, 1600), "white").save(buf, "JPEG")
    return buf.getvalue()


def test_makloon_ocr_validate_count_close_and_learn(admin, mdb, mk_env):
    if os.environ.get("OCR_ALLOW_MOCK") != "1" and "OCR_ALLOW_MOCK" not in open("/app/backend/.env").read():
        pytest.skip("OCR_ALLOW_MOCK tidak aktif")
    _cfg(admin, CFG_ON)
    g = _ok(admin.post(f"{BASE}/goods-receipts", json={"partner_type": "makloon", "partner_id": MAK,
                                                       "warehouse_id": "wh_surabaya", "mko_ids": [MKO]}))
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/files", files={"file": ("sj.jpg", _photo(), "image/jpeg")},
                       data={"expected_version": str(g["version"])}))["grn"]
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/read", json={"expected_version": g["version"]}))
    l1, l2 = g["lines"]
    assert l1["target"]["type"] == "mko_step" and l1["target"]["mko_id"] == MKO and l1["role"] == "output"
    assert l1["declared"]["qty"] == 72.5 and l1["declared"]["unit"] == "yard" and l1["declared"]["rolls"] == 3
    assert l2["role"] == "byproduct" and l2["declared"]["grade"] == "BS" and l2["declared"]["qty"] == 4.2
    assert g["dn"]["verified"] is False and l1["verified"] is False and g["extraction"]["profile_used"]["confirmed_count"] == 0
    # OCR = usulan: belum dicek → tidak boleh hitung
    r = admin.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]})
    msg = r.json()["detail"]["message"]
    assert r.status_code == 400 and "Kepala SJ" in msg and "Baris 1: hasil baca otomatis belum dicek" in msg
    # manusia: kepala SJ dikoreksi (nomor salah baca), baris 1 dikoreksi qty, baris 2 dicentang
    g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": "SJ-MKL-0139A"}))
    assert g["dn"]["verified"] is True and g["dn"]["corrected_fields"] == ["number"]
    g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/lines/1", json={"expected_version": g["version"], "declared": {
        "qty": 72.0, "unit": "yard", "rolls": 3, "lot": "071225"}}))
    assert g["lines"][0]["verified"] is True and g["lines"][0]["corrected"] is True and "qty" in g["lines"][0]["corrected_fields"]
    g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/lines/2", json={"expected_version": g["version"], "verified": True}))
    assert g["lines"][1]["verified"] is True and not g["lines"][1].get("corrected")
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))
    for length, kg in ((24.0, 5.1), (24.0, 5.0), (24.0, 4.9)):
        g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/rolls", json={
            "length": length, "weight_kg": kg, "lot": "071225", "grade": "A"}))["grn"]
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/lines/2/rolls", json={"length": 4.2, "grade": "BS"}))["grn"]
    assert g["lines"][1]["counted"]["makloon_rolls"][0]["lot"] == "SISA-MKO-00002-1"
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": g["version"]}))
    for d in [d for d in g.get("discrepancies") or [] if d.get("blocking") and d.get("status") == "open"]:
        g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/discrepancies/{d['key']}/resolve", json={
            "expected_version": g["version"], "action": "accept_note", "reason": "TEST_ terima"}))
    res = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]}))
    assert res["grn"]["status"] == "closed", res
    step = mdb.makloon_orders.find_one({"id": MKO})["steps"][0]
    assert step["status"] == "received" and step["supplier_dn"] == "SJ-MKL-0139A"
    assert step["actual_output_qty"] == 72.0 and step["actual_byproduct_qty"] == 4.2
    assert step["byproduct_lot"] == "SISA-MKO-00002-1" and all(lot.get("weight_kg") for lot in step["lots"])
    roll = mdb.inventory_rolls.find_one({"id": step["lots"][0]["roll_id"]})
    assert roll["weight_kg"] == 5.1
    prof = _ok(admin.get(f"{BASE}/goods-receipts/dn-profiles/{MAK}"))
    assert prof["confirmed_count"] >= 1 and prof["locale_votes"]["id"] >= 2 and "PT TENUN NUSANTARA" not in prof["aliases"]
    assert prof["ocr_lines_total"] == 2 and prof["ocr_lines_corrected"] == 1 and prof["ocr_accuracy_pct"] == 50.0
    assert any(i["product_id"] == "prod_grey_katun" for i in prof["item_map"])
    # admin mengunci format & menambah nama lain
    p2 = _ok(admin.patch(f"{BASE}/goods-receipts/dn-profiles/{MAK}", json={"number_locale": "id", "add_alias": "TENUN NJ"}))
    assert p2["active_locale"] == "id" and p2["locale_locked"] is True and "TENUN NJ" in p2["aliases"]
    assert any(p["partner_id"] == MAK for p in _ok(admin.get(f"{BASE}/goods-receipts/dn-profiles")))


def test_byproduct_needs_output_line_and_role_question(admin, mdb, mk_env):
    g = _ok(admin.post(f"{BASE}/goods-receipts", json={"partner_type": "makloon", "partner_id": MAK,
                                                       "warehouse_id": "wh_surabaya", "mko_ids": [MKO]}))
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/manual-entry", json={"expected_version": g["version"]}))
    g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": "SJ-T5-BP"}))
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/lines", json={
        "expected_version": g["version"], "declared": {"qty": 3, "unit": "kg", "grade": "BS"}, "role": "byproduct",
        "target": {"type": "mko_step", "mko_id": MKO, "step_seq": 1}, "description": "TEST_ sisa"}))
    r = admin.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]})
    assert r.status_code == 400 and "butuh baris output" in r.json()["detail"]["message"]
    g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/lines/1", json={"expected_version": g["version"], "role": "output"}))
    assert g["lines"][0]["role"] == "output"
    _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/cancel", json={"expected_version": g["version"], "reason": "TEST_ batal"}))
