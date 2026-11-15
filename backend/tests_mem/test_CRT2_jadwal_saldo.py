"""CR-T2 serah-terima (a) — jadwal tagihan (`billing_schedule_service`) dan saldo piutang tersimpan
(`customer_balance_service`) sebagai jalur BARU; pembaca lama belum dialihkan (docs/blueprint/unit/CR-T2.md).

Uji: U1, U2, U4, U5, U6, U11, U12, U13, U14, U16, bagian jadwal U7 dan U8, dan setara U3 (`open_lines` = baris tagihan
PK-41 `report_basis.baris_tagihan`). Bagian endpoint U3/U7/U8/U9/U10/U15 (pembaca yang dialihkan) ada di
`test_CRT2_pengalihan.py` (serah-terima b). U17 (dua kait bersamaan, indeks unik) di MongoDB asli:
`backend/tests/test_bp_CRT2_jadwal_bersamaan.py`.

FIXTURE F1 (disisipkan langsung, kasus RP-03): PT `ent_kanda` (non-PKP, tanpa PPN); pelanggan P; pesanan S1 100 yard ×
Rp 10.000 = Rp 1.000.000, termin NET30 (30 hari), dikonfirmasi 25 Agu 2026; surat jalan SJ-1 40 yard bertanggal
1 Sep 2026 dengan jurnal `shipment_revenue` Dr piutang Rp 400.000 (bentuk `gl_service.post_shipment_revenue`).
ALUR (API): `GET /api/ar/aging`, `GET /api/customers/{id}/balance`, `GET /api/customers/{id}/billing-schedule`,
`POST /api/ar-receipts`, `POST /api/payment-plans`, `POST /api/ar/balances/rebuild`. Kait `on_*` dipanggil sebagai
fungsi (di aplikasi dipanggil `confirm_core`, `dispatch_task`, `so_transition`, nota debit).

Hitung tangan:
  U1  SJ-1 1 Sep + 30 hari = 1 Okt → satu baris `shipment` Rp 400.000 jatuh tempo 2026-10-01.
  U4  15 Nov: terkirim 400.000 − bayar 0 = 400.000; belum dikirim 1.000.000 − 400.000 = 600.000; lewat tempo 400.000
      (1 Okt < 15 Nov); jatuh tempo tertua 2026-10-01.
  U5  SJ-2 10 Sep Rp 600.000 → baris kedua jatuh tempo 10 Sep + 30 = 10 Okt; Σ baris 400.000 + 600.000 = 1.000.000 =
      nilai pesanan; belum dikirim 1.000.000 − 1.000.000 = 0.
  U6  kwitansi 500.000 tgl 5 Okt → baris 1 (jatuh tempo tertua) lunas 400.000, baris 2 terbayar 100.000 sisa 500.000;
      terkirim belum lunas 1.000.000 − 500.000 = 500.000; per 15 Nov lewat tempo 500.000 (baris 1 lunas), tertua 10 Okt.
  U7  S2 Rp 2.000.000 DP50 (50 %, 14 hari) dikonfirmasi 3 Nov → baris `dp` 2.000.000 × 50 % = 1.000.000 jatuh tempo
      3 Nov; surat jalan 6 Nov Rp 800.000 → baris `shipment` 800.000 × (100 − 50) % = 400.000 jatuh tempo 6 + 14 = 20 Nov.
  U8  S3 Rp 1.000.000 NET30 terkirim penuh 1 Sep; rencana cicilan 500.000 (15 Sep) + 500.000 (15 Okt) → jadwal `term`
      di-void "diganti rencana baru"; kait surat jalan berikutnya tidak menambah baris ke rencana.
  U13 Σ terkirim belum lunas `ent_kanda` 400.000 = saldo 1-1200 `ent_kanda` 400.000; + jurnal manual Dr 1-1200 50.000
      → saldo 450.000, selisih 50.000 terjelaskan "jurnal tanpa pesanan".
"""
from __future__ import annotations

import datetime
import importlib
import re
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio

ADMIN = "admin@kainnusantara.id"
KSC, KANDA = "ent_ksc", "ent_kanda"
REPO = Path(__file__).resolve().parents[2]
S: dict = {}


def _id(awal: str) -> str:
    return f"{awal}_crt2_{uuid.uuid4().hex[:8]}"


