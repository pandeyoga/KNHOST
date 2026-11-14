#!/usr/bin/env python3
"""Data rekayasa Meja Finance untuk potret tata letak (TIDAK menyentuh DB).

Masukan: respons asli `GET /api/finance/desk?entity_id=ent_ksc` (finance@) disimpan sebagai desk_real.json.
Keluaran: desk_mockA.json (3 antrean berisi: selisih bayar 3 baris umur 9 hari, uang masuk 7 baris umur 4 hari,
faktur pajak 1 baris) dan desk_mockB.json (semua antrean kosong). Dipakai `potret_meja_finance.js` lewat
MOCK_DESK=<berkas> — Playwright mencegat `/api/finance/desk` dan menjawab dengan berkas ini.

  python3 -I buat_data_rekayasa.py desk_real.json
"""
import copy
import json
import sys

d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "desk_real.json"))
base = next(q for q in d["queues"] if q["rows"])["rows"][0]
CUST = ["Toko Kain Sejahtera", "CV Garmen Soreang Jaya", "PT Busana Prima", "Toko Batik Laras"]


def rows(n, ref_type, prefix, val, age, badge, action):
    out = []
    for i in range(n):
        r = copy.deepcopy(base)
        r.update(ref_type=ref_type, ref_id=f"{prefix}{i}", row_key=f"{prefix}{i}", number=f"KSC/{prefix.upper()}-{i + 1:05d}",
                 title=CUST[i % len(CUST)], subtitle="", value=val * (i + 1), age_days=age - i, badge=badge,
                 action=action, action_kind="open")
        r.pop("order_id", None)
        out.append(r)
    return out


def fill(qs, qid, rs):
    x = qs[qid]
    x.update(rows=rs, count=len(rs), shown=len(rs), total_value=round(sum(r["value"] for r in rs), 2),
             oldest_age_days=max((r["age_days"] for r in rs), default=0))


a = copy.deepcopy(d)
qa = {x["id"]: x for x in a["queues"]}
fill(qa, "selisih_bayar", rows(3, "ar_receipt", "rcp", 125000, 9, "pending", "Putuskan"))
fill(qa, "uang_masuk", rows(7, "customer", "cus", 2500000, 4, "lewat", "Catat kwitansi"))
a["totals"]["open_items"] = sum(x["count"] for x in a["queues"])
json.dump(a, open("desk_mockA.json", "w"))

b = copy.deepcopy(d)
for x in b["queues"]:
    fill({x["id"]: x}, x["id"], [])
b["totals"]["open_items"] = 0
json.dump(b, open("desk_mockB.json", "w"))
print("desk_mockA.json, desk_mockB.json")
