"""PK-19 (SL-05, SL-06, SL-08, SL-14, FX-05, FX-06, FX-07, IA-07) — SATU fungsi alokasi pembayaran pesanan.

Uang hanya bisa menempel ke `sales_orders.payments[]` lewat `allocate`, apa pun sumbernya (kwitansi, deposit, titipan
bank, saldo kredit, nota kredit, hapus sisa, kasus keuangan). `allocate` memeriksa pelanggan, PT, status pesanan, dan sisa
tagihan (`validate_targets`) lalu menulis baris dengan pembaruan bersyarat. Pembatalan TIDAK menghapus baris: `reverse`
menambah baris pembalik bertanggal (nominal negatif) dan menandai baris asal, sehingga angka periode lalu tidak berubah
mundur (`02_STANDAR.md` §1 P7, §5 D8).

Bentuk baris baru (`ENTITY_REGISTRY.md` → `sales_orders.payments[]`):

    id               "pay_" + 24 heksadesimal SHA-1 dari "kind|source_id|order_id|seq" — rujukan sama → id sama
    kind             salah satu PAYMENT_KINDS
    amount           positif untuk alokasi, negatif untuk pembalik
    receipt_id       id dokumen sumber (kwitansi, keputusan, baris mutasi, penebusan, nota kredit, kasus)
    receipt_number   nomor dokumen sumber
    method, date, created_at, plan_line_seq, gl_bucket   seperti sebelumnya (`date` = tanggal dokumen sumber; pembalik =
                     tanggal pembatalan)
    reverses         (hanya pembalik) id baris yang dibalik
    reversed_by      (pada baris asal) id pembaliknya

Baris lama tanpa `kind` dibaca lewat `payment_kind(row)` dari `method` (tanpa migrasi).

Fungsi pendamping:
  * `withdraw`        — penarikan alokasi (baris negatif BUKAN pembalik), dipakai kasus "realokasi pesanan": pembayaran
                         pindah dari pesanan asal ke pesanan tujuan, dua baris ber-sumber kasus yang sama.
  * `remove_unborn`   — kompensasi untuk dokumen sumber yang GAGAL LAHIR (kwitansi/penebusan yang tidak pernah sah):
                         barisnya dicabut. Tidak dipakai untuk membatalkan dokumen yang sah — itu `reverse`.
"""
import hashlib
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument

from core_utils import now_iso, rupiah
from db import db
from services.customer_service import (
    DEAD_STATUSES,
    NON_AR_METHODS,
    _order_grand_total as order_grand_total,
    _order_paid as order_paid,
    order_payment_method,
)

logger = logging.getLogger(__name__)

EPS = 0.01

PAYMENT_KINDS = ("kas", "deposit", "titipan_bank", "saldo_kredit", "nota_kredit", "hapus_sisa", "kasus")

#: Baris lama tanpa `kind` → jenis dari `method` (spesifikasi PK-19 §Data). `credit_note_void`, `bank_charge`, dan
#: `titipan_karyawan` lahir dari pemanggil lama yang sama dengan `credit_note` / kasus — diberi jenis sumbernya, bukan
#: `kas` (laporan PK-19, "Menyimpang dari blueprint").
_KIND_DARI_METODE = {
    "deposit": "deposit", "bank_holding": "titipan_bank", "store_credit": "saldo_kredit",
    "credit_note": "nota_kredit", "credit_note_void": "nota_kredit", "writeoff": "hapus_sisa",
    "realokasi": "kasus", "finance_case": "kasus", "bank_charge": "kasus", "titipan_karyawan": "kasus",
}

#: `method` bawaan baris baru bila pemanggil tidak menyebutnya (nama field lama dipertahankan untuk pembaca lama).
METODE_BAWAAN = {
    "kas": "transfer", "deposit": "deposit", "titipan_bank": "bank_holding", "saldo_kredit": "store_credit",
    "nota_kredit": "credit_note", "hapus_sisa": "writeoff", "kasus": "finance_case",
}

#: Field baris yang tidak boleh ditimpa isian tambahan pemanggil (`extra`).
_FIELD_INTI = frozenset({"id", "kind", "amount", "receipt_id", "receipt_number", "method", "date", "created_at",
                         "plan_line_seq", "reverses", "reversed_by"})


