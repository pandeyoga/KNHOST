"""FASE R0 — Profil gudang: site (lokasi), peran gedung, rules penyimpanan, gate config.

`warehouses` = GEDUNG (koleksi existing, SSOT stok tidak berubah).
`warehouse_sites` = lokasi fisik (Rancamalang, Soreang, Jakarta) — koleksi kecil SHARED.
Semua configurable oleh user (keputusan pemilik: fungsionalitas gudang bisa berubah).

PREP-C (keputusan pemilik 8 Nov 2026, K-GDG-01…08 + K-RFID-04) — data lokasi & gedung belum tervalidasi, jadi
semuanya DIATUR di profil, tidak ditanam di kode:
* `gate_config` — punya gate atau tidak (`has_gate`; `physical_gate` lama dibaca & dicerminkan), mode konfirmasi gerak
  `gate`/`handheld` (tanpa gate = handheld), pasangan gate IN/OUT (perangkat dari `rfid_devices`), tata letak pasangan
  `terpisah`/`berdampingan_sekat`/`berdampingan` + catatan clear zone. Dibaca lewat `warehouse_gate_policy()`.
* peran `inspection` (tempat inspeksi, kini Gedung Retur RCM — K-GDG-04) dan `material` (gedung bahan — K-GDG-06).
* `stock_mode` `roll_tagged` | `quantity` (K-GDG-06) — mode kuantitas hanya disimpan & ditandai "gate tidak berlaku".
* `storage_form` `rack` | `floor` per gedung (dan per zona di struktur — K-GDG-05); arti & kapasitas bin tetap.
* `storage_rules` + `template_ids` (artikel) & `owner_entity_ids` (PT pemilik) — AND seperti aturan lain (K-GDG-08).
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, safe_doc

VALID_ROLES = {"transit", "storage", "return", "staging", "central_inbound", "inspection", "material"}
VALID_RULE_MODES = {"none", "category", "grade", "combined"}
ROLE_LABEL = {
    "transit": "Transit", "storage": "Penyimpanan", "return": "Retur",
    "staging": "Staging", "central_inbound": "Penerimaan Pusat",
    "inspection": "Inspeksi", "material": "Gudang Bahan",
}
#: Gedung tempat roll DISIMPAN (tujuan putaway). `material` = gudang bahan (greige, benang, …).
STORAGE_ROLES = {"storage", "material"}
#: Gedung tujuan barang yang DIMINTA inspeksi (K-GDG-04).
INSPECTION_ROLE = "inspection"
#: Area QC barang retur (layar perjalanan retur) — `return` lama tetap dianggap area QC.
QC_AREA_ROLES = {"inspection", "return"}
STOCK_MODES = ("roll_tagged", "quantity")
STOCK_MODE_LABEL = {"roll_tagged": "Per roll bertag", "quantity": "Kuantitas tanpa tag"}
STORAGE_FORMS = ("rack", "floor")
STORAGE_FORM_LABEL = {"rack": "Rak bertingkat", "floor": "Petak lantai (tumpukan stacker)"}
CONFIRM_MODES = ("gate", "handheld")
GATE_LAYOUTS = ("terpisah", "berdampingan_sekat", "berdampingan")
GATE_LAYOUT_LABEL = {"terpisah": "Pintu IN/OUT berjauhan", "berdampingan_sekat": "Berdampingan dengan sekat",
                     "berdampingan": "Berdampingan tanpa sekat"}
MAX_GATE_PAIRS = 8
MAX_NOTE = 300


def _ids(values: Any) -> List[str]:
    return list(dict.fromkeys(str(v).strip() for v in (values or []) if str(v or "").strip()))


def normalize_rules(rules: Optional[Dict[str, Any]], *, with_mode: bool = True) -> Dict[str, Any]:
    """Aturan penyimpanan gudang/zona: daftar terisi berlaku AND (DEV-G02); `template_ids` = artikel
    (`product_templates`), `owner_entity_ids` = PT pemilik roll (K-GDG-08)."""
    rules = rules or {}
    out: Dict[str, Any] = {
        "categories": [str(c).strip() for c in (rules.get("categories") or []) if str(c).strip()],
        "grades": [str(g).strip().upper() for g in (rules.get("grades") or []) if str(g).strip()],
        "fabric_types": [str(f).strip().lower() for f in (rules.get("fabric_types") or []) if str(f).strip()],
        "template_ids": _ids(rules.get("template_ids")),
        "owner_entity_ids": _ids(rules.get("owner_entity_ids")),
    }
    if with_mode:
        mode = str(rules.get("mode") or "none").strip().lower()
        if mode not in VALID_RULE_MODES:
            raise HTTPException(status_code=400, detail=f"Mode rules tidak valid: {mode}")
        out = {"mode": mode, **out}
    return out


def normalize_gate_config(gc: Optional[Dict[str, Any]], *, strict: bool = False) -> Dict[str, Any]:
    """Bentuk baku `gate_config`. Data lama `{physical_gate}` dibaca sebagai `has_gate`; `physical_gate` tetap
    ditulis (cermin) supaya pembaca lama tidak berubah arti. `strict` = validasi masukan PATCH (400 berkalimat)."""
    gc = dict(gc or {})
    has_gate = bool(gc["has_gate"] if "has_gate" in gc else gc.get("physical_gate", False))
    mode = str(gc.get("confirm_mode") or ("gate" if has_gate else "handheld")).strip().lower()
    if mode not in CONFIRM_MODES:
        if strict:
            raise HTTPException(status_code=400, detail="Mode konfirmasi gerak harus 'gate' atau 'handheld'.")
        mode = "gate" if has_gate else "handheld"
    if not has_gate and mode == "gate":
        if strict:
            raise HTTPException(status_code=400, detail=(
                "Gedung tanpa gate hanya bisa memakai handheld — nyalakan 'Punya gate' dulu bila ingin mode gate."))
        mode = "handheld"
    raw_pairs = gc.get("pairs") or []
    if strict and len(raw_pairs) > MAX_GATE_PAIRS:
        raise HTTPException(status_code=400, detail=f"Maksimal {MAX_GATE_PAIRS} pasangan gate per gedung.")
    pairs, seen = [], set()
    for i, p in enumerate(raw_pairs[:MAX_GATE_PAIRS]):
        p = dict(p or {})
        layout = str(p.get("layout") or "").strip().lower()
        if layout and layout not in GATE_LAYOUTS:
            if strict:
                raise HTTPException(status_code=400, detail=(
                    "Tata letak pasangan gate harus 'terpisah', 'berdampingan_sekat', atau 'berdampingan'."))
            layout = ""
        dev_in, dev_out = str(p.get("in_device_id") or "").strip(), str(p.get("out_device_id") or "").strip()
        for d in (dev_in, dev_out):
            if d and d in seen and strict:
                raise HTTPException(status_code=400, detail="Satu perangkat gate hanya boleh dipakai di satu posisi.")
            if d:
                seen.add(d)
        note = str(p.get("clear_zone_note") or "").strip()
        if strict and len(note) > MAX_NOTE:
            raise HTTPException(status_code=400, detail=f"Catatan clear zone maksimal {MAX_NOTE} huruf.")
        pairs.append({"id": str(p.get("id") or "").strip() or new_id("gpair"),
                      "name": str(p.get("name") or "").strip()[:80] or f"Gate {i + 1}",
                      "in_device_id": dev_in, "out_device_id": dev_out, "layout": layout,
                      "clear_zone_note": note[:MAX_NOTE]})
    return {"has_gate": has_gate, "physical_gate": has_gate, "confirm_mode": mode, "pairs": pairs}


def _choice(data: Dict[str, Any], key: str, allowed: tuple, label: str) -> str:
    v = str(data.get(key) or "").strip().lower() or allowed[0]
    if v not in allowed:
        raise HTTPException(status_code=400, detail=f"{label} harus salah satu: {', '.join(allowed)}.")
    return v


def validate_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validasi + normalisasi field profil (roles, storage_rules, gate_config, site_id, stock_mode, storage_form)."""
    out: Dict[str, Any] = {}
    if "roles" in data:
        roles = [str(r).strip().lower() for r in (data.get("roles") or [])]
        bad = [r for r in roles if r not in VALID_ROLES]
        if bad:
            raise HTTPException(status_code=400, detail=f"Peran gudang tidak valid: {', '.join(bad)}")
        out["roles"] = sorted(set(roles))
    if "storage_rules" in data:
        out["storage_rules"] = normalize_rules(data.get("storage_rules"))
    if "gate_config" in data:
        out["gate_config"] = normalize_gate_config(data.get("gate_config"), strict=True)
    if "site_id" in data:
        out["site_id"] = data.get("site_id") or ""
    if "stock_mode" in data:
        out["stock_mode"] = _choice(data, "stock_mode", STOCK_MODES, "Mode pencatatan stok")
    if "storage_form" in data:
        out["storage_form"] = _choice(data, "storage_form", STORAGE_FORMS, "Bentuk penyimpanan")
    return out


