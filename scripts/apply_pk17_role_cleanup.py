#!/usr/bin/env python3
"""PK-17 (IA-02, pola K-47) — samakan izin TERSIMPAN peran Gudang & Admin Gudang dengan menunya.

Unit PK-17 mencabut `vendor_bill`, `landed_cost`, `input_tax` (masing-masing hanya "lihat") dari izin BAWAAN peran
`warehouse` dan `warehouse_admin` (`backend/permissions_config.py`): tidak ada satu pun menu gudang untuknya, tetapi
izin itu membuka nominal tagihan pemasok, landed cost, dan faktur pajak masukan lewat API dan Pusat Export.
Matriks yang SUDAH tersimpan (`permission_settings`, dokumen `id: "default"`) tidak diubah otomatis saat aplikasi
mulai — akses yang ada tidak dicabut diam-diam. Skrip ini yang mencabutnya, sekali, atas keputusan pemilik (H3).

    python scripts/apply_pk17_role_cleanup.py --report    # baca saja: pasangan yang akan dicabut + daftar terkait
    python scripts/apply_pk17_role_cleanup.py --apply     # cabut sekali + jejak audit `permission_cleanup_pk17`

Di kontainer backend (repo = /app): `python /app/scripts/apply_pk17_role_cleanup.py --report`.

Aturan:
  * hanya pasangan yang isinya PERSIS bawaan lama (`["view"]`) yang dicabut; aksi yang sudah diubah Admin dilaporkan
    sebagai "dilewati" (keputusan Admin, bukan bawaan);
  * peran kustom tidak diubah — yang beracuan Gudang/Admin Gudang dan masih memegang pasangan itu hanya dilaporkan;
  * laporan juga memuat peran kustom yang memegang `cash.create` tanpa `cash.configure` (PK-17: membuat/mengubah
    rekening kini butuh `cash.configure`, tidak diberikan otomatis);
  * `--apply` hanya sekali: penanda `system_settings{scope: "__migrations__"}.pk17_role_cleanup`. Pasangan yang
    dikembalikan Admin sesudahnya tidak dicabut lagi.
"""
import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

PERAN = ("warehouse", "warehouse_admin")
SUMBER_DAYA = ("vendor_bill", "landed_cost", "input_tax")
BAWAAN_LAMA = ["view"]
AKSI_AUDIT = "permission_cleanup_pk17"
PENANDA = {"scope": "__migrations__"}
FIELD_PENANDA = "pk17_role_cleanup"
PELAKU = "Sistem (pembersihan izin PK-17)"


async def _penanda(db) -> str:
    doc = await db.system_settings.find_one(PENANDA, {"_id": 0, FIELD_PENANDA: 1}) or {}
    return str(doc.get(FIELD_PENANDA) or "")


async def rencana(db) -> Dict[str, Any]:
    """Apa yang akan dicabut `--apply` dan daftar terkait. Tidak menulis apa pun."""
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1}) or {}
    matrix: Dict[str, Dict[str, List[str]]] = rec.get("matrix") or {}
    diterapkan = await _penanda(db)
    cabut: List[Dict[str, Any]] = []
    dilewati: List[Dict[str, Any]] = []
    for peran in PERAN:
        for res in SUMBER_DAYA:
            acts = list((matrix.get(peran) or {}).get(res) or [])
            if not acts:
                continue
            row = {"role": peran, "resource": res, "actions": acts}
            if not diterapkan and sorted(acts) == BAWAAN_LAMA:
                cabut.append(row)
            else:
                dilewati.append({**row, "alasan": ("dikembalikan Admin sesudah pembersihan" if diterapkan
                                                   else "aksinya sudah diubah Admin (bukan bawaan lama)")})
    customs = await db.custom_roles.find({}, {"_id": 0, "id": 1, "label": 1, "base_role": 1}).to_list(1000)
    kustom_gudang: List[Dict[str, Any]] = []
    kas_tanpa_kelola: List[Dict[str, Any]] = []
    for c in customs:
        perms = matrix.get(c["id"]) or {}
        if c.get("base_role") in PERAN:
            held = [res for res in SUMBER_DAYA if perms.get(res)]
            if held:
                kustom_gudang.append({"id": c["id"], "label": c.get("label", ""), "base_role": c.get("base_role"),
                                      "resources": held})
        cash = perms.get("cash") or []
        if "create" in cash and "configure" not in cash:
            kas_tanpa_kelola.append({"id": c["id"], "label": c.get("label", ""), "base_role": c.get("base_role", "")})
    return {"cabut": cabut, "dilewati": dilewati, "kustom_gudang": kustom_gudang,
            "kas_tanpa_kelola": kas_tanpa_kelola, "diterapkan_pada": diterapkan}


