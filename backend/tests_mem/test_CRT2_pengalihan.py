"""CR-T2 serah-terima (b) — pembaca jatuh tempo dialihkan ke jadwal tagihan (docs/blueprint/unit/CR-T2.md).

Umur piutang (`aging_report`, `customer_aging_detail`, `orders_due_soon`), status kredit (`compute_customer_credit`, dari
saldo tersimpan `customer_balance_service`), daftar tagih, proyeksi kas, dan Tanya KN membaca baris jadwal
(`billing_schedule_service.open_lines` / `lines_for_orders`) lewat `report_basis.baris_tagihan`. Bentuk jawaban dan
kelompok umur tetap; yang baru terbaca: baris uang muka dan baris rencana cicilan.

Uji (lapis B): bagian endpoint U3, U7, U8 dan U9, U10, U15 (yang terakhir sudah hijau sejak PK-41 dan harus tetap hijau).
Tiap uji memakai pelanggan + pesanan F1 sendiri (`ent_kanda`, NET30, Rp 1.000.000, SJ-1 1 Sep 2026 Rp 400.000) supaya
langkah uji lain tidak tercampur. FIXTURE: pelanggan, pesanan, surat jalan + jurnal; ALUR: endpoint di bawah; kait `on_*`
dipanggil sebagai fungsi.

Hitung tangan:
  U3  15 Nov − 1 Okt = 45 hari → kolom 31–60: 400.000; belum dikirim 1.000.000 − 400.000 = 600.000 → belum jatuh tempo.
  U7  DP50 Rp 2.000.000 dikonfirmasi 3 Nov, surat jalan 6 Nov Rp 800.000: per 20 Nov uang muka 1.000.000 telat
      20 − 3 = 17 hari → kolom 1–30 (sebelum unit ini 0); baris surat jalan 400.000 jatuh tempo 20 Nov (0 hari) +
      belum ditagih 2.000.000 − 1.000.000 − 400.000 = 600.000 → belum jatuh tempo 1.000.000; tercatat = jurnal 800.000.
  U8  rencana cicilan 500.000 (15 Sep) + 500.000 (15 Okt); per 20 Okt: 35 hari → 31–60 500.000, 5 hari → 1–30 500.000;
      telat terlama 35 (sebelum unit ini satu baris 1 Okt → 19 hari).
  U9  kwitansi 400.000 tgl 5 Nov: per 31 Okt (30 hari) 1–30 400.000 + belum jatuh tempo 600.000; per 15 Nov hanya 600.000.
  U10 20 Okt − 1 Okt = 19 hari > 14 (bawaan `ar.overdue_block_days`) → diblokir; lewat tempo 400.000 (bukan 1.000.000).
  U15 20 Sep: 400.000 jatuh tempo 1 Okt (11 hari lagi); 600.000 perkiraan 20 Sep + 30 = 20 Okt (belum dikirim).
"""
from __future__ import annotations

import datetime
import uuid

import pytest

pytestmark = pytest.mark.anyio

ADMIN = "admin@kainnusantara.id"
KANDA = "ent_kanda"


def _id(awal: str) -> str:
    return f"{awal}_crt2b_{uuid.uuid4().hex[:8]}"


def _jam(tanggal: str) -> str:
    return f"{tanggal}T03:00:00+00:00"


def _beku(monkeypatch, tanggal_wib: str, jam_wib: int = 10):
    from services import book_date
    d = datetime.date.fromisoformat(tanggal_wib)
    beku = datetime.datetime(d.year, d.month, d.day, jam_wib, 0, tzinfo=book_date.WIB).astimezone(datetime.timezone.utc)
    monkeypatch.setattr(book_date, "_sekarang", lambda: beku)


@pytest.fixture(scope="module")
async def h(sesi):
    return await sesi(ADMIN, entitas=KANDA)


