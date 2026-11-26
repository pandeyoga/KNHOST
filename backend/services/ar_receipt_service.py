"""AR Receipt service (EPIC3B) — Penerimaan pembayaran customer + aplikasi ke SO.

Mencatat penerimaan kas dari customer lalu meng-apply-nya ke sales_orders
(`payments[]`, `paid_total`, `payment_status`). Karena credit gate &
Collection Worklist sudah membaca `payments[]`/`payment_status`, AR otomatis
ter-update tanpa perubahan lapisan lain (lihat customer_service.compute_customer_credit).

Integrasi tambahan (audit fix):
  - P0-1: setiap penerimaan KAS (amount > 0) di-posting ke `cash_transactions`
    (direction=in, ref_type=ar_receipt) lewat `cash_ledger.create_cash` (PK-20) ke REKENING PENERIMA kwitansi
    (PM-T3: dikirim / rekening tujuan pesanan / bawaan PT untuk cara bayar / rekening tunggal); jenis kas = jenis
    rekening itu.
  - PM-T3: status "terverifikasi bank" (`bank_verified`) diisi rekonsiliasi saat kas kwitansi cocok penuh dengan
    mutasi rekening yang sama; kwitansi terverifikasi tidak bisa dibatalkan sebelum pencocokannya dilepas.
  - P2-5: kelebihan bayar (unapplied) → `customers.deposit_balance`; deposit dapat
    dipakai mendanai alokasi via `use_deposit_amount`.
  - P2-6: void/reversal — membalik payments[], void cash, dan koreksi deposit.

Alokasi:
  - Eksplisit: payload.allocations = [{order_id, amount}].
  - Otomatis (default): FIFO ke order terbuka tertua sampai dana habis.

Idempotensi nomor: AR-##### via next_doc_number (deletion-safe).
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc, DEFAULT_ENTITY_ID, rupiah

# Re-use kontrak AR yang sama dengan engine kredit (SSOT tunggal — hindari drift).
from services.customer_service import (
    _order_grand_total as order_grand_total,
    _order_paid as order_paid,
    order_payment_method,
    DEAD_STATUSES,
    NON_AR_METHODS,
)
from request_context import active_entity_or
from ai_card_context import card_field
logger = logging.getLogger(__name__)


EPS = 0.01

# ─── PM-T3 — kwitansi ber-rekening & ber-referensi; status "terverifikasi bank" ───────────────────────────────────
#: Pesan galat langkah PERIKSA (spesifikasi `docs/blueprint/unit/PM-T3.md` §Galat).
PESAN_REK_PT_LAIN = "Rekening penerima bukan milik PT kwitansi ini."
PESAN_REK_TIDAK_MENERIMA = "Rekening ini tidak bisa menerima pembayaran pelanggan lewat {nama}."
PESAN_REF_WAJIB = "Nomor referensi wajib diisi untuk {nama}."
PESAN_GIRO_WAJIB = "Jatuh tempo giro wajib diisi untuk {nama}."
PESAN_GIRO_FORMAT = "Jatuh tempo giro harus berupa tanggal yang sah (tahun-bulan-tanggal)."
PESAN_TIDAK_SESUAI = "Rekening penerima berbeda dari instruksi bayar pesanan. Isi catatan alasannya."
PESAN_BATAL_TERVERIFIKASI = "Kwitansi sudah terverifikasi bank. Lepaskan pencocokan mutasinya dulu."
#: Panjang minimum catatan "tidak sesuai instruksi" (validasi isian, sama dengan alasan pengecualian kirim).
CATATAN_MIN = 5
KEY_WAJIB_REF = "payment.wajib_nomor_referensi"
KEY_HARI_WAJAR = "payment.hari_wajar_verifikasi_bank"
#: Field status verifikasi bank kwitansi (diisi rekonsiliasi `bank_recon_service`, bawaan belum terverifikasi).
VERIFIKASI_AWAL = {"bank_verified": False, "bank_verified_at": "", "bank_verified_by": "", "bank_line_ids": []}


def potret_rekening(acc: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Potret rekening penerima yang disimpan di kwitansi (`02` D3): cetakan lama tetap menyebut rekening saat itu."""
    a = acc or {}
    return {"name": str(a.get("name") or ""), "bank_name": str(a.get("bank_name") or ""),
            "account_number": str(a.get("account_number") or "")}


def teks_potret(snap: Optional[Dict[str, Any]]) -> str:
    """"{bank} {nomor} ({nama rekening})" — bentuk tampil rekening kwitansi (cetakan, keterangan kas)."""
    s = snap or {}
    head = " ".join(x for x in (str(s.get("bank_name") or "").strip(), str(s.get("account_number") or "").strip()) if x)
    name = str(s.get("name") or "").strip()
    return f"{head} ({name})" if head and name else (head or name)


async def _rencana_pesanan(customer_id: str, entity_id: str, explicit: List[Dict[str, Any]],
                           total_funds: float) -> List[str]:
    """Id pesanan yang akan menerima alokasi kwitansi ini (dibaca SEBELUM tulisan): alokasi eksplisit, atau pratinjau
    FIFO yang sama dengan `_create_receipt_after_reserve` (pesanan terbuka tertua lebih dulu)."""
    if explicit:
        return [str(a.get("order_id") or "") for a in explicit
                if a.get("order_id") and round(float(a.get("amount", 0) or 0), 2) > 0]
    out, sisa = [], round(total_funds, 2)
    for oo in await list_open_orders(customer_id, entity_id=entity_id):
        if sisa <= EPS:
            break
        take = round(min(sisa, oo["outstanding"]), 2)
        if take > EPS:
            out.append(oo["order_id"])
            sisa = round(sisa - take, 2)
    return out


async def periksa_uang_masuk(payload: Dict[str, Any], *, entity_id: str, cara: Dict[str, Any], amount: float,
                             customer_id: str, total_funds: float, titipan: bool = False) -> Dict[str, Any]:
    """PM-T3 — langkah PERIKSA rekening, referensi, dan instruksi bayar kwitansi (`02` §1 langkah 1: tanpa tulisan).

    → isian kwitansi `{account_id, account_snapshot, cash_type, reference_no, giro_due_date, proof_url,
    instruction_mismatch, mismatch_note, instruction_mismatch_orders, pay_codes, order_ids}`.

    Rekening (hanya bila ada uang baru): yang dikirim → (kosong) rekening tujuan pesanan yang dialokasi bila semua
    pesanan menunjuk rekening yang sama dan rekening itu menerima cara bayar ini → rekening bawaan (PT, cara bayar)
    PM-T1 → rekening tunggal PT untuk jenis kasnya (PK-20) → 409 pesan PK-20. Rekening PT lain → 400; nonaktif → 409
    (PK-20); bukan penerimaan pelanggan / tidak melayani cara bayar → 400.

    PM-T4 — `titipan=True` (tunai yang dicatat sebagai titipan di tangan sales): tanpa rekening penerima (tidak ada kas
    sampai setorannya diterima). "Tidak sesuai instruksi" = pesanan yang dialokasi berinstruksi rekening yang tidak
    menerima tunai di PT ini (catatan alasan wajib, sama dengan tunai ke rekening kas)."""
    from services import bank_account_change_service as bacs
    from services import cash_ledger
    from services.cash_entity_service import resolve_owner
    from services.payment_code_service import teks_rekening
    nama = cara.get("name") or cara.get("code") or ""
    kode = cara.get("code") or ""
    perlu = cara.get("needs_account") or ""
    explicit = payload.get("allocations") or []
    order_ids = await _rencana_pesanan(customer_id, entity_id, explicit, total_funds)
    orders = await db.sales_orders.find({"id": {"$in": order_ids}},
                                        {"_id": 0, "id": 1, "number": 1, "receiving_account_id": 1,
                                         "receiving_account": 1}).to_list(len(order_ids) + 1) if order_ids else []
    out: Dict[str, Any] = {"account_id": "", "account_snapshot": {}, "cash_type": "", "reference_no": "",
                           "giro_due_date": "", "proof_url": str(payload.get("proof_url") or "").strip()[:500],
                           "instruction_mismatch": False, "mismatch_note": "", "instruction_mismatch_orders": [],
                           "pay_codes": [], "order_ids": order_ids}
    if order_ids:
        out["pay_codes"] = [c["code"] for c in await db.payment_codes.find(
            {"order_id": {"$in": order_ids}, "status": {"$ne": "batal"}}, {"_id": 0, "code": 1}).to_list(200)
            if c.get("code")]
    if amount <= EPS:
        return out   # deposit saja = tanpa kas baru, tanpa rekening (PK-20)
    owner = resolve_owner(entity_id, DEFAULT_ENTITY_ID, what="Kas masuk kwitansi")
    if titipan:
        penerima_tunai = {r["id"] for r in await bacs.daftar_penerima(owner, kode)}
        beda = [{"order_id": o["id"], "order_number": o.get("number") or o["id"],
                 "account_id": o.get("receiving_account_id") or "",
                 "account_text": teks_rekening(o.get("receiving_account") or {})}
                for o in orders if o.get("receiving_account_id") and o["receiving_account_id"] not in penerima_tunai]
        out["reference_no"] = str(payload.get("reference_no") or "").strip()[:80]
        if beda:
            catatan = str(payload.get("mismatch_note") or "").strip()
            if len(catatan) < CATATAN_MIN:
                raise HTTPException(status_code=400, detail=PESAN_TIDAK_SESUAI)
            out.update(instruction_mismatch=True, mismatch_note=catatan[:500], instruction_mismatch_orders=beda)
        return out
    cash_type = "kas_kecil" if perlu == "kas" else "kas_besar"
    dikirim = str(payload.get("account_id") or "").strip()
    penerima = await bacs.daftar_penerima(owner, kode) if perlu in ("bank", "kas") else []
    ids_penerima = {r["id"] for r in penerima}
    if dikirim:
        acc = await db.bank_accounts.find_one({"id": dikirim}, {"_id": 0, "id": 1, "entity_id": 1})
        if acc and (acc.get("entity_id") or "") != owner:
            raise HTTPException(status_code=400, detail=PESAN_REK_PT_LAIN)
        pilih = dikirim
    else:
        tujuan = {o.get("receiving_account_id") for o in orders if o.get("receiving_account_id")}
        pilih = ""
        if len(tujuan) == 1 and next(iter(tujuan)) in ids_penerima:
            pilih = next(iter(tujuan))   # rekening tujuan pesanan = rekening yang paling mungkin dipakai pelanggan
        if not pilih:
            pilih = next((r["id"] for r in penerima if r.get("is_default")), "")
    rek = await cash_ledger.periksa_rekening(owner, pilih, cash_type)
    if perlu in ("bank", "kas") and rek["account_id"] not in ids_penerima:
        raise HTTPException(status_code=400, detail=PESAN_REK_TIDAK_MENERIMA.format(nama=nama))
    out.update(account_id=rek["account_id"], account_snapshot=potret_rekening(rek["account"]),
               cash_type=rek["cash_type"])
    out.update(await syarat_uang_masuk(
        entity_id=owner, cara=cara, account_id=rek["account_id"], orders=orders,
        reference_no=payload.get("reference_no") or "", giro_due_date=payload.get("giro_due_date") or "",
        mismatch_note=payload.get("mismatch_note") or ""))
    return out


