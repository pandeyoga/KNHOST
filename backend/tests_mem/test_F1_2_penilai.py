"""F1 Kwitansi Otomatis dari Mutasi Bank · Tugas 2 — penilai baris mutasi (`bank_auto_receipt_service.nilai_baris`):
cocok sempurna (jalur A/B/C) atau kartu beralasan, tanpa menulis apa pun.

Rancangan `docs/superpowers/specs/2026-11-27-kwitansi-otomatis-mutasi-design.md` §5.1–§5.2, §5.4; ketetapan
pengendali R3 (calon jalur A dicari sebelum nominal harapan: kwitansi terbuka sudah mengurangi sisa tagihan).

Persiapan (ALUR lewat API/layanan kecuali disebut FIXTURE):
  * rekening `ent_ksc`: **A** (BCA, penerimaan pelanggan, transfer bawaan), **B** (Mandiri, penerimaan pelanggan,
    transfer bukan bawaan), **G** (BCA, hanya `gaji`) — `POST /api/bank-accounts`;
  * pelanggan, produk Rp 10.000/m dan Rp 3.468,75/m, gudang, roll 100 m = FIXTURE (pola `test_LB4_putus`);
  * pesanan CBD/DP lewat API → "Periksa & lepas" → `approved` + `pay_hold`; rekening instruksi = A;
  * pesanan tempo/terkonfirmasi tanpa alur jual (sudah lunas, kode baris jadwal) = FIXTURE (pola `test_CRT2_*`);
  * mutasi lewat `bank_recon_service.import_lines` (layanan impor; router impor tidak dipakai supaya kait F1 Tugas 4
    tidak ikut menilai/menautkan).

Hitung tangan (tanpa PPN):
  CBD 100 m × Rp 10.000 = Rp 1.000.000 → wajib sebelum gudang Rp 1.000.000.
  DP50 100 m × Rp 3.468,75 = Rp 346.875 → wajib 50 % = Rp 173.437,5; mutasi Rp 173.438 / Rp 173.437 → selisih 0,5 < 1
  → cocok; Rp 173.436 → selisih 1,5 → "Nominal mutasi Rp 173.436 ≠ tagihan Rp 173.437,5 (kurang Rp 1,5)".
  Jadwal DP50 Rp 2.000.000 terkonfirmasi: baris uang muka Rp 1.000.000 berkode; kwitansi Rp 400.000 → sisa baris
  Rp 600.000 (sisa pesanan Rp 1.600.000) → mutasi Rp 600.000 cocok dengan sisa baris.

    cd /home/user/KNHOST && python -m pytest backend/tests_mem/test_F1_2_penilai.py -n 0 -q -p no:cacheprovider
"""
from __future__ import annotations

import itertools
import uuid

import pytest

from core_utils import now_iso
from pembantu import tutup_periode

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module", autouse=True)
def _unggahan_sementara(tmp_path_factory):
    """Berkas unggahan uji (bila ada) ke folder sementara pytest, bukan `backend/uploads` repo."""
    from services import storage_service
    mp = pytest.MonkeyPatch()
    mp.setattr(storage_service, "STORAGE_DIR", tmp_path_factory.mktemp("unggahan_f12"))
    yield
    mp.undo()


KSC = "ent_ksc"
TGL = "2026-11-24"
KUNCI = "bank.kwitansi_otomatis_mutasi"
TOLERANSI = "payment.variance_tolerance_rupiah"
TANPA_PPN = {"tax_override": "non_ppn", "tax_override_reason": "uji F1-2 tanpa PPN"}
_n = itertools.count(1)


def _id(awal: str) -> str:
    return f"{awal}_f12_{uuid.uuid4().hex[:8]}"


