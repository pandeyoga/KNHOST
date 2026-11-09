"""FIX-10 — TABEL TRANSISI status sesi OPNAME (`cycle_count_sessions`: opname per item & per roll, PENDAFTARAN AWAL
`mode=registration`) dan sesi OPNAME RFID (`rfid_verify_sessions`, `kind=cycle_count`).

Pola `services/inbound_task_state.py` (FIX-3a) / `grn_state.py` (FIX-6): satu DAFTAR-IZIN per aksi + tulisan status CAS
(status asal + mode sesi di filter tulis) + jejak `status_history` bentuk SSOT (`services/status_history.py`). Dulu
status sesi ditulis di 10+ titik dengan daftar statusnya sendiri, tulisan akhir klaim saga memakai `{id}` saja, dan
tidak ada riwayat status (siapa menyetujui/menolak hanya di field datar yang tertimpa saat dibuka ulang).

Opname (item & roll) — `mode` ∈ {item (kosong), roll}:
    (buat) ─▶ open ─kirim─▶ submitted ─setujui─▶ approved | approved_with_exceptions
               ▲              └─tolak─▶ rejected
               └── buka kembali (hitung ulang) ── submitted | rejected
    open (mode roll) ─finalisasi─▶ approved | approved_with_exceptions          (sesi tindak lanjut lahir `open`)

Pendaftaran awal — `mode=registration` (endpoint opname biasa menolak sesi ini, FIX-3a STM-IN-03):
    (buat) ─▶ draft ─mulai (beku)─▶ running ─ajukan─▶ pending_approval ─setujui semua kelompok─▶ approved[_with_exceptions]
                  ◀─kalah balapan mulai─┘   ◀────kembalikan──────┘
    draft | running | pending_approval ─tolak─▶ rejected            (pembekuan dilepas, baris dibatalkan)

Opname RFID (`rfid_verify_sessions`, laporan saja — stok tidak diubah): open ─selesai─▶ completed.

Pembalikan saat BATAL/TOLAK jelas: opname ditolak → stok tidak pernah diubah (selisih baru diterapkan saat disetujui);
pendaftaran ditolak → pembekuan dilepas & baris lapangan `void` (EPC bebas lagi); "buka kembali" hanya bila belum ada
selisih yang diterapkan (409). Status yang sudah final (`approved*`) tidak dibuka lagi — koreksi lewat opname baru.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from pymongo import ReturnDocument

from core_utils import now_iso
from db import db
from services import status_history as sh

REG_OPEN = ("draft", "running", "pending_approval")
FINAL = ("approved", "approved_with_exceptions")

OPNAME: Dict[str, Dict[str, tuple]] = {
    "create": {"from": ("",), "to": ("open",)},
    "create_followup": {"from": ("",), "to": ("open",)},
    "submit": {"from": ("open",), "to": ("submitted",)},
    "reopen": {"from": ("submitted", "rejected"), "to": ("open",)},
    "approve": {"from": ("submitted",), "to": FINAL},
    "reject": {"from": ("submitted",), "to": ("rejected",)},
    "roll_finalize": {"from": ("open",), "to": FINAL},
}
REGISTRATION: Dict[str, Dict[str, tuple]] = {
    "reg_create": {"from": ("",), "to": ("draft",)},
    "reg_start": {"from": ("draft",), "to": ("running",)},
    "reg_start_rollback": {"from": ("running",), "to": ("draft",)},
    "reg_submit": {"from": ("running",), "to": ("pending_approval",)},
    "reg_return": {"from": ("pending_approval",), "to": ("running",)},
    "reg_approve": {"from": ("pending_approval",), "to": FINAL},
    "reg_reject": {"from": REG_OPEN, "to": ("rejected",)},
}
RFID: Dict[str, Dict[str, tuple]] = {
    "rfid_create": {"from": ("",), "to": ("open",)},
    "rfid_complete": {"from": ("open",), "to": ("completed",)},
}
TRANSITIONS: Dict[str, Dict[str, tuple]] = {**OPNAME, **REGISTRATION, **RFID}

LABEL = {"open": "terbuka", "submitted": "diajukan", "approved": "disetujui",
         "approved_with_exceptions": "disetujui — ada pengecualian", "rejected": "ditolak", "draft": "draf",
         "running": "berjalan", "pending_approval": "menunggu persetujuan", "completed": "selesai"}


def status_label(status: str) -> str:
    return LABEL.get(status or "", status or "—")


def allowed(action: str, frm: str, to: str) -> bool:
    spec = TRANSITIONS[action]
    return (frm or "") in spec["from"] and (to == frm or to in spec["to"])


def check(action: str, frm: str, to: str) -> None:
    if not allowed(action, frm, to):
        raise ValueError(f"Transisi sesi opname tidak terdaftar: {action} {frm or '—'} → {to or '—'}")


def history_entry(to: str, actor_name: str = "", note: str = "", action: str = "", frm: str = "") -> Dict[str, Any]:
    return sh.entry(to, user=actor_name, note=note, action=action, **({"from": frm} if frm else {}))


def initial_history(status: str, actor_name: str, action: str, note: str = "") -> list:
    check(action, "", status)
    return [history_entry(status, actor_name, note, action)]


def _mode_filter(action: str) -> Dict[str, Any]:
    if action in REGISTRATION:
        return {"mode": "registration"}
    if action in OPNAME:
        return {"mode": {"$ne": "registration"}}   # FIX-3a STM-IN-03 — sesi pendaftaran tidak lewat opname biasa
    return {}


async def transition(session_id: str, action: str, to: str, *, actor_name: str, frm: Optional[Iterable[str]] = None,
                     set_fields: Optional[Dict[str, Any]] = None, unset: Optional[Iterable[str]] = None,
                     extra_filter: Optional[Dict[str, Any]] = None, note: str = "", claimed: bool = False,
                     collection: str = "cycle_count_sessions", return_doc: bool = True) -> Any:
    """CAS status sesi untuk `action` (status asal ∈ daftar-izin atau `frm` yang lebih sempit) + jejak riwayat.
    `claimed=True` = tulisan akhir aksi yang diklaim saga: filter mensyaratkan `saga_lock` masih ada dan kunci dicabut.
    Mengembalikan dokumen sesudah tulis (`return_doc=False`: jumlah dokumen yang ditulis — `update_one`, dipakai jalur
    yang dulu memang `update_one`), atau None bila CAS kalah. ValueError bila transisi tidak terdaftar."""
    spec = TRANSITIONS[action]
    froms = list(frm) if frm is not None else [f for f in spec["from"] if f]
    for f in froms:
        check(action, f, to)
    out = None
    for f in froms:   # satu tulisan per status asal → entri riwayat tahu persis asalnya
        flt: Dict[str, Any] = {"id": session_id, "status": f, **_mode_filter(action), **(extra_filter or {})}
        if claimed:
            flt["saga_lock"] = {"$exists": True}
        upd: Dict[str, Any] = {"$set": {**(set_fields or {}), "status": to, "updated_at": now_iso()}}
        if f != to:
            upd["$push"] = {"status_history": history_entry(to, actor_name, note, action, f)}
        uns = {k: "" for k in (unset or [])}
        if claimed:
            uns["saga_lock"] = ""
        if uns:
            upd["$unset"] = uns
        if not return_doc:
            res = await db[collection].update_one(flt, upd)
            if res.matched_count:
                return res.matched_count
            continue
        out = await db[collection].find_one_and_update(flt, upd, projection={"_id": 0},
                                                       return_document=ReturnDocument.AFTER)
        if out:
            return out
    return out
