"""PREP-C (keputusan pemilik 8 Nov 2026: K-GDG-01…11, K-RFID-04/10) — fondasi gudang yang bisa dikonfigurasi,
draf putaway otomatis, routing inspeksi, dan tiba bertahap per trip.

Cakupan: profil gedung (peran inspection/material, gate_config + perangkat + tata letak, mode stok, bentuk simpan,
aturan artikel/PT, bentuk simpan zona, bawaan shared), gedung tunggal → stored, routing inspeksi, draf otomatis
sesudah QC / GRN / tutup SPK (idempoten), ubah/terbitkan/batal draf, tiba multi-trip + penutupan, `confirm_arrival_trip`
dari gate, celah izin accept exception, roll ditahan, status 0 tiba, izin HTTP. Residu: dokumen baru dibuang (sidik
`_id`), gudang dipulihkan, saldo & nomor urut dipulihkan.
"""
import os
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/") + "/api"
PWD = "demo12345"
ENT = "ent_ksc"
TAG = uuid.uuid4().hex[:6].upper()
NEW = ["inventory_rolls", "inventory_movements", "inventory_lots", "journal_entries", "audit_logs", "notifications",
       "inspections", "wms_tasks", "rfid_tags", "rfid_devices", "config_values", "doc_refs", "qc_inspections",
       "putaway_orders", "warehouses", "location_migrations", "backorders"]
_seq = {"n": 0}


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": PWD}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT})
    return s


@pytest.fixture(scope="module")
def mdb():
    return _db()


@pytest.fixture(scope="module", autouse=True)
def env(mdb):
    stock = snapshot_stock(["inventory_balances", "number_sequences"])
    assert stock.get("__enabled__"), "restore harus aktif (DB uji)"
    ids = snapshot_new_ids(NEW)
    whs = list(mdb.warehouses.find({}))
    yield
    purge_new_ids(ids, verbose=False)
    for w in whs:
        mdb.warehouses.replace_one({"_id": w["_id"]}, w)
    restore_stock(stock)


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def wh_staff():
    return _login("warehouse@kainnusantara.id")


@pytest.fixture(scope="module")
def W(mdb):
    """Gudang acuan Rancamalang (transit, simpan, retur) + Soreang."""
    tr = mdb.warehouses.find_one({"code": "RCM-TRANSIT"}, {"_id": 0})
    if not tr:
        pytest.skip("data acuan tidak punya RCM-TRANSIT")
    by = {w["code"]: w for w in mdb.warehouses.find({"site_id": tr["site_id"]}, {"_id": 0})}
    srg = mdb.warehouses.find_one({"code": "SRG-01"}, {"_id": 0})
    return {"transit": tr, "retur": by.get("RCM-RETUR"), "srg": srg,
            "storage": [w for c, w in sorted(by.items()) if "storage" in (w.get("roles") or []) and c != "RCM-RETUR"]}


def seed(mdb, W, n, *, status="available", stage="received_transit", **extra):
    """Salin roll tersedia milik KSC dari gudang simpan Rancamalang ke RCM-TRANSIT (id/nomor baru)."""
    src = list(mdb.inventory_rolls.find({"warehouse_id": {"$in": [w["id"] for w in W["storage"]]}, "status": "available",
                                         "owner_entity_id": ENT, "grade": {"$in": ["A", None, ""]},
                                         "length_remaining": {"$gt": 1}, "length_reserved": {"$in": [0, None]}},
                                        {"_id": 0}).limit(16))
    if not src:
        pytest.skip("tidak ada roll sumber")
    out = []
    for i in range(n):
        _seq["n"] += 1
        r = dict(src[(_seq["n"]) % len(src)])
        for k in ("inspection", "hold", "qc_hold_pending", "four_point_pending", "last_pa_landed", "transfer_ref"):
            r.pop(k, None)
        r.update({"id": f"roll_TEST_PREPC_{TAG}_{_seq['n']}", "roll_no": f"TPC{TAG}{_seq['n']}",
                  "warehouse_id": W["transit"]["id"], "status": status, "bin_id": None, "rfid_tag_id": None,
                  "journey": {"stage": stage, "routing": "store"}, "active_movement": None, "grade": "A",
                  "length_reserved": 0, "length_reservations": [], "earmarked_for": None, "reserved_ref": None,
                  "qc_task_id": None, **extra})
        mdb.inventory_rolls.insert_one(dict(r))
        out.append(r)
    return out


