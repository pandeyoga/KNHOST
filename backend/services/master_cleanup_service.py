"""PREP-A (K-OPN-06) — terapkan lembar perbaikan master produk sebagai SATU batch berjejak + rollback.

Pola saga repo (tanpa transaksi Mongo): rencana DURABLE dulu (`master_cleanup_batches`, status `planned`)
→ `atomic_claim.claim()` → tulisan per baris dengan CAS (produk harus masih seperti saat pratinjau) →
`finish_set()` mencabut kunci. Setiap produk yang disentuh diberi `last_cleanup_batch` (+ `cleanup_before`)
sehingga rollback tetap bisa membalik walau proses mati di tengah (produk "yatim" dipindai ulang).

* GANTI_NAMA → `master_governance_service.rename_product` (riwayat nama).
* GANTI_KODE → SKU lama TIDAK diubah: produk baru berkode benar (salinan atribut/induk/harga dasar/harga PT),
  alias supplier dipindah ke produk baru, produk lama nonaktif + `superseded_by` = produk baru.
* GABUNG_KE  → produk lama nonaktif + `superseded_by` = produk induk (alias supplier ikut ke induk).
* NONAKTIFKAN → nonaktif tanpa pengganti.
Stok TIDAK dipindah (didaftarkan ulang dari fisik — paket opname awal); dokumen lama tidak diubah.
"""
from typing import Any, Dict, List

from fastapi import HTTPException

from core_utils import new_id, now_iso, safe_doc
from db import db
from role_registry import role_in
from services import atomic_claim
from services import master_cleanup_validate as mv
from services import master_governance_service as mg
from services import master_usage_service as mu

COLL = "master_cleanup_batches"
ROLLBACKABLE = ["applied", "applied_partial", "failed"]
_NO_COPY = {"_id", "id", "sku", "created_at", "updated_at", "media", "media_revision", "cover_media_id",
            "name_history", "superseded_by", "superseded_at", "superseded_reason", "superseded_batch",
            "last_cleanup_batch", "cleanup_before", "saga_lock", "last_governance_batch", "batch_lot_rolls",
            "is_featured", "featured_by", "featured_note", "featured_rank", "featured_until", "replaces_product_ids",
            "replaces_skus", "created_by_cleanup_batch", "rolled_back_by_batch", "deactivated_batch",
            "import_batch", "source_file", "demo_batch"}
_SUP_UNSET = {"superseded_by": "", "superseded_at": "", "superseded_reason": "", "superseded_batch": "",
              "cleanup_before": "", "last_cleanup_batch": "", "deactivated_batch": ""}


class CleanupRowError(Exception):
    pass


def _reason(exc: Exception) -> str:
    d = getattr(exc, "detail", None)
    if isinstance(d, dict):
        d = d.get("message") or str(d)
    return str(d or exc)[:300]


def _not_superseded() -> Dict[str, Any]:
    return {"$or": [{"superseded_by": {"$exists": False}}, {"superseded_by": {"$in": ["", None]}}]}


async def _move_aliases(src_id: str, dst: Dict[str, Any], batch_id: str) -> List[str]:
    """Alias supplier (kode/nama versi supplier) ikut produk pengganti — pindai label supplier menemukan kode benar."""
    moved = []
    rows = await db.supplier_items.find({"product_id": src_id, "status": {"$ne": "inactive"}},
                                        {"_id": 0, "id": 1}).to_list(500)
    for si in rows:
        r = await db.supplier_items.update_one(
            {"id": si["id"], "product_id": src_id},
            {"$set": {"product_id": dst["id"], "sku": dst.get("sku", ""), "product_name": dst.get("name", ""),
                      "moved_by_cleanup_batch": batch_id, "moved_from_product_id": src_id, "updated_at": now_iso()}})
        if r.modified_count:
            moved.append(si["id"])
    return moved


async def _move_aliases_back(ids: List[str], cur_id: str, old: Dict[str, Any], batch_id: str) -> int:
    if not ids:
        return 0
    r = await db.supplier_items.update_many(
        {"id": {"$in": ids}, "product_id": cur_id, "moved_by_cleanup_batch": batch_id},
        {"$set": {"product_id": old["id"], "sku": old.get("sku", ""), "product_name": old.get("name", ""),
                  "updated_at": now_iso()}, "$unset": {"moved_by_cleanup_batch": "", "moved_from_product_id": ""}})
    return r.modified_count


