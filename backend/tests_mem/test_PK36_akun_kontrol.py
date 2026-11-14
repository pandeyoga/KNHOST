"""PK-36 — akun kontrol tertutup dari jurnal manual dan pembalikan sepihak (docs/blueprint/unit/PK-36.md).

Admin (`X-Entity-Id: ent_ksc` kecuali disebut). Pengaturan `gl.jurnal_manual_akun_kontrol` pada bawaan (`tolak`) kecuali
disebut; setiap uji yang mengubahnya memulihkannya. Semua jurnal uji Rp 100.000, bertanggal hari ini.
Akun kontrol bawaan (registri Pemetaan Akun): 1-1200 piutang usaha · 2-1100 hutang usaha · 1-1300 persediaan ·
1-1250/2-1250 antar-PT. Fixture "data lama" disisipkan lewat `gl_service._insert_entry` (dicatat sebagai fixture).
Urutan uji di modul ini berarti: U4 memetakan `penjualan.piutang` PT `ent_ksc` ke 1-1201; U13 dan U4b memakainya.
"""
from __future__ import annotations

import datetime

import pytest

from pembantu import saldo_akun
from services import gl_service as gl

pytestmark = pytest.mark.anyio
KSC, KANDA = "ent_ksc", "ent_kanda"
KUNCI = "gl.jurnal_manual_akun_kontrol"
HARI_INI = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
N = 100_000


def _jurnal(debit, kredit, n=N, ket="uji PK-36"):
    return {"date": HARI_INI, "description": ket, "lines": [
        {"account_code": debit, "debit": n, "credit": 0, "description": ket},
        {"account_code": kredit, "debit": 0, "credit": n, "description": ket}]}


def _h(h, ent):
    return {**h, "X-Entity-Id": ent}


def _isi(value, scope_type="global", scope_id="", reason="uji PK-36"):
    return {"items": [{"key": KUNCI, "value": value, "scope_type": scope_type, "scope_id": scope_id,
                       "reason": reason}]}


async def _pulihkan(klien, h, *pt):
    for eid in pt:
        r = await klien.post("/api/config/values/clear", headers=h,
                             json={"key": KUNCI, "scope_type": "entity", "scope_id": eid, "reason": "pulihkan uji"})
        assert r.status_code == 200, r.text
    r = await klien.post("/api/config/values/reset", headers=h,
                         json={"key": KUNCI, "scope_type": "global", "reason": "pulihkan uji"})
    assert r.status_code == 200, r.text


async def _fixture(baris, source_type, sid, ent=KSC):
    return await gl._insert_entry(lines=[{"account_code": a, "debit": d, "credit": k} for a, d, k in baris],
                                  description=f"fixture PK-36 {sid}", date=gl.now_iso(), source_type=source_type,
                                  source_id=sid, entity_id=ent, created_by="uji")


async def _balik(klien, h, jid, alasan="uji balik PK-36"):
    return await klien.post(f"/api/gl/journal/{jid}/reverse", headers=h, json={"date": HARI_INI, "reason": alasan})


# ── U1–U3 — jurnal manual ─────────────────────────────────────────────────────────────────────────────────────────
async def test_PK36_U1_jurnal_manual_ke_piutang_ditolak(klien, db, kepala_admin):
    n0 = await db.journal_entries.count_documents({})
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("1-1200", "4-9000"))
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert "akun kontrol piutang usaha" in d and "Kwitansi" in d, d
    assert d.startswith("Akun 1-1200 · Piutang Usaha adalah akun kontrol"), d
    assert await db.journal_entries.count_documents({}) == n0


@pytest.mark.parametrize("akun_kontrol, debit, kredit, dokumen", [
    ("2-1100", "6-4000", "2-1100", "Tagihan Pemasok"),
    ("1-1300", "1-1300", "4-9000", "Stock Opname"),
    ("1-1250", "1-1250", "4-9000", "dokumen Antar-PT"),
    ("2-1250", "6-4000", "2-1250", "dokumen Antar-PT"),
])
async def test_PK36_U2_empat_akun_kontrol_lain(klien, db, kepala_admin, akun_kontrol, debit, kredit, dokumen):
    n0 = await db.journal_entries.count_documents({})
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal(debit, kredit))
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert d.startswith(f"Akun {akun_kontrol} ·") and dokumen in d, d
    assert await db.journal_entries.count_documents({}) == n0


