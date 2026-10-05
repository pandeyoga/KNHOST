"""DEMO LENGKAP KN — tahap 1: master pendukung, struktur gudang, akun semua peran, produk semua tahap bahan + stok.

Melengkapi master ASLI hasil migrasi (import_master_produk_kn.py + import_stok_awal_kn.py) — TIDAK menghapus
atau menimpa master asli. Idempoten: dijalankan ulang = melengkapi yang belum ada saja.
  python scripts/seed_demo_lengkap_kn.py            (lalu: python scripts/seed_demo_transaksi_kn.py)
"""
import asyncio
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core_utils import hash_password, new_id, now_iso  # noqa: E402
from db import db  # noqa: E402
from scripts.demo_api import BATCH, DEMO_PASSWORD, Api, ApiError  # noqa: E402

KSC, KANDA = "ent_ksc", "ent_kanda"
MAIL = "@kainnusantara.id"
REF = "STOK_AWAL_DEMO"


def log(msg: str) -> None:
    print(msg, flush=True)


async def cst_id() -> str:
    ent = await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1})
    if not ent:
        sys.exit("Entitas Cipta Sandang (CST) belum ada — jalankan backend terbaru dulu (bootstrap).")
    return ent["id"]


# ─── 1. Master referensi (warna, lini, tahapan proses, jenis sampel, alasan keluhan, motif) ─────────────
async def seed_reference_masters() -> None:
    import seed_realistic as sr
    sr.init_with_db(db)
    for coll, fn in (("color_library", sr.seed_color_library), ("product_lines", sr.seed_product_lines),
                     ("process_stages", sr.seed_process_stages), ("sample_types", sr.seed_sample_types),
                     ("complaint_reasons", sr.seed_complaint_reasons)):
        if await db[coll].count_documents({}) == 0:
            await fn()
        else:
            log(f"   = {coll}: sudah ada ({await db[coll].count_documents({})}) — dilewati")
    named = await db.products.distinct("variant_attrs.color", {"import_batch": "MIGRASI_MASTER_PRODUK_KN"})
    added = 0
    for name in named:
        if re.fullmatch(r"[\d\s/A-Ca-c\-]+", name or ""):
            continue  # kode warna numerik pabrik, bukan nama
        code = "KNM-" + re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:20]
        if await db.color_library.find_one({"code": code}, {"_id": 1}):
            continue
        await db.color_library.insert_one({
            "id": f"col_{code.lower().replace('-', '_')}", "code": code, "name": name.title(), "hex": _hex(name),
            "system": "KN", "family": "Master Produk", "status": "active", "factory_name": name,
            "demo_batch": BATCH, "created_by": "Demo Lengkap", "created_at": now_iso(), "updated_at": now_iso()})
        added += 1
    log(f"   + warna dari master produk: {added} nama warna (hex perkiraan)")
    import bootstrap
    await bootstrap.seed_design_gallery_foundation()
    log(f"   = galeri motif/desain: {await db.design_gallery.count_documents({})} motif")


HEX = {"HITAM": "#1A1A1A", "BLACK": "#1A1A1A", "NAVY": "#1F2A44", "BIRU": "#2E5EAA", "BLUE": "#2E5EAA",
       "MAROON": "#6B1E2B", "BURGUNDY": "#6B1E2B", "MERAH": "#B22234", "PINK": "#E8A0B4", "PEACH": "#F4C2A1",
       "HIJAU": "#3C7A4A", "OLIVE": "#6B6B2A", "SAGE": "#9CAF88", "TOSCA": "#2BB3A3", "JADE": "#4E9F8A",
       "ABU": "#9A9A9A", "GREY": "#9A9A9A", "SILVER": "#C0C0C0", "COKLAT": "#6F4E37", "BROWN": "#5C4033",
       "MOCCA": "#8B6B4E", "KHAKI": "#C3B091", "BEIGE": "#D9C8A9", "CREAM": "#F1E6C8", "SAND": "#D8C3A0",
       "ORANGE": "#E9762B", "YELLOW": "#F3E39A", "TAN": "#C8A27A", "TAUPE": "#8B7D6B", "COFFEE": "#5B3A29"}


