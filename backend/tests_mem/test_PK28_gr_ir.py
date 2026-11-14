"""PK-28 (IV-03) — akun GR/IR (2-1150) kembali nol per PO: selisih harga faktur, retur sebelum ditagih, umur, kliring.

Lihat docs/blueprint/unit/PK-28.md. Persiapan bersama: PT `ent_ksc`; PO satu baris 100 m @ Rp 10.000 tanpa diskon
(fixture PO disisipkan langsung); akun fixture `5-9920 "Uji selisih harga"`. "Terpetakan" = `pembelian.selisih_harga`
→ 5-9920 lapisan `ent_ksc` (`gl_mapping_service.set_mapping`, fixture). Alur (lewat API): penerimaan gudang
(`POST /api/inbound/tasks/{id}/complete`), faktur (`POST /api/vendor-bills` oleh akun pembuat, setujui oleh admin = akun
kedua), retur beli (`POST /api/purchase-returns` + setujui admin), tutup-kurang, daftar & kliring GR/IR. U8 dan U10
memakai fixture penerimaan yang memanggil `post_goods_receipt` (PO tetap berstatus berjalan). U15 (dua kliring bersamaan)
di MongoDB asli: backend/tests/test_bp_PK28_kliring_bersamaan_mongo.py.

Angka harapan dihitung tangan di komentar tiap uji (masukan → langkah → hasil).
"""
import uuid
from contextlib import asynccontextmanager

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, jurnal, jumlah, saldo_akun

KSC = "ent_ksc"
AKUN = "5-9920"
KUNCI = "pembelian.selisih_harga"
GRIR, HUTANG, PERSEDIAAN, PPN_IN = "2-1150", "2-1100", "1-1300", "1-1500"
DAFTAR = "/api/finance/gr-ir"


def uid(awalan: str) -> str:
    return f"{awalan}_pk28_{uuid.uuid4().hex[:8]}"


def baris(je):
    """{akun: (debit, kredit)} — satu jurnal."""
    out = {}
    for ln in je["lines"]:
        d, c = out.get(ln["account_code"], (0.0, 0.0))
        out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2), round(c + float(ln.get("credit") or 0), 2))
    return out


async def jurnal_aktif(source_type: str, source_id: str):
    from db import db
    return await db.journal_entries.find(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}}, {"_id": 0}).to_list(20)


async def sisa_po(po_id: str, eid: str = KSC) -> float:
    """Saldo kredit GR/IR satu PO (kredit − debit) langsung dari buku besar."""
    from db import db
    sid = [po_id]
    for coll in ("wms_tasks", "vendor_bills", "purchase_returns"):
        sid += [d["id"] async for d in db[coll].find({"po_id": po_id}, {"_id": 0, "id": 1})]
    tot = 0.0
    async for je in db.journal_entries.find({"entity_id": eid, "status": {"$ne": "void"},
                                            "$or": [{"ref.po_id": po_id}, {"source_id": {"$in": sid}}]}):
        for ln in je["lines"]:
            if ln["account_code"] == GRIR:
                tot += float(ln.get("credit") or 0) - float(ln.get("debit") or 0)
    return round(tot, 2)


# ── Fixture bersama ──────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def bahan(db, akun, sesi):
    """Produk, gudang, pemasok, akun 5-9920, dan akun pembuat dokumen (≠ admin penyetuju)."""
    pid, wid, sid = uid("prd"), uid("wh"), uid("sup")
    await db.products.insert_one({"id": pid, "name": "Kain Uji PK-28", "sku": f"SKU-{pid}", "base_unit": "meter",
                                  "harga_pokok": 10_000, "price": 15_000, "is_active": True})
    await db.warehouses.insert_one({"id": wid, "name": "Gudang Uji PK-28", "entity_id": KSC, "is_active": True})
    await db.suppliers.insert_one({"id": sid, "name": "Pemasok Uji PK-28", "is_active": True, "entity_id": KSC})
    if not await db.gl_accounts.find_one({"code": AKUN}):
        await db.gl_accounts.insert_one({
            "id": uid("gla"), "code": AKUN, "name": "Uji selisih harga", "type": "expense", "normal_balance": "debit",
            "parent_code": "5-0000", "is_postable": True, "is_active": True, "entity_id": None,
            "created_at": now_iso()})
    pembuat = await akun("manager")
    return {"pid": pid, "wid": wid, "sid": sid, "h_buat": await sesi(pembuat)}


async def petakan(eid: str = KSC) -> None:
    from services import gl_mapping_service as glm
    await glm.set_mapping(KUNCI, eid, AKUN, "uji PK-28 terpetakan", AKTOR_UJI)


