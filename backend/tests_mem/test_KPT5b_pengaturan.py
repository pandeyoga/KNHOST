"""KP-T5 serah-terima (b) — tabel Penomoran Dokumen (endpoint, validasi, pratinjau) dan tiga deret KP-35.

U4  format khusus PT: KANDA `SP-` lebar 6 → `KANDA/SP-000013`; KSC tetap `KSC/SO-00031` (penghitung 12 / 30).
U5  grup: sisipan `YYYY` + mulai lagi tiap tahun → `KSC/SO-2026-00001` (31 Des 2026) lalu `KSC/SO-2027-00001`.
U6  pengulangan tanpa sisipan → 400.                U7  nota kredit retur per PT ber-awalan `CN-` → 400 (bentrok).
U8  retur penjualan dijadikan per PT: `KSC/SRET-00041`, `KANDA/SRET-00042`; nomor lama tetap.
U9  jenis terkunci → 400.                           U10 `scope` pada baris PT → 400.
U11 tiga deret KP-35 melanjutkan nomor tertinggi: `VBM-00010`, `EMP-00121`, `SORD-<hari ini>-0004`.
    + KP-35 di lingkungan B: 20 panggilan bersamaan sebelum dokumen tersimpan → 20 nomor berbeda (dulu kembar).
U13 pratinjau dua kali → contoh sama; `number_sequences` tidak berubah.
U14 Sopir 403/403; Tanpa Acuan (`settings.view` saja) 200/403.
U15 PT baru `UJI` → `provisioning.number_preview = "UJI/SO-00001"` (dan mengikuti format grup).
U12 (dua puluh permintaan HTTP bersamaan, indeks unik) = lapis A: `backend/tests/test_bp_KPT5_bersamaan.py`.

Hitungan tangan: U4 penghitung (ent_kanda, "SO") 12 → 13, lebar 6 → `000013`, awalan tercetak `SP-` (kunci deret tetap
`SO`); U8 deret per PT baru disemai dari nomor tertinggi PT itu: KSC punya `SRET-00040` → 41; KANDA `SRET-00041` → 42.
Fixture: penghitung dan dokumen lama disisipkan langsung; format disimpan lewat API (alur).
"""
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

URL = "/api/doc-numbering"


@pytest.fixture(autouse=True)
async def _bersih(db):
    await db.doc_number_formats.delete_many({})
    await db.number_sequences.delete_many({})
    yield
    await db.doc_number_formats.delete_many({})
    await db.number_sequences.delete_many({})
    for c in ("sales_returns", "vendor_bills", "hr_employees", "special_orders", "sales_orders"):
        await db[c].delete_many({"_kpt5": True})


def _isi(**kw):
    out = {"prefix": "SO-", "width": 5, "date_token": "", "reset": "tidak", "reason": "Uji"}
    out.update(kw)
    return out


async def test_KPT5_U4_format_khusus_pt_tidak_mengubah_pt_lain(klien, kepala_admin, db):
    from core_utils import next_doc_number
    r = await klien.put(f"{URL}/so", headers=kepala_admin,
                        json=_isi(entity_id="ent_kanda", prefix="SP-", width=6))
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "pt" and r.json()["format"]["prefix"] == "SP-"
    await db.number_sequences.insert_many([{"entity_id": "ent_kanda", "doc_type": "SO", "last_no": 12},
                                           {"entity_id": "ent_ksc", "doc_type": "SO", "last_no": 30}])
    assert await next_doc_number("sales_orders", "number", "SO-", entity_id="ent_kanda") == "KANDA/SP-000013"
    assert await next_doc_number("sales_orders", "number", "SO-", entity_id="ent_ksc") == "KSC/SO-00031"
    # GET baris PT dan baris grup: sumber dan contoh nomor
    pt = {x["kind"]: x for x in (await klien.get(URL, headers=kepala_admin, params={"entity_id": "ent_kanda"})).json()["rows"]}
    assert (pt["so"]["source"], pt["so"]["source_label"], pt["so"]["next_preview"]) == \
        ("pt", "Khusus PT ini", "KANDA/SP-000014")
    grp = {x["kind"]: x for x in (await klien.get(URL, headers=kepala_admin, params={"entity_id": "all"})).json()["rows"]}
    assert grp["so"]["source"] == "bawaan" and grp["so"]["format"]["prefix"] == "SO-"
    # Hapus baris PT → kembali ke grup/bawaan
    r = await klien.delete(f"{URL}/so", headers=kepala_admin, params={"entity_id": "ent_kanda", "reason": "Uji"})
    assert r.status_code == 200 and r.json()["source"] == "bawaan", r.text
    assert await next_doc_number("sales_orders", "number", "SO-", entity_id="ent_kanda") == "KANDA/SO-00014"


