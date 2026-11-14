"""PK-19 serah-terima (b) — kwitansi, deposit, selisih bayar lewat satu fungsi alokasi (alur lewat API).

docs/blueprint/unit/PK-19.md uji penerimaan U1–U14 dan U17 (lingkungan B). U15–U16 (dua permintaan bersamaan) di
MongoDB asli: `backend/tests/test_bp_PK19_bersamaan_mongo.py`.

Persiapan bersama (fixture, disisipkan langsung): `ent_ksc` dengan satu rekening Bank `rek_pk19_b` dan satu rekening
Kas Kecil `rek_pk19_k`; pelanggan A dan B; tiap uji membuat pesanannya sendiri: A1 Rp 1.000.000 dan A2 Rp 500.000
(terkirim, pendapatan sudah dijurnal Dr 1-1200 / Cr 4-1000 sehingga pelunasannya mengkredit Piutang), B1 Rp 800.000
(milik B), X1 milik A di `ent_kanda`; toleransi selisih 0 (`payment.variance_tolerance_rupiah` dan
`payment.variance_ap_tolerance_rupiah` per PT); `ensure_reasons()`. Deposit pelanggan dan kwitansi berselisih yang
dipakai keputusan = fixture; kwitansi, batal, keputusan, batal keputusan, bayar faktur, alokasi titipan = alur API.

Hitung tangan (contoh angka `00` §9):
  U4  deposit 1.000.000; alih A1 300.000 (jadi) + A2 200.000 (dipaksa gagal, depositnya dikembalikan)
      → deposit 1.000.000 − 300.000 = 700.000; jurnal Dr 2-1400 300.000 / Cr 1-1200 300.000.
  U5  ulang → A2 200.000 → deposit 700.000 − 200.000 = 500.000; dua jurnal alih (300.000 + 200.000).
  U8  K3 990.000 ke A1 1.000.000 → kurang 10.000 → hapus sisa: Dr 6-9100 10.000 / Cr 1-1200 10.000;
      sisa A1 = 1.000.000 − 990.000 − 10.000 = 0.
  U11 faktur 5.000.000, dibayar 4.990.000 (Dr 2-1100 4.990.000 / Cr 1-1100), tutup sisa 10.000 (Dr 2-1100 10.000 /
      Cr 4-9000 10.000), dibatalkan (Dr 4-9000 10.000 / Cr 2-1100 10.000) → saldo 2-1100 faktur =
      5.000.000 − 4.990.000 − 10.000 + 10.000 = 10.000 = sisa `bill_financials`.
"""
from __future__ import annotations

import datetime
import itertools
import re
import uuid
from pathlib import Path

import pytest

from core_utils import now_iso
from pembantu import aktifkan_akun, jumlah, nonaktifkan_akun, tutup_periode
from services import config_resolver as resolver

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
JT = 1_000_000
_n = itertools.count(1)
REPO = Path(__file__).resolve().parents[2]


def _id(awal: str) -> str:
    return f"{awal}_pk19_{uuid.uuid4().hex[:8]}"


def _hari(delta: int = 0) -> str:
    return (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
            + datetime.timedelta(days=delta)).date().isoformat()


@pytest.fixture(scope="module")
async def dunia(db, kepala_admin):
    from services import amendment_service
    await amendment_service.ensure_reasons()
    for key in ("payment.variance_tolerance_rupiah", "payment.variance_ap_tolerance_rupiah"):
        await resolver.set_value(key, 0, scope_type="entity", scope_id=KSC, actor="uji", reason="uji PK-19")
    await db.bank_accounts.insert_many([
        {"id": "rek_pk19_b", "name": "BCA KSC PK19", "entity_id": KSC, "account_type": "bank",
         "cash_type": "kas_besar", "is_active": True, "opening_balance": 0},
        {"id": "rek_pk19_k", "name": "Kas Kecil KSC PK19", "entity_id": KSC, "account_type": "cash",
         "cash_type": "kas_kecil", "is_active": True, "opening_balance": 0}])
    out = {}
    for k in ("A", "B"):
        cid = _id(f"cus{k.lower()}")
        await db.customers.insert_one({"id": cid, "name": f"Toko {k} PK19", "entity_id": KSC, "status": "active",
                                       "deposit_balance": 0.0})
        out[k] = cid
    return out


