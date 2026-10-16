"""P17b — GRN-06 (bagian API): timbang netto & override selisih (not_on_dn butuh goods_receipt.approve).

OCR & packing list dibuktikan `tests/test_grn_phase4_read.py` + `tests/test_grn_phase6.py` (mock OCR, serial -n0).
Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/repro_p17b.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repro_p17a as A  # noqa: E402

BASE, db, ok, check, results = A.BASE, A.db, A.ok, A.check, A.results


def run(s):
    po, (ta, tb) = A.fixture()
    g = ok(s.post(f"{BASE}/goods-receipts", json={"partner_type": "supplier", "partner_id": po["supplier_id"],
                                                 "warehouse_id": po["warehouse_id"], "po_ids": [po["id"]]}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/manual-entry", json={"expected_version": g["version"]}))
    g = ok(s.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": f"{A.T}-SJW",
                                                              "date": "2026-10-03", "recipient_name": A.T}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines", json={
        "expected_version": g["version"], "declared": {"qty": 60, "unit": ta.get("unit"), "rolls": 1,
                                                       "weight_kg": 100, "weight_basis": "net"},
        "target": {"type": "po_task", "task_id": ta["id"]}, "description": f"{A.T} timbang"}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines", json={
        "expected_version": g["version"], "declared": {"qty": 0, "unit": tb.get("unit"), "rolls": 0},
        "target": {"type": "po_task", "task_id": tb["id"]}, "description": f"{A.T} tak di SJ"}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))
    ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/rolls", json={"length": 60, "weight_kg": 90, "lot": f"{A.T}-W"}))
    ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines/2/rolls", json={"length": 15, "lot": f"{A.T}-X"}))
    v = db.goods_receipts.find_one({"id": g["id"]})["version"]
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": v}))
    d = {x["kind"]: x for x in g["discrepancies"]}
    check("GRN-06", "berat netto beda >toleransi → weight_mismatch (tidak memblokir)",
          "weight_mismatch" in d and d["weight_mismatch"]["blocking"] is False, list(d))
    check("GRN-06", "barang dihitung tanpa qty di SJ → not_on_dn memblokir", d.get("not_on_dn", {}).get("blocking") is True, list(d))
    r = s.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]})
    check("GRN-06", "tutup ditolak selama not_on_dn terbuka (BLOCKERS_OPEN)",
          r.status_code == 400 and "BLOCKERS_OPEN" in r.text, f"{r.status_code} {r.text[:120]}")
    bad = s.post(f"{BASE}/goods-receipts/{g['id']}/discrepancies/L2:not_on_dn/resolve",
                 json={"expected_version": g["version"], "action": "claim_supplier", "reason": f"{A.T} aksi salah"})
    check("GRN-06", "aksi override di luar daftar ditolak 400", bad.status_code == 400, bad.status_code)
    # peran review tanpa approve: matriks bawaan memberi keduanya sekaligus → uji via akun gudang (tanpa review)
    wh = A.login("warehouse@kainnusantara.id")
    deny = wh.post(f"{BASE}/goods-receipts/{g['id']}/discrepancies/L2:not_on_dn/resolve",
                   json={"expected_version": g["version"], "action": "accept_note", "reason": f"{A.T} gudang"})
    check("GRN-06", "penghitung gudang tidak bisa override selisih (403)", deny.status_code == 403, deny.status_code)
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/discrepancies/L2:not_on_dn/resolve",
                  json={"expected_version": g["version"], "action": "accept_note", "reason": f"{A.T} supplier kirim lebih"}))
    res = next(x for x in g["discrepancies"] if x["key"] == "L2:not_on_dn")["resolution"]
    check("GRN-06", "override approver tersimpan (aksi, alasan, oleh)", res["action"] == "accept_note" and res["by"], res)
    out = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]}))
    rec = {i["product_id"]: float(i.get("received_qty") or 0) for i in db.purchase_orders.find_one({"id": po["id"]})["items"]}
    check("GRN-06", "sesudah override GRN closed, stok B 15 diterima sesuai hitung (bukan SJ)",
          out["grn"]["status"] == "closed" and rec[tb["product_id"]] == 15.0 and rec[ta["product_id"]] == 60.0, rec)
    audit = db.audit_logs.find_one({"action": "grn_discrepancy_resolved", "entity_id": g["id"]}, {"_id": 0})
    check("GRN-06", "override tercatat di audit dengan alasan", bool(audit) and A.T in str(audit.get("reason") or audit), bool(audit))


def main():
    full = A.snapshot_stock(["inventory_balances", "number_sequences"])
    ids = A.snapshot_new_ids(A.NEW)
    try:
        run(A.login("admin@kainnusantara.id"))
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check("GRN-06", "eksekusi skenario", False, repr(exc)[:200])
    finally:
        A.purge_new_ids(ids, verbose=False)
        A.restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


main()
