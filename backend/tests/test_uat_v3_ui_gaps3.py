"""Cek UI UAT v3 (2026-10-22) — celah S13 (Pesanan Khusus) yang ditemukan saat menjalankan alur di browser.

1. Label peran memakai registri: "md" → "MD", "warehouse_admin" → "Admin Gudang" (dulu "Md", "Warehouse Admin").
2. DSR/sample/spesifikasi dari OD tercatat atas nama Sales pembuat OD (bukan Manajer yang menyetujui) → Manajer
   tidak terblokir pemisahan tugas saat ACC desain / pemenang / spesifikasi.
3. Nomor SORD & tanggal SPK memakai tanggal WIB (dulu UTC: dokumen pukul 05.00 WIB bernomor tanggal kemarin).
4. Meja MD: permintaan desain "approved" (sudah ACC) tidak lagi tampil "belum ditugaskan"; sample yang pemenangnya
   sudah dipilih tetapi SKU gagal lahir (spesifikasi belum lengkap) tampil di antrean.
5. SKU yang lahir SESUDAH pemenang dipilih (ACC spesifikasi belakangan) dikaitkan ke keputusan sample → harga OD
   bisa dikunci; artikel baru mendapat sumber restock bawaan Supplier (pemenangnya supplier).
6. OD terstruktur tidak bisa "Mulai Produksi" sebelum harga final dikunci.
7. Gudang bawaan penerimaan OD = gudang khusus PT itu (dulu gudang bersama PT lain karena urut kode).
8. OD multi-item: PO item kedua tiba setelah tugas ambil item pertama lahir → item kedua tetap dapat tugas ambil.
9. Keputusan pemilik: pemenang sample (tahap ACC Sample) boleh diputus Manajer ATAU MD.
10. Isyarat harga khusus tidak lagi menyebut Admin Sales sebagai penyetuju (semua harga khusus diputus Manajer/Admin).
11. Pengajuan harga khusus tanpa SO = harga langganan (dulu lingkup "pesanan" tanpa SO: disetujui pun tak terpakai);
    layar HP Minta Harga Khusus memuat semua pelanggan PT (dulu kosong bila pelanggan belum punya sales).
12. Trial 22 Okt — Keep tidak memuat pesanan sample / SO Pesanan Khusus yang dikonfirmasi otomatis.
Jalankan: cd /app/backend && python -m pytest tests/test_uat_v3_ui_gaps3.py -p no:randomly -n 0 -q
"""
import asyncio
import importlib
import os
import sys
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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


def test_label_peran_dari_registri():
    from config_divisions import role_label
    assert role_label("md") == "MD"
    assert role_label("warehouse_admin") == "Admin Gudang"
    assert role_label("md_quality") == "MD Quality"


def test_dsr_dan_sample_od_atas_nama_sales_pembuat():
    from services import special_order_routing as r
    sales = DB.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1, "name": 1})
    mgr = {"id": "user_mgr", "name": "Manajer Uji", "email": "manager@kainnusantara.id"}

    async def go(_db):
        by_id = await r._requester({"created_by_id": sales["id"]}, mgr)
        by_email = await r._requester({"created_by": "sales@kainnusantara.id"}, mgr)
        none = await r._requester({}, mgr)
        return by_id, by_email, none
    by_id, by_email, none = _run(["services.special_order_routing"], go)
    assert by_id["name"] == sales["name"] and by_email["name"] == sales["name"]
    assert none is mgr                                                   # tanpa pembuat → aktor penyetuju


def test_nomor_sord_dan_tanggal_spk_memakai_wib():
    from services import special_order_service as so
    from services import inspection_service as ins

    async def go(_db):
        return await so.generate_special_order_number(datetime(2026, 10, 21, 22, 30, tzinfo=timezone.utc))
    num = _run(["services.special_order_service"], go)
    assert num.startswith("SORD-261022-"), num                          # 05.30 WIB tanggal 22, bukan 21
    assert ins._today() == datetime.now(ZoneInfo("Asia/Jakarta")).date().isoformat()


