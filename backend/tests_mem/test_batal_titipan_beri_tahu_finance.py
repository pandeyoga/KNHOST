"""Temuan alur pembatalan (25 Nov 2026) — Finance tidak diberi tahu saat pesanan yang sudah dibayar batal.

Pembatalan (dan kedaluwarsa reservasi) memindahkan uang muka pesanan menjadi TITIPAN pelanggan (S3, 18 Nov). Dulu yang
diberi tahu hanya sales pemilik pesanan; Finance, yang harus mengembalikan uang atau memakainya untuk pesanan lain, harus
mengecek daftar titipan sendiri. Kalau pemindahan gagal, layar hanya berkata "hubungi Finance" tanpa Finance tahu.

  BTF-1  Pesanan ber-uang muka dibatalkan → setiap pemegang izin Meja Finance (`payment_variance.decide`) di PT pesanan
         mendapat SATU notifikasi (nomor pesanan, pelanggan, nominal titipan, tautan ke Uang Muka Pelanggan). Akun tanpa
         izin itu (sales) dan akun PT lain tidak mendapatnya.
  BTF-2  Penerima dibaca dari IZIN, bukan nama peran: peran kustom tanpa peran acuan yang diberi izin itu ikut menerima.
  BTF-3  Pesanan batal tanpa uang muka tidak memberi tahu Finance; pemindahan yang diulang tidak menggandakan notifikasi.
  BTF-4  Jalur kedaluwarsa (fungsi yang sama, pelaku "system") ikut memberi tahu Finance.
  BTF-5  Pemindahan gagal → Finance diberi tahu bahwa uang muka belum terpindah (pembatalan tetap berhasil).
"""
from __future__ import annotations

import uuid

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
JENIS = "titipan_pesanan_batal"
JENIS_GAGAL = "titipan_pesanan_batal_gagal"


def _id(awal: str) -> str:
    return f"{awal}_btf_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun):
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
        "payment_method_codes": ["transfer"], "name": "BCA Operasional BTF", "account_number": "741-559-7777",
        "holder_name": "PT Kain Suka Cita", "default_receiving_methods": ["transfer"], "entity_id": KSC})
    assert r.status_code == 200, r.text
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": "Uji BTF · Toko Kain", "entity_id": KSC, "status": "active",
                                   "payment_profile": {"default_method": "tempo", "term_days": 30}})
    return {"h": kepala_admin, "P": cus,
            "finance": await akun("finance"),
            "finance_pt_lain": await akun("finance", entitas=("ent_kanda",)),
            "sales": await akun("sales")}


async def _pesanan_dibayar(klien, db, siap, total: float, bayar: float) -> dict:
    so = {"id": _id("so"), "number": f"SO-BTF-{uuid.uuid4().hex[:4]}", "entity_id": KSC, "customer_id": siap["P"],
          "customer_name": "Uji BTF · Toko Kain", "status": "confirmed", "grand_total": float(total),
          "ppn_amount": 0.0, "payments": [], "paid_total": 0, "payment_status": "unpaid", "payment_term_code": "CBD",
          "items": [], "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    if bayar:
        r = await klien.post("/api/ar-receipts", headers=siap["h"], json={
            "customer_id": siap["P"], "amount": bayar, "method": "transfer", "entity_id": KSC,
            "reference_no": f"TRF-{so['number']}", "allocations": [{"order_id": so["id"], "amount": bayar}]})
        assert r.status_code == 200, r.text
    return so


async def _notif(db, jenis: str, so: dict) -> list:
    return await db.notifications.find({"type": jenis, "ref": {"$regex": f"^{jenis}:{so['id']}"}},
                                       {"_id": 0}).to_list(100)


async def test_BTF_1_batal_pesanan_dibayar_memberi_tahu_pemegang_izin_meja_finance(klien, db, siap):
    so = await _pesanan_dibayar(klien, db, siap, 2_000_000, 2_000_000)
    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel", headers=siap["h"],
                         json={"reason": "Pelanggan membatalkan pesanan CBD"})
    assert r.status_code == 200, r.text
    assert round(float(r.json()["advance_to_deposit"]), 2) == 2_000_000

    rows = await _notif(db, JENIS, so)
    penerima = {n["recipient_user"] for n in rows}
    assert siap["finance"]["id"] in penerima, rows
    assert siap["sales"]["id"] not in penerima, "sales tidak memegang izin Meja Finance"
    assert siap["finance_pt_lain"]["id"] not in penerima, "akun PT lain tidak bertugas di PT pesanan"
    assert all(not n.get("recipient_role") for n in rows), "alamat per orang, bukan siaran peran"
    assert len(rows) == len(penerima), "satu notifikasi per orang"
    n = next(x for x in rows if x["recipient_user"] == siap["finance"]["id"])
    assert so["number"] in n["title"]
    assert "Uji BTF · Toko Kain" in n["body"] and "2.000.000" in n["body"]
    assert "Pelanggan membatalkan pesanan CBD" in n["body"]
    assert n["link"] == "advance-report" and n["entity_id"] == KSC


