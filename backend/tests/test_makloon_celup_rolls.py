"""Kasus klien "celup": 20 roll Esmica Blue dikirim ke mitra untuk dicelup hitam; Esmica Hitam kembali sebagai barang
baru. Uji tingkat LAYANAN (tanpa HTTP, data sendiri bertanda TEST_CELUP, dibersihkan di akhir) + sedikit HTTP
baca/tolak (butuh backend yang sudah memuat kode ini — dilewati otomatis bila endpoint baru belum ada).

Cakupan:
  1. Issue per roll: sukses (qty = Σ panjang roll, estimasi diskalakan), pindai EPC/nomor roll, ditolak untuk roll
     salah produk / salah gudang / karantina / ditahan inspeksi / dipesan — pesan menyebut nomor roll; jalur jumlah
     lama (FEFO + belah roll) tetap jalan.
  2. Hasil langkah TERAKHIR dikarantina + tugas QC + SPK "Inspeksi Hasil Makloon" bila `qc_on_receipt`, tahap journey
     sesuai peran gudang (transit → received_transit, simpan → stored); rilis QC lewat SPK meluluskan roll; langkah
     TENGAH tidak dikarantina dan langkah berikutnya bisa di-issue dari roll hasilnya.
  3. Gate: OUT hijau untuk makloon & perbaikan aktif (lalu REPLAY_EXIT), merah bila dokumen batal/tidak aktif/gudang
     salah; IN hijau untuk roll perbaikan yang kembali & bahan MKO batal.
  4. Penjaga satuan: produk tanpa satuan dasar → 400 (output, sisa, PO bahan otomatis) tanpa efek samping.

Jalankan (DB uji):
  cd /app/backend && python -m pytest -q -p no:cacheprovider tests/test_makloon_celup_rolls.py
"""
import os
import sys
import uuid

import pytest
from fastapi import HTTPException
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import gate_evaluator as ge  # noqa: E402
from services import inspection_service as ins  # noqa: E402
from services import makloon_issue_rolls as mir  # noqa: E402
from services import makloon_order_service as mko  # noqa: E402
from services import makloon_receipt_qc as mqc  # noqa: E402
from services import repair_order_service as rpr  # noqa: E402
from services import rfid_service  # noqa: E402
from services import roll_service  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
ENT = f"ent_TEST_CELUP_{TAG}"
WH_SRC, WH_TRN, WH_OTH = (f"wh_TEST_CELUP_{TAG}_{k}" for k in ("src", "trn", "oth"))
P_BLUE, P_MID, P_BLACK, P_NOUNIT, P_QTY = (f"prod_TEST_CELUP_{TAG}_{k}" for k in ("blue", "mid", "black", "nounit", "qty"))
MAK = f"mak_TEST_CELUP_{TAG}"
ACTOR = {"name": "Uji Celup", "id": f"usr_TEST_CELUP_{TAG}"}
_N = {"n": 0}


def _nx() -> int:
    _N["n"] += 1
    return _N["n"]


