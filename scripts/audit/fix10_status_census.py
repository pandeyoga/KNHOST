#!/usr/bin/env python3
"""FIX-10 — sensus status (BACA-SAJA) roll, Putaway Order, SPK inspeksi, sesi opname terhadap tabel transisi.

Tujuan: status "liar" di data (di luar kosakata/tabel) DILAPORKAN — tidak diubah diam-diam. Tidak menulis apa pun.

Pakai (kontainer backend, DB dari env MONGO_URL/DB_NAME):
    python scripts/audit/fix10_status_census.py            # ringkasan teks
    python scripts/audit/fix10_status_census.py --json     # keluaran JSON
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from pymongo import MongoClient  # noqa: E402

from services import cycle_count_state as ccs  # noqa: E402
from services import inspection_state as ist  # noqa: E402
from services import putaway_state as pst  # noqa: E402
from services import roll_state as rs  # noqa: E402


def _known(table) -> set:
    out = set()
    for spec in table.values():
        out |= {s for s in spec["from"] if s} | set(spec["to"])
    return out


def census(db) -> dict:
    def count(coll, flt=None):
        return Counter({(d.get("_id") if d.get("_id") is not None else "∅"): d["n"] for d in db[coll].aggregate(
            [{"$match": flt or {}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])})

    groups = {
        "inventory_rolls": (count("inventory_rolls"), set(rs.STATUSES)),
        "putaway_orders": (count("putaway_orders"), _known(pst.TRANSITIONS) | {"cancelled"}),
        "inspections": (count("inspections"), _known(ist.TRANSITIONS)),
        "cycle_count_sessions (opname)": (count("cycle_count_sessions", {"mode": {"$ne": "registration"}}),
                                          _known(ccs.OPNAME)),
        "cycle_count_sessions (pendaftaran awal)": (count("cycle_count_sessions", {"mode": "registration"}),
                                                    _known(ccs.REGISTRATION)),
        "rfid_verify_sessions (opname RFID)": (count("rfid_verify_sessions", {"kind": "cycle_count"}), _known(ccs.RFID)),
    }
    out = {}
    for name, (cnt, known) in groups.items():
        wild = {k: v for k, v in cnt.items() if k not in known}
        out[name] = {"counts": dict(sorted(cnt.items(), key=lambda x: -x[1])), "wild": wild}
    out["inventory_rolls"]["registry_unused_present"] = {
        s: out["inventory_rolls"]["counts"].get(s, 0) for s in rs.REGISTRY_UNUSED}
    out["inventory_rolls"]["never_written_buckets"] = {
        s: out["inventory_rolls"]["counts"].get(s, 0) for s in ("picked", "packed", "in_transit_inbound",
                                                               "in_transit_intercompany")}
    return out


def main() -> int:
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
    res = census(db)
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
        return 0
    for name, r in res.items():
        print(f"== {name}")
        print("   status: " + ", ".join(f"{k} {v}" for k, v in r["counts"].items()))
        print("   LIAR (di luar tabel): " + (", ".join(f"{k} {v}" for k, v in r["wild"].items()) or "tidak ada"))
        for extra in ("registry_unused_present", "never_written_buckets"):
            if extra in r:
                print(f"   {extra}: {r[extra]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
