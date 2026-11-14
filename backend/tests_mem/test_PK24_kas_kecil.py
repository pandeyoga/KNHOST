"""PK-24 (SL-09, FY-13, FY-14, FY-19, IA-05, K-17) — kas kecil: pengembalian sisa uang muka, LPJ terkunci dan memakai akun
PT-nya, Finance bisa mencairkan, bayar reimburse berizin kas kecil (`docs/blueprint/unit/PK-24.md`, U1–U12 lingkungan B).

Persiapan bersama (FIXTURE): rekening Kas Kecil R-K milik `ent_ksc`; kategori `transportasi` global → 6-4600 dan `atk`
→ 6-4100 (bawaan seed); lapisan `ent_kanda` untuk `transportasi` → 6-4900 (disisipkan SESUDAH baris global). PD
disisipkan berstatus `approved`, lalu DICAIRKAN lewat API (ALUR): kas keluar R-K + jurnal Dr 1-1400 / Cr 1-1110. LPJ
dibuat, diajukan, disetujui, ditolak, dibuka lagi, dan sisa dikembalikan lewat API (ALUR).

Hitungan tangan (U1–U2): PD-1 Rp 1.000.000 dicairkan → Dr 1-1400 1.000.000 / Cr 1-1110 1.000.000. LPJ-1: transportasi
500.000 + ATK 300.000 = 800.000 → Dr 6-4600 500.000, Dr 6-4100 300.000 / Cr 1-1400 800.000; sisa 1.000.000 − 800.000 =
200.000 (`open`). Pengembalian tunai ke R-K → Dr 1-1110 200.000 / Cr 1-1400 200.000. Saldo 1-1400 atas PD-1:
1.000.000 − 800.000 − 200.000 = 0.
"""
import uuid

import pytest

from core_utils import now_iso
from services import config_resolver as resolver
from services import storage_service
from services.book_date import tanggal_buku

KSC, KANDA = "ent_ksc", "ent_kanda"
REK_K = "rek_pk24_k"
REK_K_KANDA = "rek_pk24_k_kanda"
BULAN_INI = tanggal_buku()[:7]
KUNCI_LAMPIRAN = "finance.lpj_wajib_lampiran"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
SISA_TAK_ADA = "tidak punya sisa uang muka yang belum dikembalikan"
SIMPAN: dict = {}   # keadaan berlanjut antar-tes satu modul (loadscope: satu pekerja per modul)


@pytest.fixture(scope="module")
async def siap(db):
    """Rekening Kas Kecil KSC & KANDA (satu-satunya → dipakai otomatis) + lapisan kategori `transportasi` milik KANDA."""
    for rid, eid, nama in ((REK_K, KSC, "Kas Kecil KSC (uji PK-24)"), (REK_K_KANDA, KANDA, "Kas Kecil KANDA (uji PK-24)")):
        if not await db.bank_accounts.find_one({"id": rid}):
            await db.bank_accounts.insert_one({"id": rid, "name": nama, "entity_id": eid, "account_type": "cash",
                                               "cash_type": "kas_kecil", "is_active": True})
    if not await db.expense_categories.find_one({"code": "transportasi", "entity_id": KANDA}):
        await db.expense_categories.insert_one({
            "id": "excat_pk24_kanda", "entity_id": KANDA, "code": "transportasi", "label": "Transportasi (KANDA)",
            "account_code": "6-4900", "sort": 7, "active": True, "created_at": now_iso(), "updated_at": now_iso()})
    return True


@pytest.fixture
def simpan_lokal(monkeypatch, tmp_path):
    """Lampiran ditulis ke folder sementara uji, bukan `backend/uploads`."""
    monkeypatch.setattr(storage_service, "STORAGE_DIR", tmp_path)
    return tmp_path


def _id(awalan):
    return f"{awalan}_pk24_{uuid.uuid4().hex[:8]}"


async def _pd(db, nilai, *, entity=KSC, status="approved", pemohon=None):
    """FIXTURE: PD berstatus `approved` (atau status lain) disisipkan langsung."""
    ca = _id("ca")
    p = pemohon or {"id": "usr_staf_pk24", "name": "Staf PK24"}
    await db.cash_advances.insert_one({
        "id": ca, "number": f"PD-{ca[-8:]}", "entity_id": entity, "status": status, "kegiatan": "uji PK-24",
        "divisi": "Umum", "lines": [{"description": "uang muka", "qty": 1, "unit_price": nilai, "amount": nilai}],
        "total_amount": float(nilai), "approvals": [], "payment_method": "cash",
        "created_by": p["name"], "created_by_id": p["id"], "created_at": now_iso()})
    return ca