@pytest.fixture(scope="module", autouse=True)
def seed():
    DB.business_entities.insert_one({"id": ENT, "short_name": f"UJI-{TAG}", "code": f"U{TAG[:4].upper()}",
                                     "legal_name": "PT Uji Celup"})
    DB.warehouses.insert_many([
        {"id": WH_SRC, "name": f"Gudang Simpan {TAG}", "code": f"GS{TAG[:4]}", "roles": ["storage"],
         "sharing_mode": "shared", "active": True},
        {"id": WH_TRN, "name": f"Gudang Transit {TAG}", "code": f"GT{TAG[:4]}", "roles": ["transit"],
         "sharing_mode": "shared", "active": True},
        {"id": WH_OTH, "name": f"Gudang Lain {TAG}", "code": f"GL{TAG[:4]}", "roles": ["storage"],
         "sharing_mode": "shared", "active": True}])
    base = {"harga_pokok": 0, "status": "active", "stage": "finished", "fabric_type": "woven"}
    DB.products.insert_many([
        {**base, "id": P_BLUE, "sku": f"ESM-BLUE-{TAG}", "name": "Esmica Blue", "base_unit": "yard"},
        {**base, "id": P_MID, "sku": f"ESM-MID-{TAG}", "name": "Esmica Setengah Jadi", "base_unit": "yard"},
        {**base, "id": P_BLACK, "sku": f"ESM-BLACK-{TAG}", "name": "Esmica Hitam", "base_unit": "yard"},
        {**base, "id": P_NOUNIT, "sku": f"ESM-NOUNIT-{TAG}", "name": "Tanpa Satuan", "base_unit": ""},
        {**base, "id": P_QTY, "sku": f"ESM-QTY-{TAG}", "name": "Esmica Jalur Jumlah", "base_unit": "yard"}])
    DB.makloons.insert_one({"id": MAK, "name": "Mitra Celup Uji", "entity_id": ENT})
    DB.system_settings.insert_one({"scope": ENT, "purchasing": {"qc_on_receipt": True}})
    yield
    rns = [r["roll_no"] for r in DB.inventory_rolls.find({"owner_entity_id": ENT}, {"roll_no": 1}) if r.get("roll_no")]
    DB.number_sequences.delete_many({"doc_type": {"$in": [f"ROLL_CHILD:{rn}" for rn in rns]}})  # penghitung roll anak
    for coll in ("inventory_rolls", "inventory_lots", "inventory_movements", "inventory_balances", "rfid_tags",
                 "material_reservations"):
        DB[coll].delete_many({"owner_entity_id": ENT})
    for coll in ("wms_tasks", "inspections", "makloon_orders", "journal_entries", "repair_orders", "vendor_bills",
                 "number_sequences", "inventory_lots", "notifications"):
        DB[coll].delete_many({"entity_id": ENT})
    DB.system_settings.delete_many({"scope": ENT})
    DB.products.delete_many({"id": {"$in": [P_BLUE, P_MID, P_BLACK, P_NOUNIT, P_QTY]}})
    DB.warehouses.delete_many({"id": {"$in": [WH_SRC, WH_TRN, WH_OTH]}})
    DB.makloons.delete_many({"id": MAK})
    DB.business_entities.delete_many({"id": ENT})


def _roll(pid, wh, qty, status="available", **extra):
    r = run(roll_service.create_inbound_roll(pid, wh, ENT, qty, lot=f"LOT-{TAG}-{_nx()}", unit="yard",
                                             unit_cost=1000.0, created_by="uji"))
    if status != "available" or extra:
        DB.inventory_rolls.update_one({"id": r["id"]}, {"$set": {"status": status, **extra}})
        run(roll_service.rebuild_balance(pid, wh, ENT))
    return DB.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0})


def _step(oid, seq, inp, out, qty, unit="yard"):
    return {"seq": seq, "status": "pending", "issue_ref": f"{oid}:{seq}", "makloon_id": MAK,
            "makloon_name": "Mitra Celup Uji", "material_flow": "moves", "process_type": "dyeing",
            "stage_label": "Celup", "changes_stage": True, "input_product_id": inp, "input_name": "bahan",
            "input_unit": unit, "input_qty": qty, "output_product_id": out, "output_name": "hasil",
            "output_unit": unit, "output_sku": "OUT", "expected_output_qty": qty, "expected_byproduct_qty": 0,
            "tariff_basis": "lumpsum", "tariff_rate": 0, "tolerance_pct": 5, "shrinkage_pct": 0, "aux_cost": 0}


