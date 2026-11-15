"""KM-T2 (keputusan K-19, K-20, K-21, K-23, K-24) — **Capaian**: angka dasar insentif per sales, per PT dan periode.

Modul ini HANYA MEMBACA. Ia tidak menghitung dan tidak menyimpan nominal insentif (itu lembar insentif, KM-T3). Sumber:

    fact_shipment_sales   omzet terkirim (`kirim`, `pesanan_lama`), retur & koreksi, nilai acuan harga, biaya  (KM-T1)
    fact_collections      pencairan per baris pembayaran × sales, jenis sumber dana, pembalik, `settles_order` (KM-T1)
    fact_sales_lines      nilai bersih per baris pesanan (`net_alloc`) — hanya untuk dasar omzet `pesanan` / `lunas`
    sales_targets         target per (PT, sales, jenis periode, periode)                                         (KM-T1)
    ar_aging_service      sisa piutang & lewat jatuh tempo per pelanggan per tanggal (PK-41, per surat jalan)

Arti angka mengikuti versi definisi PT (`incentive_definitions.current_definition`, empat kunci `insentif.*`):
    dasar_omzet    terkirim → Σ `net` `kirim` + `pesanan_lama` bertanggal dalam periode
                   pesanan  → Σ `fact_sales_lines.net_alloc` pesanan hidup bertanggal pesanan dalam periode
                   lunas    → Σ `net_alloc` pesanan yang baris `settles_order` TERAKHIRNYA bertanggal dalam periode
    isi_pencairan  uang_masuk → jenis `kas`, `deposit`, `titipan_bank` (termasuk pembaliknya) · semua_baris → semua jenis
    pemilik_angka  sales_pesanan → `sales_id` fakta (potret pembagian tim, K-21) · pemilik_pelanggan → sales penanggung
                   jawab pelanggan SAAT INI (`customers.assigned_sales_id`)
    harga_acuan    daftar_pt → `list_value` · umum → `global_value` · batas_bawah → `floor_value`

Uang dihitung dalam SEN BULAT, dibulatkan ke rupiah penuh sekali (`_rp`, `02_STANDAR.md` §5 D5); total = Σ baris. Persen
satu desimal (setengah ke atas). Satu pengumpul (`_kumpulkan`) dipakai tabel, telusur, dan ekspor, sehingga jumlah
daftar telusur selalu sama dengan angka sel yang dibuka (D4).
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from core_utils import from_cents, rupiah, to_cents
from db import db
from services import incentive_periods as ip

# ── Pesan (siap tampil) ──────────────────────────────────────────────────────────────────────────────────────────────
PESAN_SEMUA_PT = "Pilih satu PT untuk melihat Capaian. Definisi angka berbeda di tiap PT."
PESAN_PERIODE = ip.PESAN_PERIODE
PESAN_RENTANG_PANJANG = "Rentang tanggal paling panjang 366 hari."
PESAN_RENTANG = "Rentang tanggal tidak sah. Isi tanggal awal dan akhir, contoh: 2026-10-01 dan 2026-10-31."
PESAN_KUMULATIF = "Kumulatif tahun berjalan hanya untuk jenis periode Bulan."
PESAN_BANDING = "Pembanding harus Tidak, Periode sebelumnya, atau Periode sama tahun lalu."
PESAN_KELOMPOK = "Kelompokkan menurut Sales, Pelanggan, Kategori produk, atau Sumber harga."
PESAN_METRIK = "Angka yang bisa ditelusuri: omzet, retur, atau uang masuk."
PESAN_KUNCI = "Pilih baris yang ditelusuri."
CATATAN_UANG_PRODUK = ("Uang masuk dan piutang tidak bisa dipecah per kategori produk, lini, atau sumber harga: "
                       "kwitansi dialokasikan per pesanan, bukan per baris barang.")

PERIOD_TYPES = ("month", "quarter", "year", "range")
GROUPS = ("sales", "customer", "category", "price_source")
COMPARES = ("none", "prev", "yoy")
METRICS = ("omzet", "retur", "uang_masuk")
METRIC_LABEL = {"omzet": "Omzet", "retur": "Retur", "uang_masuk": "Uang masuk"}
OMZET_KINDS = ("kirim", "pesanan_lama")
RETUR_KINDS = ("retur", "koreksi")
MARGIN_KINDS = ("kirim", "pesanan_lama", "retur")
UANG_MASUK_KINDS = ("kas", "deposit", "titipan_bank")
ACUAN_FIELD = {"daftar_pt": "list_value", "umum": "global_value", "batas_bawah": "floor_value"}
ACUAN_LABEL = {"daftar_pt": "harga daftar PT", "umum": "harga umum", "batas_bawah": "batas bawah harga"}
TANPA_SALES = "Tanpa sales"
PRICE_SOURCE_LABEL = {"special_approval": "Harga khusus", "customer": "Harga pelanggan", "entity": "Harga PT",
                      "global": "Harga umum", "special_order": "Pesanan khusus", "": "Sumber harga tidak tercatat"}
SOURCE_KIND_LABEL = {"kirim": "Surat jalan", "pesanan_lama": "Pesanan (jurnal per pesanan)", "pesanan": "Pesanan dibuat",
                     "lunas": "Pesanan lunas", "retur": "Nota kredit retur", "koreksi": "Nota koreksi",
                     "kas": "Kwitansi", "deposit": "Pakai deposit", "titipan_bank": "Titipan bank",
                     "saldo_kredit": "Saldo kredit", "nota_kredit": "Nota kredit", "hapus_sisa": "Hapus sisa",
                     "kasus": "Kasus keuangan"}
_BLN_PENDEK = ("", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
KELOMPOK = 1000

_PROJ_SHIP = {"_id": 0, "source_kind": 1, "source_id": 1, "source_number": 1, "so_id": 1, "so_number": 1,
              "customer_id": 1, "customer_name": 1, "sales_id": 1, "split": 1, "category": 1, "line_code": 1,
              "price_source": 1, "net": 1, "list_value": 1, "global_value": 1, "floor_value": 1, "cost": 1,
              "cost_known": 1, "date_wib": 1}
_PROJ_COLL = {"_id": 0, "so_id": 1, "so_number": 1, "customer_id": 1, "sales_id": 1, "split": 1, "receipt_id": 1,
              "receipt_number": 1, "source_kind": 1, "is_reversal": 1, "amount": 1, "date_wib": 1,
              "giro_uncleared": 1}
_PROJ_LINE = {"_id": 0, "so_id": 1, "so_number": 1, "customer_id": 1, "customer_name": 1, "sales_id": 1, "split": 1,
              "category": 1, "line_code": 1, "net_alloc": 1, "date_wib": 1}


class CapaianError(ValueError):
    """Galat isian Capaian dengan kalimat siap tampil (→ 400)."""


# ── Angka ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _rp(cents: int) -> int:
    """Sen bulat → rupiah penuh (setengah ke atas) — satu-satunya pembulat uang jawaban Capaian."""
    return int((Decimal(int(cents)) / 100).quantize(Decimal("1"), ROUND_HALF_UP))


def _q1(x: Decimal) -> float:
    return float(x.quantize(Decimal("0.1"), ROUND_HALF_UP))


def _ratio(num: int, den: int) -> Optional[Decimal]:
    return None if not den else Decimal(int(num)) * 100 / Decimal(int(den))


def _pct(num: int, den: int) -> Optional[float]:
    r = _ratio(num, den)
    return None if r is None else _q1(r)


def _c(v: Any) -> int:
    return to_cents(v) if v is not None else 0


# ── Periode ──────────────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class Periode:
    type: str
    key: str
    label: str
    short_label: str
    date_from: str
    date_to: str
    cumulative: bool = False

    def out(self) -> Dict[str, Any]:
        return {"type": self.type, "key": self.key, "label": self.label, "short_label": self.short_label,
                "date_from": self.date_from, "date_to": self.date_to, "cumulative": self.cumulative}


def _tgl(d: str) -> str:
    from services.book_date import tanggal_panjang
    return tanggal_panjang(d)


def _rentang_label(a: str, z: str) -> str:
    return f"{_tgl(a)} – {_tgl(z)}"


def _short_month(p: str) -> str:
    return f"{_BLN_PENDEK[int(p[5:7])]} {p[:4]}"


def _parse_date(s: Any) -> date:
    try:
        v = str(s or "").strip()
        if len(v) != 10:
            raise ValueError(v)
        return date.fromisoformat(v)
    except ValueError:
        raise CapaianError(PESAN_RENTANG)


async def resolve_period(entity_id: str, period_type: str = "month", period: str = "", date_from: str = "",
                         date_to: str = "", cumulative: bool = False) -> Periode:
    """Jenis + kunci periode → batas tanggal WIB (`incentive_periods`, tahun buku PT, K-24)."""
    pt = str(period_type or "month").strip().lower()
    if pt not in PERIOD_TYPES:
        raise CapaianError(PESAN_PERIODE)
    if pt == "range":
        if cumulative:
            raise CapaianError(PESAN_KUMULATIF)
        a, z = _parse_date(date_from), _parse_date(date_to)
        if a > z:
            raise CapaianError(PESAN_RENTANG)
        if (z - a).days + 1 > 366:
            raise CapaianError(PESAN_RENTANG_PANJANG)
        lbl = _rentang_label(a.isoformat(), z.isoformat())
        return Periode("range", f"{a.isoformat()}_{z.isoformat()}", lbl, lbl, a.isoformat(), z.isoformat())
    try:
        p = period or await ip.current_period(pt, entity_id)
        pt, p = ip.normalize(pt, p)
        a, z = await ip.period_bounds(pt, p, entity_id)
    except ip.PeriodeError:
        raise CapaianError(PESAN_PERIODE)
    if cumulative:
        if pt != "month":
            raise CapaianError(PESAN_KUMULATIF)
        fy_end = await ip.fiscal_end_month(entity_id)
        fy = ip.current_period_with("year", f"{p}-01", fy_end)
        a = ip.bounds_with("year", fy, fy_end)[0]
        lbl = f"{_rentang_label(a, z)} (kumulatif tahun berjalan)"
        return Periode(pt, p, lbl, f"{_short_month(a[:7])}–{_short_month(p)}", a, z, True)
    short = _short_month(p) if pt == "month" else ip.period_label(pt, p)
    return Periode(pt, p, ip.period_label(pt, p), short, a, z)


def _shift_year(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:   # 29 Feb → 28 Feb
        return d.replace(year=d.year + n, day=28)


async def compare_period(entity_id: str, cur: Periode, compare: str) -> Optional[Periode]:
    """Periode pembanding: `prev` = periode sebelumnya (jenis sama; rentang = panjang sama tepat sebelumnya), `yoy` =
    periode sama tahun lalu. Kumulatif ikut dibandingkan kumulatif."""
    c = str(compare or "none").strip().lower()
    if c not in COMPARES:
        raise CapaianError(PESAN_BANDING)
    if c == "none":
        return None
    if cur.type == "range":
        a, z = date.fromisoformat(cur.date_from), date.fromisoformat(cur.date_to)
        if c == "prev":
            n = (z - a).days
            z2 = a - timedelta(days=1)
            a2 = z2 - timedelta(days=n)
        else:
            a2, z2 = _shift_year(a, -1), _shift_year(z, -1)
        return await resolve_period(entity_id, "range", "", a2.isoformat(), z2.isoformat())
    if c == "prev":
        key = ip.previous_period(cur.type, cur.key)
    elif cur.type == "year":
        key = str(int(cur.key) - 1)
    else:
        key = f"{int(cur.key[:4]) - 1}{cur.key[4:]}"
    return await resolve_period(entity_id, cur.type, key, cumulative=cur.cumulative)


# ── Saringan ─────────────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class Saringan:
    sales_ids: Tuple[str, ...] = ()
    customer_id: str = ""
    category: str = ""
    line_code: str = ""
    price_source: str = ""

    @property
    def produk(self) -> bool:
        """Saringan per baris barang aktif — uang masuk & piutang tidak bisa dipecah sehalus itu."""
        return bool(self.category or self.line_code or self.price_source)

    def baris_barang(self, r: Dict[str, Any]) -> bool:
        if self.customer_id and (r.get("customer_id") or "") != self.customer_id:
            return False
        if self.category and (r.get("category") or "") != self.category:
            return False
        if self.line_code and (r.get("line_code") or "").lower() != self.line_code.lower():
            return False
        if self.price_source and (r.get("price_source") or "") != self.price_source:
            return False
        return True

    def pemilik(self, owner: str) -> bool:
        return not self.sales_ids or owner in self.sales_ids


def saringan(sales_ids: Optional[Iterable[str]] = None, customer_id: str = "", category: str = "", line_code: str = "",
             price_source: str = "") -> Saringan:
    ids = tuple(dict.fromkeys(str(s).strip() for s in (sales_ids or []) if s is not None))
    return Saringan(ids, str(customer_id or "").strip(), str(category or "").strip(), str(line_code or "").strip(),
                    str(price_source or "").strip())


# ── Pengumpul ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _kunci(group_by: str, owner: str, r: Dict[str, Any]) -> Optional[str]:
    if group_by == "sales":
        return owner
    if group_by == "customer":
        return r.get("customer_id") or ""
    if group_by == "category":
        return r.get("category") or ""
    if group_by == "price_source":
        return r.get("price_source") or ""
    return None


@dataclass
class Kumpulan:
    """Hasil satu pengumpulan: butir dokumen per angka (`omzet`/`retur`/`uang_masuk`) + akumulator per kunci."""
    items: Dict[str, List[Dict[str, Any]]]
    acc: Dict[str, Dict[str, Any]]
    uang_tersedia: bool
    names: Dict[str, str]


def _acc_baru() -> Dict[str, Any]:
    return {"omzet": 0, "retur": 0, "uang": 0, "so": set(), "q_net": 0, "q_acuan": 0, "q_bawah": 0, "q_net_bawah": 0,
            "m_net": 0, "m_cost": 0, "n_tanpa_acuan": 0, "n_tanpa_biaya": 0, "giro": set(), "n_kasus": 0}


async def _owner_map(customer_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    ids = sorted(c for c in customer_ids if c)
    for i in range(0, len(ids), KELOMPOK):
        async for c in db.customers.find({"id": {"$in": ids[i:i + KELOMPOK]}},
                                         {"_id": 0, "id": 1, "name": 1, "assigned_sales_id": 1}):
            out[c["id"]] = c
    return out


async def _baris_pesanan(entity_id: str, a: str, z: str, dasar: str) -> List[Dict[str, Any]]:
    """Baris `fact_sales_lines` untuk dasar omzet `pesanan` (tanggal pesanan) atau `lunas` (tanggal lunas terakhir)."""
    if dasar == "pesanan":
        return [r async for r in db.fact_sales_lines.find(
            {"entity_id": entity_id, "is_live": True, "date_wib": {"$gte": a, "$lte": z}}, _PROJ_LINE)]
    last: Dict[str, str] = {}
    async for r in db.fact_collections.find({"entity_id": entity_id, "settles_order": True},
                                            {"_id": 0, "so_id": 1, "date_wib": 1}):
        d = r.get("date_wib") or ""
        if d > last.get(r["so_id"], ""):
            last[r["so_id"]] = d
    ids = sorted(so for so, d in last.items() if a <= d <= z)
    out: List[Dict[str, Any]] = []
    for i in range(0, len(ids), KELOMPOK):
        async for r in db.fact_sales_lines.find({"so_id": {"$in": ids[i:i + KELOMPOK]}, "is_live": True}, _PROJ_LINE):
            r["date_wib"] = last[r["so_id"]]
            out.append(r)
    return out


async def _kumpulkan(entity_id: str, per: Periode, defn: Dict[str, Any], flt: Saringan, group_by: str) -> Kumpulan:
    """Baca fakta periode `per`, petakan ke pemilik angka & kunci kelompok, terapkan saringan, kumpulkan butir dokumen
    dan akumulator per kunci. Tidak menulis apa pun."""
    a, z = per.date_from, per.date_to
    dasar = defn.get("dasar_omzet") or "terkirim"
    acuan_f = ACUAN_FIELD.get(defn.get("harga_acuan") or "daftar_pt", "list_value")
    semua_baris = (defn.get("isi_pencairan") or "uang_masuk") == "semua_baris"
    pemilik_pelanggan = (defn.get("pemilik_angka") or "sales_pesanan") == "pemilik_pelanggan"
    rng = {"entity_id": entity_id, "date_wib": {"$gte": a, "$lte": z}}
    ship = [r async for r in db.fact_shipment_sales.find(rng, _PROJ_SHIP)]
    coll = [r async for r in db.fact_collections.find(rng, _PROJ_COLL)]
    lines = await _baris_pesanan(entity_id, a, z, dasar) if dasar in ("pesanan", "lunas") else []
    cust = await _owner_map({r.get("customer_id") or "" for r in (*ship, *coll, *lines)}) if (
        pemilik_pelanggan or group_by == "customer") else {}

    def owner(r: Dict[str, Any]) -> str:
        if pemilik_pelanggan:
            return (cust.get(r.get("customer_id") or "") or {}).get("assigned_sales_id") or ""
        return r.get("sales_id") or ""

    items: Dict[str, List[Dict[str, Any]]] = {m: [] for m in METRICS}
    acc: Dict[str, Dict[str, Any]] = {}
    names: Dict[str, str] = {}

    def _slot(k: str) -> Dict[str, Any]:
        return acc.setdefault(k, _acc_baru())

    def _item(metric: str, k: str, o: str, r: Dict[str, Any], *, doc_type: str, doc_id: str, doc_number: str,
              kind: str, cents: int) -> None:
        items[metric].append({"key": k, "owner": o, "doc_type": doc_type, "doc_id": doc_id or "",
                              "doc_number": doc_number or "", "date_wib": r.get("date_wib") or "",
                              "customer_id": r.get("customer_id") or "", "customer_name": r.get("customer_name") or "",
                              "so_id": r.get("so_id") or "", "so_number": r.get("so_number") or "",
                              "source_kind": kind, "split": float(r.get("split") or 1.0), "cents": cents})

    for r in ship:
        o = owner(r)
        if not flt.pemilik(o) or not flt.baris_barang(r):
            continue
        k = _kunci(group_by, o, r)
        if group_by == "customer" and r.get("customer_name"):
            names.setdefault(k, r["customer_name"])
        kind = r.get("source_kind") or ""
        net = _c(r.get("net"))
        s = _slot(k)
        if kind in OMZET_KINDS and dasar == "terkirim":
            s["omzet"] += net
            s["so"].add(r.get("so_id") or "")
            _item("omzet", k, o, r, doc_type="shipment" if kind == "kirim" else "sales_order",
                  doc_id=r.get("source_id") if kind == "kirim" else r.get("so_id"),
                  doc_number=r.get("source_number") if kind == "kirim" else r.get("so_number"), kind=kind, cents=net)
        if kind in RETUR_KINDS:
            s["retur"] -= net
            _item("retur", k, o, r, doc_type="credit_note", doc_id=r.get("source_id"), doc_number=r.get("source_number"),
                  kind=kind, cents=-net)
        if kind == "kirim":   # kualitas harga: hanya barang terkirim
            ref = r.get(acuan_f)
            if ref is None:
                s["n_tanpa_acuan"] += 1
            else:
                ac = _c(ref)
                s["q_net"] += net
                s["q_acuan"] += ac
                if net < ac:
                    s["q_bawah"] += net
        if kind in OMZET_KINDS and not r.get("cost_known"):
            s["n_tanpa_biaya"] += 1
        if kind in MARGIN_KINDS and r.get("cost_known"):
            s["m_net"] += net
            s["m_cost"] += _c(r.get("cost"))
    for r in lines:   # dasar omzet `pesanan` / `lunas`
        o = owner(r)
        rr = {**r, "price_source": ""}
        if not flt.pemilik(o) or not flt.baris_barang(rr):
            continue
        k = _kunci(group_by, o, rr)
        if group_by == "customer" and r.get("customer_name"):
            names.setdefault(k, r["customer_name"])
        net = _c(r.get("net_alloc"))
        s = _slot(k)
        s["omzet"] += net
        s["so"].add(r.get("so_id") or "")
        _item("omzet", k, o, r, doc_type="sales_order", doc_id=r.get("so_id"), doc_number=r.get("so_number"),
              kind=dasar, cents=net)
    uang_tersedia = not flt.produk and group_by in ("sales", "customer")
    if uang_tersedia:
        rids = sorted({r.get("receipt_id") for r in coll if r.get("receipt_id")})
        kwitansi: Set[str] = set()
        for i in range(0, len(rids), KELOMPOK):
            kwitansi |= {x["id"] async for x in db.ar_receipts.find({"id": {"$in": rids[i:i + KELOMPOK]}},
                                                                     {"_id": 0, "id": 1})}
        for r in coll:
            o = owner(r)
            if not flt.pemilik(o) or (flt.customer_id and (r.get("customer_id") or "") != flt.customer_id):
                continue
            k = _kunci(group_by, o, r)
            kind = r.get("source_kind") or ""
            s = _slot(k)
            if not semua_baris and kind not in UANG_MASUK_KINDS:
                if kind == "kasus":
                    s["n_kasus"] += 1
                continue
            amt = _c(r.get("amount"))
            s["uang"] += amt
            if r.get("giro_uncleared") and r.get("receipt_id"):
                s["giro"].add(r["receipt_id"])
            rid = r.get("receipt_id") or ""
            is_rc = rid in kwitansi
            _item("uang_masuk", k, o, r, doc_type="ar_receipt" if is_rc else "sales_order",
                  doc_id=rid if is_rc else r.get("so_id"),
                  doc_number=(r.get("receipt_number") or "") if is_rc else (r.get("receipt_number") or r.get("so_number")),
                  kind="pembalik" if r.get("is_reversal") else kind, cents=amt)
    if group_by == "customer":
        for k in acc:
            if k not in names and k in cust:
                names[k] = cust[k].get("name") or ""
    return Kumpulan(items, acc, uang_tersedia, names)


# ── Angka pelengkap per sales: target, piutang, pelanggan baru ───────────────────────────────────────────────────────
def _bulan_penuh(a: str, z: str) -> List[str]:
    """Bulan (`YYYY-MM`) yang SELURUHNYA berada di dalam rentang [a, z]."""
    out = []
    for m in ip.months_between(a, z):
        s, e = ip.bounds_with("month", m, 12)
        if s >= a and e <= z:
            out.append(m)
    return out


async def _targets(entity_id: str, per: Periode) -> Dict[str, Tuple[int, int]]:
    """Target (omzet, pencairan) dalam sen per sales. Bulan/triwulan/tahun = target jenis & periode itu (angka
    tersendiri, K-24); kumulatif & rentang = Σ target BULANAN untuk bulan yang seluruhnya di dalam rentang."""
    out: Dict[str, List[int]] = {}
    if per.type in ip.PERIOD_TYPES and not per.cumulative:
        q = {"entity_id": entity_id, "period_type": per.type, "period": per.key}
    else:
        q = {"entity_id": entity_id, "period_type": "month", "period": {"$in": _bulan_penuh(per.date_from, per.date_to)}}
    async for t in db.sales_targets.find(q, {"_id": 0, "sales_id": 1, "target_sales_amount": 1,
                                             "target_collection_amount": 1}):
        v = out.setdefault(t.get("sales_id") or "", [0, 0])
        v[0] += _c(t.get("target_sales_amount"))
        v[1] += _c(t.get("target_collection_amount"))
    return {k: (v[0], v[1]) for k, v in out.items()}


def piutang_per(per: Periode) -> str:
    """Tanggal posisi piutang: akhir periode, paling jauh hari ini (posisi masa depan belum ada)."""
    from services.book_date import tanggal_buku
    return min(per.date_to, tanggal_buku())


async def _piutang(entity_id: str, per: Periode, flt: Saringan) -> Dict[str, Tuple[int, int]]:
    """(sisa piutang, lewat jatuh tempo) dalam sen per sales penanggung jawab pelanggan saat ini — `aging_report`
    (PK-41, per surat jalan) per tanggal `piutang_per`."""
    from services.ar_aging_service import aging_report
    rep = await aging_report(entity_id, None, as_of=piutang_per(per))
    out: Dict[str, List[int]] = {}
    for c in rep.get("customers") or []:
        if flt.customer_id and c.get("customer_id") != flt.customer_id:
            continue
        v = out.setdefault(c.get("assigned_sales_id") or "", [0, 0])
        v[0] += _c(c.get("outstanding"))
        v[1] += _c(c.get("overdue"))
    return {k: (v[0], v[1]) for k, v in out.items()}


async def _pelanggan_baru(entity_id: str, per: Periode, flt: Saringan) -> Dict[str, int]:
    """Pelanggan PT yang dibuat (tanggal WIB) dalam periode, per sales penanggung jawabnya saat ini."""
    from services.book_date import tanggal_buku
    lo = (date.fromisoformat(per.date_from) - timedelta(days=1)).isoformat()
    hi = (date.fromisoformat(per.date_to) + timedelta(days=1)).isoformat() + "T23:59:59"
    out: Dict[str, int] = {}
    async for c in db.customers.find({"entity_id": entity_id, "created_at": {"$gte": lo, "$lte": hi}},
                                     {"_id": 0, "id": 1, "created_at": 1, "assigned_sales_id": 1}):
        if flt.customer_id and c.get("id") != flt.customer_id:
            continue
        try:
            d = tanggal_buku(c.get("created_at"))
        except ValueError:
            continue
        if per.date_from <= d <= per.date_to:
            k = c.get("assigned_sales_id") or ""
            out[k] = out.get(k, 0) + 1
    return out


# ── Penyusun baris ───────────────────────────────────────────────────────────────────────────────────────────────────
def _label_kelompok(group_by: str, key: str, names: Dict[str, str]) -> str:
    if group_by == "sales":
        return names.get(key) or (TANPA_SALES if not key else "Akun tidak dikenal")
    if group_by == "customer":
        return names.get(key) or ("Tanpa pelanggan" if not key else "Pelanggan tidak dikenal")
    if group_by == "category":
        return key or "Tanpa kategori"
    if key in PRICE_SOURCE_LABEL:
        return PRICE_SOURCE_LABEL[key]
    return "Harga sampel" if key.startswith("sample") else "Sumber harga lain"


def _catatan(s: Dict[str, Any], margin_ok: bool) -> List[Dict[str, Any]]:
    out = []
    for code, n, teks in (("tanpa_acuan", s["n_tanpa_acuan"], "{n} baris tanpa harga acuan"),
                          ("tanpa_biaya", s["n_tanpa_biaya"] if margin_ok else 0,
                           "{n} baris tanpa biaya, tidak ikut hitungan margin"),
                          ("giro_belum_cair", len(s["giro"]), "{n} kwitansi giro belum dipastikan cair"),
                          ("kasus", s["n_kasus"], "{n} baris kasus keuangan tidak dihitung sebagai uang masuk")):
        if n:
            out.append({"code": code, "count": n, "text": teks.format(n=n)})
    return out


def _kualitas(s: Dict[str, Any], margin_ok: bool) -> Dict[str, Any]:
    real = _ratio(s["q_net"], s["q_acuan"])
    out = {"realisasi_harga_pct": None if real is None else _q1(real),
           "rata_potongan_pct": None if real is None else _q1(Decimal(100) - real),
           "porsi_bawah_acuan_pct": _pct(s["q_bawah"], s["q_net"]) if s["q_acuan"] else None}
    if margin_ok:
        out["margin_pct"] = _pct(s["m_net"] - s["m_cost"], s["m_net"])
    return out


def _gabung(accs: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    t = _acc_baru()
    for s in accs:
        for k, v in s.items():
            if isinstance(v, set):
                t[k] |= v
            else:
                t[k] += v
    return t


async def _nama_sales(entity_id: str, per: Periode, keys: Set[str]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    from services import incentive_targets as itg
    if per.type in ip.PERIOD_TYPES and not per.cumulative:
        roster = await itg.sales_roster(entity_id, per.type, per.key)
    else:
        roster = await itg.sales_roster(entity_id)
    names = {r["id"]: r["name"] for r in roster}
    missing = sorted(k for k in keys if k and k not in names)
    if missing:
        names.update({u["id"]: u.get("name") or "" async for u in db.users.find(
            {"id": {"$in": missing}}, {"_id": 0, "id": 1, "name": 1})})
    return roster, names


async def achievement(entity_id: str, per: Periode, defn: Dict[str, Any], flt: Saringan, group_by: str = "sales",
                      margin_ok: bool = False, cmp: Optional[Periode] = None, *, q: str = "",
                      only_numbers: bool = False, kp: Optional[Kumpulan] = None) -> Dict[str, Any]:
    """Baris Capaian per kunci kelompok + total (+ pembanding). `q` (nama memuat, tanpa beda huruf besar) dan
    `only_numbers` (hanya baris yang ada angkanya) menyaring BARIS sebelum total — dipakai ekspor supaya isi berkas
    sama dengan daftar yang sedang dilihat (KN_37 §6)."""
    if group_by not in GROUPS:
        raise CapaianError(PESAN_KELOMPOK)
    kp = kp or await _kumpulkan(entity_id, per, defn, flt, group_by)
    per_sales = group_by == "sales"
    notes: List[str] = []
    targets: Dict[str, Tuple[int, int]] = {}
    piutang: Dict[str, Tuple[int, int]] = {}
    baru: Dict[str, int] = {}
    names = dict(kp.names)
    keys = set(kp.acc)
    if per_sales:
        targets = await _targets(entity_id, per)
        if not flt.produk:
            piutang = await _piutang(entity_id, per, flt)
        baru = await _pelanggan_baru(entity_id, per, flt)
        roster, snames = await _nama_sales(entity_id, per, keys | set(targets) | set(piutang) | set(baru))
        names.update(snames)
        keys |= {r["id"] for r in roster}
        keys |= {k for k, v in targets.items() if any(v)} | {k for k, v in piutang.items() if any(v)} | set(baru)
        keys = {k for k in keys if flt.pemilik(k)}
    if not kp.uang_tersedia:
        notes.append(CATATAN_UANG_PRODUK)
    rows: List[Dict[str, Any]] = []
    for k in keys:
        s = kp.acc.get(k) or _acc_baru()
        bersih = s["omzet"] - s["retur"]
        row: Dict[str, Any] = {"key": k, "name": _label_kelompok(group_by, k, names)}
        if per_sales:
            row["sales_id"] = k
            ts, tc = targets.get(k, (0, 0))
            row["target_sales"] = _rp(ts)
        row.update({"omzet": _rp(s["omzet"]), "retur": _rp(s["retur"]), "omzet_bersih": _rp(s["omzet"]) - _rp(s["retur"])})
        uang = _rp(s["uang"]) if kp.uang_tersedia else None
        if per_sales:
            row["pct_omzet"] = _pct(row["omzet_bersih"], row["target_sales"])
            row["target_collection"] = _rp(tc)
        row["uang_masuk"] = uang
        if per_sales:
            row["pct_pencairan"] = _pct(uang, row["target_collection"]) if uang is not None else None
            sp, lt = piutang.get(k, (0, 0))
            row["sisa_piutang"] = _rp(sp) if not flt.produk else None
            row["lewat_tempo"] = _rp(lt) if not flt.produk else None
        row.update(_kualitas(s, margin_ok))
        if per_sales:
            row["pelanggan_baru"] = baru.get(k, 0)
        row["jumlah_pesanan"] = len(s["so"] - {""})
        row["catatan_data"] = _catatan(s, margin_ok)
        row["has_numbers"] = bool(s["omzet"] or s["retur"] or s["uang"] or row.get("target_sales")
                                  or row.get("target_collection") or row.get("sisa_piutang")
                                  or row.get("pelanggan_baru") or bersih)
        if k == "" and per_sales and not row["has_numbers"]:
            continue   # baris "Tanpa sales" hanya bila ada angkanya
        if (only_numbers and not row["has_numbers"]) or (q and q.strip().lower() not in row["name"].lower()):
            continue
        rows.append(row)
    if per_sales:
        rows.sort(key=lambda r: (r["key"] == "", r["name"].lower(), r["key"]))
    else:
        rows.sort(key=lambda r: (-r["omzet_bersih"], r["name"].lower(), r["key"]))
    totals = _totals(rows, [kp.acc.get(r["key"]) or _acc_baru() for r in rows], per_sales, kp.uang_tersedia, margin_ok,
                     flt)
    out = {"rows": rows, "totals": totals, "notes": notes, "uang_masuk_tersedia": kp.uang_tersedia}
    if cmp is not None:
        out["compare"] = await _pembanding(entity_id, cmp, defn, flt, group_by)
    return out


def _totals(rows: List[Dict[str, Any]], accs: List[Dict[str, Any]], per_sales: bool, uang_ok: bool, margin_ok: bool,
            flt: Saringan) -> Dict[str, Any]:
    t = _gabung(accs)
    tot: Dict[str, Any] = {"name": "Total", "rows": len(rows)}
    money = ["omzet", "retur", "omzet_bersih"] + (["target_sales", "target_collection"] if per_sales else [])
    for f in money:
        tot[f] = sum(r[f] for r in rows)
    tot["uang_masuk"] = sum(r["uang_masuk"] for r in rows) if uang_ok else None
    if per_sales:
        tot["pct_omzet"] = _pct(tot["omzet_bersih"], tot["target_sales"])
        tot["pct_pencairan"] = _pct(tot["uang_masuk"], tot["target_collection"]) if uang_ok else None
        tot["sisa_piutang"] = sum(r["sisa_piutang"] for r in rows) if not flt.produk else None
        tot["lewat_tempo"] = sum(r["lewat_tempo"] for r in rows) if not flt.produk else None
        tot["pelanggan_baru"] = sum(r["pelanggan_baru"] for r in rows)
    tot.update(_kualitas(t, margin_ok))
    tot["jumlah_pesanan"] = len(t["so"] - {""})   # pesanan berbagi tim dihitung sekali
    tot["catatan_data"] = _catatan(t, margin_ok)
    return tot


async def _pembanding(entity_id: str, cmp: Periode, defn: Dict[str, Any], flt: Saringan,
                      group_by: str) -> Dict[str, Any]:
    kp = await _kumpulkan(entity_id, cmp, defn, flt, group_by)
    by_key: Dict[str, Dict[str, Any]] = {}
    for k, s in kp.acc.items():
        by_key[k] = {"omzet": _rp(s["omzet"]), "retur": _rp(s["retur"]),
                     "omzet_bersih": _rp(s["omzet"]) - _rp(s["retur"]),
                     "uang_masuk": _rp(s["uang"]) if kp.uang_tersedia else None}
    tot = {"omzet_bersih": sum(v["omzet_bersih"] for v in by_key.values()),
           "uang_masuk": sum(v["uang_masuk"] for v in by_key.values()) if kp.uang_tersedia else None}
    return {"label": cmp.short_label, "period": cmp.out(), "date_from": cmp.date_from, "date_to": cmp.date_to,
            "by_key": by_key, "totals": tot}


# ── Telusur ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _link(doc_type: str, it: Dict[str, Any]) -> Dict[str, Any]:
    from services.doc_refs_service import link_of
    num = it["doc_number"]
    doc = {"id": it["doc_id"], "number": num, "shipment_no": num, "order_id": it["so_id"]}
    return link_of(doc_type, doc)


def _ringkas_butir(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Satu butir per (jenis dokumen, dokumen, pesanan, jenis sumber); nilai dalam sen dijumlahkan."""
    by: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    for it in raw:
        k = (it["doc_type"], it["doc_id"], it["so_id"], it["source_kind"])
        cur = by.get(k)
        if cur is None:
            by[k] = {**it}
        else:
            cur["cents"] += it["cents"]
    out = list(by.values())
    out.sort(key=lambda x: (x["date_wib"], x["doc_number"], x["so_number"]), reverse=True)
    return out


