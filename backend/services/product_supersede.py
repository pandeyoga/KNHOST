"""PREP-A (K-OPN-06) — produk "digantikan oleh" (`superseded_by`).

Aturan pemilik 8 Nov 2026: SKU yang salah TIDAK diubah. Kode lama dinonaktifkan dan ditandai
`superseded_by` = id produk pengganti (produk berkode benar / kode induk duplikat). Stok tidak
dipindah (didaftarkan ulang dari fisik), dokumen lama tidak diubah, laporan & riwayat tetap utuh.

Helper kecil ini dipakai paket lain (opname awal, gate) dan pemilih produk:
  * `not_superseded_query()` — saringan Mongo "belum digantikan" untuk pemilih dokumen BARU;
  * `resolve_active(product_id)` — ikuti rantai `superseded_by` sampai produk akhir;
  * `hints(text)` — "SKU X digantikan oleh Y" untuk pencarian dengan SKU lama.
"""
import re
from typing import Any, Dict, List, Optional

from db import db

FIELD = "superseded_by"
MAX_HOPS = 10
_PROJ = {"_id": 0, "id": 1, "sku": 1, "name": 1, "status": 1, FIELD: 1, "legacy_sku": 1,
         "superseded_reason": 1, "superseded_at": 1}


def is_superseded(product: Optional[Dict[str, Any]]) -> bool:
    return bool((product or {}).get(FIELD))


def not_superseded_query() -> Dict[str, Any]:
    """Produk yang BELUM digantikan (field kosong/tidak ada)."""
    return {"$or": [{FIELD: {"$exists": False}}, {FIELD: {"$in": ["", None]}}]}


def exclude_superseded(query: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    q = query or {}
    return {"$and": [q, not_superseded_query()]} if q else not_superseded_query()


async def chain(product_id: str) -> List[Dict[str, Any]]:
    """Rantai [awal, …, akhir] mengikuti `superseded_by`. Berhenti pada siklus/batas lompatan."""
    out: List[Dict[str, Any]] = []
    seen = set()
    pid = product_id
    while pid and pid not in seen and len(out) <= MAX_HOPS:
        seen.add(pid)
        doc = await db.products.find_one({"id": pid}, _PROJ)
        if not doc:
            break
        out.append(doc)
        pid = doc.get(FIELD) or ""
    return out


async def resolve_active(product_id: str) -> Optional[Dict[str, Any]]:
    """Produk akhir yang menggantikan `product_id` (dirinya sendiri bila tidak digantikan).

    None bila produk tidak ada, rantainya putus (pengganti hilang), atau berputar.
    Hasilnya bisa saja nonaktif (mis. NONAKTIFKAN tanpa pengganti) — cek `status` di pemanggil.
    """
    rows = await chain(product_id)
    if not rows:
        return None
    last = rows[-1]
    if last.get(FIELD):          # pengganti tidak ditemukan / siklus / terlalu panjang
        return None
    return await db.products.find_one({"id": last["id"]}, {"_id": 0})


def hint_text(old: Dict[str, Any], target: Optional[Dict[str, Any]]) -> str:
    if not target:
        return f"SKU {old.get('sku')} sudah digantikan — produk penggantinya tidak ditemukan."
    return f"SKU {old.get('sku')} digantikan oleh {target.get('sku')} — {target.get('name', '')}".rstrip(" —")


async def hints(text: str, visible: Optional[Dict[str, Any]] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Petunjuk untuk pencarian yang PERSIS SKU lama (atau `legacy_sku`) dari produk tergantikan."""
    q = (text or "").strip()
    if len(q) < 2:
        return []
    exact = {"$regex": f"^{re.escape(q)}$", "$options": "i"}
    match: Dict[str, Any] = {"$and": [{"$or": [{"sku": exact}, {"legacy_sku": exact}]},
                                      {FIELD: {"$nin": ["", None], "$exists": True}}]}
    if visible:
        match["$and"].append(visible)
    rows = await db.products.find(match, _PROJ).limit(limit).to_list(limit)
    out = []
    for old in rows:
        target = await resolve_active(old["id"])
        out.append({"product_id": old["id"], "sku": old.get("sku"), "name": old.get("name"),
                    "superseded_by": ({"id": target["id"], "sku": target.get("sku"), "name": target.get("name"),
                                       "status": target.get("status", "active")} if target else None),
                    "reason": old.get("superseded_reason", ""), "message": hint_text(old, target)})
    return out


async def sku_map(ids: List[str]) -> Dict[str, str]:
    """{id: sku} untuk anotasi `superseded_by_sku` (daftar besar: satu query)."""
    ids = sorted({i for i in ids if i})
    if not ids:
        return {}
    rows = await db.products.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "sku": 1}).to_list(len(ids) + 1)
    return {r["id"]: r.get("sku", "") for r in rows}


async def annotate(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tambah `superseded_by_sku` pada produk tergantikan (tanpa membuang barisnya)."""
    m = await sku_map([p.get(FIELD) for p in products if p.get(FIELD)])
    for p in products:
        if p.get(FIELD):
            p["superseded_by_sku"] = m.get(p[FIELD], "")
    return products
