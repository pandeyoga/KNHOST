"""MN-T3 — kartu pelanggan & kartu pemasok: bagian kartu menurut izin (K-18) dan bagian keuangan kartu pemasok.

Kartu tidak punya endpoint gabungan sendiri (ASUMSI unit): kepala kartu & daftar bagian dibaca dari `…/360` yang sudah
ada, isi bagian dari endpoint sumbernya masing-masing (aturan izin tiap bagian tetap satu tempat).

* `sections_allowed` = bagian kartu yang izin sumbernya DIPEGANG pemanggil (layar hanya menampilkan bagian itu dan
  tidak memanggil endpoint bagian lain).
* Angka yang sudah ada di jawaban `…/360` dikosongkan (`None`) bila izin sumbernya tidak dipegang — peran tanpa izin
  keuangan tidak melihat nominal (K-18).
* Kartu pemasok: `payables` (saldo hutang · jatuh tempo ≤ 7 hari · uang muka ke pemasok), `bills`, `contra_bons`,
  `payments`, `landed_costs` — diisi dengan memanggil fungsi layanan layar sumbernya (`02` D1); PT dari sesi (N1); mode
  Semua PT memberi angka per PT berlabel PT tanpa dijumlah lintas PT (N3).
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from db import db
from dependencies import has_permission

Izin = Tuple[str, str]

#: Bagian kartu pelanggan → izin (salah satu cukup). Urutan = urutan tampil di layar.
CUSTOMER_SECTIONS: Sequence[Tuple[str, Sequence[Izin]]] = (
    ("ringkasan", (("payment_plan", "view"), ("credit_profile", "view"))),   # kepala: eksposur, plafon, lewat tempo
    ("tagihan", (("payment_plan", "view"),)),                                # Tagihan & Jadwal
    ("pembayaran", (("ar_receipt", "view"),)),                               # kwitansi, deposit, saldo kredit
    ("denda_kasus", (("penalty", "view"), ("finance_case", "view"))),        # Denda & Kasus
    ("tindak_lanjut", (("order", "view"),)),                                 # bagian tindak lanjut …/360
    ("rekening_koran", (("credit_profile", "view"), ("ar_receipt", "view"))),
    ("riwayat", (("order", "view"),)),                                       # Riwayat Lain: pesanan, dokumen, harga, sample
)

#: Bagian kartu pemasok → izin (salah satu cukup).
SUPPLIER_SECTIONS: Sequence[Tuple[str, Sequence[Izin]]] = (
    ("ringkasan", (("vendor_bill", "view"),)),          # kepala: saldo hutang, jatuh tempo 7 hari, uang muka
    ("tagihan", (("vendor_bill", "view"),)),
    ("kontrabon", (("contra_bon", "view"),)),
    ("pembayaran", (("vendor_bill", "view"),)),
    ("retur", (("purchase_return", "view"),)),
    ("po_biaya", (("purchase_order", "view"), ("landed_cost", "view"))),   # PO & Biaya Masuk
    ("lainnya", (("supplier", "view"),)),                                   # harga, dokumen, skor
)

#: Field nominal kredit/piutang di dokumen pelanggan yang ikut tampil di `…/360` (dikosongkan tanpa izin kepala).
_NOMINAL_PELANGGAN = ("credit_limit", "deposit_balance", "ar_outstanding", "outstanding", "overdue_amount",
                      "available_credit", "store_credit_balance", "credit")

JATUH_TEMPO_HARI = 7   # "Jatuh tempo 7 hari" = nama angka di kepala kartu pemasok (spesifikasi layar), bukan aturan


async def _boleh(actor: Dict[str, Any], izin: Sequence[Izin]) -> bool:
    for res, act in izin:
        if await has_permission(actor, res, act):
            return True
    return False


async def allowed(actor: Dict[str, Any], table: Sequence[Tuple[str, Sequence[Izin]]]) -> List[str]:
    return [key for key, izin in table if await _boleh(actor, izin)]


async def customer_card(data: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Jawaban `GET /customers/{id}/360` + `sections_allowed`; angka tanpa izin dikosongkan (K-18)."""
    out = dict(data)
    sec = await allowed(actor, CUSTOMER_SECTIONS)
    out["sections_allowed"] = sec
    if "ringkasan" not in sec:
        for k in _NOMINAL_PELANGGAN:
            if k in out:
                out[k] = None
        out["credit_overrides"] = None
    if "pembayaran" not in sec:
        out["payments"] = None
    if "tindak_lanjut" not in sec:
        out["collection_followups"] = None
    if "riwayat" not in sec:
        for k in ("order_history", "document_history", "special_price_history", "sample_history", "stats"):
            out[k] = None
    return out


