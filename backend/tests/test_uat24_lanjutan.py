"""UAT 24 Okt — lanjutan sesudah F5: temuan sapuan UI yang perlu backend.

* ATP Status Stok (057) = ATP Multi-Kantong (058): backorder tanpa gudang dikurangkan SEKALI per produk × PT.
* Saldo rekening = ringkasan kas: transaksi kas tanpa rekening ikut rekening tunggal PT untuk jenis kasnya.
* Profitabilitas: qty per satuan (yard dan kg tidak dijumlah).
* Beranda admin: "Bulan Ini" ≥ "Hari Ini" (populasi SO sama).
* KPI desainer: akun teknis (system-seed) tidak ikut peringkat.
* Cetak/pratinjau PDF: status berlabel Indonesia.
* Pelacak SO di meja Admin Sample: SO sampel, bukan SO roll biasa.

Jalankan: cd /app/backend && python -m pytest tests/test_uat24_lanjutan.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402 — loop tempat klien Motor terikat

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]
ENT = "ent_ksc"
SOS: list = []
ACCS: list = []
TXNS: list = []


def _login(email, entity=ENT):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}


ADMIN = _login("admin@kainnusantara.id")


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    DB.sales_orders.delete_many({"id": {"$in": SOS}})
    DB.bank_accounts.delete_many({"id": {"$in": ACCS}})
    DB.cash_transactions.delete_many({"id": {"$in": TXNS}})


def _backorder_so(product_id, lines, status="waiting_stock", warehouse_id=""):
    sid = f"so_TEST_LJ_{T}_{len(SOS)}"
    DB.sales_orders.insert_one({
        "id": sid, "number": f"SO-TLJ-{T}-{len(SOS)}", "entity_id": ENT, "status": status, "has_backorder": True,
        "warehouse_id": warehouse_id, "customer_name": "TEST lanjutan", "items": [], "created_at": "2026-10-25T01:00:00+00:00",
        "backorders": [{"product_id": product_id, "backorder_qty": q, "warehouse_id": wh, "status": "open"} for q, wh in lines],
    })
    SOS.append(sid)
    return sid


# ── ATP 057 vs 058 ───────────────────────────────────────────────────────────
def test_unassigned_backorder_counted_once_per_product_entity():
    from services.atp_policy import backorder_map, pending_backorder_qty
    pid = f"prod_TEST_LJ_{T}"
    _backorder_so(pid, [(30.0, ""), (20.0, "wh_A")])
    _backorder_so(pid, [(5.0, "wh_B")])
    assert run(pending_backorder_qty(pid, ENT)) == 55.0
    # per gudang: dulu backorder tanpa gudang ikut dikurangkan di SETIAP gudang
    assert run(pending_backorder_qty(pid, ENT, "wh_A", include_unassigned=False)) == 20.0
    assert run(pending_backorder_qty(pid, ENT, "wh_B", include_unassigned=False)) == 5.0
    assert run(pending_backorder_qty(pid, ENT, "wh_A")) == 50.0   # perilaku lama tetap ada untuk pemanggil lain
    rec = run(backorder_map([pid]))[(pid, ENT)]
    assert rec == {"total": 55.0, "unassigned": 30.0, "by_wh": {"wh_A": 20.0, "wh_B": 5.0}}


def test_bucket_board_atp_equals_atp_detail():
    """Satu produk ber-saldo di ≥2 gudang + backorder tanpa gudang → total ATP papan = ATP detail (Status Stok)."""
    pipe = [{"$match": {"owner_entity_id": ENT}}, {"$group": {"_id": "$product_id", "wh": {"$addToSet": "$warehouse_id"}}},
            {"$match": {"wh.1": {"$exists": True}}}, {"$limit": 1}]
    hit = list(DB.inventory_balances.aggregate(pipe))
    if not hit:
        pytest.skip("tidak ada produk ber-saldo di dua gudang")
    pid = hit[0]["_id"]
    _backorder_so(pid, [(7.5, "")])
    board = requests.get(f"{BASE}/stock/buckets", params={"product_id": pid, "owner_entity_id": ENT}, headers=ADMIN, timeout=60)
    assert board.status_code == 200, board.text
    row = next(r for r in board.json() if r["product_id"] == pid)
    detail = requests.get(f"{BASE}/stock/atp", params={"product_id": pid, "owner_entity_id": ENT}, headers=ADMIN, timeout=60).json()
    assert round(row["totals"]["atp_qty"], 2) == round(detail["atp_horizon"], 2)
    # backorder tanpa gudang tidak dikurangkan di baris gudang
    assert sum(float(w.get("pending_demand_qty") or 0) for w in row.get("warehouses", [])) <= round(row["totals"]["pending_demand_qty"], 2)


# ── Saldo rekening vs ringkasan kas ──────────────────────────────────────────
def _acc(entity, cash_type):
    aid = f"acc_TEST_LJ_{T}_{len(ACCS)}"
    DB.bank_accounts.insert_one({"id": aid, "entity_id": entity, "name": f"TEST {aid}", "cash_type": cash_type,
                                 "account_type": "cash" if cash_type == "kas_kecil" else "bank", "status": "active",
                                 "opening_balance": 0})
    ACCS.append(aid)
    return aid


def _txn(entity, cash_type, amount, account_id=""):
    tid = f"cash_TEST_LJ_{T}_{len(TXNS)}"
    DB.cash_transactions.insert_one({"id": tid, "entity_id": entity, "cash_type": cash_type, "direction": "in",
                                     "amount": amount, "account_id": account_id, "status": "posted",
                                     "txn_date": "2026-10-25", "created_at": "2026-10-25T01:00:00+00:00"})
    TXNS.append(tid)
    return tid


def test_unlinked_cash_follows_sole_account_of_cash_type():
    from services import bank_service as bs
    ent = f"ent_TEST_LJ_{T}"
    a1 = _acc(ent, "kas_kecil")
    t_free = _txn(ent, "kas_kecil", 125000.0)
    _txn(ent, "kas_besar", 999.0)   # jenis kas lain tidak ikut
    assert run(bs.sole_account_id(ent, "kas_kecil")) == a1
    ids = {t["id"] for t in run(bs._txns_for(a1))}
    assert t_free in ids and len(ids) == 1
    # rekening kedua jenis kas sama → tidak ada rekening tunggal, transaksi tanpa rekening tidak ditebak
    a2 = _acc(ent, "kas_kecil")
    assert run(bs.sole_account_id(ent, "kas_kecil")) == ""
    assert t_free not in {t["id"] for t in run(bs._txns_for(a1))}
    assert not run(bs._txns_for(a2))


# ── Profitabilitas per satuan ────────────────────────────────────────────────
def test_profitability_qty_by_unit_never_mixes_units():
    r = requests.get(f"{BASE}/finance/profitability", params={"entity_id": ENT}, headers=ADMIN, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    dims = [v for v in d.values() if isinstance(v, list) and v and isinstance(v[0], dict) and "qty" in v[0]]
    assert dims, "tidak ada dimensi berisi qty"
    for rows in dims:
        for row in rows:
            assert "qty_by_unit" in row
            assert abs(sum(row["qty_by_unit"].values()) - float(row["qty"])) < 0.05
    assert "qty_by_unit" in d["totals"]


# ── Beranda admin ────────────────────────────────────────────────────────────
def test_admin_home_month_not_below_today():
    r = requests.get(f"{BASE}/home/admin", params={"entity_id": ENT}, headers=ADMIN, timeout=120)
    assert r.status_code == 200, r.text
    s = r.json()["sales"]
    assert s["mtd"] + 0.01 >= s["today"], s


# ── KPI desainer ─────────────────────────────────────────────────────────────
def test_designer_kpi_excludes_technical_accounts():
    from services.rnd_kpi_service import TECH_ACTORS
    r = requests.get(f"{BASE}/rnd/reports/designer-kpi", params={"period": "all"}, headers=ADMIN, timeout=120)
    assert r.status_code == 200, r.text
    names = {" ".join(str(i["designer"]).lower().split()) for i in r.json()["items"]}
    assert not names & TECH_ACTORS
    t = requests.get(f"{BASE}/rnd/reports/designer-kpi/trend", headers=ADMIN, timeout=120)
    assert t.status_code == 200, t.text
    assert not {" ".join(str(n).lower().split()) for n in t.json()["designers"]} & TECH_ACTORS


# ── PDF: status berlabel ─────────────────────────────────────────────────────
def test_pdf_status_labels():
    from services.pdf_engine import _label_statuses, status_label
    assert status_label("waiting_stock") == "Menunggu stok"
    assert status_label("unpaid", payment=True) == "Belum dibayar"
    assert status_label("settled_by_return") == "Lunas via retur"
    assert status_label("some_new_code") == "Some new code"
    assert status_label("Lunas") == "Lunas"
    doc = {"title": "Pesanan Pembelian", "status": "pending",
           "meta": [{"label": "Status Bayar", "value": "pending"}, {"label": "Dibuat oleh", "value": "system"}]}
    out = _label_statuses(doc)
    assert out["status"] == "Menunggu" and out["meta"][0]["value"] == "Belum dibayar"
    assert out["meta"][1]["value"] == "system" and doc["status"] == "pending"   # asli tidak diubah


def test_pdf_preview_has_no_raw_status_code():
    so = DB.sales_orders.find_one({"entity_id": ENT, "status": {"$in": ["waiting_stock", "confirmed", "approved"]}},
                                  {"_id": 0, "id": 1, "status": 1})
    if not so:
        pytest.skip("tidak ada SO untuk pratinjau")
    r = requests.post(f"{BASE}/pdf/preview", json={"doc_type": "sales_order", "source_id": so["id"], "entity_id": ENT},
                      headers=ADMIN, timeout=120)
    if r.status_code == 404:
        pytest.skip(r.text)
    assert r.status_code == 200, r.text
    assert f'status-chip">{so["status"]}<' not in r.text
    assert "/jejak-dokumen/" not in r.text   # petunjuk di kertas tanpa URL ber-id internal (QR = data URI base64)


# ── Pelacak SO meja Admin Sample ─────────────────────────────────────────────
def test_sample_desk_tracker_lists_sample_orders_only():
    from services.so_tracker_service import sample_next_step
    assert sample_next_step({"status": "waiting_approval"})["roles"] == ["sample_admin", "finance"]
    assert sample_next_step({"status": "approved"})["roles"] == ["sample_admin"]
    assert sample_next_step({"status": "approved", "sample_payment_status": "reapproval_required"})["action"] == "Setujui Bayar"
    sid = f"so_TEST_LJ_{T}_smp"
    DB.sales_orders.insert_one({"id": sid, "number": f"SMP-TLJ-{T}", "entity_id": ENT, "status": "approved", "is_sample": True,
                                "customer_name": "TEST sample", "items": [], "created_at": "2026-10-25T01:00:00+00:00"})
    SOS.append(sid)
    r = requests.get(f"{BASE}/desks/so-tracker", params={"desk": "sample_admin", "entity_id": ENT}, headers=ADMIN, timeout=60)
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    mine = [x for x in rows if x["id"] == sid]
    assert mine and mine[0]["owner_roles"] == ["sample_admin"]
    ids = [x["id"] for x in rows]
    assert DB.sales_orders.count_documents({"id": {"$in": ids}, "is_sample": {"$ne": True}}) == 0
    reg = requests.get(f"{BASE}/desks/so-tracker", params={"desk": "sales_admin", "entity_id": ENT}, headers=ADMIN, timeout=60).json()
    assert sid not in {x["id"] for x in reg["rows"]}
