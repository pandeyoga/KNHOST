"""Faktur Pajak Masukan (tax_invoices_in) service — Fase 5.5 / P0-3.

Mencatat Faktur Pajak Masukan (Input VAT) dari Vendor Bill ber-PPN agar PPN
Masukan dapat dikreditkan terhadap PPN Keluaran (compliance PKP).

Keputusan desain owner:
  - Sumber  : Vendor Bill (DPP/PPN sudah dihitung di bill, mirror PO P0-1).
  - NSFP    : Nomor Seri Faktur Pajak supplier disimpan + DEDUPE (cegah ganda).
              (tanpa flag creditable — semua faktur tercatat dianggap dikreditkan.)
  - Rekap   : PPN Masukan vs Keluaran per periode (YYYY-MM) → posisi kurang/lebih bayar.

Lifecycle: recorded → cancelled. (Tanpa approval: hanya merekam dokumen pajak
eksternal; kewajiban finansial sudah dibuat oleh Vendor Bill.)
"""
from typing import Any, Dict, List, Optional
from db import db

# Vendor bill yang AP-relevan (lihat vendor_bill_service.AP_BILL_STATUSES).
ELIGIBLE_BILL_STATUSES = {"posted", "paid"}
ACTIVE_INPUT_STATUSES = {"recorded"}


async def next_input_number(entity_id: Optional[str] = None) -> str:
    """KN-A12 — sequence ATOMIK bersama (find_one_and_update $inc), bukan 'nomor tertinggi + 1'.
    KP-T5 — `entity_id` = PT dokumennya (N1): bawaan tetap deret bersama; berlaku bila grup memilih per PT."""
    from core_utils import next_doc_number
    return await next_doc_number("tax_invoices_in", "number", "FPM-", width=5, entity_id=entity_id or None,
                                 scheme="shared", kind="fpm")


def normalize_nsfp(nsfp: Optional[str]) -> str:
    """Ambil digit saja dari NSFP supplier untuk dedupe (abaikan format titik/strip)."""
    return "".join(ch for ch in (nsfp or "") if ch.isdigit())


def kunci_aktif_masukan(doc: Dict[str, Any]) -> Dict[str, str]:
    """PK-40 (SL-13) — field kunci faktur masukan AKTIF (`recorded`): `active_key` = `vb:{vendor_bill_id}` /
    `ic:{interco_pair_id}` (indeks unik `uq_fpm_active`), `nsfp_key` = `nsfp_digits` (`uq_fpm_nsfp`). Tidak aktif → `{}`.
    `nsfp_digits` dipakai bila ada (faktur masukan internal tanpa NSFP DJP menyimpan nomor internal di `nsfp`)."""
    if doc.get("status") not in ACTIVE_INPUT_STATUSES:
        return {}
    out: Dict[str, str] = {}
    if doc.get("vendor_bill_id"):
        out["active_key"] = f"vb:{doc['vendor_bill_id']}"
    elif doc.get("interco_pair_id"):
        out["active_key"] = f"ic:{doc['interco_pair_id']}"
    digits = doc["nsfp_digits"] if "nsfp_digits" in doc else normalize_nsfp(doc.get("nsfp"))
    if digits:
        out["nsfp_key"] = digits
    return out


def format_nsfp_display(nsfp: Optional[str]) -> str:
    """Tampilkan NSFP 16-digit sebagai NNN-NN.NN-NNNNNNNN bila cukup digit."""
    d = normalize_nsfp(nsfp)
    if len(d) >= 16:
        d = d[:16]
        return f"{d[:3]}-{d[3:5]}.{d[5:7]}-{d[7:]}"
    return (nsfp or "").strip()


def period_of(iso_date: Optional[str]) -> str:
    """Periode pajak YYYY-MM dari tanggal faktur (default sekarang)."""
    from services.book_date import periode_buku   # PK-37 — periode WIB (stempel UTC dini hari tgl 1 = bulan baru)
    try:
        return periode_buku(iso_date)
    except ValueError:   # isian tak dikenal: perilaku lama (7 huruf pertama)
        return str(iso_date)[:7]