def _order(steps_spec, wh=WH_SRC):
    oid = f"mko_TEST_CELUP_{TAG}_{_nx()}"
    steps = [_step(oid, i + 1, *spec) for i, spec in enumerate(steps_spec)]
    DB.makloon_orders.insert_one({
        "id": oid, "mko_number": f"UJI/MKO-{TAG}-{_N['n']}", "entity_id": ENT, "mode": "process_only",
        "status": "draft", "from_warehouse_id": wh, "target_warehouse_id": wh, "line_code": "", "steps": steps,
        "timeline": [], "costing": {"steps": []}, "claim_summary": {}, "service_absorption_pending": 0.0,
        "created_at": "2026-11-04T00:00:00+00:00"})
    return oid


def _detail(oid):
    return DB.makloon_orders.find_one({"id": oid}, {"_id": 0})


def _http_error(coro):
    with pytest.raises(HTTPException) as ei:
        run(coro)
    return ei.value


# ── 1. Issue per roll ─────────────────────────────────────────────────────────
def test_issue_by_picked_rolls_qty_is_sum_and_estimate_scaled():
    r1, r2, r3 = _roll(P_BLUE, WH_SRC, 40), _roll(P_BLUE, WH_SRC, 35.5), _roll(P_BLUE, WH_SRC, 30)
    oid = _order([(P_BLUE, P_BLACK, 100)])
    order = run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_ids=[r1["id"], r2["id"]], actor_name="uji"))
    st = order["steps"][0]
    assert st["status"] == "issued" and st["issue_mode"] == "rolls"
    assert st["input_qty"] == 75.5                                    # Σ panjang roll terpilih, satuan dasar
    assert st["expected_output_qty"] == pytest.approx(75.5, abs=0.01)  # diskalakan 100 → 75,5
    assert st["issue_deviation"]["planned_qty"] == 100 and st["issue_deviation"]["diff"] == -24.5
    assert sorted(st["issued_roll_ids"]) == sorted([r1["id"], r2["id"]])
    assert st["material_value"] == pytest.approx(75.5 * 1000, abs=0.01)   # nilai WAC → GL WIP (tetap)
    rows = {r["id"]: r for r in DB.inventory_rolls.find({"id": {"$in": [r1["id"], r2["id"], r3["id"]]}}, {"_id": 0})}
    assert rows[r1["id"]]["status"] == rows[r2["id"]]["status"] == "subcon"
    assert rows[r1["id"]]["bucket_ref"]["id"] == f"{oid}:1"
    assert rows[r3["id"]]["status"] == "available"                    # roll yang tidak dipilih tetap di rak
    assert rows[r1["id"]]["length_remaining"] == 40                   # utuh, tidak dibelah
    movs = DB.inventory_movements.count_documents({"roll_id": {"$in": [r1["id"], r2["id"]]},
                                                   "movement_type": "subcon_issue"})
    assert movs == 2
    assert any("2 roll dipilih" in (t.get("note") or "") for t in order["timeline"])


def test_issue_by_scan_codes_epc_and_roll_no():
    r1, r2 = _roll(P_BLUE, WH_SRC, 20), _roll(P_BLUE, WH_SRC, 20)
    tag = run(rfid_service.encode_tag(r1["id"], [ENT], actor_name="uji"))
    pretty = "-".join(tag["epc"][i:i + 4] for i in range(0, 24, 4)).lower()   # dipindai berformat + huruf kecil
    oid = _order([(P_BLUE, P_BLACK, 40)])
    cand = run(mir.candidates_for(oid, 1, WH_SRC))
    epc_row = next(x for x in cand["rolls"] if x["id"] == r1["id"])
    assert epc_row["epc"] == tag["epc"]
    order = run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_codes=[pretty, r2["roll_no"]], actor_name="uji"))
    assert sorted(order["steps"][0]["issued_roll_ids"]) == sorted([r1["id"], r2["id"]])
    assert order["steps"][0]["issue_deviation"] is None                # tepat rencana → tanpa catatan
    err = _http_error(mko.issue_step(_order([(P_BLUE, P_BLACK, 10)]), 1, from_warehouse_id=WH_SRC,
                                     roll_codes=["BUKAN-KODE-ROLL"], actor_name="uji"))
    assert err.status_code == 400 and "BUKAN-KODE-ROLL" in err.detail


