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
    seperti nota amandemen (`gl_service.post_amendment_credit_note`): Dr Pendapatan + PPN / Cr Piutang (sebesar
    piutang yang masih terbuka) + Cr Saldo Kredit pelanggan untuk sisanya.

PK-32 — nota lahir dan diterbitkan lewat mesin nota (`credit_note_service`): `create` = `issue(status=
"pending_finance")`, aksi `issue` = `release` (rencana dihitung saat terbit, lalu `settle`: saldo kredit dan jurnal
lewat pintu tahan-gagal — gagal → `issued` + `gl_status="failed"`, ulang dari Posting Gagal), `void` = `void`.
Nota batal item tidak membuat baris `payments[]`: total pesanan sudah turun saat baris dikeluarkan.
"""
from typing import Any, Dict

from fastapi import HTTPException

from core_utils import next_doc_number, now_iso, rupiah
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
    from services import credit_note_service as cns   # PK-32 — satu-satunya penyisip `credit_notes`
    doc = await cns.issue(
        kind="credit_note", source=SOURCE, order=order, number=number, net=round(gross - ppn, 2), ppn=ppn,
        actor=actor_name, status="pending_finance",
        lines=[{"product_id": line.get("product_id"), "product_name": line.get("product_name"),
                "quantity": line.get("quantity"), "unit": line.get("unit"), "price": line.get("price"),
                "subtotal": line.get("line_total") or line.get("subtotal")}],
        refs={"special_order_id": order.get("source_special_order_id") or "", "special_order_item_id": od_item_id,
              "reason_code": SOURCE, "reason_label": "Batal item Pesanan Khusus", "note": reason,
              "issued_reason": issued_reason},
        extra={"computed_gross": gross, "computed_ppn": ppn, "grand_total_before": before_gt,
               "grand_total_after": after_gt, "paid_total": paid, "open_before": round(max(before_gt - paid, 0.0), 2),
               "excess_payment": round(max(paid - after_gt, 0.0), 2),
               "revenue_recognized": bool(await gl_service._already_posted("sales_order", order["id"])),
               "corrections": [], "created_by": actor_name})
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
    from services import credit_note_service as cns
    doc = await db.credit_notes.find_one({"id": cn_id}, {"_id": 0})
    if not doc or doc.get("source") != SOURCE:
        raise HTTPException(status_code=404, detail="Nota kredit batal item tidak ditemukan.")
    assert_entity_access(doc, "credit_notes", ctx)
    if doc.get("status") != "pending_finance":
        st = cns.note_status(doc)
        raise HTTPException(status_code=409, detail=(
            f"Nota {doc.get('number')} sudah berstatus '{cns.LABEL_STATUS.get(st, st)}'."))
    who, now = actor.get("name", ""), now_iso()
    note = (body.get("note") or "").strip()
    if action == "issue":
        # PK-32 — terbit lewat mesin nota (PK-37: periode diperiksa sebelum status berubah bila ada jurnal koreksi)
        return await cns.release(cn_id, actor, issue_note=note)
    if action == "void":
        return await cns.void(cn_id, note, actor)
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
    else:
        raise HTTPException(status_code=400, detail="Aksi harus adjust, issue, atau void.")
    res = await db.credit_notes.update_one({"id": cn_id, "status": "pending_finance"}, upd)
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Nota baru saja diproses pengguna lain. Muat ulang.")
    return cns.normalize(await db.credit_notes.find_one({"id": cn_id}, {"_id": 0}))