def validate_zone_forms(zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """K-GDG-05 — `storage_form` per zona: kosong = ikut gedung, `rack` | `floor`. Aturan node (artikel/PT)
    dinormalisasi sama dengan aturan gedung. Struktur lain tidak disentuh."""
    for z in zones or []:
        form = str(z.get("storage_form") or "").strip().lower()
        if form and form not in STORAGE_FORMS:
            raise HTTPException(status_code=400, detail=(
                f"Bentuk penyimpanan zona '{z.get('name') or ''}' harus 'rack' (rak) atau 'floor' (petak lantai)."))
        z["storage_form"] = form
        stack: List[Dict[str, Any]] = [z]
        while stack:
            node = stack.pop()
            if node.get("rules"):
                node["rules"] = {**node["rules"], **normalize_rules(node["rules"], with_mode=False)}
            for key in ("racks", "levels", "bins"):
                stack.extend(n for n in node.get(key) or [] if isinstance(n, dict))
    return zones


async def assert_profile_refs(warehouse_id: str, prof: Dict[str, Any]) -> None:
    """Rujukan profil harus nyata: perangkat gate milik gedung ini & arahnya cocok; artikel & PT pada aturan ada."""
    gc = prof.get("gate_config")
    if gc:
        wanted = [(p["in_device_id"], "in", p["name"]) for p in gc["pairs"] if p["in_device_id"]] + \
                 [(p["out_device_id"], "out", p["name"]) for p in gc["pairs"] if p["out_device_id"]]
        devs = {d["id"]: d for d in await db.rfid_devices.find(
            {"id": {"$in": [w[0] for w in wanted]}},
            {"_id": 0, "id": 1, "code": 1, "type": 1, "direction": 1, "warehouse_id": 1}).to_list(len(wanted) + 1)}
        for did, direction, pair in wanted:
            d = devs.get(did)
            if not d:
                raise HTTPException(status_code=400, detail=f"{pair}: perangkat gate tidak ditemukan — muat ulang daftar perangkat.")
            if d.get("type") != "gate":
                raise HTTPException(status_code=400, detail=f"{pair}: perangkat {d.get('code')} bukan reader gate.")
            if d.get("warehouse_id") != warehouse_id:
                raise HTTPException(status_code=400, detail=f"{pair}: perangkat {d.get('code')} terdaftar di gedung lain.")
            if d.get("direction") in ("in", "out") and d["direction"] != direction:
                raise HTTPException(status_code=400, detail=(
                    f"{pair}: perangkat {d.get('code')} berarah {d['direction'].upper()}, bukan {direction.upper()}."))
    rules = prof.get("storage_rules") or {}
    if rules.get("template_ids"):
        found = await db.product_templates.count_documents({"id": {"$in": rules["template_ids"]}})
        if found != len(rules["template_ids"]):
            raise HTTPException(status_code=400, detail="Sebagian artikel pada aturan gudang tidak ditemukan.")
    if rules.get("owner_entity_ids"):
        found = await db.business_entities.count_documents({"id": {"$in": rules["owner_entity_ids"]}})
        if found != len(rules["owner_entity_ids"]):
            raise HTTPException(status_code=400, detail="Sebagian PT pemilik pada aturan gudang tidak ditemukan.")


def gate_policy_of(wh: Dict[str, Any]) -> Dict[str, Any]:
    """Kebijakan konfirmasi gerak satu gedung (tanpa I/O). `effective_mode`: `gate` (lintasan gate mencatat gerak),
    `handheld` (scan genggam — juga cadangan gate), `manual` (gedung mode kuantitas: gate/tag tidak berlaku)."""
    gc = normalize_gate_config(wh.get("gate_config"))
    stock_mode = wh.get("stock_mode") if wh.get("stock_mode") in STOCK_MODES else "roll_tagged"
    gate_applies = stock_mode == "roll_tagged"
    ins = [p["in_device_id"] for p in gc["pairs"] if p["in_device_id"]]
    outs = [p["out_device_id"] for p in gc["pairs"] if p["out_device_id"]]
    use_gate = gate_applies and gc["has_gate"] and gc["confirm_mode"] == "gate"
    notes = []
    if not gate_applies:
        notes.append("Mode kuantitas tanpa tag — gate & handheld RFID tidak berlaku di gedung ini.")
    elif use_gate and not ins:
        notes.append("Mode gate tetapi belum ada perangkat gate IN tertaut — konfirmasi tiba memakai handheld dulu.")
    if any(p["layout"] in ("berdampingan", "berdampingan_sekat") for p in gc["pairs"]):
        notes.append("Ada pasangan IN/OUT berdampingan — butuh aturan penengah (K-RFID-04); efek sekat wajib diuji.")
    return {"warehouse_id": wh.get("id", ""), "warehouse_name": wh.get("name", ""), "stock_mode": stock_mode,
            "gate_applies": gate_applies, "has_gate": gc["has_gate"], "confirm_mode": gc["confirm_mode"],
            "effective_mode": "gate" if use_gate else ("handheld" if gate_applies else "manual"),
            "handheld_fallback": gate_applies, "device_ids_in": ins, "device_ids_out": outs,
            "pairs": gc["pairs"], "gate_ready": bool(use_gate and ins),
            "needs_arbitration": any(p["layout"] in ("berdampingan", "berdampingan_sekat") for p in gc["pairs"]),
            "notes": notes}


async def warehouse_gate_policy(warehouse_id: str) -> Dict[str, Any]:
    """Helper untuk paket gate (D1): bagaimana gerak roll di gedung ini dikonfirmasi (K-GDG-01/02, K-RFID-04)."""
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0, "id": 1, "name": 1, "gate_config": 1,
                                                             "stock_mode": 1})
    if not wh:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    return gate_policy_of(wh)


