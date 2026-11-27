"""KB-1 Tugas 1 — pembantu akun kas `gl_service.akun_kas`, mode per PT (`cash_account_mode`), sub-akun rekening.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` §5.1 dan §7.

Persiapan (FIXTURE kecuali disebut ALUR):
  * `ent_ksc` TIDAK PERNAH dinyalakan di modul ini: regresi "PT belum aktif → jurnal persis seperti sebelumnya".
    Rekening dibuat lewat ALUR `POST /api/bank-accounts` (saldo awal ikut terjurnal), kas lewat ALUR
    `POST /api/cash-transactions` dan kwitansi `POST /api/ar-receipts`.
  * `ent_uji_kb1m` — PT uji dengan pemetaan PT `kas_bank.kas_besar` → akun PT 1-1101 (pemetaan tetap berlaku bila PT
    tidak aktif).

REGRESI (bukti sebelum/sesudah): `BARIS_LAMA` di bawah direkam dari kode SEBELUM Tugas 1 (komit c76ba9a) dengan
`KB1_REKAM=<berkas.json>`; uji membandingkan baris jurnal (kode akun, nama akun, debit, kredit, keterangan, kunci
pemetaan) persis sama.
"""
from __future__ import annotations

import json
import os
import re
import uuid

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, pt_uji

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
REKAM = os.environ.get("KB1_REKAM", "")
_rekaman: dict = {}


def _id(awal: str) -> str:
    return f"{awal}_kb1_{uuid.uuid4().hex[:8]}"


def _baris(je: dict, nomor: str = "") -> list:
    """Baris jurnal ternormalisasi untuk dibandingkan: nomor dokumen di keterangan diganti `<NO>`."""
    out = []
    for ln in je["lines"]:
        d = dict(ln)
        if nomor:
            d["description"] = d.get("description", "").replace(nomor, "<NO>")
        out.append(d)
    return out


def _cocok(nama: str, nyata) -> None:
    if REKAM:
        _rekaman[nama] = nyata
        with open(REKAM, "w", encoding="utf-8") as f:
            json.dump(_rekaman, f, ensure_ascii=False, indent=1, sort_keys=True)
        return
    assert nyata == BARIS_LAMA[nama], f"{nama}: {json.dumps(nyata, ensure_ascii=False)}"


async def _rekening(klien, h, **isi) -> dict:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


async def _jurnal_sumber(db, source_type: str, source_id: str) -> dict:
    jes = await db.journal_entries.find({"source_type": source_type, "source_id": source_id,
                                         "status": {"$ne": "void"}}, {"_id": 0}).to_list(5)
    assert len(jes) == 1, jes
    return jes[0]


async def _kas_manual(klien, h, **isi) -> dict:
    r = await klien.post("/api/cash-transactions", headers=h, json=isi)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
async def lama(klien, db, kepala_admin):
    """Rekening `ent_ksc` (ALUR): Bank BCA saldo awal Rp 5.000.000; Kas Toko (tunai) saldo awal Rp 750.000."""
    bank = await _rekening(klien, kepala_admin, name="BCA KB1 KSC", account_number="900-111", entity_id=KSC,
                           holder_name="PT Kain Suka Cita", opening_balance=5_000_000)
    tunai = await _rekening(klien, kepala_admin, name="Kas Toko KB1 KSC", account_type="cash", bank_name="",
                            payment_method_codes=["cash"], entity_id=KSC, opening_balance=750_000)
    return {"bank": bank, "tunai": tunai, "h": kepala_admin}


# ═══ Regresi: PT tidak aktif → jurnal kas, kwitansi, saldo awal, posisi kas sama dengan sebelum ═══════════════════
async def test_KB1_1_U1a_saldo_awal_pt_tidak_aktif_sama(db, lama):
    je_bank = await _jurnal_sumber(db, "bank_opening_balance", lama["bank"]["id"])
    je_tunai = await _jurnal_sumber(db, "bank_opening_balance", lama["tunai"]["id"])
    _cocok("saldo_awal_bank", _baris(je_bank))
    _cocok("saldo_awal_tunai", _baris(je_tunai))
    assert not lama["bank"].get("gl_account_code") and not lama["tunai"].get("gl_account_code")


async def test_KB1_1_U1b_kas_manual_pt_tidak_aktif_sama(klien, db, lama):
    h = lama["h"]
    keluar = await _kas_manual(klien, h, cash_type="kas_kecil", direction="out", amount=250_000, category="sewa",
                               description="Sewa gudang KB1", account_id=lama["tunai"]["id"], entity_id=KSC)
    masuk = await _kas_manual(klien, h, cash_type="kas_besar", direction="in", amount=1_000_000, category="modal",
                              description="Setoran modal KB1", account_id=lama["bank"]["id"], entity_id=KSC)
    assert keluar["account_code"] == "1-1110" and masuk["account_code"] == "1-1100"
    _cocok("kas_keluar_manual", _baris(await _jurnal_sumber(db, "cash_transaction", keluar["id"]), keluar["number"]))
    _cocok("kas_masuk_manual", _baris(await _jurnal_sumber(db, "cash_transaction", masuk["id"]), masuk["number"]))


