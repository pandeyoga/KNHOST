"""FIX-3b — TABEL TRANSISI status tugas ambil BARANG KELUAR (`wms_tasks`, `flow_type=outbound`, sumber SO & sampel).

Audit B2b (STM-OUT-1/2/6, pola #1) — penjaga lama berbentuk DAFTAR-LARANG ("selain dispatched/cancelled boleh"),
sehingga `escalated` lolos pindai-ambil (barang berangkat tanpa keputusan supervisor), resolve tanpa qty menghidupkan
tugas BATAL / TERKIRIM menjadi `packing`, dan rilis manual tugas terjadwal menulis tanpa CAS. Sekarang setiap aksi punya
DAFTAR-IZIN status asal dan tulisan statusnya CAS (status asal ada di filter tulis), lewat satu tabel — pola yang sama
dengan `inbound_task_state` (FIX-3a).

    scheduled ─rilis─▶ created ─pindai─▶ picking ─ambil penuh─▶ packing ─kirim─▶ partially_shipped ─kirim sisa─▶ dispatched
        │                 │                 │                      │                   │
        └──────────── eskalasi ─────────────┴──────────────────────┴───────────────────┘
                              ▼
                          escalated ─putusan supervisor─▶ status TURUNAN progres (tanpa qty: status sebelum eskalasi)
    non-terminal ─batal SO / batal baris─▶ cancelled        (dispatched & cancelled = terminal)

Status turunan sesudah eskalasi dihitung dari progres (`derived_status`): tugas yang sudah terkirim penuh tidak pernah
kembali ke `packing`, tugas terkirim sebagian tetap `partially_shipped`.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument

from core_utils import now_iso
from db import db
from services import status_history as sh

EPS = 0.01
TERMINAL = ("dispatched", "cancelled", "completed")
ACTIVE_PICK = ("created", "picking", "packing", "staging", "partially_shipped")
"""Status yang boleh menerima pindai-ambil (barang belum seluruhnya diambil/dikirim)."""

TRANSITIONS: Dict[str, Dict[str, tuple]] = {
    "release": {"from": ("scheduled",), "to": ("created",)},
    "scan_pick": {"from": ACTIVE_PICK, "to": ("picking", "packing", "partially_shipped")},
    "escalate": {"from": ("scheduled",) + ACTIVE_PICK, "to": ("escalated",)},
    "resolve_escalation": {"from": ("escalated",),
                           "to": ("scheduled", "created", "picking", "packing", "staging", "partially_shipped",
                                  "dispatched")},
    "dispatch": {"from": ACTIVE_PICK, "to": ("partially_shipped", "dispatched")},
    "advance": {"from": ("created", "picking", "packing"), "to": ("picking", "packing", "staging")},
    "cancel": {"from": ("scheduled", "escalated") + ACTIVE_PICK, "to": ("cancelled",)},
}

LABEL = {"scheduled": "terjadwal (hold)", "created": "baru", "picking": "sedang diambil", "packing": "siap kirim",
         "staging": "di area muat", "partially_shipped": "terkirim sebagian", "dispatched": "terkirim",
         "escalated": "dieskalasi ke supervisor", "cancelled": "dibatalkan", "completed": "selesai"}

ACTION_LABEL = {"release": "Rilis tugas", "scan_pick": "Ambil barang", "escalate": "Eskalasi",
                "resolve_escalation": "Selesaikan eskalasi", "dispatch": "Kirim", "advance": "Lanjut tahap",
                "cancel": "Batal"}


def allowed_from(action: str) -> tuple:
    return TRANSITIONS[action]["from"]


def status_label(status: str) -> str:
    return LABEL.get(status or "", status or "—")


def assert_can(task: Dict[str, Any], action: str, *, status_code: int = 400) -> None:
    """Galat berbahasa Indonesia bila status tugas bukan status asal yang diizinkan untuk aksi ini."""
    st = task.get("status") or ""
    if st in allowed_from(action):
        return
    hint = ""
    if st == "escalated":
        hint = " Tunggu keputusan supervisor atas eskalasi lebih dulu."
    elif st == "scheduled":
        hint = " Tugas pengambilan masih di-hold (terjadwal) — rilis dulu."
    elif st in TERMINAL:
        hint = " Tugas sudah selesai/dibatalkan."
    raise HTTPException(status_code=status_code, detail=(
        f"{ACTION_LABEL.get(action, action)} tidak bisa dilakukan: tugas berstatus '{status_label(st)}'.{hint}"))


def derived_status(quantity: float, picked: float, shipped: float) -> str:
    """Status tugas ambil yang SESUAI progres (dipakai sesudah eskalasi diputus)."""
    q, p, s = float(quantity or 0), float(picked or 0), float(shipped or 0)
    if q > EPS and s + EPS >= q:
        return "dispatched"
    if s > EPS:
        return "partially_shipped"
    if q > EPS and p + EPS >= q:
        return "packing"
    if p > EPS:
        return "picking"
    return "created"


def history_entry(status: str, actor_name: str, action: str, note: str = "") -> Dict[str, Any]:
    return sh.entry(status, user=actor_name, note=note, action=action)


async def transition(task_id: str, action: str, to_status: Optional[str], *, actor_name: str,
                     set_fields: Optional[Dict[str, Any]] = None, extra_filter: Optional[Dict[str, Any]] = None,
                     push: Optional[Dict[str, Any]] = None, unset: Optional[Iterable[str]] = None,
                     from_status: Optional[Iterable[str]] = None, note: str = "",
                     prev_status: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Tulis status lewat CAS: filter = id + status asal ∈ daftar-izin aksi (atau `from_status` yang lebih sempit).
    Mengembalikan dokumen sesudah tulis, atau None bila CAS kalah (status berubah bersamaan)."""
    spec = TRANSITIONS[action]
    frm = tuple(from_status) if from_status is not None else spec["from"]
    if to_status is not None and to_status not in spec["to"]:
        raise ValueError(f"Transisi tidak terdaftar: {action} → {to_status}")
    flt: Dict[str, Any] = {"id": task_id, "flow_type": "outbound", "status": {"$in": list(frm)}, **(extra_filter or {})}
    upd: Dict[str, Any] = {"$set": {**(set_fields or {}), "updated_at": now_iso()}}
    pushes = dict(push or {})
    if to_status is not None:
        upd["$set"]["status"] = to_status
        if to_status != prev_status:
            pushes["status_history"] = history_entry(to_status, actor_name, action, note)
    if pushes:
        upd["$push"] = pushes
    if unset:
        upd["$unset"] = {k: "" for k in unset}
    return await db.wms_tasks.find_one_and_update(flt, upd, projection={"_id": 0},
                                                  return_document=ReturnDocument.AFTER)


async def cancel_for_order(order_id: str, actor_name: str, reason: str) -> int:
    """Batal SO → semua tugas ambil yang belum terminal `cancelled` (CAS daftar-izin) dan eskalasi yang menunggu
    ikut ditutup (`escalation.status = cancelled`) supaya tidak bisa diselesaikan lalu menghidupkan tugas batal."""
    flt = {"order_id": order_id, "flow_type": "outbound", "status": {"$in": list(allowed_from("cancel"))}}
    now = now_iso()
    n = 0
    async for t in db.wms_tasks.find(flt, {"_id": 0, "id": 1, "status": 1, "escalation": 1}):
        extra: Dict[str, Any] = {"cancel_reason": reason, "cancelled_by": actor_name, "cancelled_at": now}
        if (t.get("escalation") or {}).get("status") in ("pending_review", "resolving"):
            extra.update({"escalation.status": "cancelled", "escalation.cancelled_at": now,
                          "escalation.resolution_notes": f"Eskalasi ditutup: {reason}"})
        got = await transition(t["id"], "cancel", "cancelled", actor_name=actor_name, set_fields=extra,
                               note=reason, prev_status=t.get("status"))
        if got:
            n += 1
    return n
