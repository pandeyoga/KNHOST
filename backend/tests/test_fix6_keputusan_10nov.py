"""FIX-6 — keputusan pemilik 10 Nov 2026: alur masuk & retur + tabel transisi GRN / retur jual / retur beli.

Keputusan yang diuji (docs/audit/2026-11-09-wms-rfid/KEPUTUSAN-KOORDINATOR.md "Keputusan pemilik langsung — 10 Nov"):
  D5  retur penjualan MASUK STOK saat dipindai (karantina retur, nilai & jurnal saat settle, tanpa jurnal ganda,
      batal/tolak sebelum settle membalik)                                   — B2a FLW-IN-09
  D2  tolak QC + retur supplier dipilih per kasus: ganti barang / potong tagihan (PO, AP, jurnal pembalik GR-IR)
                                                                              — B2a FLW-IN-11
  D9  satu SJ supplier untuk dua PT → GRN per PT (pagar PT & lokasi)          — B2a FLW-IN-14
  minta inspeksi (baris PO / penerimaan → draf PA ke gedung inspeksi)
  izin unduh lembar master untuk MD (`product.export`)
  tabel transisi daftar-izin + CAS + status_history (GRN, retur jual, retur beli)
Setiap uji GAGAL di dasar `main` (sebelum FIX-6) dan LULUS sesudahnya. Data uji dibuat sendiri (gudang/site/PO/
supplier/produk ber-TAG) kecuali roll terkirim SO acuan KSC/SO-00001 (dipulihkan di akhir, pola test_l08_ln081).
Jalankan (stack sementara): cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_fix6_keputusan_10nov.py
"""
import os
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:6].upper()
NOTE = f"TEST_FIX6_{TAG}"
OLD_TS = "2026-01-01T00:00:00+00:00"
KSC, KANDA = "ent_ksc", "ent_kanda"
SITE, SITE2 = f"site_fx6_{TAG}", f"site_fx6b_{TAG}"
W_T, W_S, W_I, W_K, W_X = (f"wh_fx6_{k}_{TAG}" for k in ("t", "s", "i", "k", "x"))
P = f"prod_fx6_{TAG}"
SUP = f"sup_fx6_{TAG}"
SO = DB.sales_orders.find_one({"number": "KSC/SO-00001"}) or {}
JKT = "wh_jakarta"
POS, TASKS, ROLLS, PRETS, GRNS = [], [], [], [], []


@pytest.fixture(scope="module", autouse=True)
def world():
    before = {r["id"]: r for r in DB.inventory_rolls.find({"status": "delivered"})}
    DB.warehouse_sites.insert_many([{"id": SITE, "name": f"TEST_FIX6 {TAG}"}, {"id": SITE2, "name": f"TEST_FIX6 B {TAG}"}])
    base = {"city": "Bandung", "sharing_mode": "shared", "entity_ids": [], "active": True, "created_at": OLD_TS,
            "zones": []}
    DB.warehouses.insert_many([
        {**base, "id": W_T, "code": f"FX6T-{TAG}", "name": f"TEST FX6 Transit {TAG}", "site_id": SITE, "roles": ["transit"]},
        {**base, "id": W_S, "code": f"FX6S-{TAG}", "name": f"TEST FX6 Simpan {TAG}", "site_id": SITE, "roles": ["storage"]},
        {**base, "id": W_I, "code": f"FX6I-{TAG}", "name": f"TEST FX6 Inspeksi {TAG}", "site_id": SITE, "roles": ["inspection"]},
        {**base, "id": W_K, "code": f"FX6K-{TAG}", "name": f"TEST FX6 Kanda {TAG}", "site_id": SITE, "roles": ["transit"]},
        {**base, "id": W_X, "code": f"FX6X-{TAG}", "name": f"TEST FX6 Lain {TAG}", "site_id": SITE2, "roles": ["transit"]}])
    DB.products.insert_one({"id": P, "sku": f"FX6-{TAG}", "name": f"Kain Uji FIX6 {TAG}", "base_unit": "yard",
                            "status": "active", "stage": "finished", "grade": "A", "category": "Kain",
                            "harga_pokok": 10000.0, "created_at": OLD_TS})
    DB.suppliers.insert_one({"id": SUP, "name": f"Supplier Uji FIX6 {TAG}", "code": f"SFX6{TAG}", "status": "active",
                             "created_at": OLD_TS})
    yield
    # retur jual uji: balik penyelesaian lalu pulihkan roll terkirim acuan
    sr_ids = [d["id"] for d in DB.sales_returns.find({"notes": NOTE}, {"id": 1})]
    rolls = [r["id"] for r in DB.inventory_rolls.find({"$or": [{"product_id": P}, {"return_id": {"$in": sr_ids}},
                                                                 {"warehouse_id": {"$in": [W_T, W_S, W_I, W_K, W_X]}}]},
                                                       {"id": 1})] + ROLLS
    for rid, doc in before.items():
        cur = DB.inventory_rolls.find_one({"id": rid}, {"_id": 0, "status": 1, "return_intake": 1, "return_history": 1})
        if cur and (cur.get("status") != "delivered" or (cur.get("return_intake") or {}).get("return_id") in sr_ids
                    or any(x.get("return_id") in sr_ids for x in cur.get("return_history") or [])):
            DB.inventory_rolls.replace_one({"id": rid}, doc)
    DB.inventory_rolls.delete_many({"id": {"$in": [r for r in rolls if r not in before]}})
    DB.inventory_rolls.delete_many({"return_id": {"$in": sr_ids}, "id": {"$nin": list(before)}})
    for coll in ("credit_notes", "journal_entries", "cash_transactions", "inventory_movements", "store_credit_ledger"):
        DB[coll].delete_many({"$or": [{"return_id": {"$in": sr_ids}}, {"ref_id": {"$in": sr_ids}},
                                      {"source_id": {"$in": sr_ids + PRETS}}, {"roll_id": {"$in": rolls}}]})
    for coll in ("journal_entries", "cash_transactions", "store_credit_ledger"):   # penyelesaian per roll `<retur>:<ev>`
        DB[coll].delete_many({"$or": [{"source_id": {"$regex": f"^sret_fx6_{TAG}"}}, {"ref_id": {"$regex": f"^sret_fx6_{TAG}"}}]})
    DB.sales_returns.delete_many({"id": {"$in": sr_ids}})
    DB.purchase_returns.delete_many({"$or": [{"id": {"$in": PRETS}}, {"po_id": {"$in": POS}}]})
    DB.vendor_bills.delete_many({"po_id": {"$in": POS}})
    DB.wms_tasks.delete_many({"$or": [{"id": {"$in": TASKS}}, {"po_id": {"$in": POS}}]})
    DB.goods_receipts.delete_many({"$or": [{"id": {"$in": GRNS}}, {"partner_id": SUP}]})
    DB.purchase_orders.delete_many({"id": {"$in": POS}})
    DB.putaway_orders.delete_many({"$or": [{"from_warehouse_id": {"$in": [W_T, W_K]}}, {"items.product_id": P}]})
    DB.inventory_balances.delete_many({"$or": [{"product_id": P}, {"warehouse_id": {"$in": [W_T, W_S, W_I, W_K, W_X]}}]})
    DB.inventory_lots.delete_many({"product_id": P})
    DB.products.delete_many({"id": P})
    DB.suppliers.delete_many({"id": SUP})
    DB.warehouses.delete_many({"id": {"$in": [W_T, W_S, W_I, W_K, W_X]}})
    DB.warehouse_sites.delete_many({"id": {"$in": [SITE, SITE2]}})


