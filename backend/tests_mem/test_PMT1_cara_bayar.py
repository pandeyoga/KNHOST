"""PM-T1 — satu daftar induk cara bayar, dan rekening yang punya atas nama, peruntukan, dan bawaan per PT.

docs/blueprint/unit/PM-T1.md, uji penerimaan U1–U13 (lingkungan B). U14 (dua PATCH bersamaan, indeks unik) ditulis di
`backend/tests/test_bp_PMT1_bawaan_bersamaan.py` (lapis A). U15 = uji jalan layar.

Akun: `sls` (Sales, hanya `ent_ksc`), `mgr` (Manajer, `ent_ksc` + `ent_kanda`), `adm` (Admin seed). Pelanggan, pesanan,
dan rekening "lama" (U5, U11) = fixture (disisipkan langsung); master, kwitansi, rekening baru, perubahan rekening, dan
keputusan = alur lewat API.

Hitung tangan:
  U1  benih masuk & aktif: transfer (10) · cash (20) · giro (30) · qris (40) · deposit (70); va & edc nonaktif.
  U7  A bawaan transfer → PATCH B bawaan transfer → B mencabut tanda A: bawaan transfer = {B}.
  U11 PT uji: 1 bank + 2 kas tanpa field baru → bank satu-satunya → bawaan ["transfer"]; kas ada dua → [] keduanya.
"""
from __future__ import annotations

import itertools
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from core_utils import now_iso
from pembantu import pt_uji
from services import config_resolver as resolver

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
REPO = Path(__file__).resolve().parents[2]
MIN_ORANG = "kontrol.ubah_rekening.min_orang"
PESAN_DOKUMEN = "Rekening yang tampil di dokumen wajib punya atas nama dan nomor rekening."
PESAN_DIPUTUS = "Perubahan rekening ini sudah diputus atau datanya sudah berubah. Ajukan ulang."
_n = itertools.count(1)
SIMPAN: dict = {}


def _id(awal: str) -> str:
    return f"{awal}_pmt1_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def orang(akun, sesi, kepala_admin):
    sls = await akun("sales", entitas=(KSC,))
    mgr = await akun("manager", entitas=(KSC, KANDA))
    adm_kanda = await sesi("admin@kainnusantara.id", entitas=KANDA)
    return {"sls": sls, "mgr": mgr, "h_sls": await sesi(sls), "h_mgr": await sesi(mgr),
            "h_mgr_kanda": await sesi(mgr, entitas=KANDA), "h_adm": kepala_admin, "h_adm_kanda": adm_kanda}


async def _kode(klien, h, arah="masuk", entity_id=None):
    params = {"direction": arah}
    if entity_id:
        params["entity_id"] = entity_id
    r = await klien.get("/api/payment-methods", headers=h, params=params)
    assert r.status_code == 200, r.text
    return [x["code"] for x in r.json()]


# ── U1–U2: daftar induk ───────────────────────────────────────────────────────────────────────────────────────────
async def test_PMT1_U1_daftar_masuk_dari_master(klien, orang):
    r = await klien.get("/api/payment-methods", headers=orang["h_sls"], params={"direction": "masuk"})
    assert r.status_code == 200, r.text
    assert [x["code"] for x in r.json()] == ["transfer", "cash", "giro", "qris", "deposit"]
    assert set(r.json()[0]) >= {"code", "name", "needs_account", "needs_reference", "needs_due_date"}
    assert {x["code"]: x["name"] for x in r.json()}["qris"] == "QRIS"
    # arah keluar: QRIS/VA/EDC/titipan hanya penerimaan
    assert await _kode(klien, orang["h_sls"], "keluar") == ["transfer", "cash", "giro"]


