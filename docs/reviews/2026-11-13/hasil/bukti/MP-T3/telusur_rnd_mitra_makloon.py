"""Telusur R&D → master produk → kontrak → pengadaan (MongoDB asli lokal, backend 8001). Data uji lokal berawalan AUD."""
import json
import os
import sys
import uuid

import requests
from pymongo import MongoClient

BASE = "http://localhost:8001/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
KSC = "ent_ksc"
T = uuid.uuid4().hex[:5].upper()
TYPE = sys.argv[1] if len(sys.argv) > 1 else "proofing"


def login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": KSC}


def call(h, m, path, **kw):
    r = requests.request(m, f"{BASE}{path}", headers=h, timeout=60, **kw)
    body = r.text
    print(f"  {m} {path.split('?')[0]} → {r.status_code}" + ("" if r.ok else f"  {body[:360]}"))
    return r


def short(d, keys):
    return {k: d.get(k) for k in keys if k in d}


adm = login("admin@kainnusantara.id")
md = login("md@kainnusantara.id")
print(f"=== Telusur R&D jenis {TYPE} (tag {T}) ===")
spec = {"title": f"Audit {TYPE} {T}", "category": "Kain", "base_unit": "yard", "line_code": "printing" if TYPE == "proofing" else "woven",
        "sample_type_hint": TYPE, "sku_hint": f"AUD-RND-{T}",
        "target": {"stage": "finished", "fabric_type": "woven", "gramasi": 120, "lebar": 150}}
body = {"spec": spec, "sample_types": [TYPE], "title": f"Audit {TYPE} {T}", "qty_requested": 5, "unit": "yard",
        "brief": "uji telusur end-to-end"}
if TYPE == "labdip":
    body["color_target"] = {"name": "Biru Audit", "hex": "#1F4E99", "pantone_code": "19-4052 TCX"}
    body["chain_override_reason"] = "uji telusur tanpa handfeel"
if TYPE == "proofing":
    import base64
    print("0a) Desain: buat → unggah PNG cetak → ajukan → ACC")
    r = call(md, "POST", "/design-gallery", json={"title": f"Motif Audit {T}", "code": f"AUD-DSG-{T}", "line_code": "printing",
                                                   "story": "uji telusur", "repeat_cm": 64, "color_count": 4})
    if not r.ok:
        r = call(adm, "POST", "/design-gallery", json={"title": f"Motif Audit {T}", "code": f"AUD-DSG-{T}", "line_code": "printing",
                                                        "story": "uji telusur", "repeat_cm": 64, "color_count": 4})
    gid = r.json().get("id") if r.ok else None
    import io
    from PIL import Image
    _b = io.BytesIO(); Image.new("RGB", (640, 640), (31, 78, 153)).save(_b, format="PNG"); png = _b.getvalue()
    if gid:
        rr = requests.post(f"{BASE}/design-gallery/{gid}/files", headers=md, files={"file": (f"motif_{T}.png", png, "image/png")})
        print("  POST files →", rr.status_code, "" if rr.ok else rr.text[:300])
        call(md, "POST", f"/design-gallery/{gid}/submit", json={"note": "siap dinilai"})
        r2 = call(adm, "POST", f"/design-gallery/{gid}/approve", json={"note": "ACC", "score": 1.5})
        for kind, fn, ct in (("mockup", f"mockup_{T}.png", "image/png"), ("source", f"asli_{T}.png", "image/png"),
                             ("print_png", f"cetak_{T}.png", "image/png")):
            rr = requests.post(f"{BASE}/design-gallery/{gid}/files-kind/{kind}", headers=md, files={"file": (fn, png, ct)})
            print(f"  POST files-kind/{kind} →", rr.status_code, "" if rr.ok else rr.text[:240])
        call(md, "POST", f"/design-gallery/{gid}/lifecycle/submit-final", json={"note": "berkas final"})
        g = DB.design_gallery.find_one({"id": gid}, {"_id": 0})
        print("   desain:", short(g or {}, ("code", "status", "version", "approved_at")), "berkas:", len((g or {}).get("files") or []))
    print("0b) Kain dasar yang lolos (induk woven/knit dengan SKU disetujui/produksi atau handfeel/labdip ACC):")
    base = None
    for t in DB.product_templates.find({"status": "active", "stage": "pfp", "fabric_type": "woven"}, {"_id": 0, "id": 1, "name": 1, "fabric_type": 1, "stage": 1}):
        if DB.products.find_one({"template_id": t["id"], "lifecycle": {"$in": ["disetujui", "produksi"]}}):
            base = t; break
    if not base:
        for t in DB.product_templates.find({"status": "active"}, {"_id": 0, "id": 1, "name": 1, "fabric_type": 1, "stage": 1}):
            if DB.products.find_one({"template_id": t["id"], "lifecycle": {"$in": ["disetujui", "produksi"]}}):
                base = t; break
        body["base_fabric_override_reason"] = "uji telusur: belum ada induk PFP lolos"
    print("   kain dasar:", base)
    spec["design_id"] = gid or ""
    spec["base_fabric_template_id"] = (base or {}).get("id", "")
    body["design_id"] = gid or ""