def _login(email, entity=KSC):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": os.environ.get("KN_DEMO_PW", "demo12345")})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id")


def _detail(resp):
    d = resp.json().get("detail")
    return d if isinstance(d, str) else (d.get("message") if isinstance(d, dict) else str(d))


# ═══ D5 — retur penjualan masuk stok saat dipindai ═══════════════════════════════════════════════════════════════
def _whole_roll(h, skip=()):
    data = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": SO["id"]}).json()
    rows = [r for r in data["rolls"] if r["remaining"] >= r["shipped_qty"] - 0.01 and r["roll_id"] not in skip
            and (DB.inventory_rolls.find_one({"id": r["roll_id"]}) or {}).get("status") == "delivered"]
    if not rows:
        pytest.skip("tidak ada roll terkirim utuh tersisa di SO acuan")
    return rows[0]


def _new_return(h, roll, qty=None, approve=True):
    q = roll["remaining"] if qty is None else qty
    r = requests.post(f"{BASE}/sales-returns", headers=h, json={
        "order_id": SO["id"], "return_type": "retur", "notes": NOTE, "submit_now": True,
        "items": [{"product_id": roll["product_id"], "quantity_returned": q, "unit": roll["unit"],
                   "roll_ids": [roll["roll_id"]], "roll_qtys": {roll["roll_id"]: q}, "reason": "cacat warna"}]})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    if approve:
        assert requests.post(f"{BASE}/sales-returns/{rid}/approve", headers=h, json={"notes": ""}).status_code == 200
    return rid


def _scan(h, rid, stage, code, wh, to=""):
    return requests.post(f"{BASE}/sales-returns/{rid}/journey/scan", headers=h, json={
        "stage": stage, "codes": [code], "warehouse_id": wh, "to_warehouse_id": to, "carrier": "Sopir TEST"})


