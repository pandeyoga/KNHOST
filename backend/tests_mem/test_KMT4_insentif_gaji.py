"""KM-T4 — Lembar Insentif tersambung ke gaji dan buku besar; komisi otomatis mati per PT (lingkungan B).

Spesifikasi `docs/blueprint/unit/KM-T4.md`, uji penerimaan U1–U15 (U16 = lapis A `tests/test_bp_KMT4_sahkan_bersamaan_mongo.py`;
U17 = uji jalan peramban oleh integrator; komponen layar di `features/__tests__/kmt4LembarGaji.test.js`).

Fixture (disisipkan langsung): `ent_kanda` bermode `sheet` (lewat `config_resolver.set_value`, alasan tertulis); setelan
`gl.tanggal_jurnal_periodik` bawaan (`akhir_periode`). Karyawan Andi & Budi (`ent_kanda`) dan Dodi & Citra (`ent_ksc`):
gaji pokok 5.000.000, TK0, BPJS dimatikan per karyawan (`bpjs_kes_enabled`/`bpjs_tk_enabled` salah — efeknya sama dengan
mematikan BPJS untuk PT), tertaut ke akun salesnya. Karyawan seed di kedua PT dinonaktifkan supaya jurnal gaji hanya
memuat karyawan uji. Komponen insentif `BLN` (bulanan), `TW` (triwulan), `KHS` (bulanan) di `ent_kanda`, `BLN` di
`ent_ksc`. Lembar, gaji, pelunasan, dan Posting Gagal lewat HTTP (alur). "Hari ini" dibekukan lewat
`services.book_date._sekarang` (5 Nov 2026; U5 dan sesudahnya 28 Des 2026).

Lembar L1 (`pay_period` 2026-11): Andi "Insentif Bulanan" Okt 2026 Rp 2.000.000; Andi "Insentif Triwulan" Triwulan III
2026 Rp 3.000.000; Budi "Insentif Bulanan" Okt 2026 Rp 3.500.000 → T = 8.500.000.

Hitung tangan (tarif TER kategori A dibaca lewat `ter_rate`, tabel bawaan PK-46):
  U2  Andi: gaji 5.000.000 + insentif 2.000.000 + 3.000.000 = bruto 10.000.000 (komisi mesin 1.000 m × Rp 500 = 500.000
      TIDAK dimuat); PPh 21 = 10.000.000 × 2 % = 200.000; bersih 9.800.000. Budi: 5.000.000 + 3.500.000 = 8.500.000;
      PPh 21 = 8.500.000 × 1,5 % = 127.500; bersih 8.372.500.
  U3  Dr 6-1000 10.000.000 + Dr 2-1500 8.500.000 = 18.500.000 = Cr 2-1600 (9.800.000 + 8.372.500) 18.172.500
      + Cr 2-1800 (200.000 + 127.500) 327.500. Saldo 2-1500 = 8.500.000 − 8.500.000 = 0.
  U5  Desember = masa pajak terakhir (hitung ulang setahun, `_is_final_tax_period`) — spesifikasi menulis PPh 21 0 dan
      bersih 4.500.000; hitungan yang benar (lihat laporan, usulan koreksi): Andi bruto setahun 10.000.000 + 4.500.000 =
      14.500.000; biaya jabatan min(5 % × 14.500.000 = 725.000; 500.000 × 2 bulan) = 725.000; neto 13.775.000 < PTKP TK0
      54.000.000 → PKP 0 → PPh setahun 0; sudah dipotong 200.000 → PPh 21 Desember −200.000 (dikembalikan), bersih
      4.500.000 + 200.000 = 4.700.000. Budi: 8.500.000 + 5.000.000 = 13.500.000 → PPh setahun 0 → −127.500, bersih
      5.127.500. Jurnal: Dr 6-1000 10.000.000 + Dr 2-1800 327.500 = 10.327.500 = Cr 2-1500 500.000 + Cr 2-1600
      (4.700.000 + 5.127.500) 9.827.500.
  U12 Dodi (karyawan `ent_ksc`, lembar `ent_kanda` Rp 2.000.000): bruto 7.000.000 × 1,25 % = 87.500; bersih 6.912.500.
      Citra 5.000.000 × 0 % → bersih 5.000.000. Jurnal gaji `ent_ksc`: Dr 6-1000 10.000.000 + Dr 1-1250 2.000.000 =
      12.000.000 = Cr 2-1600 11.912.500 + Cr 2-1800 87.500. Jurnal `ent_kanda`: Dr 2-1500 / Cr 2-1250 2.000.000.
"""
from __future__ import annotations

import datetime
import importlib
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

from pembantu import AKTOR_UJI, aktifkan_akun, nonaktifkan_akun, tutup_periode

pytestmark = pytest.mark.anyio

KANDA, KSC = "ent_kanda", "ent_ksc"
URL = "/api/incentive/sheets"
MODE = "hr.payroll_commission_mode"
REK_KANDA, REK_KSC = "rek_kmt4_kanda", "rek_kmt4_ksc"
REPO = Path(__file__).resolve().parents[2]
UTC = datetime.timezone.utc
JAM = {"now": datetime.datetime(2026, 11, 5, 3, 0, tzinfo=UTC)}   # 5 Nov 2026 10.00 WIB
K: Dict[str, Any] = {}


@pytest.fixture(scope="module", autouse=True)
def _jam():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: JAM["now"])
        yield


async def _mode(eid: str, nilai: str) -> None:
    from services import config_resolver as resolver
    await resolver.set_value(MODE, nilai, scope_type="entity", scope_id=eid, actor="uji", reason="uji KM-T4")


