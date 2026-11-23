"""KM-T5 — kartu "Capaian & Insentif Saya" untuk sales; layar insentif lama dipindah atau dihapus (lingkungan B).

Spesifikasi `docs/blueprint/unit/KM-T5.md`, uji penerimaan U1–U12 (U13–U14 = uji komponen jest
`features/__tests__/kmt5KartuSales.test.js`; U15–U16 = uji jalan peramban oleh integrator, pengganti komponennya ikut di
berkas jest yang sama).

Fixture (DISISIPKAN langsung, pola KM-T2 F2 dan KM-T4): `ent_kanda` bermode `sheet` (`config_resolver.set_value`,
beralasan); `ent_ksc` bermode bawaan (`accrue_then_settle`). "Hari ini" dibekukan 5 Nov 2026 10.00 WIB lewat
`services.book_date._sekarang` (periode bawaan kartu & tanggal buku) dan `services.home_service.now_wib` (bulan
berjalan beranda). Andi (sales `ent_kanda` + `ent_ksc`) dan Budi (sales `ent_kanda`) punya karyawan `ent_kanda` (gaji
pokok 5.000.000, TK0, BPJS mati per karyawan); karyawan seed kedua PT dinonaktifkan supaya proses gaji uji hanya memuat
karyawan uji. Pesanan, surat jalan, kwitansi disisip/dibuat lewat fungsi asli lalu fakta insentif dibangun ulang.
Lembar, pengesahan, dan proses gaji lewat HTTP (alur).

Hitung tangan (semua harga jual Rp 50.000/yd):
  OA1 Andi 20.000 yd × 50.000 = 1.000.000.000; harga daftar 58.000 → acuan 20.000 × 58.000 = 1.160.000.000; dibuat
      28 Sep, terkirim penuh 12 Okt. OB1 Budi 10.000 yd = 500.000.000 (daftar 50.000), terkirim 9 Okt.
  Kwitansi RA1 20 Okt 700.000.000 → OA1 · RB1 15 Okt 500.000.000 → OB1.
  Target Okt 2026: Andi 800.000.000 / 750.000.000 · Budi 500.000.000 / 450.000.000.
  U1  Andi Okt: omzet bersih 1.000 jt; 1.000/800 = 125,0 %; uang masuk 700 jt; 700/750 = 93,33 → 93,3 %;
      realisasi harga 1.000/1.160 = 86,21 → 86,2 %.
  L1  (`pay_period` 2026-11): Andi "Insentif Bulanan" Okt 2026 2.000.000 + Andi "Insentif Triwulan" Triwulan III 2026
      3.000.000 + Budi "Insentif Bulanan" Okt 2026 3.500.000 = 8.500.000.
  U2  baris Andi 2.000.000 + 3.000.000 = 5.000.000. U3 baris Budi 3.500.000.
  U5  Citra (`ent_ksc`): tarif Rp 500 per meter, batas margin 0, pesanan 1.000 m lunas 10 Nov → 1.000 × 500 = 500.000.
  U10 Σ baris L1 belum dibayar = 8.500.000; sesudah gaji November diposting = 0.
"""
from __future__ import annotations

import contextlib
import datetime
import io
import json
import re
import runpy
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI

pytestmark = pytest.mark.anyio

KANDA, KSC = "ent_kanda", "ent_ksc"
MODE = "hr.payroll_commission_mode"
URL_ME = "/api/incentive/me"
URL_SHEETS = "/api/incentive/sheets"
PRD = "prd_kmt5_kain"
CA, CB = "cus_kmt5_andi", "cus_kmt5_budi"
OA1, OB1 = "so_kmt5_oa1", "so_kmt5_ob1"
REK = "rek_kmt5_kanda"
REPO = Path(__file__).resolve().parents[2]
UTC = datetime.timezone.utc
WIB = datetime.timezone(datetime.timedelta(hours=7))
JAM = datetime.datetime(2026, 11, 5, 3, 0, tzinfo=UTC)   # 5 Nov 2026 10.00 WIB
PESAN_TANPA_KOMISI = "PT ini tidak memakai komisi otomatis. Lihat Capaian & Insentif."
UANG = ("target_sales", "omzet_bersih", "target_collection", "uang_masuk")
PERSEN = ("pct_omzet", "pct_pencairan", "realisasi_harga_pct")
K: Dict[str, Any] = {}


