"""CR-T2 (CR-06, CR-09; keputusan K-16) — JADWAL TAGIHAN: satu tempat jatuh tempo piutang.

Setiap pesanan yang menimbulkan piutang punya satu jadwal hidup di `payment_plans` (tidak ada koleksi kedua, `02` D1):

* `origin: "term"` — lahir otomatis dari termin pesanan (jadwal mesin; tidak diubah tangan);
* `origin: "manual"` — rencana cicilan buatan orang (`payment_plan_service.create_plan`). Begitu ada, jadwal `term`
  di-void "diganti rencana baru" dan pembuatan otomatis berhenti untuk pesanan itu.

Kapan baris `term` lahir (K-16, tabel spesifikasi):

| Termin | Peristiwa | Baris |
|---|---|---|
| `dp_percent == 0` (tempo, juga tunai) | tiap NOMOR surat jalan dijurnal | `shipment`: nilai = Σ debit akun piutang jurnal `shipment_revenue` semua dokumen bernomor itu; jatuh tempo = tanggal surat jalan + `net_days` |
| `dp_percent > 0` | pesanan dikonfirmasi | `dp`: nilai pesanan × `dp_percent` ÷ 100; jatuh tempo = tanggal konfirmasi ("Sebelum kirim") |
| sama, `dp_percent < 100` | tiap nomor surat jalan dijurnal | `shipment`: nilai piutang surat jalan × (100 − `dp_percent`) ÷ 100; sisa pembulatan ke surat jalan penutup |
| apa pun | nota debit (PK-32 `extra_billing_lines[]`) | `debit_note`: nilai dan jatuh tempo baris tambahan itu |

SATU rumus jatuh tempo: `report_basis.jatuh_tempo(tanggal, report_basis.hari_termin(...))` — rumus yang sama dengan
`report_basis.baris_tagihan` (PK-41). Pembangun baris (`bangun_baris`) dipakai tiga jalur: kait peristiwa (disimpan),
skrip `scripts/build_billing_schedule.py` (disimpan), dan pembaca untuk pesanan yang belum berjadwal (dibaca saja, tidak
disimpan; INV-PAY-05 melaporkannya) — jadi jadwal tersimpan dan bacaan sementara tidak mungkin berbeda rumus.

`open_lines` adalah SATU-SATUNYA pembaca jatuh tempo: pembayaran `sales_orders.payments[]` bertanggal ≤ posisi
(tanpa baris nota kredit tertangguh PK-32) dialokasikan ke baris — dulu yang menunjuk baris (`plan_line_seq`), lalu
mulai jatuh tempo tertua (aturan `baris_tagihan`). Uang dihitung dalam sen bulat (`02` D5), tanggal WIB (`02` D6).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core_utils import from_cents, new_id, now_iso, safe_doc, to_cents
from db import db
from services import payment_plan_service as plans
from services import report_basis as rb
from services.book_date import tanggal_buku

logger = logging.getLogger(__name__)

ORIGIN_TERM = "term"
ORIGIN_MANUAL = "manual"
KIND_SHIPMENT = "shipment"
KIND_DP = "dp"
KIND_DEBIT_NOTE = "debit_note"
SRC_SHIPMENT = "shipment"
SRC_ORDER = "order"
SRC_DEBIT_NOTE = "debit_note"
SRC_MANUAL = "manual"
#: Baris yang dibangun mesin dari dokumen (bukan isian orang).
AUTO_SOURCES = frozenset({SRC_SHIPMENT, SRC_ORDER, SRC_DEBIT_NOTE})
LABEL_SEBELUM_KIRIM = "Sebelum kirim"
#: Status pesanan sebelum dikonfirmasi — uang muka belum jatuh tempo.
PRE_CONFIRM = frozenset({"draft", "reserved", "waiting_stock", "waiting_approval", "approved"})
#: Pesanan terkirim seluruhnya (sama dengan `gl_service.FULLY_SHIPPED_STATUSES`).
FULLY_SHIPPED = frozenset({"shipped", "done"})
#: Banyak percobaan tulis-bersyarat (`rev`) sebelum menyerah — batas teknis, bukan aturan bisnis.
MAKS_ULANG = 6
EPS_SEN = 1


class BillingError(RuntimeError):
    """Jadwal tagihan tidak bisa diperbarui (pesan siap tampil)."""


# ── Pembantu ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def is_term(plan: Optional[Dict[str, Any]]) -> bool:
    return (plan or {}).get("origin") == ORIGIN_TERM


def _hidup(order: Dict[str, Any]) -> bool:
    """Pesanan yang diberi jadwal: bukan sample dan bukan status mati."""
    from services.customer_service import DEAD_STATUSES
    return bool(order) and order.get("order_type") != "sample" and order.get("status") not in DEAD_STATUSES


def sudah_konfirmasi(order: Dict[str, Any]) -> bool:
    if order.get("confirmed_at"):
        return True
    from services.customer_service import DEAD_STATUSES
    return order.get("status") not in PRE_CONFIRM and order.get("status") not in DEAD_STATUSES


def _nilai_pesanan(order: Dict[str, Any]) -> float:
    """Nilai pesanan dasar uang muka = grand total (tagihan tambahan nota debit punya barisnya sendiri)."""
    return float(order.get("grand_total", order.get("total_amount", 0)) or 0)


def _tgl(nilai: Any) -> Optional[str]:
    try:
        return tanggal_buku(nilai) if nilai not in (None, "") else None
    except ValueError:
        return None


async def termin_pesanan(order: Dict[str, Any], customer: Optional[Dict[str, Any]] = None,
                         peta: Optional[Dict[Any, Optional[int]]] = None,
                         cache: Optional[Dict[Tuple[str, str], Optional[Dict[str, Any]]]] = None) -> Dict[str, Any]:
    """Potret termin pesanan: `{term_code, term_type, net_days, dp_percent}`. `net_days` lewat aturan hari termin yang
    sama dengan umur piutang (`report_basis.hari_termin`: snapshot hari termin pesanan → master Syarat Bayar lapisan PT
    → profil pelanggan → bawaan); `dp_percent` dan `type` dari master Syarat Bayar (lapisan PT menang)."""
    from services import entity_master_service as ems
    code = str(order.get("payment_term_code") or "")
    key = (code, order.get("entity_id") or "")
    row: Optional[Dict[str, Any]] = None
    if code:
        if cache is not None and key in cache:
            row = cache[key]
        else:
            row = await ems.resolve_row("payment-terms", code, key[1], include_inactive=True)
            if cache is not None:
                cache[key] = row
    if peta is None:
        peta = await rb.peta_termin([order])
    if customer is None:
        customer = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0, "payment_profile": 1}) or {}
    try:
        dp = float((row or {}).get("dp_percent") or 0)
    except (TypeError, ValueError):
        dp = 0.0
    return {"term_code": code, "term_type": str((row or {}).get("type") or ""),
            "net_days": rb.hari_termin(customer, order, peta), "dp_percent": max(0.0, min(dp, 100.0))}


async def _kelompok_kirim(order: Dict[str, Any], journals: Iterable[Dict[str, Any]],
                          kode_cache: Dict[str, set]) -> List[Dict[str, Any]]:
    """Jurnal pendapatan pesanan → satu kelompok per NOMOR surat jalan (`source_label`, cadangan id dokumen) atau per
    jurnal lama per pesanan: `{source_type, source_id, tanggal, nilai_sen, shipment_ids, journal_ids, journal_numbers}`.
    Nilai = Σ debit akun `penjualan.piutang` (pemetaan PT jurnal). Jurnal nota debit tidak ikut (barisnya sendiri)."""
    groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for je in journals:
        st = je.get("source_type")
        if st not in ("shipment_revenue", "sales_order"):
            continue
        tgl = _tgl(je.get("date"))
        if tgl is None:
            continue
        kode = await rb._kode_piutang(je.get("entity_id") or order.get("entity_id") or "", kode_cache)  # noqa: SLF001
        nilai = sum(to_cents(float(ln.get("debit") or 0)) for ln in je.get("lines") or []
                    if ln.get("account_code") in kode)
        if nilai <= 0:
            continue
        if st == "sales_order":
            key = (SRC_ORDER, order["id"])
        else:
            key = (SRC_SHIPMENT, str(je.get("source_label") or je.get("source_id") or ""))
        g = groups.setdefault(key, {"source_type": key[0], "source_id": key[1], "tanggal": tgl, "nilai_sen": 0,
                                    "shipment_ids": [], "journal_ids": [], "journal_numbers": []})
        g["tanggal"] = min(g["tanggal"], tgl)
        g["nilai_sen"] += nilai
        if st == "shipment_revenue" and je.get("source_id") and je["source_id"] not in g["shipment_ids"]:
            g["shipment_ids"].append(je["source_id"])
        if je.get("id"):
            g["journal_ids"].append(je["id"])
            g["journal_numbers"].append(je.get("number") or "")
    return sorted(groups.values(), key=lambda g: (g["tanggal"], g["source_id"]))


def _baris(kind: str, *, label: str, amount_sen: int, due_date: str, billed_at: str, source_type: str,
           source_id: str, percent: float = 0.0, **lain: Any) -> Dict[str, Any]:
    return {"kind": kind, "label": label, "basis": "amount", "percent": round(float(percent or 0), 4),
            "amount": from_cents(amount_sen), "due_rule": "fixed_date", "due_date": due_date, "status": "open",
            "paid_amount": 0.0, "source_type": source_type, "source_id": source_id, "billed_at": billed_at,
            "shipment_ids": [], "journal_ids": [], "journal_numbers": [], **lain}


async def bangun_baris(order: Dict[str, Any], termin: Dict[str, Any], journals: Iterable[Dict[str, Any]],
                       kode_cache: Optional[Dict[str, set]] = None) -> List[Dict[str, Any]]:
    """PEMBANGUN BARIS satu-satunya (tabel K-16 di kepala modul). Murni dari dokumen: pesanan, termin, jurnal
    pendapatan, `extra_billing_lines[]`. Belum memuat `seq`/`line_id` (diberi saat disimpan)."""
    kode_cache = kode_cache if kode_cache is not None else {}
    oid, number = order["id"], order.get("number") or order["id"]
    net = int(termin.get("net_days") or 0)
    dp = float(termin.get("dp_percent") or 0)
    out: List[Dict[str, Any]] = []
    dp_sen = 0
    if dp > 0 and sudah_konfirmasi(order):
        dp_sen = int(round(to_cents(_nilai_pesanan(order)) * dp / 100.0))
        tgl = _tgl(order.get("confirmed_at")) or _tgl(order.get("created_at")) or tanggal_buku()
        if dp_sen > 0:
            out.append(_baris(KIND_DP, label=f"Uang muka {dp:g}%", amount_sen=dp_sen, due_date=tgl,
                              billed_at=order.get("confirmed_at") or order.get("created_at") or tgl,
                              source_type=SRC_ORDER, source_id=f"dp:{oid}", percent=dp,
                              due_label=LABEL_SEBELUM_KIRIM))
    if dp < 100:
        groups = await _kelompok_kirim(order, journals, kode_cache)
        tutup = order.get("status") in FULLY_SHIPPED
        kum = billed = 0
        for i, g in enumerate(groups):
            kum += g["nilai_sen"]
            if dp > 0:
                target = kum - dp_sen if (tutup and i == len(groups) - 1) else int(round(kum * (100.0 - dp) / 100.0))
                amt = max(0, target - billed)
            else:
                amt = g["nilai_sen"]
            billed += amt
            if amt <= 0:
                continue
            label = (f"Surat jalan {g['source_id']}" if g["source_type"] == SRC_SHIPMENT
                     else f"Pengakuan penjualan {number}")
            out.append(_baris(KIND_SHIPMENT, label=label, amount_sen=amt, due_date=rb.jatuh_tempo(g["tanggal"], net),
                              billed_at=g["tanggal"], source_type=g["source_type"], source_id=g["source_id"],
                              percent=(100.0 - dp) if dp > 0 else 0.0, shipment_ids=list(g["shipment_ids"]),
                              journal_ids=list(g["journal_ids"]), journal_numbers=list(g["journal_numbers"])))
    for x in order.get("extra_billing_lines") or []:
        if not isinstance(x, dict):
            continue
        amt = to_cents(float(x.get("gross") or 0))
        if amt <= 0:
            continue
        dibuat = _tgl(x.get("created_at")) or tanggal_buku()
        due = _tgl(x.get("due_date")) or rb.jatuh_tempo(dibuat, net)
        nomor = x.get("debit_note_number") or x.get("debit_note_id") or ""
        out.append(_baris(KIND_DEBIT_NOTE, label=f"Nota debit {nomor}".strip(), amount_sen=amt, due_date=due,
                          billed_at=x.get("created_at") or dibuat, source_type=SRC_DEBIT_NOTE,
                          source_id=str(x.get("debit_note_id") or x.get("id") or ""),
                          debit_note_number=x.get("debit_note_number") or ""))
    return out


async def recognized_sen(order: Dict[str, Any], journals: Iterable[Dict[str, Any]], kode_cache: Dict[str, set],
                         per: Optional[str] = None) -> int:
    """Σ debit akun piutang jurnal pengakuan penjualan pesanan (surat jalan, jurnal lama per pesanan, nota debit PK-32)
    bertanggal ≤ `per` (None = semua) — cara `ar_aging_service.recognized_by_order`, hanya akun piutang."""
    total = 0
    for je in journals:
        tgl = _tgl(je.get("date"))
        if per is not None and (tgl is None or tgl > per):
            continue
        kode = await rb._kode_piutang(je.get("entity_id") or order.get("entity_id") or "", kode_cache)  # noqa: SLF001
        total += sum(to_cents(float(ln.get("debit") or 0)) for ln in je.get("lines") or []
                     if ln.get("account_code") in kode)
    return total


def _efektif_sen(order: Dict[str, Any]) -> int:
    """Nilai yang akhirnya ditagih per surat jalan: nilai tagihan − nota kredit tertangguh (PK-32; pengurangnya ikut
    nilai efektif jurnal surat jalan berikutnya)."""
    tangguh = sum(to_cents(float(p.get("amount") or 0)) for p in order.get("payments") or []
                  if p.get("gl_bucket") == rb.BUCKET_NOTA_TANGGUH)
    return to_cents(plans.source_total(order)) - max(0, tangguh)


# ── Jadwal tersimpan ─────────────────────────────────────────────────────────────────────────────────────────────────
async def _buat_jadwal(order: Dict[str, Any], termin: Dict[str, Any]) -> Dict[str, Any]:
    now = now_iso()
    doc = {
        "id": new_id("pyp"), "number": "", "entity_id": order.get("entity_id") or "",
        "doc_type": "sales_order", "doc_id": order["id"], "doc_number": order.get("number", ""),
        "customer_id": order.get("customer_id", ""), "customer_name": order.get("customer_name", ""),
        "origin": ORIGIN_TERM, "mode": "term", "mode_label": plans.MODE_LABEL["term"], **termin,
        "total_amount": 0.0, "billed_total": 0.0, "recognized_total": 0.0, "billed_complete": False, "lines": [],
        "penalty": {"mode": "", "grace_days": None, "rate_pct_per_month": None, "base": "", "cap_pct": None},
        "note": "", "status": "active", "rev": 0, "created_by": "system", "created_at": now, "updated_at": now,
        "replaces_plan_id": "", "refs": [],
        "explain": [f"Jadwal tagihan {order.get('number', '')} mengikuti termin {termin.get('term_code') or '-'} "
                    f"({termin.get('net_days')} hari, uang muka {float(termin.get('dp_percent') or 0):g}%)"],
    }
    try:
        await db[plans.COLL].insert_one(dict(doc))
    except Exception as exc:  # noqa: BLE001
        from indexes import is_duplicate_on
        if is_duplicate_on(exc, "doc_type", "doc_id"):   # proses lain baru saja membuat jadwal hidup pesanan ini
            ada = await plans.get_active("sales_order", order["id"])
            if ada:
                return ada
        raise
    return safe_doc(doc)


def _kunci(line: Dict[str, Any]) -> Tuple[str, str]:
    return (str(line.get("source_type") or ""), str(line.get("source_id") or ""))


def _gabung(lines: List[Dict[str, Any]], mau: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Gabungkan baris hasil pembangun ke baris tersimpan (kunci idempotensi = `source_type` + `source_id`). Baris yang
    ada mempertahankan `seq`, `line_id`, `pay_code`; nilai surat jalan & nota debit selalu mengikuti dokumen (jurnal),
    nilai uang muka hanya bila belum dibayar. Baris mesin yang dokumennya hilang → nilai 0. → (baris, baris baru)."""
    hasil = [dict(x) for x in lines]
    ada = {_kunci(x): x for x in hasil}
    baru: List[Dict[str, Any]] = []
    seq = max([int(x.get("seq") or 0) for x in hasil] + [0])
    dipakai = set()
    for w in mau:
        k = _kunci(w)
        dipakai.add(k)
        cur = ada.get(k)
        if cur is None:
            seq += 1
            row = {**w, "seq": seq, "line_id": new_id("ppl")}
            hasil.append(row)
            baru.append(row)
            continue
        if w["kind"] == KIND_DP and float(cur.get("paid_amount") or 0) > 0.0049:
            continue   # uang muka yang sudah dibayar tidak disesuaikan
        for f in ("amount", "due_date", "billed_at", "label", "percent", "shipment_ids", "journal_ids",
                  "journal_numbers"):
            if f in w:
                cur[f] = w[f]
    for cur in hasil:
        if cur.get("source_type") in AUTO_SOURCES and _kunci(cur) not in dipakai and float(cur.get("amount") or 0):
            cur["amount"] = 0.0
    return hasil, baru


