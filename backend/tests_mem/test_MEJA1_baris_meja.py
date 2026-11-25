"""MEJA-1 — kontrak baris meja (rancangan meja-kerja-di-tempat §5.6): entity_id, age_kind, at nyata, teks utuh."""
from __future__ import annotations
import ast, inspect, re
from pathlib import Path
import pytest
from core_utils import now_iso

pytestmark = pytest.mark.anyio
ROOT = Path(__file__).resolve().parents[1]
BERKAS = ["services/work_desk_service.py", "services/role_desk_service.py", "routers/sample_orders.py"]
PANJANG = "Butuh kain untuk pesanan pelanggan besar di Medan — " * 3   # ±150 huruf


def test_row_membawa_entity_id_dan_age_kind():
    from services.work_desk_service import _row
    r = _row(ref_type="x", ref_id="1", number="N", title="T", entity_id="ent_ksc", age_kind="overdue")
    assert r["entity_id"] == "ent_ksc" and r["age_kind"] == "overdue"
    d = _row(ref_type="x", ref_id="1", number="N", title="T")
    assert d["entity_id"] == "" and d["age_kind"] == "wait" and "at" not in d


@pytest.mark.parametrize("rel", BERKAS)
def test_setiap_row_memberi_entity_id_dan_at(rel):
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    kurang = [(n.lineno, k) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_row"
              for k in ("entity_id", "at") if k not in {kw.arg for kw in n.keywords}]
    assert kurang == []


def test_server_tidak_memotong_teks():
    wd = (ROOT / "services/work_desk_service.py").read_text(encoding="utf-8")
    rd = (ROOT / "services/role_desk_service.py").read_text(encoding="utf-8")
    assert set(re.findall(r"\[:(\d+)\]", wd)) <= {"10"}      # hanya potong tanggal ISO
    assert set(re.findall(r"\[:(\d+)\]", rd)) <= {"2"}       # hanya pecah `koleksi:id`
    from routers import sample_orders
    assert "[:" not in inspect.getsource(sample_orders._rows)


def test_collection_worklist_membawa_entity_id():
    from services import customer_service
    assert '"entity_id": o.get("entity_id"' in inspect.getsource(customer_service.collection_worklist)


async def test_alasan_permintaan_internal_utuh(klien, db, kepala_admin):
    await db.internal_requests.insert_one({"id": "pin_meja1", "number": "PIN-MEJA1", "reason": PANJANG,
                                           "status": "submitted", "entity_id": "ent_ksc", "created_at": now_iso(), "items": []})
    r = await klien.get("/api/sales-admin/desk", headers=kepala_admin)
    assert r.status_code == 200, r.text
    q = next(q for q in r.json()["queues"] if q["id"] == "permintaan_internal")
    row = next(x for x in q["rows"] if x["ref_id"] == "pin_meja1")
    assert row["title"] == PANJANG and row["entity_id"] == "ent_ksc"


async def test_barang_kurang_semua_baris(klien, kepala_admin, monkeypatch):
    async def papan(scope):
        return [{"order_id": "so_kurang", "order_number": "SO-KURANG", "customer_name": "Toko K", "created_at": now_iso(),
                 "coverage": "uncovered", "product_name": f"Kain {i}", "backorder_qty": 5, "unit": "yard",
                 "owner_entity_id": "ent_ksc"} for i in (1, 2, 3)]
    monkeypatch.setattr("services.stock_bucket_service.pending_so_board", papan)
    r = await klien.get("/api/sales-admin/desk", headers=kepala_admin)
    row = next(x for q in r.json()["queues"] if q["id"] == "perlu_dipenuhi" for x in q["rows"] if x["ref_id"] == "so_kurang")
    for i in (1, 2, 3):
        assert f"Kain {i} kurang 5 yard" in row["subtitle"]
    assert row["entity_id"] == "ent_ksc"


