"""Kas & Bank 3 (isi ulang dana tetap kas kecil + opname kas) — di MongoDB ASLI.

Uji tiruan (mongomock) sudah hijau; uji ini membuktikan klaim yang sama di MongoDB asli, lewat API (backend uji sendiri,
mis. `:8033`, atas database uji `MONGO_URL`/`DB_NAME`). Pola: `test_bp_KB2_bersamaan.py`. Tidak untuk data nyata.

Fixture: rekening dibuat lewat `POST /api/bank-accounts` (Admin; langsung 200, tanpa pengajuan) — satu kas kecil BARU per
putaran (nama bertanda TAG; saldo awal Rp 500.000; dana tetap Rp 2.000.000 → usulan isi ulang Rp 1.500.000) dan satu bank
sumber bertanda TAG (saldo awal Rp 50 jt). Dana tetap diisi saat membuat rekening (bukan lewat alur ubah).

Pelaku: Finance = pembuat isi ulang / penghitung opname (`cash.create`); Admin = penyetuju (orang kedua).

Kasus:
1. DUA `POST /api/kas-kecil/dana-tetap/{id}/isi-ulang` bersamaan (kunci idempotensi berbeda), 3× rekening segar → tepat satu
   Pindah Dana bertanda `isi_ulang_kas_kecil` untuk rekening itu, nominal 1.500.000 (hitungan server); lainnya 409.
2. DUA `approve` bersamaan satu opname menunggu (selisih ≠ 0, dihitung Finance, disetujui Admin), 3× → tepat satu 200;
   satu kas penyesuaian `ref_type=cash_count` + satu jurnal; opname `disetujui`.
3. DUA `batal` (Admin) bersamaan satu opname disetujui → tepat satu 200; satu jurnal pembalik; kas `void`; opname `batal`.

Pembersihan: Pindah Dana isi ulang dibatalkan; opname menunggu ditolak, opname disetujui dibatalkan lewat API.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
ENT = "ent_ksc"
DANA_TETAP = 2_000_000
SALDO_KK = 500_000
USULAN = DANA_TETAP - SALDO_KK
FISIK = 480_000          # kurang Rp 20.000 dari buku 500.000 → selisih ≠ 0


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


def _idem(h):
    return {**h, "Idempotency-Key": f"kb3-{TAG}-{uuid.uuid4().hex}"}


def _rekening(admin, nama, **lain):
    r = requests.post(f"{BASE}/bank-accounts", headers=_idem(admin), timeout=60,
                      json={"name": f"{nama} {TAG} {uuid.uuid4().hex[:4]}", "entity_id": ENT, **lain})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _kas_kecil(admin):
    return _rekening(admin, "UjiKB3 Kas Kecil", account_type="cash", cash_type="kas_kecil", opening_balance=SALDO_KK,
                     dana_tetap=DANA_TETAP)


def _serentak(*fns):
    gerbang = threading.Barrier(len(fns))

    def jalan(fn):
        gerbang.wait(timeout=30)
        return fn()
    with ThreadPoolExecutor(len(fns)) as ex:
        return [f.result() for f in [ex.submit(jalan, fn) for fn in fns]]


def _hitung(finance, acc):
    r = requests.post(f"{BASE}/cash-counts", headers=_idem(finance), timeout=60,
                      json={"account_id": acc, "jumlah_fisik": FISIK, "catatan": f"uji KB3 bersamaan {TAG}"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "menunggu_persetujuan" and d["selisih"] == FISIK - SALDO_KK, d
    return d


def _kas(cid):
    return list(DB.cash_transactions.find({"ref_type": "cash_count", "ref_id": cid}))


def _jurnal(kas_id, source_type="cash_transaction"):
    return list(DB.journal_entries.find({"source_type": source_type, "source_id": kas_id}))


def _bersih_opname(admin, ids):
    for i in ids:
        st = (DB.cash_counts.find_one({"id": i}) or {}).get("status")
        if st == "menunggu_persetujuan":
            requests.post(f"{BASE}/cash-counts/{i}/reject", headers=_idem(admin), timeout=60, json={"alasan": f"bersih uji KB3 {TAG}"})
        elif st == "disetujui":
            requests.post(f"{BASE}/cash-counts/{i}/batal", headers=_idem(admin), timeout=60, json={"alasan": f"bersih uji KB3 {TAG}"})


# ── 1. dua isi ulang bersamaan ──────────────────────────────────────────────────────────────────────────────────────
def test_KB3_dua_isi_ulang_bersamaan_satu_pindah_dana(admin, finance):
    dibuat, ringkas = [], []
    try:
        sumber = _rekening(admin, "UjiKB3 Bank Sumber", account_type="bank", opening_balance=50_000_000)
        for n in range(3):
            kk = _kas_kecil(admin)
            url = f"{BASE}/kas-kecil/dana-tetap/{kk}/isi-ulang"
            body = {"sumber_account_id": sumber, "catatan": f"uji KB3 isi ulang {TAG} #{n}"}
            r1, r2 = _serentak(lambda: requests.post(url, headers=_idem(finance), json=body, timeout=120),
                               lambda: requests.post(url, headers=_idem(finance), json=body, timeout=120))
            docs = list(DB.fund_transfers.find({"rekening_tujuan_id": kk, "jenis": "isi_ulang_kas_kecil"}))
            dibuat += [d["id"] for d in docs]
            kode = sorted([r1.status_code, r2.status_code])
            ringkas.append((n, kode, len(docs), [d.get("nominal") for d in docs], [d.get("status") for d in docs]))
            assert kode.count(200) == 1, (r1.text[:300], r2.text[:300])
            assert all(c == 409 for c in kode if c != 200), (r1.text[:300], r2.text[:300])
            assert len(docs) == 1, [(d["id"], d.get("status")) for d in docs]
            assert docs[0]["nominal"] == USULAN and docs[0]["jenis"] == "isi_ulang_kas_kecil", docs[0]
            ok = r1 if r1.status_code == 200 else r2
            assert ok.json()["id"] == docs[0]["id"]
        print("\nKB3 dua isi ulang (n, kode, jumlah dokumen, nominal, status):", ringkas)
    finally:
        for i in dibuat:
            d = DB.fund_transfers.find_one({"id": i}) or {}
            if d.get("status") not in ("batal", "dibatalkan"):
                requests.post(f"{BASE}/fund-transfers/{i}/cancel", headers=_idem(admin), timeout=60, json={"alasan": f"bersih uji KB3 {TAG}"})


# ── 2. dua approve bersamaan ────────────────────────────────────────────────────────────────────────────────────────
def test_KB3_dua_approve_opname_bersamaan_satu_kas(admin, finance):
    dibuat, ringkas = [], []
    try:
        for n in range(3):
            d = _hitung(finance, _kas_kecil(admin))
            dibuat.append(d["id"])
            assert _kas(d["id"]) == []
            url = f"{BASE}/cash-counts/{d['id']}/approve"
            a1, a2 = _serentak(
                lambda: requests.post(url, headers=_idem(admin), json={"perlakuan": "selisih_kas"}, timeout=120),
                lambda: requests.post(url, headers=_idem(admin), json={"perlakuan": "selisih_kas"}, timeout=120))
            kode = sorted([a1.status_code, a2.status_code])
            kas = _kas(d["id"])
            jr = [j for k in kas for j in _jurnal(k["id"])]
            doc = DB.cash_counts.find_one({"id": d["id"]})
            ringkas.append((n, kode, len(kas), len(jr), doc["status"]))
            assert kode.count(200) == 1, (a1.text[:300], a2.text[:300])
            assert all(c == 409 for c in kode if c != 200), (a1.text[:300], a2.text[:300])
            assert len(kas) == 1 and kas[0].get("status") != "void", [(k["id"], k.get("status")) for k in kas]
            assert len(jr) == 1, [j["id"] for j in jr]
            assert doc["status"] == "disetujui" and doc.get("cash_id") == kas[0]["id"], doc
        print("\nKB3 dua approve opname (n, kode, kas, jurnal, status):", ringkas)
    finally:
        _bersih_opname(admin, dibuat)


# ── 3. dua batal bersamaan ──────────────────────────────────────────────────────────────────────────────────────────
def test_KB3_dua_batal_opname_bersamaan_satu_pembalik(admin, finance):
    dibuat, ringkas = [], []
    try:
        for n in range(3):
            d = _hitung(finance, _kas_kecil(admin))
            dibuat.append(d["id"])
            r = requests.post(f"{BASE}/cash-counts/{d['id']}/approve", headers=_idem(admin), json={"perlakuan": "selisih_kas"}, timeout=120)
            assert r.status_code == 200, r.text
            kas = _kas(d["id"])
            assert len(kas) == 1 and len(_jurnal(kas[0]["id"])) == 1
            url = f"{BASE}/cash-counts/{d['id']}/batal"
            b1, b2 = _serentak(
                lambda: requests.post(url, headers=_idem(admin), json={"alasan": f"uji KB3 batal ganda {TAG}"}, timeout=120),
                lambda: requests.post(url, headers=_idem(admin), json={"alasan": f"uji KB3 batal ganda {TAG}"}, timeout=120))
            kode = sorted([b1.status_code, b2.status_code])
            kas = _kas(d["id"])
            pembalik = _jurnal(kas[0]["id"], "cash_transaction_void")
            doc = DB.cash_counts.find_one({"id": d["id"]})
            ringkas.append((n, kode, len(kas), kas[0].get("status"), len(pembalik), doc["status"], doc.get("batal_gl_status")))
            assert kode.count(200) == 1, (b1.text[:300], b2.text[:300])
            assert all(c == 409 for c in kode if c != 200), (b1.text[:300], b2.text[:300])
            assert len(kas) == 1 and kas[0].get("status") == "void", kas
            assert len(pembalik) == 1, [j["id"] for j in pembalik]
            assert doc["status"] == "batal" and doc.get("batal_gl_status") == "posted", doc
        print("\nKB3 dua batal opname (n, kode, kas, status kas, pembalik, status, gl):", ringkas)
    finally:
        _bersih_opname(admin, dibuat)
