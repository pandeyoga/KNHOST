"""P05 — uji penerimaan ACC-31 · ACC-33 · ACC-34 + rekonsiliasi WIP (1-1350) dengan Finance.

Fixture: MKO uji dibuat dari pola MKO-00004 (data acuan seed_p05_kn, ent_ksc, gudang wh_jakarta).
Data uji berlabel TEST_P05ACC; pulihkan data acuan sesudahnya: bash /app/scripts/restore_local_demo.sh
"""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
ENT = "ent_ksc"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
WIP = "1-1350"
S = {}


def _login(email, password="demo1234", ent=ENT):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module", autouse=True)
def output_is_makloon():
    """Artikel hasil MKO uji diatur 'makloon' selama uji (DEC-07: unknown=block), lalu dikembalikan."""
    out = DB.products.find_one({"id": _tpl()["steps"][0]["output_product_id"]}, {"_id": 0, "template_id": 1})
    tpl = DB.product_templates.find_one({"id": out["template_id"]}, {"_id": 0, "id": 1, "restock_source": 1})
    before = tpl.get("restock_source")
    DB.product_templates.update_one({"id": tpl["id"]}, {"$set": {"restock_source": {
        "mode": "makloon", "note": "TEST_P05ACC"}}})
    yield
    DB.md_samples.delete_many({"brief": {"$regex": "^TEST_P05ACC"}})
    if before:
        DB.product_templates.update_one({"id": tpl["id"]}, {"$set": {"restock_source": before}})
    else:
        DB.product_templates.update_one({"id": tpl["id"]}, {"$unset": {"restock_source": ""}})


def _tpl():
    return DB.makloon_orders.find_one({"mko_number": "MKO-00004", "entity_id": ENT}, {"_id": 0})


def _free(pid, wh):
    rows = DB.inventory_rolls.find({"product_id": pid, "warehouse_id": wh, "status": "available"},
                                   {"_id": 0, "length_remaining": 1})
    return round(sum(float(r.get("length_remaining") or 0) for r in rows), 2)


def _reserved_active(pid):
    return round(sum(float(r.get("qty") or 0) for r in DB.material_reservations.find(
        {"product_id": pid, "status": "active"}, {"_id": 0, "qty": 1})), 2)


def _wip(mko_number):
    """Saldo 1-1350 dari jurnal milik satu MKO (issue, jasa, terima, reversal)."""
    bal = 0.0
    for j in DB.journal_entries.find({"status": "posted", "$or": [
            {"source_label": {"$regex": f"^{mko_number}\\b"}}, {"description": {"$regex": f"{mko_number}\\b"}}]},
            {"_id": 0, "lines": 1}):
        for ln in j.get("lines") or []:
            if ln.get("account_code") == WIP:
                bal += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(bal, 2)


def _create(h, qty, note):
    t = _tpl()
    st = t["steps"][0]
    body = {"mode": "process_only", "material_product_id": t["material_product_id"], "material_qty": qty,
            "material_unit": t.get("material_unit") or "yard", "from_warehouse_id": t["from_warehouse_id"],
            "target_warehouse_id": t.get("target_warehouse_id") or t["from_warehouse_id"], "entity_id": ENT,
            "notes": f"TEST_P05ACC {note}", "manual_material_reason": "TEST_P05ACC resep belum diisi",
            "steps": [{k: st.get(k) for k in ("process_type", "stage_code", "material_flow", "makloon_id",
                                               "contract_id", "input_product_id", "output_product_id")}
                      | {"input_qty": qty}]}
    r = requests.post(f"{BASE}/api/makloon-orders", json=body, headers=h, timeout=60)
    assert r.status_code == 200, r.text[:400]
    return r.json()


