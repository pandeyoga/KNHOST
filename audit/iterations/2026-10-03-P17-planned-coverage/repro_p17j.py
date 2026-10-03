"""P17j — OCR SURAT JALAN SUNGGUHAN (OpenAI, model dari Pusat Pengaturan, bawaan gpt-6-sol).

Foto SJ sintetis (teks jelas) → POST /files → POST /read → periksa kepala SJ, baris ke tugas PO, biaya tercatat.
Memakai kunci OpenAI pemilik (biaya token nyata, kecil). GRN dibatalkan & semua data uji dibuang.
Usage: cd /app/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/repro_p17j.py
"""
import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repro_p17a as A  # noqa: E402

BASE, db, ok, check, results = A.BASE, A.db, A.ok, A.check, A.results
FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def photo(po, items, dn):
    im = Image.new("RGB", (1240, 1754), "#FBFAF5")
    d = ImageDraw.Draw(im)
    big, f = ImageFont.truetype(FONT, 44), ImageFont.truetype(FONT, 30)
    sup = db.suppliers.find_one({"id": po["supplier_id"]}, {"_id": 0, "name": 1}) or {}
    d.text((80, 80), (sup.get("name") or "SUPPLIER").upper(), font=big, fill="#111")
    rows = [f"SURAT JALAN   No: {dn}", "Tanggal: 03 Oktober 2026", "Kepada: PT. SUKACITA TEXTILE",
            f"No. PO: {po['po_number']}", "",
            "No   Nama Barang                               Jumlah     Satuan   Roll"]
    for i, (name, qty, unit, rolls) in enumerate(items, 1):
        rows.append(f"{i}.   {name:<40}  {qty:>6}     {unit:<6}   {rolls}")
    rows += ["", "Penerima: ____________        Pengirim: ____________"]
    for i, line in enumerate(rows):
        d.text((80, 180 + i * 56), line, font=f, fill="#222")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def run(s):
    po, (ta, tb) = A.fixture()
    po["po_number"] = po["po_number"].replace("_", "-")
    db.purchase_orders.update_one({"id": po["id"]}, {"$set": {"po_number": po["po_number"]}})
    db.wms_tasks.update_many({"po_id": po["id"]}, {"$set": {"po_number": po["po_number"]}})
    dn = "SJ-2610-0777"
    items = [(ta["product_name"], 60, "yard", 2), (tb["product_name"], 50, "yard", 1)]
    g = ok(s.post(f"{BASE}/goods-receipts", json={"partner_type": "supplier", "partner_id": po["supplier_id"],
                                                 "warehouse_id": po["warehouse_id"], "po_ids": [po["id"]]}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/files", files={"file": ("sj.jpg", photo(po, items, dn), "image/jpeg")},
                  data={"expected_version": str(g["version"])}))["grn"]
    r = s.post(f"{BASE}/goods-receipts/{g['id']}/read", json={"expected_version": g["version"]}, timeout=180)
    g = ok(r)
    ex = g.get("extraction") or {}
    runs = ex.get("runs") or []
    check("OCR-REAL", "pembacaan sungguhan selesai (status review, tidak read_failed)",
          g["status"] == "review" and ex.get("read_failed") is False, (g["status"], ex.get("read_failed"), ex.get("error")))
    check("OCR-REAL", "model sungguhan dipakai (bukan mock-*)", runs and not runs[0]["model"].startswith("mock-"),
          [(x["model"], x["role"], x["status"]) for x in runs])
    check("OCR-REAL", "nomor SJ & tanggal terbaca", (g.get("dn") or {}).get("number") == dn
          and (g.get("dn") or {}).get("date") == "2026-10-03", g.get("dn"))
    lines = g.get("lines") or []
    tgt = {(ln.get("target") or {}).get("task_id"): ln for ln in lines}
    check("OCR-REAL", "2 baris barang dipetakan ke tugas PO yang benar",
          ta["id"] in tgt and tb["id"] in tgt, [((ln.get("target") or {}).get("task_id"), (ln.get("match") or {}).get("status")) for ln in lines])
    q = {k: ((v.get("declared") or {}).get("qty"), (v.get("declared") or {}).get("rolls")) for k, v in tgt.items()}
    check("OCR-REAL", "jumlah & roll terbaca (60/2 dan 50/1)", q.get(ta["id"]) == (60, 2) and q.get(tb["id"]) == (50, 1), q)
    logs = list(db.ai_usage_log.find({"ref_id": g["id"]}, {"_id": 0, "model": 1, "cost_usd": 1, "status": 1, "usage": 1}))
    check("OCR-REAL", "biaya token nyata tercatat di ai_usage_log (> 0 USD)",
          logs and all(x["status"] == "ok" for x in logs) and sum(x["cost_usd"] for x in logs) > 0,
          [(x["model"], x["cost_usd"]) for x in logs])
    v = db.goods_receipts.find_one({"id": g["id"]})["version"]
    ok(s.post(f"{BASE}/goods-receipts/{g['id']}/cancel", json={"expected_version": v, "reason": "TEST_ uji OCR sungguhan"}))


def main():
    full = A.snapshot_stock(["inventory_balances", "number_sequences", "supplier_dn_profiles"])
    ids = A.snapshot_new_ids(A.NEW + ["ai_usage_log"])
    try:
        run(A.login("admin@kainnusantara.id"))
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check("OCR-REAL", "eksekusi skenario", False, repr(exc)[:300])
    finally:
        A.purge_new_ids(ids, verbose=False)
        A.restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


main()
