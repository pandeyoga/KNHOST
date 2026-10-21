SO = "so_485cecbd17f4"
mdq = Api("mdquality@kainnusantara.id"); qc = Api("qc@kainnusantara.id"); mgr = Api("manager@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id"); whadm=Api("wh.admin@kainnusantara.id")
c, ins = mdq.get("/inspections", params={"source": "receiving"})
I = next(x for x in ins["items"] if x.get("ref_doc_number") == "KSC/PO-00028")
c, d = mdq.get(f"/inspections/{I['id']}")
print("INS", d["number"], d["status"], d.get("kind"), "lines", [(l["id"], l.get("roll_no"), l.get("qty"), l.get("status")) for l in d.get("lines", [])], "parts", d.get("parts") or d.get("required_parts"))
for who, a in (("mdq", mdq), ("qc", qc)):
    c, b = a.post(f"/inspections/{I['id']}/start"); step(f"{who}: mulai inspeksi", c, {"s": b.get("status")} if isinstance(b, dict) and "status" in b else b, (200, 400, 403, 409))
for l in d.get("lines", []):
    c, b = mdq.post(f"/inspections/{I['id']}/lines/{l['id']}/inspect", {"part": "md_quality", "color_result": "sesuai", "handfeel_result": "sesuai", "handfeel_score": 4, "decision": "terima"})
    step(f"MDQ: warna/handfeel sesuai {l.get('roll_no')}", c, {"s": b.get("status")} if isinstance(b, dict) and "status" in b else b, (200, 400, 403))
    c, b = qc.post(f"/inspections/{I['id']}/lines/{l['id']}/inspect", {"part": "qc", "defects": [], "inspect_length_yard": 0, "decision": "terima"})
    step(f"QC: 4-point {l.get('roll_no')}", c, {"s": b.get("status")} if isinstance(b, dict) and "status" in b else b, (200, 400, 403))
for who, a in (("mdq", mdq), ("qc", qc), ("whadm", whadm), ("mgr", mgr)):
    c, b = a.post(f"/inspections/{I['id']}/finish", {"decision": "terima", "remark": "UAT"})
    if step(f"{who}: tutup inspeksi (terima)", c, {"s": b.get("status")} if isinstance(b, dict) and "status" in b else b, (200, 400, 403)) and c == 200:
        break
c, so = sadm.get(f"/sales-orders/{SO}")
print("SO setelah barang lulus:", so.get("status"), so.get("stage"), so.get("sub_status"), [(x.get("backorder_qty"), x.get("reserved_qty"), x.get("status")) for x in so.get("backorders", [])])