async def test_KPT5_U5_mulai_lagi_tiap_tahun(klien, kepala_admin, db, monkeypatch):
    from core_utils import next_doc_number
    from services import doc_numbering_service as dns
    r = await klien.put(f"{URL}/so", headers=kepala_admin,
                        json=_isi(entity_id="all", date_token="YYYY", reset="tahunan"))
    assert r.status_code == 200, r.text
    await db.number_sequences.insert_one({"entity_id": "ent_ksc", "doc_type": "SO", "last_no": 30})
    monkeypatch.setattr(dns, "_now", lambda: datetime(2026, 12, 31, 9, 0, tzinfo=timezone.utc))   # 16.00 WIB
    assert await next_doc_number("sales_orders", "number", "SO-", entity_id="ent_ksc") == "KSC/SO-2026-00001"
    monkeypatch.setattr(dns, "_now", lambda: datetime(2027, 1, 1, 2, 0, tzinfo=timezone.utc))     # 09.00 WIB
    assert await next_doc_number("sales_orders", "number", "SO-", entity_id="ent_ksc") == "KSC/SO-2027-00001"
    # penghitung lama tidak diturunkan dan tidak dipakai deret tahunan
    assert (await db.number_sequences.find_one({"entity_id": "ent_ksc", "doc_type": "SO"}))["last_no"] == 30


async def test_KPT5_U6_pengulangan_tanpa_sisipan_ditolak(klien, kepala_admin):
    r = await klien.put(f"{URL}/so", headers=kepala_admin, json=_isi(entity_id="all", reset="tahunan"))
    assert r.status_code == 400
    assert r.json()["detail"] == ("Agar nomor tidak kembar, pengulangan tahunan harus disertai sisipan tahun.")
    r = await klien.put(f"{URL}/so", headers=kepala_admin, json=_isi(entity_id="all", reset="harian", date_token="YYMM"))
    assert r.status_code == 400 and "harian harus disertai sisipan tanggal" in r.json()["detail"]


async def test_KPT5_U7_bentuk_sama_dengan_jenis_lain_ditolak(klien, kepala_admin):
    r = await klien.put(f"{URL}/cn_retur", headers=kepala_admin,
                        json=_isi(entity_id="all", scope="per_pt", prefix="CN-"))
    assert r.status_code == 400
    assert r.json()["detail"] == "Format ini sama dengan Nota kredit, sehingga nomornya bisa kembar. Bedakan awalannya."
    # awalan berbeda → boleh
    r = await klien.put(f"{URL}/cn_retur", headers=kepala_admin,
                        json=_isi(entity_id="all", scope="per_pt", prefix="CNR-"))
    assert r.status_code == 200, r.text


