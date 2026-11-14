"""PK-37 serah-terima (a) — satu fungsi tanggal buku WIB, kunci `periode.kunci_dokumen`, skrip tanggal buku lama.

U1–U3 (fungsi `services/book_date.py`), U15 (putaran `t1_config.py` untuk kunci baru), U16 (skrip baca-saja
`scripts/blueprint/pk37_tanggal_buku_lama.py`). Modul baru diimpor DI DALAM tes supaya tiap tes merah sendiri di kode
lama (modul/kunci/skrip belum ada).

Hitungan tangan zona waktu: WIB = UTC+7 → 17.00 UTC = 00.00 WIB hari berikutnya; 16.59.59 UTC = 23.59.59 WIB hari sama.
"""
import datetime
import importlib.util
from pathlib import Path

import pytest

from services.config_resolver import value_of

ROOT = Path(__file__).resolve().parents[2]
SKRIP = ROOT / "scripts/blueprint/pk37_tanggal_buku_lama.py"
KUNCI = "periode.kunci_dokumen"
KSC, KANDA = "ent_ksc", "ent_kanda"


def _isi(key, value, scope_type="global", scope_id="", reason="uji PK-37"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]}


async def _simpan(klien, h, key, value, scope_type="global", scope_id=""):
    r = await klien.put("/api/config/values", headers=h, json=_isi(key, value, scope_type, scope_id))
    assert r.status_code == 200, r.text


async def _pulihkan(klien, h, key, *pt):
    for eid in pt:
        r = await klien.post("/api/config/values/clear", headers=h,
                             json={"key": key, "scope_type": "entity", "scope_id": eid, "reason": "pulihkan"})
        assert r.status_code == 200, r.text
    r = await klien.post("/api/config/values/reset", headers=h,
                         json={"key": key, "scope_type": "global", "reason": "pulihkan"})
    assert r.status_code == 200, r.text


# ── U1 — teks ISO ber-zona diubah ke WIB ─────────────────────────────────────────────────────────────────────────────
async def test_PK37_U1_stempel_berzona_diubah_ke_wib():
    from services.book_date import tanggal_buku
    assert tanggal_buku("2026-10-31T17:30:00+00:00") == "2026-11-01"   # 17.30 UTC = 00.30 WIB 1 Nov
    assert tanggal_buku("2026-10-31T16:59:59+00:00") == "2026-10-31"   # 16.59.59 UTC = 23.59.59 WIB 31 Okt
    assert tanggal_buku("2026-10-31T17:00:00Z") == "2026-11-01"        # 17.00 UTC = 00.00 WIB 1 Nov
    # tambahan: zona lain dan objek datetime (tanpa zona = UTC)
    assert tanggal_buku("2026-11-01T00:30:00+07:00") == "2026-11-01"
    assert tanggal_buku(datetime.datetime(2026, 10, 31, 17, 30)) == "2026-11-01"
    assert tanggal_buku(datetime.datetime(2026, 10, 31, 17, 30, tzinfo=datetime.timezone.utc)) == "2026-11-01"


# ── U2 — 10 huruf dan ISO tanpa zona apa adanya; bentuk lain ditolak ─────────────────────────────────────────────────
async def test_PK37_U2_tanggal_isian_apa_adanya_bentuk_lain_ditolak():
    from services.book_date import tanggal_buku
    assert tanggal_buku("2026-11-01") == "2026-11-01"
    assert tanggal_buku("2026-11-01T00:00:00") == "2026-11-01"
    with pytest.raises(ValueError, match="Tanggal tidak dikenali"):
        tanggal_buku("31/10/2026")
    for salah in ("2026-11", "2026-13-01", "kemarin", 20261101):
        with pytest.raises(ValueError, match="Tanggal tidak dikenali"):
            tanggal_buku(salah)