async def _rekening(klien, h, **isi) -> str:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], "holder_name": "PT Kain Suka Cita", "entity_id": KSC, **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    A = await _rekening(klien, kepala_admin, name="BCA Penerimaan F12", account_number="121-212-1212",
                        default_receiving_methods=["transfer"], show_on_documents=True)
    B = await _rekening(klien, kepala_admin, name="Mandiri Penerimaan F12", bank_name="Mandiri",
                        account_number="343-434-3434", default_receiving_methods=[])
    G = await _rekening(klien, kepala_admin, name="BCA Gaji F12", account_number="565-656-5656", purposes=["gaji"])
    cus, adr, prd, prd_dp = _id("cus"), _id("adr"), _id("prd"), _id("prd")
    await db.customers.insert_one({"id": cus, "name": "Toko F1-2", "entity_id": KSC, "status": "active",
                                   "addresses": [{"id": adr, "label": "Utama", "city": "Bandung",
                                                  "address": "Jl. Uji 12", "recipient_name": "Bu Uji",
                                                  "phone": "081200000012"}]})
    for pid, sku, harga in ((prd, "F12-KAIN", 10000), (prd_dp, "F12-KAIN-DP", 3468.75)):
        await db.products.insert_one({"id": pid, "sku": sku, "name": f"Kain {sku}", "price": harga,
                                      "base_unit": "meter", "status": "active", "lifecycle": "produksi",
                                      "category": "uji"})
    await db.warehouses.insert_one({"id": "wh_f12", "name": "Gudang F1-2", "entity_id": KSC, "city": "Bandung"})
    cus_f = _id("cus")   # pelanggan pesanan FIXTURE: tagihan uang mukanya tidak menahan kredit pelanggan alur jual
    await db.customers.insert_one({"id": cus_f, "name": "Toko F1-2 Tempo", "entity_id": KSC, "status": "active"})
    sales = await akun("sales")
    sa = await akun("sales_admin")
    fin = await akun("finance")
    return {"h": kepala_admin, "A": A, "B": B, "G": G, "cus": cus, "cus_f": cus_f, "adr": adr, "prd": prd,
            "prd_dp": prd_dp, "sales": sales, "fin": fin, "h_sa": await sesi(sa)}


def _aktor(u: dict) -> dict:
    return {"id": u["id"], "name": u["name"], "role": u["role"]}


async def _pesan(klien, db, siap, term: str = "CBD", *, prd: str = "", total: float = 1_000_000) -> dict:
    """Pesanan lewat API (tanpa PPN), "Periksa & lepas" → `approved` + `pay_hold` (pola `test_LB4_putus`)."""
    await db.inventory_rolls.insert_one({
        "id": _id("roll"), "roll_no": f"R-F12-{next(_n)}", "product_id": prd or siap["prd"], "owner_entity_id": KSC,
        "warehouse_id": "wh_f12", "status": "available", "active_movement": None, "length_remaining": 100.0,
        "lot": "L-F12", "created_at": now_iso()})
    body = {"customer_id": siap["cus"], "shipping_address_id": siap["adr"], "entity_id": KSC,
            "payment_term_code": term, "payment_method_code": "transfer", "receiving_account_id": siap["A"],
            "items": [{"product_id": prd or siap["prd"], "quantity": 100, "unit": "meter"}], **TANPA_PPN}
    r = await klien.post("/api/sales-orders", headers=siap["h"], json=body)
    assert r.status_code == 200, r.text
    so = r.json()
    assert so["grand_total"] == total, so["grand_total"]
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"sales_id": siap["sales"]["id"]}})   # FIXTURE
    r = await klien.post(f"/api/sales-orders/{so['id']}/review-release", headers=siap["h"], json={"note": "uji"})
    assert r.status_code == 200, r.text
    cur = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert cur["status"] == "approved" and cur["pay_hold"], cur.get("status")
    return cur


async def _pesan_dp_pecahan(klien, db, siap) -> dict:
    return await _pesan(klien, db, siap, "DP50", prd=siap["prd_dp"], total=346_875)


