"""MP-T4b — di MongoDB ASLI (lingkungan A): jasa makloon menjadi hutang saat faktur mitra dicocokkan (K-78, K-80).

K-82: semua PT memakai `saat_faktur` lewat bawaan registri — lapisan PT KSC dicabut sebelum uji (nilai diwarisi bawaan).
1. SPK greige → PFP (kontrak Rp 5.000/yd hasil) → printing; bahan dikirim (4 roll × 50 yd); hasil langkah 1 190 yd
   diteruskan ke mitra printing (jalur terima hasil yang sama; PT KSC memakai mode Kedatangan sehingga terima langsung
   ditolak). Ongkos jasa 190 × 5.000 = Rp 950.000. Harapan: tagihan jasa `awaiting_invoice`, PPN 0; jurnal jasa Dr WIP 1-1350 950.000 / Cr GR/IR 2-1150 950.000.
2. Faktur mitra Rp 950.000 + PPN 11 % Rp 104.500 dicocokkan → tagihan `posted`, total Rp 1.054.500; jurnal
   Dr 2-1150 950.000 + Dr 1-1500 104.500 / Cr 2-1100 1.054.500. Saldo GR/IR dari dua jurnal ini = 0.
Fixture sama dengan `test_bp_MPT4a_teruskan.py` (bukan data nyata).
"""
import os
import subprocess
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(__file__))
import test_bp_MPT4a_teruskan as t  # noqa: E402

BASE, DB = t.BASE, t.DB
KUNCI = "makloon.jasa_jadi_hutang"


def _jalankan(kode):
    out = subprocess.run([sys.executable, "-c", "import asyncio, sys; sys.path.insert(0, '.')\n" + kode],
                         cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), check=True,
                         capture_output=True, text=True)
    return out.stdout.strip()


@pytest.fixture(scope="module")
def mode_faktur():
    """Cabut lapisan PT KSC (bila ada, mis. sisa uji lama) → nilai diwarisi bawaan registri `saat_faktur`."""
    _jalankan("from services import config_resolver as cr\n"
              "async def main():\n"
              "    try:\n"
              f"        await cr.clear_layer('{KUNCI}', scope_type='entity', scope_id='{t.KSC}', actor='uji MP-T4b', "
              "reason='K-82: semua PT memakai bawaan saat faktur')\n"
              "    except Exception:\n"
              "        pass\n"
              "asyncio.run(main())")
    yield


def test_MPT4b_U10_semua_pt_saat_faktur(mode_faktur):
    """K-82 — setiap PT di data uji memakai `saat_faktur` tanpa lapisan PT."""
    out = _jalankan("from db import db\nfrom services import makloon_ap_service as ap\n"
                    "async def main():\n"
                    "    ids = [e['id'] async for e in db.business_entities.find({}, {'_id': 0, 'id': 1})]\n"
                    "    print(sorted({await ap.ap_mode(i) for i in ids}), len(ids))\n"
                    "asyncio.run(main())")
    modes, n = out.rsplit(" ", 1)
    assert modes == "['saat_faktur']" and int(n) >= 2, out


def _baris(source_type, source_id):
    je = DB.journal_entries.find_one({"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}},
                                     {"_id": 0})
    assert je, (source_type, source_id)
    out = {}
    for ln in je["lines"]:
        d, c = out.get(ln["account_code"], (0.0, 0.0))
        out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2), round(c + float(ln.get("credit") or 0), 2))
    return out


