"""KA-12 — perbaikan tinjauan akhir komisi per artikel (mesin & isi awal): I1, I2, M1, M2.

Rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §6.5a, §8 butir 8 & 15; ledger R19.

Fixture (DISISIP langsung, pola KA-4/KA-7): PT `ent_kanda` dengan mode gaji bawaan (`accrue_then_settle`), dua sales
(Andi, Budi) tertaut karyawan; produk `prd_ka12_bt` berkategori `KA12Batik`; tarif kategori PT Rp 500/yd (batas margin 0,
ambang diskon 100 %).

Hitung tangan:
  I1  pesanan lama dua baris 100 yd lunas Nov: L1 `category` = "" (kunci ADA) → mesin lama `rates.get("")` = tanpa tarif →
      potret isi awal tanpa tarif, komisi 0; L2 tanpa kunci `category` → kategori produk KA12Batik → 100 × 500 = 50.000.
      Komisi Andi Nov (pesanan ini saja) = 50.000.
  I2  gaji Nov: Andi 1.000 yd lunas × 500 = 500.000 (+ 50.000 dari I1 = 550.000), Budi 200 yd × 500 = 100.000 → akrual
      gaji = Σ slip = 650.000; catatan per sales di potret bulan = komisi slip (Andi 550.000, Budi 100.000), mesin tidak
      dipanggil saat posting walau mesin Budi galat.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List

import pytest

import bootstrap
from core_utils import now_iso

pytestmark = pytest.mark.anyio

KANDA = "ent_kanda"
NOV = "2026-11"
UTC = datetime.timezone.utc
JAM = {"now": datetime.datetime(2026, 11, 5, 3, 0, tzinfo=UTC)}   # 5 Nov 2026 10.00 WIB
PRD = "prd_ka12_bt"


@pytest.fixture(scope="module", autouse=True)
def _jam():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: JAM["now"])
        yield


def _baris(qty: float, **lain) -> Dict[str, Any]:
    b = {"product_id": PRD, "sku": "KA12-01", "product_name": "Batik KA12", "quantity": qty, "base_quantity": qty,
         "unit": "yard", "base_unit": "yard", "price": 50_000, "line_total": qty * 50_000, "discount_percent": 0,
         "unit_cost": 30_000}
    b.update(lain)
    return b


async def _pesanan(db, so_id: str, cust: str, items: List[Dict[str, Any]], *, ent: str = KANDA,
                   bayar_tgl: str = "2026-11-10") -> None:
    gt = sum(it["line_total"] for it in items if isinstance(it, dict))
    await db.sales_orders.insert_one({
        "id": so_id, "number": f"SO/KA12/{so_id[-4:].upper()}", "entity_id": ent, "customer_id": cust,
        "status": "completed", "items": items, "subtotal": gt, "grand_total": gt,
        "payments": [{"amount": gt, "created_at": f"{bayar_tgl}T03:00:00+00:00"}],
        "created_at": "2026-11-02T03:00:00+00:00", "updated_at": now_iso()})


@pytest.fixture(scope="module")
async def f12(db, akun, sesi):
    await db.hr_employees.update_many({"entity_id": KANDA}, {"$set": {"status": "inactive"}})
    u: Dict[str, Dict[str, Any]] = {}
    for kode, nama in (("andi", "Andi KA12"), ("budi", "Budi KA12")):
        u[kode] = await akun("sales", entitas=(KANDA,))
        await db.users.update_one({"id": u[kode]["id"]}, {"$set": {"name": nama}})
        await db.hr_employees.insert_one({
            "id": f"emp_ka12_{kode}", "code": f"EMP-KA12-{kode.upper()}", "name": nama, "entity_id": KANDA,
            "user_id": u[kode]["id"], "status": "active", "base_salary": 5_000_000, "allowances": [],
            "ptkp_status": "TK0", "bpjs_kes_enabled": False, "bpjs_tk_enabled": False, "join_date": "2025-01-01",
            "created_at": "2025-01-01T00:00:00+00:00"})
        await db.customers.insert_one({"id": f"cus_ka12_{kode}", "name": f"Toko {nama}", "entity_id": KANDA,
                                       "status": "active", "assigned_sales_id": u[kode]["id"]})
    await db.products.insert_one({"id": PRD, "sku": "KA12-01", "name": "Batik KA12", "category": "KA12Batik",
                                  "base_unit": "yard", "price": 50_000, "status": "active", "is_active": True})
    await db.incentive_rates.insert_one({"id": "irate_ka12_kat", "entity_id": KANDA, "category": "KA12Batik",
                                         "rate_key": "kategori:KA12Batik", "per_unit_amount": 500.0,
                                         "margin_cap_pct": 0.0, "discount_threshold": 100.0,
                                         "discount_threshold_type": "pct", "discount_mechanic": "tier_factor",
                                         "discount_factor": 1.0, "status": "active"})
    return {"u": u, "h": await sesi("admin@kainnusantara.id", entitas=KANDA)}


# ═══ I1 — kategori baris kosong tetap tanpa tarif kategori (mesin lama), isi awal tidak membekukan kategori produk ═══
async def test_KA12_I1_kategori_kosong_tanpa_tarif(db, f12):
    from services import commission_rules as cr
    from services import sales_force_service as sfs
    await _pesanan(db, "so_ka12_i1", "cus_ka12_andi", [_baris(100, category=""), _baris(100)])
    # jalur baca tanpa potret (sebelum isi awal): kategori "" → tanpa tarif; tanpa kunci → kategori produk
    l1, l2 = (await db.sales_orders.find_one({"id": "so_ka12_i1"}))["items"]
    assert (await cr.aturan_dari_sekarang(l1, KANDA, {}, sumber="uji"))["tarif"] is None
    assert (await cr.aturan_dari_sekarang(l2, KANDA, {}, sumber="uji"))["tarif"]["per_unit_amount"] == 500
    sebelum = await sfs.compute_commission(f12["u"]["andi"]["id"], NOV, KANDA)
    await bootstrap.backfill_so_line_commission_rule()
    p1, p2 = [it["commission_rule"] for it in (await db.sales_orders.find_one({"id": "so_ka12_i1"}))["items"]]
    assert (p1["sumber"], p1["tarif"]) == ("isi_awal", None)
    assert (p2["tarif"]["per_unit_amount"], p2["tarif"]["asal_tingkat"]) == (500, "kategori")
    sesudah = await sfs.compute_commission(f12["u"]["andi"]["id"], NOV, KANDA)
    assert sebelum["total_incentive"] == sesudah["total_incentive"] == 50_000   # 100 × 500 dari L2 saja


async def test_KA12_I1b_pesanan_baru_tetap_kategori_produk(db, f12):
    """Pesanan BARU (`potret_pesanan`, jalur create_order) dengan baris kategori kosong tetap memakai kategori produk."""
    from services.commission_rules import potret_pesanan
    items = [_baris(10, category="")]
    await potret_pesanan(KANDA, items, {PRD: await db.products.find_one({"id": PRD}, {"_id": 0})})
    assert items[0]["commission_rule"]["tarif"]["per_unit_amount"] == 500


# ═══ M2 — isi awal tahan galat, berkelompok, tetap idempoten ════════════════════════════════════════════════════════
class _HitungFind:
    def __init__(self, asli):
        self._asli, self.n = asli, 0

    def find(self, *a, **kw):
        self.n += 1
        return self._asli.find(*a, **kw)

    def __getattr__(self, k):
        return getattr(self._asli, k)


class _DbHitung:
    def __init__(self, asli, products):
        self._asli, self.products = asli, products

    def __getattr__(self, k):
        return getattr(self._asli, k)


async def test_KA12_M2_isi_awal_tahan_galat_berkelompok(db, f12, monkeypatch, caplog):
    from services import commission_rules as cr
    rusak = "ent_ka12_rusak"
    await db.incentive_rates.insert_one({"id": "irate_ka12_rusak", "entity_id": rusak, "category": "KA12Batik",
                                         "rate_key": "kategori:KA12Batik", "per_unit_amount": "abc",
                                         "status": "active"})
    await _pesanan(db, "so_ka12_rsk", "cus_x", [_baris(5)], ent=rusak)                  # tarif rusak → dilewati
    await _pesanan(db, "so_ka12_str", "cus_ka12_lain", ["rusak", _baris(5)])             # baris bukan objek
    for i in range(4):
        await _pesanan(db, f"so_ka12_ok{i}", "cus_ka12_lain", [_baris(1 + i)])
    hitung = _HitungFind(db.products)
    monkeypatch.setattr(bootstrap, "db", _DbHitung(db, hitung))
    artikel_n = {"n": 0}
    asli_artikel = cr._muat_artikel

    async def _artikel(ids):
        artikel_n["n"] += 1
        return await asli_artikel(ids)
    monkeypatch.setattr(cr, "_muat_artikel", _artikel)
    with caplog.at_level(logging.WARNING, logger="bootstrap"):
        await bootstrap.backfill_so_line_commission_rule(kelompok=2)
    assert any("SO/KA12/_RSK" in r.getMessage() for r in caplog.records), [r.getMessage() for r in caplog.records]
    assert hitung.n <= 1                 # produk dimuat sekali per kelompok yang punya produk baru (lalu di-cache)
    assert artikel_n["n"] == 0           # produk tanpa artikel: tidak ada kueri artikel
    rsk = (await db.sales_orders.find_one({"id": "so_ka12_rsk"}))["items"][0]
    assert "commission_rule" not in rsk
    s, ok = (await db.sales_orders.find_one({"id": "so_ka12_str"}))["items"]
    assert s == "rusak" and ok["commission_rule"]["tarif"]["per_unit_amount"] == 500
    waktu = {}
    for i in range(4):
        it = (await db.sales_orders.find_one({"id": f"so_ka12_ok{i}"}))["items"][0]
        assert it["commission_rule"]["sumber"] == "isi_awal"
        waktu[i] = it["commission_rule"]["dipotret_pada"]
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="bootstrap"):
        await bootstrap.backfill_so_line_commission_rule(kelompok=2)   # idempoten; pesanan rusak dicoba lagi
    for i in range(4):
        it = (await db.sales_orders.find_one({"id": f"so_ka12_ok{i}"}))["items"][0]
        assert it["commission_rule"]["dipotret_pada"] == waktu[i]
    assert any("SO/KA12/_RSK" in r.getMessage() for r in caplog.records)
    # dibersihkan: baris bukan objek juga menghentikan isi awal LAIN yang sudah ada (`backfill_so_line_category`)
    await db.sales_orders.delete_many({"id": {"$in": ["so_ka12_rsk", "so_ka12_str"]}})
    await db.incentive_rates.delete_one({"id": "irate_ka12_rusak"})


async def test_KA12_M2b_kueri_produk_per_kelompok(db, f12, monkeypatch):
    """Lima pesanan dengan lima produk berbeda, kelompok 2 → 3 kueri produk (bukan 5)."""
    for i in range(5):
        await db.products.insert_one({"id": f"prd_ka12_k{i}", "sku": f"KA12-K{i}", "name": f"Kain K{i}",
                                      "category": "KA12Batik", "status": "active"})
        await _pesanan(db, f"so_ka12_k{i}", "cus_ka12_lain", [_baris(1, product_id=f"prd_ka12_k{i}")])
    hitung = _HitungFind(db.products)
    monkeypatch.setattr(bootstrap, "db", _DbHitung(db, hitung))
    await bootstrap.backfill_so_line_commission_rule(kelompok=2)
    assert hitung.n == 3
    for i in range(5):
        it = (await db.sales_orders.find_one({"id": f"so_ka12_k{i}"}))["items"][0]
        assert it["commission_rule"]["tarif"]["per_unit_amount"] == 500


# ═══ M1 — isi awal berjalan SESUDAH tarif bawaan dibuat (basis data baru) ═══════════════════════════════════════════
async def test_KA12_M1_isi_awal_sesudah_tarif_bawaan(db, f12):
    """Basis data tanpa tarif sama sekali + pesanan lama Batik: proses awal membuat tarif bawaan (Semua PT, Batik) lalu
    memotret pesanan dengan tarif itu — bukan memotretnya tanpa tarif lebih dulu."""
    simpan = await db.incentive_rates.find({}, {"_id": 0}).to_list(None)
    await db.incentive_rates.delete_many({})
    try:
        await db.products.insert_one({"id": "prd_ka12_m1", "sku": "KA12-M1", "name": "Batik M1", "category": "Batik",
                                      "status": "active"})
        await _pesanan(db, "so_ka12_m1", "cus_ka12_lain", [_baris(3, product_id="prd_ka12_m1", category="Batik")])
        await bootstrap.run_bootstrap()
        r = (await db.sales_orders.find_one({"id": "so_ka12_m1"}))["items"][0]["commission_rule"]
        seed = await db.incentive_rates.find_one({"entity_id": "all", "category": "Batik"}, {"_id": 0})
        assert seed and r["tarif"] and r["tarif"]["id"] == seed["id"], r
        assert (r["tarif"]["asal_tingkat"], r["tarif"]["asal_lingkup"]) == ("kategori", "semua_pt")
    finally:
        await db.incentive_rates.delete_many({})
        if simpan:
            await db.incentive_rates.insert_many(simpan)


# ═══ I2 — potret bulan saat posting gaji: aturan capaian dibekukan, catatan per sales dari slip (tanpa mesin) ════════
async def test_KA12_I2_posting_gaji_tanpa_hitung_ulang(klien, db, f12, monkeypatch):
    from services import sales_force_service as sfs
    await _pesanan(db, "so_ka12_andi", "cus_ka12_andi", [_baris(1_000, category="KA12Batik")])
    await _pesanan(db, "so_ka12_budi", "cus_ka12_budi", [_baris(200, category="KA12Batik")])
    await bootstrap.backfill_so_line_commission_rule()
    h = f12["h"]
    r = await klien.post("/api/hr/payroll/runs", headers=h, json={"entity_id": KANDA, "period": NOV,
                                                                  "run_type": "regular"})
    assert r.status_code == 200, r.text
    run = r.json()
    for aksi in ("submit", "approve"):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", headers=h, json={})
        assert r.status_code == 200, r.text
        run = r.json()
    komisi = {s["user_id"]: s["commission"] for s in run["payslips"] if s.get("commission")}
    andi, budi = f12["u"]["andi"]["id"], f12["u"]["budi"]["id"]
    assert komisi == {andi: 550_000, budi: 100_000}, komisi   # Andi 1.000 + 100 (I1, L2) yd × 500; Budi 200 × 500
    asli = sfs.compute_commission
    panggil: List[str] = []

    async def mesin(sales_id, period, entity_id=None, **kw):
        panggil.append(sales_id)
        if sales_id == budi:
            raise RuntimeError("uji: mesin komisi Budi galat")
        return await asli(sales_id, period, entity_id, **kw)
    monkeypatch.setattr(sfs, "compute_commission", mesin)
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=h, json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "posted", r.json()
    akr = await db.journal_entries.find_one({"source_type": "incentive_accrual", "source_id": f"{KANDA}:{NOV}",
                                             "status": {"$ne": "void"}}, {"_id": 0})
    assert akr and akr["total_debit"] == 650_000
    doc = await db.commission_period_rules.find_one({"entity_id": KANDA, "period": NOV}, {"_id": 0})
    assert doc and doc["journal_id"] == akr["id"] and doc["sales_sumber"] == "slip_gaji"
    assert doc["achievement"]["aktif"] is False                     # aturan capaian (bawaan mati) tetap dibekukan
    assert {s["sales_id"]: s["total"] for s in doc["sales"]} == {andi: 550_000, budi: 100_000}
    assert panggil == []                                             # posting gaji tidak menjalankan mesin komisi


async def test_KA12_I2b_hitung_ulang_upaya_terbaik_tanda_galat(db, f12, monkeypatch):
    """Akrual dengan total dari pemanggil tanpa rincian → catatan dihitung ulang; mesin Budi galat → akrual tetap
    dibukukan, potret ada, baris Budi bertanda galat, Andi tetap tercatat."""
    from services import gl_service as gl
    from services import sales_force_service as sfs
    andi, budi = f12["u"]["andi"]["id"], f12["u"]["budi"]["id"]
    asli = sfs.compute_commission

    async def mesin(sales_id, period, entity_id=None, **kw):
        if sales_id == budi:
            raise RuntimeError("uji: mesin komisi Budi galat")
        return await asli(sales_id, period, entity_id, **kw)
    monkeypatch.setattr(sfs, "compute_commission", mesin)
    j = await gl.post_incentive_accrual(KANDA, "2026-10", "Uji I2b", total=10_000, date="2026-10-31")
    assert j and j["source_type"] == "incentive_accrual"
    doc = await db.commission_period_rules.find_one({"entity_id": KANDA, "period": "2026-10"}, {"_id": 0})
    assert doc and doc["journal_id"] == j["id"] and doc["sales_sumber"] == "hitung_ulang"
    per = {s["sales_id"]: s for s in doc["sales"]}
    assert per[andi]["total"] == 0 and "galat" not in per[andi]     # Oktober: belum ada pembayaran
    assert per[budi]["total"] is None and "gagal dihitung" in per[budi]["galat"]


async def test_KA12_I2c_akrual_manual_mesin_sekali_per_sales(klien, db, f12, monkeypatch):
    """Akrual manual: mesin dijalankan SEKALI per sales daftar PT (total jurnal = catatan potret), bukan dua kali."""
    from services import sales_force_service as sfs
    from services.incentive_targets import sales_roster
    asli = sfs.compute_commission
    panggil: List[str] = []

    async def mesin(sales_id, period, entity_id=None, **kw):
        panggil.append(sales_id)
        return await asli(sales_id, period, entity_id, **kw)
    await _pesanan(db, "so_ka12_des", "cus_ka12_andi", [_baris(40, category="KA12Batik")], bayar_tgl="2026-12-05")
    await bootstrap.backfill_so_line_commission_rule()
    monkeypatch.setattr(sfs, "compute_commission", mesin)
    r = await klien.post("/api/sales/incentive/post-gl", headers=f12["h"], params={"period": "2026-12"})
    assert r.status_code == 200, r.text
    assert r.json()["created"] is True and r.json()["amount"] == 20_000, r.json()   # 40 yd × 500
    daftar = await sales_roster(KANDA, "month", "2026-12")
    assert sorted(panggil) == sorted(u["id"] for u in daftar)        # sekali per sales, bukan dua kali
    doc = await db.commission_period_rules.find_one({"entity_id": KANDA, "period": "2026-12"}, {"_id": 0})
    assert doc["sales_sumber"] == "akrual" and doc["journal_id"] == r.json()["journal_id"]
    assert {s["sales_id"]: s["total"] for s in doc["sales"] if s["total"]} == {f12["u"]["andi"]["id"]: 20_000}
    assert round(sum(s["total"] for s in doc["sales"]), 2) == r.json()["amount"]
