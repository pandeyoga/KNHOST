"""KF-T4 — tombol pengembali berarti persis seperti labelnya (KF-12), cakupan grup jujur, riwayat bersaring:
U5, U6, U7, U13 + pelengkap riwayat (docs/blueprint/unit/KF-T4.md).

`kepala_admin` = admin seed (lintas PT). PT seed `ent_ksc` (PKP) dan `ent_kanda` (bukan PKP). Satu basis data per modul;
urutan uji di berkas ini disengaja (U6 → U7 memakai keadaan grup = 6).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


def _put(key, value, *, scope_type="global", scope_id="", reason="uji KF-T4"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id,
                       "reason": reason}]}


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _item(klien, hdr, key, entity_id=""):
    r = await klien.get("/api/config/effective", headers=hdr, params={"q": key, "entity_id": entity_id})
    assert r.status_code == 200, r.text
    items = [it for it in r.json()["items"] if it["key"] == key]
    assert len(items) == 1, r.json()
    return items[0]


# ── U5 — kunci berisiko tinggi: kembalikan/cabut tanpa alasan ditolak, tidak ada alasan otomatis ─────────────────────
async def test_KFT4_U5_kembalikan_dan_cabut_wajib_alasan_kunci_berisiko(klien, kepala_admin):
    h = kepala_admin
    assert (await klien.put("/api/config/values", headers=h, json=_put("tax.ppn_rate", 11))).status_code == 200
    r = await klien.put("/api/config/values", headers=h, json=_put("tax.ppn_mode", "included", scope_type="entity",
                                                                    scope_id="ent_kanda"))
    assert r.status_code == 200, r.text

    r = await klien.post("/api/config/values/reset", headers=h, json={"key": "tax.ppn_rate", "scope_type": "global"})
    assert r.status_code == 400, r.text
    assert _detail(r) == "'Tarif PPN' berisiko tinggi — alasan wajib diisi."
    assert (await _item(klien, h, "tax.ppn_rate"))["value"] == 11
    r = await klien.post("/api/config/values/reset", headers=h,
                         json={"key": "tax.ppn_rate", "scope_type": "global", "reason": "kembali ke tarif UU"})
    assert r.status_code == 200, r.text
    assert r.json()["reason"] == "kembali ke tarif UU"
    assert (await _item(klien, h, "tax.ppn_rate"))["value"] == 12

    body = {"key": "tax.ppn_mode", "scope_type": "entity", "scope_id": "ent_kanda"}
    r = await klien.post("/api/config/values/clear", headers=h, json=body)
    assert r.status_code == 400, r.text
    assert "alasan wajib diisi" in _detail(r)
    assert (await _item(klien, h, "tax.ppn_mode", "ent_kanda"))["source_layer"] == "entity"
    r = await klien.post("/api/config/values/clear", headers=h, json={**body, "reason": "ikut grup lagi"})
    assert r.status_code == 200, r.text
    it = await _item(klien, h, "tax.ppn_mode", "ent_kanda")
    assert it["value"] == "excluded" and it["source_layer"] != "entity"


# ── U6 — "Ikuti nilai grup" mencabut lapisan PT: PT kembali mengikuti grup ───────────────────────────────────────────
async def test_KFT4_U6_cabut_lapisan_pt_kembali_mengikuti_grup(klien, kepala_admin):
    h = kepala_admin
    assert (await klien.put("/api/config/values", headers=h, json=_put("ar.grace_days", 5))).status_code == 200
    r = await klien.put("/api/config/values", headers=h,
                        json=_put("ar.grace_days", 9, scope_type="entity", scope_id="ent_kanda"))
    assert r.status_code == 200, r.text
    assert (await _item(klien, h, "ar.grace_days", "ent_kanda"))["value"] == 9

    r = await klien.post("/api/config/values/clear", headers=h,
                         json={"key": "ar.grace_days", "scope_type": "entity", "scope_id": "ent_kanda"})
    assert r.status_code == 200, r.text
    # Kunci tidak wajib alasan → alasan bawaan yang berarti persis tindakannya.
    assert r.json()["reason"] == "Kembali mengikuti nilai grup"
    it = await _item(klien, h, "ar.grace_days", "ent_kanda")
    assert (it["value"], it["source_layer"]) == (5, "global")
    assert (await klien.put("/api/config/values", headers=h, json=_put("ar.grace_days", 6))).status_code == 200
    assert (await _item(klien, h, "ar.grace_days", "ent_kanda"))["value"] == 6


# ── U7 — "Pakai nilai bawaan sistem untuk PT ini" = nilai khusus PT berisi bawaan ────────────────────────────────────
async def test_KFT4_U7_bawaan_sistem_untuk_pt_tidak_ikut_grup(klien, kepala_admin):
    h = kepala_admin
    r = await klien.post("/api/config/values/reset", headers=h,
                         json={"key": "ar.grace_days", "scope_type": "entity", "scope_id": "ent_kanda"})
    assert r.status_code == 200, r.text
    assert r.json()["reason"] == "Dikembalikan ke nilai bawaan sistem"
    it = await _item(klien, h, "ar.grace_days", "ent_kanda")
    assert (it["value"], it["source_layer"]) == (0, "entity")   # bawaan registry ar.grace_days = 0
    assert (await klien.put("/api/config/values", headers=h, json=_put("ar.grace_days", 7))).status_code == 200
    assert (await _item(klien, h, "ar.grace_days", "ent_kanda"))["value"] == 0
    assert (await _item(klien, h, "ar.grace_days", "ent_ksc"))["value"] == 7


# ── U13 — cakupan grup: nilai grup tanpa lapisan PT + daftar PT yang menyimpang ──────────────────────────────────────
async def test_KFT4_U13_cakupan_grup_memuat_pt_bernilai_sendiri(klien, kepala_admin):
    h = kepala_admin
    r = await klien.put("/api/config/values", headers=h, json=_put("tax.ppn_mode", "excluded"))
    assert r.status_code == 200, r.text
    r = await klien.put("/api/config/values", headers=h, json=_put("tax.ppn_mode", "included", scope_type="entity",
                                                                    scope_id="ent_kanda"))
    assert r.status_code == 200, r.text
    r = await klien.get("/api/config/effective", headers=h,
                        params={"group": "pajak-pembukuan", "scope": "global", "entity_id": "ent_kanda"})
    assert r.status_code == 200, r.text
    it = next(x for x in r.json()["items"] if x["key"] == "tax.ppn_mode")
    assert it["value"] == "excluded"
    assert {"entity_id": "ent_kanda", "value": "included"}.items() <= next(
        o for o in it["entity_overrides"] if o["entity_id"] == "ent_kanda").items()
    assert all(o["entity_id"] != "ent_ksc" for o in it["entity_overrides"])
    kanda = next(o for o in it["entity_overrides"] if o["entity_id"] == "ent_kanda")
    assert kanda["entity_label"] and not kanda["entity_label"].startswith("ent_")
    # Tanpa `scope=global`, PT yang diminta tetap memakai nilai khususnya.
    assert (await _item(klien, h, "tax.ppn_mode", "ent_kanda"))["value"] == "included"


# ── pelengkap — riwayat bersaring + jumlah total ─────────────────────────────────────────────────────────────────────
async def test_KFT4_riwayat_saring_kelompok_orang_tanggal_halaman(klien, kepala_admin):
    h = kepala_admin
    r = await klien.get("/api/config/history", headers=h, params={"group": "uang-masuk", "limit": 2})
    assert r.status_code == 200, r.text
    j = r.json()
    # U6/U7: ar.grace_days diubah 5× (grup 5, PT 9, cabut, grup 6, bawaan PT, grup 7) di kelompok Pembayaran pelanggan.
    assert j["total"] >= 6 and len(j["rows"]) == 2
    assert {x["group"] for x in j["rows"]} == {"pembayaran-pelanggan"}
    r2 = await klien.get("/api/config/history", headers=h, params={"group": "pembayaran-pelanggan", "limit": 2,
                                                                     "offset": 2})
    assert r2.json()["total"] == j["total"]
    assert {x["id"] for x in r2.json()["rows"]}.isdisjoint({x["id"] for x in j["rows"]})
    nama = j["rows"][0]["changed_by"]
    r = await klien.get("/api/config/history", headers=h, params={"changed_by": nama[:4].lower()})
    assert r.json()["total"] >= j["total"]
    r = await klien.get("/api/config/history", headers=h, params={"date_from": "2000-01-01", "date_to": "2000-01-02"})
    assert r.status_code == 200 and r.json()["total"] == 0
    r = await klien.get("/api/config/history", headers=h, params={"date_from": "kemarin"})
    assert r.status_code == 400
