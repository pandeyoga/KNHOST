"""MP-T4b — jurnal makloon (docs/blueprint/unit/MP-T4b.md; keputusan K-78…K-81).

Sakelar per PT `makloon.jasa_jadi_hutang`: `saat_terima` (bawaan = cara lama) · `saat_faktur` (K-63/K-78):
  * terima hasil  → Dr WIP 1-1350 / Cr GR/IR 2-1150 sebesar nilai jasa (tanpa PPN); tagihan "menunggu faktur";
  * faktur mitra dicocokkan → Dr GR/IR 2-1150 + Dr PPN Masukan 1-1500 / Cr Hutang 2-1100;
  * klaim (K-64/K-79) dibagi per keadaan roll hasil: masih di stok → Cr Persediaan 1-1300 (biaya roll turun), dikirim
    lagi ke mitra → Cr WIP 1-1350, sudah terjual → Cr Pendapatan Klaim 4-9200; sisi debit potong bon = 2-1150 bila faktur
    belum dicocokkan, 2-1100 bila sudah.
Borongan (K-81, tanpa sakelar): kontrak tarif `lot` yang sama di beberapa langkah ditagih SEKALI, di langkah terakhirnya.
"""
import uuid

import pytest

from core_utils import now_iso

KSC = "ent_ksc"


def uid(awalan: str) -> str:
    return f"{awalan}_mpt4b_{uuid.uuid4().hex[:8]}"


def baris(je):
    out = {}
    for ln in je["lines"]:
        d, c = out.get(ln["account_code"], (0.0, 0.0))
        out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2), round(c + float(ln.get("credit") or 0), 2))
    return out


async def test_MPT4b_U1_jasa_saat_terima_ke_grir():
    """Nilai jasa 950.000 (190 yd × 5.000) → Dr 1-1350 950.000 / Cr 2-1150 950.000; PPN belum ada."""
    from services import gl_service as gl
    bid = uid("vb")
    je = await gl.post_subcon_service(bill_id=bid, mko_id="mko_x", step_seq=1, entity_id=KSC, net_amount=950_000,
                                      ppn=0, grand_total=950_000, makloon_name="Mitra", label="uji",
                                      ap_mode="saat_faktur")
    assert baris(je) == {"1-1350": (950_000.0, 0.0), "2-1150": (0.0, 950_000.0)}


async def test_MPT4b_U2_faktur_dicocokkan_ke_hutang():
    """Faktur 950.000 + PPN 11 % 104.500 = 1.054.500 → Dr 2-1150 950.000 + Dr 1-1500 104.500 / Cr 2-1100 1.054.500."""
    from services import gl_service as gl
    je = await gl.post_subcon_service_invoice(bill_id=uid("vb"), entity_id=KSC, net_amount=950_000, ppn=104_500,
                                              makloon_name="Mitra", label="uji", invoice_no="INV-1")
    assert baris(je) == {"2-1150": (950_000.0, 0.0), "1-1500": (104_500.0, 0.0), "2-1100": (0.0, 1_054_500.0)}


async def _spk_klaim(db, *, ap_mode, bill_status, action="potong_bon", amount=1_000_000.0):
    """Fixture: SPK satu langkah diterima, dua roll hasil 100 yd @ Rp 30.000. Roll A masih di gudang, roll B sudah
    terkirim ke pelanggan. Tagihan jasa 2.000.000 (status sesuai mode). Klaim menunggu persetujuan."""
    mko, bill, ra, rb = uid("mko"), uid("vb"), uid("rollA"), uid("rollB")
    await db.vendor_bills.insert_one({"id": bill, "bill_number": f"VBM-{bill[-4:]}", "bill_type": "makloon_service",
                                      "entity_id": KSC, "status": bill_status, "ap_mode": ap_mode,
                                      "net_amount": 2_000_000.0, "grand_total": 2_000_000.0, "ppn_amount": 0.0,
                                      "amount_paid": 0.0, "makloon_order_id": mko, "step_seq": 1})
    for rid, st in ((ra, "available"), (rb, "delivered")):
        await db.inventory_rolls.insert_one({"id": rid, "roll_no": rid[-6:], "product_id": "p_out", "status": st,
                                             "length_initial": 100.0, "length_remaining": 100.0 if st == "available" else 0.0,
                                             "unit_cost": 30_000.0, "base_unit_cost": 30_000.0, "unit": "yard",
                                             "owner_entity_id": KSC, "warehouse_id": "wh_x"})
    step = {"seq": 1, "status": "received", "makloon_id": "mk", "makloon_name": "Pencelup", "output_unit": "yard",
            "service_bill_id": bill, "lots": [{"roll_id": ra, "length": 100.0}, {"roll_id": rb, "length": 100.0}],
            "claim": {"status": "pending_approval", "required": True, "action": action, "amount": amount,
                      "reason": "belang", "history": []}}
    await db.makloon_orders.insert_one({"id": mko, "mko_number": f"KSC/MKO-{mko[-4:]}", "entity_id": KSC,
                                        "status": "partially_received", "steps": [step], "timeline": [],
                                        "created_at": now_iso()})
    return mko, bill, ra, rb