async def test_KB1_1_U1c_kwitansi_pt_tidak_aktif_sama(klien, db, lama):
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": "Toko KB1", "entity_id": KSC, "status": "active"})
    so = {"id": _id("so"), "number": "SO-KB1-1", "entity_id": KSC, "customer_id": cus, "customer_name": "Toko KB1",
          "status": "confirmed", "grand_total": 400_000.0, "payments": [], "paid_total": 0,
          "payment_status": "unpaid", "payment_term_code": "NET30", "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    r = await klien.post("/api/ar-receipts", headers=lama["h"], json={
        "customer_id": cus, "amount": 400_000, "method": "transfer", "entity_id": KSC,
        "account_id": lama["bank"]["id"], "allocations": [{"order_id": so["id"], "amount": 400_000}],
        "notes": "uji KB1"})
    assert r.status_code == 200, r.text
    rc = r.json()
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": rc["id"]}, {"_id": 0})
    assert kas["account_code"] == "1-1100"
    je = await _jurnal_sumber(db, "cash_transaction", kas["id"])
    _cocok("kwitansi", _baris(je, kas["number"]))


async def test_KB1_1_U2_pemetaan_pt_tetap_berlaku_bila_tidak_aktif(db):
    from services import cash_ledger, gl_mapping_service as glm, gl_service as gl
    from schemas_finance import GLAccountCreate
    pt = await pt_uji("KB1M")
    await gl.create_account(GLAccountCreate(code="1-1101", name="Bank Utama KB1M", type="asset",
                                            parent_code="1-1000"), entity_id=pt)
    await glm.set_mapping("kas_bank.kas_besar", pt, "1-1101", "uji KB1 pemetaan PT", AKTOR_UJI)
    await db.bank_accounts.insert_one({"id": "rek_kb1m", "name": "BCA KB1M", "entity_id": pt, "account_type": "bank",
                                       "cash_type": "kas_besar", "is_active": True, "opening_balance": 0.0})
    kas = await cash_ledger.create_cash(entity_id=pt, direction="in", amount=300_000, ref_type="manual",
                                        ref_id="kb1_u2", account_id="rek_kb1m", category="modal",
                                        description="Modal KB1M", actor="Uji")
    assert kas["account_code"] == "1-1100"   # dokumen kas menyimpan kode jenis kas (pemetaan diterapkan di jurnal)
    _cocok("pemetaan_pt", _baris(await _jurnal_sumber(db, "cash_transaction", kas["id"]), kas["number"]))


async def test_KB1_1_U3_posisi_kas_pt_tidak_aktif_sama(db, lama):
    from services import bank_service
    pos = await bank_service.cash_position([KSC])
    _cocok("posisi_kas", {"gl_accounts": pos["gl_accounts"], "gl_total": pos["gl_total"]})


async def test_KB1_1_U3b_pemilih_refund_pt_tidak_aktif_sama(klien, lama):
    r = await klien.get("/api/gl/cash-accounts", headers=lama["h"])
    assert r.status_code == 200, r.text
    _cocok("pemilih_refund", r.json())


# ═══ Mode per PT, sub-akun rekening, pembantu akun kas ═════════════════════════════════════════════════════════════
REK = [   # FIXTURE: rekening PT uji A (empat) dan B (tiga), disisip langsung (saldo awal 0, tanpa jurnal)
    {"id": "rek_a1", "name": "BCA Operasional A", "pt": "A", "account_type": "bank", "cash_type": "kas_besar"},
    {"id": "rek_a2", "name": "Mandiri A", "pt": "A", "account_type": "bank", "cash_type": "kas_besar"},
    {"id": "rek_a3", "name": "Kas Kecil A", "pt": "A", "account_type": "cash", "cash_type": "kas_kecil"},
    {"id": "rek_a4", "name": "BRI A", "pt": "A", "account_type": "bank", "cash_type": "kas_besar"},
    {"id": "rek_b1", "name": "BCA B", "pt": "B", "account_type": "bank", "cash_type": "kas_besar"},
    {"id": "rek_b2", "name": "Mandiri B", "pt": "B", "account_type": "bank", "cash_type": "kas_besar"},
    {"id": "rek_b3", "name": "BRI B", "pt": "B", "account_type": "bank", "cash_type": "kas_besar"},
]
PESAN_MANUAL = ("Akun {kode} adalah akun rekening {nama}; isi lewat kas atau Pindah Dana, bukan jurnal manual.")


@pytest.fixture(scope="module")
async def pt(db):
    ids = {"A": await pt_uji("KB1A"), "B": await pt_uji("KB1B")}
    for r in REK:
        doc = {k: v for k, v in r.items() if k != "pt"}
        await db.bank_accounts.insert_one({**doc, "entity_id": ids[r["pt"]], "is_active": True, "opening_balance": 0.0,
                                           "bank_name": "", "account_number": "", "created_at": now_iso()})
    return ids


async def _akun_pt(db, entity_id: str, kode: str) -> dict:
    return await db.gl_accounts.find_one({"code": kode, "entity_id": entity_id}, {"_id": 0}) or {}


