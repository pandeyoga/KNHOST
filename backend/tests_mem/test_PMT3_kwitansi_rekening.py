"""PM-T3 — kwitansi ber-rekening dan ber-referensi; status "terverifikasi bank"; rekonsiliasi per rekening lewat kode
bayar (docs/blueprint/unit/PM-T3.md, uji penerimaan lapis B).

Serah-terima (a): U1–U5, U7–U9, U12–U15. Serah-terima (b): U6, U10, U11, U16 (bagian bawah berkas). U17 (dua
`auto_match` bersamaan) = lapis A `backend/tests/test_bp_PMT3_cocok_bersamaan.py`; U18 = uji jalan layar.

Persiapan (ALUR lewat API kecuali disebut FIXTURE):
  * rekening `ent_ksc`: **A** (BCA 123-456-7890, penerimaan pelanggan, melayani transfer, BAWAAN transfer), **A2**
    (Mandiri 140-00-7777, penerimaan pelanggan, transfer, bukan bawaan), **C** (BCA, hanya `gaji`), **K** (Kas Kecil,
    tunai, bawaan tunai); `ent_kanda`: **B** (BCA, bawaan transfer) — `POST /api/bank-accounts`;
  * pelanggan P "Toko Maju" (`ent_ksc`) = FIXTURE; pesanan S1 sisa Rp 1.500.000, rekening tujuan A, kode bayar
    `KN-7F3K2` = FIXTURE (pesanan + baris `payment_codes` disisip langsung, bentuk hasil PM-T2);
  * kwitansi, impor mutasi, pencocokan otomatis/manual, pelepasan, pembatalan, pengaturan = ALUR lewat API.
  Ambang & toleransi rekonsiliasi bawaan: bobot nominal 40 · tanggal 20 · referensi 25 · nama 15; otomatis ≥ 80;
  usulan ≥ 60; jendela 3 hari; toleransi nominal Rp 0.

Hitung tangan:
  U1  transfer Rp 1.500.000 tanpa rekening → rekening bawaan transfer `ent_ksc` = A (walau A2 juga bank);
      kas masuk Rp 1.500.000 di A → Dr 1-1100 Bank 1.500.000 / Cr 1-1200 Piutang 1.500.000; sisa S1 0.
  U7  mutasi A Rp 1.500.000, tanggal kwitansi + 2 hari, berita "TRSF KN-7F3K2 TOKO MAJU" → kode KN-7F3K2 menunjuk S1
      yang dialokasi kwitansi U1 → skor ≥ ambang otomatis 80 → tertaut; kas `reconciled_amount` 1.500.000 = nominal
      → kwitansi terverifikasi bank.
  U8  mutasi A Rp 1.400.000 berberita kode pesanan kwitansi Rp 1.500.000 → selisih 1.500.000 − 1.400.000 = Rp 100.000
      (> 1 % × 1.400.000 = Rp 14.000 → di luar pita nominal biasa) → tetap layak lewat kode bayar, skor ≥ usulan 60,
      TIDAK tertaut otomatis; alasan "Kode bayar cocok, nominal berbeda Rp 100.000".
  U12 kwitansi transfer berumur 5 dan 1 hari, tunai berumur 9 hari; batas bawaan 3 hari → hanya yang 5 hari.
"""
from __future__ import annotations

import datetime as _dt
import itertools
import uuid

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, jumlah, pt_uji, tutup_periode

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
BASE_REC = "/api/bank-reconciliation"
K_REF = "payment.wajib_nomor_referensi"
K_HARI = "payment.hari_wajar_verifikasi_bank"
K_DASAR = "finance.tahan_kirim_dasar_bayar"
PESAN_PT_LAIN = "Rekening penerima bukan milik PT kwitansi ini."
PESAN_TIDAK_MENERIMA = "Rekening ini tidak bisa menerima pembayaran pelanggan lewat Transfer bank."
PESAN_REF = "Nomor referensi wajib diisi untuk Transfer bank."
PESAN_TIDAK_SESUAI = "Rekening penerima berbeda dari instruksi bayar pesanan. Isi catatan alasannya."
PESAN_BATAL = "Kwitansi sudah terverifikasi bank. Lepaskan pencocokan mutasinya dulu."
_n = itertools.count(1)
SIMPAN: dict = {}


def _id(awal: str) -> str:
    return f"{awal}_pmt3_{uuid.uuid4().hex[:8]}"


def _hari(n: int) -> str:
    """Tanggal ISO `n` hari yang lalu (UTC), dipakai sebagai tanggal kwitansi/mutasi."""
    return (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=n)).isoformat()


