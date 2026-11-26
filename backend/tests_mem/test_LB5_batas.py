"""Lapor Bayar CBD & DP · Tugas 5 — batas waktu bayar, kedaluwarsa otomatis, pengingat; pagar B3 sebelum disetujui (R12).

Rancangan `docs/superpowers/specs/2026-11-25-lapor-bayar-cbd-design.md` §5.3, §7-2. Pesanan `approved` ber-`pay_hold` yang
`due_at`-nya lewat dan TANPA laporan bayar `menunggu`/`memproses` dikedaluwarsakan penyapu `expire_old_reservations`
dengan langkah yang sama persis dengan kedaluwarsa cadangan (klaim atomik, roll dilepas, `expired`, jurnal dibalik, uang
muka → titipan pelanggan, notifikasi Finance `titipan_pesanan_batal`). Laporan yang masih menunggu menahan kedaluwarsa dan
Finance diberi tahu (`lapor_bayar_lewat_batas`). Pengingat H-1 `pay_due_soon` ke sales pemilik + pemegang
`order.confirm`; `reservation_expiring` hanya untuk pesanan yang memang bisa kedaluwarsa cadangannya.

Persiapan: rekening penerimaan transfer A + kas K (`ent_ksc`), pelanggan, produk Rp 10.000/m, gudang, roll 100 m per
pesanan (fixture). Pesanan dibuat lewat API (tanpa PPN), sales pemilik ditulis langsung (FIXTURE), lalu "Periksa & lepas"
→ `approved` + `pay_hold`. "Waktu berjalan" = `pay_hold.due_at` / `reservation_expires_at` dimundurkan langsung (FIXTURE).

Hitung tangan (PT `ent_ksc`, pesanan tanpa PPN): 100 m × Rp 10.000 = Rp 1.000.000 · CBD → wajib 1.000.000.
  Kwitansi Finance 400.000 (sebagian; tetap tertahan) → Dr Bank / Cr 2-1400 Uang Muka 400.000 → lewat batas →
  kedaluwarsa → uang muka 400.000 dipindah ke titipan: `deposit_balance` pelanggan + 400.000 (tanpa jurnal baru).

    cd backend && python -m pytest tests_mem/test_LB5_batas.py -q -p no:cacheprovider -n 0
"""
from __future__ import annotations

import itertools
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core_utils import now_iso
from services import config_resolver as resolver

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
TGL = "2026-11-24"
PDF = b"%PDF-1.4\n" + b"0" * 2048
TANPA_PPN = {"tax_override": "non_ppn", "tax_override_reason": "uji LB-5 tanpa PPN"}
BATAS = "sales.batas_bayar_hari"
GERBANG = "finance.dispatch_payment_gate"
DASAR = "finance.tahan_kirim_dasar_bayar"
VALIDASI = "sales.require_so_validation"
B3 = "Pesanan ini menunggu lapor bayar — pakai Lapor bayar"
ALASAN_MATI = "Pesanan sudah batal/kedaluwarsa"
_n = itertools.count(1)


def _id(awal: str) -> str:
    return f"{awal}_lb5_{uuid.uuid4().hex[:8]}"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _lalu(**kw) -> str:
    return _iso(datetime.now(timezone.utc) - timedelta(**kw))


def _nanti(**kw) -> str:
    return _iso(datetime.now(timezone.utc) + timedelta(**kw))


async def _rekening(klien, h, **isi) -> str:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], "default_receiving_methods": ["transfer"],
            "holder_name": "PT Kain Suka Cita", "entity_id": KSC, **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    A = await _rekening(klien, kepala_admin, name="BCA Penerimaan LB5", account_number="555-666-7777",
                        show_on_documents=True)
    K = await _rekening(klien, kepala_admin, name="Kas Kecil LB5", account_type="cash", bank_name="",
                        payment_method_codes=["cash"], default_receiving_methods=["cash"])
    cus, adr, prd = _id("cus"), _id("adr"), _id("prd")
    await db.customers.insert_one({"id": cus, "name": "Toko LB-5", "entity_id": KSC, "status": "active",
                                   "addresses": [{"id": adr, "label": "Utama", "city": "Bandung",
                                                  "address": "Jl. Uji 5", "recipient_name": "Bu Uji",
                                                  "phone": "081200000005"}]})
    await db.products.insert_one({"id": prd, "sku": "LB5-KAIN", "name": "Kain LB-5", "price": 10000,
                                  "base_unit": "meter", "status": "active", "lifecycle": "produksi", "category": "uji"})
    await db.warehouses.insert_one({"id": "wh_lb5", "name": "Gudang LB-5", "entity_id": KSC, "city": "Bandung"})
    sales = await akun("sales")
    sa = await akun("sales_admin")
    fin = await akun("finance")
    return {"h": kepala_admin, "A": A, "K": K, "cus": cus, "adr": adr, "prd": prd,
            "sales": sales, "sa": sa, "fin": fin,
            "h_sales": await sesi(sales), "h_sa": await sesi(sa), "h_fin": await sesi(fin)}


