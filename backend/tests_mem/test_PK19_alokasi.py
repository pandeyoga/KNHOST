"""PK-19 serah-terima (a) — satu fungsi alokasi pembayaran pesanan (`services/ar_allocation_service.py`).

docs/blueprint/unit/PK-19.md langkah kerja 1: uji `validate_targets`, `allocate`, `reverse`, `payment_kind` LANGSUNG
(inti U1–U3, U7, U13). Pesanan dan pelanggan = fixture (disisipkan); alokasi dan pembalik = alur lewat fungsi.

Persiapan bersama (spesifikasi): `ent_ksc`; pelanggan A dan B; pesanan A1 Rp 1.000.000 dan A2 Rp 500.000 (terkirim),
B1 Rp 800.000; X1 milik A di `ent_kanda`. Tiap uji membuat pesanannya sendiri (id unik) supaya tidak bergantung urutan.

Hitung tangan:
  U7   K2 Rp 1.000.000 ke A1 tgl 10 → Σ = 1.000.000 (lunas); batal tgl 20 → baris −1.000.000 → Σ = 1.000.000 −
       1.000.000 = 0 → `unpaid`.
  U13  kas 300.000 + deposit 200.000 ke A2 (500.000) → dua baris; Σ = 500.000 → `paid`.
"""
from __future__ import annotations

import itertools
import uuid

import pytest
from fastapi import HTTPException

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
JT = 1_000_000
_n = itertools.count(1)
AKTOR = "Uji PK-19"


def _id(awal: str) -> str:
    return f"{awal}_pk19a_{uuid.uuid4().hex[:8]}"


async def _pelanggan(db, nama: str) -> str:
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": nama, "entity_id": KSC, "status": "active",
                                   "deposit_balance": 0})
    return cid


