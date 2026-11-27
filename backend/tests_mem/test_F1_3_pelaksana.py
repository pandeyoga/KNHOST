"""F1 Kwitansi Otomatis dari Mutasi Bank · Tugas 3 — pelaksana: jalur A/B/C, proses impor & rekening, pemberitahuan.

Rancangan `docs/superpowers/specs/2026-11-27-kwitansi-otomatis-mutasi-design.md` §5.1, §5.3, §5.8. Semua uang lewat
pintu yang ada: kwitansi `ar_receipt_service.create_receipt` (jalur C) atau `payment_report_service.terima` (jalur B),
tautan mutasi `bank_recon_service._link` (klaim `match_lock` yang sama; jalur A/B/C), lepas
`bank_recon_service.unmatch`.

Persiapan (ALUR lewat API/layanan kecuali disebut FIXTURE):
  * rekening `ent_ksc`: **A** (BCA, penerimaan pelanggan, transfer bawaan), **B** (Mandiri, penerimaan pelanggan) —
    `POST /api/bank-accounts`;
  * pelanggan, produk Rp 10.000/m dan Rp 3.468,75/m, gudang, roll 100 m = FIXTURE (pola `test_LB4_putus`);
  * pesanan CBD/DP lewat API → "Periksa & lepas" → `approved` + `pay_hold`; rekening instruksi = A; sales pemilik
    ditulis langsung (FIXTURE);
  * mutasi lewat `bank_recon_service.import_lines` (layanan impor; kait router milik Tugas 4).

Hitung tangan (tanpa PPN):
  CBD 100 m × Rp 10.000 = Rp 1.000.000 → wajib sebelum gudang Rp 1.000.000 → mutasi Rp 1.000.000 berkode → kwitansi
  Rp 1.000.000 ke A bertanggal mutasi, dialokasikan Rp 1.000.000 → kas Rp 1.000.000 cocok penuh dengan mutasi →
  terverifikasi bank → tahan dibuka → `confirmed` (Admin Sales sudah "Periksa & lepas").
  DP50 100 m × Rp 3.468,75 = Rp 346.875 → wajib Rp 173.437,5. Mutasi Rp 173.438 → kwitansi Rp 173.438, alokasi
  Rp 173.437,5, lebih Rp 0,5 ≤ toleransi → pembulatan diputus otomatis. Mutasi Rp 173.437 → kwitansi Rp 173.437,
  alokasi Rp 173.437 (alokasi tidak boleh melebihi dana), kurang Rp 0,5 → pembulatan. Keduanya tanpa antrean selisih.

    cd /home/user/KNHOST && python -m pytest backend/tests_mem/test_F1_3_pelaksana.py -n 0 -q -p no:cacheprovider
"""
from __future__ import annotations

import asyncio
import itertools
import uuid

import pytest
from pymongo.errors import DuplicateKeyError

from core_utils import now_iso

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module", autouse=True)
def _unggahan_sementara(tmp_path_factory):
    """Bukti bayar yang diunggah uji modul ini ditulis ke folder sementara pytest, bukan ke `backend/uploads` repo."""
    from services import storage_service
    mp = pytest.MonkeyPatch()
    mp.setattr(storage_service, "STORAGE_DIR", tmp_path_factory.mktemp("unggahan_f13"))
    yield
    mp.undo()


KSC = "ent_ksc"
TGL = "2026-11-24"
PDF = b"%PDF-1.4\n" + b"0" * 2048
TANPA_PPN = {"tax_override": "non_ppn", "tax_override_reason": "uji F1-3 tanpa PPN"}
PEMICU = "Uji Pengimpor F13"
BAYAR = "bayar_masuk_mutasi"
RINGKASAN = "ringkasan_mutasi_otomatis"
_n = itertools.count(1)


def _id(awal: str) -> str:
    return f"{awal}_f13_{uuid.uuid4().hex[:8]}"


async def _rekening(klien, h, **isi) -> str:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], "holder_name": "PT Kain Suka Cita", "entity_id": KSC, **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    A = await _rekening(klien, kepala_admin, name="BCA Penerimaan F13", account_number="131-313-1313",
                        default_receiving_methods=["transfer"], show_on_documents=True)
    B = await _rekening(klien, kepala_admin, name="Mandiri Penerimaan F13", bank_name="Mandiri",
                        account_number="353-535-3535", default_receiving_methods=[])
    cus, adr, prd, prd_dp = _id("cus"), _id("adr"), _id("prd"), _id("prd")
    await db.customers.insert_one({"id": cus, "name": "Toko F1-3", "entity_id": KSC, "status": "active",
                                   "phone": "081200000013",
                                   "addresses": [{"id": adr, "label": "Utama", "city": "Bandung",
                                                  "address": "Jl. Uji 13", "recipient_name": "Bu Uji",
                                                  "phone": "081200000013"}]})
    for pid, sku, harga in ((prd, "F13-KAIN", 10000), (prd_dp, "F13-KAIN-DP", 3468.75)):
        await db.products.insert_one({"id": pid, "sku": sku, "name": f"Kain {sku}", "price": harga,
                                      "base_unit": "meter", "status": "active", "lifecycle": "produksi",
                                      "category": "uji"})
    await db.warehouses.insert_one({"id": "wh_f13", "name": "Gudang F1-3", "entity_id": KSC, "city": "Bandung"})
    sales = await akun("sales")
    sa = await akun("sales_admin")
    fin = await akun("finance")
    return {"h": kepala_admin, "A": A, "B": B, "cus": cus, "adr": adr, "prd": prd, "prd_dp": prd_dp,
            "sales": sales, "fin": fin, "h_sa": await sesi(sa), "h_fin": await sesi(fin)}


def _aktor(u: dict) -> dict:
    return {"id": u["id"], "name": u["name"], "role": u["role"]}


async def _so(db, oid: str) -> dict:
    return await db.sales_orders.find_one({"id": oid}, {"_id": 0})


