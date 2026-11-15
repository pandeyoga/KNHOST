"""KM-T4 (K-26) — **tagihan antar-PT non-dagang** (`interco_charges`, nomor `ICC-` per PT penagih).

Sales yang menjual di PT lain dibayar gaji PT induknya. Baris Lembar Insentif PT-B (PT lembar = PT tertagih,
`to_entity_id`) untuk karyawan PT-A (PT penagih, `from_entity_id`) diakui beban & hutangnya di PT-B saat lembar disahkan;
saat proses gaji PT-A diposting, untuk Σ baris `INSENTIF` ber-`charge_entity_id` = PT-B (nilai X):

  buku PT-A  di dalam jurnal gaji: Dr Piutang antar-PT X (baris ber-`memo` = nomor tagihan; menggantikan Dr hutang
             insentif untuk baris itu)
  buku PT-B  jurnal sisi tunggal lewat pembantu jurnal kembar PK-06 (`twin_journal.post_twin`, `source_type`
             `interco_incentive_charge`, kunci = id tagihan): Dr Hutang insentif X / Cr Utang antar-PT X
  dokumen    satu tagihan per (proses gaji, PT tertagih) — indeks unik (`source.run_id`, `to_entity_id`)

Daur: `pending` (niat dibuat `siapkan` sebelum jurnal gaji; nomornya dipakai baris jurnal) → `open` (`terbitkan`
sesudah jurnal gaji terbit) → `settled` (`settle` sampai sisa 0) · `pending`/`open` → `cancelled` (batal proses /
anulir proses gaji PT-A — ditolak bila sudah ada pelunasan).

Pelunasan (`settle`, `02_STANDAR.md` §1): PERIKSA (status, nominal ≤ sisa, periode & rekening kedua PT, baris jurnal
kedua sisi) → NIAT klaim `settle_status: settling` bersyarat sisa → EFEK kas kembar (`twin_cash`: keluar PT-B, masuk
PT-A) → JURNAL kembar (`post_twin`, `interco_incentive_charge_settlement`): PT-B Dr Utang antar-PT / Cr Kas; PT-A Dr
Kas / Cr Piutang antar-PT → SELESAI `outstanding` turun; 0 → `settled`. Jurnal gagal → klaim dilepas, Posting Gagal
jenis `interco_incentive_charge` meneruskan (kas dipakai ulang, sisi yang kurang diterbitkan).

Saldo terbuka ikut `interco_money_service.non_trade_outstanding` dan dieliminasi `sync_non_trade_elimination`.
Invarian `INV-KM-5` = `rekonsiliasi`.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core_utils import next_doc_number, now_iso, rupiah, safe_doc
from db import db

COLL = "interco_charges"
SOURCE = "interco_incentive_charge"
SETTLE_SOURCE = "interco_incentive_charge_settlement"
PREFIX = "ICC-"
KIND_INCENTIVE = "incentive"
STATUS_LABEL = {"pending": "Menunggu jurnal gaji", "open": "Belum lunas", "settled": "Lunas", "cancelled": "Dibatalkan"}
KIND_LABEL = {KIND_INCENTIVE: "Insentif sales"}
EPS = 0.005
LEASE_MINUTES = 2   # jatah kerja satu pelunasan yang sedang berjalan; batas teknis, bukan aturan bisnis

PESAN_TIDAK_ADA = "Tagihan antar-PT tidak ditemukan."
PESAN_DILUNASI = "Tagihan antar-PT {nomor} sudah dilunasi sebagian. Batalkan pelunasannya dulu."
PESAN_SEDANG = "Tagihan antar-PT {nomor} sedang diproses. Muat ulang."


class ChargeError(ValueError):
    """Galat tagihan antar-PT dengan kalimat siap tampil; `status` = kode HTTP."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def charge_id(run_id: str, to_entity_id: str) -> str:
    """Id tagihan turunan (proses gaji, PT tertagih) — ulang posting = tagihan yang sama."""
    return "icc_" + hashlib.sha1(f"{run_id}|{to_entity_id}".encode("utf-8")).hexdigest()[:16]


