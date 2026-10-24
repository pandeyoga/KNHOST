"""UAT 24 Okt (P2) — harga Pesanan Khusus sesuai arahan pemilik SO-12 + nego lewat harga khusus SO.

* **Dasar harga** per item: item ber-INDUK (sumber "induk produk") → harga jual **Grade A induk** lewat rantai harga
  yang sudah ada (pelanggan → PT → global); tanpa induk → harga **diisi PIC Special Order** (`od_pricing.set_price`);
  belum diisi → usulan kontrak × (1 + margin) yang dikonfirmasi PIC saat mengunci.
* Kontrak × margin hanya **pembanding** laba untuk pemegang `od_pricing.view_cost` (keputusan P2-K4); harga di bawah
  kontrak tidak diblokir, tetapi Manajer diberi peringatan rugi.
* **Nego** sesudah kunci = harga khusus baris SO tertaut (lantai = harga kontrak, P2-K3; semua ke Manajer, P2-K2).
  Selama nego belum diputus / penolakan belum dijawab sales, pengadaan ditahan (P2.4).
* **Visibilitas biaya** (P2.5): biaya kontrak, margin, supplier, dan nomor kontrak dibuang dari respons OD (dan dari
  baris SO hasil OD) untuk peran tanpa `od_pricing.view_cost` — satu titik saring (middleware), sama seperti
  `field_visibility`.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from db import db
from core_utils import now_iso, rupiah

BASIS_LABEL = {"parent_grade_a": "Harga Grade A induk", "pic": "Harga PIC Special Order",
               "cost_margin": "Usulan kontrak + margin (dikonfirmasi PIC)", "negotiated": "Harga nego (ACC Manajer)"}
_PROJ = {"_id": 0, "id": 1, "sku": 1, "name": 1, "price": 1, "grade": 1, "variant_attrs": 1, "variant_options": 1,
         "template_id": 1, "base_unit": 1, "status": 1, "special_order_id": 1, "lebar": 1, "gramasi": 1,
         "qty_per_roll": 1, "conversion_factors": 1}


class NegoError(ValueError):
    pass


# ─── Dasar harga ─────────────────────────────────────────────────────────────
def _grade_a(p: Dict[str, Any]) -> bool:
    va = p.get("variant_attrs") if isinstance(p.get("variant_attrs"), dict) else {}
    return str(p.get("grade") or va.get("grade") or "").strip().upper() == "A"


def _color(p: Optional[Dict[str, Any]]) -> str:
    vo = (p or {}).get("variant_options") if isinstance((p or {}).get("variant_options"), dict) else {}
    return str(vo.get("color") or "").strip().upper()


def item_of(od: Dict[str, Any], item_id: str = "") -> Dict[str, Any]:
    """Item OD sumber dasar harga: per id (multi-item) atau item aktif pertama (OD satu item)."""
    items = [i for i in od.get("items") or [] if i.get("status") != "cancelled"]
    if item_id:
        return next((i for i in od.get("items") or [] if i.get("id") == item_id), {})
    return items[0] if items else {}


async def parent_reference(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Produk ACUAN Grade A induk item OD. None = item tanpa induk.
    Urutan: produk induk yang dipilih (bila Grade A) → Grade A sekeluarga berwarna sama → Grade A sekeluarga
    berharga tertinggi (aman: tidak menjual di bawah harga keluarga). SKU hasil pesanan khusus lain tidak dipakai."""
    tid = str((item or {}).get("source_template_id") or "").strip()
    pid = str((item or {}).get("source_product_id") or "").strip()
    if not tid and not pid:
        return None
    src = await db.products.find_one({"id": pid}, _PROJ) if pid else None
    if src and not tid:
        tid = src.get("template_id") or ""
    if src and _grade_a(src) and src.get("status") != "inactive":
        return {"product": src, "how": "produk induk yang dipilih (Grade A)"}
    if not tid:
        return {"product": None, "why": "produk induk tidak punya keluarga (template) — harga diisi PIC"}
    rows = await db.products.find({"template_id": tid, "status": {"$ne": "inactive"},
                                   "special_order_id": {"$in": [None, ""]},
                                   "$or": [{"grade": "A"}, {"variant_attrs.grade": "A"}]}, _PROJ).to_list(500)
    if not rows:
        return {"product": None, "why": "induk belum punya SKU Grade A — harga diisi PIC"}
    col = _color(src)
    same = [r for r in rows if col and _color(r) == col]
    if same:
        return {"product": same[0], "how": "Grade A induk, warna sama"}
    pick = sorted(rows, key=lambda r: (-float(r.get("price") or 0), r.get("sku") or ""))[0]
    return {"product": pick, "how": "Grade A induk (harga tertinggi sekeluarga)"}