async def _pesanan_fixture(db, siap, total: float, *, term: str = "NET30", status: str = "confirmed",
                           bayar: float = 0.0, kode: bool = True) -> dict:
    """FIXTURE: pesanan tanpa alur jual (pola `test_CRT2_jadwal_saldo._pesanan`) + kode bayar tingkat pesanan."""
    i = next(_n)
    so = {"id": _id("so"), "number": f"SO-F12-{i}", "entity_id": KSC, "customer_id": siap["cus_f"],
          "customer_name": "Toko F1-2 Tempo", "status": status, "grand_total": float(total),
          "total_amount": float(total), "ppn_amount": 0.0, "items": [], "payment_term_code": term,
          "created_at": "2026-11-03T03:00:00+00:00", "confirmed_at": "2026-11-03T03:00:00+00:00",
          "payment_method_code": "transfer",
          "receiving_account_id": "", "receiving_account": {},
          "payments": ([{"id": _id("pay"), "amount": float(bayar), "date": "2026-11-05", "method": "transfer"}]
                       if bayar else []),
          "paid_total": float(bayar), "payment_status": "paid" if bayar >= total else "unpaid"}
    await db.sales_orders.insert_one(dict(so))
    if kode:
        from services.payment_code_service import _acak
        so["kode"] = f"KN-{_acak()}"
        await db.payment_codes.insert_one({
            "id": _id("pyc"), "code": so["kode"], "entity_id": KSC, "order_id": so["id"], "order_number": so["number"],
            "customer_id": siap["cus_f"], "plan_id": "", "line_id": "", "order_level": True, "percent": 100.0,
            "amount": float(total), "due_date": "", "status": "aktif", "created_at": now_iso(),
            "updated_at": now_iso()})
    return so


async def _kode(db, oid: str) -> str:
    return (await db.payment_codes.find_one({"order_id": oid}, {"_id": 0}, sort=[("created_at", 1)]))["code"]


async def _impor(db, rek: str, nominal: float, berita: str, *, ref: str = "", tgl: str = TGL,
                 arah: str = "in") -> dict:
    from services import bank_recon_service as brs
    eid = _id("ext")
    res = await brs.import_lines(rek, "", [{"stmt_date": tgl, "amount": nominal, "direction": arah,
                                            "description": berita, "ref": ref, "external_id": eid}], "uji F1-2")
    assert res["imported"] == 1, res
    return await db.bank_statement_lines.find_one({"external_id": eid}, {"_id": 0})


async def _kwitansi(siap, so: dict, amount: float, *, rek: str = "", **lain) -> dict:
    """Kwitansi Finance (pemegang `payment_report.decide`) lewat satu pintu kas — belum terverifikasi bank."""
    from services import ar_receipt_service as ars
    return await ars.create_receipt({
        "customer_id": so["customer_id"], "amount": amount, "method": "transfer", "entity_id": KSC,
        "account_id": rek or siap["A"], "receipt_date": TGL, "reference_no": f"TRF-F12-{next(_n)}",
        "allocations": [{"order_id": so["id"], "amount": amount}], **lain}, _aktor(siap["fin"]))


async def _lapor(klien, siap, oid: str, amount: float = 1_000_000, *, rek: str = "", **lain) -> dict:
    r = await klien.post(f"/api/sales-orders/{oid}/payment-reports", headers=siap["h_sa"], json={
        "amount": amount, "transfer_date": TGL, "account_id": rek or siap["A"], "method": "transfer",
        "reference_no": f"TRF-LB-F12-{next(_n)}", "note": "uji F1-2", **lain})
    assert r.status_code == 200, r.text
    return r.json()


async def _nilai(line: dict) -> dict:
    from services.bank_auto_receipt_service import nilai_baris
    return await nilai_baris(line)