def _hex(name: str) -> str:
    up = (name or "").upper()
    return next((h for k, h in HEX.items() if k in up), "#B8B2A7")


# ─── 2. Struktur gudang (Rancamalang 5 gedung shared · Soreang Kanda · Jakarta Sukacita) ──────────────────
async def seed_warehouses(sys_admin, cst: str) -> Dict[str, str]:
    from services import warehouse_profile_service as whp
    res = await whp.seed_blueprint("Demo Lengkap")
    log(f"   + site baru {res['created_sites']} · gedung baru {res['created_warehouses']}")
    sites = {s["name"]: s["id"] for s in await whp.list_sites()}
    jkt = await db.warehouses.find_one({"code": "WH-JKT"}, {"_id": 0}) or {}
    if not jkt:
        wid = new_id("wh")
        await db.warehouses.insert_one({"id": wid, "code": "WH-JKT", "name": "Gudang Jakarta", "city": "Jakarta",
                                        "zones": _zones(), "active": True, "created_at": now_iso()})
        jkt = {"id": wid}
    patches = {
        "RCM-TRANSIT": {"name": "Rancamalang · Gudang Transit", "sharing_mode": "shared", "entity_ids": []},
        "RCM-WOVEN": {"name": "Rancamalang · Gudang Woven", "sharing_mode": "shared", "entity_ids": []},
        "RCM-KNITTING": {"name": "Rancamalang · Gudang Knitting", "sharing_mode": "shared", "entity_ids": []},
        "RCM-PRINTING": {"name": "Rancamalang · Gudang Printing", "sharing_mode": "shared", "entity_ids": []},
        "RCM-RETUR": {"name": "Rancamalang · Gudang Retur (grade B/BS/C)", "sharing_mode": "shared", "entity_ids": [],
                      "storage_rules": {"mode": "grade", "categories": [], "grades": ["B", "BS", "C"]}},
        "SRG-01": {"name": "Soreang · Gudang Kanda", "sharing_mode": "dedicated", "entity_ids": [KANDA]},
        "WH-JKT": {"name": "Jakarta · Gudang Sukacita", "sharing_mode": "dedicated", "entity_ids": [KSC],
                   "site_id": sites.get("Jakarta", ""), "roles": ["storage"], "city": "Jakarta",
                   "storage_rules": {"mode": "none", "categories": [], "grades": []}},
    }
    out: Dict[str, str] = {}
    for code, patch in patches.items():
        wh = await db.warehouses.find_one({"code": code}, {"_id": 0, "id": 1})
        await db.warehouses.update_one({"id": wh["id"]}, {"$set": {**patch, "active": True, "updated_at": now_iso()}})
        out[code] = wh["id"]
    await _rehome_opening_stock(out, cst)
    return out


def _zones() -> List[Dict[str, Any]]:
    return [{"id": new_id("zone"), "name": "Zone A", "racks": [{"id": new_id("rack"), "name": "Rack A1",
             "bins": [{"id": new_id("bin"), "code": "A1-01", "capacity": 100000}]}]}]


def target_wh(whs: Dict[str, str], owner: str, line: str, cst: str) -> str:
    if owner == KSC:
        return whs["WH-JKT"]
    if owner == KANDA:
        return whs["SRG-01"]
    return whs[{"knit": "RCM-KNITTING", "printing": "RCM-PRINTING"}.get(line, "RCM-WOVEN")]


