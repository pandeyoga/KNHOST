"""KF-T3 — layar menampilkan nilai yang dipakai mesin; jadwal diaktifkan penjadwal (docs/blueprint/unit/KF-T3.md).

Serah-terima (a): U1–U9 — penimpaan terdaftar (`services/config_overrides.py`), `ensure_due_applied`, job penjadwal
`config_apply_due`, dan pembatalan jadwal `POST /api/config/values/cancel-scheduled`.

Peran: `kepala_admin` = admin seed (lintas PT). PT seed `ent_ksc` (PKP) dan `ent_kanda` (bukan PKP). Satu basis data per
modul; urutan uji di berkas ini disengaja (U5 → U8 memakai baris jadwal yang sudah berlaku).
"""
from __future__ import annotations

import asyncio
import datetime as dt

import pytest

pytestmark = pytest.mark.anyio

SUDAH_BERLAKU = "Perubahan ini sudah berlaku, jadi tidak bisa dibatalkan. Simpan nilai baru bila ingin mengubahnya."
SUDAH_BATAL = "Jadwal ini sudah dibatalkan."


def _put(key, value, *, scope_type="global", scope_id="", reason="uji KF-T3", effective_from=""):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id,
                       "reason": reason, "effective_from": effective_from}]}


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


def _nanti(**delta) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(**delta)).isoformat()


async def _item(klien, hdr, key, entity_id=""):
    r = await klien.get("/api/config/effective", headers=hdr, params={"q": key, "entity_id": entity_id})
    assert r.status_code == 200, r.text
    items = [it for it in r.json()["items"] if it["key"] == key]
    assert len(items) == 1, r.json()
    return items[0]


# ── U1 — PT bukan PKP: tarif PPN yang dipakai mesin = 0, nilai tersimpan tetap terlihat ─────────────────────────────
async def test_KFT3_U1_ppn_pt_bukan_pkp_ditimpa_status_pajak(klien, kepala_admin):
    from services.config_resolver import value_of
    from services.config_service import get_effective_settings
    # Seed: ent_kanda `default_tax_mode != "ppn"`; tarif grup bawaan registry 12.0.
    it = await _item(klien, kepala_admin, "tax.ppn_rate", "ent_kanda")
    assert it["value"] == 0
    assert it["stored_value"] == 12.0
    assert it["overridden_by"]["id"] == "pt_bukan_pkp"
    assert it["overridden_by"]["label"] == "Status pajak PT ini: bukan PKP"
    assert it["overridden_by"]["link"] == {"view": "entities-access"}
    mesin = await value_of("tax.ppn_rate", {"entity_id": "ent_kanda"})
    lama = (await get_effective_settings("ent_kanda"))["tax"]["ppn_rate"]
    assert mesin == 0 and lama == 0


# ── U2 — PT PKP: tidak ada penimpa ────────────────────────────────────────────────────────────────────────────────────
async def test_KFT3_U2_ppn_pt_pkp_tanpa_penimpa(klien, kepala_admin):
    from services.config_resolver import value_of
    from services.config_service import get_effective_settings
    it = await _item(klien, kepala_admin, "tax.ppn_rate", "ent_ksc")
    assert it["value"] == 12.0
    assert it["overridden_by"] is None
    assert it["stored_value"] == 12.0
    assert await value_of("tax.ppn_rate", {"entity_id": "ent_ksc"}) == 12.0
    assert (await get_effective_settings("ent_ksc"))["tax"]["ppn_rate"] == 12.0


# ── U3 — "wajib transfer antar-PT" mematikan izin memakai stok PT lain; per PT ──────────────────────────────────────
async def test_KFT3_U3_wajib_transfer_menimpa_izin_stok_pt_lain(klien, kepala_admin):
    from services.config_resolver import value_of
    from services.config_service import get_allocation_policy
    key = "allocation.allow_intercompany"
    awal = await _item(klien, kepala_admin, key, "ent_ksc")
    # Bawaan: allow_intercompany True, intercompany_transfer_required True → mesin memakai False.
    assert awal["value"] is False
    assert awal["stored_value"] is True
    assert awal["overridden_by"]["id"] == "wajib_transfer_antar_pt"
    assert awal["overridden_by"]["link"] == {"key": "inventory.intercompany_transfer_required"}
    assert awal["overridden_by"]["label"] == (
        "Pengaturan “Wajib transfer sebelum menjual stok PT lain” sedang aktif")
    assert (await get_allocation_policy("ent_ksc"))["allow_intercompany"] == await value_of(key, {"entity_id": "ent_ksc"})

    r = await klien.put("/api/config/values", headers=kepala_admin, json=_put(
        "inventory.intercompany_transfer_required", False, scope_type="entity", scope_id="ent_ksc",
        reason="uji KF-T3 — KSC boleh menjual stok PT lain"))
    assert r.status_code == 200, r.text

    ksc = await _item(klien, kepala_admin, key, "ent_ksc")
    assert ksc["value"] is True and ksc["overridden_by"] is None
    assert (await get_allocation_policy("ent_ksc"))["allow_intercompany"] is True
    assert await value_of(key, {"entity_id": "ent_ksc"}) is True
    kanda = await _item(klien, kepala_admin, key, "ent_kanda")
    assert kanda["value"] is False and kanda["overridden_by"]["id"] == "wajib_transfer_antar_pt"
    assert (await get_allocation_policy("ent_kanda"))["allow_intercompany"] is False
    assert await value_of(key, {"entity_id": "ent_kanda"}) is False


