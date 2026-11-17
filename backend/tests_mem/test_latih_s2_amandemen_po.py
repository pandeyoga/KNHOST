"""S2 (pelatihan keuangan 18 Nov) — amandemen PO sesudah penerimaan sebagian & tagihan lebih tagih.

Uji jalan "Amandemen & situasi khusus pengadaan": PO 1.000 yard, pemasok hanya mengirim 600 (gudang eskalasi, manajer
menyesuaikan tugas ke 600, penerimaan diselesaikan), tagihan 600 diposting, lalu sisa PO ditutup lewat amandemen qty
1.000 → 600 (selalu persetujuan ulang) yang disetujui Admin. Temuan:
  U1/U2 — sesudah persetujuan PO tertulis "pending" (Menunggu barang) walau seluruh barang sudah diterima; ringkasan
          "Belum Ditagih" tetap dari nilai lama; tugas karantina (`qc_pending`) ditimpa harapan 0, dan bila QC sudah
          selesai lahir tugas BARU 600 yard ("tugas hantu" — barang yang sama bisa diterima dua kali).
  U3    — amandemen tanpa persetujuan (mis. tanggal kirim) atas PO terima sebagian → status "pending"; tugas sisa
          mengharapkan qty PENUH, bukan sisa.
  U1    — juga: amandemen tercatat "oleh Admin" walau dibuat Manajer (nama dari bawaan skema, pola C-15).
  U4    — [Kirim & Posting] tagihan lebih tagih ditolak 400 tetapi meninggalkan draf tersembunyi yang memegang No.
          faktur pemasok → tagihan yang sudah dikoreksi dengan nomor sama ditolak 409.
"""
import uuid

import pytest

from core_utils import now_iso

KSC = "ent_ksc"


def uid(awalan: str) -> str:
    return f"{awalan}_s2_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def bahan(db, akun, sesi):
    pid, wid, sid = uid("prd"), uid("wh"), uid("sup")
    await db.products.insert_one({"id": pid, "name": "Grey uji S2", "sku": f"S2-{pid[-6:]}", "base_unit": "yard",
                                  "stage": "grey", "status": "active", "lifecycle": "produksi", "harga_pokok": 10_000,
                                  "price": 15_000, "is_active": True, "created_at": now_iso()})
    await db.warehouses.insert_one({"id": wid, "name": "Gudang Uji S2", "entity_id": KSC, "is_active": True})
    await db.suppliers.insert_one({"id": sid, "name": "Pemasok Uji S2", "is_active": True, "status": "active",
                                   "entity_id": KSC})
    pembuat = await akun("manager")
    return {"pid": pid, "wid": wid, "sid": sid, "pembuat": pembuat, "h_buat": await sesi(pembuat)}


async def buat_po(db, bahan, qty=1000.0, harga=10_000.0):
    """PO berjalan (sudah disetujui) dibuat Manajer — persetujuan ulang wajib orang lain (Admin)."""
    pid = uid("po")
    sub = round(qty * harga, 2)
    ppn = round(sub * 0.11, 2)
    po = {"id": pid, "po_number": f"PO/S2/{pid[-8:]}", "entity_id": KSC, "status": "pending", "version": 1,
          "approval_status": "not_required", "supplier_id": bahan["sid"], "supplier_name": "Pemasok Uji S2",
          "warehouse_id": bahan["wid"], "warehouse_name": "Gudang Uji S2", "tax_mode": "ppn",
          "created_by": bahan["pembuat"]["name"], "created_by_id": bahan["pembuat"]["id"],
          "items": [{"line_id": "L1", "product_id": bahan["pid"], "sku": f"S2-{bahan['pid'][-6:]}",
                     "product_name": "Grey uji S2", "unit": "yard", "base_unit": "yard", "quantity": qty,
                     "price": harga, "discount_percent": 0, "subtotal": sub, "line_total": sub, "received_qty": 0.0}],
          "total_amount": sub, "order_discount_percent": 0, "net_subtotal": sub, "dpp": sub, "ppn_amount": ppn,
          "grand_total": round(sub + ppn, 2), "timeline": [], "updated_at": now_iso(), "created_at": now_iso()}
    await db.purchase_orders.insert_one(dict(po))
    return po


