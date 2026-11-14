"""PY-T1 (PY-02, K-37, K-40) — antrean masukan komponen gaji (`hr_pay_inputs`).

Angka dari modul lain (lembar insentif, lembur terlambat, kasbon, rapel) dan isian manual masuk ke proses gaji lewat SATU
antrean berstatus: `pending` (isian manual belum disahkan) → `approved` → `used` (dipakai sebuah proses gaji) →
kembali `approved` bila proses itu dihitung ulang, dibatalkan, atau dianulir; `cancelled` kapan saja sebelum dipakai
proses yang sudah diajukan.

Kunci `source_key` unik per baris sumber: mengirim ulang kunci yang sama mengembalikan dokumen yang sama (nominal tidak
dobel). Perpindahan status selalu bersyarat status lama (INV-ATOMIC-01).

Pengisi otomatis (lembar insentif KM-T4, kasbon K-40, lembur terlambat) belum dibangun: antreannya siap, sementara
lewat isian manual (`create_manual_input`).
"""
import re
from typing import Any, Dict, Iterable, List, Optional

from db import db
from core_utils import new_id, now_iso, safe_doc

STATUSES = ("pending", "approved", "used", "cancelled")
STATUS_LABEL = {"pending": "Menunggu disahkan", "approved": "Disahkan", "used": "Terpakai", "cancelled": "Dibatalkan"}
SOURCE_TYPES = ("incentive_sheet", "overtime", "cash_advance", "rapel", "manual")
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
PERIOD_MSG = "Periode harus berbentuk TTTT-BB, mis. 2026-10."


class InputConflict(ValueError):
    """Perpindahan status yang tidak boleh (router → 409). Pesan siap tampil."""


def check_period(period: str) -> str:
    p = str(period or "").strip()
    if not PERIOD_RE.match(p):
        raise ValueError(PERIOD_MSG)
    return p


def _amount(v: Any) -> int:
    try:
        f = float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError("Nominal harus angka rupiah bulat.") from exc
    if f != int(f):
        raise ValueError("Nominal harus angka rupiah bulat (tanpa sen).")
    if int(f) == 0:
        raise ValueError("Nominal tidak boleh nol.")
    return int(f)


async def _component(entity_id: str, code: str) -> Dict[str, Any]:
    from services import hr_pay_components as comps
    comp = (await comps.components_for(entity_id)).get(str(code or "").strip().upper())
    if not comp or comp.get("is_active") is False or comp.get("calc") != "masukan":
        raise ValueError(f"Komponen {code} bukan komponen masukan.")
    return comp


async def _employee(entity_id: str, employee_id: str) -> Dict[str, Any]:
    emp = await db.hr_employees.find_one({"id": employee_id, "entity_id": entity_id},
                                         {"_id": 0, "id": 1, "name": 1})
    if not emp:
        raise ValueError("Karyawan tidak ditemukan di PT ini.")
    return emp


