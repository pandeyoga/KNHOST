"""PK-05 — bayar hutang pemasok lewat satu pintu niat bayar (U1–U14, U16 di database tiruan).

Lihat docs/blueprint/unit/PK-05.md. U15 dan U17 (balapan, indeks unik) dijalankan di MongoDB asli:
backend/tests/test_bp_PK05_bayar_hutang_mongo.py.
"""
import pytest

from core_utils import now_iso
from pembantu import aktifkan_akun, jumlah, nonaktifkan_akun, saldo_akun, tutup_periode
from services import ap_payment_service as aps
from services import contra_bon_service as cbs

JT = 1_000_000
KSC = "ent_ksc"


def bill(bid, total, *, ent=KSC, sup="sup_x", status="posted", po=None):
    return {"id": bid, "bill_number": bid.upper(), "entity_id": ent, "supplier_id": sup,
            "supplier_name": "Pemasok Uji", "status": status, "grand_total": total, "subtotal": total,
            "amount_paid": 0.0, "payments": [], "timeline": [], "po_id": po, "bill_date": "2026-11-01",
            "created_at": now_iso()}


def kontrabon(cid, bills, *, status="approved", ent=KSC, potongan=1 * JT):
    cb = {"id": cid, "number": cid.upper(), "entity_id": ent, "supplier_id": "sup_x",
          "supplier_name": "Pemasok Uji", "status": status, "created_at": now_iso(), "timeline": [],
          "payments": [], "decisions": [],
          "bills": [{"bill_id": b["id"], "bill_number": b["bill_number"], "applied_amount": b["grand_total"],
                     "settled_amount": 0.0, "po_id": None} for b in bills],
          "deductions": ([{"id": f"ded_{cid}", "kind": "supplier_penalty", "amount": potongan, "posts_gl": True,
                           "label": "denda telat"}] if potongan else [])}
    return cbs.recompute(cb)


@pytest.fixture(scope="module")
async def data(db):
    await db.bank_accounts.insert_many([
        {"id": "rek_ksc", "name": "Kas Besar KSC", "entity_id": KSC, "account_type": "bank", "cash_type": "kas_besar",
         "is_active": True, "opening_balance": 0},
        {"id": "rek_kanda", "name": "Kas Kanda", "entity_id": "ent_kanda", "account_type": "bank",
         "cash_type": "kas_besar", "is_active": True, "opening_balance": 0}])
    bills = [bill("vb_1", 11.1 * JT), bill("vb_6", 2 * JT), bill("vb_4", 3 * JT), bill("vb_7", 4 * JT),
             bill("vb_8", 1 * JT)]
    cbsets = {}
    for cid in ("cbn_1", "cbn_2", "cbn_2b", "cbn_4"):
        pair = [bill(f"{cid}_a", 10 * JT), bill(f"{cid}_b", 5 * JT)]
        bills += pair
        cbsets[cid] = kontrabon(cid, pair)
    cbsets["cbn_3"] = kontrabon("cbn_3", [bills[2]], status="draft", potongan=0)
    cbsets["cbn_5"] = kontrabon("cbn_5", [bill("vb_x5", 1 * JT)], status="draft", potongan=0)
    await db.vendor_bills.insert_many([dict(b) for b in bills])
    await db.contra_bons.insert_many([dict(c) for c in cbsets.values()])
    return True


async def bayar(klien, h, kind, target, body, key=None):
    hh = dict(h)
    if key:
        hh["Idempotency-Key"] = key
    path = f"/api/vendor-bills/{target}/pay" if kind == "vendor_bill" else f"/api/contra-bons/{target}/pay"
    return await klien.post(path, headers=hh, json=body)


async def tidak_ada_tulisan(db, target):
    assert await jumlah("cash_transactions", {"ref_id": target}) == 0
    assert await jumlah("ap_payment_intents", {"target_id": target}) == 0
    doc = await db.vendor_bills.find_one({"id": target}) or await db.contra_bons.find_one({"id": target})
    assert "saga_lock" not in doc


