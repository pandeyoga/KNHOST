"""KP-T4 U15 — di MongoDB ASLI (lingkungan A): dua penyetuju menyetujui PO yang sama bersamaan → tepat satu 200.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`),
sesudah KP-T4 (b) (pintu PO bertanya ke Aturan Persetujuan). Database tiruan tidak menguji balapan, karena itu butir ini
hanya sah di sini (`docs/blueprint/03_LINGKUNGAN_UJI.md` §1).

Fixture: satu PO Rp150.000.000 di `ent_ksc` berstatus menunggu persetujuan disisipkan langsung (pembuat = akun lain,
rantai satu jenjang dari `build_approval_chain` kini = Aturan Persetujuan: ≥ Rp100 jt → J1). Dua manajer data acuan
(`manager@`, `manager.printing@`) menekan Setujui bersamaan. Harapan (perilaku lama tetap, KN-B04 CAS): satu 200, satu
409. PO dan tugas penerimaannya dihapus di akhir. Tidak untuk database berisi data nyata.
"""
import concurrent.futures
import datetime
import os
import uuid

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
JT = 1_000_000


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def akun():
    if not DB.users.find_one({"email": "manager.printing@kainnusantara.id"}):
        pytest.skip("data acuan belum dipulihkan (scripts/dev_restore_demo.sh)")
    return {"mgr": _login("manager@kainnusantara.id"), "mgr2": _login("manager.printing@kainnusantara.id")}


def _po():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pid = f"po_kpt4_{uuid.uuid4().hex[:8]}"
    chain = [{"level": 1, "label": "Persetujuan", "required_role": "manager", "policy_kind": "purchase_order",
              "roles": ["admin", "manager"], "status": "pending", "approved_by": "", "approved_by_id": "",
              "approved_at": ""}]
    doc = {"id": pid, "po_number": pid.upper(), "entity_id": ENT, "status": "waiting_approval",
           "approval_status": "pending", "required_approval_role": "manager", "approval_chain": chain,
           "approval_level_current": 1, "version": 1, "created_by": "Pembuat Uji KP-T4",
           "created_by_id": "usr_pembuat_kpt4", "supplier_id": "", "supplier_name": "Pemasok Uji", "items": [],
           "total_amount": 150 * JT, "grand_total": 150 * JT, "timeline": [], "created_at": now, "updated_at": now}
    DB.purchase_orders.insert_one(dict(doc))
    return pid


def test_U15_dua_manajer_bersamaan_satu_menang(akun):
    pid = _po()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            futs = [ex.submit(requests.post, f"{BASE}/purchase-orders/{pid}/approve", headers=h, json={}, timeout=60)
                    for h in (akun["mgr"], akun["mgr2"])]
            kode = sorted(f.result().status_code for f in futs)
        assert kode == [200, 409], kode
        po = DB.purchase_orders.find_one({"id": pid}, {"_id": 0, "status": 1, "approval_chain": 1})
        assert po["status"] == "pending"
        assert sum(1 for lv in po["approval_chain"] if lv["status"] == "approved") == 1
    finally:
        DB.purchase_orders.delete_one({"id": pid})
        DB.wms_tasks.delete_many({"po_id": pid})
