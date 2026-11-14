"""KF-T5 — aturan khusus per pelanggan dan per barang (`docs/blueprint/unit/KF-T5.md`).

Kunci registry yang `scopes`-nya memuat `customer`/`product` bisa diberi nilai sendiri untuk satu pelanggan/barang.
Nilainya disimpan seperti lapisan lain di `config_values` (`scope_type` + `scope_id` = id pelanggan/barang) dan dibaca
resolver; modul ini hanya menambah tiga hal untuk layar dan penjaga tulis:

* `pastikan_sasaran_tulis` — sasaran lapisan harus ada (404) dan pelanggan harus milik PT dalam cakupan pelaku (403,
  pesan baku `resolve_requested_entity`). Lapisan pemasok/dokumen belum punya layar → 400.
* `tambah_nilai_lapisan` — butir `GET /api/config/effective?scope=…`: hanya kunci berlapis itu, plus `layer_value`
  (nilai milik pelanggan/barang itu, atau `None`) dan `inherited_value` (nilai tanpa lapisan itu: hasil PT/grup).
* `daftar_lapisan` — `GET /api/config/layers`: satu baris per pelanggan/barang yang punya nilai sendiri (nisan
  "kembali ikut aturan PT" tidak dihitung), bernama, terbaru dulu, paling banyak 200 baris.
* `beri_nama` — baris riwayat ber-lapisan pelanggan/barang diberi nama sasarannya (`scope_label`).
"""
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException

from db import db
from services import config_resolver as resolver

LAPISAN_KHUSUS = ("customer", "product")
BELUM_TERSEDIA = ("supplier", "document")
MAKS_BARIS = 200
_KOLEKSI = {"customer": "customers", "product": "products"}
_TIDAK_ADA = {"customer": "Pelanggan tidak ditemukan.", "product": "Barang tidak ditemukan."}
_PESAN_BELUM = "Aturan khusus per pemasok atau per dokumen belum tersedia."


def periksa_lapisan(scope_type: str) -> str:
    """Lapisan aturan khusus yang sah untuk layar (`customer`/`product`); selain itu 400."""
    if scope_type in BELUM_TERSEDIA:
        raise HTTPException(status_code=400, detail=_PESAN_BELUM)
    if scope_type not in LAPISAN_KHUSUS:
        raise HTTPException(status_code=400, detail="Aturan khusus hanya bisa dibedakan per pelanggan atau per barang.")
    return scope_type


async def sasaran(scope_type: str, scope_id: str) -> Dict[str, Any]:
    """Dokumen pelanggan/barang sasaran (id, nama, PT); 404 bila tidak ada."""
    doc = None
    if scope_id:
        doc = await db[_KOLEKSI[scope_type]].find_one(
            {"id": scope_id}, {"_id": 0, "id": 1, "name": 1, "entity_id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail=_TIDAK_ADA[scope_type])
    return doc


async def pastikan_sasaran(ctx: Any, scope_type: str, scope_id: str) -> Dict[str, Any]:
    """N2 — id pelanggan/barang dari klien dibuktikan ada; pelanggan harus milik PT dalam cakupan pelaku.

    Barang berlaku di semua PT grup (tidak ber-PT), jadi cukup dibuktikan ada."""
    from entity_scope import resolve_requested_entity
    periksa_lapisan(scope_type)
    doc = await sasaran(scope_type, scope_id)
    if scope_type == "customer":
        resolve_requested_entity(ctx, doc.get("entity_id") or "")
    return doc


async def tambah_nilai_lapisan(items: List[Dict[str, Any]], scope_type: str,
                               ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Saring ke kunci ber-lapisan `scope_type`, lalu tambah `layer_value` dan `inherited_value` tiap butir."""
    field = resolver.CTX_FIELD[scope_type]
    tanpa = {**ctx, field: ""}
    out: List[Dict[str, Any]] = []
    for it in items:
        if scope_type not in (it.get("scopes") or []):
            continue
        lapisan_nilai = None
        if ctx.get(field):
            res = await resolver.resolve(it["key"], ctx)
            lap = next((x for x in res["explain"] if x.get("layer") == scope_type), None)
            if lap and lap.get("present"):
                lapisan_nilai = lap.get("value")
        warisan = (await resolver.resolve(it["key"], tanpa))["value"]
        out.append({**it, "layer_value": lapisan_nilai, "inherited_value": warisan})
    return out


async def beri_nama(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Baris riwayat ber-lapisan pelanggan/barang diberi `scope_label` (nama), supaya layar tidak menampilkan id."""
    for lapisan, koleksi in _KOLEKSI.items():
        ids = sorted({r.get("scope_id") for r in rows if r.get("scope_type") == lapisan and r.get("scope_id")})
        if not ids:
            continue
        nama = {d["id"]: d.get("name") or "" async for d in db[koleksi].find(
            {"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1})}
        for r in rows:
            if r.get("scope_type") == lapisan and r.get("scope_id"):
                r["scope_label"] = nama.get(r["scope_id"]) or (
                    "Pelanggan sudah dihapus" if lapisan == "customer" else "Barang sudah dihapus")
    return rows


async def daftar_lapisan(key: str, scope_type: str,
                         allowed_entity_ids: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Pelanggan/barang yang punya nilai sendiri untuk `key`: `{"rows": [...], "total": n}`.

    `allowed_entity_ids` (bila diisi) menyaring pelanggan ke PT dalam cakupan pembaca; pelanggan tanpa PT ikut."""
    now = datetime.now(timezone.utc)
    per_sasaran: Dict[str, List[Dict[str, Any]]] = {}
    cur = db[resolver.COLL].find({"key": key, "scope_type": scope_type}, {"_id": 0})
    async for row in cur:
        if row.get("cancelled_at"):          # baris jadwal yang dibatalkan tidak pernah berlaku
            continue
        per_sasaran.setdefault(row.get("scope_id") or "", []).append(row)
    pemenang: List[Dict[str, Any]] = []
    for sid, rows in per_sasaran.items():
        if not sid:
            continue
        rows.sort(key=lambda r: (str(r.get("effective_from") or ""), str(r.get("created_at") or "")))
        val, win, _ = resolver._pick_effective(rows, now)
        if val is resolver._MISSING or not win:
            continue
        pemenang.append({"scope_id": sid, "value": val, "changed_by": win.get("changed_by", ""),
                         "changed_at": win.get("changed_at", ""), "reason": win.get("reason", "")})
    if not pemenang:
        return {"rows": [], "total": 0}
    docs = {d["id"]: d async for d in db[_KOLEKSI[scope_type]].find(
        {"id": {"$in": [p["scope_id"] for p in pemenang]}}, {"_id": 0, "id": 1, "name": 1, "entity_id": 1})}
    izin = set(allowed_entity_ids) if allowed_entity_ids is not None else None
    rows_out: List[Dict[str, Any]] = []
    for p in pemenang:
        d = docs.get(p["scope_id"])
        if scope_type == "customer" and izin is not None and d and d.get("entity_id") and d["entity_id"] not in izin:
            continue
        nama = (d or {}).get("name") or ("Pelanggan sudah dihapus" if scope_type == "customer" else "Barang sudah dihapus")
        rows_out.append({**p, "scope_label": nama})
    rows_out.sort(key=lambda r: str(r.get("changed_at") or ""), reverse=True)
    return {"rows": rows_out[:MAKS_BARIS], "total": len(rows_out)}
