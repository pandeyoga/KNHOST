"""EPIC7-A — AR / Piutang Aging (read/derived report).

SSOT: diturunkan dari `sales_orders` + `payments[]` + jurnal pendapatan (SAMA dengan credit engine &
collection_worklist). Reuse helper `customer_service` agar TIDAK terjadi drift:
  `_order_grand_total`, `_order_paid`, `order_payment_method` (hari termin: `report_basis.hari_termin`),
  `_parse_dt`, `DEAD_STATUSES`, `NON_AR_METHODS`.

PK-41 (RP-01, RP-03, RP-05, RP-12; keputusan K-16) — piutang diumurkan PER SURAT JALAN lewat
`services/report_basis.baris_tagihan`: satu baris per jurnal pendapatan surat jalan (jatuh tempo = tanggal surat jalan +
termin), pembayaran per tanggal `per` dialokasikan ke jatuh tempo tertua, dan bagian pesanan yang belum dikirim menjadi
satu baris tanpa jatuh tempo. Kelompok umur, lewat jatuh tempo, telat terlama, dan estimasi denda dihitung per baris.
`as_of` = posisi pada tanggal itu (pembayaran sesudahnya belum dihitung; pesanan yang kini lunas tetap dibaca).
CR-T2 (b) — baris tagihan kini dibaca dari JADWAL TAGIHAN tersimpan (`billing_schedule_service`, lewat
`report_basis.baris_tagihan`): baris uang muka (termin ber-DP) dan baris rencana cicilan ikut menentukan kelompok umur;
piutang tercatat/belum dikirim dari bagian `tercatat` tiap baris.
Pelanggan dan pesanan dibaca dengan kursor tanpa batas (`02` D4); jawaban membawa pencocokan ke saldo akun piutang.

Buckets aging (berdasar hari telat jatuh tempo):
  current (belum jatuh tempo), lalu kolom dari batas `ar.aging_buckets` (judul kolom: `bucket_labels`).

Denda (late fee) = **ESTIMASI informasional** (tidak posting ke order/GL). CR-T4 — taksiran per baris tagihan =
`penalty_service.estimate` dengan aturan `penalty_policy` (PT → profil kredit pelanggan → rencana), sama dengan nota.
"""
from typing import Any, Dict, List, Optional, Tuple

from db import db
from core_utils import from_cents, to_cents
from services.config_service import get_effective_settings
from services.customer_service import (
    _order_grand_total as order_grand_total,
    _order_paid as order_paid,
    DEAD_STATUSES,
)
from services import report_basis as rb

EPS = 0.01
BUCKET_KEYS = ["current", "b1_30", "b31_60", "b61_90", "b90_plus"]
# KF-T7 (CR-03) — ambang peringatan & blokir kredit (dulu konstanta 0,8 dan 14 hari, salinan kedua dari
# `customer_service`) dibaca `customer_service.credit_thresholds` per PT pelanggan. CR-T1 — plafon, hari blokir, dan
# blokir manual dari profil kredit yang berlaku (`credit_profile_service.effective`), status dari `status_from`.


