"""CR-T3 (CR-02, CR-04, CR-05; K-14, K-27–K-29, K-31) — SATU mesin gerbang kredit di empat titik periksa.

`docs/blueprint/unit/CR-T3.md`. Kredit pelanggan diperiksa satu fungsi (`evaluate`) saat pesanan dibuat, diubah,
dilepas ke gudang, dan dikirim; titik mana yang aktif diatur per PT (`ar.periksa_kredit_*`). Pesanan yang sudah ada dan
gagal diperiksa DITAHAN (`hold` → `sales_orders.credit_hold`, sub-status "Tahan kredit"), bukan dibatalkan; tahanan
dilepas `recheck_holds` (pembayaran lewat `customer_balance_service.refresh`, keputusan izin kredit, tombol "Periksa ulang
kredit"). Izin kredit (`credit_overrides`) dipakai lewat `use_override` (pembaruan bersyarat sisa + masa berlaku).

Angka dari saldo piutang tersimpan (`customer_balance_service.get`) dan profil kredit yang berlaku
(`credit_profile_service.effective`) untuk PT itu SAJA (K-29). Eksposur (K-31):

    ar_delivered + open_orders (ar.eksposur_pesanan_belum_kirim) + giro_outstanding (ar.eksposur_giro_belum_cair)
    − deposit (ar.eksposur_titipan_mengurangi) + this_order

Pesanan bertermin tunai tanpa DP tetap dilewati (perilaku hari ini, CR-T2) KECUALI `finance.tahan_kirim_tunai` menyala:
saat itu bagian terkirimnya ikut piutang dan telat (mencabut pengecualian tunai yang ditinggalkan CR-T2).
Untuk pesanan yang SUDAH ada (`order_id`), pesanan itu sudah termuat di saldo; `this_order` = bagiannya di eksposur.
"""
from __future__ import annotations

import contextvars
import logging
from typing import Any, Dict, List, Optional, Tuple

from core_utils import from_cents, now_iso, rupiah, safe_doc, to_cents
from db import db

logger = logging.getLogger(__name__)

COLL_REJ = "credit_gate_rejections"
COLL_OV = "credit_overrides"

PESANAN_DIBUAT, PESANAN_DIUBAH, LEPAS_GUDANG, SURAT_JALAN = "pesanan_dibuat", "pesanan_diubah", "lepas_gudang", \
    "surat_jalan"
#: Pemeriksaan ulang pesanan yang ditahan (tombol, pembayaran, keputusan izin): selalu diperiksa, sakelar diabaikan.
PERIKSA_ULANG = "periksa_ulang"
CHECKPOINTS = (PESANAN_DIBUAT, PESANAN_DIUBAH, LEPAS_GUDANG, SURAT_JALAN)
#: Sakelar per titik periksa (Pusat Pengaturan, berlapis grup → PT).
KUNCI_TITIK = {
    "pesanan_dibuat": "ar.periksa_kredit_pesanan_dibuat",
    "pesanan_diubah": "ar.periksa_kredit_pesanan_diubah",
    "lepas_gudang": "ar.periksa_kredit_lepas_gudang",
    "surat_jalan": "ar.periksa_kredit_surat_jalan",
}
LABEL_TITIK = {PESANAN_DIBUAT: "pesanan dibuat", PESANAN_DIUBAH: "nilai pesanan naik",
               LEPAS_GUDANG: "pesanan dilepas ke gudang", SURAT_JALAN: "barang dikirim",
               PERIKSA_ULANG: "periksa ulang"}

LOLOS, PERINGATAN, TAHAN, TOLAK = "lolos", "peringatan", "tahan", "tolak"
_BOBOT = {LOLOS: 0, PERINGATAN: 1, TAHAN: 2, TOLAK: 3}
INFO = "keterangan"

BLOKIR_MANUAL, TERMIN_TIDAK_DIIZINKAN, LEWAT_PLAFON, TELAT = ("BLOKIR_MANUAL", "TERMIN_TIDAK_DIIZINKAN",
                                                              "LEWAT_PLAFON", "TELAT")
MENDEKATI_PLAFON, TELAT_RINGAN, PLAFON_KEDALUWARSA = "MENDEKATI_PLAFON", "TELAT_RINGAN", "PLAFON_KEDALUWARSA"

