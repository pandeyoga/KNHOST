"""Service — Cash Advance (Form PD) + Pertanggungjawaban (Settlement) + Expense Categories.

Koleksi:
- cash_advances (prefix ca_) — Form Pengajuan Dana; state-machine approval berjenjang.
- cash_advance_settlements (prefix stl_) — Laporan Pertanggungjawaban petty cash → auto-post GL.
- expense_categories (prefix excat_, SHARED) — mapping kategori pengeluaran → akun COA (configurable).

Akuntansi (anti double-count, buku per-entitas seimbang):
- Disburse : cash_transaction(out, ref_type='cash_advance') → GL Dr 1-1400 Uang Muka / Cr Kas.
- Settlement approved : GL Dr [beban per kategori, akun PT LPJ] / Cr 1-1400 Uang Muka (≤ uang muka; kelebihan →
  Cr 2-1650 Hutang Reimburse). PK-24: LPJ `approved` + jurnal lewat `post_durable` → `posted_to_gl` hanya bila jurnal
  terbit (gagal → panel Posting Gagal, jenis `petty_cash_settlement`).
- Pengembalian sisa (PK-24) : cash_transaction(in, ref_type='cash_advance_return') → Dr Kas / Cr 1-1400 (pemetaan
  `kas_bank.uang_muka_karyawan`) sebesar uang muka − pengeluaran → saldo uang muka PD = 0.
- Bayar reimburse : cash_transaction(out, ref_type='reimburse_payable') → Dr 2-1650 / Cr Kas.

Rantai approval PD (default — ACC owner, configurable):
  Atasan Langsung=manager · Pimpinan=admin · Bagian Keuangan=admin(finance); admin override semua tahap.

Kas & Bank 4 (C7) — `docs/superpowers/specs/2026-11-28-kas-bank-4-uang-muka-design.md` §5.1–§5.2, §7.9 (3–5):
- **Pemegang** PD (`pemegang = {jenis: pengguna|karyawan, id, nama}`): bawaan pembuat PD; pembuat boleh memilih karyawan
  HR aktif PT dokumen. PD lama tanpa bidang = pembuatnya (`created_by_id`/`created_by`), dibaca tanpa ditulis ulang.
- **Batas PD terbuka** per pemegang (`kas.pd_terbuka_maks` PT dokumen, 0 = tanpa batas; pengguna dihitung lintas PT):
  diperiksa saat **ajukan** (PD lain diajukan s.d. belum tuntas) dan saat **cairkan** (PD lain yang dipegang: cair belum
  tuntas, atau `settled` dengan sisa masih di tangan) di dalam kunci per pemegang (`cash_advance_locks`).
- **Batalkan PD** belum cair (draf/ditolak/dalam persetujuan/disetujui) → `cancelled`, oleh pembuat atau `cash_advance.reject`.
- **Tenggat LPJ** dipotret saat cair (`lpj_jatuh_tempo` = tanggal buku cair + `kas.lpj_tenggat_hari`); PD cair tanpa potret
  = max(tanggal cair, waktu fitur aktif) + N (penanda sekali tulis `kb4_lpj_tenggat_aktif_sejak`). Terpenuhi saat LPJ
  diajukan; LPJ ditolak → dihitung lagi. Pembaca: daftar/rincian PD, Kas Kecil, Meja Keuangan, penjadwal pengingat.
"""
import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument

from db import db
from core_utils import new_id, now_iso, next_doc_number, rupiah, safe_doc
from dependencies import audit, has_permission
from entity_scope import EntityContext, resolve_list_scope, assert_entity_access, assert_active_entity_access
from services import gl_service
from services.book_date import tanggal_buku, tanggal_panjang
# Kas & Bank 4 — status karyawan HR yang tidak bisa memegang uang muka (sudah keluar): daftar pemilih opname kas.
from services.cash_count_service import _KARYAWAN_KELUAR

logger = logging.getLogger(__name__)

CA_COLL = "cash_advances"
STL_COLL = "cash_advance_settlements"
EXCAT_COLL = "expense_categories"


async def _cara_bayar(entity_id: str, value: str) -> str:
    """PM-T1 — cara pencairan dari daftar induk cara bayar (arah keluar); `tunai` lama → `cash`. Galat → 400."""
    from services.payment_method_service import kode_400
    return await kode_400(entity_id, value or "cash", arah="keluar")

# KP-T4 — rantai persetujuan PD dari Aturan Persetujuan (jenis `cash_advance`): jenjang → status lewat
# `approval_kinds.APPROVAL_KINDS["cash_advance"]["level_status"]`; jenjang tanpa baris dilewati. Dulu `APPROVAL_STAGES`
# (tiga tahap ditulis mati: Atasan {manager, admin}, Pimpinan {admin}, Keuangan {admin}; admin selalu lolos) — kini
# baris bawaan tabel (`approval_policy_service.BAWAAN_UANG_MUKA`).
CA_KIND = "cash_advance"
_STAGE_KEY = {1: "atasan", 2: "pimpinan", 3: "finance"}
EDITABLE_STATUSES = {"draft", "rejected"}


def _level_status() -> Dict[int, str]:
    from approval_kinds import APPROVAL_KINDS
    return dict(APPROVAL_KINDS[CA_KIND]["level_status"])


def _level_of_status(status: str) -> int:
    return next((lv for lv, st in _level_status().items() if st == status), 0)


async def _next_status(doc: Dict[str, Any], after_level: int = 0) -> str:
    """Status berikutnya: jenjang wajib pertama sesudah `after_level` (menurut tabel), atau `approved`."""
    from services import approval_policy_service as _aps
    levels = await _aps.required_levels(CA_KIND, doc.get("entity_id"), float(doc.get("total_amount") or 0))
    st = _level_status()
    nxt = next((lv["level"] for lv in levels if lv["level"] > after_level and lv["level"] in st), None)
    return st[nxt] if nxt else "approved"

# Kategori pengeluaran default (dari Excel Laporan Petty Cash) → akun beban COA.
DEFAULT_EXPENSE_CATEGORIES = [
    ("office_supplies", "Office Supplies", "6-4100", 1),
    ("atk", "ATK", "6-4100", 2),
    ("lunch_snack_entertainment", "Lunch / Snack / Entertainment", "6-4200", 3),
    ("fotocopy_printing_jilid_materai", "Fotokopi / Printing / Jilid / Materai", "6-4300", 4),
    ("utilitas_kantor", "Telepon / Listrik / Air / Internet / IPKL", "6-4400", 5),
    ("kirim_dokumen", "Kirim Dokumen", "6-4500", 6),
    ("transportasi", "Transportasi (Service Mobil/Taxi/BBM/Tol/Parkir)", "6-4600", 7),
    ("petty_cash_lain", "Petty Cash Lainnya", "6-4900", 8),
]
FALLBACK_ACCOUNT = "6-4900"


def _r(v: Any) -> float:
    return round(float(v or 0), 2)


# ═══ Expense Categories (mapping kategori → akun) ════════════════════════
async def seed_expense_categories() -> int:
    """Idempotent — hanya tambah kategori yang belum ada."""
    existing = {c["code"] for c in await db[EXCAT_COLL].find({}, {"_id": 0, "code": 1}).to_list(200)}
    to_add = []
    for code, label, acc, sort in DEFAULT_EXPENSE_CATEGORIES:
        if code in existing:
            continue
        to_add.append({
            "id": new_id("excat"), "entity_id": "all", "code": code, "label": label,
            "account_code": acc, "sort": sort, "active": True,
            "created_at": now_iso(), "updated_at": now_iso(),
        })
    if to_add:
        await db[EXCAT_COLL].insert_many(to_add)
    return len(to_add)


async def list_expense_categories(active_only: bool = False,
                                  entity_id: str = "") -> List[Dict[str, Any]]:
    """Kategori biaya EFEKTIF untuk satu badan usaha — global + override, tanpa kembar.

    FASE E-4 (E4.3). `entity_id` kosong = hanya lapisan global (perilaku lama).
    """
    from services import entity_master_service as ems
    rows = await ems.effective_rows("expense-categories", entity_id,
                                    include_inactive=not active_only)
    rows.sort(key=lambda c: c.get("sort", 999))
    return rows


