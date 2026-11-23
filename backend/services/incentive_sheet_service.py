"""KM-T3 (KM-05, keputusan K-25; K-19 … K-24 lewat versi definisi yang dipotret) — **Lembar Insentif**.

Satu lembar = satu dokumen keputusan insentif per PT per periode bayar (`incentive_sheets`), berisi baris per sales dan
komponen. Nominal **diketik orang** — server tidak pernah mengisi `amount` dan tidak punya rumus. Angka dasar tiap baris
(target, omzet, retur, pencairan, kualitas harga) DIPOTRET saat baris dibuat dari pengumpul Capaian KM-T2
(`incentive_achievement.angka_sales`) bersama versi definisi angka PT (`incentive_definitions.current_definition`), lalu
disalin apa adanya. Sesudah lembar disahkan, potret tidak pernah dihitung ulang (`02_STANDAR.md` §5 D3); perubahan data
sumber sesudahnya tampil sebagai `drift` (bahan baris penyesuaian di lembar berikutnya), bukan perubahan otomatis.

Status: `draft` → `submitted` → `approved` (→ `paid`, ditulis KM-T4) · `submitted` → `draft` (dikembalikan) ·
`draft` → `cancelled`. Semua tulisan memakai pembaruan bersyarat status lama + nomor revisi (`rev`), sehingga dua
pengesahan bersamaan menghasilkan satu 200 dan satu 409. Satu (sales, komponen, periode dasar) hanya boleh diputus sekali
di lembar yang masih berlaku: `active_keys` + indeks unik wajib `uq_isheet_active_key` (lapis A); lembar dibatalkan
mengosongkan `active_keys`. Koreksi sesudah disahkan = baris penyesuaian (boleh negatif, wajib catatan dan rujukan).

Kontrol dua orang (K-25): `kontrol.lembar_insentif.min_orang` / `batas_nominal` (bawaan satu orang) lewat
`dual_control.tolak_bila_pelaku_sama` di `approve_sheet`; siapa yang boleh memutus = Aturan Persetujuan jenis
`incentive_sheet` (`approval_policy_service.guard_door`, bawaan semua pemegang `incentive.approve`).

KM-T4 — di PT bermode `sheet` (`hr.payroll_commission_mode`) pengesahan diteruskan ke `incentive_payroll.sahkan_tertaut`
(status antara `approving`, masukan gaji `INSENTIF`, jurnal beban/hutang insentif); di PT lain lembar tetap keputusan saja
(`payroll_linked: false`, `gl_status: "not_required"`). `paid` ditulis sesudah proses gaji yang memuat barisnya diposting.
"""
from __future__ import annotations

import hashlib
import io
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core_utils import new_id, next_doc_number, now_iso, rupiah, safe_doc
from db import db
from services import incentive_achievement as iach
from services import incentive_definitions as idef
from services import incentive_periods as ip

COLL = "incentive_sheets"
#: Awalan nomor per PT. Spesifikasi menulis `INS-`, tetapi awalan itu sudah dipakai Inspeksi mutu (`doc_number_kinds`
#: `ins`) dan deret per PT berkunci awalan — dua jenis dokumen akan berbagi deret dan nomor tercetak yang sama.
PREFIX = "LIN-"
AKSI_KONTROL = "lembar_insentif"
JENIS_PERSETUJUAN = "incentive_sheet"

STATUS_LABEL = {"draft": "Draf", "submitted": "Diajukan", "approving": "Sedang disahkan", "approved": "Disahkan",
                "paid": "Dibayarkan", "cancelled": "Dibatalkan"}
STATUSES = tuple(STATUS_LABEL)
DISAHKAN = ("approved", "paid")
BASIS_TYPES = ("month", "quarter", "year")
#: Angka yang dibandingkan dengan keadaan sekarang (`drift`) — label untuk layar.
DRIFT_FIELDS = {"omzet_bersih": "Omzet bersih", "uang_masuk": "Uang masuk", "realisasi_harga_pct": "Realisasi harga"}
MONEY_FIELDS = ("target_sales", "omzet", "retur", "omzet_bersih", "target_collection", "uang_masuk")
SNAP_FIELDS = ("target_sales", "omzet", "retur", "omzet_bersih", "pct_omzet", "target_collection", "uang_masuk",
               "pct_pencairan", "realisasi_harga_pct", "porsi_bawah_acuan_pct", "margin_pct", "catatan_data")
MAX_NOMINAL = 1_000_000_000_000
MAX_BARIS = 500
MIN_ALASAN = 5

