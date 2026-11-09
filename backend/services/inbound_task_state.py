"""FIX-3a — TABEL TRANSISI status tugas barang masuk (`wms_tasks`, `flow_type=inbound`).

Audit B2a (FLW-IN-01/06, pola #1) — penjaga lama berbentuk DAFTAR-LARANG ("selain completed/cancelled boleh"), sehingga
status yang lahir belakangan (`qc_pending`, `qc_rejected`, `escalated`) lolos: tugas yang sudah diputus QC bisa
"Terima" + "Selesai" lagi → roll baru, PO berlebih, tanpa jurnal. Sekarang setiap aksi punya DAFTAR-IZIN status asal
dan tulisan statusnya CAS (status asal ada di filter tulis), lewat satu tabel di bawah.

    waiting_goods ─terima─▶ receiving ─terima penuh─▶ qc_check ─selesai─▶ qc_pending ─keputusan QC─▶ completed
          │                    │                         │                    (QC mati) ─────────────▶ completed
          └──────── eskalasi ──┴─────────────────────────┘                    └─semua ditolak─▶ qc_rejected
                         ▼
                     escalated ─putusan manajer─▶ status asal (tanpa barang) / qc_check
    non-terminal (sebelum QC) ─batal PO─▶ cancelled

`put_away` (status mati — dibaca beberapa tempat, tidak pernah ditulis) tetap diterima `complete` demi data lama.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument

from core_utils import now_iso
from db import db
from services import status_history as sh

RECEIVABLE = ("waiting_goods", "receiving", "qc_check")
"""Status yang boleh menerima barang (pindai-terima / pindai label). Sesudah `complete` barang sudah diposting."""
POSTED = ("qc_pending", "qc_rejected", "completed")
"""Status sesudah barang diposting ke stok/karantina — tidak pernah kembali ke status penerimaan."""

TRANSITIONS: Dict[str, Dict[str, tuple]] = {
    "scan_receive": {"from": RECEIVABLE, "to": ("receiving", "qc_check")},
    "scan_label": {"from": RECEIVABLE, "to": ("receiving", "qc_check")},
    "escalate": {"from": RECEIVABLE, "to": ("escalated",)},
    # `qc_pending`/`qc_rejected`/`completed` sebagai tujuan HANYA untuk memulihkan eskalasi data lama (sebelum FIX-3a)
    # yang dibuat dari tugas yang barangnya sudah diposting.
    "resolve_escalation": {"from": ("escalated",), "to": ("waiting_goods", "receiving", "qc_check") + POSTED},
    "complete": {"from": ("qc_check", "put_away"), "to": ("qc_pending", "completed")},
    "complete_grn": {"from": ("qc_check", "put_away", "receiving"), "to": ("qc_pending", "completed")},
    "qc_decision": {"from": ("qc_pending",), "to": ("completed", "qc_rejected", "qc_pending")},
    "cancel": {"from": ("waiting_goods", "receiving", "qc_check", "escalated"), "to": ("cancelled",)},
}

LABEL = {"waiting_goods": "menunggu barang", "receiving": "sedang diterima", "qc_check": "siap diselesaikan",
         "escalated": "dieskalasi ke manajer", "qc_pending": "menunggu keputusan QC", "completed": "selesai",
         "qc_rejected": "ditolak QC", "cancelled": "dibatalkan", "put_away": "siap diselesaikan"}

ACTION_LABEL = {"scan_receive": "Terima barang", "scan_label": "Pindai label", "escalate": "Eskalasi",
                "resolve_escalation": "Selesaikan eskalasi", "complete": "Selesaikan penerimaan",
                "complete_grn": "Selesaikan penerimaan", "qc_decision": "Keputusan QC", "cancel": "Batal"}


def allowed_from(action: str) -> tuple:
    return TRANSITIONS[action]["from"]


def status_label(status: str) -> str:
    return LABEL.get(status or "", status or "—")


def assert_can(task: Dict[str, Any], action: str, *, status_code: int = 400) -> None:
    """400 (atau `status_code`) berbahasa Indonesia bila status tugas bukan status asal yang diizinkan untuk aksi ini."""
    st = task.get("status") or ""
    if st in allowed_from(action):
        return
    hint = ""
    if st in ("qc_pending", "qc_rejected", "completed"):
        hint = " Barang tugas ini sudah masuk stok/karantina — kekurangan atau kiriman pengganti diterima lewat tugas baru."
    elif st == "escalated":
        hint = " Tunggu keputusan manajer atas eskalasi lebih dulu."
    raise HTTPException(status_code=status_code, detail=(
        f"{ACTION_LABEL.get(action, action)} tidak bisa dilakukan: tugas berstatus '{status_label(st)}'.{hint}"))


def history_entry(status: str, actor_name: str, action: str, note: str = "") -> Dict[str, Any]:
    return sh.entry(status, user=actor_name, note=note, action=action)


async def transition(task_id: str, action: str, to_status: Optional[str], *, actor_name: str,
                     set_fields: Optional[Dict[str, Any]] = None, extra_filter: Optional[Dict[str, Any]] = None,
                     push: Optional[Dict[str, Any]] = None, unset: Optional[Iterable[str]] = None,
                     from_status: Optional[Iterable[str]] = None, note: str = "",
                     prev_status: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Tulis status lewat CAS: filter = id + status asal ∈ daftar-izin aksi (atau `from_status` yang lebih sempit).
    Mengembalikan dokumen sesudah tulis, atau None bila CAS kalah (status berubah bersamaan).
    Jejak `status_history` (bentuk SSOT `services/status_history.py`) ditulis hanya bila status benar-benar berganti."""
    spec = TRANSITIONS[action]
    frm = tuple(from_status) if from_status is not None else spec["from"]
    if to_status is not None and to_status not in spec["to"]:
        raise ValueError(f"Transisi tidak terdaftar: {action} → {to_status}")
    flt: Dict[str, Any] = {"id": task_id, "status": {"$in": list(frm)}, **(extra_filter or {})}
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
