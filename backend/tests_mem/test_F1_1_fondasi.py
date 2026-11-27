"""F1 Kwitansi Otomatis dari Mutasi Bank · Tugas 1 — fondasi: pengaturan, waktu aktif, isian kwitansi, indeks unik,
pengecualian B3 untuk pelaku sistem mutasi.

Rancangan `docs/superpowers/specs/2026-11-27-kwitansi-otomatis-mutasi-design.md` §5.3, §5.7.

    cd backend && python -m pytest tests_mem/test_F1_1_fondasi.py -q -p no:cacheprovider -n 0
"""
from __future__ import annotations

import itertools
import uuid

import pytest
from fastapi import HTTPException

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
KUNCI = "bank.kwitansi_otomatis_mutasi"
TANPA_PPN = {"tax_override": "non_ppn", "tax_override_reason": "uji F1-1 tanpa PPN"}
_n = itertools.count(1)


def _id(awal: str) -> str:
    return f"{awal}_f11_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun):
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
        "payment_method_codes": ["transfer"], "default_receiving_methods": ["transfer"],
        "holder_name": "PT Kain Suka Cita", "entity_id": KSC, "name": "BCA Penerimaan F11",
        "account_number": "111-222-3333", "show_on_documents": True})
    assert r.status_code == 200, r.text
    rek = r.json()["id"]
    cus, adr, prd = _id("cus"), _id("adr"), _id("prd")
    await db.customers.insert_one({"id": cus, "name": "Toko F1-1", "entity_id": KSC, "status": "active",
                                   "addresses": [{"id": adr, "label": "Utama", "city": "Bandung",
                                                  "address": "Jl. Uji 11", "recipient_name": "Bu Uji",
                                                  "phone": "081200000011"}]})
    await db.products.insert_one({"id": prd, "sku": "F11-KAIN", "name": "Kain F1-1", "price": 10000,
                                  "base_unit": "meter", "status": "active", "lifecycle": "produksi", "category": "uji"})
    await db.warehouses.insert_one({"id": "wh_f11", "name": "Gudang F1-1", "entity_id": KSC, "city": "Bandung"})
    sales = await akun("sales")
    fin = await akun("finance")
    return {"h": kepala_admin, "rek": rek, "cus": cus, "adr": adr, "prd": prd, "sales": sales, "fin": fin}


def _aktor(u: dict) -> dict:
    return {"id": u["id"], "name": u["name"], "role": u["role"]}


async def _pesanan_tertahan(klien, db, siap) -> dict:
    """Pesanan CBD Rp 1.000.000 yang tertahan bayar (sama dengan persiapan `test_LB4_putus`)."""
    await db.inventory_rolls.insert_one({
        "id": _id("roll"), "roll_no": f"R-F11-{next(_n)}", "product_id": siap["prd"], "owner_entity_id": KSC,
        "warehouse_id": "wh_f11", "status": "available", "active_movement": None, "length_remaining": 100.0,
        "lot": "L-F11", "created_at": now_iso()})
    body = {"customer_id": siap["cus"], "shipping_address_id": siap["adr"], "entity_id": KSC,
            "payment_term_code": "CBD", "payment_method_code": "transfer", "receiving_account_id": siap["rek"],
            "items": [{"product_id": siap["prd"], "quantity": 100, "unit": "meter"}], **TANPA_PPN}
    r = await klien.post("/api/sales-orders", headers=siap["h"], json=body)
    assert r.status_code == 200, r.text
    so = r.json()
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"sales_id": siap["sales"]["id"]}})   # FIXTURE
    r = await klien.post(f"/api/sales-orders/{so['id']}/review-release", headers=siap["h"], json={"note": "uji"})
    assert r.status_code == 200, r.text
    cur = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert cur["status"] == "approved" and cur["pay_hold"]
    return cur


def _isi(siap, **lain) -> dict:
    return {"customer_id": siap["cus"], "amount": 1_000_000, "method": "transfer", "entity_id": KSC,
            "account_id": siap["rek"], "receipt_date": "2026-11-24", "reference_no": f"TRF-F11-{next(_n)}", **lain}


# ── Pengaturan ───────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_pengaturan_terdaftar_bawaan_nyala(klien, kepala_admin):
    import config_registry
    from services.bank_auto_receipt_service import menyala

    e = config_registry.get(KUNCI)
    assert e["type"] == "bool" and e["default"] is True and tuple(e["scopes"]) == ("global", "entity")
    assert await menyala(KSC) is True
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": KUNCI, "value": False, "scope_type": "entity", "scope_id": KSC,
        "reason": "uji F1-1", "effective_from": ""}]})
    assert r.status_code == 200, r.text
    assert await menyala(KSC) is False
    assert await menyala(KANDA) is True          # PT lain tetap menyala


# ── Waktu aktif ──────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_waktu_aktif_ditulis_sekali(db):
    from services.bank_auto_receipt_service import PENANDA_AKTIF, aktif_sejak, ensure_aktif_sejak

    await db.system_settings.update_one({"scope": "__migrations__"}, {"$unset": {PENANDA_AKTIF: ""}})
    assert await aktif_sejak() == ""
    a = await ensure_aktif_sejak()
    b = await ensure_aktif_sejak()
    assert a == b != ""
    assert await aktif_sejak() == a