async def _pesanan(db, cus, total, *, ent=KSC, status="shipped", label="", jurnal=True) -> dict:
    """Fixture pesanan; `jurnal` = pendapatan sudah lahir (Dr 1-1200 / Cr 4-1000) → pelunasannya mengkredit Piutang."""
    i = next(_n)
    so = {"id": _id("so"), "number": f"SO-PK19-{label}{i}", "entity_id": ent, "customer_id": cus,
          "customer_name": "Toko PK19", "status": status, "grand_total": float(total), "payments": [],
          "paid_total": 0.0, "payment_status": "unpaid", "payment_term_code": "NET30", "items": [],
          "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    if jurnal:
        from services import gl_service as gl
        await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": float(total), "credit": 0.0},
                                      {"account_code": "4-1000", "debit": 0.0, "credit": float(total)}],
                               description=f"pendapatan {so['number']} (fixture)", date=now_iso(),
                               source_type="sales_order", source_id=so["id"], entity_id=ent, created_by="uji")
    return so


async def _deposit(db, cus, nilai):
    await db.customers.update_one({"id": cus}, {"$set": {"deposit_balance": float(nilai)}})


async def _saldo_deposit(db, cus) -> float:
    return float((await db.customers.find_one({"id": cus}) or {}).get("deposit_balance") or 0)


async def _kwitansi_lebih(db, cus, lebih, *, pembuat="usr_lain_pk19") -> str:
    """Fixture kwitansi yang LEBIH bayar `lebih` (selisih menunggu keputusan)."""
    rc = _id("arc")
    await db.ar_receipts.insert_one({
        "id": rc, "number": f"KW-PK19-{next(_n)}", "entity_id": KSC, "status": "posted", "customer_id": cus,
        "customer_name": "Toko PK19", "created_by": pembuat, "receipt_date": now_iso(), "created_at": now_iso(),
        "amount": float(lebih), "total_funds": float(lebih), "applied_total": 0.0, "unapplied_amount": float(lebih),
        "allocations": [],
        "variance": {"direction": "over", "delta": float(lebih), "expected": 0.0, "funds": float(lebih),
                     "capacity": 0.0, "needs_decision": True, "target_order_ids": [], "decision_id": "",
                     "tolerance": 0}})
    return rc


async def _kwitansi(klien, h, cus, amount, allocs, *, method="transfer", tanggal="", deposit=0.0, rek="rek_pk19_b"):
    body = {"customer_id": cus, "amount": amount, "method": method, "entity_id": KSC, "use_deposit_amount": deposit,
            "account_id": rek if amount else "",
            "allocations": [{"order_id": o["id"], "amount": a} for o, a in allocs]}
    if tanggal:
        body["receipt_date"] = tanggal
    return await klien.post("/api/ar-receipts", headers=h, json=body)


async def _putus(klien, h, rc, kind, **kw):
    reason = {"writeoff": "uncollectible_small", "allocate": "customer_overtransfer",
              "refund": "customer_refund_request"}[kind]
    return await klien.post(f"/api/payment-variances/receipt/{rc}/decide", headers=h,
                            json={"kind": kind, "reason_code": reason, "note": "uji PK-19", **kw})


async def _jurnal(db, source_type, awalan):
    return await db.journal_entries.find({"source_type": source_type, "status": {"$ne": "void"},
                                          "source_id": {"$regex": "^" + re.escape(awalan)}}, {"_id": 0}).to_list(50)


def _baris(jes):
    return sorted((ln["account_code"], float(ln.get("debit") or 0), float(ln.get("credit") or 0))
                  for j in jes for ln in j.get("lines") or [])


