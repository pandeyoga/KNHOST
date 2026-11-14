"""Products router: CRUD products + stock breakdown."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
import domain_registry as dr
from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, parse_decimal, safe_doc, strip_cost_fields
from schemas import GenericPatch, ProductPayload
from services.inventory_service import expire_old_reservations  # noqa: F401 — dipakai penjadwal (FIX-3b)
from services import pricelist_service
from services import rnd_gate
from services import product_exclusivity as pexcl
from services import line_scope
from services import supplier_item_service as _sis   # MD-08 — kode ganda KN ↔ supplier
from entity_scope import entity_ctx, apply_entity_scope

router = APIRouter(prefix="/api")


@router.get("/products")
async def list_products(request: Request, orderable_only: bool = False,
                        line: str = "", stage: str = "", include_superseded: bool = False) -> List[Dict[str, Any]]:
    # INV-AUTH-01 (KN-076-AUTH-MASTER-LEAK P1): katalog WAJIB login — auth di LUAR try/except.
    actor = await require_permission(request, "product", "view")
    # FIX-3b (STK-11) — kedaluwarsa reservasi dijalankan job penjadwal `reservation_expiry` (GET tidak menulis).
    # PS-20 — visibilitas eksklusif per sales DIPAKSA DI BACKEND (query Mongo), bukan di UI,
    # agar sales lain tidak bisa menembusnya lewat API.
    # FASE L — pagar lini ditambahkan pada query yang SAMA (bukan penyaringan di
    # memori) supaya `?line=` dari staf berpagar tidak bisa dipakai sebagai jalan
    # belakang, dan produk tanpa lini (data lama) tetap terlihat.
    query = line_scope.narrow(pexcl.visibility_query(actor), actor, line)
    if stage:  # temuan 2026-10-19D — `?stage=` sebelumnya diabaikan
        query = {"$and": [query, {"stage": {"$in": [s.strip() for s in stage.split(",") if s.strip()]}}]}
    # PREP-A (K-OPN-06) — produk "digantikan oleh" (kode salah/duplikat) tidak ditawarkan ke pemilih dokumen BARU.
    # Daftar ini adalah sumber ±20 pemilih (PR/PO/RFQ/transfer/MKO/ProductSelect …). Laporan/riwayat tidak
    # memakai daftar ini; layar yang butuh semua SKU memanggil `?include_superseded=true`.
    if not include_superseded:
        from services.product_supersede import exclude_superseded
        query = exclude_superseded(query)
    products = await db.products.find(query, {"_id": 0}).to_list(500)
    # FASE F (PS-12) — katalog jual/beli hanya menampilkan produk yang SAH dipesan.
    # Dipakai POS/Sales Portal (`orderable_only=true`); Master Produk tetap melihat semua.
    if orderable_only:
        products = [p for p in products if rnd_gate.is_orderable(p)]
    # F1a — harga jual per-entitas: tampilkan harga efektif entitas aktif (fallback global).
    role = actor.get("role")
    try:
        ctx = await entity_ctx(request)
        active = ctx.active_entity_id
    except Exception:
        ctx, active = None, None
    pmap = {p["id"]: p for p in products}
    price_map = await pricelist_service.resolve_many(active, [p["id"] for p in products], pmap)
    # MD-08 — kode/nama versi SUPPLIER ikut dibawa agar pencarian katalog/PR/PO cocok di kedua sisi.
    await _sis.attach_supplier_codes(products)
    # 2026-10 — stok GLOBAL lintas entitas (minus cadangan makloon) + barang datang untuk SO vs restock.
    # FIX-2 — angka dari SATU layanan (`stock_figures`) + dua angka {LOKAL, GLOBAL} per produk (`stock_figures`).
    from services import sales_stock_service
    from services import stock_figures as _sf
    _scope = await _sf.viewer_scope(ctx) if ctx is not None else None
    await sales_stock_service.apply_global(products, active or "", scope=_scope)
    for product in products:
        info = price_map.get(product["id"], {})
        product["global_price"] = float(product.get("price", 0) or 0)
        if info.get("source") == "entity":
            product["price"] = info["price"]
        product["price_source"] = info.get("source", "global")
    # S#096 — HPP bukan isian manual: turunan biaya PO/penerimaan (WAC roll) ditampilkan
    # sebagai `hpp` + `hpp_source`; `harga_pokok` lama hanya cadangan bila belum ada roll.
    from services import costing_service as _cs
    for product in products:
        try:
            w = await _cs.wac_for_product(product["id"], product=product)
            product["hpp"] = float(w.get("wac") or 0)
            product["hpp_source"] = w.get("source", "")
        except Exception:  # noqa: BLE001
            product["hpp"] = float(product.get("harga_pokok") or 0)
            product["hpp_source"] = "harga_pokok"
    from services.catalog_access import public_product
    from dependencies import permission_matrix
    matrix = await permission_matrix()
    manage = 'update' in matrix.get(role, {}).get('product', [])
    parent_names = {t['id']: t['name'] for t in await db.product_templates.find({}, {'_id': 0, 'id': 1, 'name': 1}).to_list(10000)}
    for p in products:
        if p.get('template_id') in parent_names:
            p['template_name'] = parent_names[p['template_id']]
    return [public_product(p, actor, manage=manage) for p in products]


def _apply_domain(data: Dict[str, Any], existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Fase A (PS-01/02/03/09) — normalisasi + validasi domain tekstil.

    Melempar HTTP 400 (pesan Indonesia) bila stage/fabric_type/grade tidak sah atau
    kelengkapan wajib per stage belum terpenuhi (GSM/lebar ≥ grey, yarn_count utk yarn).
    Mengembalikan hasil validasi (berisi `warnings` & `needs_review*`).
    """
    dr.apply_normalization(data)
    check = dr.validate_product(data, existing)
    if check["errors"]:
        raise HTTPException(status_code=400, detail=" ".join(check["errors"]))
    return check