async def _pd_cair(klien, db, h, nilai):
    """PD fixture `approved` lalu DICAIRKAN lewat API dari rekening Kas Kecil R-K."""
    ca = await _pd(db, nilai)
    r = await klien.post(f"/api/cash-advances/{ca}/disburse", headers=h,
                         json={"cash_type": "kas_kecil", "account_id": REK_K, "note": "uji PK-24"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "disbursed"
    return ca


async def _lpj(klien, h, ca, baris, *, ajukan=True, periode=""):
    r = await klien.post("/api/cash-advance-settlements", headers=h, json={
        "cash_advance_id": ca, "periode": periode or BULAN_INI,
        "expense_lines": [{"date": tanggal_buku(), "description": f"uji {k}", "category": k, "amount": v}
                          for k, v in baris]})
    assert r.status_code == 200, r.text
    stl = r.json()
    if ajukan:
        r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/submit", headers=h)
        assert r.status_code == 200, r.text
        stl = r.json()
    return stl


async def _jurnal(db, source_type, source_id):
    return await db.journal_entries.find(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}}, {"_id": 0}).to_list(10)


def _baris(je):
    return sorted((ln["account_code"], round(ln["debit"], 2), round(ln["credit"], 2)) for ln in je["lines"])


async def _kas_pencairan(db, ca):
    return await db.cash_transactions.find_one({"ref_type": "cash_advance", "ref_id": ca}, {"_id": 0})


# ── U1–U3 — setujui LPJ memakai akun PT-nya; sisa dikembalikan sampai nol; tidak bisa dikembalikan dua kali ──────────
async def test_PK24_U1_setujui_akun_pt_sendiri_dan_sisa_terbuka(klien, db, kepala_admin, siap):
    ca = await _pd_cair(klien, db, kepala_admin, 1_000_000)
    stl = await _lpj(klien, kepala_admin, ca, [("transportasi", 500_000), ("atk", 300_000)])
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/approve", headers=kepala_admin)
    assert r.status_code == 200, r.text
    d = r.json()
    (je,) = await _jurnal(db, "petty_cash_settlement", stl["id"])
    # 6-4600 = lapisan global; 6-4900 milik ent_kanda TIDAK dipakai untuk LPJ ent_ksc.
    assert _baris(je) == sorted([("6-4600", 500_000, 0), ("6-4100", 300_000, 0), ("1-1400", 0, 800_000)]), je["lines"]
    assert d["status"] == "posted_to_gl" and d["gl_status"] == "posted", d
    assert d["journal_entry_id"] == je["id"]
    sr = d["sisa_dikembalikan"]
    assert (sr["amount"], sr["status"]) == (200_000, "open"), sr
    assert d["approved_by_id"] and d["submitted_by_id"] and d["created_by_id"]
    assert (await db.cash_advances.find_one({"id": ca}))["status"] == "settled"
    SIMPAN["u1"] = (ca, stl["id"])


async def test_PK24_U2_kembalikan_sisa_ke_kas_kecil(klien, db, kepala_admin):
    ca, sid = SIMPAN["u1"]
    r = await klien.post(f"/api/cash-advance-settlements/{sid}/return-remainder", headers=kepala_admin,
                         json={"cash_type": "kas_kecil", "account_id": REK_K})
    assert r.status_code == 200, r.text
    sr = r.json()["sisa_dikembalikan"]
    assert sr["status"] == "returned" and sr["cash_txn_number"] and sr["journal_entry_number"], sr
    kas = await db.cash_transactions.find({"ref_type": "cash_advance_return", "ref_id": sid}, {"_id": 0}).to_list(5)
    assert len(kas) == 1 and kas[0]["direction"] == "in" and kas[0]["amount"] == 200_000, kas
    assert kas[0]["account_id"] == REK_K and kas[0]["entity_id"] == KSC and kas[0]["id"] == sr["cash_txn_id"]
    (je,) = await _jurnal(db, "cash_transaction", kas[0]["id"])
    assert _baris(je) == sorted([("1-1110", 200_000, 0), ("1-1400", 0, 200_000)]), je["lines"]
    # Saldo 1-1400 atas PD-1: pencairan + LPJ + pengembalian = 1.000.000 − 800.000 − 200.000 = 0.
    pencairan = await _jurnal(db, "cash_transaction", (await _kas_pencairan(db, ca))["id"])
    lpj = await _jurnal(db, "petty_cash_settlement", sid)
    saldo = sum(ln["debit"] - ln["credit"] for j in pencairan + lpj + [je] for ln in j["lines"]
                if ln["account_code"] == "1-1400")
    assert round(saldo, 2) == 0