def has_role(wh: Optional[Dict[str, Any]], *roles: str) -> bool:
    return bool(set((wh or {}).get("roles") or []) & set(roles))


async def assert_site_exists(site_id: str) -> None:
    if site_id and not await db.warehouse_sites.find_one({"id": site_id}):
        raise HTTPException(status_code=400, detail="Lokasi (site) tidak ditemukan")


def check_storage_rules(warehouse: Dict[str, Any], category: str, grade: str) -> Dict[str, Any]:
    """Apakah roll (kategori, grade) boleh disimpan di gedung ini? → {ok, reason}."""
    # P02 DEV-G02 — kategori DAN grade diperiksa bersamaan (AND), lewat evaluator bersama.
    from services import placement_rules as pr
    r = pr.warehouse_rules(warehouse)
    r = {**r, "fabric_types": [], "template_ids": [], "owner_entity_ids": []}
    out = pr._attr_violations([(warehouse.get("name", ""), r)], {"category": category}, grade)
    return {"ok": not out, "reason": " ".join(out)}


# ─── Sites ───────────────────────────────────────────────────────────────────
async def list_sites() -> List[Dict[str, Any]]:
    sites = await db.warehouse_sites.find({}, {"_id": 0}).sort("name", 1).to_list(200)
    counts: Dict[str, int] = {}
    async for w in db.warehouses.find({"site_id": {"$nin": [None, ""]}}, {"_id": 0, "site_id": 1}):
        counts[w["site_id"]] = counts.get(w["site_id"], 0) + 1
    for s in sites:
        s["warehouse_count"] = counts.get(s["id"], 0)
    return [safe_doc(s) for s in sites]