async def test_PMT1_U2_matikan_qris_hanya_di_kanda(klien, orang):
    h = orang["h_adm_kanda"]
    r = await klien.get("/api/entity-masters/payment-methods", headers=h, params={"entity_id": KANDA})
    assert r.status_code == 200, r.text
    glob = next(x for x in r.json()["rows"] if x["code"] == "qris" and x["entity_scope"] == "global")
    r = await klien.post(f"/api/entity-masters/payment-methods/{glob['id']}/override", headers=h)
    assert r.status_code == 200, r.text
    r = await klien.patch(f"/api/entity-masters/payment-methods/{r.json()['id']}", headers=h,
                          json={"data": {"active": False}})
    assert r.status_code == 200, r.text
    assert "qris" not in await _kode(klien, orang["h_mgr_kanda"], entity_id=KANDA)
    assert "qris" in await _kode(klien, orang["h_mgr"], entity_id=KSC)


# ── U3–U4: kwitansi memakai kode kanonik ──────────────────────────────────────────────────────────────────────────
async def _pelanggan(db, ent=KSC):
    """Fixture: pelanggan + satu pesanan terbuka Rp 1.000.000 (belum dibayar)."""
    i = next(_n)
    cus, so = _id("cus"), _id("so")
    await db.customers.insert_one({"id": cus, "name": f"Toko PMT1 {i}", "entity_id": ent, "status": "active"})
    await db.sales_orders.insert_one({"id": so, "number": f"SO-PMT1-{i}", "entity_id": ent, "customer_id": cus,
                                      "customer_name": f"Toko PMT1 {i}", "status": "confirmed",
                                      "grand_total": 1_000_000, "payments": [], "paid_total": 0,
                                      "payment_status": "unpaid", "payment_term_code": "NET30",
                                      "created_at": now_iso()})
    return cus, so


async def _kwitansi(klien, h, cus, so, method, ent=KSC):
    return await klien.post("/api/ar-receipts", headers=h, json={
        "customer_id": cus, "amount": 100_000, "method": method, "entity_id": ent,
        "allocations": [{"order_id": so, "amount": 100_000}], "notes": "uji PM-T1"})


async def test_PMT1_U3_kwitansi_alias_disimpan_kanonik(klien, db, orang):
    # PK-20 — kas wajib berekening: fixture satu rekening Kas Kecil milik KSC (rekening tunggal → dipakai otomatis).
    if not await db.bank_accounts.find_one({"entity_id": KSC, "cash_type": "kas_kecil"}):
        await db.bank_accounts.insert_one({"id": _id("bank"), "name": "Kas Kecil KSC (uji)", "account_type": "cash",
                                           "cash_type": "kas_kecil", "entity_id": KSC, "is_active": True,
                                           "created_at": now_iso()})
    cus, so = await _pelanggan(db)
    for kata in ("tunai", "kontan"):
        r = await _kwitansi(klien, orang["h_mgr"], cus, so, kata)
        assert r.status_code == 200, r.text
        rc = await db.ar_receipts.find_one({"id": r.json()["id"]})
        assert rc["method"] == "cash", (kata, rc["method"])
        pay = [p for p in (await db.sales_orders.find_one({"id": so}))["payments"] if p.get("receipt_id") == rc["id"]]
        assert pay and pay[0]["method"] == "cash"
    sebelum = await db.ar_receipts.count_documents({"customer_id": cus})
    r = await _kwitansi(klien, orang["h_mgr"], cus, so, "bitcoin")
    assert (r.status_code, r.json().get("detail")) == (400, "Cara bayar tidak dikenal: bitcoin."), r.text
    assert await db.ar_receipts.count_documents({"customer_id": cus}) == sebelum


async def test_PMT1_U4_kwitansi_qris_nonaktif_di_kanda(klien, db, orang):
    cus, so = await _pelanggan(db, KANDA)
    sebelum = await db.ar_receipts.count_documents({})
    r = await _kwitansi(klien, orang["h_mgr_kanda"], cus, so, "qris", ent=KANDA)
    assert (r.status_code, r.json().get("detail")) == (400, "Cara bayar QRIS tidak aktif untuk PT ini."), r.text
    assert await db.ar_receipts.count_documents({}) == sebelum


