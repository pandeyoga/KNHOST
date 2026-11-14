"""EPIC 7 — Pusat Pajak (PPN + PPh) service.

Agregasi pajak read-mostly, ENTITY-AWARE & CONFIGURABLE:
- PPN (SPT Masa): reuse `input_tax_service.vat_summary` (Keluaran − Masukan → posisi
  kurang/lebih bayar). Hanya bermakna utk entitas PKP (default_tax_mode='ppn').
- PPh: butir configurable dari `settings.tax.pph_items` (config_service). Tiap butir
  punya `basis`:
    * payroll → otomatis dari `hr_payroll_runs.totals.pph21` (periode+entitas)
    * omzet   → rate% × peredaran bruto (sales_orders periode+entitas)
    * manual  → rate% × DPP yang direkam user (`tax_pph_records`)

Aturan emas: PKP/non-PKP mengikuti konfigurasi ENTITAS (business_entities.default_tax_mode),
di-resolve via config_service.get_effective_settings (sudah men-set tax.is_pkp & ppn_rate=0
utk non-PKP). PPh berlaku lintas PKP/non-PKP (PPh ≠ PPN).
"""
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import now_iso, new_id
from services.config_service import get_effective_settings
from services import input_tax_service

PPH_RECORDS = "tax_pph_records"
# PK-40 (FY-16) — rekap PPh 21 hanya memuat penggajian yang SUDAH terjurnal (dulu ikut `approved`).
_PAYROLL_STATUSES = ["posted", "paid"]
_ACTIVE_SO_EXCLUDE = {"cancelled", "draft", "rejected"}


def _cur_month() -> str:
    from services.book_date import periode_buku   # PK-37 — bulan berjalan WIB (dulu bulan UTC)
    return periode_buku()


def _ent_q(entity_id: Any) -> Dict[str, Any]:
    """PK-09 — daftar PT (gabungan PT yang ditugaskan) → `$in`; satu PT → sama dengan; kosong/`all` → tanpa saringan
    (hanya untuk pemanggil internal; router selalu mengirim daftar)."""
    if isinstance(entity_id, (list, tuple, set)):
        return {"entity_id": {"$in": list(entity_id)}}
    return {"entity_id": entity_id} if entity_id and entity_id != "all" else {}


def _scope(entity_id: Optional[str], entity_ids: Optional[List[str]]) -> Any:
    if entity_ids is not None and (not entity_id or entity_id == "all"):
        return list(entity_ids)
    return entity_id


async def list_periods(entity_id: Optional[str]) -> List[str]:
    """Union periode dari faktur keluaran/masukan, payroll, rekam PPh, + bulan berjalan."""
    eq = _ent_q(entity_id)
    out_dates = await db.tax_invoices.distinct("faktur_date", eq)
    in_dates = await db.tax_invoices_in.distinct("faktur_date", eq)
    pay_periods = await db.hr_payroll_runs.distinct("period", eq)
    pph_periods = await db.tax_pph_records.distinct("period", eq)
    # PK-40 — masa faktur = periode WIB (`period_of`), sama dengan saringan rekap PPN (dulu 7 huruf pertama = bulan UTC).
    months = {input_tax_service.period_of(d) for d in list(out_dates) + list(in_dates) if d}
    months |= {p for p in pay_periods if p} | {p for p in pph_periods if p}
    months.add(_cur_month())
    return sorted({m for m in months if m}, reverse=True)


