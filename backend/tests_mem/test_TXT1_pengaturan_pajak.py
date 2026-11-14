"""TX-T1 — pengaturan pajak bertanggal berlaku, potret pajak di dokumen, dan data pajak pelanggan
(docs/blueprint/unit/TX-T1.md, U1–U15; keputusan K-33).

Persiapan: `ent_ksc` PKP dengan kunci bawaan (tarif 12, DPP nilai lain ya, harga belum termasuk PPN), `ent_kanda` bukan
PKP, `ent_dfd68e78add8` (PT ketiga seed, PKP). Tarif efektif bawaan = 12 × 11 ÷ 12 = 11 %.

Fixture (DISISIP langsung ke database): produk uji `prd_txt1_*` (harga dasar per yard, tanpa stok → baris jadi
backorder), pelanggan uji `cus_txt1_*`, kontrak antar-PT (U14). Alur (pesanan, override, faktur, PATCH pelanggan,
pengaturan) dijalankan lewat API. Pesanan dibuat Admin seed; status pesanan dinaikkan ke `confirmed` langsung di database
(fixture) sebelum faktur diterbitkan — alur konfirmasi gudang di luar unit ini.
"""
from __future__ import annotations

import datetime

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC, KANDA, PT3 = "ent_ksc", "ent_kanda", "ent_dfd68e78add8"
PESAN_403_NON_PPN = ("Anda belum punya akses untuk membuat pesanan tanpa PPN. "
                     "Minta Admin menambahkan akses 'Pesanan Penjualan'.")
TUJUH = ("tax.dpp_nilai_lain_pembilang", "tax.dpp_nilai_lain_penyebut", "tax.pembulatan_tingkat",
         "tax.pembulatan_satuan", "tax.kode_transaksi_diizinkan", "tax.kode_transaksi_bawaan",
         "tax.kode_transaksi_bawaan_dpp_nilai_lain")
SIMPAN: dict = {}


def _isi(key, value, scope_type="entity", scope_id=KSC, effective_from="", reason="uji TX-T1"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id,
                       "reason": reason, "effective_from": effective_from}]}


async def atur(klien, h, key, value, scope_type="entity", scope_id=KSC, effective_from=""):
    r = await klien.put("/api/config/values", headers=h, json=_isi(key, value, scope_type, scope_id, effective_from))
    assert r.status_code == 200, r.text
    return r.json()["saved"][0]


async def cabut(klien, h, key, scope_id=KSC):
    r = await klien.post("/api/config/values/clear", headers=h,
                         json={"key": key, "scope_type": "entity", "scope_id": scope_id, "reason": "pulihkan uji TX-T1"})
    assert r.status_code == 200, r.text


def _produk(pid: str, harga: float) -> dict:
    return {"id": pid, "sku": pid.upper(), "name": f"Kain Uji {pid}", "category": "Kain", "base_unit": "yard",
            "price": harga, "status": "active", "is_active": True, "lifecycle": "produksi", "created_at": now_iso()}


def _pelanggan(cid: str, entity_id: str = KSC, **lain) -> dict:
    return {"id": cid, "code": cid.upper(), "name": f"Toko {cid}", "entity_id": entity_id, "status": "active",
            "credit_limit": 0, "pic_name": "Bu Rina", "phone": "6281200000000",
            "addresses": [{"id": f"addr_{cid}", "label": "Toko", "recipient_name": "Bu Rina", "phone": "6281200000000",
                           "city": "Bandung", "address": "Jl. Uji No. 1", "is_primary": True}],
            "created_at": now_iso(), **lain}


@pytest.fixture(scope="module")
async def uji(klien, db, kepala_admin):
    await db.products.insert_many([
        _produk("prd_txt1_a", 1_200_000), _produk("prd_txt1_b", 1_234_567),
        _produk("prd_txt1_c", 100_005), _produk("prd_txt1_d", 100_005)])
    await db.customers.insert_many([
        _pelanggan("cus_txt1_a", npwp="01.111.222.3-444.000"), _pelanggan("cus_txt1_kode", npwp="01.111.222.3-555.000"),
        _pelanggan("cus_txt1_nik"), _pelanggan("cus_txt1_kosong"), _pelanggan("cus_txt1_kanda", KANDA),
        _pelanggan("cus_txt1_pt3", PT3)])
    return {"adm": kepala_admin}


