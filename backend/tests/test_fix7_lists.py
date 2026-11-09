"""FIX-7 (audit 9 Nov 2026 — B3b LST-01/02/03/07/09) — daftar WMS-RFID & harian tanpa halaman server yang tersisa.

Uji di sini GAGAL di kode sebelum FIX-7 dan LULUS sesudahnya (kecuali yang ditandai "penjaga", lulus di keduanya):
  A. Meja Cutting (LST-02, P1): tugas sample BARU tetap tampil walau sudah ada > 500 tugas sample selesai;
  B. daftar berbatas memberi jumlah SUNGGUHAN (`X-Total-Count`/`X-Truncated` atau `total/truncated` di badan) + `skip`
     menuju halaman berikutnya + `limit` dijepit (negatif/raksasa → bawaan/batas);
  C. tugas potong disaring di server (`task_subtype`, `exclude_status`); cari pengiriman di server (dulu sesudah
     dipotong 1.000); riwayat pengiriman tidak lagi berhenti di 3.000 dokumen;
  D. daftar sesi opname tanpa `items`/`roll_count` utuh (LST-07) tetapi membawa jumlahnya; saringan `status`;
  E. cari perbaikan dengan karakter khusus tidak lagi galat 500 (regex di-escape).
Penjaga kesetaraan: halaman pertama `/outbound/tasks` = 200 tugas terbaru (aturan lama); riwayat pengiriman = rumus
lama (saring tanggal `_when`, urut, statistik) pada data yang sama.

Jalankan (kontainer backend, DB salinan data acuan, backend berjalan):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_fix7_lists.py
"""
import os
import re
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
T = "fix7l"


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


def _iso(dt):
    return dt.isoformat()


def _purge():
    rx = {"$regex": f"^{T}_"}
    DB.wms_tasks.delete_many({"id": rx})
    DB.logistics_deliveries.delete_many({"id": rx})
    DB.repair_orders.delete_many({"id": rx})
    DB.cycle_count_sessions.delete_many({"id": rx})


@pytest.fixture(scope="module", autouse=True)
def bed():
    _purge()
    yield
    _purge()


def _get(admin, path, **params):
    r = requests.get(f"{BASE}{path}", params=params, headers=admin, timeout=120)
    assert r.status_code == 200, (path, params, r.status_code, r.text[:300])
    return r


def _assert_header_window(r, shown):
    assert "X-Total-Count" in r.headers and "X-Truncated" in r.headers, dict(r.headers)
    total = int(r.headers["X-Total-Count"])
    assert r.headers["X-Truncated"] == ("1" if total > shown else "0"), (total, shown)
    return total


# ── A. Meja Cutting (LST-02, P1) ──────────────────────────────────────────────────────────────────────────
def test_cutting_desk_shows_new_task_after_500_closed_samples(admin):
    sample = DB.wms_tasks.find_one({"task_subtype": "sample_cut"}, {"_id": 0}) or {}
    wh = sample.get("warehouse_id") or (DB.warehouses.find_one({"active": {"$ne": False}}, {"_id": 0, "id": 1}) or {})["id"]
    ent = sample.get("entity_id") or "ent_ksc"
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    DB.wms_tasks.insert_many([{
        "id": f"{T}_cut_done_{i}", "flow_type": "outbound", "source_type": "sales_order", "task_subtype": "sample_cut",
        "status": "dispatched", "entity_id": ent, "warehouse_id": wh, "order_id": f"{T}_so_x", "quantity": 1,
        "unit": "meter", "created_at": _iso(old + timedelta(minutes=i))} for i in range(505)])
    new_id = f"{T}_cut_new"
    DB.wms_tasks.insert_one({"id": new_id, "flow_type": "outbound", "source_type": "sales_order",
                             "task_subtype": "sample_cut", "status": "created", "entity_id": ent, "warehouse_id": wh,
                             "order_id": f"{T}_so_new", "order_number": "SO-FIX7-NEW", "quantity": 1, "unit": "meter",
                             "created_at": _iso(datetime.now(timezone.utc))})
    d = _get(admin, "/cutting/desk").json()
    ids = {r["task_id"] for q in d["queues"] for r in q["rows"]}
    assert new_id in ids, "tugas potong BARU hilang dari Meja Cutting (LST-02)"
    assert not any(i.startswith(f"{T}_cut_done_") for i in ids)
    assert d["total_open"] >= 1 and d["truncated"] is (d["total_open"] > d["shown"])


