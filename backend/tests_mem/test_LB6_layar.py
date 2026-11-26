"""Lapor Bayar CBD & DP · Tugas 6 — server untuk layar: Perjalanan, pelacak SO, Meja Keuangan, Meja Admin Sales.

Rancangan `docs/superpowers/specs/2026-11-25-lapor-bayar-cbd-design.md` §5.5. Pesanan CBD (100 m × Rp 10.000 = Rp
1.000.000, tanpa PPN, wajib bayar Rp 1.000.000) lewat "Periksa & lepas" → `approved` + `pay_hold`.

  * Perjalanan: langkah `bayar_dicek` ("Bayar dicek Finance") di antara `disetujui` dan `dikonfirmasi`; NET30 melewatinya;
    Faktur Komersial tersedia sejak tahan dimulai.
  * Pelacak: pesanan tertahan → "Menunggu bayar — Finance" (peran finance); ada laporan menunggu → kalimat lain.
  * Meja Keuangan: `lapor_bayar` hanya PT pengguna; `bayar_sebelum_kirim` tidak memuat pesanan yang punya laporan.
  * Meja Admin Sales: `_ket` "menunggu bayar (dicek Finance)"; pesanan tertahan bayar tidak masuk `siap_dikonfirmasi`.

    cd backend && python -m pytest tests_mem/test_LB6_layar.py -q -p no:cacheprovider -n 0
"""
from __future__ import annotations

import itertools
import uuid

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
TGL = "2026-11-24"
PDF = b"%PDF-1.4\n" + b"0" * 2048
TANPA_PPN = {"tax_override": "non_ppn", "tax_override_reason": "uji LB-6 tanpa PPN"}
_n = itertools.count(1)


def _id(awal: str) -> str:
    return f"{awal}_lb6_{uuid.uuid4().hex[:8]}"


async def _rekening(klien, h, **isi) -> str:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], "default_receiving_methods": ["transfer"],
            "holder_name": "PT Kain Suka Cita", "entity_id": KSC, **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    A = await _rekening(klien, kepala_admin, name="BCA Penerimaan LB6", account_number="666-777-8888",
                        show_on_documents=True)
    cus, adr, prd = _id("cus"), _id("adr"), _id("prd")
    await db.customers.insert_one({"id": cus, "name": "Toko LB-6", "entity_id": KSC, "status": "active",
                                   "addresses": [{"id": adr, "label": "Utama", "city": "Bandung",
                                                  "address": "Jl. Uji 6", "recipient_name": "Bu Uji",
                                                  "phone": "081200000006"}]})
    await db.products.insert_one({"id": prd, "sku": "LB6-KAIN", "name": "Kain LB-6", "price": 10000,
                                  "base_unit": "meter", "status": "active", "lifecycle": "produksi", "category": "uji"})
    await db.warehouses.insert_one({"id": "wh_lb6", "name": "Gudang LB-6", "entity_id": KSC, "city": "Bandung"})
    sales, sa, fin = await akun("sales"), await akun("sales_admin"), await akun("finance")
    fin_kanda = await akun("finance", entitas=KANDA)
    return {"h": kepala_admin, "A": A, "cus": cus, "adr": adr, "prd": prd, "sales": sales, "sa": sa, "fin": fin,
            "h_sales": await sesi(sales), "h_sa": await sesi(sa), "h_fin": await sesi(fin),
            "h_fin_kanda": await sesi(fin_kanda, entitas=KANDA)}


async def _so(db, oid: str) -> dict:
    return await db.sales_orders.find_one({"id": oid}, {"_id": 0})


async def _buat(klien, db, siap, term: str = "CBD") -> dict:
    await db.inventory_rolls.insert_one({
        "id": _id("roll"), "roll_no": f"R-LB6-{next(_n)}", "product_id": siap["prd"], "owner_entity_id": KSC,
        "warehouse_id": "wh_lb6", "status": "available", "active_movement": None, "length_remaining": 100.0,
        "lot": "L-LB6", "created_at": now_iso()})
    body = {"customer_id": siap["cus"], "shipping_address_id": siap["adr"], "entity_id": KSC,
            "payment_term_code": term, "payment_method_code": "transfer", "receiving_account_id": siap["A"],
            "items": [{"product_id": siap["prd"], "quantity": 100, "unit": "meter"}], **TANPA_PPN}
    r = await klien.post("/api/sales-orders", headers=siap["h"], json=body)
    assert r.status_code == 200, r.text
    so = r.json()
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"sales_id": siap["sales"]["id"]}})   # FIXTURE
    return await _so(db, so["id"])


