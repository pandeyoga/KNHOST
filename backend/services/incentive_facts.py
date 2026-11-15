"""KM-T1 (KM-01, KM-02, KM-03; keputusan K-19, K-20, K-21, K-23) — fakta insentif: omzet terkirim dan pencairan.

Dua koleksi TURUNAN (`02_STANDAR.md` §5 D2 — bisa dibangun ulang dari dokumen sumber, dijaga INV-KM-1 … INV-KM-3). Modul ini
hanya MEMBACA dokumen sumber (pesanan, surat jalan, nota kredit, retur, kwitansi; jurnal pendapatan per pesanan lama hanya
untuk memilih jalur `pesanan_lama`) dan menulis dua koleksi fakta beserta tanda airnya.

`fact_shipment_sales` — satu dokumen per (sumber × baris pesanan × sales):
    kirim         surat jalan: nilai bersih pesanan × `gl_service.shipment_value_share`, surat jalan diproses menurut
                  `created_at`; bila pesanan `shipped`/`done` surat jalan terakhir mengambil SISA (aturan yang sama dengan
                  `gl_service.post_shipment_revenue`), tanggal = `created_at` surat jalan (= tanggal jurnalnya)
    retur         nota kredit retur (negatif): `net_amount` nota, tanggal = `approved_at` retur (= tanggal jurnal
                  `post_sales_return`) atau `created_at` nota untuk penyelesaian per roll
    koreksi       nota kredit amandemen / batal item pesanan khusus yang berjurnal (negatif), tanggal `created_at` nota
    pesanan_lama  pesanan berpendapatan tanpa surat jalan (atau berjurnal per pesanan lama), per baris pesanan
  Nilai bersih & alokasi per baris = `profitability_service._order_net_alloc`; pembagian ke sales = `analytics_facts._alloc`
  (Σ baris = nilai sumber sampai sen). Pemilik angka = `sales_attribution` pesanan (potret saat dibuat, K-21); pesanan
  tanpa potret memakai `analytics_facts.attribute_sales` mode tim (tim → sales pesanan → pembuat → pemilik pelanggan).

`fact_collections` — satu dokumen per (baris `payments[]` × sales). `source_kind` = `ar_allocation_service.payment_kind`
  (PK-19); `is_reversal` = baris ber-`reverses` (pembalik bertanggal batal), sehingga pembatalan mengurangi periode saat
  batal, bukan periode asal. Kwitansi LAMA (tanpa `kind`) yang memakai deposit dalam satu baris: deposit dianggap terpakai
  lebih dulu menurut urutan `allocations[]`, sisanya `kas`. Giro dihitung pada tanggal kwitansi dan ditandai
  `giro_uncleared` sampai tanggal cair tersedia (PM-T3).

Membangun ulang: `rebuild(date_from, entity_id)` menulis generasi baru per pesanan lalu memensiunkan baris basi pesanan itu
(pola `analytics_facts._write`); tanpa `date_from` baris generasi lama yang tersisa (pesanan terhapus) ikut dipensiunkan.
`sync()` memproses pesanan yang dokumennya berubah sejak tanda air (`ai_fact_state`, id = nama koleksi).
`reconcile(entity_id, period)` = INV-KM-1 dan INV-KM-2; `rebuild_diff()` = INV-KM-3 (dipakai `verify_data_integrity.py`).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from core_utils import from_cents, now_iso, to_cents
from db import db

logger = logging.getLogger(__name__)

SHIP = "fact_shipment_sales"
COLL = "fact_collections"
STATE_IDS = (SHIP, COLL)
BATCH = 200
EPS = 0.005
#: Jurnal yang membentuk omzet di buku (INV-KM-1). Antar-PT, jurnal manual, dan penutup berjenis sumber lain.
REVENUE_SOURCES = ("shipment_revenue", "sales_order", "sales_return", "amendment_credit_note")
REVENUE_KEY = "penjualan.pendapatan"
_SO_FIELDS = {"_id": 0, "status_history": 0, "refs": 0, "verification": 0, "timeline": 0, "allocations": 0}


# ── Pembantu ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _f(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _date(value: Any, fallback: Any = None) -> str:
    """Tanggal buku WIB `YYYY-MM-DD` (satu fungsi tanggal buku, `02` D6); nilai tak dikenali → cadangan → ""."""
    from services.book_date import tanggal_buku
    for v in (value, fallback):
        if v:
            try:
                return tanggal_buku(v)
            except ValueError:
                continue
    return ""


def _giro_codes() -> Set[str]:
    from services.payment_method_service import BENIH_BY_CODE
    g = BENIH_BY_CODE.get("giro") or {}
    return {str(g.get("code") or "giro").lower(), *[str(a).lower() for a in g.get("aliases") or []]}


def attribution(so: Dict[str, Any], customer: Dict[str, Any], users: Dict[str, Dict[str, Any]]) -> List[Tuple[str, float]]:
    """(sales_id, split) pemilik angka pesanan: potret `sales_attribution` (K-21) bila ada; selain itu aturan tim
    `analytics_facts.attribute_sales`. Split dinormalkan supaya Σ = 1."""
    from services.analytics_facts import attribute_sales, snapshot_attribution
    return snapshot_attribution(so) or attribute_sales(so, customer or {}, users, "team_split")


def _split(total: float, splits: List[float]) -> List[float]:
    from services.analytics_facts import _alloc
    return _alloc(round(total, 2), splits)


def _ratio_value(net: float, item: Optional[Dict[str, Any]], field: str) -> Optional[float]:
    """`net × harga pembanding ÷ price` baris; kosong bila pembanding atau harga kosong."""
    if not item:
        return None
    ref, price = item.get(field), _f(item.get("price") or item.get("unit_price"))
    if ref is None or price <= 0:
        return None
    return round(net * _f(ref) / price, 2)


def _item_index(so: Dict[str, Any], item: Optional[Dict[str, Any]]) -> Optional[int]:
    for i, it in enumerate(so.get("items") or []):
        if it is item:
            return i
    return None


# ── Fakta omzet ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _ship_rows(kind: str, src_id: str, src_no: str, so: Dict[str, Any], customer: Dict[str, Any],
               attrs: List[Tuple[str, float]], item: Optional[Dict[str, Any]], line_idx: Optional[int], *, net: float,
               qty: float, cost: float, date_wib: str, gen: str, built: str,
               values: Optional[Dict[str, Optional[float]]] = None) -> List[Dict[str, Any]]:
    splits = [sp for _, sp in attrs]
    nets, costs = _split(net, splits), _split(cost, splits)
    vals = values if values is not None else {f: _ratio_value(net, item, f)
                                              for f in ("list_price", "global_price", "floor_price")}
    parts = {f: (_split(v, splits) if v is not None else [None] * len(splits)) for f, v in vals.items()}
    it = item or {}
    out = []
    for si, (sales_id, split) in enumerate(attrs):
        out.append({
            "_id": f"{kind}:{src_id}:{'' if line_idx is None else line_idx}:{sales_id}",
            "source_kind": kind, "source_id": src_id, "source_number": src_no,
            "entity_id": so.get("entity_id") or "", "so_id": so["id"], "so_number": so.get("number") or "",
            "customer_id": so.get("customer_id") or "",
            "customer_name": so.get("customer_name") or (customer or {}).get("name") or "",
            "line_idx": line_idx, "sales_id": sales_id, "split": round(split, 6),
            "product_id": it.get("product_id") or "", "sku": it.get("sku") or "", "category": it.get("category") or "",
            "line_code": str(it.get("line_code") or "").lower(), "price_source": it.get("price_source") or "",
            "qty_base": round(qty * split, 4), "net": nets[si],
            "list_value": parts["list_price"][si], "global_value": parts["global_price"][si],
            "floor_value": parts["floor_price"][si], "cost": costs[si], "cost_known": abs(cost) > EPS,
            "date_wib": date_wib, "period": date_wib[:7], "built_at": built, "build_gen": gen,
        })
    return out


def _shipment_cost(sh: Dict[str, Any], item: Optional[Dict[str, Any]], qty: float) -> float:
    """Biaya roll surat jalan (potret `rolls[]`, aturan `post_shipment_cogs`); tanpa potret: `unit_cost × qty`."""
    snap = sh.get("rolls") or []
    if snap:
        return from_cents(sum(to_cents(r["extended_cost"]) if r.get("extended_cost") is not None
                              else to_cents(_f(r.get("unit_cost")) * _f(r.get("length"))) for r in snap))
    return round(_f((item or {}).get("unit_cost")) * qty, 2)


def _revenue_date_legacy(so: Dict[str, Any]) -> Any:
    """Tanggal jurnal per pesanan tanpa surat jalan (`gl_service._revenue_date`)."""
    if so.get("delivered_at"):
        return so["delivered_at"]
    pays = so.get("payments") or []
    if pays:
        return pays[-1].get("date") or pays[-1].get("created_at")
    return so.get("created_at")


def shipment_rows(so: Dict[str, Any], *, customer: Dict[str, Any], users: Dict[str, Dict[str, Any]],
                  shipments: List[Dict[str, Any]], notes: List[Dict[str, Any]], returns: Dict[str, Dict[str, Any]],
                  legacy_date: Optional[str], gen: str = "", built: str = "") -> List[Dict[str, Any]]:
    """Baris `fact_shipment_sales` satu pesanan (fungsi murni atas dokumen yang sudah dimuat)."""
    from services import gl_service as gl
    from services.customer_service import DEAD_STATUSES
    from services.profitability_service import _order_net_alloc
    built = built or now_iso()
    attrs = attribution(so, customer, users)
    rows: List[Dict[str, Any]] = []
    lines, alloc = _order_net_alloc(so)
    net_order = round(sum(alloc), 2)
    live = so.get("status") not in DEAD_STATUSES and gl.order_grand_total(so) > EPS
    if live and (legacy_date is not None or (not shipments and so.get("status") in gl.REVENUE_STATUSES)):
        d = legacy_date or _date(_revenue_date_legacy(so))
        for li, it in enumerate(lines):
            if abs(alloc[li]) <= EPS:
                continue
            qty = _f(it.get("base_quantity")) or _f(it.get("quantity"))
            rows += _ship_rows("pesanan_lama", so["id"], so.get("number") or "", so, customer, attrs, it,
                               _item_index(so, it), net=alloc[li], qty=qty,
                               cost=round(_f(it.get("unit_cost")) * qty, 2), date_wib=d, gen=gen, built=built)
    elif live and shipments:
        done = 0.0
        last = len(shipments) - 1
        for i, sh in enumerate(shipments):
            if i == last and so.get("status") in gl.FULLY_SHIPPED_STATUSES:
                rev = round(net_order - done, 2)
            else:
                rev = round(min(net_order * gl.shipment_value_share(so, sh), net_order - done), 2)
            if rev <= EPS:
                continue
            done = round(done + rev, 2)
            it = gl._order_item_for(so, sh.get("product_id", ""))
            qty = _f(sh.get("qty"))
            rows += _ship_rows("kirim", sh["id"], sh.get("shipment_no") or "", so, customer, attrs, it,
                               _item_index(so, it), net=rev, qty=qty, cost=_shipment_cost(sh, it, qty),
                               date_wib=_date(sh.get("created_at")), gen=gen, built=built)
    for cn in notes:
        r = note_row_basis(cn, returns)
        if not r:
            continue
        pids = list(dict.fromkeys(ln.get("product_id") for ln in cn.get("lines") or [] if ln.get("product_id")))
        it = gl._order_item_for(so, pids[0]) if len(pids) == 1 else None
        qty = sum(_f(ln.get("quantity")) for ln in cn.get("lines") or []) if it else 0.0
        rows += _ship_rows(r["kind"], cn["id"], cn.get("number") or "", so, customer, attrs, it,
                           None, net=-r["net"], qty=-qty, cost=-r["cost"], date_wib=r["date"], gen=gen, built=built)
    return rows


def note_row_basis(cn: Dict[str, Any], returns: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Jenis, nilai bersih (positif), biaya, dan tanggal nota kredit yang mendebit pendapatan; None = tidak ikut."""
    if cn.get("status") in ("void", "cancelled", "voided"):
        return None
    if cn.get("return_id"):
        net = round(_f(cn.get("net_amount")), 2)
        if net <= EPS:
            return None
        if cn.get("settlement_id"):
            d = _date(cn.get("created_at"))
        else:
            d = _date((returns.get(cn["return_id"]) or {}).get("approved_at"), cn.get("created_at"))
        return {"kind": "retur", "net": net, "cost": round(_f(cn.get("cogs_amount")), 2), "date": d}
    if (cn.get("kind") or "credit_note") != "credit_note":
        return None
    if cn.get("source") == "amendment" and cn.get("status") == "posted":
        gross, off = _f(cn.get("gross_amount")), _f(cn.get("debit_note_offset"))
        net = _f(cn.get("net_amount"))
        if off > EPS and gross > EPS:   # nota debit belum ditagih di-offset dulu (`amendment_service._settle_credit_note`)
            g2 = round(gross - off, 2)
            net = round(g2 - round(_f(cn.get("ppn_amount")) * g2 / gross, 2), 2)
    elif cn.get("source") == "od_item_cancel" and cn.get("status") == "issued" and cn.get("revenue_recognized"):
        net = _f(cn.get("net_amount"))
    else:
        return None
    net = round(net, 2)
    if net <= EPS:
        return None
    return {"kind": "koreksi", "net": net, "cost": 0.0, "date": _date(cn.get("created_at"))}