@pytest.fixture(scope="module", autouse=True)
def _jam():
    from services import book_date, home_service
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: JAM)
        mp.setattr(home_service, "now_wib", lambda: JAM.astimezone(WIB))
        yield


def _iso(tgl: str, jam: str = "03:00:00") -> str:
    return f"{tgl}T{jam}+00:00"


def _item(qty: int, list_price: float) -> Dict[str, Any]:
    return {"product_id": PRD, "sku": "KMT5-01", "product_name": "Kain Uji KM-T5", "quantity": qty, "base_quantity": qty,
            "unit": "yard", "base_unit": "yard", "price": 50_000, "line_total": qty * 50_000, "list_price": list_price,
            "list_price_source": "entity", "global_price": 60_000, "floor_price": 45_000, "unit_cost": 35_000,
            "price_source": "entity", "category": "Katun", "line_code": "woven"}


async def _pesanan_terkirim(db, gl, so_id: str, cust: str, sales_id: str, qty: int, list_price: float,
                            dibuat: str, dikirim: str) -> None:
    """Pesanan satu baris, terkirim penuh dengan satu surat jalan; jurnal pendapatan lewat fungsi posting asli."""
    nomor = f"SO/KMT5/{so_id[-3:].upper()}"
    await db.sales_orders.insert_one({
        "id": so_id, "number": nomor, "entity_id": KANDA, "customer_id": cust, "customer_name": f"Toko {cust[-4:]}",
        "status": "shipped", "payment_term_code": "NET30", "items": [_item(qty, list_price)], "subtotal": qty * 50_000,
        "grand_total": qty * 50_000, "ppn_amount": 0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid",
        "sales_team": [{"sales_id": sales_id, "role": "pic", "split_pct": 100.0}],
        "created_at": _iso(dibuat), "updated_at": now_iso()})
    await db.shipments.insert_one({"id": f"shp_{so_id}", "shipment_no": f"SJ/KMT5/{so_id[-3:].upper()}",
                                   "entity_id": KANDA, "order_id": so_id, "order_number": nomor, "product_id": PRD,
                                   "qty": qty, "unit": "yard", "status": "dispatched", "created_at": _iso(dikirim)})
    await gl.post_order_revenue_and_cogs(so_id)


async def _karyawan(db, eid: str, user: Dict[str, Any], kode: str) -> None:
    await db.hr_employees.insert_one({
        "id": f"emp_kmt5_{kode}", "code": f"EMP-KMT5-{kode.upper()}", "name": user["name"], "entity_id": eid,
        "user_id": user["id"], "status": "active", "base_salary": 5_000_000, "allowances": [], "ptkp_status": "TK0",
        "bpjs_kes_enabled": False, "bpjs_tk_enabled": False, "join_date": "2025-01-01",
        "created_at": "2025-01-01T00:00:00+00:00"})


