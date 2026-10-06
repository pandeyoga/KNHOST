"""Audit numbers: compare Mongo-computed expected values vs backend API responses.
Read-only. Entity ent_ksc.
"""
import os, requests, asyncio, json
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/.env")
load_dotenv("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/frontend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ENT = "ent_ksc"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

def login(email, password="demo12345"):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text[:200]}"
    s.headers.update({"X-Entity-Id": ENT})
    return s

def gather_api():
    out = {}
    admin = login("admin@kainnusantara.id")
    sales = login("sales@kainnusantara.id")
    # Admin dashboard
    for ep in [
        "/api/dashboard",
        "/api/home/admin",
        "/api/home/sales",
        "/api/home/manager",
        "/api/home/warehouse",
        "/api/home/finance",
        "/api/sales/kpi",
        "/api/sales/leaderboard",
        "/api/sales-targets",
        "/api/ar/aging",
        "/api/sales-orders?limit=1",
        "/api/purchase-orders?limit=1",
        "/api/purchase-orders/board",
        "/api/vendor-bills?limit=1",
        "/api/cash-transactions/summary",
        "/api/finance/bi",
        "/api/stock/buckets",
        "/api/stock/atp",
        "/api/makloon-orders?limit=1",
        "/api/sales-returns?limit=1",
    ]:
        try:
            r = admin.get(f"{BASE}{ep}", timeout=20)
            out[ep] = {"status": r.status_code, "data": r.json() if r.headers.get("content-type","" ).startswith("application/json") else r.text[:200]}
        except Exception as e:
            out[ep] = {"error": str(e)}
    # Sales desk
    for ep in ["/api/home/sales", "/api/sales/kpi", "/api/sales/leaderboard", "/api/ar/aging"]:
        try:
            r = sales.get(f"{BASE}{ep}", timeout=20)
            out[f"[sales]{ep}"] = {"status": r.status_code, "data": r.json() if r.headers.get("content-type","" ).startswith("application/json") else r.text[:200]}
        except Exception as e:
            out[f"[sales]{ep}"] = {"error": str(e)}
    return out

