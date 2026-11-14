"""KF-T3 (KF-04, standar §2.2 / L6) — PENIMPAAN TERDAFTAR: aturan lain yang menimpa nilai sebuah pengaturan.

Masalah lama: kartu Pusat Pengaturan menampilkan nilai lapisan (mis. tarif PPN 12 % untuk PT bukan PKP), padahal mesin
memakai angka lain karena ada aturan di luar registry yang menang (status PKP di profil PT memaksa tarif 0). Pengguna
melihat angka yang tidak pernah dipakai.

Tiap butir `PENIMPA` mendaftarkan SATU aturan penimpa: kunci yang ditimpanya, kalimat untuk pengguna, tautan ke
sumbernya, dan `cek(key, ctx, nilai)` → nilai yang benar-benar dipakai mesin (atau `None` bila aturan itu tidak berlaku
untuk konteks ini). `config_resolver.resolve()` memanggil `penimpa()` sesudah pemenang lapisan ditentukan, sehingga
`value_of`, `GET /api/config/effective`, dan `GET /api/config/explain` selalu sama dengan pembaca lama
(`config_service.get_effective_settings` / `get_allocation_policy` / `qc_inspection_service.grade_from_points`), yang
tetap menegakkan aturannya sendiri.

Menambah penimpa baru = menambah satu butir di sini, BUKAN menulis ulang angka di layar.
"""
from typing import Any, Awaitable, Callable, Dict, List, Optional

from db import db


async def _pt_bukan_pkp(key: str, ctx: Dict[str, Any], nilai: Any) -> Optional[Any]:
    """Sama dengan `config_service.get_effective_settings`: PT yang ditemukan dan `default_tax_mode != "ppn"` → 0."""
    ent = (ctx or {}).get("entity_id") or ""
    if not ent or ent == "all":
        return None
    entity = await db.business_entities.find_one({"id": ent}, {"_id": 0, "default_tax_mode": 1})
    if not entity or entity.get("default_tax_mode") == "ppn":
        return None
    return 0.0


async def _wajib_transfer_antar_pt(key: str, ctx: Dict[str, Any], nilai: Any) -> Optional[Any]:
    """Sama dengan `config_service.get_allocation_policy`: wajib transfer aktif → stok PT lain tidak boleh dipakai."""
    from services.config_resolver import value_of
    if bool(await value_of("inventory.intercompany_transfer_required", ctx or {})):
        return False
    return None


_GRADE_DARI_KUNCI = {"qc.grade_thresholds.a_max": "A", "qc.grade_thresholds.b_max": "B"}


async def _master_grade_mutu(key: str, ctx: Dict[str, Any], nilai: Any) -> Optional[Any]:
    """Sama dengan `qc_inspection_service.grade_from_points`: grade aktif (bukan grade terakhir/sisa) yang punya
    `max_points` di Master Grade Mutu memakai batas itu, bukan ambang Pusat Pengaturan."""
    import domain_registry as dr
    kode = _GRADE_DARI_KUNCI.get(key)
    active = [g for g in dr.GRADES if g.get("active", True) is not False]
    for g in active[:-1]:
        if g.get("value") == kode and g.get("max_points") is not None:
            return float(g["max_points"])
    return None


Cek = Callable[[str, Dict[str, Any], Any], Awaitable[Optional[Any]]]

PENIMPA: List[Dict[str, Any]] = [
    {"id": "pt_bukan_pkp", "keys": ("tax.ppn_rate",),
     "label": "Status pajak PT ini: bukan PKP",
     "link": {"view": "entities-access"}, "cek": _pt_bukan_pkp},
    {"id": "wajib_transfer_antar_pt", "keys": ("allocation.allow_intercompany",),
     "label": "Pengaturan “Wajib transfer sebelum menjual stok PT lain” sedang aktif",
     "link": {"key": "inventory.intercompany_transfer_required"}, "cek": _wajib_transfer_antar_pt},
    {"id": "master_grade_mutu", "keys": ("qc.grade_thresholds.a_max", "qc.grade_thresholds.b_max"),
     "label": "Batas poin di Master Grade Mutu",
     "link": {"view": "grade-master"}, "cek": _master_grade_mutu},
]

_KUNCI_DITIMPA = {k for p in PENIMPA for k in p["keys"]}


def keys() -> List[str]:
    """Kunci yang punya penimpa terdaftar (urut registry penimpa)."""
    return [k for p in PENIMPA for k in p["keys"]]


async def penimpa(key: str, ctx: Optional[Dict[str, Any]], nilai: Any) -> Optional[Dict[str, Any]]:
    """Butir pertama yang `cek`-nya mengembalikan nilai → `{"id", "label", "value", "link"}`; tidak ada → `None`.

    Kunci tanpa penimpa terdaftar tidak menimbulkan kueri apa pun."""
    if key not in _KUNCI_DITIMPA:
        return None
    for p in PENIMPA:
        if key not in p["keys"]:
            continue
        dipakai = await p["cek"](key, ctx or {}, nilai)
        if dipakai is not None:
            return {"id": p["id"], "label": p["label"], "value": dipakai, "link": dict(p["link"])}
    return None
