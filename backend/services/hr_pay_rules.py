"""PY-T3 (PY-04, PY-07, PY-08, PY-12; K-38, K-39) — aturan hitung gaji per PT dari Pusat Pengaturan.

Aturan yang dulu tertanam di penghitung slip (`hr_payroll_service`) — atau dibaca dari setelan tersembunyi
`system_settings{scope:"hr"}.overtime.{mode,work_days_per_week,holidays}` tanpa layar — kini kunci registry berlapis
global → PT (`config_catalog_ops.py`, kelompok "sdm"). `rules(entity_id)` satu-satunya pembacanya; penghitung slip,
absensi (menit lembur), simulator lembur, dan dampak lembur membaca lewat sini.

Nilai bawaan = perilaku sebelum unit ini (prorata mati, potongan mati, pengali bertingkat, lima hari kerja, menit lembur
= jam kerja − durasi shift, dua desimal), KECUALI `hr.overtime.sumber` = `pengajuan` (keputusan pemilik K-39: lembur
hanya dibayar bila ada pengajuan yang disetujui).

Fungsi murni: `normalize`, `bulatkan`, `rasio`, `prorate_factor`, `masa_kerja`, `atur_potongan`, `hitung_kehadiran`.
Saldo awal pajak (`hr_tax_opening_balances`, per PT): `tax_opening(s)`, `set_tax_opening`.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core_utils import new_id, now_iso, safe_doc
from db import db

#: nama aturan → kunci Pengaturan. Hanya `rules` yang membaca kunci-kunci ini.
KUNCI: Dict[str, str] = {
    "prorata": "hr.prorata_masuk_keluar",
    "prorata_perubahan": "hr.prorata_perubahan_gaji",
    "potongan_alpha": "hr.potongan_alpha",
    "potongan_cuti_tanpa_gaji": "hr.potongan_cuti_tanpa_gaji",
    "potongan_telat_per_menit": "hr.potongan_telat_per_menit",
    "lembur_sumber": "hr.overtime.sumber",
    "lembur_ambang_menit": "hr.overtime.ambang_menit",
    "lembur_mode": "hr.overtime.mode",
    "lembur_pengali": "hr.overtime.multiplier",
    "lembur_pembagi_jam": "hr.overtime.hours_divisor",
    "hari_kerja_seminggu": "hr.overtime.work_days_per_week",
    "lembur_hitung_absensi": "hr.overtime.hitung_absensi",
    "pembulatan_rupiah": "hr.pembulatan_rupiah",
}
PRORATA = ("mati", "hari_kalender", "hari_kerja")
SUMBER = ("pengajuan", "absensi")
MODE_LEMBUR = ("bertingkat", "flat")
HITUNG_ABSENSI = ("jam_kerja_lebih", "lewat_jam_pulang")
BULAN_PENDEK = ("", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

TAX_COLL = "hr_tax_opening_balances"
MASA_MSG = "Jumlah masa harus 1 sampai 11."


class TaxOpeningConflict(ValueError):
    """Pajak tahun itu sudah dihitung ulang (router → 409)."""


def _bawaan(nama: str) -> Any:
    import config_registry as registry
    return registry.require(KUNCI[nama])["default"]


def _pilih(v: Any, sah: Tuple[str, ...], nama: str) -> str:
    s = str(v) if v is not None else ""
    return s if s in sah else str(_bawaan(nama))


def normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Nilai mentah (resolver; termasuk nilai lama `system_settings` yang belum berbentuk pilihan registry) → aturan.

    Nilai lama yang dikenal: `overtime.mode` selain "flat" = bertingkat (perilaku `_overtime_amount` lama);
    `overtime.work_days_per_week` bilangan 6 = enam hari kerja. Nilai tak dikenal → bawaan registry (KF-06)."""
    def num(nama: str, cast, minimum=None):
        v = raw.get(nama)
        try:
            out = cast(v) if v not in (None, "") else cast(_bawaan(nama))
        except (TypeError, ValueError):
            out = cast(_bawaan(nama))
        return max(minimum, out) if minimum is not None else out

    try:
        hari = int(str(raw.get("hari_kerja_seminggu") or _bawaan("hari_kerja_seminggu")))
    except (TypeError, ValueError):
        hari = int(_bawaan("hari_kerja_seminggu"))
    pengali = raw.get("lembur_pengali")
    pembagi = raw.get("lembur_pembagi_jam")
    return {
        "prorata": _pilih(raw.get("prorata"), PRORATA, "prorata"),
        "prorata_perubahan": _pilih(raw.get("prorata_perubahan"), PRORATA, "prorata_perubahan"),
        "potongan_alpha": bool(raw.get("potongan_alpha")),
        "potongan_cuti_tanpa_gaji": bool(raw.get("potongan_cuti_tanpa_gaji")),
        "potongan_telat_per_menit": num("potongan_telat_per_menit", float, 0.0),
        "lembur_sumber": _pilih(raw.get("lembur_sumber"), SUMBER, "lembur_sumber"),
        "lembur_ambang_menit": num("lembur_ambang_menit", int, 0),
        "lembur_mode": "flat" if str(raw.get("lembur_mode") or "") == "flat" else "bertingkat",
        # sama dengan pembaca lama: `float(multiplier or 1.5)`, `int(hours_divisor or 173)` (0/kosong → bawaan)
        "lembur_pengali": float(pengali) if pengali else float(_bawaan("lembur_pengali")),
        "lembur_pembagi_jam": int(pembagi) if pembagi else int(_bawaan("lembur_pembagi_jam")),
        "hari_kerja_seminggu": 6 if hari == 6 else 5,
        "six_day": hari == 6,
        "lembur_hitung_absensi": _pilih(raw.get("lembur_hitung_absensi"), HITUNG_ABSENSI, "lembur_hitung_absensi"),
        "pembulatan_rupiah": bool(raw.get("pembulatan_rupiah")),
    }


