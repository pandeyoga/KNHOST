"""RF-01/RF-11 — SATU kontrak EPC: disimpan & dicocokkan sebagai 24 hex UPPERCASE tanpa pemisah.

EPC internal KN = 96-bit (24 hex) berawalan "E2" (bukan GS1 SGTIN — tidak ada header/partisi GS1).
Tampilan berkelompok (E200-47AF-…) hanya untuk mata manusia lewat `display_epc`.
"""
import re
from typing import Iterable, List, Optional

EPC_HEX_LEN = 24
_SEP = re.compile(r"[\s\-:_.]")
_HEX = re.compile(r"^[0-9A-F]{24}$")


def try_canonical(raw: Optional[str]) -> Optional[str]:
    s = _SEP.sub("", str(raw or "")).upper()
    return s if _HEX.match(s) else None


def canonical_epc(raw: Optional[str]) -> str:
    """Normalisasi ketat: separator/huruf kecil diterima, panjang/karakter salah DITOLAK (tanpa potong diam-diam)."""
    s = try_canonical(raw)
    if not s:
        raise ValueError(f"EPC tidak valid: wajib tepat {EPC_HEX_LEN} karakter hex (0-9, A-F).")
    return s


def normalize_reads(epcs: Iterable[Optional[str]], cap: int = 500) -> List[str]:
    """Pembacaan reader → bentuk kanonik (urut, unik). EPC rusak tetap dicatat apa adanya (uppercase)
    supaya tampil sebagai 'asing', bukan hilang diam-diam."""
    out: List[str] = []
    for e in epcs or []:
        raw = str(e or "").strip()
        if not raw:
            continue
        c = try_canonical(raw) or raw.upper()
        if c not in out:
            out.append(c)
        if len(out) >= cap:
            break
    return out


def display_epc(epc: Optional[str]) -> str:
    s = try_canonical(epc)
    return "-".join(s[i:i + 4] for i in range(0, EPC_HEX_LEN, 4)) if s else (epc or "")