@pytest.mark.parametrize("case", ["product", "warehouse", "quarantine", "inspection_hold", "reserved"])
def test_issue_rejects_wrong_or_held_roll_with_roll_number(case):
    if case == "product":
        r, code = _roll(P_MID, WH_SRC, 10), 400
    elif case == "warehouse":
        r, code = _roll(P_BLUE, WH_OTH, 10), 400
    elif case == "quarantine":
        r, code = _roll(P_BLUE, WH_SRC, 10, status="quarantine"), 409
    elif case == "inspection_hold":
        r, code = _roll(P_BLUE, WH_SRC, 10, inspection={"hold": {"held": True, "reason": "warna"}}), 409
    else:
        r, code = _roll(P_BLUE, WH_SRC, 10, reserved_ref={"type": "sales_order", "id": "so_x", "number": "SO-9"}), 409
    oid = _order([(P_BLUE, P_BLACK, 10)])
    err = _http_error(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_ids=[r["id"]], actor_name="uji"))
    assert err.status_code == code and r["roll_no"] in err.detail, err.detail
    assert _detail(oid)["steps"][0]["status"] == "pending"            # tidak ada efek sebagian
    assert DB.inventory_rolls.find_one({"id": r["id"]})["status"] != "subcon"
    blocked = {x["id"]: x["reason"] for x in run(mir.candidates_for(oid, 1, WH_SRC))["blocked"]}
    if case in ("quarantine", "inspection_hold", "reserved"):
        assert r["id"] in blocked and r["roll_no"] in blocked[r["id"]]   # layar menjelaskan alasan tertahannya


def test_legacy_qty_issue_still_fefo_and_splits():
    a, b = _roll(P_QTY, WH_SRC, 20), _roll(P_QTY, WH_SRC, 20)
    oid = _order([(P_QTY, P_BLACK, 30)])
    st = run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, actor_name="uji"))["steps"][0]
    assert st["issue_mode"] == "qty" and st["input_qty"] == 30 and st["issue_deviation"] is None
    assert round(sum(r["length_remaining"] for r in DB.inventory_rolls.find(
        {"bucket_ref.id": f"{oid}:1", "status": "subcon"})), 2) == 30
    left = DB.inventory_rolls.find_one({"id": b["id"]})
    assert left["status"] == "available" and left["length_remaining"] == 10    # belah roll (perilaku lama)
    assert DB.inventory_rolls.find_one({"id": a["id"]})["status"] == "subcon"


# ── 2. Hasil langkah terakhir = barang PO; langkah tengah tidak terhalang ──────
def _receive(oid, seq, qty, wh, n_rolls=2, **data):
    per = round(qty / n_rolls, 2)
    rolls = [{"lot": f"HIT-{TAG}-{_nx()}", "length": per, "grade": "A", "dye_lot": "DL1"} for _ in range(n_rolls)]
    return run(mko.receive_step(oid, seq, {"actual_output_qty": round(per * n_rolls, 2), "actual_byproduct_qty": 0,
                                           "rolls": rolls, "output_warehouse_id": wh, **data}, actor_name="uji"))