async def test_PK24_U3_kembalikan_lagi_ditolak(klien, db, kepala_admin):
    _, sid = SIMPAN["u1"]
    r = await klien.post(f"/api/cash-advance-settlements/{sid}/return-remainder", headers=kepala_admin,
                         json={"cash_type": "kas_kecil", "account_id": REK_K})
    assert r.status_code == 409 and SISA_TAK_ADA in r.json()["detail"], r.text
    assert await db.cash_transactions.count_documents({"ref_type": "cash_advance_return", "ref_id": sid}) == 1


# ── U4–U5 — LPJ terkunci sesudah diajukan; LPJ draf tidak bisa disetujui ─────────────────────────────────────────────
async def test_PK24_U4_ubah_lpj_diajukan_ditolak(klien, db, kepala_admin, siap):
    ca = await _pd_cair(klien, db, kepala_admin, 400_000)
    stl = await _lpj(klien, kepala_admin, ca, [("transportasi", 300_000)])
    r = await klien.patch(f"/api/cash-advance-settlements/{stl['id']}", headers=kepala_admin, json={
        "expense_lines": [{"date": tanggal_buku(), "description": "ubah", "category": "transportasi", "amount": 50_000}]})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == (f"LPJ {stl['number']} sudah diajukan, jadi isinya tidak bisa diubah. Minta penyetuju "
                                  "menolaknya bila perlu diperbaiki.")
    simpan = await db.cash_advance_settlements.find_one({"id": stl["id"]})
    assert simpan["total_pengeluaran"] == 300_000 and simpan["status"] == "submitted"
    SIMPAN["u4"] = (ca, stl)


async def test_PK24_U4b_lampiran_lpj_diajukan_ditolak(klien, kepala_admin, simpan_lokal):
    _, stl = SIMPAN["u4"]
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/attachments", headers=kepala_admin,
                         files={"file": ("nota.png", PNG, "image/png")})
    assert r.status_code == 409 and "sudah diajukan" in r.json()["detail"], r.text


async def test_PK24_U5_setujui_lpj_draf_ditolak(klien, db, kepala_admin, siap):
    ca = await _pd_cair(klien, db, kepala_admin, 250_000)
    stl = await _lpj(klien, kepala_admin, ca, [("atk", 100_000)], ajukan=False)
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/approve", headers=kepala_admin)
    assert (r.status_code, r.json()["detail"]) == (409, f"LPJ {stl['number']} belum diajukan."), r.text
    pd = await db.cash_advances.find_one({"id": ca})
    assert pd["status"] == "disbursed" and not pd.get("settling_stl_id")
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/reject", headers=kepala_admin, json={"note": "x"})
    assert (r.status_code, r.json()["detail"]) == (409, f"LPJ {stl['number']} belum diajukan."), r.text
    assert await db.journal_entries.count_documents({"source_type": "petty_cash_settlement", "source_id": stl["id"]}) == 0


# ── U6–U7 — periode tertutup tidak menulis apa pun; jurnal gagal tampil di panel lalu diulang ────────────────────────
async def test_PK24_U6_periode_tertutup_tanpa_tulisan(klien, db, kepala_admin, siap, paksa_jurnal_gagal):
    _, stl = SIMPAN["u4"]
    async with paksa_jurnal_gagal("periode", entity_id=KSC, period_key=BULAN_INI):
        r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/approve", headers=kepala_admin)
    assert r.status_code == 409 and "tutup" in r.json()["detail"].lower(), r.text
    assert (await db.cash_advance_settlements.find_one({"id": stl["id"]}))["status"] == "submitted"
    assert not (await db.cash_advances.find_one({"id": stl["cash_advance_id"]})).get("settling_stl_id")
    assert await db.journal_entries.count_documents({"source_type": "petty_cash_settlement", "source_id": stl["id"]}) == 0


