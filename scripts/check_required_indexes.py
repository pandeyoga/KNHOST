#!/usr/bin/env python3
"""PK-14 — periksa indeks unik keuangan wajib, BACA-SAJA (tidak membuat, menghapus, atau mengubah apa pun).

Untuk tiap butir `backend/indexes.py` `REQUIRED_UNIQUE_INDEXES`: "terpasang" atau selisihnya (tidak ada / tidak unik /
kunci berbeda / ekspresi parsial berbeda), lalu jumlah kelompok data kembar menurut kueri pencarinya. Kode keluar 1
bila ada selisih atau kembar. Dipakai sebelum memasang versi ber-PK-14 pada salinan data nyata (PK-03, H3/H6).

    MONGO_URL=... DB_NAME=... python3 scripts/check_required_indexes.py

Jangan menghapus atau menggabung data kembar sendiri — serahkan keluaran ini kepada pemilik data.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from pymongo import MongoClient  # noqa: E402

from indexes import REQUIRED_UNIQUE_INDEXES, diff_required  # noqa: E402


def _pipeline(it: dict) -> list:
    """Kueri pencari kembar dalam bentuk Python — setara teks `finder` (cocokkan ekspresi parsial, kelompokkan kunci)."""
    group = {k.replace(".", "_"): f"${k}" for k, _ in it["keys"]}
    return [{"$match": it["partial"]}, {"$group": {"_id": group, "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]


def main() -> int:
    url = os.environ.get("MONGO_URL")
    if not url:
        print("MONGO_URL belum diisi.")
        return 2
    db = MongoClient(url, serverSelectionTimeoutMS=10000)[os.environ.get("DB_NAME", "test_database")]
    colls = sorted({it["collection"] for it in REQUIRED_UNIQUE_INDEXES})
    names = set(db.list_collection_names())
    info = {c: (db[c].index_information() if c in names else {}) for c in colls}
    diffs = {(d["collection"], d["name"]): d for d in diff_required(info)}
    buruk = 0
    for it in REQUIRED_UNIQUE_INDEXES:
        kunci = (it["collection"], it["name"])
        kembar = len(list(db[it["collection"]].aggregate(_pipeline(it)))) if it["collection"] in names else 0
        status = diffs[kunci]["problem"] if kunci in diffs else "terpasang"
        print(f"{it['collection']}.{it['name']} ({it['label']}): {status} · {kembar} kelompok kembar")
        if kunci in diffs or kembar:
            buruk += 1
            print(f"  Cari data kembar: {it['finder']}")
    print(f"\n{len(REQUIRED_UNIQUE_INDEXES) - buruk} dari {len(REQUIRED_UNIQUE_INDEXES)} indeks wajib beres.")
    return 1 if buruk else 0


if __name__ == "__main__":
    sys.exit(main())