async def _so(db, oid: str) -> dict:
    return await db.sales_orders.find_one({"id": oid}, {"_id": 0})


async def _buat(klien, db, siap, term: str = "CBD", *, prd: str = "") -> dict:
    """Pesanan lewat API (status `reserved`), sales pemilik ditulis langsung (FIXTURE). `prd` = produk lain tanpa roll
    → backorder murni → `waiting_stock`."""
    if not prd:
        await db.inventory_rolls.insert_one({
            "id": _id("roll"), "roll_no": f"R-LB5-{next(_n)}", "product_id": siap["prd"], "owner_entity_id": KSC,
            "warehouse_id": "wh_lb5", "status": "available", "active_movement": None, "length_remaining": 100.0,
            "lot": "L-LB5", "created_at": now_iso()})
    body = {"customer_id": siap["cus"], "shipping_address_id": siap["adr"], "entity_id": KSC,
            "payment_term_code": term, "payment_method_code": "transfer", "receiving_account_id": siap["A"],
            "items": [{"product_id": prd or siap["prd"], "quantity": 100, "unit": "meter"}], **TANPA_PPN,
            **({"allow_backorder": True} if prd else {})}
    r = await klien.post("/api/sales-orders", headers=siap["h"], json=body)
    assert r.status_code == 200, r.text
    so = r.json()
    assert so["grand_total"] == 1_000_000, so["grand_total"]
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"sales_id": siap["sales"]["id"]}})   # FIXTURE
    return await _so(db, so["id"])


async def _pesan(klien, db, siap, term: str = "CBD") -> dict:
    """Pesanan CBD yang sudah "Periksa & lepas" → `approved` + `pay_hold`."""
    so = await _buat(klien, db, siap, term)
    r = await klien.post(f"/api/sales-orders/{so['id']}/review-release", headers=siap["h"], json={"note": "uji"})
    assert r.status_code == 200, r.text
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["pay_hold"], cur.get("status")
    return cur


async def _lewat_batas(db, oid: str) -> None:
    await db.sales_orders.update_one({"id": oid}, {"$set": {"pay_hold.due_at": _lalu(hours=1)}})   # FIXTURE


async def _lapor(klien, siap, oid: str, amount: float = 1_000_000) -> dict:
    r = await klien.post(f"/api/sales-orders/{oid}/payment-reports", headers=siap["h_sa"], json={
        "amount": amount, "transfer_date": TGL, "account_id": siap["A"], "method": "transfer",
        "reference_no": f"TRF-LB5-{next(_n)}", "note": "uji LB-5"})
    assert r.status_code == 200, r.text
    rep = r.json()
    r = await klien.post(f"/api/payment-reports/{rep['id']}/attachments", headers=siap["h_sa"],
                         files={"file": ("bukti.pdf", PDF, "application/pdf")})
    assert r.status_code == 200, r.text
    return rep


async def _kwitansi_finance(siap, oid: str, nominal: float) -> dict:
    from services import ar_receipt_service as ars
    return await ars.create_receipt({
        "customer_id": siap["cus"], "entity_id": KSC, "amount": nominal, "method": "transfer",
        "account_id": siap["A"], "reference_no": f"TRF-LB5-{next(_n)}",
        "allocations": [{"order_id": oid, "amount": nominal}]},
        {"id": siap["fin"]["id"], "name": siap["fin"]["name"], "role": "finance"})


async def _titipan(db, cus: str) -> float:
    c = await db.customers.find_one({"id": cus}, {"_id": 0, "deposit_balance": 1})
    return round(float((c or {}).get("deposit_balance") or 0), 2)


async def _notif(db, jenis: str, ref: str) -> list:
    return await db.notifications.find({"type": jenis, "ref": {"$regex": f"^{ref}(#|$)"}}, {"_id": 0}).to_list(50)


async def _penyapu() -> int:
    from services.inventory_service import expire_old_reservations
    return await expire_old_reservations()


async def _pemegang(permission: tuple) -> set:
    from services import notification_audience as aud
    return {u["id"] for u in await aud.resolve_recipients(permission=permission, entity_id=KSC)}


