"""Lapor Bayar CBD — penyiapan data tangkapan (lingkungan uji lokal, data acuan; BUKAN data nyata).

Lewat API akun peran: Sales membuat dua pesanan (termin CBD dan DP50) → Admin Sales "Periksa & lepas"
(`review-release`; bila butuh ACC, Manajer menyetujui) → pesanan berhenti di tahap "Bayar dicek Finance"
(`approved` + `pay_hold`, `release.waiting = "bayar"`), belum ada tugas gudang.
Hasil (id & nomor) ditulis ke `lb_data.json` di folder ini untuk `tangkap_lb.js`.

Jalankan dari host dengan backend lokal menyala (:8001):  python siapkan_lb.py
Pulihkan data acuan sesudahnya:  bash scripts/dev_restore_demo.sh (atau restore_local_demo.sh).
"""
import json
import os

import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT, CUST, PW = "ent_ksc", "cust_toko_kain", "demo12345"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lb_data.json")


def masuk(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": PW}, timeout=30)
    r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}

    def call(method, path, js=None):
        r = requests.request(method, f"{BASE}{path}", json=js, headers=h, timeout=120)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text[:300]
    return call


def produk(lewati=()):
    """Produk jual KSC ber-roll cukup & bebas reservasi (sama dengan uji hidup F-10)."""
    pipa = [{"$match": {"owner_entity_id": ENT, "status": "available", "length_remaining": {"$gt": 20},
                        "length_reserved": {"$not": {"$gt": 0}}}},
            {"$group": {"_id": "$product_id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gte": 3}}}, {"$limit": 200}]
    for g in DB.inventory_rolls.aggregate(pipa):
        if g["_id"] in lewati:
            continue
        p = DB.products.find_one({"id": g["_id"], "is_active": {"$ne": False}, "base_unit": "yard",
                                  "stage": {"$in": ["finished", None]}}, {"_id": 0, "id": 1, "name": 1})
        if p:
            return p
    raise SystemExit("stok roll tidak cukup — pulihkan data acuan dulu")


def pesanan_tertahan(sales, sadm, mgr, termin, pid):
    c, so = sales("POST", "/sales-orders", {
        "customer_id": CUST, "shipping_address_id": "", "entity_id": ENT, "payment_term_code": termin,
        "items": [{"product_id": pid, "quantity": 12.5, "unit": "yard"}], "confirm_mixed_lot": True,
        "fulfillment_method": "kirim", "qc_request": "none"})
    assert c == 200, so
    c, b = sadm("POST", f"/sales-orders/{so['id']}/review-release", {"note": "Tangkapan Lapor Bayar", "hold": False})
    assert c == 200, b
    s = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    if s["status"] == "waiting_approval":
        c, b = mgr("POST", f"/sales-orders/{so['id']}/approve")
        assert c == 200, b
        s = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert s["status"] == "approved" and s.get("pay_hold") and (s.get("release") or {}).get("waiting") == "bayar", (
        s["status"], s.get("pay_hold"), s.get("release"))
    assert not DB.wms_tasks.find_one({"order_id": so["id"], "flow_type": "outbound"}), "tugas gudang lahir sebelum bayar"
    return {"id": so["id"], "number": s["number"], "term": termin, "grand_total": s.get("grand_total"),
            "due_at": s["pay_hold"].get("due_at")}


def main():
    sales, sadm, mgr = (masuk("sales@kainnusantara.id"), masuk("salesadmin@kainnusantara.id"),
                        masuk("manager@kainnusantara.id"))
    p1 = produk()
    cbd = pesanan_tertahan(sales, sadm, mgr, "CBD", p1["id"])
    p2 = produk(lewati={p1["id"]})
    dp = pesanan_tertahan(sales, sadm, mgr, "DP50", p2["id"])
    c, g = sadm("GET", f"/sales-orders/{dp['id']}/dispatch-payment-gate")
    assert c == 200, g
    dp["shortfall"] = g.get("shortfall")
    c, g = sadm("GET", f"/sales-orders/{cbd['id']}/dispatch-payment-gate")
    cbd["shortfall"] = g.get("shortfall")
    data = {"cbd": cbd, "dp": dp}
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
