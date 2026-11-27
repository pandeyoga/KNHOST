"""EPIC7-C — General Ledger & Chart of Accounts (akuntansi inti).

Dua koleksi kanonik baru:
- `gl_accounts`    (prefix `gla_`) — Bagan Akun / Chart of Accounts (master).
- `journal_entries` (prefix `je_`) — Jurnal umum (double-entry, balanced).

PRINSIP:
- Setiap jurnal WAJIB seimbang: Σdebit == Σkredit (di-enforce saat create).
- Auto-posting DITURUNKAN dari SSOT yang sudah ada (idempotent by
  source_type+source_id) agar tidak double-count:
    * `sales_orders`     → pengakuan pendapatan (Dr Piutang/Kas, Cr Pendapatan + PPN Keluaran)
    * `cash_transactions`→ mutasi kas (Dr/Cr Kas/Bank vs lawan akun by ref_type)
- Trial Balance & Buku Besar diturunkan dari journal_entries (status != void).

Normal balance: asset & expense = debit; liability, equity, income = credit.
"""
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from pymongo.errors import DuplicateKeyError

from db import db
from core_utils import (new_id, now_iso, next_doc_number, safe_doc, rupiah,
                        to_cents, from_cents, DEFAULT_ENTITY_ID)
from services import costing_service
from services.customer_service import (
    _order_grand_total as order_grand_total,
    order_payment_method,
    NON_AR_METHODS,
    DEAD_STATUSES,
)
from request_context import active_entity_or
logger = logging.getLogger(__name__)


EPS = 0.01

# ─── Tipe akun & normal balance ──────────────────────────────────────────────
ACCOUNT_TYPES = ["asset", "liability", "equity", "income", "expense"]
TYPE_LABELS = {
    "asset": "Aset",
    "liability": "Kewajiban",
    "equity": "Ekuitas",
    "income": "Pendapatan",
    "expense": "Beban",
}
DEBIT_TYPES = {"asset", "expense"}  # sisanya credit


def normal_balance(acc_type: str) -> str:
    return "debit" if acc_type in DEBIT_TYPES else "credit"


# ─── Default Chart of Accounts (Indonesia, ringkas namun lengkap) ────────────
# (code, name, type, parent_code, is_postable)
DEFAULT_COA: List = [
    # ASET
    ("1-0000", "ASET", "asset", "", False),
    ("1-1000", "Aset Lancar", "asset", "1-0000", False),
    ("1-1100", "Kas Besar / Bank", "asset", "1-1000", True),
    ("1-1110", "Kas Kecil", "asset", "1-1000", True),
    ("1-1150", "Kas & Bank Transit (Dana Dalam Perjalanan)", "asset", "1-1000", True),  # FASE G-9 — pindah-buku antar rekening sendiri
    ("1-1200", "Piutang Usaha", "asset", "1-1000", True),
    ("1-1250", "Piutang Antar-Perusahaan (IC-AR)", "asset", "1-1000", True),
    ("1-1260", "Piutang Klaim Mitra (Makloon)", "asset", "1-1000", True),  # Fase D — D-09 (ganti rugi mitra)
    ("1-1270", "Piutang Denda Pelanggan", "asset", "1-1000", True),  # FASE G-2 — denda keterlambatan
    ("1-1280", "Piutang Titipan Karyawan", "asset", "1-1000", True),  # FASE G-9 — uang perusahaan yang dipegang karyawan
    ("1-1300", "Persediaan Barang", "asset", "1-1000", True),
    # FASE G-6 — barang antar-PT yang SUDAH dibeli (dokumen & utang lahir) tetapi
    # BELUM diterima gudang pembeli. Tanpa akun ini, persediaan pembeli membengkak
    # sebelum barangnya ada (GL 1-1300 selalu drift dari subledger roll).
    ("1-1310", "Persediaan Dalam Perjalanan (Antar-PT)", "asset", "1-1000", True),
    ("1-1350", "Persediaan Dalam Proses (Makloon/WIP)", "asset", "1-1000", True),
    ("1-1400", "Uang Muka & Biaya Dibayar Dimuka", "asset", "1-1000", True),
    ("1-1500", "PPN Masukan", "asset", "1-1000", True),
    ("1-1900", "Aset Lancar Lainnya", "asset", "1-1000", True),
    ("1-9999", "Akun Sementara (Suspense)", "asset", "1-1000", True),
    ("1-2000", "Aset Tetap", "asset", "1-0000", False),
    ("1-2100", "Peralatan & Mesin", "asset", "1-2000", True),
    ("1-2200", "Kendaraan", "asset", "1-2000", True),               # R6.2 — Fixed Assets
    ("1-2300", "Inventaris & Perabot Kantor", "asset", "1-2000", True),  # R6.2
    ("1-2400", "Bangunan", "asset", "1-2000", True),                # R6.2
    ("1-2900", "Akumulasi Penyusutan Aset Tetap", "asset", "1-2000", True),  # R6.2 — contra-asset (saldo kredit)
    # KEWAJIBAN
    ("2-0000", "KEWAJIBAN", "liability", "", False),
    ("2-1000", "Kewajiban Lancar", "liability", "2-0000", False),
    ("2-1100", "Hutang Usaha", "liability", "2-1000", True),
    ("2-1150", "Hutang Belum Ditagih (GR/IR)", "liability", "2-1000", True),
    ("2-1250", "Utang Antar-Perusahaan (IC-AP)", "liability", "2-1000", True),
    ("2-1200", "PPN Keluaran", "liability", "2-1000", True),
    ("2-1300", "Hutang Pajak Lainnya", "liability", "2-1000", True),
    ("2-1400", "Uang Muka Pelanggan", "liability", "2-1000", True),
    ("2-1450", "Saldo Kredit Pelanggan (Store Credit)", "liability", "2-1000", True),  # R5.2 — store-credit ledger
    ("2-1500", "Hutang Insentif Penjualan", "liability", "2-1000", True),
    ("2-1600", "Hutang Gaji", "liability", "2-1000", True),
    ("2-1650", "Hutang Reimburse Karyawan", "liability", "2-1000", True),  # CX-05 — LPJ > uang muka
    ("2-1700", "Hutang BPJS", "liability", "2-1000", True),
    ("2-1800", "Hutang PPh 21", "liability", "2-1000", True),
    ("2-1900", "Kewajiban Lancar Lainnya", "liability", "2-1000", True),
    # FASE G-8 — dana masuk yang belum ketahuan pemiliknya diakui sebagai KEWAJIBAN
    # (titipan), bukan dibiarkan menggantung tanpa jurnal.
    ("2-1950", "Titipan Dana Belum Teridentifikasi", "liability", "2-1000", True),
    # EKUITAS
    ("3-0000", "EKUITAS", "equity", "", False),
    ("3-1000", "Modal Disetor", "equity", "3-0000", True),
    ("3-2000", "Laba Ditahan", "equity", "3-0000", True),
    ("3-2900", "Ekuitas Saldo Awal", "equity", "3-0000", True),
    ("3-3000", "Laba Tahun Berjalan", "equity", "3-0000", True),
    # PENDAPATAN
    ("4-0000", "PENDAPATAN", "income", "", False),
    ("4-1000", "Pendapatan Penjualan", "income", "4-0000", True),
    ("4-9000", "Pendapatan Lain-lain", "income", "4-0000", True),
    ("4-9100", "Laba Pelepasan Aset Tetap", "income", "4-0000", True),  # R6.2 — gain on disposal
    ("4-9200", "Pendapatan Klaim Makloon", "income", "4-0000", True),   # Fase D — D-09 (potong bon / ganti rugi)
    ("4-9300", "Pendapatan Denda Keterlambatan", "income", "4-0000", True),  # FASE G-2
    # BEBAN (termasuk HPP)
    ("5-0000", "BEBAN POKOK", "expense", "", False),
    ("5-1000", "Harga Pokok Penjualan", "expense", "5-0000", True),
    ("5-1100", "Overhead Produksi Diserap", "expense", "5-0000", True),  # R6.4 — applied mfg overhead (kredit → kapitalisasi ke persediaan)
    # FASE T — jasa makloon yang TIDAK bisa menempel ke kain mana pun. Terjadi bila
    # SPK berisi langkah "jasa murni" (mis. pembuatan kasa/screen) tetapi tidak ada
    # langkah kain sesudahnya yang bisa menyerap biayanya. Tanpa akun ini, nilainya
    # menggantung di WIP 1-1350 selamanya (drift yang tak pernah bisa dijelaskan).
    ("5-1200", "Beban Jasa Makloon Tak Terserap", "expense", "5-0000", True),
    ("5-9000", "Beban Angkut Pembelian", "expense", "5-0000", True),
    ("5-9500", "Beban Kerugian/Penghapusan Persediaan", "expense", "5-0000", True),  # R5.1 — write-off scrap/goods
    ("6-0000", "BEBAN OPERASIONAL", "expense", "", False),
    ("6-1000", "Beban Gaji", "expense", "6-0000", True),
    ("6-1100", "Beban BPJS (Perusahaan)", "expense", "6-0000", True),
    ("6-2000", "Beban Sewa", "expense", "6-0000", True),
    ("6-3000", "Beban Utilitas", "expense", "6-0000", True),
    ("6-4000", "Beban Operasional Lainnya", "expense", "6-0000", True),
    # Sub-akun beban petty cash (Digitalisasi Formulir Sukacita) — mapping configurable
    ("6-4100", "Beban ATK & Perlengkapan Kantor", "expense", "6-0000", True),
    ("6-4200", "Beban Konsumsi & Entertainment", "expense", "6-0000", True),
    ("6-4300", "Beban Cetak, Fotokopi & Materai", "expense", "6-0000", True),
    ("6-4400", "Beban Utilitas Kantor", "expense", "6-0000", True),
    ("6-4500", "Beban Kirim Dokumen & Ekspedisi", "expense", "6-0000", True),
    ("6-4600", "Beban Transportasi & BBM", "expense", "6-0000", True),
    ("6-4700", "Beban Pemasaran & Promosi", "expense", "6-0000", True),  # COMM-04 — realisasi biaya kampanye
    ("6-4900", "Beban Petty Cash Lainnya", "expense", "6-0000", True),
    ("6-5000", "Beban Insentif Penjualan", "expense", "6-0000", True),
    ("6-6000", "Beban Penyusutan Aset Tetap", "expense", "6-0000", True),  # R6.2 — depreciation expense
    ("6-7000", "Beban Sample & Pengembangan (R&D)", "expense", "6-0000", True),  # FASE F — bahan yang dipakai membuat sample
    ("6-8000", "Beban Administrasi Bank", "expense", "6-0000", True),  # FASE G-8 — biaya adm/transfer yang dipotong bank
    ("6-9000", "Beban Lain-lain", "expense", "6-0000", True),
    ("6-9100", "Beban Selisih Pembayaran Pelanggan", "expense", "6-0000", True),  # FASE G-3 — kurang bayar dihapus/pembulatan
    ("6-9500", "Rugi Pelepasan Aset Tetap", "expense", "6-0000", True),  # R6.2 — loss on disposal
]

# Akun kunci untuk auto-posting
ACC_KAS_BESAR = "1-1100"
ACC_KAS_KECIL = "1-1110"
ACC_PIUTANG = "1-1200"
ACC_UANG_MUKA_PELANGGAN = "2-1400"  # KN-076-AR-GL-DRIFT — Uang Muka Pelanggan (deposit/kelebihan bayar)
ACC_IC_AR = "1-1250"           # M-3 — Piutang Antar-Perusahaan (inter-company)
ACC_PIUTANG_KLAIM = "1-1260"   # Fase D (D-09) — Piutang Klaim Mitra Makloon (ganti rugi)
ACC_PIUTANG_DENDA = "1-1270"   # FASE G-2 — Piutang Denda Pelanggan (keterlambatan)
ACC_KAS_TRANSIT = "1-1150"     # FASE G-9 — Kas/Bank Transit (pindah-buku antar rekening sendiri)
ACC_PIUTANG_KARYAWAN = "1-1280"  # FASE G-9 — Piutang Titipan Karyawan (uang KN dipegang karyawan)
ACC_PERSEDIAAN = "1-1300"     # F3 — Persediaan Barang (Inventory)
ACC_PERSEDIAAN_TRANSIT = "1-1310"  # FASE G-6 — Persediaan Dalam Perjalanan (antar-PT)
ACC_WIP_SUBCON = "1-1350"     # M2 — Persediaan Dalam Proses (Makloon/WIP-at-vendor)
ACC_HUTANG = "2-1100"
ACC_GRIR = "2-1150"            # Gelombang 1 F-3/F-5 — GR/IR (barang diterima belum ditagih)
ACC_IC_AP = "2-1250"           # M-3 — Utang Antar-Perusahaan (inter-company)
ACC_UANG_MUKA = "1-1400"       # Uang Muka & Biaya Dibayar Dimuka (cash advance / petty cash)
ACC_HUTANG_REIMBURSE = "2-1650"  # CX-05 — kelebihan pengeluaran LPJ di atas uang muka
ACC_PPN_IN = "1-1500"          # Gelombang 1 F-5 — PPN Masukan
ACC_EKUITAS_AWAL = "3-2900"    # Gelombang 1 F-3 — saldo awal persediaan
ACC_PPN_OUT = "2-1200"
ACC_PENDAPATAN = "4-1000"
ACC_PENDAPATAN_LAIN = "4-9000"
ACC_HPP = "5-1000"            # F3 — Harga Pokok Penjualan (COGS)
ACC_OVERHEAD_APPLIED = "5-1100"  # R6.4 — Overhead Produksi Diserap (contra-expense; kredit saat kapitalisasi ke persediaan)
ACC_JASA_TAK_TERSERAP = "5-1200"  # FASE T — jasa makloon "jasa murni" yang tak menempel ke kain
ACC_LANDED = "5-9000"
ACC_WRITEOFF = "5-9500"       # R5.1 — Beban Kerugian/Penghapusan Persediaan (scrap/goods write-off)
ACC_STORE_CREDIT = "2-1450"   # R5.2 — Saldo Kredit Pelanggan (store credit liability)
ACC_TITIPAN_DANA = "2-1950"   # FASE G-8 — Titipan Dana Belum Teridentifikasi (rekonsiliasi bank)
ACC_BEBAN_OPS = "6-4000"
ACC_BEBAN_PEMASARAN = "6-4700"  # COMM-04 — Beban Pemasaran (realisasi biaya kampanye)
ACC_BEBAN_INSENTIF = "6-5000"   # F0-E — Beban Insentif Penjualan
ACC_HUTANG_INSENTIF = "2-1500"  # F0-E — Hutang Insentif Penjualan (akrual)
ACC_BEBAN_GAJI = "6-1000"       # H4 — Beban Gaji & Upah
ACC_BEBAN_BPJS = "6-1100"       # H4 — Beban BPJS (kontribusi perusahaan)
ACC_HUTANG_GAJI = "2-1600"      # H4 — Hutang Gaji (take-home belum dibayar)
ACC_HUTANG_BPJS = "2-1700"      # H4 — Hutang BPJS (employee + employer)
ACC_HUTANG_PPH21 = "2-1800"     # H4 — Hutang PPh 21
ACC_SUSPENSE = "1-9999"
# R6.2 — Fixed Assets & Depresiasi
ACC_FA_ACCUM_DEP = "1-2900"     # Akumulasi Penyusutan Aset Tetap (contra-asset)
ACC_DEP_EXPENSE = "6-6000"      # Beban Penyusutan Aset Tetap
ACC_FA_GAIN = "4-9100"          # Laba Pelepasan Aset Tetap (gain on disposal)
ACC_KLAIM_MAKLOON = "4-9200"    # Fase D (D-09) — Pendapatan Klaim Makloon (potong bon / ganti rugi)
ACC_PENDAPATAN_DENDA = "4-9300"  # FASE G-2 — Pendapatan Denda Keterlambatan
ACC_SELISIH_BAYAR = "6-9100"     # FASE G-3 — Beban Selisih Pembayaran (kurang bayar dihapus)
ACC_BEBAN_RND = "6-7000"         # FASE F — Beban Sample & Pengembangan (bahan sample keluar gudang)
ACC_BEBAN_BANK = "6-8000"        # FASE G-8 — Beban Administrasi Bank (biaya adm/transfer dipotong bank)
ACC_FA_LOSS = "6-9500"          # Rugi Pelepasan Aset Tetap (loss on disposal)

# keyword kategori → akun (manual cash entries) untuk semantik akuntansi lebih tepat
CASH_OUT_KEYWORDS = [
    ("gaji", "6-1000"), ("payroll", "6-1000"),
    ("sewa", "6-2000"), ("rent", "6-2000"),
    ("listrik", "6-3000"), ("air", "6-3000"), ("utilitas", "6-3000"),
    ("internet", "6-3000"), ("telepon", "6-3000"),
    ("pembelian", "1-1300"), ("beli", "1-1300"), ("bahan", "1-1300"),
    ("operasional", "6-4000"),
    # Latihan Keuangan 17 Nov — kategori "Transfer / Top-up" = pindah dana antar kas/rekening SENDIRI: lewat 1-1150 Kas
    # Transit (sama dengan pindah-buku G-9). Dulu jatuh ke beban (keluar) dan Suspense (masuk) → beban palsu.
    ("transfer", ACC_KAS_TRANSIT),
]
CASH_IN_KEYWORDS = [
    ("transfer", ACC_KAS_TRANSIT),   # pasangan baris keluar di atas (masuk dari kas/rekening sendiri)
    ("modal", "3-1000"), ("capital", "3-1000"), ("investasi", "3-1000"), ("setoran modal", "3-1000"),
    ("bunga", "4-9000"), ("jasa giro", "4-9000"),
    ("penjualan tunai", "4-1000"),
    # FASE G-8 — dana masuk tak dikenal: Dr Bank / Cr 2-1950 Titipan (KEWAJIBAN), bukan
    # pendapatan dan bukan suspense. Kategori ini ditulis `bank_recon_service.to_holding`.
    ("titipan", "2-1950"),
]


async def account_for(key: str, entity_id: Optional[str] = None) -> str:
    """GL-01 — akun efektif sebuah kebutuhan (PT → global → bawaan registri)."""
    from services import gl_mapping_service as _glm
    return await _glm.account_for(key, entity_id)


async def _known(key: str) -> List[str]:
    from services import gl_mapping_service as _glm
    return await _glm.known_codes(key)


async def akun_rekening(entity_id: str, account_id: str) -> str:
    """Kode akun buku besar rekening `account_id` bila PT `entity_id` sudah memakai akun per rekening
    (`cash_account_mode.aktif`) DAN rekening itu milik PT itu ber-`gl_account_code`; selain itu "" (rekening PT lain,
    rekening tanpa sub-akun, PT belum aktif → jurnal memakai akun lama)."""
    if account_id and entity_id:
        from services import cash_account_mode as _mode
        if await _mode.aktif(entity_id):
            acc = await db.bank_accounts.find_one({"id": account_id},
                                                  {"_id": 0, "entity_id": 1, "gl_account_code": 1}) or {}
            kode = acc.get("gl_account_code") or ""
            if kode and (acc.get("entity_id") or "") == entity_id:
                return kode
    return ""


async def akun_kas(entity_id: str, account_id: str, cash_type: str, *, akun_lama: str = "") -> str:
    """Kas & Bank bagian 1 (D1) — SATU pembantu akun kas untuk jurnal yang menyentuh kas.

    PT `entity_id` sudah memakai akun per rekening DAN rekening `account_id` milik PT itu ber-`gl_account_code` → kode
    akun rekening itu (`akun_rekening`; akun khusus PT, bukan kode bawaan, jadi `remap_lines` tidak memetakannya ulang).
    Selain itu → akun lama: `akun_lama` bila pemanggil sudah memegang akun kas pilihan (mis. kode pemilih refund retur,
    akun sumber dana aset yang tersimpan), kalau kosong akun jenis kas: 1-1110 kas kecil, 1-1100 kas besar/bank —
    dipetakan per PT di `_insert_entry` seperti sebelumnya, sehingga PT yang belum aktif menghasilkan jurnal yang persis
    sama. Penjaga statik `scripts/guardrails/verify_akun_kas_satu_pintu.py` (INV-CASH-02) menolak kode kas harfiah di
    baris jurnal di luar fungsi ini."""
    kode = await akun_rekening(entity_id, account_id)
    if kode:
        return kode
    return akun_lama or (ACC_KAS_KECIL if cash_type == "kas_kecil" else ACC_KAS_BESAR)


async def akun_kas_tanpa_dokumen(entity_id: str, cash_type: str) -> Dict[str, Any]:
    """Kas & Bank 1 — akun kas jurnal yang menyentuh kas TANPA dokumen kas / rekening (penjualan tunai tanpa surat
    jalan, hasil pelepasan aset): selalu akun lama (`akun_kas` tanpa rekening, dipetakan per PT seperti dulu).
    Ketetapan pengendali R6: TIDAK ke sub-akun rekening tunggal — tanpa dokumen kas, saldo sub-akun ≠ buku kas
    rekening (anti-tujuan §2 mengalahkan klausul rekening tunggal §5.1). → `{"account_code", "belum_tertaut"}`;
    `belum_tertaut` = PT sudah memakai akun per rekening (jurnal ditandai `ref.kas_belum_tertaut`)."""
    from services import cash_account_mode as _mode
    return {"account_code": await akun_kas(entity_id, "", cash_type),
            "belum_tertaut": bool(entity_id) and await _mode.aktif(entity_id)}


async def menyentuh_kas_lama(entity_id: str, codes: List[str]) -> bool:
    """Kas & Bank 1 (ketetapan R7) — PT `entity_id` sudah memakai akun per rekening DAN salah satu `codes` adalah akun
    kas LAMA PT itu (`report_basis.kode_kas` tanpa akun rekening: bawaan + pemetaan + riwayat) → jurnal tanpa dokumen
    kas ini ditandai `ref.kas_belum_tertaut` (mis. ongkir retur dibayar dari akun kas lama)."""
    from services import cash_account_mode as _mode
    if not entity_id or not await _mode.aktif(entity_id):
        return False
    from services import report_basis as _rb
    lama = await _rb.kode_kas(entity_id) - await kode_akun_rekening(entity_id)
    return any(c in lama for c in codes)


async def _cash_account(txn: Dict[str, Any], entity_id: str = "") -> str:
    """Akun kas dokumen kas `txn` = `akun_kas(PT buku jurnal, rekening, jenis kas)`. `entity_id` = PT buku jurnal
    (kosong → pemilik `owner_entity_id`, lalu PT dokumen kas). Rekening milik PT lain dari buku jurnalnya → akun lama."""
    ent = entity_id or txn.get("owner_entity_id") or txn.get("entity_id") or ""
    return await akun_kas(ent, txn.get("account_id") or "", txn.get("cash_type") or "")


# ═════════════════════════════════════════════════════════════════════════════
#  CHART OF ACCOUNTS (master)
# ═════════════════════════════════════════════════════════════════════════════

