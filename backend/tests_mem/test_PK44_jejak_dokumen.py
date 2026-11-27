"""PK-44 — Jejak dokumen membuka dokumennya (docs/blueprint/unit/PK-44.md, uji U1–U13; K-18).

Persiapan (fixture `siap`, disisipkan langsung ke database = FIXTURE, bukan alur; kecuali U6b lewat API):
  * pesanan `so_pk44` + kwitansi `rc_pk44` (alokasi 1.000.000 ke pesanan) + retur `sr_pk44` atas pesanan;
  * PD `pd_pk44` (dicairkan) + LPJ `lpj_pk44` (`cash_advance_id="pd_pk44"`, terposting) + jurnal
    `petty_cash_settlement` ber-`source_id="lpj_pk44"`; PD kedua `pd2_pk44` (dicairkan, tanpa LPJ) untuk U6b;
  * penggajian `run_pk44` (`ent_ksc`, `2026-10`) + jurnal `payroll_run` dan `payroll_pay` ber-`source_id`
    `"ent_ksc:2026-10"`; penggajian PT lain `run_kanda` (`ent_kanda`) untuk pagar PT;
  * aset `fa_pk44` + jurnal `fixed_asset_acquisition` (`"fa_pk44"`) dan `fixed_asset_depreciation`
    (`"fa_pk44:2026-10"`);
  * order makloon `mko_pk44` + jurnal `makloon_claim` (`"mko_pk44:2"`); nota denda `pen_pk44` + jurnal
    `penalty_payment` (`"pen_pk44:pay"`).
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from services import doc_refs_service as refs

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "frontend" / "src" / "AppViewRouter.jsx"
ALIASES = ROOT / "frontend" / "src" / "config" / "viewAliases.js"
SKRIP = ROOT / "scripts" / "apply_pk44_lpj_refs.py"
SEKARANG = "2026-11-14T02:00:00+00:00"
JT = 1_000_000
# U13 — layar yang menerima fokus lewat jalur lain (spesifikasi): Kasus Keuangan (`focusCase`), R&D (`focus`).
PENGECUALIAN_FOKUS = {"finance-cases", "rnd-specs", "rnd-samples"}
JENIS_BARU = {"payroll_run": "Penggajian", "cash_advance": "Pengajuan Dana (PD)",
              "cash_settlement": "Pertanggungjawaban Dana (LPJ)", "fixed_asset": "Aset Tetap"}


def _router() -> str:
    return ROUTER.read_text(encoding="utf-8")


def _alias_to() -> dict:
    """`viewAliases.js`: id lama → layar utama (`to`). Kunci bertanda kutip atau tidak."""
    txt = ALIASES.read_text(encoding="utf-8")
    return {(m.group(1) or m.group(2)): m.group(3) for m in re.finditer(
        r'(?:"([a-z0-9-]+)"|\b([a-z][a-zA-Z0-9]*))\s*:\s*\{\s*to:\s*"([a-z0-9-]+)"', txt)}


def _blok_jsx(src: str, view: str) -> str:
    """Potongan JSX yang dirender untuk `activeView === "<view>"` (sampai anak JSX tingkat atas berikutnya)."""
    i = src.find(f'activeView === "{view}"')
    if i < 0:
        return ""
    j = src.find("\n      {", i)
    return src[i: j if j > 0 else len(src)]


def _jurnal(jid, source_type, source_id, entity_id="ent_ksc", number=""):
    return {"id": jid, "number": number or f"KSC/JE-{jid[-6:].upper()}", "entity_id": entity_id,
            "source_type": source_type, "source_id": source_id, "status": "posted", "date": "2026-10-31",
            "lines": [], "created_at": SEKARANG}


def _muat_skrip():
    spec = importlib.util.spec_from_file_location("apply_pk44_lpj_refs", SKRIP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
async def siap(db):
    await db.sales_orders.insert_one({
        "id": "so_pk44", "number": "KSC/SO-UJI-PK44", "entity_id": "ent_ksc", "customer_name": "Pelanggan PK44",
        "status": "shipped", "grand_total": 5 * JT, "items": [], "created_at": SEKARANG})
    await db.ar_receipts.insert_one({
        "id": "rc_pk44", "number": "KSC/RC-UJI-PK44", "entity_id": "ent_ksc", "customer_name": "Pelanggan PK44",
        "amount": 1 * JT, "method": "transfer", "status": "posted", "receipt_date": "2026-11-01",
        "allocations": [{"order_id": "so_pk44", "applied": 1 * JT}], "created_at": SEKARANG})
    await db.sales_returns.insert_one({
        "id": "sr_pk44", "number": "KSC/RJ-UJI-PK44", "entity_id": "ent_ksc", "order_id": "so_pk44",
        "customer_name": "Pelanggan PK44", "status": "approved", "total_amount": 500_000, "created_at": SEKARANG})
    await db.shipments.insert_one({"id": "shp_pk44", "shipment_no": "KSC/SJ-UJI-PK44", "entity_id": "ent_ksc",
                                   "order_id": "so_pk44", "created_at": SEKARANG})
    await db.wms_tasks.insert_many([
        {"id": "wms_pick_pk44", "flow_type": "outbound", "order_id": "so_pk44", "entity_id": "ent_ksc",
         "created_at": SEKARANG},
        {"id": "wms_in_pk44", "flow_type": "inbound", "po_id": "po_pk44", "entity_id": "ent_ksc",
         "created_at": SEKARANG},
        {"id": "wms_in2_pk44", "flow_type": "inbound", "po_id": "", "entity_id": "ent_ksc", "created_at": SEKARANG},
    ])
    await db.cash_advances.insert_many([
        {"id": "pd_pk44", "number": "KSC/PD-UJI-PK44", "entity_id": "ent_ksc", "status": "settled",
         "total_amount": 750_000, "items": [], "created_at": SEKARANG},
        {"id": "pd2_pk44", "number": "KSC/PD-UJI-PK44B", "entity_id": "ent_ksc", "status": "disbursed",
         "total_amount": 300_000, "items": [], "divisi": "Gudang", "created_at": SEKARANG},
    ])
    await db.cash_advance_settlements.insert_one({
        "id": "lpj_pk44", "number": "KSC/STL-UJI-PK44", "entity_id": "ent_ksc", "cash_advance_id": "pd_pk44",
        "cash_advance_number": "KSC/PD-UJI-PK44", "status": "posted_to_gl", "journal_entry_id": "je_lpj_pk44",
        "total_pengeluaran": 700_000, "expense_lines": [], "created_at": SEKARANG})
    await db.hr_payroll_runs.insert_many([
        {"id": "run_pk44", "number": "KSC/PAY-UJI44", "entity_id": "ent_ksc", "period": "2026-10",
         "status": "paid", "totals": {"net": 9 * JT}, "journal_id": "", "paid_journal_id": "",
         "created_at": SEKARANG},
        {"id": "run_kanda", "number": "KANDA/PAY-UJI44", "entity_id": "ent_kanda", "period": "2026-10",
         "status": "draft", "totals": {}, "created_at": SEKARANG},
    ])
    await db.fin_fixed_assets.insert_one({"id": "fa_pk44", "number": "KSC/FA-UJI44", "entity_id": "ent_ksc",
                                          "name": "Mesin Uji", "acquisition_cost": 12 * JT, "status": "active",
                                          "created_at": SEKARANG})
    await db.makloon_orders.insert_one({"id": "mko_pk44", "mko_number": "KSC/MKO-UJI44", "entity_id": "ent_ksc",
                                        "status": "in_progress", "created_at": SEKARANG})
    await db.penalties.insert_one({"id": "pen_pk44", "number": "KSC/DND-UJI44", "entity_id": "ent_ksc",
                                   "status": "paid", "amount": 50_000, "created_at": SEKARANG})
    await db.journal_entries.insert_many([
        _jurnal("je_lpj_pk44", "petty_cash_settlement", "lpj_pk44"),
        _jurnal("je_pay_run44", "payroll_run", "ent_ksc:2026-10"),
        _jurnal("je_pay_pay44", "payroll_pay", "ent_ksc:2026-10"),
        _jurnal("je_fa_acq44", "fixed_asset_acquisition", "fa_pk44"),
        _jurnal("je_fa_dep44", "fixed_asset_depreciation", "fa_pk44:2026-10"),
        _jurnal("je_mko_klaim44", "makloon_claim", "mko_pk44:2"),
        _jurnal("je_pen_bayar44", "penalty_payment", "pen_pk44:pay"),
    ])
    return True


def _rujukan(data, rel, doc_type):
    return [r for r in data["refs"] if r.get("rel") == rel and r.get("doc_type") == doc_type]


# ── U1 / U13 — peta tujuan vs perute (statik) ───────────────────────────────────
async def test_PK44_U01_tiap_view_peta_dirender_perute():
    src = _router()
    hilang = sorted({m["view"] for m in refs.DOC_TYPES.values() if f'activeView === "{m["view"]}"' not in src})
    # Sebelum unit: sales-returns, transfers, cycle-count, cash-bank tidak punya layar.
    assert hilang == [], f"view peta jenis dokumen tanpa layar di AppViewRouter.jsx: {hilang}"


async def test_PK44_U13_tiap_view_tujuan_menerima_fokus():
    src = _router()
    alias = _alias_to()
    tidak = []
    for view in sorted({m["view"] for m in refs.DOC_TYPES.values()} - PENGECUALIAN_FOKUS):
        # Id lama (alias) dibuka di layar utamanya (`handleNavSelect`): keduanya wajib meneruskan fokus.
        for target in [view] + ([alias[view]] if view in alias else []):
            if "focusDoc" not in _blok_jsx(src, target):
                tidak.append(target)
    assert tidak == [], f"layar tujuan yang tidak menerima focusDoc: {tidak}"


# ── U2–U4 — satu pembentuk tautan ────────────────────────────────────────────────
async def test_PK44_U02_empat_view_diperbaiki():
    assert refs.link_of("sales_return", {"id": "sr1", "number": "RJ-1"}) == {
        "view": "returns", "tab": "", "focus_type": "sales_return", "focus_id": "sr1", "number": "RJ-1"}
    t = refs.link_of("warehouse_transfer", {"id": "wt1", "code": "TRF-1"})
    assert (t["view"], t["tab"], t["focus_type"], t["focus_id"]) == ("operations", "transfer",
                                                                     "warehouse_transfer", "wt1")
    c = refs.link_of("cycle_count", {"id": "cc1", "number": "SO-1"})
    assert (c["view"], c["tab"], c["focus_type"], c["focus_id"]) == ("operations", "cycle", "cycle_count", "cc1")
    k = refs.link_of("cash_transaction", {"id": "cash1", "number": "KSC/CASH-1"})
    assert (k["view"], k["focus_type"], k["focus_id"], k["number"]) == ("cash-management", "cash_transaction",
                                                                        "cash1", "KSC/CASH-1")


async def test_PK44_U03_surat_jalan_tugas_gudang_lewat_induk():
    sj = refs.link_of("shipment", {"id": "shp1", "shipment_no": "SJ-1", "order_id": "so1"})
    assert (sj["view"], sj["focus_type"], sj["focus_id"]) == ("orders", "sales_order", "so1")
    pk = refs.link_of("picking_task", {"id": "wms_pick1", "order_id": "so1"})
    assert (pk["view"], pk["focus_type"], pk["focus_id"]) == ("wms-outbound", "wms_task", "wms_pick1")
    gr = refs.link_of("grn", {"id": "wms_in1", "po_id": "po1"})
    assert (gr["view"], gr["tab"], gr["focus_type"], gr["focus_id"]) == ("goods-receipts", "inbound",
                                                                         "purchase_order", "po1")
    tanpa = refs.link_of("grn", {"id": "wms_in2", "po_id": ""})
    assert tanpa["view"] == "goods-receipts" and tanpa["focus_id"] == ""


async def test_PK44_U04_kwitansi_ke_penagihan():
    # Spesifikasi menulis `customers-crm` tab `collection`; MN-T1 (prasyarat) memindahkan tab Penagihan dari CRM ke
    # layar `collection-worklist` (Keuangan › Piutang › Penagihan & Penerimaan) — lihat laporan, usulan koreksi U4.
    rc = refs.link_of("ar_receipt", {"id": "rc1", "number": "KSC/RC-1"})
    assert rc == {"view": "collection-worklist", "tab": "", "focus_type": "ar_receipt", "focus_id": "rc1",
                  "number": "KSC/RC-1"}
    assert 'activeView === "collection-worklist"' in _router()


# ── U5 / U12 — jenis & label di ref-types ────────────────────────────────────────
async def test_PK44_U05_ref_types_memuat_empat_jenis_baru(klien, kepala_admin):
    r = await klien.get("/api/documents/ref-types", headers=kepala_admin)
    assert r.status_code == 200, r.text
    jenis = {t["doc_type"]: t for t in r.json()["types"]}
    # 39 jenis lama + 4 jenis baru + Pindah Dana (Kas & Bank 1, Tugas 6) + pengajuan kas keluar (Kas & Bank 2, Tugas 4)
    assert len(jenis) == 45
    for dt, label in JENIS_BARU.items():
        assert jenis[dt]["label"] == label
    assert jenis["payroll_run"]["view"] == "hr-payroll-runs" and jenis["payment_plan"]["tab"] == "jadwal"


async def test_PK44_U12_satu_dokumen_satu_nama(klien, kepala_admin):
    r = await klien.get("/api/documents/ref-types", headers=kepala_admin)
    label = {t["doc_type"]: t["label"] for t in r.json()["types"]}
    assert label["vendor_bill"] == "Tagihan Pemasok"
    assert label["ar_receipt"] == "Kwitansi Pelanggan"
    assert label["sales_order"] == "Pesanan Penjualan (SO)"
    assert [t for t, lb in label.items() if "(Kontrabon)" in lb] == []
    assert "Kontrabon" in label["contra_bon"]
    assert label["supplier_contract"] == "Kontrak Pemasok" and label["journal_entry"] == "Jurnal"
    assert label["interco_settlement"] == "Pelunasan Antar-PT"


# ── U6 — LPJ ↔ PD ↔ jurnal ───────────────────────────────────────────────────────
async def test_PK44_U06_lpj_induk_pd_dan_jurnal(klien, kepala_admin, db, siap, capsys):
    assert SKRIP.exists(), f"skrip {SKRIP.name} belum ada"
    skrip = _muat_skrip()
    # LPJ lama (fixture, tanpa refs) — skrip mode laporan bawaan: 1 akan ditaut, tidak menulis.
    assert await skrip.main([]) == 0
    assert "LPJ yang akan ditautkan: 1" in capsys.readouterr().out
    assert not (await db.cash_advance_settlements.find_one({"id": "lpj_pk44"})).get("refs")
    assert await skrip.main(["--apply"]) == 0
    capsys.readouterr()
    assert await skrip.main([]) == 0
    keluaran = capsys.readouterr().out
    assert "LPJ yang akan ditautkan: 0" in keluaran and "Sudah bertaut (dilewati): 1" in keluaran

    r = await klien.get("/api/documents/refs/cash_settlement/lpj_pk44", headers=kepala_admin)
    assert r.status_code == 200, r.text
    d = r.json()
    induk = _rujukan(d, "parent", "cash_advance")
    assert [x["doc_id"] for x in induk] == ["pd_pk44"]
    assert induk[0]["link"]["view"] == "cash-advances" and induk[0]["link"]["focus_type"] == "cash_advance"
    assert [x["doc_id"] for x in _rujukan(d, "journaled_by", "journal_entry")] == ["je_lpj_pk44"]
    assert d["anchor"]["link"]["view"] == "settlements"
    r = await klien.get("/api/documents/refs/journal_entry/je_lpj_pk44", headers=kepala_admin)
    asal = _rujukan(r.json(), "journal_of", "cash_settlement")
    assert [x["doc_id"] for x in asal] == ["lpj_pk44"] and asal[0]["link"]["focus_type"] == "cash_settlement"


async def test_PK44_U06b_lpj_baru_ditaut_saat_lahir(klien, kepala_admin, siap):
    r = await klien.post("/api/cash-advance-settlements", headers=kepala_admin, json={
        "cash_advance_id": "pd2_pk44", "expense_lines": [{"date": "2026-11-10", "description": "Bensin",
                                                          "category": "petty_cash_lain", "amount": 250_000}]})
    assert r.status_code == 200, r.text
    lpj = r.json()["id"]
    r = await klien.get(f"/api/documents/refs/cash_settlement/{lpj}", headers=kepala_admin)
    assert [x["doc_id"] for x in _rujukan(r.json(), "parent", "cash_advance")] == ["pd2_pk44"]
    r = await klien.get("/api/documents/refs/cash_advance/pd2_pk44", headers=kepala_admin)
    assert [x["doc_id"] for x in _rujukan(r.json(), "child", "cash_settlement")] == [lpj]


# ── U7–U9 — jurnal yang dulu tidak menaut ────────────────────────────────────────
async def test_PK44_U07_penggajian_dua_jurnal(klien, kepala_admin, siap):
    r = await klien.get("/api/documents/refs/payroll_run/run_pk44", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert sorted(x["doc_id"] for x in _rujukan(r.json(), "journaled_by", "journal_entry")) == [
        "je_pay_pay44", "je_pay_run44"]
    for jid in ("je_pay_run44", "je_pay_pay44"):
        r = await klien.get(f"/api/documents/refs/journal_entry/{jid}", headers=kepala_admin)
        asal = [x for x in r.json()["refs"] if x["rel"] == "journal_of"]
        # Dulu: pemotongan "ent_ksc:2026-10" pada ":" → `journal_of` menunjuk "ent_ksc" (id PT).
        assert [(x["doc_type"], x["doc_id"]) for x in asal] == [("payroll_run", "run_pk44")], jid


async def test_PK44_U08_aset_tetap_dua_jurnal(klien, kepala_admin, siap):
    r = await klien.get("/api/documents/refs/fixed_asset/fa_pk44", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert sorted(x["doc_id"] for x in _rujukan(r.json(), "journaled_by", "journal_entry")) == [
        "je_fa_acq44", "je_fa_dep44"]


async def test_PK44_U09_klaim_makloon_dan_bayar_denda(klien, kepala_admin, siap):
    r = await klien.get("/api/documents/refs/journal_entry/je_mko_klaim44", headers=kepala_admin)
    assert [(x["doc_type"], x["doc_id"]) for x in r.json()["refs"] if x["rel"] == "journal_of"] == [
        ("makloon_order", "mko_pk44")]
    r = await klien.get("/api/documents/refs/journal_entry/je_pen_bayar44", headers=kepala_admin)
    assert [(x["doc_type"], x["doc_id"]) for x in r.json()["refs"] if x["rel"] == "journal_of"] == [
        ("penalty", "pen_pk44")]


# ── U10 — linimasa proses memakai peta yang sama ────────────────────────────────
async def test_PK44_U10_linimasa_pesanan_tautan_dari_peta(klien, kepala_admin, db, siap):
    r = await klien.get("/api/documents/relations/sales_order/so_pk44", headers=kepala_admin)
    assert r.status_code == 200, r.text
    stages = {s["key"]: s for s in r.json()["stages"]}
    kunci = ("view", "tab", "focus_type", "focus_id", "number")
    rc = await db.ar_receipts.find_one({"id": "rc_pk44"}, {"_id": 0})
    sr = await db.sales_returns.find_one({"id": "sr_pk44"}, {"_id": 0})
    node_rc = next(n for n in stages["payment"]["docs"] if n["id"] == "rc_pk44")
    node_sr = next(n for n in stages["return"]["docs"] if n["id"] == "sr_pk44")
    assert {k: node_rc["link"][k] for k in kunci} == refs.link_of("ar_receipt", rc)
    assert {k: node_sr["link"][k] for k in kunci} == refs.link_of("sales_return", sr)
    src = _router()
    views = {n["link"].get("view") for s in stages.values() for n in s["docs"] if n["link"].get("view")}
    assert views and all(f'activeView === "{v}"' in src for v in views), views
    assert all("nav_id" not in n["link"] for s in stages.values() for n in s["docs"])


# ── U11 — penyaringan nominal menurut izin modul sumber (K-18, mekanisme PK-17) ────
async def test_PK44_U11_penggajian_disaring_izin_hr(klien, akun, sesi, siap, peran_tanpa_acuan):
    tanpa = await akun(await peran_tanpa_acuan({"document": ["view"]}, label="PK44 Dokumen"))
    r = await klien.get("/api/documents/trace-search", params={"q": "PAY-UJI44"}, headers=await sesi(tanpa))
    assert r.status_code == 200, r.text
    simpul = [n for n in r.json() if n["doc_id"] == "run_pk44"]
    # Mengikuti PK-17: simpul tetap tampil (nomor/jenis), tanpa nominal dan tanpa tombol buka.
    assert simpul and simpul[0]["amount"] is None and simpul[0]["amount_hidden"] is True
    assert simpul[0]["can_open"] is False
    dengan = await akun(await peran_tanpa_acuan({"document": ["view"], "hr": ["view"]}, label="PK44 Dokumen HR"))
    r = await klien.get("/api/documents/trace-search", params={"q": "PAY-UJI44"}, headers=await sesi(dengan))
    simpul = [n for n in r.json() if n["doc_id"] == "run_pk44"]
    assert simpul and not simpul[0].get("amount_hidden") and simpul[0]["link"]["view"] == "hr-payroll-runs"
    # Penggajian PT lain tidak ikut dicari (akun hanya bertugas di ent_ksc).
    assert all(n["doc_id"] != "run_kanda" for n in r.json())


# ── Tambahan: pagar PT jenis baru & koleksi peta ─────────────────────────────────
async def test_PK44_pagar_pt_jenis_baru_dan_biaya_masuk(klien, akun, sesi, db, siap):
    # N1 — jejak penggajian PT lain = 404 bagi akun yang hanya bertugas di ent_ksc.
    keu = await akun("finance")
    h = await sesi(keu)
    r = await klien.get("/api/documents/trace/payroll_run/run_kanda", headers=h)
    assert r.status_code == 404, r.text
    # Koleksi pagar diambil dari peta: Biaya Masuk (`landed_cost_vouchers`) dulu dicari di `landed_costs` → 404.
    await db.landed_cost_vouchers.insert_one({"id": "lcv_pk44", "number": "KSC/LCV-UJI44", "entity_id": "ent_ksc",
                                              "po_ids": [], "status": "draft", "created_at": SEKARANG})
    r = await klien.get("/api/documents/trace/landed_cost/lcv_pk44", headers=h)
    assert r.status_code == 200, r.text