async def test_PK24_U7_jurnal_gagal_ke_panel_lalu_diulang(klien, db, kepala_admin, siap, paksa_jurnal_gagal):
    ca, stl = SIMPAN["u4"]
    async with paksa_jurnal_gagal("akun", entity_id=KSC, kode_akun="6-4600"):
        r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/approve", headers=kepala_admin)
        assert r.status_code == 200, r.text
        d = r.json()
        assert (d["status"], d["gl_status"]) == ("approved", "failed") and d["gl_error"], d
        assert (await db.cash_advances.find_one({"id": ca}))["status"] == "disbursed"
        r = await klien.get("/api/finance/posting-failures", headers=kepala_admin,
                            params={"kind": "petty_cash_settlement"})
        assert r.status_code == 200, r.text
        assert [x["id"] for x in r.json()["items"]] == [stl["id"]], r.json()
        assert r.json()["items"][0]["amount"] == 300_000
        # Setujui lagi tidak menerbitkan jurnal kedua: LPJ sudah disetujui.
        r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/approve", headers=kepala_admin)
        assert r.status_code == 409, r.text
    r = await klien.post(f"/api/finance/posting-failures/petty_cash_settlement/{stl['id']}/retry", headers=kepala_admin)
    assert r.status_code == 200, r.text
    d = await db.cash_advance_settlements.find_one({"id": stl["id"]}, {"_id": 0})
    assert (d["status"], d["gl_status"]) == ("posted_to_gl", "posted"), d
    assert len(await _jurnal(db, "petty_cash_settlement", stl["id"])) == 1
    assert d["sisa_dikembalikan"]["amount"] == 100_000 and d["sisa_dikembalikan"]["status"] == "open"
    assert (await db.cash_advances.find_one({"id": ca}))["status"] == "settled"


# ── U8–U10 — izin: Finance membayar reimburse & mencairkan; `cash_settlement.pay` menerima pengembalian ──────────────
async def test_PK24_U8_finance_bayar_reimburse_dengan_rekening(klien, db, kepala_admin, akun, sesi, siap):
    ca = await _pd_cair(klien, db, kepala_admin, 500_000)
    stl = await _lpj(klien, kepala_admin, ca, [("transportasi", 650_000)])
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/approve", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["hutang_reimburse"]["amount"] == 150_000
    assert r.json()["sisa_dikembalikan"]["status"] == "none"
    h_fin = await sesi(await akun("finance"))
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/pay-reimburse", headers=h_fin,
                         json={"cash_type": "kas_kecil", "account_id": REK_K})
    assert r.status_code == 200, r.text
    assert r.json()["hutang_reimburse"]["status"] == "paid"
    kas = await db.cash_transactions.find({"ref_type": "reimburse_payable", "ref_id": stl["id"]}, {"_id": 0}).to_list(5)
    assert len(kas) == 1 and kas[0]["direction"] == "out" and kas[0]["amount"] == 150_000 and kas[0]["account_id"] == REK_K
    (je,) = await _jurnal(db, "cash_transaction", kas[0]["id"])
    assert _baris(je) == sorted([("2-1650", 150_000, 0), ("1-1110", 0, 150_000)]), je["lines"]
    r = await klien.get("/api/cash-advance-settlements/reimburse-payables", headers=h_fin)
    assert r.status_code == 200, r.text


async def test_PK24_U8b_bayar_reimburse_tanpa_izin_pay_ditolak(klien, db, kepala_admin, akun, sesi,
                                                               peran_tanpa_acuan, siap):
    """`accounting.create` saja (penjaga lama) tidak lagi cukup; `cash_settlement.pay` yang menentukan."""
    rid = await peran_tanpa_acuan({"accounting": ["view", "create"], "cash_settlement": ["view"]},
                                  label="Akuntansi Tanpa Bayar Kas Kecil")
    h = await sesi(await akun(rid))
    r = await klien.post("/api/cash-advance-settlements/stl_tidak_ada/pay-reimburse", headers=h, json={})
    assert r.status_code == 403, r.text