# ── U5: rekening nonaktif tidak ikut "rekening satu-satunya" ─────────────────────────────────────────────────────
async def test_PMT1_U5_rekening_tunggal_abaikan_nonaktif(db):
    from services import bank_service
    eid = await pt_uji("PMT1A")
    aktif, mati = _id("bank"), _id("bank")
    for bid, nyala in ((aktif, True), (mati, False)):
        await db.bank_accounts.insert_one({"id": bid, "name": f"Bank {bid[-4:]}", "account_type": "bank",
                                           "cash_type": "kas_besar", "entity_id": eid, "is_active": nyala,
                                           "created_at": now_iso()})
    assert await bank_service.sole_account_id(eid, "kas_besar") == aktif


# ── U6–U8: field rekening, bawaan penerimaan, daftar rekening penerima ───────────────────────────────────────────
async def _rekening(klien, h, **isi):
    body = {"name": f"Rek PMT1 {next(_n)}", "account_type": "bank", "bank_name": "BCA",
            "account_number": f"88{next(_n):06d}", "holder_name": "PT Uji", **isi}
    return await klien.post("/api/bank-accounts", headers=h, json=body)


async def test_PMT1_U6_tampil_di_dokumen_wajib_atas_nama(klien, db, orang):
    sebelum = await db.bank_accounts.count_documents({})
    r = await klien.post("/api/bank-accounts", headers=orang["h_adm"], json={
        "name": "Rek tanpa atas nama", "account_type": "bank", "bank_name": "BCA", "account_number": "123",
        "show_on_documents": True})
    assert (r.status_code, r.json().get("detail")) == (400, PESAN_DOKUMEN), r.text
    assert await db.bank_accounts.count_documents({}) == sebelum


async def _penerima(klien, h, method="transfer", entity_id=KSC):
    return await klien.get("/api/bank-accounts/receiving", headers=h,
                           params={"entity_id": entity_id, "method": method})


async def test_PMT1_U7_satu_bawaan_per_pt_dan_cara_bayar(klien, orang):
    h = orang["h_adm"]
    ra = await _rekening(klien, h, payment_method_codes=["transfer", "giro"], default_receiving_methods=["transfer"])
    assert ra.status_code == 200, ra.text
    rb = await _rekening(klien, h, payment_method_codes=["transfer"])
    assert rb.status_code == 200, rb.text
    a, b = ra.json()["id"], rb.json()["id"]
    SIMPAN.update(a=a, b=b)
    r = await klien.patch(f"/api/bank-accounts/{b}", headers=h, json={"default_receiving_methods": ["transfer"]})
    assert r.status_code == 200, r.text
    r = await _penerima(klien, h)
    assert r.status_code == 200, r.text
    rows = {x["id"]: x for x in r.json()}
    assert rows[b]["is_default"] is True and rows[a]["is_default"] is False
    assert sum(1 for x in r.json() if x["is_default"]) == 1
    # Kas & Bank 3 (temuan tangkapan): + `cash_type` untuk kalimat jenis kas di form kwitansi; tetap tanpa saldo.
    assert set(rows[b]) == {"id", "name", "bank_name", "account_number", "holder_name", "cash_type", "is_default"}
    # bawaan untuk cara bayar yang tidak dilayani ditolak
    r = await klien.patch(f"/api/bank-accounts/{b}", headers=h, json={"default_receiving_methods": ["giro"]})
    assert (r.status_code, r.json().get("detail")) == (400, "Rekening ini tidak melayani cara bayar Giro / cek."), r.text


async def test_PMT1_U8_rekening_penerima_per_pt(klien, orang):
    rk = await _rekening(klien, orang["h_adm_kanda"], entity_id=KANDA)
    assert rk.status_code == 200, rk.text
    r = await _penerima(klien, orang["h_sls"])
    assert r.status_code == 200, r.text
    assert rk.json()["id"] not in {x["id"] for x in r.json()} and SIMPAN["a"] in {x["id"] for x in r.json()}
    assert all("balance" not in x for x in r.json())
    r = await _penerima(klien, orang["h_sls"], entity_id=KANDA)
    assert r.status_code == 403, r.text
    SIMPAN["kanda"] = rk.json()["id"]