class TestACC34PartialCompleteCancel:
    def test_reserve_then_partial_issue(self, adm):
        t = _tpl()
        pid, wh = t["material_product_id"], t["from_warehouse_id"]
        S.update(pid=pid, wh=wh, free0=_free(pid, wh), res0=_reserved_active(pid))
        mko = _create(adm, 100, "parsial")
        S["a"] = mko
        res = DB.material_reservations.find_one({"ref_id": mko["id"]}, {"_id": 0})
        assert res and res["status"] == "active" and res["qty"] + res["shortage_qty"] == pytest.approx(100)
        assert _free(pid, wh) == pytest.approx(S["free0"])          # cadangan tidak memindah fisik
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue",
                          json={"step_seq": 1, "doc_uom": "yard", "doc_qty": 60}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:400]
        S["value_a"] = float(r.json()["steps"][0]["material_value"])
        res = DB.material_reservations.find_one({"ref_id": mko["id"]}, {"_id": 0})
        assert res["status"] == "active" and res["qty"] == pytest.approx(res["required_qty"] - 60 - res["shortage_qty"])
        assert _free(pid, wh) == pytest.approx(S["free0"] - 60, abs=0.05)
        assert _wip(mko["mko_number"]) == pytest.approx(S["value_a"], abs=1)

    def test_retry_issue_no_double_decrement(self, adm):
        r = requests.post(f"{BASE}/api/makloon-orders/{S['a']['id']}/issue",
                          json={"step_seq": 1, "doc_uom": "yard", "doc_qty": 60}, headers=adm, timeout=60)
        assert r.status_code in (400, 409), r.text[:200]
        assert _free(S["pid"], S["wh"]) == pytest.approx(S["free0"] - 60, abs=0.05)
        n = DB.journal_entries.count_documents({"source_type": "subcon_issue", "source_id": f"{S['a']['id']}:1"})
        assert n == 1

    def test_receive_completes_releases_leftover_and_wip_zero(self, adm):
        mko = S["a"]
        body = {"step_seq": 1, "actual_output_qty": 59, "rolls": [{"lot": "TEST_P05ACC-L1", "length": 59, "grade": "A"}]}
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/receive", json=body, headers=adm, timeout=90)
        assert r.status_code == 200, r.text[:400]
        S["a_status"] = r.json()["status"]
        assert S["a_status"] == "completed", r.json().get("completion_hold")
        res = DB.material_reservations.find_one({"ref_id": mko["id"]}, {"_id": 0})
        assert res["status"] == "released" and "MKO selesai" in res.get("release_reason", "")
        assert _reserved_active(S["pid"]) == pytest.approx(S["res0"])
        assert _wip(mko["mko_number"]) == pytest.approx(0, abs=1)
        # Bahan yang sudah dikirim ke mitra TIDAK kembali sebagai stok gudang.
        assert _free(S["pid"], S["wh"]) == pytest.approx(S["free0"] - 60, abs=0.05)

    def test_cancel_unissued_releases_commitment(self, adm):
        mko = _create(adm, 40, "batal-belum-issue")
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_P05ACC batal"},
                          headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert DB.material_reservations.find_one({"ref_id": mko["id"]})["status"] == "released"
        assert _wip(mko["mko_number"]) == pytest.approx(0, abs=1)

    def test_cancel_after_issue_keeps_material_at_partner(self, adm):
        """DEC-13: batal sesudah issue → bahan TETAP di mitra & WIP tetap sampai retur dicatat."""
        mko = _create(adm, 30, "batal-sesudah-issue")
        S["c"] = mko
        free_before = _free(S["pid"], S["wh"])
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue", json={"step_seq": 1}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        S["value_c"] = float(r.json()["steps"][0]["material_value"])
        free_issued = _free(S["pid"], S["wh"])
        assert free_issued == pytest.approx(free_before - 30, abs=0.05)
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_P05ACC batal"},
                          headers=adm, timeout=60)
        assert r.status_code == 200
        st = r.json()["steps"][0]
        assert r.json()["status"] == "cancelled" and st["status"] == "issued" and st["awaiting_return"] is True
        assert _free(S["pid"], S["wh"]) == pytest.approx(free_issued, abs=0.05)   # tidak kembali otomatis
        assert _wip(mko["mko_number"]) == pytest.approx(S["value_c"], abs=1)       # WIP tetap
        assert DB.material_reservations.find_one({"ref_id": mko["id"]})["status"] == "consumed"
        d = requests.get(f"{BASE}/api/makloon-orders/{mko['id']}", headers=adm, timeout=30).json()
        assert d["steps"][0]["next_action"] == "return_material" and d["steps"][0]["subcon_qty"] == pytest.approx(30, abs=0.05)
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/receive", json={
            "step_seq": 1, "actual_output_qty": 29, "rolls": [{"lot": "TEST_P05ACC-X", "length": 29, "grade": "A"}]},
            headers=adm, timeout=60)
        assert r.status_code == 409                                              # order batal: bukan terima hasil

    def test_return_material_after_cancel(self, adm):
        mko = S["c"]
        url = f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/return-material"
        free_before = _free(S["pid"], S["wh"])
        assert requests.post(url, json={"reason": "x"}, headers=adm, timeout=30).status_code == 400
        r = requests.post(url, json={"reason": "TEST_P05ACC SJ retur mitra"}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["steps"][0]["status"] == "returned" and r.json()["material_at_partner"] is False
        assert _free(S["pid"], S["wh"]) == pytest.approx(free_before + 30, abs=0.05)
        assert _wip(mko["mko_number"]) == pytest.approx(0, abs=1)
        assert requests.post(url, json={"reason": "TEST_P05ACC ulang"}, headers=adm, timeout=30).status_code == 409
        n = DB.journal_entries.count_documents({"source_type": "subcon_issue_reversal", "source_id": f"{mko['id']}:1"})
        assert n == 1

    def test_return_rejected_for_active_order(self, adm):
        r = requests.post(f"{BASE}/api/makloon-orders/{S['a']['id']}/steps/1/return-material",
                          json={"reason": "TEST_P05ACC salah order"}, headers=adm, timeout=30)
        assert r.status_code == 409


class TestACC33Shortage:
    def test_shortage_visible_and_not_guessed(self, adm):
        t = _tpl()
        free = _free(t["material_product_id"], t["from_warehouse_id"])
        mko = _create(adm, round(free + 5000, 2), "kurang")
        res = DB.material_reservations.find_one({"ref_id": mko["id"]}, {"_id": 0})
        assert res["shortage_qty"] > 0 and res["qty"] < res["required_qty"]
        assert res["product_id"] == t["material_product_id"]                # bahan dipilih per ID, bukan nama
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue", json={"step_seq": 1}, headers=adm, timeout=60)
        assert r.status_code in (400, 409), r.text[:200]                     # tidak dijanjikan melebihi stok
        requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_P05ACC"}, headers=adm, timeout=60)

    def test_manual_basis_needs_reason(self, adm):
        t = _tpl()
        st = t["steps"][0]
        body = {"mode": "process_only", "material_product_id": t["material_product_id"], "material_qty": 10,
                "from_warehouse_id": t["from_warehouse_id"], "entity_id": ENT, "notes": "TEST_P05ACC",
                "steps": [{k: st.get(k) for k in ("process_type", "stage_code", "material_flow", "makloon_id",
                                                   "contract_id", "input_product_id", "output_product_id")}
                          | {"input_qty": 10}]}
        r = requests.post(f"{BASE}/api/makloon-orders", json=body, headers=adm, timeout=60)
        assert r.status_code in (400, 409, 422), r.text[:200]


RCP = {"per_pcs_m": 1.6, "waste_pct": 5.0, "roll_m": 50.0, "target": 100}


@pytest.fixture(scope="class")
def recipe_fixture(adm):
    """Resep acuan pemilik: 1 kemeja = 1,6 m kain; kain dicatat per roll (1 roll = 50 m); yield 95%."""
    kain = {"id": "TEST_P05ACC_kain", "sku": "TEST_P05ACC-KAIN", "name": "TEST_P05ACC Kain Kemeja",
            "base_unit": "meter", "stage": "greige", "status": "active",
            "uom_conversions": [{"from_unit": "roll", "to_unit": "meter", "factor": RCP["roll_m"]}]}
    mirip = {**kain, "id": "TEST_P05ACC_kain_mirip", "sku": "TEST_P05ACC-KAIN-B", "name": "TEST_P05ACC Kain Kemeja B",
             "uom_conversions": []}
    kemeja = {"id": "TEST_P05ACC_kemeja", "sku": "TEST_P05ACC-KMJ", "name": "TEST_P05ACC Kemeja",
              "base_unit": "pcs", "stage": "finished", "status": "active"}
    DB.products.insert_many([dict(kain), dict(mirip), dict(kemeja)])
    r = requests.post(f"{BASE}/api/process-recipes", json={
        "name": "TEST_P05ACC Jahit Kemeja", "process_type": "jahit", "input_product_id": kain["id"],
        "output_product_id": kemeja["id"], "yield_factor": 1 / RCP["per_pcs_m"], "waste_pct": RCP["waste_pct"],
        "entity_id": ENT}, headers=adm, timeout=30)
    assert r.status_code == 200, r.text[:300]
    rid = r.json()["id"]
    DB.purchase_requisitions.insert_one({
        "id": "TEST_P05ACC_pr", "number": "TEST_P05ACC-PR", "status": "approved", "entity_id": ENT,
        "warehouse_id": "wh_jakarta", "items": [{"line_no": 1, "product_id": kemeja["id"], "quantity": RCP["target"],
                                                "unit": "pcs", "fulfillment_mode": "makloon"}]})
    yield {"recipe_id": rid, "kain": kain["id"], "mirip": mirip["id"], "kemeja": kemeja["id"]}
    DB.process_recipes.delete_one({"id": rid})
    DB.purchase_requisitions.delete_one({"id": "TEST_P05ACC_pr"})
    DB.products.delete_many({"id": {"$regex": "^TEST_P05ACC_"}})


@pytest.mark.usefixtures("recipe_fixture")
class TestACC33Recipe:
    def test_requirement_follows_recipe(self, adm, recipe_fixture):
        r = requests.get(f"{BASE}/api/purchase-requisitions/TEST_P05ACC_pr/makloon-prefill", params={"line_no": 1},
                         headers=adm, timeout=30)
        assert r.status_code == 200, r.text[:300]
        pre = r.json()
        assert pre["ready"] is True
        p = pre["payload"]
        # 100 kemeja × 1,6 m ÷ 95% = 168,42 m (dibulatkan ke atas → 168,43)
        assert p["material_qty"] == pytest.approx(168.43, abs=0.005)
        assert p["material_product_id"] == recipe_fixture["kain"] != recipe_fixture["mirip"]   # per ID, bukan nama mirip
        assert p["material_unit"] == "meter"
        S["need_m"] = p["material_qty"]

    def test_forecast_back_to_target(self, adm, recipe_fixture):
        r = requests.post(f"{BASE}/api/process-recipes/forecast",
                          json={"recipe_id": recipe_fixture["recipe_id"], "input_qty": S["need_m"]}, headers=adm, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["expected_output"] == pytest.approx(RCP["target"], abs=0.01)

    def test_roll_conversion_per_product(self, adm, recipe_fixture):
        url = f"{BASE}/api/uom-conversions/convert"
        r = requests.post(url, json={"product_id": recipe_fixture["kain"], "qty": S["need_m"],
                                     "from_unit": "meter", "to_unit": "roll"}, headers=adm, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["base_qty"] == pytest.approx(3.37, abs=0.005)            # 168,43 ÷ 50
        r = requests.post(url, json={"product_id": recipe_fixture["kain"], "qty": 4, "from_unit": "roll",
                                     "to_unit": "meter"}, headers=adm, timeout=30)
        assert r.status_code == 200 and r.json()["base_qty"] == pytest.approx(200)

    def test_unknown_conversion_not_guessed(self, adm, recipe_fixture):
        r = requests.post(f"{BASE}/api/uom-conversions/convert", json={
            "product_id": recipe_fixture["mirip"], "qty": 3, "from_unit": "roll", "to_unit": "meter"},
            headers=adm, timeout=30)
        assert r.status_code == 400, r.text[:300]


class TestACC31IdentityAndGrant:
    def test_identity_unchanged_and_history_kept(self, adm):
        prod = DB.products.find_one({"stage": "finished", "status": "active", "rnd_test_history.0": {"$exists": False}},
                                    {"_id": 0})
        keep = {k: prod.get(k) for k in ("sku", "name", "color_id", "color_code", "gramasi", "lebar", "spec_id")}
        r = requests.post(f"{BASE}/api/rnd/samples", json={
            "product_id": prod["id"], "sample_types": ["labdip"], "brief": "TEST_P05ACC ganti warna",
            "color_target": {"color_id": "col_kn_wht_01"}}, headers=adm, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["purpose"] == "revalidation"
        after = DB.products.find_one({"id": prod["id"]}, {"_id": 0})
        assert {k: after.get(k) for k in keep} == keep

    def test_line_grant_enforced(self):
        prod = DB.products.find_one({"stage": "finished", "status": "active", "line_code": {"$nin": ["", None]}},
                                    {"_id": 0, "id": 1, "line_code": 1})
        other = next(c for c in ("woven", "knit", "printing", "WOV", "KNT", "PRT") if c.lower() != str(prod["line_code"]).lower())
        u = DB.users.find_one({"email": "md@kainnusantara.id"}, {"_id": 0, "id": 1, "allowed_line_codes": 1})
        DB.users.update_one({"id": u["id"]}, {"$set": {"allowed_line_codes": [other]}})
        try:
            h = _login("md@kainnusantara.id")
            r = requests.post(f"{BASE}/api/rnd/samples", json={"product_id": prod["id"], "sample_types": ["handfeel"],
                                                               "brief": "TEST_P05ACC di luar lini"}, headers=h, timeout=30)
            assert r.status_code in (400, 403, 422), r.text[:300]
        finally:
            DB.users.update_one({"id": u["id"]}, {"$set": {"allowed_line_codes": u.get("allowed_line_codes")}})


class TestFinanceReconciliation:
    def test_entity_wip_equals_open_subcon(self, adm):
        """Saldo GL 1-1350 entitas = Σ nilai bahan MKO yang masih di mitra (issued, belum diterima)."""
        open_val = 0.0
        for m in DB.makloon_orders.find({"entity_id": ENT}, {"_id": 0, "steps": 1}):
            for s in m.get("steps") or []:
                if s.get("status") == "issued":
                    # L00/L01 — retur sebagian & susut di mitra mengurangi nilai yang masih terbuka
                    open_val += float(s.get("material_value_open", s.get("material_value")) or 0)
        bal = 0.0
        for j in DB.journal_entries.find({"status": "posted", "entity_id": ENT, "lines.account_code": WIP},
                                         {"_id": 0, "lines": 1}):
            for ln in j["lines"]:
                if ln.get("account_code") == WIP:
                    bal += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
        S["wip_bal"], S["wip_open"] = round(bal, 2), round(open_val, 2)
        assert abs(bal - open_val) <= 1, (bal, open_val)

    def test_inventory_gl_reconciled(self, adm):
        r = requests.get(f"{BASE}/api/gl/inventory-reconciliation", headers=adm, timeout=120)
        assert r.status_code == 200, r.text[:200]
        row = next(x for x in r.json()["rows"] if x["entity_id"] == ENT)
        S["inv_diff"] = row["difference"]
        assert abs(row["difference"]) <= r.json()["rounding_tolerance"], row
