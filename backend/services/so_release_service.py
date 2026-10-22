"""Trial 22 Okt 2026 (E8/E10, keputusan pemilik) — **Periksa & lepas ke gudang** dalam SATU langkah Admin Sales.

KENAPA
======
Dulu Admin Sales menekan tiga tombol beruntun — Verifikasi → Ajukan persetujuan → Konfirmasi — padahal di data acuan
"Ajukan" hampir selalu disetujui otomatis (ambang nilai mati, kredit sudah diblokir di checkout). Gerbang yang tersisa
(harga khusus / nilai / makloon) diputus Manajer, dan sesudah ACC Admin Sales masih harus kembali menekan Konfirmasi.

ATURAN BARU
===========
* Admin Sales menekan **Periksa & lepas ke gudang** sekali: kelengkapan diverifikasi, gerbang persetujuan diajukan,
  dan bila semua sudah beres pesanan langsung dilepas ke gudang (tugas ambil + WA pelanggan).
* Masih ada yang menunggu Manajer → pesanan berstatus "sudah diperiksa, menunggu ACC" dan **dilepas otomatis** begitu
  keputusan terakhir disetujui (hook di `routers/so_approvals._apply_decision`).
* "Tahan dulu" → diperiksa tetapi tidak dilepas sampai Admin Sales menekan **Lepas ke gudang** (`release_hold`).
* Harga khusus DITOLAK → sales memilih: ajukan harga lain (pengajuan baru menggantikan), **lanjut harga normal**
  (`continue_normal_price` — entri penolakan ditutup, pesanan lanjut & dilepas otomatis bila sudah diperiksa),
  atau batalkan pesanan.

Penanda di dokumen SO: `release = {requested, hold, by, at, note, released_at}` (tanpa koleksi baru).
"""
from typing import Any, Dict, Optional

from fastapi import HTTPException

from core_utils import now_iso, safe_doc
from db import db
from services import so_approvals

OPEN_FOR_REVIEW = ("reserved", "waiting_stock", "waiting_approval", "approved")


async def _load(order_id: str) -> Dict[str, Any]:
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan")
    return order


async def _verification_ok(order: Dict[str, Any]) -> bool:
    from services import so_verify_service as ver
    if (order.get("verification") or {}).get("status") == "verified":
        return True
    return not await ver._config_bool(ver.CONFIG_REQUIRE_VERIFY, order.get("entity_id") or "")


