"""KA-1 — aturan pengali komisi per artikel: validasi nilai tabel + pembaca kunci Pusat Pengaturan.

Kunci `commission.price_*` (pengali menurut harga jual) dan `commission.achievement_*` (pengali capaian target) hidup di
Pusat Pengaturan (`config_catalog_core`). Modul ini memeriksa isi tabelnya saat disimpan (`config_resolver.set_value`)
dan membacanya untuk mesin komisi. Rancangan: `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

PRICE_KEYS = ("commission.price_basis", "commission.price_bands", "commission.price_source_rules")
ACH_KEYS = ("commission.achievement_multiplier", "commission.achievement_basis", "commission.achievement_tiers")
SUMBER_KHUSUS = ("special_approval", "customer", "special_order")
CARA_SUMBER = ("ikut_pita", "pengali_tetap")

_KUNCI_HARGA_LAIN = ("discount_threshold_type", "discount_threshold", "discount_mechanic", "discount_factor",
                     "discount_potong_rp", "default_margin_cap_pct")
_BAWAAN_SUMBER = {"cara": "ikut_pita", "pengali": 1.0}


def _angka(v: Any, nama: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise ValueError(f"{nama} harus berupa angka.")
    try:
        return float(v)
    except ValueError:
        raise ValueError(f"{nama} harus berupa angka.") from None


def _baris(value: Any, nama: str) -> List[Dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{nama} minimal berisi satu baris.")
    if not all(isinstance(r, dict) for r in value):
        raise ValueError(f"Isi {nama} tidak sah.")
    return value


def _pengali(r: Dict[str, Any], nama: str) -> float:
    p = _angka(r.get("pengali"), f"Pengali pada {nama}")
    if p < 0:
        raise ValueError(f"Pengali pada {nama} tidak boleh negatif.")
    return p


def _periksa_pita(value: Any) -> Any:
    nama = "Pita pengali harga"
    rows = _baris(value, nama)
    batas, kosong = [], []
    for r in rows:
        p = _pengali(r, nama)
        s = r.get("sampai_pct")
        if s is None or (isinstance(s, str) and not s.strip()):
            kosong.append({"sampai_pct": None, "pengali": p})
            continue
        s = _angka(s, f"Batas selisih pada {nama}")
        if s <= 0:
            raise ValueError(f"Batas selisih pada {nama} harus lebih dari 0.")
        batas.append({"sampai_pct": s, "pengali": p})
    if len(kosong) != 1:
        raise ValueError(f"{nama} harus punya tepat satu baris terakhir tanpa batas (kolom batas dikosongkan).")
    nilai = [b["sampai_pct"] for b in batas]
    if len(set(nilai)) != len(nilai):
        raise ValueError(f"Batas selisih pada {nama} tidak boleh kembar.")
    return sorted(batas, key=lambda b: b["sampai_pct"]) + kosong


def _periksa_sumber(value: Any) -> Any:
    nama = "Aturan asal harga"
    rows = _baris(value, nama)
    out, lihat = [], set()
    for r in rows:
        sumber, cara = r.get("sumber"), r.get("cara")
        if sumber not in SUMBER_KHUSUS:
            raise ValueError(f"Asal harga '{sumber}' pada {nama} tidak dikenal.")
        if sumber in lihat:
            raise ValueError(f"Asal harga pada {nama} tidak boleh kembar.")
        lihat.add(sumber)
        if cara not in CARA_SUMBER:
            raise ValueError(f"Cara pada {nama} harus 'Ikut cara harga' atau 'Pengali tetap'.")
        out.append({"sumber": sumber, "cara": cara, "pengali": _pengali(r, nama)})
    return out


def _periksa_jenjang(value: Any) -> Any:
    nama = "Jenjang pengali capaian"
    rows = _baris(value, nama)
    out = []
    for r in rows:
        m = _angka(r.get("capaian_min_pct"), f"Capaian mulai pada {nama}")
        if m < 0:
            raise ValueError(f"Capaian mulai pada {nama} tidak boleh negatif.")
        out.append({"capaian_min_pct": m, "pengali": _pengali(r, nama)})
    nilai = [o["capaian_min_pct"] for o in out]
    if len(set(nilai)) != len(nilai):
        raise ValueError(f"Capaian mulai pada {nama} tidak boleh kembar.")
    if 0 not in nilai:
        raise ValueError(f"{nama} wajib punya satu baris yang mulai dari 0%.")
    return sorted(out, key=lambda o: o["capaian_min_pct"])


_PEMERIKSA = {
    "commission.price_bands": _periksa_pita,
    "commission.price_source_rules": _periksa_sumber,
    "commission.achievement_tiers": _periksa_jenjang,
}


def periksa_nilai(key: str, value: Any) -> Any:
    """Nilai bersih kunci tabel pengali komisi (kunci lain dikembalikan apa adanya). `ValueError` berpesan siap tampil."""
    fn = _PEMERIKSA.get(key)
    return fn(value) if fn else value


async def aturan_pt(entity_id: Optional[str], hipotetis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Aturan harga komisi satu PT. `hipotetis` = `{kunci: nilai}` yang menimpa nilai tersimpan (untuk simulasi)."""
    from services import config_resolver
    keys = list(PRICE_KEYS) + ["insentif.harga_acuan"] + [f"commission.{k}" for k in _KUNCI_HARGA_LAIN]
    res = await config_resolver.resolve_keys(keys, {"entity_id": entity_id or ""})
    nilai = {k: res[k]["value"] for k in keys}
    for k, v in (hipotetis or {}).items():
        if k in nilai:
            nilai[k] = _PEMERIKSA[k](v) if k in _PEMERIKSA else v
    ada = {r["sumber"]: r for r in nilai["commission.price_source_rules"]}
    aturan_sumber = [dict(ada.get(s) or {"sumber": s, **_BAWAAN_SUMBER}) for s in SUMBER_KHUSUS]
    out = {
        "price_basis": nilai["commission.price_basis"],
        "price_bands": nilai["commission.price_bands"],
        "price_source_rules": aturan_sumber,
        "acuan": nilai["insentif.harga_acuan"],
    }
    for k in _KUNCI_HARGA_LAIN:
        out[k] = nilai[f"commission.{k}"]
    return out


async def aturan_capaian(entity_id: str, at: Optional[datetime] = None) -> Dict[str, Any]:
    """Aturan pengali capaian target PT pada waktu `at` (bawaan: sekarang)."""
    from services import config_resolver
    res = await config_resolver.resolve_keys(list(ACH_KEYS), {"entity_id": entity_id}, at=at)
    return {"aktif": bool(res["commission.achievement_multiplier"]["value"]),
            "basis": res["commission.achievement_basis"]["value"],
            "jenjang": res["commission.achievement_tiers"]["value"]}