async def _retire(step: Dict[str, Any], batch_id: str, sets: Dict[str, Any]) -> Dict[str, Any]:
    """CAS produk lama: status & 'belum digantikan' harus masih seperti saat pratinjau."""
    old = await db.products.find_one(
        {"id": step["product_id"], "status": step["before_status"], "saga_lock": {"$exists": False},
         **_not_superseded()}, {"_id": 0})
    if not old:
        raise CleanupRowError("Produk berubah sejak pratinjau (status/penggantinya) — baris dilewati.")
    before = {"status": old.get("status", "active"), "variant_key": old.get("variant_key"),
              "updated_at": old.get("updated_at")}
    res = await db.products.update_one(
        {"id": old["id"], "status": before["status"], "updated_at": before["updated_at"], **_not_superseded()},
        {"$set": {**sets, "status": "inactive", "last_cleanup_batch": batch_id, "cleanup_before": before,
                  "updated_at": now_iso()}})
    if not res.modified_count:
        raise CleanupRowError("Produk berubah saat diterapkan — baris dilewati.")
    return old


async def _recode(step: Dict[str, Any], batch_id: str, actor: Dict[str, Any], note: str) -> Dict[str, Any]:
    nid, code = new_id("prod"), step["kode_benar"]
    why = f"GANTI_KODE → {code}: {step.get('catatan') or note}"
    peek = await db.products.find_one({"id": step["product_id"]}, {"_id": 0, "variant_key": 1}) or {}
    sets = {"superseded_by": nid, "superseded_at": now_iso(), "superseded_reason": why, "superseded_batch": batch_id}
    if peek.get("variant_key"):   # kombinasi varian (unik per induk) diserahkan ke produk berkode benar
        sets["variant_key"] = f"{peek['variant_key']}~digantikan~{nid}"
    old = await _retire(step, batch_id, sets)
    doc = {k: v for k, v in old.items() if k not in _NO_COPY}
    doc.update(id=nid, sku=code, name=step.get("nama_benar") or old.get("name"), status="active",
               replaces_product_ids=[old["id"]], replaces_skus=[old.get("sku")], created_by_cleanup_batch=batch_id,
               created_by=actor.get("name", ""), created_at=now_iso(), updated_at=now_iso(), batch_lot_rolls=[],
               name_history=([{"from": old.get("name"), "to": step["nama_benar"], "reason": why,
                               "by": actor.get("name", ""), "at": now_iso(), "batch": batch_id}]
                             if step.get("nama_benar") else []))
    try:
        await db.products.insert_one(dict(doc))
    except Exception as exc:  # noqa: BLE001 — kompensasi: kembalikan produk lama
        await db.products.update_one(
            {"id": old["id"], "superseded_by": nid, "last_cleanup_batch": batch_id},
            {"$set": {"status": old.get("status", "active"), "updated_at": now_iso(),
                      **({"variant_key": old["variant_key"]} if old.get("variant_key") else {})},
             "$unset": _SUP_UNSET})
        raise CleanupRowError(f"Produk baru {code} gagal dibuat: {_reason(exc)}") from exc
    moved = await _move_aliases(old["id"], doc, batch_id)
    copies = []
    for ep in await db.entity_prices.find({"product_id": old["id"], "status": {"$ne": "inactive"}},
                                          {"_id": 0}).to_list(500):
        c = {**ep, "id": new_id("epr"), "product_id": nid, "sku": code, "product_name": doc["name"],
             "copied_from_id": ep.get("id"), "cleanup_batch": batch_id, "created_at": now_iso(),
             "updated_at": now_iso(), "created_by": actor.get("name", "")}
        await db.entity_prices.insert_one(c)
        copies.append(c["id"])
    return {"new_product_id": nid, "new_sku": code, "new_name": doc["name"], "aliases_moved": moved,
            "price_copies": copies, "before": {"status": old.get("status", "active"),
                                               "variant_key": old.get("variant_key")}}


