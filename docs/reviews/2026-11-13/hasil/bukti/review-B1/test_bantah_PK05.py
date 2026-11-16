"""Uji bantahan reviewer B1 — PK-05 (SL-01, GL-03, SL-02). Dijalankan di lapis B (database tiruan):
cp ke backend/tests_mem/ lalu `python -m pytest tests_mem/test_bantah_PK05.py -n 0 -q`. Bukan bagian gate."""
import pytest

from core_utils import now_iso
from pembantu import jumlah, saldo_akun, tutup_periode
from test_PK05_bayar_hutang import JT, KSC, bayar, bill, kontrabon


@pytest.fixture(scope="module")
async def data(db):
    await db.bank_accounts.insert_many([
        {"id": "rek_ksc", "name": "Kas Besar KSC", "entity_id": KSC, "account_type": "bank", "cash_type": "kas_besar",
         "is_active": True, "opening_balance": 0},
        {"id": "rek_kanda", "name": "Kas Kanda", "entity_id": "ent_kanda", "account_type": "bank",
         "cash_type": "kas_besar", "is_active": True, "opening_balance": 0}])
    bills = [bill("vb_a", 10 * JT), bill("vb_b", 3 * JT), bill("vb_c", 4 * JT), bill("vb_d", 2 * JT)]
    pair = [bill("cbx_a", 10 * JT), bill("cbx_b", 5 * JT)]
    await db.vendor_bills.insert_many([dict(b) for b in bills + pair])
    await db.contra_bons.insert_one(dict(kontrabon("cbx", pair)))
    return True


async def test_SL01_ulang_bayar_kontrabon_lunas_kunci_baru(klien, kepala_admin, db, data):
    r = await bayar(klien, kepala_admin, "contra_bon", "cbx",
                    {"amount": 14 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}, key="b1")
    assert r.status_code == 200, r.text
    r2 = await bayar(klien, kepala_admin, "contra_bon", "cbx",
                     {"amount": 14 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}, key="b2")
    assert r2.status_code in (400, 409), r2.text
    assert await jumlah("cash_transactions", {"ref_id": "cbx"}) == 1
    assert await jumlah("journal_entries", {"source_type": "contra_bon_deduction", "source_id": {"$regex": "^cbx:"}}) == 1
    a = await db.vendor_bills.find_one({"id": "cbx_a"})
    assert a["amount_paid"] == 10 * JT


async def test_SL01_jalur_lain_void_bayar_faktur_milik_kontrabon(klien, kepala_admin, db, data):
    """Kas kontrabon 14 jt melunasi DUA faktur. Void lewat pintu faktur (`/vendor-bills/{id}/payments/{pid}/void`)
    untuk satu baris pelunasan tidak boleh mem-void kas 14 jt sambil hanya membuka satu faktur."""
    a = await db.vendor_bills.find_one({"id": "cbx_a"})
    p = next(x for x in a["payments"] if x.get("cash_txn_id"))
    h0 = await saldo_akun("2-1100", KSC)
    r = await klien.post(f"/api/vendor-bills/cbx_a/payments/{p['id']}/void", headers=kepala_admin,
                         json={"notes": "salah rekening uji"})
    a2 = await db.vendor_bills.find_one({"id": "cbx_a"})
    b2 = await db.vendor_bills.find_one({"id": "cbx_b"})
    kas = await db.cash_transactions.find_one({"ref_id": "cbx"})
    cb = await db.contra_bons.find_one({"id": "cbx"})
    naik_gl = round(await saldo_akun("2-1100", KSC) - h0, 2)
    naik_sub = round((a["amount_paid"] - a2["amount_paid"]) + (5 * JT - b2["amount_paid"]), 2)
    print("VOID", r.status_code, r.text[:200], "| kas", kas["status"], "| cb", cb["status"],
          "| hutang GL naik", naik_gl, "| hutang buku pembantu naik", naik_sub)
    assert r.status_code == 409 or naik_gl == naik_sub, (
        f"void lewat pintu faktur: GL hutang naik {naik_gl} tetapi buku pembantu naik {naik_sub}; "
        f"kas {kas['status']}, kontrabon {cb['status']}")