def _beku(monkeypatch, tanggal_wib: str, jam_wib: int = 10):
    """Bekukan "hari ini" (`services.book_date._sekarang`, satu-satunya jam hari ini WIB)."""
    from services import book_date
    d = datetime.date.fromisoformat(tanggal_wib)
    beku = datetime.datetime(d.year, d.month, d.day, jam_wib, 0, tzinfo=book_date.WIB).astimezone(datetime.timezone.utc)
    monkeypatch.setattr(book_date, "_sekarang", lambda: beku)


def _jam(tanggal: str) -> str:
    return f"{tanggal}T03:00:00+00:00"   # 10.00 WIB


async def _pelanggan(db, eid: str, nama: str) -> str:
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": nama, "entity_id": eid, "status": "active",
                                   "payment_profile": {}, "deposit_balance": 0.0, "assigned_sales_id": ""})
    return cid


async def _pesanan(db, cid: str, eid: str, total: float, *, term="NET30", hari=30, confirmed="2026-08-25",
                   status="partially_shipped") -> dict:
    so = {"id": _id("so"), "number": f"SO-CRT2-{uuid.uuid4().hex[:5]}", "entity_id": eid, "customer_id": cid,
          "customer_name": "Toko CR-T2", "status": status, "grand_total": float(total), "total_amount": float(total),
          "ppn_amount": 0.0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid",
          "payment_term_code": term, "items": [], "created_at": _jam(confirmed), "confirmed_at": _jam(confirmed)}
    if hari is not None:
        so["payment_term_days"] = hari
    await db.sales_orders.insert_one(dict(so))
    return so


async def _kirim(db, so: dict, nilai: float, tanggal: str, nomor: str) -> str:
    """Dokumen surat jalan + jurnal pendapatannya (Dr piutang / Cr pendapatan) — bentuk `post_shipment_revenue`."""
    from services import gl_service as gl
    shid = _id("shp")
    await db.shipments.insert_one({"id": shid, "shipment_no": nomor, "order_id": so["id"], "entity_id": so["entity_id"],
                                   "status": "dispatched", "created_at": _jam(tanggal)})
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": float(nilai), "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": float(nilai)}],
                           description=f"Pengakuan penjualan {so['number']} · {nomor}", date=_jam(tanggal),
                           source_type="shipment_revenue", source_id=shid, entity_id=so["entity_id"],
                           created_by="system", source_label=nomor,
                           ref={"order_id": so["id"], "order_number": so["number"]})
    return shid


async def _jadwal(db, oid: str, origin: str = "term"):
    return await db.payment_plans.find_one({"doc_id": oid, "origin": origin}, {"_id": 0}, sort=[("created_at", -1)])


@pytest.fixture(scope="module")
async def adm(sesi):
    simpan: dict = {}

    async def _h(eid: str):
        if eid not in simpan:
            simpan[eid] = await sesi(ADMIN, entitas=eid)
        return simpan[eid]
    return _h


@pytest.fixture(scope="module")
async def f1(db):
    cid = await _pelanggan(db, KANDA, "Toko P CR-T2")
    s1 = await _pesanan(db, cid, KANDA, 1_000_000)
    await _kirim(db, s1, 400_000, "2026-09-01", "SJ-CRT2-1")
    S.update(P=cid, S1=s1)
    return S


async def _saldo(klien, h, cid, eid=KANDA):
    r = await klien.get(f"/api/customers/{cid}/balance", headers=h, params={"entity_id": eid})
    assert r.status_code == 200, r.text
    return r.json()


# ═══ U1, U2 — baris surat jalan lahir dari jurnalnya; idempoten ════════════════════════════════════════════════════
async def test_CRT2_U1_baris_surat_jalan_dari_jurnal(f1, db):
    from services import billing_schedule_service as bss
    plan = await bss.on_shipment_posted(f1["S1"]["id"], "SJ-CRT2-1")
    assert plan and plan["origin"] == "term" and plan["mode"] == "term"
    assert (plan["term_code"], plan["net_days"], plan["dp_percent"]) == ("NET30", 30, 0.0)
    [ln] = plan["lines"]
    assert (ln["kind"], ln["amount"], ln["due_date"], ln["source_type"], ln["source_id"]) == \
        ("shipment", 400_000, "2026-10-01", "shipment", "SJ-CRT2-1")
    assert ln["line_id"].startswith("ppl_") and ln["billed_at"] == "2026-09-01" and len(ln["journal_ids"]) == 1
    assert plan["billed_total"] == 400_000 and plan["recognized_total"] == 400_000