async def parent_price(od: Dict[str, Any], item: Dict[str, Any], target: Optional[Dict[str, Any]],
                       factors: Dict[str, float]) -> Optional[Dict[str, Any]]:
    """Harga Grade A induk per SATUAN DASAR produk hasil (rantai harga pelanggan). None = tanpa induk."""
    ref = await parent_reference(item)
    if ref is None:
        return None
    p = ref.get("product")
    if not p:
        return {"error": ref.get("why", "")}
    from services import customer_price_service as cps
    res = (await cps.resolve_many(od.get("entity_id"), od.get("customer_id"), [p["id"]], {p["id"]: p})).get(p["id"]) or {}
    ref_price = float(res.get("price") or p.get("price") or 0)
    if ref_price <= 0:
        return {"error": f"SKU Grade A acuan {p.get('sku')} belum punya harga jual — harga diisi PIC"}
    price = ref_price
    tb, rb = (target or {}).get("base_unit") or "", p.get("base_unit") or ""
    if target and tb and rb and tb.lower() != rb.lower():
        from fastapi import HTTPException
        from services.uom_service import to_base
        try:   # 1 satuan dasar produk hasil = k satuan dasar SKU acuan
            price = ref_price * to_base(p, 1.0, tb, factors, precision=6)
        except HTTPException as exc:
            return {"error": f"satuan {tb} tidak bisa dikonversi ke {rb} (SKU acuan {p.get('sku')}): {exc.detail}"}
    return {"final_base": round(price, 4), "ref_product_id": p["id"], "ref_sku": p.get("sku", ""),
            "ref_price": round(ref_price, 2), "ref_unit": rb, "price_source": res.get("source", "global"),
            "how": ref.get("how", "")}


