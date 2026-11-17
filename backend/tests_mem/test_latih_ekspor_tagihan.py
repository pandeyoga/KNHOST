"""Latihan Keuangan 17 Nov — Pusat Export › Tagihan Pemasok: Sisa & Status bayar dihitung, bukan nilai tersimpan basi.

Pembayaran tagihan (ap_payment_service) hanya menambah `amount_paid`; `outstanding`/`payment_status` tersimpan tetap
nilai saat tagihan dibuat. Dataset ekspor kini menghitungnya dengan rumus `bill_financials`.
"""
import pytest

pytestmark = pytest.mark.anyio


async def test_ekspor_tagihan_sisa_dan_status_dihitung(klien, kepala_admin, db):
    ent = (await db.business_entities.find_one({"status": "active"}, {"_id": 0, "id": 1}))["id"]
    base = {"entity_id": ent, "status": "posted", "supplier_name": "Pemasok Uji Ekspor", "bill_date": "2026-11-17T00:00:00+00:00"}
    await db.vendor_bills.insert_many([
        {**base, "id": "vb_eks_lunas", "bill_number": "VB-EKS-LUNAS", "grand_total": 1000.0, "amount_paid": 1000.0,
         "outstanding": 1000.0, "payment_status": "unpaid"},                      # basi: sudah lunas
        {**base, "id": "vb_eks_sebagian", "bill_number": "VB-EKS-SEBAGIAN", "grand_total": 1000.0, "amount_paid": 400.0,
         "outstanding": 1000.0, "payment_status": "unpaid"},
        {**base, "id": "vb_eks_tutup", "bill_number": "VB-EKS-TUTUP", "grand_total": 1000.0, "amount_paid": 990.0,
         "ap_variance_closed": 10.0, "outstanding": 1000.0, "payment_status": "unpaid"},
        {**base, "id": "vb_eks_belum", "bill_number": "VB-EKS-BELUM", "grand_total": 500.0, "amount_paid": 0.0}])
    r = await klien.post("/api/export-center/preview", headers={**kepala_admin, "X-Entity-Id": ent},
                         json={"dataset": "vendor_bills", "columns": ["bill_number", "outstanding", "payment_status"],
                               "limit": 200})
    assert r.status_code == 200, r.text
    rows = {x["bill_number"]: x for x in r.json()["rows"] if str(x.get("bill_number", "")).startswith("VB-EKS-")}
    assert (rows["VB-EKS-LUNAS"]["outstanding"], rows["VB-EKS-LUNAS"]["payment_status"]) == (0, "Lunas") or \
        rows["VB-EKS-LUNAS"]["outstanding"] == 0
    assert rows["VB-EKS-SEBAGIAN"]["outstanding"] == 600
    assert rows["VB-EKS-TUTUP"]["outstanding"] == 0
    assert rows["VB-EKS-BELUM"]["outstanding"] == 500
    st = {k: str(v["payment_status"]).lower() for k, v in rows.items()}
    assert st["VB-EKS-LUNAS"] in ("paid", "lunas") and st["VB-EKS-TUTUP"] in ("paid", "lunas")
    assert st["VB-EKS-SEBAGIAN"] in ("partial", "sebagian", "dibayar sebagian")
    assert st["VB-EKS-BELUM"] in ("unpaid", "belum dibayar", "belum bayar")
