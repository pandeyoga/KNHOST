"""CR-T3 serah-terima (b) — empat titik periksa terpasang, `credit_gate_rejections`, "Tahan kredit", tahan-kirim tunai,
pratinjau & pembungkus dialihkan (U1, U2, U4, U5, U7–U10, U12–U14 lewat HTTP; `docs/blueprint/unit/CR-T3.md`).

Alur lewat API: pesanan (`POST /api/sales-orders`), override (`POST /api/sales-orders/{id}/override`), verifikasi →
setujui → konfirmasi (`/verify`, `/approve`, `/confirm`), kwitansi (`POST /api/ar-receipts`), izin kredit, pratinjau
(`GET /api/customers/{id}/credit-status`), periksa ulang (`POST /api/sales-orders/{id}/credit-recheck`).
FIXTURE SISIP: G1 tanpa O2 (`pembantu_crt3.g1(terbuka=None)`) — O2 = pesanan S dibuat lewat API Rp 2.000.000
(100 m × Rp 20.000, PT non-PKP `ent_kanda`); produk, gudang, roll; pesanan CASH untuk U14.
"""
from __future__ import annotations

import pytest

from core_utils import now_iso
from pembantu_crt3 import JUTA, KANDA, KSC, atur, cabut, g1, kode, uid

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module")
async def siap(akun, sesi, db):
    sls = await akun("sales", entitas=(KANDA, KSC))
    mgr = await akun("manager", entitas=(KANDA, KSC))
    adm = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    prd = {}
    for ent in (KANDA, KSC):
        prd[ent] = uid("prd")
        await db.products.insert_one({"id": prd[ent], "sku": f"CRT3-{ent}", "name": f"Kain CR-T3 {ent}", "price": 20000,
                                      "base_unit": "meter", "status": "active", "lifecycle": "produksi", "category": "uji"})
        await db.warehouses.insert_one({"id": f"wh_crt3_{ent}", "name": f"Gudang CR-T3 {ent}", "entity_id": ent,
                                        "city": "Bandung"})
    return {"sls": sls, "h_sls": await sesi(sls, entitas=KANDA), "h_mgr": await sesi(mgr, entitas=KANDA),
            "h_adm": await sesi(adm, entitas=KANDA), "h_adm_ksc": await sesi(adm, entitas=KSC), "prd": prd}


async def _produk(db, ent=KANDA) -> str:
    pid = uid("prd")
    await db.products.insert_one({"id": pid, "sku": f"CRT3-{pid[-8:]}", "name": f"Kain CR-T3 {pid[-4:]}", "price": 20000,
                                  "base_unit": "meter", "status": "active", "lifecycle": "produksi", "category": "uji"})
    return pid


async def _roll(db, siap, ent=KANDA, panjang=400.0, pid=""):
    await db.inventory_rolls.insert_one({
        "id": uid("roll"), "roll_no": f"R-{uid('n')}", "product_id": pid or siap["prd"][ent], "owner_entity_id": ent,
        "warehouse_id": f"wh_crt3_{ent}", "status": "available", "active_movement": None, "length_remaining": panjang,
        "lot": "L-CRT3", "created_at": now_iso()})


async def _pesan(klien, db, siap, f, meter, *, term="NET30", h=None, ent=KANDA):
    # produk baru + roll SEPANJANG pesanan (satu roll utuh): database tiruan tidak mendukung `array_filters` reservasi
    # sebagian roll, dan roll sisa uji lain tidak boleh terpilih FEFO
    pid = await _produk(db, ent)
    await _roll(db, siap, ent, panjang=float(meter), pid=pid)
    return await klien.post("/api/sales-orders", headers=h or siap["h_sls"], json={
        "customer_id": f["cid"], "shipping_address_id": f["adr"], "entity_id": ent, "payment_term_code": term,
        "items": [{"product_id": pid, "quantity": meter, "unit": "meter"}]})


async def _g1(klien, db, siap, s_term="NET30", **kw):
    """G1 lengkap: O2 = pesanan S Rp 2.000.000 lewat API (dibuat sebelum eksposur mendekati plafon: 5,5 + 2 = 7,5 jt)."""
    f = await g1(db, terbuka=None, sales_id=siap["sls"]["id"], **kw)
    r = await _pesan(klien, db, siap, f, 100, term=s_term)
    assert r.status_code == 200, r.text
    f["S"] = r.json()
    assert f["S"]["grand_total"] == 2 * JUTA
    return f