async def enqueue_input(*, entity_id: str, employee_id: str, pay_period: str, component_code: str, label: str,
                        amount: Any, source_type: str, source_key: str, source_ref: Optional[Dict[str, Any]] = None,
                        basis_period: str = "", actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Masukan dari modul sumber, langsung `approved` (sumbernya sudah disahkan di modulnya). Kunci `source_key` sama →
    dokumen yang sama (tidak ditimpa, nominal tidak dobel)."""
    actor = actor or {}
    key = str(source_key or "").strip()
    if not key:
        raise ValueError("Kunci sumber masukan wajib diisi.")
    found = await db.hr_pay_inputs.find_one({"source_key": key}, {"_id": 0})
    if found:
        return safe_doc(found)
    if source_type not in SOURCE_TYPES:
        raise ValueError("Jenis sumber masukan tidak dikenal.")
    period = check_period(pay_period)
    comp = await _component(entity_id, component_code)
    emp = await _employee(entity_id, employee_id)
    doc = _doc(entity_id=entity_id, emp=emp, period=period, comp=comp, label=label, amount=_amount(amount),
               source_type=source_type, source_key=key, source_ref=source_ref or {}, basis_period=basis_period,
               status="approved", actor=actor)
    doc["approved_by"] = actor.get("name", "system")
    doc["approved_by_id"] = actor.get("id", "")
    doc["approved_at"] = now_iso()
    from pymongo.errors import DuplicateKeyError
    try:
        await db.hr_pay_inputs.update_one({"source_key": key}, {"$setOnInsert": doc}, upsert=True)
    except DuplicateKeyError:   # D7 — dua kiriman bersamaan: indeks unik `source_key`, yang kalah membaca pemenangnya
        pass
    return safe_doc(await db.hr_pay_inputs.find_one({"source_key": key}, {"_id": 0}))


def _doc(*, entity_id, emp, period, comp, label, amount, source_type, source_key, source_ref, basis_period, status,
         actor, reason="") -> Dict[str, Any]:
    iid = new_id("pinp")
    return {
        "id": iid, "entity_id": entity_id, "employee_id": emp["id"], "employee_name": emp.get("name", ""),
        "pay_period": period, "component_code": comp["code"], "component_name": comp.get("name", ""),
        "label": str(label or "").strip() or comp.get("name", ""), "basis_period": str(basis_period or "").strip(),
        "amount": amount, "source_type": source_type, "source_key": source_key or f"manual:{iid}",
        "source_ref": source_ref or {}, "status": status, "reason": reason,
        "created_by": actor.get("name", "system"), "created_by_id": actor.get("id", ""), "created_at": now_iso(),
        "approved_by": "", "approved_by_id": "", "approved_at": "", "used_run_id": "", "used_run_number": "",
        "used_at": "", "cancelled_by": "", "cancelled_by_id": "", "cancelled_at": "", "cancel_reason": "",
        "updated_at": now_iso()}


async def create_manual_input(entity_id: str, data: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Isian manual (`payroll.create`) → `pending`; ikut proses gaji sesudah disahkan (`payroll.approve`)."""
    reason = str(data.get("reason") or "").strip()
    if not reason:
        raise ValueError("Alasan wajib diisi.")
    period = check_period(data.get("pay_period"))
    comp = await _component(entity_id, data.get("component_code"))
    emp = await _employee(entity_id, str(data.get("employee_id") or ""))
    basis = str(data.get("basis_period") or "").strip()
    if basis:
        check_period(basis)
    doc = _doc(entity_id=entity_id, emp=emp, period=period, comp=comp, label=data.get("label"),
               amount=_amount(data.get("amount")), source_type="manual", source_key="",
               source_ref={"type": "manual"}, basis_period=basis, status="pending", actor=actor, reason=reason)
    doc["source_ref"] = {"type": "manual", "id": doc["id"]}
    await db.hr_pay_inputs.insert_one(dict(doc))
    return doc


async def get_input(input_id: str) -> Optional[Dict[str, Any]]:
    return safe_doc(await db.hr_pay_inputs.find_one({"id": input_id}, {"_id": 0}))


async def approve_input(input_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    cur = await get_input(input_id)
    if not cur:
        raise LookupError("Masukan tidak ditemukan.")
    if cur["status"] != "pending":
        raise InputConflict(f"Masukan ini berstatus {STATUS_LABEL.get(cur['status'], cur['status'])}, jadi tidak "
                            f"bisa disahkan.")
    res = await db.hr_pay_inputs.update_one(
        {"id": input_id, "status": "pending"},
        {"$set": {"status": "approved", "approved_by": actor.get("name", "system"),
                  "approved_by_id": actor.get("id", ""), "approved_at": now_iso(), "updated_at": now_iso()}})
    if not res.modified_count:
        raise InputConflict("Masukan ini baru saja berubah — muat ulang.")
    return await get_input(input_id)


async def _used_conflict(doc: Dict[str, Any]) -> InputConflict:
    nomor = doc.get("used_run_number") or ""
    if not nomor and doc.get("used_run_id"):
        run = await db.hr_payroll_runs.find_one({"id": doc["used_run_id"]}, {"_id": 0, "number": 1}) or {}
        nomor = run.get("number") or doc["used_run_id"]
    return InputConflict(f"Masukan ini sudah dipakai di penggajian {nomor}, jadi tidak bisa dibatalkan.")


async def _cancel(cur: Dict[str, Any], actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    alasan = str(reason or "").strip()
    if len(alasan) < 5:   # K-14 — alasan minimum seragam 5 huruf
        raise ValueError("Alasan wajib diisi (minimal 5 huruf).")
    st = cur["status"]
    patch = {"status": "cancelled", "cancelled_by": actor.get("name", "system"),
             "cancelled_by_id": actor.get("id", ""), "cancelled_at": now_iso(), "cancel_reason": alasan,
             "cancelled_from": st, "updated_at": now_iso()}
    if st in ("pending", "approved"):
        res = await db.hr_pay_inputs.update_one({"id": cur["id"], "status": st}, {"$set": patch})
        if not res.modified_count:
            raise InputConflict("Masukan ini baru saja berubah — muat ulang.")
        return await get_input(cur["id"])
    if st == "used":
        # Dipakai proses yang MASIH DRAF: boleh dibatalkan; proses itu ditandai "perlu dihitung ulang" (pengajuan
        # ditolak sampai dihitung ulang). Proses yang sudah diajukan/disahkan/diposting → 409.
        run_id = cur.get("used_run_id") or ""
        marked = await db.hr_payroll_runs.update_one(
            {"id": run_id, "status": "draft", "recalc_claim": {"$exists": False}},
            {"$set": {"inputs_stale_at": now_iso()}})
        if not marked.matched_count:
            raise await _used_conflict(cur)
        res = await db.hr_pay_inputs.update_one({"id": cur["id"], "status": "used", "used_run_id": run_id},
                                                {"$set": patch})
        if not res.modified_count:
            raise InputConflict("Masukan ini baru saja berubah — muat ulang.")
        return await get_input(cur["id"])
    raise InputConflict(f"Masukan ini berstatus {STATUS_LABEL.get(st, st)}, jadi tidak bisa dibatalkan.")


async def cancel_input(source_key: str, *, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Pembatalan dari modul sumber (kunci sumber). Lihat `_cancel` untuk aturan status."""
    cur = safe_doc(await db.hr_pay_inputs.find_one({"source_key": source_key}, {"_id": 0}))
    if not cur:
        raise LookupError("Masukan tidak ditemukan.")
    return await _cancel(cur, actor, reason)


async def cancel_input_by_id(input_id: str, *, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    cur = await get_input(input_id)
    if not cur:
        raise LookupError("Masukan tidak ditemukan.")
    return await _cancel(cur, actor, reason)


async def _codes_for(entity_id: str, run_type: str) -> List[str]:
    from services import hr_pay_components as comps
    return [c["code"] for c in (await comps.components_for(entity_id)).values()
            if c.get("calc") == "masukan" and comps.allowed(c, run_type)]


async def approved_for(entity_id: str, pay_period: str, run_type: str,
                       employee_ids: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """Masukan `approved` yang akan dimuat proses jenis itu (pratinjau — tidak menandai)."""
    q: Dict[str, Any] = {"entity_id": entity_id, "pay_period": pay_period, "status": "approved",
                         "component_code": {"$in": await _codes_for(entity_id, run_type)}}
    if employee_ids is not None:
        q["employee_id"] = {"$in": list(employee_ids)}
    rows = await db.hr_pay_inputs.find(q, {"_id": 0}).sort("created_at", 1).to_list(None)
    return [safe_doc(r) for r in rows]


async def take_for_run(entity_id: str, pay_period: str, run_type: str, run_id: str, *, run_number: str = "",
                       employee_ids: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """`approved` → `used` (bersyarat status lama, satu per satu) untuk proses `run_id`. → masukan yang terambil."""
    taken: List[Dict[str, Any]] = []
    for inp in await approved_for(entity_id, pay_period, run_type, employee_ids):
        res = await db.hr_pay_inputs.update_one(
            {"id": inp["id"], "status": "approved"},
            {"$set": {"status": "used", "used_run_id": run_id, "used_run_number": run_number, "used_at": now_iso(),
                      "updated_at": now_iso()}})
        if res.modified_count:
            taken.append({**inp, "status": "used", "used_run_id": run_id, "used_run_number": run_number})
    return taken


async def inputs_for_run(run_id: str) -> List[Dict[str, Any]]:
    rows = await db.hr_pay_inputs.find({"used_run_id": run_id, "status": "used"},
                                       {"_id": 0}).sort("created_at", 1).to_list(None)
    return [safe_doc(r) for r in rows]


async def release_inputs(ids: Iterable[str], run_id: str) -> int:
    ids = [i for i in ids if i]
    if not ids:
        return 0
    res = await db.hr_pay_inputs.update_many(
        {"id": {"$in": ids}, "status": "used", "used_run_id": run_id},
        {"$set": {"status": "approved", "used_run_id": "", "used_run_number": "", "used_at": "",
                  "updated_at": now_iso()}})
    return res.modified_count


async def retake_inputs(ids: Iterable[str], run_id: str, run_number: str = "") -> int:
    """Kompensasi hitung ulang yang gagal: masukan yang tadinya dipakai proses itu (dan masih `approved`) diambil lagi."""
    ids = [i for i in ids if i]
    if not ids:
        return 0
    res = await db.hr_pay_inputs.update_many(
        {"id": {"$in": ids}, "status": "approved"},
        {"$set": {"status": "used", "used_run_id": run_id, "used_run_number": run_number, "used_at": now_iso(),
                  "updated_at": now_iso()}})
    return res.modified_count


async def release_for_run(run_id: str) -> int:
    """`used` → `approved` untuk semua masukan proses itu (hitung ulang, batal, anulir). → jumlah yang dilepas."""
    res = await db.hr_pay_inputs.update_many(
        {"used_run_id": run_id, "status": "used"},
        {"$set": {"status": "approved", "used_run_id": "", "used_run_number": "", "used_at": "",
                  "updated_at": now_iso()}})
    return res.modified_count


async def list_inputs(scope: Dict[str, Any], *, pay_period: str = "", status: str = "", employee_id: str = "",
                      page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    q: Dict[str, Any] = dict(scope or {})
    if pay_period:
        q["pay_period"] = check_period(pay_period)
    if status:
        if status not in STATUSES:
            raise ValueError("Status masukan tidak dikenal.")
        q["status"] = status
    if employee_id:
        q["employee_id"] = employee_id
    total = await db.hr_pay_inputs.count_documents(q)
    rows = await db.hr_pay_inputs.find(q, {"_id": 0}).sort([("pay_period", -1), ("created_at", -1)]) \
        .skip(max(0, (page - 1) * page_size)).limit(page_size).to_list(page_size)
    return {"items": [safe_doc(r) for r in rows], "total": total, "page": page, "page_size": page_size}
