"""entity_location_service — lokasi tervalidasi pada UBAH badan usaha (Fase 4 · R6, G5-25).

Dipisah dari `entity_lifecycle_service.py` (berkas itu sudah > 500 baris). Wizard buat badan usaha sudah memakai
pemilih wilayah (negara → provinsi → kota/kab → kecamatan → kode pos, `services/wilayah_service`); PATCH dulu
hanya menerima `city` teks bebas sehingga form ubah tidak bisa memakai pemilih yang sama.
"""
from typing import Any, Dict

LOCATION_FIELDS = ["country", "country_code", "province", "province_code", "city", "city_code",
                   "district", "district_code", "postal_code"]
# (nama, kode) per tingkat — dipakai `normalize_location_patch`.
_LOC_LEVELS = (("country", "country_code"), ("province", "province_code"), ("city", "city_code"),
               ("district", "district_code"))


def normalize_location_patch(existing: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Lokasi hasil PATCH yang sudah dinormalisasi (`wilayah_service`), atau {} bila patch tak menyentuh lokasi.

    Patch digabung dengan lokasi lama supaya mengubah satu isian tidak menghapus yang lain. Bila sebuah tingkat
    diubah lewat NAMA tanpa KODE-nya (form lama: "Kota" teks bebas), kode lama tingkat itu dibuang supaya kode
    dihitung ulang dari nama — kalau tidak, kode lama (mis. Jakarta) diam-diam menimpa nama baru (mis. Bandung).
    Ketidakcocokan (kota di luar provinsi, kode pos salah) → 400 dari `normalize_location`, sama seperti wizard.
    """
    if not any(k in (patch or {}) for k in LOCATION_FIELDS):
        return {}
    from services.wilayah_service import normalize_location
    merged = {k: (existing or {}).get(k) or "" for k in LOCATION_FIELDS}
    for name_key, code_key in _LOC_LEVELS:
        if name_key in patch and code_key not in patch:
            merged[code_key] = ""
    merged.update({k: patch.get(k) or "" for k in LOCATION_FIELDS if k in patch})
    return normalize_location(merged)
