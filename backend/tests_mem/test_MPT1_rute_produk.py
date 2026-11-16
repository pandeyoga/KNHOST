"""MP-T1 — Rute Produk (docs/blueprint/unit/MP-T1.md).

Rute = urutan langkah dari bahan sampai barang. Tahap asal/hasil tiap langkah makloon dibaca dari Master Tahapan Proses
(benih `domain_registry.PROCESS_STAGES`: pfp = grey→pfp, printing = pfp→finished, pfd = grey→pfd, celup = pfd→finished).
Rute yang melompat tahap, bahan yang tahapnya salah, mitra yang tidak mengerjakan prosesnya, dan rute yang tidak berakhir
di tahap artikel ditolak dengan pesan berbahasa Indonesia.
"""
import uuid

import pytest

from core_utils import now_iso

KSC = "ent_ksc"


def uid(awalan: str) -> str:
    return f"{awalan}_mpt1_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def dunia(db):
    """Fixture: artikel jadi (2 varian), greige G, PFP P, mitra pre-treatment A, mitra printing B, pemasok S."""
    tpl, v1, v2, g, p = uid("tpl"), uid("v1"), uid("v2"), uid("grey"), uid("pfp")
    a, b, s, k = uid("mkA"), uid("mkB"), uid("sup"), uid("ctr")
    await db.product_templates.insert_one({"id": tpl, "name": f"Artikel Uji {tpl[-4:]}", "stage": "finished",
                                           "fabric_type": "woven", "status": "active", "created_at": now_iso()})
    for pid, stage, t in ((v1, "finished", tpl), (v2, "finished", tpl), (g, "grey", ""), (p, "pfp", "")):
        await db.products.insert_one({"id": pid, "sku": f"MPT1-{pid[-6:].upper()}", "name": f"Uji {stage} {pid[-4:]}",
                                      "stage": stage, "fabric_type": "woven", "template_id": t, "base_unit": "yard",
                                      "status": "active", "lifecycle": "produksi", "created_at": now_iso()})
    await db.makloons.insert_one({"id": a, "name": "Mitra Pretreat Uji", "process_types": ["pre_treatment"],
                                  "entity_id": KSC, "status": "active", "is_active": True})
    await db.makloons.insert_one({"id": b, "name": "Mitra Printing Uji", "process_types": ["printing"],
                                  "entity_id": KSC, "status": "active", "is_active": True})
    await db.suppliers.insert_one({"id": s, "name": "Pemasok Uji MP", "status": "active", "is_active": True,
                                   "entity_id": KSC})
    await db.supplier_contracts.insert_one({"id": k, "contract_number": "KSC/SCT-MPT1", "contract_type": "makloon",
                                            "partner_kind": "makloon", "partner_id": b, "process_type": "printing",
                                            "status": "active", "entity_id": KSC})
    return {"tpl": tpl, "v1": v1, "v2": v2, "g": g, "p": p, "a": a, "b": b, "s": s, "k": k}


def rute_print(d, **extra):
    return {"name": "Printing di mitra B", "steps": [
        {"kind": "makloon", "stage_code": "pfp", "input_product_id": d["g"], "output_product_id": d["p"],
         "partner_id": d["a"]},
        {"kind": "makloon", "stage_code": "printing", "input_product_id": d["p"], "partner_id": d["b"],
         "contract_id": d["k"]}], **extra}


async def test_MPT1_U1_rute_dua_langkah_tahap_dari_master(klien, kepala_admin, dunia):
    r = await klien.post(f"/api/product-templates/{dunia['tpl']}/routes", headers=kepala_admin, json=rute_print(dunia))
    assert r.status_code == 200, r.text
    j = r.json()
    assert [(s["from_stage"], s["to_stage"], s["process_type"]) for s in j["steps"]] == [
        ("grey", "pfp", "pre_treatment"), ("pfp", "finished", "printing")]
    assert j["is_primary"] is True and j["entity_id"] == KSC and j["origin"] == "manual"


