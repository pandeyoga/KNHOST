"""KA-6 — pengali capaian target + pembekuan aturan bulan saat akrual komisi dibukukan.

Rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §6.4 (+ 6.5a: rincian per sales disimpan
bersama akrual); rencana Task 6 (Review Focus 3). Pembaca: `commission_rules.pengali_capaian` / `capaian_aktif` /
`bekukan_periode`; mesin `sales_force_service.compute_commission` (strategi `per_sku` bawaan).

Fixture (pola KM-T5 F5: pesanan + surat jalan disisip, jurnal pendapatan lewat `gl.post_order_revenue_and_cogs`, target
lewat `incentive_targets.save_target`, lalu fakta insentif & analitik dibangun ulang). PT `ent_ksc`. Pengaturan pengali
capaian ditulis per uji (lapisan PT, `config_resolver.set_value` beralasan) dan dihapus lagi sesudahnya (`_aturan`),
supaya uji tidak saling memengaruhi. Kunci capaian bertanggal (dibaca menurut waktu berlakunya, tidak diproyeksikan ke
penyimpanan lama), jadi menghapus barisnya mengembalikan bawaan.

Potret aturan baris: tarif artikel "Batik KA6" Rp 350/yd, batas margin 0, basis diskon baris (bawaan) → pengali harga 1.

Hitung tangan (harga jual Rp 50.000/yd, Andi = sales pesanan 100 %):
  SO-OKT  4.000 yd = 200.000.000, dibuat 2 Okt, terkirim penuh 5 Okt → omzet bersih Okt 200 jt; bayar 20 Okt 40 jt
          → fraksi 0,2 → 800 yd × 350 = 280.000 (komisi dasar Okt).
  SO-NOV  10.000 yd = 500.000.000, dibuat 2 Nov, terkirim penuh 5 Nov → omzet bersih Nov 500 jt; bayar 10 Nov 50 jt
          → fraksi 0,1 → 1.000 yd × 350 = 350.000 (komisi dasar Nov). Uang masuk Nov 50 jt.
  Target bulanan Andi: Okt omzet 400 jt (pencairan 400 jt) · Nov omzet 400 jt, pencairan 100 jt · Des omzet 100 jt
  (tanpa omzet Des → capaian 0 %).
  Jenjang J = mulai 0 % ×0,5 · 80 % ×1 · 100 % ×1,2.
  U3  Nov omzet 500/400 = 125,0 % → ×1,2 → 350.000 × 1,2 = 420.000. Basis uang masuk: 50/100 = 50,0 % → ×0,5 → 175.000.
  U6  Okt 200/400 = 50,0 % → ×0,5 → 140.000 · Nov ×1,2 → 420.000 · Des 0 % → ×0,5 → 0. Triwulan IV = 560.000
      (dihitung sekali untuk triwulan tanpa pemecahan bulan = 280.000 + 350.000 = 630.000 × 1). Proyeksi penuh = SATU
      lintasan triwulan × pengali bulan terakhir (Des ×0,5): (4.000 + 10.000) × 350 × 0,5 = 2.450.000 (bukan Σ proyeksi
      bulanan 700.000 + 4.200.000 = 4.900.000).
  U6b Citra (pengali menyala HANYA Oktober: berlaku 1 Okt, mati 1 Nov). SO-CIT 1.000 yd = 50.000.000, dibuat 3 Okt,
      terkirim 6 Okt → omzet Okt 50 jt / target Okt 50 jt = 100,0 % → ×1,2; bayar 25 Okt 10 jt (fraksi 0,2) dan
      10 Nov 20 jt (0,4). Okt 200 yd × 350 × 1,2 = 84.000 · Nov (mati) 400 yd × 350 = 140.000 · Des 0 → Triwulan IV
      224.000 (tanpa pemecahan: 600 × 350 = 210.000). Proyeksi: SO-CIT dihitung sekali × pengali Des (mati, ×1) =
      1.000 × 350 = 350.000 (Σ proyeksi bulanan menghitungnya dua kali: 420.000 + 350.000 = 770.000).
  U4  Budi: pesanan 100 yd lunas 12 Nov (tanpa surat jalan, tanpa omzet) → 100 × 350 = 35.000; hanya target TRIWULAN
      IV → pengali 1, alasan "tanpa_target_bulanan".
"""
from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
NOV, OKT, DES, Q4 = "2026-11", "2026-10", "2026-12", "2026-Q4"
PRD = "prd_ka6_batik"
TPL = {"id": "tpl_ka6_batik", "nama": "Batik KA6", "kode": "BTK-KA6"}
CA, CB, CC = "cus_ka6_andi", "cus_ka6_budi", "cus_ka6_citra"
JENJANG = [{"capaian_min_pct": 0, "pengali": 0.5}, {"capaian_min_pct": 80, "pengali": 1.0},
           {"capaian_min_pct": 100, "pengali": 1.2}]
