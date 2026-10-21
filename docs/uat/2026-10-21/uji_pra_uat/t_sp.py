# Cabang HARGA KHUSUS pada SO: ajukan -> verifikasi -> submit -> approve diblokir -> tolak -> ajukan ulang -> setujui
PID = "prod_bffe7f853835"   # DENIM TENCEL HITAM A, Rp 20.000/yd
CUST = "cust_toko_kain"
sales = Api("sales@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id"); mgr = Api("manager@kainnusantara.id")
adm = Api("admin@kainnusantara.id")


def mk(qty=110):
    c, so = sales.post("/sales-orders", {"customer_id": CUST, "shipping_address_id": "", "entity_id": "ent_ksc",
                                         "items": [{"product_id": PID, "quantity": qty, "unit": "yard"}],
                                         "payment_term_code": "NET30", "confirm_mixed_lot": True})
    return need("sales: buat SO", c, so)


def pa(so):
    return [(p["type"], p["status"], p.get("requested_price")) for p in so.get("pending_approvals", [])]


so = mk()
SO = so["id"]
print("SO", so["number"], so["grand_total"], so["items"][0]["price"])
c, b = sales.post(f"/sales-orders/{SO}/request-special-price", {"product_id": PID, "requested_price": 18000, "reason": ""})
step("NEG harga khusus tanpa alasan ditolak", c, b, (400,))
c, b = sales.post(f"/sales-orders/{SO}/request-special-price", {"product_id": PID, "requested_price": 18000, "reason": "UAT nego volume"})
step("sales: ajukan harga khusus 18.000", c, {"status": b.get("status"), "sub": b.get("sub_status"), "pa": pa(b)} if isinstance(b, dict) and "status" in b else b)
c, b = sadm.post(f"/sales-orders/{SO}/verify", {"note": "UAT"})
step("sadm: verifikasi", c, {"v": (b.get("verification") or {}).get("status")} if isinstance(b, dict) else b)
c, b = sadm.post(f"/sales-orders/{SO}/submit-for-approval")
step("sadm: ajukan persetujuan", c, {"status": b.get("status"), "sub": b.get("sub_status")} if isinstance(b, dict) and "status" in b else b)
c, b = mgr.post(f"/sales-orders/{SO}/approve")
step("NEG approve SO saat harga khusus pending diblokir", c, b, (409,))
c, b = sadm.post(f"/sales-orders/{SO}/confirm")
step("NEG confirm saat harga pending ditolak", c, b, (409,))
c, so = mgr.get(f"/sales-orders/{SO}")
ent = next(p for p in so["pending_approvals"] if p["type"] == "special_price" and p["status"] == "pending")
c, b = sales.post(f"/sales-orders/{SO}/approvals/{ent['id']}/decide", {"decision": "approve"})
step("NEG sales memutus harga khusus ditolak", c, b, (403,))
c, b = mgr.post(f"/sales-orders/{SO}/approvals/{ent['id']}/decide", {"decision": "reject", "notes": "terlalu rendah"})
step("mgr: TOLAK harga khusus", c, {"status": b.get("status"), "sub": b.get("sub_status"), "pa": pa(b)} if isinstance(b, dict) and "status" in b else b)
c, b = mgr.post(f"/sales-orders/{SO}/approve")
step("NEG approve setelah ditolak diblokir", c, b, (409,))
# Ajukan ulang (status sekarang waiting_approval) — apakah bisa?
c, b = sales.post(f"/sales-orders/{SO}/request-special-price", {"product_id": PID, "requested_price": 19000, "reason": "UAT nego ulang"})
step("sales: ajukan ulang harga khusus 19.000", c, {"status": b.get("status"), "sub": b.get("sub_status"), "pa": pa(b)} if isinstance(b, dict) and "status" in b else b, (200, 409))
c, so = mgr.get(f"/sales-orders/{SO}")
ent2 = next((p for p in so["pending_approvals"] if p["type"] == "special_price" and p["status"] == "pending"), None)
if ent2:
    c, b = mgr.post(f"/sales-orders/{SO}/approvals/{ent2['id']}/decide", {"decision": "approve", "notes": "ok 19rb"})
    step("mgr: SETUJUI harga khusus ulang", c, {"status": b.get("status"), "sub": b.get("sub_status"), "pa": pa(b), "price": b["items"][0]["price"], "grand": b.get("grand_total")} if isinstance(b, dict) and "status" in b else b)
    c, b = mgr.post(f"/sales-orders/{SO}/approve")
    step("mgr: approve SO setelah harga ulang disetujui", c, {"status": b.get("status")} if isinstance(b, dict) and "status" in b else b, (200,))
    c, b = sadm.post(f"/sales-orders/{SO}/confirm")
    step("sadm: confirm", c, {"status": b.get("status")} if isinstance(b, dict) and "status" in b else b, (200,))
print("SO_SP1", SO)

# --- Skenario 2: alokasi berubah sesudah harga diajukan
so = mk(60)
SO2 = so["id"]
c, b = sales.post(f"/sales-orders/{SO2}/request-special-price", {"product_id": PID, "requested_price": 18500, "reason": "UAT alokasi berubah"})
step("sales: ajukan harga khusus SO2", c, {"pa": pa(b)} if isinstance(b, dict) and "pending_approvals" in b else b)
c, cand = sadm.get(f"/sales-orders/{SO2}/items/{PID}/roll-candidates")
rows = cand.get("items", cand.get("rolls", [])) if isinstance(cand, dict) else (cand if isinstance(cand, list) else [])
print("kandidat roll:", c, len(rows), short(rows[:2], 400))
cur = [r["roll_id"] for a in so.get("allocations", []) for r in a.get("rolls", [])]
alt = next((r for r in rows if (r.get("roll_id") or r.get("id")) not in cur and float(r.get("length_remaining") or r.get("length") or 0) >= 60
            and not r.get("blocked") and r.get("eligible", True)), None)
if alt:
    rid = alt.get("roll_id") or alt.get("id")
    c, b = sadm.post(f"/sales-orders/{SO2}/items/{PID}/reallocate", {"roll_lines": [{"roll_id": rid, "take_qty": 60}]})
    step("sadm: ganti roll (alokasi manual)", c, {"rolls": [r.get("roll_no") for a in b.get("allocations", []) for r in a.get("rolls", [])]} if isinstance(b, dict) and "allocations" in b else b)
    c, so2 = mgr.get(f"/sales-orders/{SO2}")
    e = next((p for p in so2["pending_approvals"] if p["type"] == "special_price" and p["status"] == "pending"), None)
    if e:
        c, b = mgr.post(f"/sales-orders/{SO2}/approvals/{e['id']}/decide", {"decision": "approve"})
        step("NEG setujui harga setelah alokasi berubah ditolak", c, b, (409,))
    else:
        print("info: entri harga pending hilang setelah ganti roll", pa(so2))
print("SO_SP2", SO2)
dump("/tmp/uat_sp.json")