def _kartu(hasil: dict, kode: str) -> str:
    """Kontrak (R5-M7): setiap kode kartu yang dikembalikan penilai ada di `KODE_KARTU` (string tetap untuk layar)."""
    from services.bank_auto_receipt_service import KODE_KARTU
    assert (hasil["keputusan"], hasil["alasan_kode"]) == ("kartu", kode), hasil
    assert hasil["alasan_kode"] in KODE_KARTU, hasil
    return hasil["alasan"]


async def _setel(klien, h, key, value):
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": key, "value": value, "scope_type": "entity", "scope_id": KSC, "reason": "uji F1-2",
        "effective_from": ""}]})
    assert r.status_code == 200, r.text


# ── Jalur C — kwitansi baru ──────────────────────────────────────────────────────────────────────────────────────────
async def test_cbd_tertahan_nominal_tepat_C(klien, db, siap):
    so = await _pesan(klien, db, siap)
    ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} TOKO F12")
    h = await _nilai(ln)
    assert (h["keputusan"], h["harapan"], h["order"]["id"]) == ("C", 1_000_000, so["id"]), h
    assert h["receipt"] is None and h["report"] is None
    assert so["number"] in h["alasan"]


async def test_dp50_pecahan_dua_arah_C(klien, db, siap):
    so = await _pesan_dp_pecahan(klien, db, siap)
    kode = await _kode(db, so["id"])
    for nominal in (173_438, 173_437):
        h = await _nilai(await _impor(db, siap["A"], nominal, f"TRSF {kode} DP"))
        assert (h["keputusan"], h["harapan"]) == ("C", 173_437.5), (nominal, h)
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 173_436, f"TRSF {kode} DP")), "nominal_beda")
    assert alasan == "Nominal mutasi Rp 173.436 ≠ tagihan Rp 173.437,5 (kurang Rp 1,5)"


async def test_kode_baris_cicilan_C(klien, db, siap):
    from services import billing_schedule_service as bss
    so = await _pesanan_fixture(db, siap, 2_000_000, term="DP50", kode=False)
    plan = await bss.on_order_confirmed(so["id"])
    plan = await db.payment_plans.find_one({"id": plan["id"]}, {"_id": 0})   # `pay_code` ditulis sesudah jadwal lahir
    [dp] = [x for x in plan["lines"] if x["kind"] == "dp"]
    assert dp["amount"] == 1_000_000 and dp["pay_code"]
    await _kwitansi(siap, so, 400_000)                       # baris uang muka dibayar sebagian → sisa baris 600.000
    h = await _nilai(await _impor(db, siap["A"], 600_000, f"TRSF {dp['pay_code']} CICIL"))
    assert (h["keputusan"], h["harapan"], h["order"]["id"]) == ("C", 600_000, so["id"]), h


# ── Jalur A — kwitansi yang sudah ada (calon dicari sebelum nominal harapan, R3) ─────────────────────────────────────
async def test_kwitansi_terbuka_sama_A(klien, db, siap):
    from services.payment_report_service import sisa_tagihan
    so = await _pesan(klien, db, siap)
    kw = await _kwitansi(siap, so, 1_000_000)                # Finance mencatat dulu → sisa tagihan pesanan 0
    assert sisa_tagihan(await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})) == 0
    h = await _nilai(await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}"))
    assert (h["keputusan"], h["receipt"]["id"], h["harapan"]) == ("A", kw["id"], 1_000_000), h
    assert h["report"] is None and kw["number"] in h["alasan"]


async def test_kwitansi_terbuka_sebagian_A_bukan_C(klien, db, siap):
    so = await _pesanan_fixture(db, siap, 1_000_000)
    kw = await _kwitansi(siap, so, 500_000)                  # sisa 500.000 = nominal kwitansi: tetap A, bukan C
    h = await _nilai(await _impor(db, siap["A"], 500_000, f"TRSF {so['kode']}"))
    assert (h["keputusan"], h["receipt"]["id"]) == ("A", kw["id"]), h