async def _f1(db, nama: str, *, total=1_000_000, term="NET30", hari=30, confirmed="2026-08-25",
              status="partially_shipped", kirim=((400_000, "2026-09-01"),)) -> dict:
    from services import billing_schedule_service as bss
    from services import gl_service as gl
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": nama, "entity_id": KANDA, "status": "active",
                                   "payment_profile": {}, "deposit_balance": 0.0, "assigned_sales_id": ""})
    so = {"id": _id("so"), "number": f"SO-CRT2B-{uuid.uuid4().hex[:5]}", "entity_id": KANDA, "customer_id": cid,
          "customer_name": nama, "status": status, "grand_total": float(total), "total_amount": float(total),
          "ppn_amount": 0.0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "payment_term_code": term,
          "items": [], "created_at": _jam(confirmed), "confirmed_at": _jam(confirmed)}
    if hari is not None:
        so["payment_term_days"] = hari
    await db.sales_orders.insert_one(dict(so))
    await bss.on_order_confirmed(so["id"])
    for i, (nilai, tgl) in enumerate(kirim, 1):
        shid, nomor = _id("shp"), f"SJ-{so['number'][-5:]}-{i}"
        await db.shipments.insert_one({"id": shid, "shipment_no": nomor, "order_id": so["id"], "entity_id": KANDA,
                                       "status": "dispatched", "created_at": _jam(tgl)})
        await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": float(nilai), "credit": 0.0},
                                      {"account_code": "4-1000", "debit": 0.0, "credit": float(nilai)}],
                               description=f"Pengakuan penjualan {so['number']} · {nomor}", date=_jam(tgl),
                               source_type="shipment_revenue", source_id=shid, entity_id=KANDA, created_by="system",
                               source_label=nomor, ref={"order_id": so["id"], "order_number": so["number"]})
        await bss.on_shipment_posted(so["id"], nomor)
    return {"cus": cid, "so": so}


async def _baris_umur(klien, h, cid, **params):
    r = await klien.get("/api/ar/aging", headers=h, params=params)
    assert r.status_code == 200, r.text
    (row,) = [c for c in r.json()["customers"] if c["customer_id"] == cid]
    return row, r.json()


# ═══ U3 — umur piutang per surat jalan dari jadwal tersimpan = hasil PK-41 ═══════════════════════════════════════
async def test_CRT2_U3_umur_piutang_dari_jadwal(db, klien, h):
    f = await _f1(db, "Toko U3 CR-T2")
    row, j = await _baris_umur(klien, h, f["cus"], as_of="2026-11-15")
    assert (row["b31_60"], row["current"], row["outstanding"], row["ar_ledger"], row["exposure"]) == \
        (400_000, 600_000, 1_000_000, 400_000, 600_000)
    assert j["reconciliation"]["difference"] == 0
    r = await klien.get(f"/api/ar/aging/{f['cus']}", headers=h, params={"as_of": "2026-11-15"})
    (item,) = r.json()["items"]
    assert [(ln["sumber"], ln["jatuh_tempo"], ln["sisa"], ln["hari_lewat"]) for ln in item["lines"]] == \
        [("surat_jalan", "2026-10-01", 400_000, 45), ("belum_dikirim", None, 600_000, 0)]
    assert item["lines"][0]["line_id"].startswith("ppl_") and item["lines"][0]["jurnal_number"]