async def test_PK24_U9_cairkan_finance_boleh_sales_tidak(klien, db, akun, sesi, siap):
    ca = await _pd(db, 200_000)
    keu = await akun("finance")
    h_sales = await sesi(await akun("sales"))
    r = await klien.post(f"/api/cash-advances/{ca}/disburse", headers=h_sales,
                         json={"cash_type": "kas_kecil", "account_id": REK_K})
    assert r.status_code == 403, r.text
    r = await klien.post(f"/api/cash-advances/{ca}/disburse", headers=await sesi(keu),
                         json={"cash_type": "kas_kecil", "account_id": REK_K})
    assert r.status_code == 200, r.text
    pd = await db.cash_advances.find_one({"id": ca}, {"_id": 0})
    assert pd["status"] == "disbursed" and pd["disbursed_by_id"] == keu["id"]
    assert pd["disbursement"]["account_id"] == REK_K


async def test_PK24_U9b_cairkan_dua_orang_bila_diatur(klien, db, akun, sesi, siap):
    """K-17 — `kontrol.cairkan_uang_muka.min_orang` = 2: pemohon tidak mencairkan uang mukanya sendiri."""
    keu = await akun("finance")
    keu2 = await akun("finance")
    ca = await _pd(db, 120_000, pemohon=keu)
    key = "kontrol.cairkan_uang_muka.min_orang"
    await resolver.set_value(key, "2", scope_type="entity", scope_id=KSC, reason="uji PK-24", actor="uji")
    try:
        r = await klien.post(f"/api/cash-advances/{ca}/disburse", headers=await sesi(keu),
                             json={"cash_type": "kas_kecil", "account_id": REK_K})
        assert r.status_code == 403 and r.json()["detail"].startswith("Cairkan uang muka harus diputuskan orang lain"), \
            r.text
        assert (await db.cash_advances.find_one({"id": ca}))["status"] == "approved"
        assert await db.cash_transactions.count_documents({"ref_type": "cash_advance", "ref_id": ca}) == 0
        r = await klien.post(f"/api/cash-advances/{ca}/disburse", headers=await sesi(keu2),
                             json={"cash_type": "kas_kecil", "account_id": REK_K})
        assert r.status_code == 200, r.text
    finally:
        await resolver.clear_layer(key, scope_type="entity", scope_id=KSC, actor="uji", reason="uji PK-24")


async def test_PK24_U10_izin_terima_pengembalian(klien, db, kepala_admin, akun, sesi, peran_tanpa_acuan,
                                                peran_manajer_kosong, siap):
    ca = await _pd_cair(klien, db, kepala_admin, 300_000)
    stl = await _lpj(klien, kepala_admin, ca, [("atk", 100_000)])
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/approve", headers=kepala_admin)
    assert r.status_code == 200 and r.json()["sisa_dikembalikan"]["status"] == "open", r.text
    h_kosong = await sesi(await akun(await peran_manajer_kosong()))
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/return-remainder", headers=h_kosong,
                         json={"cash_type": "kas_kecil"})
    assert r.status_code == 403, r.text
    rid = await peran_tanpa_acuan({"cash_settlement": ["pay"]}, label="Terima Pengembalian Saja")
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/return-remainder", headers=await sesi(await akun(rid)),
                         json={"cash_type": "kas_kecil"})
    assert r.status_code == 200, r.text
    assert r.json()["sisa_dikembalikan"]["status"] == "returned"
    assert r.json()["sisa_dikembalikan"]["returned_by_id"]


async def test_PK24_U10b_izin_bawaan_bayar_kas_kecil(klien, kepala_admin):
    for peran in ("admin", "manager", "finance"):
        p = (await klien.get(f"/api/access/roles/{peran}", headers=kepala_admin)).json()["permissions"]
        assert "pay" in p["cash_settlement"], (peran, p.get("cash_settlement"))
        assert "disburse" in p["cash_advance"], (peran, p.get("cash_advance"))
    s = (await klien.get("/api/access/roles/sales", headers=kepala_admin)).json()["permissions"]
    assert "pay" not in (s.get("cash_settlement") or []) and "disburse" not in (s.get("cash_advance") or [])


