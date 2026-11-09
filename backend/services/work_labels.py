"""FIX-1 (K-B1-02, B2a FLW-IN-07) — label baris daftar PEKERJAAN FISIK lintas PT.

Daftar tugas gudang kini disaring per GEDUNG dalam lokasi kerja (bukan PT aktif), jadi setiap baris wajib
menyebut **PT pemilik** dan **jenis tugas** — tanpa itu tugas PT lain di gedung yang sama tercampur tanpa penanda
(keluhan pemilik "tugas barang keluar/masuk tercampur"). Hanya label tampilan; tidak mengubah status/stok.
"""
from typing import Any, Dict, Iterable, List

from db import db

# (flow_type, source_type, task_subtype) → (kode, label). Urutan cocok: subtype dulu, lalu source, lalu flow.
_KIND_BY_SUBTYPE = {
    "sample_cut": ("potong_sample", "Potong sample"),
    "makloon_receipt": ("terima_makloon", "Terima hasil makloon"),
}
_KIND_BY_SOURCE = {
    ("inbound", "purchase_order"): ("terima_po", "Terima PO"),
    ("inbound", "makloon_order"): ("terima_makloon", "Terima hasil makloon"),
    ("inbound", "sales_return"): ("terima_retur", "Terima retur"),
    ("inbound", "transfer"): ("transfer_masuk", "Transfer masuk"),
    ("outbound", "sales_order"): ("ambil_so", "Ambil pesanan (SO)"),
    ("outbound", "transfer"): ("transfer_keluar", "Transfer keluar"),
    ("outbound", "makloon_order"): ("kirim_makloon", "Kirim bahan makloon"),
}
_KIND_BY_FLOW = {"inbound": ("masuk", "Barang masuk"), "outbound": ("keluar", "Barang keluar"),
                 "transfer": ("transfer", "Transfer"), "picking": ("ambil", "Ambil")}


def task_kind(task: Dict[str, Any]) -> Dict[str, str]:
    sub = str(task.get("task_subtype") or "")
    if sub in _KIND_BY_SUBTYPE:
        code, label = _KIND_BY_SUBTYPE[sub]
    else:
        flow = str(task.get("flow_type") or task.get("type") or "")
        code, label = _KIND_BY_SOURCE.get((flow, str(task.get("source_type") or "")),
                                          _KIND_BY_FLOW.get(flow, ("lain", "Tugas gudang")))
    return {"task_kind": code, "task_kind_label": label}


async def entity_names(ids: Iterable[str]) -> Dict[str, str]:
    want = [i for i in set(ids) if i]
    if not want:
        return {}
    return {e["id"]: (e.get("short_name") or e.get("legal_name") or e["id"]) async for e in db.business_entities.find(
        {"id": {"$in": want}}, {"_id": 0, "id": 1, "short_name": 1, "legal_name": 1})}


async def label_rows(rows: List[Dict[str, Any]], *, entity_field: str = "entity_id", kinds: bool = True) -> List[Dict[str, Any]]:
    """Tambahkan `owner_entity_name` (PT pemilik dokumen) + jenis tugas ke tiap baris (di tempat)."""
    def owner(r):
        return r.get(entity_field) or r.get("owner_entity_id") or r.get("entity_id") or ""
    names = await entity_names(owner(r) for r in rows)
    for r in rows:
        eid = owner(r)
        r["work_entity_id"] = eid
        r["work_entity_name"] = names.get(eid, "")
        if kinds:
            r.update(task_kind(r))
    return rows