def _butir_keluar(it: Dict[str, Any]) -> Dict[str, Any]:
    return {"doc_type": it["doc_type"], "doc_id": it["doc_id"], "doc_number": it["doc_number"],
            "date_wib": it["date_wib"], "customer_name": it["customer_name"], "so_id": it["so_id"],
            "so_number": it["so_number"], "source_kind": it["source_kind"],
            "source_label": SOURCE_KIND_LABEL.get(it["source_kind"], "Pembatalan" if it["source_kind"] == "pembalik"
                                                  else "Lainnya"),
            "split": round(it["split"], 6), "amount": from_cents(it["cents"]), "link": _link(it["doc_type"], it)}


async def sources(entity_id: str, per: Periode, defn: Dict[str, Any], flt: Saringan, *, metric: str, key: str,
                  group_by: str = "sales", page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """Dokumen di balik satu sel (angka `metric` untuk kunci `key`): daftar berhalaman + jumlah total (= angka sel)."""
    if metric not in METRICS:
        raise CapaianError(PESAN_METRIK)
    if group_by not in GROUPS:
        raise CapaianError(PESAN_KELOMPOK)
    kp = await _kumpulkan(entity_id, per, defn, flt, group_by)
    if metric == "uang_masuk" and not kp.uang_tersedia:
        raise CapaianError(CATATAN_UANG_PRODUK)
    raw = [it for it in kp.items[metric] if it["key"] == key]
    rows = _ringkas_butir(raw)
    total_c = sum(it["cents"] for it in raw)
    page = max(1, int(page or 1))
    size = max(1, min(200, int(page_size or 50)))
    part = rows[(page - 1) * size: page * size]
    return {"metric": metric, "metric_label": METRIC_LABEL[metric], "key": key, "total": len(rows),
            "sum": _rp(total_c), "page": page, "page_size": size, "items": [_butir_keluar(it) for it in part]}


async def angka_sales(entity_id: str, per: Periode, defn: Dict[str, Any],
                      sales_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """KM-T3 — angka satu periode untuk beberapa sales sekaligus, untuk POTRET lembar insentif: baris Capaian per sales
    (margin ikut; layar lembar menyaringnya menurut izin) dan dokumen penyusun omzet · retur · uang masuk per sales.
    Satu pengumpul dengan tabel Capaian (`_kumpulkan` + `achievement`), jadi angka potret = angka sel Capaian."""
    ids = tuple(dict.fromkeys(s for s in sales_ids if s))
    flt = saringan(ids)
    kp = await _kumpulkan(entity_id, per, defn, flt, "sales")
    res = await achievement(entity_id, per, defn, flt, "sales", True, kp=kp)
    rows = {r["key"]: r for r in res["rows"]}
    out: Dict[str, Dict[str, Any]] = {}
    for sid in ids:
        out[sid] = {"row": rows.get(sid),
                    "docs": {m: _ringkas_butir([it for it in kp.items[m] if it["key"] == sid]) for m in METRICS}}
    return out


# ── Definisi & pencocokan ────────────────────────────────────────────────────────────────────────────────────────────
def column_help(defn: Dict[str, Any], per: Periode) -> Dict[str, str]:
    """Keterangan tiap judul kolom (disorot di layar; lembar Definisi ekspor) — mengikuti versi definisi PT."""
    acuan = ACUAN_LABEL.get(defn.get("harga_acuan") or "daftar_pt", "harga daftar PT")
    omzet = {"terkirim": "Nilai barang terkirim (surat jalan) dalam periode, tanpa PPN.",
             "pesanan": "Nilai pesanan yang dibuat dalam periode, tanpa PPN.",
             "lunas": "Nilai pesanan yang lunas dalam periode, tanpa PPN."}.get(defn.get("dasar_omzet") or "terkirim")
    uang = ("Uang yang benar-benar masuk dan dialokasikan ke pesanan: tunai, transfer, QRIS, giro, deposit, dan "
            "titipan bank. Kwitansi yang dibatalkan mengurangi periode pembatalannya."
            if (defn.get("isi_pencairan") or "uang_masuk") == "uang_masuk" else
            "Semua pelunasan yang dialokasikan ke pesanan, termasuk hapus sisa, nota kredit, saldo kredit, dan kasus "
            "keuangan.")
    milik = ("Angka dikelompokkan menurut sales penanggung jawab pelanggan saat ini."
             if defn.get("pemilik_angka") == "pemilik_pelanggan" else
             "Angka milik sales pada pesanan (dengan pembagian tim).")
    per_tgl = _tgl(piutang_per(per))
    return {
        "sales": milik,
        "target_sales": "Target omzet sales di PT ini untuk periode ini; — = belum diisi.",
        "omzet": omzet,
        "pct_omzet": "Omzet bersih dibagi target omzet.",
        "retur": "Nota kredit retur dan nota koreksi dalam periode.",
        "omzet_bersih": "Omzet dikurangi retur.",
        "target_collection": "Target pencairan sales di PT ini untuk periode ini; — = belum diisi.",
        "uang_masuk": uang,
        "pct_pencairan": "Uang masuk dibagi target pencairan.",
        "sisa_piutang": f"Piutang pelanggan yang kini dipegang sales ini, per {per_tgl}.",
        "lewat_tempo": f"Bagian sisa piutang yang sudah lewat jatuh tempo (per surat jalan), per {per_tgl}.",
        "realisasi_harga_pct": f"Nilai jual dibagi {acuan}, atas barang terkirim yang harga acuannya tercatat.",
        "rata_potongan_pct": "100 % dikurangi realisasi harga.",
        "porsi_bawah_acuan_pct": f"Porsi nilai barang terkirim yang dijual di bawah {acuan}.",
        "margin_pct": "Nilai jual dikurangi biaya barang, dibagi nilai jual — atas baris yang biayanya tercatat.",
        "pelanggan_baru": "Pelanggan PT ini yang dibuat dalam periode dan kini dipegang sales ini.",
        "jumlah_pesanan": "Banyaknya pesanan berbeda pada omzet.",
        "catatan_data": "Baris data yang tidak ikut dihitung atau belum pasti.",
    }


def definition_out(defn: Dict[str, Any], per: Periode) -> Dict[str, Any]:
    from services import incentive_definitions as idef
    return {"version": defn.get("version"), "effective_from": defn.get("effective_from") or "",
            **{f: defn.get(f) for f, _k in idef.FIELDS}, "labels": idef.labels(defn),
            "columns": column_help(defn, per)}


async def reconciliation(entity_id: str, per: Periode) -> Dict[str, Any]:
    """Pencocokan (KM-T1 INV-KM-1 & INV-KM-2) untuk tiap bulan yang tersentuh periode: cocok bila semua bulan cocok;
    selisih = Σ selisih bulan (rupiah)."""
    from services import incentive_facts as ifacts
    om_c = pc_c = 0
    om_ok = pc_ok = True
    for m in ip.months_between(per.date_from, per.date_to):
        r = await ifacts.reconcile(entity_id, m)
        om, pc = r["omzet"], r["pencairan"]
        om_ok = om_ok and bool(om.get("ok"))
        pc_ok = pc_ok and bool(pc.get("ok"))
        om_c += to_cents(om.get("selisih") or 0)
        sel = pc.get("selisih") or 0
        pc_c += to_cents(sel if abs(float(sel)) >= 1 else (pc.get("selisih_kas") or 0))
    return {"omzet_ok": om_ok, "omzet_diff": _rp(om_c), "pencairan_ok": pc_ok, "pencairan_diff": _rp(pc_c)}


# ── Ekspor Excel ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _cell(v: Any) -> Any:
    """KN-E32 — teks yang diawali = + - @ (atau tab/CR) diawali apostrof supaya tidak menjadi rumus."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


#: (kelompok, judul kolom, field) — urutan sama dengan layar.
def columns(per_sales: bool, margin_ok: bool) -> List[Tuple[str, str, str]]:
    cols: List[Tuple[str, str, str]] = []
    cols += ([("Omzet", "Target", "target_sales")] if per_sales else [])
    cols += [("Omzet", "Omzet", "omzet")]
    cols += ([("Omzet", "% capaian", "pct_omzet")] if per_sales else [])
    cols += [("Omzet", "Retur", "retur"), ("Omzet", "Omzet bersih", "omzet_bersih")]
    cols += ([("Pencairan", "Target", "target_collection")] if per_sales else [])
    cols += [("Pencairan", "Uang masuk", "uang_masuk")]
    cols += ([("Pencairan", "% capaian", "pct_pencairan"), ("Pencairan", "Sisa piutang", "sisa_piutang"),
              ("Pencairan", "Lewat tempo", "lewat_tempo")] if per_sales else [])
    cols += [("Kualitas harga", "Realisasi harga", "realisasi_harga_pct"),
             ("Kualitas harga", "Rata-rata potongan", "rata_potongan_pct"),
             ("Kualitas harga", "Di bawah harga acuan", "porsi_bawah_acuan_pct")]
    cols += ([("Kualitas harga", "Margin", "margin_pct")] if margin_ok else [])
    cols += ([("Lain", "Pelanggan baru", "pelanggan_baru")] if per_sales else [])
    cols += [("Lain", "Pesanan", "jumlah_pesanan"), ("Lain", "Catatan data", "catatan_data")]
    return cols


GROUP_HEAD = {"sales": "Sales", "customer": "Pelanggan", "category": "Kategori produk", "price_source": "Sumber harga"}


def _nilai_sel(field: str, v: Any) -> Any:
    if field == "catatan_data":
        return _cell("; ".join(c["text"] for c in v or [])) if v else None
    return v


async def export_xlsx(entity_id: str, per: Periode, defn: Dict[str, Any], flt: Saringan, group_by: str,
                      margin_ok: bool, actor: Dict[str, Any], *, q: str = "",
                      only_numbers: bool = False) -> Tuple[bytes, str]:
    """Berkas `.xlsx` tiga lembar (Definisi · Capaian · Dokumen) dan nama berkasnya. Baris = baris layar (saringan, cari
    `q`, "hanya yang ada angkanya"); lembar Dokumen hanya dokumen baris itu."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from core_utils import entity_code
    from services.analytics_time import now_wib
    if group_by not in GROUPS:
        raise CapaianError(PESAN_KELOMPOK)
    kp = await _kumpulkan(entity_id, per, defn, flt, group_by)
    res = await achievement(entity_id, per, defn, flt, group_by, margin_ok, q=q, only_numbers=only_numbers, kp=kp)
    rec = await reconciliation(entity_id, per)
    ent = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "legal_name": 1, "short_name": 1}) or {}
    pt = ent.get("legal_name") or ent.get("short_name") or entity_id
    dout = definition_out(defn, per)
    wb = Workbook()
    ws = wb.active
    ws.title = "Definisi"
    bold = Font(bold=True)
    ws.append(["Capaian insentif"])
    ws["A1"].font = bold
    for label, val in (("PT", pt), ("Periode", per.label), ("Rentang tanggal", _rentang_label(per.date_from, per.date_to)),
                       ("Dikelompokkan menurut", GROUP_HEAD.get(group_by, group_by)),
                       ("Cari nama", q or "—"),
                       ("Versi definisi", dout["version"]), ("Berlaku sejak", _tgl(dout["effective_from"])
                                                             if dout["effective_from"] else "—")):
        ws.append([label, _cell(val)])
    ws.append([])
    ws.append(["Definisi", "Pilihan", "Keterangan"])
    for c in ws[ws.max_row]:
        c.font = bold
    help_col = {"dasar_omzet": "omzet", "isi_pencairan": "uang_masuk", "pemilik_angka": "sales",
                "harga_acuan": "realisasi_harga_pct"}
    for it in dout["labels"]:
        ws.append([_cell(it["label"]), _cell(it["value_label"]), _cell(dout["columns"].get(help_col.get(it["field"], ""),
                                                                                           it.get("help") or ""))])
    ws.append([])

    def _cocok(ok: bool, diff: int) -> str:
        return "Cocok" if ok else f"Selisih {rupiah(abs(diff))}"
    ws.append(["Pencocokan omzet dengan buku besar", _cocok(rec["omzet_ok"], rec["omzet_diff"])])
    ws.append(["Pencocokan pencairan dengan kas masuk", _cocok(rec["pencairan_ok"], rec["pencairan_diff"])])
    ws.append(["Diekspor", now_wib().strftime("%d-%m-%Y %H:%M") + " WIB"])
    ws.append(["Diekspor oleh", _cell(actor.get("name") or "")])
    for n in res["notes"]:
        ws.append(["Catatan", _cell(n)])
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 90

    per_sales = group_by == "sales"
    cols = columns(per_sales, margin_ok)
    ws2 = wb.create_sheet("Capaian")
    ws2.append([""] + [g for g, _h, _f in cols])
    ws2.append([GROUP_HEAD[group_by]] + [h for _g, h, _f in cols])
    for row in (ws2[1], ws2[2]):
        for c in row:
            c.font = bold
    for r in res["rows"]:
        ws2.append([_cell(r["name"])] + [_nilai_sel(f, r.get(f)) for _g, _h, f in cols])
    t = res["totals"]
    ws2.append(["Total"] + [_nilai_sel(f, t.get(f)) for _g, _h, f in cols])
    for c in ws2[ws2.max_row]:
        c.font = bold
    ws2.column_dimensions["A"].width = 28

    ws3 = wb.create_sheet("Dokumen")
    ws3.append([GROUP_HEAD[group_by], "Angka", "Tanggal", "Jenis", "Nomor dokumen", "Pelanggan", "Pesanan", "Porsi",
                "Nilai"])
    for c in ws3[1]:
        c.font = bold
    names = {r["key"]: r["name"] for r in res["rows"]}
    for metric in METRICS:
        for it in _ringkas_butir([x for x in kp.items[metric] if x["key"] in names]):
            o = _butir_keluar(it)
            ws3.append([_cell(names.get(it["key"], _label_kelompok(group_by, it["key"], kp.names))),
                        METRIC_LABEL[metric], o["date_wib"], _cell(o["source_label"]), _cell(o["doc_number"]),
                        _cell(o["customer_name"]), _cell(o["so_number"]), o["split"], o["amount"]])
    buf = io.BytesIO()
    wb.save(buf)
    code = str(await entity_code(entity_id)).replace("/", "-").replace(" ", "-")
    key = per.key + ("-kumulatif" if per.cumulative else "")
    return buf.getvalue(), f"capaian-{code}-{key}.xlsx"
