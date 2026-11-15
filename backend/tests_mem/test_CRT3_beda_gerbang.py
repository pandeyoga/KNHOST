"""CR-T3 RISIKO — skrip pembanding `scripts/crt3_beda_gerbang_kredit.py` (BACA-SAJA) di database tiruan (H3: tidak
dijalankan ke data nyata). Fixture SISIP: pelanggan berdata di `ent_ksc` (plafon khusus 10 jt di KSC) dengan piutang
terkirim 6 jt di KSC dan 6 jt di `ent_kanda` (tanpa profil di KANDA = plafon bawaan PT 0 = tanpa batas).

Hitung tangan: aturan lama = piutang LINTAS PT 12 jt > plafon PT pemilik data 10 jt → blocked (kedua PT); mesin baru per
PT: KSC 6 jt < 8 jt (80 %) → lolos, KANDA tanpa plafon → lolos → dua pasangan berbeda, sebab "piutang kini per PT".
Pelanggan satu PT tanpa titipan/giro → sama (tidak terdaftar).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from pembantu_crt3 import JUTA, KANDA, KSC, g1, pesanan_terkirim, profil, uid

pytestmark = pytest.mark.anyio
SKRIP = Path(__file__).resolve().parents[2] / "scripts" / "crt3_beda_gerbang_kredit.py"


def _modul():
    spec = importlib.util.spec_from_file_location("crt3_beda", SKRIP)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


async def test_CRT3_skrip_pembanding_baca_saja(db):
    cid = uid("cus")
    await db.customers.insert_one({"id": cid, "name": "Toko Dua PT", "entity_id": KSC, "status": "active"})
    await profil(db, cid, KSC, plafon=10 * JUTA)
    await pesanan_terkirim(db, cid, KSC, 6 * JUTA)
    await pesanan_terkirim(db, cid, KANDA, 6 * JUTA)
    sama = await g1(db, entitas=KSC, titipan=0)          # satu PT, tanpa titipan → hasil lama = baru
    sebelum = {k: await db[k].count_documents({}) for k in ("customer_balances", "credit_gate_rejections")}
    tahan = await db.sales_orders.count_documents({"credit_hold": True})
    out = await _modul().bandingkan()
    beda = {(d["customer_id"], d["entity_id"]): d for d in out["different"]}
    assert set(beda) >= {(cid, KSC), (cid, KANDA)}
    assert all(beda[(cid, e)]["lama"] == "blocked" and beda[(cid, e)]["baru"] == "lolos" for e in (KSC, KANDA))
    assert "piutang kini per PT (K-29)" in beda[(cid, KANDA)]["sebab"]
    assert "plafon PT pesanan, bukan PT pemilik data pelanggan" in beda[(cid, KANDA)]["sebab"]
    assert not any(c == sama["cid"] for c, _ in beda)
    # baca-saja: tidak ada saldo tersimpan, penolakan, atau tahanan yang ditulis
    assert {k: await db[k].count_documents({}) for k in sebelum} == sebelum
    assert await db.sales_orders.count_documents({"credit_hold": True}) == tahan