async def _pesan(klien, db, siap, term: str = "CBD", *, prd: str = "", total: float = 1_000_000,
                periksa: bool = True) -> dict:
    """Pesanan lewat API (tanpa PPN), "Periksa & lepas" (atau hanya diajukan → disetujui otomatis, tanpa permintaan
    lepas) → `approved` + `pay_hold` (pola `test_LB4_putus`, `test_LB2_tahan_gudang`)."""
    await db.inventory_rolls.insert_one({
        "id": _id("roll"), "roll_no": f"R-F13-{next(_n)}", "product_id": prd or siap["prd"], "owner_entity_id": KSC,
        "warehouse_id": "wh_f13", "status": "available", "active_movement": None, "length_remaining": 100.0,
        "lot": "L-F13", "created_at": now_iso()})
    body = {"customer_id": siap["cus"], "shipping_address_id": siap["adr"], "entity_id": KSC,
            "payment_term_code": term, "payment_method_code": "transfer", "receiving_account_id": siap["A"],
            "items": [{"product_id": prd or siap["prd"], "quantity": 100, "unit": "meter"}], **TANPA_PPN}
    r = await klien.post("/api/sales-orders", headers=siap["h"], json=body)
    assert r.status_code == 200, r.text
    so = r.json()
    assert so["grand_total"] == total, so["grand_total"]
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"sales_id": siap["sales"]["id"]}})   # FIXTURE
    if periksa:
        r = await klien.post(f"/api/sales-orders/{so['id']}/review-release", headers=siap["h"], json={"note": "uji"})
    else:
        r = await klien.post(f"/api/sales-orders/{so['id']}/submit-for-approval", headers=siap["h"])
    assert r.status_code == 200, r.text
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["pay_hold"], cur.get("status")
    return cur


async def _kode(db, oid: str) -> str:
    return (await db.payment_codes.find_one({"order_id": oid}, {"_id": 0}, sort=[("created_at", 1)]))["code"]


async def _impor_banyak(rek: str, baris: list) -> dict:
    """Impor beberapa baris dalam SATU batch → hasil `import_lines` (`import_batch`, `imported`, `skipped`)."""
    from services import bank_recon_service as brs
    rows = [{"stmt_date": b.get("tgl", TGL), "amount": b["nominal"], "direction": b.get("arah", "in"),
             "description": b["berita"], "ref": b.get("ref", ""), "external_id": b.get("ext") or _id("ext")}
            for b in baris]
    return await brs.import_lines(rek, "", rows, "uji F1-3")


async def _baris_batch(db, batch: str) -> list:
    rows = await db.bank_statement_lines.find({"import_batch": batch}, {"_id": 0}).to_list(50)
    return sorted(rows, key=lambda r: r["created_at"])


async def _impor(db, rek: str, nominal: float, berita: str, *, ref: str = "", tgl: str = TGL) -> tuple:
    res = await _impor_banyak(rek, [{"nominal": nominal, "berita": berita, "ref": ref, "tgl": tgl}])
    assert res["imported"] == 1, res
    [ln] = await _baris_batch(db, res["import_batch"])
    return res["import_batch"], ln


async def _baris(db, lid: str) -> dict:
    return await db.bank_statement_lines.find_one({"id": lid}, {"_id": 0})


async def _kwitansi_baris(db, lid: str) -> list:
    return await db.ar_receipts.find({"bank_line_id": lid}, {"_id": 0}).to_list(10)


async def _kwitansi_pesanan(db, oid: str) -> list:
    return await db.ar_receipts.find({"allocations.order_id": oid, "status": {"$ne": "void"}}, {"_id": 0}).to_list(10)


async def _lapor(klien, siap, oid: str, amount: float = 1_000_000, *, bukti: bool = False) -> dict:
    r = await klien.post(f"/api/sales-orders/{oid}/payment-reports", headers=siap["h_sa"], json={
        "amount": amount, "transfer_date": TGL, "account_id": siap["A"], "method": "transfer",
        "reference_no": f"TRF-LB-F13-{next(_n)}", "note": "uji F1-3"})
    assert r.status_code == 200, r.text
    rep = r.json()
    if bukti:
        r = await klien.post(f"/api/payment-reports/{rep['id']}/attachments", headers=siap["h_sa"],
                             files={"file": ("bukti.pdf", PDF, "application/pdf")})
        assert r.status_code == 200, r.text
        rep["attachments"] = [r.json()]
    return rep


async def _proses_impor(batch: str) -> dict:
    from services.bank_auto_receipt_service import proses_impor
    return await proses_impor(batch, PEMICU)


async def _proses_rekening(rek: str) -> dict:
    from services.bank_auto_receipt_service import proses_rekening
    return await proses_rekening(rek, [KSC], PEMICU)


def _hasil_baris(out: dict, lid: str) -> dict:
    [h] = [x for x in out["rincian"] if x["line_id"] == lid]
    return h


async def _notif(db, jenis: str, **saring) -> list:
    return await db.notifications.find({"type": jenis, **saring}, {"_id": 0}).to_list(200)


