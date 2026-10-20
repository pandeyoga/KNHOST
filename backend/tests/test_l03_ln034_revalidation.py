"""L03 LN-034 — uji ulang SKU existing per supplier, hasil teknis tanpa kontrak, keputusan PIC atas hasil gagal."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
SUP_A, SUP_B = [s["id"] for s in DB.suppliers.find({"entity_id": "all"}, {"_id": 0, "id": 1}).sort("name", 1).limit(2)]
TAG = uuid.uuid4().hex[:6]
PROD = DB.products.find_one({"stage": "finished", "status": "active", "sku": {"$nin": ["", None]}}, {"_id": 0, "id": 1, "sku": 1, "lifecycle": 1, "status": 1})
SPEC_TEST = f"spec_TEST_{TAG}"
SMP: list = []


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345"), "md": _login("md@kainnusantara.id"),
            "sales": _login("sales@kainnusantara.id")}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    before_contracts = DB.supplier_contracts.count_documents({})
    before_prod = DB.products.find_one({"id": PROD["id"]}, {"_id": 0, "lifecycle": 1, "status": 1, "sku": 1})
    yield
    assert DB.supplier_contracts.count_documents({}) == before_contracts   # T04/T05 — tidak ada kontrak lahir
    assert DB.products.find_one({"id": PROD["id"]}, {"_id": 0, "lifecycle": 1, "status": 1, "sku": 1}) == before_prod
    DB.md_samples.delete_many({"$or": [{"id": {"$in": SMP}}, {"title": {"$regex": f"TEST_{TAG}"}}]})
    DB.md_samples.delete_many({"product_id": PROD["id"], "revalidation.reason": {"$regex": TAG}})
    DB.md_specs.delete_many({"id": SPEC_TEST})
    DB.products.update_one({"id": PROD["id"]}, {"$pull": {"rnd_test_history": {"sample_id": {"$in": SMP}}}})


def _create(H, sup, types=("labdip",), who="admin", reason=None, **kw):
    body = {"product_id": PROD["id"], "sample_types": list(types), "title": f"TEST_{TAG}",
            "revalidation_supplier_id": sup, "revalidation_reason": reason or f"uji pemasok {TAG}", **kw}
    r = requests.post(f"{BASE}/rnd/samples", json=body, headers=H[who])
    if r.status_code in (200, 201):
        SMP.append(r.json()["id"])
    return r


def _assessed(sid, sup, result):
    DB.md_samples.update_one({"id": sid}, {"$set": {"status": "assessed", "rounds": [
        {"id": f"rnd_{uuid.uuid4().hex[:6]}", "round_no": 1, "supplier_id": sup, "type_code": "labdip", "result": result, "score": 1.5}]}})


def _decide(H, sid, result, note="", who="admin", **kw):
    return requests.post(f"{BASE}/rnd/samples/{sid}/decide", json={"result": result, "note": note, **kw}, headers=H[who])


def test_t02_t03_per_supplier_cycles_and_no_contract(H):
    r = _create(H, "")
    assert r.status_code == 400 and "supplier" in r.json()["detail"].lower()
    a1 = _create(H, SUP_A)
    assert a1.status_code in (200, 201), a1.text
    a1 = a1.json()
    assert a1["revalidation"]["cycle_no"] == 1 and a1["revalidation"]["reference"] is None
    # Supplier B berjalan terpisah walau jenis sama; supplier A sama → retry ditolak (tanpa duplikat).
    b1 = _create(H, SUP_B)
    assert b1.status_code in (200, 201), b1.text
    with ThreadPoolExecutor(3) as ex:
        dup = list(ex.map(lambda _: _create(H, SUP_A), range(3)))
    assert all(x.status_code == 400 for x in dup), [x.text for x in dup]
    # Kirim ke supplier lain dari siklus A ditolak.
    s = requests.post(f"{BASE}/rnd/samples/{a1['id']}/send", json={"supplier_ids": [SUP_B]}, headers=H["admin"])
    assert s.status_code == 400
    # A lulus tanpa harga/kontrak; hasil B tidak ikut lulus.
    _assessed(a1["id"], SUP_A, "acc")
    d = _decide(H, a1["id"], "pass", "warna sesuai")
    assert d.status_code == 200, d.text
    dec = d.json()["decision"]
    assert dec["result"] == "pass" and dec["price"] == 0 and dec["contract_created"] is False and not dec["contract_id"]
    el = requests.get(f"{BASE}/rnd/products/{PROD['id']}/supplier-eligibility", headers=H["admin"]).json()
    sa = next(x for x in el["suppliers"] if x["supplier_id"] == SUP_A)
    sb = next(x for x in el["suppliers"] if x["supplier_id"] == SUP_B)
    assert sa["eligible"] is True and sb["eligible"] is False and sb["open"] and sb["latest"] is None
    # T03 — A diuji ulang: siklus 2 mereferensi siklus 1; histori lama utuh.
    a2 = _create(H, SUP_A)
    assert a2.status_code in (200, 201), a2.text
    rv = a2.json()["revalidation"]
    assert rv["cycle_no"] == 2 and rv["reference"]["sample_id"] == a1["id"] and rv["reference"]["result"] == "pass"
    el = requests.get(f"{BASE}/rnd/products/{PROD['id']}/supplier-eligibility", headers=H["admin"]).json()
    sa = next(x for x in el["suppliers"] if x["supplier_id"] == SUP_A)
    assert sa["latest"]["sample_id"] == a1["id"] and [c["sample_id"] for c in sa["open"]] == [a2.json()["id"]]
    pytest.state = {"a2": a2.json()["id"], "b1": b1.json()["id"]}


def test_t06_t07_fail_waits_pic_then_retest(H):
    b1 = pytest.state["b1"]
    _assessed(b1, SUP_B, "tolak")
    assert _decide(H, b1, "pass").status_code == 400          # tanpa round ACC tidak bisa lulus
    assert _decide(H, b1, "fail", "x").status_code == 400     # alasan wajib
    r = _decide(H, b1, "fail", "delta E terlalu besar")
    assert r.status_code == 200 and r.json()["status"] == "pending_pic", r.text
    prod = DB.products.find_one({"id": PROD["id"]}, {"_id": 0, "lifecycle": 1, "status": 1})
    assert prod["status"] != "inactive"
    q = requests.get(f"{BASE}/rnd/revalidation/pic-queue", headers=H["admin"]).json()["items"]
    assert any(i["id"] == b1 for i in q)
    el = requests.get(f"{BASE}/rnd/products/{PROD['id']}/supplier-eligibility", headers=H["admin"]).json()
    sb = next(x for x in el["suppliers"] if x["supplier_id"] == SUP_B)
    assert sb["eligible"] is False and sb["latest"]["state"] == "fail_pending_pic"
    # Hasil gagal yang menunggu PIC tidak bisa dibatalkan (hasil tidak boleh hilang dari kelayakan).
    assert requests.post(f"{BASE}/rnd/samples/{b1}/cancel", json={"reason": "TEST batal"}, headers=H["admin"]).status_code == 400
    sup = requests.get(f"{BASE}/rnd/revalidation/partners", headers=H["admin"]).json()["items"]
    assert any(p["id"] == SUP_B for p in sup) and {p["partner_kind"] for p in sup} <= {"supplier", "makloon"}
    # Siklus baru supplier B diblok sampai PIC memutus; izin dicek backend.
    assert _create(H, SUP_B).status_code == 400
    assert requests.post(f"{BASE}/rnd/samples/{b1}/pic-decision", json={"action": "retest", "reason": "ulang"}, headers=H["sales"]).status_code == 403
    assert requests.post(f"{BASE}/rnd/samples/{b1}/pic-decision", json={"action": "override", "reason": "darurat produksi"}, headers=H["md"]).status_code == 403
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(lambda w: requests.post(f"{BASE}/rnd/samples/{b1}/pic-decision",
                                                  json={"action": "retest", "reason": "ganti batch benang"}, headers=H[w]), ["admin", "md"]))
    ok = [x for x in res if x.status_code == 200]
    assert len(ok) == 1, [x.text for x in res]
    retest = ok[0].json()["retest"]
    SMP.append(retest["id"])
    doc = DB.md_samples.find_one({"id": b1})
    assert doc["decision"]["result"] == "fail" and doc["pic_decision"]["result_unchanged"] == "fail"
    assert retest["revalidation"]["cycle_no"] == 2 and retest["revalidation"]["reference"]["sample_id"] == b1
    el = requests.get(f"{BASE}/rnd/products/{PROD['id']}/supplier-eligibility", headers=H["admin"]).json()
    sb = next(x for x in el["suppliers"] if x["supplier_id"] == SUP_B)
    assert sb["eligible"] is False and sb["latest"]["state"] == "fail_decided"


def test_override_keeps_fail_and_contract_ref_validated(H):
    a2 = pytest.state["a2"]
    _assessed(a2, SUP_A, "acc")
    other = DB.supplier_contracts.find_one({"partner_id": {"$nin": [SUP_A]}}, {"_id": 0, "id": 1})
    if other:
        assert _decide(H, a2, "pass", contract_id=other["id"]).status_code == 400
    _assessed(a2, SUP_A, "revisi")
    assert _decide(H, a2, "fail", "handfeel kasar").status_code == 200
    r = requests.post(f"{BASE}/rnd/samples/{a2}/pic-decision", json={"action": "override", "reason": "stok lama tetap jual",
                                                                    "scope": {"documents": ["PO-x"], "note": "hanya batch lama"}}, headers=H["admin"])
    assert r.status_code == 200, r.text
    d = DB.md_samples.find_one({"id": a2})
    assert d["decision"]["result"] == "fail" and d["decision"]["override"] is True and d["pic_decision"]["scope"]["documents"] == ["PO-x"]
    el = requests.get(f"{BASE}/rnd/products/{PROD['id']}/supplier-eligibility", headers=H["admin"]).json()
    sa = next(x for x in el["suppliers"] if x["supplier_id"] == SUP_A)
    assert sa["latest"]["state"] == "fail_override" and sa["eligible"] is False
    assert sa["previous"][0]["state"] == "pass"   # histori siklus terdahulu tetap utuh
    assert requests.get(f"{BASE}/rnd/products/{PROD['id']}/supplier-eligibility", headers=H["sales"]).status_code == 403


def test_t01_proofing_uses_existing_approved_artwork(H):
    src = DB.design_gallery.find_one({"id": {"$not": {"$regex": "^dsgn_TEST_"}}}, {"_id": 0})
    # AUD-RND-02 — versi 3 benar-benar ada & di-ACC (fixture lama mengklaim versi 3 tanpa riwayatnya)
    design = {**src, "id": f"dsgn_TEST_{TAG}", "code": f"T34-{TAG}", "status": "on_hold_test", "on_hold": True, "version": 3,
              "versions": [{"version": 1, "acc": True}, {"version": 2}, {"version": 3, "acc": True}], "approved_version": 3}
    DB.design_gallery.insert_one(dict(design))
    DB.md_specs.insert_one({"id": SPEC_TEST, "product_id": PROD["id"], "design_id": design["id"], "design_version": design.get("version") or 1,
                            "created_at": "2099-01-01T00:00:00", "status": "approved", "title": f"TEST_{TAG}"})
    assert _create(H, SUP_A, types=("proofing",), reason=f"proofing ulang {TAG}").status_code == 400   # artwork belum ACC/HOLD
    DB.design_gallery.update_one({"id": design["id"]}, {"$set": {"status": "approved", "on_hold": False}})
    n_designs = DB.design_gallery.count_documents({})
    r = _create(H, SUP_A, types=("proofing",), reason=f"proofing ulang {TAG}")
    assert r.status_code in (200, 201), r.text
    s = r.json()
    assert s["design_id"] == design["id"] and s["purpose"] == "revalidation" and s["product_id"] == PROD["id"]
    assert DB.design_gallery.count_documents({}) == n_designs and s["design_version"] == 3
    DB.design_gallery.delete_one({"id": design["id"]})
