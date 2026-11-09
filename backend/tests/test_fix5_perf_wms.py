"""FIX-5 (audit 9 Nov 2026 — B3a SCH-9, PREP-H §9, B3b LST-01/03, B1b UI-46/UI-51) — performa WMS.

Uji di sini GAGAL di kode sebelum FIX-5 dan LULUS sesudahnya (kecuali yang ditandai "penjaga", lulus di keduanya):
  A. index `id` unik-parsial (`uq_id`) di koleksi jalur WMS-RFID & stok; kueri `{id}` / `{id: {$in}}` memakai index;
     index lama `kn_gate_id_1` tidak tersisa (kunci kembar);
  B. terima transfer: saldo dibangun ulang PER KELOMPOK roll (dulu 2× per roll) & roll/produk dibaca sekali — hasil per
     baris & saldo akhir tetap benar (penjaga: id / nomor roll / EPC / ganda / asing);
  C. tiba PA per trip: pelanggaran tujuan dihitung sekali per (produk, grade) (dulu per roll); mutasi idempoten.
Kesetaraan penuh sebelum/sesudah (DB ternormalisasi) = `scripts/fix5_equivalence.py` (laporan FIX-5 §4).

Jalankan (kontainer backend, DB salinan data acuan, backend berjalan):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_fix5_perf_wms.py
"""
import os
import sys

import pytest
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
T = "TEST_FIX5"
WH_SRC, WH_DST, WH_TR, WH_ST = (f"wh_{T}_{k}" for k in ("src", "dst", "tr", "st"))
SITE = f"site_{T}"


def _purge():
    rx = {"$regex": f"_{T}_"}
    for c in ("inventory_rolls", "rfid_tags", "warehouse_transfers", "putaway_orders", "warehouses"):
        DB[c].delete_many({"id": rx})
    DB.inventory_movements.delete_many({"roll_id": rx})
    DB.inventory_balances.delete_many({"warehouse_id": rx})


@pytest.fixture(scope="module", autouse=True)
def bed():
    _purge()
    for wid, roles in ((WH_SRC, ["storage"]), (WH_DST, ["storage"]), (WH_TR, ["transit", "receiving"]),
                       (WH_ST, ["storage"])):
        DB.warehouses.insert_one({"id": wid, "name": f"Uji FIX5 {wid[-3:]}", "code": wid[-6:].upper(), "roles": roles,
                                  "site_id": SITE, "sharing_mode": "shared", "active": True,
                                  "gate_config": {"has_gate": False}})
    yield
    _purge()


def _products(n=2):
    rows = list(DB.products.find({"base_unit": "meter", "status": {"$ne": "inactive"}}, {"_id": 0, "id": 1})
                .sort("id", 1).limit(n))
    assert len(rows) == n
    return [r["id"] for r in rows]


def _rolls(prefix, n, wh, status, prods, **extra):
    rolls, tags = [], []
    for i in range(n):
        rid, tid = f"roll_{T}_{prefix}_{i}", f"tag_{T}_{prefix}_{i}"
        rolls.append({"id": rid, "roll_no": f"F5{prefix}{i:05d}", "product_id": prods[i % len(prods)], "warehouse_id": wh,
                      "owner_entity_id": ENT, "status": status, "length_remaining": 25.0, "length_initial": 25.0,
                      "unit": "meter", "grade": "A", "lot": f"L-{T}", "rfid_tag_id": tid, "bin_id": None,
                      "length_reserved": 0, "length_reservations": [],
                      "journey": {"stage": "tag_verified", "verified_tag_id": tid, "routing": "store"},
                      **{k: (v(i) if callable(v) else v) for k, v in extra.items()}})
        tags.append({"id": tid, "epc": f"E2F5{prefix.upper()}{i:018X}", "roll_id": rid, "status": "active",
                     "warehouse_id": wh})
    DB.inventory_rolls.insert_many(rolls)
    DB.rfid_tags.insert_many(tags)
    return rolls, tags