# ── Jalur C — kwitansi baru, terverifikasi bank, pesanan dilepas ─────────────────────────────────────────────────────
async def test_jalur_C_kwitansi_terverifikasi_dan_lepas(klien, db, siap):
    so = await _pesan(klien, db, siap)
    kode = await _kode(db, so["id"])
    batch, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {kode} TOKO F13", ref="TRF-C-0001")
    out = await _proses_impor(batch)
    assert (out["kwitansi_otomatis"], out["kartu"], out["nilai_otomatis"]) == (1, 0, 1_000_000), out
    h = _hasil_baris(out, ln["id"])
    assert (h["hasil"], h["jalur"], h["order_id"], h["order_number"], h["released"]) == \
           ("otomatis", "C", so["id"], so["number"], True), h

    [kw] = await _kwitansi_baris(db, ln["id"])
    assert (h["receipt_id"], h["receipt_number"]) == (kw["id"], kw["number"])
    assert (kw["source"], kw["status"], kw["bank_verified"], kw["amount"]) == ("mutasi_bank", "posted", True, 1_000_000)
    assert (kw["reference_no"], kw["account_id"], kw["receipt_date"], kw["method"]) == \
           ("TRF-C-0001", siap["A"], TGL, "transfer")
    assert [(a["order_id"], a["applied"]) for a in kw["allocations"]] == [(so["id"], 1_000_000)]
    assert kw["notes"].startswith("Kwitansi otomatis dari mutasi bank ") and "BCA Penerimaan F13" in kw["notes"]
    assert kw["notes"].endswith(kode), kw["notes"]
    assert kw["created_by_name"] == "Sistem (mutasi bank)"
    assert not (kw.get("variance") or {}).get("needs_decision")

    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["match_type"], cur["matched_txn_id"]) == ("matched", "auto_receipt", kw["cash_txn_id"])
    assert "match_lock" not in cur
    f1 = cur["f1"]
    assert (f1["status"], f1["jalur"], f1["alasan_kode"], f1["pernah_otomatis"]) == ("otomatis", "C", "cocok", True)
    assert (f1["receipt_id"], f1["order_id"], f1["report_id"], f1["dilepas_at"]) == (kw["id"], so["id"], "", "")
    assert f1["dinilai_at"] and f1["alasan"]

    order = await _so(db, so["id"])
    assert order["status"] == "confirmed" and not order.get("pay_hold"), order.get("status")

    [nb] = await _notif(db, BAYAR, recipient_user=siap["sales"]["id"])
    assert nb["body"] == (f"Pembayaran {so['number']} Rp 1.000.000 masuk lewat mutasi bank (kwitansi {kw['number']}); "
                          "pesanan dilepas ke gudang"), nb["body"]
    ringkas = await _notif(db, RINGKASAN, ref={"$regex": f"^f1_impor:{batch}#"})
    penerima = [n["recipient_user"] for n in ringkas]
    assert siap["fin"]["id"] in penerima and len(penerima) == len(set(penerima)), penerima
    assert ringkas[0]["body"].startswith(
        "Impor mutasi BCA Penerimaan F13: 1 kwitansi otomatis (Rp 1.000.000), 0 mutasi berkode perlu dicek")
    assert siap["sales"]["id"] not in penerima      # sales tidak memegang payment_report.decide

    jejak = await db.audit_logs.find_one({"action": "bank_auto_receipt", "entity_id": ln["id"]}, {"_id": 0})
    assert jejak and jejak["actor"] == "Sistem (mutasi bank)"
    assert {k: jejak["after"][k] for k in ("line_id", "receipt_number", "order_number", "jalur", "pemicu")} == \
           {"line_id": ln["id"], "receipt_number": kw["number"], "order_number": so["number"], "jalur": "C",
            "pemicu": PEMICU}

    # layar Rekonsiliasi membawa penanda f1 apa adanya
    r = await klien.get("/api/bank-reconciliation/lines", headers=siap["h"], params={"bank_account_id": siap["A"]})
    assert r.status_code == 200, r.text
    [row] = [x for x in r.json() if x["id"] == ln["id"]]
    assert row["f1"] == f1


async def test_jalur_C_ref_kosong_memakai_kode(klien, db, siap):
    so = await _pesan(klien, db, siap)
    kode = await _kode(db, so["id"])
    batch, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {kode}")
    out = await _proses_impor(batch)
    assert _hasil_baris(out, ln["id"])["hasil"] == "otomatis", out
    [kw] = await _kwitansi_baris(db, ln["id"])
    assert kw["reference_no"] == kode


async def test_dasar_terverifikasi_lepas_sesudah_tautan(klien, db, siap):
    """PT berdasar `terverifikasi`: kwitansi jalur C belum melepas pesanan saat lahir; tautan mutasi membuatnya
    terverifikasi bank → tahan dibuka → dilepas ke gudang (jalur `_link` yang ada)."""
    from services import config_resolver as resolver
    dasar = "finance.tahan_kirim_dasar_bayar"
    await resolver.set_value(dasar, "terverifikasi", scope_type="entity", scope_id=KSC, actor="uji", reason="uji F1-3")
    try:
        so = await _pesan(klien, db, siap)
        batch, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
        h = _hasil_baris(await _proses_impor(batch), ln["id"])
    finally:
        await resolver.clear_layer(dasar, scope_type="entity", scope_id=KSC, actor="uji", reason="pulihkan uji F1-3")
    assert (h["hasil"], h["jalur"], h["released"]) == ("otomatis", "C", True), h
    assert (await _so(db, so["id"]))["status"] == "confirmed"
    [kw] = await _kwitansi_baris(db, ln["id"])
    assert kw["bank_verified"] is True and kw["bank_verified_by"] == "Sistem (mutasi bank)"


async def test_belum_periksa_lepas_menunggu_admin_sales(klien, db, siap):
    """Admin Sales belum "Periksa & lepas": uang masuk membuka tahan tetapi tidak melepas (R4 Lapor Bayar) — sales
    diberi tahu "menunggu Admin Sales"."""
    so = await _pesan(klien, db, siap, periksa=False)
    batch, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    h = _hasil_baris(await _proses_impor(batch), ln["id"])
    assert (h["hasil"], h["jalur"], h["released"]) == ("otomatis", "C", False), h
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and not cur.get("pay_hold")
    [nb] = await _notif(db, BAYAR, ref=f"f1_bayar:{ln['id']}#{siap['sales']['id']}")
    assert nb["body"].endswith(f"(kwitansi {h['receipt_number']}); pesanan menunggu Admin Sales"), nb["body"]


async def test_pesanan_tidak_tertahan_tanpa_notifikasi_sales(klien, db, siap):
    """Notifikasi sales hanya untuk pesanan yang tadinya tertahan bayar: pesanan tempo terkonfirmasi tidak."""
    so = await _pesan(klien, db, siap)
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "confirmed"},   # FIXTURE: sudah dilepas
                                                       "$unset": {"pay_hold": "", "release.waiting": ""}})
    batch, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    h = _hasil_baris(await _proses_impor(batch), ln["id"])
    assert (h["hasil"], h["released"]) == ("otomatis", False), h
    assert await _notif(db, BAYAR, ref={"$regex": f"^f1_bayar:{ln['id']}#"}) == []


