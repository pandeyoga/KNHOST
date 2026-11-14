"""AG-T1 U4 — di MongoDB ASLI (lingkungan A): dua "Setujui" kartu draf PO dikirim BERSAMAAN.

Harapan: tepat satu 200 (`confirmed`) dan satu 409 ("Draf ini sudah diproses"); jumlah PO dari kartu itu = 1.
Hitungan: kartu berisi 1 produk dari 1 pemasok → 1 kelompok → 1 PO. Klaim `pending → running` atomik
(`find_one_and_update` bersyarat status) sehingga permintaan kedua tidak bisa ikut menjalankan.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); data uji (pemasok, produk, sumber produk)
disisipkan langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`) sebagai FIXTURE, kartu disiapkan & disetujui lewat
API (`POST /api/ai/tools/propose_action`, `POST /api/ai/actions/{id}/confirm`), lalu data uji dihapus. Tidak untuk data
nyata. Tidak memanggil layanan model.
"""
import datetime
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
SUP, PRD = f"sup_agt1_{TAG}", f"prd_agt1_{TAG}"
ALASAN = f"uji AG-T1 U4 {TAG}"


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture()
def siap():
    DB.suppliers.insert_one({"id": SUP, "code": f"AGT1-{TAG}", "name": f"Pemasok Uji AG-T1 {TAG}", "entity_id": "ent_ksc",
                             "status": "active", "created_at": NOW})
    DB.products.insert_one({"id": PRD, "sku": f"AGT1-{TAG}", "name": f"Kain Uji AG-T1 {TAG}", "base_unit": "meter",
                            "is_active": True, "status": "active", "created_at": NOW})
    DB.supplier_items.insert_one({"id": f"si_agt1_{TAG}", "product_id": PRD, "supplier_id": SUP, "entity_id": "ent_ksc"})
    yield
    pos = list(DB.purchase_orders.find({"notes": {"$regex": re.escape(ALASAN)}}, {"_id": 0, "id": 1}))
    DB.wms_tasks.delete_many({"po_id": {"$in": [p["id"] for p in pos]}})
    DB.purchase_orders.delete_many({"notes": {"$regex": re.escape(ALASAN)}})
    DB.ai_action_proposals.delete_many({"reason": ALASAN})
    DB.supplier_items.delete_many({"id": f"si_agt1_{TAG}"})
    DB.products.delete_one({"id": PRD})
    DB.suppliers.delete_one({"id": SUP})


def test_AGT1_U4_dua_setujui_bersamaan_satu_po(siap):
    h = _login()
    r = requests.post(f"{BASE}/ai/tools/propose_action", headers=h, timeout=60,
                      json={"action_type": "draft_po", "items": [{"product_id": PRD, "quantity": 5}], "reason": ALASAN})
    assert r.status_code == 200, r.text
    pid = r.json()["proposal_id"]

    def setujui(_):
        return requests.post(f"{BASE}/ai/actions/{pid}/confirm", headers=h, json={"edits": None}, timeout=120)

    with ThreadPoolExecutor(2) as ex:
        hasil = [f.result() for f in [ex.submit(setujui, i) for i in range(2)]]
    kode = sorted(x.status_code for x in hasil)
    print("kode:", kode, [x.text[:160] for x in hasil])
    assert kode == [200, 409], [x.text for x in hasil]
    ok = next(x for x in hasil if x.status_code == 200).json()
    assert ok["status"] == "confirmed" and len(ok["result"]) == 1
    assert next(x for x in hasil if x.status_code == 409).json()["detail"] == "Draf ini sudah diproses"
    assert DB.purchase_orders.count_documents({"notes": {"$regex": re.escape(ALASAN)}}) == 1
    kartu = DB.ai_action_proposals.find_one({"id": pid}, {"_id": 0})
    assert kartu["status"] == "confirmed" and kartu["result"] == ok["result"]
