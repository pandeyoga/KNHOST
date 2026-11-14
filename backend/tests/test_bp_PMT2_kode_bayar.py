"""PM-T2 U15 — di MongoDB ASLI (lingkungan A): kode bayar unik lintas PT, tabrakan diulang, satu kode per pesanan.

Database tiruan tidak menguji keunikan maupun balapan (`03_LINGKUNGAN_UJI.md` §1); butir ini hanya sah di sini. Fungsi
`services.payment_code_service.ensure_for_order` dipanggil langsung (proses uji, MongoDB yang sama dengan backend)
sesudah backend dinyalakan ulang dengan PM-T2 (indeks wajib `payment_codes.uq_pay_code`, `uq_pay_code_line`).

1. Indeks unik wajib terpasang dengan kunci dan ekspresi parsial yang benar.
2. 200 pesanan bayar-dulu (fixture, termin CBD) → 200 kode dibuat bersamaan (`asyncio.gather`) → 200 kode berbeda,
   tiap kode tepat satu dokumen, tiap pesanan tepat satu kode.
3. Tabrakan dipaksa: pembangkit acak mengembalikan kode yang SUDAH ADA dulu, lalu kode baru → `DuplicateKeyError`
   indeks `uq_pay_code` ditangkap, diulang, dan berhasil; kode kembar tidak pernah tersimpan.
4. Satu pesanan, 10 pemanggilan bersamaan → tetap satu kode (indeks `uq_pay_code_line`).

Fixture pesanan & kode uji dihapus di akhir. Tidak untuk database berisi data nyata.
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

import pymongo
import pytest

DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
N = 200
TAG = f"pmt2a_{uuid.uuid4().hex[:6]}"


def _svc():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from services import payment_code_service as pcs  # noqa: E402 — butuh MONGO_URL backend
    return pcs


def _pesanan(i: int) -> dict:
    return {"id": f"so_{TAG}_{i}", "number": f"SO-{TAG}-{i}", "entity_id": ENT, "customer_id": f"cus_{TAG}",
            "grand_total": 1_000_000 + i, "payment_term_code": "CBD", "status": "confirmed", "payment_code": ""}


@pytest.fixture(scope="module", autouse=True)
def bersih():
    yield
    DB.payment_codes.delete_many({"order_id": {"$regex": f"^so_{TAG}_"}})
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_{TAG}_"}})


def test_U15_indeks_unik_wajib_terpasang():
    info = DB.payment_codes.index_information()
    kode = info.get("uq_pay_code") or {}
    assert kode.get("unique") and [(k, int(d)) for k, d in kode["key"]] == [("code", 1)], kode
    baris = info.get("uq_pay_code_line") or {}
    assert baris.get("unique") and [(k, int(d)) for k, d in baris["key"]] == [("order_id", 1), ("line_id", 1)], baris


def test_U15_dua_ratus_kode_bersamaan_berbeda():
    pcs = _svc()
    orders = [_pesanan(i) for i in range(N)]
    DB.sales_orders.insert_many([dict(o) for o in orders])

    async def _jalan():
        return await asyncio.gather(*[pcs.ensure_for_order(o) for o in orders])

    hasil = asyncio.run(_jalan())
    kode = [h["code"] for h in hasil]
    assert len(set(kode)) == N
    for c in kode:
        assert DB.payment_codes.count_documents({"code": c}) == 1, c
    assert DB.payment_codes.count_documents({"order_id": {"$regex": f"^so_{TAG}_"}}) == N
    assert DB.sales_orders.count_documents({"id": {"$regex": f"^so_{TAG}_"}, "payment_code": {"$in": kode}}) == N


def test_U15_tabrakan_dipaksa_diulang_dan_berhasil(monkeypatch):
    pcs = _svc()
    ada = DB.payment_codes.find_one({"order_id": {"$regex": f"^so_{TAG}_"}}, {"_id": 0, "code": 1})["code"]
    awalan, acak_lama = ada.split("-", 1)
    urut = iter([acak_lama, acak_lama, pcs._acak()])
    monkeypatch.setattr(pcs, "_acak", lambda: next(urut))
    o = _pesanan(N + 1)
    DB.sales_orders.insert_one(dict(o))
    baru = asyncio.run(pcs.ensure_for_order(o))
    assert baru["code"] != ada and baru["code"].startswith(f"{awalan}-")
    assert DB.payment_codes.count_documents({"code": ada}) == 1
    assert DB.payment_codes.count_documents({"order_id": o["id"]}) == 1


def test_U15_satu_pesanan_sepuluh_panggilan_bersamaan_satu_kode():
    pcs = _svc()
    o = _pesanan(N + 2)
    DB.sales_orders.insert_one(dict(o))

    async def _jalan():
        return await asyncio.gather(*[pcs.ensure_for_order(o) for _ in range(10)])

    hasil = asyncio.run(_jalan())
    assert len({h["code"] for h in hasil}) == 1
    assert DB.payment_codes.count_documents({"order_id": o["id"]}) == 1
