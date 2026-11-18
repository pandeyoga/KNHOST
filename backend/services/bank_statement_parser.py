"""FASE G-8 — PARSER MUTASI BANK MULTI-FORMAT.

MASALAH NYATA
-------------
Setiap bank mengekspor rekening koran dengan bentuk berbeda: BCA memakai SATU kolom
nominal + penanda `DB/CR`, Mandiri/BNI memakai DUA kolom (Debet & Kredit), BRI memakai
kolom `Tipe` (D/K), Permata memakai desimal gaya Inggris. Tanggalnya pun beragam
(`12/07/2026`, `12-07-26`, `12 JUL 2026`, bahkan `12/07` tanpa tahun). Sebelum fase ini
impor mutasi hanya menerima CSV 4 kolom baku yang HARUS diketik ulang manusia — praktis
tidak dipakai.

DESAIN
------
Satu **template** (`bank_statement_formats`) menjelaskan cara membaca satu bentuk berkas:
delimiter, ada/tidak header, pemetaan kolom (berdasarkan NAMA header atau INDEKS),
gaya desimal, format tanggal, dan penanda arah dana. Template bisa dibuat/disunting user
tanpa deploy — 5 preset bawaan (BCA · Mandiri · BNI · BRI · Permata) hanya titik mulai.
Selain CSV/TSV, parser ini juga membaca **MT940** (`:61:`/`:86:`) dan **OFX** (`<STMTTRN>`)
yang dipakai bank untuk unduhan terstruktur, serta **Excel .xlsx** (`xlsx_to_text` → teks CSV → template yang sama).

Semua fungsi di sini MURNI (tanpa DB, tanpa jaringan) supaya bisa diuji cepat dan dipakai
untuk **pratinjau sebelum impor** — user melihat hasil baca sebelum satu baris pun masuk.
"""
import csv
import io
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ── Bulan Indonesia & Inggris (mis. "12 JUL 2026", "12 AGU 2026") ────────────
MONTHS = {
    "jan": 1, "feb": 2, "peb": 2, "mar": 3, "apr": 4, "mei": 5, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "agu": 8, "ags": 8, "sep": 9, "okt": 10, "oct": 10,
    "nov": 11, "des": 12, "dec": 12,
}

DEFAULT_IN_MARKERS = ("cr", "k", "kredit", "credit", "masuk", "c")
DEFAULT_OUT_MARKERS = ("db", "d", "debet", "debit", "keluar")

# Awalan berita transfer yang bukan nama pihak (dibuang saat menebak nama pengirim).
NOISE_PREFIXES = (
    "trsf e-banking cr", "trsf e-banking db", "trsf e-banking", "transfer masuk",
    "transfer keluar", "setoran kliring", "kliring masuk", "switching cr", "switching db",
    "tarikan atm", "biaya adm", "bunga", "pajak bunga", "transfer dr", "transfer ke",
    "incoming transfer", "outgoing transfer", "trf", "transfer",
)

# Pola nomor dokumen yang layak dipakai untuk pencocokan referensi
# (mis. `SO-0007`, `KSC/INV-00012`, `CASH-00003`).
RE_DOCNO = re.compile(r"\b([A-Z]{2,6}/)?[A-Z]{2,6}-?\d{3,6}\b", re.I)
RE_LONGNUM = re.compile(r"\b\d{6,}\b")


