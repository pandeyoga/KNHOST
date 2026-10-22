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