AKTIF, BASIS = "commission.achievement_multiplier", "commission.achievement_basis"
TIERS = "commission.achievement_tiers"
AWAL_OKT, AWAL_NOV = "2026-10-01T00:00", "2026-11-01T00:00"


def _iso(tgl: str, jam: str = "03:00:00") -> str:
    return f"{tgl}T{jam}+00:00"


def _potret(pt: Dict[str, Any]) -> Dict[str, Any]:
    from services.commission_rules import potret
    tarif = {"id": "irate_ka6", "asal_tingkat": "artikel", "asal_lingkup": "pt", "per_unit_amount": 350.0,
             "margin_cap_pct": 0.0}
    return potret(tarif, pt, artikel=TPL, sumber="pesanan", waktu=now_iso())


def _item(qty: int, pot: Dict[str, Any]) -> Dict[str, Any]:
    return {"product_id": PRD, "sku": "KA6-01", "product_name": "Batik KA6 Merah", "quantity": qty,
            "base_quantity": qty, "unit": "yard", "base_unit": "yard", "price": 50_000, "line_total": qty * 50_000,
            "discount_percent": 0, "list_price": 50_000, "list_price_source": "entity", "global_price": 50_000,
            "floor_price": 45_000, "unit_cost": 30_000, "price_source": "entity", "category": "KA6Batik",
            "line_code": "batik", "commission_rule": pot}


async def _pesanan(db, gl, so_id: str, cust: str, sales_id: str, qty: int, pot: Dict[str, Any], *, dibuat: str,
                   dikirim: Optional[str], bayar: List[Tuple[float, str]]) -> None:
    """Pesanan satu baris; bila `dikirim`, terkirim penuh satu surat jalan + jurnal pendapatan lewat fungsi asli."""
    nomor = f"SO/KA6/{so_id[-3:].upper()}"
    gt = qty * 50_000
    await db.sales_orders.insert_one({
        "id": so_id, "number": nomor, "entity_id": KSC, "customer_id": cust, "customer_name": f"Toko {cust[-4:]}",
        "status": "shipped" if dikirim else "completed", "payment_term_code": "NET30", "items": [_item(qty, pot)],
        "subtotal": gt, "grand_total": gt, "ppn_amount": 0,
        "payments": [{"amount": a, "created_at": _iso(t), "method": "transfer"} for a, t in bayar],
        "sales_team": [{"sales_id": sales_id, "role": "pic", "split_pct": 100.0}],
        "created_at": _iso(dibuat), "updated_at": now_iso()})
    if dikirim:
        await db.shipments.insert_one({"id": f"shp_{so_id}", "shipment_no": f"SJ/KA6/{so_id[-3:].upper()}",
                                       "entity_id": KSC, "order_id": so_id, "order_number": nomor, "product_id": PRD,
                                       "qty": qty, "unit": "yard", "status": "dispatched", "created_at": _iso(dikirim)})
        await gl.post_order_revenue_and_cogs(so_id)


