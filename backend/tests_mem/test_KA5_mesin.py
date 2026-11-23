"""KA-5 — mesin komisi per-SKU membaca potret aturan baris pesanan + rincian per artikel.

Rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §6.1, §6.5a; rencana Task 5 (Review Focus 1,
2, 5). Mesin: `sales_force_service._compute_commission_per_sku` (lewat `compute_commission`, strategi `per_sku` bawaan).

Fixture (DISISIP langsung, pola KM-T5 U5): PT `ent_ksc` dengan pengaturan bawaan; tiap uji punya sales + pelanggan
sendiri supaya jumlah per sales tidak saling memengaruhi. Pesanan periode 2026-11 (dibuat 2 Nov, dibayar 10 Nov).
Potret aturan baris dibuat dengan fungsi asli: `commission_rules.potret` (aturan rakitan U4, U5, U7) atau
`commission_rules.potret_pesanan` (tarif lewat API, U3, U6, U8 — sama dengan `create_order`). Artikel: "Batik Mega
KA5" (`BTK-MEGA`), "Batik Kawung KA5" (`BTK-KWG`), dan satu artikel per uji U3/U6/U8 berkategori sendiri tanpa tarif
kategori.

Hitung tangan (satuan dasar yard/meter; fraksi terbayar = bayar dalam periode / grand total):
  U1  tanpa potret, tarif kategori Rp 500/m PT ini, batas margin 0, 1.000 m lunas → 1.000 × 500 = 500.000.
  U1b tanpa potret, tarif kategori Rp 500/m batas margin 40 %; pesanan tim (bobot 50 %) grand total 15.000.000,
      bayar 6.000.000 → fraksi 0,4. L1 200 m @50.000, HPP 49.000 → margin 1.000/m: qty 80, kotor 40.000, batas
      40 % × 80 × 1.000 = 32.000 → 32.000 × 0,5 = 16.000 (dibatasi). L2 100 m, HPP tidak diketahui → tanpa batas:
      40 × 500 = 20.000 × 0,5 = 10.000. Total 26.000. Proyeksi penuh: L1 min(100.000; 80.000) × 0,5 = 40.000 +
      L2 50.000 × 0,5 = 25.000 → 65.000. Pesanan batal (sudah dibayar) tidak ikut.
  U2  tanpa potret, diskon baris 15 % > ambang 10 %, faktor 0,5 → 1.000 × 500 × 0,5 = 250.000 (= rumus lama).
  U3  tarif artikel Semua PT 3.000 dipotret; tarif diubah ke 3.500 sesudahnya; 100 yd lunas → 100 × 3.000 = 300.000.
      Sumber aturan pengganti (simulasi) bertarif 4.000 → 400.000.
  U4  basis pricelist, pita ≤3 % ×0,8 · ≤10 % ×0,5 · sisa ×0; daftar 50.000, bersih 49.000 → selisih 2 % → ×0,8;
      100 yd lunas, tarif 3.500 → 100 × 3.500 × 0,8 = 280.000.
  U4b dua baris artikel sama, bersih 49.000 (2 %) dan 48.750 (2,5 %) → pita sama ×0,8 → satu baris rincian
      200 yd, 2 × 100 × 3.500 × 0,8 = 560.000, label rentang "2–2,5% di bawah harga acuan".
  U5  tarif 3.500 batas margin 50 %; 100 yd @50.000, HPP 49.000 → kotor 350.000, batas 50 % × 100 × 1.000 = 50.000.
  U6  pesanan 1 dipotret tanpa tarif, lalu tarif artikel 3.500 dibuat → pesanan 1 tetap 0; pesanan 2 (potret 3.500)
      100 yd lunas → 350.000. Total 350.000.
  U7  satu pesanan dua baris @100 yd bersih 47.500, daftar 50.000: A harga khusus (pengali tetap ×0,5, tarif 3.000),
      B harga PT (selisih 5 % → pita ×0,5, tarif 3.500); grand total 9.500.000, bayar 3.800.000 → fraksi 0,4.
      A 40 × 3.000 × 0,5 = 60.000 · B 40 × 3.500 × 0,5 = 70.000 → 130.000. Proyeksi penuh 150.000 + 175.000 = 325.000.
  U8  tarif artikel 3.500 dipotret, lalu tarif dihapus (DELETE) → 100 yd lunas tetap 350.000.
  F1  basis pricelist, selisih 5 %, potret TANPA pita (atau pita/aturan asal harga kosong) → bawaan registri (satu
      baris terbuka ×1,0; semua asal harga ikut pita) → pengali 1,0, bukan ×0.
  F2  baris tarif kategori dengan isian ADA bernilai None (`margin_cap_pct`, `discount_threshold`) → dibaca 0 seperti
      mesin lama (`{**cfg, **rate}` lalu `… or 0`): N1 1.000 m @50.000 HPP 49.900, tanpa batas → 1.000 × 500 =
      500.000 (batas PT 50 % akan memotong ke 50.000); N2 100 m diskon 5 % > ambang 0 → ×0,5 → 25.000 (ambang PT 10 %
      → 50.000). Total 525.000 — sama lewat jalur potret.
  F3  baris tarif kategori TANPA kunci batas margin & diskon → nilai PT (batas 50 %, ambang 10 %): A1 1.000 m @50.000
      HPP 49.900 → kotor 500.000, batas 50 % × 1.000 × 100 = 50.000; A2 100 m diskon 5 % ≤ 10 % → ×1,0 → 50.000.
      Total 100.000.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
PERIODE = "2026-11"
PITA = [{"sampai_pct": 3, "pengali": 0.8}, {"sampai_pct": 10, "pengali": 0.5}, {"sampai_pct": None, "pengali": 0.0}]
MEGA = {"id": "tpl_ka5_mega", "nama": "Batik Mega KA5", "kode": "BTK-MEGA"}
KAWUNG = {"id": "tpl_ka5_kwg", "nama": "Batik Kawung KA5", "kode": "BTK-KWG"}
KUNCI_RINCIAN = {"category", "sku", "name", "template_id", "qty_base", "commission", "rate", "rate_origin",
                 "price_factor", "price_reason", "price_reason_label", "achievement_factor", "capped"}
UJI = ("u1", "u1b", "u2", "u3", "u4", "u4b", "u5", "u6", "u7", "u8", "f2", "f2s", "f3", "u9")


def _tarif_kategori(kode: str, kategori: str, *, cap: float = 0.0, **lain) -> Dict[str, Any]:
    """Tarif kategori lama (tanpa `rate_key`, pola KM-T5): Rp 500/m, ambang diskon 10 % tier ×0,5."""
    d = {"id": f"rate_ka5_{kode}", "entity_id": KSC, "category": kategori, "per_unit_amount": 500.0,
         "margin_cap_pct": cap, "discount_threshold": 10.0, "discount_threshold_type": "pct",
         "discount_mechanic": "tier_factor", "discount_factor": 0.5, "status": "active"}
    d.update(lain)
    return d


def _baris(qty: float, bersih: float, *, pid: str, kategori: str, sku: str = "", nama: str = "", harga: float = 0,
           **lain) -> Dict[str, Any]:
    b = {"product_id": pid, "sku": sku or pid.upper(), "product_name": nama or f"Kain {pid}", "category": kategori,
         "quantity": qty, "base_quantity": qty, "unit": "yard", "base_unit": "yard", "price": harga or bersih,
         "line_total": qty * bersih, "discount_percent": 0, "unit_cost": 0, "price_source": "entity"}
    b.update(lain)
    return b


async def _pesanan(db, so_id: str, cust: str, items: List[Dict[str, Any]], *, bayar: Optional[float] = None,
                   status: str = "completed", team: Optional[List[Dict[str, Any]]] = None) -> None:
    gt = sum(it["line_total"] for it in items)
    doc = {"id": so_id, "number": f"SO/KA5/{so_id[-4:].upper()}", "entity_id": KSC, "customer_id": cust,
           "status": status, "items": items, "subtotal": gt, "grand_total": gt,
           "payments": [{"amount": gt if bayar is None else bayar, "created_at": "2026-11-10T03:00:00+00:00"}],
           "created_at": "2026-11-02T03:00:00+00:00", "updated_at": now_iso()}
    if team:
        doc["sales_team"] = team
    await db.sales_orders.insert_one(doc)


def _potret(pt: Dict[str, Any], per_unit: float, *, artikel: Dict[str, Any] = MEGA, cap: float = 0.0,
            lingkup: str = "pt", **aturan) -> Dict[str, Any]:
    """Potret rakitan lewat `commission_rules.potret` (bentuk sama dengan yang ditulis `create_order`)."""
    from services.commission_rules import potret
    tarif = {"id": f"irate_{artikel['id']}", "asal_tingkat": "artikel", "asal_lingkup": lingkup,
             "per_unit_amount": per_unit, "margin_cap_pct": cap}
    return potret(tarif, {**pt, **aturan}, artikel=artikel, sumber="pesanan", waktu=now_iso())


async def _potret_asli(db, items: List[Dict[str, Any]]) -> None:
    """Potret lewat `potret_pesanan` — jalur yang sama dengan `create_order` (aturan yang berlaku SAAT INI)."""
    from services.commission_rules import potret_pesanan
    pids = [it["product_id"] for it in items]
    prods = {p["id"]: p async for p in db.products.find({"id": {"$in": pids}}, {"_id": 0})}
    await potret_pesanan(KSC, items, prods)


async def _tarif_api(klien, h, **isi) -> Dict[str, Any]:
    r = await klien.post("/api/incentive-rates", headers=h, json={"margin_cap_pct": 0, **isi})
    assert r.status_code == 200, r.text
    return r.json()


async def _komisi(f, kode: str, **kw) -> Dict[str, Any]:
    from services import sales_force_service as sfs
    sid = f["u"][kode]["id"]
    if kw:
        from services.config_service import get_effective_settings
        return await sfs._compute_commission_per_sku(sid, PERIODE, KSC, await get_effective_settings(KSC), **kw)
    return await sfs.compute_commission(sid, PERIODE, KSC)


def _satu(hasil: Dict[str, Any]) -> Dict[str, Any]:
    rows = [r for r in hasil["breakdown"] if r["commission"] or r["qty_base"]]
    assert len(rows) == 1, hasil["breakdown"]
    return rows[0]


@pytest.fixture(scope="module")
async def f(db, akun, sesi, kepala_admin):
    from services.commission_rules import aturan_pt
    u: Dict[str, Dict[str, Any]] = {}
    for kode in UJI:
        u[kode] = await akun("sales", entitas=(KSC,))
        await db.customers.insert_one({"id": f"cus_ka5_{kode}", "name": f"Toko KA5 {kode}", "entity_id": KSC,
                                       "status": "active", "assigned_sales_id": u[kode]["id"]})
    await db.product_templates.insert_many([
        {"id": MEGA["id"], "name": MEGA["nama"], "sku_prefix": MEGA["kode"], "category": "KA5Batik",
         "status": "active"},
        {"id": KAWUNG["id"], "name": KAWUNG["nama"], "sku_prefix": KAWUNG["kode"], "category": "KA5Batik",
         "status": "active"},
        *[{"id": f"tpl_ka5_{k}", "name": f"Artikel KA5 {k.upper()}", "sku_prefix": f"ART-{k.upper()}",
           "category": f"KA5{k.upper()}", "status": "active"} for k in ("u3", "u6", "u8")]])
    await db.products.insert_many([
        {"id": f"prd_ka5_{k}", "sku": f"ART-{k.upper()}-01", "name": f"Kain Artikel {k.upper()}",
         "template_id": f"tpl_ka5_{k}", "category": f"KA5{k.upper()}", "base_unit": "yard", "status": "active",
         "is_active": True} for k in ("u3", "u6", "u8")])
    await db.incentive_rates.insert_many([_tarif_kategori("u1", "KA5-U1"), _tarif_kategori("u2", "KA5-U2"),
                                          _tarif_kategori("lama", "KA5-LAMA", cap=40.0),
                                          _tarif_kategori("null", "KA5-NULL", margin_cap_pct=None,
                                                          discount_threshold=None),
                                          {"id": "rate_ka5_absen", "entity_id": KSC, "category": "KA5-ABSEN",
                                           "per_unit_amount": 500.0, "status": "active"}])
    return {"u": u, "pt": await aturan_pt(KSC), "adm": kepala_admin,
            "h_sales": await sesi(u["u4"], entitas=KSC), "h_u9": await sesi(u["u9"], entitas=KSC)}


async def test_KA5_U1_tanpa_potret_sama_dengan_lama(db, f):
    await _pesanan(db, "so_ka5_u1", "cus_ka5_u1", [_baris(1000, 50_000, pid="prd_ka5_x1", kategori="KA5-U1",
                                                          sku="KA5U1", nama="Kain KA5 U1")])
    hasil = await _komisi(f, "u1")
    assert (hasil["total_incentive"], hasil["commission"], hasil["projection_full"]) == (500_000, 500_000, 500_000)
    b = _satu(hasil)
    assert set(b) == KUNCI_RINCIAN, b
    assert b == {"category": "KA5-U1", "sku": "KA5U1", "name": "Kain KA5 U1", "template_id": "", "qty_base": 1000,
                 "commission": 500_000, "rate": 500, "rate_origin": "Tarif kategori (PT ini)", "price_factor": 1.0,
                 "price_reason": "diskon_baris", "price_reason_label": "Diskon baris di bawah ambang",
                 "achievement_factor": 1.0, "capped": False}
    # mesin hanya membaca: pesanan tanpa potret tidak ditulisi potret saat dihitung
    assert "commission_rule" not in (await db.sales_orders.find_one({"id": "so_ka5_u1"}))["items"][0]


async def test_KA5_U1b_tanpa_potret_tim_batas_margin_bayar_sebagian(db, f):
    sid, lain = f["u"]["u1b"]["id"], f["u"]["u1"]["id"]
    l1 = _baris(200, 50_000, pid="prd_ka5_l1", kategori="KA5-LAMA", sku="LAMA-1", unit_cost=49_000)
    l2 = _baris(100, 50_000, pid="prd_ka5_l2", kategori="KA5-LAMA", sku="LAMA-2")
    team = [{"sales_id": sid, "role": "pic", "split_pct": 50.0}, {"sales_id": lain, "role": "co", "split_pct": 50.0}]
    await _pesanan(db, "so_ka5_u1b", "cus_ka5_u1b", [l1, l2], bayar=6_000_000, team=team)
    await _pesanan(db, "so_ka5_u1bx", "cus_ka5_u1b", [dict(l1)], status="cancelled")
    hasil = await _komisi(f, "u1b")
    assert (hasil["total_incentive"], hasil["projection_full"]) == (26_000, 65_000)
    rows = {r["sku"]: r for r in hasil["breakdown"]}
    assert (rows["LAMA-1"]["commission"], rows["LAMA-1"]["qty_base"], rows["LAMA-1"]["capped"]) == (16_000, 40, True)
    assert (rows["LAMA-2"]["commission"], rows["LAMA-2"]["qty_base"], rows["LAMA-2"]["capped"]) == (10_000, 20, False)


async def test_KA5_U2_diskon_lama_sama(db, f):
    await _pesanan(db, "so_ka5_u2", "cus_ka5_u2", [_baris(1000, 42_500, pid="prd_ka5_x2", kategori="KA5-U2",
                                                          harga=50_000, discount_percent=15)])
    hasil = await _komisi(f, "u2")
    assert hasil["total_incentive"] == 250_000
    b = _satu(hasil)
    assert (b["rate"], b["price_factor"], b["price_reason"], b["price_reason_label"]) == (
        500, 0.5, "diskon_lewat_ambang", "Diskon baris melewati ambang")


async def test_KA5_U3_potret_dipakai_bukan_tarif_baru(klien, db, f):
    rate = await _tarif_api(klien, f["adm"], entity_id="all", template_id="tpl_ka5_u3", per_unit_amount=3000)
    items = [_baris(100, 50_000, pid="prd_ka5_u3", kategori="KA5U3")]
    await _potret_asli(db, items)
    await _pesanan(db, "so_ka5_u3", "cus_ka5_u3", items)
    r = await klien.patch(f"/api/incentive-rates/{rate['id']}", headers=f["adm"],
                          json={"data": {"per_unit_amount": 3500}})
    assert r.status_code == 200, r.text
    hasil = await _komisi(f, "u3")
    assert hasil["total_incentive"] == 300_000
    b = _satu(hasil)
    assert (b["rate"], b["rate_origin"], b["name"], b["sku"], b["template_id"]) == (
        3000, "Tarif artikel (Semua PT)", "Artikel KA5 U3", "ART-U3", "tpl_ka5_u3")


async def test_KA5_U3b_sumber_aturan_pengganti(db, f):
    # simulasi (Task 8): `sumber_aturan` menggantikan potret/aturan_baris untuk tiap baris
    pot = _potret(f["pt"], 4000, artikel={"id": "tpl_ka5_u3", "nama": "Artikel KA5 U3", "kode": "ART-U3"})
    dilihat: List[str] = []

    async def sumber(line):
        dilihat.append(line["product_id"])
        return pot

    hasil = await _komisi(f, "u3", sumber_aturan=sumber)
    assert hasil["total_incentive"] == 400_000 and dilihat == ["prd_ka5_u3"]


async def test_KA5_U4_pita_pricelist(db, f):
    pot = _potret(f["pt"], 3500, price_basis="pricelist", price_bands=PITA)
    await _pesanan(db, "so_ka5_u4", "cus_ka5_u4", [_baris(100, 49_000, pid="prd_ka5_mega_mrh", kategori="KA5Batik",
                                                          harga=50_000, list_price=50_000, commission_rule=pot)])
    hasil = await _komisi(f, "u4")
    assert hasil["total_incentive"] == 280_000
    b = _satu(hasil)
    assert set(b) == KUNCI_RINCIAN, b
    assert (b["price_reason"], b["price_reason_label"], b["rate_origin"], b["price_factor"], b["rate"]) == (
        "pita", "2% di bawah harga acuan", "Tarif artikel (PT ini)", 0.8, 3500)
    assert (b["name"], b["sku"], b["template_id"], b["qty_base"], b["achievement_factor"], b["capped"]) == (
        "Batik Mega KA5", "BTK-MEGA", "tpl_ka5_mega", 100, 1.0, False)


async def test_KA5_U4b_pita_gabungan_label_rentang(db, f):
    pot = _potret(f["pt"], 3500, price_basis="pricelist", price_bands=PITA)
    items = [_baris(100, bersih, pid="prd_ka5_mega_mrh", kategori="KA5Batik", harga=50_000, list_price=50_000,
                    commission_rule=pot) for bersih in (49_000, 48_750)]
    await _pesanan(db, "so_ka5_u4b", "cus_ka5_u4b", items)
    hasil = await _komisi(f, "u4b")
    assert hasil["total_incentive"] == 560_000
    b = _satu(hasil)
    assert (b["qty_base"], b["price_factor"], b["price_reason_label"]) == (200, 0.8, "2–2,5% di bawah harga acuan")


async def test_KA5_U5_batas_margin_ditandai_tanpa_angka(db, f):
    pot = _potret(f["pt"], 3500, cap=50.0)
    await _pesanan(db, "so_ka5_u5", "cus_ka5_u5", [_baris(100, 50_000, pid="prd_ka5_mega_mrh", kategori="KA5Batik",
                                                          unit_cost=49_000, commission_rule=pot)])
    hasil = await _komisi(f, "u5")
    assert hasil["total_incentive"] == 50_000
    b = _satu(hasil)
    assert b["capped"] is True and b["commission"] == 50_000
    assert set(b) == KUNCI_RINCIAN
    assert not [k for k in b if "margin" in k or "cost" in k], b


async def test_KA5_U9_kartu_sales_rincian_tanpa_margin(klien, db, f):
    # 100 yd @ Rp 50.000, HPP 49.000, tarif Rp 3.500/yd, batas margin 50 % → komisi dibatasi 50.000 (seperti U5).
    pot = _potret(f["pt"], 3500, cap=50.0)
    await _pesanan(db, "so_ka5_u9", "cus_ka5_u9", [_baris(100, 50_000, pid="prd_ka5_mega_mrh", kategori="KA5Batik",
                                                          unit_cost=49_000, commission_rule=pot)])
    r = await klien.get("/api/incentive/me", headers=f["h_u9"], params={"period": PERIODE})
    assert r.status_code == 200, r.text
    ac = r.json()["auto_commission"]
    assert set(ac) == {"mtd", "projection_month_end", "breakdown"}, ac
    assert ac["mtd"] == 50_000
    b = ac["breakdown"][0]
    assert set(b) == {"name", "sku", "qty_base", "rate", "rate_origin", "price_factor", "price_reason_label",
                      "achievement_factor", "capped", "commission"}
    assert b["capped"] is True and b["commission"] == 50_000
    assert not [k for k in b if "margin" in k or "cost" in k], b


async def test_KA5_U6_tarif_ditambah_sesudah_pesanan(klien, db, f):   # Review Focus 1
    lama = [_baris(100, 50_000, pid="prd_ka5_u6", kategori="KA5U6")]
    await _potret_asli(db, lama)
    assert lama[0]["commission_rule"]["tarif"] is None
    await _pesanan(db, "so_ka5_u6a", "cus_ka5_u6", lama)
    await _tarif_api(klien, f["adm"], entity_id=KSC, template_id="tpl_ka5_u6", per_unit_amount=3500)
    baru = [_baris(100, 50_000, pid="prd_ka5_u6", kategori="KA5U6")]
    await _potret_asli(db, baru)
    await _pesanan(db, "so_ka5_u6b", "cus_ka5_u6", baru)
    hasil = await _komisi(f, "u6")
    assert hasil["total_incentive"] == 350_000      # pesanan lama tetap tanpa komisi; tarif tidak berlaku mundur
    assert [(r["qty_base"], r["commission"]) for r in hasil["breakdown"]] == [(100, 350_000)]


async def test_KA5_U7_baris_campuran_bayar_sebagian(db, f):    # Review Focus 2
    sumber = [{"sumber": "special_approval", "cara": "pengali_tetap", "pengali": 0.5},
              {"sumber": "customer", "cara": "ikut_pita", "pengali": 1.0},
              {"sumber": "special_order", "cara": "ikut_pita", "pengali": 1.0}]
    aturan = dict(price_basis="pricelist", price_bands=PITA, price_source_rules=sumber)
    a = _baris(100, 47_500, pid="prd_ka5_kwg_mrh", kategori="KA5Batik", harga=47_500, list_price=50_000,
               price_source="special_approval", commission_rule=_potret(f["pt"], 3000, artikel=KAWUNG, **aturan))
    b = _baris(100, 47_500, pid="prd_ka5_mega_mrh", kategori="KA5Batik", harga=47_500, list_price=50_000,
               commission_rule=_potret(f["pt"], 3500, **aturan))
    await _pesanan(db, "so_ka5_u7", "cus_ka5_u7", [a, b], bayar=3_800_000)
    hasil = await _komisi(f, "u7")
    assert (hasil["total_incentive"], hasil["projection_full"]) == (130_000, 325_000)
    rows = {r["template_id"]: r for r in hasil["breakdown"]}
    ra, rb = rows[KAWUNG["id"]], rows[MEGA["id"]]
    assert (ra["qty_base"], ra["rate"], ra["price_factor"], ra["price_reason"], ra["commission"]) == (
        40, 3000, 0.5, "sumber_tetap:special_approval", 60_000)
    assert ra["price_reason_label"] == "Harga khusus, memakai pengali tetap"
    assert (rb["qty_base"], rb["rate"], rb["price_factor"], rb["price_reason"], rb["commission"]) == (
        40, 3500, 0.5, "pita", 70_000)
    assert rb["price_reason_label"] == "5% di bawah harga acuan"


async def test_KA5_U8_tarif_dihapus_pesanan_lama_tetap(db, klien, f):  # Review Focus 5 (bagian 1)
    rate = await _tarif_api(klien, f["adm"], entity_id=KSC, template_id="tpl_ka5_u8", per_unit_amount=3500)
    items = [_baris(100, 50_000, pid="prd_ka5_u8", kategori="KA5U8")]
    await _potret_asli(db, items)
    await _pesanan(db, "so_ka5_u8", "cus_ka5_u8", items)
    assert (await _komisi(f, "u8"))["total_incentive"] == 350_000
    r = await klien.delete(f"/api/incentive-rates/{rate['id']}", headers=f["adm"], params={"reason": "uji KA-5"})
    assert r.status_code == 200, r.text
    assert await db.incentive_rates.find_one({"id": rate["id"]}) is None
    hasil = await _komisi(f, "u8")
    assert hasil["total_incentive"] == 350_000
    assert _satu(hasil)["rate_origin"] == "Tarif artikel (PT ini)"


# ── Perbaikan sesudah tinjauan pengendali (INV-CFG-09; isian None = mesin lama) ─────────────────────────────────────
async def test_KA5_F1_pita_kosong_ikut_bawaan_registri():
    from services.commission_rules import pengali_harga
    tarif = {"per_unit_amount": 3500, "margin_cap_pct": 0}
    line = _baris(100, 47_500, pid="prd_ka5_x", kategori="KA5Batik", harga=50_000, list_price=50_000)
    for pita in ({}, {"price_bands": None}, {"price_bands": []}):
        aturan = {"tarif": tarif, "price_basis": "pricelist", "acuan": "daftar_pt", **pita}
        assert pengali_harga(aturan, line) == (3500, 1.0, "pita", 5.0), pita
    # aturan asal harga kosong → bawaan registri (semua ikut pita), pita kosong → ×1,0
    khusus = {**line, "price_source": "special_approval"}
    aturan = {"tarif": tarif, "price_basis": "pricelist", "acuan": "daftar_pt", "price_source_rules": []}
    assert pengali_harga(aturan, khusus) == (3500, 1.0, "pita", 5.0)


def _baris_null() -> List[Dict[str, Any]]:
    return [_baris(1000, 50_000, pid="prd_ka5_n1", kategori="KA5-NULL", sku="NULL-1", unit_cost=49_900),
            _baris(100, 47_500, pid="prd_ka5_n2", kategori="KA5-NULL", sku="NULL-2", harga=50_000,
                   discount_percent=5)]


async def test_KA5_F2_isian_tarif_null_sama_dengan_mesin_lama(db, f):
    await _pesanan(db, "so_ka5_f2", "cus_ka5_f2", _baris_null())
    hasil = await _komisi(f, "f2")
    assert hasil["total_incentive"] == 525_000
    rows = {r["sku"]: r for r in hasil["breakdown"]}
    assert (rows["NULL-1"]["commission"], rows["NULL-1"]["capped"]) == (500_000, False)
    assert (rows["NULL-2"]["commission"], rows["NULL-2"]["price_factor"]) == (25_000, 0.5)
    # jalur potret (`create_order`): isian None tetap None di potret, hasilnya sama
    items = _baris_null()
    await _potret_asli(db, items)
    t = items[0]["commission_rule"]["tarif"]
    assert (t["margin_cap_pct"], t["discount_threshold"], t["discount_factor"]) == (None, None, 0.5)
    await _pesanan(db, "so_ka5_f2s", "cus_ka5_f2s", items)
    assert (await _komisi(f, "f2s"))["total_incentive"] == 525_000


async def test_KA5_F3_isian_tarif_tidak_ada_ikut_pt(db, f):
    items = [_baris(1000, 50_000, pid="prd_ka5_a1", kategori="KA5-ABSEN", sku="ABSEN-1", unit_cost=49_900),
             _baris(100, 47_500, pid="prd_ka5_a2", kategori="KA5-ABSEN", sku="ABSEN-2", harga=50_000,
                    discount_percent=5)]
    await _pesanan(db, "so_ka5_f3", "cus_ka5_f3", items)
    hasil = await _komisi(f, "f3")
    assert hasil["total_incentive"] == 100_000
    rows = {r["sku"]: r for r in hasil["breakdown"]}
    assert (rows["ABSEN-1"]["commission"], rows["ABSEN-1"]["capped"]) == (50_000, True)
    assert (rows["ABSEN-2"]["commission"], rows["ABSEN-2"]["price_factor"]) == (50_000, 1.0)
    salinan = [dict(it) for it in items]
    await _potret_asli(db, salinan)
    t = salinan[0]["commission_rule"]["tarif"]
    assert (t["margin_cap_pct"], t["discount_threshold"], t["discount_mechanic"]) == (
        f["pt"]["default_margin_cap_pct"], f["pt"]["discount_threshold"], f["pt"]["discount_mechanic"])
    assert (t["margin_cap_pct"], t["discount_threshold"]) == (50, 10)
