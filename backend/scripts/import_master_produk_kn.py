"""Inject master produk KN dari Excel migrasi (sheet PRODUK + VARIAN) → product_templates + products + entity_prices.

Pengkodean: induk = KODE_ARTIKEL (KN + KNT/WVN/PRT + 4 digit); varian = SKU 25 karakter
ARTIKEL-ASAL-WARNA-GRADE-CUSTOMER-LOT (sumbu induk: origin, color, grade, customer, lot).
Harga MOCK (deterministik per SKU): woven/printing Rp 18.000–25.000/yard · knitting Rp 40.000–45.000/kg.
Idempoten: dijalankan ulang = memperbarui, bukan menduplikasi.

Pakai (dari folder backend):
  python scripts/import_master_produk_kn.py [path.xlsx] [--dry-run]
VPS (docker):
  docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec backend \
      python scripts/import_master_produk_kn.py
"""
import asyncio
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import openpyxl  # noqa: E402

import domain_registry as dr  # noqa: E402
from core_utils import new_id, now_iso  # noqa: E402
from db import db  # noqa: E402
from services import catalog_rules  # noqa: E402

DEFAULT_XLSX = ROOT / "data" / "import" / "TEST_MIGRASI_MASTER_PRODUK.xlsx"
BATCH = "MIGRASI_MASTER_PRODUK_KN"
LINE = {"KNITTING": "knit", "WOVEN": "woven", "PRINTING": "printing"}
FABRIC = {"KNITTING": "knit", "WOVEN": "woven", "PRINTING": "woven"}
ORIGIN = {"L": ("Lokal", "lokal"), "I": ("Impor", "impor"), "X": ("Belum diketahui", "")}
ENTITY_COLS = {"ENTITAS_CST": "Cipta Sandang", "ENTITAS_KANDA": "Kanda", "ENTITAS_SUKACITA": "Sukacita"}
AXIS_LABEL = {"origin": "Asal", "color": "Warna", "grade": "Grade", "customer": "Kode Customer", "lot": "Lot"}


def rows(ws) -> List[Dict[str, Any]]:
    it = ws.iter_rows(values_only=True)
    head = [str(h).strip() if h else "" for h in next(it)]
    return [dict(zip(head, r)) for r in it if r and r[0]]


def s(v: Any) -> str:
    return "" if v is None else str(v).strip()


def num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def mock_price(sku: str, unit: str) -> float:
    lo, hi = (40, 45) if unit == "kg" else (18, 25)
    return float(random.Random(sku).randint(lo, hi) * 1000)


async def entity_map() -> Dict[str, str]:
    out = {}
    async for e in db.business_entities.find({}, {"_id": 0, "id": 1, "name": 1, "short_name": 1, "legal_name": 1}):
        label = f"{e.get('short_name', '')} {e.get('name', '')} {e.get('legal_name', '')}".lower().replace(" ", "")
        for col, key in ENTITY_COLS.items():
            if key.lower().replace(" ", "") in label:
                out[col] = e["id"]
    return out