@pytest.fixture(scope="module")
async def f6(db, akun, kepala_admin):
    from services import analytics_facts, incentive_facts
    from services import gl_service as gl
    from services import incentive_targets as itg
    from services.commission_rules import aturan_pt
    u: Dict[str, Dict[str, Any]] = {}
    for kode, nama in (("andi", "Andi KA6"), ("budi", "Budi KA6"), ("citra", "Citra KA6")):
        u[kode] = await akun("sales", entitas=(KSC,))
        await db.users.update_one({"id": u[kode]["id"]}, {"$set": {"name": nama}})
    await db.product_templates.insert_one({"id": TPL["id"], "name": TPL["nama"], "sku_prefix": TPL["kode"],
                                           "category": "KA6Batik", "status": "active"})
    await db.products.insert_one({"id": PRD, "name": "Batik KA6 Merah", "sku": "KA6-01", "template_id": TPL["id"],
                                  "base_unit": "yard", "price": 50_000, "category": "KA6Batik", "line_code": "batik",
                                  "is_active": True})
    await db.customers.insert_many([
        {"id": c, "name": f"Toko KA6 {k}", "entity_id": KSC, "status": "active", "deposit_balance": 0.0,
         "assigned_sales_id": u[k]["id"], "created_at": _iso("2026-01-05"),
         "sales_team": [{"sales_id": u[k]["id"], "role": "pic", "split_pct": 100.0}]}
        for c, k in ((CA, "andi"), (CB, "budi"), (CC, "citra"))])
    pot = _potret(await aturan_pt(KSC))
    await _pesanan(db, gl, "so_ka6_okt", CA, u["andi"]["id"], 4_000, pot, dibuat="2026-10-02", dikirim="2026-10-05",
                   bayar=[(40_000_000, "2026-10-20")])
    await _pesanan(db, gl, "so_ka6_nov", CA, u["andi"]["id"], 10_000, pot, dibuat="2026-11-02", dikirim="2026-11-05",
                   bayar=[(50_000_000, "2026-11-10")])
    await _pesanan(db, gl, "so_ka6_bdi", CB, u["budi"]["id"], 100, pot, dibuat="2026-11-03", dikirim=None,
                   bayar=[(5_000_000, "2026-11-12")])
    await _pesanan(db, gl, "so_ka6_cit", CC, u["citra"]["id"], 1_000, pot, dibuat="2026-10-03", dikirim="2026-10-06",
                   bayar=[(10_000_000, "2026-10-25"), (20_000_000, "2026-11-10")])
    for sid, jenis, per, omzet, cair in ((u["andi"]["id"], "month", OKT, 400e6, 400e6),
                                         (u["andi"]["id"], "month", NOV, 400e6, 100e6),
                                         (u["andi"]["id"], "month", DES, 100e6, 100e6),
                                         (u["citra"]["id"], "month", OKT, 50e6, 50e6),
                                         (u["citra"]["id"], "month", NOV, 100e6, 100e6),
                                         (u["budi"]["id"], "quarter", Q4, 1e6, 1e6)):
        await itg.save_target(KSC, {"sales_id": sid, "period_type": jenis, "period": per,
                                    "target_sales_amount": omzet, "target_collection_amount": cair}, AKTOR_UJI)
    await incentive_facts.rebuild()
    await analytics_facts.rebuild_facts()
    return {"u": u, "adm": kepala_admin}


@contextlib.asynccontextmanager
async def _aturan(db, *isi: Tuple[str, Any, str]):
    """Tulis nilai pengali capaian lapisan PT `ent_ksc` [(kunci, nilai, berlaku sejak)]; baris dihapus saat keluar."""
    from services import config_resolver as resolver
    ids: List[str] = []
    try:
        for key, nilai, sejak in isi:
            row = await resolver.set_value(key, nilai, scope_type="entity", scope_id=KSC, actor="uji",
                                           reason="uji KA-6", effective_from=sejak)
            ids.append(row["id"])
        yield
    finally:
        await db.config_values.delete_many({"id": {"$in": ids}})


def _menyala(sejak: str = AWAL_OKT, jenjang: Optional[List[Dict[str, Any]]] = None, basis: str = "omzet_bersih"):
    return ((AKTIF, True, sejak), (BASIS, basis, sejak), (TIERS, jenjang or JENJANG, sejak))


async def _komisi(f6, kode: str, period: str = NOV, entity_id: str = KSC) -> Dict[str, Any]:
    from services import sales_force_service as sfs
    return await sfs.compute_commission(f6["u"][kode]["id"], period, entity_id)


async def _pengali(f6, kode: str, period: str = NOV, entity_id: str = KSC):
    from services.commission_rules import pengali_capaian
    return await pengali_capaian(entity_id, f6["u"][kode]["id"], period)


def _faktor_rincian(hasil: Dict[str, Any]) -> List[float]:
    return sorted({r["achievement_factor"] for r in hasil["breakdown"] if r["commission"]})


