"""CR-T2 (CR-09; `02` D2) — SALDO PIUTANG TERSIMPAN per (pelanggan, PT): koleksi `customer_balances` (awalan `cbl_`).

Angka TURUNAN: selalu hitung ulang penuh satu pasangan dari dokumen (`compute`), tidak pernah ditambah-kurang selisih.
Pembangun ulang: `rebuild_all` (+ `POST /api/ar/balances/rebuild`). Invarian: INV-BAL-01 (isi tersimpan = hasil hitung
ulang) dan INV-BAL-02 (Σ piutang terkirim per PT = saldo akun piutang; selisih yang terjelaskan disebut sebabnya) di
`scripts/verify_data_integrity.py` lapisan `balance`.

Rumus (per pesanan hidup pasangan itu; uang dalam sen bulat `02` D5, tanggal WIB `02` D6):

* `sisa`            = nilai tagihan (`_order_grand_total`) − Σ pembayaran bertanggal ≤ hari ini
* `ar_delivered`    = Σ min(sisa, max(0, pengakuan − terbayar)) — pengakuan = Σ debit akun piutang jurnal pengakuan
                      penjualan pesanan (surat jalan, jurnal lama per pesanan, nota debit), terbayar = tanpa nota kredit
                      tertangguh (PK-32; aturan `report_basis.baris_tagihan`)
* `open_orders_amount` = Σ (sisa − bagian terkirim di atas)
* `cash_term_amount`, `cash_term_open_amount` = bagian dua angka di atas dari pesanan bertermin tunai tanpa DP
  (`report_basis.pesanan_piutang` palsu) — CR-T2 (b) tetap melewatinya untuk status kredit (perilaku hari ini, CR-T3)
* `overdue_amount`  = Σ sisa baris jadwal tagihan (`billing_schedule_service`) ber-jatuh tempo < hari ini, pesanan
                      berpiutang saja; `oldest_due_date` = jatuh tempo tertua baris yang masih bersisa; `overdue_as_of`
* `giro_outstanding` = Σ kwitansi giro tidak-batal yang belum terverifikasi bank (PM-T3 `bank_verified`)
* `deposit_balance` = cermin `customers.deposit_balance` pada PT pemilik data pelanggan (titipan belum per PT);
  `store_credit_balance` = buku saldo kredit pasangan itu; `penalty_outstanding` = Σ nota denda terbit − terbayar
* `last_payment_at`, `last_payment_amount` = kwitansi tidak-batal terakhir pasangan itu

Kegagalan `refresh` tidak membatalkan dokumen pemicunya: pasangan ditandai `stale: true` dan dibetulkan pembaca (`get`)
atau job harian 00.10 WIB (`job_refresh_overdue`).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core_utils import from_cents, new_id, now_iso, safe_doc, to_cents
from db import db
from services import report_basis as rb
from services.book_date import tanggal_buku

logger = logging.getLogger(__name__)

COLL = "customer_balances"
#: Field angka yang dibandingkan pembangun ulang dan INV-BAL-01.
FIELDS = ("ar_delivered", "cash_term_amount", "open_orders_amount", "cash_term_open_amount", "open_orders_count",
          "overdue_amount", "oldest_due_date", "overdue_as_of", "giro_outstanding", "deposit_balance",
          "store_credit_balance", "penalty_outstanding", "last_payment_at", "last_payment_amount")
#: Kata cara bayar giro pada kwitansi (kode daftar induk PM-T1 + kata lama).
GIRO = ("giro", "cek", "bilyet_giro")


def _hari(today: Any = None) -> str:
    return tanggal_buku(today or None)


async def _orders(customer_id: str, entity_id: str) -> List[Dict[str, Any]]:
    from services.customer_service import DEAD_STATUSES
    q = {"customer_id": customer_id, "entity_id": entity_id, "status": {"$nin": sorted(DEAD_STATUSES)},
         "payment_status": {"$ne": "paid"}}
    return [o async for o in db.sales_orders.find(q, {"_id": 0})]


async def compute(customer_id: str, entity_id: str, today: Any = None) -> Dict[str, Any]:
    """Saldo satu pasangan, MURNI dari dokumen (tidak menulis). Lihat rumus di kepala modul."""
    from services import billing_schedule_service as bss
    from services import store_credit_service
    from services.customer_service import _order_grand_total
    hari = _hari(today)
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0}) or {"id": customer_id}
    orders = await _orders(customer_id, entity_id)
    jurnal = await rb._jurnal_pendapatan([o["id"] for o in orders])   # noqa: SLF001
    jadwal = await bss.lines_for_orders(orders, {customer_id: customer}, per=hari)
    kode_cache: Dict[str, set] = {}
    delivered = cash_del = open_amt = cash_open = 0
    overdue = 0
    oldest: Optional[str] = None
    n_open = 0
    for o in orders:
        total = to_cents(_order_grand_total(o))
        bayar_semua = max(0, rb._terbayar_sen(o, hari))                  # noqa: SLF001
        bayar_kirim = max(0, rb._terbayar_sen(o, hari, tangguh=False))   # noqa: SLF001
        sisa = max(0, total - bayar_semua)
        if sisa <= 0:
            continue
        akui = await bss.recognized_sen(o, jurnal.get(o["id"], []), kode_cache, per=hari)
        kirim = min(sisa, max(0, akui - bayar_kirim))
        tunai = not rb.pesanan_piutang(o)
        delivered += kirim
        open_amt += sisa - kirim
        if tunai:
            cash_del += kirim
            cash_open += sisa - kirim
            continue
        n_open += 1
        for r in (jadwal.get(o["id"]) or {}).get("rows") or []:
            if r["outstanding"] <= rb.EPS or not r.get("due_date"):
                continue
            oldest = r["due_date"] if oldest is None else min(oldest, r["due_date"])
            if r["due_date"] < hari:
                overdue += to_cents(r["outstanding"])
    deposit = round(float(customer.get("deposit_balance") or 0), 2) if customer.get("entity_id") == entity_id else 0.0
    store = round(float(await store_credit_service.balance(customer_id, entity_id) or 0), 2)
    pen = 0
    async for p in db.penalties.find({"customer_id": customer_id, "entity_id": entity_id,
                                      "status": {"$in": ["issued", "adjusted"]}},
                                     {"_id": 0, "amount": 1, "paid_amount": 1}):
        pen += to_cents(float(p.get("amount") or 0)) - to_cents(float(p.get("paid_amount") or 0))
    giro = 0
    last: Optional[Dict[str, Any]] = None
    async for rc in db.ar_receipts.find({"customer_id": customer_id, "entity_id": entity_id,
                                         "status": {"$ne": "void"}},
                                        {"_id": 0, "amount": 1, "method": 1, "payment_method_code": 1,
                                         "bank_verified": 1, "receipt_date": 1, "created_at": 1}):
        cara = str(rc.get("payment_method_code") or rc.get("method") or "").lower()
        if cara in GIRO and not rc.get("bank_verified"):
            giro += to_cents(float(rc.get("amount") or 0))
        kapan = str(rc.get("receipt_date") or rc.get("created_at") or "")
        if last is None or kapan > str(last.get("receipt_date") or last.get("created_at") or ""):
            last = rc
    return {
        "customer_id": customer_id, "entity_id": entity_id,
        "ar_delivered": from_cents(delivered), "cash_term_amount": from_cents(cash_del),
        "open_orders_amount": from_cents(open_amt), "cash_term_open_amount": from_cents(cash_open),
        "open_orders_count": n_open,
        "overdue_amount": from_cents(overdue), "oldest_due_date": oldest, "overdue_as_of": hari,
        "giro_outstanding": from_cents(giro), "deposit_balance": deposit, "store_credit_balance": store,
        "penalty_outstanding": from_cents(max(0, pen)),
        "last_payment_at": (last or {}).get("receipt_date") or (last or {}).get("created_at") or None,
        "last_payment_amount": round(float((last or {}).get("amount") or 0), 2) if last else 0.0,
    }


#: Jenis jurnal pengakuan piutang pesanan (sama dengan `report_basis._jurnal_pendapatan`).
_JURNAL_PESANAN = ("shipment_revenue", "amendment_debit_note")


async def sidik(customer_id: str, entity_id: str) -> str:
    """Sidik murah dokumen sumber satu pasangan: ringkasan pesanan (id, waktu ubah, status, terbayar) + banyak jurnal pengakuan
    piutang + banyak kwitansi/nota denda. Berbeda dari sidik tersimpan → saldo basi (penulis yang melewati `refresh`,
    mis. data disisipkan langsung) → `get` menghitung ulang. Bukan angka bisnis; tidak dibandingkan INV-BAL-01."""
    import hashlib
    ids: List[str] = []
    h = hashlib.sha1()
    async for o in db.sales_orders.find({"customer_id": customer_id, "entity_id": entity_id},
                                        {"_id": 0, "id": 1, "updated_at": 1, "created_at": 1, "status": 1,
                                         "paid_total": 1, "grand_total": 1, "payment_status": 1}).sort("id", 1):
        ids.append(o["id"])
        h.update(f"{o['id']}:{o.get('updated_at') or o.get('created_at')}:{o.get('status')}:{o.get('paid_total')}:"
                 f"{o.get('grand_total')}:{o.get('payment_status')};".encode())
    terakhir = h.hexdigest()[:16]
    nj = 0
    for i in range(0, len(ids), rb.KELOMPOK):
        grup = ids[i:i + rb.KELOMPOK]
        nj += await db.journal_entries.count_documents({"status": {"$ne": "void"}, "$or": [
            {"source_type": {"$in": list(_JURNAL_PESANAN)}, "ref.order_id": {"$in": grup}},
            {"source_type": "sales_order", "source_id": {"$in": grup}}]})
    nk = await db.ar_receipts.count_documents({"customer_id": customer_id, "entity_id": entity_id,
                                               "status": {"$ne": "void"}})
    nd = await db.penalties.count_documents({"customer_id": customer_id, "entity_id": entity_id,
                                             "status": {"$in": ["issued", "adjusted", "paid", "waived"]}})
    return f"{len(ids)}|{terakhir}|{nj}|{nk}|{nd}"


def _beda(a: Dict[str, Any], b: Optional[Dict[str, Any]]) -> List[str]:
    if not b:
        return list(FIELDS)
    return [f for f in FIELDS if a.get(f) != b.get(f)]


async def _tulis(doc: Dict[str, Any], *, rebuilt: bool = False) -> Dict[str, Any]:
    now = now_iso()
    isi = {**doc, "stale": False, "stale_reason": "", "updated_at": now,
           "fingerprint": await sidik(doc["customer_id"], doc["entity_id"])}
    if rebuilt:
        isi["rebuilt_at"] = now
    await db[COLL].update_one({"customer_id": doc["customer_id"], "entity_id": doc["entity_id"]},
                              {"$set": isi, "$setOnInsert": {"id": new_id("cbl"), "created_at": now}}, upsert=True)
    return safe_doc(await db[COLL].find_one({"customer_id": doc["customer_id"], "entity_id": doc["entity_id"]},
                                            {"_id": 0}))


async def _pasangan_pelanggan(customer_id: str) -> List[str]:
    ents = set(e for e in await db.sales_orders.distinct("entity_id", {"customer_id": customer_id}) if e)
    ents |= set(e for e in await db[COLL].distinct("entity_id", {"customer_id": customer_id}) if e)
    c = await db.customers.find_one({"id": customer_id}, {"_id": 0, "entity_id": 1})
    if (c or {}).get("entity_id"):
        ents.add(c["entity_id"])
    return sorted(ents)


async def refresh(customer_id: str, entity_id: Optional[str] = None, today: Any = None) -> Optional[Dict[str, Any]]:
    """Hitung ulang penuh lalu simpan pasangan (pelanggan, PT); tanpa PT = semua PT pelanggan itu (PM-T3 memanggil
    `refresh(customer_id)`). Galat TIDAK dilempar: pasangan ditandai `stale` (dibetulkan pembaca/job harian)."""
    if not customer_id:
        return None
    ents = [entity_id] if entity_id else await _pasangan_pelanggan(customer_id)
    out = None
    for eid in ents:
        try:
            out = await _tulis(await compute(customer_id, eid, today))
        except Exception as exc:  # noqa: BLE001 — saldo turunan; dokumen pemicu tetap sah
            logger.warning("[CR-T2] saldo pelanggan %s/%s gagal dihitung: %s", customer_id, eid, exc)
            await db[COLL].update_one({"customer_id": customer_id, "entity_id": eid},
                                      {"$set": {"stale": True, "stale_reason": str(exc)[:300], "updated_at": now_iso()},
                                       "$setOnInsert": {"id": new_id("cbl"), "created_at": now_iso()}}, upsert=True)
    return out


async def refresh_safe(customer_id: str, entity_id: Optional[str] = None) -> None:
    """Untuk kait di alur dokumen: tidak pernah melempar."""
    try:
        await refresh(customer_id, entity_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[CR-T2] kait saldo pelanggan %s gagal: %s", customer_id, exc)


def with_days(row: Optional[Dict[str, Any]], today: Any = None) -> Optional[Dict[str, Any]]:
    """`days_overdue` dihitung saat baca: hari sejak jatuh tempo tertua yang masih bersisa (0 bila belum lewat)."""
    if not row:
        return row
    hari = _hari(today)
    od = row.get("oldest_due_date")
    row = dict(row)
    row["days_overdue"] = max(0, rb.hari_antara(od, hari)) if od and od < hari else 0
    return row


async def get(customer_id: str, entity_id: str, today: Any = None) -> Dict[str, Any]:
    """Saldo tersimpan; disegarkan dulu bila belum ada, basi (`stale`), dihitung untuk tanggal lain, atau dokumen
    sumbernya berubah tanpa lewat `refresh` (sidik berbeda — jaring pengaman untuk penulis yang belum berkait)."""
    hari = _hari(today)
    row = await db[COLL].find_one({"customer_id": customer_id, "entity_id": entity_id}, {"_id": 0})
    if not row or row.get("stale") or row.get("overdue_as_of") != hari or \
            row.get("fingerprint") != await sidik(customer_id, entity_id):
        row = await refresh(customer_id, entity_id, today) or row
        if not row or row.get("stale"):   # gagal dihitung → jawab dari dokumen tanpa menyimpan
            row = {**(await compute(customer_id, entity_id, today)), "stale": True}
    return with_days(safe_doc(row), today)


async def get_many(customer_id: str, entity_ids: Optional[Iterable[str]] = None, today: Any = None) -> Dict[str, Any]:
    """Jumlah saldo pelanggan atas beberapa PT (None = semua PT pelanggan itu) — untuk kartu pelanggan lintas PT."""
    ents = list(entity_ids) if entity_ids else await _pasangan_pelanggan(customer_id)
    rows = [await get(customer_id, e, today) for e in ents]
    tot: Dict[str, Any] = {"customer_id": customer_id, "entity_ids": ents, "rows": rows}
    for f in ("ar_delivered", "cash_term_amount", "open_orders_amount", "cash_term_open_amount", "overdue_amount",
              "giro_outstanding", "deposit_balance", "store_credit_balance", "penalty_outstanding"):
        tot[f] = from_cents(sum(to_cents(float(r.get(f) or 0)) for r in rows))
    tot["open_orders_count"] = sum(int(r.get("open_orders_count") or 0) for r in rows)
    tgl = [r["oldest_due_date"] for r in rows if r.get("oldest_due_date")]
    tot["oldest_due_date"] = min(tgl) if tgl else None
    tot["days_overdue"] = max([int(r.get("days_overdue") or 0) for r in rows] + [0])
    return tot


async def _semua_pasangan(entity_id: Optional[str] = None) -> List[Tuple[str, str]]:
    from services.customer_service import DEAD_STATUSES
    q: Dict[str, Any] = {"status": {"$nin": sorted(DEAD_STATUSES)}}
    if entity_id:
        q["entity_id"] = entity_id
    pairs = set()
    async for o in db.sales_orders.find(q, {"_id": 0, "customer_id": 1, "entity_id": 1}):
        if o.get("customer_id") and o.get("entity_id"):
            pairs.add((o["customer_id"], o["entity_id"]))
    async for b in db[COLL].find({"entity_id": entity_id} if entity_id else {}, {"_id": 0, "customer_id": 1,
                                                                                 "entity_id": 1}):
        if b.get("customer_id") and b.get("entity_id"):
            pairs.add((b["customer_id"], b["entity_id"]))
    async for c in db.customers.find({"entity_id": entity_id} if entity_id else {"entity_id": {"$nin": [None, ""]}},
                                     {"_id": 0, "id": 1, "entity_id": 1, "deposit_balance": 1}):
        if c.get("id") and c.get("entity_id") and float(c.get("deposit_balance") or 0):
            pairs.add((c["id"], c["entity_id"]))
    return sorted(pairs)


async def rebuild_all(entity_id: Optional[str] = None, today: Any = None) -> Dict[str, Any]:
    """Pembangun ulang (`02` D2): hitung ulang penuh tiap pasangan; tulis hanya yang berbeda. → `{pairs, changed,
    seconds}` (+ `changed_pairs` untuk jejak)."""
    t0 = time.perf_counter()
    pairs = await _semua_pasangan(entity_id)
    changed: List[Dict[str, Any]] = []
    for cid, eid in pairs:
        baru = await compute(cid, eid, today)
        lama = await db[COLL].find_one({"customer_id": cid, "entity_id": eid}, {"_id": 0})
        beda = _beda(baru, lama)
        if beda or (lama or {}).get("stale"):
            await _tulis(baru, rebuilt=True)
            changed.append({"customer_id": cid, "entity_id": eid, "fields": beda})
    return {"pairs": len(pairs), "changed": len(changed), "seconds": round(time.perf_counter() - t0, 3),
            "changed_pairs": changed[:200]}


async def job_refresh_overdue() -> Dict[str, Any]:
    """Job harian 00.10 WIB: pergantian hari mengubah lewat tempo tanpa dokumen baru → pasangan yang dihitung untuk
    tanggal lain atau basi dihitung ulang."""
    hari = _hari()
    pasangan = [(b["customer_id"], b["entity_id"]) async for b in db[COLL].find(
        {"$or": [{"overdue_as_of": {"$ne": hari}}, {"stale": True}]}, {"_id": 0, "customer_id": 1, "entity_id": 1})]
    for cid, eid in pasangan:   # daftar diambil dulu: kursor tidak membaca ulang baris yang baru ditulis
        await refresh(cid, eid)
    return {"refreshed": len(pasangan), "as_of": hari}


# ── Invarian (dipanggil `scripts/verify_data_integrity.py` lapisan `balance` dan uji) ───────────────────────────────
async def verify_stored(today: Any = None) -> Dict[str, Any]:
    """INV-BAL-01: tiap baris tersimpan yang sidik dokumennya masih sama = hasil hitung ulang untuk tanggal hitungnya
    (`overdue_as_of`); baris `stale` = merah. → `{bad, checked, missing, stale}`; `missing` = pasangan berpiutang yang belum
    punya baris, `stale` = baris yang sidiknya sudah berbeda (disegarkan saat dibaca) — keduanya WARN."""
    bad: List[str] = []
    basi: List[Tuple[str, str]] = []
    checked = 0
    async for row in db[COLL].find({}, {"_id": 0}):
        checked += 1
        if not row.get("stale") and row.get("fingerprint") != await sidik(row["customer_id"], row["entity_id"]):
            # dokumen sumber berubah lewat jalur yang belum memanggil `refresh` (mis. pesanan baru belum dikonfirmasi):
            # baris mengaku basi lewat sidiknya dan disegarkan pembaca (`get`) / job harian — bukan kerusakan angka
            basi.append((row["customer_id"], row["entity_id"]))
            continue
        baru = await compute(row["customer_id"], row["entity_id"], row.get("overdue_as_of") or today)
        beda = _beda(baru, row)
        if beda or row.get("stale"):
            nama = (await db.customers.find_one({"id": row["customer_id"]}, {"_id": 0, "name": 1}) or {}).get("name")
            bad.append(f"{nama or row['customer_id']} ({row['customer_id']}) / {row['entity_id']}: "
                       f"{', '.join(beda) or 'ditandai basi'}")
    ada = {(b["customer_id"], b["entity_id"]) async for b in db[COLL].find({}, {"_id": 0, "customer_id": 1,
                                                                                 "entity_id": 1})}
    missing = [p for p in await _semua_pasangan() if p not in ada]
    return {"bad": bad, "checked": checked, "missing": missing, "stale": basi}


#: INV-BAL-02 — sebab selisih yang terjelaskan (daftar PK-41): source_type jurnal → label sebab.
SEBAB = {"manual": "jurnal tanpa pesanan", "manual_void": "jurnal tanpa pesanan", "finance_case": "kasus keuangan"}


async def reconcile_gl(entity_id: str, today: Any = None) -> Dict[str, Any]:
    """INV-BAL-02 per PT: Σ `ar_delivered` (dihitung dari dokumen untuk semua pasangan PT itu) vs saldo akun piutang
    (`penjualan.piutang`, semua akun yang pernah dipakai) per hari ini. Selisih dipecah per sebab (`SEBAB`); sisa yang
    tidak terjelaskan = merah. → `{entity_id, ar_delivered, gl_balance, difference, explained: {sebab: rupiah},
    unexplained}`."""
    from services.gl_mapping_service import known_codes
    hari = _hari(today)
    pairs = [p for p in await _semua_pasangan(entity_id) if p[1] == entity_id]
    total = 0
    for cid, eid in pairs:
        total += to_cents((await compute(cid, eid, hari))["ar_delivered"])
    gl = await rb.saldo_akun_sen("penjualan.piutang", [entity_id], hari)
    codes = [c for c in await known_codes("penjualan.piutang", entity_id) if c]
    explained: Dict[str, int] = {}
    if codes:
        async for je in db.journal_entries.find(
                {"entity_id": entity_id, "status": {"$ne": "void"}, "source_type": {"$in": sorted(SEBAB)},
                 "lines.account_code": {"$in": codes}, "date": {"$lte": f"{hari}T23:59:59.999999"}},
                {"_id": 0, "source_type": 1, "lines": 1}):
            net = sum(to_cents(float(ln.get("debit") or 0)) - to_cents(float(ln.get("credit") or 0))
                      for ln in je.get("lines") or [] if ln.get("account_code") in codes)
            sebab = SEBAB[je["source_type"]]
            explained[sebab] = explained.get(sebab, 0) + net
    diff = gl - total
    return {"entity_id": entity_id, "ar_delivered": from_cents(total), "gl_balance": from_cents(gl),
            "difference": from_cents(diff), "explained": {k: from_cents(v) for k, v in explained.items() if v},
            "unexplained": from_cents(diff - sum(explained.values()))}
