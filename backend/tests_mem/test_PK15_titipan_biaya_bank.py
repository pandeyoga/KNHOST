"""PK-15 — alokasi titipan bank dan biaya bank: tiap langkah berjurnal dan bisa diulang (docs/blueprint/unit/PK-15.md).

Tiap uji alokasi menyiapkan sendiri: pesanan `so_x` 8.000.000 dan `so_y` 4.000.000 milik `cus_x` di `ent_ksc`, baris
rekening koran masuk 10.000.000 yang dijadikan titipan lewat API. Admin, `X-Entity-Id: ent_ksc`.
"""
from __future__ import annotations

import importlib
import itertools
import re
import sys
from pathlib import Path

import pytest

from pembantu import tutup_periode
from services import ar_receipt_service as ar
from services import gl_service as gl

pytestmark = pytest.mark.anyio
E1 = "ent_ksc"
BA = "ba_pk15"
_n = itertools.count(1)
BASE = "/api/bank-reconciliation/lines"


async def _saldo(db, akun, ent=E1) -> float:
    d = k = 0.0
    async for je in db.journal_entries.find({"entity_id": ent, "status": {"$ne": "void"}, "lines.account_code": akun}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == akun:
                d += float(ln.get("debit") or 0)
                k += float(ln.get("credit") or 0)
    return round(d - k, 2)


@pytest.fixture(scope="module", autouse=True)
async def dasar(aplikasi, db):
    await db.bank_accounts.insert_one({"id": BA, "name": "BCA PK15", "account_type": "bank", "cash_type": "bank",
                                       "bank_name": "BCA", "entity_id": E1, "is_active": True, "status": "active",
                                       "opening_balance": 0})
    await db.customers.insert_one({"id": "cus_x", "code": "CUS-PK15", "name": "Toko X", "entity_id": E1})


async def _baris(db, arah="in", nominal=10_000_000, tanggal="2026-11-05") -> str:
    i = next(_n)
    lid = f"stl_pk15_{i}"
    await db.bank_statement_lines.insert_one({
        "id": lid, "bank_account_id": BA, "entity_id": E1, "stmt_date": tanggal, "amount": float(nominal),
        "direction": arah, "description": f"mutasi uji PK-15 {i}", "counterparty": "", "desc_key": "", "ref": "",
        "external_id": f"pk15-{i}", "balance": 0.0, "status": "unmatched", "match_kind": "", "matched_txn_id": "",
        "matched_txn_ids": [], "allocations": [], "score": 0, "score_explain": [], "suggestions": [],
        "match_type": "", "matched_at": "", "matched_by": "", "holding": {}, "holding_allocated": [],
        "holding_remaining": 0.0, "import_batch": "pk15", "format_id": "", "created_at": gl.now_iso(),
        "updated_at": gl.now_iso()})
    return lid


async def _siap(klien, db, h):
    i = next(_n)
    so = {}
    for k, total in (("x", 8_000_000), ("y", 4_000_000)):
        oid = f"so_{k}_pk15_{i}"
        await db.sales_orders.insert_one({"id": oid, "number": f"SO-PK15-{k.upper()}{i}", "entity_id": E1,
                                          "customer_id": "cus_x", "customer_name": "Toko X", "grand_total": total,
                                          "status": "confirmed", "payments": [], "paid_total": 0.0,
                                          "created_at": gl.now_iso()})
        so[k] = oid
    lid = await _baris(db)
    r = await klien.post(f"{BASE}/{lid}/holding", headers=h, json={"note": "uji PK-15"})
    assert r.status_code == 200, r.text
    return lid, so


async def _alokasi(klien, h, lid, pairs):
    return await klien.post(f"{BASE}/{lid}/holding/allocate", headers=h, json={
        "customer_id": "cus_x", "reason_code": "titipan_teridentifikasi", "note": "uji",
        "allocations": [{"order_id": o, "amount": a} for o, a in pairs]})


async def _jurnal_alokasi(db, lid) -> list:
    return await db.journal_entries.find({"source_type": "bank_holding_alloc", "source_id": {"$regex": f"^{lid}:"},
                                          "status": {"$ne": "void"}}, {"_id": 0}).to_list(50)


async def _terbayar(db, oid) -> float:
    o = await db.sales_orders.find_one({"id": oid}, {"_id": 0, "payments": 1})
    return round(sum(float(p.get("amount") or 0) for p in (o.get("payments") or [])), 2)


async def _baris_doc(db, lid):
    return await db.bank_statement_lines.find_one({"id": lid}, {"_id": 0})


async def test_U01_alokasi_kedua_ke_pesanan_sama_berjurnal(klien, db, kepala_admin):
    lid, so = await _siap(klien, db, kepala_admin)
    t0 = await _saldo(db, "2-1950")
    r1 = await _alokasi(klien, kepala_admin, lid, [(so["x"], 3_000_000)])
    r2 = await _alokasi(klien, kepala_admin, lid, [(so["x"], 2_000_000)])
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    js = await _jurnal_alokasi(db, lid)
    assert sorted(j["total_debit"] for j in js) == [2_000_000, 3_000_000]
    assert len({j["source_id"] for j in js}) == 2
    b = await _baris_doc(db, lid)
    assert b["holding_remaining"] == 5_000_000
    assert await _saldo(db, "2-1950") - t0 == 5_000_000   # 2-1950 turun dari −10 jt (kredit) menjadi −5 jt
    assert await _terbayar(db, so["x"]) == 5_000_000


async def test_U02_satu_panggilan_dua_butir_ke_pesanan_sama(klien, db, kepala_admin):
    lid, so = await _siap(klien, db, kepala_admin)
    r = await _alokasi(klien, kepala_admin, lid, [(so["x"], 3_000_000), (so["x"], 2_000_000)])
    assert r.status_code == 200, r.text
    assert len(await _jurnal_alokasi(db, lid)) == 2
    b = await _baris_doc(db, lid)
    its = b["holding_allocated"]
    assert [x["status"] for x in its] == ["done", "done"] and len({x["id"] for x in its}) == 2
    assert b["holding_remaining"] == 5_000_000


async def test_U03_U04_gagal_di_tengah_lalu_dilanjutkan(klien, db, kepala_admin, monkeypatch):
    lid, so = await _siap(klien, db, kepala_admin)
    asli = ar.apply_from_bank_holding
    hit = {"n": 0}

    async def _kedua_gagal(*a, **kw):
        hit["n"] += 1
        if hit["n"] == 2:
            raise RuntimeError("uji: pelunasan pesanan gagal")
        return await asli(*a, **kw)
    monkeypatch.setattr(ar, "apply_from_bank_holding", _kedua_gagal)
    r = await _alokasi(klien, kepala_admin, lid, [(so["x"], 3_000_000), (so["y"], 4_000_000)])
    assert r.status_code >= 400, r.text
    b = await _baris_doc(db, lid)
    assert b["holding_remaining"] == 7_000_000
    assert [(x["order_id"], x["status"]) for x in b["holding_allocated"]] == [(so["x"], "done")]
    assert await _terbayar(db, so["y"]) == 0
    assert len(await _jurnal_alokasi(db, lid)) == 1
    assert "saga_lock" not in b
    monkeypatch.setattr(ar, "apply_from_bank_holding", asli)
    # U4 — paksaan dicabut, alokasi so_y
    r = await _alokasi(klien, kepala_admin, lid, [(so["y"], 4_000_000)])
    assert r.status_code == 200, r.text
    assert (await _baris_doc(db, lid))["holding_remaining"] == 3_000_000
    assert len(await _jurnal_alokasi(db, lid)) == 2
    assert await _terbayar(db, so["y"]) == 4_000_000


async def test_U05_U06_jurnal_gagal_lalu_dilanjutkan(klien, db, kepala_admin, monkeypatch):
    lid, so = await _siap(klien, db, kepala_admin)
    t0 = await _saldo(db, "2-1950")
    asli = gl._insert_entry
    hit = {"n": 0}

    async def _jurnal_kedua_gagal(*a, **kw):
        if kw.get("source_type") == "bank_holding_alloc":
            hit["n"] += 1
            if hit["n"] == 2:
                raise RuntimeError("uji: jurnal alokasi gagal")
        return await asli(*a, **kw)
    monkeypatch.setattr(gl, "_insert_entry", _jurnal_kedua_gagal)
    r = await _alokasi(klien, kepala_admin, lid, [(so["x"], 3_000_000), (so["y"], 4_000_000)])
    assert r.status_code == 409 and "jurnalnya gagal" in r.text, r.text
    b = await _baris_doc(db, lid)
    y = [x for x in b["holding_allocated"] if x["order_id"] == so["y"]][0]
    assert y["status"] == "applied" and y["gl_status"] == "failed" and y.get("gl_error")
    assert b["holding_remaining"] == 3_000_000
    assert await _terbayar(db, so["y"]) == 4_000_000
    assert len(await _jurnal_alokasi(db, lid)) == 1
    assert "saga_lock" not in b
    # layar: baris titipan membawa butir yang jurnalnya belum terbit (lencana "Jurnal belum terbit")
    r = await klien.get("/api/bank-reconciliation/holding", headers=kepala_admin)
    row = [x for x in r.json()["items"] if x["id"] == lid][0]
    assert [g["order_number"] for g in row["gl_failed"]] and "jurnal alokasi gagal" in row["gl_failed"][0]["gl_error"]
    monkeypatch.setattr(gl, "_insert_entry", asli)
    # U6 — butir tertinggal dilanjutkan; alokasi baru tidak diproses
    r = await _alokasi(klien, kepala_admin, lid, [(so["x"], 1_000_000)])
    assert r.status_code == 409 and "baru saja dilanjutkan" in r.text, r.text
    b = await _baris_doc(db, lid)
    assert len(await _jurnal_alokasi(db, lid)) == 2
    assert [x["status"] for x in b["holding_allocated"] if x["order_id"] == so["y"]] == ["done"]
    assert await _terbayar(db, so["y"]) == 4_000_000
    assert await _terbayar(db, so["x"]) == 3_000_000
    assert b["holding_remaining"] == 3_000_000
    assert await _saldo(db, "2-1950") - t0 == 7_000_000   # 2-1950 tersisa −3 jt = sisa titipan


async def test_U07_melebihi_sisa(klien, db, kepala_admin):
    lid, so = await _siap(klien, db, kepala_admin)
    r = await _alokasi(klien, kepala_admin, lid, [(so["x"], 11_000_000)])
    assert r.status_code == 400 and "melebihi sisa titipan" in r.text, r.text
    b = await _baris_doc(db, lid)
    assert b["holding_remaining"] == 10_000_000 and b["holding_allocated"] == []


async def test_U08_lintas_pt_ditolak(klien, db, kepala_admin, akun, sesi, peran_tanpa_acuan):
    lid, so = await _siap(klien, db, kepala_admin)
    await db.sales_orders.insert_one({"id": "so_k_pk15", "number": "SO-K-PK15", "entity_id": "ent_kanda",
                                      "customer_id": "cus_x", "grand_total": 5_000_000, "status": "confirmed",
                                      "payments": []})
    r = await _alokasi(klien, kepala_admin, lid, [("so_k_pk15", 1_000_000)])
    assert r.status_code == 403 and "entitas lain" in r.text, r.text
    rid = await peran_tanpa_acuan({"cash": ["view", "create"]}, label="Kas Kanda PK15")
    h = await sesi(await akun(rid, entitas=("ent_kanda",)), entitas="ent_kanda")
    r = await _alokasi(klien, h, lid, [(so["x"], 1_000_000)])
    assert r.status_code in (403, 404), r.text
    b = await _baris_doc(db, lid)
    assert b["holding_allocated"] == [] and await _terbayar(db, so["x"]) == 0
    assert await _jurnal_alokasi(db, lid) == []


async def test_U09_biaya_bank_periode_tertutup(klien, db, kepala_admin):
    lid = await _baris(db, "out", 25_000, "2026-10-15")
    c = await tutup_periode(E1, "2026-10")
    try:
        n = await db.cash_transactions.count_documents({})
        r = await klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "charge"})
        assert r.status_code == 409, r.text
        assert await db.cash_transactions.count_documents({}) == n
        b = await _baris_doc(db, lid)
        assert not b.get("charge") and "saga_lock" not in b
    finally:
        await db.period_closings.delete_one({"id": c["id"]})