# ── U9–U10: perubahan rekening dua orang ─────────────────────────────────────────────────────────────────────────
async def _atur_dua_orang(nilai="2"):
    await resolver.set_value(MIN_ORANG, nilai, scope_type="entity", scope_id=KSC, actor="uji", reason="uji PM-T1")


async def test_PMT1_U9_ubah_nomor_butuh_orang_kedua(klien, db, orang):
    await _atur_dua_orang("2")
    a = SIMPAN["a"]
    lama = (await db.bank_accounts.find_one({"id": a}))["account_number"]
    r = await klien.patch(f"/api/bank-accounts/{a}", headers=orang["h_mgr"], json={"account_number": "999000111"})
    assert r.status_code == 202, r.text
    ch = r.json()["change"]
    assert ch["status"] == "menunggu" and ch["action"] == "ubah"
    assert ch["changes"] == [{"field": "account_number", "from": lama, "to": "999000111"}]
    assert (await db.bank_accounts.find_one({"id": a}))["account_number"] == lama
    r = await klien.post(f"/api/bank-account-changes/{ch['id']}/decision", headers=orang["h_mgr"],
                         json={"decision": "approve", "note": ""})
    assert r.status_code == 403, r.text
    assert (await db.bank_accounts.find_one({"id": a}))["account_number"] == lama
    r = await klien.post(f"/api/bank-account-changes/{ch['id']}/decision", headers=orang["h_adm"],
                         json={"decision": "approve", "note": "cocok dengan buku tabungan"})
    assert r.status_code == 200, r.text
    assert (await db.bank_accounts.find_one({"id": a}))["account_number"] == "999000111"
    r = await klien.post(f"/api/bank-account-changes/{ch['id']}/decision", headers=orang["h_adm"],
                         json={"decision": "approve", "note": ""})
    assert (r.status_code, r.json().get("detail")) == (409, PESAN_DIPUTUS), r.text
    r = await klien.get("/api/bank-account-changes", headers=orang["h_adm"], params={"status": "diterapkan"})
    assert r.status_code == 200, r.text
    assert ch["id"] in {x["id"] for x in r.json()["items"]}


async def test_PMT1_U10_pt_lain_dan_bukan_field_peka_langsung(klien, db, orang):
    kanda = SIMPAN["kanda"]
    r = await klien.patch(f"/api/bank-accounts/{kanda}", headers=orang["h_mgr_kanda"],
                          json={"account_number": "777000222"})
    assert r.status_code == 200, r.text
    assert (await db.bank_accounts.find_one({"id": kanda}))["account_number"] == "777000222"
    assert await db.bank_account_changes.count_documents(
        {"account_id": kanda, "action": "ubah", "status": "diterapkan", "changes.field": "account_number"}) == 1
    a = SIMPAN["a"]
    r = await klien.patch(f"/api/bank-accounts/{a}", headers=orang["h_mgr"], json={"name": "Rek A berganti nama"})
    assert r.status_code == 200, r.text
    assert (await db.bank_accounts.find_one({"id": a}))["name"] == "Rek A berganti nama"


# ── U11: pengisian awal rekening lama ────────────────────────────────────────────────────────────────────────────
async def test_PMT1_U11_pengisian_awal_idempoten(db):
    from services import bank_service
    eid = await pt_uji("PMT1B")
    bank, kas1, kas2 = _id("bank"), _id("bank"), _id("bank")
    for bid, jenis in ((bank, "bank"), (kas1, "cash"), (kas2, "cash")):
        await db.bank_accounts.insert_one({"id": bid, "name": f"Lama {bid[-4:]}", "account_type": jenis,
                                           "entity_id": eid, "is_active": True, "created_at": now_iso()})
    hasil1 = await bank_service.isi_awal_bidang_rekening(tulis=True)
    assert hasil1["diubah"] >= 3
    b = await db.bank_accounts.find_one({"id": bank})
    assert b["purposes"] == ["penerimaan_pelanggan", "pembayaran_pemasok", "gaji", "operasional"]
    assert b["payment_method_codes"] == ["transfer", "giro", "qris"]
    assert b["default_receiving_methods"] == ["transfer"]
    assert b["holder_name"] == "" and b["show_on_documents"] is False
    for k in (kas1, kas2):
        d = await db.bank_accounts.find_one({"id": k})
        assert d["payment_method_codes"] == ["cash"] and d["default_receiving_methods"] == []
    potret = [x async for x in db.bank_accounts.find({"entity_id": eid}, {"_id": 0})]
    hasil2 = await bank_service.isi_awal_bidang_rekening(tulis=True)
    assert hasil2["diubah"] == 0
    assert [x async for x in db.bank_accounts.find({"entity_id": eid}, {"_id": 0})] == potret


