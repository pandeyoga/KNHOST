"""Gelombang lanjutan: export terjadwal, LN-083 batas retur, LN-024 bayar antar-PT, LN-100-T02 gudang shared."""
import asyncio
import os
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
T = uuid.uuid4().hex[:6]
CST = "ent_89cbf7444def"


def _login(email, pw="demo1234", ent="ent_ksc"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}


ADMIN = _login("admin@kainnusantara.id", "demo12345")
ISO = lambda d: d.isoformat()  # noqa: E731


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_TEST_{T}"}})
    DB.shipments.delete_many({"id": {"$regex": f"^shp_TEST_{T}"}})
    DB.inventory_rolls.delete_many({"id": {"$regex": f"^roll_TEST_{T}"}})
    DB.purchase_orders.delete_many({"id": {"$regex": f"^po_TEST_{T}"}})
    DB.export_templates.delete_many({"name": {"$regex": "^TEST_"}})
    pairs = [d["pair_id"] for d in DB.interco_transactions.find({"notes": f"TEST_{T}"}, {"pair_id": 1})]
    DB.interco_transactions.delete_many({"pair_id": {"$in": pairs}})
    DB.interco_settlements.delete_many({"notes": f"TEST_{T}"})
    DB.journal_entries.delete_many({"source_id": {"$in": pairs}})
    if not DB.interco_transactions.count_documents({}):
        DB.interco_accounts.delete_many({})
        DB.intercompany_eliminations.delete_many({})
        DB.journal_entries.delete_many({"source_type": {"$regex": "^interco"}})
        DB.cash_transactions.delete_many({"notes": {"$regex": f"TEST_{T}"}})
    DB.system_settings.update_one({"scope": "global"}, {"$unset": {"interco_payment": ""}})


# ── Export terjadwal ────────────────────────────────────────────────────────
def test_schedule_period_and_next_run():
    from services.export_schedule import next_run, rolling_period
    assert rolling_period("monthly", date(2026, 10, 18)) == {"date_from": "2026-09-01", "date_to": "2026-09-30"}
    assert rolling_period("weekly", date(2026, 10, 18)) == {"date_from": "2026-10-05", "date_to": "2026-10-11"}
    after = datetime(2026, 10, 18, 10, 0, tzinfo=timezone(timedelta(hours=7)))
    assert next_run({"frequency": "monthly", "day_of_month": 1, "time": "07:00"}, after).startswith("2026-11-01T00:00")
    assert next_run({"frequency": "weekly", "weekday": 0, "time": "07:00"}, after).startswith("2026-10-19T00:00")


def test_schedule_template_runs_with_owner_rights():
    spec = {"dataset": "sales_finance", "columns": ["number", "grand_total"], "date_field": "created_at",
            "date_from": "2020-01-01", "date_to": "2020-01-31"}
    t = requests.post(f"{BASE}/export-center/templates", headers=ADMIN, json={
        "name": f"TEST_sched {T}", "spec": spec, "format": "xlsx",
        "schedule": {"frequency": "monthly", "day_of_month": 1, "time": "07:00", "period": "previous"}}).json()
    assert t["schedule"]["next_run_at"] and t["schedule"]["entity_id"] == "ent_ksc"
    job = requests.post(f"{BASE}/export-center/templates/{t['id']}/schedule/run-now", headers=ADMIN)
    assert job.status_code == 200, job.text
    j = job.json()
    assert j["trigger"] == "manual_schedule" and "2026-09-01" in j["date_text"] or j["date_text"].count("-") >= 4
    DB.export_templates.update_one({"id": t["id"]}, {"$set": {"schedule.next_run_at": "2000-01-01T00:00:00+00:00"}})
    run = requests.post(f"{BASE}/scheduler/jobs/export_schedule_dispatch/run", headers=ADMIN)
    assert run.status_code == 200, run.text
    doc = DB.export_templates.find_one({"id": t["id"]})
    assert doc["last_scheduled_job"] != j["id"]
    assert doc["schedule"]["next_run_at"] > "2026" and doc["last_scheduled_job"]
    for _ in range(30):
        st = DB.export_jobs.find_one({"id": doc["last_scheduled_job"]}, {"status": 1})
        if st and st["status"] == "done":
            break
        time.sleep(1)
    assert DB.notifications.find_one({"ref": doc["last_scheduled_job"], "recipient_user": doc["user_id"]})


