from flow import *
oid=d.sales_orders.find_one({"number":"KSC/SO-00002"})["id"]
print("== F-S1 lanjutan (ambil dengan pindai roll)")
print("roll state",[(r["id"],r["status"],r.get("reserved_ref"),r.get("reserved_for")) for r in d.inventory_rolls.find({"id":{"$in":["roll_c12bec196c26","roll_0ae73ed33bbc"]}})])
print("tasks",[(t["id"],t["status"],t.get("quantity"),t.get("picked_qty")) for t in d.wms_tasks.find({"order_id":oid})])
push(oid); so=snap(oid)
print("AR/invoices",[(k,d[k].count_documents({"order_id":oid})) for k in ("invoices","ar_invoices","tax_invoices","shipments","logistics_deliveries")])
print("keys so",[k for k in so.keys()])