def test_MPT4b_U8_grir_lalu_faktur(mode_faktur):
    f = t._fixture()
    adm, md = t._login("admin@kainnusantara.id"), t._login("md@kainnusantara.id")
    k = f"sct_mpt4b_{f['t']}"
    DB.supplier_contracts.insert_one({"id": k, "contract_number": f"KSC/SCT-M4B{f['t']}", "contract_type": "makloon",
                                      "partner_kind": "makloon", "partner_id": f["m"]["pre"],
                                      "process_type": "pre_treatment", "tariff_basis": "yard", "tariff_rate": 5_000,
                                      "tariff_qty_source": "output", "status": "active", "entity_id": t.KSC})
    body = {"mode": "process_only", "material_product_id": f["p"]["grey"], "material_qty": 200, "material_unit": "yard",
            "from_warehouse_id": f["wh"], "target_warehouse_id": f["wh"], "entity_id": t.KSC,
            "manual_material_reason": "uji MP-T4b", "route_reason": "uji MP-T4b", "purpose": {"kind": "stok"},
            "steps": [{"stage_code": "pfp", "process_type": "pre_treatment", "makloon_id": f["m"]["pre"],
                       "contract_id": k, "output_product_id": f["p"]["pfp"], "input_qty": 200},
                      {"stage_code": "printing", "process_type": "printing", "makloon_id": f["m"]["prn"],
                       "output_product_id": f["p"]["jadi"]}]}
    r = requests.post(f"{BASE}/makloon-orders", headers=adm, json=body, timeout=60)
    assert r.status_code == 200, r.text[:500]
    mko = r.json()["id"]
    r = requests.post(f"{BASE}/makloon-orders/{mko}/issue", headers=adm, timeout=60,
                      json={"step_seq": 1, "roll_ids": f["rolls"]})
    assert r.status_code == 200, r.text[:500]
    r = requests.post(f"{BASE}/makloon-orders/{mko}/steps/1/forward", headers=md, timeout=90, json={
        "actual_output_qty": 190, "rolls": [{"length": 95, "lot": "PFP-A"}, {"length": 95, "lot": "PFP-B"}]})
    assert r.status_code == 200, r.text[:500]
    st = DB.makloon_orders.find_one({"id": mko}, {"_id": 0})["steps"][0]
    bill = DB.vendor_bills.find_one({"id": st["service_bill_id"]}, {"_id": 0})
    assert bill["status"] == "awaiting_invoice" and bill["ap_mode"] == "saat_faktur" and bill["ppn_amount"] == 0
    assert st["service_invoice_status"] == "menunggu_faktur"
    assert _baris("subcon_service", bill["id"]) == {"1-1350": (950_000.0, 0.0), "2-1150": (0.0, 950_000.0)}
    num = DB.makloon_orders.find_one({"id": mko}, {"_id": 0, "mko_number": 1})["mko_number"]
    g = requests.get(f"{BASE}/finance/gr-ir", headers=adm, timeout=60, params={"q": num}).json()
    spk = [x for x in g["items"] if x.get("doc_id") == mko]
    assert len(spk) == 1 and spk[0]["balance"] == 950_000.0 and spk[0]["awaiting_bills"] == [bill["bill_number"]]
    r = requests.post(f"{BASE}/makloon-orders/{mko}/steps/1/service-invoice", headers=adm, timeout=60,
                      json={"supplier_invoice_no": f"INV-M4B-{f['t']}", "net_amount": 950_000, "ppn_amount": 104_500})
    assert r.status_code == 200, r.text[:500]
    bill = DB.vendor_bills.find_one({"id": bill["id"]}, {"_id": 0})
    assert bill["status"] == "posted" and round(bill["grand_total"], 2) == 1_054_500.0
    assert _baris("subcon_service_invoice", bill["id"]) == {
        "2-1150": (950_000.0, 0.0), "1-1500": (104_500.0, 0.0), "2-1100": (0.0, 1_054_500.0)}
    gl = sum(float(ln.get("credit") or 0) - float(ln.get("debit") or 0)
             for je in DB.journal_entries.find({"source_id": bill["id"], "status": {"$ne": "void"}}, {"_id": 0})
             for ln in je["lines"] if ln["account_code"] == "2-1150")
    assert abs(gl) < 0.01
    g = requests.get(f"{BASE}/finance/gr-ir", headers=adm, timeout=60, params={"q": num, "status": "semua"}).json()
    spk = [x for x in g["items"] if x.get("doc_id") == mko]
    assert spk[0]["billed_value"] == 950_000.0 and spk[0]["balance"] == 0.0
    g = requests.get(f"{BASE}/finance/gr-ir", headers=adm, timeout=60, params={"status": "semua"}).json()
    assert round(g["total_balance"] + g["unlinked_balance"], 2) == g["ledger_balance"]


