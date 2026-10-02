"""HRD H3 services — Cuti, Izin & Lembur (Leave/Permit & Overtime).

Logika murni + I/O Mongo (motor). Koleksi kanonik (entity-scoped):
`hr_leave_requests` (leave_), `hr_leave_balances` (lbal_), `hr_overtime` (ot_).

Aturan kunci:
- Hari kerja = Senin–Jumat dalam rentang (V1 tanpa kalender libur nasional).
- Saldo cuti tahunan berkurang HANYA untuk tipe yang `deduct=True` (cuti_tahunan/besar).
- Saat cuti di-APPROVE → `hr_attendance` hari terkait di-set status `cuti`/`izin`
  (method="leave") agar rekap absensi konsisten.
- Lembur APPROVED → dikonsumsi payroll (hr_payroll_service._period_filed_overtime_min).
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc
from services import hr_attendance_service as att

WIB = timezone(timedelta(hours=7))

# Tipe cuti: deduct = mengurangi saldo cuti tahunan; att_status = status absensi saat approve.
LEAVE_TYPES: Dict[str, Dict[str, Any]] = {
    "cuti_tahunan": {"label": "Cuti Tahunan", "deduct": True, "att_status": "cuti"},
    "cuti_besar":   {"label": "Cuti Besar", "deduct": True, "att_status": "cuti"},
    "izin":         {"label": "Izin", "deduct": False, "att_status": "izin"},
    "sakit":        {"label": "Sakit", "deduct": False, "att_status": "izin"},
    "unpaid":       {"label": "Cuti Tanpa Gaji", "deduct": False, "att_status": "izin"},
}
DEDUCT_TYPES = [k for k, v in LEAVE_TYPES.items() if v["deduct"]]
DEFAULT_ANNUAL_ENTITLEMENT = 12


def wib_now() -> datetime:
    return datetime.now(WIB)


def wib_today() -> str:
    return wib_now().date().isoformat()


def current_year() -> int:
    return wib_now().year


def _parse_date(s: str) -> Optional[date]:
    try:
        return date.fromisoformat((s or "").strip()[:10])
    except (ValueError, TypeError):
        return None


def working_days(date_from: str, date_to: str) -> List[str]:
    """Daftar tanggal kerja (Senin–Jumat) dalam rentang inklusif. V1 tanpa kalender libur."""
    d0 = _parse_date(date_from)
    d1 = _parse_date(date_to)
    if not d0 or not d1 or d1 < d0:
        return []
    out: List[str] = []
    cur = d0
    # batas aman 366 hari
    for _ in range(367):
        if cur > d1:
            break
        if cur.weekday() < 5:  # 0=Senin .. 4=Jumat
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def count_working_days(date_from: str, date_to: str) -> int:
    return len(working_days(date_from, date_to))


# ── Saldo cuti ─────────────────────────────────────────────────────────
async def _annual_entitlement(entity_id: str = "") -> int:
    # FASE E-4 (E4.5) — jatah cuti tahunan boleh berbeda per badan usaha.
    from services import hr_service
    cfg = await hr_service.get_hr_settings(entity_id)
    try:
        return int((cfg.get("leave") or {}).get("annual_entitlement") or DEFAULT_ANNUAL_ENTITLEMENT)
    except (TypeError, ValueError):
        return DEFAULT_ANNUAL_ENTITLEMENT


async def recompute_balance(employee_id: str, entity_id: str, year: int) -> Dict[str, Any]:
    """Hitung ulang & simpan saldo cuti tahunan: remaining = entitlement - used(approved)."""
    entitlement = await _annual_entitlement(entity_id)
    existing = await db.hr_leave_balances.find_one(
        {"employee_id": employee_id, "year": year}, {"_id": 0})
    # IX-01 — override 0 adalah nilai sah (bukan "kosong").
    if existing and existing.get("entitlement_override") and existing.get("entitlement") is not None:
        entitlement = int(existing["entitlement"])
    used, pending = await _year_usage(employee_id, year)
    remaining = entitlement - used
    doc = {
        "employee_id": employee_id, "entity_id": entity_id, "year": year,
        "entitlement": entitlement, "used": used, "pending": pending,
        "remaining": remaining, "updated_at": now_iso(),
    }
    if existing:
        doc["id"] = existing["id"]
        doc["entitlement_override"] = bool(existing.get("entitlement_override"))
        await db.hr_leave_balances.update_one({"id": existing["id"]}, {"$set": doc})
    else:
        doc["id"] = new_id("lbal")
        doc["entitlement_override"] = False
        doc["created_at"] = now_iso()
        await db.hr_leave_balances.insert_one(dict(doc))
    return safe_doc(doc)


def _dates_of(r: Dict[str, Any]) -> List[str]:
    return r.get("work_dates") or working_days(r.get("date_from", ""), r.get("date_to", ""))


async def _year_usage(employee_id: str, year: int, exclude_id: str = "") -> tuple:
    """HR-03 — hari dibebankan ke tahun MASING-MASING tanggal kerja (cuti Des–Jan terbagi)."""
    used = pending = 0
    q = {"employee_id": employee_id, "leave_type": {"$in": DEDUCT_TYPES},
         "status": {"$in": ["approved", "pending"]}, "id": {"$ne": exclude_id},
         "$or": [{"work_dates": {"$regex": f"^{year:04d}-"}}, {"date_from": {"$regex": f"^{year:04d}"}},
                 {"date_to": {"$regex": f"^{year:04d}"}}]}
    async for r in db.hr_leave_requests.find(q, {"_id": 0}):
        n = sum(1 for d in _dates_of(r) if d.startswith(f"{year:04d}-"))
        if r["status"] == "approved":
            used += n
        else:
            pending += n
    return used, pending


def _days_per_year(dates: List[str]) -> Dict[int, int]:
    out: Dict[int, int] = {}
    for d in dates:
        out[int(d[:4])] = out.get(int(d[:4]), 0) + 1
    return out


async def get_balance(employee_id: str, entity_id: str, year: Optional[int] = None) -> Dict[str, Any]:
    year = year or current_year()
    bal = await db.hr_leave_balances.find_one({"employee_id": employee_id, "year": year}, {"_id": 0})
    if not bal:
        return await recompute_balance(employee_id, entity_id, year)
    return safe_doc(bal)


async def set_entitlement(employee_id: str, entity_id: str, year: int, entitlement: int) -> Dict[str, Any]:
    if isinstance(entitlement, bool) or int(entitlement) != entitlement or int(entitlement) < 0:
        raise ValueError("Jatah cuti harus bilangan bulat ≥ 0.")
    bal = await recompute_balance(employee_id, entity_id, year)
    await db.hr_leave_balances.update_one(
        {"id": bal["id"]},
        {"$set": {"entitlement": int(entitlement), "entitlement_override": True,
                  "remaining": int(entitlement) - int(bal.get("used") or 0), "updated_at": now_iso()}})
    return await get_balance(employee_id, entity_id, year)


async def list_balances(scope: Dict[str, Any], year: Optional[int] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = dict(scope or {})
    if year:
        q["year"] = year
    rows = await db.hr_leave_balances.find(q, {"_id": 0}).to_list(5000)
    return [safe_doc(r) for r in rows]


# ── Pengajuan cuti ──────────────────────────────────────────────────
async def submit_leave(emp: Dict[str, Any], payload: Dict[str, Any], actor_name: str) -> Dict[str, Any]:
    ltype = payload.get("leave_type") or "cuti_tahunan"
    if ltype not in LEAVE_TYPES:
        raise ValueError("Tipe cuti tidak dikenal.")
    date_from = (payload.get("date_from") or "")[:10]
    date_to = (payload.get("date_to") or date_from)[:10]
    d0 = _parse_date(date_from)
    if not d0:
        raise ValueError("Tanggal mulai tidak valid (format YYYY-MM-DD).")
    days_list = working_days(date_from, date_to)
    if not days_list:
        raise ValueError("Rentang tanggal tidak valid (pastikan ada hari kerja Senin–Jumat).")
    days = len(days_list)
    entity_id = emp.get("entity_id", "")
    # HR-03 — tanggal yang sudah tercakup cuti lain (pending/approved) ditolak.
    clash = await db.hr_leave_requests.find_one(
        {"employee_id": emp["id"], "status": {"$in": ["pending", "approved"]}, "work_dates": {"$in": days_list}},
        {"_id": 0, "number": 1})
    if clash:
        raise ValueError(f"Tanggal bertabrakan dengan pengajuan cuti {clash.get('number', '')}.")
    reserved: List[tuple] = []
    if LEAVE_TYPES[ltype]["deduct"]:
        # reservasi atomik per tahun: sisa = jatah − terpakai − pending (CAS $inc pending)
        for yr, n in _days_per_year(days_list).items():
            bal = await recompute_balance(emp["id"], entity_id, yr)
            ok = await db.hr_leave_balances.update_one(
                {"id": bal["id"], "$expr": {"$gte": [{"$subtract": [{"$subtract": ["$entitlement", "$used"]},
                                                                    "$pending"]}, n]}},
                {"$inc": {"pending": n}})
            if ok.modified_count != 1:
                for b_id, k in reserved:
                    await db.hr_leave_balances.update_one({"id": b_id}, {"$inc": {"pending": -k}})
                free = int(bal["entitlement"]) - int(bal["used"]) - int(bal["pending"])
                raise ValueError(f"Saldo cuti {yr} tidak cukup (sisa {max(free, 0)} hari setelah pengajuan "
                                 f"yang menunggu, diminta {n} hari).")
            reserved.append((bal["id"], n))
    number = await next_doc_number("hr_leave_requests", "number", "LV-", entity_id=entity_id)
    doc = {
        "id": new_id("leave"), "number": number,
        "employee_id": emp["id"], "employee_name": emp.get("name", ""),
        "entity_id": entity_id, "leave_type": ltype, "leave_label": LEAVE_TYPES[ltype]["label"],
        "date_from": date_from, "date_to": date_to, "days": days, "work_dates": days_list,
        "reason": payload.get("reason", ""), "attachment_url": payload.get("attachment_url", ""),
        "status": "pending", "approver": "", "approved_at": "", "reject_reason": "",
        "created_by": actor_name, "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.hr_leave_requests.insert_one(doc)
    for yr in _days_per_year(days_list):
        await recompute_balance(emp["id"], entity_id, yr)
    return safe_doc(doc)


async def _recompute_years(lv: Dict[str, Any]) -> None:
    for yr in (_days_per_year(_dates_of(lv)) or {current_year(): 0}):
        await recompute_balance(lv["employee_id"], lv.get("entity_id", ""), yr)


async def _mark_attendance_for_leave(lv: Dict[str, Any]) -> None:
    emp = safe_doc(await db.hr_employees.find_one({"id": lv["employee_id"]}, {"_id": 0}))
    if not emp:
        return
    meta = LEAVE_TYPES.get(lv.get("leave_type"), {})
    att_status = meta.get("att_status", "izin")
    note = f"{lv.get('leave_label', 'Cuti')}·{lv.get('number', '')}: {lv.get('reason', '')}".strip()
    for d in (lv.get("work_dates") or working_days(lv["date_from"], lv["date_to"])):
        await att.upsert_attendance(
            emp, d, "", "", "leave", lv.get("entity_id", ""),
            status_override=att_status, note=note, leave_request_id=lv["id"])


async def _clear_attendance_for_leave(lv: Dict[str, Any]) -> None:
    """Hapus rekaman absensi yang dibuat oleh cuti ini (method=leave) saat dibatalkan."""
    dates = lv.get("work_dates") or working_days(lv["date_from"], lv["date_to"])
    if not dates:
        return
    # HR-03 — hanya rekaman milik request ini (legacy tanpa id: dicocokkan lewat nomor di catatan)
    await db.hr_attendance.delete_many(
        {"employee_id": lv["employee_id"], "date": {"$in": dates}, "method": "leave",
         "$or": [{"leave_request_id": lv["id"]},
                 {"leave_request_id": {"$in": [None, ""]}, "note": {"$regex": f"·{lv.get('number', '')}:"}}]})


async def approve_leave(leave_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    lv = await db.hr_leave_requests.find_one({"id": leave_id}, {"_id": 0})
    if not lv:
        raise ValueError("Pengajuan cuti tidak ditemukan.")
    if lv["status"] != "pending":
        raise ValueError(f"Status '{lv['status']}' tidak bisa di-approve.")
    if lv.get("leave_type") in DEDUCT_TYPES:
        # HR-03 — cek ulang saldo saat approve: terpakai (approved lain) + request ini ≤ jatah
        for yr, n in _days_per_year(_dates_of(lv)).items():
            bal = await recompute_balance(lv["employee_id"], lv.get("entity_id", ""), yr)
            used_other, _ = await _year_usage(lv["employee_id"], yr, exclude_id=leave_id)
            if used_other + n > int(bal["entitlement"]):
                raise ValueError(f"Saldo cuti {yr} tidak cukup untuk disetujui (terpakai {used_other}, "
                                 f"jatah {bal['entitlement']}, diminta {n}).")
    res = await db.hr_leave_requests.update_one({"id": leave_id, "status": "pending"}, {"$set": {
        "status": "approved", "approver": actor.get("name", "system"),
        "approved_at": now_iso(), "updated_at": now_iso()}})
    if res.modified_count != 1:
        raise ValueError("Pengajuan cuti sudah diputuskan bersamaan — muat ulang.")
    if lv.get("leave_type") in DEDUCT_TYPES:
        for yr in _days_per_year(_dates_of(lv)):
            bal = await recompute_balance(lv["employee_id"], lv.get("entity_id", ""), yr)
            if int(bal["used"]) > int(bal["entitlement"]):  # approve paralel melewati jatah → batalkan milik ini
                await db.hr_leave_requests.update_one({"id": leave_id}, {"$set": {
                    "status": "pending", "approver": "", "approved_at": "", "updated_at": now_iso()}})
                await _recompute_years(lv)
                raise ValueError(f"Saldo cuti {yr} terlampaui oleh persetujuan bersamaan — coba lagi.")
    await _mark_attendance_for_leave(lv)
    await _recompute_years(lv)
    return safe_doc(await db.hr_leave_requests.find_one({"id": leave_id}, {"_id": 0}))


async def reject_leave(leave_id: str, actor: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    lv = await db.hr_leave_requests.find_one({"id": leave_id}, {"_id": 0})
    if not lv:
        raise ValueError("Pengajuan cuti tidak ditemukan.")
    if lv["status"] != "pending":
        raise ValueError(f"Status '{lv['status']}' tidak bisa ditolak.")
    res = await db.hr_leave_requests.update_one({"id": leave_id, "status": "pending"}, {"$set": {
        "status": "rejected", "approver": actor.get("name", "system"),
        "reject_reason": reason or "", "approved_at": now_iso(), "updated_at": now_iso()}})
    if res.modified_count != 1:
        raise ValueError("Pengajuan cuti sudah diputuskan bersamaan — muat ulang.")
    await _recompute_years(lv)
    return safe_doc(await db.hr_leave_requests.find_one({"id": leave_id}, {"_id": 0}))


async def cancel_leave(leave_id: str, actor: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    lv = await db.hr_leave_requests.find_one({"id": leave_id}, {"_id": 0})
    if not lv:
        raise ValueError("Pengajuan cuti tidak ditemukan.")
    if lv["status"] in ("cancelled", "rejected"):
        raise ValueError(f"Status '{lv['status']}' sudah final.")
    was_approved = lv["status"] == "approved"
    res = await db.hr_leave_requests.update_one({"id": leave_id, "status": lv["status"]}, {"$set": {
        "status": "cancelled", "reject_reason": reason or "", "updated_at": now_iso()}})
    if res.modified_count != 1:
        raise ValueError("Pengajuan cuti berubah bersamaan — muat ulang.")
    if was_approved:
        await _clear_attendance_for_leave(lv)
    await _recompute_years(lv)
    return safe_doc(await db.hr_leave_requests.find_one({"id": leave_id}, {"_id": 0}))


async def list_leaves(scope: Dict[str, Any], status: Optional[str] = None,
                      employee_id: Optional[str] = None, month: Optional[str] = None,
                      approved_only: bool = False) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = dict(scope or {})
    if status:
        q["status"] = status
    if approved_only:
        q["status"] = "approved"
    if employee_id:
        q["employee_id"] = employee_id
    if month:
        q["date_from"] = {"$regex": f"^{month}"}
    rows = await db.hr_leave_requests.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return [safe_doc(r) for r in rows]


async def my_leaves(emp: Dict[str, Any]) -> Dict[str, Any]:
    rows = await db.hr_leave_requests.find(
        {"employee_id": emp["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    bal = await get_balance(emp["id"], emp.get("entity_id", ""), current_year())
    return {"employee": {"id": emp["id"], "name": emp.get("name", "")},
            "balance": bal, "requests": [safe_doc(r) for r in rows],
            "leave_types": [{"value": k, "label": v["label"], "deduct": v["deduct"]}
                            for k, v in LEAVE_TYPES.items()]}


# ── Lembur ───────────────────────────────────────────────────────
async def submit_overtime(emp: Dict[str, Any], payload: Dict[str, Any], actor_name: str) -> Dict[str, Any]:
    d = (payload.get("date") or wib_today())[:10]
    if not _parse_date(d):
        raise ValueError("Tanggal lembur tidak valid (format YYYY-MM-DD).")
    hours = float(payload.get("hours") or 0)
    if hours <= 0 or hours > 12:
        raise ValueError("Jam lembur harus > 0 dan ≤ 12.")
    entity_id = emp.get("entity_id", "")
    number = await next_doc_number("hr_overtime", "number", "OT-", entity_id=entity_id)
    doc = {
        "id": new_id("ot"), "number": number,
        "employee_id": emp["id"], "employee_name": emp.get("name", ""),
        "entity_id": entity_id, "date": d, "period": d[:7],
        "hours": round(hours, 2), "minutes": int(round(hours * 60)),
        "reason": payload.get("reason", ""), "rate_basis": payload.get("rate_basis", "normal"),
        "status": "pending", "approver": "", "approved_at": "", "reject_reason": "",
        "created_by": actor_name, "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.hr_overtime.insert_one(doc)
    return safe_doc(doc)


async def approve_overtime(ot_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    ot = await db.hr_overtime.find_one({"id": ot_id}, {"_id": 0})
    if not ot:
        raise ValueError("Pengajuan lembur tidak ditemukan.")
    if ot["status"] != "pending":
        raise ValueError(f"Status '{ot['status']}' tidak bisa di-approve.")
    await db.hr_overtime.update_one({"id": ot_id}, {"$set": {
        "status": "approved", "approver": actor.get("name", "system"),
        "approved_at": now_iso(), "updated_at": now_iso()}})
    return safe_doc(await db.hr_overtime.find_one({"id": ot_id}, {"_id": 0}))


async def reject_overtime(ot_id: str, actor: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    ot = await db.hr_overtime.find_one({"id": ot_id}, {"_id": 0})
    if not ot:
        raise ValueError("Pengajuan lembur tidak ditemukan.")
    if ot["status"] != "pending":
        raise ValueError(f"Status '{ot['status']}' tidak bisa ditolak.")
    await db.hr_overtime.update_one({"id": ot_id}, {"$set": {
        "status": "rejected", "approver": actor.get("name", "system"),
        "reject_reason": reason or "", "approved_at": now_iso(), "updated_at": now_iso()}})
    return safe_doc(await db.hr_overtime.find_one({"id": ot_id}, {"_id": 0}))


async def list_overtime(scope: Dict[str, Any], status: Optional[str] = None,
                        employee_id: Optional[str] = None, month: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = dict(scope or {})
    if status:
        q["status"] = status
    if employee_id:
        q["employee_id"] = employee_id
    if month:
        q["period"] = month
    rows = await db.hr_overtime.find(q, {"_id": 0}).sort("date", -1).to_list(2000)
    return [safe_doc(r) for r in rows]


async def my_overtime(emp: Dict[str, Any]) -> Dict[str, Any]:
    rows = await db.hr_overtime.find(
        {"employee_id": emp["id"]}, {"_id": 0}).sort("date", -1).to_list(200)
    return {"employee": {"id": emp["id"], "name": emp.get("name", "")},
            "requests": [safe_doc(r) for r in rows]}
