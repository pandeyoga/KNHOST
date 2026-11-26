"""Lapor Bayar CBD & DP · Tugas 4 — Finance menerima / menolak laporan bayar; B3 di server.

Rancangan `docs/superpowers/specs/2026-11-25-lapor-bayar-cbd-design.md` §5.4, §7-5. Terima = kwitansi AR biasa lewat
`ar_receipt_service.create_receipt` (satu pintu kas), lalu tahan bayar dibuka dan pesanan dilepas otomatis bila Admin
Sales sudah "Periksa & lepas". Tolak = tanpa uang. Kwitansi transfer dari pencatat tanpa `payment_report.decide` ke
pesanan yang tertahan bayar ditolak 409 (B3).

Persiapan: rekening penerimaan transfer A + kas K (`ent_ksc`), pelanggan, produk Rp 10.000/m, gudang, roll 100 m per
pesanan. Pesanan dibuat lewat API (tanpa PPN), sales pemilik ditulis langsung (FIXTURE), lalu "Periksa & lepas" →
`approved` + `pay_hold` + `release.waiting = "bayar"`. Laporan dibuat Admin Sales (pelapor ≠ sales pemilik) + satu PDF.

Hitung tangan (PT `ent_ksc`, pesanan tanpa PPN):
  100 m × Rp 10.000 = Rp 1.000.000 · CBD (DP 100 %) → wajib 1.000.000 · DP50 → wajib 500.000.
  Terima laporan Rp 1.000.000 → kwitansi AR Rp 1.000.000 ke rekening A bertanggal transfer → kas masuk → jurnal
  Dr 1-1100 Bank 1.000.000 / Cr 2-1400 Uang Muka Pelanggan 1.000.000 (pesanan belum dikirim) → wajib terpenuhi →
  tahan dibuka → `confirmed` + tugas gudang.
  DP50: laporan 300.000 → kwitansi 300.000, kurang 200.000 → tetap tertahan; laporan 200.000 → lepas.

    cd backend && python -m pytest tests_mem/test_LB4_putus.py -q -p no:cacheprovider -n 0
"""
from __future__ import annotations

import asyncio
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
TANPA_PPN = {"tax_override": "non_ppn", "tax_override_reason": "uji LB-4 tanpa PPN"}
DASAR = "finance.tahan_kirim_dasar_bayar"
B3 = "Pesanan ini menunggu lapor bayar — pakai Lapor bayar"
MATI = "Pesanan sudah batal/kedaluwarsa — tolak laporan ini"
_n = itertools.count(1)


def _id(awal: str) -> str:
    return f"{awal}_lb4_{uuid.uuid4().hex[:8]}"


async def _rekening(klien, h, **isi) -> str:
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], "default_receiving_methods": ["transfer"],
            "holder_name": "PT Kain Suka Cita", "entity_id": KSC, **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    A = await _rekening(klien, kepala_admin, name="BCA Penerimaan LB4", account_number="444-555-6666",
                        show_on_documents=True)
    K = await _rekening(klien, kepala_admin, name="Kas Kecil LB4", account_type="cash", bank_name="",
                        payment_method_codes=["cash"], default_receiving_methods=["cash"])
    B = await _rekening(klien, kepala_admin, name="Mandiri Penerimaan LB4", bank_name="Mandiri",
                        account_number="777-888-9999", default_receiving_methods=[])   # rekening penerimaan kedua PT
    cus, adr, prd = _id("cus"), _id("adr"), _id("prd")
    await db.customers.insert_one({"id": cus, "name": "Toko LB-4", "entity_id": KSC, "status": "active",
                                   "addresses": [{"id": adr, "label": "Utama", "city": "Bandung",
                                                  "address": "Jl. Uji 4", "recipient_name": "Bu Uji",
                                                  "phone": "081200000004"}]})
    await db.products.insert_one({"id": prd, "sku": "LB4-KAIN", "name": "Kain LB-4", "price": 10000,
                                  "base_unit": "meter", "status": "active", "lifecycle": "produksi", "category": "uji"})
    await db.warehouses.insert_one({"id": "wh_lb4", "name": "Gudang LB-4", "entity_id": KSC, "city": "Bandung"})
    sales = await akun("sales")
    sa = await akun("sales_admin")
    fin = await akun("finance")
    fin_kanda = await akun("finance", entitas=(KANDA,))
    return {"h": kepala_admin, "A": A, "B": B, "K": K, "cus": cus, "adr": adr, "prd": prd,
            "sales": sales, "sa": sa, "fin": fin,
            "h_sales": await sesi(sales), "h_sa": await sesi(sa), "h_fin": await sesi(fin),
            "h_fin_kanda": await sesi(fin_kanda, entitas=KANDA)}


async def _so(db, oid: str) -> dict:
    return await db.sales_orders.find_one({"id": oid}, {"_id": 0})


async def _pesan(klien, db, siap, term: str = "CBD", *, periksa: bool = True) -> dict:
    await db.inventory_rolls.insert_one({
        "id": _id("roll"), "roll_no": f"R-LB4-{next(_n)}", "product_id": siap["prd"], "owner_entity_id": KSC,
        "warehouse_id": "wh_lb4", "status": "available", "active_movement": None, "length_remaining": 100.0,
        "lot": "L-LB4", "created_at": now_iso()})
    body = {"customer_id": siap["cus"], "shipping_address_id": siap["adr"], "entity_id": KSC,
            "payment_term_code": term, "payment_method_code": "transfer", "receiving_account_id": siap["A"],
            "items": [{"product_id": siap["prd"], "quantity": 100, "unit": "meter"}], **TANPA_PPN}
    r = await klien.post("/api/sales-orders", headers=siap["h"], json=body)
    assert r.status_code == 200, r.text
    so = r.json()
    assert so["grand_total"] == 1_000_000, so["grand_total"]
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"sales_id": siap["sales"]["id"]}})   # FIXTURE
    if periksa:
        r = await klien.post(f"/api/sales-orders/{so['id']}/review-release", headers=siap["h"], json={"note": "uji"})
    else:
        r = await klien.post(f"/api/sales-orders/{so['id']}/submit-for-approval", headers=siap["h"])
    assert r.status_code == 200, r.text
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["pay_hold"], cur.get("status")
    return cur


def _isi_lapor(siap, amount: float = 1_000_000, *, tgl: str = TGL, **lain) -> dict:
    return {"amount": amount, "transfer_date": tgl, "account_id": siap["A"], "method": "transfer",
            "reference_no": f"TRF-LB4-{next(_n)}", "note": "uji LB-4", **lain}


async def _lapor_mentah(klien, siap, oid: str, h=None, **isi):
    return await klien.post(f"/api/sales-orders/{oid}/payment-reports", headers=h or siap["h_sa"],
                            json=_isi_lapor(siap, **isi))


