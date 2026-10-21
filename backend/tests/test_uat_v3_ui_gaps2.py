"""Cek UI UAT v3 (2026-10-22) — celah yang ditemukan saat menjalankan skenario S8–S16 di browser.

1. Sample berbayar menunggu ACC tampil "Menunggu approval nilai" → sub-status `menunggu_persetujuan_bayar_sample`.
2. Produk lama tanpa template artikel tidak bisa dipetakan sumber restock-nya → PR dulu diblok selamanya;
   kini peringatan (artikel bertemplate tetap diblok bila belum diatur — DEC-07).
3. Pilihan petugas SPK menampilkan id peran mentah ("warehouse_admin") → label peran/divisi manusiawi.
4. Meja Finance: antrean retur selesai QC (kecuali Penggantian) & sample berbayar menunggu ACC bayar;
   Meja Admin Sales: retur tukar yang belum dibuatkan pesanan pengganti.
5. Transfer "Untuk memenuhi SO" hanya mencari roll "reserved", padahal roll SO terkonfirmasi "committed" → kini
   keduanya; SO yang sudah mulai diambil tidak ditawarkan.
Jalankan: cd /app/backend && python -m pytest tests/test_uat_v3_ui_gaps2.py -p no:randomly -n 0 -q
"""
import asyncio
import importlib
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402

DB = base.DB


def _run(mod_names, coro_fn):
    """Klien Motor baru per loop (pola tes layanan di repo ini)."""
    async def main():
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
        mods = [importlib.import_module(m) for m in mod_names]
        olds = [m.db for m in mods]
        for m in mods:
            m.db = db
        try:
            return await coro_fn(db)
        finally:
            for m, o in zip(mods, olds):
                m.db = o
    return asyncio.run(main())


@pytest.fixture(scope="module")
def u():
    return {k: base.Api(e) for k, e in (("sadm", "salesadmin@kainnusantara.id"), ("fin", "finance@kainnusantara.id"),
                                       ("whadm", "wh.admin@kainnusantara.id"))}


def _queue(desk, qid):
    return next(q for q in desk["queues"] if q["id"] == qid)


def test_substatus_sample_berbayar_menunggu_acc_bayar():
    from services.so_status import derive_stage_substatus, SUBSTATUS_LABELS
    _, subs = derive_stage_substatus({"status": "waiting_approval",
                                      "pending_approvals": [{"type": "pembayaran_sampel", "status": "pending"}]})
    assert subs == ["menunggu_persetujuan_bayar_sample"]          # dulu "menunggu_approval_nilai"
    assert "bayar sample" in SUBSTATUS_LABELS[subs[0]]


def test_restock_produk_tanpa_template_hanya_peringatan():
    from services import restock_source_service as rs

    async def go(_db):
        orig = rs.unknown_policy

        async def block(_entity):
            return "block"
        rs.unknown_policy = block
        try:
            out = await rs.check_lines([({"id": "p_lama", "name": "Produk lama", "stage": "finished"}, "purchase")],
                                       reason="", entity_id=base.ENT, where="PR")
            with pytest.raises(rs.RestockRouteError):    # artikel bertemplate tanpa mapping tetap diblok (DEC-07)
                await rs.check_lines([({"id": "p_art", "name": "Artikel", "stage": "finished",
                                        "template_id": f"ptpl_uji_{uuid.uuid4().hex[:6]}"}, "purchase")],
                                     reason="", entity_id=base.ENT, where="PR")
            return out
        finally:
            rs.unknown_policy = orig
    out = _run(["services.restock_source_service"], go)
    assert out["routes"][0]["mode"] == "no_template" and out["warnings"], out


def test_label_petugas_spk_tanpa_id_peran_mentah(u):
    c, meta = u["whadm"].call("GET", "/inspections/meta")
    assert c == 200, meta
    labels = [o["label"] for o in meta["officers"]]
    assert labels, meta
    raw = ("warehouse_admin", "md_quality", "· qc", "· warehouse", "· manager")
    assert not [lb for lb in labels if lb.endswith(raw)], labels


def test_meja_finance_dan_admin_sales_punya_antrean_retur_dan_sample(u):
    c, fd = u["fin"].call("GET", "/finance/desk")
    assert c == 200, fd
    retur = _queue(fd, "retur_putus_nilai")
    _queue(fd, "sample_acc_bayar")
    ids = [r["ref_id"] for r in retur["rows"]]
    if ids:   # penggantian (tukar barang) bukan keputusan nilai Finance
        assert not DB.sales_returns.count_documents({"id": {"$in": ids}, "return_type": "penggantian"})
    c, sd = u["sadm"].call("GET", "/sales-admin/desk")
    assert c == 200, sd
    q = _queue(sd, "retur_tukar")
    for r in q["rows"]:
        doc = DB.sales_returns.find_one({"id": r["ref_id"]}, {"_id": 0, "return_type": 1, "status": 1})
        assert doc["return_type"] == "penggantian" and doc["status"] == "credit_settled"


def test_transfer_pemenuhan_so_menerima_roll_committed_dan_menolak_so_yang_sudah_diambil():
    tag = uuid.uuid4().hex[:8]
    wh, so_id, roll_id = f"wh_uji_{tag}", f"so_uji_{tag}", f"roll_uji_{tag}"
    DB.sales_orders.insert_one({"id": so_id, "number": f"UJI/SO-{tag}", "status": "confirmed", "entity_id": base.ENT,
                                "customer_name": "Uji"})
    DB.inventory_rolls.insert_one({"id": roll_id, "roll_no": f"RL-UJI-{tag}", "product_id": "prod_uji", "warehouse_id": wh,
                                   "owner_entity_id": base.ENT, "status": "committed", "length_remaining": 10.0,
                                   "reserved_ref": {"type": "sales_order", "id": so_id}})
    try:
        from services import transfer_receipt_service as trs

        async def opts(_db):
            return await trs.so_options(wh, [])
        got = _run(["services.transfer_receipt_service"], opts)
        assert [s["id"] for s in got] == [so_id], got                 # dulu kosong: hanya status "reserved"

        async def rolls(_db):
            return await trs.so_rolls(so_id, wh)
        assert [r["roll_id"] for r in _run(["services.transfer_receipt_service"], rolls)] == [roll_id]

        DB.sales_orders.update_one({"id": so_id}, {"$set": {"status": "picked"}})
        assert _run(["services.transfer_receipt_service"], opts) == []   # sudah mulai diambil → tidak ditawarkan

        async def attach(_db):
            return await trs.attach_committed_rolls("trn_uji", so_id, [roll_id], wh, "prod_uji")
        with pytest.raises(Exception) as ei:
            _run(["services.transfer_receipt_service"], attach)
        assert "mulai diambil" in str(getattr(ei.value, "detail", ei.value))
    finally:
        DB.sales_orders.delete_one({"id": so_id})
        DB.inventory_rolls.delete_one({"id": roll_id})
