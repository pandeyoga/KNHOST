"""L03 LN-034 — uji ulang SKU existing per supplier: siklus terpisah, hasil teknis tanpa kontrak, keputusan PIC.

Keputusan owner (rev 1.3): hasil gagal → "Menunggu keputusan PIC"; tidak menghentikan produksi, tidak
menonaktifkan produk/kontrak/stok, dan hasil gagal tidak pernah berubah menjadi ACC. Histori lengkap
tetap di `md_samples` (SSOT); ringkasan kelayakan dihitung dari record, bukan satu field pemenang.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from db import db
from core_utils import now_iso, safe_doc, timeline_entry

COLL = "md_samples"
PENDING_PIC = "pending_pic"
DESIGN_OK = ("approved", "final_submitted", "active")
PIC_ACTIONS = {
    "retest": "Uji ulang (siklus baru supplier sama)",
    "operational_note": "Keputusan operasional beralasan (cakupan eksplisit)",
    "override": "Override eksplisit — tetap tercatat GAGAL",
}
CONTRACT_TYPES = ("purchase", "makloon")


class RevalError(ValueError):
    pass


def key_of(pid: str, supplier_id: str, t: str) -> str:
    return f"{pid}:{supplier_id}:{t}"


async def partner(supplier_id: str) -> Dict[str, str]:
    row = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0, "name": 1})
    if row:
        return {"supplier_id": supplier_id, "supplier_name": row.get("name", ""), "partner_kind": "supplier"}
    row = await db.makloons.find_one({"id": supplier_id}, {"_id": 0, "name": 1})
    if row:
        return {"supplier_id": supplier_id, "supplier_name": row.get("name", ""), "partner_kind": "makloon"}
    raise RevalError("Supplier/mitra yang diuji ulang tidak ditemukan — pilih dari daftar.")


async def existing_artwork(body: Dict[str, Any], pid: str) -> Dict[str, Any]:
    """Proofing SKU existing memakai artwork/versi existing yang sudah disetujui — tidak membuat desain baru."""
    spec = await db.md_specs.find_one({"product_id": pid}, {"_id": 0, "design_id": 1, "design_version": 1}, sort=[("created_at", -1)]) or {}
    did = (body.get("design_id") or spec.get("design_id") or "").strip()
    if not did:
        raise RevalError("Proofing uji ulang butuh artwork existing yang sudah disetujui — SKU ini tidak punya artwork.")
    d = await db.design_gallery.find_one({"id": did}, {"_id": 0, "id": 1, "status": 1, "version": 1, "on_hold": 1, "code": 1})
    if not d or d.get("status") not in DESIGN_OK or d.get("on_hold"):
        raise RevalError("Artwork acuan belum disetujui atau sedang HOLD — proofing uji ulang hanya memakai artwork ACC.")
    ver = int(body.get("design_version") or spec.get("design_version") or d.get("version") or 1)
    return {"design_id": did, "design_version": ver}


async def cycle_context(pid: str, supplier_id: str, types: List[str]) -> Dict[str, Any]:
    q = {"product_id": pid, "purpose": "revalidation", "revalidation.supplier_id": supplier_id, "status": {"$ne": "cancelled"}}
    n = await db[COLL].count_documents(q)
    prev = await db[COLL].find_one({**q, "status": {"$in": ["decided", PENDING_PIC]}},
                                   {"_id": 0, "id": 1, "number": 1, "revalidation": 1, "decision": 1},
                                   sort=[("created_at", -1)])
    ref = None
    if prev:
        ref = {"sample_id": prev["id"], "number": prev.get("number", ""),
               "cycle_no": (prev.get("revalidation") or {}).get("cycle_no"),
               "result": (prev.get("decision") or {}).get("result", "")}
    return {"cycle_no": n + 1, "reference": ref, "types": types}


async def prepare(body: Dict[str, Any], pid: str, types: List[str]) -> Dict[str, Any]:
    sid = (body.get("revalidation_supplier_id") or "").strip()
    if not sid:
        raise RevalError("Pilih supplier/mitra yang diuji ulang — hasil disimpan per supplier.")
    reason = (body.get("revalidation_reason") or "").strip()
    if len(reason) < 3:
        raise RevalError("Tulis alasan siklus uji ulang (mis. supplier baru, keluhan, pergantian bahan).")
    p = await partner(sid)
    ctx = await cycle_context(pid, sid, types)
    return {**p, "reason": reason, **ctx, "requested_at": now_iso()}


# ─── Keputusan teknis ────────────────────────────────────────────────────────
async def _validate_contract_ref(contract_id: str, cur: Dict[str, Any], supplier_id: str) -> Dict[str, Any]:
    c = await db.supplier_contracts.find_one({"id": contract_id}, {"_id": 0, "id": 1, "contract_number": 1, "partner_id": 1,
                                                                   "product_id": 1, "entity_id": 1, "contract_type": 1, "status": 1})
    if not c:
        raise RevalError("Kontrak yang direferensikan tidak ditemukan.")
    if c.get("partner_id") != supplier_id:
        raise RevalError("Kontrak bukan milik supplier yang diuji ulang.")
    if c.get("product_id") and c["product_id"] != cur.get("product_id"):
        raise RevalError("Kontrak untuk produk lain — tidak bisa direferensikan.")
    if c.get("entity_id") not in ("", None, "all", cur.get("entity_id")):
        raise RevalError("Kontrak milik badan usaha lain.")
    if c.get("contract_type") not in CONTRACT_TYPES:
        raise RevalError("Jenis kontrak tidak sesuai untuk referensi uji ulang.")
    return {"contract_id": c["id"], "contract_number": c.get("contract_number", ""), "contract_type": c.get("contract_type")}


async def contract_options(cur: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Kontrak supplier siklus ini yang lolos validasi referensi (produk/entitas/jenis).

    AUD-RND-03 — keputusan owner 2026-10-21: kontrak DIHENTIKAN, KEDALUWARSA, dan BATAL tetap boleh
    dipakai sebagai referensi historis → daftar = yang diterima `_validate_contract_ref` (semua status),
    statusnya dikirim agar layar memberi label."""
    sid = (cur.get("revalidation") or {}).get("supplier_id")
    if not sid:
        return []
    q = {"partner_id": sid, "contract_type": {"$in": list(CONTRACT_TYPES)},
         "product_id": {"$in": ["", None, cur.get("product_id")]},
         "entity_id": {"$in": ["", None, "all", cur.get("entity_id")]}}
    rows = await db.supplier_contracts.find(q, {"_id": 0, "id": 1, "contract_number": 1, "contract_type": 1, "status": 1,
                                                "product_id": 1, "valid_from": 1, "valid_to": 1}).sort("created_at", -1).to_list(100)
    return rows


