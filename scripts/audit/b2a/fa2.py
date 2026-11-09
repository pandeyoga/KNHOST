"""Alur A bagian 2 — SPK MD Quality (po_receipt) → tutup 'terima' → draf PA → verifikasi label → terbit → kirim → trip."""
import json
import kn
exec(open("/tmp/b2a/fa_legacy.py").read().split("stp(\"0_awal\")")[0])  # pakai ulang stp()

spk = kn.db.inspections.find_one({"task_id": TID}, {"_id": 0})
SID, LID = spk["id"], spk["lines"][0]["id"]
mdq = kn.db.users.find_one({"email": "mdquality@kainnusantara.id"}, {"_id": 0, "id": 1})
# siapa boleh menugaskan? coba petugas gudang dulu, lalu wh.admin
kn.call(W, "POST", f"/inspections/{SID}/assign", {"assigned_to": mdq["id"]}, entity="ent_ksc")
kn.call("wh.admin", "POST", f"/inspections/{SID}/assign", {"assigned_to": mdq["id"]}, entity="ent_ksc")
kn.call("mdquality", "POST", f"/inspections/{SID}/lines/{LID}/inspect",
        {"part": "md_quality", "color_result": "sesuai", "handfeel_result": "sesuai", "handfeel_score": 4}, entity="ent_ksc")
stp("3_mdq_inspected")
# tutup oleh MD Quality? oleh wh.admin?
c, o = kn.call("mdquality", "POST", f"/inspections/{SID}/finish", {"decision": "terima", "remark": "sesuai sample"}, entity="ent_ksc")
if c != 200:
    c, o = kn.call("wh.admin", "POST", f"/inspections/{SID}/finish", {"decision": "terima", "remark": "sesuai sample"}, entity="ent_ksc")
R["finish_resp"] = o
stp("4_spk_finished")
pa = (R["4_spk_finished"]["pa"] or [None])[0]
print("PA draft detail:", pa and {k: pa.get(k) for k in ("pa_number", "status", "to_warehouse_name", "purpose", "auto")})
json.dump(R, open("/tmp/b2a/fa2_state.json", "w"), default=str)
