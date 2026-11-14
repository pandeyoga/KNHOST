"""PK-32 (FX-12, FX-13, FX-14, FX-15) — SATU mesin nota kredit dan nota debit pesanan.

Semua dokumen `credit_notes` (nota kredit retur per barang, retur per roll, amandemen, batal item Pesanan Khusus, dan
nota debit amandemen) lahir lewat `issue` lalu efeknya dijalankan `settle` (`02_STANDAR.md` §1 P1–P4):

  issue   PERIKSA — batas total nota kredit pesanan (`assert_cap`, di bawah kunci pesanan supaya dua penerbitan
          bersamaan tidak sama-sama lolos) dan periode buku. RENCANA — bagian nilai yang dijurnal sekarang dan yang
          ditangguhkan (`recognition_split`), kelebihan bayar, pembagian piutang–saldo kredit, baris alokasi. SISIP —
          dokumen dengan `effects` serba `pending` dan `gl_status="pending"`. Satu-satunya penyisip `credit_notes`.
  settle  menjalankan langkah yang belum `done`, masing-masing aman diulang:
            allocation    nota kredit: baris `sales_orders.payments[]` lewat `ar_allocation_service.allocate`
                          (`kind="nota_kredit"`, id baris dari id nota); nota debit: baris
                          `sales_orders.extra_billing_lines[]` ($push bersyarat id nota belum ada)
            store_credit  saldo kredit pelanggan, rujukan = id nota
            journal       jurnal lewat `gl_service.post_durable` (hasil di nota: `gl_status`, `gl_error`,
                          `journal_entry_id`)
          semua langkah `done`/`skipped` → `status="posted"`. Jurnal gagal → nota tetap `issued`, tampil di panel
          Posting Gagal (jenis `credit_note`), ulang = `settle` lagi.
  void    hanya nota `pending_finance`/`issued` yang belum satu efek pun `done`.

Kosakata status: `pending_finance` (menunggu Finance) · `issued` (terbit, efek belum tuntas) · `posted` (semua efek
tuntas) · `void`. Data lama dibaca lewat `normalize` (nilai `offset` = `posted`, nota tanpa `kind` = nota kredit,
nota retur tanpa `source` = sumber returnya) tanpa migrasi.

Tiga angka pesanan (`02` D1): nilai tagihan = `customer_service._order_grand_total` (grand total + tagihan tambahan
nota debit); nilai efektif pendapatan = `gl_service.order_effective_totals`; sisa tagihan = nilai tagihan − Σ
`payments[]`.

Pembagian baris alokasi nota kredit amandemen: bagian yang mengurangi piutang yang sudah lahir (`ar_part`, jurnal
Cr 1-1200) ber-`gl_bucket="nota_koreksi"`; bagian yang pendapatannya belum diakui ber-`gl_bucket="nota_tangguh"`.
Keduanya mengurangi sisa tagihan tetapi tidak dihitung `gl_service.order_direct_ar_paid` — piutang yang dikurangi
nota amandemen sudah dihitung dari jurnalnya sendiri (`order_revenue_recognized`).
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import new_id, now_iso, rupiah
from db import db

_log = logging.getLogger(__name__)

EPS = 0.01
KINDS = ("credit_note", "debit_note")
SOURCES = ("sales_return", "sales_return_roll", "amendment", "od_item_cancel")
STATUSES = ("pending_finance", "issued", "posted", "void")
STEPS = ("allocation", "store_credit", "journal")
BUCKET_TANGGUH = "nota_tangguh"
BUCKET_KOREKSI = "nota_koreksi"
#: baris `payments[]` nota amandemen — mengurangi sisa tagihan, bukan pelunasan piutang langsung
NOTE_BUCKETS = (BUCKET_KOREKSI, BUCKET_TANGGUH)
#: sumber nota kredit yang dibatasi `assert_cap`. Nota batal item tidak: baris pesanannya sudah dikeluarkan dan grand
#: total sudah dihitung ulang saat batal, jadi nilainya bukan bagian dari nilai tagihan yang tersisa.
CAPPED_SOURCES = ("sales_return", "sales_return_roll", "amendment")
#: sumber yang nilainya mengurangi nilai efektif pendapatan pesanan (`gl_service.order_effective_totals`)
EFFECTIVE_SOURCES = ("amendment",)
#: lama kunci penerbitan per pesanan (batas teknis: proses yang terhenti tidak mengunci pesanan selamanya)
_KUNCI_DETIK = 30
_KUNCI_COBA, _KUNCI_JEDA = 80, 0.05

LABEL_STATUS = {"pending_finance": "Menunggu Finance", "issued": "Terbit", "posted": "Selesai", "void": "Batal"}


class CreditNoteError(HTTPException):
    """Galat nota yang pesannya siap tampil; turunan `HTTPException` (bawaan 409) supaya router meneruskannya apa
    adanya — termasuk router amandemen yang memetakan `AmendmentError` ke 400."""

    def __init__(self, detail: str, status_code: int = 409):
        super().__init__(status_code=status_code, detail=detail)


# ── Pembaca bentuk (data lama tanpa migrasi) ──────────────────────────────────────────────────────────────────────────
def note_kind(doc: Dict[str, Any]) -> str:
    return (doc or {}).get("kind") or "credit_note"


def note_source(doc: Dict[str, Any]) -> str:
    d = doc or {}
    if d.get("source"):
        return d["source"]
    if d.get("settlement_id"):
        return "sales_return_roll"
    if d.get("return_id"):
        return "sales_return"
    if d.get("amendment_id"):
        return "amendment"
    return ""


def note_status(doc: Dict[str, Any]) -> str:
    """Status kosakata baru. `offset` (nota amandemen lama yang habis menutup nota debit) = `posted`; nota batal item
    lama yang sudah diterbitkan (`issued` + `accounting` tertulis, tanpa `effects`) = `posted`."""
    d = doc or {}
    s = d.get("status") or ""
    if s == "offset":
        return "posted"
    if s == "issued" and not d.get("effects") and note_source(d) == "od_item_cancel" and d.get("accounting"):
        return "posted"
    return s


def normalize(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Salinan nota dengan `kind`, `source`, `status` kosakata baru (+ `status_label`). Data tidak diubah."""
    if not doc:
        return doc
    out = {k: v for k, v in doc.items() if k != "_id"}
    out["kind"] = note_kind(doc)
    src = note_source(doc)
    if src:
        out["source"] = src
    out["status"] = note_status(doc)
    out["status_label"] = LABEL_STATUS.get(out["status"], out["status"])
    return out