async def test_KB1_1_U4_penanda_mode_per_pt_ditulis_sekali(db):
    from services import cash_account_mode as mode
    ptn = await pt_uji("KB1N")
    assert await mode.aktif(ptn) is False and await mode.aktif_sejak(ptn) == ""
    await mode.nyalakan(ptn, "Uji Satu")
    sejak = await mode.aktif_sejak(ptn)
    assert await mode.aktif(ptn) is True and sejak[:4] == now_iso()[:4]
    await mode.nyalakan(ptn, "Uji Dua")   # tulis sekali: waktu & pelaku pertama bertahan
    assert await mode.aktif_sejak(ptn) == sejak
    docs = await db.system_settings.find({"scope": mode.SCOPE}, {"_id": 0}).to_list(5)
    assert len(docs) == 1 and docs[0][ptn]["oleh"] == "Uji Satu" and docs[0][ptn]["sejak"] == sejak
    assert await mode.aktif(KSC) is False and await mode.aktif("") is False
    # PT kedua di dokumen penanda yang sama (tidak ada dokumen penanda kedua)
    await mode.nyalakan(await pt_uji("KB1N2"), "Uji")
    assert await db.system_settings.count_documents({"scope": mode.SCOPE}) == 1
    with pytest.raises(ValueError):
        await mode.nyalakan("ent.bertitik", "Uji")


async def test_KB1_1_U5_subakun_urut_per_pt_dan_per_induk(db, pt):
    from services import cash_account_mode as mode
    rek = {r["id"]: r async for r in db.bank_accounts.find({"entity_id": {"$in": list(pt.values())}}, {"_id": 0})}
    assert await mode.buat_subakun(rek["rek_a1"]) == "1-1100-01"
    assert await mode.buat_subakun(rek["rek_a2"]) == "1-1100-02"
    assert await mode.buat_subakun(rek["rek_a3"]) == "1-1110-01"   # kas kecil → induk 1-1110, urut sendiri
    assert await mode.buat_subakun(rek["rek_b1"]) == "1-1100-01"   # PT lain → urut sendiri
    assert await mode.buat_subakun(rek["rek_a1"]) == "1-1100-01"   # idempoten
    assert await db.gl_accounts.count_documents({"bank_account_id": "rek_a1"}) == 1
    a1 = await _akun_pt(db, pt["A"], "1-1100-01")
    assert {k: a1.get(k) for k in ("name", "type", "parent_code", "is_postable", "is_active", "is_cash",
                                   "bank_account_id", "entity_id")} == {
        "name": "BCA Operasional A", "type": "asset", "parent_code": "1-1100", "is_postable": True, "is_active": True,
        "is_cash": True, "bank_account_id": "rek_a1", "entity_id": pt["A"]}
    assert (await _akun_pt(db, pt["A"], "1-1110-01"))["parent_code"] == "1-1110"
    assert (await db.bank_accounts.find_one({"id": "rek_a1"}))["gl_account_code"] == "1-1100-01"
    assert (await db.bank_accounts.find_one({"id": "rek_a3"}))["gl_account_code"] == "1-1110-01"
    assert not (await db.bank_accounts.find_one({"id": "rek_a4"})).get("gl_account_code")
    assert await mode.aktif(pt["A"]) is False   # membuat sub-akun tidak menyalakan mode


async def test_KB1_1_U6_subakun_ada_pt_belum_aktif_tetap_akun_lama(db, pt):
    from services import cash_ledger, gl_service as gl
    rek = await cash_ledger.periksa_rekening(pt["A"], "rek_a1", "")
    assert rek["account_code"] == "1-1100"
    assert await gl.akun_kas(pt["A"], "rek_a1", "kas_besar") == "1-1100"
    assert await gl.akun_kas(pt["A"], "rek_a3", "kas_kecil") == "1-1110"
    kas = await cash_ledger.create_cash(entity_id=pt["A"], direction="in", amount=100_000, ref_type="manual",
                                        ref_id="kb1_u6", account_id="rek_a1", category="modal",
                                        description="Modal sebelum aktif", actor="Uji")
    je = await _jurnal_sumber(db, "cash_transaction", kas["id"])
    assert kas["account_code"] == "1-1100"
    assert {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]} == {
        ("1-1100", 100_000.0, 0.0), ("3-1000", 0.0, 100_000.0)}