async def find_active_duplicate_nsfp(nsfp_digits: str, exclude_id: str = "") -> Optional[Dict[str, Any]]:
    """Cari Faktur Masukan AKTIF (recorded) dengan NSFP sama (cegah ganda)."""
    if not nsfp_digits:
        return None
    q: Dict[str, Any] = {"nsfp_digits": nsfp_digits, "status": {"$in": list(ACTIVE_INPUT_STATUSES)}}
    if exclude_id:
        q["id"] = {"$ne": exclude_id}
    return await db.tax_invoices_in.find_one(q, {"_id": 0, "number": 1, "nsfp": 1})


def snapshot_from_bill(bill: Dict[str, Any]) -> Dict[str, Any]:
    """Salin field pajak & referensi dari Vendor Bill ke Faktur Masukan."""
    return {
        "vendor_bill_id": bill.get("id", ""),
        "bill_number": bill.get("bill_number", ""),
        "supplier_invoice_no": bill.get("supplier_invoice_no", ""),
        "po_id": bill.get("po_id", ""),
        "po_number": bill.get("po_number", ""),
        "supplier_id": bill.get("supplier_id", ""),
        "supplier_name": bill.get("supplier_name", ""),
        "supplier_npwp": bill.get("supplier_npwp", ""),
        "entity_id": bill.get("entity_id", ""),
        "dpp": round(float(bill.get("dpp", 0) or 0), 2),
        "ppn_rate": float(bill.get("ppn_rate", 0) or 0),
        "ppn_mode": bill.get("ppn_mode", "excluded"),
        "ppn_amount": round(float(bill.get("ppn_amount", 0) or 0), 2),
        "grand_total": round(float(bill.get("grand_total", 0) or 0), 2),
    }


