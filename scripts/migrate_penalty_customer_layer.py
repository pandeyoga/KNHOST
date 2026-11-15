#!/usr/bin/env python3
"""CR-T4 — pindahkan nilai lapisan PELANGGAN lima kunci denda dari Pusat Pengaturan ke profil kredit pelanggan.

Sejak CR-T4 lima kunci denda (`payment.penalty_mode`, `payment.penalty_base`, `payment.penalty_cap_pct`,
`ar.denda_rate_pct_per_month`, `ar.grace_days`) hanya berlapis aturan grup → PT; aturan satu pelanggan dibaca mesin dari
`customer_credit_profiles.penalty_rule` (satu pemilik, `02` D1). Nilai lapisan `customer` yang pernah diisi lewat layar
KF-T5 (kartu pelanggan › Aturan khusus pelanggan ini) tidak lagi dibaca resolver; skrip ini memindahkannya:

* tarif / batas atas / tenggang / dasar → `penalty_rule` profil (pelanggan, PT = `customers.entity_id`) bermode `khusus`;
  unsur yang SUDAH terisi di profil tidak ditimpa (profil = pemilik). Profil belum ada → dibuat (versi 1);
* lapisan itu dikosongkan dengan `config_resolver.clear_layer` (baris nisan append-only — riwayat tetap ada);
* `payment.penalty_mode` per pelanggan:
    - `off` (bebas denda) → `penalty_rule` `bebas` HANYA bila pemilik memberi tanggal berakhir (`--bebas-sampai
      YYYY-MM-DD`; tidak ada bebas selamanya, keputusan unit). Tanpa tanggal: TIDAK dipindah dan TIDAK dikosongkan —
      dilaporkan "menunggu tanggal berakhir" (sementara itu pelanggan ikut aturan PT);
    - `draft` / `auto` → tidak ada padanannya per pelanggan (perlakuan usulan/terbit hanya per PT) → lapisan dikosongkan,
      dilaporkan "dilepas" bersama nilai PT yang kini berlaku.
Idempoten: putaran kedua tidak menemukan lapisan berisi (sudah bernisan) → tanpa perubahan.

Mode:
    python scripts/migrate_penalty_customer_layer.py              # = --dry-run (BACA-SAJA, bawaan)
    python scripts/migrate_penalty_customer_layer.py --dry-run    # rencana pemindahan per pelanggan
    python scripts/migrate_penalty_customer_layer.py --apply [--bebas-sampai 2026-12-31]
    ... --json                                                    # keluaran JSON

Menjalankan skrip ini pada DATA NYATA (juga `--dry-run`) = keputusan pemilik (`docs/blueprint/00_ATURAN_EKSEKUSI.md` §6
H3); di repo hanya disiapkan dan diuji di database tiruan (`backend/tests_mem/test_CRT4_denda_berlapis.py` U16).
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:  # noqa: BLE001
    pass

#: kunci lapisan pelanggan → unsur `penalty_rule`
UNSUR = {"ar.denda_rate_pct_per_month": "rate_pct_per_month", "payment.penalty_cap_pct": "cap_pct",
         "ar.grace_days": "grace_days", "payment.penalty_base": "base"}
KUNCI_MODE = "payment.penalty_mode"
AKTOR = "Sistem (migrasi CR-T4)"
ALASAN = "Dipindahkan ke profil kredit pelanggan (aturan denda, CR-T4)"
ALASAN_BEBAS = "Dipindahkan dari aturan khusus pelanggan (bebas denda)"
_TGL = re.compile(r"^\d{4}-\d{2}-\d{2}$")


async def _lapisan_berisi() -> Dict[str, Dict[str, Any]]:
    """{id pelanggan: {kunci: nilai}} — nilai lapisan `customer` yang BERLAKU sekarang (bukan nisan) untuk lima kunci."""
    from db import db
    from services import config_resolver as resolver
    kunci = [*UNSUR, KUNCI_MODE]
    baris: Dict[tuple, List[Dict[str, Any]]] = {}
    async for r in db[resolver.COLL].find({"key": {"$in": kunci}, "scope_type": "customer"}, {"_id": 0}):
        if r.get("cancelled_at"):
            continue
        baris.setdefault((r["key"], r.get("scope_id") or ""), []).append(r)
    sekarang = datetime.now(timezone.utc)
    out: Dict[str, Dict[str, Any]] = {}
    for (k, cid), rows in baris.items():
        rows.sort(key=lambda r: (str(r.get("effective_from") or ""), str(r.get("created_at") or "")))
        val, _win, _ = resolver._pick_effective(rows, sekarang)   # noqa: SLF001 — aturan pemenang yang sama
        if cid and val is not resolver._MISSING:   # noqa: SLF001
            out.setdefault(cid, {})[k] = val
    return out


def _bersih(unsur: str, v: Any) -> Any:
    if unsur == "base":
        return str(v or "")
    if unsur == "grace_days":
        return int(float(v))
    return float(v)


async def jalankan(tulis: bool = False, bebas_sampai: str = "") -> Dict[str, Any]:
    """Rencana (dan bila `tulis`, pelaksanaan) pemindahan. Jawaban: `dipindah` [{customer_id, name, entity_id,
    changes, mode_sebelum, mode_sesudah, profil_baru}], `menunggu` (bebas denda tanpa tanggal berakhir), `dilepas`
    (mode draf/otomatis per pelanggan), `dilewati` (pelanggan tidak ada / tanpa PT), `nisan` (lapisan dikosongkan)."""
    from core_utils import new_id, now_iso
    from db import db
    from services import config_resolver as resolver
    from services import credit_profile_service as cps
    if bebas_sampai and not _TGL.match(bebas_sampai):
        raise ValueError("--bebas-sampai harus berbentuk TTTT-BB-HH")
    out: Dict[str, Any] = {"mode": "apply" if tulis else "dry-run", "dipindah": [], "menunggu": [], "dilepas": [],
                           "dilewati": [], "nisan": 0}
    for cid, nilai in sorted((await _lapisan_berisi()).items()):
        cust = await db.customers.find_one({"id": cid}, {"_id": 0, "id": 1, "name": 1, "entity_id": 1})
        eid = (cust or {}).get("entity_id") or ""
        if not cust or not eid:
            out["dilewati"].append({"customer_id": cid, "keys": sorted(nilai), "sebab": "pelanggan tidak ada / tanpa PT"})
            continue
        prof = await db[cps.COLL].find_one({"customer_id": cid, "entity_id": eid}, {"_id": 0})
        lama = dict((prof or {}).get("penalty_rule") or {})
        aturan = {"mode": lama.get("mode") or "ikut_pt", "rate_pct_per_month": lama.get("rate_pct_per_month"),
                  "cap_pct": lama.get("cap_pct"), "grace_days": lama.get("grace_days"), "base": lama.get("base") or "",
                  "reason": lama.get("reason") or "", "valid_until": lama.get("valid_until") or ""}
        changes: Dict[str, Any] = {}
        kosongkan: List[str] = []
        for k, unsur in UNSUR.items():
            if k not in nilai:
                continue
            kosongkan.append(k)
            if aturan["mode"] == "bebas" or aturan.get(unsur) not in (None, ""):
                continue   # profil sudah punya aturan untuk unsur ini (pemilik) — lapisan lama hanya dikosongkan
            aturan[unsur] = _bersih(unsur, nilai[k])
            changes[unsur] = aturan[unsur]
        mode_lama = aturan["mode"]
        if changes and aturan["mode"] == "ikut_pt":
            aturan["mode"] = "khusus"
        if KUNCI_MODE in nilai:
            m = str(nilai[KUNCI_MODE] or "")
            if m == "off" and aturan["mode"] != "bebas":
                if bebas_sampai:
                    aturan.update(mode="bebas", reason=ALASAN_BEBAS, valid_until=bebas_sampai)
                    changes["mode"] = "bebas"
                    kosongkan.append(KUNCI_MODE)
                else:
                    out["menunggu"].append({"customer_id": cid, "name": cust.get("name", ""), "entity_id": eid,
                                            "nilai": m, "sebab": "bebas denda perlu tanggal berakhir (--bebas-sampai)"})
            else:
                if m in ("draft", "auto"):
                    pt = await resolver.value_of(KUNCI_MODE, {"entity_id": eid})
                    out["dilepas"].append({"customer_id": cid, "name": cust.get("name", ""), "entity_id": eid,
                                           "nilai": m, "nilai_pt": pt})
                kosongkan.append(KUNCI_MODE)
        if changes:
            out["dipindah"].append({"customer_id": cid, "name": cust.get("name", ""), "entity_id": eid,
                                    "changes": changes, "mode_sebelum": mode_lama, "mode_sesudah": aturan["mode"],
                                    "profil_baru": prof is None})
        if not tulis:
            out["nisan"] += len(kosongkan)
            continue
        if changes:
            jejak = {"updated_at": now_iso(), "updated_by": AKTOR, "updated_by_id": "", "last_request_id": ""}
            if prof:
                res = await db[cps.COLL].update_one(
                    {"customer_id": cid, "entity_id": eid, "version": int(prof.get("version") or 0)},
                    {"$set": {"penalty_rule": aturan, **jejak}, "$inc": {"version": 1}})
                if not res.matched_count:   # profil berubah bersamaan (pengajuan diputus) — ulangi skrip
                    out["dilewati"].append({"customer_id": cid, "keys": sorted(nilai), "sebab": "profil berubah"})
                    continue
            else:
                from pymongo.errors import DuplicateKeyError
                doc = {"id": new_id("ccp"), "customer_id": cid, "entity_id": eid, **cps.DASAR, "penalty_rule": aturan,
                       **jejak, "version": 1, "created_at": now_iso()}
                try:
                    await db[cps.COLL].insert_one(doc)
                except DuplicateKeyError:
                    out["dilewati"].append({"customer_id": cid, "keys": sorted(nilai), "sebab": "profil lahir bersamaan"})
                    continue
        for k in kosongkan:
            await resolver.clear_layer(k, scope_type="customer", scope_id=cid, actor=AKTOR, reason=ALASAN)
            out["nisan"] += 1
    return out


async def main() -> int:
    tulis = "--apply" in sys.argv
    if tulis and "--dry-run" in sys.argv:
        print("Pilih salah satu: --dry-run atau --apply.")
        return 2
    sampai = ""
    if "--bebas-sampai" in sys.argv:
        i = sys.argv.index("--bebas-sampai")
        sampai = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
    out = await jalankan(tulis=tulis, bebas_sampai=sampai)
    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
        return 0
    print(f"Aturan denda lapisan pelanggan ({out['mode']}): {len(out['dipindah'])} pelanggan dipindah ke profil kredit · "
          f"{out['nisan']} lapisan {'dikosongkan' if tulis else 'akan dikosongkan'}")
    for r in out["dipindah"]:
        print(f"  {r['name'] or r['customer_id']} [{r['entity_id']}]: {r['changes']} "
              f"({r['mode_sebelum']} → {r['mode_sesudah']}{', profil baru' if r['profil_baru'] else ''})")
    for r in out["menunggu"]:
        print(f"  MENUNGGU {r['name'] or r['customer_id']} [{r['entity_id']}]: {r['sebab']}")
    for r in out["dilepas"]:
        print(f"  DILEPAS {r['name'] or r['customer_id']} [{r['entity_id']}]: perlakuan '{r['nilai']}' per pelanggan "
              f"tidak ada lagi — kini ikut PT ('{r['nilai_pt']}')")
    for r in out["dilewati"]:
        print(f"  DILEWATI {r['customer_id']}: {r['sebab']} ({', '.join(r['keys'])})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