async def _rekening(klien, h, **isi) -> str:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, sesi):
    h_kanda = await sesi("admin@kainnusantara.id", entitas=KANDA)
    a = await _rekening(klien, kepala_admin, name="BCA Penerimaan KSC", account_number="123-456-7890",
                        holder_name="PT Kain Suka Cita", default_receiving_methods=["transfer"], entity_id=KSC)
    a2 = await _rekening(klien, kepala_admin, name="Mandiri Penerimaan KSC", bank_name="Mandiri",
                         account_number="140-00-7777", holder_name="PT Kain Suka Cita", entity_id=KSC)
    c = await _rekening(klien, kepala_admin, name="BCA Gaji KSC", account_number="555-000-1111",
                        holder_name="PT Kain Suka Cita", purposes=["gaji"], entity_id=KSC)
    k = await _rekening(klien, kepala_admin, name="Kas Kecil KSC", account_type="cash", bank_name="",
                        payment_method_codes=["cash"], default_receiving_methods=["cash"], entity_id=KSC)
    b = await _rekening(klien, h_kanda, name="BCA Penerimaan Kanda", account_number="987-654-3210",
                        holder_name="CV Kanda", default_receiving_methods=["transfer"], entity_id=KANDA)
    pel = {}
    for ent in (KSC, KANDA):   # FIXTURE: pelanggan "Toko Maju" per PT
        cus = _id("cus")
        await db.customers.insert_one({"id": cus, "name": "Toko Maju", "entity_id": ent, "status": "active"})
        pel[ent] = cus
    return {"A": a, "A2": a2, "C": c, "K": k, "B": b, "P": pel[KSC], "P_kanda": pel[KANDA], "h": kepala_admin,
            "h_kanda": h_kanda}


async def _pesanan(db, siap, *, sisa: float = 1_500_000, rek: str = "", kode: str = "", ent: str = KSC,
                   cus: str = "", term: str = "NET30") -> dict:
    """FIXTURE: pesanan terbuka bersisa `sisa` (belum dibayar), rekening tujuan `rek`, kode bayar `kode` (PM-T2)."""
    i = next(_n)
    so = {"id": _id("so"), "number": f"SO-PMT3-{i}", "entity_id": ent, "customer_id": cus or siap["P"],
          "customer_name": "Toko Maju", "status": "confirmed", "grand_total": float(sisa), "payments": [],
          "paid_total": 0, "payment_status": "unpaid", "payment_term_code": term, "created_at": now_iso(),
          "payment_method_code": "transfer" if rek else "", "receiving_account_id": rek,
          "receiving_account": {}, "payment_code": kode}
    await db.sales_orders.insert_one(dict(so))
    if kode:
        await db.payment_codes.insert_one({
            "id": _id("pyc"), "code": kode, "entity_id": ent, "order_id": so["id"], "order_number": so["number"],
            "customer_id": so["customer_id"], "plan_id": "", "line_id": "", "order_level": True, "percent": 100.0,
            "amount": float(sisa), "due_date": "", "status": "aktif", "created_at": now_iso(),
            "updated_at": now_iso()})
    return so


async def _kwitansi(klien, h, so: dict, amount: float, **isi):
    body = {"customer_id": so["customer_id"], "amount": amount, "method": "transfer", "entity_id": so["entity_id"],
            "allocations": [{"order_id": so["id"], "amount": amount}], "notes": "uji PM-T3", **isi}
    return await klien.post("/api/ar-receipts", headers=h, json=body)


async def _impor(klien, h, rek: str, tanggal: str, nominal: float, berita: str, ref: str = "") -> str:
    eid = _id("ext")
    r = await klien.post(f"{BASE_REC}/import", headers=h, json={"bank_account_id": rek, "lines": [{
        "stmt_date": tanggal[:10], "amount": nominal, "direction": "in", "description": berita, "ref": ref,
        "external_id": eid}]})
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1, r.json()
    from db import db as _db
    return (await _db.bank_statement_lines.find_one({"external_id": eid}, {"_id": 0}))["id"]


async def _setel(klien, h, key, value, ent=KSC):
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": key, "value": value, "scope_type": "entity", "scope_id": ent, "reason": "uji PM-T3"}]})
    assert r.status_code == 200, r.text


# ═════════════════════════════════ serah-terima (a) ═════════════════════════════════════════════════════════════
# ── U1–U5: rekening, referensi, instruksi bayar di kwitansi ─────────────────────────────────────────────────────────
async def test_PMT3_U1_transfer_tanpa_rekening_memakai_bawaan_pt(klien, db, siap):
    s1 = await _pesanan(db, siap, rek=siap["A"], kode="KN-7F3K2")
    r = await _kwitansi(klien, siap["h"], s1, 1_500_000, receipt_date=_hari(2))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["account_id"] == siap["A"]
    assert j["account_snapshot"] == {"name": "BCA Penerimaan KSC", "bank_name": "BCA",
                                     "account_number": "123-456-7890"}
    assert j["bank_verified"] is False and j["instruction_mismatch"] is False
    assert j["payment_method_code"] == "transfer" and j["method"] == "transfer"
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": j["id"]}, {"_id": 0})
    assert kas["account_id"] == siap["A"] and kas["gl_status"] == "posted"
    assert kas["counterparty_name"] == "Toko Maju"
    assert "KN-7F3K2" in kas["description"]
    so = await db.sales_orders.find_one({"id": s1["id"]}, {"_id": 0})
    assert round(sum(p["amount"] for p in so["payments"]), 2) == 1_500_000
    SIMPAN.update(u1=j["id"], s1=s1, kas_u1=kas["id"])


