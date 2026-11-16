"""Siapkan satu SPK uji (lingkungan A) dengan tagihan jasa menunggu faktur — untuk tangkapan layar MP-T4b."""
import os, sys
sys.path.insert(0, "/home/user/KNHOST/backend/tests")
import requests
import test_bp_MPT4a_teruskan as t
import test_bp_MPT4b_grir_makloon as g
g._setel("saat_faktur")
try:
    f = t._fixture()
    adm, md = t._login("admin@kainnusantara.id"), t._login("md@kainnusantara.id")
    k = f"sct_mpt4b_{f['t']}"
    t.DB.supplier_contracts.insert_one({"id": k, "contract_number": f"KSC/SCT-M4B{f['t']}", "contract_type": "makloon",
        "partner_kind": "makloon", "partner_id": f["m"]["pre"], "process_type": "pre_treatment", "tariff_basis": "yard",
        "tariff_rate": 5000, "tariff_qty_source": "output", "status": "active", "entity_id": t.KSC})
    body = {"mode": "process_only", "material_product_id": f["p"]["grey"], "material_qty": 200, "material_unit": "yard",
            "from_warehouse_id": f["wh"], "target_warehouse_id": f["wh"], "entity_id": t.KSC,
            "manual_material_reason": "uji MP-T4b", "route_reason": "uji MP-T4b", "purpose": {"kind": "stok"},
            "steps": [{"stage_code": "pfp", "process_type": "pre_treatment", "makloon_id": f["m"]["pre"], "contract_id": k,
                       "output_product_id": f["p"]["pfp"], "input_qty": 200},
                      {"stage_code": "printing", "process_type": "printing", "makloon_id": f["m"]["prn"],
                       "output_product_id": f["p"]["jadi"]}]}
    o = requests.post(f"{t.BASE}/makloon-orders", headers=adm, json=body, timeout=60).json()
    requests.post(f"{t.BASE}/makloon-orders/{o['id']}/issue", headers=adm, json={"step_seq": 1, "roll_ids": f["rolls"]}, timeout=60).raise_for_status()
    requests.post(f"{t.BASE}/makloon-orders/{o['id']}/steps/1/forward", headers=md, timeout=90,
                  json={"actual_output_qty": 190, "rolls": [{"length": 95, "lot": "A"}, {"length": 95, "lot": "B"}]}).raise_for_status()
    print(o["mko_number"], o["id"])
finally:
    g._setel("saat_terima")