async def _karyawan(db, eid: str, user: Dict[str, Any], kode: str) -> Dict[str, Any]:
    emp = {"id": f"emp_kmt4_{kode}", "code": f"EMP-KMT4-{kode.upper()}", "name": user["name"], "entity_id": eid,
           "user_id": user["id"], "status": "active", "base_salary": 5_000_000, "allowances": [], "ptkp_status": "TK0",
           "bpjs_kes_enabled": False, "bpjs_tk_enabled": False, "join_date": "2025-01-01",
           "created_at": "2025-01-01T00:00:00+00:00"}
    await db.hr_employees.insert_one(dict(emp))
    return emp


@pytest.fixture(scope="module")
async def f4(db, akun, sesi):
    from services import incentive_targets as itg
    await _mode(KANDA, "sheet")
    await db.hr_employees.update_many({"entity_id": {"$in": [KANDA, KSC]}}, {"$set": {"status": "inactive"}})
    for rid, eid in ((REK_KANDA, KANDA), (REK_KSC, KSC)):
        await db.bank_accounts.insert_one({"id": rid, "name": f"Bank {eid} KM-T4", "entity_id": eid,
                                           "account_type": "bank", "cash_type": "kas_besar", "bank_name": "BCA",
                                           "account_number": "4040", "is_active": True, "opening_balance": 50_000_000})
    u = {}
    for kode, nama, ents in (("andi", "Andi", (KANDA,)), ("budi", "Budi", (KANDA,)), ("dodi", "Dodi", (KSC, KANDA)),
                             ("citra", "Citra", (KSC,)), ("eko", "Eko", (KANDA,))):
        u[kode] = await akun("sales", entitas=ents)
        await db.users.update_one({"id": u[kode]["id"]}, {"$set": {"name": nama}})
        u[kode]["name"] = nama
    emp = {"andi": await _karyawan(db, KANDA, u["andi"], "andi"), "budi": await _karyawan(db, KANDA, u["budi"], "budi"),
           "dodi": await _karyawan(db, KSC, u["dodi"], "dodi"), "citra": await _karyawan(db, KSC, u["citra"], "citra")}
    komp = {}
    for kode, nama, jenis in (("BLN", "Insentif Bulanan", "month"), ("TW", "Insentif Triwulan", "quarter"),
                              ("KHS", "Insentif Khusus", "month")):
        komp[kode] = await itg.create_component(KANDA, {"code": kode, "name": nama, "basis_period_type": jenis,
                                                        "columns": ["omzet"]}, AKTOR_UJI)
    komp["BLN_KSC"] = await itg.create_component(KSC, {"code": "BLN", "name": "Insentif Bulanan",
                                                       "basis_period_type": "month", "columns": ["omzet"]}, AKTOR_UJI)
    return {"u": u, "emp": emp, "komp": komp,
            "h": await sesi("admin@kainnusantara.id", entitas=KANDA),
            "h_ksc": await sesi("admin@kainnusantara.id", entitas=KSC)}


# ── pembantu ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _baris_lembar(f4, sales: str, komp: str, pt: str, p: str) -> Dict[str, str]:
    return {"sales_id": f4["u"][sales]["id"], "component_id": f4["komp"][komp]["id"], "basis_period_type": pt,
            "basis_period": p}


async def _lembar(klien, f4, pay: str, isi: List[tuple], h=None, ajukan: bool = True) -> Dict[str, Any]:
    """Lembar draf → nominal diketik → diajukan. `isi` = [(sales, komponen, jenis periode, periode, nominal)]."""
    h = h or f4["h"]
    r = await klien.post(URL, headers=h, json={"pay_period": pay, "lines": [_baris_lembar(f4, *x[:4]) for x in isi]})
    assert r.status_code == 200, r.text
    s = r.json()
    for x, ln in zip(isi, s["lines"]):
        r = await klien.patch(f"{URL}/{s['id']}/lines/{ln['id']}", headers=h, json={"amount": x[4]})
        assert r.status_code == 200, r.text
    if ajukan:
        r = await klien.post(f"{URL}/{s['id']}/submit", headers=h, json={})
        assert r.status_code == 200, r.text
        s = r.json()
    return s


async def _jurnal(db, source_type: str, source_id: str) -> List[Dict[str, Any]]:
    return await db.journal_entries.find({"source_type": source_type, "source_id": source_id,
                                          "status": {"$ne": "void"}}, {"_id": 0}).to_list(20)


def _baris(je: Dict[str, Any]) -> List[tuple]:
    return sorted((ln["account_code"], round(ln["debit"], 2), round(ln["credit"], 2)) for ln in je["lines"])