async def _pesan(klien, db, siap, term: str = "CBD") -> dict:
    """"Periksa & lepas": CBD → `approved` + `pay_hold`; NET30 → langsung `confirmed`."""
    so = await _buat(klien, db, siap, term)
    r = await klien.post(f"/api/sales-orders/{so['id']}/review-release", headers=siap["h"], json={"note": "uji"})
    assert r.status_code == 200, r.text
    return await _so(db, so["id"])


async def _lapor(klien, siap, oid: str) -> dict:
    r = await klien.post(f"/api/sales-orders/{oid}/payment-reports", headers=siap["h_sa"], json={
        "amount": 1_000_000, "transfer_date": TGL, "account_id": siap["A"], "method": "transfer",
        "reference_no": f"TRF-LB6-{next(_n)}", "note": "uji LB-6"})
    assert r.status_code == 200, r.text
    return r.json()


async def _journey(klien, siap, oid: str) -> dict:
    r = await klien.get(f"/api/sales-orders/{oid}/journey", headers=siap["h"])
    assert r.status_code == 200, r.text
    return r.json()


def _baris_pelacak(data: dict, oid: str) -> dict:
    return next(b for b in data["rows"] if b["id"] == oid)


async def _antrean(klien, h, url: str, qid: str) -> list:
    r = await klien.get(url, headers=h)
    assert r.status_code == 200, r.text
    return next((q for q in r.json()["queues"] if q["id"] == qid), {"rows": []})["rows"]


# ── Perjalanan ───────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_perjalanan_cbd_tertahan_di_bayar_dicek(klien, db, siap):
    so = await _pesan(klien, db, siap)
    assert so["status"] == "approved" and so["pay_hold"]
    j = await _journey(klien, siap, so["id"])
    kunci = [s["key"] for s in j["steps"]]
    assert kunci.index("bayar_dicek") == kunci.index("disetujui") + 1 == kunci.index("dikonfirmasi") - 1
    langkah = next(s for s in j["steps"] if s["key"] == "bayar_dicek")
    assert langkah["label"] == "Bayar dicek Finance" and langkah["done"] is False and langkah["state"] == "pending"
    assert j["current_step"] == "bayar_dicek" and j["current_label"] == "Bayar dicek Finance"
    assert j["commercial_invoice"]["available"] is True          # B1: faktur berkode sejak tahan dimulai


async def test_perjalanan_laporan_menunggu_tetap_di_bayar_dicek(klien, db, siap):
    so = await _pesan(klien, db, siap)
    await _lapor(klien, siap, so["id"])
    assert (await _journey(klien, siap, so["id"]))["current_step"] == "bayar_dicek"


async def test_perjalanan_net30_melewati_bayar_dicek(klien, db, siap):
    so = await _pesan(klien, db, siap, term="NET30")
    j = await _journey(klien, siap, so["id"])
    langkah = next(s for s in j["steps"] if s["key"] == "bayar_dicek")
    assert langkah["state"] == "skipped" and langkah["done"] is False
    assert j["current_step"] != "bayar_dicek"
    assert j["commercial_invoice"]["available"] is False          # tidak berubah: belum ada surat jalan


async def test_perjalanan_tahan_dibuka_langkah_selesai(klien, db, siap):
    from services import pay_hold_service as phs
    so = await _pesan(klien, db, siap)
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"dispatch_payment_release": {   # FIXTURE: pengecualian
        "by": "uji", "reason": "uji LB-6", "at": now_iso()}}})
    assert await phs.clear_if_paid(so["id"]) in (True, False)
    j = await _journey(klien, siap, so["id"])
    langkah = next(s for s in j["steps"] if s["key"] == "bayar_dicek")
    assert langkah["done"] is True and j["current_step"] != "bayar_dicek"


# ── Pelacak SO ───────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_pelacak_next_step_menunggu_bayar_finance(klien, db, siap):
    so = await _pesan(klien, db, siap)
    r = await klien.get("/api/desks/so-tracker?desk=finance", headers=siap["h_fin"])
    assert r.status_code == 200, r.text
    b = _baris_pelacak(r.json(), so["id"])
    assert b["next_step"] == "Menunggu bayar — Finance" and b["owner_roles"] == ["finance"] and b["can_act"] is True
    # Admin Sales tidak lagi memegang bola
    r = await klien.get("/api/desks/so-tracker?desk=sales_admin", headers=siap["h_sa"])
    b = _baris_pelacak(r.json(), so["id"])
    assert b["owner_roles"] == ["finance"] and b["can_act"] is False


