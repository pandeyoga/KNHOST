"""Lapor Bayar CBD & DP — tahan bayar SEBELUM gudang (rancangan
`docs/superpowers/specs/2026-11-25-lapor-bayar-cbd-design.md` §5.1–§5.3, keputusan pemilik B1/B6).

KENAPA
======
Dulu pesanan CBD / bagian DP baru ditahan di surat jalan (`dispatch_payment_gate.guard`): gudang sudah mengambil dan
menyiapkan barang yang belum dibayar. Kini pesanan yang wajib bayar dulu BERHENTI di tahap "Bayar dicek Finance", di
antara "Disetujui" dan "Dilepas ke gudang".

ATURAN
======
* **Satu hitungan.** "Wajib bayar dulu" dan jumlahnya HANYA dari `dispatch_payment_gate.evaluate` (termin
  `dp_percent`, `type: cash` + `finance.tahan_kirim_tunai`, `pay_before_ship`, `is_sample` dikecualikan,
  `finance.dispatch_payment_gate = off` mematikan, dasar `finance.tahan_kirim_dasar_bayar`). Gerbang gudang dan gerbang
  surat jalan tidak pernah berbeda pendapat. Pesanan sample (`order_type: sample`) punya gerbang bayarnya sendiri di Meja
  Sample — tidak ditahan di sini.
* **Penanda, bukan status.** Pesanan tetap `approved` dengan `pay_hold = {since, due_at, required, basis}`; sub-status
  `menunggu_bayar` (`so_status`). Penanda hanya berarti selama status `approved`.
* **Mulai** (`start`) saat pesanan mencapai `approved` (ajukan otomatis, keputusan ACC, lanjut harga normal) dan sebagai
  cadangan di `confirm_core` sebelum menolak konfirmasi. Kode bayar ikut lahir (`payment_code_service.ensure_for_order`,
  B1: invoice berkode sejak disetujui). Idempoten: `since`/`due_at` tidak pernah ditimpa.
* **Dibuka** (`clear_if_paid`) begitu `evaluate` tidak lagi menahan — uang cukup (kwitansi dari Lapor Bayar yang
  diterima Finance, Tugas 4) atau pengecualian berizin "kirim tanpa lunas" (`dispatch_payment_gate.release`, B6). Lalu
  jalur lepas otomatis yang sama dengan sesudah ACC (`so_release_service.auto_release`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

from core_utils import now_iso, safe_doc
from db import db

logger = logging.getLogger(__name__)

PESAN_MENUNGGU_BAYAR = "Menunggu pembayaran dicek Finance — lapor bayar di rincian pesanan."
AKTOR_SISTEM = {"id": "", "name": "Sistem", "role": "system"}


class MenungguBayar(HTTPException):
    """409 pemandu dari `confirm_core` untuk pesanan yang wajib bayar dulu dan belum dibayar. Kelas sendiri supaya
    "Periksa & lepas" (`so_release_service.try_release`) bisa menangkapnya tanpa menelan 409 lain (kredit,
    verifikasi)."""

    def __init__(self) -> None:
        super().__init__(status_code=409, detail=PESAN_MENUNGGU_BAYAR)


async def due_at(entity_id: Optional[str], start: Optional[datetime] = None) -> datetime:
    """Kapan tahan bayar pesanan di PT `entity_id` jatuh tempo: `start` (bawaan sekarang) + `sales.batas_bayar_hari`
    (per PT, bawaan 3 hari). Satu-satunya pembaca pengaturan itu — layar tidak menghitung sendiri."""
    from services.nilai_pengaturan import nilai
    hari = int(await nilai("sales.batas_bayar_hari", entity_id))
    return (start or datetime.now(timezone.utc)) + timedelta(days=hari)


async def _muat(order_id: str) -> Dict[str, Any]:
    return safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0})) or {}


async def _segarkan_tahap(order_id: str) -> Dict[str, Any]:
    """`stage`/`sub_status` tersimpan mengikuti penanda (preseden `credit_gate._segarkan_tahap`)."""
    from services.so_status import stage_fields
    so = await _muat(order_id)
    if so:
        sf = stage_fields(so)
        await db.sales_orders.update_one({"id": order_id}, {"$set": sf})
        so.update(sf)
    return so


async def _status_gerbang(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Status `dispatch_payment_gate.evaluate` untuk pesanan yang bisa ditahan di gudang; `None` = di luar cakupan."""
    if not order or order.get("order_type") == "sample":
        return None
    from services import dispatch_payment_gate as gate
    return await gate.evaluate(order)


async def blocked(order: Dict[str, Any]) -> bool:
    """Benar bila pesanan wajib bayar dulu, bagian wajibnya belum terbayar, dan tidak ada pengecualian berizin."""
    st = await _status_gerbang(order)
    return bool(st and st["applies"] and st["blocked"])


