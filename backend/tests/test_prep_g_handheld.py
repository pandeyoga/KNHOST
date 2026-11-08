"""PREP-G — API handheld Chainway C72 (`/api/handheld/*`): perangkat + operator, tugas per jenis dari lokasi kerja,
unduh "yang diharapkan", batch idempoten ber-cap-waktu perangkat, konflik per item, penyelesaian, potong sampel,
tulis EPC sistem (tag baru / ganti tag), Daftar Awal dengan cadangan EPC perangkat (offline), registri perangkat.

Semua data uji dibuat sendiri (site/gudang/roll/tag/dokumen ber-TAG) lalu dibuang; saldo & nomor urut dipulihkan.
Sesi pengguna demo dibuat langsung di DB (tanpa sandi); pengguna uji ber-sandi acak dibuat & dihapus di sini.
Jalankan TERPISAH (mengaktifkan sementara `wms.location_scope_enforced` di DB uji, dipulihkan di akhir):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_prep_g_handheld.py
"""
import os
import secrets
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402
from services.rfid_ingest_service import hash_device_key  # noqa: E402

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API, HH = f"{BASE}/api", f"{BASE}/api/handheld"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
T8 = TAG.upper()
ENT = "ent_ksc"
SITE, SITE_X = f"site_TEST_G_{TAG}", f"site_TEST_GX_{TAG}"
WH_A, WH_B, WH_X, WH_R = (f"wh_TEST_G_{TAG}_{k}" for k in ("a", "b", "x", "reg"))
DEV_X, DEV_GATE, DEV_B = f"dev_TEST_G_{TAG}_x", f"dev_TEST_G_{TAG}_gate", f"dev_TEST_G_{TAG}_b"
KEY_X, KEY_GATE, KEY_B = (f"dk_TEST_G_{TAG}_{k}" for k in ("x", "gate", "b"))
STATE = {"n": 0}
COLLECTIONS = ["inventory_rolls", "inventory_movements", "inventory_lots", "audit_logs", "notifications", "rfid_tags",
               "rfid_devices", "putaway_orders", "warehouses", "warehouse_sites", "warehouse_transfers", "sales_orders",
               "wms_tasks", "rfid_verify_sessions", "rfid_cycle_counts", "rfid_print_jobs", "cycle_count_sessions",
               "initial_registration_lines", "registration_area_status", "users", "sessions", "products", "doc_refs",
               "handheld_operator_sessions", "handheld_requests", "handheld_tag_writes", "handheld_epc_reservations",
               "roll_scans", "rfid_v2_gate_txn", "rfid_v2_reviews", "login_attempts", "system_settings", "config_values",
               "config_history", "journal_entries"]


def _nx():
    STATE["n"] += 1
    return STATE["n"]


def epc(i):
    return f"E2{T8}{i:014X}"


def session_for(email):
    """Sesi ERP langsung di DB (tanpa sandi) — header Bearer seperti hasil login."""
    u = DB.users.find_one({"email": email}, {"_id": 0, "id": 1})
    assert u, f"pengguna {email} tidak ada di data acuan"
    tok = f"tok_TEST_G_{secrets.token_hex(12)}"
    DB.sessions.insert_one({"id": f"session_TEST_G_{_nx()}", "token": tok, "user_id": u["id"], "created_at": datetime.now(timezone.utc),
                            "expires_at": datetime.now(timezone.utc) + timedelta(hours=8)})
    return {"Authorization": f"Bearer {tok}"}


def hdr(user, key):
    return {**user, "X-Device-Key": key}