# ── U11 — pengaturan "wajib berlampiran" per PT ──────────────────────────────────────────────────────────────────────
async def test_PK24_U11_wajib_lampiran_per_pt(klien, db, kepala_admin, sesi, siap, simpan_lokal):
    ca = await _pd_cair(klien, db, kepala_admin, 150_000)
    stl = await _lpj(klien, kepala_admin, ca, [("atk", 50_000)], ajukan=False)
    ca_kanda = await _pd(db, 150_000, entity=KANDA, status="disbursed")
    h_kanda = await sesi("admin@kainnusantara.id", entitas=KANDA)
    stl_kanda = await _lpj(klien, h_kanda, ca_kanda, [("atk", 50_000)], ajukan=False)
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [
        {"key": KUNCI_LAMPIRAN, "value": True, "scope_type": "entity", "scope_id": KSC, "reason": "uji PK-24"}]})
    assert r.status_code == 200, r.text
    try:
        r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/submit", headers=kepala_admin)
        assert (r.status_code, r.json()["detail"]) == (
            400, "Lampirkan minimal satu bukti pengeluaran sebelum mengajukan LPJ."), r.text
        assert (await db.cash_advance_settlements.find_one({"id": stl["id"]}))["status"] == "draft"
        r = await klien.post(f"/api/cash-advance-settlements/{stl_kanda['id']}/submit", headers=h_kanda)
        assert r.status_code == 200, r.text
        r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/attachments", headers=kepala_admin,
                             files={"file": ("nota.png", PNG, "image/png")})
        assert r.status_code == 200, r.text
        att = r.json()
        assert att["filename"] == "nota.png" and att["content_type"] == "image/png" and att["size"] == len(PNG)
        r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/submit", headers=kepala_admin)
        assert r.status_code == 200, r.text
        r = await klien.get(f"/api/cash-advance-settlements/{stl['id']}/attachments/{att['id']}", headers=kepala_admin)
        assert r.status_code == 200 and r.content == PNG, r.status_code
    finally:
        await klien.post("/api/config/values/clear", headers=kepala_admin, json={
            "key": KUNCI_LAMPIRAN, "scope_type": "entity", "scope_id": KSC, "reason": "pulihkan"})


