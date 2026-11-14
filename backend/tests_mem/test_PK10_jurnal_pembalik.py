"""PK-10 — jurnal manual lewat validator pusat; satu penanda pembalik (docs/blueprint/unit/PK-10.md).

Admin, `X-Entity-Id: ent_ksc`. "Saldo kas" = Σ debit − Σ kredit akun 1-1100 di `ent_ksc`, dibaca sebagai selisih.
"Pembalik atas J" = jurnal bukan `void` ber-`ref.reverses_entry_id` = id J.
"""
from __future__ import annotations

import datetime
import importlib
import itertools
import re
import sys
from pathlib import Path

import pytest

from pembantu import AKTOR_UJI, tutup_periode
from services import gl_service as gl

pytestmark = pytest.mark.anyio
E1 = "ent_ksc"
# Tanggal buku (WIB, `book_date.tanggal_buku`), bukan tanggal UTC: antara 00.00–07.00 WIB tanggal UTC masih kemarin
# sedangkan jurnal bertanggal buku hari ini — uji yang memakai tanggal UTC merah pada jam itu.
from services.book_date import tanggal_buku as _tanggal_buku  # noqa: E402
HARI_INI = _tanggal_buku()
_n = itertools.count(1)


async def _saldo(db, akun="1-1100") -> float:
    d = k = 0.0
    async for je in db.journal_entries.find({"entity_id": E1, "status": {"$ne": "void"}}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == akun:
                d += float(ln.get("debit") or 0)
                k += float(ln.get("credit") or 0)
    return round(d - k, 2)


async def _pembalik(db, jid) -> int:
    return await db.journal_entries.count_documents({"ref.reverses_entry_id": jid, "status": {"$ne": "void"}})


def _jurnal(baris):
    return {"date": HARI_INI, "description": "uji PK-10", "lines": [
        {"account_code": a, "debit": d, "credit": c} for a, d, c in baris]}


@pytest.fixture(scope="module")
async def rek(db):
    await db.bank_accounts.insert_many([
        {"id": f"ba_pk10_{i}", "name": f"Bank PK10 {i}", "account_type": "bank", "cash_type": "kas_besar",
         "entity_id": E1, "is_active": True, "status": "active", "opening_balance": 0} for i in (1, 2)])
    return "ba_pk10_1"


async def _kas_masuk(klien, h, db, rek, n):
    r = await klien.post("/api/cash-transactions", headers=h, json={
        "cash_type": "kas_besar", "direction": "in", "amount": n, "category": "lain-lain",
        "description": f"uji PK-10 {next(_n)}", "account_id": rek})
    assert r.status_code == 200, r.text
    kas = r.json()
    j = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas["id"]}, {"_id": 0})
    return kas, j


async def _balik(klien, h, jid, alasan="uji balik manual", tanggal=HARI_INI):
    return await klien.post(f"/api/gl/journal/{jid}/reverse", headers=h, json={"date": tanggal, "reason": alasan})


def _nomor(no: str) -> int:
    return int(re.findall(r"(\d+)$", no or "0")[0])


async def test_U01_selisih_satu_sen_ditolak(klien, db, kepala_admin):
    n = await db.journal_entries.count_documents({})
    r = await klien.post("/api/gl/journal", headers=kepala_admin,
                         json=_jurnal([("1-1100", 1000.01, 0), ("4-9000", 0, 1000.00)]))
    assert r.status_code == 400, r.text
    assert "Jurnal tidak seimbang" in r.json()["detail"]
    assert await db.journal_entries.count_documents({}) == n
    akhir = await db.journal_entries.find({"entity_id": E1}).sort("number", -1).limit(1).to_list(1)
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal([("1-1100", 5, 0), ("4-9000", 0, 5)]))
    assert r.status_code == 200, r.text
    if akhir:
        assert _nomor(r.json()["number"]) == _nomor(akhir[0]["number"]) + 1


async def test_U02_pecahan_yang_pas_diterima(klien, kepala_admin):
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal(
        [("6-2000", 333.33, 0), ("6-2000", 333.33, 0), ("6-2000", 333.34, 0), ("1-1100", 0, 1000.00)]))
    assert r.status_code == 200, r.text
    r = await klien.post("/api/gl/journal", headers=kepala_admin,
                         json=_jurnal([("6-2000", 0.10, 0), ("6-2000", 0.20, 0), ("1-1100", 0, 0.30)]))
    assert r.status_code == 200, r.text


async def test_U03_baris_satu_sen(klien, kepala_admin):
    r = await klien.post("/api/gl/journal", headers=kepala_admin,
                         json=_jurnal([("6-2000", 0.01, 0), ("1-1100", 0, 0.01)]))
    assert r.status_code == 200, r.text