async def lepas_peta(eid: str = KSC) -> None:
    from services import gl_mapping_service as glm
    if (await glm.resolve(KUNCI, eid))["source"] == "entity":
        await glm.reset_mapping(KUNCI, eid, "uji PK-28 lepas pemetaan", AKTOR_UJI)


@asynccontextmanager
async def terpetakan(eid: str = KSC):
    await petakan(eid)
    try:
        yield
    finally:
        await lepas_peta(eid)


async def buat_po(db, bahan, *, qty=100.0, harga=10_000.0, ppn=False, diskon_baris=0.0, diskon_kepala=0.0,
                  status="approved", eid=KSC):
    pid = uid("po")
    sub = round(qty * harga, 2)
    lt = round(sub * (1 - diskon_baris / 100), 2)
    net = round(lt * (1 - diskon_kepala / 100), 2)
    ppn_amt = round(net * 0.11, 2) if ppn else 0.0
    po = {"id": pid, "po_number": f"PO/PK28/{pid[-8:]}", "entity_id": eid, "status": status,
          "supplier_id": bahan["sid"], "supplier_name": "Pemasok Uji PK-28", "warehouse_id": bahan["wid"],
          "warehouse_name": "Gudang Uji PK-28", "tax_mode": "ppn" if ppn else "non_ppn",
          "items": [{"line_id": "L1", "product_id": bahan["pid"], "sku": f"SKU-{bahan['pid']}",
                     "product_name": "Kain Uji PK-28", "unit": "meter", "quantity": qty, "price": harga,
                     "discount_percent": diskon_baris, "subtotal": sub, "line_total": lt, "received_qty": 0.0}],
          "total_amount": sub, "order_discount_percent": diskon_kepala, "net_subtotal": net, "dpp": net,
          "ppn_amount": ppn_amt, "grand_total": round(net + ppn_amt, 2), "timeline": [], "created_at": now_iso()}
    await db.purchase_orders.insert_one(dict(po))
    return po


async def terima(klien, h, db, bahan, po, qty: float) -> str:
    """Penerimaan lewat alur gudang (`complete_task`): roll lahir, `received_qty` PO naik, jurnal Dr 1-1300 / Cr 2-1150."""
    tid = uid("tsk")
    await db.wms_tasks.insert_one({
        "id": tid, "flow_type": "inbound", "status": "qc_check", "po_id": po["id"], "po_number": po["po_number"],
        "product_id": bahan["pid"], "warehouse_id": bahan["wid"], "entity_id": po["entity_id"], "quantity": qty,
        "received_qty": qty, "unit": "meter", "legacy_in_flight": True, "supplier_dn_number": f"SJ-{tid[-6:]}",
        "created_at": now_iso()})
    r = await klien.post(f"/api/inbound/tasks/{tid}/complete", headers=h, json={})
    assert r.status_code == 200, r.text
    return tid


async def terima_fixture(db, po, qty: float, harga: float = 10_000.0) -> str:
    """Fixture penerimaan: `post_goods_receipt` dengan nilai yang sama dengan alur gudang (PO TIDAK berubah status)."""
    from services import gl_service as gl
    tid = uid("tsk")
    await db.wms_tasks.insert_one({"id": tid, "flow_type": "inbound", "status": "completed", "po_id": po["id"],
                                   "entity_id": po["entity_id"], "quantity": qty, "created_at": now_iso()})
    await db.purchase_orders.update_one({"id": po["id"]}, {"$inc": {"items.0.received_qty": qty}})
    await gl.post_goods_receipt(task_id=tid, entity_id=po["entity_id"], amount=round(qty * harga, 2),
                                label=po["po_number"], po_id=po["id"])
    return tid


async def tagih(klien, bahan, po, qty: float, harga: float, *, setujui=None):
    """Faktur dari akun pembuat (`submit_now`); bila menunggu persetujuan → disetujui `setujui` (akun kedua)."""
    r = await klien.post("/api/vendor-bills", headers=bahan["h_buat"], json={
        "po_id": po["id"], "supplier_invoice_no": uid("INV"), "submit_now": True,
        "items": [{"product_id": bahan["pid"], "po_line_id": "L1", "billed_qty": qty, "price": harga}]})
    if r.status_code != 200 or r.json().get("status") != "pending_approval" or setujui is None:
        return r
    return await klien.post(f"/api/vendor-bills/{r.json()['id']}/approve", headers=setujui)


