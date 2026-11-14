"""PK-39 (FY-10, FY-11, FY-12) — angka anggaran: realisasi, komitmen, per PT, pagu unik, riwayat pagu.

U1–U7, U9, U16 dari `docs/blueprint/unit/PK-39.md`. PO, jurnal, dan LPJ disisipkan sebagai FIXTURE (jurnal lewat
`gl_service._insert_entry` dengan `source_type` aslinya); pagu dibuat lewat API (ALUR). Tiap tes mulai dari data bersih
(`_bersih`) supaya merah/hijau sendiri. U8 (dua POST bersamaan) hanya sah di MongoDB asli:
`backend/tests/test_bp_PK39_pagu_kembar.py`.

Hitungan tangan dasar (U1): PO 10 unit × Rp 10 = nilai dipesan 100, `net_subtotal` 100, diterima 4 unit → nilai diterima
4 × 10 = 40. Sisa PO = 100 × (1 − 40/100) = 60 (komitmen). Jurnal penerimaan Dr 1-1300 40 (realisasi). Terpakai = 40 + 60
= 100; sisa pagu = 150 − 100 = 50.
"""
import pytest

from services import gl_service as gl

KSC, KANDA = "ent_ksc", "ent_kanda"
TAHUN = 2026
PERSEDIAAN, GRIR, HPP, HUTANG = "1-1300", "2-1150", "5-1000", "2-1100"
SEWA, KAS, UANG_MUKA, BEBAN_TRANSPORT = "6-2000", "1-1100", "1-1400", "6-4600"
KATEGORI = "transportasi"   # kode kategori beban nyata (spesifikasi menulis "transport")


async def _bersih(db):
    for koleksi, saring in (("budgets", {}), ("budget_history", {}), ("purchase_orders", {"id": {"$regex": "^po_pk39"}}),
                            ("journal_entries", {"source_id": {"$regex": "^pk39"}}),
                            ("cash_advance_settlements", {"id": {"$regex": "^pk39"}})):
        await db[koleksi].delete_many(saring)