async def test_BTF_2_penerima_dibaca_dari_izin_bukan_nama_peran(klien, db, siap, akun, peran_tanpa_acuan):
    peran = await peran_tanpa_acuan({"payment_variance": ["view", "decide"]})
    orang = await akun(peran)
    so = await _pesanan_dibayar(klien, db, siap, 900_000, 450_000)
    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel", headers=siap["h"],
                         json={"reason": "Pelanggan membatalkan pesanan DP"})
    assert r.status_code == 200, r.text
    assert orang["id"] in {n["recipient_user"] for n in await _notif(db, JENIS, so)}


async def test_BTF_3_tanpa_uang_muka_tidak_memberi_tahu_dan_ulang_tidak_dobel(klien, db, siap):
    from services import ar_receipt_service as ar
    kosong = await _pesanan_dibayar(klien, db, siap, 750_000, 0)
    r = await klien.post(f"/api/sales-orders/{kosong['id']}/cancel", headers=siap["h"],
                         json={"reason": "Pelanggan membatalkan sebelum bayar"})
    assert r.status_code == 200, r.text
    assert await _notif(db, JENIS, kosong) == []

    so = await _pesanan_dibayar(klien, db, siap, 1_000_000, 1_000_000)
    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel", headers=siap["h"],
                         json={"reason": "Pelanggan membatalkan pesanan CBD"})
    assert r.status_code == 200, r.text
    sekali = len(await _notif(db, JENIS, so))
    assert sekali >= 1
    assert await ar.uang_muka_pesanan_batal_ke_titipan(so["id"], {"name": "uji"}, "ulang") == 0.0
    assert len(await _notif(db, JENIS, so)) == sekali


async def test_BTF_4_kedaluwarsa_ikut_memberi_tahu_finance(klien, db, siap):
    from services import ar_receipt_service as ar
    so = await _pesanan_dibayar(klien, db, siap, 600_000, 300_000)
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "expired"}})
    assert await ar.uang_muka_pesanan_batal_ke_titipan(so["id"], {"name": "system"}, "reservasi kedaluwarsa") == 300_000
    rows = await _notif(db, JENIS, so)
    assert siap["finance"]["id"] in {n["recipient_user"] for n in rows}
    assert "kedaluwarsa" in rows[0]["title"].lower() or "kedaluwarsa" in rows[0]["body"].lower()


async def test_BTF_5_pemindahan_gagal_memberi_tahu_finance(klien, db, siap, monkeypatch):
    from services import ar_receipt_service as ar

    async def _rusak(*_a, **_k):
        raise RuntimeError("saldo titipan tidak bisa ditulis")
    so = await _pesanan_dibayar(klien, db, siap, 800_000, 800_000)
    monkeypatch.setattr(ar, "_adjust_deposit", _rusak)   # sesudah kwitansi: hanya pemindahan ke titipan yang gagal
    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel", headers=siap["h"],
                         json={"reason": "Pelanggan membatalkan pesanan CBD"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled" and r.json().get("advance_to_deposit_error")
    assert await _notif(db, JENIS, so) == []
    rows = await _notif(db, JENIS_GAGAL, so)
    assert siap["finance"]["id"] in {n["recipient_user"] for n in rows}, rows
    n = next(x for x in rows if x["recipient_user"] == siap["finance"]["id"])
    assert so["number"] in n["title"] and n["severity"] == "danger"