async def _saldo(db, eid: str, kode: str) -> float:
    """Σ debit − kredit akun `kode` PT `eid` (jurnal tidak batal)."""
    tot = 0.0
    async for je in db.journal_entries.find({"entity_id": eid, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == kode:
                tot += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(tot, 2)


async def _masukan(db, sheet_id: str) -> List[Dict[str, Any]]:
    return await db.hr_pay_inputs.find({"source_type": "incentive_sheet", "source_ref.sheet_id": sheet_id},
                                       {"_id": 0}).sort("created_at", 1).to_list(50)


async def _proses(klien, h, period: str, *, siap_posting: bool = True) -> Dict[str, Any]:
    r = await klien.post("/api/hr/payroll/runs", headers=h, json={"entity_id": h["X-Entity-Id"], "period": period,
                                                                   "run_type": "regular"})
    assert r.status_code == 200, r.text
    run = r.json()
    if siap_posting and run["status"] == "draft":
        for aksi in ("submit", "approve"):
            r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", headers=h, json={})
            assert r.status_code == 200, r.text
            run = r.json()
    return run


def _slip(run: Dict[str, Any], nama: str) -> Dict[str, Any]:
    rows = [s for s in run["payslips"] if s["employee_name"] == nama]
    assert len(rows) == 1, [s["employee_name"] for s in run["payslips"]]
    return rows[0]


async def _ter(gross: float) -> float:
    from services import hr_payroll_service as pay
    return pay.ter_rate("A", gross, await pay.aturan_pph21("2026-11-30"))


async def _data_mesin(db, eid: str, sales: Dict[str, Any], kode: str) -> None:
    """Komisi mesin: tarif Rp 500 per meter (batas margin 0) dan pesanan sales 1.000 m lunas 10 Nov 2026."""
    kat = f"KMT4-{kode}"
    await db.incentive_rates.insert_one({"id": f"rate_kmt4_{kode}", "entity_id": eid, "category": kat,
                                         "per_unit_amount": 500.0, "margin_cap_pct": 0.0, "discount_threshold": 100.0,
                                         "discount_threshold_type": "pct", "discount_mechanic": "tier_factor",
                                         "discount_factor": 1.0, "status": "active"})
    await db.customers.insert_one({"id": f"cus_kmt4_{kode}", "name": f"Toko KM-T4 {kode}", "entity_id": eid,
                                   "status": "active", "assigned_sales_id": sales["id"]})
    await db.sales_orders.insert_one({
        "id": f"so_kmt4_{kode}", "number": f"SO/KMT4/{kode}", "entity_id": eid, "customer_id": f"cus_kmt4_{kode}",
        "status": "completed", "items": [{"product_id": f"prd_kmt4_{kode}", "sku": "KMT4", "category": kat,
                                          "product_name": "Kain KM-T4", "quantity": 1000, "base_quantity": 1000,
                                          "unit": "meter", "price": 50_000, "line_total": 50_000_000,
                                          "discount_percent": 0, "unit_cost": 30_000}],
        "subtotal": 50_000_000, "grand_total": 50_000_000, "payments": [
            {"amount": 50_000_000, "created_at": "2026-11-10T03:00:00+00:00"}],
        "created_at": "2026-11-02T03:00:00+00:00"})


async def _hapus_data_mesin(db, kode: str) -> None:
    """Data komisi mesin dicabut sesudah uji pratinjau (U2, U7) supaya proses gaji uji berikutnya tidak bergantung pada
    serah-terima (b) — di (a) mesin masih dipanggil."""
    await db.incentive_rates.delete_one({"id": f"rate_kmt4_{kode}"})
    await db.customers.delete_one({"id": f"cus_kmt4_{kode}"})
    await db.sales_orders.delete_one({"id": f"so_kmt4_{kode}"})


def _cek_slip_nov(run: Dict[str, Any]) -> None:
    """Slip Andi & Budi proses reguler 2026-11 (hitungan di kepala berkas)."""
    andi, budi = _slip(run, "Andi"), _slip(run, "Budi")
    ins = [c for c in andi["components"] if c["code"] == "INSENTIF"]
    assert sorted((c["label"], c["amount"]) for c in ins) == [("Insentif Bulanan — Okt 2026", 2_000_000),
                                                              ("Insentif Triwulan — Triwulan III 2026", 3_000_000)]
    assert not [c for c in andi["components"] if c["code"] == "KOMISI"], andi["components"]
    assert (andi["commission"], andi["gross"], andi["pph21"], andi["net"]) == (5_000_000, 10_000_000, 200_000, 9_800_000)
    assert (budi["commission"], budi["gross"], budi["pph21"], budi["net"]) == (3_500_000, 8_500_000, 127_500, 8_372_500)


# ═══ U1 — sahkan di PT bermode `sheet`: jurnal + tiga masukan ══════════════════════════════════════════════════════
async def test_KMT4_U1_sahkan_jurnal_dan_masukan(klien, db, f4):
    s = await _lembar(klien, f4, "2026-11", [("andi", "BLN", "month", "2026-10", 2_000_000),
                                             ("andi", "TW", "quarter", "2026-Q3", 3_000_000),
                                             ("budi", "BLN", "month", "2026-10", 3_500_000)])
    r = await klien.post(f"{URL}/{s['id']}/approve", headers=f4["h"], json={})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["status"], j["payroll_linked"], j["gl_status"], j["journal_date"]) == (
        "approved", True, "posted", "2026-10-31"), j
    jes = await _jurnal(db, "incentive_sheet", s["id"])
    assert len(jes) == 1 and jes[0]["entity_id"] == KANDA and jes[0]["date"] == "2026-10-31", jes
    # T = 2.000.000 + 3.000.000 + 3.500.000 = 8.500.000 → Dr 6-5000 / Cr 2-1500
    assert _baris(jes[0]) == [("2-1500", 0, 8_500_000), ("6-5000", 8_500_000, 0)]
    assert j["journal_entry_id"] == jes[0]["id"]
    inp = await _masukan(db, s["id"])
    assert sorted((x["label"], x["amount"]) for x in inp) == [
        ("Insentif Bulanan — Okt 2026", 2_000_000), ("Insentif Bulanan — Okt 2026", 3_500_000),
        ("Insentif Triwulan — Triwulan III 2026", 3_000_000)], inp
    assert {(x["status"], x["pay_period"], x["entity_id"], x["component_code"]) for x in inp} == {
        ("approved", "2026-11", KANDA, "INSENTIF")}
    assert {x["source_ref"]["charge_entity_id"] for x in inp} == {KANDA}
    assert {x["employee_id"] for x in inp} == {"emp_kmt4_andi", "emp_kmt4_budi"}
    assert all(ln["employee_id"] and ln["pay_entity_id"] == KANDA and ln["input_key"].startswith("isheet:")
               for ln in j["lines"])
    K["L1"] = j


# ═══ U4 (sebelum U3) — INV-KM-4 ════════════════════════════════════════════════════════════════════════════════════
async def test_KMT4_U4a_invarian_hutang_sebelum_gaji(db, f4, capsys):
    from services import incentive_payroll as ipay
    rows = await ipay.cek_hutang_insentif(KANDA)
    assert rows == [{"entity_id": KANDA, "saldo": 8_500_000.0, "lembar": 8_500_000.0, "ok": True}], rows
    sys.path.insert(0, str(REPO / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    awal = vdi.results["fail"]
    await vdi.layer_incentive_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == awal and re.search(r"PASS.*INV-KM-4", keluar), keluar
    # bukti-merah penjaga: satu baris lembar ditandai dibayar tanpa jurnal gaji → saldo ≠ Σ baris belum dibayar
    await db.incentive_sheets.update_one({"id": K["L1"]["id"]}, {"$set": {"lines.0.paid_run_id": "prun_palsu"}})
    await vdi.layer_incentive_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == awal + 1 and re.search(r"FAIL.*INV-KM-4", keluar), keluar
    await db.incentive_sheets.update_one({"id": K["L1"]["id"]}, {"$unset": {"lines.0.paid_run_id": ""}})


# ═══ U2 — proses reguler 2026-11: dua baris insentif, mesin tidak dipanggil ═══════════════════════════════════════
async def test_KMT4_U2_slip_dari_lembar_tanpa_komisi_mesin(klien, db, f4, monkeypatch):
    """Pratinjau proses reguler (jalur hitung yang sama dengan proses dibuat, `_build_slips`); slip proses yang dibuat
    diperiksa lagi di U3. Data komisi mesin ada (500.000 bila mesin dipanggil) lalu dicabut di akhir."""
    from services import sales_force_service as sf
    await _data_mesin(db, KANDA, f4["u"]["andi"], "andi")
    dipanggil: List[str] = []
    asli = sf.compute_commission

    async def _hitung(uid, period, entity_id=None):
        dipanggil.append(uid)
        return await asli(uid, period, entity_id=entity_id)
    monkeypatch.setattr(sf, "compute_commission", _hitung)
    try:
        assert (await asli(f4["u"]["andi"]["id"], "2026-11", entity_id=KANDA))["total_incentive"] == 500_000
        r = await klien.post("/api/hr/payroll/runs/preview", headers=f4["h"],
                             json={"entity_id": KANDA, "period": "2026-11"})
        assert r.status_code == 200, r.text
        assert dipanggil == [], dipanggil     # mode `sheet` → mesin komisi tidak dipanggil
        assert await _ter(10_000_000) == pytest.approx(0.02) and await _ter(8_500_000) == pytest.approx(0.015)
        _cek_slip_nov(r.json())
    finally:
        await _hapus_data_mesin(db, "andi")


# ═══ U3 — posting: Dr hutang insentif, lembar dibayar ═════════════════════════════════════════════════════════════
async def test_KMT4_U3_posting_melunasi_hutang_insentif(klien, db, f4):
    run = await _proses(klien, f4["h"], "2026-11")
    _cek_slip_nov(run)
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=f4["h"], json={})
    assert r.status_code == 200, r.text
    run = r.json()
    assert (run["status"], run["gl_status"], run["journal_date"]) == ("posted", "posted", "2026-11-30"), run
    je = (await _jurnal(db, "payroll_run", run["id"]))[0]
    assert _baris(je) == [("2-1500", 8_500_000, 0), ("2-1600", 0, 18_172_500), ("2-1800", 0, 327_500),
                          ("6-1000", 10_000_000, 0)], _baris(je)
    assert await db.journal_entries.count_documents({"source_type": "incentive_accrual"}) == 0
    assert await _saldo(db, KANDA, "2-1500") == 0
    l1 = await db.incentive_sheets.find_one({"id": K["L1"]["id"]}, {"_id": 0})
    assert l1["status"] == "paid", l1["status"]
    assert {(x["paid_run_id"], x["paid_run_number"]) for x in l1["lines"]} == {(run["id"], run["number"])}
    assert l1["history"][-1]["action"] == "paid"
    K["run_nov"], K["run_nov_number"] = run["id"], run["number"]


async def test_KMT4_U4b_invarian_hutang_sesudah_gaji(f4):
    from services import incentive_payroll as ipay
    assert await ipay.cek_hutang_insentif(KANDA) == [{"entity_id": KANDA, "saldo": 0.0, "lembar": 0.0, "ok": True}]


# ═══ U5 — penyesuaian −500.000 di lembar Desember ═════════════════════════════════════════════════════════════════
async def test_KMT4_U5_penyesuaian_negatif(klien, db, f4):
    JAM["now"] = datetime.datetime(2026, 12, 28, 3, 0, tzinfo=UTC)
    l1 = K["L1"]
    andi_bln = next(x for x in l1["lines"] if x["sales_name"] == "Andi" and x["component_code"] == "BLN")
    r = await klien.post(URL, headers=f4["h"], json={"pay_period": "2026-12", "lines": []})
    assert r.status_code == 200, r.text
    l2 = r.json()
    r = await klien.post(f"{URL}/{l2['id']}/lines", headers=f4["h"], json={
        "is_adjustment": True, "adjusts": {"sheet_id": l1["id"], "line_id": andi_bln["id"]}, "amount": -500_000,
        "note": "retur Oktober dikoreksi"})
    assert r.status_code == 200, r.text
    for aksi in ("submit", "approve"):
        r = await klien.post(f"{URL}/{l2['id']}/{aksi}", headers=f4["h"], json={})
        assert r.status_code == 200, r.text
    j = r.json()
    assert (j["status"], j["gl_status"], j["journal_date"]) == ("approved", "posted", "2026-10-31"), j
    je = (await _jurnal(db, "incentive_sheet", l2["id"]))[0]
    assert _baris(je) == [("2-1500", 500_000, 0), ("6-5000", 0, 500_000)]
    run = await _proses(klien, f4["h"], "2026-12")
    andi = _slip(run, "Andi")
    # Desember = masa pajak terakhir: PPh setahun 0, yang sudah dipotong 200.000 dikembalikan (hitungan di kepala berkas)
    assert (andi["commission"], andi["gross"], andi["pph21"], andi["net"]) == (-500_000, 4_500_000, -200_000, 4_700_000)
    assert andi["pph21_method"] == "annual_pasal17"
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=f4["h"], json={})
    assert r.status_code == 200, r.text
    je = (await _jurnal(db, "payroll_run", run["id"]))[0]
    assert _baris(je) == [("2-1500", 0, 500_000), ("2-1600", 0, 9_827_500), ("2-1800", 327_500, 0),
                          ("6-1000", 10_000_000, 0)], _baris(je)
    assert await _saldo(db, KANDA, "2-1500") == 0
    assert (await db.incentive_sheets.find_one({"id": l2["id"]}, {"_id": 0, "status": 1}))["status"] == "paid"


# ═══ U11 — anulir proses gaji 2026-11 ═════════════════════════════════════════════════════════════════════════════
async def test_KMT4_U11_anulir_melepas_lembar(klien, db, f4):
    r = await klien.post(f"/api/hr/payroll/runs/{K['run_nov']}/void", headers=f4["h"],
                         json={"reason": "salah hitung insentif"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "void"
    inp = await _masukan(db, K["L1"]["id"])
    assert {(x["status"], x["used_run_id"]) for x in inp} == {("approved", "")}, inp
    l1 = await db.incentive_sheets.find_one({"id": K["L1"]["id"]}, {"_id": 0})
    assert l1["status"] == "approved" and not any(x.get("paid_run_id") for x in l1["lines"]), l1
    assert await _saldo(db, KANDA, "2-1500") == -8_500_000   # kredit 8.500.000 (debit − kredit)


# ═══ U6 — PT bermode bawaan: lembar = keputusan saja ══════════════════════════════════════════════════════════════
async def test_KMT4_U6_pt_bawaan_tanpa_jurnal_tanpa_masukan(klien, db, f4):
    s = await _lembar(klien, f4, "2026-11", [("citra", "BLN_KSC", "month", "2026-10", 2_000_000)], h=f4["h_ksc"])
    r = await klien.post(f"{URL}/{s['id']}/approve", headers=f4["h_ksc"], json={})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["status"], j["payroll_linked"], j["gl_status"]) == ("approved", False, "not_required"), j
    assert await _jurnal(db, "incentive_sheet", s["id"]) == []
    assert await _masukan(db, s["id"]) == []
    K["L_ksc"] = j


# ═══ U7 — pratinjau gaji: `accrue_then_settle` memuat komisi mesin, `off` tidak ═══════════════════════════════════
async def test_KMT4_U7_mode_off_mematikan_komisi_mesin(klien, db, f4):
    await _data_mesin(db, KSC, f4["u"]["citra"], "citra")
    try:
        r = await klien.post("/api/hr/payroll/runs/preview", headers=f4["h_ksc"],
                             json={"entity_id": KSC, "period": "2026-11"})
        assert r.status_code == 200, r.text
        assert _slip(r.json(), "Citra")["commission"] == 500_000   # 1.000 m × Rp 500
        await _mode(KSC, "off")
        r = await klien.post("/api/hr/payroll/runs/preview", headers=f4["h_ksc"],
                             json={"entity_id": KSC, "period": "2026-11"})
        assert r.status_code == 200, r.text
        assert _slip(r.json(), "Citra")["commission"] == 0
    finally:
        await _hapus_data_mesin(db, "citra")
        await _mode(KSC, "off")


# ═══ U8 — sales tanpa karyawan tertaut ════════════════════════════════════════════════════════════════════════════
async def test_KMT4_U8_sales_tanpa_karyawan_ditolak(klien, db, f4):
    s = await _lembar(klien, f4, "2027-01", [("andi", "BLN", "month", "2026-08", 1_000_000),
                                             ("eko", "BLN", "month", "2026-08", 1_000_000)])
    r = await klien.post(f"{URL}/{s['id']}/approve", headers=f4["h"], json={})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == ("Eko belum tertaut ke data karyawan, jadi insentifnya tidak bisa masuk gaji. "
                                  "Tautkan akunnya di kartu karyawan.")
    cur = await db.incentive_sheets.find_one({"id": s["id"]}, {"_id": 0})
    assert cur["status"] == "submitted"
    assert await _masukan(db, s["id"]) == [] and await _jurnal(db, "incentive_sheet", s["id"]) == []
    # komponen INSENTIF nonaktif di PT induk → 400 (pesan spesifikasi)
    s2 = await _lembar(klien, f4, "2027-01", [("budi", "BLN", "month", "2026-08", 1_000_000)])
    await db.hr_pay_components.update_one({"entity_id": KANDA, "code": "INSENTIF"}, {"$set": {"is_active": False}})
    try:
        r = await klien.post(f"{URL}/{s2['id']}/approve", headers=f4["h"], json={})
    finally:
        await db.hr_pay_components.update_one({"entity_id": KANDA, "code": "INSENTIF"}, {"$set": {"is_active": True}})
    assert r.status_code == 400 and r.json()["detail"].startswith("Komponen gaji Insentif belum aktif di "), r.text
    assert (await db.incentive_sheets.find_one({"id": s2["id"]}, {"_id": 0}))["status"] == "submitted"
    K["L_budi_agu"] = s2


# ═══ U9 — akun 6-5000 nonaktif: tetap disahkan, jurnal gagal, ulang dari Posting Gagal ════════════════════════════
async def test_KMT4_U9_jurnal_gagal_diulang_sekali(klien, db, f4):
    s = await _lembar(klien, f4, "2027-01", [("andi", "BLN", "month", "2026-09", 1_000_000),
                                             ("budi", "BLN", "month", "2026-09", 1_500_000),
                                             ("andi", "KHS", "month", "2026-09", 500_000)])
    await nonaktifkan_akun(KANDA, "6-5000")
    try:
        r = await klien.post(f"{URL}/{s['id']}/approve", headers=f4["h"], json={})
    finally:
        await aktifkan_akun(KANDA, "6-5000")
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["status"], j["gl_status"]) == ("approved", "failed"), j
    assert "6-5000" in (j.get("gl_error") or ""), j
    assert len(await _masukan(db, s["id"])) == 3 and await _jurnal(db, "incentive_sheet", s["id"]) == []
    r = await klien.get("/api/finance/posting-failures", headers=f4["h"], params={"kind": "incentive_sheet"})
    assert r.status_code == 200 and [x["id"] for x in r.json()["items"]] == [s["id"]], r.text
    url = f"/api/finance/posting-failures/incentive_sheet/{s['id']}/retry"
    r = await klien.post(url, headers=f4["h"], json={})
    assert r.status_code == 200 and r.json()["gl_status"] == "posted", r.text
    assert len(await _jurnal(db, "incentive_sheet", s["id"])) == 1
    assert len(await _masukan(db, s["id"])) == 3
    r = await klien.post(url, headers=f4["h"], json={})
    assert r.status_code == 404, r.text


# ═══ U10 — periode tanggal jurnal tertutup ═══════════════════════════════════════════════════════════════════════
async def test_KMT4_U10_periode_tertutup(klien, db, f4):
    s = await _lembar(klien, f4, "2027-01", [("andi", "KHS", "month", "2026-10", 750_000)])
    c = await tutup_periode(KANDA, "2026-10")
    try:
        r = await klien.post(f"{URL}/{s['id']}/approve", headers=f4["h"], json={})
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == ("Periode Oktober 2026 sudah ditutup, jadi beban insentif tidak bisa dibukukan di "
                                  "bulan itu. Buka periodenya atau ubah pengaturan tanggal jurnal periodik.")
    assert (await db.incentive_sheets.find_one({"id": s["id"]}, {"_id": 0}))["status"] == "submitted"
    assert await _masukan(db, s["id"]) == []


# ═══ U12 — sales menjual di PT lain: tagihan antar-PT ═════════════════════════════════════════════════════════════
async def test_KMT4_U12_sales_lintas_pt_tagihan_antar_pt(klien, db, f4):
    await _mode(KSC, "sheet")
    awal_2500 = await _saldo(db, KANDA, "2-1500")
    s = await _lembar(klien, f4, "2026-11", [("dodi", "BLN", "month", "2026-10", 2_000_000)])
    r = await klien.post(f"{URL}/{s['id']}/approve", headers=f4["h"], json={})
    assert r.status_code == 200, r.text
    je = (await _jurnal(db, "incentive_sheet", s["id"]))[0]
    assert je["entity_id"] == KANDA and _baris(je) == [("2-1500", 0, 2_000_000), ("6-5000", 2_000_000, 0)]
    inp = await _masukan(db, s["id"])
    assert [(x["entity_id"], x["employee_id"], x["source_ref"]["charge_entity_id"]) for x in inp] == [
        (KSC, "emp_kmt4_dodi", KANDA)]
    # proses gaji ent_ksc → batal sekali dulu lewat anulir (tagihan terbuka belum dilunasi → ikut ditutup)
    run = await _proses(klien, f4["h_ksc"], "2026-11")
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=f4["h_ksc"], json={})
    assert r.status_code == 200, r.text
    run = r.json()
    je = (await _jurnal(db, "payroll_run", run["id"]))[0]
    assert je["entity_id"] == KSC
    assert _baris(je) == [("1-1250", 2_000_000, 0), ("2-1600", 0, 11_912_500), ("2-1800", 0, 87_500),
                          ("6-1000", 10_000_000, 0)], _baris(je)
    chg = await db.interco_charges.find({"source.run_id": run["id"]}, {"_id": 0}).to_list(5)
    assert len(chg) == 1, chg
    c = chg[0]
    assert (c["kind"], c["from_entity_id"], c["to_entity_id"], c["amount"], c["outstanding"], c["status"]) == (
        "incentive", KSC, KANDA, 2_000_000, 2_000_000, "open"), c
    assert re.search(r"ICC-\d+$", c["number"]) and c["gl_status"] == "posted", c
    tw = await _jurnal(db, "interco_incentive_charge", c["id"])
    assert len(tw) == 1 and tw[0]["entity_id"] == KANDA
    assert _baris(tw[0]) == [("2-1250", 0, 2_000_000), ("2-1500", 2_000_000, 0)]
    assert any(ln.get("memo") == c["number"] for ln in je["lines"] if ln["account_code"] == "1-1250")
    assert await _saldo(db, KANDA, "2-1500") == awal_2500   # beban L3 diakui lalu dilunasi tagihan: Δ 0
    l3 = await db.incentive_sheets.find_one({"id": s["id"]}, {"_id": 0})
    assert l3["status"] == "paid" and l3["lines"][0]["paid_run_id"] == run["id"]
    # tagihan ikut saldo non-dagang & eliminasi konsolidasi
    from services import interco_money_service as money
    nt = await money.non_trade_outstanding(KSC, KANDA)
    assert (nt["charge_outstanding"], nt["charge_count"]) == (2_000_000, 1), nt
    assert await db.intercompany_eliminations.count_documents({"source_non_trade_key": f"icc:{c['id']}"}) == 1
    # anulir proses ent_ksc: jurnal kembar dibalik, tagihan ditutup, lembar kembali disahkan
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/void", headers=f4["h_ksc"], json={"reason": "uji anulir"})
    assert r.status_code == 200, r.text
    c = await db.interco_charges.find_one({"id": c["id"]}, {"_id": 0})
    assert (c["status"], c["outstanding"], c.get("void_gl_status")) == ("cancelled", 0, "posted"), c
    assert await _jurnal(db, "interco_incentive_charge_reversal", c["id"]) != []
    assert await db.intercompany_eliminations.count_documents({"source_non_trade_key": f"icc:{c['id']}"}) == 0
    assert (await db.incentive_sheets.find_one({"id": s["id"]}, {"_id": 0}))["status"] == "approved"
    assert await _saldo(db, KANDA, "2-1500") == awal_2500 - 2_000_000
    # proses baru → tagihan baru
    run = await _proses(klien, f4["h_ksc"], "2026-11")
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=f4["h_ksc"], json={})
    assert r.status_code == 200, r.text
    c = await db.interco_charges.find_one({"source.run_id": run["id"]}, {"_id": 0})
    assert (c["status"], c["outstanding"]) == ("open", 2_000_000), c
    assert await _saldo(db, KANDA, "2-1500") == awal_2500
    K["icc"], K["run_ksc"], K["L3"] = c, run["id"], s["id"]


