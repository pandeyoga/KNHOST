"""MP-T4a — di MongoDB ASLI (lingkungan A): kain diteruskan langsung dari mitra ke mitra berikut (K-62, K-66, K-67, K-69).

SPK dua langkah: greige 200 yd @ Rp 20.000 → PFP @ mitra pre-treatment → printing @ mitra printing.
1. Kirim bahan langkah 1 (4 roll greige × 50 yd = 200 yd; nilai bahan 200 × 20.000 = Rp 4.000.000).
2. MD meneruskan hasil langkah 1 (190 yd PFP, dua roll 95 yd) langsung ke mitra printing.
   Harapan: langkah 1 `received` + `forwarded_to.seq = 2`; langkah 2 `issued` dengan bahan 190 yd dan
   `material_value` = nilai hasil langkah 1; dua roll PFP berstatus `subcon` (di mitra), tidak ada roll PFP `available`;
   jurnal terima langkah 1 (Dr 1-1300 / Cr 1-1350) dan jurnal kirim langkah 2 (Dr 1-1350 / Cr 1-1300) bernilai sama.
3. Varian K-67 (hasil antara tanpa rincian roll): satu roll gabungan (lot dinomori sistem).
4. Ditolak: langkah terakhir; langkah berikut tanpa mitra.

Uji HTTP terhadap backend yang berjalan (`REACT_APP_BACKEND_URL`); produk, mitra, gudang, roll greige disisipkan langsung
ke database uji lokal sebagai FIXTURE (saldo dibangun ulang `rebuild_balance`). Bukan untuk data nyata.
"""
import os
import sys
import uuid

import pymongo
import pytest
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
KSC = "ent_ksc"


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": KSC}


def _fixture():
    t = uuid.uuid4().hex[:6].upper()
    wh = f"wh_mpt4_{t}"
    DB.warehouses.insert_one({"id": wh, "code": f"M4{t}", "name": f"Gudang Uji MP-T4a {t}", "entity_id": KSC,
                              "is_active": True, "active": True, "roles": ["storage"], "sharing_mode": "dedicated",
                              "entity_ids": [KSC], "zones": []})
    base = {"status": "active", "is_active": True, "lifecycle": "produksi", "category": "Kain", "grade": "A",
            "fabric_type": "woven", "gramasi": 120, "lebar": 1.5, "base_unit": "yard", "entity_id": KSC}
    p = {}
    for k, st in (("grey", "grey"), ("pfp", "pfp"), ("jadi", "finished")):
        p[k] = f"prod_mpt4_{k}_{t}"
        DB.products.insert_one({**base, "id": p[k], "sku": f"MPT4-{k.upper()}-{t}", "name": f"Uji {k} {t}", "stage": st})
    m = {"pre": f"mak_mpt4_pre_{t}", "prn": f"mak_mpt4_prn_{t}"}
    DB.makloons.insert_many([
        {"id": m["pre"], "code": f"MPT4-PRE-{t}", "name": f"Mitra Pretreat {t}", "process_types": ["pre_treatment"],
         "entity_id": KSC, "status": "active"},
        {"id": m["prn"], "code": f"MPT4-PRN-{t}", "name": f"Mitra Printing {t}", "process_types": ["printing"],
         "entity_id": KSC, "status": "active"}])
    rolls = []
    for i in range(4):
        rid = f"roll_mpt4_{i}_{t}"
        rolls.append(rid)
        DB.inventory_rolls.insert_one({
            "id": rid, "roll_no": f"M4{i}{t}", "product_id": p["grey"], "warehouse_id": wh, "owner_entity_id": KSC,
            "entity_id": KSC, "unit": "yard", "status": "available", "length": 50, "length_initial": 50,
            "length_remaining": 50, "unit_cost": 20_000, "base_unit_cost": 20_000, "grade": "A", "lot": f"LOT{t}",
            "created_at": "2026-11-01T00:00:00+00:00"})
    # Saldo dibangun ulang di proses terpisah (klien motor terikat pada satu event loop).
    import subprocess
    subprocess.run([sys.executable, "-c", "import asyncio,sys; sys.path.insert(0, '.'); "
                    "from services.roll_service import rebuild_balance; "
                    f"asyncio.run(rebuild_balance('{p['grey']}', '{wh}', '{KSC}'))"],
                   cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), check=True)
    return {"t": t, "wh": wh, "p": p, "m": m, "rolls": rolls}


