"""PREP-B — rencana & rekonsiliasi pendaftaran awal gedung (K-OPN-01/02).

Data lama = HANYA pembanding: roll fisik tercatat di cakupan sesi (per produk × PT pemilik) dibandingkan dengan baris
pendaftaran (fisik). Hasil per kelompok produk×PT:
  · roll lama yang DICOCOKKAN (EPC tag lamanya terbaca / nomor roll lama terbaca, produk & PT sama) → dipakai ulang;
  · baris tanpa pasangan → roll BARU (temuan) bernilai BIAYA RATA-RATA (`stock_count_service.surplus_unit_cost`);
  · roll lama tanpa pasangan → HILANG (dihapus saat disetujui, nilai = HPP roll itu);
  · selisih qty = qty terdaftar − qty lama.
Satu fungsi `build_plan` dipakai layar rekonsiliasi DAN persetujuan — angka yang dilihat penyetuju = yang diterapkan.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from db import db
from services.location_service import flatten_bins
from services.roll_service import PHYSICAL_ROLL_STATUSES

EPS = 0.001
LINES = "initial_registration_lines"
OLD_FIELDS = {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1, "owner_entity_id": 1, "warehouse_id": 1, "bin_id": 1,
              "bin_code": 1, "length_remaining": 1, "length_reserved": 1, "unit": 1, "status": 1, "unit_cost": 1,
              "base_unit_cost": 1, "rfid_tag_id": 1, "active_movement": 1, "supplier_roll_no": 1, "created_at": 1}


def gkey(product_id: str, owner: str) -> str:
    """Kunci kelompok aman untuk path Mongo (tanpa titik/dolar)."""
    return f"{product_id}|{owner}".replace(".", "_").replace("$", "_")


def scope_of(wh: Dict[str, Any], node_ids: List[str]) -> Dict[str, Any]:
    """Cakupan sesi: node (zona/rak/tingkat/bin) → bin + label + rak. Kosong = seluruh gedung."""
    from services.stock_count_roll_service import _node_label, scope_bins
    if not node_ids:
        bins, labels = flatten_bins(wh), ["Seluruh gedung"]
    else:
        seen: Dict[str, Dict[str, Any]] = {}
        labels = []
        for nid in node_ids:
            hit = scope_bins(wh, nid)   # 400 bila node tidak ada di gudang
            labels.append(_node_label(hit[0], nid))
            for b in hit:
                seen.setdefault(b["bin_id"], b)
        bins = list(seen.values())
    racks: Dict[str, Dict[str, Any]] = {}
    for b in bins:
        r = racks.setdefault(b.get("rack_id") or "-", {"rack_id": b.get("rack_id") or "-", "rack": b.get("rack") or "-",
                                                        "zone": b.get("zone") or "", "zone_id": b.get("zone_id"), "bins": 0})
        r["bins"] += 1
    return {"bins": bins, "bin_ids": [b["bin_id"] for b in bins], "labels": labels, "racks": list(racks.values()),
            "full": not node_ids}


async def expected_rolls(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Roll lama di cakupan: fisik, bersisa, lahir SEBELUM sesi mulai, bukan hasil pendaftaran sesi ini.
    Cakupan seluruh gedung juga memuat roll tanpa bin/beralamat yatim (data lama sering tanpa alamat)."""
    reg = session.get("registration") or {}
    q: Dict[str, Any] = {"warehouse_id": session["warehouse_id"], "status": {"$in": PHYSICAL_ROLL_STATUSES},
                         "length_remaining": {"$gt": 0}, "registration.session_id": {"$ne": session["id"]}}
    started = reg.get("started_at")
    if started:
        q["$or"] = [{"created_at": {"$lt": started}}, {"created_at": {"$exists": False}}]
    if not reg.get("full_scope"):
        q["bin_id"] = {"$in": reg.get("bin_ids") or []}
    return await db.inventory_rolls.find(q, OLD_FIELDS).to_list(20000)


async def session_lines(session_id: str, statuses: Tuple[str, ...] = ("draft", "applied")) -> List[Dict[str, Any]]:
    return await db[LINES].find({"session_id": session_id, "status": {"$in": list(statuses)}},
                                {"_id": 0}).sort("created_at", 1).to_list(20000)


async def _products(pids: List[str]) -> Dict[str, Dict[str, Any]]:
    ids = sorted({p for p in pids if p})
    rows = await db.products.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "base_unit": 1}
                                  ).to_list(len(ids) + 1) if ids else []
    return {p["id"]: p for p in rows}


