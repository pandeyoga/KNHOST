"""F1 Kwitansi Otomatis dari Mutasi Bank · Tugas 4 — endpoint: kait impor & "Cocokkan otomatis", kwitansi dari mutasi
(manual, atomik), batal kwitansi mutasi; plus ketetapan R7 (Minor T3: M1, M2, M3, M5).

Rancangan `docs/superpowers/specs/2026-11-27-kwitansi-otomatis-mutasi-design.md` §5.1, §5.5, §5.6. Uang tetap lewat
pintu yang ada: kwitansi `ar_receipt_service.create_receipt` / `payment_report_service.terima`, tautan
`bank_recon_service._link`, lepas `bank_recon_service._unlink`, batal `ar_receipt_service.void_receipt`.

Persiapan (ALUR lewat API kecuali disebut FIXTURE):
  * rekening `ent_ksc`: **A** (BCA, penerimaan pelanggan, transfer bawaan), **B** (Mandiri) — `POST /api/bank-accounts`;
    rekening `ent_kanda`: **K** (untuk uji PT lain); rekening tambahan per uji bila hitungan respons harus tepat;
  * pelanggan, produk Rp 10.000/m, gudang, roll 100 m = FIXTURE (pola `test_F1_3_pelaksana`);
  * pesanan CBD lewat API → "Periksa & lepas" → `approved` + `pay_hold`; rekening instruksi = A (atau rekening uji);
  * mutasi lewat rute impor (`/import`, `/import-file`: kait F1 berjalan) atau layanan `import_lines` (tanpa kait —
    baris berkode tetap `unmatched` untuk operasi manual).

Hitung tangan (tanpa PPN): CBD 100 m × Rp 10.000 = Rp 1.000.000 = wajib sebelum gudang. Mutasi Rp 1.000.000 berkode →
kwitansi Rp 1.000.000 (kas = nominal mutasi, rekening & tanggal mutasi) → kas cocok penuh → terverifikasi bank → tahan
dibuka → `confirmed`. Mutasi Rp 1.500.000 → kartu `nominal_beda` (lebih Rp 500.000). Mutasi Rp 600.000 → kartu; Finance
mencatat Rp 400.000 → sisa Rp 600.000 = mutasi → "Cocokkan otomatis" → jalur C.

    cd /home/user/KNHOST && python -m pytest backend/tests_mem/test_F1_4_endpoint.py -n 0 -q -p no:cacheprovider
"""
from __future__ import annotations

import itertools
import uuid

import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core_utils import now_iso

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module", autouse=True)
def _unggahan_sementara(tmp_path_factory):
    """Bukti bayar yang diunggah uji modul ini ditulis ke folder sementara pytest, bukan ke `backend/uploads` repo."""
    from services import storage_service
    mp = pytest.MonkeyPatch()
    mp.setattr(storage_service, "STORAGE_DIR", tmp_path_factory.mktemp("unggahan_f14"))
    yield
    mp.undo()


KSC, KANDA = "ent_ksc", "ent_kanda"
TGL = "2026-11-24"
REC = "/api/bank-reconciliation"
TANPA_PPN = {"tax_override": "non_ppn", "tax_override_reason": "uji F1-4 tanpa PPN"}
PEMICU = "Uji Pengimpor F14"
CSV = "Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo\n{tgl},{ket},0000,\"{nom}\",{arah},0\n"
PESAN_LAPORAN = "Putuskan dulu laporan bayar {nomor}: Terima bila buktinya mutasi ini, Tolak bila bukan."
PESAN_NOMINAL = ("Nominal kwitansi dari mutasi harus sama dengan nominal mutasi Rp 1.000.000 (diisi {badan}). Uang "
                 "yang masuk adalah nominal mutasi; selisih dengan tagihan diputus lewat alokasi dan keputusan "
                 "selisih.")
PESAN_BUKAN_MUTASI = "Kwitansi ini tidak lahir dari mutasi — batalkan lewat Rekonsiliasi dan Kwitansi seperti biasa."
PERINGATAN = ("Pesanan {no} sudah dilepas ke gudang ({status}); membatalkan kwitansi tidak menahan barang — tahan "
              "pesanan atau hubungi Gudang bila perlu.")
_n = itertools.count(1)


def _id(awal: str) -> str:
    return f"{awal}_f14_{uuid.uuid4().hex[:8]}"


async def _rekening(klien, h, **isi) -> str:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], "holder_name": "PT Kain Suka Cita", "entity_id": KSC, **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def _rekening_uji(klien, siap) -> str:
    """Rekening BCA penerimaan baru (PT KSC) — hitungan respons "Cocokkan otomatis" hanya dari baris uji itu."""
    i = next(_n)
    return await _rekening(klien, siap["h"], name=f"BCA Uji F14-{i}", account_number=f"414-{i:03d}-1414")


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    A = await _rekening(klien, kepala_admin, name="BCA Penerimaan F14", account_number="141-414-1414",
                        default_receiving_methods=["transfer"], show_on_documents=True)
    B = await _rekening(klien, kepala_admin, name="Mandiri Penerimaan F14", bank_name="Mandiri",
                        account_number="414-141-4141", default_receiving_methods=[])
    h_kanda = await sesi("admin@kainnusantara.id", entitas=KANDA)
    K = await _rekening(klien, h_kanda, name="BCA Penerimaan Kanda F14", account_number="999-414-0000",
                        holder_name="CV Kanda", default_receiving_methods=["transfer"], entity_id=KANDA)
    cus, adr, prd = _id("cus"), _id("adr"), _id("prd")
    await db.customers.insert_one({"id": cus, "name": "Toko F1-4", "entity_id": KSC, "status": "active",
                                   "phone": "081200000014",
                                   "addresses": [{"id": adr, "label": "Utama", "city": "Bandung",
                                                  "address": "Jl. Uji 14", "recipient_name": "Bu Uji",
                                                  "phone": "081200000014"}]})
    await db.products.insert_one({"id": prd, "sku": "F14-KAIN", "name": "Kain F14-KAIN", "price": 10000,
                                  "base_unit": "meter", "status": "active", "lifecycle": "produksi", "category": "uji"})
    await db.warehouses.insert_one({"id": "wh_f14", "name": "Gudang F1-4", "entity_id": KSC, "city": "Bandung"})
    sales, sa, fin, mgr = await akun("sales"), await akun("sales_admin"), await akun("finance"), await akun("manager")
    return {"h": kepala_admin, "A": A, "B": B, "K": K, "cus": cus, "adr": adr, "prd": prd, "sales": sales,
            "fin": fin, "mgr": mgr, "h_sales": await sesi(sales), "h_sa": await sesi(sa), "h_fin": await sesi(fin),
            "h_mgr": await sesi(mgr)}


async def _so(db, oid: str) -> dict:
    return await db.sales_orders.find_one({"id": oid}, {"_id": 0})


