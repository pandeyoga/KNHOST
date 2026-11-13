"""PK-11 — periode yang belum berakhir tidak bisa ditutup (docs/blueprint/unit/PK-11.md).

Admin, `ent_ksc`, tanpa saldo suspense; satu jurnal manual pendapatan lawan kas bertanggal 2026-11-05. "Hari ini" diatur
dengan mengganti `closing_service._today_wib` (`raising=False` supaya berkas ini juga berjalan di kode lama sebagai
bukti merah). Uji berurutan: U3 sengaja memakai keadaan sesudah U1.
"""
from __future__ import annotations

import datetime

import pytest

from services import analytics_time
from services import closing_service as cs
from services import financial_statement_service as fs
from services import gl_service as gl

pytestmark = pytest.mark.anyio
E1 = "ent_ksc"
URL = "/api/finance/closing/close"
WIB = datetime.timezone(datetime.timedelta(hours=7))


def _hari_ini(monkeypatch, tanggal: str) -> None:
    monkeypatch.setattr(cs, "_today_wib", lambda: tanggal, raising=False)


def _badan(kunci: str, jenis: str = "month") -> dict:
    return {"period_type": jenis, "period_key": kunci, "entity_id": E1}


async def _bersihkan(db) -> None:
    await db.period_closings.delete_many({"entity_id": E1})
    await db.period_close_locks.delete_many({})
    await db.journal_entries.delete_many({"entity_id": E1, "source_type": "closing"})


async def _jurnal_penutup(db) -> list:
    return await db.journal_entries.find({"entity_id": E1, "source_type": "closing", "status": {"$ne": "void"}},
                                         {"_id": 0}).to_list(50)


@pytest.fixture(scope="module", autouse=True)
async def persiapan(aplikasi):
    saldo = await gl.suspense_balance(E1)   # data awal punya saldo suspense; dinolkan (persiapan "tanpa saldo suspense")
    if abs(saldo) > 0.005:
        d, k = (0, saldo) if saldo > 0 else (-saldo, 0)
        await gl._insert_entry(
            lines=[{"account_code": "1-9999", "account_name": "Suspense", "debit": d, "credit": k},
                   {"account_code": "3-2000", "account_name": "Laba Ditahan", "debit": k, "credit": d}],
            description="uji PK-11 nolkan suspense", date="2026-01-02T10:00:00", source_type="manual",
            source_id="pk11_suspense", entity_id=E1, created_by="uji")
    assert abs(await gl.suspense_balance(E1)) <= 0.005
    await gl._insert_entry(
        lines=[{"account_code": "1-1100", "account_name": "Kas", "debit": 2_500_000, "credit": 0},
               {"account_code": "4-1000", "account_name": "Pendapatan", "debit": 0, "credit": 2_500_000}],
        description="uji PK-11 pendapatan tunai", date="2026-11-05T10:00:00", source_type="manual",
        source_id="pk11_awal", entity_id=E1, created_by="uji")


async def test_U01_bulan_berjalan_ditolak(klien, db, kepala_admin, monkeypatch):
    await _bersihkan(db)
    _hari_ini(monkeypatch, "2026-11-13")
    r = await klien.post(URL, headers=kepala_admin, json=_badan("2026-11"))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == ("Periode November 2026 belum berakhir — tutup buku baru bisa dilakukan mulai "
                                  "1 Desember 2026.")
    assert await db.period_closings.count_documents({}) == 0
    assert await _jurnal_penutup(db) == []
    assert await db.period_close_locks.count_documents({}) == 0


async def test_U02_bulan_depan_dan_tahun_berjalan_ditolak(klien, db, kepala_admin, monkeypatch):
    _hari_ini(monkeypatch, "2026-11-13")
    for badan in (_badan("2026-12"), _badan("2026", "year")):
        r = await klien.post(URL, headers=kepala_admin, json=badan)
        assert r.status_code == 400, r.text
        assert "belum berakhir" in r.json()["detail"]
    assert await db.period_closings.count_documents({}) == 0
    assert await _jurnal_penutup(db) == []