async def test_CRT2_U2_panggil_ulang_tidak_menggandakan(f1, db):
    from services import billing_schedule_service as bss
    lama = await _jadwal(db, f1["S1"]["id"])
    for _ in range(2):
        plan = await bss.on_shipment_posted(f1["S1"]["id"], "SJ-CRT2-1")
    assert plan["id"] == lama["id"] and len(plan["lines"]) == 1 and plan["billed_total"] == 400_000
    assert plan["lines"][0]["line_id"] == lama["lines"][0]["line_id"]
    assert await db.payment_plans.count_documents({"doc_id": f1["S1"]["id"], "status": {"$ne": "void"}}) == 1


# ═══ U3 (setara) — `open_lines` = baris tagihan PK-41 untuk F1 ═════════════════════════════════════════════════════
async def test_CRT2_U3_open_lines_sama_dengan_baris_tagihan(f1, db):
    from services import billing_schedule_service as bss
    from services import report_basis as rb
    rows = await bss.open_lines(entity_ids=[KANDA], customer_ids=[f1["P"]], as_of="2026-11-15")
    assert [(r["kind"], r["amount"], r["outstanding"], r["due_date"], r["days_late"]) for r in rows] == \
        [("shipment", 400_000, 400_000, "2026-10-01", 45)]
    so = await db.sales_orders.find_one({"id": f1["S1"]["id"]}, {"_id": 0})
    pk41 = (await rb.baris_tagihan([so], {}, per="2026-11-15"))[so["id"]]
    kirim = [r for r in pk41 if r["sumber"] != rb.SUMBER_BELUM_DIKIRIM]
    assert [(r["nilai"], r["sisa"], r["jatuh_tempo"], r["hari_lewat"]) for r in kirim] == \
        [(r["amount"], r["outstanding"], r["due_date"], r["days_late"]) for r in rows]
    assert [r["sisa"] for r in pk41 if r["sumber"] == rb.SUMBER_BELUM_DIKIRIM] == [600_000]
    assert rows[0]["journal_ids"] == [kirim[0]["jurnal_id"]]   # tautan jurnal (L8) sama


# ═══ U13 — INV-BAL-02: Σ piutang terkirim per PT = saldo akun piutang ═════════════════════════════════════════════
async def test_CRT2_U13_inv_bal_02_jurnal_tanpa_pesanan(f1, db, capsys, monkeypatch):
    from services import customer_balance_service as cbs
    from services import gl_service as gl
    _beku(monkeypatch, "2026-11-15")
    sys.path.insert(0, str(REPO / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    rec = await cbs.reconcile_gl(KANDA)
    assert (rec["ar_delivered"], rec["gl_balance"], rec["difference"]) == (400_000, 400_000, 0)
    awal = dict(vdi.results)
    await vdi.layer_balance_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == awal["fail"], keluar
    assert re.search(r"PASS.*INV-BAL-02", keluar), keluar
    je = await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": 50_000.0, "credit": 0.0},
                                       {"account_code": "4-9000", "debit": 0.0, "credit": 50_000.0}],
                                description="jurnal manual uji CR-T2", date=_jam("2026-11-10"), source_type="manual",
                                source_id=_id("mj"), entity_id=KANDA, created_by="uji")
    try:
        rec = await cbs.reconcile_gl(KANDA)
        assert (rec["gl_balance"], rec["difference"], rec["explained"], rec["unexplained"]) == \
            (450_000, 50_000, {"jurnal tanpa pesanan": 50_000}, 0)
        awal = dict(vdi.results)
        await vdi.layer_balance_invariants(db)
        keluar = capsys.readouterr().out
        assert vdi.results["fail"] == awal["fail"] and vdi.results["warn"] == awal["warn"] + 1, keluar
        assert re.search(r"WARN.*INV-BAL-02.*jurnal tanpa pesanan", keluar), keluar
        # sebab lain (jurnal piutang ber-sumber tak dikenal) = merah
        await db.journal_entries.update_one({"id": je["id"]}, {"$set": {"source_type": "uji_tak_dikenal"}})
        awal = dict(vdi.results)
        await vdi.layer_balance_invariants(db)
        keluar = capsys.readouterr().out
        assert vdi.results["fail"] == awal["fail"] + 1 and re.search(r"FAIL.*INV-BAL-02", keluar), keluar
    finally:
        await db.journal_entries.update_one({"id": je["id"]}, {"$set": {"status": "void"}})