# ── Pesan (siap tampil) ──────────────────────────────────────────────────────────────────────────────────────────────
PESAN_STATUS = "Lembar {nomor} berstatus {status}, jadi tidak bisa diubah."
PESAN_KEMBAR = "{sales} · {komponen} · {periode} sudah ada di lembar {nomor}."
PESAN_NOMINAL_KOSONG = "Isi nominal semua baris sebelum mengajukan."
PESAN_NEGATIF = "Nominal negatif hanya untuk baris penyesuaian."
PESAN_PENYESUAIAN = "Baris penyesuaian harus merujuk baris lembar yang sudah disahkan dan diberi catatan."
PESAN_KOREKSI = "Beri catatan untuk setiap nominal yang dikoreksi."
PESAN_KOMPONEN = "Komponen ini tidak aktif di PT yang sedang dibuka."
PESAN_TANPA_BARIS = "Tambahkan minimal satu baris sebelum mengajukan."
PESAN_ALASAN = "Tulis alasan minimal 5 huruf."
PESAN_PERIODE_BAYAR = "Periode bayar harus satu bulan, contoh: 2026-11."
PESAN_PERIODE_DASAR = "Periode dasar tidak sesuai jenisnya. Contoh: 2026-10, 2026-Q3, atau 2026."
PESAN_BASIS_KOMPONEN = "Komponen {komponen} berperiode dasar {basis}; pilih periode dasar yang sama."
PESAN_NOMINAL = "Nominal harus rupiah bulat, paling besar Rp 1.000.000.000.000."
PESAN_BARIS = "Baris tidak ditemukan di lembar ini."
PESAN_BERUBAH = "Lembar {nomor} baru saja diubah orang lain. Muat ulang lalu ulangi."
PESAN_BARIS_PENUH = "Satu lembar paling banyak 500 baris."
PESAN_SALES_KOSONG = "Pilih sales untuk baris ini."


class LembarError(ValueError):
    """Galat lembar insentif dengan kalimat siap tampil; `status` = kode HTTP."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ── Pembantu kecil ───────────────────────────────────────────────────────────────────────────────────────────────────
def status_label(status: str) -> str:
    return STATUS_LABEL.get(status or "", status or "—")


def _pesan_status(doc: Dict[str, Any]) -> str:
    return PESAN_STATUS.format(nomor=doc.get("number") or "", status=status_label(doc.get("status")))


def _harus_status(doc: Dict[str, Any], status: str) -> None:
    if (doc or {}).get("status") != status:
        raise LembarError(_pesan_status(doc or {}), 409)


def _siapa(actor: Dict[str, Any]) -> Dict[str, str]:
    return {"id": str((actor or {}).get("id") or ""), "name": str((actor or {}).get("name") or "")}


def _riwayat(action: str, actor: Dict[str, Any], at: str, reason: str, dari: str, ke: str) -> Dict[str, Any]:
    return {"action": action, "by_id": _siapa(actor)["id"], "by_name": _siapa(actor)["name"], "at": at,
            "reason": reason, "from_status": dari, "to_status": ke}


def basis_label(period_type: str, period: str) -> str:
    """Label periode dasar: `month` · `2026-10` → "Okt 2026"; `quarter` · `2026-Q3` → "Triwulan III 2026"."""
    if period_type == "month":
        return iach._short_month(period)
    return ip.period_label(period_type, period)


def _kunci(line: Dict[str, Any]) -> str:
    return f"{line.get('sales_id')}|{line.get('component_id')}|{line.get('basis_period')}"


def _active_keys(lines: Iterable[Dict[str, Any]]) -> List[str]:
    return sorted({_kunci(x) for x in lines if not x.get("is_adjustment")})


def _totals(lines: List[Dict[str, Any]]) -> Dict[str, int]:
    """Banyak baris dan Σ nominal (rupiah bulat; nominal kosong = 0) — D5: total = Σ baris."""
    return {"lines": len(lines), "amount": sum(int(x.get("amount") or 0) for x in lines)}


def _nominal(v: Any, penyesuaian: bool) -> Optional[int]:
    """Nominal diketik → rupiah bulat; kosong → None. Negatif hanya untuk baris penyesuaian."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        d = Decimal(str(v).strip())
    except (InvalidOperation, ValueError):
        raise LembarError(PESAN_NOMINAL)
    if not d.is_finite() or d != d.to_integral_value() or abs(d) > MAX_NOMINAL:
        raise LembarError(PESAN_NOMINAL)
    n = int(d)
    if n < 0 and not penyesuaian:
        raise LembarError(PESAN_NEGATIF)
    return n


def _alasan(reason: Any) -> str:
    r = str(reason or "").strip()
    if len(r) < MIN_ALASAN:
        raise LembarError(PESAN_ALASAN)
    return r[:500]


def _periode_bayar(v: Any) -> str:
    try:
        return ip.normalize("month", str(v or "").strip())[1]
    except ip.PeriodeError:
        raise LembarError(PESAN_PERIODE_BAYAR)


def _periode_dasar(period_type: Any, period: Any) -> Tuple[str, str]:
    pt = str(period_type or "").strip().lower()
    if pt not in BASIS_TYPES:
        raise LembarError(PESAN_PERIODE_DASAR)
    try:
        return ip.normalize(pt, str(period or "").strip())
    except ip.PeriodeError:
        raise LembarError(PESAN_PERIODE_DASAR)


# ── Potret angka dasar ───────────────────────────────────────────────────────────────────────────────────────────────
async def _segarkan(defn: Dict[str, Any]) -> None:
    """Fakta insentif segar (sama dengan layar Capaian) sebelum dipotret/dibandingkan."""
    from services import incentive_facts as ifacts
    await ifacts.ensure_fresh(60)
    if defn.get("dasar_omzet") in ("pesanan", "lunas"):
        from services import analytics_facts
        await analytics_facts.ensure_fresh(60)


