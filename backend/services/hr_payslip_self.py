"""PY-T5 — swalayan slip gaji karyawan (Profil Saya › kartu "Slip Gaji Saya").

Karyawan hanya melihat slipnya sendiri yang sudah TERBIT. Satu penentu: `slip_visible_to_owner` — status slip DAN status
prosesnya termasuk daftar yang diizinkan pengaturan `hr.slip_swalayan_sejak` PT slip itu (global → PT, bawaan
`dibayar`):

* `dibayar`  → {paid}
* `disahkan` → {approved, posted, paid}   (perilaku sebelum unit ini)

Draf, menunggu pengesahan, dibatalkan, sedang dianulir, dan dianulir (serta `rejected` data lama) SELALU tertutup bagi
pemiliknya, apa pun pengaturannya — angkanya belum atau tidak lagi sah. Status antara proses `posting`/`paying` dibaca
sebagai status asalnya (`approved`/`posted`): slip tidak hilang di tengah langkah posting/bayar. Status slip sendiri
mengikuti prosesnya (`hr_payroll_service._set_run`); proses ikut diperiksa karena selama `voiding` slip masih `posted`.

Pemegang `hr.view` tidak memakai penentu ini (router `routers/hr_payroll.py:_can_view_slip`). Jawaban swalayan hanya
memuat isian slip sendiri (`OWNER_FIELDS`, komponen `COMPONENT_FIELDS`) — tanpa id karyawan lain, akun buku besar, atau
sumber masukan.
"""
import re
from typing import Any, Dict, List, Optional

from db import db
from core_utils import safe_doc

KUNCI_SLIP = "hr.slip_swalayan_sejak"
TERBIT: Dict[str, frozenset] = {
    "dibayar": frozenset({"paid"}),
    "disahkan": frozenset({"approved", "posted", "paid"}),
}
SELALU_TERTUTUP = frozenset({"draft", "pending_approval", "cancelled", "voiding", "void", "rejected"})
_ANTARA = {"posting": "approved", "paying": "posted"}   # klaim langkah yang sedang berjalan (PK-22) → status asal
BELUM_TERBIT = "Slip gaji ini belum terbit."
TAHUN_MSG = "Tahun harus berbentuk TTTT, mis. 2026."
_TAHUN_RE = re.compile(r"^\d{4}$")
_SEMUA_TERBIT = sorted(TERBIT["disahkan"])   # superset kueri; disaring per PT sesudahnya
OWNER_FIELDS = ("id", "number", "period", "run_type", "status", "paid_at", "paid_date", "gross", "net", "pph21",
                "components", "bank")
COMPONENT_FIELDS = ("code", "label", "kind", "amount", "rate", "basis_period")
_BELUM = object()


async def visible_since(entity_id: str) -> str:
    """`hr.slip_swalayan_sejak` untuk PT itu (02 §2.2); galat/nilai asing → bawaan registry (KF-06)."""
    import config_registry as registry
    from services.config_resolver import value_of
    bawaan = registry.require(KUNCI_SLIP)["default"]
    try:
        v = await value_of(KUNCI_SLIP, {"entity_id": entity_id or ""})
    except Exception:   # noqa: BLE001 — cadangan = bawaan registry, bukan nilai lain
        v = bawaan
    return v if v in TERBIT else bawaan


def terbit(since: str, slip_status: str, run_status: Optional[str] = None) -> bool:
    """Murni: slip berstatus `slip_status` (proses `run_status`, None = tidak diketahui) terlihat pemiliknya?"""
    boleh = TERBIT.get(since) or TERBIT["dibayar"]
    if (slip_status or "") in SELALU_TERTUTUP or slip_status not in boleh:
        return False
    if run_status is None:
        return True
    run_status = _ANTARA.get(run_status, run_status)
    return run_status not in SELALU_TERTUTUP and run_status in boleh


async def slip_visible_to_owner(slip: Dict[str, Any], run: Any = _BELUM, *, since: Optional[str] = None) -> bool:
    """PY-T5 — benar bila slip sudah terbit bagi pemiliknya menurut pengaturan PT slip itu. `run` = dokumen proses
    (dibaca bila tidak diberikan; proses yang tidak ada → hanya status slip yang dinilai); `since` = nilai pengaturan
    yang sudah dibaca (daftar swalayan membacanya sekali per PT)."""
    if run is _BELUM:
        run = await db.hr_payroll_runs.find_one({"id": slip.get("run_id") or "__none__"}, {"_id": 0, "status": 1})
    if since is None:
        since = await visible_since(slip.get("entity_id") or "")
    return terbit(since, slip.get("status") or "", (run or {}).get("status") if run else None)