async def test_U1_periode_tertutup_faktur(klien, kepala_admin, db, data):
    c = await tutup_periode(KSC, "2026-09")
    try:
        r = await bayar(klien, kepala_admin, "vendor_bill", "vb_1",
                        {"amount": 11.1 * JT, "paid_at": "2026-09-20", "bank_account_id": "rek_ksc"})
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409, r.text
    assert (await db.vendor_bills.find_one({"id": "vb_1"}))["amount_paid"] == 0
    await tidak_ada_tulisan(db, "vb_1")


async def test_U2_periode_tertutup_kontrabon(klien, kepala_admin, db, data):
    c = await tutup_periode(KSC, "2026-09")
    try:
        r = await bayar(klien, kepala_admin, "contra_bon", "cbn_1", {"paid_at": "2026-09-20", "bank_account_id": "rek_ksc"})
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409, r.text
    cb = await db.contra_bons.find_one({"id": "cbn_1"})
    assert cb["status"] == "approved" and cb["payments"] == [] and not cb["deductions"][0].get("applied_at")
    for b in ("cbn_1_a", "cbn_1_b"):
        assert (await db.vendor_bills.find_one({"id": b}))["amount_paid"] == 0
    await tidak_ada_tulisan(db, "cbn_1")
    assert await jumlah("journal_entries", {"source_type": "contra_bon_deduction"}) == 0


async def test_U3_akun_nonaktif(klien, kepala_admin, db, data, paksa_jurnal_gagal):
    async with paksa_jurnal_gagal("akun", entity_id=KSC, kode_akun="2-1100"):
        r = await bayar(klien, kepala_admin, "vendor_bill", "vb_1",
                        {"amount": 5 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"})
    assert r.status_code == 409 and "Pembayaran belum bisa dicatat" in r.text, r.text
    await tidak_ada_tulisan(db, "vb_1")


async def test_U4_bayar_sebagian(klien, kepala_admin, db, data):
    h0 = await saldo_akun("2-1100", KSC)
    r = await bayar(klien, kepala_admin, "vendor_bill", "vb_1",
                    {"amount": 5 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}, key="k1")
    assert r.status_code == 200, r.text
    vb = await db.vendor_bills.find_one({"id": "vb_1"})
    assert vb["amount_paid"] == 5 * JT and vb["grand_total"] - vb["amount_paid"] == 6.1 * JT
    kas = await db.cash_transactions.find({"ref_id": "vb_1"}).to_list(10)
    assert len(kas) == 1 and kas[0]["amount"] == 5 * JT and kas[0]["entity_id"] == KSC
    assert kas[0]["account_id"] == "rek_ksc" and kas[0]["gl_status"] == "posted"
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas[0]["id"]}) == 1
    # 2-1100 bersaldo normal kredit (saldo = kredit − debit): pembayaran mendebit hutang → saldo turun 5 jt
    assert round(await saldo_akun("2-1100", KSC) - h0, 2) == -5 * JT
    assert r.json()["payment_intent"]["status"] == "done"


async def test_U5_kirim_ulang_kunci_sama(klien, kepala_admin, db, data):
    r = await bayar(klien, kepala_admin, "vendor_bill", "vb_1",
                    {"amount": 5 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}, key="k1")
    assert r.status_code == 200 and r.headers.get("X-Idempotent-Replay") == "true"
    intent_id = r.json()["payment_intent"]["id"]
    it = await db.ap_payment_intents.find_one({"id": intent_id})
    res = await aps.pay_payable(kind="vendor_bill", target_id="vb_1", actor={"name": "Budi Santoso", "id": "u"},
                                amount=5 * JT, paid_at=now_iso()[:10], bank_account_id="rek_ksc",
                                method="transfer", idempotency_key="k1")
    assert res["replayed"] is True and it["status"] == "done"
    assert await jumlah("cash_transactions", {"ref_id": "vb_1"}) == 1
    kas = await db.cash_transactions.find_one({"ref_id": "vb_1"})
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas["id"]}) == 1
    assert (await db.vendor_bills.find_one({"id": "vb_1"}))["amount_paid"] == 5 * JT