# ── B/C. tugas barang keluar & potong ─────────────────────────────────────────────────────────────────────
def test_outbound_tasks_real_total_skip_and_server_filters(admin):
    r = _get(admin, "/outbound/tasks", limit=1)
    total = _assert_header_window(r, len(r.json()))
    if total > 1:
        r2 = _get(admin, "/outbound/tasks", limit=1, skip=1)
        assert r2.json()[0]["id"] != r.json()[0]["id"]
    cut = _get(admin, "/outbound/tasks", task_subtype="sample_cut", exclude_status="dispatched,cancelled", limit=500)
    rows = cut.json()
    assert all(t.get("task_subtype") == "sample_cut" and t["status"] not in ("dispatched", "cancelled") for t in rows)
    assert any(t["id"] == f"{T}_cut_new" for t in rows), "tugas potong terbuka tidak disaring di server"
    _assert_header_window(cut, len(rows))


def test_outbound_first_page_equals_old_rule(admin):
    """Penjaga — halaman pertama tanpa parameter = 200 tugas terbaru (status ≠ scheduled), sama dengan aturan lama."""
    rows = _get(admin, "/outbound/tasks").json()
    assert len(rows) <= 200
    times = [t.get("created_at") or "" for t in rows]
    assert times == sorted(times, reverse=True)
    assert all(t.get("status") != "scheduled" for t in rows)


@pytest.mark.parametrize("path", ["/outbound/tasks", "/inbound/tasks", "/sample-orders", "/makloon-orders",
                                  "/cycle-count/sessions", "/registration/sessions", "/logistics/deliveries"])
def test_array_lists_carry_real_total_and_clamp_limit(admin, path):
    r = _get(admin, path, limit=1)
    total = _assert_header_window(r, len(r.json()))
    assert len(r.json()) == min(1, total)
    for lim in (-1, 100000, "abc"):
        rr = requests.get(f"{BASE}{path}", params={"limit": lim}, headers=admin, timeout=120)
        assert rr.status_code in (200, 422), (path, lim, rr.status_code)
        if lim == -1:
            assert rr.status_code == 200 and int(rr.headers["X-Total-Count"]) == total


@pytest.mark.parametrize("path,key", [("/rfid/untagged-rolls", "rolls"), ("/rfid/devices", "devices"),
                                      ("/rfid/locations", "items"), ("/rfid/print-jobs", "jobs"),
                                      ("/rfid/cycle-counts", "counts"), ("/repair-orders", "items")])
def test_object_lists_carry_meta(admin, path, key):
    d = _get(admin, path, limit=1).json()
    assert {"total", "truncated", "skip", "limit"} <= set(d), (path, sorted(d))
    assert d["truncated"] == (d["total"] > len(d[key])), (path, d["total"], len(d[key]))
    if d["total"] > 1:
        d2 = _get(admin, path, limit=1, skip=1).json()
        assert len(d2[key]) == 1 and d2[key][0] != d[key][0], path


# ── C. pengiriman: cari di server & riwayat > 3.000 ───────────────────────────────────────────────────────
def _ksc_delivery_scope():
    d = DB.logistics_deliveries.find_one({"entity_id": "ent_ksc"}, {"_id": 0}) or {}
    return {k: d.get(k) for k in ("entity_id", "warehouse_id", "shipment_ids", "order_id") if d.get(k) is not None}


