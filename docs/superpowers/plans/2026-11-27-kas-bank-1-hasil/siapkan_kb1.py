"""F1 Kwitansi otomatis dari mutasi + Kas & Bank bagian 1 — penyiapan data tangkapan (lingkungan uji lokal, data acuan;
BUKAN data nyata).

Lewat API akun peran (pola `2026-11-25-lapor-bayar-cbd-hasil/siapkan_lb.py`): Sales membuat dua pesanan PT KSC (termin
CBD dan DP50) → Admin Sales "Periksa & lepas" → pesanan berhenti di "Bayar dicek Finance" (`approved` + `pay_hold`) dan
kode bayar tingkat pesanan lahir. Lalu berkas rekening koran CSV format BCA (yang dikenali impor:
`Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo`, pola `backend/tests_mem/test_F1_4_endpoint.py`) ditulis dengan dua
baris masuk:
  (a) kode bayar pesanan CBD + nominal PERSIS sisa wajib sebelum gudang → kwitansi otomatis;
  (b) kode bayar pesanan DP50 + nominal LEBIH Rp 250.000 dari sisa wajibnya → kartu "Mutasi berkode perlu dicek".
Hasil (id, nomor, kode, nominal) ditulis ke `kb1_data.json`; berkas mutasi ke `mutasi_uji_kb1.csv` (folder ini).

Jalankan dari host dengan backend lokal menyala (:8001):  python siapkan_kb1.py
Pulihkan data acuan sesudahnya:  bash scripts/dev_restore_demo.sh
"""
import json
import math
import os
from datetime import datetime, timedelta, timezone

import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT, CUST, PW = "ent_ksc", "cust_toko_kain", "demo12345"
DIR = os.path.dirname(os.path.abspath(__file__))
OUT, CSV = os.path.join(DIR, "kb1_data.json"), os.path.join(DIR, "mutasi_uji_kb1.csv")
SALES = ("sales@kainnusantara.id", "sales2@kainnusantara.id", "sales3@kainnusantara.id")


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
    """Produk jual PT ber-roll cukup & bebas reservasi (sama dengan `siapkan_lb.py`)."""
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


def pelanggan(ent):
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
    c, b = sadm("POST", f"/sales-orders/{so['id']}/review-release", {"note": "Tangkapan F1 / Kas & Bank 1", "hold": False})
    assert c == 200, b
    s = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    if s["status"] == "waiting_approval":
        c, b = mgr("POST", f"/sales-orders/{so['id']}/approve")
        assert c == 200, b
        s = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert s["status"] == "approved" and s.get("pay_hold") and (s.get("release") or {}).get("waiting") == "bayar", (
        s["status"], s.get("pay_hold"), s.get("release"))
    kode = DB.payment_codes.find_one({"order_id": so["id"], "order_level": True}, {"_id": 0})
    assert kode, "kode bayar tidak lahir"
    c, g = sadm("GET", f"/sales-orders/{so['id']}/dispatch-payment-gate")
    assert c == 200, g
    return {"id": so["id"], "number": s["number"], "term": termin, "customer": s.get("customer_name"),
            "customer_id": s.get("customer_id"), "entity_id": ent, "product_id": pid, "sales_email": email,
            "grand_total": s.get("grand_total"), "shortfall": g.get("shortfall"), "pay_code": kode["code"],
            "pay_code_amount": kode.get("amount"), "receiving_account_id": s.get("receiving_account_id") or "",
            "payment_method_code": s.get("payment_method_code") or ""}


def rupiah_csv(x):
    """1234567.5 → "1.234.567,50" (format angka rekening koran BCA)."""
    bulat, sen = divmod(round(x * 100), 100)
    return f"{bulat:,}".replace(",", ".") + f",{sen:02d}"


def main():
    cbd = pesanan_tertahan("CBD", ENT)
    assert cbd, "pesanan CBD gagal dibuat"
    dp = pesanan_tertahan("DP50", ENT, {cbd["product_id"]})
    if not dp:
        print("  DP50 tidak lolos untuk pelanggan mana pun — pakai CBD kedua")
        dp = pesanan_tertahan("CBD", ENT, {cbd["product_id"]})
    assert dp, "pesanan kedua gagal dibuat"
    rek = DB.bank_accounts.find_one({"entity_id": ENT, "name": "BCA Operasional KSC"}, {"_id": 0, "id": 1, "name": 1})
    tgl = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%d/%m/%Y")
    tepat = float(cbd["shortfall"])
    assert abs(tepat - round(tepat)) < 0.005, f"sisa wajib CBD berpecahan: {tepat}"
    lebih = math.ceil(float(dp["shortfall"])) + 250_000
    baris = [
        (tgl, f"TRSF E-BANKING CR 2711/FTSCY/WS95051 {cbd['pay_code']} {cbd['customer'] or ''}".strip(), tepat, "CR"),
        (tgl, f"TRSF E-BANKING CR 2711/FTSCY/WS95052 {dp['pay_code']} {dp['customer'] or ''}".strip(), lebih, "CR"),
    ]
    with open(CSV, "w", newline="\n") as f:
        f.write("Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo\n")
        for t, ket, nom, arah in baris:
            f.write(f"{t},{ket.replace(',', ' ')},0000,\"{rupiah_csv(nom)}\",{arah},0\n")
    data = {"cbd": cbd, "dp": dp, "rekening": rek, "mutasi": {"tanggal": tgl, "tepat": tepat, "lebih": lebih,
                                                              "csv": os.path.basename(CSV)}}
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print(open(CSV).read())


if __name__ == "__main__":
    main()