async def _pelanggan(db) -> tuple:
    """FIXTURE: pelanggan baru (tanpa pesanan lain) — rencana alokasi "tertua dulu" hanya melihat pesanan uji itu."""
    cus, adr = _id("cus"), _id("adr")
    await db.customers.insert_one({"id": cus, "name": "Toko F1-4 Sendiri", "entity_id": KSC, "status": "active",
                                   "phone": "081200000041",
                                   "addresses": [{"id": adr, "label": "Utama", "city": "Bandung", "address": "Jl. 41",
                                                  "recipient_name": "Pak Uji", "phone": "081200000041"}]})
    return cus, adr


async def _pesan(klien, db, siap, *, rek: str = "", periksa: bool = True, pelanggan: tuple = ()) -> dict:
    """Pesanan CBD Rp 1.000.000 lewat API (tanpa PPN), "Periksa & lepas" (atau hanya diajukan) → `approved` +
    `pay_hold` (pola `test_F1_3_pelaksana`)."""
    cus, adr = pelanggan or (siap["cus"], siap["adr"])
    await db.inventory_rolls.insert_one({
        "id": _id("roll"), "roll_no": f"R-F14-{next(_n)}", "product_id": siap["prd"], "owner_entity_id": KSC,
        "warehouse_id": "wh_f14", "status": "available", "active_movement": None, "length_remaining": 100.0,
        "lot": "L-F14", "created_at": now_iso()})
    body = {"customer_id": cus, "shipping_address_id": adr, "entity_id": KSC, "payment_term_code": "CBD",
            "payment_method_code": "transfer", "receiving_account_id": rek or siap["A"],
            "items": [{"product_id": siap["prd"], "quantity": 100, "unit": "meter"}], **TANPA_PPN}
    r = await klien.post("/api/sales-orders", headers=siap["h"], json=body)
    assert r.status_code == 200, r.text
    so = r.json()
    assert so["grand_total"] == 1_000_000, so["grand_total"]
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"sales_id": siap["sales"]["id"]}})   # FIXTURE
    jalan = "review-release" if periksa else "submit-for-approval"
    r = await klien.post(f"/api/sales-orders/{so['id']}/{jalan}", headers=siap["h"],
                         **({"json": {"note": "uji"}} if periksa else {}))
    assert r.status_code == 200, r.text
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["pay_hold"], cur.get("status")
    return cur


async def _kode(db, oid: str) -> str:
    return (await db.payment_codes.find_one({"order_id": oid}, {"_id": 0}, sort=[("created_at", 1)]))["code"]


def _baris_impor(baris: list) -> list:
    return [{"stmt_date": b.get("tgl", TGL), "amount": b["nominal"], "direction": b.get("arah", "in"),
             "description": b["berita"], "ref": b.get("ref", ""), "external_id": b.get("ext") or _id("ext")}
            for b in baris]


async def _impor_api(klien, h, rek: str, baris: list):
    """`POST /api/bank-reconciliation/import` — kait F1 berjalan."""
    return await klien.post(f"{REC}/import", headers=h, json={"bank_account_id": rek, "lines": _baris_impor(baris)})


async def _impor_svc(db, rek: str, nominal: float, berita: str, *, ref: str = "", entity: str = "") -> dict:
    """Layanan impor TANPA kait F1 — baris berkode tetap `unmatched` (bahan operasi manual)."""
    from services import bank_recon_service as brs
    res = await brs.import_lines(rek, entity, _baris_impor([{"nominal": nominal, "berita": berita, "ref": ref}]),
                                 "uji F1-4")
    assert res["imported"] == 1, res
    return await db.bank_statement_lines.find_one({"import_batch": res["import_batch"]}, {"_id": 0})


async def _baris_batch(db, batch: str) -> list:
    rows = await db.bank_statement_lines.find({"import_batch": batch}, {"_id": 0}).to_list(50)
    return sorted(rows, key=lambda r: r["created_at"])


async def _baris(db, lid: str) -> dict:
    return await db.bank_statement_lines.find_one({"id": lid}, {"_id": 0})


async def _kwitansi_baris(db, lid: str, status: str = "") -> list:
    return await db.ar_receipts.find({"bank_line_id": lid, **({"status": status} if status else {})},
                                     {"_id": 0}).to_list(10)


async def _kwitansi_pesanan(db, oid: str) -> list:
    return await db.ar_receipts.find({"allocations.order_id": oid, "status": {"$ne": "void"}}, {"_id": 0}).to_list(10)


async def _lapor(klien, siap, oid: str, amount: float = 1_000_000, *, rek: str = "", catatan: str = "") -> dict:
    r = await klien.post(f"/api/sales-orders/{oid}/payment-reports", headers=siap["h_sa"], json={
        "amount": amount, "transfer_date": TGL, "account_id": rek or siap["A"], "method": "transfer",
        "reference_no": f"TRF-LB-F14-{next(_n)}", "note": "uji F1-4", "mismatch_note": catatan})
    assert r.status_code == 200, r.text
    return r.json()


def _isi(so: dict, amount: float = 1_000_000, **lain) -> dict:
    """Isian form "Terima pembayaran" untuk `POST /lines/{id}/receipt` (`ReceiptPayload` + `payment_report_id`)."""
    return {"customer_id": so["customer_id"], "amount": amount, "method": "transfer",
            "allocations": [{"order_id": so["id"], "amount": 1_000_000}], "reference_no": f"TRF-M-{next(_n)}",
            **lain}


async def _dari_mutasi(klien, h, lid: str, body: dict):
    return await klien.post(f"{REC}/lines/{lid}/receipt", headers=h, json=body)


async def _batal(klien, h, lid: str, alasan: str = "Pelanggan salah transfer"):
    return await klien.post(f"{REC}/lines/{lid}/void-receipt", headers=h, json={"reason": alasan})


async def _setel_otomatis(klien, siap, nilai: bool, alasan: str) -> None:
    r = await klien.put("/api/config/values", headers=siap["h"], json={"items": [{
        "key": "bank.kwitansi_otomatis_mutasi", "value": nilai, "scope_type": "entity", "scope_id": KSC,
        "reason": alasan, "effective_from": ""}]})
    assert r.status_code == 200, r.text


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


# ── Kait impor & "Cocokkan otomatis" ─────────────────────────────────────────────────────────────────────────────────
async def test_impor_mengembalikan_jumlah_otomatis_dan_kartu(klien, db, siap):
    s1, s2 = await _pesan(klien, db, siap), await _pesan(klien, db, siap)
    r = await _impor_api(klien, siap["h_fin"], siap["A"], [
        {"nominal": 1_000_000, "berita": f"TRSF {await _kode(db, s1['id'])} TOKO F14", "ref": "TRF-I-01"},
        {"nominal": 1_500_000, "berita": f"TRSF {await _kode(db, s2['id'])} TOKO F14"}])
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["imported"], j["kwitansi_otomatis"], j["kartu"], j["nilai_otomatis"]) == (2, 1, 1, 1_000_000), j
    sempurna, beda = await _baris_batch(db, j["import_batch"])
    assert sempurna["status"] == "matched" and sempurna["f1"]["status"] == "otomatis"
    [kw] = await _kwitansi_baris(db, sempurna["id"])
    assert (kw["source"], kw["bank_verified"], kw["reference_no"]) == ("mutasi_bank", True, "TRF-I-01")
    assert (beda["status"], beda["f1"]["status"], beda["f1"]["alasan_kode"]) == ("unmatched", "kartu", "nominal_beda")
    assert (await _so(db, s1["id"]))["status"] == "confirmed" and (await _so(db, s2["id"]))["pay_hold"]
    jejak = await db.audit_logs.find_one({"action": "bank_auto_receipt", "entity_id": sempurna["id"]}, {"_id": 0})
    assert jejak["after"]["pemicu"] == siap["fin"]["name"]                      # pemicu = nama pengimpor


