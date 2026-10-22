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
import uuid

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
        "yard_split": {"A": 70, "A1": 0, "B": 30}, "repair_note": "potong 30-45", "remark": "noda KO", "decision": "tolak",
        "grade": "B"})
    assert c == 200, b
    ln = next(x for x in b["lines"] if x["id"] == l1["id"])
    assert ln["stdrt"] == round(6 * 3600 / (100 * 58), 2) and ln["yard_split"] == {"A": 70, "A1": 0, "B": 30}
    assert ln["qc_remark"] == "noda KO" and ln["repair_note"] == "potong 30-45"
    # F5 (keputusan pemilik) — grade roll diisi petugas; tanpa grade ditolak, roll tidak disentuh.
    g0 = DB.inventory_rolls.find_one({"id": l2["roll_id"]}, {"_id": 0, "grade": 1, "inspection": 1})
    c, b = qc.call("POST", f"/inspections/{doc['id']}/lines/{l2['id']}/inspect", {"part": "qc", "inspect_length_yard": 50})
    assert c == 400 and "Isi grade roll" in str(b), b
    assert DB.inventory_rolls.find_one({"id": l2["roll_id"]}, {"_id": 0, "grade": 1, "inspection": 1}) == g0
    c, b = qc.call("POST", f"/inspections/{doc['id']}/lines/{l2['id']}/inspect", {"part": "qc", "inspect_length_yard": 50, "grade": "A1"})
    assert c == 200, b
    ln2 = next(x for x in b["lines"] if x["id"] == l2["id"])
    assert ln2["grade_after"] == "A1" and ln2["grade_rule"]["grade_source"] == "user"
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


# ─── E5 — rencana pemenuhan memakai ROLL PILIHAN (seperti di pesanan), bukan jumlah ketik bebas ──────────
def test_e5_pemenuhan_stok_sendiri_memakai_roll_pilihan():
    sadm = base.Api("salesadmin@kainnusantara.id")
    cand = None
    for so in DB.sales_orders.find({"entity_id": base.ENT, "status": {"$in": ["reserved", "waiting_stock", "approved"]},
                                    "has_backorder": True}, {"_id": 0, "id": 1}):
        c, opts = sadm.call("GET", f"/sales-admin/orders/{so['id']}/fulfillment-plan")
        if c != 200:
            continue
        ln = next((x for x in opts.get("lines") or [] if x.get("own_rolls")), None)
        if ln:
            cand = (so["id"], ln)
            break
    if not cand:
        # Data acuan: SO backorder memang tanpa stok sendiri → tambahkan DUA roll tersedia (salinan) di DB uji.
        so = DB.sales_orders.find_one({"entity_id": base.ENT, "has_backorder": True,
                                       "status": {"$in": ["reserved", "waiting_stock", "approved"]}}, {"_id": 0})
        if not so:
            pytest.skip("tidak ada SO backorder di salinan data")
        bo = next(b for b in so["backorders"] if float(b.get("backorder_qty") or 0) > 0)
        tpl = DB.inventory_rolls.find_one({"product_id": bo["product_id"]}, {"_id": 0})
        if not tpl:
            pytest.skip("tidak ada roll contoh untuk produk backorder")
        for i in range(2):
            DB.inventory_rolls.insert_one({**tpl, "id": f"roll_uji_e5_{uuid.uuid4().hex[:8]}", "roll_no": f"UJI-E5-{uuid.uuid4().hex[:5]}",
                                           "owner_entity_id": base.ENT, "status": "available", "length_remaining": 40.0,
                                           "length_initial": 40.0, "length_reserved": 0, "reserved_ref": None,
                                           "earmarked_for": None, "created_at": f"2026-10-2{i}T00:00:00+00:00"})
        c, opts = sadm.call("GET", f"/sales-admin/orders/{so['id']}/fulfillment-plan")
        assert c == 200, opts
        ln = next((x for x in opts.get("lines") or [] if x.get("own_rolls")), None)
        assert ln, opts
        cand = (so["id"], ln)
    so_id, ln = cand
    pick = [r for r in ln["own_rolls"][::-1]][:1]          # sengaja roll TERAKHIR (bukan FIFO)
    qty = min(pick[0]["length_remaining"], ln["backorder_qty"])
    c, b = sadm.call("POST", f"/sales-admin/orders/{so_id}/fulfillment-plan", {
        "note": "uji E5", "lines": [{"product_id": ln["product_id"], "stock_qty": qty,
                                     "stock_roll_ids": [pick[0]["id"]]}]})
    assert c == 200, b
    roll = DB.inventory_rolls.find_one({"id": pick[0]["id"]}, {"_id": 0, "status": 1, "reserved_ref": 1, "length_reserved": 1})
    child = DB.inventory_rolls.find_one({"parent_roll_id": pick[0]["id"], "reserved_ref.id": so_id}, {"_id": 0, "id": 1})
    assert (roll.get("reserved_ref") or {}).get("id") == so_id or child or float(roll.get("length_reserved") or 0) > 0, roll