async def test_KB1_1_U7_mode_aktif_kas_ke_subakun_tanpa_pemetaan(db, pt):
    from services import cash_account_mode as mode, cash_ledger, gl_mapping_service as glm, gl_service as gl
    from schemas_finance import GLAccountCreate
    A = pt["A"]
    # Pemetaan PT kas besar → 1-1101: berlaku untuk rekening TANPA sub-akun, tidak untuk sub-akun.
    await gl.create_account(GLAccountCreate(code="1-1101", name="Bank Umum A", type="asset", parent_code="1-1000"),
                            entity_id=A)
    await glm.set_mapping("kas_bank.kas_besar", A, "1-1101", "uji KB1 pemetaan PT A", AKTOR_UJI)
    await mode.nyalakan(A, "Uji")
    assert await gl.akun_kas(A, "rek_a1", "kas_besar") == "1-1100-01"
    assert await gl.akun_kas(A, "rek_a3", "kas_kecil") == "1-1110-01"
    assert await gl.akun_kas(A, "rek_a4", "kas_besar") == "1-1100"     # rekening tanpa sub-akun → akun lama
    assert await gl.akun_kas(pt["B"], "rek_a1", "kas_besar") == "1-1100"   # rekening PT lain → akun lama
    assert await gl.akun_kas(A, "", "kas_besar") == "1-1100"
    assert await gl._cash_account({"entity_id": A, "account_id": "rek_a1", "cash_type": "kas_besar"}) == "1-1100-01"
    assert (await cash_ledger.periksa_rekening(A, "rek_a2", ""))["account_code"] == "1-1100-02"

    masuk = await cash_ledger.create_cash(entity_id=A, direction="in", amount=300_000, ref_type="manual",
                                          ref_id="kb1_u7_in", account_id="rek_a1", category="modal",
                                          description="Modal sesudah aktif", actor="Uji")
    assert masuk["account_code"] == "1-1100-01"
    je = await _jurnal_sumber(db, "cash_transaction", masuk["id"])
    kas_ln = next(ln for ln in je["lines"] if ln["debit"])
    assert (kas_ln["account_code"], kas_ln["debit"], kas_ln["account_name"]) == ("1-1100-01", 300_000.0,
                                                                                  "BCA Operasional A")
    assert "mapping_key" not in kas_ln

    keluar = await cash_ledger.create_cash(entity_id=A, direction="out", amount=40_000, ref_type="manual",
                                           ref_id="kb1_u7_out", account_id="rek_a3", category="sewa",
                                           description="Sewa", actor="Uji")
    je = await _jurnal_sumber(db, "cash_transaction", keluar["id"])
    assert {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]} == {
        ("6-2000", 40_000.0, 0.0), ("1-1110-01", 0.0, 40_000.0)}

    tanpa = await cash_ledger.create_cash(entity_id=A, direction="in", amount=70_000, ref_type="manual",
                                          ref_id="kb1_u7_a4", account_id="rek_a4", category="modal",
                                          description="Modal BRI", actor="Uji")
    je = await _jurnal_sumber(db, "cash_transaction", tanpa["id"])
    kas_ln = next(ln for ln in je["lines"] if ln["debit"])
    assert (kas_ln["account_code"], kas_ln.get("mapping_key")) == ("1-1101", "kas_bank.kas_besar")

    # Saldo awal (penyesuaian) rekening ber-sub-akun di PT aktif → sub-akun.
    from services import bank_service
    await bank_service.update_account("rek_a2", {"opening_balance": 200_000})
    je = (await db.journal_entries.find({"source_type": "bank_opening_adjustment",
                                         "source_id": {"$regex": "^rek_a2:"}}, {"_id": 0}).to_list(2))[0]
    assert {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]} == {
        ("1-1100-02", 200_000.0, 0.0), ("3-2900", 0.0, 200_000.0)}


async def test_KB1_1_U8_akun_pt_yang_ada_bisa_dipakai_dan_diperiksa(db, pt):
    from services import cash_account_mode as mode, gl_service as gl
    from schemas_finance import GLAccountCreate
    B = pt["B"]
    for kode, nama, jenis, postable in (("1-1120", "Bank Mandiri B (akun lama)", "asset", True),
                                        ("1-1190", "Kelompok Bank B", "asset", False),
                                        ("6-9910", "Beban Lain B", "expense", True)):
        await gl.create_account(GLAccountCreate(code=kode, name=nama, type=jenis, parent_code="",
                                                is_postable=postable), entity_id=B)
    await gl.create_account(GLAccountCreate(code="1-1130", name="Bank PT A", type="asset"), entity_id=pt["A"])
    rek = {r["id"]: r async for r in db.bank_accounts.find({"entity_id": B}, {"_id": 0})}
    salah = [("1-1199", "tidak ada di bagan akun"), ("1-1130", "tidak ada di bagan akun"),
             ("1-1100", "akun bawaan"), ("1-1190", "akun induk"), ("6-9910", "bukan akun aset")]
    for kode, potongan in salah:
        with pytest.raises(ValueError) as e:
            await mode.buat_subakun(rek["rek_b3"], kode=kode)
        assert potongan in str(e.value), (kode, str(e.value))
    assert await mode.buat_subakun(rek["rek_b2"], kode="1-1120") == "1-1120"
    a = await _akun_pt(db, B, "1-1120")
    assert (a["is_cash"], a["bank_account_id"], a["name"]) == (True, "rek_b2", "Bank Mandiri B (akun lama)")
    assert (await db.bank_accounts.find_one({"id": "rek_b2"}))["gl_account_code"] == "1-1120"
    with pytest.raises(ValueError) as e:
        await mode.buat_subakun(rek["rek_b3"], kode="1-1120")
    assert "sudah dipakai rekening Mandiri B" in str(e.value)
    with pytest.raises(ValueError) as e:
        await mode.buat_subakun(rek["rek_b3"], kode="1-1100-01")   # sub-akun rekening BCA B
    assert "sudah dipakai rekening BCA B" in str(e.value)
    assert not (await db.bank_accounts.find_one({"id": "rek_b3"})).get("gl_account_code")
    assert await mode.buat_subakun(rek["rek_b3"]) == "1-1100-02"