def _lease_until() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=LEASE_MINUTES)).isoformat()


async def _nama(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "short_name": 1, "legal_name": 1,
                                                                "name": 1}) or {}
    return e.get("short_name") or e.get("legal_name") or e.get("name") or entity_id


def _pair(dr: str, cr: str, amount: float, desc: str, memo: str) -> List[Dict[str, Any]]:
    """Dua baris seimbang; nominal negatif membalik arah. Baris ber-`memo` nomor tagihan (dibaca INV-KM-5)."""
    a = round(abs(float(amount)), 2)
    if amount < 0:
        dr, cr = cr, dr
    return [{"account_code": dr, "debit": a, "credit": 0.0, "description": desc, "memo": memo},
            {"account_code": cr, "debit": 0.0, "credit": a, "description": desc, "memo": memo}]


# ── Rencana dari slip proses gaji PT penagih ─────────────────────────────────────────────────────────────────────────
def rencana(run: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """{PT tertagih: {amount, lines}} dari baris `INSENTIF` slip proses yang `charge_entity_id`-nya PT lain."""
    out: Dict[str, Dict[str, Any]] = {}
    for s in run.get("payslips") or []:
        for c in s.get("components") or []:
            to = c.get("charge_entity_id") or ""
            if c.get("bucket") != "commission" or not to or to == run.get("entity_id"):
                continue
            src = c.get("source") or {}
            p = out.setdefault(to, {"amount": 0.0, "lines": []})
            amt = round(float(c.get("amount") or 0), 2)
            p["amount"] = round(p["amount"] + amt, 2)
            p["lines"].append({"sheet_id": src.get("sheet_id") or "", "sheet_number": src.get("number") or "",
                               "line_id": src.get("line_id") or "", "employee_id": s.get("employee_id") or "",
                               "employee_name": s.get("employee_name") or "", "label": c.get("label") or "",
                               "amount": amt})
    return {k: v for k, v in out.items() if abs(v["amount"]) > EPS}


def _side_b(doc: Dict[str, Any]):
    from services import gl_service as gl
    from services.twin_journal import TwinSide
    label = f"Tagihan insentif antar-PT {doc['number']}"
    return TwinSide("b", doc["to_entity_id"],
                    _pair(gl.ACC_HUTANG_INSENTIF, gl.ACC_IC_AP, float(doc["amount"]),
                          f"Insentif sales {doc.get('from_entity_name') or ''} dibayar lewat gaji "
                          f"{doc.get('source', {}).get('run_number') or ''}".strip(), doc["number"]),
                    label, doc["number"], (COLL, doc["id"]), "", source_type=SOURCE, source_id=doc["id"])


async def periksa(run: Dict[str, Any], plan: Dict[str, Dict[str, Any]], journal_date: str) -> None:
    """PERIKSA posting gaji (tanpa tulisan): pasangan PT aktif, periode tanggal jurnal di PT tertagih terbuka, akun
    baris jurnal PT tertagih aktif. Gagal → `ChargeError` 409."""
    from services import interco_money_service as money
    from services import twin_journal as twin
    for to, p in plan.items():
        try:
            await money.assert_pair(run["entity_id"], to, what="Tagihan insentif antar-PT")
        except money.IntercoMoneyError as exc:
            raise ChargeError(str(exc), 409) from exc
        tiruan = {"id": charge_id(run["id"], to), "number": "ICC-PERIKSA", "to_entity_id": to, "amount": p["amount"],
                  "from_entity_name": await _nama(run["entity_id"]), "source": {"run_number": run.get("number")}}
        try:
            await twin.preflight_twin(source_type=SOURCE, base_id=tiruan["id"], date=journal_date,
                                      sides=[_side_b(tiruan)])
        except twin.TwinJournalError as exc:
            raise ChargeError(str(exc), 409) from exc


async def siapkan(run: Dict[str, Any], plan: Dict[str, Dict[str, Any]], actor: Dict[str, Any]) -> Dict[str, str]:
    """NIAT — tagihan `pending` per PT tertagih (id turunan; ulang = tagihan yang sama). → {PT tertagih: nomor}."""
    from pymongo.errors import DuplicateKeyError
    nomor: Dict[str, str] = {}
    for to, p in plan.items():
        cid = charge_id(run["id"], to)
        ada = await db[COLL].find_one({"id": cid}, {"_id": 0})
        if ada and ada.get("status") != "cancelled":
            nomor[to] = ada["number"]
            continue
        src = {"run_id": run["id"], "run_number": run.get("number") or "", "period": run.get("period") or "",
               "lines": p["lines"]}
        if ada:   # dibatalkan (proses dibatalkan lalu disahkan ulang tidak mungkin; anulir → proses baru) — hidupkan
            await db[COLL].update_one({"id": cid, "status": "cancelled"}, {"$set": {
                "status": "pending", "amount": p["amount"], "outstanding": p["amount"], "source": src,
                "updated_at": now_iso()}})
            nomor[to] = ada["number"]
            continue
        number = await next_doc_number(COLL, "number", PREFIX, entity_id=run["entity_id"])
        doc = {"id": cid, "number": number, "kind": KIND_INCENTIVE, "entity_id": run["entity_id"],
               "from_entity_id": run["entity_id"], "from_entity_name": await _nama(run["entity_id"]),
               "to_entity_id": to, "to_entity_name": await _nama(to), "amount": p["amount"],
               "outstanding": p["amount"], "status": "pending", "source": src, "journals": [],
               "gl_status": "pending", "settle_status": "none", "settlements": [],
               "history": [{"action": "create", "at": now_iso(), "by": actor.get("name", "system"),
                            "note": f"Dari penggajian {run.get('number') or ''}"}],
               "created_by": actor.get("name", "system"), "created_at": now_iso(), "updated_at": now_iso()}
        try:
            await db[COLL].insert_one(dict(doc))
            nomor[to] = number
        except DuplicateKeyError:   # D7 — dua posting bersamaan: indeks unik (source.run_id, to_entity_id)
            win = await db[COLL].find_one({"source.run_id": run["id"], "to_entity_id": to}, {"_id": 0, "number": 1})
            nomor[to] = (win or {}).get("number") or number
    return nomor


async def _sync(doc: Dict[str, Any]) -> None:
    from services import interco_money_service as money
    out = float(doc.get("outstanding") or 0) if doc.get("status") == "open" else 0.0
    await money.sync_non_trade_elimination(
        source_key=f"icc:{doc['id']}", pair_id=doc["id"], from_entity=doc["from_entity_id"],
        to_entity=doc["to_entity_id"], outstanding=out, label=f"tagihan insentif {doc.get('number', '')}",
        extra_note=f"Insentif sales dari penggajian {(doc.get('source') or {}).get('run_number') or ''}")
    await money.refresh_pair_exposure(doc["from_entity_id"], doc["to_entity_id"])


async def _post_b(doc: Dict[str, Any], date: str, created_by: str) -> Dict[str, Any]:
    from services import twin_journal as twin
    hasil = await twin.post_twin(source_type=SOURCE, base_id=doc["id"], date=date, sides=[_side_b(doc)],
                                 created_by=created_by)
    r = hasil.get("b") or {}
    if r.get("journal_id"):
        await db[COLL].update_one({"id": doc["id"], "journals.journal_id": {"$ne": r["journal_id"]}},
                                  {"$push": {"journals": {"kind": "charge", "entity_id": doc["to_entity_id"],
                                                          "journal_id": r["journal_id"]}}})
    return r


async def terbitkan(run: Dict[str, Any], actor: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Sesudah jurnal gaji PT penagih terbit: tagihan `pending` proses itu → `open` + jurnal PT tertagih (tahan-gagal:
    gagal = `gl_status: failed`, tampil di Posting Gagal)."""
    from pymongo import ReturnDocument
    out = []
    date = run.get("journal_date") or ""
    async for c in db[COLL].find({"source.run_id": run["id"], "status": {"$in": ["pending", "open"]}}, {"_id": 0}):
        doc = await db[COLL].find_one_and_update(
            {"id": c["id"], "status": {"$in": ["pending", "open"]}},
            {"$set": {"status": "open", "journal_date": date, "payroll_journal_id": run.get("journal_id") or "",
                      "updated_at": now_iso()}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
        if not doc:
            continue
        if run.get("journal_id"):
            await db[COLL].update_one({"id": doc["id"], "journals.journal_id": {"$ne": run["journal_id"]}},
                                      {"$push": {"journals": {"kind": "payroll", "entity_id": doc["from_entity_id"],
                                                              "journal_id": run["journal_id"]}}})
        if doc.get("gl_status") != "posted":
            await _post_b(doc, date, actor.get("name", "system"))
        await _sync(doc)
        out.append(doc)
    return out


async def batal_tertunda(run_id: str, actor_name: str = "system") -> int:
    """Proses gaji dibatalkan sebelum jurnalnya terbit: tagihan `pending` → `cancelled`."""
    res = await db[COLL].update_many({"source.run_id": run_id, "status": "pending"},
                                     {"$set": {"status": "cancelled", "outstanding": 0.0, "cancelled_at": now_iso(),
                                               "cancelled_by": actor_name, "updated_at": now_iso()}})
    return res.modified_count


async def periksa_void(run: Dict[str, Any], journal_date: str) -> None:
    """PERIKSA anulir proses gaji PT penagih: tagihan yang sudah dilunasi (sebagian) → 409; periode PT tertagih."""
    from services import gl_service as gl
    async for c in db[COLL].find({"source.run_id": run["id"], "status": {"$in": ["open", "settled"]}}, {"_id": 0}):
        if c.get("settlements") or c.get("settle_status") == "settling" or \
                abs(float(c.get("outstanding") or 0) - float(c.get("amount") or 0)) > EPS:
            raise ChargeError(PESAN_DILUNASI.format(nomor=c.get("number") or ""), 409)
        await gl.preflight_posting(c["to_entity_id"], c.get("journal_date") or journal_date)


async def batal_void(run: Dict[str, Any], reason: str, actor_name: str, journal_date: str) -> int:
    """Anulir proses gaji PT penagih: jurnal PT tertagih dibalik (bertanggal jurnal asalnya, lewat `post_durable`
    field `void_gl_status`), tagihan → `cancelled`. Pembalik gagal → tampil di Posting Gagal (ulang = balik lagi)."""
    from services import gl_service as gl
    n = 0
    async for c in db[COLL].find({"source.run_id": run["id"], "status": {"$in": ["pending", "open"]}}, {"_id": 0}):
        await db[COLL].update_one({"id": c["id"]}, {"$set": {
            "status": "cancelled", "outstanding": 0.0, "cancel_reason": reason, "cancelled_by": actor_name,
            "cancelled_at": now_iso(), "updated_at": now_iso()}})
        if c.get("gl_status") == "posted":
            await _balik(c, reason, actor_name, c.get("journal_date") or journal_date)
        await _sync({**c, "status": "cancelled", "outstanding": 0.0})
        n += 1
    return n


async def _balik(c: Dict[str, Any], reason: str, actor_name: str, date: str, *, raise_on_fail: bool = False):
    from services import gl_service as gl
    return await gl.post_durable(
        COLL, c["id"], lambda: gl.reverse_document(SOURCE, c["id"], reason=reason or "anulir penggajian",
                                                   actor_name=actor_name, date=date),
        source_type=f"{SOURCE}_reversal", source_id=c["id"], field="void_gl_status", raise_on_fail=raise_on_fail)


# ── Baca ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
def out_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = safe_doc({k: v for k, v in (doc or {}).items() if k != "_id"})
    d["status_label"] = STATUS_LABEL.get(d.get("status") or "", d.get("status") or "")
    d["kind_label"] = KIND_LABEL.get(d.get("kind") or "", "Tagihan antar-PT")
    return d


async def list_charges(scope_ids: List[str], *, status: str = "", q: str = "", page: int = 1,
                       page_size: int = 25) -> Dict[str, Any]:
    """Tagihan yang menyangkut PT dalam cakupan (sebagai penagih ATAU tertagih), terbaru dulu, berhalaman."""
    import re
    base: Dict[str, Any] = {"$or": [{"from_entity_id": {"$in": scope_ids}}, {"to_entity_id": {"$in": scope_ids}}]}
    syarat: List[Dict[str, Any]] = [base]
    if status:
        if status not in STATUS_LABEL:
            raise ChargeError("Status tagihan tidak dikenal.")
        syarat.append({"status": status})
    if q.strip():
        rx = {"$regex": re.escape(q.strip()[:60]), "$options": "i"}
        syarat.append({"$or": [{"number": rx}, {"source.run_number": rx}]})
    flt = {"$and": syarat}
    page, size = max(1, int(page or 1)), max(1, min(100, int(page_size or 25)))
    total = await db[COLL].count_documents(flt)
    rows = await db[COLL].find(flt, {"_id": 0}).sort([("created_at", -1), ("number", -1)]) \
        .skip((page - 1) * size).limit(size).to_list(size)
    sisa = 0.0
    async for r in db[COLL].find({"$and": [base, {"status": "open"}]}, {"_id": 0, "outstanding": 1}):
        sisa += float(r.get("outstanding") or 0)
    return {"items": [out_doc(r) for r in rows], "total": total, "page": page, "page_size": size,
            "outstanding_total": round(sisa, 2),
            "statuses": [{"value": k, "label": v} for k, v in STATUS_LABEL.items()]}


async def get_charge(cid: str) -> Optional[Dict[str, Any]]:
    return await db[COLL].find_one({"id": cid}, {"_id": 0})


# ── Pelunasan ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _settle_sides(doc: Dict[str, Any], seq: int, amount: float):
    from services import gl_service as gl
    from services.twin_journal import TwinSide
    label = f"Pelunasan tagihan insentif {doc['number']} #{seq}"
    return [
        TwinSide("a", doc["to_entity_id"], _pair(gl.ACC_IC_AP, gl.ACC_KAS_BESAR, amount,
                                                 f"Bayar tagihan insentif {doc['number']} ke "
                                                 f"{doc.get('from_entity_name') or ''}".strip(), doc["number"]),
                 label, doc["number"], (COLL, doc["id"]), "_settle_payer"),
        TwinSide("b", doc["from_entity_id"], _pair(gl.ACC_KAS_BESAR, gl.ACC_IC_AR, amount,
                                                   f"Terima pelunasan tagihan insentif {doc['number']} dari "
                                                   f"{doc.get('to_entity_name') or ''}".strip(), doc["number"]),
                 label, doc["number"], (COLL, doc["id"]), "_settle_payee"),
    ]


async def settle(cid: str, payload: Dict[str, Any], actor: Dict[str, Any], *,
                 allowed_entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """`POST /api/interco/charges/{id}/settle` — lihat docstring modul. Pelunasan yang macet di `settling` (jurnal
    gagal) diteruskan dengan isi niat yang tersimpan (isian baru diabaikan)."""
    from pymongo import ReturnDocument
    from services import cash_ledger
    from services import gl_service as gl
    from services import interco_money_service as money
    from services import twin_journal as twin
    from services.book_date import tanggal_buku
    doc = await get_charge(cid)
    if not doc:
        raise ChargeError(PESAN_TIDAK_ADA, 404)
    nomor = doc.get("number") or cid
    payer, payee = doc["to_entity_id"], doc["from_entity_id"]
    if allowed_entity_ids is not None and payer not in allowed_entity_ids:
        raise ChargeError(f"Anda belum punya akses di {doc.get('to_entity_name') or payer} untuk mencatat pelunasan "
                          "tagihan ini.", 403)
    if doc.get("settle_status") == "settling":
        won = await db[COLL].find_one_and_update(
            {"id": cid, "settle_status": "settling",
             "$or": [{"settle_lease_until": {"$in": ["", None]}}, {"settle_lease_until": {"$lt": now_iso()}}]},
            {"$set": {"settle_lease_until": _lease_until()}}, projection={"_id": 0},
            return_document=ReturnDocument.AFTER)
        if not won:
            raise ChargeError(PESAN_SEDANG.format(nomor=nomor), 409)
        niat = won["pending_settlement"]
    else:
        if doc.get("status") != "open":
            raise ChargeError(f"Tagihan {nomor} berstatus {STATUS_LABEL.get(doc.get('status'), doc.get('status'))}, "
                              "jadi tidak bisa dilunasi.", 409)
        try:
            amount = round(float(payload.get("amount") or 0), 2)
        except (TypeError, ValueError):
            raise ChargeError("Nominal pelunasan harus angka rupiah.")
        sisa = round(float(doc.get("outstanding") or 0), 2)
        if amount <= EPS or amount != int(amount):
            raise ChargeError("Nominal pelunasan harus rupiah bulat lebih dari 0.")
        if sisa <= EPS:
            raise ChargeError(f"Tagihan {nomor} tidak punya sisa yang bisa dilunasi.", 409)
        if amount > sisa + EPS:
            raise ChargeError(f"Pelunasan {rupiah(amount)} melebihi sisa tagihan ({rupiah(sisa)}).")
        tgl = tanggal_buku(payload.get("date") or None)
        # ── PERIKSA (tanpa tulisan): periode & rekening Bank kedua PT, baris jurnal kedua sisi ────────────────────
        rek = {}
        for ent, pilih in ((payer, payload.get("account_id_from")), (payee, payload.get("account_id_to"))):
            try:
                await gl.preflight_posting(ent, tgl)
            except gl.ClosedPeriodError as exc:
                raise ChargeError(str(exc), 409) from exc
            try:
                r = await cash_ledger.periksa_rekening(ent, pilih or await money.default_cash_account(ent),
                                                       "kas_besar")
            except cash_ledger.CashRejected as exc:
                raise ChargeError(str(exc), 409) from exc
            if r["cash_type"] != "kas_besar":
                raise ChargeError(f"Rekening {r['account'].get('name', '')} adalah Kas Kecil; uang antar-PT dibukukan "
                                  "di Bank. Pilih rekening Bank.", 409)
            rek[ent] = r["account_id"]
        seq = len(doc.get("settlements") or []) + 1
        try:
            await twin.preflight_twin(source_type=SETTLE_SOURCE, base_id=f"{cid}:st{seq}", date=tgl,
                                      sides=_settle_sides(doc, seq, amount))
        except twin.TwinJournalError as exc:
            raise ChargeError(str(exc), 409) from exc
        niat = {"seq": seq, "amount": amount, "date": tgl, "account_id_from": rek[payer], "account_id_to": rek[payee],
                "note": str(payload.get("note") or "").strip()[:300], "by": actor.get("name", ""),
                "by_id": actor.get("id", ""), "at": now_iso()}
        # ── NIAT: klaim bersyarat sisa & tidak sedang dilunasi ───────────────────────────────────────────────────────
        won = await db[COLL].find_one_and_update(
            {"id": cid, "status": "open", "settle_status": {"$in": ["none", None]},
             "outstanding": {"$gte": round(amount - EPS, 2)}},
            {"$set": {"settle_status": "settling", "pending_settlement": niat, "settle_lease_until": _lease_until(),
                      "updated_at": now_iso()}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
        if not won:
            raise ChargeError(PESAN_SEDANG.format(nomor=nomor), 409)
    return await _lanjut_settle(won, niat, actor)


async def _lanjut_settle(doc: Dict[str, Any], niat: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import interco_money_service as money
    from services import twin_journal as twin
    cid, nomor, seq, amount = doc["id"], doc.get("number") or doc["id"], int(niat["seq"]), float(niat["amount"])
    payer, payee = doc["to_entity_id"], doc["from_entity_id"]

    async def lepas() -> None:
        await db[COLL].update_one({"id": cid, "settle_status": "settling"},
                                  {"$set": {"settle_lease_until": "", "updated_at": now_iso()}})
    # ── EFEK: kas kembar (id tetap per arah; ulang = kas yang sama) ──────────────────────────────────────────────
    try:
        cash = await money.twin_cash(
            out_entity=payer, in_entity=payee, amount=amount, category="tagihan insentif antar-PT",
            description=(f"Pelunasan tagihan insentif {nomor} ke {doc.get('from_entity_name') or ''}"
                         + (f" — {niat.get('note')}" if niat.get("note") else "")),
            ref_type=SETTLE_SOURCE, ref_id=f"{cid}:st{seq}", actor=niat.get("by") or actor.get("name", "system"),
            txn_date=niat["date"], out_account_id=niat["account_id_from"], in_account_id=niat["account_id_to"])
    except Exception:
        await lepas()
        raise
    # ── JURNAL: dua buku, status per sisi di tagihan ─────────────────────────────────────────────────────────────
    sides = _settle_sides(doc, seq, amount)
    hasil = await twin.post_twin(source_type=SETTLE_SOURCE, base_id=f"{cid}:st{seq}", date=niat["date"], sides=sides,
                                 created_by=niat.get("by") or actor.get("name", "system"))
    if any(v.get("status") == "failed" for v in hasil.values()):
        await lepas()
        raise ChargeError(f"Kas pelunasan tagihan {nomor} sudah tercatat, tetapi jurnalnya belum lengkap. "
                          f"{await twin.warning_for(hasil, sides)}", 409)
    # ── SELESAI: sisa turun bersyarat klaim; 0 → lunas ───────────────────────────────────────────────────────────
    from pymongo import ReturnDocument
    entri = {**niat, "cash_ids": [cash["out"].get("id", ""), cash["in"].get("id", "")],
             "cash_numbers": [cash["out"].get("number", ""), cash["in"].get("number", "")],
             "journal_ids": [v.get("journal_id") or "" for v in hasil.values()]}
    cur = await db[COLL].find_one({"id": cid}, {"_id": 0, "outstanding": 1}) or {}
    sisa = round(float(cur.get("outstanding") or 0) - amount, 2)
    out = await db[COLL].find_one_and_update(
        {"id": cid, "settle_status": "settling", "pending_settlement.seq": seq},
        {"$set": {"outstanding": max(sisa, 0.0), "status": "settled" if sisa <= EPS else "open",
                  "settle_status": "none", "settle_lease_until": "", "updated_at": now_iso(),
                  **({"settled_at": now_iso()} if sisa <= EPS else {})},
         "$unset": {"pending_settlement": ""},
         "$push": {"settlements": entri,
                   "journals": {"$each": [{"kind": "settlement", "entity_id": e, "journal_id": v.get("journal_id")}
                                          for e, v in ((payer, hasil.get("a") or {}), (payee, hasil.get("b") or {}))]},
                   "history": {"action": "settle", "at": now_iso(), "by": niat.get("by") or "",
                               "note": f"Pelunasan #{seq} {rupiah(amount)}"}}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    out = out or await get_charge(cid)
    await _sync(out)
    return out_doc(out)


# ── Posting Gagal (jenis `interco_incentive_charge`) ────────────────────────────────────────────────────────────────
async def ulang(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """Terbitkan jurnal yang kurang: jurnal PT tertagih (`gl_status` gagal), pelunasan yang macet di `settling`, atau
    pembalik anulir (`void_gl_status` gagal). Masih gagal → melempar."""
    cur = await get_charge(doc["id"]) or doc
    if cur.get("status") != "cancelled" and cur.get("gl_status") == "failed":
        r = await _post_b(cur, cur.get("journal_date") or "", actor.get("name", "system"))
        if r.get("status") == "failed":
            raise RuntimeError(r.get("error") or "jurnal tagihan antar-PT gagal")
    if cur.get("settle_status") == "settling":
        await settle(cur["id"], {}, actor)
    if cur.get("void_gl_status") == "failed":
        await _balik(cur, cur.get("cancel_reason") or "", actor.get("name", "system"), cur.get("journal_date") or "",
                     raise_on_fail=True)


# ── INV-KM-5 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _saldo_memo(entity_id: str, codes: set, numbers: set, credit_normal: bool) -> float:
    sen = 0
    async for je in db.journal_entries.find({"entity_id": entity_id, "status": {"$ne": "void"},
                                             "lines.memo": {"$in": sorted(numbers)}}, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("memo") in numbers and ln.get("account_code") in codes:
                d = round(float(ln.get("debit") or 0) * 100) - round(float(ln.get("credit") or 0) * 100)
                sen += -d if credit_normal else d
    return sen / 100


async def rekonsiliasi() -> List[Dict[str, Any]]:
    """INV-KM-5 per pasangan PT (penagih, tertagih): Σ `outstanding` tagihan = saldo piutang antar-PT dari jurnal
    tagihan insentif di PT penagih = saldo utang antar-PT di PT tertagih (baris ber-`memo` nomor tagihan yang tidak
    dibatalkan). → baris per pasangan {from_entity_id, to_entity_id, outstanding, piutang, utang, ok}."""
    from services import gl_mapping_service as glm
    pasangan: Dict[tuple, Dict[str, Any]] = {}
    async for c in db[COLL].find({"status": {"$in": ["open", "settled"]}}, {"_id": 0}):
        p = pasangan.setdefault((c["from_entity_id"], c["to_entity_id"]), {"outstanding": 0.0, "numbers": set()})
        p["outstanding"] = round(p["outstanding"] + float(c.get("outstanding") or 0), 2)
        p["numbers"].add(c["number"])
    out: List[Dict[str, Any]] = []
    for (a, b), p in sorted(pasangan.items()):
        ar = await _saldo_memo(a, set(await glm.known_codes("antar_pt.piutang_ic", a)), p["numbers"], False)
        ap = await _saldo_memo(b, set(await glm.known_codes("antar_pt.utang_ic", b)), p["numbers"], True)
        out.append({"from_entity_id": a, "to_entity_id": b, "outstanding": p["outstanding"], "piutang": ar,
                    "utang": ap, "ok": abs(p["outstanding"] - ar) < 1 and abs(p["outstanding"] - ap) < 1})
    return out


async def outstanding_between(from_entity: str, to_entity: str) -> Dict[str, Any]:
    """Σ sisa tagihan `open` (penagih → tertagih) — dipakai `interco_money_service.non_trade_outstanding`."""
    rows = await db[COLL].find({"from_entity_id": from_entity, "to_entity_id": to_entity, "status": "open"},
                               {"_id": 0, "outstanding": 1}).to_list(5000)
    return {"charge_outstanding": round(sum(float(r.get("outstanding") or 0) for r in rows), 2),
            "charge_count": len(rows)}

