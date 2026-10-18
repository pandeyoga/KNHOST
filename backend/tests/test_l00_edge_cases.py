"""L00 edge cases (testing agent): reval 5-paralel, validasi retur bahan, retur sebagian paralel.
Run in its own pytest invocation: python -m pytest tests/test_l00_edge_cases.py -n0 -q
"""
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

from tests.test_p05_acceptance_acc31_33_34 import BASE, DB, REVAL, _create, _login, _tpl, _wip
from tests.test_l00_p05_open_issues import _open_reval_product, output_is_makloon  # noqa: F401


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


# Revalidation: 5 parallel → exactly one 200, others 400; cancel frees slot
class TestRevalFive:
    def test_five_parallel(self, adm):
        pid = _open_reval_product()
        body = {"product_id": pid, "sample_types": ["handfeel"], "brief": "TEST_L00x paralel5", **REVAL}
        with ThreadPoolExecutor(max_workers=5) as ex:
            res = list(ex.map(lambda _: requests.post(f"{BASE}/api/rnd/samples", json=body, headers=adm, timeout=60),
                              range(5)))
        codes = [r.status_code for r in res]
        assert codes.count(200) == 1, codes
        assert all(c == 400 for c in codes if c != 200), codes
        ok = next(r for r in res if r.status_code == 200).json()
        assert ok["purpose"] == "revalidation"
        # different type for same SKU is allowed (key = sku:type)
        r = requests.post(f"{BASE}/api/rnd/samples", json={**body, "sample_types": ["labdip"],
                                                           "brief": "TEST_L00x labdip"}, headers=adm, timeout=30)
        print("labdip same sku:", r.status_code, r.text[:200])
        r = requests.post(f"{BASE}/api/rnd/samples/{ok['id']}/cancel", json={"reason": "TEST_L00x batal"},
                          headers=adm, timeout=30)
        assert r.status_code == 200
        doc = DB.md_samples.find_one({"id": ok["id"]}, {"_id": 0})
        assert "open_reval_keys" not in doc
        r = requests.post(f"{BASE}/api/rnd/samples", json=body, headers=adm, timeout=30)
        assert r.status_code == 200, r.text[:200]

    def test_index_exists(self):
        names = [i["name"] for i in DB.md_samples.list_indexes()]
        assert "uniq_open_revalidation" in names


# Makloon return-material validation + concurrent partial returns
class TestReturnEdges:
    S = {}

    def test_setup(self, adm):
        mko = _create(adm, 30, "TEST_L00x edge")
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue", json={"step_seq": 1}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        self.S.update(mko=mko, value=float(r.json()["steps"][0]["material_value"]))
        url = f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/return-material"
        # before cancel → 409
        r = requests.post(url, json={"reason": "TEST_L00x belum batal"}, headers=adm, timeout=30)
        assert r.status_code == 409, r.text[:200]
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_L00x batal"},
                          headers=adm, timeout=60)
        assert r.status_code == 200

    def test_validation(self, adm):
        mko = self.S["mko"]
        url = f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/return-material"
        r = requests.post(url, json={"reason": "abc"}, headers=adm, timeout=30)
        assert r.status_code in (400, 422), r.status_code
        r = requests.post(url, json={"reason": "TEST_L00x kosong", "roll_ids": []}, headers=adm, timeout=30)
        assert r.status_code == 400, r.text[:200]
        r = requests.post(url, json={"reason": "TEST_L00x asing", "roll_ids": ["roll_tidak_ada"]}, headers=adm, timeout=30)
        assert r.status_code == 409, r.text[:200]
        r = requests.get(f"{BASE}/api/makloon-orders/{mko['id']}/steps/9/partner-rolls", headers=adm, timeout=30)
        print("bad seq partner-rolls:", r.status_code)
        assert r.status_code in (400, 404)

    def test_parallel_partial_returns(self, adm):
        mko = self.S["mko"]
        rolls = requests.get(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/partner-rolls", headers=adm,
                             timeout=30).json()["rolls"]
        if len(rolls) < 2:
            pytest.skip("need >=2 rolls")
        url = f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/return-material"
        half = len(rolls) // 2
        groups = [[r["id"] for r in rolls[:half]], [r["id"] for r in rolls[half:]]]
        with ThreadPoolExecutor(max_workers=2) as ex:
            res = list(ex.map(lambda g: requests.post(url, json={"reason": "TEST_L00x paralel", "roll_ids": g},
                                                      headers=adm, timeout=60), groups))
        print("parallel codes:", [r.status_code for r in res])
        o = DB.makloon_orders.find_one({"id": mko["id"]}, {"_id": 0})
        st = o["steps"][0]
        n_hist = len(st.get("material_returns") or [])
        wip = _wip(mko["mko_number"])
        print("history entries:", n_hist, "status:", st["status"], "returned_qty:", st.get("returned_qty"),
              "wip:", wip, "value:", self.S["value"])
        codes = sorted(r.status_code for r in res)
        assert codes in ([200, 200], [200, 409]), codes          # kalah balapan → 409, bukan tulis basi
        assert sum(float(r.get("value") or 0) for r in st["material_returns"]) == pytest.approx(
            self.S["value"] - wip, abs=1)                          # riwayat == WIP yang benar-benar dibalik
        if codes == [200, 409]:
            r = requests.post(url, json={"reason": "TEST_L00x sisa"}, headers=adm, timeout=60)
            assert r.status_code == 200, r.text[:200]
            st = DB.makloon_orders.find_one({"id": mko["id"]}, {"_id": 0})["steps"][0]
            n_hist, wip = len(st["material_returns"]), _wip(mko["mko_number"])
        assert DB.inventory_rolls.count_documents({"bucket_ref.id": st["issue_ref"]}) == 0
        assert wip == pytest.approx(0, abs=1), f"WIP not zero after full return: {wip}"
        assert n_hist == 2, f"lost history entry under concurrency: {n_hist}"
        assert st["status"] == "returned"