async def sync_order(order_id: str, *, alasan: str = "") -> Optional[Dict[str, Any]]:
    """Samakan jadwal `term` pesanan dengan dokumennya (idempoten; panggilan ulang tidak menggandakan baris). Pesanan
    mati → jadwal `term` di-void; rencana `manual` → tidak disentuh. → jadwal hidup (atau None)."""
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        return None
    plan = await plans.get_active("sales_order", order_id)
    if not _hidup(order):
        if plan and is_term(plan):
            await db[plans.COLL].update_one({"id": plan["id"], "status": {"$ne": "void"}}, {"$set": {
                "status": "void", "void_reason": alasan or "pesanan dibatalkan", "voided_by": "system",
                "voided_at": now_iso(), "updated_at": now_iso()}, "$inc": {"rev": 1}})
            await _segarkan_saldo(order)
        return None
    if plan and not is_term(plan):
        return plan   # rencana cicilan buatan orang: pembuatan otomatis berhenti (K-16)
    customer = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0, "payment_profile": 1}) or {}
    termin = await termin_pesanan(order, customer)
    jurnal = (await rb._jurnal_pendapatan([order_id])).get(order_id, [])   # noqa: SLF001
    kode_cache: Dict[str, set] = {}
    mau = await bangun_baris(order, termin, jurnal, kode_cache)
    if not plan:
        if not mau and not sudah_konfirmasi(order):
            return None
        plan = await _buat_jadwal(order, termin)
    pengakuan = from_cents(await recognized_sen(order, jurnal, kode_cache))
    efektif = _efektif_sen(order)
    baru: List[Dict[str, Any]] = []
    for _ in range(MAKS_ULANG):
        cur = await plans.get(plan["id"])
        if not cur or cur.get("status") == "void":
            return None
        lines, baru = _gabung(cur.get("lines") or [], mau)
        billed = sum(to_cents(float(x.get("amount") or 0)) for x in lines)
        rev = cur.get("rev")
        res = await db[plans.COLL].update_one({"id": cur["id"], "rev": rev}, {"$set": {
            "lines": lines, "billed_total": from_cents(billed), "total_amount": from_cents(billed),
            "recognized_total": pengakuan, "billed_complete": billed >= efektif - EPS_SEN,
            "rev": int(rev or 0) + 1, "updated_at": now_iso()}})
        if res.matched_count:
            break
    else:
        raise BillingError(f"Jadwal tagihan {order.get('number')} terus berubah bersamaan — ulangi.")
    plan = await plans.recompute_paid(plan["id"])
    # kode bayar per baris: surat jalan pesanan bertermin tunai dibayar dengan kode tingkat pesanan (PM-T2)
    berkode = [b for b in baru if b["kind"] != KIND_SHIPMENT or rb.pesanan_piutang(order)]
    if berkode:
        await _kode_bayar(plan, berkode)
    await _segarkan_saldo(order)
    return plan


