"""Fase 4 · R5 (26 Okt 2026) — antrean persetujuan, Backorder, gerbang akses. Uji tingkat layanan, TANPA HTTP.

* INV-APPR-01 — 6 antrean baru (klaim desain, override kredit mandiri, nota kredit batal item, susut makloon, selisih
  terima PO, pengecualian retur) + SO MATI tidak lagi dihitung `sales_order` + tahanan yang sudah DITOLAK MD Quality
  keluar dari `inspection_hold`. Anti dobel-hitung dengan antrean lama (invarian C).
* Matriks divisi — pengaju tampil sebagai NAMA orang (email/id → nama), akun asli di `requester_account`.
* Backorder (keputusan pemilik #2) — `alert_ops_service`: Backorder = `waiting_stock`; baris pendingan hanya SO hidup.
* Gerbang akses — tab `inventory-lots` bersumber izin `field_visibility` (sales tanpa izin LOT → tersembunyi).

Jalankan (DB uji, data bertanda TEST_R5 dihapus lagi):
  cd /app/backend && DB_NAME=kn_test_trial python -m pytest tests/test_phase4_r5.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

import pytest
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from access_modules import view_resources_index  # noqa: E402
from permissions_config import DEFAULT_PERMISSIONS  # noqa: E402
from services import alert_ops_service as alerts  # noqa: E402
from services import approval_backlog_service as abl  # noqa: E402
from services import approval_matrix_service as amx  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
ENT = f"ent_TEST_R5_{TAG}"
T0 = "2026-10-20T00:00:00+00:00"
USER = {"id": f"user_TEST_R5_{TAG}", "email": f"pengaju.r5.{TAG}@test.local", "name": "Pengaju Uji R5", "role": "sales"}
ADMIN = {"id": f"user_TEST_R5_{TAG}_adm", "email": f"admin.r5.{TAG}@test.local", "name": "Admin Uji", "role": "admin"}
COLLS = ("sales_orders", "credit_overrides", "credit_notes", "design_gallery", "makloon_orders", "po_variance_tasks",
         "sales_returns", "inspections", "special_orders", "users")


@pytest.fixture(scope="module", autouse=True)
def seed():
    d = {"entity_id": ENT, "created_at": T0, "updated_at": T0}
    DB.users.insert_one({**USER})
    DB.sales_orders.insert_many([
        # SO mati dengan entri approval basi → bukan antrean
        {**d, "id": f"so_R5_{TAG}_dead", "number": f"R5-{TAG}-SO-X", "status": "expired",
         "pending_approvals": [{"id": "pa1", "type": "kredit", "status": "pending"}]},
        {**d, "id": f"so_R5_{TAG}_cx", "number": f"R5-{TAG}-SO-C", "status": "cancelled",
         "pending_approvals": [{"id": "pa2", "type": "nilai", "status": "pending"}]},
        # SO hidup menunggu ACC → antrean
        {**d, "id": f"so_R5_{TAG}_live", "number": f"R5-{TAG}-SO-L", "status": "reserved",
         "pending_approvals": [{"id": "pa3", "type": "nilai", "status": "pending"}]},
        # Backorder (status) vs sisa pendingan (penanda) vs penanda basi
        {**d, "id": f"so_R5_{TAG}_bo", "number": f"R5-{TAG}-BO", "status": "waiting_stock", "has_backorder": True,
         "backorders": [{"product_id": f"p_{TAG}", "backorder_qty": 5}]},
        {**d, "id": f"so_R5_{TAG}_pt", "number": f"R5-{TAG}-PT", "status": "reserved", "has_backorder": True,
         "backorders": [{"product_id": f"p_{TAG}", "backorder_qty": 2}]},
        {**d, "id": f"so_R5_{TAG}_old", "number": f"R5-{TAG}-OLD", "status": "cancelled", "has_backorder": True,
         "backorders": [{"product_id": f"p_{TAG}", "backorder_qty": 9}]},
    ])
    DB.credit_overrides.insert_many([
        {**d, "id": f"cro_R5_{TAG}_solo", "customer_name": "Toko Mandiri", "order_id": "", "status": "pending",
         "reason": "Limit kurang", "requested_by": "Sales"},
        {**d, "id": f"cro_R5_{TAG}_so", "customer_name": "Toko SO", "order_id": f"so_R5_{TAG}_dead",
         "status": "pending", "reason": "Over-limit", "requested_by": "Sales"},
    ])
    DB.credit_notes.insert_many([
        {**d, "id": f"cn_R5_{TAG}", "number": f"R5-{TAG}-CN", "source": "od_item_cancel", "status": "pending_finance",
         "customer_name": "Toko CN"},
    ])
    DB.design_gallery.insert_many([
        {**d, "id": f"dg_R5_{TAG}_ok", "code": f"R5-{TAG}-DSN", "title": "Desain klaim", "status": "approved",
         "claims": [{"id": "c1", "status": "pending"}]},
        # sudah dihitung antrean `design_gallery` (pengesahan) → tidak dobel
        {**d, "id": f"dg_R5_{TAG}_pa", "code": f"R5-{TAG}-DSN2", "title": "Desain baru", "status": "pending_approval",
         "claims": [{"id": "c2", "status": "pending"}]},
    ])
    DB.makloon_orders.insert_many([
        {**d, "id": f"mko_R5_{TAG}_loss", "mko_number": f"R5-{TAG}-MKO", "status": "cancelled",
         "steps": [{"seq": 1, "material_losses": [{"id": "l1", "status": "pending_approval"}]}]},
        {**d, "id": f"mko_R5_{TAG}_both", "mko_number": f"R5-{TAG}-MKO2", "status": "cancelled",
         "steps": [{"seq": 1, "claim": {"status": "pending_approval"},
                    "material_losses": [{"id": "l2", "status": "pending_approval"}]}]},
    ])
    DB.po_variance_tasks.insert_many([
        {**d, "id": f"pvt_R5_{TAG}", "po_number": f"R5-{TAG}-PO", "product_name": "Kain", "status": "open"},
        {**d, "id": f"pvt_R5_{TAG}_x", "po_number": f"R5-{TAG}-PO2", "product_name": "Kain", "status": "decided"},
    ])
    DB.sales_returns.insert_many([
        {**d, "id": f"sr_R5_{TAG}", "number": f"R5-{TAG}-SR", "status": "approved", "customer_name": "Toko R",
         "exceptions": [{"id": "e1", "status": "pending"}]},
        {**d, "id": f"sr_R5_{TAG}_pa", "number": f"R5-{TAG}-SR2", "status": "pending_approval",
         "exceptions": [{"id": "e2", "status": "pending"}]},
    ])
    DB.inspections.insert_many([
        {**d, "id": f"ins_R5_{TAG}_wait", "number": f"R5-{TAG}-INS", "status": "done",
         "lines": [{"id": "ln1", "hold": True}]},
        {**d, "id": f"ins_R5_{TAG}_rej", "number": f"R5-{TAG}-INS2", "status": "done",
         "lines": [{"id": "ln2", "hold": True, "md_quality_decision": {"action": "reject"}}]},
    ])
    DB.special_orders.insert_one({**d, "id": f"sord_R5_{TAG}", "number": f"R5-{TAG}-SORD", "status": "pending_approval",
                                  "created_by": USER["email"], "total_amount": 1000,
                                  "custom_item": {"description": "Kain custom"}})
    yield
    for c in COLLS:
        DB[c].delete_many({"entity_id": ENT})
    DB.users.delete_many({"id": USER["id"]})


def _counts():
    bl = run(abl.backlog(ENT))
    return {r["key"]: r["count"] for r in bl["all_items"]}


def test_antrean_baru_dan_so_mati():
    c = _counts()
    assert c["sales_order"] == 1                       # hanya SO hidup; SO kedaluwarsa/batal tidak menunggu siapa pun
    assert c["credit_override"] == 1                   # override tertaut SO = rincian entri SO (bukan dobel)
    assert c["od_cancel_credit_note"] == 1
    assert c["design_claim"] == 1 and c["design_gallery"] == 1
    assert c["makloon_loss"] == 1 and c["makloon_claim"] == 1
    assert c["po_variance"] == 1
    assert c["sales_return_exception"] == 1 and c["sales_return"] == 1
    assert c["inspection_hold"] == 1                   # baris yang sudah DITOLAK MD Quality bukan lagi menunggu


def test_anti_dobel_hitung_per_dokumen():
    seen = {}
    for key, _label, _view, coll, query in abl.QUEUES:
        for d in DB[coll].find({**query, "entity_id": ENT}, {"_id": 0, "id": 1}):
            ref = (coll, d["id"])
            assert ref not in seen, f"{ref} dihitung {seen.get(ref)} dan {key}"
            seen[ref] = key


def test_umur_tunggu_dan_nomor_antrean_baru():
    rows = run(abl.oldest(ENT, limit=50))
    nums = {r["key"]: r["number"] for r in rows}
    assert nums["od_cancel_credit_note"] == f"R5-{TAG}-CN"
    assert nums["po_variance"] == f"R5-{TAG}-PO"
    assert nums["credit_override"] == "Toko Mandiri"
    assert all(r["days_waiting"] >= 0 for r in rows)
    hold = run(abl.queue_detail("inspection_hold", ENT, limit=10))
    assert [r["number"] for r in hold["rows"]] == [f"R5-{TAG}-INS"]


def test_matriks_divisi_pengaju_nama_orang():
    q = run(amx.my_queue(ADMIN, ENT, "po_custom"))
    row = next(it for it in q["items"] if it["number"] == f"R5-{TAG}-SORD")
    assert row["requester"] == "Pengaju Uji R5" and row["requester_name"] == "Pengaju Uji R5"
    assert row["requester_account"] == USER["email"]
    # Nama yang sudah nama tidak disentuh; akun teknis tetap (layar memetakan "seed" → "Sistem (data awal)").
    assert run(amx._person_names(["Budi Santoso", "seed"])) == {}


def test_backorder_satu_definisi():
    assert alerts.BACKORDER_STATUS == "waiting_stock"
    nums = {d["number"] for d in DB.sales_orders.find({**alerts.pending_stock_query(), "entity_id": ENT})}
    assert nums == {f"R5-{TAG}-BO", f"R5-{TAG}-PT"}      # SO batal dengan penanda basi tidak ikut notifikasi
    bo = DB.sales_orders.count_documents({"entity_id": ENT, "status": alerts.BACKORDER_STATUS})
    assert bo == 1
    from routers import sales_orders_extra as soe
    import inspect
    src = inspect.getsource(soe.get_orders_stats)
    assert '"status": _alerts.BACKORDER_STATUS' in src and "partial_backorder_count" in src


def test_lot_silsilah_bersumber_izin_field_visibility():
    idx = view_resources_index()
    assert idx["inventory-lots"] == ["field_visibility"]
    sales = DEFAULT_PERMISSIONS["sales"]
    assert not sales.get("field_visibility")                          # sales: tab tersembunyi
    assert "lot" in DEFAULT_PERMISSIONS["warehouse"]["field_visibility"]   # gudang tetap