async def test_KB1_1_U9_rekening_baru_pt_aktif_dapat_subakun_dan_saldo_awal(klien, db, kepala_admin, sesi):
    from services import cash_account_mode as mode
    # PT belum aktif: memilih akun buku besar ditolak, rekening tidak dibuat
    n0 = await db.bank_accounts.count_documents({})
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "name": "BCA Tolak", "account_type": "bank", "bank_name": "BCA", "entity_id": KSC,
        "gl_account_code": "1-1101"})
    assert r.status_code == 400 and "belum memakai akun buku besar per rekening" in r.json()["detail"], r.text
    assert await db.bank_accounts.count_documents({}) == n0

    await mode.nyalakan(KANDA, "Uji")
    h = await sesi("admin@kainnusantara.id", entitas=KANDA)
    bank = await _rekening(klien, h, name="BCA KB1 Kanda", account_number="700-1", entity_id=KANDA,
                           opening_balance=2_000_000)
    assert bank["gl_account_code"] == "1-1100-01"
    assert (await _akun_pt(db, KANDA, "1-1100-01"))["bank_account_id"] == bank["id"]
    je = await _jurnal_sumber(db, "bank_opening_balance", bank["id"])
    assert {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]} == {
        ("1-1100-01", 2_000_000.0, 0.0), ("3-2900", 0.0, 2_000_000.0)}
    tunai = await _rekening(klien, h, name="Kas Kecil KB1 Kanda", account_type="cash", bank_name="",
                            payment_method_codes=["cash"], entity_id=KANDA, opening_balance=100_000)
    assert tunai["gl_account_code"] == "1-1110-01"

    r = await klien.post("/api/gl/accounts", headers=h, params={"entity_id": KANDA}, json={
        "code": "1-1105", "name": "Bank Lama Kanda", "type": "asset", "parent_code": "1-1000"})
    assert r.status_code == 200, r.text
    pilih = await _rekening(klien, h, name="Mandiri KB1 Kanda", account_number="700-2", entity_id=KANDA,
                            gl_account_code="1-1105", opening_balance=500_000)
    assert pilih["gl_account_code"] == "1-1105"
    je = await _jurnal_sumber(db, "bank_opening_balance", pilih["id"])
    assert ("1-1105", 500_000.0, 0.0) in {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]}

    n1 = await db.bank_accounts.count_documents({})
    r = await klien.post("/api/bank-accounts", headers=h, json={
        "name": "BRI Tolak", "account_type": "bank", "bank_name": "BRI", "entity_id": KANDA,
        "gl_account_code": "1-1105"})
    assert r.status_code == 400 and "sudah dipakai rekening Mandiri KB1 Kanda" in r.json()["detail"], r.text
    assert await db.bank_accounts.count_documents({}) == n1

    # Kas lewat API ke rekening baru → sub-akun
    kas = await _kas_manual(klien, h, cash_type="kas_besar", direction="out", amount=150_000, category="sewa",
                            description="Sewa Kanda", account_id=bank["id"], entity_id=KANDA)
    assert kas["account_code"] == "1-1100-01"
    je = await _jurnal_sumber(db, "cash_transaction", kas["id"])
    assert ("1-1100-01", 0.0, 150_000.0) in {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]}
    SIMPAN.update(h_kanda=h, bank_kanda=bank, tunai_kanda=tunai, pilih_kanda=pilih)


SIMPAN: dict = {}


async def test_KB1_1_U10_jurnal_manual_ke_subakun_ditolak(klien, db):
    h = SIMPAN["h_kanda"]
    for kode, nama in (("1-1100-01", "BCA KB1 Kanda"), ("1-1105", "Mandiri KB1 Kanda")):
        r = await klien.post("/api/gl/journal", headers=h, json={
            "date": now_iso()[:10], "description": "Coba manual", "entity_id": KANDA,
            "lines": [{"account_code": kode, "debit": 50_000, "credit": 0},
                      {"account_code": "3-1000", "debit": 0, "credit": 50_000}]})
        assert (r.status_code, r.json().get("detail")) == (400, PESAN_MANUAL.format(kode=kode, nama=nama)), r.text
    # Akun kas lama (bukan akun rekening) tetap boleh dijurnal manual
    r = await klien.post("/api/gl/journal", headers=h, json={
        "date": now_iso()[:10], "description": "Manual ke akun lama", "entity_id": KANDA,
        "lines": [{"account_code": "1-1100", "debit": 10_000, "credit": 0},
                  {"account_code": "3-1000", "debit": 0, "credit": 10_000}]})
    assert r.status_code in (200, 202), r.text


async def test_KB1_1_U11_posisi_kas_dan_arus_kas_menjumlah_subakun(db):
    from services import bank_service, cash_flow_service, cashflow_forecast_service, finance_tower_service
    from services import report_basis as rb
    kas = await rb.kode_kas(KANDA)
    assert {"1-1100", "1-1110", "1-1100-01", "1-1110-01", "1-1105"} <= kas
    assert kas == await rb.kode_kas({"entity_id": KANDA})
    pos = await bank_service.cash_position([KANDA])
    saldo = {g["code"]: g["balance"] for g in pos["gl_accounts"]}
    # 1-1100-01: saldo awal 2.000.000 − sewa 150.000 = 1.850.000; 1-1110-01: 100.000; 1-1105: 500.000
    assert (saldo["1-1100-01"], saldo["1-1110-01"], saldo["1-1105"]) == (1_850_000.0, 100_000.0, 500_000.0)
    assert {"1-1100", "1-1110"} <= set(saldo)
    assert pos["gl_total"] == round(sum(saldo.values()), 2)
    nama = {g["code"]: g["name"] for g in pos["gl_accounts"]}
    assert nama["1-1100-01"] == "BCA KB1 Kanda"
    scope = {"entity_id": KANDA}
    assert (await finance_tower_service._cash_position(scope))["total"] == pos["gl_total"]
    assert await cashflow_forecast_service._cash_now(scope) == pos["gl_total"]
    cf = await cash_flow_service.cash_flow_statement(scope=scope)
    assert cf["end_cash_actual"] == pos["gl_total"]


