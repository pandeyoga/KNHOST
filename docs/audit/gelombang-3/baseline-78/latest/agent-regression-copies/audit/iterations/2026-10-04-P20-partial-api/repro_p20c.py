"""P20c — SALE-05 (retur jual: nilai/pajak mengikuti baris & faktur SO asal, piutang SO = GL, reversal bersih) ·
APAR-05 (jurnal nota kredit gagal → status gagal terlihat, settle ulang melanjutkan tanpa ganda) ·
APAR-02 (kwitansi AR: alokasi + kelebihan → deposit, deposit dipakai, void memulihkan semuanya).

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-04-P20-partial-api/repro_p20c.py
Self-clean: SO/pelanggan/saldo/akun GL dipulihkan; dokumen/jurnal/kas/roll baru dihapus.
"""
import json
import os
import sys
import uuid
from collections import defaultdict

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, ".")
load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

BASE = "http://127.0.0.1:8009/api"
ENT = "ent_ksc"
SO = "so_001"
T = f"TEST_P20C_{uuid.uuid4().hex[:6]}"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NEW = ["sales_returns", "credit_notes", "journal_entries", "cash_transactions", "inventory_rolls", "inventory_movements",
       "inventory_lots", "audit_logs", "notifications", "doc_refs", "ar_receipts", "saga_locks", "posting_failures",
       "gl_outbox", "store_credit_ledger", "timeline_events", "return_inspections", "qc_inspections"]
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:400]})


def login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT})
    return s


def ok(r):
    assert r.status_code == 200, f"{r.request.method} {r.url} → {r.status_code} {r.text[:400]}"
    return r.json()


