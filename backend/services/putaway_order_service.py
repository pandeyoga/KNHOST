"""FASE R2 — PUTAWAY ORDER (PA): dokumen pemindahan roll dari gedung transit ke
gedung penyimpanan, dengan enforcement `storage_rules` + BTG (Bukti Terima Gudang).

SSOT: perpindahan antar-gedung mengubah `roll.warehouse_id` lalu `rebuild_balance`
kedua sisi (balance = proyeksi dari rolls, tidak pernah $inc). Kepemilikan TIDAK
berubah (bukan interco). Journey: putaway_assigned → putaway_in_transit → stored
(atau gate_exception untuk item yang tak tervalidasi saat tiba).

PREP-C (K-GDG-10, 8 Nov 2026) — status `draft` lahir otomatis sebelum `open` (`putaway_draft_service`), tiba
BERTAHAP per trip (`putaway_arrival_service`, status `partially_received`), status akhir tanpa roll tiba =
`returned` (bukan `completed`). PA bertujuan gedung inspeksi (`purpose = inspection`) mengembalikan roll ke tahap
terverifikasi saat tiba — roll itu nanti di-PA lagi ke gedung simpan sesudah inspeksi.
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc
from services import warehouse_profile_service as whp  # noqa: F401
from services import placement_rules as pr
from services.rfid_print_service import set_journey

#: PA yang masih "hidup" (roll di dalamnya tidak boleh masuk PA lain).
LIVE_STATUSES = ("draft", "open", "in_transit", "partially_received")
#: PA yang boleh menerima konfirmasi tiba (trip).
ARRIVAL_STATUSES = ("open", "in_transit", "partially_received")
PROD_FIELDS = {"_id": 0, "id": 1, "sku": 1, "name": 1, "category": 1, "fabric_type": 1, "template_id": 1}


async def putaway_block_reason(r: Dict[str, Any]) -> Optional[str]:
    """G3 D4-WMS-04 — resolver kelayakan putaway bersama (health, suggest, create). None = siap."""
    if r.get("status") != "available":
        return f"status_{r.get('status') or 'unknown'}"
    if pr.is_held(r):   # PREP-C — roll DITAHAN (QC/inspeksi) tidak boleh masuk PA
        return "held"
    if r.get("active_movement"):
        return "active_movement"
    if float(r.get("length_reserved") or 0) > 0:
        return "reserved"
    if (await identity_issue(r))[0] is not None:
        return "tag_identity"
    return None


async def rolls_in_live_orders(roll_ids: List[str], statuses: tuple = LIVE_STATUSES,
                               exclude_order: str = "") -> Dict[str, Dict[str, Any]]:
    """{roll_id: {id, pa_number, status}} untuk roll yang sudah ada di PA hidup (termasuk draf)."""
    if not roll_ids:
        return {}
    q: Dict[str, Any] = {"status": {"$in": list(statuses)}, "items.roll_id": {"$in": list(roll_ids)}}
    if exclude_order:
        q["id"] = {"$ne": exclude_order}
    out: Dict[str, Dict[str, Any]] = {}
    wanted = set(roll_ids)
    async for o in db.putaway_orders.find(q, {"_id": 0, "id": 1, "pa_number": 1, "status": 1, "items.roll_id": 1}):
        for it in o.get("items") or []:
            if it.get("roll_id") in wanted:
                out[it["roll_id"]] = {"id": o["id"], "pa_number": o.get("pa_number", ""), "status": o["status"]}
    return out


async def _rolls_ready(warehouse_id: str, scope_ids: List[str], limit: int = 2000) -> List[Dict[str, Any]]:
    """Roll di gudang transit yang siap putaway: tag_verified + routing store."""
    rolls = await db.inventory_rolls.find({
        "warehouse_id": warehouse_id, "owner_entity_id": {"$in": scope_ids},
        "length_remaining": {"$gt": 0},
        "journey.stage": {"$in": ["tag_verified", "label_verified"]},   # P9.3b — RFID atau label QR
        "journey.routing": {"$ne": "cross_dock"},
        "status": "available", "active_movement": None,  # AX-08/WM-05
        "length_reserved": {"$not": {"$gt": 0}},
    }, {"_id": 0}).to_list(limit)
    rolls = [r for r in rolls if await putaway_block_reason(r) is None]  # G3 D4-TAG-01 / D4-WMS-04
    # PREP-C — roll yang sudah antre di DRAF PA (otomatis/manual) tidak ditawarkan dua kali.
    drafted = await rolls_in_live_orders([r["id"] for r in rolls], ("draft",))
    rolls = [r for r in rolls if r["id"] not in drafted]
    pids = list({r["product_id"] for r in rolls})
    prods = {p["id"]: p for p in await db.products.find({"id": {"$in": pids}}, PROD_FIELDS).to_list(3000)}
    for r in rolls:
        p = prods.get(r["product_id"], {})
        r["sku"], r["product_name"], r["category"] = p.get("sku", ""), p.get("name", ""), p.get("category", "")
        r["fabric_type"] = p.get("fabric_type", "")
        r["template_id"] = p.get("template_id", "")
    return rolls


async def storage_candidates(src: Dict[str, Any]) -> List[Dict[str, Any]]:
    """P9.4 — gudang SIMPAN (peran storage / material — PREP-C) aktif di LOKASI yang sama dengan gudang asal."""
    st_q: Dict[str, Any] = {"active": {"$ne": False}, "roles": {"$in": sorted(whp.STORAGE_ROLES)},
                            "id": {"$ne": src.get("id")}}
    if src.get("site_id"):
        st_q["site_id"] = src["site_id"]
    return await db.warehouses.find(st_q, {"_id": 0}).sort("code", 1).to_list(200)


async def suggest(warehouse_from: str, scope_ids: List[str]) -> Dict[str, Any]:
    """Kelompokkan roll siap-putaway per (owner, kategori) + kandidat gudang tujuan
    berdasarkan roles=storage + storage_rules match (site sama diprioritaskan)."""
    src = await db.warehouses.find_one({"id": warehouse_from}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Gudang asal tidak ditemukan")
    rolls = await _rolls_ready(warehouse_from, scope_ids)
    # P9.4 — kandidat tujuan hanya gudang simpan di LOKASI yang sama (dulu semua lokasi, hanya diurutkan).
    storages = await storage_candidates(src)
    # PREP-C (K-GDG-08) — artikel ikut kunci grup HANYA bila ada gudang tujuan yang membatasi artikel.
    by_template = any(pr.warehouse_rules(w).get("template_ids") for w in storages)
    groups: Dict[str, Dict[str, Any]] = {}
    for r in rolls:
        unit = r.get("unit", "meter")
        # G3 D4-PA-03 — satuan masuk kunci grup: meter dan kg tidak pernah dijumlahkan jadi satu angka
        key = f"{r.get('owner_entity_id')}|{r.get('category') or '—'}|{r.get('fabric_type') or ''}|{(r.get('grade') or 'A').upper()}|{unit}"
        if by_template:
            key += f"|{r.get('template_id') or ''}"
        g = groups.setdefault(key, {
            "owner_entity_id": r.get("owner_entity_id"), "category": r.get("category") or "",
            "fabric_type": r.get("fabric_type") or "", "template_id": r.get("template_id") or "",
            "grade": (r.get("grade") or "A").upper(),
            "rolls": [], "qty": 0.0, "unit": unit, "candidates": None})
        g["rolls"].append({k: r.get(k) for k in (
            "id", "roll_no", "sku", "product_name", "category", "grade",
            "length_remaining", "unit", "lot", "rfid_tag_id")})
        g["qty"] += float(r.get("length_remaining") or 0)
    for g in groups.values():
        cands = []
        probe = {"owner_entity_id": g["owner_entity_id"], "grade": g["grade"]}
        for wh in storages:
            # P02 — evaluator bersama: dedicated/shared + rules gudang AND (kategori, grade, jenis kain, artikel, PT)
            if not await pr.warehouse_violations(wh, probe, {"category": g["category"], "fabric_type": g["fabric_type"],
                                                             "template_id": g["template_id"]}):
                cands.append({"warehouse_id": wh["id"], "warehouse_name": wh.get("name", ""),
                              "site_id": wh.get("site_id", ""),
                              "same_site": wh.get("site_id") and wh.get("site_id") == src.get("site_id"),
                              "rules_mode": (wh.get("storage_rules") or {}).get("mode", "none"),
                              # FIX-3a (B2a FLW-IN-02) — spesifik = daftar aturan TERISI (mode tanpa daftar = terima semua)
                              "specific": any(pr.warehouse_rules(wh).get(k) for k in (
                                  "categories", "grades", "fabric_types", "template_ids", "owner_entity_ids")),
                              "code": wh.get("code") or ""})
        cands.sort(key=lambda c: (not c["same_site"], not c["specific"], c["code"]))
        g["candidates"] = cands
        g["qty"] = round(g["qty"], 2)
    return {"warehouse_from": {"id": src["id"], "name": src.get("name", "")},
            "ready_count": len(rolls), "groups": list(groups.values())}


PA_ELIGIBLE_STATUS = "available"  # AX-08 — QC hold/quarantine/reserved tidak boleh diputaway


async def identity_issue(r: Dict[str, Any]):
    """G3 D4-TAG-01 — kesiapan identitas terikat ke tag AKTIF saat ini + bukti verifikasi tag itu.
    Tag lama yang di-retire / tag baru yang belum dicetak-diverifikasi tidak lolos."""
    tid = r.get("rfid_tag_id")
    j0 = r.get("journey") or {}
    if j0.get("verified_via") == "label_scan" or (not tid and j0.get("stage") == "label_verified"):
        # UAT 24 Okt (P9.3b) — label QR SETARA RFID: identitas = nomor roll yang sudah dipindai di transit. GRN selalu
        # menyiapkan data tag (EPC) walau lokasinya tidak memakai RFID, jadi `rfid_tag_id` saja bukan bukti ada tag fisik.
        # Kode yang sama dipindai saat tiba di gudang simpan (konfirmasi tiba membandingkan kode, bukan EPC hex).
        return None, {"epc": str(r.get("roll_no") or "").upper(), "kind": "qr_label"}
    if not tid:
        return "label QR roll belum dipindai di transit (atau tag RFID belum ada) — pindai label roll dulu", None
    tag = await db.rfid_tags.find_one({"id": tid}, {"_id": 0})
    if not tag or tag.get("status") != "active":
        return f"tag RFID berstatus {(tag or {}).get('status') or 'hilang'} — belum aktif/terverifikasi", None
    if tag.get("roll_id") != r.get("id") or not tag.get("epc"):
        return "tag RFID tidak tertaut benar ke roll ini", None
    j = r.get("journey") or {}
    if j.get("verified_tag_id"):
        ok = j["verified_tag_id"] == tid
    else:  # data lama tanpa verified_tag_id: tag tidak boleh lahir sesudah verifikasi terakhir
        ok = not tag.get("created_at") or str(tag["created_at"]) <= str(j.get("updated_at") or "")
    if not ok:
        return "tag RFID saat ini belum diverifikasi (bukti verifikasi milik tag lama)", None
    return None, tag


async def _release_claims(roll_ids: List[str], order_id: str) -> None:
    from services.roll_service import rebuild_balance
    segs = {(r["product_id"], r["warehouse_id"], r.get("owner_entity_id")) async for r in db.inventory_rolls.find(
        {"id": {"$in": roll_ids}, "active_movement.id": order_id},
        {"_id": 0, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1})}
    await db.inventory_rolls.update_many(
        {"id": {"$in": roll_ids}, "active_movement.id": order_id, "status": PA_ELIGIBLE_STATUS},
        {"$unset": {"active_movement": ""}})
    for pid, wid, own in segs:
        await rebuild_balance(pid, wid, own)


def assert_same_site(wh_from: Dict[str, Any], wh_to: Dict[str, Any]) -> None:
    if wh_from.get("site_id") and wh_to.get("site_id") and wh_from["site_id"] != wh_to["site_id"]:
        # UAT 24 Okt (P9.4) — putaway = transit → gudang simpan DI LOKASI YANG SAMA; antar lokasi = transfer.
        raise HTTPException(status_code=400, detail=(
            "Putaway hanya ke gudang simpan di lokasi yang sama. Pindah antar lokasi memakai Transfer Gudang."))


def item_row(r: Dict[str, Any], p: Dict[str, Any], epc: str = "") -> Dict[str, Any]:
    return {"roll_id": r["id"], "roll_no": r.get("roll_no", ""), "epc": epc,
            "sku": p.get("sku", ""), "product_name": p.get("name", ""),
            "category": p.get("category", ""), "grade": r.get("grade", ""),
            "product_id": r["product_id"], "lot": r.get("lot", ""),
            "qty": float(r.get("length_remaining") or 0), "unit": r.get("unit", "meter"),
            "status": "pending"}


def qty_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Total item PA. G3 D4-PA-03 — total per satuan (meter/kg/yard tidak dijumlahkan jadi satu label)."""
    units = {(i.get("unit") or "meter") for i in items}
    return {"item_count": len(items), "total_qty": round(sum(i["qty"] for i in items), 2),
            "qty_by_unit": {u: round(sum(i["qty"] for i in items if (i.get("unit") or "meter") == u), 2)
                            for u in units},
            "mixed_units": len(units) > 1}