async def test_impor_file_ikut_memproses(klien, db, siap):
    so = await _pesan(klien, db, siap)
    kode = await _kode(db, so["id"])
    raw = CSV.format(tgl="24/11/2026", ket=f"TRSF E-BANKING CR {kode} TOKO F14", nom="1.000.000,00", arah="CR")
    r = await klien.post(f"{REC}/import-file", headers=siap["h_fin"],
                         json={"bank_account_id": siap["A"], "raw": raw, "year_hint": 2026})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["imported"], j["kwitansi_otomatis"], j["kartu"], j["nilai_otomatis"]) == (1, 1, 0, 1_000_000), j
    [ln] = await _baris_batch(db, j["import_batch"])
    assert ln["status"] == "matched" and len(await _kwitansi_baris(db, ln["id"])) == 1


async def test_pengaturan_mati_impor_tanpa_kwitansi(klien, db, siap):
    """Review Focus 4 lewat rute impor: pengaturan PT mati → `kwitansi_otomatis == 0`, `kartu == 1`."""
    so = await _pesan(klien, db, siap)
    await _setel_otomatis(klien, siap, False, "uji F1-4")
    try:
        r = await _impor_api(klien, siap["h_fin"], siap["A"],
                             [{"nominal": 1_000_000, "berita": f"TRSF {await _kode(db, so['id'])}"}])
    finally:
        await _setel_otomatis(klien, siap, True, "pulihkan uji F1-4")
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["kwitansi_otomatis"], j["kartu"], j["nilai_otomatis"]) == (0, 1, 0), j
    [ln] = await _baris_batch(db, j["import_batch"])
    assert (ln["status"], ln["f1"]["alasan_kode"]) == ("unmatched", "otomatis_mati")
    assert await _kwitansi_pesanan(db, so["id"]) == []


async def test_galat_f1_tidak_menggagalkan_impor(klien, db, siap, monkeypatch):
    """Galat mesin F1 tidak menggagalkan impor maupun "Cocokkan otomatis": dicatat, jumlah 0."""
    from services import bank_auto_receipt_service as f1

    async def _rusak(*a, **kw):
        raise RuntimeError("mesin F1 rusak")
    monkeypatch.setattr(f1, "proses_impor", _rusak)
    monkeypatch.setattr(f1, "proses_rekening", _rusak)
    r = await _impor_api(klien, siap["h_fin"], siap["A"], [{"nominal": 250_000, "berita": "TRSF TANPA KODE F14"}])
    assert r.status_code == 200, r.text
    assert (r.json()["imported"], r.json()["kwitansi_otomatis"], r.json()["kartu"], r.json()["nilai_otomatis"]) == \
           (1, 0, 0, 0)
    r = await klien.post(f"{REC}/auto-match", headers=siap["h_fin"], json={"bank_account_id": siap["A"]})
    assert r.status_code == 200, r.text
    assert (r.json()["kwitansi_otomatis"], r.json()["kartu"], r.json()["nilai_otomatis"]) == (0, 0, 0)


async def test_cocokkan_otomatis_memproses_kartu_yang_kini_sempurna(klien, db, siap):
    rek = await _rekening_uji(klien, siap)
    so = await _pesan(klien, db, siap, rek=rek)
    r = await _impor_api(klien, siap["h_fin"], rek,
                         [{"nominal": 600_000, "berita": f"TRSF {await _kode(db, so['id'])}"}])
    assert r.status_code == 200, r.text
    assert (r.json()["kwitansi_otomatis"], r.json()["kartu"]) == (0, 1), r.json()
    [ln] = await _baris_batch(db, r.json()["import_batch"])
    assert ln["f1"]["alasan_kode"] == "nominal_beda"
    # Finance mencatat sebagian (Rp 400.000) → sisa tagihan Rp 600.000 = nominal mutasi
    r = await klien.post("/api/ar-receipts", headers=siap["h_fin"], json={
        "customer_id": so["customer_id"], "amount": 400_000, "method": "transfer", "entity_id": KSC,
        "account_id": rek, "receipt_date": TGL, "reference_no": "TRF-SEBAGIAN",
        "allocations": [{"order_id": so["id"], "amount": 400_000}]})
    assert r.status_code == 200, r.text
    r = await klien.post(f"{REC}/auto-match", headers=siap["h_fin"], json={"bank_account_id": rek})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["matched"], j["kwitansi_otomatis"], j["kartu"], j["nilai_otomatis"]) == (0, 1, 0, 600_000), j
    assert j["unmatched_lines"] == 0, j
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["f1"]["status"], cur["f1"]["jalur"]) == ("matched", "otomatis", "C")
    [kw] = await _kwitansi_baris(db, ln["id"])
    assert kw["amount"] == 600_000 and kw["bank_verified"] is True
    jejak = await db.audit_logs.find_one({"action": "bank_auto_receipt", "entity_id": ln["id"]}, {"_id": 0})
    assert jejak["after"]["pemicu"] == f"Cocokkan otomatis oleh {siap['fin']['name']}"


# ── Kwitansi dari mutasi (manual, atomik) ────────────────────────────────────────────────────────────────────────────
async def test_kwitansi_dari_mutasi_atomik(klien, db, siap):
    so = await _pesan(klien, db, siap)
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} MANUAL", ref="TRF-BANK-77")
    kas_awal = await db.cash_transactions.count_documents({})
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so, receipt_date="2030-01-01", account_id=siap["B"],
                                                               entity_id=KANDA))
    assert r.status_code == 200, r.text
    j = r.json()
    kw, baris = j["receipt"], j["line"]
    # server mengisi rekening, tanggal, nominal, PT, sumber dari MUTASI (isian badan untuk itu diabaikan)
    assert (kw["account_id"], kw["receipt_date"], kw["amount"], kw["entity_id"]) == (siap["A"], TGL, 1_000_000, KSC)
    assert (kw["source"], kw["bank_line_id"], kw["status"], kw["bank_verified"]) == \
           ("mutasi_bank", ln["id"], "posted", True)
    assert kw["created_by_name"] == siap["fin"]["name"] and kw["reference_no"].startswith("TRF-M-")
    assert [(a["order_id"], a["applied"]) for a in kw["allocations"]] == [(so["id"], 1_000_000)]
    assert (baris["status"], baris["match_type"], baris["matched_txn_id"], baris["matched_by"]) == \
           ("matched", "manual", kw["cash_txn_id"], siap["fin"]["name"])
    assert "match_lock" not in await _baris(db, ln["id"])
    assert (baris["f1"]["status"], baris["f1"]["receipt_id"], baris["f1"]["pernah_otomatis"]) == \
           ("manual", kw["id"], False)
    assert j["released_order_ids"] == [so["id"]]
    assert (await _so(db, so["id"]))["status"] == "confirmed"
    assert await db.cash_transactions.count_documents({}) == kas_awal + 1      # satu kas, tanpa kas kedua
    jejak = await db.audit_logs.find_one({"action": "bank_line_receipt_created", "entity_id": ln["id"]}, {"_id": 0})
    assert jejak and jejak["after"]["receipt_number"] == kw["number"] and jejak["actor"] == siap["fin"]["name"]
    # klik kedua pada baris yang sama: sudah tertaut → 409, tanpa kwitansi kedua
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so))
    assert r.status_code == 409, r.text
    assert len(await _kwitansi_baris(db, ln["id"])) == 1


