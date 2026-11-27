"""Kas & Bank 2 bagian 2 (kas keluar manual di atas batas PT → pengajuan `cash_out_requests`) — di MongoDB ASLI.

Uji tiruan (mongomock) sudah hijau; uji ini membuktikan klaim yang sama di MongoDB asli, lewat API (backend uji sendiri,
mis. `:8032`, atas database uji `MONGO_URL`/`DB_NAME`). Pola: `test_bp_KB1_bersamaan.py`. Tidak untuk data nyata.

Pengaju = Finance (`cash.create`), penyetuju = Admin (bukan pengaju → lolos kontrol dua orang). Batas `ent_ksc` bawaan Rp 1 jt;
nominal uji Rp 5 jt (di atas batas).

Kasus:
1. DUA `approve` bersamaan satu pengajuan, 3× pengajuan segar → tepat satu 200; satu kas `ref_type=manual`,
   `ref_id` = id pengajuan; satu jurnal; pengajuan `disetujui`.
2. `approve` (Admin) × `cancel` (Finance, pengaju) bersamaan, 5× dengan jeda mulai 0–0,1 dtk di sisi approve, 0,05–0,5 dtk di sisi cancel (berganti) →
   tidak pernah campur: disetujui + satu kas, ATAU dibatalkan + nol kas.
3. DUA POST kas keluar di atas batas dengan `Idempotency-Key` sama bersamaan → tepat satu pengajuan, nol kas langsung.

Pembersihan: kas yang terbit dari uji di-void lewat API; pengajuan yang masih menunggu dibatalkan.
"""
import os
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
ENT = "ent_ksc"
NOMINAL = 5_000_000


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def finance():
    return _login("finance@kainnusantara.id")


def _isi(n=0):
    return {"entity_id": ENT, "cash_type": "kas_kecil", "direction": "out", "amount": NOMINAL + n,
            "category": "operasional", "description": f"uji KB2 bersamaan {TAG} #{n}"}


def _ajukan(h, n=0, kunci=None):
    r = requests.post(f"{BASE}/cash-transactions", headers={**h, "Idempotency-Key": kunci or f"kb2-{TAG}-{uuid.uuid4().hex}"},
                      json=_isi(n), timeout=60)
    assert r.status_code == 202, r.text
    req = r.json()["request"]
    assert req["status"] == "menunggu_persetujuan", req
    return req


def _kas(req_id):
    return list(DB.cash_transactions.find({"ref_type": "manual", "ref_id": req_id}))


def _jurnal(kas):
    return [je for k in kas for je in DB.journal_entries.find({"source_type": "cash_transaction", "source_id": k["id"]})]


def _serentak(*fns):
    gerbang = threading.Barrier(len(fns))

    def jalan(fn):
        gerbang.wait(timeout=30)
        return fn()
    with ThreadPoolExecutor(len(fns)) as ex:
        return [f.result() for f in [ex.submit(jalan, fn) for fn in fns]]


def _bersih(admin, finance, ids, kunci=()):
    for i in ids:
        d = DB.cash_out_requests.find_one({"id": i}) or {}
        if d.get("status") == "menunggu_persetujuan":
            requests.post(f"{BASE}/cash-out-requests/{i}/cancel", headers=finance, timeout=60, json={"alasan": f"bersih uji KB2 {TAG}"})
    refs = list(ids) + list(kunci)
    for k in DB.cash_transactions.find({"ref_type": "manual", "ref_id": {"$in": refs}, "status": {"$ne": "void"}}):
        requests.post(f"{BASE}/cash-transactions/{k['id']}/void", headers=admin, timeout=60, json={"reason": f"bersih uji KB2 {TAG}"})


# ── 1. dua approve bersamaan ────────────────────────────────────────────────────────────────────────────────────────
def test_KB2_dua_approve_bersamaan_satu_kas(admin, finance):
    dibuat, ringkas = [], []
    try:
        for n in range(3):
            req = _ajukan(finance, n)
            dibuat.append(req["id"])
            assert _kas(req["id"]) == []
            a1, a2 = _serentak(
                lambda: requests.post(f"{BASE}/cash-out-requests/{req['id']}/approve", headers=admin, timeout=120),
                lambda: requests.post(f"{BASE}/cash-out-requests/{req['id']}/approve", headers=admin, timeout=120))
            kode = sorted([a1.status_code, a2.status_code])
            kas = _kas(req["id"])
            doc = DB.cash_out_requests.find_one({"id": req["id"]})
            ringkas.append((n, kode, len(kas), len(_jurnal(kas)), doc["status"]))
            assert kode.count(200) == 1, (a1.text[:300], a2.text[:300])
            assert all(c == 409 for c in kode if c != 200), (a1.text[:300], a2.text[:300])
            assert len(kas) == 1, [(k["id"], k.get("status")) for k in kas]
            assert kas[0]["ref_type"] == "manual" and kas[0]["ref_id"] == req["id"] and kas[0].get("status") != "void"
            assert len(_jurnal(kas)) == 1, [j["id"] for j in _jurnal(kas)]
            assert doc["status"] == "disetujui" and doc.get("cash_id") == kas[0]["id"], doc
        print("\nKB2 dua approve (n, kode, kas, jurnal, status):", ringkas)
    finally:
        _bersih(admin, finance, dibuat)