async def test_MPT1_U2_bahan_tahap_salah_ditolak(klien, kepala_admin, dunia):
    r = await klien.post(f"/api/product-templates/{dunia['tpl']}/routes", headers=kepala_admin, json={
        "name": "Lompat", "steps": [{"kind": "makloon", "stage_code": "printing", "input_product_id": dunia["g"],
                                     "partner_id": dunia["b"]}]})
    assert r.status_code == 400
    assert "bahan masuk harus bertahap PFP" in r.json()["detail"]


async def test_MPT1_U3_rute_tidak_berakhir_di_tahap_artikel(klien, kepala_admin, dunia):
    r = await klien.post(f"/api/product-templates/{dunia['tpl']}/routes", headers=kepala_admin, json={
        "name": "Hanya PFP", "steps": [{"kind": "makloon", "stage_code": "pfp", "partner_id": dunia["a"]}]})
    assert r.status_code == 400
    assert "Rute berakhir di" in r.json()["detail"]


async def test_MPT1_U4_mitra_tidak_mengerjakan_proses(klien, kepala_admin, dunia):
    body = rute_print(dunia)
    body["steps"][1]["partner_id"] = dunia["a"]
    body["steps"][1].pop("contract_id")
    r = await klien.post(f"/api/product-templates/{dunia['tpl']}/routes", headers=kepala_admin, json=body)
    assert r.status_code == 400
    assert "tidak mengerjakan" in r.json()["detail"]


async def test_MPT1_U4b_rantai_putus_ditolak(klien, kepala_admin, dunia):
    r = await klien.post(f"/api/product-templates/{dunia['tpl']}/routes", headers=kepala_admin, json={
        "name": "Putus", "steps": [{"kind": "makloon", "stage_code": "pfd"},
                                   {"kind": "makloon", "stage_code": "printing"}]})
    assert r.status_code == 400
    assert "butuh bahan" in r.json()["detail"]


async def test_MPT1_U5_beli_hanya_langkah_pertama(klien, kepala_admin, dunia):
    r = await klien.post(f"/api/product-templates/{dunia['tpl']}/routes", headers=kepala_admin, json={
        "name": "Salah urut", "steps": [{"kind": "makloon", "stage_code": "pfp"},
                                        {"kind": "purchase", "partner_id": dunia["s"]}]})
    assert r.status_code == 400
    assert "hanya boleh di langkah pertama" in r.json()["detail"]


async def test_MPT1_U6_rute_utama_hanya_satu(klien, kepala_admin, dunia, db):
    r = await klien.post(f"/api/product-templates/{dunia['tpl']}/routes", headers=kepala_admin,
                         json={"name": "Beli jadi", "is_primary": True,
                               "steps": [{"kind": "purchase", "partner_id": dunia["s"]}]})
    assert r.status_code == 200, r.text
    utama = await db.product_routes.find({"template_id": dunia["tpl"], "product_id": "", "is_primary": True,
                                          "status": "active"}, {"_id": 0, "id": 1}).to_list(10)
    assert [u["id"] for u in utama] == [r.json()["id"]]
    lst = (await klien.get(f"/api/product-templates/{dunia['tpl']}/routes", headers=kepala_admin)).json()
    assert lst["primary_id"] == r.json()["id"] and lst["status"] == "diatur" and len(lst["items"]) == 2


async def test_MPT1_U7_pengecualian_varian(klien, kepala_admin, dunia):
    r = await klien.post(f"/api/product-templates/{dunia['tpl']}/routes", headers=kepala_admin,
                         json=rute_print(dunia, name="Khusus V1", product_id=dunia["v1"]))
    assert r.status_code == 200, r.text
    assert r.json()["is_primary"] is True   # rute pertama untuk varian V1 → otomatis utama
    e1 = (await klien.get(f"/api/products/{dunia['v1']}/route", headers=kepala_admin)).json()
    e2 = (await klien.get(f"/api/products/{dunia['v2']}/route", headers=kepala_admin)).json()
    assert e1["route"]["name"] == "Khusus V1"
    assert e2["route"]["name"] == "Beli jadi"


