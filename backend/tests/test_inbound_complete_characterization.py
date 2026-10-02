"""GRN Fase 1 — TEST KARAKTERISASI `POST /api/inbound/tasks/{id}/complete`.

Mengunci perilaku SEKARANG (sebelum refactor ke `services/inbound_complete_service.py`) untuk dua jalur:
  A. roll hasil scan label (body `{}`)            B. rincian roll manual (`rolls`)
Yang dibandingkan: roll yang lahir, `received_qty` & status PO, jurnal GL, lot, status tugas.
Semua koleksi yang disentuh di-snapshot lalu dipulihkan EKSAK (nol residu).
"""
import os
import sys
import uuid

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

# Pemulihan TERARAH (aman bila modul uji lain berjalan paralel di worker xdist lain):
# dokumen yang LAHIR selama uji dibuang; tugas & PO yang dipakai dipulihkan per id;
# hanya saldo (proyeksi roll) & nomor urut yang dipulihkan satu koleksi penuh.
NEW_COLLS = ["inventory_rolls", "inventory_movements", "inventory_lots", "journal_entries", "inspections",
             "notifications", "audit_logs", "rfid_tags", "doc_refs", "backorders", "qc_inspections"]
FULL_COLLS = ["inventory_balances", "number_sequences"]


def _base():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        for ln in open("/app/frontend/.env"):
            if ln.startswith("REACT_APP_BACKEND_URL="):
                url = ln.split("=", 1)[1].strip()
    return url.rstrip("/") + "/api"


BASE = _base()


@pytest.fixture(scope="module")
def mdb():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def wh():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": "warehouse@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"})
    return s


@pytest.fixture()
def restore(mdb):
    full = snapshot_stock(FULL_COLLS)
    assert full.get("__enabled__"), "restore harus aktif (DB uji)"
    ids = snapshot_new_ids(NEW_COLLS)
    kept = {}   # (koleksi, id) → dokumen asli

    def keep(coll, doc_id):
        kept[(coll, doc_id)] = mdb[coll].find_one({"id": doc_id})
    yield keep
    purge_new_ids(ids)
    for (coll, doc_id), doc in kept.items():
        if doc is None:
            mdb[coll].delete_one({"id": doc_id})   # dokumen uji yang lahir di test
        else:
            mdb[coll].replace_one({"id": doc_id}, doc)
    restore_stock(full)


def _task(mdb, product_id, statuses):
    t = mdb.wms_tasks.find_one({"flow_type": "inbound", "product_id": product_id, "status": {"$in": statuses},
                                "po_id": {"$gt": ""}, "entity_id": "ent_ksc"}, {"_id": 0})
    if not t:
        pytest.skip(f"seed tak punya tugas inbound {product_id} {statuses}")
    return t


def _fingerprint(mdb, task_id, po_id, product_id, before_line):
    t = mdb.wms_tasks.find_one({"id": task_id}, {"_id": 0})
    rolls = list(mdb.inventory_rolls.find({"grn_task_id": task_id}, {"_id": 0}))
    po = mdb.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    line = next(i for i in po["items"] if i["product_id"] == product_id)
    jes = list(mdb.journal_entries.find({"source_type": "goods_receipt", "source_id": task_id}, {"_id": 0}))
    lots = list(mdb.inventory_lots.find({"id": {"$in": t.get("lot_ids") or []}}, {"_id": 0}))
    return {
        "task_status": t["status"], "qty_rolls": t.get("qty_rolls"),
        "rolls": sorted((round(r.get("length_initial") or r.get("length") or 0, 2), r.get("grade"), r.get("status"),
                         r.get("dye_lot")) for r in rolls),
        "po_received_delta": round(float(line.get("received_qty") or 0) - before_line, 2),
        "po_status": po["status"],
        "je_count": len(jes), "je_debit": round(sum(float(ln.get("debit") or 0) for j in jes for ln in j.get("lines") or []), 2),
        "lots": sorted((lt.get("dye_lot"), round(float(lt.get("qty_initial") or lt.get("quantity") or 0), 2)) for lt in lots),
    }


