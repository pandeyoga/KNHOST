"""Lapor Bayar CBD & DP · Tugas 1 — fondasi: izin, pengaturan batas bayar, penomoran & koleksi laporan."""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"


def _id(awal: str) -> str:
    return f"{awal}_lb1_{uuid.uuid4().hex[:8]}"


def test_izin_payment_report_terdaftar_dan_bawaan():
    import access_modules as am
    from permissions_config import DEFAULT_PERMISSIONS as dp

    for peran in ("sales", "sales_admin", "finance", "admin", "manager"):
        assert "create" in dp[peran]["payment_report"], peran
    for peran in ("finance", "admin", "manager"):
        assert "decide" in dp[peran]["payment_report"], peran
    for peran in ("sales", "sales_admin"):
        assert "decide" not in dp[peran]["payment_report"], peran
    assert am.RESOURCE_LABEL["payment_report"]
    assert am.ACTION_LABEL["payment_report.create"] and am.ACTION_LABEL["payment_report.decide"]
    assert sum("payment_report" in m["resources"] for m in am.MODULE_CATALOG) == 1


async def test_batas_bayar_bawaan_3_per_pt(klien, kepala_admin):
    from services.nilai_pengaturan import nilai

    assert await nilai("sales.batas_bayar_hari", KSC) == 3
    assert await nilai("sales.batas_bayar_hari", KANDA) == 3
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": "sales.batas_bayar_hari", "value": 5, "scope_type": "entity", "scope_id": KSC,
        "reason": "uji LB-1", "effective_from": ""}]})
    assert r.status_code == 200, r.text
    assert await nilai("sales.batas_bayar_hari", KSC) == 5
    assert await nilai("sales.batas_bayar_hari", KANDA) == 3   # PT lain tidak ikut berubah


async def test_nomor_LB_berurutan_per_pt(db):
    from services import payment_report_service as prs

    a1 = await prs.next_number(KSC)
    a2 = await prs.next_number(KSC)
    b1 = await prs.next_number(KANDA)
    assert a1.startswith("LB-") or "/LB-" in a1
    assert a2 != a1 and b1 != a1
    assert int(a2.rsplit("-", 1)[1]) == int(a1.rsplit("-", 1)[1]) + 1
    assert int(b1.rsplit("-", 1)[1]) == 1   # deret PT lain mulai sendiri


def test_status_dan_tampil():
    from services import payment_report_service as prs

    assert (prs.MENUNGGU, prs.DITERIMA, prs.DITOLAK) == ("menunggu", "diterima", "ditolak")
    out = prs.tampil({"_id": "x", "id": "r1", "number": "LB-1", "status": "menunggu", "idem_key": "k", "amount": 5})
    assert "_id" not in out and "idem_key" not in out and out["id"] == "r1" and out["amount"] == 5


def test_payment_reports_terdaftar_bercakupan_pt():
    from entity_scope import SCOPED_COLLECTIONS, field_for

    assert "payment_reports" in SCOPED_COLLECTIONS
    assert field_for("payment_reports") == "entity_id"


async def test_baca_laporan_pesanan_mengikuti_pt_dan_membawa_hak(klien, db, kepala_admin, akun, sesi):
    so = {"id": _id("so"), "number": "SO-LB1", "entity_id": KSC, "status": "confirmed", "customer_name": "Toko LB"}
    await db.sales_orders.insert_one(dict(so))
    await db.payment_reports.insert_one({"id": _id("lb"), "order_id": so["id"], "entity_id": KSC, "number": "LB-X",
                                         "status": "menunggu", "idem_key": "rahasia"})
    r = await klien.get(f"/api/sales-orders/{so['id']}/payment-reports", headers=kepala_admin)
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(j["items"]) == 1 and "idem_key" not in j["items"][0] and "_id" not in j["items"][0]
    assert j["bisa_lapor"] is True and j["bisa_putuskan"] is True
    assert (await klien.get("/api/sales-orders/tidak_ada/payment-reports", headers=kepala_admin)).status_code == 404


async def test_jatuh_tempo_tahan_bayar_memakai_batas_pt(db):
    from datetime import datetime, timezone
    from services import pay_hold_service as phs

    mulai = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
    assert (await phs.due_at(KANDA, mulai)).day == 28   # bawaan 3 hari
