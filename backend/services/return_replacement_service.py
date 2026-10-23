"""LN-090 T02/T03 — pesanan pengganti nyata untuk retur tukar barang (KLR-03/04/05, owner 2026-10-19).

- Kewajiban pengganti = qty AKTUAL hasil QC (accepted_qty) dalam yard (yard = source of truth).
- Retur diselesaikan dulu sebagai Store Credit (Credit Note harga transaksi awal) → saldo customer.
- Pesanan pengganti = SO biasa (alokasi, QC, picking, SJ, POD memakai alur yang sama) dengan harga
  transaksi asal (harga khusus sekali pakai yang tertaut ke retur) dan flag QC mengikuti SO awal.
- Saldo retur dipakai ke SO pengganti: pengganti LEBIH → selisih tetap ditagih; KURANG → sisa saldo
  tetap milik customer (boleh dipakai atau di-refund lewat alur saldo).
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from core_utils import now_iso
from db import db
from services import price_approval_service as pas
from services.return_compensation_service import _net_unit_price

QC_UNIT = "yard"


async def _yard_factor(prod: Dict[str, Any]) -> float:
    """Qty satuan dasar per 1 yard."""
    from services.roll_service import to_base_qty
    if (prod.get("base_unit") or "").lower() == QC_UNIT:
        return 1.0
    return float(await to_base_qty(prod, 1.0, QC_UNIT))


async def _sold_grade(it: Dict[str, Any], return_id: str = "") -> str:
    """Grade saat dijual. UAT 23 Okt — penyelesaian Store Credit menurunkan grade roll ke hasil QC (mis. A→B) tanpa
    `regraded_from`, sehingga pengganti dulu mencari stok grade B (tidak ada) padahal pelanggan membeli grade A.
    Urutan sumber: `return_history[retur ini].grade_before` → `regraded_from` → grade roll (`return_restore` tidak dipakai:
    tidak menyebut retur mana, bisa milik retur lain atas roll yang sama)."""
    ids = it.get("roll_ids") or []
    async for r in db.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0, "grade": 1, "regraded_from": 1, "return_history": 1}):
        hist = next((h for h in reversed(r.get("return_history") or [])
                     if return_id and h.get("return_id") == return_id), None) or {}
        g = hist.get("grade_before") or r.get("regraded_from") or r.get("grade") or ""
        if g:
            return g
    return it.get("grade") or ""


def _exchange_rolls(ret: Dict[str, Any]) -> Dict[str, float]:
    """UAT 23 Okt — penyelesaian per roll: roll Tukar Barang yang BELUM dibuatkan pengganti → qty aktual QC."""
    done = set(ret.get("replaced_roll_ids") or [])
    out: Dict[str, float] = {}
    for it in ret.get("items", []):
        res = (it.get("inspection") or {}).get("roll_results") or {}
        for rid in it.get("roll_ids") or []:
            o = (ret.get("roll_outcomes") or {}).get(rid) or {}
            if o.get("outcome") == "exchange" and rid not in done:
                out[rid] = float(o.get("qty_stock") or (res.get(rid) or {}).get("actual_qty") or 0)
    return out


async def obligation(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
    order = await db.sales_orders.find_one({"id": ret["order_id"]}, {"_id": 0}) or {}
    rows = []
    ex = _exchange_rolls(ret) if ret.get("roll_outcomes") else None
    for it in ret.get("items", []):
        if ex is not None:   # per roll: hanya roll Tukar Barang (qty aktual QC) yang menjadi kewajiban pengganti
            rids = [r for r in it.get("roll_ids") or [] if r in ex]
            if not rids:
                continue
            pid = it.get("product_id")
            prod = await db.products.find_one({"id": pid}, {"_id": 0}) or {}
            base_qty = round(sum(ex[r] for r in rids), 4)
            try:
                f, conv_err = await _yard_factor(prod), ""
            except Exception as e:  # noqa: BLE001
                f, conv_err = 0.0, str(getattr(e, "detail", e))
            price = await _net_unit_price(order, pid)
            res = (it.get("inspection") or {}).get("roll_results") or {}
            rows.append({"product_id": pid, "product_name": it.get("product_name", ""), "unit_base": prod.get("base_unit", ""),
                         "qty_base": base_qty, "qty_yard": round(base_qty / f, 2) if f else None, "conversion_error": conv_err,
                         "grade": "/".join(sorted({(res.get(r) or {}).get("grade", "") for r in rids} - {""})),
                         "sold_grade": await _sold_grade({**it, "roll_ids": rids}, ret.get("id", "")), "roll_ids": rids,
                         "unit_price_base": price, "value": round(base_qty * price, 2)})
            continue
        pid = it.get("product_id")
        if it.get("settle_outcome") == "reject":
            continue
        insp = it.get("inspection") or {}
        base_qty = float(insp.get("accepted_qty", it.get("quantity_returned", 0)) or 0)
        prod = await db.products.find_one({"id": pid}, {"_id": 0}) or {}
        try:
            f, conv_err = await _yard_factor(prod), ""
        except Exception as e:  # noqa: BLE001 — faktor yard belum ada di master produk/UoM
            f, conv_err = 0.0, str(getattr(e, "detail", e))
        price = await _net_unit_price(order, pid)
        rows.append({"product_id": pid, "product_name": it.get("product_name", ""), "unit_base": prod.get("base_unit", ""),
                     "qty_base": round(base_qty, 4), "qty_yard": round(base_qty / f, 2) if f else None, "conversion_error": conv_err,
                     "grade": insp.get("grade", ""), "sold_grade": await _sold_grade(it, ret.get("id", "")), "unit_price_base": price, "value": round(base_qty * price, 2)})
    return rows


async def create(ret: Dict[str, Any], items: List[Dict[str, Any]], request, actor: Dict[str, Any]) -> Dict[str, Any]:
    from routers.sales_orders import create_order
    from schemas import SalesOrderCreate
    per_roll = bool(ret.get("roll_outcomes"))
    if per_roll:   # UAT 23 Okt — penyelesaian per roll: roll Tukar Barang yang belum dibuatkan pengganti
        if not ret.get("exchange_pending") or not _exchange_rolls(ret):
            raise ValueError("Tidak ada roll Tukar Barang yang menunggu pesanan pengganti.")
    else:
        if ret.get("return_type") != "penggantian":
            raise ValueError("Pesanan pengganti hanya untuk retur jenis 'penggantian' (tukar barang).")
        if ret.get("status") != "credit_settled":
            raise ValueError("Selesaikan retur sebagai Store Credit dulu (QC selesai) — nilainya menjadi saldo pengganti.")
        if ret.get("replacement_order_id"):
            raise ValueError(f"Pesanan pengganti sudah dibuat: {ret.get('replacement_order_number')}")
    order = await db.sales_orders.find_one({"id": ret["order_id"]}, {"_id": 0}) or {}
    customer = await db.customers.find_one({"id": ret.get("customer_id")}, {"_id": 0}) or {}
    obl = {r["product_id"]: r for r in await obligation(ret)}
    lines, approvals = [], []
    until = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    for it in items or []:
        pid, qty_yard = it.get("product_id"), float(it.get("qty_yard") or 0)
        if pid not in obl:
            raise ValueError("Pengganti wajib artikel/warna yang sama dengan barang yang diretur.")
        if qty_yard <= 0:
            raise ValueError("Qty pengganti (yard) harus > 0")
        if obl[pid]["conversion_error"]:
            raise ValueError(obl[pid]["conversion_error"])
        prod = await db.products.find_one({"id": pid}, {"_id": 0}) or {}
        qty_base = round(qty_yard * await _yard_factor(prod), 2)
        appr = pas.build_doc(customer=customer, product=prod, entity_id=ret.get("entity_id", ""),
                             requested_price=obl[pid]["unit_price_base"], requester=actor, status="approved",
                             reason=f"Harga transaksi asal untuk pengganti retur {ret.get('number', '')} (KLR-05)",
                             valid_until=until, source="return_replacement",
                             extra={"replacement_return_id": ret["id"], "approved_by_name": "sistem (KLR-05)",
                                    "decided_at": now_iso()})
        await pas.insert(appr)
        approvals.append(appr["id"])
        lines.append({"product_id": pid, "quantity": qty_base, "unit": prod.get("base_unit") or "yard",
                      "price_approval_id": appr["id"], "required_grade": obl[pid].get("sold_grade", "")})
    if not lines:
        raise ValueError("Minimal satu baris pengganti")
    qc_mode = (order.get("qc_request") or {}).get("mode") or "none"
    method = (order.get("fulfillment_method") or "kirim").strip().lower()
    # Cek UI UAT v3 (S15) — SO asal tunai: saldo retur tak bisa dipakai di order tanpa piutang → pelanggan ditagih ulang
    # penuh untuk barang tukar. Pengganti memakai CBD: saldo retur melunasi di muka, selisih dibayar sebelum kirim.
    from services.customer_service import NON_AR_METHODS, order_payment_method
    term = "CBD" if order_payment_method(order) in NON_AR_METHODS else order.get("payment_term_code", "")
    payload = SalesOrderCreate(customer_id=ret["customer_id"], shipping_address_id=order.get("shipping_address_id", ""),
                               items=lines, entity_id=ret.get("entity_id", ""), qc_request=qc_mode,
                               qc_sample_pct=float((order.get("qc_request") or {}).get("sample_pct") or 10),
                               fulfillment_method=method,
                               # Cek UI UAT v3 (S15) — SO asal "ambil sendiri": pengganti dulu gagal (tanggal ambil kosong).
                               pickup_date=(datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat() if method == "ambil" else "",
                               payment_term_code=term)
    try:
        so = await create_order(payload, request)
    finally:   # harga khusus sekali pakai: tak bisa dipakai SO lain
        await db.price_approvals.update_many({"id": {"$in": approvals}}, {"$set": {"scope": "order", "valid_until": now_iso()}})
    so_id = so.get("id")
    await db.price_approvals.update_many({"id": {"$in": approvals}}, {"$set": {"so_id": so_id}})
    link = {"return_id": ret["id"], "return_number": ret.get("number", ""), "obligation": list(obl.values())}
    await db.sales_orders.update_one({"id": so_id}, {"$set": {"replacement_for_return": link}})
    so_doc = await db.sales_orders.find_one({"id": so_id}, {"_id": 0}) or so
    applied = await _apply_credit(ret, so_doc, actor)
    summary = _summary(list(obl.values()), so_doc, applied)
    upd: Dict[str, Any] = {"replacement_order_id": so_id, "replacement_order_number": so_doc.get("number", ""),
                           "replacement_summary": summary, "updated_at": now_iso()}
    push: Dict[str, Any] = {}
    if per_roll:
        upd.update({"exchange_pending": False,
                    "exchange_credit_open": round(max(float(ret.get("exchange_credit_open") or 0) - float(applied.get("applied") or 0), 0.0), 2)})
        push = {"$addToSet": {"replaced_roll_ids": {"$each": [r for x in obl.values() for r in x.get("roll_ids") or []]}},
                "$push": {"replacement_orders": {"order_id": so_id, "order_number": so_doc.get("number", ""), "at": now_iso(),
                                                 "credit_applied": applied.get("applied", 0.0)}}}
    await db.sales_returns.update_one({"id": ret["id"]}, {"$set": upd, **push})
    from services import doc_refs_service as refs
    await refs.safe_link(("sales_order", so_id), ("sales_return", ret["id"]), "parent", note="pesanan pengganti retur")
    return {"order": {"id": so_id, "number": so_doc.get("number", "")}, "summary": summary}


async def _apply_credit(ret: Dict[str, Any], so: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import store_credit_service as sc
    if ret.get("roll_outcomes"):   # per roll: saldo yang terbit dari roll Tukar Barang (bukan saldo cutloss/diskon)
        open_credit = float(ret.get("exchange_credit_open") or 0)
        bal = await sc.balance(ret["customer_id"], ret.get("entity_id", ""))
        info = {"issued": open_credit, "balance": bal, "basis": "per_roll"}
    else:
        info = await sc.issued_from_return(ret["id"])
    avail = min(float(info.get("issued") or 0), float(info.get("balance") or 0))
    amount = round(min(avail, float(so.get("grand_total") or 0)), 2)
    if amount <= 0:
        return {"applied": 0.0, "issued": float(info.get("issued") or 0), "basis": info.get("basis", ""),
                "error": "Saldo retur tidak tersedia" + (" — nilai tukar sudah memotong tagihan SO asal yang belum lunas"
                                                         if info.get("basis") == "per_roll" else "")}
    try:
        r = await sc.redeem(customer_id=ret["customer_id"], entity_id=ret.get("entity_id"), amount=amount,
                            allocations=[{"order_id": so["id"], "amount": amount}], actor=actor,
                            note=f"Saldo retur {ret.get('number', '')} untuk pesanan pengganti",
                            ref_type="sales_return_replacement", ref_id=ret["id"], ref_number=ret.get("number", ""))
        return {"applied": amount, "issued": float(info.get("issued") or 0), "redemption_number": r.get("number", ""),
                "basis": info.get("basis", "")}
    except Exception as e:  # noqa: BLE001 — SO tetap sah; saldo dapat dipakai manual
        return {"applied": 0.0, "issued": float(info.get("issued") or 0), "basis": info.get("basis", ""),
                "error": str(getattr(e, "detail", None) or e)}


async def on_replacement_cancelled(so: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """SO pengganti dibatalkan → saldo retur yang dipakai dikembalikan & retur boleh membuat pengganti baru."""
    from services import store_credit_service as sc
    rid = (so.get("replacement_for_return") or {}).get("return_id")
    async for red in db.store_credit_redemptions.find({"allocations.order_id": so["id"], "status": {"$ne": "void"}},
                                                      {"_id": 0, "id": 1}):
        await sc.reverse_redemption(red["id"], reason=f"SO pengganti {so.get('number', '')} dibatalkan", actor=actor)
    if rid:
        ret = await db.sales_returns.find_one({"id": rid}, {"_id": 0, "roll_outcomes": 1, "replacement_orders": 1,
                                                            "replaced_roll_ids": 1, "exchange_credit_open": 1}) or {}
        per_roll: Dict[str, Any] = {}
        if ret.get("roll_outcomes"):   # UAT 23 Okt — roll Tukar Barang kembali menunggu pengganti, saldo tukar pulih
            rep = next((x for x in ret.get("replacement_orders") or [] if x.get("order_id") == so["id"]), {})
            obl_rolls = [r for r in (so.get("replacement_for_return") or {}).get("roll_ids") or []] or \
                [r for x in (so.get("replacement_for_return") or {}).get("obligation") or [] for r in x.get("roll_ids") or []]
            per_roll = {"exchange_pending": True,
                        "exchange_credit_open": round(float(ret.get("exchange_credit_open") or 0) + float(rep.get("credit_applied") or 0), 2),
                        "replaced_roll_ids": [r for r in ret.get("replaced_roll_ids") or [] if r not in set(obl_rolls)]}
        await db.sales_returns.update_one({"id": rid, "replacement_order_id": so["id"]}, {
            "$set": {"replacement_order_id": "", "replacement_order_number": "", "updated_at": now_iso(), **per_roll},
            "$unset": {"replacement_summary": ""},
            "$push": {"replacement_history": {"order_id": so["id"], "order_number": so.get("number", ""),
                                              "cancelled_at": now_iso(), "by": actor.get("name", "")}}})


def _summary(obl: List[Dict[str, Any]], so: Dict[str, Any], applied: Dict[str, Any]) -> Dict[str, Any]:
    issued = float(applied.get("issued") or 0)
    # Per roll: saldo tukar bisa memang 0 (nilai tukar memotong tagihan SO asal) — jangan jatuh ke nilai kewajiban.
    credit = round(issued if applied.get("basis") == "per_roll" else (issued or sum(r["value"] for r in obl)), 2)
    total = round(float(so.get("grand_total") or 0), 2)
    diff = round(total - float(applied.get("applied") or 0), 2)
    return {"obligation_yard": round(sum(r["qty_yard"] or 0 for r in obl), 2), "obligation_value": credit,
            "replacement_total": total, "credit_applied": applied.get("applied", 0.0),
            "to_bill": max(diff, 0.0), "remaining_credit": round(max(credit - float(applied.get("applied") or 0), 0.0), 2),
            "credit_error": applied.get("error", ""), "redemption_number": applied.get("redemption_number", ""),
            "rule": "Lebih → selisih ditagih (harga asal); kurang → sisa saldo customer (pakai/refund)."}
