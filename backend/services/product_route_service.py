"""MP-T1 — Rute Produk: urutan langkah dari bahan sampai barang, per artikel per PT.

Keputusan pemilik 16 Nov 2026 (docs/blueprint/01_KEPUTUSAN.md bagian E):
  * K-65 — rute per artikel, pengecualian per varian; boleh lebih dari satu rute, satu utama; langkah memakai resep
    proses dan BOM yang sudah ada (dirujuk, tidak disalin).
  * K-57 — tahap asal/hasil langkah makloon dibaca dari Master Tahapan Proses (`master_registry`), bukan dari klien.
  * K-70 — rilis produk R&D wajib punya rute utama (`rnd.release_requires_route`).
  * K-71 — produk lama tanpa rute tetap berjalan; rute awal diusulkan dari sumber restock, resep proses, dan BOM.

Rute disimpan per PT (`entity_id`) karena mitra, kontrak, resep, dan BOM milik PT; artikel dipakai bersama semua PT.
Satu pembaca untuk semua pemakai: `effective_for_product` (rute utama yang berlaku untuk satu varian).
"""
from typing import Any, Dict, List, Optional, Tuple

import domain_registry as dr
from core_utils import new_id, now_iso
from db import db
from services import master_registry as mreg

COLL = "product_routes"
KINDS = ("purchase", "makloon", "inhouse")
KIND_LABEL = {"purchase": "Beli dari pemasok", "makloon": "Makloon", "inhouse": "Produksi sendiri"}
# Label pendek tahap untuk pesan galat (label registry terlalu panjang untuk kalimat).
STAGE_SHORT = {"yarn": "Benang", "grey": "Greige", "pfd": "PFD", "pfp": "PFP", "finished": "Jadi",
               "remnant": "Sisa", "byproduct": "Hasil samping"}
_VISIBLE = ("all", "", None)


class RouteError(ValueError):
    """Pesan siap tampil (Bahasa Indonesia) — router memetakan ke 400."""


def stage_short(value: Any) -> str:
    v = dr.normalize_stage(value) or str(value or "")
    return STAGE_SHORT.get(v, v or "-")


def _stage_of(doc: Optional[Dict[str, Any]], fallback: str = "") -> str:
    return dr.normalize_stage((doc or {}).get("stage")) or fallback


def _txt(v: Any, n: int = 300) -> str:
    return str(v or "").strip()[:n]


async def _product(pid: str) -> Optional[Dict[str, Any]]:
    if not pid:
        return None
    return await db.products.find_one({"id": pid}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "stage": 1,
                                                    "template_id": 1, "fabric_type": 1})


async def _partner(kind: str, pid: str, entity_id: str) -> Optional[Dict[str, Any]]:
    coll = db.makloons if kind == "makloon" else db.suppliers
    return await coll.find_one({"id": pid, "entity_id": {"$in": [entity_id, *_VISIBLE]}},
                               {"_id": 0, "id": 1, "name": 1, "process_types": 1, "status": 1, "is_active": 1})


def _plabel(prod: Optional[Dict[str, Any]]) -> str:
    if not prod:
        return ""
    return " · ".join(x for x in (prod.get("sku"), prod.get("name")) if x)


def _active(doc: Dict[str, Any]) -> bool:
    return doc.get("is_active") is not False and str(doc.get("status") or "active") not in ("inactive", "archived")


async def _makloon_stage(code: str, entity_id: str) -> Dict[str, Any]:
    meta = await mreg.stage_meta(code, entity_id)
    if not meta or meta.get("active") is False or str(meta.get("status") or "") == "inactive":
        return {}
    return meta if meta.get("kind") == "makloon" else {}


