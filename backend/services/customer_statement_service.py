"""CR-T5 (RP-05) — REKENING KORAN PELANGGAN disusun dari BARIS JURNAL akun piutang, bukan dari dokumen.

Saldo rekening koran = Σ debit − Σ kredit baris jurnal berakun piutang usaha (`known_codes("penjualan.piutang")`, semua
akun yang pernah dipakai PT itu) yang SUMBERNYA milik pelanggan itu, di PT itu — sehingga per tanggal berapa pun saldonya
sama dengan buku besar (aturan tanggal & status sama dengan `report_basis.saldo_akun_sen`: jurnal tidak-void, `date` ≤
akhir hari). Bagian `penalties` memakai akun piutang denda (`penjualan.piutang_denda`) dan tidak menambah saldo utama.

Pemetaan sumber jurnal → pelanggan ada di SATU fungsi (`customer_of_journal`): pengakuan penjualan (lewat pesanan),
kas kwitansi (lewat kwitansi), nota kredit/debit, retur, keputusan selisih bayar, kasus keuangan, saldo kredit, titipan
mutasi bank, denda; jurnal pembalik mengikuti jurnal asalnya (`ref.reverses_entry_id`). Jurnal akun piutang yang tidak
terpetakan (mis. jurnal manual) tidak tampil — selisihnya sudah dilaporkan INV-BAL-02
(`customer_balance_service.reconcile_gl`).

Catatan (RISIKO unit): uang muka yang belum menjadi pengurang piutang di buku besar tidak muncul di sini; layar menulis
"Titipan dan uang muka ada di kotak Eksposur."
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from core_utils import from_cents, safe_doc, to_cents
from db import db
from services.book_date import tanggal_buku, tanggal_panjang

DOC_SURAT_JALAN, DOC_KWITANSI, DOC_NOTA_KREDIT, DOC_PENYESUAIAN = "surat_jalan", "kwitansi", "nota_kredit", "penyesuaian"
DOC_NOTA_DENDA = "nota_denda"
DOC_LABEL = {DOC_SURAT_JALAN: "Surat jalan", DOC_KWITANSI: "Kwitansi", DOC_NOTA_KREDIT: "Nota kredit",
             DOC_PENYESUAIAN: "Penyesuaian", DOC_NOTA_DENDA: "Nota denda"}
PESAN_SEMUA_PT = "Pilih satu PT untuk rekening koran."
PESAN_TANGGAL = "Tanggal rekening koran harus berupa tanggal yang sah (tahun-bulan-tanggal)."
PESAN_URUTAN = "Tanggal \"Dari\" tidak boleh sesudah tanggal \"Sampai\"."
CATATAN_TITIPAN = "Titipan dan uang muka ada di kotak Eksposur."
JUDUL_PDF = "Rekening Koran Pelanggan"

#: Pesanan → pelanggan: jenis jurnal yang `source_id`-nya (sebelum ":") = id pesanan.
_LEWAT_PESANAN = {"sales_order": DOC_SURAT_JALAN, "advance_reclass": DOC_PENYESUAIAN,
                  "advance_reclass_reversal": DOC_PENYESUAIAN}
#: Dokumen ber-`customer_id` (atau ber-`order_id`): jenis jurnal → (koleksi, jenis baris, jenis Jejak Dokumen, isian nomor).
_LEWAT_DOKUMEN: Dict[str, Tuple[str, str, str, str]] = {
    "ar_receipt_deposit": ("ar_receipts", DOC_KWITANSI, "ar_receipt", "number"),
    "ar_receipt_deposit_void": ("ar_receipts", DOC_KWITANSI, "ar_receipt", "number"),
    "amendment_credit_note": ("credit_notes", DOC_NOTA_KREDIT, "credit_note", "number"),
    "amendment_debit_note": ("credit_notes", DOC_PENYESUAIAN, "credit_note", "number"),
    "sales_return": ("sales_returns", DOC_NOTA_KREDIT, "sales_return", "number"),
    "payment_variance_writeoff": ("payment_variance_decisions", DOC_PENYESUAIAN, "payment_variance", "number"),
    "payment_variance_alloc": ("payment_variance_decisions", DOC_PENYESUAIAN, "payment_variance", "number"),
    "payment_variance_reversal": ("payment_variance_decisions", DOC_PENYESUAIAN, "payment_variance", "number"),
    "finance_case": ("finance_cases", DOC_PENYESUAIAN, "finance_case", "number"),
    "store_credit_redeem": ("store_credit_redemptions", DOC_PENYESUAIAN, "", "number"),
    "penalty": ("penalties", DOC_NOTA_DENDA, "penalty", "number"),
    "penalty_reversal": ("penalties", DOC_NOTA_DENDA, "penalty", "number"),
    "penalty_payment": ("penalties", DOC_KWITANSI, "penalty", "number"),
}
_PROYEKSI = {"_id": 0, "id": 1, "number": 1, "customer_id": 1, "order_id": 1, "ref_type": 1, "ref_id": 1,
             "shipment_no": 1, "customer_name": 1, "holding_allocated": 1, "entity_id": 1}


async def _doc(coll: str, doc_id: Any, cache: Dict[Tuple[str, str], Any]) -> Optional[Dict[str, Any]]:
    key = (coll, str(doc_id or ""))
    if not key[1]:
        return None
    if key not in cache:
        cache[key] = await db[coll].find_one({"id": key[1]}, _PROYEKSI if coll != "journal_entries" else {"_id": 0})
    return cache[key]


async def _muat(coll: str, ids: Iterable[str], cache: Dict[Tuple[str, str], Any]) -> None:
    """Isi `cache` sekaligus untuk banyak id (satu kueri per 500)."""
    perlu = sorted({str(i) for i in ids if i and (coll, str(i)) not in cache})
    for i in range(0, len(perlu), 500):
        part = perlu[i:i + 500]
        for x in part:
            cache[(coll, x)] = None
        async for d in db[coll].find({"id": {"$in": part}}, _PROYEKSI):
            cache[(coll, d["id"])] = d


def _dasar(sid: Any) -> str:
    return str(sid or "").split(":")[0]


async def _pelanggan_pesanan(order_id: Any, cache) -> Tuple[str, Optional[Dict[str, Any]]]:
    o = await _doc("sales_orders", order_id, cache)
    return ((o or {}).get("customer_id") or ""), o


async def _sumber(je: Dict[str, Any], cache: Dict[Tuple[str, str], Any], depth: int = 0) -> Dict[str, Any]:
    """{customer_id, doc_type, doc_number, doc_id, trace_type} dokumen sumber satu jurnal (lihat kepala modul)."""
    ref = je.get("ref") or {}
    st = str(je.get("source_type") or "")
    sid = str(je.get("source_id") or "")
    out = {"customer_id": "", "doc_type": DOC_PENYESUAIAN, "doc_number": je.get("source_label") or je.get("number") or "",
           "doc_id": je.get("id") or "", "trace_type": "journal_entry"}
    asal = ref.get("reverses_entry_id")
    if asal and depth < 3:
        orig = await _doc("journal_entries", asal, cache)
        if orig:
            return {**await _sumber(orig, cache, depth + 1), "reversal": True}
    if st == "shipment_revenue":
        shp = await _doc("shipments", sid, cache)
        cid, _o = await _pelanggan_pesanan(ref.get("order_id") or (shp or {}).get("order_id"), cache)
        return {**out, "customer_id": cid, "doc_type": DOC_SURAT_JALAN,
                "doc_number": je.get("source_label") or (shp or {}).get("shipment_no") or "", "doc_id": sid,
                "trace_type": "shipment"}
    if st in _LEWAT_PESANAN:
        cid, o = await _pelanggan_pesanan(ref.get("order_id") or _dasar(sid), cache)
        return {**out, "customer_id": cid, "doc_type": _LEWAT_PESANAN[st],
                "doc_number": (o or {}).get("number") or out["doc_number"], "doc_id": (o or {}).get("id") or "",
                "trace_type": "sales_order"}
    if st == "cash_transaction":
        txn = await _doc("cash_transactions", sid, cache) or {}
        rt, rid = txn.get("ref_type") or "", txn.get("ref_id") or ""
        if rt == "ar_receipt":
            rc = await _doc("ar_receipts", rid, cache) or {}
            return {**out, "customer_id": rc.get("customer_id") or "", "doc_type": DOC_KWITANSI,
                    "doc_number": rc.get("number") or out["doc_number"], "doc_id": rid, "trace_type": "ar_receipt"}
        if rt == "penalty":
            p = await _doc("penalties", rid, cache) or {}
            return {**out, "customer_id": p.get("customer_id") or "", "doc_type": DOC_KWITANSI,
                    "doc_number": p.get("number") or out["doc_number"], "doc_id": rid, "trace_type": "penalty"}
        if rt in ("sales_order", "order"):
            cid, o = await _pelanggan_pesanan(rid, cache)
            return {**out, "customer_id": cid, "doc_type": DOC_KWITANSI}
        return {**out, "customer_id": txn.get("customer_id") or ""}
    if st in ("cash_holding", "cash_holding_reversal"):
        rc = await _doc("ar_receipts", ref.get("receipt_id"), cache) or {}
        return {**out, "customer_id": rc.get("customer_id") or "", "doc_type": DOC_KWITANSI,
                "doc_number": rc.get("number") or out["doc_number"], "doc_id": rc.get("id") or "",
                "trace_type": "ar_receipt" if rc else "journal_entry"}
    if st == "bank_holding_alloc":
        line_id, _, item_id = sid.partition(":")
        ln = await _doc("bank_statement_lines", line_id, cache) or {}
        item = next((a for a in ln.get("holding_allocated") or [] if a.get("id") == item_id), {})
        cid, _o = await _pelanggan_pesanan(item.get("order_id"), cache)
        return {**out, "customer_id": cid, "doc_type": DOC_KWITANSI}
    if st in _LEWAT_DOKUMEN:
        coll, jenis, trace, fld = _LEWAT_DOKUMEN[st]
        d = await _doc(coll, _dasar(sid), cache) or {}
        cid = d.get("customer_id") or ""
        if not cid:
            cid, _o = await _pelanggan_pesanan(d.get("order_id") or ref.get("order_id"), cache)
        return {**out, "customer_id": cid, "doc_type": jenis, "doc_number": d.get(fld) or out["doc_number"],
                "doc_id": (d.get("id") or _dasar(sid)) if trace else out["doc_id"],
                "trace_type": trace or "journal_entry"}
    # cadangan: rujukan umum di jurnal (bukan jurnal manual tanpa rujukan)
    if ref.get("customer_id"):
        return {**out, "customer_id": str(ref["customer_id"])}
    if ref.get("order_id"):
        cid, _o = await _pelanggan_pesanan(ref["order_id"], cache)
        return {**out, "customer_id": cid}
    if ref.get("receipt_id"):
        rc = await _doc("ar_receipts", ref["receipt_id"], cache) or {}
        return {**out, "customer_id": rc.get("customer_id") or "", "doc_type": DOC_KWITANSI}
    return out


async def customer_of_journal(je: Dict[str, Any], cache: Optional[Dict[Tuple[str, str], Any]] = None) -> str:
    """SATU-SATUNYA pemetaan jurnal → pelanggan (id, atau "" bila tidak terpetakan). `cache` = per panggilan daftar."""
    return (await _sumber(je, cache if cache is not None else {}))["customer_id"]


async def _siapkan(journals: List[Dict[str, Any]], cache: Dict[Tuple[str, str], Any]) -> None:
    """Muat sekaligus dokumen sumber yang paling sering (surat jalan, kas, kwitansi, pesanan, nota)."""
    by: Dict[str, set] = {}
    for je in journals:
        st, sid = je.get("source_type"), str(je.get("source_id") or "")
        if st == "shipment_revenue":
            by.setdefault("shipments", set()).add(sid)
        elif st == "cash_transaction":
            by.setdefault("cash_transactions", set()).add(sid)
        elif st in _LEWAT_DOKUMEN:
            by.setdefault(_LEWAT_DOKUMEN[st][0], set()).add(_dasar(sid))
        oid = (je.get("ref") or {}).get("order_id")
        if oid:
            by.setdefault("sales_orders", set()).add(oid)
    for coll in ("shipments", "cash_transactions", "credit_notes", "sales_returns", "penalties"):
        await _muat(coll, by.get(coll, ()), cache)
    rc = {d.get("ref_id") for (c, _), d in cache.items() if c == "cash_transactions" and d
          and d.get("ref_type") == "ar_receipt"}
    await _muat("ar_receipts", (by.get("ar_receipts") or set()) | rc, cache)
    so = set(by.get("sales_orders") or ()) | {d.get("order_id") for (c, _), d in cache.items()
                                               if c in ("shipments", "credit_notes", "sales_returns") and d}
    await _muat("sales_orders", so, cache)


def _sah(tgl: str) -> bool:
    try:
        return len(tgl) == 10 and tanggal_buku(tgl) == tgl
    except ValueError:
        return False


def periode(date_from: Optional[str], date_to: Optional[str]) -> Tuple[str, str]:
    """(`from`, `to`): `to` bawaan hari ini (WIB); `from` bawaan tanggal 1 bulan `to`. Galat → ValueError berkalimat."""
    to = str(date_to or "").strip() or tanggal_buku()
    if not _sah(to):
        raise ValueError(PESAN_TANGGAL)
    dari = str(date_from or "").strip() or f"{to[:8]}01"
    if not _sah(dari):
        raise ValueError(PESAN_TANGGAL)
    if dari > to:
        raise ValueError(PESAN_URUTAN)
    return dari, to


def _bagian() -> Dict[str, Any]:
    return {"opening_sen": 0, "rows": []}


def _tutup(b: Dict[str, Any]) -> Dict[str, Any]:
    saldo = b["opening_sen"]
    rows = []
    for r in b["rows"]:
        saldo += r.pop("_d") - r.pop("_c")
        rows.append({**r, "balance": from_cents(saldo)})
    return {"opening_balance": from_cents(b["opening_sen"]), "rows": rows, "closing_balance": from_cents(saldo)}


async def statement(customer_id: str, entity_id: str, date_from: Optional[str] = None,
                    date_to: Optional[str] = None) -> Dict[str, Any]:
    """Rekening koran (pelanggan, PT) untuk `from`–`to`: `{customer, entity, from, to, opening_balance, rows[],
    closing_balance, penalties: {opening_balance, rows[], closing_balance}, note}`. `opening_balance` = Σ debit − Σ kredit
    sebelum `from`. Baris: `date, doc_type, doc_label, doc_number, doc_id, trace_type, description, debit, credit,
    balance, je_id, je_number`."""
    from services import credit_profile_service as cps
    from services.gl_mapping_service import known_codes
    dari, sampai = periode(date_from, date_to)
    utama_kode = [c for c in await known_codes("penjualan.piutang", entity_id) if c]
    denda_kode = [c for c in await known_codes("penjualan.piutang_denda", entity_id) if c]
    customer = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0, "id": 1, "name": 1, "code": 1,
                                                                             "addresses": 1, "city": 1}) or {})
    q = {"entity_id": entity_id, "status": {"$ne": "void"}, "lines.account_code": {"$in": utama_kode + denda_kode},
         "date": {"$lte": f"{sampai}T23:59:59.999999"}}
    journals = [je async for je in db.journal_entries.find(
        q, {"_id": 0, "id": 1, "number": 1, "date": 1, "created_at": 1, "source_type": 1, "source_id": 1,
            "source_label": 1, "description": 1, "ref": 1, "lines": 1})]
    journals.sort(key=lambda j: (str(j.get("date") or "")[:10], str(j.get("created_at") or ""), str(j.get("number"))))
    cache: Dict[Tuple[str, str], Any] = {}
    await _siapkan(journals, cache)
    utama, denda = _bagian(), _bagian()
    for je in journals:
        src = await _sumber(je, cache)
        if src["customer_id"] != customer_id:
            continue
        for b, kode in ((utama, utama_kode), (denda, denda_kode)):
            d = sum(to_cents(float(ln.get("debit") or 0)) for ln in je.get("lines") or [] if ln.get("account_code") in kode)
            c = sum(to_cents(float(ln.get("credit") or 0)) for ln in je.get("lines") or [] if ln.get("account_code") in kode)
            if not d and not c:
                continue
            if str(je.get("date") or "") < dari:
                b["opening_sen"] += d - c
                continue
            b["rows"].append({"date": str(je.get("date") or "")[:10], "doc_type": src["doc_type"],
                              "doc_label": DOC_LABEL.get(src["doc_type"], "Penyesuaian"),
                              "doc_number": src["doc_number"], "doc_id": src["doc_id"],
                              "trace_type": src["trace_type"], "reversal": bool(src.get("reversal")),
                              "description": je.get("description") or "",
                              "debit": from_cents(d), "credit": from_cents(c), "_d": d, "_c": c,
                              "je_id": je.get("id") or "", "je_number": je.get("number") or ""})
    pt = (await cps.ringkas_pt([entity_id]) or [{"id": entity_id}])[0]
    return {"customer": {"id": customer_id, "name": customer.get("name") or "", "code": customer.get("code") or ""},
            "entity": pt, "from": dari, "to": sampai, **_tutup(utama), "penalties": _tutup(denda),
            "note": CATATAN_TITIPAN}


def _rp(v: Any) -> str:
    from services.pdf_engine import fmt_rp
    return fmt_rp(v)


def statement_document(st: Dict[str, Any]) -> Dict[str, Any]:
    """Isi dokumen mesin PDF (`pdf_engine.render_html`) untuk rekening koran — kop & gaya dari PT (pemanggil)."""
    cols = [{"key": "date", "label": "Tanggal", "align": ""}, {"key": "doc", "label": "Dokumen", "align": ""},
            {"key": "desc", "label": "Keterangan", "align": ""}, {"key": "debit", "label": "Tagihan", "align": "num"},
            {"key": "credit", "label": "Pembayaran / Kredit", "align": "num"},
            {"key": "balance", "label": "Saldo", "align": "num"}]

    def isi(b: Dict[str, Any]) -> List[Dict[str, Any]]:
        out = [{"date": tanggal_panjang(st["from"]), "doc": "", "desc": "Saldo awal", "debit": "", "credit": "",
                "balance": _rp(b["opening_balance"])}]
        for r in b["rows"]:
            out.append({"date": tanggal_panjang(r["date"]), "doc": f"{r['doc_label']} {r['doc_number']}".strip(),
                        "desc": r["description"], "debit": _rp(r["debit"]) if r["debit"] else "",
                        "credit": _rp(r["credit"]) if r["credit"] else "", "balance": _rp(r["balance"])})
        out.append({"date": tanggal_panjang(st["to"]), "doc": "", "desc": "Saldo akhir", "debit": "", "credit": "",
                    "balance": _rp(b["closing_balance"])})
        return out

    pt = st.get("entity") or {}
    cust = st.get("customer") or {}
    pen = st["penalties"]
    return {
        "title": JUDUL_PDF, "number": cust.get("code") or cust.get("name") or "",
        "date": f"{tanggal_panjang(st['from'])} – {tanggal_panjang(st['to'])}",
        "party_to": {"title": "Kepada", "name": cust.get("name") or ""},
        "meta": [{"label": "PT", "value": pt.get("legal_name") or pt.get("short_name") or ""},
                 {"label": "Periode", "value": f"{tanggal_panjang(st['from'])} – {tanggal_panjang(st['to'])}"},
                 {"label": "Saldo awal", "value": _rp(st["opening_balance"])},
                 {"label": "Saldo akhir", "value": _rp(st["closing_balance"])}],
        "columns": cols, "items": isi(st),
        "totals": [{"label": "Saldo akhir", "value": _rp(st["closing_balance"]), "strong": True}],
        "extra_tables": ([{"title": "Denda", "columns": cols, "items": isi(pen),
                           "note": "Denda tidak menambah saldo piutang usaha di atas."}]
                         if pen["rows"] or pen["opening_balance"] else []),
        "notes": st.get("note") or "",
    }


async def statement_html(st: Dict[str, Any]) -> str:
    """HTML rekening koran berkop PT (gaya dokumen bawaan PT, `pdf_service.get_template_cfg("__default__", PT)`)."""
    from services import pdf_service
    from services.pdf_engine import render_html
    eid = (st.get("entity") or {}).get("id") or ""
    cfg = await pdf_service.get_template_cfg(pdf_service.DEFAULT_CODE, eid)
    return render_html(cfg, await pdf_service.get_branding(eid), statement_document(st))