# ═══ U4 — saldo tersimpan per (pelanggan, PT) ══════════════════════════════════════════════════════════════════════
async def test_CRT2_U4_saldo_pelanggan(f1, klien, adm, db, monkeypatch):
    _beku(monkeypatch, "2026-11-15")
    b = await _saldo(klien, await adm(KANDA), f1["P"])
    assert (b["ar_delivered"], b["open_orders_amount"], b["overdue_amount"], b["oldest_due_date"]) == \
        (400_000, 600_000, 400_000, "2026-10-01")
    assert (b["overdue_as_of"], b["days_overdue"], b["cash_term_amount"], b["giro_outstanding"]) == \
        ("2026-11-15", 45, 0, 0)
    assert b["id"].startswith("cbl_") and await db.customer_balances.count_documents(
        {"customer_id": f1["P"], "entity_id": KANDA}) == 1


# ═══ U5 — surat jalan kedua; Σ baris = nilai pesanan ══════════════════════════════════════════════════════════════
async def test_CRT2_U5_surat_jalan_kedua(f1, klien, adm, db, monkeypatch):
    from services import billing_schedule_service as bss
    _beku(monkeypatch, "2026-11-15")
    await _kirim(db, f1["S1"], 600_000, "2026-09-10", "SJ-CRT2-2")
    await db.sales_orders.update_one({"id": f1["S1"]["id"]}, {"$set": {"status": "shipped"}})
    plan = await bss.on_shipment_posted(f1["S1"]["id"], "SJ-CRT2-2")
    assert [(ln["source_id"], ln["amount"], ln["due_date"]) for ln in plan["lines"]] == \
        [("SJ-CRT2-1", 400_000, "2026-10-01"), ("SJ-CRT2-2", 600_000, "2026-10-10")]
    assert plan["billed_total"] == 1_000_000 and plan["billed_complete"] is True
    b = await _saldo(klien, await adm(KANDA), f1["P"])
    assert (b["ar_delivered"], b["open_orders_amount"]) == (1_000_000, 0)


# ═══ U6 — kwitansi lewat API: alokasi ke jatuh tempo tertua; saldo disegarkan fungsi alokasi ═════════════════════
async def test_CRT2_U6_kwitansi_mengalir_ke_baris(f1, klien, adm, db, monkeypatch):
    _beku(monkeypatch, "2026-11-15")
    await db.bank_accounts.insert_one({"id": "rek_crt2_b", "name": "BCA Kanda CR-T2", "entity_id": KANDA,
                                       "account_type": "bank", "cash_type": "kas_besar", "is_active": True,
                                       "opening_balance": 0})
    r = await klien.post("/api/ar-receipts", headers=await adm(KANDA), json={
        "customer_id": f1["P"], "amount": 500_000, "method": "transfer", "entity_id": KANDA, "account_id": "rek_crt2_b",
        "receipt_date": "2026-10-05", "allocations": [{"order_id": f1["S1"]["id"], "amount": 500_000}]})
    assert r.status_code == 200, r.text
    plan = await _jadwal(db, f1["S1"]["id"])
    assert [(ln["paid_amount"], ln["status"]) for ln in plan["lines"]] == [(400_000, "paid"), (100_000, "partial")]
    # disegarkan di fungsi alokasi (tanpa pembaca): baris tersimpan sudah memuat kwitansi
    row = await db.customer_balances.find_one({"customer_id": f1["P"], "entity_id": KANDA}, {"_id": 0})
    assert (row["ar_delivered"], row["last_payment_amount"]) == (500_000, 500_000)
    b = await _saldo(klien, await adm(KANDA), f1["P"])
    assert (b["ar_delivered"], b["overdue_amount"], b["oldest_due_date"], b["last_payment_amount"]) == \
        (500_000, 500_000, "2026-10-10", 500_000)
    r = await klien.get(f"/api/customers/{f1['P']}/billing-schedule", headers=await adm(KANDA),
                        params={"entity_id": KANDA})
    assert r.status_code == 200, r.text
    j = r.json()
    assert [(x["kind_label"], x["amount"], x["paid_amount"], x["outstanding"], x["due_date"], x["days_late"])
            for x in j["items"]] == [("Surat jalan", 600_000, 100_000, 500_000, "2026-10-10", 36)]
    assert j["total"] == 1 and j["note"] == "Umur dihitung per tagihan: surat jalan, uang muka, atau baris rencana."
    r = await klien.get(f"/api/customers/{f1['P']}/billing-schedule", headers=await adm(KANDA),
                        params={"entity_id": KANDA, "status": "all"})
    assert [x["outstanding"] for x in r.json()["items"]] == [500_000, 0]   # terbuka dulu


