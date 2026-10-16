#!/usr/bin/env python3
"""Demo tab "Warna Pelanggan": 3 produk eksklusif Butik Bali Indah (labdip → ACC) + 1 warna milik Toko Kain Sejahtera.
Idempoten: dilewati bila SKU/kode sudah ada. Jalur sample mengikuti special_order_routing (penanda eksklusif pada sample)."""
import os
import requests
from pymongo import MongoClient

A = os.environ.get("KN_API", "http://localhost:8001/api")
ENT = "ent_ksc"
db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8ffff3f0300050001019cd7b3f30000000049454e44ae426082")


def hdr(email):
    t = requests.post(A + "/auth/login", json={"email": email, "password": "demo12345"}, timeout=30).json()["token"]
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": ENT}


def ok(r, step):
    assert r.status_code == 200, f"{step}: {r.status_code} {r.text[:300]}"
    return r.json()


def main():
    ad, mg = hdr("admin@kainnusantara.id"), hdr("manager@kainnusantara.id")
    if not db.color_library.find_one({"code": "KN-SJT-01"}):
        ok(requests.post(A + "/color-library", headers=ad, json={
            "code": "KN-SJT-01", "name": "Biru Sejahtera", "hex": "#2F5D8A", "family": "Biru", "system": "KN",
            "factory_name": "Royal Blue 19-4150", "exclusive_customer_id": "cust_toko_kain"}), "warna milik")
        print("warna KN-SJT-01 (milik Toko Kain Sejahtera) dibuat")
    if not db.color_library.find_one({"code": "KN-BLI-EMS-01"}):
        ok(requests.post(A + "/color-library", headers=ad, json={
            "code": "KN-BLI-EMS-01", "name": "Emas Pura", "hex": "#C9A227", "family": "Kuning", "system": "KN"}), "warna baru")
        print("warna baru KN-BLI-EMS-01 (belum bertuan) dibuat — akan ditandai otomatis saat labdip ACC")
    make_exclusive(ad, mg, "SGK-BLI-UNG-01", "KN-PUR-01", "Songket Bali Ungu Terong", "Terong 21", "TR-21")
    make_exclusive(ad, mg, "SGK-BLI-EMS-01", "KN-BLI-EMS-01", "Songket Bali Emas Pura", "Emas 88", "EM-88")
    make_exclusive(ad, mg, "SGK-BLI-TSK-01", "KN-GRN-03", "Songket Bali Hijau Toska", "Toska 05", "TS-05")


def make_exclusive(ad, mg, sku, color_code, title, sup_color, sup_code):
    if db.products.find_one({"sku": sku}):
        print(f"produk eksklusif {sku} sudah ada"); return
    cust = db.customers.find_one({"id": "cust_butik_bali"}, {"_id": 0, "id": 1, "name": 1})
    col = db.color_library.find_one({"code": color_code}, {"_id": 0, "id": 1})
    sup = db.suppliers.find_one({"name": "Palembang Silk House", "entity_id": ENT}, {"_id": 0, "id": 1})
    spec = {"title": title, "base_unit": "meter", "sku_hint": sku, "sample_type_hint": "labdip",
            "customer_id": cust["id"], "exclusive_customer_id": cust["id"],
            "target": {"fabric_type": "woven", "gramasi": 250, "lebar": 115}, "color_target": {"color_id": col["id"]}}
    smp = ok(requests.post(A + "/rnd/samples", headers=ad, json={
        "sample_types": ["labdip"], "title": f"Labdip {title} — {cust['name']}", "brief": "Warna eksklusif koleksi butik",
        "color_target": {"color_id": col["id"]}, "customer_id": cust["id"], "qty_requested": 3, "unit": "meter", "spec": spec}), "sample")
    db.md_samples.update_one({"id": smp["id"]}, {"$set": {"customer_name": cust["name"], "exclusive_customer_id": cust["id"]}})
    smp = ok(requests.post(A + f"/rnd/samples/{smp['id']}/send", headers=ad, json={"supplier_ids": [sup["id"]], "type_codes": ["labdip"], "note": "labdip eksklusif"}), "send")
    rid = smp["rounds"][0]["id"]
    ok(requests.post(A + f"/rnd/samples/{smp['id']}/rounds/{rid}/attachments", headers=ad, files={"file": ("swatch.png", PNG, "image/png")}), "attach")
    meta = requests.get(A + "/rnd/meta", headers=ad).json()
    fields = next((t.get("measurement_fields", []) for t in meta.get("sample_types", []) if t["value"] == "labdip"), [])
    ok(requests.post(A + f"/rnd/samples/{smp['id']}/rounds/{rid}/submit", headers=ad, json={"note": "kirim", "measurements": {f: 1 for f in fields}, "cost": 60000}), "submit")
    ok(requests.post(A + f"/rnd/samples/{smp['id']}/rounds/{rid}/assess", headers=ad, json={"result": "acc", "score": 90, "note": "sesuai"}), "assess")
    ok(requests.post(A + f"/rnd/samples/{smp['id']}/decide", headers=mg, json={
        "supplier_id": sup["id"], "reason_code": meta["reasons"][0]["value"], "price": 185000,
        "supplier_color_name": sup_color, "supplier_color_code": sup_code, "approve_spec": True,
        "product_sku": sku, "product_name": f"{title} (eksklusif {cust['name']})"}), "decide")
    print("produk eksklusif:", sku, db.products.find_one({"sku": sku}, {"_id": 0, "exclusive_customer_id": 1, "color_ref.code": 1}))

if __name__ == "__main__":
    main()