async def test_U04_balik_manual_lalu_batal_kas(klien, db, kepala_admin, rek):
    s0 = await _saldo(db)
    kas, j = await _kas_masuk(klien, kepala_admin, db, rek, 10_000_000)
    assert await _saldo(db) == s0 + 10_000_000
    r = await _balik(klien, kepala_admin, j["id"])
    assert r.status_code == 200, r.text
    manual = r.json()
    r = await klien.post(f"/api/cash-transactions/{kas['id']}/void", headers=kepala_admin, json={"reason": "uji batal"})
    assert r.status_code == 200, r.text
    assert await _pembalik(db, j["id"]) == 1
    assert await _saldo(db) == s0
    k = await db.cash_transactions.find_one({"id": kas["id"]})
    assert k["status"] == "void" and k.get("void_journal_entry_id") == manual["id"]


async def test_U05_U06_pembalik_otomatis_tidak_dibalik_lagi(klien, db, kepala_admin, rek):
    s0 = await _saldo(db)
    kas, j = await _kas_masuk(klien, kepala_admin, db, rek, 2_000_000)
    r = await klien.post(f"/api/cash-transactions/{kas['id']}/void", headers=kepala_admin, json={"reason": "uji batal"})
    assert r.status_code == 200, r.text
    v = await db.journal_entries.find_one({"source_type": "cash_transaction_void", "source_id": kas["id"]}, {"_id": 0})
    r = await _balik(klien, kepala_admin, v["id"])
    assert r.status_code == 400 and r.json()["detail"] == "Jurnal penutup / jurnal pembalik tidak dapat dibalik."
    r = await _balik(klien, kepala_admin, j["id"])
    assert r.status_code == 400 and r.json()["detail"] == f"Jurnal sudah dibalik oleh {v['number']}."
    assert await _saldo(db) == s0
    # U6 — penanda acuan + cermin warisan di jurnal asal; pembalik membawa ref.reverses_entry_id
    jj = await db.journal_entries.find_one({"id": j["id"]}, {"_id": 0})
    assert (jj["reversed_by_entry_id"], jj["reversed_by_entry_number"], jj["reversed"], jj["reversal_id"]) == (
        v["id"], v["number"], True, v["id"])
    assert v["ref"]["reverses_entry_id"] == j["id"]


async def _jurnal_sca(sid):
    return await gl._insert_entry(lines=[{"account_code": "2-1450", "debit": 500000, "credit": 0},
                                         {"account_code": "4-9000", "debit": 0, "credit": 500000}],
                                  description="uji store credit", date=gl.now_iso(), source_type="store_credit_adjust",
                                  source_id=sid, entity_id=E1, created_by="uji")


async def test_U07_manual_lalu_dokumen(db):
    s = await _jurnal_sca("sca_1")
    rev = await gl.reverse_entry(s["id"], HARI_INI, "uji balik manual", AKTOR_UJI)
    hasil = await gl.reverse_document("store_credit_adjust", "sca_1")
    assert [x["id"] for x in hasil] == [rev["id"]]
    assert await _pembalik(db, s["id"]) == 1


async def test_U08_dokumen_lalu_manual(db):
    s = await _jurnal_sca("sca_2")
    rev = (await gl.reverse_document("store_credit_adjust", "sca_2"))[0]
    with pytest.raises(ValueError, match="sudah dibalik"):
        await gl.reverse_entry(s["id"], HARI_INI, "uji balik manual", AKTOR_UJI)
    with pytest.raises(ValueError, match="pembalik tidak dapat dibalik"):
        await gl.reverse_entry(rev["id"], HARI_INI, "uji balik manual", AKTOR_UJI)


async def test_U09_data_warisan(klien, db, kepala_admin):
    L = await gl._insert_entry(lines=[{"account_code": "6-2000", "debit": 1000, "credit": 0},
                                      {"account_code": "1-1100", "debit": 0, "credit": 1000}],
                               description="warisan L", date=gl.now_iso(), source_type="manual_warisan",
                               source_id="", entity_id=E1, created_by="uji")
    await db.journal_entries.update_one({"id": L["id"]}, {"$set": {"reversed": True}})
    K = await gl._insert_entry(lines=[{"account_code": "1-1100", "debit": 1000, "credit": 0},
                                      {"account_code": "4-9000", "debit": 0, "credit": 1000}],
                               description="kas warisan", date=gl.now_iso(), source_type="cash_transaction",
                               source_id="kas_warisan", entity_id=E1, created_by="uji")
    await gl._insert_entry(lines=[{"account_code": "4-9000", "debit": 1000, "credit": 0},
                                  {"account_code": "1-1100", "debit": 0, "credit": 1000}],
                           description="void warisan", date=gl.now_iso(), source_type="cash_transaction_void",
                           source_id="kas_warisan", entity_id=E1, created_by="uji")
    for jid in (L["id"], K["id"]):
        r = await _balik(klien, kepala_admin, jid)
        assert r.status_code == 400 and r.json()["detail"].startswith("Jurnal sudah dibalik oleh"), r.text