async def test_PMT3_U2_rekening_pt_lain_ditolak_tanpa_tulisan(klien, db, siap):
    so = await _pesanan(db, siap, rek=siap["A"])
    n_rc = await jumlah("ar_receipts", {})
    r = await _kwitansi(klien, siap["h"], so, 1_500_000, account_id=siap["B"])
    assert (r.status_code, r.json().get("detail")) == (400, PESAN_PT_LAIN), r.text
    assert await jumlah("ar_receipts", {}) == n_rc
    assert (await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0}))["payments"] == []


async def test_PMT3_U3_rekening_tidak_bisa_ditentukan_atau_bukan_penerimaan(klien, db, siap):
    from fastapi import HTTPException
    from services import ar_receipt_service as ars
    # PT uji ketiga: dua rekening bank tanpa bawaan (FIXTURE, rekening lama tanpa field PM-T1 → tidak ada bawaan
    # karena bukan rekening tunggal). Dipanggil lewat layanan (PT uji di luar penugasan akun seed).
    eid = await pt_uji("PMT3")
    for i in (1, 2):
        await db.bank_accounts.insert_one({"id": f"rek_pmt3_{i}", "name": f"Bank {i} Uji PMT3", "account_type": "bank",
                                           "cash_type": "kas_besar", "entity_id": eid, "is_active": True,
                                           "bank_name": "BCA", "account_number": f"77{i}", "created_at": now_iso()})
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": "Toko PT Ketiga", "entity_id": eid, "status": "active"})
    so = await _pesanan(db, siap, ent=eid, cus=cus)
    n_rc, n_kas = await jumlah("ar_receipts", {}), await jumlah("cash_transactions", {})
    with pytest.raises(HTTPException) as e:
        await ars.create_receipt({"customer_id": cus, "amount": 500_000, "method": "transfer", "entity_id": eid,
                                  "allocations": [{"order_id": so["id"], "amount": 500_000}]}, AKTOR_UJI)
    assert e.value.status_code == 409 and str(e.value.detail).startswith("Pilih rekening kas/bank"), e.value.detail
    assert (await jumlah("ar_receipts", {}), await jumlah("cash_transactions", {})) == (n_rc, n_kas)
    assert (await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0}))["payments"] == []
    # Rekening C milik ent_ksc tetapi hanya untuk gaji → 400.
    so2 = await _pesanan(db, siap)
    r = await _kwitansi(klien, siap["h"], so2, 500_000, account_id=siap["C"])
    assert (r.status_code, r.json().get("detail")) == (400, PESAN_TIDAK_MENERIMA), r.text
    assert (await db.sales_orders.find_one({"id": so2["id"]}, {"_id": 0}))["payments"] == []


async def test_PMT3_U4_referensi_wajib_per_pt(klien, db, siap):
    await _setel(klien, siap["h"], K_REF, True, KSC)
    try:
        so = await _pesanan(db, siap)
        n_rc = await jumlah("ar_receipts", {})
        r = await _kwitansi(klien, siap["h"], so, 1_234_000)
        assert (r.status_code, r.json().get("detail")) == (400, PESAN_REF), r.text
        assert await jumlah("ar_receipts", {}) == n_rc
        r = await _kwitansi(klien, siap["h"], so, 1_234_000, reference_no="TRX-998877")
        assert r.status_code == 200, r.text
        assert r.json()["reference_no"] == "TRX-998877"
        kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": r.json()["id"]}, {"_id": 0})
        assert "TRX-998877" in kas["description"]
        # PT lain tidak ikut berubah: ent_kanda tanpa referensi → 200.
        so_k = await _pesanan(db, siap, ent=KANDA, cus=siap["P_kanda"])
        r = await _kwitansi(klien, siap["h_kanda"], so_k, 1_234_000)
        assert r.status_code == 200, r.text
        assert r.json()["account_id"] == siap["B"]
    finally:
        await _setel(klien, siap["h"], K_REF, False, KSC)


async def test_PMT3_U5_rekening_beda_instruksi_wajib_catatan(klien, db, siap):
    so = await _pesanan(db, siap, sisa=1_111_000, rek=siap["A"])
    n_rc = await jumlah("ar_receipts", {})
    r = await _kwitansi(klien, siap["h"], so, 1_111_000, account_id=siap["A2"])
    assert (r.status_code, r.json().get("detail")) == (400, PESAN_TIDAK_SESUAI), r.text
    assert await jumlah("ar_receipts", {}) == n_rc
    r = await _kwitansi(klien, siap["h"], so, 1_111_000, account_id=siap["A2"], mismatch_note="Pelanggan salah transfer")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["instruction_mismatch"] is True and j["mismatch_note"] == "Pelanggan salah transfer"
    assert j["account_id"] == siap["A2"]
    assert [m["order_id"] for m in j["instruction_mismatch_orders"]] == [so["id"]]


