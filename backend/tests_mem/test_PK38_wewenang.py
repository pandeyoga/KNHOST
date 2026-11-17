"""PK-38 — satu batas pengurang piutang tanpa uang masuk, izin bayar kontrabon, nilai jasa makloon, ganti termin.

docs/blueprint/unit/PK-38.md, uji penerimaan U1–U17 (lingkungan B). Bawaan: batas Rp 1.000.000 (kunci lama
`payment.variance_writeoff_max_amount`, alias kunci baru), `kontrol.pengurang_piutang.min_orang` 1,
`kontrol.admin_boleh_sendiri` ya. Akun: `mgrA`, `mgrB` (Manajer, PT ent_ksc + ent_kanda), `gdg` (Gudang), `sa` (Admin
Sales). Kwitansi, pesanan, kontrabon, order makloon = fixture (disisipkan); kasus keuangan, keputusan, bayar, catat jasa,
koreksi pesanan = alur lewat API.

Hitung tangan jurnal (contoh `00` §9):
  U2  hapus sisa kurang bayar 1.500.000 → Dr 6-9100 Beban Selisih Pembayaran 1.500.000 · Cr 1-1200 Piutang 1.500.000;
      piutang pesanan 1.500.000 → 0 (lunas lewat pembayaran ber-`method` writeoff).
  U3  biaya bank 1.500.000 → Dr 6-8000 Beban Administrasi Bank 1.500.000 · Cr 1-1200 Piutang 1.500.000.
"""
from __future__ import annotations

import itertools
import uuid

import pytest

from core_utils import now_iso
from pembantu import jumlah
from services import config_resolver as resolver

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
JT = 1_000_000
_n = itertools.count(1)
B_BARU = "kontrol.pengurang_piutang.batas_nominal"
B_LAMA = "payment.variance_writeoff_max_amount"
MIN_ORANG = "kontrol.pengurang_piutang.min_orang"
PESAN_JASA = ("Nilai tagihan jasa diisi bagian Pembelian. Kosongkan Ongkos Jasa, PPN, dan No. Faktur Mitra, lalu "
              "simpan lagi; tarif dihitung dari kontrak.")
PESAN_TARIF_NOL = "Tarif jasa langkah ini belum ada di kontrak. Minta bagian Pembelian mengisi tarifnya, lalu catat lagi."


def pesan_dua_orang() -> str:
    from services.dual_control import pesan_tolak   # teks 403 milik KF-T6
    return pesan_tolak("pengurang_piutang")


def _id(awal: str) -> str:
    return f"{awal}_pk38_{uuid.uuid4().hex[:8]}"


async def _set(key, value, scope_type="entity", scope_id=KSC):
    await resolver.set_value(key, value, scope_type=scope_type, scope_id=scope_id, actor="uji", reason="uji PK-38")


async def _clear(key, scope_type="entity", scope_id=KSC):
    await resolver.clear_layer(key, scope_type=scope_type, scope_id=scope_id, actor="uji", reason="uji PK-38")


@pytest.fixture(scope="module")
async def orang(akun, sesi):
    from services import amendment_service
    await amendment_service.ensure_reasons()
    mgr_a = await akun("manager", entitas=(KSC, KANDA))
    mgr_b = await akun("manager", entitas=(KSC, KANDA))
    gdg = await akun("warehouse")
    sa = await akun("sales_admin")
    return {"mgrA": mgr_a, "mgrB": mgr_b, "gdg": gdg, "sa": sa,
            "h_mgrA": await sesi(mgr_a), "h_mgrB": await sesi(mgr_b), "h_gdg": await sesi(gdg), "h_sa": await sesi(sa),
            "h_mgrA_kanda": await sesi(mgr_a, entitas=KANDA), "h_mgrB_kanda": await sesi(mgr_b, entitas=KANDA)}


