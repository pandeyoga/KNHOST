"""KB-1 Tugas 5 — kategori kas manual "Transfer / Top-up" ditutup untuk kas manual BARU (server).

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` §5.2 (D3) dan §7 butir 6.
Kas manual baru berkategori transfer/top-up (semua ejaan & huruf) ditolak 400 di rute dan di kartu Asisten; kas LAMA
berkategori itu tetap bisa dibatalkan & diposting ulang; Pindah Dana (`ref_type="fund_transfer"`) tidak terkena.
"""
import uuid

import pytest
from fastapi import HTTPException


pytestmark = pytest.mark.anyio

PESAN = "Pakai Pindah Dana untuk setor tunai, isi kas kecil, dan pindah antar rekening."
VARIAN = ["transfer", "Transfer", "TRANSFER", "Transfer / Top-up", "top-up", "Top-Up", "topup", "TOP UP", " Top up kas "]


async def _dua_rekening(db, ent, tag):
    await db.bank_accounts.insert_many([
        {"id": f"ba_kb5_{tag}_{i}", "name": f"Rekening KB5 {i}", "account_type": "cash" if i == 1 else "bank",
         "cash_type": "kas_besar", "entity_id": ent, "is_active": True, "status": "active", "opening_balance": 5_000_000}
        for i in (1, 2)])
    return f"ba_kb5_{tag}_1", f"ba_kb5_{tag}_2"


def _isi(rek, kategori, arah="out"):
    return {"cash_type": "kas_besar", "direction": arah, "amount": 100_000, "category": kategori,
            "description": "uji tutup transfer", "account_id": rek}


async def test_rute_menolak_semua_varian(klien, db, kepala_admin):
    ent = "ent_ksc"
    r1, _ = await _dua_rekening(db, ent, "a")
    h = {**kepala_admin, "X-Entity-Id": ent}
    for kat in VARIAN:
        for arah in ("out", "in"):
            r = await klien.post("/api/cash-transactions", headers=h, json=_isi(r1, kat, arah))
            assert r.status_code == 400 and r.json()["detail"] == PESAN, (kat, arah, r.text)
    assert await db.cash_transactions.count_documents({"account_id": r1}) == 0   # tidak ada kas tersimpan
    # kategori lain tetap boleh
    r = await klien.post("/api/cash-transactions", headers=h, json=_isi(r1, "operasional"))
    assert r.status_code == 200, r.text


async def test_kartu_asisten_menolak(aplikasi):
    from services import ai_cards

    class ApiPalsu:                      # penolakan terjadi sebelum ada panggilan API
        entity_header = "ent_x"

        async def call(self, *a, **k):
            raise AssertionError("tidak boleh dipanggil")

    for kat in ("Transfer", "top-up", "TOPUP", "Transfer / Top-up"):
        with pytest.raises(HTTPException) as e:
            await ai_cards._prep_cash_manual(ApiPalsu(), {"account_id": "x", "direction": "out", "amount": 1000,
                                                          "category": kat})
        assert e.value.status_code == 400 and e.value.detail == PESAN, kat


async def test_kas_lama_tetap_bisa_dibatalkan_dan_diposting_ulang(klien, db, kepala_admin):
    from services import cash_ledger
    ent = "ent_kanda"
    r1, _ = await _dua_rekening(db, ent, "b")
    h = {**kepala_admin, "X-Entity-Id": ent}
    lama = [await cash_ledger.create_cash(entity_id=ent, direction="out", amount=50_000, ref_type="manual",
                                          ref_id=f"kb5_{uuid.uuid4().hex[:8]}", account_id=r1,
                                          category="Transfer / Top-up", description="kas lama", actor="Uji")
            for _ in range(2)]
    # (1) dibatalkan
    r = await klien.post(f"/api/cash-transactions/{lama[0]['id']}/void", headers=h, json={"reason": "uji batal"})
    assert r.status_code == 200, r.text
    assert (await db.cash_transactions.find_one({"id": lama[0]["id"]}))["status"] == "void"
    # (2) posting gagal → Ulang
    await db.journal_entries.delete_many({"source_type": "cash_transaction", "source_id": lama[1]["id"]})
    await db.cash_transactions.update_one({"id": lama[1]["id"]}, {"$set": {"gl_status": "failed", "gl_posted": False,
                                                                           "gl_error": "uji"}})
    r = await klien.post(f"/api/finance/posting-failures/cash_transaction/{lama[1]['id']}/retry", headers=h)
    assert r.status_code == 200, r.text
    assert (await db.cash_transactions.find_one({"id": lama[1]["id"]}))["gl_status"] == "posted"
    assert await db.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": lama[1]["id"]})


async def test_pindah_dana_tidak_terkena(klien, db, kepala_admin):
    from services import cash_ledger
    ent = "ent_ksc"
    r1, r2 = await _dua_rekening(db, ent, "c")
    # kas pembuat bersama (jalur Pindah Dana) dengan kategori transfer tidak ditolak
    kas = await cash_ledger.create_cash(entity_id=ent, direction="out", amount=10_000, ref_type="fund_transfer",
                                        ref_id=f"kb5_{uuid.uuid4().hex[:8]}", account_id=r1, category="Transfer / Top-up",
                                        description="pindah dana", actor="Uji")
    assert kas["ref_type"] == "fund_transfer"
    h = {**kepala_admin, "X-Entity-Id": ent}
    r = await klien.post("/api/fund-transfers", headers=h, json={
        "entity_id": ent, "rekening_asal_id": r1, "rekening_tujuan_id": r2, "nominal": 100_000, "biaya": 0,
        "tanggal_kirim": "", "tanggal_terima": "", "catatan": "uji Pindah Dana tetap jalan"})
    assert r.status_code == 200, r.text