async def test_kwitansi_dari_mutasi_tautan_gagal_kwitansi_dibatalkan(klien, db, siap, monkeypatch):
    """Keputusan builder (Step 3): `create_receipt` sukses tetapi `_link` gagal → kwitansi itu dibatalkan (alasan sistem
    "tautan mutasi gagal") dan 409 berkalimat — tidak ada kwitansi `posted` tanpa tautan."""
    from services import bank_recon_service as brs
    so = await _pesan(klien, db, siap)
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} GAGAL")

    async def _gagal(line, allocations, actor, match_type, match_kind, op=""):
        await db.bank_statement_lines.update_one({"id": line["id"], "match_lock": op},   # perilaku `_link` gagal
                                                 {"$unset": {"match_lock": "", "match_lock_at": ""}})
        raise ValueError("Sisa transaksi buku tidak cukup (baru saja dipakai proses lain / alokasi ganda).")
    monkeypatch.setattr(brs, "_link", _gagal)
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so))
    assert r.status_code == 409, r.text
    [kw] = await _kwitansi_baris(db, ln["id"])
    assert (kw["status"], kw["voided_reason"]) == ("void", "tautan mutasi gagal")
    assert _detail(r) == (f"Mutasi gagal ditautkan ke kwitansi {kw['number']}: Sisa transaksi buku tidak cukup (baru "
                          "saja dipakai proses lain / alokasi ganda). Kwitansi itu dibatalkan lagi (tidak ada kwitansi "
                          "tanpa mutasi) — muat ulang lalu coba lagi.")
    assert r.headers.get("x-idempotency-retry") == "true"
    assert await _kwitansi_baris(db, ln["id"], "posted") == [] and await _kwitansi_pesanan(db, so["id"]) == []
    cur = await _baris(db, ln["id"])
    assert cur["status"] == "unmatched" and "match_lock" not in cur
    assert float((await _so(db, so["id"])).get("paid_total") or 0) == 0
    monkeypatch.undo()
    # percobaan berikutnya berhasil dengan kwitansi baru (indeks `uq_bank_line_receipt` hanya kwitansi hidup)
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so))
    assert r.status_code == 200, r.text
    assert [k["id"] for k in await _kwitansi_baris(db, ln["id"], "posted")] == [r.json()["receipt"]["id"]]


@pytest.mark.parametrize("nominal, kode", [(900_000, 400), (999_999.5, 200)], ids=["beda_ditolak", "pecahan_boleh"])
async def test_kwitansi_dari_mutasi_nominal_harus_sama_mutasi(klien, db, siap, nominal, kode):
    so = await _pesan(klien, db, siap)
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} NOMINAL")
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so, nominal))
    assert r.status_code == kode, r.text
    if kode == 400:
        assert _detail(r) == PESAN_NOMINAL.format(badan="Rp 900.000")
        assert await _kwitansi_baris(db, ln["id"]) == [] and "match_lock" not in await _baris(db, ln["id"])
    else:
        assert r.json()["receipt"]["amount"] == 1_000_000        # kas = nominal mutasi (cent-tepat untuk tautan)


async def test_kwitansi_dari_mutasi_keputusan_selisih_kas_tetap_mutasi(klien, db, siap):
    """R9 — nominal form ≠ nominal mutasi selalu 400, JUGA bila membawa keputusan selisih (keputusan dihitung server dari
    nominal kwitansi, bukan angka yang dilihat pengguna). Keputusan selisih tetap boleh untuk alokasi < kas: nominal =
    mutasi Rp 1.000.000, alokasi Rp 800.000 → kas Rp 1.000.000, teralokasi Rp 800.000, sisa Rp 200.000."""
    so = await _pesan(klien, db, siap)
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} SELISIH")
    keputusan = {"kind": "deposit", "reason_code": "customer_overtransfer", "note": "uji F1-4"}
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so, 1_200_000, variance=keputusan))
    assert r.status_code == 400, r.text
    assert _detail(r) == PESAN_NOMINAL.format(badan="Rp 1.200.000")
    assert await _kwitansi_baris(db, ln["id"]) == [] and "match_lock" not in await _baris(db, ln["id"])
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(
        so, 1_000_000, variance=keputusan, allocations=[{"order_id": so["id"], "amount": 800_000}]))
    assert r.status_code == 200, r.text
    kw = r.json()["receipt"]
    assert (kw["amount"], kw["applied_total"], kw["unapplied_amount"]) == (1_000_000, 800_000, 200_000), kw
    assert r.json()["line"]["status"] == "matched" and kw["bank_verified"] is True


@pytest.mark.parametrize("alokasi", ["eksplisit", "tertua_dulu"])
async def test_kwitansi_dari_mutasi_tolak_selama_laporan_menunggu(klien, db, siap, alokasi):
    so = await _pesan(klien, db, siap, pelanggan=await _pelanggan(db))
    rep = await _lapor(klien, siap, so["id"])
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} LAPOR")
    body = _isi(so) if alokasi == "eksplisit" else {**_isi(so), "allocations": []}
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], body)
    assert r.status_code == 409, r.text
    assert _detail(r) == PESAN_LAPORAN.format(nomor=rep["number"])
    assert await _kwitansi_pesanan(db, so["id"]) == []
    cur = await _baris(db, ln["id"])
    assert cur["status"] == "unmatched" and "match_lock" not in cur
    assert (await db.payment_reports.find_one({"id": rep["id"]}, {"_id": 0}))["status"] == "menunggu"


async def test_kwitansi_dari_mutasi_dengan_laporan_diterima(klien, db, siap):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])                                   # tanpa lampiran: mutasi = bukti
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} LAPOR TERIMA")
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so, payment_report_id=rep["id"]))
    assert r.status_code == 200, r.text
    j = r.json()
    lap = await db.payment_reports.find_one({"id": rep["id"]}, {"_id": 0})
    assert (lap["status"], lap["decided_by_name"], lap["receipt_id"]) == ("diterima", siap["fin"]["name"],
                                                                         j["receipt"]["id"])
    [kw] = await _kwitansi_pesanan(db, so["id"])
    assert (kw["id"], kw["payment_report_id"], kw["bank_line_id"], kw["source"]) == \
           (j["receipt"]["id"], rep["id"], ln["id"], "mutasi_bank")
    assert kw["bank_verified"] is True and (kw["account_id"], kw["receipt_date"]) == (siap["A"], TGL)
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["match_type"], cur["f1"]["status"], cur["f1"]["report_id"]) == \
           ("matched", "manual", "manual", rep["id"])
    assert j["released_order_ids"] == [so["id"]] and (await _so(db, so["id"]))["status"] == "confirmed"
    jejak = await db.audit_logs.find_one({"action": "payment_report_accepted", "entity_id": rep["id"]}, {"_id": 0})
    assert jejak and (jejak["actor"], jejak["after"]["bank_line_id"], jejak["after"]["released"]) == \
           (siap["fin"]["name"], ln["id"], True)