# ── Pembaca ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def payment_kind(row: Dict[str, Any]) -> str:
    """Jenis sumber dana satu baris `payments[]`: `kind` bila sah, selain itu diturunkan dari `method`."""
    k = (row or {}).get("kind")
    if k in PAYMENT_KINDS:
        return k
    return _KIND_DARI_METODE.get(str((row or {}).get("method") or "").strip().lower(), "kas")


def payment_id(kind: str, source_id: str, order_id: str, seq: str = "") -> str:
    """Id baris tetap dari rujukannya: rujukan yang sama selalu menghasilkan id yang sama (aman diulang)."""
    raw = f"{kind}|{source_id}|{order_id}|{seq}".encode("utf-8")
    return "pay_" + hashlib.sha1(raw).hexdigest()[:24]


def payment_status(grand_total: float, paid: float) -> str:
    if paid >= grand_total - EPS:
        return "paid"
    if paid > EPS:
        return "partial"
    return "unpaid"


def _milik(row: Dict[str, Any], source_id: str) -> bool:
    """Baris milik dokumen sumber `source_id` — `receipt_id`, atau `variance_decision_id` pada baris hapus sisa lama."""
    return bool(source_id) and (row.get("receipt_id") == source_id or row.get("variance_decision_id") == source_id)


def _nama(actor: Any) -> str:
    if isinstance(actor, dict):
        return str(actor.get("name") or "system")
    return str(actor or "system")


def _nomor(order: Dict[str, Any]) -> str:
    return str(order.get("number") or order.get("id") or "")


def _label_status(status: str) -> str:
    from services.pdf_engine import status_label   # satu kamus label status dokumen (sama dengan layar)
    return status_label(status) or status


async def _tunai_tanpa_piutang(order: Dict[str, Any]) -> bool:
    """Pesanan tunai yang tidak lewat surat jalan dijurnal Dr Kas saat dijual — tidak punya piutang untuk dilunasi
    (aturan yang sama dengan `ar_receipt_service.list_open_orders`)."""
    if order_payment_method(order) not in NON_AR_METHODS:
        return False
    sj = await db.shipments.find_one(
        {"order_id": order.get("id"), "status": {"$nin": ["cancelled", "void", "voided"]}}, {"_id": 0, "id": 1})
    return not sj


def id_pesanan(value: Any) -> str:
    """Bentuk baku id pesanan tujuan dana (spasi tepi dibuang; tanpa pengubahan huruf — id pesanan peka huruf). SATU
    penormal untuk pemeriksa alokasi, rencana alokasi keputusan selisih, dan pagar lapor bayar (LB-T4 R11)."""
    return str(value or "").strip()


# ── PERIKSA ──────────────────────────────────────────────────────────────────────────────────────────────────────────
async def validate_targets(kind: str, rows: List[Dict[str, Any]], *, customer_id: str,
                           entity_id: str) -> List[Dict[str, Any]]:
    """Periksa SEMUA pesanan tujuan tanpa menulis apa pun → dokumen pesanan (urutan kemunculan pertama).

    Menolak bila: `kind` di luar daftar; pelanggan atau PT sumber dana kosong / "all"; pesanan tidak ada; milik
    pelanggan lain (400) atau PT lain (403); status pesanan mati (409); nominal ≤ 0; Σ nominal per pesanan melebihi sisa
    tagihan (400). `saldo_kredit`: pesanan tunai tanpa piutang ditolak (perilaku penebusan saldo kredit yang ada).
    Dipanggil `allocate` dan oleh pemanggil SEBELUM efek pertamanya (`02` §1 langkah PERIKSA)."""
    if kind not in PAYMENT_KINDS:
        raise HTTPException(status_code=400, detail=f"Jenis sumber dana “{kind}” tidak dikenal.")
    if not customer_id or customer_id == "all" or not entity_id or entity_id == "all":
        raise HTTPException(status_code=400, detail=(
            "Pelanggan dan PT pemilik dana wajib jelas sebelum dana dipakai untuk melunasi pesanan."))
    per: Dict[str, float] = {}
    for r in rows or []:
        oid = id_pesanan((r or {}).get("order_id"))
        amt = round(float((r or {}).get("amount") or 0), 2)
        if not oid:
            raise HTTPException(status_code=400, detail="Pesanan tujuan wajib dipilih.")
        if amt <= EPS:
            raise HTTPException(status_code=400, detail="Nominal yang dipakai untuk melunasi pesanan harus lebih dari 0.")
        per[oid] = round(per.get(oid, 0.0) + amt, 2)
    out: List[Dict[str, Any]] = []
    for oid, total in per.items():
        o = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
        if not o:
            raise HTTPException(status_code=404, detail=f"Pesanan {oid} tidak ditemukan.")
        no = _nomor(o)
        if (o.get("customer_id") or "") != customer_id:
            raise HTTPException(status_code=400, detail=(
                f"Pesanan {no} milik pelanggan lain. Dana ini hanya bisa dipakai untuk pesanan pelanggan yang sama."))
        if (o.get("entity_id") or "") != entity_id:
            raise HTTPException(status_code=403, detail=(
                f"Pesanan {no} milik PT lain. Piutangnya tidak bisa dilunasi dari dana PT ini."))
        if o.get("status") in DEAD_STATUSES:
            raise HTTPException(status_code=409, detail=(
                f"Pesanan {no} berstatus {_label_status(o.get('status'))}, jadi tidak bisa menerima pembayaran."))
        if kind == "saldo_kredit" and await _tunai_tanpa_piutang(o):
            raise HTTPException(status_code=400, detail=f"Pesanan {no} bukan penjualan kredit (tanpa piutang).")
        sisa = round(order_grand_total(o) - order_paid(o), 2)
        if total > sisa + EPS:
            raise HTTPException(status_code=400, detail=(
                f"Alokasi {rupiah(total)} melebihi sisa tagihan pesanan {no} ({rupiah(max(sisa, 0.0))})."))
        out.append(o)
    return out