async def syarat_uang_masuk(*, entity_id: str, cara: Dict[str, Any], account_id: str, orders: List[Dict[str, Any]],
                            reference_no: str = "", giro_due_date: str = "",
                            mismatch_note: str = "") -> Dict[str, Any]:
    """LB-T4 (R10-a) — SATU aturan isian uang masuk non-tunai ber-rekening, dipakai kwitansi (`periksa_uang_masuk`, juga
    pagar cadangan saat Terima lapor bayar) DAN pembuatan laporan bayar (`payment_report_service.create_report`, supaya
    laporan yang tidak akan bisa diterima ditolak saat dibuat oleh orang yang memegang datanya). Tanpa tulisan.

    * Nomor referensi wajib bila cara bayar memintanya (`needs_reference`) DAN `payment.wajib_nomor_referensi` PT menyala.
    * Jatuh tempo giro (`needs_due_date`): tanggal sah; wajib bila pengaturan yang sama menyala.
    * Rekening penerima ≠ rekening instruksi bayar salah satu pesanan (`receiving_account_id`) → catatan alasan
      ≥ `CATATAN_MIN` huruf wajib; tanda "tidak sesuai instruksi" + daftar pesanannya ikut tersimpan.

    → `{reference_no, giro_due_date, instruction_mismatch, mismatch_note, instruction_mismatch_orders}`."""
    from services.config_resolver import value_of
    from services.payment_code_service import teks_rekening
    nama = cara.get("name") or cara.get("code") or ""
    ref = str(reference_no or "").strip()[:80]
    giro = str(giro_due_date or "").strip()
    wajib_ref = bool(await value_of(KEY_WAJIB_REF, {"entity_id": entity_id}))
    if cara.get("needs_reference") and wajib_ref and not ref:
        raise HTTPException(status_code=400, detail=PESAN_REF_WAJIB.format(nama=nama))
    if cara.get("needs_due_date"):
        if giro:
            from services.bank_statement_parser import strict_iso_date
            if not strict_iso_date(giro) or len(giro) != 10:
                raise HTTPException(status_code=400, detail=PESAN_GIRO_FORMAT)
        elif wajib_ref:
            raise HTTPException(status_code=400, detail=PESAN_GIRO_WAJIB.format(nama=nama))
    else:
        giro = ""
    out: Dict[str, Any] = {"reference_no": ref, "giro_due_date": giro, "instruction_mismatch": False,
                           "mismatch_note": "", "instruction_mismatch_orders": []}
    # Tidak sesuai instruksi: rekening penerima ≠ rekening tujuan salah satu pesanan yang dialokasi.
    beda = [{"order_id": o["id"], "order_number": o.get("number") or o["id"],
             "account_id": o.get("receiving_account_id") or "",
             "account_text": teks_rekening(o.get("receiving_account") or {})}
            for o in orders if o.get("receiving_account_id") and o["receiving_account_id"] != account_id]
    if beda:
        catatan = str(mismatch_note or "").strip()
        if len(catatan) < CATATAN_MIN:
            raise HTTPException(status_code=400, detail=PESAN_TIDAK_SESUAI)
        out.update(instruction_mismatch=True, mismatch_note=catatan[:500], instruction_mismatch_orders=beda)
    return out


def _titipan_id(receipt_id: str) -> str:
    from services.cash_holding_service import holding_id_for
    return holding_id_for(receipt_id)


def _payment_status(grand_total: float, paid: float) -> str:
    if paid >= grand_total - EPS:
        return "paid"
    if paid > EPS:
        return "partial"
    return "unpaid"


# ─── Cash posting (P0-1) ─────────────────────────────────────────────────────
# PM-T3 — `_cash_routing` (jenis kas dari cara bayar) DIHAPUS: jenis kas kwitansi = jenis rekening penerimanya
# (`periksa_uang_masuk` → `cash_ledger.periksa_rekening`), bukan tebakan dari kata cara bayar.


def keterangan_kas(receipt: Dict[str, Any], pay_codes: Optional[List[str]] = None) -> str:
    """PM-T3 — keterangan kas kwitansi: nomor, pelanggan, nomor referensi, dan kode bayar pesanan yang dialokasi
    (teks yang dibaca skor referensi rekonsiliasi bank)."""
    teks = f"Penerimaan {receipt.get('number')} — {receipt.get('customer_name', '')}"
    if receipt.get("reference_no"):
        teks += f" · Ref {receipt['reference_no']}"
    kode = [k for k in (pay_codes or []) if k]
    if kode:
        teks += " · Kode " + ", ".join(dict.fromkeys(kode))
    return teks


async def _post_cash_in(receipt: Dict[str, Any], actor: Dict[str, Any],
                        pay_codes: Optional[List[str]] = None, cash_type: str = "") -> Optional[str]:
    """Kas masuk penerimaan AR lewat pembuat kas satu pintu (PK-20). Mengembalikan id cash_transaction.

    Rekening = `receipt.account_id` (sudah diperiksa `create_receipt` sebelum tulisan; kosong = rekening tunggal PT untuk
    jenis kas cara bayarnya). FN-10 — kegagalan jurnal TIDAK disembunyikan: kas (`create_cash`) & kwitansi ditandai
    `gl_status=failed` (terlihat, bisa diulang lewat POST /ar-receipts/{id}/repost atau panel Posting Gagal).
    PM-T3 — kas membawa `counterparty_name` (nama pelanggan) dan `reference_no`; keterangannya memuat nomor referensi
    dan kode bayar pesanan yang dialokasi (`keterangan_kas`)."""
    amt = round(float(receipt.get("amount", 0) or 0), 2)
    if amt <= EPS:
        return None
    # E7.4 — pemilik uang = badan usaha kwitansinya (tidak ada lagi kas grup).
    from services.cash_entity_service import resolve_owner
    entity_id = resolve_owner(receipt.get("entity_id"), DEFAULT_ENTITY_ID,
                              what="Kas masuk kwitansi")
    from services import cash_ledger
    try:
        cdoc = await cash_ledger.create_cash(
            entity_id=entity_id, direction="in", amount=amt, ref_type="ar_receipt", ref_id=receipt["id"],
            account_id=receipt.get("account_id") or "", cash_type=cash_type,
            txn_date=receipt.get("receipt_date") or now_iso(), category="penagihan",
            description=keterangan_kas(receipt, pay_codes),
            actor=actor.get("name", "system"),
            extra={"counterparty_name": receipt.get("customer_name", ""),
                   "reference_no": receipt.get("reference_no", "")})
        # KN-G3: jurnal kas diposting SEKARANG (bukan menunggu backfill) supaya saldo Piutang & Uang Muka Pelanggan
        # langsung benar — penting sejak keputusan selisih pembayaran (FASE G-3) bisa menjurnal di detik yang sama.
        # Pelatihan 18 Nov — id jurnal kas ikut ditulis: label "Jurnal Terbit" di Riwayat Pembayaran (AR) membuka jurnalnya
        # (dulu kosong → label mati, peserta tidak bisa memeriksa Dr Bank / Cr Piutang dari kwitansinya).
        await db.ar_receipts.update_one({"id": receipt["id"]}, {"$set": {
            "gl_status": "posted", "gl_error": "", "journal_entry_id": (cdoc or {}).get("journal_entry_id") or ""}})
    except cash_ledger.CashPostingError as exc:
        logger.error("[_post_cash_in] jurnal kwitansi %s gagal: %s", receipt.get("number"), exc.error)
        cdoc = exc.txn
        await db.ar_receipts.update_one({"id": receipt["id"]}, {"$set": {
            "gl_status": "failed", "gl_error": exc.error[:300], "updated_at": now_iso()}})
    return cdoc.get("id")


