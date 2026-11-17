"""Review adversarial S5 (Hutang per Pemasok, commit ac25d81) — **uang muka ke pemasok dihitung per PT**.

Temuan R-S5-01: `ap_party_service._credits(pemasok, PT)` memakai `contra_bon_service.available_credits`, yang menyaring
nota debit per PT tetapi uang muka (`cash_transactions.ref_type = "ap_advance"`) TIDAK — semua uang muka pemasok itu
dari PT mana pun ikut. Akibatnya di Hutang per Pemasok:
  * mode Semua PT: pemasok yang punya tagihan di dua PT mendapat uang muka yang sama di KEDUA barisnya; KPI "Potongan
    belum dipakai" (totals.advance) terhitung dua kali;
  * PT lain: baris/rincian PT Kanda menampilkan uang muka milik PT Sukacita (angka PT lain bocor ke PT yang dipilih).

Persiapan (FIXTURE): pemasok **U** — tagihan KSC 1.000.000 (terbuka) + tagihan KSC lama yang lebih bayar 150.000 (uang
muka `ap_advance`, kas PT KSC) + tagihan KANDA 2.000.000 (terbuka).

Hitung tangan: uang muka U di KSC = 150.000, di KANDA = 0. Semua PT: total uang muka = 150.000 (bukan 300.000).
"""
from __future__ import annotations

import datetime

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
JT = 1_000_000
UM = 150_000.0


def _tgl(hari: int) -> str:
    # Dari tanggal buku WIB (server: `report_basis.tanggal_buku`), bukan tanggal UTC mesin uji: pukul
    # 00.00–07.00 WIB keduanya berbeda satu hari dan umur tagihan meleset satu (46 ≠ 45).
    from services.book_date import tanggal_buku
    return (datetime.date.fromisoformat(tanggal_buku()) + datetime.timedelta(days=hari)).isoformat()


def _tagihan(bid: str, total: float, ent: str, *, status: str = "posted", paid: float = 0.0) -> dict:
    return {"id": bid, "bill_number": f"VB-{bid[-4:].upper()}", "entity_id": ent, "supplier_id": "sup_rs5u",
            "supplier_name": "Pemasok U Review", "status": status, "grand_total": float(total),
            "subtotal": float(total), "amount_paid": float(paid),
            "payment_status": "paid" if status == "paid" else "unpaid", "payments": [], "timeline": [],
            "po_id": None, "po_number": f"PO-{bid[-4:].upper()}", "bill_date": _tgl(-20), "due_date": _tgl(10),
            "created_at": now_iso()}


@pytest.fixture(scope="module")
async def data(db):
    await db.suppliers.insert_one({"id": "sup_rs5u", "name": "Pemasok U Review", "code": "RS5U", "entity_id": KSC,
                                   "status": "active", "payment_term_code": "NET30"})
    await db.vendor_bills.insert_many([
        _tagihan("vb_rs5k", 1 * JT, KSC),
        _tagihan("vb_rs5l", 0.5 * JT, KSC, status="paid", paid=0.5 * JT),   # lebih bayar → uang muka di KSC
        _tagihan("vb_rs5d", 2 * JT, KANDA),
    ])
    await db.cash_transactions.insert_one({
        "id": "cash_rs5_um", "number": "KK-RS5-UM", "cash_type": "bank", "direction": "out", "amount": UM,
        "category": "supplier_advance", "description": "Uang muka pemasok (lebih bayar VB-RS5L)",
        "entity_id": KSC, "owner_entity_id": KSC, "ref_type": "ap_advance", "ref_id": "vb_rs5l",
        "ref_number": "VB-RS5L", "txn_date": _tgl(-5), "status": "posted", "created_at": now_iso()})
    return {"U": "sup_rs5u"}


def _baris(j: dict, ent: str) -> dict:
    rows = [r for r in j["rows"] if r["supplier_id"] == "sup_rs5u" and r["entity_id"] == ent]
    assert len(rows) == 1, j["rows"]
    return rows[0]


async def test_R_S5_01_semua_pt_uang_muka_tidak_dobel(klien, kepala_admin, data):
    j = (await klien.get("/api/vendor-bills/payables/by-supplier", headers=kepala_admin,
                         params={"entity_id": "all"})).json()
    assert _baris(j, KSC)["advance"] == UM and _baris(j, KSC)["advance_count"] == 1
    assert _baris(j, KANDA)["advance"] == 0.0 and _baris(j, KANDA)["advance_count"] == 0, _baris(j, KANDA)
    assert j["totals"]["advance"] == UM, j["totals"]   # KPI "Potongan belum dipakai": sekali, bukan per baris


async def test_R_S5_01_pt_lain_tidak_melihat_uang_muka_ksc(klien, kepala_admin, data):
    j = (await klien.get("/api/vendor-bills/payables/by-supplier", headers=kepala_admin,
                         params={"entity_id": KANDA})).json()
    assert _baris(j, KANDA)["advance"] == 0.0, _baris(j, KANDA)
    assert j["totals"]["advance"] == 0.0
    d = (await klien.get(f"/api/vendor-bills/payables/by-supplier/{data['U']}", headers=kepala_admin,
                         params={"entity_id": KANDA})).json()
    assert d["credits"] == [] and d["totals"]["credits"] == 0.0, d["credits"]
    k = (await klien.get(f"/api/vendor-bills/payables/by-supplier/{data['U']}", headers=kepala_admin,
                         params={"entity_id": KSC})).json()
    assert [c["ref_id"] for c in k["credits"]] == ["cash_rs5_um"] and k["totals"]["credits"] == UM
    assert all(c["entity_id"] == KSC for c in k["credits"])


async def test_R_S5_01_rincian_semua_pt_tidak_mengulang_potongan(klien, kepala_admin, data):
    """`?entity_id=all` (mis. tautan/skrip): satu uang muka tampil sekali dengan PT pemiliknya, bukan sekali per PT."""
    d = (await klien.get(f"/api/vendor-bills/payables/by-supplier/{data['U']}", headers=kepala_admin,
                         params={"entity_id": "all"})).json()
    assert [(c["ref_id"], c["entity_id"]) for c in d["credits"]] == [("cash_rs5_um", KSC)], d["credits"]
    assert d["totals"]["credits"] == UM


# RS-02 (review S5 R-S5-02) — diperbaiki di contra_bon_service.available_credits (uang muka disaring per PT kas).
async def test_R_S5_02_form_kontrabon_pt_lain_tidak_menawarkan_uang_muka(data):
    from services import contra_bon_service as cbs
    lain = await cbs.available_credits(data["U"], KANDA)
    assert lain["supplier_advances"] == [], lain["supplier_advances"]