def _cost(r: Dict[str, Any]) -> float:
    return float(r.get("unit_cost") or r.get("base_unit_cost") or 0)


async def group_cost(session: Dict[str, Any], product_id: str, owner: str) -> Tuple[float, str]:
    """K-OPN-02 — biaya rata-rata; dibekukan di sesi saat diajukan (angka penyetuju = angka yang dipakai)."""
    frozen = ((session.get("registration") or {}).get("costs") or {}).get(gkey(product_id, owner))
    if frozen:
        return float(frozen.get("cost") or 0), frozen.get("basis") or "beku"
    from services.stock_count_service import surplus_unit_cost
    return await surplus_unit_cost(product_id, session["warehouse_id"], owner)


async def build_plan(session: Dict[str, Any]) -> Dict[str, Any]:
    reg = session.get("registration") or {}
    old = await expected_rolls(session)
    lines = await session_lines(session["id"])
    # Roll lama yang SUDAH/SEDANG diterapkan (dipakai ulang / dihapus — termasuk catatan operasi yang terputus) tetap
    # ikut rencana dengan qty SEBELUM diterapkan, supaya angka kelompok utuh & pengulangan melanjutkan, bukan melompati.
    wo = dict(reg.get("writeoffs") or {})
    before: Dict[str, Any] = {}
    for k, o in ((session.get("roll_count") or {}).get("ops") or {}).items():
        rid = k.split("_", 1)[1] if "_" in k else ""
        snap = float((o.get("roll") or {}).get("length_remaining") or 0)
        if k.startswith("missing_"):
            if o.get("status") == "done":
                wo.setdefault(rid, o.get("result") or {})
            else:
                before[rid] = snap
        elif k.startswith("reg_"):
            before[rid] = (o.get("result") or {}).get("old_qty", snap)
    for ln in lines:
        if ln.get("status") == "applied" and ln.get("matched_roll_id"):
            before.setdefault(ln["matched_roll_id"], (ln.get("result") or {}).get("old_qty"))
    done_ids = set(wo) | set(before) | {ln["matched_roll_id"] for ln in lines if ln.get("matched_roll_id")}
    have = {r["id"] for r in old}
    extra = [i for i in done_ids if i not in have]
    if extra:
        old += await db.inventory_rolls.find({"id": {"$in": extra}}, OLD_FIELDS).to_list(len(extra) + 1)
    for r in old:
        if r["id"] in wo:
            r["length_remaining"] = float(wo[r["id"]].get("written_off") or 0)
        elif before.get(r["id"]) is not None:
            r["length_remaining"] = float(before[r["id"]])
    old_by_id = {r["id"]: r for r in old}
    prods = await _products([ln.get("product_id") for ln in lines] + [r.get("product_id") for r in old])
    groups: Dict[str, Dict[str, Any]] = {}

    def grp(pid: str, owner: str) -> Dict[str, Any]:
        k = gkey(pid, owner)
        if k not in groups:
            p = prods.get(pid, {})
            groups[k] = {"key": k, "product_id": pid, "owner_entity_id": owner, "sku": p.get("sku", ""),
                         "product_name": p.get("name", ""), "unit": p.get("base_unit", ""), "lines": [], "old": [],
                         "missing": [], "reuse": 0, "new": 0, "notes": []}
        return groups[k]

    unmapped, claimed = [], set()
    for ln in lines:
        if not ln.get("product_id"):
            unmapped.append(ln)
            continue
        g = grp(ln["product_id"], ln.get("owner_entity_id") or "")
        r = old_by_id.get(ln.get("matched_roll_id") or "")
        ok = bool(r) and r.get("product_id") == ln["product_id"] and r.get("owner_entity_id") == ln.get("owner_entity_id") \
            and r["id"] not in claimed
        if ln.get("matched_roll_id") and not ok:
            g["notes"].append(f"Baris {ln.get('epc_display') or ln.get('epc')}: roll lama {ln.get('old_roll_no') or ln['matched_roll_id']} "
                              "beda produk/PT atau tidak lagi di cakupan → didaftarkan sebagai roll baru, roll lama dianggap hilang.")
        if ok:
            claimed.add(r["id"])
        g["lines"].append({**ln, "reuse_roll": r if ok else None})
        g["reuse" if ok else "new"] += 1
    for r in old:
        g = grp(r.get("product_id") or "", r.get("owner_entity_id") or "")
        g["old"].append(r)
        if r["id"] not in claimed:
            g["missing"].append(r)
    results = reg.get("groups") or {}
    out = []
    for k, g in groups.items():
        cost, basis = await group_cost(session, g["product_id"], g["owner_entity_id"]) if g["new"] else (0.0, "")
        old_qty = round(sum(float(r.get("length_remaining") or 0) for r in g["old"]), 4)
        reg_qty = round(sum(float(ln.get("qty") or 0) for ln in g["lines"]), 4)
        miss_val = round(sum(float(r.get("length_remaining") or 0) * _cost(r) for r in g["missing"]), 2)
        new_val = round(sum(float(ln.get("qty") or 0) for ln in g["lines"] if not ln["reuse_roll"]) * cost, 2)
        reuse_val = round(sum((float(ln.get("qty") or 0) - float(ln["reuse_roll"].get("length_remaining") or 0))
                              * _cost(ln["reuse_roll"]) for ln in g["lines"] if ln["reuse_roll"]), 2)
        out.append({**g, "old_rolls": len(g["old"]), "old_qty": old_qty, "registered_rolls": len(g["lines"]),
                    "registered_qty": reg_qty, "qty_diff": round(reg_qty - old_qty, 4), "missing_rolls": len(g["missing"]),
                    "missing_qty": round(sum(float(r.get("length_remaining") or 0) for r in g["missing"]), 4),
                    "unverified_length": sum(1 for ln in g["lines"] if not ln.get("length_verified")),
                    "unit_cost": cost, "cost_basis": basis, "value_new": new_val, "value_missing": -miss_val,
                    "value_reuse": reuse_val, "value_net": round(new_val + reuse_val - miss_val, 2),
                    "result": results.get(k)})
    out.sort(key=lambda x: (x["sku"], x["owner_entity_id"]))
    return {"groups": out, "unmapped": unmapped, "lines_total": len(lines), "old_total": len(old)}