def _effects_of(doc: Dict[str, Any]) -> Dict[str, str]:
    """Penanda langkah; nota lama (sebelum PK-32) tanpa `effects`: alokasi & saldo sudah dikerjakan pembuat lamanya,
    jurnal tuntas bila `gl_status` posted/not_required."""
    eff = doc.get("effects")
    if isinstance(eff, dict) and eff:
        return {s: eff.get(s) or "pending" for s in STEPS}
    journal = "done" if doc.get("gl_status") in ("posted", "not_required") else "pending"
    return {"allocation": "done", "store_credit": "done", "journal": journal}


# ── Angka pesanan ─────────────────────────────────────────────────────────────────────────────────────────────────────
def billing_value(order: Dict[str, Any]) -> float:
    """Nilai tagihan = grand total + Σ tagihan tambahan nota debit (`customer_service._order_grand_total`)."""
    from services.customer_service import _order_grand_total
    return round(_order_grand_total(order or {}), 2)


def paid_total(order: Dict[str, Any]) -> float:
    from services.customer_service import _order_paid
    return round(_order_paid(order or {}), 2)


def outstanding(order: Dict[str, Any]) -> float:
    """Sisa tagihan = nilai tagihan − Σ `payments[]` (≥ 0)."""
    return round(max(billing_value(order) - paid_total(order), 0.0), 2)


def _uang_pelanggan(order: Dict[str, Any]) -> float:
    """Uang/kredit pelanggan yang menempel di pesanan — Σ `payments[]` di luar baris nota amandemen (nota amandemen
    sudah mengurangi nilai efektif, jadi tidak dihitung dua kali)."""
    return round(sum(float(p.get("amount") or 0) for p in (order or {}).get("payments") or []
                     if p.get("gl_bucket") not in NOTE_BUCKETS), 2)


def _nomor(order: Dict[str, Any]) -> str:
    return str((order or {}).get("number") or (order or {}).get("id") or "")


def _nama(actor: Any) -> str:
    if isinstance(actor, dict):
        return str(actor.get("name") or "system")
    return str(actor or "system")


async def _pesanan(order_id: str) -> Dict[str, Any]:
    o = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise CreditNoteError("Pesanan asal nota tidak ditemukan.", 404)
    return o


async def _nota(note_id: str) -> Dict[str, Any]:
    d = await db.credit_notes.find_one({"id": note_id}, {"_id": 0})
    if not d:
        raise CreditNoteError("Nota tidak ditemukan.", 404)
    return d


# ── PERIKSA: batas total nota kredit ──────────────────────────────────────────────────────────────────────────────────
async def credit_total(order_id: str, exclude_id: str = "") -> float:
    """Σ nilai nota kredit tidak-`void` pesanan yang dibatasi (`CAPPED_SOURCES`). Bagian nota amandemen lama yang habis
    menutup nota debit yang belum ditagih (`debit_note_offset`) tidak dihitung."""
    total = 0.0
    async for cn in db.credit_notes.find({"order_id": order_id, "status": {"$ne": "void"}}, {"_id": 0}):
        if (exclude_id and cn.get("id") == exclude_id) or note_kind(cn) != "credit_note" \
                or note_source(cn) not in CAPPED_SOURCES:
            continue
        total += float(cn.get("gross_amount") or 0) - float(cn.get("debit_note_offset") or 0)
    return round(total, 2)