# ── Jalur A — kwitansi yang sudah ada ditautkan ──────────────────────────────────────────────────────────────────────
async def test_jalur_A_menautkan_kwitansi_yang_ada(klien, db, siap):
    from services import ar_receipt_service as ars
    so = await _pesan(klien, db, siap)
    kw = await ars.create_receipt({
        "customer_id": so["customer_id"], "amount": 1_000_000, "method": "transfer", "entity_id": KSC,
        "account_id": siap["A"], "receipt_date": TGL, "reference_no": "TRF-A-0001",
        "allocations": [{"order_id": so["id"], "amount": 1_000_000}]}, _aktor(siap["fin"]))
    assert kw["bank_verified"] is False
    batch, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    out = await _proses_impor(batch)
    h = _hasil_baris(out, ln["id"])
    assert (h["hasil"], h["jalur"], h["receipt_id"], h["receipt_number"]) == ("otomatis", "A", kw["id"], kw["number"])
    assert [r["id"] for r in await _kwitansi_pesanan(db, so["id"])] == [kw["id"]]     # tidak ada kwitansi baru
    assert await _kwitansi_baris(db, ln["id"]) == []
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["match_type"], cur["matched_txn_id"]) == ("matched", "auto", kw["cash_txn_id"])
    assert (cur["f1"]["status"], cur["f1"]["jalur"], cur["f1"]["receipt_id"]) == ("otomatis", "A", kw["id"])
    assert (await db.ar_receipts.find_one({"id": kw["id"]}, {"_id": 0}))["bank_verified"] is True


# ── Jalur B — laporan bayar menunggu diterima otomatis ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bukti", [False, True], ids=["tanpa_lampiran", "dengan_lampiran"])
async def test_jalur_B_laporan_diterima_otomatis(klien, db, siap, bukti):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"], bukti=bukti)
    batch, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}", ref="TRF-B-01")
    out = await _proses_impor(batch)
    h = _hasil_baris(out, ln["id"])
    assert (h["hasil"], h["jalur"], h["released"]) == ("otomatis", "B", True), h

    lap = await db.payment_reports.find_one({"id": rep["id"]}, {"_id": 0})
    assert lap["status"] == "diterima" and lap["decided_by_name"] == "Sistem (mutasi bank)"
    catatan = lap["status_history"][-1]["note"]
    assert "Diterima otomatis dari mutasi bank " in catatan and "BCA Penerimaan F13" in catatan, catatan
    [kw] = await _kwitansi_pesanan(db, so["id"])
    assert (kw["payment_report_id"], kw["bank_line_id"], kw["source"]) == (rep["id"], ln["id"], "mutasi_bank")
    assert (lap["receipt_id"], h["receipt_id"]) == (kw["id"], kw["id"])
    assert kw["bank_verified"] is True and kw["amount"] == 1_000_000
    assert bool(kw["proof_url"]) is bukti
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["match_type"]) == ("matched", "auto_receipt")
    assert (cur["f1"]["jalur"], cur["f1"]["report_id"], cur["f1"]["receipt_id"]) == ("B", rep["id"], kw["id"])
    assert (await _so(db, so["id"]))["status"] == "confirmed"
    [nd] = await _notif(db, "lapor_bayar_diterima", ref=f"{rep['id']}#{siap['sales']['id']}")
    assert "otomatis dari mutasi bank" in nd["body"], nd["body"]


async def test_jalur_B_laporan_pecahan_kas_sama_dengan_mutasi(klien, db, siap):
    """Laporan Rp 173.437,5 (tagihan DP pecahan) + mutasi Rp 173.438 → jalur B: kas kwitansi = nominal mutasi (tautan
    cent-tepat), alokasi = nominal laporan; lebih Rp 0,5 diputus aturan pembulatan, tanpa antrean selisih."""
    so = await _pesan(klien, db, siap, "DP50", prd=siap["prd_dp"], total=346_875)
    rep = await _lapor(klien, siap, so["id"], 173_437.5)
    batch, ln = await _impor(db, siap["A"], 173_438, f"TRSF {await _kode(db, so['id'])} DP")
    h = _hasil_baris(await _proses_impor(batch), ln["id"])
    assert (h["hasil"], h["jalur"]) == ("otomatis", "B"), h
    [kw] = await _kwitansi_pesanan(db, so["id"])
    assert (kw["payment_report_id"], kw["amount"], kw["receipt_date"]) == (rep["id"], 173_438, TGL)
    assert [a["applied"] for a in kw["allocations"]] == [173_437.5]
    assert kw["variance"]["direction"] == "rounding" and not kw["variance"]["needs_decision"]
    assert kw["bank_verified"] is True and (await _baris(db, ln["id"]))["status"] == "matched"


# ── Kartu — alasan tertulis, tanpa uang ──────────────────────────────────────────────────────────────────────────────
async def test_kartu_menulis_alasan_tanpa_uang(klien, db, siap):
    so = await _pesan(klien, db, siap)
    kas_awal = await db.cash_transactions.count_documents({})
    batch, ln = await _impor(db, siap["A"], 1_500_000, f"TRSF {await _kode(db, so['id'])}")
    out = await _proses_impor(batch)
    assert (out["kwitansi_otomatis"], out["kartu"], out["nilai_otomatis"]) == (0, 1, 0), out
    h = _hasil_baris(out, ln["id"])
    assert (h["hasil"], h["jalur"], h["alasan_kode"], h["receipt_id"], h["released"]) == \
           ("kartu", "", "nominal_beda", "", False), h
    assert h["alasan"] == "Nominal mutasi Rp 1.500.000 ≠ tagihan Rp 1.000.000 (lebih Rp 500.000)"
    cur = await _baris(db, ln["id"])
    assert cur["status"] == "unmatched" and "match_lock" not in cur
    f1 = cur["f1"]
    assert (f1["status"], f1["alasan_kode"], f1["alasan"]) == ("kartu", "nominal_beda", h["alasan"])
    assert (cur["f1"]["order_id"], cur["f1"]["pernah_otomatis"]) == (so["id"], False)
    assert await _kwitansi_pesanan(db, so["id"]) == [] and await db.cash_transactions.count_documents({}) == kas_awal
    assert (await _so(db, so["id"]))["pay_hold"]
    [nr, *_] = await _notif(db, RINGKASAN, ref=f"f1_impor:{batch}#{siap['fin']['id']}")
    assert nr["body"].startswith(
        "Impor mutasi BCA Penerimaan F13: 0 kwitansi otomatis (Rp 0), 1 mutasi berkode perlu dicek"), nr["body"]
    assert await _notif(db, BAYAR, ref={"$regex": f"^f1_bayar:{ln['id']}#"}) == []