async def roll_violation(r: Dict[str, Any], wh_to: Dict[str, Any], p: Dict[str, Any],
                         purpose: str = "storage") -> Tuple[Optional[str], Any]:
    """Satu jawaban kelayakan roll untuk PA (buat manual & terbitkan draf). → (alasan | None, tag).
    `purpose=inspection` — aturan SIMPAN gedung tujuan tidak berlaku (roll hanya singgah diperiksa)."""
    stage = (r.get("journey") or {}).get("stage")
    if stage not in ("tag_verified", "label_verified"):
        return f"Roll {r.get('roll_no')} belum terverifikasi (stage: {stage or '—'})", None
    # AX-08 — tag terverifikasi BUKAN izin gerak: status kualitas/reservasi roll juga wajib bebas.
    if r.get("status") != PA_ELIGIBLE_STATUS:
        return (f"Roll {r.get('roll_no')} berstatus {r.get('status')} — putaway hanya "
                "untuk roll available (lolos QC, tidak dipesan)"), None
    if pr.is_held(r):   # PREP-C (celah 27 Okt) — roll DITAHAN inspeksi/QC tidak boleh masuk PA
        return f"Roll {r.get('roll_no')} sedang DITAHAN (QC/inspeksi) — lepas tahanannya dulu", None
    if float(r.get("length_reserved") or 0) > 0:  # WM-02 — ada reservasi potong tertunda
        return f"Roll {r.get('roll_no')} punya reservasi potong yang belum dikonfirmasi", None
    if float(r.get("length_remaining") or 0) <= 0:
        return f"Roll {r.get('roll_no')} panjangnya 0", None
    if (r.get("active_movement") or {}).get("id"):
        return (f"Roll {r.get('roll_no')} sedang dalam perpindahan "
                f"{r['active_movement'].get('number') or r['active_movement']['id']}"), None
    # P02 DEV-F05/G02 — gudang tujuan: dedicated/shared untuk pemilik roll + rules AND
    wv = await pr.warehouse_violations(wh_to, r, p, attrs=purpose != "inspection")
    if wv:
        return f"Roll {r.get('roll_no')}: {wv[0]}", None
    why, tag = await identity_issue(r)
    if why:
        return f"Roll {r.get('roll_no')}: {why}", None
    return None, tag