async def _period_pph21(entity_id: Optional[str], period: str) -> Dict[str, float]:
    """PK-40 (FY-16) — PPh 21 masa itu dari penggajian TERJURNAL (`posted`/`paid`), dasar sama dengan slip gaji.

    `dpp` = Σ `tax_gross` slip (bruto + JKK + JKM + kesehatan tanggungan perusahaan; slip lama tanpa `tax_gross` →
    `gross`); `amount` = Σ `pph21` slip; `gl_amount` = kredit − debit akun hutang PPh 21 pada jurnal `payroll_run`
    ber-`source_id` `{entity_id}:{period}`; `selisih` = `amount − gl_amount`; `count` = jumlah penggajian.
    """
    from services.gl_service import ACC_HUTANG_PPH21
    q = {**_ent_q(entity_id), "period": period, "status": {"$in": _PAYROLL_STATUSES}}
    runs = [r async for r in db.hr_payroll_runs.find(q, {"_id": 0, "id": 1, "entity_id": 1})]
    dpp = pph = 0.0
    if runs:
        async for s in db.hr_payslips.find({"run_id": {"$in": [r["id"] for r in runs]}},
                                           {"_id": 0, "tax_gross": 1, "gross": 1, "pph21": 1}):
            dasar = s.get("tax_gross")
            dpp += float((s.get("gross") if dasar is None else dasar) or 0)
            pph += float(s.get("pph21") or 0)
    gl_amount = 0.0
    src = sorted({f"{r.get('entity_id')}:{period}" for r in runs})
    if src:
        async for je in db.journal_entries.find(
                {"source_type": "payroll_run", "source_id": {"$in": src}, "status": {"$ne": "void"}},
                {"_id": 0, "lines": 1}):
            for ln in je.get("lines") or []:
                if ln.get("account_code") == ACC_HUTANG_PPH21:
                    gl_amount += float(ln.get("credit") or 0) - float(ln.get("debit") or 0)
    amount = round(pph, 2)
    gl_amount = round(gl_amount, 2)
    return {"dpp": round(dpp, 2), "amount": amount, "gl_amount": gl_amount,
            "selisih": round(amount - gl_amount, 2), "count": len(runs)}


async def _period_omzet(entity_id: Optional[str], period: str) -> float:
    """Peredaran bruto (omzet) periode dari sales_orders (net_subtotal, fallback total)."""
    q = _ent_q(entity_id)
    total = 0.0
    async for so in db.sales_orders.find(
        q, {"_id": 0, "net_subtotal": 1, "total_amount": 1, "grand_total": 1,
            "created_at": 1, "order_date": 1, "status": 1}):
        d = (so.get("order_date") or so.get("created_at") or "")[:7]
        if d != period:
            continue
        if (so.get("status") or "") in _ACTIVE_SO_EXCLUDE:
            continue
        total += float(so.get("net_subtotal") or so.get("total_amount") or so.get("grand_total") or 0)
    return round(total, 2)


async def _pph_records(entity_id: Optional[str], period: str) -> Dict[str, Dict[str, Any]]:
    q = {**_ent_q(entity_id), "period": period}
    rows = await db.tax_pph_records.find(q, {"_id": 0}).to_list(2000)
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        code = r.get("code") or ""
        acc = out.setdefault(code, {"dpp": 0.0, "records": []})
        acc["dpp"] = round(acc["dpp"] + float(r.get("dpp") or 0), 2)
        acc["records"].append(r)
    return out


