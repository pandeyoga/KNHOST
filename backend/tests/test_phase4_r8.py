"""Fase 4 · R8 (26 Okt 2026) — sisa backend SO & QC. Uji tingkat layanan, TANPA HTTP.

* Label status SO (keputusan pemilik #2) — `menunggu_stok` ("Menunggu stok (backorder)") HANYA status `waiting_stock`;
  SO tahap lain yang masih bersisa kurang stok = `sebagian_menunggu_stok`. `sub_status` tersimpan lama dibaca ulang.
* SO MATI — `so_approvals.closed_order_message` (dasar 409 `SO_CLOSED` di `decide` & `approve`), `dead_order_patch`;
  `so_transition` ke `cancelled` & `expire_old_reservations` menutup entri `pending_approvals` yang masih menunggu,
  dokumen rinciannya (harga khusus, override kredit), dan `has_backorder`.
* QC Hub — hitungan & saringan "Barang DITAHAN" = antrean `inspection_hold` (baris yang sudah DITOLAK MD Quality,
  SPK draf/ditutup tidak dihitung).

Jalankan (DB uji, data bertanda TEST_R8 dihapus lagi):
  cd /app/backend && DB_NAME=kn_test_trial python -m pytest tests/test_phase4_r8.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid
from pathlib import Path

import pytest
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import approval_backlog_service as abl  # noqa: E402
from services import inspection_service as ins  # noqa: E402
from services import inventory_service  # noqa: E402
from services import so_approvals  # noqa: E402
from services.sales_order_helpers import norm_backorder, so_transition  # noqa: E402
from services.so_status import SUBSTATUS_LABELS, derive_stage_substatus, read_sub_status  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
ENT = f"ent_TEST_R8_{TAG}"
T0 = "2026-10-20T00:00:00+00:00"
BACKEND = Path(__file__).resolve().parents[1]
COLLS = ("sales_orders", "price_approvals", "credit_overrides", "inspections")


def _pa(pid, typ, status, ref=None):
    return {"id": pid, "type": typ, "status": status, "required_role": "manager", "ref_id": ref}


@pytest.fixture(scope="module", autouse=True)
def seed():
    d = {"entity_id": ENT, "created_at": T0, "updated_at": T0}
    DB.sales_orders.insert_many([
        # dibatalkan lewat so_transition
        {**d, "id": f"so_R8_{TAG}_cx", "number": f"R8-{TAG}-CX", "status": "waiting_approval",
         "has_backorder": True, "backorders": [{"product_id": "p1", "backorder_qty": 4, "status": "waiting_stock"}],
         "approval_required": True, "required_approval_role": "manager",
         "pending_approvals": [_pa("pa_k", "kredit", "pending", f"cro_R8_{TAG}"),
                               _pa("pa_sp", "special_price", "pending", f"pra_R8_{TAG}"),
                               _pa("pa_ok", "nilai", "approved"), _pa("pa_rj", "special_price", "rejected")]},
        # transisi hidup — tidak boleh menyentuh entri & penanda
        {**d, "id": f"so_R8_{TAG}_live", "number": f"R8-{TAG}-LV", "status": "reserved", "has_backorder": True,
         "pending_approvals": [_pa("pa_n", "nilai", "pending")]},
        # kedaluwarsa lewat expire_old_reservations
        {**d, "id": f"so_R8_{TAG}_exp", "number": f"R8-{TAG}-EX", "status": "waiting_approval",
         "reservation_expires_at": "2026-10-01T00:00:00+00:00", "has_backorder": True,
         "pending_approvals": [_pa("pa_e", "pembayaran_sampel", "pending")]},
    ])
    DB.credit_overrides.insert_one({**d, "id": f"cro_R8_{TAG}", "order_id": f"so_R8_{TAG}_cx", "status": "pending",
                                    "amount": 1000, "customer_id": f"cust_R8_{TAG}"})
    DB.price_approvals.insert_one({**d, "id": f"pra_R8_{TAG}", "so_id": f"so_R8_{TAG}_cx", "status": "pending",
                                   "scope": "order"})
    DB.inspections.insert_many([
        {**d, "id": f"ins_R8_{TAG}_wait", "number": f"R8-{TAG}-INS1", "status": "done",
         "lines": [{"id": "l1", "hold": True}]},
        {**d, "id": f"ins_R8_{TAG}_rej", "number": f"R8-{TAG}-INS2", "status": "done",
         "lines": [{"id": "l2", "hold": True, "decision": "tolak", "md_quality_decision": {"action": "reject"}}]},
        {**d, "id": f"ins_R8_{TAG}_mix", "number": f"R8-{TAG}-INS3", "status": "in_progress",
         "lines": [{"id": "l3", "hold": True, "md_quality_decision": {"action": "reject"}},
                   {"id": "l4", "hold": True}]},
        {**d, "id": f"ins_R8_{TAG}_closed", "number": f"R8-{TAG}-INS4", "status": "closed",
         "lines": [{"id": "l5", "hold": True}]},
        {**d, "id": f"ins_R8_{TAG}_rel", "number": f"R8-{TAG}-INS5", "status": "done",
         "lines": [{"id": "l6", "hold": False, "md_quality_decision": {"action": "release"}}]},
    ])
    yield
    for c in COLLS:
        DB[c].delete_many({"entity_id": ENT})
    DB.audit_logs.delete_many({"entity_id": {"$regex": f"^so_R8_{TAG}"}})


# ─── 1 · Label status SO ─────────────────────────────────────────────────────────────────────────────────────────
def test_label_backorder_hanya_waiting_stock():
    assert derive_stage_substatus({"status": "waiting_stock"}) == ("Reserved", ["menunggu_stok"])
    assert derive_stage_substatus({"status": "approved", "has_backorder": True}) == ("Approved", ["sebagian_menunggu_stok"])
    assert derive_stage_substatus({"status": "confirmed", "has_backorder": True})[1] == ["siap_pick", "sebagian_menunggu_stok"]
    assert derive_stage_substatus({"status": "partially_shipped", "backorders": [{"backorder_qty": 3}]})[1] == \
        ["sebagian_dikirim", "sebagian_menunggu_stok"]
    assert derive_stage_substatus({"status": "cancelled", "has_backorder": True}) == ("Cancelled", ["dibatalkan"])
    assert SUBSTATUS_LABELS["menunggu_stok"] == "Menunggu stok (backorder)"
    assert SUBSTATUS_LABELS["sebagian_menunggu_stok"] == "Sebagian menunggu stok"


def test_sub_status_tersimpan_lama_dibaca_ulang():
    old = {"status": "partially_shipped", "stage": "Shipped", "sub_status": ["sebagian_dikirim", "menunggu_stok"]}
    assert read_sub_status(old) == ["sebagian_dikirim", "sebagian_menunggu_stok"]
    assert read_sub_status({"status": "waiting_stock", "sub_status": ["menunggu_stok"]}) == ["menunggu_stok"]
    assert read_sub_status({"status": "confirmed", "sub_status": ["siap_pick", "menunggu_stok", "sebagian_menunggu_stok"]}) \
        == ["siap_pick", "sebagian_menunggu_stok"]
    assert norm_backorder(dict(old))["sub_status"] == ["sebagian_dikirim", "sebagian_menunggu_stok"]


# ─── 2 · SO mati ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_pesan_409_so_mati():
    assert set(so_approvals.dead_statuses()) == set(abl.SO_DEAD_STATUSES)
    for st in ("cancelled", "expired", "rejected", "void", "done"):
        msg = so_approvals.closed_order_message({"status": st, "number": "X/SO-1"})
        assert msg.startswith("Pesanan X/SO-1 sudah ") and "tidak bisa diputuskan" in msg, st
    assert "kedaluwarsa" in so_approvals.closed_order_message({"status": "expired", "number": "X"})
    for st in ("reserved", "waiting_approval", "waiting_stock", "approved", "confirmed"):
        assert so_approvals.closed_order_message({"status": st}) == "", st


def test_patch_so_mati_hanya_entri_menunggu():
    order = {"status": "waiting_approval", "has_backorder": True,
             "pending_approvals": [_pa("a", "kredit", "pending"), _pa("b", "nilai", "approved"),
                                   _pa("c", "special_price", "rejected")]}
    patch, closed = so_approvals.dead_order_patch(order, "cancelled", "Pesanan dibatalkan: uji", "Penguji")
    assert [p["id"] for p in closed] == ["a"]
    st = {p["id"]: p["status"] for p in patch["pending_approvals"]}
    assert st == {"a": "cancelled", "b": "approved", "c": "rejected"}           # riwayat keputusan utuh
    a = patch["pending_approvals"][0]
    assert a["previous_status"] == "pending" and a["cancel_reason"] == "Pesanan dibatalkan: uji" and a["cancelled_by"] == "Penguji"
    assert patch["has_backorder"] is False and patch["approval_required"] is False
    assert order["pending_approvals"][0]["status"] == "pending"                 # dokumen masukan tidak diubah di tempat
    assert so_approvals.dead_order_patch(order, "approved") == ({}, [])
    assert so_approvals.dead_order_patch(order, "done") == ({}, [])
    p2, c2 = so_approvals.dead_order_patch({"status": "reserved"}, "expired")
    assert p2 == {"has_backorder": False} and c2 == []


def test_batal_lewat_so_transition_menutup_entri_dan_penanda():
    so_id = f"so_R8_{TAG}_cx"
    out = run(so_transition(so_id, ["waiting_approval"], "cancelled", "Penguji R8", "order_cancelled",
                            {"cancel_reason": "uji R8 batal"}))
    assert out["status"] == "cancelled" and out["stage"] == "Cancelled" and out["has_backorder"] is False
    st = {p["id"]: p["status"] for p in out["pending_approvals"]}
    assert st == {"pa_k": "cancelled", "pa_sp": "cancelled", "pa_ok": "approved", "pa_rj": "rejected"}
    assert all(p["cancel_reason"] == "Pesanan dibatalkan: uji R8 batal" for p in out["pending_approvals"]
               if p["status"] == "cancelled")
    assert out["backorders"]                                                     # riwayat baris pendingan tetap ada
    assert DB.credit_overrides.find_one({"id": f"cro_R8_{TAG}"})["status"] == "cancelled"
    assert DB.price_approvals.find_one({"id": f"pra_R8_{TAG}"})["status"] == "cancelled"


def test_transisi_hidup_tidak_menyentuh_entri():
    so_id = f"so_R8_{TAG}_live"
    out = run(so_transition(so_id, ["reserved"], "waiting_approval", "Penguji R8", "order_submitted", {}))
    assert out["has_backorder"] is True
    assert [p["status"] for p in out["pending_approvals"]] == ["pending"]


class _ScopedColl:
    """Proksi koleksi: `find` dibatasi badan usaha uji supaya `expire_old_reservations` tidak menyentuh data acuan."""

    def __init__(self, coll):
        self._c = coll

    def find(self, query, *a, **k):
        return self._c.find({**query, "entity_id": ENT}, *a, **k)

    def __getattr__(self, name):
        return getattr(self._c, name)


class _ScopedDb:
    def __init__(self, database):
        self._d = database

    def __getattr__(self, name):
        coll = getattr(self._d, name)
        return _ScopedColl(coll) if name == "sales_orders" else coll


def test_kedaluwarsa_menutup_entri(monkeypatch):
    monkeypatch.setattr(inventory_service, "db", _ScopedDb(inventory_service.db))
    assert run(inventory_service.expire_old_reservations()) == 1
    so = DB.sales_orders.find_one({"id": f"so_R8_{TAG}_exp"})
    assert so["status"] == "expired" and so["has_backorder"] is False and so["sub_status"] == ["kedaluwarsa"]
    e = so["pending_approvals"][0]
    assert e["status"] == "cancelled" and e["cancel_reason"] == "Reservasi pesanan kedaluwarsa" and e["cancelled_by"] == "system"


def test_router_menolak_keputusan_so_mati_dan_menyembunyikan_antrean():
    """Rute butuh restart untuk diuji lewat HTTP (`test_phase4_r8_http.py`); di sini dipastikan pagarnya ada & berurutan."""
    src = (BACKEND / "routers" / "so_approvals.py").read_text(encoding="utf-8")
    dec = src[src.index("async def decide_approval"):src.index("async def _apply_decision")]
    assert dec.index("closed_order_message") < dec.index("decision not in")       # sebelum apa pun ditulis
    assert '"SO_CLOSED"' in dec and "status_code=409" in dec
    q = src[src.index('@router.get("/approvals/queue")'):]
    assert "dead_statuses()" in q and '"$nin"' in q
    extra = (BACKEND / "routers" / "sales_orders_extra.py").read_text(encoding="utf-8")
    appr = extra[extra.index("async def approve_order"):extra.index("async def confirm_order")]
    assert appr.index("closed_order_message") < appr.index('p.update({"status": "approved"')


# ─── 3 · QC Hub — "Barang DITAHAN" = antrean `inspection_hold` ──────────────────────────────────────────────────
def test_qc_hub_ditahan_sama_dengan_antrean():
    scope = {"entity_id": ENT}
    st = run(ins.stats(scope))
    queue = {r["key"]: r["count"] for r in run(abl.backlog(ENT))["all_items"]}
    assert st["hold"] == 2 == queue["inspection_hold"]      # INS1 + INS3 (baris l4); INS2 ditolak, INS4 ditutup
    rows, total = run(ins.list_inspections(scope, hold_only=True))
    assert total == 2 and {r["number"] for r in rows} == {f"R8-{TAG}-INS1", f"R8-{TAG}-INS3"}
    # penyaring lain tetap berlaku (status & cari) — tidak saling menimpa kunci
    _r, t_done = run(ins.list_inspections(scope, status="done", hold_only=True))
    _r, t_closed = run(ins.list_inspections(scope, status="closed", hold_only=True))
    _r, t_q = run(ins.list_inspections(scope, q=f"R8-{TAG}-INS3", hold_only=True))
    assert (t_done, t_closed, t_q) == (1, 0, 1)
    assert ins.hold_waiting_query() == next(q[4] for q in abl.QUEUES if q[0] == "inspection_hold")
