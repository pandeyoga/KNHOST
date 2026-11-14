"""KF-T2 — U13: skrip `scripts/migrate_kft2_akun_bank.py` (docs/blueprint/unit/KF-T2.md, bagian Data · KP-30).

Modul sendiri (basis data bersih): U12 di `test_KFT2_kunci_pengaturan.py` sudah memetakan `kas_bank.beban_bank` untuk
`ent_ksc`, sehingga keadaan lama U13 tidak bisa dibuat di modul itu. Skrip dijalankan di database tiruan saja.
"""
from __future__ import annotations

import datetime
import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
SKRIP = ROOT / "scripts/migrate_kft2_akun_bank.py"


def _skrip():
    spec = importlib.util.spec_from_file_location("migrate_kft2_akun_bank", SKRIP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _akun(klien, h, entity_id, code, name):
    r = await klien.post("/api/gl/accounts", headers=h, params={"entity_id": entity_id},
                         json={"code": code, "name": name, "type": "expense", "parent_code": "6-0000"})
    assert r.status_code == 200, r.text


async def test_KFT2_U13_pindahan_akun_biaya_bank(klien, kepala_admin, db):
    from services import gl_mapping_service as glm
    mod = _skrip()
    assert mod.main(["--salah"]) == 2                   # argumen tak dikenal: keluar sebelum menyentuh basis data
    assert mod.main(["--apply", "--dry-run"]) == 2
    await _akun(klien, kepala_admin, "ent_ksc", "6-8100", "Beban Bank Uji KF-T2")
    # Fixture (sisip langsung) — keadaan lama: akun biaya bank PT KSC diubah lewat Pusat Pengaturan sebelum KF-T2.
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await db.config_values.insert_one({
        "id": "cfgv_uji_kft2", "key": "bank.charge_account_code", "scope_type": "entity", "scope_id": "ent_ksc",
        "value": "6-8100", "prev_value": "6-8000", "prev_source_layer": "code_default", "effective_from": now,
        "effective_to": "", "reason": "keadaan lama", "changed_by": "Uji", "changed_by_id": "", "approved_by": "",
        "risk": "high", "changed_at": now, "created_at": now, "applied_at": now})

    lapor = await mod.jalankan(tulis=False)
    assert [(s["kunci_lama"], s["kunci_pemetaan"], s["lapisan"], s["akun_jurnal_hari_ini"], s["akun_jurnal_sesudah"])
            for s in lapor["selisih"]] == [("bank.charge_account_code", "kas_bank.beban_bank", "ent_ksc", "6-8100",
                                            "6-8000")]
    cetak: list = []
    mod._cetak(lapor, cetak.append)
    assert "Selisih akun jurnal: 1" in cetak
    assert await db.gl_account_mappings.count_documents({}) == 0          # mode lapor tidak menulis

    tulis = await mod.jalankan(tulis=True)
    assert (tulis["ditulis"], tulis["gagal"]) == (1, [])
    assert await glm.account_for("kas_bank.beban_bank", "ent_ksc") == "6-8100"
    assert await glm.account_for("kas_bank.beban_bank", "ent_kanda") == "6-8000"
    jejak = await db.gl_account_mapping_history.find_one({"key": "kas_bank.beban_bank", "entity_id": "ent_ksc"})
    assert jejak["reason"] == "Pindahan dari Pusat Pengaturan (KF-T2)" and jejak["to_code"] == "6-8100"

    ulang = await mod.jalankan(tulis=True)
    assert (len(ulang["selisih"]), ulang["ditulis"]) == (0, 0)


async def test_KFT2_U13b_pemetaan_yang_sudah_diubah_tidak_ditimpa_bawaan(klien, kepala_admin):
    """Pelengkap U13 (lihat "Menyimpang" di laporan): Admin sudah mengubah Pemetaan Akun `kas_bank.beban_bank` untuk
    `ent_kanda`, kunci Pusat Pengaturan masih bawaan 6-8000. Jurnal hari ini sudah memakai akun pemetaan (6-8000 adalah
    kode bawaan yang dialihkan `remap_lines`), jadi skrip tidak boleh mengembalikan pemetaan ke 6-8000."""
    from services import gl_mapping_service as glm
    mod = _skrip()
    await _akun(klien, kepala_admin, "ent_kanda", "6-8200", "Beban Bank Kanda Uji KF-T2")
    r = await klien.put("/api/gl/account-mappings/kas_bank.beban_bank", headers=kepala_admin,
                        json={"account_code": "6-8200", "entity_id": "ent_kanda", "reason": "uji KF-T2 pemetaan Kanda"})
    assert r.status_code == 200, r.text
    lapor = await mod.jalankan(tulis=False)
    assert lapor["selisih"] == []
    assert await glm.account_for("kas_bank.beban_bank", "ent_kanda") == "6-8200"