# ── U12: dua pasangan izin dengan peran uji baku ─────────────────────────────────────────────────────────────────
async def _perubahan_menunggu(klien, orang):
    await _atur_dua_orang("2")
    r = await klien.patch(f"/api/bank-accounts/{SIMPAN['b']}", headers=orang["h_mgr"],
                          json={"holder_name": f"Atas nama {next(_n)}"})
    assert r.status_code == 202, r.text
    return r.json()["change"]["id"]


async def test_PMT1_U12_izin_putus_dan_kelola_master(klien, akun, sesi, orang, peran_tanpa_acuan,
                                                     peran_manajer_kosong, peran_sopir):
    baris = {"code": f"uji{next(_n)}", "name": "Cara bayar uji", "needs_account": "bank", "directions": ["masuk"],
             "active": True}
    h_ta_approve = await sesi(await akun(await peran_tanpa_acuan({"cash": ["approve"]}, label="Tanpa Acuan PMT1 a")))
    h_ta_conf = await sesi(await akun(await peran_tanpa_acuan({"cash": ["configure"]}, label="Tanpa Acuan PMT1 c")))
    cid = await _perubahan_menunggu(klien, orang)
    r = await klien.post(f"/api/bank-account-changes/{cid}/decision", headers=h_ta_approve,
                         json={"decision": "approve", "note": "uji izin"})
    assert r.status_code == 200, r.text
    r = await klien.post("/api/entity-masters/payment-methods", headers=h_ta_conf, json=baris)
    assert r.status_code == 200, r.text
    cid = await _perubahan_menunggu(klien, orang)
    for peran in (await peran_manajer_kosong(), peran_sopir):
        h = await sesi(await akun(peran))
        r = await klien.post(f"/api/bank-account-changes/{cid}/decision", headers=h,
                             json={"decision": "approve", "note": "uji izin"})
        assert r.status_code == 403, (peran, r.text)
        r = await klien.post("/api/entity-masters/payment-methods", headers=h, json={**baris, "code": f"x{next(_n)}"})
        assert r.status_code == 403, (peran, r.text)
        r = await _penerima(klien, h)
        assert r.status_code == 403, (peran, r.text)
    await _atur_dua_orang("1")


# ── U13: penjaga kosakata cara bayar ─────────────────────────────────────────────────────────────────────────────
def test_PMT1_U13_penjaga_kosakata():
    skrip = REPO / "scripts" / "guardrails" / "verify_payment_vocab.py"
    assert skrip.exists(), "penjaga verify_payment_vocab.py belum ada"
    uji = subprocess.run([sys.executable, str(skrip), "--self-test"], capture_output=True, text=True, timeout=120)
    assert uji.returncode == 0, uji.stdout + uji.stderr
    repo = subprocess.run([sys.executable, str(skrip)], capture_output=True, text=True, timeout=120)
    assert repo.returncode == 0, repo.stdout + repo.stderr


