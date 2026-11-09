"""Dashboard router: main metrics + overview."""
from typing import Any, Dict, List
from fastapi import APIRouter, Request
from db import db
from core_utils import safe_doc
from dependencies import current_user
from services.inventory_service import expire_old_reservations
from services import sales_ownership          # FASE E-8 (E8.4/US11) — "Pesanan Saya"
from entity_scope import entity_ctx, resolve_list_scope

router = APIRouter(prefix="/api")


# UAT 24 Okt (audit UI tahap 2) — KPI "Jml Tersedia/Dipesan" dulu memuat kelompok "1.503 tanpa satuan". Penyebab di data
# acuan: saldo (`inventory_balances`) milik product_id yang dokumen produknya TIDAK ADA (sisa uji), tanpa roll. Satuan kini
# diturunkan bertahap: base_unit/unit produk → satuan roll produk itu → label jujur "(produk tak terdaftar)" /
# "(satuan belum diisi)" — bukan "tanpa satuan" yang terbaca seperti nama satuan.
UNIT_MISSING = "(satuan belum diisi)"
UNIT_UNKNOWN_PRODUCT = "(produk tak terdaftar)"


async def _units_for_products(pids: List[str]):
    """→ ({pid: satuan}, {pid: label kelompok tanpa satuan})."""
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": pids}}, {"_id": 0, "id": 1, "base_unit": 1, "unit": 1}).to_list(None)}
    unit_of = {pid: (p.get("base_unit") or p.get("unit") or "") for pid, p in prods.items()}
    need = [pid for pid in pids if not unit_of.get(pid)]
    if need:
        async for r in db.inventory_rolls.aggregate([
                {"$match": {"product_id": {"$in": need}, "unit": {"$nin": [None, ""]}}},
                {"$group": {"_id": {"p": "$product_id", "u": "$unit"}, "n": {"$sum": 1}}},
                {"$sort": {"n": -1}}]):
            pid = r["_id"]["p"]
            if not unit_of.get(pid):
                unit_of[pid] = r["_id"]["u"]
    unitless = {pid: (UNIT_UNKNOWN_PRODUCT if pid not in prods else UNIT_MISSING)
                for pid in pids if not unit_of.get(pid)}
    return unit_of, unitless


