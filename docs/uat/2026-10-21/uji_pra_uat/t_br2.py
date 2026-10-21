# Cabang: KREDIT over-limit, termin CBD, AMBIL SENDIRI, permintaan QC sebelum kirim.
import os, datetime
from pymongo import MongoClient
mdb = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"))[os.environ.get("DB_NAME", "test_database")]


def free_rolls(pid, ent, n=1, minlen=0):
    q = {"product_id": pid, "owner_entity_id": ent, "status": "available", "length_reserved": {"$in": [0, None]},
         "length_remaining": {"$gt": minlen}, "reserved_ref": {"$in": [None, {}]}}
    return list(mdb.inventory_rolls.find(q, {"_id": 0, "id": 1, "roll_no": 1, "length_remaining": 1, "warehouse_id": 1}).limit(n))


def pa(so):
    return [(p["type"], p["status"]) for p in so.get("pending_approvals", [])]


def cut(b, keys=("status", "stage", "sub_status", "credit_hold", "payment_status")):
    return {k: b.get(k) for k in keys} if isinstance(b, dict) and "status" in b else b


# ---------- KREDIT ----------
sk = Api("sales.kanda@kainnusantara.id", "ent_kanda"); sak = Api("salesadmin.kanda@kainnusantara.id", "ent_kanda")
mgr_k = Api("manager@kainnusantara.id", "ent_kanda")
CK = "cust_ff0f577aceba"; PK = "prod_b2b69960cf6b"
c, so = sk.post("/sales-orders", {"customer_id": CK, "shipping_address_id": "addr_0712478c785e", "entity_id": "ent_kanda",
                                  "items": [{"product_id": PK, "quantity": 700, "unit": "kg"}], "payment_term_code": "NET30",
                                  "confirm_mixed_lot": True})
so = need("sales.kanda: SO 700 kg (> limit 25 jt)", c, so)
SOK = so["id"]
print("kredit SO", so["number"], so["grand_total"], cut(so), pa(so), "warning", so.get("credit_warning"))
c, b = sak.post(f"/sales-orders/{SOK}/verify", {"note": "UAT"})
step("sadm.kanda: verifikasi (kredit hold = peringatan, bukan blokir)", c, {"warn": (b.get("verification") or {}).get("warnings")} if isinstance(b, dict) else b)
c, b = sak.post(f"/sales-orders/{SOK}/submit-for-approval"); step("submit", c, cut(b))
c, b = mgr_k.post(f"/sales-orders/{SOK}/approve"); step("NEG approve saat kredit pending", c, b, (409,))
c, so = mgr_k.get(f"/sales-orders/{SOK}")
e = next((p for p in so["pending_approvals"] if p["type"] == "kredit" and p["status"] == "pending"), None)
if e:
    c, b = mgr_k.post(f"/sales-orders/{SOK}/approvals/{e['id']}/decide", {"decision": "approve", "notes": "UAT disetujui direktur"})
    step("mgr: setujui kredit -> SO otomatis Approved", c, cut(b))
print("SO_KREDIT", SOK)

# ---------- CBD ----------
sales = Api("sales@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id"); wh = Api("warehouse@kainnusantara.id")
whadm = Api("wh.admin@kainnusantara.id"); fin = Api("finance@kainnusantara.id")
P = "prod_a17bedf5b3f0"  # DENIM TENCEL BLUE BLACK GARMENT A
rl = free_rolls(P, "ent_ksc", 3, 50)


def mk(term, roll, **extra):
    body = {"customer_id": "cust_toko_kain", "shipping_address_id": "", "entity_id": "ent_ksc",
            "items": [{"product_id": P, "quantity": roll["length_remaining"], "unit": "yard", "purchase_mode": "roll",
                       "roll_lines": [{"roll_id": roll["id"], "take_qty": 0}], "target_quantity": roll["length_remaining"],
                       "rounding_choice": "exact"}],
            "payment_term_code": term, "confirm_mixed_lot": True}
    body.update(extra)
    c, so = sales.post("/sales-orders", body)
    return need(f"sales: SO {term} {extra}", c, so)


def to_confirm(SO):
    c, b = sadm.post(f"/sales-orders/{SO}/verify", {"note": "UAT"}); step("verifikasi", c, {"v": (b.get("verification") or {}).get("status")} if isinstance(b, dict) else b)
    c, b = sadm.post(f"/sales-orders/{SO}/submit-for-approval"); step("submit", c, cut(b))
    c, b = sadm.post(f"/sales-orders/{SO}/confirm"); step("confirm", c, cut(b))