def test_MPT4b_U9_borongan_mitra_ujung_ke_ujung():
    """K-81 (mode cara lama): mitra ujung-ke-ujung mengerjakan pre-treatment + printing dengan satu kontrak borongan
    Rp 2.500.000 (basis lot). Rencana: langkah 1 Rp 0, langkah 2 Rp 2.500.000. Hasil langkah 1 diteruskan ke langkah 2
    (mitra yang sama) → tidak ada tagihan jasa langkah 1; jejak tarif bersumber "borongan"."""
    f = t._fixture()
    adm, md = t._login("admin@kainnusantara.id"), t._login("md@kainnusantara.id")
    mk, k = f"mak_mpt4b_e2e_{f['t']}", f"sct_mpt4b_lot_{f['t']}"
    DB.makloons.insert_one({"id": mk, "code": f"M4B-E2E-{f['t']}", "name": f"Mitra Ujung {f['t']}",
                            "process_types": ["pre_treatment", "printing"], "entity_id": t.KSC, "status": "active"})
    DB.supplier_contracts.insert_one({"id": k, "contract_number": f"KSC/SCT-LOT{f['t']}", "contract_type": "makloon",
                                      "partner_kind": "makloon", "partner_id": mk, "process_type": "",
                                      "tariff_basis": "lot", "tariff_rate": 2_500_000, "tariff_qty_source": "output",
                                      "status": "active", "entity_id": t.KSC})
    body = {"mode": "process_only", "material_product_id": f["p"]["grey"], "material_qty": 200, "material_unit": "yard",
            "from_warehouse_id": f["wh"], "target_warehouse_id": f["wh"], "entity_id": t.KSC,
            "manual_material_reason": "uji MP-T4b", "route_reason": "uji MP-T4b", "purpose": {"kind": "stok"},
            "steps": [{"stage_code": "pfp", "process_type": "pre_treatment", "makloon_id": mk, "contract_id": k,
                       "output_product_id": f["p"]["pfp"], "input_qty": 200},
                      {"stage_code": "printing", "process_type": "printing", "makloon_id": mk, "contract_id": k,
                       "output_product_id": f["p"]["jadi"]}]}
    r = requests.post(f"{BASE}/makloon-orders", headers=adm, json=body, timeout=60)
    assert r.status_code == 200, r.text[:500]
    o = r.json()
    assert [round(s["tariff"], 2) for s in o["steps"]] == [0.0, 2_500_000.0]
    assert round(o["planned_service_cost"], 2) == 2_500_000.0
    r = requests.post(f"{BASE}/makloon-orders/{o['id']}/issue", headers=adm, timeout=60,
                      json={"step_seq": 1, "roll_ids": f["rolls"]})
    assert r.status_code == 200, r.text[:500]
    r = requests.post(f"{BASE}/makloon-orders/{o['id']}/steps/1/forward", headers=md, timeout=90,
                      json={"actual_output_qty": 190})
    assert r.status_code == 200, r.text[:500]
    s1, s2 = DB.makloon_orders.find_one({"id": o["id"]}, {"_id": 0})["steps"]
    assert not s1.get("service_bill_id") and (s1.get("tariff_actual") or {}).get("source") == "borongan"
    assert DB.vendor_bills.count_documents({"makloon_order_id": o["id"]}) == 0
    assert s2["status"] == "issued" and s2["borongan_billed_at_seq"] == 2 and round(s2["tariff"], 2) == 2_500_000.0