def verify_labels(s, W, rolls):
    r = s.post(f"{BASE}/putaway-orders/verify-labels", json={"warehouse_id": W["transit"]["id"],
                                                             "codes": [x["roll_no"] for x in rolls]}, timeout=60)
    assert r.status_code == 200, r.text
    assert len(r.json()["verified"]) == len(rolls), r.text


def drafts_of(mdb, roll_ids):
    return list(mdb.putaway_orders.find({"status": "draft", "items.roll_id": {"$in": roll_ids}}, {"_id": 0}))


def auto(roll_ids, trig):
    from services import inbound_qc_common as iqc
    return run(iqc.auto_draft_after_release(roll_ids, {"type": "test", "id": trig}, "Penguji"))


# ─── 1. Profil gedung ────────────────────────────────────────────────────────
def test_validate_profile_unit():
    from fastapi import HTTPException
    from services import warehouse_profile_service as whp
    p = whp.validate_profile({"roles": ["Inspection", "material", "storage"], "stock_mode": "quantity",
                              "storage_form": "floor",
                              "storage_rules": {"mode": "combined", "template_ids": ["t1", "t1", " "],
                                                "owner_entity_ids": ["ent_ksc"]}})
    assert p["roles"] == ["inspection", "material", "storage"]
    assert p["storage_rules"]["template_ids"] == ["t1"] and p["storage_rules"]["owner_entity_ids"] == ["ent_ksc"]
    assert p["stock_mode"] == "quantity" and p["storage_form"] == "floor"
    for bad in ({"roles": ["qc"]}, {"stock_mode": "liter"}, {"storage_form": "kolam"},
                {"gate_config": {"has_gate": False, "confirm_mode": "gate"}},
                {"gate_config": {"has_gate": True, "pairs": [{"layout": "miring"}]}},
                {"gate_config": {"has_gate": True, "pairs": [{"in_device_id": "d1", "out_device_id": "d1"}]}}):
        with pytest.raises(HTTPException):
            whp.validate_profile(bad)
    legacy = whp.normalize_gate_config({"physical_gate": True})   # data lama dibaca
    assert legacy["has_gate"] and legacy["physical_gate"] and legacy["confirm_mode"] == "gate"
    assert whp.normalize_gate_config({})["confirm_mode"] == "handheld"
    pol = whp.gate_policy_of({"id": "w", "stock_mode": "quantity", "gate_config": {"has_gate": True}})
    assert pol["effective_mode"] == "manual" and pol["gate_applies"] is False and pol["notes"]