async def _lapor(klien, siap, oid: str, amount: float = 1_000_000, *, tgl: str = TGL, bukti: bool = True,
                 h=None, **lain) -> dict:
    r = await _lapor_mentah(klien, siap, oid, h=h, amount=amount, tgl=tgl, **lain)
    assert r.status_code == 200, r.text
    rep = r.json()
    if bukti:
        r = await klien.post(f"/api/payment-reports/{rep['id']}/attachments", headers=h or siap["h_sa"],
                             files={"file": ("bukti.pdf", PDF, "application/pdf")})
        assert r.status_code == 200, r.text
        rep["attachments"] = [r.json()]
    return rep


async def _terima(klien, siap, lid: str, h=None, key: str = ""):
    hdr = {**(h or siap["h_fin"]), **({"Idempotency-Key": key} if key else {})}
    return await klien.post(f"/api/payment-reports/{lid}/terima", headers=hdr)


async def _tolak(klien, siap, lid: str, reason: str = "Bukti transfer tidak terbaca", h=None):
    return await klien.post(f"/api/payment-reports/{lid}/tolak", headers=h or siap["h_fin"], json={"reason": reason})


async def _kwitansi(db, lid: str) -> list:
    return await db.ar_receipts.find({"payment_report_id": lid}, {"_id": 0}).to_list(10)


async def _laporan(db, lid: str) -> dict:
    return await db.payment_reports.find_one({"id": lid}, {"_id": 0})


async def _jurnal_kas(db, receipt_id: str) -> list:
    kas = await db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": receipt_id,
                                           "status": {"$ne": "void"}}, {"_id": 0}).to_list(5)
    assert len(kas) == 1, kas
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas[0]["id"],
                                            "status": {"$ne": "void"}}, {"_id": 0})
    assert je, "jurnal kas kwitansi tidak ada"
    return [(b["account_code"], round(b.get("debit", 0), 2), round(b.get("credit", 0), 2)) for b in je["lines"]]


async def _tugas_keluar(db, oid: str) -> int:
    return await db.wms_tasks.count_documents({"order_id": oid, "flow_type": "outbound"})


async def _notif(db, jenis: str, lid: str) -> list:
    return await db.notifications.find({"type": jenis, "ref": {"$regex": f"^{lid}"}}, {"_id": 0}).to_list(20)


# ── Terima ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_terima_menerbitkan_kwitansi_uang_muka_dan_melepas(klien, db, siap):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    att = rep["attachments"][0]["id"]
    r = await _terima(klien, siap, rep["id"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j) >= {"report", "receipt_number", "released", "waiting_bank"}
    assert j["released"] is True and j["waiting_bank"] is False
    assert j["report"]["status"] == "diterima" and j["report"]["receipt_number"] == j["receipt_number"]
    assert "claim" not in j["report"]
    [kw] = await _kwitansi(db, rep["id"])
    assert kw["number"] == j["receipt_number"] and kw["id"] == j["report"]["receipt_id"]
    assert (kw["amount"], kw["method"], kw["account_id"]) == (1_000_000, "transfer", siap["A"])
    assert kw["receipt_date"] == TGL and kw["entity_id"] == KSC and kw["customer_id"] == siap["cus"]
    assert kw["proof_url"] == f"/api/payment-reports/{rep['id']}/attachments/{att}"
    assert kw["reference_no"] == rep["reference_no"]
    assert [(a["order_id"], a["applied"]) for a in kw["allocations"]] == [(so["id"], 1_000_000)]
    assert kw["source"] == "payment_report" and kw["payment_report_number"] == rep["number"]
    assert kw["unapplied_amount"] == 0 and kw["variance"]["needs_decision"] is False   # pas: tanpa selisih/titipan
    assert kw["bank_verified"] is False                     # §7-5 — terima ≠ cocok mutasi bank
    assert kw["status"] == "posted" and kw["effects_done"] is True and kw["created_by"] == siap["fin"]["id"]
    # jurnal kwitansi biasa: Dr Bank / Cr Uang Muka Pelanggan sebesar nominal (pesanan belum dikirim)
    baris = await _jurnal_kas(db, kw["id"])
    assert ("1-1100", 1_000_000, 0) in baris and ("2-1400", 0, 1_000_000) in baris, baris
    assert round(sum(d for _, d, _ in baris), 2) == round(sum(c for _, _, c in baris), 2) == 1_000_000
    # pesanan lepas ke gudang (Admin Sales sudah "Periksa & lepas")
    cur = await _so(db, so["id"])
    assert cur["status"] == "confirmed" and "pay_hold" not in cur
    assert cur["paid_total"] == 1_000_000 and await _tugas_keluar(db, so["id"]) >= 1
    # laporan: keputusan + riwayat
    lap = await _laporan(db, rep["id"])
    assert lap["status"] == "diterima" and lap["decided_by"] == siap["fin"]["id"] and lap["decided_at"]
    assert lap["status_history"][-1]["status"] == "diterima" and lap["status_history"][-1]["user"]
    assert "claim" not in lap
    # notifikasi ke pelapor (Admin Sales) + sales pemilik, per orang
    penerima = {n["recipient_user"] for n in await _notif(db, "lapor_bayar_diterima", rep["id"])}
    assert penerima == {siap["sa"]["id"], siap["sales"]["id"]}
    assert await db.audit_logs.count_documents({"action": "payment_report_accepted", "entity_id": rep["id"]}) == 1


async def test_terima_sebagian_dp_tetap_tertahan_bila_kurang(klien, db, siap):
    so = await _pesan(klien, db, siap, term="DP50")
    assert so["pay_hold"]["required"] == 500_000
    rep = await _lapor(klien, siap, so["id"], 300_000)
    r = await _terima(klien, siap, rep["id"])
    assert r.status_code == 200, r.text
    assert (r.json()["released"], r.json()["waiting_bank"]) == (False, False)
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["pay_hold"] and cur["paid_total"] == 300_000
    assert await _tugas_keluar(db, so["id"]) == 0
    rep2 = await _lapor(klien, siap, so["id"], 200_000)
    r = await _terima(klien, siap, rep2["id"])
    assert r.status_code == 200, r.text
    assert r.json()["released"] is True
    cur = await _so(db, so["id"])
    assert cur["status"] == "confirmed" and "pay_hold" not in cur and cur["paid_total"] == 500_000


async def test_terima_dua_kali_satu_kwitansi(klien, db, siap):
    """Review Focus 1 — terima diulang (tanpa kunci / kunci sama sesudah jaringan putus): tepat satu kwitansi."""
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    key = _id("idem")
    a = await _terima(klien, siap, rep["id"], key=key)
    assert a.status_code == 200, a.text
    b = await _terima(klien, siap, rep["id"], key=key)          # kirim ulang kunci sama = jawaban diputar
    assert b.status_code == 200 and b.headers.get("X-Idempotent-Replay") == "true", b.text
    assert b.json()["receipt_number"] == a.json()["receipt_number"]
    c = await _terima(klien, siap, rep["id"])                    # niat baru (tanpa kunci)
    assert c.status_code == 409, c.text
    assert "diterima" in str(c.json()["detail"])
    assert len(await _kwitansi(db, rep["id"])) == 1
    assert await db.ar_receipts.count_documents({"customer_id": siap["cus"], "allocations.order_id": so["id"]}) == 1


async def test_terima_bersamaan_satu_kwitansi(klien, db, siap, monkeypatch):
    """Review Focus 1 — dua Finance menekan Terima bersamaan (keduanya membaca laporan `menunggu`): satu kwitansi,
    yang kalah 409; laporan tidak tertinggal `memproses`."""
    from services import ar_receipt_service as ars
    from services import payment_report_service as prs
    asli = ars.create_receipt

    async def _lambat(*a, **kw):
        await asyncio.sleep(0.05)   # yang pertama masih di tengah kwitansi saat yang kedua mengklaim
        return await asli(*a, **kw)
    monkeypatch.setattr(ars, "create_receipt", _lambat)
    # lewat HTTP
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"])
    hasil = await asyncio.gather(_terima(klien, siap, rep["id"]), _terima(klien, siap, rep["id"]))
    assert sorted(h.status_code for h in hasil) == [200, 409], [h.text for h in hasil]
    assert len(await _kwitansi(db, rep["id"])) == 1
    assert (await _laporan(db, rep["id"]))["status"] == "diterima"
    # lewat layanan dengan potret basi yang sama (keduanya lolos pemeriksaan awal; klaim memutus)
    so2 = await _pesan(klien, db, siap)
    rep2 = await _lapor(klien, siap, so2["id"])
    potret, order = await _laporan(db, rep2["id"]), await _so(db, so2["id"])
    aktor = {"id": siap["fin"]["id"], "name": siap["fin"]["name"], "role": "finance"}
    hasil = await asyncio.gather(prs.terima(dict(potret), dict(order), aktor), prs.terima(dict(potret), dict(order), aktor),
                                 return_exceptions=True)
    ok = [h for h in hasil if isinstance(h, dict)]
    galat = [h for h in hasil if not isinstance(h, dict)]
    assert len(ok) == 1 and len(galat) == 1, hasil
    assert getattr(galat[0], "status_code", None) == 409
    assert len(await _kwitansi(db, rep2["id"])) == 1


async def test_terima_gagal_kembali_menunggu(klien, db, siap):
    """Review Focus 2 — periode tanggal transfer tertutup: kwitansi ditolak, laporan kembali `menunggu`, tanpa kwitansi
    maupun kas, galat (409, pesan periode) sampai ke layar; sesudah periode dibuka Terima berhasil."""
    from pembantu import tutup_periode
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap, tgl="2026-09-15")
    tutup = await tutup_periode(KSC, "2026-09")
    try:
        kas_awal = await db.cash_transactions.count_documents({})
        r = await _terima(klien, siap, rep["id"], key=_id("idem"))
        assert r.status_code == 409, r.text
        assert "periode" in str(r.json()["detail"]).lower()
        assert r.headers.get("x-idempotency-retry") == "true"   # keadaan sementara: kirim ulang kunci sama dijalankan
        lap = await _laporan(db, rep["id"])
        assert lap["status"] == "menunggu" and "claim" not in lap
        assert lap["status_history"][-1]["status"] == "menunggu" and "gagal" in lap["status_history"][-1]["note"]
        assert await _kwitansi(db, rep["id"]) == []
        assert await db.cash_transactions.count_documents({}) == kas_awal
        cur = await _so(db, so["id"])
        assert not cur.get("payments") and cur["pay_hold"] and cur["status"] == "approved"
    finally:
        await db.period_closings.delete_one({"id": tutup["id"]})
    r = await _terima(klien, siap, rep["id"])
    assert r.status_code == 200, r.text
    assert len(await _kwitansi(db, rep["id"])) == 1


