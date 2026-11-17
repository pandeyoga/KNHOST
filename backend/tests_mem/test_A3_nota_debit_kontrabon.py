"""A3 retur (pelatihan keuangan 18 Nov) — nota debit retur beli memotong kontrabon sebesar NILAI NOTA (DPP + PPN).

Jurnal retur beli (`gl_service.post_purchase_return`, dasar hutang) mendebit Hutang Usaha sebesar `grand_total` (DPP + PPN).
Dulu `contra_bon_service.available_credits` menawarkan `total_amount` (DPP saja) sebagai potongan: kontrabon membayar PPN
barang yang sudah dikembalikan dan akun hutang pemasok tersisa debit sebesar PPN itu (ditemukan saat uji jalan A3, peserta
41: DN Rp 1.287.600 ditawarkan Rp 1.160.000).
"""
import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio
KSC = "ent_ksc"


async def _nota_debit(db, rid: str, sup: str, dpp: float, ppn: float, *, tanpa_grand: bool = False) -> None:
    doc = {"id": rid, "number": f"PRET-{rid[-4:]}", "debit_note_number": f"DN-{rid[-4:]}", "entity_id": KSC,
           "status": "approved", "supplier_outcome": "ap_credit", "ap_basis": "hutang", "supplier_id": sup,
           "total_amount": dpp, "ppn_amount": ppn, "approved_at": now_iso(), "created_at": now_iso()}
    if not tanpa_grand:
        doc["grand_total"] = round(dpp + ppn, 2)
    await db.purchase_returns.insert_one(doc)


async def test_A3_nota_debit_ditawarkan_dpp_plus_ppn(db):
    from services import contra_bon_service as cbs
    await _nota_debit(db, "pret_a3_0001", "sup_a3_1", 1_160_000, 127_600)
    (dn,) = (await cbs.available_credits("sup_a3_1", KSC))["purchase_returns"]
    assert (dn["amount"], dn["total_amount"], dn["ref_number"]) == (1_287_600, 1_287_600, "DN-0001")


async def test_A3_sisa_nota_debit_sesudah_dipotong_sebagian(db):
    # Nota 100.000 + PPN 11.000 = 111.000; kontrabon lain (diajukan) sudah memotong 50.000 → sisa 61.000.
    from services import contra_bon_service as cbs
    await _nota_debit(db, "pret_a3_0002", "sup_a3_2", 100_000, 11_000)
    await db.contra_bons.insert_one({"id": "cb_a3_1", "number": "KSC/CB-A3", "status": "submitted", "entity_id": KSC,
                                     "supplier_id": "sup_a3_2", "bills": [],
                                     "deductions": [{"id": "d1", "kind": "purchase_return", "ref_id": "pret_a3_0002",
                                                     "amount": 50_000}]})
    (dn,) = (await cbs.available_credits("sup_a3_2", KSC))["purchase_returns"]
    assert (dn["amount"], dn["total_amount"]) == (61_000, 111_000)


async def test_A3_nota_debit_lama_tanpa_grand_total_tetap_dpp(db):
    from services import contra_bon_service as cbs
    await _nota_debit(db, "pret_a3_0003", "sup_a3_3", 20_000, 0, tanpa_grand=True)
    (dn,) = (await cbs.available_credits("sup_a3_3", KSC))["purchase_returns"]
    assert dn["amount"] == 20_000
