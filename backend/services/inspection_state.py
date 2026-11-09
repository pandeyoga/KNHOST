"""FIX-10 — TABEL TRANSISI status SPK inspeksi / QC penerimaan (`inspections`: `po_receipt`, `makloon_output`,
`qc_4point`, `random_check`, `return_customer`, `return_supplier`, `replacement`, `sales_order`).

Pola `services/inbound_task_state.py` (FIX-3a) / `grn_state.py` (FIX-6): satu DAFTAR-IZIN per aksi + tulisan status CAS
(status asal ∈ daftar-izin aksi di filter tulis) + jejak `status_history` bentuk SSOT (`services/status_history.py`).
Dulu `inspection_service._save` menulis `{id}` saja sesudah cek status di Python (R→W) — penutupan SPK bisa menimpa
SPK yang baru saja dibuka ulang/ditutup orang lain — dan tidak ada riwayat STATUS (hanya linimasa peristiwa `history`).

    (lahir) ─▶ draft ─tugaskan─▶ assigned ─mulai / baris QC pertama─▶ in_progress ─putuskan─▶ done
                 └───────────────── tugaskan (langsung bernama) ─▶ assigned        ▲            │
    draft | assigned | in_progress ─tutup (QC retur tidak diperlukan)─▶ closed     └─buka kembali┘
    done ─(tutup random check / QC 4-point: baris & tahanan diperbarui, status tetap)─▶ done

Pembalikan saat BATAL/BUKA KEMBALI jelas: "buka kembali" (done → in_progress) DITOLAK bila keputusan SPK sudah memutus
karantina (stok diterima/ditolak — koreksi lewat retur beli/penyesuaian) atau SPK QC (random check / 4-point: buat SPK
baru); bila boleh, keputusan & alasan tolak dikosongkan dan tonggak "retur sudah diinspeksi" dibatalkan
(`return_service.unmark_inspected_by_document`). `closed` = terminal (tidak ada roll yang disentuh).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from services import status_history as sh

DRAFT, ASSIGNED, IN_PROGRESS, DONE, CLOSED = "draft", "assigned", "in_progress", "done", "closed"
OPEN = (DRAFT, ASSIGNED, IN_PROGRESS)

TRANSITIONS: Dict[str, Dict[str, tuple]] = {
    "create": {"from": ("",), "to": (DRAFT, ASSIGNED)},
    "assign": {"from": OPEN, "to": (ASSIGNED, IN_PROGRESS)},
    "start": {"from": (DRAFT, ASSIGNED), "to": (IN_PROGRESS,)},
    "inspect_line": {"from": (ASSIGNED, IN_PROGRESS), "to": (IN_PROGRESS,)},
    "finish": {"from": (ASSIGNED, IN_PROGRESS), "to": (DONE,)},
    "reopen": {"from": (DONE,), "to": (IN_PROGRESS,)},
    "close_unneeded": {"from": OPEN, "to": (CLOSED,)},
    # sesudah diputuskan: baris/tahanan diperbarui, status TETAP
    "close_lines": {"from": (DONE,), "to": (DONE,)},
    # lepas / tolak tahanan baris (MD Quality / manajer) — status tetap
    "hold_line": {"from": OPEN + (DONE,), "to": OPEN + (DONE,)},
    # pembaruan isi tanpa perubahan status (sampling: baris tak diperiksa dikeluarkan sebelum keputusan)
    "edit": {"from": OPEN + (DONE,), "to": OPEN + (DONE,)},
}

EVENT_ACTION = {"assigned": "assign", "started": "start", "finished": "finish", "reopened": "reopen",
                "closed": "close_unneeded", "random_check_closed": "close_lines", "qc4_closed": "close_lines",
                "hold_released": "hold_line", "hold_rejected": "hold_line"}


def allowed_from(action: str) -> tuple:
    return TRANSITIONS[action]["from"]


def allowed(action: str, frm: str, to: str) -> bool:
    spec = TRANSITIONS[action]
    return (frm or "") in spec["from"] and (to == frm or to in spec["to"])


def check(action: str, frm: str, to: str) -> None:
    if not allowed(action, frm, to):
        raise ValueError(f"Transisi SPK inspeksi tidak terdaftar: {action} {frm or '—'} → {to or '—'}")


def history_entry(to: str, actor_name: str = "", note: str = "", action: str = "", frm: str = "") -> Dict[str, Any]:
    return sh.entry(to, user=actor_name, note=note, action=action, **({"from": frm} if frm else {}))


def initial_history(status: str, actor_name: str, note: str = "") -> list:
    check("create", "", status)
    return [history_entry(status, actor_name, note, "create")]


def cas_filter(doc_id: str, action: str, frm: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Filter tulis CAS: id + status asal ∈ daftar-izin aksi (atau `frm` yang lebih sempit)."""
    froms = list(frm) if frm is not None else list(allowed_from(action))
    return {"id": doc_id, "status": {"$in": froms}}