# ── Pengurang piutang tanpa kas (FX-10) ────────────────────────────────────────────────────────────────────────────
async def _kwitansi(db, pembuat, nominal, ent=KSC):
    """Fixture: pelanggan + pesanan terbuka senilai `nominal` + kwitansi buatan `pembuat` yang kurang bayar `nominal`."""
    i = next(_n)
    cus, so, rc = _id("cus"), _id("so"), _id("rcpt")
    await db.customers.insert_one({"id": cus, "name": f"Toko PK38 {i}", "entity_id": ent, "status": "active"})
    await db.sales_orders.insert_one({"id": so, "number": f"SO-PK38-{i}", "entity_id": ent, "customer_id": cus,
                                      "customer_name": f"Toko PK38 {i}", "status": "confirmed", "grand_total": nominal,
                                      "payments": [], "paid_total": 0, "payment_status": "unpaid",
                                      "payment_term_code": "NET30", "created_at": now_iso()})
    await db.ar_receipts.insert_one({
        "id": rc, "number": f"KW-PK38-{i}", "entity_id": ent, "status": "posted", "customer_id": cus,
        "customer_name": f"Toko PK38 {i}", "created_by": pembuat["id"], "created_by_name": pembuat["name"],
        "receipt_date": now_iso(), "created_at": now_iso(),
        "variance": {"direction": "under", "delta": -nominal, "expected": nominal, "funds": 0, "capacity": nominal,
                     "needs_decision": True, "target_order_ids": [so], "decision_id": "", "tolerance": 0}})
    return {"rc": rc, "so": so, "cus": cus}


async def _hapus_sisa(klien, h, k, nominal):
    return await klien.post(f"/api/payment-variances/receipt/{k['rc']}/decide", headers=h,
                            json={"kind": "writeoff", "reason_code": "uncollectible_small", "amount": nominal,
                                  "note": "uji PK-38"})


async def _jejak_hapus_sisa(db, k):
    so = await db.sales_orders.find_one({"id": k["so"]})
    dec = await db.payment_variance_decisions.find_one({"receipt_id": k["rc"]})
    je = [j async for j in db.journal_entries.find({"source_type": "payment_variance_writeoff",
                                                    "source_id": (dec or {}).get("id", "-")})]
    return so, dec, je


def _baris(je):
    return sorted((ln["account_code"], float(ln.get("debit") or 0), float(ln.get("credit") or 0))
                  for j in je for ln in j.get("lines") or [])


async def test_PK38_U1_hapus_sisa_di_bawah_batas_satu_orang(klien, db, orang):
    k = await _kwitansi(db, orang["mgrA"], 900_000)
    r = await _hapus_sisa(klien, orang["h_mgrA"], k, 900_000)
    assert r.status_code == 200, r.text   # 900.000 ≤ 1.000.000 → satu orang cukup


async def test_PK38_U2_hapus_sisa_di_atas_batas_orang_kedua(klien, db, orang):
    k = await _kwitansi(db, orang["mgrA"], 1_500_000)
    r = await _hapus_sisa(klien, orang["h_mgrA"], k, 1_500_000)
    assert (r.status_code, r.json().get("detail")) == (403, pesan_dua_orang()), r.text
    so, dec, je = await _jejak_hapus_sisa(db, k)
    assert not [p for p in so.get("payments") or [] if p.get("method") == "writeoff"] and dec is None and je == []
    r = await _hapus_sisa(klien, orang["h_mgrB"], k, 1_500_000)
    assert r.status_code == 200, r.text
    so, dec, je = await _jejak_hapus_sisa(db, k)
    # Dr 6-9100 1.500.000 / Cr 1-1200 1.500.000; piutang pesanan 1.500.000 → 0.
    assert _baris(je) == [("1-1200", 0.0, 1_500_000.0), ("6-9100", 1_500_000.0, 0.0)]
    assert [p["amount"] for p in so["payments"] if p.get("method") == "writeoff"] == [1_500_000]
    assert so["payment_status"] == "paid"


async def test_PK38_U2b_keputusan_saat_kwitansi_dibuat_tidak_membatalkan_uang(db, orang):
    """Jalur `create_receipt` menangkap `VarianceError`: penolakan dua orang adalah turunannya, jadi kwitansi tetap sah
    dan selisihnya menunggu di antrean (tidak ada 403 yang membatalkan uang yang sudah masuk)."""
    from services import payment_variance_service as pvs
    assert issubclass(pvs.VarianceForbidden, pvs.VarianceError)
    k = await _kwitansi(db, orang["mgrA"], 1_500_000)
    with pytest.raises(pvs.VarianceForbidden):
        await pvs.decide_receipt(k["rc"], {"kind": "writeoff", "reason_code": "uncollectible_small",
                                          "amount": 1_500_000}, orang["mgrA"])
    so, dec, je = await _jejak_hapus_sisa(db, k)
    assert dec is None and je == [] and not so.get("payments")