async def test_pelacak_laporan_menunggu_dicek(klien, db, siap):
    so = await _pesan(klien, db, siap)
    await _lapor(klien, siap, so["id"])
    r = await klien.get("/api/desks/so-tracker?desk=finance", headers=siap["h_fin"])
    b = _baris_pelacak(r.json(), so["id"])
    assert b["next_step"] == "Lapor bayar menunggu dicek Finance" and b["owner_roles"] == ["finance"]


def test_next_step_unit_pra_gudang():
    from services import so_tracker_service as sot
    o = {"status": "approved", "pay_hold": {"since": "x"}, "grand_total": 1}
    assert sot.next_step(o)["step"] == "Menunggu bayar — Finance"
    assert sot.next_step(o, lapor=True)["step"] == "Lapor bayar menunggu dicek Finance"
    assert sot.next_step({"status": "approved", "grand_total": 1})["roles"] == ["sales_admin"]   # tanpa tahan: lama


# ── Meja Keuangan ────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_lapor_bayar_hanya_pt_pengguna_dan_bentuk_baris(klien, db, siap):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    rows = await _antrean(klien, siap["h_fin"], "/api/finance/desk", "lapor_bayar")
    b = next(x for x in rows if x["ref_id"] == rep["id"])
    assert (b["ref_type"], b["action_kind"], b["entity_id"]) == ("payment_report", "decide_payment_report", KSC)
    assert b["order_id"] == so["id"] and b["order_number"] == so["number"] and b["amount"] == 1_000_000
    assert b["transfer_date"] == TGL and b["account_label"] == "BCA Penerimaan LB6"
    assert b["attachments_count"] == 0 and b["reported_by_name"] == siap["sa"]["name"]
    rows = await _antrean(klien, siap["h_fin_kanda"], "/api/finance/desk", "lapor_bayar")
    assert all(x["ref_id"] != rep["id"] for x in rows)


async def test_bayar_sebelum_kirim_tanpa_pesanan_ber_laporan(klien, db, siap):
    tanpa = await _pesan(klien, db, siap)
    dengan = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, dengan["id"])
    kirim = await _antrean(klien, siap["h_fin"], "/api/finance/desk", "bayar_sebelum_kirim")
    ids = {x["extra"]["order_id"] if "extra" in x else x["order_id"] for x in kirim}
    assert tanpa["id"] in ids and dengan["id"] not in ids
    lapor = await _antrean(klien, siap["h_fin"], "/api/finance/desk", "lapor_bayar")
    assert any(x["ref_id"] == rep["id"] for x in lapor)
    # laporan ditolak → pesanan kembali ke "bayar sebelum kirim"
    r = await klien.post(f"/api/payment-reports/{rep['id']}/tolak", headers=siap["h_fin"],
                         json={"reason": "bukti tidak jelas"},)
    assert r.status_code == 200, r.text
    kirim = await _antrean(klien, siap["h_fin"], "/api/finance/desk", "bayar_sebelum_kirim")
    assert dengan["id"] in {x["extra"]["order_id"] if "extra" in x else x["order_id"] for x in kirim}


# ── Meja Admin Sales ─────────────────────────────────────────────────────────────────────────────────────────────────
async def test_admin_sales_keterangan_dan_bukan_siap_dikonfirmasi(klien, db, siap):
    so = await _pesan(klien, db, siap)
    # ditahan Admin Sales ("Tahan dulu") DAN menunggu bayar: tidak boleh tampak "siap dilepas"
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"release.hold": True}})   # FIXTURE
    siapkan = await _antrean(klien, siap["h_sa"], "/api/sales-admin/desk", "siap_dikonfirmasi")
    assert all(x["ref_id"] != so["id"] for x in siapkan)
    # belum diperiksa (release.requested hilang) + menunggu bayar → keterangan jujur di antrean pertama
    await db.sales_orders.update_one({"id": so["id"]}, {"$unset": {"release": ""}})
    periksa = await _antrean(klien, siap["h_sa"], "/api/sales-admin/desk", "perlu_verifikasi")
    b = next((x for x in periksa if x["ref_id"] == so["id"]), None)
    assert b is not None and "menunggu bayar (dicek Finance)" in b["subtitle"] and "siap dilepas" not in b["subtitle"]