# ── U4 — batas poin di Master Grade Mutu menang atas ambang Pusat Pengaturan ────────────────────────────────────────
async def test_KFT3_U4_master_grade_menimpa_ambang_poin(klien, kepala_admin):
    from services.config_resolver import value_of
    key = "qc.grade_thresholds.a_max"
    # Alur: Admin mengisi batas poin grade A = 18 di Master Grade Mutu.
    r = await klien.patch("/api/master/grades/A", headers=kepala_admin, json={"max_points": 18})
    assert r.status_code == 200, r.text
    try:
        assert await value_of(key) == 18
        r = await klien.get("/api/config/explain", headers=kepala_admin, params={"key": key})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["value"] == 18 and j["stored_value"] == 20.0
        assert j["overridden_by"]["id"] == "master_grade_mutu"
        terakhir = j["explain"][-1]
        assert terakhir["layer"] == "override" and terakhir["winner"] is True
        assert terakhir["label"] == "Ditimpa aturan lain" and terakhir["note"] == "Batas poin di Master Grade Mutu"
        assert sum(1 for lay in j["explain"] if lay.get("winner")) == 1
        assert "override" in j["layer_order"]
        # Grade B tanpa batas poin di master → ambang Pusat Pengaturan tetap dipakai.
        assert await value_of("qc.grade_thresholds.b_max") == 40.0
    finally:
        r = await klien.patch("/api/master/grades/A", headers=kepala_admin, json={"max_points": None})
        assert r.status_code == 200, r.text


# ── U5 — jadwal jatuh tempo terbaca pembaca lama tanpa membuka layar ────────────────────────────────────────────────
async def test_KFT3_U5_jadwal_jatuh_tempo_terbaca_pembaca_lama(klien, kepala_admin):
    from services.config_resolver import value_of
    from services.config_service import get_effective_settings
    key = "ar.grace_days"
    awal = int(await value_of(key))
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_put(key, awal + 5, effective_from=_nanti(seconds=2)))
    assert r.status_code == 200, r.text
    assert (await get_effective_settings(None))["ar"]["grace_days"] == awal       # belum jatuh tempo
    await asyncio.sleep(3)
    # Tanpa memanggil endpoint mana pun (dulu hanya `/config/effective` & `/config/health` yang menerapkan jadwal).
    lama = (await get_effective_settings(None))["ar"]["grace_days"]
    assert lama == await value_of(key) == awal + 5


# ── U6 — job penjadwal menerapkan baris yang jatuh tempo ────────────────────────────────────────────────────────────
async def test_KFT3_U6_job_penjadwal_aktifkan_pengaturan_terjadwal(db):
    from core_utils import new_id, now_iso
    from services import scheduler_service as sch
    job = sch.JOB_MAP["config_apply_due"]
    assert job["kind"] == "interval" and job["interval_minutes"] == 5
    assert job["label"] == "Aktifkan Pengaturan Terjadwal" and job["link"] == "settings-config"
    assert job["description"] == "Menerapkan perubahan pengaturan yang tanggal berlakunya sudah tiba."
    # Fixture (sisip langsung): baris jadwal yang waktunya sudah tiba tetapi belum diterapkan siapa pun.
    lalu = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)).isoformat()
    await db.config_values.insert_one({
        "id": new_id("cfgv"), "key": "inventory.min_cut_qty", "scope_type": "global", "scope_id": "",
        "value": 2.5, "prev_value": 0.5, "prev_source_layer": "code_default", "effective_from": lalu,
        "effective_to": "", "reason": "uji KF-T3 U6", "changed_by": "Uji", "changed_by_id": "", "approved_by": "",
        "risk": "medium", "changed_at": now_iso(), "created_at": now_iso(), "applied_at": ""})
    res = await job["fn"]()
    assert res["applied"] == 1
    doc = await db.system_settings.find_one({"scope": "global"}, {"_id": 0})
    assert doc["inventory"]["min_cut_qty"] == 2.5
    assert (await job["fn"]())["applied"] == 0                                     # idempoten