async def pesan(klien, h, *, baris=(("prd_txt1_a", 10),), customer="cus_txt1_a", entity=KSC, **lain):
    r = await klien.post("/api/sales-orders", headers={**h, "X-Entity-Id": entity}, json={
        "customer_id": customer, "shipping_address_id": "", "entity_id": entity, "allow_backorder": True,
        "items": [{"product_id": p, "quantity": q, "unit": "yard"} for p, q in baris], **lain})
    return r


async def pesan_ok(klien, h, **kw) -> dict:
    r = await pesan(klien, h, **kw)
    assert r.status_code == 200, r.text
    return r.json()


async def terbitkan(klien, db, h, oid: str, **isi):
    await db.sales_orders.update_one({"id": oid}, {"$set": {"status": "confirmed"}})   # fixture: naik ke confirmed
    return await klien.post(f"/api/sales-orders/{oid}/tax-invoice", headers=h, json=isi)


# ── U1 — bawaan sama dengan sebelum unit ini ────────────────────────────────────────────────────────────────────────
async def test_TXT1_U1a_pesanan_bawaan_angka_sama_dengan_sebelumnya(klien, db, uji):
    # 10 yd × 1.200.000 = 12.000.000 → DPP 12.000.000 × 11/12 = 11.000.000 → PPN 12 % × DPP = 1.320.000 → total 13.320.000
    o = await pesan_ok(klien, uji["adm"])
    SIMPAN["u1"] = o["id"]
    assert (o["net_subtotal"], o["dpp"], o["ppn_amount"], o["grand_total"]) == (12_000_000, 11_000_000, 1_320_000,
                                                                                13_320_000)


async def test_TXT1_U1b_potret_pajak_tersimpan(klien, db, uji):
    o = await db.sales_orders.find_one({"id": SIMPAN["u1"]}, {"_id": 0})
    s = o.get("tax_snapshot") or {}
    assert (s.get("ppn_rate"), s.get("dpp_nilai_lain"), s.get("dpp_pembilang"), s.get("dpp_penyebut"),
            s.get("ppn_mode"), s.get("pembulatan_tingkat"), s.get("pembulatan_satuan"), s.get("is_pkp")) == \
        (12.0, True, 11, 12, "excluded", "dokumen", "dua_desimal", True), s
    assert s.get("berlaku_pada"), s


# ── U2 — tarif dijadwalkan: pesanan hari ini tetap; hitungan pada tanggal berlaku memakai tarif baru ──────────────────
async def test_TXT1_U2_tarif_berjadwal_berlaku_sejak_tanggalnya(klien, db, uji):
    from services.config_service import compute_tax
    baris = await atur(klien, uji["adm"], "tax.ppn_rate", 13, effective_from="2027-01-01T00:00:00+07:00")
    try:
        o = await pesan_ok(klien, uji["adm"])
        assert o["ppn_amount"] == 1_320_000   # hari ini: 12 % × 11/12
        # 15 Jan 2027: 12.000.000 × 13 % × 11/12 = 1.430.000
        hasil = await compute_tax(12_000_000, KSC, at=datetime.datetime(2027, 1, 15, tzinfo=datetime.timezone.utc))
        assert (hasil["ppn_rate"], hasil["ppn_amount"]) == (13.0, 1_430_000), hasil
        hari_ini = await compute_tax(12_000_000, KSC)
        assert hari_ini["ppn_amount"] == 1_320_000
    finally:
        r = await klien.post("/api/config/values/cancel-scheduled", headers=uji["adm"],
                             json={"id": baris["id"], "reason": "pulihkan uji TX-T1"})
        assert r.status_code == 200, r.text


