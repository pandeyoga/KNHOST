"""FASE G-3 — **SELISIH PEMBAYARAN: LEBIH & KURANG BAYAR** (`payment_variance_decisions`).

MASALAH NYATA PEMILIK
---------------------
Uang yang masuk hampir **tidak pernah** sama persis dengan tagihan: pelanggan memotong
biaya transfer, membulatkan ke bawah, membayar sebagian karena arus kas, atau justru
mengirim lebih. Sistem lama hanya punya dua sikap ekstrem: menolak (karena "melebihi
outstanding") atau diam-diam menaruh kelebihan ke deposit. Akibatnya:

  * sisa kurang bayar receh menggantung bertahun-tahun di laporan piutang;
  * kelebihan bayar hilang dari pembicaraan (pelanggan merasa sudah bayar, kami merasa belum);
  * keputusan "ya sudah, anggap lunas" terjadi di WhatsApp, tidak di sistem.

TEROBOSAN DESAIN — "KEBIJAKAN SELISIH PEMBAYARAN"
------------------------------------------------
Sistem **tidak menuntut nominal persis**, tetapi setiap selisih **wajib punya label
keputusan** dengan pemutus yang jelas:

    delta = uang masuk − Σ tagihan yang JATUH TEMPO pada pesanan tujuan

| Kondisi                   | Perlakuan                                                        |
|---------------------------|------------------------------------------------------------------|
| `abs(delta) <= toleransi` | **otomatis** (`rounding`) → sisa receh dihapus / kelebihan receh  |
|                           | jadi deposit. Tanpa persetujuan, TAPI tetap jadi keputusan        |
|                           | berlabel yang bisa diaudit.                                       |
| `delta < 0` (kurang)      | (a) sisa tetap **piutang** *(bawaan)* · (b) **ubah jadwal** —     |
|                           | sisa jadi tempo baru · (c) **hapus sisa** + alasan + wewenang     |
| `delta > 0` (lebih)       | (a) **deposit pelanggan** *(bawaan)* · (b) **alokasi ke pesanan   |
|                           | terbuka lain** · (c) **kembalikan** (kas keluar)                  |

KEJUJURAN AKUNTANSI (kenapa keputusan = dokumen sendiri)
--------------------------------------------------------
Kwitansi tetap dibukukan seperti biasa (Dr Kas · Cr Piutang sebesar yang teralokasi ·
Cr 2-1400 Uang Muka Pelanggan sebesar kelebihannya). Keputusan selisih **tidak mengubah
jurnal kwitansi** (ledger append-only, aturan repo #7) melainkan menerbitkan jurnalnya
sendiri:

  * hapus sisa kurang bayar  → Dr 6-9100 Beban Selisih Pembayaran / Cr 1-1200 Piutang
  * kelebihan dipakai untuk pesanan lain → Dr 2-1400 Uang Muka / Cr 1-1200 Piutang
  * kelebihan dikembalikan   → Dr 2-1400 Uang Muka / Cr Kas (lewat `cash_transactions`)

Karena itu keputusan bisa diambil **saat kwitansi dibuat** maupun **belakangan** dari
antrean "Selisih Bayar" tanpa pernah menghasilkan pembukuan ganda.

JALUR AP (bayar ke supplier)
----------------------------
Pola yang sama dipakai saat KITA membayar tagihan supplier: kurang bayar → sisa tetap
hutang / ditutup (potongan supplier, Dr 2-1100 · Cr 4-9000), lebih bayar → **uang muka
supplier** (Dr 1-1400 · Cr Kas) yang bisa dipotongkan pada kontrabon berikutnya (G-7).

INVARIAN
--------
* **INV-VAR-01** Setiap selisih di luar toleransi punya keputusan **berlabel** (kode alasan
  + pemutus). Penghapusan sisa & pengembalian dana wajib peran penyetuju & di bawah batas.
* **INV-VAR-02** Uang tidak hilang: pada setiap kwitansi `dana = teralokasi + belum
  teralokasi`, dan setiap rupiah yang dipindahkan oleh keputusan (alokasi ulang / refund)
  punya jurnal + tidak melebihi kelebihan bayar kwitansinya.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import DEFAULT_ENTITY_ID, new_id, next_doc_number, now_iso, safe_doc, rupiah
from db import db
from services import gl_service
from services import payment_plan_service as plans
from services.book_date import tanggal_buku
from services.config_resolver import resolve
logger = logging.getLogger(__name__)


COLL = "payment_variance_decisions"
EPS = 0.01

# Arah selisih
DIR_NONE, DIR_ROUNDING, DIR_UNDER, DIR_OVER = "none", "rounding", "under", "over"

AR_UNDER_KINDS = ("outstanding", "reschedule", "writeoff")
AR_OVER_KINDS = ("deposit", "allocate", "refund")
AP_KINDS = ("ap_outstanding", "ap_writeoff", "ap_advance")
ROUNDING_KINDS = ("rounding_writeoff", "rounding_deposit",
                  "ap_rounding_writeoff", "ap_rounding_advance")
ALL_KINDS = AR_UNDER_KINDS + AR_OVER_KINDS + AP_KINDS + ROUNDING_KINDS

KIND_LABEL = {
    "outstanding": "Sisa tetap jadi piutang",
    "reschedule": "Ubah jadwal — sisa jadi tempo baru",
    "writeoff": "Hapus sisa kurang bayar",
    "deposit": "Simpan sebagai deposit pelanggan",
    "allocate": "Alokasikan ke pesanan terbuka lain",
    "refund": "Kembalikan ke pelanggan (kas keluar)",
    "rounding_writeoff": "Pembulatan — sisa receh dihapus otomatis",
    "rounding_deposit": "Pembulatan — kelebihan receh jadi deposit",
    "ap_outstanding": "Sisa tetap jadi hutang supplier",
    "ap_writeoff": "Tutup sisa hutang (potongan supplier)",
    "ap_advance": "Kelebihan jadi uang muka supplier",
    "ap_rounding_writeoff": "Pembulatan — sisa hutang receh ditutup",
    "ap_rounding_advance": "Pembulatan — kelebihan receh jadi uang muka",
}
REASON_DOC_TYPE = "payment_variance"     # `amendment_reasons.applies_to` (taksonomi G-1)
SENSITIVE_KINDS = ("writeoff", "refund", "ap_writeoff")


async def _periksa_periode(entity_id: str) -> None:
    """PK-37 (K-03) — PERIKSA periode buku hari ini untuk keputusan berjurnal; tertutup → `VarianceError` berpesan sama
    (dipanggil sesudah uang masuk/keluar di jalur kwitansi & bayar tagihan: keputusan menunggu di antrean)."""
    from services import gl_service as _gl
    from services.book_date import periksa_periode_dokumen
    try:
        await periksa_periode_dokumen(entity_id, None, jenis="keputusan selisih bayar")
    except _gl.ClosedPeriodError as exc:
        raise VarianceError(str(exc)) from exc


class VarianceError(ValueError):
    """Kesalahan selisih pembayaran dengan pesan siap tampil (Bahasa Indonesia). `status_code` = kode jawaban router."""
    status_code = 400


class VarianceForbidden(VarianceError):
    """PK-38 — keputusan ditolak karena wewenang (dua orang); router menjawab 403. Turunan `VarianceError` supaya
    keputusan saat kwitansi dibuat tetap tidak membatalkan uang yang sudah masuk (`ar_receipt_service`)."""
    status_code = 403


class VarianceConflict(VarianceError):
    """PK-19 — keputusan kalah klaim / sedang atau sudah diputus / keadaan berubah; router menjawab 409."""
    status_code = 409


# ── Kebijakan (registry FASE G-0 — tidak ada angka hardcode) ───────────────
async def variance_policy(entity_id: str = "", customer_id: str = "") -> Dict[str, Any]:
    ctx = {"entity_id": entity_id or "", "customer_id": customer_id or ""}

    async def val(key: str) -> Any:
        return (await resolve(key, ctx))["value"]

    # KP-T4 — peran penyetuju hapus sisa (nilai kompatibel untuk tampilan pilihan) dari Aturan Persetujuan.
    from services import approval_policy_service as _aps
    _rows = (await _aps.rows_for("payment_variance.hapus_sisa", entity_id or None))["rows"]
    _first = next((r for r in _rows if r.get("roles") or r.get("any_holder")), None)
    return {
        "tolerance": float(await val("payment.variance_tolerance_rupiah") or 0),
        "underpay_default": str(await val("payment.variance_underpay_default") or "outstanding"),
        "overpay_default": str(await val("payment.variance_overpay_default") or "deposit"),
        "writeoff_requires_approval": bool(await val("payment.variance_writeoff_requires_approval")),
        "writeoff_approver_role": (_aps.compat_role(_first) if _first else "") or "manager",
        "writeoff_max_amount": float(await val("payment.variance_writeoff_max_amount") or 0),
        # PK-38 — batas pengurang piutang tanpa uang masuk (hapus sisa): di atasnya harus orang kedua.
        "ar_reduction_limit": await _ar_reduction_limit(entity_id),
        "reschedule_days": int(await val("payment.variance_reschedule_days") or 14),
        "refund_method": str(await val("payment.variance_refund_method") or "transfer"),
        "ap_tolerance": float(await val("payment.variance_ap_tolerance_rupiah") or 0),
    }


async def _ar_reduction_limit(entity_id: str) -> float:
    from services import ar_reduction_guard as _arg   # PK-38
    return await _arg.batas(entity_id or "")


# ── Label alasan (taksonomi FASE G-1, bisa ditambah admin) ─────────────────
async def reasons() -> List[Dict[str, Any]]:
    from services.amendment_service import ensure_reasons
    await ensure_reasons()
    rows = await db.amendment_reasons.find(
        {"applies_to": REASON_DOC_TYPE, "status": {"$ne": "inactive"}}, {"_id": 0}
    ).sort("label", 1).to_list(100)
    return [safe_doc(r) for r in rows]


async def _reason_or_fail(reason_code: str) -> Dict[str, Any]:
    code = (reason_code or "").strip()
    if not code:
        raise VarianceError(
            "Label alasan wajib dipilih — setiap selisih pembayaran harus punya sebab "
            "yang bisa dibaca orang lain.")
    from services.amendment_service import ensure_reasons
    await ensure_reasons()
    row = await db.amendment_reasons.find_one({"code": code}, {"_id": 0})
    if not row or row.get("status") not in (None, "active"):
        raise VarianceError(f"Label alasan '{code}' tidak terdaftar / sudah tidak aktif.")
    applies = row.get("applies_to") or []
    if applies and REASON_DOC_TYPE not in applies:
        raise VarianceError(
            f"Label alasan '{row.get('label')}' tidak berlaku untuk selisih pembayaran.")
    return safe_doc(row)


def _rp(v: Any) -> str:
    """Alias tipis ke `core_utils.rupiah` — satu sumber format uang untuk seluruh backend."""
    return rupiah(v)


def classify(delta: float, tolerance: float) -> str:
    d = round(float(delta or 0), 2)
    tol = round(float(tolerance or 0), 2)
    if abs(d) <= EPS:
        return DIR_NONE
    if abs(d) <= tol + EPS:
        return DIR_ROUNDING
    return DIR_UNDER if d < 0 else DIR_OVER


# ── Sisi AR: apa yang "seharusnya dibayar sekarang" ────────────────────────
def _hari_buku(as_of: Any = "") -> str:
    """Tanggal buku WIB untuk "jatuh tempo per hari ini". Dulu `now_iso()[:10]` = tanggal UTC: pukul 00.00–07.00 WIB
    jadwal tagihan (tanggal buku WIB) sudah hari berikutnya sehingga baris uang muka yang jatuh tempo hari ini dinilai
    "belum jatuh tempo" dan membayar tepat uang muka dinilai kurang bayar (temuan uji S3-L3, 18 Nov 00.37 WIB)."""
    try:
        return tanggal_buku(as_of or None)
    except ValueError:
        return str(as_of)[:10]


async def tagihan_uang_muka(order: Dict[str, Any], as_of: str = "",
                            customer: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """S3 (pelatihan 18 Nov) — pesanan bertermin ber-DP (`payment_terms.dp_percent` > 0) tanpa rencana manual: yang
    jatuh tempo SEKARANG dibaca dari JADWAL TAGIHAN (`billing_schedule_service.lines_for_orders`, pembaca yang sama dengan
    Penagihan & Umur Piutang) — baris uang muka jatuh tempo saat pesanan dikonfirmasi ("sebelum kirim"), baris surat
    jalan menurut termin. Dulu jatuh tempo dihitung dari tanggal pesanan + hari termin: belum jatuh tempo → harapan =
    seluruh sisa pesanan, sehingga membayar TEPAT uang muka dinilai "Kurang bayar" dan wajib diputus.
    → `{due_now, due_lines, next_due_date}`, atau None (bukan termin DP / tidak ada baris yang jatuh tempo → aturan lama)."""
    oid = order.get("id") or ""
    if not oid or not (order.get("payment_term_code") or order.get("payment_term")):
        return None
    from services import billing_schedule_service as bss
    full = await db.sales_orders.find_one({"id": oid}, {"_id": 0}) or {}
    if not full:
        return None
    if customer is None:
        customer = await db.customers.find_one({"id": full.get("customer_id")}, {"_id": 0, "payment_profile": 1}) or {}
    if float((await bss.termin_pesanan(full, customer)).get("dp_percent") or 0) <= 0:
        return None
    day = _hari_buku(as_of)
    rows = ((await bss.lines_for_orders([full], {full.get("customer_id") or "": customer}, per=day)).get(oid)
            or {}).get("rows") or []
    due = [r for r in rows if r.get("due_date") and str(r["due_date"]) <= day and float(r.get("outstanding") or 0) > EPS]
    if not due:
        return None
    nxt = sorted(str(r["due_date"]) for r in rows if r.get("due_date") and str(r["due_date"]) > day)
    return {"due_now": round(sum(float(r["outstanding"]) for r in due), 2),
            "due_lines": [{"seq": r.get("seq"), "label": r.get("label"), "due_date": r.get("due_date"),
                           "amount": r.get("amount"), "paid_amount": r.get("paid_amount"),
                           "remaining": r.get("outstanding")} for r in due],
            "next_due_date": nxt[0] if nxt else ""}


async def _order_due_now(order: Dict[str, Any], outstanding: float,
                         as_of: str) -> Dict[str, Any]:
    """Berapa yang jatuh tempo untuk satu pesanan + dari mana angkanya.

    Ada rencana pembayaran (FASE G-2) → Σ baris yang sudah jatuh tempo.
    Tidak ada rencana → pakai jatuh tempo term pesanan; kalau belum jatuh tempo,
    harapannya adalah seluruh sisa tagihan pesanan itu (yang lazim ditagih).
    """
    plan = await plans.get_manual("sales_order", order.get("id", ""))   # CR-T2 — rencana orang, bukan jadwal mesin
    if plan:
        due_now = plans.due_now_amount(plan, as_of)
        rows = plans.due_lines(plan, as_of)
        return {
            "plan_id": plan["id"], "plan_number": plan.get("number", ""),
            "due_now": min(round(due_now, 2), outstanding),
            "basis": "plan" if due_now > EPS else "plan_not_due",
            "due_lines": [{"seq": l.get("seq"), "label": l.get("label"),
                           "due_date": l.get("due_date"),
                           "amount": round(float(l.get("amount") or 0), 2),
                           "paid_amount": round(float(l.get("paid_amount") or 0), 2),
                           "remaining": round(float(l.get("amount") or 0)
                                              - float(l.get("paid_amount") or 0), 2)}
                          for l in rows],
            "next_due_date": (plans.next_due(plan) or {}).get("due_date", ""),
        }
    from services.customer_service import _parse_dt as parse_dt
    from services.report_basis import hari_termin as term_days   # CR-T2 — aturan hari termin pindah (D8)
    cust = await db.customers.find_one({"id": order.get("customer_id")},
                                       {"_id": 0, "payment_profile": 1}) or {}
    um = await tagihan_uang_muka(order, as_of, cust)
    if um:
        return {"plan_id": "", "plan_number": "", "due_now": min(um["due_now"], outstanding), "basis": "uang_muka",
                "due_lines": um["due_lines"], "next_due_date": um["next_due_date"]}
    created = parse_dt(order.get("created_at")) or datetime.now(timezone.utc)
    due = (date.fromisoformat(tanggal_buku(created)) + timedelta(days=term_days(cust, order))).isoformat()
    day = _hari_buku(as_of)
    is_due = due <= day
    return {"plan_id": "", "plan_number": "",
            "due_now": outstanding if is_due else 0.0,
            "basis": "term" if is_due else "term_not_due",
            "due_lines": [], "next_due_date": due}


async def _targets(customer_id: str, allocations: Optional[List[Dict[str, Any]]],
                   as_of: str) -> Dict[str, Any]:
    """Pesanan tujuan pembayaran + pesanan terbuka lainnya (untuk pilihan alokasi)."""
    from services import ar_receipt_service as ars
    opens = await ars.list_open_orders(customer_id)
    idx = {o["order_id"]: o for o in opens}
    if allocations:
        wanted = [str(a.get("order_id") or "") for a in allocations if a.get("order_id")]
    else:
        wanted = [o["order_id"] for o in opens]

    rows: List[Dict[str, Any]] = []
    for oid in wanted:
        base = idx.get(oid)
        if not base:
            continue
        order = await db.sales_orders.find_one(
            {"id": oid}, {"_id": 0, "id": 1, "number": 1, "customer_id": 1,
                          "created_at": 1, "payment_term_code": 1, "payment_term_days": 1,
                          "entity_id": 1}) or {}
        info = await _order_due_now(order, base["outstanding"], as_of)
        expected = round(info["due_now"] if info["due_now"] > EPS else base["outstanding"], 2)
        rows.append({
            "order_id": oid, "number": base.get("number", oid),
            "entity_id": order.get("entity_id", ""),
            "outstanding": base["outstanding"], "expected": expected, **info,
        })
    others = [{"order_id": o["order_id"], "number": o.get("number", o["order_id"]),
               "outstanding": o["outstanding"]}
              for o in opens if o["order_id"] not in {r["order_id"] for r in rows}]
    return {"targets": rows, "others": others}


def _options(direction: str, delta: float, policy: Dict[str, Any],
             ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pilihan keputusan dalam bahasa manusia + dampak masing-masing (untuk dialog)."""
    gap = round(abs(delta), 2)
    out: List[Dict[str, Any]] = []
    if direction == DIR_UNDER:
        has_plan = bool(ctx.get("has_plan"))
        new_due = ctx.get("suggested_due_date", "")
        try:   # G1-15 — tanggal di kalimat bantuan berformat Indonesia ("8 Nov 2026"), bukan ISO
            from services.analytics_time import fmt_id
            new_due = fmt_id(date.fromisoformat(str(new_due)[:10])) if new_due else new_due
        except ValueError:
            pass
        out = [
            {"value": "outstanding", "label": KIND_LABEL["outstanding"],
             "help": f"Sisa {_rp(gap)} tetap ditagih seperti biasa — jadwal tidak berubah.",
             "impact": f"Piutang tetap {_rp(gap)}; pesanan belum lunas.",
             "available": True, "requires_reason": True, "requires_role": ""},
            {"value": "reschedule", "label": KIND_LABEL["reschedule"],
             "help": (f"Sisa {_rp(gap)} dijadwalkan ulang ke {new_due} sehingga tidak "
                      "tercatat sebagai tunggakan telat."),
             "impact": f"Baris jadwal dipecah / digeser; Σ rencana tetap {_rp(ctx.get('plan_total', 0))}.",
             "available": has_plan,
             "unavailable_reason": "" if has_plan else
                 "Pesanan ini belum punya rencana pembayaran — susun jadwal dulu.",
             "requires_reason": True, "requires_role": ""},
            {"value": "writeoff", "label": KIND_LABEL["writeoff"],
             "help": (f"Sisa {_rp(gap)} dihapus dari piutang dan dibebankan ke "
                      "Beban Selisih Pembayaran — pesanan langsung lunas."),
             "impact": f"Piutang −{_rp(gap)} · beban naik {_rp(gap)} (berjurnal, tak bisa dihapus).",
             "available": True, "requires_reason": True,
             "requires_role": policy["writeoff_approver_role"] if policy["writeoff_requires_approval"] else "",
             # PK-38 — angka dari server: di atas batas ini keputusan harus oleh orang selain pembuat kwitansi.
             "max_amount": policy.get("ar_reduction_limit", policy["writeoff_max_amount"]),
             "needs_second_person_above": policy.get("ar_reduction_limit", policy["writeoff_max_amount"])},
        ]
    elif direction == DIR_OVER:
        others_total = round(float(ctx.get("others_total", 0)), 2)
        out = [
            {"value": "deposit", "label": KIND_LABEL["deposit"],
             "help": f"Kelebihan {_rp(gap)} disimpan sebagai saldo pelanggan untuk tagihan berikutnya.",
             "impact": f"Deposit pelanggan +{_rp(gap)} (kewajiban kami ke pelanggan).",
             "available": True, "requires_reason": True, "requires_role": ""},
            {"value": "allocate", "label": KIND_LABEL["allocate"],
             "help": (f"Kelebihan {_rp(gap)} dipakai melunasi pesanan terbuka lain "
                      f"(tersedia {_rp(others_total)})."),
             "impact": "Pesanan lain berkurang piutangnya; deposit tidak menumpuk.",
             "available": others_total > EPS,
             "unavailable_reason": "" if others_total > EPS else
                 "Tidak ada pesanan terbuka lain untuk dialokasikan.",
             "requires_reason": True, "requires_role": ""},
            {"value": "refund", "label": KIND_LABEL["refund"],
             "help": f"Kelebihan {_rp(gap)} dikembalikan ke pelanggan lewat kas keluar.",
             "impact": f"Kas berkurang {_rp(gap)} · deposit tidak bertambah.",
             "available": True, "requires_reason": True,
             "requires_role": policy["writeoff_approver_role"] if policy["writeoff_requires_approval"] else ""},
        ]
    for o in out:
        o["default"] = o["value"] == (policy["underpay_default"] if direction == DIR_UNDER
                                     else policy["overpay_default"]) and o["available"]
    if out and not any(o.get("default") for o in out):
        for o in out:
            if o["available"]:
                o["default"] = True
                break
    return out


