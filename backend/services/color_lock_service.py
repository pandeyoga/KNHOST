"""Kunci Warna Eksklusif + Penanda Warna Otomatis.

Warna milik pelanggan (`color_library.exclusive_customer_id`) hanya boleh dipakai produk/spesifikasi
eksklusif pelanggan itu. Pemakaian untuk produk umum / pelanggan lain butuh izin manajer (`color.approve`).
Permintaan izin disimpan di dokumen warna (`color_library.use_requests[]`) — tanpa koleksi baru.
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso
from services.notification_service import create_notification

_PROJ = {"_id": 0, "id": 1, "code": 1, "name": 1, "hex": 1, "system": 1, "exclusive_customer_id": 1,
         "exclusive_customer_name": 1, "use_requests": 1}
STATUS_LABEL = {"pending": "Menunggu", "approved": "Disetujui", "rejected": "Ditolak", "revoked": "Dicabut"}


class ColorLockError(ValueError):
    pass


def _target_label(cid: str, cname: str) -> str:
    return f"pelanggan {cname or cid}" if cid else "produk umum"


async def _customer_name(cid: str) -> str:
    if not cid:
        return ""
    c = await db.customers.find_one({"id": cid}, {"_id": 0, "name": 1})
    if not c:
        raise ColorLockError("Pelanggan tujuan tidak ditemukan.")
    return c.get("name", "")


async def _color(color_id: str = "", code: str = "") -> Optional[Dict[str, Any]]:
    if color_id:
        return await db.color_library.find_one({"id": color_id}, _PROJ)
    if code:
        return await db.color_library.find_one({"code": code.strip().upper()}, _PROJ)
    return None


def _granted(color: Dict[str, Any], target: str) -> bool:
    return any(r.get("status") == "approved" and (r.get("target_customer_id") or "") == target
               for r in color.get("use_requests") or [])


async def assert_can_use(*, color_id: str = "", code: str = "", target_customer_id: str = "", context: str = "") -> None:
    """Tolak pemakaian warna milik pelanggan lain tanpa izin manajer yang disetujui."""
    color = await _color(color_id, code)
    if not color:
        return
    owner = color.get("exclusive_customer_id") or ""
    target = (target_customer_id or "").strip()
    if not owner or owner == target or _granted(color, target):
        return
    tname = (await db.customers.find_one({"id": target}, {"_id": 0, "name": 1}) or {}).get("name", target) if target else ""
    raise ColorLockError(
        f"Warna {color['code']} · {color['name']} milik {color.get('exclusive_customer_name') or owner} (eksklusif) — "
        f"tidak boleh dipakai untuk {_target_label(target, tname)}{f' ({context})' if context else ''} tanpa persetujuan manajer. "
        "Ajukan izin di Pustaka Warna → Warna Pelanggan → Minta izin pakai.")


def _row(color: Dict[str, Any], r: Dict[str, Any]) -> Dict[str, Any]:
    return {**r, "status_label": STATUS_LABEL.get(r.get("status"), r.get("status")),
            "target_label": _target_label(r.get("target_customer_id", ""), r.get("target_customer_name", "")),
            "color_id": color["id"], "color_code": color.get("code", ""), "color_name": color.get("name", ""),
            "hex": color.get("hex", ""), "owner_customer_id": color.get("exclusive_customer_id", ""),
            "owner_customer_name": color.get("exclusive_customer_name", "")}


async def create_request(color_id: str, payload: Dict[str, Any], actor: Dict[str, Any], entity_id: str = "") -> Dict[str, Any]:
    color = await _color(color_id)
    if not color:
        raise LookupError("Warna tidak ditemukan")
    owner = color.get("exclusive_customer_id") or ""
    if not owner:
        raise ColorLockError("Warna ini bukan milik pelanggan — bebas dipakai tanpa izin.")
    target = (payload.get("target_customer_id") or "").strip()
    if target == owner:
        raise ColorLockError("Pelanggan pemilik tidak perlu izin untuk warnanya sendiri.")
    reason = (payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise ColorLockError("Alasan wajib diisi (min. 5 karakter).")
    if _granted(color, target):
        raise ColorLockError(f"Izin untuk {_target_label(target, '')} sudah disetujui sebelumnya.")
    if any(r.get("status") == "pending" and (r.get("target_customer_id") or "") == target for r in color.get("use_requests") or []):
        raise ColorLockError("Permintaan izin untuk tujuan ini masih menunggu keputusan manajer.")
    req = {"id": new_id("cur"), "target_customer_id": target, "target_customer_name": await _customer_name(target),
           "reason": reason, "context": (payload.get("context") or "").strip(), "status": "pending",
           "requested_by": actor.get("name", ""), "requested_by_id": actor.get("id", ""), "requested_at": now_iso(),
           "entity_id": entity_id or "", "decided_by": "", "decided_at": "", "decision_note": ""}
    await db.color_library.update_one({"id": color_id}, {"$push": {"use_requests": req}, "$set": {"updated_at": now_iso()}})
    await create_notification(
        notif_type="color_use_request", severity="warning", link="?view=color-library",
        title=f"Izin pakai warna eksklusif {color['code']}",
        body=f"{req['requested_by']} minta izin memakai {color['code']} · {color['name']} (milik "
             f"{color.get('exclusive_customer_name', '')}) untuk {_target_label(target, req['target_customer_name'])}: {reason}",
        entity_id=entity_id or None, recipient_role="manager", ref=req["id"], dedupe=False)
    return _row(color, req)


async def list_requests(status: str = "", visible_customer_ids: Optional[set] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    async for color in db.color_library.find({"use_requests.0": {"$exists": True}}, _PROJ):
        if visible_customer_ids is not None and color.get("exclusive_customer_id") not in visible_customer_ids:
            continue
        out += [_row(color, r) for r in color.get("use_requests") or [] if not status or r.get("status") == status]
    out.sort(key=lambda r: r.get("requested_at", ""), reverse=True)
    return sorted(out, key=lambda r: r["status"] != "pending")


async def _transition(req_id: str, allowed_from: str, to: str, note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    color = await db.color_library.find_one({"use_requests.id": req_id}, _PROJ)
    if not color:
        raise LookupError("Permintaan izin tidak ditemukan")
    req = next(r for r in color["use_requests"] if r["id"] == req_id)
    if req.get("status") != allowed_from:
        raise ColorLockError(f"Permintaan berstatus '{STATUS_LABEL.get(req.get('status'))}' tidak bisa diubah.")
    if to in ("rejected", "revoked") and len((note or "").strip()) < 3:
        raise ColorLockError("Catatan/alasan wajib diisi.")
    upd = {"status": to, "decided_by": actor.get("name", ""), "decided_at": now_iso(), "decision_note": (note or "").strip()}
    await db.color_library.update_one({"id": color["id"], "use_requests.id": req_id},
                                      {"$set": {**{f"use_requests.$.{k}": v for k, v in upd.items()}, "updated_at": now_iso()}})
    req.update(upd)
    if req.get("requested_by_id"):
        await create_notification(
            notif_type="color_use_decided", severity="success" if to == "approved" else "warning", link="?view=color-library",
            title=f"Izin warna {color['code']} {STATUS_LABEL[to].lower()}",
            body=f"Izin memakai {color['code']} · {color['name']} untuk {_target_label(req['target_customer_id'], req['target_customer_name'])} "
                 f"{STATUS_LABEL[to].lower()} oleh {upd['decided_by']}" + (f": {upd['decision_note']}" if upd["decision_note"] else ""),
            entity_id=req.get("entity_id") or None, recipient_role="", recipient_user=req["requested_by_id"], ref=req_id, dedupe=False)
    return _row(color, req)


async def decide(req_id: str, approve: bool, note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    return await _transition(req_id, "pending", "approved" if approve else "rejected", note, actor)


async def revoke(req_id: str, note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    return await _transition(req_id, "approved", "revoked", note, actor)


async def auto_mark_owner(color_id: str, customer_id: str, customer_name: str, source: Dict[str, Any]) -> bool:
    """Warna baru (sistem KN, belum bertuan) dari pesanan khusus → milik pelanggan pemesan saat labdip disetujui.
    Dilewati bila warna sudah dipakai produk umum atau produk eksklusif pelanggan lain."""
    from services.color_service import color_usage
    color = await _color(color_id)
    if not color or not customer_id or color.get("exclusive_customer_id") or (color.get("system") or "KN") != "KN":
        return False
    u = (await color_usage()).get(color_id) or {}
    if u.get("general") or any(p.get("exclusive_customer_id") != customer_id for p in u.get("exclusive") or []):
        return False
    await db.color_library.update_one({"id": color_id, "exclusive_customer_id": {"$in": ["", None]}}, {"$set": {
        "exclusive_customer_id": customer_id, "exclusive_customer_name": customer_name,
        "exclusive_source": {"kind": "auto", **source, "at": now_iso()}, "updated_at": now_iso()}})
    return True