def _po_line_received(mdb, po_id, product_id):
    po = mdb.purchase_orders.find_one({"id": po_id}, {"_id": 0, "items": 1})
    return float(next(i for i in po["items"] if i["product_id"] == product_id).get("received_qty") or 0)


def test_complete_scanned_rolls_path(wh, mdb, restore):
    seed = _task(mdb, "prod_batik_mega", ["waiting_goods", "receiving"])
    # Klon tugas seed (PO & produk sama) supaya tidak berebut tugas dengan modul uji lain yang paralel.
    t = {**seed, "id": "wms_char_" + uuid.uuid4().hex[:6], "status": "waiting_goods", "received_qty": 0.0,
         "qty_rolls_scanned": 0, "scan_log": [], "refs": []}
    t.pop("_id", None)
    restore("wms_tasks", t["id"])
    mdb.wms_tasks.insert_one(dict(t))
    restore("purchase_orders", t["po_id"])
    before = _po_line_received(mdb, t["po_id"], t["product_id"])
    exp = float(t["expected_qty"])
    tag = uuid.uuid4().hex[:4]
    for i, qty in enumerate([exp - 100, 100]):
        r = wh.post(f"{BASE}/inbound/tasks/{t['id']}/scan-label",
                    json={"raw": f"CBN-MEGA-PREM|DL-CH|CH{tag}-R{i}|{qty:g}"}, timeout=30)
        assert r.status_code == 200, r.text
    r = wh.post(f"{BASE}/inbound/tasks/{t['id']}/complete", json={}, timeout=60)
    assert r.status_code == 200, r.text
    fp = _fingerprint(mdb, t["id"], t["po_id"], t["product_id"], before)
    print("FP-A", fp)
    assert fp == GOLDEN_A(exp)


def test_complete_manual_rolls_path(wh, mdb, restore):
    t = _task(mdb, "prod_songket_palembang", ["receiving", "waiting_goods"])
    restore("wms_tasks", t["id"])
    restore("purchase_orders", t["po_id"])
    before = _po_line_received(mdb, t["po_id"], t["product_id"])
    rem = round(float(t["expected_qty"]) - float(t.get("received_qty") or 0), 2)
    r = wh.post(f"{BASE}/inbound/tasks/{t['id']}/scan-receive",
                json={"product_id": t["product_id"], "actual_qty": rem, "lot": "LOT-CH"}, timeout=30)
    assert r.status_code == 200, r.text
    recv = float(r.json()["received_qty"])
    body = {"rolls": [{"length": round(recv - 20, 2), "weight": 0, "dye_lot": "DL-M1", "grade": "A"},
                      {"length": 20, "weight": 0, "dye_lot": "DL-M1", "grade": "B"}],
            "supplier_lot": "SUP-CH-01"}
    r = wh.post(f"{BASE}/inbound/tasks/{t['id']}/complete", json=body, timeout=60)
    assert r.status_code == 200, r.text
    fp = _fingerprint(mdb, t["id"], t["po_id"], t["product_id"], before)
    print("FP-B", fp)
    assert fp == GOLDEN_B(recv, rem)


# Nilai emas = keluaran kode LAMA (router sebelum refactor Fase 1) pada seed `seed_realistic`.
# Nilai jurnal bergantung harga PO seed; bila seed berubah, rekam ulang dari kode lama — JANGAN dari kode baru.
def GOLDEN_A(exp):  # noqa: N802
    return {"task_status": "qc_pending", "qty_rolls": 2,
            "rolls": sorted([(100.0, "A", "quarantine", "DL-CH"), (round(exp - 100, 2), "A", "quarantine", "DL-CH")]),
            "po_received_delta": exp, "po_status": "completed", "je_count": 1, "je_debit": 29250000.0,
            "lots": [("DL-CH", exp)]}


def GOLDEN_B(recv, rem):  # noqa: N802
    return {"task_status": "qc_pending", "qty_rolls": 2,
            "rolls": sorted([(20.0, "B", "quarantine", "DL-M1"), (round(recv - 20, 2), "A", "quarantine", "DL-M1")]),
            "po_received_delta": recv, "po_status": "partial", "je_count": 1, "je_debit": 32250000.0,
            "lots": [("DL-M1", recv)]}