PESAN_DITAHAN = ("Pesanan {nomor} ditahan kredit — {alasan} Ajukan izin kredit atau catat pembayaran dulu.")
_BULAN = ("", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

#: Penjaga masuk-ulang: `recheck_holds` → `evaluate` → `customer_balance_service.get` → `refresh` → `recheck_holds`.
_SEDANG_PERIKSA: contextvars.ContextVar[bool] = contextvars.ContextVar("crt3_sedang_periksa", default=False)


def _tgl(iso: str) -> str:
    s = str(iso or "")[:10]
    try:
        y, m, d = s.split("-")
        return f"{int(d)} {_BULAN[int(m)]} {y}"
    except (ValueError, IndexError):
        return s


def _alasan(code: str, hasil: str, pesan: str, **data: Any) -> Dict[str, Any]:
    return {"code": code, "result": hasil, "message": pesan, "data": data}


async def _flag(key: str, entity_id: str) -> bool:
    from services.nilai_pengaturan import nilai
    return bool(await nilai(key, entity_id))


async def _term(code: str, entity_id: str) -> Optional[Dict[str, Any]]:
    if not code:
        return None
    from services import entity_master_service as ems
    return await ems.resolve_row("payment-terms", code, entity_id or "", include_inactive=True)


def bayar_penuh_dulu(term: Optional[Dict[str, Any]]) -> bool:
    """K-27 — termin bayar-penuh-sebelum-kirim: `type: cash` atau `dp_percent == 100`."""
    t = term or {}
    try:
        dp = float(t.get("dp_percent") or 0)
    except (TypeError, ValueError):
        dp = 0.0
    return str(t.get("type") or "").lower() == "cash" or abs(dp - 100.0) < 1e-9


async def _bagian_pesanan(order: Dict[str, Any], hari: str) -> Dict[str, Any]:
    """Bagian satu pesanan di saldo pasangannya — aturan SAMA dengan `customer_balance_service.compute` per pesanan:
    `{sisa, kirim, belum, tunai}` dalam sen."""
    from services import billing_schedule_service as bss
    from services import report_basis as rb
    from services.customer_service import DEAD_STATUSES, _order_grand_total
    if order.get("status") in DEAD_STATUSES or order.get("payment_status") == "paid":
        return {"sisa": 0, "kirim": 0, "belum": 0, "tunai": not rb.pesanan_piutang(order)}
    total = to_cents(_order_grand_total(order))
    sisa = max(0, total - max(0, rb._terbayar_sen(order, hari)))                       # noqa: SLF001
    bayar_kirim = max(0, rb._terbayar_sen(order, hari, tangguh=False))                  # noqa: SLF001
    jurnal = await rb._jurnal_pendapatan([order["id"]])                                 # noqa: SLF001
    akui = await bss.recognized_sen(order, jurnal.get(order["id"], []), {}, per=hari)
    kirim = min(sisa, max(0, akui - bayar_kirim))
    return {"sisa": sisa, "kirim": kirim, "belum": sisa - kirim, "tunai": not rb.pesanan_piutang(order)}


async def _telat_tunai(customer_id: str, entity_id: str, hari: str) -> Tuple[int, Optional[str]]:
    """`finance.tahan_kirim_tunai` menyala — lewat tempo baris tagihan pesanan bertermin tunai (dilewati saldo CR-T2):
    (sen lewat tempo, jatuh tempo tertua yang masih bersisa)."""
    from services import billing_schedule_service as bss
    from services import report_basis as rb
    from services.customer_service import DEAD_STATUSES
    orders = [o async for o in db.sales_orders.find(
        {"customer_id": customer_id, "entity_id": entity_id, "status": {"$nin": sorted(DEAD_STATUSES)},
         "payment_status": {"$ne": "paid"}}, {"_id": 0})]
    tunai = [o for o in orders if not rb.pesanan_piutang(o)]
    if not tunai:
        return 0, None
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0}) or {"id": customer_id}
    jadwal = await bss.lines_for_orders(tunai, {customer_id: cust}, per=hari)
    lewat, tertua = 0, None
    for o in tunai:
        for r in (jadwal.get(o["id"]) or {}).get("rows") or []:
            if r["outstanding"] <= rb.EPS or not r.get("due_date"):
                continue
            tertua = r["due_date"] if tertua is None else min(tertua, r["due_date"])
            if r["due_date"] < hari:
                lewat += to_cents(r["outstanding"])
    return lewat, tertua


# ── Izin kredit ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _berlaku(ov: Dict[str, Any], sekarang: str) -> bool:
    vu = str(ov.get("valid_until") or "")
    return not vu or vu > sekarang


def sisa_izin(ov: Dict[str, Any]) -> float:
    """Sisa nominal izin. Izin lama (sebelum CR-T3, tanpa `remaining_amount`): nominal bila belum dipakai, 0 bila sudah
    dipakai atau bernominal 0 (izin lama "tanpa batas" yang belum dipakai dianggap kedaluwarsa — spesifikasi)."""
    if ov.get("remaining_amount") is not None:
        return round(float(ov.get("remaining_amount") or 0), 2)
    return 0.0 if ov.get("consumed") else round(max(0.0, float(ov.get("amount") or 0)), 2)


def lingkup(ov: Dict[str, Any]) -> str:
    """Izin lama tanpa `scope` = lingkup pelanggan (dulu dipakai pesanan mana pun pelanggan itu)."""
    return "pesanan" if ov.get("scope") == "pesanan" else "pelanggan"