async def test_KB1_1_U12_pemilih_refund_tanpa_subakun_rekening(klien):
    r = await klien.get("/api/gl/cash-accounts", headers=SIMPAN["h_kanda"])
    assert r.status_code == 200, r.text
    kode = [a["code"] for a in r.json()]
    assert {"1-1100", "1-1110"} <= set(kode)
    assert not {"1-1100-01", "1-1110-01", "1-1105"} & set(kode)


async def test_KB1_1_U13_nama_subakun_ikut_nama_rekening(db, pt):
    from services import bank_service
    await bank_service.update_account("rek_a1", {"name": "BCA Operasional A Baru"})
    a = await _akun_pt(db, pt["A"], "1-1100-01")
    assert (a["name"], a["code"]) == ("BCA Operasional A Baru", "1-1100-01")
    assert (await db.bank_accounts.find_one({"id": "rek_a1"}))["gl_account_code"] == "1-1100-01"
    # Akun PT yang dipilih Finance (bukan buatan sistem) tidak diganti namanya
    await bank_service.update_account("rek_b2", {"name": "Mandiri B Baru"})
    assert (await _akun_pt(db, pt["B"], "1-1120"))["name"] == "Bank Mandiri B (akun lama)"


async def test_KB1_1_U14_akun_rekening_tidak_bisa_dihapus_atau_dinonaktifkan(klien, db):
    h = SIMPAN["h_kanda"]
    r = await klien.delete("/api/gl/accounts/1-1110-01", headers=h, params={"entity_id": KANDA})
    assert (r.status_code, r.json().get("detail")) == (
        400, "Akun 1-1110-01 adalah akun buku besar rekening Kas Kecil KB1 Kanda dan tidak bisa dihapus."), r.text
    r = await klien.patch("/api/gl/accounts/1-1110-01", headers=h, params={"entity_id": KANDA},
                          json={"is_active": False})
    assert (r.status_code, r.json().get("detail")) == (
        409, "Akun 1-1110-01 adalah akun buku besar rekening Kas Kecil KB1 Kanda dan tidak bisa dinonaktifkan."), r.text
    assert (await _akun_pt(db, KANDA, "1-1110-01"))["is_active"] is True


# ═══ Perbaikan putaran 1 (tinjauan Tugas 1: I1–I3) ═════════════════════════════════════════════════════════════════
async def test_KB1_1_U15_ringkasan_per_pt_membaca_kode_kas(db):
    """I2 — `_entity_financials` (ringkasan per PT / konsolidasi) menjumlah kas dari `kode_kas` PT itu. PT tidak aktif
    tanpa pemetaan → angka sama persis dengan sebelum perbaikan (`ringkasan_pt_tidak_aktif` direkam dari 663d0b2)."""
    from services import bank_service, gl_service as gl
    _cocok("ringkasan_pt_tidak_aktif", await gl._entity_financials(KSC))
    pos = await bank_service.cash_position([KANDA])
    assert (await gl._entity_financials(KANDA))["cash"] == pos["gl_total"]
    cons = await gl.consolidation([KSC, KANDA])
    row = next(r for r in cons["entities"] if r["entity_id"] == KANDA)
    assert row["cash"] == pos["gl_total"]


async def test_KB1_1_U16_akun_pemetaan_kas_dan_akun_berjurnal_ditolak(klien, db, pt):
    """I1 — akun hasil pemetaan `kas_bank.*` PT itu tidak bisa jadi akun rekening; rekening BARU tidak boleh memakai akun
    yang sudah berjurnal."""
    from services import cash_account_mode as mode, gl_mapping_service as glm, gl_service as gl
    from schemas_finance import GLAccountCreate
    B = pt["B"]
    await gl.create_account(GLAccountCreate(code="1-1121", name="Kas Kecil Pemetaan B", type="asset"), entity_id=B)
    await glm.set_mapping("kas_bank.kas_kecil", B, "1-1121", "uji KB1 pemetaan kas kecil B", AKTOR_UJI)
    try:
        await db.bank_accounts.insert_one({"id": "rek_b4", "name": "Kas B Baru", "entity_id": B, "account_type": "cash",
                                           "cash_type": "kas_kecil", "is_active": True, "opening_balance": 0.0})
        with pytest.raises(ValueError) as e:
            await mode.buat_subakun({"id": "rek_b4"}, kode="1-1121")
        assert "kas_bank.kas_kecil" in str(e.value) and "Pemetaan Akun" in str(e.value), str(e.value)
        assert not (await db.bank_accounts.find_one({"id": "rek_b4"})).get("gl_account_code")
        assert not (await _akun_pt(db, B, "1-1121")).get("bank_account_id")
    finally:
        await glm.reset_mapping("kas_bank.kas_kecil", B, "pulihkan uji KB1", AKTOR_UJI)

    h = SIMPAN["h_kanda"]
    r = await klien.post("/api/gl/accounts", headers=h, params={"entity_id": KANDA}, json={
        "code": "1-1106", "name": "Bank Berjurnal Kanda", "type": "asset", "parent_code": "1-1000"})
    assert r.status_code == 200, r.text
    r = await klien.post("/api/gl/journal", headers=h, json={
        "date": now_iso()[:10], "description": "Saldo lama 1-1106", "entity_id": KANDA,
        "lines": [{"account_code": "1-1106", "debit": 25_000, "credit": 0},
                  {"account_code": "3-1000", "debit": 0, "credit": 25_000}]})
    assert r.status_code == 200, r.text   # jurnal manual sebelum akun ditautkan ke rekening: boleh
    n0 = await db.bank_accounts.count_documents({})
    r = await klien.post("/api/bank-accounts", headers=h, json={
        "name": "BNI Tolak", "account_type": "bank", "bank_name": "BNI", "entity_id": KANDA,
        "gl_account_code": "1-1106"})
    assert (r.status_code, r.json().get("detail")) == (400, (
        "Akun 1-1106 sudah punya saldo atau riwayat jurnal. Pilih akun yang masih kosong, atau kosongkan pilihan "
        "supaya sistem membuat sub-akun rekening.")), r.text
    assert await db.bank_accounts.count_documents({}) == n0