def test_d5_scan_received_enters_return_quarantine_without_value_or_journal(adm):
    roll = _whole_roll(adm)
    rid = _new_return(adm, roll)
    jes_before = DB.journal_entries.count_documents({"source_type": "sales_return", "source_id": rid})
    r = _scan(adm, rid, "received", roll["roll_no"], JKT)
    assert r.status_code == 200, r.text
    doc = DB.inventory_rolls.find_one({"id": roll["roll_id"]})
    # stok di gudang pindai sebagai karantina retur (kelompok "Ditahan / QC" FIX-2), BUKAN tersedia
    assert doc["status"] == "quarantine" and doc["warehouse_id"] == JKT, doc.get("status")
    assert doc["qc_status"] == "return_received" and doc["return_intake"]["state"] == "received"
    assert float(doc["unit_cost"]) == 0.0 and float(doc.get("base_unit_cost") or 0) == 0.0   # nilai saat settle
    assert DB.inventory_movements.count_documents({"roll_id": roll["roll_id"], "movement_type": "return_quarantine_in",
                                                   "ref_id": rid}) == 1
    assert DB.journal_entries.count_documents({"source_type": "sales_return", "source_id": rid}) == jes_before == 0
    # belum dinilai → tidak bisa dilepas ke stok tersedia
    rel = requests.post(f"{BASE}/sales-returns/{rid}/quarantine/release", headers=adm, json={"decisions": [], "notes": ""})
    assert rel.status_code == 400 and "belum dinilai" in _detail(rel)
    q = requests.get(f"{BASE}/sales-returns/{rid}/quarantine", headers=adm).json()
    assert any(x["id"] == roll["roll_id"] and x["intake_pending_valuation"] for x in q)
    # D5 — settle MENILAI roll yang sama: satu jurnal, satu mutasi masuk, tanpa roll kedua
    assert requests.post(f"{BASE}/sales-returns/{rid}/inspect/start", headers=adm, json={}).status_code == 200
    ok = requests.post(f"{BASE}/sales-returns/{rid}/inspect/complete", headers=adm,
                       json={"inspections": [{"index": 0, "grade": "A", "condition": "ok"}]})
    assert ok.status_code == 200, ok.text
    st = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=adm, json={"outcome": "refund"})
    assert st.status_code == 200, st.text
    doc = DB.inventory_rolls.find_one({"id": roll["roll_id"]})
    assert doc["status"] == "quarantine" and doc["return_intake"]["state"] == "valued" and float(doc["unit_cost"]) > 0
    assert DB.inventory_rolls.count_documents({"return_id": rid}) == 1                  # tidak ada roll kedua
    assert DB.inventory_movements.count_documents({"roll_id": roll["roll_id"], "ref_id": rid,
                                                   "movement_type": "return_quarantine_in"}) == 1
    jes = list(DB.journal_entries.find({"source_type": "sales_return", "source_id": rid, "status": {"$ne": "void"}}))
    assert len(jes) == 1                                                                 # tanpa jurnal ganda
    persediaan_dr = sum(float(ln.get("debit") or 0) for ln in jes[0]["lines"] if ln["account_code"] == "1-1300")
    value = round(float(doc["length_remaining"]) * float(doc["unit_cost"]), 2)
    assert abs(persediaan_dr - value) <= 1.0, (persediaan_dr, value)                     # subledger = GL
    hist = DB.sales_returns.find_one({"id": rid})["status_history"]
    assert [h["status"] for h in hist][-3:] == ["inspecting", "inspected", "refund_settled"]


def test_d5_reject_before_settle_reverses_return_quarantine(adm):
    roll = _whole_roll(adm)
    orig = DB.inventory_rolls.find_one({"id": roll["roll_id"]})
    rid = _new_return(adm, roll)
    assert _scan(adm, rid, "received", roll["roll_no"], JKT).status_code == 200
    assert DB.inventory_rolls.find_one({"id": roll["roll_id"]})["status"] == "quarantine"
    rj = requests.post(f"{BASE}/sales-returns/{rid}/reject", headers=adm, json={"notes": "Klaim tidak terbukti cacat"})
    assert rj.status_code == 200, rj.text
    back = DB.inventory_rolls.find_one({"id": roll["roll_id"]})
    assert back["status"] == "delivered" and back["warehouse_id"] == orig["warehouse_id"]
    assert float(back.get("unit_cost") or 0) == float(orig.get("unit_cost") or 0)
    assert back["return_intake"]["state"] == "reversed" and not back.get("returned_identity")
    assert DB.inventory_movements.count_documents({"roll_id": roll["roll_id"], "ref_id": rid,
                                                   "movement_type": "return_reversal_out"}) == 1
    assert DB.journal_entries.count_documents({"source_type": "sales_return", "source_id": rid}) == 0
    assert DB.sales_returns.find_one({"id": rid})["status_history"][-1]["status"] == "rejected"


def test_d5_partial_claim_child_and_roll_decision_reverses(adm):
    roll = _whole_roll(adm)
    rid = _new_return(adm, roll, qty=round(roll["remaining"] / 2, 2), approve=False)   # menunggu persetujuan
    assert _scan(adm, rid, "received", roll["roll_no"], JKT).status_code == 200
    child = DB.inventory_rolls.find_one({"return_intake.return_id": rid, "return_intake.source_roll_id": roll["roll_id"]})
    assert child and child["id"] != roll["roll_id"] and child["status"] == "quarantine"
    assert child["return_intake"]["mode"] == "child" and float(child["length_remaining"]) == round(roll["remaining"] / 2, 2)
    assert DB.inventory_rolls.find_one({"id": roll["roll_id"]})["status"] == "delivered"   # induk tetap di pelanggan
    dec = requests.post(f"{BASE}/sales-returns/{rid}/roll-decisions", headers=adm, json={
        "decisions": [{"roll_id": roll["roll_id"], "decision": "reject", "reason": "Roll sudah dipotong pelanggan"}]})
    assert dec.status_code == 200, dec.text
    assert DB.inventory_rolls.find_one({"id": child["id"]}) is None                        # anak karantina dihapus
    assert DB.sales_returns.find_one({"id": rid})["status"] == "rejected"