# ═══ U1 — jenjang = nilai yang berlaku pada AKHIR bulan komisi ══════════════════════════════════════════════════════
async def test_KA6_U1_jenjang_akhir_bulan(db, f6):
    from services.commission_rules import aturan_capaian
    jenjang_30nov = [{"capaian_min_pct": 0, "pengali": 1.0}, {"capaian_min_pct": 100, "pengali": 1.5}]
    jenjang_1des = [{"capaian_min_pct": 0, "pengali": 0.8}, {"capaian_min_pct": 100, "pengali": 2.0}]
    # menyala sejak 1 Nov (sudah lewat): tidak dipakai untuk Oktober — nilai yang berlaku SESUDAH bulan itu tidak ikut
    async with _aturan(db, *_menyala(AWAL_NOV)):
        akhir_okt = await aturan_capaian(KSC, at=datetime.fromisoformat("2026-10-31T23:59:59+07:00"))
        assert akhir_okt["aktif"] is False
        faktor, info = await _pengali(f6, "andi", OKT)
        assert (faktor, info["alasan"]) == (1.0, "mati")
        async with _aturan(db, (TIERS, jenjang_30nov, "2026-11-30T12:00"), (TIERS, jenjang_1des, "2026-12-01T00:00")):
            faktor, info = await _pengali(f6, "andi", NOV)
            assert faktor == 1.5   # 125 % → baris "mulai 100 %" jenjang berlaku 30 Nov; jenjang 1 Des tidak dipakai
            assert info == {"aktif": True, "basis": "omzet_bersih", "capaian_pct": 125.0,
                            "sumber_jenjang": "akhir_bulan", "alasan": "jenjang"}
            faktor, info = await _pengali(f6, "andi", DES)
            assert (faktor, info["capaian_pct"]) == (0.8, 0.0)   # Desember: capaian 0 % → jenjang 1 Des "mulai 0 %"


# ═══ U2 — pengali capaian mati (bawaan) → ×1 ════════════════════════════════════════════════════════════════════════
async def test_KA6_U2_mati_bawaan_x1(db, f6):
    hasil = await _komisi(f6, "andi")
    assert hasil["total_incentive"] == 350_000
    assert hasil["achievement_multiplier"]["factor"] == 1.0
    assert hasil["achievement_multiplier"]["info"]["alasan"] == "mati"
    assert hasil["achievement_multiplier"]["info"]["aktif"] is False
    assert _faktor_rincian(hasil) == [1.0]
    from services.commission_rules import capaian_aktif
    assert await capaian_aktif(KSC) is False


# ═══ U3 — capaian omzet bersih vs target bulanan ═══════════════════════════════════════════════════════════════════
async def test_KA6_U3_capaian_omzet(db, f6):
    async with _aturan(db, *_menyala()):
        hasil = await _komisi(f6, "andi")
        assert hasil["total_incentive"] == 420_000      # 350.000 × 1,2
        assert hasil["achievement_multiplier"] == {"factor": 1.2, "info": {
            "aktif": True, "basis": "omzet_bersih", "capaian_pct": 125.0, "sumber_jenjang": "akhir_bulan",
            "alasan": "jenjang"}}
        assert _faktor_rincian(hasil) == [1.2]
        assert hasil["projection_full"] == 4_200_000    # 10.000 × 350 × 1,2
    # basis uang masuk: 50 jt / target pencairan 100 jt = 50 % → ×0,5
    async with _aturan(db, *_menyala(basis="uang_masuk")):
        hasil = await _komisi(f6, "andi")
        assert hasil["total_incentive"] == 175_000
        info = hasil["achievement_multiplier"]["info"]
        assert (info["basis"], info["capaian_pct"], hasil["achievement_multiplier"]["factor"]) == (
            "uang_masuk", 50.0, 0.5)


# ═══ U4 — tanpa target BULANAN (target triwulan tidak dipakai) ═════════════════════════════════════════════════════
async def test_KA6_U4_tanpa_target_bulanan(db, f6):
    async with _aturan(db, *_menyala()):
        faktor, info = await _pengali(f6, "budi")
        assert (faktor, info["alasan"], info["capaian_pct"]) == (1.0, "tanpa_target_bulanan", None)
        hasil = await _komisi(f6, "budi")
        assert hasil["total_incentive"] == 35_000
        assert hasil["achievement_multiplier"]["info"]["alasan"] == "tanpa_target_bulanan"


