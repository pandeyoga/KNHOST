"""Stock Analytics service (Fase 5) — kelas laju jual + aging + nilai persediaan.

SSOT-safe & READ-ONLY: tidak mengubah stok. Sumber:
- inventory_balances (proyeksi on_hand, sudah di-rebuild dari rolls oleh roll_service)
- inventory_rolls    (umur/aging & nilai persediaan via base_unit_cost / WAC)
- sales_orders       (K-05: laju jual = MOVING AVERAGE qty terjual per hari dari SO hidup)
- inventory_movements(sinyal PENGIRIMAN 'outbound_ship' — dipakai reorder/ROP lewat `product_sales_velocity`)

K-05 (keputusan pemilik 26 Okt 2026) — klasifikasi HANYA dari moving average penjualan:
  * ukuran  = qty terjual per hari (satuan dasar) dalam jendela `velocity_window_days` (bawaan 90), dari SO hidup
              (tanpa batal/draf/kedaluwarsa/ditolak & tanpa pesanan sample); MA 30 hari ditampilkan untuk arah tren;
  * peringkat = persentil DI DALAM SATUAN YANG SAMA (yard, meter, kg tidak dibandingkan);
  * kelas   = Best seller (persen teratas) · Normal · Slow moving (persen terbawah di antara SKU yang terjual) ·
              Tidak bergerak (punya stok, tidak terjual dalam jendela) · Baru (umur SKU < `new_sku_age_days`, tidak
              diperingkat);
  * coverage (hari persediaan = stok ÷ MA harian) ditampilkan terpisah, TIDAK menentukan kelas.
Dasar metode: analisis ABC/Pareto & klasifikasi FSN (Fast/Slow/Non-moving) yang baku dalam manajemen persediaan,
dengan moving average sebagai ukuran laju permintaan.

Semua entity-scoped via resolve_list_scope. Ambang CONFIGURABLE (config_service.inventory.stock_analytics).
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from db import db
from entity_scope import EntityContext, resolve_list_scope
from services.config_service import get_effective_settings
from services.roll_service import PHYSICAL_STATUS_TO_BUCKET
from services.analytics_time import WIB
# Status SO yang TIDAK dihitung sebagai penjualan — sama dengan definisi "SO hidup" Tanya KN/beranda.
from services.customer_service import DEAD_STATUSES as SO_DEAD_STATUSES

PHYSICAL_STATUSES = set(PHYSICAL_STATUS_TO_BUCKET.keys())

# ── K-05 — kelas laju jual ────────────────────────────────────────────────────
CLASS_ORDER = ("best", "normal", "slow", "dead", "new")
CLASS_LABEL = {"best": "Best seller", "normal": "Normal", "slow": "Slow moving",
               "dead": "Tidak bergerak", "new": "Baru"}
TREND_WINDOW_DAYS = 30        # MA pendek untuk arah tren (naik/turun)
TREND_BAND = 0.10             # MA 30 hari dalam ±10% MA jendela → "stabil"
COVERAGE_CAP_DAYS = 365       # tampilan coverage dibatasi ("> 365 hari")


def percentile_ranks(values: Dict[str, float]) -> Dict[str, float]:
    """Persentil mid-rank 0–100: (jumlah nilai lebih kecil + ½ × jumlah nilai sama) ÷ n × 100.

    Adil terhadap nilai kembar (semua sama → semua 50) dan tidak memberi 0/100 mutlak pada kelompok kecil.
    >>> percentile_ranks({"a": 1, "b": 2, "c": 3})
    {'a': 16.67, 'b': 50.0, 'c': 83.33}"""
    from bisect import bisect_left, bisect_right
    n = len(values)
    if not n:
        return {}
    ordered = sorted(values.values())
    out: Dict[str, float] = {}
    for key, v in values.items():
        lower = bisect_left(ordered, v)
        equal = bisect_right(ordered, v) - lower
        out[key] = round((lower + 0.5 * equal) / n * 100, 2)
    return out


def class_from_percentile(pct: float, best_pct: float, slow_pct: float) -> str:
    """Best seller bila persentil > 100 − best_pct; Slow moving bila persentil < slow_pct; sisanya Normal."""
    if pct > 100 - best_pct:
        return "best"
    if pct < slow_pct:
        return "slow"
    return "normal"


def trend_of(ma_daily: float, ma_trend_daily: float) -> Optional[str]:
    """Arah tren: MA 30 hari dibanding MA jendela (±TREND_BAND = stabil). None bila MA jendela 0."""
    if ma_daily <= 0:
        return None
    ratio = ma_trend_daily / ma_daily
    if ratio > 1 + TREND_BAND:
        return "naik"
    if ratio < 1 - TREND_BAND:
        return "turun"
    return "stabil"


def classify_velocity(items: Iterable[Dict[str, Any]], *, window_days: int, best_pct: float,
                      slow_pct: float, new_age_days: int,
                      trend_days: int = TREND_WINDOW_DAYS) -> Dict[str, Dict[str, Any]]:
    """FUNGSI MURNI K-05 — kelas laju jual per SKU.

    `items`: {product_id, unit, sold_window, sold_trend, on_hand, age_days} — `sold_window` = qty terjual dalam
    jendela, `sold_trend` = qty terjual dalam `trend_days` terakhir, `age_days` = umur SKU (None = tak diketahui).
    Hasil per product_id: classification (None = tanpa stok & tanpa jual → tidak ditampilkan), ma_daily,
    ma_trend_daily, trend, percentile (hanya SKU yang diperingkat), rank_unit, rank_group_size, coverage_days."""
    window = max(int(window_days or 0), 1)
    tdays = max(min(int(trend_days or 0), window), 1)
    best_pct = max(0.0, min(float(best_pct), 100.0))
    slow_pct = max(0.0, min(float(slow_pct), 100.0 - best_pct))
    new_age = max(int(new_age_days or 0), 0)
    out: Dict[str, Dict[str, Any]] = {}
    groups: Dict[str, Dict[str, float]] = {}
    for it in items:
        pid = it["product_id"]
        sold = max(float(it.get("sold_window") or 0), 0.0)
        ma = sold / window
        ma_t = max(float(it.get("sold_trend") or 0), 0.0) / tdays
        on_hand = float(it.get("on_hand") or 0)
        age = it.get("age_days")
        unit = str(it.get("unit") or "").strip().lower()
        row = {"ma_daily": round(ma, 4), "ma_trend_daily": round(ma_t, 4), "trend": trend_of(ma, ma_t),
               "percentile": None, "rank_unit": unit, "rank_group_size": 0,
               "coverage_days": (round(on_hand / ma, 1) if ma > 0 else None)}
        if age is not None and age < new_age:
            row["classification"] = "new"          # tidak diperingkat — belum adil dinilai
        elif sold > 0:
            row["classification"] = None           # diisi setelah peringkat per satuan
            groups.setdefault(unit, {})[pid] = ma
        else:
            row["classification"] = "dead" if on_hand > 0 else None
        out[pid] = row
    for unit, mas in groups.items():
        ranks = percentile_ranks(mas)
        for pid, pct in ranks.items():
            out[pid].update({"percentile": pct, "rank_group_size": len(mas),
                             "classification": class_from_percentile(pct, best_pct, slow_pct)})
    return out


async def _so_sales(ctx: Optional[EntityContext], entity_id: Optional[str], now: datetime, window: int,
                    trend_days: int) -> Dict[str, Dict[str, Any]]:
    """K-05 — qty terjual per produk dari SO HIDUP (bukan sample): jendela, MA pendek, jual pertama & terakhir.

    Qty = `base_quantity` (satuan dasar produk) dengan cadangan `quantity`. Baris `is_sample` diabaikan."""
    q = resolve_list_scope("sales_orders", {"status": {"$nin": sorted(SO_DEAD_STATUSES)},
                                            "order_type": {"$ne": "sample"}}, ctx, entity_id)
    w_start = now - timedelta(days=window)
    t_start = now - timedelta(days=max(min(trend_days, window), 1))
    out: Dict[str, Dict[str, Any]] = {}
    async for so in db.sales_orders.find(q, {"_id": 0, "created_at": 1, "items.product_id": 1,
                                             "items.base_quantity": 1, "items.quantity": 1,
                                             "items.is_sample": 1, "items.base_unit": 1}):
        dt = _parse_ts(so.get("created_at"))
        if not dt:
            continue
        for it in so.get("items") or []:
            pid = it.get("product_id") if isinstance(it, dict) else None
            if not pid or it.get("is_sample"):
                continue
            try:
                qty = abs(float(it.get("base_quantity") or it.get("quantity") or 0))
            except (TypeError, ValueError):
                qty = 0.0
            d = out.setdefault(pid, {"sold": 0.0, "trend": 0.0, "first": dt, "last": dt,
                                     "unit": it.get("base_unit") or ""})
            d["first"] = min(d["first"], dt)
            d["last"] = max(d["last"], dt)
            if dt >= w_start:
                d["sold"] += qty
            if dt >= t_start:
                d["trend"] += qty
    return out


async def _first_roll_dates(ctx: Optional[EntityContext], entity_id: Optional[str]) -> Dict[str, datetime]:
    """Tanggal roll PERTAMA tercatat per produk (seluruh gudang dalam cakupan) — bukti umur SKU."""
    q = resolve_list_scope("inventory_rolls", {}, ctx, entity_id)
    out: Dict[str, datetime] = {}
    rows = await db.inventory_rolls.aggregate([
        {"$match": q}, {"$group": {"_id": "$product_id", "first": {"$min": "$created_at"}}}]).to_list(None)
    for r in rows:
        dt = _parse_ts(r.get("first"))
        if r.get("_id") and dt:
            out[r["_id"]] = dt
    return out

# Sinyal PENJUALAN (arus keluar ke pelanggan) untuk recency & velocity.
# Mencakup jalur live (roll_service.ship_order_rolls → 'outbound_ship') maupun
# data historis/seed ('outbound_dispatch'). Retur ('return_out') = balik masuk → diabaikan.
SALE_MOVEMENT_TYPES = {"outbound_ship", "outbound_dispatch"}

AGING_BUCKETS = [
    ("0-30", 0, 30), ("31-60", 31, 60), ("61-90", 61, 90),
    ("91-180", 91, 180), (">180", 181, 10 ** 9),
]


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    """G3 D4-STOCK-04 — selalu timezone-aware: date-only = tengah malam WIB, naif = UTC."""
    if not ts:
        return None
    s = str(ts).strip()
    try:
        if len(s) == 10:
            return datetime.fromisoformat(s).replace(tzinfo=WIB)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _age_days(now: datetime, dt: datetime) -> int:
    """Umur dalam hari kalender WIB."""
    return (now.astimezone(WIB).date() - dt.astimezone(WIB).date()).days


def _age_bucket(days: int) -> str:
    for name, lo, hi in AGING_BUCKETS:
        if lo <= days <= hi:
            return name
    return ">180"


async def product_sales_velocity(
    ctx: EntityContext, entity_id: Optional[str] = None, window_days: int = 90,
) -> Dict[str, Dict[str, Any]]:
    """Kecepatan jual per PRODUK (lintas gudang) dari movement penjualan dalam jendela.
    Sumber tunggal definisi 'penjualan' (SALE_MOVEMENT_TYPES) — dipakai analytics & reorder/ROP.
    Return: {product_id: {sold, avg_daily, last_sale_days}}."""
    now = datetime.now(timezone.utc)
    window_start = now.timestamp() - window_days * 86400
    # T-03 Lapis 1 (audit 2026-09) — penyaring jenis mutasi dipindah ke QUERY (ditopang
    # indeks movement_type+timestamp), bukan memuat seluruh koleksi lalu menyaring di
    # Python. Penyaring TANGGAL sengaja TETAP di Python: `last_sale_days` dihitung dari
    # seluruh riwayat, memindahkannya ke query akan MENGUBAH hasil.
    mv_q = resolve_list_scope("inventory_movements", {}, ctx, entity_id)
    mv_q["movement_type"] = {"$in": sorted(SALE_MOVEMENT_TYPES)}
    mv = await db.inventory_movements.find(
        mv_q, {"_id": 0, "product_id": 1, "timestamp": 1, "quantity": 1, "movement_type": 1}
    ).to_list(20000)
    out: Dict[str, Dict[str, Any]] = {}
    for m in mv:
        if m.get("movement_type") not in SALE_MOVEMENT_TYPES:
            continue
        pid = m.get("product_id")
        dt = _parse_ts(m.get("timestamp"))
        d = out.setdefault(pid, {"sold": 0.0, "avg_daily": 0.0, "last_sale_days": None})
        if dt:
            days = _age_days(now, dt)
            if d["last_sale_days"] is None or days < d["last_sale_days"]:
                d["last_sale_days"] = days
            if dt.timestamp() >= window_start:
                d["sold"] += abs(float(m.get("quantity", 0) or 0))
    for d in out.values():
        d["sold"] = round(d["sold"], 2)
        d["avg_daily"] = round(d["sold"] / window_days, 4) if window_days > 0 else 0.0
    return out



async def compute_stock_analytics(
    ctx: EntityContext,
    entity_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    settings = await get_effective_settings(entity_id if entity_id and entity_id != "all" else None)
    sa = (settings.get("inventory", {}) or {}).get("stock_analytics", {}) or {}

    def _num(key: str, default: float) -> float:
        v = sa.get(key)
        try:
            return float(default if v is None else v)
        except (TypeError, ValueError):
            return float(default)
    # K-05 — semua ambang dari Pusat Pengaturan (inventory.stock_analytics.*).
    window = max(int(_num("velocity_window_days", 90)), 1)
    best_pct = _num("best_seller_pct", 20)
    slow_pct = _num("slow_moving_pct", 20)
    new_age = max(int(_num("new_sku_age_days", 90)), 0)
    trend_days = min(TREND_WINDOW_DAYS, window)

    # ── Master maps ──────────────────────────────────────────────────────────
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(200)}
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(2000)}
    # G3 D4-STOCK-02 — filter kategori diterapkan SEBELUM roll/balance (semua KPI & aging).
    allowed = {pid for pid, p in products.items() if p.get("category") == category} if category else None

    # ── Balances (on_hand > 0), entity-scoped ─────────────────────────────────
    bal_query: Dict[str, Any] = {"on_hand_qty": {"$gt": 0}}
    if warehouse_id:
        bal_query["warehouse_id"] = warehouse_id
    balances = await db.inventory_balances.find(
        resolve_list_scope("inventory_balances", bal_query, ctx, entity_id), {"_id": 0}
    ).to_list(5000)

    # ── K-05 — penjualan dari SO hidup (cakupan badan usaha; saringan gudang/kategori TIDAK mengubah kelas) ──
    sales = await _so_sales(ctx, entity_id, now, window, trend_days)
    first_rolls = await _first_roll_dates(ctx, entity_id)

    # ── Rolls (aging & nilai), entity-scoped ──────────────────────────────────
    roll_query: Dict[str, Any] = {"length_remaining": {"$gt": 0}}
    if warehouse_id:
        roll_query["warehouse_id"] = warehouse_id
    rolls = await db.inventory_rolls.find(
        resolve_list_scope("inventory_rolls", roll_query, ctx, entity_id), {"_id": 0}
    ).to_list(100000)
    # per (product, warehouse, pemilik): nilai, umur roll tertua ; aging global per bucket
    # G3 D4-STOCK-01 — seg key memuat PEMILIK: balance per pemilik tidak boleh menambahkan agregat gabungan berkali-kali.
    # G3 D4-STOCK-03 — nilai = BIAYA PENUH roll (`unit_cost` sudah memuat landed), dipecah dasar + landed.
    seg_value: Dict[tuple, float] = {}
    seg_base: Dict[tuple, float] = {}
    seg_oldest_age: Dict[tuple, int] = {}
    aging: Dict[str, Dict[str, float]] = {name: {"qty": 0.0, "value": 0.0} for name, _, _ in AGING_BUCKETS}
    for r in rolls:
        if r.get("status") not in PHYSICAL_STATUSES:
            continue
        if allowed is not None and r.get("product_id") not in allowed:
            continue
        key = (r.get("product_id"), r.get("warehouse_id"), r.get("owner_entity_id"))
        length = float(r.get("length_remaining", 0) or 0)
        base = float(r.get("base_unit_cost", 0) or 0)
        full = float(r.get("unit_cost", 0) or 0) or base
        base = min(base, full) if base > 0 else full
        value = length * full
        seg_value[key] = seg_value.get(key, 0.0) + value
        seg_base[key] = seg_base.get(key, 0.0) + length * base
        dt = _parse_ts(r.get("created_at")) or _parse_ts((r.get("acquired") or {}).get("date"))
        age = _age_days(now, dt) if dt else 9999
        if key not in seg_oldest_age or age > seg_oldest_age[key]:
            seg_oldest_age[key] = age
        b = _age_bucket(age)
        aging[b]["qty"] += length
        aging[b]["value"] += value

    def _new_row(pid: str) -> Dict[str, Any]:
        prod = products.get(pid, {})
        return {
            "product_id": pid, "sku": prod.get("sku", ""), "product_name": prod.get("name", ""),
            "category": prod.get("category", ""),
            "unit": prod.get("base_unit") or (sales.get(pid) or {}).get("unit") or "",
            "on_hand_qty": 0.0, "value": 0.0, "value_base": 0.0, "warehouses": set(), "_oldest_age": 0,
        }

    # ── Agregasi per PRODUK (lintas gudang di scope) ──────────────────────────
    prod_rows: Dict[str, Dict[str, Any]] = {}
    for b in balances:
        pid = b.get("product_id")
        if allowed is not None and pid not in allowed:
            continue
        wh = b.get("warehouse_id")
        key = (pid, wh, b.get("owner_entity_id"))
        row = prod_rows.get(pid) or prod_rows.setdefault(pid, _new_row(pid))
        row["on_hand_qty"] += float(b.get("on_hand_qty", 0) or 0)
        row["value"] += seg_value.get(key, 0.0)
        row["value_base"] += seg_base.get(key, 0.0)
        if wh in warehouses:
            row["warehouses"].add(warehouses[wh]["name"])
        row["_oldest_age"] = max(row["_oldest_age"], seg_oldest_age.get(key, 0))
    # K-05 — SKU yang TERJUAL dalam jendela tetapi stoknya habis tetap tampil (best seller kehabisan stok adalah
    # informasi penting). Hanya tanpa saringan gudang: penjualan tidak tercatat per gudang.
    if not warehouse_id:
        for pid, s in sales.items():
            if s["sold"] > 0 and pid not in prod_rows and (allowed is None or pid in allowed):
                prod_rows[pid] = _new_row(pid)

    # ── K-05 — kelas laju jual: peringkat atas SEMUA SKU terjual di cakupan badan usaha ──────────────────────
    def _age_of(pid: str) -> Optional[int]:
        """Umur SKU = sejak bukti PERTAMA: produk dibuat, roll pertama tercatat, atau penjualan pertama."""
        dates = [d for d in (_parse_ts(products.get(pid, {}).get("created_at")),
                             (sales.get(pid) or {}).get("first"), first_rolls.get(pid)) if d]
        return _age_days(now, min(dates)) if dates else None

    ages: Dict[str, Optional[int]] = {}
    cls_items = []
    for pid in set(prod_rows) | {p for p, s in sales.items() if s["sold"] > 0}:
        s = sales.get(pid) or {}
        ages[pid] = _age_of(pid)
        cls_items.append({
            "product_id": pid,
            "unit": products.get(pid, {}).get("base_unit") or s.get("unit") or "",
            "sold_window": s.get("sold", 0.0), "sold_trend": s.get("trend", 0.0),
            "on_hand": (prod_rows[pid]["on_hand_qty"] if pid in prod_rows else 0.0),
            "age_days": ages[pid]})
    cls_map = classify_velocity(cls_items, window_days=window, best_pct=best_pct, slow_pct=slow_pct,
                                new_age_days=new_age, trend_days=trend_days)
    rank_groups: Dict[str, int] = {}
    for c in cls_map.values():
        if c.get("percentile") is not None:
            rank_groups[c["rank_unit"]] = c["rank_group_size"]

    rows: List[Dict[str, Any]] = []
    by_class = {c: {"count": 0, "qty": 0.0, "value": 0.0} for c in CLASS_ORDER}
    total_value = 0.0
    total_base = 0.0
    never_sold_count = 0
    for pid, row in prod_rows.items():
        c = cls_map.get(pid) or {}
        cls = c.get("classification")
        if not cls:
            continue
        s = sales.get(pid) or {}
        last_sale_dt = s.get("last")
        never_sold = not s
        row["warehouses"] = sorted(row["warehouses"])
        row["value"] = round(row["value"], 2)
        row["value_base"] = round(row["value_base"], 2)
        row["value_landed"] = round(row["value"] - row["value_base"], 2)
        total_base += row["value_base"]
        row["on_hand_qty"] = round(row["on_hand_qty"], 2)
        coverage = c.get("coverage_days")
        row.update({
            "classification": cls,
            "classification_label": CLASS_LABEL[cls],
            "never_sold": never_sold,
            "last_sale_date": last_sale_dt.isoformat() if last_sale_dt else None,
            "days_since_sale": _age_days(now, last_sale_dt) if last_sale_dt else None,
            "oldest_age_days": row.pop("_oldest_age"),
            "sku_age_days": ages.get(pid),
            "sold_qty_window": round(float(s.get("sold", 0.0)), 2),
            "sold_qty_trend": round(float(s.get("trend", 0.0)), 2),
            "ma_daily": c.get("ma_daily", 0.0),
            "ma_trend_daily": c.get("ma_trend_daily", 0.0),
            "trend": c.get("trend"),
            "percentile": c.get("percentile"),
            "rank_unit": c.get("rank_unit", ""),
            "rank_group_size": c.get("rank_group_size", 0),
            "avg_daily_sold": round(c.get("ma_daily", 0.0), 3),   # alias lama (= ma_daily)
            "days_of_supply": coverage,
            "coverage_capped": bool(coverage is not None and coverage > COVERAGE_CAP_DAYS),
            "stock_out": row["on_hand_qty"] <= 0,
        })
        rows.append(row)
        by_class[cls]["count"] += 1
        by_class[cls]["qty"] += row["on_hand_qty"]
        by_class[cls]["value"] += row["value"]
        total_value += row["value"]
        if never_sold:
            never_sold_count += 1

    for c in by_class:
        by_class[c]["qty"] = round(by_class[c]["qty"], 2)
        by_class[c]["value"] = round(by_class[c]["value"], 2)
    for b in aging.values():
        b["qty"] = round(b["qty"], 2)
        b["value"] = round(b["value"], 2)

    # urutkan: yang perlu perhatian dulu (tidak bergerak, slow moving), lalu nilai terbesar
    order = {"dead": 0, "slow": 1, "new": 2, "normal": 3, "best": 4}
    rows.sort(key=lambda r: (order.get(r["classification"], 9), -r["value"]))

    return {
        "generated_at": now.isoformat(),
        "thresholds": {"velocity_window_days": window, "trend_window_days": trend_days,
                       "best_seller_pct": best_pct, "slow_moving_pct": slow_pct, "new_sku_age_days": new_age,
                       "coverage_cap_days": COVERAGE_CAP_DAYS, "trend_band_pct": round(TREND_BAND * 100, 1)},
        "filters": {"entity_id": entity_id or "all", "warehouse_id": warehouse_id, "category": category},
        "method": {
            "basis": "moving_average_so",
            "class_labels": CLASS_LABEL,
            "source": "Pesanan penjualan hidup (tanpa batal/draf/kedaluwarsa/ditolak & tanpa pesanan sample)",
            "rank_scope": "Persentil di antara SKU terjual pada satuan yang sama, seluruh badan usaha "
                          "(saringan gudang/kategori hanya menyaring tampilan)",
            "rank_groups": [{"unit": u, "ranked": n} for u, n in sorted(rank_groups.items())],
        },
        "summary": {
            "sku_count": len(rows),
            "total_on_hand_value": round(total_value, 2),
            "total_base_value": round(total_base, 2),
            "total_landed_value": round(total_value - total_base, 2),
            "cost_basis": "full_landed",
            "cost_basis_label": "Biaya penuh roll (dasar + landed cost)",
            "aging_filtered_by_category": bool(category),
            "by_class": by_class,
            "aging_buckets": [{"bucket": name, **aging[name]} for name, _, _ in AGING_BUCKETS],
            "dead_value": by_class["dead"]["value"],
            "dead_skus": by_class["dead"]["count"],
            "never_sold_skus": never_sold_count,
            "stock_out_skus": sum(1 for r in rows if r["stock_out"]),
        },
        "rows": rows,
    }
