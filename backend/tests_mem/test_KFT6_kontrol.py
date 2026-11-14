"""KF-T6 serah-terima (a) — jalur baru kontrol "harus dua orang" (docs/blueprint/unit/KF-T6.md).

Butir: U1, U3 (bagian pembantu), U11, U16, U17 + bentuk katalog dan `GET /api/kontrol/aturan`. Titik lama belum
disentuh di serah-terima ini; pengalihannya diuji `test_KFT6_pengalihan.py`.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

import config_registry as registry
from services import config_resolver as resolver

pytestmark = pytest.mark.anyio

PESAN_PO = ("Persetujuan PO harus diputuskan orang lain: Anda yang mengajukannya. Minta rekan yang berwenang. "
            "Admin dapat mengubah aturan ini di Pengaturan › Persetujuan › Kontrol dua orang.")
AWAL_DUA = {"acc_desain", "acc_sample", "po_custom", "permintaan_pembelian", "harga_khusus", "amandemen",
            "setujui_po", "po_tingkat_berikut", "tagihan_pemasok", "biaya_masuk", "kontrabon", "tagihan_kampanye",
            "retur_antar_pt", "susut_makloon", "pengecualian_retur", "klaim_desain", "registrasi_stok_awal"}
BERNOMINAL = {"po_custom", "permintaan_pembelian", "amandemen", "setujui_po", "tagihan_pemasok", "biaya_masuk",
              "kontrabon", "tagihan_kampanye", "retur_antar_pt", "susut_makloon", "retur_penjualan",
              "retur_pembelian", "proses_gaji", "uang_muka", "lpj_uang_muka", "pengurang_piutang",
              "lewat_batas_kredit", "klaim_makloon", "nilai_pesanan", "jurnal_manual"}


def _kontrol():
    from config_catalog_kontrol import KONTROL_AKSI
    return KONTROL_AKSI


def _item(key, value, scope_type="entity", scope_id="ent_ksc", reason="uji KF-T6"):
    return {"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}


async def _cabut(klien, h, key, scope_id):
    r = await klien.post("/api/config/values/clear", headers=h,
                         json={"key": key, "scope_type": "entity", "scope_id": scope_id, "reason": "uji KF-T6"})
    assert r.status_code == 200, r.text


async def test_katalog_35_aksi_20_bernominal():
    aksi = [a["aksi"] for a in _kontrol()]
    assert len(aksi) == len(set(aksi)) == 35
    assert {a["aksi"] for a in _kontrol() if a["awal"] == "2"} == AWAL_DUA
    assert {a["aksi"] for a in _kontrol() if a["punya_nominal"]} == BERNOMINAL
    for a in aksi:
        e = registry.require(f"kontrol.{a}.min_orang")
        assert (e["type"], e["group"], e["scopes"], e["risk"], e["requires_reason"], e["permission"]) == (
            "enum", "persetujuan", ["global", "entity"], "high", True, ["settings", "manage"])
        assert [o["value"] for o in e["options"]] == ["1", "2"]
        assert e["default"] == ("2" if a in AWAL_DUA else "1")
        assert "services/dual_control.py:butuh_orang_kedua" in e["consumers"]
        b = registry.get(f"kontrol.{a}.batas_nominal")
        assert (b is not None) == (a in BERNOMINAL), a
        if b:
            assert (b["type"], b["default"], b["min"], b["max"], b["unit"]) == ("money", 0, 0, 1000000000000, "Rp")
    assert registry.require("kontrol.admin_boleh_sendiri")["default"] is True
    assert registry.require("kontrol.admin_tetap_dua_orang")["default"] == [
        "susut_makloon", "pengecualian_retur", "klaim_desain", "registrasi_stok_awal"]
    assert len([k for k in registry.keys() if k.startswith("kontrol.")]) == 57


async def test_U01_bawaan(aplikasi):
    from services.dual_control import butuh_orang_kedua
    assert await butuh_orang_kedua("setujui_po", "ent_ksc") is True
    assert await butuh_orang_kedua("transfer_gudang", "ent_ksc") is False
    assert await butuh_orang_kedua("buka_periode", "ent_ksc") is False
    with pytest.raises(KeyError):
        await butuh_orang_kedua("aksi_tak_ada", "ent_ksc")


async def test_pelaku_sama():
    from services.dual_control import pelaku_sama
    aktor = {"id": "usr_a", "name": "Rina", "email": "rina@uji.id"}
    assert pelaku_sama({}, aktor, ["usr_a"]) is True
    assert pelaku_sama({}, aktor, ["RINA"]) is True
    assert pelaku_sama({}, aktor, ["rina@uji.id"]) is True
    assert pelaku_sama({}, aktor, ["usr_b", "", None]) is False
    assert pelaku_sama({}, aktor, []) is False
    assert pelaku_sama({"created_by_id": "usr_a"}, aktor) is True          # tanpa `pengaju`: kolom baku dokumen
    assert pelaku_sama({"created_by_id": "usr_b"}, aktor) is False


async def test_U03_batas_nominal_pembantu(aplikasi, akun):
    from services.dual_control import butuh_orang_kedua, tolak_bila_pelaku_sama
    mgr = await akun("manager")
    await resolver.set_value("kontrol.uang_muka.batas_nominal", 5000000, scope_type="global",
                             reason="uji KF-T6 U3", actor="uji")
    try:
        assert await butuh_orang_kedua("uang_muka", "ent_ksc", 4000000) is False
        assert await butuh_orang_kedua("uang_muka", "ent_ksc", 5000000) is False
        assert await butuh_orang_kedua("uang_muka", "ent_ksc", 6000000) is True
        dok = {"id": "ca_uji", "entity_id": "ent_ksc", "created_by": mgr["name"]}
        hasil = await tolak_bila_pelaku_sama("uang_muka", dok, mgr, "ent_ksc", nominal=4000000,
                                             pengaju=[mgr["id"]])
        assert hasil == {"dua_orang": False, "sendiri": True, "admin_sendiri": False}
        with pytest.raises(HTTPException) as e:
            await tolak_bila_pelaku_sama("uang_muka", dok, mgr, "ent_ksc", nominal=6000000, pengaju=[mgr["id"]])
        assert e.value.status_code == 403
        assert e.value.detail.startswith("Uang muka / kasbon harus diputuskan orang lain")
    finally:
        await resolver.set_value("kontrol.uang_muka.batas_nominal", 0, scope_type="global",
                                 reason="uji KF-T6 U3 pulihkan", actor="uji")


async def test_pembantu_admin_dan_pesan(aplikasi, db, akun):
    from services.dual_control import tolak_bila_pelaku_sama
    adm = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    mgr = await akun("manager")
    dok = {"id": "po_uji_pembantu", "entity_id": "ent_ksc", "created_by_id": mgr["id"]}
    with pytest.raises(HTTPException) as e:
        await tolak_bila_pelaku_sama("setujui_po", dok, mgr, "ent_ksc", pengaju=[mgr["id"]])
    assert (e.value.status_code, e.value.detail) == (403, PESAN_PO)
    sebelum = await db.approval_matrix_log.count_documents({"outcome": "diputuskan sendiri oleh admin"})
    dok_adm = {**dok, "created_by_id": adm["id"]}
    hasil = await tolak_bila_pelaku_sama("setujui_po", dok_adm, adm, "ent_ksc", pengaju=[adm["id"]])
    assert hasil == {"dua_orang": True, "sendiri": True, "admin_sendiri": True}
    assert await db.approval_matrix_log.count_documents({"outcome": "diputuskan sendiri oleh admin"}) == sebelum + 1
    with pytest.raises(HTTPException):   # aksi di kontrol.admin_tetap_dua_orang
        await tolak_bila_pelaku_sama("pengecualian_retur", dok_adm, adm, "ent_ksc", pengaju=[adm["id"]])
    with pytest.raises(HTTPException):   # titik yang hanya bisa dijalankan Admin
        await tolak_bila_pelaku_sama("setujui_po", dok_adm, adm, "ent_ksc", pengaju=[adm["id"]],
                                     kecualikan_admin=False)
    assert (await tolak_bila_pelaku_sama("setujui_po", dok, adm, "ent_ksc", pengaju=[mgr["id"]]))["sendiri"] is False


async def test_aturan_endpoint(klien, kepala_admin):
    r = await klien.get("/api/kontrol/aturan", headers=kepala_admin, params={"entity_id": "ent_ksc"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(j["rows"]) == 35 and j["can_edit"] is True
    assert j["admin_boleh_sendiri"] is True
    assert j["admin_tetap_dua_orang"] == ["susut_makloon", "pengecualian_retur", "klaim_desain", "registrasi_stok_awal"]
    po = next(x for x in j["rows"] if x["aksi"] == "setujui_po")
    assert {k: po[k] for k in ("label", "kelompok", "punya_nominal", "min_orang", "batas_nominal", "sumber")} == {
        "label": "Persetujuan PO", "kelompok": "B", "punya_nominal": True, "min_orang": "2", "batas_nominal": 0.0,
        "sumber": "default"}
    tr = next(x for x in j["rows"] if x["aksi"] == "transfer_gudang")
    assert (tr["min_orang"], tr["batas_nominal"], tr["kelompok"]) == ("1", None, "C")
    r = await klien.get("/api/kontrol/aturan", headers=kepala_admin)
    assert r.status_code == 200 and r.json()["entity_id"] == ""


async def test_U11_tim_kecil_satu_pt(klien, kepala_admin):
    from services.dual_control import butuh_orang_kedua
    items = [_item(f"kontrol.{a['aksi']}.min_orang", "1", reason="Tim kecil — semua cukup satu orang")
             for a in _kontrol()]
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": items})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 35
    try:
        for a in _kontrol():
            assert await butuh_orang_kedua(a["aksi"], "ent_ksc") is False, a["aksi"]
        assert await butuh_orang_kedua("setujui_po", "ent_kanda") is True
        j = (await klien.get("/api/kontrol/aturan", headers=kepala_admin, params={"entity_id": "ent_ksc"})).json()
        assert {(x["min_orang"], x["sumber"]) for x in j["rows"]} == {("1", "entity")}
        j2 = (await klien.get("/api/kontrol/aturan", headers=kepala_admin, params={"entity_id": "ent_kanda"})).json()
        assert next(x for x in j2["rows"] if x["aksi"] == "setujui_po")["min_orang"] == "2"
    finally:
        for a in _kontrol():
            await _cabut(klien, kepala_admin, f"kontrol.{a['aksi']}.min_orang", "ent_ksc")
    assert await butuh_orang_kedua("setujui_po", "ent_ksc") is True


async def test_U16_sopir_ditolak(klien, akun, sesi, peran_sopir):
    u = await akun(peran_sopir)
    h = await sesi(u)
    r = await klien.get("/api/kontrol/aturan", headers=h)
    assert r.status_code == 403, r.text
    assert "kontrol dua orang" in r.json()["detail"] and "settings.view" not in r.json()["detail"]
    r = await klien.put("/api/config/values", headers=h,
                        json={"items": [_item("kontrol.setujui_po.min_orang", "1")]})
    assert r.status_code == 403, r.text


async def test_U16b_lihat_saja_tidak_bisa_ubah(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"settings": ["view"]}, label="Lihat Pengaturan KF-T6")
    h = await sesi(await akun(rid))
    r = await klien.get("/api/kontrol/aturan", headers=h, params={"entity_id": "ent_ksc"})
    assert r.status_code == 200, r.text
    assert r.json()["can_edit"] is False


def _lain(e, v):
    if e["type"] == "enum":
        return "1" if str(v) == "2" else "2"
    if e["type"] == "money":
        return float(v or 0) + 1000000
    if e["type"] == "bool":
        return not bool(v)
    if e["type"] == "list":
        return ["setujui_po"] if v != ["setujui_po"] else []
    raise AssertionError(e["type"])


_TAK_SAH = {"enum": "3", "money": -1, "bool": "bukan-bool", "list": "bukan-daftar"}


async def test_U17_putaran_semua_kunci_kontrol(klien, kepala_admin):
    kunci = [k for k in registry.keys() if k.startswith("kontrol.")]
    assert len(kunci) == 57
    for key in kunci:
        e = registry.require(key)
        awal = await resolver.value_of(key)
        v1 = _lain(e, awal)
        r = await klien.put("/api/config/values", headers=kepala_admin,
                            json={"items": [_item(key, v1, "global", "")]})
        assert r.status_code == 200, (key, r.text)
        assert await resolver.value_of(key) == v1, key
        v2 = _lain(e, v1) if e["type"] != "money" else float(v1) + 1000000
        r = await klien.put("/api/config/values", headers=kepala_admin,
                            json={"items": [_item(key, v2, "entity", "ent_kanda")]})
        assert r.status_code == 200, (key, r.text)
        assert await resolver.value_of(key, {"entity_id": "ent_kanda"}) == v2, key
        assert await resolver.value_of(key, {"entity_id": "ent_ksc"}) == v1, key
        r = await klien.put("/api/config/values", headers=kepala_admin,
                            json={"items": [_item(key, _TAK_SAH[e["type"]], "global", "")]})
        assert r.status_code == 400, (key, r.text)
        r = await klien.put("/api/config/values", headers=kepala_admin,
                            json={"items": [_item(key, v1, "global", "", reason="")]})
        assert r.status_code == 400 and "alasan" in r.json()["detail"].lower(), (key, r.text)
        await _cabut(klien, kepala_admin, key, "ent_kanda")
        r = await klien.put("/api/config/values", headers=kepala_admin,
                            json={"items": [_item(key, awal, "global", "")]})
        assert r.status_code == 200, (key, r.text)
        assert await resolver.value_of(key, {"entity_id": "ent_kanda"}) == awal, key
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json={"items": [_item("kontrol.setujui_po.batas_nominal", 1000000000001, "global", "")]})
    assert r.status_code == 400, r.text