# ─── B3 — Barang Masuk isi manual: dibuka dari PO → nomor PO di kepala SJ; target membawa kode/nama versi supplier ──
def test_b3_grn_dari_po_nomor_po_terisi_target_berisi_versi_supplier(g):
    t = DB.wms_tasks.find_one({"entity_id": base.ENT, "flow_type": "inbound", "po_id": {"$gt": ""},
                               "status": {"$in": ["waiting_goods", "receiving"]},
                               "grn_active_id": {"$in": [None, ""]}}, {"_id": 0})
    if not t:
        pytest.skip("tidak ada tugas kedatangan PO terbuka di salinan data")
    po = DB.purchase_orders.find_one({"id": t["po_id"]}, {"_id": 0, "supplier_id": 1, "po_number": 1})
    DB.supplier_items.update_one({"supplier_id": po["supplier_id"], "product_id": t["product_id"]},
                                 {"$setOnInsert": {"id": f"sit_uji_{uuid.uuid4().hex[:6]}", "status": "active",
                                                   "supplier_sku": "SUP-UJI-1", "supplier_item_name": "Kain Uji Versi Supplier"}},
                                 upsert=True)
    si = DB.supplier_items.find_one({"supplier_id": po["supplier_id"], "product_id": t["product_id"]}, {"_id": 0})
    c, grn = g["whadm"].call("POST", "/goods-receipts", {"partner_type": "supplier", "partner_id": po["supplier_id"],
                                                        "warehouse_id": t["warehouse_id"], "po_ids": [t["po_id"]]})
    assert c == 200, grn
    try:
        assert grn["dn"]["po_refs"] == [po["po_number"]]                       # dulu kosong walau dibuka dari PO
        c, targets = g["whadm"].call("GET", f"/goods-receipts/{grn['id']}/targets")
        assert c == 200, targets
        tg = next(x for x in targets if x.get("task_id") == t["id"])
        assert tg["supplier_item_name"] == si.get("supplier_item_name", "")
        assert tg["supplier_sku"] == (t.get("supplier_sku") or si.get("supplier_sku", ""))
    finally:
        g["whadm"].call("POST", f"/goods-receipts/{grn['id']}/cancel",
                        {"expected_version": grn["version"], "reason": "uji trial 22 okt B3"})


# ─── Audit pola Lurik — retur pembelian: qty & harga satuan PO dikonversi ke satuan dasar ─────────────────────
def test_audit_retur_pembelian_satuan_po_dikonversi_ke_satuan_dasar():
    """Retur 100 meter @ Rp 95.000/meter untuk produk bersatuan dasar yard → tersimpan 109,36 yard @ Rp 86.868/yard
    (subtotal sama). Dulu 100 tersimpan sebagai 100 yard dan harga per meter dipakai per yard."""
    adm = base.Api("admin@kainnusantara.id")
    prod = DB.products.find_one({"base_unit": "yard", "is_active": {"$ne": False}}, {"_id": 0, "id": 1})
    sup = DB.suppliers.find_one({"entity_id": {"$in": [base.ENT, "", None]}}, {"_id": 0, "id": 1}) or DB.suppliers.find_one({}, {"_id": 0, "id": 1})
    wh = DB.warehouses.find_one({"owner_entity_id": base.ENT}, {"_id": 0, "id": 1}) or DB.warehouses.find_one({}, {"_id": 0, "id": 1})
    if not (prod and sup and wh):
        pytest.skip("produk yard / supplier / gudang tidak ada di salinan data")
    c, b = adm.call("POST", "/purchase-returns", {"supplier_id": sup["id"], "warehouse_id": wh["id"], "entity_id": base.ENT,
                                                  "reason": "uji audit satuan", "items": [
                                                      {"product_id": prod["id"], "quantity": 100, "unit": "meter",
                                                       "price": 95000, "reason": "cacat", "condition": "damaged"}]})
    assert c == 200, b
    it = b["items"][0]
    assert it["unit"] == "yard" and it["quantity"] == pytest.approx(100 / 0.9144, abs=0.01)
    assert it["price"] == pytest.approx(95000 * 0.9144, rel=1e-3)
    assert it["subtotal"] == pytest.approx(9500000, rel=1e-3)
    assert it["quantity_input"] == 100 and it["unit_input"] == "meter"