@pytest.fixture(scope="module")
def world():
    from core_utils import hash_password
    from services.config_resolver import set_value, value_of
    try:
        requests.get(f"{API}/health", timeout=10)
    except requests.RequestException:
        pytest.skip("backend tidak berjalan")
    stock = snapshot_stock(["inventory_balances", "number_sequences"])
    assert stock.get("__enabled__"), "restore harus aktif (DB uji)"
    ids = snapshot_new_ids(COLLECTIONS)
    was_enforced = run(value_of("wms.location_scope_enforced"))
    if not was_enforced:
        run(set_value("wms.location_scope_enforced", True, scope_type="global", actor="Uji PREP-G", reason="uji cakupan lokasi handheld"))
    DB.warehouse_sites.insert_many([{"id": SITE, "name": f"Uji G {TAG}", "code": f"UG{TAG}"},
                                    {"id": SITE_X, "name": f"Uji GX {TAG}", "code": f"UGX{TAG}"}])
    zones = [{"id": f"zone_G_{TAG}", "name": "Zona A", "racks": [{"id": f"rack_G_{TAG}", "name": "Rak A1",
                                                                  "bins": [{"id": f"bin_G_{TAG}_1", "code": f"A1-01-{TAG}", "capacity": 1000},
                                                                           {"id": f"bin_G_{TAG}_2", "code": f"A1-02-{TAG}", "capacity": 1000}]}]},
             {"id": f"zone_G2_{TAG}", "name": "Zona B", "racks": [{"id": f"rack_G2_{TAG}", "name": "Rak B1",
                                                                   "bins": [{"id": f"bin_G2_{TAG}_1", "code": f"B1-01-{TAG}", "capacity": 1000}]}]}]
    for wid, code, site, roles, extra in ((WH_A, f"GA{TAG}", SITE, ["storage"], {}), (WH_B, f"GB{TAG}", SITE, ["transit", "receiving"], {}),
                                          (WH_X, f"GX{TAG}", SITE_X, ["storage"], {}), (WH_R, f"GR{TAG}", SITE, ["storage"], {"zones": zones})):
        DB.warehouses.insert_one({"id": wid, "name": f"Uji G {code}", "code": code, "roles": roles, "site_id": site, "city": "Bandung",
                                  "sharing_mode": "shared", "active": True, "gate_config": {"has_gate": False},
                                  "created_at": "2026-01-01T00:00:00+00:00", **extra})
    for did, wh, typ, key in ((DEV_X, WH_X, "handheld", KEY_X), (DEV_GATE, WH_A, "gate", KEY_GATE), (DEV_B, WH_B, "handheld", KEY_B)):
        DB.rfid_devices.insert_one({"id": did, "code": f"G-{did[-4:]}-{TAG}", "name": f"Uji {did[-4:]}", "type": typ,
                                    "direction": "in" if typ == "gate" else "n/a", "warehouse_id": wh, "enabled": True,
                                    "status": "online", "api_key_hash": hash_device_key(key)})
    users = {}
    for k, role, sites, whs in (("op", "warehouse", [SITE], [WH_A]), ("opx", "warehouse", [SITE_X], []), ("drv", "driver", [], [])):
        pw = secrets.token_urlsafe(14)
        uid = f"usr_TEST_G_{TAG}_{k}"
        DB.users.insert_one({"id": uid, "email": f"uji.g.{k}.{TAG}@contoh.test", "name": f"Uji G {k}", "role": role, "status": "active",
                             "password_hash": hash_password(pw), "home_entity_id": ENT, "allowed_entity_ids": [ENT],
                             "location_site_ids": sites, "location_warehouse_ids": whs, "created_at": "2026-01-01T00:00:00+00:00"})
        users[k] = {"id": uid, "email": f"uji.g.{k}.{TAG}@contoh.test", "pw": pw}
    p = DB.products.find_one({"status": {"$ne": "inactive"}, "base_unit": "meter"}, {"_id": 0, "id": 1, "sku": 1, "name": 1})
    assert p, "data acuan tanpa produk meter"
    if not was_enforced:
        time.sleep(16)   # cache setelan cakupan lokasi di proses server (15 dtk)
    yield {"users": users, "product": p}
    purge_new_ids(ids, verbose=False)
    restore_stock(stock)
    if not was_enforced:
        run(set_value("wms.location_scope_enforced", False, scope_type="global", actor="Uji PREP-G", reason="pulihkan setelan uji"))