def test_final_step_quarantined_with_qc_task_spk_and_transit_journey_then_released():
    r1, r2 = _roll(P_BLUE, WH_SRC, 25), _roll(P_BLUE, WH_SRC, 25)
    oid = _order([(P_BLUE, P_BLACK, 50)])
    run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_ids=[r1["id"], r2["id"]], actor_name="uji"))
    order = _receive(oid, 1, 50, WH_TRN)
    st = order["steps"][0]
    rq = st["receipt_qc"]
    assert rq["final_step"] and rq["required"] and len(rq["task_ids"]) == 1
    tid = rq["task_ids"][0]
    outs = list(DB.inventory_rolls.find({"id": {"$in": [x["roll_id"] for x in st["lots"]]}}, {"_id": 0}))
    assert len(outs) == 2 and all(r["status"] == "quarantine" and r["qc_task_id"] == tid for r in outs)
    assert all(r["journey"]["stage"] == "received_transit" and r["journey"]["routing"] == "store" for r in outs)
    task = DB.wms_tasks.find_one({"id": tid}, {"_id": 0})
    assert task["status"] == "qc_pending" and task["flow_type"] == "inbound" and task["source_type"] == "makloon_order"
    assert task["quantity"] == 50 and task["qty_rolls"] == 2 and task["owner_entity_id"] == ENT
    spk = DB.inspections.find_one({"task_id": tid}, {"_id": 0})
    assert spk and spk["kind"] == "makloon_output" and spk["ref_doc_id"] == oid and len(spk["lines"]) == 2
    assert any(i.get("inspection", {}).get("number") == spk["number"] for i in _detail(oid)["steps"][0]["receipt_qc"]["inspections"])
    bal = DB.inventory_balances.find_one({"product_id": P_BLACK, "warehouse_id": WH_TRN, "owner_entity_id": ENT})
    assert bal["quarantine_qty"] == 50 and bal["available_qty"] == 0
    # Tag RFID otomatis mengikuti kunci yang sama dengan scan label PO (`receiving.auto_rfid_on_scan`).
    from services.receiving_roll_service import receiving_cfg
    auto = bool(run(receiving_cfg("auto_rfid_on_scan", ENT)))
    assert (_detail(oid)["steps"][0]["receipt_qc"].get("rfid_tagged") or 0) == (2 if auto else 0)
    assert all(bool(_fresh(r["id"]).get("rfid_tag_id")) == auto for r in outs)
    # Rilis QC lewat SPK (jalur F-14 yang sama dengan PO): diterima → tersedia, saldo pemilik ikut di-rebuild.
    res = run(ins._release_quarantine(spk, "terima", "lolos warna", ACTOR, "", None))
    assert res["accepted_qty"] == 50 and res["task_status"] == "completed"
    outs = list(DB.inventory_rolls.find({"id": {"$in": [r["id"] for r in outs]}}, {"_id": 0}))
    assert all(r["status"] == "available" and not r.get("qc_task_id") for r in outs)
    assert all(r["journey"]["stage"] == "received_transit" for r in outs)        # lanjut antre tag/putaway
    bal = DB.inventory_balances.find_one({"product_id": P_BLACK, "warehouse_id": WH_TRN, "owner_entity_id": ENT})
    assert bal["available_qty"] == 50 and bal["quarantine_qty"] == 0


def test_rejected_makloon_output_cannot_become_supplier_return():
    r = _roll(P_BLUE, WH_SRC, 10)
    oid = _order([(P_BLUE, P_BLACK, 10)])
    run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_ids=[r["id"]], actor_name="uji"))
    st = _receive(oid, 1, 10, WH_SRC, n_rolls=1)["steps"][0]
    spk = DB.inspections.find_one({"task_id": st["receipt_qc"]["task_ids"][0]}, {"_id": 0})
    with pytest.raises(ins.InspectionError) as ei:
        run(ins._release_quarantine(spk, "tolak", "warna belang parah", ACTOR, "return", None))
    assert "Klaim" in str(ei.value)
    out = DB.inventory_rolls.find_one({"id": st["lots"][0]["roll_id"]})
    assert out["status"] == "quarantine" and out["journey"]["stage"] == "stored"   # gudang simpan → stored