async def _post_deposit_gl(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """W2-015 — jurnal reklas kwitansi murni deposit; gagal → gl_status=failed (bisa repost)."""
    from services import gl_service as _gl
    try:
        je = await _gl.post_deposit_only_receipt(doc, created_by=actor.get("name", "system"))
        await db.ar_receipts.update_one({"id": doc["id"]}, {"$set": {
            "gl_status": "posted", "gl_error": "", "journal_entry_id": (je or {}).get("id") or ""}})
    except Exception as exc:  # noqa: BLE001
        logger.error("[deposit_gl] jurnal kwitansi %s gagal: %s", doc.get("number"), exc)
        await db.ar_receipts.update_one({"id": doc["id"]}, {"$set": {
            "gl_status": "failed", "gl_error": str(exc)[:300], "updated_at": now_iso()}})


async def repost_receipt(receipt_id: str) -> Dict[str, Any]:
    """FN-10 — ulangi jurnal kas kwitansi yang gagal (idempotent per cash_transaction)."""
    rc = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not rc:
        raise HTTPException(status_code=404, detail="Kwitansi tidak ditemukan")
    if rc.get("cash_holding_id") and not rc.get("cash_txn_id"):
        # PM-T4 — kwitansi titipan: jurnalnya milik titipan (`cash_holding`); ulang lewat pintu yang sama.
        from services import cash_holding_service as _cth
        try:
            await _cth.ulang_jurnal(rc["cash_holding_id"], "repost")
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=409, detail=f"Jurnal masih gagal: {exc}")
        return safe_doc(await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0}))
    if not rc.get("cash_txn_id") and float(rc.get("used_deposit") or 0) > EPS:
        await _post_deposit_gl(rc, {"name": "repost"})
        fresh = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
        if fresh.get("gl_status") == "failed":
            raise HTTPException(status_code=409, detail=f"Jurnal masih gagal: {fresh.get('gl_error')}")
        return safe_doc(fresh)
    txn = await db.cash_transactions.find_one({"id": rc.get("cash_txn_id") or "__none__"}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=409, detail="Kwitansi tanpa transaksi kas — tidak ada jurnal untuk diulang")
    from services import cash_ledger   # PK-20 — jurnal kas lewat pembuat kas (pintu tahan-gagal di dalamnya)
    try:
        je = await cash_ledger.ensure_posted(txn["id"])
    except cash_ledger.CashPostingError as exc:
        await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {"gl_status": "failed", "gl_error": exc.error[:300]}})
        raise HTTPException(status_code=409, detail=f"Jurnal masih gagal: {exc.error}")
    await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {"gl_status": "posted", "gl_error": "",
                                                                  "journal_entry_id": (je or {}).get("id") or "",
                                                                  "updated_at": now_iso()}})
    return safe_doc(await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0}))


# ─── Deposit (P2-5) ──────────────────────────────────────────────────────────
async def get_deposit_balance(customer_id: str) -> float:
    c = await db.customers.find_one({"id": customer_id}, {"_id": 0, "deposit_balance": 1})
    return round(float((c or {}).get("deposit_balance", 0) or 0), 2)


async def _adjust_deposit(customer_id: str, delta: float) -> None:
    if abs(delta) < EPS:
        return
    pred: Dict[str, Any] = {"id": customer_id}
    if delta < 0:
        # KN-B08 — pemakaian deposit berprasyarat saldo cukup (CAS): dua pemakaian
        # bersamaan tidak bisa membuat deposit negatif.
        pred["deposit_balance"] = {"$gte": round(-delta, 2) - EPS}
    res = await db.customers.update_one(
        pred, {"$inc": {"deposit_balance": round(delta, 2)}, "$set": {"updated_at": now_iso()}})
    if res.matched_count == 0 and delta < 0:
        raise HTTPException(status_code=409, detail="Deposit pelanggan tidak cukup (baru saja terpakai proses lain).")
    from services import customer_balance_service as _cbs   # CR-T2 — cermin titipan di saldo tersimpan (turunan)
    await _cbs.refresh_safe(customer_id)


async def adjust_deposit(customer_id: str, delta: float) -> None:
    """FASE G-3 — penyesuaian deposit dari keputusan selisih pembayaran (publik)."""
    await _adjust_deposit(customer_id, delta)


async def pindah_uang_muka_ke_titipan(order: Dict[str, Any], actor: Any, reason: str, amount: float,
                                      source_id: str, kata: str) -> float:
    """INTI pemindahan uang muka pesanan → TITIPAN pelanggan (`customers.deposit_balance`), dipakai pesanan batal /
    kedaluwarsa (`uang_muka_pesanan_batal_ke_titipan`) dan tutup sisa (BTP-4, kelebihan sesudah nilai pesanan turun ke
    yang dikirim). `amount` = nominal yang dipindah (dihitung pemanggil; dipakai hanya bila penanda belum ada),
    `source_id` = sumber baris penarikan di `payments[]` (id baris turunan → aman diulang), `kata` = keadaan pesanan
    untuk teks ("dibatalkan", "kedaluwarsa", "sisa ditutup").

    Tanpa jurnal: uang muka pesanan dan titipan sama-sama 2-1400 Uang Muka Pelanggan. Di pesanan ditulis baris penarikan
    (`ar_allocation_service.withdraw`, jenis `deposit`, `gl_bucket=advance`, `moved_to_deposit`) → terbayar pesanan dan
    uang muka tertahan turun sebesar `amount`, dan kwitansi asalnya tidak bisa lagi dibatalkan tanpa menarik titipannya
    (`reverse_check` menolak, 409). Aman diulang: penanda `advance_to_deposit` (satu per pesanan) diklaim sebelum
    titipan ditambah; ulangan mengikuti nominal & sumber penandanya. Finance (pemegang izin Meja Finance) diberi tahu —
    berhasil atau gagal. → nominal yang dipindah (0 = tidak ada / sudah dipindah)."""
    from services import ar_allocation_service as _alloc
    from services import gl_service as _gl
    order_id = order.get("id") or ""
    tanda = order.get("advance_to_deposit") or {}
    if not tanda:
        held = round(float(amount or 0), 2)
        if held <= EPS:
            return 0.0
        tanda = {"amount": held, "deposit_done": False, "at": now_iso(), "reason": reason, "source_id": source_id,
                 "kata": kata,
                 "by": (actor or {}).get("name", "system") if isinstance(actor, dict) else str(actor or "system")}
        res = await db.sales_orders.update_one({"id": order_id, "advance_to_deposit": {"$exists": False}},
                                               {"$set": {"advance_to_deposit": tanda}})
        if not res.modified_count:   # proses lain lebih dulu menandai — ikuti penandanya
            tanda = ((await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "advance_to_deposit": 1})) or {}) \
                .get("advance_to_deposit") or {}
    held = round(float(tanda.get("amount") or 0), 2)
    if held <= EPS or tanda.get("deposit_done"):
        return 0.0
    kata = tanda.get("kata") or kata
    try:
        await _alloc.withdraw(
            kind="deposit", order_id=order_id, amount=held, source_id=tanda.get("source_id") or source_id,
            source_number=order.get("number") or order_id, customer_id=order.get("customer_id") or "",
            entity_id=order.get("entity_id") or "", date=now_iso(), actor=actor, method="deposit",
            note=f"Uang muka dipindah ke titipan pelanggan (pesanan {kata}){(': ' + reason) if reason else ''}",
            extra={"gl_bucket": _gl.ADVANCE_BUCKET, "moved_to_deposit": True})
        klaim = await db.sales_orders.update_one(
            {"id": order_id, "advance_to_deposit.deposit_done": False},
            {"$set": {"advance_to_deposit.deposit_done": True, "advance_to_deposit.done_at": now_iso()}})
        if not klaim.modified_count:
            return 0.0
        try:
            await _adjust_deposit(order.get("customer_id") or "", held)
        except Exception:
            await db.sales_orders.update_one({"id": order_id}, {"$set": {"advance_to_deposit.deposit_done": False}})
            raise
    except Exception as exc:
        await _beri_tahu_finance_titipan(order, held, reason, galat=str(exc) or type(exc).__name__, kata=kata)
        raise
    await _beri_tahu_finance_titipan(order, held, reason, kata=kata)
    return held


async def uang_muka_pesanan_batal_ke_titipan(order_id: str, actor: Any, reason: str = "") -> float:
    """S3 (pelatihan 18 Nov) — pesanan BATAL / kedaluwarsa yang sudah menerima uang muka: uang muka yang masih tertahan
    untuk pesanan itu (pembayaran ber-`gl_bucket=advance` yang belum direklas ke Piutang, paling banyak yang terbayar)
    dipindah menjadi TITIPAN pelanggan lewat `pindah_uang_muka_ke_titipan`, supaya bisa dikembalikan (Kasus ›
    Pengembalian dana ke pelanggan) atau dipakai pesanan lain. Dulu uang itu tertinggal di pesanan mati: tidak tampil di
    titipan maupun Laporan Uang Muka, padahal akun 2-1400 masih memegangnya. Hanya untuk pesanan mati (`DEAD_STATUSES`).
    → nominal yang dipindah (0 = tidak ada uang muka / sudah dipindah)."""
    from services import gl_service as _gl
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not order or order.get("status") not in DEAD_STATUSES:
        return 0.0
    held = 0.0
    if not order.get("advance_to_deposit"):
        held = min(await _gl.order_advance_unrecognized(order), order_paid(order))
    kata = "kedaluwarsa" if order.get("status") == "expired" else "dibatalkan"
    return await pindah_uang_muka_ke_titipan(order, actor, reason, held, f"batal_titipan:{order_id}", kata)


#: Temuan alur pembatalan 25 Nov — penerima = pemegang izin Meja Finance (`routers/work_desks.finance_desk`), per orang.
IZIN_MEJA_FINANCE = ("payment_variance", "decide")
NOTIF_TITIPAN_BATAL = "titipan_pesanan_batal"