def test_d5_arrived_elsewhere_moves_return_quarantine(adm):
    roll = _whole_roll(adm)
    rid = _new_return(adm, roll)
    assert _scan(adm, rid, "received", roll["roll_no"], JKT).status_code == 200
    rcm = DB.warehouses.find_one({"name": {"$regex": "^Rancamalang · Gudang Retur"}})["id"]
    assert _scan(adm, rid, "dispatched", roll["roll_no"], JKT, rcm).status_code == 200
    assert _scan(adm, rid, "arrived", roll["roll_no"], rcm).status_code == 200
    doc = DB.inventory_rolls.find_one({"id": roll["roll_id"]})
    assert doc["warehouse_id"] == rcm and doc["status"] == "quarantine" and doc["return_intake"]["warehouse_id"] == rcm
    bal = DB.inventory_balances.find_one({"product_id": doc["product_id"], "warehouse_id": rcm, "owner_entity_id": KSC})
    assert bal and float(bal.get("quarantine_qty") or 0) >= float(doc["length_remaining"]) - 0.01
    requests.post(f"{BASE}/sales-returns/{rid}/reject", headers=adm, json={"notes": "Uji dibatalkan rapi"})


def test_d5_roll_settlement_values_stock_roll_and_reverses_rejected_roll(adm):
    """Penyelesaian PER ROLL sesudah pindai: roll Pengembalian Dana dinilai (roll yang sama, satu jurnal per
    penyelesaian), roll Tolak klaim dibalik ke "di pelanggan" (tanpa nilai/jurnal)."""
    from services import return_intake_service as _intake
    pid, price = "prod_batik_mega", 30000
    src = DB.sales_orders.find_one({"number": "KSC/SO-00003"}, {"_id": 0})
    if not src:
        pytest.skip("SO acuan KSC/SO-00003 tidak ada")
    so, ret_id = f"so_fx6_{TAG}", f"sret_fx6_{TAG}"
    DB.sales_orders.insert_one({**{k: src[k] for k in ("customer_id", "customer_name", "entity_id")},
                                "id": so, "number": f"TEST_SO-FX6-{TAG}", "status": "done", "payment_term_code": "NET30",
                                "items": [{"product_id": pid, "quantity": 200, "base_quantity": 200, "line_total": 200 * price}],
                                "ppn_rate": 11, "ppn_amount": 660000, "grand_total": 6660000, "qc_request": {"mode": "none"},
                                "payments": [{"amount": 6660000}]})
    tmpl = DB.inventory_rolls.find_one({"product_id": pid, "owner_entity_id": KSC}, {"_id": 0}) or {}
    rids = []
    for i in range(2):
        rid = f"roll_fx6_rs_{TAG}_{i}"
        DB.inventory_rolls.insert_one({**tmpl, "id": rid, "roll_no": f"FX6RS-{TAG}-{i}", "product_id": pid,
                                       "status": "delivered", "unit": "yard", "length": 100.0, "length_initial": 100.0,
                                       "length_remaining": 100.0, "owner_entity_id": KSC, "warehouse_id": "wh_jakarta",
                                       "unit_cost": 18000.0, "base_unit_cost": 18000.0, "grade": "A", "rfid_tag_id": None,
                                       "reserved_ref": None, "committed_to": None, "earmarked_for": None,
                                       "return_intake": None, "return_history": []})
        ROLLS.append(rid)
        rids.append(rid)
    results = {r: {"roll_no": f"FX6RS-{TAG}-{i}", "grade": "A", "actual_qty": 100.0, "condition": "ok"}
               for i, r in enumerate(rids)}
    DB.sales_returns.insert_one({
        "id": ret_id, "number": f"TEST_RET-FX6-{TAG}", "order_id": so, "order_number": f"TEST_SO-FX6-{TAG}",
        "entity_id": KSC, "customer_id": src["customer_id"], "customer_name": src["customer_name"], "notes": NOTE,
        "return_type": "retur", "status": "inspected",
        "roll_locations": {r: {"stage": "received", "warehouse_id": "wh_jakarta"} for r in rids},
        "items": [{"product_id": pid, "product_name": "TEST", "unit": "yard", "quantity_returned": 200.0, "condition": "ok",
                   "roll_ids": rids, "roll_qtys": {r: 100.0 for r in rids},
                   "inspection": {"grade": "A", "accepted_qty": 200.0, "roll_results": results,
                                  "roll_actuals": {r: 100.0 for r in rids}}}]})
    try:
        ret = DB.sales_returns.find_one({"id": ret_id}, {"_id": 0})
        got = run(_intake.receive(ret, rids, "wh_jakarta", "Uji", "TRM-1"))          # = pindai diterima
        assert len(got["received"]) == 2
        r = requests.post(f"{BASE}/sales-returns/{ret_id}/roll-settlement", headers=adm, json={
            "rolls": [{"roll_id": rids[0], "outcome": "refund"}, {"roll_id": rids[1], "outcome": "reject"}],
            "payout": "", "decision_note": "uji FIX-6 per roll"})
        assert r.status_code == 200, r.text
        ev = r.json()["settlements"][-1]
        a, b = DB.inventory_rolls.find_one({"id": rids[0]}), DB.inventory_rolls.find_one({"id": rids[1]})
        assert a["status"] == "quarantine" and a["return_intake"]["state"] == "valued" and float(a["unit_cost"]) > 0
        assert b["status"] == "delivered" and b["return_intake"]["state"] == "reversed"
        jes = list(DB.journal_entries.find({"source_type": "sales_return", "source_id": f"{ret_id}:{ev['id']}"}))
        assert len(jes) == 1
        dr = sum(float(ln.get("debit") or 0) for ln in jes[0]["lines"] if ln["account_code"] == "1-1300")
        assert abs(dr - round(float(a["length_remaining"]) * float(a["unit_cost"]), 2)) <= 1.0
        assert DB.inventory_movements.count_documents({"roll_id": rids[0], "movement_type": "return_quarantine_in"}) == 1
    finally:
        DB.sales_orders.delete_many({"id": so})


