"""FASE G-0 — CONFIG RESOLVER: nilai efektif berlapis + jejak "kenapa begini" + berlaku-sejak.

Masalah lama: nilai konfigurasi ditimpa langsung di `system_settings` sehingga
(1) tidak ada riwayat, (2) tidak bisa dijadwalkan berlaku tanggal tertentu, dan
(3) user tidak pernah tahu **lapisan mana** yang menentukan nilai yang dia lihat.

Desain:
- Penyimpanan baru `config_values` (prefix `cfgv_`) bersifat **APPEND-ONLY**:
  setiap perubahan = baris baru berisi `value`, `prev_value`, `effective_from`,
  `reason`, `changed_by`. Riwayat, rollback, dan penjadwalan otomatis tersedia.
- Lapisan (kiri kalah, kanan menang):
    default kode → (legacy global) → global → (legacy entitas) → entitas
    → supplier → customer → produk → dokumen
- **Kompatibilitas penuh:** dokumen `system_settings` lama TETAP dibaca sebagai lapisan
  dan setiap penulisan level global/entitas juga **diproyeksikan** ke sana, sehingga
  seluruh mesin lama (yang membaca `system_settings`) langsung ikut berubah tanpa migrasi.
- PK-46 — kecuali kunci registry `bertanggal`: tidak diproyeksikan dan tidak membaca lapisan lama; nilainya untuk
  tanggal tertentu dibaca dengan `resolve(key, ctx, at=<waktu>)`.

INV-CFG-03: baris `config_values` tidak pernah di-update pada field nilai. Penanda yang boleh diisi SEKALI:
`applied_at` (penanda bookkeeping proyeksi) dan — KF-T3 — `cancelled_at` (+ `cancelled_by`, `cancelled_by_id`,
`cancel_reason`) pada baris berjadwal yang dibatalkan sebelum berlaku. Baris ber-`cancelled_at` diabaikan resolver dan
`apply_due_values`, tetapi tetap tampil di riwayat (`cancelled: true`).

KF-T3 — `resolve()` juga menanyakan PENIMPAAN TERDAFTAR (`services/config_overrides.py`): bila aturan lain menimpa
nilai lapisan (mis. PT bukan PKP → tarif PPN 0), `value` = nilai yang dipakai mesin, `stored_value` = nilai lapisan
pemenang, `overridden_by` = siapa yang menimpa, dan `explain` mendapat lapisan terakhir `override` sebagai pemenang.
Perubahan berjadwal diterapkan begitu jatuh tempo oleh `ensure_due_applied()` (dipanggil pembaca lama) dan job
penjadwal `config_apply_due`, bukan hanya saat layar Pengaturan dibuka.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import config_registry as registry
from core_utils import new_id, now_iso
from db import db
logger = logging.getLogger(__name__)


COLL = "config_values"

# Lapisan dari paling umum → paling spesifik. Yang paling kanan MENANG.
LAYER_ORDER: List[str] = [
    "code_default",
    "legacy_global",
    "global",
    "legacy_entity",
    "entity",
    "supplier",
    "customer",
    "product",
    "document",
    "override",   # KF-T3 — penimpaan terdaftar (`config_overrides.PENIMPA`), selalu paling akhir
]
LAYER_LABEL = {
    # KF-T4 (KF-UX-21/22) — istilah awam: "Bawaan sistem" · "Aturan grup" · "Khusus PT"; lapisan lama ditulis sama
    # dengan padanannya (pengguna tidak perlu tahu penyimpanan mana yang dibaca).
    "code_default": "Bawaan sistem",
    "legacy_global": "Aturan grup",
    "global": "Aturan grup",
    "legacy_entity": "Khusus PT",
    "entity": "Khusus PT",
    "supplier": "Khusus pemasok",
    "customer": "Khusus pelanggan",
    "product": "Khusus produk",
    "document": "Khusus dokumen",
    "hypothetical": "Coba dulu (belum disimpan)",
    "override": "Ditimpa aturan lain",   # KF-T3
}
# Lapisan yang berasal dari `config_values` (bisa ditulis lewat API baru).
WRITABLE_LAYERS = ("global", "entity", "supplier", "customer", "product", "document")
CTX_FIELD = {
    "entity": "entity_id",
    "supplier": "supplier_id",
    "customer": "customer_id",
    "product": "product_id",
    "document": "document_id",
}
# KF-T5 — kata untuk pesan "tidak bisa dibedakan …" (tanpa id lapisan; L1).
PER_LAPISAN = {"global": "untuk semua PT", "entity": "per PT", "supplier": "per pemasok", "customer": "per pelanggan",
               "product": "per barang", "document": "per dokumen"}
_MISSING = object()


# ── util ──────────────────────────────────────────────────────────────────
def _dig(doc: Optional[Dict[str, Any]], path: str) -> Any:
    """Ambil nilai dot-path dari dokumen; `_MISSING` bila tak ada."""
    cur: Any = doc or {}
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def _iso_now() -> str:
    return now_iso()


def _as_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _is_due(row: Dict[str, Any], at: datetime) -> bool:
    ef = _as_dt(row.get("effective_from")) or datetime.min.replace(tzinfo=timezone.utc)
    return ef <= at


# ── baca lapisan ───────────────────────────────────────────────────────────
async def _legacy_doc(scope: str) -> Dict[str, Any]:
    return await db.system_settings.find_one({"scope": scope}, {"_id": 0}) or {}


async def _stored_rows(keys: List[str], ctx: Dict[str, Any]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """Semua baris `config_values` relevan untuk kumpulan kunci + konteks, dikelompokkan
    per (key, scope_type). Diurutkan effective_from lalu created_at (terbaru terakhir)."""
    ors: List[Dict[str, Any]] = [{"scope_type": "global"}]
    for layer, field in CTX_FIELD.items():
        val = (ctx or {}).get(field)
        if val:
            ors.append({"scope_type": layer, "scope_id": val})
    cur = db[COLL].find({"key": {"$in": keys}, "$or": ors}, {"_id": 0})
    out: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    async for row in cur:
        if row.get("cancelled_at"):          # KF-T3 — jadwal yang dibatalkan tidak pernah berlaku
            continue
        out.setdefault((row["key"], row["scope_type"]), []).append(row)
    for rows in out.values():
        rows.sort(key=lambda r: (str(r.get("effective_from") or ""), str(r.get("created_at") or "")))
    return out


def _pick_effective(rows: List[Dict[str, Any]], at: datetime) -> Tuple[Any, Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """(nilai efektif, baris pemenang, baris terjadwal) dari daftar baris satu scope.

    FASE E-4 (E4.6) — baris ber-`cleared: True` adalah **nisan**: ia menyatakan
    "lapisan ini dikosongkan", bukan "nilainya None". Karena penyimpanan bersifat
    append-only (INV-CFG-03: baris nilai tidak pernah di-update/dihapus), inilah cara
    jujur menyediakan tombol "Kembalikan ke global" tanpa menghapus riwayat.
    """
    due = [r for r in rows if _is_due(r, at)]
    scheduled = [r for r in rows if not _is_due(r, at)]
    if not due:
        return _MISSING, None, scheduled
    winner = due[-1]
    if winner.get("cleared"):
        return _MISSING, winner, scheduled
    return winner.get("value"), winner, scheduled


async def build_layers(key: str, ctx: Optional[Dict[str, Any]] = None,
                       at: Optional[datetime] = None,
                       preloaded: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Susun seluruh lapisan untuk satu kunci (tanpa menentukan pemenang)."""
    entry = registry.require(key)
    ctx = ctx or {}
    at = at or datetime.now(timezone.utc)
    pre = preloaded or {}

    legacy_scope, legacy_path = entry["legacy_scope"], entry["legacy_path"]
    # PK-46 — kunci `bertanggal` tidak membaca lapisan lama (`system_settings` tidak bertanggal): nilainya hanya bawaan
    # registry + baris `config_values` yang sudah berlaku pada `at`.
    bertanggal = bool(entry.get("bertanggal"))
    ent_id = ctx.get("entity_id") or ""
    legacy_global: Dict[str, Any] = {}
    legacy_entity: Dict[str, Any] = {}
    if not bertanggal:
        legacy_global = pre.get(f"legacy:{legacy_scope}")
        if legacy_global is None:
            legacy_global = await _legacy_doc(legacy_scope)
        if ent_id and ent_id != "all" and legacy_scope == "global":
            legacy_entity = pre.get(f"legacy:{ent_id}")
            if legacy_entity is None:
                legacy_entity = await _legacy_doc(ent_id)
    catatan_bertanggal = ("Tidak dibaca: pengaturan bertanggal hanya memakai nilai Pusat Pengaturan menurut "
                          "tanggal berlakunya.")

    rows_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = pre.get("rows") or {}
    if not pre:
        rows_map = await _stored_rows([key], ctx)

    layers: List[Dict[str, Any]] = [{
        "layer": "code_default", "label": LAYER_LABEL["code_default"], "scope_id": "",
        "present": True, "value": entry["default"],
        "note": "Nilai awal dari sistem — dipakai selama belum ada aturan grup atau nilai khusus PT.",
        "changed_by": "", "changed_at": "", "reason": "", "effective_from": "",
    }]

    lg = _dig(legacy_global, legacy_path)
    layers.append({
        "layer": "legacy_global", "label": LAYER_LABEL["legacy_global"], "scope_id": legacy_scope,
        "present": lg is not _MISSING, "value": None if lg is _MISSING else lg,
        "note": catatan_bertanggal if bertanggal else "Aturan grup yang tersimpan sebelum Pengaturan ini ada.",
        "changed_by": (legacy_global or {}).get("updated_by", ""),
        "changed_at": (legacy_global or {}).get("updated_at", ""),
        "reason": "", "effective_from": "",
    })

    def _cfgv_layer(layer: str, scope_id: str) -> Dict[str, Any]:
        rows = rows_map.get((key, layer), [])
        if scope_id:
            rows = [r for r in rows if r.get("scope_id") == scope_id]
        val, win, sched = _pick_effective(rows, at)
        cleared = bool(win and win.get("cleared"))
        return {
            "layer": layer, "label": LAYER_LABEL[layer], "scope_id": scope_id,
            "present": val is not _MISSING,
            "value": None if val is _MISSING else val,
            "cleared": cleared,
            "note": ("Dicabut — kembali mengikuti nilai di atasnya."
                     if cleared else
                     ("Diatur lewat Pengaturan." if win else "Belum diatur di sini.")),
            "changed_by": (win or {}).get("changed_by", ""),
            "changed_at": (win or {}).get("changed_at", ""),
            "reason": (win or {}).get("reason", ""),
            "effective_from": (win or {}).get("effective_from", ""),
            # KF-T3 — `id` + cakupan supaya layar bisa menyebut lapisannya dan membatalkan jadwal itu.
            "scheduled": [{"id": s.get("id", ""), "scope_type": layer, "scope_id": s.get("scope_id", ""),
                           "value": s.get("value"), "effective_from": s.get("effective_from"),
                           "changed_by": s.get("changed_by", ""), "reason": s.get("reason", "")}
                          for s in sched],
        }

    layers.append(_cfgv_layer("global", ""))

    le = _dig(legacy_entity, legacy_path) if legacy_entity else _MISSING
    layers.append({
        "layer": "legacy_entity", "label": LAYER_LABEL["legacy_entity"], "scope_id": ent_id,
        "present": le is not _MISSING, "value": None if le is _MISSING else le,
        "note": (catatan_bertanggal if bertanggal else
                 "Nilai khusus PT yang tersimpan sebelum Pengaturan ini ada." if ent_id
                 else "Tidak ada PT yang dipilih."),
        "changed_by": (legacy_entity or {}).get("updated_by", ""),
        "changed_at": (legacy_entity or {}).get("updated_at", ""),
        "reason": "", "effective_from": "",
    })

    for layer in ("entity", "supplier", "customer", "product", "document"):
        scope_id = ctx.get(CTX_FIELD[layer]) or ""
        if not scope_id:
            continue
        layers.append(_cfgv_layer(layer, scope_id))

    allowed = set(entry["scopes"])
    for lay in layers:
        if lay["layer"] in WRITABLE_LAYERS and lay["layer"] not in allowed:
            lay["present"] = False
            lay["note"] = "Pengaturan ini tidak bisa dibedakan di sini — pembacanya belum mendukung."
    return layers


