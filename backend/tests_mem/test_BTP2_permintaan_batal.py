"""BTP-2 — permintaan batal pesanan + persetujuan berbasis izin & kebijakan.

Rancangan `docs/superpowers/specs/2026-11-25-batal-tutup-sisa-pesanan-design.md` §5.1–§5.4, §5.8 (keputusan pemilik
A2-1…A2-5, 25 Nov). Pembatalan pesanan yang sudah ada uang masuk atau barangnya sudah disiapkan gudang tidak lagi
langsung jalan: menjadi `cancel_request` menunggu pemegang izin `order.approve_cancel` yang lolos Aturan Persetujuan
(jenis `sales_order.batal`). Pengaju yang berwenang memutus disetujui sendiri; sales pemilik pesanan tidak pernah bisa
menyetujui pembatalannya sendiri.

    cd backend && python -m pytest tests_mem/test_BTP2_permintaan_batal.py -n 0 -q
"""
from __future__ import annotations

import uuid

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
KANDA = "ent_kanda"
KUNCI = "sales.cancel_approval_when"
AJU = "permintaan_batal_pesanan"
PUTUS = "permintaan_batal_diputus"
PESAN_202 = "Permintaan diajukan — menunggu persetujuan."
R1 = {"request_id", "order_id", "number", "customer_name", "entity_id", "action", "amount", "reason",
      "requested_by", "requested_at", "approval_basis"}


def _id(awal: str) -> str:
    return f"{awal}_btp2_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
        "payment_method_codes": ["transfer"], "name": "BCA Operasional BTP2", "account_number": "741-559-8888",
        "holder_name": "PT Kain Suka Cita", "default_receiving_methods": ["transfer"], "entity_id": KSC})
    assert r.status_code == 200, r.text
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": "Uji BTP2 · Toko Kain", "entity_id": KSC, "status": "active",
                                   "payment_profile": {"default_method": "tempo", "term_days": 30}})
    sales, admin_sales = await akun("sales"), await akun("sales_admin")
    finance, manager = await akun("finance"), await akun("manager")
    return {"h": kepala_admin, "P": cus,
            "sales": sales, "hs": await sesi(sales),
            "sa": admin_sales, "hsa": await sesi(admin_sales),
            "fin": finance, "hf": await sesi(finance),
            "mgr": manager, "hm": await sesi(manager)}


async def _pesanan(klien, db, siap, total: float = 1_000_000, bayar: float = 0.0, **lain) -> dict:
    so = {"id": _id("so"), "number": f"SO-BTP2-{uuid.uuid4().hex[:5]}", "entity_id": KSC, "customer_id": siap["P"],
          "customer_name": "Uji BTP2 · Toko Kain", "status": "confirmed", "grand_total": float(total),
          "ppn_amount": 0.0, "payments": [], "paid_total": 0, "payment_status": "unpaid", "payment_term_code": "CBD",
          "items": [], "sales_id": siap["sales"]["id"], "sales_name": siap["sales"]["name"],
          "created_at": now_iso()}
    so.update(lain)
    await db.sales_orders.insert_one(dict(so))
    if bayar:
        r = await klien.post("/api/ar-receipts", headers=siap["h"], json={
            "customer_id": siap["P"], "amount": bayar, "method": "transfer", "entity_id": KSC,
            "reference_no": f"TRF-{so['number']}", "allocations": [{"order_id": so["id"], "amount": bayar}]})
        assert r.status_code == 200, r.text
    return so


async def _batal(klien, h, so, alasan: str = "Pelanggan membatalkan pesanan"):
    return await klien.post(f"/api/sales-orders/{so['id']}/cancel", headers=h, json={"reason": alasan})


async def _putus(klien, h, so, keputusan: str, catatan: str = ""):
    return await klien.post(f"/api/sales-orders/{so['id']}/cancel-request/decision", headers=h,
                            json={"decision": keputusan, "note": catatan})


async def _so(db, so) -> dict:
    return await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})


async def _titipan(db, cus: str) -> float:
    c = await db.customers.find_one({"id": cus}, {"_id": 0, "deposit_balance": 1})
    return round(float((c or {}).get("deposit_balance") or 0), 2)


async def _notif(db, jenis: str, req_id: str) -> list:
    return await db.notifications.find({"type": jenis, "ref": {"$regex": f"^{jenis}:{req_id}"}},
                                       {"_id": 0}).to_list(100)


