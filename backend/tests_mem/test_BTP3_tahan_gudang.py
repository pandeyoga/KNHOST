"""BTP-3 — gudang & jalur sejajar ditahan selama permintaan batal/tutup sisa menunggu keputusan.

Rancangan `docs/superpowers/specs/2026-11-25-batal-tutup-sisa-pesanan-design.md` §5.5 dan §5.6a (keputusan pemilik A2-4).
Selama `cancel_request.status == "pending"`: kirim (`dispatch_guard`), ambil (`scan-pick`), maju tahap WMS, eskalasi
tutup-sisa per tugas, dan batal item Pesanan Khusus ditolak 409 dengan satu pesan. Status tugas TIDAK diubah, jadi sesudah
ditolak/ditarik semuanya pulih. Daftar tugas outbound membawa `held_reason` turunan.

    cd backend && python -m pytest tests_mem/test_BTP3_tahan_gudang.py -n 0 -q
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
PESAN = "Pesanan sedang diajukan batal/tutup sisa — tunggu keputusan."


def _id(awal: str) -> str:
    return f"{awal}_btp3_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
        "payment_method_codes": ["transfer"], "name": "BCA Operasional BTP3", "account_number": "741-559-3333",
        "holder_name": "PT Kain Suka Cita", "default_receiving_methods": ["transfer"], "entity_id": KSC})
    assert r.status_code == 200, r.text
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": "Uji BTP3 · Toko Kain", "entity_id": KSC, "status": "active",
                                   "payment_profile": {"default_method": "tempo", "term_days": 30}})
    sales, finance = await akun("sales"), await akun("finance")
    return {"h": kepala_admin, "P": cus, "sales": sales, "hs": await sesi(sales), "hf": await sesi(finance)}


async def _pesanan(klien, db, siap, bayar: float = 0.0, **lain) -> dict:
    so = {"id": _id("so"), "number": f"SO-BTP3-{uuid.uuid4().hex[:5]}", "entity_id": KSC, "customer_id": siap["P"],
          "customer_name": "Uji BTP3 · Toko Kain", "status": "confirmed", "grand_total": 1_000_000.0,
          "ppn_amount": 0.0, "payments": [], "paid_total": 0, "payment_status": "unpaid", "payment_term_code": "CBD",
          "items": [], "sales_id": siap["sales"]["id"], "sales_name": siap["sales"]["name"], "created_at": now_iso()}
    so.update(lain)
    await db.sales_orders.insert_one(dict(so))
    if bayar:
        r = await klien.post("/api/ar-receipts", headers=siap["h"], json={
            "customer_id": siap["P"], "amount": bayar, "method": "transfer", "entity_id": KSC,
            "reference_no": f"TRF-{so['number']}", "allocations": [{"order_id": so["id"], "amount": bayar}]})
        assert r.status_code == 200, r.text
    return so


async def _tugas(db, so, status: str = "created", **lain) -> dict:
    t = {"id": _id("wt"), "number": f"WT-{uuid.uuid4().hex[:5]}", "flow_type": "outbound",
         "source_type": "sales_order", "order_id": so["id"], "order_number": so["number"], "entity_id": KSC,
         "status": status, "quantity": 10.0, "picked_qty": 0.0, "shipped_qty": 0.0, "product_id": _id("prd"),
         "warehouse_id": _id("wh"), "stages": ["created", "picking", "packing", "staging", "dispatched"],
         "scan_log": [], "created_at": now_iso(), "updated_at": now_iso()}
    t.update(lain)
    await db.wms_tasks.insert_one(dict(t))
    return t


async def _ajukan(klien, db, siap, **lain):
    """Pesanan dibayar → batal oleh sales → 202 (permintaan menunggu)."""
    so = await _pesanan(klien, db, siap, bayar=1_000_000, **lain)
    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel", headers=siap["hs"], json={"reason": "Pelanggan batal"})
    assert r.status_code == 202, r.text
    return so


def _teks(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _status(db, t) -> str:
    return (await db.wms_tasks.find_one({"id": t["id"]}, {"_id": 0, "status": 1}))["status"]


async def test_BTP3_kirim_diblok(klien, db, siap):
    from services import loading_check_service as lc
    so = await _ajukan(klien, db, siap)
    with pytest.raises(HTTPException) as e:
        await lc.dispatch_guard(so["id"], None)
    assert e.value.status_code == 409 and e.value.detail == PESAN


async def test_BTP3_ambil_diblok(klien, db, siap):
    so = await _ajukan(klien, db, siap)
    t = await _tugas(db, so, "created")
    r = await klien.post(f"/api/outbound/tasks/{t['id']}/scan-pick", headers=siap["h"], params={"actual_qty": 1})
    assert r.status_code == 409, r.text
    assert _teks(r) == PESAN
    assert await _status(db, t) == "created"


async def test_BTP3_maju_tahap_diblok(klien, db, siap):
    so = await _ajukan(klien, db, siap)
    t = await _tugas(db, so, "created")
    r = await klien.post(f"/api/wms/tasks/{t['id']}/advance", headers=siap["h"])
    assert r.status_code == 409, r.text
    assert _teks(r) == PESAN
    assert await _status(db, t) == "created", "status tugas tidak berubah"


async def test_BTP3_eskalasi_tutup_sisa_diblok(klien, db, siap):
    so = await _ajukan(klien, db, siap)
    t = await _tugas(db, so, "escalated", picked_qty=4.0,
                     escalation={"status": "open", "prev_status": "picking", "reason": "stok kurang"})
    r = await klien.post(f"/api/outbound/tasks/{t['id']}/resolve-escalation", headers=siap["h"],
                         params={"close_remainder": "true"})
    assert r.status_code == 409, r.text
    assert _teks(r) == PESAN
    assert await _status(db, t) == "escalated"


async def test_BTP3_batal_item_pesanan_khusus_diblok(klien, db, siap):
    from services import so_line_cancel_service as so_line
    so = await _ajukan(klien, db, siap)
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    with pytest.raises(HTTPException) as e:
        await so_line.check(o, "odi_apa_saja")
    assert e.value.status_code == 409 and e.value.detail == PESAN


async def test_BTP3_ditolak_pulih(klien, db, siap):
    so = await _ajukan(klien, db, siap)
    t = await _tugas(db, so, "created")
    assert (await klien.post(f"/api/wms/tasks/{t['id']}/advance", headers=siap["h"])).status_code == 409
    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel-request/decision", headers=siap["hf"],
                         json={"decision": "reject", "note": "Pesanan jalan terus"})
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/wms/tasks/{t['id']}/advance", headers=siap["h"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "picking"


async def test_BTP3_tanpa_permintaan_tidak_ditahan(klien, db, siap):
    so = await _pesanan(klien, db, siap)
    t = await _tugas(db, so, "created")
    r = await klien.post(f"/api/wms/tasks/{t['id']}/advance", headers=siap["h"])
    assert r.status_code == 200, r.text


async def test_BTP3_eskalasi_dibayar_pesan_baru(klien, db, siap):
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    t = await _tugas(db, so, "escalated", picked_qty=4.0,
                     escalation={"status": "open", "prev_status": "picking", "reason": "stok kurang"})
    r = await klien.post(f"/api/outbound/tasks/{t['id']}/resolve-escalation", headers=siap["h"],
                         params={"close_remainder": "true"})
    assert r.status_code == 400, r.text
    assert "Tutup sisa" in _teks(r)
    assert "retur/credit note" not in _teks(r)


async def test_BTP3_daftar_tugas_membawa_held_reason(klien, db, siap):
    so_a = await _ajukan(klien, db, siap)
    so_b = await _pesanan(klien, db, siap)
    ta, tb = await _tugas(db, so_a, "created"), await _tugas(db, so_b, "created")
    r = await klien.get("/api/outbound/tasks", headers=siap["h"], params={"limit": 500})
    assert r.status_code == 200, r.text
    baris = {x["id"]: x for x in r.json()}
    assert baris[ta["id"]]["held_reason"] == "Ditahan: menunggu keputusan batal"
    assert baris[tb["id"]].get("held_reason") in (None, "")


async def test_BTP3_wms_tasks_membawa_held_reason(klien, db, siap):
    """Daftar `/api/wms/tasks` (layar HP & Operasi Gudang) membawa tanda tahan yang sama dengan daftar outbound."""
    so_a = await _ajukan(klien, db, siap)
    so_b = await _pesanan(klien, db, siap)
    ta, tb = await _tugas(db, so_a, "created"), await _tugas(db, so_b, "created")
    r = await klien.get("/api/wms/tasks", headers=siap["h"])
    assert r.status_code == 200, r.text
    baris = {x["id"]: x for x in r.json()}
    assert baris[ta["id"]]["held_reason"] == "Ditahan: menunggu keputusan batal"
    assert baris[tb["id"]].get("held_reason") in (None, "")