async def _so(db, so):
    return await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})


# ── U1–U3 — satu pemeriksa: pelanggan, PT, status pesanan ──────────────────────────────────────────────────────────
async def test_PK19_U1_alih_deposit_ke_pelanggan_lain_ditolak(klien, kepala_admin, db, dunia):
    b1 = await _pesanan(db, dunia["B"], 800_000, label="B1-")
    await _deposit(db, dunia["A"], 300_000)
    rc = await _kwitansi_lebih(db, dunia["A"], 300_000)
    r = await _putus(klien, kepala_admin, rc, "allocate", allocations=[{"order_id": b1["id"], "amount": 300_000}])
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == (f"Pesanan {b1['number']} milik pelanggan lain. Dana ini hanya bisa dipakai untuk "
                                  "pesanan pelanggan yang sama.")
    assert await _saldo_deposit(db, dunia["A"]) == 300_000
    assert (await _so(db, b1))["payments"] == []
    assert await jumlah("payment_variance_decisions", {"receipt_id": rc}) == 0


async def test_PK19_U2_alih_deposit_ke_pt_lain_ditolak(klien, kepala_admin, db, dunia):
    x1 = await _pesanan(db, dunia["A"], 1 * JT, ent=KANDA, label="X1-")
    await _deposit(db, dunia["A"], 300_000)
    rc = await _kwitansi_lebih(db, dunia["A"], 300_000)
    r = await _putus(klien, kepala_admin, rc, "allocate", allocations=[{"order_id": x1["id"], "amount": 300_000}])
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == f"Pesanan {x1['number']} milik PT lain. Piutangnya tidak bisa dilunasi dari dana PT ini."
    assert await _saldo_deposit(db, dunia["A"]) == 300_000
    assert (await _so(db, x1))["payments"] == []


async def test_PK19_U3_kwitansi_ke_pesanan_batal_ditolak(klien, kepala_admin, db, dunia):
    a2 = await _pesanan(db, dunia["A"], 500_000, status="cancelled", label="A2-")
    n_rc, n_kas = await jumlah("ar_receipts", {}), await jumlah("cash_transactions", {})
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 500_000, [(a2, 500_000)])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"Pesanan {a2['number']} berstatus Dibatalkan, jadi tidak bisa menerima pembayaran."
    assert await jumlah("ar_receipts", {}) == n_rc and await jumlah("cash_transactions", {}) == n_kas
    assert (await _so(db, a2))["payments"] == []


# ── U4–U5 — alih deposit per baris, gagal di tengah lalu diteruskan ────────────────────────────────────────────────
async def test_PK19_U4_U5_alih_deposit_gagal_di_tengah_lalu_diteruskan(klien, kepala_admin, db, dunia, monkeypatch):
    from services import ar_allocation_service as aas
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="A1-")
    a2 = await _pesanan(db, dunia["A"], 500_000, label="A2-")
    await _deposit(db, dunia["A"], 1 * JT)
    rc = await _kwitansi_lebih(db, dunia["A"], 1 * JT)
    asli = aas.allocate

    async def _a2_gagal(**kw):
        if kw.get("order_id") == a2["id"]:
            raise RuntimeError("uji: tulisan alokasi dipaksa gagal")
        return await asli(**kw)
    monkeypatch.setattr(aas, "allocate", _a2_gagal)
    rows = [{"order_id": a1["id"], "amount": 300_000}, {"order_id": a2["id"], "amount": 200_000}]
    r = await _putus(klien, kepala_admin, rc, "allocate", allocations=rows)
    assert r.status_code >= 400, r.text
    # U4 — deposit = 1.000.000 − 300.000 = 700.000; A1 berbaris deposit 300.000; A2 tanpa baris; keputusan failed.
    assert await _saldo_deposit(db, dunia["A"]) == 700_000
    assert [(p["kind"], p["amount"]) for p in (await _so(db, a1))["payments"]] == [("deposit", 300_000)]
    assert (await _so(db, a2))["payments"] == []
    dec = await db.payment_variance_decisions.find_one({"receipt_id": rc}, {"_id": 0})
    assert dec["status"] == "failed"
    jes = await _jurnal(db, "payment_variance_alloc", dec["id"])
    assert len(jes) == 1 and _baris(jes) == [("1-1200", 0.0, 300_000.0), ("2-1400", 300_000.0, 0.0)]
    # U5 — paksaan dicabut, keputusan yang sama dikirim lagi → diteruskan.
    monkeypatch.setattr(aas, "allocate", asli)
    r = await _putus(klien, kepala_admin, rc, "allocate", allocations=rows)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done" and r.json()["id"] == dec["id"] and r.json()["gl_status"] == "posted"
    assert await _saldo_deposit(db, dunia["A"]) == 500_000
    assert len((await _so(db, a1))["payments"]) == 1
    assert [(p["kind"], p["amount"]) for p in (await _so(db, a2))["payments"]] == [("deposit", 200_000)]
    jes = await _jurnal(db, "payment_variance_alloc", dec["id"])
    assert sorted(j["total_debit"] for j in jes) == [200_000, 300_000]
    # Pilihan berbeda atas kwitansi yang sudah diputus → 409.
    r = await _putus(klien, kepala_admin, rc, "refund")
    assert r.status_code == 409, r.text


