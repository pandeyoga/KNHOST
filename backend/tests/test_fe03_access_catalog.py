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
    add = lambda mod: set(nav_for_levels({mod: "manage"})["add"])  # noqa: E731
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


def test_fixture_izin_bawaan_sama_dengan_server():
    """Fase 3 · P8 — fixture izin bawaan (dipakai uji jangkauan jest DENGAN izin server) = izin & indeks server."""
    assert json.loads(fx.BUILTIN_FIXTURE.read_text(encoding="utf-8")) == fx.build_builtin()


def _blocked(perms, idx, nav_id):
    """Cermin `roles.accessBlocks` di frontend: id diblok bila modul pembukanya ada tetapi tak satu pun berizin."""
    res = idx.get(nav_id) or []
    return bool(res) and not any((perms.get(r) or []) for r in res)


def test_pengaturan_tidak_terblokir_untuk_peran_yang_dulu_membukanya():
    """Fase 3 · P8 (temuan koordinator) — "Pengaturan" kini GRUP `settings-hub`; dulu id itu hanya milik modul Admin
    (izin settings/user/permission/entity/scheduler), sehingga Admin Sales & Admin Gudang terblokir dari seluruh grup
    (Kebijakan Retur, Master Grade Mutu, Penerimaan & OCR) walau menunya dirancang untuk mereka."""
    from permissions_config import DEFAULT_PERMISSIONS
    from access_modules import view_resources_index
    idx = view_resources_index()
    harus_terbuka = {
        "sales_admin": ["settings-hub", "settings-sales", "return-policies", "settings-warehouse", "grade-master"],
        "warehouse_admin": ["settings-hub", "settings-warehouse", "grade-master", "settings-receiving-ocr"],
        "manager": ["settings-hub", "settings-company", "settings-approval", "settings-sales", "settings-warehouse",
                    "settings-purchasing", "settings-finance", "settings-hr", "settings-rnd", "settings-masters",
                    "settings-documents", "settings-notify", "settings-system", "settings-devices",
                    "price-corrections", "fin-reports", "profitability", "supplier-internal-prices"],
        "warehouse": ["makloon-claim-recap"],
    }
    terblokir = [f"{r} → {v}" for r, ids in harus_terbuka.items() for v in ids
                 if _blocked(DEFAULT_PERMISSIONS.get(r) or {}, idx, v)]
    assert terblokir == []
