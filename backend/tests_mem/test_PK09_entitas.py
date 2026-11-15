"""PK-09 — PT tidak boleh ditentukan isi permintaan (docs/blueprint/unit/PK-09.md).

A = `ent_ksc`, B = `ent_kanda`, C = PT ketiga dari seed. Akun `akb` (peran kustom tanpa acuan: akuntansi, kas, piutang,
antar-PT, hutang = Kelola penuh) hanya ditugaskan di B dengan header B; `aka` sama tetapi hanya A. Fixture milik A
disisipkan langsung. "Tanpa tulisan" = dokumen sasaran sama sebelum/sesudah; jurnal & kas tidak bertambah.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio
A, B = "ent_ksc", "ent_kanda"
LEVELS = {"accounting": "manage", "finance_ops": "manage", "ar": "manage", "interco": "manage", "payable": "manage"}
T = "2026-11-05T00:00:00+00:00"


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    from services.amendment_service import ensure_reasons
    await ensure_reasons()
    c = (await db.business_entities.find_one({"id": {"$nin": [A, B]}, "status": "active"}, {"_id": 0, "id": 1}))["id"]
    r = await klien.post("/api/access/roles", headers=kepala_admin,
                         json={"label": "Keuangan Satu PT", "base_role": "", "levels": LEVELS})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    ub, ua = await akun(rid, entitas=(B,)), await akun(rid, entitas=(A,))
    akb, aka = await sesi(ub, entitas=B), await sesi(ua, entitas=A)
    await db.customers.insert_many([{"id": "cus_a", "name": "Pelanggan A", "entity_id": A, "status": "active"},
                                    {"id": "cus_b", "name": "Pelanggan B", "entity_id": B, "status": "active"}])
    await db.sales_orders.insert_many([
        {"id": "so_a", "number": "SO-A", "entity_id": A, "customer_id": "cus_a", "status": "confirmed",
         "grand_total": 1000000, "payments": [], "created_at": T},
        {"id": "so_b", "number": "SO-B", "entity_id": B, "customer_id": "cus_b", "status": "confirmed",
         "grand_total": 1000000, "payments": [{"amount": 400000, "date": T}], "created_at": T}])
    await db.ar_receipts.insert_one({"id": "rcp_a", "number": "RCP-A", "entity_id": A, "customer_id": "cus_a",
                                     "status": "posted", "amount": 100000,
                                     "variance": {"needs_decision": True, "delta": 1000}})
    await db.payment_plans.insert_many([
        {"id": "pyp_a", "number": "PP-A", "entity_id": A, "doc_type": "sales_order", "doc_id": "so_a",
         "customer_id": "cus_a", "status": "active", "total_amount": 1000000, "mode": "net",
         "lines": [{"seq": 1, "kind": "installment", "label": "Lunas", "amount": 1000000, "due_date": "2026-12-01",
                    "status": "open", "paid_amount": 0}], "created_at": T},
        {"id": "pyp_b", "number": "PP-B", "entity_id": B, "doc_type": "sales_order", "doc_id": "so_b",
         "customer_id": "cus_b", "status": "active", "total_amount": 1000000, "mode": "custom",
         "lines": [{"seq": 1, "kind": "dp", "label": "DP", "amount": 400000, "due_date": "2026-11-10",
                    "status": "paid", "paid_amount": 400000},
                   {"seq": 2, "kind": "installment", "label": "Pelunasan", "amount": 600000,
                    "due_date": "2026-12-10", "status": "open", "paid_amount": 0}], "created_at": T}])
    await db.penalties.insert_one({"id": "pnl_a", "number": "DN-A", "entity_id": A, "doc_id": "so_a", "plan_id": "",
                                   "line_seq": 0, "status": "draft", "amount": 50000.0, "paid_amount": 0.0})
    await db.payment_variance_decisions.insert_one({"id": "pvd_a", "number": "PVD-A", "entity_id": A,
                                                    "status": "applied", "kind": "write_off", "amount": 1000})
    await db.vendor_bills.insert_one({"id": "vb_a", "bill_number": "VB-A", "entity_id": A, "status": "posted",
                                      "ppn_amount": 11000, "dpp": 100000, "grand_total": 111000,
                                      "supplier_name": "Pemasok A"})
    await db.tax_invoices_in.insert_one({"id": "fpm_a", "entity_id": A, "status": "recorded", "vendor_bill_id": "vb_a",
                                         "ppn_amount": 11000, "faktur_date": "2026-11-05"})
    await db.tax_pph_records.insert_one({"id": "pphr_a", "entity_id": A, "period": "2026-11", "code": "pph23",
                                         "dpp": 100000, "amount": 2000})
    await db.bank_accounts.insert_one({"id": "ba_a", "name": "Bank A", "account_type": "bank", "cash_type": "kas_besar",
                                       "entity_id": A, "is_active": True, "status": "active"})
    await db.interco_transactions.insert_many([
        {"id": "ict_ac", "pair_id": "pair_ac", "role": "seller", "entity_id": A, "seller_entity_id": A,
         "buyer_entity_id": c, "status": "draft", "number": "ICT-AC", "grand_total": 100000, "lines": []},
        {"id": "ict_ac_b", "pair_id": "pair_ac", "role": "buyer", "entity_id": c, "seller_entity_id": A,
         "buyer_entity_id": c, "status": "draft", "number": "ICT-AC-B", "grand_total": 100000, "lines": []}])
    await db.interco_returns.insert_many([
        {"id": "icr_ac", "return_pair_id": "rpair_ac", "role": "returner", "entity_id": c, "status": "draft"},
        {"id": "icr_ac_r", "return_pair_id": "rpair_ac", "role": "receiver", "entity_id": A, "status": "draft"}])
    await db.interco_settlements.insert_one({"id": "ics_ac", "payer_entity_id": c, "payee_entity_id": A,
                                             "status": "posted", "amount": 100000})
    await db.intercompany_eliminations.insert_one({"id": "elim_ac", "name": "Eliminasi A-C", "entity_from": A,
                                                   "entity_to": c, "effective_date": "2026-11-30", "lines": []})
    await db.supplier_contracts.insert_one({"id": "ctr_ac", "partner_kind": "entity", "status": "active",
                                            "entity_id": A, "partner_id": c, "updated_at": T})
    return {"akb": akb, "aka": aka, "c": c, "nama_b": ub["name"]}


async def _jejak(db) -> tuple:
    return (await db.journal_entries.count_documents({}), await db.cash_transactions.count_documents({}))


def _jurnal(eid):
    return {"date": "2026-11-05", "description": "uji PK-09", "entity_id": eid, "lines": [
        {"account_code": "6-2000", "debit": 100000, "credit": 0},
        {"account_code": "1-1100", "debit": 0, "credit": 100000}]}


async def test_U01_jurnal_ke_pt_lain_ditolak(klien, db, siap):
    n = await db.journal_entries.count_documents({"entity_id": A})
    r = await klien.post("/api/gl/journal", headers=siap["akb"], json=_jurnal(A))
    assert r.status_code == 403, r.text
    assert await db.journal_entries.count_documents({"entity_id": A}) == n


async def test_U02_admin_boleh_pt_yang_ditugaskan(klien, kepala_admin, siap):
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal(B))
    assert r.status_code == 200, r.text
    assert r.json()["entity_id"] == B
    r = await klien.post("/api/gl/journal", headers=kepala_admin, json=_jurnal("all"))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Pilih satu PT untuk tindakan ini."


async def test_U03_akun_bagan_pt_lain(klien, db, siap):
    h, q = siap["akb"], {"entity_id": A}
    hasil = [
        await klien.get("/api/gl/accounts", headers=h, params=q),
        await klien.post("/api/gl/accounts", headers=h, params=q,
                         json={"code": "6-9999", "name": "Akun Uji", "type": "expense"}),
        await klien.patch("/api/gl/accounts/1-1250", headers=h, params=q, json={"is_active": False}),
        await klien.delete("/api/gl/accounts/1-1250", headers=h, params=q),
        await klien.get("/api/gl/inventory-drift-explain", headers=h, params=q),
    ]
    assert [r.status_code for r in hasil] == [403] * 5, [r.text[:80] for r in hasil]
    assert not await db.gl_accounts.find_one({"entity_id": A, "code": "6-9999"})
    assert not await db.gl_accounts.find_one({"entity_id": A, "code": "1-1250", "is_active": False})


async def test_U04_kas_manual(klien, db, siap):
    h = siap["akb"]
    dasar = {"cash_type": "kas_besar", "direction": "out", "amount": 50000, "category": "operasional",
             "description": "uji PK-09"}
    n = await db.cash_transactions.count_documents({})
    r = await klien.post("/api/cash-transactions", headers=h, json={**dasar, "entity_id": A})
    assert r.status_code == 403, r.text
    r = await klien.post("/api/cash-transactions", headers=h, json={**dasar, "ref_type": "vendor_bill", "ref_id": "vb_a"})
    assert r.status_code == 400, r.text
    r = await klien.post("/api/cash-transactions", headers=h, json={**dasar, "account_id": "ba_a"})
    # PK-20 — rekening PT lain ditolak pembuat kas satu pintu: 409 "Rekening … bukan rekening aktif {PT}" (dulu 400)
    assert r.status_code == 409 and "bukan rekening aktif" in r.text, r.text
    # PK-20 — kas wajib berekening: fixture satu rekening Bank milik B (rekening tunggal → dipakai otomatis)
    await db.bank_accounts.insert_one({"id": "ba_b", "name": "Bank B", "account_type": "bank",
                                       "cash_type": "kas_besar", "entity_id": B, "is_active": True})
    r = await klien.post("/api/cash-transactions", headers=h,
                         json={**dasar, "ref_type": "manual", "created_by": "Orang Lain"})
    assert r.status_code == 200, r.text
    k = r.json()
    # PK-20 — kas manual ber-`ref_type="manual"` (rujukan = kunci permintaan atau id baru)
    assert (k["entity_id"], k["ref_type"], k["created_by"]) == (B, "manual", siap["nama_b"])
    assert k["account_id"] == "ba_b"
    assert await db.cash_transactions.count_documents({}) == n + 1
    siap["kas_d"] = k["id"]


async def test_U05_kas_manual_bisa_dibatalkan(klien, siap):
    r = await klien.post(f"/api/cash-transactions/{siap['kas_d']}/void", headers=siap["akb"],
                         json={"reason": "uji coba"})
    assert r.status_code == 200, r.text


async def test_U06_kasus_wajib_satu_pt(klien, db, siap):
    from services import finance_case_service as svc
    n = await db.finance_cases.count_documents({})
    with pytest.raises(svc.CaseError, match="Kasus keuangan harus milik satu PT"):
        await svc.create_case({"case_type": "selisih_biaya_bank", "entity_id": ""}, {"name": "uji"}, None, "")
    r = await klien.post("/api/finance-cases", headers=siap["akb"],
                         json={"case_type": "selisih_biaya_bank", "entity_id": A, "amount": 1000})
    assert r.status_code == 403, r.text
    assert await db.finance_cases.count_documents({}) == n
    # pengecualian tunggal: alat migrasi E7e melaporkan uang tanpa pemilik PT — kasus terlihat, tidak bisa diselesaikan
    c = await svc.create_case({"case_type": "salah_entitas", "entity_id": "", "amount": 1000,
                               "source": {"type": "cash_transaction", "id": "kas_pk09_tanpa_pt"}},
                              {"id": "system", "name": "Migrasi E7e"}, None, "", allow_no_entity=True)
    with pytest.raises(svc.CaseError, match="belum punya PT"):
        await svc.assert_case_refs(c, {"action": "settlement_antar_entitas"})
    await db.finance_cases.delete_one({"id": c["id"]})


async def _kasus_b(db, cid, case_type, **extra):
    await db.finance_cases.insert_one({"id": cid, "number": cid.upper(), "entity_id": B, "case_type": case_type,
                                       "status": "in_progress", "customer_id": "cus_b", "amount": 100000,
                                       "documents": [], "attachments": [], "created_at": T, **extra})


@pytest.mark.parametrize("cid,tipe,isi,pesan", [
    ("fcs_b1", "selisih_biaya_bank", {"action": "bebankan_biaya_bank", "order_id": "so_a"}, "bukan milik PT kasus ini"),
    ("fcs_b2", "giro_ditolak", {"action": "batalkan_kwitansi", "receipt_id": "rcp_a"}, "Kwitansi RCP-A bukan milik PT"),
    ("fcs_b3", "rekening_pribadi_karyawan", {"action": "setor_dari_karyawan", "account_id": "ba_a", "amount": 1000},
     "Rekening Bank A bukan milik PT"),
    ("fcs_b4", "refund_pelanggan", {"action": "refund_pelanggan", "customer_id": "cus_a", "amount": 1000},
     "Pelanggan pada permintaan berbeda"),
])
async def test_U07_rujukan_kasus_ke_pt_lain(klien, db, siap, cid, tipe, isi, pesan):
    await _kasus_b(db, cid, tipe, resolution={"extra": {"step": 1, "held_amount": 100000}})
    so0, rcp0 = await db.sales_orders.find_one({"id": "so_a"}, {"_id": 0}), await db.ar_receipts.find_one({"id": "rcp_a"}, {"_id": 0})
    j0 = await _jejak(db)
    r = await klien.post(f"/api/finance-cases/{cid}/resolve", headers=siap["akb"],
                         json={"reason_code": "case_bank_fee", **isi})
    assert r.status_code == 400, r.text
    assert pesan in str(r.json().get("detail")), r.text
    assert await db.sales_orders.find_one({"id": "so_a"}, {"_id": 0}) == so0
    assert await db.ar_receipts.find_one({"id": "rcp_a"}, {"_id": 0}) == rcp0
    assert await _jejak(db) == j0
    assert (await db.finance_cases.find_one({"id": cid}))["status"] == "in_progress"


async def test_U08_settlement_ke_pt_bukan_tugas(klien, db, siap):
    await _kasus_b(db, "fcs_b5", "salah_entitas")
    j0 = await _jejak(db)
    r = await klien.post("/api/finance-cases/fcs_b5/resolve", headers=siap["akb"], json={
        "action": "settlement_antar_entitas", "reason_code": "case_wrong_entity", "owner_entity_id": A,
        "order_id": "so_a", "amount": 1000})
    # Penjaga tulis yang sudah ada (isi `owner_entity_id` di luar penugasan) menolak lebih dulu dengan 403; bila ia
    # tidak ada, `assert_case_refs` menolak 400. Keduanya tanpa tulisan.
    assert r.status_code in (400, 403), r.text
    assert ("Anda tidak ditugaskan di PT pemilik tagihan" in r.text) or ("tidak berwenang menyimpan data" in r.text)
    assert await _jejak(db) == j0


async def test_U09_dokumen_pt_lain_404(klien, db, siap):
    h = siap["akb"]
    snap = {k: await db[c].find_one({"id": k}, {"_id": 0}) for c, k in (
        ("penalties", "pnl_a"), ("payment_plans", "pyp_a"), ("payment_variance_decisions", "pvd_a"),
        ("tax_pph_records", "pphr_a"), ("vendor_bills", "vb_a"), ("tax_invoices_in", "fpm_a"))}
    j0 = await _jejak(db)
    panggilan = [
        ("post", "/api/payment-plans/preview", {"doc_type": "sales_order", "doc_id": "so_a", "mode": "net"}),
        ("post", "/api/payment-plans", {"doc_type": "sales_order", "doc_id": "so_a", "mode": "net"}),
        ("patch", "/api/payment-plans/pyp_a", {"note": "uji"}),
        ("post", "/api/payment-plans/pyp_a/void", {"reason": "uji batal"}),
        ("get", "/api/payment-plans/by-doc/sales_order/so_a", None),
        ("post", "/api/penalties/pnl_a/issue", None),
        ("post", "/api/penalties/pnl_a/waive", {"reason_code": "penalty_waiver", "note": "uji"}),
        ("post", "/api/penalties/pnl_a/adjust", {"amount": 1000, "reason_code": "penalty_negotiation"}),
        ("post", "/api/penalties/pnl_a/pay", {"amount": 1000, "account_id": "ba_a"}),
        ("post", "/api/payment-variances/receipt/rcp_a/decide", {"kind": "write_off", "reason_code": "x"}),
        ("post", "/api/payment-variances/pvd_a/reverse", {"reason": "uji anulir"}),
        ("delete", "/api/tax/pph-records/pphr_a", None),
        ("post", "/api/input-tax-invoices", {"vendor_bill_id": "vb_a", "nsfp": "010.000-26.00000001",
                                             "faktur_date": "2026-11-05"}),
        ("post", "/api/input-tax-invoices/fpm_a/cancel", {"reason": "uji batal"}),
    ]
    kode = []
    for m, path, body in panggilan:
        r = await getattr(klien, m)(path, headers=h, **({"json": body} if body is not None else {}))
        kode.append((path, r.status_code))
    assert all(c == 404 for _, c in kode), kode
    for (c, k), before in zip((("penalties", "pnl_a"), ("payment_plans", "pyp_a"),
                               ("payment_variance_decisions", "pvd_a"), ("tax_pph_records", "pphr_a"),
                               ("vendor_bills", "vb_a"), ("tax_invoices_in", "fpm_a")), snap.values()):
        assert await db[c].find_one({"id": k}, {"_id": 0}) == before, k
    assert await _jejak(db) == j0


async def test_U10_kueri_pt_lain_403(klien, siap):
    h, q = siap["akb"], {"entity_id": A}
    hasil = [
        await klien.get("/api/payment-plans/meta", headers=h, params=q),
        await klien.get("/api/payment-variances/meta", headers=h, params=q),
        await klien.get("/api/tax/summary", headers=h, params=q),
        await klien.get("/api/tax/pph-records", headers=h, params=q),
        await klien.post("/api/tax/pph-records", headers=h, json={"entity_id": A, "period": "2026-11", "code": "pph23",
                                                                  "name": "PPh 23", "rate": 2, "dpp": 100000}),
        await klien.get("/api/input-tax-invoices/eligible-bills", headers=h, params=q),
        await klien.get("/api/tax/vat-summary", headers=h, params=q),
    ]
    assert [r.status_code for r in hasil] == [403] * 7, [r.text[:80] for r in hasil]


async def test_U11_gabungan_pajak_hanya_pt_ditugaskan(klien, db, kepala_admin, siap):
    # TX-T2 — rekap PPN keluaran kini hanya menjumlah faktur TERBIT (`normal`/`pengganti`); fixture lama memakai status
    # "issued" yang tidak pernah ditulis layanan faktur → disamakan dengan status nyata faktur terbit (`normal`).
    await db.tax_invoices.insert_many([
        {"id": "fk_a", "entity_id": A, "status": "normal", "faktur_date": "2026-11-05", "ppn_amount": 110000, "dpp": 1000000},
        {"id": "fk_b", "entity_id": B, "status": "normal", "faktur_date": "2026-11-06", "ppn_amount": 55000, "dpp": 500000}])
    q = {"entity_id": "all", "period": "2026-11"}
    r = await klien.get("/api/tax/summary", headers=siap["akb"], params=q)
    assert r.status_code == 200, r.text
    assert r.json()["ppn"]["keluaran"]["ppn"] == 55000
    r = await klien.get("/api/tax/summary", headers={**kepala_admin, "X-Entity-Id": "all"}, params=q)
    assert r.status_code == 200, r.text
    assert r.json()["ppn"]["keluaran"]["ppn"] == 165000


async def test_U12_aksi_antar_pt_pihak_lain_404(klien, db, siap):
    h, base = siap["akb"], "/api/interco/transactions/ict_ac"
    j0 = await _jejak(db)
    panggilan = [("confirm", {"note": ""}), ("ship", {"note": ""}), ("receive", {"note": ""}), ("invoice", {"note": ""}),
                 ("cancel", {"note": ""}), ("warehouse-task", {"note": ""}), ("tax-invoice", {"nsfp": ""}),
                 ("tax-invoice/replace", {"reason": "uji"}), ("tax-invoice/cancel", {"reason": "uji"})]
    kode = [(a, (await klien.post(f"{base}/{a}", headers=h, json=b)).status_code) for a, b in panggilan]
    assert all(c == 404 for _, c in kode), kode
    assert (await db.interco_transactions.find_one({"id": "ict_ac"}))["status"] == "draft"
    assert await _jejak(db) == j0


async def test_U13_baca_antar_pt_pihak_lain_404(klien, siap):
    h, c = siap["akb"], siap["c"]
    hasil = [
        await klien.get("/api/interco/transactions/ict_ac/journal", headers=h),
        await klien.get("/api/interco/transactions/ict_ac/tax-invoice", headers=h),
        await klien.get("/api/interco/transactions/ict_ac/returnable", headers=h),
        await klien.post("/api/interco/returns", headers=h, json={"interco_id": "ict_ac", "items": [], "reason": "uji"}),
        await klien.get("/api/interco/returns/icr_ac", headers=h),
        await klien.get(f"/api/interco/accounts/{A}/{c}", headers=h),
        await klien.post(f"/api/interco/accounts/{A}/{c}/remind", headers=h, json={"note": ""}),
        await klien.get("/api/interco/settlements/ics_ac", headers=h),
    ]
    assert [r.status_code for r in hasil] == [404] * 8, [r.text[:80] for r in hasil]
    r = await klien.get("/api/interco/contracts", headers=h, params={"seller_entity_id": A})
    assert r.status_code == 200 and r.json() == [], r.text


async def test_U14_pihak_sendiri_tetap_boleh(klien, siap):
    h = siap["aka"]
    assert (await klien.get("/api/interco/transactions/ict_ac", headers=h)).status_code == 200
    assert (await klien.get("/api/interco/transactions/ict_ac/journal", headers=h)).status_code == 200
    r = await klien.post("/api/interco/transactions/ict_ac/confirm", headers=h, json={"note": ""})
    assert r.status_code != 404, r.text


async def test_U15_eliminasi(klien, db, siap):
    h = siap["akb"]
    r = await klien.get("/api/finance/consolidation/eliminations", headers=h)
    assert r.status_code == 200, r.text
    assert "elim_ac" not in {x["id"] for x in r.json()}
    r = await klien.delete("/api/finance/consolidation/eliminations/elim_ac", headers=h)
    assert r.status_code == 404, r.text
    assert await db.intercompany_eliminations.find_one({"id": "elim_ac"})
    r = await klien.post("/api/finance/consolidation/eliminations", headers=h, json={
        "entity_from": A, "entity_to": B, "lines": [{"account_code": "1-1250", "debit": 0, "credit": 1000},
                                                    {"account_code": "2-1250", "debit": 1000, "credit": 0}]})
    assert r.status_code == 403, r.text


async def test_U16_ubah_jadwal_simpan_riwayat(klien, db, siap):
    r = await klien.patch("/api/payment-plans/pyp_b", headers=siap["akb"], json={
        "reason": "pelanggan minta mundur", "lines": [
            {"kind": "dp", "label": "DP", "amount": 400000, "due_date": "2026-11-10", "paid_amount": 0,
             "status": "open"},
            {"kind": "installment", "label": "Pelunasan", "amount": 600000, "due_date": "2027-01-10"}]})
    assert r.status_code == 200, r.text
    p = await db.payment_plans.find_one({"id": "pyp_b"})
    assert p["lines"][0]["paid_amount"] == 400000
    assert p["lines"][1]["due_date"] == "2027-01-10"
    assert len(p["schedule_history"]) == 1
    h = p["schedule_history"][0]
    assert h["reason"] == "pelanggan minta mundur" and h["by"] == siap["nama_b"]
    assert h["lines_before"][1]["due_date"] == "2026-12-10"