def _teks(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


# ── Alur dasar ───────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_BTP2_belum_bayar_belum_siap_langsung_batal(klien, db, siap):
    so = await _pesanan(klien, db, siap)
    r = await _batal(klien, siap["hs"], so)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    o = await _so(db, so)
    assert o["status"] == "cancelled"
    assert not o.get("cancel_request") and not o.get("cancel_requests"), "perilaku lama: tanpa permintaan"


async def test_BTP2_dibayar_jadi_permintaan(klien, db, siap):
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r = await _batal(klien, siap["hs"], so, "Pelanggan berubah pikiran")
    assert r.status_code == 202, r.text
    j = r.json()
    req = j["request"]
    assert j["message"] == PESAN_202 and j["order_status"] == "confirmed"
    assert req["status"] == "pending" and req["needs_approval"] is True and "paid" in req["approval_basis"]
    assert req["action"] == "cancel" and round(float(req["amount"]), 2) == 1_000_000
    assert req["requested_by_id"] == siap["sales"]["id"] and req["reason"] == "Pelanggan berubah pikiran"
    for k in ("id", "requested_by", "requested_at", "decided_by", "decided_by_id", "decided_at", "decision_note",
              "self_approved", "result"):
        assert k in req, k
    o = await _so(db, so)
    assert o["status"] == "confirmed", "pesanan TIDAK batal selama menunggu"
    assert o["cancel_request"]["status"] == "pending" and o["cancel_request"]["id"] == req["id"]
    rows = await _notif(db, AJU, req["id"])
    penerima = {n["recipient_user"] for n in rows}
    assert siap["fin"]["id"] in penerima and siap["mgr"]["id"] in penerima
    assert siap["sales"]["id"] not in penerima, "sales tidak memegang izin setujui pembatalan"
    assert all(n["severity"] == "warning" and n["action_type"] == "so_cancel_request" for n in rows)

    # Antrean penyetuju (Ruling R1): bentuk baris persis.
    r = await klien.get("/api/sales-orders/cancel-requests", headers=siap["hf"], params={"status": "pending"})
    assert r.status_code == 200, r.text
    baris = next(x for x in r.json() if x["order_id"] == so["id"])
    assert set(baris) == R1, sorted(set(baris) ^ R1)
    assert baris["request_id"] == req["id"] and baris["number"] == so["number"] and baris["entity_id"] == KSC
    assert baris["action"] == "cancel" and round(float(baris["amount"]), 2) == 1_000_000
    assert baris["requested_by"] == siap["sales"]["name"] and "paid" in baris["approval_basis"]


async def test_BTP2_setujui_menjalankan_batal_dan_titipan(klien, db, siap):
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    awal = await _titipan(db, siap["P"])
    r = await _batal(klien, siap["hsa"], so)   # Admin Sales mengajukan atas pesanan milik sales
    assert r.status_code == 202, r.text
    req_id = r.json()["request"]["id"]

    r = await _putus(klien, siap["hf"], so, "approve", "Uang muka dipindah ke titipan")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["order_status"] == "cancelled" and j["request"]["status"] == "approved"
    assert round(float(j["result"]["advance_to_deposit"]), 2) == 1_000_000
    o = await _so(db, so)
    assert o["status"] == "cancelled" and "cancel_request" not in o
    h = o["cancel_requests"][-1]
    assert h["id"] == req_id and h["status"] == "approved" and h["self_approved"] is False
    assert h["decided_by_id"] == siap["fin"]["id"] and h["decision_note"] == "Uang muka dipindah ke titipan"
    assert round(float(h["result"]["advance_to_deposit"]), 2) == 1_000_000
    assert await _titipan(db, siap["P"]) == round(awal + 1_000_000, 2)
    penerima = {n["recipient_user"] for n in await _notif(db, PUTUS, req_id)}
    assert {siap["sa"]["id"], siap["sales"]["id"]} <= penerima, "pengaju dan sales pemilik diberi tahu"


async def test_BTP2_tolak_pesanan_lanjut(klien, db, siap):
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r = await _batal(klien, siap["hs"], so)
    assert r.status_code == 202, r.text
    req_id = r.json()["request"]["id"]
    r = await _putus(klien, siap["hf"], so, "reject", "")
    assert r.status_code == 422, r.text
    r = await _putus(klien, siap["hf"], so, "reject", "Pelanggan jadi mengambil barangnya")
    assert r.status_code == 200, r.text
    assert r.json()["request"]["status"] == "rejected" and r.json()["order_status"] == "confirmed"
    o = await _so(db, so)
    assert o["status"] == "confirmed" and "cancel_request" not in o
    h = o["cancel_requests"][-1]
    assert h["status"] == "rejected" and h["decision_note"] == "Pelanggan jadi mengambil barangnya"
    rows = await _notif(db, PUTUS, req_id)
    n = next(x for x in rows if x["recipient_user"] == siap["sales"]["id"])
    assert "Pelanggan jadi mengambil barangnya" in n["body"]


# ── Siapa boleh memutus ─────────────────────────────────────────────────────────────────────────────────────────────
async def test_BTP2_sales_tidak_bisa_menyetujui_miliknya(klien, db, siap, akun, sesi, peran_tanpa_acuan):
    peran = await peran_tanpa_acuan({"order": ["view", "cancel", "approve_cancel"]})
    pemilik, anggota = await akun(peran), await akun(peran)
    hp, ha = await sesi(pemilik), await sesi(anggota)
    so = await _pesanan(klien, db, siap, bayar=1_000_000, sales_id=pemilik["id"], sales_name=pemilik["name"],
                        sales_team=[{"sales_id": pemilik["id"], "share_pct": 50},
                                    {"sales_id": anggota["id"], "share_pct": 50}])
    r = await klien.get(f"/api/sales-orders/{so['id']}/cancel-check", headers=hp, params={"action": "cancel"})
    assert r.status_code == 200, r.text
    assert r.json()["needs_approval"] is True and r.json()["can_self_approve"] is False
    r = await _batal(klien, hp, so)
    assert r.status_code == 202, r.text   # TIDAK disetujui sendiri walau perannya memegang izin setujui
    r = await _putus(klien, hp, so, "approve")
    assert r.status_code == 403, r.text
    r = await _putus(klien, ha, so, "approve")
    assert r.status_code == 403, r.text   # anggota tim penjualan pesanan = sales pesanan
    assert (await _so(db, so))["cancel_request"]["status"] == "pending"
    # Pemegang izin yang bukan sales pesanan dan bukan pengaju boleh memutus (izin, bukan nama peran).
    lain = await akun(peran)
    r = await _putus(klien, await sesi(lain), so, "approve")
    assert r.status_code == 200, r.text
    assert (await _so(db, so))["status"] == "cancelled"


async def test_BTP2_manager_disetujui_sendiri(klien, db, siap):
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r = await _batal(klien, siap["hm"], so)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    o = await _so(db, so)
    assert o["status"] == "cancelled" and "cancel_request" not in o
    h = o["cancel_requests"][-1]
    assert h["status"] == "approved" and h["self_approved"] is True and h["needs_approval"] is True
    assert h["requested_by_id"] == h["decided_by_id"] == siap["mgr"]["id"]
    assert round(float(h["result"]["advance_to_deposit"]), 2) == 1_000_000


async def test_BTP2_tarik_permintaan(klien, db, siap):
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel-request/withdraw", headers=siap["hs"])
    assert r.status_code == 409, r.text   # belum ada permintaan
    r = await _batal(klien, siap["hs"], so)
    assert r.status_code == 202, r.text
    req_id = r.json()["request"]["id"]
    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel-request/withdraw", headers=siap["hs"])
    assert r.status_code == 200, r.text
    assert r.json()["request"]["status"] == "withdrawn"
    o = await _so(db, so)
    assert o["status"] == "confirmed" and "cancel_request" not in o
    assert o["cancel_requests"][-1]["status"] == "withdrawn" and o["cancel_requests"][-1]["id"] == req_id
    rows = await _notif(db, AJU, req_id)
    assert rows and all(n.get("resolved_at") and n.get("read") is True for n in rows)


# ── Pengaturan & kebijakan nominal ─────────────────────────────────────────────────────────────────────────────────
async def test_BTP2_pengaturan_selalu_dan_tidak_pernah(klien, db, siap):
    async def _atur(nilai):
        r = await klien.put("/api/config/values", headers=siap["h"], json={"items": [{
            "key": KUNCI, "value": nilai, "scope_type": "entity", "scope_id": KSC, "reason": "uji BTP-2 pengaturan"}]})
        assert r.status_code == 200, r.text
    try:
        await _atur("selalu")
        so = await _pesanan(klien, db, siap)
        r = await _batal(klien, siap["hs"], so)
        assert r.status_code == 202, r.text
        assert r.json()["request"]["approval_basis"] == []
        await _atur("tidak_pernah")
        so2 = await _pesanan(klien, db, siap, bayar=1_000_000)
        r = await _batal(klien, siap["hs"], so2)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"
    finally:
        await klien.post("/api/config/values/clear", headers=siap["h"], json={
            "key": KUNCI, "scope_type": "entity", "scope_id": KSC, "reason": "pulihkan sesudah uji BTP-2"})


async def test_BTP2_rentang_mulai_x_membebaskan(klien, db, siap):
    from services import approval_policy_service as aps
    from services import so_cancel_service as scs
    row = {**aps._row("sales_order.batal", KSC, 1, [], any_holder=True, min_amount=5_000_000),
           "id": "btp2_rentang_ksc", "version": 1}
    await db.approval_policies.insert_one(dict(row))
    try:
        so = await _pesanan(klien, db, siap, bayar=1_000_000)
        r = await _batal(klien, siap["hs"], so)
        assert r.status_code == 200, r.text   # Rp1 jt < Rp5 jt → tanpa persetujuan
        assert r.json()["status"] == "cancelled"
        besar = {"entity_id": KSC, "paid_total": 6_000_000, "id": _id("so"), "grand_total": 6_000_000}
        hasil = await scs.needs_approval(besar, "cancel", amount=6_000_000)
        assert hasil["needs"] is True and hasil["basis"] == ["paid"] and hasil["amount"] == 6_000_000
    finally:
        await db.approval_policies.delete_many({"id": "btp2_rentang_ksc"})


# ── Fokus review ────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_BTP2_ajukan_dua_kali_409(klien, db, siap):
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r1 = await _batal(klien, siap["hs"], so)
    assert r1.status_code == 202, r1.text
    r2 = await _batal(klien, siap["hs"], so)
    assert r2.status_code == 409, r2.text
    r3 = await _batal(klien, siap["hsa"], so)
    assert r3.status_code == 409, r3.text
    o = await _so(db, so)
    assert o["cancel_request"]["id"] == r1.json()["request"]["id"] and not o.get("cancel_requests")


async def test_BTP2_dua_penyetuju_satu_lolos(klien, db, siap):
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    awal = await _titipan(db, siap["P"])
    assert (await _batal(klien, siap["hs"], so)).status_code == 202
    r1 = await _putus(klien, siap["hf"], so, "approve")
    r2 = await _putus(klien, siap["hm"], so, "approve")
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 409, r2.text
    o = await _so(db, so)
    tarik = [p for p in o["payments"] if float(p.get("amount") or 0) < 0]
    assert len(tarik) == 1, "uang muka dipindah ke titipan SEKALI"
    assert await _titipan(db, siap["P"]) == round(awal + 1_000_000, 2)
    assert [h["status"] for h in o["cancel_requests"]] == ["approved"]


async def test_BTP2_faktur_terbit_saat_menunggu(klien, db, siap):
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r = await _batal(klien, siap["hs"], so)
    assert r.status_code == 202, r.text
    fkt = _id("fkt")
    await db.tax_invoices.insert_one({"id": fkt, "order_id": so["id"], "status": "normal", "entity_id": KSC,
                                      "number": "040.026-26.00000001", "created_at": now_iso()})
    r = await _putus(klien, siap["hf"], so, "approve")
    assert r.status_code == 409, r.text
    assert "Faktur Pajak" in _teks(r)
    o = await _so(db, so)
    assert o["status"] == "confirmed" and o["cancel_request"]["status"] == "pending"
    assert "deciding" not in o["cancel_request"], "penanda proses dilepas sesudah eksekusi gagal"
    # Faktur dibatalkan → keputusan yang sama bisa diulang.
    await db.tax_invoices.update_one({"id": fkt}, {"$set": {"status": "batal"}})
    r = await _putus(klien, siap["hf"], so, "approve")
    assert r.status_code == 200, r.text
    assert (await _so(db, so))["status"] == "cancelled"


async def test_BTP2_pesanan_mati_lewat_jalur_lain_mem_void(klien, db, siap):
    """Pesanan yang sudah batal lewat jalur lain selama permintaan menunggu: setujui → 409, permintaan ditutup `void`
    (tidak dicatat sebagai persetujuan yang membatalkan). Faktur aktif sebelum pengajuan → 409 tanpa permintaan."""
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r = await _batal(klien, siap["hs"], so)
    assert r.status_code == 202, r.text
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "cancelled",
                                                                  "cancelled_at": "2020-01-01T00:00:00+00:00"}})
    r = await _putus(klien, siap["hf"], so, "approve")
    assert r.status_code == 409, r.text
    o = await _so(db, so)
    assert "cancel_request" not in o and o["cancel_requests"][-1]["status"] == "void"

    so2 = await _pesanan(klien, db, siap, bayar=1_000_000)
    await db.tax_invoices.insert_one({"id": _id("fkt"), "order_id": so2["id"], "status": "normal", "entity_id": KSC,
                                      "number": "040.026-26.00000002", "created_at": now_iso()})
    for h in (siap["hs"], siap["hm"]):   # pengaju biasa & yang boleh menyetujui sendiri
        r = await _batal(klien, h, so2)
        assert r.status_code == 409 and "Faktur Pajak" in _teks(r), r.text
    o = await _so(db, so2)
    assert o["status"] == "confirmed" and not o.get("cancel_request") and not o.get("cancel_requests")