# ── A. index `id` ─────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("coll", ["inventory_rolls", "inventory_movements", "rfid_tags", "putaway_orders",
                                  "warehouse_transfers", "shipments", "sales_orders", "wms_tasks", "inventory_lots",
                                  "products", "warehouses"])
def test_id_index_unique_partial_and_used(coll):
    run(__import__("indexes").ensure_id_indexes())   # idempoten (startup sudah memanggilnya)
    info = DB[coll].index_information()
    assert "uq_id" in info, f"{coll}: index uq_id tidak ada ({sorted(info)})"
    assert info["uq_id"].get("unique") and info["uq_id"].get("partialFilterExpression") == {"id": {"$gt": ""}}
    assert "kn_gate_id_1" not in info, f"{coll}: index kn_gate_id_1 (kunci kembar) masih ada"
    for flt in ({"id": "x_tidak_ada"}, {"id": {"$in": ["a_tidak_ada", "b_tidak_ada"]}}):
        plan = DB.command("explain", {"find": coll, "filter": flt}, verbosity="queryPlanner")["queryPlanner"]["winningPlan"]
        assert "uq_id" in str(plan) and "COLLSCAN" not in str(plan), f"{coll} {flt}: {plan}"


def test_roll_reference_fields_indexed():
    info = DB.inventory_rolls.index_information()
    for f in ("reserved_ref.id", "transfer_ref.id", "last_transfer.ref_id", "active_movement.id"):
        assert f"kn_ref_{f.replace('.', '_')}" in info, f
        plan = DB.command("explain", {"find": "inventory_rolls", "filter": {f: "x_tidak_ada"}},
                          verbosity="queryPlanner")["queryPlanner"]["winningPlan"]
        assert "COLLSCAN" not in str(plan), (f, plan)


# ── B. terima transfer ────────────────────────────────────────────────────────────────────────────────────
def _transfer(tid, rolls):
    items = {}
    for r in rolls:
        items.setdefault(r["product_id"], []).append({"roll_id": r["id"], "roll_no": r["roll_no"], "length": 25.0})
    DB.warehouse_transfers.insert_one({"id": tid, "code": f"TRF-{tid[-8:]}", "status": "dispatched",
                                       "transfer_kind": "warehouse", "source_warehouse_id": WH_SRC,
                                       "dest_warehouse_id": WH_DST, "owner_entity_id": ENT, "entity_id": ENT,
                                       "items": [{"product_id": p, "unit": "meter", "rolls": rs} for p, rs in items.items()]})


def test_transfer_receive_rebuilds_per_batch_and_balance_correct(monkeypatch):
    from schemas import TransferReceiveIn, TransferReceiveLine
    from services import transfer_receipt_service as trs
    from services.roll_service import rebuild_balance
    prods = _products(2)
    tid = f"trf_{T}_b"
    rolls, _ = _rolls("b", 300, WH_SRC, "in_transit_transfer", prods,
                      reserved_ref={"type": "wh_transfer", "id": tid}, transfer_prior_status="available")
    _transfer(tid, rolls)
    calls = []
    orig = trs.rebuild_balance

    async def counting(*a, **k):
        calls.append(a)
        return await orig(*a, **k)
    monkeypatch.setattr(trs, "rebuild_balance", counting)
    t = DB.warehouse_transfers.find_one({"id": tid}, {"_id": 0})
    body = TransferReceiveIn(lines=[TransferReceiveLine(roll_id=r["id"]) for r in rolls])
    res = run(trs.receive(t, body, {"id": "u_f5", "name": "Uji F5", "role": "warehouse"}))
    assert [r["result"] for r in res["results"]] == ["received"] * 300 and res["transfer_status"] == "completed"
    # 2 produk × 2 gudang = 4 segmen; per 100 roll + akhir → ≤ 4 × 4 = 16 (dulu 2 × 300 = 600)
    assert len(calls) <= 16, f"rebuild_balance dipanggil {len(calls)}× untuk 300 roll"
    # saldo tersimpan = hasil hitung ulang segar (tidak ada saldo basi)
    for p in prods:
        for w in (WH_SRC, WH_DST):
            stored = DB.inventory_balances.find_one({"product_id": p, "warehouse_id": w, "owner_entity_id": ENT}, {"_id": 0})
            fresh = run(rebuild_balance(p, w, ENT))
            for k in ("available_qty", "in_transit_transfer_qty", "on_hand_qty", "roll_count", "on_hand_roll_count"):
                assert stored[k] == fresh[k], (p, w, k, stored[k], fresh[k])
    assert DB.inventory_movements.count_documents({"roll_id": {"$in": [r["id"] for r in rolls]},
                                                   "movement_type": "transfer_in"}) == 300