# ═══ U11 — PT lain dan pelanggan lain tidak ikut berubah ═════════════════════════════════════════════════════════
async def test_CRT2_U11_pt_lain_tidak_berubah(f1, klien, adm, db, monkeypatch):
    from services import billing_schedule_service as bss
    from services import customer_balance_service as cbs
    _beku(monkeypatch, "2026-11-15")
    q = await _pelanggan(db, KSC, "Toko Q CR-T2")
    sq = await _pesanan(db, q, KSC, 250_000)
    await _kirim(db, sq, 250_000, "2026-09-05", "SJ-CRT2-Q")
    await bss.on_shipment_posted(sq["id"], "SJ-CRT2-Q")
    sebelum = await db.customer_balances.find_one({"customer_id": q, "entity_id": KSC}, {"_id": 0})
    assert sebelum["ar_delivered"] == 250_000
    # ulangi alur U1–U6 untuk P (kait + kwitansi) → saldo Q tetap
    await bss.on_shipment_posted(f1["S1"]["id"], "SJ-CRT2-2")
    await cbs.refresh(f1["P"])
    sesudah = await db.customer_balances.find_one({"customer_id": q, "entity_id": KSC}, {"_id": 0})
    assert sesudah == sebelum
    lain = await cbs.compute(f1["P"], KSC)
    assert all(lain[k] in (0, 0.0, None) for k in ("ar_delivered", "open_orders_amount", "overdue_amount",
                                                     "oldest_due_date", "deposit_balance", "store_credit_balance",
                                                     "penalty_outstanding", "last_payment_amount")), lain
    S["Q"] = q


