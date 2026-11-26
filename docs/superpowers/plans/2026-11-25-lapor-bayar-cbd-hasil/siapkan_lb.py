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


def masuk(email, ent=ENT):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": PW}, timeout=30)
    r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}

    def call(method, path, js=None):
        r = requests.request(method, f"{BASE}{path}", json=js, headers=h, timeout=120)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text[:300]
    return call


def produk(lewati=(), ent=ENT):
    """Produk jual PT ber-roll cukup & bebas reservasi (sama dengan uji hidup F-10)."""
    pipa = [{"$match": {"owner_entity_id": ent, "status": "available", "length_remaining": {"$gt": 20},
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


SALES = ("sales@kainnusantara.id", "sales2@kainnusantara.id", "sales3@kainnusantara.id")


def pelanggan(ent):
    """(email sales, pelanggan) di PT `ent`: pelanggan milik akun sales seed itu atau tanpa sales; pelanggan acuan dulu.
    Akun yang tidak ada di data acuan dilewati."""
    out = []
    for email in SALES:
        u = DB.users.find_one({"email": email}, {"_id": 0, "id": 1})
        if not u:
            continue
        q = {"entity_id": ent, "is_active": {"$ne": False},
             "$or": [{"assigned_sales_id": u["id"]}, {"assigned_sales_id": {"$in": [None, ""]}}]}
        out += [(email, c["id"]) for c in DB.customers.find(q, {"_id": 0, "id": 1})]
    return sorted(out, key=lambda x: x[1] != CUST)


def pesanan_tertahan(termin, ent, lewati=()):
    """Pesanan `termin` di PT `ent` → Periksa & lepas → tertahan "Bayar dicek Finance". Pelanggan pertama yang lolos
    gerbang kredit dipakai (data acuan: pelanggan acuan KSC punya tagihan telat, jadi hanya CBD yang lolos untuknya)."""
    sadm, mgr = masuk("salesadmin@kainnusantara.id", ent), masuk("manager@kainnusantara.id", ent)
    pid = produk(lewati, ent)["id"]
    so, c, email = {}, 0, ""
    for email, cust in pelanggan(ent):
        c, so = masuk(email, ent)("POST", "/sales-orders", {
            "customer_id": cust, "shipping_address_id": "", "entity_id": ent, "payment_term_code": termin,
            "items": [{"product_id": pid, "quantity": 12.5, "unit": "yard"}], "confirm_mixed_lot": True,
            "fulfillment_method": "kirim", "qc_request": "none"})
        if c == 200:
            break
        print(f"  {termin} {email} {cust}: {str(so)[:160]}")
    if c != 200:
        return None
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
    return {"id": so["id"], "number": s["number"], "term": termin, "customer": s.get("customer_name"), "entity_id": ent,
            "product_id": pid, "sales_email": email, "grand_total": s.get("grand_total"),
            "due_at": s["pay_hold"].get("due_at")}


def main():
    cbd = pesanan_tertahan("CBD", ENT)
    assert cbd, "pesanan CBD gagal dibuat"
    dp = pesanan_tertahan("DP50", ENT, {cbd["product_id"]})
    assert dp, "pesanan DP50 gagal dibuat untuk semua pelanggan KSC milik sales acuan"
    for so in (cbd, dp):
        c, g = masuk("salesadmin@kainnusantara.id", so["entity_id"])("GET", f"/sales-orders/{so['id']}/dispatch-payment-gate")
        assert c == 200, g
        so["shortfall"] = g.get("shortfall")
    data = {"cbd": cbd, "dp": dp}
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