async def _beri_tahu_finance_titipan(order: Dict[str, Any], amount: Optional[float], reason: str = "",
                                     galat: str = "", kata: str = "") -> None:
    """Uang muka pesanan batal/kedaluwarsa/sisa ditutup sudah (atau GAGAL) menjadi titipan → beri tahu pemegang izin
    Meja Finance di PT pesanan. Dulu hanya sales pemilik yang diberi tahu; Finance yang harus mengembalikan uang atau
    memakainya untuk pesanan lain harus mengecek daftar titipan sendiri. Best-effort: tidak pernah menggagalkan
    pemindahan. Gagal = tingkat `critical` (audit notifikasi N-17: `"danger"` tidak dikenal). `amount=None` = nominal
    belum terhitung (galat sebelum kelebihan dihitung, tutup sisa langkah 6)."""
    from services import notification_service as _ns
    kata = kata or ("kedaluwarsa" if order.get("status") == "expired" else "dibatalkan")
    nomor = order.get("number") or order.get("id")
    pelanggan = order.get("customer_name") or order.get("customer_id") or "-"
    alasan = f" Alasan: {reason}." if reason else ""
    if galat:
        jenis, severity = f"{NOTIF_TITIPAN_BATAL}_gagal", "critical"
        jumlah = rupiah(amount) if amount is not None else "uang (nominal belum terhitung)"
        title = f"{nomor} {kata}: uang muka BELUM jadi titipan pelanggan"
        body = (f"{pelanggan} — {jumlah} masih tertahan di pesanan ini (pesanan {kata}) dan belum masuk "
                f"titipan. Periksa pesanan dan titipan pelanggan ini.{alasan} Galat: {galat}")
    else:
        jenis, severity = NOTIF_TITIPAN_BATAL, "warning"
        title = f"{nomor} {kata}: uang muka jadi titipan pelanggan"
        body = (f"{pelanggan} — {rupiah(amount)} sekarang menjadi titipan. Kembalikan lewat Kasus › Pengembalian dana "
                f"ke pelanggan, atau pakai untuk pesanan lain.{alasan}")
    try:
        await _ns.create_addressed(
            permission=IZIN_MEJA_FINANCE, notif_type=jenis, ref=f"{jenis}:{order.get('id')}", title=title,
            body=body[:400], severity=severity, link="advance-report", entity_id=order.get("entity_id") or None)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("Notifikasi titipan pesanan %s gagal: %s", order.get("id"), exc)


async def list_open_orders(customer_id: str, entity_id: Any = None) -> List[Dict[str, Any]]:
    """Order AR terbuka (ada outstanding) untuk customer, tertua dulu (FIFO).
    `entity_id` str atau list scope (CX-02 — alokasi/daftar tidak lintas badan usaha)."""
    q: Dict[str, Any] = {"customer_id": customer_id}
    if isinstance(entity_id, list):
        q["entity_id"] = {"$in": entity_id}
    elif entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    orders = await db.sales_orders.find(q, {"_id": 0}).to_list(2000)
    # Cek UI UAT v3 (S3) — pesanan TUNAI yang keluar lewat Surat Jalan dijurnal Dr Piutang per SJ (gl_service.
    # post_shipment_revenue), jadi pembayarannya dicatat lewat kwitansi seperti biasa. Hanya tunai TANPA SJ
    # (jurnal lama Dr Kas saat jual) yang tetap bukan piutang.
    cash_ids = [o["id"] for o in orders if order_payment_method(o) in NON_AR_METHODS]
    cash_with_sj = set(await db.shipments.distinct(
        "order_id", {"order_id": {"$in": cash_ids}, "status": {"$nin": ["cancelled", "void", "voided"]}})) if cash_ids else set()
    rows = []
    for o in orders:
        if o.get("status") in DEAD_STATUSES:
            continue
        if order_payment_method(o) in NON_AR_METHODS and o["id"] not in cash_with_sj:
            continue
        gt = order_grand_total(o)
        paid = order_paid(o)
        outstanding = round(gt - paid, 2)
        if outstanding <= EPS:
            continue
        rows.append({
            "order_id": o["id"],
            "entity_id": o.get("entity_id", ""),
            "number": o.get("number", o["id"]),
            "grand_total": round(gt, 2),
            "paid_total": round(paid, 2),
            "outstanding": outstanding,
            "payment_status": o.get("payment_status") or _payment_status(gt, paid),
            "created_at": o.get("created_at"),
            # PM-T3 — instruksi bayar pesanan (PM-T2): bahan isian "Rekening penerima" form kwitansi dan peringatan
            # "Tidak sesuai instruksi bayar pesanan {nomor} ({rekening instruksi})".
            "receiving_account_id": o.get("receiving_account_id") or "",
            "receiving_account": dict(o.get("receiving_account") or {}),
            "payment_code": o.get("payment_code") or "",
        })
    rows.sort(key=lambda r: str(r.get("created_at") or ""))
    return rows


async def isi_tagih_sekarang(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """S3 (pelatihan 18 Nov) — tagihan terbuka bertermin DP: `due_now` = yang ditagih SEKARANG menurut jadwal tagihan
    (uang muka "sebelum kirim"), angka yang sama dengan baris Penagihan & Penerimaan. Bahan isian bawaan alokasi form
    Terima pembayaran — dulu terisi seluruh sisa pesanan, padahal yang ditransfer pelanggan baru uang mukanya.
    Pesanan bukan termin DP / tidak ada baris jatuh tempo: tanpa `due_now` (perilaku lama). Hanya untuk daftar layar."""
    from services import entity_master_service as ems
    from services.payment_variance_service import tagihan_uang_muka
    kode = {r["order_id"]: r for r in rows}
    orders = [o async for o in db.sales_orders.find({"id": {"$in": list(kode)}},
                                                    {"_id": 0, "id": 1, "payment_term_code": 1, "entity_id": 1})]
    dp_cache: Dict[Any, float] = {}
    for o in orders:
        code = o.get("payment_term_code") or ""
        key = (code, o.get("entity_id") or "")
        if not code:
            continue
        if key not in dp_cache:
            row = await ems.resolve_row("payment-terms", code, key[1], include_inactive=True)
            dp_cache[key] = float((row or {}).get("dp_percent") or 0)
        if dp_cache[key] <= 0:
            continue
        um = await tagihan_uang_muka(o)
        if um and um["due_now"] > EPS:
            kode[o["id"]]["due_now"] = round(min(um["due_now"], kode[o["id"]]["outstanding"]), 2)
    return rows


#: LB-T4 (B3) — pesan pemandu kwitansi transfer sales ke pesanan yang menunggu lapor bayar.
PESAN_PAKAI_LAPOR_BAYAR = "Pesanan ini menunggu lapor bayar — pakai Lapor bayar"


def _tujuan_keputusan_alokasi(payload: Dict[str, Any]) -> List[str]:
    """Pesanan yang akan dibayar keputusan selisih "alokasikan ke pesanan lain" yang dikirim bersama kwitansi
    (`payload.variance = {kind: "allocate", allocations: [...]}` → `payment_variance_service.decide_receipt`). Dibangun
    dengan rencana YANG SAMA dengan pembayarnya (`payment_variance_service._rencana_alokasi`, id dinormalkan
    `ar_allocation_service.id_pesanan`) — R11: id berspasi tidak bisa lolos pagar lalu tetap dibayar."""
    v = payload.get("variance") or {}
    if not isinstance(v, dict) or str(v.get("kind") or "").strip() != "allocate":
        return []
    from services import payment_variance_service as _pvs
    return [r["order_id"] for r in _pvs._rencana_alokasi([a for a in v.get("allocations") or [] if isinstance(a, dict)])]


async def pagar_lapor_bayar(actor: Any, order_ids: List[Any]) -> None:
    """LB-T4 (B3, ketetapan R11) — SATU pagar untuk setiap jalan uang/titipan ke pesanan: pelaku tanpa
    `payment_report.decide` tidak boleh mengalokasikan APA PUN ke pesanan yang wajib bayar dulu dan belum dilepas ke
    gudang (`pay_hold_service.wajib_bayar_sebelum_gudang`, R12 — termasuk sebelum disetujui, sebelum penanda `pay_hold`
    ada) — uang baru non-tunai, deposit/titipan pelanggan, saldo kredit, titipan bank, maupun pelunasan kasus keuangan.
    Pengecualian diputus pemanggilnya, tidak di sini: uang TUNAI baru di kwitansi (diatur `pembayaran.sales_terima_tunai`,
    `_pagar_lapor_bayar`) dan saldo retur pesanan pengganti (R18-a, `store_credit_service`). Id dinormalkan `ar_allocation_service.id_pesanan`. Tanpa tulisan; 409 berkalimat.

    Pemanggil: `create_receipt` (alokasi kwitansi + keputusan selisih yang dikirim bersamanya),
    `payment_variance_service.decide_receipt` (keputusan "alokasikan" dari antrean), `store_credit_service._redeem_locked`
    (penebusan saldo kredit — R18-a: kecuali saldo retur yang diterapkan otomatis ke pesanan pengganti,
    `store_credit_service.SUMBER_RETUR_PENGGANTI`), `routers/bank_reconciliation.allocate_holding` (titipan dana bank),
    dan `finance_case_service.resolve` (pelunasan lewat kasus keuangan)."""
    from services.ar_allocation_service import id_pesanan
    ids = list(dict.fromkeys(i for i in (id_pesanan(x) for x in order_ids or []) if i))
    if not ids:
        return
    from dependencies import has_permission
    if await has_permission(actor if isinstance(actor, dict) else {}, "payment_report", "decide"):
        return
    from services import pay_hold_service as _phs
    async for o in db.sales_orders.find({"id": {"$in": ids}, "status": {"$in": list(_phs.STATUS_SEBELUM_GUDANG)}},
                                        {"_id": 0}):
        if await _phs.wajib_bayar_sebelum_gudang(o):
            raise HTTPException(status_code=409, detail=PESAN_PAKAI_LAPOR_BAYAR)


async def _pagar_lapor_bayar(payload: Dict[str, Any], actor: Dict[str, Any], *, entity_id: str, method: str,
                             amount: float, use_deposit_amount: float, customer_id: str, total_funds: float) -> None:
    """B3 untuk kwitansi: pesanan yang akan menerima dana kwitansi ini (alokasi eksplisit atau rencana FIFO yang sama
    dengan efeknya) + tujuan keputusan selisih "alokasikan" yang dikirim bersamanya → `pagar_lapor_bayar`. Alokasi
    kwitansi dikecualikan HANYA bila seluruh dananya uang TUNAI baru (cara bayar tunai daftar induk,
    `payment_method_service.is_cash`, tanpa deposit dipakai) — tunai diatur `pembayaran.sales_terima_tunai`. Keputusan
    selisih "alokasikan" memakai titipan pelanggan, jadi selalu dinilai."""
    from services import payment_method_service as _pms
    tunai_baru = amount > EPS and use_deposit_amount <= EPS and await _pms.is_cash(entity_id, method)
    ids: List[str] = [] if tunai_baru else await _rencana_pesanan(
        customer_id, entity_id, payload.get("allocations") or [], total_funds)
    await pagar_lapor_bayar(actor, ids + _tujuan_keputusan_alokasi(payload))


async def buka_tahan_bayar(order_ids: List[str], actor: Dict[str, Any], why: str) -> List[str]:
    """LB-T4 (R5, R10-d, R10-e) — sesudah uang SAH masuk ke pesanan: pesanan yang sedang ditahan bayar
    (`pay_hold_service.ditahan`) diperiksa ulang lewat `pay_hold_service.clear_if_paid` (buka tahan bila bagian wajib
    sudah terbayar, lalu lepas otomatis bila Admin Sales sudah "Periksa & lepas"). Dipanggil di titik selesai setiap
    jalan uang ke pesanan: kwitansi tuntas (`create_receipt`, termasuk Terima lapor bayar), keputusan selisih
    "alokasikan" (`payment_variance_service`), dan kwitansi yang baru cocok mutasi bank (`bank_recon_service`, dasar
    `terverifikasi`). Efek samping: galat dicatat, uang tetap sah. → id pesanan yang dilepas ke gudang."""
    out: List[str] = []
    try:
        ids = list(dict.fromkeys(str(i) for i in order_ids or [] if i))
        if not ids:
            return out
        from services import pay_hold_service as _phs
        tahan = [o["id"] async for o in db.sales_orders.find(
            {"id": {"$in": ids}, **_phs.saringan_ditahan()}, {"_id": 0, "id": 1})]
        for oid in tahan:
            try:
                if await _phs.clear_if_paid(oid, actor, why=why):
                    out.append(oid)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[pay_hold] buka tahan bayar %s sesudah %s gagal: %s", oid, why, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[pay_hold] pemeriksaan tahan bayar sesudah %s gagal: %s", why, exc)
    return out


