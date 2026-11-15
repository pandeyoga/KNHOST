"""PM-T4 — tunai yang diterima sales dicatat sebagai titipan sampai disetor (docs/blueprint/unit/PM-T4.md, uji
penerimaan lapis B U1–U15). U16 (dua `receive` bersamaan) = lapis A `backend/tests/test_bp_PMT4_terima_bersamaan.py`;
U17 = uji jalan layar.

Persiapan (ALUR lewat API kecuali disebut FIXTURE):
  * rekening `ent_kanda`: **K** (Kas Kecil, tunai, bawaan tunai) dan **B** (BCA, bawaan transfer); `ent_ksc`: **K2**
    (Kas Kecil, tunai) — `POST /api/bank-accounts`;
  * pelanggan P "Toko Kanda" (`ent_kanda`) dan Q "Toko KSC" (`ent_ksc`) = FIXTURE; tiap uji memakai tagihan sendiri:
    pesanan `shipped` Rp 1.000.000 tanpa pembayaran + jurnal pendapatannya lewat `gl_service.post_sales_order`
    (Dr 1-1200 Piutang 1.000.000 / Cr 4-1000 Pendapatan 1.000.000) = FIXTURE;
  * akun `sales` (tanpa `cash.create`) dan `finance` (pemegang `cash.create`) = FIXTURE `akun`, satu akun sales per uji
    supaya titipan tiap uji terpisah;
  * `pembayaran.sales_terima_tunai` = `titipan` pada `ent_kanda` saja (`PUT /api/config/values`); kwitansi, setoran,
    terima/tolak/batal, pembatalan kwitansi, pengaturan, ulang posting = ALUR lewat API.

Hitung tangan:
  U1  sales: tunai Rp 300.000 untuk P → bukan kas: titipan TTP Rp 300.000 `dipegang`; jurnal titipan =
      Dr 1-1280 Piutang titipan karyawan 300.000 / Cr 1-1200 Piutang 300.000 (pesanan sudah berpendapatan → kredit
      piutang, fungsi sisi kredit yang sama dengan jurnal kas kwitansi); sisa tagihan 1.000.000 − 300.000 = 700.000.
  U4  setor 300.000 → diterima ke K: kas masuk 300.000 `account_id` K → Dr 1-1110 Kas kecil 300.000 / Cr 1-1280
      300.000; titipan `disetor`; saldo 1-1280 dari modul ini = 300.000 − 300.000 = 0.
  U5  titipan 300.000 lalu 200.000; setor 350.000 (tertua dulu) → 300.000 ke titipan pertama (`disetor`),
      50.000 ke kedua (`sebagian_disetor`, sisa 150.000) → dipegang 0 + 150.000 = 150.000.
  U6  dipegang 300.000, setor 400.000 → 400.
  U8  batas 400.000; dipegang 300.000 + 150.000 = 450.000 > 400.000 → 409, tanpa kwitansi.
"""
from __future__ import annotations

import datetime as _dt
import importlib
import itertools
import re
import sys
import uuid
from pathlib import Path

import pytest

from core_utils import now_iso
from pembantu import jumlah, tutup_periode

pytestmark = pytest.mark.anyio

KANDA, KSC = "ent_kanda", "ent_ksc"
REPO = Path(__file__).resolve().parents[2]
K_MODE = "pembayaran.sales_terima_tunai"
K_BATAS = "pembayaran.titipan_batas_nominal"
K_TENGGAT = "pembayaran.titipan_tenggat_setor_hari"
PESAN_DILARANG = ("PT ini tidak mengizinkan sales menerima tunai. Minta pelanggan transfer atau bayar ke kasir.")
PESAN_PEMEGANG = "Setoran tidak bisa diterima oleh pemegang titipannya sendiri."
PESAN_DIPUTUS = "Setoran ini sudah diterima, ditolak, atau dibatalkan."
PESAN_BATAL_DISETOR = "Titipan kwitansi ini sudah disetor. Batalkan penerimaan setorannya dulu."
ACC_PIUTANG, ACC_PIUTANG_KARYAWAN, ACC_KAS_KECIL = "1-1200", "1-1280", "1-1110"
_n = itertools.count(1)
SIMPAN: dict = {}