def release_state(order: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan untuk layar: diperiksa? ditahan? menunggu apa sebelum lepas?"""
    rel = order.get("release") or {}
    s = so_approvals.summarize(order)
    waiting = ("ditolak" if s["has_rejected"] else "acc" if s["has_pending"]
               else "stok" if order.get("status") == "waiting_stock" else "")
    return {"requested": bool(rel.get("requested")), "hold": bool(rel.get("hold")), "waiting": waiting,
            "by": rel.get("by", ""), "at": rel.get("at", ""), "released_at": rel.get("released_at", "")}


async def try_release(order_id: str, actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Lepas ke gudang bila semua syarat terpenuhi; None bila belum (bukan error). Idempoten."""
    order = await _load(order_id)
    rel = order.get("release") or {}
    if not rel.get("requested") or rel.get("hold") or order.get("status") not in ("reserved", "approved"):
        return None
    if not await _verification_ok(order) or not so_approvals.all_approved(order):
        return None
    from services.so_lifecycle_service import confirm_core, submit_core
    if order.get("status") == "reserved":
        # Belum ada gerbang yang menunggu (mis. ACC harga datang sebelum Admin Sales memeriksa): ajukan ulang supaya
        # aturan nilai/validasi tetap dievaluasi. Butuh ACC → berhenti di Menunggu persetujuan (lepas nanti otomatis).
        order = await submit_core(order, actor)
        if (order or {}).get("status") != "approved":
            return None
    out = await confirm_core(order_id, actor)
    await db.sales_orders.update_one({"id": order_id}, {"$set": {"release.released_at": now_iso(),
                                                                "release.released_by": actor.get("name", "")}})
    return out


async def review_and_release(order_id: str, actor: Dict[str, Any], note: str = "", hold: bool = False) -> Dict[str, Any]:
    """Satu tombol Admin Sales: verifikasi → ajukan gerbang → lepas (atau tunggu ACC / tahan)."""
    from services import so_verify_service as ver
    order = await _load(order_id)
    if order.get("order_type") == "sample":
        raise HTTPException(status_code=409, detail="Pesanan sample diurus Admin Sample, bukan lewat meja Admin Sales.")
    if order.get("status") not in OPEN_FOR_REVIEW:
        raise HTTPException(status_code=409, detail=(
            f"Pesanan {order.get('number')} sudah dilepas/ditutup (status {order.get('status')})."))
    if (order.get("verification") or {}).get("status") != "verified":
        try:
            await ver.verify(order, actor, note)
        except ver.VerifyError as exc:
            raise HTTPException(status_code=409, detail={"message": str(exc), "checks": exc.checks}) from exc
    await db.sales_orders.update_one({"id": order_id}, {"$set": {
        "release": {"requested": True, "hold": bool(hold), "by": actor.get("name", ""), "by_id": actor.get("id", ""),
                    "at": now_iso(), "note": (note or "").strip()[:400]},
        "updated_at": now_iso()}})
    order = await _load(order_id)
    from services.so_lifecycle_service import submit_core
    s = so_approvals.summarize(order)
    if order.get("status") == "reserved" and (s["has_pending"] or not hold):
        # Ada gerbang menunggu → status jadi Menunggu persetujuan (antrean Manajer). Tanpa gerbang & tidak ditahan →
        # ajukan (otomatis Disetujui) lalu lepas.
        await submit_core(order, actor)
    released = None if hold else await try_release(order_id, actor)
    final = await _load(order_id)
    return {"order": final, "released": bool(released), "release_state": release_state(final)}


async def release_hold(order_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Lepas pesanan yang sebelumnya "Tahan dulu"."""
    order = await _load(order_id)
    if not (order.get("release") or {}).get("requested"):
        raise HTTPException(status_code=409, detail="Pesanan belum diperiksa Admin Sales — gunakan Periksa & lepas ke gudang.")
    await db.sales_orders.update_one({"id": order_id}, {"$set": {"release.hold": False, "updated_at": now_iso()}})
    if order.get("status") == "reserved":
        from services.so_lifecycle_service import submit_core
        await submit_core(await _load(order_id), actor)
    released = await try_release(order_id, actor)
    final = await _load(order_id)
    return {"order": final, "released": bool(released), "release_state": release_state(final)}


async def continue_normal_price(order_id: str, approval_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Harga khusus DITOLAK → sales lanjut dengan harga normal: entri penolakan ditutup (riwayat tetap), pesanan naik
    ke Disetujui bila tak ada gerbang lain, lalu dilepas otomatis bila Admin Sales sudah memeriksa."""
    from routers.so_approvals import _persist_pending
    from services.roll_service import set_order_rolls_status
    from services.sales_order_helpers import so_transition
    order = await _load(order_id)
    pa = list(order.get("pending_approvals") or [])
    entry = next((p for p in pa if p.get("id") == approval_id), None)
    if not entry or entry.get("type") != "special_price" or entry.get("status") != "rejected":
        raise HTTPException(status_code=409, detail="Hanya harga khusus yang DITOLAK yang bisa dilanjutkan dengan harga normal.")
    entry.update({"status": "cancelled", "previous_status": "rejected", "cancel_reason": "Sales lanjut dengan harga normal",
                  "cancelled_by": actor.get("name", ""), "cancelled_at": now_iso()})
    order = await _persist_pending(order_id, pa)
    if so_approvals.all_approved(order) and order.get("status") == "waiting_approval":
        await so_transition(order_id, ["waiting_approval"], "approved", actor.get("name", ""), "order_approved",
                            {"approved_by": actor.get("name", ""), "approval_note": "Lanjut harga normal"})
        await set_order_rolls_status(order_id, "committed")
    await try_release(order_id, actor)
    from dependencies import audit
    await audit(actor.get("name", ""), "so_special_price_continue_normal", "sales_order", order_id,
                {"approval_id": approval_id, "product": entry.get("product_name")})
    final = await _load(order_id)
    return {"order": final, "release_state": release_state(final)}


async def auto_release(order_id: str, trigger: Dict[str, Any], why: str = "ACC") -> Optional[Dict[str, Any]]:
    """Kait sesudah gerbang terakhir beres (ACC Manajer / stok backorder tiba): lepas bila Admin Sales SUDAH meminta.
    Efek samping — kegagalan tidak boleh membatalkan keputusan yang memicunya."""
    import logging
    try:
        order = await _load(order_id)
        rel = order.get("release") or {}
        if not rel.get("requested") or rel.get("hold"):
            return None
        actor = {"id": trigger.get("id", ""), "role": trigger.get("role", ""),
                 "name": f"{rel.get('by') or 'Admin Sales'} (otomatis sesudah {why} {trigger.get('name', '')})".strip()}
        return await try_release(order_id, actor)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("[so_release] lepas otomatis %s gagal: %s", order_id, exc)
        return None