def test_transfer_receive_line_resolution_guard():
    """Penjaga (lulus sebelum & sesudah): id / nomor roll / EPC / baris ganda / kode asing / roll lain."""
    from schemas import TransferReceiveIn, TransferReceiveLine
    from services import transfer_receipt_service as trs
    prods = _products(1)
    tid = f"trf_{T}_g"
    rolls, tags = _rolls("g", 6, WH_SRC, "in_transit_transfer", prods,
                         reserved_ref={"type": "wh_transfer", "id": tid}, transfer_prior_status="available")
    _transfer(tid, rolls)
    lines = [TransferReceiveLine(roll_id=rolls[0]["id"]), TransferReceiveLine(code=rolls[1]["roll_no"]),
             TransferReceiveLine(code=tags[2]["epc"]), TransferReceiveLine(roll_id=rolls[0]["id"]),
             TransferReceiveLine(code="F5-TIDAK-ADA"), TransferReceiveLine(code=rolls[3]["roll_no"]),
             TransferReceiveLine(roll_id=rolls[4]["id"], outcome="damaged", note="Sobek panjang di tepi")]
    t = DB.warehouse_transfers.find_one({"id": tid}, {"_id": 0})
    res = run(trs.receive(t, TransferReceiveIn(lines=lines), {"id": "u_f5", "name": "Uji F5", "role": "warehouse"}))
    got = [(r["result"], r.get("roll_id")) for r in res["results"]]
    assert got == [("received", rolls[0]["id"]), ("received", rolls[1]["id"]), ("received", rolls[2]["id"]),
                   ("already", rolls[0]["id"]), ("wrong_roll", None), ("received", rolls[3]["id"]),
                   ("damaged", rolls[4]["id"])], got
    assert res["results"][3]["message"].startswith("Sudah diterima sebelumnya")
    assert res["transfer_status"] == "partially_received"
    # panggilan kedua: roll yang sudah diterima = "already", sisa diterima → selesai
    t = DB.warehouse_transfers.find_one({"id": tid}, {"_id": 0})
    res2 = run(trs.receive(t, TransferReceiveIn(lines=[TransferReceiveLine(roll_id=rolls[5]["id"]),
                                                       TransferReceiveLine(roll_id=rolls[1]["id"])]),
                           {"id": "u_f5", "name": "Uji F5", "role": "warehouse"}))
    assert [r["result"] for r in res2["results"]] == ["received", "already"] and res2["transfer_status"] == "completed"


