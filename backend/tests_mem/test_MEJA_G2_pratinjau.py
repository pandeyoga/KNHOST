"""Meja gelombang 2 · Tugas 1 — pratinjau dokumen lintas PT memakai endpoint baca yang sudah ada.

Pratinjau pesanan di mode "Semua PT" mengirim header `X-Entity-Id` = PT dokumen (lihat `docEntityRegistry` di frontend).
Server harus: memuat pesanan PT lain yang diizinkan pengguna (200) dan menolak PT yang tidak diizinkan (403).
Tidak ada perubahan server di tugas ini; uji ini mengunci perilaku itu.

FIXTURE (peran `sales_admin`, bukan `finance`/`admin`/`manager` yang lintas PT): dua pesanan sederhana (`ent_ksc`, `ent_kanda`); pengguna `sales_admin` A diizinkan KSC+Kanda, pengguna B hanya KSC.
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
KANDA = "ent_kanda"


def _id(awal: str) -> str:
    return f"{awal}_mjg2_{uuid.uuid4().hex[:8]}"


async def _pesanan(db, entity_id: str) -> str:
    so = {"id": _id("so"), "number": f"SO-MJG2-{uuid.uuid4().hex[:5]}", "entity_id": entity_id, "customer_id": _id("cus"),
          "customer_name": "Toko Pratinjau", "status": "confirmed", "grand_total": 277_500.0, "total_amount": 250_000.0,
          "ppn_amount": 27_500.0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid",
          "items": [{"product_id": _id("p"), "product_name": "Katun A", "sku": "KA-01", "quantity": 10.0,
                     "unit": "meter", "price": 25_000.0, "subtotal": 250_000.0}],
          "created_at": "2026-11-20T03:00:00+00:00"}
    await db.sales_orders.insert_one(dict(so))
    return so["id"]


@pytest.fixture(scope="module")
async def data(db, akun):
    dua_pt = await akun("sales_admin", entitas=(KSC, KANDA))
    satu_pt = await akun("sales_admin", entitas=(KSC,))
    return {"dua_pt": dua_pt, "satu_pt": satu_pt, "kanda": await _pesanan(db, KANDA), "ksc": await _pesanan(db, KSC)}


async def test_pesanan_pt_lain_diizinkan_termuat(klien, sesi, data):
    h = await sesi(data["dua_pt"], entitas=KANDA)
    r = await klien.get(f"/api/sales-orders/{data['kanda']}", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["id"] == data["kanda"] and j["entity_id"] == KANDA
    assert j["items"][0]["product_name"] == "Katun A"


async def test_pesanan_pt_tak_diizinkan_ditolak(klien, sesi, data):
    h = await sesi(data["satu_pt"], entitas=KANDA)
    r = await klien.get(f"/api/sales-orders/{data['kanda']}", headers=h)
    assert r.status_code == 403, r.text
