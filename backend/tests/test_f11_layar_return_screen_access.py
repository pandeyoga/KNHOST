"""F-11-layar (uji pra-UAT 2026-10-21) — Gudang & QC membuka retur pelanggan dari layar.

Keputusan pemilik 2026-10-21 (opsi b, terbatas): pemegang `wms.scan`/`qc.inspect` TANPA
`sales_return.view` boleh membuka daftar, hitungan status, detail, timeline dan meta retur
yang sedang mereka kerjakan — daftar hanya status approved/inspecting, field uang dibuang.
Pemegang `sales_return.view` (Sales, Finance, …) tidak berubah; Desainer tetap 403.
"""
import os
import sys
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_api import DEMO_PASSWORD  # noqa: E402 — sandi akun peran seed (ikut perubahan F-01)

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = "TEST_F11_LAYAR"
SO = DB.sales_orders.find_one({"number": "KSC/SO-00001"})
JKT = "wh_jakarta"
RCM_QC = DB.warehouses.find_one({"name": {"$regex": "^Rancamalang · Gudang Retur"}})["id"]
OPERATORS = ("wh", "qc")
WORK_STATES = {"approved", "inspecting"}
# Kunci uang yang PASTI ada di dokumen/detail retur bila tidak dibuang (daftar tetap, bukan pola
# yang sama dengan penyaring di server — supaya tes tidak sekadar mengulang implementasinya).
MONEY_KEYS = {"estimated_value", "unit_price_est", "line_total_est", "order_grand_total", "compensation",
              "credit_note_number", "credit_note_amount", "logistics_costs", "value_basis"}
COMP_AMOUNT = 7777   # nilai kompensasi khas — tidak boleh muncul di mana pun pada respons Gudang/QC


def _login(email, pw=DEMO_PASSWORD):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def hs():
    before = {r["id"]: r for r in DB.inventory_rolls.find({"status": "delivered"})}
    out = {k: _login(e) for k, e in (("sales", "sales@kainnusantara.id"), ("mgr", "manager@kainnusantara.id"),
                                     ("wh", "warehouse@kainnusantara.id"), ("qc", "qc@kainnusantara.id"),
                                     ("whr", "warehouse.rancamalang@kainnusantara.id"),
                                     ("fin", "finance@kainnusantara.id"), ("des", "designer@kainnusantara.id"))}
    out["admin"] = _login("admin@kainnusantara.id", "demo12345")
    yield out
    ids = [d["id"] for d in DB.sales_returns.find({"notes": TAG}, {"id": 1})]
    for rid, doc in before.items():
        cur = DB.inventory_rolls.find_one({"id": rid}, {"return_history": 1, "status": 1})
        if cur and (cur.get("status") != "delivered" or any(x.get("return_id") in ids for x in cur.get("return_history") or [])):
            DB.inventory_rolls.replace_one({"id": rid}, doc)
    for coll in ("credit_notes", "journal_entries", "cash_transactions", "inventory_movements", "store_credit_ledger"):
        DB[coll].delete_many({"$or": [{"return_id": {"$in": ids}}, {"ref_id": {"$in": ids}}, {"source_id": {"$in": ids}}]})
    DB.sales_returns.delete_many({"notes": TAG})


@pytest.fixture(scope="module")
def pool(hs):
    """Roll utuh KSC/SO-00001 (data acuan); tiap tes memakai roll berbeda supaya klaim ≤ terkirim."""
    data = requests.get(f"{BASE}/sales-returns/returnable", headers=hs["admin"], params={"order_id": SO["id"]}).json()
    rolls = sorted((r for r in data["rolls"] if r["remaining"] >= r["shipped_qty"] - 0.01),
                   key=lambda r: (r["product_id"], r["roll_no"]))
    assert len(rolls) >= 5, "butuh ≥5 roll utuh di KSC/SO-00001 (data acuan)"
    return rolls