def test_schedule_revoked_owner_fails_safely():
    m = _login("manager@kainnusantara.id")
    t = requests.post(f"{BASE}/export-center/templates", headers=m, json={
        "name": f"TEST_sched_m {T}", "spec": {"dataset": "customers", "columns": ["code"]},
        "schedule": {"frequency": "weekly", "weekday": 0, "time": "07:00"}}).json()
    DB.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.manager.data_export": ["view"]}})
    try:
        r = requests.post(f"{BASE}/export-center/templates/{t['id']}/schedule/run-now", headers=m)
        assert r.status_code == 403   # tidak boleh export lagi → ditolak, bukan berjalan dengan hak lama
        DB.export_templates.update_one({"id": t["id"]}, {"$set": {"schedule.next_run_at": "2000-01-01T00:00:00+00:00"}})
        assert requests.post(f"{BASE}/scheduler/jobs/export_schedule_dispatch/run", headers=ADMIN).status_code == 200
        doc = DB.export_templates.find_one({"id": t["id"]})
        assert "izin export" in doc.get("last_schedule_error", "") and not doc.get("last_scheduled_job")
    finally:
        DB.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.manager.data_export": ["view", "export"]}})


# ── LN-083 ──────────────────────────────────────────────────────────────────
def _seed_order(sj_days_ago, rec_days_ago):
    now = datetime.now(timezone.utc)
    so = f"so_TEST_{T}_{sj_days_ago}_{'_'.join(map(str, rec_days_ago))}"
    DB.sales_orders.insert_one({"id": so, "number": f"TEST_SO-{so}", "entity_id": "ent_ksc", "customer_id": "c",
                                "items": [], "created_at": ISO(now - timedelta(days=60))})
    DB.shipments.insert_one({"id": f"shp_TEST_{T}_{so}", "order_id": so, "shipment_no": f"TEST_SJ-{so}",
                             "status": "dispatched", "created_at": ISO(now - timedelta(days=sj_days_ago))})
    po = f"po_TEST_{T}_{so}"
    DB.purchase_orders.insert_one({"id": po, "po_number": f"TEST_PO-{so}", "status": "completed", "entity_id": "ent_ksc",
                                   "last_received_at": ISO(now - timedelta(days=1))})
    for i, d in enumerate(rec_days_ago):
        DB.inventory_rolls.insert_one({"id": f"roll_TEST_{T}_{so}_{i}", "po_id": po, "reserved_ref": {"type": "sales_order", "id": so},
                                       "acquired": {"via": "grn", "date": ISO(now - timedelta(days=d))},
                                       "created_at": ISO(now - timedelta(days=d))})
    return so, po