# ── U7–U9: kode bayar di rekonsiliasi, status terverifikasi bank ───────────────────────────────────────────────────
async def test_PMT3_U7_kode_bayar_mencocokkan_otomatis(klien, db, siap):
    lid = await _impor(klien, siap["h"], siap["A"], _hari(0), 1_500_000, "TRSF KN-7F3K2 TOKO MAJU")
    ln = await db.bank_statement_lines.find_one({"id": lid}, {"_id": 0})
    assert [(h["code"], h["order_id"]) for h in ln["pay_code_hits"]] == [("KN-7F3K2", SIMPAN["s1"]["id"])]
    r = await klien.post(f"{BASE_REC}/auto-match", headers=siap["h"], json={"bank_account_id": siap["A"]})
    assert r.status_code == 200, r.text
    assert r.json()["matched"] == 1, r.json()
    ln = await db.bank_statement_lines.find_one({"id": lid}, {"_id": 0})
    assert ln["status"] == "matched" and ln["matched_txn_id"] == SIMPAN["kas_u1"]
    assert any("Kode bayar KN-7F3K2" in e["label"] for e in ln["score_explain"]), ln["score_explain"]
    rc = await db.ar_receipts.find_one({"id": SIMPAN["u1"]}, {"_id": 0})
    assert rc["bank_verified"] is True and rc["bank_line_ids"] == [lid]
    assert rc["bank_verified_at"] and rc["bank_verified_by"]
    SIMPAN["l7"] = lid


async def test_PMT3_contoh_angka_U1_ke_U7(db, siap):
    """Contoh angka laporan (`00` §9): kwitansi U1 → kas ber-rekening A → jurnal → mutasi tertaut (U7) → saldo rekening.

    Hitung tangan: kas U1 Rp 1.500.000 di A (Dr 1-1100 Bank 1.500.000; Cr 1.500.000 ke pelanggan — pesanan fixture belum
    dikirim → uang muka 2-1400 / piutang 1-1200 menurut ruang piutang pesanan, total kredit = 1.500.000). Saldo rekening A
    sebelum U8 = saldo awal 0 + U1 1.500.000 + U4 1.234.000 = 2.734.000; saldo terekonsiliasi = 1.500.000 (hanya U1
    yang cocok dengan mutasi)."""
    from services import bank_service
    kas = await db.cash_transactions.find_one({"id": SIMPAN["kas_u1"]}, {"_id": 0})
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas["id"],
                                            "status": {"$ne": "void"}}, {"_id": 0})
    baris = [(b["account_code"], round(b.get("debit", 0), 2), round(b.get("credit", 0), 2)) for b in je["lines"]]
    assert ("1-1100", 1_500_000, 0) in baris
    assert round(sum(c for _, _, c in baris), 2) == 1_500_000 and je["entity_id"] == KSC
    led = await bank_service.account_ledger(siap["A"])
    assert led["balance"] == 2_734_000 and led["reconciled_balance"] == 1_500_000
    SIMPAN["contoh"] = {"jurnal": baris, "saldo": led["balance"], "terekonsiliasi": led["reconciled_balance"]}
    print("CONTOH", SIMPAN["contoh"])


async def test_PMT3_U8_kode_bayar_nominal_berbeda_hanya_usulan(klien, db, siap):
    so = await _pesanan(db, siap, rek=siap["A"], kode="KN-8H4M3")
    r = await _kwitansi(klien, siap["h"], so, 1_500_000)
    assert r.status_code == 200, r.text
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": r.json()["id"]}, {"_id": 0})
    lid = await _impor(klien, siap["h"], siap["A"], _hari(0), 1_400_000, "TRSF KN-8H4M3 TOKO MAJU")
    r = await klien.post(f"{BASE_REC}/auto-match", headers=siap["h"], json={"bank_account_id": siap["A"]})
    assert r.status_code == 200, r.text
    ln = await db.bank_statement_lines.find_one({"id": lid}, {"_id": 0})
    assert ln["status"] == "unmatched"
    top = ln["suggestions"][0]
    assert top["id"] == kas["id"]
    assert any("nominal berbeda Rp 100.000" in e["label"] for e in top["explain"]), top["explain"]
    assert top["score"] >= 60
    rc = await db.ar_receipts.find_one({"id": kas["ref_id"]}, {"_id": 0})
    assert rc["bank_verified"] is False
    # Kandidat (modal pencocokan) memuat pasangan yang sama dengan alasan yang sama.
    r = await klien.get(f"{BASE_REC}/lines/{lid}/candidates", headers=siap["h"])
    assert r.status_code == 200, r.text
    assert r.json()["line"]["pay_code_hits"][0]["code"] == "KN-8H4M3"
    assert r.json()["candidates"][0]["id"] == kas["id"]