# ── U3 — "hari ini" dan periode berjalan di WIB ──────────────────────────────────────────────────────────────────────
async def test_PK37_U3_hari_ini_wib_dengan_jam_dibekukan(monkeypatch):
    from services import book_date
    beku = datetime.datetime(2026, 10, 31, 17, 30, tzinfo=datetime.timezone.utc)   # = 1 Nov 00.30 WIB
    monkeypatch.setattr(book_date, "_sekarang", lambda: beku)
    assert book_date.tanggal_buku() == "2026-11-01"
    assert book_date.tanggal_buku("") == "2026-11-01"
    assert book_date.periode_buku() == "2026-11"
    assert book_date.periode_buku("2026-10-31T17:30:00+00:00") == "2026-11"


# ── U15 — putaran t1_config untuk `periode.kunci_dokumen` ────────────────────────────────────────────────────────────
async def test_PK37_U15_putaran_t1_config(klien, kepala_admin):
    import config_registry as registry
    e = registry.require(KUNCI)
    assert (e["type"], e["default"], e["scopes"], e["permission"]) == ("bool", True, ["global", "entity"],
                                                                         ["accounting", "manage"])
    assert e["risk"] == "high" and e["requires_reason"] is True and e["status"] == "active"
    assert e["group"] == "pajak-pembukuan" and e["section"] == "tutup-buku"   # alias KF-T4 dari "keuangan-dasar"
    assert e["consumers"] == ["services/book_date.py:periksa_periode_dokumen"]
    assert await value_of(KUNCI) is True                                       # bawaan K-03 "Mengunci"
    # tulis global → terbaca lewat resolver dan lewat /api/config/effective
    await _simpan(klien, kepala_admin, KUNCI, False)
    assert await value_of(KUNCI) is False
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": KUNCI})
    assert next(i for i in r.json()["items"] if i["key"] == KUNCI)["value"] is False
    # lapisan PT → hanya PT itu
    await _simpan(klien, kepala_admin, KUNCI, True, "entity", KANDA)
    assert await value_of(KUNCI, {"entity_id": KANDA}) is True
    assert await value_of(KUNCI, {"entity_id": KSC}) is False
    await _pulihkan(klien, kepala_admin, KUNCI, KANDA)
    # nilai bukan boolean → 400
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(KUNCI, "bukan-bool"))
    assert r.status_code == 400, r.text
    await _pulihkan(klien, kepala_admin, KUNCI)
    assert await value_of(KUNCI) is True
    assert await value_of(KUNCI, {"entity_id": KANDA}) is True


async def test_PK37_U15b_pengubah_kunci_dari_izin_akuntansi(klien, akun, sesi, peran_tanpa_acuan):
    """Izin pengubah = `accounting.manage` (ASUMSI spesifikasi); pemegang `settings.manage` saja tidak bisa."""
    rid = await peran_tanpa_acuan({"accounting": ["view", "manage"]}, label="Kelola Akuntansi PK37")
    h = await sesi(await akun(rid))
    r = await klien.put("/api/config/values", headers=h, json=_isi(KUNCI, False, "entity", KSC))
    assert r.status_code == 200, r.text
    assert await value_of(KUNCI, {"entity_id": KSC}) is False
    r = await klien.post("/api/config/values/clear", headers=h,
                         json={"key": KUNCI, "scope_type": "entity", "scope_id": KSC, "reason": "pulihkan"})
    assert r.status_code == 200, r.text
    rid2 = await peran_tanpa_acuan({"settings": ["view", "manage"]}, label="Kelola Pengaturan PK37")
    h2 = await sesi(await akun(rid2))
    r = await klien.put("/api/config/values", headers=h2, json=_isi(KUNCI, False, "entity", KSC))
    assert r.status_code == 403, r.text
    assert await value_of(KUNCI, {"entity_id": KSC}) is True