print("1) Buat permintaan sample + spesifikasi (MD):")
r = call(md, "POST", "/rnd/samples", json=body)
if not r.ok:
    print("   coba sebagai admin:")
    r = call(adm, "POST", "/rnd/samples", json=body)
if not r.ok:
    sys.exit(0)
s = r.json()
sid = s["id"]
print("   sample:", short(s, ("number", "status", "sample_types", "spec_id", "line_code")))
print("2) Siapa yang bisa mengerjakan:")
r = call(md, "GET", f"/rnd/samples/{sid}/performers")
perf = r.json() if r.ok else {}
print("   performers:", json.dumps(perf)[:700])
cands = []
for k in ("suppliers", "performers", "items", "candidates", "rows"):
    if isinstance(perf, dict) and isinstance(perf.get(k), list):
        cands = perf[k]
if isinstance(perf, list):
    cands = perf
r = call(md, "GET", f"/rnd/samples/{sid}/partner-options")
opts = r.json().get("items", []) if r.ok else []
print("   tujuan kirim:", [(o["name"], o["kind_label"]) for o in opts if o["kind"] == "makloon"][:6], "+", sum(1 for o in opts if o["kind"] == "supplier"), "pemasok")
sup = "mak_seed_printing" if TYPE == "proofing" else "mak_seed_celup"
print("3) Kirim ke supplier/mitra:")
r = call(md, "POST", f"/rnd/samples/{sid}/send", json={"supplier_ids": [sup], "type_codes": [TYPE], "due_date": "2026-11-30"})
print("4) Putaran: buka → kirim hasil → nilai ACC:")
r = call(md, "POST", f"/rnd/samples/{sid}/rounds", json={"supplier_id": sup, "type_code": TYPE, "note": "putaran 1"})
cur = DB.md_samples.find_one({"id": sid}, {"_id": 0})
rounds = cur.get("rounds") or []
rid = rounds[-1]["id"] if rounds else None
print("   rounds:", [short(x, ("id", "type", "supplier_id", "status")) for x in rounds][-2:])
if rid:
    import io as _io
    from PIL import Image as _Im
    _b = _io.BytesIO(); _Im.new("RGB", (640, 640), (200, 60, 60)).save(_b, format="PNG")
    rr = requests.post(f"{BASE}/rnd/samples/{sid}/rounds/{rid}/attachments", headers=md,
                       files={"file": (f"hasil_proofing_{T}.png", _b.getvalue(), "image/png")})
    print("  POST round attachments →", rr.status_code, "" if rr.ok else rr.text[:240])
    call(md, "POST", f"/rnd/samples/{sid}/rounds/{rid}/submit", json={"note": "hasil dikirim supplier", "performed_by_user_id": "user_md_01", "cost": 150000, **({"measurements": {"delta_e": 0.8, "colorfastness_wash": 4, "colorfastness_rub": 4}} if TYPE == "labdip" else {})})
    call(md, "POST", f"/rnd/samples/{sid}/rounds/{rid}/assess", json={"result": "acc", "score": 90, "note": "warna/print sesuai"})
print("5) Opsi kontrak sebelum putus:")
r = call(md, "GET", f"/rnd/samples/{sid}/contract-options")
if r.ok:
    print("   ", json.dumps(r.json())[:500])
print("6) Putus pemenang + ACC spesifikasi (produk lahir):")
dec = {"supplier_id": sup, "reason_code": "mutu_terbaik", "price": 6_500, "tariff_mode": "per_proses", "note": "pemenang", "approve_spec": True,
       "product_sku": f"AUD-RND-{T}", "product_name": f"Kain Audit {TYPE} {T}", "moq": 100, "lead_time_days": 14,
       "override_reason": "uji telusur end-to-end"}
