"""Aturan masukan BERSAMA (FIX-3a — audit B3b FRM-09/INP-09/INP-13, keputusan koordinator K-B3b-03).

Satu tempat untuk tiga kontrak masukan yang dulu ditulis ulang di tiap router:

* **Alasan K-14** — "alasan minimal 5 huruf" (keputusan pemilik 26 Okt). Dihitung **HURUF** (K-B3b-03), bukan
  karakter: "....." / "12345" / 5 spasi ditolak. Dipakai lewat tipe `ReasonStr` (model Pydantic → 422 berpesan
  Indonesia) atau `require_reason()` (parameter query / body `dict` → 400). Paket FIX-3b memakai modul yang sama.
* **Batas angka** (INV-NUM-01 / G-NUM-02) — qty/panjang wajib berhingga dan bertanda benar: `PosQty` (> 0),
  `NonNegQty` (≥ 0), serta `require_qty()` untuk parameter query.
* **Body bertipe ketat** (INP-13 / G-API-01) — `KNIn` menolak kunci asing (`extra="forbid"`) supaya salah eja
  kunci tidak lagi dibuang diam-diam.
"""
from __future__ import annotations

import math
from typing import Annotated, Any, Optional

from fastapi import HTTPException
from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field

MIN_REASON_LETTERS = 5
MAX_REASON_LEN = 1000


def count_letters(text: Any) -> int:
    """Jumlah HURUF (alfabet Unicode — termasuk huruf beraksen) dalam teks."""
    return sum(1 for ch in str(text or "") if ch.isalpha())


def reason_problem(text: Any, *, label: str = "Alasan", min_letters: int = MIN_REASON_LETTERS) -> Optional[str]:
    """Pesan kesalahan berbahasa Indonesia, atau None bila alasan sah."""
    t = str(text or "").strip()
    if count_letters(t) < min_letters:
        return (f"{label} wajib diisi minimal {min_letters} huruf (bukan hanya angka/tanda baca) — "
                "tulis alasan yang bisa dibaca orang lain.")
    if len(t) > MAX_REASON_LEN:
        return f"{label} terlalu panjang (maksimal {MAX_REASON_LEN} karakter)."
    return None


def require_reason(text: Any, *, label: str = "Alasan", min_letters: int = MIN_REASON_LETTERS) -> str:
    """Untuk parameter query / body `dict`: alasan sah → teks ter-strip; selain itu 400."""
    msg = reason_problem(text, label=label, min_letters=min_letters)
    if msg:
        raise HTTPException(status_code=400, detail=msg)
    return str(text).strip()


def optional_reason(text: Any, *, label: str = "Catatan", min_letters: int = MIN_REASON_LETTERS) -> str:
    """Boleh kosong; bila diisi wajib memenuhi K-14 (dipakai catatan yang opsional tetapi tidak boleh asal)."""
    t = str(text or "").strip()
    return require_reason(t, label=label, min_letters=min_letters) if t else ""


def _reason_validator(v: Any) -> str:
    msg = reason_problem(v)
    if msg:
        raise ValueError(msg)
    return str(v).strip()


def _opt_reason_validator(v: Any) -> str:
    t = str(v or "").strip()
    if not t:
        return ""
    return _reason_validator(t)


# Tipe model: `reason: ReasonStr` (wajib) · `notes: OptReasonStr = ""` (opsional, bila diisi tunduk K-14).
ReasonStr = Annotated[str, AfterValidator(_reason_validator)]
OptReasonStr = Annotated[str, AfterValidator(_opt_reason_validator)]


# ── Batas angka ──────────────────────────────────────────────────────────────
def _finite(v: Any) -> Any:
    if isinstance(v, float) and not math.isfinite(v):
        raise ValueError("Angka tidak sah (NaN/tak hingga).")
    return v


PosQty = Annotated[float, BeforeValidator(_finite), Field(gt=0, allow_inf_nan=False)]
NonNegQty = Annotated[float, BeforeValidator(_finite), Field(ge=0, allow_inf_nan=False)]


def require_qty(v: Any, *, label: str = "Jumlah", allow_zero: bool = False,
                max_value: Optional[float] = None) -> float:
    """Untuk parameter query: angka berhingga, > 0 (atau ≥ 0 bila `allow_zero`), opsional ≤ `max_value` → 400."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{label} harus angka.")
    if not math.isfinite(f):
        raise HTTPException(status_code=400, detail=f"{label} tidak sah (NaN/tak hingga).")
    if f < 0 or (f == 0 and not allow_zero):
        raise HTTPException(status_code=400, detail=f"{label} wajib {'≥ 0' if allow_zero else '> 0'}.")
    if max_value is not None and f > max_value:
        raise HTTPException(status_code=400, detail=f"{label} terlalu besar (maksimal {max_value:g}).")
    return f


# ── Body bertipe ketat ───────────────────────────────────────────────────────
class KNIn(BaseModel):
    """Basis body tulis: kunci yang tidak dikenal DITOLAK (422), bukan dibuang diam-diam (INP-13)."""
    model_config = ConfigDict(extra="forbid")
