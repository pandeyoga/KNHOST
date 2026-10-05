"""Tanya KN F1.1 — tabel fakta `fact_sales_lines`.

Satu dokumen per baris pesanan per anggota sales (bila `sales_team` dibagi). Diskon pesanan,
PPN, atribusi sales, tanggal WIB, dan HPP diselesaikan SEKALI di sini sehingga kueri analitik
cepat dan konsisten. Nilai uang/qty sudah dikali `split`, jadi Σ baris = nilai pesanan.

Rumus (Katalog cat-v1 §B):
- net_alloc   = line_total × (grand_total − ppn_amount) / Σ line_total   (diskon pesanan proporsional)
- gross_alloc = total_amount × line_gross / Σ line_gross   (line_gross = line_total + diskon baris)
- discount    = gross_alloc − net_alloc   → gross − discount = net
- ppn_alloc   = ppn_amount × line_total / Σ line_total
- cost        = unit_cost × base_quantity  (HPP snapshot saat pesanan)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from db import db
from core_utils import now_iso
from services.analytics_config import ai_policy
from services.analytics_time import now_wib, to_wib_date, wib_midnight_utc
from services.customer_service import DEAD_STATUSES

logger = logging.getLogger(__name__)

STATE_ID = "fact_sales_lines"
BATCH = 500
_SO_FIELDS = {"_id": 0, "payments": 0, "status_history": 0, "allocations": 0, "refs": 0, "verification": 0}


def _f(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def attribute_sales(so: Dict[str, Any], customer: Dict[str, Any], users: Dict[str, Dict[str, Any]],
                    mode: str = "team_split") -> List[Tuple[str, float]]:
    """Daftar (sales_id, split). Katalog §C: sales_team → sales_id → pembuat (bila sales) →
    sales penanggung jawab pelanggan → "" (Tanpa sales)."""
    owner = customer.get("assigned_sales_id") or ""
    if mode == "customer_owner":
        return [(owner, 1.0)]
    team = [m for m in (so.get("sales_team") or []) if m.get("sales_id")]
    if team:
        pcts = [_f(m.get("split_pct")) for m in team]
        total = sum(pcts)
        if total <= 0:
            return [(m["sales_id"], 1.0 / len(team)) for m in team]
        return [(m["sales_id"], p / total) for m, p in zip(team, pcts)]
    if so.get("sales_id"):
        return [(so["sales_id"], 1.0)]
    creator = so.get("created_by") or ""
    if creator and (users.get(creator) or {}).get("role") == "sales":
        return [(creator, 1.0)]
    return [(owner, 1.0)]


def build_rows(so: Dict[str, Any], customer: Dict[str, Any], products: Dict[str, Dict[str, Any]],
               users: Dict[str, Dict[str, Any]], mode: str = "team_split") -> List[Dict[str, Any]]:
    items = [it for it in (so.get("items") or []) if isinstance(it, dict)]
    if not items:
        return []
    grand = _f(so.get("grand_total") if so.get("grand_total") is not None else so.get("total_amount"))
    ppn = _f(so.get("ppn_amount"))
    net_order = grand - ppn
    line_totals = [_f(it.get("line_total", it.get("subtotal"))) for it in items]
    line_gross = [lt + _f(it.get("discount_amount")) for lt, it in zip(line_totals, items)]
    s_lt, s_gross = sum(line_totals), sum(line_gross)
    total_amount = _f(so.get("total_amount")) or s_gross
    if so.get("ppn_mode") == "included" and ppn > 0:
        # KN-E35 — harga termasuk PPN: gross & diskon dinyatakan tanpa PPN (dulu "diskon" = PPN).
        net_sub = _f(so.get("net_subtotal")) or (total_amount - _f(so.get("discount_total")))
        if net_sub > 0:
            total_amount = total_amount * (net_order / net_sub)
    status = so.get("status") or ""
    built = now_iso()
    base = {
        "entity_id": so.get("entity_id") or "", "so_id": so["id"], "so_number": so.get("number") or "",
        "order_type": so.get("order_type") or "regular", "is_sample": (so.get("order_type") == "sample"),
        "status": status, "is_live": status not in DEAD_STATUSES,
        "date_wib": to_wib_date(so.get("created_at")) or "", "created_at_utc": so.get("created_at") or "",
        "customer_id": so.get("customer_id") or "",
        "customer_name": so.get("customer_name") or customer.get("name") or "",
        "customer_city": so.get("shipping_city") or so.get("customer_city") or customer.get("city") or "",
        "customer_segment": customer.get("segment") or "",
        "payment_status": so.get("payment_status") or "", "updated_at_src": so.get("updated_at") or "",
        "built_at": built,
    }
    rows: List[Dict[str, Any]] = []
    for sales_id, split in attribute_sales(so, customer, users, mode):
        for idx, it in enumerate(items):
            lt = line_totals[idx]
            share = (lt / s_lt) if s_lt else (1.0 / len(items))
            gross_share = (line_gross[idx] / s_gross) if s_gross else share
            net_alloc = net_order * share * split
            gross_alloc = total_amount * gross_share * split
            prod = products.get(it.get("product_id") or "") or {}
            qty_base = _f(it.get("base_quantity")) or _f(it.get("quantity"))
            rows.append({
                **base,
                "_id": f"{so['id']}:{idx}:{sales_id}",
                "line_idx": idx, "sales_id": sales_id,
                "sales_name": (users.get(sales_id) or {}).get("name", "") if sales_id else "",
                "split": round(split, 6),
                "product_id": it.get("product_id") or "", "sku": it.get("sku") or prod.get("sku") or "",
                "product_name": it.get("product_name") or prod.get("name") or "",
                "category": it.get("category") or prod.get("category") or "",
                "line_code": (it.get("line_code") or prod.get("line_code") or "").lower(),
                "fabric_type": prod.get("fabric_type") or "",
                "base_unit": it.get("base_unit") or prod.get("base_unit") or it.get("unit") or "",
                "qty_base": round(qty_base * split, 4),
                "rolls": round(_f(it.get("qty_rolls")) * split, 4),
                "gross": round(gross_alloc, 2),
                "net_alloc": round(net_alloc, 2),
                "discount": round(gross_alloc - net_alloc, 2),
                "ppn_alloc": round(ppn * share * split, 2),
                "cost": round(_f(it.get("unit_cost")) * qty_base * split, 2),
            })
    return rows


async def _maps(orders: List[Dict[str, Any]]):
    cids = list({o.get("customer_id") for o in orders if o.get("customer_id")})
    pids = list({it.get("product_id") for o in orders for it in (o.get("items") or []) if it.get("product_id")})
    customers = {c["id"]: c for c in await db.customers.find(
        {"id": {"$in": cids}}, {"_id": 0, "id": 1, "name": 1, "city": 1, "segment": 1,
                                "assigned_sales_id": 1}).to_list(None)}
    products = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": pids}}, {"_id": 0, "id": 1, "name": 1, "sku": 1, "category": 1, "line_code": 1,
                                "fabric_type": 1, "base_unit": 1}).to_list(None)}
    users = {u["id"]: u for u in await db.users.find({}, {"_id": 0, "id": 1, "name": 1, "role": 1}).to_list(None)}
    return customers, products, users


async def _write(orders: List[Dict[str, Any]], mode: str) -> int:
    if not orders:
        return 0
    customers, products, users = await _maps(orders)
    rows: List[Dict[str, Any]] = []
    for o in orders:
        rows.extend(build_rows(o, customers.get(o.get("customer_id") or "") or {}, products, users, mode))
    await db.fact_sales_lines.delete_many({"so_id": {"$in": [o["id"] for o in orders]}})
    if rows:
        await db.fact_sales_lines.insert_many(rows, ordered=False)
    return len(rows)


async def _process(cursor_query: Dict[str, Any]) -> Tuple[int, int, str]:
    mode = (await ai_policy())["sales_attribution"]
    n_so = n_rows = 0
    max_upd = ""
    batch: List[Dict[str, Any]] = []
    async for o in db.sales_orders.find(cursor_query, _SO_FIELDS):
        batch.append(o)
        max_upd = max(max_upd, str(o.get("updated_at") or o.get("created_at") or ""))
        if len(batch) >= BATCH:
            n_rows += await _write(batch, mode)
            n_so += len(batch)
            batch = []
    n_rows += await _write(batch, mode)
    n_so += len(batch)
    return n_so, n_rows, max_upd


async def rebuild_facts(date_from: Optional[str] = None) -> Dict[str, Any]:
    """Bangun ulang fakta untuk pesanan bertanggal (WIB) ≥ `date_from` (YYYY-MM-DD); kosong = semua."""
    q: Dict[str, Any] = {}
    if date_from:
        q["created_at"] = {"$gte": wib_midnight_utc(datetime.fromisoformat(date_from).date())}
    else:
        await db.fact_sales_lines.delete_many({})
    n_so, n_rows, max_upd = await _process(q)
    st = await db.ai_fact_state.find_one({"id": STATE_ID}, {"_id": 0}) or {}
    wm = max(st.get("watermark") or "", max_upd)
    await db.ai_fact_state.update_one({"id": STATE_ID}, {"$set": {
        "id": STATE_ID, "watermark": wm, "last_sync_at": now_iso(), "last_rebuild_at": now_iso(),
        "last_rebuild_from": date_from or ""}}, upsert=True)
    return {"orders": n_so, "rows": n_rows, "from": date_from or "", "watermark": wm}


async def sync_facts() -> Dict[str, Any]:
    """Inkremental: pesanan dengan `updated_at` (atau `created_at`) > watermark."""
    st = await db.ai_fact_state.find_one({"id": STATE_ID}, {"_id": 0})
    if not st or not st.get("watermark"):
        return await rebuild_facts()
    wm = st["watermark"]
    # KN-E41 — jendela tumpang 10 menit: SO yang ter-commit terlambat (updated_at < watermark) tetap terbaca.
    # Tulis ulang bersifat idempoten (hapus + sisip per so_id), jadi tumpang tindih aman.
    try:
        lo = (datetime.fromisoformat(wm) - timedelta(minutes=10)).isoformat()
    except ValueError:
        lo = wm
    n_so, n_rows, max_upd = await _process({"$or": [{"updated_at": {"$gt": lo}},
                                                    {"updated_at": {"$exists": False}, "created_at": {"$gt": lo}}]})
    await db.ai_fact_state.update_one({"id": STATE_ID}, {"$set": {
        "watermark": max(wm, max_upd), "last_sync_at": now_iso()}})
    return {"orders": n_so, "rows": n_rows, "watermark": max(wm, max_upd)}


async def ensure_fresh(max_age_seconds: int = 60) -> Optional[str]:
    """Sinkron inkremental bila terakhir > `max_age_seconds`. Mengembalikan jam WIB data terakhir."""
    st = await db.ai_fact_state.find_one({"id": STATE_ID}, {"_id": 0}) or {}
    last = st.get("last_sync_at") or ""
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() if last else 1e9
    except ValueError:
        age = 1e9
    if age > max_age_seconds:
        if not st.get("watermark"):
            # KN-E41 — bangun ulang penuh (hapus semua fakta) TIDAK dijalankan di dalam request pengguna.
            logger.warning("[analytics_facts] fakta belum pernah dibangun — tunggu job sinkron terjadwal.")
            return last and datetime.fromisoformat(last).astimezone(now_wib().tzinfo).strftime("%H:%M")
        now = datetime.now(timezone.utc)
        got = await db.ai_fact_state.find_one_and_update(   # KN-E41 — satu penyinkron pada satu waktu
            {"id": STATE_ID, "$or": [{"sync_lock_until": {"$exists": False}}, {"sync_lock_until": {"$lt": now.isoformat()}}]},
            {"$set": {"sync_lock_until": (now + timedelta(minutes=2)).isoformat()}}, projection={"_id": 0, "id": 1})
        if not got:
            return last and datetime.fromisoformat(last).astimezone(now_wib().tzinfo).strftime("%H:%M")
        try:
            await sync_facts()
        except Exception as exc:  # noqa: BLE001 — kueri tetap jalan dengan fakta yang ada
            logger.warning("[analytics_facts] sync gagal: %s", exc)
            return last and datetime.fromisoformat(last).astimezone(now_wib().tzinfo).strftime("%H:%M")
        finally:
            await db.ai_fact_state.update_one({"id": STATE_ID}, {"$unset": {"sync_lock_until": ""}})
    return now_wib().strftime("%H:%M")


async def job_fact_sync() -> Dict[str, Any]:
    res = await sync_facts()
    return {"scanned": res["orders"], "created": 0,
            "detail": f"{res['orders']} pesanan → {res['rows']} baris fakta diperbarui"}


async def job_fact_nightly() -> Dict[str, Any]:
    since = (now_wib().date() - timedelta(days=90)).isoformat()
    res = await rebuild_facts(since)
    return {"scanned": res["orders"], "created": 0,
            "detail": f"Bangun ulang 90 hari ({since}): {res['orders']} pesanan → {res['rows']} baris"}