async def claim_rolls(items: List[Dict[str, Any]], order_id: str, pa_number: str, warehouse_from: str) -> None:
    """WM-05 — klaim kepemilikan perpindahan PER ROLL (atomik, all-or-none) sebelum PA berlaku."""
    claimed: List[str] = []
    for it in items:
        res = await db.inventory_rolls.update_one(
            {"id": it["roll_id"], "warehouse_id": warehouse_from, "status": PA_ELIGIBLE_STATUS,
             "journey.stage": {"$in": ["tag_verified", "label_verified"]},   # P9.3b — RFID atau label QR
             "length_remaining": {"$gt": 0}, "active_movement": None,
             "inspection.hold.held": {"$ne": True},                          # PREP-C — roll ditahan tidak diklaim
             "length_reserved": {"$not": {"$gt": 0}}},
            {"$set": {"active_movement": {"type": "putaway", "id": order_id, "number": pa_number,
                                          "claimed_at": now_iso()}}})
        if res.modified_count != 1:
            await _release_claims(claimed, order_id)
            raise HTTPException(status_code=409, detail=(
                f"Roll {it['roll_no']} baru saja diambil proses lain (PA/reservasi/QC). Muat ulang layar."))
        claimed.append(it["roll_id"])


async def after_claim(items: List[Dict[str, Any]], order: Dict[str, Any]) -> None:
    from services.roll_service import rebuild_balance
    for pid in {i["product_id"] for i in items}:  # G3 D4-PA-01 — roll diklaim PA keluar dari ATP
        await rebuild_balance(pid, order["from_warehouse_id"], order["owner_entity_id"])
    await set_journey([i["roll_id"] for i in items], "putaway_assigned", {"putaway_order_id": order["id"]})