async def test_BTP2_batal_sample_mem_void(klien, db, siap):
    """Jalur sejajar §5.6a: batal Pesanan Sample (di luar alur persetujuan) menutup permintaan yang menunggu `void`."""
    so = await _pesanan(klien, db, siap, status="waiting_approval", order_type="sample",
                        cancel_request={"id": "scr_btp2_sample", "action": "cancel", "status": "pending",
                                        "reason": "uji", "requested_by": "uji", "requested_by_id": "usr_x",
                                        "requested_at": now_iso(), "amount": 1_000_000, "approval_basis": ["paid"]})
    r = await klien.post(f"/api/sample-orders/{so['id']}/cancel", headers=siap["h"], json={"note": "salah input"})
    assert r.status_code == 200, r.text
    o = await _so(db, so)
    assert o["status"] == "cancelled" and "cancel_request" not in o
    assert o["cancel_requests"][-1]["status"] == "void" and o["cancel_requests"][-1]["id"] == "scr_btp2_sample"


async def test_BTP2_lintas_pt(klien, db, siap, akun, sesi, peran_tanpa_acuan):
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r = await _batal(klien, siap["hs"], so)
    assert r.status_code == 202, r.text
    req_id = r.json()["request"]["id"]
    fk = await akun("finance", entitas=(KANDA,))
    hk = await sesi(fk, entitas=KANDA)
    r = await klien.get("/api/sales-orders/cancel-requests", headers=hk)
    assert r.status_code == 200, r.text
    assert so["id"] not in {x["order_id"] for x in r.json()}
    r = await _putus(klien, hk, so, "approve")
    assert r.status_code in (403, 404), r.text
    assert fk["id"] not in {n["recipient_user"] for n in await _notif(db, AJU, req_id)}, "pagar PT notifikasi"
    peran = await peran_tanpa_acuan({"order": ["view", "approve_cancel"]})
    u = await akun(peran, entitas=(KANDA,))
    r = await _putus(klien, await sesi(u, entitas=KSC), so, "approve")
    assert r.status_code == 403, r.text
    r = await _putus(klien, await sesi(u, entitas=KANDA), so, "approve")
    assert r.status_code == 404, r.text
    r = await klien.get("/api/sales-orders/cancel-requests", headers=await sesi(u, entitas=KANDA),
                        params={"entity_id": KSC})
    assert r.status_code == 403, r.text
    assert (await _so(db, so))["cancel_request"]["status"] == "pending"