async def _kode_bayar(plan: Dict[str, Any], baru: List[Dict[str, Any]]) -> None:
    """PM-T2 — kode bayar per baris tagihan yang baru lahir (baris uang muka memakai ulang kode pesanan). Gagal = dicatat;
    jadwal tetap sah (kode bisa dibuat ulang, `ensure_for_line` idempoten)."""
    from services import payment_code_service as pcs
    for ln in baru:
        try:
            await pcs.ensure_for_line(plan, ln)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[CR-T2] kode bayar baris %s gagal dibuat: %s", ln.get("line_id"), exc)


async def _segarkan_saldo(order: Dict[str, Any]) -> None:
    from services import customer_balance_service as cbs
    await cbs.refresh(order.get("customer_id") or "", order.get("entity_id") or "")


# ── Kait peristiwa (dipanggil alur dokumen; galat kait tidak membatalkan dokumen pemicunya) ─────────────────────────
async def on_order_confirmed(order_id: str) -> Optional[Dict[str, Any]]:
    """`confirm_core` berhasil → jadwal `term` lahir (+ baris uang muka bila termin ber-DP)."""
    return await sync_order(order_id)


async def on_shipment_posted(order_id: str, shipment_no: str) -> Optional[Dict[str, Any]]:
    """Jurnal surat jalan terbit → baris `shipment` nomor itu ditambah/disamakan (idempoten), `recompute_paid`, saldo."""
    plan = await sync_order(order_id)
    if plan and is_term(plan) and shipment_no and not any(
            ln.get("source_id") == shipment_no for ln in plan.get("lines") or []):
        logger.info("[CR-T2] surat jalan %s pesanan %s belum berjurnal piutang — baris belum lahir", shipment_no,
                    order_id)
    return plan