async def _cari_izin(customer_id: str, entity_id: str, order_id: str, perlu_sen: int) -> Optional[Dict[str, Any]]:
    """Izin `approved` yang masih berlaku untuk pesanan ini: (1) lingkup pesanan ber-`order_id` sama; (2) izin yang sudah
    dipakai pesanan ini; (3) lingkup pelanggan bersisa ≥ nilai pesanan, yang paling cepat hangus dulu."""
    sekarang = now_iso()
    q: Dict[str, Any] = {"customer_id": customer_id, "status": "approved",
                         "$or": [{"entity_id": entity_id}, {"entity_id": {"$in": [None, ""]}}]}
    rows = [r async for r in db[COLL_OV].find(q, {"_id": 0})]
    rows = [r for r in rows if _berlaku(r, sekarang)]
    if order_id:
        for r in rows:
            if lingkup(r) == "pesanan" and r.get("order_id") == order_id and sisa_izin(r) > 0:
                return r
        for r in rows:
            if any(u.get("order_id") == order_id for u in r.get("used_by") or []):
                return {**r, "_sudah_dipakai": True}
    calon = [r for r in rows if lingkup(r) == "pelanggan" and to_cents(sisa_izin(r)) >= perlu_sen and perlu_sen > 0]
    calon.sort(key=lambda r: (str(r.get("valid_until") or "9999"), str(r.get("decided_at") or ""), r.get("id") or ""))
    return calon[0] if calon else None


async def _normalisasi_izin(ov: Dict[str, Any]) -> None:
    """Izin lama → field CR-T3 (`scope`, `remaining_amount`, `used_by`) sekali, bersyarat field belum ada."""
    if ov.get("remaining_amount") is not None and ov.get("scope"):
        return
    await db[COLL_OV].update_one({"id": ov["id"], "remaining_amount": {"$exists": False}},
                                 {"$set": {"remaining_amount": sisa_izin(ov), "scope": lingkup(ov),
                                           "used_by": list(ov.get("used_by") or [])}})
    await db[COLL_OV].update_one({"id": ov["id"], "scope": {"$exists": False}}, {"$set": {"scope": lingkup(ov)}})


async def use_override(override_id: str, order_id: str, amount: float, order_number: str = "") -> bool:
    """Pakai izin untuk satu pesanan dengan PEMBARUAN BERSYARAT (sisa cukup + belum lewat `valid_until` + belum dipakai
    pesanan ini). Dua pesanan bersamaan atas izin pelanggan Rp X: satu lolos, satu gagal; sisa tidak pernah negatif.
    Idempoten per pesanan (sudah dipakai pesanan ini → True)."""
    ov = await db[COLL_OV].find_one({"id": override_id}, {"_id": 0})
    if not ov or ov.get("status") != "approved":
        return False
    await _normalisasi_izin(ov)
    if any(u.get("order_id") == order_id for u in ov.get("used_by") or []):
        return True
    amt = round(max(0.0, float(amount or 0)), 2)
    sekarang = now_iso()
    berlaku = {"$or": [{"valid_until": {"$in": [None, ""]}}, {"valid_until": {"$exists": False}},
                       {"valid_until": {"$gt": sekarang}}]}
    jejak = {"order_id": order_id, "order_number": order_number, "amount": amt, "at": sekarang}
    if lingkup(ov) == "pesanan":
        q = {"id": override_id, "status": "approved", "order_id": order_id, "remaining_amount": {"$gt": 0},
             "used_by.order_id": {"$ne": order_id}, **berlaku}
        upd = {"$set": {"remaining_amount": 0.0, "consumed": True, "consumed_order_id": order_id,
                        "consumed_at": sekarang}, "$push": {"used_by": jejak}}
    else:
        q = {"id": override_id, "status": "approved", "remaining_amount": {"$gte": round(amt - 0.005, 3)},
             "used_by.order_id": {"$ne": order_id}, **berlaku}
        upd = {"$inc": {"remaining_amount": -amt}, "$push": {"used_by": jejak}, "$set": {"last_used_at": sekarang}}
    res = await db[COLL_OV].update_one(q, upd)
    if not res.modified_count:
        return False
    sesudah = await db[COLL_OV].find_one({"id": override_id}, {"_id": 0, "remaining_amount": 1}) or {}
    if float(sesudah.get("remaining_amount") or 0) < 0.005:   # pembulatan sen: habis = 0, tanda dipakai (jejak lama)
        await db[COLL_OV].update_one({"id": override_id}, {"$set": {
            "remaining_amount": 0.0, "consumed": True, "consumed_order_id": order_id, "consumed_at": sekarang}})
    return True