async def _kasus(klien, db, h, jenis, nominal, *, deposit=0.0, bukti=False):
    i = next(_n)
    cus, so = _id("cus"), _id("so")
    await db.customers.insert_one({"id": cus, "name": f"Toko Kasus PK38 {i}", "entity_id": KSC, "status": "active",
                                   "deposit_balance": deposit})
    await db.sales_orders.insert_one({"id": so, "number": f"SO-KS-PK38-{i}", "entity_id": KSC, "customer_id": cus,
                                      "customer_name": f"Toko Kasus PK38 {i}", "status": "confirmed",
                                      "grand_total": nominal, "payments": [], "paid_total": 0,
                                      "payment_status": "unpaid", "created_at": now_iso()})
    body = {"case_type": jenis, "amount": nominal, "order_ids": [so], "customer_id": cus, "entity_id": KSC}
    if bukti:
        body["attachments"] = [{"name": "bukti.pdf", "path": "uji/bukti.pdf"}]
    r = await klien.post("/api/finance-cases", headers=h, json=body)
    assert r.status_code == 200, r.text
    return {"id": r.json()["id"], "so": so, "cus": cus}


async def _selesaikan(klien, h, kasus, aksi, alasan, nominal, **extra):
    return await klien.post(f"/api/finance-cases/{kasus['id']}/resolve", headers=h,
                            json={"action": aksi, "reason_code": alasan, "amount": nominal,
                                  "order_id": kasus["so"], "note": "uji PK-38", **extra})


async def test_PK38_U3_biaya_bank_di_atas_batas_orang_kedua(klien, db, orang):
    kasus = await _kasus(klien, db, orang["h_mgrA"], "selisih_biaya_bank", 1_500_000)
    r = await _selesaikan(klien, orang["h_mgrA"], kasus, "bebankan_biaya_bank", "bank_charge", 1_500_000)
    assert (r.status_code, r.json().get("detail")) == (403, pesan_dua_orang()), r.text
    assert await jumlah("journal_entries", {"source_type": "finance_case", "source_id": {"$regex": f"^{kasus['id']}"}}) == 0
    r = await _selesaikan(klien, orang["h_mgrB"], kasus, "bebankan_biaya_bank", "bank_charge", 1_500_000)
    assert r.status_code == 200, r.text
    je = [j async for j in db.journal_entries.find({"source_type": "finance_case",
                                                    "source_id": {"$regex": f"^{kasus['id']}"}})]
    assert _baris(je) == [("1-1200", 0.0, 1_500_000.0), ("6-8000", 1_500_000.0, 0.0)]


async def test_PK38_U4_biaya_bank_kecil_tetap_otomatis(klien, db, orang):
    kasus = await _kasus(klien, db, orang["h_mgrA"], "selisih_biaya_bank", 40_000)
    r = await _selesaikan(klien, orang["h_mgrA"], kasus, "bebankan_biaya_bank", "bank_charge", 40_000)
    assert r.status_code == 200, r.text   # 40.000 ≤ min(50.000, 1.000.000)
    assert r.json()["resolution"]["auto_resolved"] is True


async def test_PK38_U5_uang_dipegang_karyawan_di_atas_batas(klien, db, orang):
    kasus = await _kasus(klien, db, orang["h_mgrA"], "rekening_pribadi_karyawan", 1_500_000, bukti=True)
    r = await _selesaikan(klien, orang["h_mgrA"], kasus, "akui_dipegang_karyawan", "case_employee_account",
                          1_500_000, employee_name="Budi")
    assert (r.status_code, r.json().get("detail")) == (403, pesan_dua_orang()), r.text


