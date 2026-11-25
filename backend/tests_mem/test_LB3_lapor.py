"""Lapor Bayar CBD & DP · Tugas 3 — API lapor bayar: buat laporan, lampiran bukti, unduh, daftar per pesanan.

Pesanan disisipkan langsung (CBD 100 % = wajib Rp 1.000.000; NET30 = tidak wajib); aturan "menunggu bayar" tetap dari
`pay_hold_service.blocked` / `dispatch_payment_gate.evaluate` (tidak dihitung ulang di sini).

    cd backend && python -m pytest tests_mem/test_LB3_lapor.py -q -p no:cacheprovider -n 0
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
PDF = b"%PDF-1.4\n" + b"0" * (200 * 1024)
TGL = "2026-11-24"


def _id(awal: str) -> str:
    return f"{awal}_lb3_{uuid.uuid4().hex[:8]}"


async def _rekening(klien, h, entitas: str, nama: str) -> str:
    r = await klien.post("/api/bank-accounts", headers=h, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
        "payment_method_codes": ["transfer"], "name": nama, "account_number": f"9{uuid.uuid4().int % 10**8}",
        "holder_name": "PT Uji", "default_receiving_methods": ["transfer"], "show_on_documents": True,
        "entity_id": entitas})
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi):
    A = await _rekening(klien, kepala_admin, KSC, "BCA Lapor KSC")
    B = await _rekening(klien, kepala_admin, KANDA, "BCA Lapor KANDA")
    sales = await akun("sales")
    sales2 = await akun("sales")
    kanda = await akun("sales", entitas=(KANDA,))
    fin_kanda = await akun("finance", entitas=(KANDA,))
    fin_ksc = await akun("finance")
    return {
        "A": A, "B": B, "admin": kepala_admin, "sales": sales, "sales2": sales2,
        "h_sales": await sesi(sales), "h_sales2": await sesi(sales2),
        "h_kanda": await sesi(kanda, entitas=KANDA), "kanda": kanda,
        "fin_kanda": fin_kanda, "fin_ksc": fin_ksc,
    }


async def _pesanan(db, siap, *, term: str = "CBD", hold: bool = True, **lain) -> dict:
    oid = _id("so")
    so = {"id": oid, "number": f"SO-{oid[-6:]}", "entity_id": KSC, "status": "approved", "customer_id": "cus_x",
          "customer_name": "Toko LB-3", "payment_term_code": term, "grand_total": 1_000_000, "items": [],
          "payments": [], "created_by": siap["sales"]["id"], "sales_id": siap["sales"]["id"], **lain}
    if hold:
        so["pay_hold"] = {"since": "2026-11-24T00:00:00+00:00", "due_at": "2026-11-27T00:00:00+00:00",
                          "required": 1_000_000, "basis": "tercatat"}
    await db.sales_orders.insert_one(dict(so))
    return so


def _isi(siap, **lain) -> dict:
    return {"amount": 1_000_000, "transfer_date": TGL, "account_id": siap["A"], "method": "transfer",
            "reference_no": "TRF-001", "note": "uji", **lain}


async def _lapor(klien, siap, oid, h=None, **lain):
    return await klien.post(f"/api/sales-orders/{oid}/payment-reports", headers=h or siap["h_sales"],
                            json=_isi(siap, **lain))


# ── Buat laporan ─────────────────────────────────────────────────────────────────────────────────────────────────
async def test_buat_laporan_menunggu(klien, db, siap):
    so = await _pesanan(db, siap)
    r = await _lapor(klien, siap, so["id"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "menunggu" and j["order_id"] == so["id"] and j["entity_id"] == KSC
    assert j["number"].startswith("LB-") or "/LB-" in j["number"]
    assert j["amount"] == 1_000_000 and j["method"] == "transfer" and j["account_id"] == siap["A"]
    assert j["attachments"] == [] and j["attachment_count"] == 0
    assert j["created_by"] == siap["sales"]["id"]
    assert j["status_history"][0]["status"] == "menunggu" and j["status_history"][0]["user"]
    assert "_id" not in j and "idem_key" not in j
    tersimpan = await db.payment_reports.find_one({"id": j["id"]}, {"_id": 0})
    assert tersimpan["order_number"] == so["number"]


async def test_pesanan_tidak_menunggu_bayar_409(klien, db, siap):
    so = await _pesanan(db, siap, term="NET30", hold=False)
    r = await _lapor(klien, siap, so["id"])
    assert (r.status_code, r.json()["detail"]) == (409, "Pesanan ini tidak menunggu bayar"), r.text


async def test_kekurangan_tanpa_tahan_tetap_boleh_lapor(klien, db, siap):
    """DP sudah masuk tetapi pelunasan sebelum surat jalan belum: tanpa `pay_hold`, `shortfall > 0` cukup."""
    so = await _pesanan(db, siap, hold=False)
    r = await _lapor(klien, siap, so["id"], amount=500_000)
    assert r.status_code == 200, r.text


async def test_pesanan_mati_atau_tak_ada(klien, db, siap):
    so = await _pesanan(db, siap, status="cancelled")
    assert (await _lapor(klien, siap, so["id"])).status_code == 409
    assert (await _lapor(klien, siap, "tidak_ada")).status_code == 404


@pytest.mark.parametrize("nominal", [0, -5])
async def test_nominal_wajib_positif(klien, db, siap, nominal):
    so = await _pesanan(db, siap)
    assert (await _lapor(klien, siap, so["id"], amount=nominal)).status_code in (400, 422)


async def test_tanggal_tidak_sah_400(klien, db, siap):
    so = await _pesanan(db, siap)
    assert (await _lapor(klien, siap, so["id"], transfer_date="bukan-tanggal")).status_code == 400


async def test_rekening_pt_lain_atau_asing_400(klien, db, siap):
    so = await _pesanan(db, siap)
    for akun_id in (siap["B"], "rek_tidak_ada"):
        r = await _lapor(klien, siap, so["id"], account_id=akun_id)
        assert r.status_code == 400, r.text


async def test_cara_bayar_tunai_atau_asing_ditolak(klien, db, siap):
    so = await _pesanan(db, siap)
    assert (await _lapor(klien, siap, so["id"], method="cash")).status_code == 400
    assert (await _lapor(klien, siap, so["id"], method="tunai")).status_code == 400   # alias lama
    assert (await _lapor(klien, siap, so["id"], method="kartu_ajaib")).status_code == 400


async def test_laporan_kembar_menunggu_409(klien, db, siap):
    so = await _pesanan(db, siap)
    assert (await _lapor(klien, siap, so["id"])).status_code == 200
    r = await _lapor(klien, siap, so["id"], reference_no="TRF-LAIN")
    assert (r.status_code, r.json()["detail"]) == (409, "Laporan yang sama masih menunggu dicek"), r.text
    assert (await _lapor(klien, siap, so["id"], amount=900_000)).status_code == 200   # nominal beda = laporan lain
    # yang sudah diputus tidak lagi dianggap kembar
    await db.payment_reports.update_many({"order_id": so["id"]}, {"$set": {"status": "ditolak"}})
    assert (await _lapor(klien, siap, so["id"])).status_code == 200


async def test_izin_dan_pagar_pt_dan_pemilik(klien, db, siap, akun, sesi):
    so = await _pesanan(db, siap)
    # sales lain (bukan pemilik) → 403
    assert (await _lapor(klien, siap, so["id"], h=siap["h_sales2"])).status_code == 403
    # pengguna PT lain → 403
    assert (await _lapor(klien, siap, so["id"], h=siap["h_kanda"])).status_code == 403
    # tanpa izin `payment_report.create` → 403
    gudang = await akun("warehouse")
    assert (await _lapor(klien, siap, so["id"], h=await sesi(gudang))).status_code == 403
    assert await db.payment_reports.count_documents({"order_id": so["id"]}) == 0


async def test_buat_idempoten_satu_laporan(klien, db, siap):
    so = await _pesanan(db, siap)
    h = {**siap["h_sales"], "Idempotency-Key": _id("idem")}
    a = await klien.post(f"/api/sales-orders/{so['id']}/payment-reports", headers=h, json=_isi(siap))
    b = await klien.post(f"/api/sales-orders/{so['id']}/payment-reports", headers=h, json=_isi(siap))
    assert a.status_code == 200 and b.status_code == 200, (a.text, b.text)
    assert a.json()["id"] == b.json()["id"] and b.headers.get("X-Idempotent-Replay") == "true"
    assert await db.payment_reports.count_documents({"order_id": so["id"]}) == 1


# ── Notifikasi ───────────────────────────────────────────────────────────────────────────────────────────────────
async def test_notifikasi_hanya_pemegang_decide_di_pt_itu(klien, db, siap):
    so = await _pesanan(db, siap)
    r = await _lapor(klien, siap, so["id"])
    assert r.status_code == 200, r.text
    notif = await db.notifications.find({"type": "lapor_bayar_masuk", "ref": {"$regex": f"^{r.json()['id']}"}},
                                        {"_id": 0}).to_list(50)
    penerima = {n["recipient_user"] for n in notif}
    assert siap["fin_ksc"]["id"] in penerima
    assert siap["fin_kanda"]["id"] not in penerima          # finance PT lain tidak diberi tahu
    assert siap["sales"]["id"] not in penerima              # sales tidak memegang `decide`
    assert all(n["entity_id"] == KSC and not n.get("recipient_role") for n in notif)
    assert all(so["id"] in n["link"] for n in notif)
    assert all(n["ref"].count(r.json()["id"]) == 1 for n in notif)


# ── Lampiran ─────────────────────────────────────────────────────────────────────────────────────────────────────
async def _siap_laporan(klien, db, siap) -> tuple[dict, str]:
    so = await _pesanan(db, siap)
    r = await _lapor(klien, siap, so["id"])
    assert r.status_code == 200, r.text
    return so, r.json()["id"]


async def _unggah(klien, h, lid, nama="bukti.pdf", isi=PDF, tipe="application/pdf", extra=None):
    return await klien.post(f"/api/payment-reports/{lid}/attachments", headers={**h, **(extra or {})},
                            files={"file": (nama, isi, tipe)})


async def test_unggah_pdf_diterima_dan_masuk_laporan(klien, db, siap):
    so, lid = await _siap_laporan(klien, db, siap)
    r = await _unggah(klien, siap["h_sales"], lid)
    assert r.status_code == 200, r.text
    att = r.json()
    assert att["id"].startswith("att_") and att["original_filename"] == "bukti.pdf"
    assert att["content_type"] == "application/pdf" and att["size"] == len(PDF)
    assert att["uploaded_by"] and att["uploaded_at"] and "storage_path" not in att
    doc = await db.payment_reports.find_one({"id": lid}, {"_id": 0})
    assert len(doc["attachments"]) == 1 and doc["attachments"][0]["storage_path"].startswith("kn7/payment_reports")
    daftar = (await klien.get(f"/api/sales-orders/{so['id']}/payment-reports", headers=siap["h_sales"])).json()
    item = daftar["items"][0]
    assert item["attachment_count"] == 1 and "storage_path" not in item["attachments"][0]


async def test_unggah_exe_dan_terlalu_besar_ditolak(klien, db, siap):
    _, lid = await _siap_laporan(klien, db, siap)
    r = await _unggah(klien, siap["h_sales"], lid, nama="x.exe", isi=b"MZ\x90\x00" + b"0" * 100,
                      tipe="application/octet-stream")
    assert r.status_code == 400, r.text
    r = await _unggah(klien, siap["h_sales"], lid, isi=b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 1))
    assert r.status_code == 400, r.text
    assert (await db.payment_reports.find_one({"id": lid}))["attachments"] == []


async def test_unggah_pagar(klien, db, siap, akun, sesi):
    so, lid = await _siap_laporan(klien, db, siap)
    assert (await _unggah(klien, siap["h_sales2"], lid)).status_code == 403          # sales lain
    assert (await _unggah(klien, siap["h_kanda"], lid)).status_code == 403           # PT lain
    assert (await _unggah(klien, await sesi(await akun("warehouse")), lid)).status_code == 403   # tanpa izin
    assert (await _unggah(klien, siap["h_sales"], "lb_tidak_ada")).status_code == 404
    await db.payment_reports.update_one({"id": lid}, {"$set": {"status": "diterima"}})
    assert (await _unggah(klien, siap["h_sales"], lid)).status_code == 409           # sudah diputus


async def test_unduh_pemilik_boleh_lainnya_ditolak(klien, db, siap, akun, sesi):
    _, lid = await _siap_laporan(klien, db, siap)
    att = (await _unggah(klien, siap["h_sales"], lid)).json()
    url = f"/api/payment-reports/{lid}/attachments/{att['id']}"
    r = await klien.get(url, headers=siap["h_sales"])
    assert r.status_code == 200 and r.content == PDF
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.headers["content-disposition"].startswith("inline")
    assert (await klien.get(url, headers=siap["admin"])).status_code == 200             # Finance/admin boleh
    assert (await klien.get(url, headers=siap["h_sales2"])).status_code == 403          # sales lain
    assert (await klien.get(url, headers=siap["h_kanda"])).status_code == 403           # PT lain (Review Focus 4)
    assert (await klien.get(f"/api/payment-reports/{lid}/attachments/att_tidak_ada",
                            headers=siap["h_sales"])).status_code == 404


async def test_unggah_multipart_di_bawah_awalan_idempoten(klien, db, siap):
    """Unggah multipart ber-`Idempotency-Key` (awalan `/api/payment-reports`): kirim ulang = satu lampiran, balasan diputar."""
    _, lid = await _siap_laporan(klien, db, siap)
    extra = {"Idempotency-Key": _id("idem")}
    a = await _unggah(klien, siap["h_sales"], lid, extra=extra)
    b = await _unggah(klien, siap["h_sales"], lid, extra=extra)
    assert a.status_code == 200 and b.status_code == 200, (a.text, b.text)
    assert a.json()["id"] == b.json()["id"] and b.headers.get("X-Idempotent-Replay") == "true"
    assert len((await db.payment_reports.find_one({"id": lid}))["attachments"]) == 1


# ── Daftar per pesanan ───────────────────────────────────────────────────────────────────────────────────────────
async def test_daftar_pesanan_pt_lain_ditolak(klien, db, siap):
    so, _ = await _siap_laporan(klien, db, siap)
    r = await klien.get(f"/api/sales-orders/{so['id']}/payment-reports", headers=siap["h_kanda"])
    assert r.status_code in (403, 404)
    assert (await klien.get(f"/api/sales-orders/{so['id']}/payment-reports", headers=siap["h_sales2"])).status_code == 403


def test_awalan_idempoten_terdaftar():
    from idempotency import is_idempotent_path
    assert is_idempotent_path("/api/payment-reports/x/attachments")
    assert is_idempotent_path("/api/sales-orders/x/payment-reports")
