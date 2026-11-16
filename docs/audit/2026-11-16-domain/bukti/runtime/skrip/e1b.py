from e1 import *
t=d.wms_tasks.find_one({"id":"wms_715beb895da8"},{"_id":0})
print("  task",{k:t.get(k) for k in("status","expected_qty","quantity","received_qty","actual_qty","unit")},"scan_log",len(t.get("scan_log",[])),[ (s.get("roll_id"),s.get("actual_qty")) for s in t.get("scan_log",[])][:6])
rl=list(d.inventory_rolls.find({"po_id":"po_a1fabfcd2f89"},{"_id":0})) or list(d.inventory_rolls.find({"batch":"UJI1116"},{"_id":0}))
print("  roll PO",[(r["id"],r.get("roll_no"),r["status"],r.get("length_remaining"),r.get("lot")) for r in rl])
spk=d.inspections.find_one({"task_id":t["id"]},{"_id":0}); print("  SPK lines",[(l.get("roll_id"),l.get("roll_no"),l.get("qty") or l.get("length")) for l in spk["lines"]])
