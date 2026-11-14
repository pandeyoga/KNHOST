"""PM-T2 — pesanan menyimpan cara bayar dan rekening tujuan; dokumen mencetak instruksi bayar berkode.

docs/blueprint/unit/PM-T2.md, uji penerimaan U1–U14 (lingkungan B) + tambahan. U15 (200 kode cepat, tabrakan di MongoDB
asli) ditulis di `backend/tests/test_bp_PMT2_kode_bayar.py` (lapis A); di sini versi tiruannya (tabrakan dipaksa lewat
pembangkit acak). U16 = uji jalan layar.

Persiapan (alur lewat API): rekening A (`ent_ksc`, BCA 123-456-7890 a.n. PT Kain Suka Cita, penerimaan pelanggan,
melayani transfer, bawaan transfer, tampil di dokumen), B (`ent_kanda`, serupa), C (`ent_ksc`, hanya untuk gaji), D
(`ent_ksc`, penerimaan pelanggan transfer, bukan bawaan). Pelanggan, produk, gudang, dan roll = fixture (disisipkan
langsung). Pesanan, verifikasi, persetujuan, konfirmasi, override, render dokumen, dan pengaturan = alur lewat API.
Kode `KN-7F3K2` pada U9 = fixture (kode hasil U6 ditimpa supaya teks bisa dibandingkan persis).

Hitung tangan (PT `ent_ksc` PKP; pesanan U6/U7 memakai "tanpa PPN" supaya total = harga × jumlah):
  U6  100 m × Rp 20.000 = Rp 2.000.000 · termin CBD (tunai, DP 100 %) → kode Rp 2.000.000 × 100 % = Rp 2.000.000
  U7  100 m × Rp 20.000 = Rp 2.000.000 · termin DP50 (DP 50 %)       → kode Rp 2.000.000 × 50 % = Rp 1.000.000
  baris  DP50 Rp 2.000.000: DP Rp 1.000.000 (pakai ulang kode pesanan) + pelunasan Rp 1.000.000 jatuh tempo
         2026-12-15 → kode baru Rp 1.000.000, label tanggal "15 Des 2026"
"""
from __future__ import annotations

import importlib.util
import itertools
import re
import uuid
from pathlib import Path

import pytest

from core_utils import now_iso
from services import config_resolver as resolver

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
REPO = Path(__file__).resolve().parents[2]
WAJIB = "payment.wajib_cara_bayar_di_pesanan"
AWALAN = "payment.kode_bayar_awalan"
PESAN_WAJIB = "Pilih cara bayar untuk pesanan ini."
PESAN_PT_LAIN = "Rekening tujuan bukan milik PT pesanan ini."
PESAN_TIDAK_MENERIMA = "Rekening ini tidak bisa menerima pembayaran pelanggan lewat Transfer bank."
RX_KODE = re.compile(r"^KN-[2-9A-HJ-NP-Z]{5}$")
TANPA_PPN = {"tax_override": "non_ppn", "tax_override_reason": "uji PM-T2 tanpa PPN"}
_n = itertools.count(1)
SIMPAN: dict = {}


def _id(awal: str) -> str:
    return f"{awal}_pmt2_{uuid.uuid4().hex[:8]}"


