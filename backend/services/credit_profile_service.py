"""CR-T1 — profil kredit per pelanggan per PT, diubah HANYA lewat pengajuan (`docs/blueprint/unit/CR-T1.md`, K-27–K-29).

Plafon, berlaku-sampai, termin yang diizinkan, hari telat yang menahan pesanan, dan status blokir seorang pelanggan
disimpan terpisah dari data pelanggan, SATU dokumen per (pelanggan, PT PESANAN) di `customer_credit_profiles`. Tidak ada
dokumen = semua nilai ikut bawaan PT (`ar.default_credit_limit`, dan ambang KF-T7 `ar.overdue_block_days` /
`ar.credit_warning_pct` lewat `customer_service.credit_thresholds`).

Profil berubah hanya lewat dokumen pengajuan `credit_profile_requests` (`diajukan` → `disetujui` · `ditolak` ·
`dibatalkan`) yang diputus pemegang `credit_profile.approve`; pengaju ≠ pemutus bila `kontrol.ubah_profil_kredit.*`
(KF-T6, bawaan satu orang) memintanya. Satu pengajuan terbuka per (pelanggan, PT) — indeks unik parsial.

Fungsi inti:
  effective(customer_id, entity_id, today)   nilai yang DIPAKAI mesin beserta asalnya (L6)
  status_from(effective, piutang, telat)      SATU-SATUNYA penentu active · warning · blocked
  submit(...) / decide(...) / cancel(...)     alur pengajuan

Masa peralihan (RISIKO unit): selama skrip `scripts/migrate_credit_profiles.py --terapkan` belum dijalankan (penanda
`system_settings{scope:"__migrations__"}.crt1_profil_kredit`), pelanggan yang BELUM punya profil di PT pemilik datanya
dibaca dari `customers.credit_limit` / `customers.status == "blocked"` (asal `data_lama`) — nilai yang sama persis
dengan yang akan ditulis skrip. Cadangan ini dihapus di CR-T3.
"""
from __future__ import annotations

import logging
import math
import re
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import new_id, now_iso, safe_doc
from db import db

logger = logging.getLogger(__name__)

COLL = "customer_credit_profiles"
COLL_REQ = "credit_profile_requests"
AKSI = "ubah_profil_kredit"
PENANDA_MIGRASI = "crt1_profil_kredit"

MODE_IKUT, MODE_KHUSUS, MODE_TANPA = "ikut_pt", "khusus", "tanpa_batas"
LIMIT_MODES = (MODE_IKUT, MODE_KHUSUS, MODE_TANPA)
STATUS_NORMAL, STATUS_BLOKIR = "normal", "blokir_manual"
CREDIT_STATUSES = (STATUS_NORMAL, STATUS_BLOKIR)
PENALTY_MODES = ("ikut_pt", "khusus", "bebas")

ST_DIAJUKAN, ST_DISETUJUI, ST_DITOLAK, ST_DIBATALKAN = "diajukan", "disetujui", "ditolak", "dibatalkan"
ST_DIPUTUS = (ST_DISETUJUI, ST_DITOLAK)

#: Isian profil yang boleh diajukan, dengan label untuk manusia (pesan galat & riwayat — L1).
LABEL: Dict[str, str] = {
    "limit_mode": "Jenis plafon", "credit_limit": "Plafon kredit", "limit_valid_until": "Berlaku sampai",
    "allowed_term_codes": "Termin yang diizinkan", "default_term_code": "Termin bawaan",
    "overdue_block_days": "Tahan pesanan bila telat lebih dari", "credit_status": "Status kredit",
    "block_reason": "Alasan blokir", "penalty_rule": "Aturan denda", "credit_group_id": "Kelompok kredit",
}
FIELDS: Tuple[str, ...] = tuple(LABEL)
#: Nilai profil baru (= ikut PT seluruhnya).
DASAR: Dict[str, Any] = {"limit_mode": MODE_IKUT, "credit_limit": None, "limit_valid_until": "",
                         "allowed_term_codes": [], "default_term_code": "", "overdue_block_days": None,
                         "credit_status": STATUS_NORMAL, "block_reason": "", "penalty_rule": None,
                         "credit_group_id": ""}

PESAN_TERBUKA = "Masih ada pengajuan perubahan kredit yang menunggu keputusan untuk pelanggan ini."
PESAN_DIPUTUS = "Pengajuan ini sudah diputus."
PESAN_BERUBAH = "Profil kredit sudah berubah sejak pengajuan dibuat. Buat pengajuan baru."
PESAN_ALASAN = "Alasan pengajuan wajib diisi (minimal {n} huruf)."
ALASAN_DATA_LAMA = "Dipindahkan dari status pelanggan"
ALASAN_DARI_BUAT = "Plafon diusulkan saat pelanggan dibuat"
_TGL = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Galat(HTTPException):
    """HTTPException berkalimat (router meneruskan apa adanya)."""

    def __init__(self, status: int, pesan: str) -> None:
        super().__init__(status_code=status, detail=pesan)