async def validate(template: Dict[str, Any], body: Dict[str, Any], entity_id: str) -> List[Dict[str, Any]]:
    """Aturan R1–R9 (unit MP-T1). Mengembalikan langkah yang sudah dinormalkan; galat → RouteError."""
    target_pid = _txt(body.get("product_id"), 80)
    target = None
    if target_pid:
        target = await _product(target_pid)
        if not target or target.get("template_id") != template["id"]:
            raise RouteError(f"Varian {(target or {}).get('sku') or target_pid} bukan bagian artikel "
                             f"{template.get('name') or template['id']}.")
    goal = _stage_of(target) or _stage_of(template, "finished")
    raw = body.get("steps") or []
    if not isinstance(raw, list) or not raw:
        raise RouteError("Rute butuh paling sedikit satu langkah.")
    out: List[Dict[str, Any]] = []
    prev_to = ""
    for i, s in enumerate(raw, start=1):
        s = s or {}
        kind = _txt(s.get("kind"), 20)
        if kind not in KINDS:
            raise RouteError(f"Langkah {i}: pilih jenis langkah (beli dari pemasok, makloon, atau produksi sendiri).")
        step = {"seq": i, "kind": kind, "stage_code": "", "stage_label": "", "process_type": "", "from_stage": "",
                "to_stage": "", "input_product_id": _txt(s.get("input_product_id"), 80),
                "output_product_id": _txt(s.get("output_product_id"), 80),
                "partner_kind": "", "partner_id": _txt(s.get("partner_id"), 80), "partner_name": "",
                "contract_id": _txt(s.get("contract_id"), 80), "contract_number": "",
                "recipe_id": _txt(s.get("recipe_id"), 80), "bom_id": _txt(s.get("bom_id"), 80),
                "note": _txt(s.get("note"))}
        out_prod = await _product(step["output_product_id"])
        if step["output_product_id"] and not out_prod:
            raise RouteError(f"Langkah {i}: barang hasil tidak ditemukan.")
        if kind == "purchase":                                              # R2
            if i != 1:
                raise RouteError(f"Langkah {i}: beli dari pemasok hanya boleh di langkah pertama.")
            step["partner_kind"] = "supplier"
            step["to_stage"] = _stage_of(out_prod) or (goal if len(raw) == 1 else "")
            if not step["to_stage"]:
                raise RouteError(f"Langkah {i}: pilih barang yang dibeli supaya tahapnya diketahui.")
            step["input_product_id"] = ""
        elif kind == "makloon":                                             # R3
            code = _txt(s.get("stage_code"), 40).lower()
            meta = await _makloon_stage(code, entity_id) if code else {}
            if not meta:
                raise RouteError(f"Langkah {i}: tahap '{code or '-'}' tidak ada atau tidak aktif di Master Tahapan "
                                 "Proses.")
            step.update({"stage_code": meta["value"], "stage_label": meta.get("label", ""),
                         "process_type": meta.get("process_type", "") or ""})
            if meta.get("changes_stage") is False:
                passthru = prev_to or dr.normalize_stage(meta.get("from_stage")) or ""
                step["from_stage"] = step["to_stage"] = passthru
            else:
                step["from_stage"] = dr.normalize_stage(meta.get("from_stage")) or ""
                step["to_stage"] = dr.normalize_stage(meta.get("to_stage")) or ""
            step["partner_kind"] = "makloon"
        else:                                                               # R9 — produksi sendiri
            bom = await db.mfg_boms.find_one({"id": step["bom_id"], "entity_id": entity_id}, {"_id": 0}) \
                if step["bom_id"] else None
            if not bom or str(bom.get("status") or "active") != "active":
                raise RouteError(f"Langkah {i}: pilih BOM produksi yang aktif.")
            bom_out = await _product(bom.get("output_product_id") or "")
            step["to_stage"] = _stage_of(bom_out) or goal
            step["from_stage"] = prev_to
            step["output_product_id"] = step["output_product_id"] or (bom_out or {}).get("id", "")
            step["partner_id"] = ""
        if prev_to and step["from_stage"] and step["from_stage"] != prev_to:  # R4
            raise RouteError(f"Langkah {i} ({step['stage_label'] or KIND_LABEL[kind]}) butuh bahan "
                             f"{stage_short(step['from_stage'])}, sedangkan langkah {i - 1} menghasilkan "
                             f"{stage_short(prev_to)}.")
        in_prod = await _product(step["input_product_id"])                  # R6
        if step["input_product_id"] and not in_prod:
            raise RouteError(f"Langkah {i}: bahan masuk tidak ditemukan.")
        if in_prod and step["from_stage"] and _stage_of(in_prod) != step["from_stage"]:
            raise RouteError(f"Langkah {i}: bahan masuk harus bertahap {stage_short(step['from_stage'])}; "
                             f"{in_prod.get('sku') or in_prod['id']} bertahap {stage_short(in_prod.get('stage'))}.")
        if out_prod and step["to_stage"] and _stage_of(out_prod) != step["to_stage"]:
            raise RouteError(f"Langkah {i}: hasil harus bertahap {stage_short(step['to_stage'])}; "
                             f"{out_prod.get('sku') or out_prod['id']} bertahap {stage_short(out_prod.get('stage'))}.")
        if step["partner_id"]:                                              # R7
            partner = await _partner(step["partner_kind"], step["partner_id"], entity_id)
            if not partner or not _active(partner):
                who = "Mitra makloon" if step["partner_kind"] == "makloon" else "Pemasok"
                raise RouteError(f"Langkah {i}: {who.lower()} tidak ditemukan atau tidak aktif di PT ini.")
            step["partner_name"] = partner.get("name", "")
            if kind == "makloon" and step["process_type"] and \
                    step["process_type"] not in (partner.get("process_types") or []):
                raise RouteError(f"Langkah {i}: {partner.get('name')} tidak mengerjakan "
                                 f"{dr.label_of('process_type', step['process_type']) or step['process_type']}.")
        if step["contract_id"]:                                             # R8
            want = "purchase" if kind == "purchase" else "makloon"
            k = await db.supplier_contracts.find_one({"id": step["contract_id"], "entity_id": entity_id}, {"_id": 0})
            ok = bool(k) and k.get("status") == "active" and k.get("contract_type") == want \
                and (not step["partner_id"] or k.get("partner_id") == step["partner_id"]) \
                and (kind != "makloon" or not k.get("process_type") or k.get("process_type") == step["process_type"])
            if not ok:
                jenis = "pembelian" if want == "purchase" else "makloon"
                raise RouteError(f"Langkah {i}: kontrak {(k or {}).get('contract_number') or step['contract_id']} "
                                 f"bukan kontrak {jenis} aktif milik {step['partner_name'] or 'mitra langkah ini'}.")
            step["contract_number"] = k.get("contract_number", "")
            if not step["partner_id"]:
                step["partner_id"] = k.get("partner_id", "")
        if step["recipe_id"] and not await db.process_recipes.find_one({"id": step["recipe_id"],
                                                                         "entity_id": entity_id}, {"_id": 1}):
            raise RouteError(f"Langkah {i}: resep proses tidak ditemukan di PT ini.")
        step["input_product_label"] = _plabel(in_prod)
        step["output_product_label"] = _plabel(out_prod)
        prev_to = step["to_stage"] or prev_to
        out.append(step)
    if prev_to != goal:                                                     # R5
        raise RouteError(f"Rute berakhir di {stage_short(prev_to)}, padahal "
                         f"{'varian' if target else 'artikel'} ini {stage_short(goal)}.")
    return out


