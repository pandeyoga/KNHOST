"""MP-T2 — SPK makloon membaca rute; rantai tahap ditegakkan; SPK draf tanpa mitra (docs/blueprint/unit/MP-T2.md).

Tahap dari Master Tahapan Proses (benih): pfp = grey→pfp (pre_treatment), printing = pfp→finished.
K-61: SPK draf boleh tanpa mitra; kirim bahan ditolak sampai mitra diisi.
"""
import uuid

import pytest

from core_utils import now_iso

KSC = "ent_ksc"


def uid(awalan: str) -> str:
    return f"{awalan}_mpt2_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def dunia(db, klien, kepala_admin):
    """Fixture: artikel jadi J (1 varian V), greige G, PFP P; mitra pre-treatment A, printing B; kontrak makloon B.
    Rute utama dibuat lewat API (MP-T1): G → pfp@A (resep yield 0,95) → P → printing@B (kontrak) → V."""
    tpl, v, g, p, a, b, k, rc = uid("tpl"), uid("v"), uid("g"), uid("p"), uid("mkA"), uid("mkB"), uid("ctr"), uid("rcp")
    wh = uid("wh")
    await db.warehouses.insert_one({"id": wh, "code": f"M2-{wh[-5:]}", "name": "Gudang Uji MP-T2", "roles": ["storage"],
                                    "sharing_mode": "shared", "entity_ids": [], "active": True, "is_active": True,
                                    "zones": [], "created_at": now_iso()})
    await db.product_templates.insert_one({"id": tpl, "name": f"Artikel SPK {tpl[-4:]}", "stage": "finished",
                                           "status": "active", "created_at": now_iso()})
    for pid, stage, t in ((v, "finished", tpl), (g, "grey", ""), (p, "pfp", "")):
        await db.products.insert_one({"id": pid, "sku": f"MPT2-{pid[-6:].upper()}", "name": f"SPK {stage} {pid[-4:]}",
                                      "stage": stage, "fabric_type": "woven", "gramasi": 120, "lebar": 1.5,
                                      "template_id": t, "base_unit": "yard", "status": "active",
                                      "lifecycle": "produksi", "created_at": now_iso()})
    await db.makloons.insert_many([
        {"id": a, "name": "Pretreat SPK", "process_types": ["pre_treatment"], "entity_id": KSC, "status": "active"},
        {"id": b, "name": "Printing SPK", "process_types": ["printing"], "entity_id": KSC, "status": "active"}])
    await db.supplier_contracts.insert_one({"id": k, "contract_number": "KSC/SCT-MPT2", "contract_type": "makloon",
                                            "partner_kind": "makloon", "partner_id": b, "process_type": "printing",
                                            "tariff_basis": "yard", "tariff_rate": 5000, "status": "active",
                                            "entity_id": KSC})
    await db.process_recipes.insert_one({"id": rc, "name": "PFP SPK", "process_type": "pre_treatment",
                                         "input_product_id": g, "input_stage": "grey", "output_product_id": p,
                                         "output_stage": "pfp", "yield_factor": 0.95, "waste_pct": 0,
                                         "default_makloon_id": a, "entity_id": KSC, "status": "active"})
    r = await klien.post(f"/api/product-templates/{tpl}/routes", headers=kepala_admin, json={
        "name": "Printing", "steps": [
            {"kind": "makloon", "stage_code": "pfp", "input_product_id": g, "output_product_id": p, "partner_id": a,
             "recipe_id": rc},
            {"kind": "makloon", "stage_code": "printing", "input_product_id": p, "partner_id": b, "contract_id": k}]})
    assert r.status_code == 200, r.text
    return {"tpl": tpl, "v": v, "g": g, "p": p, "a": a, "b": b, "k": k, "rc": rc, "wh": wh}


def spk(d, steps, **extra):
    return {"mode": "process_only", "material_product_id": d["g"], "material_qty": 100, "material_unit": "yard",
            "from_warehouse_id": d["wh"], "manual_material_reason": "uji MP-T2", "steps": steps, **extra}


