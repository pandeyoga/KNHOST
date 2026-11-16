"""MP-T5c — MD boleh membeli bahan greige/PFD/PFP (K-77; docs/blueprint/unit/MP-T5.md).

Izin baru `purchase_order.create_bahan` ("Buat PO bahan"), bawaan MD. Pemegangnya hanya boleh membuat PO yang semua
barisnya barang katalog bertahap bahan (pengaturan `purchasing.material_purchase_stages`, bawaan greige/PFD/PFP). Pemegang
`purchase_order.create` tidak terpengaruh. Permintaan pembelian (PR) MD tidak dipersempit (MD sudah boleh membuat PR).
"""
import uuid

import pytest

from core_utils import now_iso

KSC = "ent_ksc"


def uid(awalan: str) -> str:
    return f"{awalan}_mpt5_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def dunia(db):
    wh, sup = uid("wh"), uid("sup")
    await db.warehouses.insert_one({"id": wh, "code": f"M5-{wh[-5:]}", "name": "Gudang Greige Uji", "roles": ["storage"],
                                    "sharing_mode": "shared", "entity_ids": [], "active": True, "is_active": True,
                                    "zones": [], "created_at": now_iso()})
    await db.suppliers.insert_one({"id": sup, "name": "Pemasok Greige Uji", "code": f"S{sup[-5:]}", "status": "active",
                                   "is_active": True, "entity_id": KSC, "created_at": now_iso()})
    out = {"wh": wh, "sup": sup}
    for st in ("grey", "pfp", "finished"):
        pid = uid(st)
        await db.products.insert_one({"id": pid, "sku": f"MPT5-{st.upper()}-{pid[-4:]}", "name": f"Kain {st}",
                                      "stage": st, "fabric_type": "woven", "base_unit": "yard", "status": "active",
                                      "lifecycle": "produksi", "grade": "A", "created_at": now_iso()})
        out[st] = pid
    return out


@pytest.fixture(scope="module")
async def md(akun, sesi):
    return await sesi(await akun("md"))


def pr(d, pid):
    return {"items": [{"product_id": pid, "quantity": 100, "unit": "yard", "est_price": 20_000}],
            "warehouse_id": d["wh"], "entity_id": KSC, "reason": "stok greige menipis", "route_reason": "uji MP-T5c"}


def po(d, pid):
    return {"supplier_id": d["sup"], "entity_id": KSC, "warehouse_id": d["wh"], "route_reason": "uji MP-T5c",
            "items": [{"product_id": pid, "quantity": 100, "price": 20_000, "unit": "yard", "expected_grade": "A"}]}


async def test_MPT5c_U1_md_minta_beli_greige(klien, md, dunia):
    r = await klien.post("/api/purchase-requisitions", headers=md, json=pr(dunia, dunia["grey"]))
    assert r.status_code == 200, r.text


async def test_MPT5c_U2_md_tidak_boleh_po_barang_jadi(klien, md, dunia):
    r = await klien.post("/api/purchase-orders", headers=md, json=po(dunia, dunia["finished"]))
    assert r.status_code == 403, r.text
    assert "hanya untuk pembelian bahan" in r.json()["detail"]
    # PR barang jadi tetap boleh (akses MD yang sudah ada sebelum unit ini)
    r = await klien.post("/api/purchase-requisitions", headers=md, json=pr(dunia, dunia["finished"]))
    assert r.status_code == 200, r.text


async def test_MPT5c_U3_md_po_pfp(klien, md, dunia):
    r = await klien.post("/api/purchase-orders", headers=md, json=po(dunia, dunia["pfp"]))
    assert r.status_code == 200, r.text


async def test_MPT5c_U4_tahap_dari_pengaturan(klien, md, dunia):
    from services import config_resolver
    await config_resolver.set_value("purchasing.material_purchase_stages", ["grey"], actor="uji MP-T5c", reason="uji")
    try:
        r = await klien.post("/api/purchase-orders", headers=md, json=po(dunia, dunia["pfp"]))
        assert r.status_code == 403, r.text
    finally:
        await config_resolver.set_value("purchasing.material_purchase_stages", ["grey", "pfd", "pfp"],
                                        actor="uji MP-T5c", reason="uji")


async def test_MPT5c_U5_pemegang_create_tidak_terpengaruh(klien, kepala_admin, dunia):
    r = await klien.post("/api/purchase-orders", headers=kepala_admin, json=po(dunia, dunia["finished"]))
    assert r.status_code == 200, r.text


async def test_MPT5c_U6_izin_peran_kustom(klien, sesi, akun, dunia, peran_tanpa_acuan, peran_manajer_kosong):
    boleh = await sesi(await akun(await peran_tanpa_acuan({"purchase_order": ["view", "create_bahan"],
                                                           "supplier": ["view"], "product": ["view"]})))
    kosong = await sesi(await akun(await peran_manajer_kosong()))
    assert (await klien.post("/api/purchase-orders", headers=boleh, json=po(dunia, dunia["grey"]))).status_code == 200
    assert (await klien.post("/api/purchase-orders", headers=kosong, json=po(dunia, dunia["grey"]))).status_code == 403
