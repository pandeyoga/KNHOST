"""FIX-6 — TABEL TRANSISI status Kedatangan Barang / GRN (`goods_receipts`).

Pola `services/inbound_task_state.py` (FIX-3a): satu DAFTAR-IZIN per aksi + tulisan status CAS (status asal & versi di
filter tulis, lewat `goods_receipt_service.cas`) + jejak `status_history` bentuk SSOT (`services/status_history.py`)
setiap kali status berganti. Dulu tiap fungsi GRN memegang daftar statusnya sendiri tanpa jejak riwayat; sekarang
`cas()` menolak transisi yang tidak terdaftar (galat pemrograman → 500 yang terlihat, bukan status liar).

    draft ─baca OCR─▶ reading ─hasil/galat─▶ review ─mulai hitung─▶ counting ─selesai hitung─▶ reconcile ─tutup─▶ closing ─▶ closed
      │  └──── isi manual ─────────────────────▶ review ◀──gagal klaim tugas── counting ◀─hitung ulang─ reconcile ◀─kembali─ closing
      └── draft/reading/review/counting ─batal─▶ cancelled        review ─tolak─▶ rejected

Pembalikan saat BATAL jelas (`goods_receipt_close_service.cancel_grn`): roll `receiving` hasil hitung dihapus, klaim
tugas dilepas (tugas kembali `waiting_goods`), kunci SJ (`active_key`) dicabut. `closed` = terminal (stok sudah
diposting lewat tugas penerimaan; koreksi lewat retur beli / opname, bukan membuka GRN).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

from services import status_history as sh

TERMINAL = ("closed", "cancelled", "rejected")

TRANSITIONS: Dict[str, Dict[str, tuple]] = {
    "read": {"from": ("draft", "review"), "to": ("reading",)},
    "read_done": {"from": ("reading", "review"), "to": ("review",)},
    "manual_entry": {"from": ("draft",), "to": ("review",)},
    "start_count": {"from": ("review",), "to": ("counting",)},
    "start_count_rollback": {"from": ("counting",), "to": ("review",)},
    "finish_count": {"from": ("counting",), "to": ("reconcile",)},
    "reopen_count": {"from": ("reconcile",), "to": ("counting",)},
    "close_begin": {"from": ("reconcile",), "to": ("closing",)},
    "close_done": {"from": ("closing",), "to": ("closed",)},
    "return_to_reconcile": {"from": ("closing",), "to": ("reconcile",)},
    "reject": {"from": ("review",), "to": ("rejected",)},
    "cancel": {"from": ("draft", "reading", "review", "counting"), "to": ("cancelled",)},
}

LABEL = {"draft": "draf", "reading": "sedang dibaca", "review": "ditinjau", "counting": "dihitung",
         "reconcile": "rekonsiliasi", "closing": "sedang ditutup", "closed": "selesai", "rejected": "ditolak",
         "cancelled": "dibatalkan"}


def allowed(frm: str, to: str) -> bool:
    """Transisi `frm → to` terdaftar di salah satu aksi."""
    return any(frm in spec["from"] and to in spec["to"] for spec in TRANSITIONS.values())


def check(from_statuses: Iterable[str], to: str) -> None:
    """Galat pemrograman bila salah satu status asal yang diizinkan pemanggil tidak boleh berpindah ke `to`."""
    bad = [s for s in from_statuses if s != to and not allowed(s, to)]
    if bad:
        raise ValueError(f"Transisi GRN tidak terdaftar: {', '.join(bad)} → {to}")


def history_entry(to: str, actor_name: str = "", note: str = "", action: str = "") -> Dict[str, Any]:
    return sh.entry(to, user=actor_name, note=note, action=action)


def status_label(status: str) -> str:
    return LABEL.get(status or "", status or "—")
