"""KF-T6 — tiap aksi tabel C: "pengaju = pemutus → 403 saat 2" (RISIKO unit; docs/blueprint/unit/KF-T6.md).

Pola tiap uji: `kontrol.<aksi>.min_orang = "2"` di lapisan PT `ent_ksc` → dokumen menunggu keputusan dengan pengaju `mgr`
→ `mgr` memutuskan = 403 dengan pesan dua orang; `mgr2` (manajer lain) tidak terkena 403 dua orang (keputusannya boleh
gagal/berhasil karena alasan lain — yang diuji hanya gerbang dua orang). Aksi tabel C yang juga butir spesifikasi
(uang muka U3, gaji U7, cuti U8, buka kembali U12, jurnal U13) diuji di `test_KFT6_pengalihan.py`.
"""
from __future__ import annotations

import uuid

import pytest

from core_utils import now_iso
from services import config_resolver as resolver

pytestmark = pytest.mark.anyio


def pesan(label: str) -> str:
    return (f"{label} harus diputuskan orang lain: Anda yang mengajukannya. Minta rekan yang berwenang. "
            "Admin dapat mengubah aturan ini di Pengaturan › Persetujuan › Kontrol dua orang.")


# PK-38 — label aksi `pengurang_piutang` diperluas (kini juga kasus keuangan yang menutup piutang tanpa uang masuk).
LABEL_PENGURANG_PIUTANG = "Pengurang piutang tanpa uang masuk"


def _id(awal: str) -> str:
    return f"{awal}_kft6c_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def orang(akun, sesi):
    mgr = await akun("manager", entitas=("ent_ksc", "ent_kanda"))
    mgr2 = await akun("manager", entitas=("ent_ksc", "ent_kanda"))
    return {"mgr": mgr, "mgr2": mgr2, "h_mgr": await sesi(mgr), "h_mgr2": await sesi(mgr2)}


async def _dua_orang(klien, aksi, label, url, orang, body=None):
    """`min_orang=2` di ent_ksc → mgr 403 (pesan dua orang), mgr2 tidak terkena gerbang dua orang."""
    key = f"kontrol.{aksi}.min_orang"
    await resolver.set_value(key, "2", scope_type="entity", scope_id="ent_ksc", reason="uji KF-T6", actor="uji")
    try:
        r = await klien.post(url, headers=orang["h_mgr"], json=body if body is not None else {})
        assert (r.status_code, r.json().get("detail")) == (403, pesan(label)), r.text
        r2 = await klien.post(url, headers=orang["h_mgr2"], json=body if body is not None else {})
        assert not (r2.status_code == 403 and r2.json().get("detail") == pesan(label)), r2.text
        return r2
    finally:
        await resolver.clear_layer(key, scope_type="entity", scope_id="ent_ksc", actor="uji", reason="uji KF-T6")


async def test_transfer_gudang(klien, db, orang):
    t = {"id": _id("trf"), "code": "TRF-KFT6", "entity_id": "ent_ksc", "status": "waiting_approval", "items": [],
         "source_warehouse_id": "", "dest_warehouse_id": "", "requested_by": orang["mgr"]["name"],
         "requested_by_id": orang["mgr"]["id"], "created_at": now_iso()}
    await db.warehouse_transfers.insert_one(dict(t))
    await _dua_orang(klien, "transfer_gudang", "Transfer gudang / antar-PT", f"/api/transfers/{t['id']}/approve",
                     orang, {"approved_by": "x"})


async def test_stok_opname(klien, db, orang):
    s = {"id": _id("ccs"), "number": "CC-KFT6", "entity_id": "ent_ksc", "status": "submitted", "warehouse_id": "",
         "items": [], "discrepancies": [], "submitted_by": orang["mgr"]["name"],
         "submitted_by_id": orang["mgr"]["id"], "created_at": now_iso()}
    await db.cycle_count_sessions.insert_one(dict(s))
    await _dua_orang(klien, "stok_opname", "Stok opname", f"/api/cycle-count/sessions/{s['id']}/approve", orang)


async def test_retur_penjualan(klien, db, orang):
    r = {"id": _id("sret"), "number": "RJ-KFT6", "entity_id": "ent_ksc", "status": "pending_approval",
         "order_id": "", "items": [], "attachments": [], "created_by": orang["mgr"]["name"],
         "created_by_id": orang["mgr"]["id"], "created_at": now_iso()}
    await db.sales_returns.insert_one(dict(r))
    await _dua_orang(klien, "retur_penjualan", "Retur penjualan", f"/api/sales-returns/{r['id']}/approve", orang)


async def test_retur_pembelian(klien, db, orang):
    r = {"id": _id("pret"), "number": "RB-KFT6", "entity_id": "ent_ksc", "status": "pending_approval", "items": [],
         "total_amount": 100000, "created_by": orang["mgr"]["name"], "created_at": now_iso()}   # dokumen lama: nama saja
    await db.purchase_returns.insert_one(dict(r))
    await _dua_orang(klien, "retur_pembelian", "Retur pembelian", f"/api/purchase-returns/{r['id']}/approve", orang)


async def test_lembur(klien, db, orang):
    emp = {"id": _id("emp"), "name": orang["mgr"]["name"], "entity_id": "ent_ksc", "status": "active",
           "user_id": orang["mgr"]["id"], "created_at": now_iso()}
    await db.hr_employees.insert_one(dict(emp))
    ot = {"id": _id("ot"), "number": "OT-KFT6", "employee_id": emp["id"], "employee_name": emp["name"],
          "entity_id": "ent_ksc", "date": "2026-03-02", "period": "2026-03", "hours": 2, "minutes": 120,
          "status": "pending", "approver": "", "created_by": "HR Uji", "created_at": now_iso()}
    await db.hr_overtime.insert_one(dict(ot))
    r2 = await _dua_orang(klien, "lembur", "Lembur", f"/api/hr/overtime/{ot['id']}/approve", orang)
    assert r2.status_code == 200, r2.text