async def _data_mesin(db, eid: str, sales: Dict[str, Any], kode: str) -> None:
    """Komisi otomatis: tarif Rp 500 per meter (batas margin 0) dan pesanan sales 1.000 m lunas 10 Nov 2026 (pola KM-T4)."""
    kat = f"KMT5-{kode}"
    await db.incentive_rates.insert_one({"id": f"rate_kmt5_{kode}", "entity_id": eid, "category": kat,
                                         "per_unit_amount": 500.0, "margin_cap_pct": 0.0, "discount_threshold": 100.0,
                                         "discount_threshold_type": "pct", "discount_mechanic": "tier_factor",
                                         "discount_factor": 1.0, "status": "active"})
    await db.customers.insert_one({"id": f"cus_kmt5_{kode}", "name": f"Toko KM-T5 {kode}", "entity_id": eid,
                                   "status": "active", "assigned_sales_id": sales["id"]})
    await db.sales_orders.insert_one({
        "id": f"so_kmt5_{kode}", "number": f"SO/KMT5/{kode}", "entity_id": eid, "customer_id": f"cus_kmt5_{kode}",
        "status": "completed", "items": [{"product_id": f"prd_kmt5_{kode}", "sku": "KMT5M", "category": kat,
                                          "product_name": "Kain KM-T5", "quantity": 1000, "base_quantity": 1000,
                                          "unit": "meter", "price": 50_000, "line_total": 50_000_000,
                                          "discount_percent": 0, "unit_cost": 30_000}],
        "subtotal": 50_000_000, "grand_total": 50_000_000, "payments": [
            {"amount": 50_000_000, "created_at": "2026-11-10T03:00:00+00:00"}],
        "created_at": "2026-11-02T03:00:00+00:00"})


