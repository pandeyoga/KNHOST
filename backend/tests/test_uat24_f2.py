"""UAT 24 Okt — fase F2 (ANALISIS_TEMUAN_UAT_23OKT.md P9.3b–P9.6, P10, P11): alur barang.

P9.3b label QR tanpa RFID · P9.4b cross-dock otomatis · P9.6 lokasi dulu + FIFO tanggal masuk ·
P10.5/P10.6/P10-K2 transfer antar-PT (gudang bersama, roll utuh, ke SO peminta) · P11 penanda MDQ/4-point & sampling.

Jalankan: cd /app/backend && python -m pytest tests/test_uat24_f2.py -p no:randomly -n 0 -q
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
ACTOR = {"id": "", "name": "Uji F2"}
WH_SHARED = f"wh_TEST_F2_{T}_bersama"
WH_DED = f"wh_TEST_F2_{T}_khusus"
SELLER, BUYER = "ent_kanda", "ent_ksc"


def _login(email, entity="ent_ksc"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}, r.json()["user"]


ADMIN, _ = _login("admin@kainnusantara.id")


PROD = f"prod_TEST_F2_{T}"


def _product():
    """Produk SEMENTARA — antrean backorder umum tidak boleh menyentuh SO nyata di DB uji."""
    return {"id": PROD, "base_unit": "yard"}


def _roll(suffix, **kw):
    rid = f"roll_TEST_F2_{T}_{suffix}"
    doc = {"id": rid, "roll_no": f"TF2{T}{suffix}".upper(), "product_id": _product()["id"], "owner_entity_id": SELLER,
           "warehouse_id": WH_SHARED, "status": "available", "length_remaining": 50.0, "length_initial": 50.0,
           "unit": "yard", "lot": f"LOT-F2-{T}", "grade": "A", "active_movement": None, "length_reserved": 0,
           "created_at": "2026-10-24T00:00:00+00:00", "defects": []}
    doc.update(kw)
    DB.inventory_rolls.insert_one(doc)
    return rid


@pytest.fixture(scope="module", autouse=True)
def _setup():
    src = DB.products.find_one({"status": "active", "lifecycle": "produksi"}, {"_id": 0})
    clone = {k: v for k, v in src.items() if k not in ("variant_key", "template_id", "variant_options", "variant_attrs")}
    DB.products.insert_one({**clone, "id": PROD, "sku": f"TST-F2-{T}", "name": f"Produk Uji F2 {T}"})
    DB.warehouses.insert_many([
        {"id": WH_SHARED, "code": f"UJ-B-{T}", "name": f"Uji Bersama {T}", "roles": ["storage"], "site_id": "",
         "sharing_mode": "shared", "entity_ids": [], "active": True, "city": "Bandung"},
        {"id": WH_DED, "code": f"UJ-K-{T}", "name": f"Uji Khusus {T}", "roles": ["storage"], "site_id": "",
         "sharing_mode": "dedicated", "entity_ids": [SELLER], "active": True, "city": "Bandung"}])
    yield
    DB.inventory_rolls.delete_many({"$or": [{"id": {"$regex": f"^roll_TEST_F2_{T}"}},
                                            {"parent_roll_id": {"$regex": f"^roll_TEST_F2_{T}"}}]})
    DB.inventory_movements.delete_many({"$or": [{"source_document": {"$regex": f"^so_TEST_F2_{T}"}},
                                                {"warehouse_id": {"$in": [WH_SHARED, WH_DED]}}]})
    DB.inventory_rolls.delete_many({"reserved_ref.id": {"$regex": f"^trn_TEST_F2_{T}"}})
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_TEST_F2_{T}"}})
    DB.inspections.delete_many({"$or": [{"id": {"$regex": f"^ins_TEST_F2_{T}"}},
                                        {"source_inspection_id": {"$regex": f"^ins_TEST_F2_{T}"}}]})
    DB.inventory_balances.delete_many({"warehouse_id": {"$in": [WH_SHARED, WH_DED]}})
    DB.warehouses.delete_many({"id": {"$in": [WH_SHARED, WH_DED]}})
    DB.products.delete_one({"id": PROD})


# ─── P9.3b — label QR (gudang tanpa RFID) ───────────────────────────────────
def test_p9_3b_label_qr_menyiapkan_roll_untuk_putaway():
    rid = _roll("qr", owner_entity_id=BUYER, journey={"stage": "received_transit", "routing": "store"})
    from services import putaway_order_service as pas
    no = DB.inventory_rolls.find_one({"id": rid})["roll_no"]
    res = run(pas.verify_labels(WH_SHARED, [no.lower(), "TIDAK-ADA"], [BUYER], "Uji F2"))
    assert res["verified"] == [no] and res["not_found"] == ["TIDAK-ADA"]
    roll = DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    assert roll["journey"]["stage"] == "label_verified" and roll["journey"]["verified_via"] == "label_scan"
    ready = run(pas._rolls_ready(WH_SHARED, [BUYER]))
    assert rid in {r["id"] for r in ready}


def test_p9_3b_roll_berdata_tag_grn_tetap_bisa_lewat_label_qr_ke_putaway_order():
    """GRN selalu menyiapkan data tag (EPC) walau lokasi tanpa RFID — label QR tetap jalan resmi ke Putaway Order."""
    wh_tr = f"wh_TEST_F2_{T}_transit"
    DB.warehouses.insert_one({"id": wh_tr, "code": f"UJ-T-{T}", "name": f"Uji Transit {T}", "roles": ["transit"],
                              "site_id": "", "sharing_mode": "shared", "entity_ids": [], "active": True, "city": "Bandung"})
    try:
        rid = _roll("qrtag", owner_entity_id=BUYER, warehouse_id=wh_tr, rfid_tag_id=f"rtag_TEST_F2_{T}",
                    journey={"stage": "received_transit", "routing": "store"})
        from services import putaway_order_service as pas
        no = DB.inventory_rolls.find_one({"id": rid})["roll_no"]
        assert run(pas.verify_labels(wh_tr, [no], [BUYER], "Uji F2"))["verified"] == [no]
        pa = run(pas.create_order(wh_tr, WH_SHARED, [rid], [BUYER], "Uji F2"))
        assert [(i["roll_id"], i["epc"]) for i in pa["items"]] == [(rid, no)]
        DB.putaway_orders.delete_one({"id": pa["id"]})
    finally:
        DB.warehouses.delete_one({"id": wh_tr})


# ─── P9.4b — barang tiba untuk SO menunggu → cross-dock ──────────────────────
def test_p9_4b_roll_tercadang_di_tahap_terima_ditandai_cross_dock():
    rid = _roll("xd", owner_entity_id=BUYER, status="reserved",
                journey={"stage": "label_verified", "routing": "store"})
    from services.backorder_service import mark_cross_dock
    n = run(mark_cross_dock(_product()["id"], BUYER))
    assert n >= 1
    j = DB.inventory_rolls.find_one({"id": rid})["journey"]
    assert j["routing"] == "cross_dock" and j["stage"] == "cross_dock_ready"


# ─── P9.6 — lokasi pesanan dulu, FIFO tanggal masuk ─────────────────────────
def test_p9_6_peringkat_gudang_lokasi_dulu_dan_fifo_tanggal_masuk():
    from services.roll_service import _fifo_key, _wh_rank_factory
    whs = {"a": {"city": "Jakarta", "site_id": "s_jkt"}, "b": {"city": "Bandung", "site_id": "s_rcm"}}
    rank = _wh_rank_factory(whs, "Jakarta", site_id="s_rcm")
    assert rank("b") == 0 < rank("a")
    assert _fifo_key({"received_date": "2026-01-01", "created_at": "2026-10-01"}) == "2026-01-01"


# ─── P10.6 / P10-K2 — antar-PT hanya roll di gudang bersama, roll pilihan utuh ─
def test_p10_6_roll_di_gudang_khusus_penjual_ditolak_dengan_pesan_jelas():
    rid = _roll("ded", warehouse_id=WH_DED)
    from fastapi import HTTPException
    from services.roll_service import reserve_rolls_for_transfer
    with pytest.raises(HTTPException) as ei:
        run(reserve_rolls_for_transfer(_product()["id"], SELLER, 10.0, f"trn_TEST_F2_{T}_a", roll_ids=[rid],
                                       usable_for_entity=BUYER, whole_rolls=True))
    assert "gudang bersama" in ei.value.detail or "Transfer Gudang" in ei.value.detail
    assert DB.inventory_rolls.find_one({"id": rid})["status"] == "available"


def test_p10_k2_roll_pilihan_dikirim_utuh_tanpa_dipotong():
    rid = _roll("utuh", length_remaining=50.0)
    from services.roll_service import reserve_rolls_for_transfer
    got = run(reserve_rolls_for_transfer(_product()["id"], SELLER, 20.0, f"trn_TEST_F2_{T}_b", roll_ids=[rid],
                                         usable_for_entity=BUYER, whole_rolls=True))
    assert [r["id"] for r in got] == [rid] and float(got[0]["length_remaining"]) == 50.0
    assert DB.inventory_rolls.count_documents({"parent_roll_id": rid}) == 0      # tidak ada potongan


def test_p10_6_opsi_rencana_menandai_roll_yang_bisa_dipakai_pembeli():
    a = _roll("opsiB")
    b = _roll("opsiK", warehouse_id=WH_DED)
    from services.fulfillment_plan_service import _rolls_for
    rows = {r["id"]: r for r in run(_rolls_for(_product()["id"], SELLER, limit=5000, usable_for=BUYER))}
    assert rows[a]["usable"] is True and rows[b]["usable"] is False


# ─── P10.5 — barang antar-PT dicadangkan ke SO PEMINTA dulu ──────────────────
def test_p10_5_barang_pindahan_masuk_ke_so_peminta_bukan_so_lebih_lama():
    pid = _product()["id"]
    trn = f"trn_TEST_F2_{T}_c"
    rid = _roll("pindah", owner_entity_id=BUYER, length_remaining=30.0, length_initial=30.0,
                acquired={"via": "transfer", "ref_id": trn, "date": "2026-10-24"})
    base = {"entity_id": BUYER, "status": "reserved", "has_backorder": True, "customer_name": "Uji F2",
            "items": [{"product_id": pid, "quantity": 30.0, "reserved_qty": 0.0, "backorder_qty": 30.0}],
            "backorders": [{"product_id": pid, "backorder_qty": 30.0, "reserved_qty": 0.0, "status": "pending"}],
            "allocations": []}
    old_id, req_id = f"so_TEST_F2_{T}_lama", f"so_TEST_F2_{T}_peminta"
    DB.sales_orders.insert_many([{**base, "id": old_id, "number": f"SO-UJ-LAMA-{T}", "created_at": "2020-01-01T00:00:00"},
                                 {**base, "id": req_id, "number": f"SO-UJ-MINTA-{T}", "created_at": "2026-10-24T00:00:00"}])
    from services.interco_service import _auto_fulfill_after_interco_receipt
    seller = {"buyer_entity_id": BUYER, "items": [{"product_id": pid}], "source_order_id": req_id, "pair_id": ""}
    out = run(_auto_fulfill_after_interco_receipt(seller, {"id": trn, "linked_order_id": req_id, "code": "TRF-UJ"},
                                                  "Uji F2"))
    assert out.get("linked_order_id") == req_id
    # Roll pindahan (30) seluruhnya tercadang ke SO PEMINTA — bukan ke SO lama yang lebih dulu antre.
    roll = DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    assert roll["status"] in ("reserved", "committed") and (roll.get("reserved_ref") or {}).get("id") == req_id
    req = DB.sales_orders.find_one({"id": req_id}, {"_id": 0})
    assert req["backorders"][0]["reserved_qty"] == 30.0


# ─── P11 — penanda datar MDQ / 4-point + sampling ───────────────────────────
def test_p11_1_penanda_datar_ditulis_md_lalu_4point():
    rid = _roll("flag", owner_entity_id=BUYER, status="quarantine")
    from services import qc_inspection_service as qis
    roll = DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    run(qis.record_quality(roll, color_result="sesuai", handfeel_result="sesuai", handfeel_score=None, delta_e=None,
                           baseline_sample_id="", baseline_sample_number="", color_action="tahan",
                           handfeel_action="peringatkan", actor={"name": "MDQ Uji"}, inspection_number="INS-UJ-1"))
    r1 = DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    assert r1["md_quality_checked"] is True and r1["md_quality_spk"] == "INS-UJ-1" and not r1.get("inspected_4point")
    run(qis.inspect_roll(r1, [], None, None, "bersih", {"name": "QC Uji", "id": ""}, quality_from_roll=True,
                         grade_input="A", inspection_number="INS-UJ-2"))
    r2 = DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    assert r2["inspected_4point"] is True and r2["inspected_4point_spk"] == "INS-UJ-2"
    assert r2["md_quality_checked"] is True and r2["inspection"]["md_quality_by"] == "MDQ Uji"   # P11.5 tetap


def test_p11_aturan_jumlah_wajib_sampling():
    from services.inspection_service import required_checks
    assert required_checks(10, 20, 1) == 2
    assert required_checks(10, 0, 1) == 1
    assert required_checks(3, 30, 2) == 2
    assert required_checks(10, 100, 1) == 10
    assert required_checks(2, 50, 5) == 2


def test_p11_2_spk_4point_untuk_sebagian_roll_dari_spk_md():
    ids = [_roll(f"md{i}", owner_entity_id=BUYER) for i in range(4)]
    src = f"ins_TEST_F2_{T}_md"
    DB.inspections.insert_one({"id": src, "number": f"INS-UJ-{T}", "kind": "po_receipt", "md_only": True,
                               "entity_id": BUYER, "status": "in_progress",
                               "lines": [{"id": f"ln{i}", "roll_id": r, "roll_no": f"R{i}"} for i, r in enumerate(ids)]})
    from services import inspection_service as svc
    doc = run(svc.create_qc_4point({"inspection_id": src, "roll_ids": ids[:2]}, ACTOR, BUYER))
    assert sorted(ln["roll_id"] for ln in doc["lines"]) == sorted(ids[:2])
    with pytest.raises(svc.InspectionError):
        run(svc.create_qc_4point({"inspection_id": src, "roll_ids": ["roll_lain"]}, ACTOR, BUYER))


def test_p11_2_tutup_spk_4point_sampling_roll_tak_dicek_dikeluarkan(monkeypatch):
    ids = [_roll(f"qc{i}", owner_entity_id=BUYER) for i in range(3)]
    from services import inspection_service as svc
    doc = run(svc.create_qc_4point({"roll_ids": ids}, ACTOR, BUYER))
    DB.inspections.update_one({"id": doc["id"]}, {"$set": {"status": "in_progress", "lines.0.qc_at": "2026-10-24T01:00:00",
                                                           "lines.0.inspected_at": "2026-10-24T01:00:00"}})
    with pytest.raises(svc.InspectionError) as ei:      # bawaan 100% → semua roll wajib
        run(svc.finish(doc["id"], "terima", "", ACTOR))
    assert "wajib minimal 3" in str(ei.value)

    async def rule(d):
        return {"part": "qc", "total": 3, "required": 1, "checked": 1, "pct": 30, "min": 1}
    monkeypatch.setattr(svc, "sampling_rule", rule)
    out = run(svc.finish(doc["id"], "terima", "", ACTOR))
    assert out["status"] == "done" and len(out["lines"]) == 1 and len(out["excluded_lines"]) == 2


def test_p11_4_filter_stok_belum_4point():
    rid = _roll("filt", owner_entity_id=BUYER, inspected_4point=True)
    r = requests.get(f"{BASE}/inventory/rolls", headers=ADMIN,
                     params={"check": "no_4point", "product_id": _product()["id"], "limit": 5000})
    assert r.status_code == 200, r.text
    assert rid not in {x["id"] for x in r.json()}
