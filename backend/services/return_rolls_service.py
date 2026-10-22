"""L08 LN-080 — retur hanya dari barang yang BENAR-BENAR terkirim (roll per SJ) + batas kumulatif atomik per SO."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from pymongo.errors import DuplicateKeyError

from db import db
from core_utils import now_iso

EPS = 0.01
ACTIVE = ["draft", "pending_approval", "approved", "inspecting", "inspected",
          "refund_settled", "credit_settled", "nego_settled"]
LOCK_TTL_S = 60


@asynccontextmanager
async def order_lock(order_id: str):
    """Kunci per SO: dua klaim retur paralel tidak bisa sama-sama lolos cek batas."""
    stale = (datetime.now(timezone.utc) - timedelta(seconds=LOCK_TTL_S)).isoformat()
    await db.return_create_locks.delete_one({"_id": order_id, "at": {"$lt": stale}})
    try:
        await db.return_create_locks.insert_one({"_id": order_id, "at": now_iso()})
    except DuplicateKeyError:
        raise ValueError("Retur lain untuk pesanan ini sedang disimpan — coba lagi sebentar.")
    try:
        yield
    finally:
        await db.return_create_locks.delete_one({"_id": order_id})


def _roll_claims(item: Dict[str, Any], shipped_len: Dict[str, float]) -> Dict[str, float]:
    qtys = item.get("roll_qtys") or {}
    return {rid: float(qtys.get(rid) if qtys.get(rid) is not None else shipped_len.get(rid, 0)) for rid in item.get("roll_ids") or []}


async def returnable(order_id: str, exclude_id: str = "") -> Dict[str, Any]:
    ships = await db.shipments.find({"order_id": order_id, "status": {"$ne": "cancelled"}}, {"_id": 0}).to_list(500)
    pids = list({s["product_id"] for s in ships})
    prods = {p["id"]: p async for p in db.products.find({"id": {"$in": pids}},
                                                       {"_id": 0, "id": 1, "name": 1, "sku": 1, "color": 1, "base_unit": 1})}
    rows: List[Dict[str, Any]] = []
    for s in ships:
        for r in s.get("rolls") or []:
            rows.append({"roll_id": r["roll_id"], "shipment_id": s["id"], "shipment_no": s.get("shipment_no", ""),
                         "product_id": s["product_id"], "lot": r.get("lot", ""),
                         # Trial 22 Okt (D8) — panjang roll = SATUAN DASAR produk; dulu label jatuh ke satuan SJ (= satuan
                         # baris SO pada data lama) → "Qty aktual per roll (meter)" padahal angkanya yard.
                         "shipped_qty": round(float(r.get("length") or 0), 2),
                         "unit": (prods.get(s["product_id"]) or {}).get("base_unit") or r.get("unit") or s.get("unit")})
    rnos = {x["id"]: x.get("roll_no", "") async for x in db.inventory_rolls.find(
        {"id": {"$in": [r["roll_id"] for r in rows]}}, {"_id": 0, "id": 1, "roll_no": 1})}
    shipped_len = {r["roll_id"]: r["shipped_qty"] for r in rows}
    roll_ret: Dict[str, float] = {}
    prod_ret: Dict[str, float] = {}
    async for rt in db.sales_returns.find({"order_id": order_id, "status": {"$in": ACTIVE}}, {"_id": 0, "id": 1, "items": 1}):
        if rt["id"] == exclude_id:
            continue
        for it in rt.get("items") or []:
            prod_ret[it.get("product_id")] = prod_ret.get(it.get("product_id"), 0) + float(it.get("quantity_returned") or 0)
            for rid, q in _roll_claims(it, shipped_len).items():
                roll_ret[rid] = roll_ret.get(rid, 0) + q
    for r in rows:
        p = prods.get(r["product_id"]) or {}
        r.update({"roll_no": rnos.get(r["roll_id"], ""), "product_name": p.get("name", ""), "sku": p.get("sku", ""),
                  "color": p.get("color", ""), "returned_qty": round(roll_ret.get(r["roll_id"], 0), 2)})
        r["remaining"] = round(max(r["shipped_qty"] - r["returned_qty"], 0), 2)
    by_product: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        b = by_product.setdefault(r["product_id"], {"product_id": r["product_id"], "product_name": r["product_name"],
                                                    "sku": r["sku"], "color": r["color"], "unit": r["unit"],
                                                    "shipped_qty": 0.0, "roll_count": 0})
        b["shipped_qty"] = round(b["shipped_qty"] + r["shipped_qty"], 2)
        b["roll_count"] += 1
    for b in by_product.values():
        b["returned_qty"] = round(prod_ret.get(b["product_id"], 0), 2)
        b["remaining"] = round(max(b["shipped_qty"] - b["returned_qty"], 0), 2)
    return {"order_id": order_id, "rolls": rows, "products": list(by_product.values()),
            "note": "Hanya barang yang sudah keluar lewat Surat Jalan yang bisa diretur."}


async def assert_shipped_items(order_id: str, items: List[Dict[str, Any]]) -> None:
    """Produk/roll harus berasal dari SJ SO ini; qty (kumulatif dgn retur aktif lain) ≤ terkirim."""
    data = await returnable(order_id)
    prods = {p["product_id"]: p for p in data["products"]}
    rolls = {r["roll_id"]: r for r in data["rolls"]}
    if not prods:
        raise ValueError("Pesanan ini belum punya barang terkirim (Surat Jalan) — retur belum bisa dibuat.")
    want: Dict[str, float] = {}
    per_roll: Dict[str, float] = {}
    for it in items:
        pid = it.get("product_id")
        if pid not in prods:
            raise ValueError(f"Produk '{it.get('product_name') or pid}' tidak ada di Surat Jalan pesanan ini.")
        qty = float(it.get("quantity_returned") or 0)
        want[pid] = want.get(pid, 0) + qty
        rids = list(dict.fromkeys(it.get("roll_ids") or []))
        for rid in rids:
            r = rolls.get(rid)
            if not r or r["product_id"] != pid:
                raise ValueError(f"Roll {rid} bukan roll terkirim untuk produk ini di pesanan ini.")
        if not rids:
            continue
        given = it.get("roll_qtys") or {}
        if given:
            claims = {rid: float(given.get(rid) or 0) for rid in rids}
        else:   # qty dibagi ke roll terpilih sesuai sisa masing-masing (bukan panjang kirim penuh)
            claims, left = {}, qty
            for rid in rids:
                take = round(min(left, max(rolls[rid]["remaining"] - per_roll.get(rid, 0), 0)), 2)
                claims[rid], left = take, round(left - take, 2)
        if abs(sum(claims.values()) - qty) > EPS:
            raise ValueError(f"Qty retur {qty:g} tidak sama dengan jumlah klaim per roll {sum(claims.values()):g}.")
        it["roll_ids"], it["roll_qtys"] = rids, claims
        for rid, q in claims.items():
            per_roll[rid] = per_roll.get(rid, 0) + q
    for rid, q in per_roll.items():
        if q <= 0 or q > rolls[rid]["remaining"] + EPS:
            raise ValueError(f"Roll {rolls[rid]['roll_no'] or rid}: klaim {q:g} melebihi sisa yang bisa diretur "
                             f"{rolls[rid]['remaining']:g} {rolls[rid]['unit']}.")
    for pid, q in want.items():
        if q > prods[pid]["remaining"] + EPS:
            p = prods[pid]
            raise ValueError(f"Retur melebihi batas untuk '{p['product_name']}': diminta {q:g}, sudah diretur "
                             f"{p['returned_qty']:g}, terkirim {p['shipped_qty']:g} {p['unit']}.")
