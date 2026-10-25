"""Keputusan pemilik 26 Okt 2026 (audit UI tahap 2) — wilayah D2 (stok & penjualan).

Bagian 1 (selalu jalan, TANPA DB): fungsi murni K-05 — moving average, persentil per satuan, SKU baru,
tidak bergerak, tren, coverage — dan simulator Pusat Pengaturan.

Bagian 2 (butuh DB uji TERSENDIRI — ditulisi & DIHAPUS isinya): uji service langsung (tanpa HTTP).
    cd /app/backend && DB_NAME=d2_audit_uat26 python -m pytest tests/test_uat26_d2_decisions.py -p no:randomly -n 0 -q
Tanpa DB_NAME=d2_audit_* bagian 2 dilewati.
"""
import os
from datetime import datetime, timedelta, timezone

import pytest

from services.stock_analytics_service import (
    CLASS_LABEL, class_from_percentile, classify_velocity, percentile_ranks, trend_of,
)

DB_TESTS = os.environ.get("DB_NAME", "").startswith("d2_audit")
needs_db = pytest.mark.skipif(not DB_TESTS, reason="Set DB_NAME=d2_audit_* — uji ini menulis ke DB uji sendiri.")


# ═══════════════════════════════════════════════════════════════════════════════
#  Bagian 1 — K-05 fungsi murni (data sintetis)
# ═══════════════════════════════════════════════════════════════════════════════
def _item(pid, unit="yard", sold=0.0, trend=None, on_hand=10.0, age=400):
    return {"product_id": pid, "unit": unit, "sold_window": sold,
            "sold_trend": (sold / 3 if trend is None else trend), "on_hand": on_hand, "age_days": age}


def _classify(items, **kw):
    args = {"window_days": 90, "best_pct": 20, "slow_pct": 20, "new_age_days": 90, "trend_days": 30}
    args.update(kw)
    return classify_velocity(items, **args)


def test_k05_percentile_mid_rank_and_ties():
    assert percentile_ranks({}) == {}
    assert percentile_ranks({"a": 5}) == {"a": 50.0}                 # satu SKU → tengah, bukan 0/100
    r = percentile_ranks({"a": 1, "b": 2, "c": 3, "d": 4, "e": 5})
    assert r == {"a": 10.0, "b": 30.0, "c": 50.0, "d": 70.0, "e": 90.0}
    tie = percentile_ranks({"a": 3, "b": 3, "c": 3})
    assert set(tie.values()) == {50.0}                                # kembar → sama, adil


def test_k05_class_thresholds():
    assert class_from_percentile(90, 20, 20) == "best"
    assert class_from_percentile(80, 20, 20) == "normal"              # batas: > 100 − 20
    assert class_from_percentile(50, 20, 20) == "normal"
    assert class_from_percentile(20, 20, 20) == "normal"              # batas: < 20
    assert class_from_percentile(10, 20, 20) == "slow"
    assert class_from_percentile(70, 40, 10) == "best"                # persen bisa diatur


def test_k05_ten_skus_twenty_percent_each_end():
    items = [_item(f"p{i}", sold=i * 9) for i in range(1, 11)]       # MA 0,1 … 1,0 per hari
    res = _classify(items)
    cls = {pid: r["classification"] for pid, r in res.items()}
    assert [p for p, c in cls.items() if c == "best"] == ["p9", "p10"]
    assert [p for p, c in cls.items() if c == "slow"] == ["p1", "p2"]
    assert sum(1 for c in cls.values() if c == "normal") == 6
    assert res["p10"]["ma_daily"] == 1.0 and res["p10"]["percentile"] == 95.0
    assert res["p10"]["rank_group_size"] == 10 and res["p10"]["rank_unit"] == "yard"


def test_k05_units_ranked_separately():
    # 3 SKU yard sangat laku (ratusan/hari) TIDAK boleh membuat SKU kg (puluhan/hari) jadi slow moving.
    items = [_item("y1", "yard", 9000), _item("y2", "yard", 18000), _item("y3", "yard", 27000),
             _item("k1", "kg", 90), _item("k2", "kg", 180), _item("k3", "KG", 270)]
    res = _classify(items)
    assert res["k3"]["classification"] == "best" and res["y3"]["classification"] == "best"
    assert res["k1"]["classification"] == "slow" and res["y1"]["classification"] == "slow"
    assert res["k3"]["rank_unit"] == "kg" and res["k3"]["rank_group_size"] == 3   # satuan dinormalkan huruf kecil
    assert res["y2"]["rank_group_size"] == 3


