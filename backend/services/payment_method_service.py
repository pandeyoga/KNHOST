"""PM-T1 — SATU daftar induk cara bayar (`docs/blueprint/unit/PM-T1.md`, keputusan K-34, K-35).

Setiap layar yang bertanya "dibayar lewat apa" (kwitansi, bayar tagihan pemasok, kontrabon, voucher biaya masuk, pencairan
uang muka, bayar denda, keputusan selisih bayar, pelunasan antar-PT) memakai daftar yang sama: master berlapis
`payment-methods` (koleksi `payment_methods`, global → PT; "Buat khusus PT" mematikan satu cara bayar untuk satu PT).

Dokumen lama TIDAK ditulis ulang: kata lama (`tunai`, `kontan`, `cek`, …) dibaca lewat `normalize` (alias di master).
Pembeda tunai satu-satunya = `is_cash` (`needs_account == "kas"`) — pengganti semua himpunan `{"cash", "tunai", …}`.

Ini satu-satunya berkas server yang boleh menulis kosakata cara bayar (penjaga `scripts/guardrails/verify_payment_vocab.py`).
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, now_iso
from db import db

KIND = "payment-methods"
COLL = "payment_methods"
ARAH = ("masuk", "keluar")
JENIS_REKENING = ("bank", "kas", "tidak")
LABEL_ARAH = {"masuk": "penerimaan", "keluar": "pembayaran keluar"}

#: Benih baris global (`entity_id: "all"`) — tabel "Benih" spesifikasi. Kode kanonik mengikuti nilai yang paling banyak
#: tersimpan hari ini (`cash`, bukan `tunai`) supaya data lama tidak perlu ditulis ulang.
BENIH: List[Dict[str, Any]] = [
    {"code": "transfer", "name": "Transfer bank", "needs_account": "bank", "needs_reference": True,
     "needs_due_date": False, "is_new_money": True, "directions": ["masuk", "keluar"], "aliases": [], "sort": 10,
     "active": True},
    {"code": "cash", "name": "Tunai", "needs_account": "kas", "needs_reference": False, "needs_due_date": False,
     "is_new_money": True, "directions": ["masuk", "keluar"], "aliases": ["tunai", "kontan"], "sort": 20,
     "active": True},
    {"code": "giro", "name": "Giro / cek", "needs_account": "bank", "needs_reference": True, "needs_due_date": True,
     "is_new_money": True, "directions": ["masuk", "keluar"], "aliases": ["cek"], "sort": 30, "active": True},
    {"code": "qris", "name": "QRIS", "needs_account": "bank", "needs_reference": True, "needs_due_date": False,
     "is_new_money": True, "directions": ["masuk"], "aliases": [], "sort": 40, "active": True},
    {"code": "va", "name": "Virtual account", "needs_account": "bank", "needs_reference": True,
     "needs_due_date": False, "is_new_money": True, "directions": ["masuk"], "aliases": [], "sort": 50,
     "active": False, "notes": "Belum dipakai: menunggu penyedia pembayaran (K-35)."},
    {"code": "edc", "name": "Kartu / EDC", "needs_account": "bank", "needs_reference": True, "needs_due_date": False,
     "is_new_money": True, "directions": ["masuk"], "aliases": ["kartu"], "sort": 60, "active": False},
    {"code": "deposit", "name": "Titipan / saldo kredit", "needs_account": "tidak", "needs_reference": False,
     "needs_due_date": False, "is_new_money": False, "directions": ["masuk"], "aliases": ["titipan"], "sort": 70,
     "active": True},
]
BENIH_BY_CODE: Dict[str, Dict[str, Any]] = {b["code"]: b for b in BENIH}
#: Kolom yang dikirim ke layar (`GET /api/payment-methods`) — data rujukan tanpa nominal (Z3).
KOLOM_LAYAR = ("code", "name", "needs_account", "needs_reference", "needs_due_date")


class CaraBayarError(ValueError):
    """Galat cara bayar dengan kalimat siap tampil (400)."""


def _kamus_dari(rows: List[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for r in rows:
        kode = str(r.get("code") or "").strip().lower()
        if not kode:
            continue
        out.setdefault(kode, kode)
        for a in r.get("aliases") or []:
            a = str(a or "").strip().lower()
            if a:
                out.setdefault(a, kode)
    return out


#: kata (kode/alias, huruf kecil) → kode kanonik. Diisi `muat_kamus` saat server menyala dan sesudah master diubah;
#: sebelum itu benih yang dipakai.
_KAMUS: Dict[str, str] = {}


def normalize(value: str) -> str:
    """Kode kanonik dari kode atau alias (besar-kecil huruf diabaikan). Tak dikenal → `ValueError`."""
    v = str(value or "").strip().lower()
    kamus = _KAMUS or _kamus_dari(BENIH)
    if v and v in kamus:
        return kamus[v]
    raise ValueError(f"Cara bayar tidak dikenal: {str(value or '').strip()}.")


async def muat_kamus() -> Dict[str, str]:
    """Bangun ulang kamus dari SEMUA baris master (semua lapisan, termasuk yang nonaktif)."""
    rows = await db[COLL].find({}, {"_id": 0, "code": 1, "aliases": 1}).to_list(2000)
    baru = _kamus_dari(BENIH)
    baru.update({k: v for k, v in _kamus_dari(rows).items() if k not in baru or k == v})
    _KAMUS.clear()
    _KAMUS.update(baru)
    return dict(_KAMUS)


async def ensure_seed() -> int:
    """Benih baris global yang belum ada (idempoten; baris yang sudah diubah pemilik tidak disentuh)."""
    from services.entity_master_service import GLOBAL_VALUES
    n = 0
    for b in BENIH:
        if await db[COLL].find_one({"code": b["code"], "entity_id": {"$in": list(GLOBAL_VALUES)}}, {"_id": 0, "id": 1}):
            continue
        await db[COLL].insert_one({"id": new_id("pmeth"), "entity_id": "all", "notes": "", **b,
                                   "created_at": now_iso(), "updated_at": now_iso()})
        n += 1
    await muat_kamus()
    return n


async def _baris(entity_id: str, code: str) -> Optional[Dict[str, Any]]:
    """Baris efektif PT (baris khusus PT MENANG walau nonaktif — ia sengaja menutupi baris global)."""
    from services import entity_master_service as ems
    return await ems.resolve_row(KIND, code, entity_id or "", include_inactive=True)


def _aktif(row: Optional[Dict[str, Any]]) -> bool:
    return bool(row) and row.get("active", True) is not False


async def get(entity_id: str, code: str) -> Optional[Dict[str, Any]]:
    """Baris efektif cara bayar `code` untuk PT itu; nonaktif (di PT itu) → `None`."""
    row = await _baris(entity_id, code)
    return row if _aktif(row) else None


async def active_for(entity_id: str, direction: str = "") -> List[Dict[str, Any]]:
    """Cara bayar aktif untuk PT itu menurut arah (`masuk`/`keluar`; kosong = semua), terurut `sort`."""
    from services import entity_master_service as ems
    rows = await ems.effective_rows(KIND, entity_id or "", include_inactive=True)
    out = [r for r in rows if _aktif(r) and (not direction or direction in (r.get("directions") or []))]
    out.sort(key=lambda r: (int(r.get("sort") or 0), str(r.get("code") or "")))
    return out


async def is_cash(entity_id: str, code: str) -> bool:
    """Tunai = `needs_account == "kas"` (masuk/keluar Kas Kecil). Kata yang bukan cara bayar (`writeoff`, …) → False."""
    try:
        kode = normalize(code)
    except ValueError:
        return False
    row = await _baris(entity_id, kode) or BENIH_BY_CODE.get(kode)
    return bool(row) and row.get("needs_account") == "kas"


async def wajib(entity_id: str, value: str, *, arah: str = "") -> Dict[str, Any]:
    """`normalize` lalu `get`; galat berkalimat (`CaraBayarError`). Dipanggil SEBELUM menulis apa pun."""
    try:
        kode = normalize(value)
    except ValueError:
        await muat_kamus()   # baris master baru dari proses lain
        try:
            kode = normalize(value)
        except ValueError as exc:
            raise CaraBayarError(str(exc)) from exc
    row = await get(entity_id, kode)
    if row is None:
        info = await _baris(entity_id, kode) or BENIH_BY_CODE.get(kode) or {}
        raise CaraBayarError(f"Cara bayar {info.get('name') or kode} tidak aktif untuk PT ini.")
    if arah and arah not in (row.get("directions") or []):
        raise CaraBayarError(f"Cara bayar {row.get('name') or kode} tidak dipakai untuk {LABEL_ARAH[arah]}.")
    return row


async def kode_400(entity_id: str, value: str, *, arah: str = "") -> str:
    """Kode kanonik, atau 400 berkalimat (untuk router)."""
    try:
        return (await wajib(entity_id, value, arah=arah))["code"]
    except CaraBayarError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def nama(entity_id: str, value: str) -> str:
    """Nama tampil untuk kode/alias (kata tak dikenal = apa adanya)."""
    try:
        kode = normalize(value)
    except ValueError:
        return str(value or "")
    row = await _baris(entity_id, kode) or BENIH_BY_CODE.get(kode) or {}
    return str(row.get("name") or kode)


async def _semua_baris() -> List[Dict[str, Any]]:
    """Benih + semua baris master (semua lapisan, termasuk nonaktif) — bahan saringan kata tersimpan."""
    rows = await db[COLL].find({}, {"_id": 0, "code": 1, "aliases": 1, "needs_account": 1}).to_list(2000)
    return list(BENIH) + rows


async def kata_untuk(value: str) -> List[str]:
    """PM-T3 — semua kata tersimpan (kode + alias, huruf kecil) untuk satu cara bayar; saringan daftar kwitansi lama
    (`tunai` dan `cash` sama-sama ketemu). Kata tak dikenal → hanya kata itu."""
    try:
        kode = normalize(value)
    except ValueError:
        return [str(value or "").strip().lower()]
    out = {kode}
    for r in await _semua_baris():
        if str(r.get("code") or "").strip().lower() == kode:
            out |= {str(a or "").strip().lower() for a in r.get("aliases") or [] if str(a or "").strip()}
    return sorted(out)


async def kata_bukan_bank() -> List[str]:
    """PM-T3 — kata tersimpan untuk cara bayar yang TIDAK lewat rekening bank (tunai, titipan): kwitansi seperti ini
    tidak pernah menunggu dicocokkan dengan mutasi bank. Termasuk kata yang bukan cara bayar baris pesanan (`deposit`)."""
    out = set()
    for r in await _semua_baris():
        if r.get("needs_account") != "bank":
            out.add(str(r.get("code") or "").strip().lower())
            out |= {str(a or "").strip().lower() for a in r.get("aliases") or [] if str(a or "").strip()}
    return sorted(x for x in out if x)


def untuk_layar(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: row.get(k) for k in KOLOM_LAYAR} | {"needs_reference": bool(row.get("needs_reference")),
                                                   "needs_due_date": bool(row.get("needs_due_date"))}


# ── Validasi baris master (dipanggil `entity_master_service` untuk jenis ini) ─────────────────────────────────────
def validasi_baris(data: Dict[str, Any], *, baru: bool) -> Dict[str, Any]:
    """Bersihkan + periksa isian baris master cara bayar. Galat → 400 berkalimat."""
    import re
    out = dict(data or {})
    if "code" in out or baru:
        kode = str(out.get("code") or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{2,30}", kode):
            raise HTTPException(status_code=400, detail=("Kode cara bayar 2–30 huruf kecil, angka, atau garis bawah "
                                                         "(mis. transfer, qris)."))
        out["code"] = kode
    if "needs_account" in out or baru:
        if str(out.get("needs_account") or "") not in JENIS_REKENING:
            raise HTTPException(status_code=400, detail="Jenis rekening wajib salah satu: bank, kas, atau tidak perlu.")
    if "directions" in out or baru:
        arah = out.get("directions") or []
        if isinstance(arah, str):
            arah = [x for x in (s.strip().lower() for s in arah.split(",")) if x]
        if not arah or any(a not in ARAH for a in arah):
            raise HTTPException(status_code=400, detail="Arah wajib diisi: masuk, keluar, atau keduanya.")
        out["directions"] = [a for a in ARAH if a in arah]
    if "aliases" in out:
        al = out.get("aliases") or []
        if isinstance(al, str):
            al = al.split(",")
        out["aliases"] = sorted({str(a).strip().lower() for a in al if str(a).strip()})
    for f in ("needs_reference", "needs_due_date", "is_new_money", "active"):
        if f in out:
            out[f] = bool(out[f])
    if baru:
        out.setdefault("is_new_money", True)
        out.setdefault("needs_reference", False)
        out.setdefault("needs_due_date", False)
        out.setdefault("aliases", [])
    return out


def kode_awal_rekening(account_type: str) -> List[str]:
    """Cara bayar awal sebuah rekening menurut jenisnya (rekening lama / rekening baru tanpa isian): benih aktif yang
    butuh rekening jenis itu — bank: transfer, giro, qris; kas: tunai."""
    jenis = "kas" if account_type == "cash" else "bank"
    return [b["code"] for b in BENIH if b["active"] and b["needs_account"] == jenis]


def jenis_rekening_cocok(row: Dict[str, Any], account_type: str) -> bool:
    """Cara bayar ber-`needs_account` bank hanya di rekening bank, kas hanya di kas; `tidak` (titipan) tidak di rekening."""
    need = (row or {}).get("needs_account")
    return need == ("kas" if account_type == "cash" else "bank")
