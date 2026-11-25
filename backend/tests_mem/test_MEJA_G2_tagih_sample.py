"""Meja gelombang 2 · Tugas 7 — kontrak baris Meja Keuangan untuk aksi di tempat.

`jatuh_tempo` membawa `reminded` (tindak lanjut "diingatkan" ≤ 7 hari, sama dengan layar penagihan);
`sample_acc_bayar` membawa `sample_billing`/`grand_total`/`paid_total`/`sample_payment_status`, `action_kind="approve_payment"`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"


def _id(awal: str) -> str:
    return f"{awal}_g2ts_{uuid.uuid4().hex[:8]}"


def _jam(tanggal: str) -> str:
    return f"{tanggal}T03:00:00+00:00"


async def _pesanan_lewat_tempo(db, cid: str, sales: dict) -> dict:
    from services import billing_schedule_service as bss
    from services import gl_service as gl
    so = {"id": _id("so"), "number": f"SO-G2TS-{uuid.uuid4().hex[:5]}", "entity_id": KSC, "customer_id": cid,
          "customer_name": "Toko Tagih G2", "status": "shipped", "grand_total": 1_000_000.0, "total_amount": 1_000_000.0,
          "ppn_amount": 0.0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid",
          "payment_term_code": "NET30", "payment_term_days": 30, "items": [], "sales_id": sales["id"],
          "sales_name": sales["name"], "created_at": _jam("2026-08-25"), "confirmed_at": _jam("2026-08-25")}
    await db.sales_orders.insert_one(dict(so))
    await bss.on_order_confirmed(so["id"])
    shid, nomor = _id("shp"), f"SJ-{so['number'][-5:]}"
    await db.shipments.insert_one({"id": shid, "shipment_no": nomor, "order_id": so["id"], "entity_id": KSC,
                                   "status": "dispatched", "created_at": _jam("2026-09-01")})
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": 1_000_000.0, "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": 1_000_000.0}],
                           description=f"Pengakuan penjualan {so['number']} · {nomor}", date=_jam("2026-09-01"),
                           source_type="shipment_revenue", source_id=shid, entity_id=KSC, created_by="system",
                           source_label=nomor, ref={"order_id": so["id"], "order_number": so["number"]})
    await bss.on_shipment_posted(so["id"], nomor)
    return so


def _baris(desk_json, qid, ref_id):
    return next(x for q in desk_json["queues"] if q["id"] == qid for x in q["rows"] if x["ref_id"] == ref_id)


async def test_jatuh_tempo_membawa_reminded_sesuai_tindak_lanjut_7_hari(klien, db, akun, kepala_admin):
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
    desk = (await klien.get("/api/finance/desk", headers=kepala_admin)).json()
    assert _baris(desk, "jatuh_tempo", sudah["id"])["reminded"] is True
    assert _baris(desk, "jatuh_tempo", baru["id"])["reminded"] is False
    assert _baris(desk, "jatuh_tempo", lama["id"])["reminded"] is False   # tindak lanjut > 7 hari tidak dihitung
    assert _baris(desk, "jatuh_tempo", baru["id"])["customer_id"] == cid


async def test_sample_acc_bayar_membawa_isian_dialog_setujui_bayar(klien, db, kepala_admin):
    sid = _id("sos")
    await db.sales_orders.insert_one({
        "id": sid, "number": "SOS-G2TS-1", "entity_id": KSC, "order_type": "sample", "sample_billing": "paid",
        "sample_payment_status": "awaiting_approval", "status": "confirmed", "customer_name": "Toko Sample G2",
        "grand_total": 10_000.0, "total_amount": 9_000.0, "paid_total": 4_000.0, "created_at": datetime.now(timezone.utc).isoformat()})
    row = _baris((await klien.get("/api/finance/desk", headers=kepala_admin)).json(), "sample_acc_bayar", sid)
    assert row["action_kind"] == "approve_payment" and row["action"] == "Setujui bayar"
    assert (row["sample_billing"], row["grand_total"], row["paid_total"], row["sample_payment_status"]) == (
        "paid", 10_000.0, 4_000.0, "awaiting_approval")
