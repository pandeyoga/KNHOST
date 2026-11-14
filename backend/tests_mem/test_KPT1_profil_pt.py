"""KP-T1 — profil PT yang jujur dan bisa diubah (docs/blueprint/unit/KP-T1.md), uji U1–U16 di lingkungan B.

Seed lingkungan B: `ent_ksc` PKP (NPWP 15 digit), `ent_kanda` non-PKP (NPWP 15 digit), akun Admin. Tes satu modul
berbagi basis data dan berjalan menurut urutan berkas; urutan sengaja: U13 (Kanda masih non-PKP) sebelum U11 (Kanda
menjadi PKP), U12 (KSC dijadwalkan non-PKP) sebelum U16. Status "hari ini" = tanggal WIB (`analytics_time.now_wib`).

Fixture yang disisipkan langsung ke basis data: U7 (NPWP Kanda "abc"), U9 (satu pesanan penjualan `draft` Kanda),
U13 (NPWP Kanda dikosongkan). Selebihnya alur lewat API.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict

import pytest

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
MATI = ("numbering_scheme", "incentive_payer", "coa_template", "fiscal_year_start", "parent_entity_id")
PESAN_NPWP = "NPWP harus 15 atau 16 digit angka. Periksa kembali nomor yang diketik."
PESAN_PKP_PATCH = "Status PKP diubah lewat tindakan 'Ubah status PKP', bukan lewat ubah profil."
PESAN_PERSEN = "Persen kepemilikan harus lebih dari 0 dan paling banyak 100."


def _hari_ini() -> datetime.date:
    from services.analytics_time import now_wib
    return now_wib().date()


def _iso(d: datetime.date) -> str:
    return d.isoformat()


def _detail(r) -> str:
    try:
        d = r.json().get("detail")
    except Exception:  # noqa: BLE001 — jawaban bukan JSON (mis. 404 rute tidak ada)
        return r.text
    return d if isinstance(d, str) else str(d)


async def _pt(db, eid: str) -> Dict[str, Any]:
    return await db.business_entities.find_one({"id": eid}, {"_id": 0}) or {}


async def _buat(klien, h, **isi) -> Any:
    dasar = {"type": "PT", "default_tax_mode": "non_ppn"}
    return await klien.post("/api/entities", headers=h, json={**dasar, **isi})


# ── U1 — jawaban detail PT tanpa isian mati, dengan nilai registry ─────────────────────────────────────────────────
async def test_KPT1_U1_detail_pt_tanpa_isian_mati(klien, kepala_admin):
    r = await klien.get(f"/api/entities/{KSC}", headers=kepala_admin)
    assert r.status_code == 200, r.text
    d = r.json()
    hadir = [k for k in MATI if k in d]
    assert hadir == [], hadir
    # bawaan registry: tahun buku berakhir Desember, mata uang IDR; `currency` = mata uang pembukuan (bentuk daftar)
    assert (d["ownership_pct"], d["fiscal_year_end_month"], d["base_currency"], d["currency"]) == (100, 12, "IDR", "IDR")


# ── U2 — isian mati yang ikut dikirim saat membuat PT tidak tersimpan ──────────────────────────────────────────────
async def test_KPT1_U2_buat_pt_isian_mati_dibuang(klien, kepala_admin, db):
    r = await _buat(klien, kepala_admin, legal_name="PT Uji KPT1 Dua", short_name="KPT1DUA", doc_prefix="KPTDUA",
                    numbering_scheme="shared", incentive_payer="group")
    assert r.status_code == 200, r.text
    doc = await _pt(db, r.json()["id"])
    assert "numbering_scheme" not in doc and "incentive_payer" not in doc, sorted(doc)


# ── U3 — tahun buku & mata uang saat PT dibuat ditulis ke lapisan PT registry ──────────────────────────────────────
async def test_KPT1_U3_buat_pt_tahun_buku_dan_mata_uang(klien, kepala_admin):
    from services import closing_service
    from services.config_resolver import value_of
    r = await _buat(klien, kepala_admin, legal_name="PT Uji KPT1 Tiga", short_name="KPT1TIGA", doc_prefix="KPTTIGA",
                    fiscal_year_end_month=3, base_currency="USD")
    assert r.status_code == 200, r.text
    baru = r.json()["id"]
    assert await value_of("finance.fiscal_year_end_month", {"entity_id": baru}) == 3
    assert await value_of("finance.base_currency", {"entity_id": baru}) == "USD"
    assert await value_of("finance.fiscal_year_end_month", {"entity_id": KSC}) == 12   # PT lain tidak ikut
    # bulan tutup 3 → tahun buku 2026 = 1 April 2025 s/d 31 Maret 2026 (Maret 31 hari)
    assert await closing_service.period_bounds("year", "2026", baru) == ("2025-04-01", "2026-03-31")
    j = r.json()
    assert (j["fiscal_year_end_month"], j["fiscal_year_end_month_source"], j["base_currency"], j["currency"]) == (
        3, "entity", "USD", "USD")


# ── U4 — bulan tutup tahun buku tidak sah → 400, tidak ada PT baru ─────────────────────────────────────────────────
async def test_KPT1_U4_bulan_13_ditolak(klien, kepala_admin, db):
    sebelum = await db.business_entities.count_documents({})
    r = await _buat(klien, kepala_admin, legal_name="PT Uji KPT1 Empat", short_name="KPT1EMPAT",
                    doc_prefix="KPTEMPAT", fiscal_year_end_month=13)
    assert r.status_code == 400, r.text
    assert "1" in _detail(r) and "12" in _detail(r) and "finance." not in _detail(r)
    assert await db.business_entities.count_documents({}) == sebelum
    assert not await db.business_entities.find_one({"short_name": "KPT1EMPAT"})


# ── U5 — NPWP salah bentuk ditolak, NPWP lama tetap ───────────────────────────────────────────────────────────────
async def test_KPT1_U5_npwp_salah_bentuk(klien, kepala_admin, db):
    lama = (await _pt(db, KSC))["npwp"]
    r = await klien.patch(f"/api/entities/{KSC}", headers=kepala_admin, json={"data": {"npwp": "12345"}})
    assert r.status_code == 400, r.text
    assert _detail(r) == PESAN_NPWP
    assert (await _pt(db, KSC))["npwp"] == lama


# ── U6 — NPWP 15 (bertitik) dan 16 digit diterima; disimpan seperti diketik ───────────────────────────────────────
async def test_KPT1_U6_npwp_15_dan_16_digit(klien, kepala_admin, db):
    for npwp in ("01.234.567.8-901.000", "1234567890123456", " 01.234.567.8-901.000 "):
        r = await klien.patch(f"/api/entities/{KSC}", headers=kepala_admin, json={"data": {"npwp": npwp}})
        assert r.status_code == 200, (npwp, r.text)
        assert (await _pt(db, KSC))["npwp"] == npwp.strip()


# ── U7 — data lama tidak menghalangi perubahan isian lain ─────────────────────────────────────────────────────────
async def test_KPT1_U7_isian_lain_tidak_divalidasi_ulang(klien, kepala_admin, db):
    asli = (await _pt(db, KANDA))["npwp"]
    await db.business_entities.update_one({"id": KANDA}, {"$set": {"npwp": "abc"}})   # fixture: NPWP lama rusak
    try:
        r = await klien.patch(f"/api/entities/{KANDA}", headers=kepala_admin, json={"data": {"address": "Jl. Baru 1"}})
        assert r.status_code == 200, r.text
        assert (await _pt(db, KANDA))["address"] == "Jl. Baru 1"
    finally:
        await db.business_entities.update_one({"id": KANDA}, {"$set": {"npwp": asli}})


# ── U8 — status PKP tidak bisa diubah lewat ubah profil ───────────────────────────────────────────────────────────
async def test_KPT1_U8_status_pkp_tidak_lewat_patch(klien, kepala_admin, db):
    r = await klien.patch(f"/api/entities/{KANDA}", headers=kepala_admin, json={"data": {"default_tax_mode": "ppn"}})
    assert r.status_code == 400, r.text
    assert _detail(r) == PESAN_PKP_PATCH
    assert (await _pt(db, KANDA))["default_tax_mode"] == "non_ppn"


# ── U9 — pratinjau dampak menjadi PKP hari ini ────────────────────────────────────────────────────────────────────
async def test_KPT1_U9_pratinjau_dampak(klien, kepala_admin, db):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await db.sales_orders.insert_one({   # fixture: satu pesanan penjualan draf milik Kanda (seed tidak punya pesanan)
        "id": "so_uji_kpt1", "number": "KANDA/SO-KPT1-1", "entity_id": KANDA, "status": "draft", "items": [],
        "grand_total": 0, "created_at": now})
    hari = _iso(_hari_ini())
    r = await klien.get(f"/api/entities/{KANDA}/tax-status/preview", headers=kepala_admin,
                        params={"to": "ppn", "effective_date": hari})
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["entity_id"], p["current"], p["to"], p["effective_date"], p["applies"]) == (
        KANDA, "non_ppn", "ppn", hari, "sekarang")
    so = [d for d in p["open_documents"] if d["collection"] == "sales_orders"]
    assert len(so) == 1 and so[0]["count"] == 1 and so[0]["examples"] == ["KANDA/SO-KPT1-1"], p["open_documents"]
    assert p["npwp_ok"] is True and p["blockers"] == [] and p["can_apply"] is True
    assert p["documents_since"] == [] and p["tax_invoices_issued"] == 0
    assert {s["key"] for s in p["setting_layers"]} == {"tax.ppn_rate", "tax.efaktur_enabled"}


# ── U13 — menjadi PKP tanpa NPWP ditolak (dijalankan selagi Kanda masih non-PKP) ──────────────────────────────────
async def test_KPT1_U13_pkp_tanpa_npwp(klien, kepala_admin, db):
    asli = (await _pt(db, KANDA))["npwp"]
    await db.business_entities.update_one({"id": KANDA}, {"$set": {"npwp": ""}})   # fixture: NPWP dikosongkan
    try:
        r = await klien.post(f"/api/entities/{KANDA}/tax-status", headers=kepala_admin,
                             json={"to": "ppn", "effective_date": _iso(_hari_ini()), "reason": "x"})
        assert r.status_code == 400, r.text
        assert _detail(r) == "PT yang menjadi PKP wajib mengisi NPWP."
        assert (await _pt(db, KANDA))["default_tax_mode"] == "non_ppn"
        # pratinjau ikut menyebut penghalangnya
        p = (await klien.get(f"/api/entities/{KANDA}/tax-status/preview", headers=kepala_admin,
                             params={"to": "ppn", "effective_date": _iso(_hari_ini())})).json()
        assert p["npwp_ok"] is False and p["can_apply"] is False
        assert "PT yang menjadi PKP wajib mengisi NPWP." in p["blockers"]
    finally:
        await db.business_entities.update_one({"id": KANDA}, {"$set": {"npwp": asli}})


# ── U10 — alasan wajib ────────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT1_U10_alasan_wajib(klien, kepala_admin, db):
    r = await klien.post(f"/api/entities/{KANDA}/tax-status", headers=kepala_admin,
                         json={"to": "ppn", "effective_date": _iso(_hari_ini()), "reason": ""})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Alasan perubahan status PKP wajib diisi."
    assert (await _pt(db, KANDA))["default_tax_mode"] == "non_ppn"


# ── U11 — menjadi PKP hari ini: status, riwayat, tarif PPN efektif, jejak ─────────────────────────────────────────
async def test_KPT1_U11_menjadi_pkp_hari_ini(klien, kepala_admin, db):
    from services.config_service import get_effective_settings
    sebelum_kanda = (await get_effective_settings(KANDA))["tax"]
    sebelum_ksc = (await get_effective_settings(KSC))["tax"]
    assert sebelum_kanda["ppn_rate"] == 0.0              # non-PKP dipaksa 0 (config_service.get_effective_settings)
    r = await klien.post(f"/api/entities/{KANDA}/tax-status", headers=kepala_admin,
                         json={"to": "ppn", "effective_date": _iso(_hari_ini()), "reason": "Dikukuhkan PKP"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["default_tax_mode"] == "ppn" and j["is_pkp"] is True and j.get("tax_status_pending") in (None, {})
    hist = j["tax_status_history"]
    assert [(h["from"], h["to"], h["reason"], h["effective_date"]) for h in hist] == [
        ("non_ppn", "ppn", "Dikukuhkan PKP", _iso(_hari_ini()))]
    assert hist[0]["by"] and hist[0]["at"]
    doc = await _pt(db, KANDA)
    assert doc["default_tax_mode"] == "ppn" and len(doc["tax_status_history"]) == 1
    # tarif global seed 12 % kini dipakai Kanda; KSC tidak berubah
    assert (await get_effective_settings(KANDA))["tax"]["ppn_rate"] == 12.0
    assert (await get_effective_settings(KSC))["tax"] == sebelum_ksc
    jejak = await db.audit_logs.find_one({"action": "entity_tax_status_changed", "entity_id": KANDA})
    assert jejak, "jejak entity_tax_status_changed tidak ada"


# ── U12 — perubahan bertanggal maju diterapkan pada tanggalnya ────────────────────────────────────────────────────
async def test_KPT1_U12_jadwal_diterapkan_pada_tanggalnya(klien, kepala_admin, db):
    from services import entity_lifecycle_service as lifecycle
    hari, besok = _hari_ini(), _hari_ini() + datetime.timedelta(days=1)
    r = await klien.post(f"/api/entities/{KSC}/tax-status", headers=kepala_admin,
                         json={"to": "non_ppn", "effective_date": _iso(besok), "reason": "Dicabut"})
    assert r.status_code == 200, r.text
    assert r.json()["tax_status_pending"]["to"] == "non_ppn"
    doc = await _pt(db, KSC)
    riwayat_awal = len(doc.get("tax_status_history") or [])
    assert doc["default_tax_mode"] == "ppn" and doc["tax_status_pending"]["effective_date"] == _iso(besok)
    assert await db.audit_logs.find_one({"action": "entity_tax_status_scheduled", "entity_id": KSC})

    assert await lifecycle.apply_due_tax_status(today=_iso(hari)) == 0
    assert (await _pt(db, KSC))["default_tax_mode"] == "ppn"
    assert await lifecycle.apply_due_tax_status(today=_iso(besok)) == 1
    doc = await _pt(db, KSC)
    assert doc["default_tax_mode"] == "non_ppn"
    assert len(doc["tax_status_history"]) == riwayat_awal + 1
    assert (doc["tax_status_history"][-1]["from"], doc["tax_status_history"][-1]["to"]) == ("ppn", "non_ppn")
    assert "tax_status_pending" not in doc
    assert await lifecycle.apply_due_tax_status(today=_iso(besok)) == 0       # ulang: tidak ada yang tersisa


async def test_KPT1_U12b_batalkan_jadwal(klien, kepala_admin, db):
    """Pelengkap U12 — `DELETE …/tax-status/pending`: 404 bila tidak ada jadwal; menghapus jadwal tanpa mengubah status."""
    r = await klien.delete(f"/api/entities/{KSC}/tax-status/pending", headers=kepala_admin)
    assert r.status_code == 404, r.text
    besok = _iso(_hari_ini() + datetime.timedelta(days=1))
    r = await klien.post(f"/api/entities/{KSC}/tax-status", headers=kepala_admin,
                         json={"to": "ppn", "effective_date": besok, "reason": "Rencana dikukuhkan"})
    assert r.status_code == 200, r.text
    r = await klien.delete(f"/api/entities/{KSC}/tax-status/pending", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json().get("tax_status_pending") in (None, {})
    doc = await _pt(db, KSC)
    assert "tax_status_pending" not in doc and doc["default_tax_mode"] == "non_ppn"


# ── U14 — PT induk & persen kepemilikan ───────────────────────────────────────────────────────────────────────────
async def test_KPT1_U14_pt_induk_dan_kepemilikan(klien, kepala_admin, db):
    from services import consolidation_service
    r = await klien.patch(f"/api/entities/{KSC}", headers=kepala_admin,
                          json={"data": {"is_group": True, "ownership_pct": 60}})
    assert r.status_code == 200, r.text
    try:
        rows = {e["id"]: e for e in (await klien.get("/api/entities", headers=kepala_admin)).json()}
        assert (rows[KSC]["is_group"], rows[KSC]["ownership_pct"]) == (True, 60)
        assert (rows[KANDA]["is_group"], rows[KANDA]["ownership_pct"]) == (False, 100)
        ring = await consolidation_service.summary([KSC, KANDA], 2026, "2026-12-31")
        assert [e["entity_id"] for e in ring["entities"]] == [KANDA]
    finally:
        await db.business_entities.update_one({"id": KSC}, {"$set": {"is_group": False, "ownership_pct": 100.0}})


# ── U15 — persen kepemilikan di luar (0, 100] ditolak ─────────────────────────────────────────────────────────────
async def test_KPT1_U15_persen_kepemilikan_di_luar_batas(klien, kepala_admin, db):
    for nilai in (0, 101):
        r = await klien.patch(f"/api/entities/{KSC}", headers=kepala_admin, json={"data": {"ownership_pct": nilai}})
        assert r.status_code == 400, (nilai, r.text)
        assert _detail(r) == PESAN_PERSEN, nilai
    assert (await _pt(db, KSC)).get("ownership_pct", 100) == 100


# ── U16 — izin `entity.update`, bukan nama peran ──────────────────────────────────────────────────────────────────
async def test_KPT1_U16_izin_bukan_peran(klien, akun, sesi, db, kepala_admin, peran_tanpa_acuan, peran_manajer_kosong):
    ta = await sesi(await akun(await peran_tanpa_acuan({"entity": ["update"]}, label="TA KPT1 ubah PT")))
    mk = await sesi(await akun(await peran_manajer_kosong()))
    kini = (await _pt(db, KSC))["default_tax_mode"]
    isi = {"to": "ppn" if kini == "non_ppn" else "non_ppn",
           "effective_date": _iso(_hari_ini() + datetime.timedelta(days=1)), "reason": "uji izin KP-T1"}
    r_mk = await klien.post(f"/api/entities/{KSC}/tax-status", headers=mk, json=isi)
    assert r_mk.status_code == 403, r_mk.text
    assert _detail(r_mk).startswith("Anda belum punya akses untuk") and "entity." not in _detail(r_mk)
    r_ta = await klien.post(f"/api/entities/{KSC}/tax-status", headers=ta, json=isi)
    assert r_ta.status_code == 200, r_ta.text
    assert (await klien.delete(f"/api/entities/{KSC}/tax-status/pending", headers=kepala_admin)).status_code == 200


async def test_KPT1_U16b_pratinjau_dan_batal_ikut_izin(klien, akun, sesi, peran_manajer_kosong):
    """Pelengkap U16 — pratinjau dan batal jadwal memakai izin yang sama (Manajer Kosong → 403)."""
    mk = await sesi(await akun(await peran_manajer_kosong()))
    r = await klien.get(f"/api/entities/{KSC}/tax-status/preview", headers=mk,
                        params={"to": "ppn", "effective_date": _iso(_hari_ini())})
    assert r.status_code == 403, r.text
    assert (await klien.delete(f"/api/entities/{KSC}/tax-status/pending", headers=mk)).status_code == 403


async def test_KPT1_U9b_tanggal_mundur_dan_pt_terarsip(klien, kepala_admin, db):
    """Pelengkap U9 — tanggal mundur: `applies` "sekarang" dan `documents_since` terisi; PT terarsip → 409."""
    kemarin = _iso(_hari_ini() - datetime.timedelta(days=1))
    p = (await klien.get(f"/api/entities/{KANDA}/tax-status/preview", headers=kepala_admin,
                         params={"to": "non_ppn", "effective_date": "2020-01-01"})).json()
    assert p["applies"] == "sekarang"
    since = {d["collection"]: d["count"] for d in p["documents_since"]}
    assert since.get("sales_orders") == 1, p["documents_since"]
    r = await klien.get(f"/api/entities/{KANDA}/tax-status/preview", headers=kepala_admin,
                        params={"to": "non_ppn", "effective_date": "2026-13-40"})
    assert r.status_code == 400 and _detail(r) == "Tanggal berlaku tidak valid."
    r = await klien.get(f"/api/entities/{KANDA}/tax-status/preview", headers=kepala_admin,
                        params={"to": "ppn", "effective_date": kemarin})
    assert r.json()["blockers"] == ["PT ini sudah berstatus PKP."] and r.json()["can_apply"] is False
    await db.business_entities.update_one({"id": "ent_uji_kpt1_arsip"}, {"$set": {
        "id": "ent_uji_kpt1_arsip", "legal_name": "PT Arsip KPT1", "short_name": "ARSKPT1", "status": "archived",
        "default_tax_mode": "non_ppn"}}, upsert=True)
    from services.entity_lifecycle_service import invalidate_status_cache
    invalidate_status_cache()          # fixture disisip langsung: cache status PT (20 detik) dibuang
    r = await klien.post("/api/entities/ent_uji_kpt1_arsip/tax-status", headers=kepala_admin,
                         json={"to": "non_ppn", "effective_date": kemarin, "reason": "x"})
    assert r.status_code == 409 and _detail(r) == "PT ini sudah diarsipkan.", r.text