async def on_order_changed(order_id: str) -> Optional[Dict[str, Any]]:
    """Nilai/status pesanan berubah → uang muka yang belum dibayar disesuaikan; pesanan mati → jadwal di-void."""
    return await sync_order(order_id, alasan="pesanan dibatalkan")


async def on_debit_note(order_id: str) -> Optional[Dict[str, Any]]:
    """Nota debit menulis `extra_billing_lines[]` (PK-32) → baris `debit_note`."""
    return await sync_order(order_id)


async def kait_aman(nama: str, fn, *args: Any) -> Optional[Dict[str, Any]]:
    """Pembungkus kait untuk alur dokumen: galat dicatat, tidak dilempar (dokumen pemicu tetap sah)."""
    try:
        return await fn(*args)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[CR-T2] kait %s %s gagal: %s", nama, args, exc)
        return None


async def after_shipment_journal(shipment: Dict[str, Any]) -> str:
    """Sesudah jurnal surat jalan (alur kirim dan ulang posting): kait `on_shipment_posted`; galat ditulis ke
    `shipments.billing_status: failed` (panel Posting Gagal, jenis `shipment_billing`) — surat jalan tetap sah."""
    try:
        await on_shipment_posted(shipment["order_id"], shipment.get("shipment_no") or "")
    except Exception as exc:  # noqa: BLE001
        pesan = str(exc)[:300] or exc.__class__.__name__
        await db.shipments.update_one({"id": shipment["id"]}, {"$set": {
            "billing_status": "failed", "billing_error": pesan, "billing_failed_at": now_iso(),
            "updated_at": now_iso()}})
        logger.warning("[CR-T2] jadwal tagihan surat jalan %s gagal: %s", shipment.get("shipment_no"), exc)
        return "failed"
    await db.shipments.update_one({"id": shipment["id"], "billing_status": {"$exists": True}},
                                  {"$set": {"billing_status": "done", "billing_error": ""}})
    return "done"