# ── Batas bayar per PT ───────────────────────────────────────────────────────────────────────────────────────────────
async def test_due_at_mengikuti_pengaturan_pt(klien, db, siap):
    from services import pay_hold_service as phs
    await resolver.set_value(BATAS, 2, scope_type="entity", scope_id=KSC, actor="uji", reason="uji LB-5")
    try:
        so = await _pesan(klien, db, siap)
        hold = so["pay_hold"]
        assert datetime.fromisoformat(hold["due_at"]) - datetime.fromisoformat(hold["since"]) == timedelta(days=2)
        t0 = datetime(2026, 11, 23, 3, 0, tzinfo=timezone.utc)
        assert await phs.due_at(KSC, t0) - t0 == timedelta(days=2)
        assert await phs.due_at(KANDA, t0) - t0 == timedelta(days=3)          # PT lain tetap bawaan
    finally:
        await resolver.clear_layer(BATAS, scope_type="entity", scope_id=KSC, actor="uji", reason="pulihkan uji LB-5")
    from services import pay_hold_service as phs2
    t0 = datetime(2026, 11, 23, 3, 0, tzinfo=timezone.utc)
    assert await phs2.due_at(KSC, t0) - t0 == timedelta(days=3)


def test_katalog_batas_bayar_menyebut_pembaca_nyata():
    import config_registry as registry
    from services import config_health
    entry = next(e for e in registry.all_entries() if e["key"] == BATAS)
    hasil = config_health.check_entry(entry)
    assert hasil["wiring_status"] == "OK", hasil
    assert "services/pay_hold_service.py:due_at" in entry["consumers"]


# ── Lewat batas → kedaluwarsa (langkah yang sama dengan kedaluwarsa cadangan) ────────────────────────────────────────
async def test_lewat_batas_kedaluwarsa_stok_lepas_uang_ke_titipan(klien, db, siap):
    so = await _pesan(klien, db, siap)
    assert await db.inventory_rolls.count_documents({"reserved_ref.id": so["id"]}) >= 1
    kw = await _kwitansi_finance(siap, so["id"], 400_000)            # sebagian: tetap tertahan
    assert kw["released_order_ids"] == []
    cur = await _so(db, so["id"])
    assert cur["pay_hold"] and cur["paid_total"] == 400_000
    titip_awal = await _titipan(db, siap["cus"])
    await _lewat_batas(db, so["id"])
    assert await _penyapu() >= 1
    cur = await _so(db, so["id"])
    assert cur["status"] == "expired" and cur["allocations"] == [] and "saga_lock" not in cur
    assert await db.inventory_rolls.count_documents({"reserved_ref.id": so["id"],
                                                     "status": {"$nin": ["available"]}}) == 0
    # uang muka 400.000 → titipan pelanggan (tanpa jurnal baru) + Finance diberi tahu
    assert cur["advance_to_deposit"]["amount"] == 400_000 and cur["advance_to_deposit"]["deposit_done"] is True
    assert await _titipan(db, siap["cus"]) == round(titip_awal + 400_000, 2)
    notif = await _notif(db, "titipan_pesanan_batal", f"titipan_pesanan_batal:{so['id']}")
    assert notif and {n["recipient_user"] for n in notif} <= await _pemegang(("payment_variance", "decide"))
    assert siap["fin"]["id"] in {n["recipient_user"] for n in notif}
    assert all("kedaluwarsa" in n["title"] for n in notif)
    assert await db.audit_logs.count_documents({"action": "pay_hold_expired", "entity_id": so["id"]}) == 1
    # aman diulang: putaran berikutnya tidak menyentuh pesanan ini lagi
    await _penyapu()
    assert await _titipan(db, siap["cus"]) == round(titip_awal + 400_000, 2)
    assert await db.audit_logs.count_documents({"action": "pay_hold_expired", "entity_id": so["id"]}) == 1


async def test_satu_pesanan_gagal_tidak_menghentikan_penyapu(klien, db, siap, monkeypatch):
    """R13 (Minor-3) — galat pada satu pesanan dicatat dan dilewati; pesanan berikutnya tetap dikedaluwarsakan. Galat
    sesudah klaim sebelum tulisan apa pun → kunci dilepas; galat sesudah tulisan dimulai → kunci tertinggal bertanda gagal
    (pola saga, terlihat di Kunci Saga)."""
    from services import pay_hold_service as phs
    from services import roll_service
    rusak_tulis = await _pesan(klien, db, siap)
    rusak_periksa = await _pesan(klien, db, siap)
    sehat = await _pesan(klien, db, siap)
    for so in (rusak_tulis, rusak_periksa, sehat):
        await _lewat_batas(db, so["id"])
    asli_lepas, asli_nasib = roll_service.release_order_rolls, phs.nasib_lewat_batas

    async def lepas(order_id, *a, **kw):
        if order_id == rusak_tulis["id"]:
            raise RuntimeError("uji: lepas roll gagal")
        return await asli_lepas(order_id, *a, **kw)

    async def nasib(so):
        if so["id"] == rusak_periksa["id"] and so.get("saga_lock"):   # periksa ulang SESUDAH klaim
            raise RuntimeError("uji: periksa ulang gagal")
        return await asli_nasib(so)

    monkeypatch.setattr(roll_service, "release_order_rolls", lepas)
    monkeypatch.setattr(phs, "nasib_lewat_batas", nasib)
    await _penyapu()
    a = await _so(db, rusak_tulis["id"])
    assert a["status"] == "approved" and a["saga_lock"].get("failed_at") and "lepas roll gagal" in a["saga_lock"]["error"]
    b = await _so(db, rusak_periksa["id"])
    assert b["status"] == "approved" and "saga_lock" not in b
    assert (await _so(db, sehat["id"]))["status"] == "expired"
    monkeypatch.setattr(phs, "nasib_lewat_batas", asli_nasib)
    await _penyapu()
    assert (await _so(db, rusak_periksa["id"]))["status"] == "expired"     # kunci dilepas → putaran berikutnya jalan


