"""Gate merah lama INV-BAL-02 "ent_ksc Δ6,500" (log gate 2026-11-17 latih_keuangan3) — akar di pemeriksa, bukan data.

`customer_balance_service.reconcile_gl` menghitung SETIAP jurnal `finance_case` yang menyentuh akun piutang sebagai
"sebab yang dikenal" (kasus keuangan). Padahal semua penyelesaian kasus yang mengkredit piutang (biaya bank, alokasi
titipan/uang muka, titipan karyawan, salah PT) JUGA menempelkan pelunasan ke pesanan lewat `ar_allocation_service`
(baris `payments[]` ber-`receipt_id` = id kasus) — piutang dokumen sudah ikut turun. Selisih buku besar vs dokumen = 0,
tetapi pemeriksa mengurangkan jurnal kasus lagi → "tak terjelaskan" = +nominal kasus → INV-BAL-02 MERAH palsu.

Langkah ulang (persis data gate): pesanan terkirim Rp 400.000 (jurnal pengakuan) → kasus "selisih biaya bank" Rp 6.500
diselesaikan (`finance_case_actions.act_bank_charge`: Dr 6-8000 / Cr 1-1200 + pelunasan 6.500 menempel di pesanan).
Hitung tangan: piutang terkirim 400.000 − 6.500 = 393.500 = saldo 1-1200 393.500 → selisih 0, tak terjelaskan 0.
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.anyio

KANDA = "ent_kanda"


def _id(awal: str) -> str:
    return f"{awal}_agf_{uuid.uuid4().hex[:8]}"


async def _pesanan_terkirim(db, nilai: float) -> dict:
    from services import gl_service as gl
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": "Toko Uji INV-BAL-02", "entity_id": KANDA, "status": "active",
                                   "payment_profile": {}, "deposit_balance": 0.0, "assigned_sales_id": ""})
    so = {"id": _id("so"), "number": f"SO-AGF-{uuid.uuid4().hex[:5]}", "entity_id": KANDA, "customer_id": cid,
          "customer_name": "Toko Uji INV-BAL-02", "status": "shipped", "grand_total": float(nilai),
          "total_amount": float(nilai), "ppn_amount": 0.0, "payments": [], "paid_total": 0.0,
          "payment_status": "unpaid", "payment_term_code": "NET30", "payment_term_days": 30, "items": [],
          "created_at": "2026-11-02T03:00:00+00:00", "confirmed_at": "2026-11-02T03:00:00+00:00"}
    await db.sales_orders.insert_one(dict(so))
    shid = _id("shp")
    await db.shipments.insert_one({"id": shid, "shipment_no": "SJ-AGF-1", "order_id": so["id"], "entity_id": KANDA,
                                   "status": "dispatched", "created_at": "2026-11-03T03:00:00+00:00"})
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": float(nilai), "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": float(nilai)}],
                           description=f"Pengakuan penjualan {so['number']}", date="2026-11-03T03:00:00+00:00",
                           source_type="shipment_revenue", source_id=shid, entity_id=KANDA, created_by="system",
                           source_label="SJ-AGF-1", ref={"order_id": so["id"], "order_number": so["number"]})
    return so


async def test_inv_bal02_kasus_biaya_bank_tidak_dihitung_dua_kali(db):
    from services import customer_balance_service as cbs
    from services import finance_case_actions as acts
    awal = await cbs.reconcile_gl(KANDA)
    so = await _pesanan_terkirim(db, 400_000)
    sesudah_kirim = await cbs.reconcile_gl(KANDA)
    assert sesudah_kirim["unexplained"] == awal["unexplained"], sesudah_kirim

    kasus = {"id": _id("fcs"), "number": "CASE-AGF-1", "entity_id": KANDA, "customer_id": so["customer_id"],
             "order_ids": [so["id"]], "case_type": "selisih_biaya_bank", "documents": []}
    await db.finance_cases.insert_one(dict(kasus))
    hasil = await acts.act_bank_charge(kasus, {"amount": 6_500, "order_id": so["id"]}, {"name": "Uji"})
    jenis = sorted(d["kind"] for d in hasil["documents"])
    assert jenis == ["journal_entry", "order_payment"], hasil   # dua efek: pelunasan menempel + jurnal Cr piutang
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0, "paid_total": 1})
    assert o["paid_total"] == 6_500

    rec = await cbs.reconcile_gl(KANDA)
    # piutang dokumen DAN buku besar sama-sama turun 6.500 → selisih tidak berubah
    assert round(rec["ar_delivered"] - sesudah_kirim["ar_delivered"], 2) == -6_500, rec
    assert round(rec["gl_balance"] - sesudah_kirim["gl_balance"], 2) == -6_500, rec
    assert rec["difference"] == sesudah_kirim["difference"], rec
    # kode lama: explained {"kasus keuangan": -6500} → unexplained +6.500 (MERAH palsu, persis gate "Δ6,500")
    assert rec["unexplained"] == awal["unexplained"], rec
    assert "kasus keuangan" not in rec["explained"], rec


async def test_inv_bal02_jurnal_kasus_tanpa_pelunasan_tetap_terjelaskan(db):
    """Jurnal kasus yang menyentuh piutang TANPA pelunasan menempel (mis. data lama) tetap sebab "kasus keuangan"."""
    from services import customer_balance_service as cbs
    from services import gl_service as gl
    awal = await cbs.reconcile_gl(KANDA)
    cid = _id("fcs")
    je = await gl.post_finance_case(case_id=cid, entity_id=KANDA, amount=12_000, debit_acc="6-8000",
                                    credit_acc="1-1200", label="uji kasus lama", suffix="chg:0")
    try:
        rec = await cbs.reconcile_gl(KANDA)
        assert round(rec["difference"] - awal["difference"], 2) == -12_000, rec
        assert rec["explained"].get("kasus keuangan") == round(awal["explained"].get("kasus keuangan", 0) - 12_000, 2)
        assert rec["unexplained"] == awal["unexplained"], rec
    finally:
        await db.journal_entries.update_one({"id": je["id"]}, {"$set": {"status": "void"}})