def test_meja_md_status_desain_dan_sample_sku_belum_lahir():
    from services import work_desk_service as wd
    ent = f"ent_uji_{uuid.uuid4().hex[:6]}"
    DB.design_requests.insert_many([
        {"id": f"dsr_a_{ent}", "number": "DSR-ACC", "entity_id": ent, "status": "approved", "requested_at": "2026-10-22"},
        {"id": f"dsr_s_{ent}", "number": "DSR-BARU", "entity_id": ent, "status": "submitted", "requested_at": "2026-10-22"},
        {"id": f"dsr_r_{ent}", "number": "DSR-REV", "entity_id": ent, "status": "revision", "requested_at": "2026-10-22"}])
    DB.md_specs.insert_many([{"id": f"spec_o_{ent}", "status": "draft"}, {"id": f"spec_x_{ent}", "status": "approved"}])
    DB.md_samples.insert_many([
        {"id": f"smp_o_{ent}", "number": "SMP-MACET", "entity_id": ent, "status": "decided", "spec_id": f"spec_o_{ent}",
         "decision": {"supplier_id": "sup_x", "master_error": "Spesifikasi belum lengkap"}, "created_at": "2026-10-22"},
        {"id": f"smp_x_{ent}", "number": "SMP-SUDAH", "entity_id": ent, "status": "decided", "spec_id": f"spec_x_{ent}",
         "decision": {"supplier_id": "sup_x", "master_error": "lama"}, "created_at": "2026-10-22"}])
    try:
        async def go(_db):
            return await wd.md_desk({"name": "Uji"}, {"entity_id": ent}, [ent])
        desk = _run(["services.work_desk_service"], go)
        q = {x["id"]: x for x in desk["queues"]}
        desain = {r["number"]: r["badge"] for r in q["desain"]["rows"]}
        assert desain == {"DSR-BARU": "belum ditugaskan", "DSR-REV": "revisi desainer"}, desain   # DSR ACC tidak tampil
        sample = {r["number"]: r["badge"] for r in q["sample"]["rows"]}
        assert sample == {"SMP-MACET": "SKU belum lahir · lengkapi spesifikasi"}, sample          # spesifikasi ACC → hilang
        assert "od_pemenuhan" in q
    finally:
        DB.design_requests.delete_many({"entity_id": ent})
        DB.md_specs.delete_many({"id": {"$in": [f"spec_o_{ent}", f"spec_x_{ent}"]}})
        DB.md_samples.delete_many({"entity_id": ent})


def test_sku_lahir_belakangan_dikaitkan_ke_keputusan_sample():
    from services import rnd_sample_service as rs
    tag = uuid.uuid4().hex[:6]
    spec_id, pid, tpl, sid, ct = f"spec_{tag}", f"prod_{tag}", f"ptpl_{tag}", f"smp_{tag}", f"sct_{tag}"
    DB.product_templates.insert_one({"id": tpl, "name": f"Artikel uji {tag}"})
    DB.products.insert_one({"id": pid, "sku": f"UJI-{tag}", "name": "Produk uji", "template_id": tpl})
    DB.supplier_contracts.insert_one({"id": ct, "product_id": ""})
    DB.md_samples.insert_one({"id": sid, "number": f"SMP-{tag}", "entity_id": base.ENT, "status": "decided", "spec_id": spec_id,
                              "decision": {"supplier_id": "sup_a2b92b527a33", "supplier_name": "PT Uji", "contract_id": ct,
                                           "supplier_item_id": "sudah", "master_error": "Spesifikasi belum lengkap"}})
    try:
        async def go(_db):
            n1 = await rs.bind_decided_samples(spec_id, pid, f"UJI-{tag}", "Manajer Uji")
            n2 = await rs.bind_decided_samples(spec_id, pid, f"UJI-{tag}", "Manajer Uji")
            return n1, n2
        assert _run(["services.rnd_sample_service", "services.restock_source_service", "services.color_service"], go) == (1, 0)
        dec = DB.md_samples.find_one({"id": sid})["decision"]
        assert dec["product_id"] == pid and "master_error" not in dec
        assert DB.supplier_contracts.find_one({"id": ct})["product_id"] == pid            # kontrak pemenang terikat ke SKU
        assert DB.product_templates.find_one({"id": tpl})["restock_source"]["mode"] == "supplier"
    finally:
        DB.product_templates.delete_one({"id": tpl})
        DB.products.delete_one({"id": pid})
        DB.supplier_contracts.delete_one({"id": ct})
        DB.md_samples.delete_one({"id": sid})