async def test_KPT5_U8_deret_bersama_dijadikan_per_pt(klien, kepala_admin, db):
    from services.return_service import next_return_number
    await db.sales_returns.insert_many([
        {"_kpt5": True, "id": "sr_kpt5_1", "entity_id": "ent_ksc", "number": "SRET-00040"},
        {"_kpt5": True, "id": "sr_kpt5_2", "entity_id": "ent_kanda", "number": "SRET-00041"}])
    pv = await klien.post(f"{URL}/preview", headers=kepala_admin,
                          json={"kind": "sret", "entity_id": "all", "scope": "per_pt"})
    assert pv.status_code == 200, pv.text
    assert "Deret baru melanjutkan dari nomor tertinggi tiap PT yang sudah ada." in pv.json()["warnings"]
    r = await klien.put(f"{URL}/sret", headers=kepala_admin, json=_isi(entity_id="all", scope="per_pt", prefix="SRET-"))
    assert r.status_code == 200, r.text
    assert "Deret baru melanjutkan dari nomor tertinggi tiap PT yang sudah ada." in r.json()["warnings"]
    assert await next_return_number("ent_ksc") == "KSC/SRET-00041"
    assert await next_return_number("ent_kanda") == "KANDA/SRET-00042"
    lama = sorted([d["number"] async for d in db.sales_returns.find({"_kpt5": True}, {"_id": 0, "number": 1})])
    assert lama == ["SRET-00040", "SRET-00041"]


async def test_KPT5_U9_jenis_terkunci(klien, kepala_admin):
    r = await klien.put(f"{URL}/sup", headers=kepala_admin, json=_isi(entity_id="all", prefix="SUP-"))
    assert r.status_code == 400 and r.json()["detail"] == "Format nomor Kode pemasok tidak bisa diubah dari layar."
    rows = {x["kind"]: x for x in (await klien.get(URL, headers=kepala_admin)).json()["rows"]}
    assert all(rows[k]["locked"] for k in ("sup", "mak", "cc", "btg", "pa", "pj", "inv", "cust"))
    assert rows["sup"]["locked_note"] == "Tidak bisa diubah: dipakai bersama atau diturunkan dari dokumen lain."


async def test_KPT5_U10_scope_hanya_baris_grup(klien, kepala_admin):
    r = await klien.put(f"{URL}/so", headers=kepala_admin, json=_isi(entity_id="ent_kanda", scope="bersama"))
    assert r.status_code == 400 and r.json()["detail"] == "Pilihan per PT atau bersama diatur untuk seluruh grup."


async def test_KPT5_validasi_alasan_awalan_versi(klien, kepala_admin):
    r = await klien.put(f"{URL}/so", headers=kepala_admin, json=_isi(entity_id="all", reason=" "))
    assert r.status_code == 400 and r.json()["detail"] == "Alasan perubahan format nomor wajib diisi."
    for bad in ({"prefix": "so-"}, {"prefix": "SO/"}, {"prefix": "ABCDEFGHIJKLM"}, {"width": 2}, {"width": 9},
                {"width": "x"}):
        r = await klien.put(f"{URL}/so", headers=kepala_admin, json=_isi(entity_id="all", **bad))
        assert r.status_code == 400 and r.json()["detail"].startswith("Awalan hanya huruf besar"), (bad, r.text)
    r = await klien.put(f"{URL}/so", headers=kepala_admin, json=_isi(entity_id="all", expected_version=0))
    assert r.status_code == 200 and r.json()["version"] == 1
    r = await klien.put(f"{URL}/so", headers=kepala_admin, json=_isi(entity_id="all", width=6, expected_version=0))
    assert r.status_code == 409 and r.json()["detail"] == "Format ini sudah diubah orang lain. Muat ulang."
    r = await klien.put(f"{URL}/tidak_ada", headers=kepala_admin, json=_isi(entity_id="all"))
    assert r.status_code == 404
    r = await klien.delete(f"{URL}/so", headers=kepala_admin, params={"entity_id": "all", "reason": ""})
    assert r.status_code == 400


async def test_KPT5_jejak_audit_tercatat(klien, kepala_admin, db):
    r = await klien.put(f"{URL}/po", headers=kepala_admin, json=_isi(entity_id="ent_ksc", prefix="POB-", reason="Ganti"))
    assert r.status_code == 200, r.text
    a = await db.audit_logs.find_one({"action": "doc_number_format_saved", "entity_id": "po:ent_ksc"}, {"_id": 0})
    assert a and a.get("reason") == "Ganti"


# ── KP-35 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _hari_ini_wib() -> str:
    return datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Jakarta")).strftime("%y%m%d")