async def _pesanan_tertahan_dengan_laporan(klien, db, siap, **lain):
    so = await _pesan(klien, db, siap)
    return so, await _lapor(klien, siap, so["id"], **lain)


async def test_rekening_nonaktif_kembali_menunggu(klien, db, siap):
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    await db.bank_accounts.update_one({"id": siap["A"]}, {"$set": {"is_active": False}})
    try:
        r = await _terima(klien, siap, rep["id"])
        assert r.status_code == 409 and "Rekening" in r.json()["detail"], r.text   # PK-20, pesan utuh
        assert (await _laporan(db, rep["id"]))["status"] == "menunggu"
        assert await _kwitansi(db, rep["id"]) == []
    finally:
        await db.bank_accounts.update_one({"id": siap["A"]}, {"$set": {"is_active": True}})


async def test_terima_gagal_di_tengah_tanpa_kwitansi_setengah(klien, db, siap, monkeypatch):
    """Review Focus 2 — galat SESUDAH kwitansi tersisip (kas gagal dibuat): kwitansi dicabut seluruhnya (pola rollback
    `create_receipt`), laporan kembali `menunggu`, galat diteruskan."""
    from services import cash_ledger
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)

    async def _rusak(*a, **kw):
        raise RuntimeError("uji: kas mati di tengah")
    monkeypatch.setattr(cash_ledger, "create_cash", _rusak)
    r = await _terima(klien, siap, rep["id"])
    assert r.status_code == 500, r.text
    monkeypatch.undo()
    assert (await _laporan(db, rep["id"]))["status"] == "menunggu"
    assert await _kwitansi(db, rep["id"]) == []
    assert await db.ar_receipt_failures.count_documents({"payment_report_id": rep["id"]}) == 1
    cur = await _so(db, so["id"])
    assert [p for p in cur.get("payments") or [] if float(p.get("amount") or 0)] == []
    assert cur["status"] == "approved" and cur["pay_hold"]


async def test_galat_sesudah_kwitansi_tuntas_tetap_diterima(klien, db, siap, monkeypatch):
    """Kwitansi sudah tuntas (kas + jurnal + alokasi), lalu langkah turunan melempar galat: uang sah (create_receipt
    tidak membatalkan kwitansi tuntas), jadi laporan DITERIMA dengan kwitansi itu — bukan kembali `menunggu` (yang
    akan membuat Terima berikutnya menerbitkan kwitansi kedua)."""
    from services import customer_balance_service as cbs
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    asli = cbs.refresh_safe

    async def _rusak(*a, **kw):   # hanya langkah turunan SESUDAH kwitansi tuntas yang gagal
        if await db.ar_receipts.find_one({"payment_report_id": rep["id"], "effects_done": True}):
            raise RuntimeError("uji: saldo piutang gagal dihitung")
        return await asli(*a, **kw)
    monkeypatch.setattr(cbs, "refresh_safe", _rusak)
    r = await _terima(klien, siap, rep["id"])
    monkeypatch.undo()
    assert r.status_code == 200, r.text
    [kw] = await _kwitansi(db, rep["id"])
    assert r.json()["receipt_number"] == kw["number"] and r.json()["report"]["status"] == "diterima"
    assert (await _laporan(db, rep["id"]))["receipt_id"] == kw["id"]
    assert (await _terima(klien, siap, rep["id"])).status_code == 409
    assert len(await _kwitansi(db, rep["id"])) == 1