async def test_GL03_periode_tertutup_dengan_uang_muka(klien, kepala_admin, db, data):
    c = await tutup_periode(KSC, "2026-08")
    try:
        r = await bayar(klien, kepala_admin, "vendor_bill", "vb_b",
                        {"amount": 3.5 * JT, "paid_at": "2026-08-10", "bank_account_id": "rek_ksc",
                         "variance": {"kind": "ap_advance", "reason": "lebih bayar uji"}})
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409, r.text
    assert (await db.vendor_bills.find_one({"id": "vb_b"}))["amount_paid"] == 0
    assert await jumlah("cash_transactions", {"ref_id": "vb_b"}) == 0
    assert await jumlah("ap_payment_intents", {"target_id": "vb_b"}) == 0


async def test_GL03_koreksi_bayar_lalu_void_saldo_kembali(klien, kepala_admin, db, data):
    h0 = await saldo_akun("2-1100", KSC)
    r = await bayar(klien, kepala_admin, "vendor_bill", "vb_c",
                    {"amount": 4 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}, key="g1")
    assert r.status_code == 200, r.text
    vb = await db.vendor_bills.find_one({"id": "vb_c"})
    kas = await db.cash_transactions.find_one({"ref_id": "vb_c"})
    assert kas["gl_status"] == "posted" and kas.get("payment_intent_id")
    r = await klien.post(f"/api/vendor-bills/vb_c/payments/{vb['payments'][0]['id']}/void", headers=kepala_admin,
                         json={"notes": "koreksi uji reviewer"})
    assert r.status_code == 200, r.text
    assert round(await saldo_akun("2-1100", KSC) - h0, 2) == 0
    vb = await db.vendor_bills.find_one({"id": "vb_c"})
    assert vb["amount_paid"] == 0 and vb["status"] == "posted"


async def test_SL02_kunci_sama_isi_beda_dan_entitas_dari_klien(klien, kepala_admin, db, data):
    body = {"amount": 1 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc",
            "entity_id": "ent_kanda", "cash_type": "kas_kecil", "created_by": "penyusup"}
    r = await bayar(klien, kepala_admin, "vendor_bill", "vb_a", body, key="s1")
    assert r.status_code == 200, r.text
    kas = await db.cash_transactions.find({"ref_id": "vb_a"}).to_list(10)
    assert len(kas) == 1 and kas[0]["entity_id"] == KSC and kas[0]["created_by"] != "penyusup"
    assert await jumlah("journal_entries", {"entity_id": "ent_kanda", "source_id": kas[0]["id"]}) == 0
    r2 = await bayar(klien, kepala_admin, "vendor_bill", "vb_a", dict(body, amount=2 * JT), key="s1")
    assert r2.status_code == 409, r2.text
    assert await jumlah("cash_transactions", {"ref_id": "vb_a"}) == 1
    r3 = await bayar(klien, kepala_admin, "vendor_bill", "vb_a", dict(body, bank_account_id="rek_kanda"), key="s3")
    assert r3.status_code == 400, r3.text


async def test_SL02_tanpa_kunci_klik_ganda(klien, kepala_admin, db, data):
    """Catatan: tanpa header Idempotency-Key server tetap menerima (asumsi spesifikasi). Uji ini MENCATAT akibatnya."""
    body = {"amount": 0.5 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}
    r1 = await bayar(klien, kepala_admin, "vendor_bill", "vb_d", body)
    r2 = await bayar(klien, kepala_admin, "vendor_bill", "vb_d", body)
    n = await jumlah("cash_transactions", {"ref_id": "vb_d"})
    print("TANPA_KUNCI", r1.status_code, r2.status_code, "kas:", n)
    assert n == 1, f"dua kiriman identik tanpa kunci menghasilkan {n} kas keluar"