# ── U3 — hitung ulang dokumen lama memakai potretnya ────────────────────────────────────────────────────────────────
async def test_TXT1_U3_override_dan_faktur_memakai_potret(klien, db, uji):
    oid = SIMPAN["u1"]
    pid = "prd_txt1_a"
    await atur(klien, uji["adm"], "tax.ppn_rate", 13)   # berlaku sekarang
    try:
        r = await klien.post(f"/api/sales-orders/{oid}/override", headers=uji["adm"], json={
            "note": "uji tambah jumlah TX-T1", "lines": [{"product_id": pid, "quantity": 20}]})
        assert r.status_code == 200, r.text
        o = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
        # 24.000.000 × 12 % × 11/12 = 2.640.000 (potret), bukan 24.000.000 × 13 % × 11/12 = 2.860.000
        assert (o["net_subtotal"], o["ppn_amount"]) == (24_000_000, 2_640_000), (o["net_subtotal"], o["ppn_amount"])
        assert o["tax_snapshot"]["ppn_rate"] == 12.0
        r = await terbitkan(klien, db, uji["adm"], oid)
        assert r.status_code == 200, r.text
        f = r.json()
        assert f["tax_snapshot"]["ppn_rate"] == 12.0 and f["tax_snapshot"]["dpp_pembilang"] == 11, f["tax_snapshot"]
        assert f["ppn_amount"] == 2_640_000
        SIMPAN["fkt_u3"] = f["id"]
    finally:
        await cabut(klien, uji["adm"], "tax.ppn_rate")


# ── U4 — faktor per PT; PT lain tidak ikut ──────────────────────────────────────────────────────────────────────────
async def test_TXT1_U4_faktor_per_pt(klien, db, uji):
    from services.config_service import compute_order_pricing
    await atur(klien, uji["adm"], "tax.dpp_nilai_lain_pembilang", 12)
    try:
        o = await pesan_ok(klien, uji["adm"])
        # 12.000.000 × 12/12 = DPP 12.000.000 → PPN 12 % = 1.440.000
        assert (o["dpp"], o["ppn_amount"]) == (12_000_000, 1_440_000)
        assert o["tax_snapshot"]["dpp_pembilang"] == 12
        lain = await compute_order_pricing([{"price": 1_200_000, "quantity": 10}], PT3, 0)
        assert (lain["dpp"], lain["ppn_amount"]) == (11_000_000, 1_320_000)
        assert lain["tax_snapshot"]["dpp_pembilang"] == 11
    finally:
        await cabut(klien, uji["adm"], "tax.dpp_nilai_lain_pembilang")


# ── U5 / U6 — pembulatan ────────────────────────────────────────────────────────────────────────────────────────────
async def test_TXT1_U5_rupiah_penuh(klien, db, uji):
    await atur(klien, uji["adm"], "tax.pembulatan_satuan", "rupiah_penuh")
    try:
        o = await pesan_ok(klien, uji["adm"], baris=(("prd_txt1_b", 1),))
        # 1.234.567 × 11 % = 135.802,37 → 135.802; DPP 1.234.567 × 11/12 = 1.131.686,42 → 1.131.686; total 1.370.369
        assert (o["ppn_amount"], o["dpp"], o["grand_total"]) == (135_802, 1_131_686, 1_370_369)
        assert o["tax_snapshot"]["pembulatan_satuan"] == "rupiah_penuh"
    finally:
        await cabut(klien, uji["adm"], "tax.pembulatan_satuan")


async def test_TXT1_U6_per_baris_lawan_per_dokumen(klien, db, uji):
    await atur(klien, uji["adm"], "tax.pembulatan_satuan", "rupiah_penuh")
    await atur(klien, uji["adm"], "tax.pembulatan_tingkat", "baris")
    dua = (("prd_txt1_c", 1), ("prd_txt1_d", 1))
    try:
        o = await pesan_ok(klien, uji["adm"], baris=dua)
        # tiap baris 100.005 × 11 % = 11.000,55 → 11.001; dijumlah 22.002
        assert [it.get("ppn_amount") for it in o["items"]] == [11_001, 11_001]
        assert o["ppn_amount"] == 22_002 and o["grand_total"] == 222_012
        await atur(klien, uji["adm"], "tax.pembulatan_tingkat", "dokumen")
        o = await pesan_ok(klien, uji["adm"], baris=dua)
        # 200.010 × 11 % = 22.001,10 → 22.001
        assert o["ppn_amount"] == 22_001 and all("ppn_amount" not in it for it in o["items"])
    finally:
        await cabut(klien, uji["adm"], "tax.pembulatan_tingkat")
        await cabut(klien, uji["adm"], "tax.pembulatan_satuan")


