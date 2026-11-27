"""PK-39 (FY-12, K-12) — cakupan pemeriksaan anggaran: tagihan tanpa PO, kas keluar, LPJ; mode dari Pusat Pengaturan.

U10–U15 dari `docs/blueprint/unit/PK-39.md` (lingkungan B). Pagu dibuat lewat API (ALUR); realisasi awal, tagihan
kampanye, PD, dan LPJ disisipkan sebagai FIXTURE. "Bulan ini" = bulan buku WIB hari ini (`book_date.tanggal_buku`).

Hitungan tangan dasar (U10/U11): pagu bulan ini 1.000.000, realisasi 900.000 → sisa 100.000; transaksi 200.000 →
melampaui 200.000 − 100.000 = 100.000.
"""
from services import gl_service as gl
from services.book_date import tanggal_buku
from services.config_resolver import value_of

KSC, KANDA = "ent_ksc", "ent_kanda"
KUNCI = "budget.mode"
HARI = tanggal_buku()
TAHUN, BULAN = int(HARI[:4]), int(HARI[5:7])
PEMASARAN, SEWA, KAS, UANG_MUKA, BEBAN_TRANSPORT = "6-4700", "6-2000", "1-1100", "1-1400", "6-4600"
KATEGORI = "transportasi"   # kode kategori beban nyata (spesifikasi menulis "transport")