async def retur(klien, bahan, po, qty: float, harga: float, *, setujui):
    """Retur beli presisi: roll PO itu (penerimaan ber-QC → roll `quarantine`, barang cacat dari pemeriksaan)."""
    from db import db
    roll = await db.inventory_rolls.find_one({"po_id": po["id"], "status": {"$in": ["available", "quarantine"]},
                                             "length_remaining": {"$gte": qty}}, {"_id": 0, "id": 1})
    assert roll, "fixture: roll PO tidak ada"
    r = await klien.post("/api/purchase-returns", headers=bahan["h_buat"], json={
        "po_id": po["id"], "warehouse_id": bahan["wid"], "submit_now": True, "reason": "cacat",
        "items": [{"product_id": bahan["pid"], "quantity": qty, "unit": "meter", "price": harga,
                   "reason": "cacat", "condition": "damaged", "roll_ids": [roll["id"]]}]})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    r2 = await klien.post(f"/api/purchase-returns/{rid}/approve", headers=setujui, json={})
    assert r2.status_code == 200, r2.text
    return rid


async def daftar(klien, h, **q):
    r = await klien.get(DAFTAR, headers=h, params=q)
    assert r.status_code == 200, r.text
    return r.json()


def baris_po(isi, po_id):
    return next((it for it in isi["items"] if it["po_id"] == po_id), None)


async def faktur(db, bill_id):
    return await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0})


async def tutup_kurang(klien, h, po):
    r = await klien.post(f"/api/purchase-orders/{po['id']}/close", headers=h, json={"reason": "sisa tidak dikirim"})
    assert r.status_code == 200, r.text
    return r.json()


async def kliring(klien, h, po, alasan="satu meter tidak ditagih pemasok"):
    return await klien.post(f"{DAFTAR}/{po['id']}/clear", headers=h, json={"reason": alasan})


MENUNGGU_B = pytest.mark.xfail(strict=True, reason="IV-03 — serah-terima (b) PK-28 belum mengalihkan pemanggil")


# ── U1–U4 — selisih harga faktur ─────────────────────────────────────────────────────────────────────────────────────
@MENUNGGU_B
async def test_PK28_U1_faktur_lebih_mahal_selisih_ke_akun_selisih(klien, kepala_admin, db, bahan):
    """Terima 100 m × 10.000 = 1.000.000 (Dr 1-1300 / Cr 2-1150). Faktur 100 m @ 11.000 = 1.100.000 (tanpa PPN):
    GR/IR dihapus 100 × 10.000 = 1.000.000; selisih 1.100.000 − 1.000.000 = 100.000 → Dr 5-9920. Saldo 2-1150 PO = 0."""
    async with terpetakan():
        po = await buat_po(db, bahan)
        tid = await terima(klien, kepala_admin, db, bahan, po, 100)
        gr = await jurnal_aktif("goods_receipt", tid)
        assert len(gr) == 1 and baris(gr[0]) == {PERSEDIAAN: (1_000_000, 0), GRIR: (0, 1_000_000)}
        assert gr[0]["ref"]["po_id"] == po["id"]
        r = await tagih(klien, bahan, po, 100, 11_000, setujui=kepala_admin)
        assert r.status_code == 200 and r.json()["status"] == "posted", r.text
        vb = await faktur(db, r.json()["id"])
        je = await jurnal_aktif("vendor_bill", vb["id"])
        assert len(je) == 1 and baris(je[0]) == {GRIR: (1_000_000, 0), AKUN: (100_000, 0), HUTANG: (0, 1_100_000)}
        assert je[0]["ref"]["po_id"] == po["id"]
        assert (vb["grir_amount"], vb["price_variance_amount"], vb["price_variance_posted"]) == (1_000_000, 100_000, True)
        assert await sisa_po(po["id"]) == 0


@MENUNGGU_B
async def test_PK28_U2_faktur_ber_ppn_selisih_dan_ppn_masukan(klien, kepala_admin, db, bahan):
    """PO ber-PPN 11 %. Faktur 100 m @ 11.000: neto 1.100.000, PPN 11 % = 121.000, total 1.221.000.
    Jurnal: Dr 2-1150 1.000.000 + Dr 5-9920 100.000 + Dr 1-1500 121.000 = Cr 2-1100 1.221.000."""
    async with terpetakan():
        po = await buat_po(db, bahan, ppn=True)
        await terima(klien, kepala_admin, db, bahan, po, 100)
        r = await tagih(klien, bahan, po, 100, 11_000, setujui=kepala_admin)
        assert r.status_code == 200 and r.json()["status"] == "posted", r.text
        vb = await faktur(db, r.json()["id"])
        assert (vb["net_subtotal"], vb["ppn_amount"], vb["grand_total"]) == (1_100_000, 121_000, 1_221_000)
        je = await jurnal_aktif("vendor_bill", vb["id"])
        assert baris(je[0]) == {GRIR: (1_000_000, 0), AKUN: (100_000, 0), PPN_IN: (121_000, 0),
                                HUTANG: (0, 1_221_000)}
        assert await sisa_po(po["id"]) == 0


