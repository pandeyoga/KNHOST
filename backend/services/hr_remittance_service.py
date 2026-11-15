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
tidak melampaui sisa; PY-T4 — setoran `void` tidak dihitung). Denda keterlambatan bukan dokumen ini (ASUMSI unit).

PY-T4 — batal setoran yang salah catat (`void_remittance`, izin `payroll.void`): PERIKSA `done` + alasan ≥ 5 huruf +
`preflight_posting(PT, tanggal setor)` → NIAT `done → voiding` bersyarat → kas setoran dibalik lewat pintu tahan-gagal
(`post_durable` jenis `cash_transaction_void`, bertanggal setor) lalu kas `void` → `void`. Gagal → kembali `done`.
Kewajiban setahun per masa: `outstanding_year` (12 masa per jenis).
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict

from core_utils import new_id, next_doc_number, now_iso, rupiah, safe_doc
from db import db

COLL = "hr_statutory_remittances"
KIND_LABEL = {"bpjs": "BPJS", "pph21": "PPh 21"}
#: Label status setoran (pesan 409 "…berstatus {label}…"; layar memakai label yang sama).
STATUS_LABEL = {"pending": "Diproses", "done": "Tercatat", "voiding": "Sedang dibatalkan", "void": "Dibatalkan"}
MAP_KEY = {"bpjs": "sdm.hutang_bpjs", "pph21": "sdm.hutang_pph21"}
REF_TYPE = "statutory_remittance"
EPS = 0.005


class RemittanceError(ValueError):
    """Ditolak di langkah PERIKSA (400) — pesan siap tampil."""


class RemittanceConflict(ValueError):
    """PY-T4 — aksi pada status yang salah (router → 409). Pesan siap tampil."""


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
    async for d in db[COLL].find({"entity_id": entity_id, "period": period, "status": {"$ne": "void"}},
                                 {"_id": 0, "kind": 1, "amount": 1}):
        if d.get("kind") in setor:
            setor[d["kind"]] += float(d.get("amount") or 0)
    items = []
    for k in ("bpjs", "pph21"):
        items.append({"kind": k, "label": KIND_LABEL[k], "kewajiban": _r(kew[k]), "disetor": _r(setor[k]),
                      "sisa": _r(kew[k] - setor[k])})
    return {"entity_id": entity_id, "period": period, "period_label": pp.label_periode(period), "runs": runs,
            "items": items, **{it["kind"]: it for it in items}}


async def outstanding_year(entity_id: str, year: Any) -> Dict[str, Any]:
    """PY-T4 — kewajiban, sudah disetor, sisa untuk 12 masa satu tahun, per jenis (dua kueri, bukan 12 × 2)."""
    from services import periodic_posting as pp
    try:
        y = int(str(year).strip())
    except (TypeError, ValueError) as exc:
        raise RemittanceError("Tahun harus berbentuk TTTT, mis. 2026.") from exc
    if not 2000 <= y <= 2100:
        raise RemittanceError("Tahun harus berbentuk TTTT, mis. 2026.")
    masa = [f"{y:04d}-{m:02d}" for m in range(1, 13)]
    kew = {k: {p: 0.0 for p in masa} for k in KIND_LABEL}
    runs = {p: 0 for p in masa}
    async for run in db.hr_payroll_runs.find({"entity_id": entity_id, "period": {"$in": masa},
                                              "status": {"$in": ["posted", "paid"]}},
                                             {"_id": 0, "period": 1, "totals": 1}):
        t = run.get("totals") or {}
        kew["bpjs"][run["period"]] += float(t.get("bpjs_emp") or 0) + float(t.get("bpjs_er") or 0)
        kew["pph21"][run["period"]] += float(t.get("pph21") or 0)
        runs[run["period"]] += 1
    setor = {k: {p: 0.0 for p in masa} for k in KIND_LABEL}
    async for d in db[COLL].find({"entity_id": entity_id, "period": {"$in": masa}, "status": {"$ne": "void"}},
                                 {"_id": 0, "kind": 1, "period": 1, "amount": 1}):
        if d.get("kind") in setor:
            setor[d["kind"]][d["period"]] += float(d.get("amount") or 0)
    kinds = []
    for k, label in KIND_LABEL.items():
        rows = [{"period": p, "period_label": pp.label_periode(p), "runs": runs[p], "kewajiban": _r(kew[k][p]),
                 "disetor": _r(setor[k][p]), "sisa": _r(kew[k][p] - setor[k][p])} for p in masa]
        kinds.append({"kind": k, "label": label, "rows": rows,
                      "total": {f: _r(sum(r[f] for r in rows)) for f in ("kewajiban", "disetor", "sisa")}})
    return {"entity_id": entity_id, "year": y, "kinds": kinds}


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


