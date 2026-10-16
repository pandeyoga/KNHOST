"""P18f — INV-04: transfer antar-PT disetujui → jurnal at-cost di KEDUA buku (IC-AR=IC-AP, persediaan
keluar=masuk) & kepemilikan roll pindah; DOC-02: ekspor Excel/CSV = sumber + hak akses.

Usage: cd /app/backend && python ../audit/iterations/2026-10-03-P18-partial-coverage/repro_p18f.py
Self-clean: roll/saldo dipulihkan; transfer/jurnal/mutasi baru dihapus.
"""
import asyncio
import csv
import io
import json
import sys
import uuid
from collections import defaultdict

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

T = f"TEST_P18F_{uuid.uuid4().hex[:6]}"
ENT, OTHER = "ent_ksc", "ent_kanda"
results = []
NEW = ["warehouse_transfers", "journal_entries", "inventory_movements", "audit_logs", "notifications", "inventory_lots",
       "roll_cost_history", "interco_transactions", "saga_locks", "gl_outbox"]


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def inv04(c, h, db):
    r0 = await db.inventory_rolls.find_one({"warehouse_id": "wh_jakarta", "owner_entity_id": ENT, "status": "available",
                                            "length_reserved": {"$not": {"$gt": 0}}, "length_remaining": {"$gte": 5}}, {"_id": 0})
    body = {"source_entity_id": ENT, "dest_entity_id": OTHER, "notes": T,
            "items": [{"product_id": r0["product_id"], "quantity": 3, "unit": r0.get("unit", "yard")}]}
    res = await c.post("/api/transfers/inter-company", json=body, headers=h)
    t = res.json() if res.status_code == 200 else {}
    ap = await c.post(f"/api/transfers/{t.get('id')}/approve", json={"approved_by": T}, headers=h)
    doc = await db.warehouse_transfers.find_one({"id": t.get("id")}, {"_id": 0}) or {}
    jes = await db.journal_entries.find({"intercompany_pair_id": f"ict_{t.get('id')}"}, {"_id": 0}).to_list(10)
    by = defaultdict(lambda: defaultdict(float))
    for j in jes:
        for ln in j["lines"]:
            by[j.get("entity_id")][ln["account_code"]] += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    src, dst = by.get(ENT, {}), by.get(OTHER, {})
    moved = await db.inventory_rolls.count_documents({"owner_entity_id": OTHER, "product_id": r0["product_id"],
                                                      "$or": [{"transfer_ref.id": t.get("id")}, {"last_transfer.id": t.get("id")},
                                                              {"acquired.ref_id": t.get("id")}]})
    bal = lambda d: all(abs(sum(v.values())) < 0.01 for v in d.values())  # noqa: E731
    check("INV-04", "approve antar-PT → completed, 2 buku berjurnal seimbang; Persediaan sumber turun = naik di tujuan; IC-AR (1-1250) = IC-AP; roll milik tujuan",
          res.status_code == 200 and ap.status_code == 200 and doc.get("status") == "completed" and len(by) == 2 and bal(by)
          and round(-src.get("1-1300", 0), 2) == round(dst.get("1-1300", 0), 2) > 0
          and round(src.get("1-1250", 0), 2) == round(-sum(v for k, v in dst.items() if k.startswith("2-")), 2) and moved >= 1,
          {"res": (res.status_code, res.text[:80]), "ap": (ap.status_code, ap.text[:100]), "src": dict(src), "dst": dict(dst), "moved": moved})
    again = await c.post(f"/api/transfers/{t.get('id')}/approve", json={"approved_by": T}, headers=h)
    check("INV-04", "approve ulang ditolak & jurnal tidak bertambah (idempoten)", again.status_code >= 400
          and await db.journal_entries.count_documents({"intercompany_pair_id": f"ict_{t.get('id')}"}) == len(jes), (again.status_code, len(jes)))
    tb = {}
    for e in (ENT, OTHER):
        r = await c.get("/api/gl/trial-balance", headers={**h, "X-Entity-Id": e})
        d = r.json() if r.status_code == 200 else {}
        tb[e] = (r.status_code, round(float(d.get("total_debit") or 0) - float(d.get("total_credit") or 0), 2))
    check("INV-04", "neraca saldo kedua PT tetap seimbang sesudah transfer", all(v[0] == 200 and abs(v[1]) < 0.01 for v in tb.values()), tb)


async def doc02(c, h, hd, hf, db):
    js = (await c.get("/api/finance/income-statement", headers=h)).json()
    cs = await c.get("/api/finance/income-statement/export.csv", headers=h)
    rows = list(csv.reader(io.StringIO(cs.text)))
    net = next((r[3] for r in rows if r and r[0] == "Laba Bersih"), None)
    lines = sum(len(s.get("lines", [])) for s in js.get("sections", []))
    data_rows = [r for r in rows if len(r) == 4 and r[1] and r[0] != "Bagian"]
    check("DOC-02", "ekspor CSV Laba-Rugi = sumber JSON (laba bersih & jumlah baris akun sama)",
          cs.status_code == 200 and net is not None and round(float(net), 2) == round(float(js.get("net_income") or 0), 2) and len(data_rows) == lines,
          (cs.status_code, net, js.get("net_income"), len(data_rows), lines))
    bs = (await c.get("/api/finance/balance-sheet", headers=h)).json()
    bcs = await c.get("/api/finance/balance-sheet/export.csv", headers=h)
    check("DOC-02", "ekspor CSV Neraca memuat total aset sumber", bcs.status_code == 200 and
          str(round(float((bs.get("totals") or {}).get("assets") or bs.get("total_assets") or 0), 2)).rstrip("0").rstrip(".") in bcs.text.replace(".0,", ","),
          ((bs.get("totals") or {}).get("assets") or bs.get("total_assets")))
    d1 = await c.get("/api/finance/income-statement/export.csv", headers=hd)
    d2 = await c.get("/api/finance/income-statement/export.csv", params={"entity_id": OTHER}, headers=hf)
    cp = await c.get("/api/customer-prices/export", params={"customer_id": "cust_toko_kain", "entity_id": OTHER}, headers=hf)
    check("DOC-02", "hak akses ekspor: desainer 403; finance KSC-saja minta PT lain 403 (laporan & harga pelanggan)",
          d1.status_code == 403 and d2.status_code == 403 and cp.status_code in (400, 403, 404), (d1.status_code, d2.status_code, cp.status_code))
    xl = await c.get("/api/inspections/export", headers=h)
    check("DOC-02", "ekspor daftar (inspeksi) berhasil dengan tipe unduhan & nama berkas", xl.status_code == 200
          and "attachment" in xl.headers.get("content-disposition", ""), (xl.status_code, xl.headers.get("content-type")))


async def main():
    import httpx
    from db import db
    full = snapshot_stock(["number_sequences", "inventory_rolls", "inventory_balances", "inventory_lots"])
    ids = snapshot_new_ids(NEW)
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=120) as c:
        lg = lambda e: c.post("/api/auth/login", json={"email": e, "password": "demo12345"})  # noqa: E731
        hh = lambda r: {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}  # noqa: E731
        h, hd, hf = hh(await lg("admin@kainnusantara.id")), hh(await lg("designer@kainnusantara.id")), hh(await lg("finance@kainnusantara.id"))
        for fn in (inv04(c, h, db), doc02(c, h, hd, hf, db)):
            try:
                await fn
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("P18F", "eksekusi", False, repr(exc)[:200])
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