async def test_PK38_U6_refund_tidak_terkena_pintu(klien, db, orang):
    ba = _id("ba")
    await db.bank_accounts.insert_one({"id": ba, "name": "Bank PK38", "account_type": "bank", "cash_type": "kas_besar",
                                       "entity_id": KSC, "is_active": True, "opening_balance": 0})
    kasus = await _kasus(klien, db, orang["h_mgrA"], "refund_pelanggan", 1_500_000, deposit=1_500_000)
    r = await _selesaikan(klien, orang["h_mgrA"], kasus, "refund_pelanggan", "customer_refund_request", 1_500_000,
                          customer_id=kasus["cus"], account_id=ba)
    assert r.status_code == 200, r.text   # di bawah ambang kasus Rp 5.000.000; bukan pengurang piutang


async def test_PK38_U7_batas_per_pt(klien, db, orang):
    await _set(B_BARU, 2 * JT, "entity", KSC)
    try:
        k1 = await _kwitansi(db, orang["mgrA"], 1_500_000, KSC)
        r = await _hapus_sisa(klien, orang["h_mgrA"], k1, 1_500_000)
        assert r.status_code == 200, r.text   # 1.500.000 ≤ 2.000.000 di ent_ksc
        k2 = await _kwitansi(db, orang["mgrA"], 1_500_000, KANDA)
        r = await _hapus_sisa(klien, orang["h_mgrA_kanda"], k2, 1_500_000)
        assert (r.status_code, r.json().get("detail")) == (403, pesan_dua_orang()), r.text   # ent_kanda: 1.000.000
    finally:
        await _clear(B_BARU, "entity", KSC)


async def test_PK38_U8_kunci_lama_jadi_alias(klien, db, orang, kepala_admin):
    # Kunci baru belum pernah diisi di grup maupun ent_kanda; kunci lama grup = 3.000.000 → 2.500.000 ≤ 3.000.000.
    assert (await resolver.resolve(B_BARU, {"entity_id": KANDA}))["source_layer"] == "code_default"
    awal = await resolver.value_of(B_LAMA)
    await _set(B_LAMA, 3 * JT, "global", "")
    try:
        k = await _kwitansi(db, orang["mgrA"], 2_500_000, KANDA)
        r = await _hapus_sisa(klien, orang["h_mgrA_kanda"], k, 2_500_000)
        assert r.status_code == 200, r.text
        from services import ar_reduction_guard as ard
        assert await ard.batas(KANDA) == 3 * JT
        # L6 — tab Kontrol dua orang menampilkan batas yang dipakai mesin (nilai kunci lama selama kunci baru kosong).
        r = await klien.get("/api/kontrol/aturan", headers=kepala_admin, params={"entity_id": KANDA})
        assert next(x for x in r.json()["rows"] if x["aksi"] == "pengurang_piutang")["batas_nominal"] == 3 * JT
    finally:
        await _set(B_LAMA, awal, "global", "")   # lapisan grup tidak bisa dicabut — kembalikan nilai awalnya


async def test_PK38_U9_dua_orang_selalu(klien, db, orang):
    await _set(MIN_ORANG, "2", "entity", KSC)
    try:
        k = await _kwitansi(db, orang["mgrA"], 100_000)
        r = await _hapus_sisa(klien, orang["h_mgrA"], k, 100_000)
        assert (r.status_code, r.json().get("detail")) == (403, pesan_dua_orang()), r.text
    finally:
        await _clear(MIN_ORANG, "entity", KSC)


async def test_PK38_bukan_pengurang_tanpa_kas_tidak_terkena_batas(klien, db, orang):
    """Pilihan selisih lain ("sisa tetap piutang") dan bebas denda di atas batas oleh pembuatnya: tetap satu orang."""
    k = await _kwitansi(db, orang["mgrA"], 1_500_000)
    r = await klien.post(f"/api/payment-variances/receipt/{k['rc']}/decide", headers=orang["h_mgrA"],
                         json={"kind": "outstanding", "reason_code": "partial_payment_agreed", "note": "uji PK-38"})
    assert r.status_code == 200, r.text
    p = {"id": _id("pen"), "number": "DN-PK38", "entity_id": KSC, "status": "issued", "amount": 1_500_000,
         "paid_amount": 0, "customer_id": "", "created_by": orang["mgrA"]["name"],
         "created_by_id": orang["mgrA"]["id"], "created_at": now_iso()}
    await db.penalties.insert_one(dict(p))
    r = await klien.post(f"/api/penalties/{p['id']}/waive", headers=orang["h_mgrA"],
                         json={"reason_code": "penalty_waiver", "note": "uji PK-38"})
    assert not (r.status_code == 403 and r.json().get("detail") == pesan_dua_orang()), r.text