# ═══ D2 — tolak QC + retur supplier: ganti barang / potong tagihan ════════════════════════════════════════════════
def _po_task_roll(status="completed", qty=50.0, price=10000.0, received=None):
    po_id, tid = f"po_fx6_{uuid.uuid4().hex[:8]}", f"wms_fx6_{uuid.uuid4().hex[:8]}"
    net = round(qty * price, 2)
    DB.purchase_orders.insert_one({
        "id": po_id, "po_number": f"PO-FX6-{po_id[-6:]}", "entity_id": KSC, "supplier_id": SUP,
        "supplier_name": f"Supplier Uji FIX6 {TAG}", "status": status, "warehouse_id": W_S, "po_type": "standard",
        "items": [{"product_id": P, "sku": f"FX6-{TAG}", "product_name": "Kain Uji FIX6", "quantity": qty,
                   "received_qty": qty if received is None else received, "price": price, "unit": "yard"}],
        "total_amount": net, "net_subtotal": net, "ppn_amount": round(net * 0.11, 2), "ppn_rate": 11,
        "grand_total": round(net * 1.11, 2), "amount_paid": 0.0, "returned_amount": 0.0, "timeline": [],
        "created_at": OLD_TS})
    POS.append(po_id)
    DB.wms_tasks.insert_one({"id": tid, "flow_type": "inbound", "source_type": "purchase_order", "status": "qc_pending",
                             "po_id": po_id, "po_number": f"PO-FX6-{po_id[-6:]}", "product_id": P, "warehouse_id": W_S,
                             "entity_id": KSC, "expected_qty": qty, "received_qty": qty, "unit": "yard",
                             "qc_plan": {"mode": "none"}, "supplier_name": "Supplier Uji", "created_at": OLD_TS})
    TASKS.append(tid)
    rid = f"roll_fx6_{uuid.uuid4().hex[:8]}"
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"FX6-{rid[-6:]}", "product_id": P, "warehouse_id": W_S,
                                   "owner_entity_id": KSC, "length_initial": qty, "length_remaining": qty,
                                   "unit": "yard", "status": "quarantine", "qc_task_id": tid, "grade": "A",
                                   "unit_cost": price, "base_unit_cost": price, "po_id": po_id, "created_at": OLD_TS})
    ROLLS.append(rid)
    return po_id, tid, rid


def _reject_return(h, tid, qty, **extra):
    return requests.post(f"{BASE}/inbound/tasks/{tid}/qc-decision", headers=h, json={
        "accept_qty": 0, "reject_qty": qty, "reject_disposition": "return", "reason": "Warna belang tidak sesuai",
        **extra})


def test_d2_qc_return_requires_remedy_choice_and_reason(adm):
    _po, tid, _r = _po_task_roll()
    r = _reject_return(adm, tid, 50)
    assert r.status_code == 400 and "Ganti barang" in _detail(r)
    r = _reject_return(adm, tid, 50, return_remedy="replace", return_remedy_reason="....")
    assert r.status_code == 400
    assert DB.purchase_returns.count_documents({"po_id": _po}) == 0
    assert DB.wms_tasks.find_one({"id": tid})["status"] == "qc_pending"


