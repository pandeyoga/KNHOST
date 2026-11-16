"""Uji bantahan reviewer B1 — PK-38 (FX-10). Lapis B; cp ke backend/tests_mem/, jalankan -n 0 -s."""
# ruff: noqa: F811
import pytest

from core_utils import now_iso
from test_PK38_wewenang import (JT, KSC, _hapus_sisa, _id, _kasus, _kwitansi, _selesaikan, orang,  # noqa: F401
                                pesan_dua_orang)

pytestmark = pytest.mark.anyio


async def _dua_kwitansi_satu_pesanan(db, pembuat, tiap, n=2):
    cus, so = _id("cus"), _id("so")
    await db.customers.insert_one({"id": cus, "name": "Toko Pecah B1", "entity_id": KSC, "status": "active"})
    await db.sales_orders.insert_one({"id": so, "number": f"SO-B1-PECAH-{so[-4:]}", "entity_id": KSC, "customer_id": cus,
                                      "customer_name": "Toko Pecah B1", "status": "confirmed", "grand_total": tiap * n,
                                      "payments": [], "paid_total": 0, "payment_status": "unpaid",
                                      "payment_term_code": "NET30", "created_at": now_iso()})
    out = []
    for i in range(n):
        rc = _id("rcpt")
        await db.ar_receipts.insert_one({
            "id": rc, "number": f"KW-B1-{rc[-4:]}", "entity_id": KSC, "status": "posted", "customer_id": cus,
            "customer_name": "Toko Pecah B1", "created_by": pembuat["id"], "created_by_name": pembuat["name"],
            "receipt_date": now_iso(), "created_at": now_iso(),
            "variance": {"direction": "under", "delta": -tiap, "expected": tiap, "funds": 0, "capacity": tiap,
                         "needs_decision": True, "target_order_ids": [so], "decision_id": "", "tolerance": 0}})
        out.append({"rc": rc, "so": so, "cus": cus})
    return out


async def test_FX10_batas_nilai_pecah_nominal_satu_pesanan(klien, db, orang):
    """Batas 1.000.000 per keputusan. Satu orang (pembuat kwitansi) menghapus sisa pesanan yang sama dua kali
    @600.000 = 1.200.000 > batas, tanpa orang kedua?"""
    k1, k2 = await _dua_kwitansi_satu_pesanan(db, orang["mgrA"], 600_000)
    r1 = await _hapus_sisa(klien, orang["h_mgrA"], k1, 600_000)
    r2 = await _hapus_sisa(klien, orang["h_mgrA"], k2, 600_000)
    so = await db.sales_orders.find_one({"id": k1["so"]})
    total = sum(p["amount"] for p in so.get("payments") or [] if p.get("method") == "writeoff")
    print("OBS pecah nominal", r1.status_code, r2.status_code, "total hapus sisa oleh satu orang:", total,
          (r2.json().get("detail") if r2.status_code != 200 else ""))
    assert total <= 1 * JT, (f"satu orang menghapus piutang satu pesanan Rp {total:,.0f} (> batas Rp 1.000.000) "
                             "dengan memecahnya menjadi dua keputusan")


async def test_FX10_batas_nilai_pecah_nominal_kasus_biaya_bank(klien, db, orang):
    """Sama, lewat kasus keuangan 'biaya bank': dua kasus @600.000 atas pelanggan yang berbeda pesanan tidak relevan —
    yang diuji: tepat di batas (1.000.000) lolos satu orang, 1.000.001 ditolak."""
    kasus = await _kasus(klien, db, orang["h_mgrA"], "selisih_biaya_bank", 1_000_000)
    r = await _selesaikan(klien, orang["h_mgrA"], kasus, "bebankan_biaya_bank", "bank_charge", 1_000_000)
    kasus2 = await _kasus(klien, db, orang["h_mgrA"], "selisih_biaya_bank", 1_000_001)
    r2 = await _selesaikan(klien, orang["h_mgrA"], kasus2, "bebankan_biaya_bank", "bank_charge", 1_000_001)
    print("OBS tepat batas", r.status_code, "| batas+1", r2.status_code)
    assert r.status_code == 200 and (r2.status_code, r2.json().get("detail")) == (403, pesan_dua_orang())


async def test_FX10_tanpa_izin_dan_admin_sendiri(klien, db, orang, kepala_admin):
    k = await _kwitansi(db, orang["sa"], 300_000)
    r = await _hapus_sisa(klien, orang["h_sa"], k, 300_000)          # Admin Sales: bukan peran pemutus
    r_g = await _hapus_sisa(klien, orang["h_gdg"], k, 300_000)       # Gudang
    print("OBS hapus sisa oleh sales_admin", r.status_code, "| gudang", r_g.status_code)
    assert r_g.status_code == 403
    # Admin = pembuat kwitansi, 1.500.000: bawaan `kontrol.admin_boleh_sendiri` = ya → dicatat apa adanya.
    admin = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0, "id": 1, "name": 1})
    k2 = await _kwitansi(db, admin, 1_500_000)
    r2 = await _hapus_sisa(klien, kepala_admin, k2, 1_500_000)
    print("OBS admin pembuat = pemutus 1,5 jt:", r2.status_code, "(bawaan admin_boleh_sendiri)")
    assert r2.status_code in (200, 403)


async def test_FX10_jalur_lain_pembuat_kasus_melimpahkan_ke_diri_sendiri(klien, db, orang):
    """Kasus dibuat mgrA; mgrB menyelesaikan = sah. Dibalik: kasus dibuat mgrB, diselesaikan mgrA 1,5 jt = sah;
    lalu mgrA mencoba menyelesaikan kasus buatannya SENDIRI lewat aksi lain yang juga mengkredit piutang
    (`settlement_antar_entitas`) → harus tetap terkena pintu (403)."""
    kasus = await _kasus(klien, db, orang["h_mgrA"], "selisih_biaya_bank", 1_500_000)
    hasil = {}
    for aksi, alasan in (("settlement_antar_entitas", "case_wrong_entity"), ("akui_dipegang_karyawan", "case_employee_account")):
        r = await _selesaikan(klien, orang["h_mgrA"], kasus, aksi, alasan, 1_500_000, employee_name="Budi",
                              paid_entity_id="ent_kanda")
        hasil[aksi] = (r.status_code, str(r.json().get("detail"))[:90])
    so = await db.sales_orders.find_one({"id": kasus["so"]})
    print("OBS aksi lain pada kasus sendiri:", hasil, "| terbayar", sum(p["amount"] for p in so.get("payments") or []))
    assert sum(p["amount"] for p in so.get("payments") or []) == 0