async def test_PK38_pilihan_keputusan_memakai_batas_server(klien, db, orang):
    """Layar: pilihan `writeoff` membawa `max_amount` dan `needs_second_person_above` = batas server."""
    k = await _kwitansi(db, orang["mgrA"], 700_000)
    r = await klien.get(f"/api/payment-variances/receipt/{k['rc']}", headers=orang["h_mgrA"])
    assert r.status_code == 200, r.text
    wo = next(o for o in r.json()["assessment"]["options"] if o["value"] == "writeoff")
    assert (wo["max_amount"], wo["needs_second_person_above"]) == (1 * JT, 1 * JT)
    r = await klien.get("/api/finance-cases/policy", headers=orang["h_mgrA"])
    assert r.status_code == 200, r.text
    assert r.json()["needs_second_person_above"] == 1 * JT
    assert set(r.json()["ar_reduction_actions"]) == {"bebankan_biaya_bank", "akui_dipegang_karyawan",
                                                    "settlement_antar_entitas"}


# ── Bayar kontrabon (IA-12) ─────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def kontrabon(db, orang):
    from services import contra_bon_service as cbs
    await db.bank_accounts.insert_one({"id": "rek_pk38", "name": "Kas Besar PK38", "entity_id": KSC,
                                       "account_type": "bank", "cash_type": "kas_besar", "is_active": True,
                                       "opening_balance": 0})
    out = {}
    for cid, status in (("cb_pk38_bayar", "approved"), ("cb_pk38_setuju", "verified"),
                        ("cb_pk38_bayar2", "approved"), ("cb_pk38_setuju2", "verified")):
        bid = f"vb_{cid}"
        await db.vendor_bills.insert_one({"id": bid, "bill_number": bid.upper(), "entity_id": KSC,
                                          "supplier_id": "sup_pk38", "supplier_name": "Pemasok PK38",
                                          "status": "posted", "grand_total": 2 * JT, "subtotal": 2 * JT,
                                          "amount_paid": 0.0, "payments": [], "timeline": [], "po_id": None,
                                          "bill_date": now_iso()[:10], "created_at": now_iso()})
        cb = {"id": cid, "number": cid.upper(), "entity_id": KSC, "supplier_id": "sup_pk38",
              "supplier_name": "Pemasok PK38", "status": status, "created_at": now_iso(), "timeline": [],
              "payments": [], "decisions": [], "deductions": [], "created_by": orang["mgrB"]["name"],
              "created_by_id": orang["mgrB"]["id"],
              "bills": [{"bill_id": bid, "bill_number": bid.upper(), "applied_amount": 2 * JT, "settled_amount": 0.0,
                         "po_id": None}]}
        if status == "approved":
            cb.update({"approved_by": orang["mgrB"]["name"], "approved_by_id": orang["mgrB"]["id"],
                       "approved_at": now_iso()})
        await db.contra_bons.insert_one(dict(cbs.recompute(cb)))
        out[cid] = cid
    return out


async def _bayar(klien, h, cid):
    return await klien.post(f"/api/contra-bons/{cid}/pay", headers=h,
                            json={"amount": 2 * JT, "paid_at": now_iso()[:10], "bank_account_id": "rek_pk38"})


async def test_PK38_U10_izin_bayar_saja(klien, akun, sesi, peran_tanpa_acuan, kontrabon):
    rid = await peran_tanpa_acuan({"contra_bon": ["view", "pay"]}, label="Bayar Kontrabon PK38")
    h = await sesi(await akun(rid))
    r = await _bayar(klien, h, "cb_pk38_bayar")
    assert r.status_code == 200, r.text
    r = await klien.post("/api/contra-bons/cb_pk38_setuju/approve", headers=h)
    assert r.status_code == 403, r.text


