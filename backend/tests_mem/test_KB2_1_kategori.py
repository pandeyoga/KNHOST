"""KB-2 Tugas 1 (C5) — kategori Pembelian/Gaji ditutup untuk kas manual BARU (server).

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-2-kas-manual-design.md` §5.1 dan §7.8 butir 2.
Kas manual baru berkategori pembelian/gaji (akun lawan jurnal = persediaan 1-1300 / beban gaji 6-1000) ditolak 400 di rute
dan di kartu Asisten, untuk kas masuk maupun keluar; `create_cash` (bayar tagihan, Proses Gaji) tidak terkena; kas LAMA
tetap bisa dibatalkan.
"""
import uuid

import pytest
from fastapi import HTTPException


pytestmark = pytest.mark.anyio

PESAN = ("Kategori Pembelian dan Gaji tidak lagi dipakai di kas manual: pembelian barang lewat PO/tagihan pemasok, "
         "gaji lewat Proses Gaji. Belanja kecil kebutuhan kantor pakai kategori Operasional.")
DITUTUP = ["pembelian", "Pembelian", "Beli kain", "bahan bakar", "gaji", "Gaji / Upah", "payroll"]
BOLEH = ["operasional", "lain", "modal", "sewa"]


async def _rekening(db, ent, tag):
    rek = f"ba_kb21_{tag}"
    await db.bank_accounts.insert_one(
        {"id": rek, "name": f"Rekening KB21 {tag}", "account_type": "cash", "cash_type": "kas_besar",
         "entity_id": ent, "is_active": True, "status": "active", "opening_balance": 5_000_000})
    return rek


def _isi(rek, kategori, arah="out"):
    return {"cash_type": "kas_besar", "direction": arah, "amount": 100_000, "category": kategori,
            "description": "uji C5", "account_id": rek}


async def test_pembantu_dan_konstanta():
    from services import cash_ledger as cl
    assert cl.PESAN_KATEGORI_PEMBELIAN_GAJI_DITUTUP == PESAN
    for k in DITUTUP:
        assert cl.kategori_kas_manual_ditutup(k) is True, k
    for k in BOLEH + ["", None, "Biaya listrik"]:
        assert cl.kategori_kas_manual_ditutup(k) is False, k


async def test_rute_menolak_pembelian_dan_gaji(klien, db, kepala_admin):
    ent = "ent_ksc"
    rek = await _rekening(db, ent, "a")
    h = {**kepala_admin, "X-Entity-Id": ent}
    for kat in DITUTUP:
        for arah in ("out", "in"):
            r = await klien.post("/api/cash-transactions", headers=h, json=_isi(rek, kat, arah))
            assert r.status_code == 400 and r.json()["detail"] == PESAN, (kat, arah, r.text)
    assert await db.cash_transactions.count_documents({"account_id": rek}) == 0
    for kat in BOLEH:
        r = await klien.post("/api/cash-transactions", headers=h, json=_isi(rek, kat))
        assert r.status_code == 200, (kat, r.text)


async def test_kartu_asisten_menolak(aplikasi):
    from services import ai_cards

    class ApiPalsu:
        entity_header = "ent_x"

        async def call(self, *a, **k):
            raise AssertionError("tidak boleh dipanggil")

    for kat in ("pembelian", "Gaji / Upah", "Beli kain"):
        with pytest.raises(HTTPException) as e:
            await ai_cards._prep_cash_manual(ApiPalsu(), {"account_id": "x", "direction": "out", "amount": 1000,
                                                          "category": kat})
        assert e.value.status_code == 400 and e.value.detail == PESAN, kat


async def test_create_cash_langsung_tidak_terkena(db):
    from services import cash_ledger
    ent = "ent_ksc"
    rek = await _rekening(db, ent, "b")
    kas = await cash_ledger.create_cash(entity_id=ent, direction="out", amount=50_000, ref_type="vendor_bill",
                                        ref_id=f"kb21_{uuid.uuid4().hex[:8]}", account_id=rek, category="pembelian",
                                        description="bayar tagihan", actor="Uji")
    assert kas["category"] == "pembelian"


async def test_kas_lama_pembelian_bisa_dibatalkan(klien, db, kepala_admin):
    from services import cash_ledger
    ent = "ent_kanda"
    rek = await _rekening(db, ent, "c")
    h = {**kepala_admin, "X-Entity-Id": ent}
    lama = await cash_ledger.create_cash(entity_id=ent, direction="out", amount=50_000, ref_type="manual",
                                         ref_id=f"kb21_{uuid.uuid4().hex[:8]}", account_id=rek, category="pembelian",
                                         description="kas lama", actor="Uji")
    r = await klien.post(f"/api/cash-transactions/{lama['id']}/void", headers=h, json={"reason": "uji batal"})
    assert r.status_code == 200, r.text
    assert (await db.cash_transactions.find_one({"id": lama["id"]}))["status"] == "void"