async def test_PK36_U3_akun_biasa_tetap_diterima(klien, kepala_admin):
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("6-4000", "1-1100"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "posted"


# ── U4 — akun kontrol dari Pemetaan Akun (bawaan ∪ pemetaan PT ∪ riwayat) ─────────────────────────────────────────────
async def test_PK36_U4_pemetaan_pt_menjadi_akun_kontrol(klien, kepala_admin):
    from services import gl_mapping_service as glm
    r = await klien.post("/api/gl/accounts", headers=kepala_admin,
                         json={"code": "1-1201", "name": "Piutang Usaha Baru (uji)", "type": "asset",
                               "parent_code": "1-1000"})
    assert r.status_code == 200, r.text
    r = await klien.put("/api/gl/account-mappings/penjualan.piutang", headers=kepala_admin,
                        json={"account_code": "1-1201", "entity_id": KSC, "reason": "uji PK-36 pemetaan PT"})
    assert r.status_code == 200, r.text
    # tes unit kecil: kode bawaan tetap, kode pemetaan PT hanya untuk PT itu
    ksc, kanda = await glm.control_accounts(KSC), await glm.control_accounts(KANDA)
    assert (ksc.get("1-1200"), ksc.get("1-1201")) == ("piutang", "piutang")
    assert (kanda.get("1-1200"), kanda.get("1-1201")) == ("piutang", None)
    assert {ksc.get(k) for k in ("2-1100", "1-1300", "1-1250", "2-1250")} == {"hutang", "persediaan", "antar_pt"}
    r1 = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("1-1201", "4-9000"))
    r2 = await klien.post("/api/gl/journal", headers=_h(kepala_admin, KANDA), json=_jurnal("1-1201", "4-9000"))
    r3 = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("1-1200", "4-9000"))
    assert [r1.status_code, r2.status_code, r3.status_code] == [422, 200, 422], (r1.text, r2.text, r3.text)
    assert "akun kontrol piutang usaha" in r1.json()["detail"]


# ── U5 — pengaturan per PT ────────────────────────────────────────────────────────────────────────────────────────
async def test_PK36_U5_izinkan_di_satu_pt(klien, kepala_admin):
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("izinkan", "entity", KSC))
    assert r.status_code == 200, r.text
    try:
        r1 = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("1-1200", "4-9000"))
        r2 = await klien.post("/api/gl/journal", headers=_h(kepala_admin, KANDA), json=_jurnal("1-1200", "4-9000"))
        assert [r1.status_code, r2.status_code] == [200, 422], (r1.text, r2.text)
    finally:
        await _pulihkan(klien, kepala_admin, KSC)


async def test_PK36_U5b_izinkan_juga_membuka_pembalikan(klien, db, kepala_admin):
    """Tambahan (02 §2.4 butir 2): `izinkan` di PT itu membuka pembalikan manual jurnal otomatis ke akun kontrol."""
    je = await _fixture([("1-1250", N, 0), ("4-1000", 0, N)], "interco_transaction", "pk36_u5b")
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("izinkan", "entity", KSC))
    assert r.status_code == 200, r.text
    try:
        r = await _balik(klien, kepala_admin, je["id"])
        assert r.status_code == 200, r.text
    finally:
        await _pulihkan(klien, kepala_admin, KSC)


# ── U6–U8 — pembalikan manual ─────────────────────────────────────────────────────────────────────────────────────
async def test_PK36_U6_pembalikan_manual_jurnal_antar_pt_ditolak(klien, db, kepala_admin):
    je = await _fixture([("1-1250", N, 0), ("4-1000", 0, N)], "interco_transaction", "pk36_u6")
    r = await _balik(klien, kepala_admin, je["id"])
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert "pembalikan manual ditolak" in d, d
    assert d == (f"Jurnal {je['number']} berasal dari Antar-PT dan menyentuh akun kontrol antar-PT. Batalkan atau "
                 "koreksi dokumen sumbernya; pembalikan manual ditolak."), d
    asal = await db.journal_entries.find_one({"id": je["id"]}, {"_id": 0})
    assert "reversed_by_entry_id" not in asal and not asal.get("reversed")