# ── C. tiba PA per trip ──────────────────────────────────────────────────────────────────────────────────
def test_putaway_trip_checks_destination_once_per_product_grade(monkeypatch):
    from services import placement_rules as pr
    from services import putaway_arrival_service as arr
    prods = _products(2)
    pa_id = f"pa_{T}_c"
    rolls, tags = _rolls("c", 240, WH_TR, "in_transit_transfer", prods,
                         active_movement={"type": "putaway", "id": pa_id, "number": "PA-F5"})
    items = [{"roll_id": r["id"], "roll_no": r["roll_no"], "epc": t["epc"], "grade": "A", "product_id": r["product_id"],
              "lot": r["lot"], "qty": 25.0, "unit": "meter", "status": "pending"} for r, t in zip(rolls, tags)]
    DB.putaway_orders.insert_one({"id": pa_id, "pa_number": "PA-F5", "from_warehouse_id": WH_TR, "to_warehouse_id": WH_ST,
                                  "owner_entity_id": ENT, "items": items, "status": "in_transit", "purpose": "storage",
                                  "btg_number": None, "arrival_trips": [], "dispatched_at": "2026-11-09T00:00:00+00:00"})
    calls = []
    orig = pr.warehouse_violations

    async def counting(*a, **k):
        calls.append(1)
        return await orig(*a, **k)
    monkeypatch.setattr(pr, "warehouse_violations", counting)
    out = run(arr.confirm_arrival_trip(pa_id, [t["epc"] for t in tags], {"type": "gate", "passage_id": f"pas_{T}_c"},
                                       {"name": "Uji F5"}))
    assert out["status"] == "completed" and out["arrived_count"] == 240
    assert len(calls) <= 2, f"pelanggaran tujuan dihitung {len(calls)}× untuk 240 roll (2 produk)"
    mv = DB.inventory_movements.count_documents({"reference_id": pa_id})
    assert mv == 480
    # trip yang sama diulang → duplikat idempoten, mutasi tidak bertambah
    again = run(arr.confirm_arrival_trip(pa_id, [t["epc"] for t in tags], {"type": "gate", "passage_id": f"pas_{T}_c"},
                                         {"name": "Uji F5"}))
    assert again["duplicate_trip"] is True
    assert DB.inventory_movements.count_documents({"reference_id": pa_id}) == 480
    assert DB.inventory_rolls.count_documents({"id": {"$in": [r["id"] for r in rolls]}, "warehouse_id": WH_ST}) == 240


# ── D. daftar: batas `limit` & jumlah sungguhan (B3b LST-01/03) ──────────────────────────────────────────
import re  # noqa: E402

import requests  # noqa: E402

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"


def _pw():
    if os.environ.get("KN_DEMO_PASS"):
        return os.environ["KN_DEMO_PASS"]
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    m = re.search(r"Login demo:.*?/\s*`([^`]+)`", open(os.path.join(root, "AGENTS.md"), encoding="utf-8").read())
    return m.group(1)


@pytest.fixture(scope="module")
def admin():
    try:
        r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": _pw()}, timeout=30)
    except requests.RequestException:
        pytest.skip("backend tidak berjalan")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.mark.parametrize("path", ["/goods-receipts", "/putaway-orders", "/rfid/reads", "/rfid/passages", "/rfid/incidents",
                                  "/lots", "/makloon-orders/claims", "/interco/transactions", "/interco/settlements",
                                  "/interco/returns", "/transfers", "/rfid/tags"])
def test_list_limit_negative_and_huge_are_bounded(admin, path):
    """`limit=-1` dulu → `to_list(-1)` → 500; `limit=100000` diterima apa adanya."""
    for lim in (-1, 100000, "abc"):
        r = requests.get(f"{BASE}{path}", params={"limit": lim}, headers=admin, timeout=60)
        assert r.status_code in (200, 422), (path, lim, r.status_code, r.text[:200])
        if lim == -1:
            assert r.status_code == 200, (path, r.text[:200])


def test_goods_receipts_and_transfers_report_real_total(admin):
    for path in ("/goods-receipts", "/transfers"):
        r = requests.get(f"{BASE}{path}", params={"limit": 1}, headers=admin, timeout=60)
        assert r.status_code == 200
        assert "X-Total-Count" in r.headers and "X-Truncated" in r.headers, (path, dict(r.headers))
        total = int(r.headers["X-Total-Count"])
        assert len(r.json()) == min(1, total)
        assert r.headers["X-Truncated"] == ("1" if total > 1 else "0")
        if total > 1:   # halaman berikutnya lewat `skip`
            r2 = requests.get(f"{BASE}{path}", params={"limit": 1, "skip": 1}, headers=admin, timeout=60)
            assert r2.json()[0]["id"] != r.json()[0]["id"]


