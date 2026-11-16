"""MP-T5a/5b — di MongoDB ASLI (lingkungan A): surat jalan kirim bahan makloon berisi daftar roll (K-75) dan peruntukan
pengeluaran bahan greige/PFD/PFP (K-74).

1. SPK bahan greige tanpa peruntukan → 400 "Peruntukan wajib …"; dengan peruntukan "toko AB" → 200, tersimpan.
2. Kirim bahan langkah 1 (4 roll × 50 yd) → satu surat jalan `makloon_shipments` bernomor `SJM-`, dari gudang ke mitra
   pre-treatment, 4 baris roll, total 200 yd, membawa peruntukan.
3. MD meneruskan hasil (190 yd, 2 roll) ke mitra printing → surat jalan kedua: dari MITRA pre-treatment ke mitra printing,
   2 baris roll, total 190 yd.
4. Cetak: resolver "makloon_sj" memuat baris per roll, total roll & kuantitas, dan peruntukan.
Fixture sama dengan `test_bp_MPT4a_teruskan.py` (produk, mitra, gudang, roll greige disisipkan langsung; bukan data nyata).
"""
import os
import subprocess
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(__file__))
import test_bp_MPT4a_teruskan as t  # noqa: E402

BASE, DB = t.BASE, t.DB


def _body(f, **extra):
    return {"mode": "process_only", "material_product_id": f["p"]["grey"], "material_qty": 200, "material_unit": "yard",
            "from_warehouse_id": f["wh"], "target_warehouse_id": f["wh"], "entity_id": t.KSC,
            "manual_material_reason": "uji MP-T5", "route_reason": "uji MP-T5",
            "steps": [{"stage_code": "pfp", "process_type": "pre_treatment", "makloon_id": f["m"]["pre"],
                       "output_product_id": f["p"]["pfp"], "input_qty": 200},
                      {"stage_code": "printing", "process_type": "printing", "makloon_id": f["m"]["prn"],
                       "output_product_id": f["p"]["jadi"]}], **extra}


@pytest.fixture(scope="module")
def dunia():
    return t._fixture()


def test_MPT5_U1_peruntukan_wajib_untuk_greige(dunia):
    adm = t._login("admin@kainnusantara.id")
    r = requests.post(f"{BASE}/makloon-orders", headers=adm, json=_body(dunia), timeout=60)
    assert r.status_code == 400, r.text
    assert "Peruntukan wajib" in r.json()["detail"]
    r = requests.post(f"{BASE}/makloon-orders", headers=adm, timeout=60,
                      json=_body(dunia, purpose={"kind": "toko", "store_name": "Toko AB"}))
    assert r.status_code == 200, r.text
    assert r.json()["purpose"]["kind"] == "toko" and r.json()["purpose"]["store_name"] == "Toko AB"


def test_MPT5_U2_surat_jalan_kirim_dan_teruskan():
    dunia = t._fixture()   # bahan sendiri — roll fixture U1 sudah dicadangkan SPK U1
    adm, md = t._login("admin@kainnusantara.id"), t._login("md@kainnusantara.id")
    r = requests.post(f"{BASE}/makloon-orders", headers=adm, timeout=60,
                      json=_body(dunia, purpose={"kind": "stok"}))
    assert r.status_code == 200, r.text
    mko = r.json()["id"]
    r = requests.post(f"{BASE}/makloon-orders/{mko}/issue", headers=adm, timeout=60,
                      json={"step_seq": 1, "roll_ids": dunia["rolls"]})
    assert r.status_code == 200, r.text
    sj1 = DB.makloon_shipments.find_one({"mko_id": mko, "step_seq": 1}, {"_id": 0})
    assert sj1 and sj1["number"].split("/")[-1].startswith("SJM-") or "SJM" in sj1["number"]
    assert sj1["from"]["kind"] == "gudang" and sj1["to"]["makloon_id"] == dunia["m"]["pre"]
    assert len(sj1["rolls"]) == 4 and round(sj1["total_qty"], 2) == 200.0 and sj1["purpose"]["kind"] == "stok"
    r = requests.post(f"{BASE}/makloon-orders/{mko}/steps/1/forward", headers=md, timeout=60, json={
        "actual_output_qty": 190, "rolls": [{"length": 95, "lot": "A"}, {"length": 95, "lot": "B"}]})
    assert r.status_code == 200, r.text
    sj2 = DB.makloon_shipments.find_one({"mko_id": mko, "step_seq": 2}, {"_id": 0})
    assert sj2["from"]["kind"] == "mitra" and sj2["from"]["id"] == dunia["m"]["pre"]
    assert sj2["to"]["makloon_id"] == dunia["m"]["prn"] and sj2["kind"] == "teruskan"
    assert len(sj2["rolls"]) == 2 and round(sj2["total_qty"], 2) == 190.0
    # Cetak: baris per roll + total + peruntukan (resolver dijalankan di proses terpisah — klien motor per event loop)
    out = subprocess.run([sys.executable, "-c", (
        "import asyncio, json, sys; sys.path.insert(0, '.'); from db import db; "
        "from services.pdf_resolvers import DOC_REGISTRY\n"
        "async def main():\n"
        f"    doc = await db.makloon_shipments.find_one({{'id': '{sj1['id']}'}}, {{'_id': 0}})\n"
        "    return await DOC_REGISTRY['makloon_sj']['resolver'](doc, db)\n"
        "res = asyncio.run(main())\n"
        "print(json.dumps({'items': len(res['items']), 'totals': res['totals'], 'meta': res['meta']}))")],
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), capture_output=True, text=True, check=True)
    import json
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert res["items"] == 4
    assert any(x["label"] == "Total Roll" and x["value"] == "4" for x in res["totals"])
    assert any(m["label"] == "Peruntukan" and "Stok" in m["value"] for m in res["meta"])
