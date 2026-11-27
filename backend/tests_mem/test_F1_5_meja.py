"""F1 Kwitansi Otomatis dari Mutasi Bank · Tugas 5 — antrean Meja Keuangan "Mutasi berkode perlu dicek".

Rancangan `docs/superpowers/specs/2026-11-27-kwitansi-otomatis-mutasi-design.md` §5.4. Baris antrean = mutasi bank
`unmatched` ber-penanda `f1.status == "kartu"` di PT cakupan; antrean hanya untuk pemegang `cash.create` DAN
`ar_receipt.create`. Pesanan CBD 100 m × Rp 10.000 = Rp 1.000.000 (tanpa PPN); mutasi Rp 1.500.000 → kartu
`nominal_beda` (lebih Rp 500.000).

    cd /home/user/KNHOST && python -m pytest backend/tests_mem/test_F1_5_meja.py -n 0 -q -p no:cacheprovider
"""
from __future__ import annotations

import itertools
import uuid

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
TGL = "2026-11-24"
REC = "/api/bank-reconciliation"
TANPA_PPN = {"tax_override": "non_ppn", "tax_override_reason": "uji F1-5 tanpa PPN"}
QID = "mutasi_berkode"
_n = itertools.count(1)


def _id(awal: str) -> str:
    return f"{awal}_f15_{uuid.uuid4().hex[:8]}"


async def _rekening(klien, h, **isi) -> str:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], "default_receiving_methods": ["transfer"],
            "holder_name": "PT Kain Suka Cita", "entity_id": KSC, **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    A = await _rekening(klien, kepala_admin, name="BCA Penerimaan F15", account_number="151-515-1515",
                        show_on_documents=True)
    cus, adr, prd = _id("cus"), _id("adr"), _id("prd")
    await db.customers.insert_one({"id": cus, "name": "Toko F1-5", "entity_id": KSC, "status": "active",
                                   "phone": "081200000015",
                                   "addresses": [{"id": adr, "label": "Utama", "city": "Bandung",
                                                  "address": "Jl. Uji 15", "recipient_name": "Bu Uji",
                                                  "phone": "081200000015"}]})
    await db.products.insert_one({"id": prd, "sku": "F15-KAIN", "name": "Kain F15-KAIN", "price": 10000,
                                  "base_unit": "meter", "status": "active", "lifecycle": "produksi", "category": "uji"})
    await db.warehouses.insert_one({"id": "wh_f15", "name": "Gudang F1-5", "entity_id": KSC, "city": "Bandung"})
    sales, sa, fin = await akun("sales"), await akun("sales_admin"), await akun("finance")
    fin_kanda = await akun("finance", entitas=KANDA)
    return {"h": kepala_admin, "A": A, "cus": cus, "adr": adr, "prd": prd, "sales": sales,
            "h_sa": await sesi(sa), "h_fin": await sesi(fin),
            "h_fin_kanda": await sesi(fin_kanda, entitas=KANDA)}


async def _pesan(klien, db, siap) -> dict:
    await db.inventory_rolls.insert_one({
        "id": _id("roll"), "roll_no": f"R-F15-{next(_n)}", "product_id": siap["prd"], "owner_entity_id": KSC,
        "warehouse_id": "wh_f15", "status": "available", "active_movement": None, "length_remaining": 100.0,
        "lot": "L-F15", "created_at": now_iso()})
    body = {"customer_id": siap["cus"], "shipping_address_id": siap["adr"], "entity_id": KSC,
            "payment_term_code": "CBD", "payment_method_code": "transfer", "receiving_account_id": siap["A"],
            "items": [{"product_id": siap["prd"], "quantity": 100, "unit": "meter"}], **TANPA_PPN}
    r = await klien.post("/api/sales-orders", headers=siap["h"], json=body)
    assert r.status_code == 200, r.text
    so = r.json()
    r = await klien.post(f"/api/sales-orders/{so['id']}/review-release", headers=siap["h"], json={"note": "uji"})
    assert r.status_code == 200, r.text
    return so


async def _kode(db, oid: str) -> str:
    return (await db.payment_codes.find_one({"order_id": oid}, {"_id": 0}, sort=[("created_at", 1)]))["code"]


async def _impor(klien, siap, baris: list) -> dict:
    lines = [{"stmt_date": TGL, "amount": b["nominal"], "direction": "in", "description": b["berita"],
              "ref": b.get("ref", ""), "external_id": _id("ext")} for b in baris]
    r = await klien.post(f"{REC}/import", headers=siap["h_fin"], json={"bank_account_id": siap["A"], "lines": lines})
    assert r.status_code == 200, r.text
    return r.json()


async def _antrean(klien, h, qid: str = QID):
    r = await klien.get("/api/finance/desk", headers=h)
    assert r.status_code == 200, r.text
    return next((q for q in r.json()["queues"] if q["id"] == qid), None)


async def _kartu(klien, db, siap, nominal: float = 1_500_000):
    so = await _pesan(klien, db, siap)
    kode = await _kode(db, so["id"])
    j = await _impor(klien, siap, [{"nominal": nominal, "berita": f"TRSF {kode} TOKO F15", "ref": "TRF-F15"}])
    ln = await db.bank_statement_lines.find_one({"import_batch": j["import_batch"]}, {"_id": 0})
    return so, kode, ln