def net(q):
    tot = defaultdict(float)
    for j in db.journal_entries.find({**q, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        for ln in j["lines"]:
            tot[ln["account_code"]] += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return {k: round(v, 2) for k, v in tot.items() if abs(v) > 0.005}


def outstanding(oid=SO):
    o = db.sales_orders.find_one({"id": oid}, {"_id": 0})
    return round(float(o["grand_total"]) - sum(float(p.get("amount") or 0) for p in o.get("payments") or []), 2)


def sale05_apar05(s):
    so = db.sales_orders.find_one({"id": SO}, {"_id": 0})
    line = next(i for i in so["items"] if i["product_id"] == "prod_batik_mega")
    unit_net = float(line.get("line_total") or line["price"] * line["quantity"]) / float(line.get("base_quantity") or line["quantity"])
    frac = float(so["ppn_amount"]) / (float(so["grand_total"]) - float(so["ppn_amount"]))
    exp_net = round(5 * unit_net, 2)
    exp_ppn = round(exp_net * frac, 2)
    o0 = outstanding()
    r = ok(s.post(f"{BASE}/sales-returns", json={"order_id": SO, "submit_now": True, "notes": T,
                                                 "items": [{"product_id": "prod_batik_mega", "quantity_returned": 5, "unit": "yard",
                                                            "reason": "cacat", "condition": "ok"}]}))
    rid = r["id"]
    ok(s.post(f"{BASE}/sales-returns/{rid}/approve", json={"notes": T}))
    ok(s.post(f"{BASE}/sales-returns/{rid}/inspect/start"))
    ok(s.post(f"{BASE}/sales-returns/{rid}/inspect/complete", json={"inspections": [{"index": 0, "condition": "ok", "accepted_qty": 5}]}))
    db.gl_accounts.update_many({"code": "4-1000"}, {"$set": {"is_active": False}})
    st1 = s.post(f"{BASE}/sales-returns/{rid}/settle", json={"outcome": "refund", "notes": T})
    ret = db.sales_returns.find_one({"id": rid}, {"_id": 0})
    cn = db.credit_notes.find_one({"return_id": rid}, {"_id": 0}) or {}
    check("APAR-05", "jurnal nota kredit gagal (akun 4-1000 nonaktif) → retur & CN ber-gl_status 'failed' + pesan, tanpa jurnal",
          st1.status_code == 200 and ret.get("gl_status") == "failed" and cn.get("gl_status") == "failed" and "4-1000" in (ret.get("gl_error") or "")
          and not net({"source_type": "sales_return", "source_id": rid}), (st1.status_code, ret.get("status"), ret.get("gl_status"), ret.get("gl_error")))
    check("SALE-05", "nota kredit dari baris SO asli: harga neto per yd, PPN = rasio faktur SO asal, gross = net + PPN",
          round(cn.get("net_amount", 0), 2) == exp_net and round(cn.get("ppn_amount", 0), 2) == exp_ppn
          and round(cn.get("gross_amount", 0), 2) == round(exp_net + exp_ppn, 2) and cn["lines"][0]["unit_price"] == round(unit_net, 4)
          and cn.get("order_id") == SO and cn.get("settlement") == "ar",
          (cn.get("net_amount"), exp_net, cn.get("ppn_amount"), exp_ppn, cn.get("settlement"), (cn.get("lines") or [{}])[0].get("unit_price")))
    gross = round(exp_net + exp_ppn, 2)
    check("SALE-05", "pengurang piutang: sisa tagihan SO turun tepat sebesar nota kredit (subledger), tercatat sebagai baris 'credit_note'",
          round(o0 - outstanding(), 2) == gross and any(p.get("method") == "credit_note" and p.get("receipt_id") == cn.get("id")
                                                       for p in db.sales_orders.find_one({"id": SO})["payments"]), (o0, outstanding(), gross))
    rolls = list(db.inventory_rolls.find({"return_id": rid}, {"_id": 0, "status": 1, "length_remaining": 1}))
    check("SALE-05", "barang retur masuk karantina 5 (sekali)", round(sum(float(x["length_remaining"]) for x in rolls), 2) == 5
          and all(x["status"] == "quarantine" for x in rolls), rolls)
    db.gl_accounts.update_many({"code": "4-1000"}, {"$set": {"is_active": True}})
    st2 = s.post(f"{BASE}/sales-returns/{rid}/settle", json={"outcome": "refund", "notes": T})
    st3 = s.post(f"{BASE}/sales-returns/{rid}/settle", json={"outcome": "refund", "notes": T})
    ret = db.sales_returns.find_one({"id": rid}, {"_id": 0})
    n = net({"source_type": "sales_return", "source_id": rid})
    njes = db.journal_entries.count_documents({"source_type": "sales_return", "source_id": rid, "status": {"$ne": "void"}})
    check("APAR-05", "settle ulang sesudah akun aktif → gl_status posted, tepat 1 jurnal (settle ke-3 tidak menggandakan)",
          st2.status_code == st3.status_code == 200 and ret.get("gl_status") == "posted" and njes == 1
          and db.credit_notes.count_documents({"return_id": rid}) == 1, (st2.status_code, ret.get("gl_status"), njes))
    check("SALE-05", "jurnal: Dr 4-1000 net, Dr 2-1200 PPN, Cr 1-1200 gross; piutang GL turun = subledger; stok & HPP dibalik seimbang",
          n.get("4-1000") == exp_net and n.get("2-1200") == exp_ppn and n.get("1-1200") == -gross
          and round(n.get("1-1300", 0) + n.get("5-1000", 0), 2) == 0 and round(-n["1-1200"], 2) == round(o0 - outstanding(), 2),
          n)
    check("SALE-05", "roll tidak bertambah karena settle ulang", db.inventory_rolls.count_documents({"return_id": rid}) == len(rolls), "")
    rv = s.post(f"{BASE}/sales-returns/{rid}/reverse", json={"notes": f"{T} salah retur", "reason": f"{T} salah retur"})
    ret = db.sales_returns.find_one({"id": rid}, {"_id": 0})
    check("SALE-05", "reversal: retur cancelled, CN void, net jurnal 0, roll retur dihapus, sisa tagihan SO pulih",
          rv.status_code == 200 and ret["status"] == "cancelled" and db.credit_notes.find_one({"return_id": rid})["status"] == "void"
          and not net({"source_id": rid}) and db.inventory_rolls.count_documents({"return_id": rid}) == 0 and outstanding() == o0,
          (rv.status_code, rv.text[:120], ret["status"], net({"source_id": rid}), outstanding(), o0))


def apar02(s):
    so = db.sales_orders.find_one({"id": SO}, {"_id": 0})
    cust = so["customer_id"]
    o0, dep0 = outstanding(), round(float(db.customers.find_one({"id": cust}).get("deposit_balance") or 0), 2)
    r = s.post(f"{BASE}/ar-receipts", json={"customer_id": cust, "amount": 1000000 + 250000, "method": "transfer", "notes": T,
                                           "allocations": [{"order_id": SO, "amount": 1000000}]})
    rc = r.json()
    dep1 = round(float(db.customers.find_one({"id": cust}).get("deposit_balance") or 0), 2)
    check("APAR-02", "kwitansi 1.250.000 dialokasikan 1.000.000 → sisa tagihan −1.000.000, kelebihan 250.000 masuk deposit",
          r.status_code == 200 and round(o0 - outstanding(), 2) == 1000000 and round(dep1 - dep0, 2) == 250000,
          (r.status_code, r.text[:160], o0, outstanding(), dep0, dep1))
    over = s.post(f"{BASE}/ar-receipts", json={"customer_id": cust, "amount": 0, "use_deposit_amount": dep1 + 1, "method": "transfer",
                                              "notes": T, "allocations": [{"order_id": SO, "amount": dep1 + 1}]})
    check("APAR-02", "pakai deposit melebihi saldo → 400, tanpa mutasi", over.status_code == 400 and round(o0 - outstanding(), 2) == 1000000, over.status_code)
    r2 = s.post(f"{BASE}/ar-receipts", json={"customer_id": cust, "amount": 0, "use_deposit_amount": 250000, "method": "transfer",
                                            "notes": T, "allocations": [{"order_id": SO, "amount": 250000}]})
    dep2 = round(float(db.customers.find_one({"id": cust}).get("deposit_balance") or 0), 2)
    check("APAR-02", "deposit 250.000 dipakai melunasi → sisa tagihan −1.250.000 total, deposit kembali ke awal, tanpa kas baru",
          r2.status_code == 200 and round(o0 - outstanding(), 2) == 1250000 and dep2 == dep0
          and db.cash_transactions.count_documents({"ref_id": r2.json().get("id")}) == 0, (r2.status_code, r2.text[:120], dep2))
    v1 = s.post(f"{BASE}/ar-receipts/{rc.get('id')}/void", json={"reason": f"{T} salah transfer"})
    rc_doc = db.ar_receipts.find_one({"id": rc.get("id")}, {"_id": 0})
    check("APAR-02", "void kwitansi pertama selagi depositnya sudah dipakai → 409 berpesan jelas, TANPA efek parsial (SO, kas, kunci utuh)",
          v1.status_code == 409 and "deposit" in v1.text and round(o0 - outstanding(), 2) == 1250000
          and rc_doc["status"] != "void" and not rc_doc.get("saga_lock")
          and db.cash_transactions.find_one({"ref_id": rc.get("id")})["status"] != "void",
          (v1.status_code, v1.text[:160], outstanding(), rc_doc.get("status"), rc_doc.get("saga_lock")))
    v2 = s.post(f"{BASE}/ar-receipts/{r2.json().get('id')}/void", json={"reason": f"{T} batal pakai deposit"})
    v1b = s.post(f"{BASE}/ar-receipts/{rc.get('id')}/void", json={"reason": f"{T} salah transfer"}) if v1.status_code != 200 else v1
    dep3 = round(float(db.customers.find_one({"id": cust}).get("deposit_balance") or 0), 2)
    cash = db.cash_transactions.find_one({"ref_id": rc.get("id")}, {"_id": 0}) or {}
    check("APAR-02", "void berurutan (pemakaian deposit lalu kwitansi) → sisa tagihan & deposit kembali persis, kas kwitansi void, net jurnal kas 0",
          v2.status_code == 200 and v1b.status_code == 200 and outstanding() == o0 and dep3 == dep0
          and cash.get("status") == "void" and not net({"source_id": cash.get("id", "-")}),
          (v2.status_code, v2.text[:100], v1b.status_code, v1b.text[:100], outstanding(), o0, dep3, cash.get("status")))


def main():
    full = snapshot_stock(["inventory_balances", "number_sequences", "gl_accounts", "sales_orders", "customers", "bank_accounts",
                           "cash_balances", "payment_plans"])
    ids = snapshot_new_ids(NEW)
    s = login("admin@kainnusantara.id")
    try:
        for fn in (sale05_apar05, apar02):
            try:
                fn(s)
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("RUN", f"eksekusi {fn.__name__}", False, repr(exc)[:300])
    finally:
        db.gl_accounts.update_many({"code": "4-1000"}, {"$set": {"is_active": True}})
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


if __name__ == "__main__":
    main()