def test_middle_step_not_quarantined_and_next_step_issues_from_its_rolls():
    r1, r2 = _roll(P_BLUE, WH_SRC, 30), _roll(P_BLUE, WH_SRC, 30)
    oid = _order([(P_BLUE, P_MID, 60), (P_MID, P_BLACK, 60)])
    run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_ids=[r1["id"], r2["id"]], actor_name="uji"))
    st1 = _receive(oid, 1, 60, WH_SRC)["steps"][0]
    assert not st1.get("receipt_qc")
    mids = list(DB.inventory_rolls.find({"id": {"$in": [x["roll_id"] for x in st1["lots"]]}}, {"_id": 0}))
    assert all(r["status"] == "available" and not r.get("qc_task_id") and not r.get("journey") for r in mids)
    assert DB.wms_tasks.count_documents({"mko_id": oid}) == 0
    order = run(mko.issue_step(oid, 2, from_warehouse_id=WH_SRC, roll_ids=[r["id"] for r in mids], actor_name="uji"))
    assert order["steps"][1]["status"] == "issued" and order["steps"][1]["input_qty"] == 60
    st2 = _receive(oid, 2, 60, WH_SRC)["steps"][1]
    assert st2["receipt_qc"]["required"] is True


def test_final_step_without_qc_setting_is_available_with_journey():
    DB.system_settings.update_one({"scope": ENT}, {"$set": {"purchasing.qc_on_receipt": False}})
    try:
        r = _roll(P_BLUE, WH_SRC, 12)
        oid = _order([(P_BLUE, P_BLACK, 12)])
        run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_ids=[r["id"]], actor_name="uji"))
        st = _receive(oid, 1, 12, WH_TRN, n_rolls=1)["steps"][0]
        assert st["receipt_qc"]["final_step"] and st["receipt_qc"]["required"] is False
        out = DB.inventory_rolls.find_one({"id": st["lots"][0]["roll_id"]})
        assert out["status"] == "available" and out["journey"]["stage"] == "received_transit"
        assert not out.get("qc_task_id") and DB.wms_tasks.count_documents({"mko_id": oid}) == 0
    finally:
        DB.system_settings.update_one({"scope": ENT}, {"$set": {"purchasing.qc_on_receipt": True}})


# ── 3. Gate ───────────────────────────────────────────────────────────────────
def _fresh(rid):
    return DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})


def test_gate_out_makloon_green_then_replay_and_wrong_warehouse():
    r = _roll(P_BLUE, WH_SRC, 15)
    oid = _order([(P_BLUE, P_BLACK, 15)])
    before = run(ge.evaluate("out", WH_SRC, _fresh(r["id"])))
    assert before["result"] == "red" and before["code"] == "NO_DOCUMENT"
    run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_ids=[r["id"]], actor_name="uji"))
    wrong = run(ge.evaluate("out", WH_OTH, _fresh(r["id"])))
    assert wrong["code"] == "WRONG_WAREHOUSE"
    ok = run(ge.evaluate("out", WH_SRC, _fresh(r["id"])))
    assert ok["result"] == "green" and ok["code"] == "MOVEMENT_OUT", ok
    assert _detail(oid)["mko_number"] in ok["reason"] and ok["movement"]["type"] == "makloon_order"
    run(ge.stamp_exit(r["id"], ok, {"id": "dev_uji"}, "2026-11-04T08:00:00+00:00"))
    again = run(ge.evaluate("out", WH_SRC, _fresh(r["id"])))
    assert again["result"] == "red" and again["code"] == "REPLAY_EXIT"


def test_gate_makloon_cancelled_out_red_and_return_in_green():
    r = _roll(P_BLUE, WH_SRC, 15)
    oid = _order([(P_BLUE, P_BLACK, 15)])
    run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_ids=[r["id"]], actor_name="uji"))
    run(mko.cancel_order(oid, reason="batal uji gate", actor_name="uji"))
    out = run(ge.evaluate("out", WH_SRC, _fresh(r["id"])))
    assert out["result"] == "red" and out["code"] == "DOC_CANCELLED" and ge.action_for("DOC_CANCELLED") in out["action"]
    back = run(ge.evaluate("in", WH_SRC, _fresh(r["id"])))
    assert back["result"] == "green" and back["code"] == "MOVEMENT_IN" and "Retur Bahan" in back["reason"]
    elsewhere = run(ge.evaluate("in", WH_OTH, _fresh(r["id"])))
    assert elsewhere["result"] == "red" and elsewhere["code"] == "WRONG_DESTINATION"