async def create_order(warehouse_from: str, warehouse_to: str, roll_ids: List[str],
                       scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
    if not roll_ids:
        raise HTTPException(status_code=400, detail="Pilih minimal satu roll")
    if warehouse_from == warehouse_to:
        raise HTTPException(status_code=400, detail="Gudang asal dan tujuan sama")
    roll_ids = list(dict.fromkeys(roll_ids))
    wh_to = await db.warehouses.find_one({"id": warehouse_to}, {"_id": 0})
    wh_from = await db.warehouses.find_one({"id": warehouse_from}, {"_id": 0})
    if not wh_to or not wh_from:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    assert_same_site(wh_from, wh_to)
    rolls = await db.inventory_rolls.find(
        {"id": {"$in": roll_ids}, "warehouse_id": warehouse_from,
         "owner_entity_id": {"$in": scope_ids}}, {"_id": 0}).to_list(len(roll_ids) + 5)
    if len(rolls) != len(roll_ids):
        raise HTTPException(status_code=400,
                            detail="Sebagian roll tidak ditemukan di gudang asal / di luar entitas")
    from services import registration_freeze as _rfz   # PREP-B K-OPN-03 — area beku pendaftaran awal
    await _rfz.assert_rolls_movable(rolls, "membuat perintah putaway", to_warehouse_id=warehouse_to)
    owners = {r.get("owner_entity_id") for r in rolls}
    if len(owners) > 1:
        raise HTTPException(status_code=400, detail="Satu PA hanya untuk satu pemilik barang")
    pids = list({r["product_id"] for r in rolls})
    prods = {p["id"]: p for p in await db.products.find({"id": {"$in": pids}}, PROD_FIELDS).to_list(3000)}
    in_draft = await rolls_in_live_orders(roll_ids, ("draft",))
    items, violations = [], []
    for r in rolls:
        if r["id"] in in_draft:   # PREP-C — satu roll satu antrean: draf otomatis diterbitkan/diubah, bukan digandakan
            violations.append(f"Roll {r.get('roll_no')} sudah ada di draf {in_draft[r['id']]['pa_number']} — "
                              "terbitkan atau keluarkan dari draf itu dulu")
            continue
        p = prods.get(r["product_id"], {})
        why, tag = await roll_violation(r, wh_to, p)
        if why:
            violations.append(why)
            continue
        items.append(item_row(r, p, tag.get("epc", "")))
    if violations:
        raise HTTPException(status_code=400, detail=" | ".join(violations[:5]))
    order_id = new_id("pa")
    pa_number = await next_doc_number("putaway_orders", "pa_number", "PA")
    await claim_rolls(items, order_id, pa_number, warehouse_from)
    order = {
        "id": order_id,
        "pa_number": pa_number,
        "from_warehouse_id": warehouse_from, "from_warehouse_name": wh_from.get("name", ""),
        "to_warehouse_id": warehouse_to, "to_warehouse_name": wh_to.get("name", ""),
        "owner_entity_id": list(owners)[0],
        "items": items, **qty_summary(items),
        "purpose": "inspection" if whp.has_role(wh_to, whp.INSPECTION_ROLE) and not
                   whp.has_role(wh_to, *whp.STORAGE_ROLES) else "storage",
        "status": "open", "btg_number": None,
        "created_at": now_iso(), "created_by": actor_name,
        "dispatched_at": None, "confirmed_at": None, "confirmed_by": None,
    }
    try:
        await db.putaway_orders.insert_one(dict(order))
    except Exception:
        await _release_claims([i["roll_id"] for i in items], order_id)
        raise
    await after_claim(items, order)
    return safe_doc(order)


async def list_orders(scope_ids: List[str], warehouse_id: Optional[str],
                      status: Optional[str], limit: int = 100) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"owner_entity_id": {"$in": scope_ids}}
    if warehouse_id:
        q["$or"] = [{"from_warehouse_id": warehouse_id}, {"to_warehouse_id": warehouse_id}]
    if status:
        q["status"] = status
    orders = await db.putaway_orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    # FIX-3a (B3b FRM-10, K-B3b-09) — layar menampilkan tombol simulasi HANYA untuk PT bermode simulasi RFID.
    sim = {e: await simulation_on(e) for e in {o.get("owner_entity_id") or "" for o in orders}}
    return [{**safe_doc(o), "rfid_simulation": sim.get(o.get("owner_entity_id") or "", False)} for o in orders]


async def simulation_on(entity_id: str) -> bool:
    """Mode simulasi RFID (`wms.rfid_simulation`) untuk PT pemilik PA (bawaan mati)."""
    from services.config_resolver import value_of
    return bool(await value_of("wms.rfid_simulation", {"entity_id": entity_id or ""}))


async def _get(order_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    order = await db.putaway_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Putaway Order tidak ditemukan")
    if order.get("owner_entity_id") not in scope_ids:
        raise HTTPException(status_code=403, detail="PA di luar entitas Anda")
    return order


async def dispatch(order_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    """WM-04 — roll pindah bucket available → in_transit_transfer (ATP asal turun, owned tetap)."""
    from services.roll_service import rebuild_balance
    from services import atomic_claim as _saga
    order = await _get(order_id, scope_ids)
    if order["status"] != "open":
        raise HTTPException(status_code=400, detail=f"PA berstatus {order['status']}")
    from services import registration_freeze as _rfz   # PREP-B K-OPN-03 — area beku pendaftaran awal
    await _rfz.assert_order_movable(order, "mengirim perintah putaway")
    await _saga.claim("putaway_orders", order_id, "putaway_dispatch", precondition={"status": "open"})
    moved: List[Dict[str, Any]] = []
    for it in order["items"]:
        # G3 D4-TAG-01 — identitas diperiksa ulang sebelum efek (tag bisa diganti sesudah PA dibuat)
        roll = await db.inventory_rolls.find_one({"id": it["roll_id"]}, {"_id": 0}) or {}
        why, tag = await identity_issue(roll)
        bad_identity = bool(why) or (tag or {}).get("epc", "").upper() != (it.get("epc") or "").upper()
        # G3 D4-PA-01 — CAS juga menolak roll yang punya reservasi panjang (potong) live
        res = None if bad_identity else await db.inventory_rolls.update_one(
            {"id": it["roll_id"], "active_movement.id": order_id, "status": PA_ELIGIBLE_STATUS,
             "inspection.hold.held": {"$ne": True},   # PREP-C — roll yang DITAHAN sesudah PA dibuat tidak dikirim
             "warehouse_id": order["from_warehouse_id"], "length_reserved": {"$not": {"$gt": 0}}},
            {"$set": {"status": "in_transit_transfer", "updated_at": now_iso()}})
        if res is None or res.modified_count != 1:
            for m in moved:  # kompensasi: tidak ada PA setengah terkirim
                await db.inventory_rolls.update_one(
                    {"id": m["roll_id"], "active_movement.id": order_id, "status": "in_transit_transfer"},
                    {"$set": {"status": PA_ELIGIBLE_STATUS}})
            await _saga.release("putaway_orders", order_id)
            raise HTTPException(status_code=409, detail=(
                f"Roll {it['roll_no']} " + (f"identitasnya berubah: {why or 'EPC berbeda dari PA'}. " if bad_identity
                                            else "tidak lagi available untuk PA ini (dipesan/QC/berpindah). ")
                + "Keluarkan roll itu atau buat PA baru."))
        moved.append(it)
    for pid in {i["product_id"] for i in order["items"]}:
        await rebuild_balance(pid, order["from_warehouse_id"], order["owner_entity_id"])
    await db.putaway_orders.update_one({"id": order_id}, _saga.finish_set({
        "status": "in_transit", "dispatched_at": now_iso(), "updated_at": now_iso()}))
    await set_journey([i["roll_id"] for i in order["items"]], "putaway_in_transit")
    return await _get(order_id, scope_ids)


async def _land_items(order: Dict[str, Any], items: List[Dict[str, Any]], actor_name: str,
                      reason: str) -> List[Dict[str, Any]]:
    """Satu jalur posting perpindahan (arrival normal & exception — WM-09): CAS roll milik PA ini,
    pindah gudang, tulis pasangan mutasi out/in, rebuild kedua lokasi. Hasil = item yang benar-benar pindah."""
    from services.roll_service import rebuild_balance
    now = now_iso()
    landed, movements, segs = [], [], set()
    wh_to = await db.warehouses.find_one({"id": order["to_warehouse_id"]}, {"_id": 0}) or {}
    for item in items:
        # P02 — revalidasi tujuan saat tiba (mode/rules bisa berubah sesudah PA dibuat)
        prod = await db.products.find_one({"id": item["product_id"]}, PROD_FIELDS) or {}
        wv = await pr.warehouse_violations(wh_to, {"owner_entity_id": order["owner_entity_id"],
                                                   "grade": item.get("grade") or "A"}, prod,
                                           attrs=order.get("purpose") != "inspection")
        if wv and not await db.inventory_rolls.find_one({"id": item["roll_id"], "last_pa_landed": order["id"]}, {"_id": 1}):
            item["status"] = "exception"
            item["exception_reason"] = f"Tujuan tidak lagi sah: {wv[0]}"
            continue
        res = await db.inventory_rolls.update_one(
            {"id": item["roll_id"], "active_movement.id": order["id"],
             "warehouse_id": order["from_warehouse_id"],
             "status": {"$in": [PA_ELIGIBLE_STATUS, "in_transit_transfer"]}},
            {"$set": {"warehouse_id": order["to_warehouse_id"], "bin_id": None,
                      "status": PA_ELIGIBLE_STATUS, "updated_at": now, "last_pa_landed": order["id"]},
             "$unset": {"active_movement": ""}})
        if res.modified_count != 1:
            # G3 D4-PA-02 — percobaan sebelumnya sudah memindah roll ini untuk PA yang SAMA tapi mati
            # sebelum tag/mutasi/saldo → ADOPSI efeknya dan lanjutkan langkah sisanya (idempoten).
            if not await db.inventory_rolls.find_one({"id": item["roll_id"], "last_pa_landed": order["id"],
                                                      "warehouse_id": order["to_warehouse_id"]}, {"_id": 1}):
                item["status"] = "exception"
                item["exception_reason"] = "Roll tidak lagi milik PA ini / status berubah"
                continue
        await db.rfid_tags.update_one({"roll_id": item["roll_id"], "status": "active"},
                                      {"$set": {"warehouse_id": order["to_warehouse_id"]}})
        item["status"] = "arrived"
        item.setdefault("arrived_at", now)
        item.pop("exception_reason", None)
        landed.append(item)
        for wh, mtype in ((order["from_warehouse_id"], "putaway_transfer_out"),
                          (order["to_warehouse_id"], "putaway_transfer_in")):
            movements.append({
                "id": f"mov_pa_{order['id']}_{item['roll_id']}_{mtype[-3:].strip('_')}",
                "product_id": item["product_id"], "warehouse_id": wh,
                "owner_entity_id": order["owner_entity_id"], "movement_type": mtype,
                "quantity": item["qty"] if mtype.endswith("_in") else -item["qty"],
                "unit": item["unit"], "lot": item.get("lot", ""), "roll_id": item["roll_id"],
                "qty_rolls": 1, "source_document": order["pa_number"], "reference_id": order["id"],
                "reason": reason, "created_by": actor_name, "timestamp": now,
            })
        segs.add((item["product_id"], order["from_warehouse_id"]))
        segs.add((item["product_id"], order["to_warehouse_id"]))
    for mv in movements:   # id deterministik per (PA, roll, arah) → retry tidak menggandakan mutasi
        await db.inventory_movements.update_one({"id": mv["id"]}, {"$setOnInsert": mv}, upsert=True)
    for pid, wid in segs:
        await rebuild_balance(pid, wid, order["owner_entity_id"])
    if landed and order.get("purpose") == "inspection":
        # PREP-C (K-GDG-04) — tiba di GEDUNG INSPEKSI bukan akhir perjalanan: roll kembali ke tahap terverifikasi
        # asalnya (RFID / label QR) supaya sesudah inspeksi bisa di-PA lagi ke gudang simpan.
        await _back_to_verified([i["roll_id"] for i in landed],
                                {"putaway_order_id": order["id"], "inspection_site": order["to_warehouse_id"]})
    elif landed:
        await set_journey([i["roll_id"] for i in landed], "stored", {"putaway_order_id": order["id"]})
    return landed


async def _back_to_verified(roll_ids: List[str], extra: Dict[str, Any]) -> None:
    """P9.3b — kembali ke tahap verifikasi asal roll: label QR (`label_verified`) atau tag RFID (`tag_verified`)."""
    if not roll_ids:
        return
    label = [r["id"] async for r in db.inventory_rolls.find(
        {"id": {"$in": roll_ids}, "journey.verified_via": "label_scan"}, {"_id": 0, "id": 1})]
    rfid = [r for r in roll_ids if r not in set(label)]
    if label:
        await set_journey(label, "label_verified", extra)
    if rfid:
        await set_journey(rfid, "tag_verified", extra)


async def return_items_to_transit(order: Dict[str, Any], items: List[Dict[str, Any]], actor_name: str) -> None:
    """Item PA → kembali siap-putaway di gudang ASAL (lepas klaim, status available, tahap verifikasi asal)."""
    from services.roll_service import rebuild_balance
    now = now_iso()
    segs, back = set(), []
    for item in items:
        res = await db.inventory_rolls.update_one(
            {"id": item["roll_id"], "active_movement.id": order["id"],
             "status": {"$in": [PA_ELIGIBLE_STATUS, "in_transit_transfer"]}},
            {"$set": {"status": PA_ELIGIBLE_STATUS, "updated_at": now},
             "$unset": {"active_movement": ""}})
        if res.modified_count == 1:
            item["status"] = "returned_transit"
            item["resolved_by"], item["resolved_at"] = actor_name, now
            segs.add((item["product_id"], order["from_warehouse_id"]))
            back.append(item["roll_id"])
    await _back_to_verified(back, {"exception_resolved_by": actor_name})
    for pid, wid in segs:
        await rebuild_balance(pid, wid, order["owner_entity_id"])


MIN_OVERRIDE_REASON = 10


async def confirm_arrival(order_id: str, scanned_epcs: Optional[List[str]],
                          scope_ids: List[str], actor_name: str,
                          manual_all: bool = False, reason: str = "", simulated: bool = False) -> Dict[str, Any]:
    """Konfirmasi tiba TERAKHIR (menutup PA): yang terbaca tiba, roll lain yang masih menunggu → exception.
    WM-03: `scanned_epcs=[]` = NOL roll tiba; tanpa hasil scan hanya lewat override manual ber-alasan (`manual_all`).
    PREP-C — tiba bertahap per trip (tanpa menutup) memakai `putaway_arrival_service.confirm_arrival_trip`."""
    order = await _get(order_id, scope_ids)
    if order["status"] not in ARRIVAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"PA berstatus {order['status']}")
    if simulated:
        # FIX-3a (B3b FRM-10, K-B3b-09) — "Simulasi Scan Semua" hanya saat mode simulasi RFID aktif untuk PT itu; hasilnya
        # BERTANDA simulasi (bukan "gate-in scan"). Di luar mode simulasi tombolnya ditolak (dulu melewati syarat
        # konfirmasi manual wms.approve + alasan).
        if not await simulation_on(order.get("owner_entity_id") or ""):
            raise HTTPException(status_code=403, detail=(
                "Simulasi scan hanya boleh saat 'Mode simulasi RFID' aktif untuk PT ini — pakai pindai nyata, atau "
                "konfirmasi manual ber-alasan (butuh izin setujui)."))
        scanned_epcs = [i.get("epc") for i in order.get("items") or [] if i.get("epc") and i.get("status") == "pending"]
    why = (reason or "").strip()
    if manual_all:
        if len(why) < MIN_OVERRIDE_REASON:
            raise HTTPException(status_code=400, detail=(
                f"Konfirmasi manual tanpa scan wajib beralasan (minimal {MIN_OVERRIDE_REASON} huruf)."))
    elif scanned_epcs is None:
        raise HTTPException(status_code=400, detail=(
            "Kirim hasil scan EPC, atau pilih konfirmasi manual (semua tiba) dengan alasan."))
    from services import registration_freeze as _rfz   # PREP-B K-OPN-03 — area beku pendaftaran awal
    await _rfz.assert_order_movable(order, "konfirmasi tiba perintah putaway")
    # INV-ATOMIC-01 (T-01 Opsi B) — klaim PA sebelum roll/tag/mutasi ditulis.
    from services import atomic_claim as _saga
    fresh = await _saga.claim("putaway_orders", order_id, "putaway_confirm_arrival",
                              precondition={"status": {"$in": list(ARRIVAL_STATUSES)}}, actor=actor_name)
    try:
        return await _confirm_arrival_claimed(fresh, order_id, scanned_epcs, scope_ids, actor_name,
                                              manual_all, why, _saga, simulated=simulated)
    except BaseException:
        # G3 D4-PA-02 — gagal di tengah: kunci dilepas supaya retry lewat fitur asli bisa MELANJUTKAN
        # (roll yang sudah dipindah untuk PA ini diadopsi oleh _land_items; mutasi ber-id deterministik).
        await _saga.release("putaway_orders", order_id)
        raise


async def _confirm_arrival_claimed(order, order_id, scanned_epcs, scope_ids, actor_name, manual_all, why, _saga,
                                   simulated: bool = False):
    from services import putaway_arrival_service as arr
    res = await arr.land_matching(order, None if manual_all else (scanned_epcs or []), actor_name,
                                  f"manual: {why}" if manual_all else ("SIMULASI scan (mode simulasi RFID)" if simulated
                                                                       else "gate-in scan"))
    if simulated:
        for i in res.get("arrived") or []:
            i["arrived_via"] = "simulated"
    await arr.mark_pending(order, "exception", actor_name, "EPC tidak terbaca saat konfirmasi tiba")
    upd = await arr.finish_update(order, actor_name)
    if manual_all:
        upd["manual_override"] = {"by": actor_name, "reason": why, "at": now_iso()}
    if simulated:
        upd["simulated"] = {"by": actor_name, "at": now_iso(), "rolls": [i.get("roll_no") for i in res.get("arrived") or []]}
    await db.putaway_orders.update_one({"id": order_id}, _saga.finish_set(upd))
    out = await _get(order_id, scope_ids)
    await arr.gate_session_hook(out)   # PREP-D2 — PA ditutup → sesi dokumen gate dinilai (K-RFID-10)
    return out


async def resolve_exception(order_id: str, roll_ids: List[str], action: str,
                            scope_ids: List[str], actor_name: str, reason: str = "") -> Dict[str, Any]:
    """Checker (handheld scan ulang di ERP): `accept` = barang ternyata sah → pindahkan (mutasi
    ditulis lewat jalur yang sama dengan arrival); `return_transit` = kembali siap-putaway di asal.
    PREP-C — `accept` setara konfirmasi manual (izin `wms.approve`, dijaga router); status akhir dari status item
    (semua dikembalikan & 0 tiba = `returned`, bukan `completed`)."""
    from services import putaway_arrival_service as arr
    from input_rules import require_reason
    order = await _get(order_id, scope_ids)
    if action not in ("accept", "return_transit"):
        raise HTTPException(status_code=400, detail="Aksi harus 'accept' atau 'return_transit'")
    # FIX-3a (B3b FRM-09 #13) — alasan wajib ≥ 5 huruf (dulu diisi otomatis "exception accept oleh …").
    why = require_reason(reason, label="Alasan menyelesaikan pengecualian")
    target = [i for i in order["items"] if i["status"] == "exception" and i["roll_id"] in set(roll_ids)]
    if not target:
        raise HTTPException(status_code=404, detail="Tidak ada item exception yang cocok")
    # FIX-3a (B2a STM-IN-05) — kait pembekuan pendaftaran awal (gerak roll ke tujuan / kembali ke transit).
    from services import registration_freeze as _rfz
    await _rfz.assert_order_movable({**order, "items": target}, "menyelesaikan pengecualian perintah putaway")
    # INV-ATOMIC-01 — klaim perintah putaway sebelum roll/tag/jejak/balance ditulis.
    # FIX-3a (STM-IN-05) — klaim BERPRASYARAT: PA bukan draf/batal dan roll target masih berstatus exception;
    # dokumen dibaca ULANG dari hasil klaim (dulu dibaca sebelum klaim tanpa prasyarat).
    from services import atomic_claim as _saga
    order = await _saga.claim("putaway_orders", order_id, "putaway_resolve_exception", actor=actor_name,
                              precondition={"status": {"$nin": ["draft", "cancelled"]},
                                            "items": {"$elemMatch": {"status": "exception",
                                                                     "roll_id": {"$in": [i["roll_id"] for i in target]}}}})
    target = [i for i in order["items"] if i["status"] == "exception" and i["roll_id"] in set(roll_ids)]
    now = now_iso()
    if action == "accept":
        await _land_items(order, target, actor_name, f"exception accept: {why}")
        for i in target:
            if i["status"] == "arrived":
                i["resolved_by"], i["resolved_at"] = actor_name, now
                i["arrived_via"] = "exception_accept"
    else:  # return_transit
        await return_items_to_transit(order, target, actor_name)
    upd = await arr.finish_update(order, actor_name)
    await db.putaway_orders.update_one({"id": order_id}, _saga.finish_set(upd))
    out = await _get(order_id, scope_ids)
    await arr.gate_session_hook(out)   # FIX-3a (STM-IN-05) — status akhir → sesi dokumen gate ditutup seperti jalur tiba
    return out


async def verify_labels(warehouse_id: str, codes: List[str], scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
    """UAT 24 Okt (P9.3b) — pindai LABEL QR roll di gudang transit (lokasi tanpa RFID): roll yang kodenya cocok
    (nomor roll) & masih di tahap penerimaan → `label_verified`, sehingga bisa masuk Putaway Order ke gudang simpan.
    Setara verifikasi tag RFID: roll yang tag-nya SUDAH terverifikasi (`tag_verified`) tidak disentuh."""
    wanted = {str(c or "").strip().upper() for c in codes or [] if str(c or "").strip()}
    if not wanted:
        raise HTTPException(status_code=400, detail="Pindai minimal satu label roll")
    rows = await db.inventory_rolls.find(
        {"warehouse_id": warehouse_id, "owner_entity_id": {"$in": scope_ids}, "roll_no": {"$in": list(wanted)}},
        {"_id": 0, "id": 1, "roll_no": 1, "rfid_tag_id": 1, "journey": 1, "status": 1}).to_list(2000)
    ok, skipped, no_print = [], [], []
    now = now_iso()
    # FIX-3a (B2a FLW-IN-17) — verifikasi label terikat BUKTI CETAK: roll tanpa catatan cetak label/tag tetap
    # diverifikasi (label pabrik/supplier sah dipindai) tetapi DITANDAI "tanpa bukti cetak" agar terlihat di layar & audit.
    # Bukti = `roll_label_prints` (satu baris per label tercetak, append-only — dari antrean cetak & cetak ulang).
    printed = {d["roll_id"] async for d in db.roll_label_prints.find(
        {"roll_id": {"$in": [r["id"] for r in rows]}}, {"_id": 0, "roll_id": 1})} if rows else set()
    for r in rows:
        stage = (r.get("journey") or {}).get("stage") or ""
        if stage not in ("received_transit", "tag_printed", "label_verified", "gate_exception"):
            skipped.append({"roll_no": r["roll_no"], "why": f"tahap {stage or '—'} bukan tahap penerimaan"})
            continue
        evidence = "print_record" if r["id"] in printed else "none"
        await db.inventory_rolls.update_one({"id": r["id"]}, {"$set": {
            "journey.stage": "label_verified", "journey.verified_via": "label_scan", "journey.verified_by": actor_name,
            "journey.label_print_evidence": evidence,
            "journey.updated_at": now, "updated_at": now}, "$unset": {"journey.exception_reason": ""}})
        ok.append(r["roll_no"])
        if evidence == "none":
            no_print.append(r["roll_no"])
    found = {r["roll_no"].upper() for r in rows}
    return {"verified": ok, "skipped": skipped, "not_found": sorted(wanted - found), "without_print_record": no_print}