async def test_BTP2_kedaluwarsa_mem_void(klien, db, siap):
    from services import so_cancel_service as scs
    from services.inventory_service import expire_old_reservations
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r = await _batal(klien, siap["hs"], so)
    assert r.status_code == 202, r.text
    req_id = r.json()["request"]["id"]
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "reserved",
                                                                  "reservation_expires_at": "2020-01-01T00:00:00+00:00"}})
    assert await expire_old_reservations() >= 1
    o = await _so(db, so)
    assert o["status"] == "expired" and "cancel_request" not in o
    h = o["cancel_requests"][-1]
    assert h["id"] == req_id and h["status"] == "void" and "kedaluwarsa" in h["decision_note"].lower()
    rows = await _notif(db, AJU, req_id)
    assert rows and all(n.get("resolved_at") for n in rows)
    assert await scs.void_pending(so["id"], "uji ulang") is False, "aman diulang"
    assert await scs.pending_of(so["id"]) is None


async def test_BTP2_notifikasi_terlihat_dan_ditutup(klien, db, siap):
    from access_modules import nav_allowed_for_perms
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r = await _batal(klien, siap["hs"], so)
    assert r.status_code == 202, r.text
    req_id = r.json()["request"]["id"]
    r = await klien.get("/api/notifications", headers=siap["hf"])
    assert r.status_code == 200, r.text
    n = next((x for x in r.json() if x.get("type") == AJU and x.get("action_id") == req_id), None)
    assert n, "Finance melihat permintaan lewat lonceng"
    assert n["severity"] == "warning" and n["action_type"] == "so_cancel_request" and not n.get("resolved_at")
    assert so["number"] in n["title"]
    # Tautan boleh dibuka siapa pun yang memegang izin setujui pembatalan (penyaring relevansi tautan).
    assert n["link"] in nav_allowed_for_perms({"order": ["approve_cancel"]})
    assert n["link"] in nav_allowed_for_perms({"order": ["view", "approve_cancel"]})

    r = await _putus(klien, siap["hf"], so, "reject", "Pelanggan jadi mengambil barangnya")
    assert r.status_code == 200, r.text
    r = await klien.get("/api/notifications", headers=siap["hf"])
    n = next(x for x in r.json() if x.get("type") == AJU and x.get("action_id") == req_id)
    assert n.get("resolved_at") and n.get("read") is True, "aksi tidak lagi ditawarkan"
    assert all(x.get("resolved_at") for x in await _notif(db, AJU, req_id))


