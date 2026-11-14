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

from fastapi import HTTPException

from core_utils import new_id, now_iso
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
def _now() -> datetime:
    """Jam sekarang (UTC) — satu titik supaya uji bisa membekukan waktu."""
    return datetime.now(timezone.utc)


def render_stamp(token: str, at: Any = None, clock: str = "wib") -> str:
    """Sisipan tanggal untuk `token` pada waktu `at` (bawaan sekarang). Waktu ber-zona diubah ke jam jenisnya
    (WIB, atau UTC untuk lot); waktu tanpa zona dipakai apa adanya (perilaku lama pesanan khusus)."""
    if not token:
        return ""
    stamp = at if isinstance(at, datetime) else _now()
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
               stamp: Optional[str] = None, at: Any = None, fmt: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Rencana nomor berikutnya: format, cara, kunci deret, pola semai, dan bagian rakitan — tanpa menulis apa pun.

    `stamp` = sisipan yang sudah dirakit titik panggil (mis. lot `LOT-2611-`); dipakai selama sisipan jenisnya masih
    bawaan, supaya nomornya identik dengan sebelum unit ini. `fmt` = format calon (pratinjau); bawaan = yang berlaku."""
    k = kind_entry
    has_pt = _has_pt(entity_id)
    if fmt is None:
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
    # Deret bersama yang DIPILIH grup (bukan bawaan) disemai dari nomor tertinggi gabungan semua PT (`KODE/…` juga).
    wide = (not per_pt) and fmt.get("scope_source") == "grup"
    return {"kind": k["kind"], "entry": k, "format": fmt, "per_pt": per_pt, "entity_id": entity_id if per_pt else None,
            "key": key, "stamp": sis, "period": period, "seed_patterns": patterns, "wide_seed": wide}


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


async def _max_in(collection: str, field: str, pattern: str, entity_id: Optional[str],
                  entity_field: str = "entity_id", wide: bool = False) -> int:
    """Angka urut tertinggi yang sudah terbit. Per PT: pola di mana saja dalam nomor (nomor lama `SO-…` dan baru
    `KODE/SO-…`) untuk PT itu; bersama: nomor yang diawali pola — sama dengan semai sebelum unit ini; bersama pilihan
    grup (`wide`): pola di mana saja, semua PT."""
    if entity_id is not None:
        q = {field: {"$regex": re.escape(pattern)}, entity_field: entity_id}
    elif wide:
        q = {field: {"$regex": re.escape(pattern)}}
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
            n = max(n, await _max_in(k["collection"], k["field"], pat, q["entity_id"],
                                     k.get("entity_field") or "entity_id", bool(q.get("wide_seed"))))
    return n


def render(p: Dict[str, Any], n: int, code: str = "") -> str:
    fmt = p["format"]
    sis = f"{p['stamp']}-" if p["stamp"] else ""
    body = f"{fmt['prefix']}{sis}{int(n):0{int(fmt['width'])}d}"
    return f"{code}/{body}" if p["per_pt"] else body


# ══ Serah-terima (b): tabel Penomoran Dokumen — baca, pratinjau, simpan, hapus ═══════════════════════════════════
PREFIX_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,11}$")
MSG_REASON = "Alasan perubahan format nomor wajib diisi."
MSG_FORMAT = ("Awalan hanya huruf besar, angka, dan tanda hubung (paling banyak 12 karakter); "
              "lebar angka 3 sampai 8.")
MSG_TOKEN = "Sisipan tanggal atau pengulangan tidak dikenal."
MSG_SCOPE_PT = "Pilihan per PT atau bersama diatur untuk seluruh grup."
MSG_VERSION = "Format ini sudah diubah orang lain. Muat ulang."
#: `reset` → (sisipan yang membedakan periodenya, kata untuk pesan).
RESET_NEEDS = {"tahunan": (("YY", "YYYY", "YYMM", "YYYYMM", "YYMMDD"), "tahun"),
               "bulanan": (("YYMM", "YYYYMM", "YYMMDD"), "tahun-bulan"),
               "harian": (("YYMMDD",), "tanggal")}
SOURCE_LABEL = {"bawaan": "Bawaan", "grup": "Aturan grup", "pt": "Khusus PT ini"}
PREVIEW_ENTITY = "__contoh__"   # PT contoh untuk pratinjau baris grup / PT yang belum dibuat (tanpa penghitung)


def _bad(msg: str, code: int = 400) -> HTTPException:
    return HTTPException(status_code=code, detail=msg)


def kind_or_404(kind: str) -> Dict[str, Any]:
    if kind not in dnk.KINDS:
        raise _bad("Jenis nomor dokumen tidak dikenal.", 404)
    return dnk.KINDS[kind]


async def _rows(kind: str) -> Dict[str, Dict[str, Any]]:
    return {r["entity_id"]: r async for r in db[COLL].find({"kind": kind}, {"_id": 0})}


def _apply(base: Dict[str, Any], row: Optional[Dict[str, Any]], *, group: bool) -> Dict[str, Any]:
    out = dict(base)
    if row:
        for f in FORMAT_FIELDS:
            if row.get(f) is not None:
                out[f] = row[f]
        if group and row.get("scope") in dnk.SCOPES:
            out["scope"] = row["scope"]
    return out


async def _format_at(kind: str, ent: str, cand_kind: str = "", cand_ent: str = "",
                     cand: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Format (jenis, lapisan) — aturan yang sama dengan `effective_format` — bila baris `cand_ent` milik `cand_kind`
    diganti `cand` (pratinjau dan pemeriksa bentrok). `ent = "all"` = lapisan grup."""
    k = dnk.kind(kind)
    rows = await _rows(kind)
    if kind == cand_kind and cand is not None:
        rows[cand_ent] = {**(rows.get(cand_ent) or {}), **{f: v for f, v in cand.items() if v is not None}}
    fmt = _apply(k["default"], rows.get("all"), group=True)
    if ent != "all":
        fmt = _apply(fmt, rows.get(ent), group=False)
    return fmt


