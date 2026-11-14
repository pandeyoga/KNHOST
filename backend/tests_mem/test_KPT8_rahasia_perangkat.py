"""KP-T8 — rahasia dan perangkat (docs/blueprint/unit/KP-T8.md, uji penerimaan U1–U15).

Satu modul = satu database tiruan; urutan uji disengaja: mesin absen (U1–U6) → token WhatsApp dibungkus (U7–U9) →
koneksi tunggal dan migrasi (U10–U12) → izin integrasi (U14 sebelum U13: peran U13 dibuat SESUDAH migrasi) → dua kunci
registry (U15). Skrip migrasi dijalankan di database tiruan saja (titik henti H3: data nyata dijalankan pemilik).

`KN_SECRETS_KEY` diisi kunci uji yang dibuat di dalam tes (`Fernet.generate_key()`), kecuali U8. Semua token di berkas
ini palsu (H8: unit tidak meminta rahasia apa pun).
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
SKRIP = ROOT / "scripts/migrate_kpt8_rahasia.py"
KUNCI_UJI = Fernet.generate_key().decode()
SIMPAN: dict = {}
PESAN_KONEKSI = "Koneksi WhatsApp diatur di Pengaturan › Integrasi & Sistem."


@pytest.fixture(autouse=True)
def _kunci_uji(monkeypatch):
    monkeypatch.setenv("KN_SECRETS_KEY", KUNCI_UJI)


def _skrip():
    spec = importlib.util.spec_from_file_location("migrate_kpt8_rahasia", SKRIP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(teks: str) -> str:
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()


async def _ingest(klien, token: str):
    return await klien.post("/api/hr/attendance/ingest", json={"device_token": token, "records": []})


def _ubah_satu(token: str) -> str:
    return token[:-1] + ("0" if token[-1] != "0" else "1")


# ════════════════════════════ pembungkus rahasia ════════════════════════════
async def test_KPT8_secret_box_aturan_pakai(monkeypatch):
    from services import secret_box as sb
    from services import rfid_ingest_service as rfid
    assert sb.available() is True
    t = sb.seal("rahasia-palsu")
    assert t.startswith("enc:v1:") and "rahasia-palsu" not in t
    assert sb.seal(t) == t and sb.seal("") == ""            # sudah terbungkus / kosong → apa adanya
    assert sb.open(t) == "rahasia-palsu" and sb.open("polos") == "polos"
    # Token yang hanya dicocokkan = hash; aturannya sama dengan kunci perangkat RFID (berkas RFID tidak diubah, H7).
    assert sb.hash_token("at_abc") == _sha("at_abc") == rfid.hash_device_key("at_abc")
    monkeypatch.delenv("KN_SECRETS_KEY")
    assert sb.available() is False
    assert sb.seal("polos-lagi") == "polos-lagi"            # tanpa kunci → disimpan polos (perilaku hari ini)
    with pytest.raises(sb.SecretBoxError) as e:
        sb.open(t)
    assert str(e.value) == "KN_SECRETS_KEY belum diisi — rahasia terenkripsi tidak bisa dibaca."


# ════════════════════════════ mesin absen ═══════════════════════════════════
async def test_KPT8_U1_token_baru_tampil_sekali_dan_hanya_hash_tersimpan(klien, kepala_admin, db):
    r = await klien.post("/api/hr/devices", headers=kepala_admin, json={"name": "Mesin A"})
    assert r.status_code == 200, r.text
    j = r.json()
    tok = j["device_token"]
    assert tok.startswith("at_") and len(tok) == 3 + 32 and j["shown_once"] is True
    assert "device_token_hash" not in j
    doc = await db.hr_devices.find_one({"id": j["id"]}, {"_id": 0})
    assert "device_token" not in doc and doc["device_token_hash"] == _sha(tok)
    assert doc["device_token_hint"] == tok[-4:] and doc["device_token_at"] and doc["token_rotation_required"] is False
    r = await klien.get("/api/hr/devices", headers=kepala_admin)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows and all("device_token" not in x and "device_token_hash" not in x for x in rows)
    baris = next(x for x in rows if x["id"] == j["id"])
    assert baris["device_token_hint"] == tok[-4:] and baris["token_rotation_required"] is False
    SIMPAN.update(dev_a=j["id"], tok_a=tok)


async def test_KPT8_U2_ingest_mencocokkan_hash(klien):
    r = await _ingest(klien, SIMPAN["tok_a"])
    assert r.status_code == 200, r.text
    r = await _ingest(klien, _ubah_satu(SIMPAN["tok_a"]))
    assert r.status_code == 401 and r.json()["detail"] == "device_token tidak valid"


async def test_KPT8_U3_token_lama_tetap_berlaku_sesudah_migrasi(klien, kepala_admin, db):
    # Fixture (sisip langsung) — perangkat bentuk lama: token polos yang pernah tampil di layar.
    await db.hr_devices.insert_one({"id": "dev_lama_u3", "name": "Mesin Lama", "device_token": "devtok_abc123abc123",
                                    "status": "active", "entity_id": "ent_ksc", "last_sync": ""})
    r = await _ingest(klien, "devtok_abc123abc123")                 # sebelum migrasi: pembaca bentuk lama
    assert r.status_code == 200, r.text
    rows = (await klien.get("/api/hr/devices", headers=kepala_admin)).json()
    lama = next(x for x in rows if x["id"] == "dev_lama_u3")
    assert "device_token" not in lama and lama["token_rotation_required"] is True and lama["device_token_hint"] == "c123"
    mod = _skrip()
    assert mod.main(["--salah"]) == 2                                # argumen tak dikenal: keluar sebelum basis data
    lapor = await mod.jalankan(tulis=False)                          # bawaan: hanya lapor, tidak menulis
    assert any(p["id"] == "dev_lama_u3" for p in lapor["perangkat_token_polos"])
    assert (await db.hr_devices.find_one({"id": "dev_lama_u3"}))["device_token"] == "devtok_abc123abc123"
    pertama = await mod.jalankan(tulis=True)
    kedua = await mod.jalankan(tulis=True)                           # aman diulang
    assert pertama["ditulis"]["perangkat"] >= 1 and kedua["ditulis"]["perangkat"] == 0
    doc = await db.hr_devices.find_one({"id": "dev_lama_u3"}, {"_id": 0})
    assert "device_token" not in doc and doc["token_rotation_required"] is True
    assert doc["device_token_hash"] == _sha("devtok_abc123abc123") and doc["device_token_hint"] == "c123"
    r = await _ingest(klien, "devtok_abc123abc123")                 # mesin terpasang tidak putus
    assert r.status_code == 200, r.text


async def test_KPT8_U4_ganti_token_memutus_token_lama(klien, kepala_admin, db):
    dev = SIMPAN["dev_a"]
    r = await klien.post(f"/api/hr/devices/{dev}/rotate-token", headers=kepala_admin)
    assert r.status_code == 200, r.text
    j = r.json()
    baru = j["device_token"]
    assert j["device_id"] == dev and j["shown_once"] is True and baru.startswith("at_") and baru != SIMPAN["tok_a"]
    assert j["device_token_hint"] == baru[-4:]
    assert (await _ingest(klien, SIMPAN["tok_a"])).status_code == 401
    assert (await _ingest(klien, baru)).status_code == 200
    jejak = await db.audit_logs.find_one({"action": "hr_device_token_rotated", "entity_id": dev}, {"_id": 0})
    assert jejak and baru not in str(jejak)
    # Ganti token perangkat lama: tanda "disarankan ganti" hilang.
    r = await klien.post("/api/hr/devices/dev_lama_u3/rotate-token", headers=kepala_admin)
    assert r.status_code == 200, r.text
    doc = await db.hr_devices.find_one({"id": "dev_lama_u3"}, {"_id": 0})
    assert doc["token_rotation_required"] is False and "device_token" not in doc
    assert (await _ingest(klien, "devtok_abc123abc123")).status_code == 401
    SIMPAN["tok_a"] = baru


async def test_KPT8_U5_lihat_saja_tanpa_token_dan_tidak_bisa_ganti(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"hr": ["view"]}, label="Lihat SDM KP-T8")
    h = await sesi(await akun(rid))
    r = await klien.get("/api/hr/devices", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() and all("device_token" not in x and "device_token_hash" not in x for x in r.json())
    r = await klien.post(f"/api/hr/devices/{SIMPAN['dev_a']}/rotate-token", headers=h)
    assert r.status_code == 403, r.text


async def test_KPT8_U6_ganti_token_perangkat_pt_lain_ditolak(klien, kepala_admin, akun, sesi, peran_tanpa_acuan, db):
    r = await klien.post("/api/hr/devices", headers=kepala_admin, json={"name": "Mesin Kanda", "entity_id": "ent_kanda"})
    assert r.status_code == 200, r.text
    dev = r.json()["id"]
    sebelum = (await db.hr_devices.find_one({"id": dev}))["device_token_hash"]
    rid = await peran_tanpa_acuan({"hr": ["view", "manage_attendance"]}, label="Absensi KSC KP-T8")
    h = await sesi(await akun(rid, entitas=("ent_ksc",)))
    r_patch = await klien.patch(f"/api/hr/devices/{dev}", headers=h, json={"data": {"location": "x"}})
    r = await klien.post(f"/api/hr/devices/{dev}/rotate-token", headers=h)
    assert r.status_code in (403, 404) and r.status_code == r_patch.status_code, (r.text, r_patch.text)
    assert (await db.hr_devices.find_one({"id": dev}))["device_token_hash"] == sebelum


# ════════════════════════════ token WhatsApp dibungkus ══════════════════════
async def test_KPT8_U7_token_pengingat_dibungkus(klien, kepala_admin, db):
    from services import wa_connection
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin,
                        json={"wa": {"provider": "fonnte", "fonnte_token": "tok-rahasia", "enabled": True}})
    assert r.status_code == 200, r.text
    doc = await db.system_settings.find_one({"scope": "alerts"}, {"_id": 0})
    assert doc["wa"]["fonnte_token"].startswith("enc:v1:") and "tok-rahasia" not in str(doc)
    g = (await klien.get("/api/scheduler/settings", headers=kepala_admin)).json()["wa"]
    assert g["has_fonnte_token"] is True and "fonnte_token" not in g and "access_token" not in g
    assert (await wa_connection.for_consumer("alerts"))["fonnte_token"] == "tok-rahasia"


async def test_KPT8_U8_tanpa_kunci_disimpan_polos(klien, kepala_admin, db, monkeypatch):
    monkeypatch.delenv("KN_SECRETS_KEY")
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin,
                        json={"wa": {"provider": "fonnte", "fonnte_token": "tok-rahasia", "enabled": True}})
    assert r.status_code == 200, r.text
    doc = await db.system_settings.find_one({"scope": "alerts"}, {"_id": 0})
    assert doc["wa"]["fonnte_token"] == "tok-rahasia"
    r = await klien.get("/api/admin/integrations", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["secrets_key_configured"] is False


async def test_KPT8_U9_token_polos_lama_dibungkus_saat_dibaca(db):
    from services import wa_alert_service
    # Fixture (sisip langsung) — data lama: token Meta polos.
    await db.system_settings.update_one({"scope": "alerts"}, {"$set": {"wa.access_token": "tok-meta-polos"}})
    st = await wa_alert_service.raw_settings()
    assert st["wa"]["access_token"] == "tok-meta-polos" and st["wa"]["fonnte_token"] == "tok-rahasia"
    doc = await db.system_settings.find_one({"scope": "alerts"}, {"_id": 0})
    assert doc["wa"]["access_token"].startswith("enc:v1:") and doc["wa"]["fonnte_token"].startswith("enc:v1:")


# ════════════════════════════ koneksi tunggal ═══════════════════════════════
async def _keadaan_lama(db, alerts: dict, documents: dict | None) -> None:
    """Fixture (sisip langsung): dua konfigurasi lama, tanpa koneksi tunggal."""
    from services import wa_alert_service as was
    await db.system_settings.update_one({"scope": "integrations"}, {"$unset": {"whatsapp": ""}})
    await db.system_settings.update_one({"scope": "alerts"}, {"$set": {"wa": {**was.DEFAULT_WA, **alerts}}}, upsert=True)
    await db.integration_settings.delete_many({"id": "whatsapp"})
    if documents is not None:
        await db.integration_settings.insert_one({"id": "whatsapp", **documents})


async def test_KPT8_U10_satu_konfigurasi_terisi_disalin(klien, kepala_admin, db):
    from services import wa_connection
    await _keadaan_lama(db, {"provider": "fonnte", "fonnte_token": "tok-A", "enabled": True},
                        {"provider": "simulated", "simulate": True, "enabled": True})
    await _skrip().jalankan(tulis=True)
    r = await klien.get("/api/admin/integrations/whatsapp", headers=kepala_admin)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["configured"] is True and j["conflict"] is None and j["used_by"] == {"alerts": True, "documents": True}
    assert j["provider"] == "fonnte" and j["has_fonnte_token"] is True
    assert "fonnte_token" not in j and "access_token" not in j and "tok-A" not in r.text
    doc = await db.system_settings.find_one({"scope": "integrations"}, {"_id": 0})
    assert doc["whatsapp"]["fonnte_token"].startswith("enc:v1:")
    dok = await wa_connection.for_consumer("documents")
    assert dok["provider"] == "fonnte" and dok["fonnte_token"] == "tok-A"


class _Tiru:
    terkirim: list = []
    name = "tiru"

    def __init__(self, settings):
        self.settings = settings or {}

    def _catat(self, to):
        _Tiru.terkirim.append((self.name, self.settings.get("fonnte_token") or self.settings.get("access_token"), to))
        return {"status": "sent", "provider": self.name, "message_id": "m-uji"}

    async def send_message(self, to, text):
        return self._catat(to)

    async def send_template(self, to, template, params, lang="id"):
        return self._catat(to)

    async def send_document(self, to, doc_meta, pdf_bytes, caption=""):
        return self._catat(to)


class _TiruFonnte(_Tiru):
    name = "fonnte"


class _TiruMeta(_Tiru):
    name = "meta_cloud"


@pytest.fixture
def penyedia_tiruan(monkeypatch):
    import services.wa as wa_pkg
    from services import pdf_service

    async def _render(doc_type, source_id, entity_id, fmt="pdf", **kw):
        return b"%PDF-uji", "application/pdf", {"source": {"number": "SO-UJI-1", "entity_id": "ent_ksc"}}

    monkeypatch.setitem(wa_pkg._PROVIDERS, "fonnte", _TiruFonnte)
    monkeypatch.setitem(wa_pkg._PROVIDERS, "meta_cloud", _TiruMeta)
    monkeypatch.setattr(pdf_service, "render_document", _render)
    _Tiru.terkirim = []
    return _Tiru


async def _kirim_keduanya(tiru):
    from services import delivery_service, wa_alert_service
    tiru.terkirim = []
    await wa_alert_service.send_test("081234567890", "uji KP-T8")
    await delivery_service.send_whatsapp("sales_order", "so_uji", "ent_ksc", "081234567891", "", "", "uji")
    return [(p, t) for p, t, _ in tiru.terkirim]


async def test_KPT8_U11_dua_koneksi_berbeda_tidak_digabung(klien, kepala_admin, db, penyedia_tiruan):
    await _keadaan_lama(db, {"provider": "fonnte", "fonnte_token": "tok-A", "enabled": True},
                        {"provider": "meta_cloud", "access_token": "tok-B", "phone_number_id": "1098765",
                         "simulate": False, "enabled": True})
    mod = _skrip()
    hasil = await mod.jalankan(tulis=True)
    assert hasil["whatsapp"]["keadaan"] == "berbeda"
    teks: list = []
    mod._cetak(hasil, teks.append)
    assert any("dua koneksi berbeda" in t for t in teks)
    j = (await klien.get("/api/admin/integrations/whatsapp", headers=kepala_admin)).json()
    assert j["configured"] is False and j["used_by"] == {"alerts": False, "documents": False}
    assert j["conflict"]["alerts"]["provider"] == "fonnte" and j["conflict"]["documents"]["provider"] == "meta_cloud"
    assert "tok-A" not in str(j) and "tok-B" not in str(j)
    # Tiap pemakai tetap memakai konfigurasi lamanya.
    assert await _kirim_keduanya(penyedia_tiruan) == [("fonnte", "tok-A"), ("meta_cloud", "tok-B")]
    r = await klien.post("/api/admin/integrations/whatsapp/adopt", headers=kepala_admin,
                         json={"from": "alerts", "reason": "Satu nomor"})
    assert r.status_code == 200, r.text
    assert await _kirim_keduanya(penyedia_tiruan) == [("fonnte", "tok-A"), ("fonnte", "tok-A")]
    r = await klien.post("/api/admin/integrations/whatsapp/adopt", headers=kepala_admin,
                         json={"from": "documents", "reason": "Ulang"})
    assert r.status_code == 409 and r.json()["detail"] == "Koneksi WhatsApp sudah satu."


async def test_KPT8_U12_field_koneksi_ditolak_setelah_koneksi_tunggal(klien, kepala_admin):
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin, json={"wa": {"access_token": "x"}})
    assert r.status_code == 400 and r.json()["detail"] == PESAN_KONEKSI, r.text
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin, json={"wa": {"pic_number": "081234567890"}})
    assert r.status_code == 200, r.text
    r = await klien.put("/api/deliveries/whatsapp/settings", headers=kepala_admin,
                        json={"provider": "meta_cloud", "access_token": "x"})
    assert r.status_code == 400 and r.json()["detail"] == PESAN_KONEKSI, r.text
    r = await klien.put("/api/deliveries/whatsapp/settings", headers=kepala_admin, json={"simulate": True})
    assert r.status_code == 200, r.text


# ════════════════════════════ izin integrasi ════════════════════════════════
async def test_KPT8_U14_peran_lama_hr_manage_settings_diberi_izin_integrasi(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"hr": ["view", "manage_settings"]}, label="Pengatur SDM Lama")
    h = await sesi(await akun(rid))
    assert (await klien.get("/api/admin/integrations", headers=h)).status_code == 403   # sebelum migrasi
    hasil = await _skrip().jalankan(tulis=True)
    assert any(p["id"] == rid for p in hasil["peran_integrasi"])
    r = await klien.get("/api/admin/integrations", headers=h)
    assert r.status_code == 200, r.text


async def test_KPT8_U13_izin_integrasi_sendiri(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong):
    rid = await peran_tanpa_acuan({"integration": ["manage"]}, label="Kelola Integrasi")
    r = await klien.get("/api/admin/integrations", headers=await sesi(await akun(rid)))
    assert r.status_code == 200, r.text
    assert "secrets_key_configured" in r.json()
    rid2 = await peran_tanpa_acuan({"hr": ["view", "manage_settings"]}, label="Pengatur SDM Baru")
    for peran in (rid2, await peran_manajer_kosong()):
        r = await klien.get("/api/admin/integrations", headers=await sesi(await akun(peran)))
        assert r.status_code == 403, r.text
        assert r.json()["detail"] == ("Anda belum punya akses untuk mengatur integrasi. "
                                      "Minta Admin menambahkan akses 'Pusat Pengaturan'.")


# ════════════════════════════ dua kunci registry ════════════════════════════
async def test_KPT8_U15_hidup_mati_pengenal_gambar_di_registry(klien, kepala_admin, db):
    from services import hr_ai_service, integrations_service as integ
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [
        {"key": "integrations.anthropic.enabled", "value": True, "scope_type": "global", "scope_id": "",
         "reason": "uji KP-T8"},
        {"key": "integrations.anthropic.model", "value": integ.ANTHROPIC_MODELS[-1], "scope_type": "global",
         "scope_id": "", "reason": "uji KP-T8"}]})
    assert r.status_code == 200, r.text
    doc = await db.system_settings.find_one({"scope": "integrations"}, {"_id": 0})
    assert doc["anthropic"]["enabled"] is True and doc["anthropic"]["model"] == integ.ANTHROPIC_MODELS[-1]
    r = await klien.put("/api/admin/integrations", headers=kepala_admin, json={"anthropic_api_key": "kunci-palsu-uji"})
    assert r.status_code == 200, r.text
    assert await hr_ai_service.is_enabled() is True
    doc = await db.system_settings.find_one({"scope": "integrations"}, {"_id": 0})
    assert doc["anthropic"]["api_key"].startswith("enc:v1:") and doc["anthropic"]["enabled"] is True
    r = await klien.put("/api/admin/integrations", headers=kepala_admin, json={"anthropic_enabled": False})
    assert r.status_code == 400, r.text
    r = await klien.put("/api/admin/integrations", headers=kepala_admin, json={"anthropic_model": integ.DEFAULT_MODEL})
    assert r.status_code == 400, r.text
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [
        {"key": "integrations.anthropic.enabled", "value": False, "scope_type": "global", "scope_id": "",
         "reason": "uji KP-T8"}]})
    assert r.status_code == 200, r.text
    assert await hr_ai_service.is_enabled() is False