async def create_receipt(payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    customer = await db.customers.find_one({"id": payload.get("customer_id")}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")

    amount = round(float(payload.get("amount", 0) or 0), 2)              # kas baru diterima
    use_deposit_amount = round(float(payload.get("use_deposit_amount", 0) or 0), 2)  # dana dari deposit (P2-5)
    if amount < 0 or use_deposit_amount < 0:
        raise HTTPException(status_code=400, detail="Jumlah pembayaran tidak valid")

    deposit_avail = await get_deposit_balance(customer["id"])
    if use_deposit_amount > deposit_avail + EPS:
        raise HTTPException(
            status_code=400,
            detail=f"Deposit tidak cukup (tersedia {rupiah(deposit_avail)})")

    total_funds = round(amount + use_deposit_amount, 2)
    if total_funds <= EPS:
        raise HTTPException(status_code=400, detail="Jumlah pembayaran harus > 0")

    receipt_date = payload.get("receipt_date") or now_iso()
    # FASE E-1 (E1.10) — kwitansi milik badan usaha pelanggan/konteks, bukan default.
    entity_id = (payload.get("entity_id") or customer.get("entity_id")
                 or active_entity_or(DEFAULT_ENTITY_ID))
    # PM-T1 — cara bayar dari daftar induk (kata lama → kode kanonik; tak dikenal / nonaktif di PT ini → 400)
    # SEBELUM apa pun ditulis.
    from services import payment_method_service as _pms
    try:
        cara = await _pms.wajib(entity_id, payload.get("method") or "transfer", arah="masuk")
    except _pms.CaraBayarError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    method = cara["code"]
    # LB-T4 (B3, R11) — pencatat tanpa `payment_report.decide` tidak boleh mengalokasikan apa pun (kecuali uang tunai baru)
    # ke pesanan yang tertahan bayar; ditolak SEBELUM apa pun ditulis — uangnya dilaporkan lewat Lapor bayar.
    await _pagar_lapor_bayar(payload, actor, entity_id=entity_id, method=method, amount=amount,
                             use_deposit_amount=use_deposit_amount, customer_id=customer["id"],
                             total_funds=total_funds)
    # FN-10 — periode tertutup ditolak SEBELUM kwitansi/alokasi/deposit dimutasi.
    from services import gl_service as _glp
    try:
        await _glp.preflight_posting(entity_id, receipt_date)
    except _glp.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # PM-T4 (K-36) — tunai yang dicatat bukan pemegang kas (`cash.create`): `pembayaran.sales_terima_tunai` PT kwitansi
    # menentukan kas langsung (bawaan, perilaku lama) / titipan di tangan pencatat / dilarang (403). Batas titipan per
    # orang diperiksa di sini (409) — semua SEBELUM nomor, deposit, dan alokasi.
    from services import cash_holding_service as _cth
    mode_tunai = await _cth.mode_tunai(entity_id, actor, cara, amount)
    titipan = mode_tunai == _cth.MODE_TITIPAN
    if titipan:
        await _cth.periksa_batas(entity_id, actor, amount)
    # PK-20 + PM-T3 — rekening penerima (milik PT, aktif, penerimaan pelanggan, melayani cara bayar), nomor referensi,
    # jatuh tempo giro, dan tanda "tidak sesuai instruksi" diperiksa SEBELUM kwitansi/alokasi/deposit.
    uang = await periksa_uang_masuk(payload, entity_id=entity_id, cara=cara, amount=amount,
                                    customer_id=customer["id"], total_funds=total_funds, titipan=titipan)
    uang["titipan"] = titipan
    payload["account_id"] = uang["account_id"]
    payload["_uang_masuk"] = uang
    # PK-19 (SL-08, FX-05) — SEMUA target eksplisit diperiksa satu pemeriksa (pelanggan, PT, status pesanan, sisa
    # tagihan) SEBELUM deposit direservasi; tolak di sini = tidak ada kwitansi, kas, deposit, maupun baris.
    explicit = payload.get("allocations") or []
    if explicit:
        total_alloc = round(sum(float(a.get("amount", 0) or 0) for a in explicit), 2)
        if total_alloc > total_funds + EPS:
            raise HTTPException(status_code=400, detail="Total alokasi melebihi dana (kas + deposit)")
        from services import ar_allocation_service as _aas
        await _aas.validate_targets(
            "kas" if amount > EPS else "deposit",
            [{"order_id": a.get("order_id"), "amount": a.get("amount")} for a in explicit
             if round(float(a.get("amount", 0) or 0), 2) > 0],
            customer_id=customer["id"], entity_id=entity_id)

    receipt_id = new_id("arc")
    number = await next_doc_number("ar_receipts", "number", "AR-", entity_id=entity_id)
    # W2-017 — dana deposit DIRESERVASI (CAS) sebelum alokasi SO; gagal → 409 tanpa efek apa pun.
    await _adjust_deposit(customer["id"], -use_deposit_amount)
    try:
        return await _create_receipt_after_reserve(payload, actor, customer, amount, use_deposit_amount,
                                                   total_funds, method, receipt_date, entity_id,
                                                   receipt_id, number)
    except BaseException:
        # G3 V3-AR-01 — kwitansi yang efeknya belum tuntas (atau belum lahir) dibatalkan SELURUHNYA:
        # alokasi SO dicari dari data (payments.receipt_id), bukan daftar di memori.
        r = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
        if not r or r.get("effects_done") is False:
            await _rollback_unfinished_receipt(receipt_id, r, customer["id"], use_deposit_amount)
        raise


async def _rollback_unfinished_receipt(receipt_id: str, r: Optional[Dict[str, Any]], customer_id: str,
                                       use_deposit_amount: float) -> None:
    # PK-19 — kwitansi yang gagal lahir tidak pernah sah: barisnya DICABUT (bukan dibalik) lewat modul alokasi.
    from services import ar_allocation_service as _aas
    await _aas.remove_unborn(receipt_id)
    from services import gl_service as _gl
    async for c in db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": receipt_id,
                                              "status": {"$ne": "void"}}, {"_id": 0, "id": 1}):
        await db.cash_transactions.update_one({"id": c["id"]}, {"$set": {"status": "void", "updated_at": now_iso()}})
        try:
            await _gl.post_cash_void(c["id"], label=f"rollback {receipt_id}", created_by="system")
        except Exception as exc:  # noqa: BLE001
            logger.error("[create_receipt] rollback jurnal kas %s gagal: %s", c["id"], exc)
    if r and r.get("cash_holding_id"):   # PM-T4 — titipan kwitansi yang gagal lahir dibatalkan + jurnalnya dibalik
        from services import cash_holding_service as _cth
        await _cth.batal_lahir(receipt_id)
    if r:
        try:
            await _gl.reverse_deposit_only_receipt(receipt_id, label=f"rollback {r.get('number', '')}",
                                                   created_by="system")
        except Exception as exc:  # noqa: BLE001
            logger.error("[create_receipt] rollback reklas deposit %s gagal: %s", receipt_id, exc)
        if r.get("deposit_credited"):
            await _adjust_deposit(customer_id, -float(r.get("unapplied_amount") or 0))
        await db.ar_receipt_failures.insert_one({**r, "failed_at": now_iso()})
        await db.ar_receipts.delete_one({"id": receipt_id, "effects_done": False})
    await _adjust_deposit(customer_id, use_deposit_amount)   # kompensasi reservasi


