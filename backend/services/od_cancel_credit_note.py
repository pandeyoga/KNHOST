"""Keputusan owner 2026-10-21 — batal item Pesanan Khusus pada SO yang SUDAH TERBIT → NOTA KREDIT otomatis.

SO terbit (`amendment_service.is_issued`: Faktur Pajak aktif, pembayaran masuk, sudah dikirim, pendapatan
dijurnal) dulu menolak batal item ("koreksi lewat Finance"). Kini baris yang barangnya BELUM keluar gudang tetap
dikeluarkan dari SO (jalur fisik `so_line_cancel_service`), lalu lahir nota kredit bernomor berstatus
**menunggu Finance** (`pending_finance`) yang mencatat nilai yang dibatalkan. Pemegang izin
`finance_amendment.review_credit_note` (bawaan Finance, Manager, Admin; diatur di matriks) boleh:
  * `adjust` — mengoreksi nilai nota (tidak melebihi nilai batal; alasan wajib; jejak koreksi tersimpan),
  * `issue`  — menerbitkan nota, atau
  * `void`   — membatalkan nota (mis. disepakati tanpa pengembalian), alasan wajib.

Akuntansi saat terbit (default implementer, dicatat untuk direview):
  * Pendapatan diakui per Surat Jalan dan uang sebelum kirim = Uang Muka Pelanggan (2-1400). Baris yang dibatalkan
    belum dikirim → belum ada pendapatan/piutang untuknya → **tanpa jurnal**; kelebihan bayar tetap uang muka
    pelanggan (dikembalikan/dipakai lewat alur Uang Masuk yang ada).
  * Bila pendapatan pesanan ini SUDAH diakui di tingkat pesanan (jurnal historis `sales_order`) → jurnal koreksi
    seperti nota amandemen (`gl_service.post_amendment_credit_note`): Dr Pendapatan + PPN / Cr Piutang (sebesar sisa
    tagihan sebelum batal) + Cr Saldo Kredit pelanggan untuk sisanya.
"""
from typing import Any, Dict, Optional

from fastapi import HTTPException

from core_utils import new_id, next_doc_number, now_iso, rupiah
from db import db

SOURCE = "od_item_cancel"


def _paid(order: Dict[str, Any]) -> float:
    from services.customer_service import _order_paid
    return round(max(_order_paid(order), float(order.get("paid_total") or 0)), 2)


async def create(order: Dict[str, Any], after: Dict[str, Any], line: Dict[str, Any], reason: str,
                 actor_name: str, issued_reason: str, od_item_id: str) -> Dict[str, Any]:
    """`order` = SO SEBELUM batal; `after` = total SO sesudah baris keluar (hasil compute_order_pricing)."""
    from services import gl_service
    entity_id = order.get("entity_id") or ""
    before_gt, after_gt = float(order.get("grand_total") or 0), float(after.get("grand_total") or 0)
    gross = round(before_gt - after_gt, 2)
    ppn = round(float(order.get("ppn_amount") or 0) - float(after.get("ppn_amount") or 0), 2)
    paid = _paid(order)
    number = await next_doc_number("credit_notes", "number", "CN-", entity_id=entity_id or None)
    now = now_iso()
    doc = {
        "id": new_id("cn"), "number": number, "kind": "credit_note", "source": SOURCE, "status": "pending_finance",
        "order_id": order["id"], "order_number": order.get("number", ""),
        "customer_id": order.get("customer_id"), "customer_name": order.get("customer_name", ""), "entity_id": entity_id,
        "special_order_id": order.get("source_special_order_id") or "", "special_order_item_id": od_item_id,
        "reason_code": SOURCE, "reason_label": "Batal item Pesanan Khusus", "note": reason,
        "issued_reason": issued_reason,
        "lines": [{"product_id": line.get("product_id"), "product_name": line.get("product_name"),
                   "quantity": line.get("quantity"), "unit": line.get("unit"), "price": line.get("price"),
                   "subtotal": line.get("line_total") or line.get("subtotal")}],
        "computed_gross": gross, "computed_ppn": ppn,
        "gross_amount": gross, "ppn_amount": ppn, "net_amount": round(gross - ppn, 2),
        "direction": "decrease", "grand_total_before": before_gt, "grand_total_after": after_gt,
        "paid_total": paid, "open_before": round(max(before_gt - paid, 0.0), 2),
        "excess_payment": round(max(paid - after_gt, 0.0), 2),
        "revenue_recognized": bool(await gl_service._already_posted("sales_order", order["id"])),
        "corrections": [], "created_by": actor_name, "created_at": now, "updated_at": now,
    }
    await db.credit_notes.insert_one(dict(doc))
    from services import doc_refs_service as _refs
    await _refs.safe_link(("credit_note", doc["id"]), ("sales_order", order["id"]), "corrects", note=doc["reason_label"])
    try:
        from services import notification_service as notif
        await notif.create_addressed(
            roles=("finance",), entity_id=entity_id, notif_type="od_cancel_credit_note", severity="warning",
            title=f"Nota kredit {number} menunggu Finance",
            body=(f"{order.get('number')} sudah terbit ({issued_reason}); item {line.get('product_name') or ''} dibatalkan "
                  f"— nilai {rupiah(gross)}" + (f", kelebihan bayar {rupiah(doc['excess_payment'])}" if doc["excess_payment"] else "")
                  + ". Tinjau, koreksi bila perlu, lalu terbitkan."),
            link="orders", ref=doc["id"])
    except Exception:  # noqa: BLE001 — notifikasi tidak boleh menggagalkan batal item
        pass
    return doc