async def start(order: Dict[str, Any], actor: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Mulai tahan bayar untuk pesanan `approved` yang wajib bayar dulu: tulis `pay_hold`, segarkan sub-status,
    lahirkan kode bayar tingkat pesanan. Idempoten — penanda yang sudah ada hanya diperbarui `required`/`basis`-nya
    (nilai pesanan bisa berubah lewat override), `since`/`due_at` tetap. Kembalian = `pay_hold` tersimpan, atau `None`
    bila tidak ditahan."""
    oid = (order or {}).get("id")
    if not oid:
        return None
    so = await _muat(oid)   # baca ulang: pemanggil bisa membawa potret sebelum transisi
    if so.get("status") != "approved":
        return None
    st = await _status_gerbang(so)
    if not (st and st["applies"] and st["blocked"]):
        return None
    mulai = datetime.now(timezone.utc)
    hold = {"since": mulai.isoformat(), "due_at": (await due_at(so.get("entity_id"), mulai)).isoformat(),
            "required": st["required"], "basis": st["basis"]}
    res = await db.sales_orders.update_one(
        {"id": oid, "status": "approved", "$or": [{"pay_hold": {"$exists": False}}, {"pay_hold": None}]},
        {"$set": {"pay_hold": hold, "updated_at": now_iso()}})
    if res.modified_count:
        from dependencies import audit
        await audit((actor or AKTOR_SISTEM).get("name", ""), "pay_hold_started", "sales_order", oid,
                    {"required": st["required"], "basis": st["basis"], "term": st["term_code"],
                     "due_at": hold["due_at"], "order_number": so.get("number", "")})
    else:
        await db.sales_orders.update_one({"id": oid, "status": "approved", "pay_hold.since": {"$exists": True}},
                                         {"$set": {"pay_hold.required": st["required"], "pay_hold.basis": st["basis"]}})
    so = await _segarkan_tahap(oid)
    # B1 — kode bayar sejak disetujui (Konfirmasi Pesanan/Faktur Komersial memuat instruksi bayar). Gagal = dicatat;
    # tahan tetap berlaku (penanda sudah tertulis) dan `confirm_core` mencoba lagi.
    try:
        from services import payment_code_service as _pcs
        await _pcs.ensure_for_order(so)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[pay_hold] kode bayar %s gagal dibuat: %s", oid, exc)
    return so.get("pay_hold")


def _cabut(so: Dict[str, Any]) -> Dict[str, str]:
    """Isi `$unset` penanda: `pay_hold` + `release.waiting` (hanya bila `release` berupa dokumen)."""
    out = {"pay_hold": ""}
    if isinstance(so.get("release"), dict):
        out["release.waiting"] = ""
    return out


async def drop(order_id: str) -> None:
    """Hapus penanda tanpa memicu lepas (dipakai `confirm_core` sesudah pesanan benar-benar dilepas ke gudang)."""
    so = await _muat(order_id)
    if not so.get("pay_hold") and (so.get("release") or {}).get("waiting") is None:
        return
    await db.sales_orders.update_one({"id": order_id}, {"$unset": _cabut(so)})
    await _segarkan_tahap(order_id)


async def clear_if_paid(order_id: str, actor: Optional[Dict[str, Any]] = None, why: str = "bayar diterima") -> bool:
    """Buka tahan bila `evaluate` tidak lagi menahan (uang cukup atau ada pengecualian berizin), lalu jalankan lepas
    otomatis. Kembalian = pesanan benar-benar dilepas ke gudang (`confirmed`) oleh panggilan ini.

    Aturan R4 (pengendali, 25 Nov): lepas otomatis HANYA bila Admin Sales sudah menekan "Periksa & lepas"
    (`release.requested`, diperiksa `so_release_service.auto_release`). Tanpa itu pesanan cukup kehilangan tahannya dan
    menunggu Admin Sales seperti biasa — verifikasi Admin Sales tidak boleh dilompati oleh uang yang masuk."""
    so = await _muat(order_id)
    if not so:
        return False
    if not so.get("pay_hold") and (so.get("release") or {}).get("waiting") != "bayar":
        return False   # tidak sedang ditahan (pesanan lama / non-CBD): tidak ada yang dibuka
    if await blocked(so):
        return False
    res = await db.sales_orders.update_one(
        {"id": order_id, "status": so.get("status")},
        {"$unset": _cabut(so), "$set": {"updated_at": now_iso()}})
    if not res.modified_count:
        return False   # status berubah oleh proses lain — biarkan pemiliknya yang melanjutkan
    await _segarkan_tahap(order_id)
    from dependencies import audit
    pelaku = actor or AKTOR_SISTEM
    await audit(pelaku.get("name", ""), "pay_hold_cleared", "sales_order", order_id,
                {"why": why, "required": (so.get("pay_hold") or {}).get("required"),
                 "order_number": so.get("number", "")})
    from services import so_release_service as _rel
    return _rel.dilepas(await _rel.auto_release(order_id, pelaku, why=why))
