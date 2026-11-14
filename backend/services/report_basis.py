"""PK-41 (RP-01, RP-03, RP-05, RP-06, RP-11, RP-12; keputusan K-16) — dasar hitung laporan pendukung.

Satu tempat untuk aturan yang dipakai bersama layar Piutang, Hutang, Arus Kas, Proyeksi Kas, dan Control Tower:

* `hari_antara`          — selisih tanggal kalender WIB (satu-satunya penghitung hari umur piutang, umur hutang,
                           pengingat, dan proyeksi kas). Sebelumnya `(now − due).days` dan `(due − now).days` sama-sama
                           membulatkan ke bawah sehingga dua laporan tidak saling berlawanan tanda (RP-11).
* `baris_tagihan`        — piutang per SURAT JALAN (K-16): satu baris per jurnal pendapatan surat jalan (atau jurnal
                           pesanan lama) bertanggal ≤ `per`, pembayaran bertanggal ≤ `per` dialokasikan ke jatuh tempo
                           tertua, sisanya satu baris "belum dikirim" tanpa jatuh tempo (RP-03, RP-05).
* `kode_kas`             — akun kas & setara kas dari pemetaan akun + tanda di bagan akun (bukan kode ditulis mati).
* `golongan_arus_kas`    — golongan arus kas menurut JENIS TRANSAKSI jurnal sebelum aturan akun lawan (RP-06).
* `label_kelompok_umur`  — judul kolom umur piutang dari batas `ar.aging_buckets` (RP-12).

Tidak ada koleksi atau field tersimpan baru: semua dihitung saat dibaca. Uang dihitung dalam sen bulat
(`core_utils.to_cents`, `02_STANDAR.md` §5 D5); tanggal dari `services.book_date.tanggal_buku` (D6).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core_utils import from_cents, to_cents
from db import db
from services.book_date import tanggal_buku

#: Sisa baris tagihan yang dianggap lunas (rupiah) — sama dengan ambang "belum lunas" laporan piutang lama.
EPS = 0.01
#: Banyak pesanan per kueri `$in` (spesifikasi PK-41 "Asumsi dan risiko").
KELOMPOK = 1000

SUMBER_SURAT_JALAN = "surat_jalan"
SUMBER_PESANAN = "pesanan"          # jurnal lama ber-`source_type` `sales_order` (pendapatan per pesanan)
SUMBER_NOTA_DEBIT = "nota_debit"    # PK-32 — tagihan tambahan nota debit yang sudah dijurnal (`amendment_debit_note`)
SUMBER_BELUM_DIKIRIM = "belum_dikirim"
#: PK-32 — baris `payments[]` nota kredit amandemen bagian TERTANGGUH (pendapatannya belum diakui, tanpa jurnal; di
#: `gl_service.NOTE_BUCKETS`). Pengurangnya sudah ikut nilai efektif jurnal surat jalan berikutnya, jadi baris ini
#: mengurangi bagian "belum dikirim", tidak dialokasikan ke surat jalan (tidak memotong piutang dua kali).
BUCKET_NOTA_TANGGUH = "nota_tangguh"

#: Golongan arus kas per jenis transaksi (aturan `golongan_arus_kas`, diperiksa berurutan).
SUMBER_SALDO_AWAL = frozenset({"bank_opening_balance", "bank_opening_adjustment"})
SUMBER_INVESTASI = frozenset({"fixed_asset_acquisition", "fixed_asset_disposal", "fixed_asset_transfer_settlement"})
SUMBER_PINJAMAN_ANTAR_PT = frozenset({"interco_loan", "interco_loan_repayment"})


# ── Hari ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _tgl(nilai: Any) -> date:
    return date.fromisoformat(tanggal_buku(nilai))


def hari_antara(dari: Any, ke: Any) -> int:
    """`tanggal_buku(ke) − tanggal_buku(dari)` dalam hari kalender WIB. Kosong = hari ini (WIB).

    Umur piutang: `hari_antara(jatuh_tempo, per)` (positif = lewat). Proyeksi kas: `hari_antara(hari_ini, jatuh_tempo)`
    (positif = belum jatuh tempo). Untuk pasangan tanggal yang sama keduanya tepat berlawanan tanda."""
    return (_tgl(ke) - _tgl(dari)).days


def _tgl_aman(nilai: Any) -> Optional[str]:
    """Tanggal buku, atau None bila nilainya tidak dikenali (dokumen lama)."""
    try:
        return tanggal_buku(nilai) if nilai not in (None, "") else None
    except ValueError:
        return None


# ── Termin ──────────────────────────────────────────────────────────────────────────────────────────────────────────
async def peta_termin(orders: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, str], Optional[int]]:
    """`(kode termin, PT) → net_days` dari master Syarat Bayar (lapisan PT menang atas global), SATU kali per daftar.
    Bahan `customer_service._term_days` (aturan termin yang ada: snapshot hari termin pesanan → kode termin pesanan →
    profil pelanggan → 30)."""
    from services import entity_master_service as ems
    out: Dict[Tuple[str, str], Optional[int]] = {}
    for o in orders:
        code = o.get("payment_term_code") or ""
        key = (code, o.get("entity_id") or "")
        if not code or key in out:
            continue
        row = await ems.resolve_row("payment-terms", code, key[1], include_inactive=True)
        try:
            out[key] = int(row["net_days"]) if row and row.get("net_days") not in (None, "") else None
        except (TypeError, ValueError):
            out[key] = None
    return out


# ── Baris tagihan piutang ───────────────────────────────────────────────────────────────────────────────────────────
def pesanan_piutang(o: Dict[str, Any]) -> bool:
    """Aturan pesanan yang ikut piutang (aturan yang ada): status bukan status mati dan metode bayar bukan tunai.
    `payment_status` TIDAK dilihat (RP-05: pesanan yang kini lunas bisa masih berpiutang pada tanggal lampau)."""
    from services.customer_service import DEAD_STATUSES, NON_AR_METHODS, order_payment_method
    return o.get("status") not in DEAD_STATUSES and order_payment_method(o) not in NON_AR_METHODS


async def _kode_piutang(entity_id: str, cache: Dict[str, set]) -> set:
    from services.gl_mapping_service import known_codes
    if entity_id not in cache:
        cache[entity_id] = set(await known_codes("penjualan.piutang", entity_id or None))
    return cache[entity_id]


async def _jurnal_pendapatan(order_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Jurnal pendapatan tidak-void per pesanan: per surat jalan (`shipment_revenue`, `ref.order_id`), tagihan tambahan
    nota debit (`amendment_debit_note`, `ref.order_id`, PK-32) dan jurnal lama per pesanan (`sales_order`, `source_id`).
    Dibaca per kelompok `KELOMPOK` pesanan, kursor tanpa batas (`02` D4)."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    proj = {"_id": 0, "id": 1, "number": 1, "date": 1, "source_type": 1, "source_id": 1, "source_label": 1,
            "ref": 1, "entity_id": 1, "lines": 1}
    for i in range(0, len(order_ids), KELOMPOK):
        ids = order_ids[i:i + KELOMPOK]
        async for je in db.journal_entries.find(
                {"status": {"$ne": "void"}, "$or": [
                    {"source_type": {"$in": ["shipment_revenue", "amendment_debit_note"]}, "ref.order_id": {"$in": ids}},
                    {"source_type": "sales_order", "source_id": {"$in": ids}}]}, proj):
            oid = je.get("source_id") if je.get("source_type") == "sales_order" else (je.get("ref") or {}).get("order_id")
            if oid:
                out.setdefault(oid, []).append(je)
    return out


def _terbayar_sen(o: Dict[str, Any], per: str, *, tangguh: Optional[bool] = None) -> int:
    """Σ `payments[].amount` bertanggal ≤ `per` (tanggal `date`, cadangan `created_at`; baris pembalik PK-19 bernilai
    negatif pada tanggal pembatalannya). Baris tanpa tanggal yang dikenali ikut dihitung (perilaku lama).
    `tangguh` None = semua baris; False = tanpa baris nota kredit tertangguh (`BUCKET_NOTA_TANGGUH`); True = hanya itu."""
    total = 0
    for p in o.get("payments") or []:
        if tangguh is not None and (p.get("gl_bucket") == BUCKET_NOTA_TANGGUH) != tangguh:
            continue
        tgl = _tgl_aman(p.get("date") or p.get("created_at"))
        if tgl is not None and tgl > per:
            continue
        total += to_cents(float(p.get("amount") or 0))
    return total


async def baris_tagihan(orders: List[Dict[str, Any]], customers: Dict[str, Dict[str, Any]], *,
                        per: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Per pesanan piutang (`pesanan_piutang`), daftar baris tagihan posisi tanggal `per` (kosong = hari ini WIB):

    `{sumber, ref_id, ref_number, tanggal, jatuh_tempo, nilai, terbayar, sisa, hari_lewat}`

    1. Baris terkirim — satu per jurnal pendapatan tidak-void bertanggal ≤ `per` (surat jalan, jurnal lama per pesanan,
       dan PK-32 tagihan tambahan nota debit yang sudah dijurnal): `nilai` = Σ debit akun `penjualan.piutang` (pemetaan
       PT jurnal), `tanggal` = tanggal buku jurnal, `jatuh_tempo` = `tanggal` + hari termin (`customer_service._term_days`).
       Ikut: `jurnal_id`, `jurnal_number`.
    2. Pembayaran bertanggal ≤ `per` dialokasikan ke baris terkirim mulai jatuh tempo tertua; kelebihannya `uang_muka`.
       Baris nota kredit amandemen bagian TERTANGGUH (PK-32, `BUCKET_NOTA_TANGGUH`) tidak dialokasikan ke surat jalan:
       pengurangnya sudah ada di nilai efektif jurnal surat jalan berikutnya; ia mengurangi bagian belum dikirim.
    3. Baris belum dikirim — `nilai = max(0, nilai tagihan − Σ nilai terkirim − uang_muka − Σ nota tertangguh)` (nilai
       tagihan = `_order_grand_total`: grand total + tagihan tambahan nota debit, PK-32), tanpa jatuh tempo,
       `hari_lewat = 0`. Ikut: `uang_muka`.
    4. `hari_lewat = hari_antara(jatuh_tempo, per)`.
    5. Baris bersisa ≤ 0,01 dibuang (daftar pesanan boleh kosong = lunas per tanggal itu).
    """
    from services.customer_service import _order_grand_total, _term_days
    per_tgl = tanggal_buku(per)
    hidup = [o for o in orders if o.get("id") and pesanan_piutang(o)]
    jurnal = await _jurnal_pendapatan([o["id"] for o in hidup])
    termin = await peta_termin(hidup)
    kode_cache: Dict[str, set] = {}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for o in hidup:
        cust = customers.get(o.get("customer_id") or "") or {}
        hari_termin = _term_days(cust, o, termin)
        terkirim: List[Dict[str, Any]] = []
        for je in jurnal.get(o["id"], []):
            tgl = _tgl_aman(je.get("date"))
            if tgl is None or tgl > per_tgl:
                continue
            kode = await _kode_piutang(je.get("entity_id") or o.get("entity_id") or "", kode_cache)
            nilai = sum(to_cents(float(ln.get("debit") or 0)) for ln in je.get("lines") or []
                        if ln.get("account_code") in kode)
            if nilai <= 0:
                continue
            lama = je.get("source_type") == "sales_order"
            jt = (date.fromisoformat(tgl) + timedelta(days=hari_termin)).isoformat()
            terkirim.append({
                "sumber": SUMBER_PESANAN if lama else (
                    SUMBER_NOTA_DEBIT if je.get("source_type") == "amendment_debit_note" else SUMBER_SURAT_JALAN),
                "ref_id": o["id"] if lama else (je.get("source_id") or ""),
                "ref_number": (o.get("number") or o["id"]) if lama else (je.get("source_label") or je.get("source_id") or ""),
                "tanggal": tgl, "jatuh_tempo": jt, "_nilai": nilai,
                "jurnal_id": je.get("id") or "", "jurnal_number": je.get("number") or ""})
        terkirim.sort(key=lambda r: (r["jatuh_tempo"], r["tanggal"], r["ref_id"]))
        total_kirim = sum(r["_nilai"] for r in terkirim)
        sisa_bayar = max(0, _terbayar_sen(o, per_tgl, tangguh=False))
        tangguh = max(0, _terbayar_sen(o, per_tgl, tangguh=True))
        baris: List[Dict[str, Any]] = []
        for r in terkirim:
            nilai = r.pop("_nilai")
            bayar = min(sisa_bayar, nilai)
            sisa_bayar -= bayar
            sisa = nilai - bayar
            if from_cents(sisa) <= EPS:
                continue
            baris.append({**r, "nilai": from_cents(nilai), "terbayar": from_cents(bayar), "sisa": from_cents(sisa),
                          "hari_lewat": hari_antara(r["jatuh_tempo"], per_tgl)})
        # `sisa_bayar` kini = uang muka (pembayaran melebihi seluruh nilai terkirim).
        belum = max(0, to_cents(_order_grand_total(o)) - total_kirim - sisa_bayar - tangguh)
        if from_cents(belum) > EPS:
            baris.append({"sumber": SUMBER_BELUM_DIKIRIM, "ref_id": o["id"], "ref_number": o.get("number") or o["id"],
                          "tanggal": None, "jatuh_tempo": None, "nilai": from_cents(belum), "terbayar": 0.0,
                          "sisa": from_cents(belum), "hari_lewat": 0, "uang_muka": from_cents(sisa_bayar),
                          "jurnal_id": "", "jurnal_number": ""})
        out[o["id"]] = baris
    return out