def clean_prices(raw: Optional[Dict[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k, v in (raw or {}).items():
        if v in (None, ""):
            continue
        try:
            f = round(float(v), 2)
        except (TypeError, ValueError) as exc:
            raise NegoError(f"Harga PIC tidak valid: {v}") from exc
        if f <= 0:
            raise NegoError("Harga PIC harus lebih dari 0.")
        out[str(k)] = f
    return out


async def line_basis(od: Dict[str, Any], item: Dict[str, Any], prod: Optional[Dict[str, Any]], *, cost: float,
                     margin: float, factor: float, factors: Dict[str, float],
                     pic_unit_price: Optional[float] = None) -> Dict[str, Any]:
    """Harga final per satuan dasar produk hasil + asal-usulnya. `pic_unit_price` = harga PIC per SATUAN ITEM."""
    comparator = round(cost * (1 + margin / 100.0), 2) if cost else 0.0
    par = await parent_price(od, item, prod, factors) if item else None
    out: Dict[str, Any] = {"comparator_unit_price": comparator, "has_parent": bool(par), "ref_sku": "",
                           "ref_product_id": "", "ref_price": 0.0, "ref_unit": "", "basis_note": "", "pic_unit_price": None}
    if par and not par.get("error"):
        out.update({"basis": "parent_grade_a", "final_unit_price": par["final_base"], "ref_sku": par["ref_sku"],
                    "ref_product_id": par["ref_product_id"], "ref_price": par["ref_price"], "ref_unit": par["ref_unit"],
                    "basis_note": f"{par['how']} · sumber harga {par['price_source']}"})
    elif pic_unit_price and factor:
        out.update({"basis": "pic", "final_unit_price": round(pic_unit_price / factor, 4), "pic_unit_price": pic_unit_price,
                    "basis_note": (par or {}).get("error", "")})
    else:
        out.update({"basis": "cost_margin", "final_unit_price": comparator,
                    "basis_note": (par or {}).get("error", "") or "item tanpa induk — PIC Special Order menentukan harga"})
    out["basis_label"] = BASIS_LABEL[out["basis"]]
    out["needs_pic"] = out["basis"] == "cost_margin"
    out["loss"] = bool(cost and out["final_unit_price"] and out["final_unit_price"] < cost - 0.005)
    out["margin_actual_pct"] = round((out["final_unit_price"] / cost - 1) * 100, 2) if cost and out["final_unit_price"] else None
    return out


def loss_lines(pricing: Dict[str, Any]) -> List[str]:
    rows = pricing.get("items") if pricing.get("mode") == "items" else [pricing]
    return [f"{r.get('description') or r.get('product_sku') or 'item'}: {rupiah(r.get('final_unit_price') or 0)} < kontrak "
            f"{rupiah(r.get('cost_price') or 0)}" for r in rows or [] if r.get("loss")]


async def warn_loss(od: Dict[str, Any], pricing: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """P2-K4 — harga Grade A induk di bawah biaya kontrak tidak diblokir; Manajer diberi peringatan rugi."""
    rows = loss_lines(pricing)
    if not rows:
        return
    try:
        from services import notification_service as notif
        await notif.create_addressed(
            roles=("manager",), entity_id=od.get("entity_id", ""), notif_type="special_order_price_loss",
            title=f"Harga {od.get('number')} di bawah biaya kontrak",
            body=f"Dikunci {actor.get('name', '')} · {od.get('customer_name', '')}. " + "; ".join(rows),
            severity="warning", link="special-orders", ref=f"odloss:{od['id']}")
    except Exception:  # noqa: BLE001 — peringatan tidak boleh menggagalkan kunci harga
        pass


# ─── Nego (harga khusus baris SO tertaut) ────────────────────────────────────
NEGO_KEYS = ("id", "status", "requested_price", "normal_price", "reason", "requested_by", "requested_by_id",
             "requested_at", "decided_by", "decided_at", "decision_notes", "special_order_item_id", "product_id",
             "product_name", "previous_status")


async def nego_entries(od: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    so_id = od.get("linked_sales_order_id") or ""
    if not so_id:
        return [], None
    so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0, "id": 1, "number": 1, "status": 1, "items": 1,
                                                      "pending_approvals": 1})
    if not so or so.get("status") == "cancelled":
        return [], so
    rows = [{k: p.get(k) for k in NEGO_KEYS} for p in so.get("pending_approvals") or [] if p.get("type") == "special_price"]
    return rows, so


async def nego_block(od: Dict[str, Any]) -> str:
    rows, _ = await nego_entries(od)
    if any(r["status"] == "pending" for r in rows):
        return "Nego harga belum diputus Manajer — pengadaan menunggu keputusan nego."
    if any(r["status"] == "rejected" for r in rows):
        return ("Nego harga ditolak Manajer dan belum dijawab sales (ajukan harga lain / lanjut harga normal / "
                "batalkan) — pengadaan menunggu.")
    return ""


async def nego_view(od: Dict[str, Any]) -> Dict[str, Any]:
    rows, so = await nego_entries(od)
    return {"so_id": (so or {}).get("id", ""), "so_number": (so or {}).get("number", ""),
            "so_status": (so or {}).get("status", ""), "entries": rows, "block": await nego_block(od),
            "lines": [{"index": i, "special_order_item_id": it.get("special_order_item_id", ""),
                       "product_id": it.get("product_id"), "product_name": it.get("product_name", ""),
                       "quantity": it.get("quantity"), "unit": it.get("unit"), "price": it.get("price"),
                       "price_source": it.get("price_source", "")}
                      for i, it in enumerate((so or {}).get("items") or []) if it.get("special_order_price")]}


def _sell_factor(item: Dict[str, Any]) -> float:
    q, bq = float(item.get("quantity") or 0), float(item.get("base_quantity") or 0)
    return bq / q if q and bq else 1.0


def nego_floor(item: Dict[str, Any]) -> Optional[float]:
    """Lantai nego (P2-K3) per satuan baris SO = harga kontrak per satuan dasar × faktor satuan baris."""
    if not item.get("special_order_price"):
        return None
    cost = float(item.get("cost_price") or 0)
    return round(cost * _sell_factor(item), 2) if cost > 0 else None


async def assert_nego_allowed(order: Dict[str, Any], item: Dict[str, Any], requested: float,
                              actor: Dict[str, Any]) -> None:
    floor = nego_floor(item)
    if floor is None or requested >= floor - 0.005:
        return
    from dependencies import has_permission
    show = await has_permission(actor, "od_pricing", "view_cost")
    raise NegoError("Harga nego di bawah harga kontrak supplier (lantai nego"
                    + (f" {rupiah(floor)}/{item.get('unit') or ''}" if show else "") + ") — ajukan harga yang lebih tinggi.")


async def apply_nego(order: Dict[str, Any], idx: int, entry: Dict[str, Any], actor: Dict[str, Any],
                     old_price: float) -> None:
    """P2.3 — nego ACC: harga baris SO baru → rincian harga OD, total OD, dan harga SKU eksklusif ikut berubah."""
    item = (order.get("items") or [])[idx]
    od_id = order.get("source_special_order_id") or ""
    if not od_id or not item.get("special_order_price"):
        return
    od = await db.special_orders.find_one({"id": od_id}, {"_id": 0})
    pr = (od or {}).get("pricing") or {}
    if not od or not pr.get("locked"):
        return
    new_price = float(entry.get("requested_price") or 0)
    final_base = round(new_price / _sell_factor(item), 4)
    neg = {"price_per_unit": new_price, "final_unit_price": final_base, "previous_price_per_unit": old_price,
           "special_price_id": entry.get("ref_id", ""), "approval_id": entry.get("id", ""),
           "requested_by": entry.get("requested_by", ""), "approved_by": actor.get("name", ""), "approved_at": now_iso()}
    from services import special_order_phase2 as p2
    if pr.get("mode") == "items":
        lines = list(pr.get("items") or [])
        ln = next((x for x in lines if x.get("item_id") == item.get("special_order_item_id")
                   and x.get("product_id") == item.get("product_id")), None)
        if not ln:
            return
        cost = float(ln.get("cost_price") or 0)
        ln.update({"final_unit_price": final_base, "price_per_unit": new_price,
                   "total": round(new_price * float(ln.get("quantity") or 0), 2), "negotiated": neg,
                   "basis": "negotiated", "basis_label": BASIS_LABEL["negotiated"],
                   "loss": bool(cost and final_base < cost - 0.005),
                   "margin_actual_pct": round((final_base / cost - 1) * 100, 2) if cost else None})
        total = round(sum(float(x.get("total") or 0) for x in lines), 2)
        sets = {"pricing.items": lines, "pricing.total": total, "total_amount": total}
        new_pricing = {**pr, "items": lines, "total": total}
    else:
        cost = float(pr.get("cost_price") or 0)
        total = round(new_price * float(item.get("quantity") or 0), 2)
        sets = {"pricing.final_unit_price": final_base, "pricing.total": total, "pricing.negotiated": neg,
                "pricing.basis": "negotiated", "pricing.basis_label": BASIS_LABEL["negotiated"],
                "pricing.loss": bool(cost and final_base < cost - 0.005), "final_price": final_base, "total_amount": total}
        new_pricing = {**pr, "final_unit_price": final_base, "total": total}
    await db.special_orders.update_one({"id": od_id}, {
        "$set": {**sets, "updated_at": now_iso()},
        "$push": {"status_history": {"status": od.get("status"), "timestamp": now_iso(), "user": actor.get("email", ""),
                                     "note": f"Nego harga ACC {actor.get('name', '')}: {item.get('product_name', '')} "
                                             f"{rupiah(old_price)} → {rupiah(new_price)}/{item.get('unit', '')}"}}})
    if pr.get("mode") == "items":
        await p2._sync_item_skus(od, new_pricing)  # noqa: SLF001 — sumber sinkron SKU yang sama dengan kunci harga
    else:
        await p2._sync_od_sku(od, new_pricing, pr.get("product_id") or od.get("linked_product_id") or "")  # noqa: SLF001


# ─── P2.5 — visibilitas biaya ────────────────────────────────────────────────
COST_KEYS = frozenset({"cost_price", "margin_pct", "default_margin_pct", "supplier_id", "supplier_name",
                       "contract_number", "contract_id", "harga_pokok", "rnd_supplier", "supplier_colors",
                       "partner_name", "unit_cost", "comparator_unit_price", "margin_actual_pct", "loss", "loss_lines",
                       "revalidation_ref", "eta_warning"})
SO_LINE_KEYS = frozenset({"cost_price", "margin_pct", "unit_cost"})
OD_PATH = "/api/special-orders"
SO_PATH = "/api/sales-orders"
_cache: Dict[str, Tuple[float, bool]] = {}
_TTL = 15.0


def redact_od(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in COST_KEYS:
                continue
            if k == "decision" and isinstance(v, dict):
                v = {kk: vv for kk, vv in v.items() if kk not in ("price", "contract_number", "supplier_id", "supplier_name")}
            elif k == "grand_total" and "po_number" in obj:
                continue
            out[k] = redact_od(v)
        return out
    if isinstance(obj, list):
        return [redact_od(v) for v in obj]
    return obj


def redact_so(obj: Any) -> Any:
    if isinstance(obj, dict):
        od_line = bool(obj.get("special_order_price"))
        return {k: redact_so(v) for k, v in obj.items() if not (od_line and k in SO_LINE_KEYS)}
    if isinstance(obj, list):
        return [redact_so(v) for v in obj]
    return obj


async def can_view_cost_token(token: str) -> bool:
    if not token:
        return True   # tanpa sesi → endpoint menolak sendiri (401); jangan ubah respons galat
    hit = _cache.get(token)
    now = time.time()
    if hit and hit[0] > now:
        return hit[1]
    session = await db.sessions.find_one({"token": token}, {"_id": 0, "user_id": 1})
    user = await db.users.find_one({"id": (session or {}).get("user_id")}, {"_id": 0, "role": 1}) if session else None
    ok = True
    if user:
        from dependencies import has_permission
        ok = await has_permission(user, "od_pricing", "view_cost")
    _cache[token] = (now + _TTL, ok)
    return ok


class ODCostVisibilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        is_od, is_so = path.startswith(OD_PATH), path.startswith(SO_PATH)
        if not (is_od or is_so):
            return await call_next(request)
        from dependencies import extract_token
        if await can_view_cost_token(extract_token(request)):
            return await call_next(request)
        response = await call_next(request)
        if "application/json" not in response.headers.get("content-type", ""):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            data = json.loads(body)
            content = json.dumps(redact_od(data) if is_od else redact_so(data), ensure_ascii=False, default=str).encode()
        except ValueError:
            content = body
        out = Response(content=content, status_code=response.status_code)
        out.raw_headers = [h for h in response.raw_headers if h[0].lower() != b"content-length"] + [
            (b"content-length", str(len(content)).encode()), (b"x-kn-od-cost-hidden", b"1")]
        return out
