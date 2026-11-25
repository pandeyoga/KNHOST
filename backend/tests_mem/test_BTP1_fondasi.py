"""BTP-1 — fondasi persetujuan batal & tutup sisa pesanan: izin, jenis persetujuan, antrean, pengaturan.

    python -m pytest backend/tests_mem/test_BTP1_fondasi.py -n 0 -q        # dari root repo
"""
from __future__ import annotations

import uuid

import pytest

from approval_kinds import APPROVAL_KINDS
from core_utils import now_iso
from permissions_config import DEFAULT_PERMISSIONS
from services import approval_policy_service as aps
from services.approval_backlog_service import QUEUES, backlog
from services.config_resolver import value_of

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"


async def test_BTP1_izin_bawaan():
    for r in ("admin", "manager", "finance"):
        assert "approve_cancel" in DEFAULT_PERMISSIONS[r]["order"], r
    for r in ("sales", "sales_admin"):
        assert "approve_cancel" not in DEFAULT_PERMISSIONS[r].get("order", []), r


async def test_BTP1_jenis_dan_antrean_terdaftar():
    k = APPROVAL_KINDS["sales_order.batal"]
    assert k["queue_key"] == "so_cancel" and k["permissions"] == ("order.approve_cancel",)
    assert k["amount_field"] == "grand_total" and k["group"] == "Penjualan"
    assert k["label"] == "Pesanan Penjualan — pembatalan & tutup sisa"
    q = next(x for x in QUEUES if x[0] == "so_cancel")
    assert q[2:] == ("approval-inbox", "sales_orders", {"cancel_request.status": "pending"})


async def test_BTP1_kebijakan_bawaan_semua_pemegang(aplikasi):
    lv = await aps.required_levels("sales_order.batal", KSC, 5_000_000)
    assert lv, "jenis baru harus punya jenjang bawaan"
    assert lv[0]["level"] == 1 and lv[0]["any_holder"] is True


async def test_BTP1_pengaturan_bawaan(aplikasi):
    assert await value_of("sales.cancel_approval_when", {"entity_id": KSC}) == "dibayar_atau_disiapkan"


async def test_BTP1_antrean_menghitung_pending(aplikasi, db):
    for st in ("pending", "rejected"):
        await db.sales_orders.insert_one({
            "id": f"so_btp1_{uuid.uuid4().hex[:8]}", "entity_id": KSC, "status": "confirmed",
            "number": f"SO-BTP1-{st}", "cancel_request": {"status": st}, "created_at": now_iso()})
    b = await backlog(KSC)
    baris = next(r for r in b["all_items"] if r["key"] == "so_cancel")
    assert baris["count"] == 1
