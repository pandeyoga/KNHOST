"""PK-20 (SL-11, `02_STANDAR.md` §1 P5) — SATU pembuat transaksi kas (`cash_transactions`).

Setiap rupiah kas lahir dari `create_cash`: periode diperiksa, rekening wajib (milik PT dokumennya), id tetap dari
rujukannya, dan jurnal SELALU lewat pintu tahan-gagal `gl_service.post_cash_durable`. Penjaga statik
`scripts/guardrails/verify_cash_single_door.py` menolak sisipan kas di luar berkas ini.

Pendamping di berkas yang sama:
  * `periksa_rekening` — langkah PERIKSA rekening (tanpa tulisan) untuk pemanggil yang perlu memeriksa lebih awal;
  * `next_cash_number` — satu-satunya pemberi nomor kas;
  * `ensure_posted` — memastikan jurnal kas asal ada (jalur batal & ulang posting);
  * `record_return_cash` — kas refund retur yang dijurnal dokumen induknya (R5.3). (PY-T4: bayar gaji kini kas biasa
    `create_cash(ref_type="payroll_run", contra_account_code=<hutang gaji>)`, `services/hr_payroll_pay.py`.)

Cara memakai: laporan unit `docs/reviews/2026-11-13/hasil/PK-20.md` bagian "Cara memakai pembuat kas".
"""
import hashlib
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

from db import db
from core_utils import now_iso, rupiah

# Akun GL templat yang dianggap "kas kecil" / "kas kasir" (Kas & Bank 3) — sisanya diperlakukan kas_besar/bank.
KAS_KECIL_CODE = "1-1110"
KAS_KASIR_CODE = "1-1105"
EPS = 0.005

#: Label jenis kas di pesan ("{n} rekening Kas Kecil" / "{n} rekening Bank" / "{n} rekening Kas kasir").
CASH_TYPE_LABEL = {"kas_kecil": "Kas Kecil", "kas_besar": "Bank", "kas_kasir": "Kas kasir"}

#: Label rujukan kas di pesan (kode mentah tidak boleh tampil — `02` §4 L1).
REF_LABEL = {
    "manual": "transaksi manual", "ar_receipt": "kwitansi", "ar_refund": "pengembalian dana pelanggan",
    "finance_case": "kasus keuangan", "marketing_cost": "biaya kampanye", "cash_advance": "pencairan uang muka",
    "reimburse_payable": "bayar reimburse", "bank_statement_line": "mutasi bank", "vendor_bill": "faktur pemasok",
    "ap_advance": "uang muka pemasok", "contra_bon": "kontrabon", "landed_cost": "landed cost",
    "sales_return": "retur jual", "purchase_return": "retur beli", "payroll_run": "pembayaran gaji",
    "penalty": "nota denda", "interco_loan": "pinjaman antar-PT", "interco_loan_repayment": "angsuran antar-PT",
    "fixed_asset": "perolehan aset tetap", "fixed_asset_transfer": "pembayaran pindah aset antar-PT",   # PK-23
    "statutory_remittance": "setoran kewajiban gaji",   # PK-22 — setoran BPJS / PPh 21
    "cash_deposit": "setoran titipan tunai sales",       # PM-T4 — tunai yang dipegang sales disetor ke kas/bank
    "fund_transfer": "Pindah Dana",                      # Kas & Bank 1 (Tugas 4) — pindah dana antar rekening satu PT
}

#: Kas & Bank 1 (Tugas 5) — kategori kas manual "Transfer / Top-up" ditutup untuk kas manual BARU: setor tunai, isi kas
#: kecil, dan pindah antar rekening kini lewat dokumen Pindah Dana. Kas LAMA berkategori ini tetap utuh (bisa dibatalkan,
#: diposting ulang; kata kunci jurnal `gl_service.CASH_*_KEYWORDS` tetap untuk pembalik lama).
PESAN_KATEGORI_TRANSFER_DITUTUP = "Pakai Pindah Dana untuk setor tunai, isi kas kecil, dan pindah antar rekening."
_KATA_TRANSFER_DITUTUP = ("transfer", "topup")