async def test_BTP2_barang_disiapkan_jadi_permintaan(klien, db, siap):
    from services import so_cancel_service as scs
    so = await _pesanan(klien, db, siap)
    await db.inventory_rolls.insert_one({"id": _id("roll"), "reserved_ref": {"id": so["id"], "type": "sales_order"},
                                         "status": "picked", "product_id": _id("prd"), "warehouse_id": "wh_uji",
                                         "owner_entity_id": KSC, "quantity": 10.0, "unit": "meter"})
    r = await klien.get(f"/api/sales-orders/{so['id']}/cancel-check", headers=siap["hs"], params={"action": "cancel"})
    assert r.status_code == 200, r.text
    assert r.json() == {"needs_approval": True, "basis": ["prepared"], "can_self_approve": False,
                        "amount": 1_000_000.0}
    r = await klien.get(f"/api/sales-orders/{so['id']}/cancel-check", headers=siap["hm"], params={"action": "cancel"})
    assert r.json()["can_self_approve"] is True
    r = await klien.get(f"/api/sales-orders/{so['id']}/cancel-check", headers=siap["hs"], params={"action": "hapus"})
    assert r.status_code == 400, r.text
    r = await _batal(klien, siap["hs"], so)
    assert r.status_code == 202, r.text
    assert r.json()["request"]["approval_basis"] == ["prepared"]

    # Tugas ambil yang sudah mencatat ambil / sudah dikemas juga "disiapkan"; tugas baru belum.
    lain = {"id": _id("so"), "entity_id": KSC}
    tugas = {"id": _id("wt"), "order_id": lain["id"], "flow_type": "outbound", "status": "created", "picked_qty": 0}
    await db.wms_tasks.insert_one(dict(tugas))
    assert await scs.prepared_basis(lain) is False
    await db.wms_tasks.update_one({"id": tugas["id"]}, {"$set": {"status": "packing"}})
    assert await scs.prepared_basis(lain) is True
    await db.wms_tasks.update_one({"id": tugas["id"]}, {"$set": {"status": "picking", "picked_qty": 4.0}})
    assert await scs.prepared_basis(lain) is True
    await db.wms_tasks.update_one({"id": tugas["id"]}, {"$set": {"status": "dispatched"}})
    assert await scs.prepared_basis(lain) is False
    # Roll yang sudah berangkat bukan "disiapkan" untuk bagian sisa (tutup sisa), tetapi tetap untuk batal penuh.
    await db.inventory_rolls.insert_one({"id": _id("roll"), "reserved_ref": {"id": lain["id"]},
                                         "status": "in_transit_sales", "product_id": _id("prd"),
                                         "warehouse_id": "wh_uji", "owner_entity_id": KSC, "quantity": 5.0})
    assert await scs.prepared_basis(lain, remaining_only=True) is False
    assert await scs.prepared_basis(lain) is True