async def compute_expected():
    cli = AsyncIOMotorClient(MONGO_URL)
    db = cli[DB_NAME]
    tz = timezone(timedelta(hours=7))
    now = datetime.now(tz)
    month_start_local = datetime(now.year, now.month, 1, tzinfo=tz)
    month_start_utc = month_start_local.astimezone(timezone.utc)
    exp = {}
    # SO counts by status (ent_ksc)
    pipe = [{"$match": {"entity_id": ENT}}, {"$group": {"_id": "$status", "n": {"$sum": 1}, "total": {"$sum": {"$ifNull": ["$total_amount", 0]}}}}]
    exp["so_by_status"] = await db.sales_orders.aggregate(pipe).to_list(None)
    # PO counts by status
    exp["po_by_status"] = await db.purchase_orders.aggregate(pipe).to_list(None)
    # Vendor bill totals
    exp["vendor_bills_total"] = await db.vendor_bills.aggregate([{"$match": {"entity_id": ENT}},{"$group":{"_id":"$status","n":{"$sum":1},"total":{"$sum":{"$ifNull":["$total_amount",0]}},"outstanding":{"$sum":{"$ifNull":["$outstanding_amount",0]}}}}]).to_list(None)
    # AR outstanding per customer (invoices unpaid)
    exp["ar_outstanding_by_customer"] = await db.sales_invoices.aggregate([
        {"$match": {"entity_id": ENT}},
        {"$group": {"_id": "$customer_id", "outstanding": {"$sum": {"$ifNull": ["$outstanding_amount", 0]}}}},
        {"$sort": {"outstanding": -1}}, {"$limit": 20}
    ]).to_list(None)
    # Cash accounts balances
    accounts = await db.bank_accounts.find({"entity_id": ENT}, {"_id":0}).to_list(None)
    exp["bank_accounts_count"] = len(accounts)
    exp["bank_accounts"] = [{"id": a.get("id"), "name": a.get("name"), "balance": a.get("balance"), "opening_balance": a.get("opening_balance")} for a in accounts[:5]]
    # Cash tx aggregate per account
    exp["cash_tx_by_account"] = await db.cash_transactions.aggregate([
        {"$match": {"entity_id": ENT}},
        {"$group": {"_id": {"acct": "$bank_account_id", "dir": "$direction"}, "sum": {"$sum": "$amount"}, "n": {"$sum": 1}}}
    ]).to_list(None)
    # Inventory totals
    exp["inventory_rolls_total"] = await db.inventory_rolls.aggregate([
        {"$match": {"entity_id": ENT}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}, "yd": {"$sum": {"$ifNull": ["$length_yd", 0]}}}}
    ]).to_list(None)
    # Monthly SO revenue per sales (this month, Asia/Jakarta)
    exp["monthly_so_per_sales"] = await db.sales_orders.aggregate([
        {"$match": {"entity_id": ENT, "created_at": {"$gte": month_start_utc}, "status": {"$nin": ["cancelled", "draft"]}}},
        {"$group": {"_id": "$sales_person_id", "n": {"$sum": 1}, "total": {"$sum": {"$ifNull": ["$total_amount", 0]}}}}
    ]).to_list(None)
    # sales_targets this month
    period = f"{now.year}-{now.month:02d}"
    exp["sales_targets_period"] = await db.sales_targets.find({"period": period}, {"_id":0}).to_list(None)
    # Makloon orders totals
    exp["makloon_by_status"] = await db.makloon_orders.aggregate([
        {"$match": {"entity_id": ENT}},
        {"$group": {"_id": "$status", "n": {"$sum":1}, "total": {"$sum": {"$ifNull": ["$total_amount", 0]}}}}
    ]).to_list(None)
    # Material reservations active
    exp["material_reservations_active"] = await db.material_reservations.aggregate([
        {"$match": {"entity_id": ENT, "status": "active"}},
        {"$group": {"_id": "$product_id", "qty": {"$sum": "$qty"}}}
    ]).to_list(None)
    cli.close()
    return exp, now.isoformat(), period

async def main():
    exp, now_iso, period = await compute_expected()
    api = gather_api()
    report = {"now": now_iso, "period": period, "expected": exp, "api": api}
    out = "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/test_reports/audit_numbers_dump.json"
    with open(out, "w") as f:
        json.dump(report, f, default=str, indent=2)
    print(f"WROTE {out}")
    # Print key comparisons
    print("\n=== SO BY STATUS (expected) ===")
    for s in exp["so_by_status"]:
        print(" ", s)
    print("\n=== PO BY STATUS (expected) ===")
    for s in exp["po_by_status"]:
        print(" ", s)
    print("\n=== VENDOR BILLS (expected) ===")
    for s in exp["vendor_bills_total"]:
        print(" ", s)
    print("\n=== BANK ACCOUNTS ===")
    print(" count:", exp["bank_accounts_count"])
    for a in exp["bank_accounts"]:
        print(" ", a)
    print("\n=== CASH TX BY ACCT ===")
    for s in exp["cash_tx_by_account"][:10]:
        print(" ", s)
    print("\n=== MONTHLY SO PER SALES ===")
    for s in exp["monthly_so_per_sales"]:
        print(" ", s)
    print("\n=== SALES TARGETS period ===", period)
    for t in exp["sales_targets_period"]:
        print(" ", {k:t.get(k) for k in ["sales_id","period","target_sales_amount","target_collection_amount"]})
    print("\n=== MAKLOON ===")
    for s in exp["makloon_by_status"]:
        print(" ", s)
    print("\n=== API STATUS ===")
    for k,v in api.items():
        print(f" {k}: {v.get('status') or v.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())