def _isi(value, scope_type="entity", scope_id=KSC, reason="uji PK-39"):
    return {"items": [{"key": KUNCI, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]}


async def _mode(klien, h, value, scope_id=KSC):
    r = await klien.put("/api/config/values", headers=h, json=_isi(value, scope_id=scope_id))
    assert r.status_code == 200, r.text


async def _pulihkan(klien, h, *pt):
    for eid in pt:
        r = await klien.post("/api/config/values/clear", headers=h,
                             json={"key": KUNCI, "scope_type": "entity", "scope_id": eid, "reason": "pulihkan"})
        assert r.status_code == 200, r.text


async def _bersih(db):
    for koleksi, saring in (("budgets", {}), ("journal_entries", {"source_id": {"$regex": "^pk39"}}),
                            ("vendor_bills", {"id": {"$regex": "^pk39"}}),
                            ("cash_advance_settlements", {"id": {"$regex": "^pk39"}}),
                            ("cash_advances", {"id": {"$regex": "^pk39"}}), ("fin_budget_rules", {})):
        await db[koleksi].delete_many(saring)
    await db.cash_transactions.delete_many({"category": "sewa"})
    await db.journal_entries.delete_many({"source_type": "cash_transaction"})
    # PK-20 — kas wajib berekening: fixture satu rekening Kas Kecil milik KSC (rekening tunggal → dipakai otomatis).
    if not await db.bank_accounts.find_one({"id": "rek_pk39_k"}):
        await db.bank_accounts.insert_one({"id": "rek_pk39_k", "name": "Kas Kecil KSC (uji PK-39)", "entity_id": KSC,
                                           "account_type": "cash", "cash_type": "kas_kecil", "is_active": True})


async def _pagu(klien, h, key, amount, *, dimension="account", entity=KSC):
    r = await klien.post("/api/finance/budgets", headers=h, json={
        "year": TAHUN, "month": BULAN, "dimension": dimension, "key": key, "amount": amount, "entity_id": entity})
    assert r.status_code == 200, r.text
    return r.json()


async def _realisasi(eid, akun, nilai, sid):
    await gl._insert_entry(lines=[{"account_code": akun, "debit": nilai, "credit": 0, "description": "uji"},
                                  {"account_code": KAS, "debit": 0, "credit": nilai, "description": "uji"}],
                           description="realisasi awal PK-39", date=HARI, source_type="uji", source_id=sid,
                           entity_id=eid, created_by="uji")


async def _tagihan_kampanye(db, bid, eid):
    await db.vendor_bills.insert_one({
        "id": bid, "bill_number": f"TGH-{bid[-6:]}", "bill_type": "campaign_expense", "po_id": "", "entity_id": eid,
        "supplier_id": "sup_pk39", "supplier_name": "Vendor Iklan PK39", "campaign_id": "cmp_pk39",
        "campaign_name": "Kampanye PK39", "expense_account_code": PEMASARAN, "bill_date": HARI,
        "items": [{"product_name": "Iklan", "quantity": 1, "price": 200_000, "subtotal": 200_000}],
        "total_amount": 200_000.0, "net_subtotal": 200_000.0, "dpp": 200_000.0, "ppn_amount": 0.0,
        "grand_total": 200_000.0, "status": "pending_approval", "approval_status": "pending",
        "created_by": "Marketing Uji", "created_by_id": "usr_marketing_pk39", "timeline": [], "created_at": HARI})


# ── U10 — tagihan tanpa PO: mode tolak di satu PT, PT lain bawaan (peringatkan) ─────────────────────────────────────
async def test_PK39_U10_tagihan_kampanye_tolak_vs_peringatkan(klien, db, kepala_admin, sesi):
    await _bersih(db)
    await _mode(klien, kepala_admin, "blokir", KSC)
    h_kanda = await sesi("admin@kainnusantara.id", entitas=KANDA)
    try:
        for eid in (KSC, KANDA):
            await _pagu(klien, kepala_admin, PEMASARAN, 1_000_000, entity=eid)
            await _realisasi(eid, PEMASARAN, 900_000, f"pk39_real_{eid}")
        await _tagihan_kampanye(db, "pk39_vb_ksc", KSC)
        await _tagihan_kampanye(db, "pk39_vb_kanda", KANDA)
        r = await klien.post("/api/vendor-bills/pk39_vb_ksc/approve", headers=kepala_admin)
        assert r.status_code == 400 and r.json()["detail"].startswith("Anggaran terlampaui"), r.text
        doc = await db.vendor_bills.find_one({"id": "pk39_vb_ksc"}, {"_id": 0})
        assert doc["status"] == "pending_approval" and doc.get("approval_status") == "pending", doc
        assert await db.journal_entries.count_documents({"source_type": "vendor_bill", "source_id": "pk39_vb_ksc"}) == 0
        r = await klien.post("/api/vendor-bills/pk39_vb_kanda/approve", headers=h_kanda)
        assert r.status_code == 200, r.text
        cek = r.json()["budget_check"]
        assert cek["when"] == "bill_approve" and cek["mode"] == "warn" and len(cek["warnings"]) == 1, cek
        assert "Rp 100.000" in cek["warnings"][0], cek
        tersimpan = await db.vendor_bills.find_one({"id": "pk39_vb_kanda"}, {"_id": 0})
        assert tersimpan["status"] == "posted" and tersimpan["budget_check"]["warnings"] == cek["warnings"]
    finally:
        await _pulihkan(klien, kepala_admin, KSC)


# ── U11 — kas keluar manual: peringatkan lalu tolak ──────────────────────────────────────────────────────────────────
async def _kas_sewa(klien, h):
    return await klien.post("/api/cash-transactions", headers=h, json={
        "cash_type": "kas_kecil", "direction": "out", "amount": 200_000, "category": "sewa",
        "description": "Sewa gudang PK39", "txn_date": HARI})


async def test_PK39_U11_kas_keluar_peringatkan_lalu_tolak(klien, db, kepala_admin):
    await _bersih(db)
    await _pagu(klien, kepala_admin, SEWA, 1_000_000)
    await _realisasi(KSC, SEWA, 900_000, "pk39_real_sewa")
    r = await _kas_sewa(klien, kepala_admin)                      # bawaan = peringatkan
    assert r.status_code == 200, r.text
    cek = r.json()["budget_check"]
    assert cek["when"] == "cash_out" and cek["warnings"] and not cek["blocked"], cek
    assert cek["checks"][0]["key"] == SEWA and cek["checks"][0]["over_amount"] == 100_000, cek   # 200.000 − sisa 100.000
    await _mode(klien, kepala_admin, "blokir", KSC)
    try:
        n0 = await db.cash_transactions.count_documents({})
        r = await _kas_sewa(klien, kepala_admin)
        assert r.status_code == 400 and r.json()["detail"].startswith("Anggaran terlampaui"), r.text
        assert await db.cash_transactions.count_documents({}) == n0
    finally:
        await _pulihkan(klien, kepala_admin, KSC)


async def test_PK39_U11b_kas_keluar_ke_akun_tanpa_pagu_tidak_diperiksa(klien, db, kepala_admin):
    """Kas keluar manual ke akun yang tidak punya pagu → tidak ada pemeriksaan anggaran. (Kategori "pembelian" — lawan
    akun persediaan — sudah ditutup di kas manual baru oleh KB-2 C5, jadi uji ini memakai "operasional" tanpa pagu.)"""
    await _bersih(db)
    r = await klien.post("/api/cash-transactions", headers=kepala_admin, json={
        "cash_type": "kas_kecil", "direction": "out", "amount": 1000, "category": "operasional",
        "description": "Belanja kecil PK39", "txn_date": HARI})
    assert r.status_code == 200, r.text
    cek = r.json()["budget_check"]
    assert not cek["warnings"] and not cek["blocked"], cek       # tanpa pagu → tidak ada peringatan/penolakan


# ── U12 — LPJ: ajukan hanya diperingatkan; setujui ditolak ───────────────────────────────────────────────────────────
async def _lpj(db, sid, status, nilai=400_000):
    ca = f"pk39_ca_{sid}"
    await db.cash_advances.insert_one({"id": ca, "number": f"PD-{sid}", "entity_id": KSC, "status": "disbursed",
                                       "total_amount": nilai, "created_at": HARI})
    await db.cash_advance_settlements.insert_one({
        "id": sid, "number": f"STL-{sid[-4:]}", "entity_id": KSC, "cash_advance_id": ca, "cash_advance_number": f"PD-{sid}",
        "status": status, "category_totals": {KATEGORI: float(nilai)}, "total_pengeluaran": float(nilai),
        "total_pettycash": float(nilai), "expense_lines": [{"category": KATEGORI, "amount": float(nilai)}],
        "created_by": "Staf Uji", "created_by_id": "usr_staf_pk39", "created_at": f"{HARI}T02:00:00+00:00"})


async def test_PK39_U12_lpj_ajukan_diperingatkan_setujui_ditolak(klien, db, kepala_admin):
    await _bersih(db)
    await _pagu(klien, kepala_admin, KATEGORI, 300_000, dimension="category")
    await _lpj(db, "pk39_stl_a", "submitted")
    await _lpj(db, "pk39_stl_b", "draft")
    await _mode(klien, kepala_admin, "blokir", KSC)
    try:
        r = await klien.post("/api/cash-advance-settlements/pk39_stl_b/submit", headers=kepala_admin)
        assert r.status_code == 200, r.text
        cek = r.json()["budget_check"]
        assert cek["when"] == "lpj_submit" and cek["warnings"] and cek["blocked"] is False, cek
        assert (await db.cash_advance_settlements.find_one({"id": "pk39_stl_b"}))["status"] == "submitted"
        r = await klien.post("/api/cash-advance-settlements/pk39_stl_a/approve", headers=kepala_admin)
        assert r.status_code == 400 and r.json()["detail"].startswith("Anggaran terlampaui"), r.text
        assert (await db.cash_advance_settlements.find_one({"id": "pk39_stl_a"}))["status"] == "submitted"
        assert (await db.cash_advances.find_one({"id": "pk39_ca_pk39_stl_a"})).get("settling_stl_id") is None
        assert await db.journal_entries.count_documents({"source_type": "petty_cash_settlement",
                                                         "source_id": "pk39_stl_a"}) == 0
    finally:
        await _pulihkan(klien, kepala_admin, KSC)


async def test_PK39_U12b_lpj_disetujui_menyimpan_pemeriksaan(klien, db, kepala_admin):
    """Mode bawaan (peringatkan): persetujuan jalan, hasil pemeriksaan tersimpan di LPJ dan jawaban."""
    await _bersih(db)
    await _pagu(klien, kepala_admin, KATEGORI, 300_000, dimension="category")
    await _lpj(db, "pk39_stl_c", "submitted")
    r = await klien.post("/api/cash-advance-settlements/pk39_stl_c/approve", headers=kepala_admin)
    assert r.status_code == 200, r.text
    cek = r.json()["budget_check"]
    assert cek["when"] == "lpj_approve" and len(cek["warnings"]) == 1 and "Rp 100.000" in cek["warnings"][0], cek
    assert r.json()["status"] == "posted_to_gl"


# ── U13 — mode mati: lewati pemeriksaan ──────────────────────────────────────────────────────────────────────────────
async def test_PK39_U13_mode_mati_lewati(klien, db, kepala_admin):
    await _bersih(db)
    await _pagu(klien, kepala_admin, SEWA, 1_000_000)
    await _realisasi(KSC, SEWA, 900_000, "pk39_real_sewa")
    await _mode(klien, kepala_admin, "mati", KSC)
    try:
        r = await _kas_sewa(klien, kepala_admin)
        assert r.status_code == 200, r.text
        assert r.json()["budget_check"]["skipped"] is True and r.json()["budget_check"]["mode"] == "off"
    finally:
        await _pulihkan(klien, kepala_admin, KSC)


# ── U14 — mode lama di `fin_budget_rules` dipakai sampai lapisan PT diisi; PUT mode ditolak ─────────────────────────
async def test_PK39_U14_mode_lama_dan_put_ditolak(klien, db, kepala_admin):
    await _bersih(db)
    await db.fin_budget_rules.insert_one({"id": "bgrule_pk39", "entity_id": KANDA, "mode": "block",
                                          "warn_threshold_pct": 85.0, "unbudgeted_action": "allow"})
    r = await klien.get("/api/finance/budget-rules", headers=kepala_admin, params={"entity_id": KANDA})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "block" and r.json().get("mode_source"), r.json()
    assert await value_of(KUNCI, {"entity_id": KANDA}) == "blokir"           # mesin & Pusat Pengaturan sama
    assert await value_of(KUNCI, {"entity_id": KSC}) == "peringatan"
    r = await klien.put("/api/finance/budget-rules", headers=kepala_admin, json={"entity_id": KANDA, "mode": "warn"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"].startswith("Mode anggaran sekarang diatur di Pusat Pengaturan"), r.text
    # sakelar lain tetap bisa disimpan lewat layar Anggaran
    r = await klien.put("/api/finance/budget-rules", headers=kepala_admin,
                        json={"entity_id": KANDA, "warn_threshold_pct": 90})
    assert r.status_code == 200 and r.json()["warn_threshold_pct"] == 90 and r.json()["mode"] == "block", r.text
    # lapisan PT diisi → nilai baru menang atas nilai lama
    await _mode(klien, kepala_admin, "peringatan", KANDA)
    try:
        r = await klien.get("/api/finance/budget-rules", headers=kepala_admin, params={"entity_id": KANDA})
        assert r.json()["mode"] == "warn" and r.json()["mode_source"] == "Khusus PT", r.json()
    finally:
        await _pulihkan(klien, kepala_admin, KANDA)


# ── U15 — putaran t1_config untuk `budget.mode` ──────────────────────────────────────────────────────────────────────
async def test_PK39_U15_putaran_t1_config(klien, kepala_admin):
    import config_registry as registry
    e = registry.require(KUNCI)
    assert (e["type"], e["default"], e["scopes"], e["permission"]) == ("enum", "peringatan", ["global", "entity"],
                                                                         ["budget", "configure"])
    assert [o["value"] if isinstance(o, dict) else o for o in e["options"]] == ["mati", "peringatan", "blokir"]
    assert e["risk"] == "high" and e["requires_reason"] is True and e["status"] == "active"
    assert e["consumers"] == ["services/budget_service.py:get_rules"]
    assert e["label"] == "Bila belanja melampaui anggaran"
    assert await value_of(KUNCI) == "peringatan"
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("blokir", "global", ""))
    assert r.status_code == 200, r.text
    try:
        assert await value_of(KUNCI) == "blokir" and await value_of(KUNCI, {"entity_id": KANDA}) == "blokir"
        r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": KUNCI})
        assert next(i for i in r.json()["items"] if i["key"] == KUNCI)["value"] == "blokir"
        await _mode(klien, kepala_admin, "mati", KANDA)               # lapisan PT → hanya PT itu
        assert await value_of(KUNCI, {"entity_id": KANDA}) == "mati"
        assert await value_of(KUNCI, {"entity_id": KSC}) == "blokir"
        await _pulihkan(klien, kepala_admin, KANDA)
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("keras", "global", ""))
        assert r.status_code == 400, r.text
    finally:
        r = await klien.post("/api/config/values/reset", headers=kepala_admin,
                             json={"key": KUNCI, "scope_type": "global", "reason": "pulihkan"})
        assert r.status_code == 200, r.text
    assert await value_of(KUNCI) == "peringatan"
