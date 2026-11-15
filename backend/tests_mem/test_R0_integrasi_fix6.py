"""R0 — integrasi `main` (FIX-6…FIX-10) ke cabang blueprint: satu transaksi = satu jurnal.

Lihat docs/blueprint/INTEGRASI_MAIN_FIX6-10.md. Dua implementasi bertemu di retur beli dari TOLAK QC:
  * FIX-6 (keputusan pemilik 10 Nov, D2) — pilihan per kasus "ganti barang" / "potong tagihan" (`purchase_return_remedy`);
  * PK-28 — dasar jurnal retur (`ap_basis`) ditentukan sekali dan diposting lewat satu pintu `post_purchase_return`.
Sesudah integrasi: `apply_on_approve` hanya mengurus AP & PO; jurnalnya SATU, lewat pintu PK-28:
  * ganti barang (sudah/belum ditagih)  → `gr_ir`  : Dr 2-1150 neto / Cr 1-1300 neto, tanpa Nota Debit, AP tetap;
  * potong tagihan, PO belum ditagih    → `gr_ir`  : Dr 2-1150 neto / Cr 1-1300 neto, Nota Debit, AP turun bruto;
  * potong tagihan, PO sudah ditagih    → `hutang` : Dr 2-1100 bruto / Cr 1-1300 neto / Cr 1-1500 PPN.
Ditambah: scrap roll retur jual = biaya dinolkan (PK-27) DAN status lewat `roll_state` (FIX-10, jejak status).

Angka: PO 50 yard @ 10.000, PPN 11 % → neto 500.000, PPN 55.000, bruto 555.000.
Uji yang sama di MongoDB asli (alur penuh termasuk koreksi): backend/tests/test_fix6_keputusan_10nov.py (D2).
"""
import uuid

import pytest

from core_utils import now_iso

KSC = "ent_ksc"
GRIR, HUTANG, PERSEDIAAN, PPN_IN = "2-1150", "2-1100", "1-1300", "1-1500"
NETO, PPN, BRUTO = 500_000.0, 55_000.0, 555_000.0


def uid(awalan: str) -> str:
    return f"{awalan}_r0_{uuid.uuid4().hex[:8]}"


def baris(je):
    out = {}
    for ln in je["lines"]:
        d, c = out.get(ln["account_code"], (0.0, 0.0))
        out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2), round(c + float(ln.get("credit") or 0), 2))
    return out


async def jurnal_aktif(db, source_type: str, source_id: str):
    return await db.journal_entries.find(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}}, {"_id": 0}).to_list(20)


@pytest.fixture(scope="module")
async def dunia(db):
    site, wid, pid, sid = uid("site"), uid("wh"), uid("prd"), uid("sup")
    await db.warehouse_sites.insert_one({"id": site, "name": "Site Uji R0"})
    await db.warehouses.insert_one({"id": wid, "code": f"R0-{wid[-6:]}", "name": "Gudang Uji R0", "site_id": site,
                                    "roles": ["storage"], "sharing_mode": "shared", "entity_ids": [], "active": True,
                                    "is_active": True, "zones": [], "created_at": now_iso()})
    await db.products.insert_one({"id": pid, "sku": f"R0-{pid[-6:]}", "name": "Kain Uji R0", "base_unit": "yard",
                                  "status": "active", "stage": "finished", "grade": "A", "category": "Kain",
                                  "harga_pokok": 10_000.0, "is_active": True, "created_at": now_iso()})
    await db.suppliers.insert_one({"id": sid, "name": "Pemasok Uji R0", "code": f"S{sid[-6:]}", "status": "active",
                                   "is_active": True, "entity_id": KSC, "created_at": now_iso()})
    return {"wid": wid, "pid": pid, "sid": sid}


