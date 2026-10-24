"""FE-01 lanjutan — keputusan owner 2026-10-21: batal per item Pesanan Khusus.

Alur lewat API resmi (buat OD → approve → batal item → ACC → kunci → konversi SO). Hanya hasil R&D per
item (sample `decided` + harga kontrak) yang disiapkan langsung, sama dengan tes FE-01. Bagian pengadaan
memakai helper tes LN-033 (realisasi PO/MKO lewat API).
Jalankan: cd /app/backend && python -m pytest tests/test_fe01_od_cancel_item.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest  # noqa: E402
import requests  # noqa: E402
import test_l03_ln033_fulfillment as m  # noqa: E402

BASE, DB = m.BASE, m.DB


def _so(H, od_id):
    """UAT 24 Okt (P2.1) — SO pesanan khusus lahir SAAT harga dikunci; konversi manual hanya bila belum ada."""
    so_id = (DB.special_orders.find_one({"id": od_id}, {"linked_sales_order_id": 1}) or {}).get("linked_sales_order_id")
    if not so_id:
        cv = requests.post(f"{BASE}/special-orders/{od_id}/convert-to-so", json={}, headers=H["admin"])
        assert cv.status_code == 200, cv.text
        return cv.json()["sales_order"]
    r = requests.get(f"{BASE}/sales-orders/{so_id}", headers=H["admin"])
    assert r.status_code == 200, r.text
    return r.json()
ENT, CUST = "ent_ksc", "cust_toko_kain"
TAG = uuid.uuid4().hex[:6]
SUP = DB.suppliers.find_one({}, {"_id": 0, "id": 1, "name": 1})
H = m.H
cleanup_ln033 = m.cleanup
OD_IDS: list = []
PRODUCT_FIELDS = ("price", "harga_pokok", "exclusive_customer_id", "exclusive_customer_name", "special_order_id",
                  "special_order_number", "catalog_scope", "status")


def _stocked(n):
    rows = list(DB.inventory_rolls.aggregate([
        {"$match": {"owner_entity_id": ENT, "status": "available", "unit": "yard", "grade": "A", "stage": "finished"}},
        {"$group": {"_id": "$product_id", "q": {"$sum": "$length_remaining"}}},
        {"$match": {"q": {"$gte": 300}}}, {"$sort": {"q": -1}}, {"$limit": n}]))
    return [DB.products.find_one({"id": r["_id"]}, {"_id": 0, "id": 1, "sku": 1}) for r in rows]


PA, PB, PC = _stocked(3)
SNAP = {p["id"]: DB.products.find_one({"id": p["id"]}, {"_id": 0, **{f: 1 for f in PRODUCT_FIELDS}}) for p in (PA, PB, PC)}


@pytest.fixture(scope="module", autouse=True)
def cleanup_od():
    yield
    adm = m._login("admin@kainnusantara.id", "demo12345")
    for so in DB.sales_orders.find({"source_special_order_id": {"$in": OD_IDS}, "status": {"$ne": "cancelled"}}, {"_id": 0, "id": 1}):
        requests.post(f"{BASE}/sales-orders/{so['id']}/cancel", json={"reason": "TEST batal item bersih-bersih"}, headers=adm)
    DB.md_samples.delete_many({"special_order_id": {"$in": OD_IDS}})
    spec_ids = [i.get("spec_id") for od in DB.special_orders.find({"id": {"$in": OD_IDS}}, {"_id": 0, "items.spec_id": 1})
                for i in od.get("items") or [] if i.get("spec_id")]
    DB.md_specs.delete_many({"$or": [{"special_order_id": {"$in": OD_IDS}}, {"id": {"$in": spec_ids}}]})
    DB.notifications.delete_many({"type": "special_order_item_cancelled", "ref": {"$regex": "|".join(f"^{x}:" for x in OD_IDS) or "^$"}})
    DB.special_orders.delete_many({"id": {"$in": OD_IDS}})
    for pid, snap in SNAP.items():
        unset = {f: "" for f in PRODUCT_FIELDS if f not in snap}
        DB.products.update_one({"id": pid}, {"$set": snap, **({"$unset": unset} if unset else {})})


def _approved(Hh, products, qtys=(100, 200, 300)):
    items = [{"source_type": "parent_product", "source_product_id": p["id"], "description": f"TEST BATAL {i + 1} {TAG}",
              "request_types": ["labdip"], "quantity": q, "unit": "yard", "target_price": 1000}
             for i, (p, q) in enumerate(zip(products, qtys))]
    r = requests.post(f"{BASE}/special-orders", json={"customer_id": CUST, "title": f"TEST_BATAL_{TAG}", "entity_id": ENT,
                                                     "expected_delivery": "2026-12-31", "items": items,
                                                     "submit_for_approval": True}, headers=Hh["admin"])
    assert r.status_code in (200, 201), r.text
    od_id = r.json()["id"]
    OD_IDS.append(od_id)
    for _ in range(3):
        if DB.special_orders.find_one({"id": od_id}, {"status": 1})["status"] == "confirmed":
            break
        requests.post(f"{BASE}/special-orders/{od_id}/approve", json={"notes": "TEST"}, headers=Hh["admin"])
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    assert od["status"] == "confirmed", od["status"]
    return od


def _decide(item, product, cost):
    DB.md_samples.update_one({"id": item["rnd_sample_id"]}, {"$set": {
        "status": "decided", "decision": {"product_id": product["id"], "product_sku": product["sku"], "supplier_id": SUP["id"],
                                          "supplier_name": SUP["name"], "price": float(cost)}}})


def _cancel(Hh, od_id, item_id, reason="Pelanggan tidak jadi item ini", who="admin"):
    return requests.post(f"{BASE}/special-orders/{od_id}/items/{item_id}/cancel", json={"reason": reason}, headers=Hh[who])


# ─── Sebelum ACC: sample item batal ikut batal & tidak menahan keputusan pelanggan ─────
def test_batal_item_sebelum_acc_sampai_so(H):
    od = _approved(H, [PA, PB, PC])
    i1, i2, i3 = od["items"]
    r = _cancel(H, od["id"], i3["id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cancelled_samples"], body                      # sample R&D item 3 ikut batal
    assert DB.md_samples.find_one({"id": i3["rnd_sample_id"]})["status"] == "cancelled"
    after = DB.special_orders.find_one({"id": od["id"]}, {"_id": 0})
    it3 = next(i for i in after["items"] if i["id"] == i3["id"])
    assert it3["status"] == "cancelled" and it3["cancel_reason"].startswith("Pelanggan") and it3["cancelled_by"]
    assert len(after["items"]) == 3                              # tidak dihapus — jejak tetap
    assert after["total_amount"] == round(i1["subtotal"] + i2["subtotal"], 2)
    _decide(i1, PA, 10)
    _decide(i2, PB, 30)
    acc = requests.post(f"{BASE}/special-orders/{od['id']}/customer-decision", json={"decision": "acc"}, headers=H["admin"])
    assert acc.status_code == 200, acc.text                       # sample item batal tidak menahan ACC
    pv = requests.get(f"{BASE}/special-orders/{od['id']}/pricing", params={"margin_pct": 30}, headers=H["admin"]).json()
    assert pv["ready"] is True and [ln["item_id"] for ln in pv["items"]] == [i1["id"], i2["id"]], pv
    lk = requests.post(f"{BASE}/special-orders/{od['id']}/lock-price", json={"margin_pct": 30, "auto_po": False}, headers=H["admin"])
    assert lk.status_code == 200, lk.text
    so = _so(H, od["id"])
    assert sorted(i["product_id"] for i in so["items"]) == sorted([PA["id"], PB["id"]])
    assert PC["id"] not in [i["product_id"] for i in so["items"]]
    # keputusan owner (lanjutan): batal item SESUDAH SO boleh → baris SO keluar, reservasi lepas, total turun, MD diberi tahu
    before = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    r2 = _cancel(H, od["id"], i2["id"], reason="Pelanggan batal sesudah SO")
    assert r2.status_code == 200, r2.text
    entry = r2.json()["sales_order_line"]
    after = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert [i["product_id"] for i in after["items"]] == [PA["id"]]
    assert after["grand_total"] < before["grand_total"] and entry["grand_total_after"] == after["grand_total"]
    assert after["line_cancellations"][-1]["special_order_item_id"] == i2["id"]
    assert DB.inventory_rolls.count_documents({"reserved_ref.id": so["id"], "product_id": PB["id"]}) == 0
    assert DB.wms_tasks.count_documents({"order_id": so["id"], "product_id": PB["id"], "flow_type": "outbound",
                                         "status": {"$nin": ["cancelled", "dispatched", "completed"]}}) == 0
    md_ids = [u["id"] for u in DB.users.find({"role": "md", "status": "active"}, {"_id": 0, "id": 1})]
    notes = list(DB.notifications.find({"type": "special_order_item_cancelled", "ref": {"$regex": f"^{od['id']}:"}}, {"_id": 0}))
    assert len(notes) >= 2 and {n["recipient_user"] for n in notes} <= set(md_ids)     # dua pembatalan → dua pemberitahuan
    assert any("SO " in n["body"] and n["title"].startswith("Item 2") for n in notes)
    # item aktif terakhir tetap tidak bisa dibatalkan per item
    assert _cancel(H, od["id"], i1["id"]).status_code == 400


# ─── Sesudah kunci harga: baris item batal dibuang, harga item lain tetap ─────────────
def test_batal_item_sesudah_kunci_harga(H):
    od = _approved(H, [PA, PB, PC])
    i1, i2, i3 = od["items"]
    for it, p, c in ((i1, PA, 10), (i2, PB, 30), (i3, PC, 20)):
        _decide(it, p, c)
    assert requests.post(f"{BASE}/special-orders/{od['id']}/customer-decision", json={"decision": "acc"}, headers=H["admin"]).status_code == 200
    lk = requests.post(f"{BASE}/special-orders/{od['id']}/lock-price", json={"margin_pct": 30, "auto_po": False}, headers=H["admin"])
    assert lk.status_code == 200, lk.text
    before = {ln["item_id"]: ln for ln in DB.special_orders.find_one({"id": od["id"]})["pricing"]["items"]}
    assert _cancel(H, od["id"], i2["id"]).status_code == 200
    pr = DB.special_orders.find_one({"id": od["id"]}, {"_id": 0})
    lines = {ln["item_id"]: ln for ln in pr["pricing"]["items"]}
    assert set(lines) == {i1["id"], i3["id"]}
    for k in lines:
        assert lines[k]["total"] == before[k]["total"] and lines[k]["price_per_unit"] == before[k]["price_per_unit"]
    total = round(before[i1["id"]]["total"] + before[i3["id"]]["total"], 2)
    assert pr["pricing"]["total"] == total and pr["total_amount"] == total and pr["pricing"]["item_count"] == 2
    so = _so(H, od["id"])
    assert sorted(i["product_id"] for i in so["items"] if i.get("status") != "cancelled") == sorted([PA["id"], PC["id"]])


# ─── Sesudah SO terbit (ada pembayaran): ditolak, tidak ada yang berubah ─────────────────
def test_batal_item_sesudah_so_terbit_jadi_nota_kredit(H):
    """Keputusan owner 2026-10-21 (menggantikan aturan lama "SO terbit → ditolak"): baris keluar dan lahir nota kredit
    menunggu Finance; penjaga fisik tetap — roll baris itu sudah dipick → ditolak (jalur retur)."""
    od = _approved(H, [PA, PB], qtys=(100, 200))
    i1, i2 = od["items"]
    _decide(i1, PA, 10)
    _decide(i2, PB, 30)
    assert requests.post(f"{BASE}/special-orders/{od['id']}/customer-decision", json={"decision": "acc"}, headers=H["admin"]).status_code == 200
    assert requests.post(f"{BASE}/special-orders/{od['id']}/lock-price", json={"margin_pct": 30, "auto_po": False}, headers=H["admin"]).status_code == 200
    so_id = _so(H, od["id"])["id"]
    DB.sales_orders.update_one({"id": so_id}, {"$set": {"paid_total": 1000.0}})     # fixture: sudah ada pembayaran
    roll = DB.inventory_rolls.find_one({"reserved_ref.id": so_id, "product_id": PB["id"], "status": "reserved"}, {"_id": 0, "id": 1})
    if roll:   # penjaga fisik: roll terpick → tetap ditolak walau SO terbit
        DB.inventory_rolls.update_one({"id": roll["id"]}, {"$set": {"status": "picked"}})
        blocked = _cancel(H, od["id"], i2["id"])
        DB.inventory_rolls.update_one({"id": roll["id"]}, {"$set": {"status": "reserved"}})
        assert blocked.status_code == 409 and "dipick" in blocked.text, blocked.text
    r = _cancel(H, od["id"], i2["id"])
    assert r.status_code == 200, r.text
    cn = r.json()["credit_note"]
    assert cn and cn["status"] == "pending_finance" and cn["gross_amount"] > 0
    assert len(DB.sales_orders.find_one({"id": so_id})["items"]) == 1
    DB.sales_orders.update_one({"id": so_id}, {"$set": {"paid_total": 0.0}})


# ─── Aturan penolakan ──────────────────────────────────────────────────────────────
def test_aturan_penolakan(H):
    od = _approved(H, [PA, PB], qtys=(100, 200))
    i1, i2 = od["items"]
    assert _cancel(H, od["id"], i1["id"], reason="abc").status_code == 422          # alasan min. 5 karakter
    fin = m._login("finance@kainnusantara.id")
    r = requests.post(f"{BASE}/special-orders/{od['id']}/items/{i1['id']}/cancel", json={"reason": "TEST finance"},
                      headers={**fin, "X-Entity-Id": ENT})
    assert r.status_code == 403, r.text                                              # tanpa order.update
    assert _cancel(H, od["id"], "soi_tidak_ada").status_code == 400
    assert _cancel(H, od["id"], i1["id"]).status_code == 200
    assert _cancel(H, od["id"], i1["id"]).status_code == 409                         # sudah batal
    last = _cancel(H, od["id"], i2["id"])
    assert last.status_code == 400 and "terakhir" in last.text                       # item aktif terakhir → batalkan OD


# ─── Pengadaan: PO/MKO aktif item ikut batal lewat aturan modul asal ──────────────────
def test_batal_item_membatalkan_pengadaan_aktif(H):
    m._recipe()
    od_id, (k1, k2) = m._od(H, [m.P_SUP, m.P_MKL])
    OD_IDS.append(od_id)
    r = m._realize(H, od_id, k1)
    assert r.status_code == 200, r.text
    assert m._ful(H, od_id)[k1]["active_docs"], "item 1 harus punya dokumen pengadaan aktif"
    sadm = m._login("salesadmin.kanda@kainnusantara.id")
    denied = requests.post(f"{BASE}/special-orders/{od_id}/items/{k1}/cancel", json={"reason": "TEST tanpa izin pengadaan"},
                           headers={**sadm, "X-Entity-Id": ENT})
    assert denied.status_code in (403, 404), denied.text                              # order.update ada, od_fulfillment.cancel tidak
    ok = requests.post(f"{BASE}/special-orders/{od_id}/items/{k1}/cancel", json={"reason": "TEST pengadaan ikut batal"}, headers=H["admin"])
    assert ok.status_code == 200, ok.text
    assert ok.json()["cancelled_docs"], ok.json()
    ful = m._ful(H, od_id)
    assert k1 not in ful and k2 in ful                                                # item batal keluar dari kebutuhan pemenuhan
    hist = DB.special_orders.find_one({"id": od_id})["fulfillment"][k1]["history_docs"]
    assert any(d.get("status") == "cancelled" for d in hist)