async def _apply_step(step: Dict[str, Any], batch_id: str, actor: Dict[str, Any], note: str,
                      new_ids: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    t = step["tindakan"]
    base = {"row": step["row"], "tindakan": t, "product_id": step["product_id"], "sku": step["sku"]}
    if t == mv.RENAME:
        reason = f"Perbaikan master {batch_id}: {step.get('catatan') or note}"
        await mg.rename_product(step["product_id"], step["nama_benar"], reason, actor,
                                expect_name=step["before_name"], batch_id=batch_id)
        return {**base, "before": {"name": step["before_name"]}, "after": {"name": step["nama_benar"]}}
    if t == mv.RECODE:
        out = await _recode(step, batch_id, actor, note)
        new_ids[step["kode_benar"].upper()] = {"id": out["new_product_id"], "sku": out["new_sku"],
                                                "name": out["new_name"]}
        return {**base, **out}
    if t == mv.MERGE:
        if step.get("target_new_code"):
            tgt = new_ids.get(step["target_new_code"].upper())
            if not tgt:
                raise CleanupRowError(f"Produk baru {step['target_new_code']} gagal dibuat di batch ini — baris dilewati.")
        else:
            tgt = await db.products.find_one({"id": step["target_id"], "status": "active", **_not_superseded()},
                                             {"_id": 0, "id": 1, "sku": 1, "name": 1})
            if not tgt:
                raise CleanupRowError(f"SKU target {step['target_sku']} berubah (nonaktif/digantikan) sejak pratinjau.")
        why = f"GABUNG_KE {tgt['sku']}: {step.get('catatan') or note}"
        old = await _retire(step, batch_id, {"superseded_by": tgt["id"], "superseded_at": now_iso(),
                                             "superseded_reason": why, "superseded_batch": batch_id})
        moved = await _move_aliases(old["id"], tgt, batch_id)
        return {**base, "target_id": tgt["id"], "target_sku": tgt["sku"], "aliases_moved": moved,
                "before": {"status": old.get("status", "active")}}
    if t == mv.DEACTIVATE:
        old = await _retire(step, batch_id, {"deactivated_batch": batch_id})
        return {**base, "before": {"status": old.get("status", "active")}}
    raise CleanupRowError(f"Tindakan {t} tidak dikenal.")


async def apply_cleanup(actor: Dict[str, Any], actions: List[Dict[str, Any]], signature: str, note: str,
                        filename: str = "") -> Dict[str, Any]:
    note = (note or "").strip()
    if len(note) < 5:
        raise HTTPException(status_code=422, detail="Catatan batch wajib (min. 5 karakter) — alasan perbaikan master.")
    pv = await mv.validate(actor, actions)
    if signature != pv["preview_signature"]:
        raise HTTPException(status_code=409, detail="Data berubah sejak pratinjau — pratinjau ulang sebelum menerapkan.")
    if not pv["can_apply"]:
        raise HTTPException(status_code=422, detail=(
            f"Lembar masih memuat {pv['summary']['errors']} galat atau tidak ada perubahan — perbaiki lalu pratinjau ulang."))
    batch_id = new_id("mcb")
    await db[COLL].insert_one({
        "id": batch_id, "kind": "master_cleanup", "status": "planned", "note": note,
        "source_filename": (filename or "")[:200], "preview_signature": signature, "summary": pv["summary"],
        "planned": pv["plan"], "changes": [], "failed": [], "applied_by": actor.get("name", ""),
        "applied_by_id": actor.get("id", ""), "created_at": now_iso()})
    await atomic_claim.claim(COLL, batch_id, "apply", precondition={"status": "planned"}, actor=actor.get("name", ""))
    new_ids: Dict[str, Dict[str, Any]] = {}
    changes, failed = [], []
    for step in pv["plan"]:
        try:
            ch = await _apply_step(step, batch_id, actor, note, new_ids)
        except Exception as exc:  # noqa: BLE001 — satu baris gagal tidak menggagalkan batch; tercatat
            failed.append({"row": step["row"], "sku": step["sku"], "tindakan": step["tindakan"], "reason": _reason(exc)})
            continue
        changes.append(ch)
        await db[COLL].update_one({"id": batch_id}, {"$push": {"changes": ch}})
    status = "applied" if not failed else ("applied_partial" if changes else "failed")
    await db[COLL].update_one({"id": batch_id}, atomic_claim.finish_set({
        "status": status, "failed": failed, "changed": len(changes), "applied_at": now_iso()}))
    return safe_doc(await db[COLL].find_one({"id": batch_id}, {"_id": 0}))


# ─── rollback ─────────────────────────────────────────────────────────────────
async def _restore_old(pid: str, expect_sup: Any, batch_id: str, before: Dict[str, Any]) -> bool:
    match: Dict[str, Any] = {"id": pid, "last_cleanup_batch": batch_id}
    if expect_sup is not None:
        match["superseded_by"] = expect_sup
    sets = {"status": before.get("status") or "active", "updated_at": now_iso()}
    if before.get("variant_key"):
        sets["variant_key"] = before["variant_key"]
    r = await db.products.update_one(match, {"$set": sets, "$unset": _SUP_UNSET})
    return bool(r.modified_count)


async def _undo_new_product(nid: str, old_id: str, batch_id: str, reason: str) -> str:
    """Produk hasil GANTI_KODE: dihapus bila belum dipakai, dinonaktifkan (+ digantikan oleh SKU lama) bila sudah."""
    info = await mu.usage("product", nid) if await db.products.find_one({"id": nid}, {"_id": 0, "id": 1}) else None
    if info is None:
        return "sudah tidak ada"
    if not info["in_use"]:
        await db.products.delete_one({"id": nid, "created_by_cleanup_batch": batch_id})
        return "dihapus (belum dipakai)"
    cur = await db.products.find_one({"id": nid}, {"_id": 0, "variant_key": 1}) or {}
    sets = {"status": "inactive", "superseded_by": old_id, "superseded_at": now_iso(),
            "superseded_reason": f"Batal batch {batch_id}: {reason}", "rolled_back_by_batch": batch_id,
            "updated_at": now_iso()}
    if cur.get("variant_key") and "~" not in cur["variant_key"]:
        sets["variant_key"] = f"{cur['variant_key']}~dibatalkan~{batch_id}"
    await db.products.update_one({"id": nid, "created_by_cleanup_batch": batch_id}, {"$set": sets})
    refs = ", ".join(f"{r['label']} ({r['count']})" for r in info["refs"])
    return f"dinonaktifkan (sudah dipakai: {refs})"


async def _undo(ch: Dict[str, Any], batch_id: str, reason: str, actor: Dict[str, Any]) -> str:
    t, pid = ch["tindakan"], ch["product_id"]
    if t == mv.RENAME:
        r = await db.products.update_one(
            {"id": pid, "name": ch["after"]["name"], "last_cleanup_batch": batch_id},
            {"$set": {"name": ch["before"]["name"], "updated_at": now_iso()}, "$unset": {"last_cleanup_batch": ""},
             "$push": {"name_history": {"from": ch["after"]["name"], "to": ch["before"]["name"],
                                        "reason": f"Batal batch {batch_id}: {reason}", "by": actor.get("name", ""),
                                        "at": now_iso(), "batch": batch_id}}})
        if not r.modified_count:
            raise CleanupRowError("Nama sudah diubah lagi sesudah batch — tidak dikembalikan.")
        return "nama dikembalikan"
    if t == mv.DEACTIVATE:
        if not await _restore_old(pid, None, batch_id, ch.get("before") or {}):
            raise CleanupRowError("Status SKU sudah diubah lagi sesudah batch — tidak dikembalikan.")
        return "diaktifkan kembali"
    old = await db.products.find_one({"id": pid}, {"_id": 0, "id": 1, "sku": 1, "name": 1}) or {"id": pid}
    if t == mv.MERGE:
        await _move_aliases_back(ch.get("aliases_moved") or [], ch["target_id"], old, batch_id)
        if not await _restore_old(pid, ch["target_id"], batch_id, ch.get("before") or {}):
            raise CleanupRowError("SKU sudah diubah lagi sesudah batch — tidak dikembalikan.")
        return "gabung dibatalkan"
    if t == mv.RECODE:
        nid = ch["new_product_id"]
        await _move_aliases_back(ch.get("aliases_moved") or [], nid, old, batch_id)
        if ch.get("price_copies"):
            await db.entity_prices.delete_many({"id": {"$in": ch["price_copies"]}, "cleanup_batch": batch_id})
        fate = await _undo_new_product(nid, pid, batch_id, reason)
        if not await _restore_old(pid, nid, batch_id, ch.get("before") or {}):
            raise CleanupRowError(f"SKU lama sudah diubah lagi sesudah batch — tidak dikembalikan; produk baru {fate}.")
        return f"SKU lama aktif kembali; produk baru {ch.get('new_sku')} {fate}"
    raise CleanupRowError(f"Tindakan {t} tidak dikenal.")


async def _orphans(batch_id: str, known: List[str]) -> List[Dict[str, Any]]:
    """Produk bertanda batch ini tetapi tak tercatat di `changes` (proses mati di tengah baris)."""
    rows = await db.products.find({"$or": [{"last_cleanup_batch": batch_id}, {"created_by_cleanup_batch": batch_id}],
                                   "id": {"$nin": known}}, {"_id": 0}).to_list(5000)
    return rows


async def rollback_cleanup(batch_id: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail="Alasan pembatalan wajib (min. 5 karakter).")
    head = await db[COLL].find_one({"id": batch_id}, {"_id": 0, "status": 1, "changes.tindakan": 1})
    if not head:
        raise HTTPException(status_code=404, detail="Batch perbaikan master tidak ditemukan.")
    if head.get("status") not in ROLLBACKABLE:
        raise HTTPException(status_code=409, detail=f"Batch berstatus '{head.get('status')}' — tidak bisa dibatalkan.")
    if any(c.get("tindakan") in mv.RETIRING for c in head.get("changes") or []) and \
            not role_in(actor.get("role"), mu.LIFECYCLE_ROLES):
        raise HTTPException(status_code=403, detail="Hanya Admin atau MD yang boleh membatalkan batch yang menggantikan SKU.")
    b = await atomic_claim.claim(COLL, batch_id, "rollback", precondition={"status": {"$in": ROLLBACKABLE}},
                                 actor=actor.get("name", ""))
    done, skipped = [], []
    changes = list(b.get("changes") or [])
    for ch in reversed(changes):
        try:
            done.append({"row": ch["row"], "sku": ch["sku"], "result": await _undo(ch, batch_id, reason, actor)})
        except Exception as exc:  # noqa: BLE001 — tercatat, baris lain tetap dibalik
            skipped.append({"row": ch["row"], "sku": ch["sku"], "reason": _reason(exc)})
    known = [c["product_id"] for c in changes] + [c["new_product_id"] for c in changes if c.get("new_product_id")]
    for o in await _orphans(batch_id, known):
        if o.get("created_by_cleanup_batch") == batch_id:
            fate = await _undo_new_product(o["id"], (o.get("replaces_product_ids") or [""])[0], batch_id, reason)
        else:
            ok = await _restore_old(o["id"], None, batch_id, o.get("cleanup_before") or {"status": o.get("status")})
            fate = "dipulihkan dari jejak produk" if ok else "tidak bisa dipulihkan"
        done.append({"row": None, "sku": o.get("sku"), "result": f"yatim: {fate}"})
    await db[COLL].update_one({"id": batch_id}, atomic_claim.finish_set({
        "status": "rolled_back", "rollback_reason": reason, "rolled_back_by": actor.get("name", ""),
        "rolled_back_at": now_iso(), "rollback_done": done, "rollback_skipped": skipped}))
    return safe_doc(await db[COLL].find_one({"id": batch_id}, {"_id": 0}))


async def list_cleanup_batches(limit: int = 50) -> List[Dict[str, Any]]:
    rows = await db[COLL].aggregate([
        {"$sort": {"created_at": -1}}, {"$limit": max(1, min(int(limit or 50), 200))},
        {"$addFields": {"n_changes": {"$size": {"$ifNull": ["$changes", []]}}}},
        {"$project": {"_id": 0, "planned": 0, "changes": 0, "rollback_done": 0}},
    ]).to_list(200)
    return [safe_doc(r) for r in rows]


async def get_cleanup_batch(batch_id: str) -> Dict[str, Any]:
    b = await db[COLL].find_one({"id": batch_id}, {"_id": 0, "planned": 0})
    if not b:
        raise HTTPException(status_code=404, detail="Batch perbaikan master tidak ditemukan.")
    return safe_doc(b)
