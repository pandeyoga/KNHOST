"""FE-03 (review 2026-10-20) — katalog modul akses selaras dengan menu frontend.

Jalankan: cd /app/backend && python -m pytest tests/test_fe03_access_catalog.py -p no:randomly -n 0 -q
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "guardrails"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fe03_access_fixture as fx  # noqa: E402
import verify_access_catalog_nav as guard  # noqa: E402
from access_modules import nav_allowed_for_perms, nav_for_levels  # noqa: E402


def test_katalog_selaras_menu_frontend():
    assert guard.scan() == []


def test_fixture_frontend_sama_dengan_katalog():
    """Fixture tes menu jest dihasilkan dari katalog — bila katalog berubah, jalankan ulang generatornya."""
    assert json.loads(fx.FIXTURE.read_text(encoding="utf-8")) == fx.build()


def test_pintu_kerja_per_modul():
    add = lambda mod: set(nav_for_levels({mod: "full"})["add"])  # noqa: E731
    assert {"interco-transactions", "interco-returns"} <= add("interco")
    assert {"goods-receipts", "wms-outbound", "rfid-hub"} <= add("warehouse_ops")
    assert {"ledger", "general-ledger", "fin-reports", "closing", "posting-failures"} <= add("accounting")
    assert "qc-inspection" in add("qc") and "qc-inspection" in add("md_quality")
    assert "operations" in add("inventory")
    assert "accounts-payable" not in add("interco") and "rfid" not in add("warehouse_ops")


def test_layar_izin_ikut_katalog():
    """Notifikasi/penjaga layar memakai daftar yang sama: izin wms → tab Barang Masuk/Keluar diizinkan."""
    screens = set(nav_allowed_for_perms({"wms": ["view"], "goods_receipt": ["view"]}))
    assert {"goods-receipts", "wms-outbound"} <= screens
