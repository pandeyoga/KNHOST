"""Bukti perilaku lama (bukan uji unit): jalankan di salinan kode lama `c3eb0a2`."""
from test_PK28_gr_ir import (bahan, buat_po, terima, tagih, retur, jurnal_aktif, baris, sisa_po,  # noqa: F401
                             GRIR, HUTANG, PERSEDIAAN, PPN_IN, KSC)
from db import db as _db


async def test_lama_U1_selisih_harga_mengendap_di_grir(klien, kepala_admin, db, bahan):
    po = await buat_po(db, bahan)
    await terima(klien, kepala_admin, db, bahan, po, 100)
    r = await tagih(klien, bahan, po, 100, 11_000, setujui=kepala_admin)
    je = await jurnal_aktif("vendor_bill", r.json()["id"])
    print("LAMA U1 jurnal faktur:", baris(je[0]), "sisa GR/IR PO:", await sisa_po(po["id"]))


async def test_lama_U5_retur_sebelum_tagih_bisa_ditagih_lagi(klien, kepala_admin, db, bahan):
    po = await buat_po(db, bahan, ppn=True)
    await terima(klien, kepala_admin, db, bahan, po, 100)
    rid = await retur(klien, bahan, po, 20, 10_000, setujui=kepala_admin)
    je = await jurnal_aktif("purchase_return", rid)
    print("LAMA U5 jurnal retur:", baris(je[0]))
    ctx = (await klien.get(f"/api/purchase-orders/{po['id']}/billing-context", headers=kepala_admin)).json()
    print("LAMA U5 billable_received:", ctx["items"][0]["billable_received"])
    r = await tagih(klien, bahan, po, 100, 10_000)
    print("LAMA U5 faktur 100 m:", r.status_code, r.json().get("status"))
    print("LAMA U5 sisa GR/IR PO:", await sisa_po(po["id"]))