async def assert_cap(order: Dict[str, Any], new_gross: float, exclude_id: str = "") -> None:
    """Σ nota kredit tidak-`void` pesanan + `new_gross` ≤ nilai tagihan + 0,01; selain itu `CreditNoteError` (409)."""
    fresh = await db.sales_orders.find_one({"id": order["id"]}, {"_id": 0}) or order
    cap = billing_value(fresh)
    new_gross = round(float(new_gross or 0), 2)
    after = round(await credit_total(order["id"], exclude_id) + new_gross, 2)
    if after > cap + EPS:
        raise CreditNoteError(
            f"Nota kredit {rupiah(new_gross)} akan membuat total nota kredit pesanan {_nomor(fresh)} menjadi "
            f"{rupiah(after)}, melebihi nilai pesanan {rupiah(cap)}. Periksa nota yang sudah terbit.")


async def _kunci(order_id: str) -> str:
    """Kunci penerbitan nota kredit per pesanan (klaim bersyarat). Dua penerbitan bersamaan: yang kedua menunggu
    sebentar lalu memeriksa batas terhadap nota yang pertama."""
    token = new_id("cnk")
    for _ in range(_KUNCI_COBA):
        now = now_iso()
        until = (datetime.now(timezone.utc) + timedelta(seconds=_KUNCI_DETIK)).isoformat()
        res = await db.sales_orders.update_one(
            {"id": order_id, "$or": [{"credit_note_lock": {"$exists": False}}, {"credit_note_lock": {"$in": [None, ""]}},
                                     {"credit_note_lock_until": {"$lt": now}}]},
            {"$set": {"credit_note_lock": token, "credit_note_lock_until": until}})
        if res.modified_count:
            return token
        if not await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "id": 1}):
            raise CreditNoteError("Pesanan asal nota tidak ditemukan.", 404)
        await asyncio.sleep(_KUNCI_JEDA)
    raise CreditNoteError("Pesanan ini sedang menerbitkan nota lain. Muat ulang lalu coba lagi.")


async def _lepas(order_id: str, token: str) -> None:
    await db.sales_orders.update_one({"id": order_id, "credit_note_lock": token},
                                     {"$set": {"credit_note_lock": "", "credit_note_lock_until": ""}})


# ── RENCANA: bagian yang dijurnal sekarang ────────────────────────────────────────────────────────────────────────────
async def shipped_share(order: Dict[str, Any]) -> float:
    """Porsi nilai pesanan yang pendapatannya sudah lahir: 1 bila pesanan terkirim penuh atau pendapatannya diakui di
    tingkat pesanan (jurnal lama `sales_order`); selain itu Σ `shipment_value_share` surat jalan yang sudah berjurnal."""
    from services import gl_service as gl
    oid = order.get("id", "")
    if order.get("status") in gl.FULLY_SHIPPED_STATUSES | {"delivered", "completed"} \
            or await gl._already_posted("sales_order", oid):
        return 1.0
    share = 0.0
    for sh in await gl._order_shipments(oid):
        if await gl._already_posted("shipment_revenue", sh.get("id", "")):
            share += gl.shipment_value_share(order, sh)
    return round(min(1.0, max(0.0, share)), 6)


async def recognition_split(order: Dict[str, Any], net: float, ppn: float, sign: int, *,
                            reduces_effective: bool = True) -> Dict[str, Any]:
    """Bagian nota yang dijurnal SEKARANG dan yang DITANGGUHKAN (diakui surat jalan berikutnya lewat nilai efektif).

    Nota kredit (`sign` < 0): `sekarang_net = max(0, pendapatan_diakui − porsi_terkirim × net_efektif_baru)`, paling
    besar `net`; `net_efektif_baru` = nilai efektif bersih pesanan sesudah nota ini (`reduces_effective=False` untuk
    nota batal item: total pesanannya sudah turun saat batal). Nota debit (`sign` > 0): `sekarang_net = porsi_terkirim
    × net`. PPN sebanding; sisanya `deferred_*`."""
    from services import gl_service as gl
    net, ppn = round(float(net or 0), 2), round(float(ppn or 0), 2)
    porsi = await shipped_share(order)
    if sign < 0:
        eff = await gl.order_effective_totals(order)
        new_net = round(eff["net"] - (net if reduces_effective else 0.0), 2)
        recognized = (await gl.order_revenue_recognized(order.get("id", "")))["revenue"]
        now_net = round(min(net, max(0.0, recognized - porsi * new_net)), 2)
    else:
        now_net = round(porsi * net, 2)
    now_ppn = round(ppn * now_net / net, 2) if net > EPS else 0.0
    return {"porsi_terkirim": porsi, "sekarang_net": now_net, "sekarang_ppn": now_ppn,
            "deferred_net": round(net - now_net, 2), "deferred_ppn": round(ppn - now_ppn, 2)}