async def _jurnal_klaim(db, mko):
    return await db.journal_entries.find_one({"source_type": "makloon_claim", "source_id": f"{mko}:1",
                                             "status": {"$ne": "void"}}, {"_id": 0})


async def test_MPT4b_U3_klaim_saat_faktur_kurangi_persediaan(db):
    """Klaim 1.000.000 atas 200 yd hasil → 5.000/yd. Roll A (100 yd di stok) turun 500.000 → Cr 1-1300 500.000, biaya
    30.000 → 25.000. Roll B terjual → Cr 4-9200 500.000. Faktur belum dicocokkan → Dr 2-1150 1.000.000; tagihan
    2.000.000 → 1.000.000."""
    from services import makloon_claim_service as mclaim
    mko, bill, ra, rb = await _spk_klaim(db, ap_mode="saat_faktur", bill_status="awaiting_invoice")
    await mclaim.approve_claim(mko, 1, actor="Manajer Uji")
    assert baris(await _jurnal_klaim(db, mko)) == {"2-1150": (1_000_000.0, 0.0), "1-1300": (0.0, 500_000.0),
                                                     "4-9200": (0.0, 500_000.0)}
    a = await db.inventory_rolls.find_one({"id": ra}, {"_id": 0})
    b = await db.inventory_rolls.find_one({"id": rb}, {"_id": 0})
    assert round(a["unit_cost"], 2) == 25_000.0 and round(b["unit_cost"], 2) == 30_000.0
    vb = await db.vendor_bills.find_one({"id": bill}, {"_id": 0})
    assert vb["net_amount"] == 1_000_000.0 and vb["status"] == "awaiting_invoice"


async def test_MPT4b_U4_klaim_saat_faktur_sesudah_faktur_ke_hutang(db):
    from services import makloon_claim_service as mclaim
    mko, *_ = await _spk_klaim(db, ap_mode="saat_faktur", bill_status="posted")
    await mclaim.approve_claim(mko, 1, actor="Manajer Uji")
    assert baris(await _jurnal_klaim(db, mko))["2-1100"] == (1_000_000.0, 0.0)


async def test_MPT4b_U5_cara_lama_tidak_berubah(db):
    """PT bersakelar `saat_terima` (bawaan): potong bon tetap Dr 2-1100 / Cr 4-9200; biaya roll tidak berubah."""
    from services import makloon_claim_service as mclaim
    mko, bill, ra, _ = await _spk_klaim(db, ap_mode="saat_terima", bill_status="posted")
    await mclaim.approve_claim(mko, 1, actor="Manajer Uji")
    assert baris(await _jurnal_klaim(db, mko)) == {"2-1100": (1_000_000.0, 0.0), "4-9200": (0.0, 1_000_000.0)}
    assert (await db.inventory_rolls.find_one({"id": ra}, {"_id": 0}))["unit_cost"] == 30_000.0