async def _rekening(klien, h, **isi):
    body = {"account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
            "payment_method_codes": ["transfer"], **isi}
    r = await klien.post("/api/bank-accounts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, sesi):
    h_kanda = await sesi("admin@kainnusantara.id", entitas=KANDA)
    a = await _rekening(klien, kepala_admin, name="BCA Penerimaan KSC", account_number="123-456-7890",
                        holder_name="PT Kain Suka Cita", default_receiving_methods=["transfer"],
                        show_on_documents=True, entity_id=KSC)
    b = await _rekening(klien, h_kanda, name="BCA Penerimaan Kanda", account_number="987-654-3210",
                        holder_name="CV Kanda", default_receiving_methods=["transfer"], show_on_documents=True,
                        entity_id=KANDA)
    c = await _rekening(klien, kepala_admin, name="BCA Gaji KSC", account_number="555-000-1111",
                        holder_name="PT Kain Suka Cita", purposes=["gaji"], entity_id=KSC)
    d = await _rekening(klien, kepala_admin, name="Mandiri Penerimaan KSC", bank_name="Mandiri",
                        account_number="140-00-7777", holder_name="PT Kain Suka Cita", show_on_documents=True,
                        entity_id=KSC)
    pel = {}
    for ent in (KSC, KANDA):   # fixture: pelanggan + produk + gudang per PT
        cus, adr, prd = _id("cus"), _id("adr"), _id("prd")
        await db.customers.insert_one({"id": cus, "name": f"Toko PM-T2 {ent}", "entity_id": ent, "status": "active",
                                       "addresses": [{"id": adr, "label": "Utama", "city": "Bandung",
                                                      "address": "Jl. Uji 1", "recipient_name": "Bu Uji",
                                                      "phone": "081200000000"}]})
        await db.products.insert_one({"id": prd, "sku": f"PMT2-{ent}", "name": f"Kain PM-T2 {ent}", "price": 20000,
                                      "base_unit": "meter", "status": "active", "lifecycle": "produksi",
                                      "category": "uji"})
        await db.warehouses.insert_one({"id": f"wh_pmt2_{ent}", "name": f"Gudang PM-T2 {ent}", "entity_id": ent,
                                        "city": "Bandung"})
        pel[ent] = {"cus": cus, "adr": adr, "prd": prd}
    return {"A": a, "B": b, "C": c, "D": d, "pel": pel, "h": kepala_admin, "h_kanda": h_kanda}


async def _roll(db, siap, ent=KSC) -> str:
    """Fixture: satu roll 100 m tersedia untuk produk PT itu (dipakai satu pesanan)."""
    rid = _id("roll")
    await db.inventory_rolls.insert_one({
        "id": rid, "roll_no": f"R-{next(_n)}", "product_id": siap["pel"][ent]["prd"], "owner_entity_id": ent,
        "warehouse_id": f"wh_pmt2_{ent}", "status": "available", "active_movement": None, "length_remaining": 100.0,
        "lot": "L-PMT2", "created_at": now_iso()})
    return rid


def _isi(siap, ent=KSC, *, term="NET30", stok=True, **lain):
    p = siap["pel"][ent]
    body = {"customer_id": p["cus"], "shipping_address_id": p["adr"], "entity_id": ent, "payment_term_code": term,
            "items": [{"product_id": p["prd"], "quantity": 100, "unit": "meter"}], **lain}
    if not stok:
        body["allow_backorder"] = True
    return body


async def _pesan(klien, db, siap, ent=KSC, *, h=None, stok=True, **lain):
    if stok:
        await _roll(db, siap, ent)
    return await klien.post("/api/sales-orders", headers=h or (siap["h"] if ent == KSC else siap["h_kanda"]),
                            json=_isi(siap, ent, stok=stok, **lain))


async def _konfirmasi(klien, h, oid: str) -> dict:
    """Alur: verifikasi Admin Sales → setujui → konfirmasi (lepas ke gudang)."""
    r = await klien.post(f"/api/sales-orders/{oid}/verify", headers=h, json={"note": "uji PM-T2"})
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/sales-orders/{oid}/approve", headers=h)
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/sales-orders/{oid}/confirm", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed", r.json()["status"]
    return r.json()


async def _instruksi(klien, h, oid: str):
    return await klien.get(f"/api/sales-orders/{oid}/payment-instruction", headers=h)


# ── U1–U5: field pesanan & validasi `create_order` ────────────────────────────────────────────────────────────────
async def test_PMT2_U1_pesanan_menyimpan_cara_bayar_dan_potret_rekening(klien, db, siap):
    r = await _pesan(klien, db, siap, payment_method_code="transfer", receiving_account_id=siap["A"])
    assert r.status_code == 200, r.text
    so = await db.sales_orders.find_one({"id": r.json()["id"]})
    assert so["payment_method_code"] == "transfer"
    assert so["receiving_account_id"] == siap["A"]
    assert so["receiving_account"] == {"bank_name": "BCA", "account_number": "123-456-7890",
                                       "holder_name": "PT Kain Suka Cita"}
    SIMPAN["u1"] = so["id"]


async def test_PMT2_U2_rekening_pt_lain_ditolak_tanpa_pesanan_dan_reservasi(klien, db, siap):
    sebelum = await db.sales_orders.count_documents({})
    rid = await _roll(db, siap)
    r = await klien.post("/api/sales-orders", headers=siap["h"],
                         json=_isi(siap, payment_method_code="transfer", receiving_account_id=siap["B"]))
    assert (r.status_code, r.json().get("detail")) == (400, PESAN_PT_LAIN), r.text
    assert await db.sales_orders.count_documents({}) == sebelum
    roll = await db.inventory_rolls.find_one({"id": rid})
    assert roll["status"] == "available" and not roll.get("reserved_ref"), roll
    SIMPAN["roll_bebas"] = rid


async def test_PMT2_U3_rekening_bukan_penerimaan_pelanggan_ditolak(klien, db, siap):
    sebelum = await db.sales_orders.count_documents({})
    r = await klien.post("/api/sales-orders", headers=siap["h"],
                         json=_isi(siap, stok=False, payment_method_code="transfer", receiving_account_id=siap["C"]))
    assert (r.status_code, r.json().get("detail")) == (400, PESAN_TIDAK_MENERIMA), r.text
    assert await db.sales_orders.count_documents({}) == sebelum
    # cara bayar tak dikenal / nonaktif = pesan PM-T1
    r = await klien.post("/api/sales-orders", headers=siap["h"],
                         json=_isi(siap, stok=False, payment_method_code="bitcoin"))
    assert (r.status_code, r.json().get("detail")) == (400, "Cara bayar tidak dikenal: bitcoin."), r.text
    r = await klien.post("/api/sales-orders", headers=siap["h"], json=_isi(siap, stok=False, payment_method_code="va"))
    assert (r.status_code, r.json().get("detail")) == (400, "Cara bayar Virtual account tidak aktif untuk PT ini."), \
        r.text
    assert await db.sales_orders.count_documents({}) == sebelum


async def test_PMT2_U4_rekening_bawaan_dan_tanpa_cara_bayar(klien, db, siap):
    r = await _pesan(klien, db, siap, stok=False, payment_method_code="transfer")
    assert r.status_code == 200, r.text
    so = await db.sales_orders.find_one({"id": r.json()["id"]})
    assert so["receiving_account_id"] == siap["A"]
    assert so["receiving_account"]["account_number"] == "123-456-7890"
    r = await _pesan(klien, db, siap, stok=False)
    assert r.status_code == 200, r.text
    so = await db.sales_orders.find_one({"id": r.json()["id"]})
    assert (so["payment_method_code"], so["receiving_account_id"]) == ("", "")
    # cara bayar tanpa rekening bank (tunai): rekening tidak diisi dari bawaan transfer
    r = await _pesan(klien, db, siap, stok=False, payment_method_code="tunai")
    assert r.status_code == 200, r.text
    so = await db.sales_orders.find_one({"id": r.json()["id"]})
    assert (so["payment_method_code"], so["receiving_account_id"]) == ("cash", "")


async def test_PMT2_U5_wajib_cara_bayar_per_pt(klien, db, siap):
    await resolver.set_value(WAJIB, True, scope_type="entity", scope_id=KSC, actor="uji", reason="uji PM-T2")
    try:
        sebelum = await db.sales_orders.count_documents({})
        r = await klien.post("/api/sales-orders", headers=siap["h"], json=_isi(siap, stok=False))
        assert (r.status_code, r.json().get("detail")) == (400, PESAN_WAJIB), r.text
        assert await db.sales_orders.count_documents({}) == sebelum
        r = await _pesan(klien, db, siap, KANDA, stok=False)
        assert r.status_code == 200, r.text
        assert (await db.sales_orders.find_one({"id": r.json()["id"]}))["payment_method_code"] == ""
        # PT lain tidak berubah; PT yang mewajibkan menerima pesanan bercara bayar
        assert await resolver.value_of(WAJIB, {"entity_id": KANDA}) is False
        r = await _pesan(klien, db, siap, stok=False, payment_method_code="transfer")
        assert r.status_code == 200, r.text
        # pesanan buatan sistem (konversi pesanan khusus, pengganti retur) memanggil `create_order` dari rute lain
        from starlette.requests import Request
        from routers.sales_orders import create_order
        from schemas import SalesOrderCreate
        rute_lain = Request({"type": "http", "method": "POST", "path": "/api/special-orders/od_uji/convert-to-so",
                             "raw_path": b"/api/special-orders/od_uji/convert-to-so", "query_string": b"",
                             "headers": [(k.lower().encode(), v.encode()) for k, v in siap["h"].items()],
                             "client": ("uji", 1), "server": ("uji", 80), "scheme": "http", "root_path": ""})
        so = await create_order(SalesOrderCreate(**_isi(siap, stok=False)), rute_lain)
        assert so["payment_method_code"] == "" and so["number"]
    finally:
        await resolver.clear_layer(WAJIB, scope_type="entity", scope_id=KSC, actor="uji", reason="uji PM-T2")


# ── U6–U8: kode bayar lahir saat pesanan bayar-dulu dikonfirmasi ─────────────────────────────────────────────────
async def test_PMT2_U6_konfirmasi_cbd_melahirkan_satu_kode(klien, db, siap):
    r = await _pesan(klien, db, siap, term="CBD", payment_method_code="transfer", receiving_account_id=siap["A"],
                     **TANPA_PPN)
    assert r.status_code == 200, r.text
    oid = r.json()["id"]
    assert r.json()["grand_total"] == 2_000_000
    assert await db.payment_codes.count_documents({"order_id": oid}) == 0   # belum dikonfirmasi = belum ada kode
    await _konfirmasi(klien, siap["h"], oid)
    kode = await db.payment_codes.find({"order_id": oid}, {"_id": 0}).to_list(10)
    assert len(kode) == 1, kode
    k = kode[0]
    assert k["amount"] == 2_000_000
    assert RX_KODE.match(k["code"]), k["code"]
    assert k["status"] == "aktif" and k["id"].startswith("pyc_")
    assert (k["entity_id"], k["order_number"], k["customer_id"]) == (KSC, r.json()["number"], siap["pel"][KSC]["cus"])
    assert (k["plan_id"], k["line_id"]) == ("", "")
    assert (await db.sales_orders.find_one({"id": oid}))["payment_code"] == k["code"]
    SIMPAN["u6"] = oid


async def test_PMT2_U7_konfirmasi_dp50_kode_separuh(klien, db, siap):
    r = await _pesan(klien, db, siap, term="DP50", payment_method_code="transfer", **TANPA_PPN)
    assert r.status_code == 200, r.text
    await _konfirmasi(klien, siap["h"], r.json()["id"])
    k = await db.payment_codes.find_one({"order_id": r.json()["id"]})
    assert k["amount"] == 1_000_000
    SIMPAN["u7"] = r.json()["id"]


async def test_PMT2_U8_ensure_for_order_idempoten(db, siap):
    from services import payment_code_service as pcs
    so = await db.sales_orders.find_one({"id": SIMPAN["u6"]}, {"_id": 0})
    awal = await db.payment_codes.find_one({"order_id": SIMPAN["u6"]}, {"_id": 0})
    for _ in range(2):
        again = await pcs.ensure_for_order(so)
        assert again["code"] == awal["code"]
    assert await db.payment_codes.count_documents({"order_id": SIMPAN["u6"]}) == 1


# ── U9–U11: instruksi bayar ─────────────────────────────────────────────────────────────────────────────────────
async def test_PMT2_U9_teks_instruksi_lima_baris(klien, db, siap):
    oid = SIMPAN["u6"]
    await db.payment_codes.update_one({"order_id": oid}, {"$set": {"code": "KN-7F3K2"}})   # fixture kode tetap
    await db.sales_orders.update_one({"id": oid}, {"$set": {"payment_code": "KN-7F3K2"}})
    r = await _instruksi(klien, siap["h"], oid)
    assert r.status_code == 200, r.text
    j = r.json()
    nomor = (await db.sales_orders.find_one({"id": oid}))["number"]
    assert j["text"].split("\n") == [
        f"Pembayaran untuk pesanan {nomor}",
        "Jumlah        : Rp 2.000.000",
        "Jatuh tempo   : sebelum barang dikirim",
        "Transfer ke   : BCA 123-456-7890 a.n. PT Kain Suka Cita",
        "Berita/kode   : KN-7F3K2",
    ]
    assert j["order_number"] == nomor and j["method_name"] == "Transfer bank"
    assert j["account"] == {"bank_name": "BCA", "account_number": "123-456-7890", "holder_name": "PT Kain Suka Cita"}
    assert len(j["items"]) == 1
    it = j["items"][0]
    assert (it["amount"], it["due_date"], it["due_label"], it["pay_code"]) == \
        (2_000_000, "", "sebelum barang dikirim", "KN-7F3K2")


async def _html(klien, h, jenis: str, oid: str) -> str:
    r = await klien.get(f"/api/pdf/render/{jenis}/{oid}", headers=h, params={"format": "html"})
    assert r.status_code == 200, r.text[:400]
    return r.text


async def test_PMT2_U10_blok_dokumen_mengikuti_tampil_di_dokumen(klien, db, siap):
    oid = SIMPAN["u6"]
    for jenis in ("sales_order", "invoice"):
        html = await _html(klien, siap["h"], jenis, oid)
        assert "Instruksi Pembayaran" in html and "KN-7F3K2" in html, jenis
        assert "BCA 123-456-7890 a.n. PT Kain Suka Cita" in html, jenis
    r = await klien.patch(f"/api/bank-accounts/{siap['A']}", headers=siap["h"], json={"show_on_documents": False})
    assert r.status_code == 200, r.text
    try:
        for jenis in ("sales_order", "invoice"):
            html = await _html(klien, siap["h"], jenis, oid)
            assert "Instruksi Pembayaran" not in html and "KN-7F3K2" not in html, jenis
    finally:
        r = await klien.patch(f"/api/bank-accounts/{siap['A']}", headers=siap["h"], json={"show_on_documents": True})
        assert r.status_code == 200, r.text


async def test_PMT2_U10b_bagian_dokumen_bisa_dimatikan(klien, siap):
    oid = SIMPAN["u6"]
    r = await klien.put("/api/pdf/templates/invoice", headers=siap["h"],
                        json={"config": {"sections": {"payment_instruction": False}}})
    assert r.status_code == 200, r.text
    try:
        assert "Instruksi Pembayaran" not in await _html(klien, siap["h"], "invoice", oid)
        assert "Instruksi Pembayaran" in await _html(klien, siap["h"], "sales_order", oid)   # jenis lain tetap
    finally:
        r = await klien.delete("/api/pdf/templates/invoice", headers=siap["h"])
        assert r.status_code == 200, r.text
    assert "Instruksi Pembayaran" in await _html(klien, siap["h"], "invoice", oid)


async def test_PMT2_U11_pesanan_tempo_tanpa_kode(klien, db, siap):
    r = await _pesan(klien, db, siap, term="NET30", payment_method_code="transfer", receiving_account_id=siap["A"])
    assert r.status_code == 200, r.text
    oid = r.json()["id"]
    await _konfirmasi(klien, siap["h"], oid)
    if importlib.util.find_spec("services.billing_schedule_service") is not None:
        pytest.fail("CR-T2 sudah ada: lengkapi cabang U11 (satu surat jalan → satu tagihan berkode dengan jatuh tempo "
                    "baris itu) dan kaitkan `payment_code_service.ensure_for_line` saat baris tagihan lahir")
    r = await _instruksi(klien, siap["h"], oid)
    assert r.status_code == 200, r.text
    assert r.json()["items"] == [] and r.json()["text"] == ""
    assert r.json()["note"] == "Instruksi bayar tersedia setelah barang dikirim."
    assert await db.payment_codes.count_documents({"order_id": oid}) == 0
    # pesanan bayar-dulu yang belum dikonfirmasi
    r = await _pesan(klien, db, siap, term="CBD", payment_method_code="transfer")
    r = await _instruksi(klien, siap["h"], r.json()["id"])
    assert (r.json()["items"], r.json()["note"]) == ([], "Instruksi bayar tersedia setelah pesanan dikonfirmasi.")


# ── U12: override pesanan ───────────────────────────────────────────────────────────────────────────────────────
async def test_PMT2_U12_override_rekening_tujuan(klien, db, siap):
    oid = SIMPAN["u1"]
    n_amd = await db.doc_amendments.count_documents({"doc_id": oid})
    r = await klien.post(f"/api/sales-orders/{oid}/override", headers=siap["h"],
                         json={"header": {"receiving_account_id": siap["B"]}, "note": "uji PM-T2 ganti rekening"})
    assert (r.status_code, r.json().get("detail")) == (400, PESAN_PT_LAIN), r.text
    assert (await db.sales_orders.find_one({"id": oid}))["receiving_account_id"] == siap["A"]
    r = await klien.post(f"/api/sales-orders/{oid}/override", headers=siap["h"],
                         json={"header": {"receiving_account_id": siap["D"]}, "note": "uji PM-T2 ganti rekening"})
    assert r.status_code == 200, r.text
    so = await db.sales_orders.find_one({"id": oid})
    assert so["receiving_account_id"] == siap["D"]
    assert so["receiving_account"] == {"bank_name": "Mandiri", "account_number": "140-00-7777",
                                       "holder_name": "PT Kain Suka Cita"}
    amd = await db.doc_amendments.find({"doc_id": oid}, {"_id": 0}).to_list(20)
    assert len(amd) == n_amd + 1
    ubah = [c for c in amd[-1]["changes"] if c["field"] == "receiving_account_id"]
    assert ubah and ubah[0]["label"] == "Rekening tujuan"
    assert ubah[0]["to"] == "Mandiri 140-00-7777 a.n. PT Kain Suka Cita"
    # cara bayar ikut tervalidasi: rekening gaji ditolak, cara bayar lain diterima
    r = await klien.post(f"/api/sales-orders/{oid}/override", headers=siap["h"],
                         json={"header": {"receiving_account_id": siap["C"]}, "note": "uji PM-T2 ganti rekening"})
    assert (r.status_code, r.json().get("detail")) == (400, PESAN_TIDAK_MENERIMA), r.text
    r = await klien.get(f"/api/sales-orders/{oid}/override-context", headers=siap["h"])
    assert r.status_code == 200, r.text
    ctx = r.json()
    assert "transfer" in [m["code"] for m in ctx["payment_methods"]]
    assert siap["B"] not in {x["id"] for x in ctx["receiving_accounts"]["transfer"]}
    assert {siap["A"], siap["D"]} <= {x["id"] for x in ctx["receiving_accounts"]["transfer"]}


# ── U13: izin ───────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PMT2_U13_izin_instruksi_bayar(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    oid = SIMPAN["u6"]
    rid = await peran_tanpa_acuan({"order": ["view"]}, label="Lihat Pesanan PM-T2")
    r = await _instruksi(klien, await sesi(await akun(rid)), oid)
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["pay_code"] == "KN-7F3K2"
    r = await _instruksi(klien, await sesi(await akun(await peran_manajer_kosong())), oid)
    assert r.status_code == 403, r.text
    r = await _instruksi(klien, await sesi(await akun(peran_sopir)), oid)
    assert r.status_code == 403, r.text
    # PT lain di luar penugasan
    r = await _instruksi(klien, await sesi(await akun(rid, entitas=(KANDA,)), entitas=KANDA), oid)
    assert r.status_code in (403, 404), r.text


# ── U14: dua kunci pengaturan ───────────────────────────────────────────────────────────────────────────────────
async def test_PMT2_U14_putaran_dua_kunci(klien, kepala_admin):
    from test_KFT8_putaran_pengaturan import putaran
    for kunci in (WAJIB, AWALAN):
        gagal = await putaran(klien, kepala_admin, kunci)
        assert not gagal, "\n".join(gagal)
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": AWALAN, "value": "KS", "scope_type": "entity", "scope_id": KSC, "reason": "uji PM-T2"}]})
    assert r.status_code == 400, r.text
    for buruk in ("kn", "K", "KNABC", "K1", "KN-"):
        r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
            "key": AWALAN, "value": buruk, "scope_type": "global", "scope_id": "", "reason": "uji PM-T2"}]})
        assert r.status_code == 400, (buruk, r.text)