@MENUNGGU_B
async def test_PK28_U3_faktur_lebih_murah_selisih_dikredit(klien, kepala_admin, db, bahan):
    """Faktur 100 m @ 9.500 = 950.000: GR/IR 1.000.000 dihapus; selisih 950.000 − 1.000.000 = −50.000 → Cr 5-9920."""
    async with terpetakan():
        po = await buat_po(db, bahan)
        await terima(klien, kepala_admin, db, bahan, po, 100)
        r = await tagih(klien, bahan, po, 100, 9_500, setujui=kepala_admin)
        assert r.status_code == 200 and r.json()["status"] == "posted", r.text
        je = await jurnal_aktif("vendor_bill", r.json()["id"])
        assert baris(je[0]) == {GRIR: (1_000_000, 0), AKUN: (0, 50_000), HUTANG: (0, 950_000)}
        vb = await faktur(db, r.json()["id"])
        assert (vb["price_variance_amount"], vb["price_variance_posted"]) == (-50_000, True)
        assert await sisa_po(po["id"]) == 0


@MENUNGGU_B
async def test_PK28_U4_tanpa_pemetaan_perilaku_lama_dan_terlihat_di_daftar(klien, kepala_admin, db, bahan):
    """Akun selisih belum diatur → jurnal lama Dr 2-1150 1.100.000 / Cr 2-1100 1.100.000; sisa PO = 1.000.000 −
    1.100.000 = −100.000 (saldo debit) dan selisih belum terposting 100.000 tampil di daftar GR/IR."""
    await lepas_peta()
    po = await buat_po(db, bahan)
    await terima(klien, kepala_admin, db, bahan, po, 100)
    r = await tagih(klien, bahan, po, 100, 11_000, setujui=kepala_admin)
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    je = await jurnal_aktif("vendor_bill", r.json()["id"])
    assert baris(je[0]) == {GRIR: (1_100_000, 0), HUTANG: (0, 1_100_000)}
    vb = await faktur(db, r.json()["id"])
    assert (vb["price_variance_amount"], vb["price_variance_posted"]) == (100_000, False)
    it = baris_po(await daftar(klien, kepala_admin), po["id"])
    assert (it["balance"], it["unposted_variance"]) == (-100_000, 100_000), it
    assert it["can_clear"] is False   # akun selisih belum diatur


# ── U5–U7 — retur beli sebelum/sesudah ditagih ───────────────────────────────────────────────────────────────────────
@MENUNGGU_B
async def test_PK28_U5_retur_sebelum_ditagih_dasar_grir_tanpa_ppn(klien, kepala_admin, db, bahan):
    """PO ber-PPN 11 %, terima 100 m (GR/IR kredit 1.000.000). Retur 20 m × 10.000 = 200.000 sebelum ada faktur → dasar
    GR/IR: Dr 2-1150 200.000 / Cr 1-1300 200.000, TANPA PPN (PPN masukan belum pernah dicatat). Boleh tagih = 100 − 20
    = 80. Faktur 100 m ditolak; faktur 80 m: Dr 2-1150 800.000 + Dr 1-1500 88.000 (11 % × 800.000) = Cr 2-1100 888.000.
    Sisa 2-1150 PO = 1.000.000 − 200.000 − 800.000 = 0; 1-1500 naik 88.000."""
    po = await buat_po(db, bahan, ppn=True)
    await terima(klien, kepala_admin, db, bahan, po, 100)
    ppn0 = await saldo_akun(PPN_IN, KSC)
    rid = await retur(klien, bahan, po, 20, 10_000, setujui=kepala_admin)
    ret = await db.purchase_returns.find_one({"id": rid}, {"_id": 0})
    assert ret["ap_basis"] == "gr_ir"
    je = await jurnal_aktif("purchase_return", rid)
    assert baris(je[0]) == {GRIR: (200_000, 0), PERSEDIAAN: (0, 200_000)}
    assert je[0]["ref"]["po_id"] == po["id"]
    ctx = (await klien.get(f"/api/purchase-orders/{po['id']}/billing-context", headers=kepala_admin)).json()
    assert (ctx["items"][0]["returned_unbilled_qty"], ctx["items"][0]["billable_received"]) == (20, 80)
    r100 = await tagih(klien, bahan, po, 100, 10_000)
    assert r100.status_code == 400 and "3-way match GAGAL" in r100.json()["detail"], r100.text
    r80 = await tagih(klien, bahan, po, 80, 10_000)
    assert r80.status_code == 200 and r80.json()["status"] == "posted", r80.text
    jb = await jurnal_aktif("vendor_bill", r80.json()["id"])
    assert baris(jb[0]) == {GRIR: (800_000, 0), PPN_IN: (88_000, 0), HUTANG: (0, 888_000)}
    assert await sisa_po(po["id"]) == 0
    assert round(await saldo_akun(PPN_IN, KSC) - ppn0, 2) == 88_000


