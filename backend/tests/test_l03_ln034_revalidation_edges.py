"""L03 LN-034 edge cases — validasi input uji ulang, keputusan PIC operational_note, izin, partners & eligibility kosong."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
SUPS = [s["id"] for s in DB.suppliers.find({"entity_id": "all"}, {"_id": 0, "id": 1}).sort("name", -1).limit(2)]
TAG = uuid.uuid4().hex[:6]
PRODS = list(DB.products.find({"stage": "finished", "status": "active", "sku": {"$nin": ["", None]}},
                              {"_id": 0, "id": 1, "sku": 1}).skip(5).limit(2))
PROD = PRODS[0]
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
    n_contracts = DB.supplier_contracts.count_documents({})
    yield
    assert DB.supplier_contracts.count_documents({}) == n_contracts
    DB.md_samples.delete_many({"$or": [{"id": {"$in": SMP}}, {"title": {"$regex": f"TEST_{TAG}"}},
                                       {"revalidation.reason": {"$regex": TAG}}]})
    DB.products.update_many({}, {"$pull": {"rnd_test_history": {"sample_id": {"$in": SMP}}}})


def _create(H, sup, reason=None, who="admin", pid=None):
    body = {"product_id": pid or PROD["id"], "sample_types": ["labdip"], "title": f"TEST_{TAG}",
            "revalidation_supplier_id": sup, "revalidation_reason": f"edge {TAG}" if reason is None else reason}
    r = requests.post(f"{BASE}/rnd/samples", json=body, headers=H[who])
    if r.status_code in (200, 201):
        SMP.append(r.json()["id"])
    return r


def _assessed(sid, sup, result):
    DB.md_samples.update_one({"id": sid}, {"$set": {"status": "assessed", "rounds": [
        {"id": f"rnd_{uuid.uuid4().hex[:6]}", "round_no": 1, "supplier_id": sup, "type_code": "labdip", "result": result, "score": 1.5}]}})


def _post(H, path, body, who="admin"):
    return requests.post(f"{BASE}{path}", json=body, headers=H[who])


# Validasi pembuatan siklus
def test_create_validation(H):
    assert _create(H, SUPS[0], reason="ab").status_code == 400
    assert _create(H, "sup_tidak_ada_xyz").status_code == 400


# Partners & eligibility
def test_partners_and_empty_eligibility(H):
    r = requests.get(f"{BASE}/rnd/revalidation/partners", headers=H["admin"])
    assert r.status_code == 200
    items = r.json()["items"]
    assert items and all({"id", "name", "code", "partner_kind"} <= set(i) for i in items)
    r = requests.get(f"{BASE}/rnd/revalidation/partners", params={"q": "zzzz_tidak_ada"}, headers=H["admin"])
    assert r.status_code == 200 and r.json()["items"] == []
    el = requests.get(f"{BASE}/rnd/products/{PRODS[1]['id']}/supplier-eligibility", headers=H["admin"])
    assert el.status_code == 200 and isinstance(el.json()["suppliers"], list)


# Decide guards + operational_note oleh md
def test_decide_guards_and_operational_note(H):
    r = _create(H, SUPS[0])
    assert r.status_code in (200, 201), r.text
    sid = r.json()["id"]
    # draft tanpa round → tidak bisa diputus
    assert _post(H, f"/rnd/samples/{sid}/decide", {"result": "fail", "note": "temuan awal"}).status_code == 400
    _assessed(sid, SUPS[0], "tolak")
    assert _post(H, f"/rnd/samples/{sid}/decide", {"result": "maybe", "note": "xxxxx"}).status_code == 400
    assert _post(H, f"/rnd/samples/{sid}/decide", {"result": "fail", "note": "xxxxx", "supplier_id": SUPS[1]}).status_code == 400
    # PIC sebelum gagal → 400
    assert _post(H, f"/rnd/samples/{sid}/pic-decision", {"action": "retest", "reason": "ulang dulu"}).status_code == 400
    d = _post(H, f"/rnd/samples/{sid}/decide", {"result": "fail", "note": "warna belang"}, who="md")  # keputusan owner: md cukup rnd.decide
    assert d.status_code == 200 and d.json()["status"] == "pending_pic" and d.json()["decision"]["price"] == 0, d.text
    assert _post(H, f"/rnd/samples/{sid}/pic-decision", {"action": "hapus", "reason": "alasan cukup"}).status_code == 400
    assert _post(H, f"/rnd/samples/{sid}/pic-decision", {"action": "operational_note", "reason": "abc"}).status_code == 400
    r = _post(H, f"/rnd/samples/{sid}/pic-decision", {"action": "operational_note", "reason": "pakai untuk stok lama",
                                                      "scope": {"documents": ["PO-1", "MKO-2"], "note": "batch lama"}}, who="md")
    assert r.status_code == 200, r.text
    assert r.json()["retest"] is None
    doc = DB.md_samples.find_one({"id": sid}, {"_id": 0})
    assert doc["status"] == "decided" and doc["decision"]["result"] == "fail" and doc["decision"]["override"] is False
    assert doc["pic_decision"]["scope"]["documents"] == ["PO-1", "MKO-2"]
    # Sudah diputus → keputusan PIC kedua ditolak
    assert _post(H, f"/rnd/samples/{sid}/pic-decision", {"action": "retest", "reason": "ulang lagi"}).status_code == 400
    el = requests.get(f"{BASE}/rnd/products/{PROD['id']}/supplier-eligibility", headers=H["admin"]).json()
    g = next(x for x in el["suppliers"] if x["supplier_id"] == SUPS[0])
    assert g["latest"]["state"] == "fail_decided" and g["eligible"] is False
    # Setelah PIC memutus, siklus baru supplier sama boleh dibuat (cycle 2, referensi ke gagal)
    n = _create(H, SUPS[0])
    assert n.status_code in (200, 201), n.text
    assert n.json()["revalidation"]["cycle_no"] == 2 and n.json()["revalidation"]["reference"]["result"] == "fail"
    q = requests.get(f"{BASE}/rnd/revalidation/pic-queue", headers=H["admin"]).json()["items"]
    assert not any(i["id"] == sid for i in q)


# Izin sales
def test_sales_permissions(H):
    assert requests.get(f"{BASE}/rnd/revalidation/pic-queue", headers=H["sales"]).status_code == 403


# Referensi kontrak existing: opsi tervalidasi, kontrak tidak berubah
def test_contract_reference_options(H):
    cid = f"sct_TEST_{TAG}"
    ct = {"id": cid, "contract_number": f"TEST/SCT-{TAG}", "partner_id": SUPS[1], "product_id": PRODS[1]["id"], "entity_id": ENT,
          "contract_type": "purchase", "status": "active", "unit_price": 12345, "created_at": "2099-01-01T00:00:00"}
    other = {**ct, "id": cid + "_x", "contract_number": f"TEST/SCT-{TAG}-X", "product_id": PRODS[0]["id"]}
    # AUD-RND-03 — keputusan owner 2026-10-21: kontrak DIHENTIKAN boleh jadi referensi historis
    term = {**ct, "id": cid + "_t", "contract_number": f"TEST/SCT-{TAG}-T", "status": "terminated"}
    # keputusan owner 2026-10-21 (lanjutan): kedaluwarsa & batal juga boleh jadi referensi
    exp = {**ct, "id": cid + "_e", "contract_number": f"TEST/SCT-{TAG}-E", "status": "expired"}
    can = {**ct, "id": cid + "_c", "contract_number": f"TEST/SCT-{TAG}-C", "status": "cancelled"}
    DB.supplier_contracts.insert_many([dict(ct), dict(other), dict(term), dict(exp), dict(can)])
    try:
        r = _create(H, SUPS[1], pid=PRODS[1]["id"])
        assert r.status_code in (200, 201), r.text
        sid = r.json()["id"]
        opts = requests.get(f"{BASE}/rnd/samples/{sid}/contract-options", headers=H["md"])
        assert opts.status_code == 200, opts.text
        ids = [c["id"] for c in opts.json()["items"]]
        assert cid in ids and other["id"] not in ids
        assert term["id"] in ids, "kontrak dihentikan harus tampil sebagai pilihan referensi"
        st = {c["id"]: c["status"] for c in opts.json()["items"]}
        assert st[term["id"]] == "terminated" and st[exp["id"]] == "expired" and st[can["id"]] == "cancelled"
        assert requests.get(f"{BASE}/rnd/samples/{sid}/contract-options", headers=H["sales"]).status_code == 403
        _assessed(sid, SUPS[1], "acc")
        assert _post(H, f"/rnd/samples/{sid}/decide", {"result": "pass", "contract_id": other["id"]}, who="md").status_code == 400
        d = _post(H, f"/rnd/samples/{sid}/decide", {"result": "pass", "note": "ok", "contract_id": cid}, who="md")
        assert d.status_code == 200, d.text
        dec = d.json()["decision"]
        assert dec["contract_id"] == cid and dec["contract_created"] is False and dec["price"] == 0
        after = DB.supplier_contracts.find_one({"id": cid}, {"_id": 0})
        assert after == ct
    finally:
        DB.supplier_contracts.delete_many({"id": {"$in": [cid, other["id"], term["id"], exp["id"], can["id"]]}})