async def test_PMT2_U14b_awalan_baru_hanya_untuk_kode_baru(klien, db, siap):
    await resolver.set_value(AWALAN, "KNS", scope_type="global", scope_id="", actor="uji", reason="uji PM-T2")
    try:
        r = await _pesan(klien, db, siap, term="CBD", payment_method_code="transfer", **TANPA_PPN)
        assert r.status_code == 200, r.text
        await _konfirmasi(klien, siap["h"], r.json()["id"])
        k = await db.payment_codes.find_one({"order_id": r.json()["id"]})
        assert re.match(r"^KNS-[2-9A-HJ-NP-Z]{5}$", k["code"]), k["code"]
        assert (await db.payment_codes.find_one({"order_id": SIMPAN["u6"]}))["code"] == "KN-7F3K2"
    finally:
        await resolver.set_value(AWALAN, "KN", scope_type="global", scope_id="", actor="uji", reason="pulihkan uji PM-T2")


# ── Tambahan: tabrakan kode (tiruan U15), pencari kode di teks, kode per baris tagihan, token rekening ───────────
async def test_PMT2_tabrakan_kode_diulang(db, siap, monkeypatch):
    from services import payment_code_service as pcs
    urut = iter(["7F3K2", "7F3K2", "8H4M3"])   # dua tabrakan dengan KN-7F3K2 (U9), lalu bebas
    dipanggil = []

    def _palsu():
        dipanggil.append(1)
        return next(urut)
    monkeypatch.setattr(pcs, "_acak", _palsu)
    so = {"id": _id("so"), "number": "SO-PMT2-T1", "entity_id": KSC, "customer_id": "cus_x", "grand_total": 500_000,
          "payment_term_code": "CBD", "status": "confirmed"}
    await db.sales_orders.insert_one(dict(so))   # fixture
    k = await pcs.ensure_for_order(so)
    assert k["code"] == "KN-8H4M3" and len(dipanggil) == 3
    assert await db.payment_codes.count_documents({"code": "KN-7F3K2"}) == 1
    # selalu bertabrakan → berhenti sesudah lima kali, tanpa kode baru
    monkeypatch.setattr(pcs, "_acak", lambda: "7F3K2")
    so2 = {**so, "id": _id("so"), "number": "SO-PMT2-T2"}
    await db.sales_orders.insert_one(dict(so2))
    with pytest.raises(pcs.KodeBayarError):
        await pcs.ensure_for_order(so2)
    assert await db.payment_codes.count_documents({"order_id": so2["id"]}) == 0