async def test_kwitansi_pecahan_nominal_beda(klien, db, siap):
    so = await _pesan_dp_pecahan(klien, db, siap)
    kw = await _kwitansi(siap, so, 173_437.5)                # sisa pesanan 173.437,5 → tanpa aturan R3 menjadi C ganda
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 173_438, f"TRSF {await _kode(db, so['id'])}")),
                    "nominal_beda")
    assert alasan == f"Kwitansi {kw['number']} Rp 173.437,5 berbeda Rp 0,5 dari mutasi Rp 173.438"


async def test_kas_lama_tanpa_rekening_di_rekening_tunggal_A(klien, db, siap):
    """R5-M1 — kas kwitansi lama tanpa `account_id` termasuk buku rekening mutasi bila rekening itu satu-satunya
    rekening aktif PT untuk jenis kasnya (`bank_recon_service._book_query`, `bank_service.sole_account_id`): calon
    jalur A, bukan `rekening_beda`. PT berekening ganda: kas tanpa rekening bukan milik buku rekening mana pun →
    `rekening_beda`."""
    so = await _pesanan_fixture(db, siap, 1_000_000)
    kw = await _kwitansi(siap, so, 1_000_000)
    await db.cash_transactions.update_one({"id": kw["cash_txn_id"]}, {"$set": {"account_id": ""}})   # FIXTURE: kas lama
    ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {so['kode']}")
    _kartu(await _nilai(ln), "rekening_beda")                  # rekening kas besar PT ini lebih dari satu
    lain = [a["id"] async for a in db.bank_accounts.find(
        {"entity_id": KSC, "id": {"$ne": siap["A"]}, "is_active": {"$ne": False}}, {"_id": 0, "id": 1})]
    await db.bank_accounts.update_many({"id": {"$in": lain}}, {"$set": {"is_active": False}})   # FIXTURE
    try:
        h = await _nilai(ln)
    finally:
        await db.bank_accounts.update_many({"id": {"$in": lain}}, {"$set": {"is_active": True}})
    assert (h["keputusan"], h["receipt"]["id"]) == ("A", kw["id"]), h


async def test_kwitansi_sama_rekening_lain_kartu(klien, db, siap):
    so = await _pesan(klien, db, siap)
    kw = await _kwitansi(siap, so, 1_000_000, rek=siap["B"], mismatch_note="pelanggan transfer ke Mandiri")
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")),
                    "rekening_beda")
    assert kw["number"] in alasan and "Mandiri Penerimaan F12" in alasan and "BCA Penerimaan F12" in alasan


# ── Jalur B — laporan bayar menunggu ─────────────────────────────────────────────────────────────────────────────────
async def test_laporan_menunggu_sama_B(klien, db, siap):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])                # tanpa lampiran: mutasi bank yang menjadi buktinya
    assert rep["attachment_count"] == 0
    h = await _nilai(await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}"))
    assert (h["keputusan"], h["report"]["id"], h["harapan"]) == ("B", rep["id"], 1_000_000), h
    assert h["receipt"] is None and rep["number"] in h["alasan"]


async def test_laporan_beda_kartu(klien, db, siap):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"], 600_000)
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")),
                    "laporan_beda")
    assert rep["number"] in alasan and "Rp 600.000" in alasan
    # rekening laporan ≠ rekening mutasi → juga laporan_beda
    so2 = await _pesan(klien, db, siap)
    rep2 = await _lapor(klien, siap, so2["id"], rek=siap["B"], mismatch_note="pelanggan transfer ke Mandiri")
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so2['id'])}")),
                    "laporan_beda")
    assert rep2["number"] in alasan and "Mandiri Penerimaan F12" in alasan


async def test_laporan_memproses_kartu(klien, db, siap):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    await db.payment_reports.update_one({"id": rep["id"]}, {"$set": {   # FIXTURE: Terima sedang berjalan
        "status": "memproses", "claim": {"token": "klaim_uji", "by": "", "by_name": "Uji", "at": now_iso()}}})
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")),
                    "laporan_diproses")
    assert rep["number"] in alasan