def test_k05_new_sku_excluded_from_ranking():
    items = [_item("old1", sold=90), _item("old2", sold=180), _item("old3", sold=270),
             _item("baru_laku", sold=9000, age=10), _item("baru_diam", sold=0, age=5)]
    res = _classify(items)
    assert res["baru_laku"]["classification"] == "new" and res["baru_laku"]["percentile"] is None
    assert res["baru_diam"]["classification"] == "new"                # stok baru tanpa jual BUKAN tidak bergerak
    assert res["old3"]["classification"] == "best"                    # SKU baru yang laris tidak menggeser peringkat
    assert res["old3"]["rank_group_size"] == 3
    # 0 = tanpa kelas Baru; umur tak diketahui = diperingkat seperti biasa
    res0 = _classify([_item("x", sold=10, age=1)], new_age_days=0)
    assert res0["x"]["classification"] == "normal"
    resn = _classify([_item("y", sold=10, age=None)])
    assert resn["y"]["classification"] == "normal"


def test_k05_dead_stock_vs_nothing():
    items = [_item("diam", sold=0, on_hand=50), _item("kosong", sold=0, on_hand=0), _item("laku", sold=90)]
    res = _classify(items)
    assert res["diam"]["classification"] == "dead"                    # punya stok, tak terjual dalam jendela
    assert res["diam"]["coverage_days"] is None and res["diam"]["percentile"] is None
    assert res["kosong"]["classification"] is None                    # tanpa stok & tanpa jual → tidak ditampilkan
    assert res["laku"]["rank_group_size"] == 1                        # tidak bergerak TIDAK ikut peringkat


def test_k05_trend_and_coverage():
    assert trend_of(0, 5) is None
    assert trend_of(1.0, 1.5) == "naik" and trend_of(1.0, 0.5) == "turun" and trend_of(1.0, 1.05) == "stabil"
    res = _classify([_item("a", sold=90, trend=60, on_hand=500)])     # MA90 1/hari, MA30 2/hari
    a = res["a"]
    assert a["ma_daily"] == 1.0 and a["ma_trend_daily"] == 2.0 and a["trend"] == "naik"
    assert a["coverage_days"] == 500.0                                # coverage tetap dihitung, kelas tidak berubah
    assert a["classification"] == "normal"


def test_k05_settings_change_classes():
    items = [_item(f"p{i}", sold=i * 9) for i in range(1, 11)]
    res = _classify(items, best_pct=40, slow_pct=10)
    assert sum(1 for r in res.values() if r["classification"] == "best") == 4
    assert sum(1 for r in res.values() if r["classification"] == "slow") == 1
    # window berbeda → MA berbeda, peringkat sama
    res30 = _classify(items, window_days=30, trend_days=30)
    assert res30["p10"]["ma_daily"] == 3.0 and res30["p10"]["classification"] == "best"


def test_k05_simulator_matches_engine():
    from services.config_simulator import _stock_class
    base = {"inventory.stock_analytics.velocity_window_days": 90, "inventory.stock_analytics.best_seller_pct": 20,
            "inventory.stock_analytics.slow_moving_pct": 20, "inventory.stock_analytics.new_sku_age_days": 90}
    assert _stock_class(base, {"sold_qty": 900, "percentile": 85, "age_days": 365})["result"] == "Kelas: Best seller"
    assert _stock_class(base, {"sold_qty": 900, "percentile": 10, "age_days": 365})["result"] == "Kelas: Slow moving"
    assert _stock_class(base, {"sold_qty": 0, "percentile": 50, "age_days": 365})["result"] == "Kelas: Tidak bergerak"
    assert _stock_class(base, {"sold_qty": 900, "percentile": 99, "age_days": 10})["result"] == "Kelas: Baru"
    assert set(CLASS_LABEL) == {"best", "normal", "slow", "dead", "new"}


def test_k05_registry_keys():
    import importlib
    importlib.import_module("config_catalog_core")   # mendaftarkan entri registry
    import config_registry as reg
    from services.config_service import DEFAULT_GLOBAL_SETTINGS
    sa = DEFAULT_GLOBAL_SETTINGS["inventory"]["stock_analytics"]
    for leaf in ("velocity_window_days", "best_seller_pct", "slow_moving_pct", "new_sku_age_days"):
        e = reg.get(f"inventory.stock_analytics.{leaf}")
        assert e and e["status"] == "active" and e["group"] == "stok-satuan", leaf
        assert e["default"] == sa[leaf], leaf
    for leaf in ("fast_max_days", "slow_max_days"):
        assert reg.get(f"inventory.stock_analytics.{leaf}")["status"] == "not_used"
        assert leaf not in sa