def _id(awal: str) -> str:
    return f"{awal}_pmt4_{uuid.uuid4().hex[:8]}"


def _hari(n: int) -> str:
    return (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=n)).isoformat()


async def _rekening(klien, h, **isi) -> str:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def _setel(klien, h, key, value, ent=KANDA):
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": key, "value": value, "scope_type": "entity", "scope_id": ent, "reason": "uji PM-T4"}]})
    assert r.status_code == 200, r.text


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, sesi, akun):
    h_kanda = await sesi("admin@kainnusantara.id", entitas=KANDA)
    k = await _rekening(klien, h_kanda, name="Kas Kecil Kanda", account_type="cash", bank_name="",
                        payment_method_codes=["cash"], default_receiving_methods=["cash"], entity_id=KANDA)
    b = await _rekening(klien, h_kanda, name="BCA Penerimaan Kanda", account_number="987-654-3210",
                        holder_name="CV Kanda", default_receiving_methods=["transfer"], entity_id=KANDA)
    k2 = await _rekening(klien, kepala_admin, name="Kas Kecil KSC", account_type="cash", bank_name="",
                         payment_method_codes=["cash"], default_receiving_methods=["cash"], entity_id=KSC)
    pel = {}
    for ent, nama in ((KANDA, "Toko Kanda"), (KSC, "Toko KSC")):   # FIXTURE
        cus = _id("cus")
        await db.customers.insert_one({"id": cus, "name": nama, "entity_id": ent, "status": "active"})
        pel[ent] = cus
    fin = await akun("finance", entitas=(KANDA, KSC))
    # Kode lama: kuncinya belum ada (404) — persiapan tetap jalan supaya tiap uji merah karena sebabnya sendiri
    # (U2 lulus di kode lama: PT lain tidak berubah).
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": K_MODE, "value": "titipan", "scope_type": "entity", "scope_id": KANDA, "reason": "uji PM-T4"}]})
    assert r.status_code in (200, 404), r.text
    return {"K": k, "B": b, "K2": k2, "P": pel[KANDA], "Q": pel[KSC], "h": kepala_admin, "h_kanda": h_kanda,
            "fin": fin, "h_fin": await sesi(fin, entitas=KANDA), "h_fin_ksc": await sesi(fin, entitas=KSC)}


async def _sales(akun, sesi, ent=KANDA):
    """FIXTURE: akun sales baru (tanpa `cash.create`) — satu per uji supaya titipannya terpisah."""
    u = await akun("sales", entitas=(KANDA, KSC))
    return u, await sesi(u, entitas=ent)


async def _tagihan(db, siap, *, ent=KANDA, total: float = 1_000_000) -> dict:
    """FIXTURE: pesanan terkirim bersisa `total` + jurnal pendapatannya (Dr Piutang / Cr Pendapatan)."""
    from services import gl_service as gl
    i = next(_n)
    so = {"id": _id("so"), "number": f"SO-PMT4-{i}", "entity_id": ent,
          "customer_id": siap["P"] if ent == KANDA else siap["Q"], "customer_name": "Toko", "status": "shipped",
          "grand_total": float(total), "ppn_amount": 0.0, "payments": [], "paid_total": 0, "payment_status": "unpaid",
          "payment_term_code": "NET30", "items": [], "created_at": now_iso(), "payment_method_code": "",
          "receiving_account_id": "", "receiving_account": {}}
    await db.sales_orders.insert_one(dict(so))
    je = await gl.post_sales_order(so)
    assert je and je["total_debit"] == total, je
    return so


