"""F-11/F-12 (uji pra-UAT 2026-10-21) — perjalanan & QC retur oleh peran yang mengerjakannya.

F-11: Gudang menscan terima/kirim/tiba (`wms.scan`), QC memulai & menyelesaikan inspeksi
(`qc.inspect`); peran lain tetap 403 dan pagar gudang per badan usaha tetap berlaku.
F-12: QC tidak boleh mendahului barang — tanpa scan = belum diterima (bukan pengecualian);
sebagian roll belum diterima/masih di jalan → 400; jalur diskon foto/video (KLR-06) tetap jalan.
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
TAG = "TEST_F1112"
SO = DB.sales_orders.find_one({"number": "KSC/SO-00001"})
JKT = "wh_jakarta"
RCM_QC = DB.warehouses.find_one({"name": {"$regex": "^Rancamalang · Gudang Retur"}})["id"]
# gudang khusus badan usaha lain (bukan KSC) — pagar gudang harus tetap menolak
OTHER_WH = DB.warehouses.find_one({"active": True, "sharing_mode": "dedicated",
                                   "entity_ids": {"$nin": ["ent_ksc"]}})["id"]


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
    """Roll utuh KSC/SO-00001 per produk, dibagi antar tes supaya klaim kumulatif ≤ terkirim."""
    data = requests.get(f"{BASE}/sales-returns/returnable", headers=hs["admin"], params={"order_id": SO["id"]}).json()
    by: dict = {}
    for r in data["rolls"]:
        if r["remaining"] >= r["shipped_qty"] - 0.01:
            by.setdefault(r["product_id"], []).append(r)
    groups = sorted((g for g in by.values() if len(g) >= 3), key=lambda g: g[0]["product_id"])
    assert len(groups) >= 2, "butuh dua produk dengan ≥3 roll utuh di KSC/SO-00001 (data acuan)"
    return {"A": groups[0], "B": groups[1]}


def _approved(hs, rolls=None, rollless=None, qty=None):
    """Sales mengajukan, Manajer menyetujui — status `approved`, belum ada scan.
    `qty` = klaim sebagian satu roll (selain itu tiap roll diklaim penuh)."""
    if rolls:
        claims = {r["roll_id"]: (qty if qty is not None else r["remaining"]) for r in rolls}
        item = {"product_id": rolls[0]["product_id"], "unit": rolls[0]["unit"], "reason": "cacat",
                "quantity_returned": round(sum(claims.values()), 2),
                "roll_ids": list(claims), "roll_qtys": claims}
    else:
        item = {"product_id": rollless["product_id"], "unit": rollless["unit"], "reason": "cacat",
                "quantity_returned": 10}
    r = requests.post(f"{BASE}/sales-returns", headers=hs["sales"], json={
        "order_id": SO["id"], "return_type": "retur", "notes": TAG, "submit_now": True, "items": [item]})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    a = requests.post(f"{BASE}/sales-returns/{rid}/approve", headers=hs["mgr"], json={"notes": ""})
    assert a.status_code == 200, a.text
    return rid


def _scan(h, rid, stage, codes, wh, to=""):
    return requests.post(f"{BASE}/sales-returns/{rid}/journey/scan", headers=h, json={
        "stage": stage, "codes": codes, "warehouse_id": wh, "to_warehouse_id": to, "carrier": "Sopir TEST"})


def _start(h, rid):
    return requests.post(f"{BASE}/sales-returns/{rid}/inspect/start", headers=h, json={})


def _complete(h, rid):
    return requests.post(f"{BASE}/sales-returns/{rid}/inspect/complete", headers=h,
                         json={"inspections": [{"index": 0, "grade": "A", "condition": "ok"}]})


def test_f11_warehouse_scans_qc_inspects_others_forbidden(hs, pool):
    roll = pool["A"][0]
    rid = _approved(hs, [roll])
    no = roll["roll_no"]
    for who in ("fin", "des"):                                            # peran lain tetap 403
        assert _scan(hs[who], rid, "received", [no], JKT).status_code == 403
    assert _scan(hs["wh"], rid, "received", [no], OTHER_WH).status_code == 403   # pagar gudang tetap
    r = _scan(hs["wh"], rid, "received", [no], JKT)
    assert r.status_code == 200, r.text                                   # Gudang: TRM
    assert r.json()["event"]["doc_no"].endswith("/TRM-1")
    for who in ("fin", "des"):
        assert _start(hs[who], rid).status_code == 403
    r = _start(hs["qc"], rid)
    assert r.status_code == 200, r.text                                   # QC mulai
    assert r.json()["status"] == "inspecting"
    r = _scan(hs["wh"], rid, "dispatched", [no], JKT, RCM_QC)
    assert r.status_code == 200, r.text                                   # Gudang Jakarta: SJ ke area QC
    r = _scan(hs["whr"], rid, "arrived", [no], RCM_QC)
    assert r.status_code == 200, r.text                                   # Gudang Rancamalang: TBA
    for who in ("fin", "des"):
        assert _complete(hs[who], rid).status_code == 403
    r = _complete(hs["qc"], rid)
    assert r.status_code == 200, r.text                                   # QC selesai
    doc = DB.sales_returns.find_one({"id": rid})
    assert doc["status"] == "inspected" and doc["inspected_by"]
    assert [e["doc_no"].split("/")[-1] for e in doc["journey_events"]] == ["TRM-1", "SJ-1", "TBA-1"]


# Tes F-12 memakai Admin (pemegang `sales_return.update`) supaya gerbang penerimaan diuji lepas
# dari izin peran F-11 — tanpa scan tetap ditolak untuk siapa pun.
def test_f12_qc_without_any_scan_rejected(hs, pool):
    rid = _approved(hs, [pool["A"][1]], qty=5)
    r = _start(hs["admin"], rid)
    assert r.status_code == 400, r.text
    assert "Scan terima barang retur dulu" in r.json()["detail"]
    assert DB.sales_returns.find_one({"id": rid})["status"] == "approved"


def test_f12_complete_on_unscanned_inspecting_return_rejected(hs, pool):
    """Bentuk data SRET-00007/SRET-00020: QC sudah dimulai tanpa scan sebelum perbaikan."""
    rid = _approved(hs, [pool["A"][2]], qty=5)
    DB.sales_returns.update_one({"id": rid}, {"$set": {"status": "inspecting", "inspection_status": "in_progress"}})
    r = _complete(hs["admin"], rid)
    assert r.status_code == 400 and "Scan terima barang retur dulu" in r.json()["detail"], r.text
    assert DB.sales_returns.find_one({"id": rid})["status"] == "inspecting"


def test_f12_partial_receipt_and_in_transit_rejected_then_all_arrived_ok(hs, pool):
    rolls = pool["B"][:2]
    rid = _approved(hs, rolls)
    a, b, h = rolls[0]["roll_no"], rolls[1]["roll_no"], hs["admin"]
    assert _scan(h, rid, "received", [a], JKT).status_code == 200
    r = _start(h, rid)
    assert r.status_code == 400 and "1 dari 2 roll" in r.json()["detail"], r.text      # sebagian belum diterima
    assert _scan(h, rid, "received", [b], JKT).status_code == 200
    assert _scan(h, rid, "dispatched", [b], JKT, RCM_QC).status_code == 200
    r = _start(h, rid)
    assert r.status_code == 400 and "perjalanan" in r.json()["detail"], r.text           # sebagian in_transit
    assert _scan(h, rid, "arrived", [b], RCM_QC).status_code == 200
    r = _start(h, rid)
    assert r.status_code == 200, r.text                                                  # semua di gudang
    r = _complete(h, rid)
    assert r.status_code == 200, r.text
    assert DB.sales_returns.find_one({"id": rid})["status"] == "inspected"


def test_f12_rollless_line_needs_goods_arrived(hs, pool):
    rid, h = _approved(hs, rollless=pool["B"][2]), hs["admin"]
    r = _start(h, rid)
    assert r.status_code == 400 and "tanpa roll" in r.json()["detail"], r.text
    for m in ("shipped_to_store", "goods_arrived"):
        x = requests.post(f"{BASE}/sales-returns/{rid}/milestone", headers=h, json={"milestone": m})
        assert x.status_code == 200, x.text
    r = _start(h, rid)
    assert r.status_code == 200, r.text
    r = _complete(h, rid)
    assert r.status_code == 200, r.text


def test_f12_photo_discount_without_goods_still_settles(hs, pool):
    """KLR-06 — diskon diputus dari foto/video (nilai oleh Finance), tanpa QC fisik & tanpa scan."""
    roll = pool["B"][2]
    rid = _approved(hs, [roll], qty=5)
    att = f"att_{rid}"   # fixture: bukti foto ditempel langsung (unggah berkas bukan objek uji ini)
    DB.sales_returns.update_one({"id": rid}, {"$push": {"attachments": {
        "id": att, "filename": "noda.jpg", "content_type": "image/jpeg", "is_deleted": False}}})
    d = requests.post(f"{BASE}/sales-returns/{rid}/compensation", headers=hs["fin"], json={
        "lines": [{"kind": "discount", "product_id": roll["product_id"], "qty": 5, "amount": 7500,
                   "evidence_ids": [att]}], "note": "foto noda 5 yd"})
    assert d.status_code == 200, d.text
    s = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=hs["admin"],
                      json={"outcome": "nego", "decision_note": "diskon dari foto, ACC Finance"})
    assert s.status_code == 200, s.text
    doc = DB.sales_returns.find_one({"id": rid})
    assert doc["status"] == "nego_settled" and not doc.get("journey_events")
