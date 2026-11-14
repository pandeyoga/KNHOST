#!/usr/bin/env python3
"""KP-T4 — tulis baris bawaan tabel kebijakan persetujuan (`approval_policies`) dan izin setujui yang setara hari ini.

    python scripts/migrate_kpt4_kebijakan_persetujuan.py            # bawaan: hanya lapor, tidak menulis apa pun
    python scripts/migrate_kpt4_kebijakan_persetujuan.py --apply    # tulis

Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`). Menjalankan `--apply` di DATA NYATA =
titik henti H3 (keputusan pemilik). Argumen tak dikenal → keluar 2 sebelum menyentuh database.

Langkah (idempoten; tidak ada yang dihapus; jenis × PT yang sudah punya baris dilewati):
1–3. `services/approval_policy_service.default_rows_for` untuk grup dan tiap PT: `approval_rules` aktif (SO/PO/PR,
     peran = semua peran berperingkat ≥ peran aturan), `approval.extra_levels` PO (jenjang 2, 3, …), daftar peran di
     kode dan kunci registry — dengan nilai efektif tiap PT. Baris PT ditulis hanya bila berbeda dari baris grup.
4.   Izin (K-47): peran yang tercantum di baris PO / tagihan pemasok (termasuk kampanye) / voucher biaya masuk tetapi
     belum memegang `approve` / `reject` sumber daya itu diberi izinnya (dulu pintu itu hanya memeriksa peringkat).
5.   Tujuh belas kunci registry yang isinya pindah sudah ditandai "tidak dipakai" di katalog (kode); di sini nilainya
     hanya dilaporkan.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

#: Jenis dokumen yang pintunya dulu TANPA pemeriksaan izin (PR-05) → izin yang diberikan (butir 4).
JENIS_IZIN_BARU: Dict[str, str] = {"purchase_order": "purchase_order", "purchase_order.deviasi_harga": "purchase_order",
                                   "vendor_bill": "vendor_bill", "vendor_bill.kampanye": "vendor_bill",
                                   "landed_cost": "landed_cost"}
AKSI_IZIN_BARU = ("approve", "reject")

#: Butir 5 — kunci yang isinya pindah ke Aturan Persetujuan.
KUNCI_DIPINDAH: Tuple[str, ...] = (
    "approval.extra_levels", "approval.po_custom_direksi_min", "approval.matrix_enforcement", "approval.matrix_scope",
    "approval.matrix_effective_from", "amendment.approver_role", "amendment.admin_approval_above",
    "antar_entitas.approval_role", "antar_entitas.high_value_approval_role", "antar_entitas.approval_threshold_rupiah",
    "contra_bon.approval_role", "contra_bon.high_value_approval_role", "contra_bon.approval_threshold_rupiah",
    "payment.variance_writeoff_approver_role", "rnd.spec_approval_roles", "rnd.sample_decision_roles",
    "makloon.claim_approval_roles",
)
ALASAN = "Migrasi KP-T4 — baris bawaan setara keputusan sebelum Aturan Persetujuan satu tabel."


def _sig(rows: List[Dict[str, Any]]) -> List[tuple]:
    return sorted((int(r["level"]), r.get("label") or "", float(r.get("min_amount") or 0),
                   (None if r.get("max_amount") is None else float(r["max_amount"])),
                   tuple(r.get("roles") or []), bool(r.get("any_holder"))) for r in rows)


async def rencana() -> Dict[str, Any]:
    """Apa yang AKAN ditulis (tanpa menulis): baris per (jenis, PT), izin per peran, peringatan, nilai kunci lama."""
    from approval_kinds import APPROVAL_KINDS
    from db import db
    from services import approval_policy_service as aps
    from services.config_resolver import value_of
    from services.custom_role_service import sync_registry

    await sync_registry()   # peran kustom ikut dihitung di "semua peran berperingkat ≥ …"
    entitas = [e["id"] for e in await db.business_entities.find({}, {"_id": 0, "id": 1}).sort("id", 1).to_list(None)]
    ada: Dict[str, set] = {}
    async for r in db[aps.COLL].find({}, {"_id": 0, "doc_kind": 1, "entity_id": 1}):
        ada.setdefault(r["doc_kind"], set()).add(r.get("entity_id") or "all")
    baris: List[Dict[str, Any]] = []
    dilewati: List[Dict[str, str]] = []
    for k in APPROVAL_KINDS:
        grp = await aps.default_rows_for(k, "all")
        if "all" in ada.get(k, set()):
            dilewati.append({"doc_kind": k, "entity_id": "all"})
        else:
            baris.extend(grp)
        for ent in entitas:
            if ent in ada.get(k, set()):
                dilewati.append({"doc_kind": k, "entity_id": ent})
                continue
            pt = await aps.default_rows_for(k, ent)
            if _sig(pt) != _sig(grp):
                baris.extend(pt)

    # Butir 4 — izin setara akses lewat peringkat hari ini.
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1}) or {}
    matrix = rec.get("matrix") or {}
    berlaku = list(baris)
    async for r in db[aps.COLL].find({"doc_kind": {"$in": list(JENIS_IZIN_BARU)}, "active": True}, {"_id": 0}):
        berlaku.append(r)
    izin: Dict[str, Dict[str, List[str]]] = {}
    for r in berlaku:
        res = JENIS_IZIN_BARU.get(r["doc_kind"])
        if not res or r.get("any_holder"):
            continue
        for role in r.get("roles") or []:
            punya = (matrix.get(role) or {}).get(res) or []
            kurang = [a for a in AKSI_IZIN_BARU if a not in punya and "*" not in punya]
            if kurang and rec:
                cur = izin.setdefault(role, {}).setdefault(res, [])
                cur.extend(a for a in kurang if a not in cur)

    peringatan: List[str] = []
    for ent in ["all", *entitas]:
        if not await aps._matrix_enforced(ent):   # noqa: SLF001
            peringatan.append(f"{ent}: matriks divisi tidak ditegakkan penuh (mode/cakupan) — baris PR, ACC desain, "
                              "ACC sample, pesanan khusus dihitung tanpa irisan matriks.")
    from services.config_service import get_effective_settings
    for ent in ["all", *entitas]:
        extra = ((((await get_effective_settings(None if ent == "all" else ent)).get("approval") or {})
                  .get("extra_levels")) or {})
        for dt in ("sales_order", "purchase_requisition"):
            if extra.get(dt):
                peringatan.append(f"{ent}: jenjang tambahan {dt} tidak pernah dipakai mesin — tidak dipindah.")
        mins = [float((x or {}).get("min_amount") or 0) for x in (extra.get("purchase_order") or [])
                if isinstance(x, dict) and (x.get("role") or "").strip()]
        if mins != sorted(mins):
            peringatan.append(f"{ent}: jenjang tambahan PO tidak urut nominal — nomor jenjang mengikuti urutan baris.")
    for r in baris:
        if r["doc_kind"] in ("rnd_spec", "rnd_sample", "makloon_claim") and not r["roles"] and not r["any_holder"]:
            peringatan.append(f"{r['entity_id']}: {r['doc_kind']} tanpa peran (irisan daftar kosong) — hari ini tidak "
                              "ada yang bisa memutus; baris ditulis kosong, atur di layar.")
    kunci = {}
    for key in KUNCI_DIPINDAH:
        kunci[key] = {"all": await value_of(key, {"entity_id": ""})}
        for ent in entitas:
            v = await value_of(key, {"entity_id": ent})
            if v != kunci[key]["all"]:
                kunci[key][ent] = v
    return {"baris": baris, "dilewati": dilewati, "izin": izin, "peringatan": peringatan, "kunci": kunci,
            "entitas": entitas}


async def jalankan(tulis: bool = False, aktor: str = "migrasi KP-T4") -> Dict[str, Any]:
    from core_utils import new_id, now_iso
    from db import db
    from services import approval_policy_service as aps

    hasil = await rencana()
    ditulis = {"baris": 0, "izin": 0}
    if tulis:
        now = now_iso()
        docs = [{**r, "id": new_id("appol"), "source": "migrasi", "version": 1, "reason": ALASAN,
                 "created_at": now, "created_by": aktor, "updated_at": now, "updated_by": aktor}
                for r in hasil["baris"]]
        if docs:
            await db[aps.COLL].insert_many([dict(d) for d in docs])
        ditulis["baris"] = len(docs)
        if hasil["izin"]:
            rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1}) or {}
            matrix = rec.get("matrix") or {}
            for role, mods in hasil["izin"].items():
                perms = matrix.setdefault(role, {})
                for res, acts in mods.items():
                    cur = list(perms.get(res) or [])
                    tambah = [a for a in acts if a not in cur]
                    perms[res] = cur + tambah
                    ditulis["izin"] += len(tambah)
            await db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix": matrix, "updated_at": now}})
    hasil["ditulis"] = ditulis
    hasil["mode"] = "tulis" if tulis else "lapor"
    return hasil


def _cetak(hasil: Dict[str, Any]) -> None:
    from collections import Counter
    from services.approval_policy_service import role_label
    print(f"== KP-T4 Aturan Persetujuan satu tabel — mode {hasil['mode']} ==")
    per = Counter((r["doc_kind"], r["entity_id"]) for r in hasil["baris"])
    pt = sorted({e for (_k, e) in per if e != "all"})
    print(f"1–3. Baris yang ditulis: {len(hasil['baris'])} ({len({k for k, _ in per})} jenis; "
          f"baris khusus PT: {', '.join(pt) or 'tidak ada'})")
    for (k, e), n in sorted(per.items()):
        print(f"   - {k} · {e}: {n} baris")
    if hasil["dilewati"]:
        print(f"   Dilewati (sudah punya baris): {len(hasil['dilewati'])}")
    print(f"4. Izin setujui yang diberikan: {sum(len(a) for m in hasil['izin'].values() for a in m.values())}")
    for role, mods in sorted(hasil["izin"].items()):
        for res, acts in sorted(mods.items()):
            print(f"   - {role_label(role)} ({role}) diberi {', '.join(f'{res}.{a}' for a in acts)}")
    print("5. Kunci yang dipindah (nilai efektif; kini 'tidak dipakai'):")
    for key, vals in hasil["kunci"].items():
        print(f"   - {key}: {vals}")
    for p in hasil["peringatan"]:
        print(f"   ! {p}")
    if hasil["mode"] == "tulis":
        print(f"Ditulis: {hasil['ditulis']}")
    else:
        print("(mode lapor; jalankan dengan --apply untuk menulis langkah 1–4)")


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