# ── U7 / U8 — kode transaksi dari pengaturan dan pelanggan ──────────────────────────────────────────────────────────
async def test_TXT1_U7_kode_bawaan_dari_pengaturan_dan_pelanggan(klien, db, uji):
    h = uji["adm"]
    o = await pesan_ok(klien, h)
    r = await terbitkan(klien, db, h, o["id"])
    assert r.status_code == 200, r.text
    assert r.json()["kode_transaksi"] == "04"
    await atur(klien, h, "tax.kode_transaksi_bawaan_dpp_nilai_lain", "01")
    try:
        o = await pesan_ok(klien, h)
        r = await terbitkan(klien, db, h, o["id"])
        assert r.status_code == 200, r.text
        assert r.json()["kode_transaksi"] == "01"
    finally:
        await cabut(klien, h, "tax.kode_transaksi_bawaan_dpp_nilai_lain")
    r = await klien.patch("/api/customers/cus_txt1_kode", headers=h, json={"data": {"tax_profile": {
        "id_type": "npwp", "kode_transaksi": "02"}}})
    assert r.status_code == 200, r.text
    o = await pesan_ok(klien, h, customer="cus_txt1_kode")
    r = await terbitkan(klien, db, h, o["id"])
    assert r.status_code == 200, r.text
    assert r.json()["kode_transaksi"] == "02"


async def test_TXT1_U8_kode_di_luar_daftar_pt_ditolak(klien, db, uji):
    h = uji["adm"]
    await atur(klien, h, "tax.kode_transaksi_diizinkan", ["01", "02", "03", "04", "06", "08", "09"])
    try:
        o = await pesan_ok(klien, h)
        r = await terbitkan(klien, db, h, o["id"], kode_transaksi="07")
        assert r.status_code == 400, r.text
        assert r.json()["detail"] == "Kode transaksi 07 tidak dipakai PT ini."
        assert await db.tax_invoices.count_documents({"order_id": o["id"]}) == 0
        # pembanding: kode di daftar tetap sah; mengisi NSFP dengan kode di luar daftar juga ditolak
        r = await terbitkan(klien, db, h, o["id"], kode_transaksi="08")
        assert r.status_code == 200, r.text
        r = await klien.patch(f"/api/tax-invoices/{r.json()['id']}/nsfp", headers=h,
                              json={"nsfp": "0100002612340001", "kode_transaksi": "07"})
        assert r.status_code == 400 and r.json()["detail"] == "Kode transaksi 07 tidak dipakai PT ini.", r.text
    finally:
        await cabut(klien, h, "tax.kode_transaksi_diizinkan")