async def _dn_offsets(order: Dict[str, Any], gross: float) -> Tuple[float, List[Dict[str, Any]]]:
    """Nota debit LAMA yang belum ditagih (`awaiting_billing_rule`) ditutup lebih dulu oleh nota kredit amandemen
    (perilaku sebelum PK-32 dipertahankan sampai skrip migrasi menagihkannya)."""
    rows: List[Dict[str, Any]] = []
    offset = 0.0
    async for dn in db.credit_notes.find(
            {"order_id": order["id"], "kind": "debit_note", "billing_status": "awaiting_billing_rule"},
            {"_id": 0}).sort("created_at", 1):
        avail = float(dn.get("open_amount", dn.get("gross_amount")) or 0)
        take = round(min(gross - offset, avail), 2)
        if take <= 0:
            continue
        rows.append({"debit_note_id": dn["id"], "debit_note_number": dn.get("number", ""), "amount": take})
        offset = round(offset + take, 2)
    return offset, rows


async def _ar_room(order_id: str) -> float:
    """Piutang pesanan yang benar-benar masih terbuka di 1-1200: ruang piutang (`order_ar_room`) dikurangi uang muka
    yang sudah direklas ke piutang (reklas mengkredit 1-1200 tetapi barisnya ber-bucket uang muka)."""
    from services import gl_service as gl
    return round(max(0.0, await gl.order_ar_room(order_id) - await gl.order_advance_reclassed(order_id)), 2)


async def plan_for(*, kind: str, source: str, order: Dict[str, Any], net: float, ppn: float) -> Dict[str, Any]:
    """Rencana efek nota amandemen / batal item / nota debit (tanpa menulis apa pun). Nota retur memakai rencana
    pembuatnya sendiri (`allocation_amount`) dan jurnal retur yang tidak berubah."""
    from services import gl_service as gl
    net, ppn = round(float(net or 0), 2), round(float(ppn or 0), 2)
    gross = round(net + ppn, 2)
    oid = order["id"]
    if kind == "debit_note":
        sp = await recognition_split(order, net, ppn, +1)
        return {"revenue_added_net": sp["sekarang_net"], "revenue_added_ppn": sp["sekarang_ppn"],
                "deferred_net": sp["deferred_net"], "deferred_ppn": sp["deferred_ppn"],
                "shipped_share": sp["porsi_terkirim"], "billing_status": "pending"}
    offset, offset_rows = (await _dn_offsets(order, gross)) if source == "amendment" else (0.0, [])
    part = round(gross - offset, 2)
    frac = (part / gross) if gross > EPS else 0.0
    net_p = round(net * frac, 2)
    ppn_p = round(part - net_p, 2)
    reduces = source in EFFECTIVE_SOURCES
    sp = await recognition_split(order, net_p, ppn_p, -1, reduces_effective=reduces)
    reversed_gross = round(sp["sekarang_net"] + sp["sekarang_ppn"], 2)
    alloc_total = round(min(part, outstanding(order)), 2) if source == "amendment" else 0.0
    ar_part = round(min(reversed_gross, await _ar_room(oid)), 2)
    if source == "amendment":
        ar_part = round(min(ar_part, alloc_total), 2)
    sc_part = round(reversed_gross - ar_part, 2)
    eff = await gl.order_effective_totals(order)
    new_grand = round(eff["grand"] - (part if reduces else 0.0), 2)
    overpaid = round(max(0.0, _uang_pelanggan(order) - new_grand), 2)
    excess = round(max(0.0, overpaid - sc_part), 2)
    out = {"revenue_reversed_net": sp["sekarang_net"], "revenue_reversed_ppn": sp["sekarang_ppn"],
           "deferred_net": sp["deferred_net"], "deferred_ppn": sp["deferred_ppn"], "shipped_share": sp["porsi_terkirim"],
           "ar_part": ar_part, "store_credit_part": sc_part, "excess_payment": excess,
           "allocation_amount": alloc_total, "allocation_deferred": round(alloc_total - min(ar_part, alloc_total), 2),
           "debit_note_offset": offset, "debit_note_offsets": offset_rows}
    if source == "od_item_cancel":   # bidang lama layar batal item
        out["accounting"] = "revenue_correction" if reversed_gross > EPS else "no_journal_revenue_not_recognized"
        out["excess_handling"] = "customer_advance" if excess > EPS else ""
    return out


