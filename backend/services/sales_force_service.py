"""Sales Force service (KN_17 §6) — KPI per salesperson + komisi (pencairan + tiered).

Semua KPI DERIVED dari sales_orders/payments/customers. Komisi default basis PENCAIRAN
(tertagih) + TIERED capaian target (S36).
"""
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from db import db
from core_utils import safe_doc
from services.customer_service import (
    compute_customer_credit, _order_grand_total, _order_paid, DEAD_STATUSES,
)
from services import costing_service
from services.commission_rules import (ALASAN_LABEL, KOREKSI_BATAL, KOREKSI_TUTUP_SISA, LABEL_DIBAWA, LABEL_TERBAWA,
                                      POTONGAN_DIBAWA, POTONGAN_TERBAWA, aturan_baris, bulan_awal_periode,
                                      bulan_periode, capaian_aktif, faktor_diskon, hitung_baris, hitung_koreksi,
                                      label_alasan, label_koreksi, pengali_capaian, saldo_potongan_awal)
from services.config_service import get_effective_settings

CATATAN_SIMULASI = ("Kedua kolom menghitung semua pesanan bulan ini dengan aturan hari ini (kiri) dan dengan perubahan "
                    "(kanan), jadi selisihnya murni akibat perubahan. Perubahan tarif berlaku untuk pesanan yang dibuat "
                    "sesudah disimpan; pesanan lama tetap memakai aturan saat pesanan dibuat.")

DEFAULT_TIERS = [
    {"min_achievement": 0, "rate": 1.0},
    {"min_achievement": 80, "rate": 1.5},
    {"min_achievement": 100, "rate": 2.5},
    {"min_achievement": 120, "rate": 3.5},
]


def _in_period(value: Any, period: Optional[str]) -> bool:
    """Cocokkan tanggal dengan periode: YYYY-MM (bulan), YYYY-Qn (kuartal), YYYY (tahun).
    G3 D4-DATE-01 — timestamp (Z/+00/+07/naif=UTC) dikonversi ke tanggal WIB dulu; date-only apa adanya."""
    if not period:
        return True
    from services.analytics_time import to_wib_date
    v = to_wib_date(value) or ""
    if len(v) < 7:
        return False
    ym, yr = v[:7], v[:4]
    p = str(period).upper()
    if "-Q" in p:
        try:
            py, q = p.split("-Q")
            q = int(q)
            months = [f"{py}-{m:02d}" for m in range((q - 1) * 3 + 1, (q - 1) * 3 + 4)]
            return ym in months
        except Exception:
            return False
    if len(p) == 4:
        return yr == p
    return ym == p[:7]


def _period_contains(requested: str, month_period: str) -> bool:
    """Apakah target bulanan (YYYY-MM) termasuk dalam periode yang diminta."""
    if not month_period:
        return False
    return _in_period(f"{month_period}-01", requested)


def _expand_periods(period_type: str, anchor: str, count: int) -> List[str]:
    """Daftar `count` periode terakhir (termasuk anchor) untuk tren komisi."""
    out: List[str] = []
    if period_type == "year":
        y = int(anchor[:4])
        out = [str(y - i) for i in range(count)]
    elif period_type == "quarter":
        py, q = anchor.upper().split("-Q")
        y, q = int(py), int(q)
        for _ in range(count):
            out.append(f"{y}-Q{q}")
            q -= 1
            if q < 1:
                q = 4
                y -= 1
    else:  # month
        y, m = int(anchor[:4]), int(anchor[5:7])
        for _ in range(count):
            out.append(f"{y}-{m:02d}")
            m -= 1
            if m < 1:
                m = 12
                y -= 1
    return out


def pick_tier_rate(tiers: List[Dict[str, Any]], achievement: float) -> float:
    rate = 0.0
    best = -1.0
    for t in (tiers or DEFAULT_TIERS):
        mn = float(t.get("min_achievement", 0) or 0)
        if achievement + 1e-9 >= mn and mn >= best:
            best = mn
            rate = float(t.get("rate", 0) or 0)
    return rate