def test_delivery_search_on_server_beyond_old_cap(admin):
    base = _ksc_delivery_scope() or {"entity_id": "ent_ksc"}
    now = datetime.now(timezone.utc)
    DB.logistics_deliveries.insert_one({**base, "id": f"{T}_dl_needle", "number": "LG-FIX7-NEEDLE(1)",
                                        "status": "prepared", "mode": "expedition", "customer_name": "Uji",
                                        "shipment_nos": ["SJ-FIX7-ZZ9"], "created_at": _iso(now - timedelta(days=3000)),
                                        "updated_at": _iso(now - timedelta(days=3000))})
    DB.logistics_deliveries.insert_many([{**base, "id": f"{T}_dl_fill_{i}", "number": f"LG-FIX7-F{i:05d}",
                                          "status": "prepared", "mode": "expedition", "customer_name": "Uji",
                                          "created_at": _iso(now - timedelta(minutes=i)), "updated_at": _iso(now)}
                                         for i in range(1005)])
    r = _get(admin, "/logistics/deliveries", q="sj-fix7-zz9")
    assert [x["id"] for x in r.json()] == [f"{T}_dl_needle"], "cari pengiriman lama (di luar 1.000 terbaru) gagal"
    r = _get(admin, "/logistics/deliveries", q="NEEDLE(1")   # karakter khusus dicari apa adanya
    assert [x["id"] for x in r.json()] == [f"{T}_dl_needle"]
    full = _get(admin, "/logistics/deliveries")
    assert len(full.json()) == 1000 and full.headers["X-Truncated"] == "1"
    assert int(full.headers["X-Total-Count"]) >= 1006


def _old_history(scope, date_from="", date_to="", mode="", status="", q="", page=1, size=25):
    """Rumus LAMA `logistics_service.history` (tanpa batas 3.000) — pembanding kesetaraan."""
    query = {**scope, "status": {"$in": [status] if status in ("delivered", "completed", "failed")
                                  else ["delivered", "completed", "failed"]}}
    if mode:
        query["mode"] = mode
    rows = list(DB.logistics_deliveries.find(query, {"_id": 0, "photos": 0, "timeline": 0, "positions": 0})
                .sort("updated_at", -1))

    def _when(r):
        return str(r.get("completed_at") or r.get("delivered_at") or r.get("updated_at") or "")[:10]
    if date_from:
        rows = [r for r in rows if _when(r) >= date_from]
    if date_to:
        rows = [r for r in rows if _when(r) <= date_to]
    if q:
        s = q.lower()
        rows = [r for r in rows if any(s in str(r.get(k, "")).lower() for k in
                ("number", "order_number", "customer_name", "tracking_no", "courier_name", "vehicle_plate", "driver_name"))
                or any(s in str(n).lower() for n in r.get("shipment_nos", []))]
    rows.sort(key=lambda r: str(r.get("completed_at") or r.get("delivered_at") or r.get("updated_at") or ""), reverse=True)
    start = (page - 1) * size
    return {"ids": [r["id"] for r in rows[start:start + size]], "total": len(rows),
            "delivered": sum(1 for r in rows if r.get("status") in ("delivered", "completed")),
            "failed": sum(1 for r in rows if r.get("status") == "failed"),
            "cost": round(sum(float(r.get("shipping_cost") or 0) for r in rows), 2)}


def test_history_equivalent_to_old_rule_on_reference_data(admin):
    """Penjaga — riwayat (halaman, total, statistik) = rumus lama pada data acuan (< 3.000 dokumen)."""
    scope = {"entity_id": "ent_ksc"}
    for params in ({}, {"page": 2, "size": 5}, {"date_from": "2026-10-01"}, {"status": "failed"}, {"q": "a"}):
        d = _get(admin, "/logistics/history", **params).json()
        old = _old_history(scope, **params)
        assert [r["id"] for r in d["rows"]] == old["ids"], params
        assert d["total"] == old["total"] and d["stats"]["delivered"] == old["delivered"], params
        assert d["stats"]["failed"] == old["failed"] and d["stats"]["shipping_cost_total"] == old["cost"], params


