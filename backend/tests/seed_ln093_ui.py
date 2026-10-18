"""Data contoh UI LN-093/LN-091-T02: `cd /app/backend && REACT_APP_BACKEND_URL=http://localhost:8001 python tests/seed_ln093_ui.py`."""
import sys

sys.path.insert(0, "/app/backend/tests")
import test_ln091t02_ln093_chain as t  # noqa: E402

t.TAG = "DEMO_LN093"
pair = t.make_interco()
rid = t.make_return(status="refund_settled")
for _ in range(2):
    t.make_roll(rid, t.KSC, pair=pair)
done = {"internal": {"decision": "return_internal", "status": "done", "interco_return_number": "ICR-DEMO"}}
t.make_roll(rid, t.CST, pair=pair, receipt_days=2, disposition=done)
t.make_roll(rid, t.CST, pair=pair, grade="BS", receipt_days=3, disposition=done)
t.make_roll(rid, t.CST, status="quarantine", grade="B", pair=pair, receipt_days=40, disposition=done)
q = t.make_roll(rid, t.KSC, status="quarantine", grade="A", unit_cost=t.PRICE)
r = t.requests.post(f"{t.BASE}/sales-returns/{rid}/quarantine/release", headers=t.H_KSC,
                    json={"decisions": [{"roll_id": q, "action": "release", "grade": "B"}], "notes": "demo"})
print(r.status_code, r.text[:300], "return id:", rid, t.DB.sales_returns.find_one({"id": rid})["number"])