async def _kwitansi(klien, h, so: dict, amount: float, method: str = "cash", **isi):
    body = {"customer_id": so["customer_id"], "amount": amount, "method": method, "entity_id": so["entity_id"],
            "allocations": [{"order_id": so["id"], "amount": amount}], "notes": "uji PM-T4", **isi}
    return await klien.post("/api/ar-receipts", headers=h, json=body)


async def _sisa(db, so) -> float:
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    return round(float(o["grand_total"]) - sum(float(p.get("amount") or 0) for p in o.get("payments") or []), 2)


async def _baris(db, source_type, source_id) -> dict:
    """{kode akun: (debit, kredit)} jurnal tidak-batal satu sumber."""
    out: dict = {}
    async for je in db.journal_entries.find({"source_type": source_type, "source_id": source_id,
                                             "status": {"$ne": "void"}}, {"_id": 0}):
        for ln in je["lines"]:
            d, c = out.get(ln["account_code"], (0.0, 0.0))
            out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2),
                                       round(c + float(ln.get("credit") or 0), 2))
    return out


async def _setor(klien, h, amount, **isi):
    return await klien.post("/api/cash-deposits", headers=h, json={"amount": amount, "note": "setor uji", **isi})


async def _terima(klien, h, dep_id, account_id):
    return await klien.post(f"/api/cash-deposits/{dep_id}/receive", headers=h, json={"account_id": account_id})


# ── U1–U3: kapan kwitansi tunai menjadi titipan ───────────────────────────────────────────────────────────────────
async def test_PMT4_U1_sales_tunai_menjadi_titipan_tanpa_kas(klien, db, siap, akun, sesi):
    sls, h = await _sales(akun, sesi)
    so = await _tagihan(db, siap)
    n_kas = await jumlah("cash_transactions", {})
    r = await _kwitansi(klien, h, so, 300_000)
    assert r.status_code == 200, r.text
    j = r.json()
    assert await jumlah("cash_transactions", {}) == n_kas            # tidak ada kas baru
    assert j.get("cash_holding_id"), j
    th = await db.cash_holdings.find_one({"receipt_id": j["id"]}, {"_id": 0})
    assert th and th["id"] == j["cash_holding_id"]
    assert (th["amount"], th["deposited_amount"], th["status"]) == (300_000, 0, "dipegang")
    assert (th["holder_user_id"], th["entity_id"], th["receipt_number"]) == (sls["id"], KANDA, j["number"])
    assert "TTP-" in th["number"] and th["gl_status"] == "posted"
    assert await jumlah("cash_holdings", {"receipt_id": j["id"]}) == 1
    assert await _baris(db, "cash_holding", th["id"]) == {ACC_PIUTANG_KARYAWAN: (300_000, 0), ACC_PIUTANG: (0, 300_000)}
    assert await _sisa(db, so) == 700_000
    assert j["gl_status"] == "posted" and not j.get("account_id")
    SIMPAN.update(u1=j, u1_th=th, u1_so=so, sls=sls, h_sls=h)