async def test_PMT3_U9_lepas_mengembalikan_status_dan_batal_terverifikasi_ditolak(klien, db, siap):
    # Fixture pertama (U7): lepas pencocokan → kwitansi tidak lagi terverifikasi.
    r = await klien.post(f"{BASE_REC}/lines/{SIMPAN['l7']}/unmatch", headers=siap["h"])
    assert r.status_code == 200, r.text
    rc = await db.ar_receipts.find_one({"id": SIMPAN["u1"]}, {"_id": 0})
    assert rc["bank_verified"] is False and rc["bank_line_ids"] == [] and rc["bank_verified_at"] == ""
    # Fixture kedua: cocok manual dulu, lalu batal kwitansi sebelum dilepas → 409; sesudah dilepas → boleh.
    so = await _pesanan(db, siap, sisa=1_350_000, rek=siap["A"], kode="KN-9J5N4")
    r = await _kwitansi(klien, siap["h"], so, 1_350_000)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": rid}, {"_id": 0})
    lid = await _impor(klien, siap["h"], siap["A"], _hari(0), 1_350_000, "TRSF KN-9J5N4 TOKO MAJU")
    r = await klien.post(f"{BASE_REC}/lines/{lid}/match", headers=siap["h"], json={"txn_id": kas["id"]})
    assert r.status_code == 200, r.text
    assert (await db.ar_receipts.find_one({"id": rid}, {"_id": 0}))["bank_verified"] is True
    r = await klien.post(f"/api/ar-receipts/{rid}/void", headers=siap["h"], params={"reason": "uji PM-T3"})
    assert (r.status_code, r.json().get("detail")) == (409, PESAN_BATAL), r.text
    rc = await db.ar_receipts.find_one({"id": rid}, {"_id": 0})
    assert rc["status"] == "posted" and not rc.get("void_intent")
    r = await klien.post(f"{BASE_REC}/lines/{lid}/unmatch", headers=siap["h"])
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/ar-receipts/{rid}/void", headers=siap["h"], params={"reason": "uji PM-T3"})
    assert r.status_code == 200, r.text


# ── U12: saringan "belum terverifikasi" ─────────────────────────────────────────────────────────────────────────────
async def test_PMT3_U12_daftar_belum_terverifikasi_memakai_batas_bawaan(klien, db, siap):
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": "Toko Umur", "entity_id": KSC, "status": "active"})
    dibuat = {}
    for label, hari, cara, nominal in (("t5", 5, "transfer", 210_000), ("t1", 1, "transfer", 220_000),
                                       ("c9", 9, "cash", 230_000)):
        so = await _pesanan(db, siap, sisa=nominal, cus=cus)
        r = await _kwitansi(klien, siap["h"], so, nominal, method=cara, receipt_date=_hari(hari))
        assert r.status_code == 200, r.text
        dibuat[label] = r.json()["id"]
    # `?bank_verified=false&older_than_days=` (tanpa nilai → batas bawaan 3 hari).
    r = await klien.get("/api/ar-receipts", headers=siap["h"],
                        params={"customer_id": cus, "bank_verified": "false", "older_than_days": ""})
    assert r.status_code == 200, r.text
    assert str(r.request.url).endswith("older_than_days=") or "older_than_days=&" in str(r.request.url)
    assert [x["id"] for x in r.json()] == [dibuat["t5"]]
    # Bentuk berhalaman memakai saringan yang sama.
    r = await klien.get("/api/ar-receipts", headers=siap["h"], params={
        "customer_id": cus, "bank_verified": "false", "older_than_days": "", "page": 1, "page_size": 10})
    assert r.status_code == 200, r.text
    assert [x["id"] for x in r.json()["items"]] == [dibuat["t5"]] and r.json()["total"] == 1
    # Nilai eksplisit 0 hari → transfer 1 dan 5 hari; tunai tetap tidak pernah masuk daftar.
    r = await klien.get("/api/ar-receipts", headers=siap["h"],
                        params={"customer_id": cus, "bank_verified": "false", "older_than_days": "0"})
    assert sorted(x["id"] for x in r.json()) == sorted([dibuat["t5"], dibuat["t1"]])
    r = await klien.get("/api/ar-receipts", headers=siap["h"], params={"customer_id": cus, "method": "tunai"})
    assert [x["id"] for x in r.json()] == [dibuat["c9"]]


# ── U13: periode tertutup; jurnal gagal lalu diulang ──────────────────────────────────────────────────────────────
async def test_PMT3_U13_periode_tertutup_lalu_jurnal_gagal_diulang(klien, db, siap, paksa_jurnal_gagal):
    so = await _pesanan(db, siap, sisa=1_313_000, rek=siap["A"])
    awal = (await tutup_periode(KSC, "2026-09"))
    try:
        n = (await jumlah("ar_receipts", {}), await jumlah("cash_transactions", {}))
        r = await _kwitansi(klien, siap["h"], so, 1_313_000, receipt_date="2026-09-15T03:00:00+00:00")
        assert r.status_code == 409, r.text
        assert (await jumlah("ar_receipts", {}), await jumlah("cash_transactions", {})) == n
        assert (await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0}))["payments"] == []
    finally:
        await db.period_closings.delete_one({"id": awal["id"]})
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="cash_transaction") as gagal:
        r = await _kwitansi(klien, siap["h"], so, 1_313_000)
    assert r.status_code == 200, r.text
    assert gagal, "jurnal kas tidak dipaksa gagal"
    rid = r.json()["id"]
    assert r.json()["gl_status"] == "failed"
    r = await klien.post(f"/api/ar-receipts/{rid}/repost", headers=siap["h"])
    assert r.status_code == 200, r.text
    assert r.json()["gl_status"] == "posted"
    kas = await db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": rid}, {"_id": 0}).to_list(None)
    assert len(kas) == 1 and kas[0]["account_id"] == siap["A"]
    je = await db.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": kas[0]["id"],
                                                   "status": {"$ne": "void"}})
    assert je == 1


