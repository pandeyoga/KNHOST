"""L00 — reproduksi & perbaikan open issue P05: (1) uji ulang SKU paralel atomik,
(3) retur bahan makloon sebagian per roll dengan pembalikan WIP pro-rata.
Data uji berlabel TEST_L00; pulihkan data acuan: bash /app/scripts/restore_local_demo.sh
"""
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

from tests.test_p05_acceptance_acc31_33_34 import BASE, DB, _create, _free, _login, _tpl, _wip


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module", autouse=True)
def output_is_makloon():
    out = DB.products.find_one({"id": _tpl()["steps"][0]["output_product_id"]}, {"_id": 0, "template_id": 1})
    tpl = DB.product_templates.find_one({"id": out["template_id"]}, {"_id": 0, "id": 1, "restock_source": 1})
    before = tpl.get("restock_source")
    DB.product_templates.update_one({"id": tpl["id"]}, {"$set": {"restock_source": {"mode": "makloon", "note": "TEST_L00"}}})
    yield
    DB.md_samples.delete_many({"brief": {"$regex": "^TEST_L00"}})
    if before:
        DB.product_templates.update_one({"id": tpl["id"]}, {"$set": {"restock_source": before}})
    else:
        DB.product_templates.update_one({"id": tpl["id"]}, {"$unset": {"restock_source": ""}})


def _open_reval_product():
    busy = {d.get("product_id") for d in DB.md_samples.find(
        {"purpose": "revalidation", "status": {"$nin": ["decided", "cancelled"]}}, {"_id": 0, "product_id": 1})}
    for p in DB.products.find({"status": {"$in": ["active", None]}}, {"_id": 0, "id": 1}).limit(200):
        if p["id"] not in busy:
            return p["id"]
    pytest.skip("tidak ada SKU aktif tanpa uji ulang terbuka")


class TestRevalidationRace:
    def test_parallel_requests_only_one_created(self, adm):
        pid = _open_reval_product()
        body = {"product_id": pid, "sample_types": ["handfeel"], "brief": "TEST_L00 paralel"}
        with ThreadPoolExecutor(max_workers=6) as ex:
            codes = list(ex.map(lambda _: requests.post(f"{BASE}/api/rnd/samples", json=body, headers=adm,
                                                        timeout=60).status_code, range(6)))
        assert codes.count(200) == 1, codes
        assert DB.md_samples.count_documents({"product_id": pid, "purpose": "revalidation",
                                              "brief": "TEST_L00 paralel"}) == 1

    def test_cancel_frees_slot(self, adm):
        smp = DB.md_samples.find_one({"brief": "TEST_L00 paralel"}, {"_id": 0, "id": 1, "product_id": 1})
        r = requests.post(f"{BASE}/api/rnd/samples/{smp['id']}/cancel", json={"reason": "TEST_L00 batal uji"},
                          headers=adm, timeout=30)
        assert r.status_code == 200, r.text[:300]
        r = requests.post(f"{BASE}/api/rnd/samples", json={"product_id": smp["product_id"], "sample_types": ["handfeel"],
                                                           "brief": "TEST_L00 ulang"}, headers=adm, timeout=30)
        assert r.status_code == 200, r.text[:300]


class TestPartialMaterialReturn:
    S = {}

    def test_cancel_after_issue(self, adm):
        t = _tpl()
        self.S.update(pid=t["material_product_id"], wh=t["from_warehouse_id"])
        mko = _create(adm, 30, "TEST_L00 retur sebagian")
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue", json={"step_seq": 1}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        self.S.update(mko=mko, value=float(r.json()["steps"][0]["material_value"]))
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_L00 batal"},
                          headers=adm, timeout=60)
        assert r.status_code == 200

    def test_partner_rolls_and_partial_return(self, adm):
        mko = self.S["mko"]
        d = requests.get(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/partner-rolls", headers=adm, timeout=30).json()
        rolls = d["rolls"]
        if len(rolls) < 2:
            pytest.skip("butuh ≥2 roll di mitra untuk uji retur sebagian")
        first = rolls[0]
        free0 = _free(self.S["pid"], self.S["wh"])
        url = f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/return-material"
        r = requests.post(url, json={"reason": "TEST_L00 SJ retur 1", "roll_ids": [first["id"]]}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        st = r.json()["steps"][0]
        q = float(first["length_remaining"])
        assert st["status"] == "issued" and st["awaiting_return"] is True and r.json()["material_at_partner"] is True
        assert _free(self.S["pid"], self.S["wh"]) == pytest.approx(free0 + q, abs=0.05)
        assert _wip(mko["mko_number"]) == pytest.approx(self.S["value"] * (1 - q / 30), abs=1)
        # roll yang sama tidak bisa dikembalikan dua kali
        r = requests.post(url, json={"reason": "TEST_L00 SJ retur ulang", "roll_ids": [first["id"]]}, headers=adm, timeout=30)
        assert r.status_code == 409

    def test_return_rest_closes_step_and_wip_zero(self, adm):
        mko = self.S["mko"]
        url = f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/return-material"
        r = requests.post(url, json={"reason": "TEST_L00 SJ retur sisa"}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        st = r.json()["steps"][0]
        assert st["status"] == "returned" and r.json()["material_at_partner"] is False
        assert st["returned_qty"] == pytest.approx(30, abs=0.05)
        assert _wip(mko["mko_number"]) == pytest.approx(0, abs=1)
        assert requests.post(url, json={"reason": "TEST_L00 ulang lagi"}, headers=adm, timeout=30).status_code == 409
