"""FIX-10 — TABEL TRANSISI status Putaway Order (`putaway_orders`, termasuk DRAF PA PREP-C/FIX-3a).

Pola `services/inbound_task_state.py` (FIX-3a) / `grn_state.py` (FIX-6): satu DAFTAR-IZIN per aksi + tulisan status CAS
(status asal di filter tulis) + jejak `status_history` bentuk SSOT (`services/status_history.py`) setiap kali status
berganti. Dulu status PA ditulis di 11 titik (draf, terbit, kirim, trip tiba, tutup sisa, konfirmasi lama, selesaikan
pengecualian) — tulisan akhir klaim saga memakai filter `{id}` saja dan tanpa riwayat status.

    (pemicu otomatis) ─▶ draft ─terbitkan─▶ open ─kirim (opsional)─▶ in_transit
       draft ─ubah─▶ draft          │                         │
       draft ─batal / dilepas SPK─▶ cancelled                 │
                                    └──── trip tiba / konfirmasi / tutup sisa ──┴──▶ partially_received
                                                         ─▶ completed | completed_with_exception | exception | returned
       exception / completed_with_exception / partially_received ─selesaikan pengecualian─▶ status turunan item

Status akhir diturunkan dari status ITEM (`putaway_arrival_service.final_status`): 0 roll tiba tidak pernah
`completed` (semua kembali = `returned`). Pembalikan saat BATAL jelas: draf yang dibatalkan tidak pernah mengklaim roll
(roll tetap di antrean siap-putaway); PA terbit yang tidak jadi dikirim diputus lewat "tutup sisa" `return_transit`
(roll kembali `label_verified/tag_verified` di gudang asal, klaim `active_movement` dicabut) — tidak ada status
"open → cancelled" yang meninggalkan klaim roll.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from db import db
from services import status_history as sh

ARRIVAL = ("open", "in_transit", "partially_received")
TERMINAL = ("completed", "completed_with_exception", "exception", "returned")
LIVE = ("draft",) + ARRIVAL

TRANSITIONS: Dict[str, Dict[str, tuple]] = {
    "create_draft": {"from": ("",), "to": ("draft",)},
    "create": {"from": ("",), "to": ("open",)},
    "edit_draft": {"from": ("draft",), "to": ("draft",)},
    "publish": {"from": ("draft",), "to": ("open",)},
    "cancel_draft": {"from": ("draft",), "to": ("cancelled",)},
    "release_inspection_draft": {"from": ("draft",), "to": ("draft", "cancelled")},
    "dispatch": {"from": ("open",), "to": ("in_transit",)},
    "arrival_trip": {"from": ARRIVAL, "to": ARRIVAL + TERMINAL},
    "confirm_arrival": {"from": ARRIVAL, "to": ("partially_received",) + TERMINAL},
    "close_remaining": {"from": ARRIVAL, "to": ("partially_received",) + TERMINAL},
    "resolve_exception": {"from": ARRIVAL + ("completed_with_exception", "exception"),
                          "to": ("partially_received",) + TERMINAL},
}

LABEL = {"draft": "draf", "open": "terbuka", "in_transit": "dalam perjalanan", "partially_received": "tiba sebagian",
         "completed": "selesai", "completed_with_exception": "selesai + exception", "exception": "exception",
         "returned": "dikembalikan ke transit", "cancelled": "draf dibatalkan"}


def status_label(status: str) -> str:
    return LABEL.get(status or "", status or "—")


def allowed(action: str, frm: str, to: str) -> bool:
    spec = TRANSITIONS[action]
    return frm in spec["from"] and (to == frm or to in spec["to"])


def check(action: str, frm: str, to: str) -> None:
    """Galat pemrograman (ValueError) bila `frm → to` tidak terdaftar untuk aksi ini."""
    if not allowed(action, frm or "", to or ""):
        raise ValueError(f"Transisi Putaway Order tidak terdaftar: {action} {frm or '—'} → {to or '—'}")


def history_entry(to: str, actor_name: str = "", note: str = "", action: str = "", frm: str = "") -> Dict[str, Any]:
    return sh.entry(to, user=actor_name, note=note, action=action, **({"from": frm} if frm else {}))


def with_history(op: Dict[str, Any], action: str, frm: str, to: str, actor_name: str = "",
                 note: str = "") -> Dict[str, Any]:
    """Tambahkan `$push status_history` ke update-doc bila status berganti (sesudah `check`)."""
    check(action, frm, to)
    if to and to != frm:
        op.setdefault("$push", {})["status_history"] = history_entry(to, actor_name, note, action, frm)
    return op


async def finish_claimed(order_id: str, frm: str, action: str, op: Dict[str, Any], actor_name: str = "",
                         note: str = "") -> None:
    """Tulisan akhir aksi yang diklaim saga (`atomic_claim`): CAS status asal + kunci masih dipegang, jejak riwayat.
    Kalah (status/kunci berubah di luar klaim) → 409 dan kunci DIBIARKAN (saga terlihat di Kunci Saga)."""
    to = (op.get("$set") or {}).get("status") or frm
    with_history(op, action, frm, to, actor_name, note)
    res = await db.putaway_orders.update_one({"id": order_id, "status": frm, "saga_lock": {"$exists": True}}, op)
    if not res.matched_count:
        from services import atomic_claim as _saga
        await _saga.mark_failed("putaway_orders", order_id, f"status berubah di luar klaim ({action})")
        raise HTTPException(status_code=409, detail=(
            f"Putaway Order berubah bersamaan (bukan lagi '{status_label(frm)}') — muat ulang layar."))


def initial_history(status: str, actor_name: str, action: str, note: str = "") -> list:
    check(action, "", status)
    return [history_entry(status, actor_name, note, action)]