def _create(hs, roll, qty=None, approve=True):
    claim = qty if qty is not None else roll["remaining"]
    r = requests.post(f"{BASE}/sales-returns", headers=hs["sales"], json={
        "order_id": SO["id"], "return_type": "retur", "notes": TAG, "submit_now": True,
        "items": [{"product_id": roll["product_id"], "unit": roll["unit"], "reason": "cacat",
                   "quantity_returned": claim, "roll_ids": [roll["roll_id"]], "roll_qtys": {roll["roll_id"]: claim}}]})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    if approve:
        a = requests.post(f"{BASE}/sales-returns/{rid}/approve", headers=hs["mgr"], json={"notes": ""})
        assert a.status_code == 200, a.text
    return rid


def _keys(obj):
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _keys(v)}
    return set()


def _scan(h, rid, stage, codes, wh, to=""):
    return requests.post(f"{BASE}/sales-returns/{rid}/journey/scan", headers=h, json={
        "stage": stage, "codes": codes, "warehouse_id": wh, "to_warehouse_id": to, "carrier": "Sopir TEST"})


def test_operator_list_and_counts_only_receiving_and_qc(hs, pool):
    approved = _create(hs, pool[0], qty=5)
    pending = _create(hs, pool[1], qty=5, approve=False)
    for who in OPERATORS:
        r = requests.get(f"{BASE}/sales-returns", headers=hs[who])
        assert r.status_code == 200, f"{who}: {r.text}"
        items = r.json()["items"]
        assert {d["status"] for d in items} <= WORK_STATES, who
        ids = {d["id"] for d in items}
        assert approved in ids and pending not in ids, who
        assert not (_keys(items) & MONEY_KEYS), who
        p = requests.get(f"{BASE}/sales-returns", headers=hs[who], params={"page": 1, "page_size": 100})
        assert p.status_code == 200, p.text
        assert {d["status"] for d in p.json()["items"]} <= WORK_STATES and p.json()["total"] == len(items)
        r = requests.get(f"{BASE}/sales-returns", headers=hs[who], params={"status": "pending_approval"})
        assert r.status_code == 200 and r.json()["items"] == [], r.text
        c = requests.get(f"{BASE}/sales-returns/status-counts", headers=hs[who])
        assert c.status_code == 200, c.text
        counts = c.json()
        assert set(counts) - {"all"} <= WORK_STATES and counts["all"] == len(items), counts
    for who in ("fin", "sales"):                     # pemegang sales_return.view: tidak berubah
        items = requests.get(f"{BASE}/sales-returns", headers=hs[who]).json()["items"]
        assert pending in {d["id"] for d in items}, who
        assert "pending_approval" in requests.get(f"{BASE}/sales-returns/status-counts", headers=hs[who]).json()
    for path in ("/sales-returns", "/sales-returns/status-counts"):
        assert requests.get(f"{BASE}{path}", headers=hs["des"]).status_code == 403, path


def test_operator_detail_timeline_meta_without_money(hs, pool):
    roll = pool[2]
    rid = _create(hs, roll, qty=5)
    att = f"att_{rid}"   # fixture: bukti foto ditempel langsung (unggah berkas bukan objek uji ini)
    DB.sales_returns.update_one({"id": rid}, {"$push": {"attachments": {
        "id": att, "filename": "noda.jpg", "content_type": "image/jpeg", "is_deleted": False}}})
    d = requests.post(f"{BASE}/sales-returns/{rid}/compensation", headers=hs["fin"], json={
        "lines": [{"kind": "discount", "product_id": roll["product_id"], "qty": 5, "amount": COMP_AMOUNT,
                   "evidence_ids": [att]}], "note": "foto noda"})
    assert d.status_code == 200, d.text
    full = requests.get(f"{BASE}/sales-returns/{rid}", headers=hs["fin"]).json()   # Finance: utuh
    assert full["estimated_value"] > 0 and full["items"][0]["unit_price_est"] > 0
    assert full["compensation"]["lines"][0]["amount"] == COMP_AMOUNT
    assert requests.get(f"{BASE}/sales-returns/{rid}", headers=hs["sales"]).json()["estimated_value"] > 0
    for who in OPERATORS:
        r = requests.get(f"{BASE}/sales-returns/{rid}", headers=hs[who])
        assert r.status_code == 200, f"{who}: {r.text}"
        doc = r.json()
        assert not (_keys(doc) & MONEY_KEYS), (who, _keys(doc) & MONEY_KEYS)
        assert str(COMP_AMOUNT) not in r.text, who
        it = doc["items"][0]
        assert it["quantity_returned"] == 5 and it["roll_ids"] == [roll["roll_id"]] and it["product_id"] == roll["product_id"]
        assert doc["number"] and doc["status"] == "approved" and "evidence" in doc
        t = requests.get(f"{BASE}/sales-returns/{rid}/timeline", headers=hs[who])
        assert t.status_code == 200, t.text
        tl = t.json()
        assert "settlement" not in tl["lanes"] and all(e["lane"] != "settlement" for e in tl["events"])
        assert not (_keys(tl) & MONEY_KEYS) and tl["rolls"][0]["roll_id"] == roll["roll_id"]
        for meta in ("evidence-policy", "complaint-reasons"):
            m = requests.get(f"{BASE}/sales-returns/meta/{meta}", headers=hs[who])
            assert m.status_code == 200, f"{who} {meta}: {m.text}"
    for path in (f"/sales-returns/{rid}", f"/sales-returns/{rid}/timeline",
                 "/sales-returns/meta/evidence-policy", "/sales-returns/meta/complaint-reasons"):
        assert requests.get(f"{BASE}{path}", headers=hs["des"]).status_code == 403, path


