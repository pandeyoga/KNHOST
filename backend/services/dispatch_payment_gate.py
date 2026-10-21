"""F-10 (uji pra-UAT 2026-10-21, keputusan owner Q-02) — termin bayar-sebelum-kirim MENAHAN pengiriman.

Aturan (blok keras, bawaan):
* Termin dengan "DP % sebelum kirim" (`payment_terms.dp_percent`) > 0 — CBD = 100 %, DP50 = 50 % — mewajibkan
  `paid_total ≥ dp_percent × grand_total` sebelum barang keluar. Pagar dipasang di
  `loading_check_service.dispatch_guard`, jadi berlaku di SEMUA jalur kirim (Barang Keluar, maju tahap WMS,
  cek keberangkatan trip).
* Pengecualian: pemegang izin `order.release_unpaid` (bawaan Finance, Manager, Admin — dapat diubah di Peran &
  Hak Akses) memberi pengecualian per SO dengan ALASAN WAJIB; tersimpan di SO (`dispatch_payment_release`) +
  jejak audit, dan dapat dicabut lagi (juga dengan alasan).
* Dapat dikonfigurasi: persen per termin di Pengaturan → Syarat Bayar; gerbang dapat dimatikan per PT lewat
  Pusat Pengaturan `finance.dispatch_payment_gate` (block | off).
Pesanan sample punya gerbang bayarnya sendiri (Admin Sample/Finance) — tidak dinilai di sini.
"""
from typing import Any, Dict, Iterable, Optional

from fastapi import HTTPException

from core_utils import now_iso, rupiah
from db import db

EPS = 1.0   # toleransi pembulatan Rupiah
CLOSED = ("done", "cancelled", "rejected", "void", "expired")
PROJ = {"_id": 0, "id": 1, "entity_id": 1, "status": 1, "is_sample": 1, "payment_term_code": 1, "payment_term": 1,
        "payment_term_name": 1, "grand_total": 1, "total_amount": 1, "paid_total": 1, "dispatch_payment_release": 1,
        "order_number": 1, "number": 1, "sample_billing": 1, "sample_payment_status": 1}


async def _term(code: str, entity_id: str, cache: Dict) -> Optional[Dict[str, Any]]:
    key = ("term", code or "", entity_id or "")
    if key not in cache:
        from services import entity_master_service as ems
        cache[key] = (await ems.resolve_row("payment-terms", code, entity_id or "", include_inactive=True)) if code else None
    return cache[key]


async def _mode(entity_id: str, cache: Dict) -> str:
    key = ("mode", entity_id or "")
    if key not in cache:
        from services.config_resolver import value_of
        try:
            cache[key] = str(await value_of("finance.dispatch_payment_gate", {"entity_id": entity_id or ""}) or "block")
        except Exception:   # noqa: BLE001 — registry belum termuat: tetap blok (aman)
            cache[key] = "block"
    return cache[key]


def _message(st: Dict[str, Any]) -> str:
    return (f"Tertahan pembayaran: termin {st['term_name']} mewajibkan dibayar {rupiah(st['required'])} "
            f"({st['dp_percent']:g}% dari {rupiah(st['grand_total'])}) sebelum kirim; baru dibayar "
            f"{rupiah(st['paid'])} (kurang {rupiah(st['shortfall'])}). Catat pembayaran di Uang Masuk, atau minta "
            "Finance/Manager memberi pengecualian berizin di detail SO.")


async def evaluate(order: Dict[str, Any], cache: Optional[Dict] = None) -> Dict[str, Any]:
    """Status gerbang satu SO — dipakai pagar kirim, daftar Barang Keluar, meja Gudang, pelacak SO & detail SO."""
    cache = {} if cache is None else cache
    code = order.get("payment_term_code") or order.get("payment_term") or ""
    term = await _term(code, order.get("entity_id") or "", cache)
    pct = float((term or {}).get("dp_percent") or 0)
    grand = round(float(order.get("grand_total") or order.get("total_amount") or 0), 2)
    paid = round(float(order.get("paid_total") or 0), 2)
    required = round(grand * pct / 100.0, 2)
    mode = await _mode(order.get("entity_id") or "", cache)
    release = order.get("dispatch_payment_release") or None
    applies = pct > 0 and grand > 0 and mode != "off" and not order.get("is_sample")
    shortfall = round(max(0.0, required - paid), 2)
    st = {"applies": applies, "mode": mode, "term_code": code,
          "term_name": order.get("payment_term_name") or (term or {}).get("name") or code,
          "dp_percent": pct, "grand_total": grand, "required": required, "paid": paid, "shortfall": shortfall,
          "released": release, "blocked": bool(applies and shortfall > EPS and not release)}
    st["message"] = _message(st) if st["blocked"] else ""
    return st


