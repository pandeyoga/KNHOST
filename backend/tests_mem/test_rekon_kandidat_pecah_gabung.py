"""Rekonsiliasi Bank — kandidat PECAH (1:N) dan GABUNG (N:1), 18 Nov 2026 (uji rekonsiliasi R4/R5).

Dulu `candidates` hanya melayakkan transaksi bernominal ≈ mutasi (selisih ≤ 1 %), sehingga modal "Pecah ke beberapa
transaksi" dan "Gabung ke 1 transaksi" kosong begitu nominalnya berbeda — padahal itulah kasusnya (satu transfer untuk
dua kwitansi; dua transfer untuk satu kwitansi). Kini `mode=split` menawarkan transaksi yang bisa menjadi BAGIAN transfer
(+ `combos` = kombinasi yang pas menutupnya) dan `mode=group&total=` menawarkan transaksi yang menampung Σ mutasi terpilih.

Persiapan (disisip langsung): rekening `ba_rkp` (`ent_ksc`), kas masuk KA 2.262.062 + KB 1.460.200 (pasangan pecah untuk
L4 3.722.262), KC 2.971.062 (bisa bagian, bukan pasangannya), KD 5.000.000 (lebih besar dari transfer), KE keluar,
KH di luar jendela tanggal, KF 2.615.062 (pas untuk gabung L5a 1.569.000 + L5b 1.046.062), KG 3.000.000 (menampung).
Berurutan: K3 menautkan KA+KB, K5 menautkan KF.
"""
from __future__ import annotations

import pytest

from services import bank_recon_service as svc
from services import gl_service as gl

E1 = "ent_ksc"
R1 = "ba_rkp"
BASE = "/api/bank-reconciliation"
HARI = "2026-11-18"
TOKO = "Toko Kain Maju Rkp"
KA, KB, KC, KD, KE, KF, KG, KH = (f"kas_rkp_{x}" for x in "abcdefgh")
L4, L5A, L5B = "stl_rkp_l4", "stl_rkp_l5a", "stl_rkp_l5b"


def _kas(tid: str, nominal: float, arah: str = "in", tgl: str = HARI) -> dict:
    return {"id": tid, "number": f"CASH-RKP-{tid[-1].upper()}", "cash_type": "bank", "direction": arah,
            "amount": float(nominal), "category": "penagihan", "description": f"Penerimaan — {TOKO}",
            "counterparty_name": TOKO, "entity_id": E1, "account_id": R1, "ref_type": "", "ref_id": "",
            "txn_date": tgl, "status": "posted", "reconciled": False, "reconciled_amount": 0.0, "created_by": "uji",
            "created_at": gl.now_iso(), "updated_at": gl.now_iso()}


def _baris(lid: str, nominal: float, ket: str) -> dict:
    return {"id": lid, "bank_account_id": R1, "entity_id": E1, "stmt_date": HARI, "amount": float(nominal),
            "direction": "in", "description": ket, "counterparty": "", "desc_key": "", "ref": "", "external_id": lid,
            "balance": 0.0, "status": "unmatched", "match_kind": "", "matched_txn_id": "", "matched_txn_ids": [],
            "allocations": [], "score": 0, "score_explain": [], "suggestions": [], "match_type": "", "matched_at": "",
            "matched_by": "", "holding": {}, "holding_allocated": [], "holding_remaining": 0.0,
            "import_batch": "rkp", "format_id": "", "created_at": gl.now_iso(), "updated_at": gl.now_iso()}


@pytest.fixture(scope="module")
async def dasar(aplikasi, db):
    await db.bank_accounts.insert_one({"id": R1, "name": "BCA RKP", "account_type": "bank", "cash_type": "bank",
                                       "bank_name": "BCA", "entity_id": E1, "is_active": True, "status": "active",
                                       "opening_balance": 0})
    await db.cash_transactions.insert_many([
        _kas(KA, 2_262_062), _kas(KB, 1_460_200), _kas(KC, 2_971_062), _kas(KD, 5_000_000), _kas(KE, 1_000_000, "out"),
        _kas(KF, 2_615_062), _kas(KG, 3_000_000), _kas(KH, 1_000_000, tgl="2026-11-01")])
    await db.bank_statement_lines.insert_many([
        _baris(L4, 3_722_262, "TRSF E-BANKING CR TOKO KAIN MAJU RKP DUA NOTA"),
        _baris(L5A, 1_569_000, "TRSF E-BANKING CR TOKO KAIN MAJU RKP TAHAP SATU"),
        _baris(L5B, 1_046_062, "TRSF E-BANKING CR TOKO KAIN MAJU RKP TAHAP DUA")])


async def _kandidat(klien, h, lid, **params):
    r = await klien.get(f"{BASE}/lines/{lid}/candidates", headers=h, params={"limit": 25, **params})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.anyio
async def test_K1_mode_satu_tanpa_kandidat_bila_nominal_beda(dasar, klien, kepala_admin):
    d = await _kandidat(klien, kepala_admin, L4)
    assert d["mode"] == "single" and d["candidates"] == [] and d["combos"] == [], d