def kategori_transfer_ditutup(category: Any) -> bool:
    """True bila kategori kas manual memuat "transfer" atau "top-up" (semua ejaan/huruf: `Top-up`, `top up`, `TOPUP`)."""
    teks = "".join(ch for ch in str(category or "").lower() if ch.isalnum())
    return any(k in teks for k in _KATA_TRANSFER_DITUTUP)


#: Kas & Bank 2 (Tugas 1, C5) — kategori kas manual Pembelian/Gaji ditutup untuk kas manual BARU: pembelian barang lewat
#: PO/tagihan pemasok, gaji lewat Proses Gaji. Kas LAMA tetap utuh (bisa dibatalkan, diposting ulang). `create_cash`
#: (bayar tagihan, Proses Gaji) tidak dijaga — penjagaan hanya di pintu manual (rute + kartu Asisten).
PESAN_KATEGORI_PEMBELIAN_GAJI_DITUTUP = (
    "Kategori Pembelian dan Gaji tidak lagi dipakai di kas manual: pembelian barang lewat PO/tagihan pemasok, "
    "gaji lewat Proses Gaji. Belanja kecil kebutuhan kantor pakai kategori Operasional.")


def kategori_kas_manual_ditutup(category: Any) -> bool:
    """True bila akun lawan jurnal kas manual untuk kategori ini = persediaan atau beban gaji.

    Dihitung dari tabel kata kunci KELUAR yang sama dengan jurnalnya (`gl_service.cash_contra_account`), jadi satu sumber
    kebenaran; dinilai dengan tabel KELUAR untuk kedua arah (spesifikasi §7.8 butir 2)."""
    from services import gl_service as gl
    akun = gl.cash_contra_account({"ref_type": "manual", "direction": "out", "category": str(category or "")})
    return akun in (gl.ACC_PERSEDIAAN, gl.ACC_BEBAN_GAJI)


#: Field dokumen kas yang hanya ditentukan pembuat ini — `extra` tidak boleh menimpanya.
_PROTECTED = frozenset({"id", "amount", "direction", "entity_id", "account_id", "account_code", "cash_type",
                        "ref_type", "ref_id", "seq", "status", "gl_status", "gl_error", "gl_posted",
                        "journal_entry_id", "owner_entity_id", "parent_journal"})


class CashRejected(HTTPException):
    """PK-20 — kas ditolak di langkah PERIKSA / NIAT; tidak ada tulisan apa pun. Pesan siap tampil."""

    def __init__(self, detail: str, status_code: int = 409) -> None:
        super().__init__(status_code=status_code, detail=detail)


class CashPostingError(HTTPException):
    """PK-20 — kas TERSIMPAN (`gl_status="failed"`, tampil di panel Posting Gagal), jurnalnya gagal.

    `txn` = dokumen kas terbaru, `error` = galat jurnal. Bila tidak ditangkap pemanggil → 409 dengan pesan baku."""

    def __init__(self, txn: Dict[str, Any], error: str) -> None:
        self.txn = txn or {}
        self.error = error
        super().__init__(status_code=409, detail=(
            f"Jurnal kas gagal: {error}. Transaksi tersimpan dan bisa diulang dari Posting Gagal."))


def cash_type_for(account_code: str) -> str:
    """Jenis kas dari kode akun TEMPLAT (pemilih refund `/gl/cash-accounts`, akun kas lama): persis 1-1110 = kas kecil,
    persis 1-1105 = kas kasir (Kas & Bank 3), lainnya kas besar. Jangan dipakai untuk akun rekening (`1-1110-01`
    terbaca kas besar) — pakai `jenis_kas_akun`."""
    return {KAS_KECIL_CODE: "kas_kecil", KAS_KASIR_CODE: "kas_kasir"}.get(account_code or "", "kas_besar")