# ── Fakta pencairan ──────────────────────────────────────────────────────────────────────────────────────────────────
def _legacy_deposit_part(receipt: Dict[str, Any], order_id: str) -> float:
    """Kwitansi lama (satu baris per pesanan): bagian deposit untuk pesanan itu — deposit terpakai lebih dulu menurut
    urutan `allocations[]`."""
    left = _f(receipt.get("used_deposit"))
    part = 0.0
    for a in receipt.get("allocations") or []:
        take = min(left, _f(a.get("applied")))
        if a.get("order_id") == order_id:
            part += take
        left = round(left - take, 2)
    return round(part, 2)


def collection_rows(so: Dict[str, Any], *, customer: Dict[str, Any], users: Dict[str, Dict[str, Any]],
                    receipts: Dict[str, Dict[str, Any]], gen: str = "", built: str = "") -> List[Dict[str, Any]]:
    """Baris `fact_collections` satu pesanan (fungsi murni atas dokumen yang sudah dimuat)."""
    from services import gl_service as gl
    from services.ar_allocation_service import payment_kind
    built = built or now_iso()
    attrs = attribution(so, customer, users)
    splits = [sp for _, sp in attrs]
    giro = _giro_codes()
    grand = gl.order_grand_total(so)
    cum, paid_before = 0.0, False
    rows: List[Dict[str, Any]] = []
    for n, p in enumerate(so.get("payments") or []):
        if not isinstance(p, dict):
            continue
        amt = round(_f(p.get("amount")), 2)
        cum = round(cum + amt, 2)
        paid_now = grand > EPS and cum >= grand - EPS
        settles, paid_before = paid_now and not paid_before, paid_now
        rid = str(p.get("id") or f"i{n}")
        kind = payment_kind(p)
        parts = [(kind, amt, rid)]
        rc = receipts.get(p.get("receipt_id") or "")
        if not p.get("kind") and kind == "kas" and rc and _f(rc.get("used_deposit")) > EPS and amt > EPS:
            dep = min(_legacy_deposit_part(rc, so["id"]), amt)
            parts = [x for x in (("deposit", dep, f"{rid}:deposit"), ("kas", round(amt - dep, 2), rid)) if x[1] > EPS]
        d = _date(p.get("date"), p.get("created_at"))
        method = str(p.get("method") or "")
        for k, a, pid in parts:
            amounts = _split(a, splits)
            for si, (sales_id, split) in enumerate(attrs):
                rows.append({
                    "_id": f"{so['id']}:{pid}:{sales_id}", "entity_id": so.get("entity_id") or "", "so_id": so["id"],
                    "so_number": so.get("number") or "", "customer_id": so.get("customer_id") or "",
                    "sales_id": sales_id, "split": round(split, 6), "receipt_id": p.get("receipt_id") or "",
                    "receipt_number": p.get("receipt_number") or "", "source_kind": k, "method": method,
                    "is_reversal": bool(p.get("reverses")), "amount": amounts[si], "date_wib": d, "period": d[:7],
                    "settles_order": settles, "giro_uncleared": k == "kas" and method.lower() in giro,
                    "built_at": built, "build_gen": gen})
    return rows