async def test_MPT4b_U6_borongan_sekali_di_langkah_terakhir(klien, kepala_admin, db):
    """Kontrak borongan Rp 2.500.000 (basis lot) dipakai dua langkah → langkah 1 Rp 0, langkah 2 Rp 2.500.000,
    rencana jasa SPK 2.500.000 (dulu 5.000.000)."""
    t = uuid.uuid4().hex[:6]
    wh, g, p, v, mk, k = (f"{x}_mpt4b_{t}" for x in ("wh", "g", "p", "v", "mk", "k"))
    await db.warehouses.insert_one({"id": wh, "code": f"M4B{t}", "name": "Gudang MP-T4b", "roles": ["storage"],
                                    "sharing_mode": "shared", "entity_ids": [], "active": True, "is_active": True,
                                    "zones": []})
    for pid, st in ((g, "grey"), (p, "pfp"), (v, "finished")):
        await db.products.insert_one({"id": pid, "sku": f"M4B-{st}-{t}", "name": f"{st} {t}", "stage": st,
                                      "fabric_type": "woven", "gramasi": 120, "lebar": 1.5, "base_unit": "yard",
                                      "status": "active", "lifecycle": "produksi"})
    await db.makloons.insert_one({"id": mk, "name": "Mitra Borongan", "process_types": ["pre_treatment", "printing"],
                                  "entity_id": KSC, "status": "active"})
    await db.supplier_contracts.insert_one({"id": k, "contract_number": f"KSC/SCT-B{t}", "contract_type": "makloon",
                                            "partner_kind": "makloon", "partner_id": mk, "process_type": "",
                                            "tariff_basis": "lot", "tariff_rate": 2_500_000, "status": "active",
                                            "entity_id": KSC, "tariff_qty_source": "output"})
    r = await klien.post("/api/makloon-orders", headers=kepala_admin, json={
        "mode": "process_only", "material_product_id": g, "material_qty": 200, "material_unit": "yard",
        "from_warehouse_id": wh, "manual_material_reason": "uji", "purpose": {"kind": "stok"},
        "steps": [{"stage_code": "pfp", "process_type": "pre_treatment", "makloon_id": mk, "contract_id": k,
                   "output_product_id": p},
                  {"stage_code": "printing", "process_type": "printing", "makloon_id": mk, "contract_id": k,
                   "output_product_id": v}]})
    assert r.status_code == 200, r.text
    o = r.json()
    assert [round(s["tariff"], 2) for s in o["steps"]] == [0.0, 2_500_000.0]
    assert round(o["planned_service_cost"], 2) == 2_500_000.0
    assert "borongan" in (o["steps"][0].get("tariff_note") or "").lower()
    # Langkah 2 diganti ke kontrak lain → tagihan borongan pindah ke langkah 1 (langkah terakhir yang tersisa).
    k2 = f"k2_mpt4b_{t}"
    await db.supplier_contracts.insert_one({"id": k2, "contract_number": f"KSC/SCT-Y{t}", "contract_type": "makloon",
                                            "partner_kind": "makloon", "partner_id": mk, "process_type": "printing",
                                            "tariff_basis": "yard", "tariff_rate": 1_000, "status": "active",
                                            "entity_id": KSC, "tariff_qty_source": "output"})
    r = await klien.post(f"/api/makloon-orders/{o['id']}/steps/2/partner", headers=kepala_admin,
                         json={"makloon_id": mk, "contract_id": k2})
    assert r.status_code == 200, r.text
    s1, s2 = r.json()["steps"]
    assert round(s1["tariff"], 2) == 2_500_000.0 and not s1.get("borongan_contract_id")
    assert s2["contract_id"] == k2 and round(s2["tariff"], 2) > 0 and not s2.get("borongan_contract_id")


async def test_MPT4b_U7_faktur_mitra_dicocokkan_lewat_api(klien, kepala_admin, db):
    """Tagihan menunggu faktur 2.000.000. Faktur 1.900.000 → 400 (tidak sama). Faktur 2.000.000 + PPN 220.000 → tagihan
    posted, total 2.220.000; jurnal Dr 2-1150 2.000.000 + Dr 1-1500 220.000 / Cr 2-1100 2.220.000. Ulang → 409."""
    mko, bill, *_ = await _spk_klaim(db, ap_mode="saat_faktur", bill_status="awaiting_invoice")
    await db.makloon_orders.update_one({"id": mko}, {"$unset": {"steps.0.claim": ""}})
    url = f"/api/makloon-orders/{mko}/steps/1/service-invoice"
    r = await klien.post(url, headers=kepala_admin, json={"supplier_invoice_no": "INV-9", "net_amount": 1_900_000})
    assert r.status_code == 400 and "tidak sama" in r.json()["detail"], r.text
    r = await klien.post(url, headers=kepala_admin, json={"supplier_invoice_no": "INV-9", "net_amount": 2_000_000,
                                                          "ppn_amount": 220_000})
    assert r.status_code == 200, r.text
    vb = await db.vendor_bills.find_one({"id": bill}, {"_id": 0})
    assert vb["status"] == "posted" and vb["grand_total"] == 2_220_000.0 and vb["supplier_invoice_no"] == "INV-9"
    je = await db.journal_entries.find_one({"source_type": "subcon_service_invoice", "source_id": bill,
                                            "status": {"$ne": "void"}}, {"_id": 0})
    assert baris(je) == {"2-1150": (2_000_000.0, 0.0), "1-1500": (220_000.0, 0.0), "2-1100": (0.0, 2_220_000.0)}
    st = (await db.makloon_orders.find_one({"id": mko}, {"_id": 0}))["steps"][0]
    assert st["service_invoice_status"] == "cocok"
    r = await klien.post(url, headers=kepala_admin, json={"supplier_invoice_no": "INV-9", "net_amount": 2_000_000})
    assert r.status_code == 409, r.text