def test_od_terstruktur_tidak_bisa_mulai_produksi_sebelum_harga_dikunci():
    from services import special_order_service as so
    oid = f"sord_uji_{uuid.uuid4().hex[:6]}"
    DB.special_orders.insert_one({"id": oid, "status": "confirmed", "request_types": ["labdip"], "pricing": {}})
    try:
        async def go(_db):
            return await so.transition_special_order_status(oid, "in_production", "uji@kainnusantara.id")
        with pytest.raises(ValueError) as ei:
            _run(["services.special_order_service"], go)
        assert "Kunci harga final" in str(ei.value)
        DB.special_orders.update_one({"id": oid}, {"$set": {"pricing.locked": True}})
        assert _run(["services.special_order_service"], go)["status"] == "in_production"
    finally:
        DB.special_orders.delete_one({"id": oid})


def test_gudang_bawaan_od_utamakan_gudang_khusus_pt():
    from services import special_order_phase2 as p2
    ent = f"ent_uji_{uuid.uuid4().hex[:6]}"
    DB.warehouses.insert_many([
        {"id": f"wh_a_{ent}", "code": "AAA-UJI-BERSAMA", "name": "Bersama", "sharing_mode": "shared", "entity_ids": [], "active": True},
        {"id": f"wh_z_{ent}", "code": "ZZZ-UJI-KHUSUS", "name": "Khusus", "sharing_mode": "dedicated", "entity_ids": [ent], "active": True}])
    try:
        async def go(_db):
            return await p2.default_warehouse_id(ent)
        assert _run(["services.special_order_phase2", "services.warehouse_scope_service"], go) == f"wh_z_{ent}"
    finally:
        DB.warehouses.delete_many({"id": {"$in": [f"wh_a_{ent}", f"wh_z_{ent}"]}})


def test_od_multi_item_item_kedua_tiba_belakangan_dapat_tugas_ambil():
    from services import fulfillment_status as fs
    tag = uuid.uuid4().hex[:6]
    so_id = f"so_uji_{tag}"
    allocs = [{"id": f"al_a_{tag}", "product_id": f"pa_{tag}", "warehouse_id": "wh_jakarta", "quantity": 100},
              {"id": f"al_b_{tag}", "product_id": f"pb_{tag}", "warehouse_id": "wh_jakarta", "quantity": 200}]
    DB.sales_orders.insert_one({"id": so_id, "number": f"UJI/SO-{tag}", "entity_id": base.ENT, "status": "confirmed",
                                "items": [{"product_id": f"pa_{tag}", "unit": "meter"}, {"product_id": f"pb_{tag}", "unit": "meter"}],
                                "allocations": allocs})
    DB.wms_tasks.insert_one({"id": f"wms_a_{tag}", "order_id": so_id, "flow_type": "outbound", "product_id": f"pa_{tag}"})
    try:
        async def go(_db):
            dup = await fs.create_outbound_tasks_for_order(so_id, "Uji")                       # perilaku umum: tetap lewati
            new = await fs.create_outbound_tasks_for_order(so_id, "Uji", only_products={f"pb_{tag}"})
            return dup, new
        dup, new = _run(["services.fulfillment_status"], go)
        assert dup == [] and [t["product_id"] for t in new] == [f"pb_{tag}"]
        assert DB.wms_tasks.count_documents({"order_id": so_id, "flow_type": "outbound"}) == 2
    finally:
        DB.sales_orders.delete_one({"id": so_id})
        DB.wms_tasks.delete_many({"order_id": so_id})
        DB.doc_refs.delete_many({"$or": [{"source_id": so_id}, {"target_id": so_id}]})