@MENUNGGU_B
async def test_PK28_U6_retur_sesudah_ditagih_penuh_dasar_hutang(klien, kepala_admin, db, bahan):
    """Terima 100 m, faktur 100 m @ 10.000 + PPN 11 % diposting. Retur 20 m: dasar hutang, jurnal seperti sekarang —
    Dr 2-1100 222.000 / Cr 1-1300 200.000 / Cr 1-1500 22.000 (pembalik PPN). Boleh tagih tetap 100 − 100 = 0."""
    po = await buat_po(db, bahan, ppn=True)
    await terima(klien, kepala_admin, db, bahan, po, 100)
    r = await tagih(klien, bahan, po, 100, 10_000)
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    rid = await retur(klien, bahan, po, 20, 10_000, setujui=kepala_admin)
    ret = await db.purchase_returns.find_one({"id": rid}, {"_id": 0})
    assert ret["ap_basis"] == "hutang"
    je = await jurnal_aktif("purchase_return", rid)
    assert baris(je[0]) == {HUTANG: (222_000, 0), PERSEDIAAN: (0, 200_000), PPN_IN: (0, 22_000)}
    ctx = (await klien.get(f"/api/purchase-orders/{po['id']}/billing-context", headers=kepala_admin)).json()
    assert (ctx["items"][0]["returned_unbilled_qty"], ctx["items"][0]["billable_received"]) == (0, 0)


@MENUNGGU_B
async def test_PK28_U7_retur_sesudah_ditagih_sebagian_dasar_hutang(klien, kepala_admin, db, bahan):
    """Terima 100 m, faktur 60 m diposting, retur 20 m → dasar hutang (ada faktur terposting); retur tidak mengurangi
    boleh-tagih: 100 − 60 = 40."""
    po = await buat_po(db, bahan)
    await terima(klien, kepala_admin, db, bahan, po, 100)
    r = await tagih(klien, bahan, po, 60, 10_000)
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    rid = await retur(klien, bahan, po, 20, 10_000, setujui=kepala_admin)
    assert (await db.purchase_returns.find_one({"id": rid}))["ap_basis"] == "hutang"
    ctx = (await klien.get(f"/api/purchase-orders/{po['id']}/billing-context", headers=kepala_admin)).json()
    assert (ctx["items"][0]["returned_unbilled_qty"], ctx["items"][0]["billable_received"]) == (0, 40)


# ── U8 — daftar GR/IR, umur, dan pencocokan dengan buku besar ────────────────────────────────────────────────────────
async def test_PK28_U8_daftar_per_po_dan_saldo_buku_besar(klien, kepala_admin, db, bahan):
    """PT `ent_kanda` (tidak dipakai uji lain di modul ini → total tidak tercampur). Terima 100 m × 10.000 (fixture, PO tetap `receiving`)
    → sisa PO 1.000.000, umur 0 hari. Jurnal manual Dr 2-1150 5.000 / Cr 6-9000 5.000 tanpa PO → tak terhubung −5.000.
    Buku besar 2-1150 = 1.000.000 − 5.000 = 995.000 = total sisa + tak terhubung."""
    from services.book_date import tanggal_buku
    eid = "ent_kanda"
    h = {**kepala_admin, "X-Entity-Id": eid}
    po = await buat_po(db, bahan, status="receiving", eid=eid)
    tid = await terima_fixture(db, po, 100)
    assert (await jurnal_aktif("goods_receipt", tid))[0]["ref"]["po_id"] == po["id"]
    await jurnal(eid, tanggal_buku(), [(GRIR, 5_000, 0), ("6-9000", 0, 5_000)], "Uji jurnal tanpa PO", uid("man"))
    isi = await daftar(klien, h)
    it = baris_po(isi, po["id"])
    assert (it["received_value"], it["billed_value"], it["returned_value"], it["cleared_value"]) == (1_000_000, 0, 0, 0)
    assert (it["balance"], it["bucket"], it["age_days"], it["can_clear"]) == (1_000_000, "0-30", 0, False), it
    assert it["po_number"] == po["po_number"] and it["supplier_name"] == "Pemasok Uji PK-28"
    assert it["link"]["focus_id"] == po["id"]
    assert (isi["total_balance"], isi["unlinked_balance"], isi["ledger_balance"]) == (1_000_000, -5_000, 995_000)
    assert round(isi["total_balance"] + isi["unlinked_balance"], 2) == isi["ledger_balance"] == await saldo_akun(GRIR, eid)
    assert isi["total"] == 1 and len(isi["items"]) == 1
    # saringan umur & sakelar "tampilkan yang sudah nol" (server)
    assert (await daftar(klien, h, bucket=">90"))["total"] == 0
    assert (await daftar(klien, h, bucket="0-30"))["total"] == 1
    assert (await daftar(klien, h, q=po["po_number"][-6:]))["total"] == 1
    # "Semua PT" ditolak dengan petunjuk
    r = await klien.get(DAFTAR, headers={**kepala_admin, "X-Entity-Id": "all"})
    assert r.status_code == 400 and r.json()["detail"] == "Pilih satu PT untuk melihat GR/IR.", r.text


