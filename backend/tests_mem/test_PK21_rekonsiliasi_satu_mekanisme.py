"""PK-21 — rekonsiliasi bank satu mekanisme: cocok dan lepas-cocok bersyarat, tanda manual dihapus
(docs/blueprint/unit/PK-21.md, uji penerimaan U1–U11; U12–U13 di lapis A, U14 uji layar).

Persiapan bersama (FIXTURE, disisip langsung): rekening R1 `ba_pk21` milik `ent_ksc`; kas masuk K1 Rp 1.000.000 dan
K2 Rp 600.000 di R1; mutasi bank masuk M1 Rp 1.000.000, M2 Rp 400.000, M3 Rp 200.000. Pencocokan, pelepasan, biaya bank,
dan titipan dijalankan lewat API (ALUR). Admin, `X-Entity-Id: ent_ksc`. Tes dalam modul ini berurutan (U2 lanjutan U1, …).

Tambahan di luar tabel (penyimpangan yang dicatat di laporan): U3b — pelepasan dari salinan basi (tiruan dua permintaan
bersamaan di lapis B); X1–X3 — pembaca `reconciled` diturunkan dari angka (tanda manual lama tampil "belum"), batal kas
yang dulu ditandai manual tidak buntu, dan INV-BNK-02 melaporkan tanda manual lama sebagai PERINGATAN.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

from services import bank_recon_service as svc
from services import gl_service as gl

pytestmark = pytest.mark.anyio
E1 = "ent_ksc"
R1 = "ba_pk21"
BASE = "/api/bank-reconciliation/lines"
K1, K2, K3 = "kas_pk21_k1", "kas_pk21_k2", "kas_pk21_k3"
M1, M2, M3, M4, M5, M6, M7 = (f"stl_pk21_m{i}" for i in range(1, 8))
PESAN_410 = ("Tanda rekonsiliasi manual sudah tidak dipakai. Cocokkan transaksi dengan mutasi bank di "
             "Keuangan › Rekonsiliasi Bank.")
PESAN_409 = "Mutasi bank ini baru saja dilepas atau diubah proses lain. Muat ulang."


def _kas(tid: str, nomor: str, nominal: float, arah: str = "in") -> dict:
    return {"id": tid, "number": nomor, "cash_type": "kas_besar", "direction": arah, "amount": float(nominal),
            "category": "penerimaan uji", "description": f"kas uji PK-21 {nomor}", "entity_id": E1,
            "account_id": R1, "ref_type": "", "ref_id": "", "txn_date": "2026-11-05", "status": "posted",
            "reconciled": False, "reconciled_amount": 0.0, "created_by": "uji", "created_at": gl.now_iso(),
            "updated_at": gl.now_iso()}


def _baris_doc(lid: str, nominal: float, arah: str = "in") -> dict:
    return {"id": lid, "bank_account_id": R1, "entity_id": E1, "stmt_date": "2026-11-05", "amount": float(nominal),
            "direction": arah, "description": f"mutasi uji PK-21 {lid}", "counterparty": "", "desc_key": "",
            "ref": "", "external_id": lid, "balance": 0.0, "status": "unmatched", "match_kind": "",
            "matched_txn_id": "", "matched_txn_ids": [], "allocations": [], "score": 0, "score_explain": [],
            "suggestions": [], "match_type": "", "matched_at": "", "matched_by": "", "holding": {},
            "holding_allocated": [], "holding_remaining": 0.0, "import_batch": "pk21", "format_id": "",
            "created_at": gl.now_iso(), "updated_at": gl.now_iso()}


@pytest.fixture(scope="module", autouse=True)
async def dasar(aplikasi, db):
    await db.bank_accounts.insert_one({"id": R1, "name": "BCA PK21", "account_type": "bank", "cash_type": "bank",
                                       "bank_name": "BCA", "entity_id": E1, "is_active": True, "status": "active",
                                       "opening_balance": 0})
    await db.cash_transactions.insert_many([_kas(K1, "CASH-PK21-K1", 1_000_000), _kas(K2, "CASH-PK21-K2", 600_000),
                                            _kas(K3, "CASH-PK21-K3", 500_000)])
    await db.bank_statement_lines.insert_many([
        _baris_doc(M1, 1_000_000), _baris_doc(M2, 400_000), _baris_doc(M3, 200_000), _baris_doc(M4, 6_500, "out"),
        _baris_doc(M5, 750_000), _baris_doc(M6, 300_000), _baris_doc(M7, 200_000)])


async def _t(db, tid):
    return await db.cash_transactions.find_one({"id": tid}, {"_id": 0})


async def _l(db, lid):
    return await db.bank_statement_lines.find_one({"id": lid}, {"_id": 0})


async def _cocok(klien, h, lid, tid):
    r = await klien.post(f"{BASE}/{lid}/match", headers=h, json={"txn_id": tid})
    assert r.status_code == 200, r.text
    return r.json()


async def _lepas(klien, h, lid):
    return await klien.post(f"{BASE}/{lid}/unmatch", headers=h, json={})


async def test_PK21_U1_cocok_satu_satu(klien, db, kepala_admin):
    # M1 1.000.000 → K1 1.000.000: reconciled_amount 0 + 1.000.000 = 1.000.000 ≥ 1.000.000 − 0,01 → penuh
    await _cocok(klien, kepala_admin, M1, K1)
    k1 = await _t(db, K1)
    assert k1["reconciled_amount"] == 1_000_000 and k1["reconciled"] is True and k1["matched_line_ids"] == [M1]


async def test_PK21_U2_lepas(klien, db, kepala_admin):
    r = await _lepas(klien, kepala_admin, M1)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "unmatched"          # isi jawaban tetap: baris mutasi terbaru
    k1 = await _t(db, K1)
    # 1.000.000 − 1.000.000 = 0 → tidak penuh
    assert k1["reconciled_amount"] == 0 and k1["reconciled"] is False and k1["matched_line_ids"] == []
    m1 = await _l(db, M1)
    assert m1["status"] == "unmatched" and m1["allocations"] == [] and "match_lock" not in m1


async def test_PK21_U3_lepas_kedua_ditolak(klien, db, kepala_admin, monkeypatch):
    m1_basi = {**(await _l(db, M1)), "status": "matched", "allocations": [{"txn_id": K1, "amount": 1_000_000}],
               "match_type": "manual"}
    r = await _lepas(klien, kepala_admin, M1)
    assert r.status_code in (400, 409), r.text
    assert (await _t(db, K1))["reconciled_amount"] == 0
    # Tiruan dua permintaan bersamaan (lapis B): permintaan kedua membaca baris SEBELUM permintaan pertama selesai —
    # salinannya masih `matched`. Penjaga harus mengklaim baris, bukan percaya salinan.
    asli = svc._line

    async def _salinan_basi(line_id, entity_ids):
        if line_id == M1:
            await asli(line_id, entity_ids)      # penjaga entitas tetap dijalankan
            return dict(m1_basi)
        return await asli(line_id, entity_ids)
    monkeypatch.setattr(svc, "_line", _salinan_basi)
    r = await _lepas(klien, kepala_admin, M1)
    assert r.status_code == 409 and PESAN_409 in r.text, r.text
    k1 = await _t(db, K1)
    assert k1["reconciled_amount"] == 0 and k1["reconciled"] is False


async def test_PK21_U3b_salinan_basi_tidak_mengurangi_dua_kali(klien, db, kepala_admin, monkeypatch):
    # K3 500.000 ← M6 300.000 + M7 200.000 = 500.000 (penuh). Lepas M7 → 500.000 − 200.000 = 300.000.
    # Permintaan kedua dengan salinan M7 yang masih `matched` dulu mengurangi lagi: 300.000 − 200.000 = 100.000
    # padahal M6 masih tercocok 300.000. Harus 409 dan K3 tetap 300.000.
    await _cocok(klien, kepala_admin, M6, K3)
    await _cocok(klien, kepala_admin, M7, K3)
    assert (await _t(db, K3))["reconciled_amount"] == 500_000
    m7_basi = await _l(db, M7)
    r = await _lepas(klien, kepala_admin, M7)
    assert r.status_code == 200, r.text
    asli = svc._line

    async def _salinan_basi(line_id, entity_ids):
        if line_id == M7:
            await asli(line_id, entity_ids)
            return dict(m7_basi)
        return await asli(line_id, entity_ids)
    monkeypatch.setattr(svc, "_line", _salinan_basi)
    r = await _lepas(klien, kepala_admin, M7)
    assert r.status_code == 409, r.text
    k3 = await _t(db, K3)
    assert k3["reconciled_amount"] == 300_000 and k3["matched_line_ids"] == [M6] and k3["reconciled"] is False
    assert (await _l(db, M6))["status"] == "matched"


async def test_PK21_U4_gabung_lalu_lepas_sebagian(klien, db, kepala_admin):
    r = await klien.post("/api/bank-reconciliation/match-group", headers=kepala_admin,
                         json={"line_ids": [M2, M3], "txn_id": K2})
    assert r.status_code == 200, r.text
    k2 = await _t(db, K2)
    # 400.000 + 200.000 = 600.000 ≥ 600.000 − 0,01 → penuh
    assert k2["reconciled_amount"] == 600_000 and k2["reconciled"] is True
    assert sorted(k2["matched_line_ids"]) == sorted([M2, M3])
    r = await _lepas(klien, kepala_admin, M3)
    assert r.status_code == 200, r.text
    k2 = await _t(db, K2)
    # 600.000 − 200.000 = 400.000 < 600.000 − 0,01 → tidak penuh
    assert k2["reconciled_amount"] == 400_000 and k2["reconciled"] is False and k2["matched_line_ids"] == [M2]
    assert k2.get("reconciled_at", "") == ""


async def test_PK21_U5_bangun_ulang_tanpa_perubahan(db):
    hasil = await svc.rebuild_reconciled(K2)
    assert hasil["txn_id"] == K2 and hasil["changed"] is False
    assert hasil["after"]["reconciled_amount"] == 400_000 and hasil["after"]["reconciled"] is False
    assert hasil["after"]["matched_line_ids"] == [M2]


async def test_PK21_U6_bangun_ulang_memperbaiki_angka_rusak(db):
    await db.cash_transactions.update_one({"id": K1}, {"$set": {"reconciled_amount": 999}})   # FIXTURE rusak
    assert (await _l(db, M1))["status"] == "unmatched"
    hasil = await svc.rebuild_reconciled(K1)
    assert hasil["changed"] is True and hasil["before"]["reconciled_amount"] == 999
    assert hasil["after"]["reconciled_amount"] == 0 and hasil["after"]["reconciled"] is False
    k1 = await _t(db, K1)
    assert k1["reconciled_amount"] == 0 and k1["reconciled"] is False and k1["matched_line_ids"] == []


async def test_PK21_U7_tanda_manual_410(klien, db, kepala_admin):
    sebelum = await _t(db, K1)
    r = await klien.post(f"/api/cash-transactions/{K1}/reconcile", headers=kepala_admin, json={"reconciled": True})
    assert r.status_code == 410, r.text
    assert r.json()["detail"] == PESAN_410
    assert await _t(db, K1) == sebelum


async def test_PK21_U8_tanpa_izin_403(klien, db, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"cash": ["view"]}, label="Kas Lihat PK21")
    h = await sesi(await akun(rid))
    sebelum = await _t(db, K1)
    r = await klien.post(f"/api/cash-transactions/{K1}/reconcile", headers=h, json={"reconciled": True})
    assert r.status_code == 403, r.text
    assert await _t(db, K1) == sebelum


async def _pembalik(db, tid) -> int:
    return await db.journal_entries.count_documents({"source_type": "cash_transaction_reversal", "source_id": tid})


async def _saldo(db, akun) -> float:
    d = k = 0.0
    async for je in db.journal_entries.find({"entity_id": E1, "status": {"$ne": "void"}, "lines.account_code": akun}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == akun:
                d += float(ln.get("debit") or 0)
                k += float(ln.get("credit") or 0)
    return round(d - k, 2)


async def test_PK21_U9_lepas_biaya_bank(klien, db, kepala_admin):
    akun_biaya = (await svc.load_cfg(E1))["charge_acc"]
    b0 = await _saldo(db, akun_biaya)
    r = await klien.post(f"{BASE}/{M4}/book-charge", headers=kepala_admin, json={"kind": "charge"})
    assert r.status_code == 200, r.text
    c4 = (await _l(db, M4))["charge"]["cash_txn_id"]
    assert (await _t(db, c4))["reconciled_amount"] == 6_500
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": c4}, {"_id": 0})
    print("PK21-U9 jurnal biaya:", [(x["account_code"], x["debit"], x["credit"]) for x in je["lines"]])
    assert await _saldo(db, akun_biaya) - b0 == 6_500          # Dr beban adm bank 6.500
    r = await _lepas(klien, kepala_admin, M4)
    assert r.status_code == 200, r.text
    kas = await _t(db, c4)
    assert kas["status"] == "void" and kas["reconciled_amount"] == 0
    assert await _pembalik(db, c4) == 1
    rev = await db.journal_entries.find_one({"source_type": "cash_transaction_reversal", "source_id": c4}, {"_id": 0})
    print("PK21-U9 jurnal pembalik:", [(x["account_code"], x["debit"], x["credit"]) for x in rev["lines"]])
    assert await _saldo(db, akun_biaya) - b0 == 0              # 6.500 − 6.500 = 0 (Cr beban pada pembalik)
    m4 = await _l(db, M4)
    assert m4["status"] == "unmatched" and not m4.get("charge") and "match_lock" not in m4
    r = await _lepas(klien, kepala_admin, M4)
    assert r.status_code in (400, 409), r.text
    assert await _pembalik(db, c4) == 1


async def test_PK21_U9b_pembalik_gagal_baris_tetap_tercocok(klien, db, kepala_admin, monkeypatch):
    # Spesifikasi: bila pembalik biaya bank gagal, kunci dicabut dan baris tetap `matched` (angka kas tidak disentuh).
    r = await klien.post(f"{BASE}/{M4}/book-charge", headers=kepala_admin, json={"kind": "charge"})
    assert r.status_code == 200, r.text
    c4b = (await _l(db, M4))["charge"]["cash_txn_id"]

    async def _gagal(*a, **kw):
        raise RuntimeError("uji: pembalik gagal")
    monkeypatch.setattr(gl, "reverse_document", _gagal)
    r = await _lepas(klien, kepala_admin, M4)
    assert r.status_code >= 400, r.text
    m4 = await _l(db, M4)
    assert m4["status"] == "matched" and "match_lock" not in m4
    assert (await _t(db, c4b))["reconciled_amount"] == 6_500
    monkeypatch.undo()
    r = await _lepas(klien, kepala_admin, M4)
    assert r.status_code == 200, r.text
    assert await _pembalik(db, c4b) == 1


async def test_PK21_U10_titipan(klien, db, kepala_admin):
    r = await klien.post(f"{BASE}/{M5}/holding", headers=kepala_admin, json={"note": "uji PK-21"})
    assert r.status_code == 200, r.text
    h5 = r.json()["holding"]["cash_txn_id"]
    kas = await _t(db, h5)
    assert kas["reconciled_amount"] == 750_000 and kas["reconciled"] is True
    hasil = await svc.rebuild_reconciled(h5)
    assert hasil["changed"] is False and hasil["after"]["reconciled_amount"] == 750_000


def _vdi():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("verify_data_integrity")


async def _inv_bnk(db, capsys) -> str:
    await _vdi().layer_bank_invariants(db)
    return re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)


async def test_PK21_U11_invarian(db, capsys):
    keluar = await _inv_bnk(db, capsys)
    assert re.search(r"\[PASS\][^\n]*INV-BNK-02", keluar), keluar[-2000:]
    await db.cash_transactions.update_one({"id": K2}, {"$set": {"reconciled": True}})   # FIXTURE: tanda saja
    try:
        keluar = await _inv_bnk(db, capsys)
        baris = [x for x in keluar.splitlines() if "INV-BNK-02" in x]
        assert baris and "[FAIL]" in baris[0] and "CASH-PK21-K2" in baris[0], keluar[-2000:]
    finally:
        await db.cash_transactions.update_one({"id": K2}, {"$set": {"reconciled": False}})


# ── Tambahan (penyimpangan yang dicatat di laporan) ─────────────────────────────────────────────────────────────
KL = "kas_pk21_lama"


async def test_PK21_X1_pembaca_menurunkan_dari_angka(klien, db, kepala_admin):
    # Tanda manual LAMA: `reconciled: true` tanpa pencocokan (reconciled_amount 0). FIXTURE.
    await db.cash_transactions.insert_one({**_kas(KL, "CASH-PK21-LAMA", 300_000), "reconciled": True,
                                           "reconciled_at": "2026-10-01T00:00:00+00:00"})
    r = await klien.get(f"/api/bank-accounts/{R1}/ledger", headers=kepala_admin)
    assert r.status_code == 200, r.text
    led = r.json()
    rows = {t["id"]: t for t in led["transactions"]}
    assert rows[KL]["reconciled"] is False                 # tampil "Belum"
    assert rows[K2]["reconciled"] is False and rows[K2]["reconciled_amount"] == 400_000   # "Sebagian Rp 400.000"
    terekon = [t for t in led["transactions"] if t["reconciled"]]
    # Hanya kas titipan H5 750.000 yang penuh; K1 0, K2 400.000/600.000, K3 300.000/500.000, KL tanda lama → bukan.
    # Saldo terekonsiliasi = saldo awal 0 + 750.000 = 750.000 (dulu 750.000 + 300.000 tanda manual = 1.050.000).
    assert [t["amount"] for t in terekon] == [750_000]
    assert led["reconciled_balance"] == 750_000
    assert led["unreconciled_count"] == led["txn_count"] - 1
    r = await klien.get("/api/bank-accounts", headers=kepala_admin)
    acc = [a for a in r.json() if a["id"] == R1][0]
    assert acc["reconciled_balance"] == 750_000 and acc["unreconciled_count"] == acc["txn_count"] - 1


async def test_PK21_X2_invarian_tanda_manual_lama_peringatan(db, capsys):
    keluar = await _inv_bnk(db, capsys)
    baris = [x for x in keluar.splitlines() if "INV-BNK-02" in x]
    assert baris and "[PASS]" in baris[0], keluar[-2000:]
    assert any("[WARN]" in x and "1 transaksi kas" in x and "CASH-PK21-LAMA" in x for x in baris), keluar[-2000:]


async def test_PK21_X3_batal_kas_bertanda_manual_tidak_buntu(klien, db, kepala_admin):
    # Dulu penolak batal kas membaca `reconciled` → "sudah dicocokkan, lepaskan dulu", padahal tanda manual tidak bisa
    # dilepas lagi (410). Sekarang hanya `reconciled_amount > 0` (pencocokan nyata) yang menahan.
    r = await klien.post(f"/api/cash-transactions/{KL}/void", headers=kepala_admin, json={"reason": "uji PK-21"})
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/cash-transactions/{K2}/void", headers=kepala_admin, json={"reason": "uji PK-21"})
    assert r.status_code == 409 and "dicocokkan" in r.text, r.text