def _elig(so, **kw):
    q = "&".join(f"{k}={str(v).lower()}" for k, v in kw.items())
    r = requests.get(f"{BASE}/sales-return-policies/eligibility?order_id={so}&{q}", headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()


def test_ln083_t01_customer_independent_of_supplier():
    so, _ = _seed_order(sj_days_ago=5, rec_days_ago=[40])
    e = _elig(so)
    assert e["window_days"] == 21 and e["within_window"] and e["reference_source"]["type"] == "shipment"
    assert e["supplier_linked"]["any_expired"] and not e["blocked"] and e["decision"] != "outside_window"


def test_ln083_t02_supplier_deadline_per_receiving():
    so, po = _seed_order(sj_days_ago=3, rec_days_ago=[30, 10])
    r = requests.get(f"{BASE}/return-policies/supplier-deadlines?po_id={po}", headers=ADMIN).json()
    rows = r["receivings"]
    assert len(rows) == 2 and rows[0]["deadline"] < rows[1]["deadline"]
    assert all(row["window_days"] == 21 for row in rows)


def test_ln083_t03_pending_rules_not_assumed():
    so, _ = _seed_order(sj_days_ago=2, rec_days_ago=[2])
    e = _elig(so, hangtag_missing=True, cut_by_customer=True)
    codes = {p["code"] for p in e["pending_decisions"]}
    assert codes == {"KLR-08", "KLR-09"} and e["decision"] == "pending_decision" and not e["blocked"]
    late, _ = _seed_order(sj_days_ago=30, rec_days_ago=[30])
    assert _elig(late)["decision"] == "outside_window"


# ── LN-024 ──────────────────────────────────────────────────────────────────
def _ict(seller, buyer, qty):
    r = requests.post(f"{BASE}/interco/transactions", headers={**ADMIN, "X-Entity-Id": "all"}, json={
        "seller_entity_id": seller, "buyer_entity_id": buyer, "pricing_mode": "at_cost", "notes": f"TEST_{T}",
        "items": [{"product_id": "prod_batik_mega", "quantity": qty, "unit_price": 10000}], "submit_now": True})
    assert r.status_code == 200, r.text
    d = r.json()
    # Penerimaan fisik lewat Tugas Gudang (alur existing) — di sini disimulasikan: barang diterima, belum dibayar.
    DB.interco_transactions.update_many({"pair_id": d["pair_id"]}, {"$set": {
        "status": "received", "received_at": datetime.now(timezone.utc).isoformat()}})
    return d


def test_ln024_t01_t02_per_transaction_no_netting():
    a = _ict("ent_ksc", CST, 3)       # CST berutang ke Sukacita
    b = _ict(CST, "ent_ksc", 2)       # Sukacita berutang ke CST
    sa = requests.get(f"{BASE}/interco/transactions/{a['seller']['id']}", headers=ADMIN).json()["seller"]
    assert sa["status"] == "received" and float(sa.get("settled_amount") or 0) == 0
    hdr = {**ADMIN, "X-Entity-Id": "all"}
    sch = requests.get(f"{BASE}/interco/payment-schedule", headers=hdr).json()
    nums = {r["number"] for r in sch["rows"]}
    assert a["seller"]["number"] in nums and b["seller"]["number"] in nums and sch["netting"] == "disabled"
    net = requests.post(f"{BASE}/interco/settlements", headers=hdr, json={
        "payer_entity_id": CST, "payee_entity_id": "ent_ksc", "method": "netting", "notes": f"TEST_{T}",
        "transactions": [{"interco_id": a["seller"]["id"]}]})
    assert net.status_code == 400 and "Netting" in net.text
    part = requests.post(f"{BASE}/interco/settlements", headers=hdr, json={
        "payer_entity_id": CST, "payee_entity_id": "ent_ksc", "method": "transfer", "notes": f"TEST_{T}",
        "transactions": [{"interco_id": a["seller"]["id"], "applied_amount": 1000}]})
    assert part.status_code == 400 and "penuh" in part.text
    full = requests.post(f"{BASE}/interco/settlements", headers=hdr, json={
        "payer_entity_id": CST, "payee_entity_id": "ent_ksc", "method": "transfer", "notes": f"TEST_{T}",
        "transactions": [{"interco_id": a["seller"]["id"]}]})
    assert full.status_code == 200, full.text
    assert requests.get(f"{BASE}/interco/transactions/{a['seller']['id']}", headers=ADMIN).json()["seller"]["status"] == "settled"
    sb = requests.get(f"{BASE}/interco/transactions/{b['seller']['id']}", headers=ADMIN).json()["seller"]
    assert float(sb.get("settled_amount") or 0) == 0          # arah berlawanan tidak ikut dihapus


def test_ln024_t03_cutoff_pending_then_configured():
    _ict("ent_ksc", CST, 1)
    hdr = {**ADMIN, "X-Entity-Id": "all"}
    sch = requests.get(f"{BASE}/interco/payment-schedule?payer_entity_id={CST}", headers=hdr).json()
    assert sch["cutoff_status"] == "pending_KLX-03" and all(r["period"] is None for r in sch["rows"])
    DB.system_settings.update_one({"scope": "global"}, {"$set": {"interco_payment": {
        "allow_netting": False, "require_full_payment": True, "cutoff_day": 25, "payment_day": 28, "basis": "receipt"}}})
    sch = requests.get(f"{BASE}/interco/payment-schedule?payer_entity_id={CST}", headers=hdr).json()
    assert sch["cutoff_status"] == "configured" and all(r["period"] for r in sch["rows"])
    from services.interco_service import _period_for
    assert _period_for("2026-10-25", 25, 28) == {"period": "2026-10", "pay_date": "2026-10-28"}
    assert _period_for("2026-10-26", 25, 28) == {"period": "2026-11", "pay_date": "2026-11-28"}


# ── LN-100-T02 ─────────────────────────────────────────────────────────────
def test_ln100_t02_shared_woven_node():
    from services import placement_rules as pr
    wh = DB.warehouses.find_one({"id": "wh_b0a0387806e7"}, {"_id": 0})
    assert wh["sharing_mode"] == "shared"
    wh = {**wh, "zones": [{"id": "z1", "name": "Zona T", "racks": [{"id": "r1", "name": "Rak T", "levels": [
        {"id": "l1", "name": "Tingkat 1", "bins": [{"id": "b1", "code": f"TEST-{T}", "capacity_rolls": 10,
                                                   "rules": {"fabric_types": ["woven"]}}]}]}]}]}
    node = pr.resolve_bin(wh, "b1")

    async def run():
        out = {}
        for owner, fab in (("ent_ksc", "woven"), (CST, "woven"), (CST, "knit")):
            roll = {"id": f"r-{owner}-{fab}", "warehouse_id": wh["id"], "owner_entity_id": owner, "status": "available"}
            res = await pr.evaluate(wh, node, roll, {"fabric_type": fab})
            out[(owner, fab)] = res
        return out
    res = asyncio.run(run())
    assert res[("ent_ksc", "woven")]["ok"] and res[(CST, "woven")]["ok"]
    knit = res[(CST, "knit")]
    assert not knit["ok"] and any("Jenis kain" in b and "woven" in b for b in knit["blocks"])