async def _create_receipt_after_reserve(payload, actor, customer, amount, use_deposit_amount, total_funds,
                                       method, receipt_date, entity_id, receipt_id, number) -> Dict[str, Any]:

    # FASE G-3 — hitung SELISIH PEMBAYARAN sebelum alokasi mengubah outstanding.
    # `expected` selalu dihitung server-side dari tagihan yang jatuh tempo, sehingga
    # sisi klien tidak bisa mengarang angka "seharusnya".
    from services import payment_variance_service as pvs
    explicit = payload.get("allocations") or []
    assessment = await pvs.pre_assess(customer["id"], total_funds, explicit,
                                      as_of=receipt_date, entity_id=entity_id)

    # Tentukan alokasi (dibatasi total dana = kas baru + deposit dipakai). PK-19 — tiap alokasi lewat SATU fungsi
    # alokasi (`ar_allocation_service.allocate`) dan dipecah menurut sumber dananya: kas baru dipakai lebih dulu, lalu
    # deposit, menurut urutan alokasi (ASUMSI unit: baris `kas` = uang yang benar-benar masuk). Galat di tengah →
    # kompensasi `_rollback_unfinished_receipt` (kwitansi belum lahir → barisnya dicabut).
    from services import ar_allocation_service as _aas
    dana = {"kas": amount, "deposit": use_deposit_amount}

    async def _alokasikan(i: int, oid: str, amt: float, line_seq: int = 0) -> Dict[str, Any]:
        parts: List[Dict[str, Any]] = []
        res: Dict[str, Any] = {}
        for kind in ("kas", "deposit"):
            take = round(min(dana[kind], amt - sum(p["amount"] for p in parts)), 2)
            if take <= EPS:
                continue
            res = await _aas.allocate(
                kind=kind, order_id=oid, amount=take, source_id=receipt_id, source_number=number,
                customer_id=customer["id"], entity_id=entity_id, date=receipt_date, actor=actor,
                method=method if kind == "kas" else "deposit", plan_line_seq=line_seq, seq=str(i))
            dana[kind] = round(dana[kind] - take, 2)
            parts.append({"kind": kind, "amount": take, "payment_id": res["payment_id"]})
        return {"order_id": oid, "order_number": res.get("order_number", oid), "applied": round(amt, 2),
                "outstanding_after": res.get("outstanding_after"), "payment_status": res.get("payment_status"),
                "entity_id": res.get("entity_id", ""), "plan_line_seq": int(line_seq or 0), "parts": parts}

    allocations: List[Dict[str, Any]] = []
    if explicit:
        planned = [(a["order_id"], round(float(a.get("amount", 0) or 0), 2),
                    int(a.get("plan_line_seq") or 0)) for a in explicit
                   if round(float(a.get("amount", 0) or 0), 2) > 0]
        for i, (oid, amt, seq) in enumerate(planned):
            allocations.append(await _alokasikan(i, oid, amt, seq))
    else:
        remaining = total_funds
        for oo in await list_open_orders(customer["id"], entity_id=entity_id):
            if remaining <= EPS:
                break
            take = round(min(remaining, oo["outstanding"]), 2)
            if take <= EPS:
                continue
            allocations.append(await _alokasikan(len(allocations), oo["order_id"], take))
            remaining = round(remaining - take, 2)

    applied_total = round(sum(a["applied"] for a in allocations), 2)
    unapplied = round(total_funds - applied_total, 2)
    uang = payload.get("_uang_masuk") or {}
    # Perubahan deposit: deposit terpakai berkurang, sisa tak teralokasi masuk deposit (P2-5).
    deposit_delta = round(unapplied - use_deposit_amount, 2)

    doc = {
        "id": receipt_id,
        "number": number,
        "customer_id": customer["id"],
        "customer_name": customer.get("name", ""),
        "entity_id": entity_id,
        "receipt_date": receipt_date,
        "method": method,
        "amount": amount,
        "used_deposit": use_deposit_amount,
        "total_funds": total_funds,
        "applied_total": applied_total,
        "unapplied_amount": unapplied,
        "deposit_delta": deposit_delta,
        "allocations": allocations,
        "account_id": payload.get("account_id") or "",   # PK-20 — rekening penerima kas (kosong = tanpa kas baru)
        # PM-T3 — cara bayar kanonik (`method` tetap ditulis sama untuk pembaca lama), potret rekening, referensi,
        # tanda tidak sesuai instruksi, dan status verifikasi bank (diisi rekonsiliasi).
        "payment_method_code": method,
        "account_snapshot": uang.get("account_snapshot") or {},
        "reference_no": uang.get("reference_no", ""),
        "giro_due_date": uang.get("giro_due_date", ""),
        "proof_url": uang.get("proof_url", ""),
        "instruction_mismatch": bool(uang.get("instruction_mismatch")),
        "mismatch_note": uang.get("mismatch_note", ""),
        "instruction_mismatch_orders": uang.get("instruction_mismatch_orders") or [],
        **VERIFIKASI_AWAL,
        # PM-T4 — kwitansi tunai yang uangnya dicatat sebagai titipan di tangan pencatatnya (tanpa kas sampai disetor).
        "cash_holding_id": _titipan_id(receipt_id) if uang.get("titipan") else "",
        "notes": payload.get("notes", ""),
        "status": "posted",
        "effects_done": False,   # G3 V3-AR-01 — True hanya setelah kas/GL/deposit tuntas
        # FASE G-3 — catatan selisih pembayaran (bahan antrean keputusan & INV-VAR).
        "variance": pvs.variance_block(assessment),
        "created_by": actor.get("id"),
        "created_by_name": actor.get("name", ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        # AG-T3 — kwitansi dari kartu tindakan asisten yang disetujui (hanya kartu `running` milik sesi ini).
        **card_field(),
        # LB-T4 — rujukan balik ke laporan bayar yang diterima Finance (opsional; hanya pemanggil layanan yang mengisinya —
        # `POST /ar-receipts` tidak menerima isian ini). Kunci pemulihan Terima: satu laporan = satu kwitansi.
        **({"source": "payment_report", "payment_report_id": str(payload["payment_report_id"]),
            "payment_report_number": str(payload.get("payment_report_number") or "")}
           if payload.get("payment_report_id") else {}),
    }
    await db.ar_receipts.insert_one(doc)
    # FASE G-4 — kwitansi menaut ke SETIAP pesanan yang dilunasinya (dua arah).
    from services import doc_refs_service as _refs
    for _al in allocations or []:
        if _al.get("order_id"):
            await _refs.safe_link(("ar_receipt", receipt_id), ("sales_order", _al["order_id"]),
                                  "settles", note="pembayaran dialokasikan ke pesanan")
            # FASE G-2 — jadwal pembayaran (rencana) sudah dihitung ulang oleh `allocate` (PK-19).

    # P0-1 — posting kas masuk (hanya untuk kas baru; deposit bukan kas baru). PM-T4 — kwitansi titipan: TANPA kas;
    # titipan + jurnalnya (Dr piutang titipan karyawan / Cr sisi kredit yang sama dengan jurnal kas kwitansi).
    if doc.get("cash_holding_id"):
        from services import cash_holding_service as _cth
        await _cth.buat_titipan(doc, actor)
        cash_txn_id = None
    else:
        cash_txn_id = await _post_cash_in(doc, actor, uang.get("pay_codes"), uang.get("cash_type") or "")
    if cash_txn_id:
        doc["cash_txn_id"] = cash_txn_id
        await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {"cash_txn_id": cash_txn_id}})
    elif use_deposit_amount > EPS:
        await _post_deposit_gl(doc, actor)   # W2-015 — reklas nonkas, bukan kas fiktif

    # F-01 (audit 2026-09-02) — order yang menjadi berpendapatan karena pembayaran ini
    # (kebijakan `_revenue_eligible`) dijurnal SEKARANG, bukan menunggu restart.
    for _al in allocations or []:
        try:
            from services import gl_service as _gl
            await _gl.post_order_revenue_and_cogs(_al["order_id"])
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger("ar_receipt").error(
                "GL pendapatan order %s gagal setelah kwitansi %s: %s",
                _al.get("order_id"), number, exc)

    # P2-5 — sesuaikan saldo deposit customer (pemakaian sudah direservasi di awal — W2-017).
    await _adjust_deposit(customer["id"], unapplied)
    await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {"deposit_credited": True, "effects_done": True}})

    # ── FASE G-3 — selesaikan selisih pembayaran ────────────────────────────
    # Di dalam toleransi → diputus OTOMATIS (tetap berlabel, tetap bisa diaudit).
    # Di luar toleransi → keputusan eksplisit bila petugas sudah memilih di dialog,
    # kalau belum: kwitansi masuk antrean "Selisih Bayar" (tidak ada yang senyap).
    decision = None
    v = doc.get("variance") or {}
    try:
        if v.get("direction") == pvs.DIR_ROUNDING:
            decision = await pvs.auto_resolve_receipt(doc, actor)
        elif v.get("needs_decision") and (payload.get("variance") or {}).get("kind"):
            decision = await pvs.decide_receipt(receipt_id, payload["variance"], actor)
    except pvs.VarianceError as exc:
        # Keputusan gagal (mis. wewenang kurang) TIDAK boleh membatalkan uang yang sudah
        # masuk — kwitansi tetap sah dan selisihnya menunggu di antrean, lengkap dg sebab.
        await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {
            "variance.decision_error": str(exc), "updated_at": now_iso()}})
    fresh = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
    out = safe_doc(fresh or doc)
    if decision:
        out["variance_decision"] = decision
    # CR-T2 — kwitansi tersimpan (pembayaran terakhir, giro belum cair): saldo piutang tersimpan pasangan dihitung ulang
    from services import customer_balance_service as _cbs
    await _cbs.refresh_safe(out.get("customer_id") or "", out.get("entity_id") or None)
    # LB-T4 (R5) — tahan bayar pesanan yang dialokasi diperiksa ulang (buka + lepas otomatis); tidak disimpan di kwitansi.
    # Pesanan yang dibayar keputusan selisih "alokasikan" sudah diperiksa keputusannya sendiri (R10-d).
    dilepas = await buka_tahan_bayar([a.get("order_id") for a in allocations or []], actor, f"kwitansi {number}")
    out["released_order_ids"] = list(dict.fromkeys(dilepas + list((decision or {}).get("released_order_ids") or [])))
    return out


