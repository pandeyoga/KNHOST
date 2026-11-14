#!/usr/bin/env python3
"""KP-T3 — rapikan data Aturan Persetujuan (`approval_rules`) dan laporkan jenjang tambahan ber-peran tak dikenal.

    python scripts/migrate_kpt3_aturan_persetujuan.py            # bawaan: hanya lapor, tidak menulis apa pun
    python scripts/migrate_kpt3_aturan_persetujuan.py --apply    # tulis

Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`). Menjalankan `--apply` di DATA NYATA =
titik henti H3 (keputusan pemilik).

Langkah (idempoten; tidak ada yang dihapus):
1. Aturan ber-`doc_type` `discount` yang belum dipensiunkan → `active: false`,
   `retired_reason: "Jenis aturan tidak dipakai mesin"`.
2. Aturan yang `required_role`-nya tidak kosong dan bukan peran yang dikenal (registry peran + peran kustom) →
   `required_role: "manager"`, `migrated_from_role: <nilai lama>`. Mesin hari ini sudah memperlakukan nilai tak dikenal
   sebagai peringkat Manajer (`role_registry.required_rank`), jadi tidak ada keputusan persetujuan yang berubah.
3. Baris `approval.extra_levels` (grup dan tiap PT, di `system_settings`) yang `role`-nya tidak dikenal hanya
   DILAPORKAN; tidak diubah.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

ALASAN_PENSIUN = "Jenis aturan tidak dipakai mesin"


async def periksa() -> Dict[str, List[Dict[str, Any]]]:
    """Daftar yang akan diubah (langkah 1–2) dan yang hanya dilaporkan (langkah 3)."""
    import role_registry
    from db import db
    from services.custom_role_service import sync_registry

    await sync_registry()   # peran kustom ikut dikenali — aturan yang menunjuk peran kustom TIDAK diubah
    diskon = await db.approval_rules.find(
        {"doc_type": "discount", "retired_reason": {"$exists": False}},
        {"_id": 0, "id": 1, "entity_id": 1, "min_amount": 1, "max_amount": 1, "required_role": 1, "active": 1},
    ).to_list(None)
    peran = []
    async for r in db.approval_rules.find({"required_role": {"$nin": ["", None]}}, {"_id": 0}):
        if not role_registry.is_role(r["required_role"]):
            peran.append({"id": r["id"], "doc_type": r.get("doc_type"), "entity_id": r.get("entity_id"),
                          "required_role": r["required_role"], "active": r.get("active")})
    entitas = {e["id"] for e in await db.business_entities.find({}, {"_id": 0, "id": 1}).to_list(None)}
    jenjang = []
    async for doc in db.system_settings.find({}, {"_id": 0, "scope": 1, "approval": 1}):
        scope = doc.get("scope")
        if scope != "global" and scope not in entitas:
            continue
        extra = ((doc.get("approval") or {}).get("extra_levels") or {})
        if not isinstance(extra, dict):
            continue
        for doc_type, rows in extra.items():
            for n, lv in enumerate(rows if isinstance(rows, list) else [], 1):
                role = str((lv or {}).get("role") or "").strip() if isinstance(lv, dict) else ""
                if role and not role_registry.is_role(role):
                    jenjang.append({"scope": scope, "doc_type": doc_type, "baris": n, "role": role,
                                    "min_amount": lv.get("min_amount")})
    return {"diskon": diskon, "peran_tak_dikenal": peran, "jenjang_tambahan": jenjang}


async def jalankan(tulis: bool = False) -> Dict[str, Any]:
    from core_utils import now_iso
    from db import db

    hasil: Dict[str, Any] = await periksa()
    ditulis = {"diskon": 0, "peran_tak_dikenal": 0}
    if tulis:
        for r in hasil["diskon"]:
            res = await db.approval_rules.update_one(
                {"id": r["id"], "doc_type": "discount", "retired_reason": {"$exists": False}},
                {"$set": {"active": False, "retired_reason": ALASAN_PENSIUN, "updated_at": now_iso()}})
            ditulis["diskon"] += res.modified_count
        for r in hasil["peran_tak_dikenal"]:
            res = await db.approval_rules.update_one(
                {"id": r["id"], "required_role": r["required_role"]},
                {"$set": {"required_role": "manager", "migrated_from_role": r["required_role"],
                          "updated_at": now_iso()}})
            ditulis["peran_tak_dikenal"] += res.modified_count
    hasil["ditulis"] = ditulis
    hasil["mode"] = "tulis" if tulis else "lapor"
    return hasil


def _cetak(hasil: Dict[str, Any]) -> None:
    print(f"== KP-T3 Aturan Persetujuan — mode {hasil['mode']} ==")
    print(f"1. Aturan 'Diskon (%)' yang dipensiunkan: {len(hasil['diskon'])}")
    for r in hasil["diskon"]:
        print(f"   - {r['id']} · PT {r.get('entity_id') or 'all'} · aktif={r.get('active')}")
    print(f"2. Aturan ber-peran tak dikenal → Manajer: {len(hasil['peran_tak_dikenal'])}")
    for r in hasil["peran_tak_dikenal"]:
        print(f"   - {r['id']} · {r.get('doc_type')} · PT {r.get('entity_id') or 'all'} · “{r['required_role']}”")
    print(f"3. Jenjang tambahan ber-peran tak dikenal (hanya dilaporkan): {len(hasil['jenjang_tambahan'])}")
    for r in hasil["jenjang_tambahan"]:
        print(f"   - {r['scope']} · {r['doc_type']} baris {r['baris']} · “{r['role']}”")
    if hasil["mode"] == "tulis":
        print(f"Ditulis: {hasil['ditulis']}")
    else:
        print("(mode lapor; jalankan dengan --apply untuk menulis langkah 1–2)")


def main(argv: List[str]) -> int:
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    asing = [a for a in argv if a != "--apply"]
    if asing:
        print(f"Argumen tidak dikenal: {' '.join(asing)} (pakai tanpa argumen untuk lapor, --apply untuk menulis)")
        return 2
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
    _cetak(asyncio.run(jalankan(tulis="--apply" in argv)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