def _form(fmt: Dict[str, Any]) -> tuple:
    return (fmt["scope"], fmt["prefix"], fmt["date_token"] or "")


async def _conflict(k: Dict[str, Any], ent: str, cand: Optional[Dict[str, Any]]) -> Optional[str]:
    """Label jenis lain pada koleksi+field yang sama yang bentuk nomornya (cara + awalan + sisipan) akan sama bila
    baris (jenis, `ent`) menjadi `cand` (`None` = keadaan tersimpan sekarang). Lapisan yang diperiksa: `ent`, dan untuk
    baris grup juga tiap PT yang punya baris khusus untuk jenis-jenis itu."""
    others = [o for o in dnk.KINDS_LIST if o["kind"] != k["kind"] and o["collection"] == k["collection"]
              and o["field"] == k["field"] and not o["derived"]]
    if not others:
        return None
    layers = {ent}
    if ent == "all":
        for o in [k] + others:
            layers |= {e for e in (await _rows(o["kind"])) if e != "all"}
    for lay in sorted(layers):
        mine = _form(await _format_at(k["kind"], lay, k["kind"], ent, cand))
        for o in others:
            if _form(await _format_at(o["kind"], lay)) == mine:
                return o["label"]
    return None


async def _count_docs(k: Dict[str, Any], ent: str) -> int:
    q: Dict[str, Any] = {k["field"]: {"$type": "string", "$gt": ""}}
    if ent != "all":
        q[k.get("entity_field") or "entity_id"] = ent
    try:
        return await db[k["collection"]].count_documents(q)
    except Exception:  # noqa: BLE001 — peringatan saja
        return 0