async def test_laporan_dan_kwitansi_kartu(klien, db, siap):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    kw = await _kwitansi(siap, so, 1_000_000)                # Finance mencatat langsung, laporan masih menunggu
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")),
                    "laporan_dan_kwitansi")
    assert alasan == f"Kwitansi {kw['number']} dan laporan {rep['number']} sama-sama menunggu — putuskan"


# ── Kartu lain ───────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_dua_kode_kartu(klien, db, siap):
    s1 = await _pesanan_fixture(db, siap, 700_000)
    s2 = await _pesanan_fixture(db, siap, 700_000)
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 700_000, f"TRSF {s1['kode']} {s2['kode']}")),
                    "kode_ganda")
    assert alasan == f"Dua kode bayar di berita transfer: {s1['kode']}, {s2['kode']}"


async def test_pesanan_batal_kartu(klien, db, siap):
    so = await _pesan(klien, db, siap)
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "cancelled"}})   # FIXTURE
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")),
                    "pesanan_mati")
    assert so["number"] in alasan


async def test_sudah_lunas_kartu(klien, db, siap):
    so = await _pesanan_fixture(db, siap, 800_000, bayar=800_000)
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 800_000, f"TRSF {so['kode']}")), "sudah_lunas")
    assert alasan == f"Pesanan {so['number']} sudah lunas"


async def test_sudah_lunas_oleh_kwitansi_terbuka_disebut(klien, db, siap):
    """R5-M2 — sisa < Rp 1 karena kwitansi yang belum cocok mutasi (nominalnya ≠ mutasi): alasannya menyebut kwitansi
    itu, supaya Finance tahu uangnya mungkin sama."""
    so = await _pesanan_fixture(db, siap, 1_000_000)
    k1 = await _kwitansi(siap, so, 600_000)
    k2 = await _kwitansi(siap, so, 400_000)
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 1_000_000, f"TRSF {so['kode']}")), "sudah_lunas")
    assert alasan == (f"Pesanan {so['number']} sudah lunas oleh kwitansi {k1['number']}, {k2['number']} yang belum "
                      "cocok mutasi")