def _tak_sah(field: str, sebab: str) -> Galat:
    return Galat(400, f"Isian tidak sah: {LABEL.get(field, field)} — {sebab}.")


def hari_ini() -> str:
    """Tanggal WIB hari ini (D6 — satu fungsi tanggal buku)."""
    from services.book_date import tanggal_buku
    return tanggal_buku()


# ── Pembacaan bersama (cache per panggilan daftar) ──────────────────────────────────────────────────────────────────
def cache_baru() -> Dict[str, Any]:
    """Cache satu panggilan daftar: ambang & plafon bawaan per PT, profil per (pelanggan, PT), penanda migrasi."""
    return {"thr": {}, "bawaan": {}, "prof": {}, "prof_dimuat": set(), "migrasi": None}


async def muat_profil(cache: Dict[str, Any], customer_ids: Iterable[str]) -> None:
    """Muat semua profil pelanggan `customer_ids` (semua PT) dalam SATU kueri ke `cache` (pemanggil daftar)."""
    ids = [c for c in {str(c) for c in customer_ids if c} if c not in cache["prof_dimuat"]]
    if not ids:
        return
    async for p in db[COLL].find({"customer_id": {"$in": ids}}, {"_id": 0}):
        cache["prof"][(p["customer_id"], p.get("entity_id") or "")] = p
    cache["prof_dimuat"].update(ids)