# ── Arus kas ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def kode_kas(scope: Optional[Dict[str, Any]]) -> set:
    """Akun kas & setara kas laporan bercakupan `scope` (saringan Mongo `{"entity_id": …}`): semua akun yang pernah
    dipakai `kas_bank.kas_besar` dan `kas_bank.kas_kecil` (bawaan + pemetaan + riwayat; satu PT = lapisan PT itu) ∪ akun
    bertanda `is_cash` / `cash_equivalent` di bagan akun efektif."""
    from services import financial_statement_service as fs
    from services.gl_mapping_service import known_codes
    eid = fs.scope_entity(scope)
    codes = set(await known_codes("kas_bank.kas_besar", eid)) | set(await known_codes("kas_bank.kas_kecil", eid))
    amap = await fs._accounts_map(scope)   # noqa: SLF001 — bagan akun efektif laporan (pembantu yang sama)
    codes |= {c for c, a in amap.items() if a.get("is_cash") or a.get("cash_equivalent")}
    return {c for c in codes if c}


def _jenis_akun(code: str, amap: Dict[str, Dict[str, Any]]) -> str:
    t = (amap.get(code) or {}).get("type") or ""
    if t:
        return t
    return {"1": "asset", "2": "liability", "3": "equity", "4": "income"}.get((code or "")[:1], "expense")