def test_pemenang_sample_boleh_diputus_md_tetapi_desain_tetap_manajer():
    from services import approval_matrix_service as amx
    cfg = {"mode": "enforce", "scope": "all_pending", "sod": True}
    doc = {"number": "SMP-UJI", "created_by": "Ayu Marketing"}
    md = {"role": "md", "name": "Rina Merchandiser"}
    assert amx.evaluate("sample_acc", md, doc, cfg)["allowed"] is True                 # keputusan pemilik 22 Okt
    assert amx.evaluate("sample_acc", {"role": "sales", "name": "S"}, doc, cfg)["allowed"] is False
    assert amx.evaluate("design_acc", md, doc, cfg)["allowed"] is False                # ACC desain/spesifikasi tidak berubah


def test_isyarat_harga_khusus_selalu_menyebut_manajer_sebagai_penyetuju():
    sales = base.Api("sales@kainnusantara.id")
    prod = DB.products.find_one({"price": {"$gt": 1000}, "entity_id": base.ENT}, {"_id": 0, "id": 1, "price": 1}) \
        or DB.products.find_one({"price": {"$gt": 1000}}, {"_id": 0, "id": 1, "price": 1})
    for price in (prod["price"] * 0.99, prod["price"] * 0.3):          # dalam batas & jauh di bawah batas
        c, h = sales.call("GET", f"/price-approvals/hint?product_id={prod['id']}&price={price:.0f}")
        assert c == 200, h
        assert h["approver_roles"] == ["manager", "admin"] and h["approver_label"] == "Manajer / Admin", h
        assert "admin_sales" not in str(h)                             # dulu: "penyetuju: admin_sales/manager/admin"


def test_pengajuan_harga_khusus_tanpa_so_jadi_harga_langganan():
    sales = base.Api("sales@kainnusantara.id")
    cust = DB.customers.find_one({"entity_id": base.ENT}, {"_id": 0, "id": 1})
    prod = DB.products.find_one({"price": {"$gt": 1000}}, {"_id": 0, "id": 1, "price": 1})
    c, d = sales.call("POST", "/price-approvals", {"customer_id": cust["id"], "product_id": prod["id"],
                                                   "requested_price": round(prod["price"] * 0.9), "submit_now": False,
                                                   "entity_id": base.ENT, "scope": "order", "so_id": ""})
    try:
        assert c == 200, d
        assert d["scope"] == "standing", d          # dulu "order" tanpa SO → disetujui pun tak pernah terpakai
    finally:
        DB.price_approvals.delete_one({"id": (d or {}).get("id")})


def test_daftar_pelanggan_untuk_harga_khusus_hp_memuat_pelanggan_tanpa_sales():
    sales = base.Api("sales@kainnusantara.id")
    c, rows = sales.call("GET", "/customers?for_order=true&with_credit=false")
    assert c == 200, rows
    unassigned = DB.customers.count_documents({"entity_id": base.ENT, "assigned_sales_id": {"$in": [None, ""]}})
    if unassigned:
        names = {r["name"] for r in rows}
        assert any(n in names for n in DB.customers.distinct("name", {"entity_id": base.ENT, "assigned_sales_id": {"$in": [None, ""]}}))


def test_keep_tidak_memuat_sample_dan_so_od_terkonfirmasi_otomatis():
    from services import sales_p04_service as p04
    ent = f"ent_uji_{uuid.uuid4().hex[:6]}"
    base_so = {"entity_id": ent, "customer_name": "Uji", "created_at": "2026-10-22T01:00:00+00:00", "items": []}
    DB.sales_orders.insert_many([
        {**base_so, "id": f"so_k_{ent}", "number": "KEEP-BIASA", "status": "reserved"},
        {**base_so, "id": f"so_s_{ent}", "number": "KEEP-SAMPLE", "status": "confirmed", "order_type": "sample"},
        {**base_so, "id": f"so_o_{ent}", "number": "KEEP-OD", "status": "confirmed", "admin_verified": True}])
    try:
        async def go(_db):
            return await p04.keep_pending({"entity_id": ent}, ent)
        out = _run(["services.sales_p04_service"], go)
        assert [k["number"] for k in out["keep"]] == ["KEEP-BIASA"], out["keep"]
    finally:
        DB.sales_orders.delete_many({"entity_id": ent})