async def _izin(klien, siap, cid, jumlah, **lain):
    r = await klien.post(f"/api/customers/{cid}/credit-override", headers=siap["h_sls"],
                         json={"amount": jumlah, "scope": "pelanggan", "reason_code": "cr_riwayat_baik", **lain})
    assert r.status_code == 200, r.text
    d = await klien.post(f"/api/credit-overrides/{r.json()['id']}/decision", headers=siap["h_mgr"],
                         json={"decision": "approve", "reason": "uji CR-T3"})
    assert d.status_code == 200, d.text
    return d.json()


# ── U1 — 200; peringatan; potret di pesanan ─────────────────────────────────────────────────────────────────────────
async def test_CRT3_U1_http_peringatan(klien, db, siap):
    f = await _g1(klien, db, siap)
    r = await klien.get(f"/api/customers/{f['cid']}/credit-status", headers=siap["h_sls"],
                        params={"amount": 2 * JUTA, "term_code": "NET30", "entity_id": KANDA})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["gate"]["result"] == "peringatan" and kode(j["gate"]) == ["MENDEKATI_PLAFON"]
    assert (j["level"], j["blocked"]) == ("warning", False) and j["projected_ar"] == 9_500_000   # field lama tetap
    assert j["reasons"] == ["Eksposur sudah 95 % dari plafon."]
    r = await _pesan(klien, db, siap, f, 100)
    assert r.status_code == 200, r.text
    so = r.json()
    assert so["credit_warning"] is True and so["credit_hold"] is False and so["pay_before_ship"] is False
    assert so["credit_gate_at_order"]["result"] == "peringatan"
    assert so["credit_gate_at_order"]["exposure"]["total"] == 9_500_000


# ── U2 — 409 CREDIT_BLOCKED + satu penolakan, tanpa pesanan ─────────────────────────────────────────────────────────
async def test_CRT3_U2_http_tolak_satu_penolakan(klien, db, siap):
    f = await _g1(klien, db, siap)
    n = await db.sales_orders.count_documents({"customer_id": f["cid"]})
    r = await _pesan(klien, db, siap, f, 150)   # 150 m × 20.000 = 3.000.000 → 10.500.000 > 10.000.000
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d["code"] == "CREDIT_BLOCKED" and [x["code"] for x in d["reasons"]] == ["LEWAT_PLAFON"]
    assert d["reasons"][0]["message"] == "Eksposur Rp 10.500.000 melewati plafon Rp 10.000.000."
    assert await db.sales_orders.count_documents({"customer_id": f["cid"]}) == n
    rej = [x async for x in db.credit_gate_rejections.find({"customer_id": f["cid"]}, {"_id": 0})]
    assert len(rej) == 1 and rej[0]["id"] == d["rejection_id"] and rej[0]["amount"] == 3 * JUTA
    assert (rej[0]["status"], rej[0]["entity_id"], rej[0]["exposure"]["total"]) == ("terbuka", KANDA, 10_500_000)
    assert rej[0]["payload_snapshot"]["items"][0]["quantity"] == 150
    # daftar & rincian (pembuatnya sendiri boleh; rincian memuat isi permintaan)
    r = await klien.get("/api/credit-gate-rejections", headers=siap["h_sls"], params={"customer_id": f["cid"]})
    assert r.status_code == 200 and r.json()["total"] == 1 and "payload_snapshot" not in r.json()["items"][0]
    r = await klien.get(f"/api/credit-gate-rejections/{d['rejection_id']}", headers=siap["h_sls"])
    assert r.status_code == 200 and r.json()["payload_snapshot"]["customer_id"] == f["cid"]