def _scope_key(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {"entity_id": doc["entity_id"], "template_id": doc["template_id"], "product_id": doc.get("product_id", ""),
            "status": "active"}


async def _template(template_id: str) -> Dict[str, Any]:
    tpl = await db.product_templates.find_one({"id": template_id}, {"_id": 0, "id": 1, "name": 1, "stage": 1,
                                                                    "fabric_type": 1})
    if not tpl:
        raise LookupError("Artikel tidak ditemukan")
    return tpl


async def _make_primary(doc: Dict[str, Any]) -> None:
    await db[COLL].update_many({**_scope_key(doc), "id": {"$ne": doc["id"]}, "is_primary": True},
                               {"$set": {"is_primary": False, "updated_at": now_iso()}})


async def create(template_id: str, body: Dict[str, Any], actor: Dict[str, Any], entity_id: str, *,
                 origin: str = "manual", origin_ref: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    tpl = await _template(template_id)
    name = _txt(body.get("name"), 80)
    if not name:
        raise RouteError("Isi nama rute.")
    steps = await validate(tpl, body, entity_id)
    who = (actor or {}).get("name", "")
    doc = {"id": new_id("rte"), "entity_id": entity_id, "template_id": template_id,
           "product_id": _txt(body.get("product_id"), 80), "name": name, "is_primary": False, "status": "active",
           "origin": origin, "origin_ref": origin_ref or {}, "steps": steps,
           "created_by": who, "created_at": now_iso(), "updated_by": who, "updated_at": now_iso(),
           "history": [{"at": now_iso(), "by": who, "action": "dibuat", "note": ""}]}
    first = not await db[COLL].find_one(_scope_key(doc), {"_id": 1})
    doc["is_primary"] = bool(body.get("is_primary")) or first                # R10
    await db[COLL].insert_one(dict(doc))
    if doc["is_primary"]:
        await _make_primary(doc)
    return await get(doc["id"])


async def get(route_id: str, entity_id: str = "") -> Optional[Dict[str, Any]]:
    q: Dict[str, Any] = {"id": route_id}
    if entity_id:
        q["entity_id"] = entity_id
    return await db[COLL].find_one(q, {"_id": 0})


async def update(route_id: str, body: Dict[str, Any], actor: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    cur = await get(route_id, entity_id)
    if not cur:
        raise LookupError("Rute tidak ditemukan")
    patch: Dict[str, Any] = {}
    if "name" in body:
        patch["name"] = _txt(body.get("name"), 80)
        if not patch["name"]:
            raise RouteError("Isi nama rute.")
    if "steps" in body:
        tpl = await _template(cur["template_id"])
        patch["steps"] = await validate(tpl, {"product_id": cur.get("product_id", ""), "steps": body["steps"]},
                                        entity_id)
    if "status" in body:
        st = _txt(body.get("status"), 20)
        if st not in ("active", "inactive"):
            raise RouteError("Status rute: aktif atau nonaktif.")
        patch["status"] = st
        if st == "inactive":
            patch["is_primary"] = False
    if not patch:
        return cur
    who = (actor or {}).get("name", "")
    patch.update({"updated_by": who, "updated_at": now_iso()})
    note = ", ".join(k for k in ("name", "steps", "status") if k in patch)
    await db[COLL].update_one({"id": route_id}, {"$set": patch, "$push": {"history": {
        "$each": [{"at": now_iso(), "by": who, "action": "diubah", "note": note}], "$slice": -30}}})
    return await get(route_id)


async def set_primary(route_id: str, actor: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    cur = await get(route_id, entity_id)
    if not cur:
        raise LookupError("Rute tidak ditemukan")
    if cur.get("status") != "active":
        raise RouteError("Rute nonaktif tidak bisa dijadikan utama.")
    who = (actor or {}).get("name", "")
    await db[COLL].update_one({"id": route_id}, {"$set": {"is_primary": True, "updated_by": who,
                                                          "updated_at": now_iso()},
                                                 "$push": {"history": {"$each": [{"at": now_iso(), "by": who,
                                                                                  "action": "dijadikan utama",
                                                                                  "note": ""}], "$slice": -30}}})
    await _make_primary(cur)
    return await get(route_id)


async def list_for_template(template_id: str, entity_id: str) -> Dict[str, Any]:
    await _template(template_id)
    rows = await db[COLL].find({"template_id": template_id, "entity_id": entity_id, "status": "active"},
                               {"_id": 0}).sort("created_at", 1).to_list(200)
    primary = next((r["id"] for r in rows if r.get("is_primary") and not r.get("product_id")), "")
    return {"items": rows, "primary_id": primary, "status": "diatur" if primary else "belum_diatur"}


async def effective_for_product(product: Dict[str, Any], entity_id: str) -> Optional[Dict[str, Any]]:
    """Rute utama yang berlaku untuk satu varian: pengecualian varian dulu, lalu rute artikel."""
    if not product or not product.get("template_id") or not entity_id:
        return None
    base = {"entity_id": entity_id, "template_id": product["template_id"], "status": "active", "is_primary": True}
    own = await db[COLL].find_one({**base, "product_id": product.get("id", "")}, {"_id": 0})
    return own or await db[COLL].find_one({**base, "product_id": ""}, {"_id": 0})


def route_mode(route: Optional[Dict[str, Any]]) -> str:
    """Jalur pengadaan dari satu rute: `makloon` bila ada langkah makloon, `purchase` bila beli saja, `inhouse`."""
    kinds = {s.get("kind") for s in (route or {}).get("steps") or []}
    if "makloon" in kinds:
        return "makloon"
    if "inhouse" in kinds:
        return "inhouse"
    return "purchase" if kinds else ""


async def modes_for_product(product: Dict[str, Any], entity_id: str) -> Tuple[str, List[str]]:
    """(jalur rute utama, semua jalur rute aktif) untuk satu varian — dipakai cek jalur pengadaan (MP-T1 (b))."""
    eff = await effective_for_product(product, entity_id)
    if not eff:
        return "", []
    rows = await db[COLL].find({"entity_id": entity_id, "template_id": product["template_id"], "status": "active",
                                "product_id": {"$in": ["", product.get("id", "")]}},
                               {"_id": 0, "steps.kind": 1}).to_list(200)
    return route_mode(eff), sorted({route_mode(r) for r in rows} - {""})


async def step_options(entity_id: str, from_stage: str = "") -> Dict[str, Any]:
    """Tahap makloon yang boleh sesudah `from_stage` (kosong = semua) + mitra aktif yang mengerjakan prosesnya."""
    fs = dr.normalize_stage(from_stage) or ""
    makloons = await db.makloons.find({"entity_id": {"$in": [entity_id, *_VISIBLE]}},
                                      {"_id": 0, "id": 1, "name": 1, "process_types": 1, "status": 1,
                                       "is_active": 1}).sort("name", 1).to_list(500)
    out = []
    for r in await mreg.active_stages(entity_id):
        meta = await mreg.stage_meta(r.get("value") or "", entity_id)
        if meta.get("kind") != "makloon":
            continue
        src = dr.normalize_stage(meta.get("from_stage")) or ""
        passthru = meta.get("changes_stage") is False
        if fs and src != fs and not (passthru and not src):
            continue
        pt = meta.get("process_type") or ""
        out.append({"stage_code": meta["value"], "label": meta.get("label", ""), "process_type": pt,
                    "from_stage": fs if passthru else src,
                    "to_stage": (fs or src) if passthru else (dr.normalize_stage(meta.get("to_stage")) or ""),
                    "partners": [{"id": m["id"], "name": m.get("name", "")} for m in makloons
                                 if _active(m) and pt in (m.get("process_types") or [])]})
    out.sort(key=lambda o: o["stage_code"])
    # Daftar pendukung pop-up rute (tanpa nominal tarif): pemasok, kontrak aktif, BOM aktif PT ini — supaya pengelola
    # rute tidak butuh izin modul pembelian/produksi hanya untuk memilih.
    sups = await db.suppliers.find({"entity_id": {"$in": [entity_id, *_VISIBLE]}},
                                   {"_id": 0, "id": 1, "name": 1, "status": 1, "is_active": 1}).sort("name", 1) \
        .to_list(1000)
    ctrs = await db.supplier_contracts.find({"entity_id": entity_id, "status": "active",
                                             "contract_type": {"$in": ["purchase", "makloon"]}},
                                            {"_id": 0, "id": 1, "contract_number": 1, "contract_type": 1,
                                             "partner_id": 1, "process_type": 1, "title": 1}).to_list(1000)
    boms = await db.mfg_boms.find({"entity_id": entity_id, "status": "active"},
                                  {"_id": 0, "id": 1, "code": 1, "name": 1, "output_product_id": 1}).to_list(500)
    return {"from_stage": fs, "stages": out,
            "stage_labels": {k: v for k, v in STAGE_SHORT.items()},
            "suppliers": [{"id": s["id"], "name": s.get("name", "")} for s in sups if _active(s)],
            "contracts": ctrs, "boms": boms}


# ── Rute awal dari data lama (K-71) ────────────────────────────────────────────

async def suggest(template_id: str, entity_id: str) -> List[Dict[str, Any]]:
    """Usulan rute (tidak disimpan) dari resep proses berantai, BOM aktif, dan sumber restock 'supplier'."""
    tpl = await db.product_templates.find_one({"id": template_id}, {"_id": 0, "id": 1, "name": 1, "restock_source": 1})
    if not tpl:
        return []
    variants = await db.products.find({"template_id": template_id}, {"_id": 0, "id": 1}).to_list(500)
    vids = [v["id"] for v in variants]
    out: List[Dict[str, Any]] = []
    stages = {(m.get("process_type"), m.get("target_use") or ""): m.get("value")
              for m in [await mreg.stage_meta(r.get("value") or "", entity_id)
                        for r in await mreg.active_stages(entity_id)] if m.get("kind") == "makloon"}
    recipes = await db.process_recipes.find({"entity_id": entity_id, "status": {"$ne": "inactive"}},
                                            {"_id": 0}).to_list(2000)
    by_out = {}
    for rc in recipes:
        by_out.setdefault(rc.get("output_product_id") or "", rc)
    for vid in vids:
        if vid not in by_out:
            continue
        chain, cur, seen = [], by_out[vid], set()
        while cur and cur["id"] not in seen and len(chain) < 8:
            seen.add(cur["id"])
            chain.insert(0, cur)
            cur = by_out.get(cur.get("input_product_id") or "")
        steps = []
        for rc in chain:
            tu = "print" if rc.get("output_stage") == "pfp" else ("dye" if rc.get("output_stage") == "pfd" else "")
            code = stages.get((rc.get("process_type"), tu)) or stages.get((rc.get("process_type"), ""))
            if not code:
                steps = []
                break
            steps.append({"kind": "makloon", "stage_code": code, "input_product_id": rc.get("input_product_id", ""),
                          "output_product_id": rc.get("output_product_id", "") if rc is not chain[-1] else "",
                          "partner_id": rc.get("default_makloon_id", ""), "recipe_id": rc["id"]})
        if steps:
            for st in steps:
                st["input_product_label"] = _plabel(await _product(st["input_product_id"]))
                st["output_product_label"] = _plabel(await _product(st["output_product_id"]))
            out.append({"name": f"Makloon ({' → '.join(s['stage_code'] for s in steps)})", "steps": steps,
                        "origin_ref": {"kind": "resep", "id": chain[-1]["id"], "number": chain[-1].get("name", "")}})
            break
    bom = await db.mfg_boms.find_one({"entity_id": entity_id, "status": "active", "output_product_id": {"$in": vids}},
                                     {"_id": 0}) if vids else None
    if bom:
        out.append({"name": "Produksi sendiri", "steps": [{"kind": "inhouse", "bom_id": bom["id"]}],
                    "origin_ref": {"kind": "bom", "id": bom["id"], "number": bom.get("code") or bom.get("name", "")}})
    if (tpl.get("restock_source") or {}).get("mode") in ("supplier", "both"):
        sups = sorted({r.get("supplier_id") for r in await db.supplier_items.find(
            {"product_id": {"$in": vids}, "entity_id": entity_id}, {"_id": 0, "supplier_id": 1}).to_list(200)
            if r.get("supplier_id")}) if vids else []
        out.append({"name": "Beli dari pemasok", "steps": [{"kind": "purchase",
                                                            "partner_id": sups[0] if len(sups) == 1 else ""}],
                    "origin_ref": {"kind": "sumber_restock", "id": template_id, "number": ""}})
    return out


async def ensure_rnd_purchase_route(product_id: str, supplier_id: str, contract_id: str, entity_id: str,
                                    actor_name: str, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Putusan R&D (pemenang pemasok) → rute "Beli dari <pemasok>" bila artikel belum punya rute di PT itu."""
    prod = await db.products.find_one({"id": product_id}, {"_id": 0, "id": 1, "template_id": 1})
    if not prod or not prod.get("template_id") or not entity_id:
        return None
    if await db[COLL].find_one({"entity_id": entity_id, "template_id": prod["template_id"], "status": "active"},
                               {"_id": 1}):
        return None
    sup = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0, "name": 1}) or {}
    body = {"name": f"Beli dari {sup.get('name') or 'pemasok pemenang'}",
            "steps": [{"kind": "purchase", "partner_id": supplier_id, "contract_id": contract_id,
                       "output_product_id": product_id}]}
    try:
        return await create(prod["template_id"], body, {"name": actor_name}, entity_id, origin="rnd",
                            origin_ref={"kind": "sample", "id": sample.get("id", ""),
                                        "number": sample.get("number", "")})
    except RouteError:
        # Kontrak/pemasok tidak lolos aturan rute → tetap buat rute tanpa kontrak; kontrak diisi MD belakangan.
        body["steps"][0].pop("contract_id", None)
        return await create(prod["template_id"], body, {"name": actor_name}, entity_id, origin="rnd",
                            origin_ref={"kind": "sample", "id": sample.get("id", ""),
                                        "number": sample.get("number", "")})


# ── MP-T2 — rencana SPK makloon dari rute utama ────────────────────────────────

async def _step_factor(step: Dict[str, Any], explain: List[str]) -> float:
    """Faktor hasil per bahan satu langkah: resep (yield × (1 − susut)) > susut kontrak > 1 (dicatat di `explain`)."""
    if step.get("recipe_id"):
        rc = await db.process_recipes.find_one({"id": step["recipe_id"]}, {"_id": 0}) or {}
        y = float(rc.get("yield_factor") or 1.0) or 1.0
        w = float(rc.get("waste_pct") or 0.0)
        f = y * (1 - w / 100.0)
        explain.append(f"Langkah {step['seq']}: resep '{rc.get('name', '')}' yield {y:g} × susut {w:g}% → {f:.4f}")
        return f if f > 0 else 1.0
    if step.get("contract_id"):
        k = await db.supplier_contracts.find_one({"id": step["contract_id"]}, {"_id": 0, "shrinkage_pct": 1,
                                                                               "contract_number": 1}) or {}
        w = float(k.get("shrinkage_pct") or 0.0)
        if w > 0:
            explain.append(f"Langkah {step['seq']}: susut kontrak {k.get('contract_number', '')} {w:g}%")
            return 1 - w / 100.0
    explain.append(f"Langkah {step['seq']}: tanpa resep/susut kontrak → bahan = hasil (faktor 1)")
    return 1.0


async def plan_makloon(product_id: str, qty: float, entity_id: str) -> Dict[str, Any]:
    """Payload SPK makloon (bentuk `POST /makloon-orders`) dari rute utama varian; qty bahan dihitung mundur dari hasil."""
    import math
    prod = await db.products.find_one({"id": product_id}, {"_id": 0}) or {}
    base = {"ready": False, "source": "rute", "output_product_id": product_id, "target_output_qty": qty,
            "explain": []}
    if not prod:
        return {**base, "reason": "Produk tidak ditemukan."}
    route = await effective_for_product(prod, entity_id)
    if not route:
        return {**base, "reason": f"{prod.get('sku') or prod.get('name')} belum punya rute utama di PT ini. "
                                  "Atur di Master Produk › Rute."}
    base["route"] = {"id": route["id"], "name": route["name"]}
    mode = route_mode(route)
    if mode != "makloon":
        why = "beli dari pemasok — buat PO" if mode == "purchase" else "produksi sendiri — buat perintah kerja"
        return {**base, "reason": f"Rute utama {prod.get('sku')} adalah {why}, bukan SPK makloon."}
    steps = [dict(s) for s in route.get("steps") or []]
    buy = steps[0] if steps and steps[0].get("kind") == "purchase" else None
    mk_steps = [s for s in steps if s.get("kind") == "makloon"]
    material_pid = (buy or {}).get("output_product_id") or (mk_steps[0].get("input_product_id") if mk_steps else "")
    if not material_pid:
        return {**base, "reason": "Rute belum menyebut bahan masuk langkah pertama. Lengkapi di Master Produk › Rute."}
    explain: List[str] = [f"Rute utama '{route['name']}' ({len(mk_steps)} langkah makloon)"]
    out_steps: List[Dict[str, Any]] = []
    prev_out = material_pid
    for n, s in enumerate(mk_steps, start=1):
        last = n == len(mk_steps)
        passthru = s.get("from_stage") == s.get("to_stage")
        out_pid = product_id if last else (s.get("output_product_id") or (prev_out if passthru else ""))
        if not out_pid:
            return {**base, "explain": explain,
                    "reason": f"Rute belum menyebut hasil langkah {s['seq']} ({s.get('stage_label') or s.get('stage_code')})."
                              " Lengkapi di Master Produk › Rute."}
        out_snap = await _product(out_pid) or {}
        out_steps.append({"stage_code": s.get("stage_code", ""), "process_type": s.get("process_type", ""),
                          "makloon_id": s.get("partner_id", ""), "makloon_name": s.get("partner_name", ""),
                          "contract_id": s.get("contract_id", ""), "recipe_id": s.get("recipe_id", ""),
                          "input_product_id": prev_out, "output_product_id": out_pid,
                          "output_name": out_snap.get("name", ""),
                          "output_unit": (await db.products.find_one({"id": out_pid}, {"_id": 0, "base_unit": 1})
                                          or {}).get("base_unit", ""),
                          "seq": s["seq"]})
        prev_out = out_pid
    need = float(qty or 0)
    for st in reversed(out_steps):
        need = need / await _step_factor(st, explain)
    material_qty = round(math.ceil(round(need * 100, 6)) / 100, 2)
    explain.append(f"Bahan dibutuhkan ≈ {material_qty:g} untuk hasil {float(qty or 0):g}")
    mat = await db.products.find_one({"id": material_pid}, {"_id": 0, "sku": 1, "name": 1, "base_unit": 1,
                                                             "stage": 1}) or {}
    for st in out_steps:
        st.pop("seq", None)
    payload = {"mode": "buy_process" if buy else "process_only", "material_product_id": material_pid,
               "material_sku": mat.get("sku", ""), "material_name": mat.get("name", ""),
               "material_unit": mat.get("base_unit", ""), "material_stage": _stage_of(mat), "material_qty": material_qty,
               "supplier_id": (buy or {}).get("partner_id", ""), "route_id": route["id"], "steps": out_steps}
    return {**base, "ready": True, "explain": explain, "payload": payload}


async def ensure_rnd_makloon_route(product_id: str, partner_id: str, contract_id: str, process_type: str,
                                   entity_id: str, actor_name: str, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """MP-T3 — putusan R&D (pemenang mitra makloon) → rute "<tahap> di <mitra>" bila artikel belum punya rute di PT itu.
    Bahan masuk = varian kain dasar spesifikasi yang bertahap asal tahap itu (bila ada). Aturan rute tetap berlaku: bila
    kontrak/bahan tidak lolos, rute dibuat tanpa bagian itu; bila tahapnya tidak berakhir di tahap produk, tidak dibuat."""
    prod = await db.products.find_one({"id": product_id}, {"_id": 0, "id": 1, "template_id": 1, "stage": 1,
                                                           "base_fabric_template_id": 1})
    if not prod or not prod.get("template_id") or not entity_id or not process_type:
        return None
    if await db[COLL].find_one({"entity_id": entity_id, "template_id": prod["template_id"], "status": "active"},
                               {"_id": 1}):
        return None
    goal = _stage_of(prod, "finished")
    tu = "print" if goal == "pfp" else ("dye" if goal == "pfd" else "")
    meta = await mreg.stage_by_process_type(process_type, entity_id, tu)
    if not meta or meta.get("kind") != "makloon":
        return None
    src = dr.normalize_stage(meta.get("from_stage")) or ""
    input_pid = ""
    if prod.get("base_fabric_template_id") and src:
        base = await db.products.find_one({"template_id": prod["base_fabric_template_id"], "stage": src,
                                           "status": {"$ne": "archived"}}, {"_id": 0, "id": 1})
        input_pid = (base or {}).get("id", "")
    mk = await db.makloons.find_one({"id": partner_id}, {"_id": 0, "name": 1}) or {}
    step = {"kind": "makloon", "stage_code": meta["value"], "partner_id": partner_id, "contract_id": contract_id,
            "input_product_id": input_pid}
    ref = {"kind": "sample", "id": sample.get("id", ""), "number": sample.get("number", "")}
    name = f"{meta.get('label') or meta['value']} di {mk.get('name') or 'mitra pemenang'}"
    for drop in ((), ("contract_id",), ("contract_id", "input_product_id")):
        body = {"name": name, "steps": [{k: v for k, v in step.items() if k not in drop}]}
        try:
            return await create(prod["template_id"], body, {"name": actor_name}, entity_id, origin="rnd",
                                origin_ref=ref)
        except RouteError:
            continue
    return None
