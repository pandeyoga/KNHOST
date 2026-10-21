"""F-14 (uji pra-UAT 2026-10-21, keputusan owner Q-03a) — SATU keputusan: SPK penerimaan memutus karantina.

Reproduksi INS-00019: SPK kedatangan ditutup *Diterima*, tetapi roll tetap karantina sampai ada keputusan kedua
di antrean QC (`/inbound/tasks/{id}/qc-decision`). Kini menutup SPK penerimaan PO sekaligus memutus karantina
(roll diterima → tersedia dengan grade 4-point; roll ditolak → retur supplier/rusak), antrean karantina menunjuk
SPK-nya dan menolak keputusan kedua selama SPK terbuka; SPK yang sudah memutus karantina tidak bisa dibuka kembali.
Alur nyata lewat API akun peran (data acuan): Manajer buat & setujui PO → Gudang scan terima → selesai (karantina)
→ Admin Gudang tugaskan SPK ke QC → QC mulai, periksa 4-point, tutup SPK.
Jalankan: cd /app/backend && python -m pytest tests/test_f14_spk_one_decision.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402 — Api + koneksi DB bersama

DB = base.DB
ENT = "ent_ksc"


@pytest.fixture(scope="module")
def u():
    return {k: base.Api(e) for k, e in (("mgr", "manager@kainnusantara.id"), ("wh", "warehouse@kainnusantara.id"),
                                       ("whadm", "wh.admin@kainnusantara.id"), ("qc", "qc@kainnusantara.id"),
                                       ("adm", "admin@kainnusantara.id"))}


def _po_in_quarantine(u, rolls=3, per_roll=50.0):
    prod = DB.products.find_one({"sku": "DMO-GRY-WVN-001"}, {"_id": 0, "id": 1})
    sup = DB.suppliers.find_one({"name": "CV Grey Mandiri Majalaya"}, {"_id": 0, "id": 1, "name": 1})
    wh = DB.warehouses.find_one({"code": "WH-JKT"}, {"_id": 0, "id": 1})
    if not (prod and sup and wh):
        pytest.skip("master demo (DMO-GRY-WVN-001 / CV Grey Mandiri / WH-JKT) tidak ada — jalankan restore data acuan")
    c, po = u["mgr"].call("POST", "/purchase-orders", {
        "supplier_id": sup["id"], "supplier_name": sup["name"], "warehouse_id": wh["id"], "entity_id": ENT,
        "items": [{"product_id": prod["id"], "quantity": rolls * per_roll, "unit": "yard", "price": 14000, "expected_grade": "A"}],
        "tax_mode": "ppn", "notes": "uji F-14"})
    assert c == 200, po
    if po.get("status") in ("pending_approval", "waiting_approval", "draft"):
        c, po = u["mgr"].call("POST", f"/purchase-orders/{po['id']}/approve", {})
        assert c == 200, po
    task = DB.wms_tasks.find_one({"po_id": po["id"], "flow_type": "inbound"}, {"_id": 0})
    assert task, "tugas penerimaan tidak terbentuk"
    tag = uuid.uuid4().hex[:6].upper()
    for i in range(rolls):
        c, b = u["wh"].call("POST", f"/inbound/tasks/{task['id']}/scan-receive", {
            "product_id": prod["id"], "actual_qty": per_roll, "batch": f"F14-{tag}-{i}", "lot": f"F14-LOT-{tag}-{i}",
            "grade": "A", "roll_id": f"F14-{tag}-{i:02d}"})
        assert c == 200, b
    c, b = u["wh"].call("POST", f"/inbound/tasks/{task['id']}/complete", {   # satu baris = satu roll fisik
        "dye_lot": f"F14-DL-{tag}", "grade": "A",
        "rolls": [{"length": per_roll, "dye_lot": f"F14-DL-{tag}", "grade": "A"} for _ in range(rolls)]})
    assert c == 200, b
    task = DB.wms_tasks.find_one({"id": task["id"]}, {"_id": 0})
    assert task["status"] == "qc_pending", task["status"]
    spk = DB.inspections.find_one({"task_id": task["id"]}, {"_id": 0})
    assert spk, "SPK penerimaan tidak lahir otomatis"
    assert len(spk["lines"]) == rolls, ("satu baris GRN = satu roll", spk["lines"])
    return po, task, spk


def _inspect_all(u, spk):
    qc_user = DB.users.find_one({"email": "qc@kainnusantara.id"}, {"_id": 0, "id": 1})
    c, b = u["whadm"].call("POST", f"/inspections/{spk['id']}/assign", {"assigned_to": qc_user["id"], "bagian": "QC"})
    assert c == 200, b
    c, b = u["qc"].call("POST", f"/inspections/{spk['id']}/start", {})
    assert c == 200, b
    for ln in spk["lines"]:
        c, b = u["qc"].call("POST", f"/inspections/{spk['id']}/lines/{ln['id']}/inspect",
                            {"part": "qc", "defects": [], "remark": "uji F-14 bersih"})
        assert c == 200, b
    return DB.inspections.find_one({"id": spk["id"]}, {"_id": 0})


def _rolls(task_id_or_ids):
    q = {"id": {"$in": task_id_or_ids}} if isinstance(task_id_or_ids, list) else {"qc_task_id": task_id_or_ids}
    return list(DB.inventory_rolls.find(q, {"_id": 0, "id": 1, "roll_no": 1, "status": 1, "grade": 1}))


def test_tutup_spk_terima_melepas_karantina_dan_antrean_menunjuk_spk(u):
    po, task, spk = _po_in_quarantine(u)
    roll_ids = [ln["roll_id"] for ln in spk["lines"]]
    c, queue = u["qc"].call("GET", "/inbound/qc/queue")
    assert c == 200, queue
    row = next(t for t in queue if t["id"] == task["id"])
    assert row["inspection"]["number"] == spk["number"], row.get("inspection")          # antrean menunjuk SPK
    c, b = u["qc"].call("POST", f"/inbound/tasks/{task['id']}/qc-decision",
                        {"accept_qty": 150, "reject_qty": 0, "reason": "keputusan kedua", "accept_grade": "A"})
    assert c == 409 and spk["number"] in b["detail"], b                                  # tidak ada keputusan kedua

    spk = _inspect_all(u, spk)
    c, out = u["qc"].call("POST", f"/inspections/{spk['id']}/finish", {"decision": "terima"})   # QC: qc.release
    assert c == 200, out
    assert out["quarantine_result"]["accepted_qty"] == 150 and out["quarantine_result"]["rejected_qty"] == 0, out
    assert DB.wms_tasks.find_one({"id": task["id"]}, {"_id": 0, "status": 1})["status"] == "completed"
    rolls = _rolls(roll_ids)
    assert rolls and all(r["status"] == "available" for r in rolls), rolls             # dulu: tetap "quarantine"
    assert all(r["grade"] for r in rolls), rolls
    c, b = u["adm"].call("POST", f"/inspections/{spk['id']}/reopen", {"reason": "uji F-14 coba buka kembali SPK"})
    assert c == 400 and "karantina" in b["detail"], b


def test_terima_sebagian_roll_tertentu_diretur_ke_supplier(u):
    po, task, spk = _po_in_quarantine(u)
    spk = _inspect_all(u, spk)
    bad = spk["lines"][1]["roll_id"]
    c, b = u["qc"].call("POST", f"/inspections/{spk['id']}/finish",
                        {"decision": "terima_sebagian", "rejected_roll_ids": [bad]})
    assert c == 400 and "retur" in b["detail"], b                                         # disposisi wajib
    c, b = u["qc"].call("POST", f"/inspections/{spk['id']}/finish", {"decision": "terima_sebagian", "reject_disposition": "return"})
    assert c == 400, b                                                                    # roll tolak wajib ditandai
    c, out = u["qc"].call("POST", f"/inspections/{spk['id']}/finish",
                          {"decision": "terima_sebagian", "rejected_roll_ids": [bad], "reject_disposition": "return"})
    assert c == 200, out
    qr = out["quarantine_result"]
    assert qr["accepted_qty"] == 100 and qr["rejected_qty"] == 50 and qr["purchase_return"]["number"], qr
    st = {r["id"]: r["status"] for r in _rolls([ln["roll_id"] for ln in spk["lines"]])}
    assert st[bad] != "available" and st[bad] != "quarantine", st                       # roll YANG DITANDAI yang diretur
    assert all(s == "available" for rid, s in st.items() if rid != bad), st


def test_tolak_semua_jadi_barang_rusak(u):
    po, task, spk = _po_in_quarantine(u, rolls=2)
    spk = _inspect_all(u, spk)
    c, out = u["qc"].call("POST", f"/inspections/{spk['id']}/finish", {
        "decision": "tolak", "reject_disposition": "damaged",
        "remark": "Kain berlubang di banyak titik, tidak layak jual (uji F-14)"})
    assert c == 200, out
    assert out["quarantine_result"]["rejected_qty"] == 100 and out["quarantine_result"]["accepted_qty"] == 0, out
    assert all(r["status"] == "damaged" for r in _rolls([ln["roll_id"] for ln in spk["lines"]]))
    assert DB.wms_tasks.find_one({"id": task["id"]}, {"_id": 0, "status": 1})["status"] == "qc_rejected"


def test_gagal_memutus_karantina_spk_tetap_terbuka(u):
    po, task, spk = _po_in_quarantine(u, rolls=2)
    spk = _inspect_all(u, spk)
    c, b = u["qc"].call("POST", f"/inspections/{spk['id']}/finish", {
        "decision": "tolak", "remark": "Kain berlubang di banyak titik, tidak layak jual (uji F-14)"})
    assert c == 400, b                                                                    # tanpa disposisi
    doc = DB.inspections.find_one({"id": spk["id"]}, {"_id": 0, "status": 1})
    assert doc["status"] == "in_progress", doc                                           # tidak "ditutup tanpa karantina"
    assert all(r["status"] == "quarantine" for r in _rolls([ln["roll_id"] for ln in spk["lines"]]))