async def po_tugas_roll(db, dunia, *, qty=50.0, harga=10_000.0, ditagih=False):
    """PO selesai diterima (ber-PPN 11 %) + tugas QC + satu roll karantina; `ditagih` → faktur pemasok `posted`."""
    po_id, tid, rid = uid("po"), uid("tsk"), uid("roll")
    net = round(qty * harga, 2)
    await db.purchase_orders.insert_one({
        "id": po_id, "po_number": f"PO-R0-{po_id[-6:]}", "entity_id": KSC, "supplier_id": dunia["sid"],
        "supplier_name": "Pemasok Uji R0", "status": "completed", "warehouse_id": dunia["wid"], "po_type": "standard",
        "tax_mode": "ppn", "items": [{"line_id": "L1", "product_id": dunia["pid"], "sku": "R0", "product_name": "Kain Uji R0",
                                      "quantity": qty, "received_qty": qty, "price": harga, "unit": "yard"}],
        "total_amount": net, "net_subtotal": net, "dpp": net, "ppn_amount": round(net * 0.11, 2), "ppn_rate": 11,
        "grand_total": round(net * 1.11, 2), "amount_paid": 0.0, "returned_amount": 0.0, "timeline": [],
        "created_at": now_iso()})
    await db.wms_tasks.insert_one({
        "id": tid, "flow_type": "inbound", "source_type": "purchase_order", "status": "qc_pending", "po_id": po_id,
        "po_number": f"PO-R0-{po_id[-6:]}", "product_id": dunia["pid"], "warehouse_id": dunia["wid"], "entity_id": KSC,
        "expected_qty": qty, "received_qty": qty, "unit": "yard", "qc_plan": {"mode": "none"},
        "supplier_name": "Pemasok Uji R0", "created_at": now_iso()})
    await db.inventory_rolls.insert_one({
        "id": rid, "roll_no": f"R0-{rid[-6:]}", "product_id": dunia["pid"], "warehouse_id": dunia["wid"],
        "owner_entity_id": KSC, "length_initial": qty, "length_remaining": qty, "unit": "yard", "status": "quarantine",
        "qc_task_id": tid, "grade": "A", "unit_cost": harga, "base_unit_cost": harga, "po_id": po_id,
        "created_at": now_iso()})
    if ditagih:
        await db.vendor_bills.insert_one({"id": uid("vb"), "po_id": po_id, "status": "posted", "entity_id": KSC,
                                          "grand_total": round(net * 1.11, 2), "bill_number": f"VB-R0-{po_id[-6:]}",
                                          "items": [], "created_at": now_iso()})
    return po_id, tid, rid


async def tolak_retur(klien, h, db, tid, po_id, qty, pilihan, alasan):
    r = await klien.post(f"/api/inbound/tasks/{tid}/qc-decision", headers=h, json={
        "accept_qty": 0, "reject_qty": qty, "reject_disposition": "return", "reason": "Warna belang tidak sesuai",
        "return_remedy": pilihan, "return_remedy_reason": alasan})
    assert r.status_code == 200, r.text
    pret = await db.purchase_returns.find_one({"po_id": po_id}, {"_id": 0})
    assert pret and pret["source"] == "qc_reject" and pret["remedy"]["choice"] == pilihan, pret
    return pret


async def setujui(klien, h, ret_id):
    r = await klien.post(f"/api/purchase-returns/{ret_id}/approve", headers=h, json={"notes": "uji R0"})
    assert r.status_code == 200, r.text
    return r.json()


# ── Retur beli tolak QC: tepat satu jurnal, akun menurut pilihan pemilik D2 ──────────────────────────────────────────
async def test_R0_ganti_barang_po_sudah_ditagih_tetap_balik_grir(klien, kepala_admin, db, dunia):
    """Ganti barang pada PO yang SUDAH ditagih: aturan PK-28 murni akan memilih Hutang; keputusan D2 = balik GR-IR.
    Satu jurnal Dr 2-1150 500.000 / Cr 1-1300 500.000; tanpa Nota Debit; AP PO tetap 0; PO dibuka lagi."""
    po_id, tid, _rid = await po_tugas_roll(db, dunia, ditagih=True)
    pret = await tolak_retur(klien, kepala_admin, db, tid, po_id, 50, "replace", "Supplier sanggup kirim ganti")
    await setujui(klien, kepala_admin, pret["id"])
    jes = await jurnal_aktif(db, "purchase_return", pret["id"])
    assert len(jes) == 1, jes
    assert baris(jes[0]) == {GRIR: (NETO, 0.0), PERSEDIAAN: (0.0, NETO)}, jes[0]["lines"]
    doc = await db.purchase_returns.find_one({"id": pret["id"]}, {"_id": 0})
    assert doc["ap_basis"] == "gr_ir" and not doc.get("debit_note_number"), doc
    assert doc["gl_status"] == "posted" and doc["remedy_result"]["gl_mode"] == "grir_reversal_net", doc
    assert doc["status_history"][-1]["status"] == "approved"
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    assert po["status"] == "partial" and float(po.get("returned_amount") or 0) == 0.0, po
    assert float(po["items"][0]["replaced_qty"]) == 50.0


