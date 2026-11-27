"""Kas & Bank 1 (rekening per akun + Pindah Dana) — di MongoDB ASLI: klaim bersyarat tahan balapan sungguhan.

Uji tiruan (mongomock) sudah hijau; uji ini membuktikan klaim yang sama di MongoDB asli, lewat API (backend uji sendiri,
mis. `:8031`, atas database uji `MONGO_URL`/`DB_NAME`). Pola: `test_bp_PMT3_cocok_bersamaan.py`. Tidak untuk data nyata.

Kasus (urutan berkas = urutan jalan; tiap kasus berdiri sendiri, pindah saldo SENGAJA terakhir):
1. `Pindah Dana` dua tahap (terima besok) → `receive` (Finance) dan `cancel` (Admin) BERSAMAAN, 5 dokumen segar.
   Akhirnya tidak boleh campur: semua kas void + dokumen `batal` + transit 1-1150 dokumen netto 0, ATAU tidak ada kas void
   (dokumen `selesai`, pembatalan ditolak).
2. `Pindah Dana` dengan kontrol dua orang (`kontrol.pindah_dana.min_orang` = 2 untuk `ent_ksc`, dipulihkan di `finally`):
   Admin membuat, Finance mengirim DUA `approve` bersamaan → tepat satu himpunan kas (kirim + biaya, tanpa kembaran).
3. Pindah saldo: Admin menyiapkan, Finance mengirim DUA `setujui` bersamaan dengan sidik sama → tepat satu berhasil,
   satu jurnal `pindah_saldo_kas`, mode PT menyala sekali, saldo tiap akun rekening = buku kasnya.
   Pindah saldo hanya bisa sekali per PT: kasus ini dilewati bila `ent_ksc` sudah aktif (butuh salinan data acuan segar;
   tidak ada jalan mematikan mode).

Pembersihan: dokumen Pindah Dana yang masih hidup dibatalkan lewat API (pembalik); pengaturan kontrol dipulihkan.
"""
import datetime
import os
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
TRANSIT = "1-1150"
KUNCI_MIN = "kontrol.pindah_dana.min_orang"
HARI_INI = datetime.date.today().isoformat()
BESOK = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()


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


@pytest.fixture(scope="module")
def rekening(admin):
    r = requests.get(f"{BASE}/bank-accounts", headers=admin, params={"entity_id": ENT}, timeout=30)
    assert r.status_code == 200, r.text
    aktif = [a for a in r.json() if a.get("is_active") and a.get("entity_id") == ENT]
    besar = next(a for a in aktif if a.get("cash_type") == "kas_besar")
    kecil = next(a for a in aktif if a.get("cash_type") == "kas_kecil")
    return besar, kecil


def _buat(h, asal, tujuan, *, nominal, biaya, kirim=HARI_INI, terima=BESOK):
    r = requests.post(f"{BASE}/fund-transfers", headers={**h, "Idempotency-Key": f"kb1-{TAG}-{uuid.uuid4().hex}"},
                      timeout=60, json={"entity_id": ENT, "rekening_asal_id": asal["id"],
                                        "rekening_tujuan_id": tujuan["id"], "nominal": nominal, "biaya": biaya,
                                        "tanggal_kirim": kirim, "tanggal_terima": terima,
                                        "catatan": f"uji KB1 bersamaan {TAG}"})
    assert r.status_code == 200, r.text
    return r.json()


def _kas(doc_id):
    return list(DB.cash_transactions.find({"ref_type": "fund_transfer", "ref_id": doc_id}))


