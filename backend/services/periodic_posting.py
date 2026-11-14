"""PK-22 (FY-02, keputusan K-13) — tanggal buku jurnal PERIODIK: gaji, penyusutan aset, dan akrual insentif.

Jurnal yang dibuat per periode bertanggal hari terakhir periodenya (pengaturan `gl.tanggal_jurnal_periodik`, global →
PT, bawaan `akhir_periode`), supaya gaji Oktober yang dicatat 3 November tetap masuk laporan Oktober. Pilihan
`hari_posting` mengembalikan perilaku lama (tanggal hari jurnal dibuat, WIB).

Satu-satunya sumber "hari ini" adalah `book_date.tanggal_buku()` (jam sistem WIB; uji membekukannya lewat
`services.book_date._sekarang`).

  journal_date(PT, "2026-10")     → "2026-10-31" (akhir_periode) | hari ini (hari_posting)
  assert_period_started("2026-12") → ValueError "Periode Desember 2026 belum dimulai, jadi belum bisa diproses."
"""
from __future__ import annotations

import calendar
import re

from services import book_date

KUNCI = "gl.tanggal_jurnal_periodik"
AKHIR_PERIODE = "akhir_periode"
HARI_POSTING = "hari_posting"

_PERIODE = re.compile(r"^(\d{4})-(\d{2})$")


def _ym(period: str) -> tuple:
    m = _PERIODE.match(str(period or "").strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise ValueError(f"Periode harus berbentuk TTTT-BB, mis. 2026-10 (diberi '{period}').")
    return int(m.group(1)), int(m.group(2))


def akhir_periode(period: str) -> str:
    """'2026-10' → '2026-10-31'."""
    y, m = _ym(period)
    return f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"


def label_periode(period: str) -> str:
    """'2026-12' → 'Desember 2026' (teks pesan untuk pengguna)."""
    y, m = _ym(period)
    return f"{book_date._BULAN[m]} {y}"


def hari_ini() -> str:
    """Tanggal buku hari ini (WIB)."""
    return book_date.tanggal_buku()


def assert_period_started(period: str) -> None:
    """Tolak periode yang bulan mulainya sesudah hari ini (WIB). Periode berjalan boleh (ASUMSI PK-22)."""
    y, m = _ym(period)
    if f"{y:04d}-{m:02d}-01" > hari_ini():
        raise ValueError(f"Periode {label_periode(period)} belum dimulai, jadi belum bisa diproses.")


async def journal_date(entity_id: str, period: str) -> str:
    """Tanggal buku jurnal periodik `period` untuk PT itu: hari terakhir periode (`akhir_periode`) atau hari ini
    (`hari_posting`). Nilai pengaturan dibaca berlapis global → PT (`02_STANDAR.md` §2.2)."""
    from services.config_resolver import value_of
    akhir = akhir_periode(period)   # memvalidasi bentuk periode dulu, apa pun pengaturannya
    pilihan = await value_of("gl.tanggal_jurnal_periodik", {"entity_id": entity_id or ""})
    return hari_ini() if str(pilihan) == HARI_POSTING else akhir