async def get_ar_config(entity_id: Optional[str] = None,
                        customer_id: Optional[str] = None,
                        plan: Optional[Dict[str, Any]] = None,
                        pt_cache: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Kebijakan denda & kelompok umur piutang yang BERLAKU.

    CR-T4 — denda dari `penalty_service.penalty_policy` (aturan grup → PT → profil kredit pelanggan di PT itu), satu
    aturan dengan nota denda, sehingga taksiran laporan = nota. `ar.denda_rate_pct_per_month` dan `ar.grace_days`
    tidak lagi dibaca per pelanggan dari Pusat Pengaturan (lapisan `customer` dicabut; satu pemilik = profil kredit).
    `aging_buckets` (`ar.aging_buckets`) tetap global → PT. `source` = asal tiap angka untuk layar (L6). `plan` =
    rencana cicilan pesanan yang punya aturan denda sendiri (`plan.penalty`, paling khusus — sama dengan nota).
    """
    from services import penalty_service as _pen
    from services.config_resolver import resolve
    pol = await _pen.penalty_policy(entity_id or "", customer_id or "", plan, pt_cache=pt_cache)
    buckets = await resolve("ar.aging_buckets", {"entity_id": pol.get("entity_id") or entity_id or ""})
    try:
        edges = sorted(int(float(x)) for x in (buckets["value"] or [30, 60, 90]))
    except (TypeError, ValueError):
        edges = [30, 60, 90]
    asal = pol["sources"]
    return {
        "denda_rate_pct_per_month": pol["rate_pct_per_month"],
        "grace_days": pol["grace_days"],
        "aging_buckets": edges,
        "penalty": pol,   # CR-T4 — aturan lengkap untuk taksiran (`_denda_estimate`)
        "source": {"denda_rate_pct_per_month": _pen.SOURCE_LABEL[asal["rate_pct_per_month"]],
                   "grace_days": _pen.SOURCE_LABEL[asal["grace_days"]],
                   "aging_buckets": buckets["source_label"]},
    }


def _bucket(days_late: int, edges: Optional[List[int]] = None) -> str:
    """Kolom umur piutang. `edges` CONFIGURABLE dari `ar.aging_buckets`."""
    if days_late <= 0:
        return "current"
    e = sorted(edges or [30, 60, 90])
    for idx, edge in enumerate(e):
        if days_late <= edge:
            return BUCKET_KEYS[idx + 1] if idx + 1 < len(BUCKET_KEYS) else BUCKET_KEYS[-1]
    return BUCKET_KEYS[-1]


async def _rencana_berdenda(order_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """CR-T4 — rencana cicilan hidup yang punya aturan denda SENDIRI (`plan.penalty` terisi), per pesanan — satu kueri.
    Pesanan lain memakai aturan PT/pelanggan."""
    from services import payment_plan_service as plans
    out: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(order_ids), rb.KELOMPOK):
        async for p in db[plans.COLL].find({"doc_type": "sales_order", "doc_id": {"$in": order_ids[i:i + rb.KELOMPOK]},
                                            "status": {"$ne": "void"}, "origin": {"$ne": plans.ORIGIN_TERM}},
                                           {"_id": 0, "id": 1, "doc_id": 1, "penalty": 1, "created_at": 1}):
            if any(v not in (None, "") for v in (p.get("penalty") or {}).values()):
                lama = out.get(p["doc_id"])
                if not lama or str(p.get("created_at") or "") > str(lama.get("created_at") or ""):
                    out[p["doc_id"]] = p
    return out


def _policy_bawaan() -> Dict[str, Any]:
    """Aturan denda = bawaan registry (pemanggil tanpa `get_ar_config`; KF-T2 KF-06: cadangan = bawaan registry)."""
    from config_registry import default_of
    from services import penalty_service as _pen
    return {u: _pen._cast(u, default_of(k)) for u, k in _pen.POLICY_KEYS.items()}   # noqa: SLF001


def _denda_estimate(outstanding: float, days_late: int, cfg: Dict[str, Any],
                    order_outstanding: Optional[float] = None) -> float:
    """CR-T4 — taksiran denda satu baris tagihan = `penalty_service.estimate` (rumus harian, tenggang, batas atas,
    minimum, dan mode yang sama dengan nota). Dulu dibulatkan ke bulan penuh (`ceil(hari / 30)`), berbeda dari nota."""
    from services import penalty_service as _pen
    return _pen.estimate(outstanding, days_late, cfg.get("penalty") or _policy_bawaan(), order_outstanding)


def _empty_buckets() -> Dict[str, float]:
    return {k: 0.0 for k in BUCKET_KEYS}


async def _credit_status(customer: Dict[str, Any], ar_outstanding: float, max_overdue_days: int,
                         entity_id: Optional[str] = None,
                         cache: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
    """CR-T1 — (status, profil efektif) memakai rumus yang SAMA dengan kartu pelanggan: profil kredit (pelanggan, PT)
    yang berlaku (`credit_profile_service.effective`; PT = `entity_id`, atau PT pemilik data pelanggan) lalu
    `credit_profile_service.status_from`. KF-T7 — ambang PT dibaca `credit_thresholds` di dalam `effective`."""
    from services import credit_profile_service as cps
    pt = entity_id if isinstance(entity_id, str) and entity_id and entity_id != "all" else \
        (customer.get("entity_id") or "")
    eff = await cps.effective(customer["id"], pt, customer=customer, cache=cache)
    return cps.status_from(eff, ar_outstanding, max_overdue_days), eff


async def _load_scope(entity_id: Optional[Any], sales_id: Optional[str]):
    """Ambil customers (terfilter) + map sales-name dalam minimal query.

    FASE E-0 (L9) — `entity_id` sekarang boleh berupa:
      * `str`  → satu entitas (isolasi ketat),
      * `dict` → filter Mongo siap pakai (mis. `{"$in": [...]}` untuk mode gabungan),
      * `None`/`"all"` → tanpa filter (hanya untuk peran lintas-entitas).
    PK-41 (RP-01) — kursor tanpa batas (dulu 5.000 pelanggan pertama, sisanya hilang diam-diam).
    """
    cust_filter: Dict[str, Any] = {}
    if isinstance(entity_id, dict):
        cust_filter["entity_id"] = entity_id
    elif entity_id and entity_id != "all":
        cust_filter["entity_id"] = entity_id
    if sales_id:
        cust_filter["assigned_sales_id"] = sales_id
    customers = [c async for c in db.customers.find(
        cust_filter,
        {"_id": 0, "id": 1, "name": 1, "assigned_sales_id": 1, "payment_profile": 1,
         "credit_limit": 1, "status": 1, "entity_id": 1, "deposit_balance": 1})]
    sales_ids = {c.get("assigned_sales_id") for c in customers if c.get("assigned_sales_id")}
    smap = {}
    if sales_ids:
        async for u in db.users.find({"id": {"$in": list(sales_ids)}}, {"_id": 0, "id": 1, "name": 1}):
            smap[u["id"]] = u.get("name", "")
    return customers, smap


ORDER_FIELDS = {"_id": 0, "id": 1, "number": 1, "customer_id": 1, "customer_name": 1,
                "status": 1, "payment_status": 1, "grand_total": 1, "total_amount": 1,
                "extra_billing_lines": 1,   # PK-32 — nilai tagihan = grand total + tagihan tambahan nota debit
                "payments": 1, "created_at": 1, "payment_term_code": 1,
                "payment_term_days": 1, "payment_profile_method": 1, "entity_id": 1}


async def _open_orders(cust_ids: List[str], *, include_paid: bool,
                       projection: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """PK-41 (RP-01, RP-05) — pesanan pelanggan `cust_ids` (per kelompok `report_basis.KELOMPOK`, kursor tanpa batas);
    kueri menyaring status mati, dan — bila posisi = hari ini — pesanan yang sudah lunas. Posisi tanggal lampau
    (`include_paid`) ikut membaca pesanan yang kini lunas: pada tanggal itu ia bisa masih berpiutang."""
    base: Dict[str, Any] = {"status": {"$nin": sorted(DEAD_STATUSES)}}
    if not include_paid:
        base["payment_status"] = {"$ne": "paid"}
    out: List[Dict[str, Any]] = []
    for i in range(0, len(cust_ids), rb.KELOMPOK):
        q = {**base, "customer_id": {"$in": cust_ids[i:i + rb.KELOMPOK]}}
        out += [o async for o in db.sales_orders.find(q, projection or ORDER_FIELDS)]
    return out


def _per(as_of: Optional[str]) -> str:
    """Tanggal posisi laporan (tanggal buku WIB); kosong/tidak dikenali = hari ini."""
    from services.book_date import tanggal_buku
    try:
        return tanggal_buku(as_of or None)
    except ValueError:
        return tanggal_buku()


# L02 LN-023-T01 — "Belum lunas" pesanan = Piutang ledger (sudah diakui di 1-1200 lewat surat jalan)
# + Eksposur (nilai pesanan yang belum dikirim/diakui — BUKAN piutang buku besar).
AR_DEFINITIONS = {
    "outstanding": "Belum lunas = total pesanan − pembayaran (piutang tercatat + belum dikirim).",
    "ar_ledger": "Piutang tercatat = nilai surat jalan yang sudah dijurnal − pembayaran yang dialokasikan ke surat jalan "
                 "itu; pembanding saldo akun piutang ada di `reconciliation`.",
    "exposure": "Belum dikirim = nilai pesanan yang belum dikirim/diakui; belum masuk buku besar piutang.",
}


async def recognized_by_order(order_ids: List[str]) -> Dict[str, float]:
    """Σ piutang yang lahir per pesanan (Dr 1-1200/kas dari jurnal penjualan, per surat jalan, dan nota debit PK-32).
    Pengurang piutang nota kredit amandemen tidak dihitung di sini: barisnya ada di `payments[]` (Σ terbayar).
    Kas & Bank 1 — Dr kas penjualan tunai ke akun rekening tunggal PT (`gl_service.post_sales_order`) ikut terbaca."""
    from services.gl_mapping_service import known_codes
    from services.gl_service import kode_akun_rekening
    codes = set(await known_codes("penjualan.piutang")) | set(await known_codes("kas_bank.kas_besar"))
    rekening: Dict[str, set] = {}
    out: Dict[str, float] = {}
    if not order_ids:
        return out
    async for je in db.journal_entries.find(
            {"status": {"$ne": "void"}, "$or": [
                {"source_type": "sales_order", "source_id": {"$in": order_ids}},
                # PK-32 — tagihan tambahan nota debit yang sudah dijurnal (Dr 1-1200) ikut piutang ledger
                {"source_type": {"$in": ["shipment_revenue", "amendment_debit_note"]}, "ref.order_id": {"$in": order_ids}}]},
            {"_id": 0, "source_type": 1, "source_id": 1, "ref": 1, "lines": 1, "entity_id": 1}):
        oid = je["source_id"] if je["source_type"] == "sales_order" else (je.get("ref") or {}).get("order_id")
        eid = je.get("entity_id") or ""
        if je["source_type"] == "sales_order" and eid not in rekening:
            rekening[eid] = await kode_akun_rekening(eid)
        kas = rekening.get(eid, set()) if je["source_type"] == "sales_order" else set()
        amt = sum(float(l.get("debit") or 0) for l in je.get("lines") or []
                  if l.get("account_code") in codes or l.get("account_code") in kas)
        out[oid] = round(out.get(oid, 0.0) + amt, 2)
    return out


def split_outstanding(o: Dict[str, Any], outstanding: float, recognized: float) -> Dict[str, float]:
    ledger = round(min(outstanding, max(0.0, recognized - order_paid(o))), 2)
    return {"ar_ledger": ledger, "exposure": round(outstanding - ledger, 2)}


_PENALTY_KEYS = (("penalty_docs", "count"), ("penalty_draft", "draft_amount"),
                 ("penalty_issued", "issued_outstanding"), ("penalty_waived", "waived_amount"),
                 ("penalty_paid", "paid_amount"), ("penalty_actual", "actual_amount"))


def _add_penalties(target: Dict[str, Any], pen: Dict[str, Any]) -> None:
    for key, src in _PENALTY_KEYS:
        val = pen[src]
        target[key] = round(target[key] + val, 2) if isinstance(val, float) else target[key] + val


def _sisa_pesanan(lines: List[Dict[str, Any]]) -> float:
    """Σ sisa semua baris tagihan satu pesanan (dasar denda `payment.penalty_base` = seluruh sisa pesanan)."""
    return from_cents(sum(to_cents(r["sisa"]) for r in lines))


def _line_out(r: Dict[str, Any], edges: List[int], cfg: Dict[str, Any],
              order_out: Optional[float] = None) -> Dict[str, Any]:
    """Baris tagihan untuk jawaban (rincian pelanggan): baris `report_basis` + kelompok umur + estimasi denda."""
    return {**r, "bucket": _bucket(r["hari_lewat"], edges),
            "denda_estimate": _denda_estimate(r["sisa"], r["hari_lewat"], cfg, order_out)}


def _sum_lines(acc: Dict[str, Any], lines: List[Dict[str, Any]], edges: List[int], cfg: Dict[str, Any]) -> float:
    """Tambahkan baris tagihan satu pesanan ke `acc` (kolom umur, total, lewat jatuh tempo, denda, tercatat/belum
    dikirim) dalam SEN BULAT; kembalikan estimasi denda pesanan itu."""
    denda = 0.0
    order_out = _sisa_pesanan(lines)
    for r in lines:
        sen = to_cents(r["sisa"])
        b = _bucket(r["hari_lewat"], edges)
        acc["_sen"][b] = acc["_sen"].get(b, 0) + sen
        acc["_sen"]["total"] = acc["_sen"].get("total", 0) + sen
        # CR-T2 — tercatat = bagian yang sudah di akun piutang (uang muka & baris rencana belum tentu tercatat)
        tercatat = rb.tercatat_sen(r)
        acc["_sen"]["ar_ledger"] = acc["_sen"].get("ar_ledger", 0) + tercatat
        acc["_sen"]["exposure"] = acc["_sen"].get("exposure", 0) + sen - tercatat
        if r["hari_lewat"] > 0:
            acc["_sen"]["overdue"] = acc["_sen"].get("overdue", 0) + sen
            if "oldest_days" in acc:
                acc["oldest_days"] = max(acc["oldest_days"], r["hari_lewat"])
        denda += _denda_estimate(r["sisa"], r["hari_lewat"], cfg, order_out)
    denda = round(denda, 2)
    acc["denda"] = round(acc["denda"] + denda, 2)
    return denda


_SEN_KEYS = (*BUCKET_KEYS, "total", "overdue", "ar_ledger", "exposure")


def _close(acc: Dict[str, Any], total_key: str = "total") -> None:
    """Pindahkan jumlah sen bulat ke rupiah (`02` D5: total = Σ baris dalam satuan bulat)."""
    sen = acc.pop("_sen")
    for k in _SEN_KEYS:
        acc[total_key if k == "total" else k] = from_cents(sen.get(k, 0))


async def _reconciliation(ent_ids: List[str], per: str, ar_ledger_total: float,
                          sales_id: Optional[str]) -> Dict[str, Any]:
    """PK-41 (Selesai-bila) — piutang tercatat dicocokkan dengan saldo akun piutang (`penjualan.piutang`, semua akun
    yang pernah dipakai) PT itu per tanggal `per`. Saringan sales → tidak dicocokkan (buku besar tidak per sales)."""
    from services.book_date import tanggal_panjang
    if sales_id:
        return {"ar_ledger_total": ar_ledger_total, "gl_balance": None, "difference": None,
                "note": "Saringan sales aktif: saldo akun piutang tidak bisa dipecah per sales, jadi tidak dicocokkan."}
    gl_sen = await rb.saldo_akun_sen("penjualan.piutang", ent_ids or None, per)
    diff_sen = gl_sen - to_cents(ar_ledger_total)
    tgl = tanggal_panjang(per)
    note = (f"Piutang tercatat sama dengan saldo akun piutang per {tgl}." if diff_sen == 0 else
            f"Selisih = saldo akun piutang − piutang tercatat per {tgl}. Biasanya berasal dari jurnal manual ke akun "
            "piutang, nota denda, atau jurnal pendapatan yang gagal; telusuri lewat Buku Besar akun piutang.")
    return {"ar_ledger_total": ar_ledger_total, "gl_balance": from_cents(gl_sen), "difference": from_cents(diff_sen),
            "note": note}


async def aging_report(entity_id: Optional[str] = None, sales_id: Optional[str] = None,
                       as_of: Optional[str] = None) -> Dict[str, Any]:
    """Ringkasan aging piutang: totals per-bucket + baris per-customer.

    FASE G-3 — kolom denda tidak lagi hanya ESTIMASI: setiap baris juga membawa
    **nota denda NYATA** (`penalty_*`) hasil FASE G-2 sehingga angka di laporan bisa
    diklik menuju dokumennya (dan terlihat mana yang masih usulan, sudah terbit,
    dibebaskan, atau dibayar).

    PK-41 — kelompok umur, `overdue`, `oldest_days`, dan estimasi denda per BARIS TAGIHAN (per surat jalan);
    `as_of` = posisi pada tanggal itu; `bucket_labels` (judul kolom dari `ar.aging_buckets`); `reconciliation`
    (piutang tercatat vs saldo akun piutang per tanggal itu).
    """
    per = _per(as_of)
    # FASE E-0 (L9) — normalisasi: kebijakan (config) selalu dibaca dengan entitas
    # SKALAR; filter query boleh berupa dict `{"$in": [...]}` untuk mode gabungan.
    _cfg_entity = entity_id if isinstance(entity_id, str) and entity_id != "all" else None
    if isinstance(entity_id, dict):
        _one = (entity_id.get("$in") or [])
        _cfg_entity = _one[0] if len(_one) == 1 else None
    cfg = await get_ar_config(_cfg_entity)
    cust_cfg: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    pt_cache: Dict[str, Any] = {}   # CR-T4 — aturan denda grup → PT sekali per PT
    customers, smap = await _load_scope(entity_id, sales_id)
    cmap = {c["id"]: c for c in customers}
    cust_ids = list(cmap.keys())

    per_customer: Dict[str, Dict[str, Any]] = {}
    totals = {**_empty_buckets(), "total": 0.0, "overdue": 0.0, "denda": 0.0,
              "orders": 0, "customers": 0,
              # FASE G-3 — nota denda nyata (dokumen), bukan estimasi
              "penalty_docs": 0, "penalty_draft": 0.0, "penalty_issued": 0.0,
              "penalty_waived": 0.0, "penalty_paid": 0.0, "penalty_actual": 0.0,
              "ar_ledger": 0.0, "exposure": 0.0, "_sen": {}}

    if cust_ids:
        orders = await _open_orders(cust_ids, include_paid=bool(as_of))
        lines_by_order = await rb.baris_tagihan(orders, cmap, per=per)
        open_orders = [o for o in orders if lines_by_order.get(o["id"])]

        # Nota denda nyata untuk seluruh pesanan pelanggan dalam SATU query.
        from services import penalty_service as penalties
        pen_by_doc = await penalties.for_docs([o.get("id") for o in open_orders])
        rencana_denda = await _rencana_berdenda([o["id"] for o in open_orders])   # CR-T4

        for o in open_orders:
            lines = lines_by_order[o["id"]]
            cid = o.get("customer_id")
            cust = cmap.get(cid, {})
            # CR-T4 — aturan denda per pasangan (PT pesanan, pelanggan): aturan PT → profil kredit pelanggan di PT itu,
            # sama dengan nota denda pesanan ini (`accrue_plan` memakai PT jadwal = PT pesanan).
            rencana = rencana_denda.get(o["id"])
            kunci_cfg = (o.get("entity_id") or _cfg_entity or "", cid, (rencana or {}).get("id", ""))
            ccfg = cust_cfg.get(kunci_cfg)
            if ccfg is None:
                ccfg = await get_ar_config(kunci_cfg[0], cid, rencana, pt_cache)
                cust_cfg[kunci_cfg] = ccfg
            pen = penalties.summarize(pen_by_doc.get(o.get("id")) or [])

            row = per_customer.get(cid)
            if not row:
                row = {
                    "customer_id": cid,
                    "customer_name": o.get("customer_name") or cust.get("name", ""),
                    "assigned_sales_id": cust.get("assigned_sales_id", ""),
                    "assigned_sales_name": smap.get(cust.get("assigned_sales_id", ""), ""),
                    "credit_limit": 0.0,   # CR-T1 — diisi dari profil kredit efektif di bawah
                    "deposit_balance": round(float(cust.get("deposit_balance", 0) or 0), 2),
                    **_empty_buckets(),
                    "outstanding": 0.0, "overdue": 0.0, "denda": 0.0,
                    "oldest_days": 0, "orders": 0,
                    "penalty_docs": 0, "penalty_draft": 0.0, "penalty_issued": 0.0,
                    "penalty_waived": 0.0, "penalty_paid": 0.0, "penalty_actual": 0.0,
                    "ar_ledger": 0.0, "exposure": 0.0, "_sen": {},
                }
                per_customer[cid] = row
            edges = ccfg.get("aging_buckets")
            _sum_lines(row, lines, edges, ccfg)
            _sum_lines(totals, lines, edges, ccfg)
            row["orders"] += 1
            totals["orders"] += 1
            _add_penalties(row, pen)
            _add_penalties(totals, pen)

    rows: List[Dict[str, Any]] = []
    from services import credit_profile_service as _cps
    kc = _cps.cache_baru()   # KF-T7/CR-T1 — ambang & plafon bawaan sekali per PT; profil kredit satu kueri
    await _cps.muat_profil(kc, list(per_customer))
    for row in per_customer.values():
        _close(row, "outstanding")
        st, eff = await _credit_status(cmap.get(row["customer_id"]) or {"id": row["customer_id"]}, row["outstanding"],
                                       row["oldest_days"], _cfg_entity, kc)
        row["credit_status"] = st
        row["credit_limit"] = round(float(eff["credit_limit"] or 0), 2)
        row["limit_source"] = eff["limit_source"]
        row["available_credit"] = (round(max(row["credit_limit"] - row["outstanding"], 0), 2)
                                   if row["credit_limit"] > 0 else None)
        # Selisih antara denda ESTIMASI dan denda yang benar-benar sudah jadi dokumen —
        # inilah "pekerjaan yang belum dilakukan" (belum dibuatkan nota).
        row["denda_undocumented"] = round(max(row["denda"] - row["penalty_actual"], 0), 2)
        rows.append(row)
    rows.sort(key=lambda r: r["outstanding"], reverse=True)
    _close(totals)
    totals["customers"] = len(rows)
    totals["denda_undocumented"] = round(
        max(totals["denda"] - totals["penalty_actual"], 0), 2)

    from services import penalty_service as _pen
    # FASE E-0 (L9) — laporan WAJIB menyebut entitasnya. Dulu `entity_id` selalu "all"
    # dan totalnya identik untuk KSC/KANDA/ALL (Rp 20.260.900) karena konteks tak dibaca.
    ent_scalar = entity_id if isinstance(entity_id, str) else None
    ent_ids = (entity_id or {}).get("$in", []) if isinstance(entity_id, dict) else (
        [ent_scalar] if ent_scalar and ent_scalar != "all" else [])
    ent_name = ""
    if len(ent_ids) == 1:
        ent = await db.business_entities.find_one({"id": ent_ids[0]}, {"_id": 0})
        ent_name = (ent or {}).get("short_name") or (ent or {}).get("legal_name") or ent_ids[0]
    elif ent_ids:
        names = []
        async for e in db.business_entities.find({"id": {"$in": ent_ids}}, {"_id": 0}):
            names.append(e.get("short_name") or e.get("legal_name") or e.get("id"))
        ent_name = "Gabungan: " + " + ".join(sorted(names))
    else:
        ent_name = "Semua Entitas (gabungan)"
    return {
        "as_of": per,
        "entity_id": ent_ids[0] if len(ent_ids) == 1 else "all",
        "entity_ids": ent_ids,
        "entity_name": ent_name,
        "is_consolidated": len(ent_ids) != 1,
        "config": cfg,
        "bucket_labels": rb.label_kelompok_umur(cfg.get("aging_buckets")),   # PK-41 (RP-12)
        "definitions": AR_DEFINITIONS,
        # FASE G-3 — kebijakan denda yang BERLAKU ikut dikirim supaya layar bisa
        # menjelaskan kenapa estimasi & nota denda bisa berbeda (dasar hitung, tenggang).
        "penalty_policy": await _pen.penalty_policy(ent_ids[0] if len(ent_ids) == 1 else ""),
        "totals": totals,
        "customers": rows,
        "reconciliation": await _reconciliation(ent_ids, per, totals["ar_ledger"], sales_id),
    }


async def orders_due_soon(offsets: List[int], entity_id: Optional[str] = None,
                          sales_id: Optional[str] = None,
                          as_of: Optional[str] = None) -> List[Dict[str, Any]]:
    """PS-21 — daftar order AR yang jatuh tempo **tepat** pada offset hari tertentu.

    `offsets` dihitung sebagai `hari_lewat` (`report_basis.hari_antara(jatuh_tempo, hari ini)`): `-3` = 3 hari
    sebelum jatuh tempo (H-3), `0` = hari-H, `1` = H+1.

    PK-41 (RP-03) — per BARIS TAGIHAN terkirim (per surat jalan) yang masih bersisa: satu baris jawaban per pesanan
    dan tanggal jatuh tempo; `outstanding` = sisa baris yang jatuh tempo pada tanggal itu. Bagian pesanan yang belum
    dikirim tidak diingatkan. Rumus sama dengan `aging_report` (R3).
    """
    wanted = {int(o) for o in (offsets or [])}
    if not wanted:
        return []
    per = _per(as_of)
    customers, smap = await _load_scope(entity_id, sales_id)
    cmap = {c["id"]: c for c in customers}
    if not cmap:
        return []
    orders = await _open_orders(list(cmap.keys()), include_paid=bool(as_of))
    lines_by_order = await rb.baris_tagihan(orders, cmap, per=per)

    rows: List[Dict[str, Any]] = []
    for o in orders:
        cust = cmap.get(o.get("customer_id"), {})
        per_due: Dict[str, int] = {}
        for r in lines_by_order.get(o["id"]) or []:
            if r["sumber"] == rb.SUMBER_BELUM_DIKIRIM or r["hari_lewat"] not in wanted:
                continue
            per_due[r["jatuh_tempo"]] = per_due.get(r["jatuh_tempo"], 0) + to_cents(r["sisa"])
        for due, sen in per_due.items():
            rows.append({
                "order_id": o.get("id"), "number": o.get("number", ""),
                "customer_id": o.get("customer_id"),
                "customer_name": o.get("customer_name") or cust.get("name", ""),
                "assigned_sales_id": cust.get("assigned_sales_id", ""),
                "assigned_sales_name": smap.get(cust.get("assigned_sales_id", ""), ""),
                "entity_id": o.get("entity_id"),
                "outstanding": from_cents(sen),
                "due_date": due,
                "offset": rb.hari_antara(due, per),
            })
    rows.sort(key=lambda r: (-r["offset"], -r["outstanding"]))
    return rows


async def _plafon(customer: Dict[str, Any]) -> Dict[str, Any]:
    from services import credit_profile_service as cps
    return await cps.effective(customer["id"], customer.get("entity_id") or "", customer=customer)


async def customer_aging_detail(customer_id: str, as_of: Optional[str] = None,
                               entity_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Rincian per-order untuk satu customer (untuk drill-down).

    FASE G-3 — tiap baris membawa **nota denda nyata** pesanan itu (nomor, status, jurnal)
    sehingga kolom denda di laporan bisa diklik ke dokumennya, plus penanda pesanan mana
    yang dendanya masih sekadar estimasi (belum pernah dibuatkan nota).

    FASE E-0 (L9) — `entity_ids` = pagar anti-IDOR: bila diisi, pelanggan di luar
    entitas itu dianggap TIDAK ADA (404 di router).

    PK-41 — tiap pesanan memuat `lines[]` (baris per surat jalan + satu baris "belum dikirim"); `due_date`,
    `days_late`, `bucket`, dan estimasi denda pesanan diturunkan dari baris-baris itu.
    """
    cust_q: Dict[str, Any] = {"id": customer_id}
    if entity_ids:
        cust_q["entity_id"] = {"$in": list(entity_ids)}
    customer = await db.customers.find_one(
        cust_q,
        {"_id": 0, "id": 1, "name": 1, "assigned_sales_id": 1, "payment_profile": 1,
         "credit_limit": 1, "status": 1, "deposit_balance": 1, "entity_id": 1},   # CR-T1: credit_limit/status → data lama
    )
    if not customer:
        return None
    per = _per(as_of)
    # CR-T4 — aturan PT pemilik data pelanggan untuk ringkasan; tiap pesanan memakai aturan (PT pesanan, pelanggan,
    # rencana berdenda) yang sama dengan notanya.
    cfg = await get_ar_config(customer.get("entity_id") or "", customer_id)
    edges = cfg.get("aging_buckets")
    orders = await _open_orders([customer_id], include_paid=bool(as_of), projection={"_id": 0})
    lines_by_order = await rb.baris_tagihan(orders, {customer_id: customer}, per=per)
    orders = [o for o in orders if lines_by_order.get(o["id"])]

    from services import penalty_service as penalties
    from services import payment_plan_service as plans
    pen_by_doc = await penalties.for_docs([o.get("id") for o in orders])
    rencana_denda = await _rencana_berdenda([o["id"] for o in orders])
    cfg_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
    pt_cache: Dict[str, Any] = {}

    items: List[Dict[str, Any]] = []
    totals = {**_empty_buckets(), "total": 0.0, "overdue": 0.0, "denda": 0.0,
              "penalty_docs": 0, "penalty_draft": 0.0, "penalty_issued": 0.0,
              "penalty_waived": 0.0, "penalty_paid": 0.0, "penalty_actual": 0.0,
              "ar_ledger": 0.0, "exposure": 0.0, "_sen": {}}
    all_penalties: List[Dict[str, Any]] = []
    plan_rows: List[Dict[str, Any]] = []
    for o in orders:
        lines = lines_by_order[o["id"]]
        sm = rb.ringkas_baris(lines)
        rencana = rencana_denda.get(o["id"])
        kunci_cfg = (o.get("entity_id") or customer.get("entity_id") or "", (rencana or {}).get("id", ""))
        ocfg = cfg_cache.get(kunci_cfg)
        if ocfg is None:
            ocfg = cfg_cache[kunci_cfg] = await get_ar_config(kunci_cfg[0], customer_id, rencana, pt_cache)
        denda = _sum_lines(totals, lines, edges, ocfg)
        days_late = sm["max_days"] if sm["due_date"] else 0   # belum dikirim → belum jatuh tempo
        pen_rows = pen_by_doc.get(o.get("id")) or []
        pen = penalties.summarize(pen_rows)
        _add_penalties(totals, pen)
        plan = await plans.get_manual("sales_order", o.get("id", ""))   # CR-T2 — kolom "rencana" = rencana cicilan
        if plan:
            nd = plans.next_due(plan) or {}
            plan_rows.append({
                "plan_id": plan["id"], "plan_number": plan.get("number", ""),
                "order_id": o.get("id"), "order_number": o.get("number") or o.get("id"),
                "mode_label": plan.get("mode_label", ""),
                "next_due_date": nd.get("due_date", ""),
                "overdue_count": len(plans.overdue_lines(plan)),
            })
        for p in pen_rows:
            all_penalties.append({**p, "order_number": o.get("number") or o.get("id")})
        items.append({
            "order_id": o.get("id"),
            "order_number": o.get("number") or o.get("id"),
            "grand_total": round(order_grand_total(o), 2),
            "paid_total": rb.terbayar_per(o, per),
            "outstanding": sm["total"],
            "ar_ledger": sm["ar_ledger"], "exposure": sm["exposure"],
            "status": o.get("status"),
            "due_date": sm["due_date"] or "",
            "due_basis": "per_sj" if sm["due_date"] else "not_shipped",
            "days_late": days_late,
            "bucket": _bucket(days_late, edges),
            "overdue": days_late > 0,
            "overdue_amount": sm["overdue"],
            "denda_estimate": denda,
            "lines": [_line_out(r, edges, ocfg, _sisa_pesanan(lines)) for r in lines],   # PK-41 — per surat jalan
            # FASE G-3 — dokumen denda nyata pada pesanan ini
            "penalties": [{"id": p.get("id"), "number": p.get("number"),
                           "status": p.get("status"), "status_label": p.get("status_label", ""),
                           "amount": round(float(p.get("amount") or 0), 2),
                           "paid_amount": round(float(p.get("paid_amount") or 0), 2),
                           "due_date": p.get("due_date", ""),
                           "line_label": p.get("line_label", ""),
                           "je_number": p.get("je_number", ""),
                           "reason_label": p.get("reason_label", "")} for p in pen_rows],
            "penalty_docs": pen["count"],
            "penalty_actual": pen["actual_amount"],
            "penalty_draft": pen["draft_amount"],
            "penalty_issued": pen["issued_outstanding"],
            "penalty_undocumented": round(max(denda - pen["actual_amount"], 0), 2),
            "has_plan": bool(plan),
            "plan_number": (plan or {}).get("number", ""),
            "payment_status": o.get("payment_status") or "unpaid",
            "created_at": o.get("created_at"),
        })
    items.sort(key=lambda r: r["days_late"], reverse=True)
    all_penalties.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    _close(totals)
    totals["denda_undocumented"] = round(max(totals["denda"] - totals["penalty_actual"], 0), 2)

    return {
        "customer_id": customer["id"],
        "customer_name": customer.get("name", ""),
        "as_of": per,
        # CR-T1 — plafon yang BERLAKU (profil kredit PT pemilik data pelanggan), bukan `customers.credit_limit`.
        "credit_limit": round(float((await _plafon(customer))["credit_limit"] or 0), 2),
        "deposit_balance": round(float(customer.get("deposit_balance", 0) or 0), 2),
        "config": cfg,
        "bucket_labels": rb.label_kelompok_umur(edges),   # PK-41 (RP-12)
        "definitions": AR_DEFINITIONS,
        "penalty_policy": cfg["penalty"],   # CR-T4 — aturan (PT pemilik data, pelanggan) + asal tiap unsur
        "totals": totals,
        "items": items,
        "penalties": all_penalties,
        "plans": plan_rows,
    }