async def test_KB1_1_U16b_akun_pemetaan_non_kas_ditolak(db, pt):
    """Tinjauan akhir Minor 3 — akun yang dipakai pemetaan PT untuk kebutuhan APA PUN (bukan hanya `kas_bank.*`) tidak
    bisa jadi akun rekening: jurnal otomatis jalur itu akan menulis akun rekening tanpa dokumen kas."""
    from services import cash_account_mode as mode, gl_mapping_service as glm, gl_service as gl
    from schemas_finance import GLAccountCreate
    B = pt["B"]
    await gl.create_account(GLAccountCreate(code="1-1123", name="Penampung B", type="asset"), entity_id=B)
    await glm.set_mapping("lain.suspense", B, "1-1123", "uji KB1 pemetaan non-kas B", AKTOR_UJI)
    try:
        await db.bank_accounts.insert_one({"id": "rek_b5", "name": "Bank B Pemetaan", "entity_id": B,
                                           "account_type": "bank", "is_active": True, "opening_balance": 0.0})
        with pytest.raises(ValueError) as e:
            await mode.buat_subakun({"id": "rek_b5"}, kode="1-1123")
        assert str(e.value) == (
            "Akun 1-1123 sedang dipakai Pemetaan Akun \"Akun penampung (suspense)\" (lain.suspense) di "
            f"{await mode._nama_pt(B)}, jadi jurnal otomatis jalur itu ikut masuk ke akun ini. Pilih akun lain, atau "
            "ganti pemetaannya dulu di Pemetaan Akun."), str(e.value)
        assert not (await db.bank_accounts.find_one({"id": "rek_b5"})).get("gl_account_code")
        assert not (await _akun_pt(db, B, "1-1123")).get("bank_account_id")
    finally:
        await glm.reset_mapping("lain.suspense", B, "pulihkan uji KB1", AKTOR_UJI)
        await db.bank_accounts.delete_one({"id": "rek_b5"})
    # Pemetaan dipulihkan → akun yang sama boleh dipilih
    await db.bank_accounts.insert_one({"id": "rek_b5", "name": "Bank B Pemetaan", "entity_id": B,
                                       "account_type": "bank", "is_active": True, "opening_balance": 0.0})
    try:
        assert await mode.periksa_akun_pilihan(await db.bank_accounts.find_one({"id": "rek_b5"}, {"_id": 0}),
                                               "1-1123")
    finally:
        await db.bank_accounts.delete_one({"id": "rek_b5"})


async def test_KB1_1_U17_pembalikan_manual_jurnal_akun_rekening_ditolak(klien, db, lama):
    """I3 — pembalikan manual (`reverse_entry`) jurnal yang menyentuh akun rekening ditolak; jurnal ke akun kas lama
    tetap boleh dibalik; batal kas (`post_cash_void`) tidak terhalang dan membalik sub-akun."""
    h = SIMPAN["h_kanda"]
    kas = await db.cash_transactions.find_one({"entity_id": KANDA, "description": "Sewa Kanda"}, {"_id": 0})
    je = await _jurnal_sumber(db, "cash_transaction", kas["id"])
    r = await klien.post(f"/api/gl/journal/{je['id']}/reverse", headers=h,
                         json={"date": now_iso()[:10], "reason": "uji balik manual"})
    assert (r.status_code, r.json().get("detail")) == (400, (
        f"Jurnal {je['number']} menyentuh akun 1-1100-01, akun rekening BCA KB1 Kanda; balik lewat pembatalan "
        f"dokumen kasnya, bukan pembalikan manual.")), r.text
    assert not (await db.journal_entries.find_one({"id": je["id"]})).get("reversed_by_entry_id")
    # Batal kas (jalur dokumen kas) tetap jalan dan membalik sub-akun
    r = await klien.post(f"/api/cash-transactions/{kas['id']}/void", headers=h, json={"reason": "uji batal KB1"})
    assert r.status_code == 200, r.text
    balik = await _jurnal_sumber(db, "cash_transaction_void", kas["id"])
    assert ("1-1100-01", 150_000.0, 0.0) in {(ln["account_code"], ln["debit"], ln["credit"]) for ln in balik["lines"]}
    # Jurnal kas ke akun kas lama (PT tidak aktif) tetap bisa dibalik manual seperti dulu
    lama_kas = await db.cash_transactions.find_one({"entity_id": KSC, "description": "Sewa gudang KB1"}, {"_id": 0})
    je_lama = await _jurnal_sumber(db, "cash_transaction", lama_kas["id"])
    r = await klien.post(f"/api/gl/journal/{je_lama['id']}/reverse", headers=lama["h"],
                         json={"date": now_iso()[:10], "reason": "uji balik manual lama"})
    assert r.status_code == 200, r.text