async def test_MPT4b_U11_grir_per_spk_makloon(klien, kepala_admin, db):
    """K-82 + celah GR/IR: SPK dengan tagihan jasa 950.000 menunggu faktur → Hutang › GR/IR punya baris SPK (diterima
    950.000, sisa 950.000, petunjuk "Cocokkan faktur …"). Susut di mitra dipotong dari tagihan itu 50.000 (Dr 2-1150) →
    sisa 900.000. Faktur 900.000 dicocokkan → sisa 0. Σ sisa per dokumen + tak terhubung = saldo buku besar."""
    from services import gl_service as gl
    from services import makloon_loss_service as mls
    mko, bill, t = uid("mko"), uid("vb"), uuid.uuid4().hex[:6]
    await db.makloon_orders.insert_one({"id": mko, "mko_number": f"KSC/MKO-G{t}", "entity_id": KSC,
                                        "status": "in_process", "timeline": [],
                                        "steps": [{"seq": 1, "status": "received", "makloon_id": "mk_g",
                                                   "makloon_name": "Pencelup GRIR", "service_bill_id": bill}]})
    await db.vendor_bills.insert_one({"id": bill, "bill_number": f"VBM-G{t}", "bill_type": "makloon_service",
                                      "entity_id": KSC, "status": "awaiting_invoice", "ap_mode": "saat_faktur",
                                      "makloon_id": "mk_g", "makloon_order_id": mko, "step_seq": 1,
                                      "net_amount": 950_000.0, "grand_total": 950_000.0, "ppn_amount": 0.0,
                                      "amount_paid": 0.0, "created_at": now_iso()})
    await gl.post_subcon_service(bill_id=bill, mko_id=mko, step_seq=1, entity_id=KSC, net_amount=950_000,
                                 ap_mode="saat_faktur", label="uji")

    async def baris_spk(status="terbuka"):
        r = await klien.get("/api/finance/gr-ir", headers=kepala_admin, params={"status": status, "q": f"G{t}"})
        assert r.status_code == 200, r.text
        return r.json(), [x for x in r.json()["items"] if x["doc_id"] == mko]

    j, rows = await baris_spk()
    assert len(rows) == 1 and rows[0]["kind"] == "makloon" and rows[0]["supplier_name"] == "Pencelup GRIR"
    assert rows[0]["received_value"] == 950_000.0 and rows[0]["balance"] == 950_000.0
    assert rows[0]["awaiting_bills"] == [f"VBM-G{t}"] and rows[0]["action_hint"].startswith("Cocokkan faktur")
    assert rows[0]["can_clear"] is False and rows[0]["link"]["view"] == "makloon-orders"
    # Susut di mitra SPK lain dipotong dari tagihan ini (menunggu faktur) → Dr GR/IR, ref SPK pemilik tagihan.
    assert bill in {b["id"] for b in await mls.deductible_bills(mko, 1)}
    before = await mls._deduct(bill, 50_000, "Uji", "susut", "mko_lain", 1, "loss_g")
    assert before["status"] == "awaiting_invoice"
    je = await gl.post_makloon_material_loss(mko_id="mko_lain", step_seq=1, part="loss_g", entity_id=KSC, expense=0,
                                             claim=50_000, label="uji", claim_account=gl.ACC_GRIR,
                                             grir_mko_id=mko)
    assert baris(je) == {"2-1150": (50_000.0, 0.0), "1-1350": (0.0, 50_000.0)} and je["ref"]["grir_mko_id"] == mko
    _, rows = await baris_spk()
    assert rows[0]["returned_value"] == 50_000.0 and rows[0]["balance"] == 900_000.0
    r = await klien.post(f"/api/makloon-orders/{mko}/steps/1/service-invoice", headers=kepala_admin,
                         json={"supplier_invoice_no": f"INV-G{t}", "net_amount": 900_000})
    assert r.status_code == 200, r.text
    j, rows = await baris_spk()
    assert rows == []
    j, rows = await baris_spk("semua")
    assert rows[0]["billed_value"] == 900_000.0 and rows[0]["balance"] == 0.0
    r = await klien.get("/api/finance/gr-ir", headers=kepala_admin, params={"status": "semua"})
    j = r.json()
    assert round(j["total_balance"] + j["unlinked_balance"], 2) == j["ledger_balance"]