async def compute_pph(entity_id: Optional[str], period: str,
                      pph_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Hitung tiap butir PPh enabled sesuai basis. Return {items, total}."""
    records = await _pph_records(entity_id, period)
    items: List[Dict[str, Any]] = []
    total = 0.0
    for cfg in pph_items or []:
        if not cfg.get("enabled", True):
            continue
        code = cfg.get("code") or ""
        basis = (cfg.get("basis") or "manual").lower()
        rate = float(cfg.get("rate") or 0)
        dpp = 0.0
        amount = 0.0
        source = ""
        extra: Dict[str, Any] = {}
        if basis == "payroll":
            p21 = await _period_pph21(entity_id, period)
            dpp, amount = p21["dpp"], p21["amount"]
            # PK-40 (FY-16) — pembanding buku besar + jumlah penggajian ikut di butir PPh 21.
            extra = {"gl_amount": p21["gl_amount"], "selisih": p21["selisih"], "count": p21["count"]}
            source = f"{p21['count']} penggajian terjurnal · dasar = penghasilan bruto kena pajak slip"
        elif basis == "omzet":
            dpp = await _period_omzet(entity_id, period)
            amount = round(dpp * rate / 100.0, 2)
            source = "Peredaran bruto (sales orders)"
        else:  # manual
            rec = records.get(code, {"dpp": 0.0, "records": []})
            dpp = round(float(rec["dpp"]), 2)
            amount = round(dpp * rate / 100.0, 2)
            source = f"{len(rec.get('records', []))} rekaman manual"
        total += amount
        items.append({
            "code": code, "name": cfg.get("name") or code,
            "basis": basis, "rate": rate,
            "dpp": round(dpp, 2), "amount": round(amount, 2),
            "source": source, "editable": basis == "manual", **extra,
        })
    return {"items": items, "total": round(total, 2)}


async def tax_summary(entity_id: Optional[str], period: Optional[str],
                      entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    scope = _scope(entity_id, entity_ids)   # PK-09 — gabungan = PT yang ditugaskan, bukan seluruh grup
    periods = await list_periods(scope)
    sel = period if (period and period in periods) else (periods[0] if periods else _cur_month())

    settings = await get_effective_settings(entity_id)
    tax_cfg = settings.get("tax", {}) or {}
    is_pkp = bool(tax_cfg.get("is_pkp", True))

    # Entity meta
    entity_meta: Dict[str, Any] = {"id": entity_id or "all", "name": "Semua Entitas",
                                   "npwp": "", "tax_mode": "ppn" if is_pkp else "non_ppn",
                                   "is_pkp": is_pkp}
    if entity_id and entity_id != "all":
        ent = await db.business_entities.find_one({"id": entity_id}, {"_id": 0})
        if ent:
            entity_meta = {
                "id": ent.get("id"), "name": ent.get("legal_name") or ent.get("short_name") or ent.get("id"),
                "npwp": ent.get("npwp", ""), "tax_mode": ent.get("default_tax_mode", "non_ppn"),
                "is_pkp": ent.get("default_tax_mode") == "ppn",
            }
            is_pkp = entity_meta["is_pkp"]

    # PPN (SPT Masa) — hanya bermakna utk PKP
    ppn = await input_tax_service.vat_summary(period=sel, entity_id=entity_id or "",
                                              entity_ids=scope if isinstance(scope, list) else None)
    ppn["applicable"] = is_pkp

    # PPh — configurable
    pph = await compute_pph(scope, sel, tax_cfg.get("pph_items", []))

    return {
        "period": sel,
        "periods": periods,
        "entity": entity_meta,
        "config": {
            "ppn_rate": float(tax_cfg.get("ppn_rate", 0) or 0),
            "ppn_mode": tax_cfg.get("ppn_mode", "excluded"),
            # KF-T3 (KF-11) — e-Faktur mengikuti status PKP di profil PT; `tax.efaktur_enabled` tidak dipakai (not_used).
            "efaktur_enabled": is_pkp,
            "is_pkp": is_pkp,
            "pph_items": tax_cfg.get("pph_items", []),
        },
        "ppn": ppn,
        "pph": pph,
    }


# ── PK-40 (SL-13) — masa pajak dilaporkan / terkunci ─────────────────────────────────────────────────────────────
# Satu dokumen `tax_period_locks` per (PT, masa) — indeks unik wajib `uq_tax_period`. `status` = `reported` (terkunci)
# | `reopened` (dibuka lagi; kejadian laporan lama di `history[]`). Tanpa dokumen = perilaku lama (bebas diubah).
LOCKS = "tax_period_locks"
_MASA = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
PESAN_MASA_TERKUNCI = ("Masa pajak {bulan} {pt} sudah ditandai dilaporkan, jadi {aksi} tidak bisa dilakukan. "
                       "Buka dulu masa pajaknya di Pusat Pajak.")


class TaxPeriodLocked(HTTPException):
    """Aksi pada masa pajak yang sudah ditandai dilaporkan → 409 (dilempar di langkah PERIKSA, sebelum tulisan)."""

    def __init__(self, pesan: str):
        super().__init__(status_code=409, detail=pesan)


def bulan_tahun(period: str) -> str:
    """`2026-10` → "Oktober 2026"."""
    from services.book_date import _BULAN
    return f"{_BULAN[int(period[5:7])]} {period[:4]}"


def masa_dari(tanggal: Any) -> str:
    """Masa pajak `YYYY-MM` dari tanggal/stempel (WIB, `periode_buku`) atau dari teks masa `YYYY-MM` apa adanya."""
    from services.book_date import periode_buku
    if isinstance(tanggal, str) and _MASA.match(tanggal.strip()):
        return tanggal.strip()
    return periode_buku(tanggal)


async def _nama_pt(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "legal_name": 1, "short_name": 1,
                                                                "name": 1}) or {}
    return e.get("legal_name") or e.get("short_name") or e.get("name") or entity_id


async def assert_masa_terbuka(entity_id: Optional[str], tanggal: Any, *, aksi: str) -> None:
    """Langkah PERIKSA: masa pajak `tanggal` untuk PT itu sudah ditandai dilaporkan → `TaxPeriodLocked` (409).

    `tanggal` kosong = hari ini (WIB); teks `YYYY-MM` = masa itu sendiri (rekaman PPh). `aksi` = teks Indonesia aksi.
    """
    from core_utils import DEFAULT_ENTITY_ID
    eid = entity_id or DEFAULT_ENTITY_ID
    try:
        period = masa_dari(tanggal)
    except ValueError:   # tanggal tak dikenal: perilaku lama (7 huruf pertama), tidak menebak masa lain
        period = str(tanggal)[:7]
    if await db[LOCKS].find_one({"entity_id": eid, "period": period, "status": "reported"}, {"_id": 0, "id": 1}):
        raise TaxPeriodLocked(PESAN_MASA_TERKUNCI.format(bulan=bulan_tahun(period), pt=await _nama_pt(eid),
                                                         aksi=aksi))


async def list_period_locks(entity_ids: List[str]) -> List[Dict[str, Any]]:
    """Daftar masa (sama dengan pemilih masa Pusat Pajak) + keadaan dilaporkan. Beberapa PT: `locked` = semua PT
    dalam cakupan sudah ditandai; rincian per PT di `entities`."""
    ids = list(entity_ids)
    periods = await list_periods(ids[0] if len(ids) == 1 else ids)
    locks: Dict[tuple, Dict[str, Any]] = {}
    async for d in db[LOCKS].find({"entity_id": {"$in": ids}}, {"_id": 0}):
        locks[(d.get("entity_id"), d.get("period"))] = d
    out: List[Dict[str, Any]] = []
    for p in periods:
        per_pt = []
        for eid in ids:
            d = locks.get((eid, p)) or {}
            per_pt.append({"entity_id": eid, "locked": d.get("status") == "reported", "status": d.get("status", ""),
                           "reported_at": d.get("reported_at", ""), "reported_by": d.get("reported_by", ""),
                           "note": d.get("note", ""), "reopened_at": d.get("reopened_at", ""),
                           "reopened_by": d.get("reopened_by", ""), "snapshot": d.get("snapshot")})
        row = dict(per_pt[0]) if len(per_pt) == 1 else {
            "locked": bool(per_pt) and all(x["locked"] for x in per_pt), "status": "", "reported_at": "",
            "reported_by": "", "note": "", "reopened_at": "", "reopened_by": "", "snapshot": None}
        row.pop("entity_id", None)
        out.append({"period": p, **row, "entities": per_pt})
    return out


async def _potret_masa(entity_id: str, period: str) -> Dict[str, float]:
    """Angka rekap saat masa ditandai dilaporkan (D3 — potret disimpan, tidak dihitung ulang)."""
    ppn = await input_tax_service.vat_summary(period=period, entity_id=entity_id)
    tax_cfg = (await get_effective_settings(entity_id)).get("tax", {}) or {}
    pph = await compute_pph(entity_id, period, tax_cfg.get("pph_items", []))
    return {"keluaran_ppn": ppn["keluaran"]["ppn"], "masukan_ppn": ppn["masukan"]["ppn"], "net_ppn": ppn["net_ppn"],
            "pph_total": pph["total"], "gl_keluaran_ppn": ppn["keluaran"]["gl_ppn"],
            "gl_masukan_ppn": ppn["masukan"]["gl_ppn"]}


def _periksa_teks_masa(period: str) -> str:
    p = (period or "").strip()
    if not _MASA.match(p):
        raise HTTPException(status_code=400, detail="Masa pajak harus berbentuk TTTT-BB, mis. 2026-10.")
    return p


async def lock_period(entity_id: str, period: str, note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Tandai masa pajak PT itu sudah dilaporkan (terkunci) + simpan potret angka rekap saat itu."""
    from pymongo import ReturnDocument
    from pymongo.errors import DuplicateKeyError
    from services.book_date import periode_buku, tanggal_panjang
    period = _periksa_teks_masa(period)
    if period >= periode_buku():
        raise HTTPException(status_code=400, detail=(f"Masa pajak {bulan_tahun(period)} belum berakhir, belum bisa "
                                                     "ditandai dilaporkan."))

    async def _sudah(d: Dict[str, Any]) -> HTTPException:
        return HTTPException(status_code=409, detail=(
            f"Masa pajak {bulan_tahun(period)} sudah ditandai dilaporkan oleh {d.get('reported_by') or '-'} pada "
            f"{tanggal_panjang(d.get('reported_at') or None)}."))

    ada = await db[LOCKS].find_one({"entity_id": entity_id, "period": period}, {"_id": 0})
    if ada and ada.get("status") == "reported":
        raise await _sudah(ada)
    snapshot = await _potret_masa(entity_id, period)
    now = now_iso()
    try:
        doc = await db[LOCKS].find_one_and_update(
            {"entity_id": entity_id, "period": period, "status": {"$ne": "reported"}},
            {"$set": {"status": "reported", "reported_at": now, "reported_by": actor.get("name", ""),
                      "reported_by_id": actor.get("id", ""), "note": (note or "").strip(), "snapshot": snapshot,
                      "reopened_at": "", "reopened_by": "", "reopen_reason": "", "updated_at": now},
             "$setOnInsert": {"id": new_id("tpl"), "history": [], "created_at": now}},
            upsert=True, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:   # kunci bersamaan: yang kalah melihat dokumen pemenang (indeks unik `uq_tax_period`)
        raise await _sudah(await db[LOCKS].find_one({"entity_id": entity_id, "period": period}, {"_id": 0}) or {})
    # `upsert` + saringan status: sebagian pengemudi tidak mengembalikan dokumen sesudah ubah → baca ulang.
    return doc or await db[LOCKS].find_one({"entity_id": entity_id, "period": period}, {"_id": 0})


async def unlock_period(entity_id: str, period: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Buka lagi masa pajak yang sudah ditandai dilaporkan (alasan wajib). Kejadian laporan lama → `history[]`."""
    from pymongo import ReturnDocument
    from input_rules import count_letters
    period = _periksa_teks_masa(period)
    reason = (reason or "").strip()
    if count_letters(reason) < 5:
        raise HTTPException(status_code=400, detail="Alasan membuka masa pajak wajib diisi (minimal 5 huruf).")
    ada = await db[LOCKS].find_one({"entity_id": entity_id, "period": period, "status": "reported"}, {"_id": 0})
    if not ada:
        raise HTTPException(status_code=409,
                            detail=f"Masa pajak {bulan_tahun(period)} belum ditandai dilaporkan, jadi tidak perlu dibuka.")
    now = now_iso()
    kejadian = {k: ada.get(k) for k in ("reported_at", "reported_by", "reported_by_id", "note", "snapshot")}
    kejadian.update({"reopened_at": now, "reopened_by": actor.get("name", ""), "reopened_by_id": actor.get("id", ""),
                     "reopen_reason": reason})
    doc = await db[LOCKS].find_one_and_update(
        {"id": ada["id"], "status": "reported", "reported_at": ada.get("reported_at")},
        {"$set": {"status": "reopened", "reopened_at": now, "reopened_by": actor.get("name", ""),
                  "reopened_by_id": actor.get("id", ""), "reopen_reason": reason, "updated_at": now},
         "$push": {"history": kejadian}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not doc:   # dibuka/ditandai ulang orang lain di antara baca dan tulis
        raise HTTPException(status_code=409, detail="Masa pajak ini baru saja diubah orang lain. Muat ulang lalu ulangi.")
    return doc


# ── Manual PPh records (basis=manual) ────────────────────────────────────────

async def list_pph_records(entity_id: Optional[str], period: Optional[str] = None,
                           code: Optional[str] = None, entity_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {**_ent_q(_scope(entity_id, entity_ids))}
    if period:
        q["period"] = period
    if code:
        q["code"] = code
    return await db.tax_pph_records.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)


async def record_pph(entity_id: str, period: str, code: str, name: str,
                     rate: float, dpp: float, note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    if not (entity_id and entity_id != "all"):
        raise ValueError("Pilih entitas spesifik untuk merekam PPh manual (bukan 'Semua Entitas').")
    if not period or len(period) != 7:
        raise ValueError("Periode harus format YYYY-MM.")
    await assert_masa_terbuka(entity_id, period.strip(), aksi="perekaman PPh")   # PK-40 — masa terkunci → 409
    dpp = round(float(dpp or 0), 2)
    amount = round(dpp * float(rate or 0) / 100.0, 2)
    doc = {
        "id": new_id("pphr"), "entity_id": entity_id, "period": period.strip(),
        "code": (code or "").strip(), "name": (name or code or "").strip(),
        "basis": "manual", "rate": float(rate or 0), "dpp": dpp, "amount": amount,
        "note": (note or "").strip(),
        "created_by": actor.get("name", "system"), "created_by_id": actor.get("id", ""),
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.tax_pph_records.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def delete_pph_record(record_id: str) -> bool:
    rec = await db.tax_pph_records.find_one({"id": record_id}, {"_id": 0, "entity_id": 1, "period": 1})
    if rec:   # PK-40 — rekaman masa yang sudah dilaporkan tidak bisa dihapus (409)
        await assert_masa_terbuka(rec.get("entity_id"), rec.get("period") or "", aksi="penghapusan rekaman PPh")
    res = await db.tax_pph_records.delete_one({"id": record_id})
    return res.deleted_count > 0