def _defn_kunci(defn: Dict[str, Any]) -> Tuple:
    return tuple(defn.get(f) for f, _k in idef.FIELDS)


async def _angka(entity_id: str, butir: Iterable[Tuple[str, str, str, Dict[str, Any]]]) -> Dict[Tuple, Dict[str, Any]]:
    """`butir` = (jenis periode, periode, sales, definisi) → {(jenis, periode, sales, kunci definisi): angka}. Satu
    pemanggilan pengumpul Capaian per (periode, definisi) untuk semua sales sekaligus."""
    grup: Dict[Tuple, Dict[str, Any]] = {}
    for pt, p, sid, defn in butir:
        g = grup.setdefault((pt, p, _defn_kunci(defn)), {"defn": defn, "sales": set()})
        g["sales"].add(sid)
    out: Dict[Tuple, Dict[str, Any]] = {}
    for (pt, p, dk), g in grup.items():
        per = await iach.resolve_period(entity_id, pt, p)
        res = await iach.angka_sales(entity_id, per, g["defn"], sorted(g["sales"]))
        for sid, v in res.items():
            out[(pt, p, sid, dk)] = {**v, "per": per}
    return out


def _sidik(docs: Dict[str, List[Dict[str, Any]]]) -> str:
    """SHA-256 dari daftar terurut `doc_id:amount` semua dokumen omzet, retur, dan uang masuk."""
    baris = sorted(f"{it['doc_id']}:{int(it['cents']) / 100:.2f}" for m in iach.METRICS for it in docs.get(m) or [])
    return hashlib.sha256("\n".join(baris).encode("utf-8")).hexdigest()


def _potret(v: Dict[str, Any], defn: Dict[str, Any], taken_at: str) -> Dict[str, Any]:
    row = v.get("row") or {}
    per = v["per"]
    snap: Dict[str, Any] = {
        "taken_at": taken_at, "definition_version": defn.get("version"),
        "definition_effective_from": defn.get("effective_from") or "",
        "definition": {f: defn.get(f) for f, _k in idef.FIELDS},
        "basis_from": per.date_from, "basis_to": per.date_to}
    for f in SNAP_FIELDS:
        if f in row:
            snap[f] = row[f]
        else:
            snap[f] = [] if f == "catatan_data" else (0 if f in MONEY_FIELDS else None)
    docs = v.get("docs") or {}
    snap["fingerprint"] = _sidik(docs)
    snap["source_counts"] = {m: len(docs.get(m) or []) for m in iach.METRICS}
    return snap


