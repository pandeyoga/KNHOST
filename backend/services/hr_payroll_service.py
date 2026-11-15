"""HRD H4 — Payroll & Payslip engine + run lifecycle.

Port dari H-POC (scripts/poc_hrd.py) yang TERVALIDASI: BPJS, PPh21 TER bulanan,
jurnal SEIMBANG, komisi accrue_then_settle (anti double-count). Config-driven via
`system_settings.hr` (get_hr_settings). Koleksi kanonik (entity-scoped):
`hr_payroll_runs` (prun_), `hr_payslips` (slip_).

PK-46 — tabel TER bulanan (kategori A/B/C menurut PTKP), PTKP, tarif pasal 17, dan biaya jabatan dibaca dari
pengaturan BERTANGGAL BERLAKU lewat `aturan_pph21(tanggal)` (blok PK-46 di bawah), bukan konstanta. Baris tabel:
`{batas_atas, tarif_pct}`; bruto <= batas → tarif tsb. (baris pertama yang cocok; baris terakhir tanpa batas).
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc
from services import doc_refs_service as _refs   # PK-44 — INV-REF-04 sapu tautan sebelum hapus
from services import hr_service
from role_registry import category_of   # PR-T4 — kategori kerja dari sifat peran

INF = float("inf")
PAYROLL_PREFIX = "PAY-"   # K-09 (26 Okt): awalan nomor penggajian baru (dulu "PR-", bentrok Permintaan Pembelian)

# PK-22 (FY-06) — daur proses gaji: draft → pending_approval → approved → posted → paid; batal dari tiga status pertama →
# `cancelled`; void dari `posted` → `void`. Status antara (`posting`, `paying`, `voiding`) = klaim langkah yang sedang
# berjalan. Proses `cancelled`/`void` (dan `rejected` data lama) tidak menghalangi proses baru PT+periode yang sama.
RUN_STATUS_LABEL: Dict[str, str] = {
    "draft": "Draf", "pending_approval": "Menunggu pengesahan", "approved": "Disahkan", "posting": "Sedang diposting",
    "posted": "Diposting", "paying": "Sedang dibayar", "paid": "Dibayar", "cancelled": "Dibatalkan",
    "voiding": "Sedang dianulir", "void": "Dianulir", "rejected": "Ditolak",
}
DEAD_STATUSES = ("cancelled", "void", "rejected")
CANCELLABLE = ("draft", "pending_approval", "approved")


class PayrollConflict(ValueError):
    """PK-22 — aksi pada status yang salah (router → 409). Pesan siap tampil."""


def _status_conflict(run: Dict[str, Any], verb: str) -> PayrollConflict:
    lbl = RUN_STATUS_LABEL.get(run.get("status") or "", run.get("status") or "")
    return PayrollConflict(f"Penggajian {run.get('number') or run.get('id')} berstatus {lbl}, jadi tidak bisa {verb}.")


def _min_reason(reason: str) -> str:
    r = (reason or "").strip()
    if len(r) < 5:   # K-14 (26 Okt): alasan minimum seragam 5 huruf
        raise ValueError("Alasan wajib diisi (minimal 5 huruf).")
    return r


# ── PK-46 — aturan PPh 21 dari pengaturan BERTANGGAL BERLAKU ─────────────────────────────────────────────────────────
# Tabel tarif efektif (TER), kategori per status PTKP, PTKP setahun, tarif pasal 17, dan biaya jabatan TIDAK lagi
# konstanta di sini. Keenamnya kunci registry `bertanggal` (bawaan = isi kode lama, dipindah ke `data/pph21_bawaan.py`)
# dan dibaca SEKALI per proses gaji untuk tanggal akhir periode gaji (WIB): slip periode sebelum tanggal berlaku tabel
# baru tetap memakai tabel lama, termasuk bila dihitung ulang sesudah tabel baru disimpan. Rumus tidak berubah.
PPH21_KUNCI: Dict[str, str] = {
    "ter": "hr.pph21.ter_table",
    "ptkp_ke_ter": "hr.pph21.ptkp_to_ter",
    "ptkp": "hr.ptkp_table",
    "pasal17": "hr.pph21.pasal17_table",
    "biaya_jabatan_pct": "hr.pph21.biaya_jabatan_pct",
    "biaya_jabatan_maks": "hr.pph21.biaya_jabatan_maks_bulanan",
}


def _akhir_hari_wib(tanggal: str):
    """Akhir hari `tanggal` (TTTT-BB-HH) waktu WIB, sebagai datetime UTC — titik baca pengaturan bertanggal."""
    from datetime import date, datetime, time, timezone
    from services.analytics_time import WIB
    d = date.fromisoformat(str(tanggal)[:10])
    return datetime.combine(d, time.max, tzinfo=WIB).astimezone(timezone.utc)


def akhir_periode_gaji(period: str) -> str:
    """'2026-12' → '2026-12-31' (tanggal akhir periode gaji; K-13)."""
    import calendar
    try:
        y, m = int(str(period)[:4]), int(str(period)[5:7])
        return f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"
    except (ValueError, calendar.IllegalMonthError) as exc:
        raise ValueError(f"Periode gaji harus berbentuk TTTT-BB (diberi '{period}').") from exc


def _baris_tarif(rows: Any) -> List[Dict[str, Any]]:
    return [{"batas_atas": r.get("batas_atas"), "tarif_pct": float(r.get("tarif_pct") or 0)}
            for r in (rows or []) if isinstance(r, dict)]


async def aturan_pph21(tanggal: str) -> Dict[str, Any]:
    """Enam kunci PPh 21 yang BERLAKU pada akhir hari `tanggal` (WIB).

    Bentuk: {"ter": {"A": [{batas_atas, tarif_pct}, …], "B": …, "C": …}, "ptkp_ke_ter": {status: kategori},
    "ptkp": {status: rupiah setahun}, "pasal17": [{batas_atas, tarif_pct}, …], "biaya_jabatan_pct": persen,
    "biaya_jabatan_maks": rupiah sebulan}. `batas_atas` None = baris terakhir (tanpa batas)."""
    from services.config_resolver import resolve
    at = _akhir_hari_wib(tanggal)
    v = {nama: (await resolve(kunci, {}, at=at))["value"] for nama, kunci in PPH21_KUNCI.items()}
    ter: Dict[str, List[Dict[str, Any]]] = {}
    for r in v["ter"] or []:
        if isinstance(r, dict):
            ter.setdefault(str(r.get("kategori")), []).extend(_baris_tarif([r]))
    return {"ter": ter, "ptkp_ke_ter": dict(v["ptkp_ke_ter"] or {}), "ptkp": dict(v["ptkp"] or {}),
            "pasal17": _baris_tarif(v["pasal17"]), "biaya_jabatan_pct": float(v["biaya_jabatan_pct"] or 0),
            "biaya_jabatan_maks": float(v["biaya_jabatan_maks"] or 0)}


def pasal17_tax(pkp: float, aturan: Dict[str, Any]) -> float:
    tax, lower = 0.0, 0.0
    for row in aturan["pasal17"]:
        upper = INF if row["batas_atas"] is None else float(row["batas_atas"])
        rate = row["tarif_pct"] / 100
        if pkp <= lower:
            break
        tax += (min(pkp, upper) - lower) * rate
        lower = upper
    return round(tax, 2)


def annual_pph21(*, tax_gross: float, pension_deduction: float, months: int, ptkp_status: str,
                 aturan: Dict[str, Any]) -> Dict[str, float]:
    """HR-01 — PPh21 setahun/bagian tahun (penghasilan aktual, PTKP setahun penuh). PK-46: angka dari `aturan`."""
    biaya_jabatan = min(tax_gross * (aturan["biaya_jabatan_pct"] / 100), aturan["biaya_jabatan_maks"] * max(1, months))
    neto = tax_gross - biaya_jabatan - pension_deduction
    tabel_ptkp = aturan["ptkp"]
    status = ptkp_status if ptkp_status in tabel_ptkp else "TK0"   # status tak dikenal → TK0 (perilaku kode lama)
    if status not in tabel_ptkp:
        raise ValueError(f"Status PTKP '{ptkp_status}' tidak ada di tabel PTKP setahun, dan tabel itu tidak memuat TK0.")
    ptkp = float(tabel_ptkp[status])
    pkp = max(0.0, float(int(max(0.0, neto - ptkp) // 1000) * 1000))
    return {"tax_gross": round(tax_gross, 2), "biaya_jabatan": round(biaya_jabatan, 2),
            "pension_deduction": round(pension_deduction, 2), "neto": round(neto, 2), "ptkp": float(ptkp),
            "pkp": pkp, "annual_tax": pasal17_tax(pkp, aturan)}


def ter_rate(category: str, gross: float, aturan: Dict[str, Any]) -> float:
    """Baris pertama dengan `gross <= batas_atas`; baris terakhir (tanpa batas) menangkap sisanya.
    Kategori tak dikenal → kategori A (perilaku kode lama)."""
    table = aturan["ter"].get(category) or aturan["ter"].get("A") or []
    for row in table:
        if row["batas_atas"] is None or gross <= row["batas_atas"]:
            return row["tarif_pct"] / 100
    return table[-1]["tarif_pct"] / 100 if table else 0.0
# ── akhir blok PK-46 ──────────────────────────────────────────────────────────────────────────────────────────────────


def _pct(v: Any) -> float:
    """Config menyimpan rate sebagai persen (1.0 = 1%)."""
    return float(v or 0) / 100.0


def bpjs_breakdown(base: float, emp: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Dict, Dict, float, float]:
    b = cfg.get("bpjs", {})
    # FASE G-0 — `hr.feature_toggles.bpjs_kesehatan` & `bpjs_ketenagakerjaan` DULU tidak
    # pernah dibaca mesin payroll (setting tersembunyi tanpa efek). Sekarang benar-benar
    # mematikan komponen terkait pada slip gaji bila toggle-nya dimatikan.
    toggles = cfg.get("feature_toggles", {}) or {}
    # Temuan lama #17 — kepesertaan BPJS PER KARYAWAN (bpjs_kes_enabled / bpjs_tk_enabled) ikut dihormati.
    kes_on = bool(toggles.get("bpjs_kesehatan", True)) and emp.get("bpjs_kes_enabled", True) is not False
    tk_on = bool(toggles.get("bpjs_ketenagakerjaan", True)) and emp.get("bpjs_tk_enabled", True) is not False
    kes_ceil = float(b.get("kes_ceiling") or INF)
    jp_ceil = float(b.get("jp_ceiling") or INF)
    kes_base = min(base, kes_ceil)
    jp_base = min(base, jp_ceil)
    # JKK kelas risiko per karyawan (default kelas II) → rate dari jkk_classes.
    jkk_class = emp.get("jkk_risk_class") or "II"
    jkk_rate = 0.0
    for c in cfg.get("jkk_classes", []):
        if str(c.get("class")) == str(jkk_class):
            jkk_rate = _pct(c.get("rate"))
            break
    emp_b = {
        "kesehatan": round(kes_base * _pct(b.get("kes_rate_employee")), 2) if kes_on else 0.0,
        "jht": round(base * _pct(b.get("jht_rate_employee")), 2) if tk_on else 0.0,
        "jp": round(jp_base * _pct(b.get("jp_rate_employee")), 2) if tk_on else 0.0,
    }
    er_b = {
        "kesehatan": round(kes_base * _pct(b.get("kes_rate_employer")), 2) if kes_on else 0.0,
        "jht": round(base * _pct(b.get("jht_rate_employer")), 2) if tk_on else 0.0,
        "jp": round(jp_base * _pct(b.get("jp_rate_employer")), 2) if tk_on else 0.0,
        "jkk": round(base * jkk_rate, 2) if tk_on else 0.0,
        "jkm": round(base * _pct(b.get("jkm_rate_employer")), 2) if tk_on else 0.0,
    }
    return emp_b, er_b, round(sum(emp_b.values()), 2), round(sum(er_b.values()), 2)


def bpjs_info(emp: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, bool]]:
    """PY-T1 — persen tiap iuran BPJS (1.0 = 1 %, per kode undang-undang komponen) dan program yang aktif untuk
    karyawan ini ({"kes", "tk"}); aturan sakelar sama dengan `bpjs_breakdown`. Dipakai baris komponen slip & PDF."""
    b = cfg.get("bpjs", {}) or {}
    toggles = cfg.get("feature_toggles", {}) or {}
    on = {"kes": bool(toggles.get("bpjs_kesehatan", True)) and emp.get("bpjs_kes_enabled", True) is not False,
          "tk": bool(toggles.get("bpjs_ketenagakerjaan", True)) and emp.get("bpjs_tk_enabled", True) is not False}
    jkk = 0.0
    for c in cfg.get("jkk_classes", []) or []:
        if str(c.get("class")) == str(emp.get("jkk_risk_class") or "II"):
            jkk = float(c.get("rate") or 0)
            break
    rates = {"bpjs_kes_emp": b.get("kes_rate_employee"), "bpjs_jht_emp": b.get("jht_rate_employee"),
             "bpjs_jp_emp": b.get("jp_rate_employee"), "bpjs_kes_er": b.get("kes_rate_employer"),
             "bpjs_jht_er": b.get("jht_rate_employer"), "bpjs_jp_er": b.get("jp_rate_employer"),
             "bpjs_jkk_er": jkk, "bpjs_jkm_er": b.get("jkm_rate_employer")}
    return {k: float(v or 0) for k, v in rates.items()}, on


def overtime_hour_units(hours: float, day_type: str, six_day: bool) -> float:
    """HR-02 — PP 35/2021 ps.31: hari kerja 1,5× jam pertama + 2× berikutnya; hari istirahat/libur
    5 hari kerja: 2× 8 jam, 3× jam ke-9, 4× jam ke-10–11 (6 hari kerja: 7 jam / ke-8 / ke-9–10)."""
    tiers = [(1, 1.5), (INF, 2.0)] if day_type == "workday" else \
        ([(7, 2.0), (1, 3.0), (2, 4.0)] if six_day else [(8, 2.0), (1, 3.0), (2, 4.0)])
    units, left = 0.0, max(0.0, hours)
    for span, mult in tiers:
        take = min(left, span)
        units += take * mult
        left -= take
        if left <= 0:
            break
    return units


def overtime_units(hours: float, day_type: str, rl: Dict[str, Any]) -> float:
    """PY-T3 (PY-07) — jam-upah lembur menurut `hr.overtime.mode`: `flat` = jam × "Pengali upah lembur";
    `bertingkat` (bawaan) = `overtime_hour_units` (pola enam hari kerja dari `hr.overtime.work_days_per_week`).
    Dipakai penghitung slip dan simulator lembur Pusat Pengaturan (satu rumus)."""
    if rl.get("lembur_mode") == "flat":
        return hours * float(rl.get("lembur_pengali") or 0)
    return overtime_hour_units(hours, day_type, bool(rl.get("six_day")))


def _bulan(period: str) -> Tuple[str, str]:
    from services.hr_compensation_service import period_bounds
    p0, p1, _ = period_bounds(period)
    return p0, p1


async def overtime_events(emp_id: str, period: str, entity_id: str, cfg: Optional[Dict[str, Any]] = None, *,
                          rl: Optional[Dict[str, Any]] = None, cal: Any = None) -> List[Dict[str, Any]]:
    """HR-02/IX-04 — SATU event lembur per tanggal. Pengajuan formal approved mengesahkan tanggal itu
    (dan menggantikan usulan absensi); tanpa pengajuan, menit absensi hanya dihitung bila absensinya
    approved (flagged/belum disetujui tidak dibayar). Duplikat pengajuan pada tanggal sama → diambil satu.

    PY-T3 (PY-07, PY-08; K-39) — aturan dari Pengaturan (`hr_pay_rules.rules`): `hr.overtime.sumber` = `pengajuan` →
    hanya pengajuan yang disetujui; `absensi` → juga menit absensi untuk tanggal tanpa pengajuan, menit di bawah
    `hr.overtime.ambang_menit` diabaikan. Jenis hari dari kalender kerja PT (`hr_work_calendar`: hari libur PT +
    pola hari kerja seminggu). `cfg` tidak dipakai lagi (tanda tangan lama)."""
    from services import hr_pay_rules as _pr
    from services import hr_work_calendar as _wc
    if rl is None:
        rl = await _pr.rules(entity_id)
    if cal is None:
        p0, p1 = _bulan(period)
        cal = await _wc.calendar_for(entity_id, p0, p1, rl)
    scope = {"entity_id": entity_id} if entity_id and entity_id != "all" else {}
    by_date: Dict[str, Dict[str, Any]] = {}
    async for r in db.hr_overtime.find({"employee_id": emp_id, "status": "approved", "period": period, **scope},
                                       {"_id": 0, "id": 1, "date": 1, "minutes": 1, "rate_basis": 1}):
        cur = by_date.get(r["date"])
        if not cur or int(r.get("minutes") or 0) > cur["minutes"]:
            by_date[r["date"]] = {"date": r["date"], "source": "filed", "ref_id": r["id"],
                                  "minutes": int(r.get("minutes") or 0), "rate_basis": r.get("rate_basis") or "normal"}
    if rl.get("lembur_sumber") == "absensi":
        ambang = int(rl.get("lembur_ambang_menit") or 0)
        async for a in db.hr_attendance.find({"employee_id": emp_id, "date": {"$regex": f"^{period}"},
                                              "overtime_min": {"$gt": 0}, "approved": True,
                                              "method": {"$ne": "leave"}, **scope},
                                             {"_id": 0, "id": 1, "date": 1, "overtime_min": 1}):
            menit = int(a.get("overtime_min") or 0)
            if a["date"] not in by_date and menit >= ambang:
                by_date[a["date"]] = {"date": a["date"], "source": "attendance", "ref_id": a["id"],
                                      "minutes": menit, "rate_basis": "normal"}
    events = sorted(by_date.values(), key=lambda e: e["date"])
    for e in events:
        e["day_type"] = cal.day_type(e["date"], e.pop("rate_basis"))
    return events


def _overtime_amount(ot_base: float, events: List[Dict[str, Any]], rl: Dict[str, Any]) -> float:
    """Nominal lembur: upah sejam = dasar lembur (Σ komponen ber-`in_overtime_base`) ÷ `hr.overtime.hours_divisor`;
    tiap kejadian = jam-upah (`overtime_units`) × upah sejam, dibulatkan `bulatkan` (PY-T3)."""
    from services import hr_pay_rules as _pr
    divisor = int(rl.get("lembur_pembagi_jam") or 0) or 1
    hourly = ot_base / divisor if ot_base > 0 else 0.0
    total = 0.0
    for e in events:
        units = overtime_units(e["minutes"] / 60.0, e["day_type"], rl)
        e["hour_units"] = round(units, 4)
        e["amount"] = _pr.bulatkan(units * hourly, rl)
        total += e["amount"]
    return _pr.bulatkan(total, rl)


async def _prior_year_slips(emp_id: str, period: str, entity_id: str = "") -> List[Dict[str, Any]]:
    """Slip karyawan itu tahun pajak yang sama sebelum `period`. PY-T2 — hanya slip DI PT PROSES ITU (`entity_id`):
    tiap PT pemotong pajak tersendiri, karyawan yang pindah PT dihitung ulang tahunannya per PT (ASUMSI spesifikasi)."""
    year = period[:4]
    dead = [r["id"] async for r in db.hr_payroll_runs.find(
        {"status": {"$in": ["void", "cancelled", "rejected"]}}, {"_id": 0, "id": 1})]
    q: Dict[str, Any] = {"employee_id": emp_id, "period": {"$regex": f"^{year}-", "$lt": period},
                         "run_id": {"$nin": dead}}
    if entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    # PY-T1 — satu bulan bisa memuat beberapa proses (reguler, THR, susulan): batas 12 bulan × beberapa slip.
    return await db.hr_payslips.find(
        q, {"_id": 0, "period": 1, "gross": 1, "tax_gross": 1, "pph21": 1, "bpjs_emp": 1}).to_list(240)


def _tanggal_keluar(emp: Dict[str, Any]) -> str:
    """PK-45 (PY-05) — tanggal keluar karyawan: `separation_date` (ditulis master karyawan, routers/hr.py) → bila
    kosong `end_date` (data lama) → bila kosong `resign_date`. 10 huruf pertama (YYYY-MM-DD); "" bila tidak ada."""
    return str(emp.get("separation_date") or emp.get("end_date") or emp.get("resign_date") or "")[:10]


def _is_final_tax_period(emp: Dict[str, Any], period: str) -> bool:
    end = _tanggal_keluar(emp)
    return period.endswith("-12") or (bool(end) and end[:7] == period)


async def _commission_for(emp: Dict[str, Any], period: str, entity_id: str) -> float:
    uid = emp.get("user_id")
    if not uid:
        return 0.0
    u = await db.users.find_one({"id": uid}, {"_id": 0, "role": 1})
    if not u or category_of(u.get("role")) != "sales":
        return 0.0
    try:
        from services import sales_force_service as sf
        res = await sf.compute_commission(uid, period, entity_id=entity_id)
        return round(float(res.get("total_incentive", 0) or 0), 2)
    except Exception:
        return 0.0


async def _components_map(entity_id: str) -> Dict[str, Dict[str, Any]]:
    """PY-T1 — komponen gaji PT itu (isi awal dijamin); tanpa PT tunggal → isi awal bawaan (tanpa database)."""
    from services import hr_pay_components as _pc
    if not entity_id or entity_id == "all":
        return _pc.by_code(_pc.DEFAULT_COMPONENTS)
    return await _pc.components_for(entity_id)


async def _month_prior_index(entity_id: str, period: str, run: Optional[Dict[str, Any]] = None,
                             employee_ids: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """PY-T1 — {karyawan: slip-slipnya pada proses LAIN periode itu yang tidak dibatalkan/dianulir dan dibuat lebih dulu
    dari proses `run`} (tanpa `run` = pratinjau proses baru: semua proses hidup periode itu). Urut dibuat lebih dulu.
    Dua kueri per proses gaji (bukan per karyawan)."""
    q: Dict[str, Any] = {"period": period, "status": {"$nin": list(DEAD_STATUSES)}}
    if entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    if run:
        q["id"] = {"$ne": run.get("id")}
        q["created_at"] = {"$lt": run.get("created_at") or now_iso()}
    runs = {r["id"]: r async for r in db.hr_payroll_runs.find(q, {"_id": 0, "id": 1, "number": 1, "created_at": 1})}
    if not runs:
        return {}
    sq: Dict[str, Any] = {"run_id": {"$in": list(runs)}}
    if employee_ids is not None:
        sq["employee_id"] = {"$in": list(employee_ids)}
    out: Dict[str, List[Dict[str, Any]]] = {}
    async for r in db.hr_payslips.find(sq, {"_id": 0, "id": 1, "run_id": 1, "employee_id": 1, "period": 1, "gross": 1,
                                            "tax_gross": 1, "pph21": 1, "bpjs_emp": 1}):
        r["run_number"] = runs[r["run_id"]].get("number", "")
        r["_order"] = runs[r["run_id"]].get("created_at", "")
        out.setdefault(r["employee_id"], []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r["_order"])
    return out


def _amt(doc: Dict[str, Any], field: str) -> float:
    """Nominal kolom slip (kosong = 0)."""
    return float(doc.get(field) or 0)


def _slip_tax_gross(doc: Dict[str, Any]) -> float:
    """Bruto pajak slip; slip lama tanpa `tax_gross` → `gross`."""
    return _amt(doc, "tax_gross") if doc.get("tax_gross") is not None else _amt(doc, "gross")


def _run_type(run: Optional[Dict[str, Any]], run_type: Optional[str]) -> str:
    rt = (run or {}).get("run_type") or run_type or "regular"
    return rt if rt in ("regular", "thr", "susulan") else "regular"


_BELUM = object()   # penanda "saldo awal pajak belum dimuat pemanggil" (None = dimuat, tidak ada)


async def compute_payslip(emp: Dict[str, Any], period: str, entity_id: str,
                          cfg: Dict[str, Any], aturan: Optional[Dict[str, Any]] = None, *,
                          comps: Optional[Dict[str, Dict[str, Any]]] = None, run: Optional[Dict[str, Any]] = None,
                          run_type: Optional[str] = None, inputs: Optional[List[Dict[str, Any]]] = None,
                          month_prior: Optional[List[Dict[str, Any]]] = None, rl: Optional[Dict[str, Any]] = None,
                          cal: Any = None, tax_opening: Any = _BELUM) -> Dict[str, Any]:
    """Slip satu karyawan sebagai DAFTAR KOMPONEN (PY-T1); kolom lama slip diturunkan dari komponen
    (`hr_pay_components.derive_columns`), sehingga jurnal, PDF, ekspor, dan rekap pajak membaca angka yang sama.

    Proses reguler: gaji pokok, tunjangan per nama, lembur, komisi mesin, BPJS, PPh 21, dan masukan antrean. Proses THR /
    susulan: hanya masukan antrean + PPh 21 (tanpa BPJS — ASUMSI spesifikasi). `inputs` = masukan karyawan ini yang dimuat
    (proses: yang terambil `take_for_run`; pratinjau: yang `approved`); kosong + `run` = masukan yang dipakai proses itu.

    PPh 21 gabungan bulan: bruto pajak bulan = bruto pajak slip ini + Σ bruto pajak slip karyawan yang sama di proses lain
    periode itu yang hidup dan dibuat lebih dulu (`month_prior`); `pph21_month` = bruto pajak bulan × tarif(kategori,
    bruto pajak bulan); `pph21` slip ini = `pph21_month` − Σ `pph21` slip terdahulu bulan itu. Masa pajak terakhir
    (Desember / bulan keluar) = hitung ulang tahunan yang ikut memuat slip terdahulu bulan itu. Tarif dari tabel yang
    berlaku (PK-46, `aturan_pph21`); unit ini tidak mengubah isinya.

    PY-T3 — aturan hitung dari Pengaturan per PT (`rl` = `hr_pay_rules.rules`, `cal` = kalender kerja PT): lembur
    (sumber, menit minimal, cara pengali, jenis hari), dasar upah lembur = Σ komponen ber-`in_overtime_base`, dasar BPJS =
    Σ komponen ber-`in_bpjs_base`, semua angka lewat `bulatkan`, dan saldo awal pajak (`tax_opening`) pada masa pajak
    terakhir."""
    from services import hr_pay_components as _pc
    from services import hr_pay_inputs as _pi
    from services import hr_pay_rules as _pr
    from services import hr_work_calendar as _wc
    # PK-46 — `aturan` = aturan_pph21(akhir periode gaji); proses gaji membacanya sekali dan meneruskannya ke sini.
    if aturan is None:
        aturan = await aturan_pph21(akhir_periode_gaji(period))
    if comps is None:
        comps = await _components_map(entity_id)
    if rl is None:
        rl = await _pr.rules(entity_id)

    def bul(x: Any) -> float:
        return _pr.bulatkan(x, rl)
    rt = _run_type(run, run_type)
    if inputs is None:
        inputs = [i for i in await _pi.inputs_for_run(run["id"]) if i.get("employee_id") == emp["id"]] if run else []
    if month_prior is None:
        month_prior = (await _month_prior_index(entity_id, period, run, [emp["id"]])).get(emp["id"], [])
    # PY-T2 — gaji pokok & komponen tetap dari riwayat kompensasi yang berlaku pada periode itu (potongan menurut
    # `hr.prorata_perubahan_gaji` PT itu), bukan master saat dihitung. Karyawan tanpa riwayat → master (perilaku lama).
    segs: Optional[List[Dict[str, Any]]] = None
    if rt == "regular":
        from services import hr_compensation_service as _hc
        segs = emp.get("_segments")
        if segs is None:
            segs = await _hc.segments(emp["id"], entity_id, period, emp=emp)
        if not segs:   # dipanggil langsung untuk PT yang tidak menggajinya periode itu → nilai akhir periode sebulan
            segs = await _hc.full_month_segments(emp, entity_id, period)
        if cal is None:
            p0, p1 = _bulan(period)
            cal = await _wc.calendar_for(entity_id, p0, p1, rl)
    base = float(emp.get("base_salary") or 0)
    events: List[Dict[str, Any]] = []
    overtime, commission, ot_base, bpjs_base = 0.0, 0.0, 0.0, 0.0
    segs_slip = segs
    kehadiran: Optional[Dict[str, Any]] = None
    if rt == "regular":
        # PY-T3 (K-38) — prorata masuk/keluar & perubahan gaji hari kerja (bawaan mati → potongan tidak berubah).
        segs_slip = _pr.atur_potongan(segs, emp, period, rl, cal)
        commission = bul(await _commission_for(emp, period, entity_id))
        # PY-T3 — dasar upah lembur & dasar BPJS = Σ komponen bertanda (isi awal: Gaji Pokok saja = angka sebelumnya).
        dasar = _pc.segment_lines(comps, segs, run_type=rt) + [
            _pc.input_line(comps[i["component_code"]], i) for i in inputs or ()
            if _pc.allowed(comps.get(i.get("component_code") or ""), rt)
            and (comps.get(i.get("component_code") or "") or {}).get("calc") == "masukan"]
        ot_base = _pc.basis(comps, dasar, "in_overtime_base")
        bpjs_base = _pc.basis(comps, dasar, "in_bpjs_base")
        base = sum(float(ln["amount"]) for ln in dasar if ln.get("code") == "GAJI_POKOK")
        events = await overtime_events(emp["id"], period, entity_id, cfg, rl=rl, cal=cal)
        overtime = _overtime_amount(ot_base, events, rl)
        perlu_hadir = rl["potongan_alpha"] or rl["potongan_cuti_tanpa_gaji"] or rl["potongan_telat_per_menit"] > 0 \
            or any(c.get("calc") == "per_hari_hadir" and _pc.allowed(c, rt) for c in comps.values())
        if perlu_hadir:
            s0, e0 = _pr.masa_kerja(emp, period)
            kehadiran = await _pr.ringkasan_kehadiran(emp["id"], s0, e0, cal)
    ot_auto = sum(e["minutes"] for e in events if e["source"] == "attendance")
    ot_filed = sum(e["minutes"] for e in events if e["source"] == "filed")
    ot_min = ot_auto + ot_filed
    earn = _pc.earning_components(comps, run_type=rt, base=base, allowances=emp.get("allowances"),
                                  overtime=overtime, overtime_min=ot_min, commission=commission, inputs=inputs,
                                  segments=segs_slip)
    for ln in earn:
        ln["amount"] = bul(ln["amount"])
    if rt == "regular":
        # PY-T3 — komponen per hari hadir / persen gaji pokok (sesudah prorata) dan potongan absensi. Upah sehari =
        # Σ komponen ber-`prorate` sesudah prorata ÷ hari kerja bulan itu (kalender PT).
        gaji_pokok = sum(float(ln["amount"]) for ln in earn if ln.get("code") == "GAJI_POKOK")
        extra = _pc.rate_components(comps, run_type=rt, present_days=(kehadiran or {}).get("present_days", 0),
                                    base_salary=gaji_pokok)
        p0, p1 = _bulan(period)
        hk = cal.work_days(p0, p1)
        harian = _pc.basis(comps, earn, "prorate") / hk if hk else 0.0
        extra += _pc.attendance_deductions(comps, run_type=rt, kehadiran=kehadiran, daily=harian,
                                           per_minute=float(rl["potongan_telat_per_menit"] or 0),
                                           alpha_on=rl["potongan_alpha"], unpaid_on=rl["potongan_cuti_tanpa_gaji"])
        for ln in extra:
            ln["amount"] = bul(ln["amount"])
        earn += extra
    rates, on = bpjs_info(emp, cfg)
    if rt == "regular":
        emp_b, er_b, _, _ = bpjs_breakdown(bpjs_base, emp, cfg)
    else:   # ASUMSI spesifikasi — iuran BPJS hanya di proses reguler
        emp_b = {"kesehatan": 0.0, "jht": 0.0, "jp": 0.0}
        er_b = {"kesehatan": 0.0, "jht": 0.0, "jp": 0.0, "jkk": 0.0, "jkm": 0.0}
        on = {"kes": False, "tk": False}
    emp_b = {k: bul(v) for k, v in emp_b.items()}
    er_b = {k: bul(v) for k, v in er_b.items()}
    bpjs_lines = _pc.statutory_components(comps, run_type=rt, bpjs_emp=emp_b, bpjs_er=er_b, bpjs_rates=rates,
                                          bpjs_on=on)
    # HR-01 — bruto pajak memuat premi JKK, JKM & BPJS Kesehatan yang dibayar pemberi kerja (komponen tanggungan itu
    # bertanda kena pajak); potongan bertanda kena pajak (PY-T3) mengurangi.
    tax_gross = _pc.derive_columns(earn + bpjs_lines)["tax_gross"]
    ptkp = emp.get("ptkp_status") or "TK0"
    category = aturan["ptkp_ke_ter"].get(ptkp, "A")   # PK-46 — kategori dari pengaturan bertanggal
    # FASE G-0 — `hr.feature_toggles.pph21` kini benar-benar mengendalikan pemotongan PPh 21
    # (sebelumnya toggle ini tersimpan tetapi tidak pernah diperiksa mesin payroll).
    _pph21_on = bool((cfg.get("feature_toggles", {}) or {}).get("pph21", True))
    tax_on = bool(cfg.get("ter_enabled", True) and _pph21_on)
    prior_tg = bul(sum(_slip_tax_gross(p) for p in month_prior))
    prior_pph = bul(sum(_amt(p, "pph21") for p in month_prior))
    tg_month = bul(tax_gross + prior_tg)
    rate = ter_rate(category, tg_month, aturan) if tax_on else 0.0
    pph21_month = bul(tg_month * rate)
    pph21 = bul(pph21_month - prior_pph) if tax_on else 0.0
    pph21_method, annual = "ter", None
    if tax_on and _is_final_tax_period(emp, period):
        prior = await _prior_year_slips(emp["id"], period, entity_id) + month_prior
        pension = lambda s: float((s.get("bpjs_emp") or {}).get("jht", 0) or 0) + \
            float((s.get("bpjs_emp") or {}).get("jp", 0) or 0)  # noqa: E731
        # PY-T3 (PY-12) — saldo awal pajak: masa, bruto, iuran pensiun, dan PPh 21 yang dibayar di luar sistem tahun itu
        # ditambahkan sebelum hitung ulang setahun. Tarif, PTKP, biaya jabatan tetap dari aturan yang berlaku (PK-46).
        op = await _pr.tax_opening(entity_id, emp["id"], period[:4]) if tax_opening is _BELUM else tax_opening
        op = op or {}
        months = len({str(p.get("period") or "") for p in prior} | {period}) + int(op.get("months") or 0)
        annual = annual_pph21(
            tax_gross=tax_gross + sum(float(s.get("tax_gross", s.get("gross", 0)) or 0) for s in prior)
            + float(op.get("tax_gross") or 0),
            pension_deduction=pension({"bpjs_emp": emp_b}) + sum(pension(s) for s in prior)
            + float(op.get("pension_deduction") or 0),
            months=months, ptkp_status=ptkp, aturan=aturan)
        annual["prior_withheld"] = round(sum(float(s.get("pph21", 0) or 0) for s in prior)
                                         + float(op.get("pph21_withheld") or 0), 2)
        annual["months"] = months
        annual["opening"] = ({k: op.get(k) for k in ("year", "months", "tax_gross", "pension_deduction",
                                                     "pph21_withheld")} if op else None)
        # selisih negatif = lebih potong dikembalikan lewat slip ini (jurnal mendebit Hutang PPh 21)
        pph21 = bul(annual["annual_tax"] - annual["prior_withheld"])
        pph21_month = bul(pph21 + prior_pph)
        pph21_method, rate = "annual_pasal17", 0.0
    pph_lines = _pc.statutory_components(comps, run_type=rt, pph21=pph21, pph21_rate_pct=rate * 100,
                                         pph21_method=pph21_method)
    components = _pc.sort_components(earn + bpjs_lines + pph_lines, comps)
    cols = _pc.derive_columns(components)
    return {
        "employee_id": emp["id"], "employee_name": emp.get("name", ""),
        "user_id": emp.get("user_id", ""), "position": emp.get("position_name", ""),
        "run_type": rt, "ptkp_status": ptkp, "ter_category": category, "pph21_rate": rate,
        "base_salary": cols["base_salary"], "allowances": cols["allowances"],
        "overtime_min": ot_min, "overtime_auto_min": ot_auto, "overtime_filed_min": ot_filed,
        "overtime": cols["overtime"], "overtime_events": events, "commission": cols["commission"],
        "other_earnings": cols["other_earnings"], "salary_earnings": cols["salary_earnings"], "gross": cols["gross"],
        "tax_gross": cols["tax_gross"], "pph21_method": pph21_method, "pph21_annual": annual,
        "bpjs_emp": cols["bpjs_emp"], "bpjs_er": cols["bpjs_er"],
        "bpjs_emp_total": cols["bpjs_emp_total"], "bpjs_er_total": cols["bpjs_er_total"],
        "pph21": cols["pph21"], "pph21_month": pph21_month,
        "pph21_month_detail": {"tax_gross_month": tg_month, "rate": rate, "prior_pph21": prior_pph,
                               "prior": [{"run_id": p["run_id"], "run_number": p.get("run_number", ""),
                                          "slip_id": p.get("id", ""), "tax_gross": _slip_tax_gross(p),
                                          "pph21": _amt(p, "pph21")} for p in month_prior]},
        "other_deductions": cols["other_deductions"], "net": cols["net"], "components": components,
        # PY-T3 (02 §5 D3) — potret aturan hitung yang dipakai slip ini, dan dasar upah lembur & BPJS.
        "pay_rules": _pr.ringkas(rl), "overtime_base": bul(ot_base), "bpjs_base": bul(bpjs_base),
        "attendance_summary": ({k: v for k, v in kehadiran.items() if not k.endswith("_dates")} if kehadiran
                               else None),
        "bank": {"bank_name": emp.get("bank_name", ""), "acc_no": emp.get("bank_acc_no", ""),
                 "acc_name": emp.get("bank_acc_name", "")},
    }


def _empty_totals() -> Dict[str, float]:
    return {"employees": 0, "salary_earnings": 0.0, "commission": 0.0, "gross": 0.0,
            "bpjs_emp": 0.0, "bpjs_er": 0.0, "pph21": 0.0, "other_deductions": 0.0, "net": 0.0}


def _accumulate(totals: Dict[str, float], s: Dict[str, Any]) -> None:
    totals["employees"] += 1
    totals["salary_earnings"] += s["salary_earnings"]
    totals["commission"] += s["commission"]
    totals["gross"] += s["gross"]
    totals["bpjs_emp"] += s["bpjs_emp_total"]
    totals["bpjs_er"] += s["bpjs_er_total"]
    totals["pph21"] += s["pph21"]
    totals["other_deductions"] += float(s.get("other_deductions") or 0)   # PY-T1 — potongan lain (komponen)
    totals["net"] += s["net"]


def _round_totals(t: Dict[str, float]) -> Dict[str, float]:
    return {k: (v if k == "employees" else round(v, 2)) for k, v in t.items()}


async def _active_employees(entity_id: str, period: str = "") -> List[Dict[str, Any]]:
    # HR-01 — karyawan yang berhenti pada periode ini tetap digaji (masa pajak terakhir).
    # PK-45 (PY-05) — master karyawan menulis `separation_date`; `end_date` tetap dibaca untuk data lama.
    # PY-T2 — PT + periode: karyawan menurut PENUGASAN bertanggal berlaku (`employees_for_run`), bukan `entity_id` master.
    if period and entity_id and entity_id != "all":
        from services import hr_compensation_service as _hc
        from services import hr_pay_rules as _pr
        # PY-T3 (perbaikan cacat, tanpa sakelar) — karyawan yang tanggal masuknya sesudah akhir periode tidak digaji
        # periode itu (dulu ikut digaji sebulan penuh karena dipilih dari status aktif saja).
        return [e for e in await _hc.employees_for_run(entity_id, period) if not _pr.masuk_setelah(e, period)]
    awal = {"$regex": f"^{re.escape(period)}"}
    keluar = [{"separation_date": awal}, {"end_date": awal}]
    q: Dict[str, Any] = {"$or": [{"status": "active"}, {"status": {"$in": ["resigned", "inactive"]},
                                                       "$or": keluar}]} \
        if period else {"status": "active"}
    if entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    rows = await db.hr_employees.find(q, {"_id": 0}).to_list(2000)
    if period:
        from services import hr_pay_rules as _pr
        rows = [r for r in rows if not _pr.masuk_setelah(r, period)]   # PY-T3 — perbaikan tanggal masuk
    return [safe_doc(r) for r in rows]


async def _build_slips(entity_id: str, period: str, run_type: str, *, run: Optional[Dict[str, Any]] = None,
                       inputs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """PY-T1 — slip satu proses. Reguler: semua karyawan yang digaji periode itu (+ masukan mereka); THR/susulan: hanya
    karyawan yang punya masukan. `inputs` = masukan yang dimuat (terambil untuk proses / `approved` untuk pratinjau)."""
    # FASE E-4 (E4.5) — BPJS/PPh21/lembur mengikuti badan usaha yang digaji.
    from services import hr_pay_rules as _pr
    from services import hr_work_calendar as _wc
    cfg = await hr_service.get_hr_settings(entity_id)
    aturan = await aturan_pph21(akhir_periode_gaji(period))   # PK-46 — sekali per proses gaji
    comps = await _components_map(entity_id)                  # PY-T1 — komponen PT, sekali per proses gaji
    rl = await _pr.rules(entity_id)                           # PY-T3 — aturan hitung PT, sekali per proses gaji
    p0, p1 = _bulan(period)
    cal = await _wc.calendar_for(entity_id, p0, p1, rl)       # PY-T3 — hari libur PT + pola hari kerja
    openings = await _pr.tax_openings(entity_id, period[:4])  # PY-T3 — saldo awal pajak PT itu tahun itu
    per_emp: Dict[str, List[Dict[str, Any]]] = {}
    for inp in inputs or []:
        per_emp.setdefault(inp["employee_id"], []).append(inp)
    if run_type == "regular":
        emps = await _active_employees(entity_id, period)
    else:
        # PY-T2 — masukan sudah ber-PT (antrean per PT); karyawan yang pindah PT tetap dimuat di PT masukannya.
        emps = [safe_doc(e) for e in await db.hr_employees.find(
            {"id": {"$in": list(per_emp)}}, {"_id": 0}).to_list(len(per_emp) + 1)]
    prior = await _month_prior_index(entity_id, period, run)   # PPh 21 gabungan bulan — sekali per proses gaji
    slips: List[Dict[str, Any]] = []
    totals = _empty_totals()
    for emp in emps:
        s = await compute_payslip(emp, period, entity_id, cfg, aturan, comps=comps, run=run, run_type=run_type,
                                  inputs=per_emp.get(emp["id"], []), month_prior=prior.get(emp["id"], []),
                                  rl=rl, cal=cal, tax_opening=openings.get(emp["id"]))
        slips.append(s)
        _accumulate(totals, s)
    slips.sort(key=lambda x: x["employee_name"])
    return {"entity_id": entity_id, "period": period, "run_type": run_type,
            "commission_mode": cfg.get("payroll_commission_mode", "accrue_then_settle"),
            "payslips": slips, "totals": _round_totals(totals), "count": len(slips)}


def _check_run_input(period: str, run_type: str) -> Tuple[str, str]:
    from services import hr_pay_inputs as _pi
    p = _pi.check_period(period)   # PY-13 — "Periode harus berbentuk TTTT-BB, mis. 2026-10."
    rt = run_type or "regular"
    if rt not in ("regular", "thr", "susulan"):
        raise ValueError("Jenis proses gaji harus Reguler, THR, atau Susulan.")
    return p, rt


def _no_input_msg(period: str, run_type: str) -> str:
    from services import periodic_posting
    lbl = periodic_posting.label_periode(period)
    if run_type == "thr":
        return f"Tidak ada masukan THR yang disahkan untuk {lbl}."
    return f"Tidak ada masukan yang belum terpakai untuk {lbl}."


async def preview_run(entity_id: str, period: str, run_type: str = "regular") -> Dict[str, Any]:
    """Pratinjau tanpa menandai masukan (masukan `approved` periode itu ikut dihitung).

    Reguler yang SUDAH ada untuk periode itu = pratinjau hitung ulang proses itu (masukan yang dipakainya ikut; PPh 21
    gabungan bulan hanya memuat proses yang dibuat lebih dulu darinya). Selain itu proses baru dianggap dibuat terakhir:
    semua proses hidup periode itu menjadi "slip terdahulu bulan itu"."""
    from services import hr_pay_inputs as _pi
    period, run_type = _check_run_input(period, run_type)
    emp_ids = [e["id"] for e in await _active_employees(entity_id, period)] if run_type == "regular" else None
    inputs = await _pi.approved_for(entity_id, period, run_type, emp_ids)
    existing = await existing_run(entity_id, period) if run_type == "regular" else None
    if existing:
        inputs = await _pi.inputs_for_run(existing["id"]) + inputs
    return await _build_slips(entity_id, period, run_type, run=existing, inputs=inputs)


async def existing_run(entity_id: str, period: str) -> Optional[Dict[str, Any]]:
    """Proses gaji REGULER yang masih hidup untuk PT+periode (PK-22: `cancelled`/`void` tidak menghalangi proses baru;
    PY-T1: proses THR dan susulan tidak dihitung — proses lama tanpa `run_type` = reguler)."""
    return safe_doc(await db.hr_payroll_runs.find_one(
        {"entity_id": entity_id, "period": period, "status": {"$nin": list(DEAD_STATUSES)},
         "run_type": {"$in": ["regular", None]}}, {"_id": 0}))


def active_key_of(entity_id: str, period: str) -> str:
    """PY-T1 (D7) — kunci unik proses reguler hidup (`hr_payroll_runs.uq_active_key`)."""
    return f"{entity_id}:{period}:regular"


async def _next_seq(entity_id: str, period: str, run_type: str) -> int:
    q: Dict[str, Any] = {"entity_id": entity_id, "period": period}
    q["run_type"] = {"$in": ["regular", None]} if run_type == "regular" else run_type
    return await db.hr_payroll_runs.count_documents(q) + 1


async def _slip_docs(run: Dict[str, Any], slips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for s in slips:
        snum = await next_doc_number("hr_payslips", "number", "SLIP-", entity_id=run["entity_id"])
        out.append({"id": new_id("slip"), "number": snum, "run_id": run["id"], "entity_id": run["entity_id"],
                    "period": run["period"], "status": "draft", "pdf_url": "", **s,
                    "created_at": now_iso(), "updated_at": now_iso()})
    return out


async def create_run(entity_id: str, period: str, actor: Dict[str, Any], run_type: str = "regular") -> Dict[str, Any]:
    """Buat proses gaji (PY-T1): `regular` (satu per PT per periode — permintaan kedua mengembalikan proses yang ada,
    dijamin indeks unik parsial `active_key`), `thr` (karyawan yang punya masukan THR), `susulan` (karyawan yang punya
    masukan belum terpakai). Masukan `approved` → `used` (`take_for_run`) SEBELUM slip dihitung, jadi slip memuat persis
    masukan yang ditandai proses ini; gagal → masukan dilepas dan proses dihapus (INV-ATOMIC-01)."""
    from pymongo.errors import DuplicateKeyError
    from services import hr_pay_inputs as _pi
    if not entity_id or entity_id == "all" or not period:
        raise ValueError("Payroll run butuh entitas spesifik & periode (mis. 2026-06).")
    period, run_type = _check_run_input(period, run_type)
    from services import periodic_posting
    periodic_posting.assert_period_started(period)   # PK-22 (FY-02) — periode yang belum dimulai ditolak
    emp_ids = None
    if run_type == "regular":
        found = await existing_run(entity_id, period)
        if found:
            return await get_run(found["id"])
        emp_ids = [e["id"] for e in await _active_employees(entity_id, period)]
        if not emp_ids:
            raise ValueError("Tidak ada karyawan aktif pada entitas ini.")
    elif not await _pi.approved_for(entity_id, period, run_type):
        raise ValueError(_no_input_msg(period, run_type))
    # Keputusan pemilik K-09 (26 Okt) — awalan "PR-" dulu sama dengan Permintaan Pembelian (KSC/PR-00002 · Payroll).
    # Penggajian BARU memakai "PAY-" (deret per badan usaha sendiri: KSC/PAY-00001); nomor lama TIDAK diubah.
    number = await next_doc_number("hr_payroll_runs", "number", PAYROLL_PREFIX, entity_id=entity_id)
    cfg = await hr_service.get_hr_settings(entity_id)
    run_id = new_id("prun")
    run = {
        "id": run_id, "number": number, "entity_id": entity_id, "period": period, "run_type": run_type,
        "seq": await _next_seq(entity_id, period, run_type),
        "status": "draft", "commission_mode": cfg.get("payroll_commission_mode", "accrue_then_settle"),
        "totals": _round_totals(_empty_totals()), "gl_posted": False, "journal_id": "", "journal_number": "",
        "incentive_journal_id": "", "paid_journal_id": "", "paid_journal_number": "",
        "approved_by": "", "approved_at": "", "posted_at": "", "paid_at": "",
        "created_by": actor.get("name", "system"), "created_by_id": actor.get("id", ""),
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    if run_type == "regular":
        run["active_key"] = active_key_of(entity_id, period)
    try:
        await db.hr_payroll_runs.insert_one(dict(run))
    except DuplicateKeyError:
        # PY-T1 (D7) — dua permintaan reguler bersamaan: indeks unik `active_key` menolak yang kalah; yang kalah
        # mengembalikan proses pemenang (perilaku "permintaan kedua mengembalikan proses yang ada").
        win = await db.hr_payroll_runs.find_one({"active_key": run["active_key"]}, {"_id": 0, "id": 1})
        if win:
            return await get_run(win["id"])
        raise
    try:
        taken = await _pi.take_for_run(entity_id, period, run_type, run_id, run_number=number, employee_ids=emp_ids)
        built = await _build_slips(entity_id, period, run_type, run=run, inputs=taken)
        ada = {s["employee_id"] for s in built["payslips"]}
        await _pi.release_inputs([i["id"] for i in taken if i["employee_id"] not in ada], run_id)
        if built["count"] == 0:
            raise ValueError("Tidak ada karyawan aktif pada entitas ini." if run_type == "regular"
                             else _no_input_msg(period, run_type))
        slip_docs = await _slip_docs(run, built["payslips"])
        if slip_docs:
            await db.hr_payslips.insert_many(slip_docs)
        await db.hr_payroll_runs.update_one({"id": run_id}, {"$set": {
            "totals": built["totals"], "commission_mode": built["commission_mode"], "updated_at": now_iso()}})
    except Exception:
        await rollback_run(run_id)
        raise
    return await get_run(run_id)


async def rollback_run(run_id: str) -> None:
    """Kompensasi: lepas masukan + hapus run + slip yang lahir dari permintaan yang gagal."""
    from services import hr_pay_inputs as _pi
    await _pi.release_for_run(run_id)
    await db.hr_payslips.delete_many({"run_id": run_id})
    await _refs.safe_unlink_all("payroll_run", run_id)   # PK-44 — INV-REF-04
    await db.hr_payroll_runs.delete_one({"id": run_id})


async def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    run = safe_doc(await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}))
    if not run:
        return None
    slips = [safe_doc(s) for s in await db.hr_payslips.find(
        {"run_id": run_id}, {"_id": 0}).sort("employee_name", 1).to_list(5000)]
    run["payslips"] = slips
    return run


async def list_runs(scope: Dict[str, Any], status: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = dict(scope or {})
    if status:
        q["status"] = status
    rows = await db.hr_payroll_runs.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [safe_doc(r) for r in rows]


async def _set_run(run_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    patch["updated_at"] = now_iso()
    await db.hr_payroll_runs.update_one({"id": run_id}, {"$set": patch})
    await db.hr_payslips.update_many({"run_id": run_id}, {"$set": {"status": patch.get("status", "draft"),
                                                                  "updated_at": now_iso()}}
                                     if "status" in patch else {"$set": {"updated_at": now_iso()}})
    return await get_run(run_id)


# ── UTANG ALUR F-6.7 (dibayar 2026-08-18): payroll punya langkah "Ajukan" ─────
# MASALAH: pengesahan payroll dulu bekerja langsung dari status `draft`, sehingga
# draf yang MASIH DIKERJAKAN HR tidak bisa dibedakan dari yang siap disahkan. Dua
# akibatnya nyata: (a) penyetuju tidak punya cara tahu mana yang menunggu dirinya —
# ia harus menebak dari daftar draf; (b) antrean "menunggu persetujuan" TIDAK BISA
# menghitung payroll tanpa ikut menghitung pekerjaan orang lain, jadi payroll
# sengaja dibebaskan dari penjaga antrean (`DOOR_EXEMPT` di
# `scripts/guardrails/verify_approval_queues.py`) dengan alasan bertanda "UTANG ALUR".
# Sekarang alurnya: draft → (Ajukan) pending_approval → approved → posted → paid,
# dan `pending_approval` itulah yang dihitung antrean `hr_payroll`.
async def submit_run(run_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """draft → pending_approval (HR menyatakan payroll ini SIAP disahkan)."""
    run = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise ValueError("Payroll run tidak ditemukan.")
    if run["status"] != "draft":
        raise ValueError(f"Hanya payroll draf yang bisa diajukan (status sekarang: "
                         f"'{run['status']}').")
    if not await db.hr_payslips.count_documents({"run_id": run_id}):
        raise ValueError("Payroll ini belum punya slip gaji — hitung dulu sebelum diajukan.")
    if run.get("inputs_stale_at"):   # PY-T1 — masukan yang dipakai dibatalkan sesudah dihitung
        raise PayrollConflict(f"Ada masukan yang dibatalkan sesudah penggajian {run.get('number')} dihitung — "
                              f"hitung ulang dulu sebelum diajukan.")
    # PK-22 — bersyarat status lama (dan tidak sedang dihitung ulang): pengajuan tidak menyalip hitung ulang/batal.
    # PY-T1 — juga tidak menyalip pembatalan masukan yang menandai proses ini perlu dihitung ulang.
    if not (await db.hr_payroll_runs.update_one(
            {"id": run_id, "status": "draft", "recalc_claim": {"$exists": False},
             "inputs_stale_at": {"$exists": False}},
            {"$set": {"status": "pending_approval"}})).modified_count:
        raise ValueError("Payroll ini sedang dihitung ulang / sudah berubah — muat ulang.")
    return await _set_run(run_id, {
        "status": "pending_approval",
        "submitted_by": actor.get("name", "system"), "submitted_at": now_iso(),
        "submitted_by_id": actor.get("id", ""),   # KF-T6 — pengaju andal untuk kontrol dua orang
        "reject_reason": "", "rejected_by": "", "rejected_at": ""})


async def recalculate_run(run_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """PK-22 (FY-06) — hitung ulang proses `draft` (data karyawan, lembur, komisi terbaru). Slip per karyawan diperbarui
    DI TEMPAT (id & nomor slip tetap), karyawan baru ditambah slip baru, yang tidak lagi termasuk dihapus; `totals`
    diperbarui; jejak `recalculated_at/_by`, `recalc_count`. → proses + slip.

    PY-T1 — masukan proses ini dilepas lebih dulu (`release_for_run`), lalu diambil lagi bersama masukan yang baru
    disahkan (`take_for_run`); masukan yang dibatalkan tidak ikut. Tanda "perlu dihitung ulang" dihapus. Gagal → masukan
    yang tadinya dipakai diambil kembali."""
    from services import hr_pay_inputs as _pi
    run = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise ValueError("Payroll run tidak ditemukan.")
    if run["status"] != "draft":
        raise _status_conflict(run, "dihitung ulang")
    rt = _run_type(run, None)
    emp_ids = None
    if rt == "regular":
        emp_ids = [e["id"] for e in await _active_employees(run["entity_id"], run["period"])]
        if not emp_ids:
            raise ValueError("Tidak ada karyawan aktif pada entitas ini.")
    elif not (await _pi.inputs_for_run(run_id) or await _pi.approved_for(run["entity_id"], run["period"], rt)):
        raise ValueError(_no_input_msg(run["period"], rt))
    # INV-ATOMIC-01 — klaim bersyarat (draf & tidak sedang dihitung ulang); ajukan/batal menunggu klaim lepas.
    claimed = await db.hr_payroll_runs.find_one_and_update(
        {"id": run_id, "status": "draft", "recalc_claim": {"$exists": False}},
        {"$set": {"recalc_claim": now_iso()}}, projection={"_id": 0, "id": 1})
    if not claimed:
        fresh = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}) or run
        if fresh.get("status") != "draft":
            raise _status_conflict(fresh, "dihitung ulang")
        raise PayrollConflict(f"Penggajian {run.get('number')} sedang dihitung ulang — muat ulang.")
    dipakai = [i["id"] for i in await _pi.inputs_for_run(run_id)]
    try:
        await _pi.release_for_run(run_id)
        taken = await _pi.take_for_run(run["entity_id"], run["period"], rt, run_id, run_number=run.get("number", ""),
                                       employee_ids=emp_ids)
        prev = await _build_slips(run["entity_id"], run["period"], rt, run=run, inputs=taken)
        if prev["count"] == 0:
            raise ValueError(_no_input_msg(run["period"], rt))
        ada = {s["employee_id"] for s in prev["payslips"]}
        await _pi.release_inputs([i["id"] for i in taken if i["employee_id"] not in ada], run_id)
    except Exception:
        await _pi.release_for_run(run_id)
        await _pi.retake_inputs(dipakai, run_id, run.get("number", ""))
        await db.hr_payroll_runs.update_one({"id": run_id}, {"$unset": {"recalc_claim": ""}})
        raise
    try:
        lama = {sl["employee_id"]: sl async for sl in db.hr_payslips.find({"run_id": run_id}, {"_id": 0})}
        baru = set()
        for sl in prev["payslips"]:
            baru.add(sl["employee_id"])
            old = lama.get(sl["employee_id"])
            if old:
                keep = {k: old.get(k) for k in ("id", "number", "run_id", "entity_id", "period", "status", "pdf_url",
                                                 "created_at")}
                await db.hr_payslips.replace_one({"id": old["id"]}, {**keep, **sl, "updated_at": now_iso()})
            else:
                snum = await next_doc_number("hr_payslips", "number", "SLIP-", entity_id=run["entity_id"])
                await db.hr_payslips.insert_one({
                    "id": new_id("slip"), "number": snum, "run_id": run_id, "entity_id": run["entity_id"],
                    "period": run["period"], "status": "draft", "pdf_url": "", **sl,
                    "created_at": now_iso(), "updated_at": now_iso()})
        gone = [sl["id"] for eid, sl in lama.items() if eid not in baru]
        if gone:
            await db.hr_payslips.delete_many({"id": {"$in": gone}})
        await db.hr_payroll_runs.update_one({"id": run_id}, {
            "$set": {"totals": prev["totals"], "commission_mode": prev["commission_mode"],
                     "recalculated_at": now_iso(), "recalculated_by": actor.get("name", "system"),
                     "recalculated_by_id": actor.get("id", ""), "updated_at": now_iso()},
            "$inc": {"recalc_count": 1}, "$unset": {"inputs_stale_at": ""}})
    finally:
        await db.hr_payroll_runs.update_one({"id": run_id}, {"$unset": {"recalc_claim": ""}})
    return await get_run(run_id)


async def cancel_run(run_id: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """PK-22 (FY-06) — batalkan proses `draft`/`pending_approval`/`approved` (bersyarat status lama); slip ikut
    `cancelled`. Tanpa jurnal (belum diposting). Izin dipilih router menurut status (`payroll.create` untuk draf,
    `payroll.approve` untuk yang sudah diajukan/disahkan)."""
    run = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise ValueError("Payroll run tidak ditemukan.")
    if run["status"] not in CANCELLABLE:
        raise _status_conflict(run, "dibatalkan")
    alasan = _min_reason(reason)
    flt: Dict[str, Any] = {"id": run_id, "status": run["status"]}
    if run["status"] == "draft":
        flt["recalc_claim"] = {"$exists": False}
    # PY-T1 — proses yang batal melepas kunci "satu reguler hidup per PT per periode" dan masukan yang dipakainya.
    if not (await db.hr_payroll_runs.update_one(flt, {"$set": {"status": "cancelled"},
                                                      "$unset": {"active_key": ""}})).modified_count:
        fresh = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}) or run
        raise _status_conflict(fresh, "dibatalkan")
    from services import hr_pay_inputs as _pi
    await _pi.release_for_run(run_id)
    hist = list(run.get("decision_history") or [])
    hist.append({"action": "cancelled", "by": actor.get("name", "system"), "at": now_iso(), "reason": alasan,
                 "from_status": run["status"], "to_status": "cancelled"})
    return await _set_run(run_id, {
        "status": "cancelled", "cancel_reason": alasan, "cancelled_by": actor.get("name", "system"),
        "cancelled_by_id": actor.get("id", ""), "cancelled_at": now_iso(), "cancelled_from": run["status"],
        "decision_history": hist})


async def approve_run(run_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    run = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise ValueError("Payroll run tidak ditemukan.")
    if run["status"] not in ("pending_approval",):
        raise ValueError(
            f"Hanya payroll yang sudah DIAJUKAN bisa disahkan (status sekarang: "
            f"'{run['status']}'). Ajukan dulu dari layar Payroll."
            if run["status"] == "draft" else
            f"Run status '{run['status']}' tidak bisa di-approve.")
    # KF-T6 — pengaju (yang mengajukan proses) ≠ pengesah dari `kontrol.proses_gaji.*` (bawaan satu orang); nominal =
    # total gaji bersih proses ini.
    from services import dual_control as _dc
    await _dc.tolak_bila_pelaku_sama("proses_gaji", run, actor, run.get("entity_id", ""),
                                     nominal=float((run.get("totals") or {}).get("net") or 0),
                                     pengaju=[run.get("submitted_by_id") or run.get("submitted_by")])
    if not (await db.hr_payroll_runs.update_one({"id": run_id, "status": "pending_approval"},
                                                {"$set": {"status": "approved"}})).modified_count:
        fresh = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}) or run
        raise _status_conflict(fresh, "disahkan")
    return await _set_run(run_id, {"status": "approved", "approved_by": actor.get("name", "system"),
                                   "approved_by_id": actor.get("id", ""),   # PK-22 — id pelaku (KF-T6)
                                   "approved_at": now_iso()})


async def reject_run(run_id: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """pending_approval → draft, dengan ALASAN yang tersimpan di dokumennya.

    Alasan disimpan di dokumen (bukan hanya jejak audit) supaya HR yang membuka
    payrollnya besok tahu apa yang harus diperbaiki tanpa membuka layar lain.
    """
    run = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise ValueError("Payroll run tidak ditemukan.")
    if run["status"] != "pending_approval":
        raise ValueError(f"Hanya payroll yang sedang diajukan bisa dikembalikan "
                         f"(status sekarang: '{run['status']}').")
    if len((reason or "").strip()) < 5:   # K-14 (26 Okt): alasan minimum seragam 5 huruf
        raise ValueError("Alasan wajib diisi (minimal 5 huruf) supaya HR tahu apa yang harus diperbaiki.")
    hist = list(run.get("decision_history") or [])
    hist.append({"action": "rejected", "by": actor.get("name", "system"),
                 "at": now_iso(), "reason": reason.strip(),
                 "from_status": "pending_approval", "to_status": "draft"})
    if not (await db.hr_payroll_runs.update_one({"id": run_id, "status": "pending_approval"},
                                                {"$set": {"status": "draft"}})).modified_count:
        fresh = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}) or run
        raise _status_conflict(fresh, "dikembalikan ke draf")
    return await _set_run(run_id, {
        "status": "draft", "reject_reason": reason.strip(),
        "rejected_by": actor.get("name", "system"), "rejected_by_id": actor.get("id", ""), "rejected_at": now_iso(),
        "decision_history": hist})


async def _kontrol_dua_orang(run: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """KF-T6 / K-41 — pengaju (yang mengajukan proses) ≠ pelaku sahkan/posting/bayar bila `kontrol.proses_gaji.*`
    menuntut dua orang (bawaan satu orang). Nominal = total gaji bersih proses ini."""
    from services import dual_control as _dc
    await _dc.tolak_bila_pelaku_sama("proses_gaji", run, actor, run.get("entity_id", ""),
                                     nominal=float((run.get("totals") or {}).get("net") or 0),
                                     pengaju=[run.get("submitted_by_id") or run.get("submitted_by")])


async def post_run_gl(run_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """PK-22 (FY-02, FY-06, FY-08) — posting jurnal gaji (`02_STANDAR.md` §1).

    PERIKSA status `approved` + periode tanggal buku (`periodic_posting.journal_date`) terbuka + kontrol dua orang →
    NIAT klaim `approved → posting` (tanggal buku disimpan di `journal_date`) → JURNAL lewat `post_durable` dengan resep
    `posting_registry.post_payroll` (akrual insentif dari komisi slip lalu jurnal gaji, kunci = id proses) → `posted`.
    Jurnal gagal: status kembali `approved`, `gl_status="failed"` + `gl_error`, tampil di panel Posting Gagal (jenis
    `payroll_run`, ulang = fungsi ini). Periode tertutup → `ClosedPeriodError` sebelum tulisan apa pun."""
    from services import gl_service, periodic_posting
    from services import posting_registry as _reg
    run = await get_run(run_id)
    if not run:
        raise ValueError("Payroll run tidak ditemukan.")
    if run["status"] not in ("approved",):
        raise ValueError(f"Run status '{run['status']}' harus 'approved' sebelum posting GL.")
    journal_date = await periodic_posting.journal_date(run["entity_id"], run["period"])
    await gl_service.preflight_posting(run["entity_id"], journal_date)
    await _kontrol_dua_orang(run, actor)
    # P20 HR-05 — klaim CAS: posting bersamaan → satu menang, sisanya 400 (bukan 500 duplikat jurnal).
    if not (await db.hr_payroll_runs.update_one(
            {"id": run_id, "status": "approved"},
            {"$set": {"status": "posting", "journal_date": journal_date, "gl_status": "pending"}})).modified_count:
        raise ValueError("Payroll ini sedang/sudah diposting — muat ulang.")
    run["journal_date"] = journal_date
    name = actor.get("name", "system")
    try:
        src_id = await gl_service.payroll_source_id(run)
        res = await gl_service.post_durable("hr_payroll_runs", run_id, lambda: _reg.post_payroll(run, name),
                                            source_type="payroll_run", source_id=src_id)
    except Exception:
        await db.hr_payroll_runs.update_one({"id": run_id, "status": "posting"}, {"$set": {"status": "approved"}})
        raise
    if res["gl_status"] == "failed":
        await db.hr_payroll_runs.update_one({"id": run_id, "status": "posting"}, {"$set": {"status": "approved"}})
        return await get_run(run_id)
    je = res.get("journal") or {}
    if not je and res.get("journal_entry_id"):
        je = await db.journal_entries.find_one({"id": res["journal_entry_id"]}, {"_id": 0, "id": 1, "number": 1}) or {}
    patch = {"status": "posted", "gl_posted": True, "posted_at": now_iso(), "posted_by": name,
             "posted_by_id": actor.get("id", "")}
    if je:
        patch["journal_id"] = je.get("id", "")
        patch["journal_number"] = je.get("number", "")
        patch["incentive_journal_id"] = je.get("incentive_journal_id", "")
    return await _set_run(run_id, patch)


async def void_run(run_id: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """PK-22 (FY-06) — void proses `posted`: jurnal gaji dibalik bertanggal buku jurnal asal, proses & slip `void`.

    PERIKSA status `posted` (gaji yang sudah dibayar tidak bisa di-void — koreksinya proses susulan PY-T1) + alasan +
    periode tanggal buku terbuka → NIAT `posted → voiding` bersyarat (dua void bersamaan: satu menang) → JURNAL
    `gl_service.reverse_document("payroll_run", kunci jurnal, date=journal_date)` lewat `post_durable`
    (`void_gl_status`) → `void` + jejak. Gagal → kembali `posted`, galat dilempar (router 409)."""
    from services import gl_service, periodic_posting
    run = await get_run(run_id)
    if not run:
        raise ValueError("Payroll run tidak ditemukan.")
    if run["status"] != "posted":
        raise _status_conflict(run, "dianulir")
    alasan = _min_reason(reason)
    # PY-T4 — kas pembayaran yang jurnalnya gagal menahan proses di `posted`; anulir sekarang membuat jurnal bayar yang
    # menyusul mendebit hutang gaji proses yang sudah dibalik. Selesaikan pembayarannya dulu.
    from services.hr_payroll_pay import kas_bayar_hidup
    kas = await kas_bayar_hidup(run_id)
    if kas:
        raise PayrollConflict(f"Penggajian {run.get('number') or run_id} sudah punya kas pembayaran "
                              f"{kas.get('number') or ''}, jadi tidak bisa dianulir. Selesaikan pembayarannya dulu "
                              "(ulangi Bayar).")
    src_id = await gl_service.payroll_source_id(run)
    je = await db.journal_entries.find_one({"id": run.get("journal_id") or "__none__"}, {"_id": 0, "date": 1}) or \
        await db.journal_entries.find_one({"source_type": "payroll_run", "source_id": src_id,
                                           "status": {"$ne": "void"}}, {"_id": 0, "date": 1}) or {}
    journal_date = run.get("journal_date") or (je.get("date") or "")[:10] or \
        periodic_posting.akhir_periode(run["period"])
    await gl_service.preflight_posting(run["entity_id"], journal_date)
    if not (await db.hr_payroll_runs.update_one({"id": run_id, "status": "posted"},
                                                {"$set": {"status": "voiding"}})).modified_count:
        fresh = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}) or run
        raise _status_conflict(fresh, "dianulir")
    name = actor.get("name", "system")
    try:
        await gl_service.post_durable(
            "hr_payroll_runs", run_id,
            lambda: gl_service.reverse_document("payroll_run", src_id, reason=alasan, actor_name=name,
                                                date=journal_date),
            source_type="payroll_run_reversal", source_id=src_id, field="void_gl_status", raise_on_fail=True)
    except Exception as exc:
        await db.hr_payroll_runs.update_one({"id": run_id, "status": "voiding"}, {"$set": {"status": "posted"}})
        raise PayrollConflict(f"Jurnal pembalik gaji gagal: {exc}. Penggajian tetap berstatus Diposting.") from exc
    rev = await db.journal_entries.find_one({"source_type": "payroll_run_reversal", "source_id": src_id,
                                             "status": {"$ne": "void"}}, {"_id": 0, "id": 1, "number": 1}) or {}
    hist = list(run.get("decision_history") or [])
    hist.append({"action": "void", "by": name, "at": now_iso(), "reason": alasan,
                 "from_status": "posted", "to_status": "void"})
    # PY-T1 — proses yang dianulir melepas kunci reguler hidup dan masukannya (kembali `approved`, bisa dipakai lagi).
    from services import hr_pay_inputs as _pi
    await db.hr_payroll_runs.update_one({"id": run_id}, {"$unset": {"active_key": ""}})
    await _pi.release_for_run(run_id)
    return await _set_run(run_id, {
        "status": "void", "void_reason": alasan, "voided_by": name, "voided_by_id": actor.get("id", ""),
        "voided_at": now_iso(), "void_journal_id": rev.get("id", ""), "void_journal_number": rev.get("number", ""),
        "decision_history": hist})


# PY-T4 (PY-11) — bayar gaji pindah ke `services/hr_payroll_pay.py` (`pay_run`): rekening berperuntukan Gaji, tanggal
# bayar, daftar transfer, satu kas keluar lewat pembuat kas yang menjurnal Dr hutang gaji / Cr kas. Jalur lama (jurnal
# `payroll_pay` dari kode akun isi permintaan + kas `record_return_cash`) dihapus — pemanggilnya hanya router bayar.


async def overtime_impact(entity_id: str, period: str) -> Dict[str, Any]:
    """PY-T3 (K-39) — dampak `hr.overtime.sumber`: per karyawan yang digaji PT itu pada periode itu, menit lembur
    ABSENSI (disetujui, pada tanggal tanpa pengajuan, ≥ `hr.overtime.ambang_menit`) dan nilainya menurut aturan lembur
    PT itu. Pada sumber `pengajuan` menit ini tidak dibayar; pada `absensi` dibayar. Upah sejam = Σ gaji pokok &
    komponen tetap ber-`in_overtime_base` ÷ pembagi jam (masukan antrean tidak ikut — perkiraan)."""
    from services import hr_compensation_service as _hc
    from services import hr_pay_components as _pc
    from services import hr_pay_inputs as _pi
    from services import hr_pay_rules as _pr
    from services import hr_work_calendar as _wc
    period = _pi.check_period(period)
    rl = await _pr.rules(entity_id)
    p0, p1 = _bulan(period)
    cal = await _wc.calendar_for(entity_id, p0, p1, rl)
    comps = await _components_map(entity_id)
    abs_rl = {**rl, "lembur_sumber": "absensi"}
    rows: List[Dict[str, Any]] = []
    for emp in await _active_employees(entity_id, period):
        ev = [e for e in await overtime_events(emp["id"], period, entity_id, rl=abs_rl, cal=cal)
              if e["source"] == "attendance"]
        if not ev:
            continue
        segs = emp.get("_segments") or await _hc.segments(emp["id"], entity_id, period, emp=emp) or \
            await _hc.full_month_segments(emp, entity_id, period)
        ot_base = _pc.basis(comps, _pc.segment_lines(comps, segs), "in_overtime_base")
        amount = _overtime_amount(ot_base, ev, rl)
        rows.append({"employee_id": emp["id"], "employee_name": emp.get("name", ""), "code": emp.get("code", ""),
                     "days": len(ev), "minutes": sum(e["minutes"] for e in ev), "amount": amount,
                     "dates": [e["date"] for e in ev]})
    rows.sort(key=lambda r: (-r["amount"], r["employee_name"]))
    return {"entity_id": entity_id, "period": period, "sumber": rl["lembur_sumber"],
            "ambang_menit": rl["lembur_ambang_menit"], "rows": rows, "count": len(rows),
            "total_minutes": sum(r["minutes"] for r in rows),
            "total_amount": _pr.bulatkan(sum(r["amount"] for r in rows), rl)}


async def list_payslips(scope: Dict[str, Any], period: Optional[str] = None,
                        employee_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = dict(scope or {})
    if period:
        q["period"] = period
    if employee_id:
        q["employee_id"] = employee_id
    rows = await db.hr_payslips.find(q, {"_id": 0}).sort("period", -1).to_list(2000)
    return [safe_doc(r) for r in rows]


async def get_payslip(slip_id: str) -> Optional[Dict[str, Any]]:
    return safe_doc(await db.hr_payslips.find_one({"id": slip_id}, {"_id": 0}))