async def test_belum_lewat_batas_tidak_disentuh(klien, db, siap):
    so = await _pesan(klien, db, siap)
    await _penyapu()
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["pay_hold"]


# ── Review Focus 3 — laporan menunggu menahan kedaluwarsa ────────────────────────────────────────────────────────────
async def test_laporan_menunggu_menahan_kedaluwarsa_dan_memberi_tahu_finance(klien, db, siap):
    from services import payment_report_service as prs
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    await _lewat_batas(db, so["id"])
    await _penyapu()
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["pay_hold"]
    assert (await db.payment_reports.find_one({"id": rep["id"]}))["status"] == "menunggu"
    notif = await _notif(db, "lapor_bayar_lewat_batas", f"lapor_lewat:{so['id']}")
    assert notif, "Finance tidak diberi tahu laporan menunggu yang lewat batas"
    assert {n["recipient_user"] for n in notif} == await _pemegang(("payment_report", "decide"))
    assert siap["sales"]["id"] not in {n["recipient_user"] for n in notif}
    assert all(so["number"] in n["title"] and rep["number"] in n["body"] for n in notif)
    # satu per pesanan per hari: putaran berikutnya hari yang sama tidak menambah
    await _penyapu()
    assert len(await _notif(db, "lapor_bayar_lewat_batas", f"lapor_lewat:{so['id']}")) == len(notif)
    # `memproses` (baru maupun basi) juga menahan kedaluwarsa
    for menit in (1, prs.KLAIM_BASI_MENIT + 5):
        await db.payment_reports.update_one({"id": rep["id"]}, {"$set": {"status": "memproses", "claim": {
            "token": "klaim_uji", "by": "usr_x", "by_name": "Finance X", "at": _lalu(minutes=menit)}}})
        await _penyapu()
        assert (await _so(db, so["id"]))["status"] == "approved", menit
    # laporan ditolak → putaran berikutnya mengedaluwarsakan
    await db.payment_reports.update_one({"id": rep["id"]}, {"$set": {"status": "menunggu"}, "$unset": {"claim": ""}})
    r = await klien.post(f"/api/payment-reports/{rep['id']}/tolak", headers=siap["h_fin"],
                         json={"reason": "Bukti transfer tidak terbaca"})
    assert r.status_code == 200, r.text
    await _penyapu()
    assert (await _so(db, so["id"]))["status"] == "expired"


async def test_laporan_menunggu_menahan_kedaluwarsa_cadangan(klien, db, siap):
    """Pesanan CBD yang belum disetujui (`reserved`) boleh dilapor bayar; laporan menunggu juga menahan kedaluwarsa
    cadangannya (penyapu yang sama, Review Focus 3)."""
    so = await _buat(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"reservation_expires_at": _lalu(hours=1)}})
    await _penyapu()
    assert (await _so(db, so["id"]))["status"] == "reserved"
    assert (await db.payment_reports.find_one({"id": rep["id"]}))["status"] == "menunggu"
    assert await _notif(db, "lapor_bayar_lewat_batas", f"lapor_lewat:{so['id']}")