# ═══ U12 — INV-BAL-01 merah sesudah angka diubah langsung; bangun ulang → changed 1 → hijau ═══════════════════════
async def test_CRT2_U12_inv_bal_01_dan_bangun_ulang(f1, klien, adm, db, capsys, monkeypatch):
    from services import customer_balance_service as cbs
    _beku(monkeypatch, "2026-11-15")
    sys.path.insert(0, str(REPO / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    r = await klien.post("/api/ar/balances/rebuild", headers=await adm(KANDA))   # samakan semua pasangan dulu
    assert r.status_code == 200, r.text
    await db.customer_balances.update_one({"customer_id": f1["P"], "entity_id": KANDA}, {"$set": {"ar_delivered": 1}})
    awal = dict(vdi.results)
    await vdi.layer_balance_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == awal["fail"] + 1 and re.search(r"FAIL.*INV-BAL-01", keluar), keluar
    assert "Toko P CR-T2" in keluar and "ar_delivered" in keluar
    r = await klien.post("/api/ar/balances/rebuild", headers=await adm(KANDA))
    assert r.status_code == 200, r.text
    assert (r.json()["changed"], r.json()["entity_id"]) == (1, KANDA) and r.json()["pairs"] >= 1
    awal = dict(vdi.results)
    await vdi.layer_balance_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == awal["fail"] and re.search(r"PASS.*INV-BAL-01", keluar), keluar
    assert (await cbs.verify_stored())["bad"] == []


# ═══ U14 — izin: peran uji baku ════════════════════════════════════════════════════════════════════════════════════
async def test_CRT2_U14_izin_peran_uji_baku(f1, klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong,
                                            peran_sopir):
    url = f"/api/customers/{f1['P']}/billing-schedule"
    u = await akun(await peran_tanpa_acuan({"payment_plan": ["view"]}, label="Lihat Jadwal"), entitas=(KANDA,))
    r = await klien.get(url, headers=await sesi(u, entitas=KANDA), params={"entity_id": KANDA})
    assert r.status_code == 200, r.text
    for peran in (await peran_manajer_kosong(), peran_sopir):
        u = await akun(peran, entitas=(KANDA,))
        r = await klien.get(url, headers=await sesi(u, entitas=KANDA), params={"entity_id": KANDA})
        assert r.status_code == 403, (peran, r.text)
    # PT di luar penugasan → 403; pelanggan di luar cakupan → 403 berkalimat
    u = await akun(await peran_tanpa_acuan({"payment_plan": ["view"]}, label="Lihat Jadwal KSC"), entitas=(KSC,))
    h = await sesi(u, entitas=KSC)
    r = await klien.get(f"/api/customers/{S['Q']}/billing-schedule", headers=h, params={"entity_id": KANDA})
    assert r.status_code == 403, r.text
    r = await klien.get(url, headers=h)
    assert (r.status_code, r.json()["detail"]) == (403, "Pelanggan ini di luar cakupan Anda."), r.text
    # saldo: salah satu dari payment_plan.view / credit_profile.view
    u = await akun(await peran_tanpa_acuan({"credit_profile": ["view"]}, label="Lihat Kredit"), entitas=(KANDA,))
    r = await klien.get(f"/api/customers/{f1['P']}/balance", headers=await sesi(u, entitas=KANDA))
    assert r.status_code == 200, r.text
    u = await akun(peran_sopir, entitas=(KANDA,))
    r = await klien.get(f"/api/customers/{f1['P']}/balance", headers=await sesi(u, entitas=KANDA))
    assert r.status_code == 403, r.text
    r = await klien.post("/api/ar/balances/rebuild", headers=await sesi(u, entitas=KANDA))
    assert r.status_code == 403, r.text


# ═══ U7 (bagian jadwal) — termin DP: baris uang muka saat konfirmasi, surat jalan × (100 − DP) % ═════════════════
async def test_CRT2_U7_jadwal_dp(db, monkeypatch):
    from services import billing_schedule_service as bss
    _beku(monkeypatch, "2026-11-20")
    cid = await _pelanggan(db, KANDA, "Toko DP CR-T2")
    s2 = await _pesanan(db, cid, KANDA, 2_000_000, term="DP50", hari=None, confirmed="2026-11-03", status="confirmed")
    plan = await bss.on_order_confirmed(s2["id"])
    assert (plan["term_code"], plan["net_days"], plan["dp_percent"]) == ("DP50", 14, 50.0)
    assert [(ln["kind"], ln["amount"], ln["due_date"], ln["label"]) for ln in plan["lines"]] == \
        [("dp", 1_000_000, "2026-11-03", "Uang muka 50%")]
    await _kirim(db, s2, 800_000, "2026-11-06", "SJ-CRT2-DP")
    await db.sales_orders.update_one({"id": s2["id"]}, {"$set": {"status": "partially_shipped"}})
    plan = await bss.on_shipment_posted(s2["id"], "SJ-CRT2-DP")
    assert [(ln["kind"], ln["amount"], ln["due_date"]) for ln in plan["lines"]] == \
        [("dp", 1_000_000, "2026-11-03"), ("shipment", 400_000, "2026-11-20")]
    rows = await bss.open_lines(entity_ids=[KANDA], customer_ids=[cid])
    assert [(r["kind"], r["outstanding"], r["days_late"]) for r in rows] == [("dp", 1_000_000, 17), ("shipment", 400_000, 0)]
    S["DP"] = {"cus": cid, "so": s2}


# ═══ U8 (bagian jadwal) — rencana cicilan menggantikan jadwal termin ═════════════════════════════════════════════
async def test_CRT2_U8_rencana_cicilan_menggantikan(db, klien, adm, monkeypatch):
    from services import billing_schedule_service as bss
    _beku(monkeypatch, "2026-10-20")
    cid = await _pelanggan(db, KANDA, "Toko Cicil CR-T2")
    s3 = await _pesanan(db, cid, KANDA, 1_000_000, status="shipped")
    await _kirim(db, s3, 1_000_000, "2026-09-01", "SJ-CRT2-C")
    term = await bss.on_shipment_posted(s3["id"], "SJ-CRT2-C")
    assert [ln["amount"] for ln in term["lines"]] == [1_000_000]
    r = await klien.post("/api/payment-plans", headers=await adm(KANDA), json={
        "doc_type": "sales_order", "doc_id": s3["id"], "mode": "custom", "lines": [
            {"kind": "installment", "label": "Cicilan 1", "amount": 500_000, "due_rule": "fixed_date",
             "due_date": "2026-09-15"},
            {"kind": "installment", "label": "Cicilan 2", "amount": 500_000, "due_rule": "fixed_date",
             "due_date": "2026-10-15"}]})
    assert r.status_code == 200, r.text
    manual = r.json()
    assert manual["origin"] == "manual" and all(ln["line_id"].startswith("ppl_") for ln in manual["lines"])
    lama = await db.payment_plans.find_one({"id": term["id"]}, {"_id": 0})
    assert (lama["status"], lama["void_reason"]) == ("void", "diganti rencana baru")
    plan = await bss.on_shipment_posted(s3["id"], "SJ-CRT2-C")
    assert plan["id"] == manual["id"] and len(plan["lines"]) == 2
    assert await db.payment_plans.count_documents({"doc_id": s3["id"], "status": {"$ne": "void"}}) == 1
    rows = await bss.open_lines(entity_ids=[KANDA], customer_ids=[cid])
    assert [(r["due_date"], r["outstanding"], r["days_late"]) for r in rows] == \
        [("2026-09-15", 500_000, 35), ("2026-10-15", 500_000, 5)]
    # jadwal mesin tidak bisa diubah tangan
    r = await klien.patch(f"/api/payment-plans/{term['id']}", headers=await adm(KANDA), json={"note": "x"})
    assert r.status_code in (400, 409), r.text
    S["CICIL"] = {"cus": cid, "so": s3}


# ═══ U16 — pesanan batal sebelum surat jalan → jadwal void; saldo 0 ══════════════════════════════════════════════
async def test_CRT2_U16_pesanan_batal(db, klien, adm, monkeypatch):
    from services import billing_schedule_service as bss
    _beku(monkeypatch, "2026-11-15")
    cid = await _pelanggan(db, KANDA, "Toko Batal CR-T2")
    so = await _pesanan(db, cid, KANDA, 1_000_000, status="confirmed")
    plan = await bss.on_order_confirmed(so["id"])
    assert plan and plan["lines"] == [] and plan["status"] == "active"
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "cancelled"}})
    assert await bss.on_order_changed(so["id"]) is None
    assert (await db.payment_plans.find_one({"id": plan["id"]}))["status"] == "void"
    b = await _saldo(klien, await adm(KANDA), cid)
    assert (b["ar_delivered"], b["open_orders_amount"], b["overdue_amount"], b["oldest_due_date"]) == (0, 0, 0, None)