# ── U14: izin ────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PMT3_U14_izin_kwitansi(klien, db, siap, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong,
                                      peran_sopir):
    so = await _pesanan(db, siap, sisa=1_414_000, rek=siap["A"])
    rid = await peran_tanpa_acuan({"ar_receipt": ["create", "view"]})
    h = await sesi(await akun(rid))
    r = await _kwitansi(klien, h, so, 1_414_000)
    assert r.status_code == 200, r.text
    assert r.json()["account_id"] == siap["A"]
    for peran in (await peran_manajer_kosong(), peran_sopir):
        h = await sesi(await akun(peran))
        r = await _kwitansi(klien, h, so, 1_000)
        assert r.status_code == 403, (peran, r.text)


# ── U15: tiga kunci pengaturan ──────────────────────────────────────────────────────────────────────────────────
async def test_PMT3_U15_putaran_tiga_kunci(klien, kepala_admin):
    from test_KFT8_putaran_pengaturan import putaran
    for kunci in (K_REF, K_HARI, K_DASAR):
        gagal = await putaran(klien, kepala_admin, kunci)
        assert not gagal, "\n".join(gagal)


async def test_PMT3_cetak_kwitansi_memuat_cara_bayar_rekening_referensi(db, siap):
    from services import pdf_resolvers
    rc = await db.ar_receipts.find_one({"reference_no": "TRX-998877"}, {"_id": 0})
    out = await pdf_resolvers.resolve_ar_receipt(rc, db)
    meta = {m["label"]: m["value"] for m in out["meta"]}
    assert meta["Cara bayar"] == "Transfer bank"
    assert meta["Rekening"] == "BCA 123-456-7890 (BCA Penerimaan KSC)"
    assert meta["No. referensi"] == "TRX-998877"
    # Kwitansi lama (tanpa field PM-T3) dicetak seperti dulu — isi yang ditandatangani tidak berubah.
    lama = {"number": "AR-LAMA", "method": "transfer", "amount": 1000, "applied_total": 1000, "unapplied_amount": 0,
            "customer_name": "X", "allocations": []}
    labels = [m["label"] for m in (await pdf_resolvers.resolve_ar_receipt(lama, db))["meta"]]
    assert labels == ["Metode", "Jumlah Diterima", "Dialokasikan", "Sisa/Deposit"]


# ═════════════════════════════════ serah-terima (b) ═════════════════════════════════════════════════════════════
# ── U6: kandidat hanya kas rekening mutasi ──────────────────────────────────────────────────────────────────────
async def test_PMT3_U6_kandidat_mutasi_hanya_kas_rekening_itu(klien, db, siap):
    # Kas U1 (rekening A) sudah dilepas di U9 → belum cocok lagi. Mutasi Rp 1.500.000 di A2 dan di A (tanpa kode bayar).
    l_a2 = await _impor(klien, siap["h"], siap["A2"], _hari(0), 1_500_000, "SETORAN TOKO MAJU")
    l_a = await _impor(klien, siap["h"], siap["A"], _hari(0), 1_500_000, "SETORAN TOKO MAJU")
    r = await klien.get(f"{BASE_REC}/lines/{l_a2}/candidates", headers=siap["h"], params={"limit": 50})
    assert r.status_code == 200, r.text
    assert SIMPAN["kas_u1"] not in [c["id"] for c in r.json()["candidates"]]
    r = await klien.get(f"{BASE_REC}/lines/{l_a}/candidates", headers=siap["h"], params={"limit": 50})
    assert SIMPAN["kas_u1"] in [c["id"] for c in r.json()["candidates"]]
    # Pencocokan manual ke rekening lain ditolak dengan pesan yang sama seperti dulu (validator tunggal).
    r = await klien.post(f"{BASE_REC}/lines/{l_a2}/match", headers=siap["h"], json={"txn_id": SIMPAN["kas_u1"]})
    assert r.status_code == 400 and "bukan milik buku rekening mutasi ini" in r.json()["detail"], r.text