async def test_dasar_terverifikasi_waiting_bank(klien, db, siap):
    """§7-5 — PT berdasar `terverifikasi`: kwitansi hasil Terima belum cocok mutasi bank → pesanan tetap tertahan,
    `waiting_bank = True`."""
    await resolver.set_value(DASAR, "terverifikasi", scope_type="entity", scope_id=KSC, actor="uji", reason="uji LB-4")
    try:
        so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
        r = await _terima(klien, siap, rep["id"])
        assert r.status_code == 200, r.text
        assert (r.json()["released"], r.json()["waiting_bank"]) == (False, True)
        cur = await _so(db, so["id"])
        assert cur["status"] == "approved" and cur["pay_hold"] and cur["paid_total"] == 1_000_000
        [kw] = await _kwitansi(db, rep["id"])
        assert kw["bank_verified"] is False
    finally:
        await resolver.clear_layer(DASAR, scope_type="entity", scope_id=KSC, actor="uji", reason="pulihkan uji LB-4")


async def test_terima_tanpa_lampiran_409(klien, db, siap):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"], bukti=False)
    r = await _terima(klien, siap, rep["id"])
    assert (r.status_code, r.json()["detail"]) == (409, "Lampirkan bukti bayar dulu"), r.text
    assert (await _laporan(db, rep["id"]))["status"] == "menunggu"
    assert await _kwitansi(db, rep["id"]) == []


@pytest.mark.parametrize("mati", ["cancelled", "expired"])
async def test_terima_pesanan_mati_409(klien, db, siap, mati):
    """Review Focus 3 — laporan `menunggu` milik pesanan yang sudah batal/kedaluwarsa tidak bisa diterima; tolak boleh."""
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": mati}})
    r = await _terima(klien, siap, rep["id"])
    assert (r.status_code, r.json()["detail"]) == (409, MATI), r.text
    assert (await _laporan(db, rep["id"]))["status"] == "menunggu"
    assert await _kwitansi(db, rep["id"]) == []
    r = await _tolak(klien, siap, rep["id"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ditolak"


async def test_terima_tolak_izin_dan_pt(klien, db, siap):
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    for h in (siap["h_sales"], siap["h_sa"]):               # tanpa `payment_report.decide`
        assert (await _terima(klien, siap, rep["id"], h=h)).status_code == 403
        assert (await _tolak(klien, siap, rep["id"], h=h)).status_code == 403
    assert (await _terima(klien, siap, rep["id"], h=siap["h_fin_kanda"])).status_code == 403   # Finance PT lain
    assert (await _tolak(klien, siap, rep["id"], h=siap["h_fin_kanda"])).status_code == 403
    assert (await _terima(klien, siap, "lb_tidak_ada")).status_code == 404
    assert (await _laporan(db, rep["id"]))["status"] == "menunggu"


# ── Klaim `memproses` yang tertinggal (proses mati di tengah) ────────────────────────────────────────────────────────
def _klaim(menit_lalu: int) -> dict:
    at = (datetime.now(timezone.utc) - timedelta(minutes=menit_lalu)).isoformat()
    return {"token": "klaim_lama", "by": "usr_lama", "by_name": "Finance Lama", "at": at}


async def test_klaim_baru_ditolak_klaim_basi_diambil_alih(klien, db, siap):
    from services import payment_report_service as prs
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    await db.payment_reports.update_one({"id": rep["id"]}, {"$set": {"status": "memproses", "claim": _klaim(1)}})
    r = await _terima(klien, siap, rep["id"])
    assert r.status_code == 409 and "sedang diproses" in str(r.json()["detail"]), r.text
    assert r.headers.get("x-idempotency-retry") == "true"
    assert (await _tolak(klien, siap, rep["id"])).status_code == 409   # tolak hanya dari `menunggu`
    menit = prs.KLAIM_BASI_MENIT + 1
    await db.payment_reports.update_one({"id": rep["id"]}, {"$set": {"claim": _klaim(menit)}})
    r = await _terima(klien, siap, rep["id"])
    assert r.status_code == 200, r.text
    assert len(await _kwitansi(db, rep["id"])) == 1
    assert (await _laporan(db, rep["id"]))["status"] == "diterima"


async def test_klaim_basi_dengan_kwitansi_tuntas_tidak_menggandakan(klien, db, siap):
    """Proses mati SESUDAH kwitansi tuntas dan sebelum laporan ditandai diterima: Terima ulang memakai kwitansi yang
    sudah ada (rujukan balik `payment_report_id`), tidak menerbitkan yang kedua; tahan dibuka."""
    from services import ar_receipt_service as ars
    from services import payment_report_service as prs
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    att = rep["attachments"][0]["id"]
    kw = await ars.create_receipt({
        "customer_id": siap["cus"], "entity_id": KSC, "amount": 1_000_000, "method": "transfer",
        "account_id": siap["A"], "receipt_date": TGL, "reference_no": rep["reference_no"],
        "proof_url": f"/api/payment-reports/{rep['id']}/attachments/{att}",
        "allocations": [{"order_id": so["id"], "amount": 1_000_000}],
        "payment_report_id": rep["id"], "payment_report_number": rep["number"]},
        {"id": siap["fin"]["id"], "name": siap["fin"]["name"], "role": "finance"})
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"pay_hold": so["pay_hold"],
                                                                "release.waiting": "bayar", "status": "approved"}})
    await db.payment_reports.update_one({"id": rep["id"]}, {"$set": {
        "status": "memproses", "claim": _klaim(prs.KLAIM_BASI_MENIT + 5)}})
    r = await _terima(klien, siap, rep["id"])
    assert r.status_code == 200, r.text
    assert r.json()["receipt_number"] == kw["number"]
    assert [k["id"] for k in await _kwitansi(db, rep["id"])] == [kw["id"]]
    lap = await _laporan(db, rep["id"])
    assert lap["status"] == "diterima" and lap["receipt_id"] == kw["id"]


