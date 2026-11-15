"""PY-T2 (PY-09, K-37, K-38) — riwayat kompensasi dan penugasan PT karyawan bertanggal berlaku.

Gaji pokok, komponen tetap bulanan, dan PT tempat karyawan digaji tidak lagi ditimpa di master karyawan. Tiap perubahan
adalah satu baris bertanggal berlaku yang diusulkan (`pending`) lalu disahkan (`approved`):

  * `hr_compensation_history` (`hcomp_…`) — `base_salary` + `fixed_components[]` ({component_code, label, amount};
    komponen `tetap_bulanan` PT selain Gaji Pokok, mis. tunjangan per nama).
  * `hr_employee_assignments` (`hasg_…`) — PT (`entity_id`), departemen, jabatan.

Hanya baris `approved` yang dibaca proses gaji. `effective_to` diisi sistem: sehari sebelum baris sah berikutnya
(`_rechain`). Baris sah PALING AWAL dianggap berlaku sejak awal (prorata masuk/keluar tengah bulan = PY-T3), jadi
potongan periode hanya lahir dari PERUBAHAN. Karyawan tanpa riwayat (data lama sebelum migrasi
`scripts/migrate_hr_compensation_py_t2.py`) dibaca dari master seperti sebelum unit ini.

`base_salary`, `allowances`, dan `entity_id` di `hr_employees` menjadi nilai turunan = baris yang berlaku hari ini (WIB),
ditulis hanya oleh `apply_effective` (saat pengesahan dan tugas terjadwal harian `hr_compensation_effective`);
invarian `INV-PY-2` (`scripts/verify_data_integrity.py`) memakai `master_drift`.

Proses gaji (`hr_payroll_service`): `employees_for_run` memilih karyawan menurut penugasan, `segments` memotong periode
menurut perubahan kompensasi dan penugasan, aturan `hr.prorata_perubahan_gaji` (global → PT; bawaan `mati`, K-38):
  * `mati`         — satu potongan sebulan penuh bernilai baris yang berlaku pada hari terakhir periode (atau hari
                     terakhir bekerja); PT pada hari itu yang menggaji, PT lama tidak memuatnya bulan itu.
  * `hari_kalender`— tiap potongan baris sendiri, nilai × hari potongan ÷ hari kalender bulan itu (rupiah penuh).
  * `hari_kerja`   — (PY-T3) potongan sama dengan hari kalender; nilai × hari kerja potongan ÷ hari kerja bulan itu
                     menurut kalender kerja PT (`hr_pay_rules.atur_potongan` → `rasio_ubah`; rupiah penuh).
Prorata masuk/keluar tengah bulan (PY-T3, `hr.prorata_masuk_keluar`) memotong potongan ini lagi menurut masa kerja.

Rapel: baris kompensasi yang disahkan dengan `effective_from` pada periode yang proses regulernya sudah `posted`/`paid`
→ satu masukan `pending` komponen `RAPEL` per periode (PY-T1 `enqueue_input`, kunci `rapel:<id baris>:<periode>`).
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db import db
from core_utils import new_id, now_iso, safe_doc

COMP = "hr_compensation_history"
ASG = "hr_employee_assignments"
STATUSES = ("pending", "approved", "rejected", "cancelled")
STATUS_LABEL = {"pending": "Menunggu disahkan", "approved": "Disahkan", "rejected": "Ditolak",
                "cancelled": "Dibatalkan"}
SOURCES = ("manual", "migrasi")
KUNCI_PRORATA = "hr.prorata_perubahan_gaji"
MATI, HARI_KALENDER, HARI_KERJA = "mati", "hari_kalender", "hari_kerja"
# PY-T3 — `hari_kerja`: potongan sama dengan hari kalender; nilainya × hari kerja potongan ÷ hari kerja bulan
# (kalender PT, `hr_pay_rules.atur_potongan` → `rasio_ubah`).
PRORATA_MODES = (MATI, HARI_KALENDER, HARI_KERJA)
AWAL, AKHIR = "0000-01-01", "9999-12-31"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_MSG = "Tanggal berlaku harus berbentuk TTTT-BB-HH."
REASON_MSG = "Alasan wajib diisi."
LOCKED_MSG = "Baris yang sudah disahkan tidak bisa diubah. Buat baris baru dengan tanggal berlaku baru."
BULAN_PENDEK = ("", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
LIVE_RUN = ("posted", "paid")   # proses reguler yang sudah dibayarkan nilainya → dasar rapel


class CompensationConflict(ValueError):
    """Status/tanggal bentrok (router → 409). Pesan siap tampil."""


# ── pembantu murni ────────────────────────────────────────────────────────────────────────────────────────────────────
def check_date(value: Any) -> str:
    s = str(value or "").strip()
    if not DATE_RE.match(s):
        raise ValueError(DATE_MSG)
    try:
        date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(DATE_MSG) from exc
    return s


def _prev_day(d: str) -> str:
    return (date.fromisoformat(d) - timedelta(days=1)).isoformat()


def today() -> str:
    """Hari ini (WIB) — satu sumber dengan tanggal buku (`book_date`, dibekukan uji)."""
    from services import book_date
    return book_date.tanggal_buku()


def period_bounds(period: str) -> Tuple[str, str, int]:
    y, m = int(period[:4]), int(period[5:7])
    dim = calendar.monthrange(y, m)[1]
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{dim:02d}", dim


def segment_label(seg: Dict[str, Any]) -> str:
    """'(1–15 Nov)' untuk potongan 2026-11-01 … 2026-11-15."""
    d1, d2 = date.fromisoformat(seg["date_from"]), date.fromisoformat(seg["date_to"])
    return f"({d1.day}–{d2.day} {BULAN_PENDEK[d2.month]})"


def prorate(value: Any, days: int, dim: int) -> float:
    """nilai × hari ÷ hari kalender bulan itu, dibulatkan ke rupiah penuh (setengah ke atas)."""
    d = Decimal(str(float(value or 0))) * Decimal(int(days)) / Decimal(int(dim))
    return float(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def fixed_from_allowances(allowances: Any) -> List[Dict[str, Any]]:
    """Tunjangan master (bentuk lama `[{name, amount}]` atau angka) → `fixed_components` (kode TUNJANGAN; komponen lain
    bila master menyimpannya `component_code`)."""
    from services import hr_pay_components as _pc
    if isinstance(allowances, list):
        out = []
        for a in allowances:
            if isinstance(a, dict) and float(a.get("amount") or 0):
                out.append({"component_code": str(a.get("component_code") or "TUNJANGAN"),
                            "label": str(a.get("name") or a.get("label") or "").strip(),
                            "amount": round(float(a.get("amount") or 0), 2)})
            elif isinstance(a, (int, float)) and float(a):
                out.append({"component_code": "TUNJANGAN", "label": "", "amount": round(float(a), 2)})
        return out
    return [{"component_code": "TUNJANGAN", "label": nama, "amount": round(amt, 2)}
            for nama, amt in _pc.allowance_rows(allowances)]


def allowances_from_fixed(fixed: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """`fixed_components` → bentuk master `allowances` (nilai turunan). TUNJANGAN tanpa `component_code` (bentuk lama)."""
    out = []
    for fc in fixed or ():
        row = {"name": fc.get("label") or "", "amount": round(float(fc.get("amount") or 0), 2)}
        if (fc.get("component_code") or "TUNJANGAN") != "TUNJANGAN":
            row["component_code"] = fc["component_code"]
        out.append(row)
    return out


def _norm_fixed(fixed: Iterable[Dict[str, Any]]) -> List[Tuple[str, str, float]]:
    return sorted((str(f.get("component_code") or "TUNJANGAN"), str(f.get("label") or ""),
                   round(float(f.get("amount") or 0), 2)) for f in fixed or () if float(f.get("amount") or 0))


def master_comp_row(emp: Dict[str, Any]) -> Dict[str, Any]:
    """Baris maya dari master (karyawan tanpa riwayat): perilaku sebelum PY-T2."""
    return {"id": "", "effective_from": AWAL, "base_salary": round(float(emp.get("base_salary") or 0), 2),
            "fixed_components": fixed_from_allowances(emp.get("allowances")), "virtual": True}


def master_asg_row(emp: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": "", "effective_from": AWAL, "entity_id": emp.get("entity_id") or "",
            "department_id": emp.get("department_id") or "", "position_id": emp.get("position_id") or "",
            "virtual": True}


def intervals(rows: List[Dict[str, Any]]) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Baris sah urut `effective_from` → [(mulai, akhir, baris)]; baris paling awal berlaku sejak AWAL, baris terakhir
    sampai AKHIR, sisanya sampai sehari sebelum baris berikutnya."""
    rows = sorted(rows, key=lambda r: r.get("effective_from") or AWAL)
    out = []
    for i, r in enumerate(rows):
        start = AWAL if i == 0 else r["effective_from"]
        end = _prev_day(rows[i + 1]["effective_from"]) if i + 1 < len(rows) else AKHIR
        out.append((start, end, r))
    return out


