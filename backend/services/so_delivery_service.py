"""F-06 (uji pra-UAT 2026-10-21, keputusan owner Q-01a) — bukti terima (POD) menutup SO otomatis.

Dulu POD *Terkirim* di Logistik hanya memicu hook Pesanan Khusus; SO tetap `shipped` ("Dikirim") sampai ada yang
menekan "Tandai diterima" manual. Kini: begitu SO sudah terkirim penuh (`shipped`) dan **setiap** Surat Jalan aktifnya
ber-POD (status logistik `delivered`/`completed` — kurir/sopir, atau serah terima ambil sendiri), SO otomatis
`done` dengan aktor = petugas POD, roll `in_transit_sales` → `delivered`, jejak audit `order_delivered`
(`via: pod_auto`). Tombol manual `mark-delivered` tetap ada untuk SO tanpa alur Logistik.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import now_iso
from db import db

logger = logging.getLogger(__name__)
POD_DONE = ("delivered", "completed")
SJ_INACTIVE = ("cancelled", "void", "voided")


async def pod_progress(order_id: str) -> Dict[str, Any]:
    """Berapa Surat Jalan aktif SO ini yang sudah ber-POD."""
    ships = await db.shipments.find({"order_id": order_id, "status": {"$nin": list(SJ_INACTIVE)}},
                                    {"_id": 0, "id": 1, "shipment_no": 1, "logistics_status": 1}).to_list(500)
    done = [s for s in ships if (s.get("logistics_status") or "") in POD_DONE]
    return {"total": len(ships), "with_pod": len(done), "complete": bool(ships) and len(done) == len(ships),
            "missing": [s.get("shipment_no") or s["id"] for s in ships if s not in done]}


async def complete_if_all_pod(order_id: str, actor_name: str) -> Optional[Dict[str, Any]]:
    """Tutup SO (shipped → done) bila semua SJ aktif ber-POD. Idempoten; None bila belum memenuhi."""
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "id": 1, "status": 1})
    if not order or order.get("status") != "shipped":
        return None
    prog = await pod_progress(order_id)
    if not prog["complete"]:
        return None
    from dependencies import audit
    from services.roll_service import deliver_order_rolls
    from services.sales_order_helpers import so_transition
    delivered = await deliver_order_rolls(order_id)
    try:
        result = await so_transition(order_id, ["shipped"], "done", actor_name or "Sistem (POD)", "order_delivered",
                                     {"delivered_at": now_iso(), "delivered_by": actor_name or "Sistem (POD)",
                                      "delivered_via": "pod"})
    except HTTPException:
        return None   # balapan: sudah ditutup jalur lain (manual / POD lain) — bukan galat
    await audit(actor_name or "Sistem (POD)", "order_delivered", "sales_order", order_id,
                {"rolls_delivered": delivered, "via": "pod_auto", "shipments": prog["total"]})
    try:
        from services import special_order_phase2 as _p2
        await _p2.on_delivered(order_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[complete_if_all_pod] efek samping gagal diabaikan: %s", exc)  # KN-C10
    return result


async def on_pod(order_ids: List[str], actor_name: str) -> None:
    """Dipanggil Logistik sesudah POD / serah terima — tidak pernah menggagalkan transisi logistiknya."""
    for oid in order_ids:
        try:
            await complete_if_all_pod(oid, actor_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[so_delivery.on_pod] SO %s gagal ditutup otomatis: %s", oid, exc)