def _beda_potret(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    keys = SNAP_FIELDS + ("fingerprint", "definition_version")
    return any((a or {}).get(k) != (b or {}).get(k) for k in keys)


def _defn_potret(snap: Dict[str, Any]) -> Dict[str, Any]:
    return {"version": snap.get("definition_version"), "effective_from": snap.get("definition_effective_from"),
            **(snap.get("definition") or {})}


# ── Menyiapkan baris ─────────────────────────────────────────────────────────────────────────────────────────────────
async def _komponen(entity_id: str, component_id: Any) -> Dict[str, Any]:
    c = await db.incentive_components.find_one({"id": str(component_id or "") or "__none__", "entity_id": entity_id},
                                               {"_id": 0})
    if not c or c.get("is_active") is False:
        raise LembarError(PESAN_KOMPONEN)
    return c


async def _sales(entity_id: str, sales_id: Any) -> Dict[str, Any]:
    from services import incentive_targets as itg
    if not str(sales_id or "").strip():
        raise LembarError(PESAN_SALES_KOSONG)
    try:
        return await itg.assigned_user(str(sales_id).strip(), entity_id)   # N2: id dari klien milik PT ini
    except itg.InsentifError as exc:
        raise LembarError(str(exc))


async def _karyawan(sales_id: str) -> str:
    emp = await db.hr_employees.find_one({"user_id": sales_id}, {"_id": 0, "id": 1})
    return (emp or {}).get("id") or ""


async def _rujukan(entity_id: str, adjusts: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Baris lembar `approved`/`paid` PT yang sama yang dirujuk baris penyesuaian."""
    ref = adjusts if isinstance(adjusts, dict) else {}
    sid, lid = str(ref.get("sheet_id") or ""), str(ref.get("line_id") or "")
    if not sid or not lid:
        raise LembarError(PESAN_PENYESUAIAN)
    src = await db.incentive_sheets.find_one({"id": sid, "entity_id": entity_id, "status": {"$in": list(DISAHKAN)}},
                                             {"_id": 0, "id": 1, "number": 1, "lines": 1})
    line = next((x for x in (src or {}).get("lines") or [] if x.get("id") == lid and not x.get("is_adjustment")), None)
    if not src or not line:
        raise LembarError(PESAN_PENYESUAIAN)
    return src, line


async def _kembar_lintas(entity_id: str, lines: List[Dict[str, Any]], sheet_id: str) -> str:
    """Pesan 409 bila salah satu (sales, komponen, periode dasar) sudah ada di lembar lain yang masih berlaku."""
    for x in lines:
        if x.get("is_adjustment"):
            continue
        other = await db.incentive_sheets.find_one(
            {"entity_id": entity_id, "active_keys": _kunci(x), "id": {"$ne": sheet_id}}, {"_id": 0, "number": 1})
        if other:
            return PESAN_KEMBAR.format(sales=x.get("sales_name") or "Sales", komponen=x.get("component_name") or "",
                                       periode=x.get("basis_label") or x.get("basis_period"),
                                       nomor=other.get("number") or "")
    return ""


async def _siapkan(entity_id: str, raw: List[Dict[str, Any]], ada: List[Dict[str, Any]], *, sheet_id: str,
                   nomor: str, actor: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Periksa isian baris baru, lalu potret angka dasarnya. Tidak menulis apa pun."""
    rencana: List[Dict[str, Any]] = []
    kunci_ada = {_kunci(x): x for x in ada if not x.get("is_adjustment")}
    for p in raw:
        p = dict(p or {})
        penyesuaian = bool(p.get("is_adjustment"))
        amount = _nominal(p.get("amount"), penyesuaian)
        note = str(p.get("note") or "").strip()[:500]
        adjusts = None
        if penyesuaian:
            if not note:
                raise LembarError(PESAN_PENYESUAIAN)
            src, src_line = await _rujukan(entity_id, p.get("adjusts"))
            for f in ("sales_id", "component_id", "basis_period_type", "basis_period"):
                if p.get(f) not in (None, "") and str(p.get(f)).strip() != str(src_line.get(f)):
                    raise LembarError(PESAN_PENYESUAIAN)
                p[f] = src_line.get(f)
            adjusts = {"sheet_id": src["id"], "sheet_number": src.get("number") or "", "line_id": src_line["id"]}
        comp = await _komponen(entity_id, p.get("component_id"))
        sales = await _sales(entity_id, p.get("sales_id"))
        pt, per = _periode_dasar(p.get("basis_period_type"), p.get("basis_period"))
        if comp.get("basis_period_type") in BASIS_TYPES and comp["basis_period_type"] != pt:
            from services import incentive_targets as itg
            raise LembarError(PESAN_BASIS_KOMPONEN.format(
                komponen=comp.get("name") or comp.get("code"),
                basis=itg.COMPONENT_BASIS_LABEL.get(comp["basis_period_type"], comp["basis_period_type"]).lower()))
        line = {"id": new_id("iline"), "sales_id": sales["id"], "sales_name": sales.get("name") or "",
                "employee_id": await _karyawan(sales["id"]), "component_id": comp["id"],
                "component_code": comp.get("code") or "", "component_name": comp.get("name") or "",
                "basis_period_type": pt, "basis_period": per, "basis_label": basis_label(pt, per),
                "amount": amount, "note": note, "is_adjustment": penyesuaian, "adjusts": adjusts,
                "created_by": _siapa(actor)}
        if not penyesuaian:
            k = _kunci(line)
            if k in kunci_ada:
                raise LembarError(PESAN_KEMBAR.format(sales=line["sales_name"], komponen=line["component_name"],
                                                      periode=line["basis_label"], nomor=nomor or "ini"), 409)
            kunci_ada[k] = line
        rencana.append(line)
    msg = await _kembar_lintas(entity_id, rencana, sheet_id)
    if msg:
        raise LembarError(msg, 409)
    if not rencana:
        return []
    defn = await idef.current_definition(entity_id)
    await _segarkan(defn)
    angka = await _angka(entity_id, [(x["basis_period_type"], x["basis_period"], x["sales_id"], defn) for x in rencana])
    taken = now_iso()
    dk = _defn_kunci(defn)
    for x in rencana:
        x["snapshot"] = _potret(angka[(x["basis_period_type"], x["basis_period"], x["sales_id"], dk)], defn, taken)
        x["created_at"] = taken
    return rencana


# ── Menyimpan (bersyarat status lama + revisi) ───────────────────────────────────────────────────────────────────────
async def _simpan(doc: Dict[str, Any], dari: str, fields: Dict[str, Any], *, history: Optional[Dict[str, Any]] = None,
                  unset: Iterable[str] = ()) -> Dict[str, Any]:
    from pymongo import ReturnDocument
    from pymongo.errors import DuplicateKeyError
    upd: Dict[str, Any] = {"$set": {**fields, "updated_at": now_iso()}, "$inc": {"rev": 1}}
    if history:
        upd["$push"] = {"history": history}
    if unset:
        upd["$unset"] = {f: "" for f in unset}
    try:
        out = await db.incentive_sheets.find_one_and_update(
            {"id": doc["id"], "status": dari, "rev": int(doc.get("rev") or 0)}, upd, projection={"_id": 0},
            return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:
        msg = await _kembar_lintas(doc["entity_id"], fields.get("lines") or doc.get("lines") or [], doc["id"])
        raise LembarError(msg or PESAN_BERUBAH.format(nomor=doc.get("number") or ""), 409)
    if out is None:
        cur = await db.incentive_sheets.find_one({"id": doc["id"]}, {"_id": 0, "status": 1, "number": 1}) or {}
        if cur.get("status") == "approving":   # KM-T4 — pengesahan lain sedang berjalan
            raise LembarError(f"Lembar {doc.get('number') or ''} sedang diproses. Muat ulang.", 409)
        if cur.get("status") and cur.get("status") != dari:
            raise LembarError(_pesan_status(cur), 409)
        raise LembarError(PESAN_BERUBAH.format(nomor=doc.get("number") or ""), 409)
    return out


async def _baris_baru(doc: Dict[str, Any], lines: List[Dict[str, Any]],
                      history: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return await _simpan(doc, "draft", {"lines": lines, "active_keys": _active_keys(lines), "totals": _totals(lines)},
                         history=history)


# ── Baca ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
def sheet_out(doc: Dict[str, Any], margin_ok: bool, *, snapshot: bool = True) -> Dict[str, Any]:
    """Lembar untuk jawaban: label status; potret tanpa `margin_pct` bagi yang tidak memegang `incentive.view_margin`;
    daftar (`snapshot=False`) tanpa potret dan tanpa riwayat."""
    d = safe_doc({k: v for k, v in (doc or {}).items() if k != "_id"})
    d["status_label"] = status_label(d.get("status"))
    lines = []
    for x in d.get("lines") or []:
        x = dict(x)
        if not snapshot:
            x.pop("snapshot", None)
        elif isinstance(x.get("snapshot"), dict) and not margin_ok:
            x["snapshot"] = {k: v for k, v in x["snapshot"].items() if k != "margin_pct"}
        lines.append(x)
    d["lines"] = lines
    if not snapshot:
        d.pop("history", None)
    d["margin_visible"] = bool(margin_ok)
    return d


async def list_sheets(query: Dict[str, Any], *, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
    page = max(1, int(page or 1))
    size = max(1, min(100, int(page_size or 25)))
    total = await db.incentive_sheets.count_documents(query)
    rows = await db.incentive_sheets.find(query, {"_id": 0, "history": 0}).sort(
        [("created_at", -1), ("number", -1)]).skip((page - 1) * size).limit(size).to_list(size)
    return {"items": [sheet_out(r, False, snapshot=False) for r in rows], "total": total, "page": page,
            "page_size": size}


async def get_sheet(sheet_id: str) -> Optional[Dict[str, Any]]:
    return await db.incentive_sheets.find_one({"id": sheet_id}, {"_id": 0})


def _selisih(field: str, snap: Any, cur: Any) -> Any:
    if snap is None or cur is None:
        return None
    if field.endswith("_pct"):
        return round(float(cur) - float(snap), 1)
    return int(cur) - int(snap)


async def drift(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per baris: angka dasar yang KINI berbeda dari potret (dihitung dengan definisi yang dipotret baris itu, jadi
    yang terlihat adalah perubahan data sumber, bukan perubahan definisi). Lembar dibatalkan → kosong."""
    lines = [x for x in doc.get("lines") or [] if isinstance(x.get("snapshot"), dict)]
    if doc.get("status") == "cancelled" or not lines:
        return []
    defs = {}
    for x in lines:
        d = _defn_potret(x["snapshot"])
        defs[_defn_kunci(d)] = d
    for d in defs.values():
        await _segarkan(d)
    angka = await _angka(doc["entity_id"], [(x["basis_period_type"], x["basis_period"], x["sales_id"],
                                             _defn_potret(x["snapshot"])) for x in lines])
    out: List[Dict[str, Any]] = []
    for x in lines:
        snap = x["snapshot"]
        v = angka[(x["basis_period_type"], x["basis_period"], x["sales_id"], _defn_kunci(_defn_potret(snap)))]
        row = v.get("row") or {}
        for f, label in DRIFT_FIELDS.items():
            cur = row.get(f, 0 if f in MONEY_FIELDS else None)
            if cur != snap.get(f):
                out.append({"line_id": x["id"], "field": f, "label": label, "snapshot": snap.get(f), "current": cur,
                            "diff": _selisih(f, snap.get(f), cur)})
    return out


async def adjustable_lines(entity_id: str, sales_id: str) -> Dict[str, Any]:
    """Baris lembar `approved`/`paid` sales itu di PT ini — rujukan baris penyesuaian."""
    items: List[Dict[str, Any]] = []
    cur = db.incentive_sheets.find({"entity_id": entity_id, "status": {"$in": list(DISAHKAN)},
                                    "lines.sales_id": sales_id},
                                   {"_id": 0, "id": 1, "number": 1, "status": 1, "pay_period": 1, "lines": 1}
                                   ).sort("created_at", -1).limit(200)
    async for s in cur:
        for x in s.get("lines") or []:
            if x.get("sales_id") != sales_id or x.get("is_adjustment"):
                continue
            items.append({"sheet_id": s["id"], "sheet_number": s.get("number") or "", "sheet_status": s.get("status"),
                          "sheet_status_label": status_label(s.get("status")), "pay_period": s.get("pay_period"),
                          "line_id": x["id"], "sales_id": x.get("sales_id"), "sales_name": x.get("sales_name"),
                          "component_id": x.get("component_id"), "component_name": x.get("component_name"),
                          "basis_period_type": x.get("basis_period_type"), "basis_period": x.get("basis_period"),
                          "basis_label": x.get("basis_label"), "amount": x.get("amount")})
    return {"items": items}


# ── Tulis: buat & baris ──────────────────────────────────────────────────────────────────────────────────────────────
async def create_sheet(entity_id: str, payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Lembar `draft` baru (PT = PT konteks, N1); baris opsional langsung dipotret. Nomor `LIN-` per PT."""
    from pymongo.errors import DuplicateKeyError
    pay = _periode_bayar(payload.get("pay_period"))
    title = str(payload.get("title") or "").strip()[:120]
    raw = list(payload.get("lines") or [])
    if len(raw) > MAX_BARIS:
        raise LembarError(PESAN_BARIS_PENUH)
    lines = await _siapkan(entity_id, raw, [], sheet_id="", nomor="", actor=actor)
    number = await next_doc_number("incentive_sheets", "number", "LIN-", entity_id=entity_id)
    now = now_iso()
    doc = {"id": new_id("isheet"), "number": number, "entity_id": entity_id, "pay_period": pay, "title": title,
           "status": "draft", "lines": lines, "active_keys": _active_keys(lines), "totals": _totals(lines),
           "prepared_by": _siapa(actor), "created_at": now, "updated_at": now, "rev": 0,
           "history": [_riwayat("create", actor, now, "", "", "draft")]}
    try:
        await db.incentive_sheets.insert_one(dict(doc))
    except DuplicateKeyError:
        msg = await _kembar_lintas(entity_id, lines, doc["id"])
        raise LembarError(msg or PESAN_BERUBAH.format(nomor=number), 409)
    return doc


async def add_line(doc: Dict[str, Any], payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    _harus_status(doc, "draft")
    if len(doc.get("lines") or []) >= MAX_BARIS:
        raise LembarError(PESAN_BARIS_PENUH)
    baru = await _siapkan(doc["entity_id"], [payload], doc.get("lines") or [], sheet_id=doc["id"],
                          nomor=doc.get("number") or "", actor=actor)
    return await _baris_baru(doc, list(doc.get("lines") or []) + baru)


async def patch_line(doc: Dict[str, Any], line_id: str, payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    _harus_status(doc, "draft")
    lines = [dict(x) for x in doc.get("lines") or []]
    ln = next((x for x in lines if x.get("id") == line_id), None)
    if ln is None:
        raise LembarError(PESAN_BARIS, 404)
    if "amount" in payload:
        ln["amount"] = _nominal(payload.get("amount"), bool(ln.get("is_adjustment")))
    if "note" in payload:
        ln["note"] = str(payload.get("note") or "").strip()[:500]
    ln["updated_by"] = _siapa(actor)
    ln["updated_at"] = now_iso()
    return await _baris_baru(doc, lines)


async def delete_line(doc: Dict[str, Any], line_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    _harus_status(doc, "draft")
    lines = [x for x in doc.get("lines") or [] if x.get("id") != line_id]
    if len(lines) == len(doc.get("lines") or []):
        raise LembarError(PESAN_BARIS, 404)
    return await _baris_baru(doc, lines)


async def refresh_sheet(doc: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Potret semua baris diambil ulang (versi definisi berlaku sekarang). Jawaban `{changed: [line_id], sheet}`."""
    _harus_status(doc, "draft")
    eid = doc["entity_id"]
    lines = [dict(x) for x in doc.get("lines") or []]
    if not lines:
        return {"changed": [], "sheet": doc}
    defn = await idef.current_definition(eid)
    await _segarkan(defn)
    angka = await _angka(eid, [(x["basis_period_type"], x["basis_period"], x["sales_id"], defn) for x in lines])
    taken = now_iso()
    dk = _defn_kunci(defn)
    changed: List[str] = []
    for x in lines:
        snap = _potret(angka[(x["basis_period_type"], x["basis_period"], x["sales_id"], dk)], defn, taken)
        if _beda_potret(x.get("snapshot") or {}, snap):
            changed.append(x["id"])
        x["snapshot"] = snap
        x["employee_id"] = await _karyawan(x["sales_id"]) or x.get("employee_id") or ""
    now = now_iso()
    out = await _simpan(doc, "draft", {"lines": lines}, history=_riwayat(
        "refresh", actor, now, f"{len(changed)} baris berubah" if changed else "Tidak ada angka yang berubah",
        "draft", "draft"))
    return {"changed": changed, "sheet": out}


# ── Tulis: transisi status ───────────────────────────────────────────────────────────────────────────────────────────
async def submit_sheet(doc: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    _harus_status(doc, "draft")
    lines = doc.get("lines") or []
    if not lines:
        raise LembarError(PESAN_TANPA_BARIS)
    if any(x.get("amount") is None for x in lines):
        raise LembarError(PESAN_NOMINAL_KOSONG)
    if any(x.get("is_adjustment") and not str(x.get("note") or "").strip() for x in lines):
        raise LembarError(PESAN_PENYESUAIAN)
    now = now_iso()
    return await _simpan(doc, "draft", {"status": "submitted", "submitted_by": _siapa(actor), "submitted_at": now},
                         history=_riwayat("submit", actor, now, "", "draft", "submitted"))


async def approve_sheet(doc: Dict[str, Any], corrections: Optional[List[Dict[str, Any]]],
                        actor: Dict[str, Any]) -> Dict[str, Any]:
    """Sahkan lembar `submitted`; pemutus boleh mengoreksi nominal (wajib catatan; nominal penyiap disimpan di
    `amount_prepared`). Kontrol dua orang `kontrol.lembar_insentif.*` (K-25) dinilai atas nominal terbesar antara
    sebelum dan sesudah koreksi, supaya koreksi tidak bisa dipakai untuk turun di bawah batas nominal."""
    from services import approval_policy_service as aps
    from services import dual_control as dc
    from services import incentive_payroll as ipay
    if (doc or {}).get("status") == "approving":   # KM-T4 — pengesahan yang berhenti di tengah diteruskan
        return await ipay.lanjutkan(doc, actor)
    _harus_status(doc, "submitted")
    lines = [dict(x) for x in doc.get("lines") or []]
    by_id = {x["id"]: x for x in lines}
    sebelum = _totals(lines)["amount"]
    catatan: List[str] = []
    for c in corrections or []:
        c = dict(c or {})
        ln = by_id.get(str(c.get("line_id") or ""))
        if ln is None:
            raise LembarError(PESAN_BARIS)
        note = str(c.get("note") or "").strip()
        if not note:
            raise LembarError(PESAN_KOREKSI)
        amt = _nominal(c.get("amount"), bool(ln.get("is_adjustment")))
        if amt is None:
            raise LembarError(PESAN_NOMINAL)
        if "amount_prepared" not in ln:
            ln["amount_prepared"] = ln.get("amount")
        ln["amount"] = amt
        ln["approver_note"] = note[:500]
        catatan.append(f"{ln.get('sales_name') or 'Sales'} {ln.get('component_name') or ''} "
                       f"{rupiah(ln['amount_prepared'] or 0)} → {rupiah(amt)}: {note[:120]}")
    totals = _totals(lines)
    nominal = max(sebelum, totals["amount"])
    # literal nama aksi (bukan konstanta): dikenali `config_health` & uji titik pasang KF-T6 (U15)
    await dc.tolak_bila_pelaku_sama("lembar_insentif", doc, actor, doc["entity_id"], nominal=float(nominal),
                                    pengaju=[(doc.get("submitted_by") or {}).get("id") or ""])
    await aps.guard_door(JENIS_PERSETUJUAN, actor, doc=doc, amount=float(totals["amount"]))
    # KM-T4 — sakelar PT lembar: `sheet` → jurnal + masukan gaji (PERIKSA dulu, tanpa tulisan); lainnya → keputusan saja.
    if ipay.lembar_ke_gaji(await ipay.mode_pt(doc["entity_id"])):
        rencana = await ipay.periksa(doc, lines)
        return await ipay.sahkan_tertaut(doc, lines, totals, rencana, "; ".join(catatan), actor)
    now = now_iso()
    return await _simpan(doc, "submitted", {"status": "approved", "approved_by": _siapa(actor), "approved_at": now,
                                            "lines": lines, "totals": totals, "payroll_linked": False,
                                            "gl_status": "not_required"},
                         history=_riwayat("approve", actor, now, "; ".join(catatan), "submitted", "approved"))


async def return_sheet(doc: Dict[str, Any], reason: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    r = _alasan(reason)
    _harus_status(doc, "submitted")
    now = now_iso()
    return await _simpan(doc, "submitted", {"status": "draft", "returned_by": _siapa(actor), "returned_at": now,
                                            "return_reason": r},
                         history=_riwayat("return", actor, now, r, "submitted", "draft"),
                         unset=("submitted_by", "submitted_at"))


async def cancel_sheet(doc: Dict[str, Any], reason: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    r = _alasan(reason)
    _harus_status(doc, "draft")
    now = now_iso()
    return await _simpan(doc, "draft", {"status": "cancelled", "active_keys": [], "cancelled_by": _siapa(actor),
                                        "cancelled_at": now, "cancel_reason": r},
                         history=_riwayat("cancel", actor, now, r, "draft", "cancelled"))


# ── Ekspor Excel ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _pct_teks(v: Any) -> Any:
    return None if v is None else float(v)



async def export_xlsx(doc: Dict[str, Any], margin_ok: bool) -> Tuple[bytes, str]:
    """`.xlsx` dua lembar: "Lembar" (kolom layar + total) dan "Potret" (seluruh angka potret per baris)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from services.analytics_time import now_wib
    cell = iach._cell
    ent = await db.business_entities.find_one({"id": doc.get("entity_id")}, {"_id": 0, "legal_name": 1,
                                                                            "short_name": 1}) or {}
    pt = ent.get("legal_name") or ent.get("short_name") or doc.get("entity_id") or ""
    bold = Font(bold=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Lembar"
    for label, val in (("Lembar insentif", doc.get("number") or ""), ("PT", pt),
                       ("Periode bayar", ip.period_label("month", doc.get("pay_period") or "2000-01")),
                       ("Judul", doc.get("title") or "—"), ("Status", status_label(doc.get("status"))),
                       ("Penyiap", (doc.get("prepared_by") or {}).get("name") or "—"),
                       ("Pemutus", (doc.get("approved_by") or {}).get("name") or "—"),
                       ("Diekspor", now_wib().strftime("%d-%m-%Y %H:%M") + " WIB")):
        ws.append([label, cell(val)])
        ws.cell(row=ws.max_row, column=1).font = bold
    ws.append([])
    head = ["Sales", "Komponen", "Periode dasar", "Omzet", "Target omzet", "Uang masuk", "Target pencairan",
            "Realisasi harga (%)", "Nominal", "Catatan", "Penyesuaian atas"]
    ws.append(head)
    for c in ws[ws.max_row]:
        c.font = bold
    for x in doc.get("lines") or []:
        s = x.get("snapshot") or {}
        ws.append([cell(x.get("sales_name") or ""), cell(x.get("component_name") or ""), cell(x.get("basis_label") or ""),
                   s.get("omzet_bersih"), s.get("target_sales"), s.get("uang_masuk"), s.get("target_collection"),
                   _pct_teks(s.get("realisasi_harga_pct")), x.get("amount"), cell(x.get("note") or ""),
                   cell((x.get("adjusts") or {}).get("sheet_number") or "")])
    t = doc.get("totals") or _totals(doc.get("lines") or [])
    ws.append(["Total", f"{t.get('lines', 0)} baris", None, None, None, None, None, None, t.get("amount", 0)])
    for c in ws[ws.max_row]:
        c.font = bold
    for col, w in (("A", 28), ("B", 26), ("C", 18), ("J", 40)):
        ws.column_dimensions[col].width = w

    ws2 = wb.create_sheet("Potret")
    cols = [("Sales", "sales_name"), ("Komponen", "component_name"), ("Periode dasar", "basis_label"),
            ("Dipotret (WIB)", "taken_at"), ("Versi definisi", "definition_version"),
            ("Dasar omzet", "dasar_omzet"), ("Isi pencairan", "isi_pencairan"), ("Pemilik angka", "pemilik_angka"),
            ("Harga acuan", "harga_acuan"), ("Dari tanggal", "basis_from"), ("Sampai tanggal", "basis_to"),
            ("Target omzet", "target_sales"), ("Omzet", "omzet"), ("Retur", "retur"), ("Omzet bersih", "omzet_bersih"),
            ("% capaian omzet", "pct_omzet"), ("Target pencairan", "target_collection"), ("Uang masuk", "uang_masuk"),
            ("% capaian pencairan", "pct_pencairan"), ("Realisasi harga (%)", "realisasi_harga_pct"),
            ("Di bawah harga acuan (%)", "porsi_bawah_acuan_pct")]
    if margin_ok:
        cols.append(("Margin (%)", "margin_pct"))
    cols += [("Catatan data", "catatan_data"), ("Dokumen omzet", "n_omzet"), ("Dokumen retur", "n_retur"),
             ("Dokumen uang masuk", "n_uang_masuk"), ("Sidik dokumen", "fingerprint")]
    ws2.append([h for h, _f in cols])
    for c in ws2[1]:
        c.font = bold
    for x in doc.get("lines") or []:
        s = x.get("snapshot") or {}
        # label pilihan definisi (bukan kode mentah), mis. "terkirim" → label Pusat Pengaturan
        d = {it["field"]: it["value_label"] for it in idef.labels(s.get("definition") or {})}
        n = s.get("source_counts") or {}
        vals = {"sales_name": x.get("sales_name"), "component_name": x.get("component_name"),
                "basis_label": x.get("basis_label"), **d, **s,
                "taken_at": _jam_wib(s.get("taken_at")) if s.get("taken_at") else "",
                "catatan_data": "; ".join(c.get("text") or "" for c in s.get("catatan_data") or []),
                "n_omzet": n.get("omzet"), "n_retur": n.get("retur"), "n_uang_masuk": n.get("uang_masuk")}
        ws2.append([cell(vals.get(f)) if isinstance(vals.get(f), str) else vals.get(f) for _h, f in cols])
    buf = io.BytesIO()
    wb.save(buf)
    nama = str(doc.get("number") or doc.get("id")).replace("/", "-").replace(" ", "-")
    return buf.getvalue(), f"lembar-insentif-{nama}.xlsx"


def _jam_wib(iso: str) -> str:
    from datetime import datetime, timedelta, timezone
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return str(iso)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return (d.astimezone(timezone(timedelta(hours=7)))).strftime("%d-%m-%Y %H:%M")