async def rules(entity_id: str) -> Dict[str, Any]:
    """Semua aturan hitung gaji yang berlaku untuk PT itu (global → PT), sekali baca (`resolve_keys` = `value_of`
    untuk beberapa kunci dengan satu kali muat). Galat baca → bawaan registry (02 §2.2)."""
    from services.config_resolver import resolve_keys
    ctx = {"entity_id": entity_id} if entity_id and entity_id != "all" else {}
    try:
        res = await resolve_keys(list(KUNCI.values()), ctx)
        raw = {nama: res[kunci]["value"] for nama, kunci in KUNCI.items()}
    except Exception:   # noqa: BLE001 — cadangan = bawaan registry, bukan nilai lain
        raw = {nama: _bawaan(nama) for nama in KUNCI}
    out = normalize(raw)
    out["entity_id"] = entity_id or ""
    return out


def ringkas(rl: Dict[str, Any]) -> Dict[str, Any]:
    """Potret aturan yang dipakai slip (disimpan di slip: `pay_rules`, 02 §5 D3)."""
    return {k: rl.get(k) for k in ("prorata", "prorata_perubahan", "potongan_alpha", "potongan_cuti_tanpa_gaji",
                                   "potongan_telat_per_menit", "lembur_sumber", "lembur_ambang_menit", "lembur_mode",
                                   "lembur_pengali", "lembur_pembagi_jam", "hari_kerja_seminggu",
                                   "pembulatan_rupiah")}