async def test_kwitansi_dari_mutasi_laporan_tidak_sama_ditolak(klien, db, siap):
    so = await _pesan(klien, db, siap)
    kode = await _kode(db, so["id"])
    rep_nom = await _lapor(klien, siap, so["id"], 600_000)
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {kode} LAPOR BEDA")
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so, payment_report_id=rep_nom["id"]))
    assert r.status_code == 409, r.text
    assert _detail(r) == (f"Nominal laporan bayar {rep_nom['number']} Rp 600.000 berbeda dari mutasi Rp 1.000.000 — "
                          "Tolak laporan itu bila bukan pembayaran ini.")
    r = await klien.post(f"/api/payment-reports/{rep_nom['id']}/tolak", headers=siap["h_fin"],
                         json={"reason": "Nominal salah ketik"})
    assert r.status_code == 200, r.text
    rep_rek = await _lapor(klien, siap, so["id"], rek=siap["B"], catatan="Pelanggan transfer ke Mandiri")
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so, payment_report_id=rep_rek["id"]))
    assert r.status_code == 409, r.text
    assert _detail(r) == (f"Laporan bayar {rep_rek['number']} ke rekening Mandiri Penerimaan F14 ≠ rekening mutasi BCA "
                          "Penerimaan F14 — Tolak laporan itu bila bukan pembayaran ini.")
    assert await _kwitansi_pesanan(db, so["id"]) == []
    assert (await db.payment_reports.find_one({"id": rep_rek["id"]}, {"_id": 0}))["status"] == "menunggu"
    cur = await _baris(db, ln["id"])
    assert cur["status"] == "unmatched" and "match_lock" not in cur


async def test_kwitansi_dari_mutasi_sudah_punya_kwitansi(klien, db, siap):
    """Kwitansi otomatis yang tautannya dilepas lewat "Lepas" biasa masih hidup: catat lagi dari mutasi → 409 (bukan
    kwitansi kedua)."""
    so = await _pesan(klien, db, siap)
    r = await _impor_api(klien, siap["h_fin"], siap["A"], [{"nominal": 1_000_000,
                                                           "berita": f"TRSF {await _kode(db, so['id'])} LEPAS"}])
    [ln] = await _baris_batch(db, r.json()["import_batch"])
    [kw] = await _kwitansi_baris(db, ln["id"])
    r = await klien.post(f"{REC}/lines/{ln['id']}/unmatch", headers=siap["h_fin"])
    assert r.status_code == 200, r.text
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so))
    assert r.status_code == 409, r.text
    assert _detail(r) == (f"Mutasi ini sudah punya kwitansi {kw['number']}. Cocokkan kwitansi itu di Rekonsiliasi "
                          "Bank, atau batalkan dulu bila keliru.")
    assert [k["id"] for k in await _kwitansi_baris(db, ln["id"])] == [kw["id"]]


async def test_kwitansi_dari_mutasi_baris_sedang_diklaim(klien, db, siap):
    """Baris yang `match_lock`-nya dipegang proses lain (pencocokan / mesin F1) → 409 sementara (boleh kirim ulang),
    tanpa kwitansi; kunci proses lain tidak disentuh."""
    so = await _pesan(klien, db, siap)
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} DIKLAIM")
    await db.bank_statement_lines.update_one({"id": ln["id"]}, {"$set": {   # FIXTURE: proses lain memegang baris
        "match_lock": "bmatch_lain", "match_lock_at": now_iso()}})
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so))
    assert r.status_code == 409, r.text
    assert _detail(r) == "Mutasi ini sedang diproses pencocokan lain. Tunggu sebentar lalu muat ulang."
    assert r.headers.get("x-idempotency-retry") == "true"
    assert await _kwitansi_pesanan(db, so["id"]) == [] and (await _baris(db, ln["id"]))["match_lock"] == "bmatch_lain"
    await db.bank_statement_lines.update_one({"id": ln["id"]}, {"$unset": {"match_lock": "", "match_lock_at": ""}})


async def test_manual_tidak_diproses_mesin_sesudah_lepas(klien, db, siap):
    """Baris yang kwitansinya dicatat manual dari mutasi (`f1.status = manual`) lalu dilepas tidak ditautkan ulang
    mesin."""
    from services.bank_auto_receipt_service import proses_baris
    so = await _pesan(klien, db, siap)
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} MANUAL LEPAS")
    assert (await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so))).status_code == 200
    r = await klien.post(f"{REC}/lines/{ln['id']}/unmatch", headers=siap["h_fin"])
    assert r.status_code == 200, r.text
    h = await proses_baris(await _baris(db, ln["id"]), PEMICU)
    assert (h["hasil"], h["alasan_kode"]) == ("lewati", "dicatat_manual"), h
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["f1"]["status"]) == ("unmatched", "manual")


# ── Izin & PT ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_izin(klien, db, siap, akun, sesi, peran_tanpa_acuan):
    so = await _pesan(klien, db, siap)
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} IZIN")
    # sales: punya ar_receipt.create, tanpa cash.create → 403
    r = await _dari_mutasi(klien, siap["h_sales"], ln["id"], _isi(so))
    assert r.status_code == 403, r.text
    # pemegang cash.create tanpa ar_receipt.create → 403
    kas_saja = await akun(await peran_tanpa_acuan({"cash": ["view", "create"]}, label="F14 kas saja"))
    r = await _dari_mutasi(klien, await sesi(kas_saja), ln["id"], _isi(so))
    assert r.status_code == 403, r.text
    # menerima laporan bersama mutasi = putusan Lapor Bayar: tanpa payment_report.decide → 403
    rep = await _lapor(klien, siap, so["id"])
    tanpa_putus = await akun(await peran_tanpa_acuan({"cash": ["view", "create"], "ar_receipt": ["view", "create"]},
                                                     label="F14 tanpa putus"))
    r = await _dari_mutasi(klien, await sesi(tanpa_putus), ln["id"], _isi(so, payment_report_id=rep["id"]))
    assert r.status_code == 403, r.text
    assert await _kwitansi_baris(db, ln["id"]) == [] and (await _baris(db, ln["id"]))["status"] == "unmatched"
    # manajer → 200
    r = await _dari_mutasi(klien, siap["h_mgr"], ln["id"], _isi(so, payment_report_id=rep["id"]))
    assert r.status_code == 200, r.text
    # batal: sales, dan peran finance tanpa ar_receipt.void (cash.create + ar_receipt.create) → 403; ar_receipt.void
    # tanpa cash.create → 403; manajer → 200. (Finance bawaan memegang ar_receipt.void sejak K-FIN-01: Finance =
    # Manajer.)
    for h in (siap["h_sales"], await sesi(tanpa_putus)):
        r = await _batal(klien, h, ln["id"])
        assert r.status_code == 403, r.text
    void_saja = await akun(await peran_tanpa_acuan({"ar_receipt": ["view", "void"]}, label="F14 void saja"))
    r = await _batal(klien, await sesi(void_saja), ln["id"])
    assert r.status_code == 403, r.text
    assert (await _baris(db, ln["id"]))["status"] == "matched"
    r = await _batal(klien, siap["h_mgr"], ln["id"])
    assert r.status_code == 200, r.text