async def create_site(name: str, city: str, actor_name: str, location: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nama lokasi wajib diisi")
    if await db.warehouse_sites.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}}):
        raise HTTPException(status_code=409, detail="Nama lokasi sudah ada")
    site = {"id": new_id("site"), "name": name, "city": (city or "").strip(), **(location or {}),
            "created_at": now_iso(), "created_by": actor_name}
    await db.warehouse_sites.insert_one(dict(site))
    return safe_doc(site)


async def update_site(site_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    _keys = {"name", "city", "country", "country_code", "province", "province_code", "city_code", "district", "district_code", "postal_code", "location_status"}
    data = {k: str(v).strip() for k, v in patch.items() if k in _keys and v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan")
    data["updated_at"] = now_iso()
    await db.warehouse_sites.update_one({"id": site_id}, {"$set": data})
    site = await db.warehouse_sites.find_one({"id": site_id}, {"_id": 0})
    if not site:
        raise HTTPException(status_code=404, detail="Lokasi tidak ditemukan")
    return safe_doc(site)


async def delete_site(site_id: str) -> Dict[str, Any]:
    used = await db.warehouses.count_documents({"site_id": site_id})
    if used:
        raise HTTPException(status_code=409,
                            detail=f"Lokasi masih dipakai {used} gedung — lepaskan dulu dari gedungnya.")
    res = await db.warehouse_sites.delete_one({"id": site_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lokasi tidak ditemukan")
    return {"ok": True}


# ─── Seed blueprint (idempotent) — peta gudang nyata user ────────────────────
BLUEPRINT_SITES = [
    {"key": "rancamalang", "name": "Rancamalang", "city": "Bandung"},
    {"key": "soreang", "name": "Soreang", "city": "Bandung"},
    {"key": "jakarta", "name": "Jakarta", "city": "Jakarta"},
]
BLUEPRINT_WH = [
    {"site": "rancamalang", "code": "RCM-TRANSIT", "name": "Gedung Transit (Central)",
     "roles": ["transit", "central_inbound", "staging"], "gate": False,
     "rules": {"mode": "none", "categories": [], "grades": []}},
    {"site": "rancamalang", "code": "RCM-WOVEN", "name": "Gedung Woven",
     "roles": ["storage"], "gate": True, "rules": {"mode": "category", "categories": [], "grades": []}},
    {"site": "rancamalang", "code": "RCM-KNITTING", "name": "Gedung Knitting",
     "roles": ["storage"], "gate": True, "rules": {"mode": "category", "categories": [], "grades": []}},
    {"site": "rancamalang", "code": "RCM-PRINTING", "name": "Gedung Printing",
     "roles": ["storage"], "gate": True, "rules": {"mode": "category", "categories": [], "grades": []}},
    # PREP-C (K-GDG-01/04) — Gedung Retur = tempat inspeksi; gate fisik hanya di gedung penyimpanan.
    {"site": "rancamalang", "code": "RCM-RETUR", "name": "Gedung Retur",
     "roles": ["inspection", "return", "storage"], "gate": False,
     "rules": {"mode": "grade", "categories": [], "grades": ["B", "C", "BS"]}},
    {"site": "soreang", "code": "SRG-01", "name": "Gedung Soreang",
     "roles": ["storage"], "gate": True, "rules": {"mode": "none", "categories": [], "grades": []}},
]


async def seed_blueprint(actor_name: str) -> Dict[str, Any]:
    """Buat 3 site + gedung sesuai peta user. Idempotent; gudang existing tidak diubah
    kecuali wh_jakarta yang dipetakan ke site Jakarta (handheld-only)."""
    site_ids: Dict[str, str] = {}
    created_sites = 0
    for s in BLUEPRINT_SITES:
        cur = await db.warehouse_sites.find_one({"name": s["name"]}, {"_id": 0})
        if cur:
            site_ids[s["key"]] = cur["id"]
            continue
        doc = {"id": new_id("site"), "name": s["name"], "city": s["city"],
               "created_at": now_iso(), "created_by": actor_name}
        await db.warehouse_sites.insert_one(doc)
        site_ids[s["key"]] = doc["id"]
        created_sites += 1

    created_wh = 0
    for spec in BLUEPRINT_WH:
        if await db.warehouses.find_one({"code": spec["code"]}):
            continue
        wid = new_id("wh")
        await db.warehouses.insert_one({
            "id": wid, "code": spec["code"], "name": spec["name"],
            "city": next(s["city"] for s in BLUEPRINT_SITES if s["key"] == spec["site"]),
            "site_id": site_ids[spec["site"]],
            "roles": spec["roles"], "storage_rules": spec["rules"],
            "gate_config": normalize_gate_config({"has_gate": spec["gate"]}),
            "stock_mode": "roll_tagged", "storage_form": "rack",
            "sharing_mode": "shared", "entity_ids": [],
            "zones": [{"id": new_id("zone"), "name": "Zone A", "racks": [
                {"id": new_id("rack"), "name": "Rack A1",
                 "bins": [{"id": new_id("bin"), "code": "A1-01", "capacity": 5000.0}]}]}],
            "active": True, "created_at": now_iso(),
        })
        created_wh += 1

    # Gudang Jakarta existing → site Jakarta, storage, handheld-only (tanpa gate fisik)
    jkt = await db.warehouses.find_one({"id": "wh_jakarta"}, {"_id": 0})
    if jkt and not jkt.get("site_id"):
        await db.warehouses.update_one({"id": "wh_jakarta"}, {"$set": {
            "site_id": site_ids["jakarta"], "roles": ["storage"],
            "storage_rules": jkt.get("storage_rules") or {"mode": "none", "categories": [], "grades": []},
            "gate_config": normalize_gate_config({"has_gate": False}), "updated_at": now_iso()}})

    return {"created_sites": created_sites, "created_warehouses": created_wh,
            "sites": await list_sites()}