async def test_BTP2_izin_baku(klien, db, siap, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong):
    peran = await peran_tanpa_acuan({"order": ["view", "approve_cancel"]})
    h = await sesi(await akun(peran))
    r = await klien.get("/api/sales-orders/cancel-requests", headers=h, params={"status": "pending"})
    assert r.status_code == 200, r.text
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    assert (await _batal(klien, siap["hs"], so)).status_code == 202
    h0 = await sesi(await akun(await peran_manajer_kosong()))
    for cara, url, isi in (
            ("get", "/api/sales-orders/cancel-requests", None),
            ("get", f"/api/sales-orders/{so['id']}/cancel-check", None),
            ("post", f"/api/sales-orders/{so['id']}/cancel", {"reason": "uji manajer kosong"}),
            ("post", f"/api/sales-orders/{so['id']}/cancel-request/decision", {"decision": "approve", "note": ""}),
            ("post", f"/api/sales-orders/{so['id']}/cancel-request/withdraw", None)):
        r = await (klien.get(url, headers=h0) if cara == "get" else klien.post(url, headers=h0, json=isi))
        assert r.status_code == 403, (url, r.status_code, r.text)
    # Peran tanpa acuan yang hanya memegang izin setujui pembatalan boleh memutus.
    r = await _putus(klien, h, so, "approve")
    assert r.status_code == 200, r.text
    assert (await _so(db, so))["status"] == "cancelled"