async def test_pt_lain_403(klien, db, siap):
    """Baris mutasi rekening PT lain (`ent_kanda`) → 403 untuk kedua rute baru, tanpa tulisan."""
    so = await _pesan(klien, db, siap)
    ln = await _impor_svc(db, siap["K"], 1_000_000, "TRSF TOKO KANDA F14", entity=KANDA)
    assert ln["entity_id"] == KANDA
    r = await _dari_mutasi(klien, siap["h_mgr"], ln["id"], _isi(so))
    assert r.status_code == 403, r.text
    r = await _batal(klien, siap["h_mgr"], ln["id"])
    assert r.status_code == 403, r.text
    cur = await _baris(db, ln["id"])
    assert cur["status"] == "unmatched" and "match_lock" not in cur and "f1" not in cur
    assert await _kwitansi_baris(db, ln["id"]) == []


# ── Batal kwitansi mutasi ────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("periksa", [True, False], ids=["sudah_dilepas", "belum_dilepas"])
async def test_batal_kwitansi_mutasi(klien, db, siap, periksa):
    so = await _pesan(klien, db, siap, periksa=periksa)
    r = await _impor_api(klien, siap["h_fin"], siap["A"], [{"nominal": 1_000_000,
                                                           "berita": f"TRSF {await _kode(db, so['id'])} BATAL"}])
    assert r.json()["kwitansi_otomatis"] == 1, r.json()
    [ln] = await _baris_batch(db, r.json()["import_batch"])
    [kw] = await _kwitansi_baris(db, ln["id"])
    status_pesanan = (await _so(db, so["id"]))["status"]
    assert status_pesanan == ("confirmed" if periksa else "approved")
    r = await _batal(klien, siap["h_mgr"], ln["id"], "  ab ")                   # alasan < 5 huruf
    assert r.status_code == 400, r.text
    assert _detail(r) == "Alasan pembatalan wajib diisi (min. 5 huruf)."
    r = await _batal(klien, siap["h_mgr"], ln["id"], "Salah pelanggan transfer")
    assert r.status_code == 200, r.text
    j = r.json()
    if periksa:
        assert j["order_released"] is True
        assert j["peringatan"] == PERINGATAN.format(no=so["number"], status="Terkonfirmasi")
    else:
        assert (j["order_released"], j["peringatan"]) == (False, "")
    rc = await db.ar_receipts.find_one({"id": kw["id"]}, {"_id": 0})
    assert (rc["status"], rc["voided_reason"], rc["voided_by"]) == ("void", "Salah pelanggan transfer",
                                                                    siap["mgr"]["name"])
    cur = await _baris(db, ln["id"])
    assert cur["status"] == "unmatched" and "match_lock" not in cur
    assert (cur["f1"]["status"], cur["f1"]["pernah_otomatis"], cur["f1"]["receipt_id"]) == \
           ("dibatalkan", True, kw["id"])
    assert cur["f1"]["dilepas_at"]
    jejak = await db.audit_logs.find_one({"action": "bank_line_receipt_voided", "entity_id": ln["id"]}, {"_id": 0})
    assert jejak and jejak["after"]["receipt_number"] == kw["number"] and jejak["actor"] == siap["mgr"]["name"]
    assert await db.audit_logs.find_one({"action": "ar_receipt_voided", "entity_id": kw["id"]})
    # "Cocokkan otomatis" sesudahnya tidak membuat kwitansi baru untuk baris ini
    r = await klien.post(f"{REC}/auto-match", headers=siap["h_fin"], json={"bank_account_id": siap["A"]})
    assert r.status_code == 200, r.text
    assert await _kwitansi_pesanan(db, so["id"]) == [] and (await _baris(db, ln["id"]))["f1"]["status"] == "dibatalkan"
    # pembatalan kedua: baris tidak tertaut → 409
    r = await _batal(klien, siap["h_mgr"], ln["id"])
    assert r.status_code == 409, r.text


async def test_batal_kwitansi_bukan_dari_mutasi_ditolak(klien, db, siap):
    """Baris jalur A (kwitansi manual biasa yang ditautkan mesin) → 409; kwitansi & tautan tidak berubah."""
    so = await _pesan(klien, db, siap)
    r = await klien.post("/api/ar-receipts", headers=siap["h_fin"], json={
        "customer_id": so["customer_id"], "amount": 1_000_000, "method": "transfer", "entity_id": KSC,
        "account_id": siap["A"], "receipt_date": TGL, "reference_no": "TRF-A-F14",
        "allocations": [{"order_id": so["id"], "amount": 1_000_000}]})
    assert r.status_code == 200, r.text
    kw = r.json()
    r = await _impor_api(klien, siap["h_fin"], siap["A"], [{"nominal": 1_000_000,
                                                           "berita": f"TRSF {await _kode(db, so['id'])} JALUR A"}])
    [ln] = await _baris_batch(db, r.json()["import_batch"])
    assert (ln["status"], ln["f1"]["jalur"]) == ("matched", "A")
    r = await _batal(klien, siap["h_mgr"], ln["id"])
    assert r.status_code == 409, r.text
    assert _detail(r) == PESAN_BUKAN_MUTASI
    assert (await db.ar_receipts.find_one({"id": kw["id"]}, {"_id": 0}))["status"] == "posted"
    assert (await _baris(db, ln["id"]))["status"] == "matched"


async def test_batal_gagal_mutasi_ditautkan_kembali(klien, db, siap, monkeypatch):
    """`void_receipt` menolak sesudah tautan dilepas → tautan dipasang kembali (kwitansi tetap terverifikasi bank,
    penanda f1 seperti semula), galat aslinya diteruskan."""
    from services import ar_receipt_service as ars
    so = await _pesan(klien, db, siap)
    r = await _impor_api(klien, siap["h_fin"], siap["A"], [{"nominal": 1_000_000,
                                                           "berita": f"TRSF {await _kode(db, so['id'])} TOLAK BATAL"}])
    [ln] = await _baris_batch(db, r.json()["import_batch"])
    [kw] = await _kwitansi_baris(db, ln["id"])

    async def _tolak(receipt_id, actor, reason=""):
        raise HTTPException(status_code=409, detail="Periode buku hari ini sudah ditutup.")
    monkeypatch.setattr(ars, "void_receipt", _tolak)
    r = await _batal(klien, siap["h_mgr"], ln["id"])
    assert r.status_code == 409 and _detail(r) == "Periode buku hari ini sudah ditutup.", r.text
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["matched_txn_id"], cur["match_type"]) == ("matched", kw["cash_txn_id"], "auto_receipt")
    assert "match_lock" not in cur and cur["f1"] == ln["f1"]
    rc = await db.ar_receipts.find_one({"id": kw["id"]}, {"_id": 0})
    assert (rc["status"], rc["bank_verified"]) == ("posted", True)