async def release_use(override_id: str, order_id: str) -> None:
    """Kembalikan pemakaian izin oleh pesanan yang GAGAL dibuat sesudah izinnya dipakai (bersyarat jejak pesanan itu)."""
    ov = await db[COLL_OV].find_one({"id": override_id}, {"_id": 0})
    jejak = next((u for u in (ov or {}).get("used_by") or [] if u.get("order_id") == order_id), None)
    if not jejak:
        return
    if lingkup(ov) == "pesanan":
        upd = {"$set": {"remaining_amount": round(float(ov.get("amount") or 0), 2), "consumed": False},
               "$pull": {"used_by": {"order_id": order_id}}, "$unset": {"consumed_order_id": "", "consumed_at": ""}}
    else:
        upd = {"$inc": {"remaining_amount": round(float(jejak.get("amount") or 0), 2)},
               "$pull": {"used_by": {"order_id": order_id}}, "$set": {"consumed": False}}
    await db[COLL_OV].update_one({"id": override_id, "used_by.order_id": order_id}, upd)


# ── Penilaian ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _kosong(checkpoint: str, customer_id: str, entity_id: str, term_code: str) -> Dict[str, Any]:
    return {"result": LOLOS, "raw_result": LOLOS, "checked": False, "checkpoint": checkpoint,
            "customer_id": customer_id, "entity_id": entity_id, "term_code": term_code, "reasons": [],
            "exposure": {}, "limit": {}, "overdue": {}, "override": None, "pay_before_ship": False,
            "counted": {}}