async def test_PMT4_U2_pt_lain_tetap_kas_langsung(klien, db, siap, akun, sesi):
    _sls, h = await _sales(akun, sesi, ent=KSC)
    so = await _tagihan(db, siap, ent=KSC)
    r = await _kwitansi(klien, h, so, 300_000)
    assert r.status_code == 200, r.text
    j = r.json()
    kas = [c async for c in db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": j["id"]}, {"_id": 0})]
    assert len(kas) == 1 and kas[0]["amount"] == 300_000 and kas[0]["account_id"] == siap["K2"]
    assert not j.get("cash_holding_id")
    assert await jumlah("cash_holdings", {"receipt_id": j["id"]}) == 0


async def test_PMT4_U3_pemegang_kas_selalu_kas_langsung(klien, db, siap):
    so = await _tagihan(db, siap)
    r = await _kwitansi(klien, siap["h_fin"], so, 300_000)
    assert r.status_code == 200, r.text
    j = r.json()
    kas = [c async for c in db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": j["id"]}, {"_id": 0})]
    assert len(kas) == 1 and kas[0]["account_id"] == siap["K"]
    assert await jumlah("cash_holdings", {"receipt_id": j["id"]}) == 0


# ── U4–U7: setoran ────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PMT4_U4_setor_lalu_diterima_ke_rekening_kas(klien, db, siap):
    th = SIMPAN["u1_th"]
    r = await _setor(klien, SIMPAN["h_sls"], 300_000)
    assert r.status_code == 200, r.text
    dep = r.json()
    assert dep["status"] == "diajukan" and "STT-" in dep["number"]
    assert [(a["holding_id"], a["amount"]) for a in dep["allocations"]] == [(th["id"], 300_000)]
    assert dep["allocations"][0]["holding_number"] == th["number"]
    r = await _terima(klien, siap["h_fin"], dep["id"], siap["K"])
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["status"], d["account_id"], d["received_by_id"]) == ("diterima", siap["K"], siap["fin"]["id"])
    kas = [c async for c in db.cash_transactions.find({"ref_type": "cash_deposit", "ref_id": dep["id"]}, {"_id": 0})]
    assert len(kas) == 1 and (kas[0]["amount"], kas[0]["account_id"], kas[0]["direction"]) == (300_000, siap["K"], "in")
    assert d["cash_txn_id"] == kas[0]["id"] and d["gl_status"] == "posted"
    assert await _baris(db, "cash_transaction", kas[0]["id"]) == {ACC_KAS_KECIL: (300_000, 0),
                                                                    ACC_PIUTANG_KARYAWAN: (0, 300_000)}
    fresh = await db.cash_holdings.find_one({"id": th["id"]}, {"_id": 0})
    assert (fresh["status"], fresh["deposited_amount"]) == ("disetor", 300_000)
    # saldo piutang karyawan dari modul ini = Σ debit jurnal titipan − Σ kredit kas setoran (titipan ini) = 0
    titipan = (await _baris(db, "cash_holding", th["id"]))[ACC_PIUTANG_KARYAWAN][0]
    setoran = (await _baris(db, "cash_transaction", kas[0]["id"]))[ACC_PIUTANG_KARYAWAN][1]
    assert titipan - setoran == 0
    SIMPAN.update(u4_dep=d, u4_kas=kas[0])


async def test_PMT4_U5_setoran_dialokasikan_ke_titipan_tertua(klien, db, siap, akun, sesi):
    _sls, h = await _sales(akun, sesi)
    so = await _tagihan(db, siap)
    r1 = await _kwitansi(klien, h, so, 300_000, receipt_date=_hari(1))
    r2 = await _kwitansi(klien, h, so, 200_000)
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    r = await _setor(klien, h, 350_000)
    assert r.status_code == 200, r.text
    dep = r.json()
    r = await _terima(klien, siap["h_fin"], dep["id"], siap["K"])
    assert r.status_code == 200, r.text
    t1 = await db.cash_holdings.find_one({"receipt_id": r1.json()["id"]}, {"_id": 0})
    t2 = await db.cash_holdings.find_one({"receipt_id": r2.json()["id"]}, {"_id": 0})
    assert (t1["status"], t1["deposited_amount"]) == ("disetor", 300_000)
    assert (t2["status"], t2["deposited_amount"]) == ("sebagian_disetor", 50_000)
    r = await klien.get("/api/cash-holdings/me/summary", headers=h)
    assert r.status_code == 200, r.text
    s = r.json()
    assert (s["held_total"], s["count"], s["mode"]) == (150_000, 1, "titipan"), s
    SIMPAN.update(u5_t2=t2)


async def test_PMT4_U6_setoran_melebihi_titipan_ditolak(klien, db, siap, akun, sesi):
    _sls, h = await _sales(akun, sesi)
    so = await _tagihan(db, siap)
    assert (await _kwitansi(klien, h, so, 300_000)).status_code == 200
    n = await jumlah("cash_deposits", {})
    r = await _setor(klien, h, 400_000)
    assert (r.status_code, r.json().get("detail")) == (400, "Setoran melebihi tunai yang Anda pegang (Rp 300.000)."), r.text
    assert await jumlah("cash_deposits", {}) == n


async def test_PMT4_U7_penerima_tidak_boleh_pemegang(klien, db, siap, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"ar_receipt": ["create"], "cash_holding": ["create", "approve"]})
    u = await akun(rid, entitas=(KANDA,))
    h = await sesi(u, entitas=KANDA)
    so = await _tagihan(db, siap)
    r = await _kwitansi(klien, h, so, 100_000)
    assert r.status_code == 200, r.text
    assert await jumlah("cash_holdings", {"receipt_id": r.json()["id"], "holder_user_id": u["id"]}) == 1
    dep = (await _setor(klien, h, 100_000)).json()
    r = await _terima(klien, h, dep["id"], siap["K"])
    assert (r.status_code, r.json().get("detail")) == (403, PESAN_PEMEGANG), r.text
    assert (await db.cash_deposits.find_one({"id": dep["id"]}, {"_id": 0}))["status"] == "diajukan"
    assert await jumlah("cash_transactions", {"ref_type": "cash_deposit", "ref_id": dep["id"]}) == 0