# ═══ Tambahan — kait gagal ditandai di surat jalan dan bisa diulang dari panel Posting Gagal ═════════════════════
async def test_CRT2_kait_surat_jalan_gagal_tercatat(db, klien, adm, monkeypatch):
    from services import billing_schedule_service as bss
    cid = await _pelanggan(db, KANDA, "Toko Gagal CR-T2")
    so = await _pesanan(db, cid, KANDA, 300_000)
    shid = await _kirim(db, so, 300_000, "2026-09-02", "SJ-CRT2-G")
    asli = bss.sync_order

    async def _gagal(*a, **kw):
        raise RuntimeError("uji: jadwal tagihan dipaksa gagal")
    monkeypatch.setattr(bss, "sync_order", _gagal)
    sh = await db.shipments.find_one({"id": shid}, {"_id": 0})
    assert await bss.after_shipment_journal(sh) == "failed"
    monkeypatch.setattr(bss, "sync_order", asli)
    sh = await db.shipments.find_one({"id": shid}, {"_id": 0})
    assert sh["billing_status"] == "failed" and "dipaksa gagal" in sh["billing_error"]
    r = await klien.get("/api/finance/posting-failures", headers=await adm(KANDA), params={"kind": "shipment_billing"})
    assert r.status_code == 200, r.text
    assert [x["number"] for x in r.json()["items"]] == ["SJ-CRT2-G"], r.json()
    r = await klien.post(f"/api/finance/posting-failures/shipment_billing/{shid}/retry", headers=await adm(KANDA))
    assert r.status_code == 200, r.text
    assert (await db.shipments.find_one({"id": shid}))["billing_status"] == "done"
    assert [ln["source_id"] for ln in (await _jadwal(db, so["id"]))["lines"]] == ["SJ-CRT2-G"]