async def evaluate(*, customer_id: str, entity_id: str, checkpoint: str, order_id: str = "",
                   order_amount: float = 0.0, term_code: str = "", actor: Optional[Dict[str, Any]] = None,
                   order: Optional[Dict[str, Any]] = None, today: Any = None) -> Dict[str, Any]:
    """Hasil gerbang kredit `{result: lolos|peringatan|tahan|tolak, checked, reasons[{code, message, data}], exposure,
    limit, overdue, override, pay_before_ship}` (spesifikasi "Urutan dan aturan `evaluate`").

    `order_id`/`order` kosong = pesanan BARU senilai `order_amount`; terisi = pesanan yang sudah ada (bagiannya di saldo
    dipakai sebagai `this_order`). `checkpoint = "periksa_ulang"` mengabaikan sakelar titik (pesanan yang ditahan)."""
    from services import credit_profile_service as cps
    from services import customer_balance_service as cbs
    from services.book_date import tanggal_buku
    if checkpoint not in CHECKPOINTS and checkpoint != PERIKSA_ULANG:
        raise ValueError(f"Titik periksa kredit tidak dikenal: {checkpoint!r}")
    eid = entity_id or ""
    if checkpoint != PERIKSA_ULANG and not await _flag(KUNCI_TITIK[checkpoint], eid):
        return _kosong(checkpoint, customer_id, eid, term_code)              # 1. titik periksa mati untuk PT itu
    hari = tanggal_buku(today)
    if order is None and order_id:
        order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if order:
        order_id = order.get("id") or order_id
        term_code = term_code or str(order.get("payment_term_code") or "")
    eff = await cps.effective(customer_id, eid, hari)
    bal = await cbs.get(customer_id, eid, today)
    tunai_ikut = await _flag("finance.tahan_kirim_tunai", eid)
    hitung = {"open_orders": await _flag("ar.eksposur_pesanan_belum_kirim", eid),
              "giro": await _flag("ar.eksposur_giro_belum_cair", eid),
              "deposit": await _flag("ar.eksposur_titipan_mengurangi", eid), "cash_term": tunai_ikut}
    # 2. eksposur (sen bulat, `02` D5)
    ar_c = to_cents(bal.get("ar_delivered") or 0) - (0 if tunai_ikut else to_cents(bal.get("cash_term_amount") or 0))
    open_c = to_cents(bal.get("open_orders_amount") or 0) - to_cents(bal.get("cash_term_open_amount") or 0)
    giro_c = to_cents(bal.get("giro_outstanding") or 0)
    dep_c = to_cents(bal.get("deposit_balance") or 0)
    dasar = ar_c + (open_c if hitung["open_orders"] else 0) + (giro_c if hitung["giro"] else 0) \
        - (dep_c if hitung["deposit"] else 0)
    if order:   # pesanan yang sudah ada: sudah termuat di saldo pasangan → bagiannya = `this_order`
        b = await _bagian_pesanan(order, hari)
        ikut_kirim = b["kirim"] if (not b["tunai"] or tunai_ikut) else 0
        ikut_belum = b["belum"] if (hitung["open_orders"] and not b["tunai"]) else 0
        ini_c, total_c, perlu_c = ikut_kirim + ikut_belum, dasar, b["sisa"]
    else:
        ini_c = max(0, to_cents(order_amount or 0))
        total_c, perlu_c = dasar + ini_c, ini_c
    tanpa_ini_c = total_c - ini_c
    lewat_c = to_cents(bal.get("overdue_amount") or 0)
    hari_telat = int(bal.get("days_overdue") or 0)
    if tunai_ikut:
        t_c, t_tua = await _telat_tunai(customer_id, eid, hari)
        if t_c:
            from services import report_basis as rb
            lewat_c += t_c
            hari_telat = max(hari_telat, max(0, rb.hari_antara(t_tua, hari)) if t_tua and t_tua < hari else 0)
    limit = float(eff.get("credit_limit") or 0)
    limit_c = to_cents(limit)
    ratio = float(eff.get("warning_ratio") or 0)
    block_days = int(eff.get("overdue_block_days") or 0)
    # 3. alasan
    reasons: List[Dict[str, Any]] = []
    if eff.get("credit_status") == cps.STATUS_BLOKIR:
        why = (eff.get("block_reason") or "").strip()
        reasons.append(_alasan(BLOKIR_MANUAL, TAHAN, f"Pelanggan diblokir manual{': ' + why if why else ''}.",
                               block_reason=why))
    allowed = [str(x) for x in eff.get("allowed_term_codes") or [] if x]
    if term_code and allowed and term_code not in allowed:
        nama = {c: ((await _term(c, eid)) or {}).get("name") or c for c in [term_code, *allowed]}
        reasons.append(_alasan(TERMIN_TIDAK_DIIZINKAN, TOLAK,
                               f"Termin {nama[term_code]} tidak diizinkan untuk pelanggan ini. Termin yang diizinkan: "
                               f"{', '.join(nama[c] for c in allowed)}.", term_code=term_code, allowed=allowed))
    lewat_plafon = limit_c > 0 and (total_c > limit_c or tanpa_ini_c >= limit_c)
    if lewat_plafon:
        reasons.append(_alasan(LEWAT_PLAFON, TAHAN,
                               f"Eksposur {rupiah(from_cents(total_c))} melewati plafon {rupiah(limit)}.",
                               exposure=from_cents(total_c), credit_limit=limit))
    if hari_telat > block_days:
        reasons.append(_alasan(TELAT, TAHAN, f"Ada tagihan telat {hari_telat} hari (batas {block_days} hari) senilai "
                                             f"{rupiah(from_cents(lewat_c))}.",
                               days=hari_telat, block_days=block_days, amount=from_cents(lewat_c)))
    if limit_c > 0 and not lewat_plafon and total_c + 0.5 >= ratio * limit_c:
        pct = round(total_c * 100.0 / limit_c)
        reasons.append(_alasan(MENDEKATI_PLAFON, PERINGATAN, f"Eksposur sudah {pct:g} % dari plafon.", pct=pct))
    if 1 <= hari_telat <= block_days:
        reasons.append(_alasan(TELAT_RINGAN, PERINGATAN, f"Ada tagihan telat {hari_telat} hari senilai "
                                                         f"{rupiah(from_cents(lewat_c))}.",
                               days=hari_telat, amount=from_cents(lewat_c)))
    if eff.get("limit_source") == "kedaluwarsa":
        reasons.append(_alasan(PLAFON_KEDALUWARSA, INFO, f"Plafon khusus berakhir {_tgl(eff.get('limit_valid_until'))}; "
                                                         "dipakai plafon bawaan PT.",
                               valid_until=eff.get("limit_valid_until")))
    hasil = LOLOS
    for r in reasons:
        if r["result"] in _BOBOT and _BOBOT[r["result"]] > _BOBOT[hasil]:
            hasil = r["result"]
    mentah = hasil
    blokir = any(r["code"] == BLOKIR_MANUAL for r in reasons)
    izin, bayar_dulu = None, False
    if hasil == TAHAN and not blokir:
        # 4. izin kredit yang berlaku melepas tahan (bukan blokir manual, bukan tolak)
        izin = await _cari_izin(customer_id, eid, order_id, perlu_c)
        if izin:
            hasil = LOLOS
        elif checkpoint == PESANAN_DIBUAT and bayar_penuh_dulu(await _term(term_code, eid)):
            hasil, bayar_dulu = LOLOS, True                                    # 5. K-27 — bayar penuh sebelum kirim
    avail = from_cents(max(0, limit_c - total_c)) if limit_c > 0 else None
    return {
        "result": hasil, "raw_result": mentah, "checked": True, "checkpoint": checkpoint,
        "customer_id": customer_id, "entity_id": eid, "order_id": order_id, "term_code": term_code,
        "reasons": reasons,
        "exposure": {"ar_delivered": from_cents(ar_c), "open_orders": from_cents(open_c if hitung["open_orders"] else 0),
                     "giro_outstanding": from_cents(giro_c if hitung["giro"] else 0),
                     "deposit": from_cents(dep_c if hitung["deposit"] else 0), "this_order": from_cents(ini_c),
                     "total": from_cents(total_c), "without_this_order": from_cents(tanpa_ini_c)},
        "counted": hitung,
        "limit": {"credit_limit": limit, "limit_source": eff.get("limit_source"), "available": avail,
                  "warning_pct": round(ratio * 100, 2), "limit_valid_until": eff.get("limit_valid_until") or ""},
        "overdue": {"amount": from_cents(lewat_c), "days": hari_telat, "block_days": block_days},
        "override": ({k: v for k, v in izin.items() if not k.startswith("_")} if izin else None),
        "override_used_before": bool(izin and izin.get("_sudah_dipakai")),
        "override_amount_needed": from_cents(perlu_c),
        "pay_before_ship": bayar_dulu,
        "allowed_term_codes": allowed,
    }


