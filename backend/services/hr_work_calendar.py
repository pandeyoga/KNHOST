"""PY-T3 (PY-07, PY-08; K-38, K-39) — kalender kerja per PT: hari libur (`hr_holidays`) + pola hari kerja seminggu.

Hari kerja = Senin–Jumat (atau Senin–Sabtu bila `hr.overtime.work_days_per_week` = 6) yang bukan hari libur PT itu.
Dipakai penghitung slip (`hr_payroll_service`: jenis hari lembur, hari kerja untuk prorata dan potongan) dan dibaca
lewat `Kalender` (fungsi murni, sekali dimuat per proses gaji).

`hr_holidays` (`hhol_…`, per PT): `entity_id`, `date` (TTTT-BB-HH), `name`, `kind` (`nasional` · `cuti_bersama` ·
`perusahaan`), jejak pembuat. Unik (`entity_id`, `date`) — `uq_entity_date` (indeks wajib). **Tanpa isi awal**: tanggal
libur nasional dan cuti bersama berasal dari keputusan resmi dan diisi pemilik di Pengaturan › SDM › Kalender Libur
(titik henti H4) — sistem tidak mengisinya sendiri.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

from core_utils import new_id, now_iso, safe_doc
from db import db

COLL = "hr_holidays"
KINDS = ("nasional", "cuti_bersama", "perusahaan")
KIND_LABEL = {"nasional": "Nasional", "cuti_bersama": "Cuti bersama", "perusahaan": "Perusahaan"}
DATE_MSG = "Tanggal harus berbentuk TTTT-BB-HH."


class HolidayConflict(ValueError):
    """Tanggal sudah terdaftar sebagai hari libur PT itu (router → 409)."""


def _d(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


def check_date(value: Any) -> str:
    s = str(value or "").strip()
    try:
        if len(s) != 10:
            raise ValueError(s)
        _d(s)
    except ValueError as exc:
        raise ValueError(DATE_MSG) from exc
    return s


def dup_msg(tanggal: str) -> str:
    return f"Tanggal {tanggal} sudah terdaftar sebagai hari libur di PT ini."


class Kalender:
    """Kalender kerja satu PT untuk rentang yang dimuat (fungsi murni sesudah dimuat)."""

    def __init__(self, entity_id: str = "", holidays: Iterable[str] = (), six_day: bool = False) -> None:
        self.entity_id = entity_id or ""
        self.holidays = frozenset(str(h)[:10] for h in holidays or ())
        self.six_day = bool(six_day)

    def is_holiday(self, d: str) -> bool:
        return str(d)[:10] in self.holidays

    def is_rest_day(self, d: str) -> bool:
        """Minggu, atau Sabtu pada pola lima hari kerja."""
        wd = _d(d).weekday()
        return wd == 6 or (wd == 5 and not self.six_day)

    def is_work_day(self, d: str) -> bool:
        return not self.is_rest_day(d) and not self.is_holiday(d)

    def work_day_list(self, date_from: str, date_to: str) -> List[str]:
        """Tanggal hari kerja dalam [date_from, date_to] (inklusif); [] bila rentang terbalik."""
        try:
            cur, end = _d(date_from), _d(date_to)
        except ValueError:
            return []
        out: List[str] = []
        while cur <= end:
            s = cur.isoformat()
            if self.is_work_day(s):
                out.append(s)
            cur += timedelta(days=1)
        return out

    def work_days(self, date_from: str, date_to: str) -> int:
        return len(self.work_day_list(date_from, date_to))

    def day_type(self, d: str, rate_basis: str = "normal") -> str:
        """Jenis hari lembur: `holiday` (libur PT / pengajuan berdasar libur) · `rest` (hari istirahat mingguan /
        pengajuan berdasar akhir pekan) · `workday`. Sama dengan aturan sebelum unit ini, dengan daftar libur dari
        `hr_holidays` PT itu (dulu daftar tersembunyi `overtime.holidays` tanpa layar)."""
        if rate_basis == "holiday" or self.is_holiday(d):
            return "holiday"
        try:
            rest = self.is_rest_day(d)
        except ValueError:
            rest = False
        if rate_basis == "weekend" or rest:
            return "rest"
        return "workday"


# ── baca ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def holidays_between(entity_id: str, date_from: str, date_to: str) -> List[str]:
    if not entity_id or entity_id == "all":
        return []
    return sorted({r["date"] async for r in db[COLL].find(
        {"entity_id": entity_id, "date": {"$gte": str(date_from)[:10], "$lte": str(date_to)[:10]}},
        {"_id": 0, "date": 1})})


async def calendar_for(entity_id: str, date_from: str, date_to: str,
                       rl: Optional[Dict[str, Any]] = None) -> Kalender:
    """Kalender PT itu untuk rentang tanggal; pola hari kerja dari `hr_pay_rules.rules` (sekali dibaca)."""
    if rl is None:
        from services import hr_pay_rules
        rl = await hr_pay_rules.rules(entity_id)
    return Kalender(entity_id, await holidays_between(entity_id, date_from, date_to), bool(rl.get("six_day")))


async def is_holiday(entity_id: str, d: str) -> bool:
    """Tanggal itu terdaftar sebagai hari libur PT itu."""
    if not entity_id or entity_id == "all":
        return False
    return bool(await db[COLL].find_one({"entity_id": entity_id, "date": str(d)[:10]}, {"_id": 1}))


async def work_days(entity_id: str, date_from: str, date_to: str) -> int:
    """Banyaknya hari kerja PT itu dalam [date_from, date_to]: pola hari kerja seminggu, dikurangi hari libur PT."""
    return (await calendar_for(entity_id, date_from, date_to)).work_days(date_from, date_to)


async def list_holidays(entity_id: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"entity_id": entity_id}
    if year:
        q["date"] = {"$regex": f"^{int(year):04d}-"}
    rows = await db[COLL].find(q, {"_id": 0}).sort("date", 1).to_list(400)   # D4 — satu PT, satu tahun (≤ 366)
    for r in rows:
        r["kind_label"] = KIND_LABEL.get(r.get("kind") or "", r.get("kind") or "")
    return [safe_doc(r) for r in rows]


# ── tulis ────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def add_holiday(entity_id: str, data: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from pymongo.errors import DuplicateKeyError
    tanggal = check_date(data.get("date"))
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("Nama hari libur wajib diisi.")
    if len(name) > 120:
        raise ValueError("Nama hari libur paling banyak 120 huruf.")
    kind = str(data.get("kind") or "")
    if kind not in KINDS:
        raise ValueError("Jenis hari libur harus Nasional, Cuti bersama, atau Perusahaan.")
    if await db[COLL].find_one({"entity_id": entity_id, "date": tanggal}, {"_id": 1}):
        raise HolidayConflict(dup_msg(tanggal))
    doc = {"id": new_id("hhol"), "entity_id": entity_id, "date": tanggal, "name": name, "kind": kind,
           "created_by": actor.get("name", "system"), "created_by_id": actor.get("id", ""),
           "created_at": now_iso(), "updated_at": now_iso()}
    try:
        await db[COLL].insert_one(dict(doc))
    except DuplicateKeyError as exc:   # D7 — dua permintaan bersamaan: indeks unik (entity_id, date) menolak yang kalah
        raise HolidayConflict(dup_msg(tanggal)) from exc
    doc["kind_label"] = KIND_LABEL[kind]
    return doc


async def delete_holiday(entity_id: str, holiday_id: str) -> Dict[str, Any]:
    cur = await db[COLL].find_one({"id": holiday_id, "entity_id": entity_id}, {"_id": 0})
    if not cur:
        raise LookupError("Hari libur tidak ditemukan di PT ini.")
    await db[COLL].delete_one({"id": holiday_id, "entity_id": entity_id})
    return safe_doc(cur)