# ── U9 / U10 — data pajak pelanggan ─────────────────────────────────────────────────────────────────────────────────
async def test_TXT1_U9_profil_pajak_pelanggan(klien, db, uji):
    h = uji["adm"]
    url = "/api/customers/cus_txt1_nik"
    r = await klien.patch(url, headers=h, json={"data": {"tax_profile": {"id_type": "nik", "nik": "12ab"}}})
    assert r.status_code == 400 and r.json()["detail"] == "NIK hanya boleh berisi angka.", r.text
    r = await klien.patch(url, headers=h, json={"data": {"tax_profile": {"id_type": "nik"}}})
    assert r.status_code == 400 and r.json()["detail"] == "NIK wajib diisi bila identitas pajak memakai NIK.", r.text
    r = await klien.patch(url, headers=h, json={"data": {"npwp": "01.23A"}})
    assert r.status_code == 400 and r.json()["detail"] == "NPWP hanya boleh berisi angka.", r.text
    r = await klien.patch(url, headers=h, json={"data": {"tax_profile": {
        "id_type": "nik", "nik": "3273011234560001", "tax_name": "Rina Wati", "tax_address": "Jl. Pajak 2, Bandung",
        "is_pkp": False, "always_tax_invoice": True}}})
    assert r.status_code == 200, r.text
    assert r.json()["tax_data_warnings"] == []
    c = await db.customers.find_one({"id": "cus_txt1_nik"}, {"_id": 0})
    assert c["tax_profile"]["nik"] == "3273011234560001" and c["tax_profile"]["always_tax_invoice"] is True
    # Jumlah digit menyimpang → disimpan + peringatan (tidak menolak) — konfirmasi konsultan pajak.
    r = await klien.patch("/api/customers/cus_txt1_kosong", headers=h, json={"data": {"tax_profile": {
        "id_type": "nik", "nik": "12345"}}})
    assert r.status_code == 200, r.text
    assert len(r.json()["tax_data_warnings"]) == 1 and "NIK berisi 5 angka" in r.json()["tax_data_warnings"][0]
    r = await klien.patch("/api/customers/cus_txt1_kosong", headers=h, json={"data": {"tax_profile": {}}})
    assert r.status_code == 200, r.text
    o = await pesan_ok(klien, h, customer="cus_txt1_nik")
    r = await terbitkan(klien, db, h, o["id"])
    assert r.status_code == 200, r.text
    ct = r.json()["customer_tax"]
    assert (ct["id_type"], ct["id_number"], ct["tax_name"], ct["tax_address"], ct["is_pkp"]) == \
        ("nik", "3273011234560001", "Rina Wati", "Jl. Pajak 2, Bandung", False)
    assert r.json()["data_incomplete"] == []


async def test_TXT1_U10_tanpa_identitas_tetap_terbit_dengan_tanda(klien, db, uji):
    h = uji["adm"]
    o = await pesan_ok(klien, h, customer="cus_txt1_kosong")
    r = await terbitkan(klien, db, h, o["id"])
    assert r.status_code == 200, r.text
    assert "identitas_pajak" in r.json()["data_incomplete"]
    assert r.json()["customer_tax"]["tax_address"] == "Jl. Uji No. 1, Bandung"   # kosong = alamat utama


# ── U11 / U12 — pesanan tanpa PPN ───────────────────────────────────────────────────────────────────────────────────
async def test_TXT1_U11_pesanan_tanpa_ppn(klien, db, uji, sesi):
    isi = {"tax_override": "non_ppn"}
    r = await pesan(klien, await sesi("sales@kainnusantara.id"), customer="cus_txt1_a",
                    **isi, tax_override_reason="Kawasan berikat")
    assert r.status_code == 403 and r.json()["detail"] == PESAN_403_NON_PPN, r.text
    mgr = await sesi("manager@kainnusantara.id")
    r = await pesan(klien, mgr, **isi)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Alasan pesanan tanpa PPN wajib diisi (minimal 10 huruf)."
    r = await pesan(klien, mgr, **isi, tax_override_reason="Kawasan berikat")
    assert r.status_code == 200, r.text
    o = await db.sales_orders.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert (o["ppn_amount"], o["grand_total"]) == (0, 12_000_000)
    assert o["tax_override_reason"] == "Kawasan berikat"
    assert o["tax_override_by"]   # nama pembuat tercatat
    assert (o["tax_snapshot"]["is_pkp"], o["tax_snapshot"]["ppn_rate"]) == (False, 0.0)