# ═══ U13 — pelunasan tagihan + INV-KM-5 ═══════════════════════════════════════════════════════════════════════════
async def test_KMT4_U13_pelunasan_dan_invarian(klien, db, f4, capsys):
    from services import interco_charge_service as icc
    c = K["icc"]
    awal = {k: await _saldo(db, e, a) for k, e, a in (("ar", KSC, "1-1250"), ("ap", KANDA, "2-1250"))}
    assert awal == {"ar": 2_000_000, "ap": -2_000_000}, awal
    r = await klien.get("/api/interco/charges", headers=f4["h"])
    assert r.status_code == 200, r.text
    rows = r.json()["items"]   # terbaru dulu: tagihan proses kedua, lalu tagihan proses yang dianulir (U12)
    assert [(x["id"], x["status_label"]) for x in rows][:1] == [(c["id"], "Belum lunas")], rows
    assert r.json()["total"] == 2 and rows[1]["status_label"] == "Dibatalkan", rows
    body = {"amount": 2_000_000, "date": "2026-11-20", "account_id_from": REK_KANDA, "account_id_to": REK_KSC}
    r = await klien.post(f"/api/interco/charges/{c['id']}/settle", headers=f4["h"], json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["status"], j["outstanding"]) == ("settled", 0), j
    kas = await db.cash_transactions.find({"ref_type": "interco_incentive_charge_settlement"},
                                          {"_id": 0}).to_list(5)
    assert sorted((k["entity_id"], k["direction"], k["amount"]) for k in kas) == [
        (KANDA, "out", 2_000_000), (KSC, "in", 2_000_000)], kas
    assert await _saldo(db, KSC, "1-1250") == 0 and await _saldo(db, KANDA, "2-1250") == 0
    assert all(x["ok"] for x in await icc.rekonsiliasi())
    assert await db.intercompany_eliminations.count_documents({"source_non_trade_key": f"icc:{c['id']}"}) == 0
    sys.path.insert(0, str(REPO / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    gagal = vdi.results["fail"]
    await vdi.layer_incentive_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == gagal and re.search(r"PASS.*INV-KM-5", keluar), keluar
    # sudah dilunasi → anulir proses ent_ksc ditolak (pesan spesifikasi)
    r = await klien.post(f"/api/hr/payroll/runs/{K['run_ksc']}/void", headers=f4["h_ksc"], json={"reason": "uji tolak"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == (f"Tagihan antar-PT {c['number']} sudah dilunasi sebagian. Batalkan pelunasannya dulu.")
    # lunas → pelunasan kedua ditolak
    r = await klien.post(f"/api/interco/charges/{c['id']}/settle", headers=f4["h"], json=body)
    assert r.status_code == 409, r.text
    # bukti-merah INV-KM-5: sisa tagihan diubah tanpa jurnal
    await db.interco_charges.update_one({"id": c["id"]}, {"$set": {"status": "open", "outstanding": 500_000}})
    await vdi.layer_incentive_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == gagal + 1 and re.search(r"FAIL.*INV-KM-5", keluar), keluar
    await db.interco_charges.update_one({"id": c["id"]}, {"$set": {"status": "settled", "outstanding": 0}})


# ═══ U16 (pengganti lapis B; lapis A = tests/test_bp_KMT4_sahkan_bersamaan_mongo.py) — dua pengesahan bersamaan ═══
async def test_KMT4_U16_dua_pengesahan_bersamaan_lapis_b(klien, db, f4):
    import asyncio
    s = await _lembar(klien, f4, "2027-01", [("budi", "KHS", "month", "2026-08", 400_000)])
    hasil = await asyncio.gather(*[klien.post(f"{URL}/{s['id']}/approve", headers=f4["h"], json={}) for _ in range(2)])
    assert sorted(r.status_code for r in hasil) == [200, 409], [r.text for r in hasil]
    kalah = next(r for r in hasil if r.status_code == 409).json()["detail"]
    assert kalah in (f"Lembar {s['number']} sedang diproses. Muat ulang.",
                     f"Lembar {s['number']} berstatus Disahkan, jadi tidak bisa diubah."), kalah
    assert len(await _jurnal(db, "incentive_sheet", s["id"])) == 1 and len(await _masukan(db, s["id"])) == 1
    # NIAT yang terhenti di tengah (`approving`, jatah kerja habis) diteruskan oleh Sahkan berikutnya — tanpa dobel
    s2 = await _lembar(klien, f4, "2027-01", [("budi", "KHS", "month", "2026-07", 600_000)])
    await db.incentive_sheets.update_one({"id": s2["id"]}, {"$set": {"status": "approving", "payroll_linked": True,
                                                                      "journal_date": "2026-07-31", "gl_status": "pending",
                                                                      "approved_by": {"id": "u", "name": "Uji"},
                                                                      "approving_lease_until": "2000-01-01T00:00:00+00:00",
                                                                      "lines.0.employee_id": "emp_kmt4_budi",
                                                                      "lines.0.pay_entity_id": KANDA,
                                                                      "lines.0.input_key": f"isheet:{s2['id']}:x"}})
    r = await klien.post(f"{URL}/{s2['id']}/approve", headers=f4["h"], json={})
    assert r.status_code == 200 and (r.json()["status"], r.json()["gl_status"]) == ("approved", "posted"), r.text
    assert len(await _jurnal(db, "incentive_sheet", s2["id"])) == 1 and len(await _masukan(db, s2["id"])) == 1


# ═══ (b) langkah 4 — `incentive_unit` dicabut dari API tarif; kuncinya "tidak dipakai" ════════════════════════════
async def test_KMT4_b_satuan_insentif_dicabut(klien, db, f4):
    import config_registry as registry
    e = registry.require("commission.incentive_unit")
    assert e.get("status") == "not_used", e.get("status")
    assert e.get("not_used_reason") == "Tarif komisi dihitung dari satuan dasar barang; isian ini tidak dipakai."
    r = await klien.post("/api/incentive-rates", headers=f4["h"], json={
        "entity_id": KANDA, "category": "KMT4-SATUAN", "per_unit_amount": 750, "incentive_unit": "yard"})
    assert r.status_code == 200, r.text
    assert "incentive_unit" not in r.json(), r.json()
    assert "incentive_unit" not in (await db.incentive_rates.find_one({"category": "KMT4-SATUAN"}, {"_id": 0}))
    r = await klien.get("/api/incentive-rates", headers=f4["h"])
    assert r.status_code == 200 and all("incentive_unit" not in x for x in r.json()), r.text


# ═══ U14 — akrual manual ditolak di PT bermode `sheet` ════════════════════════════════════════════════════════════
async def test_KMT4_U14_akrual_manual_ditolak(klien, db, f4):
    r = await klien.post("/api/sales/incentive/post-gl", headers=f4["h"], params={"period": "2026-10"})
    assert r.status_code == 409, r.text
    assert await db.journal_entries.count_documents({"source_type": "incentive_accrual"}) == 0


# ═══ Kesiapan beralih (langkah 5) ═════════════════════════════════════════════════════════════════════════════════
async def test_KMT4_kesiapan_beralih(klien, db, f4, peran_manajer_kosong, akun, sesi):
    r = await klien.get("/api/incentive/switch-readiness", headers=f4["h"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "sheet" and j["mode_label"] == "Dari Lembar Insentif yang disahkan"
    assert [c["code"] for c in j["checks"]] == ["pencocokan", "saldo_hutang", "tautan_karyawan", "proses_gaji"]
    hut = next(c for c in j["checks"] if c["code"] == "saldo_hutang")
    # saldo hutang insentif ent_kanda belum dibayar: L1 8.500.000 (proses Nov dianulir) + lembar U9 3.000.000
    # + lembar U16 400.000 + 600.000 = 12.500.000
    assert hut["ok"] is False and "Rp 12.500.000" in hut["text"], hut
    tautan = next(c for c in j["checks"] if c["code"] == "tautan_karyawan")
    assert tautan["ok"] is False and "Eko" in tautan["text"], tautan   # lembar U8 masih diajukan
    hk = await sesi(await akun(await peran_manajer_kosong(), entitas=(KANDA,)), entitas=KANDA)
    r = await klien.get("/api/incentive/switch-readiness", headers=hk)
    assert r.status_code == 403, r.text


# ═══ U15 — kunci mode: putaran, alasan, izin ══════════════════════════════════════════════════════════════════════
async def test_KMT4_U15_kunci_mode(klien, kepala_admin, peran_tanpa_acuan, akun, sesi):
    import config_registry as registry
    from test_KFT8_putaran_pengaturan import putaran
    e = registry.require(MODE)
    assert [(o["value"], o["label"]) for o in e["options"]] == [
        ("accrue_then_settle", "Komisi otomatis: dicadangkan, dilunasi lewat gaji"),
        ("pay_on_invoice", "Dibayar saat faktur terbit"), ("off", "Tidak ada komisi di gaji"),
        ("sheet", "Dari Lembar Insentif yang disahkan")]
    assert (e["group"], e["type"], e["default"], e["scopes"], e["risk"], e["requires_reason"], e["permission"],
            e["label"], e["consumers"]) == (
        "sdm", "enum", "accrue_then_settle", ["global", "entity"], "high", True, ["hr", "manage_payroll"],
        "Cara insentif sales masuk penggajian", ["services/hr_payroll_service.py:commission_mode"])
    gagal = await putaran(klien, kepala_admin, MODE)
    assert not gagal, "\n".join(gagal)
    item = {"key": MODE, "value": "sheet", "scope_type": "entity", "scope_id": KANDA}
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [item]})
    assert r.status_code == 400, r.text
    rid = await peran_tanpa_acuan({"settings": ["view", "manage"]}, label="Pengatur tanpa gaji KM-T4")
    h = await sesi(await akun(rid, entitas=(KANDA,)), entitas=KANDA)
    r = await klien.put("/api/config/values", headers=h, json={"items": [{**item, "reason": "uji izin KM-T4"}]})
    assert r.status_code == 403, r.text
