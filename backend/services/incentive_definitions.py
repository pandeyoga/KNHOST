"""KM-T1 (keputusan K-19, K-20, K-21, K-23) — versi DEFINISI ANGKA insentif per PT (`incentive_definitions`).

Pemilik nilai = Pusat Pengaturan (empat kunci `insentif.*`, `config_catalog_insentif.py`). Koleksi ini hanya-tambah:
setiap kali `current_definition(entity_id)` membaca nilai PT yang berbeda dari versi terakhir PT itu, satu versi baru
disisipkan (`version` naik, `effective_from` = tanggal WIB saat perubahan terbaca). Lembar insentif (KM-T3) memotret
versi ini, sehingga perubahan definisi tidak mengubah lembar yang sudah disahkan (`02_STANDAR.md` §5 D3).

Bentuk dokumen: `{id: "idef_…", entity_id, version, effective_from, dasar_omzet, isi_pencairan, pemilik_angka,
harga_acuan, recorded_at}`; indeks unik (`entity_id`, `version`) — dua pembaca bersamaan menghasilkan satu versi.
"""
from __future__ import annotations

from typing import Any, Dict, List

from core_utils import new_id, now_iso
from db import db

COLL = "incentive_definitions"
#: (field dokumen, kunci Pusat Pengaturan) — urutan tampil di layar Target & Aturan.
FIELDS = (
    ("dasar_omzet", "insentif.dasar_omzet"),
    ("isi_pencairan", "insentif.isi_pencairan"),
    ("pemilik_angka", "insentif.pemilik_angka"),
    ("harga_acuan", "insentif.harga_acuan"),
)


async def _values(entity_id: str) -> Dict[str, Any]:
    from services.config_resolver import value_of
    return {f: await value_of(k, {"entity_id": entity_id}) for f, k in FIELDS}


async def _latest(entity_id: str) -> Dict[str, Any]:
    return await db[COLL].find_one({"entity_id": entity_id}, {"_id": 0}, sort=[("version", -1)]) or {}


async def current_definition(entity_id: str) -> Dict[str, Any]:
    """Versi definisi yang berlaku untuk PT: nilai empat kunci `insentif.*` sekarang; bila berbeda dari versi terakhir
    PT itu (atau belum ada versi), versi baru disisipkan. Mengembalikan dokumen versinya."""
    from pymongo.errors import DuplicateKeyError
    from services.book_date import tanggal_buku
    vals = await _values(entity_id)
    for _ in range(5):
        last = await _latest(entity_id)
        if last and all(last.get(f) == vals[f] for f, _k in FIELDS):
            return last
        doc = {"id": new_id("idef"), "entity_id": entity_id, "version": int(last.get("version") or 0) + 1,
               "effective_from": tanggal_buku(), **vals, "recorded_at": now_iso()}
        try:
            await db[COLL].insert_one(dict(doc))
            return doc
        except DuplicateKeyError:
            continue   # pembaca lain baru saja menyisipkan versi yang sama nomornya — baca ulang
    return await _latest(entity_id)


def labels(defn: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Baris hanya-baca untuk layar: label kunci, nilai, dan label Indonesia pilihannya (tanpa kode mentah)."""
    import config_registry
    out = []
    for f, k in FIELDS:
        e = config_registry.require(k)
        v = defn.get(f)
        out.append({"field": f, "key": k, "label": e["label"], "value": v,
                    "value_label": next((o["label"] for o in e["options"] if o["value"] == v), str(v or "—")),
                    "help": e["help"]})
    return out