@pytest.mark.anyio
async def test_K2_mode_pecah_menawarkan_bagian_dan_kombinasi_pas(dasar, klien, kepala_admin):
    d = await _kandidat(klien, kepala_admin, L4, mode="split")
    ids = [c["id"] for c in d["candidates"]]
    # Bisa menjadi bagian: sisa ≤ 3.722.262, arah masuk, dalam jendela tanggal. KD (lebih besar), KE (keluar), KH (17 hari)
    # tidak layak. KF/KG (≤ transfer) tetap layak sebagai bagian. (Kas data dasar PT tanpa rekening bisa ikut ditawarkan
    # — `_book_query` — jadi diperiksa sebagai himpunan bagian.)
    assert {KA, KB, KC, KF, KG} <= set(ids) and not {KD, KE, KH} & set(ids), ids
    assert set(ids[:2]) == {KA, KB}, ids            # anggota kombinasi pas naik ke atas
    top = d["candidates"][0]
    assert top["explain"][0]["label"].startswith("Bersama CASH-RKP-") and top["explain"][0]["points"] == 40, top
    assert d["candidates"][2]["explain"][0]["label"].startswith("Bisa menjadi bagian transfer ini"), d["candidates"][2]
    assert d["candidates"][2]["explain"][0]["points"] == 20
    assert d["combos"][0]["total"] == 3_722_262 and set(d["combos"][0]["txn_ids"]) == {KA, KB}, d["combos"]


@pytest.mark.anyio
async def test_K3_pecah_lewat_kombinasi_tersimpan(dasar, klien, db, kepala_admin):
    d = await _kandidat(klien, kepala_admin, L4, mode="split")
    c = d["combos"][0]
    r = await klien.post(f"{BASE}/lines/{L4}/match-split", headers=kepala_admin,
                         json={"allocations": [{"txn_id": t, "amount": a} for t, a in zip(c["txn_ids"], c["amounts"])]})
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["match_kind"], r.json()["allocated_total"]) == ("matched", "1:N", 3_722_262)
    for t in (KA, KB):
        k = await db.cash_transactions.find_one({"id": t}, {"_id": 0})
        assert k["reconciled_amount"] == k["amount"] and k["reconciled"] is True


@pytest.mark.anyio
async def test_K4_mode_gabung_menilai_terhadap_total_terpilih(dasar, klien, kepala_admin):
    d = await _kandidat(klien, kepala_admin, L5A, mode="group", total=2_615_062)
    ids = [c["id"] for c in d["candidates"]]
    # Menampung 2.615.062: KF (pas), KG, KC, KD. KA/KB sudah habis (K3) atau terlalu kecil, KE keluar, KH di luar jendela.
    assert {KF, KG, KC, KD} <= set(ids) and not {KA, KB, KE, KH} & set(ids) and ids[0] == KF, ids
    assert d["candidates"][0]["explain"][0]["label"].startswith("Sisa transaksi pas sama dengan total mutasi terpilih")
    assert d["candidates"][0]["score"] > d["candidates"][1]["score"]
    assert "menampung total mutasi terpilih" in d["candidates"][1]["explain"][0]["label"]
    # Tanpa `total` → dinilai terhadap nominal baris itu sendiri (semua transaksi ≥ 1.569.000 menampung).
    d = await _kandidat(klien, kepala_admin, L5A, mode="group")
    assert KF in [c["id"] for c in d["candidates"]]


@pytest.mark.anyio
async def test_K5_gabung_ke_transaksi_pas(dasar, klien, db, kepala_admin):
    r = await klien.post(f"{BASE}/match-group", headers=kepala_admin, json={"line_ids": [L5A, L5B], "txn_id": KF})
    assert r.status_code == 200, r.text
    assert (r.json()["lines"], r.json()["allocated_total"], r.json()["match_kind"]) == (2, 2_615_062, "N:1")
    kf = await db.cash_transactions.find_one({"id": KF}, {"_id": 0})
    assert kf["reconciled_amount"] == 2_615_062 and kf["reconciled"] is True


@pytest.mark.anyio
async def test_K6_mode_tak_dikenal_ditolak(dasar, klien, kepala_admin):
    r = await klien.get(f"{BASE}/lines/{L4}/candidates", headers=kepala_admin, params={"mode": "acak"})
    assert r.status_code == 422, r.text


def _r(tid: str, sisa: float, skor: float = 50) -> dict:
    return {"id": tid, "number": tid, "outstanding": sisa, "score": skor}


def test_K7_kombinasi_pasangan_sebelum_tiga_dan_toleransi():
    rows = [_r("a", 100), _r("b", 200), _r("c", 300), _r("d", 300, 70), _r("e", 1_000)]
    found = svc._combos(rows, 600, 0)
    # c+d (pasangan) lebih dulu dari a+b+c / a+b+d (tiga-serangkai); e lebih besar dari target.
    assert [sorted(r["id"] for r in c) for c in found] == [["c", "d"], ["a", "b", "d"], ["a", "b", "c"]], found
    assert svc._combos([_r("a", 299.9), _r("b", 300)], 600, 0) == []
    assert len(svc._combos([_r("a", 299.5), _r("b", 300)], 600, 1)) == 1        # dalam toleransi Rp 1
    assert svc._combos([], 600, 0) == []