# ── U8–U10: batas, tenggat, dilarang ──────────────────────────────────────────────────────────────────────────────
async def test_PMT4_U8_batas_titipan_per_orang(klien, db, siap, akun, sesi):
    _sls, h = await _sales(akun, sesi)
    so = await _tagihan(db, siap)
    assert (await _kwitansi(klien, h, so, 300_000)).status_code == 200
    await _setel(klien, siap["h"], K_BATAS, 400_000)
    try:
        n = await jumlah("ar_receipts", {})
        r = await _kwitansi(klien, h, so, 150_000)
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == ("Titipan tunai Anda Rp 300.000 sudah mencapai batas Rp 400.000. Setor dulu "
                                      "sebelum menerima tunai lagi."), r.text
        assert await jumlah("ar_receipts", {}) == n
        assert await _sisa(db, so) == 700_000
        r = await klien.get("/api/cash-holdings/me/summary", headers=h)
        assert r.json()["limit"] == 400_000
    finally:
        await _setel(klien, siap["h"], K_BATAS, 0)


async def test_PMT4_U9_lewat_tenggat(klien, db, siap, akun, sesi):
    await _setel(klien, siap["h"], K_TENGGAT, 1)
    try:
        _sls, h = await _sales(akun, sesi)
        so = await _tagihan(db, siap)
        r = await _kwitansi(klien, h, so, 120_000, receipt_date=_hari(2))
        assert r.status_code == 200, r.text
        hid = r.json()["cash_holding_id"]
        r2 = await _kwitansi(klien, h, so, 80_000)
        assert r2.status_code == 200, r2.text
        r = await klien.get("/api/cash-holdings", headers=siap["h_fin"], params={"overdue": "true"})
        assert r.status_code == 200, r.text
        ids = {x["id"] for x in r.json()["items"]}
        assert hid in ids and r2.json()["cash_holding_id"] not in ids
        assert all(x["overdue"] for x in r.json()["items"])
        s = (await klien.get("/api/cash-holdings/me/summary", headers=h)).json()
        assert s["oldest_due_at"] and s["oldest_due_at"] < now_iso(), s
    finally:
        await _setel(klien, siap["h"], K_TENGGAT, 0)


async def test_PMT4_U10_pt_melarang_sales_terima_tunai(klien, db, siap, akun, sesi):
    _sls, h = await _sales(akun, sesi)
    so = await _tagihan(db, siap)
    await _setel(klien, siap["h"], K_MODE, "dilarang")
    try:
        n = await jumlah("ar_receipts", {})
        r = await _kwitansi(klien, h, so, 100_000)
        assert (r.status_code, r.json().get("detail")) == (403, PESAN_DILARANG), r.text
        assert await jumlah("ar_receipts", {}) == n
        assert (await klien.get("/api/cash-holdings/me/summary", headers=h)).json()["mode"] == "dilarang"
        r = await _kwitansi(klien, h, so, 100_000, method="transfer")
        assert r.status_code == 200, r.text
        assert r.json()["account_id"] == siap["B"]
        # pemegang kas tetap boleh menerima tunai di PT ini
        assert (await _kwitansi(klien, siap["h_fin"], so, 50_000)).status_code == 200
    finally:
        await _setel(klien, siap["h"], K_MODE, "titipan")