# ── Laporan yang tertinggal di pesanan mati ──────────────────────────────────────────────────────────────────────────
async def test_laporan_pada_pesanan_mati_ditolak_penyapu(klien, db, siap):
    from services import payment_report_service as prs
    kasus = {}
    for nama in ("menunggu", "basi", "baru", "basi_berkwitansi", "basi_setengah"):
        so = await _pesan(klien, db, siap)
        rep = await _lapor(klien, siap, so["id"])
        kasus[nama] = (so, rep)
    klaim = lambda menit: {"token": "klaim_uji", "by": "usr_x", "by_name": "Finance X", "at": _lalu(minutes=menit)}  # noqa: E731
    await db.payment_reports.update_one({"id": kasus["basi"][1]["id"]}, {"$set": {
        "status": "memproses", "claim": klaim(prs.KLAIM_BASI_MENIT + 5)}})
    await db.payment_reports.update_one({"id": kasus["baru"][1]["id"]}, {"$set": {"status": "memproses",
                                                                                 "claim": klaim(1)}})
    await db.payment_reports.update_one({"id": kasus["basi_berkwitansi"][1]["id"]}, {"$set": {
        "status": "memproses", "claim": klaim(prs.KLAIM_BASI_MENIT + 5)}})
    await db.payment_reports.update_one({"id": kasus["basi_setengah"][1]["id"]}, {"$set": {
        "status": "memproses", "claim": klaim(prs.KLAIM_BASI_MENIT + 5)}})
    kw_ada = _id("arc")
    await db.ar_receipts.insert_one({"id": kw_ada, "number": "AR-LB5-ADA", "status": "posted",
                                     "effects_done": True, "payment_report_id": kasus["basi_berkwitansi"][1]["id"],
                                     "customer_id": siap["cus"], "entity_id": KSC, "amount": 1_000_000,
                                     "created_at": now_iso()})
    await db.ar_receipts.insert_one({"id": _id("arc"), "number": "AR-LB5-SETENGAH", "status": "posted",
                                     "effects_done": False, "payment_report_id": kasus["basi_setengah"][1]["id"],
                                     "customer_id": siap["cus"], "entity_id": KSC, "amount": 1_000_000,
                                     "created_at": now_iso()})
    for nama, (so, _rep) in kasus.items():
        await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "cancelled" if nama != "basi"
                                                                     else "expired"}})
    await _penyapu()
    for nama in ("menunggu", "basi"):
        so, rep = kasus[nama]
        lap = await db.payment_reports.find_one({"id": rep["id"]}, {"_id": 0})
        assert lap["status"] == "ditolak" and lap["reason"] == ALASAN_MATI, (nama, lap["status"])
        assert "claim" not in lap
        assert lap["status_history"][-1]["status"] == "ditolak"
        assert lap["status_history"][-1]["note"] == ALASAN_MATI
        assert lap["status_history"][-1].get("timestamp")
        notif = await _notif(db, "lapor_bayar_ditolak", rep["id"])
        assert siap["sa"]["id"] in {n["recipient_user"] for n in notif}, nama        # pelapor diberi tahu
        assert await db.audit_logs.count_documents({"action": "payment_report_rejected", "entity_id": rep["id"]}) == 1
    assert (await db.payment_reports.find_one({"id": kasus["baru"][1]["id"]}))["status"] == "memproses"
    # R13 (Minor-1) — kwitansi laporan ini sudah tuntas (uang benar): laporan diselesaikan `diterima` dengan kwitansi itu
    rid = kasus["basi_berkwitansi"][1]["id"]
    lap = await db.payment_reports.find_one({"id": rid}, {"_id": 0})
    assert lap["status"] == "diterima" and "claim" not in lap, lap["status"]
    assert (lap["receipt_id"], lap["receipt_number"]) == (kw_ada, "AR-LB5-ADA")
    assert lap["status_history"][-1]["status"] == "diterima" and "AR-LB5-ADA" in lap["status_history"][-1]["note"]
    assert lap["status_history"][-1].get("timestamp")
    assert await db.audit_logs.count_documents({"action": "payment_report_accepted", "entity_id": rid}) == 1
    assert siap["sa"]["id"] in {n["recipient_user"] for n in await _notif(db, "lapor_bayar_diterima", rid)}
    assert await db.ar_receipts.count_documents({"payment_report_id": rid}) == 1          # tanpa kwitansi kedua
    # kwitansi setengah jadi: tetap `memproses` (perilaku lama — dicatat di log)
    assert (await db.payment_reports.find_one({"id": kasus["basi_setengah"][1]["id"]}))["status"] == "memproses"
    # aman diulang
    n_notif = await db.notifications.count_documents({"type": {"$in": ["lapor_bayar_ditolak", "lapor_bayar_diterima"]}})
    await _penyapu()
    assert await db.notifications.count_documents(
        {"type": {"$in": ["lapor_bayar_ditolak", "lapor_bayar_diterima"]}}) == n_notif
    assert await db.audit_logs.count_documents({"action": "payment_report_accepted", "entity_id": rid}) == 1