# ═══ U5 — "Semua PT" → ×1 (Review Focus 3) ═════════════════════════════════════════════════════════════════════════
async def test_KA6_U5_semua_pt(db, f6):
    from services.commission_rules import capaian_aktif
    async with _aturan(db, *_menyala()):
        assert await capaian_aktif(KSC) is True
        assert await capaian_aktif("all") is False
        faktor, info = await _pengali(f6, "andi", entity_id="all")
        assert (faktor, info["alasan"]) == (1.0, "semua_pt")
        hasil = await _komisi(f6, "andi", entity_id="all")
        assert hasil["total_incentive"] == 350_000
        assert hasil["achievement_multiplier"]["info"]["alasan"] == "semua_pt"
        assert _faktor_rincian(hasil) == [1.0]
        q = await _komisi(f6, "andi", Q4, entity_id="all")   # Semua PT: triwulan tidak dipecah per bulan
        assert q["total_incentive"] == 630_000 and q["achievement_multiplier"]["info"]["alasan"] == "semua_pt"


# ═══ U6 — triwulan = Σ hasil per bulan; proyeksi satu lintasan × pengali bulan terakhir (Review Focus 3) ══════════════
async def test_KA6_U6_triwulan_jumlah_bulanan(db, f6):
    from services import sales_force_service as sfs
    sid = f6["u"]["andi"]["id"]
    # pengali menyala: mesin dipanggil langsung dengan triwulan → ×1 berkode "bukan_bulan"
    async with _aturan(db, *_menyala()):
        langsung = await sfs._compute_commission_per_sku(sid, Q4, KSC, {})
        assert langsung["total_incentive"] == 630_000
        assert langsung["achievement_multiplier"]["info"]["alasan"] == "bukan_bulan"
        bulan = [await _komisi(f6, "andi", m) for m in (OKT, NOV, DES)]
        assert [b["total_incentive"] for b in bulan] == [140_000, 420_000, 0]
        assert [b["achievement_multiplier"]["factor"] for b in bulan] == [0.5, 1.2, 0.5]
        q = await _komisi(f6, "andi", Q4)
        assert q["period"] == Q4 and q["strategy"] == "per_sku"
        assert q["total_incentive"] == q["commission"] == 560_000
        # proyeksi: satu lintasan triwulan (tiap pesanan sekali) × pengali Desember 0,5 — bukan Σ proyeksi bulanan
        assert q["projection_full"] == 2_450_000
        assert sum(b["projection_full"] for b in bulan) == 4_900_000
        assert (q["base_amount"], q["kpi"]) == (langsung["base_amount"], langsung["kpi"])
        rincian = sorted((r["achievement_factor"], r["qty_base"], r["commission"]) for r in q["breakdown"]
                         if r["commission"])
        assert rincian == [(0.5, 800, 140_000), (1.2, 1_000, 420_000)]
        am = q["achievement_multiplier"]
        assert am["factor"] is None and am["info"]["alasan"] == "per_bulan"
        assert [(b["period"], b["factor"]) for b in am["per_bulan"]] == [(OKT, 0.5), (NOV, 1.2), (DES, 0.5)]
    # pengali mati → triwulan dihitung sekali seperti sebelum fitur ini (bukan dipecah)
    q = await _komisi(f6, "andi", Q4)
    assert q["total_incentive"] == 630_000 and q["achievement_multiplier"]["info"]["alasan"] == "mati"


# ═══ U6b — pengali menyala hanya Oktober: triwulan tetap dipecah; pesanan dibayar dua bulan diproyeksi sekali ═════════
async def test_KA6_U6b_menyala_satu_bulan_proyeksi_sekali(db, f6):
    from services.commission_rules import capaian_aktif
    sid = f6["u"]["citra"]["id"]
    async with _aturan(db, *_menyala(), (AKTIF, False, AWAL_NOV)):
        assert await capaian_aktif(KSC) is False                    # hari ini mati …
        assert await capaian_aktif(KSC, [OKT, NOV, DES]) is True    # … tetapi menyala di Oktober
        bulan = [await _komisi(f6, "citra", m) for m in (OKT, NOV, DES)]
        assert [b["total_incentive"] for b in bulan] == [84_000, 140_000, 0]
        assert [(b["achievement_multiplier"]["factor"], b["achievement_multiplier"]["info"]["alasan"])
                for b in bulan] == [(1.2, "jenjang"), (1.0, "mati"), (1.0, "mati")]
        q = await _komisi(f6, "citra", Q4)
        assert q["sales_id"] == sid and q["total_incentive"] == 224_000      # bukan 210.000 (tanpa pemecahan)
        assert [b["factor"] for b in q["achievement_multiplier"]["per_bulan"]] == [1.2, 1.0, 1.0]
        assert q["projection_full"] == 350_000                              # SO-CIT sekali × pengali Des (×1)
        assert sum(b["projection_full"] for b in bulan) == 770_000           # Σ bulanan menghitungnya dua kali