async def test_U03_jurnal_hari_ini_tetap_bisa(klien, db, kepala_admin):
    # sengaja tanpa _bersihkan: memakai keadaan sesudah U1/U2
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json={
        "date": "2026-11-13", "description": "uji PK-11 jurnal hari ini",
        "lines": [{"account_code": "6-2000", "debit": 1000, "credit": 0},
                  {"account_code": "1-1100", "debit": 0, "credit": 1000}]})
    assert r.status_code == 200, r.text


async def test_U04_akhir_periode_hari_ini_ditolak(klien, db, kepala_admin, monkeypatch):
    await _bersihkan(db)
    _hari_ini(monkeypatch, "2026-11-30")
    r = await klien.post(URL, headers=kepala_admin, json=_badan("2026-11"))
    assert r.status_code == 400, r.text
    assert "belum berakhir" in r.json()["detail"]
    assert await db.period_closings.count_documents({}) == 0


async def test_U05_sehari_sesudah_akhir_boleh(klien, db, kepala_admin, monkeypatch):
    await _bersihkan(db)
    _hari_ini(monkeypatch, "2026-12-01")
    r = await klien.post(URL, headers=kepala_admin, json=_badan("2026-11"))
    assert r.status_code == 200, r.text
    rec = await db.period_closings.find_one({"entity_id": E1, "period_key": "2026-11"}, {"_id": 0})
    assert rec["status"] == "closed" and rec["stale"] is False
    jp = await _jurnal_penutup(db)
    assert len(jp) == 1 and jp[0]["date"][:10] == "2026-11-30"


async def test_U06_batas_tanggal_wib_bukan_utc(klien, db, kepala_admin, monkeypatch):
    await _bersihkan(db)
    # 2026-12-01 00:30 WIB = 2026-11-30 17:30 UTC
    monkeypatch.setattr(analytics_time, "now_wib", lambda: datetime.datetime(2026, 12, 1, 0, 30, tzinfo=WIB))
    r = await klien.post(URL, headers=kepala_admin, json=_badan("2026-11"))
    assert r.status_code == 200, r.text


async def test_U07_pratinjau_bulan_depan(klien, db, kepala_admin, monkeypatch):
    await _bersihkan(db)
    _hari_ini(monkeypatch, "2026-12-01")
    r = await klien.get("/api/finance/closing/preview", headers=kepala_admin,
                        params={"period_type": "month", "period_key": "2026-12", "entity_id": E1})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p.get("period_ended") is False
    assert p["can_close"] is False
    assert p.get("earliest_close_date") == "2027-01-01"
    r = await klien.get("/api/finance/closing/preview", headers=kepala_admin,
                        params={"period_type": "month", "period_key": "2026-11", "entity_id": E1})
    assert r.json().get("period_ended") is True and r.json()["can_close"] is True


async def test_U08_tutup_dua_kali(klien, db, kepala_admin, monkeypatch):
    await _bersihkan(db)
    _hari_ini(monkeypatch, "2026-12-01")
    r1 = await klien.post(URL, headers=kepala_admin, json=_badan("2026-11"))
    r2 = await klien.post(URL, headers=kepala_admin, json=_badan("2026-11"))
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 400 and r2.json()["detail"].startswith("Periode tumpang tindih"), r2.text
    assert len(await _jurnal_penutup(db)) == 1