async def test_klaim_basi_kwitansi_setengah_jadi_409(klien, db, siap):
    from services import payment_report_service as prs
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    await db.ar_receipts.insert_one({"id": _id("arc"), "number": "AR-SETENGAH", "payment_report_id": rep["id"],
                                     "status": "posted", "effects_done": False, "customer_id": siap["cus"],
                                     "entity_id": KSC, "amount": 1_000_000, "created_at": now_iso()})
    await db.payment_reports.update_one({"id": rep["id"]}, {"$set": {
        "status": "memproses", "claim": _klaim(prs.KLAIM_BASI_MENIT + 5)}})
    r = await _terima(klien, siap, rep["id"])
    assert r.status_code == 409 and "AR-SETENGAH" in str(r.json()["detail"]), r.text
    assert r.headers.get("x-idempotency-retry") == "true"      # Minor-3 — keadaan sementara
    assert len(await _kwitansi(db, rep["id"])) == 1
    assert (await _laporan(db, rep["id"]))["status"] == "memproses"


# ── Tolak ────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_tolak_tanpa_uang(klien, db, siap):
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    kas_awal = await db.cash_transactions.count_documents({})
    kw_awal = await db.ar_receipts.count_documents({})
    alasan = "Nominal di bukti berbeda dengan laporan"
    r = await _tolak(klien, siap, rep["id"], alasan)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "ditolak" and j["reason"] == alasan and j["decided_by"] == siap["fin"]["id"]
    assert j["status_history"][-1]["status"] == "ditolak" and alasan in j["status_history"][-1]["note"]
    assert (await db.cash_transactions.count_documents({}), await db.ar_receipts.count_documents({})) == (kas_awal, kw_awal)
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["pay_hold"] and not cur.get("payments")
    notif = await _notif(db, "lapor_bayar_ditolak", rep["id"])
    assert {n["recipient_user"] for n in notif} == {siap["sa"]["id"], siap["sales"]["id"]}
    assert all(alasan in n["body"] for n in notif)
    assert await db.audit_logs.count_documents({"action": "payment_report_rejected", "entity_id": rep["id"]}) == 1
    # sudah diputus: terima/tolak lagi 409; sales boleh lapor ulang (nominal & tanggal sama)
    assert (await _terima(klien, siap, rep["id"])).status_code == 409
    assert (await _tolak(klien, siap, rep["id"])).status_code == 409
    ulang = await _lapor(klien, siap, so["id"])
    assert ulang["status"] == "menunggu"


async def test_tolak_alasan_pendek_400(klien, db, siap):
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    for alasan in ("", "abc", "    a  "):
        r = await _tolak(klien, siap, rep["id"], alasan)
        assert r.status_code == 400, r.text
    assert (await _laporan(db, rep["id"]))["status"] == "menunggu"


# ── B3 — kwitansi transfer sales ke pesanan tertahan ─────────────────────────────────────────────────────────────────
def _kw(siap, oid, nominal, method="transfer", account=None, **lain) -> dict:
    return {"customer_id": siap["cus"], "entity_id": KSC, "amount": nominal, "method": method,
            "account_id": account or siap["A"], "reference_no": f"TRF-LB4-{next(_n)}",
            "allocations": [{"order_id": oid, "amount": nominal}] if oid else [], **lain}


async def test_sales_kwitansi_transfer_ke_pesanan_tertahan_409(klien, db, siap):
    so = await _pesan(klien, db, siap)
    n = await db.ar_receipts.count_documents({})
    r = await klien.post("/api/ar-receipts", headers=siap["h_sales"], json=_kw(siap, so["id"], 1_000_000))
    assert (r.status_code, r.json()["detail"]) == (409, B3), r.text
    # tanpa alokasi eksplisit: rencana FIFO menunjuk pesanan tertahan yang sama
    r = await klien.post("/api/ar-receipts", headers=siap["h_sales"], json=_kw(siap, None, 1_000_000))
    assert (r.status_code, r.json()["detail"]) == (409, B3), r.text
    assert await db.ar_receipts.count_documents({}) == n
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["pay_hold"] and not cur.get("payments")


async def test_sales_tunai_dan_finance_transfer_tetap_boleh(klien, db, siap):
    # tunai sales tetap mengikuti `pembayaran.sales_terima_tunai` (bawaan kas langsung)
    so = await _pesan(klien, db, siap)
    r = await klien.post("/api/ar-receipts", headers=siap["h_sales"],
                         json=_kw(siap, so["id"], 400_000, method="cash", account=siap["K"],
                                  mismatch_note="Pelanggan bayar tunai ke sales"))
    assert r.status_code == 200, r.text
    assert r.json().get("released_order_ids") == []            # sebagian: tetap tertahan
    assert (await _so(db, so["id"]))["pay_hold"]
    # kwitansi transfer Finance langsung (bukan lewat Terima) tetap bebas — dan ikut membuka tahan (R5)
    r = await klien.post("/api/ar-receipts", headers=siap["h_fin"], json=_kw(siap, so["id"], 600_000))
    assert r.status_code == 200, r.text
    assert r.json()["released_order_ids"] == [so["id"]]
    cur = await _so(db, so["id"])
    assert cur["status"] == "confirmed" and "pay_hold" not in cur and await _tugas_keluar(db, so["id"]) >= 1


async def test_sales_transfer_pesanan_tanpa_tahan_tetap_boleh(klien, db, siap):
    """Pesanan tanpa tahan bayar (NET30 yang sudah dilepas): kwitansi transfer sales tetap boleh (perilaku lama)."""
    oid = _id("so")
    await db.sales_orders.insert_one({"id": oid, "number": "SO-LB4-NET", "entity_id": KSC, "status": "confirmed",
                                      "customer_id": siap["cus"], "customer_name": "Toko LB-4",
                                      "payment_term_code": "NET30", "grand_total": 500_000.0, "paid_total": 0,
                                      "payments": [], "items": [], "created_at": now_iso()})
    r = await klien.post("/api/ar-receipts", headers=siap["h_sales"], json=_kw(siap, oid, 500_000))
    assert r.status_code == 200, r.text
    assert r.json()["released_order_ids"] == []


async def test_buka_tahan_gagal_tidak_membatalkan_kwitansi(klien, db, siap, monkeypatch):
    """R5 — pembukaan tahan sesudah kwitansi adalah efek samping: galatnya dicatat, kwitansi tetap sah."""
    from services import pay_hold_service as phs
    so = await _pesan(klien, db, siap)

    async def _rusak(*a, **kw):
        raise RuntimeError("uji: buka tahan gagal")
    monkeypatch.setattr(phs, "clear_if_paid", _rusak)
    r = await klien.post("/api/ar-receipts", headers=siap["h_fin"], json=_kw(siap, so["id"], 1_000_000))
    assert r.status_code == 200, r.text
    assert r.json()["released_order_ids"] == [] and r.json()["effects_done"] is True
    monkeypatch.undo()
    cur = await _so(db, so["id"])
    assert cur["paid_total"] == 1_000_000 and cur["pay_hold"] and cur["status"] == "approved"
    assert await phs.clear_if_paid(so["id"]) is True           # pemanggil berikutnya membuka & melepas