async def test_PK36_U7_jurnal_manual_lama_boleh_dibalik(klien, db, kepala_admin):
    # Fixture "data lama": jurnal manual Dr 1-1200 100.000 / Cr 4-9000 100.000 (sebelum PK-36 diterima).
    je = await _fixture([("1-1200", N, 0), ("4-9000", 0, N)], "manual", "")
    r = await _balik(klien, kepala_admin, je["id"])
    assert r.status_code == 200, r.text
    # Hitung tangan: asal D 100.000 → pembalik K 100.000 → saldo 1-1200 dari dua jurnal = 100.000 − 100.000 = 0.
    saldo = 0.0
    for j in (je, r.json()):
        for ln in j["lines"]:
            if ln["account_code"] == "1-1200":
                saldo += float(ln["debit"]) - float(ln["credit"])
    assert saldo == 0


async def test_PK36_U8_pembalikan_jurnal_kas_tanpa_akun_kontrol(klien, kepala_admin):
    # Sebelum unit ini (PK-10): pembalikan manual jurnal kas otomatis = 200. Tetap begitu; tidak ada galat akun kontrol.
    je = await _fixture([("6-4000", N, 0), ("1-1100", 0, N)], "cash_transaction", "pk36_u8")
    r = await _balik(klien, kepala_admin, je["id"])
    assert r.status_code == 200, r.text
    assert "akun kontrol" not in r.text


# ── U9 — reklasifikasi suspense ───────────────────────────────────────────────────────────────────────────────────
async def test_PK36_U9_reklas_suspense_ke_akun_kontrol(klien, kepala_admin):
    await _fixture([("1-1100", N, 0), ("1-9999", 0, N)], "uji", "pk36_u9")   # saldo suspense kredit 100.000
    dasar = {"amount": N, "side": "credit", "note": "uji PK-36", "entity_id": KSC}
    r = await klien.post("/api/gl/suspense/reclass", headers=kepala_admin, json={**dasar, "target_account": "1-1200"})
    assert r.status_code == 422, r.text
    assert "akun kontrol piutang usaha" in r.json()["detail"]
    r = await klien.post("/api/gl/suspense/reclass", headers=kepala_admin, json={**dasar, "target_account": "6-4000"})
    assert r.status_code == 200, r.text


# ── U10–U13 — hapus akun (GL-10) ──────────────────────────────────────────────────────────────────────────────────
async def test_PK36_U10_akun_khusus_pt_berjurnal_tidak_bisa_dihapus(klien, db, kepala_admin):
    q = {"entity_id": KSC}
    r = await klien.post("/api/gl/accounts", headers=kepala_admin, params=q,
                         json={"code": "6-9901", "name": "Beban Khusus KSC (uji)", "type": "expense"})
    assert r.status_code == 200, r.text
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("6-9901", "1-1100"))
    assert r.status_code == 200, r.text
    r = await klien.delete("/api/gl/accounts/6-9901", headers=kepala_admin, params=q)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == ("Akun 6-9901 dipakai pada 1 jurnal PT ini, jadi tidak bisa dihapus. Nonaktifkan "
                                  "saja bila tidak dipakai lagi.")
    assert await db.gl_accounts.find_one({"code": "6-9901", "entity_id": KSC})


async def test_PK36_U11_akun_khusus_pt_kosong_bisa_dihapus(klien, db, kepala_admin):
    q = {"entity_id": KSC}
    r = await klien.post("/api/gl/accounts", headers=kepala_admin, params=q,
                         json={"code": "6-9902", "name": "Beban Khusus KSC 2 (uji)", "type": "expense"})
    assert r.status_code == 200, r.text
    r = await klien.delete("/api/gl/accounts/6-9902", headers=kepala_admin, params=q)
    assert r.status_code == 200, r.text
    assert not await db.gl_accounts.find_one({"code": "6-9902"})


async def test_PK36_U12_hapus_penimpa_laporan_kembali_ke_templat(klien, db, kepala_admin):
    q = {"entity_id": KSC}
    r = await klien.patch("/api/gl/accounts/6-4000", headers=kepala_admin, params=q,
                          json={"name": "Beban Operasional KSC (uji)"})
    assert r.status_code == 200, r.text
    assert await db.gl_accounts.find_one({"code": "6-4000", "entity_id": KSC})
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("6-4000", "1-1100"))
    assert r.status_code == 200, r.text
    r = await klien.delete("/api/gl/accounts/6-4000", headers=kepala_admin, params=q)
    assert r.status_code == 200, r.text
    r = await klien.get("/api/finance/income-statement", headers=kepala_admin, params=q)
    assert r.status_code == 200, r.text
    baris = [ln for s in r.json()["sections"] for ln in s["lines"] if ln["code"] == "6-4000"]
    assert len(baris) == 1 and baris[0]["name"] == "Beban Operasional Lainnya", baris