# ── Temuan tinjauan BTP-2 (jalur galat, notifikasi, cakupan uji) ──────────────────────────────────────────────────────
def _eksekutor(monkeypatch, perilaku):
    """Ganti eksekutor batal dengan pembungkus; `perilaku(asli, order_id, actor, reason, request_id)` boleh melempar."""
    from services import so_cancel_service as scs
    asli = scs.EXECUTORS["cancel"]

    async def _ganti(order_id, actor, reason, request_id=""):
        return await perilaku(asli, order_id, actor, reason, request_id)
    monkeypatch.setitem(scs.EXECUTORS, "cancel", _ganti)


async def test_BTP2_galat_sesudah_batal_tetap_menutup_notifikasi_dan_audit(klien, db, siap, monkeypatch):
    async def _batal_lalu_galat(asli, order_id, actor, reason, request_id):
        await asli(order_id, actor, reason, request_id=request_id)
        raise RuntimeError("uji: galat sesudah transisi")
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    r = await _batal(klien, siap["hs"], so)
    assert r.status_code == 202, r.text
    req_id = r.json()["request"]["id"]
    _eksekutor(monkeypatch, _batal_lalu_galat)
    r = await _putus(klien, siap["hf"], so, "approve")
    assert r.status_code >= 500, r.text
    o = await _so(db, so)
    assert o["status"] == "cancelled" and "cancel_request" not in o
    assert o["cancel_requests"][-1]["status"] == "approved" and o["cancel_requests"][-1]["id"] == req_id
    rows = await _notif(db, AJU, req_id)
    assert rows and all(n.get("resolved_at") for n in rows), "notifikasi 'menunggu persetujuan' ditutup"
    assert await db.audit_logs.find_one({"action": "so_cancel_request_approved", "entity_id": so["id"]}), \
        "putusan tetap diaudit"
    assert await _notif(db, PUTUS, o["cancel_requests"][-1]["id"]), "pengaju diberi tahu putusannya"


async def test_BTP2_dibatalkan_jalur_lain_sesudah_mulai_bukan_persetujuan(klien, db, siap, monkeypatch):
    """Heuristik waktu lama menganggap pesanan yang dibatalkan jalur lain SESUDAH eksekusi dimulai sebagai hasil
    eksekusi ini. Penandanya kini id permintaan yang ditulis eksekutor."""
    async def _jalur_lain(asli, order_id, actor, reason, request_id):
        await db.sales_orders.update_one({"id": order_id}, {"$set": {"status": "cancelled",
                                                                     "cancelled_at": now_iso()}})
        raise RuntimeError("uji: bentrok dengan jalur lain")
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    assert (await _batal(klien, siap["hs"], so)).status_code == 202
    _eksekutor(monkeypatch, _jalur_lain)
    r = await _putus(klien, siap["hf"], so, "approve")
    assert r.status_code == 409, r.text
    o = await _so(db, so)
    assert "cancel_request" not in o and o["cancel_requests"][-1]["status"] == "void"


async def test_BTP2_galat_eksekusi_pesan_manusia(klien, db, siap, monkeypatch):
    async def _galat(asli, order_id, actor, reason, request_id):
        raise RuntimeError("Traceback rahasia internal XYZ")
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    assert (await _batal(klien, siap["hs"], so)).status_code == 202
    _eksekutor(monkeypatch, _galat)
    r = await _putus(klien, siap["hf"], so, "approve")
    assert r.status_code == 409, r.text
    assert "XYZ" not in _teks(r) and "Pembatalan belum bisa dijalankan — coba lagi atau hubungi Admin." in _teks(r)
    o = await _so(db, so)
    assert o["cancel_request"]["status"] == "pending" and "deciding" not in o["cancel_request"], \
        "tetap menunggu, penanda proses dilepas"


async def test_BTP2_kode_galat_asli_diteruskan(klien, db, siap, monkeypatch):
    from fastapi import HTTPException

    async def _forbidden(asli, order_id, actor, reason, request_id):
        raise HTTPException(status_code=403, detail="Tidak berwenang atas gudang ini")
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    assert (await _batal(klien, siap["hs"], so)).status_code == 202
    _eksekutor(monkeypatch, _forbidden)
    r = await _putus(klien, siap["hf"], so, "approve")
    assert r.status_code == 403, r.text
    assert "Tidak berwenang atas gudang ini" in _teks(r)
    assert (await _so(db, so))["cancel_request"]["status"] == "pending"


