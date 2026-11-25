"""Lapor Bayar CBD & DP · Tugas 2 — pesanan wajib bayar dulu ditahan SEBELUM gudang; kode bayar lahir sejak disetujui.

Rancangan `docs/superpowers/specs/2026-11-25-lapor-bayar-cbd-design.md` §3, §5.1, §5.2. "Wajib bayar dulu" dan jumlahnya
hanya dari `dispatch_payment_gate.evaluate`. Penanda `pay_hold` + sub-status `menunggu_bayar` (bukan status baru).

Persiapan: rekening penerimaan `ent_ksc`, pelanggan + produk Rp 10.000/m + gudang + roll 100 m (fixture, disisipkan
langsung). Pesanan, ajukan, Periksa & lepas, ACC, konfirmasi, lepas tanpa bayar = alur lewat API. Kwitansi Finance lewat
`ar_receipt_service.create_receipt` (pintu kas satu-satunya), lalu `pay_hold_service.clear_if_paid` (dipanggil Tugas 4).

Hitung tangan (PT `ent_ksc`, pesanan "tanpa PPN" supaya total = harga × jumlah):
  100 m × Rp 10.000 = Rp 1.000.000 · CBD (DP 100 %) → wajib Rp 1.000.000 · DP50 → wajib Rp 500.000 · NET30 → 0.

    cd backend && python -m pytest tests_mem/test_LB2_tahan_gudang.py -q -p no:cacheprovider -n 0
"""
from __future__ import annotations

import itertools
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from core_utils import now_iso
from services import config_resolver as resolver

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
PESAN = "Menunggu pembayaran dicek Finance — lapor bayar di rincian pesanan."
TANPA_PPN = {"tax_override": "non_ppn", "tax_override_reason": "uji LB-2 tanpa PPN"}
GERBANG = "finance.dispatch_payment_gate"
VALIDASI = "sales.require_so_validation"
_n = itertools.count(1)


def _id(awal: str) -> str:
    return f"{awal}_lb2_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun):
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
        "payment_method_codes": ["transfer"], "name": "BCA Penerimaan LB2", "account_number": "222-333-4444",
        "holder_name": "PT Kain Suka Cita", "default_receiving_methods": ["transfer"], "show_on_documents": True,
        "entity_id": KSC})
    assert r.status_code == 200, r.text
    cus, adr, prd = _id("cus"), _id("adr"), _id("prd")
    await db.customers.insert_one({"id": cus, "name": "Toko LB-2", "entity_id": KSC, "status": "active",
                                   "addresses": [{"id": adr, "label": "Utama", "city": "Bandung",
                                                  "address": "Jl. Uji 2", "recipient_name": "Bu Uji",
                                                  "phone": "081200000002"}]})
    await db.products.insert_one({"id": prd, "sku": "LB2-KAIN", "name": "Kain LB-2", "price": 10000,
                                  "base_unit": "meter", "status": "active", "lifecycle": "produksi", "category": "uji"})
    await db.warehouses.insert_one({"id": "wh_lb2", "name": "Gudang LB-2", "entity_id": KSC, "city": "Bandung"})
    finance = await akun("finance")
    return {"h": kepala_admin, "A": r.json()["id"], "cus": cus, "adr": adr, "prd": prd,
            "finance": {"id": finance["id"], "name": finance["name"], "role": "finance"}}


async def _pesan(klien, db, siap, term: str = "CBD", **lain) -> dict:
    await db.inventory_rolls.insert_one({
        "id": _id("roll"), "roll_no": f"R-LB2-{next(_n)}", "product_id": siap["prd"], "owner_entity_id": KSC,
        "warehouse_id": "wh_lb2", "status": "available", "active_movement": None, "length_remaining": 100.0,
        "lot": "L-LB2", "created_at": now_iso()})
    body = {"customer_id": siap["cus"], "shipping_address_id": siap["adr"], "entity_id": KSC,
            "payment_term_code": term, "payment_method_code": "transfer", "receiving_account_id": siap["A"],
            "items": [{"product_id": siap["prd"], "quantity": 100, "unit": "meter"}], **TANPA_PPN, **lain}
    r = await klien.post("/api/sales-orders", headers=siap["h"], json=body)
    assert r.status_code == 200, r.text
    assert r.json()["grand_total"] == 1_000_000, r.json()["grand_total"]
    return r.json()