# ── U7 — membatalkan jadwal ─────────────────────────────────────────────────────────────────────────────────────────
async def _jadwalkan(klien, hdr, key="ar.grace_days", value=11):
    r = await klien.put("/api/config/values", headers=hdr, json=_put(key, value, effective_from=_nanti(hours=1)))
    assert r.status_code == 200, r.text
    return r.json()["saved"][0]


async def test_KFT3_U7_batalkan_jadwal(klien, kepala_admin, db):
    from services.config_resolver import resolve
    row = await _jadwalkan(klien, kepala_admin)
    sched = (await resolve("ar.grace_days"))["scheduled"]
    assert [s["id"] for s in sched] == [row["id"]]
    assert sched[0]["scope_type"] == "global" and sched[0]["scope_id"] == ""

    r = await klien.post("/api/config/values/cancel-scheduled", headers=kepala_admin,
                         json={"id": row["id"], "reason": "uji KF-T3 — tidak jadi"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["id"] == row["id"] and j["cancelled_at"]
    assert j["cancel_reason"] == "uji KF-T3 — tidak jadi" and j["cancelled_by"]
    assert (await resolve("ar.grace_days"))["scheduled"] == []

    r = await klien.post("/api/config/values/cancel-scheduled", headers=kepala_admin,
                         json={"id": row["id"], "reason": "lagi"})
    assert r.status_code == 409, r.text
    assert _detail(r) == SUDAH_BATAL

    # Riwayat menandai baris yang dibatalkan.
    h = await klien.get("/api/config/history", headers=kepala_admin, params={"key": "ar.grace_days"})
    baris = [x for x in h.json()["rows"] if x["id"] == row["id"]]
    assert baris and baris[0]["cancelled"] is True and baris[0]["scheduled"] is False


async def test_KFT3_U7b_jadwal_tak_ada_dan_alasan_wajib(klien, kepala_admin):
    r = await klien.post("/api/config/values/cancel-scheduled", headers=kepala_admin,
                         json={"id": "cfgv_tidak_ada", "reason": "x"})
    assert r.status_code == 404, r.text
    assert _detail(r) == "Jadwal perubahan tidak ditemukan."
    # `tax.ppn_rate` berisiko tinggi → alasan pembatalan wajib.
    row = await _jadwalkan(klien, kepala_admin, "tax.ppn_rate", 11.0)
    r = await klien.post("/api/config/values/cancel-scheduled", headers=kepala_admin, json={"id": row["id"], "reason": " "})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Alasan pembatalan wajib diisi."
    r = await klien.post("/api/config/values/cancel-scheduled", headers=kepala_admin,
                         json={"id": row["id"], "reason": "uji KF-T3 — tarif tidak jadi"})
    assert r.status_code == 200, r.text


# ── U8 — baris yang sudah berlaku tidak bisa dibatalkan ─────────────────────────────────────────────────────────────
async def test_KFT3_U8_yang_sudah_berlaku_tidak_bisa_dibatalkan(klien, kepala_admin, db):
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_put("ar.grace_days", 4))
    assert r.status_code == 200, r.text
    row_id = r.json()["saved"][0]["id"]
    sebelum = await db.config_values.find_one({"id": row_id}, {"_id": 0})
    assert sebelum["applied_at"]
    r = await klien.post("/api/config/values/cancel-scheduled", headers=kepala_admin,
                         json={"id": row_id, "reason": "uji KF-T3"})
    assert r.status_code == 409, r.text
    assert _detail(r) == SUDAH_BERLAKU
    assert await db.config_values.find_one({"id": row_id}, {"_id": 0}) == sebelum


# ── U9 — Sopir tidak berwenang ──────────────────────────────────────────────────────────────────────────────────────
async def test_KFT3_U9_sopir_tidak_bisa_membatalkan(klien, kepala_admin, akun, sesi, peran_sopir, db):
    row = await _jadwalkan(klien, kepala_admin, value=13)
    sopir = await sesi(await akun(peran_sopir))
    r = await klien.post("/api/config/values/cancel-scheduled", headers=sopir,
                         json={"id": row["id"], "reason": "uji KF-T3"})
    assert r.status_code == 403, r.text
    assert "Anda belum punya akses untuk mengubah pengaturan" in _detail(r)
    assert "cancelled_at" not in (await db.config_values.find_one({"id": row["id"]}, {"_id": 0}))