@pytest.fixture(scope="module")
async def f5(db, akun, sesi):
    from services import analytics_facts, incentive_facts
    from services import ar_receipt_service as ars
    from services import config_resolver as resolver
    from services import gl_service as gl
    from services import incentive_targets as itg
    await resolver.set_value(MODE, "sheet", scope_type="entity", scope_id=KANDA, actor="uji", reason="uji KM-T5")
    await resolver.set_value("payment.variance_tolerance_rupiah", 0, scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji KM-T5")
    await db.hr_employees.update_many({"entity_id": {"$in": [KANDA, KSC]}}, {"$set": {"status": "inactive"}})
    await db.bank_accounts.insert_one({"id": REK, "name": "BCA Kanda KM-T5", "entity_id": KANDA, "account_type": "bank",
                                       "cash_type": "kas_besar", "is_active": True, "opening_balance": 0})
    u: Dict[str, Dict[str, Any]] = {}
    for kode, nama, peran, ents in (("andi", "Andi", "sales", (KANDA, KSC)), ("budi", "Budi", "sales", (KANDA,)),
                                    ("citra", "Citra", "sales", (KSC,)), ("gudang", "Gani Gudang", "warehouse", (KANDA,))):
        u[kode] = await akun(peran, entitas=ents)
        await db.users.update_one({"id": u[kode]["id"]}, {"$set": {"name": nama}})
        u[kode]["name"] = nama
    await _karyawan(db, KANDA, u["andi"], "andi")
    await _karyawan(db, KANDA, u["budi"], "budi")
    await db.products.insert_one({"id": PRD, "name": "Kain Uji KM-T5", "sku": "KMT5-01", "base_unit": "yard",
                                  "price": 60_000, "category": "Katun", "line_code": "woven", "is_active": True})
    await db.customers.insert_many([
        {"id": CA, "name": "Toko Andi KM-T5", "entity_id": KANDA, "status": "active", "deposit_balance": 0.0,
         "assigned_sales_id": u["andi"]["id"], "created_at": _iso("2026-01-05"),
         "sales_team": [{"sales_id": u["andi"]["id"], "role": "pic", "split_pct": 100.0}]},
        {"id": CB, "name": "Toko Budi KM-T5", "entity_id": KANDA, "status": "active", "deposit_balance": 0.0,
         "assigned_sales_id": u["budi"]["id"], "created_at": _iso("2026-01-05"),
         "sales_team": [{"sales_id": u["budi"]["id"], "role": "pic", "split_pct": 100.0}]}])
    await _pesanan_terkirim(db, gl, OA1, CA, u["andi"]["id"], 20_000, 58_000, "2026-09-28", "2026-10-12")
    await _pesanan_terkirim(db, gl, OB1, CB, u["budi"]["id"], 10_000, 50_000, "2026-10-05", "2026-10-09")
    for cust, so, nilai, tgl in ((CA, OA1, 700_000_000, "2026-10-20"), (CB, OB1, 500_000_000, "2026-10-15")):
        await ars.create_receipt({"customer_id": cust, "entity_id": KANDA, "amount": nilai, "method": "transfer",
                                  "account_id": REK, "allocations": [{"order_id": so, "amount": nilai}],
                                  "receipt_date": tgl}, AKTOR_UJI)
    for sid, omzet, cair in ((u["andi"]["id"], 800e6, 750e6), (u["budi"]["id"], 500e6, 450e6)):
        await itg.save_target(KANDA, {"sales_id": sid, "period_type": "month", "period": "2026-10",
                                      "target_sales_amount": omzet, "target_collection_amount": cair}, AKTOR_UJI)
    await incentive_facts.rebuild()
    await analytics_facts.rebuild_facts()
    komp = {}
    for kode, nama, jenis in (("BLN", "Insentif Bulanan", "month"), ("TW", "Insentif Triwulan", "quarter")):
        komp[kode] = await itg.create_component(KANDA, {"code": kode, "name": nama, "basis_period_type": jenis,
                                                        "columns": ["omzet"]}, AKTOR_UJI)
    komp["BLN_KSC"] = await itg.create_component(KSC, {"code": "BLN", "name": "Insentif Bulanan",
                                                       "basis_period_type": "month", "columns": ["omzet"]}, AKTOR_UJI)
    await _data_mesin(db, KSC, u["citra"], "citra")
    h = {k: await sesi(v, entitas=KANDA if k != "citra" else KSC) for k, v in u.items()}
    return {"u": u, "komp": komp, "h": h,
            "adm": await sesi("admin@kainnusantara.id", entitas=KANDA),
            "adm_ksc": await sesi("admin@kainnusantara.id", entitas=KSC)}


# ── pembantu ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _me(klien, h, **params) -> Dict[str, Any]:
    r = await klien.get(URL_ME, headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def _lembar(klien, f5, h, pay: str, isi: List[tuple]) -> Dict[str, Any]:
    """Lembar draf → nominal diketik → diajukan. `isi` = [(sales, komponen, jenis periode, periode, nominal)]."""
    lines = [{"sales_id": f5["u"][s]["id"], "component_id": f5["komp"][c]["id"], "basis_period_type": pt,
              "basis_period": p} for s, c, pt, p, _n in isi]
    r = await klien.post(URL_SHEETS, headers=h, json={"pay_period": pay, "lines": lines})
    assert r.status_code == 200, r.text
    s = r.json()
    for x, ln in zip(isi, s["lines"]):
        r = await klien.patch(f"{URL_SHEETS}/{s['id']}/lines/{ln['id']}", headers=h, json={"amount": x[4]})
        assert r.status_code == 200, r.text
    r = await klien.post(f"{URL_SHEETS}/{s['id']}/submit", headers=h, json={})
    assert r.status_code == 200, r.text
    return r.json()


async def _sahkan(klien, h, sheet_id: str) -> Dict[str, Any]:
    r = await klien.post(f"{URL_SHEETS}/{sheet_id}/approve", headers=h, json={})
    assert r.status_code == 200, r.text
    return r.json()


def _baris(j: Dict[str, Any]) -> List[tuple]:
    return sorted((ln["component_name"], ln["basis_label"], ln["amount"]) for s in j["sheets"] for ln in s["lines"])


# ═══ U1 — capaian Oktober Andi; lembar masih diajukan tidak terkirim ═══════════════════════════════════════════════
async def test_KMT5_U1_capaian_oktober_tanpa_lembar_diajukan(klien, f5):
    K["L1"] = await _lembar(klien, f5, f5["adm"], "2026-11", [("andi", "BLN", "month", "2026-10", 2_000_000),
                                                             ("andi", "TW", "quarter", "2026-Q3", 3_000_000),
                                                             ("budi", "BLN", "month", "2026-10", 3_500_000)])
    assert K["L1"]["status"] == "submitted"
    j = await _me(klien, f5["h"]["andi"], period="2026-10")
    a = j["achievement"]
    assert tuple(a[k] for k in ("target_sales", "omzet_bersih", "pct_omzet", "target_collection", "uang_masuk",
                                "pct_pencairan", "realisasi_harga_pct")) == (
        800_000_000, 1_000_000_000, 125.0, 750_000_000, 700_000_000, 93.3, 86.2), a
    assert "margin_pct" not in a and "sisa_piutang" not in a and a["facts_as_of"], a
    assert (j["period"], j["entity_id"], j["mode"], j["sheets"], j["auto_commission"]) == (
        "2026-10", KANDA, "sheet", [], None), j
    # lembar `submitted` tidak pernah dikirim, juga pada periode bayarnya
    assert (await _me(klien, f5["h"]["andi"], period="2026-11"))["sheets"] == []


# ═══ U2 — lembar disahkan: hanya baris milik pelaku ════════════════════════════════════════════════════════════════
async def test_KMT5_U2_lembar_disahkan_baris_milik_sendiri(klien, f5):
    K["L1"] = await _sahkan(klien, f5["adm"], K["L1"]["id"])
    assert (K["L1"]["status"], K["L1"]["payroll_linked"]) == ("approved", True)
    j = await _me(klien, f5["h"]["andi"], period="2026-11")
    assert len(j["sheets"]) == 1, j["sheets"]
    s = j["sheets"][0]
    assert (s["sheet_number"], s["pay_period"], s["status"]) == (K["L1"]["number"], "2026-11", "approved"), s
    assert _baris(j) == [("Insentif Bulanan", "Okt 2026", 2_000_000), ("Insentif Triwulan", "Triwulan III 2026", 3_000_000)]
    assert sum(ln["amount"] for ln in s["lines"]) == 5_000_000
    assert j["auto_commission"] is None and j["mode"] == "sheet"
    bln = next(ln for ln in s["lines"] if ln["basis_label"] == "Okt 2026")
    assert bln["snapshot"] == {"target_sales": 800_000_000, "omzet_bersih": 1_000_000_000,
                               "target_collection": 750_000_000, "uang_masuk": 700_000_000,
                               "realisasi_harga_pct": 86.2}, bln["snapshot"]
    assert (bln["is_adjustment"], bln["note"], bln["paid_run_number"]) == (False, "", ""), bln
    assert set(bln) == {"component_name", "basis_label", "amount", "is_adjustment", "note", "paid_run_number",
                        "snapshot"}, bln
    teks = json.dumps(j)
    assert "Budi" not in teks and "3500000" not in teks, teks


# ═══ U3 — parameter sales_id diabaikan ═════════════════════════════════════════════════════════════════════════════
async def test_KMT5_U3_sales_id_diabaikan(klien, f5):
    j = await _me(klien, f5["h"]["budi"], period="2026-11", sales_id=f5["u"]["andi"]["id"])
    assert _baris(j) == [("Insentif Bulanan", "Okt 2026", 3_500_000)], j["sheets"]
    j10 = await _me(klien, f5["h"]["budi"], period="2026-10", sales_id=f5["u"]["andi"]["id"])
    assert (j10["achievement"]["target_sales"], j10["achievement"]["omzet_bersih"]) == (500_000_000, 500_000_000)


# ═══ U10 (a) — beranda admin PT bermode `sheet`: lembar disahkan belum dibayar ═════════════════════════════════════
async def test_KMT5_U10a_beranda_admin_belum_dibayar(klien, f5):
    r = await klien.get("/api/home/admin", headers=f5["adm"])
    assert r.status_code == 200, r.text
    assert (r.json()["incentive_payout"], r.json()["incentive_payout_label"]) == (8_500_000, "Belum dibayar"), {
        k: r.json().get(k) for k in ("incentive_payout", "incentive_payout_label")}
    r = await klien.get("/api/home/admin", headers=f5["adm_ksc"])   # PT bermode bawaan: tetap estimasi mesin
    assert r.status_code == 200, r.text
    assert r.json()["incentive_payout_label"] == "Estimasi bulan ini"
    assert r.json()["incentive_payout"] >= 500_000   # komisi Citra 1.000 m × Rp 500 ikut


# ═══ U4 — gaji November diposting: lembar dibayar, baris ber-nomor proses gaji ═════════════════════════════════════
async def test_KMT5_U4_gaji_diposting_lembar_dibayar(klien, f5):
    h = f5["adm"]
    r = await klien.post("/api/hr/payroll/runs", headers=h, json={"entity_id": KANDA, "period": "2026-11",
                                                                  "run_type": "regular"})
    assert r.status_code == 200, r.text
    run = r.json()
    for aksi in ("submit", "approve"):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", headers=h, json={})
        assert r.status_code == 200, r.text
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=h, json={})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "posted", run["status"]
    j = await _me(klien, f5["h"]["andi"], period="2026-11")
    s = j["sheets"][0]
    assert s["status"] == "paid", s
    assert {ln["paid_run_number"] for ln in s["lines"]} == {run["number"]}, s["lines"]
    K["run_nov"] = run


# ═══ U10 (b) — sesudah gaji diposting: 0 ═══════════════════════════════════════════════════════════════════════════
async def test_KMT5_U10b_beranda_admin_sesudah_gaji(klien, f5):
    r = await klien.get("/api/home/admin", headers=f5["adm"])
    assert r.status_code == 200, r.text
    assert (r.json()["incentive_payout"], r.json()["incentive_payout_label"]) == (0, "Belum dibayar")


# ═══ U5 — PT bermode komisi otomatis: komisi berjalan ═════════════════════════════════════════════════════════════
async def test_KMT5_U5_komisi_otomatis_pt_bawaan(klien, f5):
    j = await _me(klien, f5["h"]["citra"])   # periode bawaan = bulan berjalan WIB (beku: November 2026)
    assert (j["period"], j["entity_id"], j["mode"]) == ("2026-11", KSC, "accrue_then_settle"), j
    assert j["auto_commission"]["mtd"] == 500_000, j["auto_commission"]   # 1.000 m × Rp 500
    assert set(j["auto_commission"]) == {"mtd", "projection_month_end"}
    assert j["sheets"] == []


# ═══ U6 — beranda sales: mesin tidak dipanggil di PT bermode `sheet` ═══════════════════════════════════════════════
async def test_KMT5_U6_beranda_sales_menurut_mode(klien, f5, monkeypatch):
    from services import sales_force_service as sf
    dipanggil: List[str] = []
    asli = sf.compute_commission

    async def _hitung(uid, period, entity_id=None):
        dipanggil.append(uid)
        return await asli(uid, period, entity_id=entity_id)
    monkeypatch.setattr(sf, "compute_commission", _hitung)
    r = await klien.get("/api/home/sales", headers=f5["h"]["andi"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["incentive_mode"], j["commission"], j["history"]) == ("sheet", None, []), {
        k: j.get(k) for k in ("incentive_mode", "commission", "history")}
    assert dipanggil == [], dipanggil
    assert "total_sales" in j["kpi"] and "customers" in j   # bagian lain beranda tetap
    r = await klien.get("/api/home/sales", headers=f5["h"]["citra"])
    assert r.status_code == 200, r.text
    assert (r.json()["incentive_mode"], r.json()["commission"]["mtd_accrual"]) == ("accrue_then_settle", 500_000)


# ═══ U7 — akun tanpa pesanan: 200, angka 0 ═════════════════════════════════════════════════════════════════════════
async def test_KMT5_U7_akun_gudang_tanpa_pesanan(klien, f5):
    j = await _me(klien, f5["h"]["gudang"])
    a = j["achievement"]
    assert [a[k] for k in UANG] == [0, 0, 0, 0], a
    assert [a[k] for k in PERSEN] == [None, None, None], a   # persen tanpa pembagi = kosong (lihat laporan)
    assert j["sheets"] == []


# ═══ U8 — akun berperan kustom beracuan sales ikut daftar sales & papan peringkat ══════════════════════════════════
async def test_KMT5_U8_peran_kustom_acuan_sales(klien, akun, f5):
    r = await klien.post("/api/access/roles", headers=f5["adm"], json={
        "label": "Sales Lapangan KM-T5", "base_role": "sales", "description": "peran uji KM-T5"})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    senior = await akun(rid, entitas=(KANDA,))
    r = await klien.get("/api/sales-users", headers=f5["adm"])
    assert r.status_code == 200, r.text
    ids = {x["id"] for x in r.json()}
    assert {senior["id"], f5["u"]["andi"]["id"], f5["u"]["budi"]["id"]} <= ids, ids
    assert f5["u"]["citra"]["id"] not in ids   # sales PT lain tidak ikut
    r = await klien.get("/api/sales/leaderboard", headers=f5["adm"])
    assert r.status_code == 200, r.text
    papan = {x["sales_id"] for x in r.json()}
    assert senior["id"] in papan and f5["u"]["citra"]["id"] not in papan, papan
    r = await klien.get("/api/sales/my-rank", headers=f5["h"]["andi"])
    assert r.status_code == 200, r.text
    assert r.json()["total"] == len(papan)


# ═══ U9 — komisi otomatis ditolak di PT bermode `sheet` ════════════════════════════════════════════════════════════
async def test_KMT5_U9_komisi_otomatis_ditolak(klien, f5):
    for jalur, isi in (("/api/sales/commission", {"period": "2026-11"}),
                       ("/api/sales/commission-history", {"anchor": "2026-11"})):
        r = await klien.get(jalur, headers=f5["h"]["andi"], params=isi)
        assert r.status_code == 409, (jalur, r.text)
        assert r.json()["detail"] == PESAN_TANPA_KOMISI
    r = await klien.get("/api/sales/commission", headers=f5["h"]["citra"], params={"period": "2026-11"})
    assert r.status_code == 200 and r.json()["total_incentive"] == 500_000, r.text


# ═══ U11 — jalur lama `sales-targets` dihapus; tidak ada panggilan layar tanpa rute ════════════════════════════════
async def test_KMT5_U11_sales_targets_dihapus(klien, aplikasi, f5, tmp_path):
    r = await klien.post("/api/sales-targets", headers=f5["adm"], json={"sales_id": f5["u"]["andi"]["id"],
                                                                        "period": "2026-12", "target_sales_amount": 1})
    assert r.status_code in (404, 405), r.text
    r = await klien.get("/api/sales-targets", headers=f5["adm"])
    assert r.status_code in (404, 405), r.text
    # pencarian: tidak ada pemanggil tersisa di layar (jalur API lama, impor/pemakaian tiga layar lama yang dihapus)
    src = REPO / "frontend" / "src"
    lama = r"(SalesForceDashboard|IncentiveSchemeEditor|IncentiveRatesEditor)"
    pola = re.compile(rf"/sales-targets|crm/{lama}[\"']|<{lama}\b|\b{lama}\s*[,}}]")
    sisa = [str(p.relative_to(src)) for p in src.rglob("*.js*")
            if "__tests__" not in p.parts and pola.search(p.read_text(encoding="utf-8"))]
    assert sisa == [], sisa
    assert not [p for p in ("SalesForceDashboard", "IncentiveSchemeEditor", "IncentiveRatesEditor")
                if (src / "features" / "crm" / f"{p}.jsx").exists()]
    # `fe_be_routes.py` (audit konfigurasi peran): panggilan API layar dicocokkan dengan rute aplikasi ini. Dijalankan
    # lewat `runpy` supaya daftar lengkapnya terbaca (cetakannya dipotong 70 baris).
    inv = tmp_path / "rute.json"
    inv.write_text(json.dumps([{"path": rt.path, "method": m} for rt in aplikasi.routes
                               for m in (getattr(rt, "methods", None) or ())]))
    skrip = REPO / "docs/audit/konfigurasi-peran-2026-11-13/bukti/fe_be_routes.py"
    argv, cetak = sys.argv, io.StringIO()
    sys.argv = [str(skrip), str(inv)]
    try:
        with contextlib.redirect_stdout(cetak):
            g = runpy.run_path(str(skrip), run_name="__main__")
    finally:
        sys.argv = argv
    # KA-9 — `LegacyRatesEditor` dihapus (tarif & bawaan komisi kini tab Skema & Tarif); berkas layar barunya ikut diperiksa.
    berkas_unit = ("MyIncentiveCard", "LegacySchemeEditor", "IncentiveSetupView", "SalesHome",
                   "MobileCollectionTargets", "EmployeeSelfService", "AdminHome", "IncentiveSheetsView",
                   "IncentiveSchemeView", "ArticleRatesTable", "RateFormModal", "RatesExcelImport", "SchemeSimulation",
                   "SchemeSourcePicker", "KartuAkrual")
    tanpa = [x for x in g["miss"] if "sales-targets" in x[1] or any(b in x[2] for b in berkas_unit)]
    jalur_unit = ("/incentive/me", "/sales/commission", "/sales/incentive/", "/incentive-rates", "/sales-incentives",
                  "/sales-users", "/sales/my-rank", "/incentive/targets")
    beda = [x for x in g["wrong"] if any(x[1].startswith(j) for j in jalur_unit)]
    assert (tanpa, beda) == ([], []), (tanpa, beda)
    K["fe_be"] = re.search(r"TIDAK ADA rute: \d+", cetak.getvalue()).group(0)


# ═══ U12 — lembar PT lain tidak ikut ══════════════════════════════════════════════════════════════════════════════
async def test_KMT5_U12_hanya_lembar_pt_aktif(klien, f5):
    s = await _lembar(klien, f5, f5["adm_ksc"], "2026-11", [("andi", "BLN_KSC", "month", "2026-10", 1_000_000)])
    s = await _sahkan(klien, f5["adm_ksc"], s["id"])
    assert (s["status"], s["payroll_linked"]) == ("approved", False)
    j = await _me(klien, f5["h"]["andi"], period="2026-11")
    assert [x["sheet_number"] for x in j["sheets"]] == [K["L1"]["number"]], j["sheets"]
    assert j["entity_id"] == KANDA
    j = await _me(klien, {**f5["h"]["andi"], "X-Entity-Id": KSC}, period="2026-11")
    assert (j["entity_id"], j["mode"], [x["sheet_number"] for x in j["sheets"]]) == (
        KSC, "accrue_then_settle", [s["number"]]), j
    assert _baris(j) == [("Insentif Bulanan", "Okt 2026", 1_000_000)]


# ═══ Tambahan — periode salah ditolak dengan kalimat; endpoint hanya butuh login (Z3) ══════════════════════════════
async def test_KMT5_periode_salah_dan_login(klien, f5):
    r = await klien.get(URL_ME, headers=f5["h"]["andi"], params={"period": "2026-Q4"})
    assert r.status_code == 400 and r.json()["detail"] == "Periode harus satu bulan, contoh: 2026-10.", r.text
    r = await klien.get(URL_ME)
    assert r.status_code == 401, r.text
    import login_only_endpoints as lo
    assert lo.LOGIN_ONLY[("GET", URL_ME)] == "milik_sendiri"
