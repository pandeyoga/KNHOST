"""FIX-6 — TULIS status Retur Penjualan (`sales_returns`) lewat tabel transisi + CAS + `status_history`.

Tabel transisinya tetap SATU: `services/return_state.TRANSITIONS` (daftar-izin `dari → ke`, modul murni). Modul ini
menambahkan sisi TULIS yang dulu hilang: banyak jalur memeriksa status di Python lalu menulis `{id}` saja (R→W, B2a
§8 #83–#84), dan tidak ada jejak riwayat status. Sekarang:

* `transition()` — filter tulis = id + status asal (CAS); status tujuan wajib sah menurut `return_state`; jejak
  `status_history` (bentuk SSOT `services/status_history.py`) ikut di tulisan yang sama. Kalah balapan → None.
* `history_entry()` — untuk jalur yang statusnya ditulis lewat klaim saga (`atomic_claim.finish_set`: settle,
  reverse, penyelesaian per roll) supaya riwayatnya berbentuk sama.

Efek balik saat BATAL/TOLAK sebelum settle (D5, keputusan pemilik 10 Nov): roll karantina retur yang lahir saat pindai
diterima dibalik oleh `return_intake_service.reverse` (dipanggil penolak/pembatal), bukan di sini.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Union

from pymongo import ReturnDocument

from core_utils import now_iso
from db import db
from services import return_state as st
from services import status_history as sh


def history_entry(to: str, actor_name: str = "", note: str = "", action: str = "") -> Dict[str, Any]:
    return sh.entry(to, user=actor_name, note=note, action=action)


async def transition(return_id: str, frm: Union[str, Iterable[str]], to: str, *, actor_name: str,
                     set_fields: Optional[Dict[str, Any]] = None, note: str = "", action: str = "",
                     extra_filter: Optional[Dict[str, Any]] = None,
                     unset: Optional[Iterable[str]] = None) -> Optional[Dict[str, Any]]:
    """CAS `frm → to`. ValueError bila transisi tidak sah; None bila status berubah bersamaan (CAS kalah)."""
    froms = [frm] if isinstance(frm, str) else list(frm)
    for f in froms:
        st.assert_transition(f, to)
    upd: Dict[str, Any] = {"$set": {**(set_fields or {}), "status": to, "updated_at": now_iso()},
                           "$push": {"status_history": history_entry(to, actor_name, note, action)}}
    if unset:
        upd["$unset"] = {k: "" for k in unset}
    return await db.sales_returns.find_one_and_update(
        {"id": return_id, "status": {"$in": froms}, **(extra_filter or {})}, upd,
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