async def test_U6_jurnal_kas_gagal_lalu_diulang(klien, kepala_admin, db, data, paksa_jurnal_gagal):
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="cash_transaction"):
        r = await bayar(klien, kepala_admin, "vendor_bill", "vb_1",
                        {"amount": 6.1 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}, key="k2")
    assert r.status_code == 200 and r.json()["warning"], r.text
    vb = await db.vendor_bills.find_one({"id": "vb_1"})
    assert vb["status"] == "paid" and round(vb["amount_paid"], 2) == 11.1 * JT
    kas = await db.cash_transactions.find_one({"ref_id": "vb_1", "amount": 6.1 * JT})
    assert kas["gl_status"] == "failed"
    panel = (await klien.get("/api/finance/posting-failures", headers=kepala_admin)).json()
    assert any(i["id"] == kas["id"] for i in panel["items"])
    r2 = await klien.post(f"/api/finance/posting-failures/cash_transaction/{kas['id']}/retry", headers=kepala_admin)
    assert r2.status_code == 200, r2.text
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas["id"]}) == 1
    assert (await db.cash_transactions.find_one({"id": kas["id"]}))["gl_status"] == "posted"
    assert (await db.ap_payment_intents.find_one({"id": kas["payment_intent_id"]}))["gl_status"] == "posted"


async def test_U7_bayar_kontrabon(klien, kepala_admin, db, data):
    h0 = await saldo_akun("2-1100", KSC)
    r = await bayar(klien, kepala_admin, "contra_bon", "cbn_1",
                    {"amount": 14 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}, key="k3")
    assert r.status_code == 200, r.text
    a, b = await db.vendor_bills.find_one({"id": "cbn_1_a"}), await db.vendor_bills.find_one({"id": "cbn_1_b"})
    assert a["amount_paid"] == 10 * JT and b["amount_paid"] == 5 * JT
    assert await jumlah("cash_transactions", {"ref_id": "cbn_1"}) == 1
    assert await jumlah("journal_entries", {"source_type": "contra_bon_deduction", "source_id": {"$regex": "^cbn_1:"}}) == 1
    assert round(await saldo_akun("2-1100", KSC) - h0, 2) == -15 * JT   # kas 14 jt + potongan 1 jt
    cb = await db.contra_bons.find_one({"id": "cbn_1"})
    assert cb["status"] == "paid" and len(cb["payments"]) == 1 and cb["version"] >= 1


async def test_U8_gagal_di_kas_lalu_diulang(klien, kepala_admin, db, data, monkeypatch):
    asli = aps._insert_cash
    state = {"n": 1}

    async def gagal_sekali(intent):
        if state["n"]:
            state["n"] -= 1
            raise RuntimeError("uji: kas dipaksa gagal")
        return await asli(intent)
    monkeypatch.setattr(aps, "_insert_cash", gagal_sekali)
    body = {"amount": 14 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}
    r1 = await bayar(klien, kepala_admin, "contra_bon", "cbn_2", body, key="k4")
    assert r1.status_code == 500
    it = await db.ap_payment_intents.find_one({"target_id": "cbn_2"})
    assert it["status"] == "pending" and it["step"] == "bills"
    r2 = await bayar(klien, kepala_admin, "contra_bon", "cbn_2", body, key="k4")
    assert r2.status_code == 200, r2.text
    a, b = await db.vendor_bills.find_one({"id": "cbn_2_a"}), await db.vendor_bills.find_one({"id": "cbn_2_b"})
    assert a["amount_paid"] == 10 * JT and b["amount_paid"] == 5 * JT
    assert await jumlah("cash_transactions", {"ref_id": "cbn_2"}) == 1
    kas = await db.cash_transactions.find_one({"ref_id": "cbn_2"})
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas["id"]}) == 1
    assert await jumlah("journal_entries", {"source_type": "contra_bon_deduction", "source_id": {"$regex": "^cbn_2:"}}) == 1
    assert len((await db.contra_bons.find_one({"id": "cbn_2"}))["payments"]) == 1