async def review(cn_id: str, action: str, body: Dict[str, Any], actor: Dict[str, Any], ctx) -> Dict[str, Any]:
    from entity_scope import assert_entity_access
    doc = await db.credit_notes.find_one({"id": cn_id}, {"_id": 0})
    if not doc or doc.get("source") != SOURCE:
        raise HTTPException(status_code=404, detail="Nota kredit batal item tidak ditemukan.")
    assert_entity_access(doc, "credit_notes", ctx)
    if doc.get("status") != "pending_finance":
        raise HTTPException(status_code=409, detail=f"Nota {doc.get('number')} sudah berstatus '{doc.get('status')}'.")
    who, now = actor.get("name", ""), now_iso()
    note = (body.get("note") or "").strip()
    if action == "adjust":
        if len(note) < 5:
            raise HTTPException(status_code=400, detail="Alasan koreksi wajib (minimal 5 huruf).")
        try:
            gross = round(float(body.get("gross_amount")), 2)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Nilai nota harus angka.") from exc
        cap = float(doc.get("computed_gross") or 0)
        if gross <= 0 or gross > cap + 0.005:
            raise HTTPException(status_code=400, detail=(
                f"Nilai nota harus lebih dari 0 dan tidak melebihi nilai baris yang dibatalkan ({rupiah(cap)})."))
        ppn = round(float(doc.get("computed_ppn") or 0) * gross / cap, 2) if cap else 0.0
        upd = {"$set": {"gross_amount": gross, "ppn_amount": ppn, "net_amount": round(gross - ppn, 2), "updated_at": now},
               "$push": {"corrections": {"from": doc.get("gross_amount"), "to": gross, "by": who, "at": now, "reason": note}}}
    elif action == "issue":
        upd = {"$set": {"status": "issued", "issued_by": who, "issued_at": now, "issue_note": note, "updated_at": now}}
    elif action == "void":
        if len(note) < 5:
            raise HTTPException(status_code=400, detail="Alasan pembatalan nota wajib (minimal 5 huruf).")
        upd = {"$set": {"status": "void", "void_reason": note, "voided_by": who, "voided_at": now, "updated_at": now}}
    else:
        raise HTTPException(status_code=400, detail="Aksi harus adjust, issue, atau void.")
    res = await db.credit_notes.update_one({"id": cn_id, "status": "pending_finance"}, upd)
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Nota baru saja diproses pengguna lain. Muat ulang.")
    if action == "issue":
        await _post_if_revenue_recognized(await db.credit_notes.find_one({"id": cn_id}, {"_id": 0}))
    return await db.credit_notes.find_one({"id": cn_id}, {"_id": 0})


async def _post_if_revenue_recognized(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Jurnal hanya bila pendapatan pesanan sudah diakui di tingkat pesanan (historis). Idempoten per nota."""
    if not doc.get("revenue_recognized"):
        await db.credit_notes.update_one({"id": doc["id"]}, {"$set": {
            "accounting": "no_journal_revenue_not_recognized",
            "excess_handling": "customer_advance" if doc.get("excess_payment") else ""}})
        return None
    from services import gl_service, store_credit_service
    gross = float(doc.get("gross_amount") or 0)
    ar_part = round(min(gross, float(doc.get("open_before") or 0)), 2)
    sc_part = round(gross - ar_part, 2)
    je = await gl_service.post_amendment_credit_note(doc, ar_part=ar_part, store_credit_part=sc_part)
    if sc_part > 0:
        await store_credit_service.issue(
            customer_id=doc.get("customer_id") or "", entity_id=doc.get("entity_id", ""), amount=sc_part,
            ref_type="credit_note", ref_id=doc["id"], ref_number=doc["number"],
            note=f"Nota kredit batal item {doc['number']}", je_id=(je or {}).get("id", ""),
            customer_name=doc.get("customer_name", ""))
    await db.credit_notes.update_one({"id": doc["id"]}, {"$set": {
        "accounting": "revenue_correction", "ar_applied": ar_part, "store_credit_amount": sc_part,
        "journal_entry_id": (je or {}).get("id", "")}})
    return je
