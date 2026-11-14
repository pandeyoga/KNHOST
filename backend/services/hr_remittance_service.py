"""PK-22 (FY-07) — setoran kewajiban gaji: hutang BPJS (2-1700) dan PPh 21 (2-1800) turun lewat dokumen setoran.

Koleksi `hr_statutory_remittances` (`strm_`, nomor `STR-` per PT). Satu setoran = satu kas keluar ber-
`ref_type="statutory_remittance"` lewat pembuat kas (`cash_ledger.create_cash`, PK-20) dengan lawan akun pemetaan
`sdm.hutang_bpjs` / `sdm.hutang_pph21` PT itu → jurnal kas tahan-gagal Dr hutang / Cr kas (`02_STANDAR.md` §1):

  PERIKSA  jenis · masa · nominal > 0 · nominal ≤ sisa kewajiban masa itu · periode tanggal setor terbuka · rekening
  NIAT     dokumen `pending` ber-id tetap (dari kunci idempotensi bila ada)
  EFEK+JURNAL  kas keluar (id kas tetap dari id setoran) → jurnal kas lewat `post_cash_durable`
  SELESAI  `done` + `cash_txn_id` + `journal_entry_id`
  ULANG    kirim ulang kunci yang sama / ulang jurnal kas dari panel Posting Gagal → `finish_remittance`

Kewajiban masa = Σ dari proses gaji `posted`/`paid` PT itu masa itu: BPJS = `totals.bpjs_emp + totals.bpjs_er`,
PPh 21 = `totals.pph21`. Disetor = Σ setoran masa itu (termasuk yang masih `pending`, supaya dua setoran bersamaan
tidak melampaui sisa). Denda keterlambatan bukan dokumen ini (ASUMSI unit).
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict

from core_utils import new_id, next_doc_number, now_iso, rupiah, safe_doc
from db import db

COLL = "hr_statutory_remittances"
KIND_LABEL = {"bpjs": "BPJS", "pph21": "PPh 21"}
MAP_KEY = {"bpjs": "sdm.hutang_bpjs", "pph21": "sdm.hutang_pph21"}
REF_TYPE = "statutory_remittance"
EPS = 0.005


class RemittanceError(ValueError):
    """Ditolak di langkah PERIKSA (400) — pesan siap tampil."""


def _r(v: Any) -> float:
    return round(float(v or 0), 2)


def _check_kind(kind: str) -> str:
    k = (kind or "").strip()
    if k not in KIND_LABEL:
        raise RemittanceError("Jenis setoran harus BPJS atau PPh 21.")
    return k


async def outstanding(entity_id: str, period: str) -> Dict[str, Any]:
    """Per jenis: `kewajiban` (dari proses gaji `posted`/`paid` masa itu), `disetor`, `sisa`."""
    from services import periodic_posting as pp
    pp.akhir_periode(period)   # validasi bentuk masa
    kew = {"bpjs": 0.0, "pph21": 0.0}
    runs = 0
    async for run in db.hr_payroll_runs.find({"entity_id": entity_id, "period": period,
                                              "status": {"$in": ["posted", "paid"]}}, {"_id": 0, "totals": 1}):
        t = run.get("totals") or {}
        kew["bpjs"] += float(t.get("bpjs_emp") or 0) + float(t.get("bpjs_er") or 0)
        kew["pph21"] += float(t.get("pph21") or 0)
        runs += 1
    setor = {"bpjs": 0.0, "pph21": 0.0}
    async for d in db[COLL].find({"entity_id": entity_id, "period": period}, {"_id": 0, "kind": 1, "amount": 1}):
        if d.get("kind") in setor:
            setor[d["kind"]] += float(d.get("amount") or 0)
    items = []
    for k in ("bpjs", "pph21"):
        items.append({"kind": k, "label": KIND_LABEL[k], "kewajiban": _r(kew[k]), "disetor": _r(setor[k]),
                      "sisa": _r(kew[k] - setor[k])})
    return {"entity_id": entity_id, "period": period, "period_label": pp.label_periode(period), "runs": runs,
            "items": items, **{it["kind"]: it for it in items}}


async def list_remittances(scope: Dict[str, Any], *, period: str = "", kind: str = "", page: int = 1,
                           page_size: int = 50) -> Dict[str, Any]:
    q: Dict[str, Any] = dict(scope or {})
    if period:
        q["period"] = period
    if kind:
        q["kind"] = _check_kind(kind)
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 50), 200))
    total = await db[COLL].count_documents(q)
    rows = await db[COLL].find(q, {"_id": 0}).sort([("paid_date", -1), ("created_at", -1)]) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return {"items": [safe_doc(r) for r in rows], "total": total, "page": page, "page_size": page_size}


def remittance_id(entity_id: str, idem_key: str = "") -> str:
    """Id tetap dari kunci idempotensi (kirim ulang = setoran yang sama); tanpa kunci = id baru."""
    if idem_key:
        return "strm_" + hashlib.sha1(f"{entity_id}|{idem_key}".encode("utf-8")).hexdigest()[:20]
    return new_id("strm")


async def create_remittance(entity_id: str, payload: Dict[str, Any], actor: Dict[str, Any], *,
                            idem_key: str = "") -> Dict[str, Any]:
    """`payload` = {kind, period, amount, paid_date, account_id?, cash_type, reference?, notes?}. Galat:
    `RemittanceError` (400), `ClosedPeriodError` (409), `cash_ledger.CashRejected` (409 — rekening),
    `cash_ledger.CashPostingError` (409 — kas & setoran tersimpan, jurnal gagal; ulang dari Posting Gagal)."""
    from services import cash_ledger, gl_service as gl, periodic_posting as pp
    from services.book_date import tanggal_buku
    # ── 1. PERIKSA (tanpa tulisan) ────────────────────────────────────────────────────────────────────────────────
    kind = _check_kind(payload.get("kind"))
    period = str(payload.get("period") or "").strip()
    pp.akhir_periode(period)
    amount = _r(payload.get("amount"))
    if amount <= EPS:
        raise RemittanceError("Nominal setoran harus lebih dari 0.")
    try:
        paid_date = tanggal_buku(str(payload.get("paid_date") or "").strip() or None)
    except ValueError as exc:
        raise RemittanceError("Tanggal setor tidak dikenali (TTTT-BB-HH).") from exc
    rid = remittance_id(entity_id, idem_key)
    prior = await db[COLL].find_one({"id": rid}, {"_id": 0})
    if prior:   # kirim ulang niat yang sama → teruskan dari langkah terakhir
        return await finish_remittance(rid)
    sisa = (await outstanding(entity_id, period))[kind]["sisa"]
    if amount > sisa + EPS:
        raise RemittanceError(f"Setoran {rupiah(amount)} melebihi sisa kewajiban {KIND_LABEL[kind]} "
                              f"{pp.label_periode(period)} ({rupiah(max(sisa, 0))}).")
    await gl.preflight_posting(entity_id, paid_date)
    cash_type = payload.get("cash_type") if payload.get("cash_type") in ("kas_besar", "kas_kecil") else "kas_besar"
    rek = await cash_ledger.periksa_rekening(entity_id, payload.get("account_id") or "", cash_type)
    contra = await gl.account_for(MAP_KEY[kind], entity_id)
    # ── 2. NIAT ────────────────────────────────────────────────────────────────────────────────────────────────────
    number = await next_doc_number(COLL, "number", "STR-", entity_id=entity_id)
    now = now_iso()
    doc = {
        "id": rid, "number": number, "entity_id": entity_id, "kind": kind, "period": period, "amount": amount,
        "paid_date": paid_date, "account_id": rek["account_id"], "cash_type": rek["cash_type"],
        "contra_account_code": contra, "cash_txn_id": "", "journal_entry_id": "",
        "status": "pending", "gl_status": "pending", "gl_error": "",
        "reference": str(payload.get("reference") or "").strip()[:120],
        "notes": str(payload.get("notes") or "").strip()[:500],
        "created_by": actor.get("name", "system"), "created_by_id": actor.get("id", ""),
        "created_at": now, "updated_at": now,
    }
    await db[COLL].update_one({"id": rid}, {"$setOnInsert": doc}, upsert=True)
    # INV-ATOMIC-01 — dua setoran bersamaan bisa sama-sama lolos PERIKSA: hitung ulang sesudah niat tersimpan; bila
    # melampaui, niat milik permintaan INI dihapus lagi (belum ada kas) dan ditolak dengan pesan yang sama.
    after = (await outstanding(entity_id, period))[kind]
    if after["sisa"] < -EPS:
        await db[COLL].delete_one({"id": rid, "status": "pending", "cash_txn_id": ""})
        raise RemittanceError(f"Setoran {rupiah(amount)} melebihi sisa kewajiban {KIND_LABEL[kind]} "
                              f"{pp.label_periode(period)} ({rupiah(max(after['sisa'] + amount, 0))}).")
    return await finish_remittance(rid)


async def finish_remittance(rid: str) -> Dict[str, Any]:
    """EFEK + JURNAL + SELESAI (dan ULANG): kas keluar ber-id tetap dari id setoran → jurnal kas → `done`."""
    from services import cash_ledger
    doc = await db[COLL].find_one({"id": rid}, {"_id": 0})
    if not doc:
        raise RemittanceError("Setoran tidak ditemukan.")
    if doc.get("status") == "done":
        return safe_doc(doc)
    label = KIND_LABEL.get(doc.get("kind"), doc.get("kind", ""))
    from services import periodic_posting as pp
    try:
        txn = await cash_ledger.create_cash(
            entity_id=doc["entity_id"], direction="out", amount=float(doc["amount"]), ref_type=REF_TYPE, ref_id=rid,
            account_id=doc.get("account_id") or "", cash_type=doc.get("cash_type") or "kas_besar",
            txn_date=doc.get("paid_date") or "", category="setoran kewajiban",
            description=f"Setoran {label} {pp.label_periode(doc['period'])} ({doc.get('number', '')})",
            actor=doc.get("created_by") or "system", contra_account_code=doc.get("contra_account_code") or "",
            extra={"remittance_kind": doc.get("kind"), "period": doc.get("period"),
                   "reference": doc.get("reference") or ""})
    except cash_ledger.CashPostingError as exc:
        await db[COLL].update_one({"id": rid}, {"$set": {
            "cash_txn_id": exc.txn.get("id", ""), "gl_status": "failed", "gl_error": str(exc.error)[:300],
            "gl_failed_at": now_iso(), "updated_at": now_iso()}})
        raise
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": txn["id"],
                                            "status": {"$ne": "void"}}, {"_id": 0, "id": 1, "number": 1})
    await db[COLL].update_one({"id": rid}, {"$set": {
        "status": "done", "gl_status": "posted" if je else (txn.get("gl_status") or "posted"), "gl_error": "",
        "cash_txn_id": txn["id"], "cash_txn_number": txn.get("number", ""),
        "journal_entry_id": (je or {}).get("id", ""), "journal_entry_number": (je or {}).get("number", ""),
        "updated_at": now_iso()}})
    return safe_doc(await db[COLL].find_one({"id": rid}, {"_id": 0}))
