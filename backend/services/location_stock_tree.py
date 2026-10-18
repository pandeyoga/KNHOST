"""L10 LN-100/LN-102 — stok per alamat fisik (Lokasi → Gudang → Zona → Lemari → Rak → Bin).

Sumber tunggal: saldo roll (`inventory_rolls.length_remaining` + status) — bukan snapshot + mutasi.
Induk = jumlah anak karena semua tingkat dihitung dari baris roll yang sama. Owner bukan lokasi:
owner hanya filter/rincian, tidak membentuk node.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from db import db
from services import placement_rules as pr
from services.roll_service import PHYSICAL_STATUS_TO_BUCKET, TRANSIT_STATUS_TO_BUCKET

BUCKETS = ("available", "reserved", "qc_hold", "wip", "in_transit")
BUCKET_LABEL = {"available": "Tersedia", "reserved": "Dipesan/dialokasikan", "qc_hold": "QC / ditahan (tidak tersedia)",
                "wip": "Sedang diproses", "in_transit": "Dalam perjalanan"}
DEFINITIONS = {
    "available": "Roll status available, dikurangi panjang yang dipesan (length_reserved) dan roll yang diklaim perpindahan.",
    "reserved": "Status reserved/committed/picked/packed + panjang dipesan pada roll available.",
    "qc_hold": "Status hold/quarantine/blocked/damaged atau inspeksi menahan roll — tidak pernah dihitung tersedia.",
    "wip": "Status wip (sedang diproses di gudang).",
    "in_transit": "Status in_transit_* dengan warehouse_id gudang ini — tidak berada di bin.",
    "source": "inventory_rolls (saldo roll SSOT), dihitung saat permintaan.",
}
ORDER_HELD = {"reserved", "committed", "picked", "packed"}
QC_HELD = set(pr.QC_STATUSES)


def _bucket(r: Dict[str, Any]) -> List[tuple]:
    st, qty = r.get("status") or "", float(r.get("length_remaining") or 0)
    if st in TRANSIT_STATUS_TO_BUCKET:
        return [("in_transit", qty)]
    if pr.is_held(r) or st in QC_HELD:
        return [("qc_hold", qty)]
    if st in ORDER_HELD:
        return [("reserved", qty)]
    if st == "wip":
        return [("wip", qty)]
    if (r.get("active_movement") or {}).get("id"):
        return [("qc_hold", qty)]
    res = min(qty, float(r.get("length_reserved") or 0))
    return [("available", qty - res)] + ([("reserved", res)] if res > 0 else [])


def _new_node(kind: str, nid: str, name: str) -> Dict[str, Any]:
    return {"kind": kind, "id": nid, "name": name, "rolls": 0, "by_unit": {}, "children": []}


def _add(node: Dict[str, Any], unit: str, parts: List[tuple], count: bool) -> None:
    u = node["by_unit"].setdefault(unit, {b: 0.0 for b in BUCKETS} | {"total": 0.0})
    for b, q in parts:
        u[b] = round(u[b] + q, 4)
        u["total"] = round(u["total"] + q, 4)
    if count:
        node["rolls"] += 1


async def warehouse_tree(wh: Dict[str, Any], owners: Optional[List[str]] = None, site_name: str = "") -> Dict[str, Any]:
    root = _new_node("warehouse", wh["id"], wh.get("name", ""))
    index: Dict[str, List[Dict[str, Any]]] = {}
    for z in wh.get("zones") or []:
        zn = _new_node("zone", z.get("id"), z.get("name", ""))
        root["children"].append(zn)
        for rk in z.get("racks") or []:
            rn = _new_node("lemari", rk.get("id"), rk.get("name", ""))
            zn["children"].append(rn)
            levels = rk.get("levels") or []
            groups = [(lv, lv.get("bins") or []) for lv in levels] or [(None, rk.get("bins") or [])]
            for lv, bins in groups:
                ln = None
                if lv is not None:
                    ln = _new_node("rak", lv.get("id"), lv.get("name", ""))
                    rn["children"].append(ln)
                for b in bins:
                    bn = _new_node("bin", b.get("id"), b.get("code", ""))
                    bn["address"] = " › ".join(x for x in (site_name, wh.get("name", ""), z.get("name", ""), rk.get("name", ""),
                                                          (lv or {}).get("name", ""), b.get("code", "")) if x)
                    (ln or rn)["children"].append(bn)
                    index[b.get("id")] = [n for n in (root, zn, rn, ln, bn) if n is not None]
    unassigned = _new_node("unassigned", f"{wh['id']}:unassigned", "Belum ditempatkan")
    orphan = _new_node("orphan", f"{wh['id']}:orphan", "Alamat yatim (bin tidak ada di master)")
    transit = _new_node("transit", f"{wh['id']}:transit", "Dalam perjalanan")
    by_owner: Dict[str, Dict[str, Any]] = {}
    q: Dict[str, Any] = {"warehouse_id": wh["id"], "length_remaining": {"$gt": 0},
                         "status": {"$in": list(PHYSICAL_STATUS_TO_BUCKET) + list(TRANSIT_STATUS_TO_BUCKET)}}
    if owners is not None:
        q["owner_entity_id"] = {"$in": owners}
    async for r in db.inventory_rolls.find(q, {"_id": 0, "bin_id": 1, "status": 1, "length_remaining": 1, "length_reserved": 1,
                                               "unit": 1, "owner_entity_id": 1, "inspection.hold": 1, "active_movement": 1}):
        parts, unit = _bucket(r), (r.get("unit") or "?")
        if r.get("status") in TRANSIT_STATUS_TO_BUCKET:
            chain = [root, transit]
        elif not r.get("bin_id"):
            chain = [root, unassigned]
        else:
            chain = index.get(r["bin_id"]) or [root, orphan]
        for n in chain:
            _add(n, unit, parts, True)
        ow = by_owner.setdefault(r.get("owner_entity_id") or "", {"owner_entity_id": r.get("owner_entity_id") or "", "rolls": 0, "by_unit": {}})
        _add(ow, unit, parts, True)
    root["children"] += [n for n in (unassigned, orphan, transit) if n["rolls"]]
    root["by_owner"] = list(by_owner.values())
    return root


def _merge(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    dst["rolls"] += src["rolls"]
    for unit, vals in src["by_unit"].items():
        u = dst["by_unit"].setdefault(unit, {b: 0.0 for b in BUCKETS} | {"total": 0.0})
        for k, v in vals.items():
            u[k] = round(u[k] + v, 4)


async def site_tree(site: Dict[str, Any], warehouses: List[Dict[str, Any]], owners: Optional[List[str]]) -> Dict[str, Any]:
    root = _new_node("site", site["id"], site.get("name", ""))
    for wh in warehouses:
        t = await warehouse_tree(wh, owners, site.get("name", ""))
        root["children"].append(t)
        _merge(root, t)
    return root
