"""P20d — GL-01 (saldo awal → posting semua sumber → neraca saldo) · GL-05 (konsolidasi & eliminasi multi-periode).

Usage: cd /app/backend && python ../audit/iterations/2026-10-04-P20-partial-api/repro_p20d.py
Self-clean: rekening/jurnal/kas uji dihapus; saldo kas & nomor dipulihkan.
"""
import json
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, ".")
load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

BASE = "http://localhost:8001/api"
ENT = "ent_ksc"
T = f"TEST_P20D_{uuid.uuid4().hex[:6]}"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NEW = ["bank_accounts", "journal_entries", "cash_transactions", "audit_logs", "notifications", "gl_outbox"]
NOW = datetime.now(timezone.utc)
TODAY = NOW.strftime("%Y-%m-%d")
PREV_END = (NOW.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:400]})


def login(email, ent=ENT):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent})
    return s


def ok(r):
    assert r.status_code == 200, f"{r.request.method} {r.url} → {r.status_code} {r.text[:400]}"
    return r.json()


def tb(s, as_of=None):
    d = ok(s.get(f"{BASE}/gl/trial-balance", params={"as_of": as_of} if as_of else {}))
    return d, {a["code"]: round(float(a["debit"]) - float(a["credit"]), 2) for a in d.get("rows") or d.get("accounts") or []}