async def test_pengaturan_mati_kartu_tanpa_kwitansi(klien, db, siap):
    """Review Focus 4 — `bank.kwitansi_otomatis_mutasi` mati untuk PT: tidak ada kwitansi; baris berkode tetap kartu
    `otomatis_mati` (mesin menilai, tidak bertindak)."""
    so = await _pesan(klien, db, siap)
    batch, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    r = await klien.put("/api/config/values", headers=siap["h"], json={"items": [{
        "key": "bank.kwitansi_otomatis_mutasi", "value": False, "scope_type": "entity", "scope_id": KSC,
        "reason": "uji F1-3", "effective_from": ""}]})
    assert r.status_code == 200, r.text
    try:
        out = await _proses_impor(batch)
    finally:
        r = await klien.put("/api/config/values", headers=siap["h"], json={"items": [{
            "key": "bank.kwitansi_otomatis_mutasi", "value": True, "scope_type": "entity", "scope_id": KSC,
            "reason": "pulihkan uji F1-3", "effective_from": ""}]})
        assert r.status_code == 200, r.text
    h = _hasil_baris(out, ln["id"])
    assert (h["hasil"], h["alasan_kode"]) == ("kartu", "otomatis_mati"), h
    assert await _kwitansi_pesanan(db, so["id"]) == []
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["f1"]["status"], cur["f1"]["alasan_kode"]) == ("unmatched", "kartu", "otomatis_mati")


async def test_impor_tanpa_kode_tanpa_ringkasan(klien, db, siap):
    batch, ln = await _impor(db, siap["A"], 250_000, "TRSF TOKO TANPA KODE F13")
    out = await _proses_impor(batch)
    assert (out["kwitansi_otomatis"], out["kartu"]) == (0, 0)
    assert _hasil_baris(out, ln["id"])["hasil"] == "lewati"
    assert "f1" not in await _baris(db, ln["id"])
    assert await _notif(db, RINGKASAN, ref={"$regex": f"^f1_impor:{batch}#"}) == []


# ── Review Focus 1 — impor ulang berkas yang sama ────────────────────────────────────────────────────────────────────
async def test_impor_ulang_tidak_ganda(klien, db, siap):
    so = await _pesan(klien, db, siap)
    berkas = [{"nominal": 1_000_000, "berita": f"TRSF {await _kode(db, so['id'])}", "ext": _id("ext")}]
    r1 = await _impor_banyak(siap["A"], berkas)
    r2 = await _impor_banyak(siap["A"], berkas)
    assert (r1["imported"], r2["imported"], r2["skipped"]) == (1, 0, 1)
    await _proses_impor(r1["import_batch"])
    await _proses_impor(r2["import_batch"])
    ulang = await _proses_impor(r1["import_batch"])
    [ln] = await _baris_batch(db, r1["import_batch"])
    assert _hasil_baris(ulang, ln["id"])["hasil"] == "lewati"
    assert len(await _kwitansi_pesanan(db, so["id"])) == 1 and len(await _kwitansi_baris(db, ln["id"])) == 1


# ── Review Focus 2 — dua mutasi berkode sama dalam satu impor ────────────────────────────────────────────────────────
async def test_dua_mutasi_kode_sama_satu_batch(klien, db, siap):
    so = await _pesan(klien, db, siap)
    kode = await _kode(db, so["id"])
    res = await _impor_banyak(siap["A"], [{"nominal": 1_000_000, "berita": f"TRSF {kode} PERTAMA"},
                                          {"nominal": 1_000_000, "berita": f"TRSF {kode} KEDUA"}])
    pertama, kedua = await _baris_batch(db, res["import_batch"])
    out = await _proses_impor(res["import_batch"])
    assert [x["line_id"] for x in out["rincian"]] == [pertama["id"], kedua["id"]]
    assert (out["kwitansi_otomatis"], out["kartu"]) == (1, 1), out
    assert _hasil_baris(out, pertama["id"])["hasil"] == "otomatis"
    h2 = _hasil_baris(out, kedua["id"])
    assert (h2["hasil"], h2["alasan_kode"]) == ("kartu", "sudah_lunas"), h2
    assert len(await _kwitansi_pesanan(db, so["id"])) == 1
    assert (await _baris(db, kedua["id"]))["status"] == "unmatched"


async def test_urutan_tanggal_mutasi_naik(klien, db, siap):
    """Dalam satu batch, baris diproses menurut tanggal mutasi naik — bukan urutan berkas."""
    so = await _pesan(klien, db, siap)
    kode = await _kode(db, so["id"])
    res = await _impor_banyak(siap["A"], [{"nominal": 1_000_000, "berita": f"TRSF {kode} BELAKANGAN", "tgl": TGL},
                                          {"nominal": 1_000_000, "berita": f"TRSF {kode} DULUAN", "tgl": "2026-11-23"}])
    belakangan, duluan = await _baris_batch(db, res["import_batch"])
    out = await _proses_impor(res["import_batch"])
    assert [x["line_id"] for x in out["rincian"]] == [duluan["id"], belakangan["id"]]
    assert _hasil_baris(out, duluan["id"])["hasil"] == "otomatis"
    assert _hasil_baris(out, belakangan["id"])["hasil"] == "kartu"