async def test_U9_niat_menggantung_lalu_dilanjutkan(klien, kepala_admin, db, data, monkeypatch):
    asli = aps._insert_cash
    state = {"n": 1}

    async def gagal_sekali(intent):
        if state["n"]:
            state["n"] -= 1
            raise RuntimeError("uji: kas dipaksa gagal")
        return await asli(intent)
    monkeypatch.setattr(aps, "_insert_cash", gagal_sekali)
    body = {"amount": 14 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}
    assert (await bayar(klien, kepala_admin, "contra_bon", "cbn_2b", body, key="k5")).status_code == 500
    r = await bayar(klien, kepala_admin, "contra_bon", "cbn_2b", body, key="k6")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "AP_PAYMENT_PENDING", r.text
    iid = r.json()["detail"]["intent_id"]
    assert await jumlah("cash_transactions", {"ref_id": "cbn_2b"}) == 0
    r2 = await klien.post(f"/api/ap-payments/{iid}/resume", headers=kepala_admin)
    assert r2.status_code == 200, r2.text
    a, b = await db.vendor_bills.find_one({"id": "cbn_2b_a"}), await db.vendor_bills.find_one({"id": "cbn_2b_b"})
    assert a["amount_paid"] == 10 * JT and b["amount_paid"] == 5 * JT
    assert await jumlah("cash_transactions", {"ref_id": "cbn_2b"}) == 1


async def test_U10_jurnal_potongan_gagal_lalu_diulang(klien, kepala_admin, db, data, paksa_jurnal_gagal):
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="contra_bon_deduction"):
        r = await bayar(klien, kepala_admin, "contra_bon", "cbn_4",
                        {"amount": 14 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}, key="k7")
    assert r.status_code == 200 and r.json()["warning"], r.text
    assert (await db.contra_bons.find_one({"id": "cbn_4"}))["gl_status"] == "failed"
    r2 = await klien.post("/api/finance/posting-failures/contra_bon/cbn_4/retry", headers=kepala_admin)
    assert r2.status_code == 200, r2.text
    assert await jumlah("journal_entries", {"source_type": "contra_bon_deduction", "source_id": {"$regex": "^cbn_4:"}}) == 1
    assert (await db.contra_bons.find_one({"id": "cbn_4"}))["gl_status"] == "posted"


async def test_U11_faktur_dipegang_kontrabon(klien, kepala_admin, db, data):
    body = {"amount": 3 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}
    r = await bayar(klien, kepala_admin, "vendor_bill", "vb_4", body)
    assert r.status_code == 409 and "sedang dipegang kontrabon" in r.text, r.text
    await tidak_ada_tulisan(db, "vb_4")
    cb = await cbs._get("cbn_3")
    await cbs.cancel("cbn_3", {"note": "uji"}, {"name": "uji"}) if hasattr(cbs, "cancel") else None
    if (await db.contra_bons.find_one({"id": "cbn_3"}))["status"] != "cancelled":
        await db.contra_bons.update_one({"id": cb["id"]}, {"$set": {"status": "cancelled"}})
    r2 = await bayar(klien, kepala_admin, "vendor_bill", "vb_4", body)
    assert r2.status_code == 200, r2.text


