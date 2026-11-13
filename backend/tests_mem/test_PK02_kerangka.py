"""PK-02 U1, U2, U4–U10, U14 — kerangka uji: aplikasi, akun, sesi, tiga peran uji, pembantu periode/akun/jurnal."""
import pytest
from mongomock_motor import AsyncMongoMockClient

import db as _dbmod
from pembantu import (alasan_xfail_sah, buka_periode, jurnal, jurnal_dari, tutup_periode)
from services import gl_service as gl
from services.gl_service import ClosedPeriodError, JournalValidationError


async def test_U1_registry_bisa_dibaca_admin(klien, kepala_admin):
    r = await klien.get("/api/config/registry", headers=kepala_admin)
    assert r.status_code == 200


async def test_U2_klien_database_tiruan(aplikasi):
    assert isinstance(_dbmod.client, AsyncMongoMockClient)


async def test_U4_sesi_akun_seed(klien, sesi):
    r = await klien.get("/api/auth/me", headers=await sesi("sales@kainnusantara.id"))
    assert r.status_code == 200
    j = r.json()
    assert (j.get("user") or j)["role"] == "sales"


async def test_U5_peran_tanpa_acuan(klien, akun, sesi, peran_tanpa_acuan):
    p = await peran_tanpa_acuan({"accounting": ["view"]})
    h = await sesi(await akun(p))
    assert (await klien.get("/api/finance/posting-failures", headers=h)).status_code == 200
    assert (await klien.get("/api/vendor-bills/status-counts", headers=h)).status_code == 403


async def test_U6_peran_manajer_kosong(klien, akun, sesi, peran_manajer_kosong):
    h = await sesi(await akun(await peran_manajer_kosong()))
    assert (await klien.get("/api/finance/posting-failures", headers=h)).status_code == 403


async def test_U7_peran_sopir(klien, akun, sesi, peran_sopir):
    h = await sesi(await akun(peran_sopir))
    assert (await klien.get("/api/finance/posting-failures", headers=h)).status_code == 403


async def test_U8_tutup_periode_per_pt(aplikasi):
    c = await tutup_periode("ent_kanda", "2026-09")
    with pytest.raises(ClosedPeriodError):
        await gl.preflight_posting("ent_kanda", "2026-09-15")
    await gl.preflight_posting("ent_ksc", "2026-09-15")
    await buka_periode(c["id"])
    await gl.preflight_posting("ent_kanda", "2026-09-15")


async def test_U9_paksa_gagal_lewat_akun(aplikasi, paksa_jurnal_gagal):
    baris = [("6-2000", 1000, 0), ("1-1100", 0, 1000)]
    async with paksa_jurnal_gagal("akun", entity_id="ent_kanda", kode_akun="6-2000"):
        with pytest.raises(JournalValidationError):
            await jurnal("ent_kanda", "2026-11-05", baris, "uji akun nonaktif", "u9a")
        assert (await jurnal("ent_ksc", "2026-11-05", baris, "PT lain tidak ikut", "u9b"))["id"]
    assert (await jurnal("ent_kanda", "2026-11-05", baris, "sesudah dipulihkan", "u9c"))["id"]


async def test_U10_paksa_gagal_sisip_sekali(aplikasi, paksa_jurnal_gagal):
    baris = [("6-2000", 1000, 0), ("1-1100", 0, 1000)]
    async with paksa_jurnal_gagal("sisip", entity_id="ent_ksc", kali=1) as gagal:
        with pytest.raises(RuntimeError, match="dipaksa gagal"):
            await jurnal("ent_ksc", "2026-11-06", baris, "pertama", "x1")
        await jurnal("ent_ksc", "2026-11-06", baris, "kedua", "x1")
    assert len(await jurnal_dari("uji", "x1")) == 1
    assert len(gagal) == 1


def test_U14_alasan_xfail():
    assert alasan_xfail_sah("GL-01 — dibalik dua kali")
    assert not alasan_xfail_sah("nanti diperbaiki")
