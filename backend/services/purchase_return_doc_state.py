"""FIX-6 — TABEL TRANSISI status DOKUMEN Retur Beli (`purchase_returns.status`).

Pelengkap `purchase_return_state` (yang melacak `supplier_status` RMA). Dulu status dokumen ditulis lewat `{id}` saja
sesudah cek di Python (R→W) tanpa jejak riwayat. Sekarang satu daftar-izin per aksi + tulisan CAS (status asal di
filter) + jejak `status_history` bentuk SSOT (`services/status_history.py`):

    draft ─ajukan─▶ pending_approval ─setujui─▶ approved ─koreksi (reverse)─▶ cancelled
      └────────────────┴─────tolak─▶ rejected            (draft juga boleh langsung disetujui/ditolak — jalur lama)

Pembalikan yang JELAS per transisi:
  * tolak (retur dari TOLAK QC, `source=qc_reject`) — roll yang sudah dipisah `returned_supplier` saat keputusan QC
    tidak lagi menggantung: kembali ke gudang sebagai barang RUSAK (`damaged`, tetap dihitung persediaan; jurnal
    belum pernah diposting sehingga subledger = GL tanpa jurnal baru) — `purchase_return_remedy.on_reject`.
  * reverse (approved → cancelled) — jurnal retur beli dibalik, roll kembali (tolak QC → karantina), AP dipulihkan
    (bila memotong tagihan), dan efek PO pilihan tolak QC dibalik (`purchase_return_remedy.undo`).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Union

from fastapi import HTTPException
from pymongo import ReturnDocument

from core_utils import now_iso
from db import db
from services import status_history as sh

TRANSITIONS: Dict[str, Dict[str, tuple]] = {
    "submit": {"from": ("draft",), "to": ("pending_approval",)},
    "approve": {"from": ("draft", "pending_approval", "approved"), "to": ("approved",)},
    "reject": {"from": ("draft", "pending_approval"), "to": ("rejected",)},
    "reverse": {"from": ("approved",), "to": ("cancelled",)},
}
LABEL = {"draft": "draf", "pending_approval": "menunggu persetujuan", "approved": "disetujui", "rejected": "ditolak",
         "cancelled": "dibatalkan"}


def history_entry(to: str, actor_name: str = "", note: str = "", action: str = "") -> Dict[str, Any]:
    return sh.entry(to, user=actor_name, note=note, action=action)


def assert_can(doc: Dict[str, Any], action: str) -> None:
    st = (doc or {}).get("status") or ""
    if st not in TRANSITIONS[action]["from"]:
        raise ValueError(f"Retur beli {doc.get('number', '')} berstatus '{LABEL.get(st, st)}' — aksi ini tidak bisa.")


async def transition(return_id: str, action: str, to: str, *, actor_name: str,
                     set_fields: Optional[Dict[str, Any]] = None, note: str = "",
                     frm: Optional[Union[str, Iterable[str]]] = None,
                     extra_filter: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """CAS status dokumen retur beli; None bila status berubah bersamaan."""
    spec = TRANSITIONS[action]
    if to not in spec["to"]:
        raise ValueError(f"Transisi retur beli tidak terdaftar: {action} → {to}")
    froms = list(spec["from"]) if frm is None else ([frm] if isinstance(frm, str) else list(frm))
    return await db.purchase_returns.find_one_and_update(
        {"id": return_id, "status": {"$in": froms}, **(extra_filter or {})},
        {"$set": {**(set_fields or {}), "status": to, "updated_at": now_iso()},
         "$push": {"status_history": history_entry(to, actor_name, note, action)}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)


def conflict() -> HTTPException:
    return HTTPException(status_code=409, detail="Retur beli baru saja berubah oleh pengguna lain — muat ulang.")