# ── U9–U12 — kliring ─────────────────────────────────────────────────────────────────────────────────────────────────
async def _po_sisa_satu_meter(klien, kepala_admin, db, bahan):
    """PO 100 m: terima 60 m (Cr 2-1150 600.000), faktur 59 m @ 10.000 (Dr 2-1150 590.000), tutup-kurang → sisa
    600.000 − 590.000 = 10.000 (kredit)."""
    po = await buat_po(db, bahan)
    await terima(klien, kepala_admin, db, bahan, po, 60)
    r = await tagih(klien, bahan, po, 59, 10_000)
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    await tutup_kurang(klien, kepala_admin, po)
    assert await sisa_po(po["id"]) == 10_000
    return po


async def test_PK28_U9_kliring_sisa_kredit_lalu_nol(klien, kepala_admin, db, bahan):
    """Sisa kredit 10.000 → Dr 2-1150 10.000 / Cr 5-9920 10.000; sisa 0; ulang → 409 "sudah nol"."""
    async with terpetakan():
        po = await _po_sisa_satu_meter(klien, kepala_admin, db, bahan)
        it = baris_po(await daftar(klien, kepala_admin), po["id"])
        assert it["balance"] == 10_000 and it["can_clear"] is True and it["po_status"] == "closed_short"
        r = await kliring(klien, kepala_admin, po)
        assert r.status_code == 200, r.text
        assert r.json()["clearing"]["gl_status"] == "posted" and r.json()["balance"] == 0
        je = await jurnal_aktif("grir_clearing", f"{po['id']}:1")
        assert len(je) == 1 and baris(je[0]) == {GRIR: (10_000, 0), AKUN: (0, 10_000)}
        assert je[0]["ref"]["po_id"] == po["id"]
        doc = await db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
        c = doc["grir_clearings"][0]
        assert (c["seq"], c["amount"], c["direction"], c["gl_status"], c["journal_entry_id"]) == (
            1, 10_000, "debit_grir", "posted", je[0]["id"])
        assert c["reason"] == "satu meter tidak ditagih pemasok" and c["by"] and c["at"]
        assert await sisa_po(po["id"]) == 0
        it = baris_po(await daftar(klien, kepala_admin), po["id"])
        assert it is None   # daftar "terbuka" tidak lagi memuat PO bersisa nol
        it = baris_po(await daftar(klien, kepala_admin, status="semua"), po["id"])
        assert (it["cleared_value"], it["balance"], it["can_clear"]) == (10_000, 0, False)
        r2 = await kliring(klien, kepala_admin, po)
        assert r2.status_code == 409 and r2.json()["detail"] == f"Sisa GR/IR PO {po['po_number']} sudah nol.", r2.text


async def test_PK28_U10_po_masih_berjalan_ditolak_tanpa_tulisan(klien, kepala_admin, db, bahan):
    async with terpetakan():
        po = await buat_po(db, bahan, status="receiving")
        await terima_fixture(db, po, 40)
        je0 = await jumlah("journal_entries", {})
        r = await kliring(klien, kepala_admin, po)
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == (
            f"PO {po['po_number']} masih berjalan (status sedang diterima). Kliring GR/IR hanya untuk PO yang sudah "
            "selesai, ditutup-kurang, atau dibatalkan.")
        assert "grir_clearings" not in await db.purchase_orders.find_one({"id": po["id"]})
        assert await jumlah("journal_entries", {}) == je0


