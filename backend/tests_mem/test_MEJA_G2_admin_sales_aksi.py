"""Meja gelombang 2 · Tugas 8 — kontrak baris Meja Admin Sales untuk aksi di tempat.

`jatuh_tempo` membawa `reminded` (tindak lanjut "diingatkan" ≤ 7 hari, sama dengan layar penagihan & Meja Keuangan)
dan `customer_id`/`order_id` untuk `POST /collection-reminders/mark`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests_mem.test_MEJA_G2_tagih_sample import KSC, _id, _pesanan_lewat_tempo

pytestmark = pytest.mark.anyio


def _baris(desk_json, qid, ref_id):
    return next(x for q in desk_json["queues"] if q["id"] == qid for x in q["rows"] if x["ref_id"] == ref_id)


async def test_admin_sales_jatuh_tempo_membawa_reminded_dan_customer_id(klien, db, akun, kepala_admin):
    sales = await akun("sales", entitas=(KSC,))
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": "Toko Tagih G2", "entity_id": KSC, "status": "active",
                                   "payment_profile": {}, "deposit_balance": 0.0, "assigned_sales_id": sales["id"]})
    baru = await _pesanan_lewat_tempo(db, cid, sales)
    lama = await _pesanan_lewat_tempo(db, cid, sales)
    sudah = await _pesanan_lewat_tempo(db, cid, sales)
    now = datetime.now(timezone.utc)
    await db.collection_followups.insert_one({"id": _id("fu"), "order_id": sudah["id"], "customer_id": cid,
                                              "outcome": "reminded", "created_at": (now - timedelta(days=2)).isoformat()})
    await db.collection_followups.insert_one({"id": _id("fu"), "order_id": lama["id"], "customer_id": cid,
                                              "outcome": "reminded", "created_at": (now - timedelta(days=10)).isoformat()})
    desk = (await klien.get("/api/sales-admin/desk", headers=kepala_admin)).json()
    assert _baris(desk, "jatuh_tempo", sudah["id"])["reminded"] is True
    assert _baris(desk, "jatuh_tempo", baru["id"])["reminded"] is False
    assert _baris(desk, "jatuh_tempo", lama["id"])["reminded"] is False   # tindak lanjut > 7 hari tidak dihitung
    r = _baris(desk, "jatuh_tempo", baru["id"])
    assert r["customer_id"] == cid and r["order_id"] == baru["id"]
    assert r["action_kind"] == "open"   # navigasi lama tetap bawaan server; meja yang menukar aksinya menurut izin