async def test_T4_M1_klaim_ulang_gagal_kwitansi_tidak_dibatalkan(klien, db, siap, monkeypatch):
    """T4-M1 (gelombang akhir) — sesudah tautan dilepas, klaim ulang baris gagal (proses lain memegang baris): kwitansi
    TIDAK dibatalkan, tautan dipasang kembali (penanda f1 seperti semula), 409 "sedang diproses pencocokan lain"."""
    from services import bank_auto_receipt_service as f1
    so = await _pesan(klien, db, siap)
    r = await _impor_api(klien, siap["h_fin"], siap["A"], [{"nominal": 1_000_000,
                                                           "berita": f"TRSF {await _kode(db, so['id'])} KLAIM KALAH"}])
    [ln] = await _baris_batch(db, r.json()["import_batch"])
    [kw] = await _kwitansi_baris(db, ln["id"])

    async def _kalah(line_id):
        return ""
    monkeypatch.setattr(f1, "_klaim", _kalah)
    r = await _batal(klien, siap["h_mgr"], ln["id"])
    assert r.status_code == 409, r.text
    assert _detail(r) == f1.PESAN_BATAL_DIKLAIM
    assert r.headers.get("x-idempotency-retry") == "true"
    rc = await db.ar_receipts.find_one({"id": kw["id"]}, {"_id": 0})
    assert (rc["status"], rc["bank_verified"]) == ("posted", True)
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["matched_txn_id"], cur["match_type"]) == ("matched", kw["cash_txn_id"], "auto_receipt")
    assert "match_lock" not in cur and cur["f1"] == ln["f1"]
    monkeypatch.undo()
    r = await _batal(klien, siap["h_mgr"], ln["id"])                          # klaim tidak lagi kalah: batal berjalan
    assert r.status_code == 200, r.text
    assert (await _baris(db, ln["id"]))["f1"]["status"] == "dibatalkan"


async def test_T4_M5_batal_kwitansi_jalur_B_laporan_tetap_diterima(klien, db, siap):
    """T4-M5 — kwitansi jalur B (laporan bayar diterima otomatis bersama mutasi) dibatalkan lewat "Batalkan kwitansi
    dari mutasi": aturan Lapor Bayar yang ada (§5.6) — laporan tetap `diterima` (tidak terkunci, tidak kembali
    menunggu), pembayaran pesanan dibalik, baris `dibatalkan` dengan rujukan laporannya."""
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    r = await _impor_api(klien, siap["h_fin"], siap["A"], [{"nominal": 1_000_000,
                                                           "berita": f"TRSF {await _kode(db, so['id'])} BATAL B"}])
    assert r.json()["kwitansi_otomatis"] == 1, r.json()
    [ln] = await _baris_batch(db, r.json()["import_batch"])
    assert (ln["f1"]["status"], ln["f1"]["jalur"], ln["f1"]["report_id"]) == ("otomatis", "B", rep["id"])
    [kw] = await _kwitansi_baris(db, ln["id"])
    assert kw["payment_report_id"] == rep["id"]
    r = await _batal(klien, siap["h_mgr"], ln["id"], "Bukti laporan keliru")
    assert r.status_code == 200, r.text
    assert (await db.ar_receipts.find_one({"id": kw["id"]}, {"_id": 0}))["status"] == "void"
    lap = await db.payment_reports.find_one({"id": rep["id"]}, {"_id": 0})
    assert (lap["status"], lap["receipt_id"]) == ("diterima", kw["id"])
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["f1"]["status"], cur["f1"]["report_id"]) == ("unmatched", "dibatalkan", rep["id"])
    assert float((await _so(db, so["id"])).get("paid_total") or 0) == 0
    assert await _kwitansi_pesanan(db, so["id"]) == []


async def test_laporan_manual_tautan_gagal_laporan_kembali_menunggu(klien, db, siap, monkeypatch):
    """Gelombang akhir (Minor 1 tinjauan) — "Terima laporan ini dengan mutasi ini": Terima berhasil tetapi tautan
    mutasi gagal → kwitansi dibatalkan DAN laporan kembali `menunggu` (dulu tertinggal `diterima` menunjuk kwitansi
    batal, tidak bisa diulang). Percobaan berikutnya menerima laporan yang sama dengan kwitansi baru."""
    from services import bank_auto_receipt_service as f1
    from services import bank_recon_service as brs
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} LAPOR GAGAL TAUT")

    async def _gagal(line, allocations, actor, match_type, match_kind, op=""):
        await db.bank_statement_lines.update_one({"id": line["id"], "match_lock": op},   # perilaku `_link` gagal
                                                 {"$unset": {"match_lock": "", "match_lock_at": ""}})
        raise ValueError("Sisa transaksi buku tidak cukup (baru saja dipakai proses lain / alokasi ganda).")
    monkeypatch.setattr(brs, "_link", _gagal)
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so, payment_report_id=rep["id"]))
    assert r.status_code == 409, r.text
    [kw] = await _kwitansi_baris(db, ln["id"])
    assert (kw["status"], kw["voided_reason"]) == ("void", "tautan mutasi gagal")
    assert _detail(r) == f1.PESAN_TAUTAN_GAGAL_LAPORAN.format(
        nomor=kw["number"], galat="Sisa transaksi buku tidak cukup (baru saja dipakai proses lain / alokasi ganda)",
        laporan=rep["number"])
    lap = await db.payment_reports.find_one({"id": rep["id"]}, {"_id": 0})
    assert lap["status"] == "menunggu" and not lap.get("receipt_id") and "claim" not in lap, lap
    assert "tautan mutasi gagal" in lap["status_history"][-1]["note"]
    assert (await _baris(db, ln["id"]))["status"] == "unmatched"
    monkeypatch.undo()
    r = await _dari_mutasi(klien, siap["h_fin"], ln["id"], _isi(so, payment_report_id=rep["id"]))
    assert r.status_code == 200, r.text
    lap = await db.payment_reports.find_one({"id": rep["id"]}, {"_id": 0})
    assert (lap["status"], lap["receipt_id"]) == ("diterima", r.json()["receipt"]["id"])
    assert [k["id"] for k in await _kwitansi_pesanan(db, so["id"])] == [r.json()["receipt"]["id"]]


