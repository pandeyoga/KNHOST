"""Smoke COMM-04 + LN-042-T03 (self-clean)."""
import os
import sys
import requests
from pymongo import MongoClient

B = os.environ.get("BASE", "http://localhost:8001") + "/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ok_all = True


def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{B}/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    tok = r.json().get("token") or r.json().get("session_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    s.headers["X-Entity-Id"] = "ent_ksc"
    return s


def bal(code):
    tot = 0.0
    for je in db.journal_entries.find({"entity_id": "ent_ksc", "status": {"$ne": "void"}, "lines.account_code": code}):
        for ln in je["lines"]:
            if ln["account_code"] == code:
                tot += ln.get("debit", 0) - ln.get("credit", 0)
    return round(tot, 2)


admin = login("admin@kainnusantara.id", "demo12345")
sales = login("sales@kainnusantara.id", "demo1234")
created = {"camp": None, "costs": [], "prints": []}
try:
    c = admin.post(f"{B}/marketing/campaigns", json={"name": "TEST_COMM04 Kampanye", "budget": 1000000}).json()
    created["camp"] = c["id"]
    b0, k0 = bal("6-4700"), bal("1-1100")
    r = admin.post(f"{B}/marketing/campaigns/{c['id']}/costs", json={"amount": 250000, "description": "Iklan IG", "date": ""})
    check("record cost 200", r.status_code == 200, r.text[:200])
    cost = r.json(); created["costs"].append(cost.get("id"))
    check("beban +250rb & kas -250rb", bal("6-4700") - b0 == 250000 and k0 - bal("1-1100") == 250000)
    s = admin.get(f"{B}/marketing/campaigns/{c['id']}/costs").json()
    check("ringkasan realisasi/sisa", s["realized"] == 250000 and s["remaining"] == 750000, str(s)[:150])
    lst = [x for x in admin.get(f"{B}/marketing/campaigns").json() if x["id"] == c["id"]][0]
    check("list kampanye cost_realized", lst["cost_realized"] == 250000)
    check("sales tidak boleh posting (403)", sales.post(f"{B}/marketing/campaigns/{c['id']}/costs", json={"amount": 1, "description": "xxx"}).status_code == 403)
    check("nominal 0 → 400", admin.post(f"{B}/marketing/campaigns/{c['id']}/costs", json={"amount": 0, "description": "xxx"}).status_code == 400)
    cash = db.cash_transactions.find_one({"id": cost["cash_txn_id"]})
    check("void kas manual ditolak (dokumen asal)", admin.post(f"{B}/cash-transactions/{cash['id']}/void").status_code == 409)
    check("void alasan pendek → 400", admin.post(f"{B}/marketing/campaigns/{c['id']}/costs/{cost['id']}/void", json={"reason": "x"}).status_code == 400)
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(2) as ex:
        res = list(ex.map(lambda _: admin.post(f"{B}/marketing/campaigns/{c['id']}/costs/{cost['id']}/void", json={"reason": "salah input biaya"}).status_code, range(2)))
    check("void bersamaan → satu 200 satu 409", sorted(res) == [200, 409], str(res))
    check("saldo beban & kas kembali", bal("6-4700") == b0 and bal("1-1100") == k0)
    check("pembalik tepat satu", db.journal_entries.count_documents({"source_type": "cash_transaction_void", "source_id": cash["id"]}) == 1)
    check("void ulang → 409", admin.post(f"{B}/marketing/campaigns/{c['id']}/costs/{cost['id']}/void", json={"reason": "ulang lagi"}).status_code == 409)

    # LN-042-T03
    roll = db.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available", "length_remaining": {"$gt": 1}})
    r1 = admin.post(f"{B}/rfid/rolls/{roll['id']}/label-prints", json={}).json()
    db.inventory_rolls.update_one({"id": roll["id"]}, {"$inc": {"length_remaining": -0.25}})
    lk = admin.get(f"{B}/rfid/lookup", params={"code": roll["roll_no"], "record": "false"}).json()
    check("lookup: label basi setelah saldo turun", lk["label"]["label_outdated"] is True and abs(lk["label"]["current_qty"] - (roll["length_remaining"] - 0.25)) < 1e-6, str(lk["label"]))
    r2 = admin.post(f"{B}/rfid/rolls/{roll['id']}/label-prints", json={}).json()
    check("reprint: qty terkini, seq 2, reprint", r2["reprint"] and r2["print_seq"] == r1["print_seq"] + 1 and abs(r2["qty"] - (roll["length_remaining"] - 0.25)) < 1e-6)
    check("reprint: epc sama & roll sama", r2["epc"] == r1["epc"] and r2["roll_id"] == roll["id"])
    h = admin.get(f"{B}/rfid/rolls/{roll['id']}/print-history").json()
    check("histori: label tidak basi lagi, 2+ cetak", h["label_outdated"] is False and h["prints_count"] >= 2)
    check("roll tidak bertambah", db.inventory_rolls.count_documents({"roll_no": roll["roll_no"]}) == 1)
    created["prints"].append(roll["id"])
    db.inventory_rolls.update_one({"id": roll["id"]}, {"$inc": {"length_remaining": 0.25}})
finally:
    if created["camp"]:
        ids = [x["id"] for x in db.mkt_campaign_costs.find({"campaign_id": created["camp"]})]
        cash_ids = [x["cash_txn_id"] for x in db.mkt_campaign_costs.find({"campaign_id": created["camp"]}) if x.get("cash_txn_id")]
        db.journal_entries.delete_many({"source_id": {"$in": cash_ids}})
        db.cash_transactions.delete_many({"id": {"$in": cash_ids}})
        db.mkt_campaign_costs.delete_many({"id": {"$in": ids}})
        db.mkt_campaigns.delete_one({"id": created["camp"]})
    db.roll_label_prints.delete_many({"roll_id": {"$in": created["prints"]}})
print("ALL PASS" if ok_all else "SOME FAIL")
sys.exit(0 if ok_all else 1)
