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
WORK_HOURS_DIVISOR = 173  # jam kerja/bulan (rumus upah-sejam Kepmenaker)
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


def _sum_allowances(allowances: Any) -> float:
    if isinstance(allowances, (int, float)):
        return round(float(allowances), 2)
    total = 0.0
    if isinstance(allowances, list):
        for a in allowances:
            if isinstance(a, dict):
                total += float(a.get("amount", 0) or 0)
            elif isinstance(a, (int, float)):
                total += float(a)
    return round(total, 2)


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


def _day_type(d: str, rate_basis: str, ot_cfg: Dict[str, Any]) -> str:
    from datetime import date as _date
    if rate_basis == "holiday" or d in set(ot_cfg.get("holidays") or []):
        return "holiday"
    try:
        wd = _date.fromisoformat(d[:10]).weekday()
    except ValueError:
        wd = 0
    six_day = int(ot_cfg.get("work_days_per_week") or 5) == 6
    if rate_basis == "weekend" or wd == 6 or (wd == 5 and not six_day):
        return "rest"
    return "workday"


async def overtime_events(emp_id: str, period: str, entity_id: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """HR-02/IX-04 — SATU event lembur per tanggal. Pengajuan formal approved mengesahkan tanggal itu
    (dan menggantikan usulan absensi); tanpa pengajuan, menit absensi hanya dihitung bila absensinya
    approved (flagged/belum disetujui tidak dibayar). Duplikat pengajuan pada tanggal sama → diambil satu."""
    scope = {"entity_id": entity_id} if entity_id and entity_id != "all" else {}
    ot_cfg = cfg.get("overtime", {}) or {}
    by_date: Dict[str, Dict[str, Any]] = {}
    async for r in db.hr_overtime.find({"employee_id": emp_id, "status": "approved", "period": period, **scope},
                                       {"_id": 0, "id": 1, "date": 1, "minutes": 1, "rate_basis": 1}):
        cur = by_date.get(r["date"])
        if not cur or int(r.get("minutes") or 0) > cur["minutes"]:
            by_date[r["date"]] = {"date": r["date"], "source": "filed", "ref_id": r["id"],
                                  "minutes": int(r.get("minutes") or 0), "rate_basis": r.get("rate_basis") or "normal"}
    async for a in db.hr_attendance.find({"employee_id": emp_id, "date": {"$regex": f"^{period}"},
                                          "overtime_min": {"$gt": 0}, "approved": True,
                                          "method": {"$ne": "leave"}, **scope},
                                         {"_id": 0, "id": 1, "date": 1, "overtime_min": 1}):
        if a["date"] not in by_date:
            by_date[a["date"]] = {"date": a["date"], "source": "attendance", "ref_id": a["id"],
                                  "minutes": int(a.get("overtime_min") or 0), "rate_basis": "normal"}
    events = sorted(by_date.values(), key=lambda e: e["date"])
    for e in events:
        e["day_type"] = _day_type(e["date"], e.pop("rate_basis"), ot_cfg)
    return events


def _overtime_amount(base: float, events: List[Dict[str, Any]], cfg: Dict[str, Any]) -> float:
    ot = cfg.get("overtime", {}) or {}
    divisor = int(ot.get("hours_divisor", WORK_HOURS_DIVISOR) or WORK_HOURS_DIVISOR)
    six_day = int(ot.get("work_days_per_week") or 5) == 6
    hourly = base / divisor if base > 0 else 0.0
    total = 0.0
    for e in events:
        hours = e["minutes"] / 60.0
        if ot.get("mode") == "flat":  # kompatibilitas: pengali tunggal lama bila dipilih eksplisit
            units = hours * float(ot.get("multiplier", 1.5) or 1.5)
        else:
            units = overtime_hour_units(hours, e["day_type"], six_day)
        e["hour_units"] = round(units, 4)
        e["amount"] = round(units * hourly, 2)
        total += e["amount"]
    return round(total, 2)


async def _prior_year_slips(emp_id: str, period: str) -> List[Dict[str, Any]]:
    year = period[:4]
    dead = [r["id"] async for r in db.hr_payroll_runs.find(
        {"status": {"$in": ["void", "cancelled", "rejected"]}}, {"_id": 0, "id": 1})]
    return await db.hr_payslips.find(
        {"employee_id": emp_id, "period": {"$regex": f"^{year}-", "$lt": period}, "run_id": {"$nin": dead}},
        {"_id": 0, "period": 1, "gross": 1, "tax_gross": 1, "pph21": 1, "bpjs_emp": 1}).to_list(24)


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


async def compute_payslip(emp: Dict[str, Any], period: str, entity_id: str,
                          cfg: Dict[str, Any], aturan: Optional[Dict[str, Any]] = None, *,
                          comps: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    # PK-46 — `aturan` = aturan_pph21(akhir periode gaji); proses gaji membacanya sekali dan meneruskannya ke sini.
    if aturan is None:
        aturan = await aturan_pph21(akhir_periode_gaji(period))
    if comps is None:
        comps = await _components_map(entity_id)
    base = float(emp.get("base_salary") or 0)
    allowances = _sum_allowances(emp.get("allowances"))
    events = await overtime_events(emp["id"], period, entity_id, cfg)
    ot_auto = sum(e["minutes"] for e in events if e["source"] == "attendance")
    ot_filed = sum(e["minutes"] for e in events if e["source"] == "filed")
    ot_min = ot_auto + ot_filed
    overtime = _overtime_amount(base, events, cfg)
    commission = await _commission_for(emp, period, entity_id)
    salary_earnings = round(base + allowances + overtime, 2)
    gross = round(salary_earnings + commission, 2)
    emp_b, er_b, emp_total, er_total = bpjs_breakdown(base, emp, cfg)
    # HR-01 — bruto pajak memuat premi JKK, JKM & BPJS Kesehatan yang dibayar pemberi kerja.
    tax_gross = round(gross + er_b["jkk"] + er_b["jkm"] + er_b["kesehatan"], 2)
    ptkp = emp.get("ptkp_status") or "TK0"
    category = aturan["ptkp_ke_ter"].get(ptkp, "A")   # PK-46 — kategori dari pengaturan bertanggal
    # FASE G-0 — `hr.feature_toggles.pph21` kini benar-benar mengendalikan pemotongan PPh 21
    # (sebelumnya toggle ini tersimpan tetapi tidak pernah diperiksa mesin payroll).
    _pph21_on = bool((cfg.get("feature_toggles", {}) or {}).get("pph21", True))
    tax_on = bool(cfg.get("ter_enabled", True) and _pph21_on)
    rate = ter_rate(category, tax_gross, aturan) if tax_on else 0.0
    pph21 = round(tax_gross * rate, 2)
    pph21_method, annual = "ter", None
    if tax_on and _is_final_tax_period(emp, period):
        prior = await _prior_year_slips(emp["id"], period)
        pension = lambda s: float((s.get("bpjs_emp") or {}).get("jht", 0) or 0) + \
            float((s.get("bpjs_emp") or {}).get("jp", 0) or 0)  # noqa: E731
        annual = annual_pph21(
            tax_gross=tax_gross + sum(float(s.get("tax_gross", s.get("gross", 0)) or 0) for s in prior),
            pension_deduction=pension({"bpjs_emp": emp_b}) + sum(pension(s) for s in prior),
            months=len(prior) + 1, ptkp_status=ptkp, aturan=aturan)
        annual["prior_withheld"] = round(sum(float(s.get("pph21", 0) or 0) for s in prior), 2)
        annual["months"] = len(prior) + 1
        # selisih negatif = lebih potong dikembalikan lewat slip ini (jurnal mendebit Hutang PPh 21)
        pph21 = round(annual["annual_tax"] - annual["prior_withheld"], 2)
        pph21_method, rate = "annual_pasal17", 0.0
    net = round(gross - emp_total - pph21, 2)
    # PY-T1 (a) — daftar komponen slip dibangun DI SAMPING kolom lama (kolom lama belum diturunkan darinya); uji PY-T1
    # U1/U2 membuktikan Σ komponen per kolom = kolom lama.
    from services import hr_pay_components as _pc
    rates, on = bpjs_info(emp, cfg)
    components = _pc.sort_components(
        _pc.earning_components(comps, base=base, allowances=emp.get("allowances"), overtime=overtime,
                               overtime_min=ot_min, commission=commission)
        + _pc.statutory_components(comps, bpjs_emp=emp_b, bpjs_er=er_b, bpjs_rates=rates, bpjs_on=on, pph21=pph21,
                                   pph21_rate_pct=rate * 100, pph21_method=pph21_method), comps)
    return {
        "employee_id": emp["id"], "employee_name": emp.get("name", ""),
        "user_id": emp.get("user_id", ""), "position": emp.get("position_name", ""),
        "ptkp_status": ptkp, "ter_category": category, "pph21_rate": rate,
        "base_salary": round(base, 2), "allowances": allowances,
        "overtime_min": ot_min, "overtime_auto_min": ot_auto, "overtime_filed_min": ot_filed,
        "overtime": overtime, "overtime_events": events, "commission": commission,
        "salary_earnings": salary_earnings, "gross": gross, "tax_gross": tax_gross,
        "pph21_method": pph21_method, "pph21_annual": annual,
        "bpjs_emp": emp_b, "bpjs_er": er_b,
        "bpjs_emp_total": emp_total, "bpjs_er_total": er_total,
        "pph21": pph21, "net": net, "components": components,
        "bank": {"bank_name": emp.get("bank_name", ""), "acc_no": emp.get("bank_acc_no", ""),
                 "acc_name": emp.get("bank_acc_name", "")},
    }


def _empty_totals() -> Dict[str, float]:
    return {"employees": 0, "salary_earnings": 0.0, "commission": 0.0, "gross": 0.0,
            "bpjs_emp": 0.0, "bpjs_er": 0.0, "pph21": 0.0, "net": 0.0}


def _accumulate(totals: Dict[str, float], s: Dict[str, Any]) -> None:
    totals["employees"] += 1
    totals["salary_earnings"] += s["salary_earnings"]
    totals["commission"] += s["commission"]
    totals["gross"] += s["gross"]
    totals["bpjs_emp"] += s["bpjs_emp_total"]
    totals["bpjs_er"] += s["bpjs_er_total"]
    totals["pph21"] += s["pph21"]
    totals["net"] += s["net"]


def _round_totals(t: Dict[str, float]) -> Dict[str, float]:
    return {k: (v if k == "employees" else round(v, 2)) for k, v in t.items()}


async def _active_employees(entity_id: str, period: str = "") -> List[Dict[str, Any]]:
    # HR-01 — karyawan yang berhenti pada periode ini tetap digaji (masa pajak terakhir).
    # PK-45 (PY-05) — master karyawan menulis `separation_date`; `end_date` tetap dibaca untuk data lama.
    awal = {"$regex": f"^{re.escape(period)}"}
    keluar = [{"separation_date": awal}, {"end_date": awal}]
    q: Dict[str, Any] = {"$or": [{"status": "active"}, {"status": {"$in": ["resigned", "inactive"]},
                                                       "$or": keluar}]} \
        if period else {"status": "active"}
    if entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    rows = await db.hr_employees.find(q, {"_id": 0}).to_list(2000)
    return [safe_doc(r) for r in rows]


async def preview_run(entity_id: str, period: str) -> Dict[str, Any]:
    # FASE E-4 (E4.5) — BPJS/PPh21/lembur mengikuti badan usaha yang digaji.
    cfg = await hr_service.get_hr_settings(entity_id)
    aturan = await aturan_pph21(akhir_periode_gaji(period))   # PK-46 — sekali per proses gaji
    comps = await _components_map(entity_id)                  # PY-T1 — komponen PT, sekali per proses gaji
    emps = await _active_employees(entity_id, period)
    slips: List[Dict[str, Any]] = []
    totals = _empty_totals()
    for emp in emps:
        s = await compute_payslip(emp, period, entity_id, cfg, aturan, comps=comps)
        slips.append(s)
        _accumulate(totals, s)
    slips.sort(key=lambda x: x["employee_name"])
    return {"entity_id": entity_id, "period": period,
            "commission_mode": cfg.get("payroll_commission_mode", "accrue_then_settle"),
            "payslips": slips, "totals": _round_totals(totals), "count": len(slips)}


async def existing_run(entity_id: str, period: str) -> Optional[Dict[str, Any]]:
    """Proses gaji yang masih hidup untuk PT+periode (PK-22: `cancelled`/`void` tidak menghalangi proses baru)."""
    return safe_doc(await db.hr_payroll_runs.find_one(
        {"entity_id": entity_id, "period": period, "status": {"$nin": list(DEAD_STATUSES)}}, {"_id": 0}))


async def create_run(entity_id: str, period: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    if not entity_id or entity_id == "all" or not period:
        raise ValueError("Payroll run butuh entitas spesifik & periode (mis. 2026-06).")
    from services import periodic_posting
    periodic_posting.assert_period_started(period)   # PK-22 (FY-02) — periode yang belum dimulai ditolak
    found = await existing_run(entity_id, period)
    if found:
        return await get_run(found["id"])
    prev = await preview_run(entity_id, period)
    if prev["count"] == 0:
        raise ValueError("Tidak ada karyawan aktif pada entitas ini.")
    # Keputusan pemilik K-09 (26 Okt) — awalan "PR-" dulu sama dengan Permintaan Pembelian (KSC/PR-00002 · Payroll).
    # Penggajian BARU memakai "PAY-" (deret per badan usaha sendiri: KSC/PAY-00001); nomor lama TIDAK diubah.
    number = await next_doc_number("hr_payroll_runs", "number", PAYROLL_PREFIX, entity_id=entity_id)
    run_id = new_id("prun")
    run = {
        "id": run_id, "number": number, "entity_id": entity_id, "period": period,
        "status": "draft", "commission_mode": prev["commission_mode"],
        "totals": prev["totals"], "gl_posted": False, "journal_id": "", "journal_number": "",
        "incentive_journal_id": "", "paid_journal_id": "", "paid_journal_number": "",
        "approved_by": "", "approved_at": "", "posted_at": "", "paid_at": "",
        "created_by": actor.get("name", "system"), "created_by_id": actor.get("id", ""),
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.hr_payroll_runs.insert_one(run)
    # INV-ATOMIC-01 — kompensasi saga: run adalah dokumen baru per permintaan. Bila balapan
    # melahirkan run kedua untuk entitas+periode yang sama, atau slip gagal ditulis, run
    # milik permintaan ini dihapus lagi (tanpa slip yatim).
    dup = await db.hr_payroll_runs.find_one(
        {"entity_id": entity_id, "period": period, "id": {"$ne": run_id},
         "status": {"$nin": list(DEAD_STATUSES)}}, {"_id": 0, "id": 1, "created_at": 1})
    if dup and dup.get("created_at", "") <= run["created_at"]:
        await _refs.safe_unlink_all("payroll_run", run_id)   # PK-44 — INV-REF-04 (run kini jenis dokumen ber-refs)
        await db.hr_payroll_runs.delete_one({"id": run_id})
        return await get_run(dup["id"])
    try:
        slip_docs = []
        for s in prev["payslips"]:
            sid = new_id("slip")
            snum = await next_doc_number("hr_payslips", "number", "SLIP-", entity_id=entity_id)
            slip_docs.append({
                "id": sid, "number": snum, "run_id": run_id, "entity_id": entity_id, "period": period,
                "status": "draft", "pdf_url": "", **s,
                "created_at": now_iso(), "updated_at": now_iso(),
            })
        if slip_docs:
            await db.hr_payslips.insert_many(slip_docs)
    except Exception:
        await rollback_run(run_id)
        raise
    return await get_run(run_id)


async def rollback_run(run_id: str) -> None:
    """Kompensasi: hapus run + slip yang lahir dari permintaan yang gagal."""
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
    # PK-22 — bersyarat status lama (dan tidak sedang dihitung ulang): pengajuan tidak menyalip hitung ulang/batal.
    if not (await db.hr_payroll_runs.update_one(
            {"id": run_id, "status": "draft", "recalc_claim": {"$exists": False}},
            {"$set": {"status": "pending_approval"}})).modified_count:
        raise ValueError("Payroll ini sedang dihitung ulang / sudah berubah — muat ulang.")
    return await _set_run(run_id, {
        "status": "pending_approval",
        "submitted_by": actor.get("name", "system"), "submitted_at": now_iso(),
        "submitted_by_id": actor.get("id", ""),   # KF-T6 — pengaju andal untuk kontrol dua orang
        "reject_reason": "", "rejected_by": "", "rejected_at": ""})


async def recalculate_run(run_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """PK-22 (FY-06) — hitung ulang proses `draft` dari `preview_run` (data karyawan, lembur, komisi terbaru). Slip per
    karyawan diperbarui DI TEMPAT (id & nomor slip tetap), karyawan baru ditambah slip baru, yang tidak lagi termasuk
    dihapus; `totals` diperbarui; jejak `recalculated_at/_by`, `recalc_count`. → proses + slip."""
    run = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise ValueError("Payroll run tidak ditemukan.")
    if run["status"] != "draft":
        raise _status_conflict(run, "dihitung ulang")
    prev = await preview_run(run["entity_id"], run["period"])
    if prev["count"] == 0:
        raise ValueError("Tidak ada karyawan aktif pada entitas ini.")
    # INV-ATOMIC-01 — klaim bersyarat (draf & tidak sedang dihitung ulang); ajukan/batal menunggu klaim lepas.
    claimed = await db.hr_payroll_runs.find_one_and_update(
        {"id": run_id, "status": "draft", "recalc_claim": {"$exists": False}},
        {"$set": {"recalc_claim": now_iso()}}, projection={"_id": 0, "id": 1})
    if not claimed:
        fresh = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}) or run
        if fresh.get("status") != "draft":
            raise _status_conflict(fresh, "dihitung ulang")
        raise PayrollConflict(f"Penggajian {run.get('number')} sedang dihitung ulang — muat ulang.")
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
            "$inc": {"recalc_count": 1}})
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
    if not (await db.hr_payroll_runs.update_one(flt, {"$set": {"status": "cancelled"}})).modified_count:
        fresh = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}) or run
        raise _status_conflict(fresh, "dibatalkan")
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
    return await _set_run(run_id, {
        "status": "void", "void_reason": alasan, "voided_by": name, "voided_by_id": actor.get("id", ""),
        "voided_at": now_iso(), "void_journal_id": rev.get("id", ""), "void_journal_number": rev.get("number", ""),
        "decision_history": hist})