def row_at(rows: List[Dict[str, Any]], d: str) -> Optional[Dict[str, Any]]:
    for start, end, r in intervals(rows):
        if start <= d <= end:
            return r
    return None


def _tanggal_keluar(emp: Dict[str, Any]) -> str:
    return str(emp.get("separation_date") or emp.get("end_date") or emp.get("resign_date") or "")[:10]


def reference_day(emp: Dict[str, Any], period: str) -> str:
    """Hari acuan aturan `mati`: hari terakhir periode, atau hari terakhir bekerja bila keluar di periode itu."""
    _, end, _ = period_bounds(period)
    keluar = _tanggal_keluar(emp)
    return keluar if keluar and keluar[:7] == period and keluar < end else end


def build_segments(emp: Dict[str, Any], entity_id: str, period: str, mode: str,
                   comp_rows: List[Dict[str, Any]], asg_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Potongan periode karyawan di PT itu: [{date_from, date_to, days, base_salary, fixed_components, full}].
    [] = karyawan tidak digaji PT itu pada periode itu. Fungsi murni (baris sah sudah dimuat)."""
    start, end, dim = period_bounds(period)
    comp_rows = comp_rows or [master_comp_row(emp)]
    asg_rows = asg_rows or [master_asg_row(emp)]
    if mode not in (HARI_KALENDER, HARI_KERJA):
        ref = reference_day(emp, period)
        asg = row_at(asg_rows, ref)
        if not asg or asg.get("entity_id") != entity_id:
            return []
        comp = row_at(comp_rows, ref) or {}
        return [{"date_from": start, "date_to": end, "days": dim, "full": True,
                 "base_salary": round(float(comp.get("base_salary") or 0), 2),
                 "fixed_components": list(comp.get("fixed_components") or []), "compensation_id": comp.get("id", ""),
                 "assignment_id": asg.get("id", "")}]
    pieces: List[Dict[str, Any]] = []
    for a0, a1, asg in intervals(asg_rows):
        if asg.get("entity_id") != entity_id:
            continue
        s, e = max(a0, start), min(a1, end)
        if s > e:
            continue
        for c0, c1, comp in intervals(comp_rows):
            ps, pe = max(s, c0), min(e, c1)
            if ps > pe:
                continue
            piece = {"date_from": ps, "date_to": pe,
                     "base_salary": round(float(comp.get("base_salary") or 0), 2),
                     "fixed_components": list(comp.get("fixed_components") or []),
                     "compensation_id": comp.get("id", ""), "assignment_id": asg.get("id", "")}
            prev = pieces[-1] if pieces else None
            if prev and _prev_day(ps) == prev["date_to"] and prev["base_salary"] == piece["base_salary"] and \
                    _norm_fixed(prev["fixed_components"]) == _norm_fixed(piece["fixed_components"]):
                prev["date_to"] = pe   # nilai sama → satu potongan (perubahan PT di dalam bulan tidak relevan)
            else:
                pieces.append(piece)
    for p in pieces:
        p["days"] = (date.fromisoformat(p["date_to"]) - date.fromisoformat(p["date_from"])).days + 1
        p["full"] = p["date_from"] == start and p["date_to"] == end
    return pieces


def segment_total(seg: Dict[str, Any], dim: int, codes: Optional[Iterable[str]] = None,
                  comps: Optional[Dict[str, Dict[str, Any]]] = None, potong: Optional[bool] = None) -> float:
    """Σ gaji pokok + komponen tetap satu potongan (diprorata bila bukan sebulan penuh). PY-T3 — `comps` diberikan →
    nilai tiap komponen lewat `hr_pay_components.nilai_tetap` (prorata masuk/keluar, hari kerja), sama dengan slip."""
    if comps is not None:
        from services import hr_pay_components as _pc
        cut = (not seg.get("full")) if potong is None else potong
        items = [(comps.get("GAJI_POKOK") or {}, seg.get("base_salary") or 0)] + [
            (comps.get(f.get("component_code") or "TUNJANGAN") or {}, f.get("amount") or 0)
            for f in seg.get("fixed_components") or ()
            if codes is None or (f.get("component_code") or "TUNJANGAN") in codes]
        return round(sum(_pc.nilai_tetap(seg, c, v, dim, cut)[0] for c, v in items), 2)
    vals = [seg.get("base_salary") or 0] + [f.get("amount") or 0 for f in seg.get("fixed_components") or ()
                                            if codes is None or (f.get("component_code") or "TUNJANGAN") in codes]
    if seg.get("full"):
        return round(sum(float(v) for v in vals), 2)
    return round(sum(prorate(v, seg["days"], dim) for v in vals), 2)


# ── baca ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _approved(coll: str, employee_ids: Iterable[str]) -> Dict[str, List[Dict[str, Any]]]:
    ids = [i for i in employee_ids if i]
    out: Dict[str, List[Dict[str, Any]]] = {i: [] for i in ids}
    if not ids:
        return out
    async for r in db[coll].find({"employee_id": {"$in": ids}, "status": "approved"}, {"_id": 0}) \
            .sort([("employee_id", 1), ("effective_from", 1)]):
        out.setdefault(r["employee_id"], []).append(r)
    return out


async def _setting(key: str, entity_id: str) -> str:
    """Nilai pengaturan berlapis global → PT (02 §2.2); galat → bawaan registry (KF-06)."""
    from services.config_resolver import value_of
    import config_registry as registry
    try:
        v = await value_of(key, {"entity_id": entity_id})
    except Exception:   # noqa: BLE001 — cadangan = bawaan registry, bukan nilai lain
        v = registry.require(key)["default"]
    return v if v in PRORATA_MODES else MATI


async def prorata_mode(entity_id: str) -> str:
    """`hr.prorata_perubahan_gaji` untuk PT itu (pemilihan karyawan proses gaji, rapel)."""
    return await _setting(KUNCI_PRORATA, entity_id)


async def compensation_at(employee_id: str, d: str, *, emp: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Baris kompensasi `approved` yang berlaku pada tanggal itu; tanpa riwayat → baris maya dari master; {} bila
    karyawan tidak ada."""
    rows = (await _approved(COMP, [employee_id]))[employee_id]
    if rows:
        return row_at(rows, d) or {}
    emp = emp or await db.hr_employees.find_one({"id": employee_id}, {"_id": 0})
    return master_comp_row(emp) if emp else {}


async def assignment_at(employee_id: str, d: str, *, emp: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rows = (await _approved(ASG, [employee_id]))[employee_id]
    if rows:
        return row_at(rows, d) or {}
    emp = emp or await db.hr_employees.find_one({"id": employee_id}, {"_id": 0})
    return master_asg_row(emp) if emp else {}


async def segments(employee_id: str, entity_id: str, period: str, *, emp: Optional[Dict[str, Any]] = None,
                   mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """Potongan periode menurut perubahan kompensasi dan penugasan di PT itu (`build_segments`)."""
    emp = emp or safe_doc(await db.hr_employees.find_one({"id": employee_id}, {"_id": 0})) or {"id": employee_id}
    mode = mode or await _setting(KUNCI_PRORATA, entity_id)
    comp = (await _approved(COMP, [employee_id]))[employee_id]
    asg = (await _approved(ASG, [employee_id]))[employee_id]
    return build_segments(emp, entity_id, period, mode, comp, asg)


async def full_month_segments(emp: Dict[str, Any], entity_id: str, period: str) -> List[Dict[str, Any]]:
    """Satu potongan sebulan penuh bernilai kompensasi pada hari acuan, tanpa melihat penugasan (pemanggil langsung
    `compute_payslip` untuk PT yang tidak menggaji karyawan itu pada periode itu)."""
    comp = (await _approved(COMP, [emp["id"]]))[emp["id"]]
    return build_segments(emp, entity_id, period, MATI, comp, [master_asg_row({**emp, "entity_id": entity_id})])


def _employee_status_query(period: str) -> Dict[str, Any]:
    # HR-01 — karyawan yang berhenti pada periode ini tetap digaji (masa pajak terakhir); PK-45 `separation_date`.
    awal = {"$regex": f"^{re.escape(period)}"}
    return {"$or": [{"status": "active"}, {"status": {"$in": ["resigned", "inactive"]},
                                           "$or": [{"separation_date": awal}, {"end_date": awal}]}]}


async def employees_for_run(entity_id: str, period: str) -> List[Dict[str, Any]]:
    """Karyawan yang digaji PT itu pada periode itu: penugasannya di PT itu bersinggungan dengan periode (aturan
    prorata PT itu; `mati` = PT pada hari acuan). Menggantikan saringan `entity_id` master. Tiap karyawan membawa
    `_segments` (dipakai `compute_payslip`, tanpa kueri ulang)."""
    ids = set(await db[ASG].distinct("employee_id", {"entity_id": entity_id, "status": "approved"}))
    ids |= set(await db.hr_employees.distinct("id", {"entity_id": entity_id}))
    if not ids:
        return []
    q = {"id": {"$in": sorted(ids)}, **_employee_status_query(period)}
    emps = [safe_doc(e) async for e in db.hr_employees.find(q, {"_id": 0})]
    mode = await prorata_mode(entity_id)
    eids = [e["id"] for e in emps]
    comp, asg = await _approved(COMP, eids), await _approved(ASG, eids)
    out = []
    for e in emps:
        segs = build_segments(e, entity_id, period, mode, comp.get(e["id"], []), asg.get(e["id"], []))
        if segs:
            e["_segments"] = segs
            out.append(e)
    return out


async def history(employee_id: str) -> Dict[str, Any]:
    """Semua baris (semua status) untuk kartu karyawan, terbaru dulu; baris kompensasi diberi `entity_id` = PT karyawan
    pada tanggal berlakunya (teks konfirmasi sahkan)."""
    comp = [safe_doc(r) async for r in db[COMP].find({"employee_id": employee_id}, {"_id": 0})
            .sort([("effective_from", -1), ("created_at", -1)])]
    asg = [safe_doc(r) async for r in db[ASG].find({"employee_id": employee_id}, {"_id": 0})
           .sort([("effective_from", -1), ("created_at", -1)])]
    emp = await db.hr_employees.find_one({"id": employee_id}, {"_id": 0}) or {}
    asg_ok = [r for r in asg if r.get("status") == "approved"] or [master_asg_row(emp)]
    for r in comp:
        r["entity_id"] = (row_at(asg_ok, r.get("effective_from") or AWAL) or {}).get("entity_id", "")
    unit_ids = sorted({r.get(f) for r in asg for f in ("department_id", "position_id") if r.get(f)})
    names = {u["id"]: u.get("name", "") async for u in db.hr_org_units.find({"id": {"$in": unit_ids}},
                                                                            {"_id": 0, "id": 1, "name": 1})}
    for r in asg:
        r["department_name"] = names.get(r.get("department_id") or "", "")
        r["position_name"] = names.get(r.get("position_id") or "", "")
    return {"compensation": comp, "assignments": asg, "today": today()}


async def fixed_component_options(entity_id: str) -> List[Dict[str, Any]]:
    """Komponen `tetap_bulanan` aktif PT itu selain Gaji Pokok (pilihan isian Komponen tetap)."""
    from services import hr_pay_components as _pc
    if not entity_id or entity_id == "all":
        return []
    return [{"code": c["code"], "name": c.get("name") or c["code"]}
            for c in (await _pc.list_components(entity_id, active_only=True))
            if c.get("calc") == "tetap_bulanan" and c["code"] != "GAJI_POKOK"]


# ── tulis: usul, sahkan, tolak ───────────────────────────────────────────────────────────────────────────────────────
def _who(actor: Dict[str, Any]) -> Dict[str, str]:
    return {"id": actor.get("id", ""), "name": actor.get("name", "system")}


def _reason(v: Any) -> str:
    r = str(v or "").strip()
    if not r:
        raise ValueError(REASON_MSG)
    return r


def _money(v: Any, msg: str) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError(msg) from exc
    if f < 0 or f != f:
        raise ValueError(msg)
    return round(f, 2)


async def _check_fixed(entity_id: str, fixed: Any) -> List[Dict[str, Any]]:
    from services import hr_pay_components as _pc
    comps = await _pc.components_for(entity_id) if entity_id and entity_id != "all" else \
        _pc.by_code(_pc.DEFAULT_COMPONENTS)
    out = []
    for fc in fixed or []:
        if not isinstance(fc, dict):
            raise ValueError("Komponen tetap harus berisi kode komponen, keterangan, dan nominal.")
        code = str(fc.get("component_code") or "").strip().upper()
        comp = comps.get(code)
        if not comp or comp.get("calc") != "tetap_bulanan" or code == "GAJI_POKOK" or comp.get("is_active") is False:
            raise ValueError(f"Komponen {code or '(kosong)'} bukan komponen tetap bulanan di PT ini.")
        out.append({"component_code": code, "label": str(fc.get("label") or "").strip(),
                    "amount": _money(fc.get("amount"), f"Nominal komponen {code} harus angka rupiah ≥ 0.")})
    return out


async def propose_compensation(emp: Dict[str, Any], data: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Baris kompensasi `pending`. `fixed_components` tidak dikirim → disalin dari baris yang berlaku pada tanggal itu
    (kenaikan gaji pokok tidak menghapus tunjangan); `[]` = tanpa komponen tetap."""
    eff = check_date(data.get("effective_from"))
    base = _money(data.get("base_salary"), "Gaji pokok harus angka rupiah ≥ 0.")
    asg = await assignment_at(emp["id"], eff, emp=emp)
    if data.get("fixed_components") is None:
        cur = await compensation_at(emp["id"], eff, emp=emp)
        fixed = [dict(f) for f in cur.get("fixed_components") or []]
    else:
        fixed = await _check_fixed(asg.get("entity_id") or emp.get("entity_id", ""), data.get("fixed_components"))
    reason = _reason(data.get("reason"))
    doc = {"id": new_id("hcomp"), "employee_id": emp["id"], "employee_name": emp.get("name", ""),
           "effective_from": eff, "effective_to": "", "base_salary": base, "fixed_components": fixed,
           "status": "pending", "reason": reason, "source": "manual", "proposed_by": _who(actor),
           "proposed_at": now_iso(), "approved_by": {}, "approved_at": "", "decision_reason": "",
           "created_at": now_iso(), "updated_at": now_iso()}
    await db[COMP].insert_one(dict(doc))
    return doc


async def propose_assignment(emp: Dict[str, Any], data: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Penugasan `pending` ke PT `entity_id` (router sudah memastikan PT itu dalam cakupan pelaku). Departemen/jabatan
    harus milik PT tujuan (02 §3.4 N2)."""
    ent = str(data.get("entity_id") or "").strip()
    if not ent or ent == "all":
        raise ValueError("Pilih PT tujuan.")
    pt = await db.business_entities.find_one({"id": ent}, {"_id": 0, "id": 1, "status": 1, "is_active": 1})
    if not pt or pt.get("is_active") is False or (pt.get("status") or "active") not in ("active",):
        raise ValueError("PT tujuan tidak ada atau tidak aktif.")
    eff = check_date(data.get("effective_from"))
    unit = {}
    for f, jenis in (("department_id", "Departemen"), ("position_id", "Jabatan")):
        v = str(data.get(f) or "").strip()
        if v:
            u = await db.hr_org_units.find_one({"id": v}, {"_id": 0, "entity_id": 1, "parent_id": 1})
            if not u or (u.get("entity_id") or "") != ent:
                raise ValueError(f"{jenis} yang dipilih bukan milik PT tujuan.")
            unit[f] = u
        data[f] = v
    if unit.get("position_id") and data.get("department_id") and \
            unit["position_id"].get("parent_id") != data["department_id"]:
        raise ValueError("Jabatan yang dipilih bukan bagian dari departemen itu.")
    reason = _reason(data.get("reason"))
    doc = {"id": new_id("hasg"), "employee_id": emp["id"], "employee_name": emp.get("name", ""), "entity_id": ent,
           "effective_from": eff, "effective_to": "", "department_id": data.get("department_id") or "",
           "position_id": data.get("position_id") or "", "status": "pending", "reason": reason, "source": "manual",
           "proposed_by": _who(actor), "proposed_at": now_iso(), "approved_by": {}, "approved_at": "",
           "decision_reason": "", "created_at": now_iso(), "updated_at": now_iso()}
    await db[ASG].insert_one(dict(doc))
    return doc


async def _rechain(coll: str, employee_id: str) -> None:
    """`effective_to` tiap baris sah = sehari sebelum baris sah berikutnya; baris terakhir kosong (terbuka)."""
    rows = (await _approved(coll, [employee_id]))[employee_id]
    for i, r in enumerate(rows):
        to = _prev_day(rows[i + 1]["effective_from"]) if i + 1 < len(rows) else ""
        if (r.get("effective_to") or "") != to:
            await db[coll].update_one({"id": r["id"], "status": "approved"}, {"$set": {"effective_to": to}})


def _dup_msg(coll: str, eff: str) -> str:
    if coll == COMP:
        return f"Sudah ada perubahan kompensasi yang berlaku {eff} untuk karyawan ini."
    return f"Sudah ada penugasan PT yang berlaku {eff} untuk karyawan ini."


async def get_row(coll: str, row_id: str) -> Optional[Dict[str, Any]]:
    return safe_doc(await db[coll].find_one({"id": row_id}, {"_id": 0}))


async def _decide(coll: str, row_id: str, action: str, actor: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    """pending → approved | rejected | cancelled, bersyarat status lama (INV-ATOMIC-01). Sesudah sah: `_rechain`,
    `apply_effective` karyawan itu, dan (kompensasi) masukan rapel — ketiganya idempoten."""
    from pymongo.errors import DuplicateKeyError
    row = await get_row(coll, row_id)
    if not row:
        raise LookupError("Baris riwayat tidak ditemukan.")
    if row["status"] != "pending":
        if row["status"] == "approved":
            if action == "approve":   # kirim ulang: lengkapi langkah sesudah sah yang mungkin terputus (idempoten)
                await _after_approve(coll, row, actor)
            raise CompensationConflict(LOCKED_MSG)
        lbl = STATUS_LABEL.get(row["status"], row["status"])
        verb = {"approve": "disahkan", "reject": "ditolak", "cancel": "dibatalkan"}[action]
        raise CompensationConflict(f"Baris ini berstatus {lbl}, jadi tidak bisa {verb}.")
    patch: Dict[str, Any] = {"updated_at": now_iso(), "decision_reason": str(reason or "").strip()}
    if action == "approve":
        if await db[coll].find_one({"employee_id": row["employee_id"], "effective_from": row["effective_from"],
                                    "status": "approved", "id": {"$ne": row_id}}, {"_id": 1}):
            raise CompensationConflict(_dup_msg(coll, row["effective_from"]))
        patch.update({"status": "approved", "approved_by": _who(actor), "approved_at": now_iso()})
    elif action == "reject":
        patch.update({"status": "rejected", "rejected_by": _who(actor), "rejected_at": now_iso()})
    else:
        patch.update({"status": "cancelled", "cancelled_by": _who(actor), "cancelled_at": now_iso()})
    try:
        res = await db[coll].update_one({"id": row_id, "status": "pending"}, {"$set": patch})
    except DuplicateKeyError as exc:   # D7 — indeks unik parsial (employee_id, effective_from) baris sah
        raise CompensationConflict(_dup_msg(coll, row["effective_from"])) from exc
    if not res.modified_count:
        raise CompensationConflict("Baris ini baru saja berubah — muat ulang.")
    row = await get_row(coll, row_id)
    if action == "approve":
        await _after_approve(coll, row, actor)
        row = await get_row(coll, row_id)
    return row


async def _after_approve(coll: str, row: Dict[str, Any], actor: Dict[str, Any]) -> None:
    await _rechain(coll, row["employee_id"])
    await apply_effective(employee_ids=[row["employee_id"]], actor=actor)
    if coll == COMP:
        await enqueue_rapel(row, actor)


async def decide_compensation(row_id: str, action: str, actor: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    return await _decide(COMP, row_id, action, actor, reason)


async def decide_assignment(row_id: str, action: str, actor: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    return await _decide(ASG, row_id, action, actor, reason)


async def initial_rows(emp: Dict[str, Any], actor: Dict[str, Any], *, source: str = "manual",
                       effective_from: str = "", reason: str = "") -> Dict[str, Any]:
    """Baris kompensasi + penugasan pertama berstatus `approved` dari isi master (karyawan baru / migrasi). Bagian yang
    sudah punya baris (status apa pun) dilewati — aman diulang. → {"compensation": doc|None, "assignment": doc|None}."""
    eff = effective_from or today()
    who = _who(actor)
    why = reason or ("Data awal karyawan baru." if source == "manual" else "Migrasi PY-T2 dari data master.")
    out: Dict[str, Any] = {"compensation": None, "assignment": None}
    base = {"employee_id": emp["id"], "employee_name": emp.get("name", ""), "effective_from": eff, "effective_to": "",
            "status": "approved", "reason": why, "source": source, "proposed_by": who, "proposed_at": now_iso(),
            "approved_by": who, "approved_at": now_iso(), "decision_reason": "", "applied_at": now_iso(),
            "created_at": now_iso(), "updated_at": now_iso()}
    if not await db[COMP].find_one({"employee_id": emp["id"]}, {"_id": 1}):
        doc = {**base, "id": new_id("hcomp"), "base_salary": round(float(emp.get("base_salary") or 0), 2),
               "fixed_components": fixed_from_allowances(emp.get("allowances"))}
        await db[COMP].insert_one(dict(doc))
        out["compensation"] = doc
    if not await db[ASG].find_one({"employee_id": emp["id"]}, {"_id": 1}):
        doc = {**base, "id": new_id("hasg"), "entity_id": emp.get("entity_id") or "",
               "department_id": emp.get("department_id") or "", "position_id": emp.get("position_id") or ""}
        await db[ASG].insert_one(dict(doc))
        out["assignment"] = doc
    return out


async def remove_rows(employee_id: str) -> None:
    """Kompensasi pembuatan karyawan yang gagal (POST /hr/employees)."""
    await db[COMP].delete_many({"employee_id": employee_id})
    await db[ASG].delete_many({"employee_id": employee_id})


# ── nilai turunan master ─────────────────────────────────────────────────────────────────────────────────────────────
def expected_master(emp: Dict[str, Any], comp_rows: List[Dict[str, Any]], asg_rows: List[Dict[str, Any]],
                    d: str) -> Dict[str, Any]:
    """Nilai master yang benar pada tanggal `d` (hanya bagian yang punya riwayat)."""
    out: Dict[str, Any] = {}
    c = row_at(comp_rows, d) if comp_rows else None
    if c:
        out["base_salary"] = round(float(c.get("base_salary") or 0), 2)
        out["allowances"] = allowances_from_fixed(c.get("fixed_components") or [])
    a = row_at(asg_rows, d) if asg_rows else None
    if a:
        out["entity_id"] = a.get("entity_id") or ""
        out["_asg"] = a
    return out


def master_diff(emp: Dict[str, Any], exp: Dict[str, Any]) -> List[str]:
    beda = []
    if "base_salary" in exp and round(float(emp.get("base_salary") or 0), 2) != exp["base_salary"]:
        beda.append("base_salary")
    if "allowances" in exp and _norm_fixed(fixed_from_allowances(emp.get("allowances"))) != \
            _norm_fixed(fixed_from_allowances(exp["allowances"])):
        beda.append("allowances")
    if "entity_id" in exp and (emp.get("entity_id") or "") != exp["entity_id"]:
        beda.append("entity_id")
    return beda


async def _with_history(employee_ids: Optional[Iterable[str]]) -> List[str]:
    if employee_ids is not None:
        return [i for i in employee_ids if i]
    ids = set(await db[COMP].distinct("employee_id", {"status": "approved"}))
    ids |= set(await db[ASG].distinct("employee_id", {"status": "approved"}))
    return sorted(ids)


async def apply_effective(today_: Optional[str] = None, *, employee_ids: Optional[Iterable[str]] = None,
                          actor: Optional[Dict[str, Any]] = None) -> int:
    """Salin baris yang berlaku pada `today_` (bawaan hari ini WIB) ke master: `base_salary`, `allowances`, `entity_id`
    (+ departemen/jabatan penugasan saat baris itu PERTAMA berlaku). Pembangun ulang nilai turunan (02 §5 D2).
    → jumlah karyawan yang masternya berubah."""
    from dependencies import audit
    d = check_date(today_) if today_ else today()
    ids = await _with_history(employee_ids)
    if not ids:
        return 0
    comp, asg = await _approved(COMP, ids), await _approved(ASG, ids)
    emps = {e["id"]: e async for e in db.hr_employees.find({"id": {"$in": ids}}, {"_id": 0})}
    n = 0
    who = (actor or {}).get("name", "system")
    for eid in ids:
        emp = emps.get(eid)
        if not emp:
            continue
        exp = expected_master(emp, comp.get(eid, []), asg.get(eid, []), d)
        a = exp.pop("_asg", None)
        patch = {k: exp[k] for k in master_diff(emp, exp)}
        if a and not a.get("applied_at") and not a.get("virtual"):
            for f in ("department_id", "position_id"):
                if a.get(f) and a[f] != emp.get(f):
                    patch[f] = a[f]
            await db[ASG].update_one({"id": a["id"], "status": "approved"}, {"$set": {"applied_at": now_iso()}})
        if not patch:
            continue
        patch["updated_at"] = now_iso()
        await db.hr_employees.update_one({"id": eid}, {"$set": patch})
        n += 1
        pii = [k for k in patch if k in ("base_salary", "allowances")]
        await audit(who, "hr_employee_effective_applied", "hr_employee", eid,
                    {k: v for k, v in patch.items() if k not in pii}, before={k: emp.get(k) for k in patch
                                                                              if k not in pii},
                    masked_fields=pii, scope_entity_id=patch.get("entity_id") or emp.get("entity_id", ""),
                    source="hr_compensation_effective")
    return n


async def job_apply_effective() -> Dict[str, Any]:
    """Tugas terjadwal `hr_compensation_effective` (harian 00.10 WIB)."""
    return {"date": today(), "updated": await apply_effective()}


async def master_drift(today_: Optional[str] = None) -> Dict[str, Any]:
    """INV-PY-2 — karyawan aktif yang master `base_salary`/`allowances`/`entity_id`-nya ≠ baris sah yang berlaku hari
    ini. Karyawan aktif tanpa riwayat dihitung terpisah (belum dimigrasi; master masih sumbernya)."""
    d = today_ or today()
    emps = [e async for e in db.hr_employees.find({"status": "active"}, {"_id": 0, "id": 1, "name": 1, "code": 1,
                                                                         "base_salary": 1, "allowances": 1,
                                                                         "entity_id": 1})]
    ids = [e["id"] for e in emps]
    comp, asg = await _approved(COMP, ids), await _approved(ASG, ids)
    drift, tanpa = [], []
    for e in emps:
        c, a = comp.get(e["id"], []), asg.get(e["id"], [])
        if not c and not a:
            tanpa.append(e["id"])
            continue
        exp = expected_master(e, c, a, d)
        exp.pop("_asg", None)
        beda = master_diff(e, exp)
        if beda:
            drift.append({"employee_id": e["id"], "name": e.get("name", ""), "code": e.get("code", ""),
                          "fields": beda})
    return {"date": d, "checked": len(emps) - len(tanpa), "without_history": tanpa, "drift": drift}


# ── rapel ────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _paid_slips(employee_id: str, start: str, end: str) -> Dict[str, List[Dict[str, Any]]]:
    """{periode: slip reguler karyawan itu} dari proses reguler `posted`/`paid` periode `start`…`end` (YYYY-MM)."""
    runs = {r["id"]: r async for r in db.hr_payroll_runs.find(
        {"status": {"$in": list(LIVE_RUN)}, "run_type": {"$in": ["regular", None]},
         "period": {"$gte": start, "$lte": end}}, {"_id": 0, "id": 1, "entity_id": 1, "period": 1})}
    out: Dict[str, List[Dict[str, Any]]] = {}
    if not runs:
        return out
    async for s in db.hr_payslips.find({"employee_id": employee_id, "run_id": {"$in": list(runs)}},
                                       {"_id": 0, "run_id": 1, "entity_id": 1, "period": 1, "components": 1,
                                        "base_salary": 1, "allowances": 1}):
        out.setdefault(s["period"], []).append(s)
    return out


async def _paid_fixed(slip: Dict[str, Any]) -> float:
    """Gaji pokok + komponen tetap yang DIBAYAR slip itu (komponen; slip lama → kolom)."""
    from services import hr_pay_components as _pc
    if slip.get("components"):
        comps = await _pc.components_for(slip.get("entity_id") or "")
        return round(sum(float(c.get("amount") or 0) for c in slip["components"]
                         if (comps.get(c.get("code") or "") or {}).get("calc") == "tetap_bulanan"), 2)
    return round(float(slip.get("base_salary") or 0) + float(slip.get("allowances") or 0), 2)


async def rapel_lines(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Selisih per periode yang sudah dibayar (proses reguler posted/paid) sejak `effective_from` baris itu sampai
    `effective_to`-nya (atau bulan berjalan): nilai menurut riwayat sekarang − nilai yang dibayar, mengikuti aturan prorata
    PT slip itu. → [{period, amount}] (selisih 0 dilewati)."""
    from services import hr_pay_components as _pc
    from services import hr_pay_rules as _pr
    from services import hr_work_calendar as _wc
    eid = row["employee_id"]
    now_p = today()[:7]
    start = row["effective_from"][:7]
    end = min((row.get("effective_to") or AKHIR)[:7], now_p)
    if start > end:
        return []
    paid = await _paid_slips(eid, start, end)
    if not paid:
        return []
    emp = safe_doc(await db.hr_employees.find_one({"id": eid}, {"_id": 0})) or {"id": eid}
    comp, asg = (await _approved(COMP, [eid]))[eid], (await _approved(ASG, [eid]))[eid]
    out = []
    for period in sorted(paid):
        _, _, dim = period_bounds(period)
        selisih = 0.0
        for ent in sorted({s.get("entity_id") or "" for s in paid[period]}):
            comps = await _pc.components_for(ent)
            tetap = [c for c, v in comps.items() if v.get("calc") == "tetap_bulanan" and c != "GAJI_POKOK"]
            segs = build_segments(emp, ent, period, await prorata_mode(ent), comp, asg)
            # PY-T3 — nilai menurut aturan slip PT itu (prorata masuk/keluar, hari kerja), supaya rapel = selisih nyata.
            rl = await _pr.rules(ent)
            p0, p1, _ = period_bounds(period)
            segs = _pr.atur_potongan(segs, emp, period, rl, await _wc.calendar_for(ent, p0, p1, rl))
            potong = len(segs) > 1 or bool(segs and not segs[0].get("full"))
            baru = round(sum(segment_total(s, dim, tetap, comps, potong) for s in segs), 2)
            dibayar = round(sum([await _paid_fixed(s) for s in paid[period] if (s.get("entity_id") or "") == ent]), 2)
            selisih += baru - dibayar
        selisih = float(Decimal(str(selisih)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if selisih:
            out.append({"period": period, "amount": int(selisih)})
    return out


async def enqueue_rapel(row: Dict[str, Any], actor: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Masukan `pending` komponen RAPEL di bulan berjalan untuk tiap periode yang sudah dibayar (kunci
    `rapel:<id baris>:<periode>` — mengulang tidak menambah masukan). PT masukan = PT karyawan pada akhir bulan
    berjalan (yang memuatnya di proses gaji bulan ini)."""
    from services import hr_pay_inputs as _pi
    from services import periodic_posting
    lines = await rapel_lines(row)
    if not lines:
        return []
    pay_period = today()[:7]
    _, akhir, _ = period_bounds(pay_period)
    ent = (await assignment_at(row["employee_id"], akhir)).get("entity_id") or ""
    out = []
    for ln in lines:
        out.append(await _pi.enqueue_input(
            entity_id=ent, employee_id=row["employee_id"], pay_period=pay_period, component_code="RAPEL",
            label=f"Rapel gaji {periodic_posting.label_periode(ln['period'])}", amount=ln["amount"],
            source_type="rapel", source_key=f"rapel:{row['id']}:{ln['period']}",
            source_ref={"type": "compensation", "id": row["id"], "effective_from": row["effective_from"]},
            basis_period=ln["period"], actor=actor, status="pending"))
    return out