async def void_remittance(rid: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """PY-T4 — batalkan setoran `done` yang salah catat. Galat: `RemittanceError` 400 (alasan), `RemittanceConflict`
    409 (status / kas sudah dicocokkan / jurnal pembalik gagal), `ClosedPeriodError` 409 (periode tanggal setor)."""
    from services import cash_ledger, gl_service as gl
    doc = await db[COLL].find_one({"id": rid}, {"_id": 0})
    if not doc:
        raise RemittanceError("Setoran tidak ditemukan.")
    # ── 1. PERIKSA (tanpa tulisan) ────────────────────────────────────────────────────────────────────────────────
    if doc.get("status") != "done":
        lbl = STATUS_LABEL.get(doc.get("status") or "", doc.get("status") or "")
        raise RemittanceConflict(f"Setoran {doc.get('number') or rid} berstatus {lbl}, jadi tidak bisa dibatalkan.")
    alasan = (reason or "").strip()
    if len(alasan) < 5:   # K-14 (26 Okt): alasan minimum seragam 5 huruf
        raise RemittanceError("Alasan wajib diisi (minimal 5 huruf).")
    tanggal = doc.get("paid_date") or ""
    await gl.preflight_posting(doc["entity_id"], tanggal)
    cid = doc.get("cash_txn_id") or ""
    kas = await db.cash_transactions.find_one({"id": cid or "__none__"}, {"_id": 0})
    if kas and float(kas.get("reconciled_amount") or 0) > 0:
        raise RemittanceConflict("Kas setoran ini sudah dicocokkan dengan mutasi bank — lepaskan dulu.")
    # ── 2. NIAT ────────────────────────────────────────────────────────────────────────────────────────────────────
    nama = actor.get("name", "system")
    if not (await db[COLL].update_one({"id": rid, "status": "done"}, {"$set": {
            "status": "voiding", "void_reason": alasan, "updated_at": now_iso()}})).matched_count:
        fresh = await db[COLL].find_one({"id": rid}, {"_id": 0}) or doc
        lbl = STATUS_LABEL.get(fresh.get("status") or "", fresh.get("status") or "")
        raise RemittanceConflict(f"Setoran {doc.get('number') or rid} berstatus {lbl}, jadi tidak bisa dibatalkan.")
    # ── 3. EFEK + JURNAL (pintu kas tahan-gagal) ──────────────────────────────────────────────────────────────────
    rev: Dict[str, Any] = {}
    try:
        if kas and kas.get("status") != "void":
            await cash_ledger.ensure_posted(cid)   # jurnal setoran asal ada (mis. sesudah ulang dari panel)
            res = await gl.post_durable(
                "cash_transactions", cid,
                lambda: gl.post_cash_void(cid, label=doc.get("number", ""), created_by=nama, date=tanggal),
                source_type="cash_transaction_void", source_id=cid, field="void_gl_status", raise_on_fail=True)
            rev = res.get("journal") or ({"id": res["journal_entry_id"]} if res.get("journal_entry_id") else {})
            await db.cash_transactions.update_one({"id": cid, "status": {"$ne": "void"}}, {"$set": {
                "status": "void", "void_journal_entry_id": rev.get("id", ""), "void_reason": alasan,
                "voided_by": nama, "voided_at": now_iso(), "updated_at": now_iso()}})
    except Exception as exc:  # noqa: BLE001 — jurnal pembalik gagal: setoran kembali Tercatat, kas tidak di-void
        await db[COLL].update_one({"id": rid, "status": "voiding"}, {"$set": {"status": "done", "updated_at": now_iso()},
                                                                      "$unset": {"void_reason": ""}})
        pesan = getattr(exc, "error", None) or str(exc)
        raise RemittanceConflict(f"Jurnal pembalik setoran gagal: {pesan}. Setoran tetap Tercatat.") from exc
    if rev.get("id") and not rev.get("number"):
        rev = await db.journal_entries.find_one({"id": rev["id"]}, {"_id": 0, "id": 1, "number": 1}) or rev
    # ── 4. SELESAI ─────────────────────────────────────────────────────────────────────────────────────────────────
    await db[COLL].update_one({"id": rid, "status": "voiding"}, {"$set": {
        "status": "void", "voided_by": nama, "voided_by_id": actor.get("id", ""), "voided_at": now_iso(),
        "void_journal_id": rev.get("id", ""), "void_journal_number": rev.get("number", ""), "updated_at": now_iso()}})
    return safe_doc(await db[COLL].find_one({"id": rid}, {"_id": 0}))