async def test_PK38_U11_izin_setujui_saja(klien, akun, sesi, peran_tanpa_acuan, kontrabon, kepala_admin):
    rid = await peran_tanpa_acuan({"contra_bon": ["view", "approve"]}, label="Setujui Kontrabon PK38")
    h = await sesi(await akun(rid))
    # Koreksi blueprint (laporan PK-38): sejak KP-T4 siapa yang boleh menyetujui kontrabon juga dibaca dari Aturan
    # Persetujuan (bawaan: Admin atau Manajer) — peran Tanpa Acuan harus tercantum di sana, selain memegang izinnya.
    r = await klien.put("/api/approval-policies/contra_bon_approve", headers=kepala_admin, json={
        "entity_id": KSC, "reason": "uji PK-38", "levels": [{"level": 1, "tiers": [{"min_amount": 0, "roles": [rid]}]}]})
    assert r.status_code == 200, r.text
    try:
        r = await klien.post("/api/contra-bons/cb_pk38_setuju2/approve", headers=h)
        assert r.status_code == 200, r.text
        r = await _bayar(klien, h, "cb_pk38_bayar2")
        assert r.status_code == 403, r.text
    finally:
        r = await klien.delete("/api/approval-policies/contra_bon_approve", headers=kepala_admin,
                               params={"entity_id": KSC, "reason": "uji PK-38"})
        assert r.status_code == 200, r.text