# ── U6–U7 — batal kwitansi: niat, langkah bertanda, baris pembalik bertanggal ─────────────────────────────────────
async def test_PK19_U6_batal_kwitansi_gagal_di_tengah_lalu_diulang(klien, kepala_admin, db, dunia, monkeypatch):
    from services import ar_allocation_service as aas
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="A1-")
    await _deposit(db, dunia["A"], 0)
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 1_200_000, [(a1, 1 * JT)], method="tunai", rek="rek_pk19_k")
    assert r.status_code == 200, r.text
    k1 = r.json()
    assert k1["unapplied_amount"] == 200_000 and await _saldo_deposit(db, dunia["A"]) == 200_000

    async def _gagal(**kw):
        raise RuntimeError("uji: langkah pesanan dipaksa gagal")
    monkeypatch.setattr(aas, "reverse", _gagal)
    r = await klien.post(f"/api/ar-receipts/{k1['id']}/void", headers=kepala_admin, params={"reason": "uji U6"})
    assert r.status_code >= 400, r.text
    doc = await db.ar_receipts.find_one({"id": k1["id"]}, {"_id": 0})
    assert doc["status"] != "void" and "saga_lock" not in doc
    assert doc["void_intent"]["status"] == "pending" and doc["void_intent"]["steps"]["deposit_pulled"] is True
    assert await _saldo_deposit(db, dunia["A"]) == 0
    monkeypatch.undo()
    r = await klien.post(f"/api/ar-receipts/{k1['id']}/void", headers=kepala_admin, params={"reason": "uji U6"})
    assert r.status_code == 200, r.text
    doc = await db.ar_receipts.find_one({"id": k1["id"]}, {"_id": 0})
    assert doc["status"] == "void" and "saga_lock" not in doc and doc["void_intent"]["status"] == "done"
    assert doc["void_intent"]["steps"]["orders"] == [a1["id"]] and doc["void_gl_status"] == "posted"
    assert r.json()["void_gl_status"] == "posted"
    assert await _saldo_deposit(db, dunia["A"]) == 0   # turun 200.000 tepat sekali
    assert sum(p["amount"] for p in (await _so(db, a1))["payments"]) == 0