def test_gate_makloon_inactive_step_red_not_released():
    r = _roll(P_BLUE, WH_SRC, 15)
    oid = _order([(P_BLUE, P_BLACK, 15)])
    run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_ids=[r["id"]], actor_name="uji"))
    DB.makloon_orders.update_one({"id": oid}, {"$set": {"steps.0.status": "received"}})   # anomali: dokumen tak aktif
    out = run(ge.evaluate("out", WH_SRC, _fresh(r["id"])))
    assert out["result"] == "red" and out["code"] == "NOT_RELEASED" and "langkah 1" in out["reason"]


def test_gate_repair_out_green_in_green_and_inactive_red():
    r = _roll(P_BLACK, WH_SRC, 18)
    ro = run(rpr.create({"kind": "celup_ulang", "partner_type": "internal", "target_color": "Hitam pekat",
                         "roll_ids": [r["id"]]}, ACTOR, ENT))
    draft = run(ge.evaluate("out", WH_SRC, _fresh(r["id"])))
    assert draft["code"] == "NO_DOCUMENT"                              # Draf: roll belum keluar stok
    run(rpr.send(ro["id"], ACTOR))
    out = run(ge.evaluate("out", WH_SRC, _fresh(r["id"])))
    assert out["result"] == "green" and out["code"] == "MOVEMENT_OUT" and ro["number"] in out["reason"]
    back = run(ge.evaluate("in", WH_SRC, _fresh(r["id"])))
    assert back["result"] == "green" and back["code"] == "MOVEMENT_IN" and "perbaikan" in back["reason"]
    assert run(ge.evaluate("in", WH_OTH, _fresh(r["id"])))["code"] == "WRONG_DESTINATION"
    DB.repair_orders.update_one({"id": ro["id"]}, {"$set": {"status": "done"}})       # dokumen tak aktif
    bad = run(ge.evaluate("out", WH_SRC, _fresh(r["id"])))
    assert bad["result"] == "red" and bad["code"] == "NOT_RELEASED" and ro["number"] in bad["reason"]


# ── 4. Penjaga satuan ─────────────────────────────────────────────────────────
def test_unit_guard_rejects_output_without_base_unit_before_any_effect():
    r = _roll(P_BLUE, WH_SRC, 10)
    oid = _order([(P_BLUE, P_NOUNIT, 10)])
    DB.makloon_orders.update_one({"id": oid}, {"$set": {"steps.0.output_unit": ""}})
    run(mko.issue_step(oid, 1, from_warehouse_id=WH_SRC, roll_ids=[r["id"]], actor_name="uji"))
    err = _http_error(mko.receive_step(oid, 1, {"actual_output_qty": 10, "rolls": [{"lot": "X1", "length": 10}],
                                                "output_warehouse_id": WH_SRC}, actor_name="uji"))
    assert err.status_code == 400 and f"ESM-NOUNIT-{TAG}" in err.detail and "Satuan dasar produk" in err.detail
    doc = _detail(oid)
    assert doc["steps"][0]["status"] == "issued" and "saga_lock" not in doc            # tanpa efek / kunci tertinggal
    assert DB.inventory_rolls.find_one({"id": r["id"]})["status"] == "subcon"