async def update_expense_category(code: str, patch: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    cat = await db[EXCAT_COLL].find_one({"code": code}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Kategori tidak ditemukan")
    upd: Dict[str, Any] = {}
    if patch.get("label") is not None:
        upd["label"] = str(patch["label"]).strip()
    if patch.get("active") is not None:
        upd["active"] = bool(patch["active"])
    if patch.get("account_code") is not None:
        acc_code = str(patch["account_code"]).strip()
        acc = await db.gl_accounts.find_one({"code": acc_code, "entity_id": {"$in": [None, ""]}}, {"_id": 0})
        if not acc:
            raise HTTPException(status_code=400, detail=f"Akun '{acc_code}' tidak ditemukan")
        if not acc.get("is_postable", True):
            raise HTTPException(status_code=400, detail=f"Akun '{acc_code}' header — pilih akun detail")
        upd["account_code"] = acc_code
    upd["updated_at"] = now_iso()
    await db[EXCAT_COLL].update_one({"code": code}, {"$set": upd})
    await audit(actor.get("name", ""), "expense_category_updated", "expense_category", code, upd)
    return await db[EXCAT_COLL].find_one({"code": code}, {"_id": 0})


async def _category_account_map(entity_id: str) -> Dict[str, str]:
    """PK-24 (FY-13) — peta kategori → akun beban EFEKTIF untuk PT LPJ (lapisan PT menang atas global, tanpa kembar).
    Dulu dibaca dari SEMUA baris kategori tanpa lapisan, sehingga lapisan PT lain bisa terpakai."""
    rows = await list_expense_categories(entity_id=entity_id)
    return {r["code"]: r.get("account_code") or FALLBACK_ACCOUNT for r in rows if r.get("code")}


# ═══ Cash Advance (Form PD) ════════════════════════════════════
def _compute_lines(raw_lines) -> (List[Dict[str, Any]], float):
    lines: List[Dict[str, Any]] = []
    total = 0.0
    for ln in (raw_lines or []):
        d = ln.model_dump() if hasattr(ln, "model_dump") else dict(ln)
        qty = _r(d.get("qty"))
        unit_price = _r(d.get("unit_price"))
        amount = _r(qty * unit_price)   # FIX: amount SELALU dari qty aktif × harga
        d["qty"] = qty
        d["unit_price"] = unit_price
        d["amount"] = amount
        total += amount
        lines.append(d)
    return lines, _r(total)


async def create_cash_advance(payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    entity_id = payload.entity_id or ctx.active_entity_id
    if entity_id not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
    payload.payment_method = await _cara_bayar(entity_id, payload.payment_method)
    lines, total = _compute_lines(payload.lines)
    if not lines:
        raise HTTPException(status_code=400, detail="Minimal 1 baris rincian dana")
    if total <= 0:
        raise HTTPException(status_code=400, detail="Total pengajuan harus lebih dari 0")
    # Kas & Bank 4 (§7.9.3) — pemegang uang: bawaan pembuat; karyawan HR aktif PT dokumen bila dipilih.
    pemegang_uang = await _pemegang_isian(getattr(payload, "pemegang", None), entity_id,
                                          {"id": actor.get("id", ""), "name": actor.get("name", "")})
    number = await next_doc_number(CA_COLL, "number", "PD-", entity_id=entity_id)
    bank = payload.bank_detail.model_dump() if payload.bank_detail else {}
    doc = {
        "id": new_id("ca"),
        "number": number,
        "entity_id": entity_id,
        "divisi": (payload.divisi or "").strip(),
        "kegiatan": (payload.kegiatan or "").strip(),
        "period_from": payload.period_from or "",
        "period_to": payload.period_to or "",
        "tanggal_pengajuan": payload.tanggal_pengajuan or now_iso(),
        "account_label": (payload.account_label or "").strip(),
        "payment_method": payload.payment_method,
        "bank_detail": bank,
        "lines": lines,
        "total_amount": total,
        "status": "draft",
        "approvals": [],
        "disbursement": None,
        "rejected_reason": "",
        "catatan": (payload.catatan or "").strip(),
        "created_by": actor.get("name", ""),
        "created_by_id": actor.get("id", ""),   # KF-T6 — pemohon andal untuk kontrol dua orang
        "pemegang": pemegang_uang,              # Kas & Bank 4 — orang yang batas PD terbukanya dihitung
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db[CA_COLL].insert_one(doc)
    await audit(actor.get("name", ""), "cash_advance_created", "cash_advance", doc["id"],
                {"number": number, "total": total, "entity_id": entity_id, "pemegang": pemegang_uang})
    return safe_doc(doc)


def cash_advance_query(ctx: EntityContext, entity_id: Optional[str] = None,
                       status: Optional[str] = None) -> Dict[str, Any]:
    """Kueri daftar PD yang boleh dilihat pemanggil (aturan PT satu tempat: daftar PD dan daftar kerja kas kecil)."""
    q = resolve_list_scope(CA_COLL, {}, ctx, entity_id)
    if status:
        q["status"] = status
    return q


async def list_cash_advances(ctx: EntityContext, entity_id: Optional[str] = None,
                             status: Optional[str] = None,
                             actor: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Daftar PD + bidang turunan Kas & Bank 4 (`_hiasi`: pemegang, tenggat LPJ, boleh diajukan)."""
    q = cash_advance_query(ctx, entity_id, status)
    rows = await db[CA_COLL].find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return await _hiasi(rows, actor)


async def get_cash_advance(ca_id: str, ctx: EntityContext) -> Dict[str, Any]:
    doc = await db[CA_COLL].find_one({"id": ca_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Pengajuan Dana tidak ditemukan")
    assert_active_entity_access(doc, CA_COLL, ctx)   # KN-B35 — penjaga KETAT (jalur tulis memakai loader ini)
    return safe_doc(doc)


async def rincian_cash_advance(ca_id: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`GET /api/cash-advances/{id}` — dokumen PD + bidang turunan Kas & Bank 4 (loader tulis tetap `get_cash_advance`)."""
    return (await _hiasi([await get_cash_advance(ca_id, ctx)], actor))[0]


async def update_cash_advance(ca_id: str, payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_cash_advance(ca_id, ctx)
    if doc["status"] not in EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Hanya PD draft/ditolak yang bisa diubah")
    upd: Dict[str, Any] = {}
    for f in ["divisi", "kegiatan", "period_from", "period_to", "tanggal_pengajuan",
              "account_label", "catatan"]:
        v = getattr(payload, f, None)
        if v is not None:
            upd[f] = v.strip() if isinstance(v, str) else v
    if payload.payment_method is not None:
        upd["payment_method"] = await _cara_bayar(doc.get("entity_id") or "", payload.payment_method)
    if payload.bank_detail is not None:
        upd["bank_detail"] = payload.bank_detail.model_dump()
    if payload.lines is not None:
        lines, total = _compute_lines(payload.lines)
        if not lines or total <= 0:
            raise HTTPException(status_code=400, detail="Rincian dana tidak valid")
        upd["lines"] = lines
        upd["total_amount"] = total
    if getattr(payload, "pemegang", None) is not None:   # Kas & Bank 4 — "pengguna" = pembuat PD, bukan penyunting
        upd["pemegang"] = await _pemegang_isian(payload.pemegang, doc.get("entity_id") or "",
                                                {"id": doc.get("created_by_id") or "", "name": doc.get("created_by") or ""})
    upd["updated_at"] = now_iso()
    updated = await db[CA_COLL].find_one_and_update(
        {"id": ca_id}, {"$set": upd}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "cash_advance_updated", "cash_advance", ca_id, upd)
    return safe_doc(updated)


async def submit_cash_advance(ca_id: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_cash_advance(ca_id, ctx)
    if doc["status"] not in EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail=PESAN_BUKAN_DRAF)
    # Kas & Bank 4 (C7) — PERIKSA batas PD terbuka pemegang → KUNCI pemegang → PERIKSA ULANG → KLAIM status bersyarat.
    batas = await batas_pd_terbuka(doc.get("entity_id") or "")
    await _tolak_bila_tertahan(doc, actor, saat="ajukan", batas=batas)
    async with _kunci_pemegang(doc, actor, aktif=batas > 0):
        doc = await get_cash_advance(ca_id, ctx)
        if doc["status"] not in EDITABLE_STATUSES:
            raise HTTPException(status_code=409, detail=PESAN_BUKAN_DRAF)
        await _tolak_bila_tertahan(doc, actor, saat="ajukan", batas=batas)
        first = await _next_status(doc, 0)   # KP-T4 — jenjang wajib pertama menurut Aturan Persetujuan
        updated = await db[CA_COLL].find_one_and_update(
            {"id": ca_id, "status": {"$in": sorted(EDITABLE_STATUSES)}},
            {"$set": {"status": first, "rejected_reason": "", "updated_at": now_iso()}},
            projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(status_code=409, detail=f"PD {doc.get('number', '')} berubah saat diajukan. Muat ulang.")
    await audit(actor.get("name", ""), "cash_advance_submitted", "cash_advance", ca_id,
                {"status": first})
    return safe_doc(updated)


async def approve_cash_advance(ca_id: str, note: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_cash_advance(ca_id, ctx)
    level = _level_of_status(doc["status"])
    if not level:
        raise HTTPException(status_code=409, detail="PD tidak dalam status menunggu persetujuan")
    role = actor.get("role", "")
    # KP-T4 — izin `cash_advance.approve` + peran tercantum di Aturan Persetujuan pada jenjang ini (dulu daftar ditulis
    # mati + pengecualian nama admin).
    from services import approval_policy_service as _aps
    await _aps.assert_can_decide(CA_KIND, doc.get("entity_id"), float(doc.get("total_amount") or 0), actor, level)
    lv_label = next((x["label"] for x in await _aps.required_levels(
        CA_KIND, doc.get("entity_id"), float(doc.get("total_amount") or 0)) if x["level"] == level), "")
    stage = {"stage": _STAGE_KEY.get(level, f"jenjang_{level}"), "label": lv_label or f"Jenjang {level}",
             "next": await _next_status(doc, level)}
    # KF-T6 — pemohon ≠ penyetuju dari `kontrol.uang_muka.*` (bawaan satu orang; di atas batas nominal dua orang).
    from services import dual_control as _dc
    await _dc.tolak_bila_pelaku_sama("uang_muka", doc, actor, doc.get("entity_id", ""),
                                     nominal=float(doc.get("total_amount") or 0),
                                     pengaju=[doc.get("created_by_id"), doc.get("created_by")])
    approval = {"stage": stage["stage"], "label": stage["label"], "decision": "approved",
                "by": actor.get("name", ""), "role": role, "note": (note or "").strip(),
                "at": now_iso()}
    updated = await db[CA_COLL].find_one_and_update(
        {"id": ca_id},
        {"$set": {"status": stage["next"], "updated_at": now_iso()},
         "$push": {"approvals": approval}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "cash_advance_approved", "cash_advance", ca_id,
                {"stage": stage["stage"], "next": stage["next"]})
    return safe_doc(updated)


async def reject_cash_advance(ca_id: str, reason: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_cash_advance(ca_id, ctx)
    level = _level_of_status(doc["status"])
    if not level:
        raise HTTPException(status_code=409, detail="PD tidak dalam status menunggu persetujuan")
    role = actor.get("role", "")
    from services import approval_policy_service as _aps   # KP-T4 — izin `cash_advance.reject` + Aturan Persetujuan
    await _aps.assert_can_decide(CA_KIND, doc.get("entity_id"), float(doc.get("total_amount") or 0), actor, level,
                                 action="reject")
    stage = {"stage": _STAGE_KEY.get(level, f"jenjang_{level}"), "label": f"Jenjang {level}"}
    approval = {"stage": stage["stage"], "label": stage["label"], "decision": "rejected",
                "by": actor.get("name", ""), "role": role, "note": (reason or "").strip(),
                "at": now_iso()}
    updated = await db[CA_COLL].find_one_and_update(
        {"id": ca_id},
        {"$set": {"status": "rejected", "rejected_reason": (reason or "").strip(), "updated_at": now_iso()},
         "$push": {"approvals": approval}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "cash_advance_rejected", "cash_advance", ca_id, {"reason": reason})
    return safe_doc(updated)


async def disburse_cash_advance(ca_id: str, payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_cash_advance(ca_id, ctx)
    if doc["status"] != "approved":
        raise HTTPException(status_code=409, detail="Hanya PD berstatus 'approved' yang bisa dicairkan")
    cash_type = payload.cash_type if payload.cash_type in ("kas_kecil", "kas_besar") else "kas_kecil"
    entity_id = doc["entity_id"]
    # PK-24 (K-17) — pemohon ≠ pencair dari `kontrol.cairkan_uang_muka.*` (bawaan satu orang; di atas batas nominal dua
    # orang). Wewenang mencairkan sendiri = izin `cash_advance.disburse` (bawaan Admin, Manajer, Finance).
    from services import dual_control as _dc
    await _dc.tolak_bila_pelaku_sama("cairkan_uang_muka", doc, actor, entity_id,
                                     nominal=float(doc.get("total_amount") or 0),
                                     pengaju=[doc.get("created_by_id"), doc.get("created_by")])
    try:
        await gl_service.preflight_posting(entity_id, payload.txn_date or now_iso())
    except gl_service.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # PK-20 — rekening sumber (isian baru `account_id`; kosong = rekening tunggal PT jenis kas itu) diperiksa SEBELUM klaim.
    from services import cash_ledger
    rek = await cash_ledger.periksa_rekening(entity_id, getattr(payload, "account_id", "") or "", cash_type)
    # Kas & Bank 4 (§7.9.5) — pemegang yang masih memegang PD lain (cair belum tuntas / sisa di tangan) → 409; diperiksa
    # ulang di dalam kunci pemegang yang dipegang sampai pencairan selesai (dua cairkan bersamaan = satu lolos).
    batas = await batas_pd_terbuka(entity_id)
    await _tolak_bila_tertahan(doc, actor, saat="cairkan", batas=batas)
    async with _kunci_pemegang(doc, actor, aktif=batas > 0):
        await _tolak_bila_tertahan(doc, actor, saat="cairkan", batas=batas)
        # CX-04 — klaim atomik (satu pencairan per PD) + resume: kas lama dari percobaan gagal DIPAKAI ULANG.
        from services import atomic_claim as _saga
        await _saga.claim(CA_COLL, ca_id, "cash_advance_disburse", precondition={"status": "approved"},
                          actor=actor.get("name", ""))
        try:
            return await _disburse_locked(ca_id, doc, payload, rek["cash_type"], entity_id, actor, rek["account_id"])
        finally:
            await _saga.release(CA_COLL, ca_id)


async def _disburse_locked(ca_id: str, doc: Dict[str, Any], payload, cash_type: str, entity_id: str,
                           actor: Dict[str, Any], account_id: str = "") -> Dict[str, Any]:
    """PK-20 — kas pencairan lewat pembuat kas satu pintu: rujukan (`cash_advance`, id PD, keluar) memberi id tetap,
    jadi percobaan ulang memakai kas yang sama. Jurnal gagal → PD tetap 'approved', kas tertaut ber-`failed`."""
    from services import cash_ledger
    try:
        txn = await cash_ledger.create_cash(
            entity_id=entity_id, direction="out", amount=_r(doc["total_amount"]), ref_type="cash_advance", ref_id=ca_id,
            account_id=account_id, cash_type=cash_type, txn_date=payload.txn_date or "", category="cash_advance",
            # FASE E-7 (E7.4) — kas grup dihapus: pencairan uang muka karyawan tetap uang badan usaha yang
            # menugaskannya, walau ditransfer lewat bank (`kas_besar`).
            description=f"Pencairan {doc['number']} — {doc.get('kegiatan', '')}".strip(),
            actor=actor.get("name", ""))
    except cash_ledger.CashPostingError as exc:
        await db[CA_COLL].update_one({"id": ca_id}, {"$set": {"disbursement_attempt": {
            "cash_txn_id": exc.txn.get("id", ""), "at": now_iso(), "by": actor.get("name", "")}}})
        raise HTTPException(status_code=409, detail=(
            f"Kas {exc.txn.get('number', '')} tercatat tetapi jurnal gagal: {exc.error}. Ulangi pencairan untuk "
            "melanjutkan (tanpa kas ganda)."))
    # GL: Dr 1-1400 Uang Muka / Cr Kas (idempotent by source cash_transaction).
    je = await db.journal_entries.find_one(
        {"source_type": "cash_transaction", "source_id": txn["id"], "status": {"$ne": "void"}},
        {"_id": 0, "id": 1, "number": 1})
    return await _finish_disburse(ca_id, doc, txn, je, txn.get("cash_type") or cash_type, payload, actor)


async def _finish_disburse(ca_id: str, doc: Dict[str, Any], txn: Dict[str, Any], je, cash_type: str,
                           payload, actor: Dict[str, Any]) -> Dict[str, Any]:
    number = txn.get("number", "")
    disb = {
        "cash_txn_id": txn["id"], "cash_txn_number": number,
        "je_id": (je or {}).get("id"), "je_number": (je or {}).get("number"),
        "cash_type": cash_type, "amount": _r(doc["total_amount"]),
        "account_id": txn.get("account_id", ""),   # PK-24 — rekening sumber pencairan
        "disbursed_at": now_iso(), "disbursed_by": actor.get("name", ""),
        "disbursed_by_id": actor.get("id", ""),    # PK-24 — id pelaku (bahan kontrol dua orang)
        "note": (payload.note or "").strip(),
    }
    # Kas & Bank 4 (§5.2) — potret tenggat LPJ: tanggal buku kas pencairan + `kas.lpj_tenggat_hari` PT PD saat ini;
    # pengaturan yang berubah sesudahnya tidak menggeser tenggat PD ini.
    hari = await hari_tenggat_lpj(doc.get("entity_id") or "")
    tgl_cair = _tanggal_aman(txn.get("txn_date") or getattr(payload, "txn_date", "") or "") or tanggal_buku()
    jatuh_tempo = (date.fromisoformat(tgl_cair) + timedelta(days=hari)).isoformat()
    updated = await db[CA_COLL].find_one_and_update(
        {"id": ca_id, "status": "approved"},
        {"$set": {"status": "disbursed", "disbursement": disb, "disbursed_by_id": actor.get("id", ""),
                  "lpj_jatuh_tempo": jatuh_tempo, "lpj_tenggat_hari": hari, "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "cash_advance_disbursed", "cash_advance", ca_id,
                {**disb, "lpj_jatuh_tempo": jatuh_tempo, "lpj_tenggat_hari": hari})
    return safe_doc(updated)


# ═══ Kas & Bank 4 (C7) — pemegang PD, batas PD terbuka, Batalkan PD, tenggat LPJ ═══════════════════════════════════
K_PD_TERBUKA_MAKS = "kas.pd_terbuka_maks"
K_LPJ_TENGGAT_HARI = "kas.lpj_tenggat_hari"
#: Waktu fitur tenggat aktif (sekali tulis, dokumen `system_settings.__migrations__`, pola F1 / Kas & Bank 3): PD yang
#: cair sebelum fitur ini (tanpa potret `lpj_jatuh_tempo`) bertenggat dari waktu ini, jadi tidak ada yang langsung lewat.
PENANDA_TENGGAT_AKTIF = "kb4_lpj_tenggat_aktif_sejak"
#: Kunci per pemegang (`_id` = `kunci_pemegang`, pola `petty_float_locks`): ajukan & cairkan pemegang yang sama berurutan.
COLL_KUNCI = "cash_advance_locks"
KUNCI_BASI_DETIK = 300      # proses yang mati meninggalkan kunci → diambil alih sesudah ini
KUNCI_TUNGGU_DETIK = 3.0    # pemanggil kedua menunggu kunci sebentar, lalu memeriksa ulang dengan data terbaru
KUNCI_JEDA_DETIK = 0.05
#: LPJ yang memenuhi tenggat (diajukan, disetujui, terjurnal); draf & ditolak tidak.
LPJ_MEMENUHI_TENGGAT = ("submitted", "approved", "posted_to_gl")
#: PD yang punya tenggat LPJ (sudah cair).
STATUS_BERTENGGAT = ("disbursed", "settled")
#: Status sisa uang muka LPJ terjurnal yang berarti uangnya masih di tangan pemegang.
SISA_DI_TANGAN = ("open", "returning")
PESAN_BUKAN_DRAF = "Hanya PD draft/ditolak yang bisa diajukan"
PESAN_ALASAN_BATAL = "Alasan pembatalan wajib diisi (minimal 5 huruf)."
PESAN_PEMEGANG_JENIS = "Pemegang uang hanya pembuat PD sendiri atau karyawan PT ini."
PESAN_PEMEGANG_PENGGUNA = "Pemegang uang pengguna hanya pembuat PD sendiri. Untuk orang lain, pilih karyawan."
PESAN_PEMEGANG_KOSONG = "Pilih karyawan yang memegang uang."
PESAN_PEMEGANG_TIDAK_ADA = "Karyawan pemegang uang tidak ditemukan."


def _status_menunggu() -> List[str]:
    """PD yang sudah diajukan tetapi belum cair: tiap jenjang persetujuan + disetujui."""
    return [*_level_status().values(), "approved"]


def _status_bisa_batal() -> List[str]:
    """§7.9.4 — PD belum cair yang boleh dibatalkan: draf, ditolak, dalam persetujuan, disetujui."""
    return [*sorted(EDITABLE_STATUSES), *_status_menunggu()]


def pemegang(pd: Dict[str, Any]) -> Dict[str, str]:
    """Pemegang uang PD → `{jenis, id, nama}`. PD lama tanpa bidang = pembuatnya (pengguna); tidak ditulis ulang."""
    p = (pd or {}).get("pemegang") or {}
    if p.get("jenis") in ("pengguna", "karyawan") and p.get("id"):
        return {"jenis": p["jenis"], "id": str(p["id"]), "nama": str(p.get("nama") or "")}
    return {"jenis": "pengguna", "id": str((pd or {}).get("created_by_id") or ""),
            "nama": str((pd or {}).get("created_by") or "")}


def kunci_pemegang(pd: Dict[str, Any]) -> str:
    """Kunci orang yang batasnya dihitung: `"u:" + id pengguna` (lintas PT) atau `"k:" + id karyawan`."""
    p = pemegang(pd)
    return ("k:" if p["jenis"] == "karyawan" else "u:") + p["id"]


def _saring_pemegang(kunci: str) -> Optional[Dict[str, Any]]:
    """Saringan PD milik pemegang `kunci`; None bila pemegangnya tidak dikenal (PD sangat lama tanpa id pembuat)."""
    jenis, _, pid = (kunci or "").partition(":")
    if not pid:
        return None
    if jenis == "k":
        return {"pemegang.jenis": "karyawan", "pemegang.id": pid}
    if jenis == "u":
        return {"$or": [{"pemegang.jenis": "pengguna", "pemegang.id": pid},
                        {"pemegang": {"$exists": False}, "created_by_id": pid}]}
    return None


async def _pemegang_isian(isian: Any, entity_id: str, pembuat: Dict[str, Any]) -> Dict[str, str]:
    """§7.9.3 — isian pemegang → `{jenis, id, nama}`. Kosong / "pengguna" = pembuat PD; "karyawan" = karyawan HR aktif PT
    dokumen (nama diambil dari master, bukan dari klien). Selain itu 400 berkalimat."""
    d = isian.model_dump() if hasattr(isian, "model_dump") else dict(isian or {})
    jenis = str(d.get("jenis") or "pengguna").strip()
    pid = str(d.get("id") or "").strip()
    if jenis == "pengguna":
        if pid and pid != (pembuat.get("id") or ""):
            raise HTTPException(status_code=400, detail=PESAN_PEMEGANG_PENGGUNA)
        return {"jenis": "pengguna", "id": pembuat.get("id") or "", "nama": pembuat.get("name") or ""}
    if jenis != "karyawan":
        raise HTTPException(status_code=400, detail=PESAN_PEMEGANG_JENIS)
    if not pid:
        raise HTTPException(status_code=400, detail=PESAN_PEMEGANG_KOSONG)
    emp = await db.hr_employees.find_one({"id": pid}, {"_id": 0, "id": 1, "name": 1, "entity_id": 1, "status": 1})
    if not emp:
        raise HTTPException(status_code=400, detail=PESAN_PEMEGANG_TIDAK_ADA)
    nama = emp.get("name") or pid
    if (emp.get("entity_id") or "") != entity_id:
        raise HTTPException(status_code=400, detail=f"{nama} bukan karyawan PT ini. Pilih karyawan PT pengajuan dana ini.")
    if (emp.get("status") or "") in _KARYAWAN_KELUAR:
        raise HTTPException(status_code=400, detail=(f"{nama} sudah tidak aktif sebagai karyawan, jadi tidak bisa "
                                                     "memegang uang muka."))
    return {"jenis": "karyawan", "id": emp["id"], "nama": nama}


async def karyawan_pemegang(entity_id: str, q: str = "") -> List[Dict[str, Any]]:
    """`GET /api/cash-advances/karyawan` — karyawan HR aktif PT (id, kode, nama) untuk pilihan pemegang uang; pemilih
    yang sama dengan opname kas (tanpa data pribadi lain)."""
    from services import cash_count_service as ccs
    return await ccs.karyawan(entity_id, q)


async def batas_pd_terbuka(entity_id: str) -> int:
    """`kas.pd_terbuka_maks` PT dokumen: berapa PD terbuka yang boleh dipegang satu orang (0 = tanpa batas)."""
    try:
        return max(int(await _nilai_pengaturan(K_PD_TERBUKA_MAKS, entity_id)), 0)
    except (TypeError, ValueError):
        import config_registry as _reg
        return int(_reg.default_of(K_PD_TERBUKA_MAKS))


async def hari_tenggat_lpj(entity_id: str) -> int:
    """`kas.lpj_tenggat_hari` PT dokumen: LPJ jatuh tempo sekian hari sesudah tanggal buku cair."""
    try:
        return int(await _nilai_pengaturan(K_LPJ_TENGGAT_HARI, entity_id))
    except (TypeError, ValueError):
        import config_registry as _reg
        return int(_reg.default_of(K_LPJ_TENGGAT_HARI))


async def pd_terbuka(kunci: str, *, kecuali_id: str = "", hanya_dipegang: bool = False) -> List[Dict[str, Any]]:
    """PD terbuka milik pemegang `kunci` (selain `kecuali_id`), urut: yang uangnya dipegang dulu, lalu yang terlama.

    `hanya_dipegang` False (ajukan) = diajukan / dalam persetujuan / disetujui / cair, atau `settled` yang sisanya masih
    di tangan; True (cairkan, §7.9.5) = hanya cair belum tuntas atau `settled` bersisa di tangan. PD `settled` membawa
    `sisa_di_tangan` (nominal sisa LPJ yang belum kembali)."""
    siapa = _saring_pemegang(kunci)
    if siapa is None:
        return []
    status = list(STATUS_BERTENGGAT) if hanya_dipegang else [*_status_menunggu(), *STATUS_BERTENGGAT]
    q: Dict[str, Any] = {**siapa, "status": {"$in": status}}
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    rows = await db[CA_COLL].find(q, {"_id": 0}).to_list(500)
    selesai = [r["id"] for r in rows if r.get("status") == "settled"]
    sisa: Dict[str, float] = {}
    if selesai:
        async for s in db[STL_COLL].find({"cash_advance_id": {"$in": selesai}, "status": "posted_to_gl",
                                          "sisa_dikembalikan.status": {"$in": list(SISA_DI_TANGAN)}},
                                         {"_id": 0, "cash_advance_id": 1, "sisa_dikembalikan": 1}):
            sisa[s["cash_advance_id"]] = _r((s.get("sisa_dikembalikan") or {}).get("amount"))
    out = []
    for r in rows:
        if r.get("status") == "settled":
            if r["id"] not in sisa:
                continue
            r["sisa_di_tangan"] = sisa[r["id"]]
        out.append(r)
    out.sort(key=lambda r: (r.get("status") not in STATUS_BERTENGGAT, str(r.get("created_at") or ""),
                            str(r.get("number") or "")))
    return out


async def _kalimat_tertahan(pd: Dict[str, Any], terbuka: List[Dict[str, Any]], actor: Optional[Dict[str, Any]],
                            saat: str) -> str:
    """Kalimat 409 (Global Constraints rencana): "<Anda|nama pemegang> masih memegang uang muka PD-… (Rp …, LPJ jatuh
    tempo …). Selesaikan LPJ-nya dulu sebelum mengajukan uang muka baru." — rincian & suruhan mengikuti keadaan PD yang
    disebut (belum cair / cair / sisa belum kembali); saat cairkan berakhir "sebelum <PD ini> dicairkan"."""
    p = pemegang(pd)
    if p["jenis"] == "pengguna" and p["id"] and p["id"] == (actor or {}).get("id"):
        subjek = "Anda"
    else:
        subjek = p["nama"] or "Pemegang uang PD ini"
    pertama = terbuka[0]
    nominal = rupiah(_r(pertama.get("total_amount")))
    st = pertama.get("status")
    if st == "disbursed":
        t = await tenggat(pertama) or {}
        rincian = f"{nominal}, LPJ jatuh tempo {tanggal_panjang(t['jatuh_tempo'])}" if t.get("jatuh_tempo") else nominal
        suruhan = "Selesaikan LPJ-nya dulu"
    elif st == "settled":
        rincian = f"{nominal}, sisa {rupiah(pertama.get('sisa_di_tangan') or 0)} belum dikembalikan"
        suruhan = "Kembalikan sisanya dulu"
    else:
        rincian = f"{nominal}, disetujui, belum dicairkan" if st == "approved" else f"{nominal}, menunggu persetujuan"
        suruhan = "Selesaikan atau batalkan PD itu dulu"
    lain = f" dan {len(terbuka) - 1} PD lain" if len(terbuka) > 1 else ""
    akhir = f"sebelum {pd.get('number', '')} dicairkan." if saat == "cairkan" else "sebelum mengajukan uang muka baru."
    return f"{subjek} masih memegang uang muka {pertama.get('number', '')} ({rincian}){lain}. {suruhan} {akhir}"


async def periksa_batas(pd: Dict[str, Any], actor: Optional[Dict[str, Any]], *, saat: str,
                        batas: Optional[int] = None) -> str:
    """"" = boleh; selain itu kalimat kenapa PD ini tertahan (`saat` "ajukan" | "cairkan"). Tanpa tulisan."""
    if batas is None:
        batas = await batas_pd_terbuka(pd.get("entity_id") or "")
    if batas <= 0:
        return ""
    terbuka = await pd_terbuka(kunci_pemegang(pd), kecuali_id=pd.get("id") or "", hanya_dipegang=saat == "cairkan")
    if len(terbuka) < batas:
        return ""
    return await _kalimat_tertahan(pd, terbuka, actor, saat)


async def _tolak_bila_tertahan(pd: Dict[str, Any], actor: Dict[str, Any], *, saat: str, batas: int) -> None:
    alasan = await periksa_batas(pd, actor, saat=saat, batas=batas)
    if alasan:
        raise HTTPException(status_code=409, detail=alasan)


@asynccontextmanager
async def _kunci_pemegang(pd: Dict[str, Any], actor: Dict[str, Any], *, aktif: bool = True):
    """Kunci ajukan/cairkan satu pemegang (pola `petty_float_service._kunci`): satu dokumen ber-`_id` = kunci pemegang;
    kunci basi diambil alih; pemanggil kedua menunggu sampai `KUNCI_TUNGGU_DETIK` lalu 409. `aktif` False (tanpa batas)
    → tanpa kunci."""
    kunci = kunci_pemegang(pd)
    if not aktif or _saring_pemegang(kunci) is None:
        yield
        return
    from pymongo.errors import DuplicateKeyError
    token = new_id("lk")
    tenggat_tunggu = time.monotonic() + KUNCI_TUNGGU_DETIK
    while True:
        sekarang = datetime.now(timezone.utc)
        await db[COLL_KUNCI].delete_one({"_id": kunci,
                                         "mulai": {"$lt": (sekarang - timedelta(seconds=KUNCI_BASI_DETIK)).isoformat()}})
        try:
            await db[COLL_KUNCI].insert_one({"_id": kunci, "token": token, "pd_id": pd.get("id") or "",
                                             "oleh": (actor or {}).get("name") or "", "mulai": sekarang.isoformat()})
            break
        except DuplicateKeyError:
            if time.monotonic() >= tenggat_tunggu:
                nama = pemegang(pd)["nama"] or "pemegang ini"
                raise HTTPException(status_code=409, detail=(
                    f"Uang muka atas nama {nama} sedang diproses orang lain. Tunggu sebentar lalu ulangi.")) from None
            await asyncio.sleep(KUNCI_JEDA_DETIK)
    try:
        yield
    finally:
        await db[COLL_KUNCI].delete_one({"_id": kunci, "token": token})


# ── Tenggat LPJ ──────────────────────────────────────────────────────────────────────────────────────────────────────
async def ensure_tenggat_aktif_sejak() -> str:
    """Tulis waktu aktif tenggat LPJ SEKALI (saat backend pertama menyala); panggilan berikutnya tidak menimpa. Pola
    `cash_count_service.ensure_aktif_sejak` (dibaca dulu, ditulis hanya bila kuncinya belum ada)."""
    penanda = {"scope": "__migrations__"}
    doc = await db.system_settings.find_one(penanda, {"_id": 0, PENANDA_TENGGAT_AKTIF: 1})
    if doc is None:
        await db.system_settings.update_one(penanda, {"$set": {PENANDA_TENGGAT_AKTIF: now_iso()}}, upsert=True)
    elif not doc.get(PENANDA_TENGGAT_AKTIF):
        await db.system_settings.update_one({**penanda, PENANDA_TENGGAT_AKTIF: {"$in": [None, ""]}},
                                            {"$set": {PENANDA_TENGGAT_AKTIF: now_iso()}})
    return await tenggat_aktif_sejak()


async def tenggat_aktif_sejak() -> str:
    """Waktu aktif tenggat LPJ (ISO); kosong bila belum pernah ditulis (PD tanpa potret lalu bertenggat dari hari ini)."""
    doc = await db.system_settings.find_one({"scope": "__migrations__"}, {"_id": 0, PENANDA_TENGGAT_AKTIF: 1}) or {}
    return doc.get(PENANDA_TENGGAT_AKTIF) or ""


def _tanggal_aman(nilai: Any) -> str:
    """Tanggal buku WIB dari tanggal/stempel waktu; "" bila kosong atau tidak terbaca."""
    try:
        return tanggal_buku(nilai) if nilai else ""
    except ValueError:
        return ""


def _hitung_tenggat(pd: Dict[str, Any], status_lpj: set, aktif_iso: str, hari: Optional[int],
                    hari_ini: str) -> Optional[Dict[str, Any]]:
    """Tenggat satu PD cair → `{jatuh_tempo, status, hari_lewat}` (None bila belum cair). Potret `lpj_jatuh_tempo` menang;
    tanpa potret = max(tanggal cair, tanggal fitur aktif) + `hari` (pengaturan PT saat ini)."""
    if pd.get("status") not in STATUS_BERTENGGAT:
        return None
    jt = _tanggal_aman(pd.get("lpj_jatuh_tempo"))
    if not jt:
        cair = _tanggal_aman((pd.get("disbursement") or {}).get("disbursed_at")) or hari_ini
        aktif = _tanggal_aman(aktif_iso) or hari_ini
        jt = (date.fromisoformat(max(cair, aktif)) + timedelta(days=int(hari or 0))).isoformat()
    if pd.get("status") == "settled" or status_lpj & set(LPJ_MEMENUHI_TENGGAT):
        return {"jatuh_tempo": jt, "status": "terpenuhi", "hari_lewat": 0}
    lewat = (date.fromisoformat(hari_ini) - date.fromisoformat(jt)).days
    if lewat > 0:
        return {"jatuh_tempo": jt, "status": "lewat", "hari_lewat": lewat}
    return {"jatuh_tempo": jt, "status": "jatuh_tempo_besok" if lewat == -1 else "aman", "hari_lewat": 0}


async def _tenggat_banyak(rows: List[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Tenggat banyak PD sekaligus (satu kueri LPJ, pengaturan per PT hanya untuk PD tanpa potret)."""
    cair = [r for r in rows if r.get("status") in STATUS_BERTENGGAT and r.get("id")]
    if not cair:
        return {}
    status_lpj: Dict[str, set] = {}
    async for s in db[STL_COLL].find({"cash_advance_id": {"$in": [r["id"] for r in cair]}},
                                     {"_id": 0, "cash_advance_id": 1, "status": 1}):
        status_lpj.setdefault(s.get("cash_advance_id") or "", set()).add(s.get("status") or "")
    hari: Dict[str, int] = {}
    for eid in {r.get("entity_id") or "" for r in cair if not _tanggal_aman(r.get("lpj_jatuh_tempo"))}:
        hari[eid] = await hari_tenggat_lpj(eid)
    aktif, hari_ini = await tenggat_aktif_sejak(), tanggal_buku()
    return {r["id"]: _hitung_tenggat(r, status_lpj.get(r["id"], set()), aktif, hari.get(r.get("entity_id") or ""),
                                     hari_ini) for r in cair}


async def tenggat(pd: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Tenggat LPJ satu PD → `{jatuh_tempo: YYYY-MM-DD, status: aman|jatuh_tempo_besok|lewat|terpenuhi, hari_lewat}`;
    None bila PD belum cair."""
    return (await _tenggat_banyak([pd])).get(pd.get("id") or "")


async def jatuh_tempo_lpj(entity_ids: List[str]) -> List[Dict[str, Any]]:
    """PD cair di PT dalam cakupan yang LPJ-nya lewat tenggat (antrean Meja Keuangan), urut jatuh tempo terlama.
    → `[{pd, pemegang, jatuh_tempo, hari_lewat}]`."""
    if not entity_ids:
        return []
    rows = [d async for d in db[CA_COLL].find({"entity_id": {"$in": list(entity_ids)}, "status": "disbursed"},
                                              {"_id": 0})]
    peta = await _tenggat_banyak(rows)
    out = []
    for pd in rows:
        t = peta.get(pd["id"]) or {}
        if t.get("status") == "lewat":
            out.append({"pd": pd, "pemegang": pemegang(pd), "jatuh_tempo": t["jatuh_tempo"],
                        "hari_lewat": t["hari_lewat"]})
    return sorted(out, key=lambda x: (x["jatuh_tempo"], str(x["pd"].get("number") or "")))


async def job_lpj_tenggat_reminder() -> Dict[str, Any]:
    """Penjadwal `lpj_tenggat_reminder` — PD cair yang LPJ-nya jatuh tempo besok (H-1) atau sudah lewat → pemberitahuan ke
    pembuat PD (`notification_service.notify_lpj_tenggat`), sekali per PD per jenis (aman dijalankan berulang). Gagal
    memberi tahu satu PD → hanya log."""
    from services import notification_service as ns
    rows = [d async for d in db[CA_COLL].find({"status": "disbursed"}, {"_id": 0})]
    peta = await _tenggat_banyak(rows)
    dibuat = gagal = 0
    for pd in rows:
        t = peta.get(pd["id"]) or {}
        jenis = {"jatuh_tempo_besok": "h-1", "lewat": "lewat"}.get(t.get("status") or "")
        if not jenis:
            continue
        try:
            dibuat += len(await ns.notify_lpj_tenggat(pd, jenis, tenggat=t))
        except Exception as exc:  # noqa: BLE001 — satu pemberitahuan gagal tidak menghentikan yang lain
            gagal += 1
            logger.warning("[lpj_tenggat] pemberitahuan %s %s gagal: %s", pd.get("number"), jenis, exc)
    detail = f"{dibuat} pemberitahuan tenggat LPJ" + (f", {gagal} gagal (lihat log)" if gagal else "")
    return {"created": dibuat, "scanned": len(rows), "detail": detail}


# ── Bidang turunan daftar & rincian ──────────────────────────────────────────────────────────────────────────────────
async def _hiasi(rows: List[Dict[str, Any]], actor: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tambah `pemegang`, `lpj_jatuh_tempo` + `tenggat_status` + `tenggat_hari_lewat` (None/0 bila belum cair), dan
    `bisa_ajukan` + `alasan_ajukan` (kalimat server yang sama dengan 409 ajukan) — tanpa menulis dokumen."""
    peta = await _tenggat_banyak(rows)
    alasan_per: Dict[tuple, str] = {}
    for r in rows:
        r["pemegang"] = pemegang(r)
        t = peta.get(r.get("id") or "")
        r["lpj_jatuh_tempo"] = t["jatuh_tempo"] if t else None
        r["tenggat_status"] = t["status"] if t else None
        r["tenggat_hari_lewat"] = t["hari_lewat"] if t else 0
        if r.get("status") in EDITABLE_STATUSES:
            # draf/ditolak tidak pernah terhitung terbuka, jadi hasilnya sama untuk semua draf satu pemegang di satu PT
            k = (kunci_pemegang(r), r.get("entity_id") or "")
            if k not in alasan_per:
                alasan_per[k] = await periksa_batas(r, actor, saat="ajukan")
            alasan = alasan_per[k]
        else:
            alasan = PESAN_BUKAN_DRAF
        r["bisa_ajukan"], r["alasan_ajukan"] = not alasan, alasan
    return rows


# ── Batalkan PD ──────────────────────────────────────────────────────────────────────────────────────────────────────
async def cancel_cash_advance(ca_id: str, alasan: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    """§7.9.4 — `POST /api/cash-advances/{id}/cancel {alasan}`: PD belum cair → `cancelled` (tidak lagi terhitung terbuka).
    Oleh pembuat PD atau pemegang `cash_advance.reject`; alasan ≥ 5 huruf; PD cair / berkas pencairan → 409. Klaim
    bersyarat status + tanpa `saga_lock` (pencairan yang sedang berjalan menang)."""
    doc = await get_cash_advance(ca_id, ctx)
    nomor, st = doc.get("number", ""), doc.get("status")
    teks = (alasan or "").strip()
    if st == "cancelled":
        raise HTTPException(status_code=409, detail=f"PD {nomor} sudah dibatalkan.")
    if st in STATUS_BERTENGGAT:
        raise HTTPException(status_code=409, detail=(f"PD {nomor} sudah dicairkan, jadi tidak bisa dibatalkan. Selesaikan "
                                                     "lewat LPJ dan kembalikan sisanya."))
    bisa = _status_bisa_batal()
    if st not in bisa:
        raise HTTPException(status_code=409, detail=f"PD {nomor} tidak bisa dibatalkan pada status ini.")
    if not _pembuat(doc, actor) and not await has_permission(actor, "cash_advance", "reject"):
        raise HTTPException(status_code=403, detail=(
            f"Hanya pembuat PD {nomor} ({doc.get('created_by') or 'pembuatnya'}) atau pemegang izin menolak pengajuan "
            "dana yang bisa membatalkannya."))
    if len(teks) < 5:
        raise HTTPException(status_code=400, detail=PESAN_ALASAN_BATAL)
    kas = await db.cash_transactions.find_one({"ref_type": "cash_advance", "ref_id": ca_id, "status": {"$ne": "void"}},
                                              {"_id": 0, "number": 1})
    if kas:
        raise HTTPException(status_code=409, detail=(
            f"PD {nomor} sudah punya kas pencairan {kas.get('number') or ''}, jadi tidak bisa dibatalkan. Ulangi "
            "pencairannya, lalu selesaikan lewat LPJ."))
    from services.atomic_claim import LOCK
    updated = await db[CA_COLL].find_one_and_update(
        {"id": ca_id, "status": {"$in": bisa}, LOCK: {"$exists": False}},
        {"$set": {"status": "cancelled", "cancelled_reason": teks[:500], "cancelled_from": st,
                  "cancelled_by": actor.get("name", ""), "cancelled_by_id": actor.get("id", ""),
                  "cancelled_at": now_iso(), "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        cur = await db[CA_COLL].find_one({"id": ca_id}, {"_id": 0, LOCK: 1}) or {}
        if cur.get(LOCK):
            raise HTTPException(status_code=409, detail=(f"PD {nomor} sedang dicairkan, jadi tidak bisa dibatalkan. Muat "
                                                         "ulang sebentar lagi."))
        raise HTTPException(status_code=409, detail=f"PD {nomor} berubah saat dibatalkan. Muat ulang.")
    await audit(actor.get("name", ""), "cash_advance_cancelled", "cash_advance", ca_id,
                {"number": nomor, "alasan": teks[:500], "dari": st}, reason=teks[:500])
    return safe_doc(updated)


# ═══ Settlement (Laporan Pertanggungjawaban) ══════════════════════════
#: PK-24 — status LPJ: draft → submitted → approved (disetujui, jurnal belum terbit) → posted_to_gl; ditolak = rejected
#: (pembuatnya bisa membuka lagi → draft). LPJ "aktif" (memblokir LPJ kedua atas PD yang sama) = selain ditolak.
STL_ACTIVE_STATUSES = ["draft", "submitted", "approved", "posted_to_gl"]
_STL_STATUS_KATA = {"draft": "masih draf", "submitted": "sudah diajukan", "approved": "sudah disetujui",
                    "posted_to_gl": "sudah disetujui dan dijurnal", "rejected": "sudah ditolak"}
#: PK-24 (FY-14) — pengaturan Pusat Pengaturan: LPJ wajib berlampiran bukti saat diajukan (bawaan mati, per PT).
K_WAJIB_LAMPIRAN = "finance.lpj_wajib_lampiran"
_RX_PERIODE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _periode(value: Optional[str]) -> str:
    """PK-24 — isian `periode` LPJ = bulan `YYYY-MM` (layar: pilihan bulan); kosong boleh. Teks bebas lama di LPJ yang
    sudah ada tidak ditulis ulang (hanya nilai baru yang diperiksa)."""
    v = (value or "").strip()
    if v and not _RX_PERIODE.match(v):
        raise HTTPException(status_code=400, detail="Periode LPJ diisi bulan, mis. 2026-07 (pilih dari daftar bulan).")
    return v


def _pesan_terkunci(doc: Dict[str, Any]) -> str:
    return (f"LPJ {doc.get('number', '')} sudah diajukan, jadi isinya tidak bisa diubah. Minta penyetuju menolaknya "
            "bila perlu diperbaiki.")


def _harus_draf(doc: Dict[str, Any]) -> None:
    """PK-24 (FY-14) — isi & lampiran LPJ hanya bisa diubah selagi draf."""
    if doc.get("status") != "draft":
        raise HTTPException(status_code=409, detail=_pesan_terkunci(doc))


def _harus_diajukan(doc: Dict[str, Any]) -> None:
    """PK-24 (FY-14) — setujui/tolak hanya untuk LPJ berstatus diajukan (dulu LPJ draf bisa langsung disetujui)."""
    st, nomor = doc.get("status"), doc.get("number", "")
    if st == "submitted":
        return
    if st == "draft":
        raise HTTPException(status_code=409, detail=f"LPJ {nomor} belum diajukan.")
    if st == "approved":
        raise HTTPException(status_code=409, detail=(
            f"LPJ {nomor} sudah disetujui; jurnalnya belum terbit dan diulang dari Keuangan › Posting Gagal."))
    raise HTTPException(status_code=409, detail=f"LPJ {nomor} {_STL_STATUS_KATA.get(st, st)}, jadi tidak menunggu "
                                                "persetujuan.")


def _pembuat(doc: Dict[str, Any], actor: Dict[str, Any]) -> bool:
    """Apakah aktor = pembuat LPJ: id bila tersimpan (KF-T6), nama untuk LPJ lama tanpa id."""
    if doc.get("created_by_id"):
        return doc["created_by_id"] == (actor or {}).get("id")
    return bool(doc.get("created_by")) and doc.get("created_by") == (actor or {}).get("name")


def _compute_settlement(expense_lines, total_pettycash: float) -> Dict[str, Any]:
    lines: List[Dict[str, Any]] = []
    cat_totals: Dict[str, float] = {}
    total = 0.0
    for ln in (expense_lines or []):
        d = ln.model_dump() if hasattr(ln, "model_dump") else dict(ln)
        amt = _r(d.get("amount"))
        d["amount"] = amt
        cat = d.get("category") or "petty_cash_lain"
        cat_totals[cat] = _r(cat_totals.get(cat, 0.0) + amt)
        total += amt
        lines.append(d)
    total = _r(total)
    return {
        "expense_lines": lines,
        "category_totals": cat_totals,
        "total_pengeluaran": total,
        "total_pettycash": _r(total_pettycash),
        "sisa_kurang_dana": _r(total_pettycash - total),
    }


async def create_settlement(payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    ca = await get_cash_advance(payload.cash_advance_id, ctx)
    # CX-05 — kebijakan: SATU pertanggungjawaban per PD. PD settled / sudah punya LPJ aktif ditolak.
    if ca["status"] != "disbursed":
        raise HTTPException(status_code=409, detail="Pertanggungjawaban hanya untuk PD berstatus dicairkan (belum selesai)")
    other = await db[STL_COLL].find_one(
        {"cash_advance_id": ca["id"], "status": {"$in": STL_ACTIVE_STATUSES}},
        {"_id": 0, "number": 1})
    if other:
        raise HTTPException(status_code=409, detail=f"PD ini sudah punya pertanggungjawaban {other['number']}")
    periode = _periode(payload.periode)
    calc = _compute_settlement(payload.expense_lines, ca.get("total_amount", 0))
    if not calc["expense_lines"]:
        raise HTTPException(status_code=400, detail="Minimal 1 baris pengeluaran")
    number = await next_doc_number(STL_COLL, "number", "STL-", entity_id=ca["entity_id"])
    doc = {
        "id": new_id("stl"),
        "number": number,
        "entity_id": ca["entity_id"],
        "cash_advance_id": ca["id"],
        "cash_advance_number": ca["number"],
        "divisi": (payload.divisi or ca.get("divisi", "")).strip(),
        "periode": periode,
        # Pelatihan 18 Nov — karyawan penanggung jawab LPJ (yang mengembalikan sisa / menerima reimburse) bawaannya
        # PEMOHON PD, bukan pengetik LPJ: Finance yang mengetik LPJ atas nama karyawan dulu tercatat sebagai "karyawan".
        # Kas & Bank 4 — pemohon = PEMEGANG uang PD (bawaan pembuatnya; karyawan HR bila Finance mengetik PD untuknya).
        "dibuat_oleh": (payload.dibuat_oleh or pemegang(ca)["nama"] or actor.get("name", "")).strip(),
        "disetujui_oleh": "",
        "catatan": (payload.catatan or "").strip(),
        "status": "draft",
        "journal_entry_id": "",
        "attachments": [],   # PK-24 — bukti pengeluaran (unggah/hapus hanya saat draf)
        "created_by": actor.get("name", ""),
        "created_by_id": actor.get("id", ""),   # KF-T6 — pemohon andal untuk kontrol dua orang
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **calc,
    }
    await db[STL_COLL].insert_one(doc)
    # PK-44 (IA-10) — LPJ lahir dari PD-nya: relasi dua arah untuk Jejak Dokumen (INV-REF-01 menuntutnya).
    from services import doc_refs_service as _refs
    await _refs.safe_link(("cash_settlement", doc["id"]), ("cash_advance", ca["id"]), "parent", note=_refs.LPJ_NOTE)
    await audit(actor.get("name", ""), "settlement_created", "cash_advance_settlement", doc["id"],
                {"number": number, "total": calc["total_pengeluaran"]})
    return safe_doc(doc)


def settlement_query(ctx: EntityContext, entity_id: Optional[str] = None, cash_advance_id: Optional[str] = None,
                     status: Optional[str] = None) -> Dict[str, Any]:
    """Kueri daftar LPJ yang boleh dilihat pemanggil (aturan PT satu tempat: daftar LPJ dan daftar kerja kas kecil)."""
    q = resolve_list_scope(STL_COLL, {}, ctx, entity_id)
    if cash_advance_id:
        q["cash_advance_id"] = cash_advance_id
    if status:
        q["status"] = status
    return q


async def list_settlements(ctx: EntityContext, entity_id: Optional[str] = None,
                           cash_advance_id: Optional[str] = None,
                           status: Optional[str] = None) -> List[Dict[str, Any]]:
    q = settlement_query(ctx, entity_id, cash_advance_id, status)
    return await db[STL_COLL].find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)


async def get_settlement(stl_id: str, ctx: EntityContext) -> Dict[str, Any]:
    doc = await db[STL_COLL].find_one({"id": stl_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Pertanggungjawaban tidak ditemukan")
    assert_active_entity_access(doc, STL_COLL, ctx)  # KN-B35
    return safe_doc(doc)


async def update_settlement(stl_id: str, payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_settlement(stl_id, ctx)
    _harus_draf(doc)   # PK-24 (FY-14) — dulu LPJ diajukan pun bisa diubah
    upd: Dict[str, Any] = {}
    for f in ["divisi", "catatan"]:
        v = getattr(payload, f, None)
        if v is not None:
            upd[f] = v.strip() if isinstance(v, str) else v
    if getattr(payload, "periode", None) is not None:
        upd["periode"] = _periode(payload.periode)
    if payload.expense_lines is not None:
        calc = _compute_settlement(payload.expense_lines, doc.get("total_pettycash", 0))
        if not calc["expense_lines"]:
            raise HTTPException(status_code=400, detail="Minimal 1 baris pengeluaran")
        upd.update(calc)
    upd["updated_at"] = now_iso()
    updated = await db[STL_COLL].find_one_and_update(
        {"id": stl_id, "status": "draft"}, {"$set": upd}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:   # diajukan di antara baca dan tulis
        raise HTTPException(status_code=409, detail=_pesan_terkunci(doc))
    await audit(actor.get("name", ""), "settlement_updated", "cash_advance_settlement", stl_id, upd)
    return safe_doc(updated)


async def _nilai_pengaturan(key: str, entity_id: str) -> Any:
    """Nilai Pusat Pengaturan untuk PT dokumen (berlapis global → PT). Galat baca = bawaan registry (`02` §2.2)."""
    from services.config_resolver import value_of
    try:
        return await value_of(key, {"entity_id": entity_id or ""})
    except Exception:  # noqa: BLE001
        import config_registry as _reg
        return _reg.require(key)["default"]


async def submit_settlement(stl_id: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_settlement(stl_id, ctx)
    if doc["status"] != "draft":
        kata = _STL_STATUS_KATA.get(doc["status"], doc["status"])
        raise HTTPException(status_code=409, detail=(
            f"Hanya LPJ draf yang bisa diajukan; LPJ {doc.get('number', '')} {kata}."))
    # PK-24 (FY-14) — bukti pengeluaran wajib bila pengaturan PT menyala (bawaan mati = perilaku lama).
    if bool(await _nilai_pengaturan(K_WAJIB_LAMPIRAN, doc["entity_id"])) and not (doc.get("attachments") or []):
        raise HTTPException(status_code=400, detail="Lampirkan minimal satu bukti pengeluaran sebelum mengajukan LPJ.")
    # PK-39 (K-12) — PERIKSA anggaran tiap kategori; mode tolak di sini hanya memperingatkan (persetujuannya yang ditahan).
    from services import budget_service as _bs
    try:
        budget_check = await _bs.enforce_budget(doc["entity_id"], _bs.settlement_budget_targets(doc), when="lpj_submit",
                                                date="", actor=actor, exclude_stl_id=stl_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    updated = await db[STL_COLL].find_one_and_update(
        {"id": stl_id, "status": "draft"},
        {"$set": {"status": "submitted", "budget_check": budget_check, "submitted_by": actor.get("name", ""),
                  "submitted_by_id": actor.get("id", ""), "submitted_at": now_iso(), "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(status_code=409, detail=f"LPJ {doc.get('number', '')} berubah saat diajukan. Muat ulang.")
    await audit(actor.get("name", ""), "settlement_submitted", "cash_advance_settlement", stl_id, {})
    return safe_doc(updated)


async def reopen_settlement(stl_id: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    """PK-24 — LPJ ditolak dibuka lagi (→ draf) oleh PEMBUATNYA untuk diperbaiki lalu diajukan ulang."""
    doc = await get_settlement(stl_id, ctx)
    nomor = doc.get("number", "")
    if doc.get("status") != "rejected":
        kata = _STL_STATUS_KATA.get(doc.get("status"), doc.get("status"))
        raise HTTPException(status_code=409, detail=f"Hanya LPJ yang ditolak yang bisa dibuka lagi; LPJ {nomor} {kata}.")
    if not _pembuat(doc, actor):
        pembuat = doc.get("created_by") or "pembuatnya"
        raise HTTPException(status_code=403, detail=(
            f"Hanya pembuat LPJ {nomor} ({pembuat}) yang bisa membukanya lagi untuk diperbaiki."))
    ca = await db[CA_COLL].find_one({"id": doc.get("cash_advance_id")}, {"_id": 0, "status": 1, "number": 1}) or {}
    if ca.get("status") != "disbursed":
        raise HTTPException(status_code=409, detail=(
            f"PD {ca.get('number') or doc.get('cash_advance_number', '')} sudah tidak menunggu pertanggungjawaban, jadi "
            f"LPJ {nomor} tidak bisa dibuka lagi."))
    other = await db[STL_COLL].find_one({"cash_advance_id": doc.get("cash_advance_id"), "id": {"$ne": stl_id},
                                         "status": {"$in": STL_ACTIVE_STATUSES}}, {"_id": 0, "number": 1})
    if other:
        raise HTTPException(status_code=409, detail=f"PD ini sudah punya pertanggungjawaban {other['number']}")
    updated = await db[STL_COLL].find_one_and_update(
        {"id": stl_id, "status": "rejected"},
        {"$set": {"status": "draft", "last_rejected_reason": doc.get("rejected_reason", ""), "rejected_reason": "",
                  "reopened_at": now_iso(), "reopened_by": actor.get("name", ""),
                  "reopened_by_id": actor.get("id", ""), "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(status_code=409, detail=f"LPJ {nomor} berubah saat dibuka. Muat ulang.")
    await audit(actor.get("name", ""), "settlement_reopened", "cash_advance_settlement", stl_id, {})
    return safe_doc(updated)


# ── PK-24 — lampiran bukti pengeluaran (pola lampiran retur; penyimpanan `services/storage_service`) ──────────────────
def _lampiran_aktif(doc: Dict[str, Any], att_id: str) -> Dict[str, Any]:
    att = next((a for a in (doc.get("attachments") or []) if a.get("id") == att_id), None)
    if not att:
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    return att


async def add_settlement_attachment(stl_id: str, filename: str, content_type: str, data: bytes,
                                    ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import storage_service as storage
    doc = await get_settlement(stl_id, ctx)
    _harus_draf(doc)
    try:
        ct = storage.validate_upload(filename, content_type, len(data), data[:16])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    att_id = new_id("att")
    path = f"cash_advance_settlements/{stl_id}/{att_id}.{storage.ext_of(filename)}"
    await storage.put_object(path, data, ct)
    att = {"id": att_id, "filename": filename or "lampiran", "content_type": ct, "size": len(data), "path": path,
           "uploaded_by": actor.get("name", ""), "uploaded_by_id": actor.get("id", ""), "uploaded_at": now_iso()}
    res = await db[STL_COLL].update_one({"id": stl_id, "status": "draft"},
                                        {"$push": {"attachments": att}, "$set": {"updated_at": now_iso()}})
    if not res.modified_count:   # diajukan di antara baca dan tulis — berkas yang terlanjur tersimpan dibuang
        try:
            await storage.delete_object(path)
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(status_code=409, detail=_pesan_terkunci(doc))
    await audit(actor.get("name", ""), "settlement_attachment_added", "cash_advance_settlement", stl_id,
                {"attachment_id": att_id, "filename": att["filename"]})
    return att


async def get_settlement_attachment(stl_id: str, att_id: str, ctx: EntityContext):
    """→ (lampiran, isi berkas). 404 bila lampiran / berkasnya tidak ada."""
    from services import storage_service as storage
    att = _lampiran_aktif(await get_settlement(stl_id, ctx), att_id)
    try:
        data, _ = await storage.get_object(att["path"])
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Berkas lampiran tidak ditemukan di penyimpanan.") from exc
    return att, data


async def delete_settlement_attachment(stl_id: str, att_id: str, ctx: EntityContext,
                                       actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import storage_service as storage
    doc = await get_settlement(stl_id, ctx)
    _harus_draf(doc)
    att = _lampiran_aktif(doc, att_id)
    res = await db[STL_COLL].update_one({"id": stl_id, "status": "draft"},
                                        {"$pull": {"attachments": {"id": att_id}}, "$set": {"updated_at": now_iso()}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail=_pesan_terkunci(doc))
    try:
        await storage.delete_object(att.get("path", ""))
    except Exception:  # noqa: BLE001 — berkas fisik yang gagal dihapus tidak membatalkan penghapusan di dokumen
        pass
    await audit(actor.get("name", ""), "settlement_attachment_deleted", "cash_advance_settlement", stl_id,
                {"attachment_id": att_id, "filename": att.get("filename", "")})
    return {"ok": True}


# ── PK-24 — setujui LPJ: PERIKSA → NIAT (PD diklaim + LPJ `approved`) → JURNAL (`post_durable`) → SELESAI ────────────
async def _settlement_lines(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Baris beban per kategori dengan akun PT LPJ (FY-13); kategori tanpa akun → akun cadangan."""
    cat_map = await _category_account_map(doc.get("entity_id") or "")
    return [{"account_code": cat_map.get(cat, FALLBACK_ACCOUNT), "amount": _r(amt), "desc": f"Beban {cat}"}
            for cat, amt in (doc.get("category_totals") or {}).items() if _r(amt) > 0]


def settlement_journal_date(doc: Dict[str, Any]) -> str:
    """PK-22 (FY-02, K-13) — tanggal buku jurnal LPJ = tanggal pengeluaran TERAKHIR di `expense_lines[].date`; tidak ada
    yang bertanggal → tanggal LPJ diajukan (`submitted_at`, lalu `created_at`). Dipakai
    langkah PERIKSA, anggaran PK-39, dan jurnal (`_post_and_finish`, juga ulang dari panel PK-24). `periode` LPJ teks bebas, jadi tidak
    dipakai (ASUMSI unit). Dulu: hari LPJ disetujui."""
    from services.book_date import tanggal_buku
    tanggal = []
    for ln in doc.get("expense_lines") or []:
        try:
            if str((ln or {}).get("date") or "").strip():
                tanggal.append(tanggal_buku(str(ln["date"]).strip()))
        except ValueError:
            continue
    if tanggal:
        return max(tanggal)
    for f in ("submitted_at", "created_at"):
        if doc.get(f):
            try:
                return tanggal_buku(doc[f])
            except ValueError:
                continue
    return tanggal_buku()


async def approve_settlement(stl_id: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_settlement(stl_id, ctx)
    _harus_diajukan(doc)   # PK-24 (FY-14) — LPJ draf tidak bisa langsung disetujui
    # KF-T6 — pemohon ≠ penyetuju dari `kontrol.lpj_uang_muka.*` (bawaan satu orang).
    from services import dual_control as _dc
    await _dc.tolak_bila_pelaku_sama("lpj_uang_muka", doc, actor, doc.get("entity_id", ""),
                                     nominal=float(doc.get("total_pengeluaran") or 0),
                                     pengaju=[doc.get("created_by_id"), doc.get("created_by")])
    if not await _settlement_lines(doc):
        raise HTTPException(status_code=400, detail="Tidak ada pengeluaran untuk diposting")
    tgl_jurnal = settlement_journal_date(doc)   # PK-22 — tanggal pengeluaran terakhir, bukan hari disetujui
    try:
        await gl_service.preflight_posting(doc["entity_id"], tgl_jurnal)
    except gl_service.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # PK-39 (K-12) — PERIKSA anggaran tiap kategori (bulan buku jurnal LPJ) sebelum PD induk diklaim. PK-22 — bulan buku
    # jurnal LPJ kini tanggal pengeluaran terakhir (dulu hari ini), jadi anggaran yang diperiksa = bulan jurnalnya.
    from services import budget_service as _bs
    try:
        budget_check = await _bs.enforce_budget(doc["entity_id"], _bs.settlement_budget_targets(doc),
                                                when="lpj_approve", date=tgl_jurnal, actor=actor,
                                                exclude_stl_id=stl_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # NIAT (1) CX-05 — tutup PD induk atomik LEBIH DULU (settling_stl_id): LPJ kedua tidak dapat memposting.
    parent = await db[CA_COLL].find_one_and_update(
        {"id": doc["cash_advance_id"], "status": "disbursed",
         "$or": [{"settling_stl_id": {"$exists": False}}, {"settling_stl_id": stl_id}]},
        {"$set": {"settling_stl_id": stl_id, "updated_at": now_iso()}}, projection={"_id": 0})
    if not parent:
        raise HTTPException(status_code=409, detail="PD induk sudah dipertanggungjawabkan / sedang diproses LPJ lain")
    # NIAT (2) — LPJ `submitted → approved` dengan jurnal `pending` (bersyarat nilai lama: satu penyetuju menang).
    approved = await db[STL_COLL].find_one_and_update(
        {"id": stl_id, "status": "submitted"},
        {"$set": {"status": "approved", "gl_status": "pending", "gl_error": "", "budget_check": budget_check,
                  "disetujui_oleh": actor.get("name", ""), "approved_by_id": actor.get("id", ""),
                  "approved_at": now_iso(), "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not approved:
        await db[CA_COLL].update_one({"id": doc["cash_advance_id"], "settling_stl_id": stl_id, "status": "disbursed"},
                                     {"$unset": {"settling_stl_id": ""}})
        raise HTTPException(status_code=409, detail=f"LPJ {doc.get('number', '')} berubah saat disetujui. Muat ulang.")
    await audit(actor.get("name", ""), "settlement_approved", "cash_advance_settlement", stl_id,
                {"total": doc.get("total_pengeluaran")})
    return await _post_and_finish(approved, actor)


async def _post_and_finish(doc: Dict[str, Any], actor: Dict[str, Any], *, raise_on_fail: bool = False) -> Dict[str, Any]:
    """JURNAL lewat pintu tahan-gagal → SELESAI hanya bila jurnal `posted`. Jurnal gagal: LPJ tetap `approved` +
    `gl_status="failed"` (panel Posting Gagal, jenis `petty_cash_settlement`); PD induk tetap terklaim LPJ ini."""
    stl_id = doc["id"]
    parent = await db[CA_COLL].find_one({"id": doc.get("cash_advance_id")}, {"_id": 0}) or {}
    advance = float(parent.get("total_amount") or doc.get("total_pettycash") or 0)
    cat_lines = await _settlement_lines(doc)
    if not cat_lines:   # tidak terjadi lewat `approve_settlement` (diperiksa lebih dulu); penjaga untuk data lama
        if raise_on_fail:
            raise RuntimeError("Tidak ada pengeluaran untuk diposting")
        return safe_doc(await db[STL_COLL].find_one({"id": stl_id}, {"_id": 0}))
    res = await gl_service.post_durable(
        STL_COLL, stl_id, lambda: gl_service.post_petty_cash_settlement(
            settlement_id=stl_id, entity_id=doc["entity_id"], category_lines=cat_lines,
            actor_name=actor.get("name", ""), date=settlement_journal_date(doc),   # PK-22 (FY-02)
            label=f"{doc['number']} · {doc.get('divisi', '')}".strip(), advance_amount=advance),
        source_type="petty_cash_settlement", source_id=stl_id, raise_on_fail=raise_on_fail)
    if res["gl_status"] != "posted":
        return safe_doc(await db[STL_COLL].find_one({"id": stl_id}, {"_id": 0}))
    je = res.get("journal") or await db.journal_entries.find_one({"id": res["journal_entry_id"]},
                                                                 {"_id": 0, "id": 1, "number": 1}) or {}
    total = float(doc.get("total_pengeluaran") or 0)
    excess = _r(max(total - advance, 0.0))
    remainder = _r(max(advance - total, 0.0))
    updated = await db[STL_COLL].find_one_and_update(
        {"id": stl_id, "status": "approved"},
        {"$set": {"status": "posted_to_gl", "journal_entry_id": je.get("id", ""),
                  "journal_entry_number": je.get("number", ""), "posted_at": now_iso(),
                  # CX-05 — kelebihan pengeluaran = Hutang Reimburse Karyawan (2-1650) yang harus dibayar
                  "hutang_reimburse": {"amount": excess, "status": "open" if excess > 0 else "none",
                                       "cash_txn_id": "", "paid_at": ""},
                  # PK-24 (SL-09) — sisa uang muka yang harus kembali; ditutup oleh `return_remainder`
                  "sisa_dikembalikan": {"amount": remainder, "status": "open" if remainder > 0 else "none",
                                        "cash_txn_id": "", "cash_txn_number": "", "journal_entry_number": "",
                                        "returned_at": "", "returned_by": ""},
                  "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:   # sudah diselesaikan pemanggil lain (ulang bersamaan)
        return safe_doc(await db[STL_COLL].find_one({"id": stl_id}, {"_id": 0}))
    # Tandai PD induk sebagai settled
    await db[CA_COLL].update_one({"id": doc["cash_advance_id"], "settling_stl_id": stl_id},
                                 {"$set": {"status": "settled", "settled_by_stl_id": stl_id,
                                           "updated_at": now_iso()}})
    await audit(actor.get("name", ""), "settlement_posted", "cash_advance_settlement", stl_id,
                {"je_id": je.get("id"), "total": doc.get("total_pengeluaran")})
    return safe_doc(updated)


async def repost_settlement(stl_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """PK-24 — jalur ulang panel Posting Gagal: meneruskan LPJ `approved` dari langkah JURNAL (tepat satu jurnal)."""
    doc = await db[STL_COLL].find_one({"id": stl_id}, {"_id": 0})
    if not doc or doc.get("status") != "approved":
        raise RuntimeError("LPJ ini tidak menunggu jurnal.")
    return await _post_and_finish(doc, actor, raise_on_fail=True)


async def pay_reimburse(stl_id: str, payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    """CX-05 — bayar kelebihan LPJ ke karyawan: kas keluar Dr 2-1650 / Cr Kas, menutup saldo hutang
    reimburse LPJ ini. Klaim atomik + resume (kas dari percobaan gagal dipakai ulang)."""
    doc = await get_settlement(stl_id, ctx)
    hr = doc.get("hutang_reimburse") or {}
    if doc.get("status") != "posted_to_gl" or hr.get("status") != "open" or float(hr.get("amount") or 0) <= 0:
        raise HTTPException(status_code=409, detail="LPJ ini tidak punya hutang reimburse terbuka")
    cash_type = getattr(payload, "cash_type", "") if getattr(payload, "cash_type", "") in ("kas_kecil", "kas_besar") else "kas_besar"
    txn_date = getattr(payload, "txn_date", None) or now_iso()
    try:
        await gl_service.preflight_posting(doc["entity_id"], txn_date)
    except gl_service.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # PK-20 — rekening sumber (isian baru `account_id`; kosong = rekening tunggal PT jenis kas itu) diperiksa SEBELUM klaim.
    from services import cash_ledger
    rek = await cash_ledger.periksa_rekening(doc["entity_id"], getattr(payload, "account_id", "") or "", cash_type)
    from services import atomic_claim as _saga
    await _saga.claim(STL_COLL, stl_id, "reimburse_pay", precondition={"hutang_reimburse.status": "open"},
                      actor=actor.get("name", ""))
    try:
        try:   # PK-20 — rujukan (reimburse_payable, id LPJ) memberi id kas tetap: ulang memakai kas yang sama
            txn = await cash_ledger.create_cash(
                entity_id=doc["entity_id"], direction="out", amount=_r(hr["amount"]), ref_type="reimburse_payable",
                ref_id=stl_id, account_id=rek["account_id"], cash_type=cash_type, txn_date=txn_date,
                category="reimburse karyawan", description=f"Bayar kelebihan LPJ {doc.get('number', '')}",
                actor=actor.get("name", ""))
        except cash_ledger.CashPostingError as exc:
            raise HTTPException(status_code=409, detail=(
                f"Kas {exc.txn.get('number', '')} tercatat tetapi jurnal gagal: {exc.error}. Ulangi untuk melanjutkan."))
        je = await db.journal_entries.find_one(
            {"source_type": "cash_transaction", "source_id": txn["id"], "status": {"$ne": "void"}},
            {"_id": 0, "id": 1, "number": 1})
        updated = await db[STL_COLL].find_one_and_update(
            {"id": stl_id},
            _saga.finish_set({"hutang_reimburse.status": "paid", "hutang_reimburse.cash_txn_id": txn["id"],
                              "hutang_reimburse.cash_txn_number": txn["number"],
                              "hutang_reimburse.journal_entry_number": (je or {}).get("number", ""),
                              "hutang_reimburse.account_id": txn.get("account_id", ""),
                              "hutang_reimburse.paid_at": now_iso(), "hutang_reimburse.paid_by": actor.get("name", ""),
                              "hutang_reimburse.paid_by_id": actor.get("id", ""),
                              "updated_at": now_iso()}),
            projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    except Exception:
        await _saga.release(STL_COLL, stl_id)
        raise
    await audit(actor.get("name", ""), "reimburse_paid", "cash_advance_settlement", stl_id,
                {"amount": hr["amount"], "cash_txn_id": txn["id"]})
    return safe_doc(updated)


def _pesan_tanpa_sisa(doc: Dict[str, Any]) -> str:
    return f"LPJ {doc.get('number', '')} tidak punya sisa uang muka yang belum dikembalikan."


async def return_remainder(stl_id: str, payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    """PK-24 (SL-09) — terima pengembalian SISA uang muka (uang muka − pengeluaran) dari karyawan: satu kas MASUK
    Dr Kas / Cr uang muka karyawan (pemetaan `kas_bank.uang_muka_karyawan`, bawaan 1-1400) → saldo uang muka PD = 0.

    PERIKSA (status `open`, periode, rekening) → NIAT `open → returning` (bersyarat: satu penerima menang) → EFEK +
    JURNAL lewat pembuat kas `cash_ledger.create_cash` (rujukan `cash_advance_return`/id LPJ = id kas tetap) →
    `returned`. Jurnal gagal → kembali `open`; kas `failed` tertinggal dan DIPAKAI ULANG saat diulang."""
    doc = await get_settlement(stl_id, ctx)
    sr = doc.get("sisa_dikembalikan") or {}
    amount = _r(sr.get("amount"))
    if doc.get("status") != "posted_to_gl" or amount <= 0 or sr.get("status") not in ("open", "returning"):
        raise HTTPException(status_code=409, detail=_pesan_tanpa_sisa(doc))
    if sr.get("status") == "returning":
        raise HTTPException(status_code=409, detail=(
            f"Pengembalian sisa LPJ {doc.get('number', '')} sedang diproses. Muat ulang sebentar lagi."))
    cash_type = getattr(payload, "cash_type", "") or ""
    cash_type = cash_type if cash_type in ("kas_kecil", "kas_besar") else "kas_kecil"
    txn_date = getattr(payload, "txn_date", None) or now_iso()
    entity_id = doc["entity_id"]
    try:
        await gl_service.preflight_posting(entity_id, txn_date)
    except gl_service.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    from services import cash_ledger
    from services import gl_mapping_service as _glm
    rek = await cash_ledger.periksa_rekening(entity_id, getattr(payload, "account_id", "") or "", cash_type)
    lawan = await _glm.account_for("kas_bank.uang_muka_karyawan", entity_id)
    claimed = await db[STL_COLL].find_one_and_update(
        {"id": stl_id, "status": "posted_to_gl", "sisa_dikembalikan.status": "open"},
        {"$set": {"sisa_dikembalikan.status": "returning", "sisa_dikembalikan.returning_at": now_iso(),
                  "sisa_dikembalikan.returning_by": actor.get("name", ""), "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not claimed:
        cur = (await db[STL_COLL].find_one({"id": stl_id}, {"_id": 0, "sisa_dikembalikan": 1}) or {}).get(
            "sisa_dikembalikan") or {}
        if cur.get("status") == "returning":
            raise HTTPException(status_code=409, detail=(
                f"Pengembalian sisa LPJ {doc.get('number', '')} sedang diproses. Muat ulang sebentar lagi."))
        raise HTTPException(status_code=409, detail=_pesan_tanpa_sisa(doc))

    async def _buka_lagi(extra: Optional[Dict[str, Any]] = None):
        await db[STL_COLL].update_one({"id": stl_id, "sisa_dikembalikan.status": "returning"},
                                      {"$set": {"sisa_dikembalikan.status": "open", **(extra or {}),
                                                "updated_at": now_iso()}})

    karyawan = (doc.get("dibuat_oleh") or doc.get("created_by") or "karyawan").strip()
    try:
        txn = await cash_ledger.create_cash(
            entity_id=entity_id, direction="in", amount=amount, ref_type="cash_advance_return", ref_id=stl_id,
            account_id=rek["account_id"], cash_type=rek["cash_type"], txn_date=txn_date,
            category="pengembalian uang muka", contra_account_code=lawan,
            description=f"Pengembalian sisa uang muka {doc.get('number', '')} — {karyawan}",
            actor=actor.get("name", ""))
    except cash_ledger.CashPostingError as exc:
        await _buka_lagi({"sisa_dikembalikan.cash_txn_id": exc.txn.get("id", ""),
                          "sisa_dikembalikan.last_error": str(exc.error)[:300]})
        raise HTTPException(status_code=409, detail=(
            f"Kas {exc.txn.get('number', '')} tercatat tetapi jurnal gagal: {exc.error}. Ulangi untuk melanjutkan "
            "(tanpa kas ganda).")) from exc
    except Exception:
        await _buka_lagi()
        raise
    je = await db.journal_entries.find_one(
        {"source_type": "cash_transaction", "source_id": txn["id"], "status": {"$ne": "void"}},
        {"_id": 0, "id": 1, "number": 1}) or {}
    updated = await db[STL_COLL].find_one_and_update(
        {"id": stl_id, "sisa_dikembalikan.status": "returning"},
        {"$set": {"sisa_dikembalikan.status": "returned", "sisa_dikembalikan.cash_txn_id": txn["id"],
                  "sisa_dikembalikan.cash_txn_number": txn.get("number", ""),
                  "sisa_dikembalikan.journal_entry_number": je.get("number", ""),
                  "sisa_dikembalikan.account_id": txn.get("account_id", ""),
                  "sisa_dikembalikan.last_error": "",
                  "sisa_dikembalikan.returned_at": now_iso(), "sisa_dikembalikan.returned_by": actor.get("name", ""),
                  "sisa_dikembalikan.returned_by_id": actor.get("id", ""), "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "settlement_remainder_returned", "cash_advance_settlement", stl_id,
                {"amount": amount, "cash_txn_id": txn["id"]})
    return safe_doc(updated or await db[STL_COLL].find_one({"id": stl_id}, {"_id": 0}))


REIMBURSE_BUCKETS = (("0-7", 7), ("8-14", 14), ("15-30", 30), (">30", None))


def _reimburse_bucket(days: int) -> str:
    for label, upper in REIMBURSE_BUCKETS:
        if upper is None or days <= upper:
            return label
    return ">30"


async def reimburse_payables(ctx: EntityContext, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Laporan Hutang Reimburse (2-1650) terbuka per karyawan + umur sejak LPJ disetujui."""
    from datetime import datetime, timezone
    q = resolve_list_scope(STL_COLL, {"status": "posted_to_gl", "hutang_reimburse.status": "open"}, ctx, entity_id)
    now = datetime.now(timezone.utc)
    blank = {label: 0.0 for label, _ in REIMBURSE_BUCKETS}
    by_emp: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    async for d in db[STL_COLL].find(q, {"_id": 0}):
        amt = _r((d.get("hutang_reimburse") or {}).get("amount") or 0)
        if amt <= 0:
            continue
        ref = d.get("approved_at") or d.get("updated_at") or d.get("created_at") or ""
        try:
            dt = datetime.fromisoformat(str(ref).replace("Z", "+00:00"))
            days = max((now - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))).days, 0)
        except ValueError:
            days = 0
        bucket = _reimburse_bucket(days)
        emp = (d.get("dibuat_oleh") or d.get("created_by") or "—").strip() or "—"
        e = by_emp.setdefault(emp, {"employee": emp, "outstanding": 0.0, "count": 0, "oldest_days": 0,
                                     "aging": dict(blank)})
        e["outstanding"] = _r(e["outstanding"] + amt)
        e["count"] += 1
        e["oldest_days"] = max(e["oldest_days"], days)
        e["aging"][bucket] = _r(e["aging"][bucket] + amt)
        rows.append({"id": d["id"], "number": d.get("number"), "employee": emp,
                     "cash_advance_number": d.get("cash_advance_number", ""), "entity_id": d.get("entity_id"),
                     "divisi": d.get("divisi", ""), "approved_at": d.get("approved_at", ""),
                     "amount": amt, "days": days, "bucket": bucket})
    aging = dict(blank)
    for r in rows:
        aging[r["bucket"]] = _r(aging[r["bucket"]] + r["amount"])
    rows.sort(key=lambda r: (-r["days"], -r["amount"]))
    return {"total_outstanding": _r(sum(r["amount"] for r in rows)), "aging": aging,
            "buckets": [label for label, _ in REIMBURSE_BUCKETS],
            "by_employee": sorted(by_emp.values(), key=lambda e: (-e["oldest_days"], -e["outstanding"])),
            "items": rows}


async def reject_settlement(stl_id: str, reason: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_settlement(stl_id, ctx)
    _harus_diajukan(doc)   # PK-24 (FY-14) — hanya LPJ diajukan yang bisa ditolak
    updated = await db[STL_COLL].find_one_and_update(
        {"id": stl_id, "status": "submitted"},
        {"$set": {"status": "rejected", "rejected_reason": (reason or "").strip(), "rejected_by": actor.get("name", ""),
                  "rejected_by_id": actor.get("id", ""), "rejected_at": now_iso(), "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(status_code=409, detail=f"LPJ {doc.get('number', '')} berubah saat ditolak. Muat ulang.")
    await audit(actor.get("name", ""), "settlement_rejected", "cash_advance_settlement", stl_id,
                {"reason": reason})
    return safe_doc(updated)


# ═══ MN-T2 — daftar kerja Kas Kecil (satu baris per PD, tahap turunan) ═════════════════════════════════════════════
#: Tahap layar Kas Kecil, diturunkan dari status PD dan LPJ-nya (tanpa field baru):
#:   diajukan = PD belum dicairkan (draf, menunggu tiap jenjang, disetujui, ditolak);
#:   dicairkan = PD dicairkan, LPJ belum diajukan (tanpa LPJ, draf, atau ditolak);
#:   dipertanggungjawabkan = LPJ diajukan/disetujui (jurnal belum terbit), atau sudah dijurnal tetapi sisa uang muka
#:     belum kembali / hutang reimburse belum dibayar;
#:   selesai = LPJ dijurnal dan tidak ada sisa di kedua arah, atau PD dibatalkan (Kas & Bank 4 — tidak lagi menunggu).
WORKLIST_STAGES = ("diajukan", "dicairkan", "dipertanggungjawabkan", "selesai")
_EPS = 0.005


def _lpj_terpilih(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """LPJ yang mewakili PD: yang aktif (bukan ditolak; paling banyak satu per PD), selain itu yang ditolak terbaru."""
    aktif = [d for d in rows if d.get("status") in STL_ACTIVE_STATUSES]
    pilih = aktif or rows
    return max(pilih, key=lambda d: str(d.get("created_at") or "")) if pilih else None


def _sisa_lpj(stl: Dict[str, Any], advance: float) -> tuple:
    """(sisa kembali, hutang reimburse) yang belum tuntas. LPJ dijurnal: dari catatan sisa/hutang yang masih terbuka;
    LPJ draf/diajukan/disetujui: perkiraan dari pengeluaran vs uang muka (angka final ditetapkan saat dijurnal)."""
    st = stl.get("status")
    if st == "posted_to_gl":
        sr, hr = stl.get("sisa_dikembalikan") or {}, stl.get("hutang_reimburse") or {}
        kembali = _r(sr.get("amount")) if sr.get("status") in ("open", "returning") else 0.0
        reimburse = _r(hr.get("amount")) if hr.get("status") == "open" else 0.0
        return kembali, reimburse
    if st in ("draft", "submitted", "approved"):
        spent = _r(stl.get("total_pengeluaran"))
        return _r(max(advance - spent, 0.0)), _r(max(spent - advance, 0.0))
    return 0.0, 0.0


def worklist_stage(ca: Dict[str, Any], stl: Optional[Dict[str, Any]]) -> str:
    """Tahap Kas Kecil satu PD (lihat `WORKLIST_STAGES`)."""
    if ca.get("status") == "cancelled":
        return "selesai"
    if ca.get("status") not in ("disbursed", "settled"):
        return "diajukan"
    if not stl:
        return "selesai" if ca.get("status") == "settled" else "dicairkan"
    st = stl.get("status")
    if st in ("draft", "rejected"):
        return "dicairkan"
    if st in ("submitted", "approved"):
        return "dipertanggungjawabkan"
    kembali, reimburse = _sisa_lpj(stl, _r(ca.get("total_amount")))
    return "dipertanggungjawabkan" if kembali > _EPS or reimburse > _EPS else "selesai"


def _baris_kerja(ca: Dict[str, Any], stl: Optional[Dict[str, Any]], lihat_reimburse: bool,
                tenggat_pd: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    advance = _r(ca.get("total_amount"))
    lpj = None
    if stl:
        kembali, reimburse = _sisa_lpj(stl, advance)
        lpj = {"id": stl.get("id"), "number": stl.get("number", ""), "status": stl.get("status", ""),
               "spent": _r(stl.get("total_pengeluaran")), "refund_due": kembali,
               "reimburse_due": reimburse if lihat_reimburse else None}
    terbaru = max(str(ca.get("updated_at") or ca.get("created_at") or ""),
                  str((stl or {}).get("updated_at") or (stl or {}).get("created_at") or ""))
    return {"id": ca.get("id"), "number": ca.get("number", ""), "entity_id": ca.get("entity_id", ""),
            "requester": ca.get("created_by", ""), "purpose": ca.get("kegiatan", ""), "divisi": ca.get("divisi", ""),
            "amount": advance, "stage": worklist_stage(ca, stl), "status": ca.get("status", ""),
            "settlement": lpj, "updated_at": terbaru,
            # Kas & Bank 4 — pemegang uang + lencana tenggat LPJ (None/0 bila PD belum cair)
            "pemegang": pemegang(ca), "lpj_jatuh_tempo": (tenggat_pd or {}).get("jatuh_tempo"),
            "tenggat_status": (tenggat_pd or {}).get("status"),
            "tenggat_hari_lewat": (tenggat_pd or {}).get("hari_lewat", 0)}


async def petty_cash_worklist(ctx: EntityContext, *, entity_id: Optional[str] = None, stage: str = "", q: str = "",
                              page: int = 1, page_size: int = 25, lihat_pd: bool = True,
                              lihat_reimburse: bool = False) -> Dict[str, Any]:
    """MN-T2 — `GET /api/petty-cash/worklist`: satu baris per PD dengan LPJ-nya, tahap turunan, jumlah per tahap.

    Cakupan = kueri daftar PD dan LPJ yang sama dengan `GET /api/cash-advances` dan `/api/cash-advance-settlements`
    (aturan PT tidak disalin). Dibaca dengan kursor (tanpa batas 1000 baris); halaman dipotong di sini dengan `total`.
    `lihat_pd` False (pemanggil hanya ber-`cash_settlement.view`) → hanya PD yang punya LPJ terlihat. `lihat_reimburse`
    False → `settlement.reimburse_due` = None."""
    stage = (stage or "").strip()
    if stage and stage not in WORKLIST_STAGES:
        raise HTTPException(status_code=400, detail="Tahap tidak dikenal.")
    per_pd: Dict[str, List[Dict[str, Any]]] = {}
    async for d in db[STL_COLL].find(settlement_query(ctx, entity_id), {"_id": 0}):
        per_pd.setdefault(d.get("cash_advance_id") or "", []).append(d)
    cari = (q or "").strip().lower()
    terpilih: List[tuple] = []
    async for ca in db[CA_COLL].find(cash_advance_query(ctx, entity_id), {"_id": 0}):
        stl = _lpj_terpilih(per_pd.get(ca.get("id") or "", []))
        if not lihat_pd and not stl:
            continue
        if cari and not any(cari in str(v or "").lower() for v in (
                ca.get("number"), ca.get("kegiatan"), ca.get("divisi"), ca.get("created_by"), (stl or {}).get("number"),
                pemegang(ca)["nama"])):
            continue
        terpilih.append((ca, stl))
    peta = await _tenggat_banyak([ca for ca, _ in terpilih])
    rows: List[Dict[str, Any]] = [_baris_kerja(ca, stl, lihat_reimburse, peta.get(ca.get("id") or ""))
                                  for ca, stl in terpilih]
    counts = {s: 0 for s in WORKLIST_STAGES}
    for r in rows:
        counts[r["stage"]] += 1
    pilih = [r for r in rows if not stage or r["stage"] == stage]
    pilih.sort(key=lambda r: (r["updated_at"], r["number"]), reverse=True)
    page, page_size = max(int(page or 1), 1), min(max(int(page_size or 25), 1), 100)
    awal = (page - 1) * page_size
    return {"items": pilih[awal:awal + page_size], "total": len(pilih), "page": page, "page_size": page_size,
            "stage_counts": counts}