async def _so(db, oid: str) -> dict:
    return await db.sales_orders.find_one({"id": oid}, {"_id": 0})


async def _ajukan(klien, siap, oid: str) -> dict:
    r = await klien.post(f"/api/sales-orders/{oid}/submit-for-approval", headers=siap["h"])
    assert r.status_code == 200, r.text
    return r.json()


async def _periksa_lepas(klien, siap, oid: str) -> dict:
    r = await klien.post(f"/api/sales-orders/{oid}/review-release", headers=siap["h"], json={"note": "uji LB-2"})
    assert r.status_code == 200, r.text
    return r.json()


async def _tugas_keluar(db, oid: str) -> int:
    return await db.wms_tasks.count_documents({"order_id": oid, "flow_type": "outbound"})


async def _kwitansi_finance(siap, oid: str, nominal: float) -> dict:
    from services import ar_receipt_service as ars
    return await ars.create_receipt({
        "customer_id": siap["cus"], "entity_id": KSC, "amount": nominal, "method": "transfer",
        "account_id": siap["A"], "reference_no": f"TRF-LB2-{next(_n)}",
        "allocations": [{"order_id": oid, "amount": nominal}]}, siap["finance"])


# ── Tahan dimulai saat disetujui (B1: kode bayar sejak disetujui) ───────────────────────────────────────────────────
async def test_cbd_disetujui_tertahan_dan_berkode(klien, db, siap):
    so = await _pesan(klien, db, siap)
    assert await db.payment_codes.count_documents({"order_id": so["id"]}) == 0
    await _ajukan(klien, siap, so["id"])                       # auto-approve (tanpa gerbang ACC)
    so = await _so(db, so["id"])
    assert so["status"] == "approved"
    hold = so["pay_hold"]
    assert hold["required"] == 1_000_000 and hold["basis"] == "tercatat"
    mulai = datetime.fromisoformat(hold["since"])
    assert datetime.fromisoformat(hold["due_at"]) - mulai == timedelta(days=3)   # `sales.batas_bayar_hari` bawaan
    kode = await db.payment_codes.find({"order_id": so["id"]}, {"_id": 0}).to_list(5)
    assert [(k["amount"], k["order_level"]) for k in kode] == [(1_000_000, True)], kode
    assert so["payment_code"] == kode[0]["code"]
    assert so["sub_status"][0] == "menunggu_bayar"
    assert "siap_confirm" not in so["sub_status"]
    from services.so_status import SUBSTATUS_LABELS
    assert SUBSTATUS_LABELS["menunggu_bayar"] == "Menunggu bayar"
    # idempoten: mulai lagi tidak menimpa `since`/`due_at` dan tidak melahirkan kode kedua
    from services import pay_hold_service as phs
    await phs.start(so)
    again = await _so(db, so["id"])
    assert (again["pay_hold"]["since"], again["pay_hold"]["due_at"]) == (hold["since"], hold["due_at"])
    assert await db.payment_codes.count_documents({"order_id": so["id"]}) == 1
    assert await phs.blocked(again) is True


async def test_periksa_lepas_menunggu_bayar_tanpa_409(klien, db, siap):
    so = await _pesan(klien, db, siap)
    out = await _periksa_lepas(klien, siap, so["id"])
    assert out["released"] is False
    assert out["release_state"]["waiting"] == "bayar"
    assert out["order"]["status"] == "approved"
    so = await _so(db, so["id"])
    assert so["status"] == "approved"
    assert so["release"]["requested"] is True and so["release"]["waiting"] == "bayar"
    assert so["pay_hold"]["required"] == 1_000_000
    assert await _tugas_keluar(db, so["id"]) == 0
    # layanan langsung: `try_release` tidak melempar, mengembalikan bentuk menunggu
    from services import so_release_service as rel
    assert await rel.try_release(so["id"], {"id": "u", "name": "Uji", "role": "admin"}) == {
        "released": False, "waiting": "bayar"}
    assert (await _so(db, so["id"]))["status"] == "approved"