# ── TERBIT ────────────────────────────────────────────────────────────────────────────────────────────────────────────
_FIELD_INTI = frozenset({"id", "number", "kind", "source", "status", "effects", "order_id", "entity_id", "net_amount",
                         "ppn_amount", "gross_amount", "gl_status", "refs"})


async def issue(*, kind: str, source: str, order: Dict[str, Any], number: str, net: float, ppn: float,
                lines: List[Dict[str, Any]], actor: Any, refs: Optional[Dict[str, Any]] = None, cogs: float = 0.0,
                status: str = "issued", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Terbitkan satu nota (SATU-SATUNYA penyisip `credit_notes`). PERIKSA: periode buku (nota terbit) dan batas total
    nota kredit (`assert_cap`, sumber `CAPPED_SOURCES`) di bawah kunci pesanan. Nota amandemen/batal item/debit yang
    terbit langsung membawa rencananya (`plan_for`). `refs` = rujukan sumber (`return_id`, `amendment_id`, …) ditulis
    sebagai field dokumen; `extra` = field tambahan (tidak bisa menimpa field inti)."""
    if kind not in KINDS:
        raise ValueError(f"jenis nota tidak dikenal: {kind}")
    if source not in SOURCES:
        raise ValueError(f"sumber nota tidak dikenal: {source}")
    if status not in ("pending_finance", "issued"):
        raise ValueError(f"status awal nota tidak sah: {status}")
    net, ppn = round(float(net or 0), 2), round(float(ppn or 0), 2)
    gross = round(net + ppn, 2)
    oid = order["id"]
    eid = order.get("entity_id") or ""
    if status == "issued":
        from services.book_date import periksa_periode_dokumen_409
        await periksa_periode_dokumen_409(eid, None, jenis="nota debit" if kind == "debit_note" else "nota kredit")
    capped = kind == "credit_note" and source in CAPPED_SOURCES
    token = await _kunci(oid) if capped else ""
    try:
        fresh = await db.sales_orders.find_one({"id": oid}, {"_id": 0}) or order
        if capped:
            await assert_cap(fresh, gross)
        plan: Dict[str, Any] = {}
        if status == "issued" and (kind == "debit_note" or source in ("amendment", "od_item_cancel")):
            plan = await plan_for(kind=kind, source=source, order=fresh, net=net, ppn=ppn)
        now = now_iso()
        doc: Dict[str, Any] = {k: v for k, v in (extra or {}).items() if k not in _FIELD_INTI}
        doc.update({k: v for k, v in (refs or {}).items() if k not in _FIELD_INTI})
        doc.update(plan)
        doc.update({
            "id": new_id("dn" if kind == "debit_note" else "cn"), "number": number, "kind": kind, "source": source,
            "order_id": oid, "order_number": fresh.get("number", ""),
            "customer_id": fresh.get("customer_id"), "customer_name": fresh.get("customer_name", ""), "entity_id": eid,
            "lines": list(lines or []), "net_amount": net, "ppn_amount": ppn, "gross_amount": gross,
            "cogs_amount": round(float(cogs or 0), 2),
            "direction": doc.get("direction") or ("increase" if kind == "debit_note" else "decrease"),
            "status": status, "effects": {s: "pending" for s in STEPS},
            "gl_status": "pending" if status == "issued" else "", "gl_error": "", "journal_entry_id": "",
            "created_by": doc.get("created_by") or _nama(actor), "created_at": now, "updated_at": now,
            "refs": [],   # jejak dua arah ditulis `doc_refs_service` oleh pembuatnya
        })
        if status == "issued":
            doc["issued_at"] = now
        await db.credit_notes.insert_one(dict(doc))
    finally:
        if token:
            await _lepas(oid, token)
    return doc


async def release(note_id: str, actor: Any, *, issue_note: str = "") -> Dict[str, Any]:
    """Nota `pending_finance` (batal item) diterbitkan: rencana dihitung saat ini (PERIKSA periode bila ada jurnal),
    status `issued` (bersyarat masih `pending_finance`), lalu `settle`."""
    doc = await _nota(note_id)
    if note_status(doc) != "pending_finance":
        raise CreditNoteError(f"Nota {doc.get('number')} sudah berstatus "
                              f"'{LABEL_STATUS.get(note_status(doc), note_status(doc))}'.")
    order = await _pesanan(doc["order_id"])
    plan = await plan_for(kind=note_kind(doc), source=note_source(doc), order=order,
                          net=float(doc.get("net_amount") or 0), ppn=float(doc.get("ppn_amount") or 0))
    if float(plan.get("revenue_reversed_net") or 0) + float(plan.get("revenue_reversed_ppn") or 0) > EPS:
        from services.book_date import periksa_periode_dokumen_409
        await periksa_periode_dokumen_409(doc.get("entity_id") or "", None, jenis="nota kredit")
    now = now_iso()
    res = await db.credit_notes.update_one({"id": note_id, "status": "pending_finance"}, {"$set": {
        **plan, "status": "issued", "issued_by": _nama(actor), "issued_at": now, "issue_note": issue_note,
        "effects": {s: "pending" for s in STEPS}, "gl_status": "pending", "gl_error": "", "updated_at": now}})
    if not res.modified_count:
        raise CreditNoteError("Nota baru saja diproses pengguna lain. Muat ulang.")
    return await settle(note_id, actor)


# ── EFEK ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _tandai(note_id: str, step: str, value: str, extra: Optional[Dict[str, Any]] = None) -> None:
    await db.credit_notes.update_one({"id": note_id, f"effects.{step}": {"$ne": "done"}},
                                     {"$set": {f"effects.{step}": value, **(extra or {}), "updated_at": now_iso()}})


async def _alokasi(note: Dict[str, Any], order: Dict[str, Any], actor: Any) -> Tuple[str, Dict[str, Any]]:
    """→ (penanda, field tambahan). Nota kredit: baris `payments[]`; nota debit: baris tagihan tambahan."""
    from services import ar_allocation_service as aas
    nid, src = note["id"], note_source(note)
    if note_kind(note) == "debit_note":
        return await _baris_tagihan(note, order)
    for row in note.get("debit_note_offsets") or []:   # nota debit lama yang belum ditagih (lihat `_dn_offsets`)
        res = await db.credit_notes.update_one(
            {"id": row["debit_note_id"], "offsets.credit_note_id": {"$ne": nid}},
            {"$inc": {"open_amount": -float(row["amount"])}, "$set": {"updated_at": now_iso()},
             "$push": {"offsets": {"credit_note_id": nid, "credit_note_number": note.get("number", ""),
                                   "amount": float(row["amount"]), "at": now_iso()}}})
        if res.modified_count:
            dn = await db.credit_notes.find_one({"id": row["debit_note_id"]}, {"_id": 0, "open_amount": 1}) or {}
            if float(dn.get("open_amount") or 0) <= 0.005:
                await db.credit_notes.update_one({"id": row["debit_note_id"]},
                                                 {"$set": {"billing_status": "offset_by_credit_note"}})
    total = round(float(note.get("allocation_amount") or 0), 2)
    if src == "od_item_cancel" or total <= EPS:
        return "skipped", {"ar_applied": 0.0}
    if src == "amendment":
        deferred = round(float(note.get("allocation_deferred") or 0), 2)
        parts = [("", round(total - deferred, 2), BUCKET_KOREKSI), ("tangguh", deferred, BUCKET_TANGGUH)]
    else:
        parts = [("", total, "")]
    applied = 0.0
    for seq, amount, bucket in parts:
        if amount <= EPS:
            continue
        pid = aas.payment_id("nota_kredit", nid, order["id"], seq)
        cur = await db.sales_orders.find_one({"id": order["id"]}, {"_id": 0}) or order
        if not any(p.get("id") == pid for p in cur.get("payments") or []):
            amount = round(min(amount, outstanding(cur)), 2)   # sisa tagihan berubah sejak rencana dibuat
            if amount <= EPS:
                continue
        await aas.allocate(kind="nota_kredit", order_id=order["id"], amount=amount, source_id=nid,
                           source_number=note.get("number", ""),
                           customer_id=note.get("customer_id") or order.get("customer_id") or "",
                           entity_id=note.get("entity_id") or order.get("entity_id") or "", date=now_iso(),
                           actor=_nama(actor), method="credit_note", seq=seq,
                           extra={"gl_bucket": bucket} if bucket else None)
        applied = round(applied + amount, 2)
    return ("done" if applied > EPS else "skipped"), {"ar_applied": applied}


async def due_date_of(note: Dict[str, Any], order: Dict[str, Any]) -> str:
    """Jatuh tempo tagihan tambahan = tanggal nota + hari termin pesanan (aturan termin yang sama dengan umur piutang)."""
    from services.customer_service import _term_days, due_context
    customer = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0}) or {}
    ctx = await due_context([order])
    days = _term_days(customer, order, ctx.get("terms"))
    from services.book_date import tanggal_buku
    base = datetime.fromisoformat(tanggal_buku(note.get("issued_at") or note.get("created_at") or ""))
    return (base + timedelta(days=days)).date().isoformat()


async def _baris_tagihan(note: Dict[str, Any], order: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Nota debit → satu baris `sales_orders.extra_billing_lines[]` (K-14); `grand_total` dan `items[]` tidak diubah."""
    gross = round(float(note.get("bill_gross", note.get("gross_amount")) or 0), 2)
    ppn = round(float(note.get("bill_ppn", note.get("ppn_amount")) or 0), 2)
    if gross <= EPS:
        return "skipped", {"billing_status": "billed"}
    labels = ", ".join(f"{ln.get('product_name') or ln.get('product_id') or ''} {ln.get('label') or ln.get('field') or ''}"
                       .strip() for ln in note.get("lines") or [] if ln)
    row = {"id": new_id("xbl"), "debit_note_id": note["id"], "debit_note_number": note.get("number", ""),
           "description": note.get("reason_label") or labels or "Nota debit", "net": round(gross - ppn, 2),
           "ppn": ppn, "gross": gross, "due_date": await due_date_of(note, order), "created_at": now_iso()}
    await db.sales_orders.update_one(
        {"id": order["id"], "extra_billing_lines.debit_note_id": {"$ne": note["id"]}},
        {"$push": {"extra_billing_lines": row}, "$set": {"updated_at": now_iso()}})
    try:   # status bayar & rencana bayar mengikuti nilai tagihan baru (turunan)
        from services import ar_allocation_service as aas
        await aas._segarkan(order["id"])
    except Exception as exc:  # noqa: BLE001 — turunan, bukan syarat sah tagihan tambahan
        _log.warning("status bayar %s gagal disegarkan: %s", order.get("number"), exc)
    return "done", {"billing_status": "billed", "open_amount": 0.0}


async def _saldo_kredit(note: Dict[str, Any], order: Dict[str, Any], actor: Any) -> str:
    amount = round(float(note.get("store_credit_part") or 0), 2)
    if note_kind(note) != "credit_note" or note_source(note) not in ("amendment", "od_item_cancel") or amount <= EPS:
        return "skipped"
    from services import store_credit_service
    label = "amandemen" if note_source(note) == "amendment" else "batal item"
    await store_credit_service.issue(
        customer_id=note.get("customer_id") or order.get("customer_id") or "", entity_id=note.get("entity_id", ""),
        amount=amount, ref_type="credit_note", ref_id=note["id"], ref_number=note.get("number", ""),
        note=f"Sisa nota kredit {label} {note.get('number', '')}", actor=_nama(actor),
        je_id=note.get("journal_entry_id", ""), customer_name=order.get("customer_name", ""))
    return "done"


async def _jurnal(note: Dict[str, Any], *, raise_on_fail: bool) -> Dict[str, Any]:
    """Jurnal nota lewat pintu tahan-gagal → `{gl_status, gl_error, journal_entry_id}`."""
    from services import gl_service as gl
    src, nid = note_source(note), note["id"]
    if src in ("sales_return", "sales_return_roll"):
        ret = await db.sales_returns.find_one({"id": note.get("return_id")}, {"_id": 0})
        if not ret:
            raise CreditNoteError("Retur asal nota kredit tidak ditemukan.", 404)
        if src == "sales_return_roll":
            from services.return_roll_settlement_service import post_settlement_gl
            return await post_settlement_gl(ret, note, raise_on_fail=raise_on_fail)
        from services.return_service import _post_cn_gl
        cn = await _post_cn_gl(ret, note, raise_on_fail=raise_on_fail)
        return {"gl_status": cn.get("gl_status"), "gl_error": cn.get("gl_error", ""),
                "journal_entry_id": cn.get("journal_entry_id", "")}
    if note_kind(note) == "debit_note":
        return await gl.post_durable("credit_notes", nid, lambda: gl.post_amendment_debit_note(note),
                                     source_type="amendment_debit_note", source_id=nid, raise_on_fail=raise_on_fail)
    return await gl.post_durable(
        "credit_notes", nid,
        lambda: gl.post_amendment_credit_note(note, ar_part=float(note.get("ar_part") or 0),
                                              store_credit_part=float(note.get("store_credit_part") or 0)),
        source_type="amendment_credit_note", source_id=nid, raise_on_fail=raise_on_fail)


async def settle(note_id: str, actor: Any, *, raise_on_fail: bool = False) -> Dict[str, Any]:
    """Jalankan langkah yang belum `done` (alokasi → saldo kredit → jurnal); semuanya tuntas → `posted`. Aman diulang:
    alokasi ber-id dari id nota, saldo kredit idempoten per rujukan nota, baris tagihan bersyarat id nota, jurnal
    idempoten per (`source_type`, id nota). Jurnal gagal → nota tetap `issued`, `gl_status="failed"` (`raise_on_fail`
    = lempar, dipakai Ulang Posting panel)."""
    note = await _nota(note_id)
    st = note_status(note)
    eff = _effects_of(note)
    if st == "posted" and all(v in ("done", "skipped") for v in eff.values()):
        return normalize(note)
    if st in ("void", "pending_finance"):
        raise CreditNoteError(f"Nota {note.get('number')} berstatus '{LABEL_STATUS.get(st, st)}' — "
                              "tidak ada efek yang bisa dituntaskan.")
    if not (isinstance(note.get("effects"), dict) and note["effects"]):
        # nota lama (sebelum PK-32): penanda dibentuk sekali dari keadaannya supaya langkah lain tidak diulang
        await db.credit_notes.update_one({"id": note_id, "effects": {"$exists": False}}, {"$set": {"effects": eff}})
    order = await _pesanan(note["order_id"])
    if eff["allocation"] == "pending":
        mark, extra = await _alokasi(note, order, actor)
        await _tandai(note_id, "allocation", mark, extra)
        note = await _nota(note_id)
    if eff["store_credit"] == "pending":
        await _tandai(note_id, "store_credit", await _saldo_kredit(note, order, actor))
        note = await _nota(note_id)
    if eff["journal"] == "pending":
        jr = await _jurnal(note, raise_on_fail=raise_on_fail)
        if jr.get("gl_status") == "failed":
            _log.error("jurnal nota %s gagal: %s", note.get("number"), jr.get("gl_error"))
            return normalize(await _nota(note_id))
        jid = jr.get("journal_entry_id") or ""
        await _tandai(note_id, "journal", "done" if jr.get("gl_status") == "posted" else "skipped")
        if jid:
            await db.store_credit_ledger.update_many(
                {"type": "issue", "ref_type": "credit_note", "ref_id": note_id, "journal_entry_id": {"$in": ["", None]}},
                {"$set": {"journal_entry_id": jid}})
    note = await _nota(note_id)
    if all(v in ("done", "skipped") for v in _effects_of(note).values()):
        await db.credit_notes.update_one({"id": note_id, "status": "issued"},
                                         {"$set": {"status": "posted", "posted_at": now_iso(), "updated_at": now_iso()}})
        note = await _nota(note_id)
    return normalize(note)


async def void(note_id: str, reason: str, actor: Any) -> Dict[str, Any]:
    """Batalkan nota `pending_finance`/`issued` yang belum satu efek pun `done` (alasan ≥ 5 huruf)."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise CreditNoteError("Alasan pembatalan nota wajib (minimal 5 huruf).", 400)
    doc = await _nota(note_id)
    st = note_status(doc)
    if st not in ("pending_finance", "issued") or any(v == "done" for v in _effects_of(doc).values()):
        raise CreditNoteError(f"Nota {doc.get('number')} sudah mengurangi tagihan atau sudah dijurnal, jadi tidak bisa "
                              "dibatalkan.")
    flt: Dict[str, Any] = {"id": note_id, "status": doc.get("status")}
    for s in STEPS:
        flt[f"effects.{s}"] = {"$ne": "done"}
    now = now_iso()
    res = await db.credit_notes.update_one(flt, {"$set": {"status": "void", "void_reason": reason,
                                                          "voided_by": _nama(actor), "voided_at": now,
                                                          "updated_at": now}})
    if not res.modified_count:
        raise CreditNoteError("Nota baru saja diproses pengguna lain. Muat ulang.")
    return normalize(await _nota(note_id))


# ── Nota debit lama (`awaiting_billing_rule`) — dipakai skrip migrasi ─────────────────────────────────────────────────
async def awaiting_debit_notes() -> List[Dict[str, Any]]:
    return await db.credit_notes.find({"kind": "debit_note", "billing_status": "awaiting_billing_rule"},
                                      {"_id": 0}).sort([("created_at", 1), ("id", 1)]).to_list(5000)


async def bill_legacy_debit_note(note_id: str, actor: Any) -> Dict[str, Any]:
    """Nota debit lama yang menunggu aturan tagih → ditagihkan lewat mesin ini: sisa terbukanya (`open_amount`, sesudah
    ditutup nota kredit) menjadi baris tagihan tambahan, bagian yang sudah terkirim dijurnal, lalu `settle`."""
    doc = await _nota(note_id)
    if doc.get("billing_status") != "awaiting_billing_rule":
        return normalize(doc)
    order = await _pesanan(doc["order_id"])
    gross = round(float(doc.get("gross_amount") or 0), 2)
    open_amt = round(float(doc.get("open_amount", gross) or 0), 2)
    frac = (open_amt / gross) if gross > EPS else 0.0
    ppn = round(float(doc.get("ppn_amount") or 0) * frac, 2)
    net = round(open_amt - ppn, 2)
    plan = await plan_for(kind="debit_note", source="amendment", order=order, net=net, ppn=ppn)
    now = now_iso()
    res = await db.credit_notes.update_one({"id": note_id, "billing_status": "awaiting_billing_rule"}, {"$set": {
        **plan, "source": note_source(doc) or "amendment", "status": "issued", "bill_gross": open_amt, "bill_ppn": ppn,
        "effects": {"allocation": "pending", "store_credit": "skipped", "journal": "pending"},
        "gl_status": "pending", "gl_error": "", "migrated_pk32_at": now, "migrated_pk32_by": _nama(actor),
        "updated_at": now}})
    if not res.modified_count:
        return normalize(await _nota(note_id))
    return await settle(note_id, actor)
