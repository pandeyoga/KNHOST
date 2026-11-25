"""MEJA-2 — §5.6: SOS tidak tampil sebagai giliran manajer; Pelacak SO memakai sample_next_step untuk SOS."""
from __future__ import annotations
import pytest
from core_utils import now_iso

pytestmark = pytest.mark.anyio


async def _dua_pesanan(db, akhir: str):
    t = now_iso()
    so = {"id": f"so_m2{akhir}", "number": f"SO-M2{akhir}", "status": "waiting_approval", "entity_id": "ent_ksc",
          "grand_total": 1000, "customer_name": "Toko Biasa", "created_at": t, "updated_at": t, "items": []}
    sos = {"id": f"sos_m2{akhir}", "number": f"KSC/SOS-M2{akhir}", "status": "waiting_approval", "order_type": "sample",
           "sample_billing": "paid", "entity_id": "ent_ksc", "grand_total": 83250, "customer_name": "Toko Sample",
           "created_at": t, "updated_at": t, "items": []}
    await db.sales_orders.insert_many([dict(so), dict(sos)])
    return so, sos


async def test_pelacak_sos_tahap_sample(klien, db, kepala_admin):
    so, sos = await _dua_pesanan(db, "a")
    rows = (await klien.get("/api/desks/so-tracker", headers=kepala_admin, params={"desk": "sales_admin"})).json()["rows"]
    s = next(r for r in rows if r["id"] == sos["id"])
    assert s["next_step"] == "Persetujuan pembayaran sample" and s["order_type"] == "sample"
    assert s["entity_id"] == "ent_ksc"
    assert next(r for r in rows if r["id"] == so["id"])["order_type"] == "regular"
    smp = (await klien.get("/api/desks/so-tracker", headers=kepala_admin, params={"desk": "sample_admin"})).json()["rows"]
    ids = {r["id"] for r in smp}
    assert sos["id"] in ids and so["id"] not in ids


async def test_meja_manajer_tanpa_pesanan_sample(klien, db, akun, sesi):
    so, sos = await _dua_pesanan(db, "b")
    mgr = await akun("manager")
    for doc in (so, sos):
        await db.notifications.insert_one({
            "id": f"ntf_{doc['id']}", "recipient_user": mgr["id"], "type": "turn", "read": False,
            "ref": f"turn:sales_orders:{doc['id']}:waiting_approval#{mgr['id']}", "action_id": f"sales_orders:{doc['id']}",
            "title": f"Giliran Anda — Setujui pesanan: {doc['number']}", "created_at": now_iso(), "severity": "info"})
    qs = {q["id"]: q for q in (await klien.get("/api/desks/me", headers=await sesi(mgr))).json()["queues"]}
    assert {r["ref_id"] for r in qs["so_acc"]["rows"]} >= {so["id"]}
    assert sos["id"] not in {r["ref_id"] for r in qs["so_acc"]["rows"]}
    giliran = {r["ref_id"] for r in qs["giliran_saya"]["rows"]}
    assert so["id"] in giliran and sos["id"] not in giliran


async def test_turn_queue_bawaan_tidak_menyaring(db, akun):
    from services.role_desk_service import _turn_queue
    _, sos = await _dua_pesanan(db, "c")
    u = await akun("sales")
    await db.notifications.insert_one({
        "id": f"ntf_sales_{sos['id']}", "recipient_user": u["id"], "type": "turn", "read": False,
        "ref": f"turn:sales_orders:{sos['id']}:waiting_approval#{u['id']}", "action_id": f"sales_orders:{sos['id']}",
        "title": "Giliran Anda — Uji: X", "created_at": now_iso(), "severity": "info"})
    assert sos["id"] in {r["ref_id"] for r in (await _turn_queue(u))["rows"]}
    assert sos["id"] not in {r["ref_id"] for r in (await _turn_queue(u, skip_sample_orders=True))["rows"]}