# ── EFEK ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _segarkan(order_id: str, order: Optional[Dict[str, Any]] = None) -> str:
    """`payment_status` dari Σ baris + rencana bayar dihitung ulang (turunan; galat rencana tidak menggagalkan)."""
    o = order or await db.sales_orders.find_one({"id": order_id}, {"_id": 0}) or {}
    status = payment_status(order_grand_total(o), round(order_paid(o), 2))
    if o and o.get("payment_status") != status:
        await db.sales_orders.update_one({"id": order_id}, {"$set": {"payment_status": status,
                                                                     "updated_at": now_iso()}})
    try:
        from services import payment_plan_service as _plans
        await _plans.recompute_for_doc("sales_order", order_id)
    except Exception as exc:  # noqa: BLE001 — jadwal bayar turunan dari payments[]
        logger.warning("[ar_allocation] rencana bayar %s gagal dihitung ulang: %s", order_id, exc)  # KN-C10
    # CR-T2 — sesudah langkah efek: saldo piutang tersimpan pasangan (pelanggan, PT) dihitung ulang penuh (turunan)
    from services import customer_balance_service as _cbs
    await _cbs.refresh_safe(o.get("customer_id") or "", o.get("entity_id") or "")
    return status


def _hasil(order: Dict[str, Any], row: Dict[str, Any], *, replayed: bool) -> Dict[str, Any]:
    gt = order_grand_total(order)
    paid = round(order_paid(order), 2)
    return {"order_id": order.get("id"), "order_number": _nomor(order), "applied": round(float(row["amount"]), 2),
            "outstanding_after": round(gt - paid, 2), "payment_status": payment_status(gt, paid),
            "entity_id": order.get("entity_id", ""), "plan_line_seq": int(row.get("plan_line_seq") or 0),
            "payment_id": row["id"], "kind": payment_kind(row), "replayed": replayed}


def _baris(order: Dict[str, Any], row_id: str) -> Optional[Dict[str, Any]]:
    return next((p for p in order.get("payments") or [] if p.get("id") == row_id), None)