# ═══ U7 — uang muka belum dibayar telat sejak konfirmasi (sebelum unit ini 0) ═════════════════════════════════════
async def test_CRT2_U7_uang_muka_terbaca_umur_piutang(db, klien, h):
    f = await _f1(db, "Toko U7 CR-T2", total=2_000_000, term="DP50", hari=None, confirmed="2026-11-03",
                  kirim=((800_000, "2026-11-06"),))
    row, j = await _baris_umur(klien, h, f["cus"], as_of="2026-11-20")
    assert (row["b1_30"], row["current"], row["outstanding"], row["oldest_days"]) == \
        (1_000_000, 1_000_000, 2_000_000, 17)
    assert (row["ar_ledger"], row["exposure"]) == (800_000, 1_200_000)   # tercatat = jurnal surat jalan 800.000
    assert j["reconciliation"]["ar_ledger_total"] == j["reconciliation"]["gl_balance"] - (
        j["reconciliation"]["difference"] or 0)
    r = await klien.get(f"/api/ar/aging/{f['cus']}", headers=h, params={"as_of": "2026-11-20"})
    (item,) = r.json()["items"]
    assert [(ln["sumber"], ln["label"], ln["jatuh_tempo"], ln["sisa"], ln["hari_lewat"]) for ln in item["lines"]] == [
        ("uang_muka", "Uang muka 50%", "2026-11-03", 1_000_000, 17),
        ("surat_jalan", f"Surat jalan SJ-{f['so']['number'][-5:]}-1", "2026-11-20", 400_000, 0),
        ("belum_dikirim", "", None, 600_000, 0)]


# ═══ U8 — rencana cicilan menentukan telat (sebelum unit ini satu baris 19 hari) ═══════════════════════════════════
async def test_CRT2_U8_rencana_cicilan_menentukan_telat(db, klien, h, monkeypatch):
    _beku(monkeypatch, "2026-10-20")
    f = await _f1(db, "Toko U8 CR-T2", status="shipped", kirim=((1_000_000, "2026-09-01"),))
    r = await klien.post("/api/payment-plans", headers=h, json={
        "doc_type": "sales_order", "doc_id": f["so"]["id"], "mode": "custom", "lines": [
            {"kind": "installment", "label": "Cicilan 1", "amount": 500_000, "due_rule": "fixed_date",
             "due_date": "2026-09-15"},
            {"kind": "installment", "label": "Cicilan 2", "amount": 500_000, "due_rule": "fixed_date",
             "due_date": "2026-10-15"}]})
    assert r.status_code == 200, r.text
    row, _ = await _baris_umur(klien, h, f["cus"])
    assert (row["b31_60"], row["b1_30"], row["current"], row["oldest_days"]) == (500_000, 500_000, 0, 35)
    r = await klien.get(f"/api/customers/{f['cus']}/credit-status", headers=h)
    assert r.status_code == 200, r.text
    c = r.json()["credit"]
    assert (c["max_overdue_days"], c["overdue_amount"], c["ar_outstanding"], c["status"]) == \
        (35, 1_000_000, 1_000_000, "blocked")


# ═══ U9 — posisi per tanggal: pembayaran sesudahnya belum dihitung (RP-05) ═══════════════════════════════════════
async def test_CRT2_U9_posisi_per_tanggal(db, klien, h):
    f = await _f1(db, "Toko U9 CR-T2")
    await db.sales_orders.update_one({"id": f["so"]["id"]}, {"$push": {"payments": {
        "id": _id("pay"), "kind": "kas", "amount": 400_000.0, "method": "transfer", "date": _jam("2026-11-05"),
        "created_at": _jam("2026-11-05")}}, "$set": {"paid_total": 400_000.0, "payment_status": "partial"}})
    row, _ = await _baris_umur(klien, h, f["cus"], as_of="2026-10-31")
    assert (row["b1_30"], row["current"], row["outstanding"]) == (400_000, 600_000, 1_000_000)
    row, _ = await _baris_umur(klien, h, f["cus"], as_of="2026-11-15")
    assert (row["b1_30"], row["b31_60"], row["current"], row["outstanding"]) == (0, 0, 600_000, 600_000)