async def terima_sebagian(klien, h, db, bahan, po, qty: float) -> str:
    """Alur gudang lama sesudah eskalasi (manajer menyesuaikan tugas ke qty yang datang): tugas `qc_check` → complete."""
    tid = uid("tsk")
    await db.wms_tasks.insert_one({
        "id": tid, "flow_type": "inbound", "status": "qc_check", "po_id": po["id"], "po_number": po["po_number"],
        "product_id": bahan["pid"], "warehouse_id": bahan["wid"], "entity_id": KSC, "quantity": qty,
        "expected_qty": qty, "received_qty": qty, "unit": "yard", "legacy_in_flight": True,
        "supplier_dn_number": f"SJ-{tid[-6:]}", "created_at": now_iso()})
    r = await klien.post(f"/api/inbound/tasks/{tid}/complete", headers=h, json={})
    assert r.status_code == 200, r.text
    return tid


async def tagih(klien, bahan, po, qty: float, *, faktur: str = "", submit=True):
    return await klien.post("/api/vendor-bills", headers=bahan["h_buat"], json={
        "po_id": po["id"], "supplier_invoice_no": faktur or uid("INV"), "submit_now": submit,
        "items": [{"product_id": bahan["pid"], "po_line_id": "L1", "billed_qty": qty, "price": 10_000}]})


async def amandemen_ke(klien, bahan, po, qty: float, alasan: str):
    r = await klien.post(f"/api/purchase-orders/{po['id']}/amend", headers=bahan["h_buat"], json={
        "reason": alasan, "items": [{"product_id": bahan["pid"], "quantity": qty, "unit": "yard", "price": 10_000}]})
    assert r.status_code == 200, r.text
    return r.json()


async def tugas(db, po_id):
    return await db.wms_tasks.find({"po_id": po_id, "flow_type": "inbound"}, {"_id": 0}).to_list(20)


async def test_S2_U1_amandemen_ke_qty_diterima_sesudah_qc_po_selesai_tanpa_tugas_hantu(klien, kepala_admin, db, bahan):
    """PO 1.000 @ 10.000 + PPN 11 %; terima 600 (QC selesai → tugas `completed`); tagihan 600 = 600 × 10.000 × 1,11 =
    6.660.000. Amandemen 1.000 → 600 → menunggu persetujuan (qty ke qty diterima) → Admin setuju → PO SELESAI (600/600),
    tidak ada tugas penerimaan baru, Belum Ditagih = 6.660.000 − 6.660.000 = 0."""
    po = await buat_po(db, bahan)
    tid = await terima_sebagian(klien, kepala_admin, db, bahan, po, 600)
    await db.wms_tasks.update_one({"id": tid}, {"$set": {"status": "completed"}})   # SPK kedatangan sudah ditutup
    assert (await db.purchase_orders.find_one({"id": po["id"]}))["status"] == "partial"
    r = await tagih(klien, bahan, po, 600)
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    am = await amandemen_ke(klien, bahan, po, 600, "Pemasok hanya sanggup 600 yard")
    assert am["status"] == "waiting_approval" and "qty_to_received" in am["approval_reason"], am
    # Riwayat amandemen & timeline mencatat akun yang masuk (dulu "Admin" dari bawaan skema).
    assert am["amendments"][-1]["amended_by"] == bahan["pembuat"]["name"], am["amendments"][-1]["amended_by"]
    r = await klien.post(f"/api/purchase-orders/{po['id']}/approve", headers=kepala_admin, json={})
    assert r.status_code == 200, r.text
    d = await db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    assert d["status"] == "completed", d["status"]
    assert r.json()["status"] == "completed"
    assert (d["grand_total"], d["billed_total"], d["unbilled_total"]) == (6_660_000, 6_660_000, 0), d
    ts = await tugas(db, po["id"])
    assert [t["id"] for t in ts] == [tid], [(t["status"], t.get("expected_qty")) for t in ts]


async def test_S2_U2_tugas_karantina_tidak_ditimpa(klien, kepala_admin, db, bahan):
    """Sama dengan U1 tetapi SPK kedatangan belum ditutup (tugas `qc_pending`): harapan tugas tetap 600 (dulu 0)."""
    po = await buat_po(db, bahan)
    tid = await terima_sebagian(klien, kepala_admin, db, bahan, po, 600)
    t0 = await db.wms_tasks.find_one({"id": tid}, {"_id": 0})
    am = await amandemen_ke(klien, bahan, po, 600, "Pemasok hanya sanggup 600 yard")
    assert am["status"] == "waiting_approval"
    r = await klien.post(f"/api/purchase-orders/{po['id']}/approve", headers=kepala_admin, json={})
    assert r.status_code == 200, r.text
    t1 = await db.wms_tasks.find_one({"id": tid}, {"_id": 0})
    assert (t1["status"], t1["expected_qty"]) == (t0["status"], 600), (t1["status"], t1["expected_qty"])
    assert len(await tugas(db, po["id"])) == 1
    assert (await db.purchase_orders.find_one({"id": po["id"]}))["status"] == "completed"