def db_net(q):
    tot = defaultdict(float)
    for j in db.journal_entries.find({**q, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        for ln in j["lines"]:
            tot[ln["account_code"]] += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return {k: round(v, 2) for k, v in tot.items() if abs(v) > 0.005}


def gl01(s):
    d0, b0 = tb(s)
    check("GL-01", "neraca saldo KSC seimbang (Σ debit = Σ kredit)", d0["balanced"] and d0["total_debit"] == d0["total_credit"],
          (d0["total_debit"], d0["total_credit"]))
    srcs = defaultdict(int)
    bad = []
    for j in db.journal_entries.find({"entity_id": ENT, "status": {"$ne": "void"}}, {"_id": 0, "number": 1, "source_type": 1, "lines": 1}):
        srcs[j.get("source_type") or "manual"] += 1
        dr = round(sum(float(x.get("debit") or 0) for x in j["lines"]), 2)
        cr = round(sum(float(x.get("credit") or 0) for x in j["lines"]), 2)
        if dr != cr:
            bad.append(j.get("number"))
    check("GL-01", f"setiap jurnal semua sumber ({len(srcs)} jenis) seimbang per dokumen", not bad and len(srcs) >= 5, (dict(srcs), bad[:5]))
    check("GL-01", "neraca saldo API = agregasi langsung baris jurnal DB (tanpa akun hilang/ganda)",
          {k: v for k, v in b0.items() if abs(v) > 0.005} == db_net({"entity_id": ENT}), "")
    acc = ok(s.post(f"{BASE}/bank-accounts", json={"name": f"Bank {T}", "account_type": "bank", "bank_name": "BCA",
                                                   "account_number": T[-6:], "opening_balance": 1000000}))
    _, b1 = tb(s)
    dl = {k: round(b1.get(k, 0) - b0.get(k, 0), 2) for k in set(b0) | set(b1) if abs(b1.get(k, 0) - b0.get(k, 0)) > 0.005}
    gl_code = acc.get("gl_account_code") or acc.get("account_code") or "1-1100"
    check("GL-01", "saldo awal rekening baru 1.000.000 → TB bertambah tepat Dr kas/bank & Cr 3-2900 (ekuitas saldo awal)",
          sorted(dl.values()) == [-1000000.0, 1000000.0] and dl.get("3-2900") == -1000000.0, (gl_code, dl))
    je = ok(s.post(f"{BASE}/gl/journal", json={"date": TODAY, "description": f"{T} biaya", "lines": [
        {"account_code": "6-1100", "debit": 250000}, {"account_code": "1-1110", "credit": 250000}]}))
    _, b2 = tb(s)
    dl2 = {k: round(b2.get(k, 0) - b1.get(k, 0), 2) for k in set(b1) | set(b2) if abs(b2.get(k, 0) - b1.get(k, 0)) > 0.005}
    check("GL-01", "jurnal manual 250.000 → TB bergeser tepat dua akun, tetap seimbang", dl2 == {"6-1100": 250000.0, "1-1110": -250000.0}
          and tb(s)[0]["balanced"], (je.get("number"), dl2))
    bad_je = s.post(f"{BASE}/gl/journal", json={"date": TODAY, "description": f"{T} timpang", "lines": [
        {"account_code": "6-1100", "debit": 100}, {"account_code": "1-1110", "credit": 90}]})
    check("GL-01", "jurnal timpang ditolak 400, TB tidak berubah", bad_je.status_code == 400 and tb(s)[1] == b2, bad_je.status_code)
    _, bp = tb(s, PREV_END)
    check("GL-01", "TB per akhir bulan lalu tidak memuat posting hari ini (saldo awal & jurnal uji)",
          bp.get("6-1100", 0) == round(db_net({"entity_id": ENT, "date": {"$lte": PREV_END + "T23:59:59.999999+00:00"}}).get("6-1100", 0), 2)
          and abs((b2.get("3-2900", 0) - bp.get("3-2900", 0))) >= 1000000 - 0.01, (bp.get("6-1100"), bp.get("3-2900"), b2.get("3-2900")))
    rec = ok(s.get(f"{BASE}/gl/inventory-reconciliation"))
    check("GL-01", "rekonsiliasi persediaan: GL 1-1300 vs subledger roll terbaca (selisih dilaporkan, tidak error)",
          isinstance(rec, dict) and any(k in rec for k in ("gl_balance", "gl", "rows", "entities", "difference", "drift")), list(rec)[:8])


def gl05(s):
    out = {}
    for label, ao in (("bulan_lalu", PREV_END), ("hari_ini", TODAY)):
        d = ok(s.get(f"{BASE}/finance/consolidation/summary", params={"year": NOW.year, "as_of": ao}))
        out[label] = d
        g, e, c = d["gross"], d["elimination"], d["consolidated"]
        per = {k: round(sum(float(x.get(k) or 0) for x in d["entities"]), 2) for k in ("revenue", "assets", "liabilities", "equity")}
        check("GL-05", f"[{label} {ao}] Σ per-PT = gross; konsolidasi = gross + eliminasi (pendapatan/aset/kewajiban/ekuitas)",
              all(abs(per[k] - float(g[k])) < 1 for k in per)
              and all(abs(float(g[k]) + float(e[k]) - float(c[k])) < 1 for k in ("revenue", "cogs", "assets", "liabilities", "equity")),
              (per, g, e, c))
        check("GL-05", f"[{label}] eliminasi seimbang (Δaset = Δkewajiban + Δekuitas) & neraca konsolidasi balanced",
              abs(float(e["assets"]) - float(e["liabilities"]) - float(e["equity"])) < 1 and d["balanced"], (e, d["balanced"]))
    for e in out["hari_ini"]["entities"]:
        sk = login("admin@kainnusantara.id", e["entity_id"])
        d_, _ = tb(sk)
        check("GL-05", f"buku PT {e['entity_id']}: TB seimbang (eliminasi tidak menyentuh buku PT)", d_["balanced"], (d_["total_debit"], d_["total_credit"]))
    elims = ok(s.get(f"{BASE}/finance/consolidation/eliminations"))
    lst = elims if isinstance(elims, list) else elims.get("items", [])
    check("GL-05", "setiap entri eliminasi seimbang", all(x.get("balanced", True) for x in lst), [(x.get("name"), x.get("balanced")) for x in lst][:5])


def main():
    full = snapshot_stock(["number_sequences", "bank_accounts", "cash_balances"])
    ids = snapshot_new_ids(NEW)
    s = login("admin@kainnusantara.id")
    try:
        for fn in (gl01, gl05):
            try:
                fn(s)
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("RUN", f"eksekusi {fn.__name__}", False, repr(exc)[:300])
    finally:
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


if __name__ == "__main__":
    main()