# ── U10: kas lama tanpa rekening hanya untuk rekening tunggal PT-nya ───────────────────────────────────────────
async def test_PMT3_U10_kas_lama_tanpa_rekening_hanya_di_rekening_tunggal(klien, db, siap):
    # FIXTURE — kas lama (sebelum PK-20) tanpa `account_id`, kas besar, Rp 1.212.000: satu di ent_ksc (tiga rekening
    # bank: A, A2, C → tidak ada rekening tunggal), satu di ent_kanda (satu rekening bank: B).
    for kid, ent in (("kas_pmt3_lama_ksc", KSC), ("kas_pmt3_lama_kanda", KANDA)):
        await db.cash_transactions.insert_one({
            "id": kid, "number": f"CASH-LAMA-{ent}", "cash_type": "kas_besar", "direction": "in",
            "amount": 1_212_000.0, "category": "penagihan", "description": "Penerimaan lama Toko Maju",
            "entity_id": ent, "ref_type": "ar_receipt", "ref_id": f"arc_lama_{ent}", "txn_date": _hari(0),
            "status": "posted", "gl_status": "posted", "reconciled_amount": 0.0, "created_at": now_iso()})
    hasil = {}
    for kunci, rek, h in (("A", siap["A"], siap["h"]), ("A2", siap["A2"], siap["h"]), ("B", siap["B"], siap["h_kanda"])):
        lid = await _impor(klien, h, rek, _hari(0), 1_212_000, f"SETORAN LAMA {kunci}")
        r = await klien.get(f"{BASE_REC}/lines/{lid}/candidates", headers=h, params={"limit": 50})
        assert r.status_code == 200, r.text
        hasil[kunci] = {c["id"] for c in r.json()["candidates"]}
    assert "kas_pmt3_lama_ksc" not in hasil["A"] | hasil["A2"]
    assert "kas_pmt3_lama_kanda" not in hasil["A"] | hasil["A2"]
    assert "kas_pmt3_lama_kanda" in hasil["B"]
    assert "kas_pmt3_lama_ksc" not in hasil["B"]   # dulu ikut tampil lintas PT (cakupan pengguna, bukan PT rekening)


# ── U11: dasar tahan-kirim ──────────────────────────────────────────────────────────────────────────────────────
async def test_PMT3_U11_tahan_kirim_menunggu_verifikasi_bank(klien, db, siap):
    from fastapi import HTTPException
    from services import loading_check_service as lcs
    await _setel(klien, siap["h"], K_DASAR, "terverifikasi", KSC)
    try:
        # Hitung tangan: CBD (DP 100 %) Rp 2.000.000 → wajib Rp 2.000.000; kwitansi transfer Rp 2.000.000 tercatat
        # tetapi belum cocok mutasi → terbayar terverifikasi Rp 0 → kurang Rp 2.000.000.
        so = await _pesanan(db, siap, sisa=2_000_000, rek=siap["A"], kode="KN-6P7Q8", term="CBD")
        r = await _kwitansi(klien, siap["h"], so, 2_000_000)
        assert r.status_code == 200, r.text
        kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": r.json()["id"]}, {"_id": 0})
        with pytest.raises(HTTPException) as e:
            await lcs.dispatch_guard(so["id"])
        assert e.value.status_code == 409 and "kurang Rp 2.000.000" in e.value.detail, e.value.detail
        lid = await _impor(klien, siap["h"], siap["A"], _hari(0), 2_000_000, "TRSF KN-6P7Q8 TOKO MAJU")
        r = await klien.post(f"{BASE_REC}/lines/{lid}/match", headers=siap["h"], json={"txn_id": kas["id"]})
        assert r.status_code == 200, r.text
        await lcs.dispatch_guard(so["id"])   # lolos
        # PT lain (dasar bawaan "tercatat"): pesanan CBD serupa lolos tanpa pencocokan.
        so_k = await _pesanan(db, siap, sisa=2_000_000, ent=KANDA, cus=siap["P_kanda"], term="CBD")
        r = await _kwitansi(klien, siap["h_kanda"], so_k, 2_000_000)
        assert r.status_code == 200, r.text
        await lcs.dispatch_guard(so_k["id"])
    finally:
        await _setel(klien, siap["h"], K_DASAR, "tercatat", KSC)


async def test_PMT3_U11b_tunai_dihitung_terbayar_pada_dasar_terverifikasi(klien, db, siap):
    from services import dispatch_payment_gate as gate
    await _setel(klien, siap["h"], K_DASAR, "terverifikasi", KSC)
    try:
        so = await _pesanan(db, siap, sisa=750_000, term="CBD")
        r = await _kwitansi(klien, siap["h"], so, 750_000, method="cash")
        assert r.status_code == 200, r.text
        assert r.json()["account_id"] == siap["K"]
        st = await gate.evaluate(await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0}))
        assert st["basis"] == "terverifikasi" and st["paid"] == 750_000 and not st["blocked"], st
    finally:
        await _setel(klien, siap["h"], K_DASAR, "tercatat", KSC)


