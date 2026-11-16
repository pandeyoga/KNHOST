"""MP-T4a — klaim makloon tanpa jurnal baru (docs/blueprint/unit/MP-T4a.md).

Temuan audit makloon 16 Nov (B-S5): validasi klaim baru jalan saat disetujui (potong bon melebihi tagihan baru ketahuan
di persetujuan), menolak klaim langsung menutup SPK (selisih belum diselesaikan dianggap beres), dan tolak QC hasil
makloon tidak membuka klaim ke mitra. Sesudah unit ini: validasi saat diajukan; tolak = klaim kembali "perlu tindakan"
(SPK tetap Sebagian); tolak QC hasil makloon membuka/menambah klaim langkah itu.
Fixture: SPK satu langkah sudah diterima, tagihan jasa Rp 500.000 belum dibayar.
"""
import uuid

import pytest

from core_utils import now_iso

KSC = "ent_ksc"


def uid(awalan: str) -> str:
    return f"{awalan}_mpt4_{uuid.uuid4().hex[:8]}"


async def spk(db, *, step_status="received", claim=None):
    mko, bill = uid("mko"), uid("bill")
    await db.vendor_bills.insert_one({"id": bill, "bill_number": f"KSC/SVB-{bill[-4:]}", "entity_id": KSC,
                                      "status": "posted", "grand_total": 500_000.0, "net_amount": 500_000.0,
                                      "amount_paid": 0.0, "created_at": now_iso()})
    step = {"seq": 1, "status": step_status, "process_type": "celup", "stage_label": "Celup", "makloon_id": "mk_x",
            "makloon_name": "Pencelup", "input_product_id": "p_in", "output_product_id": "p_out", "input_qty": 100,
            "expected_output_qty": 95, "actual_output_qty": 90 if step_status == "received" else 0,
            "output_unit": "yard", "service_bill_id": bill if step_status == "received" else "",
            "claim": claim or {"status": "open", "required": True, "action": "", "amount": 0.0,
                               "amount_suggested": 250_000.0, "reason": "", "history": []}}
    await db.makloon_orders.insert_one({"id": mko, "mko_number": f"KSC/MKO-{mko[-4:]}", "entity_id": KSC,
                                        "status": "partially_received", "steps": [step], "timeline": [], "created_at": now_iso()})
    return mko


async def test_MPT4a_U1_klaim_hanya_langkah_diterima(klien, kepala_admin, db):
    mko = await spk(db, step_status="issued")
    r = await klien.post(f"/api/makloon-orders/{mko}/claim", headers=kepala_admin,
                         json={"step_seq": 1, "action": "tagih_ganti", "amount": 100_000, "reason": "kurang"})
    assert r.status_code == 400, r.text
    assert "hasilnya sudah diterima" in r.json()["detail"]


async def test_MPT4a_U2_potong_bon_dicek_saat_diajukan(klien, kepala_admin, db):
    mko = await spk(db)
    r = await klien.post(f"/api/makloon-orders/{mko}/claim", headers=kepala_admin,
                         json={"step_seq": 1, "action": "potong_bon", "amount": 600_000, "reason": "kurang 5 yd"})
    assert r.status_code == 400, r.text
    assert "melebihi sisa tagihan jasa" in r.json()["detail"]
    r = await klien.post(f"/api/makloon-orders/{mko}/claim", headers=kepala_admin,
                         json={"step_seq": 1, "action": "potong_bon", "amount": 250_000, "reason": "kurang 5 yd"})
    assert r.status_code == 200, r.text


async def test_MPT4a_U3_tolak_klaim_tidak_menutup_spk(klien, kepala_admin, db):
    mko = await spk(db)
    r = await klien.post(f"/api/makloon-orders/{mko}/claim", headers=kepala_admin,
                         json={"step_seq": 1, "action": "tagih_ganti", "amount": 250_000, "reason": "kurang 5 yd"})
    assert r.status_code == 200, r.text
    from services import makloon_claim_service as mclaim
    await mclaim.reject_claim(mko, 1, reason="bukti kurang, minta foto timbangan", actor="Manajer Uji")
    o = await db.makloon_orders.find_one({"id": mko}, {"_id": 0})
    c = o["steps"][0]["claim"]
    assert c["status"] == "open" and c["rejected_reason"] == "bukti kurang, minta foto timbangan"
    assert o["status"] == "partially_received" and (o.get("completion_hold") or {}).get("reason") == "claim_unsettled"
    assert [h["event"] for h in c["history"]][-1] == "rejected"


async def test_MPT4a_U4_tolak_qc_membuka_klaim(db):
    from services import makloon_claim_service as mclaim
    mko = await spk(db, claim={"status": "none", "required": False, "action": "", "amount": 0.0,
                               "amount_suggested": 0.0, "reason": "", "history": []})
    await db.makloon_orders.update_one({"id": mko}, {"$set": {"status": "completed"}})
    await mclaim.open_from_qc(mko, 1, rejected_qty=12.5, unit="yard", reason="belang warna", task_id="tsk_qc",
                              actor="QC Uji")
    o = await db.makloon_orders.find_one({"id": mko}, {"_id": 0})
    c = o["steps"][0]["claim"]
    assert c["status"] == "open" and c["required"] is True
    assert c["qc_rejects"][0]["qty"] == 12.5 and c["qc_rejects"][0]["task_id"] == "tsk_qc"
    assert o["status"] == "partially_received"


async def test_MPT4a_U4b_tolak_qc_saat_klaim_menunggu(db):
    from services import makloon_claim_service as mclaim
    mko = await spk(db, claim={"status": "pending_approval", "required": True, "action": "tagih_ganti",
                               "amount": 100_000.0, "amount_suggested": 0.0, "reason": "kurang", "history": []})
    await mclaim.open_from_qc(mko, 1, rejected_qty=5, unit="yard", reason="noda", task_id="tsk_2", actor="QC")
    c = (await db.makloon_orders.find_one({"id": mko}, {"_id": 0}))["steps"][0]["claim"]
    assert c["status"] == "pending_approval" and c["amount"] == 100_000.0
    assert c["qc_rejects"][0]["qty"] == 5 and c["history"][-1]["event"] == "qc_reject"


def test_MPT4a_U5_keputusan_qc_memanggil_klaim():
    """Jalur QC hasil makloon memanggil `open_from_qc` (pemeriksaan kode; alur penuh diuji lapis A)."""
    import inspect
    from services import qc_service
    src = inspect.getsource(qc_service.process_qc_decision)
    assert "open_from_qc" in src