r = call(adm, "POST", f"/rnd/samples/{sid}/decide", json=dec)
if not r.ok and "reason" in r.text.lower():
    dec["reason_code"] = "best_quality"
    r = call(adm, "POST", f"/rnd/samples/{sid}/decide", json=dec)
cur = DB.md_samples.find_one({"id": sid}, {"_id": 0})
d = cur.get("decision") or {}
print("   keputusan:", short(d, ("supplier_name", "price", "contract_number", "supplier_item_id")))
spec_doc = DB.md_specs.find_one({"id": cur.get("spec_id")}, {"_id": 0}) or {}
print("   spesifikasi:", short(spec_doc, ("number", "status", "lifecycle", "product_id", "product_sku")))
pid = spec_doc.get("product_id")
prod = DB.products.find_one({"id": pid}, {"_id": 0}) if pid else {}
print("   produk lahir:", short(prod or {}, ("sku", "name", "stage", "lifecycle", "template_id", "base_unit", "fabric_type", "status")))
if prod and prod.get("template_id"):
    tpl = DB.product_templates.find_one({"id": prod["template_id"]}, {"_id": 0})
    print("   induk:", short(tpl or {}, ("code", "name", "stage", "restock_source", "default_route", "status")))
k = DB.supplier_contracts.find_one({"id": d.get("contract_id")}, {"_id": 0}) if d.get("contract_id") else None
print("   kontrak otomatis:", short(k or {}, ("contract_number", "contract_type", "partner_kind", "partner_id", "process_type", "product_id", "tariff_basis",
                                             "tariff_rate", "status")))
rt = DB.product_routes.find_one({"template_id": (prod or {}).get("template_id"), "entity_id": KSC}, {"_id": 0})
print("   rute lahir:", rt and (rt["name"], rt["origin"], rt["is_primary"], [(x["stage_code"], x["partner_name"], x["contract_number"], x.get("input_product_label")) for x in rt["steps"]]))
print("   produk color_id/design/kain dasar:", short(prod or {}, ("color_id", "design_id", "base_fabric_template_id")))
print("   resep proses untuk produk ini:", DB.process_recipes.count_documents({"output_product_id": pid}) if pid else "-")
print("7) Rilis ke produksi:")
if spec_doc.get("id"):
    r = call(md, "POST", f"/rnd/specs/{spec_doc['id']}/release-product", json={"reason": "rilis uji telusur", "override_reason": "uji telusur"})
    if not r.ok:
        call(adm, "POST", f"/rnd/specs/{spec_doc['id']}/release-product", json={"reason": "rilis uji telusur", "override_reason": "uji telusur"})
prod = DB.products.find_one({"id": pid}, {"_id": 0}) if pid else {}
print("   produk sesudah rilis:", short(prod or {}, ("sku", "lifecycle", "stage")))
print("8) Rencana SPK dari rute:")
if pid:
    r = call(adm, "GET", "/makloon-orders/plan-from-route", params={"product_id": pid, "qty": 100})
    j = r.json() if r.ok else {}
    print("   ", j.get("ready"), j.get("reason"), (j.get("payload") or {}).get("material_name"), (j.get("payload") or {}).get("material_qty"),
          [(x["stage_code"], x["makloon_name"], x["contract_id"] != "") for x in (j.get("payload") or {}).get("steps", [])])
print("9) Pengadaan produk baru (lama):")
if pid:
    po = {"supplier_id": sup, "entity_id": KSC, "warehouse_id": DB.warehouses.find_one({"entity_id": KSC}, {"_id": 0, "id": 1})["id"],
          "items": [{"product_id": pid, "quantity": 100, "price": 25_000, "unit": "yard"}], "notes": "uji telusur"}
    call(adm, "POST", "/purchase-orders", json=po)
    ken = DB.makloons.find_one({"process_types": "printing"}, {"_id": 0, "id": 1, "name": 1})
    grey = DB.products.find_one({"stage": "pfp"}, {"_id": 0, "id": 1, "sku": 1})
    if ken and grey:
        mko = {"mode": "process_only", "material_product_id": grey["id"], "material_qty": 100, "material_unit": "yard",
               "entity_id": KSC, "manual_material_reason": "uji", "route_reason": "uji telusur",
               "steps": [{"process_type": "printing", "stage_code": "printing", "makloon_id": ken["id"], "input_product_id": grey["id"],
                          "output_product_id": pid, "input_qty": 100}]}
        r = call(adm, "POST", "/makloon-orders", json=mko)
        if r.ok:
            print("   peringatan SPK:", r.json().get("warnings"))
print("TAG", T, "sample", sid)
