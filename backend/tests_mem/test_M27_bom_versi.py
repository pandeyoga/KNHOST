"""M27 (masukan pemilik 16 Nov: "nama BOM diisi bebas? kenapa perlu nama BOM?").

U1 BOM baru tanpa nama → kode sistem "BOM {SKU} v1", versi 1, otomatis BOM UTAMA (pertama untuk produk itu).
U2 BOM kedua produk yang sama → v2, bukan utama; "Jadikan utama" memindah tanda utama (hanya satu per produk).
U3 Menonaktifkan BOM utama → versi aktif terbaru lain menjadi utama.
U4 Usulan Rute Produk memakai BOM UTAMA (dulu BOM aktif sembarang).
U5 BOM lama (tanpa versi) diberi versi + kode + utama oleh `backfill_bom_versions`.
"""
from __future__ import annotations

import uuid

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio
KSC = "ent_ksc"


def uid(p: str) -> str:
    return f"{p}_{uuid.uuid4().hex[:8]}"


async def _produk(db, stage: str, tpl: str = "") -> dict:
    pid = uid("p")
    doc = {"id": pid, "sku": f"M27-{pid[-5:].upper()}", "name": f"Uji {stage}", "stage": stage, "template_id": tpl,
           "base_unit": "yard", "status": "active", "created_at": now_iso()}
    await db.products.insert_one(dict(doc))
    return doc


async def _bom(klien, h, out: dict, bahan: dict, **extra) -> dict:
    r = await klien.post("/api/production/boms", headers=h, json={
        "entity_id": KSC, "output_product_id": out["id"],
        "components": [{"material_product_id": bahan["id"], "qty_per_unit": 1.1}], **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def test_U1_U2_U3_kode_versi_utama(klien, kepala_admin, db):
    out, bahan = await _produk(db, "finished"), await _produk(db, "grey")
    b1 = await _bom(klien, kepala_admin, out, bahan, name="nama bebas diabaikan")
    assert b1["code"] == f"BOM {out['sku']} v1" and b1["name"] == b1["code"]
    assert b1["version"] == 1 and b1["is_primary"] is True
    b2 = await _bom(klien, kepala_admin, out, bahan)
    assert b2["code"].endswith("v2") and b2["is_primary"] is False
    r = await klien.patch(f"/api/production/boms/{b2['id']}", headers=kepala_admin, json={"is_primary": True})
    assert r.status_code == 200 and r.json()["is_primary"] is True
    utama = await db.mfg_boms.count_documents({"output_product_id": out["id"], "is_primary": True})
    assert utama == 1
    r = await klien.patch(f"/api/production/boms/{b2['id']}", headers=kepala_admin, json={"status": "inactive"})
    assert r.status_code == 200 and r.json()["is_primary"] is False
    b1n = await db.mfg_boms.find_one({"id": b1["id"]}, {"_id": 0})
    assert b1n["is_primary"] is True   # versi aktif lain naik menjadi utama


async def test_U4_rute_memakai_bom_utama(klien, kepala_admin, db):
    from services.product_route_service import suggest
    tpl = uid("tpl")
    await db.product_templates.insert_one({"id": tpl, "name": "Artikel M27", "stage": "finished", "status": "active"})
    out, bahan = await _produk(db, "finished", tpl), await _produk(db, "grey")
    await _bom(klien, kepala_admin, out, bahan)
    b2 = await _bom(klien, kepala_admin, out, bahan)
    await klien.patch(f"/api/production/boms/{b2['id']}", headers=kepala_admin, json={"is_primary": True})
    usul = await suggest(tpl, KSC)
    sendiri = next(u for u in usul if u["name"] == "Produksi sendiri")
    assert sendiri["steps"][0]["bom_id"] == b2["id"]


async def test_U5_bom_lama_diberi_versi(db):
    from services.production_service import backfill_bom_versions
    out = await _produk(db, "finished")
    for i, nm in enumerate(("Resep lama A", "Resep lama B")):
        await db.mfg_boms.insert_one({"id": uid("bom"), "entity_id": KSC, "name": nm, "output_product_id": out["id"],
                                      "output_sku": out["sku"], "status": "active", "components": [],
                                      "created_at": f"2026-01-0{i + 1}T00:00:00+00:00"})
    assert await backfill_bom_versions() >= 2
    rows = await db.mfg_boms.find({"output_product_id": out["id"]}, {"_id": 0}).sort("version", 1).to_list(5)
    assert [r["version"] for r in rows] == [1, 2]
    assert rows[0]["code"] == f"BOM {out['sku']} v1" and rows[0]["name"] == "Resep lama A"   # nama lama tetap
    assert sum(1 for r in rows if r.get("is_primary")) == 1 and rows[1]["is_primary"] is True
    assert await backfill_bom_versions() == 0   # idempoten