async def test_MPT1_U8_izin_kelola_rute(klien, sesi, akun, dunia, peran_tanpa_acuan, peran_manajer_kosong):
    boleh = await sesi(await akun(await peran_tanpa_acuan({"product": ["view"], "product_route": ["update"]})))
    kosong = await sesi(await akun(await peran_manajer_kosong()))
    body = {"name": "Beli lagi", "steps": [{"kind": "purchase", "partner_id": dunia["s"]}]}
    r1 = await klien.post(f"/api/product-templates/{dunia['tpl']}/routes", headers=boleh, json=body)
    r2 = await klien.post(f"/api/product-templates/{dunia['tpl']}/routes", headers=kosong, json=body)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 403


async def test_MPT1_U9_rilis_wajib_rute_utama(klien, kepala_admin, db):
    """Fixture: spesifikasi disetujui + produk lahir dari R&D tanpa rute → rilis ditolak; sesudah rute → lolos."""
    from services import config_resolver
    tpl, pid, sid = uid("tplr"), uid("prdr"), uid("spec")
    await db.product_templates.insert_one({"id": tpl, "name": "Artikel Rilis Uji", "stage": "finished",
                                           "status": "active", "created_at": now_iso()})
    await db.products.insert_one({"id": pid, "sku": f"MPT1R-{pid[-5:]}", "name": "Produk Rilis Uji", "stage": "finished",
                                  "template_id": tpl, "spec_id": sid, "status": "active", "lifecycle": "disetujui",
                                  "base_unit": "yard", "created_at": now_iso()})
    await db.md_specs.insert_one({"id": sid, "number": "KSC/SPEC-MPT1", "status": "approved", "lifecycle": "disetujui",
                                  "product_id": pid, "entity_id": KSC, "title": "Spesifikasi uji", "timeline": [],
                                  "created_at": now_iso()})
    body = {"reason": "rilis uji", "override_reason": "uji MP-T1"}
    r = await klien.post(f"/api/rnd/specs/{sid}/release-product", headers=kepala_admin, json=body)
    assert r.status_code == 400, r.text
    assert "belum punya rute utama" in r.json()["detail"]
    await config_resolver.set_value("rnd.release_requires_route", False, actor="uji MP-T1", reason="uji")
    try:
        r = await klien.post(f"/api/rnd/specs/{sid}/release-product", headers=kepala_admin, json=body)
        assert r.status_code == 200, r.text
    finally:
        await config_resolver.set_value("rnd.release_requires_route", True, actor="uji MP-T1", reason="uji")


async def test_MPT1_U10_putusan_rnd_melahirkan_rute_beli(db, dunia):
    """Fixture: keputusan pemenang pemasok S berkontrak → `_bind_product` membuat rute "Beli dari S"."""
    from services import rnd_sample_service
    tpl, pid, k = uid("tplb"), uid("prdb"), uid("ctrb")
    await db.product_templates.insert_one({"id": tpl, "name": "Artikel Putusan Uji", "stage": "finished",
                                           "status": "active", "created_at": now_iso()})
    await db.products.insert_one({"id": pid, "sku": f"MPT1B-{pid[-5:]}", "name": "Produk Putusan Uji",
                                  "stage": "finished", "template_id": tpl, "status": "active", "created_at": now_iso()})
    await db.supplier_contracts.insert_one({"id": k, "contract_number": "KSC/SCT-MPT1B", "contract_type": "purchase",
                                            "partner_kind": "supplier", "partner_id": dunia["s"], "product_id": pid,
                                            "status": "active", "entity_id": KSC})
    cur = {"id": uid("smp"), "number": "KSC/SMP-MPT1", "entity_id": KSC, "title": "Sample uji"}
    dec = {"supplier_id": dunia["s"], "supplier_name": "Pemasok Uji MP", "contract_id": k,
           "supplier_item_id": "sudah"}
    await rnd_sample_service._bind_product(cur, dec, pid, "Uji")
    rows = await db.product_routes.find({"template_id": tpl, "entity_id": KSC}, {"_id": 0}).to_list(5)
    assert len(rows) == 1
    rte = rows[0]
    assert rte["origin"] == "rnd" and rte["is_primary"] is True
    assert [(s["kind"], s["partner_id"], s["contract_id"]) for s in rte["steps"]] == [("purchase", dunia["s"], k)]