async def test_MPT2_U1_rencana_dari_rute(klien, kepala_admin, dunia):
    """Target 95 yard jadi. Langkah 2 tanpa resep → faktor 1 → bahan langkah 2 = 95 PFP.
    Langkah 1 resep yield 0,95 → greige = 95 ÷ 0,95 = 100 yard."""
    r = await klien.get("/api/makloon-orders/plan-from-route", headers=kepala_admin,
                        params={"product_id": dunia["v"], "qty": 95})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ready"] is True
    pl = j["payload"]
    assert pl["material_product_id"] == dunia["g"] and pl["material_qty"] == 100
    assert [(s["stage_code"], s["makloon_id"], s["output_product_id"]) for s in pl["steps"]] == [
        ("pfp", dunia["a"], dunia["p"]), ("printing", dunia["b"], dunia["v"])]
    assert pl["steps"][0]["recipe_id"] == dunia["rc"] and pl["steps"][1]["contract_id"] == dunia["k"]


async def test_MPT2_U2_rantai_tahap_ditegakkan(klien, kepala_admin, dunia):
    r = await klien.post("/api/makloon-orders", headers=kepala_admin, json=spk(dunia, [
        {"stage_code": "printing", "process_type": "printing", "makloon_id": dunia["b"],
         "output_product_id": dunia["v"]}]))
    assert r.status_code == 400, r.text
    assert "bahan masuk harus bertahap PFP" in r.json()["detail"]


async def test_MPT2_U2b_hasil_tahap_salah_ditolak(klien, kepala_admin, dunia):
    r = await klien.post("/api/makloon-orders", headers=kepala_admin, json=spk(dunia, [
        {"stage_code": "pfp", "process_type": "pre_treatment", "makloon_id": dunia["a"],
         "output_product_id": dunia["v"]}]))
    assert r.status_code == 400, r.text
    assert "hasil harus bertahap PFP" in r.json()["detail"]


async def test_MPT2_U3_draf_tanpa_mitra_lalu_isi_mitra(klien, kepala_admin, dunia, db):
    r = await klien.post("/api/makloon-orders", headers=kepala_admin, json=spk(dunia, [
        {"stage_code": "pfp", "process_type": "pre_treatment", "output_product_id": dunia["p"]}]))
    assert r.status_code == 200, r.text
    mko = r.json()["id"]
    r = await klien.post(f"/api/makloon-orders/{mko}/issue", headers=kepala_admin,
                         json={"step_seq": 1, "from_warehouse_id": dunia["wh"]})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Isi mitra langkah 1 sebelum mengirim bahan."
    r = await klien.post(f"/api/makloon-orders/{mko}/steps/1/partner", headers=kepala_admin,
                         json={"makloon_id": dunia["b"]})
    assert r.status_code == 400 and "tidak mengerjakan" in r.json()["detail"]
    r = await klien.post(f"/api/makloon-orders/{mko}/steps/1/partner", headers=kepala_admin,
                         json={"makloon_id": dunia["a"]})
    assert r.status_code == 200, r.text
    st = (await db.makloon_orders.find_one({"id": mko}, {"_id": 0}))["steps"][0]
    assert st["makloon_id"] == dunia["a"] and st["makloon_name"] == "Pretreat SPK"


async def test_MPT2_U5_prefill_pr_membaca_rute(db, dunia):
    """Baris PR ber-mode makloon untuk varian V → prefill memakai rute utama (2 langkah), bukan resep tunggal."""
    from services import pr_sourcing_service as src
    pr = uid("pr")
    await db.purchase_requisitions.insert_one({"id": pr, "number": "KSC/PR-MPT2", "entity_id": KSC,
                                               "warehouse_id": dunia["wh"], "status": "approved",
                                               "items": [{"line_no": 1, "product_id": dunia["v"], "quantity": 95,
                                                          "unit": "yard", "fulfillment_mode": "makloon"}],
                                               "created_at": now_iso()})
    out = await src.makloon_prefill(pr, 1)
    assert out["ready"] is True and out["source"] == "rute"
    assert [s["stage_code"] for s in out["payload"]["steps"]] == ["pfp", "printing"]
    assert out["payload"]["material_qty"] == 100