def alasan_utama(result: Dict[str, Any]) -> str:
    """Pesan alasan pertama yang menahan/menolak (untuk pesan 409)."""
    for r in result.get("reasons") or []:
        if r.get("result") in (TAHAN, TOLAK):
            return r.get("message") or ""
    for r in result.get("reasons") or []:
        if r.get("message"):
            return r["message"]
    return ""


def ringkas(result: Dict[str, Any]) -> Dict[str, Any]:
    """Potret hasil gerbang untuk disimpan (D3 — tidak dihitung ulang)."""
    keep = ("result", "raw_result", "checked", "checkpoint", "reasons", "exposure", "limit", "overdue",
            "pay_before_ship", "term_code")
    out = {k: result.get(k) for k in keep}
    ov = result.get("override") or None
    out["override_id"] = (ov or {}).get("id", "")
    out["at"] = now_iso()
    return out


# ── Penolakan saat dibuat ───────────────────────────────────────────────────────────────────────────────────────────
async def record_rejection(*, result: Dict[str, Any], customer: Dict[str, Any], entity_id: str, actor: Dict[str, Any],
                           amount: float, term_code: str, payload_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Satu dokumen `credit_gate_rejections` (`cgr_`) per pesanan yang ditolak saat dibuat — eksposur = potret (D3)."""
    from core_utils import new_id
    doc = {"id": new_id("cgr"), "entity_id": entity_id, "customer_id": customer.get("id"),
           "customer_name": customer.get("name", ""), "actor_id": (actor or {}).get("id", ""),
           "actor_name": (actor or {}).get("name", ""), "amount": round(float(amount or 0), 2),
           "term_code": term_code or "", "result": result.get("result"),
           "reasons": [{k: r.get(k) for k in ("code", "result", "message", "data")} for r in result.get("reasons") or []],
           "exposure": dict(result.get("exposure") or {}), "limit": dict(result.get("limit") or {}),
           "overdue": dict(result.get("overdue") or {}), "payload_snapshot": payload_snapshot or {},
           "status": "terbuka", "override_id": "", "created_at": now_iso()}
    await db[COLL_REJ].insert_one(dict(doc))
    return safe_doc(doc)


async def tandai_penolakan_dilanjutkan(customer_id: str, entity_id: str, override_id: str) -> None:
    """Izin kredit disetujui → penolakan terbuka pelanggan itu di PT itu ditandai `dilanjutkan` (bisa dibuka lagi)."""
    await db[COLL_REJ].update_many({"customer_id": customer_id, "entity_id": entity_id, "status": "terbuka"},
                                   {"$set": {"status": "dilanjutkan", "override_id": override_id,
                                             "updated_at": now_iso()}})


# ── Tahan & lepas ───────────────────────────────────────────────────────────────────────────────────────────────────
def _alasan_tahan(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{k: r.get(k) for k in ("code", "result", "message")} for r in result.get("reasons") or []
            if r.get("result") in (TAHAN, TOLAK)]


async def _segarkan_tahap(order_id: str) -> Dict[str, Any]:
    from services.so_status import stage_fields
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0}) or {}
    if so:
        await db.sales_orders.update_one({"id": order_id}, {"$set": stage_fields(so)})
    return safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}) or {})


async def hold(order_id: str, result: Dict[str, Any], actor: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Tahan kredit: `credit_hold: true` + `credit_hold_info {since, checkpoint, reasons[]}` + sub-status
    `tahan_kredit`. Sudah ditahan → alasan diperbarui, `since` tetap."""
    from dependencies import audit
    now = now_iso()
    nama = (actor or {}).get("name") or "sistem"
    info = {"since": now, "checkpoint": result.get("checkpoint") or "", "reasons": _alasan_tahan(result),
            "exposure": dict(result.get("exposure") or {}), "by": nama, "by_id": (actor or {}).get("id", "")}
    res = await db.sales_orders.update_one({"id": order_id, "credit_hold": {"$ne": True}},
                                           {"$set": {"credit_hold": True, "credit_hold_info": info, "updated_at": now}})
    if not res.modified_count:
        await db.sales_orders.update_one({"id": order_id, "credit_hold": True}, {"$set": {
            "credit_hold_info.reasons": info["reasons"], "credit_hold_info.exposure": info["exposure"],
            "credit_hold_info.last_checked_at": now}})
    so = await _segarkan_tahap(order_id)
    if res.modified_count:
        await audit(nama, "so_credit_hold", "sales_order", order_id,
                    {"checkpoint": info["checkpoint"], "reasons": [r["code"] for r in info["reasons"]],
                     "exposure": info["exposure"].get("total"), "number": so.get("number", "")})
    return so.get("credit_hold_info") or info


async def release(order: Dict[str, Any], result: Dict[str, Any], actor: Optional[Dict[str, Any]], why: str) -> bool:
    """Lepas tahanan: info pindah ke `credit_hold_history` (satu baris per tahanan); bersyarat masih ditahan."""
    from dependencies import audit
    now = now_iso()
    nama = (actor or {}).get("name") or "sistem"
    info = dict(order.get("credit_hold_info") or {})
    baris = {**info, "released_at": now, "released_by": nama, "release_reason": why,
             "release_result": result.get("result"), "override_id": ((result.get("override") or {}).get("id") or "")}
    res = await db.sales_orders.update_one({"id": order["id"], "credit_hold": True}, {
        "$set": {"credit_hold": False, "credit_hold_info": None, "updated_at": now},
        "$push": {"credit_hold_history": baris}})
    if not res.modified_count:
        return False
    await _segarkan_tahap(order["id"])
    await audit(nama, "so_credit_hold_released", "sales_order", order["id"],
                {"reason": why, "result": result.get("result"), "override_id": baris["override_id"],
                 "number": order.get("number", "")})
    return True


async def _pakai_izin_bila_perlu(result: Dict[str, Any], order_id: str) -> bool:
    """Izin yang melepas tahan dipakai (bersyarat). Gagal (kalah balapan) → False."""
    ov = result.get("override")
    if not ov or result.get("override_used_before"):
        return True
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "number": 1}) or {}
    ok = await use_override(ov["id"], order_id, float(result.get("override_amount_needed") or 0), so.get("number", ""))
    if ok:
        await db.sales_orders.update_one({"id": order_id}, {"$set": {"credit_override_id": ov["id"]}})
    return ok