@router.get("/dashboard")
async def dashboard(request: Request, entity_id: str = None) -> Dict[str, Any]:
    expired = await expire_old_reservations()
    # Multi-Entity (Fase 0): orders & customers di-scope per entitas; produk,
    # gudang & stok bersifat SHARED lintas-entitas (lihat KN_14 §7).
    # KONSISTENSI (RC-7/INV-4/INV-5): pakai resolve_list_scope yang sama dgn
    # GET /sales-orders → tanpa header/param = entitas AKTIF; header X-Entity-Id:all
    # (view_all) = semua entitas yang diizinkan. KPI dashboard SELALU == list.
    ctx = await entity_ctx(request)
    actor = await current_user(request)
    scope = resolve_list_scope("sales_orders", {}, ctx, entity_id)
    # FASE E-8 (E8.4 · US11) — KEPEMILIKAN SALES WAJIB IKUT DI SINI JUGA.
    # Layar "Pesanan" tidak memanggil `GET /sales-orders`; ia memakai `orders[]`
    # dari respons dasbor ini (`hooks/useAppActions.js` — satu panggilan untuk
    # seluruh aplikasi). Karena dasbor dulu hanya menyaring per BADAN USAHA,
    # sales lapangan tetap melihat pesanan rekannya di layar (mis. `sales@`
    # melihat `SO-0008` milik `sales2@`) dan kartu TOTAL menghitung 9, padahal
    # `GET /sales-orders` sudah benar mengembalikan 8. Inilah kelas bug yang
    # diperingatkan `services/sales_ownership.py`: definisi "pesanan saya"
    # tercecer di satu tempat saja sudah cukup untuk membocorkan pipeline rekan.
    # `apply_scope` hanya mengikat peran `sales`; sales_admin/finance/manager/
    # admin/warehouse tetap melihat keseluruhan pesanan seperti sebelumnya.
    order_scope = sales_ownership.apply_scope(scope, actor)
    # FIX-1 (B3a SCP-5) — dulu `find({})`: produk eksklusif sales lain & produk lini lain ikut terkirim ke dasbor.
    # Kini pagar yang SAMA dengan `GET /products` (eksklusivitas per sales + lini; produk tanpa lini tetap terlihat).
    from services import product_exclusivity as _pexcl, line_scope as _lines
    products_raw = await db.products.find(_lines.narrow(_pexcl.visibility_query(actor), actor, ""),
                                          {"_id": 0}).to_list(None)   # G3 D4-DASH-01 — tanpa batas 3.000
    # PREP-A (K-OPN-06) — SKU tergantikan TETAP dikirim (stok lama/lot/riwayat masih menunjuknya) tetapi diberi
    # `superseded_by_sku` agar katalog jual (POS/Sales Portal) menyembunyikannya & memberi petunjuk kode penggantinya.
    from services.product_supersede import annotate as _sup_annotate
    await _sup_annotate(products_raw)
    # S#096 — HPP turunan pembelian (WAC roll) untuk layar Master Produk; diredaksi strip_cost_fields per peran.
    from services import costing_service as _cs
    for _p in products_raw:
        try:
            _w = await _cs.wac_for_product(_p["id"], product=_p)
            _p["hpp"], _p["hpp_source"] = float(_w.get("wac") or 0), _w.get("source", "")
        except Exception:  # noqa: BLE001
            _p["hpp"], _p["hpp_source"] = 0.0, "none"
    orders_raw = await db.sales_orders.find(order_scope, {"_id": 0}).sort("created_at", -1).to_list(20)
    # FASE E-4 (E4.1) — gudang KHUSUS badan usaha lain tidak ikut ke dasbor:
    # kalau ikut, angka "Gudang Aktif" & pemilih gudang di layar menawarkan
    # gudang yang haram dipakai badan usaha aktif.
    from services import warehouse_scope_service as whscope
    wh_filter = {**whscope.usable_query(ctx.active_entity_id), "is_test": {"$ne": True}}   # FIX-1 (K-B1-10) — tanpa gudang data uji
    warehouses_raw = await db.warehouses.find(wh_filter, {"_id": 0}).to_list(100)
    # UAT 24 Okt (P14/P8) — pemilih pelanggan POS & HP: sales hanya pelanggannya (+ walk-in PT), sama dengan
    # CRM; dulu semua pelanggan PT dan terpotong di 100.
    from services.customer_service import scope_query as _cust_scope
    customers_raw = await db.customers.find(_cust_scope(actor, scope), {"_id": 0}).sort("name", 1).to_list(1000)
    from core_utils import strip_cost_fields as _strip_cost
    products = _strip_cost([safe_doc(p) for p in products_raw if p], actor.get("role"))
    orders = [safe_doc(o) for o in orders_raw if o]
    wh_names = await whscope.entity_name_map()
    warehouses = [whscope.decorate(safe_doc(w), wh_names, ctx.active_entity_id)
                  for w in warehouses_raw if w]
    customers = [safe_doc(c) for c in customers_raw if c]
    # G9 fix (RC-7): active_orders dihitung dari SELURUH order via count_documents,
    # BUKAN dari window 20 order terakhir (yang membuat KPI salah saat >20 order).
    # E8.4 — ikut `order_scope` supaya kartu "Pesanan Aktif" tidak pernah lebih besar
    # dari daftar di bawahnya (angka yang tak cocok = pengguna berhenti percaya).
    active_orders = await db.sales_orders.count_documents(
        {**order_scope, "status": {"$nin": ["done", "cancelled", "expired"]}}
    )
    total_products = await db.products.count_documents({})
    total_warehouses = await db.warehouses.count_documents(wh_filter)
    total_customers = await db.customers.count_documents(scope)
    # INV-2/INV-3 (RC-7) — KPI stok dashboard SELALU konsisten dgn GET /inventory/balances:
    # agregasi dari koleksi inventory_balances yang di-SCOPE sama (owner_entity_id).
    # Sebelumnya memakai product_summary() TANPA scope → menghitung stok LINTAS-entitas
    # (mis. roll yang kepemilikannya sudah dipindah lintas-PT via R3 ownership transfer),
    # sehingga KPI > Σbalances (drift 1 meter). Kini keduanya seragam per-entitas aktif.
    bal_scope = resolve_list_scope("inventory_balances", {}, ctx, entity_id)
    # FIX-2 (B3a STK-8/SSOT-4, B1 UI-40) — KPI dibangun dari SATU layanan angka stok (`stock_figures.segments`):
    # cadangan makloon dikurangkan per PT PEMILIK di cakupan (dulu hanya PT AKTIF → mode "Semua PT" +300 kg), gudang
    # non-aktif/uji/yatim tidak ikut. Cakupan PT & lokasi kerja sama dengan `bal_scope` (resolve_list_scope).
    from entity_scope import resolve_scope_ids
    from services import stock_figures as _sf
    owner_ids = set(resolve_scope_ids(ctx, entity_id))
    loc_whs = getattr(ctx, "warehouse_ids", None)
    all_segs = await _sf.segments()
    kpi_segs = [s for s in all_segs if s["owner_entity_id"] in owner_ids
                and (loc_whs is None or s["warehouse_id"] in loc_whs)]
    per_prod: Dict[str, Dict[str, float]] = {}
    for b in kpi_segs:
        d = per_prod.setdefault(b["product_id"], {"on_hand_qty": 0.0, "reserved_qty": 0.0, "available_qty": 0.0,
                                                  "makloon_reserved_qty": 0.0, "roll_count": 0,
                                                  "on_hand_roll_count": 0})
        d["available_qty"] += max(float(b["available_qty"]), 0.0)
        d["reserved_qty"] += float(b.get("reserved_qty") or 0)
        d["on_hand_qty"] += float(b.get("on_hand_qty") or 0)
        d["makloon_reserved_qty"] += float(b.get("makloon_reserved_qty") or 0)
        d["roll_count"] += int(b.get("available_rolls") or 0)
        d["on_hand_roll_count"] += int(b.get("on_hand_rolls") or 0)
    total_available = round(sum(d["available_qty"] for d in per_prod.values()), 2)
    total_reserved = round(sum(d["reserved_qty"] for d in per_prod.values()), 2)
    # F-04 (uji pra-UAT 2026-10-21) — KPI "Jml Tersedia/Dipesan" per SATUAN: yard dan kg tidak boleh dijumlahkan
    # menjadi satu angka. Satuan = base_unit produk (saldo tidak menyimpan satuan); + jumlah roll tersedia.
    unit_of, unitless = await _units_for_products(list(per_prod))
    available_by_unit: Dict[str, float] = {}
    reserved_by_unit: Dict[str, float] = {}
    for pid, d in per_prod.items():
        unit = unit_of.get(pid) or unitless.get(pid) or UNIT_MISSING   # tetap terlihat, tidak dicampur
        available_by_unit[unit] = round(available_by_unit.get(unit, 0.0) + d["available_qty"], 2)
        reserved_by_unit[unit] = round(reserved_by_unit.get(unit, 0.0) + d["reserved_qty"], 2)
    available_rolls = sum(int(d.get("roll_count") or 0) for d in per_prod.values())
    # 2026-10 — kartu produk (Kasir/katalog) memakai stok GLOBAL; KPI di atas tetap per entitas aktif.
    # FIX-2 — + dua angka {LOKAL, GLOBAL} per produk (`stock_figures`) untuk katalog POS/HP & Master Produk.
    from services import sales_stock_service
    _own = bal_scope.get("owner_entity_id")
    _scope = await _sf.viewer_scope(ctx, entity_id=entity_id if entity_id and entity_id != "all" else "")
    await sales_stock_service.apply_global(products, _own if isinstance(_own, str) else "", scope=_scope)
    if not isinstance(_own, str):
        # mode gabungan: "stok PT" = Σ PT dalam cakupan (definisi tunggal, makloon per PT pemilik)
        for product in products:
            d = per_prod.get(product.get("id"), {})
            product["entity_available_qty"] = round(float(d.get("available_qty") or 0), 2)
            product["entity_roll_count"] = int(d.get("roll_count") or 0)
    # MD-08 — kode versi supplier ikut ke Master Produk (pencarian dua sisi).
    from services.supplier_item_service import attach_supplier_codes
    await attach_supplier_codes(products)
    return {
        "expired_released": expired,
        "metrics": {
            "products": total_products,
            "warehouses": total_warehouses,
            "customers": total_customers,
            # FIX-2 (STK-8) — angka campur satuan ini TIDAK untuk ditampilkan; layar memakai `available_by_unit`.
            "available_qty": total_available,
            # UAT 24 Okt (audit UI tahap 2) — produk yang satuannya tak bisa diturunkan (untuk perbaikan data).
            "unitless_product_ids": sorted(unitless)[:50],
            "reserved_qty": total_reserved,
            "available_by_unit": {u: q for u, q in available_by_unit.items() if q > 0.004},
            "reserved_by_unit": {u: q for u, q in reserved_by_unit.items() if q > 0.004},
            "available_rolls": available_rolls,
            "active_orders": active_orders,
        },
        "products": products,
        "stock_scope": _sf.scope_public(_scope),
        "orders": orders,
        "warehouses": warehouses,
        "customers": customers,
    }