async def _manual(klien, h, n, tanggal=HARI_INI):
    r = await klien.post("/api/gl/journal", headers=h,
                         json={**_jurnal([("6-2000", n, 0), ("1-1100", 0, n)]), "date": tanggal})
    assert r.status_code == 200, r.text
    return r.json()


async def test_U10_sisip_gagal_klaim_dicabut(klien, db, kepala_admin, paksa_jurnal_gagal):
    m = await _manual(klien, kepala_admin, 750000)
    async with paksa_jurnal_gagal("sisip", entity_id=E1, source_type="reversal", kali=1):
        r = await _balik(klien, kepala_admin, m["id"])
    assert r.status_code >= 400
    assert "reversed_by_entry_id" not in await db.journal_entries.find_one({"id": m["id"]}, {"_id": 0})
    assert await _pembalik(db, m["id"]) == 0
    r = await _balik(klien, kepala_admin, m["id"])
    assert r.status_code == 200, r.text
    assert await _pembalik(db, m["id"]) == 1


async def test_U11_tanggal_pembalik_di_periode_tertutup(klien, db, kepala_admin):
    m2 = await _manual(klien, kepala_admin, 50000, tanggal="2026-09-15")
    c = await tutup_periode(E1, "2026-10")
    try:
        n = await db.journal_entries.count_documents({})
        r = await _balik(klien, kepala_admin, m2["id"], tanggal="2026-10-15")
        assert r.status_code == 409, r.text
        assert "reversed_by_entry_id" not in await db.journal_entries.find_one({"id": m2["id"]}, {"_id": 0})
        assert await db.journal_entries.count_documents({}) == n
    finally:
        await db.period_closings.delete_one({"id": c["id"]})


async def test_U12_anulir_jurnal_yang_sudah_dibalik(klien, kepala_admin):
    m3 = await _manual(klien, kepala_admin, 25000)
    assert (await _balik(klien, kepala_admin, m3["id"])).status_code == 200
    r = await klien.post(f"/api/gl/journal/{m3['id']}/void", headers=kepala_admin)
    assert r.status_code == 400 and r.json()["detail"] == "Jurnal sudah/sedang dibalik — tidak bisa dianulir lagi."


async def test_U13_penjaga_pt_tetap(klien, db, kepala_admin, akun, sesi, peran_tanpa_acuan):
    j = await _manual(klien, kepala_admin, 12000)
    rid = await peran_tanpa_acuan({"accounting": ["view", "void"]}, label="Pembalik Kanda")
    h = await sesi(await akun(rid, entitas=("ent_kanda",)), entitas="ent_kanda")
    r = await _balik(klien, h, j["id"])
    assert r.status_code == 404, r.text
    assert "reversed_by_entry_id" not in await db.journal_entries.find_one({"id": j["id"]}, {"_id": 0})


async def test_U14_invarian_satu_pembalik(db, capsys):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    await vdi.layer_gl_audit_2026_09_invariants(db)
    keluar = capsys.readouterr().out
    assert re.search(r"\[PASS\].*INV-GL-REV-02", keluar), keluar[-600:]
    x = await _manual_service_dobel(db)
    await vdi.layer_gl_audit_2026_09_invariants(db)
    keluar = capsys.readouterr().out
    assert re.search(r"\[FAIL\].*INV-GL-REV-02", keluar) and x in keluar, keluar[-600:]


async def _manual_service_dobel(db) -> str:
    """Fixture: dua pembalik atas satu jurnal (disisip langsung, melewati jalur pembalik)."""
    asal = await gl._insert_entry(lines=[{"account_code": "6-2000", "debit": 100, "credit": 0},
                                         {"account_code": "1-1100", "debit": 0, "credit": 100}],
                                  description="asal dobel", date=gl.now_iso(), source_type="manual_dobel",
                                  source_id="", entity_id=E1, created_by="uji")
    # Indeks unik (source_type, source_id) → dua pembalik dibedakan tipe sumbernya, menunjuk jurnal asal yang sama.
    for st in ("reversal", "manual_dobel_reversal"):
        await gl._insert_entry(lines=[{"account_code": "1-1100", "debit": 100, "credit": 0},
                                      {"account_code": "6-2000", "debit": 0, "credit": 100}],
                               description="pembalik dobel", date=gl.now_iso(), source_type=st,
                               source_id=asal["id"], entity_id=E1, created_by="uji",
                               ref={"reverses_entry_id": asal["id"]})
    return asal["id"]