async def _kas_baris(db, lid):
    return await db.cash_transactions.find({"ref_type": "bank_statement_line", "ref_id": lid,
                                            "status": {"$ne": "void"}}, {"_id": 0}).to_list(10)


async def test_U10_U12_biaya_bank_jurnal_gagal_lalu_ulang(klien, db, kepala_admin, paksa_jurnal_gagal):
    lid = await _baris(db, "out", 25_000, "2026-11-06")
    from services import bank_recon_service as brs
    akun_biaya = (await brs.load_cfg(E1))["charge_acc"]
    b0 = await _saldo(db, akun_biaya)
    async with paksa_jurnal_gagal("sisip", entity_id=E1, source_type="cash_transaction", kali=1):
        r = await klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "charge"})
    assert r.status_code == 409 and "sudah tercatat, tetapi jurnalnya gagal" in r.text, r.text
    kas = await _kas_baris(db, lid)
    assert len(kas) == 1 and kas[0]["gl_status"] == "failed"
    assert "saga_lock" not in await _baris_doc(db, lid)
    r = await klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "charge"})
    assert r.status_code == 200, r.text
    kas = await _kas_baris(db, lid)
    assert len(kas) == 1 and kas[0]["gl_status"] == "posted"
    assert await db.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": kas[0]["id"],
                                                     "status": {"$ne": "void"}}) == 1
    assert (await _baris_doc(db, lid))["charge"]["cash_txn_id"] == kas[0]["id"]
    assert await _saldo(db, akun_biaya) - b0 == 25_000
    # U12 — lepas tautan (kas lama di-void), catat lagi → satu kas bukan-void baru
    r = await klien.post(f"{BASE}/{lid}/unmatch", headers=kepala_admin, json={"reason": "uji ulang PK-15"})
    assert r.status_code == 200, r.text
    r = await klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "charge"})
    assert r.status_code == 200, r.text
    baru = await _kas_baris(db, lid)
    assert len(baru) == 1 and baru[0]["id"] != kas[0]["id"]


async def test_U11_bunga_bank(klien, db, kepala_admin):
    lid = await _baris(db, "in", 15_000, "2026-11-06")
    from services import bank_recon_service as brs
    akun_bunga = (await brs.load_cfg(E1))["interest_acc"]
    r = await klien.post(f"{BASE}/{lid}/book-charge", headers=kepala_admin, json={"kind": "interest"})
    assert r.status_code == 200, r.text
    kas = await _kas_baris(db, lid)
    assert len(kas) == 1 and kas[0]["direction"] == "in" and kas[0]["amount"] == 15_000
    assert kas[0]["gl_status"] == "posted"
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas[0]["id"]})
    assert any(ln["account_code"] == akun_bunga and ln["credit"] == 15_000 for ln in je["lines"])


async def test_U13_invarian_titipan(db, capsys):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    await vdi.layer_bank_invariants(db)
    keluar = capsys.readouterr().out
    assert re.search(r"PASS.*INV-BNK-03", keluar), keluar[-1500:]