# ═══ U7 — aturan dibekukan saat akrual dibukukan ═══════════════════════════════════════════════════════════════════
async def test_KA6_U7_beku_saat_akrual(klien, db, f6):
    from services.commission_rules import aturan_capaian
    sid = f6["u"]["andi"]["id"]
    async with _aturan(db, *_menyala(AWAL_NOV)):
        r = await klien.post("/api/sales/incentive/post-gl", params={"period": NOV, "entity_id": KSC},
                             headers=f6["adm"])
        assert r.status_code == 200, r.text
        assert r.json()["created"] is True, r.json()
        doc = await db.commission_period_rules.find_one({"entity_id": KSC, "period": NOV}, {"_id": 0})
        assert doc and doc["id"].startswith("cpr_")
        assert doc["achievement"] == {"aktif": True, "basis": "omzet_bersih", "jenjang": JENJANG}
        andi = next(s for s in doc["sales"] if s["sales_id"] == sid)
        assert andi["total"] == 420_000
        assert [(b["qty_base"], b["achievement_factor"], b["commission"]) for b in andi["breakdown"]
                if b["commission"]] == [(1_000, 1.2, 420_000)]
        assert r.json()["amount"] == round(sum(s["total"] for s in doc["sales"]), 2)
        assert doc["recorded_by"] and doc["recorded_at"]
        # jenjang diubah sesudah akrual, berlaku mundur 1 Nov → pengaturan berubah, komisi Nov tetap jenjang beku
        baru = [{"capaian_min_pct": 0, "pengali": 1.0}, {"capaian_min_pct": 100, "pengali": 2.0}]
        async with _aturan(db, (TIERS, baru, AWAL_NOV)):
            akhir_nov = await aturan_capaian(KSC, at=datetime.fromisoformat("2026-11-30T23:59:59+07:00"))
            assert akhir_nov["jenjang"] == baru
            faktor, info = await _pengali(f6, "andi")
            assert (faktor, info["sumber_jenjang"], info["alasan"]) == (1.2, "beku", "jenjang")
            assert (await _komisi(f6, "andi"))["total_incentive"] == 420_000


# ═══ U8 — akrual ulang / koreksi tidak menimpa potret; bulan lama dipotret saat koreksi pertama ═════════════════════
async def test_KA6_U8_akrual_ulang_tidak_menimpa(db, f6):
    from services import gl_service as gl
    from services.commission_rules import bekukan_periode
    q = {"entity_id": KSC, "period": OKT}
    async with _aturan(db, *_menyala()):
        await gl.post_incentive_accrual(KSC, OKT, "Uji Satu", total=100_000, date="2026-10-31")
        d1 = await db.commission_period_rules.find_one(q, {"_id": 0})
        assert d1 and d1["recorded_by"] == "Uji Satu" and d1["achievement"]["aktif"] is True
    # pengaturan berubah (mati), akrual dikoreksi: cabang koreksi juga memanggil pembekuan — dokumen lama dikembalikan
    jurnal = await gl.post_incentive_accrual(KSC, OKT, "Uji Dua", total=150_000, date="2026-10-31")
    assert jurnal and jurnal["source_type"] == "incentive_accrual_adj"
    d2 = await bekukan_periode(KSC, OKT, oleh="Uji Tiga")
    assert (d2["id"], d2["recorded_at"], d2["recorded_by"], d2["achievement"]) == (
        d1["id"], d1["recorded_at"], "Uji Satu", d1["achievement"])
    assert await db.commission_period_rules.count_documents(q) == 1
    # bulan yang diakru sebelum fitur ini (tanpa potret): koreksi pertama memotretnya
    await db.commission_period_rules.delete_many(q)
    await gl.post_incentive_accrual(KSC, OKT, "Uji Empat", total=175_000, date="2026-10-31")
    d3 = await db.commission_period_rules.find_one(q, {"_id": 0})
    assert d3 and d3["recorded_by"] == "Uji Empat" and d3["achievement"]["aktif"] is False