async def test_PK28_U10b_pemeriksaan_lain_tanpa_tulisan(klien, kepala_admin, db, bahan):
    """Alasan pendek → 400; faktur draf → 409; akun selisih belum diatur → 409 — tidak ada tulisan."""
    po = await buat_po(db, bahan, status="completed")
    await terima_fixture(db, po, 100)
    je0 = await jumlah("journal_entries", {})
    r = await kliring(klien, kepala_admin, po, alasan="ok")
    assert r.status_code == 400 and r.json()["detail"] == "Alasan kliring wajib diisi (minimal 5 huruf).", r.text
    await lepas_peta()
    r = await kliring(klien, kepala_admin, po)
    assert r.status_code == 409 and r.json()["detail"] == (
        'Akun "Selisih harga pembelian" belum diatur untuk PT ini. Isi di Pengaturan › Keuangan & Pajak › '
        "Pemetaan Akun."), r.text
    async with terpetakan():
        await db.vendor_bills.insert_one({"id": uid("vb"), "bill_number": "VB/PK28/DRAF", "po_id": po["id"],
                                          "entity_id": KSC, "status": "draft", "items": [], "created_at": now_iso()})
        r = await kliring(klien, kepala_admin, po)
        assert r.status_code == 409 and r.json()["detail"] == (
            f"Masih ada faktur pemasok untuk PO {po['po_number']} yang belum diposting (VB/PK28/DRAF). Selesaikan dulu.")
    assert "grir_clearings" not in await db.purchase_orders.find_one({"id": po["id"]})
    assert await jumlah("journal_entries", {}) == je0


async def test_PK28_U11_kliring_sisa_debit(klien, kepala_admin, db, bahan):
    """Terima 100 m (Cr 1.000.000); faktur 100 m @ 10.050 tanpa pemetaan (+0,5 %, dalam toleransi) → Dr 2-1150 1.005.000
    → sisa debit −5.000. Dipetakan lalu dikliring: Dr 5-9920 5.000 / Cr 2-1150 5.000, arah `kredit_grir`."""
    await lepas_peta()
    po = await buat_po(db, bahan)
    await terima(klien, kepala_admin, db, bahan, po, 100)
    r = await tagih(klien, bahan, po, 100, 10_050)
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    assert (await db.purchase_orders.find_one({"id": po["id"]}))["status"] == "completed"
    assert await sisa_po(po["id"]) == -5_000
    async with terpetakan():
        r = await kliring(klien, kepala_admin, po, alasan="selisih harga lama sebelum akun diatur")
        assert r.status_code == 200, r.text
        assert r.json()["clearing"]["direction"] == "kredit_grir" and r.json()["clearing"]["amount"] == 5_000
        je = await jurnal_aktif("grir_clearing", f"{po['id']}:1")
        assert len(je) == 1 and baris(je[0]) == {AKUN: (5_000, 0), GRIR: (0, 5_000)}
        assert await sisa_po(po["id"]) == 0


async def test_PK28_U12_jurnal_kliring_gagal_lalu_ulang_tepat_sekali(klien, kepala_admin, db, bahan, paksa_jurnal_gagal):
    async with terpetakan():
        po = await _po_sisa_satu_meter(klien, kepala_admin, db, bahan)
        async with paksa_jurnal_gagal("sisip", source_type="grir_clearing") as gagal:
            r = await kliring(klien, kepala_admin, po)
        assert r.status_code == 200 and len(gagal) == 1, r.text
        assert r.json()["clearing"]["gl_status"] == "failed" and "dipaksa gagal" in r.json()["clearing"]["gl_error"]
        doc = await db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
        assert doc["grir_clearings"][0]["gl_status"] == "failed" and doc["grir_clearings"][0]["gl_failed_at"]
        assert await jurnal_aktif("grir_clearing", f"{po['id']}:1") == []
        p = (await klien.get("/api/finance/posting-failures", headers=kepala_admin,
                             params={"kind": "grir_clearing"})).json()
        assert p["counts"]["grir_clearing"] == 1 and p["labels"]["grir_clearing"] == "Kliring GR/IR"
        row = p["items"][0]
        assert (row["id"], row["amount"], row["number"]) == (f"{po['id']}:1", 10_000, f"{po['po_number']} · kliring 1")
        assert row["link"]["focus_id"] == po["id"]
        # ulang dari panel dua kali → tepat satu jurnal
        r1 = await klien.post(f"/api/finance/posting-failures/grir_clearing/{po['id']}:1/retry", headers=kepala_admin)
        r2 = await klien.post(f"/api/finance/posting-failures/grir_clearing/{po['id']}:1/retry", headers=kepala_admin)
        assert r1.status_code == 200 and r1.json()["gl_status"] == "posted", r1.text
        assert r2.status_code == 404, r2.text
        je = await jurnal_aktif("grir_clearing", f"{po['id']}:1")
        assert len(je) == 1 and baris(je[0]) == {GRIR: (10_000, 0), AKUN: (0, 10_000)}
        assert r1.json()["journal_entry_id"] == je[0]["id"]
        assert await sisa_po(po["id"]) == 0