# ── Review Focus 3 — DP berpecahan ───────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("nominal", [173_438, 173_437])
async def test_dp_pecahan_tanpa_selisih_terbuka(klien, db, siap, nominal):
    from services import payment_variance_service as pvs
    so = await _pesan(klien, db, siap, "DP50", prd=siap["prd_dp"], total=346_875)
    batch, ln = await _impor(db, siap["A"], nominal, f"TRSF {await _kode(db, so['id'])} DP")
    out = await _proses_impor(batch)
    h = _hasil_baris(out, ln["id"])
    assert (h["hasil"], h["jalur"]) == ("otomatis", "C"), h
    [kw] = await _kwitansi_baris(db, ln["id"])
    assert kw["amount"] == nominal and kw["bank_verified"] is True
    assert [a["applied"] for a in kw["allocations"]] == [min(173_437.5, nominal)]
    v = kw["variance"]
    assert v["direction"] == "rounding" and not v["needs_decision"], v
    terbuka = [r for r in await pvs.pending(KSC) if r.get("receipt_id") == kw["id"]]
    assert terbuka == []
    r = await klien.get("/api/finance/desk", headers=siap["h_fin"])
    assert r.status_code == 200, r.text
    q = next(q for q in r.json()["queues"] if q["id"] == "selisih_bayar")
    assert [x for x in q["rows"] if x.get("ref_id") == kw["id"]] == []


# ── Klaim baris — dua proses bersamaan ───────────────────────────────────────────────────────────────────────────────
async def test_proses_baris_bersamaan_satu_kwitansi(klien, db, siap):
    from services.bank_auto_receipt_service import proses_baris
    so = await _pesan(klien, db, siap)
    _, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    a, b = await asyncio.gather(proses_baris(ln, PEMICU), proses_baris(ln, PEMICU))
    assert sorted([a["hasil"], b["hasil"]]) == ["lewati", "otomatis"], (a, b)
    assert len(await _kwitansi_baris(db, ln["id"])) == 1 and len(await _kwitansi_pesanan(db, so["id"])) == 1


async def test_klaim_dipegang_proses_lain_dilewati(klien, db, siap):
    """Baris yang `match_lock`-nya dipegang proses lain (belum basi) tidak disentuh: lewati, tanpa tulisan."""
    from services.bank_auto_receipt_service import proses_baris
    so = await _pesan(klien, db, siap)
    _, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    await db.bank_statement_lines.update_one({"id": ln["id"]}, {"$set": {   # FIXTURE: pencocokan lain sedang berjalan
        "match_lock": "bmatch_lain", "match_lock_at": now_iso()}})
    h = await proses_baris(ln, PEMICU)
    assert (h["hasil"], h["alasan_kode"]) == ("lewati", "sedang_diproses"), h
    cur = await _baris(db, ln["id"])
    assert cur["match_lock"] == "bmatch_lain" and "f1" not in cur and await _kwitansi_baris(db, ln["id"]) == []
    await db.bank_statement_lines.update_one({"id": ln["id"]}, {"$unset": {"match_lock": "", "match_lock_at": ""}})


# ── Pemulihan — kwitansi lahir, tautan belum ─────────────────────────────────────────────────────────────────────────
async def test_pemulihan_kwitansi_tanpa_tautan(klien, db, siap):
    from services import ar_receipt_service as ars
    from services.bank_auto_receipt_service import AKTOR_MUTASI, proses_baris
    so = await _pesan(klien, db, siap)
    _, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    # FIXTURE alur: proses sebelumnya mati sesudah kwitansi tuntas, sebelum tautan
    kw = await ars.create_receipt({
        "customer_id": so["customer_id"], "amount": 1_000_000, "method": "transfer", "entity_id": KSC,
        "account_id": siap["A"], "receipt_date": TGL, "reference_no": "TRF-PULIH",
        "allocations": [{"order_id": so["id"], "amount": 1_000_000}], "source": "mutasi_bank",
        "bank_line_id": ln["id"]}, dict(AKTOR_MUTASI))
    h = await proses_baris(ln, PEMICU)
    assert (h["hasil"], h["jalur"], h["receipt_id"]) == ("otomatis", "C", kw["id"]), h
    assert [r["id"] for r in await _kwitansi_pesanan(db, so["id"])] == [kw["id"]]
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["match_type"], cur["f1"]["receipt_id"]) == ("matched", "auto_receipt", kw["id"])


async def test_kwitansi_kembar_indeks_unik_hanya_menautkan(klien, db, siap, monkeypatch):
    """`DuplicateKeyError` dari `uq_bank_line_receipt` (proses lain sudah melahirkan kwitansi baris ini) → kwitansi
    pemenang ditautkan; tidak ada kwitansi kedua. Database tiruan tidak memasang indeks unik parsial: tabrakan
    ditiru."""
    from services import ar_receipt_service as ars
    from services.bank_auto_receipt_service import proses_baris
    so = await _pesan(klien, db, siap)
    _, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    asli = ars.create_receipt

    async def _kalah(payload, actor):
        await asli(dict(payload), actor)                 # pemenang (proses lain) lebih dulu menyimpan kwitansinya
        raise DuplicateKeyError("E11000 duplicate key error index: uq_bank_line_receipt")
    monkeypatch.setattr(ars, "create_receipt", _kalah)
    h = await proses_baris(ln, PEMICU)
    assert (h["hasil"], h["jalur"]) == ("otomatis", "C"), h
    [kw] = await _kwitansi_baris(db, ln["id"])
    assert h["receipt_id"] == kw["id"] and len(await _kwitansi_pesanan(db, so["id"])) == 1
    assert (await _baris(db, ln["id"]))["status"] == "matched"


