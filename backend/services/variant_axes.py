"""Sumbu varian yang dapat dikonfigurasi pemilik (rnd.variant_axes_default / _optional).

Katalog sumbu tetap hidup di kode (size/material/lebar tidak dihapus), tetapi
yang DITAWARKAN ke MD & dipasang otomatis pada induk baru dibaca dari konfigurasi.
"""
from typing import Any, Dict, List

import domain_registry as dr
from services.config_resolver import value_of

def grade_sku_code(value: str) -> str:
    """Kode grade di SKU KN selalu 2 karakter: A → XA, B → XB, A1 → A1."""
    return str(value or "").strip().upper().rjust(2, "X")


NONE_OPT = {"code": "XX", "label": "Tidak ada", "value": "", "hex": ""}

# 2026-09-28 — pengkodean SKU KN: ARTIKEL(9)-ASAL(1)-WARNA(4)-GRADE(2)-CUSTOMER(2)-LOT(2), placeholder X.
AXIS_CATALOG: Dict[str, Dict[str, Any]] = {
    "origin": {"label": "Asal", "options": [
        {"code": "I", "label": "Impor", "value": "impor", "hex": ""},
        {"code": "L", "label": "Lokal", "value": "lokal", "hex": ""},
        {"code": "X", "label": "Belum diketahui", "value": "", "hex": ""}]},
    "color": {"label": "Warna", "options": [], "source": "color_library", "code_len": 4},
    "grade": {"label": "Grade", "options": [
        {"code": grade_sku_code(g["value"]), "label": g["value"], "value": g["value"], "hex": ""} for g in dr.GRADES]},
    "customer": {"label": "Kode Customer", "options": [dict(NONE_OPT)], "code_len": 2},
    "lot": {"label": "Lot", "options": [dict(NONE_OPT)], "code_len": 2},
    "size": {"label": "Ukuran", "options": []},
    "material": {"label": "Material", "options": []},
    # Temuan lama #15 — opsi diisi cm (mis. 150); saat generate varian dikonversi ke meter (1.5) seperti master produk.
    "lebar": {"label": "Lebar (cm)", "options": [], "unit": "cm", "stored_unit": "m"},
}
DEFAULT_AXES = ["origin", "color", "grade", "customer", "lot"]


def _clean(values: Any, fallback: List[str]) -> List[str]:
    if not isinstance(values, list):
        return list(fallback)
    out: List[str] = []
    for v in values:
        k = str(v or "").strip().lower()
        if k in AXIS_CATALOG and k not in out:
            out.append(k)
    return out


async def axis_config(entity_id: str = "") -> Dict[str, Any]:
    ctx = {"entity_id": entity_id or ""}
    default = _clean(await value_of("rnd.variant_axes_default", ctx), DEFAULT_AXES)
    optional = [k for k in _clean(await value_of("rnd.variant_axes_optional", ctx), []) if k not in default]
    return {"default": default, "optional": optional,
            "catalog": [{"key": k, **AXIS_CATALOG[k], "preset": k in default} for k in default + optional]}