async def test_TXT1_U12_izin_dari_peran_bukan_nama(klien, db, uji, akun, sesi, peran_tanpa_acuan,
                                                    peran_manajer_kosong, peran_sopir):
    isi = {"tax_override": "non_ppn", "tax_override_reason": "Pelanggan kawasan berikat"}
    rid = await peran_tanpa_acuan({"order": ["view", "create", "tax_override"], "customer": ["view"]},
                                  label="Pesanan Tanpa PPN TX-T1")
    r = await pesan(klien, await sesi(await akun(rid)), **isi)
    assert r.status_code == 200, r.text
    assert r.json()["ppn_amount"] == 0
    r = await pesan(klien, await sesi(await akun(await peran_manajer_kosong())), **isi)
    assert r.status_code == 403, r.text
    r = await pesan(klien, await sesi(await akun(peran_sopir)), **isi)
    assert r.status_code == 403, r.text


# ── U13 — PT bukan PKP ──────────────────────────────────────────────────────────────────────────────────────────────
async def test_TXT1_U13a_pt_bukan_pkp_tanpa_ppn(klien, db, uji):
    await atur(klien, uji["adm"], "tax.ppn_rate", 13, scope_id=KANDA)   # apa pun nilai kunci tarif
    try:
        o = await pesan_ok(klien, uji["adm"], customer="cus_txt1_kanda", entity=KANDA)
        assert (o["ppn_amount"], o["grand_total"], o["is_pkp"]) == (0, 12_000_000, False)
        SIMPAN["u13"] = o["id"]
    finally:
        await cabut(klien, uji["adm"], "tax.ppn_rate", scope_id=KANDA)


async def test_TXT1_U13b_potret_pt_bukan_pkp(klien, db, uji):
    o = await db.sales_orders.find_one({"id": SIMPAN["u13"]}, {"_id": 0})
    assert (o.get("tax_snapshot") or {}).get("is_pkp") is False, o.get("tax_snapshot")
    assert o["tax_snapshot"]["ppn_rate"] == 0.0


# ── U14 — antar-PT: faktor dibaca dari tempat yang sama ─────────────────────────────────────────────────────────────
async def _transaksi_antar_pt(klien, h) -> dict:
    r = await klien.post("/api/interco/transactions", headers=h, json={
        "seller_entity_id": KSC, "buyer_entity_id": KANDA, "items": [{"product_id": "prd_txt1_ic", "quantity": 100}]})
    assert r.status_code == 200, r.text
    pair = r.json()
    from db import db as _db
    return await _db.interco_transactions.find_one({"pair_id": pair["pair_id"], "role": "seller"}, {"_id": 0})


async def test_TXT1_U14_dpp_faktur_antar_pt(klien, db, uji, akun, sesi):
    from services.interco_tax_service import _faktur_dpp
    await db.products.insert_one({**_produk("prd_txt1_ic", 120_000), "base_unit": "meter"})
    await db.supplier_contracts.insert_one({
        "id": "ctr_txt1", "contract_number": "KTR-TXT1", "entity_id": KSC, "partner_kind": "entity",
        "partner_id": KANDA, "product_id": "prd_txt1_ic", "status": "active", "tariff_rate": 120_000,
        "valid_from": "2026-01-01", "created_at": now_iso()})
    mgr = await sesi(await akun("manager", entitas=(KSC, KANDA)))
    lama = await _transaksi_antar_pt(klien, mgr)
    # 100 m × 120.000 = 12.000.000; penjual PKP ber-DPP nilai lain → DPP faktur 12.000.000 × 11/12 = 11.000.000
    assert lama["subtotal"] == 12_000_000 and lama["tax_dpp_nilai_lain"] is True
    assert _faktur_dpp(lama, lama["subtotal"]) == 11_000_000
    assert lama["tax_rate"] == 11.0
    await atur(klien, uji["adm"], "tax.dpp_nilai_lain_pembilang", 12)
    try:
        baru = await _transaksi_antar_pt(klien, mgr)
        assert _faktur_dpp(baru, baru["subtotal"]) == 12_000_000   # faktor 12/12 dari tax_settings PT penjual
        assert baru["tax_rate"] == 12.0
        assert _faktur_dpp(lama, lama["subtotal"]) == 11_000_000   # transaksi lama: potret saat dibuat
    finally:
        await cabut(klien, uji["adm"], "tax.dpp_nilai_lain_pembilang")