async def test_tautan_gagal_sekali_dipulihkan(klien, db, siap, monkeypatch):
    """Kwitansi jalur C sudah tuntas, tautan pertama gagal (kapasitas kas direbut; `_link` mencabut kunci) → pemulihan
    di operasi yang sama mengklaim ulang dan menautkan kwitansi itu: tidak ada kwitansi tanpa tautan, tidak ada
    kwitansi kedua."""
    from services import bank_recon_service as brs
    from services.bank_auto_receipt_service import proses_baris
    so = await _pesan(klien, db, siap)
    _, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    asli, panggil = brs._link, []

    async def _sekali_gagal(line, allocations, actor, match_type, match_kind, op=""):
        panggil.append(op)
        if len(panggil) == 1:   # perilaku `_link` saat kapasitas kas gagal diklaim: kunci dicabut, lalu galat
            await db.bank_statement_lines.update_one({"id": line["id"], "match_lock": op},
                                                     {"$unset": {"match_lock": "", "match_lock_at": ""}})
            raise ValueError("Sisa transaksi buku tidak cukup (baru saja dipakai proses lain / alokasi ganda).")
        return await asli(line, allocations, actor, match_type, match_kind, op=op)
    monkeypatch.setattr(brs, "_link", _sekali_gagal)
    h = await proses_baris(ln, PEMICU)
    assert (h["hasil"], h["jalur"]) == ("otomatis", "C"), h
    assert len(panggil) == 2 and panggil[0] and panggil[1] and panggil[0] != panggil[1]   # diklaim ulang
    [kw] = await _kwitansi_baris(db, ln["id"])
    assert h["receipt_id"] == kw["id"] and kw["bank_verified"] is True
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["match_type"], cur["f1"]["status"]) == ("matched", "auto_receipt", "otomatis")


async def test_tautan_selalu_gagal_kartu_galat(klien, db, siap, monkeypatch):
    from services import bank_recon_service as brs
    from services.bank_auto_receipt_service import proses_baris
    so = await _pesan(klien, db, siap)
    _, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")

    async def _gagal(line, allocations, actor, match_type, match_kind, op=""):
        await db.bank_statement_lines.update_one({"id": line["id"], "match_lock": op},
                                                 {"$unset": {"match_lock": "", "match_lock_at": ""}})
        raise ValueError("Sisa transaksi buku tidak cukup.")
    monkeypatch.setattr(brs, "_link", _gagal)
    h = await proses_baris(ln, PEMICU)
    [kw] = await _kwitansi_baris(db, ln["id"])
    assert (h["hasil"], h["alasan_kode"]) == ("kartu", "galat"), h
    assert h["alasan"] == (f"Mutasi gagal ditautkan otomatis ke kwitansi {kw['number']}: Sisa transaksi buku tidak "
                           "cukup. Cocokkan manual di Rekonsiliasi Bank.")
    cur = await _baris(db, ln["id"])
    assert (cur["status"], cur["f1"]["alasan_kode"]) == ("unmatched", "galat") and "match_lock" not in cur
    monkeypatch.undo()
    # kesempatan berikutnya ("Cocokkan otomatis"): kwitansi baris itu ditautkan, bukan kwitansi kedua
    h = _hasil_baris(await _proses_rekening(siap["A"]), ln["id"])
    assert (h["hasil"], h["receipt_id"]) == ("otomatis", kw["id"]), h
    assert len(await _kwitansi_pesanan(db, so["id"])) == 1


async def test_kwitansi_mutasi_lain_bukan_calon_A(klien, db, siap, monkeypatch):
    """Kwitansi yang lahir dari mutasi L1 (tautannya gagal) milik L1: mutasi kedua L2 berkode & bernominal sama tidak
    menautkannya (kartu "sudah lunas oleh kwitansi … yang belum cocok mutasi"); L1 berikutnya memulihkan kwitansinya."""
    from services import bank_recon_service as brs
    from services.bank_auto_receipt_service import proses_baris
    so = await _pesan(klien, db, siap)
    kode = await _kode(db, so["id"])
    _, l1 = await _impor(db, siap["A"], 1_000_000, f"TRSF {kode} SATU")

    async def _gagal(line, allocations, actor, match_type, match_kind, op=""):
        await db.bank_statement_lines.update_one({"id": line["id"], "match_lock": op},
                                                 {"$unset": {"match_lock": "", "match_lock_at": ""}})
        raise ValueError("Sisa transaksi buku tidak cukup.")
    monkeypatch.setattr(brs, "_link", _gagal)
    assert (await proses_baris(l1, PEMICU))["alasan_kode"] == "galat"
    monkeypatch.undo()
    [kw] = await _kwitansi_baris(db, l1["id"])
    _, l2 = await _impor(db, siap["A"], 1_000_000, f"TRSF {kode} DUA")
    h2 = await proses_baris(l2, PEMICU)
    assert (h2["hasil"], h2["alasan_kode"]) == ("kartu", "sudah_lunas"), h2
    assert h2["alasan"] == f"Pesanan {so['number']} sudah lunas oleh kwitansi {kw['number']} yang belum cocok mutasi"
    h1 = await proses_baris(l1, PEMICU)
    assert (h1["hasil"], h1["receipt_id"]) == ("otomatis", kw["id"]), h1
    assert len(await _kwitansi_pesanan(db, so["id"])) == 1


# ── Review Focus 5 — dilepas lewat "Lepas" biasa / mutasi lama ───────────────────────────────────────────────────────
async def test_lepas_biasa_tidak_diproses_lagi(klien, db, siap):
    from services import bank_recon_service as brs
    so = await _pesan(klien, db, siap)
    batch, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    assert _hasil_baris(await _proses_impor(batch), ln["id"])["hasil"] == "otomatis"
    await brs.unmatch(ln["id"], "Uji Finance F13", [KSC])
    cur = await _baris(db, ln["id"])
    assert cur["status"] == "unmatched"
    assert cur["f1"]["pernah_otomatis"] is True and cur["f1"]["dilepas_at"], cur["f1"]
    assert cur["f1"]["status"] == "otomatis" and cur["f1"]["receipt_id"]
    out = await _proses_rekening(siap["A"])
    assert ln["id"] not in [x["line_id"] for x in out["rincian"]]      # dilewati: tidak disentuh, tidak dirinci
    assert all(x["hasil"] != "lewati" for x in out["rincian"])
    from services.bank_auto_receipt_service import proses_baris
    h = await proses_baris(cur, PEMICU)
    assert (h["hasil"], h["alasan_kode"]) == ("lewati", "pernah_otomatis"), h
    assert len(await _kwitansi_pesanan(db, so["id"])) == 1
    cur = await _baris(db, ln["id"])
    assert cur["status"] == "unmatched" and cur["f1"]["status"] == "otomatis"