async def _rehome_opening_stock(whs: Dict[str, str], cst: str) -> None:
    """Stok awal yang mendarat di gudang lama (Gudang Utama <entitas>/gudang bawaan) dipindah ke struktur baru.
    Hanya untuk gudang yang BELUM punya transaksi (isinya murni stok awal); lainnya dibiarkan + diberi tahu."""
    from services import lot_service, roll_service
    keep = set(whs.values())
    old = await db.warehouses.find({"id": {"$nin": list(keep)}, "active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
    for wh in old:
        busy = await db.inventory_movements.count_documents({"warehouse_id": wh["id"], "movement_type": {"$nin": ["initial_stock", "in", "adjustment"]}})
        docs = sum([await db[c].count_documents({"warehouse_id": wh["id"]}) for c in ("purchase_orders", "sales_orders", "wms_tasks", "makloon_orders")])
        if busy or docs:
            log(f"   ! {wh['name']}: sudah dipakai transaksi — stoknya TIDAK dipindah")
            continue
        rolls = await db.inventory_rolls.find({"warehouse_id": wh["id"]}, {"_id": 0, "id": 1, "product_id": 1, "owner_entity_id": 1, "lot_id": 1}).to_list(None)
        lines = {p["id"]: p.get("line_code") or "" for p in await db.products.find(
            {"id": {"$in": list({r["product_id"] for r in rolls})}}, {"_id": 0, "id": 1, "line_code": 1}).to_list(None)}
        groups: Dict[tuple, List[str]] = {}
        for r in rolls:
            dest = target_wh(whs, r.get("owner_entity_id") or KSC, lines.get(r["product_id"], ""), cst)
            groups.setdefault((dest, r["product_id"], r.get("owner_entity_id") or KSC), []).append(r["id"])
        lot_ids = {r["lot_id"] for r in rolls if r.get("lot_id")}
        for (dest, pid, owner), ids in groups.items():
            await db.inventory_rolls.update_many({"id": {"$in": ids}}, {"$set": {"warehouse_id": dest, "bin_id": None}})
            await db.inventory_movements.update_many({"roll_id": {"$in": ids}}, {"$set": {"warehouse_id": dest}})
        await db.inventory_lots.update_many({"id": {"$in": list(lot_ids)}, "warehouse_id": wh["id"]},
                                            {"$set": {"warehouse_id": next(iter(groups))[0] if groups else wh["id"]}})
        for lid in lot_ids:
            r0 = await db.inventory_rolls.find_one({"lot_id": lid}, {"_id": 0, "warehouse_id": 1})
            if r0:
                await db.inventory_lots.update_one({"id": lid}, {"$set": {"warehouse_id": r0["warehouse_id"]}})
        await db.inventory_balances.delete_many({"warehouse_id": wh["id"]})
        for (dest, pid, owner) in groups:
            await roll_service.rebuild_balance(pid, dest, owner)
        if lot_ids:
            await lot_service.recompute_many(list(lot_ids))
        await db.warehouses.update_one({"id": wh["id"]}, {"$set": {"active": False, "updated_at": now_iso(),
                                       "deactivated_reason": "Diganti struktur gudang Rancamalang/Soreang/Jakarta (Demo Lengkap)"}})
        log(f"   ~ {wh['name']}: {len(rolls)} roll dipindah ke struktur baru · gudang lama dinonaktifkan")


# ─── 3. Akun semua peran (sandi demo1234) ────────────────────────────────────────────────────────────────
def accounts(cst: str) -> List[Dict[str, Any]]:
    allx = [KSC, KANDA, cst]
    return [
        {"email": "md" + MAIL, "name": "Hendra Wijaya", "role": "md", "home": KSC, "allowed": allx},
        {"email": "manager" + MAIL, "name": "Dewi Rahayu", "role": "manager", "home": KSC, "allowed": allx},
        {"email": "finance" + MAIL, "name": "Sri Mulyani", "role": "finance", "home": KSC, "allowed": allx},
        {"email": "salesadmin" + MAIL, "name": "Rina Kartika", "role": "sales_admin", "home": KSC, "allowed": [KSC]},
        {"email": "salesadmin.kanda" + MAIL, "name": "Yuni Astuti", "role": "sales_admin", "home": KANDA, "allowed": [KANDA]},
        {"email": "salesadmin.cst" + MAIL, "name": "Nadia Putri", "role": "sales_admin", "home": cst, "allowed": [cst]},
        {"email": "sales" + MAIL, "name": "Ayu Permatasari", "role": "sales", "home": KSC, "allowed": [KSC]},
        {"email": "sales2" + MAIL, "name": "Bima Saputra", "role": "sales", "home": KSC, "allowed": [KSC]},
        {"email": "sales.kanda" + MAIL, "name": "Citra Lestari", "role": "sales", "home": KANDA, "allowed": [KANDA]},
        {"email": "sales.cst" + MAIL, "name": "Dimas Prakoso", "role": "sales", "home": cst, "allowed": [cst]},
        {"email": "warehouse" + MAIL, "name": "Eko Prasetyo", "role": "warehouse", "home": KSC, "allowed": [KSC]},
        {"email": "warehouse.soreang" + MAIL, "name": "Fajar Nugroho", "role": "warehouse", "home": KANDA, "allowed": [KANDA]},
        {"email": "warehouse.rancamalang" + MAIL, "name": "Gilang Ramadhan", "role": "warehouse", "home": cst, "allowed": allx},
        {"email": "whadmin" + MAIL, "name": "Hana Safitri", "role": "warehouse_admin", "home": cst, "allowed": allx},
        {"email": "designer" + MAIL, "name": "Intan Maharani", "role": "designer", "home": KSC, "allowed": allx},
        {"email": "sampleadmin" + MAIL, "name": "Joko Santoso", "role": "sample_admin", "home": KSC, "allowed": allx},
        {"email": "driver" + MAIL, "name": "Kurniawan", "role": "driver", "home": KSC, "allowed": allx},
    ]


async def seed_users(sys_admin, cst: str) -> None:
    made = reset = 0
    for a in accounts(cst):
        ex = await db.users.find_one({"email": a["email"]}, {"_id": 0, "id": 1})
        if not ex:
            await sys_admin.post("/users", {"name": a["name"], "email": a["email"], "role": a["role"], "password": DEMO_PASSWORD,
                                            "phone": f"0812{random.Random(a['email']).randint(10000000, 99999999)}",
                                            "home_entity_id": a["home"], "allowed_entity_ids": a["allowed"]})
            made += 1
        await db.users.update_one({"email": a["email"]}, {"$set": {
            "role": a["role"], "status": "active", "home_entity_id": a["home"], "allowed_entity_ids": a["allowed"],
            "password_hash": hash_password(DEMO_PASSWORD), "must_change_password": False, "demo_batch": BATCH,
            "updated_at": now_iso()}})
        reset += 1 if ex else 0
    await db.login_attempts.delete_many({})
    log(f"   + akun baru {made} · akun lama diseragamkan sandinya {reset} (semua: {DEMO_PASSWORD})")


# ─── 4. Mitra: supplier, makloon + kontrak tarif, customer, rekening bank, target sales ────────────────────
SUPPLIERS = [
    ("PT Benang Sejahtera Abadi", "benang", "Bandung", "NET30", 7),
    ("PT Indo Spinning Mills", "benang", "Karawang", "NET30", 10),
    ("CV Grey Mandiri Majalaya", "kain grey", "Bandung", "NET14", 7),
    ("PT Kain Jadi Nusantara", "kain jadi", "Jakarta", "NET30", 14),
    ("PT Kimia Warna Prima", "bahan pembantu celup/printing", "Bekasi", "NET30", 5),
]
MAKLOONS = [
    ("CV Tenun Rancaekek", ["tenun"], "Bandung", "meter", 1800, "meter"),
    ("PT Rajut Cigondewah", ["rajut"], "Bandung", "kg", 6500, "kg"),
    ("PT Celup Warna Dayeuhkolot", ["pre_treatment", "celup", "finishing"], "Bandung", "kg", 9500, "kg"),
    ("CV Printing Sablon Cimahi", ["pre_treatment", "screen", "printing"], "Cimahi", "yard", 4500, "yard"),
]
CUSTOMERS = [
    ("Toko Kain Sejahtera", "Pak Haris", "Bandung", "Wholesale", 250_000_000, "sales"),
    ("Konveksi Maju Bersama", "Bu Lina", "Bandung", "Distributor", 400_000_000, "sales2"),
    ("Butik Bali Indah", "Ibu Komang", "Denpasar", "Retail", 75_000_000, "sales"),
    ("CV Garmen Soreang Jaya", "Pak Ujang", "Kabupaten Bandung", "Wholesale", 25_000_000, "sales.kanda"),
    ("Toko Tekstil Pasar Baru", "Ko Ahong", "Bandung", "Retail", 120_000_000, "sales.kanda"),
    ("PT Fashion Ibukota", "Bu Sinta", "Jakarta", "VIP", 600_000_000, "sales.cst"),
    ("Konveksi Tanah Abang Makmur", "Pak Rudi", "Jakarta", "Distributor", 350_000_000, "sales.cst"),
]


async def seed_partners(sys_admin, cst: str) -> None:
    n = 0
    for name, goods, city, term, lead in SUPPLIERS:
        if await db.suppliers.find_one({"name": name}, {"_id": 1}):
            continue
        await sys_admin.post("/suppliers", {"name": name, "goods_type": goods, "city": city, "address": f"Kawasan Industri {city}",
                                            "pic_name": "Bagian Penjualan", "phone": "0221234567", "payment_term_code": term,
                                            "lead_time_days": lead, "entity_id": "all", "origin_type": "local",
                                            "notes": "Supplier demo"}, entity=KSC)
        n += 1
    log(f"   + supplier baru {n}")
    n = 0
    for name, procs, city, cap_unit, tariff, t_unit in MAKLOONS:
        if await db.makloons.find_one({"name": name}, {"_id": 1}):
            continue
        mk = await sys_admin.post("/makloons", {"name": name, "process_types": procs, "city": city, "address": f"Jl. Industri {city}",
                                                "pic_name": "Kepala Produksi", "phone": "0227654321", "capacity_per_month": 50000,
                                                "capacity_unit": cap_unit, "default_tariff": tariff, "tariff_unit": "output",
                                                "payment_term_code": "NET30", "lead_time_days": 10, "entity_id": "all"}, entity=KSC)
        for p in procs:
            await sys_admin.post("/supplier-contracts", {
                "contract_type": "makloon", "partner_id": mk["id"], "partner_name": name, "title": f"Kontrak {p} {name}",
                "process_type": p, "tariff_basis": t_unit if t_unit in ("kg", "meter", "yard") else "lumpsum",
                "tariff_rate": tariff, "tariff_qty_source": "output", "shrinkage_pct": 3 if p in ("celup", "pre_treatment") else 2,
                "tolerance_pct": 3, "lead_time_days": 10, "payment_term_code": "NET30", "status": "active",
                "notes": "Kontrak demo"}, entity=KSC)
        n += 1
    log(f"   + makloon baru {n} (beserta kontrak tarif tiap proses)")
    sales = {u["email"].split("@")[0]: u for u in await db.users.find({"role": "sales"}, {"_id": 0, "id": 1, "email": 1, "home_entity_id": 1}).to_list(50)}
    n = 0
    for i, (name, pic, city, seg, limit, s_key) in enumerate(CUSTOMERS):
        if await db.customers.find_one({"name": name}, {"_id": 1}):
            continue
        s = sales[s_key]
        await sys_admin.post("/customers", {"name": name, "pic_name": pic, "phone": f"08133{i:03d}4455", "city": city,
                                            "address": f"Jl. Perdagangan No. {10 + i}, {city}", "type": seg, "segment": seg,
                                            "credit_limit": limit, "assigned_sales_id": s["id"], "entity_id": s["home_entity_id"],
                                            "payment_profile": {"default_method": "tempo", "term_days": 30}}, entity=s["home_entity_id"])
        n += 1
    log(f"   + customer baru {n} (plafon kredit & PIC sales)")
    n = 0
    for eid in (KSC, KANDA, cst):
        if await db.bank_accounts.count_documents({"entity_id": eid, "demo_batch": BATCH}):
            continue
        ent = await db.business_entities.find_one({"id": eid}, {"_id": 0, "doc_prefix": 1})
        for nm, bank, typ, bal in ((f"BCA Operasional {ent['doc_prefix']}", "BCA", "bank", 750_000_000),
                                   (f"Kas Toko {ent['doc_prefix']}", "", "cash", 25_000_000)):
            acc = await sys_admin.post("/bank-accounts", {"name": nm, "account_type": typ, "bank_name": bank,
                                                          "account_number": f"{random.Random(nm).randint(1000000000, 9999999999)}" if bank else "",
                                                          "entity_id": eid, "opening_balance": bal, "note": "Rekening demo"}, entity=eid)
            await db.bank_accounts.update_one({"id": acc["id"]}, {"$set": {"demo_batch": BATCH}})
            n += 1
    log(f"   + rekening kas/bank baru {n}")
    from datetime import datetime, timezone
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    n = 0
    for s in sales.values():
        if await db.sales_targets.find_one({"sales_id": s["id"], "period": period}, {"_id": 1}):
            continue
        await sys_admin.post("/sales-targets", {"sales_id": s["id"], "entity_id": s.get("home_entity_id") or KSC, "period_type": "month",
                                                "period": period, "target_sales_amount": 500_000_000, "target_collection_amount": 350_000_000,
                                                "target_new_customers": 3, "notes": "Target demo"}, entity=s.get("home_entity_id") or KSC)
        n += 1
    log(f"   + target sales bulan {period}: {n}")


# ─── 5. Produk semua tahap bahan (benang → grey → PFD/PFP → jadi, + sisa & hasil samping) ──────────────────
STAGE_PRODUCTS = [
    # sku, nama, stage, fabric, line, unit, extra
    ("DMO-YRN-WVN-30S", "Benang Katun 30s (untuk Tenun)", "yarn", "woven", "woven", "kg",
     {"yarn_count": "30s", "yarn_count_system": "Ne", "yarn_material": "katun", "yarn_ply": "1", "yarn_twist": "Z", "yarn_dye_status": "raw", "price": 52000}),
    ("DMO-YRN-KNT-30S", "Benang Cotton Combed 30s (untuk Rajut)", "yarn", "knit", "knit", "kg",
     {"yarn_count": "30s", "yarn_count_system": "Ne", "yarn_material": "katun", "yarn_ply": "1", "yarn_twist": "Z", "yarn_dye_status": "raw", "price": 58000}),
    ("DMO-GRY-WVN-001", "Grey Woven Katun Poplin", "grey", "woven", "woven", "yard", {"gramasi": 110, "lebar": 1.5, "price": 14000}),
    ("DMO-GRY-KNT-001", "Grey Knit Single Jersey 30s", "grey", "knit", "knit", "kg", {"gramasi": 150, "lebar": 1.8, "price": 68000}),
    ("DMO-PFD-WVN-001", "PFD Woven Katun Poplin (siap celup)", "pfd", "woven", "woven", "yard", {"gramasi": 108, "lebar": 1.48, "price": 16500}),
    ("DMO-PFD-KNT-001", "PFD Knit Single Jersey (siap celup)", "pfd", "knit", "knit", "kg", {"gramasi": 148, "lebar": 1.78, "price": 74000}),
    ("DMO-PFP-WVN-001", "PFP Woven Katun Poplin (siap print)", "pfp", "woven", "printing", "yard", {"gramasi": 108, "lebar": 1.48, "price": 17000}),
    ("DMO-RMN-WVN-001", "Sisa Potongan / Perca Woven Campur", "remnant", "woven", "woven", "kg", {"price": 15000}),
    ("DMO-BYP-YRN-001", "Hasil Samping Waste Benang", "byproduct", "knit", "knit", "kg", {"price": 6000}),
]


async def seed_stage_products(sys_admin, cst: str) -> List[Dict[str, Any]]:
    out, n = [], 0
    for sku, name, stage, fabric, line, unit, extra in STAGE_PRODUCTS:
        ex = await db.products.find_one({"sku": sku}, {"_id": 0})
        if not ex:
            price = extra.get("price", 0)
            body = {"sku": sku, "name": name, "category": {"woven": "Woven", "knit": "Knitting", "printing": "Printing"}[line],
                    "variant": "Standar", "color": "Natural", "motif": "Polos", "grade": "A", "stage": stage,
                    "fabric_type": fabric, "line_code": line, "base_unit": unit, "supplier": "Internal",
                    "harga_pokok": round(price * 0.8), "description": f"Bahan demo tahap {stage}",
                    **{k: v for k, v in extra.items() if k != "price"}, "price": price,
                    "uom_conversions": [{"from_unit": "roll", "to_unit": unit, "factor": 25 if unit == "kg" else 50}]}
            ex = await sys_admin.post("/products", body, entity=KSC)
            n += 1
        cost = round(extra.get("price", 0) * 0.8)
        await db.products.update_one({"id": ex["id"]}, {"$set": {"entity_ids": [KSC, KANDA, cst], "demo_batch": BATCH,
                                                              "harga_pokok": cost, "cost_price": cost}})
        await db.inventory_rolls.update_many({"product_id": ex["id"], "acquired.ref_id": REF, "unit_cost": None},
                                             {"$set": {"unit_cost": cost, "base_unit_cost": cost}})
        out.append(ex)
    log(f"   + produk tahap bahan baru {n} (benang, grey, PFD, PFP, sisa, hasil samping)")
    return out


async def seed_stage_stock(whs: Dict[str, str], cst: str) -> None:
    from services import gl_service, lot_service, roll_service
    from scripts.import_stok_awal_kn import reserve_roll_numbers
    plan = []
    for sku, _n, stage, _f, line, unit, _e in STAGE_PRODUCTS:
        prod = await db.products.find_one({"sku": sku}, {"_id": 0})
        for owner in (cst, KSC, KANDA):
            if await db.inventory_rolls.find_one({"product_id": prod["id"], "owner_entity_id": owner, "acquired.ref_id": REF}, {"_id": 1}):
                continue
            rnd = random.Random(sku + owner)
            n = rnd.randint(40, 80) if owner == cst else rnd.randint(15, 30)
            base = 25.0 if unit == "kg" else 50.0
            plan.append((prod, owner, target_wh(whs, owner, line, cst), [round(base * rnd.uniform(0.95, 1.05), 2) for _ in range(n)], "A"))
    # Gudang Retur Rancamalang (shared): roll kain jadi grade di bawah A (B/BS/C) milik ketiga entitas.
    for owner in (cst, KSC, KANDA):
        if await db.inventory_rolls.find_one({"owner_entity_id": owner, "warehouse_id": whs["RCM-RETUR"], "acquired.ref_id": REF}, {"_id": 1}):
            continue
        fins = await db.products.find({"import_batch": "MIGRASI_MASTER_PRODUK_KN", "entity_ids": owner}, {"_id": 0}).sort("sku", 1).to_list(4)
        for i, prod in enumerate(fins):
            rnd = random.Random(prod["sku"] + owner + "retur")
            base = 25.0 if prod.get("base_unit") == "kg" else 50.0
            plan.append((prod, owner, whs["RCM-RETUR"], [round(base * rnd.uniform(0.4, 0.9), 2) for _ in range(rnd.randint(4, 8))],
                         ("B", "BS", "C", "B")[i]))
    if not plan:
        gl = await gl_service.post_inventory_opening_balance(actor_name="Demo Lengkap", reason="Stok awal demo tahap bahan")
        log(f"   = stok tahap bahan sudah ada — dilewati (true-up jurnal {len(gl.get('posted') or [])} entitas)")
        return
    numbers = iter(await reserve_roll_numbers(sum(len(p[3]) for p in plan)))
    lot_ids, keys, total = set(), set(), 0
    for prod, owner, wid, lens, grade in plan:
        ent = await db.business_entities.find_one({"id": owner}, {"_id": 0, "doc_prefix": 1})
        code = f"DM-{prod['sku'][4:]}-{ent['doc_prefix']}" if grade == "A" else f"RT-{prod['sku'][-14:]}-{ent['doc_prefix']}-{grade}"
        lot = await lot_service.resolve_or_create(
            product_id=prod["id"], owner_entity_id=owner, warehouse_id=wid, lot_code=code,
            source="migration", source_ref={"type": "initial", "id": REF, "number": "Stok awal demo"}, status="released", actor="Demo Lengkap")
        lot_ids.add(lot["id"])
        cost = round(float(prod.get("harga_pokok") or 0) * (1 if grade == "A" else 0.6), 4)
        rolls, moves = [], []
        for ln in lens:
            rid, ts = new_id("roll"), now_iso()
            rolls.append({"id": rid, "product_id": prod["id"], "owner_entity_id": owner, "ownership_type": "internal", "consignor_ref": None,
                          "warehouse_id": wid, "bin_id": None, "lot": lot["lot_number"], "lot_id": lot["id"], "supplier_lot": "",
                          "dye_lot": lot["lot_number"], "batch": "DM-AWAL", "roll_no": next(numbers), "length_initial": ln,
                          "length_remaining": ln, "unit": prod.get("base_unit"), **roll_service._domain_snapshot(prod), "grade": grade,
                          "status": "available", "tracking_mode": "barcode", "earmarked_for": None, "secondary_measures": None,
                          "location_type": "warehouse_bin", "reserved_ref": None, "base_unit_cost": cost, "unit_cost": cost or None,
                          "landed_cost_total": 0.0, "acquired": {"via": "initial", "ref_id": REF, "date": ts}, "rfid_tag_id": None,
                          "is_remnant": prod.get("stage") == "remnant", "created_at": ts, "updated_at": ts, "created_by": "Demo Lengkap",
                          "created_by_name": "Demo Lengkap", "defects": [], "landed_cost_refs": []})
            moves.append({"id": new_id("mov"), "product_id": prod["id"], "warehouse_id": wid, "owner_entity_id": owner,
                          "movement_type": "initial_stock", "quantity": ln, "unit": prod.get("base_unit"), "lot": lot["lot_number"],
                          "lot_id": lot["id"], "batch": "DM-AWAL", "roll_id": rid, "qty_rolls": 1, "source_document": REF,
                          "notes": "Stok awal demo (tahap bahan)" if grade == "A" else f"Stok retur demo grade {grade}", "created_by": "Demo Lengkap", "timestamp": ts})
        await db.inventory_rolls.insert_many(rolls)
        await db.inventory_movements.insert_many(moves)
        keys.add((prod["id"], wid, owner))
        total += len(rolls)
    await lot_service.recompute_many(list(lot_ids))
    for key in keys:
        await roll_service.rebuild_balance(*key)
    gl = await gl_service.post_inventory_opening_balance(actor_name="Demo Lengkap", reason="Stok awal demo tahap bahan")
    log(f"   + stok tahap bahan: {total} roll · {len(lot_ids)} lot · jurnal saldo awal {len(gl.get('posted') or [])} entitas")


async def main() -> None:
    if not await db.products.count_documents({"import_batch": "MIGRASI_MASTER_PRODUK_KN"}):
        sys.exit("Master produk asli belum diimpor — jalankan dulu deploy/setup_vps_ai_import.sh (atau import_master_produk_kn.py).")
    cst = await cst_id()
    api = Api()
    try:
        sys_admin = await api.system_admin()
        log("1/5 Master referensi (warna, lini produk, tahapan proses, jenis sampel, alasan keluhan, motif)")
        await seed_reference_masters()
        log("2/5 Struktur gudang: Rancamalang (Transit, Woven, Knitting, Printing, Retur) · Soreang (Kanda) · Jakarta (Sukacita)")
        whs = await seed_warehouses(sys_admin, cst)
        log("3/5 Akun semua peran")
        await seed_users(sys_admin, cst)
        log("4/5 Supplier, makloon + kontrak, customer, rekening, target sales")
        await seed_partners(sys_admin, cst)
        log("5/5 Produk & stok semua tahap bahan")
        await seed_stage_products(sys_admin, cst)
        await seed_stage_stock(whs, cst)
        await db.migrations.update_one({"id": "demo_lengkap_master"}, {"$set": {"applied_at": now_iso(), "batch": BATCH}}, upsert=True)
        log("SELESAI tahap 1 (master & stok demo).")
    except ApiError as e:
        sys.exit(f"GAGAL: {e}")
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