async def _pagu(klien, h, key, amount, *, month=0, dimension="account", entity=None):
    body = {"year": TAHUN, "month": month, "dimension": dimension, "key": key, "amount": amount}
    if entity:
        body["entity_id"] = entity
    r = await klien.post("/api/finance/budgets", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


async def _jurnal(eid, tanggal, baris, source_type, source_id):
    return await gl._insert_entry(
        lines=[{"account_code": k, "debit": d, "credit": c, "description": "uji PK-39"} for k, d, c in baris],
        description=f"uji PK-39 {source_type}", date=tanggal, source_type=source_type, source_id=source_id,
        entity_id=eid, created_by="uji")


async def _po_u1(db, status="partial"):
    """Fixture U1: PO 10 × 10, diterima 4, `net_subtotal` 100 + jurnal penerimaan Dr 1-1300 40 / Cr GR-IR 40."""
    await db.purchase_orders.insert_one({
        "id": "po_pk39_u1", "po_number": "PO-PK39-1", "entity_id": KSC, "status": status,
        "supplier_name": "Pemasok Uji PK39", "net_subtotal": 100.0, "total_amount": 100.0, "grand_total": 100.0,
        "items": [{"product_id": "prd_pk39", "quantity": 10, "price": 10, "received_qty": 4}],
        "expected_delivery_date": "2026-08-15", "created_at": "2026-08-01T03:00:00+00:00"})
    await _jurnal(KSC, "2026-08-10", [(PERSEDIAAN, 40, 0), (GRIR, 0, 40)], "goods_receipt", "pk39_gr_1")


async def _laporan(klien, h, **params):
    r = await klien.get("/api/finance/budget-vs-actual", headers=h, params={"year": TAHUN, **params})
    assert r.status_code == 200, r.text
    return r.json()


def _baris(rep, key, entity=KSC):
    return next(r for r in rep["rows"] if r["key"] == key and r.get("entity_id", entity) == entity)


# ── U1 — PO diterima sebagian (`partial`): sisa PO tetap komitmen ───────────────────────────────────────────────────
async def test_PK39_U1_po_sebagian_sisa_jadi_komitmen(klien, db, kepala_admin):
    await _bersih(db)
    await _pagu(klien, kepala_admin, PERSEDIAAN, 150)
    await _po_u1(db, "partial")
    b = _baris(await _laporan(klien, kepala_admin), PERSEDIAAN)
    # realisasi 40 · komitmen 100 × (1 − 40/100) = 60 · terpakai 100 · sisa 150 − 100 = 50
    assert (b["actual"], b["committed"], b["spent"], b["remaining"]) == (40, 60, 100, 50), b


# ── U2 — PO `receiving` tidak dihitung dua kali ──────────────────────────────────────────────────────────────────────
async def test_PK39_U2_po_sedang_diterima_tidak_dihitung_dua_kali(klien, db, kepala_admin):
    await _bersih(db)
    await _pagu(klien, kepala_admin, PERSEDIAAN, 150)
    await _po_u1(db, "receiving")
    b = _baris(await _laporan(klien, kepala_admin), PERSEDIAAN)
    # sebelum unit: komitmen = net_subtotal penuh 100 → terpakai 140
    assert (b["actual"], b["committed"], b["spent"], b["remaining"]) == (40, 60, 100, 50), b


# ── U3 — HPP mengkredit persediaan, bukan belanja yang berkurang ─────────────────────────────────────────────────────
async def test_PK39_U3_hpp_tidak_mengurangi_realisasi_persediaan(klien, db, kepala_admin):
    await _bersih(db)
    await _pagu(klien, kepala_admin, PERSEDIAAN, 150)
    await _po_u1(db)
    await _jurnal(KSC, "2026-08-20", [(HPP, 30, 0), (PERSEDIAAN, 0, 30)], "shipment_cogs", "pk39_cogs_1")
    b = _baris(await _laporan(klien, kepala_admin), PERSEDIAAN)
    assert b["actual"] == 40, b   # sebelum unit: 40 − 30 = 10


# ── U4 — retur beli mengurangi realisasi persediaan (HPP tetap diabaikan) ────────────────────────────────────────────
async def test_PK39_U4_retur_beli_mengurangi_realisasi(klien, db, kepala_admin):
    """Spesifikasi: "U1 + retur → 35". Dengan U1 saja kode lama juga 35 (debit − kredit), jadi uji ini memakai keadaan
    U3 (HPP 30 sudah ada) seperti urutan tabel: baru = 40 − 5 = 35; lama = 40 − 30 − 5 = 5."""
    await _bersih(db)
    await _pagu(klien, kepala_admin, PERSEDIAAN, 150)
    await _po_u1(db)
    await _jurnal(KSC, "2026-08-20", [(HPP, 30, 0), (PERSEDIAAN, 0, 30)], "shipment_cogs", "pk39_cogs_1")
    await _jurnal(KSC, "2026-08-25", [(HUTANG, 5, 0), (PERSEDIAAN, 0, 5)], "purchase_return", "pk39_pret_1")
    b = _baris(await _laporan(klien, kepala_admin), PERSEDIAAN)
    assert b["actual"] == 35, b


# ── U5 — LPJ dihitung pada bulan jurnalnya, bukan teks `periode` ─────────────────────────────────────────────────────
async def test_PK39_U5_lpj_pada_bulan_jurnal(klien, db, kepala_admin):
    await _bersih(db)
    await _pagu(klien, kepala_admin, KATEGORI, 300_000, month=8, dimension="category")
    await db.cash_advance_settlements.insert_one({
        "id": "pk39_stl_u5", "number": "STL-PK39-5", "entity_id": KSC, "status": "posted_to_gl",
        "periode": "Juli 2026", "category_totals": {KATEGORI: 250_000.0}, "total_pengeluaran": 250_000.0,
        "created_at": "2026-07-30T02:00:00+00:00"})
    await _jurnal(KSC, "2026-08-03", [(BEBAN_TRANSPORT, 250_000, 0), (UANG_MUKA, 0, 250_000)],
                  "petty_cash_settlement", "pk39_stl_u5")
    b = _baris(await _laporan(klien, kepala_admin), KATEGORI)
    assert (b["month"], b["actual"]) == (8, 250_000), b   # sebelum unit: "Juli 2026" → tahun 0 → hilang (0)


# ── U6 — mode gabungan: tiap PT dibandingkan dengan pagunya sendiri ──────────────────────────────────────────────────
async def test_PK39_U6_gabungan_per_pt(klien, db, kepala_admin):
    await _bersih(db)
    await _pagu(klien, kepala_admin, SEWA, 100, entity=KSC)
    await _pagu(klien, kepala_admin, SEWA, 100, entity=KANDA)
    await _jurnal(KSC, "2026-03-10", [(SEWA, 80, 0), (KAS, 0, 80)], "uji", "pk39_sewa_ksc")
    await _jurnal(KANDA, "2026-03-10", [(SEWA, 10, 0), (KAS, 0, 10)], "uji", "pk39_sewa_kanda")
    rep = await _laporan(klien, kepala_admin, entity_id="all")
    sewa = sorted((r for r in rep["rows"] if r["key"] == SEWA), key=lambda r: r.get("entity_id", ""))
    # sebelum unit: kedua baris berealisasi 80 + 10 = 90 dan tanpa `entity_id`
    assert [(r.get("entity_id"), r["actual"]) for r in sewa] == [(KANDA, 10), (KSC, 80)], sewa
    assert all(r.get("entity_name") for r in sewa), sewa
    assert rep["totals"]["actual"] == 90
    assert rep.get("is_combined") is True
    assert rep.get("combined_note") == "Penjumlahan pagu dan realisasi tiap PT; transaksi antar-PT belum dieliminasi."
    # satu PT tetap satu hitungan, tanpa tanda gabungan
    tunggal = await _laporan(klien, kepala_admin, entity_id=KSC)
    assert _baris(tunggal, SEWA)["actual"] == 80 and tunggal.get("is_combined") is False


# ── U7 — pagu kembar ditolak 409 ─────────────────────────────────────────────────────────────────────────────────────
async def test_PK39_U7_pagu_kembar_409(klien, db, kepala_admin):
    await _bersih(db)
    await _pagu(klien, kepala_admin, SEWA, 100)
    r = await klien.post("/api/finance/budgets", headers=kepala_admin,
                         json={"year": TAHUN, "month": 0, "dimension": "account", "key": SEWA, "amount": 200})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == ("Pagu untuk PT, tahun, bulan, dan akun/kategori ini sudah ada. Ubah pagu yang ada.")
    assert await db.budgets.count_documents({"entity_id": KSC, "year": TAHUN, "month": 0, "key": SEWA}) == 1


async def test_PK39_U7b_indeks_unik_terdaftar_wajib():
    import indexes
    it = next((x for x in indexes.REQUIRED_UNIQUE_INDEXES if x["name"] == "uq_budget_key"), None)
    assert it is not None and it["collection"] == "budgets"
    assert [k for k, _ in it["keys"]] == ["entity_id", "year", "month", "dimension", "key"]
    assert "db.budgets.aggregate" in it["finder"]


# ── U9 — setiap perubahan pagu berbekas (sebelum/sesudah, alasan) ───────────────────────────────────────────────────
async def test_PK39_U9_riwayat_pagu(klien, db, kepala_admin):
    await _bersih(db)
    b = await _pagu(klien, kepala_admin, SEWA, 100)
    r = await klien.patch(f"/api/finance/budgets/{b['id']}", headers=kepala_admin,
                          json={"amount": 150, "reason": "revisi triwulan"})
    assert r.status_code == 200 and r.json()["amount"] == 150, r.text
    r = await klien.get(f"/api/finance/budgets/{b['id']}/history", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert [x["action"] for x in r.json()] == ["updated", "created"]
    r = await klien.delete(f"/api/finance/budgets/{b['id']}", headers=kepala_admin, params={"reason": "salah akun"})
    assert r.status_code == 200, r.text
    r = await klien.get(f"/api/finance/budgets/{b['id']}/history", headers=kepala_admin)
    assert r.status_code == 200, r.text
    hist = r.json()
    assert [x["action"] for x in hist] == ["deleted", "updated", "created"], hist
    hapus, ubah, buat = hist
    assert ubah["before"]["amount"] == 100 and ubah["after"]["amount"] == 150 and ubah["reason"] == "revisi triwulan"
    assert hapus["before"]["amount"] == 150 and not hapus["after"] and hapus["reason"] == "salah akun"
    assert buat["after"]["amount"] == 100 and buat["entity_id"] == KSC and buat["by"]
    assert set(ubah["before"]) == {"amount", "year", "month", "note"}
    # jejak audit memuat nilai sebelum/sesudah
    log = await db.audit_logs.find_one({"action": "budget_updated", "entity_id": b["id"]}, {"_id": 0})
    assert log and (log.get("before") or {}).get("amount") == 100 and log["after"]["amount"] == 150, log
    assert log.get("reason") == "revisi triwulan"
    r = await klien.get("/api/finance/budgets/budget_tidak_ada/history", headers=kepala_admin)
    assert r.status_code == 404 and r.json()["detail"] == "Pagu tidak ditemukan."


# ── U16 — riwayat cukup izin lihat; ubah tetap butuh izin ubah ──────────────────────────────────────────────────────
async def test_PK39_U16_riwayat_berizin_lihat(klien, db, kepala_admin, akun, sesi, peran_tanpa_acuan):
    await _bersih(db)
    b = await _pagu(klien, kepala_admin, SEWA, 100)
    rid = await peran_tanpa_acuan({"budget": ["view"]}, label="Lihat Anggaran PK39")
    h = await sesi(await akun(rid))
    r = await klien.get(f"/api/finance/budgets/{b['id']}/history", headers=h)
    assert r.status_code == 200, r.text
    r = await klien.patch(f"/api/finance/budgets/{b['id']}", headers=h, json={"amount": 120, "reason": "x"})
    assert r.status_code == 403, r.text


# ── tambahan: sisa PO (fungsi murni) ─────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("items, harapan", [
    ([{"quantity": 10, "price": 10, "received_qty": 4}], 60.0),          # U1
    ([{"quantity": 10, "price": 10, "received_qty": 12}], 0.0),          # terima lebih → dibatasi pesanan → 0
    ([{"quantity": 10, "price": 10, "received_qty": 0},
      {"quantity": 5, "price": 20, "received_qty": 5}], 50.0),           # 100 × (1 − 100/200)
])
def test_PK39_sisa_po(items, harapan):
    from services.budget_service import po_open_value
    assert po_open_value({"net_subtotal": 100.0, "items": items}) == harapan


def test_PK39_status_po_tertutup_sama_dengan_router():
    """PO terbuka = status di luar status akhir router PO (satu daftar; `partial` dan `receiving` terbuka)."""
    from routers.purchase_orders import TERMINAL_PO_STATUSES
    from services.budget_service import CLOSED_PO_STATUSES
    assert set(CLOSED_PO_STATUSES) == set(TERMINAL_PO_STATUSES)
    assert "partial" not in CLOSED_PO_STATUSES and "receiving" not in CLOSED_PO_STATUSES
