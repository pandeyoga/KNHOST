"""FIX-7 (audit 9 Nov 2026, sisa FIX-5 §8) — performa baca & masa simpan log.

Uji di sini GAGAL di kode sebelum FIX-7 dan LULUS sesudahnya, kecuali yang ditandai "penjaga" (kesetaraan hasil,
lulus di keduanya):
  A. cari roll `?q=`: tiap cabang ber-index (tanpa pindai penuh roll), hasil = definisi lama (regex "mengandung" 6 field +
     nama/SKU produk; kutip = persis) [penjaga], EPC persis menemukan roll (baru);
  B. papan stok: backorder dibaca SEKALI (dulu satu kueri `sales_orders` per segmen saldo), angka ATP/permintaan tertunda
     sama dengan `pending_backorder_qty` per segmen [penjaga];
  C. pohon stok: dihitung dengan agregat Mongo (dulu semua roll gudang dikirim ke backend), angka per bin = aturan
     `_bucket` per roll [penjaga];
  D. dasbor: HPP (WAC) tidak dihitung untuk peran yang tidak menerimanya; admin = satu pembacaan roll; nilai sama
     dengan `wac_for_product` [penjaga];
  E. mutasi petugas berpagar lokasi: index (warehouse_id, timestamp) dipakai;
  F. masa simpan log teknis: job `log_retention` + setelan registri; jejak audit tidak disentuh;
  G. index `id` (`uq_id`) di koleksi bisnis lain.

Jalankan (kontainer backend, DB salinan data acuan, backend berjalan di 8001):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_fix7_perf_sisa.py
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # backend berkas uji ini (dasar/baru)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
T = "TFIX7"


def _pw():
    if os.environ.get("KN_DEMO_PASS"):
        return os.environ["KN_DEMO_PASS"]
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    m = re.search(r"Login demo:.*?/\s*`([^`]+)`", open(os.path.join(root, "AGENTS.md"), encoding="utf-8").read())
    return m.group(1)


def _login(email):
    try:
        r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": _pw()}, timeout=30)
    except requests.RequestException:
        pytest.skip("backend tidak berjalan")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def sales():
    return _login("sales@kainnusantara.id")


class Profiler:
    """Profil Mongo level 2 selama satu blok → operasi per koleksi (koleksi profil diperbesar agar tidak terpotong)."""

    def __enter__(self):
        DB.command({"profile": 0})
        DB.system.profile.drop()
        DB.create_collection("system.profile", capped=True, size=64 * 1024 * 1024)
        DB.command({"profile": 2})
        self.t0 = datetime.now(timezone.utc) - timedelta(seconds=1)
        return self

    def __exit__(self, *exc):
        DB.command({"profile": 0})
        self.ops = list(DB.system.profile.find({"ts": {"$gte": self.t0}}))
        return False

    def on(self, coll, op=None):
        ns = f"{DB.name}.{coll}"
        return [o for o in self.ops if o.get("ns") == ns and (op is None or o.get("op") == op)]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    DB.command({"profile": 0})
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_{T}_"}})
    DB.sys_scheduler_runs.delete_many({"job_id": {"$regex": f"^{T}_"}})
    DB.sys_wa_outbox.delete_many({"id": {"$regex": f"^wa_{T}_"}})
    DB.sys_digest_claims.delete_many({"key": {"$regex": f"^{T}:"}})
    DB.audit_logs.delete_many({"id": {"$regex": f"^aud_{T}_"}})
    DB.rfid_tags.delete_many({"id": {"$regex": f"^tag_{T}_"}})


# ── A. cari roll ──────────────────────────────────────────────────────────────────────────────────────────────
FIELDS = ("roll_no", "lot", "dye_lot", "batch", "grade", "consignor_ref")
OWNER = "ent_ksc"   # cakupan PT eksplisit (daftar roll memakai PT aktif bila tanpa saringan)


def _expected_ids(q):
    """Definisi LAMA (sebelum FIX-7): `$or` regex i pada 6 field + product_id dari nama/SKU produk."""
    qs = q.strip()
    pat = f"^{re.escape(qs[1:-1].strip())}$" if len(qs) >= 3 and qs[0] == qs[-1] == '"' else re.escape(qs)
    rx = {"$regex": pat, "$options": "i"}
    ql = qs.lower()
    pids = [p["id"] for p in DB.products.find({}, {"_id": 0, "id": 1, "sku": 1, "name": 1})
            if ql in (p.get("name") or "").lower() or ql in (p.get("sku") or "").lower()]
    ors = [{f: rx} for f in FIELDS] + ([{"product_id": {"$in": pids}}] if pids else [])
    return {r["id"] for r in DB.inventory_rolls.find({"$or": ors, "owner_entity_id": OWNER}, {"_id": 0, "id": 1})}


def _search_ids(admin, q):
    r = requests.get(f"{BASE}/inventory/rolls", params={"q": q, "limit": 5000, "owner_entity_id": OWNER},
                     headers=admin, timeout=120)
    assert r.status_code == 200, r.text
    return {x["id"] for x in r.json()}


def _queries():
    roll = DB.inventory_rolls.find_one({"roll_no": {"$regex": "^RL-"}, "lot": {"$nin": [None, ""]}, "owner_entity_id": OWNER},
                                       {"_id": 0, "roll_no": 1, "lot": 1, "product_id": 1, "batch": 1})
    prod = DB.products.find_one({"id": roll["product_id"]}, {"_id": 0, "name": 1, "sku": 1})
    return [roll["roll_no"], roll["roll_no"][-4:], f'"{roll["roll_no"]}"', roll["lot"], (roll.get("batch") or "SA-")[:6],
            (prod.get("sku") or "")[:7], (prod.get("name") or "x").split()[0], "lot-26", "TIDAK-ADA-ROLL-INI", "(+",
            roll["roll_no"].lower()]


@pytest.mark.parametrize("i", range(11))
def test_roll_search_same_result_as_old_definition(admin, i):
    """Penjaga — hasil cari = definisi lama untuk nomor tepat/sebagian/kutip, lot, batch, SKU, nama, huruf kecil,
    karakter khusus, tanpa hasil: jumlah (mode berhalaman) selalu, himpunan id bila ≤ 5.000."""
    q = _queries()[i]
    exp = _expected_ids(q)
    r = requests.get(f"{BASE}/inventory/rolls", params={"q": q, "page": 1, "page_size": 20, "owner_entity_id": OWNER},
                     headers=admin, timeout=120)
    assert r.status_code == 200 and r.json()["total"] == len(exp), (q, r.json().get("total"), len(exp))
    if len(exp) <= 5000:
        assert _search_ids(admin, q) == exp, q


def test_roll_search_paged_total_matches(admin):
    """Penjaga — mode berhalaman: `total` = jumlah definisi lama."""
    q = _queries()[3]   # lot
    r = requests.get(f"{BASE}/inventory/rolls", params={"q": q, "page": 1, "page_size": 20, "owner_entity_id": OWNER},
                     headers=admin, timeout=120)
    assert r.status_code == 200
    assert r.json()["total"] == len(_expected_ids(q))


def test_roll_search_indexes_exist_and_no_full_scan(admin):
    """Dulu: `$or` 6 regex tanpa index → pindai penuh koleksi roll dua kali (hitung + halaman). Kini tiap cabang
    ber-index (lot/batch/grade/consignor_ref baru) → dokumen roll yang diperiksa ≈ hasil, bukan 46.700 × 2."""
    names = set(DB.inventory_rolls.index_information())
    for f in ("lot", "batch", "grade", "consignor_ref"):
        assert f"kn_{f}_1" in names, f
    roll = DB.inventory_rolls.find_one({"roll_no": {"$regex": "^RL-"}}, {"_id": 0, "roll_no": 1})
    with Profiler() as prof:
        r = requests.get(f"{BASE}/inventory/rolls", params={"q": roll["roll_no"], "page": 1, "page_size": 50},
                         headers=admin, timeout=120)
    assert r.status_code == 200 and r.json()["total"] >= 1
    ops = [o for o in prof.on("inventory_rolls") if roll["roll_no"] in str(o.get("command"))]
    assert ops
    examined = sum(int(o.get("docsExamined") or 0) for o in ops)
    collscans = [o for o in ops if "COLLSCAN" in str(o.get("planSummary"))]
    assert not collscans, [o.get("planSummary") for o in collscans]
    assert examined < 1000, f"dokumen roll diperiksa {examined}"


def test_roll_search_by_epc_finds_roll(admin):
    """Baru — EPC (heksadesimal) yang dipindai/ditempel ke kotak cari menemukan roll pemilik tag."""
    roll = DB.inventory_rolls.find_one({"roll_no": {"$regex": "^RL-"}, "owner_entity_id": OWNER},
                                       {"_id": 0, "id": 1, "owner_entity_id": 1})
    epc = "E28011700000020F" + "7A1B2C3D"
    DB.rfid_tags.insert_one({"id": f"tag_{T}_1", "epc": epc, "roll_id": roll["id"], "status": "active",
                             "owner_entity_id": roll.get("owner_entity_id"), "created_at": datetime.now(timezone.utc).isoformat()})
    assert roll["id"] in _search_ids(admin, epc)
    assert roll["id"] in _search_ids(admin, epc.lower())


# ── B. papan stok ─────────────────────────────────────────────────────────────────────────────────────────────
def _bo_product():
    b = DB.inventory_balances.find_one({"available_qty": {"$gt": 0}}, {"_id": 0, "product_id": 1, "warehouse_id": 1,
                                                                        "owner_entity_id": 1})
    return b["product_id"], b["warehouse_id"], b["owner_entity_id"]


@pytest.fixture(scope="module")
def backorders():
    pid, wid, ent = _bo_product()
    other = DB.warehouses.find_one({"id": {"$ne": wid}, "active": {"$ne": False}}, {"_id": 0, "id": 1})["id"]
    rows = [  # (entitas SO, gudang SO, [(gudang backorder, qty, status)])
        (ent, wid, [(wid, 12.5, "open"), ("", 3.25, "open"), (wid, 99, "fulfilled")]),
        (ent, "", [("", 7.0, "open"), (other, 4.0, "open")]),
        (ent, other, [(None, 2.0, "open")]),
        ("ent_kanda", wid, [(wid, 5.5, "open")]),
    ]
    for i, (e, so_wh, bos) in enumerate(rows):
        DB.sales_orders.insert_one({
            "id": f"so_{T}_{i}", "number": f"SO-{T}-{i}", "entity_id": e, "status": "waiting_stock",
            "has_backorder": True, "warehouse_id": so_wh, "created_at": datetime.now(timezone.utc).isoformat(),
            "backorders": [{"product_id": pid, "warehouse_id": w, "backorder_qty": q, "status": st} for w, q, st in bos]})
    yield pid
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_{T}_"}})


ACTIVE_BO = ["waiting_stock", "reserved", "waiting_approval", "approved", "confirmed", "partially_picked",
             "partially_shipped"]


def _old_pending(pid, eid, wid=None, include_unassigned=True):
    """Orakel independen = isi `pending_backorder_qty` SEBELUM FIX-7 (satu kueri per panggilan), disalin apa adanya."""
    q = {"has_backorder": True, "backorders.product_id": pid, "status": {"$in": ACTIVE_BO}}
    if eid:
        q["entity_id"] = eid
    total = 0.0
    for so in DB.sales_orders.find(q, {"_id": 0, "backorders": 1, "warehouse_id": 1}):
        for bo in so.get("backorders", []) or []:
            if bo.get("product_id") != pid or bo.get("status") == "fulfilled":
                continue
            bo_wh = bo.get("warehouse_id") or so.get("warehouse_id") or ""
            if wid and bo_wh not in ("", wid):
                continue
            if wid and not include_unassigned and not bo_wh:
                continue
            total += float(bo.get("backorder_qty", 0) or 0)
    return round(total, 2)


def test_backorder_function_matches_old_algorithm(backorders):
    """Penjaga — `pending_backorder_qty` (kini lewat `BackorderIndex`) = algoritma lama untuk semua kombinasi PT ×
    gudang × tanpa-gudang dari data uji (backorder bergudang, tanpa gudang, gudang SO, `fulfilled`, PT lain)."""
    from services.atp_policy import pending_backorder_qty
    pid = backorders
    whs = {None, ""} | {w["id"] for w in DB.warehouses.find({}, {"_id": 0, "id": 1})}
    for eid in ("ent_ksc", "ent_kanda", "ent_cst", ""):
        for wid in whs:
            for inc in (True, False):
                got = run(pending_backorder_qty(pid, eid, wid, include_unassigned=inc))
                assert got == _old_pending(pid, eid, wid, inc), (eid, wid, inc)


def test_status_board_pending_demand_equals_per_segment_formula(admin, backorders):
    """Penjaga — permintaan tertunda & ATP per PT dan per gudang = algoritma lama `pending_backorder_qty` (orakel
    independen `_old_pending`) yang dulu dipanggil per segmen."""
    from services.atp_policy import compute_atp
    pid = backorders
    r = requests.get(f"{BASE}/inventory/status-board", params={"product_id": pid}, headers=admin, timeout=120)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    ents = rows[0]["by_entity"]
    assert ents, "produk uji tidak punya saldo"
    seen_nonzero = False
    for e in ents:
        exp_e = _old_pending(pid, e["entity_id"])
        assert e["pending_demand"] == exp_e, e["entity_id"]
        assert e["atp"] == compute_atp(e["available"], e["incoming"], exp_e)
        seen_nonzero |= exp_e > 0
        for w in e["by_warehouse"]:
            exp_w = _old_pending(pid, e["entity_id"], w["warehouse_id"], include_unassigned=False)
            assert w["pending_demand"] == exp_w, (e["entity_id"], w["warehouse_id"])
    assert seen_nonzero


def test_status_board_reads_backorders_once(admin, backorders):
    """Dulu satu kueri `sales_orders` (backorder) per segmen saldo + per (produk, PT): ratusan kueri per buka papan."""
    with Profiler() as prof:
        r = requests.get(f"{BASE}/inventory/status-board", headers=admin, timeout=300)
    assert r.status_code == 200
    bo_q = [o for o in prof.on("sales_orders") if "has_backorder" in str(o.get("command", {}).get("filter", {}))]
    assert 1 <= len(bo_q) <= 2, f"kueri backorder: {len(bo_q)}"


# ── C. pohon stok ─────────────────────────────────────────────────────────────────────────────────────────────
def _busiest_wh():
    g = list(DB.inventory_rolls.aggregate([{"$match": {"status": "available", "length_remaining": {"$gt": 0}}},
                                           {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}},
                                           {"$sort": {"n": -1}}, {"$limit": 1}]))
    return g[0]["_id"]


def _walk(node, out):
    if node.get("kind") in ("bin", "unassigned", "orphan", "transit"):
        out[node["id"]] = node
    for c in node.get("children") or []:
        _walk(c, out)


def test_stock_tree_bins_equal_per_roll_rule(admin):
    """Penjaga — angka tiap bin / belum ditempatkan / dalam perjalanan = aturan `_bucket` per roll (dihitung ulang di
    uji dari roll mentah)."""
    from services.location_stock_tree import _bucket, BUCKETS
    from services.roll_service import PHYSICAL_STATUS_TO_BUCKET, TRANSIT_STATUS_TO_BUCKET
    wid = _busiest_wh()
    r = requests.get(f"{BASE}/warehouses/{wid}/stock-tree", headers=admin, timeout=120)
    assert r.status_code == 200, r.text
    tree = r.json()["tree"]
    nodes = {}
    _walk(tree, nodes)
    exp = {}
    bins = {n for n in nodes if not n.startswith(f"{wid}:")}
    q = {"warehouse_id": wid, "length_remaining": {"$gt": 0},
         "status": {"$in": list(PHYSICAL_STATUS_TO_BUCKET) + list(TRANSIT_STATUS_TO_BUCKET)}}
    n_rolls = 0
    for x in DB.inventory_rolls.find(q, {"_id": 0}):
        n_rolls += 1
        if x.get("status") in TRANSIT_STATUS_TO_BUCKET:
            key = f"{wid}:transit"
        elif not x.get("bin_id"):
            key = f"{wid}:unassigned"
        else:
            key = x["bin_id"] if x["bin_id"] in bins else f"{wid}:orphan"
        e = exp.setdefault(key, {"rolls": 0, "by_unit": {}})
        e["rolls"] += 1
        u = e["by_unit"].setdefault(x.get("unit") or "?", {b: 0.0 for b in BUCKETS} | {"total": 0.0})
        for b, qty in _bucket(x):
            u[b] += qty
            u["total"] += qty
    assert tree["rolls"] == n_rolls
    for key, e in exp.items():
        assert key in nodes, key
        assert nodes[key]["rolls"] == e["rolls"], key
        for unit, vals in e["by_unit"].items():
            for b, v in vals.items():
                assert abs(nodes[key]["by_unit"][unit][b] - v) < 0.01, (key, unit, b)


def test_stock_tree_aggregated_in_mongo(admin):
    """Dulu SEMUA roll fisik gudang dibaca ke backend lalu dijumlah per roll; kini `$group` di Mongo — dokumen yang
    dikirim ke backend ≤ jumlah kelompok (bin × satuan × PT × jenis), jauh di bawah jumlah roll."""
    wid = _busiest_wh()
    n_rolls = DB.inventory_rolls.count_documents({"warehouse_id": wid, "length_remaining": {"$gt": 0}})
    with Profiler() as prof:
        r = requests.get(f"{BASE}/warehouses/{wid}/stock-tree", headers=admin, timeout=120)
    assert r.status_code == 200
    ops = [o for o in prof.on("inventory_rolls") if wid in str(o.get("command"))]
    returned = sum(int(o.get("nreturned") or 0) for o in ops)
    assert any(o.get("op") == "command" and "aggregate" in (o.get("command") or {}) for o in ops)
    assert returned < max(50, n_rolls // 4), f"dokumen roll dikirim {returned} dari {n_rolls}"


# ── D. dasbor ─────────────────────────────────────────────────────────────────────────────────────────────────
def _wac_queries(prof):
    """Kueri rumus WAC: roll per produk dengan status HIDUP (daftar status fisik, memuat 'damaged')."""
    out = []
    for o in prof.on("inventory_rolls"):
        flt = str((o.get("command") or {}).get("filter", {}))
        if "product_id" in flt and "damaged" in flt and o.get("op") == "query":
            out.append(o)
    return out


def test_dashboard_sales_no_wac_queries(sales):
    """Peran tanpa hak biaya: `hpp` dibuang `strip_cost_fields` → dulu tetap dihitung = satu kueri roll per produk."""
    with Profiler() as prof:
        r = requests.get(f"{BASE}/dashboard", headers=sales, timeout=300)
    assert r.status_code == 200
    assert all("hpp" not in p for p in r.json()["products"])
    assert len(_wac_queries(prof)) == 0, len(_wac_queries(prof))


def test_dashboard_admin_wac_single_read_and_same_values(admin):
    """Admin: HPP tetap ada, nilainya = `wac_for_product` per produk [penjaga nilai], dibaca sekali (dulu per produk)."""
    from services.costing_service import wac_for_product
    with Profiler() as prof:
        r = requests.get(f"{BASE}/dashboard", headers=admin, timeout=300)
    assert r.status_code == 200
    prods = r.json()["products"]
    assert prods and all("hpp" in p and "hpp_source" in p for p in prods)
    n_q = len(_wac_queries(prof))
    for p in prods[:60]:
        w = run(wac_for_product(p["id"], product=p, use_cache=False))
        assert p["hpp"] == float(w.get("wac") or 0) and p["hpp_source"] == w.get("source", ""), p["id"]
    assert n_q <= 2, f"kueri WAC per produk: {n_q} untuk {len(prods)} produk"


# ── E. mutasi petugas berpagar lokasi ─────────────────────────────────────────────────────────────────────────
def test_movements_location_fence_uses_warehouse_timestamp_index():
    assert "kn_warehouse_id_1__timestamp_-1" in DB.inventory_movements.index_information()
    whs = [w["id"] for w in DB.warehouses.find({"site_id": {"$exists": True}}, {"_id": 0, "id": 1}).limit(3)]
    ex = DB.command("explain", {"find": "inventory_movements",
                                "filter": {"owner_entity_id": {"$in": ["ent_ksc", "ent_kanda", None, ""]},
                                           "warehouse_id": {"$in": whs}},
                                "sort": {"timestamp": -1}, "limit": 100}, verbosity="queryPlanner")
    assert "kn_warehouse_id_1__timestamp_-1" in str(ex["queryPlanner"]["winningPlan"])


# ── F. masa simpan log teknis ─────────────────────────────────────────────────────────────────────────────────
def _ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def test_log_retention_job_registered_and_settings_in_registry():
    from services import scheduler_service as ss
    import config_registry as cr
    assert "log_retention" in ss.JOB_MAP
    keys = {"ops.log_retention_mode", "ops.scheduler_runs_retention_days", "ops.scheduler_runs_failed_retention_days",
            "ops.wa_outbox_retention_days", "ops.digest_claims_retention_days"}
    reg = getattr(cr, "_REGISTRY", {})
    assert keys <= set(reg), keys - set(reg)
    assert reg["ops.log_retention_mode"]["default"] == "delete"
    assert reg["ops.scheduler_runs_retention_days"]["default"] == 30


def test_log_retention_deletes_old_technical_logs_only():
    from services import log_retention as lr
    j1, j2 = f"{T}_job_a", f"{T}_job_b"
    DB.sys_scheduler_runs.insert_many([
        {"id": f"srun_{T}_1", "job_id": j1, "status": "success", "started_at": _ago(40)},   # dihapus
        {"id": f"srun_{T}_2", "job_id": j1, "status": "success", "started_at": _ago(5)},    # disimpan (baru)
        {"id": f"srun_{T}_3", "job_id": j1, "status": "failed", "started_at": _ago(40)},    # gagal < 90 → disimpan
        {"id": f"srun_{T}_4", "job_id": j1, "status": "failed", "started_at": _ago(120)},   # gagal > 90 → dihapus
        {"id": f"srun_{T}_5", "job_id": j2, "status": "success", "started_at": _ago(200)},  # TERAKHIR job b → disimpan
        {"id": f"srun_{T}_6", "job_id": j2, "status": "success", "started_at": _ago(300)},  # dihapus
    ])
    DB.sys_wa_outbox.insert_many([
        {"id": f"wa_{T}_1", "status": "sent", "created_at": _ago(100)},     # dihapus
        {"id": f"wa_{T}_2", "status": "queued", "created_at": _ago(100)},   # antre → disimpan
        {"id": f"wa_{T}_3", "status": "failed", "created_at": _ago(10)},    # baru → disimpan
    ])
    DB.sys_digest_claims.insert_many([{"key": f"{T}:old", "created_at": _ago(45)}, {"key": f"{T}:new", "created_at": _ago(1)}])
    DB.audit_logs.insert_one({"id": f"aud_{T}_1", "action": "x", "timestamp": _ago(4000)})

    dry = run(lr.run(mode="dry_run"))
    assert dry["deleted"] == 0 and dry["candidates"] >= 5
    assert DB.sys_scheduler_runs.count_documents({"job_id": {"$in": [j1, j2]}}) == 6

    res = run(lr.run(mode="delete"))
    assert res["deleted"] >= 5
    left = {d["id"] for d in DB.sys_scheduler_runs.find({"job_id": {"$in": [j1, j2]}}, {"_id": 0, "id": 1})}
    assert left == {f"srun_{T}_2", f"srun_{T}_3", f"srun_{T}_5"}, left
    assert {d["id"] for d in DB.sys_wa_outbox.find({"id": {"$regex": f"^wa_{T}_"}})} == {f"wa_{T}_2", f"wa_{T}_3"}
    assert [d["key"] for d in DB.sys_digest_claims.find({"key": {"$regex": f"^{T}:"}})] == [f"{T}:new"]
    assert DB.audit_logs.count_documents({"id": f"aud_{T}_1"}) == 1   # jejak audit tidak disentuh
    with pytest.raises(AssertionError):
        run(lr._delete_batched("audit_logs", {"id": "x"}, 1))


# ── G. index `id` koleksi bisnis lain ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("coll", ["journal_entries", "notifications", "credit_notes", "supplier_contracts", "md_specs",
                                  "entity_prices", "vendor_bills", "store_credit_ledger"])
def test_id_index_on_more_business_collections(coll):
    info = DB[coll].index_information()
    assert "uq_id" in info, sorted(info)
    assert info["uq_id"].get("unique") is True
    one = DB[coll].find_one({"id": {"$gt": ""}}, {"_id": 0, "id": 1})
    if one:
        ex = DB.command("explain", {"find": coll, "filter": {"id": one["id"]}}, verbosity="queryPlanner")
        assert "uq_id" in str(ex["queryPlanner"]["winningPlan"])


def test_existing_id_index_respected_not_duplicated():
    """`product_templates` sudah punya index unik `{id: 1}` sendiri (`catalog_parent_id`) → tidak dibuat `uq_id` kedua."""
    from indexes import ensure_id_index
    if "catalog_parent_id" not in DB.product_templates.index_information():
        pytest.skip("index katalog tidak ada di DB ini")
    if "uq_id" in DB.product_templates.index_information():
        DB.product_templates.drop_index("uq_id")   # DB dibangun kode versi awal FIX-7
    assert run(ensure_id_index("product_templates")) == "existed"
    assert "uq_id" not in DB.product_templates.index_information()