def golongan_arus_kas(je: Dict[str, Any], kas: set, amap: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Golongan arus kas satu jurnal menurut jenis transaksinya — diperiksa berurutan (spesifikasi PK-41, RP-06):

    1. `source_type` saldo awal rekening → `saldo_awal` (bukan arus periode; menambah kas awal);
    2. `source_type` aset tetap, atau jurnal memuat akun aset tidak lancar (golongan `investing` menurut akun) →
       `investing` untuk SELURUH kas jurnal (laba/rugi pelepasan tidak dipecah ke operasi);
    3. pinjaman antar-PT → `financing` bila kas berlawanan dengan akun utang (pihak peminjam), `investing` bila berlawanan
       dengan akun piutang (pihak pemberi pinjaman);
    4. selain itu `None` → pemecahan kas per akun lawan seperti sebelumnya.
    """
    from services.cash_flow_service import _section
    st = je.get("source_type") or ""
    if st in SUMBER_SALDO_AWAL:
        return "saldo_awal"
    lawan = [ln["account_code"] for ln in je.get("lines") or []
             if ln.get("account_code") and ln["account_code"] not in kas]
    if st in SUMBER_INVESTASI or any(_section(_jenis_akun(c, amap), c) == "investing" for c in lawan):
        return "investing"
    if st in SUMBER_PINJAMAN_ANTAR_PT:
        jenis = {_jenis_akun(c, amap) for c in lawan}
        if "liability" in jenis:
            return "financing"
        if "asset" in jenis:
            return "investing"
    return None


# ── Umur piutang ────────────────────────────────────────────────────────────────────────────────────────────────────
#: Kunci kolom umur piutang (sama dengan `ar_aging_service.BUCKET_KEYS`).
KUNCI_UMUR = ("current", "b1_30", "b31_60", "b61_90", "b90_plus")


def label_kelompok_umur(batas: List[int]) -> List[Dict[str, str]]:
    """Judul kolom umur piutang dari batas hari `ar.aging_buckets` (nilai yang dipakai `ar_aging_service._bucket`).

    Batas [30, 60, 90] → "Belum jatuh tempo", "1–30 hari", "31–60 hari", "61–90 hari", "> 90 hari". Hanya kolom yang
    bisa terisi dikembalikan: dengan dua batas, kolom ketiga tidak pernah dipakai `_bucket`; batas keempat dan
    seterusnya masuk kolom terakhir (aturan `_bucket`). Batas kosong = bawaan pengaturan."""
    try:
        e = sorted(int(float(x)) for x in (batas or []))
    except (TypeError, ValueError):
        e = []
    if not e:
        from config_registry import default_of
        e = sorted(int(x) for x in default_of("ar.aging_buckets"))
    pakai = e[:3]
    out = [{"key": "current", "label": "Belum jatuh tempo"}]
    bawah = 1
    for i, atas in enumerate(pakai):
        out.append({"key": KUNCI_UMUR[i + 1], "label": f"{bawah}–{atas} hari"})
        bawah = atas + 1
    out.append({"key": "b90_plus", "label": f"> {pakai[-1]} hari"})
    return out


# ── Serah-terima (b): pembantu pemanggil laporan ────────────────────────────────────────────────────────────────────
def terbayar_per(o: Dict[str, Any], per: Any) -> float:
    """Σ pembayaran pesanan bertanggal ≤ `per` (rupiah) — pasangan `baris_tagihan` untuk kolom "Terbayar" rincian."""
    return from_cents(max(0, _terbayar_sen(o, tanggal_buku(per))))


def ringkas_baris(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ringkasan baris tagihan satu pesanan (sen bulat → rupiah): `total` = Σ sisa, `ar_ledger` = Σ sisa baris terkirim,
    `exposure` = Σ sisa baris belum dikirim, `overdue` = Σ sisa baris lewat jatuh tempo, `oldest_days` = hari lewat
    terlama (0 bila tidak ada), `due_date` = jatuh tempo tertua baris terkirim yang masih bersisa (None = belum dikirim)."""
    kirim = [r for r in rows if r["sumber"] != SUMBER_BELUM_DIKIRIM]
    lewat = [r for r in kirim if r["hari_lewat"] > 0]
    return {"total": from_cents(sum(to_cents(r["sisa"]) for r in rows)),
            "ar_ledger": from_cents(sum(to_cents(r["sisa"]) for r in kirim)),
            "exposure": from_cents(sum(to_cents(r["sisa"]) for r in rows if r["sumber"] == SUMBER_BELUM_DIKIRIM)),
            "overdue": from_cents(sum(to_cents(r["sisa"]) for r in lewat)),
            "oldest_days": max((r["hari_lewat"] for r in lewat), default=0),
            "max_days": max((r["hari_lewat"] for r in kirim), default=0),
            "due_date": min((r["jatuh_tempo"] for r in kirim), default=None)}


async def saldo_akun_sen(key: str, entity_ids: Optional[List[str]], per: Any = None, *, kredit: bool = False) -> int:
    """Saldo buku besar kebutuhan akun `key` (semua akun yang pernah dipakainya, `known_codes` per PT) dalam SEN BULAT:
    Σ debit − Σ kredit (`kredit=True` → kredit − debit) jurnal tidak-void PT `entity_ids` (None/kosong = semua PT)
    bertanggal ≤ `per` (None = tanpa batas tanggal). Satu agregasi per PT; tiap nominal dibulatkan lewat `to_cents`."""
    from services.gl_mapping_service import known_codes
    daftar: List[Optional[str]] = list(entity_ids) if entity_ids else [None]
    total = 0
    for eid in daftar:
        codes = [c for c in await known_codes(key, eid) if c]
        if not codes:
            continue
        match: Dict[str, Any] = {"status": {"$ne": "void"}, "lines.account_code": {"$in": codes}}
        if eid:
            match["entity_id"] = eid
        if per not in (None, ""):
            match["date"] = {"$lte": f"{tanggal_buku(per)}T23:59:59.999999"}
        pipe = [{"$match": match}, {"$unwind": "$lines"}, {"$match": {"lines.account_code": {"$in": codes}}},
                {"$group": {"_id": {"d": "$lines.debit", "c": "$lines.credit"}, "n": {"$sum": 1}}}]
        async for g in db.journal_entries.aggregate(pipe):
            k = g.get("_id") or {}
            total += int(g.get("n") or 0) * (to_cents(float(k.get("d") or 0)) - to_cents(float(k.get("c") or 0)))
    return -total if kredit else total


async def jatuh_tempo_tagihan(bill: Dict[str, Any], cache: Dict[str, int]) -> Tuple[Optional[str], str]:
    """(jatuh tempo `YYYY-MM-DD`, dasar) satu tagihan pemasok: `due_date` bila ada (dasar `due_date`), selain itu tanggal
    tagihan + `net_days` termin pemasok (dasar `bill_date`; pemasok tanpa termin = 0 hari, perilaku lama). `cache` =
    `{pemasok|PT: net_days}` per panggilan daftar."""
    due = _tgl_aman(bill.get("due_date"))
    if due:
        return due, "due_date"
    base = _tgl_aman(bill.get("bill_date") or bill.get("created_at"))
    if not base:
        return None, "bill_date"
    return (date.fromisoformat(base) + timedelta(days=await hari_termin_pemasok(
        bill.get("supplier_id") or "", bill.get("entity_id") or "", cache))).isoformat(), "bill_date"


async def hari_termin_pemasok(supplier_id: str, entity_id: str, cache: Optional[Dict[str, int]] = None) -> int:
    """`net_days` termin pembayaran pemasok (master Syarat Bayar lapisan PT); tanpa pemasok/termin = 0."""
    key = f"{supplier_id}|{entity_id}"
    if cache is not None and key in cache:
        return cache[key]
    hari = 0
    if supplier_id:
        sup = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0, "payment_term_code": 1})
        code = (sup or {}).get("payment_term_code") or ""
        if code:
            from services.supplier_service import resolve_payment_term
            hari = int((await resolve_payment_term(code, entity_id) or {}).get("net_days") or 0)
    if cache is not None:
        cache[key] = hari
    return hari