async def test_PK19_U7_batal_kwitansi_baris_pembalik_bertanggal(klien, kepala_admin, db, dunia):
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="A1-")
    tgl10 = _hari(-4)
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 1 * JT, [(a1, 1 * JT)], tanggal=tgl10)
    assert r.status_code == 200, r.text
    k2 = r.json()
    r = await klien.post(f"/api/ar-receipts/{k2['id']}/void", headers=kepala_admin, params={"reason": "uji U7"})
    assert r.status_code == 200, r.text
    so = await _so(db, a1)
    asal, balik = so["payments"]
    assert (asal["amount"], asal["date"][:10], asal["reversed_by"]) == (1 * JT, tgl10, balik["id"])
    assert (balik["amount"], balik["reverses"], balik["receipt_id"]) == (-1 * JT, asal["id"], k2["id"])
    assert balik["date"][:10] != tgl10 and balik["date"] >= asal["date"]
    assert sum(p["amount"] for p in so["payments"]) == 0 and so["payment_status"] == "unpaid"


async def test_PK19_U7b_batal_kwitansi_yang_sudah_dipindah_kasus_ditolak(klien, kepala_admin, db, dunia):
    """Tabel galat "Pembalik membuat terbayar negatif" (ASUMSI unit): pembayaran K sudah dipindah lewat kasus
    (penarikan realokasi = fixture lewat modul alokasi) → batal K = 409 di PERIKSA; tidak ada niat, baris, maupun kunci."""
    from services import ar_allocation_service as aas
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="A1-")
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 1 * JT, [(a1, 1 * JT)])
    assert r.status_code == 200, r.text
    k = r.json()
    await aas.withdraw(kind="kasus", order_id=a1["id"], amount=1 * JT, source_id="fcs_pk19", source_number="KAS-PK19",
                       customer_id=dunia["A"], entity_id=KSC, date=now_iso(), actor="uji", method="realokasi")
    r = await klien.post(f"/api/ar-receipts/{k['id']}/void", headers=kepala_admin, params={"reason": "uji U7b"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == (f"Pembayaran {k['number']} pada pesanan {a1['number']} sudah dipindahkan lewat "
                                  "dokumen lain. Batalkan pemindahan itu dulu.")
    doc = await db.ar_receipts.find_one({"id": k["id"]}, {"_id": 0})
    assert doc["status"] == "posted" and "void_intent" not in doc and "saga_lock" not in doc
    assert [p["amount"] for p in (await _so(db, a1))["payments"]] == [1 * JT, -1 * JT]


# ── U8–U9 — hapus sisa: klaim keputusan, satu jurnal, gagal jurnal lalu diulang ───────────────────────────────────
async def test_PK19_U8_hapus_sisa_dua_kali_berurutan(klien, kepala_admin, db, dunia):
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="A1-")
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 990_000, [(a1, 990_000)])
    assert r.status_code == 200, r.text
    k3 = r.json()
    assert k3["variance"]["direction"] == "under" and k3["variance"]["delta"] == -10_000
    r1 = await _putus(klien, kepala_admin, k3["id"], "writeoff")
    r2 = await _putus(klien, kepala_admin, k3["id"], "writeoff")
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"] == f"Selisih kwitansi {k3['number']} sedang atau sudah diputus (Hapus sisa kurang bayar)."
    so = await _so(db, a1)
    hapus = [p for p in so["payments"] if p.get("kind") == "hapus_sisa"]
    assert [p["amount"] for p in hapus] == [10_000] and hapus[0]["method"] == "writeoff"
    jes = await _jurnal(db, "payment_variance_writeoff", r1.json()["id"])
    assert len(jes) == 1 and _baris(jes) == [("1-1200", 0.0, 10_000.0), ("6-9100", 10_000.0, 0.0)]
    assert round(so["grand_total"] - sum(p["amount"] for p in so["payments"]), 2) == 0   # 1.000.000 − 990.000 − 10.000
    assert r1.json()["status"] == "done" and r1.json()["gl_status"] == "posted"


