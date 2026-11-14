"""KP-T5 U12 — di MongoDB ASLI (lingkungan A): deret KP-35 tidak kembar saat dipanggil bersamaan.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`),
sesudah KP-T5 (b). Database tiruan tidak menguji balapan; butir ini hanya sah di sini (`03_LINGKUNGAN_UJI.md` §1).

1. 20 permintaan `POST /api/hr/employees` bersamaan (admin) → 20 kode karyawan berbeda dan berurutan, mulai dari kode
   `EMP-` tertinggi + 1 (dulu "baca kode terakhir + 1": beberapa permintaan mendapat kode yang sama).
2. 20 pemanggilan `makloon_order_service._next_service_bill_no` bersamaan pada MongoDB yang sama (penghitung atomik
   `number_sequences`, kunci unik `uq_entity_doctype`) → 20 nomor `VBM-` berbeda dan berurutan. Pencatatan jasa makloon
   lewat HTTP butuh order makloon lengkap per permintaan; yang diuji di sini adalah pembuat nomornya.
3. Indeks unik `number_sequences.uq_entity_doctype` dan `doc_number_formats.uq_kind_entity` terpasang.

Karyawan uji dihapus di akhir; penghitung tidak diturunkan (nomor yang sudah dipakai tidak dipakai ulang). Tidak untuk
database berisi data nyata.
"""
import asyncio
import concurrent.futures
import os
import re
import sys
import uuid
from pathlib import Path

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
N = 20


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def admin():
    if not DB.users.find_one({"email": "admin@kainnusantara.id"}):
        pytest.skip("data acuan belum dipulihkan (scripts/dev_restore_demo.sh)")
    return _login("admin@kainnusantara.id")


def _max_emp() -> int:
    n = 0
    for d in DB.hr_employees.find({"code": {"$regex": "^EMP-"}}, {"_id": 0, "code": 1}):
        m = re.search(r"(\d+)\s*$", d.get("code") or "")
        if m:
            n = max(n, int(m.group(1)))
    seq = DB.number_sequences.find_one({"entity_id": "__shared__", "doc_type": "hr_employees:code:EMP-"})
    return max(n, int((seq or {}).get("last_no") or 0))


def test_U12_dua_puluh_karyawan_bersamaan_kode_berbeda(admin):
    awal = _max_emp()
    tag = uuid.uuid4().hex[:6]
    with concurrent.futures.ThreadPoolExecutor(max_workers=N) as ex:
        futs = [ex.submit(requests.post, f"{BASE}/hr/employees", headers=admin,
                          json={"name": f"Uji KPT5 {tag} {i}"}, timeout=60) for i in range(N)]
        res = [f.result() for f in futs]
    ids = [r.json().get("id") for r in res if r.status_code == 200]
    try:
        assert all(r.status_code == 200 for r in res), [r.text for r in res if r.status_code != 200][:3]
        kode = sorted(r.json()["code"] for r in res)
        assert len(set(kode)) == N
        assert kode == [f"EMP-{n:05d}" for n in range(awal + 1, awal + N + 1)]
    finally:
        DB.hr_employees.delete_many({"id": {"$in": ids}})


def test_U12_dua_puluh_tagihan_jasa_makloon_bersamaan_nomor_berbeda():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from services.makloon_order_service import _next_service_bill_no  # noqa: E402 — butuh MONGO_URL backend

    async def _jalan():
        return await asyncio.gather(*[_next_service_bill_no(ENT) for _ in range(N)])

    nomor = asyncio.run(_jalan())
    assert len(set(nomor)) == N
    angka = sorted(int(x.split("-")[1]) for x in nomor)
    assert angka == list(range(angka[0], angka[0] + N))


def test_U12_indeks_unik_penghitung_dan_format():
    assert DB.number_sequences.index_information().get("uq_entity_doctype", {}).get("unique")
    assert DB.doc_number_formats.index_information().get("uq_kind_entity", {}).get("unique")
