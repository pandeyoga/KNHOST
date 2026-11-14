"""KP-T2 — kesiapan PT yang lengkap, penyiapan yang bisa diulang, pemeriksaan sebelum arsip (docs/blueprint/unit/KP-T2.md).

Uji U1–U17 di lingkungan B (database tiruan). Seed: `ent_ksc` (PKP), `ent_kanda` (non-PKP), akun Admin/Manajer (lintas
PT, berizin `cash.create`), Sales/Gudang (KSC). Satu modul berbagi basis data dan berjalan menurut urutan berkas; urutan
sengaja: rekening Kanda U3 → U4 → U15, U8 menonaktifkan sementara akun Admin/Manajer, U17 (mengarsipkan Kanda) terakhir.
"Hari ini" = tanggal WIB (`entity_lifecycle_service.today_wib`).

Fixture yang disisipkan langsung ke basis data (bukan alur): rekening/akun kas U3, U4, U15; periode tertutup U6; akun
pengguna U8 (fixture `akun`) dan penonaktifan sementara Admin/Manajer; `document_branding` U9; penanda lapisan dihapus
U11; pesanan batal U13; tagihan pemasok U14; uang muka & karyawan U16. Alur lewat API: U1, U2, U5 (pembanding
`GET /api/gl/account-mappings`), U7 (`PUT /api/config/values`), U10–U12, U16 (`DELETE`), U17.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
URUTAN = ["provisioning", "address", "tax", "doc_prefix", "users", "finance_user", "warehouses", "bank_account",
          "cash_account", "gl_mappings", "period", "payment_term", "prices", "opening_balance", "branding", "signers"]
PESAN_ARSIP = "PT ini sudah diarsipkan."


def _detail(r) -> str:
    try:
        d = r.json().get("detail")
    except Exception:  # noqa: BLE001 — jawaban bukan JSON (mis. 404/405 rute tidak ada)
        return r.text
    return d if isinstance(d, str) else str(d)


async def _siap(klien, h, eid: str) -> Dict[str, Any]:
    r = await klien.get(f"/api/entities/{eid}/readiness", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _butir(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    cocok = [i for i in data.get("items", []) if i.get("key") == key]
    assert cocok, f"butir {key!r} tidak ada: {[i.get('key') for i in data.get('items', [])]}"
    return cocok[0]


async def _dampak(klien, h, eid: str = KANDA) -> Dict[str, Any]:
    r = await klien.get(f"/api/entities/{eid}/deactivation-impact", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def _buat_pt(klien, h, kode: str) -> Any:
    return await klien.post("/api/entities", headers=h, json={
        "type": "PT", "default_tax_mode": "non_ppn", "legal_name": f"PT Uji {kode}", "short_name": kode,
        "doc_prefix": kode})


# ── U1 — 16 butir berurutan; butir lama `bank_accounts`/`fiscal_year` hilang ───────────────────────────────────────
async def test_KPT2_U1_enam_belas_butir_berurutan(klien, kepala_admin):
    d = await _siap(klien, kepala_admin, KSC)
    keys = [i["key"] for i in d["items"]]
    assert d["total"] == 16, keys
    assert keys == URUTAN
    assert "bank_accounts" not in keys and "fiscal_year" not in keys
    for i in d["items"]:   # bentuk tiap butir tetap; `tab` opsional
        assert {"key", "label", "ready", "count", "detail", "how_to", "view"} <= set(i), i
    assert set(d) >= {"ready", "total", "percent", "is_ready"}


# ── U2 — baris gudang ke Master Gudang, tidak ada baris ke layar "Integrasi & Audit" ─────────────────────────────────
async def test_KPT2_U2_gudang_ke_master_gudang(klien, kepala_admin):
    d = await _siap(klien, kepala_admin, KSC)
    assert _butir(d, "warehouses")["view"] == "md-warehouses"
    assert [i["key"] for i in d["items"] if i.get("view") == "admin"] == []
    # baris ke hub Badan Usaha & Akses menyebut tab tujuannya
    assert _butir(d, "address").get("tab") == "entities" and _butir(d, "users").get("tab") == "accounts"


# ── U3 — akun kas dan rekening bank dihitung terpisah ─────────────────────────────────────────────────────────────
async def test_KPT2_U3_kas_terpisah_dari_bank(klien, kepala_admin, db):
    await db.bank_accounts.delete_many({"entity_id": KANDA})
    await db.bank_accounts.insert_one({"id": "bank_uji_kpt2_kas1", "name": "Kas Kanda (uji)", "entity_id": KANDA,
                                       "account_type": "cash", "is_active": True})
    d = await _siap(klien, kepala_admin, KANDA)
    assert _butir(d, "cash_account")["ready"] is True
    assert _butir(d, "bank_account")["ready"] is False


# ── U4 — rekening tingkat grup (`entity_id: "all"`) tidak dihitung sebagai milik PT ────────────────────────────────
async def test_KPT2_U4_rekening_grup_tidak_dihitung(klien, kepala_admin, db):
    await db.bank_accounts.insert_one({"id": "bank_uji_kpt2_grup", "name": "Bank Grup (uji)", "entity_id": "all",
                                       "account_type": "bank", "is_active": True})
    d = await _siap(klien, kepala_admin, KANDA)
    assert _butir(d, "bank_account")["ready"] is False
    await db.bank_accounts.delete_one({"id": "bank_uji_kpt2_grup"})


# ── U5 — akun terpetakan wajib dinonaktifkan → pemetaan belum beres; angka = layar Pemetaan Akun ───────────────────
async def test_KPT2_U5_pemetaan_wajib_belum_beres(klien, kepala_admin):
    from pembantu import aktifkan_akun, nonaktifkan_akun
    awal = (await klien.get("/api/gl/account-mappings", headers=kepala_admin, params={"entity_id": KANDA})).json()
    wajib = [r for r in awal["rows"] if r["required"] and r["status"] == "ok"]
    assert wajib, "data acuan: tidak ada pemetaan wajib yang beres"
    kode = wajib[0]["account_code"]
    await nonaktifkan_akun(KANDA, kode)
    try:
        api = (await klien.get("/api/gl/account-mappings", headers=kepala_admin, params={"entity_id": KANDA})).json()
        belum = sum(1 for r in api["rows"] if r["required"] and r["status"] != "ok")
        assert belum >= 1
        b = _butir(await _siap(klien, kepala_admin, KANDA), "gl_mappings")
        assert b["ready"] is False
        assert b["count"] == belum, (b, belum)
        assert b["detail"] == f"{belum} pemetaan akun wajib belum beres"
        assert _butir(await _siap(klien, kepala_admin, KSC), "gl_mappings")["count"] == sum(
            1 for r in (await klien.get("/api/gl/account-mappings", headers=kepala_admin,
                                        params={"entity_id": KSC})).json()["rows"]
            if r["required"] and r["status"] != "ok")   # PT lain tidak ikut berubah
    finally:
        await aktifkan_akun(KANDA, kode)


# ── U6 — periode hari ini tertutup hanya untuk Kanda ──────────────────────────────────────────────────────────────
async def test_KPT2_U6_periode_hari_ini_tertutup(klien, kepala_admin, db):
    from pembantu import tutup_periode
    from services.entity_lifecycle_service import today_wib
    c = await tutup_periode(KANDA, today_wib()[:7])
    try:
        assert _butir(await _siap(klien, kepala_admin, KANDA), "period")["ready"] is False
        assert _butir(await _siap(klien, kepala_admin, KSC), "period")["ready"] is True
    finally:
        await db.period_closings.delete_one({"id": c["id"]})


# ── U7 — termin bawaan lapisan PT yang tidak ada di daftar termin ─────────────────────────────────────────────────
async def test_KPT2_U7_termin_bawaan_tidak_ada(klien, kepala_admin, monkeypatch):
    # KF-T4 — kode termin yang tidak ada di master kini ditolak saat disimpan (400). Keadaan "termin bawaan PT tidak ada
    # di master" (mis. baris master dihapus sesudah disimpan, atau nilai lama sebelum validasi) ditiru di pembacanya.
    from services import config_service as cs
    asli = cs.default_payment_term_code

    async def palsu(entity_id=None, *a, **kw):
        return "TIDAKADA" if entity_id == KANDA else await asli(entity_id, *a, **kw)
    monkeypatch.setattr(cs, "default_payment_term_code", palsu)
    b = _butir(await _siap(klien, kepala_admin, KANDA), "payment_term")
    assert b["ready"] is False and "TIDAKADA" in b["detail"], b
    assert _butir(await _siap(klien, kepala_admin, KSC), "payment_term")["ready"] is True


# ── U8 — pengguna keuangan dibaca dari matriks izin (peran Tanpa Acuan berizin `cash.create`) ──────────────────────
async def test_KPT2_U8_pengguna_keuangan_dari_izin(klien, akun, sesi, db, peran_tanpa_acuan):
    pembaca = await sesi(await akun(await peran_tanpa_acuan({"entity": ["view"]}, label="TA KPT2 baca PT")))
    kas = await peran_tanpa_acuan({"cash": ["view", "create"]}, label="TA KPT2 kas")
    # Admin & Manajer (lintas PT, ber-`cash.create`) dinonaktifkan sementara → yang bisa bekerja di Kanda hanya peran
    # tanpa `cash.create` (Sales/Gudang KSC tidak ditugaskan ke Kanda; pembaca berperan tanpa `cash.create`).
    lintas = [u["id"] async for u in db.users.find({"role": {"$in": ["admin", "manager"]}, "status": "active"},
                                                    {"_id": 0, "id": 1})]
    await db.users.update_many({"id": {"$in": lintas}}, {"$set": {"status": "inactive"}})
    try:
        sebelum = _butir(await _siap(klien, pembaca, KANDA), "finance_user")
        assert sebelum["ready"] is False, sebelum
        assert sebelum["detail"] == "Belum ada pengguna yang bisa mencatat kas untuk PT ini"
        await akun(kas, entitas=(KANDA,))
        sesudah = _butir(await _siap(klien, pembaca, KANDA), "finance_user")
        assert sesudah["ready"] is True and sesudah["count"] == 1, sesudah
    finally:
        await db.users.update_many({"id": {"$in": lintas}}, {"$set": {"status": "active"}})


# ── U9 — penanda tangan: baris tanpa nama tidak dihitung ──────────────────────────────────────────────────────────
async def test_KPT2_U9_penanda_tangan(klien, kepala_admin, db):
    await db.document_branding.update_one({"entity_id": KANDA}, {"$set": {
        "entity_id": KANDA, "signatures": [{"label": "Direktur", "name": ""}]}}, upsert=True)
    assert _butir(await _siap(klien, kepala_admin, KANDA), "signers")["ready"] is False
    await db.document_branding.update_one({"entity_id": KANDA}, {"$set": {
        "signatures": [{"label": "Direktur", "name": "Budi"}]}})
    b = _butir(await _siap(klien, kepala_admin, KANDA), "signers")
    assert b["ready"] is True and "Budi" in b["detail"], b


# ── U10 — bagan akun gagal disiapkan → PT TIDAK tersimpan ────────────────────────────────────────────────────────
async def test_KPT2_U10_bagan_akun_gagal_pt_tidak_tersimpan(klien, kepala_admin, db, monkeypatch):
    from services import gl_service
    asli = gl_service.seed_default_coa
    sisa = {"n": 1}

    async def _palsu(*a, **kw):
        if sisa["n"] > 0:
            sisa["n"] -= 1
            raise RuntimeError("uji: bagan akun dipaksa gagal")
        return await asli(*a, **kw)

    monkeypatch.setattr(gl_service, "seed_default_coa", _palsu)
    sebelum = await db.business_entities.count_documents({})
    r = await _buat_pt(klien, kepala_admin, "KPTDGAGAL")
    assert r.status_code >= 400, r.text
    assert sisa["n"] == 0, "bagan akun tidak dipanggil"
    assert await db.business_entities.count_documents({}) == sebelum
    assert not await db.business_entities.find_one({"short_name": "KPTDGAGAL"})


# ── U11 — penanda lapisan hilang → belum siap → Ulangi penyiapan → siap ──────────────────────────────────────────
async def test_KPT2_U11_ulangi_penyiapan(klien, kepala_admin, db):
    r = await _buat_pt(klien, kepala_admin, "KPTDULANG")
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    doc = await db.business_entities.find_one({"id": eid}, {"_id": 0})
    assert (doc.get("provisioning") or {}).get("coa") is True, doc.get("provisioning")
    assert _butir(r.json()["readiness"], "provisioning")["ready"] is True
    await db.system_settings.delete_many({"scope": eid})
    assert _butir(await _siap(klien, kepala_admin, eid), "provisioning")["ready"] is False
    rr = await klien.post(f"/api/entities/{eid}/provisioning/retry", headers=kepala_admin)
    assert rr.status_code == 200, rr.text
    j = rr.json()
    assert j["entity_id"] == eid and j["provisioning"]["config_layer"] is True, j
    assert _butir(j["readiness"], "provisioning")["ready"] is True
    assert _butir(await _siap(klien, kepala_admin, eid), "provisioning")["ready"] is True


# ── U12 — ulangi penyiapan dua kali: aman diulang ─────────────────────────────────────────────────────────────────
async def test_KPT2_U12_ulangi_dua_kali_aman(klien, kepala_admin, db):
    from services.group_partner_service import KIND_ENTITY
    eid = (await db.business_entities.find_one({"short_name": "KPTDULANG"}, {"_id": 0, "id": 1}))["id"]
    r1 = await klien.post(f"/api/entities/{eid}/provisioning/retry", headers=kepala_admin)
    pemasok_1 = await db.suppliers.count_documents({"partner_kind": KIND_ENTITY})
    r2 = await klien.post(f"/api/entities/{eid}/provisioning/retry", headers=kepala_admin)
    assert (r1.status_code, r2.status_code) == (200, 200), (r1.text, r2.text)
    assert await db.system_settings.count_documents({"scope": eid}) == 1
    assert await db.suppliers.count_documents({"partner_kind": KIND_ENTITY}) == pemasok_1
    langkah = r2.json()["provisioning"]
    assert (langkah["coa"], langkah["config_layer"], langkah["group_partners"]) == (True, True, True), langkah


async def test_KPT2_U12b_ulangi_penyiapan_ikut_izin(klien, akun, sesi, db, peran_tanpa_acuan, peran_manajer_kosong,
                                                   kepala_admin):
    """Pelengkap U11/U12 — izin `entity.update` (Z1, pesan Z6), bukan nama peran; PT tidak ada → 404."""
    eid = (await db.business_entities.find_one({"short_name": "KPTDULANG"}, {"_id": 0, "id": 1}))["id"]
    mk = await sesi(await akun(await peran_manajer_kosong()))
    r = await klien.post(f"/api/entities/{eid}/provisioning/retry", headers=mk)
    assert r.status_code == 403, r.text
    # KP-T9 — nama modul pemilik `entity` kini "Data PT" (diambil dari katalog, dulu "Badan Usaha (PT)").
    assert _detail(r).startswith("Anda belum punya akses untuk") and "'Data PT'" in _detail(r)
    assert "entity." not in _detail(r)
    ta = await sesi(await akun(await peran_tanpa_acuan({"entity": ["update"]}, label="TA KPT2 ubah PT")))
    r = await klien.post(f"/api/entities/{KSC}/provisioning/retry", headers=ta)   # PT penugasannya (N1)
    assert r.status_code == 200, r.text
    assert (await klien.post(f"/api/entities/{eid}/provisioning/retry", headers=ta)).status_code == 404   # bukan PT-nya
    r = await klien.post("/api/entities/ent_tidak_ada_kpt2/provisioning/retry", headers=kepala_admin)
    assert r.status_code == 404, r.text


async def test_KPT2_U18b_pt_baru_langsung_bisa_dipilih(klien, kepala_admin):
    """Pelengkap U18 (sisi server) — "Lengkapi" langsung mengganti PT aktif ke PT baru: permintaan ber-`X-Entity-Id`
    PT baru tidak boleh ditolak 403 karena cache status PT (20 detik) belum memuat PT itu."""
    assert (await klien.get("/api/warehouses", headers=kepala_admin)).status_code == 200   # cache status terisi
    r = await _buat_pt(klien, kepala_admin, "KPTDBARU")
    assert r.status_code == 200, r.text
    h = {**kepala_admin, "X-Entity-Id": r.json()["id"]}
    r2 = await klien.get("/api/warehouses", headers=h)
    assert r2.status_code == 200, r2.text


# ── U13 — pesanan batal tidak dihitung sebagai piutang ────────────────────────────────────────────────────────────
async def test_KPT2_U13_pesanan_batal_bukan_piutang(klien, kepala_admin, db):
    # Hitungan tangan: satu pesanan batal Rp1.000.000, dibayar 0 → piutang terbuka = 0 (dulu Σ grand_total − paid
    # semua pesanan = 1.000.000). Pesanan milik pelanggan Kanda supaya benar-benar ikut dipindai umur piutang.
    await db.customers.insert_one({"id": "cust_uji_kpt2", "name": "Pelanggan Kanda (uji)", "entity_id": KANDA,
                                   "status": "active"})
    await db.sales_orders.insert_one({"id": "so_uji_kpt2_batal", "number": "KANDA/SO-90001", "entity_id": KANDA,
                                      "customer_id": "cust_uji_kpt2", "status": "cancelled", "grand_total": 1000000,
                                      "paid_total": 0, "payments": []})
    d = await _dampak(klien, kepala_admin)
    assert [b for b in d["balances"] if b["key"] == "piutang"] == [], d["balances"]
    # Pembanding (bukan baris spesifikasi): pesanan terkonfirmasi Rp400.000 tanpa bayaran → piutang 400.000.
    await db.sales_orders.insert_one({"id": "so_uji_kpt2_buka", "number": "KANDA/SO-90002", "entity_id": KANDA,
                                      "customer_id": "cust_uji_kpt2", "status": "confirmed", "grand_total": 400000,
                                      "paid_total": 0, "payments": []})
    d = await _dampak(klien, kepala_admin)
    assert [b["amount"] for b in d["balances"] if b["key"] == "piutang"] == [400000], d["balances"]


# ── U14 — hutang pemasok dari sisa tagihan ber-status posted ─────────────────────────────────────────────────────
async def test_KPT2_U14_hutang_pemasok(klien, kepala_admin, db):
    # Hitungan tangan: tagihan posted 500.000 − dibayar 200.000 = sisa 300.000.
    await db.vendor_bills.insert_one({"id": "vb_uji_kpt2", "bill_number": "VB-90001", "entity_id": KANDA,
                                      "status": "posted", "grand_total": 500000, "amount_paid": 200000})
    d = await _dampak(klien, kepala_admin)
    hutang = [b for b in d["balances"] if b["key"] == "hutang"]
    assert len(hutang) == 1 and hutang[0]["amount"] == 300000, d["balances"]
    assert d["can_archive"] is False


# ── U15 — saldo kas & bank dari saldo awal rekening ─────────────────────────────────────────────────────────────────
async def test_KPT2_U15_saldo_kas_bank(klien, kepala_admin, db):
    # Hitungan tangan: Kanda kini punya DUA akun kas (U3: saldo awal 0; ini: 250.000), tanpa transaksi bertaut
    # rekening → transaksi kas lama tanpa rekening tidak dibebankan ke salah satunya (`bank_service._txns_for`, hanya
    # bila satu-satunya akun jenis itu). Σ |saldo| = |0| + |250.000| = 250.000.
    await db.bank_accounts.insert_one({"id": "bank_uji_kpt2_kas2", "name": "Kas Kanda 2 (uji)", "entity_id": KANDA,
                                       "account_type": "cash", "opening_balance": 250000, "is_active": True})
    d = await _dampak(klien, kepala_admin)
    kas = [b for b in d["balances"] if b["key"] == "kas_bank"]
    assert len(kas) == 1 and kas[0]["amount"] == 250000, d["balances"]


# ── U16 — uang muka terbuka + karyawan → penghalang arsip ───────────────────────────────────────────────────────────
async def test_KPT2_U16_uang_muka_dan_karyawan_menghalangi(klien, kepala_admin, db):
    await db.cash_advances.insert_one({"id": "ca_uji_kpt2", "number": "KANDA/PD-90001", "entity_id": KANDA,
                                       "status": "approved", "amount": 100000})
    await db.hr_employees.insert_one({"id": "emp_uji_kpt2", "code": "EMP-90001", "name": "Karyawan Kanda (uji)",
                                      "entity_id": KANDA, "status": "active"})
    d = await _dampak(klien, kepala_admin)
    um = [x for x in d["open_documents"] if x["label"] == "Uang muka"]
    assert len(um) == 1 and um[0]["count"] == 1 and um[0]["examples"] == ["KANDA/PD-90001"], d["open_documents"]
    assert d["employees"] == 1
    cek = {c["key"]: c for c in d["checks"]}
    assert list(cek) == ["pengguna", "dokumen", "saldo", "karyawan", "periode"], d["checks"]
    assert all({"key", "label", "ok", "detail"} <= set(c) for c in d["checks"])
    assert cek["dokumen"]["ok"] is False and cek["karyawan"]["ok"] is False and cek["saldo"]["ok"] is False
    assert "Rp 300.000" in cek["saldo"]["detail"], cek["saldo"]   # nominal berpemisah ribuan
    r = await klien.delete(f"/api/entities/{KANDA}", headers=kepala_admin)
    assert r.status_code == 409, r.text
    blok: List[str] = r.json()["detail"]["blockers"]
    assert any("dokumen masih terbuka" in b and "Uang muka" in b for b in blok), blok
    assert "1 karyawan masih terdaftar di PT ini — pindahkan atau akhiri dulu" in blok, blok


# ── U17 — cara memaksa tidak berubah; PT terarsip menolak ulang penyiapan ──────────────────────────────────────────
async def test_KPT2_U17_paksa_arsip_dengan_alasan(klien, kepala_admin, db):
    r = await klien.delete(f"/api/entities/{KANDA}", headers=kepala_admin,
                           params={"force": "true", "reason": "Tutup usaha"})
    assert r.status_code == 200, r.text
    assert (await db.business_entities.find_one({"id": KANDA}, {"_id": 0, "status": 1}))["status"] == "archived"
    r = await klien.post(f"/api/entities/{KANDA}/provisioning/retry", headers=kepala_admin)
    assert r.status_code == 409 and _detail(r) == PESAN_ARSIP, r.text
