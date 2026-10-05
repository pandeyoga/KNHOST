"""Demo TERIMA MAKLOON BERTAHAP (E07) — satu langkah MKO diterima dari dua surat jalan.

Hasil:
  1) GRN kiriman-1 (SJ-DEMO-MKL-P1, 30 yd / 2 roll) DITUTUP sebagai "Terima sebagian"
     → tertahan di steps[].partial_receipts, langkah tetap "Di Makloon".
  2) GRN kiriman-2 (SJ-DEMO-MKL-P2, 42 yd / 2 roll) berhenti di status REKONSILIASI
     → di layar tampak centang `grn-mko-partial-toggle`; tutup tanpa centang = kiriman
       terakhir (menyerap kiriman-1: satu posting stok & satu tagihan jasa).

Idempoten (dilewati bila SJ demo sudah ada). Jalankan:  cd /app/backend && python ../scripts/seed_makloon_partial_demo.py
"""
import io
import os
import sys

import requests
from dotenv import load_dotenv
from PIL import Image
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
BASE = os.environ.get("KN_API_BASE") or "http://localhost:8001/api"
ENT = "ent_ksc"
DEMOS = [("SJ-DEMO-MKL-P1", [15.0, 15.0], True), ("SJ-DEMO-MKL-P2", [21.0, 21.0], False)]


def ok(r):
    if r.status_code >= 400:
        raise SystemExit(f"{r.request.method} {r.url} → {r.status_code}: {r.text[:400]}")
    return r.json()


def photo() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1200, 1600), "white").save(buf, "JPEG")
    return buf.getvalue()


def find_step(db):
    for m in db.makloon_orders.find({"entity_id": ENT, "status": {"$nin": ["cancelled", "completed"]}},
                                    {"_id": 0, "id": 1, "mko_number": 1, "steps": 1}):
        for s in m.get("steps") or []:
            if s.get("status") == "issued" and (s.get("material_flow") or "moves") == "moves":
                return m, s
    return None, None


def run_grn(s, mko, step, dn, lengths, partial):
    wh = step.get("from_warehouse_id") or "wh_surabaya"
    g = ok(s.post(f"{BASE}/goods-receipts", json={"partner_type": "makloon", "partner_id": step["makloon_id"],
                                                  "warehouse_id": wh, "mko_ids": [mko["id"]]}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/files", files={"file": ("sj.jpg", photo(), "image/jpeg")},
                  data={"expected_version": str(g["version"])}))["grn"]
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/manual-entry", json={"expected_version": g["version"]}))
    g = ok(s.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": dn}))
    lot = f"DEMO-{mko['mko_number']}-P"
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines", json={
        "expected_version": g["version"], "role": "output",
        "declared": {"qty": sum(lengths), "unit": step.get("output_unit") or "yard", "rolls": len(lengths), "lot": lot},
        "target": {"type": "mko_step", "mko_id": mko["id"], "step_seq": step["seq"]},
        "description": step.get("output_name") or "Hasil makloon"}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))
    for ln in lengths:
        g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/rolls", json={"length": ln, "lot": lot, "grade": "A"}))["grn"]
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": g["version"]}))
    for d in [d for d in g.get("discrepancies") or [] if d.get("blocking") and not d.get("resolution")]:
        g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/discrepancies/{d['key']}/resolve", json={
            "expected_version": g["version"], "action": "accept_note", "reason": "Demo terima bertahap"}))
    if partial:
        g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/mko-partial", json={"expected_version": g["version"], "partial": True}))
        g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]}))["grn"]
    print(f"{g['number']} ({dn}) → {g['status']}{' · terima sebagian' if partial else ''}")


def main() -> None:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if db.goods_receipts.find_one({"dn.number": DEMOS[0][0], "status": {"$nin": ["cancelled", "rejected"]}}):
        print("Demo terima makloon bertahap sudah ada — lewati.")
        return
    mko, step = find_step(db)
    if not mko:
        print("Tidak ada langkah MKO berstatus issued di ent_ksc — lewati demo.")
        return
    s = requests.Session()
    tok = ok(s.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id",
                                                "password": os.environ.get("KN_TEST_PASSWORD") or "demo12345"}))["token"]
    s.headers.update({"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT})
    print(f"MKO {mko['mko_number']} langkah {step['seq']} ({step.get('output_name')})")
    for dn, lengths, partial in DEMOS:
        run_grn(s, mko, step, dn, lengths, partial)


if __name__ == "__main__":
    sys.exit(main())