async def test_lpj_uang_muka(klien, db, orang):
    s = {"id": _id("stl"), "number": "STL-KFT6", "entity_id": "ent_ksc", "cash_advance_id": "ca_tidak_ada",
         "status": "submitted", "total_pengeluaran": 100000, "created_by": orang["mgr"]["name"],
         "created_by_id": orang["mgr"]["id"], "created_at": now_iso()}
    await db.cash_advance_settlements.insert_one(dict(s))
    await _dua_orang(klien, "lpj_uang_muka", "Pertanggungjawaban uang muka",
                     f"/api/cash-advance-settlements/{s['id']}/approve", orang)


async def test_pengurang_piutang_bebas_denda(klien, db, orang):
    p = {"id": _id("pen"), "number": "DN-KFT6", "entity_id": "ent_ksc", "status": "issued", "amount": 50000,
         "paid_amount": 0, "customer_id": "", "created_by": orang["mgr"]["name"], "created_at": now_iso()}
    await db.penalties.insert_one(dict(p))
    await _dua_orang(klien, "pengurang_piutang", LABEL_PENGURANG_PIUTANG,
                     f"/api/penalties/{p['id']}/waive", orang, {"reason_code": "penalty_waiver", "note": "uji"})


async def test_pengurang_piutang_selisih_kwitansi(klien, db, orang):
    rc = {"id": _id("rcpt"), "number": "KW-KFT6", "entity_id": "ent_ksc", "status": "posted", "customer_id": "",
          "created_by": orang["mgr"]["id"], "created_by_name": orang["mgr"]["name"],
          "variance": {"direction": "under", "delta": -1000, "needs_decision": True}, "created_at": now_iso()}
    await db.ar_receipts.insert_one(dict(rc))
    await _dua_orang(klien, "pengurang_piutang", LABEL_PENGURANG_PIUTANG,
                     f"/api/payment-variances/receipt/{rc['id']}/decide", orang,
                     {"kind": "writeoff", "reason_code": "rounding_diff", "amount": 1000})


async def test_lewat_batas_kredit(klien, db, orang):
    co = {"id": _id("cov"), "entity_id": "ent_ksc", "customer_id": "", "amount": 1000000, "status": "pending",
          "requested_by": orang["mgr"]["name"], "requested_by_id": orang["mgr"]["id"], "created_at": now_iso()}
    await db.credit_overrides.insert_one(dict(co))
    # CR-T3 — label aksi `lewat_batas_kredit` kini "Izin kredit" (izin kredit juga melepas tahan karena telat).
    r2 = await _dua_orang(klien, "lewat_batas_kredit", "Izin kredit",
                          f"/api/credit-overrides/{co['id']}/decision", orang, {"decision": "approve", "reason": "ok"})
    assert r2.status_code == 200, r2.text


async def test_klaim_makloon(klien, db, orang):
    mko = {"id": _id("mko"), "mko_number": "MKO-KFT6", "entity_id": "ent_ksc", "status": "in_progress",
           "steps": [{"seq": 1, "claim": {"status": "pending_approval", "action": "terima_catatan", "amount": 0,
                                          "proposed_by": orang["mgr"]["name"], "proposed_at": now_iso()}}],
           "created_at": now_iso()}   # dokumen lama: pengusul hanya nama
    await db.makloon_orders.insert_one(dict(mko))
    await _dua_orang(klien, "klaim_makloon", "Klaim selisih makloon", f"/api/makloon-orders/{mko['id']}/claim/approve",
                     orang, {"step_seq": 1, "note": "uji"})


async def test_permintaan_internal(klien, db, orang):
    rq = {"id": _id("ireq"), "number": "PI-KFT6", "entity_id": "ent_ksc", "status": "submitted", "items": [],
          "reason": "uji", "requested_by": orang["mgr"]["name"], "requested_by_id": orang["mgr"]["id"],
          "created_at": now_iso()}
    await db.internal_requests.insert_one(dict(rq))
    await _dua_orang(klien, "permintaan_internal", "Permintaan internal antar-PT",
                     f"/api/internal-requests/{rq['id']}/convert", orang, {"source_entity_id": "ent_kanda"})


async def test_permintaan_desain(klien, db, orang):
    rq = {"id": _id("dreq"), "number": "PD-KFT6", "entity_id": "ent_ksc", "status": "delivered", "gallery_ids": [],
          "requested_by": orang["mgr"]["name"], "requested_by_id": orang["mgr"]["id"], "created_at": now_iso()}
    await db.design_requests.insert_one(dict(rq))
    await _dua_orang(klien, "permintaan_desain", "Permintaan desain", f"/api/design-requests/{rq['id']}/approve",
                     orang, {"note": ""})


async def test_nilai_pesanan(klien, db, orang):
    so = {"id": _id("so"), "number": "SO-KFT6", "entity_id": "ent_ksc", "status": "pending_approval",
          "required_approval_role": "manager", "grand_total": 1000000, "items": [],
          "pending_approvals": [{"id": "pa1", "type": "nilai", "status": "pending", "required_role": "manager"}],
          "created_by": orang["mgr"]["id"], "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    await _dua_orang(klien, "nilai_pesanan", "Persetujuan nilai pesanan", f"/api/sales-orders/{so['id']}/approve",
                     orang)