async def test_R0_potong_tagihan_belum_ditagih_grir_dan_nota_debit(klien, kepala_admin, db, dunia):
    """Potong tagihan, PO belum ditagih: satu jurnal pembalik GR-IR neto; Nota Debit terbit; AP turun bruto 555.000
    satu kali (bukan dua kali: blok AP umum dilewati untuk retur ber-pilihan)."""
    po_id, tid, _rid = await po_tugas_roll(db, dunia)
    pret = await tolak_retur(klien, kepala_admin, db, tid, po_id, 50, "bill_cut", "Tidak perlu ganti, potong saja")
    await setujui(klien, kepala_admin, pret["id"])
    jes = await jurnal_aktif(db, "purchase_return", pret["id"])
    assert len(jes) == 1 and baris(jes[0]) == {GRIR: (NETO, 0.0), PERSEDIAAN: (0.0, NETO)}, jes
    doc = await db.purchase_returns.find_one({"id": pret["id"]}, {"_id": 0})
    assert doc["ap_basis"] == "gr_ir" and doc.get("debit_note_number"), doc
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    assert abs(float(po["returned_amount"]) - BRUTO) < 0.01, po
    assert po["status"] == "closed_short" and float(po["items"][0]["returned_qty"]) == 50.0, po


async def test_R0_potong_tagihan_sudah_ditagih_ke_hutang(klien, kepala_admin, db, dunia):
    """Potong tagihan, PO sudah ditagih: satu jurnal Nota Debit Dr 2-1100 555.000 / Cr 1-1300 500.000 / Cr 1-1500 55.000.
    Setujui ulang tidak menambah jurnal (idempoten per sumber `purchase_return`)."""
    po_id, tid, _rid = await po_tugas_roll(db, dunia, ditagih=True)
    pret = await tolak_retur(klien, kepala_admin, db, tid, po_id, 50, "bill_cut", "Sudah ditagih, potong tagihan")
    await setujui(klien, kepala_admin, pret["id"])
    jes = await jurnal_aktif(db, "purchase_return", pret["id"])
    assert len(jes) == 1, jes
    assert baris(jes[0]) == {HUTANG: (BRUTO, 0.0), PERSEDIAAN: (0.0, NETO), PPN_IN: (0.0, PPN)}, jes[0]["lines"]
    doc = await db.purchase_returns.find_one({"id": pret["id"]}, {"_id": 0})
    assert doc["ap_basis"] == "hutang" and doc["remedy_result"]["gl_mode"] == "debit_note_ap", doc
    await klien.post(f"/api/purchase-returns/{pret['id']}/approve", headers=kepala_admin, json={})
    assert len(await jurnal_aktif(db, "purchase_return", pret["id"])) == 1
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    assert abs(float(po["returned_amount"]) - BRUTO) < 0.01, po


async def tertagih(klien, h, po_id) -> float:
    r = await klien.get(f"/api/purchase-orders/{po_id}/billing-context", headers=h)
    assert r.status_code == 200, r.text
    return float((r.json().get("items") or [{}])[0].get("billable_received", -1))


async def test_R0_qty_tertagih_potong_tagihan_dikurangi_sekali(klien, kepala_admin, db, dunia):
    """50 karantina → 30 diterima, 20 ditolak & diretur (potong tagihan, belum ditagih). Boleh ditagih 50 − 20 = 30.
    Sebelum R0 dikurangi dua kali (PK-28 `returned_unbilled_map` + FIX-6 `returned_qty`) → 10."""
    po_id, tid, _rid = await po_tugas_roll(db, dunia)
    r = await klien.post(f"/api/inbound/tasks/{tid}/qc-decision", headers=kepala_admin, json={
        "accept_qty": 30, "reject_qty": 20, "reject_disposition": "return", "reason": "Belang di 20 yard",
        "return_remedy": "bill_cut", "return_remedy_reason": "Tidak perlu ganti, potong saja"})
    assert r.status_code == 200, r.text
    pret = await db.purchase_returns.find_one({"po_id": po_id}, {"_id": 0})
    await setujui(klien, kepala_admin, pret["id"])
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    assert float(po["items"][0]["returned_qty"]) == 20.0          # keterangan FIX-6 tetap tercatat
    assert await tertagih(klien, kepala_admin, po_id) == 30.0