async def test_U12_rekening_dan_entitas(klien, kepala_admin, db, data):
    body = {"amount": 2 * JT, "paid_at": now_iso()[:10]}
    r = await bayar(klien, kepala_admin, "vendor_bill", "vb_6", {**body, "bank_account_id": "rek_kanda"})
    assert r.status_code == 400 and "bukan milik" in r.text, r.text
    r = await bayar(klien, kepala_admin, "vendor_bill", "vb_6", body)
    assert r.status_code == 400 and "Pilih rekening" in r.text, r.text
    await tidak_ada_tulisan(db, "vb_6")
    kanda_kas0 = await jumlah("cash_transactions", {"entity_id": "ent_kanda"})
    kanda_je0 = await jumlah("journal_entries", {"entity_id": "ent_kanda"})
    r = await bayar(klien, kepala_admin, "vendor_bill", "vb_6",
                    {**body, "bank_account_id": "rek_ksc", "entity_id": "ent_kanda", "cash_type": "kas_kecil"})
    assert r.status_code == 200, r.text
    kas = await db.cash_transactions.find_one({"ref_id": "vb_6"})
    assert kas["entity_id"] == kas["owner_entity_id"] == KSC and kas["cash_type"] == "kas_besar"
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas["id"]})
    assert je["entity_id"] == KSC
    assert await jumlah("cash_transactions", {"entity_id": "ent_kanda"}) == kanda_kas0
    assert await jumlah("journal_entries", {"entity_id": "ent_kanda"}) == kanda_je0


async def test_U13_gagal_sebelum_efek_lalu_batal(klien, kepala_admin, db, data, monkeypatch):
    asli = aps._apply_allocations
    state = {"n": 1}

    async def gagal_sekali(intent, actor):
        if state["n"]:
            state["n"] -= 1
            raise RuntimeError("uji: alokasi dipaksa gagal")
        return await asli(intent, actor)
    monkeypatch.setattr(aps, "_apply_allocations", gagal_sekali)
    body = {"amount": 4 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_ksc"}
    assert (await bayar(klien, kepala_admin, "vendor_bill", "vb_7", body, key="k8")).status_code == 500
    it = await db.ap_payment_intents.find_one({"target_id": "vb_7"})
    assert it["status"] == "pending" and it["step"] == "intent"
    assert (await db.vendor_bills.find_one({"id": "vb_7"}))["amount_paid"] == 0
    r = await klien.post(f"/api/ap-payments/{it['id']}/cancel", headers=kepala_admin, json={"reason": "salah nominal"})
    assert r.status_code == 200, r.text
    assert (await db.ap_payment_intents.find_one({"id": it["id"]}))["status"] == "cancelled"
    assert "saga_lock" not in await db.vendor_bills.find_one({"id": "vb_7"})
    r = await bayar(klien, kepala_admin, "vendor_bill", "vb_7", body, key="k9")
    assert r.status_code == 200, r.text
    assert await jumlah("cash_transactions", {"ref_id": "vb_7"}) == 1
    kas = await db.cash_transactions.find_one({"ref_id": "vb_7"})
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas["id"]}) == 1


async def test_U14_pengguna_pt_lain(klien, akun, sesi, peran_tanpa_acuan, data):
    # Koreksi blueprint: peran bawaan Finance tidak memegang vendor_bill.pay di HEAD (dijawab 403, bukan 404), jadi
    # pagar PT diuji dengan peran yang memegang izin bayar tetapi ditugaskan di PT lain.
    p = await peran_tanpa_acuan({"vendor_bill": ["view", "pay"]})
    h = await sesi(await akun(p, entitas=("ent_kanda",)), entitas="ent_kanda")
    r = await bayar(klien, h, "vendor_bill", "vb_8", {"amount": 1 * JT, "bank_account_id": "rek_ksc"})
    assert r.status_code == 404, r.text
    r = await klien.get("/api/ap-payments/accounts", headers=h, params={"kind": "vendor_bill", "target_id": "vb_8"})
    assert r.status_code == 404, r.text


async def test_U16_simpan_kontrabon_berversi(db, data):
    a = await cbs._get("cbn_5")
    b = await cbs._get("cbn_5")
    a["note"] = "salinan A"
    b["note"] = "salinan B"
    await cbs._save(a)
    with pytest.raises(cbs.ContraBonConflict):
        await cbs._save(b)
    assert (await db.contra_bons.find_one({"id": "cbn_5"}))["version"] == 1