async def test_PK19_U9_hapus_sisa_jurnal_gagal_lalu_diulang_dari_panel(klien, kepala_admin, db, dunia):
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="A1-")
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 990_000, [(a1, 990_000)])
    assert r.status_code == 200, r.text
    k3 = r.json()
    await nonaktifkan_akun(KSC, "6-9100")
    try:
        r = await _putus(klien, kepala_admin, k3["id"], "writeoff")
    finally:
        await aktifkan_akun(KSC, "6-9100")
    assert r.status_code == 200, r.text
    dec = r.json()
    assert dec["status"] == "done" and dec["gl_status"] == "failed" and "6-9100" in dec["gl_error"]
    panel = await klien.get("/api/finance/posting-failures", headers=kepala_admin, params={"kind": "payment_variance"})
    assert panel.status_code == 200, panel.text
    assert [x["id"] for x in panel.json()["items"]] == [dec["id"]]
    assert panel.json()["items"][0]["amount"] == 10_000
    r = await klien.post(f"/api/finance/posting-failures/payment_variance/{dec['id']}/retry", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["gl_status"] == "posted"
    assert len(await _jurnal(db, "payment_variance_writeoff", dec["id"])) == 1
    d = await db.payment_variance_decisions.find_one({"id": dec["id"]}, {"_id": 0})
    assert d["gl_status"] == "posted" and d["je_id"]


# ── U10 — batal kwitansi di periode tertutup ──────────────────────────────────────────────────────────────────────
async def test_PK19_U10_batal_kwitansi_periode_tertutup(klien, kepala_admin, db, dunia):
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="A1-")
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 1 * JT, [(a1, 1 * JT)])
    assert r.status_code == 200, r.text
    k4 = r.json()
    sebelum_so = await _so(db, a1)
    sebelum_kas = await db.cash_transactions.find({"ref_id": k4["id"]}, {"_id": 0}).to_list(10)
    dep = await _saldo_deposit(db, dunia["A"])
    c = await tutup_periode(KSC, _hari()[:7])
    try:
        r = await klien.post(f"/api/ar-receipts/{k4['id']}/void", headers=kepala_admin, params={"reason": "uji U10"})
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409, r.text
    assert "tertutup" in r.text.lower() or "ditutup" in r.text.lower(), r.text
    doc = await db.ar_receipts.find_one({"id": k4["id"]}, {"_id": 0})
    assert doc["status"] == "posted" and "void_intent" not in doc and "saga_lock" not in doc
    assert (await _so(db, a1))["payments"] == sebelum_so["payments"]
    assert await db.cash_transactions.find({"ref_id": k4["id"]}, {"_id": 0}).to_list(10) == sebelum_kas
    assert await _saldo_deposit(db, dunia["A"]) == dep


