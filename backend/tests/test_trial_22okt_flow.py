"""Trial 22 Okt 2026 (E3/E8/E10) — alur pesanan baru, uji ujung-ke-ujung lewat API.

E3.  Pelanggan kredit terblokir (lewat batas / diblokir) → SO DITOLAK 409 CREDIT_BLOCKED (dulu lahir dengan ACC kredit).
E10. Harga khusus dari checkout terikat SO: SO lahir harga normal + entri ACC harga menunggu; ACC → harga baris.
E8.  Periksa & lepas ke gudang (satu tombol Admin Sales): menunggu ACC → dilepas otomatis sesudah ACC; ditolak →
     sales "lanjut harga normal" → dilepas otomatis; "tahan dulu" → dilepas lewat tombol Lepas; ACC datang sebelum
     diperiksa → dilepas saat Admin Sales memeriksa.

Tes ini MEMBUAT pesanan, jadi WAJIB dijalankan terhadap DB salinan, bukan DB data acuan UAT:
  docker exec kn-dev-mongo-1 sh -c "mongodump --archive --db kn_verify_owner3 | mongorestore --archive \\
      --nsFrom 'kn_verify_owner3.*' --nsTo 'kn_test_trial.*' --drop"
  (backend kedua) DB_NAME=kn_test_trial uvicorn server:app --port 8099
  DB_NAME=kn_test_trial REACT_APP_BACKEND_URL=http://localhost:8099 python -m pytest tests/test_trial_22okt_flow.py \\
      -p no:randomly -n 0 -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402

if os.environ.get("DB_NAME") != "kn_test_trial":
    pytest.skip("hanya untuk DB salinan kn_test_trial (tes ini membuat pesanan)", allow_module_level=True)

DB = base.DB


@pytest.fixture(scope="module")
def u():
    return {k: base.Api(e) for k, e in (("sales", "sales@kainnusantara.id"), ("sadm", "salesadmin@kainnusantara.id"),
                                       ("mgr", "manager@kainnusantara.id"))}


def _so(u, requested_price=None, qty=5):
    pid = base._product()
    item = {"product_id": pid, "quantity": qty, "unit": "yard"}
    if requested_price:
        item.update({"requested_price": requested_price, "special_price_reason": "uji trial — pesaing lebih murah"})
    c, so = u["sales"].call("POST", "/sales-orders", {
        "customer_id": base.CUST, "shipping_address_id": "", "entity_id": base.ENT, "allow_backorder": False,
        "items": [item], "confirm_mixed_lot": True, "fulfillment_method": "kirim"})
    assert c == 200, so
    return so


def _entry(so_id, atype="special_price"):
    so = DB.sales_orders.find_one({"id": so_id}, {"_id": 0})
    return so, next((p for p in so.get("pending_approvals") or [] if p.get("type") == atype), None)


def _tasks(so_id):
    return DB.wms_tasks.count_documents({"order_id": so_id, "flow_type": "outbound"})


def test_e3_kredit_terblokir_tidak_bisa_buat_so(u):
    cust = DB.customers.find_one({"id": base.CUST}, {"_id": 0, "credit_limit": 1})
    DB.customers.update_one({"id": base.CUST}, {"$set": {"credit_limit": 1}})
    try:
        n0 = DB.sales_orders.count_documents({"customer_id": base.CUST})
        c, b = u["sales"].call("POST", "/sales-orders", {
            "customer_id": base.CUST, "shipping_address_id": "", "entity_id": base.ENT,
            "items": [{"product_id": base._product(), "quantity": 5, "unit": "yard"}], "confirm_mixed_lot": True})
        assert c == 409 and b["detail"]["code"] == "CREDIT_BLOCKED", b
        assert DB.sales_orders.count_documents({"customer_id": base.CUST}) == n0          # tidak ada SO lahir
    finally:
        DB.customers.update_one({"id": base.CUST}, {"$set": {"credit_limit": (cust or {}).get("credit_limit", 0)}})


def test_e10_e8_harga_khusus_checkout_acc_lalu_lepas_otomatis(u):
    so = _so(u, requested_price=1000)
    normal = float(so["items"][0]["price"])
    doc, entry = _entry(so["id"])
    assert entry and entry["status"] == "pending" and entry["requested_price"] == 1000
    assert doc["items"][0]["price"] == normal                                           # SO lahir harga normal
    pra = DB.price_approvals.find_one({"id": entry["ref_id"]}, {"_id": 0})
    assert pra["scope"] == "order" and pra["so_id"] == so["id"]                         # bukan harga langganan
    c, r = u["sadm"].call("POST", f"/sales-orders/{so['id']}/review-release", {"note": "uji"})
    assert c == 200, r
    assert r["released"] is False and r["release_state"]["waiting"] == "acc" and r["order"]["status"] == "waiting_approval"
    assert _tasks(so["id"]) == 0
    c, r = u["mgr"].call("POST", f"/sales-orders/{so['id']}/approvals/{entry['id']}/decide", {"decision": "approve"})
    assert c == 200, r
    doc = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert doc["status"] == "confirmed" and doc["items"][0]["price"] == 1000            # dilepas otomatis, harga ACC
    assert _tasks(so["id"]) >= 1 and doc["release"]["released_at"]


def test_e10_harga_ditolak_lanjut_harga_normal_lalu_lepas_otomatis(u):
    so = _so(u, requested_price=1000)
    _, entry = _entry(so["id"])
    assert u["sadm"].call("POST", f"/sales-orders/{so['id']}/review-release", {})[0] == 200
    c, r = u["mgr"].call("POST", f"/sales-orders/{so['id']}/approvals/{entry['id']}/decide",
                         {"decision": "reject", "notes": "minimal harga lebih tinggi"})
    assert c == 200, r
    doc = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert doc["status"] == "waiting_approval" and _tasks(so["id"]) == 0
    c, r = u["sales"].call("POST", f"/sales-orders/{so['id']}/approvals/{entry['id']}/continue-normal-price")
    assert c == 200, r
    assert r["order"]["status"] == "confirmed" and float(r["order"]["items"][0]["price"]) == float(so["items"][0]["price"])


def test_e8_tahan_dulu_lalu_lepas(u):
    so = _so(u)
    c, r = u["sadm"].call("POST", f"/sales-orders/{so['id']}/review-release", {"hold": True})
    assert c == 200 and r["released"] is False and r["release_state"]["hold"] is True, r
    assert _tasks(so["id"]) == 0
    c, r = u["sadm"].call("POST", f"/sales-orders/{so['id']}/release")
    assert c == 200 and r["released"] is True and r["order"]["status"] == "confirmed", r


def test_e8_acc_sebelum_diperiksa_dilepas_saat_diperiksa(u):
    so = _so(u, requested_price=1000)
    _, entry = _entry(so["id"])
    assert u["mgr"].call("POST", f"/sales-orders/{so['id']}/approvals/{entry['id']}/decide", {"decision": "approve"})[0] == 200
    doc = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert doc["status"] == "approved" and _tasks(so["id"]) == 0                        # belum diperiksa → belum lepas
    c, r = u["sadm"].call("POST", f"/sales-orders/{so['id']}/review-release", {})
    assert c == 200 and r["released"] is True and r["order"]["status"] == "confirmed", r


def test_e10_harga_khusus_tanpa_alasan_ditolak(u):
    c, b = u["sales"].call("POST", "/sales-orders", {
        "customer_id": base.CUST, "shipping_address_id": "", "entity_id": base.ENT, "confirm_mixed_lot": True,
        "items": [{"product_id": base._product(), "quantity": 5, "unit": "yard", "requested_price": 1000}]})
    assert c == 400 and "Alasan" in str(b), b


# ─── A2/F1 — paket potong sample/catalogue: potong semua → terima semua → kirim SATU Surat Jalan ─────────────
@pytest.fixture(scope="module")
def g():
    return {k: base.Api(e) for k, e in (("wh", "warehouse@kainnusantara.id"), ("smp", "sampleadmin@kainnusantara.id"),
                                       ("whadm", "wh.admin@kainnusantara.id"))}


def test_a2_potong_semua_lalu_terima_semua_satu_klik(g):
    so = DB.sales_orders.find_one({"number": "KSC/SOS-00002"}, {"_id": 0, "id": 1, "status": 1})
    if not so:
        pytest.skip("SOS-00002 tidak ada di salinan data acuan")
    if so["status"] == "approved":
        c, b = g["smp"].call("POST", f"/sample-orders/{so['id']}/confirm")
        assert c == 200, b
    tasks = list(DB.wms_tasks.find({"order_id": so["id"], "task_subtype": "sample_cut"}, {"_id": 0}))
    assert tasks, "tugas potong tidak lahir"
    tasks = [t for t in tasks if not float(t.get("picked_qty") or 0)]
    if not tasks:
        pytest.skip("SOS-00002 sudah dipotong oleh run sebelumnya — salin ulang DB uji untuk mengulang")
    c, r = g["wh"].call("POST", f"/outbound/so/{so['id']}/cut-samples", {"warehouse_id": tasks[0]["warehouse_id"]})
    assert c == 200, r
    assert len(r["cut"]) + len(r["failed"]) == len(tasks) and r["cut"], r
    c, r = g["smp"].call("POST", f"/cutting/orders/{so['id']}/receive", {})
    assert c == 200 and r["received"] == len([t for t in r.get("failed", [])]) + r["received"], r
    left = DB.wms_tasks.count_documents({"order_id": so["id"], "roll_id": {"$nin": [None, ""]},
                                         "cutting_handoff.received_at": {"$exists": False}})
    assert left == 0


def test_a2_kirim_semua_tugas_pesanan_satu_nomor_sj(g):
    so = DB.sales_orders.find_one({"number": "KSC/SOS-00005"}, {"_id": 0, "id": 1})
    tasks = list(DB.wms_tasks.find({"order_id": so["id"], "flow_type": "outbound"}, {"_id": 0}))
    ready = [t for t in tasks if t.get("status") != "dispatched" and (t.get("cutting_handoff") or {}).get("received_at")]
    if len(ready) < 2:
        pytest.skip("SOS-00005 di salinan data tidak lagi punya ≥2 baris siap kirim")
    wh = ready[0]["warehouse_id"]
    g["whadm"].call("POST", f"/outbound/so/{so['id']}/loading-check/override",
                    {"reason": "uji trial 22 okt — tanpa perangkat RFID, validasi manual"})
    c, r = g["wh"].call("POST", f"/outbound/so/{so['id']}/dispatch-batch", params={"warehouse_id": wh})
    assert c == 200, r
    nums = {s["shipment_no"] for s in DB.shipments.find({"batch_id": r["batch_id"]}, {"_id": 0, "shipment_no": 1})}
    assert nums == {r["shipment_no"]} and r["lines"] == len([t for t in ready if t["warehouse_id"] == wh])


# ─── E9/F5 — SPK QC 4-point tersendiri: lembar inspect (interval + kode), STDRT, yard per grade, tolak = tahan ────
def test_e9_spk_qc_4point_tersendiri_tolak_menahan_roll():
    qc = base.Api("qc@kainnusantara.id")
    rolls = list(DB.inventory_rolls.find({"owner_entity_id": base.ENT, "status": "available", "earmarked_for": {"$in": [None, ""]},
                                          "length_remaining": {"$gt": 20}}, {"_id": 0, "id": 1}).limit(2))
    if len(rolls) < 2:
        pytest.skip("roll tersedia tidak cukup di salinan data")
    c, doc = qc.call("POST", "/inspections/qc-4point", {"roll_ids": [r["id"] for r in rolls]})
    assert c == 200 and doc["kind"] == "qc_4point" and len(doc["lines"]) == 2, doc
    l1, l2 = doc["lines"]
    c, b = qc.call("POST", f"/inspections/{doc['id']}/lines/{l1['id']}/inspect", {"part": "md_quality", "color_result": "sesuai"})
    assert c in (400, 403), b                                              # SPK QC tidak menerima bagian MD
    c, b = qc.call("POST", f"/inspections/{doc['id']}/lines/{l1['id']}/inspect", {
        "part": "qc", "inspect_length_yard": 100, "width_actual": 147.32,          # 58 inci
        "defects": [{"interval": 0, "code": "CG", "point_value": 2, "count": 1},
                    {"interval": 2, "code": "KO", "point_value": 4, "count": 1}],
        "yard_split": {"A": 70, "A1": 0, "B": 30}, "repair_note": "potong 30-45", "remark": "noda KO", "decision": "tolak"})
    assert c == 200, b
    ln = next(x for x in b["lines"] if x["id"] == l1["id"])
    assert ln["stdrt"] == round(6 * 3600 / (100 * 58), 2) and ln["yard_split"] == {"A": 70, "A1": 0, "B": 30}
    assert ln["qc_remark"] == "noda KO" and ln["repair_note"] == "potong 30-45"
    c, b = qc.call("POST", f"/inspections/{doc['id']}/lines/{l2['id']}/inspect", {"part": "qc", "inspect_length_yard": 50})
    assert c == 200, b
    c, b = qc.call("POST", f"/inspections/{doc['id']}/finish", {"decision": "terima", "remark": "lulus kecuali roll noda"})
    assert c == 200, b
    st = {r["id"]: r["status"] for r in DB.inventory_rolls.find({"id": {"$in": [l1["roll_id"], l2["roll_id"]]}}, {"_id": 0, "id": 1, "status": 1})}
    assert st[l2["roll_id"]] == "available" and st[l1["roll_id"]] != "available"      # gagal QC → ditahan


def test_e9_spk_penerimaan_baru_md_quality_saja():
    """SPK yang lahir otomatis saat kedatangan masuk karantina = MD Quality saja; bagian QC ditolak; rencana QC bawaan
    'tidak wajib' → SPK MD bisa ditutup (lepas karantina) tanpa menunggu QC 4-point."""
    import test_f14_spk_one_decision as f14
    u = {k: base.Api(e) for k, e in (("mgr", "manager@kainnusantara.id"), ("wh", "warehouse@kainnusantara.id"),
                                    ("whadm", "wh.admin@kainnusantara.id"), ("qc", "qc@kainnusantara.id"),
                                    ("mdq", "mdquality@kainnusantara.id"), ("adm", "admin@kainnusantara.id"))}
    _, task, spk = f14._po_in_quarantine(u, rolls=2)
    assert spk["md_only"] is True
    spk = f14._inspect_all(u, spk)
    c, b = u["qc"].call("POST", f"/inspections/{spk['id']}/lines/{spk['lines'][0]['id']}/inspect", {"part": "qc", "defects": []})
    assert c == 400 and "SPK QC 4-point" in str(b), b
    c, b = u["qc"].call("POST", f"/inspections/{spk['id']}/finish", {"decision": "terima", "remark": "MD lulus"})
    assert c == 200 and (b.get("quarantine_result") or {}).get("accepted_qty", 0) > 0, b
