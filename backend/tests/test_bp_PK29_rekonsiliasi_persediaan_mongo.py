"""PK-29 U4 (+ U1/U11 cakupan) — di MongoDB ASLI (lingkungan A): nilai roll dihitung dari SEMUA roll tanpa terpotong
(GL-13) dan baris rekonsiliasi mengikuti penugasan PT pengguna.

Lapis B (`tests_mem/test_PK29_rekonsiliasi_persediaan.py::test_PK29_U4_…`) memakai tiruan kursor Motor:
`mongomock_motor` mengabaikan `to_list(n)`, jadi batas `to_list(100000)` lama tidak terlihat di database tiruan, dan
150.000 dokumen tiruan butuh ± 6 menit. Di sini 150.000 roll disisipkan sungguhan lalu dihapus lagi.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.

Persiapan (fixture): PT uji `ent_bp29_<acak>` (status aktif) tanpa jurnal; 150.000 roll `available`, sisa 10 m, biaya
1.234,56. Harapan: `subledger_value` = 150.000 × 12.345,60 = 1.851.840.000,00 (kode lama: 100.000 × 12.345,60 =
1.234.560.000), `difference` sama (tanpa jurnal), `reconciled` salah; penjelas selisih menghitung 150.000 roll.
"""
import os
import time
import uuid
from datetime import datetime, timezone

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
JUMLAH = 150_000


def _login(entity: str, email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_U4_150000_roll_tanpa_batas():
    t = uuid.uuid4().hex[:8]
    eid = f"ent_bp29_{t}"
    DB.business_entities.insert_one({"id": eid, "code": f"BP29{t[:3].upper()}", "doc_prefix": f"B29{t[:3].upper()}",
                                     "legal_name": f"PT Uji BP29 {t}", "short_name": f"Uji BP29 {t}",
                                     "name": f"PT Uji BP29 {t}", "status": "active", "is_active": True,
                                     "is_pkp": False, "created_at": _now()})
    try:
        for awal in range(0, JUMLAH, 10_000):
            DB.inventory_rolls.insert_many([
                {"id": f"roll_bp29_{t}_{i}", "roll_no": f"BP29-{t}-{i:06d}", "owner_entity_id": eid, "entity_id": eid,
                 "status": "available", "unit": "meter", "length_initial": 10.0, "length_remaining": 10.0,
                 "unit_cost": 1234.56, "base_unit_cost": 1234.56, "grade": "A",
                 "acquired": {"via": "inbound", "date": "2026-11-01"}, "created_at": _now()}
                for i in range(awal, min(awal + 10_000, JUMLAH))], ordered=False)
        h = _login(eid)
        for _ in range(8):   # cache status PT di backend (± 20 detik) belum mengenal PT baru → 403 sementara
            r = requests.get(f"{BASE}/gl/inventory-reconciliation", headers=h, timeout=300)
            if r.status_code != 403:
                break
            time.sleep(5)
        assert r.status_code == 200, r.text
        row = next(x for x in r.json()["rows"] if x["entity_id"] == eid)
        assert row["subledger_value"] == 1_851_840_000.00, row
        assert (row["gl_balance"], row["difference"], row["reconciled"]) == (0, 1_851_840_000.00, False)
        x = requests.get(f"{BASE}/gl/inventory-drift-explain", headers=h, params={"entity_id": eid}, timeout=300)
        assert x.status_code == 200, x.text
        assert x.json()["subledger_value"] == 1_851_840_000.00
        assert sum(o["rolls"] for o in x.json()["physical_by_origin"]) == JUMLAH
    finally:
        DB.inventory_rolls.delete_many({"owner_entity_id": eid, "id": {"$regex": f"^roll_bp29_{t}_"}})
        DB.business_entities.delete_one({"id": eid})