def variant_codes(v: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    art, asal, warna, grade, cust, lot = s(v["SKU"]).upper().split("-")
    return {
        "origin": {"code": asal, "label": ORIGIN[asal][0], "value": ORIGIN[asal][1]},
        "color": {"code": warna, "label": s(v["WARNA"]) or warna, "value": s(v.get("KODE_WARNA"))},
        "grade": {"code": grade, "label": s(v["GRADE"]).upper() or grade.lstrip("X"), "value": s(v["GRADE"]).upper()},
        "customer": {"code": cust, "label": s(v.get("KODE_CUSTOMER")) or "Tidak ada", "value": s(v.get("KODE_CUSTOMER"))},
        "lot": {"code": lot, "label": f"LOT {s(v.get('LOT'))}" if s(v.get("LOT")) else "Tidak ada", "value": s(v.get("LOT"))},
    }


def build_axes(variants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    axes = []
    for key in ("origin", "color", "grade", "customer", "lot"):
        opts: Dict[str, Dict[str, str]] = {}
        labels = set()
        for v in variants:
            o = dict(v["_codes"][key])
            if o["code"] in opts:
                continue
            if o["label"].casefold() in labels:   # label kembar dengan kode beda → bedakan dengan kodenya
                o["label"] = f"{o['label']} ({o['code']})"
            labels.add(o["label"].casefold())
            opts[o["code"]] = {**o, "hex": ""}
            v["_codes"][key] = o
        axes.append({"key": key, "label": AXIS_LABEL[key], "options": list(opts.values())})
    return catalog_rules.normalize_axes(axes)


async def ensure_categories() -> None:
    for code, unit in (("KNITTING", "kg"), ("WOVEN", "yard"), ("PRINTING", "yard")):
        await db.product_categories.update_one({"code": code}, {"$setOnInsert": {
            "id": new_id("cat"), "code": code, "name": code.title(), "base_unit": unit,
            "description": f"Kategori kain {code.title()} (master produk KN)", "sort_order": 0, "status": "active",
            "created_at": now_iso(), "updated_at": now_iso()}}, upsert=True)


def template_doc(p: Dict[str, Any], axes, base_price: float) -> Dict[str, Any]:
    kat = s(p["KATEGORI"]).upper()
    doc = {
        "name": s(p["NAMA_ARTIKEL"]), "category": kat.title(), "fabric_type": FABRIC[kat], "line_code": LINE[kat],
        "motif": "Print" if kat == "PRINTING" else "Polos", "stage": "finished", "base_unit": s(p["SATUAN"]).lower(),
        "base_price": base_price, "harga_pokok": round(base_price * 0.72), "gramasi": num(p.get("GRAMASI_MAX")) or num(p.get("GRAMASI_MIN")),
        "gramasi_min": num(p.get("GRAMASI_MIN")), "gramasi_max": num(p.get("GRAMASI_MAX")),
        "lebar": round(num(p.get("LEBAR_CM")) / 100, 4), "lebar_inch": num(p.get("LEBAR_INCH")),
        "qty_per_roll": num(p.get("QTY_PER_ROLL")),
        "origin": "" if "ASAL" in s(p.get("STATUS_DATA")).upper() else ORIGIN[{"LOKAL": "L", "IMPOR": "I"}.get(s(p.get("ASAL")).upper(), "X")][1],
        "supplier": "Internal", "sku_prefix": s(p["KODE_ARTIKEL"]).upper(), "axes": axes,
        "exclusivity": "umum", "owner_sales_ids": [], "status": "active", "image": "", "description": "",
        "import_batch": BATCH, "source_name": s(p.get("NAMA_KAIN_ASLI")), "data_status": s(p.get("STATUS_DATA")),
        "yarn_count": "", "yarn_count_system": "", "updated_at": now_iso(),
    }
    dr.apply_normalization(doc)
    return doc


def product_doc(tpl: Dict[str, Any], v: Dict[str, Any]) -> Dict[str, Any]:
    c = v["_codes"]
    unit = s(v["SATUAN"]).lower()
    price = mock_price(s(v["SKU"]).upper(), unit)
    extra = [o["label"] for k, o in c.items() if k in ("customer", "lot") and o["code"] != "XX"]
    qpr = num(v.get("QTY_PER_ROLL"))
    review = s(v.get("STATUS_DATA")).upper() != "OK"
    prod = {
        "sku": s(v["SKU"]).upper(), "name": " ".join([tpl["name"], c["color"]["label"], c["grade"]["label"], *extra]),
        "category": tpl["category"], "variant": s(v.get("NAMA_VARIAN")) or c["color"]["label"],
        "variant_label": " · ".join([c["origin"]["label"], c["color"]["label"], c["grade"]["label"], *extra]),
        "motif": tpl["motif"], "stage": "finished", "fabric_type": tpl["fabric_type"], "line_code": tpl["line_code"],
        "yarn_count": "", "yarn_count_system": "", "supplier": "Internal", "base_unit": unit,
        "price": price, "harga_pokok": round(price * 0.72), "gramasi": tpl["gramasi"], "gramasi_min": tpl["gramasi_min"],
        "gramasi_max": tpl["gramasi_max"], "lebar": round(num(v.get("LEBAR_CM")) / 100, 4), "lebar_inch": num(v.get("LEBAR_INCH")),
        "kg_per_meter": 0, "reorder_point": 0, "reorder_qty": 0, "image": "", "description": "", "media": [], "media_revision": 0,
        "lifecycle": "produksi", "exclusivity": "umum", "owner_sales_ids": [], "status": "active",
        "uom_conversions": [{"from_unit": "roll", "to_unit": unit, "factor": qpr}] if qpr else [],
        "template_id": tpl["id"], "template_name": tpl["name"], "catalog_version": 2,
        "variant_attrs": {k: o["label"] for k, o in c.items()}, "variant_options": {k: o["code"] for k, o in c.items()},
        "customer_code": c["customer"]["value"], "lot_code": c["lot"]["value"], "color_initial": c["color"]["code"],
        "legacy_sku": s(v.get("SKU_LAMA")), "source_name": s(v.get("NAMA_KAIN_ASLI")), "source_color": s(v.get("WARNA_ASLI")),
        "source_file": s(v.get("SUMBER_FILE")), "data_status": s(v.get("STATUS_DATA")),
        "import_batch": BATCH, "batch_lot_rolls": [], "updated_at": now_iso(),
    }
    catalog_rules.combination(tpl, prod)
    dr.apply_normalization(prod)
    prod["variant_label"] = " · ".join([c["origin"]["label"], c["color"]["label"], c["grade"]["label"], *extra])
    check = dr.validate_product(prod)
    # Printing di sumber belum punya lebar/gramasi → tetap diimpor, ditandai perlu dilengkapi (bukan ditolak).
    soft = [e for e in check["errors"] if e.startswith(("Gramasi", "Lebar"))]
    if check["errors"] != soft:
        raise ValueError(f"{prod['sku']}: " + " ".join(e for e in check["errors"] if e not in soft))
    if soft:
        check["needs_review"] = True
        check["needs_review_reasons"] = check["needs_review_reasons"] + ["Lebar/gramasi belum ada di data sumber — lengkapi di master"]
    prod["needs_review"] = review or check["needs_review"]
    prod["needs_review_reasons"] = (["Asal (lokal/impor) belum dikonfirmasi"] if review else []) + check["needs_review_reasons"]
    return prod


async def main(path: Path, dry: bool) -> None:
    wb = openpyxl.load_workbook(path, data_only=True)
    produk, varian = rows(wb["PRODUK"]), rows(wb["VARIAN"])
    ents = await entity_map()
    by_art: Dict[str, List[Dict[str, Any]]] = {}
    for v in varian:
        v["_codes"] = variant_codes(v)
        by_art.setdefault(s(v["KODE_ARTIKEL"]).upper(), []).append(v)
    if not dry:
        await ensure_categories()
    stats = {"templates_new": 0, "templates_upd": 0, "products_new": 0, "products_upd": 0, "prices": 0}
    for p in produk:
        art = s(p["KODE_ARTIKEL"]).upper()
        vs = by_art.get(art, [])
        if not vs:
            print(f"!! {art} tanpa varian — dilewati")
            continue
        axes = build_axes(vs)
        unit = s(p["SATUAN"]).lower()
        tdoc = template_doc(p, axes, min(mock_price(s(v["SKU"]).upper(), unit) for v in vs))
        old = await db.product_templates.find_one({"sku_prefix": art}, {"_id": 0, "id": 1})
        tdoc["id"] = old["id"] if old else new_id("ptpl")
        prods = [product_doc(tdoc, v) for v in vs]
        flags = [ents[col] for col in ENTITY_COLS if s(p.get(col)).upper() == "Y" and col in ents]
        tdoc["entity_ids"] = flags
        if dry:
            print(f"{art} {tdoc['name']}: {len(prods)} varian · entitas {flags} · contoh {prods[0]['sku']} Rp {prods[0]['price']:,.0f}/{unit}")
            continue
        if old:
            await db.product_templates.update_one({"id": old["id"]}, {"$set": tdoc})
            stats["templates_upd"] += 1
        else:
            await db.product_templates.insert_one({**tdoc, "created_by": "Import Master Produk", "created_at": now_iso()})
            stats["templates_new"] += 1
        for prod in prods:
            prod["entity_ids"] = flags
            ex = await db.products.find_one({"sku": prod["sku"]}, {"_id": 0, "id": 1, "import_batch": 1})
            if ex and ex.get("import_batch") != BATCH:
                raise ValueError(f"SKU {prod['sku']} sudah dipakai produk lain (bukan hasil impor ini).")
            if ex:
                await db.products.update_one({"id": ex["id"]}, {"$set": prod})
                prod["id"] = ex["id"]
                stats["products_upd"] += 1
            else:
                prod.update(id=new_id("prod"), created_at=now_iso())
                await db.products.insert_one(dict(prod))
                stats["products_new"] += 1
            for eid in flags:
                await db.entity_prices.update_one({"entity_id": eid, "product_id": prod["id"]}, {"$set": {
                    "sku": prod["sku"], "product_name": prod["name"], "sell_price": prod["price"], "currency": "IDR",
                    "is_listed": True, "status": "active", "note": "Harga MOCK migrasi master produk", "updated_at": now_iso(),
                    "import_batch": BATCH}, "$setOnInsert": {"id": new_id("epr"), "valid_from": now_iso(), "valid_until": "",
                                                              "created_by": "Import Master Produk", "created_at": now_iso()}}, upsert=True)
                stats["prices"] += 1
    total = await db.products.count_documents({"import_batch": BATCH})
    print(f"{'DRY-RUN · ' if dry else ''}{len(produk)} artikel · {len(varian)} varian di Excel · {stats} · total produk batch di DB: {total}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main(Path(args[0]) if args else DEFAULT_XLSX, "--dry-run" in sys.argv))