# ── pembulatan (D5: satu fungsi) ──────────────────────────────────────────────────────────────────────────────────────
def bulatkan(amount: Any, rules: Optional[Dict[str, Any]] = None) -> float:
    """Dua desimal (bawaan; sama dengan `round(x, 2)` sebelum unit ini) atau rupiah penuh, setengah ke atas
    (`hr.pembulatan_rupiah`). Semua angka slip lewat sini."""
    x = float(amount or 0)
    if (rules or {}).get("pembulatan_rupiah"):
        return float(Decimal(repr(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return round(x, 2)


RUPIAH = {"pembulatan_rupiah": True}


# ── prorata ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _bounds(period: str) -> Tuple[str, str, int]:
    from services.hr_compensation_service import period_bounds
    return period_bounds(period)


def _hari(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days + 1


def rasio(rule: str, start: str, end: str, period: str, cal: Any) -> Tuple[int, int]:
    """(pembilang, penyebut) prorata rentang [start, end] di bulan `period`: `hari_kalender` = hari ÷ hari kalender
    bulan; `hari_kerja` = hari kerja rentang ÷ hari kerja bulan (kalender PT); `mati` = (1, 1)."""
    p0, p1, dim = _bounds(period)
    if rule not in ("hari_kalender", "hari_kerja"):
        return 1, 1
    s, e = max(start or p0, p0), min(end or p1, p1)
    if s > e:
        return 0, dim if rule == "hari_kalender" else max(1, cal.work_days(p0, p1))
    if rule == "hari_kalender":
        return _hari(s, e), dim
    total = cal.work_days(p0, p1)
    return (cal.work_days(s, e), total) if total else (0, 1)


def prorate_factor(rule: str, start: str, end: str, period: str, cal: Any) -> float:
    """`mati` → 1; `hari_kalender` → hari dalam [start, end] ÷ hari kalender bulan; `hari_kerja` → hari kerja dalam
    rentang ÷ hari kerja bulan."""
    n, d = rasio(rule, start, end, period, cal)
    return n / d if d else 0.0


def masa_kerja(emp: Dict[str, Any], period: str) -> Tuple[str, str]:
    """Rentang bekerja karyawan di bulan itu: tanggal masuk (bila jatuh di dalam periode) s.d. tanggal keluar
    (`separation_date` → `end_date` → `resign_date`, PK-45; bila jatuh di dalam periode)."""
    p0, p1, _ = _bounds(period)

    def tgl(v: Any) -> str:
        s = str(v or "")[:10]
        try:
            date.fromisoformat(s)
            return s
        except ValueError:
            return ""
    masuk = tgl(emp.get("join_date"))
    keluar = tgl(emp.get("separation_date") or emp.get("end_date") or emp.get("resign_date"))
    s = masuk if masuk and p0 < masuk <= p1 else p0
    e = keluar if keluar and p0 <= keluar < p1 else p1
    return s, e


def masuk_setelah(emp: Dict[str, Any], period: str) -> bool:
    """Tanggal masuk sesudah akhir periode (karyawan belum bekerja bulan itu)."""
    masuk = str(emp.get("join_date") or "")[:10]
    return bool(masuk) and len(masuk) == 10 and masuk > _bounds(period)[1]


def rentang_label(date_from: str, date_to: str) -> str:
    d1, d2 = date.fromisoformat(date_from), date.fromisoformat(date_to)
    return f"({d1.day}–{d2.day} {BULAN_PENDEK[d2.month]})"


def atur_potongan(segs: List[Dict[str, Any]], emp: Dict[str, Any], period: str, rl: Dict[str, Any],
                  cal: Any) -> List[Dict[str, Any]]:
    """Potongan periode (PY-T2 `segments`) + aturan PY-T3, tanpa mengubah masukan:

    * `hr.prorata_masuk_keluar` ≠ mati dan karyawan masuk/keluar di dalam periode → tiap potongan diberi
      `masuk_keluar` = {date_from, date_to, rasio: [n, d], bulat}: rentang potongan ∩ masa kerja dan rasionya; komponen
      ber-`prorate` dibayar nilai × n ÷ d (`hr_pay_components.nilai_tetap`), yang lain tetap nilai potongannya.
    * `hr.prorata_perubahan_gaji` = hari_kerja → potongan perubahan gaji (bukan sebulan penuh) diberi `rasio_ubah` =
      [hari kerja potongan, hari kerja bulan] (PY-T2 hari_kalender tetap hari ÷ hari kalender)."""
    p0, p1, _ = _bounds(period)
    s0, e0 = masa_kerja(emp, period)
    potong_mk = rl.get("prorata") in ("hari_kalender", "hari_kerja") and (s0 > p0 or e0 < p1)
    ubah_hk = rl.get("prorata_perubahan") == "hari_kerja"
    if not potong_mk and not ubah_hk:
        return segs
    wd_bulan = cal.work_days(p0, p1)
    bulat = "rupiah" if rl.get("pembulatan_rupiah") else "sen"
    out = []
    for seg in segs or ():
        seg = dict(seg)
        if ubah_hk and not seg.get("full"):
            seg["rasio_ubah"] = [cal.work_days(seg["date_from"], seg["date_to"]), max(1, wd_bulan)]
        if potong_mk:
            cs, ce = max(seg["date_from"], s0), min(seg["date_to"], e0)
            if (cs, ce) != (seg["date_from"], seg["date_to"]):
                n, d = rasio(rl["prorata"], cs, ce, period, cal)
                seg["masuk_keluar"] = {"date_from": cs, "date_to": ce, "rasio": [n, d], "bulat": bulat,
                                       "rule": rl["prorata"]}
        out.append(seg)
    return out


# ── kehadiran (potongan & komponen per hari hadir) ────────────────────────────────────────────────────────────────────
HADIR = ("hadir", "telat")


def hitung_kehadiran(work_days: Iterable[str], records: Iterable[Dict[str, Any]],
                     leaves: Iterable[Dict[str, Any]], date_from: str, date_to: str) -> Dict[str, Any]:
    """Ringkasan kehadiran satu karyawan dalam masa kerjanya (fungsi murni).

    * tidak hadir = hari kerja tanpa rekaman absensi (atau berekaman berstatus `alpha`) dan tanpa cuti disetujui;
    * cuti tanpa gaji = hari kerja yang tercakup cuti berjenis `unpaid` yang disetujui;
    * terlambat = Σ `late_min` rekaman dalam masa kerja (rekaman cuti tidak ikut);
    * hari hadir = rekaman berstatus hadir/telat (atau di luar lokasi yang sudah disetujui)."""
    wd = list(work_days)
    rec = {}
    for r in records or ():
        d = str(r.get("date") or "")[:10]
        if date_from <= d <= date_to:
            rec[d] = r
    cuti, unpaid = set(), set()
    for lv in leaves or ():
        dates = lv.get("work_dates") or []
        for d in dates:
            cuti.add(str(d)[:10])
            if lv.get("leave_type") == "unpaid":
                unpaid.add(str(d)[:10])
    alpha = [d for d in wd if d not in cuti and (d not in rec or rec[d].get("status") == "alpha")]
    tanpa_gaji = [d for d in wd if d in unpaid]
    late = sum(int(r.get("late_min") or 0) for r in rec.values() if r.get("method") != "leave")
    hadir = sum(1 for r in rec.values() if r.get("method") != "leave" and (
        r.get("status") in HADIR or (r.get("status") == "flagged" and r.get("approved"))))
    return {"work_days": len(wd), "alpha_days": len(alpha), "alpha_dates": alpha, "unpaid_days": len(tanpa_gaji),
            "unpaid_dates": tanpa_gaji, "late_min": late, "present_days": hadir}


async def ringkasan_kehadiran(emp_id: str, date_from: str, date_to: str, cal: Any) -> Dict[str, Any]:
    """Absensi dan cuti disetujui karyawan dalam [date_from, date_to] → `hitung_kehadiran`."""
    recs = await db.hr_attendance.find(
        {"employee_id": emp_id, "date": {"$gte": date_from, "$lte": date_to}},
        {"_id": 0, "date": 1, "status": 1, "late_min": 1, "method": 1, "approved": 1}).to_list(62)
    lvs = []
    async for lv in db.hr_leave_requests.find(
            {"employee_id": emp_id, "status": "approved", "date_from": {"$lte": date_to},
             "date_to": {"$gte": date_from}}, {"_id": 0, "leave_type": 1, "work_dates": 1, "date_from": 1,
                                               "date_to": 1}):
        if not lv.get("work_dates"):
            from services.hr_leave_service import working_days
            lv["work_dates"] = working_days(lv.get("date_from", ""), lv.get("date_to", ""))
        lvs.append(lv)
    return hitung_kehadiran(cal.work_day_list(date_from, date_to), recs, lvs, date_from, date_to)


# ── saldo awal pajak (PY-12) ──────────────────────────────────────────────────────────────────────────────────────────
def _uang(v: Any, label: str) -> float:
    try:
        x = float(v if v not in (None, "") else 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} harus berupa angka.") from exc
    if x < 0:
        raise ValueError(f"{label} tidak boleh negatif.")
    return round(x, 2)


def check_tax_opening(data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        year = int(data.get("year"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Tahun pajak wajib diisi (mis. 2026).") from exc
    if year < 2000 or year > 2100:
        raise ValueError("Tahun pajak wajib diisi (mis. 2026).")
    try:
        months = int(data.get("months"))
    except (TypeError, ValueError) as exc:
        raise ValueError(MASA_MSG) from exc
    if months != data.get("months") and str(months) != str(data.get("months")).strip():
        raise ValueError(MASA_MSG)
    if months < 1 or months > 11:
        raise ValueError(MASA_MSG)
    return {"year": year, "months": months,
            "tax_gross": _uang(data.get("tax_gross"), "Bruto"),
            "pension_deduction": _uang(data.get("pension_deduction"), "Iuran pensiun"),
            "pph21_withheld": _uang(data.get("pph21_withheld"), "PPh 21 sudah dipotong"),
            "note": str(data.get("note") or "").strip()[:300]}


async def tax_opening(entity_id: str, employee_id: str, year: Any) -> Optional[Dict[str, Any]]:
    if not entity_id or entity_id == "all":
        return None
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None
    return safe_doc(await db[TAX_COLL].find_one({"entity_id": entity_id, "employee_id": employee_id, "year": y},
                                                {"_id": 0}))


async def tax_openings(entity_id: str, year: Any, employee_ids: Optional[Iterable[str]] = None
                       ) -> Dict[str, Dict[str, Any]]:
    """{karyawan: saldo awal} PT itu untuk tahun itu (sekali per proses gaji)."""
    if not entity_id or entity_id == "all":
        return {}
    q: Dict[str, Any] = {"entity_id": entity_id, "year": int(year)}
    if employee_ids is not None:
        q["employee_id"] = {"$in": list(employee_ids)}
    return {r["employee_id"]: safe_doc(r) async for r in db[TAX_COLL].find(q, {"_id": 0})}


async def final_slip_locked(entity_id: str, employee_id: str, year: int) -> Optional[Dict[str, Any]]:
    """Slip masa pajak terakhir (hitung ulang setahun) tahun itu yang sudah diposting/dibayar, bila ada."""
    return await db.hr_payslips.find_one(
        {"entity_id": entity_id, "employee_id": employee_id, "period": {"$regex": f"^{int(year):04d}-"},
         "pph21_method": "annual_pasal17", "status": {"$in": ["posted", "paid"]}}, {"_id": 0, "id": 1, "number": 1})


async def set_tax_opening(entity_id: str, emp: Dict[str, Any], data: Dict[str, Any],
                          actor: Dict[str, Any]) -> Dict[str, Any]:
    v = check_tax_opening(data)
    if await final_slip_locked(entity_id, emp["id"], v["year"]):
        raise TaxOpeningConflict(f"Pajak {v['year']} karyawan ini sudah dihitung ulang, jadi saldo awalnya tidak "
                                 f"bisa diubah.")
    key = {"entity_id": entity_id, "employee_id": emp["id"], "year": v["year"]}
    now = now_iso()
    await db[TAX_COLL].update_one(key, {
        "$set": {**v, "employee_name": emp.get("name", ""), "updated_at": now,
                 "updated_by": actor.get("name", "system"), "updated_by_id": actor.get("id", "")},
        "$setOnInsert": {"id": new_id("htob"), "created_at": now, "created_by": actor.get("name", "system"),
                         "created_by_id": actor.get("id", "")}}, upsert=True)
    return await tax_opening(entity_id, emp["id"], v["year"])