async def test_KPT5_U11_tiga_deret_melanjutkan_nomor_tertinggi(db):
    from services.hr_service import next_employee_code
    from services.makloon_order_service import _next_service_bill_no
    from services.special_order_service import generate_special_order_number
    hari = _hari_ini_wib()
    await db.vendor_bills.insert_one({"_kpt5": True, "id": "vb_kpt5", "bill_type": "makloon_service",
                                      "bill_number": "VBM-00009", "entity_id": "ent_ksc"})
    await db.hr_employees.insert_one({"_kpt5": True, "id": "emp_kpt5", "code": "EMP-00120", "entity_id": "ent_ksc"})
    await db.special_orders.insert_one({"_kpt5": True, "id": "sord_kpt5", "number": f"SORD-{hari}-0003",
                                        "entity_id": "ent_ksc"})
    assert await _next_service_bill_no("ent_ksc") == "VBM-00010"
    assert await next_employee_code("ent_ksc") == "EMP-00121"
    assert await generate_special_order_number(entity_id="ent_ksc") == f"SORD-{hari}-0004"


async def test_KPT5_KP35_dua_puluh_panggilan_bersamaan_tidak_kembar(db):
    """Lingkungan B: dulu "baca nomor terakhir + 1" — 20 pemanggil sebelum dokumennya tersimpan mendapat nomor yang
    SAMA. Kini penghitung atomik → 20 nomor berbeda. (Bukti MongoDB asli + HTTP: U12 lapis A.)"""
    from services.hr_service import next_employee_code
    from services.makloon_order_service import _next_service_bill_no
    from services.special_order_service import generate_special_order_number
    await db.hr_employees.insert_one({"_kpt5": True, "id": "emp_kpt5", "code": "EMP-00120", "entity_id": "ent_ksc"})
    await db.vendor_bills.insert_one({"_kpt5": True, "id": "vb_kpt5", "bill_type": "makloon_service",
                                      "bill_number": "VBM-00009", "entity_id": "ent_ksc"})
    # Dipanggil tanpa PT (tanda tangan lama) supaya uji yang sama berjalan di kode lama dan memperlihatkan nomor kembar.
    emp = await asyncio.gather(*[next_employee_code() for _ in range(20)])
    vbm = await asyncio.gather(*[_next_service_bill_no() for _ in range(20)])
    sord = await asyncio.gather(*[generate_special_order_number() for _ in range(20)])
    assert sorted(emp) == [f"EMP-{n:05d}" for n in range(121, 141)]
    assert sorted(vbm) == [f"VBM-{n:05d}" for n in range(10, 30)]
    assert len(set(sord)) == 20


# Salinan generator LAMA (HEAD 1392969) — oracle setara untuk tiga deret KP-35 pada data yang sama.
async def _lama_vbm(db):
    last = await db.vendor_bills.find_one(
        {"bill_type": "makloon_service"}, {"_id": 0, "bill_number": 1}, sort=[("bill_number", -1)])
    n = await db.vendor_bills.count_documents({"bill_type": "makloon_service"})
    if last and isinstance(last.get("bill_number"), str) and last["bill_number"].startswith("VBM-"):
        n = int(last["bill_number"].split("-")[1])
    return f"VBM-{n + 1:05d}"


async def _lama_emp(db):
    last = await db.hr_employees.find_one({}, {"_id": 0, "code": 1}, sort=[("code", -1)])
    if last and isinstance(last.get("code"), str) and last["code"].startswith("EMP-"):
        n = int(last["code"].split("-")[1])
    else:
        n = await db.hr_employees.count_documents({})
    return f"EMP-{n + 1:05d}"


async def _lama_sord(db, on_date):
    stamp = on_date.astimezone(ZoneInfo("Asia/Jakarta")) if on_date.tzinfo else on_date
    prefix = f"SORD-{stamp.strftime('%y%m%d')}"
    latest = await db.special_orders.find_one({"number": {"$regex": f"^{prefix}"}}, sort=[("number", -1)])
    seq = int(latest["number"].split("-")[-1]) + 1 if latest else 1
    return f"{prefix}-{seq:04d}"