async def test_rekening_beda_instruksi_kartu(klien, db, siap):
    so = await _pesan(klien, db, siap)                       # rekening instruksi = BCA Penerimaan F12
    alasan = _kartu(await _nilai(await _impor(db, siap["B"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")),
                    "rekening_beda")
    assert alasan == "Rekening mutasi Mandiri Penerimaan F12 ≠ rekening instruksi pesanan BCA Penerimaan F12"


async def test_rekening_tolak_cara_kartu(klien, db, siap):
    so = await _pesanan_fixture(db, siap, 900_000)
    alasan = _kartu(await _nilai(await _impor(db, siap["G"], 900_000, f"TRSF {so['kode']}")), "rekening_tolak_cara")
    assert "tidak bisa menerima pembayaran pelanggan" in alasan


async def test_periode_tutup_kartu(klien, db, siap):
    so = await _pesan(klien, db, siap)
    await tutup_periode(KSC, "2026-10")
    alasan = _kartu(await _nilai(await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}",
                                              tgl="2026-10-15")), "periode_tutup")
    assert alasan == "Periode Oktober 2026 sudah ditutup"   # R5-M8 — kalimat pendek, nama bulan Indonesia


async def test_selisih_perlu_putusan_kartu(klien, db, siap):
    so = await _pesan_dp_pecahan(klien, db, siap)
    await _setel(klien, siap["h"], TOLERANSI, 0)             # selisih pembulatan Rp 0,5 kini butuh putusan
    try:
        alasan = _kartu(await _nilai(await _impor(db, siap["A"], 173_438, f"TRSF {await _kode(db, so['id'])}")),
                        "selisih_perlu_putusan")
    finally:
        await _setel(klien, siap["h"], TOLERANSI, 5000)
    assert "Rp 0,5" in alasan and "lebih" in alasan.lower()


async def test_baris_pt_all_kartu(klien, db, siap):
    so = await _pesan(klien, db, siap)
    ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    _kartu(await _nilai({**ln, "entity_id": "all"}), "pt_tidak_jelas")


async def test_pengaturan_mati_kartu_otomatis_mati(klien, db, siap):
    so = await _pesan(klien, db, siap)
    ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    await _setel(klien, siap["h"], KUNCI, False)
    try:
        h = await _nilai(ln)
    finally:
        await _setel(klien, siap["h"], KUNCI, True)
    alasan = _kartu(h, "otomatis_mati")
    assert alasan.startswith("Kwitansi otomatis mati untuk PT ini — mutasi ini cocok sempurna dengan ")
    assert so["number"] in alasan and (h["order"]["id"], h["harapan"]) == (so["id"], 1_000_000)
    assert (await _nilai(ln))["keputusan"] == "C"            # pengaturan dipulihkan → jalur C lagi


# ── Lewati (bukan urusan F1) ─────────────────────────────────────────────────────────────────────────────────────────
async def test_lewati(klien, db, siap):
    so = await _pesan(klien, db, siap)
    kode = await _kode(db, so["id"])
    ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {kode}")
    assert (await _nilai(ln))["keputusan"] == "C"
    kasus = {   # R5-M7 — kode lewati yang tepat per kasus
        "bukan_masuk": await _impor(db, siap["A"], 1_000_000, f"TRSF {kode}", arah="out"),
        "tanpa_kode": await _impor(db, siap["A"], 1_000_000, "TRSF TOKO TANPA KODE"),
        "sebelum_aktif": {**ln, "created_at": "2000-01-01T00:00:00+00:00"},
        "pernah_otomatis": {**ln, "f1": {"status": "kartu", "pernah_otomatis": True}},
        "dibatalkan": {**ln, "f1": {"status": "dibatalkan"}},
        "bukan_unmatched": {**ln, "status": "matched"},
    }
    for kode_lewati, baris in kasus.items():
        h = await _nilai(baris)
        assert (h["keputusan"], h["alasan_kode"]) == ("lewati", kode_lewati), (kode_lewati, h)
        assert h["alasan"], (kode_lewati, h)


def test_kode_kartu_tetap_dan_unik():
    """R5-M7 — daftar kode kartu tetap (dipakai layar), tanpa kembar; `galat` milik pelaksana ikut terdaftar."""
    from services.bank_auto_receipt_service import KODE_COCOK, KODE_KARTU
    assert len(KODE_KARTU) == len(set(KODE_KARTU)) and "galat" in KODE_KARTU and KODE_COCOK not in KODE_KARTU
    assert "kemungkinan_ganda" in KODE_KARTU   # R11 (I5)


# ── R11 (I5) — impor ganda yang lolos dedupe ─────────────────────────────────────────────────────────────────────────
async def test_mutasi_serupa_tertaut_manual_kemungkinan_ganda(klien, db, siap):
    """Baris lain di rekening sama, tanggal & nominal & kode sama, sudah tertaut (pencocokan manual biasa, tanpa penanda
    F1) ke kas kwitansi pesanan kode itu → kartu `kemungkinan_ganda` yang menyebut kwitansinya — sebelum calon jalur A
    dan sebelum harapan. Tanggal lain, rekening lain, atau kwitansinya sudah batal → bukan kartu ini."""
    from services import ar_receipt_service as ars
    from services import bank_recon_service as brs
    so = await _pesanan_fixture(db, siap, 1_000_000)
    kw = await _kwitansi(siap, so, 500_000)
    asli = await _impor(db, siap["A"], 500_000, f"TRSF {so['kode']} TOKO")
    await brs.manual_match(asli["id"], kw["cash_txn_id"], "Uji F1-2", [KSC])
    assert (await db.bank_statement_lines.find_one({"id": asli["id"]}, {"_id": 0}))["status"] == "matched"
    kembar = await _impor(db, siap["A"], 500_000, f"TRSF  {so['kode']}  TOKO")   # spasi lain: lolos dedupe impor
    alasan = _kartu(await _nilai(kembar), "kemungkinan_ganda")
    assert alasan == (f"Mutasi serupa 24 November 2026 Rp 500.000 sudah dicatat sebagai kwitansi {kw['number']} — "
                      "periksa apakah impor ganda")
    assert (await _nilai(await _impor(db, siap["A"], 500_000, f"TRSF {so['kode']} LAIN", tgl="2026-11-25"))
            )["alasan_kode"] != "kemungkinan_ganda"
    assert (await _nilai(await _impor(db, siap["B"], 500_000, f"TRSF {so['kode']} REK B"))
            )["alasan_kode"] != "kemungkinan_ganda"
    await brs.unmatch(asli["id"], "Uji F1-2", [KSC])
    await ars.void_receipt(kw["id"], _aktor(siap["fin"]), reason="uji F1-2 batal")
    assert (await _nilai(kembar))["alasan_kode"] != "kemungkinan_ganda"


async def test_mutasi_serupa_berpenanda_f1_kemungkinan_ganda(klien, db, siap):
    """Baris lain berpenanda `f1.status` otomatis/manual dengan kwitansi hidup → kartu; kwitansinya batal → bukan."""
    so = await _pesanan_fixture(db, siap, 1_000_000)
    kw = await _kwitansi(siap, so, 400_000)
    for status in ("otomatis", "manual"):
        asli = await _impor(db, siap["A"], 400_000, f"TRSF {so['kode']} {status.upper()}")
        await db.bank_statement_lines.update_one({"id": asli["id"]}, {"$set": {   # FIXTURE — penanda F1 baris lain
            "f1": {"status": status, "receipt_id": kw["id"], "order_id": so["id"]}}})
        kembar = await _impor(db, siap["A"], 400_000, f"TRSF {so['kode']} {status.upper()} ULANG")
        assert kw["number"] in _kartu(await _nilai(kembar), "kemungkinan_ganda")
        await db.bank_statement_lines.update_one({"id": asli["id"]}, {"$set": {"f1.receipt_id": "arc_tidak_ada"}})
        assert (await _nilai(kembar))["alasan_kode"] != "kemungkinan_ganda"


# ── Tanpa tulisan ────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_penilai_tidak_menulis(klien, db, siap):
    c = await _pesan(klien, db, siap)
    a = await _pesan(klien, db, siap)
    await _kwitansi(siap, a, 1_000_000)
    b = await _pesan(klien, db, siap)
    await _lapor(klien, siap, b["id"])
    baris = [await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}") for so in (c, a, b)]
    baris.append(await _impor(db, siap["B"], 1_000_000, f"TRSF {await _kode(db, c['id'])}"))

    async def potret() -> dict:
        out = {n: await db[n].count_documents({}) for n in sorted(await db.list_collection_names())}
        for n in ("bank_statement_lines", "sales_orders", "ar_receipts", "payment_reports", "cash_transactions"):
            out[f"isi:{n}"] = sorted((await db[n].find({}, {"_id": 0}).to_list(5000)), key=lambda d: d.get("id", ""))
        return out

    sebelum = await potret()
    hasil = [(await _nilai(ln))["keputusan"] for ln in baris]
    assert hasil == ["C", "A", "B", "kartu"]
    sesudah = await potret()
    for kunci in ("ar_receipts", "cash_transactions", "bank_statement_lines"):
        assert sesudah[kunci] == sebelum[kunci], kunci
    assert sesudah == sebelum