async def retry_shipment_billing(doc: Dict[str, Any], actor: Any = None) -> None:
    """Jalur ulang panel Posting Gagal: kait dijalankan lagi; masih gagal → melempar (409 di panel)."""
    await on_shipment_posted(doc["order_id"], doc.get("shipment_no") or "")
    await db.shipments.update_one({"id": doc["id"]}, {"$set": {"billing_status": "done", "billing_error": "",
                                                              "updated_at": now_iso()}})


# ── Pembaca ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _alokasi(rows: List[Dict[str, Any]], order: Dict[str, Any], per: str) -> int:
    """Isi `_paid` (sen) tiap baris: pembayaran bertanggal ≤ `per` (tanpa nota tertangguh) — dulu yang menunjuk baris
    (`payments[].plan_line_seq`), sisanya mulai jatuh tempo tertua. → sisa pembayaran (uang muka di atas tagihan)."""
    budget = max(0, rb._terbayar_sen(order, per, tangguh=False))   # noqa: SLF001
    tuju: Dict[int, int] = {}
    for p in order.get("payments") or []:
        seq = p.get("plan_line_seq")
        if not seq or p.get("gl_bucket") == rb.BUCKET_NOTA_TANGGUH:
            continue
        tgl = _tgl(p.get("date") or p.get("created_at"))
        if tgl is not None and tgl > per:
            continue
        tuju[int(seq)] = tuju.get(int(seq), 0) + to_cents(float(p.get("amount") or 0))
    rows.sort(key=lambda r: (r.get("due_date") or "9999-12-31", int(r.get("seq") or 0)))
    for r in rows:
        r["_paid"] = 0
    for r in rows:
        want = tuju.get(int(r.get("seq") or 0), 0)
        if want <= 0 or budget <= 0:
            continue
        take = min(want, r["_amt"], budget)
        r["_paid"] += take
        budget -= take
    for r in rows:
        if budget <= 0:
            break
        take = min(r["_amt"] - r["_paid"], budget)
        if take > 0:
            r["_paid"] += take
            budget -= take
    return budget