def public_group(g: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan kelompok untuk layar (tanpa dokumen roll/baris penuh)."""
    keep = ("key", "product_id", "owner_entity_id", "sku", "product_name", "unit", "old_rolls", "old_qty",
            "registered_rolls", "registered_qty", "qty_diff", "missing_rolls", "missing_qty", "reuse", "new",
            "unverified_length", "unit_cost", "cost_basis", "value_new", "value_missing", "value_reuse", "value_net",
            "notes", "result")
    out = {k: g.get(k) for k in keep}
    out["missing"] = [{"roll_id": r["id"], "roll_no": r.get("roll_no", ""), "bin_code": r.get("bin_code", ""),
                       "qty": float(r.get("length_remaining") or 0), "status": r.get("status")} for r in g["missing"][:200]]
    return out


async def reconcile(session: Dict[str, Any]) -> Dict[str, Any]:
    plan = await build_plan(session)
    groups = [public_group(g) for g in plan["groups"]]
    tot = lambda f: round(sum(float(g.get(f) or 0) for g in groups), 2)  # noqa: E731
    return {"session_id": session["id"], "status": session.get("status"), "groups": groups,
            "unmapped": [{"id": ln["id"], "epc": ln.get("epc"), "bin_code": ln.get("bin_code"), "qty": ln.get("qty_input"),
                          "unit": ln.get("unit_input") or "", "note": (ln.get("unrecognized") or {}).get("note", ""),
                          "has_photo": bool((ln.get("unrecognized") or {}).get("photo"))} for ln in plan["unmapped"]],
            "totals": {"lines": plan["lines_total"], "old_rolls": plan["old_total"], "value_new": tot("value_new"),
                       "value_missing": tot("value_missing"), "value_reuse": tot("value_reuse"), "value_net": tot("value_net"),
                       "missing_rolls": sum(g["missing_rolls"] for g in groups), "new_rolls": sum(g["new"] for g in groups),
                       "reused_rolls": sum(g["reuse"] for g in groups)},
            "policy": ("K-OPN-01: data lama hanya pembanding. Roll lama yang cocok (EPC/nomor lama, produk & PT sama) dipakai "
                       "ulang; baris tanpa pasangan = roll baru bernilai biaya rata-rata (K-OPN-02); roll lama tanpa pasangan "
                       "dihapus saat disetujui; selisih nilai dijurnal per produk.")}


def assert_owner_access(groups: List[Dict[str, Any]], allowed: Optional[List[str]]) -> None:
    if allowed is None:
        return
    foreign = sorted({g["owner_entity_id"] for g in groups} - set(allowed))
    if foreign:
        raise HTTPException(status_code=403, detail="Kelompok menyentuh stok badan usaha di luar akses Anda: " + ", ".join(foreign))