# ═══════════════════════════════════════════════════════════════════════════════
#  Bagian 2 — uji service (DB uji tersendiri)
# ═══════════════════════════════════════════════════════════════════════════════
def _run(coro):
    from tests._shared_loop import run
    return run(coro)


def _iso(days=0):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


@pytest.fixture
def clean_db():
    if not DB_TESTS:
        pytest.skip("butuh DB_NAME=d2_audit_*")
    from db import db

    async def wipe():
        for c in await db.list_collection_names():
            await db[c].delete_many({})
    _run(wipe())
    yield db
    _run(wipe())


def _so(sid, items, days=-10, status="confirmed", order_type="regular", entity="ent_A"):
    return {"id": sid, "entity_id": entity, "status": status, "order_type": order_type, "created_at": _iso(days),
            "items": [{"product_id": p, "quantity": q, "base_quantity": q} for p, q in items]}


def _roll(rid, pid, length, wh="wh1", days=-400, status="available"):
    return {"id": rid, "roll_no": rid.upper(), "product_id": pid, "owner_entity_id": "ent_A", "warehouse_id": wh,
            "status": status, "length_remaining": length, "unit_cost": 10, "base_unit_cost": 10,
            "created_at": _iso(days)}


@needs_db
def test_k05_service_so_based_classes(clean_db, monkeypatch):
    db = clean_db
    from services import stock_analytics_service as sas

    async def settings(_e=None):
        return {}
    monkeypatch.setattr(sas, "resolve_list_scope", lambda c, q, ctx, e=None: dict(q))
    monkeypatch.setattr(sas, "get_effective_settings", settings)

    async def go():
        old = _iso(-400)
        await db.products.insert_many([
            {"id": f"y{i}", "sku": f"Y{i}", "name": f"Yard {i}", "base_unit": "yard", "category": "A",
             "created_at": old} for i in range(1, 6)] + [
            {"id": "k1", "sku": "K1", "name": "Kg 1", "base_unit": "kg", "category": "B", "created_at": old},
            {"id": "k2", "sku": "K2", "name": "Kg 2", "base_unit": "kg", "category": "B", "created_at": old},
            {"id": "k3", "sku": "K3", "name": "Kg 3", "base_unit": "kg", "category": "B", "created_at": old},
            {"id": "diam", "sku": "D", "name": "Diam", "base_unit": "yard", "category": "A", "created_at": old},
            {"id": "baru", "sku": "N", "name": "Baru", "base_unit": "yard", "category": "A",
             "created_at": _iso(-10)}])
        await db.warehouses.insert_many([{"id": "wh1", "name": "Gudang 1"}, {"id": "wh2", "name": "Gudang 2"}])
        stock = ["y1", "y2", "y3", "y4", "k1", "k2", "k3", "diam", "baru"]          # y5 = laku tapi stok habis
        await db.inventory_balances.insert_many([
            {"product_id": p, "warehouse_id": ("wh2" if p == "y4" else "wh1"), "owner_entity_id": "ent_A",
             "on_hand_qty": 100} for p in stock])
        await db.inventory_rolls.insert_many([
            _roll(f"r_{p}", p, 100, wh=("wh2" if p == "y4" else "wh1"),
                  days=(-5 if p == "baru" else -400)) for p in stock])
        await db.sales_orders.insert_many([
            _so("s1", [("y1", 90), ("y2", 180), ("y3", 270), ("y4", 360), ("y5", 450)], days=-40),
            _so("s2", [("k1", 9), ("k2", 18), ("k3", 27)]),
            _so("s3", [("baru", 900)], days=-3),
            _so("x_batal", [("diam", 999)], status="cancelled"),           # SO mati tidak dihitung
            _so("x_draf", [("diam", 999)], status="draft"),
            _so("x_sample", [("diam", 999)], order_type="sample"),         # pesanan sample dipisah
            _so("x_lama", [("diam", 999)], days=-200),                      # di luar jendela 90 hari
            _so("s4", [("y5", 30)], days=-5)])                               # MA 30 hari untuk tren
        full = await sas.compute_stock_analytics(None)
        wh2 = await sas.compute_stock_analytics(None, warehouse_id="wh2")
        catb = await sas.compute_stock_analytics(None, category="B")
        return full, wh2, catb
    full, wh2, catb = _run(go())
    rows = {r["product_id"]: r for r in full["rows"]}
    assert rows["y5"]["classification"] == "best" and rows["y5"]["stock_out"] is True   # stok habis tetap tampil
    assert rows["y1"]["classification"] == "slow"
    assert rows["y3"]["classification"] == "normal"
    assert rows["k3"]["classification"] == "best" and rows["k1"]["classification"] == "slow"   # per satuan
    assert rows["k2"]["classification"] == "normal"
    assert rows["diam"]["classification"] == "dead" and rows["diam"]["sold_qty_window"] == 0
    assert rows["diam"]["last_sale_date"] is not None                  # SO lama tetap jadi "jual terakhir"
    assert rows["baru"]["classification"] == "new" and rows["baru"]["percentile"] is None
    assert rows["y5"]["sold_qty_window"] == 480.0 and rows["y5"]["sold_qty_trend"] == 30.0
    assert rows["y4"]["days_of_supply"] == 25.0                         # 100 ÷ (360/90)
    s = full["summary"]["by_class"]
    assert (s["best"]["count"], s["slow"]["count"], s["dead"]["count"], s["new"]["count"]) == (2, 2, 1, 1)
    assert {g["unit"]: g["ranked"] for g in full["method"]["rank_groups"]} == {"kg": 3, "yard": 5}
    # saringan gudang/kategori hanya menyaring tampilan — kelas tidak berubah
    assert [(r["product_id"], r["classification"]) for r in wh2["rows"]] == [("y4", "normal")]
    assert {r["product_id"]: r["classification"] for r in catb["rows"]} == {"k1": "slow", "k2": "normal", "k3": "best"}
    assert full["thresholds"]["best_seller_pct"] == 20 and full["thresholds"]["velocity_window_days"] == 90