async def allocate(*, kind: str, order_id: str, amount: float, source_id: str, source_number: str, customer_id: str,
                   entity_id: str, date: str, actor: Any, method: str = "", plan_line_seq: int = 0, seq: str = "",
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tempelkan `amount` dari dokumen sumber `source_id` ke pesanan `order_id`.

    Urutan: baris ber-id sama sudah ada → dikembalikan apa adanya (aman diulang) → `validate_targets` → pembaruan
    bersyarat (`Σ payments + amount ≤ grand_total` DAN belum ada baris ber-id itu) yang menambah baris + `paid_total`
    → `payment_status` → rencana bayar. Kalah balapan → 409. `extra` = field tambahan baris (tidak bisa menimpa field
    inti)."""
    amt = round(float(amount or 0), 2)
    if not source_id:
        raise HTTPException(status_code=400, detail="Dokumen sumber dana wajib disebut.")
    pid = payment_id(kind, source_id, order_id, seq)
    ada = await db.sales_orders.find_one({"id": order_id, "payments.id": pid}, {"_id": 0})
    if ada:
        return _hasil(ada, _baris(ada, pid), replayed=True)
    [o] = await validate_targets(kind, [{"order_id": order_id, "amount": amt}],
                                 customer_id=customer_id, entity_id=entity_id)
    gt = order_grand_total(o)
    tgl = date or now_iso()
    row: Dict[str, Any] = {k: v for k, v in (extra or {}).items() if k not in _FIELD_INTI}
    row.update({"id": pid, "kind": kind, "amount": amt, "receipt_id": source_id,
                "receipt_number": source_number or source_id, "method": method or METODE_BAWAAN[kind],
                "date": tgl, "created_at": tgl, "created_by": _nama(actor)})
    if int(plan_line_seq or 0) > 0:   # FASE G-3 — pembayaran boleh MENYEBUT baris jadwal tujuan
        row["plan_line_seq"] = int(plan_line_seq)
    # INV-CONC-01 — $push ATOMIK + syarat $expr (Σ payments + amount ≤ grand_total) + id belum ada: K permintaan paralel
    # untuk satu sisa tagihan → hanya yang muat yang lolos; id yang sama tidak pernah tertulis dua kali.
    updated = await db.sales_orders.find_one_and_update(
        {"id": order_id, "payments.id": {"$ne": pid},
         "$expr": {"$lte": [{"$add": [{"$sum": "$payments.amount"}, amt]}, gt + EPS]}},
        {"$push": {"payments": row}, "$inc": {"paid_total": amt}, "$set": {"updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        lain = await db.sales_orders.find_one({"id": order_id, "payments.id": pid}, {"_id": 0})
        if lain:   # permintaan kembar bersamaan menulis baris yang sama lebih dulu
            return _hasil(lain, _baris(lain, pid), replayed=True)
        raise HTTPException(status_code=409, detail=(
            f"Alokasi ke pesanan {_nomor(o)} gagal karena sisa tagihannya baru berubah. Muat ulang lalu coba lagi."))
    await _segarkan(order_id, updated)
    return _hasil(updated, row, replayed=False)


async def withdraw(*, kind: str, order_id: str, amount: float, source_id: str, source_number: str, customer_id: str,
                   entity_id: str, date: str, actor: Any, method: str = "", seq: str = "",
                   note: str = "", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tarik `amount` yang sudah terbayar dari pesanan `order_id` lewat baris NEGATIF ber-sumber `source_id` (bukan
    pembalik baris tertentu). Dipakai kasus "realokasi pesanan" (pembayaran dipindah ke pesanan lain pelanggan yang
    sama) dan pesanan batal yang uang mukanya dipindah ke titipan (S3). Syarat bersyarat `Σ payments − amount ≥ 0`;
    id tetap → aman diulang. `extra` = field tambahan baris (tidak bisa menimpa field inti), mis. `gl_bucket`."""
    amt = round(float(amount or 0), 2)
    if amt <= EPS:
        raise HTTPException(status_code=400, detail="Nominal penarikan harus lebih dari 0.")
    if kind not in PAYMENT_KINDS:
        raise HTTPException(status_code=400, detail=f"Jenis sumber dana “{kind}” tidak dikenal.")
    pid = payment_id(kind, source_id, order_id, f"tarik:{seq}")
    ada = await db.sales_orders.find_one({"id": order_id, "payments.id": pid}, {"_id": 0})
    if ada:
        return {**_hasil(ada, _baris(ada, pid), replayed=True), "withdrawn": amt}
    o = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail=f"Pesanan {order_id} tidak ditemukan.")
    no = _nomor(o)
    if (o.get("customer_id") or "") != customer_id:
        raise HTTPException(status_code=400, detail=(
            f"Pesanan {no} milik pelanggan lain. Dana ini hanya bisa dipakai untuk pesanan pelanggan yang sama."))
    if (o.get("entity_id") or "") != entity_id:
        raise HTTPException(status_code=403, detail=(
            f"Pesanan {no} milik PT lain. Piutangnya tidak bisa dilunasi dari dana PT ini."))
    paid = round(order_paid(o), 2)
    if amt > paid + EPS:
        raise HTTPException(status_code=400, detail=(
            f"Penarikan {rupiah(amt)} melebihi yang sudah dibayar di pesanan {no} ({rupiah(paid)})."))
    tgl = date or now_iso()
    row: Dict[str, Any] = {k: v for k, v in (extra or {}).items() if k not in _FIELD_INTI}
    row.update({"id": pid, "kind": kind, "amount": -amt, "receipt_id": source_id,
                "receipt_number": source_number or source_id, "method": method or METODE_BAWAAN[kind],
                "date": tgl, "created_at": tgl, "created_by": _nama(actor), "withdrawal": True})
    if note:
        row["note"] = note
    updated = await db.sales_orders.find_one_and_update(
        {"id": order_id, "payments.id": {"$ne": pid},
         "$expr": {"$gte": [{"$add": [{"$sum": "$payments.amount"}, -amt]}, -EPS]}},
        {"$push": {"payments": row}, "$inc": {"paid_total": -amt}, "$set": {"updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(status_code=409, detail=(
            f"Penarikan alokasi pesanan {no} gagal karena nilai terbayarnya baru berubah. Muat ulang lalu coba lagi."))
    await _segarkan(order_id, updated)
    return {**_hasil(updated, row, replayed=False), "withdrawn": amt}


def _sisa_pembalik(order: Dict[str, Any], source_id: str) -> tuple:
    """(baris positif `source_id` yang belum dibalik, Σ terbayar sesudah semuanya dibalik)."""
    asal = [p for p in order.get("payments") or []
            if _milik(p, source_id) and float(p.get("amount") or 0) > EPS
            and not p.get("reverses") and not p.get("reversed_by") and p.get("id")]
    return asal, round(order_paid(order) - sum(float(p["amount"]) for p in asal), 2)


async def reverse_check(source_id: str, order_ids: Optional[List[str]] = None) -> None:
    """PERIKSA tanpa tulisan sebelum `reverse` (dipanggil di langkah PERIKSA pembatalan): membalik semua baris
    `source_id` tidak boleh membuat terbayar pesanan mana pun negatif (pembayarannya sudah dipindah lewat dokumen lain
    — mis. kasus realokasi) → 409 dengan pesan yang sama dengan `reverse`."""
    if not source_id:
        return
    flt: Dict[str, Any] = {"$or": [{"payments.receipt_id": source_id}, {"payments.variance_decision_id": source_id}]}
    if order_ids is not None:
        flt["id"] = {"$in": list(order_ids)}
    async for o in db.sales_orders.find(flt, {"_id": 0}):
        asal, sesudah = _sisa_pembalik(o, source_id)
        if asal and sesudah < -EPS:
            raise HTTPException(status_code=409, detail=(
                f"Pembayaran {asal[0].get('receipt_number') or source_id} pada pesanan {_nomor(o)} sudah dipindahkan "
                "lewat dokumen lain. Batalkan pemindahan itu dulu."))


async def reverse(*, source_id: str, date: str, actor: Any, reason: str, order_id: str = "") -> List[Dict[str, Any]]:
    """Balik semua baris POSITIF milik `source_id` yang belum dibalik (opsional: hanya di pesanan `order_id`).

    Tiap baris: tambah pembalik ber-id tetap (`payment_id(jenis, sumber, pesanan, "balik:<id baris>")`, nominal
    negatif, `reverses`, tanggal `date`) dengan syarat `Σ payments − amount ≥ 0` dan id pembalik belum ada, lalu tandai
    baris asal `reversed_by`. Baris yang sudah dibalik dilewati; pembalik yang sudah tertulis tetapi baris asalnya
    belum bertanda (proses terhenti) hanya ditandai. Terbayar akan negatif (pembayaran sudah dipindah lewat dokumen
    lain) → 409 tanpa menulis baris itu."""
    if not source_id:
        return []
    tgl = date or now_iso()
    flt: Dict[str, Any] = {"$or": [{"payments.receipt_id": source_id}, {"payments.variance_decision_id": source_id}]}
    if order_id:
        flt["id"] = order_id
    out: List[Dict[str, Any]] = []
    ids = [d["id"] async for d in db.sales_orders.find(flt, {"_id": 0, "id": 1})]
    for oid in ids:
        o = await db.sales_orders.find_one({"id": oid}, {"_id": 0}) or {"id": oid}
        dibalik: List[str] = []
        total = 0.0
        asal, _ = _sisa_pembalik(o, source_id)
        for p in asal:
            amt = round(float(p.get("amount") or 0), 2)
            rev_id = payment_id(payment_kind(p), source_id, oid, f"balik:{p['id']}")
            rev = {"id": rev_id, "kind": payment_kind(p), "amount": -amt, "receipt_id": source_id,
                   "receipt_number": p.get("receipt_number") or source_id, "method": p.get("method") or "",
                   "date": tgl, "created_at": tgl, "reverses": p["id"], "reason": (reason or "").strip(),
                   "created_by": _nama(actor)}
            for k in ("plan_line_seq", "gl_bucket"):
                if p.get(k) not in (None, ""):
                    rev[k] = p[k]
            for _coba in range(5):
                cur = await db.sales_orders.find_one({"id": oid}, {"_id": 0}) or {}
                if _baris(cur, rev_id) is None:
                    asal_kini = _baris(cur, p["id"]) or {}
                    if asal_kini.get("reversed_by"):
                        break   # dibalik permintaan lain di antara baca dan tulis
                    res = await db.sales_orders.update_one(
                        {"id": oid, "payments.id": {"$ne": rev_id},
                         "payments": {"$elemMatch": {"id": p["id"], "reversed_by": {"$exists": False}}},
                         "$expr": {"$gte": [{"$add": [{"$sum": "$payments.amount"}, -amt]}, -EPS]}},
                        {"$push": {"payments": rev}, "$inc": {"paid_total": -amt}, "$set": {"updated_at": now_iso()}})
                    if not res.modified_count:
                        cur = await db.sales_orders.find_one({"id": oid}, {"_id": 0}) or {}
                        if _baris(cur, rev_id) is None and not (_baris(cur, p["id"]) or {}).get("reversed_by") \
                                and round(order_paid(cur) - amt, 2) < -EPS:
                            raise HTTPException(status_code=409, detail=(
                                f"Pembayaran {p.get('receipt_number') or source_id} pada pesanan {_nomor(cur or o)} "
                                "sudah dipindahkan lewat dokumen lain. Batalkan pemindahan itu dulu."))
                        continue
                    dibalik.append(rev_id)
                    total = round(total + amt, 2)
                await db.sales_orders.update_one({"id": oid, "payments.id": p["id"]},
                                                 {"$set": {"payments.$.reversed_by": rev_id}})
                break
            else:
                raise HTTPException(status_code=409, detail=(
                    f"Pesanan {_nomor(o)} terus berubah bersamaan. Muat ulang lalu coba batalkan lagi."))
        fresh = await db.sales_orders.find_one({"id": oid}, {"_id": 0}) or o
        status = await _segarkan(oid, fresh)
        out.append({"order_id": oid, "order_number": _nomor(fresh), "entity_id": fresh.get("entity_id", ""),
                    "reversed": total, "rows": dibalik, "payment_status": status,
                    "outstanding_after": round(order_grand_total(fresh) - order_paid(fresh), 2)})
    return out


async def remove_unborn(source_id: str) -> List[str]:
    """Kompensasi dokumen sumber yang GAGAL LAHIR (tidak pernah sah, mis. kwitansi yang efeknya terhenti sebelum
    tuntas): semua barisnya dicabut dari pesanan dengan tulis-ulang bersyarat (larik belum berubah sejak dibaca).
    → id pesanan yang disentuh. Untuk dokumen yang SAH gunakan `reverse`."""
    touched: List[str] = []
    if not source_id:
        return touched
    async for o in db.sales_orders.find({"payments.receipt_id": source_id}, {"_id": 0}):
        for _coba in range(10):
            payments = [p for p in (o.get("payments") or []) if p.get("receipt_id") != source_id]
            paid = round(sum(float(p.get("amount", 0) or 0) for p in payments), 2)
            res = await db.sales_orders.update_one(
                {"id": o["id"], "payments": o.get("payments") or []},
                {"$set": {"payments": payments, "paid_total": paid,
                          "payment_status": payment_status(order_grand_total(o), paid), "updated_at": now_iso()}})
            if res.matched_count:
                touched.append(o["id"])
                break
            o = await db.sales_orders.find_one({"id": o["id"]}, {"_id": 0}) or o
        try:
            from services import payment_plan_service as _plans
            await _plans.recompute_for_doc("sales_order", o["id"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ar_allocation] rencana bayar %s gagal dihitung ulang: %s", o["id"], exc)  # KN-C10
        from services import customer_balance_service as _cbs   # CR-T2 — saldo tersimpan (turunan)
        await _cbs.refresh_safe(o.get("customer_id") or "", o.get("entity_id") or "")
    return touched