def _decide(layers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Tentukan pemenang (lapisan paling spesifik yang punya nilai) + tandai di explain."""
    rank = {name: i for i, name in enumerate(LAYER_ORDER)}
    winner = None
    for lay in layers:
        if lay.get("present") and (winner is None or rank.get(lay["layer"], -1) >= rank.get(winner["layer"], -1)):
            winner = lay
    for lay in layers:
        lay["winner"] = winner is not None and lay is winner
    return winner or layers[0]


async def resolve(key: str, ctx: Optional[Dict[str, Any]] = None,
                  at: Optional[datetime] = None,
                  hypothetical: Any = _MISSING,
                  preloaded: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Nilai efektif + jejak lengkap. `hypothetical` = nilai simulasi (tidak disimpan)."""
    entry = registry.require(key)
    layers = await build_layers(key, ctx, at, preloaded)
    if hypothetical is not _MISSING:
        layers.append({
            "layer": "hypothetical", "label": LAYER_LABEL["hypothetical"], "scope_id": "",
            "present": True, "value": hypothetical,
            "note": "Nilai yang sedang Anda coba — belum tersimpan.",
            "changed_by": "", "changed_at": "", "reason": "", "effective_from": "",
        })
        for lay in layers:
            lay["winner"] = lay["layer"] == "hypothetical"
        winner = layers[-1]
    else:
        winner = _decide(layers)
    value = winner.get("value")
    stored = value
    overridden_by: Optional[Dict[str, Any]] = None
    if hypothetical is _MISSING:
        # KF-T3 (KF-04) — aturan lain yang menimpa nilai lapisan (PT bukan PKP, wajib transfer antar-PT, Master Grade).
        from services.config_overrides import penimpa
        overridden_by = await penimpa(key, ctx or {}, stored)
        if overridden_by is not None:
            value = overridden_by["value"]
            for lay in layers:
                lay["winner"] = False
            layers.append({
                "layer": "override", "label": LAYER_LABEL["override"], "scope_id": "",
                "present": True, "value": value, "winner": True, "note": overridden_by["label"],
                "changed_by": "", "changed_at": "", "reason": "", "effective_from": "",
            })
    return {
        "key": key,
        "value": value,
        # KF-T3 — lapisan asal NILAI TERSIMPAN (yang bisa diubah/dicabut di kartu); penimpa ada di `overridden_by`.
        "source_layer": winner["layer"],
        "source_label": winner["label"],
        "stored_value": stored,
        "overridden_by": overridden_by,
        "type": entry["type"],
        "status": entry["status"],
        "explain": layers,
        "scheduled": [s for lay in layers for s in (lay.get("scheduled") or [])],
    }


async def value_of(key: str, ctx: Optional[Dict[str, Any]] = None) -> Any:
    """Pintasan untuk kode mesin: ambil nilai efektif saja."""
    return (await resolve(key, ctx))["value"]


async def resolve_group(group_id: Optional[str] = None, ctx: Optional[Dict[str, Any]] = None,
                        term: str = "") -> List[Dict[str, Any]]:
    """Nilai efektif untuk sekumpulan setting (satu grup / hasil pencarian) — hemat query.

    KF-T4 — tiap butir juga memuat sub-judul (`section`), tema lintas kelompok (`themes`), isi daftar (`items`,
    `ordered`), rujukan master (`ref`, `ref_options`), layar pengubah lain (`edit_at`), izin pengubah + nama modulnya
    (`permission`, `permission_label`), dan `never_changed` (belum pernah diubah: tanpa baris riwayat dan nilai =
    bawaan). `group_id` boleh id kelompok lama (`GROUP_ALIASES`)."""
    entries = registry.search(term) if term else (
        registry.by_group(group_id) if group_id else registry.all_entries())
    if not entries:
        return []
    keys = [e["key"] for e in entries]
    ctx = ctx or {}
    scopes_needed = {e["legacy_scope"] for e in entries}
    pre: Dict[str, Any] = {"rows": await _stored_rows(keys, ctx)}
    for sc in scopes_needed:
        pre[f"legacy:{sc}"] = await _legacy_doc(sc)
    ent_id = ctx.get("entity_id") or ""
    if ent_id and ent_id != "all":
        pre[f"legacy:{ent_id}"] = await _legacy_doc(ent_id)
    pernah = set(await db[COLL].distinct("key", {"key": {"$in": keys}}))   # KF-T4 — `never_changed`
    refs: Dict[str, List[Dict[str, Any]]] = {}
    for e in entries:
        if e.get("ref") and e["ref"] not in refs:
            refs[e["ref"]] = await ref_options(e["ref"], ent_id)
    peran = role_options() if any(e.get("items") == "roles" or any(c.get("ref") == "role" for c in e.get("columns") or [])
                                  for e in entries) else []

    out: List[Dict[str, Any]] = []
    at = datetime.now(timezone.utc)
    for e in entries:
        res = await resolve(e["key"], ctx, at=at, preloaded=pre)
        out.append({**{k: e[k] for k in (
            "key", "group", "label", "help", "impact", "example", "type", "default",
            "min", "max", "step", "options", "unit", "scopes", "consumers",
            "risk", "requires_reason", "status", "not_used_reason", "simulate", "related",
            "row_shape", "columns", "editable", "bertanggal",
            # KF-T4 — sub-judul, isi daftar, rujukan, layar lain, format nilai, izin pengubah
            "section", "items", "ordered", "ref", "edit_at", "value_format", "permission")},
            "themes": registry.themes_for(e["key"]),
            "permission_label": permission_label(e),
            # KF-T4 — pilihan editor: rujukan master (`ref`) atau daftar peran (`items: "roles"`, kolom ber-`ref: "role"`).
            "ref_options": refs.get(e.get("ref") or "", []) if e.get("ref") else (
                peran if e.get("items") == "roles" else []),
            "role_options": peran if any(c.get("ref") == "role" for c in e.get("columns") or []) else [],
            "never_changed": e["key"] not in pernah and res["stored_value"] == e["default"],
            "value": res["value"], "source_layer": res["source_layer"],
            "source_label": res["source_label"], "scheduled": res["scheduled"],
            # KF-T3 — nilai tersimpan + penimpa (null bila tidak ditimpa): kartu menulis siapa yang menimpa.
            "stored_value": res["stored_value"], "overridden_by": res["overridden_by"],
            "is_default": res["source_layer"] == "code_default"})
    return out


def permission_label(entry: Dict[str, Any]) -> str:
    """KF-T4 — nama modul akses pemilik izin pengubah (`access_modules.MODULE_CATALOG`), untuk kalimat kartu terkunci."""
    resource = (entry.get("permission") or ["settings", "manage"])[0]
    try:
        from access_modules import MODULE_CATALOG
    except Exception:   # noqa: BLE001
        return resource
    for m in MODULE_CATALOG:
        if resource in (m.get("resources") or []):
            return m.get("label", resource)
    return resource


def role_options() -> List[Dict[str, Any]]:
    """KF-T4 — id peran yang dikenal (bawaan + kustom terdaftar) berlabel nama peran, untuk kotak centang daftar peran."""
    from role_registry import role_ids, role_label
    return [{"value": rid, "label": role_label(rid)} for rid in role_ids()]


# ── KF-T4 (KF-UX-18) — pilihan untuk kunci teks yang merujuk master ─────────────────────────────────────────────────
async def ref_options(ref: str, entity_id: str = "") -> List[Dict[str, Any]]:
    """Pilihan untuk kunci ber-`ref`: `[{value, label}]`.

    `payment_term` → baris efektif master Syarat Bayar PT itu (kode · nama) · `uom` → master satuan (`uoms`; nilai =
    kata satuan pertama, mis. "meter") · `department` → nama unit organisasi SDM yang dicocokkan
    `notification_audience._users_in_division`."""
    ent = entity_id if entity_id and entity_id != "all" else ""
    if ref == "payment_term":
        from services import entity_master_service as ems
        rows = await ems.effective_rows("payment-terms", ent)
        out = [{"value": r.get("code"), "label": f"{r.get('code')} · {r.get('name') or r.get('code')}"}
               for r in rows if r.get("code")]
        return sorted(out, key=lambda o: str(o["value"]))
    if ref == "uom":
        rows = await db.uoms.find({}, {"_id": 0, "code": 1, "name": 1, "aliases": 1, "status": 1}).to_list(500)
        out = []
        for r in rows:
            if r.get("status") not in (None, "", "active"):
                continue
            kata = (r.get("aliases") or [str(r.get("name") or r.get("code") or "").lower()])[0]
            out.append({"value": kata, "label": str(r.get("name") or kata),
                        "match": sorted({str(x).lower() for x in [r.get("code"), r.get("name"), *(r.get("aliases") or [])]
                                         if x})})
        return sorted(out, key=lambda o: o["label"])
    if ref == "department":
        from services.notification_audience import _ORG_COLL
        q: Dict[str, Any] = {"entity_id": ent} if ent else {}
        rows = await db[_ORG_COLL].find(q, {"_id": 0, "name": 1}).to_list(500)
        names = sorted({str(r.get("name") or "").strip() for r in rows if str(r.get("name") or "").strip()})
        return [{"value": n, "label": n} for n in names]
    return []


async def _check_ref(entry: Dict[str, Any], value: Any, entity_id: str) -> None:
    """Nilai kunci ber-`ref` harus ada di pilihannya (kosong hanya bila bawaannya kosong)."""
    teks = str(value or "").strip()
    if not teks:
        if str(entry.get("default") or "").strip():
            raise ConfigWriteError(f"'{entry['label']}' wajib dipilih.")
        return
    opsi = await ref_options(entry["ref"], entity_id)
    cocok = {str(o["value"]).lower() for o in opsi}
    for o in opsi:
        cocok |= set(o.get("match") or [])
    if teks.lower() not in cocok:
        daftar = ", ".join(str(o["label"]) for o in opsi[:12]) or "belum ada"
        raise ConfigWriteError(f"'{entry['label']}': butir '{teks}' tidak dikenal. Pilihan: {daftar}.")


async def entity_overrides(items: List[Dict[str, Any]], entity_ids: List[str]) -> List[Dict[str, Any]]:
    """KF-T4 (KF-UX-09) — cakupan grup: tiap butir mendapat `entity_overrides` = PT (di antara `entity_ids`) yang punya
    nilai sendiri untuk kunci itu: `[{entity_id, entity_label, value}]`."""
    keys = [it["key"] for it in items]
    ids = [e for e in dict.fromkeys(entity_ids or []) if e and e != "all"]
    nama = {d["id"]: (d.get("short_name") or d.get("legal_name") or d.get("name") or d["id"])
            async for d in db.business_entities.find({"id": {"$in": ids}},
                                                     {"_id": 0, "id": 1, "short_name": 1, "legal_name": 1, "name": 1})}
    per_key: Dict[str, List[Dict[str, Any]]] = {k: [] for k in keys}
    entries = [registry.require(k) for k in keys]
    at = datetime.now(timezone.utc)
    for eid in ids:
        ctx = {"entity_id": eid}
        pre: Dict[str, Any] = {"rows": await _stored_rows(keys, ctx)}
        for sc in {e["legacy_scope"] for e in entries}:
            pre[f"legacy:{sc}"] = await _legacy_doc(sc)
        pre[f"legacy:{eid}"] = await _legacy_doc(eid)
        for e in entries:
            if "entity" not in (e.get("scopes") or []):
                continue
            res = await resolve(e["key"], ctx, at=at, preloaded=pre)
            if res["source_layer"] in ("entity", "legacy_entity"):
                per_key[e["key"]].append({"entity_id": eid, "entity_label": nama.get(eid, eid),
                                          "value": res["stored_value"]})
    for it in items:
        it["entity_overrides"] = per_key.get(it["key"], [])
    return items


# ── tulis (append-only) ─────────────────────────────────────────────────────
class ConfigWriteError(ValueError):
    """Nilai/scope tidak sah — pesan siap tampil ke user (Bahasa Indonesia)."""


#: KF-T4 — sasaran lapisan untuk pesan "Pilih … dulu." (tanpa id lapisan).
SASARAN = {"entity": "PT", "customer": "pelanggan", "supplier": "pemasok", "product": "produk",
           "document": "dokumen"}
#: KF-T4 (KF-12) — alasan bawaan "kembalikan"/"cabut" untuk kunci yang tidak wajib beralasan.
ALASAN_BAWAAN_RESET = "Dikembalikan ke nilai bawaan sistem"
ALASAN_BAWAAN_CLEAR = "Kembali mengikuti nilai grup"


def alasan_wajib(entry: Dict[str, Any]) -> str:
    return f"'{entry['label']}' berisiko tinggi — alasan wajib diisi."


async def set_value(key: str, value: Any, *, scope_type: str = "global", scope_id: str = "",
                    actor: str = "system", actor_id: str = "", reason: str = "",
                    effective_from: str = "", ctx: Optional[Dict[str, Any]] = None,
                    approved_by: str = "") -> Dict[str, Any]:
    """Simpan perubahan sebagai baris BARU (append-only) + proyeksikan ke penyimpanan lama."""
    entry = registry.require(key)
    if entry["status"] != "active":
        raise ConfigWriteError(
            f"'{entry['label']}' tidak dipakai sistem saat ini — {entry['not_used_reason']}")
    if scope_type not in entry["scopes"]:
        # KF-T5 — pesan tanpa istilah "level"/id lapisan: "“{label}” tidak bisa dibedakan per pelanggan."
        raise ConfigWriteError(f"“{entry['label']}” tidak bisa dibedakan {PER_LAPISAN.get(scope_type, scope_type)}.")
    if scope_type != "global" and not scope_id:
        raise ConfigWriteError(f"Pilih {SASARAN.get(scope_type, 'sasarannya')} dulu.")
    if entry["requires_reason"] and not (reason or "").strip():
        raise ConfigWriteError(alasan_wajib(entry))
    try:
        clean = registry.coerce(entry, value)
        if key == "approval.extra_levels":   # KP-T3 — isi jenjang tambahan: peran dikenal, nilai minimal ≥ 0
            from services.config_service import validate_extra_levels
            validate_extra_levels(clean)
        from services.reminder_policy import periksa_nilai   # KP-T7 — penerima/rantai/peran/hari/nomor PIC pengingat
        clean = periksa_nilai(key, clean)
    except ValueError as exc:
        raise ConfigWriteError(str(exc)) from exc
    if entry.get("ref"):   # KF-T4 — rujukan master harus ada di pilihannya (PT sasaran bila lapisan PT)
        await _check_ref(entry, clean, scope_id if scope_type == "entity" else (ctx or {}).get("entity_id", ""))

    eff = (effective_from or "").strip() or _iso_now()
    if _as_dt(eff) is None:
        raise ConfigWriteError("Tanggal 'berlaku sejak' tidak valid (pakai format ISO).")

    prev = await resolve(key, {**(ctx or {}), **_ctx_for(scope_type, scope_id)})
    row = {
        "id": new_id("cfgv"),
        "key": key,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "value": clean,
        "prev_value": prev["stored_value"],   # KF-T3 — riwayat = perubahan nilai TERSIMPAN (bukan nilai penimpa)
        "prev_source_layer": prev["source_layer"],
        "effective_from": eff,
        "effective_to": "",
        "reason": (reason or "").strip(),
        "changed_by": actor,
        "changed_by_id": actor_id,
        "approved_by": approved_by,
        "risk": entry["risk"],
        "changed_at": _iso_now(),
        "created_at": _iso_now(),
        "applied_at": "",
    }
    await db[COLL].insert_one(dict(row))
    if _is_due(row, datetime.now(timezone.utc)):
        await _project(entry, scope_type, scope_id, clean, actor)
        await db[COLL].update_one({"id": row["id"]}, {"$set": {"applied_at": _iso_now()}})
        row["applied_at"] = row["changed_at"]
    else:
        _catat_jadwal(_as_dt(eff))           # KF-T3 — `ensure_due_applied` tahu kapan harus menerapkan
    row.pop("_id", None)
    return row


def _ctx_for(scope_type: str, scope_id: str) -> Dict[str, Any]:
    field = CTX_FIELD.get(scope_type)
    return {field: scope_id} if field and scope_id else {}


async def _project(entry: Dict[str, Any], scope_type: str, scope_id: str,
                   value: Any, actor: str) -> None:
    """Tuliskan nilai ke `system_settings` supaya mesin lama langsung ikut berubah.

    Hanya level `global` & `entity` yang punya padanan di penyimpanan lama. Level
    lain (customer/supplier/product/document) HANYA dibaca lewat resolver — karena itu
    registry hanya mengizinkan level tersebut untuk kunci yang mesinnya sudah memakai resolver.

    PK-46 — kunci `bertanggal` TIDAK diproyeksikan: penyimpanan lama tidak bertanggal, sehingga nilai baru yang
    diproyeksikan akan ikut terbaca untuk tanggal lampau. Pembacanya memakai `resolve(key, ctx, at=…)`.
    """
    if entry.get("bertanggal"):
        return
    if scope_type == "global":
        target_scope = entry["legacy_scope"]
    elif scope_type == "entity":
        if entry["legacy_scope"] != "global":
            # FASE E-4 (E4.5) — dokumen setelan operasional (`hr`/`uom`/`lot`/
            # `receiving`/`makloon`) tidak punya varian per badan usaha di
            # penyimpanan lama, jadi TIDAK ada yang bisa diproyeksikan. Override
            # badan usaha tetap berlaku karena pembacanya memakai
            # `entity_overlay()` di atas nilai globalnya.
            return
        target_scope = scope_id
    else:
        return
    await db.system_settings.update_one(
        {"scope": target_scope},
        {"$set": {entry["legacy_path"]: value, "updated_at": _iso_now(), "updated_by": actor},
         "$setOnInsert": {"id": new_id("set"), "scope": target_scope, "created_at": _iso_now()}},
        upsert=True,
    )


async def clear_layer(key: str, *, scope_type: str, scope_id: str = "",
                      actor: str = "system", actor_id: str = "",
                      reason: str = "") -> Dict[str, Any]:
    """FASE E-4 (E4.6) — KOSONGKAN satu lapisan: "Kembalikan ke global".

    Bedanya dengan `values/reset`: `reset` MENULIS nilai bawaan kode pada lapisan ini
    (jadi lapisannya tetap ada dan tetap menang), sementara fungsi ini MENCABUT
    lapisannya sehingga nilai kembali diwarisi dari lapisan yang lebih umum
    (badan usaha → global → bawaan sistem). Itulah yang sebenarnya diminta pengguna
    ketika menekan "kembalikan ke global"; membedakannya mencegah nilai global yang
    sudah disesuaikan pemilik tertimpa angka bawaan kode.

    Tetap append-only: yang ditulis adalah baris NISAN (`cleared: True`), jadi
    riwayat "pernah diatur X lalu dicabut" tidak hilang.
    """
    entry = registry.require(key)
    if scope_type not in WRITABLE_LAYERS:
        raise ConfigWriteError("Nilai ini tidak bisa dicabut.")
    if scope_type == "global":
        raise ConfigWriteError(
            "Aturan grup tidak punya nilai di atasnya untuk diikuti. "
            "Pakai 'Pakai nilai bawaan sistem' bila ingin kembali ke nilai awal sistem.")
    if not scope_id:
        raise ConfigWriteError(f"Pilih {SASARAN.get(scope_type, 'sasarannya')} dulu.")
    # KF-T4 (KF-12) — kunci berisiko tinggi: mencabut nilai khusus juga perubahan, alasannya wajib (tanpa alasan otomatis).
    if entry["requires_reason"] and not (reason or "").strip():
        raise ConfigWriteError(alasan_wajib(entry))

    prev = await resolve(key, _ctx_for(scope_type, scope_id))
    row = {
        "id": new_id("cfgv"), "key": key,
        "scope_type": scope_type, "scope_id": scope_id,
        "value": None, "cleared": True,
        "prev_value": prev["stored_value"], "prev_source_layer": prev["source_layer"],   # KF-T3 — nilai tersimpan
        "effective_from": _iso_now(), "effective_to": "",
        "reason": (reason or "").strip() or ALASAN_BAWAAN_CLEAR,
        "changed_by": actor, "changed_by_id": actor_id, "approved_by": "",
        "risk": entry["risk"], "changed_at": _iso_now(), "created_at": _iso_now(),
        "applied_at": _iso_now(),
    }
    await db[COLL].insert_one(dict(row))
    # Bersihkan juga proyeksi di penyimpanan lama, kalau ada — kalau tidak, mesin
    # lama akan tetap membaca angka yang sudah dicabut (bug senyap).
    if scope_type == "entity" and entry["legacy_scope"] == "global":
        await db.system_settings.update_one(
            {"scope": scope_id}, {"$unset": {entry["legacy_path"]: ""}})
        # Jangan tinggalkan CANGKANG KOSONG. `$unset` membuang nilainya tetapi baris
        # `system_settings` per badan usaha tetap ada — tanpa satu pun setelan di
        # dalamnya. Baris hampa itu tak mengubah perilaku (pembaca jatuh ke global),
        # tetapi ia BERTAMBAH permanen setiap kali sebuah override dicabut: layar
        # Pusat Pengaturan menampilkan "ada override untuk PT ini" yang isinya nol,
        # dan INV-GATE-01 memerah `system_settings +N` pada gate yang menjalankan
        # alur cabut-override (terukur 2026-08-24: +4 pada satu gate --full).
        # "Kembalikan ke global" karena itu berarti barisnya IKUT hilang.
        sisa = await db.system_settings.find_one({"scope": scope_id})
        if sisa is not None:
            META = {"_id", "id", "scope", "created_at", "updated_at", "updated_by"}
            # `$unset` pada jalur bersarang (mis. `ar.denda_rate_pct_per_month`)
            # meninggalkan INDUKNYA sebagai wadah kosong (`ar: {}`) — jadi "kosong"
            # harus dinilai dari ISI, bukan dari ada/tidaknya kunci.
            kosong = [k for k, v in sisa.items()
                      if k not in META and v in ({}, None, "")]
            isi = [k for k, v in sisa.items()
                   if k not in META and v not in ({}, None, "")]
            if not isi:
                await db.system_settings.delete_one({"_id": sisa["_id"]})
            elif kosong:
                await db.system_settings.update_one(
                    {"_id": sisa["_id"]}, {"$unset": {k: "" for k in kosong}})
    row.pop("_id", None)
    after = await resolve(key, _ctx_for(scope_type, scope_id))
    row["value_now"] = after["value"]
    row["source_layer_now"] = after["source_layer"]
    row["source_label_now"] = after["source_label"]
    return row


def _put(doc: Dict[str, Any], path: str, value: Any) -> None:
    """Tulis nilai ke dot-path (membuat sub-dict bila perlu)."""
    parts = path.split(".")
    cur = doc
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


async def entity_overlay(legacy_scope: str, entity_id: str) -> Dict[str, Any]:
    """FASE E-4 (E4.5) — HANYA nilai yang benar-benar ditimpa satu badan usaha.

    Dokumen setelan operasional (`system_settings{scope:"hr"|"uom"|"lot"|"receiving"|
    "makloon"}`) dulu **hanya bisa global**: BPJS, presisi satuan, ketatnya nomor lot,
    toleransi makloon — satu nilai memaksa seluruh grup. Padahal PT Kain Suka Cita
    (PKP, karyawan tetap) dan CV Kanda Suka (non-PKP, borongan) memang berbeda.

    Fungsi ini mengembalikan dokumen bersarang berisi **hanya** kunci yang lapisan
    pemenangnya = badan usaha. Sengaja tidak mengembalikan seluruh nilai efektif:
    dengan begitu pemanggil cukup menimpa dokumen globalnya (`deep_merge`) dan
    perilaku lama tetap identik bila belum ada override sama sekali — nol risiko
    regresi untuk badan usaha yang tidak mengatur apa pun.
    """
    ent = (entity_id or "").strip()
    if not ent or ent == "all":
        return {}
    entries = [e for e in registry.all_entries()
               if e.get("legacy_scope") == legacy_scope and "entity" in e.get("scopes", [])]
    if not entries:
        return {}
    keys = [e["key"] for e in entries]
    ctx = {"entity_id": ent}
    pre: Dict[str, Any] = {"rows": await _stored_rows(keys, ctx)}
    pre[f"legacy:{legacy_scope}"] = await _legacy_doc(legacy_scope)
    pre[f"legacy:{ent}"] = await _legacy_doc(ent)
    at = datetime.now(timezone.utc)
    out: Dict[str, Any] = {}
    for e in entries:
        res = await resolve(e["key"], ctx, at=at, preloaded=pre)
        if res["source_layer"] in ("entity", "legacy_entity"):
            _put(out, e["legacy_path"], res["value"])
    return out


async def apply_due_values() -> Dict[str, int]:
    """Terapkan perubahan berjadwal yang sudah jatuh tempo (idempotent).

    Dipanggil oleh `ensure_due_applied` (pembaca lama), job penjadwal `config_apply_due`, dan saat membaca Pusat
    Pengaturan, sehingga nilai "berlaku sejak" otomatis aktif tanpa intervensi manual. KF-T3 — baris yang dibatalkan
    dilewati; `applied_at` diisi bersyarat (sekali saja, juga bila dua pemanggil berjalan bersamaan).
    """
    now = datetime.now(timezone.utc)
    applied = 0
    cur = db[COLL].find({"applied_at": ""}, {"_id": 0})
    pending: List[Dict[str, Any]] = [r async for r in cur if not r.get("cancelled_at") and _is_due(r, now)]
    pending.sort(key=lambda r: (str(r.get("effective_from")), str(r.get("created_at"))))
    for row in pending:
        entry = registry.get(row["key"])
        if not entry:
            continue
        await _project(entry, row["scope_type"], row.get("scope_id", ""),
                       row["value"], row.get("changed_by", "scheduler"))
        res = await db[COLL].update_one({"id": row["id"], "applied_at": "", "cancelled_at": {"$exists": False}},
                                        {"$set": {"applied_at": _iso_now()}})
        if getattr(res, "modified_count", 1):
            applied += 1
    await _muat_jadwal()
    return {"applied": applied, "pending": len(pending) - applied}


# ── KF-T3 (KF-09) — jadwal diterapkan begitu jatuh tempo ────────────────────────────────────────────────────────────
#: Cache memori proses: waktu jatuh tempo terdekat dari baris `applied_at == ""` tanpa `cancelled_at`.
#: `{}` = belum dimuat; `{"dimuat": True, "berikut": None}` = tidak ada jadwal tertunda (nol kueri).
#: ASUMSI (unit KF-T3): satu proses server; proses lain baru segar saat job lima menit berjalan.
_JATUH_TEMPO: Dict[str, Any] = {}


async def _muat_jadwal() -> None:
    berikut: Optional[datetime] = None
    async for r in db[COLL].find({"applied_at": ""}, {"_id": 0, "key": 1, "effective_from": 1, "cancelled_at": 1}):
        if r.get("cancelled_at") or not registry.get(r.get("key", "")):
            continue                         # baris kunci yang sudah tidak terdaftar tidak pernah diterapkan
        t = _as_dt(r.get("effective_from")) or datetime.min.replace(tzinfo=timezone.utc)
        if berikut is None or t < berikut:
            berikut = t
    _JATUH_TEMPO.clear()
    _JATUH_TEMPO.update({"dimuat": True, "berikut": berikut})


def _catat_jadwal(t: Optional[datetime]) -> None:
    """`set_value` berjadwal: majukan waktu jatuh tempo terdekat bila cache sudah dimuat."""
    if not _JATUH_TEMPO.get("dimuat") or t is None:
        return
    cur = _JATUH_TEMPO.get("berikut")
    if cur is None or t < cur:
        _JATUH_TEMPO["berikut"] = t


def _lupakan_jadwal() -> None:
    """Pembatalan jadwal: cache dihitung ulang pada pembacaan berikutnya."""
    _JATUH_TEMPO.clear()


async def ensure_due_applied() -> Dict[str, int]:
    """Terapkan jadwal yang sudah jatuh tempo SEBELUM pembaca lama membaca `system_settings`.

    Dipanggil baris pertama `config_service.get_global_settings()` dan `policy_settings()`. Tanpa jadwal tertunda
    biayanya nol kueri (sesudah pemuatan pertama)."""
    if not _JATUH_TEMPO.get("dimuat"):
        await _muat_jadwal()
    berikut = _JATUH_TEMPO.get("berikut")
    if berikut is None or datetime.now(timezone.utc) < berikut:
        return {"applied": 0, "pending": 0}
    return await apply_due_values()


async def job_config_apply_due() -> Dict[str, Any]:
    """Job penjadwal `config_apply_due` (setiap 5 menit) — jaring pengaman untuk proses lain / baris tanpa pembaca."""
    res = await apply_due_values()
    return {**res, "scanned": res["applied"] + res["pending"],
            "detail": f"{res['applied']} perubahan pengaturan diterapkan"}


class ScheduleError(ValueError):
    """KF-T3 — pembatalan jadwal ditolak; `status` = kode HTTP, pesan siap tampil."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


async def scheduled_row(row_id: str) -> Dict[str, Any]:
    row = await db[COLL].find_one({"id": row_id}, {"_id": 0}) if row_id else None
    if not row or not registry.get(row.get("key", "")):
        raise ScheduleError(404, "Jadwal perubahan tidak ditemukan.")
    return row


async def cancel_scheduled(row_id: str, *, actor: str = "system", actor_id: str = "",
                           reason: str = "") -> Dict[str, Any]:
    """Batalkan satu baris berjadwal yang belum berlaku. Nilai yang berlaku sekarang tidak berubah."""
    row = await scheduled_row(row_id)
    entry = registry.require(row["key"])
    if row.get("cancelled_at"):
        raise ScheduleError(409, "Jadwal ini sudah dibatalkan.")
    sudah = ("Perubahan ini sudah berlaku, jadi tidak bisa dibatalkan. Simpan nilai baru bila ingin mengubahnya.")
    if row.get("applied_at") or _is_due(row, datetime.now(timezone.utc)):
        raise ScheduleError(409, sudah)
    alasan = (reason or "").strip()
    if entry["requires_reason"] and not alasan:
        raise ScheduleError(400, "Alasan pembatalan wajib diisi.")
    tanda = {"cancelled_at": _iso_now(), "cancelled_by": actor, "cancelled_by_id": actor_id, "cancel_reason": alasan}
    res = await db[COLL].update_one(
        {"id": row_id, "applied_at": "", "cancelled_at": {"$exists": False}}, {"$set": tanda})
    if not getattr(res, "modified_count", 1):
        now = await db[COLL].find_one({"id": row_id}, {"_id": 0}) or {}
        raise ScheduleError(409, "Jadwal ini sudah dibatalkan." if now.get("cancelled_at") else sudah)
    _lupakan_jadwal()
    return {**row, **tanda}


def _awal_hari_wib(tanggal: str, tambah_hari: int = 0) -> str:
    """'YYYY-MM-DD' (tanggal WIB) → awal hari itu dalam ISO UTC, bentuk yang sama dengan `changed_at` (`now_iso`)."""
    from datetime import date, timedelta
    try:
        d = date.fromisoformat(str(tanggal).strip()[:10]) + timedelta(days=tambah_hari)
    except ValueError as exc:
        raise ConfigWriteError("Tanggal saringan riwayat tidak valid (pakai tahun-bulan-tanggal).") from exc
    awal = datetime(d.year, d.month, d.day, tzinfo=timezone(timedelta(hours=7)))
    return awal.astimezone(timezone.utc).isoformat()


async def history(key: str = "", scope_type: str = "", scope_id: str = "",
                  limit: int = 100, *, keys: Optional[List[str]] = None, changed_by: str = "",
                  date_from: str = "", date_to: str = "", offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    """Riwayat perubahan (terbaru dulu): siapa, kapan, dari→ke, alasan.

    KF-T4 (KF-UX-19) — saringan kelompok (`keys` = kunci kelompok itu), orang (`changed_by`, sebagian nama), rentang
    tanggal (`date_from`/`date_to`, YYYY-MM-DD, WIB tidak diubah: dibandingkan dengan awalan `changed_at`) dan halaman
    (`offset`). Mengembalikan `(baris, total sebelum dipotong halaman)`."""
    import re as _re
    q: Dict[str, Any] = {}
    if key:
        q["key"] = key
    elif keys is not None:
        q["key"] = {"$in": list(keys)}
    if scope_type:
        q["scope_type"] = scope_type
    if scope_id:
        q["scope_id"] = scope_id
    if changed_by.strip():
        q["changed_by"] = {"$regex": _re.escape(changed_by.strip()), "$options": "i"}
    rentang: Dict[str, Any] = {}
    if date_from.strip():
        rentang["$gte"] = _awal_hari_wib(date_from)
    if date_to.strip():
        rentang["$lt"] = _awal_hari_wib(date_to, tambah_hari=1)
    if rentang:
        q["changed_at"] = rentang
    total = await db[COLL].count_documents(q)
    rows = await (db[COLL].find(q, {"_id": 0}).sort("created_at", -1).skip(max(int(offset), 0)).limit(int(limit))
                  .to_list(int(limit)))
    for r in rows:
        e = registry.get(r["key"])
        r["label"] = e["label"] if e else r["key"]
        r["group"] = e["group"] if e else ""
        r["section"] = e["section"] if e else ""
        r["unit"] = e["unit"] if e else ""
        # KF-T4 — layar memformat nilai riwayat seperti di kartu (label pilihan, rupiah, satuan).
        r["type"] = e["type"] if e else ""
        r["options"] = e["options"] if e else []
        r["cancelled"] = bool(r.get("cancelled_at"))      # KF-T3 — jadwal yang dibatalkan tetap tercatat
        r["scheduled"] = not r["cancelled"] and not _is_due(r, datetime.now(timezone.utc))
    return rows, total


async def ensure_indexes() -> None:
    """Index minimal untuk pembacaan resolver (idempotent, non-fatal)."""
    try:
        await db[COLL].create_index([("key", 1), ("scope_type", 1), ("scope_id", 1),
                                     ("effective_from", 1)], name="cfgv_lookup", background=True)
        await db[COLL].create_index([("applied_at", 1)], name="cfgv_pending", background=True)
        await db[COLL].create_index([("created_at", -1)], name="cfgv_recent", background=True)
    except Exception as exc:  # noqa: BLE001 — index bentrok tidak boleh menggagalkan request
        logger.warning("[ensure_indexes] efek samping gagal diabaikan: %s", exc)  # KN-C10


async def policy_settings(legacy_scope: str, defaults: Dict[str, Any], entity_id: str = "") -> Dict[str, Any]:
    """GN-15 — SATU resolver kebijakan operasional: default → dokumen global → override badan usaha.

    Dipakai `get_settings` lot/makloon/receiving/uom (dulu empat salinan AST identik).
    Tanpa `entity_id` hasilnya = nilai global; `entity_overrides` = kunci yang ditimpa PT.
    """
    await ensure_due_applied()   # KF-T3 (KF-09) — jadwal yang jatuh tempo berlaku sebelum dokumen lama dibaca
    doc = await db.system_settings.find_one({"scope": legacy_scope}, {"_id": 0}) or {}
    out = dict(defaults)
    for key in defaults:
        if doc.get(key) is not None:
            out[key] = doc[key]
    out["updated_at"] = doc.get("updated_at", "")
    out["updated_by"] = doc.get("updated_by", "")
    if entity_id and entity_id != "all":
        ovr = await entity_overlay(legacy_scope, entity_id) or {}
        for key, val in ovr.items():
            if key in defaults:
                out[key] = val
        out["entity_id"] = entity_id
        out["entity_overrides"] = sorted(k for k in ovr if k in defaults)
    return out