async def check_order(order: Dict[str, Any], checkpoint: str, actor: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Titik `lepas_gudang`/`surat_jalan`/`pesanan_diubah` untuk satu pesanan: nilai → `tahan`/`tolak` = `hold(...)`;
    lolos berkat izin = izin dipakai. → hasil `evaluate`."""
    if order.get("order_type") == "sample":
        return _kosong(checkpoint, order.get("customer_id", ""), order.get("entity_id", ""), "")
    res = await evaluate(customer_id=order.get("customer_id", ""), entity_id=order.get("entity_id", ""),
                         checkpoint=checkpoint, order=order, actor=actor)
    if res["result"] in (TAHAN, TOLAK):
        await hold(order["id"], res, actor)
    elif res.get("override") and not await _pakai_izin_bila_perlu(res, order["id"]):
        res = {**res, "result": TAHAN}
        await hold(order["id"], res, actor)
    return res


def pesan_ditahan(order: Dict[str, Any]) -> str:
    info = order.get("credit_hold_info") or {}
    alasan = next((r.get("message") for r in info.get("reasons") or [] if r.get("message")), "") \
        or "kredit pelanggan belum memenuhi syarat."
    return PESAN_DITAHAN.format(nomor=order.get("number") or order.get("id"), alasan=alasan)


async def guard_held(order_id: Optional[str]) -> None:
    """Pesanan ber-`credit_hold: true` ditolak di `confirm_core` dan `dispatch_guard` WALAU titik periksanya mati."""
    from fastapi import HTTPException
    if not order_id:
        return
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "id": 1, "number": 1, "credit_hold": 1,
                                                            "credit_hold_info": 1})
    if so and so.get("credit_hold"):
        raise HTTPException(status_code=409, detail=pesan_ditahan(so))


async def gate_checkpoint(order_id: Optional[str], checkpoint: str, actor: Optional[Dict[str, Any]] = None) -> None:
    """`confirm_core` (lepas_gudang) & `dispatch_guard` (surat_jalan): tahanan lama → 409; titik menyala & gagal →
    `hold(...)` lalu 409."""
    from fastapi import HTTPException
    if not order_id:
        return
    await guard_held(order_id)
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not so or so.get("order_type") == "sample":
        return
    res = await check_order(so, checkpoint, actor)
    if res["result"] in (TAHAN, TOLAK):
        so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0}) or so
        raise HTTPException(status_code=409, detail=pesan_ditahan(so))


async def recheck_order(order: Dict[str, Any], actor: Optional[Dict[str, Any]], why: str) -> Dict[str, Any]:
    """Periksa ulang SATU pesanan yang ditahan: lolos/peringatan (izin dipakai bila perlu) → lepas."""
    res = await evaluate(customer_id=order.get("customer_id", ""), entity_id=order.get("entity_id", ""),
                         checkpoint=PERIKSA_ULANG, order=order, actor=actor)
    released = False
    if res["result"] in (LOLOS, PERINGATAN) and await _pakai_izin_bila_perlu(res, order["id"]):
        released = await release(order, res, actor, why)
    elif res["result"] in (TAHAN, TOLAK) and order.get("credit_hold"):
        await hold(order["id"], res, actor)   # alasan diperbarui
    return {**res, "released": released}


async def recheck_holds(customer_id: str, entity_id: str, actor: Optional[Dict[str, Any]] = None,
                        why: str = "Kredit pelanggan kini memenuhi syarat") -> List[Dict[str, Any]]:
    """Periksa ulang pesanan yang DITAHAN pelanggan itu di PT itu, tertua dulu; melepas yang kini lolos.
    → daftar `{order_id, number, released, result}`. Tidak pernah melempar ke pemanggil kait."""
    if not customer_id or _SEDANG_PERIKSA.get():
        return []
    q: Dict[str, Any] = {"customer_id": customer_id, "credit_hold": True}
    if entity_id:
        q["entity_id"] = entity_id
    rows = [o async for o in db.sales_orders.find(q, {"_id": 0}).sort([("created_at", 1), ("id", 1)])]
    if not rows:
        return []
    tanda = _SEDANG_PERIKSA.set(True)
    out = []
    try:
        for o in rows:
            try:
                r = await recheck_order(o, actor, why)
                out.append({"order_id": o["id"], "number": o.get("number", ""), "released": r["released"],
                            "result": r["result"]})
            except Exception as exc:  # noqa: BLE001 — satu pesanan gagal diperiksa tidak menghentikan yang lain
                logger.warning("[CR-T3] periksa ulang kredit %s gagal: %s", o.get("id"), exc)
    finally:
        _SEDANG_PERIKSA.reset(tanda)
    return out


async def recheck_holds_safe(customer_id: str, entity_id: Optional[str] = None,
                             actor: Optional[Dict[str, Any]] = None, why: str = "") -> None:
    """Untuk kait (saldo disegarkan, izin diputus): tidak pernah melempar."""
    try:
        await recheck_holds(customer_id, entity_id or "", actor,
                            why or "Kredit pelanggan kini memenuhi syarat")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[CR-T3] periksa ulang tahanan %s/%s gagal: %s", customer_id, entity_id, exc)


async def after_order_changed(order_id: str, before_total: float, before_term: str,
                              actor: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Titik `pesanan_diubah` SESUDAH perubahan tersimpan, hanya bila nilai tagihan naik atau `net_days` termin baru lebih
    besar. Perubahan tetap berlaku; gagal = `hold(...)`. → hasil `evaluate` atau None (tidak diperiksa)."""
    from services.customer_service import _order_grand_total
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not so or so.get("order_type") == "sample":
        return None
    naik = to_cents(_order_grand_total(so)) > to_cents(before_total or 0)
    longgar = False
    if (so.get("payment_term_code") or "") != (before_term or ""):
        lama = await _term(before_term, so.get("entity_id", ""))
        baru = await _term(so.get("payment_term_code") or "", so.get("entity_id", ""))
        longgar = int((baru or {}).get("net_days") or 0) > int((lama or {}).get("net_days") or 0)
    if not (naik or longgar):
        return None
    return await check_order(so, PESANAN_DIUBAH, actor)


async def term_change_allowed(order: Dict[str, Any], new_term: str) -> None:
    """Titik `pesanan_diubah` — ganti ke termin di luar `allowed_term_codes` pelanggan ditolak (400) SEBELUM perubahan
    disimpan, bila titik periksa itu menyala untuk PT pesanan."""
    from fastapi import HTTPException
    if not new_term or not await _flag(KUNCI_TITIK[PESANAN_DIUBAH], order.get("entity_id") or ""):
        return
    from services import credit_profile_service as cps
    eff = await cps.effective(order.get("customer_id") or "", order.get("entity_id") or "")
    allowed = [str(x) for x in eff.get("allowed_term_codes") or [] if x]
    if allowed and new_term not in allowed:
        eid = order.get("entity_id") or ""
        nama = {c: ((await _term(c, eid)) or {}).get("name") or c for c in [new_term, *allowed]}
        raise HTTPException(status_code=400, detail=(
            f"Termin {nama[new_term]} tidak diizinkan untuk pelanggan ini. Termin yang diizinkan: "
            f"{', '.join(nama[c] for c in allowed)}."))