async def test_BTP2_notifikasi_tidak_sampai_ke_yang_tak_boleh_memutus(klien, db, siap, akun, sesi, peran_tanpa_acuan):
    """Sales pesanan yang memegang `order.approve_cancel` lewat peran kustom tidak boleh memutus (403) — lonceng tidak
    boleh menawarkan tombol yang pasti gagal."""
    peran = await peran_tanpa_acuan({"order": ["view", "approve_cancel", "cancel"]})
    u = await akun(peran)
    so = await _pesanan(klien, db, siap, bayar=1_000_000, sales_id=u["id"], sales_name=u["name"])
    r = await _batal(klien, await sesi(u), so)
    assert r.status_code == 202, r.text
    req_id = r.json()["request"]["id"]
    rows = [n for n in await _notif(db, AJU, req_id) if n.get("recipient_user") == u["id"]]
    assert all(n.get("resolved_at") for n in rows), "tombol yang pasti 403 tidak ditawarkan"
    lain = [n for n in await _notif(db, AJU, req_id) if n.get("recipient_user") == siap["fin"]["id"]]
    assert lain and not any(n.get("resolved_at") for n in lain), "penyetuju lain tetap menerima"


async def test_BTP2_void_batal_sample_gagal_tidak_menggagalkan(klien, db, siap, monkeypatch):
    from services import so_cancel_service as scs

    async def _rusak(*a, **k):
        raise RuntimeError("uji: void gagal")
    monkeypatch.setattr(scs, "void_pending", _rusak)
    so = await _pesanan(klien, db, siap, status="waiting_approval", order_type="sample")
    r = await klien.post(f"/api/sample-orders/{so['id']}/cancel", headers=siap["h"], json={"note": "salah input"})
    assert r.status_code == 200, r.text
    assert (await _so(db, so))["status"] == "cancelled"


# ── Cakupan "sales pesanan" & kegagalan eksekusi ─────────────────────────────────────────────────────────────────────
async def test_BTP2_created_by_bukan_sales_pesanan(klien, db, siap):
    """Manager yang menginput atas nama sales (`created_by`) tetap boleh memutus: disetujui sendiri (200)."""
    so = await _pesanan(klien, db, siap, bayar=1_000_000, created_by=siap["mgr"]["id"])
    r = await _batal(klien, siap["hm"], so)
    assert r.status_code == 200, r.text
    assert (await _so(db, so))["cancel_requests"][-1]["self_approved"] is True


async def test_BTP2_cakupan_tim_bukan_sales_pesanan(klien, db, siap, akun):
    """Supervisor yang cakupannya meliputi sales pesanan (bukan `sales_id`/`sales_team`) bukan sales pesanan itu."""
    from services import so_cancel_service as scs
    spv = await akun("manager")
    spv = {**spv, "supervisor_of": [siap["sales"]["id"]], "team_ids": [siap["sales"]["id"]]}
    so = {"sales_id": siap["sales"]["id"], "sales_team": [{"sales_id": "usr_lain"}], "created_by": spv["id"]}
    assert scs.is_order_sales(so, spv) is False
    assert scs.is_order_sales(so, {"id": siap["sales"]["id"]}) is True
    assert scs.is_order_sales(so, {"id": "usr_lain"}) is True


async def test_BTP2_galat_non_http_permintaan_tetap_menunggu(klien, db, siap, monkeypatch):
    async def _galat(asli, order_id, actor, reason, request_id):
        raise ValueError("uji: galat non-HTTP")
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    assert (await _batal(klien, siap["hs"], so)).status_code == 202
    _eksekutor(monkeypatch, _galat)
    r = await _putus(klien, siap["hf"], so, "approve")
    assert r.status_code == 409, r.text
    o = await _so(db, so)
    assert o["status"] == "confirmed" and o["cancel_request"]["status"] == "pending"
    assert "deciding" not in o["cancel_request"]
    monkeypatch.undo()
    assert (await _putus(klien, siap["hf"], so, "approve")).status_code == 200, "bisa diulang sesudah pulih"


async def test_BTP2_disetujui_sendiri_gagal_tidak_meninggalkan_permintaan(klien, db, siap, monkeypatch):
    async def _galat(asli, order_id, actor, reason, request_id):
        raise ValueError("uji: galat non-HTTP")
    so = await _pesanan(klien, db, siap, bayar=1_000_000)
    _eksekutor(monkeypatch, _galat)
    r = await _batal(klien, siap["hm"], so)
    assert r.status_code >= 400, r.text
    o = await _so(db, so)
    assert o["status"] == "confirmed" and not o.get("cancel_request"), "tidak ada permintaan setengah jadi"