# ── U16 — skrip tanggal buku lama, mode baca-saja ────────────────────────────────────────────────────────────────────
def _muat_skrip():
    spec = importlib.util.spec_from_file_location("pk37_tanggal_buku_lama", SKRIP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def test_PK37_U16_skrip_baca_saja_hanya_jurnal_dini_hari(db, capsys):
    # Fixture (sisip langsung): tiga jurnal "lama" di PT uji.
    #  1. 2026-10-31T17:30:00+00:00 = 1 Nov 00.30 WIB → tercatat Okt, seharusnya Nov  → TERDAFTAR
    #  2. 2026-10-15T03:00:00+00:00 = 15 Okt 10.00 WIB → tanggal sama               → tidak
    #  3. 2026-10-20 (10 huruf)                                                       → tidak
    eid = "ent_uji_pk37s"
    dasar = {"description": "uji", "source_type": "uji", "status": "posted", "entity_id": eid, "lines": [],
             "total_credit": 0}
    await db.journal_entries.insert_many([
        {**dasar, "id": "je_pk37s_1", "number": "S/JE-1", "date": "2026-10-31T17:30:00+00:00", "total_debit": 1_000_000},
        {**dasar, "id": "je_pk37s_2", "number": "S/JE-2", "date": "2026-10-15T03:00:00+00:00", "total_debit": 200_000},
        {**dasar, "id": "je_pk37s_3", "number": "S/JE-3", "date": "2026-10-20", "total_debit": 300_000}])
    sebelum = [d async for d in db.journal_entries.find({"entity_id": eid}, {"_id": 0}).sort("id", 1)]
    mod = _muat_skrip()
    rows = [r for r in await mod.kumpulkan(db) if r["entity_id"] == eid]
    assert [(r["id"], r["bulan_asal"], r["bulan_seharusnya"], r["baru"]) for r in rows] == [
        ("je_pk37s_1", "2026-10", "2026-11", "2026-11-01")]
    capsys.readouterr()
    assert await mod.jalankan([], db=db) == 0
    keluar = capsys.readouterr().out
    assert f"{eid} · 2026-10 → 2026-11 · 1 jurnal · debit Rp 1.000.000" in keluar
    assert "S/JE-1: 2026-10-31T17:30:00+00:00 → 2026-11-01" in keluar
    assert "S/JE-2" not in keluar and "S/JE-3" not in keluar
    assert "Mode baca-saja" in keluar
    sesudah = [d async for d in db.journal_entries.find({"entity_id": eid}, {"_id": 0}).sort("id", 1)]
    assert sesudah == sebelum                                                   # database tidak berubah


async def test_PK37_U16b_terapkan_melewati_periode_tertutup(db):
    """`--terapkan` (lingkungan B saja): `date` → tanggal WIB + `date_asli`; jurnal di periode tertutup dilewati."""
    eid = "ent_uji_pk37t"
    dasar = {"description": "uji", "source_type": "uji", "status": "posted", "entity_id": eid, "lines": [],
             "total_credit": 0, "total_debit": 1}
    await db.journal_entries.insert_many([
        {**dasar, "id": "je_pk37t_1", "number": "T/JE-1", "date": "2026-10-31T17:30:00+00:00"},
        {**dasar, "id": "je_pk37t_2", "number": "T/JE-2", "date": "2026-08-31T18:00:00+00:00"}])
    await db.period_closings.insert_one({"id": "pc_pk37t", "entity_id": eid, "period_type": "month",
                                         "period_key": "2026-09", "start_date": "2026-09-01",
                                         "end_date": "2026-09-30", "status": "closed"})
    mod = _muat_skrip()
    assert await mod.jalankan(["--terapkan"], db=db) == 0
    j1 = await db.journal_entries.find_one({"id": "je_pk37t_1"}, {"_id": 0})
    j2 = await db.journal_entries.find_one({"id": "je_pk37t_2"}, {"_id": 0})
    assert (j1["date"], j1["date_asli"]) == ("2026-11-01", "2026-10-31T17:30:00+00:00")
    assert j2["date"] == "2026-08-31T18:00:00+00:00" and "date_asli" not in j2   # tujuan 1 Sep = periode tertutup
    assert await mod.jalankan(["--terapkan"], db=db) == 0                          # diulang: tidak berubah lagi
    assert (await db.journal_entries.find_one({"id": "je_pk37t_1"}, {"_id": 0}))["date_asli"] == \
        "2026-10-31T17:30:00+00:00"