async def test_KPT5_KP35_setara_generator_lama(db):
    """Untuk data rapi (semua tagihan jasa ber-`VBM-`, semua karyawan ber-`EMP-`), nomor pertama yang terbit sama
    dengan generator lama: kosong → 00001; berisi n → n+1. Pesanan khusus diuji dengan tanggal dokumen (penyemai)."""
    from services.hr_service import next_employee_code
    from services.makloon_order_service import _next_service_bill_no
    from services.special_order_service import generate_special_order_number
    hari = datetime(2026, 8, 16, 18, 30, tzinfo=timezone.utc)   # 17 Agt 01.30 WIB → SORD-260817
    await db.hr_employees.delete_many({"_kpt5": {"$ne": True}})   # seed boleh berisi karyawan lain — oracle butuh data rapi
    for isi in (0, 1, 7):
        for c in ("vendor_bills", "hr_employees", "special_orders"):
            await db[c].delete_many({"_kpt5": True})
        await db.number_sequences.delete_many({})
        for i in range(1, isi + 1):
            await db.vendor_bills.insert_one({"_kpt5": True, "id": f"vbk{i}", "bill_type": "makloon_service",
                                              "bill_number": f"VBM-{i * 3:05d}", "entity_id": "ent_ksc"})
            await db.hr_employees.insert_one({"_kpt5": True, "id": f"empk{i}", "code": f"EMP-{i * 5:05d}"})
            await db.special_orders.insert_one({"_kpt5": True, "id": f"sordk{i}", "number": f"SORD-260817-{i:04d}"})
        harap = (await _lama_vbm(db), await _lama_emp(db), await _lama_sord(db, hari))
        hasil = (await _next_service_bill_no(), await next_employee_code(), await generate_special_order_number(hari))
        assert hasil == harap, isi


# ── U13 / U14 / U15 ───────────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT5_U13_pratinjau_tidak_menaikkan_penghitung(klien, kepala_admin, db):
    await db.number_sequences.insert_one({"entity_id": "ent_ksc", "doc_type": "SO", "last_no": 41})
    body = {"kind": "so", "entity_id": "ent_ksc", "prefix": "SO-", "width": 6, "date_token": "", "reset": "tidak"}
    a = (await klien.post(f"{URL}/preview", headers=kepala_admin, json=body)).json()
    b = (await klien.post(f"{URL}/preview", headers=kepala_admin, json=body)).json()
    assert a["samples"] == b["samples"] == ["KSC/SO-000042", "KSC/SO-000043", "KSC/SO-000044"]
    assert (await db.number_sequences.find_one({"entity_id": "ent_ksc", "doc_type": "SO"}))["last_no"] == 41
    assert await db.number_sequences.count_documents({}) == 1


async def test_KPT5_U14_izin(klien, akun, sesi, peran_sopir, peran_tanpa_acuan):
    sopir = await sesi(await akun(peran_sopir))
    assert (await klien.get(URL, headers=sopir)).status_code == 403
    assert (await klien.put(f"{URL}/so", headers=sopir, json=_isi(entity_id="ent_ksc"))).status_code == 403
    rid = await peran_tanpa_acuan({"settings": ["view"]}, label="Lihat Pengaturan KPT5")
    lihat = await sesi(await akun(rid))
    r = await klien.get(URL, headers=lihat, params={"entity_id": "ent_ksc"})
    # CR-T1 — jenis `pkr` (pengajuan perubahan kredit); PK-22 — jenis `str` (setoran kewajiban gaji).
    # PM-T4 — + jenis `ttp` (titipan tunai sales) dan `stt` (setoran titipan): + 2. KM-T3 — + jenis `lin` (lembar insentif).
    assert r.status_code == 200 and len(r.json()["rows"]) == 66 + 1 + 1 + 2 + 1
    r = await klien.put(f"{URL}/so", headers=lihat, json=_isi(entity_id="ent_ksc"))
    assert r.status_code == 403 and "penomoran dokumen" in r.json()["detail"]
    # Baris grup hanya untuk orang yang ditugaskan di semua PT (penugasan, bukan nama peran)
    rid2 = await peran_tanpa_acuan({"settings": ["view", "manage"]}, label="Kelola Pengaturan KPT5")
    satu_pt = await sesi(await akun(rid2, entitas=("ent_ksc",)))
    assert (await klien.put(f"{URL}/so", headers=satu_pt, json=_isi(entity_id="all"))).status_code == 403
    r = await klien.put(f"{URL}/so", headers=satu_pt, json=_isi(entity_id="ent_ksc", width=6))
    assert r.status_code == 200, r.text
    assert (await klien.put(f"{URL}/so", headers=satu_pt, json=_isi(entity_id="ent_kanda"))).status_code == 403