async def test_PMT2_kode_dibuat_dari_alfabet_aman(db):
    from services import payment_code_service as pcs
    contoh = {pcs._acak() for _ in range(300)}
    assert all(len(x) == 5 and set(x) <= set("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for x in contoh)
    assert len(contoh) > 290


async def test_PMT2_find_in_text(db, siap):
    from services import payment_code_service as pcs
    for teks in ("TRF KN-7F3K2 TOKO PMT2", "transfer kn 7f3k2 makasih", "KN7F3K2", "berita: KN-7F3K2."):
        assert [k["code"] for k in await pcs.find_in_text(teks)] == ["KN-7F3K2"], teks
    assert await pcs.find_in_text("KN-AAAAA bukan kode") == []
    assert await pcs.find_in_text("") == []


async def test_PMT2_kode_per_baris_tagihan(db, siap, klien):
    """`ensure_for_line` (dipanggil CR-T2 saat baris tagihan lahir): baris DP memakai ulang kode pesanan; baris lain kode
    baru. Rencana bayar = fixture (CR-T2 belum ada)."""
    from services import payment_code_service as pcs
    oid = SIMPAN["u7"]
    kode_pesanan = (await db.payment_codes.find_one({"order_id": oid}))["code"]
    plan = {"id": _id("pplan"), "doc_type": "sales_order", "doc_id": oid, "entity_id": KSC, "status": "active",
            "lines": [{"seq": 1, "line_id": "ppl_dp", "kind": "dp", "label": "Uang Muka (DP)", "amount": 1_000_000,
                       "due_date": "", "status": "open"},
                      {"seq": 2, "line_id": "ppl_lunas", "kind": "installment", "label": "Pelunasan",
                       "amount": 1_000_000, "due_date": "2026-12-15", "status": "open"}]}
    await db.payment_plans.insert_one(dict(plan))
    dp = await pcs.ensure_for_line(plan, plan["lines"][0])
    assert dp["code"] == kode_pesanan and (dp["plan_id"], dp["line_id"]) == (plan["id"], "ppl_dp")
    lunas = await pcs.ensure_for_line(plan, plan["lines"][1])
    assert lunas["code"] != kode_pesanan and lunas["amount"] == 1_000_000 and lunas["due_date"] == "2026-12-15"
    assert (await pcs.ensure_for_line(plan, plan["lines"][1]))["code"] == lunas["code"]
    assert await db.payment_codes.count_documents({"order_id": oid}) == 2
    so = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    assert (await pcs.ensure_for_order(so))["code"] == kode_pesanan   # pesanan tetap satu kode tingkat pesanan
    rp = await db.payment_plans.find_one({"id": plan["id"]})
    assert [ln.get("pay_code") for ln in rp["lines"]] == [kode_pesanan, lunas["code"]]
    r = await _instruksi(klien, siap["h"], oid)
    j = r.json()
    assert [it["due_label"] for it in j["items"]] == ["sebelum barang dikirim", "15 Des 2026"]
    assert "\n\n" in j["text"] and j["text"].count("Pembayaran untuk pesanan") == 2


async def test_PMT2_token_rekening_bank_dari_rekening_tujuan(klien, db, siap):
    """KP-T6 `{{rekening_bank}}`: potret rekening tujuan pesanan, lalu rekening bawaan transfer PT."""
    r = await klien.put("/api/pdf/templates/invoice", headers=siap["h"], params={"entity_id": KSC},
                        json={"config": {"closing_note": "Transfer ke {{rekening_bank}}."}})
    assert r.status_code == 200, r.text
    try:
        await db.sales_orders.update_one({"id": SIMPAN["u1"]}, {"$set": {"payment_code": ""}})
        html = await _html(klien, siap["h"], "invoice", SIMPAN["u1"])   # rekening tujuan = D (U12)
        assert "Transfer ke Mandiri 140-00-7777 a.n. PT Kain Suka Cita." in html
        r = await klien.post("/api/sales-orders", headers=siap["h"], json=_isi(siap, stok=False))
        html = await _html(klien, siap["h"], "invoice", r.json()["id"])   # tanpa rekening tujuan → bawaan transfer
        assert "Transfer ke BCA 123-456-7890 a.n. PT Kain Suka Cita." in html
    finally:
        await klien.delete("/api/pdf/templates/invoice", headers=siap["h"], params={"entity_id": KSC})


async def test_PMT2_kode_tidak_ikut_hash_tanda_tangan(db, siap):
    """Instruksi bayar berubah saat tagihan lunas; isi yang ditandatangani (hash e-sign) tidak boleh ikut berubah."""
    from services import pdf_service
    built = await pdf_service.build_document("sales_order", SIMPAN["u6"], None)
    assert built["doc"]["payment_instruction"]
    assert "payment_instruction" not in pdf_service.canonical_content(built["doc"])


async def test_PMT2_skrip_cari_rekening_ketikan_hanya_lapor(db, capsys):
    """H3 — calon nomor rekening ketikan di naskah templat dilaporkan, tidak diubah."""
    spec = importlib.util.spec_from_file_location("pmt2_cari", REPO / "scripts" / "blueprint" /
                                                  "pmt2_rekening_ketikan_lapor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    await db.pdf_templates.insert_many([
        {"doc_type": "invoice", "entity_id": "ent_uji_pmt2", "version": 1,
         "config": {"closing_note": "Transfer ke BCA 1234567890 a.n. PT Lama."}},
        {"doc_type": "sales_order", "entity_id": "ent_uji_pmt2", "version": 1,
         "config": {"footer_text": "Rek. Mandiri 140-00-1234-5678"}},
        {"doc_type": "quotation", "entity_id": "ent_uji_pmt2", "version": 1,
         "config": {"intro_text": "Penawaran berlaku 14 hari. Telp 022-123"}}])
    sebelum = await db.pdf_templates.find({"entity_id": "ent_uji_pmt2"}, {"_id": 0}).to_list(10)
    assert await mod.jalankan([]) == 0
    out = capsys.readouterr().out
    assert "invoice" in out and "1234567890" in out and "140-00-1234-5678" in out
    assert "quotation" not in out
    assert "2 templat" in out
    assert await db.pdf_templates.find({"entity_id": "ent_uji_pmt2"}, {"_id": 0}).to_list(10) == sebelum