async def lines_for_orders(orders: List[Dict[str, Any]], customers: Optional[Dict[str, Dict[str, Any]]] = None, *,
                           per: Any = None) -> Dict[str, Dict[str, Any]]:
    """Per pesanan: `{"rows": [...], "uang_muka": rupiah, "stored": bool, "origin": term|manual}` posisi `per`.

    Baris = jadwal hidup tersimpan (`term` atau `manual`); pesanan tanpa jadwal → baris dari pembangun yang sama
    (`bangun_baris`), tidak disimpan. Baris `term` hanya yang ber-`billed_at` ≤ `per`; baris rencana `manual` selalu
    (rencana menggantikan seluruh jadwal pesanan). Baris bernilai 0 dibuang."""
    per_tgl = tanggal_buku(per)
    hidup = [o for o in orders if o.get("id") and _hidup(o)]
    ids = [o["id"] for o in hidup]
    jadwal: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(ids), rb.KELOMPOK):
        async for p in db[plans.COLL].find({"doc_type": "sales_order", "doc_id": {"$in": ids[i:i + rb.KELOMPOK]},
                                            "status": {"$ne": "void"}}, {"_id": 0}):
            lama = jadwal.get(p["doc_id"])
            # data kembar (sebelum indeks unik): rencana manual menang, lalu yang terbaru
            if lama is None or (is_term(lama) and not is_term(p)) or (
                    is_term(lama) == is_term(p) and str(p.get("created_at")) > str(lama.get("created_at"))):
                jadwal[p["doc_id"]] = p
    maya = [o for o in hidup if o["id"] not in jadwal]
    jurnal = await rb._jurnal_pendapatan([o["id"] for o in maya]) if maya else {}   # noqa: SLF001
    peta = await rb.peta_termin(maya) if maya else {}
    cust = dict(customers or {})
    kurang = sorted({o.get("customer_id") for o in maya if o.get("customer_id") and o.get("customer_id") not in cust})
    for i in range(0, len(kurang), rb.KELOMPOK):
        async for c in db.customers.find({"id": {"$in": kurang[i:i + rb.KELOMPOK]}}, {"_id": 0, "id": 1,
                                                                                     "payment_profile": 1}):
            cust[c["id"]] = c
    kode_cache: Dict[str, set] = {}
    term_cache: Dict[Tuple[str, str], Any] = {}
    out: Dict[str, Dict[str, Any]] = {}
    for o in hidup:
        p = jadwal.get(o["id"])
        if p is not None:
            lines, origin, plan_id = p.get("lines") or [], (p.get("origin") or ORIGIN_MANUAL), p["id"]
        else:
            termin = await termin_pesanan(o, cust.get(o.get("customer_id") or "") or {}, peta, term_cache)
            lines = await bangun_baris(o, termin, jurnal.get(o["id"], []), kode_cache)
            for n, ln in enumerate(lines, 1):
                ln["seq"], ln["line_id"] = n, f"v:{ln['source_type']}:{ln['source_id']}"
            origin, plan_id = ORIGIN_TERM, ""
        rows: List[Dict[str, Any]] = []
        for ln in lines:
            amt = to_cents(float(ln.get("amount") or 0))
            if amt <= 0:
                continue
            if origin == ORIGIN_TERM:
                b = _tgl(ln.get("billed_at"))
                if b is not None and b > per_tgl:
                    continue
            rows.append({**ln, "_amt": amt, "plan_id": plan_id})
        sisa = _alokasi(rows, o, per_tgl)
        hasil = []
        for r in rows:
            amt, paid = r.pop("_amt"), r.pop("_paid")
            due = _tgl(r.get("due_date"))
            hasil.append({
                "plan_id": r["plan_id"], "line_id": r.get("line_id") or "", "seq": int(r.get("seq") or 0),
                "order_id": o["id"], "order_number": o.get("number") or o["id"],
                "customer_id": o.get("customer_id") or "", "entity_id": o.get("entity_id") or "",
                "kind": r.get("kind") or "installment", "label": r.get("label") or "",
                "source_type": r.get("source_type") or SRC_MANUAL, "source_id": r.get("source_id") or "",
                "shipment_ids": list(r.get("shipment_ids") or []), "journal_ids": list(r.get("journal_ids") or []),
                "journal_numbers": list(r.get("journal_numbers") or []),
                "billed_at": _tgl(r.get("billed_at")), "due_date": due,
                "amount": from_cents(amt), "paid_amount": from_cents(paid), "outstanding": from_cents(amt - paid),
                "days_late": rb.hari_antara(due, per_tgl) if due else 0,
                "origin": origin, "stored": p is not None})
        out[o["id"]] = {"rows": hasil, "uang_muka": from_cents(sisa), "stored": p is not None, "origin": origin}
    return out


