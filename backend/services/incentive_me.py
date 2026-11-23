"""KM-T5 (keputusan K-22, K-46) — kartu **Capaian & Insentif Saya**: angka milik pelaku sendiri, satu PT, satu bulan.

`GET /api/incentive/me?period=YYYY-MM` (cukup login — Z3 milik sendiri, `login_only_endpoints.LOGIN_ONLY`). PT = PT aktif
pengguna; sales = pelaku (tidak bisa dikirim klien). Isi:

    achievement      target omzet, omzet bersih, % omzet, target pencairan, uang masuk, % pencairan, realisasi harga —
                     dari pengumpul Capaian KM-T2 (`incentive_achievement.achievement`, kolom margin tidak diminta);
                     tanpa margin, tanpa sisa piutang, tanpa angka sales lain. Persen tanpa pembagi = `None`.
    sheets           lembar insentif PT itu berstatus `approved` / `paid` dengan periode bayar = `period`, HANYA baris milik
                     pelaku (lembar `draft`, `submitted`, `approving`, `cancelled` tidak pernah dikirim) beserta potret
                     angka dasarnya (target, omzet bersih, uang masuk, realisasi harga).
    auto_commission  {mtd, projection_month_end} hanya bila sakelar PT (`hr.payroll_commission_mode`) masih komisi
                     otomatis (bukan `sheet` / `off`) — dihitung mesin lama `sales_force_service.compute_commission`.

Modul ini hanya membaca.
"""
from __future__ import annotations

from calendar import monthrange
from typing import Any, Dict, List, Optional

from db import db
from services import incentive_achievement as iach
from services import incentive_periods as ip
from services import incentive_sheet_service as iss

PESAN_PERIODE = "Periode harus satu bulan, contoh: 2026-10."
#: Angka capaian yang dikirim ke kartu (uang = rupiah bulat; persen satu desimal atau `None`).
ACH_UANG = ("target_sales", "omzet_bersih", "target_collection", "uang_masuk")
ACH_PERSEN = ("pct_omzet", "pct_pencairan", "realisasi_harga_pct")
#: Potret angka dasar per baris lembar yang boleh dilihat sales.
POTRET = ("target_sales", "omzet_bersih", "target_collection", "uang_masuk", "realisasi_harga_pct")


class KartuError(ValueError):
    """Isian kartu tidak sah (→ 400, kalimat siap tampil)."""


async def periode(entity_id: str, period: str = "") -> str:
    """`YYYY-MM`; kosong = bulan berjalan WIB (tanggal buku)."""
    p = str(period or "").strip() or await ip.current_period("month", entity_id)
    try:
        return ip.normalize("month", p)[1]
    except ip.PeriodeError:
        raise KartuError(PESAN_PERIODE)


async def capaian_saya(entity_id: str, user_id: str, period: str) -> Dict[str, Any]:
    """Satu baris Capaian milik pelaku (angka sama dengan sel tabel Capaian KM-T2 untuk sales itu)."""
    from services import incentive_definitions as idef
    from services import incentive_facts as ifacts
    synced = await ifacts.ensure_fresh(60)
    defn = await idef.current_definition(entity_id)
    if defn.get("dasar_omzet") in ("pesanan", "lunas"):
        from services import analytics_facts
        await analytics_facts.ensure_fresh(60)
    per = await iach.resolve_period(entity_id, "month", period)
    res = await iach.achievement(entity_id, per, defn, iach.saringan([user_id]), "sales", False)
    row = next((r for r in res["rows"] if r.get("sales_id") == user_id), None) or {}
    out: Dict[str, Any] = {k: int(row.get(k) or 0) for k in ACH_UANG}
    out.update({k: row.get(k) for k in ACH_PERSEN})
    out["facts_as_of"] = synced
    return out


def _baris(x: Dict[str, Any]) -> Dict[str, Any]:
    snap = x.get("snapshot") if isinstance(x.get("snapshot"), dict) else {}
    return {"component_name": x.get("component_name") or "", "basis_label": x.get("basis_label") or "",
            "amount": int(x.get("amount") or 0), "is_adjustment": bool(x.get("is_adjustment")),
            "note": x.get("note") or "", "paid_run_number": x.get("paid_run_number") or "",
            "snapshot": {k: snap.get(k) for k in POTRET}}


async def lembar_saya(entity_id: str, user_id: str, period: str) -> List[Dict[str, Any]]:
    """Lembar disahkan PT itu dengan periode bayar `period` — hanya baris milik pelaku."""
    out: List[Dict[str, Any]] = []
    q = {"entity_id": entity_id, "pay_period": period, "status": {"$in": list(iss.DISAHKAN)},
         "lines.sales_id": user_id}
    async for s in db[iss.COLL].find(q, {"_id": 0, "number": 1, "pay_period": 1, "status": 1, "lines": 1}).sort(
            "number", 1):
        lines = [_baris(x) for x in s.get("lines") or [] if x.get("sales_id") == user_id]
        if lines:
            out.append({"sheet_number": s.get("number") or "", "pay_period": s.get("pay_period") or "",
                        "status": s.get("status"), "lines": lines})
    return out


# Daftar putih rincian komisi untuk sales: tanpa angka margin/HPP (jangan menyalin baris mesin apa adanya).
KUNCI_RINCIAN = ("name", "sku", "qty_base", "unit", "rate", "rate_origin", "price_factor", "price_reason_label",
                 "achievement_factor", "capped", "commission")


async def komisi_otomatis(entity_id: str, user_id: str, period: str, mode: str) -> Optional[Dict[str, Any]]:
    """Komisi berjalan mesin lama — hanya untuk PT yang masih bermode komisi otomatis."""
    from services import incentive_payroll as ipay
    if mode in ipay.TANPA_MESIN:
        return None
    from services import sales_force_service as sf
    from services.book_date import tanggal_buku
    hasil = await sf.compute_commission(user_id, period, entity_id)
    total = round(float(hasil["total_incentive"] or 0), 2)
    hari_ini = tanggal_buku()
    if hari_ini[:7] == period:
        day, dim = int(hari_ini[8:10]), monthrange(int(period[:4]), int(period[5:7]))[1]
        proyeksi = round(total / day * dim, 2) if day else total
    else:
        proyeksi = total
    return {"mtd": total, "projection_month_end": proyeksi,
            "breakdown": [{k: r.get(k) for k in KUNCI_RINCIAN} for r in hasil.get("breakdown") or []]}


async def kartu(entity_id: str, user_id: str, period: str = "") -> Dict[str, Any]:
    from services import incentive_payroll as ipay
    p = await periode(entity_id, period)
    mode = await ipay.mode_pt(entity_id)
    return {"period": p, "entity_id": entity_id, "mode": mode,
            "achievement": await capaian_saya(entity_id, user_id, p),
            "sheets": await lembar_saya(entity_id, user_id, p),
            "auto_commission": await komisi_otomatis(entity_id, user_id, p, mode)}