@pytest.fixture(scope="module")
def admin(world):
    return session_for("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def whadmin(world):
    return session_for("wh.admin@kainnusantara.id")


@pytest.fixture(scope="module")
def device(world, admin):
    """Perangkat C72 dibuat lewat API registri (key tampil SEKALI) — terikat WH_A, cakupan site."""
    r = requests.post(f"{HH}/devices", headers=admin, timeout=30,
                      json={"name": f"C72 Uji {TAG}", "warehouse_id": WH_A, "code": f"C72-{TAG}", "scope_level": "site"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["shown_once"] and body["api_key"].startswith("dk_") and '"kn":"c72"' in body["provisioning"]["qr_text"]
    assert not DB.rfid_devices.find_one({"id": body["device"]["id"]}).get("api_key"), "key tidak boleh tersimpan polos"
    return {"id": body["device"]["id"], "key": body["api_key"]}


@pytest.fixture(scope="module")
def op(world):
    """Operator gudang uji: login ERP sungguhan (sandi acak) — lokasi kerja hanya WH_A."""
    u = world["users"]["op"]
    r = requests.post(f"{API}/auth/login", json={"email": u["email"], "password": u["pw"]}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def start_op(user, key):
    r = requests.post(f"{HH}/session/start", headers=hdr(user, key), json={"app_version": "0.1.0-lab"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def rolls(world, n, wh, status="available", tagged=True, **extra):
    out = []
    for _ in range(n):
        i = _nx()
        rid, tid = f"roll_TEST_G_{TAG}_{i}", f"tag_TEST_G_{TAG}_{i}"
        if tagged:
            DB.rfid_tags.insert_one({"id": tid, "epc": epc(i), "roll_id": rid, "status": "active", "warehouse_id": wh,
                                     "owner_entity_id": ENT, "created_at": "2026-11-01T00:00:00+00:00"})
        DB.inventory_rolls.insert_one({
            "id": rid, "roll_no": f"G{TAG}{i}", "product_id": world["product"]["id"], "warehouse_id": wh, "owner_entity_id": ENT,
            "status": status, "length_remaining": 30.0, "length_initial": 30.0, "unit": "meter", "grade": "A", "lot": "L-G",
            "rfid_tag_id": tid if tagged else None, "bin_id": None, "active_movement": None, "length_reserved": 0,
            "length_reservations": [], "created_at": "2026-11-01T00:00:00+00:00",
            "journey": {"stage": "tag_verified", "verified_tag_id": tid, "routing": "store", "updated_at": "2026-11-02T00:00:00+00:00"} if tagged else {},
            **extra})
        out.append({"id": rid, "epc": epc(i) if tagged else "", "roll_no": f"G{TAG}{i}"})
    return out


def batch(user, key, kind, doc_id, reads=(), labels=(), cid=None, op_id=None, **extra):
    body = {"client_batch_id": cid or f"b-{uuid.uuid4()}", "kind": kind, "doc_id": doc_id, "operator_session_id": op_id,
            "device_time": "2026-11-09T01:00:00Z", "clock_offset_ms": 1200, "clock_synced": True,
            "reads": [{"epc": e, "rssi": -55.5, "count": 3, "first_seen": "2026-11-09T00:59:58Z", "last_seen": "2026-11-09T00:59:59Z"} for e in reads],
            "labels": list(labels), **extra}
    return requests.post(f"{HH}/batches", headers=hdr(user, key), json=body, timeout=90), body


def expected(user, key, kind, doc_id, **params):
    r = requests.get(f"{HH}/tasks/{kind}/{doc_id}/expected", headers=hdr(user, key), params=params, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def code_of(r):
    d = r.json().get("detail")
    return d.get("code") if isinstance(d, dict) else d


# ── 1. Identitas: perangkat + pengguna, binding & penolakan ───────────────────
def test_device_identity_and_binding(world, device, op):
    r = requests.get(f"{HH}/device/config", headers={"X-Device-Key": device["key"]}, timeout=30)
    assert r.status_code == 200, r.text
    cfg = r.json()
    whs = {w["id"] for w in cfg["device"]["warehouses"]}
    assert {WH_A, WH_B, WH_R} <= whs and WH_X not in whs, "cakupan perangkat = site gudangnya"
    assert cfg["profile"]["commissioned"] is False and cfg["server_time"] and len(cfg["kinds"]) == 8
    assert code_of(requests.get(f"{HH}/device/config", timeout=30)) == "DEVICE_KEY_REQUIRED"
    assert code_of(requests.get(f"{HH}/device/config", headers={"X-Device-Key": "dk_salah"}, timeout=30)) == "DEVICE_KEY_INVALID"
    g = requests.get(f"{HH}/device/config", headers={"X-Device-Key": KEY_GATE}, timeout=30)
    assert g.status_code == 403 and code_of(g) == "DEVICE_NOT_HANDHELD"
    assert requests.get(f"{HH}/me", headers={"X-Device-Key": device["key"]}, timeout=30).status_code == 401, "kerja wajib sesi pengguna"
    assert code_of(requests.get(f"{HH}/me", headers=op, timeout=30)) == "DEVICE_KEY_REQUIRED", "kerja wajib device key"


def test_operator_session_switch_and_scope(world, device, op, whadmin):
    me = start_op(op, device["key"])
    assert [w["id"] for w in me["warehouses"]] == [WH_A] and me["location_restricted"], "perangkat ∩ lokasi kerja pengguna"
    op1 = me["operator_session"]["id"]
    sup = start_op(whadmin, device["key"])
    assert {WH_A, WH_B, WH_R} <= {w["id"] for w in sup["warehouses"]}, "supervisor: seluruh cakupan perangkat"
    assert DB.handheld_operator_sessions.find_one({"id": op1})["ended_at"], "login operator lain = ganti operator (sesi lama ditutup)"
    r, _ = batch(whadmin, device["key"], "putaway_in", "pa_tidak_ada", reads=[epc(999)], op_id=op1)
    assert r.status_code == 409 and code_of(r) == "OPERATOR_MISMATCH", "bukti operator lama tidak dikirim atas nama operator baru"
    r, _ = batch(op, device["key"], "putaway_in", "pa_tidak_ada", reads=[epc(999)], user_id=world["users"]["opx"]["id"])
    assert r.status_code == 409 and code_of(r) == "OPERATOR_MISMATCH"
    opx = session_for(world["users"]["opx"]["email"])
    mx = start_op(opx, device["key"])
    assert mx["warehouses"] == [], "pengguna site lain: tidak ada gudang di perangkat ini"
    assert start_op(opx, KEY_X)["warehouses"][0]["id"] == WH_X
    drv = session_for(world["users"]["drv"]["email"])
    r = requests.get(f"{HH}/tasks", headers=hdr(drv, device["key"]), params={"kind": "putaway_in"}, timeout=30)
    assert r.status_code == 403 and code_of(r) == "PERMISSION_DENIED", "izin jenis tugas = izin endpoint web asal"
    WORLD_OPS["op"] = start_op(op, device["key"])["operator_session"]["id"]


WORLD_OPS = {}


# ── 2. Masuk · Putaway: trip massal idempoten, ekstra diabaikan, dokumen tertutup = konflik ───────────
def published_pa(world, admin, n):
    from services import inbound_qc_common as iqc
    rs = rolls(world, n, WH_B)
    out = run(iqc.auto_draft_after_release([r["id"] for r in rs], {"type": "test_g", "id": f"{TAG}-{_nx()}"}, "Penguji"))
    drafts = [d for d in out["drafts"] if d["to_warehouse_name"] == f"Uji G GA{TAG}"]
    assert len(drafts) == 1, out
    pa_id = drafts[0]["id"]
    for path in ("publish", "dispatch"):
        r = requests.post(f"{API}/putaway-orders/{pa_id}/{path}", headers={**admin, "X-Entity-Id": ENT}, json={}, timeout=60)
        assert r.status_code == 200, r.text
    return pa_id, rs


def test_putaway_bulk_trip(world, device, op, admin):
    pa_id, rs = published_pa(world, admin, 4)
    tasks = requests.get(f"{HH}/tasks", headers=hdr(op, device["key"]), params={"kind": "putaway_in"}, timeout=30).json()["tasks"]
    assert pa_id in {t["doc_id"] for t in tasks}, "PA ke WH_A tampil di daftar Masuk · Putaway"
    snap = expected(op, device["key"], "putaway_in", pa_id)
    assert snap["counts"]["expected"] == 4 and {r["epc"] for r in snap["rows"]} == {r["epc"] for r in rs} and not snap["closed"]
    r, body = batch(op, device["key"], "putaway_in", pa_id, reads=[rs[0]["epc"], rs[1]["epc"], epc(9999)], op_id=WORLD_OPS["op"],
                    snapshot_version=snap["version"])
    assert r.status_code == 200, r.text
    res = r.json()
    by = {i["ref"]: i for i in res["items"]}
    assert res["status"] == "accepted" and not res["replay"] and not res["snapshot_stale"]
    assert by[rs[0]["epc"]]["result"] == "arrived" and by[rs[1]["epc"]]["result"] == "arrived" and by[epc(9999)]["result"] == "extra"
    assert res["doc"]["status"] == "partially_received" and res["doc"]["done"] == 2
    again = requests.post(f"{HH}/batches", headers=hdr(op, device["key"]), json=body, timeout=60).json()
    assert again["replay"] and again["items"] == res["items"], "kirim ulang badan sama = hasil tersimpan"
    assert len(DB.putaway_orders.find_one({"id": pa_id})["arrival_trips"]) == 1, "kirim ulang tidak menambah trip"
    bad = requests.post(f"{HH}/batches", headers=hdr(op, device["key"]), json={**body, "reads": [{"epc": rs[2]["epc"]}]}, timeout=60)
    assert bad.status_code == 409 and code_of(bad) == "IDEMPOTENCY_CONFLICT"
    req = DB.handheld_requests.find_one({"_id": f"{device['id']}:batch:{body['client_batch_id']}"})
    assert req["clock_skew_ms"] is not None and req["device_time"] == "2026-11-09T01:00:00Z" and req["reads"][0]["rssi"] == -55.5
    assert req["user_id"] == world["users"]["op"]["id"] and req["operator_session_id"] == WORLD_OPS["op"]
    r2, _ = batch(op, device["key"], "putaway_in", pa_id, reads=[rs[1]["epc"], rs[2]["epc"], rs[3]["epc"]], op_id=WORLD_OPS["op"])
    by2 = {i["ref"]: i["result"] for i in r2.json()["items"]}
    assert by2 == {rs[1]["epc"]: "already", rs[2]["epc"]: "arrived", rs[3]["epc"]: "arrived"}
    assert r2.json()["doc"]["status"] == "completed"
    r3, _ = batch(op, device["key"], "putaway_in", pa_id, reads=[rs[0]["epc"]], op_id=WORLD_OPS["op"])
    assert r3.status_code == 200 and r3.json()["status"] == "conflict" and r3.json()["error"]["code"] == "DOC_CLOSED", \
        "dokumen tertutup saat offline → konflik final (HTTP 200, tidak diulang)"
    trips = DB.putaway_orders.find_one({"id": pa_id})["arrival_trips"]
    assert len(trips) == 2 and all(t["source"]["type"] == "handheld" for t in trips)
    sim, _ = batch(op, device["key"], "putaway_in", pa_id, reads=[rs[0]["epc"]], simulated=True)
    assert sim.json()["status"] == "conflict" and sim.json()["error"]["code"] == "SIMULATION_NOT_ALLOWED"


def test_scope_denied_other_location(world, device, admin):
    pa_id, _ = published_pa(world, admin, 1)
    opx = session_for(world["users"]["opx"]["email"])
    r = requests.get(f"{HH}/tasks/putaway_in/{pa_id}/expected", headers=hdr(opx, KEY_X), timeout=30)
    assert r.status_code == 403 and code_of(r) == "SCOPE_DENIED", "dokumen gudang lain ditolak"
    tasks = requests.get(f"{HH}/tasks", headers=hdr(opx, KEY_X), params={"kind": "putaway_in"}, timeout=30).json()["tasks"]
    assert pa_id not in {t["doc_id"] for t in tasks}


# ── 3. Transfer masuk: terima per roll lewat layanan asal, ekstra tidak jadi exception ─────────────
def test_transfer_receive(world, device, op):
    tid = f"trf_TEST_G_{TAG}"
    rs = rolls(world, 3, WH_B, status="in_transit_transfer", reserved_ref={"type": "wh_transfer", "id": tid})
    DB.warehouse_transfers.insert_one({
        "id": tid, "code": f"TRF-G-{TAG}", "transfer_number": f"TRF-G-{TAG}", "status": "dispatched", "transfer_kind": "intra_entity",
        "entity_id": ENT, "source_warehouse_id": WH_B, "dest_warehouse_id": WH_A, "source_warehouse_name": "Uji B",
        "items": [{"product_id": world["product"]["id"], "sku": world["product"]["sku"], "product_name": world["product"]["name"], "unit": "meter",
                   "rolls": [{"roll_id": r["id"], "roll_no": r["roll_no"], "lot": "L-G", "length": 30.0} for r in rs]}],
        "created_at": "2026-11-09T00:00:00+00:00"})
    assert tid in {t["doc_id"] for t in requests.get(f"{HH}/tasks", headers=hdr(op, device["key"]), params={"kind": "transfer_in"}, timeout=30).json()["tasks"]}
    snap = expected(op, device["key"], "transfer_in", tid)
    assert snap["counts"]["pending"] == 3
    r, _ = batch(op, device["key"], "transfer_in", tid, reads=[rs[0]["epc"], rs[1]["epc"], epc(8888)], op_id=WORLD_OPS["op"])
    res = r.json()
    by = {i["ref"]: i["result"] for i in res["items"]}
    assert by == {rs[0]["epc"]: "received", rs[1]["epc"]: "received", epc(8888): "extra"}, res
    assert res["doc"]["status"] == "partially_received"
    t = DB.warehouse_transfers.find_one({"id": tid})
    assert not [e for e in t.get("exceptions") or [] if e.get("kind") == "wrong_roll"], "bacaan sekitar tidak jadi 'salah kirim'"
    assert DB.inventory_rolls.find_one({"id": rs[0]["id"]})["warehouse_id"] == WH_A
    DB.inventory_rolls.update_one({"id": rs[2]["id"]}, {"$set": {"status": "available", "reserved_ref": None}})   # berubah saat offline
    r2, _ = batch(op, device["key"], "transfer_in", tid, reads=[rs[1]["epc"], rs[2]["epc"]], op_id=WORLD_OPS["op"])
    by2 = {i["ref"]: i for i in r2.json()["items"]}
    assert by2[rs[1]["epc"]]["result"] == "already" and by2[rs[2]["epc"]]["result"] == "conflict" and by2[rs[2]["epc"]]["conflict"], \
        "roll yang statusnya berubah saat offline → konflik per item"


# ── 4. Keluar · SO: sesi cek muat eksplisit, batch massal, selesaikan idempoten ─────────────────────
def test_loading_check(world, device, op):
    so = f"so_TEST_G_{TAG}"
    DB.sales_orders.insert_one({"id": so, "number": f"SO-G-{TAG}", "status": "in_progress", "entity_id": ENT, "customer_name": "Uji"})
    rs = rolls(world, 3, WH_A, status="picked", reserved_ref={"type": "sales_order", "id": so})
    DB.wms_tasks.insert_one({"id": f"wms_TEST_G_{TAG}", "flow_type": "outbound", "order_id": so, "order_number": f"SO-G-{TAG}",
                             "warehouse_id": WH_A, "entity_id": ENT, "status": "packing", "product_name": "Uji",
                             "created_at": "2026-11-09T00:00:00+00:00"})
    doc = f"{so}~{WH_A}"
    assert doc in {t["doc_id"] for t in requests.get(f"{HH}/tasks", headers=hdr(op, device["key"]), params={"kind": "outbound_so"}, timeout=30).json()["tasks"]}
    snap = expected(op, device["key"], "outbound_so", doc)
    assert snap["needs_start"] and not snap["session_id"], "sesi cek muat TIDAK dibuat diam-diam"
    snap = expected(op, device["key"], "outbound_so", doc, start="true")
    sid = snap["session_id"]
    assert sid and snap["counts"]["expected"] == 3
    r, _ = batch(op, device["key"], "outbound_so", doc, reads=[rs[0]["epc"], rs[1]["epc"], epc(7777)], session_id=sid, op_id=WORLD_OPS["op"])
    by = {i["ref"]: i["result"] for i in r.json()["items"]}
    assert by == {rs[0]["epc"]: "matched", rs[1]["epc"]: "matched", epc(7777): "extra"}
    sess = DB.rfid_verify_sessions.find_one({"id": sid})
    assert sess["scan_sources"] == ["device"] and sess["scan_log"][-1]["device_id"] == device["id"], "bukti asal = perangkat (tercatat)"
    cid = f"c-{uuid.uuid4()}"
    body = {"client_request_id": cid, "session_id": sid, "operator_session_id": WORLD_OPS["op"]}
    c = requests.post(f"{HH}/tasks/outbound_so/{doc}/complete", headers=hdr(op, device["key"]), json=body, timeout=60)
    assert c.status_code == 200 and c.json()["result"] == "with_issues" and c.json()["session"]["missing"] == 1, c.text
    again = requests.post(f"{HH}/tasks/outbound_so/{doc}/complete", headers=hdr(op, device["key"]), json=body, timeout=60).json()
    assert again["replay"] and again["result"] == "with_issues"
    assert (DB.sales_orders.find_one({"id": so}).get("loading_checks") or {}).get(WH_A, {}).get("result") == "with_issues"
    late, _ = batch(op, device["key"], "outbound_so", doc, reads=[rs[2]["epc"]], session_id=sid, op_id=WORLD_OPS["op"])
    assert late.json()["status"] == "conflict" and late.json()["error"]["code"] == "DOC_CLOSED"
    no = requests.post(f"{HH}/tasks/putaway_in/x/complete", headers=hdr(op, device["key"]), json={"client_request_id": f"c-{uuid.uuid4()}"}, timeout=30)
    assert no.status_code == 400 and code_of(no) == "COMPLETE_NOT_SUPPORTED"


# ── 5. Stock Opname RFID + verifikasi cetak (sesi bukti; simulasi berlabel) ──────────────────────────
def test_cycle_count_and_print_verify(world, device, whadmin):
    hh = hdr(whadmin, device["key"])
    opw = start_op(whadmin, device["key"])["operator_session"]["id"]
    snap = expected(whadmin, device["key"], "cycle_count", WH_A, start="true")
    sid = snap["session_id"]
    reads = [r["epc"] for r in snap["rows"]]
    assert len(reads) >= 5, "roll bertag di WH_A (dari uji sebelumnya) masuk daftar opname"
    r, _ = batch(whadmin, device["key"], "cycle_count", WH_A, reads=reads + [epc(6666)], session_id=sid, op_id=opw)
    assert r.json()["summary"]["matched"] == len(reads) and r.json()["summary"]["extra"] == 1
    c = requests.post(f"{HH}/tasks/cycle_count/{WH_A}/complete", headers=hh, timeout=90,
                      json={"client_request_id": f"c-{uuid.uuid4()}", "session_id": sid, "operator_session_id": opw})
    assert c.status_code == 200 and c.json()["cycle_count"]["cc_number"], c.text
    rs = rolls(world, 2, WH_A)
    job = f"rpj_TEST_G_{TAG}"
    DB.rfid_print_jobs.insert_one({"id": job, "job_number": f"PJ-G-{TAG}", "status": "printed", "kind": "rfid_tag", "warehouse_id": WH_A,
                                   "owner_entity_id": ENT, "created_at": "2026-11-09T00:00:00+00:00",
                                   "items": [{"epc": r["epc"], "roll_id": r["id"], "roll_no": r["roll_no"], "sku": "S", "product_name": "P"} for r in rs]})
    assert job in {t["doc_id"] for t in requests.get(f"{HH}/tasks", headers=hh, params={"kind": "print_verify"}, timeout=30).json()["tasks"]}
    pv = expected(whadmin, device["key"], "print_verify", job, start="true")
    batch(whadmin, device["key"], "print_verify", job, reads=[r["epc"] for r in rs], session_id=pv["session_id"], op_id=opw)
    c2 = requests.post(f"{HH}/tasks/print_verify/{job}/complete", headers=hh, timeout=60,
                       json={"client_request_id": f"c-{uuid.uuid4()}", "session_id": pv["session_id"], "operator_session_id": opw})
    assert c2.json()["result"] == "clean" and DB.rfid_print_jobs.find_one({"id": job})["status"] == "verified"
    # simulasi di sesi bukti → berlabel simulated (tidak pernah jadi hasil operasional)
    sim = expected(whadmin, device["key"], "cycle_count", WH_A, start="true")
    rs_sim, _ = batch(whadmin, device["key"], "cycle_count", WH_A, reads=reads[:1], session_id=sim["session_id"], op_id=opw, simulated=True)
    assert rs_sim.json()["status"] == "accepted"
    assert "simulated" in DB.rfid_verify_sessions.find_one({"id": sim["session_id"]})["scan_sources"]


# ── 6. Potong sampel (identifikasi roll induk → layanan potong asal) ───────────────────────────────
def test_cutting(world, device, op):
    so = f"sos_TEST_G_{TAG}"
    pid = world["product"]["id"]
    DB.sales_orders.insert_one({"id": so, "number": f"SOS-G-{TAG}", "status": "confirmed", "entity_id": ENT, "order_type": "sample",
                                "customer_name": "Uji", "items": [{"product_id": pid, "is_sample": True, "quantity": 2, "unit": "meter",
                                                                    "price": 0, "subtotal": 0}], "allocations": []})
    parent = rolls(world, 1, WH_A)[0]
    task = f"wms_TEST_G_{TAG}_cut"
    DB.wms_tasks.insert_one({"id": task, "flow_type": "outbound", "task_subtype": "sample_cut", "order_type": "sample", "order_id": so,
                             "order_number": f"SOS-G-{TAG}", "product_id": pid, "sku": world["product"]["sku"], "product_name": "Uji",
                             "quantity": 2, "picked_qty": 0, "unit": "meter", "warehouse_id": WH_A, "entity_id": ENT, "status": "created",
                             "suggested_roll_id": parent["id"], "suggested_roll_no": parent["roll_no"], "scan_log": [],
                             "created_at": "2026-11-09T00:00:00+00:00"})
    snap = expected(op, device["key"], "cutting", task)
    assert snap["rows"][0]["roll_id"] == parent["id"] and snap["rows"][0]["suggested"] and snap["rows"][0]["epc"] == parent["epc"]
    body = {"client_request_id": f"k-{uuid.uuid4()}", "epc": parent["epc"], "actual_length": 2, "operator_session_id": WORLD_OPS["op"]}
    r = requests.post(f"{HH}/tasks/cutting/{task}/cut", headers=hdr(op, device["key"]), json=body, timeout=60)
    assert r.status_code == 200 and r.json()["status"] == "accepted", r.text
    child = r.json()["cut"]["child_roll_id"]
    assert r.json()["child_needs_tag"] and not DB.inventory_rolls.find_one({"id": child}).get("rfid_tag_id"), "potongan lahir tanpa tag"
    again = requests.post(f"{HH}/tasks/cutting/{task}/cut", headers=hdr(op, device["key"]), json=body, timeout=60).json()
    assert again["replay"] and again["cut"]["child_roll_id"] == child, "potong tidak terjadi dua kali"
    WORLD_OPS["child"] = child


# ── 7. Tulis EPC sistem: tag baru (roll potongan) & ganti tag ───────────────────────────────────────
def write_intent(user, key, code, op_id):
    cid = f"w-{uuid.uuid4()}"
    r = requests.post(f"{HH}/tag-writes", headers=hdr(user, key), timeout=30, json={"client_request_id": cid, "code": code, "operator_session_id": op_id})
    assert r.status_code == 200 and r.json()["status"] == "accepted", r.text
    return cid, r.json()["write"]


def confirm(user, key, wid, verified, op_id):
    return requests.post(f"{HH}/tag-writes/{wid}/confirm", headers=hdr(user, key), timeout=30,
                         json={"client_request_id": f"t-{uuid.uuid4()}", "verified_epc": verified, "rssi": -41.0, "attempts": 1,
                               "operator_session_id": op_id})


def test_tag_write_new_and_replace(world, device, op):
    child = WORLD_OPS["child"]
    cid, w = write_intent(op, device["key"], child, WORLD_OPS["op"])
    assert w["purpose"] == "new" and len(w["epc"]) == 24 and w["epc"].startswith("E2") and not w["old_epc"]
    same = requests.post(f"{HH}/tag-writes", headers=hdr(op, device["key"]), timeout=30,
                         json={"client_request_id": cid, "code": child, "operator_session_id": WORLD_OPS["op"]}).json()
    assert same["replay"] and same["write"]["epc"] == w["epc"], "minta ulang = EPC sama"
    opb = session_for("wh.admin@kainnusantara.id")
    other = requests.post(f"{HH}/tag-writes", headers=hdr(opb, KEY_B), timeout=30, json={"client_request_id": f"w-{uuid.uuid4()}", "code": child})
    assert other.json()["status"] == "conflict" and other.json()["error"]["code"] == "WRITE_IN_PROGRESS", "satu roll satu niat tulis"
    bad = confirm(op, device["key"], w["id"], epc(5555), WORLD_OPS["op"]).json()
    assert bad["status"] == "conflict" and bad["error"]["code"] == "VERIFY_MISMATCH"
    ok = confirm(op, device["key"], w["id"], w["epc"], WORLD_OPS["op"]).json()
    assert ok["status"] == "accepted" and ok["write"]["status"] == "confirmed"
    roll = DB.inventory_rolls.find_one({"id": child})
    tag = DB.rfid_tags.find_one({"id": roll["rfid_tag_id"]})
    assert tag["epc"] == w["epc"] and tag["status"] == "active" and tag["written_via"] == "handheld_c72"
    assert roll["journey"]["verified_tag_id"] == tag["id"], "baca ulang C72 = bukti verifikasi tag-roll"
    # ganti tag: tag lama tetap berlaku sampai konfirmasi
    _, w2 = write_intent(op, device["key"], child, WORLD_OPS["op"])
    assert w2["purpose"] == "replace" and w2["old_epc"] == w["epc"]
    assert DB.rfid_tags.find_one({"id": tag["id"]})["status"] == "active", "tag lama belum dicabut sebelum konfirmasi"
    assert confirm(op, device["key"], w2["id"], w2["epc"], WORLD_OPS["op"]).json()["status"] == "accepted"
    assert DB.rfid_tags.find_one({"id": tag["id"]})["status"] == "retired"
    assert DB.rfid_tags.find_one({"epc": w2["epc"], "status": "active"})["roll_id"] == child
    # gagal tulis → niat ditutup, EPC tidak dipakai
    _, w3 = write_intent(op, device["key"], child, WORLD_OPS["op"])
    f = requests.post(f"{HH}/tag-writes/{w3['id']}/fail", headers=hdr(op, device["key"]), json={"reason": "tag rusak"}, timeout=30).json()
    assert f["write"]["status"] == "failed" and not DB.rfid_tags.find_one({"epc": w3["epc"]})
    lk = requests.get(f"{HH}/lookup", headers=hdr(op, device["key"]), params={"code": w2["epc"]}, timeout=30).json()
    assert lk["roll"]["id"] == child and lk["tag"]["epc"] == w2["epc"]


# ── 8. Daftar Awal: cadangan EPC perangkat (offline) + mode baca ────────────────────────────────────
def reg_session(whadmin, mode, zone):
    r = requests.post(f"{API}/registration/sessions", headers={**whadmin, "X-Entity-Id": ENT}, timeout=30,
                      json={"warehouse_id": WH_R, "name": f"Uji G {mode} {TAG}", "freeze_mode": "zone", "node_ids": [zone],
                            "epc_mode": mode})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    s = requests.post(f"{API}/registration/sessions/{sid}/start", headers={**whadmin, "X-Entity-Id": ENT}, timeout=30)
    assert s.status_code == 200, s.text
    return sid


def test_registration_system_and_read(world, device, whadmin):
    opw = start_op(whadmin, device["key"])["operator_session"]["id"]
    hh = hdr(whadmin, device["key"])
    sid = reg_session(whadmin, "system", f"zone_G_{TAG}")
    assert sid in {t["doc_id"] for t in requests.get(f"{HH}/tasks", headers=hh, params={"kind": "registration"}, timeout=30).json()["tasks"]}
    snap = expected(whadmin, device["key"], "registration", sid)
    reg = snap["registration"]
    assert reg["epc_mode"] == "system" and len(reg["bins"]) == 2 and reg["owners"]
    cat = requests.get(f"{HH}/registration/catalog", headers=hh, timeout=60).json()
    assert cat["count"] > 0 and all(p["base_unit"] for p in cat["products"])
    pool = requests.post(f"{HH}/registration/{sid}/epc-pool", headers=hh, json={"count": 5}, timeout=30).json()
    assert pool["count"] == 5 and len(set(pool["epcs"])) == 5
    assert requests.post(f"{HH}/registration/{sid}/epc-pool", headers=hh, json={"count": 5}, timeout=30).json()["epcs"] == pool["epcs"], \
        "cadangan diisi sampai jumlah, tidak menumpuk"
    bin1 = reg["bins"][0]["id"]
    line = {"client_line_id": f"l-{TAG}-1", "epc": pool["epcs"][0], "written": True, "captured_at": "2026-11-09T02:00:00Z",
            "bin_id": bin1, "owner_entity_id": ENT, "product_id": world["product"]["id"], "qty": 25.5, "unit": "meter",
            "length_from_label": True, "lot": "LT-1", "grade": "A", "old_roll_no": ""}
    foreign = {**line, "client_line_id": f"l-{TAG}-2", "epc": epc(4444)}
    unrec = {"client_line_id": f"l-{TAG}-3", "epc": pool["epcs"][1], "written": True, "bin_id": bin1, "owner_entity_id": ENT,
             "unrecognized": True, "note": "motif uji biru"}
    r, body = batch(whadmin, device["key"], "registration", sid, lines=[line, foreign, unrec], op_id=opw)
    assert r.status_code == 200, r.text
    by = {i["ref"]: i for i in r.json()["items"]}
    assert by[line["client_line_id"]]["result"] == "saved" and by[line["client_line_id"]]["tag_state"] == "written"
    assert by[foreign["client_line_id"]]["result"] == "conflict", "EPC bukan cadangan perangkat ditolak"
    assert by[unrec["client_line_id"]]["result"] == "saved"
    ln = DB.initial_registration_lines.find_one({"id": by[line["client_line_id"]]["line_id"]})
    assert ln["epc"] == pool["epcs"][0] and ln["epc_source"] == "system" and ln["tag_state"] == "written" and ln["length_verified"]
    assert ln["hh_client_line_id"] == line["client_line_id"] and ln["hh_device_id"] == device["id"]
    assert DB.handheld_epc_reservations.find_one({"epc": pool["epcs"][0]})["status"] == "used"
    r2, _ = batch(whadmin, device["key"], "registration", sid, lines=[line], op_id=opw)
    assert r2.json()["items"][0]["result"] == "saved" and "sebelumnya" in r2.json()["items"][0]["message"], "baris dikirim ulang tidak berlipat"
    assert DB.initial_registration_lines.count_documents({"session_id": sid, "live": True}) == 2
    sim, _ = batch(whadmin, device["key"], "registration", sid, lines=[line], simulated=True)
    assert sim.json()["error"]["code"] == "SIMULATION_NOT_ALLOWED"
    # mode EPC bawaan (dibaca): EPC tag terkuat dikirim apa adanya; cadangan EPC tidak berlaku
    rid = reg_session(whadmin, "read", f"zone_G2_{TAG}")
    assert requests.post(f"{HH}/registration/{rid}/epc-pool", headers=hh, json={"count": 5}, timeout=30).status_code == 400
    rbin = expected(whadmin, device["key"], "registration", rid)["registration"]["bins"][0]["id"]
    rl = {"client_line_id": f"l-{TAG}-r1", "epc": epc(3333), "bin_id": rbin, "owner_entity_id": ENT, "product_id": world["product"]["id"],
          "qty": 10, "unit": "meter"}
    r3, _ = batch(whadmin, device["key"], "registration", rid, lines=[rl, {**rl, "client_line_id": f"l-{TAG}-r2"}], op_id=opw)
    res3 = {i["ref"]: i for i in r3.json()["items"]}
    assert res3[f"l-{TAG}-r1"]["result"] == "saved" and res3[f"l-{TAG}-r1"]["tag_state"] == "read"
    assert res3[f"l-{TAG}-r2"]["result"] == "conflict", "EPC yang sama di baris lain ditolak (keunikan layanan asal)"


# ── 9. Registri perangkat: profil, jejak pakai, cabut & aktifkan ────────────────────────────────────
def test_device_registry(world, device, admin, whadmin):
    p = requests.put(f"{HH}/devices/{device['id']}/profile", headers=admin, timeout=30,
                     json={"profile": {"rfid": {"power_dbm": 18}, "trigger": {"mode": "toggle"}}})
    assert p.status_code == 200 and p.json()["profile"]["rfid"]["power_dbm"] == 18, p.text
    bad = requests.put(f"{HH}/devices/{device['id']}/profile", headers=admin, timeout=30, json={"profile": {"rfid": {"power_dbm": 99}}})
    assert bad.status_code == 400 and code_of(bad) == "PROFILE_INVALID"
    cfg = requests.get(f"{HH}/device/config", headers={"X-Device-Key": device["key"]}, timeout=30).json()
    assert cfg["profile"]["rfid"]["power_dbm"] == 18 and cfg["profile"]["trigger"]["mode"] == "toggle"
    lst = requests.get(f"{HH}/devices", headers=whadmin, timeout=30).json()["devices"]
    me = next(d for d in lst if d["id"] == device["id"])
    assert me["has_api_key"] and "api_key_hash" not in me and me["operator"]
    act = requests.get(f"{HH}/devices/{device['id']}/activity", headers=whadmin, timeout=30).json()
    assert act["operator_sessions"] and any(r["scope"] == "batch" for r in act["requests"]) and act["tag_writes"]
    assert requests.post(f"{HH}/devices/{device['id']}/revoke", headers=whadmin, json={"reason": "x"}, timeout=30).status_code == 400
    rv = requests.post(f"{HH}/devices/{device['id']}/revoke", headers=whadmin, json={"reason": "unit uji hilang"}, timeout=30)
    assert rv.status_code == 200 and rv.json()["enabled"] is False and not rv.json()["has_api_key"]
    assert requests.get(f"{HH}/device/config", headers={"X-Device-Key": device["key"]}, timeout=30).status_code == 401, "key dicabut"
    assert not DB.handheld_operator_sessions.find_one({"device_id": device["id"], "ended_at": None})
    en = requests.post(f"{HH}/devices/{device['id']}/enable", headers=admin, timeout=30).json()
    assert en["enabled"] and en["needs_new_key"]
    rot = requests.post(f"{HH}/devices/{device['id']}/rotate-key", headers=admin, timeout=30).json()
    assert requests.get(f"{HH}/device/config", headers={"X-Device-Key": rot["api_key"]}, timeout=30).status_code == 200
    DB.rfid_devices.update_one({"id": DEV_B}, {"$set": {"enabled": False}})
    off = requests.get(f"{HH}/device/config", headers={"X-Device-Key": KEY_B}, timeout=30)
    assert off.status_code == 403 and code_of(off) == "DEVICE_DISABLED"
    assert requests.post(f"{HH}/devices", headers=whadmin, json={"name": "x", "warehouse_id": WH_A}, timeout=30).status_code == 403
