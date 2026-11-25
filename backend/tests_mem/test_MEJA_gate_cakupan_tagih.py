"""Meja gelombang 1 — perbaikan gate: daftar penagihan dibatasi ke PT yang boleh dibaca pengguna.

Gejala (audit_entity_isolation): sales PT-A melihat baris `entity_id = ent_kanda` di `/api/collection-worklist` dan
`/api/collection-reminders`. Akar: `collection_worklist` tidak membatasi PESANAN ke PT yang boleh dibaca. Perbaikan:
parameter `entity_ids` (cakupan PT) di layanan + `entity_ctx`/`resolve_scope_ids` di rute.

FIXTURE: satu pelanggan milik sales (PT `ent_ksc`) dengan dua pesanan sama-sama sudah dikirim dan lewat jatuh tempo —
satu `entity_id="ent_ksc"`, satu `entity_id="ent_kanda"`. ALUR: layanan dipanggil langsung + rute HTTP.
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
KANDA = "ent_kanda"


def _id(awal: str) -> str:
    return f"{awal}_mjgt_{uuid.uuid4().hex[:8]}"


def _jam(tanggal: str) -> str:
    return f"{tanggal}T03:00:00+00:00"


async def _pesanan(db, cid: str, nama: str, entity_id: str, sales: dict) -> dict:
    from services import billing_schedule_service as bss
    from services import gl_service as gl
    so = {"id": _id("so"), "number": f"SO-MJGT-{uuid.uuid4().hex[:5]}", "entity_id": entity_id, "customer_id": cid,
          "customer_name": nama, "status": "shipped", "grand_total": 1_000_000.0, "total_amount": 1_000_000.0,
          "ppn_amount": 0.0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid",
          "payment_term_code": "NET30", "payment_term_days": 30, "items": [], "sales_id": sales["id"],
          "sales_name": sales["name"], "created_at": _jam("2026-08-25"), "confirmed_at": _jam("2026-08-25")}
    await db.sales_orders.insert_one(dict(so))
    await bss.on_order_confirmed(so["id"])
    shid, nomor = _id("shp"), f"SJ-{so['number'][-5:]}"
    await db.shipments.insert_one({"id": shid, "shipment_no": nomor, "order_id": so["id"], "entity_id": entity_id,
                                   "status": "dispatched", "created_at": _jam("2026-09-01")})
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": 1_000_000.0, "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": 1_000_000.0}],
                           description=f"Pengakuan penjualan {so['number']} · {nomor}", date=_jam("2026-09-01"),
                           source_type="shipment_revenue", source_id=shid, entity_id=entity_id, created_by="system",
                           source_label=nomor, ref={"order_id": so["id"], "order_number": so["number"]})
    await bss.on_shipment_posted(so["id"], nomor)
    return so


@pytest.fixture(scope="module")
async def data(db, akun):
    sales = await akun("sales", entitas=(KSC,))
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": "Toko Gate Tagih", "entity_id": KSC, "status": "active",
                                   "payment_profile": {}, "deposit_balance": 0.0, "assigned_sales_id": sales["id"]})
    so_ksc = await _pesanan(db, cid, "Toko Gate Tagih", KSC, sales)
    so_kanda = await _pesanan(db, cid, "Toko Gate Tagih", KANDA, sales)
    return {"sales": sales, "cid": cid, "ksc": so_ksc["id"], "kanda": so_kanda["id"]}


def _ids(rows) -> set:
    return {r["order_id"] for r in rows}


async def test_worklist_tidak_memuat_pesanan_pt_lain(data):
    from services.customer_service import collection_worklist
    rows = await collection_worklist(data["sales"], entity_ids=[KSC])
    assert _ids(rows) == {data["ksc"]}
    assert {r["entity_id"] for r in rows} == {KSC}


async def test_reminders_meneruskan_cakupan(data):
    from services.customer_service import collection_reminders
    rows = await collection_reminders(data["sales"], days_ahead=30, entity_ids=[KSC])
    assert _ids(rows) == {data["ksc"]}


async def test_tanpa_entity_ids_perilaku_lama(data):
    from services.customer_service import collection_reminders, collection_worklist
    assert _ids(await collection_worklist(data["sales"])) == {data["ksc"], data["kanda"]}
    assert _ids(await collection_reminders(data["sales"], days_ahead=30)) == {data["ksc"], data["kanda"]}


async def test_rute_dibatasi_pt_pengguna(klien, sesi, data):
    h = await sesi(data["sales"], entitas=KSC)
    for path in ("/api/collection-worklist", "/api/collection-reminders"):
        r = await klien.get(path, headers=h)
        assert r.status_code == 200, r.text
        assert {x["entity_id"] for x in r.json()} <= {KSC}, path
        assert data["ksc"] in _ids(r.json()) and data["kanda"] not in _ids(r.json()), path


async def test_rute_entity_id_di_luar_izin_403(klien, sesi, data):
    h = await sesi(data["sales"], entitas=KSC)
    for path in ("/api/collection-worklist", "/api/collection-reminders"):
        r = await klien.get(path, headers=h, params={"entity_id": KANDA})
        assert r.status_code == 403, (path, r.text)