# ═══ U10 — status kredit dari saldo tersimpan: hanya bagian terkirim yang telat ═════════════════════════════════
async def test_CRT2_U10_status_kredit(db, klien, h, monkeypatch):
    _beku(monkeypatch, "2026-10-20")
    f = await _f1(db, "Toko U10 CR-T2")
    r = await klien.get(f"/api/customers/{f['cus']}/credit-status", headers=h)
    assert r.status_code == 200, r.text
    c = r.json()["credit"]
    assert (c["overdue_amount"], c["max_overdue_days"], c["status"]) == (400_000, 19, "blocked")
    assert (c["ar_outstanding"], c["ar_ledger"], c["exposure"]) == (1_000_000, 400_000, 600_000)
    row = await db.customer_balances.find_one({"customer_id": f["cus"], "entity_id": KANDA}, {"_id": 0})
    assert (row["overdue_amount"], row["overdue_as_of"], row["oldest_due_date"]) == (400_000, "2026-10-20",
                                                                                      "2026-10-01")


# ═══ U15 — proyeksi kas: uang masuk pada jatuh tempo baris; belum dikirim = perkiraan ═════════════════════════════
async def test_CRT2_U15_proyeksi_kas(db, klien, h, monkeypatch):
    _beku(monkeypatch, "2026-09-20")
    f = await _f1(db, "Toko U15 CR-T2")
    r = await klien.get("/api/finance/cashflow-forecast", headers=h, params={"entity_id": KANDA})
    assert r.status_code == 200, r.text
    its = [i for i in r.json()["ar_items"] if i["number"] == f["so"]["number"]]
    assert sorted((i["amount"], i["due_date"], i["due_basis"]) for i in its) == [
        (400_000, "2026-10-01", "per_sj"), (600_000, "2026-10-20", "estimate_not_shipped")]


# ═══ Tambahan — pengingat H-x dan daftar tagih membaca baris jadwal (uang muka ikut) ═══════════════════════════════
async def test_CRT2_b_pengingat_dan_daftar_tagih(db, monkeypatch):
    from services import ar_aging_service as ara
    from services import customer_service as cs
    _beku(monkeypatch, "2026-11-04")
    f = await _f1(db, "Toko Ingat CR-T2", total=2_000_000, term="DP50", hari=None, confirmed="2026-11-03", kirim=())
    rows = await ara.orders_due_soon([1], entity_id=KANDA)
    assert [(r["order_id"], r["due_date"], r["outstanding"]) for r in rows if r["customer_id"] == f["cus"]] == \
        [(f["so"]["id"], "2026-11-03", 1_000_000)]   # H+1 uang muka
    wl = await cs.collection_worklist({"id": "usr_uji", "role": "admin"}, entity_id=KANDA)
    (w,) = [x for x in wl if x["customer_id"] == f["cus"]]
    assert (w["due_date"], w["days_late"], w["overdue"]) == ("2026-11-03", 1, True)


# ═══ Tambahan — job harian 00.10 WIB: pergantian hari mengubah lewat tempo tanpa dokumen baru ═══════════════════
async def test_CRT2_b_job_harian_lewat_tempo(db, monkeypatch):
    from services import customer_balance_service as cbs
    from services import scheduler_service as sch
    assert sch.JOB_MAP["customer_balance_overdue"]["fn"] is cbs.job_refresh_overdue
    assert (sch.JOB_MAP["customer_balance_overdue"]["hour"], sch.JOB_MAP["customer_balance_overdue"]["minute"]) == (0, 10)
    _beku(monkeypatch, "2026-09-30")
    f = await _f1(db, "Toko Job CR-T2")   # jatuh tempo 1 Okt: per 30 Sep belum lewat
    row = await db.customer_balances.find_one({"customer_id": f["cus"], "entity_id": KANDA}, {"_id": 0})
    assert (row["overdue_amount"], row["overdue_as_of"]) == (0, "2026-09-30")
    _beku(monkeypatch, "2026-10-02")
    hasil = await cbs.job_refresh_overdue()
    assert hasil["refreshed"] >= 1 and hasil["as_of"] == "2026-10-02"
    row = await db.customer_balances.find_one({"customer_id": f["cus"], "entity_id": KANDA}, {"_id": 0})
    assert (row["overdue_amount"], row["overdue_as_of"], row["oldest_due_date"]) == (400_000, "2026-10-02", "2026-10-01")