async def test_MPT1_U11_cek_jalur_membaca_rute(db, dunia):
    """Artikel bersumber restock 'supplier' tetapi rute utamanya makloon → SPK makloon tidak dianggap menyimpang."""
    from services import restock_source_service as rss
    await db.product_templates.update_one({"id": dunia["tpl"]}, {"$set": {"restock_source": {"mode": "supplier"}}})
    v1 = await db.products.find_one({"id": dunia["v1"]}, {"_id": 0})
    out = await rss.check_lines([(v1, "makloon")], reason="", entity_id=KSC, where="SPK")
    assert out["warnings"] == []
    assert out["routes"][0]["mode"] == "makloon" and out["routes"][0]["source"] == "rute"


async def test_MPT1_U12_pembuat_rute_awal(db):
    """Fixture: resep G→P (mitra A) dan P→jadi (mitra B) berakhir di varian artikel tanpa rute."""
    from scripts import mpt1_rute_awal as skrip
    tpl, v, g, p, a, b = uid("tpla"), uid("va"), uid("ga"), uid("pa"), uid("ma"), uid("mb")
    await db.product_templates.insert_one({"id": tpl, "name": "Artikel Rute Awal", "stage": "finished",
                                           "status": "active", "created_at": now_iso()})
    for pid, st, t in ((v, "finished", tpl), (g, "grey", ""), (p, "pfp", "")):
        await db.products.insert_one({"id": pid, "sku": f"MPT1A-{pid[-5:]}", "name": f"RA {st}", "stage": st,
                                      "template_id": t, "status": "active", "created_at": now_iso()})
    await db.makloons.insert_many([
        {"id": a, "name": "RA Pretreat", "process_types": ["pre_treatment"], "entity_id": KSC, "status": "active"},
        {"id": b, "name": "RA Printing", "process_types": ["printing"], "entity_id": KSC, "status": "active"}])
    await db.process_recipes.insert_many([
        {"id": uid("rcp"), "name": "RA pfp", "process_type": "pre_treatment", "input_product_id": g,
         "input_stage": "grey", "output_product_id": p, "output_stage": "pfp", "default_makloon_id": a,
         "entity_id": KSC, "status": "active"},
        {"id": uid("rcp"), "name": "RA print", "process_type": "printing", "input_product_id": p, "input_stage": "pfp",
         "output_product_id": v, "output_stage": "finished", "default_makloon_id": b, "entity_id": KSC,
         "status": "active"}])
    hasil = await skrip.jalankan(apply=False, entity_id=KSC, template_ids=[tpl])
    assert hasil["akan_dibuat"] == 1 and await db.product_routes.count_documents({"template_id": tpl}) == 0
    await skrip.jalankan(apply=True, entity_id=KSC, template_ids=[tpl])
    await skrip.jalankan(apply=True, entity_id=KSC, template_ids=[tpl])   # ulang → tidak menggandakan
    rows = await db.product_routes.find({"template_id": tpl}, {"_id": 0}).to_list(5)
    assert len(rows) == 1 and rows[0]["origin"] == "rute_awal"
    assert [(s["stage_code"], s["partner_id"]) for s in rows[0]["steps"]] == [("pfp", a), ("printing", b)]


async def test_MPT1_U14_pilihan_langkah_tersaring(klien, kepala_admin, dunia):
    j = (await klien.get("/api/product-routes/step-options", headers=kepala_admin,
                         params={"from_stage": "grey"})).json()
    kode = {o["stage_code"] for o in j["stages"]}
    assert {"pfp", "pfd"} <= kode and "printing" not in kode and "celup" not in kode
    pfp = next(o for o in j["stages"] if o["stage_code"] == "pfp")
    assert dunia["a"] in {m["id"] for m in pfp["partners"]} and dunia["b"] not in {m["id"] for m in pfp["partners"]}
