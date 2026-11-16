"""MP-T3 — R&D tersambung ke mitra makloon (docs/blueprint/unit/MP-T3.md).

Labdip dikerjakan pencelup, proofing dikerjakan mitra printing: sample boleh dikirim ke mitra makloon yang mengerjakan
proses jenis sample-nya (labdip → celup, proofing → printing, handfeel → tenun/rajut/pre-treatment). Pemenang mitra
makloon → kontrak makloon (per proses atau borongan, K-68) + rute utama makloon. Gerbang kain dasar proofing (K-72).
"""
import uuid

import pytest

from core_utils import now_iso

KSC = "ent_ksc"


def uid(awalan: str) -> str:
    return f"{awalan}_mpt3_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def dunia(db):
    c, p = uid("mkC"), uid("mkP")
    await db.makloons.insert_many([
        {"id": c, "name": "Pencelup Uji", "process_types": ["celup"], "entity_id": KSC, "status": "active"},
        {"id": p, "name": "Printing Uji", "process_types": ["printing"], "entity_id": KSC, "status": "active"}])
    return {"c": c, "p": p}


async def sample_acc(db, dunia, *, mitra: str, jenis: str = "labdip"):
    """Fixture: spesifikasi ber-produk (SKU lahir lebih dulu) + sample in_progress dengan round ACC milik `mitra`."""
    tpl, v, spec, smp = uid("tpl"), uid("v"), uid("spec"), uid("smp")
    await db.product_templates.insert_one({"id": tpl, "name": f"Artikel R&D {tpl[-4:]}", "stage": "finished",
                                           "status": "active", "created_at": now_iso()})
    await db.products.insert_one({"id": v, "sku": f"MPT3-{v[-6:].upper()}", "name": "Kain R&D uji", "stage": "finished",
                                  "template_id": tpl, "spec_id": spec, "base_unit": "yard", "status": "active",
                                  "lifecycle": "disetujui", "created_at": now_iso()})
    await db.md_specs.insert_one({"id": spec, "number": f"KSC/SPEC-{spec[-4:]}", "status": "approved",
                                  "product_id": v, "template_id": tpl, "entity_id": KSC, "timeline": [],
                                  "created_at": now_iso()})
    snap = {"supplier_id": mitra, "supplier_name": "Mitra", "partner_kind": "makloon"}
    await db.md_samples.insert_one({
        "id": smp, "number": f"KSC/SMP-{smp[-4:]}", "title": "Sample uji", "entity_id": KSC, "status": "in_progress",
        "sample_types": [jenis], "spec_id": spec, "unit": "yard", "timeline": [],
        "participants": [{**snap, "status": "invited", "rounds": 1}],
        "rounds": [{"id": uid("rnd"), "round_no": 1, **snap, "type_code": jenis, "status": "assessed",
                    "result": "acc", "score": 90}],
        "created_at": now_iso()})
    return {"tpl": tpl, "v": v, "spec": spec, "smp": smp}


def putus(mitra: str, **extra):
    return {"supplier_id": mitra, "reason_code": "mutu_terbaik", "price": 9_000, "note": "pemenang",
            "override_reason": "uji MP-T3 tanpa uji wajib", **extra}


async def test_MPT3_U1_pemenang_mitra_makloon_kontrak_dan_rute(klien, kepala_admin, db, dunia):
    s = await sample_acc(db, dunia, mitra=dunia["c"])
    r = await klien.post(f"/api/rnd/samples/{s['smp']}/decide", headers=kepala_admin, json=putus(dunia["c"]))
    assert r.status_code == 200, r.text
    dec = (await db.md_samples.find_one({"id": s["smp"]}, {"_id": 0}))["decision"]
    k = await db.supplier_contracts.find_one({"id": dec["contract_id"]}, {"_id": 0})
    assert (k["contract_type"], k["partner_id"], k["process_type"], k["tariff_basis"], k["tariff_rate"]) == \
        ("makloon", dunia["c"], "celup", "yard", 9000.0)
    assert not dec.get("supplier_item_id")   # barang supplier hanya untuk pemasok
    rte = await db.product_routes.find_one({"template_id": s["tpl"], "entity_id": KSC}, {"_id": 0})
    assert rte and rte["origin"] == "rnd" and rte["is_primary"] is True
    assert [(x["kind"], x["stage_code"], x["partner_id"], x["contract_id"]) for x in rte["steps"]] == [
        ("makloon", "celup", dunia["c"], dec["contract_id"])]
    tpl = await db.product_templates.find_one({"id": s["tpl"]}, {"_id": 0, "restock_source": 1})
    assert (tpl.get("restock_source") or {}).get("mode") == "makloon"