async def pre_assess(customer_id: str, funds: float,
                     allocations: Optional[List[Dict[str, Any]]] = None,
                     as_of: str = "", entity_id: str = "") -> Dict[str, Any]:
    """Hitung selisih pembayaran SEBELUM uang dialokasikan (dipakai dialog & kwitansi).

    Dua batas yang dipakai — dan inilah yang membuat angkanya jujur:
      * `expected`  = Σ tagihan yang **sudah jatuh tempo** pada pesanan tujuan;
      * `capacity`  = Σ **seluruh sisa tagihan** pesanan tujuan.

    Uang di antara kedua batas itu (mis. pelanggan membayar cicilan berikutnya lebih awal)
    BUKAN selisih: uangnya masih bisa dialokasikan ke pesanan yang sama, jadi tidak ada
    yang perlu diputuskan. Selisih hanya lahir bila uang **kurang dari yang jatuh tempo**
    atau **lebih dari yang bisa dialokasikan**.

    Dipanggil dari `ar_receipt_service.create_receipt` sebelum alokasi mengubah
    outstanding, sehingga `expected` tidak bisa dikarang dari sisi klien.
    """
    day = _hari_buku(as_of)
    policy = await variance_policy(entity_id, customer_id)
    tg = await _targets(customer_id, allocations, day)
    targets, others = tg["targets"], tg["others"]
    expected = round(sum(t["expected"] for t in targets), 2)
    open_capacity = round(sum(t["outstanding"] for t in targets), 2)
    # Bila petugas MENYEBUT alokasinya, yang benar-benar mendarat di tagihan adalah
    # nominal itu (dibatasi sisa tagihan) — sisanya pasti menjadi kelebihan bayar.
    # UAT 24 Okt (audit UI tahap 2) — G1-12: alokasi yang hanya menyebut pesanan (tanpa `amount`, mis. takar ulang
    # "putus belakangan" dari antrean Selisih Bayar) berarti "pesanan tujuan", BUKAN nominal 0. Dulu kapasitasnya
    # jadi 0 → dialog menulis "seharusnya Rp 0 … LEBIH bayar" untuk kwitansi yang sebenarnya KURANG bayar.
    sized = [a for a in (allocations or []) if a.get("amount") is not None]
    if sized:
        planned = round(sum(min(round(float(a.get("amount") or 0), 2),
                                next((t["outstanding"] for t in targets
                                      if t["order_id"] == a.get("order_id")), 0.0))
                            for a in sized), 2)
        capacity = min(planned, open_capacity)
    else:
        capacity = open_capacity
    others_total = round(sum(o["outstanding"] for o in others), 2)
    money = round(float(funds or 0), 2)
    # Pelatihan 18 Nov — pesanan tujuan yang belum jatuh tempo memakai sisa tagihannya sebagai `expected` (lihat
    # `_targets`); labelnya dulu tetap "tagihan yang jatuh tempo" sehingga bayar 40 % atas tagihan "30 hari lagi" terbaca
    # seolah tagihannya sudah jatuh tempo. Angka & arah selisih tidak berubah, hanya kalimatnya.
    belum_tempo = bool(targets) and all(t.get("basis") in ("term_not_due", "plan_not_due") for t in targets)
    label_harap = "sisa tagihan pesanan tujuan, belum jatuh tempo" if belum_tempo else "tagihan yang jatuh tempo"

    if money > capacity + EPS:
        delta = round(money - capacity, 2)          # LEBIH bayar (tak bisa dialokasikan)
        boundary, boundary_label = capacity, "sisa tagihan pesanan tujuan"
    elif money < expected - EPS:
        delta = round(money - expected, 2)          # KURANG bayar (jatuh tempo tak tertutup)
        boundary, boundary_label = expected, label_harap
    else:
        delta, boundary, boundary_label = 0.0, expected, label_harap
    direction = classify(delta, policy["tolerance"])
    # Usulan jatuh tempo baru dihitung dari hari ini WIB (dulu tanggal UTC: pukul 00.00–07.00 WIB sehari lebih awal).
    suggested_due = (date.fromisoformat(_hari_buku())
                     + timedelta(days=int(policy["reschedule_days"]))).isoformat()
    ctx = {"has_plan": any(t.get("plan_id") for t in targets),
           "others_total": others_total, "plan_total": capacity,
           "suggested_due_date": suggested_due}
    cust = await db.customers.find_one({"id": customer_id},
                                       {"_id": 0, "name": 1, "deposit_balance": 1}) or {}
    explain = [
        f"Uang masuk {_rp(money)}",
        (f"{boundary_label.capitalize()} ({len(targets)} pesanan tujuan) = {_rp(boundary)}"
         if targets else "Tidak ada pesanan terbuka untuk dialokasikan"),
        (f"Selisih {_rp(abs(delta))} "
         + ("KURANG bayar" if delta < 0 else "LEBIH bayar" if delta > 0 else "nihil")),
        f"Toleransi berlaku {_rp(policy['tolerance'])} (Pusat Pengaturan → Uang Masuk & Piutang)",
    ]
    return {
        "customer_id": customer_id, "customer_name": cust.get("name", ""),
        "deposit_balance": round(float(cust.get("deposit_balance") or 0), 2),
        "as_of": day, "funds": money, "expected": expected, "delta": delta,
        "capacity": capacity, "open_capacity": open_capacity,
        "boundary": round(float(boundary), 2),
        "boundary_label": boundary_label, "direction": direction,
        "needs_decision": direction in (DIR_UNDER, DIR_OVER),
        "auto": direction == DIR_ROUNDING,
        "tolerance": policy["tolerance"], "policy": policy,
        "targets": targets, "others": others, "others_total": others_total,
        "suggested_due_date": suggested_due,
        "options": _options(direction, delta, policy, ctx),
        "explain": explain,
    }


