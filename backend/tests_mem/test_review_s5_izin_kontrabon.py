"""Review adversarial S5 (Hutang per Pemasok, commit ac25d81) — **data kontrabon hanya bagi `contra_bon.view`**.

Temuan R-S5-03: `GET /vendor-bills/payables/by-supplier/{id}` berjanji "kontrabon hanya bagi pemegang contra_bon.view"
(daftar `contra_bons` memang `None`), tetapi tiap baris tagihan tetap membawa `contra_bon: {id, number, status,
status_label}` kontrabon pemegangnya. Pemegang `vendor_bill.view` saja melihat nomor & status kontrabon.

Persiapan (FIXTURE): pemasok **K** (`ent_ksc`) — tagihan T1 1.000.000 (bebas) + T2 2.000.000 dipegang kontrabon KB-RS5
(disetujui).
Harapan: Admin melihat nomor KB-RS5 di baris T2; peran kustom `vendor_bill.view` saja melihat T2 "dipegang" (tidak bisa
dibayar langsung) tanpa id/nomor/status kontrabon.
"""
import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio
KSC = "ent_ksc"


def _tagihan(bid: str, total: float) -> dict:
    return {"id": bid, "bill_number": f"VB-{bid[-4:].upper()}", "entity_id": KSC, "supplier_id": "sup_rs5k",
            "supplier_name": "Pemasok K Review", "status": "posted", "grand_total": float(total),
            "subtotal": float(total), "amount_paid": 0.0, "payment_status": "unpaid", "payments": [], "timeline": [],
            "po_id": None, "po_number": "PO-RS5K", "bill_date": "2026-10-01", "due_date": "", "created_at": now_iso()}


@pytest.fixture(scope="module")
async def data(db):
    from services import contra_bon_service as cbs
    await db.suppliers.insert_one({"id": "sup_rs5k", "name": "Pemasok K Review", "code": "RS5K", "entity_id": KSC,
                                   "status": "active", "payment_term_code": "NET30"})
    await db.vendor_bills.insert_many([_tagihan("vb_rs5k1", 1_000_000), _tagihan("vb_rs5k2", 2_000_000)])
    cb = cbs.recompute({"id": "cbn_rs5", "number": "KB-RS5", "entity_id": KSC, "supplier_id": "sup_rs5k",
                        "supplier_name": "Pemasok K Review", "status": "approved", "created_at": now_iso(),
                        "timeline": [], "payments": [], "decisions": [], "deductions": [],
                        "bills": [{"bill_id": "vb_rs5k2", "bill_number": "VB-S5K2", "applied_amount": 2_000_000.0,
                                   "settled_amount": 0.0, "po_id": None}]})
    await db.contra_bons.insert_one(dict(cb))
    return "sup_rs5k"


async def test_R_S5_03_admin_melihat_kontrabon_pemegang(klien, kepala_admin, data):
    j = (await klien.get(f"/api/vendor-bills/payables/by-supplier/{data}", headers=kepala_admin,
                         params={"entity_id": KSC})).json()
    t2 = next(b for b in j["bills"] if b["bill_id"] == "vb_rs5k2")
    assert t2["contra_bon"]["number"] == "KB-RS5" and [c["number"] for c in j["contra_bons"]] == ["KB-RS5"]


async def test_R_S5_03_tanpa_izin_kontrabon_hanya_fakta_dipegang(klien, data, akun, sesi, peran_tanpa_acuan):
    lihat = await peran_tanpa_acuan({"vendor_bill": ["view"]}, label="RS5 lihat tagihan saja")
    h = await sesi(await akun(lihat))
    r = await klien.get(f"/api/vendor-bills/payables/by-supplier/{data}", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["contra_bons"] is None
    t1 = next(b for b in j["bills"] if b["bill_id"] == "vb_rs5k1")
    t2 = next(b for b in j["bills"] if b["bill_id"] == "vb_rs5k2")
    assert t1["contra_bon"] is None
    assert t2["contra_bon"] and not any(t2["contra_bon"].values()), t2["contra_bon"]   # dipegang, tanpa identitas
    assert "KB-RS5" not in r.text and "cbn_rs5" not in r.text
    assert j["totals"]["held"] == 2_000_000.0 and j["totals"]["payable_direct"] == 1_000_000.0