async def decide(cur: Dict[str, Any], payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Hasil teknis uji ulang: pass → selesai; fail → Menunggu keputusan PIC. Tanpa harga, tanpa kontrak baru."""
    rv = cur.get("revalidation") or {}
    sid = rv.get("supplier_id") or (payload.get("supplier_id") or "").strip()
    result = (payload.get("result") or "").strip()
    if result not in ("pass", "fail"):
        raise RevalError("Pilih hasil teknis uji ulang: lulus atau gagal.")
    if payload.get("supplier_id") and rv.get("supplier_id") and payload["supplier_id"] != rv["supplier_id"]:
        raise RevalError("Hasil uji ulang hanya untuk supplier siklus ini — supplier lain dibuat siklus terpisah.")
    rounds = [r for r in cur.get("rounds") or [] if r.get("supplier_id") == sid and r.get("result")]
    note = (payload.get("note") or "").strip()
    if result == "pass" and not any(r.get("result") == "acc" for r in rounds):
        raise RevalError("Belum ada round ACC dari supplier ini — tidak bisa dinyatakan lulus.")
    if result == "fail" and len(note) < 5:
        raise RevalError("Tulis alasan/temuan kegagalan (min. 5 karakter) — dibaca PIC saat memutus tindak lanjut.")
    contract_ref = await _validate_contract_ref(payload["contract_id"], cur, sid) if payload.get("contract_id") else {}
    last = rounds[-1] if rounds else {}
    name = actor.get("name", "")
    decision = {"result": result, "result_label": "Lulus" if result == "pass" else "Gagal",
                "supplier_id": sid, "supplier_name": rv.get("supplier_name", ""), "note": note,
                "reason_code": payload.get("reason_code") or "", "decided_by": name, "decided_at": now_iso(),
                "round_id": last.get("id", ""), "round_no": last.get("round_no"), "score": last.get("score"),
                "cycle_no": rv.get("cycle_no"), "reference": rv.get("reference"), "types": cur.get("sample_types") or [],
                "product_id": cur.get("product_id", ""), "product_sku": cur.get("product_sku", ""),
                "design_id": cur.get("design_id", ""), "design_version": cur.get("design_version"),
                "price": 0, "contract_id": contract_ref.get("contract_id", ""),
                "contract_number": contract_ref.get("contract_number", ""), "contract_ref": contract_ref,
                "contract_created": False}
    status = "decided" if result == "pass" else PENDING_PIC
    upd: Dict[str, Any] = {"$set": {"status": status, "decision": decision, "updated_at": now_iso()},
                           "$push": {"timeline": timeline_entry(
                               "revalidation_" + result,
                               f"Uji ulang siklus {rv.get('cycle_no')} {rv.get('supplier_name', '')}: "
                               + ("LULUS" if result == "pass" else "GAGAL — menunggu keputusan PIC"), name, note)}}
    if result == "pass":
        upd["$unset"] = {"open_reval_keys": ""}
    res = await db[COLL].update_one({"id": cur["id"], "status": {"$in": ["in_progress", "assessed"]}}, upd)
    if res.matched_count == 0:
        raise RevalError("Uji ulang ini baru saja diputus pengguna lain — muat ulang.")
    await db.products.update_one({"id": cur.get("product_id")}, {"$push": {"rnd_test_history": {"$each": [{
        "sample_id": cur["id"], "sample_number": cur.get("number", ""), "types": cur.get("sample_types") or [],
        "supplier_id": sid, "supplier_name": rv.get("supplier_name", ""), "cycle_no": rv.get("cycle_no"),
        "result": result, "score": last.get("score"), "decided_by": name, "decided_at": decision["decided_at"]}], "$slice": -50}}})
    if result == "fail":
        try:
            from services import notification_service as notif
            await notif.create_addressed(roles=("md", "manager"), entity_id=cur.get("entity_id", ""), notif_type="revalidation_failed",
                                         title=f"Uji ulang gagal · {cur.get('product_sku')} · {rv.get('supplier_name')}",
                                         body=note[:200], severity="warning", link="rnd-samples", ref=cur["id"])
        except Exception:  # noqa: BLE001 — notifikasi bukan syarat keputusan
            pass
    return safe_doc(await db[COLL].find_one({"id": cur["id"]}, {"_id": 0}))


# ─── Keputusan PIC atas hasil gagal ──────────────────────────────────────────
async def pic_decide(cur: Dict[str, Any], payload: Dict[str, Any], actor: Dict[str, Any], *, can_override: bool) -> Dict[str, Any]:
    if cur.get("status") != PENDING_PIC:
        raise RevalError("Uji ulang ini tidak sedang menunggu keputusan PIC.")
    action = (payload.get("action") or "").strip()
    if action not in PIC_ACTIONS:
        raise RevalError("Pilih tindak lanjut: uji ulang, keputusan operasional, atau override.")
    reason = (payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise RevalError("Alasan keputusan PIC wajib (min. 5 karakter).")
    if action == "override" and not can_override:
        raise PermissionError("Permission ditolak: rnd.override_fail (override hasil gagal).")
    scope = payload.get("scope") or {}
    rv = cur.get("revalidation") or {}
    rec = {"action": action, "action_label": PIC_ACTIONS[action], "reason": reason, "by": actor.get("name", ""),
           "at": now_iso(), "scope": {"supplier_id": rv.get("supplier_id"), "supplier_name": rv.get("supplier_name"),
                                     "product_id": cur.get("product_id"), "documents": list(scope.get("documents") or [])[:20],
                                     "note": (scope.get("note") or "").strip()[:300]},
           "result_unchanged": "fail"}
    res = await db[COLL].update_one({"id": cur["id"], "status": PENDING_PIC}, {
        "$set": {"status": "decided", "pic_decision": rec, "decision.pic_action": action,
                 "decision.override": action == "override", "updated_at": now_iso()},
        "$unset": {"open_reval_keys": ""},
        "$push": {"timeline": timeline_entry("pic_decision", f"Keputusan PIC: {PIC_ACTIONS[action]} (hasil tetap GAGAL)",
                                               rec["by"], reason)}})
    if res.matched_count == 0:
        raise RevalError("Keputusan PIC baru saja dicatat pengguna lain — muat ulang.")
    out = {"sample": safe_doc(await db[COLL].find_one({"id": cur["id"]}, {"_id": 0})), "retest": None}
    if action == "retest":
        from services import rnd_sample_service as smp
        body = {"product_id": cur.get("product_id"), "sample_types": cur.get("sample_types") or [],
                "revalidation_supplier_id": rv.get("supplier_id"), "revalidation_reason": f"Uji ulang atas keputusan PIC: {reason}",
                "design_id": cur.get("design_id") or "", "design_version": cur.get("design_version") or 0,
                "color_target": cur.get("color_target") or {}, "title": ""}
        body = await smp.prepare_revalidation(body)
        out["retest"] = await smp.create_sample(body, entity_id=cur.get("entity_id", ""), actor=actor.get("name", ""))
        await db[COLL].update_one({"id": cur["id"]}, {"$set": {"pic_decision.retest_sample_id": out["retest"]["id"],
                                                              "pic_decision.retest_number": out["retest"].get("number", "")}})
    return out


# ─── Bacaan: kelayakan per supplier & antrean PIC ────────────────────────────
def _state(s: Dict[str, Any]) -> str:
    d = s.get("decision") or {}
    if s.get("status") == PENDING_PIC:
        return "fail_pending_pic"
    if s.get("status") == "decided":
        if d.get("result") == "fail":
            return "fail_override" if d.get("override") else "fail_decided"
        return "pass"
    return "open"


STATE_LABEL = {"pass": "Lulus", "fail_pending_pic": "Gagal — menunggu keputusan PIC", "fail_decided": "Gagal (diputus PIC)",
               "fail_override": "Gagal — override PIC", "open": "Siklus berjalan"}


async def eligibility(pid: str) -> Dict[str, Any]:
    rows = await db[COLL].find({"product_id": pid, "purpose": "revalidation", "status": {"$ne": "cancelled"},
                                "revalidation.supplier_id": {"$exists": True}},
                               {"_id": 0, "id": 1, "number": 1, "status": 1, "sample_types": 1, "revalidation": 1,
                                "decision": 1, "pic_decision": 1, "created_at": 1}).sort("created_at", 1).to_list(500)
    by: Dict[str, Dict[str, Any]] = {}
    for s in rows:
        rv = s.get("revalidation") or {}
        st = _state(s)
        cyc = {"sample_id": s["id"], "number": s.get("number"), "cycle_no": rv.get("cycle_no"), "types": s.get("sample_types"),
               "state": st, "state_label": STATE_LABEL[st], "reference": rv.get("reference"), "reason": rv.get("reason"),
               "decided_at": (s.get("decision") or {}).get("decided_at"), "pic_decision": s.get("pic_decision")}
        g = by.setdefault(rv["supplier_id"], {"supplier_id": rv["supplier_id"], "supplier_name": rv.get("supplier_name", ""),
                                              "partner_kind": rv.get("partner_kind", ""), "cycles": []})
        g["cycles"].append(cyc)
    out = []
    for g in by.values():
        done = [c for c in g["cycles"] if c["state"] != "open"]
        g["latest"] = done[-1] if done else None
        g["previous"] = list(reversed(done[:-1]))
        g["open"] = [c for c in g["cycles"] if c["state"] == "open"]
        g["eligible"] = bool(g["latest"]) and g["latest"]["state"] == "pass"
        out.append(g)
    return {"product_id": pid, "suppliers": out}


async def latest_for(pid: str, supplier_id: str) -> Optional[Dict[str, Any]]:
    if not (pid and supplier_id):
        return None
    s = await db[COLL].find_one({"product_id": pid, "purpose": "revalidation", "revalidation.supplier_id": supplier_id,
                                 "status": {"$in": ["decided", PENDING_PIC]}},
                                {"_id": 0, "id": 1, "number": 1, "status": 1, "decision": 1, "revalidation": 1},
                                sort=[("updated_at", -1)])
    if not s:
        return None
    st = _state(s)
    return {"sample_id": s["id"], "number": s.get("number"), "cycle_no": (s.get("revalidation") or {}).get("cycle_no"),
            "state": st, "state_label": STATE_LABEL[st], "design_version": (s.get("decision") or {}).get("design_version")}


async def pic_queue(entity_id: str) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"purpose": "revalidation", "status": PENDING_PIC}
    if entity_id:
        q["entity_id"] = entity_id
    return await db[COLL].find(q, {"_id": 0, "id": 1, "number": 1, "product_id": 1, "product_sku": 1, "product_name": 1,
                                   "sample_types": 1, "revalidation": 1, "decision": 1, "updated_at": 1}
                               ).sort("updated_at", -1).to_list(200)


async def lookup_partners(q: str = "") -> List[Dict[str, Any]]:
    """Daftar supplier + mitra makloon untuk dipilih sebagai pihak yang diuji ulang."""
    flt: Dict[str, Any] = {"status": {"$ne": "inactive"}}
    if q:
        flt["name"] = {"$regex": q, "$options": "i"}
    out: List[Dict[str, Any]] = []
    for coll, kind in (("suppliers", "supplier"), ("makloons", "makloon")):
        # PT internal grup (group_entity_id) bukan pemasok luar — tidak diuji ulang di sini.
        cf = {**flt, "group_entity_id": {"$in": [None, ""]}} if coll == "suppliers" else flt
        async for r in db[coll].find(cf, {"_id": 0, "id": 1, "name": 1, "code": 1}).sort("name", 1).limit(300):
            out.append({"id": r["id"], "name": r.get("name", ""), "code": r.get("code", ""), "partner_kind": kind})
    return out