async def test_S2_U3_amandemen_tanpa_persetujuan_status_tetap_terima_sebagian(klien, kepala_admin, db, bahan):
    """PO 1.000, terima 600 (QC selesai). Amandemen tanggal kirim saja (nilai di bawah ambang → tanpa persetujuan):
    status tetap "partial" (dulu "pending"); tugas sisa yang dibuat mengharapkan 1.000 − 600 = 400 (dulu 1.000)."""
    po = await buat_po(db, bahan)
    tid = await terima_sebagian(klien, kepala_admin, db, bahan, po, 600)
    await db.wms_tasks.update_one({"id": tid}, {"$set": {"status": "completed"}})
    r = await klien.post(f"/api/purchase-orders/{po['id']}/amend", headers=bahan["h_buat"], json={
        "reason": "Pemasok mengirim sisa minggu depan", "expected_delivery_date": "2026-11-30"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "partial", r.json()["status"]
    sisa = [t for t in await tugas(db, po["id"]) if t["id"] != tid]
    assert [(t["status"], t["expected_qty"]) for t in sisa] == [("waiting_goods", 400)], sisa


async def test_S2_U4_kirim_lebih_tagih_ditolak_tanpa_draf_tersembunyi(klien, kepala_admin, db, bahan):
    """Terima 600; [Kirim & Posting] tagihan 700 → 400 berpesan "lebih tagih" dan TIDAK ada tagihan tersimpan; tagihan
    yang dikoreksi (600) dengan No. faktur yang SAMA diterima (dulu 409 "sudah dipakai" oleh draf tersembunyi)."""
    po = await buat_po(db, bahan)
    await terima_sebagian(klien, kepala_admin, db, bahan, po, 600)
    no = uid("INV")
    r = await tagih(klien, bahan, po, 700, faktur=no)
    assert r.status_code == 400 and "lebih tagih" in r.json()["detail"], r.text
    assert "Tagih 700 melebihi sisa yang boleh ditagih 600" in r.json()["detail"], r.text
    assert await db.vendor_bills.count_documents({"po_id": po["id"]}) == 0
    r = await tagih(klien, bahan, po, 600, faktur=no)
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text


async def test_S2_U5_draf_lebih_tagih_menyebut_jalan_keluar(klien, kepala_admin, db, bahan):
    """Draf 700 (Simpan Draf) → [Kirim] ditolak 400: pesan menyebut batalkan draf & buat tagihan baru; draf tetap draf."""
    po = await buat_po(db, bahan)
    await terima_sebagian(klien, kepala_admin, db, bahan, po, 600)
    r = await tagih(klien, bahan, po, 700, submit=False)
    assert r.status_code == 200 and r.json()["status"] == "draft", r.text
    bid = r.json()["id"]
    r = await klien.post(f"/api/vendor-bills/{bid}/submit", headers=bahan["h_buat"], json={})
    assert r.status_code == 400 and "batalkan draf" in r.json()["detail"], r.text
    assert (await db.vendor_bills.find_one({"id": bid}))["status"] == "draft"


async def test_S2_U6_pesan_selisih_harga_gaya_indonesia(klien, kepala_admin, db, bahan):
    """Faktur 500 × Rp 15.000 atas PO Rp 10.000 (+50%) → menunggu persetujuan; pengecualian berbunyi "Harga Rp 15.000
    menyimpang +50% dari harga PO Rp 10.000 (toleransi ±5%)" (dulu "Harga 15000 menyimpang +50.0% … 10000")."""
    po = await buat_po(db, bahan)
    await terima_sebagian(klien, kepala_admin, db, bahan, po, 500)
    r = await klien.post("/api/vendor-bills", headers=bahan["h_buat"], json={
        "po_id": po["id"], "supplier_invoice_no": uid("INV"), "submit_now": True,
        "items": [{"product_id": bahan["pid"], "po_line_id": "L1", "billed_qty": 500, "price": 15_000}]})
    assert r.status_code == 200 and r.json()["status"] == "pending_approval", r.text
    det = [e["detail"] for e in r.json()["match_exceptions"]]
    assert det == ["Harga Rp 15.000 menyimpang +50% dari harga PO Rp 10.000 (toleransi ±5%)"], det
