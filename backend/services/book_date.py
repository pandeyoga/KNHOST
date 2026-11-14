"""PK-37 (GL-05, keputusan K-03) — SATU tanggal buku WIB dan kunci periode untuk dokumen, pembayaran, dan mutasi stok.

`tanggal_buku` adalah satu-satunya pengubah nilai tanggal/stempel waktu menjadi tanggal buku jurnal `YYYY-MM-DD`
berzona WIB (UTC+7). Transaksi pukul 00.00–06.59 WIB tanggal 1 tidak lagi jatuh ke bulan sebelumnya karena
stempel UTC-nya terpotong 10 huruf.

`periksa_periode_dokumen` adalah langkah PERIKSA (`docs/blueprint/02_STANDAR.md` §1, P2) untuk aksi yang berakibat
jurnal: dokumen yang bertanggal di periode tertutup ditolak SEBELUM ada yang tersimpan. Sakelarnya
`periode.kunci_dokumen` (global → PT, bawaan menyala). Jendela Buka Periode yang aktif tetap meloloskan (penjaga
`gl_service.enforce_closed_period_guard`).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Union

WIB = timezone(timedelta(hours=7))

_TANGGAL = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# ISO 8601: tanggal + jam (pemisah `T`, atau spasi seperti `str(datetime)`), detik/pecahan opsional, zona opsional.
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:?\d{2})?$")

_BULAN = ("", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
          "November", "Desember")

PESAN_TERTUTUP = ("Periode {periode} sudah ditutup, jadi {jenis} bertanggal {tanggal} tidak bisa dicatat. Pakai "
                  "tanggal di periode yang masih terbuka, atau ajukan Buka Periode di menu Keuangan.")


def _sekarang() -> datetime:
    """Jam sistem (UTC). Dipanggil lewat nama modul supaya uji bisa membekukannya."""
    return datetime.now(timezone.utc)


def _tidak_dikenali(nilai: Any) -> ValueError:
    return ValueError(f"Tanggal tidak dikenali: {nilai!r}")


def tanggal_buku(nilai: Any = None) -> str:
    """Tanggal buku WIB `YYYY-MM-DD`.

    - kosong (`None`/"") → tanggal hari ini di WIB;
    - `datetime` → diubah ke WIB (tanpa zona dianggap UTC); `date` → apa adanya;
    - teks 10 huruf `YYYY-MM-DD` → apa adanya (tanggal yang diketik pengguna);
    - teks ISO **ber-zona** (`Z` / `±hh:mm`) → diubah ke WIB;
    - teks ISO **tanpa zona** (`YYYY-MM-DDThh:mm:ss`) → 10 huruf pertamanya (tanggal isian pengguna);
    - bentuk lain → `ValueError("Tanggal tidak dikenali: …")`.
    """
    if nilai is None or (isinstance(nilai, str) and not nilai.strip()):
        return _sekarang().astimezone(WIB).date().isoformat()
    if isinstance(nilai, datetime):
        dt = nilai if nilai.tzinfo else nilai.replace(tzinfo=timezone.utc)
        return dt.astimezone(WIB).date().isoformat()
    if isinstance(nilai, date):
        return nilai.isoformat()
    if not isinstance(nilai, str):
        raise _tidak_dikenali(nilai)
    s = nilai.strip()
    try:
        if _TANGGAL.match(s):
            return date.fromisoformat(s).isoformat()
        if _ISO.match(s):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.date().isoformat()
            return dt.astimezone(WIB).date().isoformat()
    except ValueError:
        raise _tidak_dikenali(nilai) from None
    raise _tidak_dikenali(nilai)


def periode_buku(nilai: Any = None) -> str:
    """Periode buku WIB `YYYY-MM` dari nilai yang sama dengan `tanggal_buku`."""
    return tanggal_buku(nilai)[:7]


def tanggal_panjang(tanggal: str) -> str:
    """`2026-11-01` → "1 November 2026" (teks pesan untuk pengguna)."""
    d = date.fromisoformat(tanggal_buku(tanggal))
    return f"{d.day} {_BULAN[d.month]} {d.year}"


async def periksa_periode_dokumen(entity_id: str, tanggal: Any, *, jenis: str) -> None:
    """Langkah PERIKSA: tolak dokumen yang tanggal bukunya di periode tertutup PT itu (`ClosedPeriodError`).

    Sakelar `periode.kunci_dokumen` mati untuk PT itu → kembali tanpa memeriksa (jurnalnya tetap dijaga
    `_insert_entry`). Jendela Buka Periode yang aktif meloloskan. `jenis` = teks Indonesia jenis dokumen pada pesan.
    """
    from core_utils import DEFAULT_ENTITY_ID
    from services import gl_service as gl
    from services.config_resolver import value_of
    eid = entity_id or DEFAULT_ENTITY_ID
    if not await value_of("periode.kunci_dokumen", {"entity_id": eid}):
        return
    tgl = tanggal_buku(tanggal)
    try:
        await gl.enforce_closed_period_guard(eid, tgl, source_type="preflight", can_backdate=True)
    except gl.ClosedPeriodError as exc:
        from services import closing_service as cs
        st = await cs.status_for_date(tgl, eid)
        periode = cs._period_label(st.get("period_type") or "month", st.get("period_key") or tgl[:7]) \
            if st.get("closed") else tgl[:7]
        raise gl.ClosedPeriodError(PESAN_TERTUTUP.format(periode=periode, jenis=jenis,
                                                         tanggal=tanggal_panjang(tgl))) from exc


async def periksa_periode_dokumen_409(entity_ids: Union[str, Iterable[str]], tanggal: Any, *, jenis: str) -> None:
    """`periksa_periode_dokumen` untuk tiap PT yang terlibat (urutan tetap, tanpa kembar); periode tertutup →
    `HTTPException(409, detail=<pesan>)`. Untuk router dan layanan yang galatnya HTTP (pola `routers/cash.py`)."""
    from fastapi import HTTPException
    from services import gl_service as gl
    daftar = [entity_ids] if isinstance(entity_ids, str) or entity_ids is None else list(entity_ids)
    dilihat: set = set()
    for eid in daftar:
        eid = eid or ""
        if eid in dilihat:
            continue
        dilihat.add(eid)
        try:
            await periksa_periode_dokumen(eid, tanggal, jenis=jenis)
        except gl.ClosedPeriodError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
