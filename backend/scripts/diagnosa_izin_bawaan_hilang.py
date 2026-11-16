#!/usr/bin/env python3
"""DIAGNOSA SAJA (M41, masukan pemilik 16 Nov: "saya admin tapi tidak punya akses" Pusat Export).

Membandingkan matriks izin tersimpan (`permission_settings.matrix`) dengan izin bawaan kode (`DEFAULT_PERMISSIONS`)
per peran bawaan, dan mendaftar pasangan bawaan yang TIDAK ADA di matriks. Untuk tiap pasangan dicek apakah jejak audit
menunjukkan peran itu pernah diubah Admin (`role_access_updated`/`role_access_reset`/…): bila tidak ada, besar
kemungkinan pasangan itu hilang karena cacat garis dasar migrasi izin (diperbaiki M41), bukan dicabut.

TIDAK mengubah data. Admin (peran terkunci) dipulihkan otomatis saat server menyala; peran lain dipulihkan dari layar
Pengaturan › Peran & Hak Akses (ubah peran / "Kembalikan ke bawaan") setelah pemilik memutuskan.

Pakai (di dalam container backend; ikut terpasang di image produksi karena berada di `backend/`):
    python scripts/diagnosa_izin_bawaan_hilang.py [--json]
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))
from permissions_config import DEFAULT_PERMISSIONS  # noqa: E402

AKSI_UBAH_PERAN = ("role_access_updated", "role_access_reset", "role_updated", "custom_role_updated",
                   "role_followed_base", "permission_matrix_updated")


def main() -> int:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rec = db.permission_settings.find_one({"id": "default"}, {"_id": 0}) or {}
    matrix = rec.get("matrix") or {}
    applied = rec.get("defaults_applied") or {}
    hasil = []
    for role, mods in sorted(DEFAULT_PERMISSIONS.items()):
        cur = matrix.get(role) or {}
        hilang = {res: [a for a in acts if a not in (cur.get(res) or []) and "*" not in (cur.get(res) or [])]
                  for res, acts in mods.items()}
        hilang = {k: v for k, v in hilang.items() if v}
        if not hilang:
            continue
        pernah_diubah = db.audit_logs.count_documents({"entity_id": role, "action": {"$in": list(AKSI_UBAH_PERAN)}})
        ditandai = {res: [a for a in acts if a in ((applied.get(role) or {}).get(res) or [])]
                    for res, acts in hilang.items()}
        hasil.append({"peran": role, "hilang": hilang, "ditandai_sudah_diterapkan": {k: v for k, v in ditandai.items() if v},
                      "jejak_ubah_peran_oleh_admin": pernah_diubah})
    if "--json" in sys.argv:
        print(json.dumps(hasil, ensure_ascii=False, indent=2))
        return 0
    if not hasil:
        print("Semua peran bawaan memegang seluruh izin bawaannya.")
        return 0
    for h in hasil:
        print(f"\n== {h['peran']} — {sum(len(v) for v in h['hilang'].values())} izin bawaan tidak ada di matriks"
              f" (jejak ubah peran oleh Admin: {h['jejak_ubah_peran_oleh_admin']})")
        for res, acts in sorted(h["hilang"].items()):
            tanda = " [ditandai sudah diterapkan]" if res in h["ditandai_sudah_diterapkan"] else ""
            print(f"   {res}: {', '.join(acts)}{tanda}")
    print("\nCatatan: 'ditandai sudah diterapkan' tanpa jejak ubah peran = kemungkinan besar cacat migrasi (M41).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