async def test_waktu_aktif_tidak_menggandakan_dokumen_migrasi(db):
    """I1 (tinjauan akhir) — penanda dibaca dulu, ditulis hanya bila kuncinya belum ada, pada dokumen `__migrations__`
    yang sudah ada: tiap nyala ulang backend tidak menyisipkan dokumen penanda kedua (dibaca migrasi sekali-jalan lain
    lewat `find_one`)."""
    from services.bank_auto_receipt_service import PENANDA_AKTIF, aktif_sejak, ensure_aktif_sejak

    penanda = {"scope": "__migrations__"}
    simpan = await db.system_settings.find(penanda).to_list(50)
    try:
        # (a) satu dokumen migrasi tanpa kunci F1 → kunci ditulis di dokumen itu; tiga kali nyala = tetap satu dokumen
        await db.system_settings.delete_many(penanda)
        await db.system_settings.insert_one({"scope": "__migrations__", "kft1_izin_pengaturan": "2026-01-01T00:00:00"})
        a = await ensure_aktif_sejak()
        for _ in range(2):
            assert await ensure_aktif_sejak() == a != ""
        assert await db.system_settings.count_documents(penanda) == 1
        doc = await db.system_settings.find_one(penanda, {"_id": 0})
        assert doc[PENANDA_AKTIF] == a and doc["kft1_izin_pengaturan"] == "2026-01-01T00:00:00"
        # (b) belum ada dokumen migrasi sama sekali → dibuat sekali
        await db.system_settings.delete_many(penanda)
        b = await ensure_aktif_sejak()
        assert b != "" and await ensure_aktif_sejak() == b == await aktif_sejak()
        assert await db.system_settings.count_documents(penanda) == 1
    finally:
        await db.system_settings.delete_many(penanda)
        if simpan:
            await db.system_settings.insert_many(simpan)


# ── Isian kwitansi ───────────────────────────────────────────────────────────────────────────────────────────────────
async def test_kwitansi_menyimpan_sumber_dan_baris(klien, db, siap):
    from services import ar_receipt_service as ars
    from services.bank_auto_receipt_service import AKTOR_MUTASI, SUMBER

    kw = await ars.create_receipt(_isi(siap, source=SUMBER, bank_line_id="stmtline_x"), _aktor(siap["fin"]))
    doc = await db.ar_receipts.find_one({"id": kw["id"]}, {"_id": 0})
    assert doc["source"] == SUMBER and doc["bank_line_id"] == "stmtline_x"
    assert AKTOR_MUTASI == {"id": "", "name": "Sistem (mutasi bank)", "role": "system", "sistem": "mutasi_bank"}

    # Pintu HTTP tidak menerima isian ini: model badan mengabaikan field asing (ReceiptPayload tanpa field itu).
    r = await klien.post("/api/ar-receipts", headers=siap["h"],
                         json=_isi(siap, amount=500_000, source=SUMBER, bank_line_id="stmtline_y"))
    assert r.status_code == 200, r.text
    doc = await db.ar_receipts.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert "source" not in doc and "bank_line_id" not in doc


# ── Indeks unik ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_indeks_unik_baris_mutasi():
    from indexes import REQUIRED_UNIQUE_INDEXES

    [ix] = [i for i in REQUIRED_UNIQUE_INDEXES if i["name"] == "uq_bank_line_receipt"]
    assert ix["collection"] == "ar_receipts" and ix["keys"] == [("bank_line_id", 1)]
    assert ix["partial"] == {"bank_line_id": {"$exists": True}, "status": "posted"}


# ── B3 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_b3_dikecualikan_hanya_untuk_aktor_mutasi(klien, db, siap):
    from services import ar_receipt_service as ars
    from services.bank_auto_receipt_service import AKTOR_MUTASI, SUMBER

    await _pesanan_tertahan(klien, db, siap)
    # aktor sales tanpa `payment_report.decide` meski membawa source="mutasi_bank" → tetap ditolak
    with pytest.raises(HTTPException) as e:
        await ars.create_receipt(_isi(siap, source=SUMBER, bank_line_id=_id("stmtline")), _aktor(siap["sales"]))
    assert e.value.status_code == 409 and e.value.detail == ars.PESAN_PAKAI_LAPOR_BAYAR
    # AKTOR_MUTASI tanpa source → tetap ditolak
    with pytest.raises(HTTPException) as e:
        await ars.create_receipt(_isi(siap), dict(AKTOR_MUTASI))
    assert e.value.status_code == 409 and e.value.detail == ars.PESAN_PAKAI_LAPOR_BAYAR
    # AKTOR_MUTASI + source="mutasi_bank" → lolos
    kw = await ars.create_receipt(_isi(siap, source=SUMBER, bank_line_id=_id("stmtline")), dict(AKTOR_MUTASI))
    doc = await db.ar_receipts.find_one({"id": kw["id"]}, {"_id": 0})
    assert doc["status"] == "posted" and doc["source"] == SUMBER