async def test_PK28_U12b_kliring_gagal_menahan_kliring_baru(klien, kepala_admin, db, bahan, paksa_jurnal_gagal):
    """Tambahan (bukan baris tabel): unsur kliring yang jurnalnya gagal belum mengubah buku besar; kliring baru selama
    itu = jurnal ganda saat unsur pertama diulang. Ditolak 409 sampai unsur itu diulang dari Posting Gagal."""
    async with terpetakan():
        po = await _po_sisa_satu_meter(klien, kepala_admin, db, bahan)
        async with paksa_jurnal_gagal("sisip", source_type="grir_clearing"):
            assert (await kliring(klien, kepala_admin, po)).json()["clearing"]["gl_status"] == "failed"
        r = await kliring(klien, kepala_admin, po)
        assert r.status_code == 409 and r.json()["detail"] == (
            f"Kliring GR/IR sebelumnya untuk PO {po['po_number']} belum terjurnal. Ulang dari Tutup Buku › "
            "Posting Gagal dulu."), r.text
        assert len((await db.purchase_orders.find_one({"id": po["id"]}))["grir_clearings"]) == 1
        # unsur `pending` (proses lain sedang menjurnal) → pesan spesifikasi
        await db.purchase_orders.update_one({"id": po["id"]}, {"$set": {"grir_clearings.0.gl_status": "pending"}})
        r = await kliring(klien, kepala_admin, po)
        assert r.status_code == 409 and r.json()["detail"] == (
            f"Kliring GR/IR PO {po['po_number']} sedang diproses. Muat ulang."), r.text


# ── U13 — izin ───────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PK28_U13_lihat_dengan_vendor_bill_view_kliring_butuh_accounting_manage(
        klien, db, bahan, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong):
    peran = await peran_tanpa_acuan({"vendor_bill": ["view"]}, label="Tanpa Acuan PK-28")
    u = await akun(peran)
    h = await sesi(u)
    po = await buat_po(db, bahan, status="completed")
    await terima_fixture(db, po, 10)
    r = await klien.get(DAFTAR, headers=h)
    assert r.status_code == 200, r.text
    r = await kliring(klien, h, po)
    assert r.status_code == 403, r.text
    kosong = await sesi(await akun(await peran_manajer_kosong()))
    assert (await klien.get(DAFTAR, headers=kosong)).status_code == 403
    assert "grir_clearings" not in await db.purchase_orders.find_one({"id": po["id"]})


# ── U14 — harga neto baris PO tidak berubah sesudah dipindah ─────────────────────────────────────────────────────────
async def test_PK28_U14_harga_neto_baris_po_dipakai_penerimaan(klien, kepala_admin, db, bahan):
    """PO 100 m @ 10.000, diskon baris 5 %, diskon kepala 2 %: neto = 10.000 × 0,95 × 0,98 = 9.310 (line_total
    950.000 ÷ 100 = 9.500; × 0,98). Terima 50 m → 50 × 9.310 = 465.500 (Dr 1-1300 / Cr 2-1150)."""
    po = await buat_po(db, bahan, diskon_baris=5, diskon_kepala=2)
    tid = await terima(klien, kepala_admin, db, bahan, po, 50)
    je = await jurnal_aktif("goods_receipt", tid)
    assert len(je) == 1 and baris(je[0]) == {PERSEDIAAN: (465_500, 0), GRIR: (0, 465_500)}
    from services.po_pricing import po_line_net_unit_price
    fresh = await db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    assert po_line_net_unit_price(fresh, line_id="L1") == 9_310
    assert po_line_net_unit_price(fresh, product_id=bahan["pid"]) == 9_310
    # tanpa line_total: price × (1 − diskon baris) × (1 − diskon kepala)
    tanpa_lt = {**fresh, "items": [{k: v for k, v in fresh["items"][0].items() if k != "line_total"}]}
    assert po_line_net_unit_price(tanpa_lt, line_id="L1") == 9_310
    assert po_line_net_unit_price(fresh, line_id="L9", product_id=bahan["pid"]) == 9_310   # baris tak dikenal → produk
    assert po_line_net_unit_price(fresh, line_id="L9", product_id="prd_lain") == 0