#: Direkam dari kode SEBELUM Tugas 1 (c76ba9a) — jangan disunting tangan.
BARIS_LAMA: dict = {'kas_keluar_manual': [{'account_code': '6-2000',
                        'account_name': 'Beban Sewa',
                        'credit': 0.0,
                        'debit': 250000.0,
                        'description': '<NO> · Sewa gudang KB1'},
                       {'account_code': '1-1110',
                        'account_name': 'Kas Kecil',
                        'credit': 250000.0,
                        'debit': 0.0,
                        'description': '<NO> · Sewa gudang KB1'}],
 'kas_masuk_manual': [{'account_code': '1-1100',
                       'account_name': 'Kas Besar / Bank',
                       'credit': 0.0,
                       'debit': 1000000.0,
                       'description': '<NO> · Setoran modal KB1'},
                      {'account_code': '3-1000',
                       'account_name': 'Modal Disetor',
                       'credit': 1000000.0,
                       'debit': 0.0,
                       'description': '<NO> · Setoran modal KB1'}],
 'kwitansi': [{'account_code': '1-1100',
               'account_name': 'Kas Besar / Bank',
               'credit': 0.0,
               'debit': 400000.0,
               'description': '<NO> · Penerimaan KSC/AR-00001 — Toko KB1'},
              {'account_code': '2-1400',
               'account_name': 'Uang Muka Pelanggan',
               'credit': 400000.0,
               'debit': 0.0,
               'description': '<NO> · uang muka pesanan belum dikirim'}],
 'pemetaan_pt': [{'account_code': '1-1101',
                  'account_name': '',
                  'credit': 0.0,
                  'debit': 300000.0,
                  'description': '<NO> · Modal KB1M',
                  'mapping_key': 'kas_bank.kas_besar'},
                 {'account_code': '3-1000',
                  'account_name': 'Modal Disetor',
                  'credit': 300000.0,
                  'debit': 0.0,
                  'description': '<NO> · Modal KB1M'}],
 'pemilih_refund': [{'code': '1-1100', 'name': 'Kas Besar / Bank'},
                    {'code': '1-1110', 'name': 'Kas Kecil'},
                    {'code': '1-1150', 'name': 'Kas & Bank Transit (Dana Dalam Perjalanan)'}],
 'posisi_kas': {'gl_accounts': [{'balance': 106400000.0, 'code': '1-1100', 'name': 'Kas Besar / Bank'},
                                {'balance': 8250000.0, 'code': '1-1110', 'name': 'Kas Kecil'}],
                'gl_total': 114650000.0},
 'saldo_awal_bank': [{'account_code': '1-1100',
                      'account_name': 'Kas Besar / Bank',
                      'credit': 0.0,
                      'debit': 5000000.0,
                      'description': 'Saldo awal BCA KB1 KSC'},
                     {'account_code': '3-2900',
                      'account_name': 'Ekuitas Saldo Awal',
                      'credit': 5000000.0,
                      'debit': 0.0,
                      'description': 'Saldo awal BCA KB1 KSC'}],
 'saldo_awal_tunai': [{'account_code': '1-1110',
                       'account_name': 'Kas Kecil',
                       'credit': 0.0,
                       'debit': 750000.0,
                       'description': 'Saldo awal Kas Toko KB1 KSC'},
                      {'account_code': '3-2900',
                       'account_name': 'Ekuitas Saldo Awal',
                       'credit': 750000.0,
                       'debit': 0.0,
                       'description': 'Saldo awal Kas Toko KB1 KSC'}]}

#: Perbaikan putaran 1 (I2) — `_entity_financials(ent_ksc)` direkam dari 663d0b2 (sebelum perbaikan I2).
BARIS_LAMA["ringkasan_pt_tidak_aktif"] = {'ap': 0.0,
 'ar': 0.0,
 'assets': 105400000.0,
 'balanced': True,
 'cash': 114650000.0,
 'cogs': 0.0,
 'equity': 106750000.0,
 'equity_total': 105000000.0,
 'expense': 1750000.0,
 'gross_profit': 0.0,
 'inventory': 750000.0,
 'journal_count': 9,
 'liabilities': 400000.0,
 'net_income': -1750000.0,
 'net_margin': 0.0,
 'opex': 1750000.0,
 'ppn_out': 0.0,
 'retained_earnings': -1750000.0,
 'revenue': 0.0}