# ── K-04 — definisi tunggal "Tersedia" & "Stok rendah" ───────────────────────────
def test_k04_is_low_stock_rule():
    from services.stock_availability import LOW_STOCK_QTY, is_low_stock
    assert LOW_STOCK_QTY == 100
    assert is_low_stock(1) and is_low_stock(99.9)
    assert not is_low_stock(0) and not is_low_stock(100) and not is_low_stock(-5)   # 0 = habis, bukan rendah


@needs_db
def test_k04_single_available_definition(clean_db):
    db = clean_db
    from services import fulfillment_service as fs
    from services import stock_availability as sav

    async def go():
        await db.warehouses.insert_many([{"id": "w1", "name": "G1"}, {"id": "w2", "name": "G2"}])
        await db.products.insert_many([{"id": "pA", "sku": "A", "name": "Kain A", "base_unit": "yard", "status": "active"},
                                       {"id": "pB", "sku": "B", "name": "Kain B", "base_unit": "kg", "status": "active"}])
        await db.inventory_balances.insert_many([
            {"product_id": "pA", "warehouse_id": "w1", "owner_entity_id": "E1", "available_qty": 60, "on_hand_qty": 80},
            {"product_id": "pA", "warehouse_id": "w2", "owner_entity_id": "E1", "available_qty": 30, "on_hand_qty": 30},
            {"product_id": "pA", "warehouse_id": "w_dihapus", "owner_entity_id": "E1", "available_qty": 29,
             "on_hand_qty": 29},                                                  # saldo yatim (G4-24)
            {"product_id": "pB", "warehouse_id": "w1", "owner_entity_id": "E1", "available_qty": 500, "on_hand_qty": 500},
            {"product_id": "pB", "warehouse_id": "w1", "owner_entity_id": "E2", "available_qty": 40, "on_hand_qty": 40}])
        await db.material_reservations.insert_one({"status": "active", "product_id": "pA", "owner_entity_id": "E1",
                                                   "qty": 20})                    # cadangan makloon
        by_e1 = await sav.available_by_product("E1")
        low_e1 = await sav.low_stock_summary(["E1"])
        low_all = await sav.low_stock_summary(None)
        low_none = await sav.low_stock_summary([])
        board = await fs.build_supply_index(["pA"], registered_only=True)
        board_raw = await fs.build_supply_index(["pA"])
        return by_e1, low_e1, low_all, low_none, board, board_raw
    by_e1, low_e1, low_all, low_none, board, board_raw = _run(go())
    assert by_e1 == {"pA": 70.0, "pB": 500.0}                 # 60 + 30 − 20 makloon; yatim tidak ikut
    assert board["pA"]["E1"]["available"] == 70.0            # papan stok (router) = definisi yang sama
    assert board_raw["pA"]["E1"]["available"] == 99.0        # pemanggil lama tanpa saringan gudang tetap
    assert [(i["product_id"], i["entity_id"], i["available"]) for i in low_e1["items"]] == [("pA", "E1", 70.0)]
    assert low_all["count"] == 2 and low_all["items"][0]["entity_id"] == "E2"   # per produk PER badan usaha
    assert low_none["count"] == 0                              # cakupan kosong ≠ semua