# ── Pemuatan & penulisan per kelompok pesanan ────────────────────────────────────────────────────────────────────────
async def _context(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    from services import gl_service as gl
    ids = [o["id"] for o in orders]
    cids = list({o.get("customer_id") for o in orders if o.get("customer_id")})
    customers = {c["id"]: c for c in await db.customers.find(
        {"id": {"$in": cids}}, {"_id": 0, "id": 1, "name": 1, "assigned_sales_id": 1}).to_list(None)}
    users = {u["id"]: u for u in await db.users.find({}, {"_id": 0, "id": 1, "name": 1, "role": 1}).to_list(None)}
    ships: Dict[str, List[Dict[str, Any]]] = {}
    async for s in db.shipments.find({"order_id": {"$in": ids}, "status": {"$nin": list(gl.SHIPMENT_DEAD)}},
                                     {"_id": 0}).sort("created_at", 1):
        ships.setdefault(s["order_id"], []).append(s)
    notes: Dict[str, List[Dict[str, Any]]] = {}
    async for cn in db.credit_notes.find({"order_id": {"$in": ids}}, {"_id": 0}).sort("created_at", 1):
        notes.setdefault(cn["order_id"], []).append(cn)
    rids = list({cn["return_id"] for v in notes.values() for cn in v if cn.get("return_id")})
    returns = {r["id"]: r for r in await db.sales_returns.find(
        {"id": {"$in": rids}}, {"_id": 0, "id": 1, "approved_at": 1, "order_id": 1}).to_list(None)} if rids else {}
    legacy = {j["source_id"]: j.get("date") or "" async for j in db.journal_entries.find(
        {"source_type": "sales_order", "source_id": {"$in": ids}, "status": {"$ne": "void"}},
        {"_id": 0, "source_id": 1, "date": 1})}
    rc_ids = list({p.get("receipt_id") for o in orders for p in o.get("payments") or []
                   if isinstance(p, dict) and p.get("receipt_id") and not p.get("kind")})
    receipts = {r["id"]: r for r in await db.ar_receipts.find(
        {"id": {"$in": rc_ids}}, {"_id": 0, "id": 1, "used_deposit": 1, "allocations": 1}).to_list(None)} if rc_ids else {}
    return {"customers": customers, "users": users, "ships": ships, "notes": notes, "returns": returns,
            "legacy": legacy, "receipts": receipts}


async def rows_for(orders: List[Dict[str, Any]], gen: str = "") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(baris omzet, baris pencairan) untuk sekelompok pesanan — tanpa menulis apa pun."""
    if not orders:
        return [], []
    ctx = await _context(orders)
    built = now_iso()
    ship_rows: List[Dict[str, Any]] = []
    coll_rows: List[Dict[str, Any]] = []
    for o in orders:
        cust = ctx["customers"].get(o.get("customer_id") or "") or {}
        ship_rows += shipment_rows(o, customer=cust, users=ctx["users"], shipments=ctx["ships"].get(o["id"], []),
                                   notes=ctx["notes"].get(o["id"], []), returns=ctx["returns"],
                                   legacy_date=ctx["legacy"][o["id"]] if o["id"] in ctx["legacy"] else None,
                                   gen=gen, built=built)
        coll_rows += collection_rows(o, customer=cust, users=ctx["users"], receipts=ctx["receipts"], gen=gen,
                                     built=built)
    return ship_rows, coll_rows


async def _write(orders: List[Dict[str, Any]], gen: str) -> Tuple[int, int]:
    """Tulis generasi baru per `_id` LALU pensiunkan baris basi pesanan itu (gagal di tengah → baris lama tetap)."""
    from pymongo import ReplaceOne
    ship_rows, coll_rows = await rows_for(orders, gen)
    ids = [o["id"] for o in orders]
    for name, rows in ((SHIP, ship_rows), (COLL, coll_rows)):
        if rows:
            await db[name].bulk_write([ReplaceOne({"_id": r["_id"]}, r, upsert=True) for r in rows], ordered=False)
        await db[name].delete_many({"so_id": {"$in": ids}, "_id": {"$nin": [r["_id"] for r in rows]}})
    return len(ship_rows), len(coll_rows)


async def _process(query: Dict[str, Any], gen: str) -> Dict[str, int]:
    n_so = n_ship = n_coll = 0
    batch: List[Dict[str, Any]] = []

    async def _flush() -> None:
        nonlocal n_so, n_ship, n_coll, batch
        if batch:
            a, b = await _write(batch, gen)
            n_so, n_ship, n_coll = n_so + len(batch), n_ship + a, n_coll + b
            batch = []

    async for o in db.sales_orders.find(query, _SO_FIELDS):
        batch.append(o)
        if len(batch) >= BATCH:
            await _flush()
    await _flush()
    return {"orders": n_so, "rows_shipment": n_ship, "rows_collection": n_coll}


def _utc_from_wib_date(d: str) -> str:
    from services.analytics_time import wib_midnight_utc
    return wib_midnight_utc(date.fromisoformat(d))


async def changed_order_ids(since_utc: str, since_date: str = "", entity_id: Optional[str] = None) -> List[str]:
    """Pesanan yang dokumen sumbernya berubah/bertanggal sejak `since_utc` (stempel UTC) atau `since_date` (WIB)."""
    ids: Set[str] = set()
    ent = {"entity_id": entity_id} if entity_id else {}
    ts = lambda f: {f: {"$gte": since_utc}}   # noqa: E731
    async for o in db.sales_orders.find({**ent, "$or": [ts("updated_at"), ts("created_at")]}, {"_id": 0, "id": 1}):
        ids.add(o["id"])
    async for s in db.shipments.find({**ent, "$or": [ts("updated_at"), ts("created_at")]}, {"_id": 0, "order_id": 1}):
        ids.add(s.get("order_id") or "")
    async for c in db.credit_notes.find({**ent, "$or": [ts("updated_at"), ts("created_at")]},
                                        {"_id": 0, "order_id": 1}):
        ids.add(c.get("order_id") or "")
    rq: List[Dict[str, Any]] = [ts("updated_at"), ts("created_at"), ts("voided_at")]
    if since_date:
        rq.append({"receipt_date": {"$gte": since_date}})
    async for r in db.ar_receipts.find({**ent, "$or": rq}, {"_id": 0, "allocations.order_id": 1}):
        ids.update(a.get("order_id") or "" for a in r.get("allocations") or [])
    ids.discard("")
    return sorted(ids)


# ── Kunci, tanda air, bangun ulang ───────────────────────────────────────────────────────────────────────────────────
class FaktaSibuk(RuntimeError):
    """Pembangun fakta lain sedang berjalan."""


async def _claim(minutes: int = 10) -> bool:
    now = datetime.now(timezone.utc)
    await db.ai_fact_state.update_one({"id": SHIP}, {"$setOnInsert": {"id": SHIP}}, upsert=True)
    got = await db.ai_fact_state.find_one_and_update(
        {"id": SHIP, "$or": [{"build_lock_until": {"$exists": False}}, {"build_lock_until": {"$lt": now.isoformat()}}]},
        {"$set": {"build_lock_until": (now + timedelta(minutes=minutes)).isoformat()}}, projection={"_id": 0, "id": 1})
    return bool(got)


async def _release() -> None:
    await db.ai_fact_state.update_one({"id": SHIP}, {"$unset": {"build_lock_until": ""}})


async def _mark(watermark: str, **extra: Any) -> None:
    for sid in STATE_IDS:
        st = await db.ai_fact_state.find_one({"id": sid}, {"_id": 0}) or {}
        await db.ai_fact_state.update_one({"id": sid}, {"$set": {
            "id": sid, "watermark": max(st.get("watermark") or "", watermark), "last_sync_at": now_iso(),
            "last_error": "", **extra}}, upsert=True)


async def rebuild(date_from: Optional[str] = None, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Bangun ulang fakta pesanan yang dokumennya bertanggal/berubah ≥ `date_from` (tanggal WIB; kosong = semua) di PT
    `entity_id` (kosong = semua PT). Menulis generasi baru lalu memensiunkan baris basi."""
    if not await _claim():
        raise FaktaSibuk("Fakta insentif sedang dibangun ulang. Coba lagi sebentar lagi.")
    started = now_iso()
    gen = f"gen_{started}"
    try:
        ent = {"entity_id": entity_id} if entity_id else {}
        if date_from:
            ids = await changed_order_ids(_utc_from_wib_date(date_from), date_from, entity_id)
            res = {"orders": 0, "rows_shipment": 0, "rows_collection": 0}
            for i in range(0, len(ids), BATCH):
                part = await _process({**ent, "id": {"$in": ids[i:i + BATCH]}}, gen)
                res = {k: res[k] + part[k] for k in res}
        else:
            res = await _process(ent, gen)
            for name in (SHIP, COLL):
                await db[name].delete_many({**ent, "build_gen": {"$ne": gen}})
        await _mark(started, last_rebuild_at=now_iso(), last_rebuild_from=date_from or "",
                    last_rebuild_entity=entity_id or "")
    except Exception as exc:
        for sid in STATE_IDS:
            await db.ai_fact_state.update_one({"id": sid}, {"$set": {
                "id": sid, "last_error": str(exc)[:300], "last_error_at": now_iso()}}, upsert=True)
        raise
    finally:
        await _release()
    return {**res, "from": date_from or "", "entity_id": entity_id or ""}


async def sync() -> Dict[str, Any]:
    """Inkremental: pesanan yang dokumennya berubah sejak tanda air (jendela tumpang 10 menit). Belum pernah dibangun →
    bangun ulang penuh."""
    st = await db.ai_fact_state.find_one({"id": SHIP}, {"_id": 0}) or {}
    if not st.get("watermark"):
        return await rebuild()
    if not await _claim():
        raise FaktaSibuk("Fakta insentif sedang dibangun ulang.")
    started = now_iso()
    try:
        try:
            lo = (datetime.fromisoformat(st["watermark"]) - timedelta(minutes=10)).isoformat()
        except ValueError:
            lo = st["watermark"]
        ids = await changed_order_ids(lo)
        res = {"orders": 0, "rows_shipment": 0, "rows_collection": 0}
        gen = f"gen_{started}"
        for i in range(0, len(ids), BATCH):
            part = await _process({"id": {"$in": ids[i:i + BATCH]}}, gen)
            res = {k: res[k] + part[k] for k in res}
        await _mark(started)
    finally:
        await _release()
    return res


async def ensure_fresh(max_age_seconds: int = 60) -> str:
    """Sinkron inkremental bila terakhir > `max_age_seconds`; bangun ulang penuh tidak dijalankan di dalam permintaan
    pengguna (menunggu tugas terjadwal). Mengembalikan stempel sinkron terakhir."""
    st = await db.ai_fact_state.find_one({"id": SHIP}, {"_id": 0}) or {}
    last = st.get("last_sync_at") or ""
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() if last else 1e9
    except ValueError:
        age = 1e9
    if age > max_age_seconds and st.get("watermark"):
        try:
            await sync()
        except FaktaSibuk:
            pass
        except Exception as exc:  # noqa: BLE001 — pembaca tetap memakai fakta yang ada
            logger.warning("[incentive_facts] sinkron gagal: %s", exc)
        st = await db.ai_fact_state.find_one({"id": SHIP}, {"_id": 0}) or {}
    return st.get("last_sync_at") or ""


async def job_incentive_fact_sync() -> Dict[str, Any]:
    from services.incentive_definitions import current_definition
    res = await sync()
    for e in await db.business_entities.find({}, {"_id": 0, "id": 1}).to_list(None):   # potret versi definisi PT
        await current_definition(e["id"])
    return {"scanned": res["orders"], "created": 0,
            "detail": f"{res['orders']} pesanan → {res['rows_shipment']} baris omzet, "
                      f"{res['rows_collection']} baris pencairan diperbarui"}


async def job_incentive_fact_nightly() -> Dict[str, Any]:
    from services.analytics_time import now_wib
    since = (now_wib().date() - timedelta(days=90)).isoformat()
    res = await rebuild(since)
    return {"scanned": res["orders"], "created": 0,
            "detail": f"Bangun ulang 90 hari ({since}): {res['orders']} pesanan → {res['rows_shipment']} baris omzet, "
                      f"{res['rows_collection']} baris pencairan"}


# ── Pencocokan (INV-KM-1, INV-KM-2) ──────────────────────────────────────────────────────────────────────────────────
def _month_bounds(period: str) -> Tuple[str, str]:
    from services.incentive_periods import bounds_with
    return bounds_with("month", period, 12)


async def _revenue_codes(entity_id: str) -> Set[str]:
    from services.gl_mapping_service import known_codes
    return set(await known_codes(REVENUE_KEY, entity_id))


async def book_revenue_by_order(entity_id: str, period: str) -> Dict[str, float]:
    """Σ (kredit − debit) akun pendapatan penjualan per pesanan pada jurnal tidak batal bersumber penjualan, bulan WIB."""
    start, end = _month_bounds(period)
    codes = await _revenue_codes(entity_id)
    out: Dict[str, float] = {}
    ret_ids: Set[str] = set()
    async for je in db.journal_entries.find(
            {"entity_id": entity_id, "source_type": {"$in": list(REVENUE_SOURCES)}, "status": {"$ne": "void"},
             "date": {"$gte": start, "$lte": end}}, {"_id": 0, "source_type": 1, "source_id": 1, "ref": 1, "lines": 1}):
        val = sum(_f(ln.get("credit")) - _f(ln.get("debit")) for ln in je.get("lines") or []
                  if ln.get("account_code") in codes)
        ref = je.get("ref") or {}
        st = je.get("source_type")
        if st == "sales_order":
            key = je.get("source_id") or ""
        elif st == "sales_return":
            rid = ref.get("return_id") or str(je.get("source_id") or "").split(":")[0]
            ret_ids.add(rid)
            key = f"ret:{rid}"
        else:
            key = ref.get("order_id") or f"{st}:{je.get('source_id')}"
        out[key] = round(out.get(key, 0.0) + val, 2)
    if ret_ids:
        for r in await db.sales_returns.find({"id": {"$in": list(ret_ids)}}, {"_id": 0, "id": 1,
                                                                               "order_id": 1}).to_list(None):
            v = out.pop(f"ret:{r['id']}", 0.0)
            key = r.get("order_id") or f"ret:{r['id']}"
            out[key] = round(out.get(key, 0.0) + v, 2)
    return out


async def fact_revenue_by_order(entity_id: str, period: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    async for r in db[SHIP].find({"entity_id": entity_id, "period": period},
                                 {"_id": 0, "so_id": 1, "so_number": 1, "net": 1}):
        d = out.setdefault(r["so_id"], {"so_number": r.get("so_number") or "", "net": 0.0})
        d["net"] = from_cents(to_cents(d["net"]) + to_cents(r.get("net")))
    return out


async def reconcile_revenue(entity_id: str, period: str) -> Dict[str, Any]:
    """INV-KM-1 — Σ `fact_shipment_sales.net` (semua sales, termasuk tanpa sales) = Σ mutasi akun pendapatan penjualan."""
    facts = await fact_revenue_by_order(entity_id, period)
    book = await book_revenue_by_order(entity_id, period)
    fakta = from_cents(sum(to_cents(v["net"]) for v in facts.values()))
    buku = from_cents(sum(to_cents(v) for v in book.values()))
    keys = set(facts) | set(book)
    sebab: List[Dict[str, Any]] = []
    numbers = {k: v["so_number"] for k, v in facts.items()}
    missing = [k for k in keys if k not in numbers]
    if missing:
        numbers.update({o["id"]: o.get("number") or "" for o in await db.sales_orders.find(
            {"id": {"$in": missing}}, {"_id": 0, "id": 1, "number": 1}).to_list(None)})
    for k in keys:
        f, b = (facts.get(k) or {}).get("net", 0.0), book.get(k, 0.0)
        if abs(f - b) < 1:
            continue
        if abs(b) < EPS:
            ada = await db.journal_entries.find_one({"source_type": {"$in": list(REVENUE_SOURCES)},
                                                     "status": {"$ne": "void"},
                                                     "$or": [{"ref.order_id": k}, {"source_id": k}]}, {"_id": 0, "id": 1})
            alasan = "Jurnal pendapatan ada di bulan lain (tanggal beda bulan)." if ada else "Jurnal pendapatan belum terbit."
        elif abs(f) < EPS:
            alasan = "Ada jurnal pendapatan tanpa fakta di bulan ini (tanggal beda bulan atau fakta belum dibangun ulang)."
        else:
            alasan = "Nilai fakta berbeda dengan jurnal pendapatan."
        sebab.append({"so_id": k, "so_number": numbers.get(k, ""), "fakta": round(f, 2), "buku": round(b, 2),
                      "selisih": round(f - b, 2), "sebab": alasan})
    sebab.sort(key=lambda x: -abs(x["selisih"]))
    selisih = round(fakta - buku, 2)
    return {"fakta": fakta, "buku": buku, "selisih": selisih, "ok": abs(selisih) < max(1, len(keys)),
            "pesanan": len(keys), "penyebab": sebab[:50], "jumlah_penyebab": len(sebab)}


def receipt_unallocated_cash(r: Dict[str, Any]) -> float:
    """Kas kwitansi yang belum dialokasikan: kas baru − bagian kas alokasi. Kwitansi PK-19 menyimpan `parts` (kas lebih
    dulu, lalu deposit); kwitansi lama memakai aturan "deposit terpakai lebih dulu"."""
    amount, applied = _f(r.get("amount")), _f(r.get("applied_total"))
    allocs = r.get("allocations") or []
    if any("parts" in a for a in allocs):
        kas = sum(_f(p.get("amount")) for a in allocs for p in a.get("parts") or [] if p.get("kind") == "kas")
    else:
        kas = applied - min(_f(r.get("used_deposit")), applied)
    return round(amount - kas, 2)


async def reconcile_collections(entity_id: str, period: str) -> Dict[str, Any]:
    """INV-KM-2 — A = Σ fakta jenis `kas` (termasuk pembalik); B = kas kwitansi belum dialokasikan; C = Σ kwitansi bulan
    itu − kwitansi yang batal di bulan itu; D = Σ kas masuk kwitansi (aturan batal sama). Lulus bila |A + B − C| < 1 dan
    |C − D| < 1."""
    start, end = _month_bounds(period)
    per: Dict[str, Dict[str, float]] = {}

    def _r(rid: str) -> Dict[str, float]:
        return per.setdefault(rid, {"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0})

    async for f in db[COLL].find({"entity_id": entity_id, "period": period, "source_kind": "kas"},
                                 {"_id": 0, "receipt_id": 1, "amount": 1}):
        _r(f.get("receipt_id") or "")["a"] += _f(f.get("amount"))
    numbers: Dict[str, str] = {}
    async for r in db.ar_receipts.find({"entity_id": entity_id}, {"_id": 0, "id": 1, "number": 1, "amount": 1,
                                                                  "applied_total": 1, "used_deposit": 1,
                                                                  "allocations": 1, "receipt_date": 1, "status": 1,
                                                                  "voided_at": 1, "created_at": 1}):
        numbers[r["id"]] = r.get("number") or ""
        d = _date(r.get("receipt_date"), r.get("created_at"))
        if start <= d <= end:
            x = _r(r["id"])
            x["c"] += _f(r.get("amount"))
            x["b"] += receipt_unallocated_cash(r)
        if r.get("status") == "void" and start <= _date(r.get("voided_at")) <= end:
            x = _r(r["id"])
            x["c"] -= _f(r.get("amount"))
            x["b"] -= receipt_unallocated_cash(r)
    voided = {r["id"]: r.get("voided_at") for r in await db.ar_receipts.find(
        {"entity_id": entity_id, "status": "void"}, {"_id": 0, "id": 1, "voided_at": 1}).to_list(None)}
    async for c in db.cash_transactions.find({"ref_type": "ar_receipt", "direction": "in", "entity_id": entity_id},
                                             {"_id": 0, "ref_id": 1, "amount": 1, "txn_date": 1, "created_at": 1,
                                              "status": 1, "updated_at": 1}):
        rid = c.get("ref_id") or ""
        if start <= _date(c.get("txn_date"), c.get("created_at")) <= end:
            _r(rid)["d"] += _f(c.get("amount"))
        if c.get("status") == "void" and start <= _date(voided.get(rid) or c.get("updated_at")) <= end:
            _r(rid)["d"] -= _f(c.get("amount"))
    # PM-T4 — kwitansi tunai yang dicatat sebagai titipan di tangan sales tidak punya kas masuk sampai disetor: uangnya
    # tercatat di titipan (`cash_holdings`, nominal = uang baru kwitansi). Titipan batal mengikuti tanggal batal kwitansi.
    async for h in db.cash_holdings.find({"entity_id": entity_id}, {"_id": 0, "receipt_id": 1, "amount": 1,
                                                                    "received_at": 1, "status": 1, "voided_at": 1}):
        rid = h.get("receipt_id") or ""
        if start <= _date(h.get("received_at")) <= end:
            _r(rid)["d"] += _f(h.get("amount"))
        if h.get("status") == "batal" and start <= _date(voided.get(rid) or h.get("voided_at")) <= end:
            _r(rid)["d"] -= _f(h.get("amount"))
    tot = {k: round(sum(v[k] for v in per.values()), 2) for k in ("a", "b", "c", "d")}
    sebab = []
    for rid, v in per.items():
        if abs(v["a"] + v["b"] - v["c"]) < 1 and abs(v["c"] - v["d"]) < 1:
            continue
        if not rid:
            alasan = "Baris pembayaran jenis kas tanpa kwitansi."
        elif rid not in numbers:
            alasan = "Kas masuk atau baris pembayaran merujuk kwitansi yang tidak ada."
        elif abs(v["c"] - v["d"]) >= 1:
            alasan = "Kas masuk kwitansi berbeda dengan nominal kwitansi."
        else:
            alasan = "Alokasi kwitansi ke pesanan berbeda dengan baris pembayaran (tanggal beda bulan atau fakta belum dibangun ulang)."
        sebab.append({"receipt_id": rid, "receipt_number": numbers.get(rid, ""), "dialokasikan": round(v["a"], 2),
                      "belum_dialokasikan": round(v["b"], 2), "kwitansi": round(v["c"], 2), "kas": round(v["d"], 2),
                      "sebab": alasan})
    selisih = round(tot["a"] + tot["b"] - tot["c"], 2)
    selisih_kas = round(tot["c"] - tot["d"], 2)
    return {"dialokasikan": tot["a"], "belum_dialokasikan": tot["b"], "kwitansi": tot["c"], "kas": tot["d"],
            "selisih": selisih, "selisih_kas": selisih_kas, "ok": abs(selisih) < 1 and abs(selisih_kas) < 1,
            "penyebab": sebab[:50], "jumlah_penyebab": len(sebab)}


async def reconcile(entity_id: str, period: str) -> Dict[str, Any]:
    """`{omzet: INV-KM-1, pencairan: INV-KM-2}` untuk satu PT dan satu bulan (`YYYY-MM`)."""
    from services.incentive_periods import normalize
    _pt, p = normalize("month", period)
    return {"entity_id": entity_id, "period": p, "omzet": await reconcile_revenue(entity_id, p),
            "pencairan": await reconcile_collections(entity_id, p)}


async def months_with_facts(entity_id: Optional[str] = None) -> List[Tuple[str, str]]:
    """(PT, bulan) yang punya fakta atau kwitansi — daftar periksa invarian."""
    flt = {"entity_id": entity_id} if entity_id else {}
    seen: Set[Tuple[str, str]] = set()
    for name in (SHIP, COLL):
        async for r in db[name].find(flt, {"_id": 0, "entity_id": 1, "period": 1}):
            if r.get("period"):
                seen.add((r.get("entity_id") or "", r["period"]))
    return sorted(seen)


# ── INV-KM-3 — hasil bangun ulang penuh = isi koleksi ────────────────────────────────────────────────────────────────
async def rebuild_diff(entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Bandingkan hasil `rebuild` penuh (dihitung di memori, tanpa menulis) dengan isi koleksi: jumlah baris dan Σ
    `net`/`amount` per PT per bulan. Kosong = cocok."""
    def _agg(acc: Dict[Tuple[str, str, str], List[int]], name: str, rows: Iterable[Dict[str, Any]]) -> None:
        fld = "net" if name == SHIP else "amount"
        for r in rows:
            k = (name, r.get("entity_id") or "", r.get("period") or "")
            v = acc.setdefault(k, [0, 0])
            v[0] += 1
            v[1] += to_cents(r.get(fld))

    expected: Dict[Tuple[str, str, str], List[int]] = {}
    batch: List[Dict[str, Any]] = []
    flt = {"entity_id": entity_id} if entity_id else {}
    async for o in db.sales_orders.find(flt, _SO_FIELDS):
        batch.append(o)
        if len(batch) >= BATCH:
            s, c = await rows_for(batch)
            _agg(expected, SHIP, s)
            _agg(expected, COLL, c)
            batch = []
    s, c = await rows_for(batch)
    _agg(expected, SHIP, s)
    _agg(expected, COLL, c)
    actual: Dict[Tuple[str, str, str], List[int]] = {}
    for name, fld in ((SHIP, "net"), (COLL, "amount")):
        _agg(actual, name, [r async for r in db[name].find(flt, {"_id": 0, "entity_id": 1, "period": 1, fld: 1})])
    out = []
    for k in sorted(set(expected) | set(actual)):
        e, a = expected.get(k, [0, 0]), actual.get(k, [0, 0])
        if e != a:
            out.append({"collection": k[0], "entity_id": k[1], "period": k[2], "rows_expected": e[0],
                        "rows_actual": a[0], "sum_expected": from_cents(e[1]), "sum_actual": from_cents(a[1])})
    return out