async def seed_default_coa() -> int:
    """Pastikan bagan akun baku tersedia (idempotent — hanya tambah yg belum ada).

    Akun template (`entity_id=None`) berlaku sebagai default lintas-PT. Setiap
    PT boleh membuat akun tambahan atau override nama/status via field `entity_id`
    (lihat M-3 CoA per-PT). Posting JE tetap resolve by-code global.
    """
    existing = {a["code"] for a in await db.gl_accounts.find(
        {"entity_id": {"$in": [None, ""]}}, {"_id": 0, "code": 1}).to_list(2000)}
    to_add = []
    for code, name, atype, parent, postable in DEFAULT_COA:
        if code in existing:
            continue
        to_add.append({
            "id": new_id("gla"),
            "code": code,
            "name": name,
            "type": atype,
            "normal_balance": normal_balance(atype),
            "parent_code": parent,
            "is_postable": bool(postable),
            "is_active": True,
            "system": True,           # akun baku — tak boleh dihapus
            "currency": "IDR",
            "description": "",
            "entity_id": None,        # M-3 — None = template global (SHARED)
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    if to_add:
        await db.gl_accounts.insert_many(to_add)
    return len(to_add)


async def list_accounts(active_only: bool = False,
                        entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Daftar akun.
    - Tanpa `entity_id` → HANYA template global (entity_id=None).
    - Dengan `entity_id` → effective view: override PT (kalau ada) menang atas
      template global per `code`; akun khusus PT (code hanya ada di override) juga
      ikut muncul. Tidak menyentuh akun PT lain.
    """
    q: Dict[str, Any] = {}
    if active_only:
        q["is_active"] = True
    if entity_id:
        # Ambil template global + override untuk entity ini; dedupe by-code, override wins.
        q_or = [{"entity_id": {"$in": [None, ""]}}, {"entity_id": entity_id}]
        rows = await db.gl_accounts.find({**q, "$or": q_or}, {"_id": 0}).to_list(4000)
        merged: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            code = r.get("code", "")
            if not code:
                continue
            eid = r.get("entity_id")
            if code not in merged:
                merged[code] = r
            else:
                # Override wins bila entity_id cocok dengan yang diminta.
                if eid == entity_id:
                    merged[code] = r
        result = list(merged.values())
    else:
        q["entity_id"] = {"$in": [None, ""]}
        result = await db.gl_accounts.find(q, {"_id": 0}).to_list(2000)
    # FASE E-4 (E4.4) — sebutkan ASAL setiap baris. Tanpa ini layar CoA tidak bisa
    # membedakan "akun ini memang milik badan usaha saya" dari "akun ini warisan
    # template grup", padahal keduanya tampil identik dan konsekuensinya beda:
    # menonaktifkan yang pertama hanya kena satu badan usaha, yang kedua kena semua.
    # PK-36 (IC-06) — tanda akun kontrol & boleh-tidaknya jurnal manual, dari pengaturan dan pemetaan PT ini (tanpa PT =
    # lapisan global). Layar memakai `manual_allowed` untuk pilihan akun jurnal manual / reklas suspense.
    from services.config_resolver import value_of
    from services import gl_mapping_registry as _reg, gl_mapping_service as _glm
    kontrol = await _glm.control_accounts(entity_id)
    tolak = await value_of("gl.jurnal_manual_akun_kontrol", {"entity_id": entity_id or ""}) != "izinkan"
    for row in result:
        own = entity_id and row.get("entity_id") == entity_id
        row["entity_scope"] = "entity" if own else "global"
        row["source_label"] = "Badan usaha ini" if own else "Global"
        row["is_entity_override"] = bool(own)
        ledger = kontrol.get(row.get("code", ""), "")
        row["is_control"] = bool(ledger)
        row["control_ledger"] = ledger
        row["control_ledger_label"] = _reg.CONTROL_LEDGERS[ledger]["label"] if ledger else ""
        row["manual_allowed"] = not (ledger and tolak)
    result.sort(key=lambda a: a.get("code", ""))
    return result


async def get_account(code: str,
                      entity_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Ambil 1 akun by-code. Kalau `entity_id` diberikan, override PT diutamakan;
    fallback ke template global."""
    if entity_id:
        override = await db.gl_accounts.find_one(
            {"code": code, "entity_id": entity_id}, {"_id": 0})
        if override:
            return override
    return await db.gl_accounts.find_one(
        {"code": code, "entity_id": {"$in": [None, ""]}}, {"_id": 0})


async def create_account(payload, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Buat akun. `entity_id=None` = akun template global; `entity_id=<id>` =
    akun khusus PT (bisa akun baru atau override akun template dengan `code` sama).
    Duplicate check: unique per `(code, entity_id)`."""
    code = (payload.code or "").strip()
    name = (payload.name or "").strip()
    atype = (payload.type or "").strip()
    if not code or not name:
        raise ValueError("Kode dan nama akun wajib diisi.")
    if atype not in ACCOUNT_TYPES:
        raise ValueError(f"Tipe akun harus salah satu: {', '.join(ACCOUNT_TYPES)}")
    scope_q: Dict[str, Any] = {"code": code}
    if entity_id:
        scope_q["entity_id"] = entity_id
    else:
        scope_q["entity_id"] = {"$in": [None, ""]}
    if await db.gl_accounts.find_one(scope_q, {"_id": 0}):
        scope_note = f" untuk PT {entity_id}" if entity_id else " (template global)"
        raise ValueError(f"Kode akun '{code}' sudah dipakai{scope_note}.")
    if payload.parent_code:
        parent = await db.gl_accounts.find_one(
            {"code": payload.parent_code, "entity_id": {"$in": [None, "", entity_id]}},
            {"_id": 0})
        if not parent:
            raise ValueError("Akun induk tidak ditemukan.")
    doc = {
        "id": new_id("gla"),
        "code": code,
        "name": name,
        "type": atype,
        "normal_balance": normal_balance(atype),
        "parent_code": (payload.parent_code or "").strip(),
        "is_postable": bool(payload.is_postable if payload.is_postable is not None else True),
        "is_active": True,
        "system": False,
        "currency": payload.currency or "IDR",
        "description": (payload.description or "").strip(),
        "entity_id": entity_id or None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.gl_accounts.insert_one(doc)
    return safe_doc(doc)


class AccountInUseError(ValueError):
    """PK-18 (GL-02) — akun yang masih dipakai pemetaan atau masih bersaldo tidak boleh dinonaktifkan (router → 409)."""


async def _tolak_akun_rekening_dipakai(acc: Dict[str, Any], aksi: str) -> None:
    """Kas & Bank 1 — akun buku besar rekening (ber-`bank_account_id`) yang masih ditautkan rekeningnya tidak boleh
    dihapus / dinonaktifkan: jurnal kas rekening itu akan gagal. `AccountInUseError` (router → 409)."""
    rid = (acc or {}).get("bank_account_id") or ""
    if not rid:
        return
    rek = await db.bank_accounts.find_one({"id": rid, "gl_account_code": acc.get("code")}, {"_id": 0, "name": 1})
    if rek:
        raise AccountInUseError(f"Akun {acc.get('code')} adalah akun buku besar rekening {rek.get('name') or rid} "
                                f"dan tidak bisa {aksi}.")


async def assert_can_deactivate(code: str, entity_id: Optional[str] = None) -> None:
    """PK-18 — tolak menonaktifkan akun yang (1) menjadi hasil Pemetaan Akun (`gl_mapping_service.account_for`) untuk
    salah satu kebutuhan `gl_mapping_registry.ENTRIES` pada PT itu — tanpa `entity_id`: bawaan global dan tiap PT yang
    tidak punya baris akun sendiri berkode sama; atau (2) bersaldo: Σ debit − Σ kredit jurnal tidak-void akun itu pada
    PT itu (tanpa `entity_id`: semua PT) ≠ 0 dalam sen. Akun nonaktif membuat setiap jurnal yang memakainya gagal."""
    from services import gl_mapping_registry as _reg, gl_mapping_service as _glm
    if entity_id:   # Kas & Bank 1 — akun buku besar rekening yang masih dipakai rekeningnya
        await _tolak_akun_rekening_dipakai(await db.gl_accounts.find_one(
            {"code": code, "entity_id": entity_id}, {"_id": 0}) or {}, "dinonaktifkan")
    nama = ((await effective_accounts([code], entity_id)).get(code) or {}).get("name", "")
    label = f"{code} {nama}".strip()
    if entity_id:
        pts: List[Optional[str]] = [entity_id]
    else:
        sendiri = {a.get("entity_id") for a in await db.gl_accounts.find(
            {"code": code, "entity_id": {"$nin": [None, ""]}}, {"_id": 0, "entity_id": 1}).to_list(500)}
        pts = [None] + [e["id"] for e in await db.business_entities.find({}, {"_id": 0, "id": 1}).to_list(500)
                        if e.get("id") not in sendiri]
    for eid in pts:
        for entry in _reg.ENTRIES:
            if await _glm.account_for(entry["key"], eid) == code:
                raise AccountInUseError(f"Akun {label} masih dipakai pemetaan akun \"{entry['label']}\". "
                                        f"Ganti pemetaannya dulu di Pemetaan Akun.")
    q: Dict[str, Any] = {"lines.account_code": code, "status": {"$ne": "void"}}
    if entity_id:
        q["entity_id"] = entity_id
    sen = 0
    async for je in db.journal_entries.find(q, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == code:
                sen += _sen(ln.get("debit")) - _sen(ln.get("credit"))
    if sen != 0:
        raise AccountInUseError(f"Akun {label} masih bersaldo {rupiah(abs(sen) / 100)}. "
                                f"Pindahkan saldonya dulu sebelum dinonaktifkan.")


async def update_account(code: str, patch: Dict[str, Any],
                         entity_id: Optional[str] = None, *,
                         tolak_bila_dipakai: bool = False) -> Optional[Dict[str, Any]]:
    """Update akun. Kalau `entity_id` diberikan, target override PT (buat baru
    kalau belum ada — upsert override). Kalau tanpa `entity_id`, update akun
    template global. PK-18 — `tolak_bila_dipakai` (endpoint PATCH): menonaktifkan akun yang masih dipakai pemetaan
    atau bersaldo → `AccountInUseError` sebelum apa pun ditulis (fixture uji memanggil tanpa penanda ini)."""
    if tolak_bila_dipakai and patch.get("is_active") is False:
        cur = await get_account(code, entity_id=entity_id)
        if cur and cur.get("is_active") is not False:
            await assert_can_deactivate(code, entity_id)
    if tolak_bila_dipakai and patch.get("is_postable") is False and entity_id:
        # Kas & Bank 1 (tinjauan T1 M2) — akun rekening yang dijadikan akun induk membuat jurnal kas rekening gagal
        await _tolak_akun_rekening_dipakai(await db.gl_accounts.find_one(
            {"code": code, "entity_id": entity_id}, {"_id": 0}) or {}, "diubah menjadi akun induk")
    scope: Dict[str, Any] = {"code": code}
    if entity_id:
        scope["entity_id"] = entity_id
    else:
        scope["entity_id"] = {"$in": [None, ""]}
    acc = await db.gl_accounts.find_one(scope, {"_id": 0})
    if not acc and entity_id:
        # Belum ada override untuk PT ini → buat baru berbasis template global.
        template = await db.gl_accounts.find_one(
            {"code": code, "entity_id": {"$in": [None, ""]}}, {"_id": 0})
        if not template:
            return None
        override = {**template, "id": new_id("gla"), "entity_id": entity_id,
                    "system": False, "created_at": now_iso(), "updated_at": now_iso()}
        override.pop("_id", None)
        await db.gl_accounts.insert_one(override)
        acc = override
    if not acc:
        return None
    upd: Dict[str, Any] = {}
    for k in ["name", "description", "parent_code"]:
        if patch.get(k) is not None:
            upd[k] = str(patch[k]).strip()
    if patch.get("is_active") is not None:
        upd["is_active"] = bool(patch["is_active"])
    if patch.get("is_postable") is not None and not acc.get("system"):
        upd["is_postable"] = bool(patch["is_postable"])
    upd["updated_at"] = now_iso()
    await db.gl_accounts.update_one({"id": acc["id"]}, {"$set": upd})
    return await db.gl_accounts.find_one({"id": acc["id"]}, {"_id": 0})


async def delete_account(code: str, entity_id: Optional[str] = None) -> None:
    """Hapus akun. Untuk akun template global (entity_id=None) tidak boleh sistem.
    Untuk override PT, hanya menghapus override (template tetap). PK-36 (GL-10): akun khusus PT yang dipakai jurnal
    PT itu, dan akun yang masih dipetakan di Pemetaan Akun, tidak bisa dihapus."""
    scope: Dict[str, Any] = {"code": code}
    if entity_id:
        scope["entity_id"] = entity_id
    else:
        scope["entity_id"] = {"$in": [None, ""]}
    acc = await db.gl_accounts.find_one(scope, {"_id": 0})
    if not acc:
        raise ValueError("Akun tidak ditemukan.")
    if acc.get("system") and not entity_id:
        raise ValueError("Akun baku sistem tidak dapat dihapus (boleh dinonaktifkan).")
    await _tolak_akun_rekening_dipakai(acc, "dihapus")   # Kas & Bank 1
    # PK-36 (GL-10) — baris PT: (1) ada templat berkode sama → hanya penimpa, hapus boleh (laporan kembali ke templat);
    # (2) akun khusus PT → tolak bila dipakai jurnal PT itu; (3) templat maupun akun khusus PT → tolak bila masih
    # dipetakan (Pemetaan Akun). Pemetaan diperiksa dulu: pesannya bisa ditindaklanjuti (ganti pemetaan).
    penimpa = bool(entity_id) and bool(await db.gl_accounts.find_one(
        {"code": code, "entity_id": {"$in": [None, ""]}}, {"_id": 0, "id": 1}))
    if not penimpa:
        from services import gl_mapping_registry as _reg, gl_mapping_service as _glm
        lapisan: Dict[str, Any] = {"entity_id": {"$in": ["", None, entity_id]}} if entity_id else {}
        dipetakan = await db[_glm.COLL].find({"account_code": code, **lapisan}, {"_id": 0, "key": 1}).to_list(100)
        if dipetakan:
            label = ", ".join(sorted({(_reg.BY_KEY.get(m["key"]) or {}).get("label", m["key"]) for m in dipetakan}))
            raise ValueError(f"Akun {code} sedang dipakai di Pemetaan Akun ({label}). Ganti pemetaannya dulu.")
    if entity_id and not penimpa:
        used = await db.journal_entries.count_documents(
            {"entity_id": entity_id, "lines.account_code": code, "status": {"$ne": "void"}})
        if used:
            raise ValueError(f"Akun {code} dipakai pada {used} jurnal PT ini, jadi tidak bisa dihapus. "
                             f"Nonaktifkan saja bila tidak dipakai lagi.")
    # Cegah hapus bila dipakai jurnal (template global; override PT boleh dilepas karena kode templat tetap ada).
    if not entity_id:
        used = await db.journal_entries.count_documents(
            {"lines.account_code": code, "status": {"$ne": "void"}}
        )
        if used:
            raise ValueError(f"Akun dipakai pada {used} jurnal — tidak dapat dihapus.")
        child = await db.gl_accounts.count_documents(
            {"parent_code": code, "entity_id": {"$in": [None, ""]}})
        if child:
            raise ValueError("Akun memiliki sub-akun — hapus/abaikan sub-akun dahulu.")
    await db.gl_accounts.delete_one({"id": acc["id"]})


# ═════════════════════════════════════════════════════════════════════════════
#  JOURNAL ENTRIES (general ledger)
# ═════════════════════════════════════════════════════════════════════════════

def _norm_lines(raw_lines: List[Dict[str, Any]], names: Dict[str, str]) -> List[Dict[str, Any]]:
    out = []
    for ln in raw_lines:
        code = str(ln.get("account_code", "")).strip()
        debit = round(float(ln.get("debit", 0) or 0), 2)
        credit = round(float(ln.get("credit", 0) or 0), 2)
        norm = {
            "account_code": code,
            "account_name": names.get(code, ln.get("account_name", "")),
            "debit": debit,
            "credit": credit,
            "description": str(ln.get("description", "") or "").strip(),
        }
        # Digitalisasi Sukacita — bawa metadata voucher opsional bila ada
        for extra in ("job", "memo", "tax_code", "mapping_key"):
            if ln.get(extra) not in (None, ""):
                norm[extra] = ln.get(extra)
        out.append(norm)
    return out


async def _account_names(codes: List[str], entity_id: Optional[str] = None) -> Dict[str, str]:
    """Nama akun by-code — dari template global (posting-agnostik terhadap PT).

    Kas & Bank 1 — akun rekening (akun khusus PT ber-`bank_account_id`) tidak punya template global: namanya diambil
    dari bagan akun PT itu, PT sudah memakai akun per rekening atau belum (jurnal pindah saldo Tugas 3 bisa terbit
    sebelum PT menyala; tinjauan T1 M4). Akun khusus PT lainnya tetap tanpa nama di baris (seperti sebelumnya)."""
    rows = await db.gl_accounts.find(
        {"code": {"$in": list(set(codes))}, "entity_id": {"$in": [None, ""]}},
        {"_id": 0, "code": 1, "name": 1}).to_list(2000)
    names = {r["code"]: r["name"] for r in rows}
    hilang = sorted({c for c in codes if c and c not in names})
    if hilang and entity_id:
        async for a in db.gl_accounts.find({"code": {"$in": hilang}, "entity_id": entity_id,
                                            "bank_account_id": {"$nin": [None, ""]}},
                                           {"_id": 0, "code": 1, "name": 1}):
            names[a["code"]] = a.get("name", "")
    return names


# ─── FASE G-5 — Hard-lock periode tertutup (unlock berotoritas) ──────────────
class ClosedPeriodError(ValueError):
    """Posting ke periode tertutup tanpa jendela unlock aktif — pesan siap tampil (ID)."""


async def enforce_closed_period_guard(entity_id: str, date: str, *,
                                      source_type: str = "",
                                      can_backdate: bool = True) -> Optional[Dict[str, Any]]:
    """FASE G-5 — jaga agar tak ada jurnal MUNDUR menyusup ke periode `closed`.

    - `source_type == "closing"` → dilewati (jurnal penutup MEMANG di dalam periode).
    - Tanggal di luar periode tertutup → return None (posting normal, tanpa tanda).
    - Periode tertutup + ADA jendela unlock aktif → return dokumen `plu` (caller
      WAJIB menandai `backdated_in_unlock` dan mendaftarkan JE-nya).
    - Periode tertutup TANPA jendela unlock aktif → raise ClosedPeriodError.
    - Periode dibuka tapi `can_backdate=False` (tak punya izin) → raise ClosedPeriodError.
    """
    if source_type == "closing":
        return None
    if not date or not entity_id:
        return None
    from services.book_date import tanggal_buku   # PK-37 (GL-05) — tanggal buku WIB, bukan potong 10 huruf stempel UTC
    d = tanggal_buku(date)
    from services import closing_service as _cs
    st = await _cs.status_for_date(d, entity_id)
    if not st.get("closed"):
        return None
    label = st.get("period_label", st.get("period_key", d))
    from services import period_unlock_service as _pus
    plu = await _pus.find_active_unlock(entity_id, d)
    if not plu:
        raise ClosedPeriodError(
            f"Periode {label} sudah DITUTUP (terkunci). Jurnal mundur ke tanggal {d} "
            f"memerlukan izin 'Buka Periode' yang disetujui dua orang. "
            f"Ajukan di Keuangan → Buka Periode (Unlock).")
    if not can_backdate:
        raise ClosedPeriodError(
            f"Periode {label} sedang dibuka, tetapi Anda tidak memiliki izin "
            f"'period.backdate' untuk memposting jurnal mundur.")
    return plu


class JournalValidationError(ValueError):
    """FN-15 — jurnal ditolak di pintu insert (tidak seimbang / angka / akun tidak layak)."""


# ─── PK-36 (IC-06) — akun kontrol hanya berubah lewat dokumennya ─────────────────────────────────────────────────────
class ControlAccountError(JournalValidationError):
    """PK-36 — jurnal manual / reklas suspense / pembalikan manual menyentuh akun kontrol (router → 422)."""

    def __init__(self, message: str, *, code: str, ledger: str) -> None:
        super().__init__(message)
        self.code = code
        self.ledger = ledger


async def assert_no_control_accounts(codes: List[str], entity_id: Optional[str], *, aksi: str,
                                     jurnal: Optional[Dict[str, Any]] = None) -> None:
    """PK-36 — tolak bila salah satu `codes` akun kontrol PT itu (pengaturan `gl.jurnal_manual_akun_kontrol` = tolak).

    `aksi`: "jurnal_manual" · "reklas_suspense" · "pembalikan_manual" (`jurnal` = jurnal asal, untuk pesannya).
    Tidak dipasang di `_insert_entry`: jurnal otomatis dokumen tetap bebas menulis akun kontrol (02 §1 P10)."""
    from services.config_resolver import value_of
    from services import gl_mapping_registry as _reg, gl_mapping_service as _glm
    if await value_of("gl.jurnal_manual_akun_kontrol", {"entity_id": entity_id or ""}) == "izinkan":
        return
    kontrol = await _glm.control_accounts(entity_id)
    kena = sorted({c for c in codes if c in kontrol})
    if not kena:
        return
    code = kena[0]
    ledger = kontrol[code]
    info = _reg.CONTROL_LEDGERS[ledger]
    if aksi == "pembalikan_manual":
        je = jurnal or {}
        msg = (f"Jurnal {je.get('number') or je.get('id', '')} berasal dari "
               f"{journal_source_label(je.get('source_type'))} dan menyentuh akun kontrol {info['label']}. "
               f"Batalkan atau koreksi dokumen sumbernya; pembalikan manual ditolak.")
    else:
        nama = ((await effective_accounts([code], entity_id)).get(code) or {}).get("name", "")
        msg = (f"Akun {code}{f' · {nama}' if nama else ''} adalah akun kontrol {info['label']} dan tidak menerima "
               f"jurnal manual. Koreksi lewat {info['dokumen']}.")
    raise ControlAccountError(msg, code=code, ledger=ledger)


async def assert_bukan_akun_rekening(codes: List[str], accounts: Dict[str, Dict[str, Any]], *,
                                     jurnal: Optional[Dict[str, Any]] = None) -> None:
    """Kas & Bank 1 — tolak jurnal manual ke akun rekening (akun bagan PT ber-`bank_account_id`, `accounts` = bagan
    akun efektif PT buku jurnal) dengan kalimat siap tampil (`ValueError` → router 400). `jurnal` diisi = pembalikan
    manual jurnal itu (tinjauan T1 I3): saldo akun rekening hanya berubah lewat dokumen kasnya (batal kas)."""
    for c in codes:
        rid = (accounts.get(c) or {}).get("bank_account_id") or ""
        if rid:
            rek = await db.bank_accounts.find_one({"id": rid}, {"_id": 0, "name": 1}) or {}
            nama = rek.get("name") or accounts[c].get("name") or rid
            if jurnal is not None:
                raise ValueError(f"Jurnal {jurnal.get('number') or jurnal.get('id', '')} menyentuh akun {c}, akun "
                                 f"rekening {nama}; balik lewat pembatalan dokumen kasnya, bukan pembalikan manual.")
            raise ValueError(f"Akun {c} adalah akun rekening {nama}; isi lewat kas atau Pindah Dana, bukan jurnal "
                             f"manual.")


async def effective_accounts(codes: Optional[List[str]] = None,
                             entity_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """FN-05/FN-06 — COA efektif satu entitas: template global + override/akun khusus entitas
    itu (override menang, deterministik). Tanpa entity_id → global saja (dimensi grup)."""
    q: Dict[str, Any] = {"$or": [{"entity_id": {"$in": [None, ""]}}]}
    if entity_id:
        q["$or"].append({"entity_id": entity_id})
    if codes is not None:
        q["code"] = {"$in": list(codes)}
    out: Dict[str, Dict[str, Any]] = {}
    for a in await db.gl_accounts.find(q, {"_id": 0}).to_list(5000):
        code = a.get("code")
        if code and (code not in out or (entity_id and a.get("entity_id") == entity_id)):
            out[code] = a
    return out


def _sen(x: Any) -> int:
    """PK-10 (GL-07) — rupiah → sen bulat. Seimbang dibandingkan dalam sen, bukan pecahan bertoleransi."""
    return int(round(float(x or 0) * 100))


async def _validate_entry_lines(norm: List[Dict[str, Any]], entity_id: Optional[str] = None) -> None:
    """FN-15 — validator pusat untuk SEMUA autopost & manual: angka finite, non-negatif,
    satu sisi per baris, seimbang setelah pembulatan, akun ada + aktif + boleh diposting."""
    import math
    if not norm:
        raise JournalValidationError("Jurnal tanpa baris")
    for ln in norm:
        d, c = ln["debit"], ln["credit"]
        if not (math.isfinite(d) and math.isfinite(c)):
            raise JournalValidationError(f"Nilai jurnal tidak valid (NaN/Infinity) pada akun {ln['account_code']}")
        if d < 0 or c < 0:
            raise JournalValidationError(f"Nilai jurnal negatif pada akun {ln['account_code']}")
        if d > 0 and c > 0:
            raise JournalValidationError(f"Baris akun {ln['account_code']} berisi debit DAN kredit sekaligus")
        if not ln["account_code"]:
            raise JournalValidationError("Baris jurnal tanpa kode akun")
    td = round(sum(ln["debit"] for ln in norm), 2)
    tc = round(sum(ln["credit"] for ln in norm), 2)
    sd, sc = sum(_sen(ln["debit"]) for ln in norm), sum(_sen(ln["credit"]) for ln in norm)
    if sd <= 0 or sd != sc:
        raise JournalValidationError(f"Jurnal tidak seimbang (debit {td:,.2f} ≠ kredit {tc:,.2f})")
    codes = sorted({ln["account_code"] for ln in norm})
    accs = await effective_accounts(codes, entity_id)  # FN-06 — resolver akun yang sama dgn laporan
    for code in codes:
        a = accs.get(code)
        if not a:
            raise JournalValidationError(f"Akun {code} tidak ada di bagan akun")
        if a.get("is_active") is False:
            raise JournalValidationError(f"Akun {code} nonaktif")
        if a.get("is_postable") is False:
            raise JournalValidationError(f"Akun {code} adalah akun induk (tidak boleh diposting)")


async def preflight_posting(entity_id: str, date: str = "") -> None:
    """P03 — cek periode SEBELUM efek bisnis ditulis (gagal cepat, tanpa state setengah jadi)."""
    from services.book_date import tanggal_buku   # PK-37 — kosong = hari ini di WIB
    await enforce_closed_period_guard(entity_id or DEFAULT_ENTITY_ID, tanggal_buku(date),
                                      source_type="preflight", can_backdate=True)


async def preflight_entry(*, lines: List[Dict[str, Any]], entity_id: str, date: str = "",
                          source_type: str = "preflight") -> None:
    """PK-05 — pemeriksaan yang SAMA dengan `_insert_entry` (pemetaan akun, normalisasi, validator, periode
    tertutup) tanpa nomor dan tanpa sisip. Dipanggil langkah PERIKSA aksi posting sebelum efek apa pun ditulis.
    Melempar `JournalValidationError` atau `ClosedPeriodError`."""
    from services import gl_mapping_service as _glm
    lines = await _glm.remap_lines(lines, entity_id or DEFAULT_ENTITY_ID, source_type)
    names = await _account_names([l["account_code"] for l in lines], entity_id)
    norm = [ln for ln in _norm_lines(lines, names) if ln["debit"] or ln["credit"]]
    await _validate_entry_lines(norm, entity_id)
    await enforce_closed_period_guard(entity_id or DEFAULT_ENTITY_ID, date or now_iso(),
                                      source_type=source_type, can_backdate=True)


def durable_fields(field: str = "gl_status") -> Dict[str, str]:
    """PK-18 — nama field penanda jurnal untuk `field` status: `gl_status` → `gl_error`/`gl_failed_at`/
    `journal_entry_id`; `void_gl_status` → `void_gl_error`/…; `steps.$.gl_status` → `steps.$.gl_error`/…"""
    pre = field[:-len("gl_status")] if field.endswith("gl_status") else f"{field}_"
    return {"status": field, "error": f"{pre}gl_error", "failed_at": f"{pre}gl_failed_at",
            "journal": f"{pre}journal_entry_id"}


async def post_durable(collection: str, doc_id: str, post: Callable[[], Awaitable[Any]], *,
                       source_type: str, source_id: str, field: str = "gl_status",
                       match: Optional[Dict[str, Any]] = None, raise_on_fail: bool = False) -> Dict[str, Any]:
    """PK-18 (GL-02, IV-04) — satu pintu tahan-gagal untuk jurnal dokumen apa pun (`02_STANDAR.md` §1 P1, langkah 4).

    `post` = fungsi tanpa argumen yang memanggil satu fungsi `post_*` (atau resep `posting_registry`). Urutan:
    (a) jalankan `post()`; (b) melempar → `<field>="failed"`, galat (≤ 300 huruf), waktu gagal; lempar ulang hanya bila
    `raise_on_fail`; (c) selesai → jurnal tidak-void ber-(`source_type`, `source_id`) ada → `posted` + id jurnalnya,
    tidak ada → `not_required` (fungsi posting sengaja tidak menjurnal, mis. nominal nol). Status ditulis dari HASIL,
    bukan dianggap berhasil. `match` = saringan tambahan untuk unsur larik (`{"steps.seq": 2}` dengan
    `field="steps.$.gl_status"`). → `{"gl_status", "gl_error", "journal_entry_id", "journal"}`."""
    f = durable_fields(field)
    flt = {"id": doc_id, **(match or {})}
    try:
        je = await post()
    except Exception as exc:
        pesan = str(exc)[:300] or exc.__class__.__name__
        await db[collection].update_one(flt, {"$set": {f["status"]: "failed", f["error"]: pesan,
                                                       f["failed_at"]: now_iso(), "updated_at": now_iso()}})
        if raise_on_fail:
            raise
        return {"gl_status": "failed", "gl_error": pesan, "journal_entry_id": "", "journal": None}
    posted = je if isinstance(je, dict) and je.get("id") else await db.journal_entries.find_one(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}},
        {"_id": 0, "id": 1, "number": 1})
    status = "posted" if posted else "not_required"
    jid = (posted or {}).get("id", "")
    await db[collection].update_one(flt, {"$set": {f["status"]: status, f["error"]: "", f["journal"]: jid,
                                                   "updated_at": now_iso()}})
    return {"gl_status": status, "gl_error": "", "journal_entry_id": jid,
            "journal": je if isinstance(je, dict) else None}


async def post_cash_durable(txn: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """FN-07/FN-10/CX-04 — posting jurnal kas dengan status TERLIHAT di dokumen kas
    (`gl_status` posted|failed + galat). Idempotent; kegagalan dilempar ke pemanggil.
    PK-18 — pembungkus tipis `post_durable(..., raise_on_fail=True)`; perilakunya tidak berubah."""
    res = await post_durable("cash_transactions", txn["id"], lambda: _post_cash_transaction(txn),
                             source_type="cash_transaction", source_id=txn["id"], raise_on_fail=True)
    return res["journal"]


async def _insert_entry(*, lines: List[Dict[str, Any]], description: str, date: str,
                        source_type: str, source_id: str, entity_id: str,
                        created_by: str, source_label: str = "",
                        ref: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Insert jurnal seimbang. Caller MEMASTIKAN balance (helper auto-post).
    `ref` (opsional) = tautan dokumen induk, mis. {"order_id": ...} untuk jurnal per surat jalan."""
    from services import gl_mapping_service as _glm  # GL-01 — akun dari Pemetaan Akun
    lines = await _glm.remap_lines(lines, entity_id or DEFAULT_ENTITY_ID, source_type)
    names = await _account_names([l["account_code"] for l in lines], entity_id)
    norm = _norm_lines(lines, names)
    norm = [ln for ln in norm if ln["debit"] or ln["credit"] or ln["debit"] != ln["debit"]]  # buang baris 0/0
    await _validate_entry_lines(norm, entity_id)  # FN-15 — pintu kontrol, bukan tanggung jawab tiap caller
    total_debit = round(sum(l["debit"] for l in norm), 2)
    total_credit = round(sum(l["credit"] for l in norm), 2)
    from services.book_date import tanggal_buku   # PK-37 (GL-05) — tanggal buku WIB 10 huruf; stempel di created_at
    book_date = tanggal_buku(date)
    number = await next_doc_number("journal_entries", "number", "JE-", entity_id=entity_id)
    doc = {
        "id": new_id("je"),
        "number": number,
        "date": book_date,
        "description": description,
        "source": source_type,
        "source_type": source_type,
        "source_id": source_id,
        "source_label": source_label,
        "lines": norm,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "status": "posted",
        "entity_id": entity_id or DEFAULT_ENTITY_ID,
        "created_by": created_by or "system",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    if ref:
        doc["ref"] = ref
    # AG-T5 — jurnal yang lahir dari permintaan kartu tindakan asisten (balik jurnal, kas bayar hutang/kas manual).
    from ai_card_context import card_field
    doc.update(card_field())
    # FASE G-5 — hard-lock periode tertutup + tandai jurnal mundur ber-unlock.
    plu = await enforce_closed_period_guard(
        doc["entity_id"], doc["date"], source_type=source_type, can_backdate=True)
    if plu:
        doc["backdated_in_unlock"] = plu["id"]
    try:
        await db.journal_entries.insert_one(doc)
    except Exception as exc:  # noqa: BLE001
        # PK-14 (W1) — jurnal aktif untuk sumber ini sudah ada (posting bersamaan): kembalikan yang ada, jangan melempar.
        # Duplikat pada `number` tetap dilempar.
        from indexes import is_duplicate_on
        if source_id and is_duplicate_on(exc, "source_type", "source_id"):
            prior = await db.journal_entries.find_one(
                {"source_type": source_type, "source_id": source_id, "status": {"$in": ["posted", "draft"]}},
                {"_id": 0})
            if prior:
                return safe_doc(prior)
        raise
    if source_type != "closing":
        await _mark_stale_closings(doc["entity_id"], doc["date"])
        if plu:
            from services import period_unlock_service as _pus
            await _pus.register_backdated_je(plu["id"], doc["id"])
    return safe_doc(doc)


async def _mark_stale_closings(entity_id: str, date_iso: str) -> None:
    """F-9 — posting backdate ke periode tertutup → tandai closing STALE (perlu re-close)."""
    d = (date_iso or "")[:10]
    if not d or not entity_id:
        return
    await db.period_closings.update_many(
        # PK-11 — juga catatan yang SEDANG ditutup (`closing`): jurnal yang menyusup selama proses tidak hilang tanpa tanda.
        {"entity_id": entity_id, "status": {"$in": ["closed", "closing"]}, "stale": {"$ne": True},
         "start_date": {"$lte": d}, "end_date": {"$gte": d}},
        {"$set": {"stale": True, "stale_at": now_iso(),
                  "stale_reason": f"Ada posting jurnal backdate ({d}) setelah periode ditutup",
                  "updated_at": now_iso()}})


async def create_manual_entry(payload, actor: Dict[str, Any],
                              entity_id: Optional[str] = None,
                              can_backdate: bool = True, *,
                              hanya_periksa: bool = False,
                              disetujui: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Jurnal manual. KF-T6 — `hanya_periksa=True`: validasi + periksa periode SAJA (tanpa nomor, tanpa sisip) untuk
    usulan jurnal yang menunggu orang kedua; `disetujui` = penyetuju usulan (`approved_by` di jurnal; `actor` =
    pengusul sebagai `created_by`)."""
    raw = [ln.model_dump() if hasattr(ln, "model_dump") else dict(ln) for ln in (payload.lines or [])]
    if len(raw) < 2:
        raise ValueError("Jurnal minimal 2 baris (debit & kredit).")
    codes = [str(l.get("account_code", "")).strip() for l in raw]
    if any(not c for c in codes):
        raise ValueError("Setiap baris harus memilih akun.")
    # FN-06 — akun efektif badan usaha buku jurnal (global + override/akun khusus entitas).
    # PK-09 (IC-05) — PT dari ROUTER (sudah diadu dengan penugasan); isi jurnal tidak boleh menunjuk PT lain.
    if entity_id and payload.entity_id and payload.entity_id != entity_id:
        raise ValueError("PT pada isi jurnal berbeda dengan PT yang sedang aktif.")
    eid = entity_id or payload.entity_id or active_entity_or(DEFAULT_ENTITY_ID)
    accounts = await effective_accounts(codes, eid)
    for c in codes:
        if c not in accounts:
            raise ValueError(f"Akun '{c}' tidak ditemukan.")
        if not accounts[c].get("is_postable", True):
            raise ValueError(f"Akun '{c}' adalah header — pilih akun detail (postable).")
        if accounts[c].get("is_active") is False:
            raise ValueError(f"Akun '{c}' nonaktif.")
    # Kas & Bank 1 (§7 butir 3) — akun rekening hanya diisi lewat kas/Pindah Dana, supaya saldonya = buku kas rekening;
    # juga untuk usulan (`hanya_periksa`) & saat disetujui.
    await assert_bukan_akun_rekening(codes, accounts)
    await assert_no_control_accounts(codes, eid, aksi="jurnal_manual")
    names = {c: accounts[c]["name"] for c in codes}
    lines = _norm_lines(raw, names)
    import math as _math
    for l in lines:
        # G3 D4-GL-02 — NaN/±Infinity lolos semua perbandingan di bawah → tolak lebih dulu.
        if not (_math.isfinite(float(l["debit"])) and _math.isfinite(float(l["credit"]))):
            raise ValueError("Nilai debit/kredit harus angka terhingga (NaN/Infinity ditolak).")
    for l in lines:
        if l["debit"] < 0 or l["credit"] < 0:
            raise ValueError("Nilai debit/kredit tidak boleh negatif.")
        if _sen(l["debit"]) > 0 and _sen(l["credit"]) > 0:
            raise ValueError("Satu baris hanya boleh debit ATAU kredit.")
        if _sen(l["debit"]) == 0 and _sen(l["credit"]) == 0:   # PK-10 — baris 0,01 bukan "kosong"
            raise ValueError("Setiap baris harus punya nilai debit atau kredit.")
    total_debit = round(sum(l["debit"] for l in lines), 2)
    total_credit = round(sum(l["credit"] for l in lines), 2)
    # PK-10 (GL-07) — seimbang lewat VALIDATOR PUSAT (sen bulat), sebelum nomor jurnal diambil.
    await _validate_entry_lines(lines, eid)
    if hanya_periksa:   # KF-T6 — usulan: periode diperiksa dengan aturan yang sama, tidak ada yang ditulis
        await enforce_closed_period_guard(eid, payload.date or now_iso(), source_type="manual",
                                          can_backdate=can_backdate)
        return {"entity_id": eid, "lines": lines, "total_debit": total_debit, "total_credit": total_credit}
    # FASE E-1 (E1.10) — jurnal manual masuk buku badan usaha konteks bila tak disebut (eid di atas).
    from services.book_date import tanggal_buku   # PK-37 (GL-05) — tanggal buku WIB 10 huruf
    book_date = tanggal_buku(payload.date)
    number = await next_doc_number("journal_entries", "number", "JE-", entity_id=eid)
    doc = {
        "id": new_id("je"),
        "number": number,
        "date": book_date,
        "description": (payload.description or "").strip() or "Jurnal manual",
        "source": "manual",
        "source_type": "manual",
        "source_id": "",
        "source_label": "Manual",
        "lines": lines,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "status": "posted",
        "entity_id": eid,
        "created_by": actor.get("name", "system"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    from ai_card_context import card_field   # AG-T5 — jurnal manual dari kartu tindakan asisten
    doc.update(card_field())
    if disetujui:   # KF-T6 — jurnal manual dua orang: pengusul (created_by) ≠ penyetuju (approved_by)
        doc.update({"created_by_id": actor.get("id", ""), "approved_by": disetujui.get("name", ""),
                    "approved_by_id": disetujui.get("id", ""), "approved_at": now_iso(),
                    "proposal_id": disetujui.get("proposal_id", "")})
    # FASE G-5 — jurnal manual mundur ke periode tertutup butuh jendela unlock aktif.
    plu = await enforce_closed_period_guard(
        eid, doc["date"], source_type="manual", can_backdate=can_backdate)
    if plu:
        doc["backdated_in_unlock"] = plu["id"]
    await db.journal_entries.insert_one(doc)
    await _mark_stale_closings(eid, doc["date"])
    if plu:
        from services import period_unlock_service as _pus
        await _pus.register_backdated_je(plu["id"], doc["id"])
    return safe_doc(doc)


async def list_entries(source: Optional[str] = None, account_code: Optional[str] = None,
                       status: Optional[str] = None, limit: int = 500,
                       scope: Optional[Dict[str, Any]] = None, start: str = "",
                       end: str = "") -> List[Dict[str, Any]]:
    q = _journal_query(source, account_code, status, scope, start, end)
    rows = await db.journal_entries.find(q, {"_id": 0}).sort("number", -1).to_list(limit)
    return rows


def _journal_query(source: Optional[str], account_code: Optional[str],
                   status: Optional[str], scope: Optional[Dict[str, Any]], start: str = "",
                   end: str = "") -> Dict[str, Any]:
    """Satu tempat pembentuk filter jurnal — dipakai versi biasa MAUPUN versi paginasi,
    supaya halaman & total tidak pernah dihitung dari filter yang berbeda.

    PK-43 (UX-13) — `start`/`end` (`YYYY-MM-DD`) menyaring tanggal buku: batas bawah tanggal saja (≤ semua nilai hari
    itu), batas atas sampai akhir hari (`_gl_day_end`) — sama dengan laporan keuangan."""
    q: Dict[str, Any] = dict(scope or {})
    if source:
        q["source_type"] = source
    if account_code:
        q["lines.account_code"] = account_code
    if status:
        q["status"] = status
    rentang: Dict[str, str] = {}
    if start:
        rentang["$gte"] = start[:10]
    if end:
        rentang["$lte"] = _gl_day_end(end)
    if rentang:
        q["date"] = rentang
    return q


async def list_entries_paged(source: Optional[str] = None, account_code: Optional[str] = None,
                             status: Optional[str] = None, scope: Optional[Dict[str, Any]] = None,
                             page: int = 1, page_size: int = 20,
                             q: str = "", start: str = "", end: str = "") -> Dict[str, Any]:
    """P2 — satu halaman jurnal + total (kontrak {items,total,page,page_size,has_more}).

    Urutan `number` menurun dipertahankan supaya jurnal terbaru tetap di halaman 1 —
    sama seperti perilaku daftar tanpa paginasi.
    """
    from pagination import build_search, merge_query, envelope
    query = _journal_query(source, account_code, status, scope, start, end)
    if q:
        query = merge_query(query, build_search(
            q, ["number", "description", "memo", "ref_number", "source_type",
                "source_label"]))   # Latihan Keuangan 17 Nov — nomor dokumen sumber (KSC/CASH-…, AR-…) bisa dicari
    total = await db.journal_entries.count_documents(query)
    rows = await (db.journal_entries.find(query, {"_id": 0})
                  .sort("number", -1)
                  .skip((page - 1) * page_size)
                  .limit(page_size)
                  .to_list(page_size))
    return envelope(rows, total, page, page_size)


async def get_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    return await db.journal_entries.find_one(
        {"$or": [{"id": entry_id}, {"number": entry_id}]}, {"_id": 0})


async def void_entry(entry_id: str, actor: Dict[str, Any],
                     can_backdate: bool = True, reason: str = "") -> Optional[Dict[str, Any]]:
    je = await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})
    if not je:
        return None
    if je.get("status") == "void":
        raise ValueError("Jurnal sudah di-void.")
    if je.get("source_type") != "manual":
        raise ValueError("Hanya jurnal manual yang dapat di-void langsung (jurnal otomatis mengikuti dokumen sumber).")
    if je.get("reversed_by_entry_id") or await reversal_of(je):  # G3 D4-GL-01 / PK-10 — semua mekanisme pembalik
        raise ValueError("Jurnal sudah/sedang dibalik — tidak bisa dianulir lagi.")
    # FN-09 — void mengubah angka periode jurnal itu: penjaga periode sama dengan posting.
    plu = await enforce_closed_period_guard(je.get("entity_id", ""), je.get("date", ""),
                                            source_type="manual_void", can_backdate=can_backdate)
    res = await db.journal_entries.update_one(
        {"id": entry_id, "status": {"$ne": "void"}, "reversed_by_entry_id": {"$exists": False}},
        {"$set": {"status": "void", "voided_by": actor.get("name", "system"),
                  "voided_at": now_iso(), "updated_at": now_iso(),
                  **({"void_reason": reason.strip()[:500]} if (reason or "").strip() else {}),   # S4 — N5
                  **({"voided_in_unlock": plu["id"]} if plu else {})}},
    )
    if res.modified_count != 1:
        raise ValueError("Jurnal sudah di-void.")
    if plu:
        from services import period_unlock_service as _pus
        await _pus.register_backdated_je(plu["id"], entry_id)
    # F-9 — void jurnal dalam periode tertutup juga mengubah angka → tandai stale
    await _mark_stale_closings(je.get("entity_id", ""), je.get("date", ""))
    return await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})


async def reverse_entry(entry_id: str, date: str, reason: str,
                        actor: Dict[str, Any], *, periksa_akun_kontrol: bool = True) -> Optional[Dict[str, Any]]:
    """Kebijakan 2026-10-05 — jurnal pembalik (debit↔kredit) bertanggal pilihan user yang WAJIB di
    periode terbuka (jendela unlock tidak dipakai). Manual + otomatis; jurnal asli & dokumen sumber
    tidak berubah. Satu jurnal hanya bisa dibalik sekali (CAS), jurnal penutup/pembalik tidak.

    PK-36 — jurnal otomatis yang menyentuh akun kontrol tidak bisa dibalik manual (dokumennya yang dibatalkan).
    `periksa_akun_kontrol=False` hanya untuk pemilik dokumen yang membalik jurnalnya sendiri (P10)."""
    je = await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})
    if not je:
        return None
    reason = (reason or "").strip()
    if len(reason) < 5:   # K-14 (26 Okt) — minimum seragam 5 huruf
        raise ValueError("Alasan pembalikan wajib diisi (minimal 5 huruf).")
    d = (date or "").strip()[:10]
    if len(d) != 10:
        raise ValueError("Tanggal jurnal pembalik wajib diisi (YYYY-MM-DD).")
    if je.get("status") == "void":
        raise ValueError("Jurnal sudah dianulir — tidak bisa dibalik.")
    if is_reversal_type(je.get("source_type")):
        raise ValueError("Jurnal penutup / jurnal pembalik tidak dapat dibalik.")
    prior = await reversal_of(je)
    if prior:
        raise ValueError(f"Jurnal sudah dibalik oleh {prior.get('number') or prior.get('id')}.")
    if d < (je.get("date") or "")[:10]:
        raise ValueError("Tanggal pembalik tidak boleh sebelum tanggal jurnal asli.")
    # PK-36 (IC-06) — sebelum klaim `reversed_by_entry_id`. Jurnal `manual` lama yang telanjur menyentuh akun kontrol
    # tetap boleh dibalik: pembalikannya justru mengembalikan saldo ke buku pembantu.
    if periksa_akun_kontrol and je.get("source_type") != "manual":
        await assert_no_control_accounts([ln.get("account_code", "") for ln in je.get("lines") or []],
                                         je.get("entity_id"), aksi="pembalikan_manual", jurnal=je)
    if periksa_akun_kontrol:
        # Kas & Bank 1 (tinjauan T1 I3) — pembalikan manual jurnal apa pun yang menyentuh akun rekening ditolak: dokumen
        # kasnya tetap tercatat sehingga saldo akun ≠ buku kas rekening. Batal kas memakai `post_cash_void` /
        # `_reverse_once` (bukan fungsi ini) dan tidak terhalang; pemilik dokumen (`periksa_akun_kontrol=False`) juga.
        kode = [ln.get("account_code", "") for ln in je.get("lines") or []]
        await assert_bukan_akun_rekening(kode, await effective_accounts(kode, je.get("entity_id")), jurnal=je)
        # Kas & Bank 1 (Tugas 2) — jurnal kas LAMA (akun lama) yang saldonya sudah dipindah ke akun rekening:
        # pembaliknya akan masuk akun rekening (`baris_kas_rekening`), padahal dokumen kasnya tetap tercatat → ditolak.
        alih = await baris_kas_rekening(je)
        if alih:
            a = next(iter(alih.values()))
            rek = await db.bank_accounts.find_one({"id": a["rekening"]}, {"_id": 0, "name": 1}) or {}
            raise ValueError(f"Jurnal {je.get('number') or je.get('id', '')} mencatat kas rekening "
                             f"{rek.get('name') or a['rekening']} yang saldonya sudah dipindah ke akun {a['akun']}; "
                             f"balik lewat pembatalan dokumen kasnya, bukan pembalikan manual.")
    await enforce_closed_period_guard(je["entity_id"], d, source_type="reversal", can_backdate=False)
    return await _reverse_once(
        je, source_type="reversal", source_id=entry_id, date=f"{d}T00:00:00",
        description=f"Pembalik {je.get('number', '')}: {reason}", created_by=actor.get("name", "system"),
        source_label=f"Pembalik {je.get('number', '')}", line_desc=f"Pembalik {je.get('number', '')}",
        reason=reason, extra_ref={"reason": reason}, strict=True)


# ═════════════════════════════════════════════════════════════════════════════
#  PK-10 (GL-01) — SATU JALUR PEMBALIK untuk semua mekanisme (manual, batal dokumen, batal kas, reklas deposit)
# ═════════════════════════════════════════════════════════════════════════════
_LEGACY_REVERSAL_TYPE = {"cash_transaction": "cash_transaction_void", "ar_receipt_deposit": "ar_receipt_deposit_void"}


def is_reversal_type(source_type: Optional[str]) -> bool:
    """Jurnal bertipe pembalik/penutup tidak bisa dibalik lagi."""
    st = source_type or ""
    return st in ("closing", "reversal") or st.endswith("_reversal") or st.endswith("_void")


async def reversal_of(je: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Jurnal pembalik yang SUDAH ada untuk `je`, siapa pun yang membuatnya. Penanda acuan dulu, lalu warisan."""
    for key in (je.get("reversed_by_entry_id"), je.get("reversal_id")):
        if key and key != "pending":
            r = await db.journal_entries.find_one({"id": key, "status": {"$ne": "void"}}, {"_id": 0})
            if r:
                return r
    if je.get("id"):
        r = await db.journal_entries.find_one({"ref.reverses_entry_id": je["id"], "status": {"$ne": "void"}},
                                              {"_id": 0})
        if r:
            return r
    sid = je.get("source_id") or ""
    if sid:
        st = je.get("source_type") or ""
        r = await db.journal_entries.find_one(
            {"source_type": _LEGACY_REVERSAL_TYPE.get(st, f"{st}_reversal"), "source_id": sid,
             "status": {"$ne": "void"}}, {"_id": 0})
        if r:
            return r
    if je.get("reversed") is True:   # penanda warisan tanpa id jurnal pembalik
        return {"id": je.get("reversal_id") or "", "number": je.get("reversal_id") or "(tanpa nomor)"}
    return None


async def _reverse_once_ex(je: Dict[str, Any], *, source_type: str, source_id: str, date: str, description: str,
                           created_by: str, source_label: str = "", line_prefix: str = "Pembalik",
                           line_desc: str = "", reason: str = "", extra_ref: Optional[Dict[str, Any]] = None,
                           strict: bool = False) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Balik `je` TEPAT SEKALI. → (jurnal pembalik, baru dibuat?). `strict`: tipe pembalik / sudah dibalik → ValueError.

    Klaim di jurnal asal (`reversed_by_entry_id: "pending"`) sebelum sisip; gagal sisip → klaim dicabut. Sesudah
    sisip semua penanda (acuan + cermin warisan) ditulis pada jurnal asal; pembalik membawa `ref.reverses_entry_id`."""
    if is_reversal_type(je.get("source_type")):
        if strict:
            raise ValueError("Jurnal penutup / jurnal pembalik tidak dapat dibalik.")
        return None, False
    prior = await reversal_of(je) or await db.journal_entries.find_one(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}}, {"_id": 0})
    if prior:
        if strict:
            raise ValueError(f"Jurnal sudah dibalik oleh {prior.get('number') or prior.get('id')}.")
        return prior, False
    claim = await db.journal_entries.find_one_and_update(
        {"id": je["id"], "status": {"$ne": "void"}, "reversed_by_entry_id": {"$exists": False},
         "reversed": {"$ne": True}},
        {"$set": {"reversed_by_entry_id": "pending", "updated_at": now_iso()}})
    if not claim:
        fresh = await db.journal_entries.find_one({"id": je["id"]}, {"_id": 0}) or je
        prior = await reversal_of(fresh)
        if strict:
            raise ValueError(f"Jurnal sudah dibalik oleh {prior.get('number') or prior.get('id')}." if prior
                             else "Jurnal sedang/sudah dibalik — muat ulang.")
        return prior, False
    ref = {**(je.get("ref") or {}), **(extra_ref or {}),
           "reverses_entry_id": je["id"], "reverses_entry_number": je.get("number", "")}
    try:
        # Kas & Bank 1 (§5.1) — baris kas LAMA milik dokumen kas ber-rekening yang saldonya sudah dipindah ke akun
        # rekening (PT aktif sesudah jurnal & kasnya terbit) dibalik ke akun rekening itu, bukan ke akun lama.
        alih = await baris_kas_rekening(je)
        rev = await _insert_entry(
            lines=[{"account_code": (alih.get(i) or {}).get("akun") or ln["account_code"],
                    "debit": float(ln.get("credit", 0) or 0), "credit": float(ln.get("debit", 0) or 0),
                    "description": line_desc or f"{line_prefix} {ln.get('description', '')}".strip()}
                   for i, ln in enumerate(je.get("lines", []))],
            description=description, date=date or now_iso(), source_type=source_type, source_id=source_id,
            entity_id=je.get("entity_id", ""), created_by=created_by, source_label=source_label, ref=ref)
    except Exception:
        await db.journal_entries.update_one({"id": je["id"], "reversed_by_entry_id": "pending"},
                                            {"$unset": {"reversed_by_entry_id": ""}})
        raise
    await db.journal_entries.update_one({"id": je["id"]}, {"$set": {
        "reversed_by_entry_id": rev["id"], "reversed_by_entry_number": rev.get("number", ""),
        "reversed": True, "reversed_at": now_iso(), "reversal_id": rev["id"],
        "reversal_reason": reason, "reversed_by": created_by, "updated_at": now_iso()}})
    return rev, True


async def _reverse_once(je: Dict[str, Any], **kw: Any) -> Optional[Dict[str, Any]]:
    rev, _created = await _reverse_once_ex(je, **kw)
    return rev


async def kas_jurnal(je: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Dokumen kas yang dijurnal `je`: kas sumber jurnal `cash_transaction` (id kas = `source_id`), atau kas yang
    menumpang jurnal induk (`journal_entry_id` / `parent_journal` = id jurnal — refund retur, gaji jalur lama, aset).
    Kas berstatus apa pun (pembalik dipanggil saat kasnya sedang dibatalkan)."""
    if je.get("source_type") == "cash_transaction":
        t = await db.cash_transactions.find_one({"id": je.get("source_id") or "__none__"}, {"_id": 0})
        return [t] if t else []
    if not je.get("id"):
        return []
    return await db.cash_transactions.find({"$or": [{"journal_entry_id": je["id"]}, {"parent_journal": je["id"]}]},
                                           {"_id": 0}).to_list(50)


async def baris_kas_rekening(je: Dict[str, Any]) -> Dict[int, Dict[str, str]]:
    """Kas & Bank 1 (§5.1 "pembalik jurnal kas lama sesudah PT aktif") — baris akun kas LAMA jurnal `je` yang mencatat
    kas ber-rekening dan saldonya SUDAH dipindah ke akun rekening (pindah saldo Tugas 3 memindah saldo per rekening per
    akun asal dari jurnal yang terbit sebelum PT menyala). → `{indeks baris: {"akun": kode akun rekening, "rekening": id
    rekening}}`; kosong = baris jurnal dipakai apa adanya.

    Syarat (semuanya): PT jurnal sudah aktif; jurnal DAN dokumen kasnya terbit sebelum PT aktif (`aktif_sejak`);
    rekening dokumen kas milik PT jurnal ber-akun rekening (`akun_rekening` — rekening PT lain tetap akun lama, R4);
    baris = akun kas lama PT itu (`report_basis.kode_kas` tanpa akun rekening: bawaan + pemetaan + riwayat) di sisi kas
    dokumen (kas masuk = debit, keluar = kredit) bernominal sama. Satu baris per dokumen kas. Dipakai pembalik terpadu
    (`_reverse_once_ex`: batal kas, batal dokumen) dan penolakan pembalikan manual (`reverse_entry`)."""
    eid = je.get("entity_id") or ""
    from services import cash_account_mode as _mode
    sejak = await _mode.aktif_sejak(eid)
    if not sejak or not (je.get("created_at") or "") or je["created_at"] >= sejak:
        return {}
    kas = [t for t in await kas_jurnal(je) if t.get("account_id") and (t.get("created_at") or "") < sejak]
    if not kas:
        return {}
    from services import report_basis as _rb
    lama = await _rb.kode_kas(eid) - await kode_akun_rekening(eid)
    lines = je.get("lines") or []
    out: Dict[int, Dict[str, str]] = {}
    for t in kas:
        akun = await akun_rekening(eid, t["account_id"])
        if not akun:
            continue
        sisi = "debit" if t.get("direction") == "in" else "credit"
        sen = _sen(t.get("amount"))
        for i, ln in enumerate(lines):
            if i not in out and ln.get("account_code") in lama and _sen(ln.get(sisi)) == sen:
                out[i] = {"akun": akun, "rekening": t["account_id"]}
                break
    return out


# ═════════════════════════════════════════════════════════════════════════════
#  AUTO-POSTING (idempotent, derived from SSOT)
# ═════════════════════════════════════════════════════════════════════════════

async def _already_posted(source_type: str, source_id: str) -> bool:
    return bool(await db.journal_entries.find_one(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}},
        {"_id": 0, "id": 1}))


async def any_posting_for(source_id: str) -> bool:
    """F-03/F-04 — sudah ada JE non-void APA PUN source_type-nya untuk dokumen ini?
    Menutup kelas dobel-posting lintas source_type (subcon_service vs vendor_bill)."""
    if not source_id:
        return False
    return bool(await db.journal_entries.find_one(
        {"source_id": source_id, "status": {"$ne": "void"},
         "source_type": {"$not": re.compile(r"_reversal$")}},
        {"_id": 0, "id": 1}))


async def post_order_revenue_and_cogs(order_id: str) -> Dict[str, Any]:
    """F-01 — posting pendapatan + HPP pada PERISTIWA bisnis (dispatch), bukan menunggu
    backfill. KEB-PDPT tahap 2 (pro-rata): bila pesanan punya surat jalan, pendapatan & HPP
    diakui PER SURAT JALAN sebanding nilai barang yang keluar (`shipment_revenue` /
    `shipment_cogs`); pesanan tanpa surat jalan (jalur lama) memakai jurnal per pesanan.
    Uang muka yang tertahan di 2-1400 direklas ke Piutang sebesar yang sudah berpendapatan."""
    fresh = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not fresh:
        return {"revenue": None, "cogs": None, "advance_reclass": None, "shipments": []}
    out: Dict[str, Any] = {"revenue": None, "cogs": None, "advance_reclass": None, "shipments": []}
    ships = await _order_shipments(order_id)
    if ships and not await _already_posted("sales_order", order_id):
        for sh in ships:
            rev = await post_shipment_revenue(sh, fresh)
            cogs = await post_shipment_cogs(sh, fresh)
            out["shipments"].append({"shipment_id": sh.get("id"), "revenue": rev, "cogs": cogs})
        out["revenue"] = next((x["revenue"] for x in out["shipments"] if x["revenue"]), None)
        out["cogs"] = next((x["cogs"] for x in out["shipments"] if x["cogs"]), None)
    else:
        out["revenue"] = await post_sales_order(fresh)
        out["cogs"] = await post_order_cogs(fresh)
    out["advance_reclass"] = await post_advance_reclass(fresh)
    return out


# ─── KEB-PDPT — kebijakan pengakuan pendapatan (Sesi #089/#090) ──────────────
# Pendapatan & HPP HANYA diakui saat barang DIKIRIM. Pembayaran (uang muka/DP) TIDAK
# memicu pengakuan: kas yang masuk untuk pesanan yang belum dikirim dibukukan Cr 2-1400
# Uang Muka Pelanggan (kewajiban) dan direklas ke Piutang sebesar pendapatan yang lahir.
# Tahap 2 — PRO-RATA: tiap surat jalan mengakui porsi nilai barangnya; surat jalan
# penutup (pesanan shipped/done) mengambil SISA supaya total tepat sama grand total.
# Jurnal historis per pesanan (`sales_order`) dibiarkan (prospektif).
REVENUE_STATUSES = {"shipped", "partially_shipped", "done"}
FULLY_SHIPPED_STATUSES = {"shipped", "done"}
ADVANCE_BUCKET = "advance"
SHIPMENT_DEAD = {"cancelled", "void"}


def _revenue_eligible(order: Dict[str, Any]) -> bool:
    return order.get("status") in REVENUE_STATUSES


async def _order_shipments(order_id: str) -> List[Dict[str, Any]]:
    return await db.shipments.find(
        {"order_id": order_id, "status": {"$nin": list(SHIPMENT_DEAD)}}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)


async def _sum_lines(flt: Dict[str, Any], account: str, side: str) -> float:
    """Σ debit/credit satu akun dari JE non-void yang cocok filter."""
    total = 0.0
    async for je in db.journal_entries.find({**flt, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        total += sum(float(l.get(side) or 0) for l in je.get("lines") or [] if l.get("account_code") == account)
    return round(total, 2)


async def kode_akun_rekening(entity_id: str) -> set:
    """Kas & Bank 1 — kode akun rekening (akun bagan PT ber-`bank_account_id`) PT `entity_id`."""
    if not entity_id:
        return set()
    return {a["code"] async for a in db.gl_accounts.find(
        {"entity_id": entity_id, "bank_account_id": {"$nin": [None, ""]}}, {"_id": 0, "code": 1})}


async def order_revenue_posted(order_id: str) -> bool:
    """Sudah ada pendapatan yang lahir (per pesanan ATAU per surat jalan)?"""
    if await _already_posted("sales_order", order_id):
        return True
    return bool(await db.journal_entries.find_one(
        {"source_type": "shipment_revenue", "ref.order_id": order_id, "status": {"$ne": "void"}},
        {"_id": 0, "id": 1}))


#: PK-32 — jurnal nota koreksi pesanan yang ikut menentukan pendapatan yang sudah diakui (`ref.order_id`)
AMENDMENT_NOTE_SOURCES = ("amendment_credit_note", "amendment_debit_note")


async def order_amendment_recognized(order_id: str) -> Dict[str, float]:
    """PK-32 — {revenue, ppn, ar} neto jurnal nota koreksi pesanan: nota debit menambah (Cr 4-1000 / Cr 2-1200 /
    Dr 1-1200), nota kredit mengurangi (Dr 4-1000 / Dr 2-1200 / Cr 1-1200)."""
    flt = {"source_type": {"$in": list(AMENDMENT_NOTE_SOURCES)}, "ref.order_id": order_id}
    rev = await _sum_lines(flt, ACC_PENDAPATAN, "credit") - await _sum_lines(flt, ACC_PENDAPATAN, "debit")
    ppn = await _sum_lines(flt, ACC_PPN_OUT, "credit") - await _sum_lines(flt, ACC_PPN_OUT, "debit")
    ar = await _sum_lines(flt, ACC_PIUTANG, "debit") - await _sum_lines(flt, ACC_PIUTANG, "credit")
    return {"revenue": round(rev, 2), "ppn": round(ppn, 2), "ar": round(ar, 2)}


async def order_revenue_recognized(order_id: str) -> Dict[str, float]:
    """{revenue, ppn, ar} yang sudah diakui untuk pesanan (legacy + per surat jalan + PK-32 nota koreksi pesanan
    `amendment_credit_note`/`amendment_debit_note`), sehingga surat jalan penutup mengambil sisa terhadap nilai efektif.
    Piutang yang dikurangi nota kredit amandemen dihitung dari jurnalnya di sini — baris `payments[]` nota itu
    (`nota_koreksi`/`nota_tangguh`) tidak dihitung `order_direct_ar_paid`."""
    flt = {"$or": [{"source_type": "sales_order", "source_id": order_id},
                   {"source_type": "shipment_revenue", "ref.order_id": order_id}]}
    rev = await _sum_lines(flt, ACC_PENDAPATAN, "credit")
    ppn = await _sum_lines(flt, ACC_PPN_OUT, "credit")
    ar = await _sum_lines(flt, ACC_PIUTANG, "debit") + await _sum_lines(flt, ACC_KAS_BESAR, "debit")
    amd = await order_amendment_recognized(order_id)
    return {"revenue": round(rev + amd["revenue"], 2), "ppn": round(ppn + amd["ppn"], 2),
            "ar": round(ar + amd["ar"], 2)}


async def order_effective_totals(order: Dict[str, Any]) -> Dict[str, float]:
    """PK-32 (`02` D1) — NILAI EFEKTIF PENDAPATAN pesanan `{grand, ppn, net}`: nilai tagihan (grand total + tagihan
    tambahan nota debit, `order_grand_total`) dikurangi Σ nota kredit amandemen yang tidak `void` (bagian yang menutup
    nota debit lama yang belum ditagih, `debit_note_offset`, tidak dihitung); PPN dengan cara yang sama. Dasar
    pendapatan surat jalan dan jurnal per pesanan. Pesanan tanpa nota dan tanpa tagihan tambahan = grand total & PPN
    mentah (tidak berubah satu rupiah pun). Nota batal item tidak dihitung: total pesanannya sudah turun saat batal."""
    grand = round(order_grand_total(order), 2)
    ppn = float(order.get("ppn_amount", order.get("tax", 0)) or 0) + sum(
        float(x.get("ppn") or 0) for x in (order.get("extra_billing_lines") or []) if isinstance(x, dict))
    oid = order.get("id")
    if oid:
        async for cn in db.credit_notes.find({"order_id": oid, "source": "amendment", "status": {"$ne": "void"}},
                                             {"_id": 0, "kind": 1, "gross_amount": 1, "ppn_amount": 1,
                                              "debit_note_offset": 1}):
            if (cn.get("kind") or "credit_note") != "credit_note":
                continue
            g = float(cn.get("gross_amount") or 0)
            part = g - float(cn.get("debit_note_offset") or 0)
            if part <= EPS or g <= EPS:
                continue
            grand -= part
            ppn -= float(cn.get("ppn_amount") or 0) * part / g
    grand, ppn = round(grand, 2), round(ppn, 2)
    return {"grand": grand, "ppn": ppn, "net": round(grand - ppn, 2)}


def order_advance_total(order: Dict[str, Any]) -> float:
    """Σ pembayaran ber-`gl_bucket=advance` (kas yang masuk lewat 2-1400)."""
    return round(sum(float(p.get("amount") or 0) for p in (order.get("payments") or [])
                     if p.get("gl_bucket") == ADVANCE_BUCKET), 2)


#: PK-32 — baris `payments[]` nota kredit amandemen: bagian tertangguh (`nota_tangguh`, pendapatannya belum diakui)
#: dan bagian yang dijurnal Cr 1-1200 (`nota_koreksi`, sudah dihitung `order_revenue_recognized` dari jurnalnya)
NOTE_BUCKETS = ("nota_koreksi", "nota_tangguh")


def order_direct_ar_paid(order: Dict[str, Any], exclude_receipt_id: str = "") -> float:
    """Σ pembayaran yang LANGSUNG mengkredit Piutang (bukan uang muka, bukan baris nota kredit amandemen)."""
    return round(sum(float(p.get("amount") or 0) for p in (order.get("payments") or [])
                     if p.get("gl_bucket") != ADVANCE_BUCKET and p.get("gl_bucket") not in NOTE_BUCKETS
                     and (not exclude_receipt_id or p.get("receipt_id") != exclude_receipt_id)), 2)


async def order_ar_room(order_id: str, exclude_receipt_id: str = "") -> float:
    """Piutang yang sudah LAHIR (pendapatan diakui) dan belum dilunasi langsung —
    batas aman Cr 1-1200 untuk kwitansi baru; sisanya uang muka (2-1400)."""
    if not await order_revenue_posted(order_id):
        return 0.0
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "payments": 1}) or {}
    ar = (await order_revenue_recognized(order_id))["ar"]
    return round(max(0.0, ar - order_direct_ar_paid(order, exclude_receipt_id)), 2)


async def tag_advance_payment(order_id: str, receipt_id: str) -> None:
    """Tandai pembayaran (payments[].receipt_id) sebagai uang muka yang belum diakui.

    PK-19 — satu dokumen sumber bisa punya LEBIH dari satu baris di pesanan yang sama (kwitansi kas + deposit), jadi
    SEMUA barisnya ditandai (dulu hanya baris pertama lewat `payments.$`)."""
    for _ in range(50):
        res = await db.sales_orders.update_one(
            {"id": order_id, "payments": {"$elemMatch": {"receipt_id": receipt_id,
                                                         "gl_bucket": {"$ne": ADVANCE_BUCKET}}}},
            {"$set": {"payments.$.gl_bucket": ADVANCE_BUCKET}})
        if not res.modified_count:
            break


async def order_advance_reclassed(order_id: str) -> float:
    """Netto uang muka yang sudah direklas ke Piutang (reklas − pembalik)."""
    flt = {"source_type": {"$in": ["advance_reclass", "advance_reclass_reversal"]},
           "$or": [{"ref.order_id": order_id}, {"source_id": order_id},
                   {"source_id": {"$regex": f"^{re.escape(order_id)}:"}}]}
    plus = await _sum_lines(flt, ACC_UANG_MUKA_PELANGGAN, "debit")
    minus = await _sum_lines(flt, ACC_UANG_MUKA_PELANGGAN, "credit")
    return round(plus - minus, 2)


async def order_advance_unrecognized(order: Dict[str, Any]) -> float:
    """Uang muka yang MASIH kewajiban di 2-1400 (belum direklas karena barang belum keluar)."""
    adv = order_advance_total(order)
    if adv <= EPS:
        return 0.0
    return round(max(0.0, adv - await order_advance_reclassed(order.get("id", ""))), 2)


async def post_advance_reclass(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Dr 2-1400 Uang Muka Pelanggan / Cr 1-1200 Piutang sebesar uang muka yang SUDAH
    berpendapatan (pro-rata mengikuti surat jalan) dan belum direklas. Berulang aman:
    memposting selisihnya saja. source_id: order_id (pertama), lalu `{order_id}:rc{n}`."""
    sid = order.get("id")
    adv = order_advance_total(order)
    if not sid or adv <= EPS:
        return None
    ar = (await order_revenue_recognized(sid))["ar"]
    # Piutang yang sudah dilunasi LANGSUNG (bukan lewat uang muka) tak boleh direklas lagi.
    ar = round(ar - order_direct_ar_paid(order), 2)
    if ar <= EPS:
        return None
    target = round(min(adv, ar), 2)
    done = await order_advance_reclassed(sid)
    delta = round(target - done, 2)
    if delta <= EPS:
        return None
    n = await db.journal_entries.count_documents(
        {"source_type": "advance_reclass", "$or": [{"ref.order_id": sid}, {"source_id": sid}]})
    src = sid if n == 0 else f"{sid}:rc{n + 1}"
    num = order.get("number", sid)
    lines = _balanced_pair(ACC_UANG_MUKA_PELANGGAN, ACC_PIUTANG, delta,
                           f"Reklas uang muka → piutang {num}")
    return await _insert_entry(
        lines=lines, description=f"Uang muka {num} diakui sebagai pelunasan piutang",
        date=await _revenue_date(order), source_type="advance_reclass", source_id=src,
        entity_id=order.get("entity_id", ""), created_by="system", source_label=num,
        ref={"order_id": sid})


async def post_advance_reclass_reversal(order: Dict[str, Any], receipt_id: str, amount: float,
                                        *, label: str = "") -> Optional[Dict[str, Any]]:
    """Kwitansi uang muka dibatalkan SETELAH (sebagian) direklas: kembalikan porsinya ke
    Piutang (Dr 1-1200 / Cr 2-1400) supaya net bersama jurnal void kas = Dr Piutang / Cr Kas.
    Besarnya = min(nominal kwitansi, netto yang sudah direklas). source_id `{order_id}:{receipt_id}`."""
    sid = order.get("id", "")
    amount = round(float(amount or 0), 2)
    if not sid or amount <= EPS:
        return None
    done = await order_advance_reclassed(sid)
    amount = round(min(amount, done), 2)
    if amount <= EPS:
        return None
    src = f"{sid}:{receipt_id}"
    if await _already_posted("advance_reclass_reversal", src):
        return None
    num = order.get("number", sid)
    lines = _balanced_pair(ACC_PIUTANG, ACC_UANG_MUKA_PELANGGAN, amount,
                           f"Balik reklas uang muka {num} · {label or receipt_id}")
    return await _insert_entry(
        lines=lines, description=f"Pembalikan reklas uang muka {num}", date=now_iso(),
        source_type="advance_reclass_reversal", source_id=src,
        entity_id=order.get("entity_id", ""), created_by="system", source_label=num,
        ref={"order_id": sid})


# ─── KEB-PDPT tahap 2 — pendapatan & HPP PER SURAT JALAN (pro-rata) ──────────
def _order_line_total(item: Dict[str, Any]) -> float:
    lt = item.get("line_total")
    if lt is None:
        lt = item.get("subtotal")
    if lt is None:
        lt = float(item.get("quantity") or 0) * float(item.get("price") or item.get("unit_price") or 0)
    return round(float(lt or 0), 2)


def _order_item_for(order: Dict[str, Any], product_id: str) -> Optional[Dict[str, Any]]:
    return next((it for it in order.get("items") or [] if it.get("product_id") == product_id), None)


def shipment_value_share(order: Dict[str, Any], shipment: Dict[str, Any]) -> float:
    """Porsi nilai pesanan (0..1) yang keluar lewat satu surat jalan = nilai baris × qty/qty baris."""
    total = round(sum(_order_line_total(it) for it in order.get("items") or []), 2)
    it = _order_item_for(order, shipment.get("product_id", ""))
    if total <= EPS or not it:
        return 0.0
    line_qty = float(it.get("base_quantity") or it.get("quantity") or 0)
    if line_qty <= 0:
        return 0.0
    frac = min(1.0, float(shipment.get("qty") or 0) / line_qty)
    return max(0.0, min(1.0, _order_line_total(it) * frac / total))


async def _is_closing_shipment(order: Dict[str, Any], shipment: Dict[str, Any]) -> bool:
    """Surat jalan PENUTUP: pesanan sudah shipped/done dan tidak ada surat jalan lain
    yang belum berjurnal → ambil SISA supaya total pendapatan tepat = grand total."""
    if order.get("status") not in FULLY_SHIPPED_STATUSES:
        return False
    others = [s for s in await _order_shipments(order["id"]) if s.get("id") != shipment.get("id")]
    for s in others:
        if not await _already_posted("shipment_revenue", s.get("id", "")):
            return False
    return True


async def post_shipment_revenue(shipment: Dict[str, Any],
                                order: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Pendapatan pro-rata satu surat jalan: Dr 1-1200 Piutang = porsi grand total;
    Cr 4-1000 Pendapatan = porsi (grand − PPN); Cr 2-1200 PPN Keluaran = porsi PPN.
    Idempotent (source_type shipment_revenue, source_id shipment.id, ref.order_id)."""
    shid, oid = shipment.get("id"), shipment.get("order_id")
    if not shid or not oid or shipment.get("status") in SHIPMENT_DEAD:
        return None
    order = order or await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    if not order or order.get("status") in DEAD_STATUSES:
        return None
    if await _already_posted("sales_order", oid):      # jalur lama per pesanan — jangan dobel
        return None
    if await _already_posted("shipment_revenue", shid):
        return None
    # PK-32 (FX-12/FX-14) — basis = NILAI EFEKTIF (nilai tagihan − nota kredit amandemen); tanpa nota = grand total.
    eff = await order_effective_totals(order)
    grand = eff["grand"]
    ppn_total = eff["ppn"]
    rev_total = round(grand - ppn_total, 2)
    if grand <= EPS:
        return None
    done = await order_revenue_recognized(oid)
    if await _is_closing_shipment(order, shipment):
        rev = round(rev_total - done["revenue"], 2)
        ppn = round(ppn_total - done["ppn"], 2)
    else:
        share = shipment_value_share(order, shipment)
        rev = round(min(rev_total * share, rev_total - done["revenue"]), 2)
        ppn = round(min(ppn_total * share, ppn_total - done["ppn"]), 2)
    if rev <= EPS and ppn <= EPS:
        return None
    num, sj = order.get("number", oid), shipment.get("shipment_no", shid)
    ar = round(rev + max(ppn, 0.0), 2)
    lines = [{"account_code": ACC_PIUTANG, "debit": ar, "credit": 0.0,
              "description": f"Piutang {num} · {sj}"},
             {"account_code": ACC_PENDAPATAN, "debit": 0.0, "credit": rev,
              "description": f"Penjualan {num} · {sj}"}]
    if ppn > EPS:
        lines.append({"account_code": ACC_PPN_OUT, "debit": 0.0, "credit": ppn,
                      "description": f"PPN Keluaran {num} · {sj}"})
    return await _insert_entry(
        lines=lines, description=f"Pengakuan penjualan {num} · {sj}",
        date=shipment.get("created_at") or now_iso(), source_type="shipment_revenue",
        source_id=shid, entity_id=order.get("entity_id", ""), created_by="system",
        source_label=sj, ref={"order_id": oid, "order_number": num})


async def post_shipment_cogs(shipment: Dict[str, Any],
                             order: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """HPP satu surat jalan: Dr 5-1000 / Cr 1-1300 = qty keluar × cost baris (roll aktual/WAC)."""
    shid, oid = shipment.get("id"), shipment.get("order_id")
    if not shid or not oid or shipment.get("status") in SHIPMENT_DEAD:
        return None
    order = order or await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    if not order or order.get("status") in DEAD_STATUSES:
        return None
    if await _already_posted("sales_cogs", oid) or await _already_posted("shipment_cogs", shid):
        return None
    it = _order_item_for(order, shipment.get("product_id", ""))
    qty = float(shipment.get("qty") or 0)
    if not it or qty <= 0:
        return None
    snap = shipment.get("rolls") or []
    if snap:
        # FN-11 — snapshot biaya per roll yang BENAR-BENAR keluar pada surat jalan ini. PK-27 (IV-07) — SEMUA roll,
        # termasuk yang berbiaya 0 (dulu satu roll berbiaya 0 menjatuhkan seluruh surat jalan ke rata-rata roll
        # pesanan berbiaya > 0 × qty → HPP lebih besar dari nilai roll yang keluar). Σ dalam sen (`02` D5).
        cogs = from_cents(sum(
            to_cents(r["extended_cost"]) if r.get("extended_cost") is not None
            else to_cents(float(r.get("unit_cost") or 0) * float(r.get("length") or 0)) for r in snap))
    else:  # surat jalan lama tanpa snapshot → rata-rata roll pesanan (perilaku lama)
        cogs = round(qty * await _order_item_unit_cost(order, it), 2)
    if cogs <= EPS:
        return None
    num, sj = order.get("number", oid), shipment.get("shipment_no", shid)
    lines = _balanced_pair(ACC_HPP, ACC_PERSEDIAAN, cogs, f"HPP penjualan {num} · {sj}")
    return await _insert_entry(
        lines=lines, description=f"HPP penjualan {num} · {sj}",
        date=shipment.get("created_at") or now_iso(), source_type="shipment_cogs",
        source_id=shid, entity_id=order.get("entity_id", ""), created_by="system",
        source_label=sj, ref={"order_id": oid, "order_number": num})


async def _revenue_date(order: Dict[str, Any]) -> str:
    """Tanggal JE = tanggal EVENT pengakuan (pengiriman/pembayaran), bukan created_at."""
    ship = await db.shipments.find_one(
        {"order_id": order.get("id")}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
    if ship and ship.get("created_at"):
        return ship["created_at"]
    if order.get("delivered_at"):
        return order["delivered_at"]
    pays = order.get("payments") or []
    if pays:
        last = pays[-1]
        return last.get("date") or last.get("created_at") or now_iso()
    return order.get("created_at") or now_iso()


def _balanced_pair(debit_acc: str, credit_acc: str, amount: float, desc: str) -> List[Dict[str, Any]]:
    return [
        {"account_code": debit_acc, "debit": amount, "credit": 0.0, "description": desc},
        {"account_code": credit_acc, "debit": 0.0, "credit": amount, "description": desc},
    ]


async def post_sales_order(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pengakuan pendapatan: Dr Piutang/Kas = grand_total; Cr Pendapatan = DPP; Cr PPN Keluaran."""
    if order.get("status") in DEAD_STATUSES:
        return None
    if not _revenue_eligible(order):
        return None
    sid = order.get("id")
    if not sid or await _already_posted("sales_order", sid):
        return None
    # KEB-PDPT tahap 2 — pesanan yang punya surat jalan dijurnal per surat jalan.
    if await db.shipments.find_one({"order_id": sid, "status": {"$nin": list(SHIPMENT_DEAD)}}, {"_id": 0, "id": 1}):
        return None
    # PK-32 — nilai efektif dikurangi bagian yang sudah dijurnal nota koreksi pesanan (tanpa nota = grand total).
    eff = await order_effective_totals(order)
    amd = await order_amendment_recognized(sid)
    grand = round(eff["grand"] - amd["revenue"] - amd["ppn"], 2)
    if grand <= EPS:
        return None
    ppn = round(eff["ppn"] - amd["ppn"], 2)
    is_cash = order_payment_method(order) in NON_AR_METHODS
    debit_acc, ref = ACC_PIUTANG, None
    if is_cash:   # Kas & Bank 1 (R6) — tanpa dokumen kas: akun lama; PT aktif → ditandai belum tertaut
        kas = await akun_kas_tanpa_dokumen(order.get("entity_id", ""), "kas_besar")
        debit_acc = kas["account_code"]
        ref = {"kas_belum_tertaut": True} if kas["belum_tertaut"] else None
    num = order.get("number", sid)
    lines = [{"account_code": debit_acc, "debit": grand, "credit": 0.0,
              "description": f"{'Tunai' if is_cash else 'Piutang'} {num}"}]
    # F-10 — basis pendapatan = HARGA JUAL (grand − PPN), BUKAN DPP Nilai Lain (11/12).
    # DPP nilai lain hanya representasi Faktur Pajak; akuntansi memakai harga jual.
    rev = round(grand - ppn, 2)
    lines.append({"account_code": ACC_PENDAPATAN, "debit": 0.0, "credit": rev,
                  "description": f"Penjualan {num}"})
    if ppn > EPS:
        lines.append({"account_code": ACC_PPN_OUT, "debit": 0.0, "credit": ppn,
                      "description": f"PPN Keluaran {num}"})
    diff = round(grand - (rev + (ppn if ppn > EPS else 0)), 2)
    if abs(diff) > EPS:
        if diff > 0:
            lines.append({"account_code": ACC_PENDAPATAN_LAIN, "debit": 0.0, "credit": diff, "description": "Pembulatan"})
        else:
            lines.append({"account_code": ACC_PENDAPATAN_LAIN, "debit": -diff, "credit": 0.0, "description": "Pembulatan"})
    return await _insert_entry(
        lines=lines, description=f"Pengakuan penjualan {num}", date=await _revenue_date(order),
        source_type="sales_order", source_id=sid, entity_id=order.get("entity_id", ""),
        created_by="system", source_label=num, ref=ref)


COGS_ROLL_STATUSES = ["reserved", "committed", "picked", "packed", "in_transit_sales", "delivered"]


async def _order_item_unit_cost(order: Dict[str, Any], item: Dict[str, Any]) -> float:
    """F-7 — cost per unit untuk 1 baris order (engine costing TUNGGAL).

    Prioritas: (1) roll AKTUAL yang dialokasikan ke order (tertimbang length_initial),
    (2) snapshot cost-at-sale `item.unit_cost`, (3) WAC `costing_service` (fallback)."""
    pid = item.get("product_id", "")
    rolls = await db.inventory_rolls.find(
        {"reserved_ref.id": order.get("id"), "product_id": pid,
         "status": {"$in": COGS_ROLL_STATUSES}},
        {"_id": 0, "unit_cost": 1, "base_unit_cost": 1, "length_initial": 1}).to_list(2000)
    tot_c, tot_w = 0.0, 0.0
    for r in rolls:
        c = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
        w = float(r.get("length_initial") or 0)
        if c > 0 and w > 0:
            tot_c += c * w
            tot_w += w
    if tot_w > 0:
        return round(tot_c / tot_w, 2)
    snap = float(item.get("unit_cost") or 0)
    if snap > 0:
        return snap
    w = await costing_service.wac_for_product(pid, entity_id=order.get("entity_id") or None)
    return float(w.get("wac") or 0)


async def post_order_cogs(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """F3/F-7 — HPP penjualan: Dr HPP / Cr Persediaan = Σ(qty × cost roll aktual).
    Idempotent (source_type='sales_cogs'). Skip bila cost tak diketahui (0)."""
    if order.get("status") in DEAD_STATUSES:
        return None
    if not _revenue_eligible(order):
        return None
    sid = order.get("id")
    if not sid or await _already_posted("sales_cogs", sid):
        return None
    if await db.shipments.find_one({"order_id": sid, "status": {"$nin": list(SHIPMENT_DEAD)}}, {"_id": 0, "id": 1}):
        return None
    eid = order.get("entity_id", "")
    total_cogs = 0.0
    for it in order.get("items", []):
        qty = float(it.get("base_quantity", it.get("quantity", 0)) or 0)
        if qty <= 0:
            continue
        total_cogs += qty * await _order_item_unit_cost(order, it)
    total_cogs = round(total_cogs, 2)
    if total_cogs <= EPS:
        return None
    num = order.get("number", sid)
    lines = _balanced_pair(ACC_HPP, ACC_PERSEDIAAN, total_cogs, f"HPP penjualan {num}")
    return await _insert_entry(
        lines=lines, description=f"HPP penjualan {num}", date=await _revenue_date(order),
        source_type="sales_cogs", source_id=sid, entity_id=eid,
        created_by="system", source_label=num)


# ─── M-3 — Inter-company transfer JE (at-cost) ───────────────────────────────

async def _transfer_items_value_at_cost(
    transfer: Dict[str, Any], source_entity_id: str
) -> Dict[str, Any]:
    """Hitung nilai transfer at-cost dari WAC per produk di entitas SUMBER.
    Return {total, breakdown:[{product_id, sku, name, qty, unit_cost, value}]}."""
    from services.costing_service import wac_for_product
    breakdown: List[Dict[str, Any]] = []
    total = 0.0
    for it in transfer.get("items", []) or []:
        qty = float(it.get("qty") or it.get("quantity") or 0)
        if qty <= 0:
            continue
        pid = it.get("product_id")
        if not pid:
            continue
        wac = await wac_for_product(pid, entity_id=source_entity_id, use_cache=False)
        snap = it.get("unit_cost_snapshot")   # G3 D4-INTERCO-02 — biaya aktual roll yang dipindah
        unit_cost = float(snap) if snap is not None else float(wac.get("wac") or 0)
        value = round(qty * unit_cost, 2)
        breakdown.append({
            "product_id": pid, "sku": it.get("sku", "") or wac.get("sku", ""),
            "name": it.get("product_name", "") or wac.get("name", ""),
            "qty": round(qty, 2), "unit_cost": round(unit_cost, 2), "value": value,
            "cost_source": "roll_snapshot" if snap is not None else wac.get("source", "none"),
        })
        total += value
    return {"total": round(total, 2), "breakdown": breakdown}


async def post_intercompany_transfer(transfer: Dict[str, Any]) -> Dict[str, Any]:
    """M-3 — Posting JE saat kepemilikan roll berpindah antar-PT (at-cost).

    Konservatif (no IC profit sampai barang dijual ke external): senilai WAC-cost
    di entitas SUMBER.

    Buku B (source):  Dr `1-1250` IC-AR         / Cr `1-1300` Persediaan
    Buku E (dest):    Dr `1-1300` Persediaan    / Cr `2-1250` IC-AP

    Idempotent via source_type='inter_company_transfer' + source_id=transfer_id
    (dicek terpisah untuk sisi src dan dst via source_label suffix ':src' / ':dst').

    Jika total cost = 0 (barang tak ber-cost di source), JE dilewati dan return
    metadata dengan `posted=False` — bukan error.
    """
    tid = transfer.get("id")
    src = transfer.get("source_entity_id")
    dst = transfer.get("dest_entity_id")
    if not (tid and src and dst) or src == dst:
        return {"posted": False, "reason": "invalid_transfer", "total": 0.0}

    # G3 D4-INTERCO-01 — guard PER SISI (bukan OR): satu sisi yang sudah ada tidak berarti selesai;
    # sisi yang hilang diposting dengan nilai sisi yang ada, lalu pasangan ditautkan (idempoten).
    src_id = f"{tid}:src"
    dst_id = f"{tid}:dst"
    q_act = {"source_type": "inter_company_transfer", "status": {"$ne": "void"}}
    have_src = await db.journal_entries.find_one({**q_act, "source_id": src_id}, {"_id": 0})
    have_dst = await db.journal_entries.find_one({**q_act, "source_id": dst_id}, {"_id": 0})
    if have_src and have_dst and have_src.get("intercompany_pair_id") and have_dst.get("intercompany_pair_id"):
        return {"posted": False, "reason": "already_posted", "total": 0.0}

    valuation = await _transfer_items_value_at_cost(transfer, src)
    total = float(valuation["total"])
    done = have_src or have_dst
    if done:
        total = round(sum(float(l.get("debit", 0) or 0) for l in done.get("lines") or []), 2)
    if total <= EPS:
        return {"posted": False, "reason": "zero_cost", "total": 0.0,
                "breakdown": valuation["breakdown"]}

    code = transfer.get("code") or tid
    pair_id = f"ict_{tid}"
    date = transfer.get("approved_at") or transfer.get("updated_at") or now_iso()
    desc_src = f"Transfer antar-PT {code} → {dst} (at-cost)"
    desc_dst = f"Transfer antar-PT {code} ← {src} (at-cost)"

    # Buku SOURCE: Dr IC-AR / Cr Persediaan
    je_src = have_src or await _insert_entry(
        lines=_balanced_pair(ACC_IC_AR, ACC_PERSEDIAAN, total, desc_src), description=desc_src, date=date,
        source_type="inter_company_transfer", source_id=src_id, entity_id=src,
        created_by="system", source_label=code,
    )
    # Buku DEST: Dr Persediaan / Cr IC-AP
    je_dst = have_dst or await _insert_entry(
        lines=_balanced_pair(ACC_PERSEDIAAN, ACC_IC_AP, total, desc_dst), description=desc_dst, date=date,
        source_type="inter_company_transfer", source_id=dst_id, entity_id=dst,
        created_by="system", source_label=code,
    )

    # Tautkan pair (untuk audit/konsolidasi). Set pair_id sekaligus + counterpart
    # per-baris dalam DUA update_one terpisah (src.counterpart=dst, dst.counterpart=src).
    await db.journal_entries.update_one(
        {"id": je_src["id"]},
        {"$set": {"intercompany_pair_id": pair_id,
                  "intercompany_counterpart_entity_id": dst,
                  "updated_at": now_iso()}},
    )
    await db.journal_entries.update_one(
        {"id": je_dst["id"]},
        {"$set": {"intercompany_pair_id": pair_id,
                  "intercompany_counterpart_entity_id": src,
                  "updated_at": now_iso()}},
    )

    return {
        "posted": True, "total": total, "pair_id": pair_id,
        "source_je": {"id": je_src["id"], "number": je_src["number"], "entity_id": src},
        "dest_je": {"id": je_dst["id"], "number": je_dst["number"], "entity_id": dst},
        "breakdown": valuation["breakdown"],
    }


# ─── F-8 — Suspense (1-9999): laporan, saldo, reklasifikasi ──────────────────

async def suspense_report(scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Saldo & daftar jurnal yang menyentuh akun Suspense (wajib nol sebelum tutup buku)."""
    sus = await _known("lain.suspense")
    q = {**(scope or {}), "status": {"$ne": "void"}, "lines.account_code": {"$in": sus}}
    entries = await db.journal_entries.find(q, {"_id": 0}).sort("date", -1).to_list(2000)
    balance = 0.0
    items: List[Dict[str, Any]] = []
    for je in entries:
        d = c = 0.0
        for l in je.get("lines", []):
            if l.get("account_code") in sus:
                d += float(l.get("debit", 0) or 0)
                c += float(l.get("credit", 0) or 0)
        balance += d - c
        items.append({"id": je["id"], "number": je.get("number", ""), "date": je.get("date", ""),
                      "description": je.get("description", ""), "source_type": je.get("source_type", ""),
                      "source_label": je.get("source_label", ""), "entity_id": je.get("entity_id", ""),
                      "suspense_debit": round(d, 2), "suspense_credit": round(c, 2)})
    return {"account_code": ACC_SUSPENSE, "account_name": "Suspense (Sementara)",
            "balance": round(balance, 2), "entry_count": len(items), "items": items}


async def suspense_balance(entity_id: str, as_of: str = "") -> float:
    """Saldo bersih (debit − kredit) akun Suspense per entitas s/d tanggal `as_of`."""
    sus = await _known("lain.suspense")
    q: Dict[str, Any] = {"entity_id": entity_id, "status": {"$ne": "void"},
                         "lines.account_code": {"$in": sus}}
    if as_of:
        q["date"] = {"$lte": as_of[:10] + "T23:59:59.9999"}
    bal = 0.0
    async for je in db.journal_entries.find(q, {"_id": 0, "lines": 1}):
        for l in je.get("lines", []):
            if l.get("account_code") in sus:
                bal += float(l.get("debit", 0) or 0) - float(l.get("credit", 0) or 0)
    return round(bal, 2)


async def reclass_suspense(*, amount: float, side: str, target_account: str, note: str,
                           entity_id: str, actor_name: str, date: str = "") -> Dict[str, Any]:
    """F-8 — reklasifikasi saldo suspense ke akun yang benar (JE source suspense_reclass).

    side = posisi saldo suspense SAAT INI yang mau dibersihkan:
    'credit' (kas masuk tak dikenal) → Dr Suspense / Cr target; 'debit' → sebaliknya.

    S4 (pelatihan 18 Nov) — `date` (YYYY-MM-DD, opsional, ≤ hari ini) = tanggal buku jurnal reklas. Dulu selalu hari
    ini: saldo suspense Oktober yang ditemukan awal November direklas ke NOVEMBER, sehingga gerbang tutup buku Oktober
    (K-15, saldo per akhir periode) tetap terblokir. Periode tertutup tetap ditolak `_insert_entry`."""
    from services.book_date import tanggal_buku
    try:
        tgl = tanggal_buku(date or None)
    except ValueError:
        raise ValueError("Tanggal reklasifikasi tidak dikenali (YYYY-MM-DD).")
    if tgl > tanggal_buku():
        raise ValueError("Tanggal reklasifikasi tidak boleh di masa depan.")
    amount = round(float(amount or 0), 2)
    if amount <= 0:
        raise ValueError("Nominal reklasifikasi harus lebih dari 0.")
    if side not in ("debit", "credit"):
        raise ValueError("side harus 'debit' atau 'credit'.")
    if target_account == ACC_SUSPENSE:
        raise ValueError("Akun tujuan tidak boleh akun suspense itu sendiri.")
    acc = await db.gl_accounts.find_one(
        {"code": target_account, "entity_id": {"$in": [None, ""]}}, {"_id": 0})
    if not acc:
        raise ValueError(f"Akun '{target_account}' tidak ditemukan.")
    if not acc.get("is_postable", True):
        raise ValueError(f"Akun '{target_account}' adalah header — pilih akun detail (postable).")
    await assert_no_control_accounts([target_account], entity_id, aksi="reklas_suspense")   # PK-36 (IC-06)
    desc = (note or "").strip() or "Reklasifikasi saldo suspense"
    if side == "credit":
        lines = [{"account_code": ACC_SUSPENSE, "debit": amount, "credit": 0.0, "description": desc},
                 {"account_code": target_account, "debit": 0.0, "credit": amount, "description": desc}]
    else:
        lines = [{"account_code": target_account, "debit": amount, "credit": 0.0, "description": desc},
                 {"account_code": ACC_SUSPENSE, "debit": 0.0, "credit": amount, "description": desc}]
    return await _insert_entry(
        lines=lines, description=f"Reklas suspense → {target_account} · {desc}",
        date=tgl if date else now_iso(), source_type="suspense_reclass", source_id=new_id("reclass"),
        entity_id=entity_id, created_by=actor_name, source_label="Suspense")


async def reverse_order_journals(order_id: str, reason: str = "",
                                 actor_name: str = "system") -> List[Dict[str, Any]]:
    """Gelombang 1 F-1 — jurnal balik otomatis saat order batal/expired (audit trail utuh)."""
    out: List[Dict[str, Any]] = []
    entries = await db.journal_entries.find(
        {"$or": [{"source_id": order_id, "source_type": {"$in": ["sales_order", "sales_cogs"]}},
                 # KEB-PDPT tahap 2 — jurnal per surat jalan & reklas uang muka ikut dibalik
                 {"ref.order_id": order_id,
                  "source_type": {"$in": ["shipment_revenue", "shipment_cogs", "advance_reclass"]}}],
         "status": {"$ne": "void"}}, {"_id": 0}).to_list(200)
    for je in entries:
        rev_type = f"{je['source_type']}_reversal"
        rev_src = order_id if je["source_type"] in ("sales_order", "sales_cogs") else je["source_id"]
        rev, created = await _reverse_once_ex(   # PK-10 — satu jalur pembalik
            je, source_type=rev_type, source_id=rev_src, date=now_iso(),
            description=f"Reversal {je.get('number')} — {reason or 'order dibatalkan'}", created_by=actor_name,
            source_label=je.get("source_label", ""), line_prefix="Reversal:", reason=reason)
        if created:
            out.append(rev)
    return out


async def reverse_document(source_type: str, source_id: str, *, reason: str = "",
                           actor_name: str = "system",
                           extra_source_types: Optional[List[str]] = None,
                           rev_suffix: str = "_reversal",
                           date: str = "") -> List[Dict[str, Any]]:
    """R5.4 — Reversal generik: balik SEMUA JE non-void utk (source_type[+extra], source_id)
    dengan reversing entry (Dr↔Cr). Append-only (JE asal tetap 'posted', ditandai reversed=True)
    agar audit trail utuh. Idempotent per (f'{type}{rev_suffix}', source_id).

    Dipakai R5.4 untuk membatalkan settle retur, redeem/adjust store credit, dll. tanpa
    menghapus data — trial balance otomatis nol (asal + reversal saling meniadakan)."""
    out: List[Dict[str, Any]] = []
    if not source_id:
        return out
    types = [source_type] + list(extra_source_types or [])
    entries = await db.journal_entries.find(
        {"source_id": source_id, "source_type": {"$in": types}, "status": {"$ne": "void"}},
        {"_id": 0}).to_list(50)
    for je in entries:
        rev_type = f"{je['source_type']}{rev_suffix}"
        # PK-10 — satu jalur pembalik; sudah dibalik (oleh mekanisme apa pun) → jurnal pembaliknya dikembalikan.
        rev = await _reverse_once(
            je, source_type=rev_type, source_id=source_id, date=date or now_iso(),
            description=f"Reversal {je.get('number')} — {reason or 'koreksi/pembatalan'}", created_by=actor_name,
            source_label=je.get("source_label", ""), line_prefix="Reversal:", reason=reason)
        if rev and rev not in out:
            out.append(rev)
    return out


async def post_goods_receipt(*, task_id: str, entity_id: str, amount: float,
                             label: str = "", date: str = "", po_id: str = "") -> Optional[Dict[str, Any]]:
    """Gelombang 1 F-3 — GR → GL: Dr Persediaan / Cr GR-IR (barang diterima belum ditagih).
    PK-28 — `po_id` → `ref.po_id` jurnal (sisa GR/IR per PO, `vendor_bill_service.grir_by_po`)."""
    amount = round(float(amount or 0), 2)
    if amount <= EPS or not task_id or await _already_posted("goods_receipt", task_id):
        return None
    await seed_default_coa()
    lines = _balanced_pair(ACC_PERSEDIAAN, ACC_GRIR, amount, f"Penerimaan barang {label}".strip())
    return await _insert_entry(
        lines=lines, description=f"Penerimaan barang {label}".strip(), date=date or now_iso(),
        source_type="goods_receipt", source_id=task_id, entity_id=entity_id,
        created_by="system", source_label=label, ref={"po_id": po_id} if po_id else None)


async def post_grir_clearing(po: Dict[str, Any], clearing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """PK-28 (IV-03) — kliring sisa GR/IR satu PO ke akun selisih harga pembelian (`pembelian.selisih_harga`).

      `direction="debit_grir"`  (sisa kredit, balance > 0) → Dr GR/IR / Cr selisih harga
      `direction="kredit_grir"` (sisa debit,  balance < 0) → Dr selisih harga / Cr GR/IR
    Nominal = `clearing.amount` (positif). Akun GR/IR dan akun selisih dari pemetaan PT PO (`02` P9). Idempoten per
    unsur kliring (`source_id = "<po_id>:<seq>"`). Tanggal = hari kliring (`clearing.at`)."""
    po_id, seq = po.get("id") or "", int(clearing.get("seq") or 0)
    amount = round(float(clearing.get("amount") or 0), 2)
    src = f"{po_id}:{seq}"
    if not po_id or not seq or amount <= EPS or await _already_posted("grir_clearing", src):
        return None
    eid = po.get("entity_id") or DEFAULT_ENTITY_ID
    selisih = await account_for("pembelian.selisih_harga", eid)
    if not selisih:
        raise JournalValidationError('Akun "Selisih harga pembelian" belum diatur untuk PT ini.')
    await seed_default_coa()
    num = po.get("po_number") or po_id
    desc = f"Kliring GR/IR {num} — {clearing.get('reason') or ''}".strip(" —")
    grir = {"account_key": "pembelian.gr_ir", "description": desc}
    lawan = {"account_key": "pembelian.selisih_harga", "description": desc}
    if clearing.get("direction") == "kredit_grir":
        lines = [{**lawan, "debit": amount, "credit": 0.0}, {**grir, "debit": 0.0, "credit": amount}]
    else:
        lines = [{**grir, "debit": amount, "credit": 0.0}, {**lawan, "debit": 0.0, "credit": amount}]
    return await _insert_entry(
        lines=lines, description=f"Kliring GR/IR {num}", date=clearing.get("at") or now_iso(),
        source_type="grir_clearing", source_id=src, entity_id=eid, created_by=clearing.get("by") or "system",
        source_label=f"{num} · kliring {seq}", ref={"po_id": po_id})


# ── M2 (Makloon/Subcon) — WIP-at-vendor postings ─────────────────────────────

async def post_subcon_issue(*, mko_id: str, step_seq: int, entity_id: str,
                            amount: float, label: str = "", date: str = "") -> Optional[Dict[str, Any]]:
    """M2 — Keluarkan bahan KN ke makloon: Dr WIP (1-1350) / Cr Persediaan (1-1300).
    Nilai = WAC bahan yang di-issue. Idempotent per (mko,step)."""
    amount = round(float(amount or 0), 2)
    src = f"{mko_id}:{step_seq}"
    if amount <= EPS or not mko_id or await _already_posted("subcon_issue", src):
        return None
    await seed_default_coa()
    lines = _balanced_pair(ACC_WIP_SUBCON, ACC_PERSEDIAAN, amount,
                           f"Issue bahan ke makloon {label}".strip())
    return await _insert_entry(
        lines=lines, description=f"Subcon Issue {label}".strip(), date=date or now_iso(),
        source_type="subcon_issue", source_id=src, entity_id=entity_id,
        created_by="system", source_label=label)


async def post_subcon_service(*, bill_id: str, mko_id: str, step_seq: int, entity_id: str,
                              net_amount: float, ppn: float = 0.0, grand_total: float = 0.0,
                              makloon_name: str = "", label: str = "", date: str = "",
                              ap_mode: str = "") -> Optional[Dict[str, Any]]:
    """M2 — Tagihan JASA makloon (posted): Dr WIP (net) + Dr PPN Masukan / Cr Hutang Usaha.
    Ongkos jasa+bahan pembantu ditambahkan ke WIP (biaya konversi). Idempotent per bill.

    MP-T4b (K-78) — `ap_mode="saat_faktur"`: jasa diterima belum ditagih → Dr WIP / Cr GR/IR 2-1150 sebesar nilai jasa
    (tanpa PPN); hutang lahir di `post_subcon_service_invoice` saat faktur mitra dicocokkan."""
    net_amount = round(float(net_amount or 0), 2)
    ppn = round(float(ppn or 0), 2)
    grand = round(float(grand_total or (net_amount + ppn)), 2)
    if ap_mode == "saat_faktur":
        if net_amount <= EPS or not bill_id or await _already_posted("subcon_service", bill_id):
            return None
        await seed_default_coa()
        lines = _balanced_pair(ACC_WIP_SUBCON, ACC_GRIR, net_amount,
                               f"Jasa makloon diterima, faktur belum dicocokkan {label}".strip())
        return await _insert_entry(
            lines=lines, description=f"Jasa Makloon Diterima {label}".strip(), date=date or now_iso(),
            source_type="subcon_service", source_id=bill_id, entity_id=entity_id,
            created_by="system", source_label=label, ref={"grir_mko_id": mko_id, "vendor_bill_id": bill_id})
    if grand <= EPS or not bill_id or await _already_posted("subcon_service", bill_id):
        return None
    await seed_default_coa()
    lines: List[Dict[str, Any]] = [
        {"account_code": ACC_WIP_SUBCON, "debit": net_amount, "credit": 0.0,
         "description": f"Ongkos makloon {label}".strip()}]
    if ppn > EPS:
        lines.append({"account_code": ACC_PPN_IN, "debit": ppn, "credit": 0.0,
                      "description": f"PPN Masukan jasa makloon {label}".strip()})
    diff = round(grand - net_amount - (ppn if ppn > EPS else 0), 2)
    if abs(diff) > EPS:
        acc = ACC_SUSPENSE
        if diff > 0:
            lines.append({"account_code": acc, "debit": diff, "credit": 0.0, "description": "Selisih pembulatan"})
        else:
            lines.append({"account_code": acc, "debit": 0.0, "credit": -diff, "description": "Selisih pembulatan"})
    lines.append({"account_code": ACC_HUTANG, "debit": 0.0, "credit": grand,
                  "description": f"Hutang jasa makloon — {makloon_name}".strip()})
    return await _insert_entry(
        lines=lines, description=f"Tagihan Jasa Makloon {label}".strip(), date=date or now_iso(),
        source_type="subcon_service", source_id=bill_id, entity_id=entity_id,
        created_by="system", source_label=label)


async def post_subcon_service_invoice(*, bill_id: str, entity_id: str, net_amount: float, ppn: float = 0.0,
                                      makloon_name: str = "", label: str = "", invoice_no: str = "",
                                      date: str = "", mko_id: str = "") -> Optional[Dict[str, Any]]:
    """MP-T4b (K-63, K-78) — faktur mitra makloon dicocokkan: Dr GR/IR 2-1150 (nilai jasa) + Dr PPN Masukan 1-1500 /
    Cr Hutang Usaha 2-1100 (total faktur). Idempoten per tagihan. `ref.grir_mko_id` = SPK (GR/IR per SPK)."""
    net_amount = round(float(net_amount or 0), 2)
    ppn = round(float(ppn or 0), 2)
    grand = round(net_amount + ppn, 2)
    if grand <= EPS or not bill_id or await _already_posted("subcon_service_invoice", bill_id):
        return None
    await seed_default_coa()
    lines: List[Dict[str, Any]] = [
        {"account_code": ACC_GRIR, "debit": net_amount, "credit": 0.0,
         "description": f"Kliring jasa makloon {label}".strip()}]
    if ppn > EPS:
        lines.append({"account_code": ACC_PPN_IN, "debit": ppn, "credit": 0.0,
                      "description": f"PPN Masukan jasa makloon {invoice_no}".strip()})
    lines.append({"account_code": ACC_HUTANG, "debit": 0.0, "credit": grand,
                  "description": f"Hutang jasa makloon — {makloon_name} {invoice_no}".strip()})
    return await _insert_entry(
        lines=lines, description=f"Faktur Jasa Makloon {invoice_no} {label}".strip(), date=date or now_iso(),
        source_type="subcon_service_invoice", source_id=bill_id, entity_id=entity_id,
        created_by="system", source_label=label, ref={"grir_mko_id": mko_id, "vendor_bill_id": bill_id})


async def post_subcon_receipt(*, mko_id: str, step_seq: int, entity_id: str,
                              amount: float, label: str = "", date: str = "") -> Optional[Dict[str, Any]]:
    """M2 — Terima output makloon: Dr Persediaan (1-1300) / Cr WIP (1-1350).
    `amount` = total nilai WIP yang di-clear (material + jasa + aux) → jadi HPP output.
    Byproduct/barang sisa dinilai 0 (metode conservative) → tak menambah 1-1300 di luar
    subledger (anti-drift). Idempotent per (mko,step)."""
    amount = round(float(amount or 0), 2)
    src = f"{mko_id}:{step_seq}"
    if amount <= EPS or not mko_id or await _already_posted("subcon_receipt", src):
        return None
    await seed_default_coa()
    lines = _balanced_pair(ACC_PERSEDIAAN, ACC_WIP_SUBCON, amount,
                           f"Terima output makloon {label}".strip())
    return await _insert_entry(
        lines=lines, description=f"Subcon Receipt {label}".strip(), date=date or now_iso(),
        source_type="subcon_receipt", source_id=src, entity_id=entity_id,
        created_by="system", source_label=label)


async def post_subcon_service_unabsorbed(*, mko_id: str, entity_id: str, amount: float,
                                        label: str = "", date: str = "") -> Optional[Dict[str, Any]]:
    """FASE T — bersihkan WIP jasa "jasa murni" yang tak menempel ke kain mana pun.

    Langkah ber-`material_flow="service_only"` (mis. pembuatan kasa/screen) tidak
    memindahkan kain, jadi tidak ada penerimaan roll yang meng-clear WIP-nya.
    Biayanya **diserap langkah kain berikutnya** di SPK yang sama (`receive_step`
    menambahkannya ke `wip_total`). Bila SPK habis tanpa langkah kain — mis. SPK
    berisi Screen saja — sisanya WAJIB keluar dari WIP, kalau tidak saldo 1-1350
    membesar tanpa penjelasan dan `verify_data_integrity` akan melaporkan drift
    yang tak ada pemiliknya.

        Dr 5-1200 Beban Jasa Makloon Tak Terserap / Cr 1-1350 WIP Makloon

    Idempotent per order (satu SPK = satu pembersihan).
    """
    amount = round(float(amount or 0), 2)
    src = f"{mko_id}:service_unabsorbed"
    if amount <= EPS or not mko_id or await _already_posted("subcon_service_unabsorbed", src):
        return None
    await seed_default_coa()
    lines = _balanced_pair(ACC_JASA_TAK_TERSERAP, ACC_WIP_SUBCON, amount,
                           f"Jasa makloon tanpa kain penyerap {label}".strip())
    return await _insert_entry(
        lines=lines, description=f"Jasa Makloon Tak Terserap {label}".strip(),
        date=date or now_iso(), source_type="subcon_service_unabsorbed", source_id=src,
        entity_id=entity_id, created_by="system", source_label=label)


async def post_makloon_claim(*, mko_id: str, step_seq: int, entity_id: str, action: str,
                             amount: float, label: str = "", date: str = "",
                             split: Optional[Dict[str, Any]] = None,
                             debit_account: str = "") -> Optional[Dict[str, Any]]:
    """FASE D (PS-11 · D-09) — jurnal konsekuensi selisih makloon. Idempotent per (mko,step).

    * `potong_bon`  → Dr Hutang Usaha (2-1100) / Cr Pendapatan Klaim Makloon (4-9200):
      tagihan jasa mitra dipotong; utang berkurang, subledger vendor_bill ikut dikurangi
      oleh `makloon_claim_service` sehingga AP tetap rekonsiliasi.
    * `tagih_ganti` → Dr Piutang Klaim Mitra (1-1260) / Cr Pendapatan Klaim Makloon (4-9200).
    * `terima_catatan` → TIDAK ada jurnal: kerugian sudah terserap ke HPP output saat
      penerimaan (WIP di-clear penuh ke persediaan) — mencegah dobel-hitung & drift 1-1300.
    """
    amount = round(float(amount or 0), 2)
    src = f"{mko_id}:{step_seq}"
    if action == "terima_catatan":
        return None
    if amount <= EPS or not mko_id or await _already_posted("makloon_claim", src):
        return None
    if action == "potong_bon":
        debit, credit = ACC_HUTANG, ACC_KLAIM_MAKLOON
        desc = f"Potong bon klaim makloon {label}".strip()
    elif action == "tagih_ganti":
        debit, credit = ACC_PIUTANG_KLAIM, ACC_KLAIM_MAKLOON
        desc = f"Tagih ganti rugi mitra makloon {label}".strip()
    else:
        return None
    await seed_default_coa()
    if split is not None:
        # MP-T4b (K-64, K-79) — hasil klaim per keadaan roll hasil: stok → Cr Persediaan, WIP mitra → Cr WIP,
        # sudah keluar → Cr Pendapatan Klaim. Debit potong bon = 2-1150 bila faktur belum dicocokkan (`debit_account`).
        lines = [{"account_code": debit_account or debit, "debit": amount, "credit": 0.0, "description": desc}]
        for acc, key, ket in ((ACC_PERSEDIAAN, "inventory_amount", "pengurang biaya roll di stok"),
                              (ACC_WIP_SUBCON, "wip_amount", "pengurang biaya roll di mitra"),
                              (ACC_KLAIM_MAKLOON, "income_amount", "bagian hasil yang sudah keluar")):
            v = round(float(split.get(key) or 0), 2)
            if v > EPS:
                lines.append({"account_code": acc, "debit": 0.0, "credit": v, "description": f"{desc} — {ket}"})
        selisih = round(amount - sum(ln["credit"] for ln in lines), 2)
        if abs(selisih) > EPS:   # sisa sen pembulatan ke pendapatan klaim
            lines.append({"account_code": ACC_KLAIM_MAKLOON, "debit": 0.0 if selisih > 0 else -selisih,
                          "credit": selisih if selisih > 0 else 0.0, "description": "Selisih pembulatan klaim"})
        return await _insert_entry(
            lines=lines, description=desc, date=date or now_iso(),
            source_type="makloon_claim", source_id=src, entity_id=entity_id,
            created_by="system", source_label=label,
            ref={"grir_mko_id": mko_id} if debit_account == ACC_GRIR else None)
    lines = _balanced_pair(debit, credit, amount, desc)
    return await _insert_entry(
        lines=lines, description=desc, date=date or now_iso(),
        source_type="makloon_claim", source_id=src, entity_id=entity_id,
        created_by="system", source_label=label)


async def post_contra_bon_deduction(*, cb_id: str, deduction_id: str, entity_id: str,
                                    kind: str, amount: float, label: str = "",
                                    date: str = "", dry_run: bool = False) -> Optional[Dict[str, Any]]:
    """FASE G-7 — jurnal POTONGAN kontrabon. Idempotent per (kontrabon, potongan).

    Lawan akun per jenis potongan:
      * `supplier_advance` → Dr 2-1100 Hutang / Cr 1-1400 Uang Muka (aset dipakai)
      * `supplier_penalty` → Dr 2-1100 Hutang / Cr 4-9300 Pendapatan Denda
      * `match_variance`   → Dr 2-1100 Hutang / Cr 2-1150 GR/IR (barangnya memang tak diterima)
      * `other_agreed`     → Dr 2-1100 Hutang / Cr 4-9000 Pendapatan Lain-lain

    **`purchase_return` SENGAJA TIDAK ADA di sini.** Retur beli `ap_credit` sudah
    memposting `Dr 2-1100 / Cr 1-1300` saat retur disetujui; menjurnalnya lagi akan
    mengurangi Hutang DUA KALI. Di kontrabon ia hanya diterapkan sebagai pelunasan
    non-kas pada subledger `vendor_bills` — justru itu yang menutup drift GL↔subledger.
    """
    credit_by_kind = {
        "supplier_advance": ACC_UANG_MUKA,
        "supplier_penalty": ACC_PENDAPATAN_DENDA,
        "match_variance": ACC_GRIR,
        "other_agreed": ACC_PENDAPATAN_LAIN,
    }
    credit = credit_by_kind.get(kind)
    amount = round(float(amount or 0), 2)
    src = f"{cb_id}:{deduction_id}"
    if not credit or amount <= EPS or await _already_posted("contra_bon_deduction", src):
        return None
    desc = f"Potongan kontrabon {label}".strip()
    lines = _balanced_pair(ACC_HUTANG, credit, amount, desc)
    if dry_run:   # PK-05 — langkah PERIKSA: validasi tanpa menulis
        await preflight_entry(lines=lines, entity_id=entity_id, date=date or now_iso(),
                              source_type="contra_bon_deduction")
        return None
    await seed_default_coa()
    return await _insert_entry(
        lines=lines, description=desc, date=date or now_iso(),
        source_type="contra_bon_deduction", source_id=src, entity_id=entity_id,
        created_by="system", source_label=label)


async def post_production_output(*, wo_id: str, entity_id: str, overhead: float,
                                 label: str = "", date: str = "") -> Optional[Dict[str, Any]]:
    """R6.4 — Produksi in-house: kapitalisasi OVERHEAD ke Persediaan Barang Jadi.
    Transformasi bahan→barang jadi memakai akun Persediaan 1-1300 yang sama (raw==FG),
    sehingga porsi bahan NET-0 di GL (subledger roll sudah menyeimbangkan). Hanya OVERHEAD
    yang menambah nilai persediaan: Dr 1-1300 / Cr 5-1100 (Overhead Diserap). Idempotent per WO.
    Bila overhead<=0 → tak ada jurnal (GL-3 tetap konsisten dari transformasi roll)."""
    overhead = round(float(overhead or 0), 2)
    if overhead <= EPS or not wo_id or await _already_posted("production_output", wo_id):
        return None
    await seed_default_coa()
    lines = _balanced_pair(ACC_PERSEDIAAN, ACC_OVERHEAD_APPLIED, overhead,
                           f"Kapitalisasi overhead produksi {label}".strip())
    return await _insert_entry(
        lines=lines, description=f"Produksi WO {label}".strip(), date=date or now_iso(),
        source_type="production_output", source_id=wo_id, entity_id=entity_id,
        created_by="system", source_label=label)


async def post_makloon_material_loss(*, mko_id: str, step_seq: int, part: str, entity_id: str,
                                     expense: float, claim: float, label: str = "",
                                     claim_account: str = "", grir_mko_id: str = "") -> Optional[Dict[str, Any]]:
    """L01 — susut/hilang bahan di mitra (MKO batal): Dr 5-9500 (dalam toleransi) + Dr 1-1260
    Piutang Klaim Mitra (di atas toleransi, sesudah disetujui) / Cr 1-1350 WIP. Idempotent per catatan.
    Potong tagihan jasa: Dr Hutang 2-1100, atau (MP-T4b K-82) Dr GR/IR 2-1150 bila tagihan itu masih menunggu faktur
    mitra — `grir_mko_id` = SPK pemilik tagihan (GR/IR per SPK)."""
    expense, claim = round(float(expense or 0), 2), round(float(claim or 0), 2)
    total = round(expense + claim, 2)
    src = f"{mko_id}:{step_seq}:{part}"
    if total <= EPS or await _already_posted("makloon_material_loss", src):
        return None
    await seed_default_coa()
    lines = []
    if expense > EPS:
        lines.append({"account_code": ACC_WRITEOFF, "debit": expense, "credit": 0.0,
                      "description": f"Susut wajar bahan di mitra {label}"})
    if claim > EPS:
        deduct = claim_account in (ACC_HUTANG, ACC_GRIR)
        lines.append({"account_code": claim_account if deduct else ACC_PIUTANG_KLAIM, "debit": claim, "credit": 0.0,
                      "description": (f"Potong tagihan jasa mitra atas susut di atas toleransi {label}" if deduct
                                      else f"Klaim mitra atas susut di atas toleransi {label}")})
    lines.append({"account_code": ACC_WIP_SUBCON, "debit": 0.0, "credit": total,
                  "description": f"Bahan hilang/susut di mitra {label}"})
    return await _insert_entry(lines=lines, description=f"Susut bahan di mitra {label}".strip(), date=now_iso(),
                               source_type="makloon_material_loss", source_id=src, entity_id=entity_id,
                               created_by="system", source_label=label,
                               ref={"grir_mko_id": grir_mko_id} if claim_account == ACC_GRIR and grir_mko_id else None)


async def reverse_subcon_issue(*, mko_id: str, step_seq: int, entity_id: str,
                               amount: float, label: str = "", part: str = "") -> Optional[Dict[str, Any]]:
    """M2 — Batalkan issue bahan (step belum diterima): Dr Persediaan / Cr WIP.
    Mengembalikan nilai WIP ke Persediaan saat order/step dibatalkan. Idempotent."""
    amount = round(float(amount or 0), 2)
    src = f"{mko_id}:{step_seq}" + (f":{part}" if part else "")
    if amount <= EPS or not mko_id or await _already_posted("subcon_issue_reversal", src):
        return None
    await seed_default_coa()
    lines = _balanced_pair(ACC_PERSEDIAAN, ACC_WIP_SUBCON, amount,
                           f"Batal issue makloon {label}".strip())
    return await _insert_entry(
        lines=lines, description=f"Subcon Issue Reversal {label}".strip(), date=now_iso(),
        source_type="subcon_issue_reversal", source_id=src, entity_id=entity_id,
        created_by="system", source_label=label)


async def post_vendor_bill(bill: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Gelombang 1 F-5 — Vendor Bill posted → Dr GR-IR + Dr PPN Masukan / Cr Hutang Usaha.

    PK-28 (IV-03) — faktur ber-PO yang menyimpan `grir_amount` (Σ qty tagih × harga neto baris PO) dan
    `price_variance_amount` (neto faktur − `grir_amount`): GR/IR dihapus sebesar `grir_amount`, selisihnya ke akun
    `pembelian.selisih_harga` (selisih > 0 debit, < 0 kredit) — bila akun itu terpetakan untuk PT faktur; jurnal yang
    memuat selisih menandai `price_variance_posted=true`. Akun belum terpetakan, faktur lama tanpa `grir_amount`, atau
    selisih ≤ 0,005 → perilaku lama (Dr GR/IR sebesar neto). `ref.po_id` diisi untuk faktur ber-PO."""
    bid = bill.get("id")
    if not bid or bill.get("status") not in ("posted", "paid"):
        return None
    # F-03 (audit 2026-09-02) — tagihan JASA makloon sudah berjurnal lewat
    # `post_subcon_service` (Dr WIP / Cr Hutang); memposting lagi = Hutang dobel.
    if bill.get("bill_type") == "makloon_service":
        return None
    if await _already_posted("vendor_bill", bid) or await any_posting_for(bid):
        return None
    grand = round(float(bill.get("grand_total", bill.get("total_amount", 0)) or 0), 2)
    if grand <= EPS:
        return None
    await seed_default_coa()
    ppn = round(float(bill.get("ppn_amount", 0) or 0), 2)
    # F-10 — basis biaya/GRIR = harga beli neto (grand − PPN), BUKAN DPP Nilai Lain (11/12)
    net = round(grand - ppn, 2)
    num = bill.get("bill_number", bid)
    # COMM-04 lanjutan — tagihan vendor kampanye (tanpa PO): Dr Beban Pemasaran, bukan GR-IR.
    is_campaign = bill.get("bill_type") == "campaign_expense"
    debit_acc = (bill.get("expense_account_code") or ACC_BEBAN_PEMASARAN) if is_campaign else ACC_GRIR
    variance = round(float(bill.get("price_variance_amount") or 0), 2)
    split = (not is_campaign and bill.get("grir_amount") is not None and abs(variance) > 0.005
             and bool(await account_for("pembelian.selisih_harga", bill.get("entity_id") or None)))
    selisih_desc = f"Selisih harga terhadap PO {bill.get('po_number') or ''} — {num}".replace("  ", " ")
    lines: List[Dict[str, Any]] = [
        {"account_code": debit_acc, "debit": round(float(bill["grir_amount"]), 2) if split else net, "credit": 0.0,
         "description": (f"Biaya kampanye {bill.get('campaign_name', '')} {num}" if is_campaign
                         else f"Tagihan supplier {num}")}]
    if split and variance > 0:
        lines.append({"account_key": "pembelian.selisih_harga", "debit": variance, "credit": 0.0,
                      "description": selisih_desc})
    if ppn > EPS:
        lines.append({"account_code": ACC_PPN_IN, "debit": ppn, "credit": 0.0,
                      "description": f"PPN Masukan {num}"})
    if split and variance < 0:
        lines.append({"account_key": "pembelian.selisih_harga", "debit": 0.0, "credit": -variance,
                      "description": selisih_desc})
    diff = round(grand - sum(float(ln["debit"]) for ln in lines) + sum(float(ln["credit"]) for ln in lines), 2)
    if abs(diff) > EPS:
        if diff > 0:
            lines.append({"account_code": ACC_SUSPENSE, "debit": diff, "credit": 0.0,
                          "description": "Selisih pembulatan"})
        else:
            lines.append({"account_code": ACC_SUSPENSE, "debit": 0.0, "credit": -diff,
                          "description": "Selisih pembulatan"})
    lines.append({"account_code": ACC_HUTANG, "debit": 0.0, "credit": grand,
                  "description": f"Hutang usaha {num} — {bill.get('supplier_name', '')}".strip()})
    je = await _insert_entry(
        lines=lines, description=f"Tagihan pemasok {num}",
        date=bill.get("posted_at") or bill.get("bill_date") or now_iso(),
        source_type="vendor_bill", source_id=bid, entity_id=bill.get("entity_id", ""),
        created_by="system", source_label=num, ref={"po_id": bill["po_id"]} if bill.get("po_id") else None)
    if split:   # PK-28 — selisih sudah pindah dari GR/IR ke akun selisih harga
        await db.vendor_bills.update_one({"id": bid}, {"$set": {"price_variance_posted": True}})
    return je


async def reverse_vendor_bill(bill: Dict[str, Any], reason: str = "",
                              actor_name: str = "system") -> Optional[Dict[str, Any]]:
    """Session #074 (VB-CANCEL-GL) — balik jurnal Vendor Bill saat bill posted dibatalkan.
    Idempotent (source_type='vendor_bill_reversal'). Membalik Dr↔Cr dari JE vendor_bill."""
    bid = bill.get("id")
    if not bid:
        return None
    je = await db.journal_entries.find_one(
        {"source_type": "vendor_bill", "source_id": bid, "status": {"$ne": "void"}}, {"_id": 0})
    if not je:
        return None
    rev, created = await _reverse_once_ex(   # PK-10 — satu jalur pembalik
        je, source_type="vendor_bill_reversal", source_id=bid, date=now_iso(),
        description=f"Reversal {je.get('number')} — {reason or 'bill dibatalkan'}", created_by=actor_name,
        source_label=je.get("source_label", ""), line_prefix="Reversal:", reason=reason)
    return rev if created else None

async def post_cycle_count_variance(*, source_id: str, entity_id: str, amount_signed: float,
                                    label: str = "") -> Optional[Dict[str, Any]]:
    """FN-14 — selisih stock opname per baris hitung (idempoten per source_id = sesi:baris).
      amount_signed < 0 (kurang) → Dr 5-9500 Beban Kerugian Persediaan / Cr 1-1300 Persediaan.
      amount_signed > 0 (lebih)  → Dr 1-1300 Persediaan / Cr 4-9000 Pendapatan Lain-lain."""
    amount = round(abs(float(amount_signed or 0)), 2)
    if not source_id or amount <= EPS or await _already_posted("cycle_count_variance", source_id):
        return None
    await seed_default_coa()
    lbl = label or source_id
    if amount_signed < 0:
        lines = [{"account_code": ACC_WRITEOFF, "debit": amount, "credit": 0.0, "description": f"Selisih kurang {lbl}"},
                 {"account_code": ACC_PERSEDIAAN, "debit": 0.0, "credit": amount, "description": f"Susut opname {lbl}"}]
    else:
        lines = [{"account_code": ACC_PERSEDIAAN, "debit": amount, "credit": 0.0, "description": f"Surplus opname {lbl}"},
                 {"account_code": ACC_PENDAPATAN_LAIN, "debit": 0.0, "credit": amount, "description": f"Selisih lebih {lbl}"}]
    return await _insert_entry(lines=lines, description=f"Selisih stock opname {lbl}", date=now_iso(),
                               source_type="cycle_count_variance", source_id=source_id, entity_id=entity_id or "",
                               created_by="system", source_label=lbl)


async def post_inventory_writeoff(*, roll_id: str, entity_id: str, amount: float,
                                  reason: str = "", label: str = "",
                                  date: str = "", source_id: str = "") -> Optional[Dict[str, Any]]:
    """R5.1 — Write-off / penghapusan persediaan (scrap & goods) → GL.
      Dr 5-9500 Beban Kerugian/Penghapusan Persediaan / Cr 1-1300 Persediaan.
    Dipanggil saat roll keluar dari subledger fisik menjadi 'damaged' (scrap) tanpa
    lawan-akun lain, agar GL 1-1300 turun sejalan subledger (anti INV-GL-DRIFT).
    Idempotent (source_type='inventory_writeoff', source_id=roll_id by default).
    `amount` = length_remaining * unit_cost roll yang di-scrap."""
    amount = round(float(amount or 0), 2)
    sid = source_id or roll_id
    if not sid or amount <= EPS or await _already_posted("inventory_writeoff", sid):
        return None
    await seed_default_coa()
    lbl = label or roll_id or sid
    rtxt = f" · {reason}" if reason else ""
    lines = [
        {"account_code": ACC_WRITEOFF, "debit": amount, "credit": 0.0,
         "description": f"Write-off persediaan {lbl}{rtxt}"},
        {"account_code": ACC_PERSEDIAAN, "debit": 0.0, "credit": amount,
         "description": f"Penghapusan stok {lbl}"},
    ]
    return await _insert_entry(
        lines=lines, description=f"Write-off persediaan {lbl}",
        date=date or now_iso(), source_type="inventory_writeoff",
        source_id=sid, entity_id=entity_id or "", created_by="system", source_label=lbl)


async def post_return_grade_impairment(*, source_id: str, entity_id: str, amount: float,
                                       label: str = "", date: str = "") -> Optional[Dict[str, Any]]:
    """LN-091-T02 — penurunan nilai roll retur yang turun grade (terpisah dari kredit pelanggan).
      Dr 5-9500 Beban Kerugian Persediaan / Cr 1-1300 Persediaan. Idempotent per source_id."""
    amount = round(float(amount or 0), 2)
    if not source_id or amount <= EPS or await _already_posted("return_grade_impairment", source_id):
        return None
    await seed_default_coa()
    lines = [
        {"account_code": ACC_WRITEOFF, "debit": amount, "credit": 0.0,
         "description": f"Kerugian turun grade {label}"},
        {"account_code": ACC_PERSEDIAAN, "debit": 0.0, "credit": amount,
         "description": f"Penurunan nilai persediaan {label}"},
    ]
    return await _insert_entry(
        lines=lines, description=f"Kerugian turun grade {label}", date=date or now_iso(),
        source_type="return_grade_impairment", source_id=source_id, entity_id=entity_id or "",
        created_by="system", source_label=label)


async def post_sample_material_issue(*, movement_id: str, entity_id: str, amount: float,
                                     label: str = "", note: str = "",
                                     date: str = "",
                                     created_by: str = "system") -> Optional[Dict[str, Any]]:
    """FASE F — Bahan yang dipakai MEMBUAT SAMPLE keluar dari persediaan → GL.
      Dr 6-7000 Beban Sample & Pengembangan (R&D) / Cr 1-1300 Persediaan.

    Tanpa jurnal ini nilai persediaan turun di subledger (roll berkurang) tetapi GL
    1-1300 tidak — memunculkan drift INV-GL-DRIFT (uang "hilang" tanpa jejak beban).
    Idempotent per `movement_id` (source_type='rnd_sample_issue')."""
    amount = round(float(amount or 0), 2)
    if not movement_id or amount <= EPS or await _already_posted("rnd_sample_issue", movement_id):
        return None
    await seed_default_coa()
    lbl = label or movement_id
    ntxt = f" · {note}" if note else ""
    lines = [
        {"account_code": ACC_BEBAN_RND, "debit": amount, "credit": 0.0,
         "description": f"Bahan sample {lbl}{ntxt}"},
        {"account_code": ACC_PERSEDIAAN, "debit": 0.0, "credit": amount,
         "description": f"Bahan keluar gudang untuk sample {lbl}"},
    ]
    return await _insert_entry(
        lines=lines, description=f"Pengambilan bahan sample {lbl}",
        date=date or now_iso(), source_type="rnd_sample_issue",
        source_id=movement_id, entity_id=entity_id or "", created_by=created_by or "system",
        source_label=lbl)


async def post_penalty_issue(*, penalty_id: str, entity_id: str, amount: float,
                             label: str = "", date: str = "",
                             created_by: str = "system") -> Optional[Dict[str, Any]]:
    """FASE G-2 — Terbitkan denda keterlambatan:
      Dr 1-1270 Piutang Denda Pelanggan / Cr 4-9300 Pendapatan Denda Keterlambatan.

    Denda berstatus `draft` SENGAJA tidak pernah lewat sini (INV-PEN-01): itulah yang
    membuat denda bisa dinegosiasikan tanpa mengotori buku besar. Idempotent per
    (`penalty`, penalty_id).
    """
    amount = round(float(amount or 0), 2)
    if not penalty_id or amount <= EPS or await _already_posted("penalty", penalty_id):
        return None
    await seed_default_coa()
    lbl = label or penalty_id
    lines = _balanced_pair(ACC_PIUTANG_DENDA, ACC_PENDAPATAN_DENDA, amount,
                           f"Denda keterlambatan {lbl}")
    return await _insert_entry(
        lines=lines, description=f"Denda keterlambatan {lbl}", date=date or now_iso(),
        source_type="penalty", source_id=penalty_id, entity_id=entity_id or "",
        created_by=created_by, source_label=lbl)


async def post_penalty_reversal(*, penalty_id: str, entity_id: str, amount: float,
                                label: str = "", date: str = "", created_by: str = "system",
                                suffix: str = "waive") -> Optional[Dict[str, Any]]:
    """FASE G-2 — Pembebasan / penyesuaian denda yang SUDAH terbit → jurnal PEMBALIK:
      Dr 4-9300 Pendapatan Denda / Cr 1-1270 Piutang Denda.

    Ledger append-only (aturan repo #7): jurnal lama TIDAK diubah/dihapus; koreksi
    selalu berupa jurnal baru yang bisa dibaca auditor. `suffix` memisahkan pembebasan
    dari penyesuaian sehingga keduanya bisa terjadi berurutan tanpa saling menimpa.
    """
    amount = round(float(amount or 0), 2)
    sid = f"{penalty_id}:{suffix}"
    if not penalty_id or amount <= EPS or await _already_posted("penalty_reversal", sid):
        return None
    await seed_default_coa()
    lbl = label or penalty_id
    lines = _balanced_pair(ACC_PENDAPATAN_DENDA, ACC_PIUTANG_DENDA, amount, lbl)
    return await _insert_entry(
        lines=lines, description=lbl, date=date or now_iso(),
        source_type="penalty_reversal", source_id=sid, entity_id=entity_id or "",
        created_by=created_by, source_label=penalty_id)


async def post_penalty_payment(*, penalty_id: str, entity_id: str, amount: float,
                               method: str = "transfer", label: str = "", date: str = "",
                               created_by: str = "system") -> Optional[Dict[str, Any]]:
    """USANG (PK-08) — tidak dipanggil kode aplikasi lagi: bayar denda kini lewat dokumen kas `cash_pnl_<id>`
    (`penalty_service.pay` → `post_cash_durable`). Kuncinya tetap `<id nota>:pay`, jadi pembayaran KEDUA dulu
    dilewati diam-diam (FX-02). Dibiarkan untuk jurnal lama.

    FASE G-2 — Pembayaran denda oleh pelanggan:
      Dr Kas/Bank (atau Kas Kecil untuk tunai) / Cr 1-1270 Piutang Denda.
    """
    amount = round(float(amount or 0), 2)
    sid = f"{penalty_id}:pay"
    if not penalty_id or amount <= EPS or await _already_posted("penalty_payment", sid):
        return None
    await seed_default_coa()
    from services.payment_method_service import is_cash   # PM-T1 — satu pembeda tunai
    # Kas & Bank 1 — tanpa dokumen kas / rekening → akun jenis kas lama (satu pembantu `akun_kas`)
    jenis = "kas_kecil" if await is_cash(entity_id or "", method) else "kas_besar"
    cash_acc = await akun_kas(entity_id or "", "", jenis)
    lbl = label or f"Pembayaran denda {penalty_id}"
    lines = _balanced_pair(cash_acc, ACC_PIUTANG_DENDA, amount, lbl)
    return await _insert_entry(
        lines=lines, description=lbl, date=date or now_iso(),
        source_type="penalty_payment", source_id=sid, entity_id=entity_id or "",
        created_by=created_by, source_label=penalty_id)


async def penalty_receivable_balance(entity_id: str = "") -> float:
    """Saldo akun 1-1270 (Piutang Denda) dari jurnal — bahan INV-PEN-03."""
    codes = await _known("penjualan.piutang_denda")
    flt: Dict[str, Any] = {"status": {"$ne": "void"}, "lines.account_code": {"$in": codes}}
    if entity_id and entity_id != "all":
        flt["entity_id"] = entity_id
    total = 0.0
    async for je in db.journal_entries.find(flt, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") in codes:
                total += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(total, 2)


# ── FASE G-3 — Selisih pembayaran (lebih / kurang bayar) ────────────────────
async def post_variance_writeoff(*, decision_id: str, entity_id: str, amount: float,
                                 label: str = "", date: str = "",
                                 created_by: str = "system") -> Optional[Dict[str, Any]]:
    """FASE G-3 — Sisa KURANG bayar yang diputus dihapus (termasuk pembulatan otomatis):
      Dr 6-9100 Beban Selisih Pembayaran Pelanggan / Cr 1-1200 Piutang Usaha.

    Piutangnya benar-benar hilang dari buku (bukan hanya ditandai lunas di dokumen),
    sehingga subledger pesanan dan saldo Piutang di GL tetap bercerita sama.
    Idempotent per (`payment_variance_writeoff`, decision_id).
    """
    amount = round(float(amount or 0), 2)
    if not decision_id or amount <= EPS or await _already_posted(
            "payment_variance_writeoff", decision_id):
        return None
    await seed_default_coa()
    lbl = label or decision_id
    lines = _balanced_pair(ACC_SELISIH_BAYAR, ACC_PIUTANG, amount,
                           f"Selisih kurang bayar {lbl}")
    return await _insert_entry(
        lines=lines, description=f"Selisih kurang bayar dihapus · {lbl}",
        date=date or now_iso(), source_type="payment_variance_writeoff",
        source_id=decision_id, entity_id=entity_id or "", created_by=created_by,
        source_label=lbl)


async def post_ap_variance_writeoff(*, decision_id: str, entity_id: str, amount: float,
                                    label: str = "", date: str = "",
                                    created_by: str = "system") -> Optional[Dict[str, Any]]:
    """FASE G-3 (jalur AP) — Sisa hutang supplier yang diputus tidak dibayar:
      Dr 2-1100 Hutang Usaha / Cr 4-9000 Pendapatan Lain-lain (potongan dari supplier).

    Idempotent per (`ap_variance_writeoff`, decision_id).
    """
    amount = round(float(amount or 0), 2)
    if not decision_id or amount <= EPS or await _already_posted(
            "ap_variance_writeoff", decision_id):
        return None
    await seed_default_coa()
    lbl = label or decision_id
    lines = _balanced_pair(ACC_HUTANG, ACC_PENDAPATAN_LAIN, amount,
                           f"Selisih pembayaran supplier {lbl}")
    return await _insert_entry(
        lines=lines, description=f"Selisih hutang supplier ditutup · {lbl}",
        date=date or now_iso(), source_type="ap_variance_writeoff",
        source_id=decision_id, entity_id=entity_id or "", created_by=created_by,
        source_label=lbl)


async def post_variance_reallocation(*, decision_id: str, entity_id: str, amount: float,
                                    label: str = "", date: str = "",
                                    created_by: str = "system") -> Optional[Dict[str, Any]]:
    """FASE G-3 — Kelebihan bayar dipakai melunasi pesanan LAIN:
      Dr 2-1400 Uang Muka Pelanggan / Cr 1-1200 Piutang Usaha.

    Kwitansi aslinya tidak diubah (append-only): uang yang tadi jadi kewajiban kami
    sekarang menutup piutang lain, dan perpindahannya punya jurnal sendiri.
    Idempotent per (`payment_variance_alloc`, decision_id).
    """
    amount = round(float(amount or 0), 2)
    if not decision_id or amount <= EPS or await _already_posted(
            "payment_variance_alloc", decision_id):
        return None
    await seed_default_coa()
    lbl = label or decision_id
    lines = _balanced_pair(ACC_UANG_MUKA_PELANGGAN, ACC_PIUTANG, amount,
                           f"Alokasi kelebihan bayar {lbl}")
    return await _insert_entry(
        lines=lines, description=f"Kelebihan bayar dialokasikan · {lbl}",
        date=date or now_iso(), source_type="payment_variance_alloc",
        source_id=decision_id, entity_id=entity_id or "", created_by=created_by,
        source_label=lbl)


async def post_bank_holding_allocation(*, source_id: str, entity_id: str, amount: float,
                                      label: str = "", date: str = "",
                                      created_by: str = "system") -> Optional[Dict[str, Any]]:
    """FASE G-8 — Titipan dana teridentifikasi → melunasi piutang pesanan:
      Dr 2-1950 Titipan Dana Belum Teridentifikasi / Cr 1-1200 Piutang Usaha.

    Kasnya SUDAH diakui saat dana dititipkan (Dr Bank / Cr 2-1950), jadi alokasi TIDAK
    boleh menyentuh kas lagi — kalau tidak, uang yang sama terhitung dua kali.
    Idempotent per (`bank_holding_alloc`, source_id).
    """
    amount = round(float(amount or 0), 2)
    if not source_id or amount <= EPS or await _already_posted("bank_holding_alloc", source_id):
        return None
    await seed_default_coa()
    lbl = label or source_id
    lines = _balanced_pair(ACC_TITIPAN_DANA, ACC_PIUTANG, amount,
                           f"Alokasi titipan dana {lbl}")
    return await _insert_entry(
        lines=lines, description=f"Titipan dana dialokasikan · {lbl}",
        date=date or now_iso(), source_type="bank_holding_alloc",
        source_id=source_id, entity_id=entity_id or "", created_by=created_by,
        source_label=lbl)


async def post_paired_entry(*, source_type: str, source_id: str, entity_id: str,
                            lines: List[Dict[str, Any]], label: str = "",
                            date: str = "", created_by: str = "system"
                            ) -> Optional[Dict[str, Any]]:
    """FASE E-7 (E7f/E7g) — jurnal SATU SISI dari peristiwa antar-PT (dokumen kembar).

    Pinjaman uang & pindah aset tetap antar-PT membentuk dua jurnal terpisah — satu di
    buku PT pengirim, satu di buku PT penerima — karena tiap badan hukum punya neraca
    sendiri (dan sejak E7.4 tidak ada lagi buku "grup"). Fungsi ini menulis satu sisi
    dengan `source_id` yang sudah dibedakan pemanggilnya (`…:a` / `…:b`) sehingga
    idempotensinya per sisi, bukan per peristiwa.
    """
    total_d = round(sum(float(l.get("debit") or 0) for l in lines), 2)
    total_c = round(sum(float(l.get("credit") or 0) for l in lines), 2)
    if not lines or total_d <= EPS or abs(total_d - total_c) > 0.01:
        return None
    if await _already_posted(source_type, source_id):
        return None
    await seed_default_coa()
    return await _insert_entry(
        lines=lines, description=label or source_type, date=date or now_iso(),
        source_type=source_type, source_id=source_id, entity_id=entity_id or "",
        created_by=created_by, source_label=label or source_id)


async def post_finance_case(*, case_id: str, entity_id: str, amount: float,
                            debit_acc: str, credit_acc: str, label: str = "",
                            suffix: str = "", date: str = "",
                            created_by: str = "system") -> Optional[Dict[str, Any]]:
    """FASE G-9 — Jurnal penyelesaian **kasus keuangan** (Pusat Kasus Keuangan).

    Satu pintu untuk seluruh playbook yang memindahkan uang: pindah-buku antar rekening
    sendiri, uang yang dipegang karyawan, settlement antar entitas, selisih biaya bank,
    uang muka supplier. Akun debit/kredit ditentukan playbook-nya (lihat
    `services/finance_case_playbooks.py`) supaya jurnalnya bisa dibaca auditor tanpa
    membuka kode.

    Idempotent per (`finance_case`, `case_id:suffix`) — satu kasus bisa melahirkan
    beberapa jurnal berlabel (mis. pindah-buku = 2 jurnal `keluar` & `masuk`), tetapi
    aksi yang sama tidak akan pernah menjurnal dua kali.

    PK-25 (FX-09) — kunci PER KEJADIAN: pemanggil mengirim `suffix` berakhiran nomor penyelesaian (`chg:<n>`), jadi
    penyelesaian kedua pada kasus yang sama menerbitkan jurnal kedua. Jurnal ber-kunci sama yang SUDAH ada dikembalikan
    (bukan kosong) supaya pengulangan mengadopsinya; untuk `n = 0` kunci lama tanpa nomor (`{id}:chg`, sebelum PK-25)
    ikut dikenali.
    """
    amount = round(float(amount or 0), 2)
    sid = f"{case_id}:{suffix}" if suffix else str(case_id or "")
    if not case_id or amount <= EPS:
        return None
    kunci = [sid] + ([f"{case_id}:{suffix[:-2]}"] if suffix.endswith(":0") and len(suffix) > 2 else [])
    for k in kunci:
        ada = await db.journal_entries.find_one(
            {"source_type": "finance_case", "source_id": k, "status": {"$ne": "void"}}, {"_id": 0})
        if ada:
            return safe_doc(ada)
    await seed_default_coa()
    lbl = label or case_id
    lines = _balanced_pair(debit_acc, credit_acc, amount, f"Kasus keuangan {lbl}")
    return await _insert_entry(
        lines=lines, description=f"Penyelesaian kasus keuangan · {lbl}",
        date=date or now_iso(), source_type="finance_case", source_id=sid,
        entity_id=entity_id or "", created_by=created_by, source_label=lbl)


async def post_variance_reversal(*, decision_id: str, entity_id: str, amount: float,
                                 debit_acc: str, credit_acc: str, label: str = "",
                                 date: str = "", created_by: str = "system",
                                 suffix: str = "rev") -> Optional[Dict[str, Any]]:
    """FASE G-3 — PEMBALIK keputusan selisih pembayaran (ledger append-only).

    Dipakai saat kwitansinya dibatalkan / keputusan dianulir: jurnal lama TIDAK
    diubah, dibuat jurnal baru yang membalik arahnya supaya auditor bisa membaca
    kedua kejadian. Idempotent per (`payment_variance_reversal`, decision:suffix).
    """
    amount = round(float(amount or 0), 2)
    sid = f"{decision_id}:{suffix}"
    if not decision_id or amount <= EPS or await _already_posted(
            "payment_variance_reversal", sid):
        return None
    await seed_default_coa()
    lbl = label or decision_id
    lines = _balanced_pair(debit_acc, credit_acc, amount, f"Pembalik selisih bayar {lbl}")
    return await _insert_entry(
        lines=lines, description=f"Pembalik keputusan selisih · {lbl}",
        date=date or now_iso(), source_type="payment_variance_reversal",
        source_id=sid, entity_id=entity_id or "", created_by=created_by, source_label=lbl)


async def post_cash_void(txn_id: str, *, label: str = "",
                         created_by: str = "system", date: str = "") -> Optional[Dict[str, Any]]:
    """Pembalik jurnal mutasi kas yang DI-VOID (append-only, idempotent).

    Dipakai saat kwitansi / pembayaran dibatalkan: jurnal aslinya tidak diubah, dibuat
    jurnal baru dengan debit-kredit tertukar sehingga buku besar ikut kembali dan tidak
    ada saldo hantu (mis. Piutang sudah ter-kredit padahal uangnya dianulir).
    `date` kosong = hari ini (perilaku lama); PY-T4 — batal setoran kewajiban gaji membalik pada tanggal setornya.
    """
    if not txn_id:
        return None
    orig = await db.journal_entries.find_one(
        {"source_type": "cash_transaction", "source_id": txn_id, "status": {"$ne": "void"}},
        {"_id": 0})
    if not orig or not orig.get("lines"):
        return None
    # PK-10 (GL-01) — sudah dibalik manual / oleh rekonsiliasi → jurnal pembalik itu yang dipakai (tidak dibalik lagi).
    return await _reverse_once(
        orig, source_type="cash_transaction_void", source_id=txn_id, date=date or now_iso(),
        description=f"Pembalik mutasi kas · {label or orig.get('source_label', txn_id)}", created_by=created_by,
        source_label=orig.get("source_label", ""), line_prefix="Pembalik", reason=label)


async def post_deposit_only_receipt(r: Dict[str, Any], created_by: str = "system") -> Optional[Dict[str, Any]]:
    """W2-015 — kwitansi TANPA kas baru (murni deposit): reklasifikasi nonkas
    Dr Uang Muka Pelanggan (deposit dipakai) / Cr Piutang (porsi pesanan berpiutang). Idempotent."""
    rid = r.get("id") or ""
    used_dep = round(float(r.get("used_deposit", 0) or 0), 2)
    if not rid or used_dep <= EPS or await _already_posted("ar_receipt_deposit", rid):
        return None
    advance = 0.0
    for al in (r.get("allocations") or []):
        oid, amt_al = al.get("order_id"), round(float(al.get("applied") or 0), 2)
        if oid and amt_al > EPS and amt_al > (await order_ar_room(oid, exclude_receipt_id=rid)) + EPS:
            advance = round(advance + amt_al, 2)
            await tag_advance_payment(oid, rid)
    to_ar = round(float(r.get("applied_total", 0) or 0) - advance, 2)
    if to_ar <= EPS:
        return None   # deposit → uang muka pesanan belum dikirim: akun sama, tidak ada reklas
    lines = [{"account_code": ACC_UANG_MUKA_PELANGGAN, "debit": to_ar, "credit": 0.0,
              "description": f"{r.get('number', '')} · pakai deposit"},
             {"account_code": ACC_PIUTANG, "debit": 0.0, "credit": to_ar,
              "description": f"{r.get('number', '')} · pelunasan AR dari deposit"}]
    return await _insert_entry(
        lines=lines, description=f"Pelunasan dari deposit · {r.get('number', '')}",
        date=r.get("receipt_date") or now_iso(), source_type="ar_receipt_deposit", source_id=rid,
        entity_id=r.get("entity_id", ""), created_by=created_by, source_label=r.get("number", ""))


async def reverse_deposit_only_receipt(receipt_id: str, *, label: str = "",
                                       created_by: str = "system") -> Optional[Dict[str, Any]]:
    """W2-015 — pembalik reklas deposit saat kwitansi di-void (append-only, idempotent)."""
    if not receipt_id:
        return None
    orig = await db.journal_entries.find_one(
        {"source_type": "ar_receipt_deposit", "source_id": receipt_id, "status": {"$ne": "void"}}, {"_id": 0})
    if not orig:
        return None
    rev, created = await _reverse_once_ex(   # PK-10 — satu jalur pembalik
        orig, source_type="ar_receipt_deposit_void", source_id=receipt_id, date=now_iso(),
        description=f"Pembalik pelunasan deposit · {label or orig.get('source_label', '')}", created_by=created_by,
        source_label=orig.get("source_label", ""), line_prefix="Pembalik", reason=label)
    return rev if created else None


async def customer_advance_balance(entity_id: str = "") -> float:
    """Saldo akun 2-1400 (Uang Muka Pelanggan) dari jurnal — bahan INV-VAR-02.

    Nilai positif = kewajiban (uang pelanggan yang kami tahan). Dihitung
    kredit − debit supaya arahnya sesuai sifat akun kewajiban.
    """
    codes = await _known("penjualan.uang_muka_pelanggan")
    flt: Dict[str, Any] = {"status": {"$ne": "void"},
                           "lines.account_code": {"$in": codes}}
    if entity_id and entity_id != "all":
        flt["entity_id"] = entity_id
    total = 0.0
    async for je in db.journal_entries.find(flt, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") in codes:
                total += float(ln.get("credit") or 0) - float(ln.get("debit") or 0)
    return round(total, 2)


async def variance_writeoff_total(entity_id: str = "") -> float:
    """Σ beban selisih pembayaran (6-9100) — bahan invarian & laporan."""
    codes = await _known("penjualan.selisih_bayar")
    flt: Dict[str, Any] = {"status": {"$ne": "void"},
                           "lines.account_code": {"$in": codes}}
    if entity_id and entity_id != "all":
        flt["entity_id"] = entity_id
    total = 0.0
    async for je in db.journal_entries.find(flt, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") in codes:
                total += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(total, 2)


async def post_asset_acquisition(*, asset_id: str, entity_id: str, amount: float,
                                 asset_acc: str, funding_acc: str = "", funding_fixed: bool = False,
                                 label: str = "", date: str = "") -> Optional[Dict[str, Any]]:
    """R6.2 — Perolehan aset tetap → GL.
      Dr <akun aset> (harga perolehan) / Cr <akun sumber dana> (kosong = akun kas besar lama lewat `akun_kas`).
    Menaruh aset di neraca sehingga disposal (Cr aset) tidak membuat saldo negatif.
    Idempotent per asset (source_type='fixed_asset_acquisition').
    PK-23 — `funding_fixed=True`: akun sumber dana sudah hasil pemetaan khusus aset (`aset.sumber_hutang`,
    `aset.sumber_saldo_awal`) dan dipakai apa adanya (tidak dialihkan pemetaan kebutuhan lain berkode bawaan sama)."""
    amount = round(float(amount or 0), 2)
    if amount <= EPS or await _already_posted("fixed_asset_acquisition", asset_id):
        return None
    await seed_default_coa()
    funding_acc = funding_acc or await akun_kas(entity_id or "", "", "kas_besar")
    lbl = label or asset_id
    lines = [
        {"account_code": asset_acc, "debit": amount, "credit": 0.0,
         "description": f"Perolehan aset {lbl}"},
        {"account_code": funding_acc, "debit": 0.0, "credit": amount,
         "description": f"Pembayaran perolehan aset {lbl}", **({"fixed_account": True} if funding_fixed else {})},
    ]
    return await _insert_entry(
        lines=lines, description=f"Perolehan aset tetap {lbl}",
        date=date or now_iso(), source_type="fixed_asset_acquisition",
        source_id=asset_id, entity_id=entity_id or "", created_by="system", source_label=lbl)


async def post_depreciation(*, asset_id: str, period: str, entity_id: str, amount: float,
                            asset_label: str = "", dep_exp_acc: str = ACC_DEP_EXPENSE,
                            acc_dep_acc: str = ACC_FA_ACCUM_DEP,
                            date: str = "") -> Optional[Dict[str, Any]]:
    """R6.2 — Penyusutan bulanan (straight-line) → GL.
      Dr 6-6000 Beban Penyusutan / Cr 1-2900 Akumulasi Penyusutan.
    Idempotent per (asset_id, period) via source_type='fixed_asset_depreciation',
    source_id=f'{asset_id}:{period}'. Tidak mengubah subledger fisik (GL murni)."""
    amount = round(float(amount or 0), 2)
    sid = f"{asset_id}:{period}"
    if amount <= EPS or await _already_posted("fixed_asset_depreciation", sid):
        return None
    await seed_default_coa()
    lbl = asset_label or asset_id
    lines = [
        {"account_code": dep_exp_acc, "debit": amount, "credit": 0.0,
         "description": f"Beban penyusutan {lbl} ({period})"},
        {"account_code": acc_dep_acc, "debit": 0.0, "credit": amount,
         "description": f"Akumulasi penyusutan {lbl} ({period})"},
    ]
    return await _insert_entry(
        lines=lines, description=f"Penyusutan {lbl} — {period}",
        date=date or now_iso(), source_type="fixed_asset_depreciation",
        source_id=sid, entity_id=entity_id or "", created_by="system", source_label=lbl)


async def post_asset_disposal(*, asset_id: str, entity_id: str, acquisition_cost: float,
                              accumulated: float, proceeds: float, asset_acc: str,
                              acc_dep_acc: str = ACC_FA_ACCUM_DEP, cash_acc: str = "",
                              gain_acc: str = ACC_FA_GAIN, loss_acc: str = ACC_FA_LOSS,
                              label: str = "", date: str = "") -> Optional[Dict[str, Any]]:
    """R6.2 — Pelepasan/disposal aset tetap → GL (menyertakan gain/loss).
      Dr 1-2900 Akumulasi Penyusutan (hapus akumulasi)
      Dr 1-1100 Kas/Bank (proceeds, bila ada)
      [Dr 6-9500 Rugi Pelepasan]   ← bila proceeds < book value
      Cr <akun aset>  (harga perolehan)
      [Cr 4-9100 Laba Pelepasan]   ← bila proceeds > book value
    book_value = acquisition_cost − accumulated; gain_loss = proceeds − book_value.
    Self-balancing (lihat pembuktian POC). Idempotent per asset (source_type='fixed_asset_disposal').
    Kas & Bank 1 — hasil pelepasan tidak punya dokumen kas / rekening: `cash_acc` kosong = akun kas besar lama
    (`akun_kas` tanpa rekening); di PT yang sudah memakai akun per rekening jurnalnya ditandai
    `ref.kas_belum_tertaut`."""
    acquisition_cost = round(float(acquisition_cost or 0), 2)
    accumulated = round(float(accumulated or 0), 2)
    proceeds = round(float(proceeds or 0), 2)
    if await _already_posted("fixed_asset_disposal", asset_id):
        return None
    await seed_default_coa()
    ref = None
    if not cash_acc:
        kas = await akun_kas_tanpa_dokumen(entity_id or "", "kas_besar")
        cash_acc = kas["account_code"]
        if proceeds > EPS and kas["belum_tertaut"]:
            ref = {"kas_belum_tertaut": True}
    book_value = round(acquisition_cost - accumulated, 2)
    gain_loss = round(proceeds - book_value, 2)
    lbl = label or asset_id
    lines: List[Dict[str, Any]] = []
    if accumulated > EPS:
        lines.append({"account_code": acc_dep_acc, "debit": accumulated, "credit": 0.0,
                      "description": f"Hapus akumulasi penyusutan {lbl}"})
    if proceeds > EPS:
        lines.append({"account_code": cash_acc, "debit": proceeds, "credit": 0.0,
                      "description": f"Hasil pelepasan {lbl}"})
    if gain_loss < -EPS:  # RUGI
        lines.append({"account_code": loss_acc, "debit": round(-gain_loss, 2), "credit": 0.0,
                      "description": f"Rugi pelepasan {lbl}"})
    lines.append({"account_code": asset_acc, "debit": 0.0, "credit": acquisition_cost,
                  "description": f"Hapus aset {lbl} (harga perolehan)"})
    if gain_loss > EPS:  # LABA
        lines.append({"account_code": gain_acc, "debit": 0.0, "credit": round(gain_loss, 2),
                      "description": f"Laba pelepasan {lbl}"})
    return await _insert_entry(
        lines=lines, description=f"Pelepasan aset {lbl} (gain/loss)",
        date=date or now_iso(), source_type="fixed_asset_disposal",
        source_id=asset_id, entity_id=entity_id or "", created_by="system", source_label=lbl, ref=ref)





#: PK-28 — dasar jurnal retur beli (`purchase_returns.ap_basis`): akun yang didebit.
PURCHASE_RETURN_BASES = ("gr_ir", "hutang", "kas")


async def purchase_return_basis(ret: Dict[str, Any], outcome: str = "ap_credit") -> str:
    """PK-28 — aturan memilih dasar retur beli (TIDAK berubah dari sebelumnya): refund → `kas`; PO retur sudah punya
    faktur terposting/lunas → `hutang`; selain itu → `gr_ir` (barang belum ditagih)."""
    if (outcome or "").lower() == "refund":
        return "kas"
    po_id = ret.get("po_id")
    if po_id and await db.vendor_bills.find_one(
            {"po_id": po_id, "status": {"$in": ["posted", "paid"]}}, {"_id": 0, "id": 1}):
        return "hutang"
    return "gr_ir"


#: PK-27 (IV-06) — kunci Pemetaan Akun selisih nilai nota retur beli terhadap nilai buku roll (bawaan kosong, H4).
PURCHASE_RETURN_VARIANCE_KEY = "retur.selisih_retur_beli"


def purchase_return_book_diff(*, amount: float, ppn: float = 0.0,
                              book_value: Optional[float] = None) -> Optional[float]:
    """PK-27 (IV-06) — selisih nilai buku roll yang diretur (`B`) terhadap nilai nota tanpa PPN (`D = amount − ppn`),
    dalam rupiah 2 desimal (hitungan sen, `02` D5). `None` = retur lama tanpa nilai buku (perilaku lama)."""
    if book_value is None:
        return None
    return from_cents(to_cents(book_value) - (to_cents(amount) - to_cents(ppn)))


async def purchase_return_book_lines(ret: Dict[str, Any], lines: List[Dict[str, Any]], *, net: float,
                                     book_value: Optional[float] = None, label: str = "") -> List[Dict[str, Any]]:
    """PK-27 (IV-06) — baris persediaan jurnal retur beli dinilai pada NILAI BUKU roll yang keluar.

    Baris kredit persediaan sebesar nilai nota (`net` = D) diganti Cr persediaan `book_value` (B) + baris selisih
    `retur.selisih_retur_beli` (Dr bila B > D, Cr bila B < D). Tanpa `book_value`, selisih nol, atau kunci belum
    terpetakan untuk PT retur: baris dikembalikan apa adanya (perilaku lama; selisihnya dicatat di dokumen retur).
    Baris debit (hutang/GR-IR/kas) dan PPN masukan tidak disentuh."""
    diff = purchase_return_book_diff(amount=net, book_value=book_value)
    if diff is None or to_cents(diff) == 0:
        return lines
    eid = ret.get("entity_id") or DEFAULT_ENTITY_ID
    if not await account_for(PURCHASE_RETURN_VARIANCE_KEY, eid):
        return lines
    stok = [ln for ln in lines if ln.get("account_code") == ACC_PERSEDIAAN and float(ln.get("credit") or 0) > 0]
    if len(stok) != 1:
        return lines
    out = [ln for ln in lines if ln is not stok[0]]
    nilai_buku = from_cents(to_cents(book_value))
    if nilai_buku > 0:
        out.append({**stok[0], "credit": nilai_buku,
                    "description": f"Barang keluar retur beli {label} (nilai buku roll)"})
    desc = f"Selisih nilai buku roll vs nota retur beli {label}"
    out.append({"account_key": PURCHASE_RETURN_VARIANCE_KEY, "debit": diff if diff > 0 else 0.0,
                "credit": -diff if diff < 0 else 0.0, "description": desc})
    return out


async def post_purchase_return(ret: Dict[str, Any], *, amount: float, ppn: float = 0.0,
                               label: str = "", outcome: str = "ap_credit",
                               cash_account_code: str = "", ap_basis: str = "",
                               book_value: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Session #074 (PRET-GL) — Retur beli (Nota Debit) → balik GL. Dasar (`ap_basis`, lihat `purchase_return_basis`):
      hutang : Dr Hutang(2-1100) sebesar nilai + PPN / Cr Persediaan(1-1300) neto + Cr PPN Masukan.
      kas    : Dr Kas/Bank (supplier kembalikan dana) / Cr Persediaan [+ Cr PPN Masukan].
      gr_ir  : PK-28 — Dr GR/IR(2-1150) sebesar nilai TANPA PPN / Cr Persediaan; PPN masukan tidak dibalik (barang
               belum ditagih → PPN masukannya belum pernah dicatat).
    `ap_basis` kosong → dihitung saat ini (pemanggil lama). Idempotent (source_type='purchase_return'); `ref.po_id`.
    PK-27 (IV-06) — `book_value` (nilai buku roll yang diretur): baris persediaan = nilai buku + baris selisih
    (`purchase_return_book_lines`); tanpa `book_value` = Cr persediaan nilai nota tanpa PPN (perilaku lama)."""
    rid = ret.get("id")
    amount = round(float(amount or 0), 2)
    if not rid or amount <= EPS or await _already_posted("purchase_return", rid):
        return None
    await seed_default_coa()
    ppn = round(float(ppn or 0), 2)
    net = round(amount - ppn, 2)
    basis = ap_basis if ap_basis in PURCHASE_RETURN_BASES else await purchase_return_basis(ret, outcome)
    if basis == "kas":   # Kas & Bank 1 — akun kas refund dari pemanggil (`cash_ledger.akun_refund`)
        debit_acc = cash_account_code or await akun_kas(ret.get("entity_id", ""), "", "kas_besar")
        debit_amt = amount
        debit_desc = f"Refund tunai supplier — retur beli {label}"
    elif basis == "hutang":
        debit_acc, debit_amt = ACC_HUTANG, amount
        debit_desc = f"Retur beli {label} (Nota Debit)"
    else:
        debit_acc, debit_amt = ACC_GRIR, net
        debit_desc = f"Retur beli {label} (Nota Debit) — barang belum ditagih"
    lines = [{"account_code": debit_acc, "debit": debit_amt, "credit": 0.0,
              "description": debit_desc},
             {"account_code": ACC_PERSEDIAAN, "debit": 0.0, "credit": net,
              "description": f"Barang keluar retur beli {label}"}]
    if ppn > EPS and basis != "gr_ir":
        lines.append({"account_code": ACC_PPN_IN, "debit": 0.0, "credit": ppn,
                      "description": f"Reversal PPN Masukan {label}"})

    lines = await purchase_return_book_lines(ret, lines, net=net, book_value=book_value, label=label)   # PK-27
    return await _insert_entry(
        lines=lines, description=f"Retur beli {label}",
        date=ret.get("approved_at") or now_iso(), source_type="purchase_return",
        source_id=rid, entity_id=ret.get("entity_id", ""), created_by="system", source_label=label,
        ref={"po_id": ret["po_id"]} if ret.get("po_id") else None)


def landed_cost_lines(capitalization: Dict[str, Any], label: str = "") -> List[Dict[str, Any]]:
    """PK-26 (IV-01, K-05) — baris jurnal voucher biaya masuk dari potret `capitalization` (murni, belum dipetakan).

    Dr persediaan (`inventory_amount`) · Dr persediaan dalam proses makloon (`wip_amount`) · Dr porsi sudah keluar
    (`expensed_amount`: HPP bila `expensed_to="hpp"`, akun biaya masuk pembelian bila `varians`) / Cr hutang (jumlah
    ketiganya = `allocated_total`). Akun lewat kunci Pemetaan Akun per PT (P9); baris bernilai 0 tidak ditulis."""
    from services.landed_cost_service import (EXPENSE_ACCOUNT_KEY, TREATMENT_ACCOUNT_KEY, TREATMENT_PERSEDIAAN,
                                              TREATMENT_WIP)
    cap = capitalization or {}
    porsi = [(TREATMENT_ACCOUNT_KEY[TREATMENT_PERSEDIAAN], to_cents(cap.get("inventory_amount")),
              f"Kapitalisasi landed cost {label} ke persediaan"),
             (TREATMENT_ACCOUNT_KEY[TREATMENT_WIP], to_cents(cap.get("wip_amount")),
              f"Kapitalisasi landed cost {label} ke barang di makloon"),
             (EXPENSE_ACCOUNT_KEY.get(cap.get("expensed_to"), EXPENSE_ACCOUNT_KEY["hpp"]),
              to_cents(cap.get("expensed_amount")), f"Landed cost {label} untuk roll yang sudah keluar")]
    lines = [{"account_key": key, "debit": from_cents(sen), "credit": 0.0, "description": desc}
             for key, sen, desc in porsi if sen > 0]
    total = sum(sen for _, sen, _ in porsi if sen > 0)
    if total <= 0:
        return []
    lines.append({"account_key": "pembelian.hutang", "debit": 0.0, "credit": from_cents(total),
                  "description": f"Hutang landed cost {label}"})
    return lines


async def post_landed_cost(voucher: Dict[str, Any], *, amount: float = 0.0,
                           label: str = "") -> Optional[Dict[str, Any]]:
    """Session #074 (LC-APPLY-GL) — jurnal voucher landed cost. Idempotent (source_type='landed_cost').

    PK-26 — voucher ber-`capitalization` (disetujui sejak PK-26): baris dari potret itu (`landed_cost_lines`); ulang
    posting memakai potret yang sama. Voucher lama tanpa `capitalization`: perilaku lama, Dr Persediaan(1-1300) /
    Cr Hutang(2-1100) sebesar `amount`. Konsisten dgn LC-PAY (bayar = Dr Hutang / Cr Kas)."""
    vid = voucher.get("id")
    label = label or voucher.get("voucher_number") or vid or ""
    if not vid or await _already_posted("landed_cost", vid):
        return None
    if voucher.get("capitalization"):
        lines = landed_cost_lines(voucher["capitalization"], label)
        if not lines:
            return None
    else:
        amount = round(float(amount or 0), 2)
        if amount <= EPS:
            return None
        lines = _balanced_pair(ACC_PERSEDIAAN, ACC_HUTANG, amount, f"Kapitalisasi landed cost {label}")
    await seed_default_coa()
    return await _insert_entry(
        lines=lines, description=f"Landed cost {label}", date=now_iso(),
        source_type="landed_cost", source_id=vid, entity_id=voucher.get("entity_id", ""),
        created_by="system", source_label=label)


async def post_sales_return(ret: Dict[str, Any], *, return_net: float, return_ppn: float,
                            return_cogs: float, is_cash: bool = False,
                            settlement: str = "", cash_account_code: str = "",
                            credit_note_number: str = "", ar_part: float = 0.0) -> Optional[Dict[str, Any]]:
    """F3 — Credit Note (retur penjualan) → GL reversal. Idempotent (source_type='sales_return').
      Dr Pendapatan (net) + Dr PPN Keluaran (ppn) / Cr Piutang|Kas|Store-Credit (gross)
      Dr Persediaan (cogs)  / Cr HPP (cogs)   — barang balik ke stok

    R5.2 — `settlement` menentukan akun kredit sisi kewajiban/aset:
      cash          → 1-1100 Kas (refund tunai; R5.3 buat cash_transaction terpisah)
      store_credit  → 2-1450 Saldo Kredit Pelanggan (bukan pengurang piutang; jadi kewajiban)
      ar/nego/""    → 1-1200 Piutang (pengurang piutang) — default lama (kompatibel `is_cash`).
    """
    rid = ret.get("id")
    if not rid or await _already_posted("sales_return", rid):
        return None
    if (is_cash or (settlement or "").lower() == "cash") and not cash_account_code:
        # Kas & Bank 1 — akun kas refund dari pemanggil (`cash_ledger.akun_refund`); kosong = akun kas besar lama
        cash_account_code = await akun_kas(ret.get("entity_id", ""), "", "kas_besar")
    lines = sales_return_lines(return_net=return_net, return_ppn=return_ppn, return_cogs=return_cogs, is_cash=is_cash,
                               settlement=settlement, cash_account_code=cash_account_code, ar_part=ar_part,
                               label=credit_note_number or ret.get("number", rid))
    if not lines:
        return None
    label = credit_note_number or ret.get("number", rid)
    return await _insert_entry(
        lines=lines, description=f"Credit Note / Retur penjualan {label}",
        date=ret.get("approved_at") or now_iso(),
        source_type="sales_return", source_id=rid, entity_id=ret.get("entity_id", ""),
        created_by="system", source_label=label)


def sales_return_lines(*, return_net: float, return_ppn: float, return_cogs: float, is_cash: bool = False,
                       settlement: str = "", cash_account_code: str = "", ar_part: float = 0.0,
                       label: str = "") -> List[Dict[str, Any]]:
    """Baris jurnal Nota Kredit retur (belum dipetakan per PT) — dipakai posting & pratinjau keputusan (23 Okt)."""
    return_net = round(float(return_net or 0), 2)
    return_ppn = round(float(return_ppn or 0), 2)
    return_cogs = round(float(return_cogs or 0), 2)
    gross = round(return_net + return_ppn, 2)
    if gross <= EPS and return_cogs <= EPS:
        return []
    stype = (settlement or "").lower()
    lines: List[Dict[str, Any]] = []
    if gross > EPS:
        lines.append({"account_code": ACC_PENDAPATAN, "debit": return_net, "credit": 0.0,
                      "description": f"Retur penjualan {label}"})
        if return_ppn > EPS:
            lines.append({"account_code": ACC_PPN_OUT, "debit": return_ppn, "credit": 0.0,
                          "description": f"Reversal PPN Keluaran {label}"})
        if is_cash or stype == "cash":
            if not cash_account_code:   # Kas & Bank 1 — akun kas refund dari pemanggil (`cash_ledger.akun_refund`)
                raise ValueError("Akun kas refund tunai belum ditentukan.")
            credit_acc, credit_desc = cash_account_code, "Refund tunai"
        elif stype == "store_credit":
            credit_acc, credit_desc = ACC_STORE_CREDIT, "Saldo kredit pelanggan (store credit)"
        else:
            credit_acc, credit_desc = ACC_PIUTANG, "Pengurang piutang"
        ar_part = round(min(max(float(ar_part or 0), 0.0), gross), 2) if credit_acc != ACC_PIUTANG else 0.0
        if ar_part > 0:   # LN-091 — potong tagihan SO asal dulu, sisanya refund/saldo
            lines.append({"account_code": ACC_PIUTANG, "debit": 0.0, "credit": ar_part,
                          "description": f"Pengurang piutang {label}"})
        if round(gross - ar_part, 2) > 0:
            lines.append({"account_code": credit_acc, "debit": 0.0, "credit": round(gross - ar_part, 2),
                          "description": f"{credit_desc} {label}"})
    if return_cogs > EPS:
        lines += _balanced_pair(ACC_PERSEDIAAN, ACC_HPP, return_cogs, f"Barang retur masuk stok {label}")
    return lines


def sales_return_settlement_lines(*, net: float, ppn: float, cogs: float, credits: List[Any],
                                  label: str = "") -> List[Dict[str, Any]]:
    """UAT 23 Okt — Nota Kredit penyelesaian retur PER ROLL: Dr Pendapatan (DPP) + Dr PPN Keluaran / beberapa sisi
    kredit sekaligus (potong tagihan SO asal 1-1200 · refund kas · saldo pelanggan 2-1450) + Dr Persediaan / Cr HPP
    untuk roll yang kembali ke stok. `credits` = [(kode akun, nominal, keterangan)]."""
    net, ppn, cogs = round(float(net or 0), 2), round(float(ppn or 0), 2), round(float(cogs or 0), 2)
    lines: List[Dict[str, Any]] = []
    if net > EPS:
        lines.append({"account_code": ACC_PENDAPATAN, "debit": net, "credit": 0.0, "description": f"Retur penjualan {label}"})
    if ppn > EPS:
        lines.append({"account_code": ACC_PPN_OUT, "debit": ppn, "credit": 0.0, "description": f"Reversal PPN Keluaran {label}"})
    for acc, amount, desc in credits:
        amount = round(float(amount or 0), 2)
        if amount > EPS:
            lines.append({"account_code": acc, "debit": 0.0, "credit": amount, "description": f"{desc} {label}"})
    if cogs > EPS:
        lines += _balanced_pair(ACC_PERSEDIAAN, ACC_HPP, cogs, f"Barang retur masuk stok {label}")
    return lines


async def post_sales_return_settlement(ret: Dict[str, Any], settlement_id: str, *, net: float, ppn: float, cogs: float,
                                       credits: List[Any], label: str) -> Optional[Dict[str, Any]]:
    """Jurnal satu penyelesaian per roll. Idempoten per (sales_return, `<retur>:<penyelesaian>`) — bisa dibalik per
    penyelesaian lewat `reverse_document("sales_return", "<retur>:<penyelesaian>")`."""
    sid = f"{ret['id']}:{settlement_id}"
    if await _already_posted("sales_return", sid):
        return await db.journal_entries.find_one({"source_type": "sales_return", "source_id": sid, "status": {"$ne": "void"}},
                                                 {"_id": 0})
    lines = sales_return_settlement_lines(net=net, ppn=ppn, cogs=cogs, credits=credits, label=label)
    if not lines:
        return None
    return await _insert_entry(
        lines=lines, description=f"Credit Note / Retur penjualan {label}", date=now_iso(),
        source_type="sales_return", source_id=sid, entity_id=ret.get("entity_id", ""),
        created_by="system", source_label=label,
        ref={"return_id": ret["id"], "return_number": ret.get("number", ""), "settlement_id": settlement_id})


async def post_amendment_credit_note(note: Dict[str, Any], *, ar_part: float,
                                     store_credit_part: float) -> Optional[Dict[str, Any]]:
    """L02 LN-022-T03 — Nota Kredit amandemen (harga/qty turun setelah terbit).
      Dr Pendapatan (net) + Dr PPN Keluaran (ppn) / Cr Piutang (ar_part) + Cr Saldo Kredit (sisa).
    Idempotent (source_type='amendment_credit_note', source_id=note.id)."""
    nid = note.get("id")
    if not nid or await _already_posted("amendment_credit_note", nid):
        return None
    # PK-32 (FX-14) — nota dari mesin nota (`credit_note_service`) hanya membalik pendapatan yang SUDAH diakui
    # (`revenue_reversed_*`); nota lama tanpa field itu = seluruh nilainya (perilaku lama).
    if "revenue_reversed_net" in note:
        net, ppn = round(float(note.get("revenue_reversed_net") or 0), 2), round(float(note.get("revenue_reversed_ppn") or 0), 2)
    else:
        net, ppn = round(float(note.get("net_amount") or 0), 2), round(float(note.get("ppn_amount") or 0), 2)
    ar_part, sc_part = round(float(ar_part or 0), 2), round(float(store_credit_part or 0), 2)
    if net + ppn <= EPS:
        return None
    label = note.get("number", nid)
    lines = [{"account_code": ACC_PENDAPATAN, "debit": net, "credit": 0.0,
              "description": f"Koreksi penjualan {label}"}]
    if ppn > EPS:
        lines.append({"account_code": ACC_PPN_OUT, "debit": ppn, "credit": 0.0,
                      "description": f"Koreksi PPN Keluaran {label}"})
    if ar_part > EPS:
        lines.append({"account_code": ACC_PIUTANG, "debit": 0.0, "credit": ar_part,
                      "description": f"Pengurang piutang {label}"})
    if sc_part > EPS:
        lines.append({"account_code": ACC_STORE_CREDIT, "debit": 0.0, "credit": sc_part,
                      "description": f"Saldo kredit pelanggan {label}"})
    return await _insert_entry(
        lines=lines, description=f"Nota Kredit amandemen {label}", date=note.get("created_at") or now_iso(),
        source_type="amendment_credit_note", source_id=nid, entity_id=note.get("entity_id", ""),
        created_by="system", source_label=label,
        ref={"order_id": note.get("order_id"), "order_number": note.get("order_number")})



async def post_amendment_debit_note(note: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """PK-32 (FX-15, K-14) — Nota Debit amandemen (harga/qty naik setelah terbit) yang sudah menjadi tagihan tambahan:
      Dr 1-1200 Piutang (`revenue_added_net + revenue_added_ppn`) / Cr 4-1000 Pendapatan (`revenue_added_net`)
      / Cr 2-1200 PPN Keluaran (`revenue_added_ppn`).
    Hanya bagian yang barangnya sudah terkirim (`credit_note_service.recognition_split`); sisanya diakui surat jalan
    berikutnya lewat nilai efektif. Nol → tanpa jurnal. Idempotent (source_type='amendment_debit_note', source_id=note.id,
    ref.order_id)."""
    nid = note.get("id")
    if not nid or await _already_posted("amendment_debit_note", nid):
        return None
    net = round(float(note.get("revenue_added_net") or 0), 2)
    ppn = round(float(note.get("revenue_added_ppn") or 0), 2)
    if net + ppn <= EPS:
        return None
    label = note.get("number", nid)
    lines = [{"account_code": ACC_PIUTANG, "debit": round(net + ppn, 2), "credit": 0.0,
              "description": f"Tagihan tambahan {label}"}]
    if net > EPS:
        lines.append({"account_code": ACC_PENDAPATAN, "debit": 0.0, "credit": net,
                      "description": f"Koreksi penjualan {label}"})
    if ppn > EPS:
        lines.append({"account_code": ACC_PPN_OUT, "debit": 0.0, "credit": ppn,
                      "description": f"Koreksi PPN Keluaran {label}"})
    return await _insert_entry(
        lines=lines, description=f"Nota Debit amandemen {label}", date=note.get("issued_at") or note.get("created_at")
        or now_iso(), source_type="amendment_debit_note", source_id=nid, entity_id=note.get("entity_id", ""),
        created_by="system", source_label=label,
        ref={"order_id": note.get("order_id"), "order_number": note.get("order_number")})


async def post_store_credit_redemption(*, redemption_id: str, entity_id: str, amount: float,
                                        customer_label: str = "", date: str = "",
                                        advance: float = 0.0) -> Optional[Dict[str, Any]]:
    """R5.2 — Redeem store credit sebagai pembayaran piutang.
      Dr 2-1450 Saldo Kredit Pelanggan / Cr 1-1200 Piutang (sebesar yang dialokasikan).
    KEB-PDPT (temuan gate INV-BAL-02, 18 Nov) — bagian yang dialokasikan ke pesanan yang pendapatannya BELUM lahir
    (`advance`, baris bayarnya ditandai `gl_bucket=advance`) adalah uang muka: Cr 2-1400, bukan Cr 1-1200; direklas ke
    piutang saat surat jalan (`post_advance_reclass`) — sama dengan kwitansi kas (`_receipt_lines`).
    Idempotent (source_type='store_credit_redeem', source_id=redemption_id)."""
    amount = round(float(amount or 0), 2)
    if not redemption_id or amount <= EPS or await _already_posted("store_credit_redeem", redemption_id):
        return None
    lbl = customer_label or redemption_id
    advance = round(min(max(float(advance or 0), 0.0), amount), 2)
    to_ar = round(amount - advance, 2)
    lines = [{"account_code": ACC_STORE_CREDIT, "debit": amount, "credit": 0.0,
              "description": f"Pemakaian store credit {lbl}"}]
    if to_ar > 0:
        lines.append({"account_code": ACC_PIUTANG, "debit": 0.0, "credit": to_ar,
                      "description": f"Pelunasan piutang via store credit {lbl}"})
    if advance > 0:
        lines.append({"account_code": ACC_UANG_MUKA_PELANGGAN, "debit": 0.0, "credit": advance,
                      "description": f"Uang muka pesanan belum dikirim via store credit {lbl}"})
    return await _insert_entry(
        lines=lines, description=f"Redeem store credit {lbl}",
        date=date or now_iso(), source_type="store_credit_redeem",
        source_id=redemption_id, entity_id=entity_id or "", created_by="system", source_label=lbl)


async def post_store_credit_adjust(*, adjust_id: str, entity_id: str, amount_signed: float,
                                    customer_label: str = "", date: str = "") -> Optional[Dict[str, Any]]:
    """R5.2 — Penyesuaian manual saldo store credit (admin).
      amount_signed > 0 (tambah saldo)  → Cr 2-1450 / Dr 5-9500 (beban)
      amount_signed < 0 (kurangi saldo) → Dr 2-1450 / Cr 4-9000 (pendapatan lain, hangus)
    Idempotent (source_type='store_credit_adjust', source_id=adjust_id)."""
    amt = round(float(amount_signed or 0), 2)
    if not adjust_id or abs(amt) <= EPS or await _already_posted("store_credit_adjust", adjust_id):
        return None
    lbl = customer_label or adjust_id
    if amt > 0:
        lines = [
            {"account_code": ACC_WRITEOFF, "debit": amt, "credit": 0.0,
             "description": f"Penambahan store credit {lbl}"},
            {"account_code": ACC_STORE_CREDIT, "debit": 0.0, "credit": amt,
             "description": f"Store credit bertambah {lbl}"},
        ]
    else:
        lines = [
            {"account_code": ACC_STORE_CREDIT, "debit": -amt, "credit": 0.0,
             "description": f"Store credit hangus/berkurang {lbl}"},
            {"account_code": ACC_PENDAPATAN_LAIN, "debit": 0.0, "credit": -amt,
             "description": f"Pendapatan store credit hangus {lbl}"},
        ]
    return await _insert_entry(
        lines=lines, description=f"Penyesuaian store credit {lbl}",
        date=date or now_iso(), source_type="store_credit_adjust",
        source_id=adjust_id, entity_id=entity_id or "", created_by="system", source_label=lbl)


def _cash_out_contra(txn: Dict[str, Any]) -> str:
    """Lawan akun kas KELUAR menurut `ref_type` / kategori / akun eksplisit. Murni (dipakai juga `preflight_cash`)."""
    ref_type = txn.get("ref_type") or ""
    if ref_type == "ar_refund":
        # FASE G-3 — pengembalian KELEBIHAN bayar pelanggan: uang itu tercatat sebagai
        # kewajiban (2-1400 Uang Muka Pelanggan) saat diterima, jadi saat dikembalikan
        # kewajibannya yang berkurang — bukan beban baru.
        contra = ACC_UANG_MUKA_PELANGGAN
    elif ref_type == "vendor_bill":
        contra = ACC_HUTANG
    elif ref_type == "contra_bon":
        # FASE G-7 — satu kas keluar melunasi BANYAK faktur supplier dalam satu siklus
        # tukar faktur. Lawan akunnya tetap Hutang Usaha: yang berubah hanya caranya
        # (borongan, bukan per faktur), bukan sifat kewajibannya.
        contra = ACC_HUTANG
    elif ref_type == "ap_advance":
        # FASE G-3 — kelebihan bayar ke supplier menjadi UANG MUKA (aset), bukan beban.
        contra = ACC_UANG_MUKA
    elif ref_type == "landed_cost":
        contra = ACC_HUTANG   # S#074 (LC-PAY): lunasi Hutang landed-cost (dikapitalisasi ke Persediaan), bukan Beban Angkut (double-count)
    elif ref_type == "reimburse_payable":
        contra = ACC_HUTANG_REIMBURSE  # CX-05 — bayar kelebihan LPJ: Dr 2-1650 / Cr Kas
    elif ref_type == "cash_advance":
        contra = ACC_UANG_MUKA  # Sukacita: pencairan PD → Dr Uang Muka / Cr Kas (beban diakui saat settlement)
    else:
        contra = ACC_BEBAN_OPS
        cat = (txn.get("category") or "").lower()
        for kw, acc in CASH_OUT_KEYWORDS:
            if kw in cat:
                contra = acc
                break
    # FASE G-8 — lawan akun EKSPLISIT (biaya administrasi bank dari layar rekonsiliasi,
    # kodenya diatur di Pusat Pengaturan) menang atas dugaan berbasis kata kunci.
    return (txn.get("contra_account_code") or "").strip() or contra


def cash_contra_account(txn: Dict[str, Any]) -> str:
    """PK-39 — lawan akun kas KELUAR yang akan dijurnal `_post_cash_transaction` (publik: pemeriksaan anggaran kas keluar
    membaca akun yang sama dengan jurnalnya). Logikanya tetap satu: `_cash_out_contra`."""
    return _cash_out_contra(txn)


async def preflight_cash(txn: Dict[str, Any]) -> None:
    """PK-05 — periksa jurnal kas KELUAR yang akan terbit (akun, periode) tanpa menulis apa pun.

    Baris = baris `_post_cash_transaction` cabang keluar; tanggal `txn_date`; entitas = pemilik (owner) kas.
    Melempar `JournalValidationError` / `ClosedPeriodError`."""
    amount = round(float(txn.get("amount", 0) or 0), 2)
    if amount <= EPS or txn.get("direction") != "out":
        return
    ent = txn.get("owner_entity_id") or txn.get("entity_id") or ""
    await preflight_entry(lines=_balanced_pair(_cash_out_contra(txn), await _cash_account(txn, ent), amount,
                                               "preflight"),
                          entity_id=ent, date=txn.get("txn_date") or now_iso(), source_type="cash_transaction")


async def _receipt_lines(r: Dict[str, Any], *, debit_acc: str, amount: float, number: str,
                         desc: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Baris jurnal uang baru kwitansi `r` dengan sisi debit `debit_acc` (kas/bank kwitansi biasa, atau piutang titipan
    karyawan untuk titipan tunai sales PM-T4). → (baris, pesanan yang uang mukanya perlu direklas sesudah jurnal).

    KN-076-AR-GL-DRIFT (bagian deposit): jangan meng-Cr Piutang untuk SELURUH uang bila ada kelebihan bayar / pemakaian
    deposit. Split: Dr `debit_acc` = amount (uang baru) ; Dr Uang Muka = used_deposit ; Cr Piutang = applied_total ;
    Cr Uang Muka = unapplied (applied + unapplied == amount + used_deposit → seimbang). KEB-PDPT — alokasi ke pesanan
    yang pendapatannya BELUM lahir (belum dikirim) adalah uang muka → Cr 2-1400, bukan Cr Piutang (pembayarannya
    ditandai `gl_bucket=advance`)."""
    adv_orders: List[str] = []
    applied = round(float(r.get("applied_total", amount) or 0), 2)
    used_dep = round(float(r.get("used_deposit", 0) or 0), 2)
    unapplied = round(float(r.get("unapplied_amount", 0) or 0), 2)
    advance = 0.0
    for al in (r.get("allocations") or []):
        oid, amt_al = al.get("order_id"), round(float(al.get("applied") or 0), 2)
        if not oid or amt_al <= EPS:
            continue
        # Pesanan terkirim SEBAGIAN: piutang yang lahir bisa lebih kecil dari
        # yang dibayar → kelebihannya uang muka (direklas pro-rata saat dikirim).
        room = await order_ar_room(oid, exclude_receipt_id=r.get("id", ""))
        if amt_al > room + EPS:
            advance = round(advance + amt_al, 2)
            adv_orders.append(oid)
            await tag_advance_payment(oid, r.get("id", ""))
    applied = round(applied - advance, 2)
    lines = [{"account_code": debit_acc, "debit": amount, "credit": 0.0,
              "description": f"{number} · {desc}"}]
    if used_dep > EPS:
        lines.append({"account_code": ACC_UANG_MUKA_PELANGGAN, "debit": used_dep,
                      "credit": 0.0, "description": f"{number} · pakai deposit"})
    if applied > EPS:
        lines.append({"account_code": ACC_PIUTANG, "debit": 0.0, "credit": applied,
                      "description": f"{number} · pelunasan AR"})
    if advance > EPS:
        lines.append({"account_code": ACC_UANG_MUKA_PELANGGAN, "debit": 0.0,
                      "credit": advance,
                      "description": f"{number} · uang muka pesanan belum dikirim"})
    if unapplied > EPS:
        lines.append({"account_code": ACC_UANG_MUKA_PELANGGAN, "debit": 0.0,
                      "credit": unapplied, "description": f"{number} · titipan/deposit"})
    return lines, adv_orders


async def post_cash_holding(holding: Dict[str, Any], created_by: str = "system") -> Optional[Dict[str, Any]]:
    """PM-T4 — jurnal titipan tunai sales (kwitansi tunai yang uangnya masih di tangan pencatatnya): Dr Piutang titipan
    karyawan (`kas_bank.piutang_karyawan`) sebesar uang baru kwitansi / Cr sisi kredit yang SAMA dengan jurnal kas
    kwitansi biasa (`_receipt_lines`: piutang untuk bagian yang sudah diakui, uang muka pelanggan untuk sisanya).
    Sumber `cash_holding` + id titipan; idempoten (jurnal tidak-batal yang sudah ada → None). Dipanggil lewat pintu
    tahan-gagal `post_durable` (`services/cash_holding_service.py`, panel Posting Gagal jenis `cash_holding`)."""
    hid = holding.get("id") or ""
    amount = round(float(holding.get("amount") or 0), 2)
    if not hid or amount <= EPS or holding.get("status") == "batal" or await _already_posted("cash_holding", hid):
        return None
    r = await db.ar_receipts.find_one({"id": holding.get("receipt_id") or "__none__"}, {"_id": 0})
    if not r:
        raise ValueError(f"Kwitansi titipan {holding.get('receipt_number') or ''} tidak ditemukan.")
    number = holding.get("number") or hid
    desc = f"Titipan tunai {holding.get('holder_name') or ''} · {r.get('number', '')} — {r.get('customer_name', '')}"
    lines, adv_orders = await _receipt_lines(r, debit_acc=ACC_PIUTANG_KARYAWAN, amount=amount, number=number,
                                             desc=desc)
    je = await _insert_entry(
        lines=lines, description=f"Titipan tunai sales · {desc}", date=holding.get("received_at") or now_iso(),
        source_type="cash_holding", source_id=hid, entity_id=r.get("entity_id") or holding.get("entity_id") or "",
        created_by=created_by, source_label=number, ref={"receipt_id": r.get("id", "")})
    for oid in adv_orders:
        fresh = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
        if fresh:
            await post_advance_reclass(fresh)
    return je


async def reverse_cash_holding(holding_id: str, *, label: str = "",
                               created_by: str = "system") -> Optional[Dict[str, Any]]:
    """PM-T4 — pembalik jurnal titipan tunai (kwitansi titipan dibatalkan sebelum disetor) lewat satu jalur pembalik
    (PK-10, `02` P7): sumber `cash_holding_reversal` + id titipan; jurnal asal ditandai. Idempoten: pembalik yang sudah
    ada dikembalikan."""
    if not holding_id:
        return None
    orig = await db.journal_entries.find_one(
        {"source_type": "cash_holding", "source_id": holding_id, "status": {"$ne": "void"}}, {"_id": 0})
    if not orig:
        return None
    return await _reverse_once(
        orig, source_type="cash_holding_reversal", source_id=holding_id, date=now_iso(),
        description=f"Pembalik titipan tunai · {label or orig.get('source_label', '')}", created_by=created_by,
        source_label=orig.get("source_label", ""), line_prefix="Pembalik", reason=label)


async def _post_cash_transaction(txn: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Mutasi kas: Dr/Cr Kas/Bank vs lawan akun berdasar ref_type / kategori.

    PK-20 — PRIBADI: pemanggil luar memakai `post_cash_durable` (penanda gagal di dokumen kas) yang dipanggil hanya oleh
    pembuat kas `services/cash_ledger.py` (`create_cash` / `ensure_posted`) dan jalur ulang panel Posting Gagal;
    di sini dipakai pintu itu dan isi ulang jurnal (`backfill_journals`). Penjaga INV-CASH-01."""
    if txn.get("status") == "void":
        return None
    # F-04 (audit 2026-09-02) — kas ber-`gl_posted:true` sudah dijurnal oleh dokumen
    # induknya (CN/nota debit/pinjaman antar-PT/aset). Jangan dijurnal ulang.
    if txn.get("gl_posted") is True:
        return None
    tid = txn.get("id")
    if not tid or await _already_posted("cash_transaction", tid):
        return None
    amount = round(float(txn.get("amount", 0) or 0), 2)
    if amount <= EPS:
        return None
    ref_type = txn.get("ref_type") or ""
    direction = txn.get("direction")
    desc = txn.get("description") or txn.get("category") or "Transaksi kas"
    number = txn.get("number", tid)

    # KN-076-AR-GL-DRIFT (P2, INV-AR-01): entitas buku JE + split deposit.
    # AR receipt via kas_besar mem-set cash entity="all"; jika seluruh JE (termasuk Cr Piutang)
    # dibukukan di "all", saldo Piutang 1-1200 per-PT DRIFT. Bukukan JE penerimaan AR di entitas
    # PEMILIK piutang (= entitas receipt/order). Kas gabungan tetap ter-net di konsolidasi.
    je_entity = txn.get("entity_id", "")
    ar_receipt_doc = None
    adv_orders: List[str] = []
    if ref_type == "ar_receipt":
        ar_receipt_doc = await db.ar_receipts.find_one({"id": txn.get("ref_id")}, {"_id": 0})
        if ar_receipt_doc and ar_receipt_doc.get("entity_id") and ar_receipt_doc["entity_id"] != "all":
            je_entity = ar_receipt_doc["entity_id"]
    # FASE G-3 — pengembalian dana / pembayaran supplier lewat kas gabungan tetap harus
    # dibukukan di buku entitas PEMILIK kewajiban (pola KN-076-AR-GL-DRIFT).
    if txn.get("owner_entity_id"):
        je_entity = txn["owner_entity_id"]
    cash_acc = await _cash_account(txn, je_entity)   # Kas & Bank 1 — akun kas menurut PT buku jurnal & rekening

    if direction == "in":
        if ref_type == "ar_receipt":
            # KN-076-AR-GL-DRIFT (bagian deposit) — sisi kredit dihitung `_receipt_lines` (dipakai juga jurnal titipan
            # tunai sales PM-T4, `post_cash_holding`, supaya kedua jurnal mengkredit akun yang sama).
            r = ar_receipt_doc
            if r is None:
                lines = _balanced_pair(cash_acc, ACC_PIUTANG, amount, f"{number} · {desc}")
            else:
                lines, adv_orders = await _receipt_lines(r, debit_acc=cash_acc, amount=amount, number=number,
                                                         desc=desc)
        else:
            contra = ACC_SUSPENSE  # default netral (tidak menggelembungkan pendapatan)
            cat = (txn.get("category") or "").lower()
            for kw, acc in CASH_IN_KEYWORDS:
                if kw in cat:
                    contra = acc
                    break
            # FASE G-8 — lawan akun EKSPLISIT menang atas pencocokan kata kunci: bunga/jasa
            # giro yang dibukukan dari layar rekonsiliasi memakai akun dari Pusat Pengaturan.
            contra = (txn.get("contra_account_code") or "").strip() or contra
            lines = _balanced_pair(cash_acc, contra, amount, f"{number} · {desc}")
    else:  # out
        lines = _balanced_pair(_cash_out_contra(txn), cash_acc, amount, f"{number} · {desc}")

    je = await _insert_entry(
        lines=lines, description=f"Kas {({'in': 'masuk', 'out': 'keluar'}).get(direction, direction)} · {desc}", date=txn.get("txn_date") or now_iso(),
        source_type="cash_transaction", source_id=tid, entity_id=je_entity,
        created_by=txn.get("created_by", "system"), source_label=number)
    # Uang muka untuk pesanan yang SUDAH sebagian berpendapatan: reklas porsi yang lahir
    # ke Piutang sekarang (bukan menunggu surat jalan berikutnya).
    for oid in adv_orders:
        fresh = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
        if fresh:
            await post_advance_reclass(fresh)
    return je


async def backfill_journals(entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Posting otomatis (idempotent) seluruh SSOT yang belum berjurnal.

    Urutan: sales_orders (pendapatan) lalu cash_transactions (mutasi kas).
    Aman diulang — yang sudah posted dilewati.

    F-02 (audit 2026-09-02): satu dokumen yang jatuh ke periode TERTUTUP tidak boleh
    menghentikan loop (apalagi mematikan startup). Dokumen itu dikumpulkan ke
    `skipped_closed` dan dilaporkan; kegagalan lain dicatat ke `errors`.
    """
    import logging
    log = logging.getLogger("gl.backfill")
    await seed_default_coa()
    posted_so = posted_cash = 0
    posted_cogs = 0
    skipped_closed: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []
    ent_q: Dict[str, Any] = {"entity_id": entity_id} if entity_id else {}

    async def _guarded(kind: str, doc_id: str, coro):
        try:
            return await coro
        except ClosedPeriodError as exc:
            skipped_closed.append({"kind": kind, "id": doc_id, "reason": str(exc)})
        except Exception as exc:  # noqa: BLE001
            errors.append({"kind": kind, "id": doc_id, "error": str(exc)})
            log.warning("backfill %s %s gagal: %s", kind, doc_id, exc)
        return None

    orders = await db.sales_orders.find(ent_q, {"_id": 0}).to_list(20000)
    for o in orders:
        oid = o.get("id", "")
        ships = await _order_shipments(oid)
        if ships and not await _already_posted("sales_order", oid):
            # KEB-PDPT tahap 2 — pro-rata per surat jalan.
            for sh in ships:
                if await _guarded("shipment_revenue", sh.get("id", ""), post_shipment_revenue(sh, o)):
                    posted_so += 1
                if await _guarded("shipment_cogs", sh.get("id", ""), post_shipment_cogs(sh, o)):
                    posted_cogs += 1
            continue
        if await _guarded("sales_order", oid, post_sales_order(o)):
            posted_so += 1
        # KN-076-COGS-ZERO (P2, INV-DATA): setiap order berpendapatan WAJIB punya jurnal HPP.
        if await _guarded("sales_cogs", oid, post_order_cogs(o)):
            posted_cogs += 1
    # F-04 — kas ber-gl_posted sudah berjurnal lewat dokumen induknya.
    txns = await db.cash_transactions.find(
        {**ent_q, "status": {"$ne": "void"}, "gl_posted": {"$ne": True}},
        {"_id": 0}).sort("txn_date", 1).to_list(20000)
    for t in txns:
        if await _guarded("cash_transaction", t.get("id", ""), _post_cash_transaction(t)):
            posted_cash += 1
    # KEB-PDPT — setelah kas (penanda uang muka) terposting: reklas uang muka pesanan
    # yang sudah berpendapatan ke Piutang.
    async for o in db.sales_orders.find({**ent_q, "payments.gl_bucket": ADVANCE_BUCKET}, {"_id": 0}):
        await _guarded("advance_reclass", o.get("id", ""), post_advance_reclass(o))
    # Gelombang 1 F-5 — vendor bills posted/paid yang belum berjurnal.
    # F-03 — tagihan jasa makloon dijurnal `post_subcon_service`, bukan di sini.
    posted_bill = 0
    bills = await db.vendor_bills.find(
        {**ent_q, "status": {"$in": ["posted", "paid"]},
         "bill_type": {"$ne": "makloon_service"}}, {"_id": 0}).to_list(20000)
    for b in bills:
        if await _guarded("vendor_bill", b.get("id", ""), post_vendor_bill(b)):
            posted_bill += 1
    return {"sales_orders": posted_so, "cash_transactions": posted_cash,
            "vendor_bills": posted_bill, "sales_cogs": posted_cogs,
            "total": posted_so + posted_cash + posted_bill + posted_cogs,
            "skipped_closed": skipped_closed, "errors": errors}


async def post_incentive_accrual(entity_id: str, period: str,
                                 created_by: str = "system", *, total: Optional[float] = None,
                                 date: str = "", rincian_sales: Optional[List[Dict[str, Any]]] = None
                                 ) -> Optional[Dict[str, Any]]:
    """F0-E — Akrual beban insentif penjualan per (entitas, periode).

    Model 1 (silo selling): biaya insentif ditanggung entitas SO (= entitas sales).
    Total = Σ total_incentive seluruh sales (komisi dihitung khusus entitas itu, jadi
    sales entitas lain otomatis 0). Idempotent via source_type='incentive_accrual',
    source_id=f'{entity_id}:{period}'.
      Dr Beban Insentif Penjualan / Cr Hutang Insentif Penjualan.

    PK-22 (FY-02, FY-08) — `total` (opsional) = Σ komisi slip gaji: posting gaji mengakru TEPAT angka yang dilunasi slip
    (dulu dihitung ulang dari daftar akun sales, bisa berbeda dari slip). `date` = tanggal buku jurnal periodik
    (`periodic_posting.journal_date`); kosong = hari ini (perilaku lama).

    KA-6 — aturan komisi bulan itu dibekukan (`commission_rules.bekukan_periode`): SESUDAH jurnal akrual pertama
    tersimpan (jurnal ditolak, mis. periode tertutup → tidak ada potret), dan pada setiap panggilan berikutnya selama
    akrual hidup ada, sebelum jurnal koreksi (idempoten). Potret terikat ke jurnal akrual itu: bila dianulir, potret
    diabaikan dan diganti saat akrual berikutnya. Galat pembekuan aturan merambat (gagal sesudah jurnal → panggilan
    akrual berikutnya membekukan). Bulan yang diakru sebelum fitur ini dibekukan pada panggilan akrual berikutnya.

    Tinjauan akhir I2 — catatan per sales di potret bulan = angka yang DIAKRU, tanpa menghitung ulang: `rincian_sales`
    dari pemanggil (posting gaji: komisi slip); tanpa `total` (akrual manual) mesin dijalankan SEKALI per sales
    (`incentive_accrual_rincian`) dan hasilnya menjadi total jurnal sekaligus catatannya.

    BTP-5 (A1-6, ruling R13) — setiap panggilan = finalisasi komisi PT·bulan itu: saldo potongan per sales dari
    `rincian_sales` (baris ber-`carry_out` — hasil mesin akrual manual, atau hasil mesin yang dibawa slip gaji) dicatat
    di `commission_carry_balances` (`commission_rules.catat_saldo_potongan`) — juga bila total PT 0 dan tidak ada
    jurnal, dan diperbarui setiap akrual diulang (koreksi). Panggilan dengan `total` tanpa `rincian_sales` tidak mencatat saldo.
    """
    if not entity_id or entity_id == "all" or not period:
        raise ValueError("Akrual insentif membutuhkan entitas spesifik & periode (mis. 2026-06).")
    src_id = f"{entity_id}:{period}"
    await seed_default_coa()
    sumber_rincian = "slip_gaji" if rincian_sales is not None else ""
    if total is None:
        total, rincian_sales = await incentive_accrual_rincian(entity_id, period)
        sumber_rincian = "akrual"
    total = round(float(total or 0), 2)
    tgl = date or now_iso()
    # lokal: modul aturan memanggil mesin komisi
    from services.commission_rules import bekukan_periode, catat_saldo_potongan
    akrual = await db.journal_entries.find_one(
        {"source_type": "incentive_accrual", "source_id": src_id, "status": {"$ne": "void"}}, {"_id": 0, "id": 1})
    sumber_saldo = sumber_rincian or "pemanggil"
    if not akrual:
        if total <= EPS:
            # BTP-5 (R13) — bulan difinalkan bertotal 0 (mis. semua komisi habis dipotong koreksi): tanpa jurnal, tetapi
            # saldo potongan tetap dicatat supaya terbawa ke bulan berikutnya.
            await catat_saldo_potongan(entity_id, period, rincian_sales, oleh=created_by, sumber=sumber_saldo)
            return None
        lines = _balanced_pair(ACC_BEBAN_INSENTIF, ACC_HUTANG_INSENTIF, total,
                               f"Akrual insentif penjualan {period}")
        entry = await _insert_entry(
            lines=lines, description=f"Akrual insentif penjualan {period}",
            date=tgl, source_type="incentive_accrual", source_id=src_id,
            entity_id=entity_id, created_by=created_by, source_label=f"INS-{period}")
        await bekukan_periode(entity_id, period, oleh=created_by, journal_id=entry["id"], rincian_sales=rincian_sales,
                              sumber_rincian=sumber_rincian)
        await catat_saldo_potongan(entity_id, period, rincian_sales, oleh=created_by, sumber=sumber_saldo,
                                   journal_id=entry["id"])
        return entry
    # KA-6 — akrual hidup sudah ada: pastikan potretnya ada (idempoten), juga bila tidak ada selisih — pembekuan yang
    # gagal sesudah jurnal akrual pertama dibuat di panggilan berikutnya.
    await bekukan_periode(entity_id, period, oleh=created_by, journal_id=akrual["id"], rincian_sales=rincian_sales,
                          sumber_rincian=sumber_rincian)
    # P17 COMM-04 — komisi on-collection berubah (pembayaran batal/susulan) → jurnal koreksi selisih.
    accrued = await _incentive_accrued(src_id)
    delta = round(total - accrued, 2)
    koreksi = None
    if abs(delta) > EPS:
        dr, cr = (ACC_BEBAN_INSENTIF, ACC_HUTANG_INSENTIF) if delta > 0 else (ACC_HUTANG_INSENTIF, ACC_BEBAN_INSENTIF)
        desc = f"Koreksi akrual insentif {period} ({accrued:,.0f} → {total:,.0f})"
        try:   # kunci deterministik dari saldo saat ini: klik bersamaan → indeks unik menolak duplikat
            koreksi = await _insert_entry(
                lines=_balanced_pair(dr, cr, abs(delta), desc), description=desc, date=tgl,
                source_type="incentive_accrual_adj", source_id=f"{src_id}@{accrued:.2f}",
                entity_id=entity_id, created_by=created_by, source_label=f"INS-{period}-ADJ")
        except DuplicateKeyError:
            koreksi = None
    # BTP-5 (R13) — akrual diulang (koreksi) = finalisasi ulang: saldo potongan ikut diperbarui (tidak pernah basi),
    # SESUDAH jurnal koreksinya berhasil (jurnal ditolak → galat merambat, catatan tidak berubah).
    await catat_saldo_potongan(entity_id, period, rincian_sales, oleh=created_by, sumber=sumber_saldo,
                               journal_id=akrual["id"])
    return koreksi


async def _incentive_accrued(src_id: str) -> float:
    """Saldo akrual insentif bersih (akrual + koreksi, non-void) untuk (entitas, periode)."""
    total = 0.0
    async for je in db.journal_entries.find(
            {"status": {"$ne": "void"}, "$or": [
                {"source_type": "incentive_accrual", "source_id": src_id},
                {"source_type": "incentive_accrual_adj", "source_id": {"$regex": f"^{re.escape(src_id)}@"}}]},
            {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == ACC_HUTANG_INSENTIF:
                total += float(ln.get("credit") or 0) - float(ln.get("debit") or 0)
    return round(total, 2)


async def incentive_accrual_rincian(entity_id: str, period: str) -> Tuple[float, List[Dict[str, Any]]]:
    """`(Σ komisi, [{sales_id, total, breakdown, commission_raw, carry_in, carry_out}])` — mesin komisi SEKALI per sales
    daftar PT (`sales_roster`). Galat mesin merambat: akrual manual tidak boleh membukukan total yang kurang satu sales.
    BTP-5 — `carry_out` (saldo potongan komisi yang dibawa ke bulan berikutnya, ≤ 0) dicatat `post_incentive_accrual`
    di `commission_carry_balances` (`commission_rules.catat_saldo_potongan`), dibaca mesin bulan berikutnya."""
    from services import sales_force_service as sf
    from services.incentive_targets import sales_roster
    rincian: List[Dict[str, Any]] = []
    for u in await sales_roster(entity_id, "month", period):
        dihitung = now_iso()   # BTP-5 R19 — waktu final = saat angka yang diakru dihitung
        c = await sf.compute_commission(u["id"], period, entity_id=entity_id)
        rincian.append({"sales_id": u["id"], "total": round(float(c.get("total_incentive", 0) or 0), 2),
                        "breakdown": c.get("breakdown") or [],
                        # BTP-5 — hasil mesin untuk catatan saldo potongan (`commission_rules.catat_saldo_potongan`)
                        **{k: round(float(c.get(k, 0) or 0), 2) for k in ("commission_raw", "carry_in", "carry_out")},
                        "computed_at": dihitung})
    return round(sum(float(r["total"]) for r in rincian), 2), rincian


async def incentive_accrual_estimate(entity_id: str, period: str) -> float:
    """Σ komisi otomatis bulan itu untuk daftar sales PT — angka yang dibukukan akrual manual (`post_incentive_accrual`
    tanpa `total`). KM-T4 (KM-07) — daftar = `sales_roster` (akun berperan acuan sales yang ditugaskan di PT + yang punya
    fakta/target bulan itu), sama dengan Meja Insentif; dulu semua akun berkategori sales seluruh grup. KM-T5 — juga
    dibaca layar sebelum konfirmasi "Bukukan akrual komisi {bulan}" (nominal di kalimat konfirmasi)."""
    return (await incentive_accrual_rincian(entity_id, period))[0]


async def incentive_accrual_status(entity_id: str, period: str) -> Dict[str, Any]:
    """Status akrual insentif (entitas, periode): sudah diposting? + ringkasan jurnal."""
    src_id = f"{entity_id}:{period}"
    je = await db.journal_entries.find_one(
        {"source_type": "incentive_accrual", "source_id": src_id, "status": {"$ne": "void"}},
        {"_id": 0})
    return {
        "entity_id": entity_id,
        "period": period,
        "posted": bool(je),
        "amount": await _incentive_accrued(src_id) if je else 0.0,
        "journal_number": je.get("number") if je else None,
        "journal_id": je.get("id") if je else None,
        "posted_at": je.get("created_at") if je else None,
    }


async def post_incentive_sheet(sheet: Dict[str, Any], created_by: str = "system") -> Optional[Dict[str, Any]]:
    """KM-T4 (K-22, K-13) — jurnal Lembar Insentif yang disahkan di PT bermode `sheet` (`hr.payroll_commission_mode`).

    Satu jurnal per lembar di buku PT lembar, bertanggal `sheet["journal_date"]` (akhir bulan periode dasar paling akhir
    lewat `periodic_posting.journal_date`). T = Σ nominal baris (rupiah bulat):
      T > 0  Dr Beban Insentif Penjualan / Cr Hutang Insentif Penjualan  sebesar T
      T < 0  Dr Hutang Insentif Penjualan / Cr Beban Insentif Penjualan  sebesar |T|   (lembar penyesuaian)
      T = 0  tanpa jurnal (`post_durable` mencatat `not_required`)
    Akun lewat pemetaan PT (`penjualan.beban_insentif` / `penjualan.hutang_insentif`, remap kode bawaan). Idempoten per
    (`incentive_sheet`, id lembar). Hutangnya dilunasi jurnal gaji (Dr hutang insentif / tagihan antar-PT)."""
    sid = sheet.get("id") or ""
    if not sid or await _already_posted("incentive_sheet", sid):
        return None
    total = round(sum(float(x.get("amount") or 0) for x in sheet.get("lines") or []), 2)
    if abs(total) <= EPS:
        return None
    await seed_default_coa()
    nomor = sheet.get("number") or sid
    desc = f"Beban insentif {nomor} (periode bayar {sheet.get('pay_period') or '-'})"
    dr, cr = (ACC_BEBAN_INSENTIF, ACC_HUTANG_INSENTIF) if total > 0 else (ACC_HUTANG_INSENTIF, ACC_BEBAN_INSENTIF)
    return await _insert_entry(
        lines=_balanced_pair(dr, cr, abs(total), desc), description=desc, date=sheet.get("journal_date") or now_iso(),
        source_type="incentive_sheet", source_id=sid, entity_id=sheet.get("entity_id") or "", created_by=created_by,
        source_label=nomor)


# ─── Digitalisasi Formulir Sukacita — Pertanggungjawaban petty cash → GL ─────

async def post_petty_cash_settlement(*, settlement_id: str, entity_id: str,
                                     category_lines: List[Dict[str, Any]],
                                     actor_name: str = "system", date: str = "",
                                     label: str = "",
                                     advance_amount: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Laporan Pertanggungjawaban (settlement) petty cash → jurnal.
    CX-05 — bila `advance_amount` diberikan dan pengeluaran melebihinya: Cr Uang Muka dibatasi
    nilai uang muka, kelebihannya Cr 2-1650 Hutang Reimburse Karyawan (dibayar lewat kas terpisah).

      Dr [beban per kategori COA] = Σ pengeluaran per kategori
      Cr 1-1400 Uang Muka        = Σ total pengeluaran

    Anti double-count: beban diakui SAAT settlement (bukan saat disburse). Pada
    pencairan (disburse) hanya Dr Uang Muka / Cr Kas (lihat _post_cash_transaction
    ref_type='cash_advance'); settlement membersihkan Uang Muka dengan beban riil.
    Idempotent (source_type='petty_cash_settlement').
    """
    if not settlement_id or await _already_posted("petty_cash_settlement", settlement_id):
        return None
    await seed_default_coa()
    lines: List[Dict[str, Any]] = []
    total = 0.0
    for cl in (category_lines or []):
        amt = round(float(cl.get("amount", 0) or 0), 2)
        if amt <= EPS:
            continue
        lines.append({"account_code": cl.get("account_code") or ACC_BEBAN_OPS,
                      "debit": amt, "credit": 0.0,
                      "description": cl.get("desc") or f"Beban kas kecil {label}".strip()})
        total += amt
    total = round(total, 2)
    if total <= EPS:
        return None
    to_advance = total if advance_amount is None else round(min(total, float(advance_amount)), 2)
    if to_advance > EPS:
        lines.append({"account_code": ACC_UANG_MUKA, "debit": 0.0, "credit": to_advance,
                      "description": f"Pertanggungjawaban {label}".strip()})
    excess = round(total - to_advance, 2)
    if excess > EPS:
        lines.append({"account_code": ACC_HUTANG_REIMBURSE, "debit": 0.0, "credit": excess,
                      "description": f"Kelebihan pengeluaran di atas uang muka {label}".strip()})
    return await _insert_entry(
        lines=lines, description=f"Pertanggungjawaban kas kecil {label}".strip(),
        date=date or now_iso(), source_type="petty_cash_settlement",
        source_id=settlement_id, entity_id=entity_id, created_by=actor_name,
        source_label=label)


# ═════════════════════════════════════════════════════════════════════════════
#  H4 — Payroll posting. PK-22 (FY-06): idempoten per PROSES gaji (dulu per entitas+periode). Lihat PLAN_HRD §4.4.
# ═════════════════════════════════════════════════════════════════════════════

async def payroll_source_id(run: Dict[str, Any]) -> str:
    """PK-22 (FY-06, P4) — kunci jurnal gaji (`payroll_run`, `payroll_pay`, pembaliknya) = id proses gaji, supaya proses
    kedua sesudah void/batal menerbitkan jurnalnya sendiri. Proses lama yang jurnalnya terbit dengan kunci lama
    "{PT}:{periode}" dikenali lewat `journal_id`-nya dan tetap memakai kunci lama (bayar & void menemukan jurnal yang
    sama). MEMBATALKAN perubahan kunci: kembalikan `f"{entity_id}:{period}"` di fungsi ini saja."""
    legacy = f"{run.get('entity_id')}:{run.get('period')}"
    jid = run.get("journal_id") or ""
    if jid:
        je = await db.journal_entries.find_one({"id": jid}, {"_id": 0, "source_id": 1})
        return legacy if je and je.get("source_id") == legacy else run["id"]
    # Data lama (sebelum PK-22 — belum ber-`journal_date`) yang sudah diposting tetapi `journal_id`-nya kosong: kunci lama
    # dipakai bila jurnal berkunci lama ada. Hitungan kasus ini di data nyata = kueri baca-saja laporan PK-22 (H3).
    if run.get("status") in ("posted", "paying", "paid", "voiding", "void") and not run.get("journal_date"):
        if await db.journal_entries.find_one({"source_type": "payroll_run", "source_id": legacy}, {"_id": 0, "id": 1}):
            return legacy
    return run["id"]


def payroll_journal_lines(slips: List[Dict[str, Any]], mode: str = "accrue_then_settle", *, entity_id: str = "",
                          charge_numbers: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """PY-T1 — baris jurnal gaji dari KOMPONEN slip (slip lama tanpa `components` dari kolomnya), akun dan arah tetap:

      pendapatan (selain kolom komisi) → Dr Beban Gaji 6-1000, atau Dr `account_code` komponen bila diisi
      kolom komisi                      → Dr Hutang Insentif 2-1500 [accrue_then_settle] / Dr Beban Insentif 6-5000
      baris Lembar Insentif (KM-T4)     → PT lembar = PT proses: Dr Hutang Insentif 2-1500 (apa pun mode proses: bebannya
                                          sudah diakui saat lembar disahkan); PT lain: Dr Piutang antar-PT 1-1250 per PT
                                          tertagih (memo = nomor tagihan `charge_numbers`). Negatif = kredit.
      tanggungan perusahaan (BPJS)      → Dr Beban BPJS 6-1100
      bersih                            → Cr Hutang Gaji 2-1600
      BPJS karyawan + perusahaan        → Cr Hutang BPJS 2-1700
      PPh 21                            → Cr Hutang PPh 21 2-1800 (negatif = lebih potong dikembalikan → Dr)
      potongan lain                     → Cr `account_code` komponennya (negatif → Dr)
    Untuk slip berisi komponen bawaan saja, barisnya SAMA dengan jurnal gaji sebelum PY-T1 (Σ salary_earnings → 6-1000)."""
    from services.hr_pay_components import commission_parts   # KM-T4 — komisi mesin/manual vs baris Lembar Insentif
    from services.incentive_payroll import akru               # KA-7 — `auto_and_sheet` juga mengakru komisi mesin
    salary = er_total = emp_total = pph21 = net = 0.0
    commission, lembar = commission_parts(slips)
    lembar_pt = round(lembar.pop(entity_id, 0.0), 2) if entity_id else 0.0
    extra: Dict[str, float] = {}       # akun → nominal bertanda (+ = debit) untuk pendapatan berakun & potongan lain
    extra_desc: Dict[str, str] = {}
    for s in slips:
        er_total += float(s.get("bpjs_er_total", 0) or 0)
        emp_total += float(s.get("bpjs_emp_total", 0) or 0)
        pph21 += float(s.get("pph21", 0) or 0)
        net += float(s.get("net", 0) or 0)
        comps = s.get("components")
        if not comps:
            salary += float(s.get("salary_earnings", 0) or 0)
            continue
        for c in comps:
            amt = float(c.get("amount") or 0)
            if c.get("kind") == "pendapatan" and c.get("bucket") != "commission":
                acc = (c.get("account_code") or "").strip()
                if acc:
                    extra[acc] = extra.get(acc, 0.0) + amt
                    extra_desc.setdefault(acc, f"Beban {c.get('name') or c.get('code')}")
                else:
                    salary += amt
            elif c.get("kind") == "potongan" and c.get("bucket") == "other_deductions":
                acc = (c.get("account_code") or "").strip()
                extra[acc] = extra.get(acc, 0.0) - amt
                extra_desc.setdefault(acc, f"Potongan gaji — {c.get('name') or c.get('code')}")
    salary, er_total, emp_total = round(salary, 2), round(er_total, 2), round(emp_total, 2)
    pph21, net, commission = round(pph21, 2), round(net, 2), round(commission, 2)

    def L(code, dr, cr, d=""):
        return {"account_code": code, "debit": round(dr, 2), "credit": round(cr, 2), "description": d}

    lines: List[Dict[str, Any]] = []
    if salary > EPS:
        lines.append(L(ACC_BEBAN_GAJI, salary, 0, "Beban gaji, tunjangan & lembur"))
    elif salary < -EPS:
        lines.append(L(ACC_BEBAN_GAJI, 0, -salary, "Koreksi beban gaji"))
    if er_total > EPS:
        lines.append(L(ACC_BEBAN_BPJS, er_total, 0, "Kontribusi BPJS perusahaan"))
    if abs(commission) > EPS:
        acc, d = ((ACC_HUTANG_INSENTIF, "Pelunasan hutang insentif via payroll") if akru(mode)
                  else (ACC_BEBAN_INSENTIF, "Beban insentif penjualan (payroll)"))
        lines.append(L(acc, commission, 0, d) if commission > 0 else L(acc, 0, -commission, d))
    if abs(lembar_pt) > EPS:   # KM-T4 — beban sudah diakui saat lembar disahkan; gaji melunasi hutangnya
        d = "Pelunasan hutang insentif — Lembar Insentif"
        lines.append(L(ACC_HUTANG_INSENTIF, lembar_pt, 0, d) if lembar_pt > 0 else L(ACC_HUTANG_INSENTIF, 0, -lembar_pt, d))
    for pt, amt in sorted(lembar.items()):   # KM-T4 (K-26) — insentif lembar PT lain: ditagihkan ke PT itu
        if abs(amt) <= EPS:
            continue
        memo = (charge_numbers or {}).get(pt) or ""
        d = f"Insentif sales ditagihkan antar-PT {memo}".strip()
        ln = L(ACC_IC_AR, amt, 0, d) if amt > 0 else L(ACC_IC_AR, 0, -amt, d)
        if memo:
            ln["memo"] = memo
        lines.append(ln)
    for acc, amt in extra.items():
        if amt > EPS and acc:
            lines.append(L(acc, round(amt, 2), 0, extra_desc[acc]))
    if net > EPS:
        lines.append(L(ACC_HUTANG_GAJI, 0, net, "Take-home pay terhutang"))
    if (emp_total + er_total) > EPS:
        lines.append(L(ACC_HUTANG_BPJS, 0, round(emp_total + er_total, 2), "Hutang BPJS (employee+employer)"))
    if pph21 > EPS:
        lines.append(L(ACC_HUTANG_PPH21, 0, pph21, "Hutang PPh 21"))
    elif pph21 < -EPS:  # HR-01 — lebih potong masa terakhir dikembalikan ke karyawan
        lines.append(L(ACC_HUTANG_PPH21, -pph21, 0, "Pengembalian lebih potong PPh 21"))
    for acc, amt in extra.items():
        if amt < -EPS and acc:
            lines.append(L(acc, 0, round(-amt, 2), extra_desc[acc]))
    return lines


async def post_payroll_run(run: Dict[str, Any], slips: List[Dict[str, Any]],
                           created_by: str = "system", *, date: str = "") -> Optional[Dict[str, Any]]:
    """Posting jurnal payroll run (SEIMBANG, idempotent per proses — `payroll_source_id`).

      Dr Beban Gaji (6-1000)            = Σ(pokok+tunjangan+lembur)
      Dr Beban BPJS Perusahaan (6-1100) = Σ kontribusi employer
      Dr Hutang Insentif (2-1500)       = Σ komisi   [mode accrue_then_settle]
        atau Dr Beban Insentif (6-5000) [mode expense_in_payroll]
      Cr Hutang Gaji (2-1600)           = Σ take-home (net)
      Cr Hutang BPJS (2-1700)           = Σ(employee + employer)
      Cr Hutang PPh21 (2-1800)          = Σ PPh21
    Anti double-count: mode accrue → komisi sudah jadi beban saat akrual penjualan,
    payroll hanya MEMINDAH liability 2-1500 → 2-1600 (bukan beban baru).

    PK-22 — akrual insentif (mode accrue) TIDAK lagi diposting diam-diam di sini (galatnya dulu ditelan): resep
    `posting_registry.post_payroll` mengakru Σ komisi slip lebih dulu dan galatnya menggagalkan posting. `date` =
    tanggal buku jurnal periodik (`periodic_posting.journal_date`); kosong = hari ini. Akun dan arah tidak berubah.

    PY-T1 — baris dibangun dari komponen slip (`payroll_journal_lines`): pendapatan berakun sendiri dan potongan lain
    (Cr akun komponennya) ikut; untuk komponen bawaan saja barisnya sama dengan sebelumnya.
    """
    entity_id = run.get("entity_id")
    period = run.get("period")
    src_id = await payroll_source_id(run)
    existing = await db.journal_entries.find_one(
        {"source_type": "payroll_run", "source_id": src_id, "status": {"$ne": "void"}}, {"_id": 0})
    if existing:
        return safe_doc(existing)
    await seed_default_coa()

    mode = run.get("commission_mode", "accrue_then_settle")
    label = run.get("number", f"PAY-{period}")   # K-09 — payroll memakai awalan PAY- (bukan PR- = Permintaan Pembelian)
    desc = f"Payroll {period} ({label})"
    lines = payroll_journal_lines(slips, mode, entity_id=entity_id or "",
                                  charge_numbers=run.get("_tagihan_antar_pt") or {})
    total_debit = round(sum(l["debit"] for l in lines), 2)
    total_credit = round(sum(l["credit"] for l in lines), 2)
    if abs(total_debit - total_credit) > 0.5:
        raise ValueError(f"Jurnal payroll tidak seimbang: Dr {total_debit:,.0f} ≠ Cr {total_credit:,.0f}")

    return await _insert_entry(
        lines=lines, description=desc, date=date or now_iso(),
        source_type="payroll_run", source_id=src_id, entity_id=entity_id,
        created_by=created_by, source_label=label)


# PY-T4 (PY-11) — bayar gaji tidak lagi menjurnal dari sini: kas keluar `cash_ledger.create_cash(ref_type="payroll_run")`
# berlawan akun pemetaan `sdm.hutang_gaji` menjurnal Dr hutang gaji / Cr kas rekening (`services/hr_payroll_pay.py`).
# `pay_payroll_run`, `assert_payroll_cash_account`, `payroll_cash_accounts` (akun bayar dari kode akun isi permintaan)
# dihapus; jurnal lama `payroll_pay` tetap dibaca (`payroll_source_id`, Jejak Dokumen, label sumber).



# ═════════════════════════════════════════════════════════════════════════════
#  REPORTS — Trial Balance & Account Ledger
# ═════════════════════════════════════════════════════════════════════════════

def _gl_day_end(d: Optional[str]) -> Optional[str]:
    """Gelombang 1 F-6 — as_of tanggal-saja mencakup SELURUH hari itu (konsisten dgn laporan keuangan)."""
    if not d:
        return None
    return d if "T" in d else f"{d}T23:59:59.999999"

async def trial_balance(as_of: Optional[str] = None,
                        scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Neraca saldo: saldo debit/kredit per akun (akun postable yg punya mutasi).

    `scope` = fragmen filter entitas untuk journal_entries (buku terpisah per PT).
    """
    accounts = await db.gl_accounts.find({}, {"_id": 0}).to_list(2000)
    amap = {a["code"]: a for a in accounts}
    q: Dict[str, Any] = {"status": {"$ne": "void"}, **(scope or {})}
    if as_of:
        q["date"] = {"$lte": _gl_day_end(as_of)}
    entries = db.journal_entries.find(q, {"_id": 0, "lines": 1})   # W2-021 — kursor utuh, tanpa cap 50.000

    agg: Dict[str, Dict[str, float]] = {}
    async for je in entries:
        for ln in je.get("lines", []):
            code = ln.get("account_code")
            if not code:
                continue
            a = agg.setdefault(code, {"debit": 0.0, "credit": 0.0})
            a["debit"] += float(ln.get("debit", 0) or 0)
            a["credit"] += float(ln.get("credit", 0) or 0)

    rows: List[Dict[str, Any]] = []
    tot_debit = tot_credit = 0.0
    for code, v in agg.items():
        acc = amap.get(code, {})
        net = round(v["debit"] - v["credit"], 2)
        nb = acc.get("normal_balance", normal_balance(acc.get("type", "asset")))
        debit_bal = net if net > 0 else 0.0
        credit_bal = -net if net < 0 else 0.0
        rows.append({
            "code": code,
            "name": acc.get("name", code),
            "type": acc.get("type", ""),
            "type_label": TYPE_LABELS.get(acc.get("type", ""), ""),
            "normal_balance": nb,
            "debit": round(v["debit"], 2),
            "credit": round(v["credit"], 2),
            "debit_balance": round(debit_bal, 2),
            "credit_balance": round(credit_bal, 2),
        })
        tot_debit += debit_bal
        tot_credit += credit_bal
    rows.sort(key=lambda r: r["code"])
    return {
        "as_of": as_of or now_iso(),
        "rows": rows,
        "total_debit": round(tot_debit, 2),
        "total_credit": round(tot_credit, 2),
        "balanced": abs(tot_debit - tot_credit) < 0.5,
        "account_count": len(rows),
    }


async def account_ledger(code: str, as_of: Optional[str] = None,
                         scope: Optional[Dict[str, Any]] = None,
                         start: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Buku besar 1 akun: baris jurnal yg menyentuh akun + running balance (per entitas via `scope`).

    PK-43 (UX-13) — `start` (`YYYY-MM-DD`): `lines` hanya mutasi `start ≤ tanggal ≤ as_of`; `opening_balance` = saldo
    sebelum `start` (tanda mengikuti saldo normal akun), `running_balance` berangkat dari saldo awal, `balance` = saldo
    akhir, `period = {start, end}`. Tanpa `start` bentuk jawabannya tetap."""
    acc = await db.gl_accounts.find_one({"code": code}, {"_id": 0})
    if not acc:
        return None
    q: Dict[str, Any] = {"status": {"$ne": "void"}, "lines.account_code": code, **(scope or {})}
    if as_of:
        q["date"] = {"$lte": _gl_day_end(as_of)}
    entries = await db.journal_entries.find(q, {"_id": 0}).to_list(None)   # W2-021 — tanpa cap diam-diam
    nb = acc.get("normal_balance", normal_balance(acc.get("type", "asset")))
    sign = 1 if nb == "debit" else -1

    start = (start or "")[:10]
    flat: List[Dict[str, Any]] = []
    opening = 0.0
    for je in entries:
        for ln in je.get("lines", []):
            if ln.get("account_code") != code:
                continue
            debit = round(float(ln.get("debit", 0) or 0), 2)
            credit = round(float(ln.get("credit", 0) or 0), 2)
            if start and str(je.get("date") or "") < start:   # sebelum rentang → saldo awal
                opening += sign * (debit - credit)
                continue
            flat.append({
                "entry_id": je.get("id"),
                "number": je.get("number"),
                "date": je.get("date"),
                "description": ln.get("description") or je.get("description"),
                "source_type": je.get("source_type"),
                "source_id": je.get("source_id", ""),
                "source_label": je.get("source_label", ""),
                "debit": debit,
                "credit": credit,
            })
    flat.sort(key=lambda r: (r.get("date") or "", r.get("number") or ""))
    opening = round(opening, 2)
    running = opening
    total_debit = total_credit = 0.0
    for r in flat:
        running += sign * (r["debit"] - r["credit"])
        r["running_balance"] = round(running, 2)
        total_debit += r["debit"]
        total_credit += r["credit"]
    flat.reverse()  # terbaru dulu
    out = {
        "account": {"code": acc["code"], "name": acc["name"], "type": acc.get("type"),
                    "type_label": TYPE_LABELS.get(acc.get("type", ""), ""),
                    "normal_balance": nb},
        "lines": flat,
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "balance": round(running, 2),
        "count": len(flat),
    }
    if start:
        out.update({"opening_balance": opening, "period": {"start": start, "end": (as_of or "")[:10]}})
    return out


async def gl_summary(scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """KPI ringkas untuk header GL (per entitas via `scope`)."""
    tb = await trial_balance(scope=scope)
    posted = await db.journal_entries.count_documents({"status": {"$ne": "void"}, **(scope or {})})
    accounts = await db.gl_accounts.count_documents({})
    # UAT 24 Okt (audit UI tahap 2) — G1-26: KPI menghitung jurnal NON-anulir, daftar jurnal menampilkan semua
    # (termasuk anulir) → 562 vs 563. Jumlah anulir & jenis sumber yang benar-benar ada dikirim supaya layar bisa
    # menyebut selisihnya dan filter sumber tidak hanya Manual/Penjualan/Kas.
    voided = await db.journal_entries.count_documents({"status": "void", **(scope or {})})
    sources = sorted(s for s in await db.journal_entries.distinct("source_type", dict(scope or {})) if s)
    return {
        "journal_count": posted,
        "void_count": voided,
        "sources": sources,
        "account_count": accounts,
        "total_debit": tb["total_debit"],
        "total_credit": tb["total_credit"],
        "balanced": tb["balanced"],
    }


# ═════════════════════════════════════════════════════════════════════════════
#  Gelombang 1 F-3 — Rekonsiliasi persediaan (subledger rolls vs GL) + saldo awal
# ═════════════════════════════════════════════════════════════════════════════

#: Ambang PEMBULATAN SEN rekonsiliasi persediaan — SATU angka untuk layar & penjelas
#: selisih (gap iterasi 256: layar memakai 0.01, penjelas memakai Rp 1). KF-T7 (#64) — angkanya pengaturan
#: `finance.rounding_tolerance_rupiah` (bawaan Rp 1, grup), dibaca kedua fungsi di bawah.

#: NILAI satu roll dalam SEN BULAT — SSOT-nya di `services/roll_service` supaya
#: rekonsiliasi, penjelas selisih, dan true-up saldo awal mustahil memakai rumus
#: yang berbeda (gap iterasi 257: uang tidak boleh dijumlahkan sebagai float).
from services.roll_service import roll_value_cents as _roll_value_cents  # noqa: E402

from services.roll_service import PHYSICAL_ROLL_STATUSES  # KN-C05 — satu definisi bersama (termasuk wip/blocked/damaged)

#: P05 rekonsiliasi — roll transfer INTERNAL yang masih di jalan tetap aset pemiliknya (GL tidak
#: bergerak saat transfer satu entitas), jadi subledger nilai persediaan ikut menghitungnya.
OWNED_ROLL_STATUSES = list(PHYSICAL_ROLL_STATUSES) + ["in_transit_transfer"]


#: PK-29 (IV-05/IV-09) — kebutuhan akun persediaan; saldo buku besar dibaca dari SEMUA akun yang pernah dipetakan untuk
#: kebutuhan ini di PT itu (`gl_mapping_service.known_codes(…, entity_id)`), bukan kode tetap 1-1300.
INVENTORY_ACCOUNT_KEY = "persediaan.persediaan"
#: Jurnal yang TIDAK dihitung sebagai "transaksi persediaan": jurnal saldo awal itu sendiri dan pembaliknya.
OPENING_SOURCES = ("inventory_opening", "inventory_opening_reversal")
ROLL_VALUE_FIELDS = {"_id": 0, "length_remaining": 1, "unit_cost": 1, "base_unit_cost": 1}


class TrueupNotAllowed(ValueError):
    """PK-29 (K-06) — true-up ditolak karena PT sudah punya transaksi persediaan (router → 409)."""


async def _inventory_codes(entity_id: str) -> List[str]:
    from services import gl_mapping_service as _glm
    return [c for c in await _glm.known_codes(INVENTORY_ACCOUNT_KEY, entity_id) if c]


async def accounts_balance_cents(codes: List[str], entity_id: str, as_of: str = "") -> int:
    """PK-29 (IV-05) — saldo (debit − kredit) dalam SEN BULAT untuk baris berakun ∈ `codes` pada jurnal tidak-void PT
    itu. Satu agregasi di database; baris dikelompokkan per pasangan (debit, kredit) lalu tiap nominal dibulatkan ke sen
    lewat satu fungsi (`core_utils.to_cents`, `02` D5) — Σ round(debit × 100) − Σ round(credit × 100).
    PK-43 — `as_of` (`YYYY-MM-DD`, opsional): hanya jurnal bertanggal sampai akhir hari itu."""
    codes = [c for c in codes or [] if c]
    if not codes or not entity_id:
        return 0
    match: Dict[str, Any] = {"entity_id": entity_id, "status": {"$ne": "void"}, "lines.account_code": {"$in": codes}}
    if as_of:
        match["date"] = {"$lte": _gl_day_end(as_of)}
    pipe = [{"$match": match},
            {"$unwind": "$lines"},
            {"$match": {"lines.account_code": {"$in": codes}}},
            {"$group": {"_id": {"d": "$lines.debit", "c": "$lines.credit"}, "n": {"$sum": 1}}}]
    total = 0
    async for g in db.journal_entries.aggregate(pipe):
        k = g.get("_id") or {}
        total += int(g.get("n") or 0) * (to_cents(float(k.get("d") or 0)) - to_cents(float(k.get("c") or 0)))
    return total


async def _owned_rolls_value_cents(entity_id: str) -> int:
    """Nilai roll milik PT berstatus persediaan (`OWNED_ROLL_STATUSES`) dalam sen — kursor tanpa batas (`02` D4, GL-13);
    nilai per roll dari SATU fungsi `roll_service.roll_value_cents` (`02` D5)."""
    total = 0
    async for r in db.inventory_rolls.find(
            {"owner_entity_id": entity_id, "status": {"$in": OWNED_ROLL_STATUSES}}, ROLL_VALUE_FIELDS):
        total += _roll_value_cents(r)
    return total


def _pt_text(name: str) -> str:
    """"PT {nama}" tanpa menggandakan bentuk badan usaha yang sudah tertulis di nama ("PT Uji", "CV Kanda")."""
    n = (name or "").strip()
    return n if re.match(r"^(PT|CV|UD|Koperasi|Yayasan)\.?\s", n, re.IGNORECASE) else f"PT {n}"


async def _has_inventory_transactions(entity_id: str, codes: List[str]) -> bool:
    """Ada jurnal tidak-void PT itu yang menyentuh akun persediaannya selain jurnal saldo awal (`OPENING_SOURCES`)?
    Pembalik manual (`reversal`) atas jurnal saldo awal ikut dianggap bagian saldo awal."""
    if not codes:
        return False
    async for je in db.journal_entries.find(
            {"entity_id": entity_id, "status": {"$ne": "void"}, "lines.account_code": {"$in": codes},
             "source_type": {"$nin": list(OPENING_SOURCES)}},
            {"_id": 0, "source_type": 1, "ref": 1}):
        asal = ((je.get("ref") or {}).get("reverses_entry_id") or "") if je.get("source_type") == "reversal" else ""
        if asal and await db.journal_entries.find_one(
                {"id": asal, "source_type": {"$in": list(OPENING_SOURCES)}}, {"_id": 0, "id": 1}):
            continue
        return True
    return False


async def assert_trueup_allowed(entity_id: str, *, entity_name: Optional[str] = None,
                                codes: Optional[List[str]] = None) -> None:
    """PK-29 (K-06) — bila `inventory.trueup_hanya_saldo_awal` benar untuk PT ini DAN PT sudah punya jurnal persediaan
    selain saldo awal → `TrueupNotAllowed` (pesan siap tampil). Pengaturan salah → lolos (perilaku sebelum PK-29).
    Dipanggil endpoint true-up dan baris rekonsiliasi (`trueup_allowed`); `post_inventory_opening_balance` (skrip impor
    stok awal, seed) tidak menegakkannya. `entity_name`/`codes` opsional (sudah dibaca pemanggil)."""
    from services.config_resolver import value_of
    if not await value_of("inventory.trueup_hanya_saldo_awal", {"entity_id": entity_id}):
        return
    if codes is None:
        codes = await _inventory_codes(entity_id)
    if not await _has_inventory_transactions(entity_id, codes):
        return
    if entity_name is None:
        ent = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "name": 1, "legal_name": 1}) or {}
        entity_name = ent.get("legal_name") or ent.get("name") or entity_id
    raise TrueupNotAllowed(
        f"True-up persediaan hanya untuk pengisian saldo awal. {_pt_text(entity_name)} sudah punya transaksi "
        "persediaan; telusuri selisihnya lewat \"Jelaskan selisih\" lalu koreksi dokumennya.")


async def _trueup_block_reason(entity_id: str, entity_name: str, codes: List[str]) -> str:
    """Alasan true-up ditolak untuk PT ini (kosong = boleh) — aturan yang SAMA dengan endpoint."""
    try:
        await assert_trueup_allowed(entity_id, entity_name=entity_name, codes=codes)
    except TrueupNotAllowed as exc:
        return str(exc)
    return ""


async def inventory_reconciliation(entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Banding nilai persediaan fisik (Σ roll × unit_cost) vs saldo buku besar akun persediaan, PER PT.

    `entity_ids` = PT yang dibaca (endpoint: penugasan pengguna); `None` = semua PT (skrip, penjaga data, pengingat).

    AMBANG PEMBULATAN (2026-06c, gap iterasi 256): nilai roll disimpan sebagai float, jadi Σ-nya bisa meninggalkan residu
    sen — `inventory_drift_explain()` menggolongkan selisih ≤ ambang sebagai "pembulatan sen"; layar memakai ambang yang
    SAMA yang dikirim dari sini (INV-HOME-01).

    PK-29: saldo buku besar = `accounts_balance_cents(known_codes("persediaan.persediaan", PT), PT)` (IV-05); nilai roll
    dari kursor tanpa batas (GL-13); `reconciled` per baris dan tingkat atas = SEMUA baris sinkron (IV-09) — PT A lebih
    dan PT B kurang dengan jumlah sama tidak lagi "sinkron". `total_difference` (jumlah aljabar) dipertahankan;
    `total_abs_difference` = Σ |selisih|. `trueup_allowed`/`trueup_blocked_reason` = aturan K-06 (`assert_trueup_allowed`).
    """
    from services.nilai_pengaturan import nilai
    toleransi = float(await nilai("finance.rounding_tolerance_rupiah"))   # KF-T7
    tol_cents = to_cents(toleransi)
    q: Dict[str, Any] = {} if entity_ids is None else {"id": {"$in": [e for e in entity_ids if e]}}
    ents = [e async for e in db.business_entities.find(q, {"_id": 0, "id": 1, "name": 1, "legal_name": 1})]
    rows: List[Dict[str, Any]] = []
    for e in ents:
        name = e.get("legal_name") or e.get("name") or e["id"]
        codes = await _inventory_codes(e["id"])
        sub_cents = await _owned_rolls_value_cents(e["id"])
        gl_cents = await accounts_balance_cents(codes, e["id"])
        diff_cents = sub_cents - gl_cents
        alasan = await _trueup_block_reason(e["id"], name, codes)
        rows.append({"entity_id": e["id"], "entity_name": name,
                     "subledger_value": from_cents(sub_cents), "gl_balance": from_cents(gl_cents),
                     "difference": from_cents(diff_cents),
                     "rounding_only": bool(0 < abs(diff_cents) <= tol_cents),
                     "reconciled": abs(diff_cents) <= tol_cents,
                     "inventory_accounts": codes,
                     "trueup_allowed": not alasan, "trueup_blocked_reason": alasan})
    out_of_sync = sum(1 for r in rows if not r["reconciled"])
    return {"rows": rows,
            "total_difference": from_cents(sum(to_cents(r["difference"]) for r in rows)),
            "total_abs_difference": from_cents(sum(abs(to_cents(r["difference"])) for r in rows)),
            "rows_out_of_sync": out_of_sync,
            "roll_statuses": list(OWNED_ROLL_STATUSES),   # status roll yang dinilai (layar menampilkannya, `02` L6)
            "rounding_tolerance": toleransi,
            "reconciled": out_of_sync == 0,
            "as_of": now_iso()}


#: PK-27 — roll yang sudah dihapus-buku (scrap retur, jurnal `inventory_writeoff` belum dibalik) memang bernilai 0;
#: bukan "roll berbiaya 0" yang perlu diperbaiki datanya.
WRITEOFF_ACTIVE: Dict[str, Any] = {"writeoff_je_id": {"$nin": [None, ""]}, "writeoff_reversed": {"$ne": True}}
ZERO_COST: Dict[str, Any] = {"unit_cost": {"$in": [0, None]}, "base_unit_cost": {"$in": [0, None]}}


async def zero_cost_rolls(entity_ids: List[str], *, page: int = 1, page_size: int = 50, q: str = "") -> Dict[str, Any]:
    """PK-27 (IV-07) — daftar berhalaman roll berbiaya 0 per PT (`GET /api/gl/zero-cost-rolls`).

    `in_stock`: roll berstatus persediaan (`OWNED_ROLL_STATUSES`), sisa > 0, `unit_cost` dan `base_unit_cost` 0/kosong,
    bukan roll yang sudah dihapus-buku. `shipped`: baris potret `shipments.rolls[]` ber-`unit_cost` 0 pada surat jalan
    yang tidak batal (HPP-nya nol). Jumlah total dari kueri (`02` D4), bukan dari halaman. `q` (cek layar 15 Nov, KN_37
    butir cari) menyaring nomor roll / nama barang di daftar gudang dan nomor roll / surat jalan / pesanan di daftar
    terkirim, di server (berlaku untuk jumlah dan halaman)."""
    page, page_size = max(1, int(page or 1)), min(max(1, int(page_size or 50)), 200)
    skip = (page - 1) * page_size
    ids = [e for e in entity_ids if e]
    q_roll: Dict[str, Any] = {"$and": [
        {"owner_entity_id": {"$in": ids}, "status": {"$in": OWNED_ROLL_STATUSES}, "length_remaining": {"$gt": 0},
         **ZERO_COST},
        {"$nor": [WRITEOFF_ACTIVE]}]}
    cari = re.escape((q or "").strip())
    if cari:
        pids = [p["id"] async for p in db.products.find({"name": {"$regex": cari, "$options": "i"}}, {"_id": 0, "id": 1})]
        q_roll["$and"].append({"$or": [{"roll_no": {"$regex": cari, "$options": "i"}}, {"product_id": {"$in": pids}}]})
    total_roll = await db.inventory_rolls.count_documents(q_roll)
    rows = await (db.inventory_rolls.find(q_roll, {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1,
                                                   "owner_entity_id": 1, "length_remaining": 1, "status": 1})
                  .sort([("roll_no", 1), ("id", 1)]).skip(skip).limit(page_size).to_list(page_size))
    names = {p["id"]: p.get("name") or p["id"] async for p in db.products.find(
        {"id": {"$in": list({r.get("product_id") for r in rows})}}, {"_id": 0, "id": 1, "name": 1})}
    in_stock = [{"roll_id": r["id"], "roll_no": r.get("roll_no") or "", "product_name": names.get(r.get("product_id"), ""),
                 "entity_id": r.get("owner_entity_id", ""), "length_remaining": float(r.get("length_remaining") or 0),
                 "status": r.get("status", "")} for r in rows]
    base = [{"$match": {"entity_id": {"$in": ids}, "status": {"$nin": list(SHIPMENT_DEAD)},
                        "rolls.unit_cost": {"$in": [0, None]}}},
            {"$unwind": "$rolls"}, {"$match": {"rolls.unit_cost": {"$in": [0, None]}}}]
    if cari:
        rids = [x["id"] async for x in db.inventory_rolls.find({"roll_no": {"$regex": cari, "$options": "i"}},
                                                                {"_id": 0, "id": 1})]
        base.append({"$match": {"$or": [{"shipment_no": {"$regex": cari, "$options": "i"}},
                                        {"order_number": {"$regex": cari, "$options": "i"}},
                                        {"rolls.roll_id": {"$in": rids}}]}})
    hit = await db.shipments.aggregate(base + [{"$group": {"_id": None, "n": {"$sum": 1}}}]).to_list(1)
    total_ship = int((hit[0] if hit else {}).get("n") or 0)
    srows = await db.shipments.aggregate(base + [
        {"$sort": {"created_at": -1, "id": 1}}, {"$skip": skip}, {"$limit": page_size},
        {"$project": {"_id": 0, "shipment_no": 1, "order_number": 1, "entity_id": 1, "created_at": 1,
                      "roll_id": "$rolls.roll_id", "length": "$rolls.length"}}]).to_list(page_size)
    nos = {r["id"]: r.get("roll_no") or "" async for r in db.inventory_rolls.find(
        {"id": {"$in": [x.get("roll_id") for x in srows if x.get("roll_id")]}}, {"_id": 0, "id": 1, "roll_no": 1})}
    shipped = [{"shipment_no": x.get("shipment_no", ""), "order_number": x.get("order_number", ""),
                "roll_no": nos.get(x.get("roll_id"), "") or x.get("roll_id", ""),
                "length": float(x.get("length") or 0), "shipped_at": x.get("created_at", ""),
                "entity_id": x.get("entity_id", "")} for x in srows]
    return {"in_stock": {"items": in_stock, "total": total_roll},
            "shipped": {"items": shipped, "total": total_ship}, "page": page, "page_size": page_size}


def _roll_ref(roll: Dict[str, Any]) -> Dict[str, Any]:
    """ALAMAT sebuah tuduhan selisih: roll mana, dokumen mana, layar mana.

    KENAPA ADA (2026-06): penjelas selisih sudah bisa berkata "Roll RTN-00001 bernilai
    Rp 900.000", tetapi kalimat itu berhenti sebagai TEKS — orang yang membacanya masih
    harus mencari roll itu sendiri di layar lain. Dengan alamat ini setiap dugaan
    penyebab bisa diklik sampai ke dokumennya (`kind` = apa yang dibuka, `q` = kata
    kunci pencariannya, `view` = layar tujuan bila pengguna ingin pindah).
    """
    acq = roll.get("acquired") or {}
    return {"kind": "roll", "id": roll.get("id", ""),
            "number": roll.get("roll_no") or "", "q": roll.get("roll_no") or "",
            "view": "inventory-rolls",
            "source_ref_id": acq.get("ref_id", ""),
            "source_via": acq.get("via") or roll.get("origin_type") or ""}


# UAT 24 Okt (audit UI tahap 2) — G1-07: kalimat penjelas selisih dulu memuat kode mentah ("Roll dengan asal
# 'cycle_count_found'", "Tidak ada jurnal goods_receipt / landed_cost"). Padanan frontend: finance/glSourceLabels.js.
ROLL_ORIGIN_LABEL: Dict[str, str] = {
    "initial": "Saldo awal", "inbound": "Barang masuk (penerimaan PO)", "transfer": "Transfer antar-PT",
    "production_output": "Hasil produksi", "subcon_receipt": "Terima dari makloon",
    "subcon_receipt_byproduct": "Hasil sampingan makloon", "return": "Retur penjualan",
    "cycle_count_found": "Temuan stock opname", "cut": "Hasil potong roll", "split": "Pecahan roll",
    "pod_auto": "Konfirmasi terima otomatis", "tidak tercatat": "Asal tidak tercatat",
}
JOURNAL_SOURCE_LABEL: Dict[str, str] = {
    "inventory_opening": "Saldo Awal Persediaan", "goods_receipt": "Penerimaan Barang", "landed_cost": "Biaya Masuk",
    "interco_transaction": "Antar-PT", "interco_return": "Retur Antar-PT", "production_output": "Hasil Produksi",
    "subcon_receipt": "Terima dari Makloon", "subcon_issue": "Kirim ke Makloon", "sales_return": "Retur Penjualan",
    "shipment_cogs": "HPP Kirim", "sales_cogs": "HPP Penjualan", "cycle_count_variance": "Selisih Stok Opname",
    "inventory_writeoff": "Hapus Persediaan", "purchase_return": "Retur Pembelian", "vendor_bill": "Tagihan Supplier",
    "manual": "Manual", "reversal": "Pembalik", "rnd_sample_issue": "Pemakaian Sample R&D",
    "return_cutloss": "Rugi Retur (cut-loss)", "return_grade_impairment": "Penurunan Grade Retur",
    "inter_company_transfer": "Transfer Antar-PT", "tanpa sumber": "Tanpa sumber",
    # PK-36 — sumber jurnal otomatis yang menyentuh akun kontrol disebut di pesan tolak pembalikan manual (padanan
    # frontend glSourceLabels.js).
    "cash_transaction": "Kas", "interco_settlement": "Pelunasan Antar-PT", "interco_loan": "Pinjaman Antar-PT",
    "interco_loan_repayment": "Cicilan Pinjaman Antar-PT", "ar_receipt_deposit": "Penerimaan Piutang",
    "sales_order": "Penjualan", "shipment_revenue": "Pendapatan Kirim", "contra_bon_deduction": "Potongan Kontrabon",
    "amendment_credit_note": "Nota Kredit Koreksi", "return_logistics": "Ongkir Retur",
    "suspense_reclass": "Reklas Akun Penampung", "finance_case": "Kasus Keuangan",
    "grir_clearing": "Kliring GR/IR",   # PK-28
    "cash_holding": "Titipan Tunai Sales", "cash_holding_reversal": "Pembalik Titipan Tunai",   # PM-T4
}


def _human_code(code: Any) -> str:
    t = str(code or "").replace("_", " ").strip()
    return t[:1].upper() + t[1:] if t else "—"


def roll_origin_label(code: Any) -> str:
    return ROLL_ORIGIN_LABEL.get(str(code or ""), _human_code(code))


def journal_source_label(code: Any) -> str:
    return JOURNAL_SOURCE_LABEL.get(str(code or ""), _human_code(code))


async def inventory_drift_explain(entity_id: str) -> Dict[str, Any]:
    """PENJELAS SELISIH persediaan (lanjutan INV-GL-DRIFT, 2026-06).

    KENAPA ADA: layar rekonsiliasi bisa berkata "berselisih Rp 900.000" tetapi tidak
    bisa berkata **di mana**. Satu-satunya tombol yang tersedia lalu berupa true-up —
    menyamakan angka tanpa tahu penyebabnya, yang artinya cacat aslinya tetap hidup dan
    akan melahirkan selisih berikutnya. Modul ini tidak MENEBAK: ia memecah kedua sisi
    memakai field yang benar-benar ada di dokumennya, lalu menaruhnya berdampingan.

    Sisi FISIK dari koleksi `inventory_rolls` (`acquired.via` → asal barang), dipotong
    dengan status & rumus nilai yang SAMA dengan `inventory_reconciliation()` supaya
    totalnya tak mungkin berbeda dari angka di layar. Sisi GL dari baris jurnal
    berakun persediaan PT itu (`journal_entries.lines`), dikelompokkan per `source_type`.

    PK-29 — akun persediaan = `known_codes("persediaan.persediaan", PT)` (bukan kode tetap 1-1300) dan saldo dari
    `accounts_balance_cents`; roll dibaca lewat kursor tanpa batas (GL-13) dalam satu putaran (yang perlu diingat hanya
    roll terbesar per asal, contoh roll ber-HPP nol, dan tiga roll terbaru), putaran kedua hanya untuk mencari roll yang
    nilainya persis sebesar selisih.
    """
    from services.nilai_pengaturan import nilai
    toleransi = float(await nilai("finance.rounding_tolerance_rupiah"))   # KF-T7 — sama dengan rekonsiliasi
    ent = await db.business_entities.find_one(
        {"id": entity_id}, {"_id": 0, "id": 1, "name": 1, "legal_name": 1}) or {}
    roll_q = {"owner_entity_id": entity_id, "status": {"$in": OWNED_ROLL_STATUSES}}
    roll_fields = {"_id": 0, "id": 1, "roll_no": 1, "length_remaining": 1, "unit_cost": 1,
                   "base_unit_cost": 1, "acquired": 1, "origin_type": 1, "writeoff_je_id": 1,
                   "writeoff_reversed": 1}

    per_origin: Dict[str, Dict[str, Any]] = {}
    zero_cost: Dict[str, Any] = {"count": 0, "length": 0.0, "examples": []}
    #: Roll TERBESAR per asal & roll ber-HPP nol pertama — dipakai sebagai ALAMAT
    #: tuduhan (lihat `_roll_ref`): satu klik harus sampai ke dokumennya, bukan
    #: berhenti di kategori.
    biggest_per_origin: Dict[str, Dict[str, Any]] = {}
    zero_cost_ref: Optional[Dict[str, Any]] = None
    subledger_cents = 0
    #: tiga roll paling baru masuk (tanggal turun; tanggal sama → urutan baca) — pengganti `sorted(rolls)[:3]`
    terbaru_rolls: List[Tuple[str, int, Dict[str, Any]]] = []
    i = -1
    async for r in db.inventory_rolls.find(roll_q, roll_fields):
        i += 1
        tgl = str((r.get("acquired") or {}).get("date") or "")
        terbaru_rolls = sorted(terbaru_rolls + [(tgl, i, r)], key=lambda x: (x[0], -x[1]), reverse=True)[:3]
        via = str(((r.get("acquired") or {}).get("via")
                   or r.get("origin_type") or "tidak tercatat"))
        cost = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
        length = float(r.get("length_remaining", 0) or 0)
        # Nilai roll = SEN BULAT dari SSOT yang sama dengan rekonsiliasi (roll_service).
        value_cents = _roll_value_cents(r)
        value = from_cents(value_cents)
        subledger_cents += value_cents
        slot = per_origin.setdefault(via, {"origin": via, "rolls": 0, "value": 0.0,
                                           "value_cents": 0})
        slot["rolls"] += 1
        slot["value_cents"] += value_cents
        slot["value"] = from_cents(slot["value_cents"])
        if value > float((biggest_per_origin.get(via) or {}).get("value") or 0):
            biggest_per_origin[via] = {"roll": r, "value": value}
        if cost <= 0 and not (r.get("writeoff_je_id") and not r.get("writeoff_reversed")):   # PK-27 — scrap
            zero_cost["count"] += 1
            zero_cost["length"] = round(zero_cost["length"] + length, 2)
            if len(zero_cost["examples"]) < 5:
                zero_cost["examples"].append(r.get("roll_no") or "(tanpa nomor)")
            if zero_cost_ref is None:
                zero_cost_ref = _roll_ref(r)

    gl_by_source: Dict[str, float] = {}
    inv_codes = await _inventory_codes(entity_id)
    inv_account = await account_for(INVENTORY_ACCOUNT_KEY, entity_id)   # akun yang dipakai jurnal baru PT ini
    async for je in db.journal_entries.find(
            {"entity_id": entity_id, "lines.account_code": {"$in": inv_codes},
             "status": {"$ne": "void"}},
            {"_id": 0, "source_type": 1, "lines": 1}):
        for line in je.get("lines", []):
            if line.get("account_code") not in inv_codes:
                continue
            key = str(je.get("source_type") or "tanpa sumber")
            gl_by_source[key] = round(
                gl_by_source.get(key, 0.0)
                + float(line.get("debit") or 0) - float(line.get("credit") or 0), 2)

    gl_cents = await accounts_balance_cents(inv_codes, entity_id)
    gl_balance = from_cents(gl_cents)
    subledger = from_cents(subledger_cents)
    difference = from_cents(subledger_cents - gl_cents)

    #: Asal barang → jenis jurnal yang SEHARUSNYA menemaninya. Dipakai hanya untuk
    #: menuduh "asal ini tidak punya jurnal pasangan", bukan untuk menghitung angka.
    expected = {
        "initial": ("inventory_opening",),
        "inbound": ("goods_receipt", "landed_cost"),
        "transfer": ("interco_transaction", "interco_return"),
        "production_output": ("production_output",),
        "subcon_receipt": ("subcon_receipt",),
        "subcon_receipt_byproduct": ("subcon_receipt",),
        "return": ("sales_return", "interco_return"),
    }
    suspects: List[Dict[str, Any]] = []
    #: Roll yang nilainya PERSIS sebesar selisih adalah petunjuk terkuat yang bisa
    #: diberikan tanpa menebak: ia menunjuk satu dokumen untuk diperiksa, bukan kategori.
    if abs(difference) > 1:
        async for r in db.inventory_rolls.find(roll_q, roll_fields):
            cost = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
            nilai = round(float(r.get("length_remaining", 0) or 0) * cost, 2)
            if nilai <= 0 or abs(nilai - abs(difference)) > 1:
                continue
            acq = r.get("acquired") or {}
            suspects.append({
                "kind": "nilai_cocok_selisih", "value": nilai,
                "label": (f"Roll {r.get('roll_no') or '(tanpa nomor)'} bernilai "
                          f"{rupiah(nilai)} — PERSIS sebesar selisihnya"),
                "hint": (f"Masuk lewat {roll_origin_label(acq.get('via') or r.get('origin_type') or '—')}"
                         f" (dokumen {acq.get('ref_id') or '—'}, "
                         f"{str(acq.get('date') or '')[:10]}). Barangnya ada di gudang "
                         f"tetapi nilainya tidak pernah berjurnal ke {inv_account} — periksa "
                         "dokumen itu dulu, jangan langsung true-up."),
                "ref": _roll_ref(r)})
            break
    for slot in sorted(per_origin.values(), key=lambda s: -s["value"]):
        srcs = expected.get(slot["origin"])
        if not srcs:
            suspects.append({
                "kind": "asal_tak_dikenal", "value": slot["value"],
                "label": f"Roll dengan asal {roll_origin_label(slot['origin'])} ({slot['rolls']} roll)",
                "hint": "Asal ini belum punya pasangan jenis jurnal yang diketahui — "
                        "periksa pembuat roll-nya sebelum true-up.",
                "ref": _roll_ref((biggest_per_origin.get(slot["origin"]) or {}).get("roll") or {})})
            continue
        if slot["value"] > 0 and not any(abs(gl_by_source.get(s, 0.0)) > 0 for s in srcs):
            suspects.append({
                "kind": "tanpa_jurnal", "value": slot["value"],
                "label": (f"Barang dari {roll_origin_label(slot['origin'])} bernilai "
                          f"{rupiah(slot['value'])} ({slot['rolls']} roll)"),
                "hint": f"Tidak ada jurnal {' / '.join(journal_source_label(x) for x in srcs)} di buku ini — "
                        "barangnya masuk gudang tanpa jurnal pasangannya.",
                "ref": _roll_ref((biggest_per_origin.get(slot["origin"]) or {}).get("roll") or {})})
    if zero_cost["count"]:
        suspects.append({
            "kind": "roll_tanpa_hpp", "value": 0.0,
            "label": f"{zero_cost['count']} roll aktif tanpa HPP "
                     f"({zero_cost['length']:,.0f} unit)".replace(",", "."),
            "hint": "Roll ber-HPP nol membuat nilai FISIK lebih kecil dari GL. "
                    f"Contoh: {', '.join(zero_cost['examples'])}.",
            "ref": zero_cost_ref or {}})
    opening = gl_by_source.get("inventory_opening", 0.0)
    if opening:
        last_trueup = await db.journal_entries.find_one(
            {"entity_id": entity_id, "source_type": "inventory_opening",
             "status": {"$ne": "void"}},
            {"_id": 0, "id": 1, "number": 1}, sort=[("date", -1)]) or {}
        suspects.append({
            "kind": "true_up_sebelumnya", "value": opening,
            "label": f"GL sudah pernah disamakan manual (true-up) {rupiah(opening)}",
            "hint": "Bagian ini bukan hasil transaksi — ia hasil penyesuaian orang. "
                    "Lihat riwayat true-up untuk dasarnya.",
            "ref": {"kind": "journal", "id": last_trueup.get("id", ""),
                    "number": last_trueup.get("number", ""),
                    "q": last_trueup.get("number", ""), "view": "general-ledger",
                    "source_type": "inventory_opening"}})
    by_source_total = round(sum(gl_by_source.values()), 2)
    if abs(by_source_total - gl_balance) > 0.01:
        suspects.append({
            "kind": "jurnal_di_luar_rincian", "value": round(gl_balance - by_source_total, 2),
            "label": "Ada saldo GL yang tidak terwakili rincian sumber di atas",
            "hint": "Kemungkinan jurnal manual/anulir yang bentuknya berbeda — buka Buku "
                    f"Besar akun {inv_account}.",
            "ref": {"kind": "account", "id": inv_account, "number": inv_account,
                    "q": inv_account, "view": "general-ledger"}})
    if 0 < abs(difference) <= toleransi:
        suspects.append({
            "kind": "pembulatan", "value": difference,
            "label": f"Selisihnya paling banyak {rupiah(toleransi)} — pembulatan sen",
            "hint": "Tidak perlu true-up; ambang peringatan sudah menyaringnya."})
    # Selisih yang MASIH belum tertunjuk tidak boleh berakhir tanpa arah: sebutkan
    # roll yang paling baru masuk supaya ada dokumen konkret untuk diperiksa.
    tertunjuk = {"tanpa_jurnal", "nilai_cocok_selisih", "roll_tanpa_hpp", "pembulatan"}
    if abs(difference) > toleransi and not any(s["kind"] in tertunjuk for s in suspects):
        terbaru_rolls = [r for _, _, r in terbaru_rolls]
        terbaru = [{"roll_no": r.get("roll_no") or "(tanpa nomor)",
                    "via": ((r.get("acquired") or {}).get("via")
                            or r.get("origin_type") or "—"),
                    "date": str((r.get("acquired") or {}).get("date") or "")[:10],
                    "value": round(float(r.get("length_remaining", 0) or 0)
                                   * float(r.get("unit_cost")
                                           or r.get("base_unit_cost") or 0), 2)}
                   for r in terbaru_rolls]
        suspects.append({
            "kind": "selisih_belum_terjelaskan", "value": difference,
            "label": f"{rupiah(difference)} belum bisa ditunjuk ke satu kategori",
            "hint": "Roll yang paling baru masuk: "
                    + " · ".join(f"{t['roll_no']} {rupiah(t['value'])} ({roll_origin_label(t['via'])}, "
                                 f"{t['date']})" for t in terbaru)
                    + ". Periksa dokumen sumbernya sebelum true-up.",
            "ref": _roll_ref(terbaru_rolls[0]) if terbaru_rolls else {}})

    return {
        "entity_id": entity_id,
        "entity_name": ent.get("legal_name") or ent.get("name") or entity_id,
        "subledger_value": subledger, "gl_balance": gl_balance, "difference": difference,
        "inventory_accounts": inv_codes,   # PK-29 — akun yang dibaca (sama dengan baris rekonsiliasi)
        "physical_by_origin": sorted(({**o, "origin_label": roll_origin_label(o["origin"])}
                                      for o in per_origin.values()), key=lambda s: -s["value"]),
        "gl_by_source": sorted(({"source": k, "source_label": journal_source_label(k), "net": v}
                                for k, v in gl_by_source.items()), key=lambda s: -abs(s["net"])),
        "zero_cost_rolls": zero_cost, "suspects": suspects, "as_of": now_iso(),
    }


async def post_inventory_opening_balance(actor_name: str = "system",
                                         tag: str = "",
                                         reason: str = "",
                                         include_rounding: bool = False,
                                         entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """True-up saldo GL Persediaan ke nilai subledger per entitas.

    PK-29 — `entity_ids` diisi → hanya PT itu yang diproses (endpoint: PT aktif saja); kosong = semua PT (skrip impor
    stok awal, seed). Aturan K-06 (`assert_trueup_allowed`) SENGAJA tidak dipasang di sini: skrip impor stok awal
    memanggil fungsi ini langsung untuk stok yang memang saldo awal; yang ditutup adalah tombol di layar (endpoint).

    Dr Persediaan / Cr Ekuitas Saldo Awal (atau sebaliknya bila GL > subledger).

    IDEMPOTENSI YANG BENAR (INV-GL-DRIFT dibayar 2026-06): kuncinya BUKAN kalender.
    Versi lama memakai `f"{entitas}:{tanggal}"`, jadi begitu true-up sudah berjalan
    sekali hari ini, panggilan BERIKUTNYA di hari yang sama selalu dilewati
    (`_already_posted`) — padahal stok bisa bergerak lagi setelahnya. Akibatnya GL
    tertinggal dari subledger sampai HARI BERGANTI dan `verify_data_integrity` GL-3
    memperingatkan drift (mis. `ent_kanda` Δ900.000) yang tidak bisa dipulihkan hari
    itu juga. Sekarang kuncinya diberi urutan (`#n`) sehingga true-up boleh berjalan
    berapa kali pun; pengaman terhadap klik ganda tetap ADA dan lebih kuat: selisih
    dihitung ULANG tiap panggilan, jadi setelah satu true-up berhasil selisihnya 0
    dan tidak ada jurnal kedua yang lahir.
    `tag` opsional tetap didukung (dipakai fixture/QA yang ingin kunci bernama).

    `reason` (lanjutan 2026-06): DASAR penyesuaian ikut menempel di JURNALNYA
    (deskripsi + field `reason`), bukan hanya di jejak audit batch. Layar sudah lama
    MEWAJIBKAN alasan, tetapi alasan itu berhenti di `audit_logs`: akuntan yang membuka
    jurnal saat tutup buku hanya membaca "Saldo awal / true-up persediaan" tanpa tahu
    dasarnya, lalu harus menebak atau menelusuri audit log per-batch. Pertanggungjawaban
    yang tidak ada di tempat yang dibaca sama saja tidak ada.
    """
    await seed_default_coa()
    recon = await inventory_reconciliation(entity_ids)
    posted: List[Dict[str, Any]] = []
    dasar = (reason or "").strip()
    # `include_rounding` (2026-06c): sisa SEN warisan jurnal lama (≤ ambang
    # pembulatan) sengaja TIDAK ikut true-up otomatis — supaya tombol utama tidak
    # menerbitkan jurnal Rp 0,01 tanpa diminta. Pemilik bisa merapikannya secara
    # SADAR lewat tombol "Rapikan sisa pembulatan" yang mengirim bendera ini.
    minimum = 0.0 if include_rounding else EPS
    for r in recon["rows"]:
        diff = r["difference"]
        if abs(diff) <= minimum:
            continue
        hari = now_iso()[:10]
        base = f"{r['entity_id']}:{hari}" + (f":{tag}" if tag else "")
        seq = await db.journal_entries.count_documents(
            {"source_type": "inventory_opening", "entity_id": r["entity_id"],
             "source_id": {"$regex": f"^{re.escape(base)}"}, "status": {"$ne": "void"}})
        src_id = base if seq == 0 else f"{base}#{seq + 1}"
        if await _already_posted("inventory_opening", src_id):
            continue
        if diff > 0:
            lines = _balanced_pair(ACC_PERSEDIAAN, ACC_EKUITAS_AWAL, diff,
                                   f"Saldo awal persediaan {r['entity_name']}")
        else:
            lines = _balanced_pair(ACC_EKUITAS_AWAL, ACC_PERSEDIAAN, -diff,
                                   f"Penyesuaian persediaan {r['entity_name']}")
        je = await _insert_entry(
            lines=lines,
            description=(f"Saldo awal / true-up persediaan — {r['entity_name']}"
                         + (f" · dasar: {dasar}" if dasar else "")),
            date=now_iso(), source_type="inventory_opening", source_id=src_id,
            entity_id=r["entity_id"], created_by=actor_name, source_label="OPENING-INV")
        if dasar:
            await db.journal_entries.update_one({"id": je["id"]},
                                                {"$set": {"reason": dasar}})
        posted.append({"entity_id": r["entity_id"], "amount": round(diff, 2),
                       "journal_number": je["number"], "reason": dasar})
    return {"posted": posted, "count": len(posted)}


# ═════════════════════════════════════════════════════════════════════════════
#  KONSOLIDASI GRUP vs PER-PT (Multi-Entity F0-E enhancement)
#  Memanfaatkan buku terpisah per entitas (scope journal_entries.entity_id) untuk
#  menyajikan ringkasan P&L + neraca tiap PT, lalu menjumlahkannya jadi gabungan.
# ═════════════════════════════════════════════════════════════════════════════

_CONS_SUM_FIELDS = [
    "revenue", "cogs", "opex", "expense", "gross_profit", "net_income",
    "assets", "liabilities", "equity", "retained_earnings", "equity_total",
    "cash", "ar", "ap", "inventory", "ppn_out", "journal_count",
]


async def _entity_financials(entity_id: str, as_of: Optional[str] = None) -> Dict[str, Any]:
    """Ringkasan keuangan satu buku (entity_id) dari trial balance terisolasi. Kas & Bank 1 (tinjauan T1 I2) — kas =
    akun `report_basis.kode_kas` PT itu (bawaan + pemetaan + `is_cash`, termasuk sub-akun rekening), sama dengan
    pembaca saldo kas lain."""
    from services import report_basis as _rb
    scope = {"entity_id": entity_id}
    tb = await trial_balance(as_of=as_of, scope=scope)
    kas = await _rb.kode_kas(scope)
    revenue = cogs = opex = 0.0
    assets = liabilities = equity = 0.0
    cash = ar = ap = ppn_out = inventory = 0.0
    for r in tb["rows"]:
        t = r.get("type")
        code = r.get("code", "")
        debit_net = round(r["debit_balance"] - r["credit_balance"], 2)
        credit_net = round(r["credit_balance"] - r["debit_balance"], 2)
        if t == "income":
            revenue += credit_net
        elif t == "expense":
            if code.startswith("5"):
                cogs += debit_net
            else:
                opex += debit_net
        elif t == "asset":
            assets += debit_net
        elif t == "liability":
            liabilities += credit_net
        elif t == "equity":
            equity += credit_net
        if code in kas:
            cash += debit_net
        elif code == ACC_PIUTANG:
            ar += debit_net
        elif code == "1-1300":
            inventory += debit_net
        elif code == ACC_HUTANG:
            ap += credit_net
        elif code == ACC_PPN_OUT:
            ppn_out += credit_net
    revenue = round(revenue, 2)
    cogs = round(cogs, 2)
    opex = round(opex, 2)
    expense = round(cogs + opex, 2)
    gross_profit = round(revenue - cogs, 2)
    net_income = round(revenue - expense, 2)
    equity = round(equity, 2)
    journal_count = await db.journal_entries.count_documents(
        {"status": {"$ne": "void"}, "entity_id": entity_id})
    return {
        "revenue": revenue, "cogs": cogs, "opex": opex, "expense": expense,
        "gross_profit": gross_profit, "net_income": net_income,
        "net_margin": round(net_income / revenue * 100, 1) if revenue > 0 else 0.0,
        "assets": round(assets, 2), "liabilities": round(liabilities, 2),
        "equity": equity, "retained_earnings": net_income,
        "equity_total": round(equity + net_income, 2),
        "cash": round(cash, 2), "ar": round(ar, 2), "ap": round(ap, 2),
        "inventory": round(inventory, 2), "ppn_out": round(ppn_out, 2),
        "journal_count": journal_count, "balanced": tb["balanced"],
    }


async def consolidation(entity_ids: List[str], as_of: Optional[str] = None) -> Dict[str, Any]:
    """Konsolidasi grup: ringkasan keuangan per-PT + total gabungan.

    `entity_ids` = entitas dalam cakupan baca user (admin/manager = semua aktif).
    Jurnal ber-entity_id 'all' (kas/bank grup) ditampilkan sebagai baris 'Grup /
    Kas Bersama' agar penjumlahan baris == total konsolidasi (faithful)."""
    from services.config_currency import base_currency   # KP-T1 — mata uang baris = registry, bukan master PT
    ents = {e["id"]: e for e in await db.business_entities.find(
        {"id": {"$in": list(entity_ids)}}, {"_id": 0}).to_list(200)}
    rows: List[Dict[str, Any]] = []
    for eid in entity_ids:
        e = ents.get(eid, {})
        if e.get("is_group"):
            continue
        fin = await _entity_financials(eid, as_of)
        raw_pkp = e.get("is_pkp")
        is_pkp = (e.get("default_tax_mode") in ("ppn", "pkp")) if raw_pkp is None else bool(raw_pkp)
        rows.append({
            "entity_id": eid,
            "entity_name": e.get("legal_name") or e.get("short_name") or eid,
            "short_name": e.get("short_name") or e.get("doc_prefix") or eid,
            "currency": await base_currency(eid),
            "is_pkp": is_pkp,
            "is_shared": False,
            **fin,
        })
    rows.sort(key=lambda r: r["revenue"], reverse=True)
    # Bucket grup (kas/bank bersama, entity_id == 'all')
    shared = await _entity_financials("all", as_of)
    if shared["journal_count"] > 0:
        rows.append({
            "entity_id": "all", "entity_name": "Grup / Kas Bersama", "short_name": "Grup",
            "currency": await base_currency(None), "is_pkp": None, "is_shared": True, **shared,
        })
    cons = {f: round(sum(float(r.get(f, 0) or 0) for r in rows), 2) for f in _CONS_SUM_FIELDS}
    cons["journal_count"] = int(cons["journal_count"])
    cons["net_margin"] = round(cons["net_income"] / cons["revenue"] * 100, 1) if cons["revenue"] > 0 else 0.0
    cons["balanced"] = all(r.get("balanced", True) for r in rows)
    cons["entity_count"] = len([r for r in rows if not r.get("is_shared")])
    return {"as_of": as_of or now_iso(), "entities": rows, "consolidated": cons}
