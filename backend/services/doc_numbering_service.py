"""doc_numbering_service.py — format nomor dokumen yang berlaku (unit KP-T5, KP-12).

Pembaca tunggal tabel **Penomoran Dokumen** (`doc_number_formats`): baris PT → baris grup (`entity_id = "all"`) → bawaan
katalog `doc_number_kinds.py`. Pilihan "per PT atau bersama" (`scope`) hanya dari baris grup atau katalog. Koleksi hanya
menyimpan yang **diubah**; tanpa baris = bawaan = bentuk nomor sebelum unit ini dipasang.

Pembuat nomor tetap satu: `core_utils.next_doc_number` (semai sekali + `$inc` atomik). Modul ini merencanakan nomornya —
format, cara (per PT / bersama), kunci deret, pola semai, dan perakitan — supaya pratinjau dan pembuat nomor memakai
rumus yang sama.

Kunci deret di `number_sequences` (tidak berubah dari sebelum unit ini, sehingga penghitung berlanjut):
- per PT: `entity_id` = id PT, `doc_type` = (awalan identitas + bagian periode + `-`) tanpa tanda hubung akhir, huruf besar;
- bersama: `entity_id = "__shared__"`, `doc_type` = `koleksi:field:` + awalan identitas + bagian periode + `-`.
Bagian periode menurut `reset`: `tidak` → kosong; `tahunan` → tahun; `bulanan` → tahun-bulan; `harian` → tanggal.
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db import db
import doc_number_kinds as dnk

COLL = "doc_number_formats"
SHARED_ENTITY = "__shared__"
FORMAT_FIELDS = ("prefix", "width", "date_token", "reset")
_TRAILING_NO = re.compile(r"(\d+)\s*$")


def _has_pt(entity_id: Optional[str]) -> bool:
    """PT terisi menurut aturan lama `next_doc_number`: hanya `None` dan `"all"` yang berarti tanpa PT."""
    return entity_id is not None and entity_id != "all"


async def effective_format(kind: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Format yang dipakai mesin untuk (jenis, PT): baris PT → baris grup → bawaan katalog.

    Jawaban: `{prefix, width, date_token, reset, scope, source, scope_source, group_version, pt_version}` dengan
    `source` = `bawaan` | `grup` | `pt` (lapisan teratas yang mengisi format) dan `scope_source` = `bawaan` | `grup`."""
    k = dnk.kind(kind)
    out: Dict[str, Any] = {**k["default"], "source": "bawaan", "scope_source": "bawaan",
                           "group_version": 0, "pt_version": 0}
    if k["locked"] or k["derived"]:
        return out
    ents = ["all"] + ([entity_id] if _has_pt(entity_id) and entity_id else [])
    rows = {r.get("entity_id"): r async for r in db[COLL].find({"kind": kind, "entity_id": {"$in": ents}},
                                                               {"_id": 0})}
    grp = rows.get("all")
    if grp:
        for f in FORMAT_FIELDS:
            if grp.get(f) is not None:
                out[f] = grp[f]
        if grp.get("scope") in dnk.SCOPES:
            out["scope"] = grp["scope"]
            out["scope_source"] = "grup"
        out["source"] = "grup"
        out["group_version"] = int(grp.get("version") or 0)
    pt = rows.get(entity_id) if _has_pt(entity_id) and entity_id else None
    if pt:
        for f in FORMAT_FIELDS:
            if pt.get(f) is not None:
                out[f] = pt[f]
        out["source"] = "pt"
        out["pt_version"] = int(pt.get("version") or 0)
    return out


# ── Rencana satu nomor (dipakai pembuat nomor dan pratinjau) ───────────────────────────────────────────────────────
def render_stamp(token: str, at: Any = None, clock: str = "wib") -> str:
    """Sisipan tanggal untuk `token` pada waktu `at` (bawaan sekarang). Waktu ber-zona diubah ke jam jenisnya
    (WIB, atau UTC untuk lot); waktu tanpa zona dipakai apa adanya (perilaku lama pesanan khusus)."""
    if not token:
        return ""
    stamp = at if isinstance(at, datetime) else datetime.now(timezone.utc)
    if stamp.tzinfo is not None:
        if clock == "utc":
            stamp = stamp.astimezone(timezone.utc)
        else:
            from zoneinfo import ZoneInfo
            stamp = stamp.astimezone(ZoneInfo("Asia/Jakarta"))
    return stamp.strftime(dnk.DATE_FORMAT[token])


def period_part(token: str, stamp: str, reset: str) -> str:
    """Bagian sisipan yang masuk kunci deret menurut `reset` (kosong = deret tidak pernah mulai dari 1)."""
    if not token or not stamp or reset == "tidak":
        return ""
    year = stamp[:4] if token.startswith("YYYY") else stamp[:2]
    if reset == "tahunan":
        return year
    if reset == "bulanan":
        return stamp[:len(year) + 2] if token in ("YYMM", "YYYYMM", "YYMMDD") else stamp
    return stamp