async def _warnings(k: Dict[str, Any], ent: str, cur: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
    out = []
    if any(cur[f] != new[f] for f in ("prefix", "width", "date_token")):
        n = await _count_docs(k, ent)
        if n:
            out.append(f"Sudah ada {n} dokumen bernomor format lama; nomor lama tidak berubah.")
    if cur["scope"] != new["scope"]:
        which = "tiap PT" if new["scope"] == "per_pt" else "gabungan"
        out.append(f"Deret baru melanjutkan dari nomor tertinggi {which} yang sudah ada.")
    return out


def _validate(k: Dict[str, Any], ent: str, body: Dict[str, Any], reason: Optional[str]) -> Dict[str, Any]:
    """Isian → format bersih, atau 400 dengan pesan manusia. `reason=None` = pratinjau (alasan tidak diminta)."""
    if k["locked"] or k["derived"]:
        raise _bad(f"Format nomor {k['label']} tidak bisa diubah dari layar.")
    if reason is not None and not (reason or "").strip():
        raise _bad(MSG_REASON)
    prefix = str(body.get("prefix") or "").strip()
    try:
        width = int(str(body.get("width")).strip())
    except (TypeError, ValueError):
        width = 0
    if not PREFIX_RE.match(prefix) or not 3 <= width <= 8:
        raise _bad(MSG_FORMAT)
    token = str(body.get("date_token") or "")
    reset = str(body.get("reset") or "tidak")
    if token not in dnk.DATE_TOKENS or reset not in dnk.RESETS:
        raise _bad(MSG_TOKEN)
    scope = body.get("scope")
    if scope not in (None, ""):
        if ent != "all":
            raise _bad(MSG_SCOPE_PT)
        if scope not in dnk.SCOPES:
            raise _bad(MSG_TOKEN)
    if reset in RESET_NEEDS and token not in RESET_NEEDS[reset][0]:
        raise _bad(f"Agar nomor tidak kembar, pengulangan {reset} harus disertai sisipan {RESET_NEEDS[reset][1]}.")
    out = {"prefix": prefix, "width": width, "date_token": token, "reset": reset}
    if scope:
        out["scope"] = scope
    return out


async def preview(k: Dict[str, Any], ent: str, cand: Optional[Dict[str, Any]] = None, *, n: int = 3,
                  code: str = "") -> Dict[str, Any]:
    """Contoh `n` nomor berikutnya untuk (jenis, lapisan) dengan format `cand` (kosong = format yang berlaku). Tidak
    menulis apa pun: penghitung dibaca, deret yang belum ada dihitung dari nomor tertinggi yang ada."""
    cur = await _format_at(k["kind"], ent)
    fmt = dict(cur)
    warnings: List[str] = []
    if cand:
        clean = _validate(k, ent, {**{f: cur[f] for f in FORMAT_FIELDS}, **cand}, None)
        fmt.update(clean)
        warnings = await _warnings(k, ent, cur, fmt)
    real_pt = ent != "all" and not code
    pseudo = ent if real_pt else PREVIEW_ENTITY
    eff = await effective_format(k["kind"], ent if real_pt else None)
    scope_src = "grup" if (fmt["scope"] != k["default"]["scope"] or eff["scope_source"] == "grup") else "bawaan"
    p = await plan(k, pseudo, fmt={**fmt, "scope_source": scope_src})
    seq = await db.number_sequences.find_one(p["key"], {"_id": 0, "last_no": 1})
    last = int(seq["last_no"]) if seq else await seed_number(p)
    if p["per_pt"]:
        from core_utils import entity_code
        kode = await entity_code(ent) if real_pt else (code or "KODE")
    else:
        kode = ""
    if p["per_pt"] and not real_pt and not code:
        warnings.append("Contoh untuk PT yang belum punya dokumen; tiap PT melanjutkan nomornya sendiri.")
    return {"kind": k["kind"], "samples": [render(p, last + i, kode) for i in range(1, n + 1)],
            "last_no": last if (real_pt or not p["per_pt"]) else None, "warnings": warnings,
            "format": {f: fmt[f] for f in (*FORMAT_FIELDS, "scope")}}


async def row_view(k: Dict[str, Any], ent: str) -> Dict[str, Any]:
    eff = await effective_format(k["kind"], None if ent == "all" else ent)
    source = eff["source"]
    if k["derived"]:   # nomor turunan: bentuknya, bukan hitungan
        pv = {"samples": ["INV-‹nomor pesanan›-01"], "last_no": None}
    else:
        pv = await preview(k, ent)
    version = eff["group_version"] if ent == "all" else eff["pt_version"]
    return {"kind": k["kind"], "label": k["label"], "group": k["group"], "note": k.get("note", ""),
            "format": {f: eff[f] for f in (*FORMAT_FIELDS, "scope")}, "default": dict(k["default"]),
            "source": source, "source_label": SOURCE_LABEL[source], "scope_source": eff["scope_source"],
            "next_preview": pv["samples"][0], "samples": pv["samples"], "last_no": pv["last_no"],
            "locked": bool(k["locked"] or k["derived"]),
            "locked_note": dnk.LOCKED_NOTE if (k["locked"] or k["derived"]) else "",
            "version": version}


async def list_formats(ent: str) -> List[Dict[str, Any]]:
    return [await row_view(k, ent) for k in dnk.KINDS_LIST]


async def save_format(k: Dict[str, Any], ent: str, body: Dict[str, Any], *, reason: str,
                      expected_version: Optional[int], actor: Dict[str, Any]) -> Dict[str, Any]:
    clean = _validate(k, ent, body, reason)
    rows = await _rows(k["kind"])
    old = rows.get(ent)
    version = int((old or {}).get("version") or 0)
    if expected_version is not None and int(expected_version) != version:
        raise _bad(MSG_VERSION, 409)
    if ent == "all" and "scope" not in clean and (old or {}).get("scope") in dnk.SCOPES:
        clean["scope"] = old["scope"]
    other = await _conflict(k, ent, clean)
    if other:
        raise _bad(f"Format ini sama dengan {other}, sehingga nomornya bisa kembar. Bedakan awalannya.")
    cur = await _format_at(k["kind"], ent)
    new = await _format_at(k["kind"], ent, k["kind"], ent, clean)
    warnings = await _warnings(k, ent, cur, new)
    now = now_iso()
    who = (actor or {}).get("name", "")
    doc = {**clean, "version": version + 1, "reason": reason.strip()[:400], "updated_at": now, "updated_by": who}
    if old:
        unset = {} if "scope" in clean else {"scope": ""}
        upd: Dict[str, Any] = {"$set": doc}
        if unset:
            upd["$unset"] = unset
        res = await db[COLL].update_one({"kind": k["kind"], "entity_id": ent, "version": version}, upd)
        if not res.modified_count:
            raise _bad(MSG_VERSION, 409)
    else:
        from pymongo.errors import DuplicateKeyError
        try:
            await db[COLL].insert_one({"id": new_id("dnf"), "kind": k["kind"], "entity_id": ent, **doc,
                                       "created_at": now, "created_by": who})
        except DuplicateKeyError:
            raise _bad(MSG_VERSION, 409)
    await _audit(who, "doc_number_format_saved", k, ent, before=old, after=doc, reason=reason)
    view = await row_view(k, ent)
    view["warnings"] = warnings
    return view


async def clear_format(k: Dict[str, Any], ent: str, *, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    if k["locked"] or k["derived"]:
        raise _bad(f"Format nomor {k['label']} tidak bisa diubah dari layar.")
    if not (reason or "").strip():
        raise _bad(MSG_REASON)
    old = await db[COLL].find_one({"kind": k["kind"], "entity_id": ent}, {"_id": 0})
    if old:
        # Baris dihapus → lapisan di atasnya berlaku; tolak bila bentuknya jadi sama dengan jenis sejenis.
        await db[COLL].delete_one({"kind": k["kind"], "entity_id": ent})
        other = await _conflict(k, ent, None)
        if other:
            await db[COLL].insert_one(dict(old))
            raise _bad(f"Format ini sama dengan {other}, sehingga nomornya bisa kembar. Bedakan awalannya.")
        await _audit((actor or {}).get("name", ""), "doc_number_format_cleared", k, ent, before=old, after=None,
                     reason=reason)
    return await row_view(k, ent)


async def _audit(who: str, action: str, k: Dict[str, Any], ent: str, *, before: Any, after: Any,
                 reason: str) -> None:
    try:
        from dependencies import audit
        await audit(who, action, COLL, f"{k['kind']}:{ent}",
                    {"kind": k["kind"], "entity_id": ent, "format": after}, reason=(reason or "").strip()[:400],
                    scope_entity_id="" if ent == "all" else ent,
                    before={"kind": k["kind"], "entity_id": ent, "format": before})
    except Exception:  # noqa: BLE001 — jejak tambahan; baris sudah tersimpan
        pass
