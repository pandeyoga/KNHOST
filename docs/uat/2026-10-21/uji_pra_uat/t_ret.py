# Cabang RETUR dari SO yang sudah diterima & lunas (KSC/SO-00038)
SO = "so_d9aa799376ff"
sales = Api("sales@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id"); mgr = Api("manager@kainnusantara.id")
wh = Api("warehouse@kainnusantara.id"); whr = Api("warehouse.rancamalang@kainnusantara.id"); qc = Api("qc@kainnusantara.id")
fin = Api("finance@kainnusantara.id")
png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360000000000200015e2f3a8d0000000049454e44ae426082")


def cut(b, keys=("number", "status", "return_type")):
    return {k: b.get(k) for k in keys} if isinstance(b, dict) and ("status" in b or "number" in b) else b


c, r = sales.get("/sales-returns/returnable", params={"order_id": SO})
step("sales: barang yang bisa diretur dari SO", c, short(r, 600))
c, meta = sales.get("/sales-returns/meta/complaint-reasons")
codes = [i.get("value") or i.get("code") for i in (meta.get("items") or [])] if isinstance(meta, dict) else []
print("kode keluhan:", codes[:8], "milestones", [m["value"] for m in meta.get("milestones", [])] if isinstance(meta, dict) else "")
c, pol = sales.get("/sales-returns/meta/evidence-policy"); print("kebijakan bukti:", pol)
P = "prod_c854e5856251"
R1 = "roll_c0a6a0b383da"   # RL-36311 121,59 yd terkirim

# klaim melebihi qty terkirim (negatif)
c, b = sales.post("/sales-returns", {"order_id": SO, "return_type": "retur", "items": [
    {"product_id": P, "quantity_returned": 500, "unit": "yard", "reason": "cacat", "condition": "damaged",
     "roll_ids": [R1], "roll_qtys": {R1: 500}}], "complaint_code": codes[0] if codes else ""})
step("NEG klaim melebihi qty terkirim", c, b, (400, 409, 422))
# roll asing (negatif)
c, b = sales.post("/sales-returns", {"order_id": SO, "return_type": "retur", "items": [
    {"product_id": P, "quantity_returned": 10, "unit": "yard", "roll_ids": ["roll_1c4a2e07ab21"]}]})
step("NEG roll bukan dari SO ini", c, b, (400, 409, 422))

# Retur A — alur lengkap fisik
c, ra = sales.post("/sales-returns", {"order_id": SO, "return_type": "retur", "items": [
    {"product_id": P, "quantity_returned": 50, "unit": "yard", "reason": "warna belang", "condition": "damaged",
     "roll_ids": [R1], "roll_qtys": {R1: 50}}], "complaint_code": codes[0] if codes else "",
    "notes": "UAT retur sebagian", "submit_now": True})
ra = need("sales: buat & ajukan retur 50 yd", c, ra)
RA = ra["id"]
print("retur", ra.get("number"), ra.get("status"), "deadline", ra.get("deadline") or ra.get("policy"))
c, b = sales.post(f"/sales-returns/{RA}/approve", {"notes": "x"})
step("NEG sales approve retur sendiri", c, b, (403,))
c, b = mgr.post(f"/sales-returns/{RA}/approve", {"notes": "UAT disetujui"})
step("mgr: setujui pengajuan retur", c, cut(b))
c, b = qc.post(f"/sales-returns/{RA}/inspect/start")
step("CEK: QC mulai sebelum barang diterima", c, cut(b), (200, 400, 403))

# Retur B — QC tanpa scan apa pun (cek pagar receipt)
c, rb = sales.post("/sales-returns", {"order_id": SO, "return_type": "retur", "items": [
    {"product_id": P, "quantity_returned": 10, "unit": "yard", "reason": "uji", "condition": "ok",
     "roll_ids": [R1], "roll_qtys": {R1: 10}}], "complaint_code": codes[0] if codes else "", "submit_now": True})
step("sales: retur B 10 yd", c, cut(rb), (200, 400, 409))
if isinstance(rb, dict) and rb.get("id"):
    RB = rb["id"]
    mgr.post(f"/sales-returns/{RB}/approve", {"notes": "UAT"})
    c, b = qc.post(f"/sales-returns/{RB}/inspect/start"); step("retur B: QC mulai TANPA scan terima", c, cut(b), (200, 400, 403))
    c, b = qc.post(f"/sales-returns/{RB}/inspect/complete", {"inspections": [{"product_id": P, "condition": "ok", "accepted_qty": 10}]})
    step("CEK: retur B QC SELESAI tanpa barang pernah diterima", c, cut(b), (200, 400, 403))

# Retur A — perjalanan fisik Jakarta -> Rancamalang
c, b = wh.post(f"/sales-returns/{RA}/journey/scan", {"stage": "received", "codes": ["RL-36311"], "warehouse_id": "wh_jakarta"})
step("gudang JKT: scan terima retur", c, {"doc": (b.get("event") or {}).get("doc_no")} if isinstance(b, dict) and "event" in b else b)
c, b = wh.post(f"/sales-returns/{RA}/journey/scan", {"stage": "dispatched", "codes": ["RL-36311"], "warehouse_id": "wh_jakarta",
                                                     "to_warehouse_id": "wh_5894191fae62", "carrier": "Armada KN"})
step("gudang JKT: kirim ke Rancamalang transit", c, {"doc": (b.get("event") or {}).get("doc_no")} if isinstance(b, dict) and "event" in b else b)
c, b = qc.post(f"/sales-returns/{RA}/inspect/complete", {"inspections": [{"product_id": P, "condition": "damaged", "accepted_qty": 50}]})
step("NEG QC selesai saat roll masih di perjalanan", c, b, (400,))
c, b = whr.post(f"/sales-returns/{RA}/journey/scan", {"stage": "arrived", "codes": ["RL-36311"], "warehouse_id": "wh_5894191fae62"})
step("gudang RCM: scan tiba", c, {"doc": (b.get("event") or {}).get("doc_no")} if isinstance(b, dict) and "event" in b else b)
c, b = qc.post(f"/sales-returns/{RA}/inspect/start"); step("QC: mulai inspeksi", c, cut(b), (200, 400))
c, b = qc.post(f"/sales-returns/{RA}/inspect/complete", {"inspections": [{"product_id": P, "condition": "damaged", "accepted_qty": 48,
                                                                         "grade": "B", "roll_actuals": {R1: 48}, "note": "belang 2 titik"}]})
step("QC: selesai (aktual 48 yd, grade B)", c, cut(b))
c, b = sadm.post(f"/sales-returns/{RA}/settle", {"outcome": "store_credit", "decision_note": "ACC Pak Budi via WA (UAT)"})
step("CEK: admin sales memutus kompensasi", c, cut(b), (200, 400, 403))
c, b = mgr.post(f"/sales-returns/{RA}/settle", {"outcome": "store_credit", "decision_note": "ACC Pak Budi via WA (UAT)", "return_warehouse_id": "wh_5894191fae62"})
step("mgr: keputusan akhir saldo kredit", c, cut(b), (200, 400, 409))
c, t = sales.get(f"/sales-returns/{RA}/timeline"); step("timeline retur", c, short(t, 800))
c, d = sadm.get(f"/sales-returns/{RA}/disposition"); step("disposisi tersedia", c, short(d, 800))
print("RETUR_A", RA)
dump("/tmp/uat_ret.json")