async def test_R0_qty_tertagih_ganti_barang_tetap_penuh(klien, kepala_admin, db, dunia):
    """Ganti barang 50 (belum ditagih): `received_qty` PO turun ke 0 → boleh ditagih 0; barang pengganti diterima
    (fixture: `received_qty` +50) → boleh ditagih 50 penuh (tagihan tetap, D2) — retur ganti barang tidak dikurangi lagi."""
    po_id, tid, _rid = await po_tugas_roll(db, dunia)
    pret = await tolak_retur(klien, kepala_admin, db, tid, po_id, 50, "replace", "Supplier kirim ganti minggu depan")
    await setujui(klien, kepala_admin, pret["id"])
    assert await tertagih(klien, kepala_admin, po_id) == 0.0
    await db.purchase_orders.update_one({"id": po_id}, {"$inc": {"items.0.received_qty": 50}})
    assert await tertagih(klien, kepala_admin, po_id) == 50.0


async def test_R0_jalur_jurnal_kedua_fix6_tidak_ada():
    """Pintu jurnal kedua FIX-6 (`post_purchase_return_grir`) tidak ikut masuk; `purchase_return_remedy` tidak mengimpor
    `gl_service` (jurnalnya hanya lewat `purchase_return_service` → `post_purchase_return`)."""
    import ast
    import inspect
    from services import gl_service, purchase_return_remedy
    assert not hasattr(gl_service, "post_purchase_return_grir")
    impor = set()
    for node in ast.walk(ast.parse(inspect.getsource(purchase_return_remedy))):
        if isinstance(node, ast.ImportFrom):
            impor |= {f"{node.module}.{a.name}" for a in node.names}
        elif isinstance(node, ast.Import):
            impor |= {a.name for a in node.names}
    assert not any("gl_service" in x for x in impor), impor


# ── Scrap roll retur jual: biaya PK-27 + status lewat roll_state FIX-10 ───────────────────────────────────────────────
async def test_R0_scrap_dan_batal_scrap_biaya_dan_jejak_status(klien, kepala_admin, db, dunia):
    """Scrap: status `damaged` lewat `roll_state` (status_history bertambah) dan biaya roll dinolkan (writeoff_* tersimpan);
    batal scrap: status `available` lewat `roll_state` dan biaya pulih. Satu jurnal hapus-buku + satu pembalik."""
    sr, rid = uid("sr"), uid("rtn")
    await db.sales_returns.insert_one({"id": sr, "number": f"RJ/R0/{sr[-6:]}", "entity_id": KSC,
                                       "status": "refund_settled", "order_id": "", "items": [], "attachments": [],
                                       "created_at": now_iso()})
    await db.inventory_rolls.insert_one({
        "id": rid, "roll_no": f"R0R-{rid[-6:]}", "product_id": dunia["pid"], "warehouse_id": dunia["wid"],
        "owner_entity_id": KSC, "entity_id": KSC, "unit": "yard", "status": "quarantine", "length": 20,
        "length_initial": 20, "length_remaining": 20, "unit_cost": 12_000, "base_unit_cost": 11_000, "grade": "A",
        "origin_type": "return", "return_id": sr, "qc_status": "pending_release", "created_at": now_iso()})
    r = await klien.post(f"/api/sales-returns/{sr}/quarantine/release", headers=kepala_admin,
                         json={"decisions": [{"roll_id": rid, "action": "scrap"}], "notes": "kain rusak berat"})
    assert r.status_code == 200, r.text
    rd = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    assert (rd["status"], rd["unit_cost"], rd["base_unit_cost"]) == ("damaged", 0, 0), rd
    assert (rd["writeoff_unit_cost"], rd["writeoff_base_unit_cost"]) == (12_000, 11_000), rd
    assert (rd.get("status_history") or [{}])[-1].get("status") == "damaged", rd.get("status_history")
    assert len(await jurnal_aktif(db, "inventory_writeoff", rid)) == 1
    r = await klien.post(f"/api/sales-returns/{sr}/reverse-writeoff", headers=kepala_admin,
                         json={"reason": "salah putus scrap"})
    assert r.status_code == 200, r.text
    rd = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    assert (rd["status"], rd["unit_cost"], rd["base_unit_cost"]) == ("available", 12_000, 11_000), rd
    assert rd["status_history"][-1].get("status") == "available", rd["status_history"]
    assert len(await jurnal_aktif(db, "inventory_writeoff_reversal", rid)) == 1
    assert await db.roll_cost_history.count_documents({"roll_id": rid}) == 2