async def open_lines(*, entity_ids: list, customer_ids: Optional[list] = None,
                     as_of: Optional[str] = None) -> list:
    """SATU-SATUNYA pembaca jatuh tempo piutang. Baris tagihan terbuka (sisa > 0) pesanan hidup di PT `entity_ids`
    (wajib; N1) — opsional pelanggan `customer_ids` — posisi `as_of` (kosong = hari ini WIB). Tiap baris:
    `plan_id, line_id, order_id, order_number, customer_id, entity_id, kind, amount, paid_amount, outstanding, due_date,
    days_late` (+ `label`, `source_type`, `source_id`, `journal_ids`, `billed_at`, `origin`, `stored`). Dengan `as_of`:
    hanya baris ber-`billed_at` ≤ tanggal itu dan pembayaran bertanggal ≤ tanggal itu (RP-05)."""
    ents = [e for e in (entity_ids or []) if e and e != "all"]
    if not ents:
        return []
    from services.customer_service import DEAD_STATUSES
    q: Dict[str, Any] = {"entity_id": {"$in": ents}, "status": {"$nin": sorted(DEAD_STATUSES)},
                         "order_type": {"$ne": "sample"}}
    if customer_ids is not None:
        q["customer_id"] = {"$in": list(customer_ids)}
    if not as_of:
        q["payment_status"] = {"$ne": "paid"}
    orders = [o async for o in db.sales_orders.find(q, {"_id": 0})]
    per = rb._tgl_aman(as_of) if as_of else None   # noqa: SLF001
    hasil = await lines_for_orders(orders, per=per)
    rows = [r for v in hasil.values() for r in v["rows"] if r["outstanding"] > rb.EPS]
    rows.sort(key=lambda r: (r["due_date"] or "9999-12-31", r["order_number"], r["seq"]))
    return rows