async def eligible_vendor_bills(entity_id: str = "", entity_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Vendor Bill ber-PPN (posted/paid) yang BELUM punya Faktur Masukan aktif."""
    q: Dict[str, Any] = {
        "status": {"$in": list(ELIGIBLE_BILL_STATUSES)},
        "ppn_amount": {"$gt": 0},
        "$or": [
            {"input_faktur_status": {"$exists": False}},
            {"input_faktur_status": {"$nin": list(ACTIVE_INPUT_STATUSES)}},
        ],
    }
    if entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    elif entity_ids is not None:   # PK-09 — gabungan = PT yang ditugaskan
        q["entity_id"] = {"$in": list(entity_ids)}
    bills = await db.vendor_bills.find(q, {"_id": 0}).sort("bill_date", -1).to_list(500)
    rows = []
    for b in bills:
        rows.append({
            "vendor_bill_id": b.get("id"),
            "bill_number": b.get("bill_number"),
            "supplier_invoice_no": b.get("supplier_invoice_no", ""),
            "supplier_id": b.get("supplier_id", ""),
            "supplier_name": b.get("supplier_name", ""),
            "supplier_npwp": b.get("supplier_npwp", ""),
            "po_number": b.get("po_number", ""),
            "entity_id": b.get("entity_id", ""),
            "bill_date": b.get("bill_date", ""),
            "dpp": round(float(b.get("dpp", 0) or 0), 2),
            "ppn_rate": float(b.get("ppn_rate", 0) or 0),
            "ppn_amount": round(float(b.get("ppn_amount", 0) or 0), 2),
            "grand_total": round(float(b.get("grand_total", 0) or 0), 2),
        })
    return rows


# PK-40 (SL-13) — teks pembanding buku besar di rekap PPN.
SELISIH_NOTE = "Selisih berarti ada jurnal PPN tanpa faktur pajak, atau faktur tanpa jurnal, pada masa ini."
_FIELDS_REKAP = {"_id": 0, "faktur_date": 1, "ppn_amount": 1, "dpp": 1, "supplier_name": 1}


def _jendela_masa(period: str) -> Dict[str, str]:
    """PK-40 — rentang teks `faktur_date` [awal masa − 1 hari, akhir masa + 1 hari] (stempel UTC/WIB di tepi masa ikut
    terambil); baris lalu disaring persis dengan `period_of` (WIB). Batas atas eksklusif = akhir + 2 hari."""
    import calendar
    from datetime import date, timedelta
    y, m = int(period[:4]), int(period[5:7])
    awal = date(y, m, 1)
    akhir = date(y, m, calendar.monthrange(y, m)[1])
    return {"$gte": (awal - timedelta(days=1)).isoformat(), "$lt": (akhir + timedelta(days=2)).isoformat()}


async def _gl_ppn_masa(period: str, entity_q: Dict[str, Any]) -> Dict[str, float]:
    """PK-40 — mutasi akun PPN di buku besar masa itu (jurnal bukan `void`, PT sama, tanggal buku dalam masa):
    keluaran = kredit − debit akun `penjualan.ppn_keluaran`; masukan = debit − kredit akun `pembelian.ppn_masukan`
    (semua kode yang pernah dipakai kebutuhan itu: `known_codes`)."""
    import calendar
    from services.gl_mapping_service import known_codes
    out_codes = set(await known_codes("penjualan.ppn_keluaran"))
    in_codes = set(await known_codes("pembelian.ppn_masukan"))
    y, m = int(period[:4]), int(period[5:7])
    akhir = f"{period}-{calendar.monthrange(y, m)[1]:02d}"
    q = {"status": {"$ne": "void"}, **entity_q, "lines.account_code": {"$in": sorted(out_codes | in_codes)},
         "date": {"$gte": f"{period}-01", "$lte": f"{akhir}T23:59:59.999999"}}   # sama dengan batas laporan
    keluaran = masukan = 0.0
    async for je in db.journal_entries.find(q, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            code = ln.get("account_code")
            dr, cr = float(ln.get("debit") or 0), float(ln.get("credit") or 0)
            if code in out_codes:
                keluaran += cr - dr
            if code in in_codes:
                masukan += dr - cr
    return {"keluaran": round(keluaran, 2), "masukan": round(masukan, 2)}


async def vat_summary(period: str = "", entity_id: str = "", entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Rekap PPN Masukan vs Keluaran untuk satu periode (YYYY-MM).

    Keluaran = Σ ppn_amount faktur berstatus `normal`/`pengganti` (TX-T2; `draf`, `diganti`, `batal` tidak dihitung —
               PK-45 TX-01) − Σ ppn_amount dokumen pajak retur berstatus `normal` (TX-T2, `doc_kind: retur`).
    Masukan  = Σ ppn_amount Faktur Pajak Masukan (tax_invoices_in, status recorded).
    Net      = Keluaran − Masukan → >0 KURANG BAYAR (setor), <0 LEBIH BAYAR (kredit).
    PK-40 (SL-13): masa = `period_of(faktur_date)` (WIB), disaring di kueri lalu persis di baris; kursor dibaca habis
    (tanpa batas 5.000); pembanding `gl_ppn` dari buku besar + `selisih` (rekap − buku besar).
    """
    if not period:   # PK-37 — bulan pajak berjalan WIB (dulu bulan UTC)
        from services.book_date import periode_buku
        period = periode_buku()
    period = period.strip()

    def _in_period(doc: Dict[str, Any]) -> bool:
        return period_of(doc.get("faktur_date", "") or "") == period

    from services.tax_invoice_service import saringan_keluaran_aktif, saringan_retur_aktif
    out_q: Dict[str, Any] = saringan_keluaran_aktif()   # PK-45 (TX-01) — faktur yang sudah diganti tidak dihitung
    ret_q: Dict[str, Any] = saringan_retur_aktif()      # TX-T2 — dokumen pajak retur (pengurang)
    in_q: Dict[str, Any] = {"status": {"$in": list(ACTIVE_INPUT_STATUSES)}}
    ent_q: Dict[str, Any] = {}
    if entity_id and entity_id != "all":
        ent_q = {"entity_id": entity_id}
    elif entity_ids is not None:   # PK-09 — gabungan = PT yang ditugaskan
        ent_q = {"entity_id": {"$in": list(entity_ids)}}
    out_q.update(ent_q)
    ret_q.update(ent_q)
    in_q.update(ent_q)
    try:
        jendela = _jendela_masa(period)
    except ValueError:   # teks masa tak dikenal: tanpa saringan kueri, saringan baris tetap
        jendela = None
    if jendela:
        out_q["faktur_date"] = dict(jendela)
        ret_q["faktur_date"] = dict(jendela)
        in_q["faktur_date"] = dict(jendela)

    out_docs = [d async for d in db.tax_invoices.find(out_q, _FIELDS_REKAP) if _in_period(d)]
    ret_docs = [d async for d in db.tax_invoices.find(ret_q, _FIELDS_REKAP) if _in_period(d)]
    in_docs = [d async for d in db.tax_invoices_in.find(in_q, _FIELDS_REKAP) if _in_period(d)]

    faktur_ppn = round(sum(float(d.get("ppn_amount", 0) or 0) for d in out_docs), 2)
    retur_ppn = round(sum(float(d.get("ppn_amount", 0) or 0) for d in ret_docs), 2)
    keluaran_ppn = round(faktur_ppn - retur_ppn, 2)
    keluaran_dpp = round(sum(float(d.get("dpp", 0) or 0) for d in out_docs)
                         - sum(float(d.get("dpp", 0) or 0) for d in ret_docs), 2)
    masukan_ppn = round(sum(float(d.get("ppn_amount", 0) or 0) for d in in_docs), 2)
    masukan_dpp = round(sum(float(d.get("dpp", 0) or 0) for d in in_docs), 2)

    net = round(keluaran_ppn - masukan_ppn, 2)
    if net > 0.01:
        position, position_label = "kurang_bayar", "PPN Kurang Bayar (setor ke negara)"
    elif net < -0.01:
        position, position_label = "lebih_bayar", "PPN Lebih Bayar (kredit dibawa ke periode berikutnya)"
    else:
        position, position_label = "nihil", "PPN Nihil"

    # ringkas Masukan per supplier
    by_supplier: Dict[str, Dict[str, Any]] = {}
    for d in in_docs:
        key = d.get("supplier_name") or "—"
        s = by_supplier.setdefault(key, {"supplier_name": key, "ppn": 0.0, "dpp": 0.0, "count": 0})
        s["ppn"] = round(s["ppn"] + float(d.get("ppn_amount", 0) or 0), 2)
        s["dpp"] = round(s["dpp"] + float(d.get("dpp", 0) or 0), 2)
        s["count"] += 1

    gl = await _gl_ppn_masa(period, ent_q) if jendela else {"keluaran": 0.0, "masukan": 0.0}
    return {
        "period": period,
        "keluaran": {"ppn": keluaran_ppn, "dpp": keluaran_dpp, "count": len(out_docs), "gl_ppn": gl["keluaran"],
                     "selisih": round(keluaran_ppn - gl["keluaran"], 2),
                     "faktur_ppn": faktur_ppn, "retur_ppn": retur_ppn, "retur_count": len(ret_docs)},
        "masukan": {"ppn": masukan_ppn, "dpp": masukan_dpp, "count": len(in_docs), "gl_ppn": gl["masukan"],
                    "selisih": round(masukan_ppn - gl["masukan"], 2)},
        "selisih_note": SELISIH_NOTE,
        "net_ppn": net,
        "position": position,
        "position_label": position_label,
        "masukan_by_supplier": sorted(by_supplier.values(), key=lambda s: -s["ppn"]),
    }