def _pajak_produk(data: Dict[str, Any]) -> None:
    """TX-T1 — `tax_treatment` (kena · dibebaskan · tidak_dipungut) dan `tax_item_code`; tidak sah → 400."""
    from services.tax_config_service import periksa_pajak_produk
    try:
        periksa_pajak_produk(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/products")
async def create_product(payload: ProductPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "create")
    if await db.products.find_one({"sku": payload.sku}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="SKU sudah digunakan")
    product = payload.model_dump()
    product["harga_pokok"] = 0.0   # S#096 — HPP tidak diisi manual; terbentuk dari PO/penerimaan (WAC roll)
    _pajak_produk(product)         # TX-T1 — perlakuan PPN & kode barang pajak (disimpan, belum dipakai mesin)
    # FASE G-0 — `inventory.default_uom` DULU tidak dibaca kode mana pun. Sekarang benar-benar
    # menjadi satuan dasar bawaan produk baru bila pengguna tidak mengisinya.
    if not (product.get("base_unit") or "").strip():
        # KF-T3 (KF-10) — satuan bawaan PT AKTIF pembuatnya (lapisan PT Pusat Pengaturan berlaku).
        from config_registry import default_of
        from services.config_resolver import value_of
        try:
            _pt_pembuat = getattr(await entity_ctx(request), "active_entity_id", "") or ""
        except Exception:                   # noqa: BLE001 — tanpa konteks = nilai grup
            _pt_pembuat = ""
        product["base_unit"] = str(await value_of("inventory.default_uom", {"entity_id": _pt_pembuat})
                                   or default_of("inventory.default_uom"))
    check = _apply_domain(product)
    # PS-20 — normalisasi + validasi eksklusivitas (owner wajib sales aktif bila eksklusif).
    await pexcl.normalize(db, product)
    # FASE L — lini divalidasi terhadap MASTER (bukan daftar hardcode) + INV-LINE-02.
    # Staf berpagar lini hanya boleh membuat produk di lininya sendiri, kalau tidak
    # pagar bacanya bisa dilewati hanya dengan membuat produk baru.
    ctx_l = None
    try:
        ctx_l = await entity_ctx(request)
    except Exception:                       # noqa: BLE001 — tanpa konteks = master global
        ctx_l = None
    await line_scope.normalize_product(
        product, entity_id=getattr(ctx_l, "active_entity_id", "") or "")
    line_scope.assert_can_order(actor, product)
    # FASE F (PS-12) — produk yang dibuat LANGSUNG dari Master Produk mengikuti kebijakan
    # `rnd.new_product_default_lifecycle` (bawaan `produksi` agar cara kerja lama tetap sama).
    if not (product.get("lifecycle") or "").strip():
        product["lifecycle"] = await rnd_gate.default_new_lifecycle()
    product.update({"id": new_id("prod"), "batch_lot_rolls": [],
                    "needs_review": check["needs_review"],
                    "needs_review_reasons": check["needs_review_reasons"],
                    "created_at": now_iso(), "updated_at": now_iso()})
    from services import product_variant_service as pvs
    if product.get('template_id'):
        from services.catalog_access import template_for
        await template_for(actor, product['template_id'], manage=True)
    product = await pvs.save_product(product, actor=actor.get('name', 'System'), entity_id=getattr(ctx_l, 'active_entity_id', '') or '')
    await audit(actor["name"], "product_created", "product", product["id"], product)
    out = safe_doc(product)
    out["domain_warnings"] = check["warnings"]
    return out


@router.patch("/products/{product_id}")
async def update_product(product_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    allowed = ["sku", "name", "category", "variant", "color", "motif", "supplier",
               "color_code", "color_name", "color_hex",
               "base_unit", "price", "image", "description", "status", "uom_conversions",
               # "harga_pokok" SENGAJA tidak boleh di-PATCH: HPP datang dari PO/penerimaan (S#096)
               "kg_per_meter", "reorder_point", "reorder_qty", "template_id", "variant_attrs", "variant_options",
               "lifecycle", "spec_id", "design_id", "design_version",
               "source_name", "source_color"] \
        + dr.PRODUCT_DOMAIN_FIELDS   # Fase A — stage/fabric_type/grade/gramasi/lebar/yarn_count*
    allowed += ["exclusivity", "owner_sales_ids"]   # PS-20 — kepemilikan/visibilitas produk
    allowed += ["line_code"]                        # FASE L — pembagian kerja MD
    allowed += ["base_fabric_template_id", "origin"]  # kain dasar master data · asal impor/lokal
    allowed += ["tax_treatment", "tax_item_code"]     # TX-T1 — disimpan & ditampilkan, belum dipakai mesin (L5)
    data = {k: v for k, v in payload.data.items() if k in allowed}
    _pajak_produk(data)
    if "lifecycle" in data:
        lc = str(data["lifecycle"] or "").strip().lower()
        if lc and not dr.is_valid("lifecycle", lc):
            raise HTTPException(status_code=400, detail=(
                f"Tahap produk (lifecycle) '{lc}' tidak dikenal. "
                f"Pilihan: {', '.join(dr.values_of('lifecycle'))}."))
        data["lifecycle"] = lc
    from services.catalog_access import product_for, template_for
    existing = await product_for(actor, product_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    if 'template_id' in data and not data['template_id']:
        raise HTTPException(400, 'SKU wajib memiliki induk.')
    if data.get('template_id'):
        await template_for(actor, data['template_id'], manage=True)
    if existing.get('spec_id') and any(k in data and data[k] != existing.get(k) for k in ('lifecycle', 'spec_id', 'design_id', 'design_version', 'variant_attrs', 'variant_options', 'template_id', 'color', 'color_code', 'grade', 'lebar', 'fabric_type', 'stage')):
        raise HTTPException(409, 'Spesifikasi/identitas varian R&D dikunci. Gunakan alur R&D untuk keputusan dan rilis, atau buat spesifikasi baru.')
    if 'sku' in data and data['sku'] != existing.get('sku'):
        raise HTTPException(409, 'Kode SKU yang sudah dibuat tidak dapat diganti; riwayat transaksi harus tetap konsisten.')
    if existing.get('media') and 'image' in data:
        data.pop('image')  # cover dikelola atomik oleh galeri, bukan URL editor lama
    # PS-15/R5 — angka boleh dikirim sebagai teks berkoma ("10,5").
    for num_field in ("price", "gramasi", "lebar", "kg_per_meter",
                      "reorder_point", "reorder_qty"):
        if num_field in data:
            try:
                data[num_field] = parse_decimal(data[num_field])
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"{num_field}: {exc}")
    check = _apply_domain(data, existing)
    data["needs_review"] = check["needs_review"]
    data["needs_review_reasons"] = check["needs_review_reasons"]
    data["updated_at"] = now_iso()
    # PS-20 — normalisasi eksklusivitas bila field dikirim pada patch ini.
    await pexcl.normalize(db, data)
    # FASE L — pagar lini dua arah: staf berpagar tidak boleh menyentuh produk lini
    # lain, dan tidak boleh MEMINDAHKAN produk ke lini di luar aksesnya.
    line_scope.assert_can_touch(actor, existing, what=f"Produk '{existing.get('name', product_id)}'")
    try:
        ctx_l = await entity_ctx(request)
        active_eid = getattr(ctx_l, "active_entity_id", "") or ""
    except Exception:                       # noqa: BLE001
        active_eid = ""
    await line_scope.normalize_product(data, existing, entity_id=active_eid)
    if "line_code" in data:
        line_scope.assert_can_order(actor, {**existing, **data})
    from services import product_variant_service as pvs
    merged = {**existing, **data}
    if 'variant_attrs' not in data and 'variant_options' not in data:
        attrs = dict(existing.get('variant_attrs') or {})
        codes = dict(existing.get('variant_options') or {})
        for key in ('color', 'grade', 'lebar', 'origin'):
            if key in data and data[key] != existing.get(key):
                attrs[key] = data[key]
                codes.pop(key, None)
        merged.update(variant_attrs=attrs, variant_options=codes)
    product = await pvs.save_product(merged, actor=actor['name'], existing=existing, entity_id=active_eid)
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    _changed = [k for k in data if k != "updated_at"]
    await audit(actor["name"], "product_updated", "product", product_id,
                {k: product.get(k) for k in _changed}, before={k: existing.get(k) for k in _changed})
    product["domain_warnings"] = check["warnings"]
    return product


@router.get("/products/sales-owners")
async def list_sales_owners(request: Request) -> List[Dict[str, Any]]:
    """PS-20 — daftar user sales (id + nama) untuk memilih pemilik produk eksklusif.

    Dipakai form Master Produk. Digerbang izin `product:update` (yang punya hanya admin),
    jadi tidak membocorkan daftar user ke role lain.
    """
    await require_permission(request, "product", "update")
    from role_registry import roles_in_category   # PR-T4 — kategori kerja "sales" (bukan nama peran persis)
    users = await db.users.find(
        {"role": {"$in": roles_in_category("sales")}, "status": "active"}, {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).sort("name", 1).to_list(200)
    return users


# PK-47 (MB-01) — baca SATU master barang. Didaftarkan SESUDAH `/products/sales-owners` (dan rute ber-kata tetap
# lain) supaya tidak menelannya. Hanya master barang: harga per PT, HPP hitung, dan stok tetap milik daftar atau
# `stock-breakdown` (02_STANDAR §5 D1 — satu rumus per angka).
@router.get("/products/{product_id}")
async def get_product(product_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "view")
    product = await db.products.find_one({"$and": [pexcl.visibility_query(actor), {"id": product_id}]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    line_scope.assert_can_touch(actor, product, what=f"Produk '{product.get('name', product_id)}'")
    from dependencies import has_permission
    from services.catalog_access import public_product
    return public_product(safe_doc(product), actor, manage=await has_permission(actor, "product", "update"))


@router.delete("/products/{product_id}")
async def delete_product(product_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "delete")
    from services.master_usage_service import assert_lifecycle_role
    await assert_lifecycle_role(actor, "menonaktifkan SKU")
    from services.catalog_access import product_for
    existing = await product_for(actor, product_id)
    if existing.get('saga_lock'):
        raise HTTPException(409, 'SKU sedang diproses. Tunggu sebelum menonaktifkan.')
    product = await db.products.find_one_and_update(
        {"id": product_id},
        {"$set": {"status": "inactive", "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    await audit(actor["name"], "product_deactivated", "product", product_id, {"status": product.get("status")},
                before={"status": existing.get("status")})
    return product


@router.get("/products/{product_id}/stock-breakdown")
async def stock_breakdown(product_id: str, request: Request) -> Dict[str, Any]:
    # INV-AUTH-01 (KN-076-AUTH-MASTER-LEAK P1): WAJIB login — auth di LUAR try/except.
    # S-10 — role penentu redaksi HPP (default teredaksi utk non admin/manager).
    actor = await require_permission(request, "product", "view")
    role = actor.get("role")
    product = safe_doc(await db.products.find_one({"id": product_id}, {"_id": 0}))
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    # FASE L — pagar lini juga berlaku pada BACA per dokumen. Kalau hanya daftarnya
    # disaring, alamat langsung `/products/{id}/stock-breakdown` tetap membocorkan
    # produk lini lain (kelas bug IDOR yang sama dengan pagar entitas).
    line_scope.assert_can_touch(actor, product,
                                what=f"Produk '{product.get('name', product_id)}'")
    # FIX-2 (B3a SSOT-4/STK-7/SCP-4, keputusan #7) — angka dari SATU layanan (`stock_figures`): saldo per segmen sudah
    # dikurangi cadangan makloon; matriks dihitung dari SELURUH roll (agregasi, tanpa batas 5.000) dengan definisi
    # tunggal (panjang dipesan potong & klaim PA keluar dari Tersedia, hold/wip ikut Stok Fisik); roll milik PT di luar
    # izin pengguna hanya angka + identitas (tanpa supplier/PO/faktur/reservasi/HPP).
    from services import stock_figures as _sf
    from services.roll_service import PHYSICAL_ROLL_STATUSES
    _segs = await _sf.segments([product_id])
    _idx = _sf.segment_index(_segs)
    balances_raw = await db.inventory_balances.find({"product_id": product_id}, {"_id": 0}).to_list(None)
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(None)}
    entities = {e["id"]: e for e in await db.business_entities.find({}, {"_id": 0}).to_list(None)}
    # E-01 (audit 2026-09-02) — reservasi HANYA dari badan usaha yang diizinkan, dan
    # diproyeksikan ringkas: dokumen SO utuh PT lain (pelanggan, harga, alamat) pernah
    # bocor ke sales PT lain lewat endpoint ini.
    ctx_sb = await entity_ctx(request)
    allowed_ents = set(getattr(ctx_sb, "allowed_entity_ids", None) or [])
    reservations_raw = await db.sales_orders.find(
        apply_entity_scope("sales_orders", {
            "allocations.product_id": product_id,
            "status": {"$in": ["reserved", "waiting_approval", "approved", "confirmed"]}},
            ctx_sb, mode="allowed"),
        {"_id": 0, "id": 1, "number": 1, "entity_id": 1, "status": 1, "allocations": 1,
         "customer_name": 1, "created_at": 1}
    ).to_list(100)
    _ROLL_LIMIT = 5000
    rolls_total = await db.inventory_rolls.count_documents({"product_id": product_id})
    rolls_raw = await db.inventory_rolls.find({"product_id": product_id}, {"_id": 0}).to_list(_ROLL_LIMIT)

    def _ent_name(eid):
        e = entities.get(eid, {})
        return e.get("short_name") or e.get("legal_name", eid)

    rows = []
    for balance in balances_raw:
        b = _sf.adjust_balance_row(safe_doc(balance), _idx)
        warehouse = safe_doc(warehouses.get(b.get("warehouse_id"), {}))
        rows.append({**b, "warehouse_name": warehouse.get("name"), "warehouse_city": warehouse.get("city"),
                     "owner_entity_name": _ent_name(b.get("owner_entity_id"))})

    # Matriks (Owner × Gudang × Lot) — KN_15 §8 (K1); FIX-2: agregasi seluruh roll, definisi tunggal.
    counted = {wid for wid, w in (await _sf.warehouse_map()).items() if w["counted"]}
    matrix: Dict[tuple, Dict[str, Any]] = {}
    async for g in db.inventory_rolls.aggregate([
            {"$match": {"product_id": product_id, "length_remaining": {"$gt": 0}}},
            {"$group": {"_id": {"o": "$owner_entity_id", "w": "$warehouse_id", "l": "$lot", "s": "$status",
                                "am": {"$gt": ["$active_movement.id", None]},
                                "ih": {"$eq": ["$inspection.hold.held", True]}},
                        "len": {"$sum": "$length_remaining"},
                        "lres": {"$sum": {"$min": ["$length_remaining", {"$ifNull": ["$length_reserved", 0]}]}},
                        "n": {"$sum": 1}, "grade": {"$first": "$grade"}}}]):
        k = g["_id"]
        if k.get("w") not in counted:
            continue
        wh = warehouses.get(k.get("w"), {})
        cell = matrix.setdefault((k.get("o"), k.get("w"), k.get("l")), {
            "owner_entity_id": k.get("o"), "owner_entity_name": _ent_name(k.get("o")),
            "warehouse_id": k.get("w"), "warehouse_name": wh.get("name", ""),
            "warehouse_city": wh.get("city", ""), "lot": k.get("l"), "grade": g.get("grade"),
            "available_qty": 0.0, "available_rolls": 0, "reserved_qty": 0.0, "committed_qty": 0.0,
            "hold_qty": 0.0, "makloon_reserved_qty": 0.0, "on_hand_qty": 0.0, "roll_count": 0,
        })
        length, status = float(g["len"] or 0), k.get("s")
        if status == "available":
            if k.get("am") or k.get("ih"):
                cell["hold_qty"] += length          # diklaim PA / tahan inspeksi: fisik, tidak tersedia
            else:
                free = length - float(g.get("lres") or 0)
                cell["available_qty"] += free
                cell["reserved_qty"] += float(g.get("lres") or 0)   # panjang dipesan potong
                cell["available_rolls"] += int(g["n"] or 0) if free > 0.001 else 0
        elif status == "reserved":
            cell["reserved_qty"] += length
        elif status in ("committed", "picked", "packed"):
            cell["committed_qty"] += length
        elif status in PHYSICAL_ROLL_STATUSES:
            cell["hold_qty"] += length
        if status in PHYSICAL_ROLL_STATUSES:
            cell["on_hand_qty"] += length
            cell["roll_count"] += int(g["n"] or 0)
    # cadangan makloon per segmen (aturan tunggal) dibagikan ke lot terbesar dulu dalam segmen itu
    for s_ in _segs:
        left = float(s_.get("makloon_reserved_qty") or 0)
        cells = sorted([c for (o, w, _l), c in matrix.items() if o == s_["owner_entity_id"] and w == s_["warehouse_id"]],
                       key=lambda c: -c["available_qty"])
        for c in cells:
            cut = min(left, max(c["available_qty"], 0.0))
            c["available_qty"] -= cut
            c["makloon_reserved_qty"] += cut
            left -= cut
            if left <= 0.001:
                break
    matrix_list = []
    for cell in matrix.values():
        for k in ("available_qty", "reserved_qty", "committed_qty", "hold_qty", "makloon_reserved_qty", "on_hand_qty"):
            cell[k] = round(max(cell[k], 0.0), 2)
        matrix_list.append(cell)
    matrix_list.sort(key=lambda c: (c["owner_entity_name"], c["warehouse_name"], c["lot"] or ""))

    _IDENTITY = ("id", "roll_no", "lot", "dye_lot", "grade", "warehouse_id", "bin_id", "owner_entity_id", "status",
                 "length_initial", "length_remaining", "length_reserved", "unit", "product_id")
    rolls = []
    for r in rolls_raw:
        r = safe_doc(r)
        if allowed_ents and r.get("owner_entity_id") not in allowed_ents:
            r = {k: r.get(k) for k in _IDENTITY if k in r}   # B3a keputusan #7 — angka + identitas saja
            r["restricted"] = True
        wh = warehouses.get(r.get("warehouse_id"), {})
        r["warehouse_name"] = wh.get("name", "")
        r["owner_entity_name"] = _ent_name(r.get("owner_entity_id"))
        rolls.append(r)

    return strip_cost_fields({
        "product": product,
        "balances": rows,
        "ownership_matrix": matrix_list,
        "rolls": rolls,
        "rolls_total": rolls_total,
        "rolls_truncated": rolls_total > len(rolls),
        "reservations": [safe_doc(r) for r in reservations_raw if r]
    }, role)
