"""FE-03 — peran kustom acuan untuk tes menu frontend (dihasilkan dari katalog backend, satu sumber).

Tulis ulang fixture:  cd /app/backend && python tests/fe03_access_fixture.py
Tes `tests/test_fe03_access_catalog.py` menggagalkan bila fixture tidak sama dengan katalog.

Fase 3 · P8 — fixture KEDUA `access_builtin_fixture.json`: izin bawaan peran bawaan (`DEFAULT_PERMISSIONS`) +
`view_resources_index()` — persis yang dikirim server saat login (`routers/auth._my_nav`) dan dipakai
`roles.setAccessContext` untuk menyembunyikan menu/tab yang modul pembukanya tanpa izin. Uji jest
`config/__tests__/serverAccessReach.test.js` memuatnya supaya jangkauan peran bawaan diuji DENGAN izin server
(temuan koordinator: grup Pengaturan dulu terblokir untuk Admin Sales karena `settings-hub` hanya milik modul Admin).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from access_modules import MODULE_CATALOG, nav_for_levels, view_resources_index  # noqa: E402
from permissions_config import DEFAULT_PERMISSIONS  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[2] / "frontend/src/config/__tests__/fixtures/access_nav_fixture.json"
BUILTIN_FIXTURE = FIXTURE.with_name("access_builtin_fixture.json")
ROLES = {
    "cr_interco": {"base_role": "", "levels": {"interco": "manage"}},
    "cr_accounting": {"base_role": "", "levels": {"accounting": "manage"}},
    "cr_warehouse_ops": {"base_role": "", "levels": {"warehouse_ops": "manage"}},
    "cr_qc": {"base_role": "", "levels": {"qc": "manage"}},
    # Fase 3 · P8 — Pengaturan kini GRUP (P16-K1) & Margin & HPP digabung ke Profitabilitas (D-11).
    "cr_settings_admin": {"base_role": "", "levels": {"admin": "manage"}},
    "cr_hr": {"base_role": "", "levels": {"hr": "manage"}},
    "cr_reports": {"base_role": "", "levels": {"reports": "manage"}},
    # turunan Manager: semua modul penuh kecuali Akuntansi (editor peran selalu mengirim semua modul)
    "cr_manager_no_accounting": {"base_role": "manager",
                                 "levels": {**{m["id"]: "manage" for m in MODULE_CATALOG}, "accounting": "none"}},
}


def build() -> list:
    return [{"id": rid, "label": rid, "custom": True, "base_role": r["base_role"], "nav": nav_for_levels(r["levels"])}
            for rid, r in ROLES.items()]


def build_builtin() -> dict:
    """Izin bawaan per peran bawaan + indeks id menu → sumber daya izin (sama dengan respons login)."""
    return {"view_resources": view_resources_index(),
            "permissions": {r: {k: list(v) for k, v in sorted((p or {}).items())}
                            for r, p in sorted(DEFAULT_PERMISSIONS.items())}}


if __name__ == "__main__":
    FIXTURE.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    BUILTIN_FIXTURE.write_text(json.dumps(build_builtin(), indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                               encoding="utf-8")
    print(f"ditulis: {FIXTURE}\nditulis: {BUILTIN_FIXTURE}")