async def terapkan(db) -> Dict[str, Any]:
    """Cabut pasangan `rencana()["cabut"]` sekali; tulis jejak audit dan penanda."""
    from core_utils import now_iso
    from dependencies import audit

    plan = await rencana(db)
    if plan["diterapkan_pada"]:
        return {**plan, "dicabut": [],
                "pesan": f"Sudah diterapkan pada {plan['diterapkan_pada']}; tidak ada yang diubah."}
    unset = {f"matrix.{x['role']}.{x['resource']}": "" for x in plan["cabut"]}
    stamp = now_iso()
    if unset:
        await db.permission_settings.update_one({"id": "default"}, {"$unset": unset, "$set": {"updated_at": stamp}})
        await audit(PELAKU, AKSI_AUDIT, "permission_settings", "default",
                    {"dicabut": plan["cabut"]}, reason="PK-17 — izin bawaan gudang disamakan dengan menunya (IA-02)",
                    before={f"{x['role']}.{x['resource']}": x["actions"] for x in plan["cabut"]},
                    source="scripts/apply_pk17_role_cleanup.py")
    await db.system_settings.update_one(PENANDA, {"$set": {FIELD_PENANDA: stamp}}, upsert=True)
    return {**plan, "dicabut": plan["cabut"], "pesan": f"{len(plan['cabut'])} pasangan dicabut."}


def _label_peran(role: str) -> str:
    try:
        from role_registry import role_label
        return role_label(role)
    except Exception:  # noqa: BLE001 — laporan tetap jalan tanpa registry
        return role


def tulis(plan: Dict[str, Any], apply: bool) -> str:
    baris = [f"PK-17 — pembersihan izin tersimpan peran gudang ({'TERAPKAN' if apply else 'laporan, baca saja'})"]
    if plan.get("diterapkan_pada"):
        baris.append(f"  Sudah diterapkan pada {plan['diterapkan_pada']} (sekali saja).")
    judul = "Pasangan yang dicabut" if apply else "Pasangan yang akan dicabut"
    isi = plan.get("dicabut") if apply else plan["cabut"]
    baris.append(f"{judul}: {len(isi or [])}")
    for x in isi or []:
        baris.append(f"  {x['role']:<16} {x['resource']:<12} {x['actions']}  ({_label_peran(x['role'])})")
    baris.append(f"Dilewati (tidak diubah): {len(plan['dilewati'])}")
    for x in plan["dilewati"]:
        baris.append(f"  {x['role']:<16} {x['resource']:<12} {x['actions']}  — {x['alasan']}")
    baris.append("Peran kustom beracuan Gudang/Admin Gudang yang masih memegang pasangan itu "
                 f"(tidak diubah; putuskan di Peran & Hak Akses): {len(plan['kustom_gudang'])}")
    for x in plan["kustom_gudang"]:
        baris.append(f"  {x['id']:<24} {x['label']} (acuan {x['base_role']}): {', '.join(x['resources'])}")
    baris.append("Peran kustom yang memegang cash.create tanpa cash.configure (tidak diubah; tambahkan "
                 "'Kelola rekening kas & bank' bila perannya memang mengelola rekening): "
                 f"{len(plan['kas_tanpa_kelola'])}")
    for x in plan["kas_tanpa_kelola"]:
        acuan = f" (acuan {x['base_role']})" if x.get("base_role") else ""
        baris.append(f"  {x['id']:<24} {x['label']}{acuan}")
    if not apply:
        baris.append("(mode --report; jalankan --apply untuk mencabut — keputusan pemilik)")
    elif plan.get("pesan"):
        baris.append(plan["pesan"])
    return "\n".join(baris)


async def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true", help="tampilkan pasangan yang akan dicabut, TANPA menulis")
    g.add_argument("--apply", action="store_true", help="cabut sekali dan catat jejak audit")
    args = ap.parse_args(argv)
    from db import db

    plan = await (terapkan(db) if args.apply else rencana(db))
    print(tulis(plan, args.apply))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