# ── Bukan lagi wajib bayar / uang sudah tercatat ─────────────────────────────────────────────────────────────────────
async def test_tahan_yang_tidak_lagi_menahan_tidak_dikedaluwarsakan(klien, db, siap):
    """Gerbang dimatikan untuk PT sesudah tahan dimulai: lewat batas tidak mengedaluwarsakan; tahan basi dibuka."""
    so = await _pesan(klien, db, siap)
    await _lewat_batas(db, so["id"])
    await resolver.set_value(GERBANG, "off", scope_type="entity", scope_id=KSC, actor="uji", reason="uji LB-5")
    try:
        await _penyapu()
        cur = await _so(db, so["id"])
        assert cur["status"] in ("approved", "confirmed") and not cur.get("pay_hold"), cur["status"]
    finally:
        await resolver.clear_layer(GERBANG, scope_type="entity", scope_id=KSC, actor="uji", reason="pulihkan uji LB-5")


async def test_terverifikasi_uang_tercatat_lunas_tidak_dikedaluwarsakan(klien, db, siap):
    """Dasar `terverifikasi`: kwitansi lunas tercatat tetapi belum cocok mutasi bank — yang terlambat pengecekan
    Finance, bukan pelanggan: pesanan tidak dikedaluwarsakan; Finance diberi tahu."""
    await resolver.set_value(DASAR, "terverifikasi", scope_type="entity", scope_id=KSC, actor="uji", reason="uji LB-5")
    try:
        so = await _pesan(klien, db, siap)
        await _kwitansi_finance(siap, so["id"], 1_000_000)
        cur = await _so(db, so["id"])
        assert cur["pay_hold"] and cur["paid_total"] == 1_000_000
        await _lewat_batas(db, so["id"])
        await _penyapu()
        cur = await _so(db, so["id"])
        assert cur["status"] == "approved" and cur["pay_hold"]
        assert await _notif(db, "lapor_bayar_lewat_batas", f"lapor_lewat:{so['id']}")
    finally:
        await resolver.clear_layer(DASAR, scope_type="entity", scope_id=KSC, actor="uji", reason="pulihkan uji LB-5")


async def test_pesanan_tanpa_pay_hold_tidak_tersentuh_penyapu_baru(db, siap):
    """Pesanan `approved` tanpa penanda (CBD lama sebelum fitur, NET30, SO pesanan khusus) tidak pernah kedaluwarsa
    otomatis — walau tanggal cadangannya sudah lewat (FIX-3b / K-B2b-12)."""
    ids = []
    for nomor, isi in (("SO-LB5-LAMA", {"payment_term_code": "CBD"}),
                       ("SO-LB5-NET", {"payment_term_code": "NET30"}),
                       ("SO-LB5-OD", {"payment_term_code": "CBD", "source_special_order_id": "od_lb5"}),
                       ("SO-LB5-STOK", {"payment_term_code": "CBD", "status": "waiting_stock"})):
        oid = _id("so")
        ids.append(oid)
        await db.sales_orders.insert_one({
            "id": oid, "number": nomor, "entity_id": KSC, "status": "approved", "customer_id": siap["cus"],
            "customer_name": "Toko LB-5", "grand_total": 1_000_000.0, "paid_total": 0, "payments": [], "items": [],
            "reservation_expires_at": _lalu(days=5), "created_at": now_iso(), **isi})
    await _penyapu()
    for oid in ids:
        cur = await _so(db, oid)
        assert cur["status"] in ("approved", "waiting_stock"), (cur["number"], cur["status"])
        assert await db.audit_logs.count_documents({"entity_id": oid}) == 0


# ── Pengingat ───────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_pengingat_h1_ke_sales_pemilik(klien, db, siap):
    from services.notification_service import generate_system_notifications
    so = await _pesan(klien, db, siap)
    jauh = await _pesan(klien, db, siap)
    dilapor = await _pesan(klien, db, siap)
    await _lapor(klien, siap, dilapor["id"])
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"pay_hold.due_at": _nanti(hours=20)}})
    await db.sales_orders.update_one({"id": jauh["id"]}, {"$set": {"pay_hold.due_at": _nanti(hours=30)}})
    await db.sales_orders.update_one({"id": dilapor["id"]}, {"$set": {"pay_hold.due_at": _nanti(hours=20)}})
    await generate_system_notifications()
    notif = await _notif(db, "pay_due_soon", f"paydue:{so['id']}")
    penerima = {n["recipient_user"] for n in notif}
    assert siap["sales"]["id"] in penerima
    assert penerima == await _pemegang(("order", "confirm")) | {siap["sales"]["id"]}
    assert all(so["number"] in n["title"] and n["severity"] == "warning" for n in notif)
    assert all("WIB" in n["body"] for n in notif)
    assert await _notif(db, "pay_due_soon", f"paydue:{jauh['id']}") == []          # > 24 jam (bawaan)
    assert await _notif(db, "pay_due_soon", f"paydue:{dilapor['id']}") == []       # laporan menunggu: tidak gugur
    # sudah lunas tetapi penanda belum dibuka: tidak ada yang perlu dibayar → tanpa pengingat
    lunas = await _pesan(klien, db, siap)
    await db.sales_orders.update_one({"id": lunas["id"]}, {"$set": {"pay_hold.due_at": _nanti(hours=20),
                                                                    "paid_total": 1_000_000}})   # FIXTURE
    await generate_system_notifications()
    assert await _notif(db, "pay_due_soon", f"paydue:{lunas['id']}") == []
    # satu pengingat per pesanan per orang (job pindai berjalan tiap beberapa jam)
    await db.notifications.update_many({"type": "pay_due_soon"}, {"$set": {"read": True}})
    await generate_system_notifications()
    assert len(await _notif(db, "pay_due_soon", f"paydue:{so['id']}")) == len(notif)