STORED_KEYS = ("expected", "funds", "capacity", "boundary", "boundary_label", "delta", "direction", "explain")


def apply_stored_variance(assessment: Dict[str, Any], variance: Dict[str, Any]) -> Dict[str, Any]:
    """G1-12 — dialog "putus belakangan" memakai SATU sumber angka: blok selisih yang disimpan pada kwitansi
    (angka saat kwitansi dibuat, sebelum uangnya dialokasikan). Takar ulang sesudah alokasi hanya dipakai untuk
    pesanan tujuan/lain & kebijakan; kalimat, rincian, tabel dan pilihan semuanya dari blok tersimpan."""
    v = variance or {}
    out = dict(assessment or {})
    for k in STORED_KEYS:
        if v.get(k) not in (None, "", []):
            out[k] = v[k]
    for k in ("expected", "funds", "capacity", "boundary", "delta"):
        if k in out:
            out[k] = round(float(out.get(k) or 0), 2)
    if not out.get("boundary"):
        out["boundary"] = out.get("expected", 0.0)
    if out.get("policy"):
        out["options"] = _options(out.get("direction", ""), out.get("delta", 0.0), out["policy"],
                                  {"has_plan": any(t.get("plan_id") for t in out.get("targets") or []),
                                   "others_total": out.get("others_total", 0),
                                   "plan_total": out.get("capacity", 0),
                                   "suggested_due_date": out.get("suggested_due_date", "")})
    return out


