"""PK-40 — pajak: keunikan faktur, rekap tanpa potongan, masa pajak terkunci, basis PPh 21 (SL-13, FY-16).

Spesifikasi: `docs/blueprint/unit/PK-40.md` (U1, U3–U5, U7–U16 lapis B; U2 & U6 lapis A di
`backend/tests/test_bp_PK40_serentak.py`).

Fixture (DISISIP langsung ke database):
  * pelanggan `cus_pk40` (PT `ent_ksc`, PKP) + pesanan terkonfirmasi ber-PPN `so_pk40_1`, `so_pk40_2`, `so_pk40_okt`,
    `so_pk40_nov` — DPP 1.000.000, PPN 110.000 per pesanan; `so_pk40_kanda` di `ent_kanda` (dijadikan PKP uji);
  * U7: 6.000 faktur keluaran aktif masa 2026-10 (DPP 10.000, PPN 1.100) + satu jurnal Cr PPN keluaran 6.600.000;
  * U10: tagihan pemasok ber-PPN `vb_pk40_okt` (tanggal 2026-10-15);
  * U14/U15: penggajian + slip; jurnal gaji U14 lewat `gl_service.post_payroll_run` (alur layanan).
Alur (terbit/ganti/batal/NSFP faktur, faktur masukan, rekam PPh, kunci/buka masa, rekap) dijalankan lewat API.

Batas lapis B: mongomock menegakkan indeks unik parsial `$type`/`$gt` (dibuktikan U4b) tetapi bukan balapan; uji
bersamaan ada di lapis A.
"""
from __future__ import annotations

import datetime

import pytest

from pembantu import jumlah, jurnal

pytestmark = pytest.mark.anyio

ENT = "ent_ksc"
NSFP_A = "010.000-26.00000001"
NSFP_A_DIGIT = "0100002600000001"
SIMPAN: dict = {}


def _sekarang() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _pesanan(oid: str, entity_id: str = ENT) -> dict:
    # Hitungan tangan: 10 m × 100.000 = DPP 1.000.000; PPN 11% = 110.000; total 1.110.000.
    return {"id": oid, "number": oid.upper(), "entity_id": entity_id, "customer_id": "cus_pk40",
            "customer_name": "Toko Pajak", "status": "confirmed", "subtotal": 1_000_000, "dpp": 1_000_000,
            "net_subtotal": 1_000_000, "ppn_amount": 110_000, "ppn_rate": 11, "grand_total": 1_110_000,
            "is_pkp": True, "items": [{"product_name": "Kain Uji", "quantity": 10, "unit": "m", "price": 100_000,
                                       "line_total": 1_000_000}],
            "payments": [], "created_at": _sekarang()}


@pytest.fixture(scope="module")
async def uji(klien, db, kepala_admin, sesi):
    await db.customers.insert_one({"id": "cus_pk40", "name": "Toko Pajak", "entity_id": ENT, "status": "active",
                                   "npwp": "01.234.567.8-901.000", "created_at": _sekarang()})
    await db.sales_orders.insert_many([_pesanan("so_pk40_1"), _pesanan("so_pk40_2"), _pesanan("so_pk40_okt"),
                                       _pesanan("so_pk40_nov"), _pesanan("so_pk40_kanda", "ent_kanda")])
    await db.business_entities.update_one({"id": "ent_kanda"}, {"$set": {"default_tax_mode": "ppn"}})   # PKP uji
    return {"adm": kepala_admin, "adm_kanda": await sesi("admin@kainnusantara.id", entitas="ent_kanda")}


async def _terbit(klien, h, oid: str, **isi):
    return await klien.post(f"/api/sales-orders/{oid}/tax-invoice", json=isi, headers=h)


async def _rekap(klien, h, periode: str, ent: str = ENT) -> dict:
    r = await klien.get("/api/tax/vat-summary", params={"period": periode, "entity_id": ent}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _masa_berjalan() -> str:
    from services.book_date import periode_buku
    return periode_buku()


# ── Keunikan faktur keluaran (SL-13) ────────────────────────────────────────
async def test_PK40_U1_terbit_dua_kali_satu_faktur_aktif(klien, db, uji):
    r1 = await _terbit(klien, uji["adm"], "so_pk40_1")
    assert r1.status_code == 200, r1.text
    SIMPAN["f1"] = r1.json()
    r2 = await _terbit(klien, uji["adm"], "so_pk40_1")
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"] == (f"Faktur Pajak sudah diterbitkan untuk order ini ({r1.json()['number']}). "
                                   "Gunakan Pengganti untuk revisi.")
    assert await jumlah("tax_invoices", {"order_id": "so_pk40_1"}) == 1
    # Sebelum unit ini: tidak ada field `active_key` (keunikan hanya dijaga "cari dulu, lalu sisip").
    assert await jumlah("tax_invoices", {"active_key": "so:so_pk40_1"}) == 1