# ─── Kartu pemasok ──────────────────────────────────────────────────────────────────────────────────────────────────

async def _nama_pt(ids: List[str]) -> Dict[str, str]:
    names: Dict[str, str] = {}
    # Cek layar MN-T3 (integrator): PT ada di `business_entities` (bukan `entities`) — dulu label jatuh ke kode mentah
    # "PT ent_ksc" di kepala kartu pemasok dan baris hutang per PT.
    async for e in db.business_entities.find({"id": {"$in": ids}},
                                             {"_id": 0, "id": 1, "short_name": 1, "name": 1, "legal_name": 1}):
        names[e["id"]] = e.get("short_name") or e.get("name") or e.get("legal_name") or e["id"]
    return names


def _payment_rows(bills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Baris pembayaran pemasok = `vendor_bills.payments[]` yang tidak dibatalkan (bayar tagihan langsung DAN pelunasan
    lewat kontrabon — pintu PK-05 menulis keduanya ke tagihan), terbaru dulu."""
    rows: List[Dict[str, Any]] = []
    for b in bills:
        for p in b.get("payments") or []:
            if p.get("voided"):
                continue
            rows.append({
                "id": p.get("id", ""), "bill_id": b.get("id", ""), "bill_number": b.get("bill_number", ""),
                "entity_id": b.get("entity_id", ""), "amount": round(float(p.get("amount") or 0), 2),
                "method": p.get("method", ""), "paid_at": p.get("paid_at", ""),
                "cash_txn_number": p.get("cash_txn_number", ""), "contra_bon_number": p.get("contra_bon_number", ""),
                "non_cash": str(p.get("method") or "").endswith(":deduction"), "notes": p.get("notes", ""),
            })
    rows.sort(key=lambda r: str(r.get("paid_at") or ""), reverse=True)
    return rows


async def supplier_card(data: Dict[str, Any], actor: Dict[str, Any], scope_ids: List[str]) -> Dict[str, Any]:
    """Jawaban `GET /suppliers/{id}/360` + bagian keuangan kartu pemasok (MN-T3) + `sections_allowed`.

    `scope_ids` = PT dalam cakupan sesi (`resolve_scope_ids`). Bagian yang izinnya tidak dipegang bernilai `None`."""
    from services import contra_bon_service as cbs
    from services.landed_cost_service import voucher_financials
    from services.vendor_bill_service import bill_financials, open_payables
    from services import report_basis as rb

    out = dict(data)
    sid = out.get("id") or ""
    sec = await allowed(actor, SUPPLIER_SECTIONS)
    out["sections_allowed"] = sec
    ent_q: Dict[str, Any] = {"entity_id": scope_ids[0]} if len(scope_ids) == 1 else {"entity_id": {"$in": scope_ids}}
    names = await _nama_pt(scope_ids)
    out["scope_entities"] = [{"entity_id": e, "label": names.get(e, e)} for e in scope_ids]

    lihat_tagihan = "tagihan" in sec
    if lihat_tagihan:
        bills = [dict(b) for b in await db.vendor_bills.find({"supplier_id": sid, **ent_q}, {"_id": 0})
                 .sort("created_at", -1).to_list(None)]
        for b in bills:
            b["financials"] = bill_financials(b)
        out["bills"] = bills
        out["payments"] = _payment_rows(bills)
        # Kepala kartu: per PT, tanpa dijumlah lintas PT (N3).
        hari_ini = rb.tanggal_buku()
        per: Dict[str, Dict[str, Any]] = {e: {"entity_id": e, "label": names.get(e, e), "outstanding": 0.0,
                                              "due_soon": 0.0, "overdue": 0.0, "advance": 0.0, "bill_count": 0}
                                          for e in scope_ids}
        for item in await open_payables({"supplier_id": sid, **ent_q}):
            e = item["bill"].get("entity_id") or ""
            row = per.setdefault(e, {"entity_id": e, "label": names.get(e, e), "outstanding": 0.0, "due_soon": 0.0,
                                     "overdue": 0.0, "advance": 0.0, "bill_count": 0})
            sisa = item["fin"]["outstanding"]
            row["outstanding"] = round(row["outstanding"] + sisa, 2)
            row["bill_count"] += 1
            if item["due"] and rb.hari_antara(hari_ini, item["due"]) <= JATUH_TEMPO_HARI:
                row["due_soon"] = round(row["due_soon"] + sisa, 2)   # lewat jatuh tempo ikut dihitung
            if item["days"] > 0:
                row["overdue"] = round(row["overdue"] + sisa, 2)
        for e, row in per.items():
            credits = await cbs.available_credits(sid, e)
            row["advance"] = round(sum(float(a.get("amount") or 0) for a in credits["supplier_advances"]), 2)
        rows = [per[e] for e in scope_ids] + [r for e, r in per.items() if e not in scope_ids]
        single = rows[0] if len(scope_ids) == 1 and rows else None
        out["payables"] = {
            "single_entity": bool(single), "entity_id": single["entity_id"] if single else "all",
            "outstanding": single["outstanding"] if single else None,
            "due_soon": single["due_soon"] if single else None,
            "advance": single["advance"] if single else None,
            "due_soon_days": JATUH_TEMPO_HARI, "by_entity": rows,
        }
    else:
        out["bills"] = out["payments"] = out["payables"] = None
        out["vendor_bills"] = None
        out["bill_count"] = out["bill_total"] = None
        fin = dict(out.get("finance") or {})
        for k in ("ap_outstanding", "overdue_amount", "overdue_days", "paid_total", "bill_total"):
            fin[k] = None
        out["finance"] = fin

    if "kontrabon" in sec:
        out["contra_bons"] = await cbs.list_contra_bons(scope_ids, "", supplier_id=sid, limit=500)
    else:
        out["contra_bons"] = None

    if await _boleh(actor, (("landed_cost", "view"),)):
        po_ids = [p.get("id") for p in (out.get("purchase_orders") or []) if p.get("id")]
        vouchers = await db.landed_cost_vouchers.find({"po_ids": {"$in": po_ids}, **ent_q}, {"_id": 0}) \
            .sort("created_at", -1).to_list(None) if po_ids else []
        out["landed_costs"] = [{**v, "financials": voucher_financials(v)} for v in vouchers]
    else:
        out["landed_costs"] = None

    if not await _boleh(actor, (("purchase_order", "view"),)):
        out["purchase_orders"] = None
        out["po_count"] = out["po_total_value"] = None
        fin = dict(out.get("finance") or {})
        for k in ("open_po_value", "po_total_value", "purchase_ytd", "open_po_count"):
            fin[k] = None
        out["finance"] = fin
    if "retur" not in sec:
        out["returns"] = None
        out["return_count"] = None

    # Daftar dokumen gabungan (bagian Lainnya) hanya memuat jenis yang izin sumbernya dipegang.
    boleh_jenis = {"vendor_bill": lihat_tagihan, "purchase_order": out.get("purchase_orders") is not None,
                   "purchase_return": "retur" in sec}
    out["documents"] = [d for d in (out.get("documents") or []) if boleh_jenis.get(d.get("doc_type"), True)]
    return out