async def test_confirm_lama_409_pemandu(klien, db, siap):
    so = await _pesan(klien, db, siap)
    r = await klien.post(f"/api/sales-orders/{so['id']}/verify", headers=siap["h"], json={"note": "uji LB-2"})
    assert r.status_code == 200, r.text
    await _ajukan(klien, siap, so["id"])
    r = await klien.post(f"/api/sales-orders/{so['id']}/confirm", headers=siap["h"])
    assert (r.status_code, r.json().get("detail")) == (409, PESAN), r.text
    assert (await _so(db, so["id"]))["status"] == "approved"
    assert await _tugas_keluar(db, so["id"]) == 0


async def test_net30_tidak_tertahan(klien, db, siap):
    so = await _pesan(klien, db, siap, term="NET30")
    out = await _periksa_lepas(klien, siap, so["id"])
    assert out["released"] is True and out["release_state"]["waiting"] == ""
    so = await _so(db, so["id"])
    assert so["status"] == "confirmed"
    assert "pay_hold" not in so
    assert await _tugas_keluar(db, so["id"]) >= 1
    assert await db.payment_codes.count_documents({"order_id": so["id"]}) == 0


async def test_dp50_tertahan_setengah(klien, db, siap):
    so = await _pesan(klien, db, siap, term="DP50")
    await _ajukan(klien, siap, so["id"])
    so = await _so(db, so["id"])
    assert so["status"] == "approved" and so["pay_hold"]["required"] == 500_000
    k = await db.payment_codes.find_one({"order_id": so["id"]}, {"_id": 0})
    assert k["amount"] == 500_000


async def test_gerbang_off_tidak_menahan(klien, db, siap):
    await resolver.set_value(GERBANG, "off", scope_type="entity", scope_id=KSC, actor="uji", reason="uji LB-2")
    try:
        so = await _pesan(klien, db, siap)
        out = await _periksa_lepas(klien, siap, so["id"])
        assert out["released"] is True
        so = await _so(db, so["id"])
        assert so["status"] == "confirmed" and "pay_hold" not in so
    finally:
        await resolver.clear_layer(GERBANG, scope_type="entity", scope_id=KSC, actor="uji", reason="pulihkan uji LB-2")


