#!/usr/bin/env python3
"""KF-T2 — pindahkan akun rekonsiliasi bank dari Pusat Pengaturan ke Pemetaan Akun.

    python scripts/migrate_kft2_akun_bank.py              # bawaan (= --dry-run): hanya cetak selisih, tidak menulis
    python scripts/migrate_kft2_akun_bank.py --dry-run
    python scripts/migrate_kft2_akun_bank.py --apply      # tulis pemetaan akun

Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`). Menjalankan `--apply` di DATA NYATA =
titik henti H3 (keputusan pemilik), dan harus SEBELUM kode KF-T2 (pembaca baru) dipasang di sana.

Sebelum KF-T2 rekonsiliasi bank membaca tiga kunci Pusat Pengaturan; sesudahnya membaca Pemetaan Akun:

| Kunci lama                    | Kunci pemetaan              | Dipakai jurnal hari ini? |
|-------------------------------|-----------------------------|--------------------------|
| `bank.charge_account_code`    | `kas_bank.beban_bank`       | ya — lawan jurnal "Catat biaya bank" |
| `bank.interest_account_code`  | `kas_bank.pendapatan_bunga` | ya — lawan jurnal "Catat bunga / jasa giro" |
| `bank.holding_account_code`   | `kas_bank.titipan_dana`     | tidak — jurnal titipan memakai akun tetap 2-1950 yang sudah dialihkan Pemetaan Akun; kunci ini hanya tampil di ringkasan titipan |

"Akun jurnal" = akun yang benar-benar tertulis di jurnal, yaitu kode itu SESUDAH pengalihan Pemetaan Akun
(`gl_mapping_service.remap_lines`: kode bawaan sebuah kebutuhan ber-`remap` diganti akun pemetaannya). Untuk lapisan
grup lalu tiap PT: bila akun jurnal hari ini (dari nilai efektif kunci lama) berbeda dari akun jurnal sesudah pembaca
dialihkan (dari kode pemetaan yang berlaku untuk lapisan itu, termasuk rencana lapisan grup), skrip memanggil
`gl_mapping_service.set_mapping(<kunci pemetaan>, <PT atau None>, <akun jurnal hari ini>,
"Pindahan dari Pusat Pengaturan (KF-T2)", aktor sistem)`. Dengan begitu tidak ada akun jurnal yang berubah karena
pengalihan pembaca. Kunci titipan hanya DILAPORKAN bila nilainya berbeda dari pemetaan (tampilan saja). Jalan kedua
tanpa perubahan. Argumen tidak dikenal → keluar 2 sebelum menyentuh basis data.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

ALASAN = "Pindahan dari Pusat Pengaturan (KF-T2)"
AKTOR = {"id": "system", "name": "Sistem (pindahan KF-T2)"}
#: (kunci lama, kunci pemetaan, dipakai jurnal hari ini)
PASANGAN: Tuple[Tuple[str, str, bool], ...] = (
    ("bank.charge_account_code", "kas_bank.beban_bank", True),
    ("bank.interest_account_code", "kas_bank.pendapatan_bunga", True),
    ("bank.holding_account_code", "kas_bank.titipan_dana", False),
)
GRUP = ""


def _nama_lapisan(eid: str) -> str:
    return eid or "grup (semua PT)"


async def rencana() -> Dict[str, Any]:
    """Selisih per (kunci, lapisan) tanpa menulis apa pun. Lapisan grup dihitung lebih dulu; PT memakai rencana grup."""
    from db import db
    from services import config_resolver
    from services import gl_mapping_registry as reg
    from services import gl_mapping_service as svc

    svc.invalidate()
    baris_kini = dict(await svc._rows())               # {(kunci, PT atau ""): dokumen pemetaan}
    rencana_tulis: Dict[Tuple[str, str], str] = {}      # {(kunci, PT atau ""): kode}

    def akun_pemetaan(kunci: str, eid: str, pakai_rencana: bool) -> str:
        for lap in ((eid, GRUP) if eid else (GRUP,)):
            if pakai_rencana and (kunci, lap) in rencana_tulis:
                return rencana_tulis[(kunci, lap)]
            if (kunci, lap) in baris_kini:
                return baris_kini[(kunci, lap)]["account_code"]
        return reg.require(kunci)["default"]

    def akun_jurnal(kode: str, eid: str, pakai_rencana: bool) -> str:
        """Kode yang tertulis di jurnal sesudah `remap_lines` (satu tingkat, sama dengan mesinnya)."""
        k = reg.REMAP_BY_DEFAULT.get(kode)
        return akun_pemetaan(k, eid, pakai_rencana) if k else kode

    entitas = [e["id"] for e in await db.business_entities.find({}, {"_id": 0, "id": 1}).sort("id", 1).to_list(None)]
    selisih: List[Dict[str, Any]] = []
    catatan: List[Dict[str, Any]] = []
    for eid in [GRUP] + entitas:
        for lama, kunci, dipakai_jurnal in PASANGAN:
            nilai = str(await config_resolver.value_of(lama, {"entity_id": eid}) or "").strip()
            pemetaan = akun_pemetaan(kunci, eid, True)
            if not dipakai_jurnal:
                if nilai and nilai != pemetaan:
                    catatan.append({"kunci_lama": lama, "kunci_pemetaan": kunci, "lapisan": eid, "nilai_lama": nilai,
                                    "akun_pemetaan": pemetaan,
                                    "pesan": "hanya tampilan ringkasan titipan; jurnal titipan sudah memakai pemetaan"})
                continue
            hari_ini = akun_jurnal(nilai, eid, False) if nilai else akun_jurnal(reg.require(kunci)["default"], eid, False)
            sesudah = akun_jurnal(pemetaan, eid, True)
            if hari_ini == sesudah:
                continue
            baris = {"kunci_lama": lama, "kunci_pemetaan": kunci, "lapisan": eid, "nilai_lama": nilai,
                     "akun_jurnal_hari_ini": hari_ini, "akun_jurnal_sesudah": sesudah, "pemetaan_kini": pemetaan}
            if pemetaan == hari_ini:
                # Akun pemetaan sendiri adalah kode bawaan kebutuhan lain yang dialihkan lagi — tidak bisa dibetulkan
                # dengan menulis kode yang sama. Dilaporkan untuk ditangani manual.
                catatan.append({**baris, "pesan": "akun pemetaan dialihkan lagi oleh kebutuhan lain; periksa manual"})
                continue
            rencana_tulis[(kunci, eid)] = hari_ini
            selisih.append(baris)
    return {"selisih": selisih, "catatan": catatan, "jumlah_pt": len(entitas)}


async def jalankan(tulis: bool = False) -> Dict[str, Any]:
    from services import gl_mapping_service as svc

    hasil = await rencana()
    ditulis, gagal = 0, []
    if tulis:
        for s in hasil["selisih"]:
            try:
                await svc.set_mapping(s["kunci_pemetaan"], s["lapisan"] or None, s["akun_jurnal_hari_ini"], ALASAN, AKTOR)
                ditulis += 1
            except (KeyError, ValueError) as exc:
                gagal.append({**s, "galat": str(exc)})
    hasil.update(mode="tulis" if tulis else "lapor", ditulis=ditulis, gagal=gagal)
    return hasil


def _cetak(hasil: Dict[str, Any], tulis: Optional[Callable[[str], None]] = None) -> None:
    out = tulis or print
    out(f"== KF-T2 akun rekonsiliasi bank → Pemetaan Akun — mode {hasil['mode']} "
        f"(lapisan grup + {hasil['jumlah_pt']} PT) ==")
    out(f"Selisih akun jurnal: {len(hasil['selisih'])}")
    for s in hasil["selisih"]:
        out(f"  - {s['kunci_lama']} → {s['kunci_pemetaan']} · {_nama_lapisan(s['lapisan'])} · "
            f"hari ini {s['akun_jurnal_hari_ini']}, sesudah pengalihan {s['akun_jurnal_sesudah']} "
            f"→ pemetaan diisi {s['akun_jurnal_hari_ini']}")
    for c in hasil["catatan"]:
        out(f"  ! {c['kunci_lama']} · {_nama_lapisan(c['lapisan'])} · nilai lama {c['nilai_lama'] or '-'}, "
            f"pemetaan {c.get('akun_pemetaan') or c.get('pemetaan_kini')} — {c['pesan']}")
    if hasil["mode"] == "tulis":
        out(f"Ditulis: {hasil['ditulis']} · gagal: {len(hasil['gagal'])}")
        for g in hasil["gagal"]:
            out(f"  x {g['kunci_pemetaan']} · {_nama_lapisan(g['lapisan'])}: {g['galat']}")
    else:
        out("(mode lapor; jalankan dengan --apply untuk menulis)")


def main(argv: List[str]) -> int:
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    asing = [a for a in argv if a not in ("--apply", "--dry-run")]
    if asing or {"--apply", "--dry-run"} <= set(argv):
        print(f"Argumen tidak dikenal atau bertentangan: {' '.join(argv)} "
              "(tanpa argumen / --dry-run untuk lapor, --apply untuk menulis)")
        return 2
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
    _cetak(asyncio.run(jalankan(tulis="--apply" in argv)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
