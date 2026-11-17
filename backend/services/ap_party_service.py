"""S5 (pelatihan keuangan 18 Nov, permintaan pemilik: hutang & piutang per pihak) — **Hutang per Pemasok**.

Pemilik: "sekarang hanya berdasarkan PO atau SO … saya ingin ada UI di finance yang view-nya per orang atau supplier, di
klik muncul semua hutang atau piutangnya dan bisa aksi bayar juga". Sisi piutang sudah ada (Keuangan › Piutang › Saldo &
Umur, `ar_aging_service`); sisi hutang dulu hanya per dokumen (Hutang › Tagihan & Kontrabon).

Tidak ada angka baru yang disimpan: semuanya dibaca dari pemilik yang sudah ada (D1).
  * Tagihan berhutang terbuka, jatuh tempo, hari lewat = `vendor_bill_service.open_payables` (pembaca yang sama dengan
    ringkasan Hutang › Tagihan `GET /vendor-bills/payables/summary` dan kartu pemasok `GET /suppliers/{id}/360`).
  * Kelompok umur = `vendor_bill_service.ap_aging_bucket` (sama dengan ringkasan Hutang › Tagihan).
  * Tagihan yang sedang dipegang kontrabon aktif tidak boleh dibayar langsung (PK-05) — dipetakan dari `contra_bons`
    berstatus selain `paid`/`cancelled` (aturan `contra_bon_service.active_holder_of`).
  * Potongan yang belum dipakai (nota debit retur beli + uang muka ke pemasok) = `contra_bon_service.available_credits`
    (sumber yang sama dengan pilihan potongan di form kontrabon).
  * Kontrabon bisa dibayar bila statusnya ada di `ap_payment_service.cb_payable_statuses` (kebijakan PT).

Satu baris daftar = satu pasangan (pemasok, PT): angka lintas PT tidak dijumlah dalam satu baris (N3).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core_utils import from_cents, to_cents
from db import db

#: Status kontrabon yang masih memegang tagihannya (aturan `contra_bon_service.active_holder_of`).
_CB_CLOSED = ("paid", "cancelled")


async def _pt_names(ids: List[str]) -> Dict[str, str]:
    from services.party_card import _nama_pt
    return await _nama_pt([i for i in ids if i])


async def _holders(bill_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """{bill_id: {id, number, status, status_label}} kontrabon AKTIF yang memegang tagihan (satu kueri)."""
    from services.contra_bon_service import STATUS_LABEL
    out: Dict[str, Dict[str, Any]] = {}
    if not bill_ids:
        return out
    async for cb in db.contra_bons.find({"bills.bill_id": {"$in": bill_ids}, "status": {"$nin": list(_CB_CLOSED)}},
                                        {"_id": 0, "id": 1, "number": 1, "status": 1, "bills.bill_id": 1}):
        info = {"id": cb.get("id", ""), "number": cb.get("number", ""), "status": cb.get("status", ""),
                "status_label": STATUS_LABEL.get(cb.get("status", ""), cb.get("status", ""))}
        for b in cb.get("bills") or []:
            if b.get("bill_id") in bill_ids:
                out[b["bill_id"]] = info
    return out


async def _credits(supplier_id: str, entity_id: str) -> Dict[str, Any]:
    """Potongan belum dipakai pemasok di satu PT: nota debit (retur beli potong hutang) + uang muka ke pemasok."""
    from services.contra_bon_service import available_credits
    cr = await available_credits(supplier_id, entity_id)
    notes = cr.get("purchase_returns") or []
    adv = cr.get("supplier_advances") or []
    # Review S5 (R-S5-01) — `available_credits` menyaring nota debit per PT tetapi uang muka (`ap_advance`) TIDAK: uang
    # muka pemasok dari PT lain ikut, sehingga baris PT lain menampilkannya dan "Semua PT" menjumlahnya sekali per PT.
    # Uang muka milik PT kas-nya (`cash_transactions.entity_id` = PT tagihan yang lebih bayar, `ap_payment_service`).
    if adv:
        ids = [x.get("ref_id") for x in adv if x.get("ref_id")]
        pemilik = {t["id"]: t.get("entity_id") or "" async for t in db.cash_transactions.find(
            {"id": {"$in": ids}}, {"_id": 0, "id": 1, "entity_id": 1})}
        adv = [x for x in adv if pemilik.get(x.get("ref_id")) == entity_id]
    return {"debit_notes": from_cents(sum(to_cents(x.get("amount")) for x in notes)), "debit_note_count": len(notes),
            "advance": from_cents(sum(to_cents(x.get("amount")) for x in adv)), "advance_count": len(adv),
            "items": [{**x, "entity_id": entity_id} for x in notes + adv]}


def _tgl_buku(nilai: Any) -> str:
    """Tanggal buku WIB tagihan (agen zona waktu 18 Nov): tagihan makloon menyimpan `bill_date = now_iso()` (UTC) —
    dulu dipotong 10 huruf sehingga tagihan pukul 00.00–07.00 WIB tampil bertanggal kemarin."""
    if not nilai:
        return ""
    from services.book_date import tanggal_buku
    try:
        return tanggal_buku(nilai)
    except ValueError:
        return str(nilai)[:10]


def _bill_row(item: Dict[str, Any], holder: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    from services.vendor_bill_service import AP_AGING_LABELS, ap_aging_bucket
    b, fin = item["bill"], item["fin"]
    bucket = ap_aging_bucket(item["days"])
    return {
        "bill_id": b.get("id", ""), "bill_number": b.get("bill_number", ""),
        "supplier_invoice_no": b.get("supplier_invoice_no", ""), "po_id": b.get("po_id") or "",
        "po_number": b.get("po_number", ""), "entity_id": b.get("entity_id", ""),
        "bill_date": _tgl_buku(b.get("bill_date") or b.get("created_at")),
        "due_date": item["due"] or "", "due_basis": item["basis"], "days_past_due": item["days"],
        "aging_bucket": bucket, "aging_label": AP_AGING_LABELS[bucket],
        "grand_total": fin["grand_total"], "amount_paid": fin["amount_paid"], "outstanding": fin["outstanding"],
        "status": b.get("status", ""), "contra_bon": holder,
    }


async def supplier_rows(scope_q: Dict[str, Any]) -> Dict[str, Any]:
    """Daftar Hutang per Pemasok: satu baris per (pemasok, PT) yang punya tagihan berhutang terbuka.

    `scope_q` = saringan PT dari `resolve_list_scope("vendor_bills", …)`. Baris diurut: lewat jatuh tempo terbesar,
    lalu sisa hutang terbesar. Kelompok umur sama dengan ringkasan Hutang › Tagihan."""
    from services.vendor_bill_service import AP_AGING_KEYS, AP_AGING_LABELS, ap_aging_bucket, open_payables
    items = await open_payables(scope_q)
    holders = await _holders([it["bill"].get("id", "") for it in items])
    rows: Dict[Tuple[str, str], Dict[str, Any]] = {}
    tot_aging = {k: 0 for k in AP_AGING_KEYS}
    tot_sen = 0
    for it in items:
        b = it["bill"]
        sid = b.get("supplier_id") or ""
        eid = b.get("entity_id") or ""
        sen = to_cents(it["fin"]["outstanding"])
        bucket = ap_aging_bucket(it["days"])
        r = rows.setdefault((sid, eid), {
            "supplier_id": sid, "supplier_name": b.get("supplier_name") or "—", "entity_id": eid,
            "bill_count": 0, "_sen": 0, "_aging": {k: 0 for k in AP_AGING_KEYS}, "_overdue": 0,
            "nearest_due": "", "max_days_past_due": 0, "held_count": 0, "_held": 0})
        r["bill_count"] += 1
        r["_sen"] += sen
        r["_aging"][bucket] += sen
        if it["days"] > 0:
            r["_overdue"] += sen
        r["max_days_past_due"] = max(r["max_days_past_due"], int(it["days"] or 0))
        if it["due"] and (not r["nearest_due"] or it["due"] < r["nearest_due"]):
            r["nearest_due"] = it["due"]
        if b.get("id") in holders:
            r["held_count"] += 1
            r["_held"] += sen
        tot_aging[bucket] += sen
        tot_sen += sen
    names = await _pt_names(sorted({e for _, e in rows}))
    out: List[Dict[str, Any]] = []
    tot_adv = tot_dn = 0
    for (sid, eid), r in rows.items():
        kosong = {"advance": 0.0, "debit_notes": 0.0, "advance_count": 0, "debit_note_count": 0}
        cr = await _credits(sid, eid) if sid else kosong
        tot_adv += to_cents(cr["advance"])
        tot_dn += to_cents(cr["debit_notes"])
        out.append({
            "supplier_id": sid, "supplier_name": r["supplier_name"], "entity_id": eid,
            "entity_label": names.get(eid, eid), "bill_count": r["bill_count"],
            "outstanding": from_cents(r["_sen"]), "overdue": from_cents(r["_overdue"]),
            "aging": {k: from_cents(v) for k, v in r["_aging"].items()},
            "nearest_due": r["nearest_due"], "max_days_past_due": r["max_days_past_due"],
            "held_count": r["held_count"], "held_outstanding": from_cents(r["_held"]),
            "advance": cr["advance"], "advance_count": cr["advance_count"],
            "debit_notes": cr["debit_notes"], "debit_note_count": cr["debit_note_count"],
        })
    out.sort(key=lambda x: (-x["overdue"], -x["outstanding"], x["supplier_name"]))
    return {
        "rows": out,
        "aging_labels": [{"key": k, "label": AP_AGING_LABELS[k]} for k in AP_AGING_KEYS],
        "totals": {"outstanding": from_cents(tot_sen), "aging": {k: from_cents(v) for k, v in tot_aging.items()},
                   "overdue": from_cents(sum(v for k, v in tot_aging.items() if k != "not_due")),
                   "bill_count": len(items), "supplier_count": len({s for s, _ in rows}), "row_count": len(out),
                   "advance": from_cents(tot_adv), "debit_notes": from_cents(tot_dn)},
    }


async def _tolerance(entity_id: str) -> Optional[float]:
    """Toleransi selisih bayar pemasok PT (`payment.variance_ap_tolerance_rupiah`), sama dengan rincian tagihan."""
    from services.config_resolver import resolve
    try:
        return round(float((await resolve("payment.variance_ap_tolerance_rupiah", {"entity_id": entity_id}))["value"]
                           or 0), 2)
    except Exception:  # noqa: BLE001 — pengaturan tak terbaca tidak boleh menggagalkan rincian
        return None


async def supplier_detail(supplier_id: str, scope_ids: List[str], scope_q: Dict[str, Any], *,
                          with_contra_bons: bool = True) -> Optional[Dict[str, Any]]:
    """Rincian hutang satu pemasok di PT dalam cakupan: tagihan terbuka (umur, kontrabon pemegang, toleransi bayar),
    kontrabon terbuka (boleh dibayar sekarang atau belum), dan potongan belum dipakai. None = pemasok tidak ada."""
    from services import contra_bon_service as cbs
    from services.ap_payment_service import cb_payable_statuses
    from services.vendor_bill_service import AP_AGING_KEYS, AP_AGING_LABELS, open_payables
    sup = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0, "id": 1, "name": 1, "code": 1, "entity_id": 1,
                                                            "payment_term_code": 1, "status": 1})
    if not sup:
        return None
    items = await open_payables({**(scope_q or {}), "supplier_id": supplier_id})
    holders = await _holders([it["bill"].get("id", "") for it in items])
    if not with_contra_bons:
        # Review S5 (R-S5-03) — tanpa `contra_bon.view` hanya FAKTA "dipegang kontrabon" (alasan tidak bisa dibayar
        # langsung) yang dikirim; nomor, status, dan id kontrabonnya tidak (dulu bocor lewat baris tagihan).
        holders = {k: {"id": "", "number": "", "status": "", "status_label": ""} for k in holders}
    bills = [_bill_row(it, holders.get(it["bill"].get("id", ""))) for it in items]
    bills.sort(key=lambda r: (r["due_date"] or "9999-99-99", r["bill_number"]))
    ents = sorted({b["entity_id"] for b in bills} | set(scope_ids or []))
    tol = {e: await _tolerance(e) for e in ents}
    for b in bills:
        b["payment_tolerance"] = tol.get(b["entity_id"])
    cbs_out: Optional[List[Dict[str, Any]]] = None
    if with_contra_bons:
        cbs_out = []
        pol_cache: Dict[str, Dict[str, Any]] = {}
        for cb in await cbs.list_contra_bons(scope_ids, "", supplier_id=supplier_id, limit=500):
            if cb.get("status") in _CB_CLOSED:
                continue
            e = cb.get("entity_id") or ""
            if e not in pol_cache:
                pol_cache[e] = await cbs.policy(e)
            t = cb.get("totals") or {}
            cbs_out.append({
                "id": cb.get("id", ""), "number": cb.get("number", ""), "entity_id": e,
                "status": cb.get("status", ""), "status_label": cb.get("status_label", ""),
                "bill_count": len(cb.get("bills") or []), "net_payable": t.get("net_payable", 0),
                "deductions_total": t.get("deductions_total", 0), "outstanding": t.get("outstanding", 0),
                "payable": cb.get("status") in cb_payable_statuses(pol_cache[e]),
                "scheduled_date": (cb.get("schedule") or {}).get("date", ""),
            })
    credits: List[Dict[str, Any]] = []
    for e in ents:
        credits.extend((await _credits(supplier_id, e))["items"])
    names = await _pt_names(ents)
    aging = {k: 0 for k in AP_AGING_KEYS}
    for b in bills:
        aging[b["aging_bucket"]] += to_cents(b["outstanding"])
    sen = sum(to_cents(b["outstanding"]) for b in bills)
    return {
        "supplier": {k: sup.get(k) for k in ("id", "name", "code", "entity_id", "payment_term_code", "status")},
        "entities": [{"entity_id": e, "label": names.get(e, e)} for e in ents],
        "bills": bills, "contra_bons": cbs_out, "credits": credits,
        "aging_labels": [{"key": k, "label": AP_AGING_LABELS[k]} for k in AP_AGING_KEYS],
        "totals": {
            "outstanding": from_cents(sen), "bill_count": len(bills),
            "aging": {k: from_cents(v) for k, v in aging.items()},
            "overdue": from_cents(sum(v for k, v in aging.items() if k != "not_due")),
            "payable_direct": from_cents(sum(to_cents(b["outstanding"]) for b in bills if not b["contra_bon"])),
            "held": from_cents(sum(to_cents(b["outstanding"]) for b in bills if b["contra_bon"])),
            "credits": from_cents(sum(to_cents(c.get("amount")) for c in credits)),
        },
    }