async def test_reservation_expiring_tidak_lagi_untuk_approved(klien, db, siap):
    from services.notification_service import generate_system_notifications
    ids = {}
    for status in ("reserved", "waiting_approval", "approved", "waiting_stock"):
        oid = _id("so")
        ids[status] = oid
        await db.sales_orders.insert_one({
            "id": oid, "number": f"SO-LB5-R-{status}", "entity_id": KSC, "status": status,
            "customer_id": siap["cus"], "customer_name": "Toko LB-5", "sales_id": siap["sales"]["id"],
            "total_amount": 1, "pending_approvals": [], "reservation_expires_at": _nanti(hours=5),
            "created_at": now_iso()})
    # CBD `reserved` yang laporan bayarnya menunggu: tidak gugur (penyapu menahannya) → tanpa pengingat "gugur"
    dilapor = await _buat(klien, db, siap)
    await _lapor(klien, siap, dilapor["id"])
    await db.sales_orders.update_one({"id": dilapor["id"]}, {"$set": {"reservation_expires_at": _nanti(hours=5)}})
    await generate_system_notifications()
    for status, oid in ids.items():
        ada = bool(await _notif(db, "reservation_expiring", f"resv:{oid}"))
        assert ada is (status in ("reserved", "waiting_approval")), status
    assert await _notif(db, "reservation_expiring", f"resv:{dilapor['id']}") == []


# ── R12 — pagar B3 sejak sebelum disetujui ───────────────────────────────────────────────────────────────────────────
def _kw(siap, oid, nominal, method="transfer", account=None, **lain) -> dict:
    return {"customer_id": siap["cus"], "entity_id": KSC, "amount": nominal, "method": method,
            "account_id": account or siap["A"], "reference_no": f"TRF-LB5-{next(_n)}",
            "allocations": [{"order_id": oid, "amount": nominal}] if oid else [], **lain}


async def test_R12_sales_transfer_ke_cbd_reserved_dan_waiting_approval_409(klien, db, siap):
    so = await _buat(klien, db, siap)
    assert so["status"] == "reserved" and not so.get("pay_hold")
    n = await db.ar_receipts.count_documents({})
    r = await klien.post("/api/ar-receipts", headers=siap["h_sales"], json=_kw(siap, so["id"], 1_000_000))
    assert (r.status_code, r.json()["detail"]) == (409, B3), r.text
    await resolver.set_value(VALIDASI, True, scope_type="entity", scope_id=KSC, actor="uji", reason="uji LB-5")
    try:
        so2 = await _buat(klien, db, siap)
        r = await klien.post(f"/api/sales-orders/{so2['id']}/review-release", headers=siap["h"], json={"note": "uji"})
        assert r.status_code == 200, r.text
        cur = await _so(db, so2["id"])
        assert cur["status"] == "waiting_approval" and not cur.get("pay_hold")
        r = await klien.post("/api/ar-receipts", headers=siap["h_sales"], json=_kw(siap, so2["id"], 1_000_000))
        assert (r.status_code, r.json()["detail"]) == (409, B3), r.text
    finally:
        await resolver.clear_layer(VALIDASI, scope_type="entity", scope_id=KSC, actor="uji", reason="pulihkan uji LB-5")
    assert await db.ar_receipts.count_documents({}) == n
    assert not (await _so(db, so["id"])).get("payments") and not (await _so(db, so2["id"])).get("payments")


async def test_R12_finance_net30_dan_tunai_tetap_boleh(klien, db, siap):
    # Finance (pemegang payment_report.decide) → boleh ke CBD `reserved`
    so = await _buat(klien, db, siap)
    r = await klien.post("/api/ar-receipts", headers=siap["h_fin"], json=_kw(siap, so["id"], 300_000))
    assert r.status_code == 200, r.text
    # NET30 `reserved` (tidak wajib bayar dulu) → sales tetap boleh transfer
    net = await _buat(klien, db, siap, term="NET30")
    r = await klien.post("/api/ar-receipts", headers=siap["h_sales"], json=_kw(siap, net["id"], 200_000))
    assert r.status_code == 200, r.text
    # sales tunai ke CBD `reserved` → aturan tunai yang ada (bawaan kas langsung)
    so2 = await _buat(klien, db, siap)
    r = await klien.post("/api/ar-receipts", headers=siap["h_sales"],
                         json=_kw(siap, so2["id"], 400_000, method="cash", account=siap["K"],
                                  mismatch_note="Pelanggan bayar tunai ke sales"))
    assert r.status_code == 200, r.text