async def test_lepas_baris_bukan_f1_tanpa_penanda(klien, db, siap):
    """`_unlink` baris yang tidak pernah disentuh F1 tidak menulis penanda `f1`."""
    from services import ar_receipt_service as ars
    from services import bank_recon_service as brs
    so = await _pesan(klien, db, siap)
    kw = await ars.create_receipt({
        "customer_id": so["customer_id"], "amount": 1_000_000, "method": "transfer", "entity_id": KSC,
        "account_id": siap["A"], "receipt_date": TGL, "reference_no": "TRF-MANUAL",
        "allocations": [{"order_id": so["id"], "amount": 1_000_000}]}, _aktor(siap["fin"]))
    _, ln = await _impor(db, siap["A"], 1_000_000, "TRSF TOKO F13 MANUAL")
    await brs.manual_match(ln["id"], kw["cash_txn_id"], "Uji Finance F13", [KSC])
    await brs.unmatch(ln["id"], "Uji Finance F13", [KSC])
    assert "f1" not in await _baris(db, ln["id"])


async def test_mutasi_lama_tidak_disentuh(klien, db, siap):
    so = await _pesan(klien, db, siap)
    _, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    await db.bank_statement_lines.update_one({"id": ln["id"]}, {"$set": {   # FIXTURE: diimpor sebelum F1 aktif
        "created_at": "2026-01-01T00:00:00+00:00"}})
    out = await _proses_rekening(siap["A"])
    assert ln["id"] not in [x["line_id"] for x in out["rincian"]]
    from services.bank_auto_receipt_service import proses_baris
    h = await proses_baris(await _baris(db, ln["id"]), PEMICU)
    assert (h["hasil"], h["alasan_kode"]) == ("lewati", "sebelum_aktif"), h
    cur = await _baris(db, ln["id"])
    assert cur["status"] == "unmatched" and "f1" not in cur
    assert await _kwitansi_pesanan(db, so["id"]) == []


async def test_proses_rekening_menilai_ulang_kartu(klien, db, siap):
    """Kartu boleh dinilai ulang: laporan yang membuat kartu ditolak → "Cocokkan otomatis" → jalur C. Tanpa ringkasan
    Finance (ringkasan hanya dari impor)."""
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"], 600_000)
    batch, ln = await _impor(db, siap["A"], 1_000_000, f"TRSF {await _kode(db, so['id'])}")
    out = await _proses_impor(batch)
    assert _hasil_baris(out, ln["id"])["alasan_kode"] == "laporan_beda"
    r = await klien.post(f"/api/payment-reports/{rep['id']}/tolak", headers=siap["h_fin"],
                         json={"reason": "Nominal laporan salah ketik"})
    assert r.status_code == 200, r.text
    ringkasan_awal = len(await _notif(db, RINGKASAN))
    out = await _proses_rekening(siap["A"])
    h = _hasil_baris(out, ln["id"])
    assert (h["hasil"], h["jalur"]) == ("otomatis", "C"), h
    assert out["kwitansi_otomatis"] >= 1 and len(await _notif(db, RINGKASAN)) == ringkasan_awal
    assert (await _baris(db, ln["id"]))["f1"]["status"] == "otomatis"


# ── Galat tak terduga → kartu `galat`, batch berlanjut ───────────────────────────────────────────────────────────────
async def test_galat_tak_terduga_jadi_kartu(klien, db, siap, monkeypatch):
    from services import ar_receipt_service as ars
    s1 = await _pesan(klien, db, siap)
    s2 = await _pesan(klien, db, siap)
    res = await _impor_banyak(siap["A"], [{"nominal": 1_000_000, "berita": f"TRSF {await _kode(db, s1['id'])}"},
                                          {"nominal": 1_000_000, "berita": f"TRSF {await _kode(db, s2['id'])}"}])
    l1, l2 = await _baris_batch(db, res["import_batch"])
    asli = ars._post_cash_in
    panggil = []

    async def _kas_gagal(receipt, *a, **kw):
        panggil.append(receipt["id"])
        if len(panggil) == 1:                            # kwitansi pertama mati di tengah (sesudah alokasi & sisip)
            raise RuntimeError("koneksi basis data terputus")
        return await asli(receipt, *a, **kw)
    monkeypatch.setattr(ars, "_post_cash_in", _kas_gagal)
    out = await _proses_impor(res["import_batch"])
    h1, h2 = _hasil_baris(out, l1["id"]), _hasil_baris(out, l2["id"])
    assert (h1["hasil"], h1["alasan_kode"], h1["receipt_id"]) == ("kartu", "galat", ""), h1
    assert h1["alasan"] == "Kwitansi otomatis gagal dibuat: koneksi basis data terputus. Catat manual dari kartu ini."
    assert (h2["hasil"], h2["jalur"]) == ("otomatis", "C"), h2
    # kwitansi setengah jadi dicabut rollback `create_receipt`: tanpa kwitansi, kas, maupun alokasi pesanan
    assert await db.ar_receipts.find_one({"id": panggil[0]}) is None
    assert await _kwitansi_pesanan(db, s1["id"]) == [] and await _kwitansi_baris(db, l1["id"]) == []
    assert await db.cash_transactions.count_documents({"ref_id": panggil[0], "status": {"$ne": "void"}}) == 0
    o1 = await _so(db, s1["id"])
    assert float(o1.get("paid_total") or 0) == 0 and o1["pay_hold"]
    cur = await _baris(db, l1["id"])
    assert (cur["status"], cur["f1"]["status"], cur["f1"]["alasan_kode"]) == ("unmatched", "kartu", "galat")
    assert "match_lock" not in cur
    assert len(await _kwitansi_baris(db, l2["id"])) == 1