async def _pesanan(db, cus: str, total: float, *, ent: str = KSC, status: str = "shipped", label: str = "") -> dict:
    i = next(_n)
    so = {"id": _id("so"), "number": f"SO-PK19-{label or i}", "entity_id": ent, "customer_id": cus,
          "customer_name": "Toko Uji", "status": status, "grand_total": float(total), "payments": [],
          "paid_total": 0.0, "payment_status": "unpaid", "payment_term_code": "NET30", "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    return so


@pytest.fixture(scope="module")
async def dasar(db):
    a = await _pelanggan(db, "Toko A")
    b = await _pelanggan(db, "Toko B")
    return {"A": a, "B": b}


async def _gagal(coro) -> HTTPException:
    with pytest.raises(HTTPException) as e:
        await coro
    return e.value


def _alokasi(kind, so, amount, *, cus, source="krw_x", ent=KSC, date="", seq=""):
    from services import ar_allocation_service as aas
    return aas.allocate(kind=kind, order_id=so["id"], amount=amount, source_id=source, source_number=source.upper(),
                        customer_id=cus, entity_id=ent, date=date or now_iso(), actor=AKTOR, seq=seq)


async def test_PK19_inti_U1_pelanggan_lain_ditolak(db, dasar):
    from services import ar_allocation_service as aas
    b1 = await _pesanan(db, dasar["B"], 800_000, label="B1")
    e = await _gagal(aas.validate_targets("deposit", [{"order_id": b1["id"], "amount": 300_000}],
                                          customer_id=dasar["A"], entity_id=KSC))
    assert e.status_code == 400
    assert e.detail == (f"Pesanan {b1['number']} milik pelanggan lain. Dana ini hanya bisa dipakai untuk pesanan "
                        "pelanggan yang sama.")
    e = await _gagal(_alokasi("deposit", b1, 300_000, cus=dasar["A"]))
    assert e.status_code == 400
    assert (await db.sales_orders.find_one({"id": b1["id"]}))["payments"] == []


async def test_PK19_inti_U2_pt_lain_ditolak(db, dasar):
    x1 = await _pesanan(db, dasar["A"], 1 * JT, ent=KANDA, label="X1")
    e = await _gagal(_alokasi("deposit", x1, 300_000, cus=dasar["A"]))
    assert e.status_code == 403
    assert e.detail == f"Pesanan {x1['number']} milik PT lain. Piutangnya tidak bisa dilunasi dari dana PT ini."
    assert (await db.sales_orders.find_one({"id": x1["id"]}))["payments"] == []


async def test_PK19_inti_U3_pesanan_batal_ditolak(db, dasar):
    a2 = await _pesanan(db, dasar["A"], 500_000, status="cancelled", label="A2-batal")
    e = await _gagal(_alokasi("kas", a2, 500_000, cus=dasar["A"]))
    assert e.status_code == 409
    assert e.detail == f"Pesanan {a2['number']} berstatus Dibatalkan, jadi tidak bisa menerima pembayaran."
    assert (await db.sales_orders.find_one({"id": a2["id"]}))["payments"] == []


async def test_PK19_inti_melebihi_sisa_dan_isian_wajib(db, dasar):
    from services import ar_allocation_service as aas
    a1 = await _pesanan(db, dasar["A"], 1 * JT)
    e = await _gagal(_alokasi("kas", a1, 1_200_000, cus=dasar["A"]))
    assert (e.status_code, e.detail) == (400, f"Alokasi Rp 1.200.000 melebihi sisa tagihan pesanan {a1['number']} "
                                              "(Rp 1.000.000).")
    # Σ per pesanan: dua baris 600.000 + 600.000 ke pesanan yang sama = 1.200.000 > 1.000.000
    e = await _gagal(aas.validate_targets("kas", [{"order_id": a1["id"], "amount": 600_000},
                                                  {"order_id": a1["id"], "amount": 600_000}],
                                          customer_id=dasar["A"], entity_id=KSC))
    assert e.status_code == 400 and "melebihi sisa tagihan" in e.detail
    for kw in ({"customer_id": "", "entity_id": KSC}, {"customer_id": dasar["A"], "entity_id": "all"},
               {"customer_id": dasar["A"], "entity_id": ""}):
        e = await _gagal(aas.validate_targets("kas", [{"order_id": a1["id"], "amount": 1}], **kw))
        assert e.status_code == 400 and "wajib jelas" in e.detail
    e = await _gagal(aas.validate_targets("tunai", [], customer_id=dasar["A"], entity_id=KSC))
    assert e.status_code == 400 and "tidak dikenal" in e.detail
    e = await _gagal(aas.validate_targets("kas", [{"order_id": a1["id"], "amount": 0}], customer_id=dasar["A"],
                                          entity_id=KSC))
    assert e.status_code == 400 and "lebih dari 0" in e.detail
    assert (await db.sales_orders.find_one({"id": a1["id"]}))["payments"] == []


async def test_PK19_inti_U7_pembalik_bertanggal_bukan_hapus(db, dasar):
    from services import ar_allocation_service as aas
    a1 = await _pesanan(db, dasar["A"], 1 * JT)
    r = await _alokasi("kas", a1, 1 * JT, cus=dasar["A"], source="arc_k2", date="2026-11-10T09:00:00+07:00")
    assert r["payment_status"] == "paid" and r["outstanding_after"] == 0
    hasil = await aas.reverse(source_id="arc_k2", date="2026-11-20T10:00:00+07:00", actor=AKTOR, reason="uji U7")
    assert [h["reversed"] for h in hasil] == [1 * JT]
    so = await db.sales_orders.find_one({"id": a1["id"]})
    asal, balik = so["payments"]
    assert (asal["amount"], asal["date"][:10], asal["reversed_by"]) == (1 * JT, "2026-11-10", balik["id"])
    assert (balik["amount"], balik["date"][:10], balik["reverses"]) == (-1 * JT, "2026-11-20", asal["id"])
    assert balik["kind"] == "kas" and balik["receipt_id"] == "arc_k2"
    assert sum(p["amount"] for p in so["payments"]) == 0 and so["paid_total"] == 0
    assert so["payment_status"] == "unpaid"
    # Diulang → baris yang sudah dibalik dilewati (tetap dua baris).
    await aas.reverse(source_id="arc_k2", date="2026-11-21", actor=AKTOR, reason="ulang")
    assert len((await db.sales_orders.find_one({"id": a1["id"]}))["payments"]) == 2


async def test_PK19_inti_U13_kas_dan_deposit_dua_baris(db, dasar):
    from services import ar_allocation_service as aas
    a2 = await _pesanan(db, dasar["A"], 500_000, label="A2")
    await _alokasi("kas", a2, 300_000, cus=dasar["A"], source="arc_k13", seq="0")
    r = await _alokasi("deposit", a2, 200_000, cus=dasar["A"], source="arc_k13", seq="0")
    assert r["payment_status"] == "paid"
    so = await db.sales_orders.find_one({"id": a2["id"]})
    assert [(p["kind"], p["amount"]) for p in so["payments"]] == [("kas", 300_000), ("deposit", 200_000)]
    assert [aas.payment_kind(p) for p in so["payments"]] == ["kas", "deposit"]
    # Baris lama tanpa `kind` → dari `method`.
    assert aas.payment_kind({"method": "writeoff", "kind": "writeoff"}) == "hapus_sisa"
    lama = {"deposit": "deposit", "bank_holding": "titipan_bank", "store_credit": "saldo_kredit",
            "credit_note": "nota_kredit", "writeoff": "hapus_sisa", "realokasi": "kasus", "finance_case": "kasus",
            "transfer": "kas", "tunai": "kas", "": "kas"}
    assert {m: aas.payment_kind({"method": m}) for m in lama} == lama


async def test_PK19_inti_alokasi_aman_diulang(db, dasar):
    from services import ar_allocation_service as aas
    a1 = await _pesanan(db, dasar["A"], 1 * JT)
    r1 = await _alokasi("kas", a1, 400_000, cus=dasar["A"], source="arc_ulang", seq="0")
    r2 = await _alokasi("kas", a1, 400_000, cus=dasar["A"], source="arc_ulang", seq="0")
    assert r1["payment_id"] == r2["payment_id"] == aas.payment_id("kas", "arc_ulang", a1["id"], "0")
    assert (r1["replayed"], r2["replayed"]) == (False, True)
    so = await db.sales_orders.find_one({"id": a1["id"]})
    assert [p["amount"] for p in so["payments"]] == [400_000] and so["paid_total"] == 400_000
    assert so["payment_status"] == "partial"
    assert r1["payment_id"].startswith("pay_") and len(r1["payment_id"]) == 28


async def test_PK19_inti_kalah_balapan_409(db, dasar, monkeypatch):
    """Pemeriksa lolos (membaca sisa lama) tetapi sisa sudah habis saat menulis → syarat bersyarat menolak → 409."""
    from services import ar_allocation_service as aas
    a1 = await _pesanan(db, dasar["A"], 1 * JT)
    lama = dict(a1)
    await _alokasi("kas", a1, 1 * JT, cus=dasar["A"], source="arc_pertama")

    async def _periksa_basi(*a, **kw):
        return [lama]
    monkeypatch.setattr(aas, "validate_targets", _periksa_basi)
    e = await _gagal(_alokasi("kas", a1, 1 * JT, cus=dasar["A"], source="arc_kedua"))
    assert (e.status_code, e.detail) == (409, f"Alokasi ke pesanan {a1['number']} gagal karena sisa tagihannya baru "
                                              "berubah. Muat ulang lalu coba lagi.")
    assert [p["receipt_id"] for p in (await db.sales_orders.find_one({"id": a1["id"]}))["payments"]] == ["arc_pertama"]


async def test_PK19_inti_pembalik_negatif_ditolak(db, dasar):
    """Pembayaran kwitansi sudah dipindah lewat kasus (penarikan) → membaliknya membuat terbayar negatif → 409."""
    from services import ar_allocation_service as aas
    a1 = await _pesanan(db, dasar["A"], 1 * JT)
    await _alokasi("kas", a1, 1 * JT, cus=dasar["A"], source="arc_pindah")
    await aas.withdraw(kind="kasus", order_id=a1["id"], amount=1 * JT, source_id="fcs_x", source_number="KAS-1",
                       customer_id=dasar["A"], entity_id=KSC, date=now_iso(), actor=AKTOR, method="realokasi")
    e = await _gagal(aas.reverse(source_id="arc_pindah", date=now_iso(), actor=AKTOR, reason="uji"))
    assert (e.status_code, e.detail) == (409, f"Pembayaran ARC_PINDAH pada pesanan {a1['number']} sudah dipindahkan "
                                              "lewat dokumen lain. Batalkan pemindahan itu dulu.")
    so = await db.sales_orders.find_one({"id": a1["id"]})
    assert [p["amount"] for p in so["payments"]] == [1 * JT, -1 * JT] and "reversed_by" not in so["payments"][0]


async def test_PK19_inti_cabut_dokumen_gagal_lahir(db, dasar):
    from services import ar_allocation_service as aas
    a1 = await _pesanan(db, dasar["A"], 1 * JT)
    await _alokasi("kas", a1, 250_000, cus=dasar["A"], source="arc_gagal")
    assert await aas.remove_unborn("arc_gagal") == [a1["id"]]
    so = await db.sales_orders.find_one({"id": a1["id"]})
    assert so["payments"] == [] and so["paid_total"] == 0 and so["payment_status"] == "unpaid"