async def test_PK40_U3_ganti_lalu_batalkan_pengganti(klien, db, uji):
    f1 = SIMPAN["f1"]
    r = await klien.post(f"/api/tax-invoices/{f1['id']}/replace", json={"reason": "koreksi alamat"}, headers=uji["adm"])
    assert r.status_code == 200, r.text
    f2 = r.json()
    asli = await db.tax_invoices.find_one({"id": f1["id"]}, {"_id": 0})
    ganti = await db.tax_invoices.find_one({"id": f2["id"]}, {"_id": 0})
    assert asli["replaced_by_id"] == f2["id"]
    assert "active_key" not in asli
    assert ganti["active_key"] == "so:so_pk40_1"
    r = await _terbit(klien, uji["adm"], "so_pk40_1")
    assert r.status_code == 409, r.text
    r = await klien.post(f"/api/tax-invoices/{f1['id']}/replace", json={"reason": "ganti kedua kali"},
                         headers=uji["adm"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "Faktur ini sudah pernah diganti."
    r = await klien.post(f"/api/tax-invoices/{f2['id']}/cancel", json={"reason": "pengganti salah"}, headers=uji["adm"])
    assert r.status_code == 200, r.text
    asli = await db.tax_invoices.find_one({"id": f1["id"]}, {"_id": 0})
    ganti = await db.tax_invoices.find_one({"id": f2["id"]}, {"_id": 0})
    assert asli.get("replaced_by_id") is None
    assert asli["active_key"] == "so:so_pk40_1"
    assert "active_key" not in ganti and ganti["status"] == "batal"
    assert await jumlah("tax_invoices", {"active_key": "so:so_pk40_1"}) == 1


async def test_PK40_U4_nsfp_kembar_ditolak_walau_format_beda(klien, db, uji):
    f1 = SIMPAN["f1"]
    r = await klien.patch(f"/api/tax-invoices/{f1['id']}/nsfp", json={"nsfp": NSFP_A}, headers=uji["adm"])
    assert r.status_code == 200, r.text
    assert (await db.tax_invoices.find_one({"id": f1["id"]}))["nsfp_key"] == NSFP_A_DIGIT
    r = await _terbit(klien, uji["adm"], "so_pk40_2")
    assert r.status_code == 200, r.text
    SIMPAN["f_so2"] = r.json()
    r = await klien.patch(f"/api/tax-invoices/{SIMPAN['f_so2']['id']}/nsfp", json={"nsfp": NSFP_A_DIGIT},
                          headers=uji["adm"])
    # Sebelum unit ini: 200 (NSFP disimpan tanpa pemeriksaan kembar).
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == (f"Nomor seri {NSFP_A_DIGIT} sudah dipakai faktur {f1['number']}. "
                                  "Periksa nomor serinya.")
    so2 = await db.tax_invoices.find_one({"id": SIMPAN["f_so2"]["id"]}, {"_id": 0})
    assert so2.get("nsfp", "") == "" and "nsfp_key" not in so2


async def test_PK40_U4b_jalur_indeks_tanpa_jalan_cepat(klien, db, uji, monkeypatch):
    """Penjamin keunikan = indeks `uq_fkt_nsfp`, bukan pencarian sebelum tulis: jalan cepat dimatikan → tetap 409."""
    from services import tax_invoice_service as svc
    import indexes

    nama = {(it["collection"], it["name"]) for it in indexes.REQUIRED_UNIQUE_INDEXES}
    assert {("tax_invoices", "uq_fkt_active"), ("tax_invoices", "uq_fkt_nsfp"),
            ("tax_invoices_in", "uq_fpm_active"), ("tax_invoices_in", "uq_fpm_nsfp")} <= nama

    async def _tanpa_jalan_cepat(*a, **kw):
        return None
    monkeypatch.setattr(svc, "_pemakai_nsfp", _tanpa_jalan_cepat)
    r = await klien.patch(f"/api/tax-invoices/{SIMPAN['f_so2']['id']}/nsfp", json={"nsfp": NSFP_A},
                          headers=uji["adm"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == (f"Nomor seri {NSFP_A} sudah dipakai faktur {SIMPAN['f1']['number']}. "
                                  "Periksa nomor serinya.")


async def test_PK40_U5_ganti_dengan_nsfp_sama_memindah_kunci(klien, db, uji):
    f1 = SIMPAN["f1"]
    r = await klien.post(f"/api/tax-invoices/{f1['id']}/replace", json={"reason": "ganti alamat", "nsfp": NSFP_A},
                         headers=uji["adm"])
    assert r.status_code == 200, r.text
    f3 = r.json()
    asli = await db.tax_invoices.find_one({"id": f1["id"]}, {"_id": 0})
    ganti = await db.tax_invoices.find_one({"id": f3["id"]}, {"_id": 0})
    assert "nsfp_key" not in asli and "active_key" not in asli
    assert ganti["nsfp_key"] == NSFP_A_DIGIT and ganti["active_key"] == "so:so_pk40_1"
    SIMPAN["f3"] = f3


async def test_PK40_U6b_faktur_masukan_kunci_aktif_dan_nsfp(klien, db, uji):
    """Lapis B untuk pola `tax_invoices_in` (bersamaan = U6 lapis A): kunci terisi saat dicatat, dicabut saat batal."""
    for vb in ("vb_pk40_a", "vb_pk40_b"):
        await db.vendor_bills.insert_one({"id": vb, "bill_number": vb.upper(), "entity_id": ENT, "status": "posted",
                                          "supplier_id": "sup_x", "supplier_name": "Pemasok Uji", "dpp": 1_000_000,
                                          "ppn_amount": 110_000, "grand_total": 1_110_000, "bill_date": _sekarang()})
    r = await klien.post("/api/input-tax-invoices", headers=uji["adm"],
                         json={"vendor_bill_id": "vb_pk40_a", "nsfp": "010.000-26.12345678"})
    assert r.status_code == 200, r.text
    fpm = await db.tax_invoices_in.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert fpm["active_key"] == "vb:vb_pk40_a" and fpm["nsfp_key"] == "0100002612345678"
    r2 = await klien.post("/api/input-tax-invoices", headers=uji["adm"],
                          json={"vendor_bill_id": "vb_pk40_b", "nsfp": "0100002612345678"})
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"] == (f"Nomor seri 0100002612345678 sudah dipakai faktur {fpm['number']}. "
                                   "Periksa nomor serinya.")
    r = await klien.post(f"/api/input-tax-invoices/{fpm['id']}/cancel", json={"reason": "salah catat"},
                         headers=uji["adm"])
    assert r.status_code == 200, r.text
    fpm = await db.tax_invoices_in.find_one({"id": fpm["id"]}, {"_id": 0})
    assert "active_key" not in fpm and "nsfp_key" not in fpm
    r2 = await klien.post("/api/input-tax-invoices", headers=uji["adm"],
                          json={"vendor_bill_id": "vb_pk40_b", "nsfp": "0100002612345678"})
    assert r2.status_code == 200, r2.text


# ── Rekap PPN tanpa potongan, masa WIB, pembanding buku besar ───────────────
async def test_PK40_U7_rekap_6000_faktur_dan_buku_besar(klien, db, uji, monkeypatch):
    # Fixture 6.000 baris: pemeriksaan keunikan mongomock O(n²) dimatikan HANYA selama sisip (data memang unik).
    monkeypatch.setattr(getattr(db.tax_invoices, "_AsyncMongoMockCollection__collection"), "_ensure_uniques",
                        lambda data: None)
    await db.tax_invoices.insert_many([
        {"id": f"fkt_u7_{i:05d}", "number": f"KSC/FKT-U7-{i:05d}", "entity_id": ENT, "status": "normal",
         "replaces_id": None, "replaced_by_id": None, "order_id": f"so_u7_{i:05d}", "active_key": f"so:so_u7_{i:05d}",
         "faktur_date": "2026-10-15T03:00:00+00:00", "dpp": 10_000, "ppn_amount": 1_100, "ppn_rate": 11,
         "net_subtotal": 10_000, "grand_total": 11_100, "is_pkp": True, "customer_name": "Toko Pajak"}
        for i in range(6000)])
    monkeypatch.undo()
    # Jurnal penjualan masa itu: Dr 1-1200 Piutang 6.600.000 / Cr 2-1200 PPN Keluaran 6.600.000.
    await jurnal(ENT, "2026-10-31", [("1-1200", 6_600_000, 0), ("2-1200", 0, 6_600_000)], "PPN Oktober", "pk40_u7")
    # mongomock-motor mengabaikan batas `to_list(n)`; Motor asli memotong. Disamakan selama rekap supaya batas lama
    # (5.000 baris) terlihat di kode lama.
    import mongomock_motor as mm
    asli_to_list = mm.AsyncCursor.to_list

    async def _to_list_seperti_motor(self, length=None, *a, **kw):
        rows = await asli_to_list(self)
        return rows if length is None else rows[:length]
    monkeypatch.setattr(mm.AsyncCursor, "to_list", _to_list_seperti_motor)
    k = (await _rekap(klien, uji["adm"], "2026-10"))["keluaran"]
    monkeypatch.undo()
    # Hitungan tangan: 6.000 × 1.100 = 6.600.000; 6.000 × 10.000 = 60.000.000. Sebelum unit ini 5.000 × 1.100 = 5.500.000.
    assert k["count"] == 6000
    assert k["ppn"] == 6_600_000
    assert k["dpp"] == 60_000_000
    assert k["gl_ppn"] == 6_600_000
    assert k["selisih"] == 0


async def test_PK40_U8_faktur_dini_hari_tanggal_1_masuk_november(klien, db, uji):
    okt = (await _rekap(klien, uji["adm"], "2026-10"))["keluaran"]
    nov = (await _rekap(klien, uji["adm"], "2026-11"))["keluaran"]
    # 2026-10-31 17.30 UTC = 1 November 2026 00.30 WIB → masa 2026-11.
    await db.tax_invoices.insert_one({"id": "fkt_u8", "number": "KSC/FKT-U8", "entity_id": ENT, "status": "normal",
                                      "replaced_by_id": None, "order_id": "so_u8", "active_key": "so:so_u8",
                                      "faktur_date": "2026-10-31T17:30:00+00:00", "dpp": 10_000, "ppn_amount": 1_100})
    okt2 = (await _rekap(klien, uji["adm"], "2026-10"))["keluaran"]
    nov2 = (await _rekap(klien, uji["adm"], "2026-11"))["keluaran"]
    assert (okt2["count"], okt2["ppn"]) == (okt["count"], okt["ppn"])
    assert (nov2["count"], nov2["ppn"]) == (nov["count"] + 1, nov["ppn"] + 1_100)


async def test_PK40_U9_jurnal_ppn_tanpa_faktur_tampil_sebagai_selisih(klien, db, uji):
    # Jurnal manual Dr 1-1100 Kas 1.000 / Cr 2-1200 PPN Keluaran 1.000 tanpa faktur pajak.
    await jurnal(ENT, "2026-10-20", [("1-1100", 1_000, 0), ("2-1200", 0, 1_000)], "PPN tanpa faktur", "pk40_u9")
    j = await _rekap(klien, uji["adm"], "2026-10")
    # Hitungan tangan: buku besar 6.600.000 + 1.000 = 6.601.000; selisih = rekap − buku besar = 6.600.000 − 6.601.000.
    assert j["keluaran"]["gl_ppn"] == 6_601_000
    assert j["keluaran"]["selisih"] == -1_000
    assert j["masukan"]["gl_ppn"] == 0 and j["masukan"]["selisih"] == 0
    assert j["selisih_note"] == ("Selisih berarti ada jurnal PPN tanpa faktur pajak, atau faktur tanpa jurnal, "
                                 "pada masa ini.")


# ── Masa pajak dilaporkan / terkunci ────────────────────────────────────────
PESAN_KUNCI = ("Masa pajak Oktober 2026 {pt} sudah ditandai dilaporkan, jadi {aksi} tidak bisa "
               "dilakukan. Buka dulu masa pajaknya di Pusat Pajak.")


async def _pesan_kunci(db, aksi: str) -> str:
    pt = await db.business_entities.find_one({"id": ENT}, {"_id": 0})
    return PESAN_KUNCI.format(pt=pt["legal_name"], aksi=aksi)


async def test_PK40_U10_masa_terkunci_menolak_aksi_oktober(klien, db, uji):
    h = uji["adm"]
    await db.vendor_bills.insert_one({"id": "vb_pk40_okt", "bill_number": "VB-PK40-OKT", "entity_id": ENT,
                                      "status": "posted", "supplier_id": "sup_x", "supplier_name": "Pemasok Uji",
                                      "dpp": 500_000, "ppn_amount": 55_000, "grand_total": 555_000,
                                      "bill_date": "2026-10-15"})
    # Rekaman PPh 23 Oktober SEBELUM dikunci: DPP 1.000.000 × 2% = 20.000.
    r = await klien.post("/api/tax/pph-records", headers=h, json={"entity_id": ENT, "period": "2026-10", "code": "pph23",
                                                                  "name": "PPh 23", "rate": 2, "dpp": 1_000_000})
    assert r.status_code == 200, r.text
    SIMPAN["pph_okt"] = r.json()["id"]

    r = await klien.post("/api/tax/periods/2026-10/lock", headers=h, json={"entity_id": ENT, "note": "SPT Oktober"})
    assert r.status_code == 200, r.text
    kunci = r.json()
    assert kunci["status"] == "reported" and kunci["entity_id"] == ENT and kunci["period"] == "2026-10"
    # Potret: keluaran 6.600.000 (U7), buku besar 6.601.000 (U7 + U9); masukan 0; PPh 23 20.000 (PPh 21 belum ada).
    assert kunci["snapshot"] == {"keluaran_ppn": 6_600_000, "masukan_ppn": 0, "net_ppn": 6_600_000,
                                 "pph_total": 20_000, "gl_keluaran_ppn": 6_601_000, "gl_masukan_ppn": 0}

    langkah = [
        ("penerbitan faktur", "post", "/api/sales-orders/so_pk40_okt/tax-invoice", {"faktur_date": "2026-10-20"}),
        ("pembatalan faktur", "post", "/api/tax-invoices/fkt_u7_00000/cancel", {"reason": "salah terbit"}),
        ("perekaman PPh", "post", "/api/tax/pph-records",
         {"entity_id": ENT, "period": "2026-10", "code": "pph23", "name": "PPh 23", "rate": 2, "dpp": 500_000}),
        ("pencatatan faktur masukan", "post", "/api/input-tax-invoices",
         {"vendor_bill_id": "vb_pk40_okt", "nsfp": "010.000-26.55550001", "faktur_date": "2026-10-20"}),
        # tambahan di luar tabel U10: ganti & NSFP faktur Oktober, hapus rekaman PPh Oktober
        ("penggantian faktur", "post", "/api/tax-invoices/fkt_u7_00001/replace", {"reason": "koreksi alamat"}),
        ("perubahan nomor seri", "patch", "/api/tax-invoices/fkt_u7_00002/nsfp", {"nsfp": "0100002699990001"}),
    ]
    sebelum = await jumlah("tax_invoices", {})
    for aksi, cara, url, isi in langkah:
        r = await getattr(klien, cara)(url, json=isi, headers=h)
        assert r.status_code == 409, (url, r.text)
        assert r.json()["detail"] == await _pesan_kunci(db, aksi), url
    r = await klien.delete(f"/api/tax/pph-records/{SIMPAN['pph_okt']}", headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == await _pesan_kunci(db, "penghapusan rekaman PPh")
    assert await jumlah("tax_invoices", {}) == sebelum
    assert (await db.tax_invoices.find_one({"id": "fkt_u7_00000"}))["status"] == "normal"
    assert await jumlah("tax_invoices_in", {"vendor_bill_id": "vb_pk40_okt"}) == 0
    assert await jumlah("tax_pph_records", {"entity_id": ENT, "period": "2026-10"}) == 1

    r = await _terbit(klien, h, "so_pk40_nov", faktur_date="2026-11-02")
    assert r.status_code == 200, r.text


async def test_PK40_U11_kunci_hanya_untuk_pt_itu(klien, db, uji):
    r = await _terbit(klien, uji["adm_kanda"], "so_pk40_kanda", faktur_date="2026-10-20")
    assert r.status_code == 200, r.text
    assert r.json()["entity_id"] == "ent_kanda"


async def test_PK40_U12_buka_masa_dengan_alasan(klien, db, uji):
    h = uji["adm"]
    r = await klien.post("/api/tax/periods/2026-10/unlock", headers=h, json={"entity_id": ENT, "reason": ""})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Alasan membuka masa pajak wajib diisi (minimal 5 huruf)."
    r = await klien.post("/api/tax/periods/2026-10/unlock", headers=h,
                         json={"entity_id": ENT, "reason": "pembetulan SPT"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "reopened" and j["reopen_reason"] == "pembetulan SPT"
    assert len(j["history"]) == 1
    assert j["history"][0]["snapshot"]["keluaran_ppn"] == 6_600_000
    r = await _terbit(klien, h, "so_pk40_okt", faktur_date="2026-10-20")
    assert r.status_code == 200, r.text


async def test_PK40_U13_kunci_masa_berjalan_dan_kunci_ganda(klien, db, uji):
    h = uji["adm"]
    from services.book_date import _BULAN
    berjalan = _masa_berjalan()
    nama_bulan = f"{_BULAN[int(berjalan[5:])]} {berjalan[:4]}"
    r = await klien.post(f"/api/tax/periods/{berjalan}/lock", headers=h, json={"entity_id": ENT})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == f"Masa pajak {nama_bulan} belum berakhir, belum bisa ditandai dilaporkan."
    r = await klien.post("/api/tax/periods/2026-10/lock", headers=h, json={"entity_id": ENT})
    assert r.status_code == 200, r.text
    kunci = r.json()
    assert kunci["status"] == "reported" and len(kunci["history"]) == 1
    r = await klien.post("/api/tax/periods/2026-10/lock", headers=h, json={"entity_id": ENT})
    assert r.status_code == 409, r.text
    from services.book_date import tanggal_panjang
    assert r.json()["detail"] == (f"Masa pajak Oktober 2026 sudah ditandai dilaporkan oleh {kunci['reported_by']} "
                                  f"pada {tanggal_panjang(kunci['reported_at'])}.")
    assert await jumlah("tax_period_locks", {"entity_id": ENT, "period": "2026-10"}) == 1
    r = await klien.get("/api/tax/periods", params={"entity_id": ENT}, headers=h)
    assert r.status_code == 200, r.text
    okt = next(p for p in r.json() if p["period"] == "2026-10")
    assert okt["locked"] is True and okt["reported_by"] == kunci["reported_by"]
    assert next(p for p in r.json() if p["period"] == berjalan)["locked"] is False


# ── PPh 21 (FY-16) ──────────────────────────────────────────────────────────
def _butir_pph21(j: dict) -> dict:
    return next(it for it in j["pph"]["items"] if it["basis"] == "payroll")


async def test_PK40_U14_dasar_pph21_bruto_kena_pajak_dan_buku_besar(klien, db, uji):
    from services import gl_service as gl
    run = {"id": "prun_pk40_ksc", "number": "PAY-PK40-KSC", "entity_id": ENT, "period": "2026-10", "status": "posted",
           "totals": {"gross": 10_000_000, "pph21": 150_000}, "commission_mode": "accrue_then_settle"}
    slip = {"id": "slip_pk40_ksc", "run_id": run["id"], "entity_id": ENT, "period": "2026-10", "status": "posted",
            "salary_earnings": 10_000_000, "gross": 10_000_000, "tax_gross": 10_300_000, "pph21": 150_000,
            "bpjs_er_total": 300_000, "bpjs_emp_total": 200_000, "net": 9_650_000, "commission": 0}
    await db.hr_payroll_runs.insert_one(dict(run))
    await db.hr_payslips.insert_one(dict(slip))
    # Jurnal gaji (hitungan tangan): Dr 6-1000 10.000.000 + Dr 6-1100 300.000 = 10.300.000
    #   = Cr 2-1600 9.650.000 + Cr 2-1700 (200.000 + 300.000) 500.000 + Cr 2-1800 150.000.
    je = await gl.post_payroll_run(run, [slip])
    # PK-22 (FY-06) — kunci jurnal gaji = id proses (dulu "{PT}:{periode}"); rekap pajak mencari lewat kunci yang sama.
    assert je and je["source_id"] == run["id"]
    r = await klien.get("/api/tax/summary", params={"period": "2026-10", "entity_id": ENT}, headers=uji["adm"])
    assert r.status_code == 200, r.text
    b = _butir_pph21(r.json())
    # Sebelum unit ini: dpp 10.000.000 (`totals.gross`), tanpa `gl_amount`.
    assert b["dpp"] == 10_300_000
    assert b["amount"] == 150_000
    assert b["gl_amount"] == 150_000
    assert b["selisih"] == 0
    assert b["count"] == 1
    assert b["source"] == "1 penggajian terjurnal · dasar = penghasilan bruto kena pajak slip"


async def test_PK40_U15_penggajian_belum_terjurnal_tidak_dihitung(klien, db, uji):
    await db.hr_payroll_runs.insert_one({"id": "prun_pk40_kanda", "number": "PAY-PK40-KANDA", "entity_id": "ent_kanda",
                                         "period": "2026-10", "status": "approved",
                                         "totals": {"gross": 5_000_000, "pph21": 80_000}})
    await db.hr_payslips.insert_one({"id": "slip_pk40_kanda", "run_id": "prun_pk40_kanda", "entity_id": "ent_kanda",
                                     "period": "2026-10", "gross": 5_000_000, "tax_gross": 5_150_000, "pph21": 80_000})
    r = await klien.get("/api/tax/summary", params={"period": "2026-10", "entity_id": "ent_kanda"},
                        headers=uji["adm_kanda"])
    assert r.status_code == 200, r.text
    b = _butir_pph21(r.json())
    # Sebelum unit ini: 80.000 (status `approved` ikut dihitung).
    assert b["amount"] == 0
    assert b["count"] == 0


async def test_PK40_U16_izin_baca_dan_kunci(klien, db, uji, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"accounting": ["view"]}, label="Pajak Baca Saja")
    h = await sesi(await akun(rid))
    r = await klien.get("/api/tax/periods", params={"entity_id": ENT}, headers=h)
    assert r.status_code == 200, r.text
    r = await klien.post("/api/tax/periods/2026-09/lock", headers=h, json={"entity_id": ENT})
    assert r.status_code == 403, r.text
    assert await jumlah("tax_period_locks", {"period": "2026-09"}) == 0


# ── Faktur internal antar-PT (jalur ganti/batalnya ikut kunci) ──────────────
async def _pasangan(db, pair: str, tanggal: str) -> None:
    dasar = {"pair_id": pair, "seller_entity_id": ENT, "buyer_entity_id": "ent_kanda", "status": "invoiced",
             "tax_apply": True, "tax_rate": 11, "tax_amount": 110_000, "subtotal": 1_000_000,
             "invoiced_at": tanggal, "items": [{"product_name": "Kain", "quantity": 10, "unit_price": 100_000}],
             "seller_entity_name": "PT Kain Suka Cita", "buyer_entity_name": "CV Kanda Suka"}
    await db.interco_transactions.insert_many([
        {**dasar, "id": f"{pair}_s", "number": f"{pair.upper()}-S", "role": "seller", "entity_id": ENT},
        {**dasar, "id": f"{pair}_b", "number": f"{pair.upper()}-B", "role": "buyer", "entity_id": "ent_kanda"}])


async def test_PK40_antar_pt_kunci_aktif_ganti_dan_batal(klien, db, uji):
    from services import interco_tax_service as ictax
    await _pasangan(db, "icp_pk40", "2026-11-03")
    res = await ictax.issue("icp_pk40", actor="uji", nsfp="010.000-26.77770001")
    out1, in1 = res["out"], res["in"]
    assert (await db.tax_invoices.find_one({"id": out1["id"]}))["active_key"] == "ic:icp_pk40"
    assert (await db.tax_invoices_in.find_one({"id": in1["id"]}))["active_key"] == "ic:icp_pk40"
    with pytest.raises(ictax.IntercoTaxError):
        await ictax.issue("icp_pk40", actor="uji")
    res2 = await ictax.replace("icp_pk40", "angka sesudah retur", actor="uji")
    lama_out = await db.tax_invoices.find_one({"id": out1["id"]}, {"_id": 0})
    lama_in = await db.tax_invoices_in.find_one({"id": in1["id"]}, {"_id": 0})
    assert lama_out["replaced_by_id"] == res2["out"]["id"]
    assert "active_key" not in lama_out and "nsfp_key" not in lama_out
    assert "active_key" not in lama_in and lama_in["status"] == "cancelled"
    baru_out = await db.tax_invoices.find_one({"id": res2["out"]["id"]}, {"_id": 0})
    assert baru_out["active_key"] == "ic:icp_pk40" and baru_out["nsfp_key"] == "0100002677770001"
    await ictax.cancel("icp_pk40", "transaksi dibatalkan", actor="uji")
    assert await jumlah("tax_invoices", {"active_key": "ic:icp_pk40"}) == 0
    assert await jumlah("tax_invoices_in", {"active_key": "ic:icp_pk40"}) == 0


async def test_PK40_antar_pt_masa_terkunci(klien, db, uji):
    from fastapi import HTTPException
    from services import interco_tax_service as ictax
    await _pasangan(db, "icp_pk40_okt", "2026-10-10")
    # Masa Oktober `ent_ksc` terkunci (U13) → penerbitan faktur internal bertanggal Oktober ditolak di sisi penjual.
    with pytest.raises(HTTPException) as e:
        await ictax.issue("icp_pk40_okt", actor="uji")
    assert e.value.status_code == 409
    assert e.value.detail == await _pesan_kunci(db, "penerbitan faktur")
    assert await jumlah("tax_invoices", {"interco_pair_id": "icp_pk40_okt"}) == 0
    assert await jumlah("tax_invoices_in", {"interco_pair_id": "icp_pk40_okt"}) == 0


# ── Skrip data lama `scripts/blueprint/pk40_kunci_faktur.py` (database tiruan; data nyata = H3) ─────────────
async def test_PK40_skrip_kunci_faktur_lama_baca_saja_dan_terapkan(klien, db, uji, capsys):
    import importlib.util
    from pathlib import Path
    jalur = Path(__file__).resolve().parents[2] / "scripts" / "blueprint" / "pk40_kunci_faktur.py"
    spec = importlib.util.spec_from_file_location("pk40_kunci_faktur", jalur)
    skrip = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(skrip)
    dasar = {"entity_id": ENT, "faktur_date": "2026-09-10", "dpp": 1_000, "ppn_amount": 110, "replaced_by_id": None}
    await db.tax_invoices.insert_many([
        {**dasar, "id": "fkt_lama_1", "number": "KSC/FKT-L1", "status": "normal", "order_id": "so_lama_a",
         "nsfp": "010.000-26.88880001"},
        {**dasar, "id": "fkt_lama_2", "number": "KSC/FKT-L2", "status": "normal", "order_id": "so_lama_a"},
        {**dasar, "id": "fkt_lama_3", "number": "KSC/FKT-L3", "status": "batal", "order_id": "so_lama_b",
         "active_key": "so:so_lama_b"}])
    await db.tax_invoices_in.insert_one({"id": "fpm_lama_1", "number": "FPM-L1", "entity_id": ENT,
                                         "status": "recorded", "vendor_bill_id": "vb_lama", "nsfp": "010.000-26.88880002",
                                         "nsfp_digits": "0100002688880002", "faktur_date": "2026-09-10"})
    # Baca-saja: dua faktur aktif untuk satu pesanan = kembar (H6) → keluar 1, tidak menulis apa pun.
    assert await skrip.jalankan([], db=db) == 1
    keluar = capsys.readouterr().out
    assert "KEMBAR active_key=so:so_lama_a: KSC/FKT-L1, KSC/FKT-L2" in keluar
    assert await skrip.jalankan(["--terapkan"], db=db) == 1
    assert "active_key" not in await db.tax_invoices.find_one({"id": "fkt_lama_1"}, {"_id": 0})
    # Pemilik data membereskan kembarnya (di sini: fixture) → --terapkan mengisi/mencabut field kunci.
    await db.tax_invoices.update_one({"id": "fkt_lama_2"}, {"$set": {"status": "batal"}})
    capsys.readouterr()
    assert await skrip.jalankan(["--terapkan"], db=db) == 0
    assert "Selesai: 3 faktur diubah." in capsys.readouterr().out
    l1 = await db.tax_invoices.find_one({"id": "fkt_lama_1"}, {"_id": 0})
    assert (l1["active_key"], l1["nsfp_key"]) == ("so:so_lama_a", "0100002688880001")
    assert "active_key" not in await db.tax_invoices.find_one({"id": "fkt_lama_3"}, {"_id": 0})
    m1 = await db.tax_invoices_in.find_one({"id": "fpm_lama_1"}, {"_id": 0})
    assert (m1["active_key"], m1["nsfp_key"]) == ("vb:vb_lama", "0100002688880002")
    assert await skrip.jalankan([], db=db) == 0   # aman diulang: tidak ada lagi yang perlu diubah
    assert "tax_invoices: 0 faktur perlu diisi" in capsys.readouterr().out


async def test_PK40_invarian_kunci_faktur(klien, db, uji, capsys):
    """`scripts/verify_data_integrity.py` (D2): satu faktur aktif per pemilik + field kunci sesuai keadaan faktur."""
    import importlib
    import re
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    await vdi.layer_tax_invoice_invariants(db)
    keluar = capsys.readouterr().out
    assert re.search(r"PASS.*≤1 faktur aktif/order", keluar), keluar[-2000:]
    assert re.search(r"PASS.*field kunci aktif .* sesuai keadaan faktur", keluar), keluar[-2000:]
    # Kunci tersisa di faktur batal = FAIL (bukan diam-diam).
    await db.tax_invoices.insert_one({"id": "fkt_salah", "number": "KSC/FKT-SALAH", "entity_id": ENT, "status": "batal",
                                      "order_id": "so_x9", "active_key": "so:so_x9", "faktur_date": "2026-09-01"})
    await vdi.layer_tax_invoice_invariants(db)
    keluar = capsys.readouterr().out
    assert re.search(r"FAIL.*field kunci aktif tidak sesuai", keluar) and "KSC/FKT-SALAH" in keluar, keluar[-2000:]
    await db.tax_invoices.delete_one({"id": "fkt_salah"})