# ── U11: pembatalan kwitansi ber-titipan ──────────────────────────────────────────────────────────────────────────
async def test_PMT4_U11_batal_kwitansi_titipan(klien, db, siap, akun, sesi):
    _sls, h = await _sales(akun, sesi)
    so = await _tagihan(db, siap)
    j = (await _kwitansi(klien, h, so, 300_000)).json()
    r = await klien.post(f"/api/ar-receipts/{j['id']}/void", headers=siap["h_kanda"], params={"reason": "salah catat"})
    assert r.status_code == 200, r.text
    th = await db.cash_holdings.find_one({"id": j["cash_holding_id"]}, {"_id": 0})
    assert th["status"] == "batal"
    assert await _baris(db, "cash_holding_reversal", th["id"]) == {ACC_PIUTANG_KARYAWAN: (0, 300_000),
                                                                     ACC_PIUTANG: (300_000, 0)}
    assert r.json()["void_gl_status"] == "posted"
    assert await _sisa(db, so) == 1_000_000
    # kwitansi U1 — titipannya sudah disetor (U4) → 409, tanpa niat batal
    u1 = SIMPAN["u1"]
    r = await klien.post(f"/api/ar-receipts/{u1['id']}/void", headers=siap["h_kanda"], params={"reason": "uji"})
    assert (r.status_code, r.json().get("detail")) == (409, PESAN_BATAL_DISETOR), r.text
    rc = await db.ar_receipts.find_one({"id": u1["id"]}, {"_id": 0})
    assert rc["status"] == "posted" and not rc.get("void_intent")


# ── U12: periode tertutup, jurnal kas gagal, ulang dari panel posting gagal ──────────────────────────────────────
async def test_PMT4_U12_terima_periode_tertutup_lalu_jurnal_gagal_diulang(klien, db, siap, akun, sesi,
                                                                          paksa_jurnal_gagal):
    _sls, h = await _sales(akun, sesi)
    so = await _tagihan(db, siap)
    hid = (await _kwitansi(klien, h, so, 300_000)).json()["cash_holding_id"]
    dep = (await _setor(klien, h, 300_000)).json()
    c = await tutup_periode(KANDA, now_iso()[:7])
    try:
        r = await _terima(klien, siap["h_fin"], dep["id"], siap["K"])
        assert r.status_code == 409, r.text
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    d0 = await db.cash_deposits.find_one({"id": dep["id"]}, {"_id": 0})
    assert d0["status"] == "diajukan" and not d0.get("receive_intent")
    assert (await db.cash_holdings.find_one({"id": hid}, {"_id": 0}))["deposited_amount"] == 0
    assert await jumlah("cash_transactions", {"ref_type": "cash_deposit", "ref_id": dep["id"]}) == 0
    async with paksa_jurnal_gagal("sisip", entity_id=KANDA, source_type="cash_transaction") as gagal:
        r = await _terima(klien, siap["h_fin"], dep["id"], siap["K"])
    assert gagal and r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["gl_status"]) == ("diterima", "failed")
    panel = (await klien.get("/api/finance/posting-failures", headers=siap["h_kanda"],
                             params={"kind": "cash_deposit"})).json()
    assert dep["id"] in {x["id"] for x in panel["items"]}, panel
    r = await klien.post(f"/api/finance/posting-failures/cash_deposit/{dep['id']}/retry", headers=siap["h_kanda"])
    assert r.status_code == 200, r.text
    kas = [x async for x in db.cash_transactions.find({"ref_type": "cash_deposit", "ref_id": dep["id"]}, {"_id": 0})]
    assert len(kas) == 1
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas[0]["id"],
                                            "status": {"$ne": "void"}}) == 1
    assert (await db.cash_deposits.find_one({"id": dep["id"]}, {"_id": 0}))["gl_status"] == "posted"
    assert (await db.cash_holdings.find_one({"id": hid}, {"_id": 0}))["deposited_amount"] == 300_000
    r = await _terima(klien, siap["h_fin"], dep["id"], siap["K"])
    assert (r.status_code, r.json().get("detail")) == (409, PESAN_DIPUTUS), r.text


