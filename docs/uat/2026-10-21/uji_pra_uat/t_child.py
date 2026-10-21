SO="so_d9aa799376ff"
wh = Api("warehouse@kainnusantara.id"); whadm = Api("wh.admin@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id")
c, tasks = wh.get("/outbound/tasks", params={"status":"partially_shipped"})
tl = [t for t in (tasks if isinstance(tasks, list) else []) if t.get("order_id") == SO]
print("tasks", [(t["id"], t["status"], t.get("picked_qty"), t.get("shipped_qty"), t.get("quantity")) for t in tl])
t = tl[0]
# picking list yang dilihat gudang
c, b = wh.get(f"/outbound/so/{SO}/surat-jalan")
print("sj-preview", c, short(b, 300))
c, b = wh.post(f"/outbound/tasks/{t['id']}/scan-pick", params={"actual_qty": 28.41, "roll_id": "RL-36312-1"})
step("wh: scan-pick roll ANAK RL-36312-1", c, {k: b.get(k) for k in ("status","picked_qty")} if isinstance(b, dict) and "status" in b else b)
c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
if c != 200:
    step("info dispatch", c, b, (400,409))
    c2,b2 = whadm.post(f"/outbound/so/{SO}/loading-check/override", {"reason":"UAT tanpa RFID - manual"}); step("override", c2, {"r":b2.get("result")} if isinstance(b2,dict) else b2)
    c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
step("wh: dispatch sisa", c, {"task": (b.get("task") or {}).get("status"), "sj": (b.get("shipment") or {}).get("shipment_no"), "qty": (b.get("shipment") or {}).get("qty")} if isinstance(b, dict) and "task" in b else b)
c, so = sadm.get(f"/sales-orders/{SO}")
print("SO:", so.get("status"), so.get("stage"))
print("alloc rolls:", [(r.get("roll_no"), r.get("length")) for a in so.get("allocations",[]) for r in a.get("rolls",[])])
dump("/tmp/uat_child.json")