def _pesan_deposit_terpakai(r: Dict[str, Any], dep_delta: float) -> str:
    return (f"Kelebihan bayar {rupiah(dep_delta)} dari kwitansi {r.get('number', '')} sudah dipakai sebagai deposit. "
            "Batalkan dulu kwitansi yang memakai deposit tersebut, lalu batalkan kwitansi ini.")


async def _void_step(receipt_id: str, update: Dict[str, Any]) -> None:
    """PK-19 — tulis penanda satu langkah EFEK pembatalan (`void_intent.steps.*`) sesudah langkahnya jadi."""
    await db.ar_receipts.update_one({"id": receipt_id}, {**update, "$set": {
        **(update.get("$set") or {}), "updated_at": now_iso()}})


async def void_receipt(receipt_id: str, actor: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    """Batalkan penerimaan AR (P2-6) dengan urutan `02_STANDAR.md` §1 (PK-19, SL-06).

    PERIKSA status + periode buku hari ini (tanggal pembalik) → NIAT: klaim + `void_intent.status="pending"` → EFEK,
    tiap langkah memeriksa penandanya di `void_intent.steps` lalu menulisnya sesudah jadi: (1) kelebihan bayar ditarik
    dari deposit (CAS), (2) keputusan selisih dibatalkan, (3) baris pembayaran tiap pesanan DIBALIK lewat
    `ar_allocation_service.reverse` (baris pembalik bertanggal hari ini, baris asal tetap), (4) kas kwitansi di-void,
    (5) deposit yang dipakai dikembalikan → JURNAL pembalik (kas, reklas deposit, reklas uang muka) lewat
    `post_durable` (`void_gl_status`) → SELESAI `status="void"`, `void_intent.status="done"`. Kunci dilepas di
    `finally`: galat di tengah tidak meninggalkan kunci, dan panggilan ulang meneruskan dari langkah yang belum
    bertanda. `reason` (FASE P5) disimpan sebagai `voided_reason`."""
    r = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Kwitansi tidak ditemukan.")
    if r.get("status") == "void":
        raise HTTPException(status_code=409, detail="Kwitansi ini sudah dibatalkan.")
    # PM-T3 — kwitansi yang kasnya sudah dicocokkan dengan mutasi bank (penuh = terverifikasi, atau sebagian) tidak
    # dibatalkan diam-diam: pencocokannya dilepas dulu di Rekonsiliasi Bank (baris mutasi tidak menunjuk kas batal).
    if r.get("bank_verified") or await db.cash_transactions.find_one(
            {"ref_type": "ar_receipt", "ref_id": receipt_id, "status": {"$ne": "void"},
             "reconciled_amount": {"$gt": EPS}}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=409, detail=PESAN_BATAL_TERVERIFIKASI)
    # PM-T4 — kwitansi titipan yang titipannya sudah (sebagian) disetor / sedang diajukan dalam setoran → 409.
    from services import cash_holding_service as _cth
    await _cth.periksa_batal_kwitansi(r)
    # PERIKSA — periode buku hari ini (tanggal jurnal pembalik) sebelum apa pun dibalik (`02` §1 P2).
    from services.book_date import periksa_periode_dokumen_409
    from services.posting_registry import tanggal_pembalik
    await periksa_periode_dokumen_409(r.get("entity_id") or "", tanggal_pembalik(r.get("receipt_date")) or None,
                                      jenis="pembatalan kwitansi")
    dep_delta = round(float(r.get("deposit_delta", 0) or 0), 2)
    if dep_delta > EPS and not ((r.get("void_intent") or {}).get("steps") or {}).get("deposit_pulled") \
            and await get_deposit_balance(r.get("customer_id") or "") < dep_delta - EPS:
        raise HTTPException(status_code=409, detail=_pesan_deposit_terpakai(r, dep_delta))
    # PK-19 — pembalik baris pembayaran tidak boleh membuat terbayar negatif (sudah dipindah lewat kasus) → 409 di sini,
    # sebelum niat dan efek apa pun.
    from services import ar_allocation_service as _aas
    await _aas.reverse_check(receipt_id, [a.get("order_id") for a in r.get("allocations") or [] if a.get("order_id")])

    # NIAT — INV-ATOMIC-01: klaim kwitansi SEBELUM uang dibalik (dua batal bersamaan → satu 409).
    from services import atomic_claim as _saga
    lk = await _saga.claim("ar_receipts", receipt_id, "ar_receipt_void",
                           precondition={"status": {"$ne": "void"}}, actor=actor.get("name", ""))
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    try:
        intent = dict(lk.get("void_intent") or {})
        if intent.get("status") != "pending":
            intent = {"status": "pending", "reason": (reason or "").strip(), "by": actor.get("name", ""),
                      "at": now_iso(), "steps": {"deposit_pulled": False, "decision_reversed": False, "orders": [],
                                                 "cash": [], "deposit_restored": False}}
            await _void_step(receipt_id, {"$set": {"void_intent": intent}})
        reason = (reason or "").strip() or intent.get("reason", "")
        steps = intent.get("steps") or {}
        label = f"kwitansi {r.get('number', '')} dibatalkan"

        # EFEK 0 — PM-T4: titipan kwitansi → `batal` dengan syarat belum disetor (kalah balapan dengan penerimaan
        # setoran → 409 sebelum efek lain). Jurnal pembaliknya di langkah JURNAL (`posting_registry.post_receipt_void`).
        await _cth.batalkan_untuk_kwitansi(r, reason or label)

        # EFEK 1 — P20 APAR-02 / W2-016: kelebihan bayar kwitansi ini ditarik atomik (CAS) lebih dulu.
        if dep_delta > EPS and not steps.get("deposit_pulled"):
            try:
                await _adjust_deposit(r["customer_id"], -dep_delta)
            except HTTPException:
                raise HTTPException(status_code=409, detail=_pesan_deposit_terpakai(r, dep_delta))
            await _void_step(receipt_id, {"$set": {"void_intent.steps.deposit_pulled": True}})

        # EFEK 2 — FASE G-3: keputusan selisih yang sudah dijalankan dibalik lebih dulu (jejaknya tetap).
        decision_id = ((r.get("variance") or {}).get("decision_id") or "").strip()
        if decision_id and not steps.get("decision_reversed"):
            from services import payment_variance_service as _pvs
            try:
                await _pvs.reverse_decision(decision_id, label, actor)
            except _pvs.VarianceError as exc:
                raise HTTPException(status_code=int(getattr(exc, "status_code", 400) or 400), detail=str(exc)) from exc
            await _void_step(receipt_id, {"$set": {"void_intent.steps.decision_reversed": True}})

        # EFEK 3 — baris pembayaran tiap pesanan dibalik (tidak dihapus); periode lalu tidak berubah mundur.
        from services import ar_allocation_service as _aas
        # Pelatihan 18 Nov (uji adversarial, kelas V-09) — kwitansi bertanggal MAJU: baris pembalik tidak boleh mendahului
        # baris pembayaran aslinya (umur piutang / rekening koran); tanggal sama dengan pembalik jurnal kasnya.
        from services.posting_registry import tanggal_pembalik
        hari_ini = r.get("receipt_date") if tanggal_pembalik(r.get("receipt_date")) else now_iso()
        done_orders = set(steps.get("orders") or [])
        for alloc in r.get("allocations") or []:
            oid = alloc.get("order_id")
            if not oid or oid in done_orders:
                continue
            hasil = await _aas.reverse(source_id=receipt_id, date=hari_ini, actor=actor, reason=reason or label,
                                       order_id=oid)
            ringkas = next((h for h in hasil if h["order_id"] == oid), {})
            await _void_step(receipt_id, {
                "$addToSet": {"void_intent.steps.orders": oid},
                "$push": {"reversed_orders": {"order_id": oid, "reversed": ringkas.get("reversed", 0.0),
                                              "outstanding_after": ringkas.get("outstanding_after"),
                                              "payment_status": ringkas.get("payment_status")}}})
            done_orders.add(oid)

        # EFEK 4 — kas kwitansi di-void (saldo kas tak lagi menghitungnya); jurnal pembalik di langkah JURNAL.
        async for c in db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": receipt_id,
                                                  "status": {"$ne": "void"}}, {"_id": 0, "id": 1}):
            await db.cash_transactions.update_one({"id": c["id"], "status": {"$ne": "void"}},
                                                  {"$set": {"status": "void", "updated_at": now_iso()}})
            await _void_step(receipt_id, {"$addToSet": {"void_intent.steps.cash": c["id"]}})

        # EFEK 5 — deposit yang dipakai kwitansi ini dikembalikan (porsi kelebihan sudah ditarik di langkah 1).
        if dep_delta < -EPS and not steps.get("deposit_restored"):
            await _adjust_deposit(r["customer_id"], -dep_delta)
            await _void_step(receipt_id, {"$set": {"void_intent.steps.deposit_restored": True}})

        # JURNAL — PK-18 (GL-02): pembalik kas, reklas deposit, dan reklas uang muka lewat pintu tahan-gagal
        # (`void_gl_status`/`void_gl_error`; ulang dari panel Posting Gagal).
        await _void_step(receipt_id, {"$set": {"void_gl_status": "pending"}})
        from services import posting_registry as _preg
        await _preg.durable_receipt_void(r, actor.get("name", "system"))

        # SELESAI
        await db.ar_receipts.update_one({"id": receipt_id}, _saga.finish_set({
            "status": "void", "voided_by": actor.get("name", ""), "voided_at": now_iso(), "voided_reason": reason,
            "variance.needs_decision": False, "variance.resolved": True,
            "void_intent.status": "done", "void_intent.done_at": now_iso(), "updated_at": now_iso()}))
    finally:
        await _saga.release("ar_receipts", receipt_id, token)
    out = safe_doc(await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0}))
    from services import customer_balance_service as _cbs   # CR-T2 — kwitansi batal: saldo tersimpan (turunan)
    await _cbs.refresh_safe(out.get("customer_id") or "", out.get("entity_id") or None)
    return out