def _transit_netto(doc_id):
    """Debit − kredit akun transit 1-1150 dari semua jurnal kas dokumen (asli + pembalik)."""
    ids = set()
    for k in _kas(doc_id):
        ids.update(x for x in (k.get("journal_entry_id"), k.get("void_journal_entry_id")) if x)
    netto = 0.0
    for je in DB.journal_entries.find({"id": {"$in": sorted(ids)}}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == TRANSIT:
                netto += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(netto, 2)


def _batalkan_sisa(h, ids):
    for i in ids:
        d = DB.fund_transfers.find_one({"id": i}) or {}
        if d.get("status") != "batal" or d.get("batal_tertunda"):
            requests.post(f"{BASE}/fund-transfers/{i}/cancel", headers=h, timeout=60,
                          json={"alasan": f"bersih uji KB1 bersamaan {TAG}"})


def _serentak(*fns):
    """Jalankan semua fungsi bersamaan (gerbang awal bersama) → daftar respons berurut."""
    import threading
    gerbang = threading.Barrier(len(fns))

    def jalan(fn):
        gerbang.wait(timeout=30)
        return fn()
    with ThreadPoolExecutor(len(fns)) as ex:
        return [f.result() for f in [ex.submit(jalan, fn) for fn in fns]]


# ── 1. terima × batal ───────────────────────────────────────────────────────────────────────────────────────────────
def test_KB1_terima_dan_batal_bersamaan_tidak_pernah_campur(admin, finance, rekening):
    besar, kecil = rekening
    dibuat, ringkas = [], []
    try:
        for n in range(5):
            d = _buat(admin, besar, kecil, nominal=100_000 + n, biaya=1_000)
            dibuat.append(d["id"])
            assert d["status"] == "dalam_perjalanan", d
            assert {k["seq"] for k in _kas(d["id"])} == {"kirim", "biaya"}
            tunda = (0.0, 0.0, 0.03, 0.06, 0.1)[n]   # sebagian dokumen: terima ditunda sedikit supaya batal bisa menang

            def terima(d=d, tunda=tunda):
                time.sleep(tunda)
                return requests.post(f"{BASE}/fund-transfers/{d['id']}/receive", headers=finance, timeout=120,
                                     json={"tanggal": HARI_INI})
            rc, bt = _serentak(
                terima,
                lambda d=d: requests.post(f"{BASE}/fund-transfers/{d['id']}/cancel", headers=admin, timeout=120,
                                      json={"alasan": f"uji KB1 balapan {TAG}"}))
            doc = DB.fund_transfers.find_one({"id": d["id"]})
            kas = _kas(d["id"])
            void = [k for k in kas if k.get("status") == "void"]
            ringkas.append((n, rc.status_code, bt.status_code, doc["status"], f"{len(void)}/{len(kas)} void",
                            _transit_netto(d["id"])))
            assert all(x.status_code in (200, 409) for x in (rc, bt)), (rc.text, bt.text)
            assert rc.status_code == 200 or bt.status_code == 200, (rc.text, bt.text)
            if void:
                assert len(void) == len(kas), f"CAMPUR: {[(k['seq'], k['status']) for k in kas]}"
                assert doc["status"] == "batal", doc["status"]
                assert all(k.get("void_journal_entry_id") for k in void)
            else:
                assert doc["status"] == "selesai" and bt.status_code == 409, (doc["status"], bt.text)
                assert {k["seq"] for k in kas} == {"kirim", "biaya", "terima"}
                assert all(k.get("status") != "void" for k in kas)
            # tidak ada kas kembar per peran (kirim/biaya/terima masing-masing satu)
            assert len({k["seq"] for k in kas}) == len(kas), [(k["seq"], k["id"]) for k in kas]
            assert _transit_netto(d["id"]) == 0.0, _transit_netto(d["id"])
        print("\nKB1 terima×batal:", ringkas)
    finally:
        _batalkan_sisa(admin, dibuat)


# ── 2. dua `approve` bersamaan ──────────────────────────────────────────────────────────────────────────────────────
def test_KB1_dua_approve_bersamaan_satu_himpunan_kas(admin, finance, rekening):
    besar, kecil = rekening
    r = requests.get(f"{BASE}/config/effective", headers=admin, params={"entity_id": ENT}, timeout=30)
    assert r.status_code == 200, r.text
    lama = next((it for it in r.json()["items"] if it["key"] == KUNCI_MIN), None)
    r = requests.put(f"{BASE}/config/values", headers=admin, timeout=30, json={"items": [{
        "key": KUNCI_MIN, "value": "2", "scope_type": "entity", "scope_id": ENT,
        "reason": f"uji KB1 bersamaan {TAG}: Pindah Dana KSC harus dua orang"}]})
    assert r.status_code == 200, r.text
    dibuat = []
    try:
        d = _buat(admin, besar, kecil, nominal=250_000, biaya=2_000, terima=HARI_INI)
        dibuat.append(d["id"])
        assert d["status"] == "menunggu_persetujuan", d
        assert _kas(d["id"]) == []
        a1, a2 = _serentak(
            lambda: requests.post(f"{BASE}/fund-transfers/{d['id']}/approve", headers=finance, timeout=120),
            lambda: requests.post(f"{BASE}/fund-transfers/{d['id']}/approve", headers=finance, timeout=120))
        kode = sorted([a1.status_code, a2.status_code])
        print("\nKB1 dua approve:", kode, [x.text[:160] for x in (a1, a2) if x.status_code != 200])
        assert kode[0] == 200, (a1.text, a2.text)          # sedikitnya satu berhasil
        assert all(c in (200, 409) for c in kode), (a1.text, a2.text)
        kas = _kas(d["id"])
        seq = sorted(k["seq"] for k in kas)
        assert seq == ["biaya", "kirim", "terima"] or seq == ["biaya", "kirim"], seq   # satu himpunan, tanpa kembaran
        assert len(seq) == len(set(seq))
        assert all(k.get("status") != "void" for k in kas)
        assert DB.cash_transactions.count_documents({"ref_type": "fund_transfer", "ref_id": d["id"], "seq": "kirim"}) == 1
        doc = DB.fund_transfers.find_one({"id": d["id"]})
        assert doc["status"] in ("dalam_perjalanan", "selesai") and doc.get("disetujui_oleh"), doc["status"]
        assert sum(1 for j in doc.get("jejak") or [] if j.get("aksi") == "setujui") == 1, doc.get("jejak")
        # satu jurnal per kas (tidak ada kas yang terjurnal dua kali)
        for k in kas:
            assert DB.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": k["id"]}) == 1, k["id"]
        assert _transit_netto(d["id"]) in (0.0, round(float(d["nominal"]), 2))   # tahap kirim saja → transit berisi nominal
    finally:
        _batalkan_sisa(admin, dibuat)
        if lama is not None and lama.get("source_layer") in ("entity", "legacy_entity"):
            requests.put(f"{BASE}/config/values", headers=admin, timeout=30, json={"items": [{
                "key": KUNCI_MIN, "value": lama.get("value"), "scope_type": "entity", "scope_id": ENT,
                "reason": f"pulihkan sesudah uji KB1 {TAG}"}]})
        else:
            requests.post(f"{BASE}/config/values/reset", headers=admin, timeout=30, json={
                "key": KUNCI_MIN, "scope_type": "entity", "scope_id": ENT, "reason": f"pulihkan sesudah uji KB1 {TAG}"})


# ── 3. dua `setujui` pindah saldo bersamaan (terakhir: menyalakan PT) ───────────────────────────────────────────────
def test_KB1_dua_setujui_pindah_saldo_bersamaan_satu_jurnal(admin, finance):
    pv = requests.get(f"{BASE}/kas-per-rekening/{ENT}/pratinjau", headers=admin, timeout=60).json()
    if pv.get("aktif"):
        pytest.skip("ent_ksc sudah memakai akun per rekening; pindah saldo hanya sekali per PT (butuh data acuan segar)")
    assert not pv.get("posting_gagal"), pv.get("posting_gagal_rincian")
    r = requests.post(f"{BASE}/kas-per-rekening/{ENT}/siapkan", headers=admin, timeout=120, json={"pilihan_akun": {}})
    assert r.status_code == 200, r.text
    us = r.json()
    assert us["status"] == "menunggu", us
    sidik = requests.get(f"{BASE}/kas-per-rekening/{ENT}/pratinjau", headers=admin, timeout=60).json()["sidik"]
    badan = {"sidik": sidik, "selisih_diperiksa": True}
    s1, s2 = _serentak(
        lambda: requests.post(f"{BASE}/kas-per-rekening/usulan/{us['id']}/setujui", headers=finance, timeout=180, json=badan),
        lambda: requests.post(f"{BASE}/kas-per-rekening/usulan/{us['id']}/setujui", headers=finance, timeout=180, json=badan))
    print("\nKB1 dua setujui:", s1.status_code, s2.status_code, [x.text[:200] for x in (s1, s2) if x.status_code != 200])
    assert sorted([s1.status_code, s2.status_code]) == [200, 409], (s1.text, s2.text)
    kalah = s1 if s1.status_code == 409 else s2
    assert isinstance(kalah.json().get("detail"), str) and kalah.json()["detail"], kalah.text
    # tepat satu jurnal pindah saldo, usulan disetujui sekali
    je = list(DB.journal_entries.find({"source_type": "pindah_saldo_kas", "entity_id": ENT}))
    assert len(je) == 1 and je[0].get("status") == "posted", [(j["id"], j.get("status")) for j in je]
    assert je[0]["source_id"] == us["id"]
    assert DB.cash_account_cutovers.count_documents({"entity_id": ENT, "status": "disetujui"}) == 1 \
        if "cash_account_cutovers" in DB.list_collection_names() else True
    # mode PT menyala sekali: satu kunci ent_ksc di penanda (kembaran digabung oleh pembaca, tapi tidak boleh ada)
    penanda = [d for d in DB.system_settings.find({"scope": "__kas_per_rekening__"}) if isinstance(d.get(ENT), dict)]
    assert len(penanda) == 1 and penanda[0][ENT].get("sejak"), penanda
    # saldo tiap akun rekening = buku kasnya
    akun = requests.get(f"{BASE}/bank-accounts", headers=admin, params={"entity_id": ENT}, timeout=30).json()
    diperiksa = 0
    for a in akun:
        if a.get("entity_id") != ENT or not a.get("gl_account_code"):
            continue
        buku = requests.get(f"{BASE}/bank-accounts/{a['id']}/ledger", headers=admin, timeout=60).json()["balance"]
        gl = requests.get(f"{BASE}/gl/accounts/{a['gl_account_code']}/ledger", headers=admin,
                          params={"entity_id": ENT}, timeout=60).json()["balance"]
        print(f"KB1 {a['name']}: akun {a['gl_account_code']} {gl} vs buku kas {buku}")
        assert abs(float(gl) - float(buku)) < 0.005, (a["name"], gl, buku)
        diperiksa += 1
    assert diperiksa >= 2
    # sub-akun dipakai sekali: tiap rekening punya kode akun unik
    kode = [a["gl_account_code"] for a in akun if a.get("entity_id") == ENT and a.get("gl_account_code")]
    assert len(kode) == len(set(kode)), kode