# ── Tambahan: pintu lain yang menerima cara bayar (langkah kerja 3) ──────────────────────────────────────────────
async def test_PMT1_normalisasi_pintu_bayar_hutang(db):
    """Bayar tagihan pemasok / kontrabon (satu pintu `ap_payment_service.pay_payable`): kata tak dikenal ditolak
    SEBELUM niat bayar lahir. Tagihan = fixture."""
    from services import ap_payment_service as aps
    vb = _id("vb")
    await db.vendor_bills.insert_one({"id": vb, "bill_number": "VB-PMT1", "entity_id": KSC, "status": "posted",
                                      "total": 500_000, "created_at": now_iso()})
    with pytest.raises(aps.ApPaymentError) as e:
        await aps.pay_payable(kind="vendor_bill", target_id=vb, actor={"id": "u", "name": "Uji"}, amount=100_000,
                              method="bitcoin")
    assert (e.value.status_code, str(e.value)) == (400, "Cara bayar tidak dikenal: bitcoin.")
    assert await db.ap_payment_intents.count_documents({"target_id": vb}) == 0


async def test_PMT1_normalisasi_uang_muka(klien, db, orang):
    r = await klien.post("/api/cash-advances", headers=orang["h_adm"], json={
        "kegiatan": "uji PM-T1", "payment_method": "tunai",
        "lines": [{"description": "bensin", "qty": 1, "unit_price": 50_000}]})
    assert r.status_code == 200, r.text
    assert (await db.cash_advances.find_one({"id": r.json()["id"]}))["payment_method"] == "cash"
    r = await klien.post("/api/cash-advances", headers=orang["h_adm"], json={
        "kegiatan": "uji PM-T1", "payment_method": "qris",
        "lines": [{"description": "bensin", "qty": 1, "unit_price": 50_000}]})
    assert (r.status_code, r.json().get("detail")) == (400, "Cara bayar QRIS tidak dipakai untuk pembayaran keluar."), r.text


async def test_PMT1_is_cash_mengganti_himpunan_tunai():
    from services import payment_method_service as pms
    assert pms.normalize("TUNAI") == "cash" and pms.normalize(" Kontan ") == "cash" and pms.normalize("cek") == "giro"
    with pytest.raises(ValueError):
        pms.normalize("bitcoin")
    assert await pms.is_cash(KSC, "tunai") is True
    assert await pms.is_cash(KSC, "transfer") is False
    assert await pms.is_cash(KSC, "writeoff") is False   # kata lain di riwayat pembayaran (bukan cara bayar)


async def test_PMT1_master_menolak_isian_tak_sah(klien, orang):
    r = await klien.post("/api/entity-masters/payment-methods", headers=orang["h_adm"],
                         json={"code": "aneh", "name": "Aneh", "needs_account": "dompet", "directions": ["masuk"]})
    assert r.status_code == 400, r.text
    r = await klien.post("/api/entity-masters/payment-methods", headers=orang["h_adm"],
                         json={"code": "aneh2", "name": "Aneh", "needs_account": "bank", "directions": ["ke samping"]})
    assert r.status_code == 400, r.text


async def test_PMT1_skrip_isi_awal_lapor_bawaan(db, capsys):
    """Skrip data nyata (H3): bawaan = lapor saja, tidak menulis; `--terapkan` mengisi; diulang = 0 perubahan."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("pmt1_isi", REPO / "scripts" / "blueprint" / "pmt1_isi_rekening.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    eid = await pt_uji("PMT1C")
    bid = _id("bank")
    await db.bank_accounts.insert_one({"id": bid, "name": "Lama skrip", "account_type": "bank", "entity_id": eid,
                                       "is_active": True, "created_at": now_iso()})
    assert await mod.jalankan(["--pt", eid]) == 0
    assert "purposes" not in await db.bank_accounts.find_one({"id": bid})
    assert "Mode lapor: 1 rekening perlu diisi" in capsys.readouterr().out
    assert await mod.jalankan(["--pt", eid, "--terapkan"]) == 0
    assert (await db.bank_accounts.find_one({"id": bid}))["default_receiving_methods"] == ["transfer"]
    assert await mod.jalankan(["--pt", eid, "--terapkan"]) == 0
    assert "Selesai: 0 rekening diisi." in capsys.readouterr().out