def tasks_of(SO, status=None):
    c, t = wh.get("/outbound/tasks", params={"status": status} if status else None)
    return [x for x in (t if isinstance(t, list) else []) if x.get("order_id") == SO]


def pick_all(SO, roll):
    for t in tasks_of(SO):
        c, b = wh.post(f"/outbound/tasks/{t['id']}/scan-pick", params={"actual_qty": roll["length_remaining"], "roll_id": roll["id"]})
        step("pick", c, cut(b, ("status", "picked_qty")))


def dispatch(SO, label):
    out = None
    for t in tasks_of(SO):
        c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
        if c != 200 and "RFID" in short(b):
            whadm.post(f"/outbound/so/{SO}/loading-check/override", {"reason": "UAT tanpa RFID - manual"})
            c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
        out = (c, b)
        step(label, c, {"sj": (b.get("shipment") or {}).get("shipment_no")} if isinstance(b, dict) and "shipment" in b else b, (200, 400, 409))
    return out


so = mk("CBD", rl[0]); SOC = so["id"]
print("CBD SO", so["number"], so.get("payment_term_name"), so["grand_total"])
to_confirm(SOC)
pick_all(SOC, rl[0])
res = dispatch(SOC, "CEK: dispatch SO CBD sebelum dibayar")
if res and res[0] == 200:
    print("TEMUAN?: SO CBD (Bayar Sebelum Kirim) bisa dikirim walau payment_status=pending")
print("SO_CBD", SOC)

# ---------- AMBIL SENDIRI ----------
today = datetime.date.today().isoformat()
tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
c, b = sales.post("/sales-orders", {"customer_id": "cust_toko_kain", "shipping_address_id": "", "entity_id": "ent_ksc",
                                    "items": [{"product_id": P, "quantity": 10, "unit": "yard"}], "fulfillment_method": "ambil"})
step("NEG ambil tanpa tanggal ditolak", c, b, (400,))
so = mk("NET30", rl[1], fulfillment_method="ambil", pickup_date=tomorrow); SOP = so["id"]
to_confirm(SOP)
st = tasks_of(SOP, "scheduled")
step("ambil besok: tugas gudang di-hold (scheduled)", 200, [(t["id"], t["status"]) for t in st])
for t in st:
    c, b = wh.post(f"/outbound/tasks/{t['id']}/scan-pick", params={"actual_qty": 1, "roll_id": rl[1]["id"]})
    step("NEG pick saat hold ditolak", c, b, (400,))
    c, b = wh.post(f"/outbound/tasks/{t['id']}/release"); step("gudang: rilis hold manual", c, cut(b, ("status",)))
pick_all(SOP, rl[1])
dispatch(SOP, "dispatch SO ambil sendiri")
c, shp = wh.get("/shipments", params={"order_id": SOP})
sl = [s for s in shp if s.get("order_id") == SOP]
c, dv = whadm.post("/logistics/deliveries", {"shipment_ids": [s["id"] for s in sl], "mode": "self_pickup"})
step("logistik: pengiriman 'Diambil pelanggan'", c, {"n": dv.get("number"), "s": dv.get("status"), "code": dv.get("pickup_code")} if isinstance(dv, dict) else dv)
if isinstance(dv, dict) and dv.get("id"):
    c, b = whadm.post(f"/logistics/deliveries/{dv['id']}/pickup-handover", {"pickup_code": "000000", "picker_name": "Pak Hendra", "picker_id_no": "3201"})
    step("NEG serah terima kode salah", c, b, (400,))
    c, sdv = sales.get(f"/logistics/deliveries/{dv['id']}")
    code = (sdv or {}).get("pickup_code") if isinstance(sdv, dict) else None
    print("kode pickup terlihat oleh sales:", code)
    if code:
        c, b = whadm.post(f"/logistics/deliveries/{dv['id']}/pickup-handover", {"pickup_code": code, "picker_name": "Pak Hendra", "picker_id_no": "3201"})
        step("serah terima ke pengambil (kode cocok)", c, {"s": b.get("status")} if isinstance(b, dict) else b)
print("SO_PICKUP", SOP)

# ---------- QC sebelum kirim ----------
so = mk("NET30", rl[2], qc_request="full"); SOQ = so["id"]
print("QC SO", so["number"], so.get("qc_request"))
to_confirm(SOQ)
pick_all(SOQ, rl[2])
dispatch(SOQ, "CEK: dispatch SO minta QC sebelum QC lulus (harus ditolak)")
print("SO_QC", SOQ)
dump("/tmp/uat_br2.json")