async def test_U09_jurnal_menyusup_saat_tutup_menandai_basi(klien, db, kepala_admin, monkeypatch):
    await _bersihkan(db)
    _hari_ini(monkeypatch, "2026-12-01")
    asli = fs.income_statement

    async def _bungkus(*a, **kw):
        hasil = await asli(*a, **kw)
        await gl._insert_entry(
            lines=[{"account_code": "6-2000", "account_name": "Beban", "debit": 50_000, "credit": 0},
                   {"account_code": "1-1100", "account_name": "Kas", "debit": 0, "credit": 50_000}],
            description="uji PK-11 jurnal menyusup", date="2026-11-20T09:00:00", source_type="uji_menyusup",
            source_id="pk11_susup", entity_id=E1, created_by="uji")
        return hasil
    monkeypatch.setattr(fs, "income_statement", _bungkus)
    r = await klien.post(URL, headers=kepala_admin, json=_badan("2026-11"))
    assert r.status_code == 200, r.text
    rec = await db.period_closings.find_one({"entity_id": E1, "period_key": "2026-11"}, {"_id": 0})
    assert rec["status"] == "closed"
    assert rec["stale"] is True and rec.get("stale_reason")


async def test_U10_jurnal_penutup_gagal_catatan_dihapus(klien, db, kepala_admin, monkeypatch, paksa_jurnal_gagal):
    await _bersihkan(db)
    _hari_ini(monkeypatch, "2026-12-01")
    async with paksa_jurnal_gagal("sisip", entity_id=E1, source_type="closing") as gagal:
        r = await klien.post(URL, headers=kepala_admin, json=_badan("2026-11"))
    assert r.status_code >= 400 and gagal, r.text
    assert await db.period_closings.count_documents({}) == 0
    assert await db.period_close_locks.count_documents({}) == 0
    r = await klien.post(URL, headers=kepala_admin, json=_badan("2026-11"))
    assert r.status_code == 200, r.text
    assert await db.period_closings.count_documents({"status": "closed"}) == 1
    assert len(await _jurnal_penutup(db)) == 1


async def test_U11_sisa_proses_terputus_dibereskan(klien, db, kepala_admin, monkeypatch):
    await _bersihkan(db)
    _hari_ini(monkeypatch, "2026-12-01")
    dasar = {"entity_id": E1, "period_type": "month", "status": "closing", "stale": False, "closed_by": "uji"}
    await db.period_closings.insert_many([
        {**dasar, "id": "pc_pk11_okt", "period_key": "2026-10", "period_label": "Oktober 2026",
         "start_date": "2026-10-01", "end_date": "2026-10-31"},
        {**dasar, "id": "pc_pk11_sep", "period_key": "2026-09", "period_label": "September 2026",
         "start_date": "2026-09-01", "end_date": "2026-09-30"}])
    await db.journal_entries.insert_one({
        "id": "je_pk11_sep", "number": "JE-PK11-SEP", "entity_id": E1, "status": "posted",
        "source_type": "closing", "source_id": "pc_pk11_sep", "date": "2026-09-30T23:59:59",
        "description": "Jurnal Penutup — September 2026",
        "lines": [{"account_code": "4-1000", "debit": 0, "credit": 0}]})
    r = await klien.post(URL, headers=kepala_admin, json=_badan("2026-11"))
    assert r.status_code == 200, r.text
    assert await db.period_closings.find_one({"id": "pc_pk11_okt"}) is None
    sep = await db.period_closings.find_one({"id": "pc_pk11_sep"}, {"_id": 0})
    assert sep["status"] == "closed" and sep["stale"] is True
    assert sep.get("journal_entry_id") == "je_pk11_sep"
    nov = await db.period_closings.find_one({"entity_id": E1, "period_key": "2026-11"}, {"_id": 0})
    assert nov["status"] == "closed"


async def test_U12_kunci_hanya_dilepas_pemiliknya(db):
    await db.period_close_locks.delete_many({})
    await db.period_close_locks.insert_one({"_id": E1, "token": "tok_b", "period": "month:2026-11",
                                            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    await cs._release_close_lock(E1, "tok_a")
    kunci = await db.period_close_locks.find_one({"_id": E1})
    assert kunci is not None and kunci["token"] == "tok_b"
    await db.period_close_locks.delete_many({})