async def test_R13_sales_transfer_ke_cbd_waiting_stock_409_finance_boleh(klien, db, siap):
    """R13 — pesanan CBD backorder murni (`waiting_stock`, sebelum disetujui & gudang) juga dipagari B3; penyapu dan
    pengingat tidak berubah untuk `waiting_stock` tanpa penanda (tidak kedaluwarsa, tanpa pengingat)."""
    from services.notification_service import generate_system_notifications
    kosong = _id("prd")
    await db.products.insert_one({"id": kosong, "sku": f"LB5-KOSONG-{next(_n)}", "name": "Kain LB-5 kosong",
                                  "price": 10000, "base_unit": "meter", "status": "active", "lifecycle": "produksi",
                                  "category": "uji"})
    so = await _buat(klien, db, siap, prd=kosong)
    assert so["status"] == "waiting_stock" and not so.get("pay_hold"), so["status"]
    r = await klien.post("/api/ar-receipts", headers=siap["h_sales"], json=_kw(siap, so["id"], 1_000_000))
    assert (r.status_code, r.json().get("detail")) == (409, B3), r.text
    assert not (await _so(db, so["id"])).get("payments")
    r = await klien.post("/api/ar-receipts", headers=siap["h_fin"], json=_kw(siap, so["id"], 300_000))
    assert r.status_code == 200, r.text
    assert (await _so(db, so["id"]))["paid_total"] == 300_000
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"reservation_expires_at": _lalu(days=1)}})
    await _penyapu()
    cur = await _so(db, so["id"])
    assert cur["status"] == "waiting_stock" and not cur.get("pay_hold") and "saga_lock" not in cur
    assert await db.audit_logs.count_documents({"entity_id": so["id"], "action": {"$in": [
        "reservation_expired", "pay_hold_expired"]}}) == 0
    assert await _notif(db, "lapor_bayar_lewat_batas", f"lapor_lewat:{so['id']}") == []
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"reservation_expires_at": _nanti(hours=5)}})
    await generate_system_notifications()
    assert await _notif(db, "reservation_expiring", f"resv:{so['id']}") == []
    assert await _notif(db, "pay_due_soon", f"paydue:{so['id']}") == []


async def test_R12_titipan_dan_pengecualian_berizin(klien, db, siap):
    """Satu predikat untuk semua jalan: titipan pelanggan ke CBD `reserved` oleh sales → 409; pesanan yang sudah diberi
    pengecualian "kirim tanpa lunas" (B6) dan SO pesanan khusus tidak dinilai."""
    from services import ar_receipt_service as ars
    from fastapi import HTTPException
    so = await _buat(klien, db, siap)
    await db.customers.update_one({"id": siap["cus"]}, {"$inc": {"deposit_balance": 100_000}})   # FIXTURE titipan
    try:
        r = await klien.post("/api/ar-receipts", headers=siap["h_sales"], json={
            "customer_id": siap["cus"], "entity_id": KSC, "amount": 0, "use_deposit_amount": 100_000,
            "allocations": [{"order_id": so["id"], "amount": 100_000}]})
        assert (r.status_code, r.json()["detail"]) == (409, B3), r.text
    finally:
        await db.customers.update_one({"id": siap["cus"]}, {"$inc": {"deposit_balance": -100_000}})
    sales = {"id": siap["sales"]["id"], "name": siap["sales"]["name"], "role": "sales"}
    with pytest.raises(HTTPException) as e:
        await ars.pagar_lapor_bayar(sales, [f"  {so['id']} "])
    assert (e.value.status_code, e.value.detail) == (409, B3)
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"dispatch_payment_release": {
        "reason": "uji", "by": "Finance", "at": now_iso()}}})
    await ars.pagar_lapor_bayar(sales, [so["id"]])                       # sudah diberi pengecualian berizin
    od = _id("so")
    await db.sales_orders.insert_one({"id": od, "number": "SO-LB5-OD2", "entity_id": KSC, "status": "approved",
                                      "customer_id": siap["cus"], "payment_term_code": "CBD",
                                      "source_special_order_id": "od_lb5b", "grand_total": 1_000_000.0,
                                      "paid_total": 0, "payments": [], "items": [], "created_at": now_iso()})
    await ars.pagar_lapor_bayar(sales, [od])                             # SO pesanan khusus: dikecualikan seperti start()