def test_d2_replace_reopens_po_with_remainder_task_and_grir_reversal(adm):
    po_id, tid, rid = _po_task_roll()
    r = _reject_return(adm, tid, 50, return_remedy="replace", return_remedy_reason="Supplier sanggup kirim ganti")
    assert r.status_code == 200, r.text
    pret = DB.purchase_returns.find_one({"po_id": po_id})
    PRETS.append(pret["id"])
    assert pret["remedy"]["choice"] == "replace" and pret["remedy"]["reason"] == "Supplier sanggup kirim ganti"
    assert DB.audit_logs.find_one({"action": "purchase_return_remedy_chosen", "entity_id": pret["id"]})
    ap = requests.post(f"{BASE}/purchase-returns/{pret['id']}/approve", headers=adm, json={"notes": "ok ganti"})
    assert ap.status_code == 200, ap.text
    po = DB.purchase_orders.find_one({"id": po_id})
    assert po["status"] == "partial" and float(po["items"][0]["received_qty"]) == 0.0
    assert float(po["items"][0]["replaced_qty"]) == 50.0 and float(po.get("returned_amount") or 0) == 0.0  # AP tetap
    new = DB.wms_tasks.find_one({"po_id": po_id, "status": "waiting_goods"})
    assert new and float(new["expected_qty"]) == 50.0 and new["replacement_for_return"]["id"] == pret["id"]
    je = DB.journal_entries.find_one({"source_type": "purchase_return", "source_id": pret["id"]})
    lines = {ln["account_code"]: ln for ln in je["lines"]}
    assert set(lines) == {"2-1150", "1-1300"} and float(lines["2-1150"]["debit"]) == 500000.0   # neto, tanpa PPN
    assert float(lines["1-1300"]["credit"]) == 500000.0
    doc = DB.purchase_returns.find_one({"id": pret["id"]})
    assert doc["status_history"][-1]["status"] == "approved" and not doc.get("debit_note_number")
    # koreksi (reverse) membalik efek PO: tugas pengganti batal, PO kembali seperti sebelum retur
    rv = requests.post(f"{BASE}/purchase-returns/{pret['id']}/reverse", headers=adm, json={"notes": "salah pilih remedi"})
    assert rv.status_code == 200, rv.text
    po = DB.purchase_orders.find_one({"id": po_id})
    assert po["status"] == "completed" and float(po["items"][0]["received_qty"]) == 50.0
    assert DB.wms_tasks.find_one({"id": new["id"]})["status"] == "cancelled"
    assert DB.inventory_rolls.find_one({"id": rid})["status"] == "quarantine"
    assert DB.purchase_returns.find_one({"id": pret["id"]})["status_history"][-1]["status"] == "cancelled"


def test_d2_bill_cut_unbilled_closes_short_and_reduces_billing(adm):
    po_id, tid, _rid = _po_task_roll()
    # 50 karantina → 30 diterima, 20 ditolak & diretur (potong tagihan)
    r = requests.post(f"{BASE}/inbound/tasks/{tid}/qc-decision", headers=adm, json={
        "accept_qty": 30, "reject_qty": 20, "reject_disposition": "return", "reason": "Belang di 20 yard",
        "return_remedy": "bill_cut", "return_remedy_reason": "Tidak perlu ganti, potong saja"})
    assert r.status_code == 200, r.text
    pret = DB.purchase_returns.find_one({"po_id": po_id})
    PRETS.append(pret["id"])
    ap = requests.post(f"{BASE}/purchase-returns/{pret['id']}/approve", headers=adm, json={"notes": "potong"})
    assert ap.status_code == 200, ap.text
    po = DB.purchase_orders.find_one({"id": po_id})
    assert po["status"] == "closed_short" and float(po["items"][0]["returned_qty"]) == 20.0
    assert float(po["items"][0]["received_qty"]) == 50.0
    assert abs(float(po["returned_amount"]) - 222000.0) < 0.01                        # AP turun bruto (20×10.000×1,11)
    je = DB.journal_entries.find_one({"source_type": "purchase_return", "source_id": pret["id"]})
    accs = {ln["account_code"] for ln in je["lines"]}
    assert accs == {"2-1150", "1-1300"}                                              # belum ditagih: pembalik GR-IR neto
    ctx = requests.get(f"{BASE}/purchase-orders/{po_id}/billing-context", headers=adm)
    assert ctx.status_code == 200, ctx.text
    it = (ctx.json().get("items") or [{}])[0]
    assert float(it.get("billable_received", 0)) == 30.0                             # tagihan = diterima − diretur


def test_d2_bill_cut_billed_posts_debit_note_against_payable(adm):
    po_id, tid, _rid = _po_task_roll()
    DB.vendor_bills.insert_one({"id": f"vb_fx6_{po_id[-6:]}", "po_id": po_id, "status": "posted", "entity_id": KSC,
                                "grand_total": 555000.0, "bill_number": f"VB-FX6-{po_id[-6:]}", "items": []})
    r = _reject_return(adm, tid, 50, return_remedy="bill_cut", return_remedy_reason="Sudah ditagih, potong tagihan")
    assert r.status_code == 200, r.text
    pret = DB.purchase_returns.find_one({"po_id": po_id})
    PRETS.append(pret["id"])
    assert requests.post(f"{BASE}/purchase-returns/{pret['id']}/approve", headers=adm, json={}).status_code == 200
    je = DB.journal_entries.find_one({"source_type": "purchase_return", "source_id": pret["id"]})
    lines = {ln["account_code"]: ln for ln in je["lines"]}
    assert "2-1100" in lines and float(lines["2-1100"]["debit"]) == 555000.0          # Nota Debit ke Hutang (bruto)
    assert "2-1150" not in lines
    doc = DB.purchase_returns.find_one({"id": pret["id"]})
    assert doc["remedy"]["choice"] == "bill_cut" and doc["remedy_result"]["gl_mode"] == "debit_note_ap"
    po = DB.purchase_orders.find_one({"id": po_id})
    assert po["status"] == "closed_short" and float(po["items"][0]["returned_qty"]) == 50.0     # PO ditutup kurang