def test_operator_cannot_open_returns_outside_receiving_qc(hs, pool):
    pending = _create(hs, pool[3], qty=3, approve=False)
    for who in OPERATORS:
        for path in (f"/sales-returns/{pending}", f"/sales-returns/{pending}/timeline"):
            r = requests.get(f"{BASE}{path}", headers=hs[who])
            assert r.status_code == 403, f"{who} {path}: {r.status_code} {r.text}"
    assert requests.get(f"{BASE}/sales-returns/{pending}", headers=hs["fin"]).status_code == 200


def test_operator_flow_scan_then_qc_from_screen_endpoints(hs, pool):
    roll = pool[4]
    rid = _create(hs, roll, qty=4)
    no = roll["roll_no"]
    assert rid in {d["id"] for d in requests.get(f"{BASE}/sales-returns", headers=hs["wh"]).json()["items"]}
    assert requests.get(f"{BASE}/sales-returns/{rid}", headers=hs["wh"]).status_code == 200
    assert _scan(hs["wh"], rid, "received", [no], JKT).status_code == 200            # Gudang Jakarta: TRM
    r = requests.post(f"{BASE}/sales-returns/{rid}/inspect/start", headers=hs["qc"], json={})
    assert r.status_code == 200, r.text                                               # QC mulai
    assert not (_keys(r.json()) & MONEY_KEYS)
    listed = {d["id"]: d["status"] for d in requests.get(f"{BASE}/sales-returns", headers=hs["qc"]).json()["items"]}
    assert listed.get(rid) == "inspecting"
    assert _scan(hs["wh"], rid, "dispatched", [no], JKT, RCM_QC).status_code == 200  # SJ ke area QC
    assert requests.get(f"{BASE}/sales-returns/{rid}", headers=hs["whr"]).status_code == 200
    assert _scan(hs["whr"], rid, "arrived", [no], RCM_QC).status_code == 200         # Rancamalang: TBA
    r = requests.post(f"{BASE}/sales-returns/{rid}/inspect/complete", headers=hs["qc"],
                      json={"inspections": [{"index": 0, "grade": "A", "condition": "ok"}]})
    assert r.status_code == 200, r.text                                               # QC selesai
    assert r.json()["status"] == "inspected" and not (_keys(r.json()) & MONEY_KEYS)
    d = requests.get(f"{BASE}/sales-returns/{rid}", headers=hs["qc"])                 # hasil QC tetap terbaca
    assert d.status_code == 200 and d.json()["status"] == "inspected", d.text
    assert requests.get(f"{BASE}/sales-returns/{rid}/timeline", headers=hs["qc"]).status_code == 200
    ids = {x["id"] for x in requests.get(f"{BASE}/sales-returns", headers=hs["qc"]).json()["items"]}
    assert rid not in ids                                                             # daftar: approved/inspecting saja
    assert DB.sales_returns.find_one({"id": rid})["status"] == "inspected"
