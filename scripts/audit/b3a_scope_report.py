#!/usr/bin/env python3
"""B3a — ringkas hasil GET cakupan per akun (keluaran b3a_api_fetch.py): jumlah baris, gudang & PT yang terlihat."""
import json
import os
import sys
from collections import Counter

api = sys.argv[1]
WH = {"wh_jakarta": "JKT", "wh_adc8726d019e": "RCM-WOV", "wh_fe25df27918e": "RCM-KNT", "wh_09155c408ab2": "RCM-PRT",
      "wh_6cccc13554f8": "RCM-RET", "wh_5ae35dcd8837": "RCM-TRN", "wh_40e831c5bb53": "SRG-01"}
EN = {"ent_ksc": "KSC", "ent_kanda": "KANDA", "ent_82b52ed6ee8b": "CST"}
accts = ["admin", "manager", "wh.admin", "warehouse.rancamalang", "warehouse.soreang", "sales", "sales.kanda"]
names = ["wmstasks", "balances", "rolls", "transfers", "putaway", "grn", "cyclecount", "rfidtags", "printjobs",
         "deliveries", "statusboard", "buckets", "rfidsummary", "myloc"]


def rows_of(body):
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ("items", "orders", "tasks", "tags", "jobs", "deliveries", "rows", "sessions", "data"):
            if isinstance(body.get(k), list):
                return body[k]
    return []


def whs(r):
    out = set()
    for k in ("warehouse_id", "source_warehouse_id", "dest_warehouse_id", "from_warehouse_id", "to_warehouse_id"):
        if r.get(k):
            out.add(WH.get(r[k], r[k][-6:]))
    for w in r.get("by_warehouse") or []:
        out.add(WH.get(w.get("warehouse_id"), str(w.get("warehouse_id"))[-6:]))
    for w in r.get("warehouses") or []:
        if isinstance(w, dict):
            out.add(WH.get(w.get("warehouse_id"), str(w.get("warehouse_id"))[-6:]))
    for e in r.get("by_entity") or []:
        for w in e.get("by_warehouse") or []:
            out.add(WH.get(w.get("warehouse_id"), str(w.get("warehouse_id"))[-6:]))
    return out


def ents(r):
    out = set()
    for k in ("entity_id", "owner_entity_id", "source_entity_id", "dest_entity_id"):
        if r.get(k):
            out.add(EN.get(r[k], r[k][-6:]))
    for e in r.get("by_entity") or []:
        out.add(EN.get(e.get("entity_id"), str(e.get("entity_id"))[-6:]))
    for w in r.get("warehouses") or []:
        if isinstance(w, dict) and w.get("owner_entity_id"):
            out.add(EN.get(w["owner_entity_id"], w["owner_entity_id"][-6:]))
    return out


print("| endpoint | " + " | ".join(accts) + " |")
print("|---|" + "---|" * len(accts))
for n in names:
    cells = []
    for a in accts:
        fn = os.path.join(api, f"{a}__scope_{n}.json")
        if not os.path.exists(fn):
            cells.append("—")
            continue
        d = json.load(open(fn, encoding="utf-8"))
        if d["status"] != 200:
            cells.append(str(d["status"]))
            continue
        b = d["body"]
        if n == "myloc":
            cells.append(f"restricted={b.get('restricted')} whs={','.join(b.get('warehouses') or []) or '-'}")
            continue
        if n == "rfidsummary":
            cells.append(json.dumps({k: b.get(k) for k in list(b)[:3]}, ensure_ascii=False)[:60])
            continue
        rs = rows_of(b)
        W, E = Counter(), Counter()
        for r in rs:
            for w in whs(r):
                W[w] += 1
            for e in ents(r):
                E[e] += 1
        trunc = " (terpotong)" if d.get("x_truncated") == "1" else ""
        cells.append(f"{len(rs)}{trunc}; gudang {'/'.join(sorted(W)) or '-'}; PT {'/'.join(sorted(E)) or '-'}")
    print(f"| `{n}` | " + " | ".join(cells) + " |")