def test_putaway_orders_tags_incidents_meta(admin):
    for path, key in (("/putaway-orders", "orders"), ("/rfid/tags", "tags"), ("/rfid/incidents", "incidents")):
        d = requests.get(f"{BASE}{path}", params={"limit": 1}, headers=admin, timeout=60).json()
        assert {"total", "truncated", "skip", "limit"} <= set(d), (path, sorted(d))
        assert d["truncated"] == (d["total"] > len(d[key])), (path, d["total"], len(d[key]))
    live = requests.get(f"{BASE}/putaway-orders", params={"status": "live"}, headers=admin, timeout=60).json()
    assert all(o["status"] in ("draft", "open", "in_transit", "partially_received") for o in live["orders"])


def test_unpaged_rolls_and_tasks_say_when_truncated(admin):
    r = requests.get(f"{BASE}/inventory/rolls", params={"limit": 2}, headers=admin, timeout=120)
    assert r.status_code == 200 and len(r.json()) <= 2
    assert int(r.headers["X-Total-Count"]) >= len(r.json()) and r.headers["X-Truncated"] in ("0", "1")
    t = requests.get(f"{BASE}/wms/tasks", headers=admin, timeout=120)
    assert t.status_code == 200 and "X-Total-Count" in t.headers and "X-Truncated" in t.headers


# ── E. penampil roll berkelompok (B4 §3.8) ─────────────────────────────────────────────────────────────
PHYS = ("available", "reserved", "committed", "picked", "packed", "hold", "wip", "quarantine", "blocked", "damaged")


def test_roll_groups_product_lot_location_consistent(admin):
    g = requests.get(f"{BASE}/inventory/roll-groups", params={"level": "product", "page_size": 5}, headers=admin, timeout=120)
    assert g.status_code == 200, g.text
    d = g.json()
    assert d["level"] == "product" and d["scope"] == "physical" and d["total"] >= len(d["groups"])
    assert d["groups"], "data acuan punya roll fisik"
    p = d["groups"][0]
    assert {"product_id", "sku", "product_name", "roll_count", "total_length", "lot_count", "status_counts"} <= set(p)
    assert sum(p["status_counts"].values()) == p["roll_count"]
    lots = requests.get(f"{BASE}/inventory/roll-groups", params={"level": "lot", "product_id": p["product_id"],
                                                                  "page_size": 200}, headers=admin, timeout=120).json()
    assert sum(x["roll_count"] for x in lots["groups"]) == p["roll_count"] or lots["has_more"]
    lt = lots["groups"][0]
    locs = requests.get(f"{BASE}/inventory/roll-groups", params={"level": "location", "product_id": p["product_id"],
                                                                  "lot": lt["lot"], "page_size": 200}, headers=admin,
                        timeout=120).json()
    assert sum(x["roll_count"] for x in locs["groups"]) == lt["roll_count"] or locs["has_more"]
    loc = locs["groups"][0]
    params = {"page": 1, "page_size": 200, "product_id": p["product_id"], "warehouse_id": loc["warehouse_id"],
              "bin_id": loc["bin_id"], "lot": lt["lot"] or "__none__", "scope": "physical"}
    rolls = requests.get(f"{BASE}/inventory/rolls", params=params, headers=admin, timeout=120).json()
    assert all((r.get("lot") or "") == lt["lot"] for r in rolls["items"])
    assert all(float(r.get("length_remaining") or 0) > 0 and r["status"] in PHYS for r in rolls["items"])
    assert rolls["total"] == loc["roll_count"]
    assert requests.get(f"{BASE}/inventory/roll-groups", params={"level": "lot"}, headers=admin, timeout=30).status_code == 400