async def holds_for_orders(order_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Status gerbang banyak SO sekaligus (satu query; termin & mode di-cache)."""
    ids = [i for i in dict.fromkeys(order_ids) if i]
    if not ids:
        return {}
    cache: Dict = {}
    return {o["id"]: await evaluate(o, cache) for o in await db.sales_orders.find({"id": {"$in": ids}}, PROJ).to_list(len(ids))}


def desk_note(hold: Optional[Dict[str, Any]]) -> str:
    """Catatan singkat untuk baris meja Gudang/pelacak: kosong bila tidak tertahan."""
    if not hold or not hold.get("blocked"):
        return ""
    return f"tertahan bayar {hold['term_code'] or 'termin'} (kurang {rupiah(hold['shortfall'])})"


async def guard(order_id: Optional[str]) -> None:
    """Pagar kirim: 409 bila termin belum terpenuhi dan tidak ada pengecualian berizin."""
    if not order_id:
        return
    order = await db.sales_orders.find_one({"id": order_id}, PROJ)
    if not order:
        return
    if order.get("sample_billing") == "paid" and order.get("sample_payment_status") == "reapproval_required":
        # F-15 — sample berbayar: tagihan berubah melewati toleransi sesudah potong → tunggu persetujuan ulang.
        raise HTTPException(status_code=409, detail=(
            "Sample tertahan: tagihan berubah melewati toleransi sesudah dipotong — menunggu persetujuan ulang "
            "pembayaran oleh Finance/Admin Sample (Meja Admin Sample)."))
    st = await evaluate(order)
    if st["blocked"]:
        raise HTTPException(status_code=409, detail=st["message"])


def _reason(reason: str) -> str:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Alasan pengecualian wajib diisi (min. 5 huruf).")
    return reason


async def release(order: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Pengecualian berizin: SO boleh dikirim walau termin belum terpenuhi. Alasan wajib, teraudit."""
    from dependencies import audit
    reason = _reason(reason)
    if order.get("status") in CLOSED:
        raise HTTPException(status_code=400, detail="Pesanan sudah ditutup/dibatalkan.")
    st = await evaluate(order)
    if not st["applies"]:
        raise HTTPException(status_code=400, detail="Termin pesanan ini tidak menahan pengiriman — tidak perlu pengecualian.")
    if st["released"]:
        raise HTTPException(status_code=409, detail="Pesanan ini sudah punya pengecualian kirim.")
    if not st["blocked"]:
        raise HTTPException(status_code=400, detail="Pembayaran sudah memenuhi termin — tidak perlu pengecualian.")
    rel = {"by": actor.get("name", ""), "by_id": actor.get("id", ""), "by_role": actor.get("role", ""),
           "at": now_iso(), "reason": reason, "paid_at_release": st["paid"], "required_at_release": st["required"],
           "shortfall_at_release": st["shortfall"], "term_code": st["term_code"]}
    res = await db.sales_orders.update_one(
        {"id": order["id"], "$or": [{"dispatch_payment_release": {"$exists": False}}, {"dispatch_payment_release": None}]},
        {"$set": {"dispatch_payment_release": rel, "updated_at": now_iso()}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Pesanan ini sudah punya pengecualian kirim.")
    await audit(actor.get("name", ""), "dispatch_payment_released", "sales_order", order["id"],
                {"reason": reason, "term": st["term_code"], "paid": st["paid"], "required": st["required"],
                 "shortfall": st["shortfall"], "order_number": order.get("order_number") or order.get("number", "")})
    return await evaluate({**order, "dispatch_payment_release": rel})


async def revoke(order: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Cabut pengecualian — pengiriman berikutnya kembali mengikuti termin. Alasan wajib, teraudit."""
    from dependencies import audit
    reason = _reason(reason)
    prev = order.get("dispatch_payment_release")
    if not prev:
        raise HTTPException(status_code=400, detail="Pesanan ini tidak punya pengecualian kirim.")
    revoked = {**prev, "revoked_by": actor.get("name", ""), "revoked_at": now_iso(), "revoke_reason": reason}
    res = await db.sales_orders.update_one(
        {"id": order["id"], "dispatch_payment_release.at": prev.get("at")},
        {"$set": {"dispatch_payment_release": None, "updated_at": now_iso()},
         "$push": {"dispatch_payment_release_history": revoked}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Pengecualian sudah berubah — muat ulang pesanan.")
    await audit(actor.get("name", ""), "dispatch_payment_release_revoked", "sales_order", order["id"],
                {"reason": reason, "released_by": prev.get("by", ""),
                 "order_number": order.get("order_number") or order.get("number", "")})
    return await evaluate({**order, "dispatch_payment_release": None})