# ── U4 / U5 — izin pelanggan dipakai pesanan; izin kedaluwarsa → 409 ────────────────────────────────────────────────
async def test_CRT3_U4_http_izin_dipakai_pesanan(klien, db, siap):
    f = await _g1(klien, db, siap)
    await atur("ar.izin_kredit_masa_berlaku_hari", 3, KANDA)
    try:
        izin = await _izin(klien, siap, f["cid"], 3 * JUTA)
    finally:
        await cabut("ar.izin_kredit_masa_berlaku_hari", KANDA)
    assert izin["valid_until"]
    rej = await db.credit_gate_rejections.count_documents({"customer_id": f["cid"]})
    r = await _pesan(klien, db, siap, f, 150)
    assert r.status_code == 200, r.text
    so = r.json()
    assert so["credit_override_id"] == izin["id"]
    assert so["credit_override_used"]["amount"] == 3 * JUTA
    d = await db.credit_overrides.find_one({"id": izin["id"]})
    assert d["remaining_amount"] == 0 and len(d["used_by"]) == 1 and d["used_by"][0]["order_id"] == so["id"]
    assert d["used_by"][0]["order_number"] == so["number"]
    assert await db.credit_gate_rejections.count_documents({"customer_id": f["cid"]}) == rej
    # izin habis: pesanan berikutnya ditolak lagi
    r = await _pesan(klien, db, siap, f, 10)
    assert r.status_code == 409, r.text