async def jenis_kas_akun(entity_id: str, kode: str) -> str:
    """Kas & Bank 1 (ketetapan R2) — jenis kas akun buku besar `kode` di PT `entity_id`: akun rekening (akun PT
    ber-`bank_account_id`) → jenis REKENING pemiliknya (`bank_service.account_cash_type`); akun lain → `cash_type_for`
    (akun templat lama, seperti dulu)."""
    from services import bank_service as bs
    akun = await db.gl_accounts.find_one({"code": kode or "__none__", "entity_id": entity_id or "__none__",
                                          "bank_account_id": {"$nin": [None, ""]}}, {"_id": 0, "bank_account_id": 1})
    if akun:
        rek = await db.bank_accounts.find_one({"id": akun["bank_account_id"]}, {"_id": 0})
        if rek:
            return bs.account_cash_type(rek)
    return cash_type_for(kode)


async def akun_refund(entity_id: str, account_id: str, kode_pilihan: str = "") -> Dict[str, str]:
    """Kas & Bank 1 — akun kas jurnal refund retur tunai (R5.3: retur jual, retur jual per roll, retur beli).

    `kode_pilihan` = kode pemilih refund `/gl/cash-accounts` (akun templat global, dibaca sebagai JENIS kas —
    ketetapan R5; kosong = kas besar). → `{"account_code": akun kas jurnal, "cash_type": jenis kas akun itu (dikirim ke
    `record_return_cash`), "kode_pilihan": kode pilihan yang disimpan di dokumen (kosong → akun kas besar lama)}`. PT
    sudah memakai akun per rekening + rekening `account_id` ber-sub-akun → sub-akun rekening itu dan jenis REKENINGNYA
    (R2); selain itu kode pilihan dan jenisnya — PT belum aktif: persis seperti dulu."""
    from services import bank_service as bs
    from services import gl_service as gl
    ct = cash_type_for(kode_pilihan)
    pilihan = kode_pilihan or await gl.akun_kas(entity_id, "", ct)
    sub = await gl.akun_rekening(entity_id, account_id)
    if sub:
        ct = bs.account_cash_type(await db.bank_accounts.find_one({"id": account_id}, {"_id": 0}) or {})
    return {"account_code": sub or pilihan, "cash_type": ct, "kode_pilihan": pilihan}


def cash_id(ref_type: str, ref_id: str, direction: str, seq: str = "") -> str:
    """Id tetap kas: `cash_` + 24 heksadesimal pertama SHA-1 dari `ref_type|ref_id|direction|seq`."""
    raw = f"{ref_type}|{ref_id}|{direction}|{seq}".encode("utf-8")
    return "cash_" + hashlib.sha1(raw).hexdigest()[:24]


async def next_cash_number(entity_id: str = "") -> str:
    """Satu-satunya pemberi nomor kas — deret per PT (E1.7); kas grup sudah dihapus (E7.4)."""
    from core_utils import next_doc_number
    return await next_doc_number("cash_transactions", "number", "CASH-", entity_id=(entity_id or None))


async def _nama_pt(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "short_name": 1, "legal_name": 1,
                                                                "name": 1}) or {}
    return e.get("short_name") or e.get("legal_name") or e.get("name") or "PT ini"


def _ref_label(ref_type: str) -> str:
    return REF_LABEL.get(ref_type or "", "dokumen")


async def periksa_rekening(entity_id: str, account_id: str = "", cash_type: str = "") -> Dict[str, Any]:
    """PERIKSA rekening kas (tanpa tulisan). → `{account, account_id, cash_type, account_code}`.

    `account_id` dikirim → harus rekening AKTIF milik `entity_id`; kosong → rekening tunggal PT untuk `cash_type`
    (`bank_service.sole_account_id`); tetap kosong → `CashRejected` 409 "Pilih rekening kas/bank…". Jenis kas dan akun
    buku besar diturunkan dari rekening (`bank_service.account_cash_type`), bukan dari pemanggil. Kas & Bank 1 — akun
    buku besar = `gl_service.akun_kas` (sub-akun rekening bila PT sudah memakai akun per rekening, selain itu akun jenis
    kas seperti sebelumnya)."""
    from services import bank_service as bs
    from services import gl_service as gl
    account_id = (account_id or "").strip()
    if account_id:
        acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
        if not acc or not bs._aktif(acc) or (acc.get("entity_id") or "") != entity_id:
            nama = (acc or {}).get("name") or "yang dipilih"
            raise CashRejected(f"Rekening {nama} bukan rekening aktif {await _nama_pt(entity_id)}.")
    else:
        sole = await bs.sole_account_id(entity_id, cash_type) if cash_type in bs.CASH_TYPES else ""
        if not sole:
            accs = [a async for a in db.bank_accounts.find({"entity_id": entity_id}, {"_id": 0})]
            aktif = [a for a in accs if bs._aktif(a)
                     and (cash_type not in bs.CASH_TYPES or bs.account_cash_type(a) == cash_type)]
            jenis = CASH_TYPE_LABEL.get(cash_type, "kas/bank")
            raise CashRejected(f"Pilih rekening kas/bank untuk transaksi ini. {await _nama_pt(entity_id)} punya "
                               f"{len(aktif)} rekening {jenis}.")
        acc = await db.bank_accounts.find_one({"id": sole}, {"_id": 0})
    ct = bs.account_cash_type(acc)
    return {"account": acc, "account_id": acc["id"], "cash_type": ct,
            "account_code": await gl.akun_kas(entity_id, acc["id"], ct)}