def test_d2_rejected_qc_return_rolls_back_as_damaged(adm):
    po_id, tid, rid = _po_task_roll()
    assert _reject_return(adm, tid, 50, return_remedy="replace",
                          return_remedy_reason="Minta ganti barang").status_code == 200
    pret = DB.purchase_returns.find_one({"po_id": po_id})
    PRETS.append(pret["id"])
    assert DB.inventory_rolls.find_one({"id": rid})["status"] == "returned_supplier"
    rj = requests.post(f"{BASE}/purchase-returns/{pret['id']}/reject", headers=adm, json={"notes": "Supplier menolak retur"})
    assert rj.status_code == 200, rj.text
    assert DB.inventory_rolls.find_one({"id": rid})["status"] == "damaged"            # tetap persediaan (rusak)
    doc = DB.purchase_returns.find_one({"id": pret["id"]})
    assert doc["status_history"][-1]["status"] == "rejected" and doc["rejected_rolls_back_damaged"] == 1
    assert DB.purchase_orders.find_one({"id": po_id})["status"] == "completed"       # PO tidak tersentuh


# ═══ D9 — satu SJ supplier untuk dua PT → GRN per PT ═══════════════════════════════════════════════════════════════
def _open_po(entity, wh, qty=10.0):
    po_id = f"po_fx6_{uuid.uuid4().hex[:8]}"
    DB.purchase_orders.insert_one({
        "id": po_id, "po_number": f"PO-FX6D9-{po_id[-6:]}", "entity_id": entity, "supplier_id": SUP,
        "supplier_name": f"Supplier Uji FIX6 {TAG}", "status": "pending", "warehouse_id": wh, "po_type": "standard",
        "items": [{"product_id": P, "quantity": qty, "received_qty": 0.0, "price": 1000.0, "unit": "yard"}],
        "created_at": OLD_TS})
    POS.append(po_id)
    tid = f"wms_fx6_{uuid.uuid4().hex[:8]}"
    DB.wms_tasks.insert_one({"id": tid, "flow_type": "inbound", "source_type": "purchase_order", "status": "waiting_goods",
                             "po_id": po_id, "po_number": f"PO-FX6D9-{po_id[-6:]}", "product_id": P, "warehouse_id": wh,
                             "entity_id": entity, "expected_qty": qty, "received_qty": 0.0, "unit": "yard",
                             "created_at": OLD_TS})
    TASKS.append(tid)
    return po_id


def test_d9_one_delivery_note_two_pts_split_into_grn_per_pt(adm):
    a, b = _open_po(KSC, W_T), _open_po(KANDA, W_K)
    cand = requests.get(f"{BASE}/goods-receipts/arrival-candidates", headers=adm, params={"partner_id": SUP})
    assert cand.status_code == 200, cand.text
    site = next(s for s in cand.json()["sites"] if s["site_id"] == SITE)
    assert {p["id"] for p in site["pos"]} >= {a, b} and {p["entity_id"] for p in site["pos"]} >= {KSC, KANDA}
    r = requests.post(f"{BASE}/goods-receipts/arrival", headers=adm, json={"partner_id": SUP, "po_ids": [a, b]})
    assert r.status_code == 200, r.text
    out = r.json()
    GRNS.extend(g["id"] for g in out["grns"])
    by_ent = {g["entity_id"]: g for g in out["grns"]}
    assert set(by_ent) == {KSC, KANDA}
    assert by_ent[KSC]["source"]["po_ids"] == [a] and by_ent[KANDA]["source"]["po_ids"] == [b]
    assert by_ent[KSC]["warehouse_id"] == W_T and by_ent[KANDA]["warehouse_id"] == W_K
    for g in out["grns"]:
        doc = DB.goods_receipts.find_one({"id": g["id"]})
        assert doc["arrival"]["id"] == out["arrival_id"] and len(doc["arrival"]["siblings"]) == 2
    # transisi GRN tercatat (tabel transisi + status_history): batal satu GRN
    g = DB.goods_receipts.find_one({"id": by_ent[KANDA]["id"]})
    h_k = {**adm, "X-Entity-Id": KANDA}
    c = requests.post(f"{BASE}/goods-receipts/{g['id']}/cancel", headers=h_k,
                      json={"expected_version": g["version"], "reason": "Uji batal kedatangan"})
    assert c.status_code == 200, c.text
    hist = DB.goods_receipts.find_one({"id": g["id"]})["status_history"]
    assert hist[-1]["status"] == "cancelled" and hist[-1]["action"] == "cancel"


def test_d9_arrival_fences_location_and_pt(adm):
    a, x = _open_po(KSC, W_T), _open_po(KANDA, W_X)                       # dua lokasi berbeda
    r = requests.post(f"{BASE}/goods-receipts/arrival", headers=adm, json={"partner_id": SUP, "po_ids": [a, x]})
    assert r.status_code == 400 and "satu lokasi" in _detail(r)
    assert DB.goods_receipts.count_documents({"partner_id": SUP, "source.po_ids": {"$in": [a, x]}}) == 0
    wh = _login("warehouse@kainnusantara.id")                               # penugasan hanya PT KSC
    b = _open_po(KANDA, W_K)
    r = requests.post(f"{BASE}/goods-receipts/arrival", headers=wh, json={"partner_id": SUP, "po_ids": [a, b]})
    assert r.status_code == 403