async def test_CRT3_U5_http_izin_kedaluwarsa(klien, db, siap):
    from datetime import datetime, timedelta, timezone
    f = await _g1(klien, db, siap)
    izin = await _izin(klien, siap, f["cid"], 3 * JUTA)
    await db.credit_overrides.update_one({"id": izin["id"]}, {"$set": {   # FIXTURE: digeser ke kemarin
        "valid_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}})
    r = await _pesan(klien, db, siap, f, 150)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "CREDIT_BLOCKED", r.text
    assert (await db.credit_overrides.find_one({"id": izin["id"]}))["remaining_amount"] == 3 * JUTA


# ── U7 / U8 — override menaikkan nilai: tahan bila titik menyala, tidak bila bawaan ─────────────────────────────────
async def _naikkan(klien, siap, so, meter, db=None):
    item = so["items"][0]
    if db is not None:   # roll utuh untuk tambahan panjang (lihat `_pesan`)
        await _roll(db, siap, KANDA, panjang=float(meter - item["quantity"]), pid=item["product_id"])
    return await klien.post(f"/api/sales-orders/{so['id']}/override", headers=siap["h_adm"], json={
        "lines": [{"product_id": item["product_id"], "quantity": meter}], "note": "uji CR-T3 naik nilai"})


async def test_CRT3_U7_U9_U10_tahan_lepas(klien, db, siap):
    f = await _g1(klien, db, siap)
    await atur("ar.periksa_kredit_pesanan_diubah", True, KANDA)
    try:
        r = await _naikkan(klien, siap, f["S"], 250, db)   # 250 m × 20.000 = 5.000.000
    finally:
        await cabut("ar.periksa_kredit_pesanan_diubah", KANDA)
    assert r.status_code == 200, r.text
    so = await db.sales_orders.find_one({"id": f["S"]["id"]}, {"_id": 0})
    # 6.000.000 + 5.000.000 − 500.000 = 10.500.000 > 10.000.000 → Tahan kredit; nilai baru tetap tersimpan
    assert so["grand_total"] == 5 * JUTA and so["credit_hold"] is True
    assert [x["code"] for x in so["credit_hold_info"]["reasons"]] == ["LEWAT_PLAFON"]
    assert so["credit_hold_info"]["checkpoint"] == "pesanan_diubah"
    assert so["sub_status"][0] == "tahan_kredit"
    from services.so_status import SUBSTATUS_LABELS
    assert SUBSTATUS_LABELS["tahan_kredit"] == "Tahan kredit"
    # U9 — lepas ke gudang ditolak walau titik `lepas_gudang` mati; status tidak berubah
    h = siap["h_adm"]
    assert (await klien.post(f"/api/sales-orders/{so['id']}/verify", headers=h, json={"note": "uji CR-T3"})).status_code == 200
    r = await klien.post(f"/api/sales-orders/{so['id']}/approve", headers=h)
    assert r.status_code == 200, r.text
    status = (await db.sales_orders.find_one({"id": so["id"]}))["status"]
    r = await klien.post(f"/api/sales-orders/{so['id']}/confirm", headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith(f"Pesanan {so['number']} ditahan kredit — Eksposur Rp 10.500.000 melewati")
    assert r.json()["detail"].endswith("Ajukan izin kredit atau catat pembayaran dulu.")
    assert (await db.sales_orders.find_one({"id": so["id"]}))["status"] == status
    # periksa ulang manual: masih tahan
    r = await klien.post(f"/api/sales-orders/{so['id']}/credit-recheck", headers=h)
    assert r.status_code == 200 and r.json()["released"] is False and r.json()["result"] == "tahan", r.text
    # U10 — kwitansi Rp 1.000.000 untuk tagihan terkirim (O1) → 5 + 5 − 0,5 = 9,5 jt ≤ 10 jt → dilepas sendiri
    await db.bank_accounts.insert_one({"id": uid("rek"), "name": "BCA Kanda CR-T3", "entity_id": KANDA,
                                       "account_type": "bank", "cash_type": "kas_besar", "is_active": True,
                                       "opening_balance": 0})
    rek = (await db.bank_accounts.find_one({"name": "BCA Kanda CR-T3"}))["id"]
    r = await klien.post("/api/ar-receipts", headers=h, json={
        "customer_id": f["cid"], "amount": JUTA, "method": "transfer", "entity_id": KANDA, "account_id": rek,
        "allocations": [{"order_id": f["o1"], "amount": JUTA}]})
    assert r.status_code == 200, r.text
    so = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert so["credit_hold"] is False and so["credit_hold_info"] is None
    assert len(so["credit_hold_history"]) == 1 and so["credit_hold_history"][0]["checkpoint"] == "pesanan_diubah"
    assert "tahan_kredit" not in so["sub_status"]
    r = await klien.post(f"/api/sales-orders/{so['id']}/confirm", headers=h)
    assert r.status_code == 200, r.text


async def test_CRT3_U8_kunci_bawaan_tidak_menahan(klien, db, siap):
    f = await _g1(klien, db, siap)
    r = await _naikkan(klien, siap, f["S"], 250, db)
    assert r.status_code == 200, r.text
    so = await db.sales_orders.find_one({"id": f["S"]["id"]}, {"_id": 0})
    assert so["grand_total"] == 5 * JUTA and so["credit_hold"] is False


async def test_CRT3_ganti_termin_di_luar_daftar_ditolak(klien, db, siap):
    f = await _g1(klien, db, siap, allowed_term_codes=["NET30", "NET14"])
    await atur("ar.periksa_kredit_pesanan_diubah", True, KANDA)
    try:
        r = await klien.post(f"/api/sales-orders/{f['S']['id']}/override", headers=siap["h_adm"], json={
            "header": {"payment_term_code": "NET60"}, "note": "uji CR-T3 termin"})
    finally:
        await cabut("ar.periksa_kredit_pesanan_diubah", KANDA)
    assert r.status_code == 400, r.text
    assert "tidak diizinkan untuk pelanggan ini" in r.json()["detail"]
    assert (await db.sales_orders.find_one({"id": f["S"]["id"]}))["payment_term_code"] == "NET30"


# ── U12 / U13 — termin ditolak 400; telat: CBD lolos bayar dulu, kirim tertahan bayar; NET30 409 ──────────────────
async def test_CRT3_U12_http_termin(klien, db, siap):
    f = await _g1(klien, db, siap, s_term="NET14", allowed_term_codes=["CASH", "NET14"])
    r = await _pesan(klien, db, siap, f, 50)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "TERM_NOT_ALLOWED", r.text
    assert r.json()["detail"]["message"].startswith("Termin Kredit NET 30 Hari tidak diizinkan")
    r = await _pesan(klien, db, siap, f, 50, term="NET14")
    assert r.status_code == 200, r.text


async def test_CRT3_U13_http_telat(klien, db, siap):
    from services import loading_check_service as lcs
    from fastapi import HTTPException
    f = await g1(db, telat=20, terbuka=None, sales_id=siap["sls"]["id"])
    r = await _pesan(klien, db, siap, f, 50, term="CBD")
    assert r.status_code == 200, r.text
    so = r.json()
    assert so["pay_before_ship"] is True and so["credit_hold"] is False
    with pytest.raises(HTTPException) as e:
        await lcs.dispatch_guard(so["id"])
    assert e.value.status_code == 409 and e.value.detail.startswith("Tertahan pembayaran: termin CBD")
    r = await _pesan(klien, db, siap, f, 50, term="NET30")
    assert r.status_code == 409 and [x["code"] for x in r.json()["detail"]["reasons"]] == ["TELAT"], r.text


# ── U14 — tahan-kirim tunai per PT ───────────────────────────────────────────────────────────────────────────────────
async def test_CRT3_U14_tahan_kirim_tunai(db):
    from fastapi import HTTPException
    from services import dispatch_payment_gate as dpg
    from services import loading_check_service as lcs
    oid = {}
    for ent in (KANDA, KSC):
        oid[ent] = uid("so")
        await db.sales_orders.insert_one({
            "id": oid[ent], "number": f"SO-{oid[ent]}", "customer_id": uid("cus"), "entity_id": ent, "status": "picked",
            "payment_status": "unpaid", "grand_total": JUTA, "total_amount": JUTA, "paid_total": 0, "payments": [],
            "payment_term_code": "CASH", "payment_term_name": "Tunai / POS", "items": [], "created_at": now_iso()})
    assert (await dpg.evaluate(await db.sales_orders.find_one({"id": oid[KANDA]}, dpg.PROJ)))["applies"] is False
    await atur("finance.tahan_kirim_tunai", True, KANDA)
    try:
        with pytest.raises(HTTPException) as e:
            await lcs.dispatch_guard(oid[KANDA])
        assert e.value.status_code == 409 and "kurang Rp 1.000.000" in e.value.detail, e.value.detail
        await lcs.dispatch_guard(oid[KSC])                       # PT lain tidak ikut
    finally:
        await cabut("finance.tahan_kirim_tunai", KANDA)
    await lcs.dispatch_guard(oid[KANDA])                         # kunci dicabut → lolos lagi


async def test_CRT3_tunai_ditahan_ikut_piutang_dan_telat(db):
    """`finance.tahan_kirim_tunai` menyala → tagihan tunai terkirim ikut eksposur dan telat (pengecualian CR-T2 dicabut)."""
    from services import credit_gate as cg
    from pembantu_crt3 import pesanan_terkirim
    f = await g1(db, terkirim=0, terbuka=None, titipan=0)
    await pesanan_terkirim(db, f["cid"], KANDA, 3 * JUTA, telat=20, term="CASH")
    h = await cg.evaluate(customer_id=f["cid"], entity_id=KANDA, checkpoint="pesanan_dibuat", order_amount=0)
    assert h["exposure"]["ar_delivered"] == 0 and h["result"] == "lolos"      # bawaan: tunai dilewati (CR-T2)
    await atur("finance.tahan_kirim_tunai", True, KANDA)
    try:
        h = await cg.evaluate(customer_id=f["cid"], entity_id=KANDA, checkpoint="pesanan_dibuat", order_amount=0)
    finally:
        await cabut("finance.tahan_kirim_tunai", KANDA)
    assert h["exposure"]["ar_delivered"] == 3 * JUTA and h["overdue"]["days"] == 20 and "TELAT" in kode(h)


# ── titik lepas_gudang & surat_jalan menyala ─────────────────────────────────────────────────────────────────────────
async def test_CRT3_titik_lepas_gudang_menahan(klien, db, siap):
    f = await g1(db, telat=20, terbuka=None, sales_id=siap["sls"]["id"])
    await db.customer_credit_profiles.update_one({"customer_id": f["cid"]}, {"$set": {"overdue_block_days": 30}})
    r = await _pesan(klien, db, siap, f, 50)   # telat 20 ≤ 30 → peringatan, pesanan lahir
    assert r.status_code == 200, r.text
    so = r.json()
    await db.customer_credit_profiles.update_one({"customer_id": f["cid"]}, {"$set": {"overdue_block_days": None}})
    h = siap["h_adm"]
    assert (await klien.post(f"/api/sales-orders/{so['id']}/verify", headers=h, json={"note": "uji"})).status_code == 200
    assert (await klien.post(f"/api/sales-orders/{so['id']}/approve", headers=h)).status_code == 200
    await atur("ar.periksa_kredit_lepas_gudang", True, KANDA)
    try:
        r = await klien.post(f"/api/sales-orders/{so['id']}/confirm", headers=h)
    finally:
        await cabut("ar.periksa_kredit_lepas_gudang", KANDA)
    assert r.status_code == 409 and "ditahan kredit" in r.json()["detail"], r.text
    d = await db.sales_orders.find_one({"id": so["id"]})
    assert d["credit_hold"] is True and d["credit_hold_info"]["checkpoint"] == "lepas_gudang"
    assert [x["code"] for x in d["credit_hold_info"]["reasons"]] == ["TELAT"]
    # izin lingkup pesanan disetujui → pesanan yang ditahan diperiksa ulang dan dilepas (izin dipakai)
    r = await klien.post(f"/api/customers/{f['cid']}/credit-override", headers=siap["h_sls"], json={
        "amount": 1 * JUTA, "scope": "pesanan", "order_id": so["id"], "reason_code": "cr_jaminan"})
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/credit-overrides/{r.json()['id']}/decision", headers=siap["h_mgr"],
                         json={"decision": "approve", "reason": "ada giro mundur"})
    assert r.status_code == 200, r.text
    d = await db.sales_orders.find_one({"id": so["id"]})
    assert d["credit_hold"] is False and d["credit_override_id"] == r.json()["id"]
    assert r.json()["remaining_amount"] == 0 and r.json()["used_by"][0]["order_id"] == so["id"]


async def test_CRT3_titik_surat_jalan_menahan(db):
    from fastapi import HTTPException
    from services import loading_check_service as lcs
    f = await g1(db, telat=20, terbuka=None)
    oid = uid("so")
    await db.sales_orders.insert_one({
        "id": oid, "number": f"SO-{oid}", "customer_id": f["cid"], "entity_id": KANDA, "status": "picked",
        "payment_status": "unpaid", "grand_total": JUTA, "total_amount": JUTA, "paid_total": 0, "payments": [],
        "payment_term_code": "NET30", "items": [], "created_at": now_iso()})
    await lcs.dispatch_guard(oid)                                   # titik bawaan mati → lolos
    await atur("ar.periksa_kredit_surat_jalan", True, KANDA)
    try:
        with pytest.raises(HTTPException) as e:
            await lcs.dispatch_guard(oid)
    finally:
        await cabut("ar.periksa_kredit_surat_jalan", KANDA)
    assert e.value.status_code == 409 and "ditahan kredit" in e.value.detail
    with pytest.raises(HTTPException):                              # tahanan tetap berlaku walau titik dimatikan
        await lcs.dispatch_guard(oid)


# ── pembungkus request-credit-approval ───────────────────────────────────────────────────────────────────────────────
async def test_CRT3_request_credit_approval_pembungkus(klien, db, siap, akun, sesi):
    f = await _g1(klien, db, siap)
    oid = f["S"]["id"]
    r = await klien.post(f"/api/sales-orders/{oid}/request-credit-approval", headers=siap["h_sls"],
                         json={"reason": "Pelanggan minta tambahan barang minggu ini"})
    assert r.status_code == 200, r.text
    so = r.json()
    entri = [p for p in so["pending_approvals"] if p["type"] == "kredit"]
    assert len(entri) == 1 and entri[0]["status"] == "pending"
    izin = await db.credit_overrides.find_one({"id": entri[0]["ref_id"]}, {"_id": 0})
    assert (izin["scope"], izin["order_id"], izin["amount"], izin["reason_code"], izin["has_so_entry"]) == \
        ("pesanan", oid, 2 * JUTA, "cr_lain", True)
    assert so["credit_hold"] is False                     # tanda "Tahan kredit" hanya dari gerbang kredit
    r = await klien.post(f"/api/sales-orders/{oid}/approvals/{entri[0]['id']}/decide", headers=siap["h_adm"],
                         json={"decision": "approve", "notes": "ok"})
    assert r.status_code == 200, r.text
    izin = await db.credit_overrides.find_one({"id": izin["id"]}, {"_id": 0})
    assert izin["status"] == "approved" and izin["remaining_amount"] == 2 * JUTA and izin["decided_at"]
    # tanpa izin `credit_override.create` → 403 (dulu `order.update`)
    sopir = await akun("driver", entitas=(KANDA,))
    r = await klien.post(f"/api/sales-orders/{oid}/request-credit-approval", headers=await sesi(sopir, entitas=KANDA),
                         json={"reason": "uji"})
    assert r.status_code == 403, r.text


async def test_CRT3_jalur_lama_dihapus():
    """D8 — `evaluate_credit_gate` dan `check_credit_for_order` tanpa pemanggil lalu dihapus."""
    import services.customer_service as cs
    assert not hasattr(cs, "evaluate_credit_gate") and not hasattr(cs, "check_credit_for_order")