async def test_PK36_U13_akun_terpetakan_tidak_bisa_dihapus(klien, db, kepala_admin):
    r = await klien.delete("/api/gl/accounts/1-1201", headers=kepala_admin)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == ("Akun 1-1201 sedang dipakai di Pemetaan Akun (Piutang usaha). Ganti pemetaannya "
                                  "dulu."), r.text
    assert await db.gl_accounts.find_one({"code": "1-1201", "entity_id": None})


async def test_PK36_U4b_kode_lama_dari_riwayat_tetap_akun_kontrol(klien, kepala_admin):
    """Langkah 2 (riwayat): pemetaan PT dikembalikan ke bawaan → 1-1201 tetap akun kontrol di PT yang pernah
    memakainya (ASUMSI unit: kode lama tetap diperlakukan akun kontrol)."""
    from services import gl_mapping_service as glm
    r = await klien.post("/api/gl/account-mappings/penjualan.piutang/reset", headers=kepala_admin,
                         json={"entity_id": KSC, "reason": "uji PK-36 kembali ke bawaan"})
    assert r.status_code == 200, r.text
    assert (await glm.resolve("penjualan.piutang", KSC))["account_code"] == "1-1200"
    assert (await glm.control_accounts(KSC)).get("1-1201") == "piutang"
    assert (await glm.control_accounts(KANDA)).get("1-1201") is None
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("1-1201", "4-9000"))
    assert r.status_code == 422, r.text


# ── U14 — putaran pengaturan (02 §2.4 butir 1) ────────────────────────────────────────────────────────────────────
async def test_PK36_U14_putaran_pengaturan(klien, kepala_admin):
    import config_registry as registry
    from services.config_resolver import value_of
    e = registry.require(KUNCI)
    assert (e["group"], e["type"], e["default"], e["scopes"], e["permission"]) == (
        "pajak-pembukuan", "enum", "tolak", ["global", "entity"], ["accounting", "manage"])   # KF-T4 — kelompok baru
    assert {o["value"] for o in e["options"]} == {"tolak", "izinkan"}
    assert (e["risk"], e["requires_reason"], e["status"]) == ("high", True, "active")
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("izinkan"))
    assert r.status_code == 200, r.text
    assert await value_of(KUNCI) == "izinkan"
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": KUNCI})
    assert next(i for i in r.json()["items"] if i["key"] == KUNCI)["value"] == "izinkan"
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("tolak", "entity", KANDA))
    assert r.status_code == 200, r.text
    assert await value_of(KUNCI, {"entity_id": KANDA}) == "tolak"
    assert await value_of(KUNCI, {"entity_id": KSC}) == "izinkan"          # PT lain tidak ikut
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("mungkin"))
    assert r.status_code == 400, r.text
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("tolak", reason=""))
    assert r.status_code == 400, r.text                                    # wajib beralasan
    await _pulihkan(klien, kepala_admin, KANDA)
    assert await value_of(KUNCI) == "tolak" and await value_of(KUNCI, {"entity_id": KANDA}) == "tolak"


# ── U15 — jawaban daftar akun ─────────────────────────────────────────────────────────────────────────────────────
async def test_PK36_U15_daftar_akun_menandai_akun_kontrol(klien, kepala_admin):
    r = await klien.get("/api/gl/accounts", headers=kepala_admin, params={"entity_id": KSC})
    assert r.status_code == 200, r.text
    by = {a["code"]: a for a in r.json()}
    assert (by["1-1200"]["is_control"], by["1-1200"]["control_ledger"], by["1-1200"]["manual_allowed"]) == (
        True, "piutang", False)
    assert (by["6-4000"]["is_control"], by["6-4000"]["manual_allowed"]) == (False, True)
    assert by["1-1200"]["control_ledger_label"] == "piutang usaha"
    r = await klien.get("/api/gl/accounts", headers=kepala_admin)               # tanpa PT → lapisan global
    by = {a["code"]: a for a in r.json()}
    assert (by["2-1250"]["is_control"], by["2-1250"]["control_ledger"], by["2-1250"]["manual_allowed"]) == (
        True, "antar_pt", False)
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("izinkan", "entity", KSC))
    assert r.status_code == 200, r.text
    try:
        r = await klien.get("/api/gl/accounts", headers=kepala_admin, params={"entity_id": KSC})
        by = {a["code"]: a for a in r.json()}
        assert (by["1-1200"]["is_control"], by["1-1200"]["manual_allowed"]) == (True, True)
    finally:
        await _pulihkan(klien, kepala_admin, KSC)