async def sales_kpi(sales_id: str, period: Optional[str] = None, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """KPI salesperson untuk periode (YYYY-MM) atau seluruh waktu bila period kosong."""
    cust_filter: Dict[str, Any] = {"assigned_sales_id": sales_id}
    if entity_id and entity_id != "all":
        cust_filter["entity_id"] = entity_id
    customers = await db.customers.find(cust_filter, {"_id": 0}).to_list(2000)
    cust_ids = [c["id"] for c in customers]

    orders: List[Dict[str, Any]] = []
    if cust_ids:
        oq: Dict[str, Any] = {"customer_id": {"$in": cust_ids}}
        if entity_id and entity_id != "all":
            oq["entity_id"] = entity_id   # SO entitas lain dari pelanggan yang sama tidak ikut dihitung
        orders = await db.sales_orders.find(oq, {"_id": 0}).to_list(8000)
    live_orders = [o for o in orders if o.get("status") not in DEAD_STATUSES]
    period_orders = [o for o in live_orders if _in_period(o.get("created_at"), period)]

    total_sales = sum(_order_grand_total(o) for o in period_orders)
    total_collected = 0.0
    for o in live_orders:
        for p in (o.get("payments") or []):
            if _in_period(p.get("created_at") or p.get("date"), period):
                total_collected += float(p.get("amount", 0) or 0)

    # K-01 (26 Okt) — `overdue_amount` (Performa Saya "Lewat Jatuh Tempo", papan tim Dasbor Manajer) memakai definisi
    # layar Piutang: lewat ≥ 1 hari setelah jatuh tempo (SJ pertama + termin) — diselaraskan di
    # `compute_customer_credit`; cakupan tetap pelanggan milik sales ini (`assigned_sales_id`).
    ar = overdue = ledger = 0.0
    blocked = warning = 0
    from services import credit_profile_service as _cps
    kc = _cps.cache_baru()   # KF-T7/CR-T1 — ambang & plafon bawaan dibaca sekali per PT; profil kredit satu kueri
    await _cps.muat_profil(kc, [c.get("id") for c in customers])
    for c in customers:
        cc = await compute_customer_credit(c, entity_id, cache=kc)
        ar += cc["ar_outstanding"]
        ledger += cc["ar_ledger"]
        overdue += cc["overdue_amount"]
        if cc["status"] == "blocked":
            blocked += 1
        elif cc["status"] == "warning":
            warning += 1

    new_customers = len([c for c in customers if _in_period(c.get("created_at"), period)])
    orders_count = len(period_orders)
    aov = total_sales / orders_count if orders_count else 0
    collection_rate = (total_collected / total_sales) if total_sales else 0
    return {
        "sales_id": sales_id,
        "period": period or "all",
        "total_sales": round(total_sales, 2),
        "total_collected": round(total_collected, 2),
        "collection_rate": round(collection_rate, 4),
        "ar_outstanding": round(ar, 2),
        "ar_ledger": round(ledger, 2),
        "exposure": round(ar - ledger, 2),
        "overdue_amount": round(overdue, 2),
        "customers_count": len(customers),
        "new_customers": new_customers,
        "blocked_customers": blocked,
        "warning_customers": warning,
        "orders_count": orders_count,
        "avg_order_value": round(aov, 2),
    }


async def _targets_in_scope(sales_id: str, entity_id: Optional[str]) -> List[Dict[str, Any]]:
    """G3 D4-SALES-01 — target milik entitas yang diminta; target lama tanpa entity_id hanya
    berlaku untuk entitas induk sales tersebut (tidak dipinjam entitas lain)."""
    targets = await db.sales_targets.find({"sales_id": sales_id}, {"_id": 0}).to_list(400)
    if not entity_id or entity_id == "all":
        return targets
    home = (await db.users.find_one({"id": sales_id}, {"_id": 0, "entity_id": 1}) or {}).get("entity_id")
    return [t for t in targets if t.get("entity_id") == entity_id
            or (not t.get("entity_id") and home == entity_id)]


async def _target_collection_for(sales_id: str, period: str, entity_id: Optional[str] = None) -> float:
    """Agregasi target_collection bulanan yang termasuk dalam periode (bulan/kuartal/tahun)."""
    targets = await _targets_in_scope(sales_id, entity_id)
    total = 0.0
    for t in targets:
        if _period_contains(period, t.get("period", "")):
            total += float(t.get("target_collection_amount") or t.get("target_sales_amount") or 0)
    return total


async def _target_sales_for(sales_id: str, period: str, entity_id: Optional[str] = None) -> float:
    """Target PENJUALAN (omzet) dalam periode — terpisah dari target penagihan."""
    targets = await _targets_in_scope(sales_id, entity_id)
    return sum(float(t.get("target_sales_amount") or 0) for t in targets if _period_contains(period, t.get("period", "")))


async def _scheme_for(sales_id: str, period: str) -> Dict[str, Any]:
    """Skema insentif: exact period -> skema terbaru sales -> default tiers."""
    scheme = safe_doc(await db.sales_incentives.find_one({"sales_id": sales_id, "period": period}, {"_id": 0}))
    if not scheme:
        scheme = safe_doc(await db.sales_incentives.find_one(
            {"sales_id": sales_id}, {"_id": 0}, sort=[("period", -1)])) or {}
    return scheme


async def compute_commission(sales_id: str, period: str, entity_id: Optional[str] = None, *,
                             sumber_aturan: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None
                             ) -> Dict[str, Any]:
    """Dispatcher strategi komisi (EPIC4). Mode dari settings.commission.strategy:
      - per_sku (default v2): per-SKU, 3 faktor, margin-aware, on-collection.
      - achievement_tiered (arsip): basis pencairan × tier capaian target (lama).
    KA-8 — `sumber_aturan` (simulasi) menggantikan potret baris pada strategi per_sku; strategi arsip mengabaikannya.
    """
    settings = await get_effective_settings(entity_id if entity_id and entity_id != "all" else None)
    strategy = (settings.get("commission") or {}).get("strategy", "per_sku")
    if strategy == "achievement_tiered":
        return await _compute_commission_tiered(sales_id, period, entity_id)
    bulan = bulan_periode(period)
    # KA-6 — triwulan/tahun yang salah satu bulannya berpengali capaian menyala (aturan bulan itu) = Σ per bulan
    if bulan and await capaian_aktif(entity_id, bulan):
        return await _jumlah_bulanan(sales_id, period, entity_id, settings, bulan, sumber_aturan=sumber_aturan)
    return await _compute_commission_per_sku(sales_id, period, entity_id, settings, sumber_aturan=sumber_aturan)


async def boleh_lihat_komisi_sales(actor: Dict[str, Any], sales_id: str) -> bool:
    """Aturan satu pintu: komisi sales `sales_id` boleh dilihat `actor` bila itu dirinya, atau (cakupan data terbatas) anggota
    timnya, atau (cakupan penuh) ia memegang izin `order.view_sales_kpi` (PR-T4 / KN-E38)."""
    from dependencies import has_permission
    from services.data_scope import own_scoped, owner_ids
    if sales_id and sales_id == actor.get("id"):
        return True
    if own_scoped(actor):
        return sales_id in (await owner_ids(actor) or [])
    return bool(sales_id) and await has_permission(actor, "order", "view_sales_kpi")


TANDA_SIMULASI = {
    "strategi_berjenjang": "Draf tidak berpengaruh: PT ini memakai cara hitung berjenjang.",
    "tanpa_komisi_otomatis": "Komisi otomatis tidak dibayar di PT ini.",
}


async def simulate_commission(sales_id: str, period: str, entity_id: str, draft_rates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """KA-8 — simulasi "coba dulu" (keputusan R18, tinjauan akhir I3). Dua kolom pembanding SAMA-SAMA mengabaikan potret
    pesanan, jadi selisihnya murni efek draf:
      * `sekarang` ("Aturan sekarang") — tiap baris dihitung dari aturan SEKARANG (`aturan_dari_sekarang` atas indeks
        tarif tersimpan + aturan PT saat ini);
      * `dengan_perubahan` — sama, atas indeks tarif + draf (`indeks_dengan_draf`) dengan aturan PT yang sama.
    `komisi_menurut_potret` = hasil mesin biasa (aturan saat pesanan dibuat) — angka yang akan dibayar, untuk baris info.
    `tanda` = `[{kode, pesan}]`: strategi arsip berjenjang (draf tidak berpengaruh) dan mode gaji `sheet`/`off` (komisi
    otomatis tidak dibayar). Tidak menulis apa pun. `draft_rates` = `[{template_id|product_id|category, per_unit_amount,
    margin_cap_pct?}]`; draf tidak sah → `HTTPException` 400."""
    from services.commission_rate_service import indeks_dengan_draf
    from services.commission_rules import aturan_dari_sekarang, aturan_pt, muat_indeks_tarif
    from services.incentive_payroll import TANPA_MESIN, mode_pt
    ent = entity_id or ""
    pt = await aturan_pt(entity_id)

    def _sumber(indeks: Dict[str, Any]):
        cache: Dict[Any, Any] = {("indeks", ent): indeks, ("pt", ent): pt}

        async def _aturan(line: Dict[str, Any]) -> Dict[str, Any]:
            return await aturan_dari_sekarang(line, entity_id, cache, sumber="simulasi")
        return _aturan

    menurut_potret = await compute_commission(sales_id, period, entity_id)
    sekarang = await compute_commission(sales_id, period, entity_id, sumber_aturan=_sumber(await muat_indeks_tarif(entity_id)))
    dengan = await compute_commission(sales_id, period, entity_id,
                                      sumber_aturan=_sumber(await indeks_dengan_draf(entity_id, draft_rates)))
    tanda = []
    if menurut_potret.get("strategy") == "achievement_tiered":
        tanda.append({"kode": "strategi_berjenjang", "pesan": TANDA_SIMULASI["strategi_berjenjang"]})
    if await mode_pt(entity_id) in TANPA_MESIN:
        tanda.append({"kode": "tanpa_komisi_otomatis", "pesan": TANDA_SIMULASI["tanpa_komisi_otomatis"]})
    return {"sekarang": sekarang, "dengan_perubahan": dengan,
            "komisi_menurut_potret": round(float(menurut_potret.get("total_incentive") or 0), 2),
            "tanda": tanda, "catatan": CATATAN_SIMULASI}


async def _jumlah_bulanan(sales_id: str, period: str, entity_id: Optional[str], settings: Dict[str, Any],
                          bulan: List[str], *, sumber_aturan: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None
                          ) -> Dict[str, Any]:
    """KA-6 (Review Focus 3) — triwulan/tahun berpengali capaian: komisi = Σ hasil `_compute_commission_per_sku` tiap
    bulan, masing-masing dengan pengali capaian bulannya; rincian digabung (baris dengan faktor sama dijumlah, pengali
    capaian berbeda = baris berbeda). `projection_full` = SATU lintasan mesin atas seluruh periode (tiap pesanan yang
    ikut dihitung sekali, seperti mesin lama) dengan pengali capaian bulan TERAKHIR periode itu; angka ringkasan
    (pencairan, target, KPI) dari lintasan yang sama."""
    hasil = [await _compute_commission_per_sku(sales_id, m, entity_id, settings, sumber_aturan=sumber_aturan)
             for m in bulan]
    akhir = hasil[-1]["achievement_multiplier"]
    utuh = await _compute_commission_per_sku(sales_id, period, entity_id, settings, sumber_aturan=sumber_aturan,
                                             capaian_tetap=(akhir["factor"], akhir["info"]))
    gabung: Dict[tuple, Dict[str, Any]] = {}
    for h in hasil:
        for r in h["breakdown"]:
            key = tuple((k, r[k]) for k in sorted(r) if k not in ("qty_base", "commission"))
            g = gabung.setdefault(key, {**r, "qty_base": 0.0, "commission": 0.0})
            g["qty_base"] += r["qty_base"]
            g["commission"] += r["commission"]
    rows = sorted(gabung.values(), key=lambda x: x["commission"], reverse=True)
    for r in rows:
        r["qty_base"], r["commission"] = round(r["qty_base"], 2), round(r["commission"], 2)
    total = round(sum(h["total_incentive"] for h in hasil), 2)
    per_bulan = [{"period": m, **h["achievement_multiplier"]} for m, h in zip(bulan, hasil)]
    return {
        **utuh,
        "commission": total,
        "total_incentive": total,
        # BTP-5 — Σ mentah per bulan; saldo masuk = saldo bulan pertama, saldo keluar = saldo bulan terakhir
        "commission_raw": round(sum(h["commission_raw"] for h in hasil), 2),
        "carry_in": hasil[0]["carry_in"],
        "carry_out": hasil[-1]["carry_out"],
        "breakdown": rows,
        "achievement_multiplier": {"factor": None, "info": {"aktif": True, "basis": None, "capaian_pct": None,
                                                            "sumber_jenjang": None, "alasan": "per_bulan"},
                                   "per_bulan": per_bulan},
    }


async def _compute_commission_tiered(sales_id: str, period: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """ARSIP — Komisi = basis PENCAIRAN (tertagih) x rate tiered capaian target (S36) + bonus."""
    kpi = await sales_kpi(sales_id, period, entity_id)
    scheme = await _scheme_for(sales_id, period)
    basis = scheme.get("basis", "collection")
    base_amount = kpi["total_collected"] if basis != "sales" else kpi["total_sales"]
    target_collection = await _target_collection_for(sales_id, period, entity_id)
    achievement = (base_amount / target_collection * 100) if target_collection else 0
    tiers = scheme.get("tiers") or DEFAULT_TIERS
    rate = pick_tier_rate(tiers, achievement)
    commission = base_amount * rate / 100
    bonus_new = float(scheme.get("bonus_new_customer", 0) or 0) * kpi["new_customers"]
    total = commission + bonus_new
    return {
        "sales_id": sales_id,
        "period": period,
        "strategy": "achievement_tiered",
        "basis": basis,
        "base_amount": round(base_amount, 2),
        "target_amount": round(target_collection, 2),
        "achievement_pct": round(achievement, 2),
        "applied_rate": rate,
        "commission": round(commission, 2),
        "bonus_new_customer": round(bonus_new, 2),
        "total_incentive": round(total, 2),
        "breakdown": [],
        "projection_full": round(total, 2),
        "kpi": kpi,
    }


async def _load_incentive_rates(entity_id: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Map category -> rate doc. Prioritas entity spesifik, fallback 'all'.

    KA-5 — mesin komisi tidak memakainya lagi (tarif lewat potret baris / `commission_rules.aturan_baris`); tetap untuk
    pemanggil lama dan uji KA-2."""
    rows = await db.incentive_rates.find({"status": "active"}, {"_id": 0}).to_list(1000)
    # KA-2 — baris artikel/varian memotret kategori katalog; jangan menimpa tarif kategori (mesin lama hanya per kategori).
    rows = [r for r in rows if not (r.get("template_id") or r.get("product_id"))]
    by_cat: Dict[str, Dict[str, Any]] = {}
    ent = entity_id if entity_id and entity_id != "all" else None
    for r in rows:
        if r.get("entity_id") == "all":
            by_cat.setdefault(r["category"], r)
    for r in rows:  # entity spesifik menimpa 'all'
        if ent and r.get("entity_id") == ent:
            by_cat[r["category"]] = r
    return by_cat


_discount_factor = faktor_diskon   # KA-3 — rumus pindah ke commission_rules; nama lama tetap untuk pemanggil lama

_TINGKAT_TARIF = {"artikel": "Tarif artikel", "varian": "Tarif varian", "kategori": "Tarif kategori"}
_LINGKUP_TARIF = {"pt": "PT ini", "semua_pt": "Semua PT"}


def _asal_tarif(tarif: Dict[str, Any]) -> str:
    """KA-5 — teks asal tarif di rincian: "Tarif artikel (PT ini)", "Tarif kategori (Semua PT)", dst."""
    dasar = _TINGKAT_TARIF.get(tarif.get("asal_tingkat") or "", "Tarif")
    lingkup = _LINGKUP_TARIF.get(tarif.get("asal_lingkup") or "")
    return f"{dasar} ({lingkup})" if lingkup else dasar


def _persen_teks(n: float) -> str:
    return f"{round(float(n), 2):.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _label_rincian(alasan: str, selisih: set) -> str:
    """KA-5 — label alasan harga satu baris rincian gabungan. Baris pita yang menggabung selisih berbeda (pita sama)
    menulis rentangnya, mis. "2–2,5% di bawah harga acuan"."""
    if alasan == "pita" and len(selisih) > 1:
        return ALASAN_LABEL["pita"].format(selisih=f"{_persen_teks(min(selisih))}–{_persen_teks(max(selisih))}")
    return label_alasan(alasan, next(iter(selisih), None))


# ── BTP-5 (A1-6) — komisi pesanan batal sesudah bayar / tutup sisa ──────────────────────────────────────────────────
def _bertitipan(o: Dict[str, Any]) -> bool:
    """Uang muka pesanan sudah dipindah ke titipan pelanggan (`ar_receipt_service.pindah_uang_muka_ke_titipan`)."""
    return bool((o.get("advance_to_deposit") or {}).get("deposit_done"))


def _ikut_komisi(o: Dict[str, Any]) -> bool:
    """Pesanan hidup, atau pesanan mati (batal/kedaluwarsa) yang uang mukanya sudah dipindah ke titipan: bulan bayarnya
    tetap berkomisi (bulan yang sudah berakrual tidak berubah) dan bulan pemindahannya berkoreksi negatif. Pesanan mati
    tanpa penanda itu (batal sebelum ada uang, atau batal lama sebelum S3) tetap dikecualikan seperti dulu."""
    return o.get("status") not in DEAD_STATUSES or _bertitipan(o)


def _qty_dasar(line: Dict[str, Any]) -> float:
    return float(line.get("base_quantity", line.get("quantity", 0)) or 0)


def _dasar_komisi(o: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], float, bool]:
    """`(baris, nilai tagihan, ditutup_sisa)` dasar komisi pesanan.

    Pesanan ber-`closed_short` (tutup sisa, BTP-4) memakai dasar ASLI sebelum ditutup (`closed_short.commission_basis`)
    di SETIAP periode, supaya bulan yang sudah berakrual dihitung ulang persis sama: `grand_total` asli, dan per baris
    (urutan baris asli) jumlah dasar, jumlah jual, harga, diskon, dan nilai baris asli — baris yang masih ada di `items`
    dipulihkan dari `commission_basis.items[]` (bentuk lama tanpa rincian baris: diskalakan dari baris sekarang menurut
    jumlah dasar), baris yang terkirim 0 diambil utuh dari `closed_lines[]`. Pesanan lain: `items` + nilai tagihan."""
    dasar = (o.get("closed_short") or {}).get("commission_basis") or {}
    if not dasar:
        return o.get("items") or [], _order_grand_total(o), False
    kini = {it.get("product_id"): it for it in o.get("items") or []}
    keluar = {it.get("product_id"): it for it in o.get("closed_lines") or []}
    baris: List[Dict[str, Any]] = []
    for d in dasar.get("items") or []:
        pid = d.get("product_id")
        if pid in kini:
            it = kini[pid]
            asli = float(d.get("base_quantity") or 0)
            skala = asli / _qty_dasar(it) if _qty_dasar(it) > 0 else 0.0
            n = {**it, "base_quantity": asli,
                 "quantity": d.get("quantity", it.get("quantity_ordered_original",
                                                     float(it.get("quantity") or 0) * skala)),
                 "line_total": d.get("line_total", float(it.get("line_total") or 0) * skala)}
            for k in ("price", "discount_percent"):
                if k in d:
                    n[k] = d[k]
            baris.append(n)
        elif pid in keluar:
            baris.append(keluar[pid])
    return baris, float(dasar.get("grand_total") or 0) or _order_grand_total(o), True


def _uang_periode(o: Dict[str, Any], period: str) -> Tuple[float, float]:
    """`(Σ baris bayar biasa, Σ baris uang pindah ke titipan (≤ 0))` pesanan dalam periode."""
    biasa = pindah = 0.0
    for p in o.get("payments") or []:
        if not _in_period(p.get("created_at") or p.get("date"), period):
            continue
        if p.get("moved_to_deposit"):
            pindah += float(p.get("amount", 0) or 0)
        else:
            biasa += float(p.get("amount", 0) or 0)
    return biasa, pindah


def _baris_saldo(kode: str, label: str, komisi: float) -> Dict[str, Any]:
    """Baris rincian saldo potongan (bukan artikel): kuncinya sama dengan baris artikel supaya layar & gabungan tetap
    jalan; Σ `commission` rincian = `total_incentive`."""
    return {"category": "", "sku": "", "name": label, "template_id": "", "qty_base": 0.0, "unit": "",
            "commission": round(komisi, 2), "rate": 0.0, "rate_origin": "", "price_factor": None,
            "price_reason": kode, "price_reason_label": label, "achievement_factor": None, "capped": False}


async def _compute_commission_per_sku(
    sales_id: str, period: str, entity_id: Optional[str], settings: Dict[str, Any], *,
    sumber_aturan: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
    capaian_tetap: Optional[Tuple[float, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Engine per-SKU, margin-aware, on-collection (EPIC4) — aturan tiap baris dari potret pesanan (KA-5).

    Untuk tiap order, fraksi terbayar = Σpembayaran-dalam-periode / grand_total (≤1). Aturan baris = potret
    `items[].commission_rule` (aturan saat pesanan dibuat); baris tanpa potret memakai aturan PT saat ini lewat
    `commission_rules.aturan_baris` (hanya dibaca, tidak ditulis). `sumber_aturan` (simulasi) menggantikan keduanya.
    Komisi baris = `commission_rules.hitung_baris`: qty dasar terbayar × tarif × pengali harga × pengali capaian × bobot
    tim, dibatasi batas margin (margin_cap_pct% × margin baris terbayar) hanya bila HPP diketahui. Baris tanpa tarif
    (dipotret kosong atau ≤ 0) tidak berkomisi. `settings` tidak dibaca lagi (nilai PT ada di potret).
    KA-6 — pengali capaian = `commission_rules.pengali_capaian` (sekali per proses hitung, sama untuk semua baris),
    atau `capaian_tetap` `(faktor, info)` dari pemanggil (proyeksi triwulan/tahun, `_jumlah_bulanan`); hasil +
    `achievement_multiplier` `{factor, info}`.

    BTP-5 (keputusan pemilik A1-6, rancangan batal & tutup sisa §5.9) — komisi barang yang tidak jadi dikirim dipotong
    di BULAN PENUTUPAN, bulan yang sudah berakrual tidak berubah:
      * pesanan mati ikut dihitung hanya bila uang mukanya sudah dipindah ke titipan (`_ikut_komisi`), dan hanya di
        periode yang ada uangnya; pesanan tutup sisa memakai dasar ASLI di setiap periode (`_dasar_komisi`);
      * baris bayar `moved_to_deposit` di periode dibersihkan dengan bayar biasa periode itu; sisa negatif → baris
        koreksi `commission_rules.hitung_koreksi` (potret aturan yang sama, tidak dipotong nol) per pesanan, berkode
        `koreksi_batal` / `koreksi_tutup_sisa` (+ `order_id`, `order_number`, label pesanan & alasannya);
      * per sales per PT: `total_incentive = max(0, commission_raw + carry_in)`, `carry_out = min(0, …)`; `carry_in` =
        `carry_out` potret beku bulan sebelumnya (`commission_rules.saldo_potongan_awal`); "Semua PT" = jumlah per PT.
        Saldo tampil sebagai baris rincian `potongan_terbawa` / `potongan_dibawa` (Σ rincian = `total_incentive`).
    Pesanan tanpa `closed_short` dan tanpa `advance_to_deposit` dihitung persis seperti dulu.
    """
    kpi = await sales_kpi(sales_id, period, entity_id)
    cache: Dict[Any, Any] = {}   # indeks tarif, aturan PT, produk, artikel — sekali per proses hitung

    async def _aturan_sekarang(line: Dict[str, Any]) -> Dict[str, Any]:
        return await aturan_baris(line, entity_id, cache)

    ambil_aturan = sumber_aturan or _aturan_sekarang
    # KA-6 — pengali capaian target sales periode ini: dihitung SEKALI, dipakai semua baris.
    faktor_capaian, info_capaian = capaian_tetap or await pengali_capaian(entity_id, sales_id, period)
    wac_cache: Dict[str, float] = {}
    prod_cache: Dict[str, Dict[str, Any]] = {}
    ent_for_wac = entity_id if entity_id and entity_id != "all" else None

    async def _live_wac(pid: str) -> float:
        if pid not in wac_cache:
            w = await costing_service.wac_for_product(pid, entity_id=ent_for_wac)
            wac_cache[pid] = float(w.get("wac", 0) or 0)
        return wac_cache[pid]

    async def _hpp(pid: str) -> float:
        if pid not in prod_cache:
            prod_cache[pid] = await db.products.find_one({"id": pid}, {"_id": 0, "harga_pokok": 1}) or {}
        return float(prod_cache[pid].get("harga_pokok", 0) or 0)

    async def cost_for_line(line: Dict[str, Any], pid: str) -> tuple:
        """Cost-at-sale (P2-3). Prioritas: snapshot SO line -> live WAC -> harga_pokok -> unknown.

        Mengembalikan (cost_per_base_unit, cost_known). Bila tak diketahui, margin
        cap TIDAK diterapkan (hindari cap 'raksasa' diam-diam saat WAC=0/stok habis).
        """
        snap = float(line.get("unit_cost", 0) or 0)
        if snap > 0:
            return snap, True
        live = await _live_wac(pid)
        if live > 0:
            return live, True
        hpp = await _hpp(pid)
        if hpp > 0:
            return hpp, True
        return 0.0, False

    cust_filter: Dict[str, Any] = {"assigned_sales_id": sales_id}
    if entity_id and entity_id != "all":
        cust_filter["entity_id"] = entity_id
    customers = await db.customers.find(cust_filter, {"_id": 0, "id": 1}).to_list(2000)
    cust_id_set = {c["id"] for c in customers}
    # F-4c — sertakan order ber-`sales_team` (join/group sales) walau customer-nya tak di-assign ke sales ini.
    order_filter: Dict[str, Any] = {"$or": [{"customer_id": {"$in": list(cust_id_set)}}, {"sales_team.sales_id": sales_id}]}
    if entity_id and entity_id != "all":  # G3 D4-SALES-03 — basis komisi hanya SO entitas yang diminta
        order_filter["entity_id"] = entity_id
    orders = await db.sales_orders.find(order_filter, {"_id": 0}).to_list(8000)
    live = [o for o in orders if _ikut_komisi(o)]   # BTP-5 — + pesanan mati yang uang mukanya sudah jadi titipan

    breakdown: Dict[tuple, Dict[str, Any]] = {}
    total = 0.0
    projection_full = 0.0
    mentah_pt: Dict[str, float] = {}   # BTP-5 — komisi mentah per PT pesanan (saldo potongan per sales per PT)

    for o in live:
        # F-4c — bobot atribusi insentif untuk sales_id pada order ini.
        #   order ber-sales_team → split_pct anggota; selain itu → 1.0 (atribusi assigned_sales lama).
        team = o.get("sales_team") or []
        if team:
            member = next((m for m in team if m.get("sales_id") == sales_id), None)
            if not member:
                continue
            weight = float(member.get("split_pct", 0) or 0) / 100.0
        else:
            if o.get("customer_id") not in cust_id_set:
                continue
            weight = 1.0
        if weight <= 0:
            continue
        lines, gt, ditutup = _dasar_komisi(o)   # BTP-5 — tutup sisa: dasar ASLI di setiap periode
        if gt <= 0:
            continue
        biasa, pindah = _uang_periode(o, period)
        paid_in_period = biasa + pindah
        if pindah:
            # BTP-5 (A1-6) — uang yang pindah ke titipan di periode ini: dulu dihitung sebagai bayar negatif lalu
            # dipotong nol (koreksinya hilang). Kini dibersihkan dengan bayar biasa periode yang sama; sisa negatif =
            # koreksi.
            bersih = max(biasa, 0.0) + pindah
            frac_paid = min(bersih / gt, 1.0) if bersih > 0 else 0.0
            frac_koreksi = min(-bersih / gt, 1.0) if bersih < 0 else 0.0
        else:
            frac_paid, frac_koreksi = min(biasa / gt, 1.0), 0.0
        mati = o.get("status") in DEAD_STATUSES
        if mati and not frac_paid and not frac_koreksi:
            continue   # pesanan batal hanya muncul di bulan yang ada uangnya
        order_in_period = _in_period(o.get("created_at"), period)
        contributes = not mati and (order_in_period or paid_in_period > 0)
        kode_koreksi = KOREKSI_TUTUP_SISA if ditutup else KOREKSI_BATAL
        ent_o = o.get("entity_id") or ""
        for line in lines:
            base_qty = _qty_dasar(line)
            if base_qty <= 0:
                continue
            aturan = await ambil_aturan(line)
            tarif = (aturan or {}).get("tarif")
            if not tarif or float(tarif.get("per_unit_amount", 0) or 0) <= 0:
                continue   # tanpa tarif (dipotret kosong / ≤ 0) = tanpa komisi, seperti dulu
            cost, cost_known = await cost_for_line(line, line.get("product_id"))
            hitung = hitung_koreksi if frac_koreksi else hitung_baris
            h = hitung(aturan, line, fraksi=frac_koreksi or frac_paid, bobot=weight, biaya=cost,
                       biaya_diketahui=cost_known, pengali_capaian=faktor_capaian)
            total += h["komisi"]
            mentah_pt[ent_o] = mentah_pt.get(ent_o, 0.0) + h["komisi"]
            if contributes and not ditutup:
                projection_full += abs(h["komisi_penuh"])

            # Rincian per artikel (tanpa angka margin/HPP): gabung per artikel (atau SKU bila tanpa artikel) × tarif ×
            # pengali harga & alasannya × dibatasi × asal tarif. BTP-5 — baris koreksi terpisah per pesanan.
            artikel = aturan.get("artikel") or {}
            tpl = artikel.get("id") or ""
            asal = _asal_tarif(tarif)
            key = (("artikel", tpl) if tpl else ("sku", line.get("sku", "")), h["tarif"], h["pengali_harga"],
                   h["alasan_harga"], h["dibatasi"], asal)
            if frac_koreksi:
                key = ("koreksi", kode_koreksi, o.get("id")) + key
            b = breakdown.setdefault(key, {
                "category": line.get("category", ""), "sku": artikel.get("kode") or line.get("sku", ""),
                "name": artikel.get("nama") or line.get("product_name", ""), "template_id": tpl,
                "qty_base": 0.0, "unit": line.get("base_unit") or "", "commission": 0.0, "rate": h["tarif"], "rate_origin": asal,
                "price_factor": h["pengali_harga"], "price_reason": h["alasan_harga"], "price_reason_label": "",
                "achievement_factor": h["pengali_capaian"], "capped": h["dibatasi"], "_selisih": set(),
            })
            if frac_koreksi and "_label" not in b:
                kata = "kedaluwarsa" if o.get("status") == "expired" else "dibatalkan"
                b.update({"price_reason": kode_koreksi, "order_id": o.get("id") or "",
                          "order_number": o.get("number") or o.get("id") or "",
                          "_label": label_koreksi(kode_koreksi, o.get("number") or o.get("id") or "", kata)})
            b["qty_base"] += h["qty_dasar_terbayar"] * weight
            b["commission"] += h["komisi"]
            if h["selisih_pct"] is not None:
                b["_selisih"].add(h["selisih_pct"])
        if contributes and ditutup:   # proyeksi pesanan tutup sisa = barang yang terkirim (baris sekarang)
            for line in o.get("items") or []:
                if _qty_dasar(line) <= 0:
                    continue
                aturan = await ambil_aturan(line)
                tarif = (aturan or {}).get("tarif")
                if not tarif or float(tarif.get("per_unit_amount", 0) or 0) <= 0:
                    continue
                cost, cost_known = await cost_for_line(line, line.get("product_id"))
                penuh = hitung_baris(aturan, line, fraksi=1.0, bobot=weight, biaya=cost, biaya_diketahui=cost_known,
                                     pengali_capaian=faktor_capaian)
                projection_full += penuh["komisi_penuh"]

    target_collection = await _target_collection_for(sales_id, period, entity_id)
    achievement = (kpi["total_collected"] / target_collection * 100) if target_collection else 0
    rows = sorted(breakdown.values(), key=lambda x: x["commission"], reverse=True)
    for r in rows:
        selisih = r.pop("_selisih")
        r["price_reason_label"] = r.pop("_label") if "_label" in r else _label_rincian(r["price_reason"], selisih)
        r["qty_base"] = round(r["qty_base"], 2)
        r["commission"] = round(r["commission"], 2)
        r["rate"] = round(r["rate"], 2)

    # BTP-5 (A1-6) — saldo potongan per sales per PT: total bulan = max(0, mentah + saldo masuk); sisa negatif dibawa ke
    # bulan berikutnya (disimpan potret beku bulan ini, `carry_out`), tidak pernah menjadi komisi/gaji negatif.
    saldo_awal = await saldo_potongan_awal(sales_id, period, entity_id)
    bersih_pt = {pt: mentah_pt.get(pt, 0.0) + saldo_awal.get(pt, 0.0) for pt in set(mentah_pt) | set(saldo_awal)}
    if saldo_awal or any(v < 0 for v in bersih_pt.values()):
        dibayar = sum(max(v, 0.0) for v in bersih_pt.values())
        carry_out = round(sum(min(v, 0.0) for v in bersih_pt.values()), 2) or 0.0
    else:   # tanpa koreksi & saldo: angka persis seperti dulu
        dibayar, carry_out = total, 0.0
    carry_in = round(sum(saldo_awal.values()), 2) or 0.0
    if carry_in < 0:
        from services import incentive_periods as ip
        lalu = ip.previous_period("month", bulan_awal_periode(period))
        rows.append(_baris_saldo(POTONGAN_TERBAWA, LABEL_TERBAWA.format(bulan=ip.period_label("month", lalu)),
                                 carry_in))
    if carry_out < 0:
        rows.append(_baris_saldo(POTONGAN_DIBAWA, LABEL_DIBAWA, -carry_out))

    return {
        "sales_id": sales_id,
        "period": period,
        "strategy": "per_sku",
        "basis": "per_sku_collection",
        "base_amount": round(kpi["total_collected"], 2),
        "target_amount": round(target_collection, 2),
        "achievement_pct": round(achievement, 2),
        "applied_rate": None,
        "commission": round(dibayar, 2),
        "bonus_new_customer": 0.0,
        "total_incentive": round(dibayar, 2),
        "commission_raw": round(total, 2) or 0.0,
        "carry_in": carry_in,
        "carry_out": carry_out,
        "projection_full": round(projection_full, 2),
        "breakdown": rows,
        "achievement_multiplier": {"factor": faktor_capaian, "info": info_capaian},
        "kpi": kpi,
    }


async def commission_history(
    sales_id: str, period_type: str = "month", anchor: str = None, count: int = 6, entity_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Tren komisi `count` periode terakhir (untuk grafik multi-periode, S+5a)."""
    from services.analytics_time import now_wib
    now = now_wib()
    if not anchor:
        if period_type == "year":
            anchor = now.strftime("%Y")
        elif period_type == "quarter":
            anchor = f"{now.year}-Q{(now.month - 1) // 3 + 1}"
        else:
            anchor = now.strftime("%Y-%m")
    periods = _expand_periods(period_type, anchor, count)
    rows = []
    for p in reversed(periods):  # urut kronologis
        c = await compute_commission(sales_id, p, entity_id)
        rows.append({
            "period": p,
            "total_sales": c["kpi"]["total_sales"],
            "total_collected": c["kpi"]["total_collected"],
            "achievement_pct": c["achievement_pct"],
            "total_incentive": c["total_incentive"],
        })
    return rows


async def leaderboard(period: Optional[str] = None, entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """KPI semua salesperson, urut total_sales desc (Manager view).

    KM-T5 — daftar sales = `incentive_targets.sales_roster` PT itu (akun aktif berperan acuan / berkategori sales yang
    ditugaskan di PT — sama dengan Meja Insentif); "Semua PT" = gabungan daftar tiap PT. Dulu: semua akun berkategori sales
    seluruh grup (PR-T4), termasuk sales PT lain berangka 0."""
    from services.incentive_targets import sales_roster
    if entity_id and entity_id != "all":
        ents = [entity_id]
    else:
        ents = [e["id"] async for e in db.business_entities.find({}, {"_id": 0, "id": 1}) if e.get("id")]
    sales_users: Dict[str, str] = {}
    for e in ents:
        for u in await sales_roster(e):
            if u.get("active"):
                sales_users.setdefault(u["id"], u.get("name") or "")
    rows = []
    for uid, name in sales_users.items():
        kpi = await sales_kpi(uid, period, entity_id)
        kpi["sales_name"] = name
        rows.append(kpi)
    rows.sort(key=lambda r: r["total_sales"], reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows
