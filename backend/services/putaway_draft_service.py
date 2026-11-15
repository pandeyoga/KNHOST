"""PREP-C (K-GDG-10 + K-GDG-04, keputusan pemilik 8 Nov 2026) — DRAF Putaway Order otomatis.

Sesudah barang LEPAS ke stok tersedia — keputusan QC (antrean karantina / tutup SPK MD Quality yang memutus
karantina), GRN tanpa QC, atau SPK QC 4-point ditutup di gedung inspeksi — sistem menyiapkan DRAF PA per
(gedung asal, PT pemilik, gedung tujuan, tujuan). Admin mengecek (boleh ubah isi/tujuan) lalu MENERBITKAN → `open`.

Aturan:
* Draf TIDAK mengklaim roll (tanpa `active_movement`): stok transit tetap boleh dialokasikan/dijual (K-GDG-09).
  Satu roll hanya di satu PA hidup (draf/terbuka/jalan) — roll yang sudah ada di PA lain dilewati.
* Tujuan: `putaway_order_service.suggest`-setara — gudang simpan (`storage`/`material`) aktif di LOKASI yang sama,
  lolos aturan gudang (kategori, grade, jenis kain, artikel, PT — AND), yang beraturan spesifik didahulukan; bahan
  (benang/greige) mendahulukan gudang `material`.
* Roll yang DIMINTA inspeksi (tercantum di SPK QC 4-point — inspeksi per 15 yard — yang masih terbuka) → gedung
  `inspection` di lokasi yang sama (`purpose = inspection`; aturan simpan tujuan tidak berlaku). Tanpa gedung inspeksi
  di lokasi itu → perilaku lama (gudang simpan). MD Quality = cek manual, tidak memindah barang.
* Roll yang belum `tag_verified`/`label_verified` BOLEH masuk draf (tanda "belum siap" + alasannya), tetapi draf baru
  bisa DITERBITKAN untuk roll yang siap; `split_unready=True` menerbitkan yang siap dan memindah sisanya ke draf baru.
* Idempoten: kunci draf = pemicu + gudang + PT + tujuan + himpunan roll (`_id` dokumen) → retry tidak menggandakan.
* Pengaturan `putaway.auto_draft` (bawaan aktif, per badan usaha pemilik barang).
"""
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, next_doc_number, now_iso, safe_doc
from db import db
from services import placement_rules as pr
from services import putaway_order_service as pa
from services import putaway_state as _pst   # FIX-10 — tabel transisi Putaway Order
from services import warehouse_profile_service as whp

DRAFTABLE_STAGES = ("received_transit", "tag_printed", "tag_verified", "label_verified")
OPEN_SPK = ("draft", "assigned", "in_progress")
MATERIAL_STAGES = ("yarn", "grey")
SYSTEM_ACTOR = "Sistem (draf otomatis)"
MAX_ROLLS = 2000
MIN_CANCEL_REASON = 5


async def auto_draft_enabled(entity_id: str) -> bool:
    from services.config_resolver import value_of
    v = await value_of("putaway.auto_draft", {"entity_id": entity_id or ""})
    return True if v is None else bool(v)


async def inspection_requested(roll_ids: List[str]) -> Set[str]:
    """Penanda "minta inspeksi" (K-GDG-04): roll tercantum di SPK QC 4-point (inspeksi per 15 yard) yang terbuka,
    ATAU — FIX-6 (keputusan pemilik 10 Nov) — roll bertanda `inspection_request.requested` (dipilih di BARIS PO atau
    saat PENERIMAAN) yang BELUM pernah singgah di gedung inspeksi (`journey.inspection_site` kosong). Sesudah tiba di
    gedung inspeksi, perjalanan berikutnya mengikuti aturan biasa (SPK 4-point terbuka tetap menahan rutenya)."""
    if not roll_ids:
        return set()
    wanted, out = set(roll_ids), set()
    async for d in db.inspections.find({"kind": "qc_4point", "status": {"$in": list(OPEN_SPK)},
                                        "lines.roll_id": {"$in": list(roll_ids)}}, {"_id": 0, "lines.roll_id": 1}):
        out |= {ln.get("roll_id") for ln in d.get("lines") or []} & wanted
    async for r in db.inventory_rolls.find(
            {"id": {"$in": list(roll_ids)}, "inspection_request.requested": True,
             "journey.inspection_site": {"$in": [None, ""]}}, {"_id": 0, "id": 1}):
        out.add(r["id"])
    return out


def draft_block(r: Dict[str, Any]) -> Optional[str]:
    """Kenapa roll TIDAK boleh masuk draf (None = boleh). Kesiapan identitas tag dinilai saat terbit, bukan di sini."""
    if r.get("status") != pa.PA_ELIGIBLE_STATUS:
        return f"berstatus {r.get('status') or '—'}"
    if pr.is_held(r) or r.get("qc_hold_pending"):
        return "sedang/akan ditahan (QC/inspeksi)"
    if (r.get("active_movement") or {}).get("id"):
        return "sedang dalam perpindahan"
    if float(r.get("length_reserved") or 0) > 0:
        return "punya reservasi potong"
    if float(r.get("length_remaining") or 0) <= 0:
        return "panjangnya 0"
    j = r.get("journey") or {}
    if j.get("routing") == "cross_dock":
        return "dialihkan cross-dock"
    if j.get("stage") not in DRAFTABLE_STAGES:
        return f"tahap {j.get('stage') or '—'} (tidak perlu putaway)"
    return None


def is_specific(wh: Dict[str, Any]) -> bool:
    """FIX-3a (B2a FLW-IN-02) — gudang ber-aturan SPESIFIK = ada daftar aturan yang TERISI. `storage_rules.mode`
    tanpa daftar (mis. `{"mode":"category","categories":[]}` = menerima semua) BUKAN aturan spesifik; dulu dianggap
    spesifik sehingga tiga gedung "kosong" seri dan dipecah urut kode -> roll Woven ke Gudang Knitting."""
    rules = pr.warehouse_rules(wh)
    return any(rules.get(k) for k in ("categories", "grades", "fabric_types", "template_ids", "owner_entity_ids"))


def _rank(wh: Dict[str, Any], roll: Dict[str, Any]) -> Tuple[int, int, str]:
    material = str(roll.get("stage") or "").lower() in MATERIAL_STAGES
    is_mat = whp.has_role(wh, "material")
    return (0 if is_mat == material else 1, 0 if is_specific(wh) else 1, str(wh.get("code") or ""))


async def site_targets(src: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Gudang tujuan putaway di LOKASI gudang asal: simpan & inspeksi (aktif, bukan gudang asal)."""
    q: Dict[str, Any] = {"active": {"$ne": False}, "id": {"$ne": src.get("id")}}
    if src.get("site_id"):
        q["site_id"] = src["site_id"]
    else:
        q["id"] = "__tanpa_lokasi__"   # gudang tanpa lokasi: tidak ada tujuan yang bisa dipastikan
    rows = await db.warehouses.find(q, {"_id": 0}).sort("code", 1).to_list(200)
    return {"storage": [w for w in rows if whp.has_role(w, *whp.STORAGE_ROLES)],
            "inspection": [w for w in rows if whp.has_role(w, whp.INSPECTION_ROLE)]}


async def choose_destination(src: Dict[str, Any], roll: Dict[str, Any], product: Dict[str, Any],
                             targets: Dict[str, List[Dict[str, Any]]], want_inspection: bool
                             ) -> Tuple[Optional[Dict[str, Any]], str, str]:
    """→ (gudang tujuan | None, purpose, catatan). Roll yang diminta inspeksi ke gedung inspeksi lebih dulu."""
    if want_inspection:
        if whp.has_role(src, whp.INSPECTION_ROLE):
            return None, "", "menunggu inspeksi di gedung ini"
        for w in targets["inspection"]:
            if not await pr.warehouse_violations(w, roll, product, attrs=False):
                return w, "inspection", "diminta inspeksi (SPK QC 4-point terbuka / penanda minta inspeksi PO-penerimaan)"
    visiting = ((roll.get("journey") or {}).get("inspection_site") or "") == src.get("id")
    if whp.has_role(src, *whp.STORAGE_ROLES):
        if not visiting:
            return None, "", "sudah di gudang simpan"
        if not await pr.warehouse_violations(src, roll, product):
            return None, "", "boleh tetap disimpan di gedung ini"   # singgah inspeksi di gedung yang juga gudang simpan
    cands = [w for w in targets["storage"] if not await pr.warehouse_violations(w, roll, product)]
    if not cands:
        return None, "", "tidak ada gudang simpan di lokasi ini yang aturannya cocok"
    best = sorted(cands, key=lambda w: _rank(w, roll))[0]
    if len(cands) > 1 and not is_specific(best):
        # FIX-3a (FLW-IN-02) — tanpa aturan yang cocok khusus, pilihan hanya urutan kode gudang: beri tahu penyetuju.
        return best, "storage", (f"tujuan dipilih menurut urutan kode gudang ({len(cands)} gudang simpan menerima barang "
                                 "ini, belum ada aturan kategori/grade/artikel yang khusus) — periksa tujuan sebelum terbit")
    return best, "storage", ""


def _key(trigger: Dict[str, Any], src_id: str, owner: str, dest_id: str, purpose: str, roll_ids: List[str]) -> str:
    raw = "|".join([str(trigger.get("type") or ""), str(trigger.get("id") or ""), src_id, owner or "", dest_id,
                    purpose, ",".join(sorted(roll_ids))])
    return "padraft:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]


async def _insert_draft(key: str, src: Dict[str, Any], dest: Dict[str, Any], owner: str, purpose: str,
                        items: List[Dict[str, Any]], trigger: Dict[str, Any], actor_name: str,
                        split_from: str = "") -> Optional[Dict[str, Any]]:
    if await db.putaway_orders.find_one({"_id": key}, {"_id": 1}):
        return None   # idempoten — pemicu yang sama sudah menyiapkan draf ini (atau drafnya sengaja dibatalkan)
    doc = {"_id": key, "id": new_id("pa"), "pa_number": await next_doc_number("putaway_orders", "pa_number", "PA"),
           "status": "draft", "purpose": purpose,
           "from_warehouse_id": src["id"], "from_warehouse_name": src.get("name", ""),
           "to_warehouse_id": dest["id"], "to_warehouse_name": dest.get("name", ""),
           "owner_entity_id": owner, "items": items, **pa.qty_summary(items),
           "auto": {"trigger": trigger, "at": now_iso()}, "draft_rev": 0, "split_from": split_from,
           "btg_number": None, "created_at": now_iso(), "created_by": actor_name or SYSTEM_ACTOR,
           "status_history": _pst.initial_history("draft", actor_name or SYSTEM_ACTOR, "create_draft",
                                                  f"pemicu {trigger.get('type') or '—'}"),   # FIX-10
           "dispatched_at": None, "confirmed_at": None, "confirmed_by": None}
    try:
        await db.putaway_orders.insert_one(dict(doc))
    except DuplicateKeyError:
        return None
    doc.pop("_id", None)
    return doc


async def auto_draft(roll_ids: List[str], trigger: Dict[str, Any], actor_name: str = "") -> Dict[str, Any]:
    """Siapkan draf PA untuk roll yang baru tersedia. Hasil: {drafts[], unrouted[], skipped, disabled_entities[]}."""
    ids = list(dict.fromkeys(roll_ids or []))[:MAX_ROLLS]
    rolls = await db.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0}).to_list(len(ids) + 5)
    live = await pa.rolls_in_live_orders([r["id"] for r in rolls])
    cand = [r for r in rolls if draft_block(r) is None and r["id"] not in live]
    enabled: Dict[str, bool] = {}
    for o in {r.get("owner_entity_id") or "" for r in cand}:
        enabled[o] = await auto_draft_enabled(o)
    cand = [r for r in cand if enabled.get(r.get("owner_entity_id") or "")]
    whs = {w["id"]: w for w in await db.warehouses.find(
        {"id": {"$in": list({r["warehouse_id"] for r in cand})}}, {"_id": 0}).to_list(200)}
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": list({r["product_id"] for r in cand})}}, pa.PROD_FIELDS).to_list(3000)}
    requested = await inspection_requested([r["id"] for r in cand])
    targets: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    groups: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = {}
    dests: Dict[str, Dict[str, Any]] = {}
    unrouted: List[Dict[str, str]] = []
    stay: List[str] = []
    for r in cand:
        src = whs.get(r["warehouse_id"])
        if not src or src.get("stock_mode") == "quantity":
            continue   # gudang kuantitas tanpa tag: tidak ada PA per roll
        if not src.get("site_id") and not whp.has_role(src, *whp.STORAGE_ROLES):
            unrouted.append({"roll_no": r.get("roll_no", ""), "reason": f"{src.get('name')} belum ditautkan ke lokasi"})
            continue
        if src["id"] not in targets:
            targets[src["id"]] = await site_targets(src)
        p = prods.get(r["product_id"], {})
        dest, purpose, note = await choose_destination(src, r, p, targets[src["id"]], r["id"] in requested)
        if not dest:
            if note == "boleh tetap disimpan di gedung ini":
                stay.append(r["id"])
            elif note not in ("sudah di gudang simpan", "menunggu inspeksi di gedung ini"):
                unrouted.append({"roll_no": r.get("roll_no", ""), "reason": note})
            continue
        dests[dest["id"]] = dest
        item = {**pa.item_row(r, p, ""), "inspection_requested": r["id"] in requested,
                **({"destination_note": note} if note else {})}
        groups.setdefault((src["id"], r.get("owner_entity_id") or "", dest["id"], purpose), []).append(item)
    out = []
    for (src_id, owner, dest_id, purpose), items in groups.items():
        key = _key(trigger, src_id, owner, dest_id, purpose, [i["roll_id"] for i in items])
        doc = await _insert_draft(key, whs[src_id], dests[dest_id], owner, purpose, items, trigger, actor_name)
        if doc:
            out.append({k: doc.get(k) for k in ("id", "pa_number", "to_warehouse_name", "item_count", "purpose")})
    if stay:   # selesai inspeksi di gedung inspeksi yang juga gudang simpan & aturannya menerima → tersimpan di sini
        from services.rfid_print_service import set_journey
        await set_journey(stay, "stored", {"inspection_done_at": now_iso()}, only_from=list(DRAFTABLE_STAGES))
    return {"drafts": out, "unrouted": unrouted[:50], "skipped": len(rolls) - len(cand), "stored_in_place": len(stay),
            "disabled_entities": sorted(o for o, v in enabled.items() if not v)}


async def prepare_for_warehouse(warehouse_id: str, scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
    """Tombol "Siapkan draf" — roll tersedia di gudang ini yang belum masuk PA mana pun (pengisi ulang / data lama)."""
    ids = [r["id"] async for r in db.inventory_rolls.find(
        {"warehouse_id": warehouse_id, "owner_entity_id": {"$in": scope_ids}, "status": pa.PA_ELIGIBLE_STATUS,
         "length_remaining": {"$gt": 0}, "active_movement": None, "journey.stage": {"$in": list(DRAFTABLE_STAGES)}},
        {"_id": 0, "id": 1}).limit(MAX_ROLLS)]
    trigger = {"type": "manual", "id": f"{warehouse_id}:{now_iso()[:16]}", "by": actor_name}
    return await auto_draft(ids, trigger, actor_name)


# ─── Detail, ubah, terbitkan, batalkan ───────────────────────────────────────
async def _draft(order_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    order = await pa._get(order_id, scope_ids)
    if order.get("status") != "draft":
        raise HTTPException(status_code=400, detail=f"PA berstatus {order.get('status')} — hanya draf yang bisa diubah/diterbitkan.")
    return order


async def _readiness(order: Dict[str, Any], wh_to: Dict[str, Any]) -> Dict[str, Tuple[Optional[str], Any]]:
    ids = [i["roll_id"] for i in order["items"]]
    rolls = {r["id"]: r for r in await db.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0}).to_list(len(ids) + 5)}
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": list({i["product_id"] for i in order["items"]})}}, pa.PROD_FIELDS).to_list(3000)}
    other = await pa.rolls_in_live_orders(ids, exclude_order=order["id"])
    out: Dict[str, Tuple[Optional[str], Any]] = {}
    for it in order["items"]:
        r = rolls.get(it["roll_id"])
        if not r or r.get("warehouse_id") != order["from_warehouse_id"]:
            out[it["roll_id"]] = (f"Roll {it.get('roll_no')} tidak lagi di gudang asal", None)
        elif it["roll_id"] in other:
            out[it["roll_id"]] = (f"Roll {it.get('roll_no')} sudah ada di {other[it['roll_id']]['pa_number']}", None)
        else:
            out[it["roll_id"]] = await pa.roll_violation(r, wh_to, prods.get(r["product_id"], {}), order.get("purpose", "storage"))
    return out


async def detail(order_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    """PA + (untuk draf) kesiapan per roll, penanda minta-inspeksi terkini, dan pilihan gudang tujuan."""
    order = await pa._get(order_id, scope_ids)
    if order.get("status") != "draft":
        return safe_doc(order)
    wh_to = await db.warehouses.find_one({"id": order["to_warehouse_id"]}, {"_id": 0}) or {}
    src = await db.warehouses.find_one({"id": order["from_warehouse_id"]}, {"_id": 0}) or {}
    ready = await _readiness(order, wh_to)
    requested = await inspection_requested([i["roll_id"] for i in order["items"]])
    for it in order["items"]:
        why = ready.get(it["roll_id"], (None, None))[0]
        it.update({"ready": why is None, "block_reason": why or "", "inspection_requested": it["roll_id"] in requested})
    tg = await site_targets(src) if src else {"storage": [], "inspection": []}
    opts = {w["id"]: w for w in tg["storage"] + tg["inspection"]}
    order["destination_options"] = [{"warehouse_id": w["id"], "warehouse_name": w.get("name", ""),
                                     "roles": w.get("roles") or []} for w in opts.values()]
    order["ready_count"] = sum(1 for i in order["items"] if i["ready"])
    if requested and order.get("purpose") != "inspection":
        order["inspection_warning"] = (f"{len(requested)} roll diminta inspeksi (SPK QC 4-point / penanda minta inspeksi) — "
                                       "pertimbangkan tujuan gedung inspeksi.")
    return safe_doc(order)


def _purpose_for(dest: Dict[str, Any], items: List[Dict[str, Any]], wanted: str = "") -> str:
    if wanted:
        if wanted not in ("storage", "inspection"):
            raise HTTPException(status_code=400, detail="Tujuan PA harus 'storage' (simpan) atau 'inspection'.")
        if wanted == "inspection" and not whp.has_role(dest, whp.INSPECTION_ROLE):
            raise HTTPException(status_code=400, detail=f"{dest.get('name')} bukan gedung inspeksi.")
        if wanted == "storage" and not whp.has_role(dest, *whp.STORAGE_ROLES):
            raise HTTPException(status_code=400, detail=f"{dest.get('name')} bukan gudang simpan.")
        return wanted
    if whp.has_role(dest, whp.INSPECTION_ROLE) and (not whp.has_role(dest, *whp.STORAGE_ROLES)
                                                    or any(i.get("inspection_requested") for i in items)):
        return "inspection"
    if not whp.has_role(dest, *whp.STORAGE_ROLES):
        raise HTTPException(status_code=400, detail=f"{dest.get('name')} bukan gudang simpan/inspeksi.")
    return "storage"


async def update_draft(order_id: str, patch: Dict[str, Any], scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
    """Admin mengubah draf: tujuan (`to_warehouse_id`, `purpose`), keluarkan (`remove_roll_ids`) / tambah
    (`add_roll_ids`) roll. CAS `draft_rev` — dua admin mengubah bersamaan → yang kalah 409."""
    order = await _draft(order_id, scope_ids)
    src = await db.warehouses.find_one({"id": order["from_warehouse_id"]}, {"_id": 0}) or {}
    items = [i for i in order["items"] if i["roll_id"] not in set(patch.get("remove_roll_ids") or [])]
    add = [r for r in dict.fromkeys(patch.get("add_roll_ids") or []) if r not in {i["roll_id"] for i in items}]
    if add:
        rows = await db.inventory_rolls.find({"id": {"$in": add}, "warehouse_id": order["from_warehouse_id"],
                                              "owner_entity_id": order["owner_entity_id"]}, {"_id": 0}).to_list(len(add) + 5)
        live = await pa.rolls_in_live_orders(add, exclude_order=order_id)
        bad = [f"{r.get('roll_no')}: {draft_block(r) or 'sudah ada di ' + live[r['id']]['pa_number']}"
               for r in rows if draft_block(r) or r["id"] in live]
        if len(rows) != len(add) or bad:
            raise HTTPException(status_code=400, detail="Roll tambahan tidak sah (harus di gudang asal, PT yang sama, "
                                                        "bebas): " + " | ".join(bad[:5] or ["sebagian tidak ditemukan"]))
        prods = {p["id"]: p for p in await db.products.find(
            {"id": {"$in": list({r["product_id"] for r in rows})}}, pa.PROD_FIELDS).to_list(3000)}
        items += [pa.item_row(r, prods.get(r["product_id"], {}), "") for r in rows]
    if not items:
        raise HTTPException(status_code=400, detail="Draf tidak boleh kosong — batalkan drafnya bila tidak dipakai.")
    dest_id = patch.get("to_warehouse_id") or order["to_warehouse_id"]
    dest = await db.warehouses.find_one({"id": dest_id, "active": {"$ne": False}}, {"_id": 0})
    if not dest or dest_id == order["from_warehouse_id"]:
        raise HTTPException(status_code=400, detail="Gudang tujuan tidak sah (nonaktif / sama dengan gudang asal).")
    pa.assert_same_site(src, dest)
    purpose = _purpose_for(dest, items, str(patch.get("purpose") or ""))
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": list({i["product_id"] for i in items})}}, pa.PROD_FIELDS).to_list(3000)}
    viol = []
    for i in items:
        v = await pr.warehouse_violations(dest, {"owner_entity_id": order["owner_entity_id"], "grade": i.get("grade") or "A"},
                                          prods.get(i["product_id"], {}), attrs=purpose != "inspection")
        if v:
            viol.append(f"Roll {i.get('roll_no')}: {v[0]}")
    if viol:
        raise HTTPException(status_code=400, detail=" | ".join(viol[:5]))
    upd = {"items": items, **pa.qty_summary(items), "to_warehouse_id": dest["id"], "to_warehouse_name": dest.get("name", ""),
           "purpose": purpose, "updated_at": now_iso(), "draft_edited_by": actor_name}
    res = await db.putaway_orders.find_one_and_update(
        {"id": order_id, "status": "draft", "draft_rev": order.get("draft_rev", 0)},
        {"$set": upd, "$inc": {"draft_rev": 1}}, projection={"_id": 0})
    if not res:
        raise HTTPException(status_code=409, detail="Draf baru saja diubah/diterbitkan pengguna lain — muat ulang.")
    return await detail(order_id, scope_ids)


async def publish(order_id: str, scope_ids: List[str], actor_name: str, split_unready: bool = False) -> Dict[str, Any]:
    """Terbitkan draf → `open`: roll yang siap DIKLAIM (keluar ATP, sama dengan PA manual). Roll belum siap →
    409 berdaftar, atau (`split_unready`) dipindah ke draf baru supaya bisa diterbitkan sesudah tag/label siap."""
    order = await _draft(order_id, scope_ids)
    wh_to = await db.warehouses.find_one({"id": order["to_warehouse_id"]}, {"_id": 0}) or {}
    ready = await _readiness(order, wh_to)
    ok = [{**i, "epc": (ready[i["roll_id"]][1] or {}).get("epc", ""), "status": "pending"}
          for i in order["items"] if ready[i["roll_id"]][0] is None]
    rest = [{**i, "block_reason": ready[i["roll_id"]][0]} for i in order["items"] if ready[i["roll_id"]][0]]
    if not ok:
        raise HTTPException(status_code=400, detail="Belum ada roll yang siap diterbitkan: "
                                                    + " | ".join(i["block_reason"] for i in rest[:5]))
    if rest and not split_unready:
        raise HTTPException(status_code=409, detail={
            "code": "PA_DRAFT_NOT_READY", "rolls": [{"roll_no": i.get("roll_no"), "reason": i["block_reason"]} for i in rest],
            "message": f"{len(rest)} roll belum siap (tag/label belum terverifikasi atau berubah). Terbitkan yang siap "
                       "saja (sisanya tetap draf) atau keluarkan roll itu dari draf."})
    from services import registration_freeze as _rfz   # PREP-B K-OPN-03 — area beku pendaftaran awal (integrasi)
    await _rfz.assert_order_movable({**order, "items": ok}, "menerbitkan draf perintah putaway")
    from services import atomic_claim as _saga
    await _saga.claim("putaway_orders", order_id, "putaway_publish",
                      precondition={"status": "draft", "draft_rev": order.get("draft_rev", 0)}, actor=actor_name)
    claimed = False
    try:
        await pa.claim_rolls(ok, order_id, order["pa_number"], order["from_warehouse_id"])
        claimed = True
        now = now_iso()
        await _pst.finish_claimed(order_id, "draft", "publish", _saga.finish_set({
            "status": "open", "items": ok, **pa.qty_summary(ok), "published_at": now, "published_by": actor_name,
            "updated_at": now}), actor_name)
    except BaseException:
        if claimed:
            await pa._release_claims([i["roll_id"] for i in ok], order_id)
        await _saga.release("putaway_orders", order_id)
        raise
    await pa.after_claim(ok, {**order, "id": order_id})
    if rest:
        src = await db.warehouses.find_one({"id": order["from_warehouse_id"]}, {"_id": 0}) or {}
        items = [{k: v for k, v in i.items() if k != "block_reason"} for i in rest]
        trig = {"type": "split", "id": order_id}
        await _insert_draft(_key(trig, src.get("id", ""), order["owner_entity_id"], wh_to.get("id", ""),
                                 order.get("purpose", "storage"), [i["roll_id"] for i in items]),
                            src, wh_to, order["owner_entity_id"], order.get("purpose", "storage"), items, trig,
                            actor_name, split_from=order_id)
    return await pa._get(order_id, scope_ids)


async def release_inspection_drafts(roll_ids: List[str], why: str, actor_name: str) -> int:
    """FIX-3a (B2a FLW-IN-12) — SPK QC 4-point ditutup: draf PA `purpose=inspection` untuk roll-roll itu tidak relevan
    lagi (pemeriksaan selesai / roll gagal ditahan). Roll dikeluarkan dari draf (draf kosong → dibatalkan) supaya
    "satu roll satu antrean" tidak memblok draf simpan berikutnya. Mengembalikan jumlah roll yang dilepas."""
    ids = [r for r in roll_ids if r]
    if not ids:
        return 0
    freed = 0
    async for d in db.putaway_orders.find({"status": "draft", "purpose": "inspection", "items.roll_id": {"$in": ids}},
                                          {"_id": 0, "id": 1, "items": 1, "draft_rev": 1}):
        keep = [i for i in d.get("items") or [] if i.get("roll_id") not in set(ids)]
        gone = len(d.get("items") or []) - len(keep)
        upd: Dict[str, Any] = {"items": keep, **pa.qty_summary(keep), "updated_at": now_iso(),
                               "draft_edited_by": actor_name}
        if not keep:
            upd.update({"status": "cancelled", "cancel_reason": why, "cancelled_by": actor_name,
                        "cancelled_at": now_iso()})
        op = _pst.with_history({"$set": upd, "$inc": {"draft_rev": 1}}, "release_inspection_draft", "draft",
                               upd.get("status", "draft"), actor_name, why)
        res = await db.putaway_orders.update_one({"id": d["id"], "status": "draft", "draft_rev": d.get("draft_rev", 0)},
                                                 op)
        freed += gone if res.modified_count else 0
    return freed


async def cancel_draft(order_id: str, reason: str, scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
    from input_rules import require_reason   # FIX-3a — K-14 dihitung huruf (satu validator bersama)
    why = require_reason(reason, label="Alasan membatalkan draf")
    await _draft(order_id, scope_ids)
    res = await db.putaway_orders.find_one_and_update(
        {"id": order_id, "status": "draft"},
        _pst.with_history({"$set": {"status": "cancelled", "cancel_reason": why, "cancelled_by": actor_name,
                                    "cancelled_at": now_iso(), "updated_at": now_iso()}},
                          "cancel_draft", "draft", "cancelled", actor_name, why), projection={"_id": 0})
    if not res:
        raise HTTPException(status_code=409, detail="Draf baru saja diterbitkan/diubah — muat ulang.")
    return await pa._get(order_id, scope_ids)