# ── U11 — batal keputusan sisi hutang ─────────────────────────────────────────────────────────────────────────────
async def test_PK19_U11_batal_tutup_sisa_hutang(klien, kepala_admin, db, dunia):
    from services import gl_service as gl
    from services.vendor_bill_service import bill_financials
    vb = _id("vb")
    await db.vendor_bills.insert_one({
        "id": vb, "bill_number": vb.upper(), "entity_id": KSC, "supplier_id": "sup_pk19", "supplier_name": "Pemasok",
        "status": "posted", "grand_total": 5 * JT, "subtotal": 5 * JT, "amount_paid": 0.0, "payments": [],
        "timeline": [], "po_id": None, "bill_date": _hari(), "created_at": now_iso()})
    await gl._insert_entry(lines=[{"account_code": "5-1000", "debit": 5 * JT, "credit": 0.0},
                                  {"account_code": "2-1100", "debit": 0.0, "credit": 5 * JT}],
                           description="faktur pemasok (fixture)", date=now_iso(), source_type="vendor_bill",
                           source_id=vb, entity_id=KSC, created_by="uji")
    r = await klien.post(f"/api/vendor-bills/{vb}/pay", headers={**kepala_admin, "Idempotency-Key": _id("k")}, json={
        "amount": 4_990_000, "paid_at": _hari(), "bank_account_id": "rek_pk19_b",
        "variance": {"kind": "ap_writeoff", "reason_code": "supplier_discount", "note": "uji U11"}})
    assert r.status_code == 200, r.text
    dec = await db.payment_variance_decisions.find_one({"bill_id": vb}, {"_id": 0})
    assert dec and dec["kind"] == "ap_writeoff" and dec["amount"] == 10_000 and dec["gl_status"] == "posted"
    tutup = await db.vendor_bills.find_one({"id": vb}, {"_id": 0})
    # Sebelum dibatalkan: 5.000.000 − 4.990.000 − 10.000 (ditutup) = 0 → lunas.
    assert tutup["status"] == "paid" and bill_financials(tutup)["outstanding"] == 0
    r = await klien.post(f"/api/payment-variances/{dec['id']}/reverse", headers=kepala_admin,
                         json={"reason": "uji batal potongan"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "reversed" and r.json()["reversal_gl_status"] == "posted"
    rev = await _jurnal(db, "payment_variance_reversal", f"{dec['id']}:rev")
    assert len(rev) == 1 and _baris(rev) == [("2-1100", 0.0, 10_000.0), ("4-9000", 10_000.0, 0.0)]
    bill = await db.vendor_bills.find_one({"id": vb}, {"_id": 0})
    kas = [p.get("cash_txn_id") for p in bill.get("payments") or []]
    sumber = {vb, dec["id"], f"{dec['id']}:rev", *[k for k in kas if k]}
    saldo = 0.0
    async for je in db.journal_entries.find({"source_id": {"$in": list(sumber)}, "status": {"$ne": "void"}}):
        saldo += sum(float(ln.get("credit") or 0) - float(ln.get("debit") or 0)
                     for ln in je["lines"] if ln["account_code"] == "2-1100")
    assert round(saldo, 2) == 10_000 == bill_financials(bill)["outstanding"]
    assert bill["status"] != "paid" and not bill.get("ap_variance_closed")


# ── U12 — titipan bank ke pesanan pelanggan lain ──────────────────────────────────────────────────────────────────
async def test_PK19_U12_titipan_ke_pelanggan_lain_ditolak(klien, kepala_admin, db, dunia):
    b1 = await _pesanan(db, dunia["B"], 800_000, label="B1-")
    lid = _id("stl")
    await db.bank_statement_lines.insert_one({
        "id": lid, "bank_account_id": "rek_pk19_b", "entity_id": KSC, "stmt_date": _hari(), "amount": 400_000.0,
        "direction": "in", "description": "titipan uji PK-19", "status": "holding",
        "holding": {"cash_number": "KAS-PK19"}, "holding_allocated": [], "holding_remaining": 400_000.0,
        "created_at": now_iso(), "updated_at": now_iso()})
    r = await klien.post(f"/api/bank-reconciliation/lines/{lid}/holding/allocate", headers=kepala_admin, json={
        "customer_id": dunia["A"], "reason_code": "titipan_teridentifikasi", "note": "uji",
        "allocations": [{"order_id": b1["id"], "amount": 400_000}]})
    assert r.status_code == 400, r.text
    assert "milik pelanggan lain" in r.json()["detail"], r.text
    ln = await db.bank_statement_lines.find_one({"id": lid}, {"_id": 0})
    assert ln["holding_remaining"] == 400_000 and ln["holding_allocated"] == [] and "saga_lock" not in ln
    assert (await _so(db, b1))["payments"] == []


# ── U13 — kwitansi kas + deposit = dua baris berjenis ─────────────────────────────────────────────────────────────
async def test_PK19_U13_kwitansi_kas_dan_deposit(klien, kepala_admin, db, dunia):
    from services import ar_allocation_service as aas
    a2 = await _pesanan(db, dunia["A"], 500_000, label="A2-")
    await _deposit(db, dunia["A"], 200_000)
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 300_000, [(a2, 500_000)], deposit=200_000)
    assert r.status_code == 200, r.text
    so = await _so(db, a2)
    assert [(p["kind"], p["amount"]) for p in so["payments"]] == [("kas", 300_000), ("deposit", 200_000)]
    assert so["payment_status"] == "paid" and await _saldo_deposit(db, dunia["A"]) == 0
    assert r.json()["allocations"][0]["applied"] == 500_000
    assert aas.payment_kind({"method": "writeoff", "amount": 10_000}) == "hapus_sisa"


# ── U14 — kembalikan kelebihan bayar: deposit dulu, kas gagal → deposit kembali ───────────────────────────────────
async def test_PK19_U14_refund_kas_gagal_deposit_kembali(klien, kepala_admin, db, dunia, monkeypatch):
    from services import cash_ledger
    await _deposit(db, dunia["A"], 100_000)
    rc = await _kwitansi_lebih(db, dunia["A"], 100_000)

    async def _kas_gagal(**kw):
        raise RuntimeError("uji: pembuatan kas dipaksa gagal")
    monkeypatch.setattr(cash_ledger, "create_cash", _kas_gagal)
    r = await _putus(klien, kepala_admin, rc, "refund", amount=100_000, account_id="rek_pk19_b")
    assert r.status_code >= 400, r.text
    assert await _saldo_deposit(db, dunia["A"]) == 100_000
    dec = await db.payment_variance_decisions.find_one({"receipt_id": rc}, {"_id": 0})
    assert dec and dec["status"] == "failed"
    assert await jumlah("cash_transactions", {"ref_type": "ar_refund", "ref_id": dec["id"]}) == 0
    monkeypatch.undo()
    r = await _putus(klien, kepala_admin, rc, "refund", amount=100_000, account_id="rek_pk19_b")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done" and await _saldo_deposit(db, dunia["A"]) == 0
    kas = await db.cash_transactions.find({"ref_type": "ar_refund", "ref_id": dec["id"]}, {"_id": 0}).to_list(5)
    assert len(kas) == 1 and kas[0]["amount"] == 100_000 and kas[0]["gl_status"] == "posted"


# ── U17 — "Simulasi bayar" dimatikan ──────────────────────────────────────────────────────────────────────────────
async def test_PK19_U17_simulasi_bayar_dimatikan(klien, kepala_admin, db, dunia):
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="A1-")
    n_inv = await jumlah("invoices", {})
    r = await klien.post(f"/api/sales-orders/{a1['id']}/simulate-payment", headers=kepala_admin,
                         json={"amount": 0, "method": "transfer"})
    assert r.status_code == 410, r.text
    assert r.json()["detail"] == ("Simulasi pembayaran sudah tidak dipakai. Catat pembayaran lewat kwitansi "
                                  "(Catat Penerimaan).")
    assert await jumlah("invoices", {}) == n_inv
    so = await _so(db, a1)
    assert so["payments"] == [] and so["paid_total"] == 0 and "saga_lock" not in so
    # Pencarian di backend/ dan frontend/src/: selain definisi endpoint 410, hanya uji yang memastikan 410.
    pola = re.compile(r"simulate-payment|_apply_to_order|apply_from_")
    temu = []
    for akar in (REPO / "backend", REPO / "frontend" / "src"):
        for f in akar.rglob("*"):
            if f.suffix not in (".py", ".js", ".jsx") or "node_modules" in f.parts or "__pycache__" in f.parts:
                continue
            for i, baris in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if pola.search(baris):
                    temu.append((str(f.relative_to(REPO)), i))
    kode = [t for t in temu if not re.search(r"(^|/)(tests?|tests_mem|__tests__)/|/test_[^/]*\.py$", t[0])]
    assert [t[0] for t in kode] == ["backend/routers/invoices.py"], kode
    panel = (REPO / "frontend/src/features/orders/OrderDetailPanel.jsx").read_text(encoding="utf-8")
    assert "Simulasi Pembayaran" not in panel and "simulate-payment-button" not in panel and "onPay" not in panel
    aksi = (REPO / "frontend/src/hooks/useAppActions.js").read_text(encoding="utf-8")
    assert "payInvoice" not in aksi