# ═══ Tambahan — INV-PAY-01 untuk jadwal termin: Σ baris = billed_total ≤ nilai; = nilai bila terkirim penuh ═══════
async def test_CRT2_inv_pay_01_jadwal_termin(db, capsys):
    sys.path.insert(0, str(REPO / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    awal = dict(vdi.results)
    await vdi.layer_payment_penalty_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == awal["fail"], keluar
    assert re.search(r"PASS.*INV-PAY-01.*jadwal tagihan", keluar), keluar
    # jadwal pesanan terkirim penuh yang kurang baris → merah
    plan = await _jadwal(db, S["S1"]["id"])
    await db.payment_plans.update_one({"id": plan["id"]}, {"$set": {"lines": plan["lines"][:1]}})
    try:
        awal = dict(vdi.results)
        await vdi.layer_payment_penalty_invariants(db)
        keluar = capsys.readouterr().out
        assert vdi.results["fail"] == awal["fail"] + 1 and re.search(r"FAIL.*INV-PAY-01", keluar), keluar
    finally:
        await db.payment_plans.update_one({"id": plan["id"]}, {"$set": {"lines": plan["lines"]}})


# ═══ Tambahan — pembaca lama tidak berubah di serah-terima (a): denda dan panel rencana mengabaikan jadwal mesin ══
async def test_CRT2_a_pembaca_lama_mengabaikan_jadwal_mesin(f1, db, klien, adm):
    from services import payment_plan_service as plans
    from services import penalty_service as pen
    assert await plans.get_manual("sales_order", f1["S1"]["id"]) is None
    assert (await plans.get_active("sales_order", f1["S1"]["id"]))["origin"] == "term"
    r = await klien.get(f"/api/payment-plans/by-doc/sales_order/{f1['S1']['id']}", headers=await adm(KANDA))
    assert r.status_code == 200 and r.json()["plan"] is None, r.text
    r = await klien.get("/api/payment-plans", headers=await adm(KANDA))
    assert r.status_code == 200 and all(p.get("origin") != "term" for p in r.json()["items"]), r.text
    # CR-T4 — perilaku denda SENGAJA berubah: job memindai jadwal tagihan mesin juga (pesanan tanpa rencana cicilan
    # ikut terhitung; angka & aturan diuji di `test_CRT4_denda_berlapis.py`). Panel rencana & daftar rencana tetap
    # mengabaikan jadwal mesin (di atas).
    hasil = await pen.job_penalty_accrual()
    assert hasil["by_origin"]["term"]["scanned"] >= 1, hasil


# ═══ Skrip `scripts/build_billing_schedule.py` — baca-saja dulu, lalu tulis; idempoten; daftar status kredit berubah ═
async def test_CRT2_skrip_bangun_jadwal(db, monkeypatch):
    from services import billing_schedule_service as bss
    _beku(monkeypatch, "2026-11-20")
    sys.path.insert(0, str(REPO / "scripts"))
    skrip = importlib.import_module("build_billing_schedule")
    cid = await _pelanggan(db, KANDA, "Toko Lama CR-T2")
    lama = await _pesanan(db, cid, KANDA, 700_000)
    await _kirim(db, lama, 700_000, "2026-09-03", "SJ-CRT2-L")      # data lama: berjurnal, belum berjadwal
    jumlah_jadwal = await db.payment_plans.count_documents({})
    kering = await skrip.jalankan(apply=False)
    assert kering["schedules_created"] >= 1 and kering["lines_added"] >= 1, kering
    assert await db.payment_plans.count_documents({}) == jumlah_jadwal   # baca-saja
    ubah = {r["customer_name"]: r for r in kering["status_changes"]}
    # uang muka belum dibayar kini telat sejak konfirmasi: 20 Nov − 3 Nov = 17 hari > 14 → diblokir (dulu 0 hari)
    assert (ubah["Toko DP CR-T2"]["status_lama"], ubah["Toko DP CR-T2"]["status_baru"],
            ubah["Toko DP CR-T2"]["telat_baru"], ubah["Toko DP CR-T2"]["lewat_tempo_baru"]) == \
        ("active", "blocked", 17, 1_000_000), ubah
    assert "Toko Lama CR-T2" not in ubah   # jadwal per surat jalan = rumus lama untuk pesanan tempo tanpa DP
    tulis = await skrip.jalankan(apply=True)
    assert tulis["balances"]["pairs"] >= 1
    plan = await _jadwal(db, lama["id"])
    assert [(ln["source_id"], ln["amount"], ln["due_date"]) for ln in plan["lines"]] == \
        [("SJ-CRT2-L", 700_000, "2026-10-03")]
    ulang = await skrip.jalankan(apply=False)
    assert (ulang["schedules_created"], ulang["lines_added"], ulang["manual_line_ids"]) == (0, 0, 0), ulang
    assert (await bss.lines_for_orders([await db.sales_orders.find_one({"id": lama["id"]}, {"_id": 0})]))[
        lama["id"]]["stored"] is True