async def test_sample_tidak_menahan(klien, db, siap):
    from services import pay_hold_service as phs
    so = await _pesan(klien, db, siap)
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"is_sample": True}})   # dikecualikan `evaluate`
    out = await _periksa_lepas(klien, siap, so["id"])
    assert out["released"] is True
    so = await _so(db, so["id"])
    assert so["status"] == "confirmed" and "pay_hold" not in so
    # pesanan sample (Meja Sample punya gerbang bayarnya sendiri) tidak pernah diberi tahan gudang
    sampel = {"id": _id("so"), "number": "SOS-LB2", "entity_id": KSC, "status": "approved", "order_type": "sample",
              "payment_term_code": "CBD", "grand_total": 1_000_000.0, "paid_total": 0, "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(sampel))
    assert await phs.blocked(sampel) is False
    assert await phs.start(sampel) is None
    assert "pay_hold" not in await _so(db, sampel["id"])


# ── Tahan dibuka: lepas tanpa bayar (B6) dan kwitansi Finance ──────────────────────────────────────────────────────
async def test_release_unpaid_membuka_tahan_dan_melepas(klien, db, siap):
    so = await _pesan(klien, db, siap)
    await _periksa_lepas(klien, siap, so["id"])
    assert (await _so(db, so["id"]))["status"] == "approved"
    r = await klien.post(f"/api/sales-orders/{so['id']}/dispatch-payment-release", headers=siap["h"],
                         json={"reason": "Pelanggan langganan, bayar di tempat"})
    assert r.status_code == 200, r.text
    assert r.json()["blocked"] is False and r.json()["released"]
    so = await _so(db, so["id"])
    assert so["status"] == "confirmed"
    assert "pay_hold" not in so and "waiting" not in so["release"]
    assert await _tugas_keluar(db, so["id"]) >= 1


async def test_cabut_pengecualian_menahan_lagi(klien, db, siap):
    """Pengecualian dicabut sebelum dilepas ke gudang → pesanan kembali tertahan (penanda baru)."""
    so = await _pesan(klien, db, siap)
    await _ajukan(klien, siap, so["id"])                       # belum "Periksa & lepas": tidak dilepas otomatis
    path = f"/api/sales-orders/{so['id']}/dispatch-payment-release"
    r = await klien.post(path, headers=siap["h"], json={"reason": "Pelanggan langganan, bayar di tempat"})
    assert r.status_code == 200, r.text
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and "pay_hold" not in cur and cur["sub_status"] == ["siap_confirm"]
    r = await klien.post(f"{path}/revoke", headers=siap["h"], json={"reason": "Batal, tetap bayar dulu"})
    assert r.status_code == 200 and r.json()["blocked"] is True, r.text
    cur = await _so(db, so["id"])
    assert cur["pay_hold"]["required"] == 1_000_000 and cur["sub_status"][0] == "menunggu_bayar"


async def test_tahan_dulu_lalu_lepas_menunggu_bayar(klien, db, siap):
    """"Tahan dulu" Admin Sales lalu "Lepas ke gudang" (`/release`): 200 menunggu bayar, bukan 409."""
    so = await _pesan(klien, db, siap)
    r = await klien.post(f"/api/sales-orders/{so['id']}/review-release", headers=siap["h"],
                         json={"note": "uji LB-2", "hold": True})
    assert r.status_code == 200, r.text
    assert r.json()["release_state"]["hold"] is True and r.json()["order"]["status"] == "reserved"
    r = await klien.post(f"/api/sales-orders/{so['id']}/release", headers=siap["h"])
    assert r.status_code == 200, r.text
    assert r.json()["released"] is False and r.json()["release_state"]["waiting"] == "bayar"
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["release"]["waiting"] == "bayar" and cur["pay_hold"]
    assert await _tugas_keluar(db, so["id"]) == 0


async def test_kwitansi_finance_cukup_melepas(klien, db, siap):
    from services import pay_hold_service as phs
    so = await _pesan(klien, db, siap)
    await _periksa_lepas(klien, siap, so["id"])
    await _kwitansi_finance(siap, so["id"], 400_000)          # sebagian: masih kurang → tetap tertahan
    assert await phs.clear_if_paid(so["id"]) is False
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and cur["pay_hold"]
    await _kwitansi_finance(siap, so["id"], 600_000)          # lunas bagian wajib
    assert (await _so(db, so["id"]))["status"] == "approved"   # kwitansi sendiri tidak melepas
    assert await phs.clear_if_paid(so["id"]) is True
    so = await _so(db, so["id"])
    assert so["status"] == "confirmed" and "pay_hold" not in so
    assert await _tugas_keluar(db, so["id"]) >= 1
    assert await db.payment_codes.count_documents({"order_id": so["id"]}) == 1   # kode yang sama dipakai jadwal


async def test_lunas_sebelum_diperiksa_admin_sales_tidak_lepas_otomatis(klien, db, siap):
    """R4 — tanpa "Periksa & lepas" (`release.requested`), tahan hanya dicabut; pesanan menunggu Admin Sales."""
    from services import pay_hold_service as phs
    so = await _pesan(klien, db, siap)
    await _ajukan(klien, siap, so["id"])
    await _kwitansi_finance(siap, so["id"], 1_000_000)
    assert await phs.clear_if_paid(so["id"]) is False
    cur = await _so(db, so["id"])
    assert cur["status"] == "approved" and "pay_hold" not in cur
    assert cur["sub_status"] == ["siap_confirm"]
    assert await _tugas_keluar(db, so["id"]) == 0
    out = await _periksa_lepas(klien, siap, so["id"])
    assert out["released"] is True and (await _so(db, so["id"]))["status"] == "confirmed"


async def test_pesanan_confirmed_lama_tidak_tertahan(klien, db, siap):
    """Pesanan CBD yang sudah dilepas ke gudang sebelum fitur ini: tanpa `pay_hold`, tetap jalan; gerbang surat jalan
    tetap menjadi pagar kedua seperti dulu."""
    from services import dispatch_payment_gate as gate
    from services import pay_hold_service as phs
    from services.so_status import derive_stage_substatus
    lama = {"id": _id("so"), "number": "SO-LB2-LAMA", "entity_id": KSC, "customer_id": siap["cus"],
            "status": "confirmed", "payment_term_code": "CBD", "grand_total": 1_000_000.0, "paid_total": 0,
            "payments": [], "items": [], "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(lama))
    assert await phs.start(lama) is None
    assert await phs.clear_if_paid(lama["id"]) is False
    cur = await _so(db, lama["id"])
    assert cur["status"] == "confirmed" and "pay_hold" not in cur
    assert derive_stage_substatus(cur)[1] == ["siap_pick"]
    with pytest.raises(HTTPException) as e:
        await gate.guard(lama["id"])
    assert e.value.status_code == 409 and e.value.detail.startswith("Tertahan pembayaran: termin")


# ── Semua penulis `approved` memulai tahan ──────────────────────────────────────────────────────────────────────────
async def test_acc_manajer_memulai_tahan_lalu_menunggu_bayar(klien, db, siap):
    await resolver.set_value(VALIDASI, True, scope_type="entity", scope_id=KSC, actor="uji", reason="uji LB-2")
    try:
        # jalur Pusat Persetujuan: keputusan entri (routers/so_approvals.decide_approval)
        so = await _pesan(klien, db, siap)
        out = await _periksa_lepas(klien, siap, so["id"])
        assert out["order"]["status"] == "waiting_approval" and out["release_state"]["waiting"] == "acc"
        cur = await _so(db, so["id"])
        assert "pay_hold" not in cur and await db.payment_codes.count_documents({"order_id": so["id"]}) == 0
        entri = next(p for p in cur["pending_approvals"] if p["status"] == "pending")
        r = await klien.post(f"/api/sales-orders/{so['id']}/approvals/{entri['id']}/decide", headers=siap["h"],
                             json={"decision": "approve", "notes": "uji LB-2"})
        assert r.status_code == 200, r.text
        cur = await _so(db, so["id"])
        assert cur["status"] == "approved" and cur["pay_hold"]["required"] == 1_000_000
        assert cur["release"]["waiting"] == "bayar"            # lepas otomatis dicoba → menunggu bayar
        assert await db.payment_codes.count_documents({"order_id": so["id"], "order_level": True}) == 1
        assert await _tugas_keluar(db, so["id"]) == 0
        # jalur tombol Setujui pesanan (routers/sales_orders_extra.approve_order)
        so2 = await _pesan(klien, db, siap)
        await _ajukan(klien, siap, so2["id"])
        assert (await _so(db, so2["id"]))["status"] == "waiting_approval"
        r = await klien.post(f"/api/sales-orders/{so2['id']}/approve", headers=siap["h"])
        assert r.status_code == 200, r.text
        cur = await _so(db, so2["id"])
        assert cur["status"] == "approved" and cur["pay_hold"]["required"] == 1_000_000
        assert await db.payment_codes.count_documents({"order_id": so2["id"], "order_level": True}) == 1
    finally:
        await resolver.clear_layer(VALIDASI, scope_type="entity", scope_id=KSC, actor="uji", reason="pulihkan uji LB-2")


async def test_lanjut_harga_normal_memulai_tahan(db, siap):
    from services import so_release_service as rel
    apr = "apr_lb2_hk"
    so = {"id": _id("so"), "number": "SO-LB2-HK", "entity_id": KSC, "customer_id": siap["cus"],
          "status": "waiting_approval", "payment_term_code": "CBD", "grand_total": 1_000_000.0, "paid_total": 0,
          "payments": [], "items": [], "verification": {"status": "verified"},
          "release": {"requested": True, "hold": False, "by": "Uji", "at": now_iso()},
          "pending_approvals": [{"id": apr, "type": "special_price", "status": "rejected", "product_name": "Kain"}],
          "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    out = await rel.continue_normal_price(so["id"], apr, {"id": "u", "name": "Uji Sales", "role": "sales"})
    assert out["order"]["status"] == "approved"
    assert out["release_state"]["waiting"] == "bayar"
    cur = await _so(db, so["id"])
    assert cur["pay_hold"]["required"] == 1_000_000 and cur["release"]["waiting"] == "bayar"