async def pay_run(run_id: str, actor: Dict[str, Any], cash_account: Optional[str] = None,
                  account_id: str = "") -> Dict[str, Any]:
    """PK-20 — `account_id` = rekening sumber (`bank_accounts`, milik PT proses gaji); kosong = rekening tunggal PT untuk
    jenis kas akun `cash_account`. Diperiksa SEBELUM jurnal gaji; layar menyusul di PY-T4.

    PK-22 (FY-09) — `cash_account` hanya akun pemetaan `kas_bank.kas_besar`/`kas_bank.kas_kecil` PT itu (dulu cukup
    "anak 1-1000", jadi piutang & persediaan lolos) — diperiksa SEBELUM klaim; kontrol dua orang; jurnal bayar lewat
    `post_durable` (`pay_gl_status`), kunci = id proses."""
    from services import gl_service
    from services import cash_ledger
    run = await get_run(run_id)
    if not run:
        raise ValueError("Payroll run tidak ditemukan.")
    if run["status"] not in ("posted",):
        raise ValueError(f"Run status '{run['status']}' harus 'posted' sebelum dibayar.")
    net = round(float((run.get("totals") or {}).get("net", 0) or 0), 2)
    if net > 0.01:
        cash_account = await gl_service.assert_payroll_cash_account(run.get("entity_id", ""), cash_account)
    await _kontrol_dua_orang(run, actor)
    if net > 0.01:
        account_id = (await cash_ledger.periksa_rekening(
            run.get("entity_id", ""), account_id, cash_ledger.cash_type_for(cash_account or "1-1100")))["account_id"]
        await gl_service.preflight_posting(run.get("entity_id", ""), now_iso())
    if not (await db.hr_payroll_runs.update_one({"id": run_id, "status": "posted"},
                                                {"$set": {"status": "paying"}})).modified_count:
        raise ValueError("Payroll ini sedang/sudah dibayar — muat ulang.")
    name = actor.get("name", "system")
    try:
        src_id = await gl_service.payroll_source_id(run)
        res = await gl_service.post_durable(
            "hr_payroll_runs", run_id, lambda: gl_service.pay_payroll_run(run, name, cash_account),
            source_type="payroll_pay", source_id=src_id, field="pay_gl_status", raise_on_fail=True)
    except Exception:
        await db.hr_payroll_runs.update_one({"id": run_id, "status": "paying"}, {"$set": {"status": "posted"}})
        raise
    je = res.get("journal") or {}
    if not je and res.get("journal_entry_id"):
        je = await db.journal_entries.find_one({"id": res["journal_entry_id"]}, {"_id": 0}) or {}
    patch = {"status": "paid", "paid_at": now_iso(), "paid_by": name, "paid_by_id": actor.get("id", "")}
    if je:
        patch["paid_journal_id"] = je.get("id", "")
        patch["paid_journal_number"] = je.get("number", "")
        # W2-022 — kredit kas GL WAJIB punya pasangan di buku kas (idempotent per run).
        acc_code = next((ln.get("account_code") for ln in je.get("lines") or [] if float(ln.get("credit") or 0) > 0),
                        cash_account or "1-1100")
        try:
            ctxn = await cash_ledger.record_return_cash(
                direction="out", amount=net, account_code=acc_code, category="Pembayaran Gaji",
                description=f"Pembayaran gaji {run.get('period', '')} ({run.get('number', '')})",
                entity_id=run.get("entity_id", ""), ref_type="payroll_run", ref_id=run_id,
                journal_entry_id=je.get("id", ""), created_by=name, account_id=account_id)
        except Exception as exc:
            await db.hr_payroll_runs.update_one({"id": run_id, "status": "paying"}, {"$set": {
                "status": "posted", "cash_error": str(exc)[:300]}})   # retry: jurnal idempotent, kas dilengkapi
            raise ValueError(f"Jurnal gaji tercatat, tetapi buku kas gagal — ulangi Bayar. ({exc})") from exc
        if ctxn:
            patch["cash_txn_id"] = ctxn.get("id", "")
            patch["cash_txn_number"] = ctxn.get("number", "")
    return await _set_run(run_id, patch)


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


async def my_payslips(user: Dict[str, Any], period: Optional[str] = None) -> Dict[str, Any]:
    emp = await db.hr_employees.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1, "name": 1})
    if not emp:
        return {"employee": None, "payslips": []}
    q: Dict[str, Any] = {"employee_id": emp["id"], "status": {"$in": ["posted", "paid", "approved"]}}
    if period:
        q["period"] = period
    rows = await db.hr_payslips.find(q, {"_id": 0}).sort("period", -1).to_list(200)
    return {"employee": {"id": emp["id"], "name": emp.get("name", "")},
            "payslips": [safe_doc(r) for r in rows]}