# ═══ Penanda "minta inspeksi" ═══════════════════════════════════════════════════════════════════════════════════════
def test_inspection_flag_po_line_to_task_roll_and_inspection_draft():
    from routers.purchase_orders import _create_inbound_tasks_for_po
    from services import putaway_draft_service as pad
    po = {"id": f"po_fx6_{uuid.uuid4().hex[:8]}", "po_number": f"PO-FX6I-{TAG}", "entity_id": KSC, "warehouse_id": W_T,
          "supplier_name": "Supplier Uji", "items": [{"product_id": P, "quantity": 5, "unit": "yard",
                                                      "inspection_requested": True}]}
    POS.append(po["id"])
    run(_create_inbound_tasks_for_po(po))
    task = DB.wms_tasks.find_one({"po_id": po["id"]})
    TASKS.append(task["id"])
    assert task["inspection_request"]["requested"] is True and task["inspection_request"]["source"] == "po_line"
    rid = f"roll_fx6_{uuid.uuid4().hex[:8]}"
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"FX6I-{rid[-6:]}", "product_id": P, "warehouse_id": W_T,
                                   "owner_entity_id": KSC, "length_initial": 5, "length_remaining": 5, "unit": "yard",
                                   "status": "available", "grade": "A", "unit_cost": 1000, "stage": "finished",
                                   "inspection_request": task["inspection_request"],
                                   "journey": {"stage": "received_transit", "routing": "store"}, "created_at": OLD_TS})
    ROLLS.append(rid)
    assert run(pad.inspection_requested([rid])) == {rid}
    out = run(pad.auto_draft([rid], {"type": "qc_decision", "id": task["id"], "number": po["po_number"]}, "Uji"))
    d = next(x for x in out["drafts"])
    assert d["purpose"] == "inspection" and d["to_warehouse_name"].startswith("TEST FX6 Inspeksi")
    # sesudah singgah di gedung inspeksi, penanda tidak menahan rute lagi
    DB.inventory_rolls.update_one({"id": rid}, {"$set": {"journey.inspection_site": W_I}})
    assert run(pad.inspection_requested([rid])) == set()


def test_inspection_request_at_receiving_marks_task_and_rolls(adm):
    _po, tid, rid = _po_task_roll()
    bad = requests.post(f"{BASE}/inbound/tasks/{tid}/inspection-request", headers=adm, json={"requested": True, "reason": "..."})
    assert bad.status_code == 422
    r = requests.post(f"{BASE}/inbound/tasks/{tid}/inspection-request", headers=adm,
                      json={"requested": True, "reason": "Pola cetak meragukan"})
    assert r.status_code == 200, r.text
    assert DB.wms_tasks.find_one({"id": tid})["inspection_request"]["source"] == "receiving"
    assert DB.inventory_rolls.find_one({"id": rid})["inspection_request"]["requested"] is True
    DB.wms_tasks.update_one({"id": tid}, {"$set": {"status": "completed"}})
    late = requests.post(f"{BASE}/inbound/tasks/{tid}/inspection-request", headers=adm,
                         json={"requested": True, "reason": "Terlambat menandai"})
    assert late.status_code == 409


# ═══ Izin unduh lembar master untuk MD ═════════════════════════════════════════════════════════════════════════════
def test_md_can_download_master_cleanup_sheet():
    from permissions_config import DEFAULT_PERMISSIONS
    assert "export" in DEFAULT_PERMISSIONS["md"]["product"]
    md = _login("md@kainnusantara.id")
    r = requests.get(f"{BASE}/master-governance/cleanup/sheet", headers=md, params={"format": "csv"})
    assert r.status_code == 200, r.text[:300]


# ═══ Tabel transisi (daftar-izin + CAS + status_history) ═══════════════════════════════════════════════════════════
def test_transition_tables_allowlist_and_cas():
    from services import grn_state, purchase_return_doc_state as prds, sales_return_transition as srt
    grn_state.check(["review"], "counting")
    for frm, to in ((["closed"], "counting"), (["cancelled"], "review"), (["draft"], "closed")):
        with pytest.raises(ValueError):
            grn_state.check(frm, to)
    assert prds.TRANSITIONS["reverse"]["from"] == ("approved",)
    with pytest.raises(ValueError):
        prds.assert_can({"status": "rejected", "number": "X"}, "approve")
    rid = f"sret_fx6_{uuid.uuid4().hex[:8]}"
    DB.sales_returns.insert_one({"id": rid, "number": f"SRET-FX6-{TAG}", "status": "pending_approval", "notes": NOTE,
                                 "items": [], "entity_id": KSC})
    with pytest.raises(ValueError):                                      # pending_approval → inspected tidak sah
        run(srt.transition(rid, "pending_approval", "inspected", actor_name="Uji"))
    assert run(srt.transition(rid, "draft", "pending_approval", actor_name="Uji")) is None   # CAS kalah (status lain)
    doc = run(srt.transition(rid, "pending_approval", "approved", actor_name="Uji", action="approve"))
    assert doc["status"] == "approved" and doc["status_history"][-1]["user"] == "Uji"
