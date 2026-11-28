"""Penanda per PT sekali tulis — SATU pembantu untuk saklar "PT ini sudah pindah" (Kas & Bank 1 akun per rekening,
Kas & Bank 4 akun uang muka pemasok, dan pindah saldo berikutnya).

Bentuk data (sama persis dengan penanda Kas & Bank 1 yang sudah ada di data nyata — tidak berubah): satu dokumen
`system_settings{scope: <scope>}`, kunci = id PT, nilai = `{"sejak": <ISO>, "oleh": <nama>}`. Ditulis SEKALI
(`nyalakan`): dibaca dulu, lalu ditulis bersyarat kunci PT itu belum ada; tidak ada jalan mematikannya dan tidak ada
migrasi saat aplikasi menyala.

Balapan dua `nyalakan` pertama untuk scope yang belum punya dokumen bisa melahirkan dua dokumen penanda (database uji
tiruan tidak menguji indeks; indeks unik/migrasi sengaja tidak ditambah — bentuk data KB-1 tetap). Akibatnya ditutup saat
BACA: `aktif_sejak` menggabung semua dokumen scope itu dan yang paling awal berlaku, dan `nyalakan` mengembalikan nilai
gabungan itu — jadi kedua pemenang balapan, dan semua pembaca sesudahnya, melihat satu waktu yang sama. `oleh` dokumen
yang kalah tidak dibaca siapa pun. Penanda PT lain sesudahnya ditulis tanpa upsert ke dokumen yang sudah ada.

Pemakai (pembungkus tipis, API publiknya tetap): `cash_account_mode` (`__kas_per_rekening__`),
`supplier_advance_mode` (`__uang_muka_pemasok_per_pt__`).
"""
import re
from typing import Any, Optional

from core_utils import now_iso
from db import db

_KUNCI_SAH = re.compile(r"^[A-Za-z0-9_\-]+$")


def kunci_sah(entity_id: Any) -> str:
    """Id PT yang aman dipakai sebagai nama kolom dokumen penanda (huruf, angka, `_`, `-`); selain itu ""."""
    eid = str(entity_id or "").strip()
    return eid if eid and _KUNCI_SAH.match(eid) else ""


async def aktif_sejak(scope: str, entity_id: Optional[str]) -> str:
    """Waktu PT `entity_id` dinyalakan pada penanda `scope` (ISO), kosong bila belum. Dokumen penanda kembar digabung;
    yang paling awal berlaku."""
    eid = kunci_sah(entity_id)
    if not eid:
        return ""
    sejak = [d[eid]["sejak"] async for d in db.system_settings.find({"scope": scope}, {"_id": 0, eid: 1})
             if isinstance(d.get(eid), dict) and d[eid].get("sejak")]
    return min(sejak) if sejak else ""


async def aktif(scope: str, entity_id: Optional[str]) -> bool:
    return bool(await aktif_sejak(scope, entity_id))


async def nyalakan(scope: str, entity_id: str, oleh: Any, label: str) -> str:
    """Nyalakan penanda `scope` untuk PT `entity_id` — SEKALI. → `aktif_sejak` PT itu (gabungan, yang paling awal).
    Panggilan berikutnya tidak menulis dan tidak menggeser waktu & pelakunya. `oleh` = nama atau dokumen pengguna;
    `label` = nama penanda di pesan galat ("akun per rekening")."""
    eid = kunci_sah(entity_id)
    if not eid:
        raise ValueError(f"Id PT tidak sah untuk penanda {label}: {entity_id!r}.")
    sejak = await aktif_sejak(scope, eid)
    if sejak:
        return sejak
    nama = (oleh.get("name") if isinstance(oleh, dict) else oleh) or "system"
    nilai = {"sejak": now_iso(), "oleh": str(nama)}
    syarat = {"scope": scope, eid: {"$exists": False}}
    if await db.system_settings.find_one({"scope": scope}, {"_id": 0, "scope": 1}) is None:
        await db.system_settings.update_one(syarat, {"$set": {eid: nilai}}, upsert=True)
    else:   # tanpa upsert: dokumen penanda tetap satu
        await db.system_settings.update_one(syarat, {"$set": {eid: nilai}})
    return await aktif_sejak(scope, eid)