# ═══════════════════════════════════════════════════════════════════════════
#  PRESET BAWAAN — titik mulai, BUKAN aturan mati (user boleh mengubah)
# ═══════════════════════════════════════════════════════════════════════════
BUILTIN_FORMATS: List[Dict[str, Any]] = [
    {
        "bank_code": "bca", "name": "BCA — Rekening Koran (CSV)", "file_kind": "csv",
        "delimiter": ",", "has_header": True, "skip_rows": 0,
        "decimal_style": "id", "date_format": "dd/mm/yyyy",
        "columns": {"date": "tanggal", "description": "keterangan", "amount": "jumlah",
                    "direction": "db/cr", "balance": "saldo", "ref": ""},
        "in_markers": ["cr"], "out_markers": ["db"],
        "header_signature": ["tanggal", "keterangan", "jumlah"],
        "note": "Ekspor KlikBCA/myBCA: satu kolom Jumlah + penanda DB/CR. Tanggal bisa tanpa tahun.",
    },
    {
        "bank_code": "mandiri", "name": "Mandiri — Rekening Koran (CSV)", "file_kind": "csv",
        "delimiter": ",", "has_header": True, "skip_rows": 0,
        "decimal_style": "id", "date_format": "dd/mm/yyyy",
        "columns": {"date": "tanggal", "description": "keterangan", "amount_out": "debet",
                    "amount_in": "kredit", "balance": "saldo", "ref": "no. referensi"},
        "in_markers": [], "out_markers": [],
        "header_signature": ["tanggal", "keterangan", "debet", "kredit"],
        "note": "Dua kolom nominal: Debet (uang keluar) & Kredit (uang masuk).",
    },
    {
        "bank_code": "bni", "name": "BNI — Rekening Koran (CSV)", "file_kind": "csv",
        "delimiter": ",", "has_header": True, "skip_rows": 0,
        "decimal_style": "id", "date_format": "dd-mm-yyyy",
        "columns": {"date": "tanggal", "description": "uraian transaksi",
                    "amount_out": "debet", "amount_in": "kredit", "balance": "saldo"},
        "in_markers": [], "out_markers": [],
        "header_signature": ["tanggal", "uraian", "debet", "kredit"],
        "note": "Header BNI memakai 'Uraian Transaksi'.",
    },
    {
        "bank_code": "bri", "name": "BRI — Rekening Koran (CSV)", "file_kind": "csv",
        "delimiter": ",", "has_header": True, "skip_rows": 0,
        "decimal_style": "id", "date_format": "dd/mm/yyyy",
        "columns": {"date": "tanggal transaksi", "description": "uraian", "amount": "jumlah",
                    "direction": "tipe", "balance": "saldo"},
        "in_markers": ["k", "kredit", "cr"], "out_markers": ["d", "debet", "db"],
        "header_signature": ["tanggal transaksi", "uraian", "tipe"],
        "note": "BRI memakai kolom Tipe berisi D atau K.",
    },
    {
        "bank_code": "permata", "name": "Permata — Statement (CSV, desimal Inggris)",
        "file_kind": "csv", "delimiter": ",", "has_header": True, "skip_rows": 0,
        "decimal_style": "en", "date_format": "yyyy-mm-dd",
        "columns": {"date": "date", "description": "description", "amount_out": "debit",
                    "amount_in": "credit", "balance": "balance", "external_id": "reference"},
        "in_markers": [], "out_markers": [],
        "header_signature": ["date", "description", "debit", "credit"],
        "note": "Ekspor berbahasa Inggris dengan desimal 1,234.56.",
    },
    {
        "bank_code": "generic", "name": "MT940 (SWIFT) — semua bank", "file_kind": "mt940",
        "delimiter": "", "has_header": False, "skip_rows": 0,
        "decimal_style": "id", "date_format": "yymmdd", "columns": {},
        "in_markers": ["c"], "out_markers": ["d"], "header_signature": [":61:"],
        "note": "Format standar antarbank. Baris :61: = mutasi, :86: = keterangan.",
    },
    {
        "bank_code": "generic", "name": "OFX / QFX — semua bank", "file_kind": "ofx",
        "delimiter": "", "has_header": False, "skip_rows": 0,
        "decimal_style": "en", "date_format": "yyyymmdd", "columns": {},
        "in_markers": [], "out_markers": [], "header_signature": ["<STMTTRN>"],
        "note": "Nominal bertanda: negatif = uang keluar.",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  NILAI & TANGGAL
# ═══════════════════════════════════════════════════════════════════════════
def parse_amount(raw: Any, style: str = "auto") -> Tuple[float, bool]:
    """Ubah teks nominal menjadi angka. Return (nilai_absolut, bertanda_minus).

    `style`: `id` (1.234.567,89) · `en` (1,234,567.89) · `auto` (tebak dari pemisah
    TERAKHIR — cara ini benar untuk kedua gaya dan tidak menebak asal).
    """
    if raw is None:
        return 0.0, False
    s = str(raw).strip()
    if not s:
        return 0.0, False
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = re.sub(r"[^\d.,-]", "", s).lstrip("-")
    if not s:
        return 0.0, neg
    # Uji variasi isian (pelatihan 18 Nov): nominal yang JELAS bergaya lain dari template dulu terbaca 0 ("Nominal tidak
    # terbaca / nol"): "1,500,000.00" ditempel ke template BCA (desimal koma), "1.500.000,00" ke template berdesimal titik.
    # Gaya Indonesia tidak pernah memuat koma > 1 atau koma SEBELUM titik (dan sebaliknya) → dibaca sesuai gaya aslinya.
    # Pemisah ribuan selalu diikuti TEPAT 3 angka: "3240090.00" ke template BCA dulu dibaca 324.009.000 (×100, diam-diam)
    # — titik yang tidak diikuti 3 angka pasti titik desimal (sebaliknya "1500000,00" ke template bertitik desimal).
    # Bentuk yang ambigu ("1,500" · "1.500") tetap mengikuti template.
    def _bukan_ribuan(sep: str) -> bool:
        return any(len(g) != 3 for g in s.split(sep)[1:])

    if style == "id" and (s.count(",") > 1 or ("," in s and "." in s and s.rfind(".") > s.rfind(","))
                          or ("," not in s and "." in s and _bukan_ribuan("."))):
        style = "en"
    elif style == "en" and (s.count(".") > 1 or ("," in s and "." in s and s.rfind(",") > s.rfind("."))
                            or ("." not in s and "," in s and _bukan_ribuan(","))):
        style = "id"
    if style == "id":
        s = s.replace(".", "").replace(",", ".")
    elif style == "en":
        s = s.replace(",", "")
    else:  # auto
        last_dot, last_com = s.rfind("."), s.rfind(",")
        if last_dot > last_com:                 # desimal pakai titik
            s = s.replace(",", "")
        elif last_com > last_dot:               # desimal pakai koma
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(".", "").replace(",", "")
    try:
        return round(abs(float(s)), 2), neg
    except ValueError:
        return 0.0, neg


def strict_iso_date(s: Any) -> str:
    """G3 D4-BANK-01 — 'YYYY-MM-DD' hanya bila tanggal kalender sah (2026-02-30/13-01 → "")."""
    txt = str(s or "").strip()[:10]
    try:
        return datetime.strptime(txt, "%Y-%m-%d").strftime("%Y-%m-%d") if len(txt) == 10 else ""
    except ValueError:
        return ""


def parse_date(raw: Any, fmt: str = "auto", year_hint: int = 0) -> str:
    return strict_iso_date(_parse_date_loose(raw, fmt, year_hint))


def _parse_date_loose(raw: Any, fmt: str = "auto", year_hint: int = 0) -> str:
    """Ubah teks tanggal menjadi `YYYY-MM-DD` ("" bila tidak terbaca).

    Mendukung `dd/mm/yyyy`, `dd-mm-yy`, `yyyy-mm-dd`, `yyyymmdd`, `yymmdd`,
    `dd MMM yyyy` (bulan Indonesia/Inggris), dan **`dd/mm` tanpa tahun**
    (BCA) — tahunnya diambil dari `year_hint` (mis. tahun periode statement).
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    s = s.split(" ")[0] if (" " in s and re.match(r"^\d{4}-\d{2}-\d{2}", s)) else s
    y = year_hint or datetime.now().year

    # ISO / kompak
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if fmt == "yyyymmdd" and re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    if fmt == "yymmdd" and re.fullmatch(r"\d{6}", s):
        return f"20{s[0:2]}-{s[2:4]}-{s[4:6]}"
    if re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"

    # dd MMM yyyy / dd-MMM-yy
    m = re.match(r"^(\d{1,2})[\s./-]*([A-Za-z]{3,})[\s./-]*(\d{2,4})?$", s)
    if m:
        mon = MONTHS.get(m.group(2)[:3].lower())
        if mon:
            yy = m.group(3)
            year = int(yy) if yy and len(yy) == 4 else (2000 + int(yy) if yy else y)
            return f"{year:04d}-{mon:02d}-{int(m.group(1)):02d}"

    # dd/mm[/yyyy]  ·  dd-mm[-yy]
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?$", s)
    if m:
        d, mo, yy = int(m.group(1)), int(m.group(2)), m.group(3)
        if fmt.startswith("mm/"):            # format Amerika bila diminta eksplisit
            d, mo = mo, d
        year = int(yy) if yy and len(yy) == 4 else (2000 + int(yy) if yy else y)
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{year:04d}-{mo:02d}-{d:02d}"
    return ""


def counterparty_of(desc: str) -> str:
    """Tebak NAMA pihak lawan dari berita transfer (untuk skor kemiripan nama)."""
    s = (desc or "").strip()
    low = s.lower()
    for p in sorted(NOISE_PREFIXES, key=len, reverse=True):
        if low.startswith(p):
            s = s[len(p):]
            break
    s = re.sub(r"\b\d{4,}\b", " ", s)                 # buang nomor rekening/ref
    s = re.sub(r"[^A-Za-z0-9.&\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -.")
    return s[:80]


def ref_tokens_of(text: str) -> List[str]:
    """Kandidat nomor referensi di dalam teks (nomor dokumen & angka panjang)."""
    if not text:
        return []
    out = [m.group(0).upper() for m in RE_DOCNO.finditer(text)]
    out += RE_LONGNUM.findall(text)
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:6]


def desc_key(desc: str) -> str:
    """Sidik jari berita transfer untuk **pembelajaran aturan**.

    Angka dibuang (nomor referensi selalu berubah) sehingga dua transfer dari pihak
    yang sama menghasilkan kunci yang sama.
    """
    s = (desc or "").lower()
    s = re.sub(r"\d+", " ", s)
    s = re.sub(r"[^a-z\s]", " ", s)
    words = [w for w in s.split() if len(w) > 2]
    return " ".join(words[:8])


# ═══════════════════════════════════════════════════════════════════════════
#  PEMBACA PER JENIS BERKAS
# ═══════════════════════════════════════════════════════════════════════════
def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", str(h or "").strip().lower())


def _col_index(spec: Any, headers: List[str]) -> int:
    """Cari indeks kolom dari spesifikasi template (nama header ATAU indeks)."""
    if spec is None or spec == "":
        return -1
    if isinstance(spec, int):
        return spec
    if isinstance(spec, str) and spec.isdigit():
        return int(spec)
    want = _norm_header(spec)
    for i, h in enumerate(headers):
        if _norm_header(h) == want:
            return i
    for i, h in enumerate(headers):
        if want in _norm_header(h):
            return i
    return -1


def _dir_from_marker(val: str, fmt: Dict[str, Any]) -> str:
    """Baca penanda arah dana (`CR`/`DB`, `K`/`D`, `masuk`/`keluar`) dari satu sel.

    Ditulis ulang saat penutupan FASE G-8 (`KN-G8-DIR-SILENT`) karena dua celah:

    1. **Penanda tidak selalu berdiri sendiri.** Ekspor nyata menempelkannya pada kolom
       nominal (`"12.500.000,00 CR"`) atau menggesernya ke kolom sebelah karena koma
       desimal Indonesia bertabrakan dengan pemisah CSV. Karena itu penanda dicari
       **di mana pun** dalam sel — tetapi hanya sebagai **kata utuh**.
    2. **`startswith` polos salah baca.** `"KREDITUR"` (nama pihak) dulu terbaca sebagai
       `kredit` = uang masuk. Sekarang batas kata (`\\b`) mencegahnya.

    Bila satu sel memuat penanda masuk DAN keluar sekaligus (mis. sisa baris header
    `"DB/CR"`), hasilnya **kosong** — ambigu tidak pernah ditebak; pemanggil akan
    menolak barisnya.
    """
    v = _norm_header(val)
    if not v:
        return ""
    ins = [m.lower() for m in (fmt.get("in_markers") or DEFAULT_IN_MARKERS) if m]
    outs = [m.lower() for m in (fmt.get("out_markers") or DEFAULT_OUT_MARKERS) if m]
    if v in ins:
        return "in"
    if v in outs:
        return "out"

    def found(markers: List[str]) -> bool:
        return any(re.search(rf"(?<![a-z]){re.escape(m)}(?![a-z])", v) for m in markers)

    hit_in, hit_out = found(ins), found(outs)
    if hit_in and not hit_out:
        return "in"
    if hit_out and not hit_in:
        return "out"
    return ""


def _sniff_delimiter(sample: str, default: str = ",") -> str:
    counts = {d: sample.count(d) for d in (",", ";", "\t", "|")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else default


def parse_csv(raw: str, fmt: Dict[str, Any], year_hint: int = 0) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text.strip():
        return rows, [{"row": 0, "reason": "Berkas/teks kosong", "raw": ""}]
    first = next((ln for ln in text.split("\n") if ln.strip()), "")
    delim = fmt.get("delimiter") or _sniff_delimiter(first)
    if delim == "\\t":
        delim = "\t"
    # Uji variasi isian (pelatihan 18 Nov): teks yang disalin dari Excel / tabel KlikBCA berpemisah TAB (atau ";"),
    # sedangkan template BCA ber-koma → seluruh baris menjadi satu kolom dan setiap baris ditolak "Tanggal tidak
    # terbaca". Pemisah lain yang jelas (≥ 2 kali dan lebih sering dari pemisah template di baris pertama) dipakai.
    # Salinan dari PDF (kolom dipisah ≥ 2 spasi, tanpa pemisah apa pun) → spasi berderet dijadikan TAB.
    hitung = {d: first.count(d) for d in ("\t", ";", "|", ",")}
    lain = max((d for d in ("\t", ";", "|") if d != delim), key=lambda d: hitung[d])
    if hitung[lain] >= 2 and hitung[lain] > hitung.get(delim, first.count(delim)):
        delim = lain
    elif not any(hitung.values()) and re.search(r"\S {2,}\S", first):
        text = "\n".join(re.sub(r" {2,}", "\t", ln.strip()) for ln in text.split("\n"))
        delim = "\t"
    reader = list(csv.reader(io.StringIO(text), delimiter=delim))
    skip = int(fmt.get("skip_rows") or 0)
    reader = reader[skip:]
    if not reader:
        return rows, [{"row": 0, "reason": "Tidak ada baris setelah skip_rows", "raw": ""}]

    headers: List[str] = []
    body = reader
    if fmt.get("has_header", True):
        headers = [str(c) for c in reader[0]]
        body = reader[1:]

    cols = fmt.get("columns") or {}
    i_date = _col_index(cols.get("date"), headers)
    i_desc = _col_index(cols.get("description"), headers)
    i_amt = _col_index(cols.get("amount"), headers)
    i_in = _col_index(cols.get("amount_in"), headers)
    i_out = _col_index(cols.get("amount_out"), headers)
    i_dir = _col_index(cols.get("direction"), headers)
    i_ref = _col_index(cols.get("ref"), headers)
    i_bal = _col_index(cols.get("balance"), headers)
    i_ext = _col_index(cols.get("external_id"), headers)
    style = fmt.get("decimal_style") or "auto"
    dfmt = fmt.get("date_format") or "auto"
    # Uji variasi isian (pelatihan 18 Nov): baris judul kolom tidak ikut ditempel → baris data pertama dipakai sebagai
    # judul, kolom tidak ketemu, dan pratinjau diam-diam "Terbaca 0 baris" tanpa alasan. Kini ditolak dengan arahan.
    if fmt.get("has_header", True):
        hilang = []
        if i_date < 0:
            hilang.append("tanggal")
        if i_amt < 0 and i_in < 0 and i_out < 0:
            hilang.append("nominal (jumlah / debet-kredit)")
        if hilang:
            contoh = ", ".join(str(s) for s in (fmt.get("header_signature") or []) if s)
            return rows, [{"row": 0, "raw": delim.join(headers)[:160], "reason": (
                f"Baris judul kolom tidak dikenali — kolom {' & '.join(hilang)} tidak ditemukan. Baris pertama harus judul "
                f"kolom rekening koran ({contoh or 'sesuai template'}); salin juga baris judulnya, atau pilih template yang "
                f"cocok.")}]

    def cell(r: List[str], idx: int) -> str:
        return str(r[idx]).strip() if 0 <= idx < len(r) else ""

    for n, r in enumerate(body, start=1):
        if not any(str(c).strip() for c in r):
            continue
        raw_line = delim.join(str(c) for c in r)
        stmt_date = parse_date(cell(r, i_date), dfmt, year_hint)
        desc = cell(r, i_desc)
        amount, neg = 0.0, False
        direction = ""
        two_col = i_in >= 0 or i_out >= 0
        if two_col:
            a_in, _ = parse_amount(cell(r, i_in), style)
            a_out, _ = parse_amount(cell(r, i_out), style)
            if a_in > 0:
                amount, direction = a_in, "in"
            elif a_out > 0:
                amount, direction = a_out, "out"
        else:
            amt_cell = cell(r, i_amt)
            amount, neg = parse_amount(amt_cell, style)
            # 1) kolom arah dana yang ditunjuk template
            if i_dir >= 0:
                direction = _dir_from_marker(cell(r, i_dir), fmt)
            # 2) penanda menempel pada kolom nominal ("12.500.000,00 CR")
            if not direction:
                direction = _dir_from_marker(amt_cell, fmt)
            # 3) nominal bertanda minus = pernyataan eksplisit uang keluar (gaya OFX/ekspor Inggris)
            if not direction and neg:
                direction = "out"
        if amount <= 0:
            isi = cell(r, i_amt) if not two_col else f"{cell(r, i_in)}/{cell(r, i_out)}"
            errors.append({"row": n, "reason": f"Nominal tidak terbaca / nol ('{isi[:40]}')", "raw": raw_line[:160]})
            continue
        if not stmt_date:
            errors.append({"row": n, "reason": f"Tanggal tidak terbaca ('{cell(r, i_date)[:40]}')", "raw": raw_line[:160]})
            continue
        # ── KN-G8-DIR-SILENT (P1, uang) ───────────────────────────────────────────
        # DULU: bila penanda arah tidak terbaca, baris DIAM-DIAM dianggap uang MASUK.
        # Akibatnya baris biaya bank ("BIAYA ADM … DB") pada ekspor tanpa tanda kutip
        # (koma desimal Indonesia menggeser kolom) masuk sebagai UANG MASUK: saldo
        # rekening, "selisih rekening vs buku", bahkan kandidat pencocokan ke kwitansi
        # piutang menjadi salah — tanpa satu pun peringatan.
        # SEKARANG: arah dana tidak pernah ditebak. Baris yang arahnya tak bisa
        # dipastikan DITOLAK dengan arahan perbaikan dan ikut dilaporkan di pratinjau.
        if not direction:
            errors.append({
                "row": n,
                "reason": ("Arah dana (masuk/keluar) tidak bisa dipastikan — sistem tidak "
                           "menebak uang. Periksa kolom penanda DB/CR pada template, atau "
                           "bungkus nominal dengan tanda kutip bila koma desimal membuat "
                           "kolom bergeser."),
                "raw": raw_line[:160],
            })
            continue
        bal, _ = parse_amount(cell(r, i_bal), style) if i_bal >= 0 else (0.0, False)
        rows.append({
            "row": n, "stmt_date": stmt_date, "amount": amount, "direction": direction,
            "description": desc, "ref": cell(r, i_ref), "external_id": cell(r, i_ext),
            "balance": bal, "raw": raw_line[:200],
        })
    return rows, errors


RE_MT940_61 = re.compile(
    r"^:61:(?P<vdate>\d{6})(?P<edate>\d{4})?(?P<mark>R?[CD])(?P<funds>[A-Z])?(?P<amt>\d[\d.,]*)"
    r"(?P<code>[A-Z]\w{3})?(?P<rest>.*)$")


def parse_mt940(raw: str, fmt: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    for n, line in enumerate((raw or "").replace("\r", "").split("\n"), start=1):
        line = line.strip()
        if line.startswith(":61:"):
            m = RE_MT940_61.match(line)
            if not m:
                errors.append({"row": n, "reason": "Baris :61: tidak dikenal", "raw": line[:160]})
                continue
            amt, _ = parse_amount(m.group("amt"), "id")
            vdate = parse_date(m.group("vdate"), "yymmdd")
            if not vdate or amt <= 0:
                errors.append({"row": n, "reason": "Tanggal valuta tidak sah" if not vdate else "Nominal nol",
                               "raw": line[:160]})
                if cur:
                    rows.append(cur)
                cur = None
                continue
            if cur:
                rows.append(cur)
            mark = m.group("mark")
            # G3 D4-BANK-02 — RC = pembalikan kredit (uang keluar), RD = pembalikan debit (uang masuk).
            direction = {"C": "in", "D": "out", "RC": "out", "RD": "in"}[mark]
            rest = (m.group("rest") or "").replace("//", " ").strip()
            cur = {
                "row": n, "stmt_date": vdate, "reversal": mark.startswith("R"), "mark": mark,
                "amount": amt, "direction": direction,
                "description": rest, "ref": "", "external_id": "", "balance": 0.0,
                "raw": line[:200],
            }
        elif line.startswith(":86:") and cur is not None:
            extra = line[4:].strip()
            cur["description"] = (cur["description"] + " " + extra).strip()
    if cur:
        rows.append(cur)
    rows = [r for r in rows if r["amount"] > 0 and r["stmt_date"]]
    if not rows and not errors:
        errors.append({"row": 0, "reason": "Tidak ada baris :61: yang terbaca", "raw": ""})
    return rows, errors


def _ofx_tag(block: str, tag: str) -> str:
    m = re.search(rf"<{tag}>([^<\r\n]*)", block, re.I)
    return (m.group(1) or "").strip() if m else ""


def parse_ofx(raw: str, fmt: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", raw or "", re.S | re.I)
    for n, b in enumerate(blocks, start=1):
        amt_raw = _ofx_tag(b, "TRNAMT")
        amount, neg = parse_amount(amt_raw, "en")
        dt = _ofx_tag(b, "DTPOSTED")[:8]
        name = _ofx_tag(b, "NAME")
        memo = _ofx_tag(b, "MEMO")
        if amount <= 0 or not dt or not parse_date(dt, "yyyymmdd"):
            errors.append({"row": n, "reason": "STMTTRN tanpa nominal/tanggal sah", "raw": b[:160]})
            continue
        rows.append({
            "row": n, "stmt_date": parse_date(dt, "yyyymmdd"), "amount": amount,
            "direction": "out" if neg else "in",
            "description": " ".join(x for x in (name, memo) if x),
            "ref": _ofx_tag(b, "CHECKNUM"), "external_id": _ofx_tag(b, "FITID"),
            "balance": 0.0, "raw": b.strip()[:200],
        })
    if not blocks:
        errors.append({"row": 0, "reason": "Tidak ada blok <STMTTRN>", "raw": ""})
    return rows, errors


def parse_rows(raw: str, fmt: Dict[str, Any], year_hint: int = 0) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Baca mutasi sesuai template. Return (baris_sah, kesalahan_per_baris)."""
    kind = (fmt.get("file_kind") or "csv").lower()
    if kind == "mt940":
        rows, errors = parse_mt940(raw, fmt)
    elif kind == "ofx":
        rows, errors = parse_ofx(raw, fmt)
    else:
        rows, errors = parse_csv(raw, fmt, year_hint)
    for r in rows:
        r["counterparty"] = counterparty_of(r.get("description", ""))
        r["desc_key"] = desc_key(r.get("description", ""))
        if not r.get("ref"):
            toks = ref_tokens_of(r.get("description", ""))
            r["ref"] = toks[0] if toks else ""
    return rows, errors


# ═══════════════════════════════════════════════════════════════════════════
#  EXCEL (.xlsx) — rekening koran yang diunduh bank sebagai lembar kerja
# ═══════════════════════════════════════════════════════════════════════════
# Unduhan internet banking (KlikBCA Bisnis, Livin' Mandiri, BRI CMS, BNI Direct) umumnya Excel: beberapa baris
# pembuka (nomor rekening, periode), tabel mutasi, lalu baris ringkasan saldo di bawah baris kosong. Lembar itu
# diubah menjadi teks CSV lalu dibaca dengan TEMPLATE yang sama seperti CSV — tidak ada aturan baca kedua.
XLSX_MAX_BYTES = 5 * 1024 * 1024
XLSX_MAX_ROWS = 20000
XLSX_HEADER_SCAN = 60          # baris pembuka yang diperiksa untuk mencari judul kolom


class StatementFileError(ValueError):
    """Berkas rekening koran tidak bisa dibaca (bukan .xlsx, .xls lama, rusak, terlalu besar)."""


def is_xlsx(data: bytes) -> bool:
    return bytes(data[:4]) == b"PK\x03\x04"


def is_legacy_xls(data: bytes) -> bool:
    return bytes(data[:8]) == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _xlsx_cell(v: Any) -> str:
    """Nilai sel → teks yang dibaca parser CSV. Tanggal Excel → ISO (diterima template mana pun); angka → tanpa
    pemisah ribuan dengan titik desimal (`parse_amount` mengenalinya di template bergaya Indonesia maupun Inggris)."""
    from datetime import date
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:.2f}"
    return re.sub(r"\s+", " ", str(v)).strip()


def _row_has_signature(cells: List[str], sig: List[str]) -> bool:
    low = [_norm_header(c) for c in cells if c]
    return bool(low) and all(any(s in c for c in low) for s in sig)


def xlsx_to_text(data: bytes, formats: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Lembar Excel rekening koran → teks CSV (judul kolom di baris pertama) untuk `parse_rows`.

    Lembar yang dipakai = lembar pertama yang memuat baris judul kolom salah satu template (`header_signature`);
    baris di atasnya (nama rekening, periode) dibuang, dan tabel berhenti di baris kosong pertama sesudahnya
    (ringkasan saldo awal/akhir tidak ikut). Tanpa judul dikenali → lembar pertama dari baris berisi pertama, dan
    template yang dipilih/terdeteksi menentukan hasilnya seperti CSV biasa.
    """
    if not data:
        raise StatementFileError("Berkas kosong.")
    if len(data) > XLSX_MAX_BYTES:
        raise StatementFileError(f"Berkas Excel lebih dari {XLSX_MAX_BYTES // (1024 * 1024)} MB — unduh per periode yang lebih pendek.")
    if is_legacy_xls(data):
        raise StatementFileError("Berkas .xls (Excel 97–2003) belum bisa dibaca — buka di Excel lalu Simpan Sebagai "
                                 "'Excel Workbook (.xlsx)', atau unduh rekening koran dalam bentuk CSV.")
    if not is_xlsx(data):
        raise StatementFileError("Berkas bukan Excel .xlsx yang sah.")
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 — isi berkas dari luar; pesan untuk pengguna
        raise StatementFileError(f"Berkas Excel tidak bisa dibuka ({type(exc).__name__}) — simpan ulang sebagai .xlsx.") from exc
    sigs = [[str(s).lower() for s in (f.get("header_signature") or []) if s]
            for f in formats if (f.get("file_kind") or "csv").lower() == "csv"]
    sigs = [s for s in sigs if s]
    first: Optional[Tuple[str, List[List[str]]]] = None
    chosen: Optional[Tuple[str, List[List[str]], int]] = None
    try:
        for ws in wb.worksheets:
            rows: List[List[str]] = []
            for i, r in enumerate(ws.iter_rows(values_only=True)):
                if i >= XLSX_MAX_ROWS:
                    break
                rows.append([_xlsx_cell(v) for v in r])
            if first is None:
                first = (ws.title, rows)
            hit = next((i for i, r in enumerate(rows[:XLSX_HEADER_SCAN])
                        if any(_row_has_signature(r, s) for s in sigs)), None)
            if hit is not None:
                chosen = (ws.title, rows, hit)
                break
    finally:
        wb.close()
    if chosen:
        title, rows, start = chosen
    else:
        title, rows = first or ("", [])
        start = next((i for i, r in enumerate(rows) if any(r)), 0)
    table: List[List[str]] = []
    for r in rows[start:]:
        if not any(r):
            if table:
                break
            continue
        table.append(r)
    if not table:
        raise StatementFileError("Lembar Excel kosong — tidak ada tabel mutasi.")
    width = max(max((i for i, c in enumerate(r) if c), default=-1) for r in table) + 1
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for r in table:
        writer.writerow((r + [""] * width)[:width])
    return {"text": out.getvalue(), "sheet": title, "header_row": (start + 1) if chosen else 0,
            "rows": max(len(table) - 1, 0), "header_found": bool(chosen)}


def detect_format(raw: str, formats: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Tebak template dari tanda tangan header/isi berkas (nilai tertinggi menang)."""
    text = (raw or "")[:4000]
    low = text.lower()
    best, best_score = None, 0
    for f in formats:
        sig = [str(s).lower() for s in (f.get("header_signature") or []) if s]
        if not sig:
            continue
        hit = sum(1 for s in sig if s in low)
        if hit and hit == len(sig) and hit > best_score:
            best, best_score = f, hit
    return best
