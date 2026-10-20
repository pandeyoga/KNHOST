"""FE-03 — peran kustom acuan untuk tes menu frontend (dihasilkan dari katalog backend, satu sumber).

Tulis ulang fixture:  cd /app/backend && python tests/fe03_access_fixture.py
Tes `tests/test_fe03_access_catalog.py` menggagalkan bila fixture tidak sama dengan katalog.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from access_modules import MODULE_CATALOG, nav_for_levels  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[2] / "frontend/src/config/__tests__/fixtures/access_nav_fixture.json"
ROLES = {
    "cr_interco": {"base_role": "", "levels": {"interco": "manage"}},
    "cr_accounting": {"base_role": "", "levels": {"accounting": "manage"}},
    "cr_warehouse_ops": {"base_role": "", "levels": {"warehouse_ops": "manage"}},
    "cr_qc": {"base_role": "", "levels": {"qc": "manage"}},
    # turunan Manager: semua modul penuh kecuali Akuntansi (editor peran selalu mengirim semua modul)
    "cr_manager_no_accounting": {"base_role": "manager",
                                 "levels": {**{m["id"]: "manage" for m in MODULE_CATALOG}, "accounting": "none"}},
}


def build() -> list:
    return [{"id": rid, "label": rid, "custom": True, "base_role": r["base_role"], "nav": nav_for_levels(r["levels"])}
            for rid, r in ROLES.items()]


if __name__ == "__main__":
    FIXTURE.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ditulis: {FIXTURE}")
