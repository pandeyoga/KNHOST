"""UAT 24 Okt — fase F3 (ANALISIS_TEMUAN_UAT_23OKT.md P1/P3/P4/P5/P6): R&D & desain.

P1 kepemilikan desain (white/customer label, klaim, pembeli lama, penegakan SO, OD) · P6 tag desain di produk + export ·
P4 rantai handfeel → labdip, labdip multi-warna, Pustaka lahir dari labdip, supplier uji ulang berkontrak, aksi tahap ·
P3 Pantone wajib saat kirim labdip, PNG cetak wajib, surat perintah kerja · P5 nilai sumbu baru saat ACC spesifikasi.

Jalankan: cd /app/backend && python -m pytest tests/test_uat24_f3.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]
ENT = "ent_ksc"
ACTOR = {"id": "u_uji_f3", "name": "Uji F3"}


def _login(email, entity=ENT):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}, r.json()["user"]


ADMIN, ADMIN_USER = _login("admin@kainnusantara.id")
MANAGER, MANAGER_USER = _login("manager@kainnusantara.id")
SALES2, SALES2_USER = _login("sales2@kainnusantara.id")
DSG = f"dsgn_TEST_F3_{T}"
TPL = f"tpl_TEST_F3_{T}"
PROD = f"prod_TEST_F3_{T}"


def _customers(n=2):
    rows = list(DB.customers.find({"entity_id": ENT, "shared_walk_in": {"$ne": True}}, {"_id": 0, "id": 1, "name": 1}).limit(n))
    assert len(rows) >= n
    return rows


@pytest.fixture(scope="module", autouse=True)
def _setup():
    DB.design_gallery.insert_one({"id": DSG, "code": f"UJ-F3-{T}", "title": f"Desain Uji {T}", "status": "approved",
                                  "entity_id": ENT, "category_code": "FLR", "category_name": "Floral",
                                  "design_category_code": "MDN", "design_category_name": "Modern", "tags": ["uji"],
                                  "files": [], "versions": [{"version": 1}], "version": 1})
    src = DB.product_templates.find_one({"status": "active", "axes.key": "color"}, {"_id": 0})
    DB.product_templates.insert_one({**src, "id": TPL, "name": f"Induk Uji F3 {T}", "sku_prefix": f"TF3{T}".upper()})
    p = DB.products.find_one({"status": "active"}, {"_id": 0})
    clone = {k: v for k, v in p.items() if k not in ("variant_key", "template_id", "variant_options", "variant_attrs")}
    DB.products.insert_one({**clone, "id": PROD, "sku": f"TST-F3-{T}", "name": f"Produk Uji F3 {T}",
                            "exclusive_customer_id": "", "design_id": ""})
    yield
    DB.design_gallery.delete_many({"id": {"$regex": f"^dsgn_TEST_F3_{T}"}})
    DB.product_templates.delete_one({"id": TPL})
    DB.products.delete_many({"id": {"$regex": f"^prod_TEST_F3_{T}"}})
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_TEST_F3_{T}"}})
    sm = [s["id"] for s in DB.md_samples.find({"title": {"$regex": f"UJI-F3-{T}"}}, {"id": 1})]
    specs = [s["spec_id"] for s in DB.md_samples.find({"id": {"$in": sm}}, {"spec_id": 1}) if s.get("spec_id")]
    DB.md_samples.delete_many({"id": {"$in": sm}})
    DB.md_specs.delete_many({"id": {"$in": specs}})
    DB.color_library.delete_many({"source.sample_number": {"$regex": "."}, "name": {"$regex": f"UJI{T}"}})
    DB.supplier_contracts.delete_many({"contract_number": f"UJ-SCT-{T}"})


# ─── P1/P6 — kepemilikan desain & turunannya di SKU ─────────────────────────
def test_p6_tautan_desain_menyalin_kode_dan_kategori_ke_sku():
    r = requests.post(f"{BASE}/design-gallery/{DSG}/products", headers=ADMIN, json={"product_ids": [PROD]})
    assert r.status_code == 200, r.text
    p = DB.products.find_one({"id": PROD}, {"_id": 0})
    assert p["design_id"] == DSG and p["design_code"] == f"UJ-F3-{T}"
    assert p["pattern_category_name"] == "Floral" and p["design_category_name"] == "Modern" and p["design_tags"] == ["uji"]


def test_p1_customer_label_mengunci_sku_dan_pembeli_lama_boleh_repeat_dari_stok():
    owner, old_buyer = _customers(2)
    other = DB.customers.find_one({"entity_id": ENT, "id": {"$nin": [owner["id"], old_buyer["id"]]},
                                   "shared_walk_in": {"$ne": True}}, {"_id": 0, "id": 1})
    DB.sales_orders.insert_one({"id": f"so_TEST_F3_{T}_old", "number": f"SO-UJ-F3-{T}", "status": "confirmed",
                                "entity_id": ENT, "customer_id": old_buyer["id"], "customer_name": old_buyer["name"],
                                "created_at": "2026-10-01T00:00:00", "items": [{"product_id": PROD, "quantity": 10,
                                                                               "unit": "yard", "line_total": 1000}]})
    from fastapi import HTTPException
    from services import design_ownership_service as own
    from services import special_order_phase2 as p2
    run(own.set_customer_owner(DSG, owner["id"], "manual", ACTOR, "uji"))
    p = DB.products.find_one({"id": PROD}, {"_id": 0})
    assert p["exclusive_customer_id"] == owner["id"] and p["exclusive_source"] == "design"
    assert old_buyer["id"] in p["exclusive_allow_customer_ids"]
    assert p2.assert_customer_allowed(p, owner["id"]) == ""
    assert p2.assert_customer_allowed(p, old_buyer["id"]) == "grandfathered"
    with pytest.raises(HTTPException) as ei:
        p2.assert_customer_allowed(p, other["id"])
    assert "customer label" in ei.value.detail
    use = run(own.usage(DSG))
    assert use["orders"] == 1 and use["customers"][0]["customer_id"] == old_buyer["id"]
    run(own.release_to_white(DSG, ACTOR, "uji selesai"))
    p = DB.products.find_one({"id": PROD}, {"_id": 0})
    assert not p.get("exclusive_customer_id") and not p.get("exclusive_source")


def test_p1_klaim_diajukan_sales_diputus_manajer():
    owner = _customers(1)[0]
    r = requests.post(f"{BASE}/design-gallery/{DSG}/claims", headers=ADMIN,
                      json={"customer_id": owner["id"], "reason": "pelanggan minta eksklusif"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["claim_pending"] and d["ownership"] == "white"
    cid = d["pending_claims"][0]["id"]
    r2 = requests.post(f"{BASE}/design-gallery/{DSG}/claims/{cid}/decide", headers=ADMIN, json={"approve": True})
    assert r2.status_code == 400 and "sendiri" in r2.text      # pengaju tidak memutus klaimnya sendiri
    r3 = requests.post(f"{BASE}/design-gallery/{DSG}/claims/{cid}/decide", headers=MANAGER, json={"approve": True, "reason": "OK"})
    assert r3.status_code == 200, r3.text
    assert r3.json()["ownership"] == "customer" and r3.json()["owner_customer_id"] == owner["id"]
    lst = requests.get(f"{BASE}/design-gallery", headers=ADMIN, params={"ownership": "customer"}).json()
    assert any(x["id"] == DSG for x in lst)
    requests.post(f"{BASE}/design-gallery/{DSG}/ownership/white", headers=MANAGER, json={"reason": "uji selesai"})


def test_p1_6_artwork_customer_label_pelanggan_lain_ditolak_di_od():
    owner, other = _customers(2)
    from services import design_ownership_service as own
    from services import special_order_items as items
    run(own.set_customer_owner(DSG, owner["id"], "manual", ACTOR, "uji"))
    try:
        assert run(items.assert_artwork_usable(DSG, ENT, owner["id"]))["id"] == DSG
        with pytest.raises(items.ItemError):
            run(items.assert_artwork_usable(DSG, ENT, other["id"]))
    finally:
        run(own.release_to_white(DSG, ACTOR, "uji selesai"))


def test_p6_4_dataset_penjualan_per_desain():
    from services import export_registry as reg
    from services.export_registry_more import DESIGN_SALES_STAGES
    assert any(d["id"] == "design_sales" for d in reg.DATASETS)
    rows = list(DB.design_gallery.aggregate([{"$match": {"id": DSG}}, *DESIGN_SALES_STAGES]))
    assert rows and rows[0]["sku_count"] == 1 and rows[0]["so_count"] >= 1 and rows[0]["customer_count"] >= 1


# ─── P4/P3 — R&D produk baru ────────────────────────────────────────────────
def _labdip(colors=None, parent="", title="labdip"):
    body = {"sample_types": ["labdip"], "title": f"UJI-F3-{T} {title}", "unit": "meter", "qty_requested": 2,
            "parent_sample_id": parent,
            "spec": {"target": {"fabric_type": "woven", "gramasi": 150}, "sku_hint": f"TST-F3-{uuid.uuid4().hex[:5]}"}}
    if colors:
        body["color_targets"] = colors
        body["color_target"] = colors[0]
    return requests.post(f"{BASE}/rnd/samples", headers=ADMIN, json=body)


def _handfeel_acc():
    r = requests.post(f"{BASE}/rnd/samples", headers=ADMIN, json={
        "sample_types": ["handfeel"], "title": f"UJI-F3-{T} handfeel", "unit": "meter", "qty_requested": 2,
        "spec": {"target": {"fabric_type": "knit", "gramasi": 180, "lebar": 170, "yarn_count": "30s"},
                 "sku_hint": f"TST-F3-{uuid.uuid4().hex[:5]}"}})
    assert r.status_code == 200, r.text
    DB.md_samples.update_one({"id": r.json()["id"]}, {"$set": {"status": "decided"}})
    return r.json()


def test_p4_2_labdip_produk_baru_wajib_dari_handfeel_acc_dan_mewarisi_konstruksi():
    c = [{"name": "Biru Uji", "hex": "#123456", "pantone_code": "19-4052 TCX"}]
    r = _labdip(c)
    assert r.status_code == 400 and "HANDFEEL" in r.text
    hf = _handfeel_acc()
    r2 = _labdip(c, parent=hf["id"])
    assert r2.status_code == 200, r2.text
    s = r2.json()
    assert s["parent_sample_id"] == hf["id"] and s["stage"] == "labdip"
    spec = DB.md_specs.find_one({"id": s["spec_id"]}, {"_id": 0})
    assert spec["target"]["yarn_count"] == "30s"                         # warisan konstruksi handfeel
    assert s["color_target"]["pantone_code"] == "19-4052 TCX" and not s["color_target"]["color_id"]


def test_p4_3_labdip_multi_warna_jadi_kelompok_sampel_per_warna():
    hf = _handfeel_acc()
    cols = [{"name": f"Merah UJI{T}", "hex": "#AA0000", "pantone_code": "18-1664 TCX"},
            {"name": f"Hijau UJI{T}", "hex": "#00AA00", "pantone_code": "15-5534 TCX"},
            {"name": f"Kuning UJI{T}", "hex": "#EEEE00", "pantone_code": "13-0858 TCX"}]
    r = _labdip(cols, parent=hf["id"], title="multi")
    assert r.status_code == 200, r.text
    batch = r.json()["color_batch"]
    assert len(batch["samples"]) == 3
    docs = list(DB.md_samples.find({"color_batch_id": batch["id"]}, {"_id": 0}))
    assert sorted(d["color_target"]["name"] for d in docs) == sorted(c["name"] for c in cols)
    assert len({d["spec_id"] for d in docs}) == 3                          # satu spesifikasi per warna
    lst = requests.get(f"{BASE}/rnd/samples", headers=ADMIN, params={"color_batch_id": batch["id"]}).json()
    assert lst["count"] == 3


def test_p3_5_labdip_tanpa_pantone_tidak_bisa_dikirim_ke_supplier():
    hf = _handfeel_acc()
    r = _labdip([{"name": f"Abu UJI{T}", "hex": "#888888"}], parent=hf["id"], title="tanpa pantone")
    assert r.status_code == 200, r.text
    sup = DB.suppliers.find_one({"group_entity_id": {"$in": [None, ""]}}, {"_id": 0, "id": 1})
    s = requests.post(f"{BASE}/rnd/samples/{r.json()['id']}/send", headers=ADMIN, json={"supplier_ids": [sup["id"]]})
    assert s.status_code == 400 and "Pantone" in s.text


def test_p4_4_warna_labdip_acc_lahir_di_pustaka_atau_tertaut_pantone_sama():
    from services import rnd_flow_service as flow
    pantone = f"{(int(T, 16) % 89) + 10:02d}-{int(T, 16) % 9000 + 1000:04d} TPX"
    sm = {"id": f"smp_uji_{T}", "number": f"SMP-UJI-{T}", "spec_id": "",
          "color_target": {"name": f"Navy UJI{T}", "hex": "#1F3A93", "pantone_code": pantone}}
    DB.md_samples.insert_one({**sm, "title": f"UJI-F3-{T} pustaka"})
    born = run(flow.color_from_labdip(sm, "Uji F3"))
    assert born["color_id"] and born["code"].startswith("KN-NAV") and not born["linked_existing"]
    col = DB.color_library.find_one({"id": born["color_id"]}, {"_id": 0})
    assert col["pantone_code"] == pantone and col["source"]["kind"] == "labdip"
    sm2 = {**sm, "id": f"smp_uji_{T}_2", "color_target": {"name": "Navy lain", "hex": "#1F3A90", "pantone_code": pantone}}
    DB.md_samples.insert_one({**sm2, "title": f"UJI-F3-{T} pustaka 2"})
    again = run(flow.color_from_labdip(sm2, "Uji F3"))
    assert again["color_id"] == born["color_id"] and again["linked_existing"]
    DB.color_library.delete_one({"id": born["color_id"]})


def test_p3_5_format_pantone_divalidasi():
    from services import rnd_flow_service as flow
    assert flow.normalize_pantone("19-4052 tcx") == "19-4052 TCX"
    assert flow.normalize_pantone("Cool Gray 11 C") == "COOL GRAY 11 C"
    with pytest.raises(flow.FlowError):
        flow.normalize_pantone("biru muda")


def test_p4_7_terima_sampel_fisik_hanya_setelah_pemenang():
    hf = _handfeel_acc()
    r = requests.post(f"{BASE}/rnd/samples", headers=ADMIN, json={
        "sample_types": ["handfeel"], "title": f"UJI-F3-{T} finish", "unit": "meter", "qty_requested": 2,
        "spec": {"target": {"fabric_type": "woven"}, "sku_hint": f"TST-F3-{uuid.uuid4().hex[:5]}"}})
    sid = r.json()["id"]
    DB.md_samples.update_one({"id": sid}, {"$set": {"status": "assessed", "rounds": [{"id": "r1", "result": "acc"}]}})
    f = requests.post(f"{BASE}/rnd/samples/{sid}/finish", headers=ADMIN, json={})
    assert f.status_code == 400 and "pemenang" in f.text.lower()
    DB.md_samples.update_one({"id": sid}, {"$set": {"status": "decided"}})
    assert requests.post(f"{BASE}/rnd/samples/{sid}/finish", headers=ADMIN, json={}).status_code == 200
    d = requests.post(f"{BASE}/rnd/samples/{sid}/deliver", headers=ADMIN, json={"to": "customer"})
    assert d.status_code == 400 and "arsip" in d.text.lower()
    assert hf


def test_p4_6_supplier_uji_ulang_berkontrak_lalu_pernah_po():
    p = DB.products.find_one({"status": "active", "lifecycle": "produksi"}, {"_id": 0, "id": 1})
    sup = DB.suppliers.find_one({"group_entity_id": {"$in": [None, ""]}}, {"_id": 0, "id": 1, "name": 1})
    DB.supplier_contracts.insert_one({"id": f"sct_uji_{T}", "contract_number": f"UJ-SCT-{T}", "contract_type": "purchase",
                                      "partner_kind": "supplier", "partner_id": sup["id"], "partner_name": sup["name"],
                                      "product_id": p["id"], "status": "active", "entity_id": ENT})
    r = requests.get(f"{BASE}/rnd/revalidation/partners", headers=ADMIN, params={"product_id": p["id"]})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items[0]["basis"] == "contract" and any(x["id"] == sup["id"] and x["basis"] == "contract" for x in items)
    assert all(x["basis"] in ("contract", "po_history") for x in items)


# ─── P3.3 / P3.1 — PNG cetak & surat perintah kerja ──────────────────────────
def test_p3_3_png_cetak_wajib_berkas_final_dan_harus_png():
    from services import design_studio_service as studio
    req = studio.final_requirement({"files": [{"kind": "mockup"}, {"kind": "source"}]})
    assert not req["complete"] and req["print_png_required"] == 1
    assert studio.final_requirement({"files": [{"kind": "mockup"}, {"kind": "source"}, {"kind": "print_png"}]})["complete"]
    r = requests.post(f"{BASE}/design-gallery/{DSG}/files-kind/print_png", headers=ADMIN,
                      files={"file": ("pattern.png", b"\xff\xd8\xff\xe0 bukan png", "image/png")})
    assert r.status_code == 400 and "PNG" in r.text


def test_p3_1_surat_perintah_kerja_labdip_memuat_warna_pantone():
    from services.pdf_resolvers import DOC_REGISTRY, WO_SUPPLIER
    assert "md_sample_work_order" in DOC_REGISTRY
    sup = DB.suppliers.find_one({"group_entity_id": {"$in": [None, ""]}}, {"_id": 0, "id": 1, "name": 1})
    doc = {"id": "x", "number": "SMP-UJI", "title": "Uji", "sample_types": ["labdip"], "created_by": "MD Uji",
           "participants": [{"supplier_id": sup["id"], "supplier_name": sup["name"]}],
           "rounds": [{"supplier_id": sup["id"], "due_date": "2026-11-01"}],
           "color_target": {"name": "Navy", "hex": "#1F3A93", "pantone_code": "19-4052 TCX"}}
    WO_SUPPLIER.set(sup["id"])
    from db import db as _db
    out = run(DOC_REGISTRY["md_sample_work_order"]["resolver"](doc, _db))
    assert out["party_to"]["name"] == sup["name"]
    assert out["swatches"][0]["sub"] == "Pantone 19-4052 TCX"
    assert any(t["title"].startswith("LABDIP") for t in out["extra_tables"])


# ─── P5.3 — nilai sumbu baru saat ACC spesifikasi ────────────────────────────
def test_p5_3_nilai_sumbu_baru_ditambahkan_ke_induk():
    from services import rnd_spec_service as specs
    code = f"U{T[:3]}".upper()
    added = run(specs.add_axis_values(TPL, {"color": {"code": code, "label": f"Warna Uji {T}",
                                                      "value": "KN-UJI-01", "hex": "#123456"}}))
    assert added == [f"color:{code}"]
    tpl = DB.product_templates.find_one({"id": TPL}, {"_id": 0})
    opts = next(a for a in tpl["axes"] if a["key"] == "color")["options"]
    assert any(o["code"] == code and o["label"] == f"Warna Uji {T}" for o in opts)
    with pytest.raises(specs.RndError):      # kode sama, label beda → ditolak
        run(specs.add_axis_values(TPL, {"color": {"code": code, "label": "Lain"}}))