# ── R7 — Minor T3 dibawa ke T4 ───────────────────────────────────────────────────────────────────────────────────────
async def test_R7_M1_pemenang_kembar_belum_tuntas(klien, db, siap, monkeypatch):
    """M1 — `DuplicateKeyError` dan kwitansi pemenang belum tuntas (`effects_done: False`) → tidak ditautkan: kartu
    `galat` "belum tuntas dibuat" (pola `_pulihkan`)."""
    from services import ar_receipt_service as ars
    from services.bank_auto_receipt_service import proses_baris
    so = await _pesan(klien, db, siap)
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} KEMBAR")
    nomor = f"AR-F14-SETENGAH-{next(_n)}"

    async def _kalah(payload, actor):
        await db.ar_receipts.insert_one({   # FIXTURE: pemenang (proses lain) masih membuat kwitansinya
            "id": _id("arc"), "number": nomor, "status": "posted", "effects_done": False, "bank_line_id": ln["id"],
            "source": "mutasi_bank", "amount": 1_000_000, "cash_txn_id": "", "allocations": [],
            "entity_id": KSC, "created_at": now_iso()})
        raise DuplicateKeyError("E11000 duplicate key error index: uq_bank_line_receipt")
    monkeypatch.setattr(ars, "create_receipt", _kalah)
    h = await proses_baris(ln, PEMICU)
    assert (h["hasil"], h["alasan_kode"]) == ("kartu", "galat"), h
    assert h["alasan"] == (f"Kwitansi {nomor} dari mutasi ini belum tuntas dibuat. Tunggu sebentar lalu tekan "
                           "\"Cocokkan otomatis\" lagi.")
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["f1"]["alasan_kode"]) == ("unmatched", "galat") and "match_lock" not in cur


async def test_R7_M2_penanda_tidak_ditimpa_pagar_terakhir(klien, db, siap, monkeypatch):
    """M2 — pagar terakhir `proses_baris` (galat sebelum klaim) tidak menimpa penanda baris yang pernah otomatis."""
    from services import bank_auto_receipt_service as f1
    from services import bank_recon_service as brs
    so = await _pesan(klien, db, siap)
    r = await _impor_api(klien, siap["h_fin"], siap["A"], [{"nominal": 1_000_000,
                                                           "berita": f"TRSF {await _kode(db, so['id'])} PAGAR"}])
    [ln] = await _baris_batch(db, r.json()["import_batch"])
    await brs.unmatch(ln["id"], "Uji Finance F14", [KSC])
    lepas = await _baris(db, ln["id"])
    assert lepas["f1"]["pernah_otomatis"] is True

    async def _rusak(line):
        raise RuntimeError("basis data terputus")
    monkeypatch.setattr(f1, "nilai_baris", _rusak)
    h = await f1.proses_baris(lepas, PEMICU)
    assert (h["hasil"], h["alasan_kode"]) == ("kartu", "galat"), h
    assert (await _baris(db, ln["id"]))["f1"] == lepas["f1"]                   # penanda tetap, tidak ditimpa


@pytest.mark.parametrize("penanda", ["dibatalkan", "pernah_otomatis"])
async def test_R7_M2_penanda_dicek_ulang_sebelum_pemulihan(klien, db, siap, monkeypatch, penanda):
    """M2 — penanda yang terpasang sesudah penilaian awal (sebelum klaim) dicek ulang di bawah kunci: tidak ada
    pemulihan (tautan) untuk baris berpenanda."""
    from services import ar_receipt_service as ars
    from services import bank_auto_receipt_service as f1
    so = await _pesan(klien, db, siap)
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} CEK ULANG")
    kw = await ars.create_receipt({   # FIXTURE alur: kwitansi lahir dari baris ini, belum tertaut
        "customer_id": so["customer_id"], "amount": 1_000_000, "method": "transfer", "entity_id": KSC,
        "account_id": siap["A"], "receipt_date": TGL, "reference_no": "TRF-CEK",
        "allocations": [{"order_id": so["id"], "amount": 1_000_000}], "source": "mutasi_bank",
        "bank_line_id": ln["id"]}, dict(f1.AKTOR_MUTASI))
    asli = f1.nilai_baris
    panggil = []

    async def _awal_bersih(line):
        panggil.append(line["id"])
        if len(panggil) == 1:   # penilaian awal melihat baris tanpa penanda; penanda terpasang sebelum klaim
            hasil = await asli(line)
            tanda = ({"status": "dibatalkan", "pernah_otomatis": False} if penanda == "dibatalkan"
                     else {"status": "otomatis", "pernah_otomatis": True})
            await db.bank_statement_lines.update_one({"id": line["id"]}, {"$set": {"f1": tanda}})
            return hasil
        return await asli(line)
    monkeypatch.setattr(f1, "nilai_baris", _awal_bersih)
    h = await f1.proses_baris(ln, PEMICU)
    assert h["hasil"] == "lewati" and h["alasan_kode"] == penanda, h
    cur = await _baris(db, ln["id"])
    assert cur["status"] == "unmatched" and "match_lock" not in cur
    assert (await db.ar_receipts.find_one({"id": kw["id"]}, {"_id": 0}))["bank_verified"] is False


async def test_R7_M3_pemulihan_B_menuntaskan_laporan(klien, db, siap):
    """M3 — Terima jalur B mati sesudah kwitansi tuntas, sebelum laporan ditulis `diterima` (laporan tertinggal
    `memproses`, klaim basi) → pemulihan menautkan kwitansi DAN menuntaskan laporan."""
    from services import ar_receipt_service as ars
    from services import payment_report_service as prs
    from services.bank_auto_receipt_service import AKTOR_MUTASI, proses_baris
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    ln = await _impor_svc(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])} PULIH B")
    lap = await db.payment_reports.find_one({"id": rep["id"]}, {"_id": 0})
    kw = await ars.create_receipt(prs.isi_kwitansi(lap, await _so(db, so["id"]), ln), dict(AKTOR_MUTASI))
    await db.payment_reports.update_one({"id": rep["id"]}, {"$set": {   # FIXTURE: Terima terhenti, klaim basi
        "status": "memproses", "claim": {"token": "klaim_mati", "by": "", "by_name": "Sistem (mutasi bank)",
                                         "at": "2026-01-01T00:00:00+00:00"}}})
    h = await proses_baris(ln, PEMICU)
    assert (h["hasil"], h["jalur"], h["receipt_id"]) == ("otomatis", "B", kw["id"]), h
    lap = await db.payment_reports.find_one({"id": rep["id"]}, {"_id": 0})
    assert (lap["status"], lap["receipt_id"]) == ("diterima", kw["id"]) and "claim" not in lap
    assert len(await _kwitansi_pesanan(db, so["id"])) == 1
    assert (await _baris(db, ln["id"]))["status"] == "matched"


async def test_R7_M5_jalur_B_sales_satu_notifikasi(klien, db, siap):
    """M5 — jalur B untuk pesanan tertahan: sales menerima `lapor_bayar_diterima` saja (tanpa `bayar_masuk_mutasi`)."""
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    r = await _impor_api(klien, siap["h_fin"], siap["A"], [{"nominal": 1_000_000,
                                                           "berita": f"TRSF {await _kode(db, so['id'])} SATU NOTIF"}])
    assert r.json()["kwitansi_otomatis"] == 1, r.json()
    [ln] = await _baris_batch(db, r.json()["import_batch"])
    assert ln["f1"]["jalur"] == "B"
    assert await db.notifications.count_documents({"type": "bayar_masuk_mutasi",
                                                   "ref": {"$regex": f"^f1_bayar:{ln['id']}#"}}) == 0
    assert await db.notifications.count_documents({"type": "lapor_bayar_diterima",
                                                   "ref": f"{rep['id']}#{siap['sales']['id']}"}) == 1