# ── U16: skrip isi-ulang rekening kas kwitansi lama ───────────────────────────────────────────────────────────
async def test_PMT3_U16_isi_rekening_kwitansi_lama(db, siap, capsys):
    import importlib.util
    from pathlib import Path
    from services import ar_receipt_service as ars
    # FIXTURE — kwitansi + kas lama tanpa rekening: ent_kanda (rekening bank tunggal B) dan ent_ksc (bank ganda).
    for ent in (KANDA, KSC):
        rid, kid = f"arc_pmt3_u16_{ent}", f"kas_pmt3_u16_{ent}"
        await db.ar_receipts.insert_one({"id": rid, "number": f"AR-U16-{ent}", "entity_id": ent, "amount": 300_000,
                                         "method": "transfer", "status": "posted", "cash_txn_id": kid,
                                         "customer_id": "cus_x", "receipt_date": _hari(30)})
        await db.cash_transactions.insert_one({
            "id": kid, "number": f"CASH-U16-{ent}", "cash_type": "kas_besar", "direction": "in", "amount": 300_000.0,
            "entity_id": ent, "ref_type": "ar_receipt", "ref_id": rid, "status": "posted", "txn_date": _hari(30),
            "created_at": now_iso()})
    hasil = await ars.isi_rekening_kwitansi_lama(tulis=True)
    diisi = {r["cash_id"]: r for r in hasil["diisi"]}
    assert diisi["kas_pmt3_u16_ent_kanda"]["account_id"] == siap["B"]
    assert "kas_pmt3_u16_ent_ksc" in {r["cash_id"] for r in hasil["diputus_orang"]}
    kas_k = await db.cash_transactions.find_one({"id": "kas_pmt3_u16_ent_kanda"}, {"_id": 0})
    rc_k = await db.ar_receipts.find_one({"id": "arc_pmt3_u16_ent_kanda"}, {"_id": 0})
    assert kas_k["account_id"] == siap["B"] and rc_k["account_id"] == siap["B"]
    assert rc_k["account_snapshot"]["account_number"] == "987-654-3210"
    kas_s = await db.cash_transactions.find_one({"id": "kas_pmt3_u16_ent_ksc"}, {"_id": 0})
    assert not kas_s.get("account_id")
    # Putaran kedua: tidak ada perubahan; kas PT ganda tetap tercantum.
    kedua = await ars.isi_rekening_kwitansi_lama(tulis=True)
    assert kedua["diubah"] == 0 and "kas_pmt3_u16_ent_kanda" not in {r["cash_id"] for r in kedua["diisi"]}
    assert "kas_pmt3_u16_ent_ksc" in {r["cash_id"] for r in kedua["diputus_orang"]}
    # Skrip: bawaan = lapor saja (tidak menulis), keluaran menyebut kas yang perlu diputus orang.
    await db.cash_transactions.update_one({"id": "kas_pmt3_u16_ent_kanda"}, {"$set": {"account_id": ""}})
    spec = importlib.util.spec_from_file_location(
        "pmt3_isi", Path(__file__).resolve().parents[2] / "scripts" / "backfill_receipt_accounts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert await mod.jalankan(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "CASH-U16-ent_ksc" in out and "Mode lapor" in out
    assert not (await db.cash_transactions.find_one({"id": "kas_pmt3_u16_ent_kanda"}, {"_id": 0})).get("account_id")


# ── Layar rekonsiliasi: lencana kode bayar & "Catat kwitansi dari mutasi ini" ───────────────────────────────────
async def test_PMT3_daftar_mutasi_memuat_kode_bayar_dan_tanda_kwitansi(klien, db, siap):
    so = await _pesanan(db, siap, sisa=990_000, rek=siap["A"], kode="KN-5R6S7")
    lid = await _impor(klien, siap["h"], siap["A"], _hari(0), 990_000, "TRSF KN5R6S7 TOKO MAJU")
    r = await klien.get(f"{BASE_REC}/lines", headers=siap["h"], params={"bank_account_id": siap["A"]})
    assert r.status_code == 200, r.text
    ln = next(x for x in r.json() if x["id"] == lid)
    hit = ln["pay_code_hits"][0]
    assert (hit["code"], hit["order_id"], hit["customer_name"], hit["has_open_receipt"]) == \
        ("KN-5R6S7", so["id"], "Toko Maju", False)
    # Kwitansi dicatat → tanda berubah (layar tidak lagi menawarkan "Catat kwitansi dari mutasi ini").
    r = await _kwitansi(klien, siap["h"], so, 990_000, account_id=siap["A"], reference_no="KN-5R6S7")
    assert r.status_code == 200, r.text
    r = await klien.get(f"{BASE_REC}/lines", headers=siap["h"], params={"bank_account_id": siap["A"]})
    ln = next(x for x in r.json() if x["id"] == lid)
    assert ln["pay_code_hits"][0]["has_open_receipt"] is True
    # Pesanan terbuka membawa rekening tujuan (bahan isian "Rekening penerima" & peringatan instruksi di form).
    so2 = await _pesanan(db, siap, sisa=10_000, rek=siap["A"], kode="KN-4T5U6")
    r = await klien.get("/api/ar-receipts/open-orders", headers=siap["h"], params={"customer_id": siap["P"]})
    row = next(x for x in r.json() if x["order_id"] == so2["id"])
    assert (row["receiving_account_id"], row["payment_code"]) == (siap["A"], "KN-4T5U6")