async def _profil(customer_id: str, entity_id: str, cache: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if cache is not None and customer_id in cache["prof_dimuat"]:
        return cache["prof"].get((customer_id, entity_id))
    return await db[COLL].find_one({"customer_id": customer_id, "entity_id": entity_id}, {"_id": 0})


async def sudah_migrasi(cache: Optional[Dict[str, Any]] = None) -> bool:
    """Penanda skrip `migrate_credit_profiles.py --terapkan` sudah selesai (cadangan `data_lama` mati)."""
    if cache is not None and cache.get("migrasi") is not None:
        return cache["migrasi"]
    doc = await db.system_settings.find_one({"scope": "__migrations__"}, {"_id": 0, PENANDA_MIGRASI: 1}) or {}
    hasil = bool(doc.get(PENANDA_MIGRASI))
    if cache is not None:
        cache["migrasi"] = hasil
    return hasil


def _angka(v: Any) -> float:
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        return 0.0
    return f if math.isfinite(f) else 0.0


def profil_data_lama(customer: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Isi profil yang AKAN ditulis migrasi untuk pelanggan lama (tabel "Migrasi" unit), atau None bila tidak ada.

    `credit_limit > 0` → plafon khusus sama; `status == "blocked"` → blokir manual beralasan "Dipindahkan dari status
    pelanggan". Plafon 0/kosong dan tidak diblokir → tidak ada profil (ikut PT)."""
    if not customer:
        return None
    limit = _angka(customer.get("credit_limit"))
    blocked = customer.get("status") == "blocked"
    if limit <= 0 and not blocked:
        return None
    out = dict(DASAR)
    if limit > 0:
        out.update(limit_mode=MODE_KHUSUS, credit_limit=round(limit, 2))
    if blocked:
        out.update(credit_status=STATUS_BLOKIR, block_reason=ALASAN_DATA_LAMA)
    return out


async def _pelanggan(customer_id: str, customer: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Dokumen pelanggan dari pemanggil bila memuat field yang dibutuhkan (proyeksi daftar), selain itu dibaca."""
    if customer is not None and all(k in customer for k in ("entity_id", "status")):
        return customer
    return await db.customers.find_one({"id": customer_id}, {"_id": 0, "id": 1, "entity_id": 1, "credit_limit": 1,
                                                              "status": 1, "name": 1})


async def profil_dasar(customer_id: str, entity_id: str, *, customer: Optional[Dict[str, Any]] = None,
                       cache: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], bool]:
    """(profil yang berlaku sebagai DASAR perubahan, apakah dari data lama). Tersimpan menang; tanpa profil dan sebelum
    migrasi → data lama pelanggan di PT pemilik datanya; selain itu None (ikut PT)."""
    prof = await _profil(customer_id, entity_id, cache)
    if prof:
        return prof, False
    if await sudah_migrasi(cache):
        return None, False
    cust = await _pelanggan(customer_id, customer)
    if cust and (cust.get("entity_id") or "") == entity_id:
        lama = profil_data_lama(cust)
        if lama:
            return lama, True
    return None, False


# ── Nilai yang dipakai mesin ────────────────────────────────────────────────────────────────────────────────────────
async def effective(customer_id: str, entity_id: str, today: Optional[str] = None, *,
                    customer: Optional[Dict[str, Any]] = None,
                    cache: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Nilai profil kredit yang DIPAKAI mesin untuk (pelanggan, PT) beserta asalnya.

    `credit_limit` (0 = tanpa batas) + `limit_source`: `khusus` (plafon profil) · `bawaan_pt` (`ar.default_credit_limit`)
    · `tanpa_batas` (pilihan tersendiri) · `kedaluwarsa` (plafon khusus lewat `limit_valid_until` → bawaan PT) ·
    `data_lama` (masa peralihan, lihat kepala modul). `overdue_block_days` + `block_days_source` (`khusus` ·
    `bawaan_pt`), `warning_ratio` (KF-T7), `allowed_term_codes`, `default_term_code`, `credit_status`, `block_reason`,
    `limit_valid_until`."""
    from services.customer_service import credit_thresholds
    eid = entity_id if entity_id and entity_id != "all" else ""
    if not eid:
        cust = await _pelanggan(customer_id, customer)
        eid = (cust or {}).get("entity_id") or ""
    tgl = today or hari_ini()
    thr = await credit_thresholds(eid, cache["thr"] if cache is not None else None)
    if cache is not None and eid in cache["bawaan"]:
        bawaan = cache["bawaan"][eid]
    else:   # plafon bawaan PT (0 = tanpa batas); galat baca = bawaan registry (`nilai_pengaturan`)
        from services.nilai_pengaturan import nilai
        bawaan = _angka(await nilai("ar.default_credit_limit", eid))
        if cache is not None:
            cache["bawaan"][eid] = bawaan
    prof, lama = await profil_dasar(customer_id, eid, customer=customer, cache=cache)
    p = {**DASAR, **(prof or {})}
    mode = p.get("limit_mode") or MODE_IKUT
    valid = str(p.get("limit_valid_until") or "")
    if mode == MODE_TANPA:
        limit, src = 0.0, "tanpa_batas"
    elif mode == MODE_KHUSUS and p.get("credit_limit") is not None:
        if valid and valid < tgl:
            limit, src = bawaan, "kedaluwarsa"
        else:
            limit, src = round(_angka(p.get("credit_limit")), 2), ("data_lama" if lama else "khusus")
    else:
        limit, src = bawaan, "bawaan_pt"
    if p.get("overdue_block_days") is not None:
        block_days, block_src = int(p["overdue_block_days"]), ("data_lama" if lama else "khusus")
    else:
        block_days, block_src = int(thr["block_days"]), "bawaan_pt"
    status = p.get("credit_status") or STATUS_NORMAL
    return {
        "customer_id": customer_id, "entity_id": eid,
        "credit_limit": limit, "limit_source": src, "limit_mode": mode, "limit_valid_until": valid,
        "khusus_credit_limit": (round(_angka(p.get("credit_limit")), 2) if p.get("credit_limit") is not None
                                else None),
        "default_credit_limit": bawaan,
        "overdue_block_days": block_days, "block_days_source": block_src,
        "default_overdue_block_days": int(thr["block_days"]),
        "warning_ratio": thr["warning_ratio"],
        "allowed_term_codes": list(p.get("allowed_term_codes") or []),
        "default_term_code": p.get("default_term_code") or "",
        "credit_status": status, "status_source": ("data_lama" if lama and status == STATUS_BLOKIR else
                                                  ("khusus" if status == STATUS_BLOKIR else "bawaan_pt")),
        "block_reason": p.get("block_reason") or "",
        "penalty_rule": p.get("penalty_rule"), "credit_group_id": p.get("credit_group_id") or "",
        "has_profile": bool(prof) and not lama, "data_lama": lama,
        "version": int((prof or {}).get("version") or 0) if not lama else 0,
    }


def status_from(effective: Dict[str, Any], ar_outstanding: float, max_overdue_days: int) -> str:
    """SATU-SATUNYA penentu status kredit `active · warning · blocked` (kartu pelanggan, umur piutang, pemeriksaan kredit
    pesanan, beranda). Aturan sama dengan sebelum unit ini: `warning` bila piutang ≥ rasio × plafon atau telat ≥ 1
    hari; `blocked` bila piutang ≥ plafon, telat > hari blokir, atau blokir manual. Plafon 0 = tanpa batas."""
    limit = _angka(effective.get("credit_limit"))
    ar = _angka(ar_outstanding)
    telat = int(max_overdue_days or 0)
    status = "active"
    if (limit > 0 and ar >= float(effective.get("warning_ratio") or 0) * limit) or telat > 0:
        status = "warning"
    if (limit > 0 and ar >= limit) or telat > int(effective.get("overdue_block_days") or 0):
        status = "blocked"
    if effective.get("credit_status") == STATUS_BLOKIR:
        status = "blocked"
    return status


# ── Pemeriksaan isian ───────────────────────────────────────────────────────────────────────────────────────────────
async def term_options(entity_id: str) -> List[Dict[str, Any]]:
    """Termin pembayaran AKTIF untuk PT itu (master berlapis `payment-terms`)."""
    from services import entity_master_service as ems
    rows = await ems.effective_rows("payment-terms", entity_id)
    return [{"code": r.get("code"), "name": r.get("name") or r.get("code"), "net_days": r.get("net_days"),
             "type": r.get("type") or ""} for r in rows if r.get("code")]


def _angka_sah(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _tanggal(field: str, v: Any, today: str) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    if not _TGL.match(s):
        raise _tak_sah(field, "tanggal harus berbentuk TTTT-BB-HH")
    try:
        date.fromisoformat(s)
    except ValueError:
        raise _tak_sah(field, "tanggal tidak dikenal") from None
    if s < today:
        raise _tak_sah(field, "tanggal sudah lewat")
    return s


PESAN_BEBAS_DENDA = "Bebas denda wajib beralasan dan punya tanggal berakhir."


def pesan_tarif_denda() -> str:
    """Galat tarif denda di luar batas registry `ar.denda_rate_pct_per_month` (0–100 % per bulan)."""
    import config_registry as registry
    e = registry.require("ar.denda_rate_pct_per_month")
    return f"Tarif denda harus antara {e['min']:g} dan {e['max']:g} % per bulan."


def _aturan_denda(v: Any, today: str) -> Optional[Dict[str, Any]]:
    """CR-T4 — `penalty_rule` dibaca mesin denda (`penalty_service.penalty_policy`), diperiksa menurut tabel Data unit:

    * `ikut_pt` (atau kosong) → None (tanpa aturan khusus);
    * `khusus` → `rate_pct_per_month` / `cap_pct` 0–100, `grace_days` bulat 0–batas `ar.grace_days`, `base` dari pilihan
      `payment.penalty_base`; `null` = ikut PT untuk unsur itu;
    * `bebas` → alasan ≥ 5 huruf DAN `valid_until` (≥ hari ini) wajib — tidak ada bebas selamanya."""
    if v is None:
        return None
    if not isinstance(v, dict):
        raise _tak_sah("penalty_rule", "harus berupa aturan")
    import config_registry as registry
    from input_rules import MIN_REASON_LETTERS, count_letters
    mode = str(v.get("mode") or MODE_IKUT)
    if mode not in PENALTY_MODES:
        raise _tak_sah("penalty_rule", "pilihan aturan denda tidak dikenal")
    if mode == MODE_IKUT:
        return None
    out: Dict[str, Any] = {"mode": mode, "rate_pct_per_month": None, "cap_pct": None, "grace_days": None, "base": "",
                           "reason": str(v.get("reason") or "").strip()[:500], "valid_until": ""}
    if mode == "bebas":
        if count_letters(out["reason"]) < MIN_REASON_LETTERS or not str(v.get("valid_until") or "").strip():
            raise Galat(400, PESAN_BEBAS_DENDA)
        out["valid_until"] = _tanggal("penalty_rule", v.get("valid_until"), today)
        return out
    for k, kunci in (("rate_pct_per_month", "ar.denda_rate_pct_per_month"), ("cap_pct", "payment.penalty_cap_pct")):
        x = v.get(k)
        if x in (None, ""):
            continue
        e = registry.require(kunci)
        if not _angka_sah(x) or not float(e["min"]) <= x <= float(e["max"]):
            raise Galat(400, pesan_tarif_denda() if k == "rate_pct_per_month" else
                        f"Batas atas denda harus antara {e['min']:g} dan {e['max']:g} % dari dasar.")
        out[k] = float(x)
    g = v.get("grace_days")
    if g not in (None, ""):
        maks = int(registry.require("ar.grace_days")["max"])
        if not isinstance(g, int) or isinstance(g, bool) or not 0 <= g <= maks:
            raise _tak_sah("penalty_rule", f"hari tenggang harus bilangan bulat 0–{maks}")
        out["grace_days"] = g
    base = v.get("base")
    dasar_sah = {o["value"] for o in (registry.require("payment.penalty_base").get("options") or [])}
    if base not in (None, "") and base not in dasar_sah:
        raise _tak_sah("penalty_rule", "dasar denda tidak dikenal")
    out["base"] = base or ""
    return out


async def periksa_perubahan(changes: Dict[str, Any], dasar: Optional[Dict[str, Any]], entity_id: str,
                            today: Optional[str] = None) -> Dict[str, Any]:
    """Bersihkan & periksa `changes` (`{isian: nilai baru}`) terhadap profil dasar. Galat → 400 berkalimat.
    Jawaban: isian yang benar-benar berubah (sudah bersih)."""
    import config_registry as registry
    from input_rules import MIN_REASON_LETTERS, count_letters
    if not isinstance(changes, dict) or not changes:
        raise Galat(400, "Isi perubahan profil kredit yang diajukan.")
    tgl = today or hari_ini()
    bersih: Dict[str, Any] = {}
    for f, v in changes.items():
        if f not in LABEL:
            raise Galat(400, f"Isian tidak sah: {f} — tidak dikenal.")
        if f == "limit_mode":
            if v not in LIMIT_MODES:
                raise _tak_sah(f, "pilihan tidak dikenal")
            bersih[f] = v
        elif f == "credit_limit":
            if v is None:
                bersih[f] = None
            elif not _angka_sah(v) or v < 0:
                raise _tak_sah(f, "harus angka nol atau lebih")
            else:
                maks = float(registry.require("ar.default_credit_limit")["max"])
                if v > maks:
                    raise _tak_sah(f, "melebihi batas atas plafon")
                bersih[f] = round(float(v), 2)
        elif f == "limit_valid_until":
            bersih[f] = _tanggal(f, v, tgl)
        elif f == "allowed_term_codes":
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise _tak_sah(f, "harus daftar kode termin")
            bersih[f] = list(dict.fromkeys(x.strip() for x in v if x.strip()))
        elif f == "default_term_code":
            if v is not None and not isinstance(v, str):
                raise _tak_sah(f, "harus kode termin")
            bersih[f] = (v or "").strip()
        elif f == "overdue_block_days":
            if v is None:
                bersih[f] = None
            elif not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise _tak_sah(f, "harus bilangan bulat nol atau lebih")
            elif v > int(registry.require("ar.overdue_block_days")["max"]):
                raise _tak_sah(f, f"paling banyak {int(registry.require('ar.overdue_block_days')['max'])} hari")
            else:
                bersih[f] = v
        elif f == "credit_status":
            if v not in CREDIT_STATUSES:
                raise _tak_sah(f, "pilihan tidak dikenal")
            bersih[f] = v
        elif f == "block_reason":
            bersih[f] = str(v or "").strip()[:500]
        elif f == "penalty_rule":
            bersih[f] = _aturan_denda(v, tgl)
        elif f == "credit_group_id":
            bersih[f] = str(v or "").strip()[:80]
    sesudah = {**DASAR, **(dasar or {}), **bersih}
    if sesudah["limit_mode"] == MODE_KHUSUS and sesudah.get("credit_limit") is None:
        raise _tak_sah("credit_limit", "wajib diisi untuk plafon khusus")
    kode = {t["code"] for t in await term_options(entity_id)}
    for c in bersih.get("allowed_term_codes") or []:
        if c not in kode:
            raise _tak_sah("allowed_term_codes", f"kode termin tidak dikenal: {c}")
    dft = sesudah.get("default_term_code") or ""
    if "default_term_code" in bersih and dft and dft not in kode:
        raise _tak_sah("default_term_code", f"kode termin tidak dikenal: {dft}")
    if dft and sesudah.get("allowed_term_codes") and dft not in sesudah["allowed_term_codes"]:
        raise _tak_sah("default_term_code", "harus salah satu termin yang diizinkan")
    if sesudah["credit_status"] == STATUS_BLOKIR and count_letters(sesudah.get("block_reason")) < MIN_REASON_LETTERS:
        raise _tak_sah("block_reason", f"wajib diisi minimal {MIN_REASON_LETTERS} huruf saat pelanggan diblokir")
    if sesudah["credit_status"] == STATUS_NORMAL and "credit_status" in bersih and "block_reason" not in bersih:
        bersih["block_reason"] = ""   # buka blokir → alasan blokir lama tidak terbawa
    lama = {**DASAR, **(dasar or {})}
    return {f: v for f, v in bersih.items() if v != lama.get(f)}


def _dari(dasar: Optional[Dict[str, Any]], field: str) -> Any:
    """Nilai TERSIMPAN saat diajukan (None bila belum ada profil)."""
    return None if dasar is None else dasar.get(field, DASAR.get(field))


def nominal_dari(req_or_changes: Any) -> float:
    """`nominal` kontrol dua orang = plafon BARU (ASUMSI unit), 0 bila pengajuan tidak mengubah plafon."""
    changes = req_or_changes.get("changes") if isinstance(req_or_changes, dict) and "changes" in req_or_changes \
        else req_or_changes
    for c in changes or []:
        if c.get("field") == "credit_limit":
            return _angka(c.get("to"))
    return 0.0


def label_changes(changes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{**c, "label": LABEL.get(c.get("field"), c.get("field"))} for c in changes or []]


async def _nama_pt(entity_id: str) -> Dict[str, str]:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "short_name": 1, "legal_name": 1,
                                                                 "name": 1}) or {}
    return {"id": entity_id, "short_name": e.get("short_name") or e.get("name") or "",
            "legal_name": e.get("legal_name") or e.get("name") or ""}


# ── Pengajuan ───────────────────────────────────────────────────────────────────────────────────────────────────────
async def pengajuan_terbuka(customer_id: str, entity_id: str) -> Optional[Dict[str, Any]]:
    return await db[COLL_REQ].find_one({"customer_id": customer_id, "entity_id": entity_id, "status": ST_DIAJUKAN},
                                       {"_id": 0})


async def submit(customer: Dict[str, Any], entity_id: str, changes: Dict[str, Any], reason: str,
                 attachment_url: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Validasi, tolak bila sudah ada pengajuan `diajukan` (409), simpan pengajuan + potret kredit (D3)."""
    from input_rules import MIN_REASON_LETTERS, count_letters
    from pymongo.errors import DuplicateKeyError
    if customer.get("status") == "merged":   # P18 MASTER-05 — duplikat yang sudah digabung tidak dihidupkan lagi
        raise Galat(409, "Pelanggan ini sudah digabung ke pelanggan lain — ajukan perubahan kredit di pelanggan "
                         "hasil gabungan.")
    alasan = str(reason or "").strip()
    if count_letters(alasan) < MIN_REASON_LETTERS:
        raise Galat(400, PESAN_ALASAN.format(n=MIN_REASON_LETTERS))
    cid = customer["id"]
    if await pengajuan_terbuka(cid, entity_id):
        raise Galat(409, PESAN_TERBUKA)
    dasar, _lama = await profil_dasar(cid, entity_id, customer=customer)
    bersih = await periksa_perubahan(changes, dasar, entity_id)
    if not bersih:
        raise Galat(400, "Tidak ada perubahan: nilai yang diajukan sama dengan profil kredit sekarang.")
    from services.customer_service import compute_customer_credit
    snapshot = await compute_customer_credit(customer, entity_id)
    from core_utils import next_doc_number
    doc = {
        "id": new_id("cpr"),
        "number": await next_doc_number(COLL_REQ, "number", "PKR-", entity_id=entity_id),
        "customer_id": cid, "customer_name": customer.get("name", ""), "entity_id": entity_id,
        "changes": [{"field": f, "from": _dari(dasar, f), "to": v} for f, v in bersih.items()],
        "base_version": int((dasar or {}).get("version") or 0),
        "reason": alasan[:1000], "attachment_url": str(attachment_url or "").strip()[:500],
        "credit_snapshot": snapshot, "status": ST_DIAJUKAN,
        "requested_by": actor.get("name", ""), "requested_by_id": actor.get("id", ""), "created_at": now_iso(),
        "decided_by": "", "decided_by_id": "", "decided_at": "", "decision_note": "",
    }
    try:
        await db[COLL_REQ].insert_one(dict(doc))
    except DuplicateKeyError:   # indeks unik parsial: satu pengajuan terbuka per (pelanggan, PT)
        raise Galat(409, PESAN_TERBUKA) from None
    if await db[COLL_REQ].count_documents({"customer_id": cid, "entity_id": entity_id, "status": ST_DIAJUKAN}) > 1:
        # Database tanpa indeks parsial (tiruan): yang terbaru mengalah — tetap satu pengajuan terbuka.
        first = await db[COLL_REQ].find_one({"customer_id": cid, "entity_id": entity_id, "status": ST_DIAJUKAN},
                                            {"_id": 0, "id": 1}, sort=[("created_at", 1), ("id", 1)])
        if first and first["id"] != doc["id"]:
            await db[COLL_REQ].delete_one({"id": doc["id"], "status": ST_DIAJUKAN})
            raise Galat(409, PESAN_TERBUKA)
    from dependencies import audit
    await audit(actor.get("name", ""), "credit_profile_requested", "customer", cid,
                {"request_id": doc["id"], "number": doc["number"], "entity_id": entity_id,
                 "changes": doc["changes"]}, reason=alasan[:1000], scope_entity_id=entity_id)
    return safe_doc(doc)


async def _tulis_profil(req: Dict[str, Any], dasar: Optional[Dict[str, Any]], lama: bool,
                        actor: Dict[str, Any]) -> Dict[str, Any]:
    """Terapkan perubahan pengajuan dengan syarat `version` yang dibaca saat pemeriksaan `from` (tulis bersyarat):
    profil tersimpan → `$set` bersyarat versi itu; belum ada (atau dasar dari data lama) → sisip, indeks unik
    (pelanggan, PT) menolak kembaran. Gagal syarat → 409."""
    from pymongo import ReturnDocument
    from pymongo.errors import DuplicateKeyError
    cid, eid = req["customer_id"], req["entity_id"]
    baru = {c["field"]: c["to"] for c in req.get("changes") or []}
    jejak = {"updated_at": now_iso(), "updated_by": actor.get("name", ""), "updated_by_id": actor.get("id", ""),
             "last_request_id": req["id"]}
    if dasar and not lama:
        res = await db[COLL].find_one_and_update(
            {"customer_id": cid, "entity_id": eid, "version": int(dasar.get("version") or 0)},
            {"$set": {**baru, **jejak}, "$inc": {"version": 1}}, projection={"_id": 0},
            return_document=ReturnDocument.AFTER)
        if not res:
            raise Galat(409, PESAN_BERUBAH)
        return res
    doc = {"id": new_id("ccp"), "customer_id": cid, "entity_id": eid, **DASAR, **(dasar or {}), **baru, **jejak,
           "version": 1, "created_at": now_iso()}
    doc.pop("_id", None)
    try:
        await db[COLL].insert_one(dict(doc))
    except DuplicateKeyError:   # indeks unik (pelanggan, PT): profil lahir bersamaan dari jalur lain
        raise Galat(409, PESAN_BERUBAH) from None
    return safe_doc(doc)


async def _batal_otomatis(req: Dict[str, Any], catatan: str) -> None:
    await db[COLL_REQ].update_one({"id": req["id"], "status": ST_DIAJUKAN},
                                  {"$set": {"status": ST_DIBATALKAN, "decision_note": catatan,
                                            "decided_by": "Sistem", "decided_by_id": "", "decided_at": now_iso()}})


async def decide(request_id: str, decision: str, note: str, actor: Dict[str, Any], *,
                 request: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Putuskan pengajuan. Urutan (spesifikasi): status `diajukan` → `tolak_bila_pelaku_sama("ubah_profil_kredit", …)`
    (403 bila wajib orang kedua dan pemutus = pengaju) → setuju: tulis profil bersyarat `version` → tandai pengajuan →
    jejak audit. Tolak: catatan wajib. Jawaban: `{request, effective}`."""
    from services.dual_control import tolak_bila_pelaku_sama
    req = request or await db[COLL_REQ].find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise Galat(404, "Pengajuan perubahan kredit tidak ditemukan.")
    if decision not in ("approve", "reject"):
        raise Galat(400, "Keputusan harus setujui atau tolak.")
    if req.get("status") != ST_DIAJUKAN:
        raise Galat(409, PESAN_DIPUTUS)
    eid, cid = req.get("entity_id") or "", req["customer_id"]
    await tolak_bila_pelaku_sama("ubah_profil_kredit", req, actor, eid, nominal=nominal_dari(req),
                                 pengaju=[req.get("requested_by_id")])
    catatan = str(note or "").strip()[:1000]
    putus = {"decided_by": actor.get("name", ""), "decided_by_id": actor.get("id", ""), "decided_at": now_iso(),
             "decision_note": catatan}
    from dependencies import audit
    if decision == "reject":
        if not catatan:
            raise Galat(400, "Alasan penolakan wajib diisi.")
        res = await db[COLL_REQ].find_one_and_update({"id": req["id"], "status": ST_DIAJUKAN},
                                                     {"$set": {"status": ST_DITOLAK, **putus}},
                                                     projection={"_id": 0}, return_document=True)
        if not res:
            raise Galat(409, PESAN_DIPUTUS)
        await audit(actor.get("name", ""), "credit_profile_request_rejected", "customer", cid,
                    {"request_id": req["id"], "number": req.get("number")}, reason=catatan, scope_entity_id=eid)
        return {"request": safe_doc(res), "effective": await effective(cid, eid)}
    customer = await db.customers.find_one({"id": cid}, {"_id": 0})
    dasar, _lama = await profil_dasar(cid, eid, customer=customer)
    for c in req.get("changes") or []:
        if _dari(dasar, c["field"]) != c.get("from"):
            await _batal_otomatis(req, "Dibatalkan otomatis: profil kredit berubah sejak pengajuan dibuat.")
            raise Galat(409, PESAN_BERUBAH)
    sebelum = {c["field"]: _dari(dasar, c["field"]) for c in req.get("changes") or []}
    stored_before = None if _lama else dasar
    try:
        prof = await _tulis_profil(req, dasar, _lama, actor)
    except Galat:
        await _batal_otomatis(req, "Dibatalkan otomatis: profil kredit berubah sejak pengajuan dibuat.")
        raise
    res = await db[COLL_REQ].find_one_and_update({"id": req["id"], "status": ST_DIAJUKAN},
                                                 {"$set": {"status": ST_DISETUJUI, **putus,
                                                           "profile_version": int(prof.get("version") or 0)}},
                                                 projection={"_id": 0}, return_document=True)
    if not res:
        # Pengajuan diputus/dibatalkan orang lain di sela-sela: profil dikembalikan (bersyarat versi baru).
        if stored_before:
            await db[COLL].update_one({"customer_id": cid, "entity_id": eid, "version": prof["version"]},
                                      {"$set": {k: stored_before.get(k) for k in FIELDS},
                                       "$inc": {"version": 1}})
        else:
            await db[COLL].delete_one({"customer_id": cid, "entity_id": eid, "version": prof["version"]})
        raise Galat(409, PESAN_DIPUTUS)
    await audit(actor.get("name", ""), "credit_profile_changed", "customer", cid,
                {"request_id": req["id"], "number": req.get("number"), "entity_id": eid,
                 **{c["field"]: c["to"] for c in req.get("changes") or []}},
                reason=str(req.get("reason") or "")[:1000], before=sebelum, scope_entity_id=eid)
    return {"request": safe_doc(res), "effective": await effective(cid, eid)}


async def cancel(req: Dict[str, Any], reason: str, actor: Dict[str, Any], *, boleh_semua: bool) -> Dict[str, Any]:
    """Batalkan pengajuan `diajukan` — oleh pengajunya sendiri, atau pemegang `credit_profile.approve`."""
    from input_rules import MIN_REASON_LETTERS, count_letters
    if req.get("status") != ST_DIAJUKAN:
        raise Galat(409, PESAN_DIPUTUS)
    if not boleh_semua and req.get("requested_by_id") != actor.get("id"):
        raise Galat(403, "Hanya pengaju atau pemutus pengajuan perubahan kredit yang bisa membatalkannya.")
    alasan = str(reason or "").strip()
    if count_letters(alasan) < MIN_REASON_LETTERS:
        raise Galat(400, f"Alasan pembatalan wajib diisi (minimal {MIN_REASON_LETTERS} huruf).")
    res = await db[COLL_REQ].find_one_and_update(
        {"id": req["id"], "status": ST_DIAJUKAN},
        {"$set": {"status": ST_DIBATALKAN, "decided_by": actor.get("name", ""), "decided_by_id": actor.get("id", ""),
                  "decided_at": now_iso(), "decision_note": alasan[:1000]}},
        projection={"_id": 0}, return_document=True)
    if not res:
        raise Galat(409, PESAN_DIPUTUS)
    from dependencies import audit
    await audit(actor.get("name", ""), "credit_profile_request_cancelled", "customer", req["customer_id"],
                {"request_id": req["id"], "number": req.get("number")}, reason=alasan[:1000],
                scope_entity_id=req.get("entity_id") or "")
    return safe_doc(res)


async def periksa_putus(req: Dict[str, Any], actor: Dict[str, Any]) -> str:
    """Alasan tombol Setujui/Tolak mati untuk pembaca ini (pengaju sendiri saat wajib dua orang), atau ""."""
    from services import dual_control as dc
    cek = await dc.periksa(AKSI, req, actor, req.get("entity_id") or "", nominal=nominal_dari(req),
                           pengaju=[req.get("requested_by_id")])
    return cek["pesan"]


async def aturan_dua_orang(entity_id: str) -> Dict[str, Any]:
    """Untuk layar: apakah pengaju boleh langsung memutus (tombol "Ajukan & setujui")."""
    from config_catalog_kontrol import kunci_batas
    from services import dual_control as dc
    return {"dua_orang": await dc.butuh_orang_kedua(AKSI, entity_id, 0.0),
            "batas_nominal": _angka(await dc._nilai(kunci_batas(AKSI), entity_id))}   # noqa: SLF001


async def riwayat(customer_id: str, entity_id: str, n: int = 20) -> List[Dict[str, Any]]:
    rows = await db[COLL_REQ].find({"customer_id": customer_id, "entity_id": entity_id,
                                    "status": {"$in": list(ST_DIPUTUS)}},
                                   {"_id": 0, "credit_snapshot": 0}).sort("decided_at", -1).limit(n).to_list(n)
    return [{**r, "label_changes": label_changes(r.get("changes"))} for r in rows]


async def ringkas_pt(entity_ids: Iterable[str]) -> List[Dict[str, str]]:
    return [await _nama_pt(e) for e in entity_ids if e and e != "all"]


# ── Migrasi data lama (H3: dijalankan pemilik lewat `scripts/migrate_credit_profiles.py`) ───────────────────────────
async def migrasi_data_lama(tulis: bool = False) -> Dict[str, Any]:
    """Untuk tiap pelanggan (PT = `customers.entity_id`): `credit_limit > 0` → profil `khusus` dengan plafon sama;
    `status == "blocked"` → `blokir_manual` (alasan "Dipindahkan dari status pelanggan") dan `customers.status` menjadi
    `active`. Idempoten: pelanggan yang sudah punya profil di PT itu tidak dibuatkan lagi (profil itu sudah dibangun dari
    data lama yang sama, lihat `profil_dasar`). `tulis=False` (bawaan) = lapor saja. `customers.credit_limit` tidak
    dihapus. Penanda `crt1_profil_kredit` dipasang sesudah putaran tulis selesai (mematikan cadangan `data_lama`)."""
    dibuat: List[Dict[str, Any]] = []
    dibuka: List[str] = []
    async for c in db.customers.find({"$or": [{"credit_limit": {"$gt": 0}}, {"status": "blocked"}]},
                                     {"_id": 0, "id": 1, "name": 1, "entity_id": 1, "credit_limit": 1, "status": 1}):
        eid = c.get("entity_id") or ""
        lama = profil_data_lama(c)
        if not eid or not lama:
            continue
        ada = await db[COLL].find_one({"customer_id": c["id"], "entity_id": eid}, {"_id": 0, "id": 1})
        if not ada:
            dibuat.append({"customer_id": c["id"], "name": c.get("name", ""), "entity_id": eid,
                           "limit_mode": lama["limit_mode"], "credit_limit": lama["credit_limit"],
                           "credit_status": lama["credit_status"]})
            if tulis:
                doc = {"id": new_id("ccp"), "customer_id": c["id"], "entity_id": eid, **lama, "version": 1,
                       "created_at": now_iso(), "updated_at": now_iso(), "updated_by": "Sistem (migrasi CR-T1)",
                       "updated_by_id": "", "last_request_id": ""}
                from pymongo.errors import DuplicateKeyError
                try:
                    await db[COLL].insert_one(doc)
                except DuplicateKeyError:
                    dibuat.pop()
        if c.get("status") == "blocked":
            dibuka.append(c["id"])
            if tulis:
                await db.customers.update_one({"id": c["id"], "status": "blocked"},
                                              {"$set": {"status": "active", "updated_at": now_iso()}})
    if tulis:
        await db.system_settings.update_one({"scope": "__migrations__"},
                                            {"$set": {PENANDA_MIGRASI: now_iso()}}, upsert=True)
    return {"tulis": tulis, "profil_dibuat": len(dibuat), "status_dibuka": len(dibuka), "rincian": dibuat,
            "pelanggan_dibuka": dibuka}