def test_unit_guard_byproduct_and_material_po():
    with pytest.raises(HTTPException) as ei:
        run(mqc.receipt_units({"output_unit": "", "input_unit": "", "byproduct_product_id": P_NOUNIT},
                              {"sku": "OUT", "base_unit": "yard"}, 3))
    assert ei.value.status_code == 400 and f"ESM-NOUNIT-{TAG}" in ei.value.detail
    assert run(mqc.receipt_units({"output_unit": "", "input_unit": ""}, {"sku": "OUT", "base_unit": "yard"}, 0)) == ("yard", "")
    err = _http_error(mko.create_makloon_order({"mode": "buy_process", "steps": [{}], "material_product_id": P_NOUNIT,
                                                "material_qty": 10}, entity_id=ENT, actor_name="uji"))
    assert err.status_code == 400 and "Satuan dasar produk" in err.detail
    assert DB.makloon_orders.count_documents({"entity_id": ENT, "mode": "buy_process"}) == 0


def test_final_step_detection_ignores_trailing_service_steps():
    order = {"steps": [{"seq": 1, "material_flow": "moves"}, {"seq": 2, "material_flow": "service_only"}]}
    assert mqc.is_final_fabric_step(order, 1) is True
    order["steps"].append({"seq": 3, "material_flow": "moves"})
    assert mqc.is_final_fabric_step(order, 1) is False and mqc.is_final_fabric_step(order, 3) is True


# ── HTTP (baru berjalan setelah backend memuat kode ini — dilewati bila endpoint belum ada) ──
def _base() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not v and os.path.exists("/app/frontend/.env"):
        for ln in open("/app/frontend/.env"):
            if ln.startswith("REACT_APP_BACKEND_URL="):
                v = ln.split("=", 1)[1].strip().strip('"').strip("'")
    return v.rstrip("/")


@pytest.fixture(scope="module")
def http():
    requests = pytest.importorskip("requests")
    base = _base()
    if not base:
        pytest.skip("REACT_APP_BACKEND_URL tidak diketahui")
    try:
        r = requests.post(f"{base}/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"},
                          timeout=15)
    except requests.RequestException:
        pytest.skip("backend tidak terjangkau")
    if r.status_code != 200:
        pytest.skip(f"login admin gagal ({r.status_code})")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}",
                      "X-Entity-Id": "ent_ksc"})
    rows = s.get(f"{base}/api/makloon-orders", timeout=30)
    rows = rows.json() if rows.status_code == 200 else []
    rows = rows.get("items", rows) if isinstance(rows, dict) else rows
    target = next(((o, st) for o in rows if o.get("status") not in ("completed", "cancelled")
                   for st in o.get("steps") or [] if st.get("status") == "pending"
                   and st.get("material_flow", "moves") != "service_only"), None)
    if not target:
        pytest.skip("tidak ada MKO dengan langkah pending di data acuan")
    probe = s.get(f"{base}/api/makloon-orders/{target[0]['id']}/steps/{target[1]['seq']}/issue-rolls", timeout=30)
    if probe.status_code in (404, 405) and "tidak ditemukan" not in probe.text.lower():
        pytest.skip("endpoint issue-rolls belum dimuat backend (perlu restart)")
    return {"s": s, "base": base, "order": target[0], "step": target[1], "probe": probe}


def test_http_issue_rolls_listing_and_reject_unknown_code(http):
    s, base, o, st = http["s"], http["base"], http["order"], http["step"]
    assert http["probe"].status_code in (200, 400), http["probe"].text
    if http["probe"].status_code == 200:
        body = http["probe"].json()
        assert {"rolls", "blocked", "unit", "planned_qty"} <= set(body)
    r = s.post(f"{base}/api/makloon-orders/{o['id']}/issue", json={
        "step_seq": st["seq"], "from_warehouse_id": o.get("from_warehouse_id") or "", "roll_codes": [f"TIDAK-ADA-{TAG}"]},
        timeout=30)
    assert r.status_code == 400 and f"TIDAK-ADA-{TAG}" in r.text, r.text    # ditolak, tanpa mutasi
