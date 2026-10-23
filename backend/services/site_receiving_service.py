"""UAT 24 Okt (P9, fase F1) — LOKASI (site) sebagai tujuan kirim & konteks kerja.

Model pemilik: Lokasi = area berisi beberapa gudang ber-PERAN (transit / penerimaan pusat / penyimpanan / retur).
PO dikirim ke LOKASI; barang masuk lewat gudang transit lokasi itu untuk dihitung & dilabel, lalu langsung ke SO
yang menunggu atau dipindah ke gudang simpan DI LOKASI YANG SAMA.

Sebelumnya setiap jalur menebak gudangnya sendiri (PO = gudang pilihan bebas termasuk nonaktif, OD = gudang
dedicated pertama, reorder = gudang pertama koleksi). Modul ini satu-satunya tempat menurunkan:
* gudang PENERIMAAN sebuah lokasi untuk satu PT (`receiving_warehouse`),
* lokasi bawaan PT / pengguna (`default_site_for_entity`, `default_site_for_user`),
* tujuan dokumen dari `ship_to_site_id` ATAU `warehouse_id` lama (`resolve_destination`).
Keputusan pemilik P9-K1 (24 Okt): lokasi bergudang tunggal (Soreang, Jakarta) — gudangnya merangkap transit+simpan.
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from db import db
from services import warehouse_scope_service as whscope

RECEIVING_ROLES = ("central_inbound", "transit")


def _rank(w: Dict[str, Any]) -> Tuple[int, int, str]:
    roles = set(w.get("roles") or [])
    return (0 if "central_inbound" in roles else 1 if "transit" in roles else 2,
            0 if w.get("sharing_mode") == "dedicated" else 1, str(w.get("code") or ""))


async def site_doc(site_id: str) -> Optional[Dict[str, Any]]:
    if not site_id:
        return None
    return await db.warehouse_sites.find_one({"id": site_id}, {"_id": 0})


async def usable_site_warehouses(site_id: str, entity_id: Optional[str]) -> List[Dict[str, Any]]:
    """Gudang AKTIF di lokasi itu yang boleh dipakai PT (bersama, atau khusus PT itu)."""
    q = {"$and": [{"site_id": site_id}, {"active": {"$ne": False}}, whscope.usable_query(entity_id)]}
    return await db.warehouses.find(q, {"_id": 0}).to_list(200)


async def receiving_warehouse(site_id: str, entity_id: Optional[str]) -> Dict[str, Any]:
    """Gudang penerimaan lokasi untuk PT: ber-peran penerimaan pusat/transit; bila lokasi hanya punya SATU gudang
    yang boleh dipakai, gudang itu (merangkap). 400 berkalimat jelas bila lokasi tak punya gudang yang sah."""
    site = await site_doc(site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Lokasi kirim tidak ditemukan")
    rows = await usable_site_warehouses(site_id, entity_id)
    inbound = [w for w in rows if set(w.get("roles") or []) & set(RECEIVING_ROLES)]
    if inbound:
        return sorted(inbound, key=_rank)[0]
    if len(rows) == 1:
        return rows[0]
    raise HTTPException(status_code=400, detail=(
        f"Lokasi {site.get('name')} belum punya gudang penerimaan (peran Transit / Penerimaan Pusat) yang boleh "
        "dipakai badan usaha ini. Atur perannya di Data Gudang."))


async def site_of_warehouse(warehouse_id: str) -> str:
    w = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0, "site_id": 1}) if warehouse_id else None
    return (w or {}).get("site_id") or ""


async def default_site_for_entity(entity_id: Optional[str]) -> str:
    """Lokasi bawaan PT: `business_entities.default_site_id`, else lokasi gudang dedicated PT itu, else lokasi
    pertama yang punya gudang penerimaan sah untuk PT tsb."""
    if not entity_id or entity_id == "all":
        return ""
    ent = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "default_site_id": 1})
    if (ent or {}).get("default_site_id"):
        return ent["default_site_id"]
    ded = await db.warehouses.find_one({"entity_ids": entity_id, "sharing_mode": "dedicated", "active": {"$ne": False},
                                        "site_id": {"$nin": [None, ""]}}, {"_id": 0, "site_id": 1})
    if ded:
        return ded["site_id"]
    async for s in db.warehouse_sites.find({}, {"_id": 0, "id": 1}).sort("name", 1):
        try:
            await receiving_warehouse(s["id"], entity_id)
            return s["id"]
        except HTTPException:
            continue
    return ""


def default_site_for_user(user: Optional[Dict[str, Any]]) -> str:
    sites = (user or {}).get("location_site_ids") or []
    return sites[0] if sites else ""


async def resolve_destination(entity_id: Optional[str], ship_to_site_id: str = "", warehouse_id: str = "", *,
                              action: str = "menerima barang di sini") -> Dict[str, Any]:
    """Tujuan penerimaan sebuah dokumen beli/terima.

    * `ship_to_site_id` diisi → gudang penerimaan lokasi itu (jalur baru, PO dikirim ke LOKASI).
    * hanya `warehouse_id` (klien/skrip lama) → gudang penerimaan LOKASI gudang itu (barang tetap masuk lewat
      transit); gudang tanpa lokasi dipakai apa adanya (kompatibel).
    Hasil: {warehouse, site_id, site_name} — `warehouse` sudah lolos `assert_usable` (aktif & boleh dipakai PT).
    """
    site_id = (ship_to_site_id or "").strip()
    if not site_id and warehouse_id:
        site_id = await site_of_warehouse(warehouse_id)
    if site_id:
        wh = await receiving_warehouse(site_id, entity_id)
    elif warehouse_id:
        wh = await whscope.assert_usable(warehouse_id, entity_id, action=action, field_label="Gudang penerimaan")
    else:
        raise HTTPException(status_code=400, detail="Lokasi kirim wajib dipilih")
    wh = await whscope.assert_usable(wh["id"], entity_id, action=action, field_label="Gudang penerimaan")
    site = await site_doc(site_id) if site_id else None
    return {"warehouse": wh, "site_id": site_id, "site_name": (site or {}).get("name", "")}