async def test_antrean_muncul_untuk_finance_dan_baris_kartu(klien, db, siap):
    so, kode, ln = await _kartu(klien, db, siap)
    assert ln["f1"]["status"] == "kartu" and ln["f1"]["alasan_kode"] == "nominal_beda"
    q = await _antrean(klien, siap["h_fin"])
    assert q is not None
    assert (q["label"], q["hint"]) == (
        "Mutasi berkode perlu dicek",
        "Mutasi bank berkode bayar yang belum bisa menjadi kwitansi otomatis. Baca alasannya, lalu Catat kwitansi dari "
        "mutasi atau buka Rekonsiliasi.")
    b = next(x for x in q["rows"] if x["ref_id"] == ln["id"])
    assert (b["ref_type"], b["action"], b["action_kind"], b["badge"]) == (
        "bank_statement_line", "Catat kwitansi", "receipt_from_line", "nominal_beda")
    assert b["number"] == so["number"] and b["title"] == "Toko F1-5" and b["value"] == 1_500_000
    assert b["subtitle"].startswith(f"{TGL} · BCA Penerimaan F15 · {kode} · ")
    assert ln["f1"]["alasan"] in b["subtitle"] and "nominal" in b["subtitle"].lower()
    assert (b["line_id"], b["order_id"], b["order_number"], b["customer_id"], b["bank_account_id"]) == (
        ln["id"], so["id"], so["number"], siap["cus"], siap["A"])
    assert (b["stmt_date"], b["ref"], b["codes"], b["alasan_kode"], b["report_id"], b["receipt_id"]) == (
        TGL, "TRF-F15", [kode], "nominal_beda", "", "")
    assert b["alasan"] == ln["f1"]["alasan"] and b["entity_id"] == KSC


async def test_baris_kartu_membawa_kwitansi_yang_disebut(klien, db, siap):
    """Gelombang akhir (Minor 3 tinjauan) — kartu yang alasannya menyebut kwitansi terbuka (`f1.receipt_id`, mis.
    `kemungkinan_ganda`) membawa `receipt_id`: layar tidak menawarkan "Catat kwitansi" untuk baris itu."""
    so = await _pesan(klien, db, siap)
    kode = await _kode(db, so["id"])
    j = await _impor(klien, siap, [{"nominal": 1_000_000, "berita": f"TRSF {kode} ASLI"},
                                   {"nominal": 1_000_000, "berita": f"TRSF  {kode}  ASLI"}])
    asli, kembar = sorted(await db.bank_statement_lines.find({"import_batch": j["import_batch"]}, {"_id": 0})
                          .to_list(5), key=lambda r: r["created_at"])
    assert (asli["f1"]["status"], kembar["f1"]["alasan_kode"]) == ("otomatis", "kemungkinan_ganda")
    b = next(x for x in (await _antrean(klien, siap["h_fin"]))["rows"] if x["ref_id"] == kembar["id"])
    assert b["receipt_id"] == asli["f1"]["receipt_id"] != "" and b["badge"] == "kemungkinan_ganda"


async def test_baris_otomatis_dan_pt_lain_tidak_tampil(klien, db, siap):
    so = await _pesan(klien, db, siap)
    j = await _impor(klien, siap, [{"nominal": 1_000_000, "berita": f"TRSF {await _kode(db, so['id'])}"}])
    otomatis = await db.bank_statement_lines.find_one({"import_batch": j["import_batch"]}, {"_id": 0})
    assert otomatis["f1"]["status"] == "otomatis"
    _, _, kartu = await _kartu(klien, db, siap)
    # kartu yang sudah dilepas manusia (status bukan unmatched / f1 bukan kartu) juga tidak tampil
    _, _, manual = await _kartu(klien, db, siap)
    await db.bank_statement_lines.update_one({"id": manual["id"]}, {"$set": {"f1.status": "manual"}})   # FIXTURE
    # T5-M2 (gelombang akhir) — kartu PT lain benar-benar ADA di DB: asersi PT tidak boleh lolos hampa
    kanda = {**kartu, "id": _id("stmtline"), "entity_id": KANDA, "bank_account_id": _id("bank"),   # FIXTURE
             "external_id": _id("ext"), "f1": {**kartu["f1"], "alasan": "Kartu PT Kanda F15"}}
    await db.bank_statement_lines.insert_one(dict(kanda))
    assert await db.bank_statement_lines.count_documents({"id": kanda["id"], "entity_id": KANDA, "status": "unmatched",
                                                          "f1.status": "kartu"}) == 1
    ids = {x["ref_id"] for x in (await _antrean(klien, siap["h_fin"]))["rows"]}
    assert kartu["id"] in ids and otomatis["id"] not in ids and manual["id"] not in ids
    assert kanda["id"] not in ids                                   # kartu PT Kanda tidak tampil bagi Finance KSC
    q_kanda = await _antrean(klien, siap["h_fin_kanda"])
    assert q_kanda is not None                                      # Finance Kanda memang memegang antrean ini
    ids_kanda = {x["ref_id"] for x in q_kanda["rows"]}
    assert kanda["id"] in ids_kanda and kartu["id"] not in ids_kanda


async def test_sales_admin_tidak_melihat_antrean(klien, db, siap):
    await _kartu(klien, db, siap)
    r = await klien.get("/api/finance/desk", headers=siap["h_sa"])
    assert r.status_code == 403 or all(q["id"] != QID for q in r.json()["queues"])


@pytest.mark.parametrize("ditolak", [("cash", "create"), ("ar_receipt", "create")])
async def test_perlu_kedua_izin(klien, db, siap, monkeypatch, ditolak):
    await _kartu(klien, db, siap)
    import dependencies
    asli = dependencies.has_permission

    async def _izin(user, module, action):
        if (module, action) == ditolak:
            return False
        return await asli(user, module, action)
    monkeypatch.setattr(dependencies, "has_permission", _izin)
    assert await _antrean(klien, siap["h_fin"]) is None
    monkeypatch.setattr(dependencies, "has_permission", asli)
    assert await _antrean(klien, siap["h_fin"]) is not None