def variance_block(assessment: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan selisih yang DISIMPAN pada kwitansi (bahan antrean & invarian)."""
    return {
        "expected": assessment["expected"], "funds": assessment["funds"],
        "capacity": assessment.get("capacity", 0.0),
        "boundary": assessment.get("boundary", assessment["expected"]),
        "boundary_label": assessment.get("boundary_label", ""),
        "delta": assessment["delta"], "direction": assessment["direction"],
        "tolerance": assessment["tolerance"],
        "needs_decision": assessment["needs_decision"],
        "target_order_ids": [t["order_id"] for t in assessment.get("targets") or []],
        "decision_id": "", "decision_kind": "", "decision_number": "",
        "resolved": assessment["direction"] in (DIR_NONE,),
        "explain": assessment.get("explain") or [],
    }


# ── Efek keputusan (masing-masing punya jejak jurnal sendiri) ──────────────
# PK-19 — efek keputusan melewati SATU fungsi alokasi (`ar_allocation_service`): hapus sisa = baris `hapus_sisa`,
# alih deposit = baris `deposit` per pesanan, pembatalan = baris pembalik. Jurnalnya lewat pintu tahan-gagal
# (`posting_registry.durable_variance_decision`), bukan dipanggil telanjang.
WRITEOFF_KINDS = ("writeoff", "rounding_writeoff")
AP_WRITEOFF_KINDS = ("ap_writeoff", "ap_rounding_writeoff")
#: Pilihan yang menerbitkan jurnal keputusan (selain itu `gl_status="not_required"`).
JOURNAL_KINDS = WRITEOFF_KINDS + ("allocate", "refund") + AP_WRITEOFF_KINDS


def _dari_http(exc: HTTPException) -> "VarianceError":
    """Galat pemeriksa alokasi (HTTP 400/403/404/409) → galat keputusan berkode sama (pesan siap tampil)."""
    pesan = exc.detail if isinstance(exc.detail, str) else str((exc.detail or {}).get("message") or exc.detail)
    if exc.status_code == 403:
        return VarianceForbidden(pesan)
    if exc.status_code == 409:
        return VarianceConflict(pesan)
    return VarianceError(pesan)


async def _rencana_hapus_sisa(order_ids: List[str], amount: float, entity_id: str = "") -> List[Dict[str, Any]]:
    """Bagi nominal hapus sisa ke pesanan tujuan berurutan menurut sisa tagihannya (tanpa tulisan). Hanya pesanan PT
    kwitansi (`entity_id`) — pesanan tujuan FIFO bisa memuat pesanan pelanggan di PT lain (PK-19 FX-05)."""
    from services.customer_service import _order_grand_total as gt_of, _order_paid as paid_of
    left = round(float(amount or 0), 2)
    rows: List[Dict[str, Any]] = []
    for oid in order_ids:
        if left <= EPS:
            break
        order = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
        if not order or (entity_id and (order.get("entity_id") or "") != entity_id):
            continue
        take = min(left, round(gt_of(order) - paid_of(order), 2))
        if take <= EPS:
            continue
        rows.append({"order_id": oid, "order_number": order.get("number", oid), "amount": round(take, 2),
                     "entity_id": order.get("entity_id", "")})
        left = round(left - take, 2)
    if left > EPS:
        raise VarianceError(
            f"Sisa {_rp(left)} tidak bisa dihapus — tidak ada tagihan terbuka sebesar itu "
            "pada pesanan tujuan.")
    return rows


def _rencana_alokasi(allocations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Baris alih deposit (gabung per pesanan, urutan pertama muncul) — tiap baris punya penanda langkahnya."""
    from services.ar_allocation_service import id_pesanan
    per: Dict[str, float] = {}
    for al in allocations or []:
        oid = id_pesanan(al.get("order_id"))
        amt = round(float(al.get("amount") or 0), 2)
        if oid and amt > EPS:
            per[oid] = round(per.get(oid, 0.0) + amt, 2)
    return [{"order_id": oid, "amount": amt, "deposit_taken": False, "allocated": False, "ar": False}
            for oid, amt in per.items()]


async def _tandai(decision_id: str, fields: Dict[str, Any]) -> None:
    await db[COLL].update_one({"id": decision_id}, {"$set": {**fields, "updated_at": now_iso()}})


async def _jalankan_hapus_sisa(d: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Tutup sisa piutang pesanan lewat baris `hapus_sisa` (satu per pesanan, id dari keputusan → aman diulang)."""
    from services import ar_allocation_service as aas
    done: List[Dict[str, Any]] = []
    for row in d.get("plan") or []:
        try:
            res = await aas.allocate(
                kind="hapus_sisa", order_id=row["order_id"], amount=row["amount"], source_id=d["id"],
                source_number=d.get("receipt_number") or d["number"], customer_id=d.get("customer_id", ""),
                entity_id=d.get("entity_id", ""), date=d.get("decided_at") or now_iso(), actor=actor,
                method="writeoff",
                extra={"variance_decision_id": d["id"], "variance_decision_number": d["number"],
                       "note": f"Selisih kurang bayar dihapus · {d.get('reason_label', '')}"})
        except HTTPException as exc:
            raise _dari_http(exc) from exc
        done.append({"order_id": row["order_id"], "order_number": res["order_number"], "amount": row["amount"],
                     "payment_status": res["payment_status"], "entity_id": res["entity_id"]})
    return {"orders": done, "effect": {"written_off": done, "account": gl_service.ACC_SELISIH_BAYAR}}


async def _jalankan_alokasi(d: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Kelebihan bayar dipakai melunasi pesanan lain, PER BARIS: kurangi deposit (bersyarat saldo cukup) →
    `allocate(kind="deposit", seq=id pesanan)`; gagal → deposit baris itu dikembalikan dan galat dilempar (baris
    sebelumnya tetap). Penanda per baris (`plan.<i>.deposit_taken/allocated`) membuat panggilan ulang meneruskan."""
    from services import ar_allocation_service as aas
    from services import ar_receipt_service as ars
    plan = [dict(r) for r in d.get("plan") or []]
    for i, row in enumerate(plan):
        if row.get("allocated"):
            continue
        oid, amt = row["order_id"], round(float(row["amount"]), 2)
        if not row.get("deposit_taken"):
            try:
                await ars.adjust_deposit(d.get("customer_id", ""), -amt)
            except HTTPException as exc:
                raise VarianceConflict(
                    f"Deposit pelanggan tidak cukup untuk alokasi ke pesanan {row.get('order_number') or oid} "
                    "(baru saja terpakai proses lain).") from exc
            row["deposit_taken"] = True
            await _tandai(d["id"], {f"plan.{i}.deposit_taken": True})
        try:
            res = await aas.allocate(
                kind="deposit", order_id=oid, amount=amt, source_id=d["id"],
                source_number=f"{d['number']} (dari kelebihan bayar {d.get('receipt_number', '')})",
                customer_id=d.get("customer_id", ""), entity_id=d.get("entity_id", ""),
                date=d.get("decided_at") or now_iso(), actor=actor, method="deposit", seq=oid)
        except Exception as exc:
            await ars.adjust_deposit(d.get("customer_id", ""), amt)   # deposit baris ini dikembalikan
            await _tandai(d["id"], {f"plan.{i}.deposit_taken": False})
            if isinstance(exc, HTTPException):
                raise _dari_http(exc) from exc
            raise
        # KEB-PDPT — pesanan tujuan belum dikirim → dananya tetap uang muka (2-1400), tanpa jurnal alih.
        ar = await gl_service.order_revenue_posted(oid)
        if not ar:
            await gl_service.tag_advance_payment(oid, d["id"])
        row.update({"allocated": True, "ar": ar, "order_number": res["order_number"],
                    "payment_status": res["payment_status"], "outstanding_after": res["outstanding_after"]})
        await _tandai(d["id"], {f"plan.{i}": row})
    total = round(sum(r["amount"] for r in plan if r.get("allocated")), 2)
    ar_total = round(sum(r["amount"] for r in plan if r.get("allocated") and r.get("ar")), 2)
    rows = [{"order_id": r["order_id"], "order_number": r.get("order_number", r["order_id"]), "applied": r["amount"],
             "payment_status": r.get("payment_status"), "outstanding_after": r.get("outstanding_after")}
            for r in plan if r.get("allocated")]
    return {"orders": rows, "amount": total,
            "effect": {"allocated": rows, "ar_total": ar_total, "advance_total": round(total - ar_total, 2)}}


async def _jalankan_refund(d: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Kelebihan bayar dikembalikan (SL-14): deposit dikurangi DULU (bersyarat saldo cukup), lalu kas keluar lewat
    pembuat kas satu pintu (PK-20, rujukan `ar_refund` = id keputusan, rekening dari `decide_receipt`). Kas gagal
    DIBUAT → deposit dikembalikan dan galat dilempar. Kas tercatat tetapi jurnalnya gagal → uang sudah keluar: deposit
    tetap berkurang, kas `failed` tampil di panel Posting Gagal."""
    from services import ar_receipt_service as ars
    from services import cash_ledger
    ref = dict((d.get("effect") or {}).get("refund") or {})
    amt = round(float(d.get("amount") or 0), 2)
    if not ref.get("deposit_taken"):
        try:
            await ars.adjust_deposit(d.get("customer_id", ""), -amt)
        except HTTPException as exc:
            raise VarianceConflict("Saldo kelebihan bayar pelanggan tidak cukup untuk dikembalikan "
                                   "(baru saja terpakai proses lain).") from exc
        ref["deposit_taken"] = True
        await _tandai(d["id"], {"effect.refund.deposit_taken": True})
    from services.cash_entity_service import resolve_owner as _cash_owner
    entity_id = d.get("entity_id") or DEFAULT_ENTITY_ID
    gl_error = ""
    try:
        cdoc = await cash_ledger.create_cash(
            entity_id=_cash_owner(entity_id, DEFAULT_ENTITY_ID, what="Kas pengembalian dana pelanggan"),
            direction="out", amount=amt, ref_type="ar_refund", ref_id=d["id"],
            account_id=ref.get("account_id") or "", cash_type=ref.get("cash_type") or "kas_besar",
            category="pengembalian dana pelanggan",
            description=(f"Pengembalian kelebihan bayar {d['number']} · "
                         f"{d.get('customer_name', '')} ({d.get('reason_label', '')})"),
            owner_entity_id=entity_id, actor=actor.get("name", "system"))
    except cash_ledger.CashPostingError as exc:
        cdoc, gl_error = exc.txn, exc.error
    except Exception as exc:
        await ars.adjust_deposit(d.get("customer_id", ""), amt)   # kas tidak lahir → deposit dikembalikan
        await _tandai(d["id"], {"effect.refund.deposit_taken": False})
        if isinstance(exc, cash_ledger.CashRejected):
            raise _dari_http(exc) from exc
        raise
    ref.update({"amount": amt, "cash_txn_id": cdoc["id"], "cash_txn_number": cdoc.get("number", ""),
                "account_id": cdoc.get("account_id", ""), "gl_status": cdoc.get("gl_status", ""),
                "gl_error": gl_error})
    return {"orders": [], "effect": {"refund": ref}}


async def _reschedule(target: Dict[str, Any], amount: float, due_date: str,
                      reason_label: str, note: str,
                      actor: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Sisa kurang bayar dijadikan tempo baru pada rencana pembayaran pesanan."""
    plan_id = target.get("plan_id") or ""
    if not plan_id:
        raise VarianceError(
            f"Pesanan {target.get('number')} belum punya rencana pembayaran — "
            "susun jadwal dulu sebelum memilih 'Ubah jadwal'.")
    plan = await plans.get(plan_id)
    if not plan:
        raise VarianceError("Rencana pembayaran tujuan tidak ditemukan.")
    left = round(float(amount or 0), 2)
    moved: List[Dict[str, Any]] = []
    guard = 0
    while left > EPS and guard < 24:
        guard += 1
        plan = await plans.get(plan_id)
        rows = plans.due_lines(plan) or [l for l in (plan.get("lines") or [])
                                         if l.get("status") != "paid"]
        if not rows:
            raise VarianceError("Tidak ada baris jadwal terbuka untuk dijadwalkan ulang.")
        line = rows[0]
        remaining = round(float(line.get("amount") or 0) - float(line.get("paid_amount") or 0), 2)
        take = min(left, remaining)
        if take <= EPS:
            break
        plan = await plans.reschedule_line(
            plan_id, int(line.get("seq") or 0), take, due_date,
            reason_label=reason_label, note=note, actor=actor)
        moved.append({"plan_id": plan_id, "plan_number": plan.get("number", ""),
                      "line_seq": int(line.get("seq") or 0),
                      "line_label": line.get("label", ""), "amount": take,
                      "new_due_date": due_date})
        left = round(left - take, 2)
    if left > EPS:
        raise VarianceError(
            f"Sisa {_rp(left)} melebihi baris jadwal yang bisa digeser pada rencana ini.")
    return moved



# ── Wewenang ──────────────────────────────────────────────────────────────
async def _assert_authority(kind: str, amount: float, policy: Dict[str, Any],
                            actor: Dict[str, Any], entity_id: str = "") -> str:
    """Peran & batas nominal untuk keputusan sensitif (hapus sisa / refund).

    KP-T4 — kapan wajib disetujui tetap `payment.variance_writeoff_requires_approval` (pemicu); SIAPA yang boleh
    memutus dibaca dari Aturan Persetujuan (jenis `payment_variance.hapus_sisa`; dulu `payment.variance_writeoff_
    approver_role` + admin, termasuk peran kustom beracuannya).

    PK-38 — hapus sisa (`writeoff`) tidak lagi dibatasi "harus admin" di atas `writeoff_max_amount`: batasnya kini satu
    untuk semua pengurang piutang tanpa uang masuk dan di atasnya keputusan harus orang kedua
    (`services/ar_reduction_guard.py`). Pengembalian dana (`refund`) dan tutup sisa hutang (`ap_writeoff`) bukan
    pengurang piutang: batas "harus admin" di atas `writeoff_max_amount` tetap berlaku untuk keduanya (perilaku hari ini)."""
    if kind not in SENSITIVE_KINDS or not policy["writeoff_requires_approval"]:
        return ""
    role = (actor.get("role") or "").lower()
    need = (policy["writeoff_approver_role"] or "manager").lower()
    from services import approval_policy_service as _aps
    res = await _aps.can_decide("payment_variance.hapus_sisa", entity_id or None, float(amount or 0), actor,
                                check_permission=False)
    if not res["allowed"]:
        raise VarianceError(f"Keputusan '{KIND_LABEL.get(kind, kind)}': {res['message']} Ajukan ke penyetuju.")
    cap = float(policy["writeoff_max_amount"] or 0)
    if kind != "writeoff" and cap > 0 and round(float(amount), 2) > cap + EPS and role != "admin":
        raise VarianceError(
            f"Nominal {_rp(amount)} melebihi batas keputusan {need} ({_rp(cap)}) — "
            "harus admin/direksi.")
    return need


# ── Dokumen keputusan ─────────────────────────────────────────────────────
async def _insert_decision(doc: Dict[str, Any]) -> Dict[str, Any]:
    await db[COLL].insert_one(dict(doc))
    # FASE G-4 — keputusan selisih adalah DOKUMEN: menaut sumbernya dua arah.
    try:
        from services import doc_refs_service as _refs
        if doc.get("receipt_id"):
            await _refs.safe_link(("payment_variance", doc["id"]),
                                  ("ar_receipt", doc["receipt_id"]), "parent",
                                  note="keputusan selisih pembayaran kwitansi ini")
        for t in doc.get("orders") or []:
            if t.get("order_id"):
                await _refs.safe_link(("payment_variance", doc["id"]),
                                      ("sales_order", t["order_id"]), "settles",
                                      note="selisih pembayaran pesanan ini")
    except Exception as exc:  # noqa: BLE001 — jejak relasi best-effort
        logger.warning("[_insert_decision] efek samping gagal diabaikan: %s", exc)  # KN-C10
    return safe_doc(doc)


async def _notify(doc: Dict[str, Any]) -> None:
    if doc.get("kind") not in SENSITIVE_KINDS:
        return
    try:
        from services import notification_service as ns
        await ns.create_notification(
            notif_type="payment_variance", severity="warning",
            title=f"{KIND_LABEL.get(doc['kind'], doc['kind'])} {doc['number']}",
            body=(f"{doc.get('customer_name', '')} · {_rp(doc.get('amount'))} "
                  f"— alasan: {doc.get('reason_label', '')} (pemutus {doc.get('decided_by', '')})"),
            link="payment-plans", entity_id=doc.get("entity_id"),
            recipient_role="manager", ref=doc["id"], dedupe_scope="day")
    except Exception:  # noqa: BLE001
        return


async def get(decision_id: str) -> Optional[Dict[str, Any]]:
    row = await db[COLL].find_one({"id": decision_id}, {"_id": 0})
    return safe_doc(row) if row else None


# ── Keputusan sisi AR ─────────────────────────────────────────────────────
async def _kalah_balapan_atau(receipt_id: str, exc: Exception) -> Exception:
    """Galat PERIKSA keputusan kwitansi: bila sementara itu keputusan lain sudah lahir untuk kwitansi ini (balapan),
    jawab 409 "sedang atau sudah diputus"; selain itu galat aslinya."""
    fresh = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0, "number": 1, "variance": 1}) or {}
    v = fresh.get("variance") or {}
    if v.get("decision_id"):
        d = await get(v["decision_id"])
        return VarianceConflict(_pesan_klaim(fresh, (d or {}).get("kind") or v.get("decision_kind") or ""))
    return exc


def _pesan_klaim(receipt: Dict[str, Any], kind: str) -> str:
    return (f"Selisih kwitansi {receipt.get('number', '')} sedang atau sudah diputus "
            f"({KIND_LABEL.get(kind, kind) or 'keputusan lain'}).")


async def decide_receipt(receipt_id: str, payload: Dict[str, Any],
                         actor: Dict[str, Any]) -> Dict[str, Any]:
    """Terapkan keputusan selisih pada satu kwitansi (saat dibuat ATAU belakangan) — urutan `02_STANDAR.md` §1
    (PK-19, FX-06).

    PERIKSA (pilihan, wewenang, pesanan tujuan lewat `ar_allocation_service.validate_targets`, saldo deposit,
    periode) → NIAT: `variance.decision_id` ditulis pada kwitansi DENGAN SYARAT masih kosong (kalah → 409) lalu
    keputusan `pending` ber-id itu disimpan → EFEK → JURNAL lewat pintu tahan-gagal → `done`. Panggilan ulang atas
    keputusan `pending`/`failed` dengan pilihan yang sama meneruskan; pilihan berbeda → 409."""
    receipt = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not receipt:
        raise VarianceError("Kwitansi tidak ditemukan.")
    receipt = safe_doc(receipt)
    if receipt.get("status") == "void":
        raise VarianceError("Kwitansi sudah dibatalkan — tidak ada selisih untuk diputus.")
    v = receipt.get("variance") or {}
    if not v:
        raise VarianceError(
            "Kwitansi ini tidak punya catatan selisih pembayaran (dibuat sebelum FASE G-3).")
    direction = v.get("direction") or DIR_NONE
    kind = str(payload.get("kind") or "").strip()
    if v.get("decision_id"):
        d = await get(v["decision_id"])
        if d and d.get("status") in ("pending", "failed") and d.get("kind") == kind:
            return await _jalankan_ar(d, actor, receipt=receipt)   # ULANG — teruskan dari langkah terakhir yang tercatat
        raise VarianceConflict(_pesan_klaim(receipt, (d or {}).get("kind") or v.get("decision_kind") or ""))
    if direction in (DIR_NONE,):
        raise VarianceError("Kwitansi ini tidak punya selisih yang perlu diputus.")

    allowed = (AR_UNDER_KINDS if direction in (DIR_UNDER,) else AR_OVER_KINDS)
    if direction == DIR_ROUNDING:
        allowed = ("rounding_writeoff", "rounding_deposit")
    if kind not in allowed:
        raise VarianceError(
            f"Pilihan '{kind}' tidak tersedia untuk selisih {direction}. "
            f"Pilihan yang sah: {', '.join(allowed)}.")

    customer = await db.customers.find_one({"id": receipt.get("customer_id")}, {"_id": 0}) or {}
    entity_id = receipt.get("entity_id") or customer.get("entity_id") or DEFAULT_ENTITY_ID
    policy = await variance_policy(entity_id, receipt.get("customer_id", ""))
    gap = round(abs(float(v.get("delta") or 0)), 2)
    amount = round(float(payload.get("amount") or 0), 2) or gap
    if amount > gap + EPS:
        raise VarianceError(f"Nominal keputusan {_rp(amount)} melebihi selisih {_rp(gap)}.")
    reason = await _reason_or_fail(payload.get("reason_code", ""))
    approver_role = await _assert_authority(kind, amount, policy, actor, entity_id)
    from services import ar_reduction_guard as _arg
    if _arg.berlaku("payment_variance", kind):
        # PK-38 — hapus sisa = pengurang piutang tanpa uang masuk: satu batas + orang kedua (sebelum efek apa pun).
        # `VarianceForbidden` (turunan `VarianceError`): jalur antrean menjawab 403; keputusan saat kwitansi dibuat
        # tidak membatalkan uang yang sudah masuk — selisih masuk antrean.
        try:
            await _arg.periksa(sumber="payment_variance", jenis=kind, entity_id=entity_id, nominal=amount,
                               dokumen=receipt, aktor=actor, pengaju=[receipt.get("created_by")])
        except HTTPException as exc:
            raise VarianceForbidden(str(exc.detail)) from exc
    elif not payload.get("auto"):
        # KF-T6 — pencatat kwitansi ≠ pemutus selisih dari `kontrol.pengurang_piutang.*`. Di sini `VarianceError` (bukan
        # 403): keputusan saat kwitansi dibuat tidak boleh membatalkan uang yang sudah masuk — selisih masuk antrean.
        # Jalur antrean (`routers/payment_variance.py`) sudah menolak 403 lebih dulu. PK-38 — pilihan selain hapus sisa
        # tidak mengurangi piutang tanpa uang masuk: hanya jumlah orang (batas nominal tidak berlaku, `nominal=0`).
        from services import dual_control as _dc
        _dcr = await _dc.periksa("pengurang_piutang", receipt, actor, entity_id, nominal=0.0,
                                 pengaju=[receipt.get("created_by")])
        if _dcr["ditolak"]:
            raise VarianceError(_dcr["pesan"])
    if kind not in ("outstanding", "reschedule"):   # PK-37 — dua pilihan ini tanpa perubahan pembukuan
        await _periksa_periode(entity_id)
    refund: Dict[str, Any] = {}
    if kind == "refund":   # PM-T1 — cara pengembalian dari daftar induk cara bayar (arah keluar), sebelum menulis
        from services import payment_method_service as _pms
        try:
            refund_method = (await _pms.wajib(entity_id, payload.get("method") or policy["refund_method"],
                                              arah="keluar"))["code"]
        except _pms.CaraBayarError as exc:
            raise VarianceError(str(exc)) from exc
        # PK-20 — rekening sumber pengembalian (isian `account_id`; kosong = rekening tunggal PT jenis kas itu)
        # diperiksa SEBELUM menulis apa pun.
        from services import cash_ledger as _cl
        cash_type = "kas_kecil" if await _pms.is_cash(entity_id or "", refund_method) else "kas_besar"
        try:
            acc = (await _cl.periksa_rekening(entity_id or DEFAULT_ENTITY_ID, payload.get("account_id") or "",
                                              cash_type))["account_id"]
        except _cl.CashRejected as exc:
            raise VarianceError(str(exc.detail)) from exc
        refund = {"method": refund_method or "transfer", "cash_type": cash_type, "account_id": acc,
                  "deposit_taken": False}

    target_ids = list(v.get("target_order_ids") or [])
    tg = await _targets(receipt.get("customer_id", ""),
                        [{"order_id": oid} for oid in target_ids] or None,
                        _hari_buku(receipt.get("receipt_date") or ""))   # tanggal buku WIB (dulu 10 huruf / UTC)
    targets = tg["targets"]
    # PERIKSA tujuan & saldo — tanpa tulisan (PK-19 FX-05/SL-08: pemeriksa alokasi yang sama dengan kwitansi).
    from services import ar_allocation_service as aas
    plan: List[Dict[str, Any]] = []
    effect: Dict[str, Any] = {}
    orders_touched: List[Dict[str, Any]] = []
    try:
        if kind in WRITEOFF_KINDS:
            plan = await _rencana_hapus_sisa([t["order_id"] for t in targets] or target_ids, amount, entity_id)
            await aas.validate_targets("hapus_sisa", plan, customer_id=receipt.get("customer_id", ""),
                                       entity_id=entity_id)
        elif kind == "allocate":
            plan = _rencana_alokasi(payload.get("allocations") or [])
            total = round(sum(r["amount"] for r in plan), 2)
            if total <= EPS:
                raise VarianceError("Pilih minimal satu pesanan dan nominal alokasinya.")
            # LB-T4 (B3, R11) — titipan pelanggan ke pesanan yang ditahan bayar hanya oleh pemegang
            # `payment_report.decide` (409 → `VarianceConflict` lewat `_dari_http`).
            from services import ar_receipt_service as _ars_b3
            await _ars_b3.pagar_lapor_bayar(actor, [r["order_id"] for r in plan])
            if total > gap + EPS:
                raise VarianceError(f"Total alokasi {_rp(total)} melebihi kelebihan bayar {_rp(gap)}.")
            from services import ar_receipt_service as ars
            avail = await ars.get_deposit_balance(receipt.get("customer_id", ""))
            if total > avail + EPS:
                raise VarianceError(f"Deposit pelanggan tidak cukup (tersedia {_rp(avail)}).")
            await aas.validate_targets("deposit", plan, customer_id=receipt.get("customer_id", ""),
                                       entity_id=entity_id)
            amount = total
        elif kind == "refund":
            from services import ar_receipt_service as ars
            avail = await ars.get_deposit_balance(receipt.get("customer_id", ""))
            if amount <= EPS:
                raise VarianceError("Nominal pengembalian harus lebih dari nol.")
            if amount > avail + EPS:
                raise VarianceError(f"Saldo kelebihan bayar pelanggan tidak cukup untuk dikembalikan "
                                    f"(tersedia {_rp(avail)}).")
            effect = {"refund": refund}
    except HTTPException as exc:
        raise await _kalah_balapan_atau(receipt_id, _dari_http(exc)) from exc
    except VarianceError as exc:
        # Lapis A U16 — dua keputusan bersamaan: yang kalah bisa membaca kwitansi sebelum pemenang mengklaim, lalu
        # gagal di PERIKSA karena pemenang sudah menulis efeknya (mis. "tidak ada tagihan terbuka"). Itu "sudah
        # diputus" (409), bukan masukan salah (400).
        raise await _kalah_balapan_atau(receipt_id, exc) from exc
    if kind == "reschedule":
        due = str(payload.get("due_date") or "")[:10] or (
            datetime.now(timezone.utc)
            + timedelta(days=int(policy["reschedule_days"]))).date().isoformat()
        chosen = next((t for t in targets if t.get("plan_id")), None)
        if payload.get("order_id"):
            chosen = next((t for t in targets if t["order_id"] == payload["order_id"]), chosen)
        if not chosen:
            raise VarianceError(
                "Tidak ada pesanan tujuan yang punya rencana pembayaran — "
                "susun jadwal dulu atau pilih 'sisa tetap piutang'.")
        effect = {"due_date": due, "reschedule_target": chosen}
        orders_touched = [{"order_id": chosen["order_id"], "order_number": chosen["number"], "amount": amount}]

    # NIAT — klaim kwitansi (`variance.decision_id` masih kosong) lalu keputusan `pending` ber-id itu.
    number = await next_doc_number(COLL, "number", "SLB-", entity_id=entity_id or None)
    decision_id = new_id("pvd")
    klaim = await db.ar_receipts.update_one(
        {"id": receipt_id, "status": {"$ne": "void"},
         "$or": [{"variance.decision_id": ""}, {"variance.decision_id": None},
                 {"variance.decision_id": {"$exists": False}}]},
        {"$set": {"variance.decision_id": decision_id, "variance.decision_kind": kind,
                  "variance.decision_number": number, "variance.decision_status": "pending",
                  "updated_at": now_iso()}})
    if not klaim.modified_count:
        fresh = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0, "number": 1, "variance": 1}) or receipt
        raise VarianceConflict(_pesan_klaim(fresh, ((fresh.get("variance") or {}).get("decision_kind")) or ""))
    doc = {
        "id": decision_id, "number": number, "side": "ar", "entity_id": entity_id,
        "receipt_id": receipt["id"], "receipt_number": receipt.get("number", ""),
        "customer_id": receipt.get("customer_id", ""),
        "customer_name": receipt.get("customer_name", ""),
        "direction": direction, "kind": kind, "kind_label": KIND_LABEL.get(kind, kind),
        "expected": round(float(v.get("expected") or 0), 2),
        "funds": round(float(v.get("funds") or 0), 2),
        "delta": round(float(v.get("delta") or 0), 2),
        "amount": amount, "tolerance": round(float(v.get("tolerance") or 0), 2),
        "auto": bool(payload.get("auto")),
        "reason_code": reason["code"], "reason_label": reason["label"],
        "note": str(payload.get("note") or ""),
        "decided_by": actor.get("name", "system"), "decided_by_role": actor.get("role", ""),
        "decided_at": now_iso(), "approver_role_required": approver_role,
        "status": "pending", "plan": plan,
        "gl_status": "pending" if kind in JOURNAL_KINDS else "not_required", "gl_error": "",
        "journal_entry_id": "",
        "orders": orders_touched, "effect": effect,
        "je_id": "", "je_number": "",
        "policy_snapshot": policy, "refs": [],
        "explain": (v.get("explain") or []) + [
            f"Keputusan: {KIND_LABEL.get(kind, kind)} sebesar {_rp(amount)}",
            f"Alasan: {reason['label']}" + (f" — {payload.get('note')}" if payload.get("note") else ""),
            f"Pemutus: {actor.get('name', 'system')}"
            + (f" (wajib {approver_role})" if approver_role else ""),
        ],
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    # Keputusan lahir TERKUNCI milik permintaan ini (INV-ATOMIC-01): panggilan ulang bersamaan tidak bisa ikut
    # menjalankan efeknya sebelum permintaan ini selesai (kalah → 409).
    from services import atomic_claim as _saga
    token = new_id("lk")
    doc[_saga.LOCK] = {"action": "variance_decide", "by": actor.get("name", ""), "started_at": now_iso(),
                       "token": token}
    saved = await _insert_decision(doc)
    return await _jalankan_ar(saved, actor, receipt=receipt, token=token)


async def _jalankan_ar(d: Dict[str, Any], actor: Dict[str, Any], *, receipt: Dict[str, Any],
                       token: str = "") -> Dict[str, Any]:
    """Klaim keputusan (bila belum dipegang) → EFEK → JURNAL → SELESAI; kunci dilepas di `finally`."""
    from services import atomic_claim as _saga
    if not token:
        try:
            lk = await _saga.claim(COLL, d["id"], "variance_decide",
                                   precondition={"status": {"$in": ["pending", "failed"]}},
                                   actor=actor.get("name", ""))
        except HTTPException as exc:
            raise VarianceConflict(_pesan_klaim(receipt, d.get("kind", ""))) from exc
        token = (lk.get(_saga.LOCK) or {}).get("token", "")
        d = safe_doc({k: v for k, v in lk.items() if k != _saga.LOCK})
    try:
        await _jalankan_ar_inti(d, actor)
    finally:
        await _saga.release(COLL, d["id"], token)
    saved = await get(d["id"]) or d
    if saved.get("status") == "done":
        await _notify(saved)
        if saved.get("kind") == "allocate":
            # LB-T4 (R10-d) — kelebihan bayar yang dialokasikan ke pesanan lain juga uang masuk ke pesanan itu: pesanan
            # yang ditahan bayar diperiksa ulang (buka + lepas otomatis), sama dengan sesudah kwitansi (R5). Efek
            # samping — tidak melempar. Tidak disimpan di keputusan.
            from services import ar_receipt_service as _ars
            saved["released_order_ids"] = await _ars.buka_tahan_bayar(
                [r.get("order_id") for r in saved.get("orders") or []], actor,
                f"keputusan selisih {saved.get('number', '')}")
    return saved


async def _jalankan_ar_inti(d: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """EFEK → JURNAL → SELESAI satu keputusan sisi AR (dipakai keputusan baru dan panggilan ulang)."""
    from services import posting_registry as _preg
    kind = d.get("kind", "")
    hasil: Dict[str, Any] = {}
    try:
        if kind in WRITEOFF_KINDS:
            hasil = await _jalankan_hapus_sisa(d, actor)
        elif kind == "allocate":
            hasil = await _jalankan_alokasi(d, actor)
        elif kind == "refund":
            hasil = await _jalankan_refund(d, actor)
        elif kind == "reschedule":
            ef = d.get("effect") or {}
            if not ef.get("rescheduled"):
                moved = await _reschedule(ef.get("reschedule_target") or {}, float(d.get("amount") or 0),
                                          ef.get("due_date", ""), d.get("reason_label", ""), d.get("note", ""),
                                          actor)
                hasil = {"effect": {"rescheduled": moved, "due_date": ef.get("due_date", "")}}
        elif kind in ("deposit", "rounding_deposit"):
            hasil = {"effect": {"deposit_added": d.get("amount"),
                                "note": "Kelebihan bayar tetap sebagai saldo/deposit pelanggan."}}
        else:   # outstanding
            hasil = {"effect": {"note": "Sisa tetap ditagih — tidak ada perubahan pembukuan."}}
    except Exception as exc:
        pesan = str(getattr(exc, "detail", "") or exc)[:300]
        await _tandai(d["id"], {"status": "failed", "error": pesan, "failed_at": now_iso()})
        await db.ar_receipts.update_one({"id": d.get("receipt_id")}, {"$set": {
            "variance.decision_status": "failed", "updated_at": now_iso()}})
        if kind == "allocate":   # baris yang sudah jadi tetap berjurnal (Dr 2-1400 / Cr 1-1200 per baris)
            fresh = await get(d["id"]) or d
            await _preg.durable_variance_decision(fresh)
        if isinstance(exc, VarianceError):
            raise
        if isinstance(exc, HTTPException):
            raise _dari_http(exc) from exc
        raise VarianceError(f"Keputusan {d.get('number', '')} gagal di tengah: {pesan}. Kirim keputusan yang sama "
                            "lagi untuk melanjutkan.") from exc
    upd: Dict[str, Any] = {"error": ""}
    if "orders" in hasil:
        upd["orders"] = hasil["orders"]
    if "amount" in hasil:
        upd["amount"] = hasil["amount"]
    if hasil.get("effect"):
        upd["effect"] = hasil["effect"]
    await _tandai(d["id"], upd)
    fresh = await get(d["id"]) or d
    # JURNAL — PK-18/PK-19: pintu tahan-gagal; gagal → `gl_status="failed"` (panel Posting Gagal), keputusan tetap jadi.
    if kind in JOURNAL_KINDS:
        jr = await _preg.durable_variance_decision(fresh)
        je = jr.get("journal") or {}
        if jr.get("journal_entry_id") and not je.get("number"):
            je = await db.journal_entries.find_one({"id": jr["journal_entry_id"]}, {"_id": 0, "id": 1, "number": 1}) or {}
        await _tandai(d["id"], {"je_id": je.get("id", ""), "je_number": je.get("number", "")})
    # SELESAI
    await _tandai(d["id"], {"status": "done", "done_at": now_iso()})
    await db.ar_receipts.update_one({"id": d.get("receipt_id")}, {"$set": {
        "variance.decision_status": "done", "variance.resolved": True, "variance.needs_decision": False,
        "variance.decided_by": d.get("decided_by", ""), "variance.decided_at": d.get("decided_at", ""),
        "variance.reason_label": d.get("reason_label", ""), "variance.decision_amount": fresh.get("amount"),
        "updated_at": now_iso()}})


async def auto_resolve_receipt(receipt: Dict[str, Any], actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Selisih di dalam toleransi → diputus otomatis, TAPI tetap tercatat berlabel."""
    v = receipt.get("variance") or {}
    if v.get("direction") != DIR_ROUNDING or v.get("decision_id"):
        return None
    delta = round(float(v.get("delta") or 0), 2)
    kind = "rounding_writeoff" if delta < 0 else "rounding_deposit"
    return await decide_receipt(receipt["id"], {
        "kind": kind, "reason_code": "rounding_diff", "auto": True,
        "note": "Diselesaikan otomatis karena masih di dalam toleransi selisih pembayaran.",
    }, {**actor, "role": "admin"})


# ── Pembatalan keputusan (dipakai saat kwitansi di-void) ──────────────────
async def reverse_decision(decision_id: str, reason: str,
                           actor: Dict[str, Any]) -> Dict[str, Any]:
    """Anulir keputusan selisih: efeknya dibalik, jejaknya TETAP ada (append-only).

    Dipanggil otomatis saat kwitansinya dibatalkan (`void_receipt`) sehingga tidak
    mungkin ada piutang yang sudah "dihapus" atau dana yang sudah "dikembalikan"
    padahal uangnya ternyata tidak pernah ada.

    PK-19 — baris pembayaran hapus sisa / alih deposit DIBALIK lewat `ar_allocation_service.reverse` (baris pembalik
    bertanggal, bukan dihapus); sisi hutang (`ap_writeoff`) kini benar-benar dibalik (FX-07): jurnal kebalikan persis
    Dr 4-9000 / Cr 2-1100 dan faktur kembali terbuka. Jurnal pembalik lewat pintu tahan-gagal
    (`reversal_gl_status`). Penanda langkah (`reversal_steps`) membuat panggilan ulang tidak menggandakan efek.
    """
    d = await get(decision_id)
    if not d:
        raise VarianceError("Keputusan selisih pembayaran tidak ditemukan.")
    if d.get("status") == "reversed":
        return d
    if not (reason or "").strip():
        raise VarianceError("Alasan pembatalan keputusan wajib diisi.")
    if d.get("kind") in WRITEOFF_KINDS + ("allocate",):   # PK-19 — PERIKSA: pembalik tidak membuat terbayar negatif
        from services import ar_allocation_service as _aas
        await _aas.reverse_check(decision_id)
    # T-01 Opsi B (INV-ATOMIC-01) — klaim keputusan sebelum payments SO / deposit / kas / JE dibalik;
    # dua pembatalan bersamaan (tombol + void kwitansi) tidak membalik jurnal dua kali.
    from services import atomic_claim as _saga
    lk = await _saga.claim(COLL, decision_id, "variance_reverse",
                           precondition={"status": {"$ne": "reversed"}}, actor=actor.get("name", "system"))
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    try:
        from services import ar_allocation_service as aas
        from services import ar_receipt_service as ars
        from services import posting_registry as _preg
        d = safe_doc(lk)
        steps = dict(d.get("reversal_steps") or {})
        kind = d.get("kind", "")
        undone: Dict[str, Any] = {}
        label = f"{d.get('number')} · {reason.strip()}"

        if kind in WRITEOFF_KINDS + ("allocate",):
            hasil = await aas.reverse(source_id=decision_id, date=now_iso(), actor=actor, reason=label)
            undone = {"orders_restored": [h["order_number"] for h in hasil if h.get("reversed")]}
            if kind == "allocate":
                kembali = round(sum(float(r.get("amount") or 0) for r in d.get("plan") or [] if r.get("deposit_taken"))
                                if d.get("plan") else float(d.get("amount") or 0), 2)
                if kembali > EPS and not steps.get("deposit_restored"):
                    await ars.adjust_deposit(d.get("customer_id", ""), kembali)
                    await _tandai(decision_id, {"reversal_steps.deposit_restored": True})
                undone["deposit_restored"] = kembali
        elif kind == "refund":
            ref = (d.get("effect") or {}).get("refund") or {}
            cash_id = ref.get("cash_txn_id", "")
            if cash_id:
                await db.cash_transactions.update_one(
                    {"id": cash_id, "status": {"$ne": "void"}}, {"$set": {"status": "void", "updated_at": now_iso()}})
            amt = round(float(d.get("amount") or 0), 2)
            if (ref.get("deposit_taken", True)) and not steps.get("deposit_restored"):
                await ars.adjust_deposit(d.get("customer_id", ""), amt)
                await _tandai(decision_id, {"reversal_steps.deposit_restored": True})
            undone = {"cash_voided": cash_id, "deposit_restored": amt}
        elif kind in AP_WRITEOFF_KINDS:
            # FX-07 — dulu jatuh ke cabang "tidak memindahkan uang" padahal jurnal Dr 2-1100 / Cr 4-9000 pernah terbit.
            bill = await db.vendor_bills.find_one({"id": d.get("bill_id")}, {"_id": 0}) or {}
            if bill.get("ap_variance_decision_id") == decision_id:
                from services.vendor_bill_service import bill_financials
                sisa = bill_financials({**bill, "ap_variance_closed": 0})["outstanding"]
                await db.vendor_bills.update_one(
                    {"id": bill["id"], "ap_variance_decision_id": decision_id},
                    {"$set": {"ap_variance_closed": 0.0, "ap_variance_decision_id": "", "updated_at": now_iso(),
                              **({"status": "posted"} if sisa > EPS and bill.get("status") == "paid" else {})}})
            undone = {"bill_reopened": d.get("bill_number", ""), "closed_amount": round(float(d.get("amount") or 0), 2)}
        else:
            # `outstanding` / `deposit` / `reschedule` / `ap_advance` tidak memindahkan uang di sini. Jadwal yang
            # sudah digeser TIDAK dipaksa kembali (itu kesepakatan dengan pelanggan) — cukup dicatat.
            undone = {"note": "Keputusan tidak memindahkan uang; tidak ada jurnal untuk dibalik."}

        await _tandai(decision_id, {"reversal_effect": undone, "reversed_reason": reason.strip(),
                                    "reversed_by": actor.get("name", "system"), "reversed_at": now_iso(),
                                    "reversal_gl_status": "pending" if kind in JOURNAL_KINDS else "not_required"})
        # JURNAL — pembalik lewat pintu tahan-gagal (`reversal_gl_status`; ulang dari panel Posting Gagal).
        rev_je: Dict[str, Any] = {}
        if kind in JOURNAL_KINDS:
            jr = await _preg.durable_variance_reversal(await get(decision_id) or d, actor.get("name", "system"))
            rev_je = jr.get("journal") or {}
            if jr.get("journal_entry_id") and not rev_je.get("number"):
                rev_je = await db.journal_entries.find_one({"id": jr["journal_entry_id"]},
                                                           {"_id": 0, "id": 1, "number": 1}) or {}
        await db[COLL].update_one({"id": decision_id}, _saga.finish_set({
            "status": "reversed", "reversal_je_id": rev_je.get("id", ""),
            "reversal_je_number": rev_je.get("number", ""), "updated_at": now_iso()}))
        if d.get("receipt_id"):
            await db.ar_receipts.update_one({"id": d["receipt_id"], "variance.decision_id": decision_id}, {"$set": {
                "variance.decision_id": "", "variance.decision_kind": "",
                "variance.decision_number": "", "variance.decision_status": "", "variance.resolved": False,
                "variance.reversed_decision_id": decision_id,
                "variance.needs_decision": (d.get("direction") in (DIR_UNDER, DIR_OVER)),
                "updated_at": now_iso()}})
    finally:
        await _saga.release(COLL, decision_id, token)
    return await get(decision_id)


# ── Keputusan sisi AP (bayar supplier) ────────────────────────────────────
async def assess_bill(bill: Dict[str, Any], amount: float) -> Dict[str, Any]:
    """Selisih saat membayar tagihan supplier (kurang / lebih dari sisa hutang)."""
    entity_id = bill.get("entity_id") or DEFAULT_ENTITY_ID
    policy = await variance_policy(entity_id)
    grand = round(float(bill.get("grand_total") or 0), 2)
    paid = round(float(bill.get("amount_paid") or 0), 2)
    outstanding = round(grand - paid, 2)
    money = round(float(amount or 0), 2)
    delta = round(money - outstanding, 2)
    direction = classify(delta, policy["ap_tolerance"])
    options: List[Dict[str, Any]] = []
    if direction == DIR_UNDER:
        options = [
            {"value": "ap_outstanding", "label": KIND_LABEL["ap_outstanding"],
             "help": f"Sisa {_rp(abs(delta))} tetap tercatat sebagai hutang supplier.",
             "impact": "Tagihan tetap berstatus sebagian dibayar.",
             "available": True, "default": True, "requires_reason": True, "requires_role": ""},
            {"value": "ap_writeoff", "label": KIND_LABEL["ap_writeoff"],
             "help": (f"Sisa {_rp(abs(delta))} dianggap selesai (potongan/pembulatan dari "
                      "supplier) dan tagihan ditutup lunas."),
             "impact": "Hutang −" + _rp(abs(delta)) + " · Pendapatan lain-lain naik (berjurnal).",
             "available": True, "default": False, "requires_reason": True,
             "requires_role": policy["writeoff_approver_role"] if policy["writeoff_requires_approval"] else ""},
        ]
    elif direction == DIR_OVER:
        options = [
            {"value": "ap_advance", "label": KIND_LABEL["ap_advance"],
             "help": (f"Kelebihan {_rp(delta)} dicatat sebagai uang muka ke supplier dan bisa "
                      "dipotongkan pada tagihan / kontrabon berikutnya."),
             "impact": "Uang Muka (1-1400) +" + _rp(delta) + " · kas keluar lebih besar.",
             "available": True, "default": True, "requires_reason": True, "requires_role": ""},
        ]
    return {
        "side": "ap", "bill_id": bill.get("id"), "bill_number": bill.get("bill_number", ""),
        "supplier_name": bill.get("supplier_name", ""), "entity_id": entity_id,
        "grand_total": grand, "paid": paid, "outstanding": outstanding,
        "funds": money, "expected": outstanding, "delta": delta, "direction": direction,
        "needs_decision": direction in (DIR_UNDER, DIR_OVER),
        "auto": direction == DIR_ROUNDING, "tolerance": policy["ap_tolerance"],
        "policy": policy, "options": options,
        "explain": [
            f"Sisa hutang {bill.get('bill_number', '')} = {_rp(outstanding)}",
            f"Dibayar {_rp(money)}",
            f"Selisih {_rp(abs(delta))} " + ("KURANG" if delta < 0 else "LEBIH" if delta > 0 else "nihil"),
            f"Toleransi supplier {_rp(policy['ap_tolerance'])}",
        ],
    }


async def decide_bill(bill: Dict[str, Any], assessment: Dict[str, Any],
                      payload: Dict[str, Any], actor: Dict[str, Any],
                      *, advance_cash: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Catat + terapkan keputusan selisih pembayaran supplier."""
    direction = assessment["direction"]
    if direction in (DIR_NONE,):
        raise VarianceError("Tidak ada selisih yang perlu diputus pada pembayaran ini.")
    kind = str(payload.get("kind") or "").strip()
    if direction == DIR_ROUNDING:
        kind = kind or ("ap_rounding_writeoff" if assessment["delta"] < 0
                        else "ap_rounding_advance")
    if kind not in AP_KINDS + ("ap_rounding_writeoff", "ap_rounding_advance"):
        raise VarianceError(f"Pilihan '{kind}' tidak dikenal untuk selisih pembayaran supplier.")
    entity_id = assessment["entity_id"]
    await _periksa_periode(entity_id)   # PK-37 (K-03) — sebelum nomor keputusan & jurnal selisih
    policy = assessment["policy"]
    gap = round(abs(float(assessment["delta"])), 2)
    reason_code = payload.get("reason_code") or (
        "rounding_diff" if direction == DIR_ROUNDING else "")
    reason = await _reason_or_fail(reason_code)
    approver_role = await _assert_authority(
        "ap_writeoff" if kind in ("ap_writeoff",) else kind, gap, policy, actor, entity_id)
    if direction != DIR_ROUNDING:
        # KF-T6 — pembuat tagihan ≠ pemutus selisih bayar dari `kontrol.pengurang_piutang.*`. `VarianceError` (bukan
        # 403): keputusan ini diambil SESUDAH uang keluar; pemanggil mencatat kegagalannya di linimasa tagihan.
        # PK-38 — hutang, bukan piutang: batas pengurang piutang tidak berlaku (`nominal=0`), hanya jumlah orang.
        from services import dual_control as _dc
        _dcr = await _dc.periksa("pengurang_piutang", bill, actor, entity_id, nominal=0.0,
                                 pengaju=[bill.get("created_by_id")])
        if _dcr["ditolak"]:
            raise VarianceError(_dcr["pesan"])

    number = await next_doc_number(COLL, "number", "SLB-", entity_id=entity_id or None)
    decision_id = new_id("pvd")
    if kind in AP_WRITEOFF_KINDS:
        effect: Dict[str, Any] = {"closed_amount": gap, "bill_status": "paid"}
    elif kind in ("ap_advance", "ap_rounding_advance"):
        effect = {"advance_amount": gap,
                  "cash_txn_number": (advance_cash or {}).get("number", ""),
                  "account": gl_service.ACC_UANG_MUKA}
    else:  # ap_outstanding
        effect = {"note": "Sisa tetap hutang supplier — tidak ada perubahan pembukuan."}

    # PK-19 — NIAT dulu (keputusan `pending`), lalu EFEK, JURNAL lewat pintu tahan-gagal, SELESAI (`02` §1).
    doc = {
        "id": decision_id, "number": number, "side": "ap", "entity_id": entity_id,
        "bill_id": bill.get("id"), "bill_number": bill.get("bill_number", ""),
        "supplier_id": bill.get("supplier_id", ""), "supplier_name": bill.get("supplier_name", ""),
        "direction": direction, "kind": kind, "kind_label": KIND_LABEL.get(kind, kind),
        "expected": assessment["expected"], "funds": assessment["funds"],
        "delta": assessment["delta"], "amount": gap, "tolerance": assessment["tolerance"],
        "auto": direction == DIR_ROUNDING,
        "reason_code": reason["code"], "reason_label": reason["label"],
        "note": str(payload.get("note") or ""),
        "decided_by": actor.get("name", "system"), "decided_by_role": actor.get("role", ""),
        "decided_at": now_iso(), "approver_role_required": approver_role,
        "status": "pending", "gl_status": "pending" if kind in AP_WRITEOFF_KINDS else "not_required",
        "gl_error": "", "journal_entry_id": "",
        "orders": [], "effect": effect, "je_id": "", "je_number": "",
        "policy_snapshot": policy, "refs": [],
        "explain": (assessment.get("explain") or []) + [
            f"Keputusan: {KIND_LABEL.get(kind, kind)} sebesar {_rp(gap)}",
            f"Alasan: {reason['label']}",
            f"Pemutus: {actor.get('name', 'system')}",
        ],
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    saved = await _insert_decision(doc)
    try:
        from services import doc_refs_service as _refs
        if bill.get("id"):
            await _refs.safe_link(("payment_variance", decision_id),
                                  ("vendor_bill", bill["id"]), "parent",
                                  note="selisih pembayaran tagihan supplier")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[decide_bill] efek samping gagal diabaikan: %s", exc)  # KN-C10
    # EFEK
    if kind in AP_WRITEOFF_KINDS:
        await db.vendor_bills.update_one({"id": bill["id"]}, {"$set": {
            "status": "paid", "ap_variance_closed": gap,
            "ap_variance_decision_id": decision_id, "updated_at": now_iso()}})
    elif kind in ("ap_advance", "ap_rounding_advance") and bill.get("supplier_id"):
        await db.suppliers.update_one({"id": bill["supplier_id"]},
                                      {"$inc": {"advance_balance": gap},
                                       "$set": {"updated_at": now_iso()}})
    # JURNAL — Dr 2-1100 / Cr 4-9000 (potongan supplier); gagal → `gl_status="failed"`, keputusan tetap jadi.
    if kind in AP_WRITEOFF_KINDS:
        from services import posting_registry as _preg
        jr = await _preg.durable_variance_decision(saved)
        je = jr.get("journal") or {}
        await _tandai(decision_id, {"je_id": je.get("id", "") or jr.get("journal_entry_id", ""),
                                    "je_number": je.get("number", "")})
    # SELESAI
    await _tandai(decision_id, {"status": "done", "done_at": now_iso()})
    return await get(decision_id) or saved


# ── Pembacaan untuk UI, antrean & invarian ────────────────────────────────
async def list_decisions(entity_id: Any = "", side: str = "", kind: str = "",
                         direction: str = "", q: str = "",
                         limit: int = 200) -> List[Dict[str, Any]]:
    flt: Dict[str, Any] = {}
    # FASE E-0 (L3) — dukung filter entitas siap-pakai `{"$in": [...]}`.
    if isinstance(entity_id, dict):
        flt["entity_id"] = entity_id
    elif entity_id and entity_id != "all":
        flt["entity_id"] = entity_id
    if side:
        flt["side"] = side
    if kind:
        flt["kind"] = kind
    if direction:
        flt["direction"] = direction
    if q:
        import re as _re
        rx = _re.compile(_re.escape(q), _re.I)
        flt["$or"] = [{"number": rx}, {"receipt_number": rx}, {"customer_name": rx},
                      {"bill_number": rx}, {"supplier_name": rx}]
    rows = await db[COLL].find(flt, {"_id": 0}).sort("created_at", -1).to_list(int(limit))
    return [safe_doc(r) for r in rows]


async def pending(entity_id: Any = "", limit: int = 200) -> List[Dict[str, Any]]:
    """Kwitansi yang selisihnya BELUM diputus — antrean kerja finance."""
    # PK-19 — keputusan yang belum tuntas (`pending`/`failed`) tetap di antrean: kirim pilihan yang sama untuk melanjutkan.
    flt: Dict[str, Any] = {"status": {"$ne": "void"},
                           "variance.needs_decision": True,
                           "$or": [{"variance.decision_id": ""},
                                   {"variance.decision_status": {"$in": ["pending", "failed"]}}]}
    if isinstance(entity_id, dict):
        flt["entity_id"] = entity_id
    elif entity_id and entity_id != "all":
        flt["entity_id"] = entity_id
    rows = await db.ar_receipts.find(flt, {"_id": 0}).sort("created_at", -1).to_list(int(limit))
    out = []
    for r in rows:
        r = safe_doc(r)
        v = r.get("variance") or {}
        out.append({
            "receipt_id": r["id"], "number": r.get("number", ""),
            "entity_id": r.get("entity_id", ""),
            "customer_id": r.get("customer_id", ""), "customer_name": r.get("customer_name", ""),
            "receipt_date": r.get("receipt_date", ""), "method": r.get("method", ""),
            "funds": round(float(r.get("total_funds") or 0), 2),
            "applied_total": round(float(r.get("applied_total") or 0), 2),
            "unapplied_amount": round(float(r.get("unapplied_amount") or 0), 2),
            "expected": round(float(v.get("expected") or 0), 2),
            "delta": round(float(v.get("delta") or 0), 2),
            "direction": v.get("direction", ""),
            "target_order_ids": v.get("target_order_ids") or [],
            "decision_id": v.get("decision_id") or "", "decision_kind": v.get("decision_kind") or "",
            "decision_status": v.get("decision_status") or "",
            "explain": v.get("explain") or [],
            "age_days": _age_days(r.get("created_at", "")),
        })
    return out


def _age_days(created_at: str) -> int:
    try:
        d = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - d).days)
    except Exception:  # noqa: BLE001
        return 0


async def stats(entity_id: Any = "") -> Dict[str, Any]:
    flt: Dict[str, Any] = {}
    if isinstance(entity_id, dict):
        flt["entity_id"] = entity_id
    elif entity_id and entity_id != "all":
        flt["entity_id"] = entity_id
    out = {"decisions": 0, "under": 0, "over": 0, "rounding": 0,
           "writeoff_amount": 0.0, "refund_amount": 0.0, "allocated_amount": 0.0,
           "deposit_amount": 0.0, "rescheduled_amount": 0.0, "auto": 0}
    async for r in db[COLL].find(flt, {"_id": 0, "direction": 1, "kind": 1,
                                       "amount": 1, "auto": 1}):
        out["decisions"] += 1
        out[r.get("direction", "rounding")] = out.get(r.get("direction", "rounding"), 0) + 1
        amt = float(r.get("amount") or 0)
        kind = r.get("kind", "")
        if r.get("auto"):
            out["auto"] += 1
        if kind in ("writeoff", "rounding_writeoff", "ap_writeoff", "ap_rounding_writeoff"):
            out["writeoff_amount"] += amt
        elif kind == "refund":
            out["refund_amount"] += amt
        elif kind == "allocate":
            out["allocated_amount"] += amt
        elif kind in ("deposit", "rounding_deposit", "ap_advance", "ap_rounding_advance"):
            out["deposit_amount"] += amt
        elif kind == "reschedule":
            out["rescheduled_amount"] += amt
    for k in ("writeoff_amount", "refund_amount", "allocated_amount", "deposit_amount",
              "rescheduled_amount"):
        out[k] = round(out[k], 2)
    out["pending"] = len(await pending(entity_id))
    return out


# ── Bahan invarian (INV-VAR-01 / INV-VAR-02) ──────────────────────────────
async def undecided_variances(limit: int = 20) -> List[Dict[str, Any]]:
    """INV-VAR-01 — selisih di luar toleransi yang tidak punya keputusan berlabel."""
    bad: List[Dict[str, Any]] = []
    async for r in db.ar_receipts.find(
            {"status": {"$ne": "void"}, "variance.needs_decision": True},
            {"_id": 0, "id": 1, "number": 1, "variance": 1, "created_at": 1}):
        v = r.get("variance") or {}
        if v.get("decision_id"):
            continue
        bad.append({"id": r["id"], "number": r.get("number", r["id"]),
                    "delta": round(float(v.get("delta") or 0), 2),
                    "age_days": _age_days(r.get("created_at", ""))})
        if len(bad) >= limit:
            break
    return bad


async def decisions_without_label(limit: int = 20) -> List[Dict[str, Any]]:
    """INV-VAR-01 — keputusan tanpa label alasan / tanpa pemutus (tidak boleh ada)."""
    bad: List[Dict[str, Any]] = []
    async for r in db[COLL].find({}, {"_id": 0, "id": 1, "number": 1, "kind": 1,
                                      "reason_code": 1, "decided_by": 1}):
        if not (r.get("reason_code") or "").strip() or not (r.get("decided_by") or "").strip():
            bad.append({"id": r["id"], "number": r.get("number", r["id"]),
                        "kind": r.get("kind", "")})
            if len(bad) >= limit:
                break
    return bad


async def sensitive_without_journal(limit: int = 20) -> List[Dict[str, Any]]:
    """INV-VAR-02 — keputusan yang MEMINDAHKAN uang wajib punya jurnal."""
    need_je = ("writeoff", "rounding_writeoff", "allocate", "refund",
               "ap_writeoff", "ap_rounding_writeoff")
    bad: List[Dict[str, Any]] = []
    async for r in db[COLL].find({"kind": {"$in": list(need_je)}},
                                 {"_id": 0, "id": 1, "number": 1, "kind": 1,
                                  "je_id": 1, "amount": 1, "effect": 1}):
        if float(r.get("amount") or 0) <= EPS:
            continue
        # KEB-PDPT — alokasi ke pesanan yang BELUM dikirim tidak memindahkan uang antar
        # akun (tetap Uang Muka 2-1400) → memang tanpa jurnal, bukan kebocoran.
        if r.get("kind") == "allocate" and "ar_total" in (r.get("effect") or {}) \
                and float((r.get("effect") or {}).get("ar_total") or 0) <= EPS:
            continue
        if not (r.get("je_id") or "").strip():
            bad.append({"id": r["id"], "number": r.get("number", r["id"]),
                        "kind": r.get("kind", "")})
            if len(bad) >= limit:
                break
    return bad


async def receipt_money_leaks(limit: int = 20) -> List[Dict[str, Any]]:
    """INV-VAR-02 — pada tiap kwitansi: dana == teralokasi + belum teralokasi."""
    bad: List[Dict[str, Any]] = []
    async for r in db.ar_receipts.find(
            {"status": {"$ne": "void"}},
            {"_id": 0, "id": 1, "number": 1, "total_funds": 1, "amount": 1,
             "used_deposit": 1, "applied_total": 1, "unapplied_amount": 1}):
        funds = round(float(r.get("total_funds")
                            if r.get("total_funds") is not None
                            else float(r.get("amount") or 0) + float(r.get("used_deposit") or 0)), 2)
        parts = round(float(r.get("applied_total") or 0) + float(r.get("unapplied_amount") or 0), 2)
        if abs(funds - parts) > 0.01:
            bad.append({"id": r["id"], "number": r.get("number", r["id"]),
                        "funds": funds, "parts": parts})
            if len(bad) >= limit:
                break
    return bad


async def overspent_decisions(limit: int = 20) -> List[Dict[str, Any]]:
    """INV-VAR-02 — keputusan tidak boleh memindahkan lebih dari kelebihan kwitansinya."""
    bad: List[Dict[str, Any]] = []
    async for r in db[COLL].find({"side": "ar", "kind": {"$in": ["allocate", "refund"]}},
                                 {"_id": 0, "id": 1, "number": 1, "amount": 1,
                                  "receipt_id": 1, "delta": 1}):
        rec = await db.ar_receipts.find_one({"id": r.get("receipt_id")},
                                            {"_id": 0, "unapplied_amount": 1, "number": 1})
        cap = round(float((rec or {}).get("unapplied_amount") or 0), 2)
        if round(float(r.get("amount") or 0), 2) > cap + 0.01:
            bad.append({"id": r["id"], "number": r.get("number", r["id"]),
                        "amount": round(float(r.get("amount") or 0), 2), "cap": cap})
            if len(bad) >= limit:
                break
    return bad