async def test_PK24_U11b_lampiran_hanya_saat_draf_dan_bisa_dihapus(klien, db, kepala_admin, siap, simpan_lokal):
    ca = await _pd_cair(klien, db, kepala_admin, 90_000)
    stl = await _lpj(klien, kepala_admin, ca, [("atk", 40_000)], ajukan=False)
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/attachments", headers=kepala_admin,
                         files={"file": ("catatan.txt", b"bukan gambar", "text/plain")})
    assert r.status_code == 400, r.text
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/attachments", headers=kepala_admin,
                         files={"file": ("nota.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    att = r.json()
    r = await klien.delete(f"/api/cash-advance-settlements/{stl['id']}/attachments/{att['id']}", headers=kepala_admin)
    assert r.status_code == 200, r.text
    d = (await klien.get(f"/api/cash-advance-settlements/{stl['id']}", headers=kepala_admin)).json()
    assert d["attachments"] == []
    r = await klien.get(f"/api/cash-advance-settlements/{stl['id']}/attachments/{att['id']}", headers=kepala_admin)
    assert r.status_code == 404, r.text


# ── U12 — LPJ ditolak dibuka lagi oleh pembuatnya, diubah, diajukan lagi ─────────────────────────────────────────────
async def test_PK24_U12_buka_lagi_ubah_ajukan(klien, db, kepala_admin, akun, sesi, siap):
    ca = await _pd_cair(klien, db, kepala_admin, 500_000)
    stl = await _lpj(klien, kepala_admin, ca, [("atk", 200_000)])
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/reject", headers=kepala_admin,
                         json={"note": "nota kurang jelas"})
    assert r.status_code == 200 and r.json()["status"] == "rejected", r.text
    # Bukan pembuatnya → ditolak (izin ubah saja tidak cukup).
    h_lain = await sesi(await akun("manager"))
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/reopen", headers=h_lain)
    assert r.status_code == 403, r.text
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/reopen", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "draft"
    r = await klien.patch(f"/api/cash-advance-settlements/{stl['id']}", headers=kepala_admin, json={
        "expense_lines": [{"date": tanggal_buku(), "description": "nota baru", "category": "atk", "amount": 250_000}]})
    assert r.status_code == 200, r.text
    assert r.json()["total_pengeluaran"] == 250_000 and r.json()["sisa_kurang_dana"] == 250_000
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/submit", headers=kepala_admin)
    assert r.status_code == 200 and r.json()["status"] == "submitted", r.text
    d = await db.cash_advance_settlements.find_one({"id": stl["id"]})
    assert d["expense_lines"][0]["description"] == "nota baru"


async def test_PK24_U12b_buka_lagi_hanya_lpj_ditolak(klien, db, kepala_admin, siap):
    ca = await _pd_cair(klien, db, kepala_admin, 80_000)
    stl = await _lpj(klien, kepala_admin, ca, [("atk", 30_000)])
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/reopen", headers=kepala_admin)
    assert r.status_code == 409, r.text


# ── Tambahan — periode bulan; pengembalian gagal dapat diulang tanpa kas ganda ──────────────────────────────────────
async def test_PK24_periode_lpj_berupa_bulan(klien, db, kepala_admin, siap):
    ca = await _pd_cair(klien, db, kepala_admin, 70_000)
    r = await klien.post("/api/cash-advance-settlements", headers=kepala_admin, json={
        "cash_advance_id": ca, "periode": "Juli 2026",
        "expense_lines": [{"date": tanggal_buku(), "description": "x", "category": "atk", "amount": 10_000}]})
    assert r.status_code == 400 and "bulan" in r.json()["detail"].lower(), r.text
    stl = await _lpj(klien, kepala_admin, ca, [("atk", 10_000)], ajukan=False, periode="2026-07")
    assert stl["periode"] == "2026-07"


async def test_PK24_pengembalian_gagal_jurnal_diulang_satu_kas(klien, db, kepala_admin, siap, paksa_jurnal_gagal):
    ca = await _pd_cair(klien, db, kepala_admin, 260_000)
    stl = await _lpj(klien, kepala_admin, ca, [("atk", 60_000)])
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/approve", headers=kepala_admin)
    assert r.status_code == 200 and r.json()["sisa_dikembalikan"]["amount"] == 200_000, r.text
    url = f"/api/cash-advance-settlements/{stl['id']}/return-remainder"
    async with paksa_jurnal_gagal("periode", entity_id=KSC, period_key=BULAN_INI):
        r = await klien.post(url, headers=kepala_admin, json={"cash_type": "kas_kecil"})
    assert r.status_code == 409, r.text
    assert await db.cash_transactions.count_documents({"ref_type": "cash_advance_return", "ref_id": stl["id"]}) == 0
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="cash_transaction"):
        r = await klien.post(url, headers=kepala_admin, json={"cash_type": "kas_kecil"})
    assert r.status_code == 409 and "jurnal gagal" in r.json()["detail"].lower(), r.text
    d = await db.cash_advance_settlements.find_one({"id": stl["id"]})
    assert d["sisa_dikembalikan"]["status"] == "open"
    r = await klien.post(url, headers=kepala_admin, json={"cash_type": "kas_kecil"})
    assert r.status_code == 200 and r.json()["sisa_dikembalikan"]["status"] == "returned", r.text
    kas = await db.cash_transactions.find({"ref_type": "cash_advance_return", "ref_id": stl["id"]}, {"_id": 0}).to_list(5)
    assert len(kas) == 1 and kas[0]["gl_status"] == "posted"
    assert len(await _jurnal(db, "cash_transaction", kas[0]["id"])) == 1


async def test_PK24_U13_padanan_b_dua_pengembalian_bersamaan(klien, db, kepala_admin, siap):
    """Padanan lapis B untuk U13 (lapis A: `tests/test_bp_PK24_kembali_bersamaan_mongo.py`). Database tiruan tidak
    membuktikan balapan sejati — di sini hanya dua permintaan yang diselang-seling event loop."""
    import asyncio
    ca = await _pd_cair(klien, db, kepala_admin, 330_000)
    stl = await _lpj(klien, kepala_admin, ca, [("atk", 30_000)])
    r = await klien.post(f"/api/cash-advance-settlements/{stl['id']}/approve", headers=kepala_admin)
    assert r.status_code == 200 and r.json()["sisa_dikembalikan"]["amount"] == 300_000, r.text
    url = f"/api/cash-advance-settlements/{stl['id']}/return-remainder"
    hasil = await asyncio.gather(klien.post(url, headers=kepala_admin, json={"cash_type": "kas_kecil"}),
                                 klien.post(url, headers=kepala_admin, json={"cash_type": "kas_kecil"}))
    assert sorted(h.status_code for h in hasil) == [200, 409], [h.text for h in hasil]
    kas = await db.cash_transactions.find({"ref_type": "cash_advance_return", "ref_id": stl["id"]}, {"_id": 0}).to_list(5)
    assert len(kas) == 1 and len(await _jurnal(db, "cash_transaction", kas[0]["id"])) == 1