# ── U13: INV-TTP-01 ──────────────────────────────────────────────────────────────────────────────────────────────
async def test_PMT4_U13_invarian_titipan(db, capsys):
    sys.path.insert(0, str(REPO / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    awal = vdi.results["fail"]
    await vdi.layer_cash_holding_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == awal, keluar
    assert re.search(r"PASS.*INV-TTP-01", keluar), keluar
    t2 = SIMPAN["u5_t2"]
    await db.cash_holdings.update_one({"id": t2["id"]}, {"$inc": {"deposited_amount": 10_000}})
    try:
        await vdi.layer_cash_holding_invariants(db)
        keluar = capsys.readouterr().out
        assert vdi.results["fail"] == awal + 1, keluar
        assert re.search(r"FAIL.*INV-TTP-01.*ent_kanda", keluar), keluar
    finally:
        await db.cash_holdings.update_one({"id": t2["id"]}, {"$inc": {"deposited_amount": -10_000}})


# ── U14: izin ────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PMT4_U14_izin_terima_dan_lihat(klien, db, siap, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong,
                                              peran_sopir):
    sls, h = await _sales(akun, sesi)
    so = await _tagihan(db, siap)
    assert (await _kwitansi(klien, h, so, 100_000)).status_code == 200
    assert (await _kwitansi(klien, h, so, 60_000)).status_code == 200
    dep1 = (await _setor(klien, h, 100_000)).json()
    dep2 = (await _setor(klien, h, 60_000)).json()
    assert dep1["status"] == dep2["status"] == "diajukan"
    for siapa in (await peran_manajer_kosong(), peran_sopir):
        u = await akun(siapa, entitas=(KANDA,))
        r = await _terima(klien, await sesi(u, entitas=KANDA), dep2["id"], siap["K"])
        assert r.status_code == 403, (siapa, r.text)
    tanpa = await akun(await peran_tanpa_acuan({"cash_holding": ["approve"]}), entitas=(KANDA,))
    r = await _terima(klien, await sesi(tanpa, entitas=KANDA), dep1["id"], siap["K"])
    assert r.status_code == 200, r.text
    assert (await db.cash_deposits.find_one({"id": dep2["id"]}, {"_id": 0}))["status"] == "diajukan"
    # sales hanya melihat titipannya sendiri; finance (pemegang `cash_holding.approve`) melihat semua
    lihat = (await klien.get("/api/cash-holdings", headers=h, params={"status": "all"})).json()
    assert lihat["total"] == 2 and {x["holder_user_id"] for x in lihat["items"]} == {sls["id"]}, lihat
    semua = (await klien.get("/api/cash-holdings", headers=siap["h_fin"], params={"status": "all"})).json()
    assert len({x["holder_user_id"] for x in semua["items"]}) > 1, semua
    r = await klien.get("/api/cash-holdings", headers=h, params={"holder_user_id": siap["fin"]["id"]})
    assert r.status_code == 200 and r.json()["total"] == 0
    # tolak & batal: titipan tidak berubah
    r = await klien.post(f"/api/cash-deposits/{dep2['id']}/cancel", headers=siap["h_fin"], json={"reason": "uji"})
    assert r.status_code == 403, r.text
    r = await klien.post(f"/api/cash-deposits/{dep2['id']}/reject", headers=siap["h_fin"],
                         json={"reason": "uang belum diserahkan"})
    assert r.status_code == 200 and r.json()["status"] == "ditolak", r.text
    dep3 = (await _setor(klien, h, 60_000)).json()
    r = await klien.post(f"/api/cash-deposits/{dep3['id']}/cancel", headers=h, json={"reason": "salah nominal"})
    assert r.status_code == 200 and r.json()["status"] == "dibatalkan", r.text
    r = await klien.post(f"/api/cash-deposits/{dep3['id']}/reject", headers=siap["h_fin"], json={"reason": "x"})
    assert (r.status_code, r.json().get("detail")) == (409, PESAN_DIPUTUS), r.text
    s = (await klien.get("/api/cash-holdings/me/summary", headers=h)).json()
    assert (s["held_total"], s["pending_total"]) == (60_000, 0), s


# ── tambahan: jurnal titipan gagal → ulang; mulai ulang server tidak membuat kas untuk kwitansi titipan ──────────
async def test_PMT4_jurnal_titipan_gagal_lalu_diulang(klien, db, siap, akun, sesi, paksa_jurnal_gagal):
    _sls, h = await _sales(akun, sesi)
    so = await _tagihan(db, siap)
    async with paksa_jurnal_gagal("sisip", entity_id=KANDA, source_type="cash_holding"):
        r = await _kwitansi(klien, h, so, 90_000)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["gl_status"] == "failed"
    th = await db.cash_holdings.find_one({"id": j["cash_holding_id"]}, {"_id": 0})
    assert th["gl_status"] == "failed" and await _sisa(db, so) == 910_000
    r = await klien.post(f"/api/finance/posting-failures/cash_holding/{th['id']}/retry", headers=siap["h_kanda"])
    assert r.status_code == 200, r.text
    assert (await db.cash_holdings.find_one({"id": th["id"]}, {"_id": 0}))["gl_status"] == "posted"
    assert (await db.ar_receipts.find_one({"id": j["id"]}, {"_id": 0}))["gl_status"] == "posted"
    assert await jumlah("journal_entries", {"source_type": "cash_holding", "source_id": th["id"]}) == 1
    import bootstrap
    await bootstrap.backfill_ar_cash_postings()
    assert await jumlah("cash_transactions", {"ref_type": "ar_receipt", "ref_id": j["id"]}) == 0


# ── contoh angka U1 → U4 (dokumen → jurnal → saldo) ─────────────────────────────────────────────────────────────
async def test_PMT4_contoh_angka_U1_ke_U4(db, siap):
    th, so, dep, kas = SIMPAN["u1_th"], SIMPAN["u1_so"], SIMPAN["u4_dep"], SIMPAN["u4_kas"]
    assert await _baris(db, "sales_order", so["id"]) == {ACC_PIUTANG: (1_000_000, 0), "4-1000": (0, 1_000_000)}
    assert await _baris(db, "cash_holding", th["id"]) == {ACC_PIUTANG_KARYAWAN: (300_000, 0), ACC_PIUTANG: (0, 300_000)}
    assert await _baris(db, "cash_transaction", kas["id"]) == {ACC_KAS_KECIL: (300_000, 0),
                                                                 ACC_PIUTANG_KARYAWAN: (0, 300_000)}
    assert await _sisa(db, so) == 700_000
    assert (await db.cash_holdings.find_one({"id": th["id"]}, {"_id": 0}))["status"] == "disetor"
    assert dep["amount"] == 300_000


# ── U15: tiga kunci pengaturan (terakhir: putaran mencabut lapisan PT `ent_kanda`) ───────────────────────────────
async def test_PMT4_U15_putaran_tiga_kunci(klien, kepala_admin):
    from test_KFT8_putaran_pengaturan import putaran
    for kunci in (K_MODE, K_BATAS, K_TENGGAT):
        gagal = await putaran(klien, kepala_admin, kunci)
        assert not gagal, "\n".join(gagal)
