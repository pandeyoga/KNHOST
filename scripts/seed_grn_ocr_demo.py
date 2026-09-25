"""Demo GRN Fase 4/5: kedatangan KSC/PO-00014 + kedatangan makloon MKO-00002 (baris BS → barang sisa). Kedatangan PO yang dibaca dengan model TIRUAN `mock-sj_doubt` (angka ragu + beda
pembaca kedua) supaya layar Tinjau SJ bisa dicoba tanpa kunci OpenAI. Konfigurasi OCR dikembalikan ke bawaan sesudahnya.

Syarat: backend/.env memuat OCR_ALLOW_MOCK="1".  Jalankan:  cd /app/backend && python ../scripts/seed_grn_ocr_demo.py
"""
import io
import os
import sys

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw
from pymongo import MongoClient

sys.path.insert(0, "/app/backend/tests")
from test_inbound_complete_characterization import BASE  # noqa: E402

TASK = "wms_51600206da7f"   # KSC/PO-00014 · Batik Mega Mendung Premium · 250 yd
MKO = "mko_e7566f649bf7"    # MKO-00002 langkah 1 (PT Tenun Nusantara Jaya, punya produk sisa)


def cfg(s, values):
    items = [{"key": k, "value": v, "scope_type": "global", "reason": "demo OCR fase 4"} for k, v in values.items()]
    s.put(f"{BASE}/config/values", json={"items": items}, timeout=30).raise_for_status()


def photo() -> bytes:
    im = Image.new("RGB", (1240, 1754), "#FBFAF5")
    d = ImageDraw.Draw(im)
    for i, line in enumerate(["CV. CIREBON CRAFT", "SURAT JALAN  No: SJ-MOCK-DOUBT", "Tgl: 10 Juni 2026",
                              "Kepada: PT. SUKACITA", "PO: KSC/PO-00014", "",
                              "1. BATIK MEGA MENDUNG PREMIUM   2 pcs   1.250 yd"]):
        d.text((80, 100 + i * 60), line, fill="#222")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def main() -> None:
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    r.raise_for_status()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"})
    load_dotenv("/app/backend/.env")
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    t = db.wms_tasks.find_one({"id": TASK}, {"_id": 0})
    po = db.purchase_orders.find_one({"id": t["po_id"]}, {"_id": 0, "supplier_id": 1})
    demos = [("SJ-MOCK-DOUBT", "mock-sj_doubt", {"partner_type": "supplier", "partner_id": po["supplier_id"],
                                                 "warehouse_id": t["warehouse_id"], "po_ids": [t["po_id"]]}),
             ("SJ-MOCK-PACK", "mock-sj_packing", {"partner_type": "supplier", "partner_id": po["supplier_id"],
                                                  "warehouse_id": t["warehouse_id"], "po_ids": [t["po_id"]]}),
             ("SJ-MKL-0139", "mock-sj_makloon", {"partner_type": "makloon", "partner_id": "mak_seed_tenun",
                                                 "warehouse_id": "wh_surabaya", "mko_ids": [MKO]})]
    try:
        for dn, model, body in demos:
            if db.goods_receipts.find_one({"dn.number": dn, "status": {"$nin": ["cancelled", "rejected"]}}):
                print(f"Demo {dn} sudah ada — lewati.")
                continue
            if body["partner_type"] == "makloon" and not db.makloon_orders.find_one({"id": MKO, "steps.0.status": "issued"}):
                print("MKO-00002 langkah 1 tidak issued — lewati demo makloon.")
                continue
            cfg(s, {"receiving.ocr_enabled": True, "receiving.ocr_model_primary": model,
                    "receiving.ocr_model_second": "mock-sj_doubt_second",
                    "receiving.ocr_extract_packing_list": model == "mock-sj_packing"})
            g = s.post(f"{BASE}/goods-receipts", json=body).json()
            g = s.post(f"{BASE}/goods-receipts/{g['id']}/files", files={"file": ("sj.jpg", photo(), "image/jpeg")},
                       data={"expected_version": str(g["version"])}).json()["grn"]
            g = s.post(f"{BASE}/goods-receipts/{g['id']}/read", json={"expected_version": g["version"]}).json()
            print(f"{g['number']} ({dn}) → {g['status']} · baris {len(g['lines'])} · runs {len(g['extraction']['runs'])}")
    finally:
        cfg(s, {"receiving.ocr_enabled": False, "receiving.ocr_model_primary": "gpt-6-sol",
                "receiving.ocr_model_second": "gpt-5.6-sol", "receiving.ocr_extract_packing_list": False})


if __name__ == "__main__":
    main()