#: PK-42 (UX-12) — urutan daftar kwitansi: terbaru dulu, DI KUERI. Dulu 2.000 baris diambil tanpa urutan lalu diurutkan
#: di memori, jadi kwitansi terbaru bisa terbuang begitu baris lebih dari 2.000. `id` = pemecah seri (halaman stabil).
RECEIPT_SORT = [("created_at", -1), ("id", -1)]
#: Batas daftar tanpa halaman (bentuk jawaban lama, larik telanjang) — tetap 2.000, kini sesudah pengurutan.
RECEIPT_UNPAGED_LIMIT = 2000
#: PK-42 — kotak cari riwayat kwitansi (`q`): nomor kwitansi dan nama pelanggan.
RECEIPT_SEARCH_FIELDS = ("number", "customer_name")


def _receipt_query(customer_id: Optional[str], scope: Optional[Dict[str, Any]], q: str = "",
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from pagination import build_search, merge_query
    query: Dict[str, Any] = dict(scope or {})
    if customer_id:
        query["customer_id"] = customer_id
    query = merge_query(query, build_search(q, RECEIPT_SEARCH_FIELDS))
    return merge_query(query, extra) if extra else query


async def saringan_verifikasi(*, bank_verified: Optional[str] = None, older_than_days: Optional[str] = None,
                              method: Optional[str] = None, entity_id: str = "") -> Dict[str, Any]:
    """PM-T3 — saringan daftar kwitansi `?bank_verified=&older_than_days=&method=` → kueri tambahan.

    * `bank_verified=false` = daftar "Belum terverifikasi": kwitansi tidak batal, ber-uang baru, belum cocok mutasi
      bank — kwitansi tunai dan titipan TIDAK PERNAH masuk (tidak ada mutasi bank untuk dicocokkan); `true` = sudah.
    * `older_than_days` dikirim tanpa nilai → batas `payment.hari_wajar_verifikasi_bank` PT; angka → angka itu.
      Kwitansi bertanggal lebih lama dari batas saja yang tampil.
    * `method` = cara bayar (kode/alias; kata lama ikut ketemu)."""
    from datetime import datetime, timedelta, timezone
    from services import payment_method_service as _pms
    syarat: List[Dict[str, Any]] = []
    bv = str(bank_verified or "").strip().lower()
    if bv in ("true", "1", "ya"):
        syarat.append({"bank_verified": True})
    elif bv in ("false", "0", "tidak"):
        syarat += [{"bank_verified": {"$ne": True}}, {"status": {"$ne": "void"}}, {"amount": {"$gt": EPS}},
                   {"method": {"$nin": await _pms.kata_bukan_bank()}}]
    if older_than_days is not None:
        teks = str(older_than_days).strip()
        if teks:
            try:
                hari = int(teks)
            except ValueError:
                raise HTTPException(status_code=400, detail="Umur kwitansi harus berupa angka hari.")
        else:
            from services.config_resolver import value_of
            hari = int(await value_of(KEY_HARI_WAJAR, {"entity_id": entity_id or ""}) or 0)
        batas = (datetime.now(timezone.utc) - timedelta(days=max(hari, 0))).isoformat()
        syarat.append({"receipt_date": {"$lt": batas}})
    if method and str(method).strip():
        syarat.append({"method": {"$in": await _pms.kata_untuk(method)}})
    if not syarat:
        return {}
    return syarat[0] if len(syarat) == 1 else {"$and": syarat}


async def _isi_id_jurnal(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pelatihan 18 Nov — kwitansi lama (sebelum `journal_entry_id` ditulis) berjurnal tetapi tanpa id jurnal: id dibaca
    dari transaksi kasnya (atau jurnal reklas deposit) supaya label "Jurnal Terbit" bisa dibuka. Hanya baca, tanpa tulis."""
    kurang = [r for r in rows if r.get("gl_status") == "posted" and not r.get("journal_entry_id")]
    if not kurang:
        return rows
    kas = [r["cash_txn_id"] for r in kurang if r.get("cash_txn_id")]
    peta: Dict[str, str] = {}
    if kas:
        async for c in db.cash_transactions.find({"id": {"$in": kas}}, {"_id": 0, "id": 1, "journal_entry_id": 1}):
            peta[c["id"]] = c.get("journal_entry_id") or ""
    dep = [r["id"] for r in kurang if not r.get("cash_txn_id")]
    peta_dep: Dict[str, str] = {}
    if dep:
        async for j in db.journal_entries.find({"source_type": "ar_receipt_deposit", "source_id": {"$in": dep},
                                                "status": {"$ne": "void"}}, {"_id": 0, "id": 1, "source_id": 1}):
            peta_dep[j["source_id"]] = j["id"]
    for r in kurang:
        r["journal_entry_id"] = peta.get(r.get("cash_txn_id") or "", "") or peta_dep.get(r["id"], "")
    return rows


async def list_receipts(customer_id: Optional[str] = None,
                        scope: Optional[Dict[str, Any]] = None,
                        extra: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    rows = await db.ar_receipts.find(_receipt_query(customer_id, scope, extra=extra), {"_id": 0}) \
        .sort(RECEIPT_SORT).to_list(RECEIPT_UNPAGED_LIMIT)
    return await _isi_id_jurnal([safe_doc(r) for r in rows])


async def list_receipts_page(customer_id: Optional[str], scope: Optional[Dict[str, Any]], *, page: int,
                             page_size: int, q: str = "", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """PK-42 (UX-12) — satu halaman riwayat kwitansi + jumlah total (kontrak `pagination.envelope`)."""
    from pagination import envelope
    query = _receipt_query(customer_id, scope, q, extra)
    total = await db.ar_receipts.count_documents(query)
    rows = await db.ar_receipts.find(query, {"_id": 0}).sort(RECEIPT_SORT) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return envelope(await _isi_id_jurnal([safe_doc(r) for r in rows]), total, page, page_size)


async def get_receipt(receipt_id: str) -> Optional[Dict[str, Any]]:
    return safe_doc(await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0}))


async def isi_rekening_kwitansi_lama(tulis: bool = False, entity_id: str = "") -> Dict[str, Any]:
    """PM-T3 (H3) — isi `account_id` kas kwitansi LAMA tanpa rekening (sebelum PK-20) dan `account_id` +
    `account_snapshot` kwitansinya, HANYA bila PT kas itu punya tepat satu rekening aktif untuk jenis kasnya
    (`bank_service.sole_account_id` — aturan saldo rekening). Sisanya (PT berekening ganda / tanpa rekening) didaftar
    di `diputus_orang` untuk diputus manusia. `tulis=False` (bawaan) = lapor saja. Idempoten: syarat tulis = field masih
    kosong, jadi putaran kedua tidak mengubah apa pun.

    → `{mode, diisi: [{cash_id, cash_number, receipt_id, receipt_number, entity_id, cash_type, amount, account_id,
    account_name}], diputus_orang: [{… tanpa account, alasan}], diubah}`."""
    from services import bank_service as bs
    kosong = [{"account_id": {"$exists": False}}, {"account_id": {"$in": ["", None]}}]
    q: Dict[str, Any] = {"ref_type": "ar_receipt", "status": {"$ne": "void"}, "$or": kosong}
    if entity_id:
        q["entity_id"] = entity_id
    tunggal: Dict[tuple, str] = {}
    rekening: Dict[str, Dict[str, Any]] = {}
    diisi: List[Dict[str, Any]] = []
    putus: List[Dict[str, Any]] = []
    diubah = 0
    async for t in db.cash_transactions.find(q, {"_id": 0}).sort("txn_date", 1):
        ent, ct = t.get("entity_id") or "", t.get("cash_type") or ""
        kunci = (ent, ct)
        if kunci not in tunggal:
            tunggal[kunci] = await bs.sole_account_id(ent, ct) if ct in bs.CASH_TYPES else ""
        rc = await db.ar_receipts.find_one({"id": t.get("ref_id")}, {"_id": 0, "id": 1, "number": 1}) or {}
        baris = {"cash_id": t["id"], "cash_number": t.get("number", ""), "receipt_id": t.get("ref_id", ""),
                 "receipt_number": rc.get("number", ""), "entity_id": ent, "cash_type": ct,
                 "amount": round(float(t.get("amount") or 0), 2)}
        sole = tunggal[kunci]
        if not sole:
            n = await db.bank_accounts.count_documents({"entity_id": ent, "is_active": {"$ne": False}})
            putus.append({**baris, "alasan": (f"PT punya {n} rekening aktif — pilih rekening kas ini secara manual"
                                              if n else "PT belum punya rekening aktif")})
            continue
        if sole not in rekening:
            rekening[sole] = await db.bank_accounts.find_one({"id": sole}, {"_id": 0}) or {}
        acc = rekening[sole]
        diisi.append({**baris, "account_id": sole, "account_name": acc.get("name", "")})
        if tulis:
            res = await db.cash_transactions.update_one({"id": t["id"], "$or": kosong},
                                                        {"$set": {"account_id": sole, "updated_at": now_iso()}})
            diubah += res.modified_count
            if rc:
                await db.ar_receipts.update_one(
                    {"id": rc["id"], "$or": kosong},
                    {"$set": {"account_id": sole, "account_snapshot": potret_rekening(acc), "updated_at": now_iso()}})
    return {"mode": "tulis" if tulis else "lapor", "diisi": diisi, "diputus_orang": putus,
            "diubah": diubah if tulis else 0}