def test_history_not_capped_at_3000(admin):
    base = _ksc_delivery_scope() or {"entity_id": "ent_ksc"}
    old = datetime(2021, 1, 1, tzinfo=timezone.utc)
    DB.logistics_deliveries.insert_many([{**base, "id": f"{T}_dh_{i}", "number": f"LG-FIX7-H{i:05d}",
                                          "status": "delivered", "mode": "expedition", "customer_name": "Uji",
                                          "created_at": _iso(old), "delivered_at": _iso(old + timedelta(days=1)),
                                          "updated_at": _iso(old + timedelta(days=1))} for i in range(3005)])
    before = DB.logistics_deliveries.count_documents({"entity_id": "ent_ksc",
                                                      "status": {"$in": ["delivered", "completed", "failed"]}})
    d = _get(admin, "/logistics/history", size=5).json()
    assert d["total"] == before >= 3005, (d["total"], before)
    last = _get(admin, "/logistics/history", size=5, page=(before + 4) // 5).json()
    assert last["rows"], "halaman terakhir riwayat kosong (dulu terpotong 3.000)"


# ── D. sesi opname tanpa dokumen utuh ─────────────────────────────────────────────────────────────────────
def test_cycle_count_list_light_rows_with_counts_and_status_filter(admin):
    wh = (DB.warehouses.find_one({"active": {"$ne": False}, "sharing_mode": "shared", "is_test": {"$ne": True}},
                                 {"_id": 0, "id": 1, "name": 1}) or {})
    now = datetime.now(timezone.utc)
    DB.cycle_count_sessions.insert_many([
        {"id": f"{T}_cc_items", "entity_id": "ent_ksc", "warehouse_id": wh.get("id"), "warehouse_name": wh.get("name"),
         "name": "Uji FIX7 item", "status": "submitted", "mode": "cycle",
         "items": [{"product_id": f"p{i}", "counted_qty": i} for i in range(3)], "created_at": _iso(now)},
        {"id": f"{T}_cc_rolls", "entity_id": "ent_ksc", "warehouse_id": wh.get("id"), "warehouse_name": wh.get("name"),
         "name": "Uji FIX7 roll", "status": "open", "mode": "cycle", "items": [],
         "roll_count": {"scans": [{"code": "R1"}, {"code": "R2"}], "expected": []},
         "created_at": _iso(now - timedelta(minutes=1))}])
    rows = _get(admin, "/cycle-count/sessions").json()
    assert {f"{T}_cc_items", f"{T}_cc_rolls"} <= {s["id"] for s in rows}, [s["id"] for s in rows]
    for s in rows:
        assert "items" not in s and "roll_count" not in s, "baris daftar masih memuat dokumen sesi utuh (LST-07)"
        assert isinstance(s.get("item_count"), int) and isinstance(s.get("scan_count"), int)
        full = DB.cycle_count_sessions.find_one({"id": s["id"]}, {"_id": 0, "items": 1, "roll_count": 1}) or {}
        assert s["item_count"] == len(full.get("items") or [])
        assert s["scan_count"] == len((full.get("roll_count") or {}).get("scans") or [])
        assert s["roll_mode"] == bool(full.get("roll_count"))
    st = rows[0]["status"]
    only = _get(admin, "/cycle-count/sessions", status=st).json()
    assert only and all(s["status"] == st for s in only)


# ── E. cari perbaikan dengan karakter khusus ──────────────────────────────────────────────────────────────
def test_repair_search_special_chars_no_500(admin):
    for q in ("(", "[x", "a+"):
        r = requests.get(f"{BASE}/repair-orders", params={"q": q}, headers=admin, timeout=60)
        assert r.status_code == 200, (q, r.status_code, r.text[:200])
        assert "total" in r.json()