async def plan(kind_entry: Dict[str, Any], entity_id: Optional[str], *, scheme: str = "per_entity_prefix",
               stamp: Optional[str] = None, at: Any = None) -> Dict[str, Any]:
    """Rencana nomor berikutnya: format, cara, kunci deret, pola semai, dan bagian rakitan — tanpa menulis apa pun.

    `stamp` = sisipan yang sudah dirakit titik panggil (mis. lot `LOT-2611-`); dipakai selama sisipan jenisnya masih
    bawaan, supaya nomornya identik dengan sebelum unit ini."""
    k = kind_entry
    has_pt = _has_pt(entity_id)
    fmt = await effective_format(k["kind"], entity_id if has_pt else None)
    per_pt = has_pt and fmt["scope"] == "per_pt"
    if scheme == "shared" and fmt["scope_source"] == "bawaan":
        per_pt = False   # titik panggil ber-scheme "shared" tetap bersama selama grup belum memilih cara
    token = fmt["date_token"] or ""
    if token and stamp is not None and token == k["default"]["date_token"]:
        sis = stamp
    else:
        sis = render_stamp(token, at, k["clock"])
    period = period_part(token, sis, fmt["reset"])
    tail = f"{period}-" if period else ""
    ident = k["identity_prefix"]
    if per_pt:
        doc_type = (ident + tail).rstrip("-/").upper() or ident
        key = {"entity_id": entity_id, "doc_type": doc_type}
    else:
        key = {"entity_id": SHARED_ENTITY, "doc_type": f"{k['collection']}:{k['field']}:{ident}{tail}"}
    # Pola semai = awalan + bagian periode (+ `-` bila periode = seluruh sisipan, persis awalan lama `LOT-2611-`).
    seed_tail = (f"{period}-" if period == sis else period) if period else ""
    patterns = [fmt["prefix"] + seed_tail]
    if ident + seed_tail not in patterns:
        patterns.append(ident + seed_tail)
    return {"kind": k["kind"], "entry": k, "format": fmt, "per_pt": per_pt, "entity_id": entity_id if per_pt else None,
            "key": key, "stamp": sis, "period": period, "seed_patterns": patterns}


async def _siblings(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Jenis lain yang memakai kunci deret per PT yang sama (awalan identitas sama, cara per PT di PT itu) —
    mis. nota debit penjualan dan nota debit retur pembelian bila grup menjadikan keduanya per PT."""
    out = []
    for other in dnk.KINDS_LIST:
        if other["kind"] == p["kind"] or other["locked"] or other["derived"]:
            continue
        if other["identity_prefix"].rstrip("-/").upper() != p["entry"]["identity_prefix"].rstrip("-/").upper():
            continue
        q = await plan(other, p["entity_id"], stamp=p["stamp"] or None)
        if q["per_pt"] and q["key"] == p["key"]:
            out.append(q)
    return out


async def _max_in(collection: str, field: str, pattern: str, entity_id: Optional[str]) -> int:
    """Angka urut tertinggi yang sudah terbit. Per PT: pola di mana saja dalam nomor (nomor lama `SO-…` dan baru
    `KODE/SO-…`) untuk PT itu; bersama: nomor yang diawali pola — sama dengan semai sebelum unit ini."""
    if entity_id is not None:
        q = {field: {"$regex": re.escape(pattern)}, "entity_id": entity_id}
    else:
        q = {field: {"$regex": f"^{re.escape(pattern)}"}}
    n = 0
    async for d in db[collection].find(q, {"_id": 0, field: 1}):
        val = d.get(field)
        if isinstance(val, str):
            m = _TRAILING_NO.search(val)
            if m:
                n = max(n, int(m.group(1)))
    return n


async def seed_number(p: Dict[str, Any]) -> int:
    """Nomor tertinggi yang sudah ada untuk deret baru (0 bila belum ada) — semai SEKALI sebelum `$inc` pertama."""
    plans = [p] + (await _siblings(p) if p["per_pt"] else [])
    n = 0
    for q in plans:
        k = q["entry"]
        for pat in q["seed_patterns"]:
            n = max(n, await _max_in(k["collection"], k["field"], pat, q["entity_id"]))
    return n


def render(p: Dict[str, Any], n: int, code: str = "") -> str:
    fmt = p["format"]
    sis = f"{p['stamp']}-" if p["stamp"] else ""
    body = f"{fmt['prefix']}{sis}{int(n):0{int(fmt['width'])}d}"
    return f"{code}/{body}" if p["per_pt"] else body