async def test_jatuh_tempo_at_nyata_dan_lewat(klien, kepala_admin, monkeypatch):
    async def tagih(actor, days_ahead=30, sales_id=None, entity_id=None, entity_ids=None):
        return [{"order_id": "so_jt", "order_number": "SO-JT", "customer_id": "cus_jt", "customer_name": "Toko JT",
                 "outstanding": 500000, "days_late": 8, "overdue": True, "due_date": "2026-11-17", "sales_name": "Ayu",
                 "entity_id": "ent_ksc"},
                {"order_id": "so_nanti", "order_number": "SO-NANTI", "customer_id": "cus_jt", "customer_name": "Toko JT",
                 "outstanding": 100000, "days_late": -3, "overdue": False, "due_date": "2026-11-28", "sales_name": "Ayu",
                 "entity_id": "ent_ksc"}]
    monkeypatch.setattr("services.customer_service.collection_reminders", tagih)
    fin = (await klien.get("/api/finance/desk", headers=kepala_admin)).json()["queues"]
    jt = next(x for q in fin if q["id"] == "jatuh_tempo" for x in q["rows"] if x["ref_id"] == "so_jt")
    assert jt["at"].startswith("2026-11-17") and jt["age_kind"] == "overdue" and jt["age_days"] == 8
    assert jt["entity_id"] == "ent_ksc"
    um = {x["order_id"]: x for q in fin if q["id"] == "uang_masuk" for x in q["rows"]}
    assert um["so_jt"]["age_kind"] == "overdue" and um["so_jt"]["at"].startswith("2026-11-17")
    assert um["so_nanti"]["age_kind"] == "wait" and um["so_nanti"].get("at", "") == ""
    sa = (await klien.get("/api/sales-admin/desk", headers=kepala_admin)).json()["queues"]
    sajt = next(x for q in sa if q["id"] == "jatuh_tempo" for x in q["rows"] if x["ref_id"] == "so_jt")
    assert sajt["age_kind"] == "overdue" and sajt["at"].startswith("2026-11-17")


async def test_baris_sample_semua_barang_dan_at(klien, db, kepala_admin):
    t = now_iso()
    await db.sales_orders.insert_one({
        "id": "sos_meja1", "number": "KSC/SOS-M1", "order_type": "sample", "status": "approved", "sample_billing": "free",
        "grand_total": 0, "customer_name": "Toko Sample", "entity_id": "ent_ksc", "created_at": t, "updated_at": t,
        "items": [{"product_id": f"p{i}", "product_name": f"Sample {i}", "quantity": 1, "unit": "meter"} for i in range(1, 5)]})
    r = await klien.get("/api/sample-orders/desk", headers=kepala_admin)
    row = next(x for q in r.json()["queues"] if q["id"] == "siap_gudang" for x in q["rows"] if x["ref_id"] == "sos_meja1")
    assert all(f"Sample {i}" in row["subtitle"] for i in range(1, 5))
    assert row["at"] == t and row["entity_id"] == "ent_ksc"


async def test_hutang_jatuh_tempo_membawa_pt_dan_tanggal(klien, db, kepala_admin):
    await db.purchase_orders.insert_one({
        "id": "po_meja1", "po_number": "PO-MEJA1", "supplier_name": "Pemasok M", "supplier_id": "sup_m", "status": "receiving",
        "payment_due_date": "2026-11-10", "grand_total": 900000, "amount_paid": 0, "payment_status": "unpaid",
        "entity_id": "ent_ksc", "created_at": now_iso()})
    fin = (await klien.get("/api/finance/desk", headers=kepala_admin)).json()["queues"]
    row = next(x for q in fin if q["id"] == "hutang_jatuh_tempo" for x in q["rows"] if x["ref_id"] == "po_meja1")
    assert row["entity_id"] == "ent_ksc" and row["at"].startswith("2026-11-10") and row["age_kind"] == "overdue"
