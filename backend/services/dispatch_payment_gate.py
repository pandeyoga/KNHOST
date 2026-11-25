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
Lapor Bayar CBD & DP (LB-T2) — hitungan `evaluate` yang SAMA juga menahan pesanan sebelum gudang (`pay_hold_service`,
titik periksa `confirm_core`); pagar surat jalan di sini tetap sebagai pagar kedua.
"""
import logging
from typing import Any, Dict, Iterable, Optional

from fastapi import HTTPException

from core_utils import now_iso, rupiah
from db import db

logger = logging.getLogger(__name__)

EPS = 1.0   # toleransi pembulatan Rupiah
BASIS_KEY = "finance.tahan_kirim_dasar_bayar"   # PM-T3 — dasar "terbayar": tercatat | terverifikasi
CLOSED = ("done", "cancelled", "rejected", "void", "expired")
PROJ = {"_id": 0, "id": 1, "entity_id": 1, "status": 1, "is_sample": 1, "payment_term_code": 1, "payment_term": 1,
        "payment_term_name": 1, "grand_total": 1, "total_amount": 1, "paid_total": 1, "dispatch_payment_release": 1,
        "extra_billing_lines": 1, "pay_before_ship": 1,
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


async def _tunai_ditahan(entity_id: str, cache: Dict) -> bool:
    """CR-T3 — `finance.tahan_kirim_tunai` (per PT, bawaan mati): termin tunai diperlakukan bayar dulu 100 %."""
    key = ("tunai", entity_id or "")
    if key not in cache:
        from services.nilai_pengaturan import nilai
        cache[key] = bool(await nilai("finance.tahan_kirim_tunai", entity_id or ""))
    return cache[key]


async def _basis(entity_id: str, cache: Dict) -> str:
    """PM-T3 — `finance.tahan_kirim_dasar_bayar`: `tercatat` (semua pembayaran) | `terverifikasi` (kwitansi yang sudah
    cocok dengan mutasi bank + kwitansi tunai)."""
    key = ("basis", entity_id or "")
    if key not in cache:
        from services.config_resolver import value_of
        try:
            cache[key] = str(await value_of(BASIS_KEY, {"entity_id": entity_id or ""}) or "tercatat")
        except Exception:   # noqa: BLE001 — registry belum termuat: perilaku lama
            from config_registry import default_of
            cache[key] = str(default_of(BASIS_KEY))
    return cache[key]


async def _verified_paid(order: Dict[str, Any], cache: Dict) -> float:
    """PM-T3 — "terbayar" pada dasar `terverifikasi`: baris uang baru dari kwitansi (`kind` kas) hanya dihitung bila
    kwitansinya `bank_verified` atau bercara bayar tunai (masuk rekening kas — tidak ada mutasi bank untuk dicocokkan).
    Baris jenis lain (deposit, titipan bank, saldo kredit, nota kredit, hapus sisa, kasus) dihitung seperti biasa: bukan
    uang baru kwitansi yang menunggu mutasi bank. Pembalik (nominal negatif) mengikuti kwitansi asalnya."""
    from services.ar_allocation_service import payment_kind
    from services.payment_method_service import is_cash
    rows = order.get("payments")
    if rows is None:
        rows = ((await db.sales_orders.find_one({"id": order.get("id")}, {"_id": 0, "payments": 1})) or {}) \
            .get("payments") or []
    eid = order.get("entity_id") or ""
    ids = sorted({r.get("receipt_id") for r in rows if payment_kind(r) == "kas" and r.get("receipt_id")})
    belum = [i for i in ids if ("rc", i) not in cache]
    if belum:
        async for rc in db.ar_receipts.find({"id": {"$in": belum}},
                                            {"_id": 0, "id": 1, "bank_verified": 1, "method": 1, "entity_id": 1}):
            cache[("rc", rc["id"])] = bool(rc.get("bank_verified")) or await is_cash(
                rc.get("entity_id") or eid, rc.get("method") or "")
        for i in belum:
            cache.setdefault(("rc", i), False)
    total = 0.0
    for r in rows:
        if payment_kind(r) == "kas":
            rid = r.get("receipt_id")
            ok = cache.get(("rc", rid), False) if rid else await is_cash(eid, r.get("method") or "")
            if not ok:
                continue
        total += float(r.get("amount", 0) or 0)
    return round(total, 2)


def _message(st: Dict[str, Any]) -> str:
    msg = (f"Tertahan pembayaran: termin {st['term_name']} mewajibkan dibayar {rupiah(st['required'])} "
           f"({st['dp_percent']:g}% dari {rupiah(st['grand_total'])}) sebelum kirim; baru dibayar "
           f"{rupiah(st['paid'])} (kurang {rupiah(st['shortfall'])}). ")
    if st.get("basis") == "terverifikasi" and st.get("paid_recorded", 0) > st["paid"] + EPS:
        msg += (f"Pembayaran tercatat {rupiah(st['paid_recorded'])} — sebagian belum cocok dengan mutasi bank; "
                "cocokkan di Rekonsiliasi Bank. ")
    return msg + ("Catat pembayaran di Uang Masuk, atau minta Finance/Manager memberi pengecualian berizin di "
                  "detail SO.")


async def evaluate(order: Dict[str, Any], cache: Optional[Dict] = None) -> Dict[str, Any]:
    """Status gerbang satu SO — dipakai pagar kirim, daftar Barang Keluar, meja Gudang, pelacak SO & detail SO."""
    cache = {} if cache is None else cache
    code = order.get("payment_term_code") or order.get("payment_term") or ""
    term = await _term(code, order.get("entity_id") or "", cache)
    pct = float((term or {}).get("dp_percent") or 0)
    # CR-T3 — wajib bayar 100 % bila pesanan lahir "bayar penuh sebelum kirim" (K-27, pelanggan sedang ditahan), atau
    # termin `type: cash` dan `finance.tahan_kirim_tunai` menyala untuk PT pesanan.
    if order.get("pay_before_ship") or (str((term or {}).get("type") or "").lower() == "cash"
                                        and await _tunai_ditahan(order.get("entity_id") or "", cache)):
        pct = 100.0
    from services.customer_service import _order_grand_total   # PK-32 — nilai tagihan (+ tagihan tambahan)
    grand = round(float(order.get("grand_total") or order.get("total_amount") or 0), 2)
    if order.get("extra_billing_lines"):
        grand = round(_order_grand_total({**order, "grand_total": grand}), 2)
    paid_recorded = round(float(order.get("paid_total") or 0), 2)
    required = round(grand * pct / 100.0, 2)
    mode = await _mode(order.get("entity_id") or "", cache)
    release = order.get("dispatch_payment_release") or None
    applies = pct > 0 and grand > 0 and mode != "off" and not order.get("is_sample")
    basis = await _basis(order.get("entity_id") or "", cache) if applies else "tercatat"
    paid = min(paid_recorded, await _verified_paid(order, cache)) if basis == "terverifikasi" else paid_recorded
    shortfall = round(max(0.0, required - paid), 2)
    st = {"applies": applies, "mode": mode, "basis": basis, "paid_recorded": paid_recorded, "term_code": code,
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
            "pembayaran oleh Finance/Admin Sample (Meja Sample)."))
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
    # LB-T2 (B6) — pengecualian yang sama juga membuka tahan sebelum gudang dan memicu lepas otomatis (bila Admin Sales
    # sudah "Periksa & lepas"). Efek samping: kegagalannya tidak membatalkan pengecualian yang sudah tercatat.
    try:
        from services import pay_hold_service as _phs
        await _phs.clear_if_paid(order["id"], actor, why="kirim tanpa lunas")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[dispatch_payment_gate] buka tahan gudang %s gagal: %s", order["id"], exc)
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
    # LB-T2 — pesanan yang belum dilepas ke gudang kembali ditahan (penanda baru; hanya status `approved`).
    try:
        from services import pay_hold_service as _phs
        await _phs.start(order, actor)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[dispatch_payment_gate] tahan gudang ulang %s gagal: %s", order["id"], exc)
    return await evaluate({**order, "dispatch_payment_release": None})
