"""Pelacak SO di setiap meja — pesanan aktif (baru muncul, hilang saat selesai/batal) beserta
tahap berikutnya dan SIAPA yang menindaklanjuti. `can_act` = peran meja ini pemilik tahap itu."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from db import db

CLOSED = ["done", "cancelled", "rejected", "expired", "void"]
STATUS_LABEL = {
    "draft": "Draft", "pending": "Draft", "waiting_approval": "Menunggu persetujuan",
    "approved": "Disetujui", "reserved": "Dicadangkan", "waiting_stock": "Menunggu stok",
    "confirmed": "Dikonfirmasi", "partially_picked": "Sebagian diambil", "picked": "Sudah diambil",
    "packing": "Dikemas", "packed": "Dikemas", "partially_shipped": "Sebagian dikirim",
    "shipped": "Dikirim", "dispatched": "Dikirim",
}
DESK_ROLES = {
    "sales_admin": {"sales_admin"}, "finance": {"finance"}, "md": {"md"},
    "warehouse_admin": {"warehouse_admin", "warehouse"}, "sample_admin": {"sample_admin"},
}
ROLE_LABEL = {"sales": "Sales", "sales_admin": "Admin Sales", "manager": "Manager", "finance": "Finance",
              "warehouse_admin": "Admin Gudang", "warehouse": "Staf Gudang", "logistics": "Logistik",
              "admin": "Admin", "director": "Direktur", "owner": "Pemilik"}


def next_step(o: Dict[str, Any]) -> Dict[str, Any]:
    """Tahap berikutnya + peran pemiliknya, diturunkan dari status SO."""
    st = o.get("status") or ""
    verified = (o.get("verification") or {}).get("status") == "verified"
    outstanding = float(o.get("grand_total") or o.get("total_amount") or 0) - float(o.get("paid_total") or 0)
    if st in ("draft", "pending", ""):
        return {"step": "Dilengkapi & diajukan", "roles": ["sales"], "action": "Buka SO"}
    if st == "waiting_approval":
        r = o.get("required_approval_role") or "manager"
        return {"step": "Diputuskan (setuju/tolak)", "roles": [r], "action": "Putuskan"}
    if st == "waiting_stock" or o.get("has_backorder"):
        return {"step": "Keputusan pemenuhan stok", "roles": ["sales_admin"], "action": "Atur pemenuhan"}
    if st in ("approved", "reserved"):
        return {"step": "Dikonfirmasi" if verified else "Diverifikasi & dikonfirmasi",
                "roles": ["sales_admin"], "action": "Verifikasi" if not verified else "Konfirmasi"}
    if st in ("confirmed", "partially_picked", "picked", "packing", "packed"):
        return {"step": "Diambil, dicek muat & diberangkatkan", "roles": ["warehouse_admin", "warehouse"],
                "action": "Buka tugas gudang"}
    if st == "partially_shipped":
        return {"step": "Kirim sisa barang", "roles": ["warehouse_admin", "warehouse"], "action": "Buka tugas gudang"}
    if outstanding > 0.009:
        return {"step": "Ditagih & dilunasi", "roles": ["finance"], "action": "Tagih"}
    return {"step": "Dikonfirmasi diterima pelanggan", "roles": ["logistics", "warehouse_admin"],
            "action": "Konfirmasi diterima"}


def _age(ts: str, now: datetime) -> int:
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return max(0, (now - dt).days)
    except (TypeError, ValueError):
        return 0


async def so_tracker(desk: str, actor: Dict[str, Any], scope: Dict[str, Any]) -> Dict[str, Any]:
    roles: Set[str] = DESK_ROLES.get(desk) or {actor.get("role") or ""}
    now = datetime.now(timezone.utc)
    q = {**scope, "status": {"$nin": CLOSED}, "is_sample": {"$ne": True}}
    proj = {"_id": 0, "id": 1, "order_number": 1, "number": 1, "customer_name": 1, "sales_name": 1,
            "status": 1, "verification": 1, "grand_total": 1, "total_amount": 1, "paid_total": 1,
            "required_approval_role": 1, "has_backorder": 1, "created_at": 1, "updated_at": 1, "entity_id": 1}
    rows: List[Dict[str, Any]] = []
    async for o in db.sales_orders.find(q, proj):
        ns = next_step(o)
        upd = o.get("updated_at") or o.get("created_at") or ""
        rows.append({
            "id": o["id"], "number": o.get("order_number") or o.get("number") or o["id"],
            "customer_name": o.get("customer_name") or "", "sales_name": o.get("sales_name") or "",
            "status": o.get("status"), "status_label": STATUS_LABEL.get(o.get("status") or "", o.get("status") or "-"),
            "next_step": ns["step"], "owner_roles": ns["roles"],
            "owner_label": " / ".join(ROLE_LABEL.get(r, r) for r in ns["roles"]),
            "can_act": bool(roles & set(ns["roles"])), "action": ns["action"],
            "grand_total": float(o.get("grand_total") or o.get("total_amount") or 0),
            "created_at": o.get("created_at") or "", "updated_at": upd,
            "age_days": _age(o.get("created_at") or "", now), "idle_days": _age(upd, now),
        })
    rows.sort(key=lambda r: (not r["can_act"], r["updated_at"] or ""))
    return {"desk": desk, "rows": rows, "count": len(rows), "actionable": sum(r["can_act"] for r in rows),
            "generated_at": now.isoformat()}


def desk_for(desk: Optional[str]) -> str:
    return desk if desk in DESK_ROLES or desk == "me" else "me"