# ── U16 — berlaku untuk semua peran ───────────────────────────────────────────────────────────────────────────────
async def test_PK36_U16_peran_tanpa_acuan_kena_penjaga_bukan_403(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"accounting": ["view", "create"]}, label="Jurnal Manual PK-36")
    h = await sesi(await akun(rid))
    r = await klien.post("/api/gl/journal", headers=h, json=_jurnal("1-1200", "4-9000"))
    assert r.status_code == 422, r.text
    assert "akun kontrol piutang usaha" in r.json()["detail"]
    r = await klien.post("/api/gl/journal", headers=h, json=_jurnal("6-4000", "1-1100"))
    assert r.status_code == 200, r.text


# ── Tambahan — usulan jurnal dua orang (KF-T6) kena pemeriksaan yang sama ─────────────────────────────────────────
async def test_PK36_U16b_usulan_jurnal_dua_orang_kena_penjaga(klien, db, kepala_admin, akun, sesi):
    from services import config_resolver as resolver
    await resolver.set_value("kontrol.jurnal_manual.min_orang", "2", scope_type="entity", scope_id=KSC,
                             reason="uji PK-36", actor="uji")
    try:
        p0 = await db.journal_proposals.count_documents({})
        r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("1-1200", "4-9000"))
        assert r.status_code == 422, r.text                                 # bukan 202: usulan tidak dibuat
        assert await db.journal_proposals.count_documents({}) == p0
        # usulan dibuat saat PT mengizinkan, disetujui sesudah aturan kembali "tolak" → 422, usulan tetap menunggu
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("izinkan", "entity", KSC))
        assert r.status_code == 200, r.text
        r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("1-1200", "4-9000"))
        assert r.status_code == 202, r.text
        pid = r.json()["proposal_id"]
        await _pulihkan(klien, kepala_admin, KSC)
        n0 = await db.journal_entries.count_documents({})
        penyetuju = await sesi(await akun("manager", entitas=(KSC, KANDA)))
        r = await klien.post(f"/api/gl/journal-proposals/{pid}/approve", headers=penyetuju)
        assert r.status_code == 422, r.text
        assert "akun kontrol piutang usaha" in r.json()["detail"]
        assert await db.journal_entries.count_documents({}) == n0
        assert (await db.journal_proposals.find_one({"id": pid}))["status"] == "pending"
    finally:
        if (await resolver.resolve(KUNCI, {"entity_id": KSC}))["source_layer"] == "entity":
            await resolver.clear_layer(KUNCI, scope_type="entity", scope_id=KSC, actor="uji", reason="uji PK-36")
        await resolver.clear_layer("kontrol.jurnal_manual.min_orang", scope_type="entity", scope_id=KSC, actor="uji",
                                   reason="uji PK-36")


# ── Tambahan — jurnal otomatis dokumen tetap bebas (P10) ──────────────────────────────────────────────────────────
async def test_PK36_P10_jurnal_dokumen_dan_pembalik_dokumen_tetap_jalan(db):
    """Penjaga tidak dipasang di `_insert_entry`; pembalik milik dokumen (ongkir retur ditagih ke pelanggan, Dr 1-1200)
    tetap lewat `reverse_entry` tanpa pemeriksaan akun kontrol."""
    from pembantu import AKTOR_UJI
    from services import return_logistics_service as rls
    s0 = await saldo_akun("1-1200", KSC)
    je = await _fixture([("1-1200", N, 0), ("4-9000", 0, N)], "return_logistics", "pk36_rl:qc:1")
    assert await saldo_akun("1-1200", KSC) == s0 + N
    await rls._reverse(je, "uji PK-36 ongkir diubah", AKTOR_UJI)
    assert await saldo_akun("1-1200", KSC) == s0
    asal = await db.journal_entries.find_one({"id": je["id"]}, {"_id": 0})
    assert asal["reversed_by_entry_id"] not in ("", "pending")