async def test_KPT5_U15_pt_baru_pratinjau_nomor(klien, kepala_admin):
    r = await klien.post("/api/entities", headers=kepala_admin, json={
        "type": "PT", "default_tax_mode": "non_ppn", "legal_name": "PT Uji Nomor", "short_name": "UJI",
        "doc_prefix": "UJI"})
    assert r.status_code == 200, r.text
    assert r.json()["provisioning"]["number_preview"] == "UJI/SO-00001"
    # Pratinjau wizard (PT belum dibuat): kode dari isian, format grup
    assert (await klien.put(f"{URL}/so", headers=kepala_admin, json=_isi(entity_id="all", width=6))).status_code == 200
    pv = await klien.post(f"{URL}/preview", headers=kepala_admin, json={"kind": "so", "entity_id": "", "code": "BARU"})
    assert pv.status_code == 200 and pv.json()["samples"][0] == "BARU/SO-000001"


async def test_KPT5_daftar_lengkap_dan_contoh_berikutnya(klien, kepala_admin, db):
    await db.number_sequences.insert_many([
        {"entity_id": "__shared__", "doc_type": "sales_returns:number:SRET-", "last_no": 7}])
    j = (await klien.get(URL, headers=kepala_admin, params={"entity_id": "ent_ksc"})).json()
    rows = {x["kind"]: x for x in j["rows"]}
    # CR-T1 — + jenis `pkr`; PK-22 — + jenis `str`; PM-T4 — + jenis `ttp`, `stt`; KM-T3 — + jenis `lin`
    assert len(rows) == 66 + 1 + 1 + 2 + 1 and j["groups"][0] == "Penjualan"
    assert rows["sret"]["next_preview"] == "SRET-00008" and rows["sret"]["format"]["scope"] == "bersama"
    assert rows["so"]["next_preview"] == "KSC/SO-00001" and rows["so"]["last_no"] == 0
    assert rows["inv"]["locked"] and rows["inv"]["next_preview"].startswith("INV-")
    lot = rows["lot"]
    assert lot["format"]["date_token"] == "YYMM" and lot["format"]["reset"] == "bulanan"
    ym = datetime.now(timezone.utc).strftime("%y%m")
    assert lot["next_preview"].startswith(f"KSC/LOT-{ym}-")
    # pratinjau grup untuk jenis per PT: kode contoh, tanpa penghitung
    g = {x["kind"]: x for x in (await klien.get(URL, headers=kepala_admin)).json()["rows"]}
    assert g["so"]["next_preview"] == "KODE/SO-00001" and g["so"]["last_no"] is None
    # tidak ada penghitung yang dibuat oleh daftar/pratinjau
    assert await db.number_sequences.count_documents({}) == 1
    # "Contoh nomor berikutnya" = nomor yang benar-benar terbit berikutnya
    from core_utils import next_doc_number
    from services.lot_service import next_lot_number
    from services.return_service import next_return_number
    assert await next_doc_number("sales_orders", "number", "SO-", entity_id="ent_ksc") == rows["so"]["next_preview"]
    assert await next_return_number("ent_ksc") == rows["sret"]["next_preview"]
    assert await next_lot_number("ent_ksc") == lot["next_preview"]