# ── Antrean Meja Keuangan `lapor_bayar` (R2: baris server minimal; layar menyusul) ─────────────────────────────────
async def test_antrean_meja_keuangan_lapor_bayar(klien, db, siap, akun, sesi):
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    r = await klien.get("/api/finance/desk", headers=siap["h_fin"])
    assert r.status_code == 200, r.text
    q = next(q for q in r.json()["queues"] if q["id"] == "lapor_bayar")
    baris = next(b for b in q["rows"] if b["ref_id"] == rep["id"])
    assert (baris["ref_type"], baris["action_kind"], baris["value"]) == ("payment_report", "decide_payment_report",
                                                                       1_000_000)
    assert baris["order_id"] == so["id"] and baris["order_number"] == so["number"] and baris["amount"] == 1_000_000
    assert baris["attachments_count"] == 1 and baris["account_label"] == "BCA Penerimaan LB4"
    assert baris["transfer_date"] == TGL and baris["reported_by_name"] == siap["sa"]["name"]
    assert baris["entity_id"] == KSC
    # Finance PT lain tidak melihat laporan PT ini
    r = await klien.get("/api/finance/desk", headers=siap["h_fin_kanda"])
    assert r.status_code == 200, r.text
    q = next((q for q in r.json()["queues"] if q["id"] == "lapor_bayar"), {"rows": []})
    assert all(b["ref_id"] != rep["id"] for b in q["rows"])
    # diputus → keluar dari antrean
    assert (await _tolak(klien, siap, rep["id"])).status_code == 200
    q = next(q for q in (await klien.get("/api/finance/desk", headers=siap["h_fin"])).json()["queues"]
             if q["id"] == "lapor_bayar")
    assert all(b["ref_id"] != rep["id"] for b in q["rows"])


async def test_antrean_lapor_bayar_hanya_pemegang_decide(klien, db, siap, akun, sesi, peran_tanpa_acuan):
    """Antrean bergerbang izin `payment_report.decide` (bukan nama peran): pemegang meja Finance tanpa izin itu tidak
    mendapat antreannya."""
    await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    peran = await peran_tanpa_acuan({"payment_variance": ["decide"]}, label="Meja Finance tanpa lapor bayar")
    r = await klien.get("/api/finance/desk", headers=await sesi(await akun(peran)))
    assert r.status_code == 200, r.text
    assert "lapor_bayar" not in {q["id"] for q in r.json()["queues"]}