async def _cari_kas(cid: str, *, txn_id: str, ref_type: str, ref_id: str, direction: str,
                    seq: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """→ (id yang dipakai, dokumen yang sudah ada atau None). Kas di id tetap yang sudah `void` = kejadian lama yang
    dibatalkan: rujukan yang sama membuat kejadian berikutnya di id generasi berikutnya (`…|seq#2`, `#3`, …)."""
    if txn_id:
        return txn_id, await db.cash_transactions.find_one({"id": txn_id}, {"_id": 0})
    gen = 1
    while True:
        gid = cid if gen == 1 else cash_id(ref_type, ref_id, direction, f"{seq}#{gen}")
        doc = await db.cash_transactions.find_one({"id": gid}, {"_id": 0})
        if not doc or doc.get("status") != "void":
            break
        gen += 1
    if doc is None and gen == 1 and not seq:
        # Kas lama (sebelum PK-20, id acak) untuk rujukan yang sama dipakai ulang — "kas dicari ulang per rujukan".
        doc = await db.cash_transactions.find_one(
            {"ref_type": ref_type, "ref_id": ref_id, "direction": direction, "status": {"$ne": "void"},
             "seq": {"$in": [None, ""]}}, {"_id": 0})
        if doc:
            gid = doc["id"]
    return gid, doc


async def create_cash(*, entity_id: str, direction: str, amount: float, ref_type: str, ref_id: str,
                      account_id: str = "", cash_type: str = "", seq: str = "", txn_date: str = "",
                      category: str = "", description: str = "", actor: str = "system",
                      contra_account_code: str = "", owner_entity_id: str = "",
                      counterparty_entity_id: str = "", journal_by_parent: str = "",
                      txn_id: str = "", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """PK-20 — buat (atau pakai ulang) SATU transaksi kas lalu jurnalnya. → dokumen kas terbaru.

    1. PERIKSA tanpa tulisan: nominal > 0, arah `in`/`out`, PT bukan grup, rekening (`periksa_rekening`), periode
       (`preflight_posting(owner_entity_id or entity_id, txn_date)`). Gagal → `CashRejected` (409/400).
    2. NIAT + EFEK: `update_one({"id": id tetap}, {"$setOnInsert": dokumen}, upsert=True)` ber-`gl_status: "pending"`.
       Id tetap = `cash_id(ref_type, ref_id, direction, seq)`, atau `txn_id` bila pemanggil menurunkannya sendiri.
       Dokumen yang sudah ada dipakai apa adanya; nominal/arah berbeda → `CashRejected` 409.
    3. JURNAL: selalu `gl_service.post_cash_durable`. `journal_by_parent` (id jurnal induk, atau rujukan jurnal induk
       yang terbit sesudah kas) → `gl_posted: true` → pintu menulis `not_required` dan tidak menjurnal dua kali.
    4. Galat jurnal → `CashPostingError` (membawa dokumen kas); kas TIDAK dihapus dan bertanda `failed`."""
    from services import gl_service as gl
    from services.cash_entity_service import assert_owned
    # ── 1. PERIKSA ─────────────────────────────────────────────────────────────────────────────────────────────────
    amt = round(float(amount or 0), 2)
    if amt <= EPS:
        raise CashRejected("Nominal kas harus lebih dari 0.", 400)
    if direction not in ("in", "out"):
        raise CashRejected("Arah kas harus masuk atau keluar.", 400)
    if not (ref_type or "").strip() or not (ref_id or "").strip():
        raise CashRejected("Transaksi kas wajib punya dokumen rujukan.", 400)
    try:
        ent = assert_owned(entity_id, what="Transaksi kas")
    except HTTPException as exc:
        raise CashRejected(str(exc.detail), exc.status_code) from exc
    owner = (owner_entity_id or "").strip()
    rek = await periksa_rekening(ent, account_id, cash_type)
    if journal_by_parent and cash_type in CASH_TYPE_LABEL and rek["cash_type"] != cash_type:
        # Jurnal induk sudah memakai akun kas `cash_type`; rekening jenis lain membuat buku kas ≠ buku besar.
        raise CashRejected(f"Rekening {rek['account'].get('name', '')} bukan rekening "
                           f"{CASH_TYPE_LABEL[cash_type]} {await _nama_pt(ent)}.")
    try:
        await gl.preflight_posting(owner or ent, txn_date or now_iso())
    except gl.ClosedPeriodError as exc:
        raise CashRejected(str(exc)) from exc
    # ── 2. NIAT + EFEK ─────────────────────────────────────────────────────────────────────────────────────────────
    base = cash_id(ref_type, ref_id, direction, seq)
    cid, existing = await _cari_kas(base, txn_id=txn_id, ref_type=ref_type, ref_id=ref_id, direction=direction,
                                    seq=seq)
    if existing is None:
        now = now_iso()
        tambahan = {k: v for k, v in (extra or {}).items() if k not in _PROTECTED}
        doc: Dict[str, Any] = {
            "id": cid, "number": "", "cash_type": rek["cash_type"], "direction": direction, "amount": amt,
            "category": category or "", "description": description or "", "entity_id": ent,
            "ref_type": ref_type, "ref_id": ref_id, "seq": seq or "",
            "account_id": rek["account_id"], "account_code": rek["account_code"],
            "txn_date": txn_date or now, "reconciled": False, "status": "posted",
            "gl_status": "pending", "gl_error": "", "journal_entry_id": "",
            "created_by": actor or "system", "created_at": now, "updated_at": now,
        }
        if contra_account_code:
            doc["contra_account_code"] = contra_account_code
        if owner:
            doc["owner_entity_id"] = owner
        if counterparty_entity_id:
            doc["counterparty_entity_id"] = counterparty_entity_id
        if journal_by_parent:
            doc["gl_posted"] = True   # dijurnal dokumen induknya (CN/nota debit/pinjaman antar-PT)
            doc["parent_journal"] = journal_by_parent
        doc.update(tambahan)
        if not doc.get("number"):
            doc["number"] = await next_cash_number(ent)
        try:
            await db.cash_transactions.update_one({"id": cid}, {"$setOnInsert": doc}, upsert=True)
        except Exception as exc:  # noqa: BLE001 — balapan upsert di indeks unik `uq_id`: yang kalah membaca pemenang
            if "E11000" not in str(exc) and "duplicate key" not in str(exc).lower():
                raise
        existing = await db.cash_transactions.find_one({"id": cid}, {"_id": 0})
        if existing is None:   # tidak mungkin kecuali dihapus di antara dua langkah
            raise CashRejected("Transaksi kas gagal tercatat. Muat ulang lalu ulangi.")
    txn = existing
    if txn.get("status") == "void":
        raise CashRejected(f"Transaksi kas {txn.get('number', '')} untuk {_ref_label(ref_type)} ini sudah "
                           "dibatalkan. Muat ulang lalu periksa.")
    if round(float(txn.get("amount") or 0), 2) != amt or txn.get("direction") != direction:
        raise CashRejected(f"Transaksi kas untuk {_ref_label(ref_type)} ini sudah tercatat dengan nominal "
                           f"{rupiah(txn.get('amount'))}. Muat ulang lalu periksa.")
    # ── 3. JURNAL (tahan-gagal) ────────────────────────────────────────────────────────────────────────────────────
    try:
        await gl.post_cash_durable(txn)
    except Exception as exc:  # noqa: BLE001 — penanda `failed` sudah ditulis `post_durable`
        fresh = await db.cash_transactions.find_one({"id": cid}, {"_id": 0}) or txn
        raise CashPostingError(fresh, str(exc)[:300] or exc.__class__.__name__) from exc
    parent = txn.get("parent_journal") or ""
    if parent and await db.journal_entries.find_one({"id": parent}, {"_id": 0, "id": 1}):
        # `post_durable` menulis `journal_entry_id=""` untuk kas `not_required`; tautan ke jurnal induk dipulihkan.
        await db.cash_transactions.update_one({"id": cid}, {"$set": {"journal_entry_id": parent}})
    return await db.cash_transactions.find_one({"id": cid}, {"_id": 0}) or txn


async def ensure_posted(txn_id: str) -> Optional[Dict[str, Any]]:
    """Pastikan jurnal kas asal ada (jalur batal & ulang posting; idempoten). → jurnal kas (baru atau yang sudah ada),
    atau None (kas tidak ada / void / dijurnal dokumen induk / nominal nol). Gagal → `CashPostingError`."""
    from services import gl_service as gl
    txn = await db.cash_transactions.find_one({"id": txn_id or "__none__"}, {"_id": 0})
    if not txn:
        return None
    try:
        je = await gl.post_cash_durable(txn)
    except Exception as exc:  # noqa: BLE001
        fresh = await db.cash_transactions.find_one({"id": txn_id}, {"_id": 0}) or txn
        raise CashPostingError(fresh, str(exc)[:300] or exc.__class__.__name__) from exc
    return je or await db.journal_entries.find_one(
        {"source_type": "cash_transaction", "source_id": txn_id, "status": {"$ne": "void"}}, {"_id": 0})


async def record_return_cash(*, direction: str, amount: float, account_code: str,
                             category: str, description: str, entity_id: str,
                             ref_type: str, ref_id: str, journal_entry_id: str = "",
                             created_by: str = "system", txn_date: str = "",
                             account_id: str = "", cash_type: str = "") -> Optional[Dict[str, Any]]:
    """R5.3 — 1 mutasi kas untuk refund retur (in = pemasok kembalikan dana; out = refund ke pelanggan), yang JURNALNYA
    milik dokumen induk (nota kredit / nota debit, `account_code` = akun kas jurnal itu).

    PK-20 — pembungkus `create_cash(..., journal_by_parent=…)`: rekening = `account_id` (rekening dokumen) atau rekening
    tunggal PT untuk jenis kas akun jurnal; `account_id` tidak pernah lagi berisi kode akun. Idempoten per rujukan
    (id tetap `ref_type|ref_id|direction`; kas lama ber-id acak untuk rujukan sama dipakai ulang). Kas & Bank 1 (R2) —
    `cash_type` = jenis kas akun jurnal dari `akun_refund` (sub-akun rekening → jenis rekening); kosong = dibaca dari
    kode templat `account_code` (`cash_type_for`, pemanggil lama)."""
    amount = round(float(amount or 0), 2)
    if amount <= 0.01 or not ref_id:
        return None
    # FASE E-7 (E7.4) — kas grup DIHAPUS: refund retur tetap uang badan usaha dokumennya.
    from services.cash_entity_service import resolve_owner
    txn_entity = resolve_owner(entity_id, what="Kas refund retur")
    return await create_cash(
        entity_id=txn_entity, direction=direction, amount=amount, ref_type=ref_type, ref_id=ref_id,
        account_id=account_id, cash_type=cash_type or cash_type_for(account_code), txn_date=txn_date, category=category,
        description=description, actor=created_by,
        # id jurnal induk bila sudah ada; bila jurnalnya terbit kemudian (penyelesaian per roll), rujukan dokumennya
        journal_by_parent=journal_entry_id or f"{ref_type}:{ref_id}",
        extra={"source_entity_id": entity_id or ""})