async def test_PK38_U12_finance_bawaan_bayar_kontrabon(klien, kepala_admin):
    from permissions_config import DEFAULT_PERMISSIONS
    # K-FIN-01 (pemilik 17 Nov 2026 malam) — Finance setara Manajer: kontrabon penuh (dulu hanya lihat + bayar, PK-38).
    assert DEFAULT_PERMISSIONS["finance"]["contra_bon"][:2] == ["view", "pay"]
    assert set(DEFAULT_PERMISSIONS["finance"]["contra_bon"]) == set(DEFAULT_PERMISSIONS["manager"]["contra_bon"])
    r = await klien.get("/api/access/roles/finance", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert sorted(r.json()["permissions"]["contra_bon"]) == sorted(DEFAULT_PERMISSIONS["manager"]["contra_bon"])


async def test_PK38_bayar_orang_kedua_bila_diatur(klien, db, kontrabon, orang):
    """IA-12 — `kontrol.bayar_hutang.min_orang = 2`: penyetuju kontrabon tidak boleh membayarnya sendiri."""
    from services.dual_control import pesan_tolak
    cid = "cb_pk38_bayar_sod"
    bid = f"vb_{cid}"
    from services import contra_bon_service as cbs
    await db.vendor_bills.insert_one({"id": bid, "bill_number": bid.upper(), "entity_id": KSC, "supplier_id": "sup_pk38",
                                      "supplier_name": "Pemasok PK38", "status": "posted", "grand_total": 2 * JT,
                                      "subtotal": 2 * JT, "amount_paid": 0.0, "payments": [], "timeline": [],
                                      "po_id": None, "bill_date": now_iso()[:10], "created_at": now_iso()})
    await db.contra_bons.insert_one(dict(cbs.recompute({
        "id": cid, "number": cid.upper(), "entity_id": KSC, "supplier_id": "sup_pk38", "supplier_name": "Pemasok PK38",
        "status": "approved", "created_at": now_iso(), "timeline": [], "payments": [], "decisions": [],
        "deductions": [], "approved_by": orang["mgrA"]["name"], "approved_by_id": orang["mgrA"]["id"],
        "bills": [{"bill_id": bid, "bill_number": bid.upper(), "applied_amount": 2 * JT, "settled_amount": 0.0,
                   "po_id": None}]})))
    await _set("kontrol.bayar_hutang.min_orang", "2", "entity", KSC)
    try:
        r = await _bayar(klien, orang["h_mgrA"], cid)
        assert (r.status_code, r.json().get("detail")) == (403, pesan_tolak("bayar_hutang")), r.text
        assert await jumlah("cash_transactions", {"ref_id": cid}) == 0
        r = await _bayar(klien, orang["h_mgrB"], cid)
        assert r.status_code == 200, r.text
    finally:
        await _clear("kontrol.bayar_hutang.min_orang", "entity", KSC)


# ── Nilai jasa makloon (IA-08) ─────────────────────────────────────────────────────────────────────────────────────
async def _order_makloon(db, *, alur="service_only", status="pending", kontrak=True):
    mko = _id("mko")
    ctr = _id("ctr")
    if kontrak:
        await db.supplier_contracts.insert_one({"id": ctr, "contract_number": f"KTR-{ctr}", "entity_id": KSC,
                                                "tariff_basis": "lumpsum", "tariff_rate": 400_000, "aux_fees": [],
                                                "status": "active"})
    step = {"seq": 1, "material_flow": alur, "status": status, "makloon_id": "mkl_pk38", "makloon_name": "Mitra PK38",
            "contract_id": ctr if kontrak else "", "tariff_basis": "lumpsum", "tariff_rate": 0, "input_qty": 100,
            "input_unit": "meter", "input_product_id": "", "output_product_id": "prd_out_pk38", "aux_cost": 0,
            "stage_label": "Pembuatan kasa", "process_type": "screen", "issue_ref": f"iss_{mko}",
            "tolerance_pct": 0, "expected_output_qty": 100}
    await db.makloon_orders.insert_one({"id": mko, "mko_number": f"MKO-{mko}", "entity_id": KSC,
                                        "status": "in_progress" if status == "issued" else "draft",
                                        "steps": [step], "timeline": [], "created_at": now_iso()})
    return mko


async def _catat_jasa(klien, h, mko, **isi):
    return await klien.post(f"/api/makloon-orders/{mko}/record-service", headers=h, json={"step_seq": 1, **isi})


async def test_PK38_U13_gudang_tidak_mengetik_nilai_jasa(klien, db, orang):
    mko = await _order_makloon(db)
    n_tagihan = await jumlah("vendor_bills", {})
    r = await _catat_jasa(klien, orang["h_gdg"], mko, tariff=500_000)
    assert (r.status_code, r.json().get("detail")) == (403, PESAN_JASA), r.text
    assert (await db.makloon_orders.find_one({"id": mko}))["steps"][0]["status"] == "pending"
    assert await jumlah("vendor_bills", {}) == n_tagihan


async def test_PK38_U14_tarif_dari_kontrak_dan_pembelian_menimpa(klien, db, orang):
    mko = await _order_makloon(db)
    r = await _catat_jasa(klien, orang["h_gdg"], mko)
    assert r.status_code == 200, r.text
    vb = await db.vendor_bills.find_one({"makloon_order_id": mko, "bill_type": "makloon_service"})
    assert vb["net_amount"] == 400_000
    mko2 = await _order_makloon(db)
    r = await _catat_jasa(klien, orang["h_mgrA"], mko2, tariff=500_000)
    assert r.status_code == 200, r.text
    vb = await db.vendor_bills.find_one({"makloon_order_id": mko2, "bill_type": "makloon_service"})
    assert vb["net_amount"] == 500_000


async def test_PK38_U13b_tarif_kontrak_nol_untuk_gudang(klien, db, orang):
    mko = await _order_makloon(db, kontrak=False)   # tanpa kontrak, tarif langkah 0
    r = await _catat_jasa(klien, orang["h_gdg"], mko)
    assert (r.status_code, r.json().get("detail")) == (400, PESAN_TARIF_NOL), r.text
    assert (await db.makloon_orders.find_one({"id": mko}))["steps"][0]["status"] == "pending"


async def test_PK38_U15_terima_hasil_gudang_isi_ppn(klien, db, orang):
    mko = await _order_makloon(db, alur="moves", status="issued")
    await db.products.update_one({"id": "prd_out_pk38"}, {"$set": {"id": "prd_out_pk38", "name": "Kain Hasil PK38",
                                                                   "sku": "OUT-PK38", "base_unit": "meter"}},
                                 upsert=True)
    wh = {"id": _id("wh")}
    await db.warehouses.insert_one({**wh, "name": "Gudang PK38", "code": wh["id"][-6:], "entity_id": KSC,
                                    "status": "active", "is_active": True, "type": "main"})
    r = await klien.post(f"/api/makloon-orders/{mko}/receive", headers=orang["h_gdg"],
                         json={"step_seq": 1, "actual_output_qty": 100, "ppn": 55_000,
                               "output_warehouse_id": wh.get("id", ""),
                               "rolls": [{"lot": "LOT-PK38", "length": 100, "grade": "A"}]})
    assert (r.status_code, r.json().get("detail")) == (403, PESAN_JASA), r.text
    st = (await db.makloon_orders.find_one({"id": mko}))["steps"][0]
    assert st["status"] == "issued" and not st.get("receive_progress")   # roll input belum dikonsumsi


async def test_PK38_detail_menandai_isian_nilai_jasa(klien, db, orang):
    mko = await _order_makloon(db)
    r = await klien.get(f"/api/makloon-orders/{mko}", headers=orang["h_gdg"])
    assert r.status_code == 200, r.text
    assert [s["service_value_editable"] for s in r.json()["steps"]] == [False]
    r = await klien.get(f"/api/makloon-orders/{mko}", headers=orang["h_mgrA"])
    assert [s["service_value_editable"] for s in r.json()["steps"]] == [True]


# ── Ganti termin (FX-16) ───────────────────────────────────────────────────────────────────────────────────────────
async def _pesanan(db, termin):
    so = _id("so")
    await db.sales_orders.insert_one({
        "id": so, "number": f"SO-T-{so}", "entity_id": KSC, "customer_id": "cus_pk38_t", "customer_name": "Toko Termin",
        "status": "confirmed", "payment_term_code": termin, "grand_total": 5 * JT, "paid_total": 0, "payments": [],
        "fulfillment_method": "kirim", "order_type": "regular", "created_at": now_iso(),
        "items": [{"product_id": "prd_pk38", "product_name": "Kain PK38", "quantity": 10, "base_quantity": 10,
                   "price": 500_000, "discount_percent": 0, "unit": "meter"}]})
    return so


async def _ganti_termin(klien, h, so, termin):
    return await klien.post(f"/api/sales-orders/{so}/override", headers=h,
                            json={"header": {"payment_term_code": termin}, "note": "uji ganti termin PK-38"})


async def test_PK38_U16_cbd_ke_net30(klien, db, orang):
    so = await _pesanan(db, "CBD")
    r = await _ganti_termin(klien, orang["h_sa"], so, "NET30")
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == ("Anda belum punya akses untuk melonggarkan termin bayar (CBD → NET30). Minta Finance "
                                  "atau Manajer yang mengubahnya, atau minta Admin menambahkan akses 'Pesanan Penjualan'.")
    assert (await db.sales_orders.find_one({"id": so}))["payment_term_code"] == "CBD"
    r = await _ganti_termin(klien, orang["h_mgrA"], so, "NET30")
    assert r.status_code == 200, r.text
    ch = next(c for c in r.json()["changes"] if c["field"] == "payment_term_code")
    assert ch["loosened"] is True
    amd = await db.doc_amendments.find_one({"doc_id": so}) or await db.doc_amendments.find_one({"doc_id": so})
    assert amd and any(c.get("loosened") is True for c in amd.get("changes") or [])
    assert await jumlah("audit_logs", {"action": "so_term_loosened", "entity_id": so}) == 1


@pytest.mark.parametrize("dari,ke,kode", [("NET30", "CBD", 200), ("DP50", "NET30", 403), ("NET14", "NET30", 403),
                                          ("NET30", "NET14", 200)])
async def test_PK38_U17_arah_termin(klien, db, orang, dari, ke, kode):
    so = await _pesanan(db, dari)
    r = await _ganti_termin(klien, orang["h_sa"], so, ke)
    assert r.status_code == kode, r.text
    assert (await db.sales_orders.find_one({"id": so}))["payment_term_code"] == (ke if kode == 200 else dari)


async def test_PK38_konteks_koreksi_termin(klien, db, orang):
    so = await _pesanan(db, "CBD")
    r = await klien.get(f"/api/sales-orders/{so}/override-context", headers=orang["h_sa"])
    assert r.status_code == 200, r.text
    assert r.json()["can_loosen_term"] is False
    assert r.json()["current_term"] == {"code": "CBD", "dp_percent": 100.0, "net_days": 0}
    r = await klien.get(f"/api/sales-orders/{so}/override-context", headers=orang["h_mgrA"])
    assert r.json()["can_loosen_term"] is True
