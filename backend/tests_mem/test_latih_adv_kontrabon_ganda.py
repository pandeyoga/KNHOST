"""Uji adversarial pelatihan 18 Nov (agen D) — dua kontrabon dibuat BERSAMAAN untuk tagihan yang sama.

Di layar (peserta 97): Finance dan Manajer membuka "Kontrabon baru" untuk pemasok yang sama, memilih tagihan VB-00032,
lalu menekan [Terbitkan kontrabon] hampir bersamaan → KSC/CB-00005 (Manajer) dan KSC/CB-00006 (Finance) sama-sama
terbit berisi VB-00032. Sebab: `contra_bon_service.create` memeriksa `occupied_bills()` (baca) lalu `insert_one` (tulis)
tanpa penjaga di antaranya. Aturan "satu faktur tidak boleh masuk dua kontrabon" harus tetap berlaku saat bersamaan:
paling banyak SATU kontrabon aktif memegang tagihan itu; yang kalah mendapat pesan yang jelas.
"""
from __future__ import annotations

import asyncio

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"


@pytest.fixture(scope="module")
async def data(db):
    await db.suppliers.insert_one({"id": "sup_cbadv", "name": "Pemasok Uji Kontrabon Ganda", "entity_id": KSC,
                                   "status": "active"})
    await db.vendor_bills.insert_one({
        "id": "vb_cbadv", "bill_number": "VB-CBADV", "entity_id": KSC, "supplier_id": "sup_cbadv",
        "supplier_name": "Pemasok Uji Kontrabon Ganda", "status": "posted", "grand_total": 1_864_800.0,
        "subtotal": 1_864_800.0, "amount_paid": 0.0, "payments": [], "timeline": [], "po_id": None,
        "bill_date": "2026-11-01", "created_at": now_iso()})
    return True


async def test_dua_kontrabon_bersamaan_hanya_satu_memegang_tagihan(db, data, monkeypatch):
    from services import contra_bon_service as cbs
    # Database tiruan menjalankan kueri tanpa jeda; balapan di layar (dua permintaan HTTP) dibuat ulang dengan
    # palang: kedua pembuatan selesai MEMBACA tagihan yang terpakai sebelum salah satunya MENULIS.
    asli = cbs.occupied_bills
    tiba, lanjut = [], asyncio.Event()

    async def occupied_bills_berpalang(exclude_cb_id: str = ""):
        out = await asli(exclude_cb_id)
        tiba.append(1)
        if len(tiba) >= 2:
            lanjut.set()
        await asyncio.wait_for(lanjut.wait(), 5)
        return out

    monkeypatch.setattr(cbs, "occupied_bills", occupied_bills_berpalang)
    payload = {"supplier_id": "sup_cbadv", "entity_id": KSC, "bills": [{"bill_id": "vb_cbadv"}]}
    hasil = await asyncio.gather(
        cbs.create(dict(payload), {"id": "usr_fin", "name": "Peserta 97"}, [KSC]),
        cbs.create(dict(payload), {"id": "usr_mgr", "name": "Dewi Manager"}, [KSC]),
        return_exceptions=True)
    monkeypatch.setattr(cbs, "occupied_bills", asli)
    aktif = await db.contra_bons.find({"bills.bill_id": "vb_cbadv", "status": {"$ne": "cancelled"}}).to_list(10)
    assert len(aktif) <= 1, [c["number"] for c in aktif]
    gagal = [h for h in hasil if isinstance(h, Exception)]
    assert len(gagal) >= 1
    for g in gagal:
        assert isinstance(g, cbs.ContraBonError), repr(g)
        assert "VB-CBADV" in str(g) and "kontrabon" in str(g).lower(), str(g)


async def test_kontrabon_berurutan_tetap_ditolak_seperti_dulu(db, data):
    from services import contra_bon_service as cbs
    aktif = await db.contra_bons.find({"bills.bill_id": "vb_cbadv", "status": {"$ne": "cancelled"}}).to_list(10)
    if not aktif:   # kedua pembuatan bersamaan sama-sama mundur → buat satu sekarang
        await cbs.create({"supplier_id": "sup_cbadv", "entity_id": KSC, "bills": [{"bill_id": "vb_cbadv"}]},
                         {"id": "usr_fin", "name": "Peserta 97"}, [KSC])
    with pytest.raises(cbs.ContraBonError) as e:
        await cbs.create({"supplier_id": "sup_cbadv", "entity_id": KSC, "bills": [{"bill_id": "vb_cbadv"}]},
                         {"id": "usr_mgr", "name": "Dewi Manager"}, [KSC])
    assert "sudah ada di kontrabon" in str(e.value)
    assert await db.contra_bons.count_documents({"bills.bill_id": "vb_cbadv", "status": {"$ne": "cancelled"}}) == 1
