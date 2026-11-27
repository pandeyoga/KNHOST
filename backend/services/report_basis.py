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

CR-T2 (b) — jatuh tempo `baris_tagihan` dibaca dari jadwal tagihan tersimpan (`billing_schedule_service`, satu-satunya
pembaca jatuh tempo); `hari_termin` + `jatuh_tempo` = satu rumus jatuh tempo untuk semua pembaca. Uang dihitung dalam sen bulat
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
    Bahan `hari_termin` (aturan termin yang ada: snapshot hari termin pesanan → kode termin pesanan →
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


def hari_termin(customer: Dict[str, Any], order: Dict[str, Any],
                terms: Optional[Dict[Any, Optional[int]]] = None) -> int:
    """CR-T2 — hari termin satu pesanan, SATU aturan untuk umur piutang, jadwal tagihan, proyeksi kas, nota debit, denda
    pesanan tanpa rencana, dan selisih bayar (dipindah dari `customer_service._term_days`, D8):

    1. snapshot hari termin pesanan (`payment_term_days`) menang; G3 D4-FIN-02 — termin 0 (tunai/COD) tetap 0;
    2. F-16 — kode termin pesanan di `terms` (`peta_termin`: CBD = 0, NET30 = 30, DP50 = 14, …) SEBELUM profil pelanggan
       (pesanan CBD tidak tampil "30 hari lagi" hanya karena profil pelanggannya NET30);
    3. profil pelanggan (`payment_profile.term_days`);
    4. 30."""
    pp = (customer or {}).get("payment_profile") or {}
    if order.get("payment_term_days") not in (None, ""):
        try:
            return max(0, int(order["payment_term_days"]))
        except (TypeError, ValueError):
            pass
    code = order.get("payment_term_code") or ""
    if terms is not None and code:
        nd = terms.get((code, order.get("entity_id") or ""))
        if nd is not None:
            return max(0, int(nd))
    if pp.get("term_days") not in (None, ""):
        try:
            return max(0, int(pp["term_days"]))
        except (TypeError, ValueError):
            pass
    return 30


def jatuh_tempo(tanggal: Any, hari: int) -> str:
    """CR-T2 — SATU rumus jatuh tempo: tanggal buku WIB `tanggal` + `hari` hari kalender (`YYYY-MM-DD`). Dipakai
    `baris_tagihan` (PK-41) dan pembangun jadwal tagihan (`billing_schedule_service.bangun_baris`)."""
    return (_tgl(tanggal) + timedelta(days=int(hari or 0))).isoformat()


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


SUMBER_UANG_MUKA = "uang_muka"     # CR-T2 — baris uang muka jadwal tagihan (termin ber-DP, jatuh tempo saat konfirmasi)
SUMBER_RENCANA = "rencana"         # CR-T2 — baris rencana cicilan buatan orang (`payment_plans` `origin: manual`)


def _sumber_baris(r: Dict[str, Any]) -> str:
    """Jenis baris jadwal tagihan → `sumber` baris tagihan (bentuk PK-41)."""
    if r.get("origin") == "manual":
        return SUMBER_RENCANA
    if r.get("kind") == "dp":
        return SUMBER_UANG_MUKA
    if r.get("kind") == "debit_note":
        return SUMBER_NOTA_DEBIT
    return SUMBER_PESANAN if r.get("source_type") == "order" else SUMBER_SURAT_JALAN


async def baris_tagihan(orders: List[Dict[str, Any]], customers: Dict[str, Dict[str, Any]], *,
                        per: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Per pesanan piutang (`pesanan_piutang`), daftar baris tagihan posisi tanggal `per` (kosong = hari ini WIB):

    `{sumber, ref_id, ref_number, tanggal, jatuh_tempo, nilai, terbayar, sisa, hari_lewat, jurnal_id, jurnal_number,
    tercatat}` (+ CR-T2: `line_id`, `plan_id`, `kind`, `label`).

    CR-T2 (b) — jatuh tempo dibaca dari JADWAL TAGIHAN (`billing_schedule_service.lines_for_orders`, pembaca yang sama
    dengan `open_lines`): jadwal tersimpan (`payment_plans`), atau — pesanan yang belum berjadwal — pembangun baris yang
    sama tanpa disimpan. Rumus jatuh tempo SATU: `jatuh_tempo(tanggal, hari_termin(...))`.

    1. Baris jadwal — surat jalan (nilai = Σ debit akun piutang jurnal semua dokumen bernomor itu), uang muka (termin
       ber-DP, jatuh tempo = tanggal konfirmasi), nota debit (PK-32), atau baris rencana cicilan; baris termin hanya
       yang lahir ≤ `per`. Pembayaran bertanggal ≤ `per` (tanpa nota kredit tertangguh) dialokasikan: dulu yang menunjuk
       baris, lalu mulai jatuh tempo tertua; kelebihannya `uang_muka`.
    2. Baris belum dikirim — `nilai = max(0, nilai tagihan − Σ nilai baris jadwal − uang_muka − Σ nota tertangguh)`
       (nilai tagihan = `_order_grand_total`), tanpa jatuh tempo, `hari_lewat = 0`.
    3. `tercatat` — bagian sisa baris yang sudah ada di akun piutang: tercatat pesanan = min(Σ sisa, max(0, pengakuan
       piutang ≤ `per` − terbayar)) dibagi ke baris mulai jatuh tempo tertua (baris belum dikirim terakhir). Untuk
       pesanan tanpa uang muka/rencana sama dengan sisa baris surat jalan (perilaku PK-41).
    4. `hari_lewat = hari_antara(jatuh_tempo, per)`; baris bersisa ≤ 0,01 dibuang (daftar boleh kosong = lunas).
    """
    from services import billing_schedule_service as bss
    from services.customer_service import _order_grand_total
    per_tgl = tanggal_buku(per)
    hidup = [o for o in orders if o.get("id") and pesanan_piutang(o)]
    jadwal = await bss.lines_for_orders(hidup, customers, per=per_tgl)
    jurnal = await _jurnal_pendapatan([o["id"] for o in hidup])
    kode_cache: Dict[str, set] = {}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for o in hidup:
        info = jadwal.get(o["id"]) or {"rows": [], "uang_muka": 0.0}
        baris: List[Dict[str, Any]] = []
        ditagih = 0
        for r in info["rows"]:
            ditagih += to_cents(r["amount"])
            sumber = _sumber_baris(r)
            sj, nd = sumber == SUMBER_SURAT_JALAN, sumber == SUMBER_NOTA_DEBIT
            baris.append({
                "sumber": sumber,
                "ref_id": ((r.get("shipment_ids") or [""])[0] if sj else (r.get("source_id") if nd else o["id"])),
                "ref_number": (r.get("source_id") if sj else (r.get("debit_note_number") or o.get("number") or o["id"])),
                "tanggal": r.get("billed_at"), "jatuh_tempo": r["due_date"], "nilai": r["amount"],
                "terbayar": r["paid_amount"], "sisa": r["outstanding"],
                "hari_lewat": r["days_late"] if r["due_date"] else 0,
                "jurnal_id": (r.get("journal_ids") or [""])[0], "jurnal_number": (r.get("journal_numbers") or [""])[0],
                "line_id": r.get("line_id") or "", "plan_id": r.get("plan_id") or "", "kind": r.get("kind") or "",
                "label": r.get("label") or ""})
        uang_muka = to_cents(info["uang_muka"])
        tangguh = max(0, _terbayar_sen(o, per_tgl, tangguh=True))
        belum = max(0, to_cents(_order_grand_total(o)) - ditagih - uang_muka - tangguh)
        if from_cents(belum) > EPS:
            baris.append({"sumber": SUMBER_BELUM_DIKIRIM, "ref_id": o["id"], "ref_number": o.get("number") or o["id"],
                          "tanggal": None, "jatuh_tempo": None, "nilai": from_cents(belum), "terbayar": 0.0,
                          "sisa": from_cents(belum), "hari_lewat": 0, "uang_muka": from_cents(uang_muka),
                          "jurnal_id": "", "jurnal_number": "", "line_id": "", "plan_id": "", "kind": "",
                          "label": ""})
        baris = [b for b in baris if b["sisa"] > EPS]
        akui = await bss.recognized_sen(o, jurnal.get(o["id"], []), kode_cache, per=per_tgl)
        sisa_total = sum(to_cents(b["sisa"]) for b in baris)
        tercatat = min(sisa_total, max(0, akui - max(0, _terbayar_sen(o, per_tgl, tangguh=False))))
        for b in baris:   # urutan: jatuh tempo tertua dulu (jadwal), belum dikirim terakhir
            bagian = min(to_cents(b["sisa"]), tercatat)
            b["tercatat"] = from_cents(bagian)
            tercatat -= bagian
        out[o["id"]] = baris
    return out


# ── Arus kas ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def kode_kas(scope: Any) -> set:
    """Akun kas & setara kas laporan bercakupan `scope` (saringan Mongo `{"entity_id": …}`, atau id satu PT): semua akun
    yang pernah dipakai `kas_bank.kas_besar` dan `kas_bank.kas_kecil` (bawaan + pemetaan + riwayat; satu PT = lapisan PT
    itu) ∪ akun bertanda `is_cash` / `cash_equivalent` di bagan akun efektif — termasuk sub-akun rekening (Kas & Bank 1).
    Satu pembantu untuk semua pembaca saldo kas (Arus Kas, posisi kas, Dasbor Keuangan, Proyeksi Arus Kas)."""
    from services import financial_statement_service as fs
    from services.gl_mapping_service import known_codes
    if isinstance(scope, str):
        scope = {"entity_id": scope} if scope else None
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


def tercatat_sen(r: Dict[str, Any]) -> int:
    """Bagian sisa satu baris tagihan yang sudah tercatat di akun piutang (sen). Baris tanpa `tercatat` (pembuat lain):
    baris terkirim = seluruh sisanya, belum dikirim = 0 (aturan PK-41)."""
    if "tercatat" in r:
        return to_cents(r["tercatat"])
    return 0 if r["sumber"] == SUMBER_BELUM_DIKIRIM else to_cents(r["sisa"])


def ringkas_baris(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ringkasan baris tagihan satu pesanan (sen bulat → rupiah): `total` = Σ sisa, `ar_ledger` = Σ bagian tercatat di
    akun piutang (`tercatat`), `exposure` = `total − ar_ledger`, `tagih` = Σ sisa baris berjatuh tempo (yang bisa
    ditagih: surat jalan, uang muka, nota debit, baris rencana), `overdue` = Σ sisa baris lewat jatuh tempo,
    `oldest_days` = hari lewat terlama (0 bila tidak ada), `due_date` = jatuh tempo tertua baris berjatuh tempo yang masih
    bersisa (None = belum dikirim). CR-T2 — sebelum ada baris uang muka/rencana, `tercatat` = sisa baris terkirim, jadi
    `ar_ledger` = `tagih` dan `exposure` = Σ baris belum dikirim (PK-41)."""
    kirim = [r for r in rows if r["sumber"] != SUMBER_BELUM_DIKIRIM]
    lewat = [r for r in kirim if r["hari_lewat"] > 0]
    total = sum(to_cents(r["sisa"]) for r in rows)
    ledger = sum(tercatat_sen(r) for r in rows)
    return {"total": from_cents(total),
            "ar_ledger": from_cents(ledger),
            "exposure": from_cents(total - ledger),
            "tagih": from_cents(sum(to_cents(r["sisa"]) for r in kirim)),
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