def test_pintu_terdaftar_di_penjaga_antrean():
    """Pintu `terima`/`tolak` ber-antrean Meja Keuangan `lapor_bayar` (penjaga INV-APPR-01)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "guardrails"))
    import verify_approval_queues as vaq
    for aksi in ("terima", "tolak"):
        pintu = f"payment_reports.py::/api/payment-reports/{{report_id}}/{aksi}"
        assert pintu in vaq.doors_from_code()
        assert vaq.DOOR_DESK_QUEUE[pintu] == "lapor_bayar"
    assert "lapor_bayar" in vaq.desk_queue_keys()


# ── Putaran perbaikan 1 (ketetapan R10) ──────────────────────────────────────────────────────────────────────────────
PESAN_BEDA = "Rekening penerima berbeda dari instruksi bayar pesanan. Isi catatan alasannya."
WAJIB_REF = "payment.wajib_nomor_referensi"


def _aktor_fin(siap) -> dict:
    return {"id": siap["fin"]["id"], "name": siap["fin"]["name"], "role": "finance"}


async def test_R10a_rekening_beda_instruksi_wajib_alasan_lalu_terima(klien, db, siap):
    """Pelanggan transfer ke rekening penerimaan PT yang lain (B) dari instruksi pesanan (A): pelapor wajib menulis
    alasannya (B7 tetap boleh memilih rekening); alasan ikut ke kwitansi sehingga Terima tidak buntu."""
    so = await _pesan(klien, db, siap)
    assert so["receiving_account_id"] == siap["A"]
    r = await _lapor_mentah(klien, siap, so["id"], account_id=siap["B"])
    assert (r.status_code, r.json()["detail"]) == (400, PESAN_BEDA), r.text
    r = await _lapor_mentah(klien, siap, so["id"], account_id=siap["B"], mismatch_note="ok")   # < 5 huruf
    assert r.status_code == 400, r.text
    alasan = "Pelanggan biasa transfer ke Mandiri"
    rep = await _lapor(klien, siap, so["id"], account_id=siap["B"], mismatch_note=alasan)
    assert rep["instruction_mismatch"] is True and rep["mismatch_note"] == alasan
    r = await _terima(klien, siap, rep["id"])
    assert r.status_code == 200, r.text
    [kw] = await _kwitansi(db, rep["id"])
    assert kw["account_id"] == siap["B"] and kw["instruction_mismatch"] is True and kw["mismatch_note"] == alasan
    assert [m["order_id"] for m in kw["instruction_mismatch_orders"]] == [so["id"]]
    # rekening sama dengan instruksi: tanpa alasan, tanpa tanda
    so2 = await _pesan(klien, db, siap)
    rep2 = await _lapor(klien, siap, so2["id"])
    assert rep2["instruction_mismatch"] is False and rep2["mismatch_note"] == ""


async def test_R10a_referensi_wajib_saat_lapor_dan_cadangan_saat_terima(klien, db, siap):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"], reference_no="")          # pengaturan PT mati: boleh tanpa referensi
    await resolver.set_value(WAJIB_REF, True, scope_type="entity", scope_id=KSC, actor="uji", reason="uji LB-4")
    try:
        r = await _lapor_mentah(klien, siap, so["id"], reference_no="", amount=500_000)
        assert (r.status_code, r.json()["detail"]) == (400, "Nomor referensi wajib diisi untuk Transfer bank."), r.text
        # pengaturan menyala sesudah laporan dibuat: pemeriksa yang sama di `create_receipt` menjadi cadangan
        r = await _terima(klien, siap, rep["id"])
        assert (r.status_code, r.json()["detail"]) == (400, "Nomor referensi wajib diisi untuk Transfer bank."), r.text
        assert (await _laporan(db, rep["id"]))["status"] == "menunggu" and await _kwitansi(db, rep["id"]) == []
        assert (await _lapor_mentah(klien, siap, so["id"], amount=500_000)).status_code == 200   # berreferensi
    finally:
        await resolver.clear_layer(WAJIB_REF, scope_type="entity", scope_id=KSC, actor="uji", reason="pulihkan uji")


async def test_R10a_cara_bayar_berjatuh_tempo_tidak_lewat_lapor_bayar(klien, db, siap):
    so = await _pesan(klien, db, siap)
    r = await _lapor_mentah(klien, siap, so["id"], method="giro")
    assert r.status_code == 400 and "berjatuh tempo" in r.json()["detail"], r.text
    assert await db.payment_reports.count_documents({"order_id": so["id"]}) == 0


async def test_R10b_nominal_melebihi_sisa_ditolak_saat_lapor_dan_sebelum_klaim(klien, db, siap):
    so = await _pesan(klien, db, siap)
    r = await _lapor_mentah(klien, siap, so["id"], amount=1_200_000)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == ("Nominal melebihi sisa tagihan pesanan (Rp 1.000.000). Kelebihan bayar dicatat "
                                  "Finance lewat kwitansi + keputusan selisih.")
    rep = await _lapor(klien, siap, so["id"])                           # pas = boleh
    r = await klien.post("/api/ar-receipts", headers=siap["h_fin"], json=_kw(siap, so["id"], 300_000))
    assert r.status_code == 200, r.text                                 # Finance mencatat sebagian lebih dulu
    r = await _terima(klien, siap, rep["id"])
    assert r.status_code == 409 and "(Rp 700.000)" in r.json()["detail"], r.text
    lap = await _laporan(db, rep["id"])
    assert lap["status"] == "menunggu" and "claim" not in lap and len(lap["status_history"]) == 1   # tanpa klaim
    assert await _kwitansi(db, rep["id"]) == []


async def test_R10c_klaim_disalip_pekerja_hidup_tetap_satu_kwitansi(klien, db, siap, monkeypatch):
    """Pekerja pertama (W1) macet SEBELUM menyisip kwitansi, klaimnya basi dan diambil alih W2 yang menyelesaikan
    laporan; W1 lalu bangun. Indeks unik `ar_receipts.uq_payment_report` (ditiru di sini — mongomock tidak menegakkan
    indeks unik parsial) membuat sisipan W1 gagal → rollback `create_receipt` → tepat satu kwitansi, kas, dan jurnal."""
    import indexes
    import mongomock.collection as _mc
    from pymongo.errors import DuplicateKeyError
    from services import ar_receipt_service as ars
    from services import payment_report_service as prs
    it = next(i for i in indexes.REQUIRED_UNIQUE_INDEXES if i["name"] == "uq_payment_report")
    assert (it["collection"], it["keys"], it["partial"]) == ("ar_receipts", [("payment_report_id", 1)],
                                                             {"payment_report_id": {"$exists": True}})
    asli_sisip = _mc.Collection.insert_one

    def _sisip_unik(self, doc, *a, **kw):   # tiruan indeks unik parsial
        if self.name == "ar_receipts" and doc.get("payment_report_id") and \
                self.find_one({"payment_report_id": doc["payment_report_id"]}):
            raise DuplicateKeyError("E11000 duplicate key uq_payment_report (uji)", 11000,
                                    {"keyPattern": {"payment_report_id": 1}, "keyValue": {}})
        return asli_sisip(self, doc, *a, **kw)
    monkeypatch.setattr(_mc.Collection, "insert_one", _sisip_unik)
    so = await _pesan(klien, db, siap, term="DP50")                     # sebagian: CAS alokasi tidak menolak W1
    rep = await _lapor(klien, siap, so["id"], 300_000)
    bangun, macet = asyncio.Event(), asyncio.Event()
    asli_efek = ars._create_receipt_after_reserve
    pertama = {"n": 0}

    async def _efek(*a, **kw):
        pertama["n"] += 1
        if pertama["n"] == 1:
            macet.set()
            await bangun.wait()      # W1 macet sesudah nomor & reservasi, sebelum alokasi + sisip kwitansi
        return await asli_efek(*a, **kw)
    monkeypatch.setattr(ars, "_create_receipt_after_reserve", _efek)
    w1 = asyncio.create_task(prs.terima(await _laporan(db, rep["id"]), await _so(db, so["id"]), _aktor_fin(siap)))
    await asyncio.wait_for(macet.wait(), 10)
    await db.payment_reports.update_one({"id": rep["id"]}, {"$set": {"claim.at": _klaim(prs.KLAIM_BASI_MENIT + 1)["at"]}})
    w2 = await prs.terima(await _laporan(db, rep["id"]), await _so(db, so["id"]), _aktor_fin(siap))   # ambil alih
    assert w2["report"]["status"] == "diterima"
    bangun.set()
    with pytest.raises(Exception) as e:
        await asyncio.wait_for(w1, 10)
    assert getattr(e.value, "status_code", None) == 409, e.value      # W1 tidak melaporkan sukses
    kws = await _kwitansi(db, rep["id"])
    assert [k["number"] for k in kws] == [w2["receipt_number"]]
    kas = await db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": {"$in": [k["id"] for k in kws]},
                                           "status": {"$ne": "void"}}, {"_id": 0, "id": 1}).to_list(5)
    assert len(kas) == 1
    assert await db.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": kas[0]["id"],
                                                     "status": {"$ne": "void"}}) == 1
    cur = await _so(db, so["id"])
    assert round(sum(float(p.get("amount") or 0) for p in cur.get("payments") or []), 2) == 300_000
    assert (await _laporan(db, rep["id"]))["receipt_id"] == kws[0]["id"]


def _lebih(siap, x_id: str, y_id: str, *, x_nominal: float, y_nominal: float) -> dict:
    """Kwitansi transfer ke pesanan X yang lebih bayar; kelebihannya diputus "alokasikan" ke pesanan Y."""
    return {**_kw(siap, x_id, x_nominal + y_nominal), "allocations": [{"order_id": x_id, "amount": x_nominal}],
            "variance": {"kind": "allocate", "reason_code": "customer_overtransfer", "note": "uji LB-4",
                         "allocations": [{"order_id": y_id, "amount": y_nominal}]}}


async def _pesanan_bebas(db, siap, nominal: float = 500_000) -> dict:
    so = {"id": _id("so"), "number": f"SO-LB4-X{next(_n)}", "entity_id": KSC, "status": "confirmed",
          "customer_id": siap["cus"], "customer_name": "Toko LB-4", "payment_term_code": "NET30",
          "grand_total": nominal, "paid_total": 0, "payments": [], "items": [], "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    return so


async def test_R10d_b3_menilai_tujuan_keputusan_selisih_alokasi(klien, db, siap):
    x = await _pesanan_bebas(db, siap)
    y = await _pesan(klien, db, siap)
    n = await db.ar_receipts.count_documents({})
    r = await klien.post("/api/ar-receipts", headers=siap["h_sales"],
                         json=_lebih(siap, x["id"], y["id"], x_nominal=500_000, y_nominal=1_000_000))
    assert (r.status_code, r.json()["detail"]) == (409, B3), r.text
    assert await db.ar_receipts.count_documents({}) == n


async def test_R10d_keputusan_selisih_alokasi_membuka_tahan(klien, db, siap):
    x = await _pesanan_bebas(db, siap)
    y = await _pesan(klien, db, siap)                                   # sudah "Periksa & lepas"
    r = await klien.post("/api/ar-receipts", headers=siap["h_fin"],
                         json=_lebih(siap, x["id"], y["id"], x_nominal=500_000, y_nominal=1_000_000))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["variance_decision"]["kind"] == "allocate" and j["variance_decision"]["status"] == "done", j
    assert j["released_order_ids"] == [y["id"]]
    cur = await _so(db, y["id"])
    assert cur["status"] == "confirmed" and "pay_hold" not in cur and await _tugas_keluar(db, y["id"]) >= 1


async def test_R10d_kwitansi_deposit_saja_tidak_dihalangi_b3(klien, db, siap):
    y = await _pesan(klien, db, siap)
    await db.customers.update_one({"id": siap["cus"]}, {"$set": {"deposit_balance": 1_000_000.0}})   # FIXTURE titipan
    r = await klien.post("/api/ar-receipts", headers=siap["h_sales"], json={
        "customer_id": siap["cus"], "entity_id": KSC, "amount": 0, "use_deposit_amount": 1_000_000,
        "method": "transfer", "allocations": [{"order_id": y["id"], "amount": 1_000_000}]})
    assert r.status_code == 200, r.text
    assert r.json()["released_order_ids"] == [y["id"]]                  # uang sah (titipan) → tahan dibuka (R5)
    assert (await _so(db, y["id"]))["status"] == "confirmed"


async def test_R10e_cocok_mutasi_bank_membuka_tahan(klien, db, siap):
    await resolver.set_value(DASAR, "terverifikasi", scope_type="entity", scope_id=KSC, actor="uji", reason="uji LB-4")
    try:
        so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
        r = await _terima(klien, siap, rep["id"])
        assert r.status_code == 200 and r.json()["waiting_bank"] is True, r.text
        [kw] = await _kwitansi(db, rep["id"])
        kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": kw["id"]}, {"_id": 0})
        eid = _id("ext")
        r = await klien.post("/api/bank-reconciliation/import", headers=siap["h"], json={
            "bank_account_id": siap["A"], "lines": [{"stmt_date": TGL, "amount": 1_000_000, "direction": "in",
                                                    "description": "TRSF TOKO LB-4", "ref": "", "external_id": eid}]})
        assert r.status_code == 200 and r.json()["imported"] == 1, r.text
        lid = (await db.bank_statement_lines.find_one({"external_id": eid}, {"_id": 0}))["id"]
        r = await klien.post(f"/api/bank-reconciliation/lines/{lid}/match", headers=siap["h"],
                             json={"txn_id": kas["id"]})
        assert r.status_code == 200, r.text
        assert (await db.ar_receipts.find_one({"id": kw["id"]}, {"_id": 0}))["bank_verified"] is True
        cur = await _so(db, so["id"])
        assert cur["status"] == "confirmed" and "pay_hold" not in cur and await _tugas_keluar(db, so["id"]) >= 1
    finally:
        await resolver.clear_layer(DASAR, scope_type="entity", scope_id=KSC, actor="uji", reason="pulihkan uji LB-4")


class _Mati(BaseException):
    """Penghentian paksa (bukan `Exception`), mis. pembatalan tugas saat server dimatikan."""


async def test_minor1_laporan_berkwitansi_tidak_bisa_ditolak(klien, db, siap, monkeypatch):
    from services import pay_hold_service as phs
    from services import payment_report_service as prs
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)

    async def _mati(*a, **kw):
        raise _Mati()
    monkeypatch.setattr(phs, "clear_if_paid", _mati)   # sesudah kwitansi tuntas (R5)
    with pytest.raises(_Mati):
        await prs.terima(await _laporan(db, rep["id"]), await _so(db, so["id"]), _aktor_fin(siap))
    monkeypatch.undo()
    [kw] = await _kwitansi(db, rep["id"])
    assert kw["effects_done"] is True
    assert (await _laporan(db, rep["id"]))["status"] == "memproses"   # tidak kembali `menunggu`
    assert (await _tolak(klien, siap, rep["id"])).status_code == 409
    # laporan `menunggu` yang (entah bagaimana) sudah berkwitansi pun tidak bisa ditolak
    await db.payment_reports.update_one({"id": rep["id"]}, {"$set": {"status": "menunggu"}, "$unset": {"claim": ""}})
    r = await _tolak(klien, siap, rep["id"])
    assert r.status_code == 409 and kw["number"] in r.json()["detail"], r.text
    r = await _terima(klien, siap, rep["id"])                           # dipulihkan dengan kwitansi yang sama
    assert r.status_code == 200 and r.json()["receipt_number"] == kw["number"], r.text
    assert len(await _kwitansi(db, rep["id"])) == 1


@pytest.mark.parametrize("disalip", ["memproses", "diterima"])
async def test_minor2_klaim_hilang_bukan_sukses(klien, db, siap, monkeypatch, disalip):
    from services import ar_receipt_service as ars
    from services import payment_report_service as prs
    so, rep = await _pesanan_tertahan_dengan_laporan(klien, db, siap)
    asli = ars.create_receipt

    async def _disalip(*a, **kw):
        out = await asli(*a, **kw)
        upd = {"claim.token": "klaim_lain"} if disalip == "memproses" else {"status": "diterima"}
        await db.payment_reports.update_one({"id": rep["id"]}, {"$set": upd})
        return out
    monkeypatch.setattr(ars, "create_receipt", _disalip)
    r = await _terima(klien, siap, rep["id"])
    monkeypatch.undo()
    assert r.status_code == 409, r.text
    if disalip == "memproses":
        assert r.json()["detail"] == prs.PESAN_DIPROSES and r.headers.get("x-idempotency-retry") == "true"
    else:
        assert r.json()["detail"] == "Laporan ini sudah diterima."
    assert await _notif(db, "lapor_bayar_diterima", rep["id"]) == []   # pemenang yang memberi tahu
    assert await db.audit_logs.count_documents({"action": "payment_report_accepted", "entity_id": rep["id"]}) == 0
    assert len(await _kwitansi(db, rep["id"])) == 1


async def test_minor3_tanpa_bukti_kirim_ulang_kunci_sama_sesudah_lampir(klien, db, siap):
    so = await _pesan(klien, db, siap)
    rep = await _lapor(klien, siap, so["id"], bukti=False)
    key = _id("idem")
    r = await _terima(klien, siap, rep["id"], key=key)
    assert (r.status_code, r.json()["detail"]) == (409, "Lampirkan bukti bayar dulu"), r.text
    assert r.headers.get("x-idempotency-retry") == "true"
    r = await klien.post(f"/api/payment-reports/{rep['id']}/attachments", headers=siap["h_sa"],
                         files={"file": ("bukti.pdf", PDF, "application/pdf")})
    assert r.status_code == 200, r.text
    r = await _terima(klien, siap, rep["id"], key=key)                  # kunci sama: dijalankan, bukan diputar
    assert r.status_code == 200 and r.headers.get("X-Idempotent-Replay") != "true", r.text
    assert len(await _kwitansi(db, rep["id"])) == 1