# ── B1 — SPK "Diterima seluruhnya" dengan roll ditahan ───────────────────────────
def _spk(kind="makloon_output", lines=None):
    return {"id": "ins1", "number": "KSC/INS-00072", "kind": kind, "entity_id": "E1", "status": "in_progress",
            "lines": lines or [], "history": []}


@needs_db
def test_b1_warn_default_records_held_rolls(clean_db):
    db = clean_db
    from services import inspection_service as svc

    async def go():
        await db.inventory_rolls.insert_many([
            {"id": "r1", "roll_no": "RL-00001", "status": "available"},
            {"id": "r5", "roll_no": "RL-00005", "status": "quarantine",
             "qc_hold_pending": {"reason": "QC 4-point GAGAL — SPK KSC/INS-00080"}}])
        await db.inspections.insert_one(_spk(lines=[
            {"id": "l1", "roll_id": "r1", "roll_no": "RL-00001", "inspected_at": "2026-10-26T01:00:00+00:00"},
            {"id": "l5", "roll_id": "r5", "roll_no": "RL-00005", "inspected_at": "2026-10-26T01:00:00+00:00"}]))
        held = await svc.held_rolls(await svc._load("ins1"))
        policy = await svc.accept_all_hold_action("E1")
        out = await svc.finish("ins1", "terima", "", {"name": "Uji"})
        return held, policy, out
    held, policy, out = _run(go())
    assert policy == "peringatkan"                                     # bawaan = peringatan
    assert [h["roll_no"] for h in held] == ["RL-00005"]                # tahanan QC 4-point yang menunggu karantina
    assert out["status"] == "done" and out["decision"] == "terima"
    assert out["accepted_with_held_rolls"][0]["roll_no"] == "RL-00005"
    assert "1 roll tetap ditahan" in out["history"][-1]["label"]


@needs_db
def test_b1_block_setting_rejects_accept_all(clean_db):
    db = clean_db
    from services import inspection_service as svc

    async def go():
        await db.system_settings.insert_one({"scope": "global", "qc": {"accept_all_with_hold_action": "blokir"}})
        await db.inspections.insert_one(_spk(kind="qc_4point", lines=[
            {"id": "l1", "roll_id": "r1", "roll_no": "RL-00001", "inspected_at": "x", "qc_at": "x"},
            {"id": "l2", "roll_id": "r2", "roll_no": "RL-00002", "inspected_at": "x", "qc_at": "x",
             "decision": "tolak"}]))
        err = None
        try:
            await svc.finish("ins1", "terima", "", {"name": "Uji"})
        except svc.InspectionError as exc:
            err = str(exc)
        doc = await svc._load("ins1")
        meta = await svc.meta("E1")
        return err, doc, meta
    err, doc, meta = _run(go())
    assert err and "RL-00002" in err and "Diterima seluruhnya" in err
    assert doc["status"] == "in_progress"                              # tidak ada yang berubah
    assert meta["policy"]["accept_all_with_hold_action"] == "blokir"


# ── B3 — grade per roll di timeline retur ───────────────────────────────────────
@needs_db
def test_b3_timeline_grade_per_roll(clean_db):
    from services import return_timeline_service as rts
    ret = {"id": "ret1", "number": "SRET-00005", "items": [
        {"product_name": "Kain", "unit": "yard", "roll_ids": ["ra", "rb"], "roll_qtys": {"ra": 60.5, "rb": 20},
         "inspection": {"grade": "B", "roll_results": {"ra": {"grade": "A", "condition": "ok", "points": 2.0},
                                                       "rb": {"grade": "B", "condition": "minor", "points": 6.0}}}},
        {"product_name": "Lama", "unit": "yard", "roll_ids": ["rc"], "inspection": {"grade": "C"}}]}
    rows = {r["roll_id"]: r for r in _run(rts._roll_rows(ret))}
    assert (rows["ra"]["qc_grade"], rows["ra"]["qc_grade_source"], rows["ra"]["qc_line_grade"]) == ("A", "roll", "B")
    assert (rows["rb"]["qc_grade"], rows["rb"]["qc_condition"]) == ("B", "minor")
    assert (rows["rc"]["qc_grade"], rows["rc"]["qc_grade_source"]) == ("C", "line")   # QC lama: grade baris, bertanda