async def test_MPT3_U1b_tarif_borongan(klien, kepala_admin, db, dunia):
    s = await sample_acc(db, dunia, mitra=dunia["c"])
    r = await klien.post(f"/api/rnd/samples/{s['smp']}/decide", headers=kepala_admin,
                         json=putus(dunia["c"], tariff_mode="borongan", price=2_500_000))
    assert r.status_code == 200, r.text
    dec = (await db.md_samples.find_one({"id": s["smp"]}, {"_id": 0}))["decision"]
    k = await db.supplier_contracts.find_one({"id": dec["contract_id"]}, {"_id": 0})
    assert (k["tariff_basis"], k["tariff_rate"]) == ("lot", 2_500_000.0)


async def test_MPT3_U2_kirim_ke_mitra_yang_tidak_mengerjakan_prosesnya(klien, kepala_admin, db, dunia):
    smp = uid("smp")
    await db.md_samples.insert_one({"id": smp, "number": f"KSC/SMP-{smp[-4:]}", "title": "Kirim uji", "entity_id": KSC,
                                    "status": "draft", "sample_types": ["labdip"], "unit": "yard",
                                    "color_target": {"name": "Biru", "hex": "#1F4E99", "pantone_code": "19-4052 TCX"},
                                    "chain_override": {"reason": "uji"}, "timeline": [], "created_at": now_iso()})
    r = await klien.post(f"/api/rnd/samples/{smp}/send", headers=kepala_admin,
                         json={"supplier_ids": [dunia["p"]], "type_codes": ["labdip"], "due_date": "2026-12-01"})
    assert r.status_code == 400, r.text
    assert "tidak mengerjakan" in r.json()["detail"]
    r = await klien.post(f"/api/rnd/samples/{smp}/send", headers=kepala_admin,
                         json={"supplier_ids": [dunia["c"]], "type_codes": ["labdip"], "due_date": "2026-12-01"})
    assert r.status_code == 200, r.text
    cur = await db.md_samples.find_one({"id": smp}, {"_id": 0})
    assert cur["participants"][0]["partner_kind"] == "makloon"
    assert cur["rounds"][0]["supplier_name"] == "Pencelup Uji"


async def test_MPT3_U3_gerbang_kain_dasar_proofing(db):
    from services import rnd_flow_service as flow
    jadi, pfp = uid("tplj"), uid("tplp")
    for tid, st in ((jadi, "finished"), (pfp, "pfp")):
        await db.product_templates.insert_one({"id": tid, "name": f"Dasar {st}", "stage": st, "fabric_type": "woven",
                                               "status": "active", "created_at": now_iso()})
        await db.products.insert_one({"id": uid("pd"), "sku": f"DSR-{tid[-5:]}", "name": "Dasar", "stage": st,
                                      "template_id": tid, "lifecycle": "produksi", "status": "active"})
    spec = {"base_fabric_template_id": jadi, "target": {"fabric_type": "woven", "stage": "finished"}}
    with pytest.raises(flow.FlowError) as e:
        await flow.assert_stage_chain({}, ["proofing"], spec, KSC)
    assert "kain dasar harus bertahap PFP" in str(e.value)
    out = await flow.assert_stage_chain({"base_fabric_override_reason": "stok PFP kosong, pakai kain jadi putih"},
                                        ["proofing"], spec, KSC)
    assert out["base_fabric_override"]["reason"].startswith("stok PFP kosong")
    spec_rajut = {"base_fabric_template_id": pfp, "target": {"fabric_type": "knit", "stage": "finished"}}
    with pytest.raises(flow.FlowError) as e:
        await flow.assert_stage_chain({}, ["proofing"], spec_rajut, KSC)
    assert "jenis kain" in str(e.value)
    ok = await flow.assert_stage_chain({}, ["proofing"], {**spec_rajut, "target": {"fabric_type": "woven"}}, KSC)
    assert "base_fabric_override" not in ok


async def test_MPT3_U4_pesan_desain_belum_final(db):
    from services import rnd_flow_service as flow
    gid = uid("dsg")
    await db.design_gallery.insert_one({"id": gid, "code": "DSG-MPT3", "status": "approved", "files": []})
    with pytest.raises(flow.FlowError) as e:
        await flow.assert_design_usable(gid, for_send=True)
    assert "sudah disetujui tetapi berkas final belum diajukan" in str(e.value)


async def test_MPT3_U6_produk_membawa_color_id(db):
    from services import rnd_spec_service as specs
    doc = specs._product_draft({"id": uid("spec"), "target": {"stage": "finished"},  # noqa: SLF001
                                "color_target": {"color_id": "col_mpt3", "code": "KN-BIR-01", "name": "Biru",
                                                 "hex": "#1F4E99"}}, "SKU-MPT3", "Kain", 10_000)
    assert doc["color_id"] == "col_mpt3"