def _tanggal_bayar(run: Dict[str, Any]) -> str:
    from services import book_date
    if run.get("paid_date"):
        return str(run["paid_date"])[:10]
    try:
        return book_date.tanggal_buku(run["paid_at"]) if run.get("paid_at") else ""
    except ValueError:
        return ""


def owner_row(slip: Dict[str, Any], run: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Isian slip untuk pemiliknya (kartu Slip Gaji Saya)."""
    run = run or {}
    comps = [{k: c[k] for k in COMPONENT_FIELDS if k in c and c[k] not in (None, "")}
             for c in slip.get("components") or [] if isinstance(c, dict)]
    row = {
        "id": slip.get("id", ""), "number": slip.get("number", ""), "period": slip.get("period", ""),
        "run_type": slip.get("run_type") or run.get("run_type") or "regular", "status": slip.get("status", ""),
        "paid_at": run.get("paid_at") or "", "paid_date": _tanggal_bayar(run),
        "gross": slip.get("gross", 0), "net": slip.get("net", 0), "pph21": slip.get("pph21", 0),
        "components": comps, "bank": slip.get("bank") or {},
    }
    return {k: row[k] for k in OWNER_FIELDS}


def _cek_tahun(year: Any) -> int:
    y = str(year or "").strip()
    if not _TAHUN_RE.match(y):
        raise ValueError(TAHUN_MSG)
    return int(y)


async def my_payslips(user: Dict[str, Any], *, year: Optional[str] = None,
                      period: Optional[str] = None) -> Dict[str, Any]:
    """`GET /api/hr/payslips/me` — slip TERBIT milik karyawan yang tertaut akun ini.

    `years` = tahun yang punya slip terlihat (menurun); `payslips` = slip terlihat tahun `year` (bawaan tahun berjalan
    WIB) atau periode `period` (TTTT-BB; bila diisi, `year` = tahun periode itu), urut periode menurun lalu tanggal bayar
    menurun (belum dibayar — pengaturan `disahkan` — di atas). `visible_since` = pengaturan PT karyawan saat ini.
    Akun tanpa karyawan tertaut → `{employee: None, years: [], payslips: []}`."""
    from services import book_date
    from services import hr_pay_inputs as _pi
    emp = await db.hr_employees.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1, "name": 1, "entity_id": 1})
    if not emp:
        return {"employee": None, "years": [], "payslips": []}
    if period:
        period = _pi.check_period(period)
        tahun = int(period[:4])
    else:
        tahun = _cek_tahun(year) if year not in (None, "") else int(book_date.tanggal_buku()[:4])
    # Satu karyawan: belasan slip per tahun — dibaca utuh (tanpa batas diam-diam, 02 §5 D4), proyeksi sempit dulu.
    calon: List[Dict[str, Any]] = [s async for s in db.hr_payslips.find(
        {"employee_id": emp["id"], "status": {"$in": _SEMUA_TERBIT}},
        {"_id": 0, "id": 1, "run_id": 1, "entity_id": 1, "status": 1, "period": 1})]
    runs: Dict[str, Dict[str, Any]] = {}
    ids = sorted({s.get("run_id") for s in calon if s.get("run_id")})
    if ids:
        async for r in db.hr_payroll_runs.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "status": 1, "run_type": 1,
                                                                       "paid_at": 1, "paid_date": 1}):
            runs[r["id"]] = r
    sejak: Dict[str, str] = {}
    terlihat: List[Dict[str, Any]] = []
    for s in calon:
        eid = s.get("entity_id") or ""
        if eid not in sejak:
            sejak[eid] = await visible_since(eid)
        if await slip_visible_to_owner(s, runs.get(s.get("run_id") or ""), since=sejak[eid]):
            terlihat.append(s)
    years = sorted({int(str(s.get("period") or "0000")[:4]) for s in terlihat if str(s.get("period") or "")[:4].isdigit()},
                   reverse=True)
    pilih = [s["id"] for s in terlihat if (s.get("period") == period if period else
                                            str(s.get("period") or "").startswith(f"{tahun:04d}-"))]
    rows: List[Dict[str, Any]] = []
    if pilih:
        async for s in db.hr_payslips.find({"id": {"$in": pilih}}, {"_id": 0}):
            s = safe_doc(s)
            rows.append(owner_row(s, runs.get(s.get("run_id") or "")))
    rows.sort(key=lambda r: (r["period"], r["paid_at"] or "~", r["number"]), reverse=True)
    if emp.get("entity_id") not in sejak:
        sejak[emp.get("entity_id") or ""] = await visible_since(emp.get("entity_id") or "")
    return {"employee": {"id": emp["id"], "name": emp.get("name", "")},
            "visible_since": sejak[emp.get("entity_id") or ""], "year": tahun, "years": years, "payslips": rows}