def test_create_default_shared_and_gate_profile(admin, mdb, W):
    r = admin.post(f"{BASE}/warehouses", json={"code": f"TPC-{TAG}", "name": f"Gedung Uji {TAG}", "city": "Bandung",
                                               "bin_code": f"TPC{TAG}-01", "bin_capacity": 10}, timeout=60)
    assert r.status_code == 200, r.text
    wh = r.json()
    assert wh["sharing_mode"] == "shared" and wh.get("entity_ids") == []       # K-GDG-07
    wid = wh["id"]
    d_in, d_out, d_other = f"rdev_TPC_{TAG}_in", f"rdev_TPC_{TAG}_out", f"rdev_TPC_{TAG}_x"
    mdb.rfid_devices.insert_many([
        {"id": d_in, "code": f"TPC-{TAG}-IN", "type": "gate", "direction": "in", "warehouse_id": wid},
        {"id": d_out, "code": f"TPC-{TAG}-OUT", "type": "gate", "direction": "out", "warehouse_id": wid},
        {"id": d_other, "code": f"TPC-{TAG}-X", "type": "gate", "direction": "in", "warehouse_id": W["transit"]["id"]}])
    gc = {"has_gate": True, "confirm_mode": "gate",
          "pairs": [{"name": "Pintu Utara", "in_device_id": d_in, "out_device_id": d_out,
                     "layout": "berdampingan_sekat", "clear_zone_note": "jarak rak 3 m (belum diukur)"}]}
    r = admin.patch(f"{BASE}/warehouses/{wid}", json={"data": {
        "site_id": W["transit"]["site_id"], "roles": ["storage", "material"], "gate_config": gc,
        "stock_mode": "roll_tagged", "storage_form": "floor"}}, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gate_config"]["physical_gate"] is True and body["gate_config"]["pairs"][0]["id"]
    assert body["storage_form"] == "floor" and body["roles"] == ["material", "storage"]
    pol = admin.get(f"{BASE}/warehouses/{wid}/gate-policy", timeout=30).json()
    assert pol["effective_mode"] == "gate" and pol["gate_ready"] is True and pol["needs_arbitration"] is True
    assert pol["device_ids_in"] == [d_in] and pol["device_ids_out"] == [d_out]
    for bad_gc in ({**gc, "pairs": [{"in_device_id": d_out}]},                 # arah salah
                   {**gc, "pairs": [{"in_device_id": d_other}]},               # gedung lain
                   {**gc, "pairs": [{"in_device_id": "rdev_tidak_ada"}]},
                   {"has_gate": False, "confirm_mode": "gate"}):
        r = admin.patch(f"{BASE}/warehouses/{wid}", json={"data": {"gate_config": bad_gc}}, timeout=30)
        assert r.status_code == 400, (bad_gc, r.text)
    r = admin.patch(f"{BASE}/warehouses/{wid}", json={"data": {"stock_mode": "quantity"}}, timeout=30)
    assert r.status_code == 200
    pol = admin.get(f"{BASE}/warehouses/{wid}/gate-policy", timeout=30).json()
    assert pol["effective_mode"] == "manual" and pol["gate_applies"] is False
    assert admin.patch(f"{BASE}/warehouses/{wid}", json={"data": {"stock_mode": "liter"}}, timeout=30).status_code == 400
    assert admin.patch(f"{BASE}/warehouses/{wid}", json={"data": {"storage_form": "kolam"}}, timeout=30).status_code == 400
    # data lama {physical_gate} tetap terbaca sebagai gate
    mdb.warehouses.update_one({"id": wid}, {"$set": {"gate_config": {"physical_gate": True}, "stock_mode": "roll_tagged"}})
    pol = admin.get(f"{BASE}/warehouses/{wid}/gate-policy", timeout=30).json()
    assert pol["has_gate"] is True and pol["confirm_mode"] == "gate" and pol["gate_ready"] is False and pol["notes"]


def test_rules_template_owner_and_zone_form(admin, mdb, W):
    from services import placement_rules as pr
    wid = W["storage"][0]["id"]
    tpl = mdb.product_templates.find_one({}, {"_id": 0, "id": 1})["id"]
    rules = {"mode": "combined", "template_ids": [tpl], "owner_entity_ids": ["ent_kanda"]}
    r = admin.patch(f"{BASE}/warehouses/{wid}", json={"data": {"storage_rules": rules}}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["storage_rules"]["template_ids"] == [tpl]
    for bad in ({**rules, "template_ids": ["ptpl_tidak_ada"]}, {**rules, "owner_entity_ids": ["ent_tidak_ada"]}):
        assert admin.patch(f"{BASE}/warehouses/{wid}", json={"data": {"storage_rules": bad}}, timeout=30).status_code == 400
    wh = mdb.warehouses.find_one({"id": wid}, {"_id": 0})
    v = run(pr.warehouse_violations(wh, {"owner_entity_id": ENT, "grade": "A"}, {"template_id": "lain", "name": "Kain X"}))
    assert any("Artikel" in x for x in v) and any("tidak diizinkan" in x and "milik" in x for x in v)
    assert not run(pr.warehouse_violations(wh, {"owner_entity_id": "ent_kanda", "grade": "A"}, {"template_id": tpl}))
    assert not run(pr.warehouse_violations(wh, {"owner_entity_id": ENT}, {"template_id": "lain"}, attrs=False))
    # bentuk simpan per zona (K-GDG-05) — arti bin tetap, hanya informasi efektif
    zones = wh.get("zones") or []
    assert zones, "gudang acuan tanpa zona"
    zones[0]["storage_form"] = "floor"
    zones[0]["rules"] = {"owner_entity_ids": [ENT, ENT]}
    r = admin.put(f"{BASE}/warehouses/{wid}/structure", json={"zones": zones, "migration_reason": "uji PREP-C"}, timeout=60)
    assert r.status_code == 200, r.text
    saved = mdb.warehouses.find_one({"id": wid}, {"_id": 0})
    assert saved["zones"][0]["storage_form"] == "floor" and saved["zones"][0]["rules"]["owner_entity_ids"] == [ENT]
    node = pr.flatten_nodes(saved)[0]
    assert pr.effective_view(saved, node)["storage_form"] == "floor"
    zones[0]["storage_form"] = "kolam"
    r = admin.put(f"{BASE}/warehouses/{wid}/structure", json={"zones": zones, "migration_reason": "uji PREP-C"}, timeout=60)
    assert r.status_code == 400
    mdb.warehouses.update_one({"id": wid}, {"$set": {k: W["storage"][0].get(k) for k in ("storage_rules", "zones")}})


def test_return_journey_qc_area_roles():
    from services import return_journey_service as rj
    assert "inspection" in rj.QC_ROLES and "return" in rj.QC_ROLES and "qc" not in rj.QC_ROLES


# ─── 2. Gedung tunggal (P9-K1) ───────────────────────────────────────────────
def test_single_building_starts_stored(mdb):
    from services import inbound_qc_common as iqc
    assert iqc.stage_for_roles(["storage", "transit", "central_inbound"]) == "stored"
    assert iqc.stage_for_roles(["material"]) == "stored"
    assert iqc.stage_for_roles(["transit", "central_inbound", "staging"]) == "received_transit"
    assert iqc.stage_for_roles(["inspection"]) == "received_transit"
    assert iqc.stage_for_roles([]) == "received_transit"
    wid = f"wh_TPC_{TAG}_single"
    mdb.warehouses.insert_one({"id": wid, "code": f"TPCS-{TAG}", "name": "Gedung Tunggal Uji",
                               "roles": ["storage", "transit", "central_inbound"], "active": True})
    assert run(iqc.initial_journey_stage(wid)) == "stored"


# ─── 3. Routing inspeksi + draf otomatis (idempoten) ─────────────────────────
def test_auto_draft_routes_inspection_and_is_idempotent(admin, mdb, W):
    assert W["retur"], "data acuan tanpa RCM-RETUR"
    r = admin.patch(f"{BASE}/warehouses/{W['retur']['id']}", json={"data": {"roles": ["inspection", "return", "storage"]}},
                    timeout=30)
    assert r.status_code == 200, r.text
    rolls = seed(mdb, W, 3)
    ids = [x["id"] for x in rolls]
    mdb.inspections.insert_one({"id": f"ins_TPC_{TAG}", "kind": "qc_4point", "status": "assigned", "entity_id": ENT,
                                "number": f"TPC-INS-{TAG}", "lines": [{"roll_id": ids[0]}]})
    res = auto(ids, f"route-{TAG}")
    assert not res.get("error"), res
    drafts = drafts_of(mdb, ids)
    by_roll = {it["roll_id"]: d for d in drafts for it in d["items"]}
    assert set(by_roll) == set(ids)
    assert by_roll[ids[0]]["to_warehouse_id"] == W["retur"]["id"] and by_roll[ids[0]]["purpose"] == "inspection"
    assert next(i for i in by_roll[ids[0]]["items"] if i["roll_id"] == ids[0])["inspection_requested"] is True
    for rid in ids[1:]:
        assert by_roll[rid]["to_warehouse_id"] != W["retur"]["id"] and by_roll[rid]["purpose"] == "storage"
        assert by_roll[rid]["status"] == "draft" and by_roll[rid]["created_by"].startswith("Sistem")
    # draf TIDAK mengklaim roll (stok transit tetap bisa dijual — K-GDG-09)
    assert all(mdb.inventory_rolls.find_one({"id": rid})["active_movement"] is None for rid in ids)
    n = len(drafts)
    assert auto(ids, f"route-{TAG}")["drafts"] == []          # retry pemicu yang sama
    assert auto(ids, f"route2-{TAG}")["drafts"] == []         # pemicu lain: roll sudah di draf hidup
    assert len(drafts_of(mdb, ids)) == n
    # tanpa gedung inspeksi di lokasi → perilaku lama (gudang simpan)
    admin.patch(f"{BASE}/warehouses/{W['retur']['id']}", json={"data": {"roles": ["return", "storage"]}}, timeout=30)
    extra = seed(mdb, W, 1)
    mdb.inspections.update_one({"id": f"ins_TPC_{TAG}"}, {"$push": {"lines": {"roll_id": extra[0]["id"]}}})
    auto([extra[0]["id"]], f"route3-{TAG}")
    d = drafts_of(mdb, [extra[0]["id"]])
    assert len(d) == 1 and d[0]["purpose"] == "storage" and d[0]["to_warehouse_id"] != W["retur"]["id"]


def test_auto_draft_config_off_and_held_skipped(admin, mdb, W):
    import config_registry
    e = config_registry.get("putaway.auto_draft")
    assert e and e["default"] is True and "entity" in e["scopes"]
    off = seed(mdb, W, 1)
    mdb.config_values.insert_one({"id": f"cfgv_TPC_{TAG}", "key": "putaway.auto_draft", "scope_type": "entity",
                                  "scope_id": ENT, "value": False, "effective_from": "2020-01-01T00:00:00+00:00",
                                  "created_at": "2020-01-01T00:00:00+00:00"})
    try:
        res = auto([off[0]["id"]], f"off-{TAG}")
        assert res["drafts"] == [] and ENT in res["disabled_entities"]
    finally:
        mdb.config_values.delete_one({"id": f"cfgv_TPC_{TAG}"})
    held = seed(mdb, W, 1, inspection={"hold": {"held": True, "reason": "beda shade"}})
    res = auto([held[0]["id"]], f"held-{TAG}")
    assert res["drafts"] == [] and res["skipped"] == 1
    # celah 27 Okt — roll DITAHAN tidak boleh masuk PA manual
    verify_labels(admin, W, held)
    r = admin.post(f"{BASE}/putaway-orders", json={"from_warehouse_id": W["transit"]["id"],
                                                   "to_warehouse_id": W["storage"][0]["id"],
                                                   "roll_ids": [held[0]["id"]]}, timeout=60)
    assert r.status_code == 400 and "DITAHAN" in r.text, r.text


def test_qc_decision_triggers_draft(monkeypatch, mdb, W):
    import services.backorder_service as bo
    from services import qc_service

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(bo, "auto_fulfill_backorders", _noop)
    task_id = f"wms_TPC_{TAG}_qc"
    rolls = seed(mdb, W, 2, status="quarantine", qc_task_id=task_id)
    task = {"id": task_id, "flow_type": "inbound", "status": "qc_pending", "product_id": rolls[0]["product_id"],
            "warehouse_id": W["transit"]["id"], "owner_entity_id": ENT, "entity_id": ENT, "qc_plan": {"mode": "none"},
            "po_number": f"TPC-QC-{TAG}", "unit": rolls[0].get("unit", "meter")}
    for r in rolls:   # keputusan QC per tugas: satu produk
        mdb.inventory_rolls.update_one({"id": r["id"]}, {"$set": {"product_id": task["product_id"]}})
    mdb.wms_tasks.insert_one(dict(task))
    total = round(sum(float(r["length_remaining"]) for r in rolls), 2)
    res = run(qc_service.process_qc_decision(task, total, 0, "damaged", "uji PREP-C", {"name": "Penguji", "id": "u"}))
    assert res["accepted_qty"] > 0 and res["putaway_draft"]["drafts"], res.get("putaway_draft")
    ids = [r["id"] for r in rolls]
    d = drafts_of(mdb, ids)
    assert d and d[0]["auto"]["trigger"]["type"] == "qc_decision" and d[0]["auto"]["trigger"]["id"] == task_id
    from services import inbound_qc_common as iqc
    again = run(iqc.auto_draft_after_release(ids, {"type": "qc_decision", "id": task_id}, "Penguji"))
    assert again["drafts"] == [] and len(drafts_of(mdb, ids)) == len(d)


def test_grn_without_qc_triggers_draft(monkeypatch, mdb, W):
    import services.backorder_service as bo
    from services import inbound_qc_common as iqc
    from services.inbound_complete_service import complete_task
    from schemas_purchasing import GRCompletePayload, GRRollLine

    async def _noop(*a, **k):
        return None

    async def _no_qc(_e):
        return False
    monkeypatch.setattr(bo, "auto_fulfill_backorders", _noop)
    monkeypatch.setattr(iqc, "qc_on_receipt_enabled", _no_qc)
    src = seed(mdb, W, 1)[0]
    prod = mdb.products.find_one({"id": src["product_id"]}, {"_id": 0, "base_unit": 1}) or {}
    unit = prod.get("base_unit", "meter")
    task_id = f"wms_TPC_{TAG}_grn"
    mdb.wms_tasks.insert_one({"id": task_id, "flow_type": "inbound", "status": "put_away", "product_id": src["product_id"],
                              "warehouse_id": W["transit"]["id"], "quantity": 30.0, "unit": unit, "entity_id": ENT,
                              "po_number": f"TPC-GRN-{TAG}", "lot": f"LOT-TPC-{TAG}"})
    payload = GRCompletePayload(rolls=[GRRollLine(length=10, dye_lot="DL1"), GRRollLine(length=20, dye_lot="DL1")],
                                supplier_lot=f"SL-{TAG}")
    out = run(complete_task(task_id, payload, {"name": "Penguji", "id": "u"}))
    assert out["status"] == "completed", out.get("status")
    ids = [r["id"] for r in out["created_rolls"]]
    assert all(mdb.inventory_rolls.find_one({"id": i})["journey"]["stage"] == "received_transit" for i in ids)
    assert out["putaway_draft"]["drafts"], out["putaway_draft"]
    d = drafts_of(mdb, ids)
    assert d and d[0]["auto"]["trigger"]["type"] == "grn"


# ─── 4. Ubah / terbitkan / batalkan draf ─────────────────────────────────────
def test_draft_edit_publish_split_and_cancel(admin, mdb, W):
    rolls = seed(mdb, W, 2)
    ids = [r["id"] for r in rolls]
    auto(ids, f"pub-{TAG}")
    drafts = drafts_of(mdb, ids)
    assert len(drafts) == 1 and drafts[0]["item_count"] == 2, drafts
    did = drafts[0]["id"]
    det = admin.get(f"{BASE}/putaway-orders/{did}", timeout=30).json()
    assert det["ready_count"] == 0 and all(not i["ready"] and i["block_reason"] for i in det["items"])
    assert det["destination_options"]
    r = admin.post(f"{BASE}/putaway-orders/{did}/publish", json={}, timeout=60)
    assert r.status_code == 400 and "Belum ada roll" in r.text
    verify_labels(admin, W, rolls[:1])
    r = admin.post(f"{BASE}/putaway-orders/{did}/publish", json={}, timeout=60)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "PA_DRAFT_NOT_READY"
    r = admin.post(f"{BASE}/putaway-orders/{did}/publish", json={"split_unready": True}, timeout=60)
    assert r.status_code == 200, r.text
    pa = r.json()
    assert pa["status"] == "open" and [i["roll_id"] for i in pa["items"]] == [ids[0]]
    assert pa["items"][0]["epc"] == rolls[0]["roll_no"].upper()
    assert mdb.inventory_rolls.find_one({"id": ids[0]})["active_movement"]["id"] == did
    rest = drafts_of(mdb, [ids[1]])
    assert len(rest) == 1 and rest[0]["split_from"] == did
    rid = rest[0]["id"]
    # ubah tujuan / isi
    other = next(w for w in W["storage"] if w["id"] != rest[0]["to_warehouse_id"])
    r = admin.patch(f"{BASE}/putaway-orders/{rid}/draft", json={"to_warehouse_id": other["id"]}, timeout=30)
    assert r.status_code == 200 and r.json()["to_warehouse_id"] == other["id"] and r.json()["purpose"] == "storage"
    if W["srg"]:
        r = admin.patch(f"{BASE}/putaway-orders/{rid}/draft", json={"to_warehouse_id": W["srg"]["id"]}, timeout=30)
        assert r.status_code == 400 and "lokasi yang sama" in r.text
    r = admin.patch(f"{BASE}/putaway-orders/{rid}/draft", json={"remove_roll_ids": [ids[1]]}, timeout=30)
    assert r.status_code == 400 and "kosong" in r.text
    # roll di draf tidak boleh dibuatkan PA manual (satu roll satu antrean)
    verify_labels(admin, W, rolls[1:])
    r = admin.post(f"{BASE}/putaway-orders", json={"from_warehouse_id": W["transit"]["id"],
                                                   "to_warehouse_id": other["id"], "roll_ids": [ids[1]]}, timeout=60)
    assert r.status_code == 400 and "draf" in r.text
    assert admin.post(f"{BASE}/putaway-orders/{rid}/cancel-draft", json={"reason": "x"}, timeout=30).status_code == 400
    r = admin.post(f"{BASE}/putaway-orders/{rid}/cancel-draft", json={"reason": "salah tujuan, buat ulang"}, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert admin.post(f"{BASE}/putaway-orders/{rid}/publish", json={}, timeout=30).status_code == 400
    sugg = admin.get(f"{BASE}/putaway-orders/suggest", params={"from_warehouse_id": W["transit"]["id"]}, timeout=60).json()
    listed = {x["id"] for g in sugg["groups"] for x in g["rolls"]}
    assert ids[1] in listed and ids[0] not in listed


# ─── 5. Tiba bertahap per trip + penutupan ───────────────────────────────────
def _open_pa(admin, mdb, W, n):
    rolls = seed(mdb, W, n)
    verify_labels(admin, W, rolls)
    r = admin.post(f"{BASE}/putaway-orders", json={"from_warehouse_id": W["transit"]["id"],
                                                   "to_warehouse_id": W["storage"][0]["id"],
                                                   "roll_ids": [x["id"] for x in rolls]}, timeout=60)
    assert r.status_code == 200, r.text
    pa = r.json()
    assert admin.post(f"{BASE}/putaway-orders/{pa['id']}/dispatch", timeout=60).status_code == 200
    return pa, rolls


def test_multi_trip_arrival_and_close_return(admin, mdb, W):
    pa, rolls = _open_pa(admin, mdb, W, 3)
    url = f"{BASE}/putaway-orders/{pa['id']}"
    r = admin.post(f"{url}/arrival-trips", json={"epcs": [rolls[0]["roll_no"]], "client_trip_id": "T1"}, timeout=60)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["status"] == "partially_received" and o["btg_number"] and o["trip"]["arrived_roll_nos"] == [rolls[0]["roll_no"]]
    roll0 = mdb.inventory_rolls.find_one({"id": rolls[0]["id"]})
    assert roll0["warehouse_id"] == W["storage"][0]["id"] and roll0["journey"]["stage"] == "stored"
    assert mdb.inventory_rolls.find_one({"id": rolls[1]["id"]})["status"] == "in_transit_transfer"   # tetap menunggu
    dup = admin.post(f"{url}/arrival-trips", json={"epcs": [rolls[0]["roll_no"]], "client_trip_id": "T1"}, timeout=60).json()
    assert dup["duplicate_trip"] is True and len(dup["arrival_trips"]) == 1
    r = admin.post(f"{url}/arrival-trips", json={"epcs": [rolls[0]["roll_no"], rolls[1]["roll_no"], "BUKANROLLINI"]},
                   timeout=60)
    o = r.json()
    assert o["status"] == "partially_received" and o["trip"]["arrived_roll_nos"] == [rolls[1]["roll_no"]]
    assert o["trip"]["already_roll_nos"] == [rolls[0]["roll_no"]] and "BUKANROLLINI" in o["trip"]["unknown_epcs"]
    assert o["btg_number"] == pa.get("btg_number") or o["btg_number"]
    assert mdb.inventory_movements.count_documents({"roll_id": rolls[0]["id"], "reference_id": pa["id"]}) == 2
    assert admin.post(f"{url}/close", json={"action": "return_transit", "reason": "x"}, timeout=30).status_code == 400
    r = admin.post(f"{url}/close", json={"action": "return_transit", "reason": "roll ketiga tertinggal di transit"},
                   timeout=60)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["status"] == "completed" and o["arrived_count"] == 2 and o["returned_count"] == 1 and o["closed_remaining"]
    roll2 = mdb.inventory_rolls.find_one({"id": rolls[2]["id"]})
    assert roll2["warehouse_id"] == W["transit"]["id"] and roll2["status"] == "available"
    assert not roll2.get("active_movement") and roll2["journey"]["stage"] == "label_verified"
    assert admin.post(f"{url}/arrival-trips", json={"epcs": [rolls[2]["roll_no"]]}, timeout=30).status_code == 400


def test_zero_arrival_never_completed_and_accept_needs_approve(admin, wh_staff, mdb, W):
    pa, rolls = _open_pa(admin, mdb, W, 2)
    url = f"{BASE}/putaway-orders/{pa['id']}"
    r = admin.post(f"{url}/close", json={"action": "exception", "reason": "EPC tidak terbaca di gate"}, timeout=60)
    o = r.json()
    assert r.status_code == 200 and o["status"] == "exception" and not o.get("btg_number")
    ids = [x["id"] for x in rolls]
    r = wh_staff.post(f"{url}/resolve-exception", json={"roll_ids": ids[:1], "action": "accept"}, timeout=30)
    assert r.status_code == 403, r.text                         # accept setara manual → wms.approve
    r = admin.post(f"{url}/resolve-exception", json={"roll_ids": ids, "action": "return_transit"}, timeout=60)
    o = r.json()
    assert r.status_code == 200 and o["status"] == "returned" and not o.get("btg_number"), o.get("status")


def test_confirm_arrival_trip_from_gate_service(admin, mdb, W):
    from fastapi import HTTPException
    from services import putaway_arrival_service as arr
    pa, rolls = _open_pa(admin, mdb, W, 1)
    src = {"type": "gate", "passage_id": f"PSG-{TAG}"}
    out = run(arr.confirm_arrival_trip(pa["id"], [rolls[0]["roll_no"]], src, {"name": "Gate IN"}))
    assert out["status"] == "completed" and out["trip"]["source"]["passage_id"] == f"PSG-{TAG}"
    assert out["items"][0]["arrived_via"] == "gate"
    with pytest.raises(HTTPException):   # PA sudah selesai
        run(arr.confirm_arrival_trip(pa["id"], [rolls[0]["roll_no"]], src, "Gate IN"))
    with pytest.raises(HTTPException):
        arr.norm_source({"type": "gate"})                         # gate wajib passage_id
    pa2, rolls2 = _open_pa(admin, mdb, W, 2)
    run(arr.confirm_arrival_trip(pa2["id"], [rolls2[0]["roll_no"]], {"type": "gate", "passage_id": "P2"}, "Gate"))
    dup = run(arr.confirm_arrival_trip(pa2["id"], [rolls2[1]["roll_no"]], {"type": "gate", "passage_id": "P2"}, "Gate"))
    assert dup["duplicate_trip"] is True and dup["status"] == "partially_received"


# ─── 6. Izin HTTP ────────────────────────────────────────────────────────────
def test_http_permissions(mdb, W):
    anon = requests.post(f"{BASE}/putaway-orders/pa_x/publish", json={}, timeout=30)
    assert anon.status_code in (401, 403)
    sales = _login("sales@kainnusantara.id")
    for path, body in (("/putaway-orders/pa_x/publish", {}), ("/putaway-orders/pa_x/arrival-trips", {"epcs": ["A"]}),
                       ("/putaway-orders/pa_x/close", {"action": "exception", "reason": "uji izin tanpa hak"}),
                       ("/putaway-orders/auto-draft", {"from_warehouse_id": W["transit"]["id"]})):
        assert sales.post(f"{BASE}{path}", json=body, timeout=30).status_code == 403, path
    assert sales.patch(f"{BASE}/putaway-orders/pa_x/draft", json={}, timeout=30).status_code == 403
    assert sales.get(f"{BASE}/warehouses/{W['transit']['id']}/gate-policy", timeout=30).status_code == 200


def test_prepare_drafts_endpoint(admin, mdb, W):
    rolls = seed(mdb, W, 1)
    r = admin.post(f"{BASE}/putaway-orders/auto-draft", json={"from_warehouse_id": W["transit"]["id"]}, timeout=120)
    assert r.status_code == 200, r.text
    assert drafts_of(mdb, [rolls[0]["id"]]), r.json()