# ── 2. approve × cancel ─────────────────────────────────────────────────────────────────────────────────────────────
def test_KB2_approve_dan_cancel_bersamaan_tidak_pernah_campur(admin, finance):
    dibuat, ringkas = [], []
    try:
        for n in range(5):
            req = _ajukan(finance, 10 + n)
            dibuat.append(req["id"])
            # approve lebih lambat dari cancel (jurnal + kas): jeda 0–0,1 dtk di sisi approve; di sisi cancel jeda lebih
            # lebar (0,05–0,5 dtk) supaya approve juga sempat menang → kedua urutan terjadi.
            tunda = random.uniform(0, 0.1) if n % 2 == 0 else random.uniform(0.05, 0.5)
            sisi = n % 2   # 0: setuju ditunda, 1: batal ditunda → kedua urutan terjadi

            def setuju(t=tunda if sisi == 0 else 0.0):
                time.sleep(t)
                return requests.post(f"{BASE}/cash-out-requests/{req['id']}/approve", headers=admin, timeout=120)

            def batal(t=tunda if sisi == 1 else 0.0):
                time.sleep(t)
                return requests.post(f"{BASE}/cash-out-requests/{req['id']}/cancel", headers=finance, timeout=120,
                                     json={"alasan": f"uji KB2 balapan {TAG}"})
            ap, bt = _serentak(setuju, batal)
            doc = DB.cash_out_requests.find_one({"id": req["id"]})
            kas = [k for k in _kas(req["id"]) if k.get("status") != "void"]
            ringkas.append((n, f"tunda {'setuju' if sisi == 0 else 'batal'} {tunda:.3f}s", ap.status_code, bt.status_code,
                            doc["status"], len(kas)))
            assert ap.status_code in (200, 409) and bt.status_code in (200, 409), (ap.text[:300], bt.text[:300])
            assert [ap.status_code, bt.status_code].count(200) == 1, (ap.text[:300], bt.text[:300])
            if doc["status"] == "disetujui":
                assert ap.status_code == 200 and bt.status_code == 409
                assert len(kas) == 1 and kas[0]["ref_id"] == req["id"] and len(_jurnal(kas)) == 1
            else:
                assert doc["status"] == "dibatalkan" and bt.status_code == 200 and ap.status_code == 409, doc["status"]
                assert len(_kas(req["id"])) == 0, "CAMPUR: dibatalkan tetapi ada kas"
        print("\nKB2 approve×cancel (n, tunda, approve, cancel, status, kas):")
        for b in ringkas:
            print("  ", b)
    finally:
        _bersih(admin, finance, dibuat)


# ── 3. dua POST berkunci sama ───────────────────────────────────────────────────────────────────────────────────────
def test_KB2_dua_kiriman_kunci_sama_satu_pengajuan(admin, finance):
    kunci = f"kb2-{TAG}-sama-{uuid.uuid4().hex}"
    try:
        r1, r2 = _serentak(
            lambda: requests.post(f"{BASE}/cash-transactions", headers={**finance, "Idempotency-Key": kunci}, json=_isi(20), timeout=120),
            lambda: requests.post(f"{BASE}/cash-transactions", headers={**finance, "Idempotency-Key": kunci}, json=_isi(20), timeout=120))
        n_req = DB.cash_out_requests.count_documents({"entity_id": ENT, "idempotency_key": kunci})
        n_kas = DB.cash_transactions.count_documents({"ref_type": "manual", "ref_id": kunci})
        n_kas_ent = DB.cash_transactions.count_documents({"entity_id": ENT, "ref_type": "manual", "ref_id": kunci})
        print("\nKB2 kunci sama:", r1.status_code, r2.status_code, "pengajuan", n_req, "kas langsung", n_kas)
        assert all(x.status_code in (202, 409) for x in (r1, r2)), (r1.text[:300], r2.text[:300])
        assert 202 in (r1.status_code, r2.status_code), (r1.text[:300], r2.text[:300])
        assert n_req == 1, n_req
        assert n_kas == 0 and n_kas_ent == 0
        ids = {x.json()["request"]["id"] for x in (r1, r2) if x.status_code == 202}
        assert len(ids) == 1, ids
    finally:
        ids = [d["id"] for d in DB.cash_out_requests.find({"idempotency_key": kunci})]
        _bersih(admin, finance, ids, [kunci])