def _spk(h, f, *, mitra2=True):
    body = {"mode": "process_only", "material_product_id": f["p"]["grey"], "material_qty": 200, "material_unit": "yard",
            "from_warehouse_id": f["wh"], "target_warehouse_id": f["wh"], "entity_id": KSC,
            "manual_material_reason": "uji MP-T4a", "route_reason": "uji MP-T4a", "purpose": {"kind": "stok"},
            "steps": [{"stage_code": "pfp", "process_type": "pre_treatment", "makloon_id": f["m"]["pre"],
                       "output_product_id": f["p"]["pfp"], "input_qty": 200},
                      {"stage_code": "printing", "process_type": "printing",
                       "makloon_id": f["m"]["prn"] if mitra2 else "", "output_product_id": f["p"]["jadi"]}]}
    r = requests.post(f"{BASE}/makloon-orders", headers=h, json=body, timeout=60)
    assert r.status_code == 200, r.text
    mko = r.json()["id"]
    r = requests.post(f"{BASE}/makloon-orders/{mko}/issue", headers=h, json={"step_seq": 1, "roll_ids": f["rolls"]},
                      timeout=60)
    assert r.status_code == 200, r.text
    return mko


@pytest.fixture(scope="module")
def dunia():
    return _fixture()


def test_MPT4a_U6_teruskan_mitra_ke_mitra(dunia):
    adm, md = _login("admin@kainnusantara.id"), _login("md@kainnusantara.id")
    mko = _spk(adm, dunia)
    r = requests.post(f"{BASE}/makloon-orders/{mko}/steps/1/forward", headers=md, timeout=60, json={
        "actual_output_qty": 190, "rolls": [{"length": 95, "lot": "PFP-A"}, {"length": 95, "lot": "PFP-B"}]})
    assert r.status_code == 200, r.text
    o = DB.makloon_orders.find_one({"id": mko}, {"_id": 0})
    s1, s2 = o["steps"]
    assert s1["status"] == "received" and s1["forwarded_to"]["seq"] == 2
    assert s2["status"] == "issued" and s2["forwarded_from"]["seq"] == 1
    assert round(float(s2["input_qty"]), 2) == 190.0
    assert abs(float(s2["material_value"]) - float(s1["output_value"])) < 1.0
    pfp = list(DB.inventory_rolls.find({"product_id": dunia["p"]["pfp"]}, {"_id": 0, "status": 1, "length_remaining": 1}))
    assert sorted(x["status"] for x in pfp) == ["subcon", "subcon"]
    assert not [x for x in pfp if x["status"] == "available"]
    terima = sum(float(x.get("total_debit") or sum(float(ln.get("debit") or 0) for ln in x["lines"]))
                 for x in DB.journal_entries.find({"status": {"$ne": "void"}, "source_type": "subcon_receipt",
                                                   "source_id": {"$regex": f"^{mko}"}}, {"_id": 0}))
    kirim2 = sum(sum(float(ln.get("debit") or 0) for ln in x["lines"])
                 for x in DB.journal_entries.find({"status": {"$ne": "void"}, "source_type": "subcon_issue",
                                                   "source_id": f"{mko}:2"}, {"_id": 0}))
    assert terima > 0 and abs(terima - kirim2) < 1.0, (terima, kirim2)
    assert any(e.get("event") == "forwarded" for e in o.get("timeline") or [])


def test_MPT4a_U7_hasil_antara_tanpa_rincian_roll(dunia):
    """Ulang dari bahan baru: hanya jumlah 188 yd → satu roll gabungan 188 yd di mitra berikut."""
    f = _fixture()
    adm, md = _login("admin@kainnusantara.id"), _login("md@kainnusantara.id")
    mko = _spk(adm, f)
    r = requests.post(f"{BASE}/makloon-orders/{mko}/steps/1/forward", headers=md, timeout=60,
                      json={"actual_output_qty": 188})
    assert r.status_code == 200, r.text
    pfp = list(DB.inventory_rolls.find({"product_id": f["p"]["pfp"]}, {"_id": 0, "status": 1, "lot": 1,
                                                                        "length_remaining": 1}))
    # nomor lot diberi penomoran lot PT (bukan teks "TERUS-…" usulan) — satu roll gabungan di mitra
    assert len(pfp) == 1 and pfp[0]["status"] == "subcon"
    assert round(float(pfp[0]["length_remaining"]), 2) == 188.0


def test_MPT4a_U8_teruskan_ditolak(dunia):
    f = _fixture()
    adm, md = _login("admin@kainnusantara.id"), _login("md@kainnusantara.id")
    mko = _spk(adm, f, mitra2=False)
    r = requests.post(f"{BASE}/makloon-orders/{mko}/steps/1/forward", headers=md, timeout=60,
                      json={"actual_output_qty": 190})
    assert r.status_code == 400 and "Isi mitra langkah 2" in r.json()["detail"], r.text
    r = requests.post(f"{BASE}/makloon-orders/{mko}/steps/2/forward", headers=md, timeout=60,
                      json={"actual_output_qty": 190})
    assert r.status_code == 400 and "langkah terakhir" in r.json()["detail"], r.text