# ── U15 — putaran tujuh kunci; pembilang 0 ditolak ──────────────────────────────────────────────────────────────────
async def test_TXT1_U15_putaran_tujuh_kunci(klien, db, uji):
    import config_registry as reg
    from services.config_resolver import value_of
    h = uji["adm"]
    lain = {"tax.dpp_nilai_lain_pembilang": 10, "tax.dpp_nilai_lain_penyebut": 11, "tax.pembulatan_tingkat": "baris",
            "tax.pembulatan_satuan": "rupiah_penuh", "tax.kode_transaksi_diizinkan": ["01", "04"],
            "tax.kode_transaksi_bawaan": "02", "tax.kode_transaksi_bawaan_dpp_nilai_lain": "01"}
    for key in TUJUH:
        e = reg.require(key)
        assert e["scopes"] == ["global", "entity"] and e["risk"] == "high" and e["requires_reason"], key
        assert e["permission"] == ["accounting", "manage"] and e["group"] == "pajak-pembukuan", key
        assert e["consumers"][0] == "services/tax_config_service.py:tax_settings", key
        try:
            await atur(klien, h, key, lain[key], scope_type="global", scope_id="")
            assert await value_of(key, {"entity_id": KSC}) == lain[key], key
            await atur(klien, h, key, e["default"], scope_id=KANDA)
            assert await value_of(key, {"entity_id": KANDA}) == e["default"], key
            assert await value_of(key, {"entity_id": KSC}) == lain[key], key   # PT lain tidak ikut
            r = await klien.put("/api/config/values", headers=h, json=_isi(key, "__tidak_sah__", "global", ""))
            assert r.status_code == 400, (key, r.text)
            r = await klien.put("/api/config/values", headers=h, json=_isi(key, lain[key], "global", "", reason=""))
            assert r.status_code == 400, (key, r.text)   # wajib beralasan
        finally:
            await cabut(klien, h, key, scope_id=KANDA)
            r = await klien.post("/api/config/values/reset", headers=h,
                                 json={"key": key, "scope_type": "global", "reason": "pulihkan uji TX-T1"})
            assert r.status_code == 200, r.text
        assert await value_of(key, {"entity_id": KSC}) == e["default"], key
    r = await klien.put("/api/config/values", headers=h, json=_isi("tax.dpp_nilai_lain_pembilang", 0, "global", ""))
    assert r.status_code == 400, r.text


# ── tambahan: satu fungsi bulat; "Coba dulu" memakai faktor pengaturan ──────────────────────────────────────────────
def test_TXT1_round_money_satu_fungsi():
    from services.tax_config_service import round_money
    assert round_money(135_802.37, "dua_desimal") == 135_802.37
    assert round_money(135_802.37, "rupiah_penuh") == 135_802
    assert round_money(11_000.55, "rupiah_penuh") == 11_001
    with pytest.raises(ValueError):
        round_money(1, "seribu")


async def test_TXT1_coba_dulu_memakai_faktor_pengaturan(klien, uji):
    r = await klien.post("/api/config/simulate", headers=uji["adm"], json={
        "key": "tax.ppn_rate", "ctx": {"entity_id": KSC}, "sample": {"subtotal": 12_000_000},
        "overrides": {"tax.dpp_nilai_lain_pembilang": 12}})
    assert r.status_code == 200, r.text
    assert (r.json()["breakdown"]["dpp"], r.json()["breakdown"]["ppn_amount"]) == (12_000_000, 1_440_000)


async def test_TXT1_pengaturan_efektif_memuat_aturan_pajak_mesin(klien, uji, sesi):
    s = (await klien.get("/api/settings/effective", headers=await sesi("sales@kainnusantara.id"))).json()
    t = s["tax"]
    assert (t["dpp_nilai_lain_pembilang"], t["dpp_nilai_lain_penyebut"], t["pembulatan_tingkat"],
            t["pembulatan_satuan"], t["kode_transaksi_bawaan"]) == (11, 12, "dokumen", "dua_desimal", "01")
    assert t["kode_transaksi_diizinkan"] == ["01", "02", "03", "04", "06", "07", "08", "09"]
