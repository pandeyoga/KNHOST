"""PK-45 — penjaga cepat: plafon pelanggan, faktur pajak, dan gaji (docs/blueprint/unit/PK-45.md, U1–U16).

Fixture (DISISIP langsung ke database, mengikuti dua skrip bukti audit `t8_cr01_plafon_oleh_sales.py` dan
`t7_tx01_faktur_pengganti.py`):
  * pelanggan `cus_s` — PT `ent_ksc`, `status: "blocked"`, `credit_limit: 5.000.000`, milik akun Sales seed;
  * pelanggan `cus_x` + pesanan terkonfirmasi `so_x`, `so_u11`, `so_u12` — DPP 1.000.000, PPN 110.000 per pesanan;
  * karyawan keluar `emp_pk45_*` (U14, U15).
Alur (terbit/ganti/batal faktur, PATCH/PUT/POST pelanggan, pratinjau gaji) dijalankan lewat API.

Akun: `sls` = Sales seed; `fin` = Finance hanya `ent_ksc`; `mgr` = Manajer seed; `adm` = Admin seed;
`fin_k` = Finance hanya `ent_kanda`. Manajer bawaan selalu lintas PT, jadi "Manajer yang hanya ditugaskan ke satu PT"
(U7, U12, U16) memakai peran kustom beracuan Manajer dengan akses lintas PT dimatikan: `mgr_k` (hanya `ent_kanda`)
dan `mgr_s` (hanya `ent_ksc`).
"""
from __future__ import annotations

import datetime

import pytest

import bootstrap
from pembantu import jumlah

pytestmark = pytest.mark.anyio

PESAN_403_NON_PPN = ("Anda belum punya akses untuk membuat pesanan tanpa PPN. "
                     "Minta Admin menambahkan akses 'Pesanan Penjualan'.")
SIMPAN: dict = {}


def _sekarang() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _pesanan(oid: str) -> dict:
    # Hitungan tangan: 10 m × 100.000 = DPP 1.000.000; PPN 11% = 110.000; total 1.110.000.
    return {"id": oid, "number": oid.upper(), "entity_id": "ent_ksc", "customer_id": "cus_x",
            "customer_name": "Toko Uji", "status": "confirmed", "subtotal": 1_000_000, "dpp": 1_000_000,
            "ppn_amount": 110_000, "ppn_rate": 11, "grand_total": 1_110_000, "is_pkp": True,
            "items": [{"product_name": "Kain Uji", "quantity": 10, "unit": "m", "price": 100_000,
                       "line_total": 1_000_000}],
            "payments": [], "created_at": _sekarang()}


@pytest.fixture(scope="module")
async def uji(klien, db, akun, sesi, kepala_admin):
    sales = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0})
    await db.customers.insert_one({"id": "cus_s", "code": "CUST-PK45", "name": "Toko Milik Sales", "entity_id": "ent_ksc",
                                   "status": "blocked", "credit_limit": 5_000_000, "pic_name": "Andi",
                                   "assigned_sales_id": sales["id"], "assigned_sales_name": sales.get("name", ""),
                                   "created_at": _sekarang()})
    await db.customers.insert_one({"id": "cus_x", "name": "Toko Uji", "entity_id": "ent_ksc", "status": "active",
                                   "npwp": "01.234.567.8-901.000", "created_at": _sekarang()})
    await db.sales_orders.insert_many([_pesanan("so_x"), _pesanan("so_u11"), _pesanan("so_u12")])
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Manajer Satu PT", "base_role": "manager", "cross_entity": False, "description": "peran uji PK-45"})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    fin = await akun("finance", entitas=("ent_ksc",))
    fin_k = await akun("finance", entitas=("ent_kanda",))
    mgr_k = await akun(rid, entitas=("ent_kanda",))
    mgr_s = await akun(rid, entitas=("ent_ksc",))
    return {"sls": await sesi("sales@kainnusantara.id"), "fin": await sesi(fin),
            "mgr": await sesi("manager@kainnusantara.id"), "adm": kepala_admin,
            "fin_k": await sesi(fin_k, entitas="ent_kanda"), "mgr_k": await sesi(mgr_k, entitas="ent_kanda"),
            "mgr_s": await sesi(mgr_s, entitas="ent_ksc"), "sales_id": sales["id"], "peran_mgr_satu_pt": rid}


async def _pelanggan(db, cid: str = "cus_s") -> dict:
    return await db.customers.find_one({"id": cid}, {"_id": 0})


def _bukan_rute_hilang(r) -> bool:
    """Penolakan harus dari penjaga, bukan karena rutenya belum ada (FastAPI: 404/405 "Not Found"/"Method Not Allowed")."""
    return (r.json() or {}).get("detail") not in ("Not Found", "Method Not Allowed")


# ── Kredit pelanggan (CR-01, CR-04) ─────────────────────────────────────────
async def test_PK45_U1_patch_sales_tidak_mengubah_plafon_dan_status(klien, db, uji):
    r = await klien.patch("/api/customers/cus_s", headers=uji["sls"],
                          json={"data": {"credit_limit": 900_000_000, "status": "active", "pic_name": "Budi"}})
    assert r.status_code == 200, r.text
    c = await _pelanggan(db)
    assert c["credit_limit"] == 5_000_000
    assert c["status"] == "blocked"
    assert c["pic_name"] == "Budi"


# CR-T1 (perilaku SENGAJA diubah) — jalur sementara PK-45 `PUT /api/customers/{id}/credit` kini dijawab 410: plafon &
# blokir hanya lewat pengajuan profil kredit (uji pengganti: `test_CRT1_profil_kredit.py` U2–U13). Tiga pemanggil yang dulu
# diuji di sini (Sales tanpa izin = U2, Finance berizin = U3/U4, Finance PT lain = U6) kini sama-sama 410 dan data tetap.
PESAN_410 = "Plafon dan blokir kredit diubah lewat pengajuan perubahan kredit."


async def test_PK45_U2_U3_U4_U6_jalur_kredit_lama_410(klien, db, uji):
    for h, isi in ((uji["sls"], {"credit_limit": 900_000_000, "reason": "naikkan plafon"}),
                   (uji["fin"], {"credit_limit": 20_000_000, "status": "active", "reason": "tinjauan triwulan"}),
                   (uji["fin"], {"credit_limit": -1, "reason": "koreksi plafon"}),
                   (uji["fin_k"], {"credit_limit": 1, "status": "blocked", "reason": "uji pt lain"})):
        r = await klien.put("/api/customers/cus_s/credit", headers=h, json=isi)
        assert r.status_code == 410, r.text
        assert r.json()["detail"] == PESAN_410
    c = await _pelanggan(db)
    assert (c["credit_limit"], c["status"]) == (5_000_000, "blocked")
    assert await jumlah("audit_logs", {"action": "customer_credit_changed", "entity_id": "cus_s"}) == 0


async def test_PK45_U5_pelanggan_baru_oleh_sales_tanpa_plafon(klien, db, uji):
    r = await klien.post("/api/customers", headers=uji["sls"], json={
        "name": "Toko Baru PK45", "pic_name": "Sinta", "phone": "081234567845", "city": "Bandung",
        "address": "Jl. Uji No. 45", "credit_limit": 50_000_000, "status": "blocked"})
    assert r.status_code == 200, r.text
    c = await _pelanggan(db, r.json()["id"])
    assert c["credit_limit"] == 0
    assert c["status"] == "active"


async def test_PK45_U5b_pelanggan_baru_oleh_admin_plafon_jadi_pengajuan(klien, db, uji):
    # CR-T1 (SENGAJA diubah) — dulu Admin (`customer.manage_credit`) menyimpan plafon 50 jt langsung. Kini pelanggan selalu
    # plafon 0 dan isiannya menjadi pengajuan perubahan kredit `diajukan` atas nama Admin.
    r = await klien.post("/api/customers", headers=uji["adm"], json={
        "name": "Toko Baru Admin PK45", "pic_name": "Rina", "phone": "081234567846", "city": "Bandung",
        "address": "Jl. Uji No. 46", "credit_limit": 50_000_000, "assigned_sales_id": uji["sales_id"]})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert (await _pelanggan(db, cid))["credit_limit"] == 0
    req = await db.credit_profile_requests.find_one({"customer_id": cid}, {"_id": 0})
    assert req["status"] == "diajukan" and {c["field"]: c["to"] for c in req["changes"]}["credit_limit"] == 50_000_000


async def test_PK45_U7_izin_lewat_batas_pt_lain(klien, db, uji):
    await db.credit_overrides.insert_one({"id": "cro_pk45", "customer_id": "cus_s", "customer_name": "Toko Milik Sales",
                                          "amount": 1_000_000, "reason": "uji", "entity_id": "ent_ksc",
                                          "status": "pending", "requested_by_id": uji["sales_id"],
                                          "created_at": _sekarang()})
    r = await klien.get("/api/credit-overrides", headers=uji["mgr_k"])
    assert r.status_code == 200, r.text
    assert "cro_pk45" not in [x["id"] for x in r.json()]
    r = await klien.get("/api/credit-overrides/cro_pk45", headers=uji["mgr_k"])
    assert r.status_code == 404, r.text
    r = await klien.post("/api/credit-overrides/cro_pk45/decision", headers=uji["mgr_k"],
                         json={"decision": "approve", "reason": "uji pt lain"})
    assert not (200 <= r.status_code < 300), r.text
    assert (await db.credit_overrides.find_one({"id": "cro_pk45"}))["status"] == "pending"
    # pembanding: di PT-nya sendiri dokumen terlihat
    r = await klien.get("/api/credit-overrides", headers=uji["mgr"])
    assert "cro_pk45" in [x["id"] for x in r.json()]


async def test_PK45_U8_permohonan_nominal_nol_400(klien, db, uji):
    awal = await jumlah("credit_overrides", {})
    r = await klien.post("/api/customers/cus_s/credit-override", headers=uji["sls"],
                         json={"customer_id": "cus_s", "amount": 0, "reason": "pesanan besar"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Nominal izin wajib lebih dari 0."
    assert await jumlah("credit_overrides", {}) == awal


# ── Faktur pajak (TX-01, TX-02, TX-03) ──────────────────────────────────────
async def _rekap(klien, h, periode: str) -> dict:
    r = await klien.get("/api/tax/vat-summary", params={"period": periode, "entity_id": "ent_ksc"}, headers=h)
    assert r.status_code == 200, r.text
    # PK-40 menambah `gl_ppn`/`selisih` (pembanding buku besar) di kartu keluaran; uji PK-45 menilai tiga angka faktur.
    return {k: r.json()["keluaran"][k] for k in ("ppn", "dpp", "count")}


async def _terbitkan(klien, h, oid: str) -> dict:
    r = await klien.post(f"/api/sales-orders/{oid}/tax-invoice", json={}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_PK45_U9_faktur_diganti_tidak_dihitung_dua_kali(klien, db, uji):
    f1 = await _terbitkan(klien, uji["adm"], "so_x")
    SIMPAN["periode"] = f1["faktur_date"][:7]
    assert await _rekap(klien, uji["adm"], SIMPAN["periode"]) == {"ppn": 110_000, "dpp": 1_000_000, "count": 1}
    r = await klien.post(f"/api/tax-invoices/{f1['id']}/replace", json={"reason": "koreksi alamat"}, headers=uji["adm"])
    assert r.status_code == 200, r.text
    SIMPAN["f1"], SIMPAN["f2"] = f1["id"], r.json()["id"]
    # Sebelum perbaikan: 220.000 / 2.000.000 / 2 (faktur asli + pengganti).
    assert await _rekap(klien, uji["adm"], SIMPAN["periode"]) == {"ppn": 110_000, "dpp": 1_000_000, "count": 1}


async def test_PK45_U10_pengganti_dibatalkan_faktur_asli_dihitung_lagi(klien, db, uji):
    r = await klien.post(f"/api/tax-invoices/{SIMPAN['f2']}/cancel", json={"reason": "pengganti salah"},
                         headers=uji["adm"])
    assert r.status_code == 200, r.text
    asli = await db.tax_invoices.find_one({"id": SIMPAN["f1"]})
    assert asli.get("replaced_by_id") is None
    assert await _rekap(klien, uji["adm"], SIMPAN["periode"]) == {"ppn": 110_000, "dpp": 1_000_000, "count": 1}


async def test_PK45_U11_faktur_batal_membuka_kunci_amandemen(klien, db, uji):
    from services import amendment_service
    f = await _terbitkan(klien, uji["adm"], "so_u11")
    terbit, alasan = await amendment_service.is_issued(await db.sales_orders.find_one({"id": "so_u11"}, {"_id": 0}))
    assert terbit is True
    assert alasan == f"sudah terbit Faktur Pajak {f['number']}"
    r = await klien.post(f"/api/tax-invoices/{f['id']}/cancel", json={"reason": "salah terbit"}, headers=uji["adm"])
    assert r.status_code == 200, r.text
    terbit, _ = await amendment_service.is_issued(await db.sales_orders.find_one({"id": "so_u11"}, {"_id": 0}))
    assert terbit is False


async def test_PK45_U12_faktur_pt_lain_tidak_bisa_diubah(klien, db, uji):
    f = await _terbitkan(klien, uji["adm"], "so_u12")
    awal = await db.tax_invoices.find_one({"id": f["id"]}, {"_id": 0})
    langkah = [("patch", f"/api/tax-invoices/{f['id']}/nsfp", {"nsfp": "0100002612345678"}),
               ("post", f"/api/tax-invoices/{f['id']}/replace", {"reason": "uji pt lain"}),
               ("post", f"/api/tax-invoices/{f['id']}/cancel", {"reason": "uji pt lain"})]
    for cara, url, isi in langkah:
        r = await getattr(klien, cara)(url, json=isi, headers=uji["mgr_k"])
        assert not (200 <= r.status_code < 300), (url, r.text)
    akhir = await db.tax_invoices.find_one({"id": f["id"]}, {"_id": 0})
    for k in ("nsfp", "status", "replaced_by_id"):
        assert akhir.get(k) == awal.get(k), k
    assert await jumlah("tax_invoices", {"replaces_id": f["id"]}) == 0
    # pembanding: Admin di PT pemilik tetap bisa mengisi NSFP
    r = await klien.patch(f"/api/tax-invoices/{f['id']}/nsfp", json={"nsfp": "0100002612345678"}, headers=uji["adm"])
    assert r.status_code == 200, r.text


# ── Pesanan tanpa PPN (TX-04) ───────────────────────────────────────────────
def _isi_pesanan(customer_id: str = "cus_s", **lain) -> dict:
    # `cus_s` (bukan `cus_x`: NPWP `cus_x` = NPWP PT sendiri → ditolak sebagai badan usaha grup).
    return {"customer_id": customer_id, "shipping_address_id": "", "entity_id": "ent_ksc",
            "items": [{"product_id": "prd_pk45_tidak_ada", "quantity": 10, "unit": "meter"}], **lain}


async def test_PK45_U13_pesanan_tanpa_ppn_butuh_izin_dan_alasan(klien, db, uji):
    awal = await jumlah("sales_orders", {})
    r = await klien.post("/api/sales-orders", headers=uji["sls"], json=_isi_pesanan(tax_override="non_ppn",
                         tax_override_reason="pelanggan kawasan berikat"))
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == PESAN_403_NON_PPN
    r = await klien.post("/api/sales-orders", headers=uji["mgr"], json=_isi_pesanan(tax_override="non_ppn"))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Alasan pesanan tanpa PPN wajib diisi (minimal 10 huruf)."
    r = await klien.post("/api/sales-orders", headers=uji["mgr"], json=_isi_pesanan(
        tax_override="non_ppn", tax_override_reason="berikat 12345"))   # 7 huruf
    assert r.status_code == 400, r.text
    r = await klien.post("/api/sales-orders", headers=uji["mgr"], json=_isi_pesanan(tax_override="abc"))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Pilihan pajak pesanan tidak dikenal."
    assert await jumlah("sales_orders", {}) == awal
    # Lolos pemeriksaan pajak → berhenti di langkah sesudahnya (pelanggan tidak ada), bukan di penjaga pajak.
    # Pesanan sah ber-200 (ppn_amount 0, alasan tersimpan) diuji di MongoDB asli: tests/test_bp_PK45_pesanan_non_ppn.py.
    r = await klien.post("/api/sales-orders", headers=uji["mgr"], json=_isi_pesanan(
        "cus_pk45_tidak_ada", tax_override="non_ppn", tax_override_reason="pelanggan kawasan berikat"))
    assert r.status_code == 404, r.text
    r = await klien.post("/api/sales-orders", headers=uji["sls"], json=_isi_pesanan("cus_pk45_tidak_ada"))
    assert r.status_code == 404, r.text   # tanpa pilihan pajak: Sales tidak terpengaruh


# ── Gaji (PY-05, PY-10) ─────────────────────────────────────────────────────
async def test_PK45_U14_karyawan_keluar_ikut_gaji_bulan_terakhir(db, uji):
    from services import hr_payroll_service as pay
    emp = {"id": "emp_pk45_a", "entity_id": "ent_ksc", "name": "Karyawan Keluar", "status": "resigned",
           "separation_date": "2026-05-20", "base_salary": 5_000_000}
    await db.hr_employees.insert_one(dict(emp))
    assert "emp_pk45_a" in [e["id"] for e in await pay._active_employees("ent_ksc", "2026-05")]
    assert pay._is_final_tax_period(emp, "2026-05") is True
    assert "emp_pk45_a" not in [e["id"] for e in await pay._active_employees("ent_ksc", "2026-06")]


async def test_PK45_U15_data_lama_end_date_tetap_terbaca(db, uji):
    from services import hr_payroll_service as pay
    await db.hr_employees.insert_one({"id": "emp_pk45_b", "entity_id": "ent_ksc", "name": "Karyawan Lama",
                                      "status": "inactive", "end_date": "2026-05-31", "base_salary": 5_000_000})
    assert "emp_pk45_b" in [e["id"] for e in await pay._active_employees("ent_ksc", "2026-05")]


async def test_PK45_U16_pratinjau_gaji_tidak_membuka_pt_lain(klien, db, uji):
    # Catatan cek ulang: tiga baris spesifikasi sudah ditolak di HEAD oleh penjaga isi-permintaan
    # `entity_lifecycle_service.assert_body_entity_allowed` (dipanggil `current_user`), bukan oleh router.
    for ent, kode in (("ent_kanda", 403), ("all", 403), ("ent_ksc", 200)):
        r = await klien.post("/api/hr/payroll/runs/preview", headers=uji["mgr_s"],
                             json={"entity_id": ent, "period": "2026-05"})
        assert r.status_code == kode, (ent, r.text)
    assert r.json()["entity_id"] == "ent_ksc"
    # Lubang yang tersisa di HEAD: `entity_id` KOSONG lolos penjaga isi-permintaan lalu diteruskan mentah →
    # pratinjau tanpa saringan PT (karyawan semua PT). Kini = PT aktif, sama dengan proses buat.
    r = await klien.post("/api/hr/payroll/runs/preview", headers=uji["mgr_s"],
                         json={"entity_id": "", "period": "2026-05"})
    assert r.status_code == 200, r.text
    assert r.json()["entity_id"] == "ent_ksc"
    ids = [s["employee_id"] for s in r.json()["payslips"]]
    pt = {e["entity_id"] async for e in db.hr_employees.find({"id": {"$in": ids}}, {"_id": 0, "entity_id": 1})}
    assert pt == {"ent_ksc"}, pt


# ── Izin baru (02_STANDAR §3.2 butir 4) ─────────────────────────────────────
async def test_PK45_izin_kredit_lama_tidak_dikenal_lagi(klien, peran_tanpa_acuan, kepala_admin, uji):
    # CR-T1 (SENGAJA diubah) — `customer.manage_credit` dicabut dari katalog: peran baru dengan pasangan itu ditolak.
    # Uji izin pengganti (`credit_profile.*`, Tanpa Acuan / Manajer Kosong / Sopir): `test_CRT1_profil_kredit.py::U12`.
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Hanya Kredit Pelanggan", "base_role": "", "permissions": {"customer": ["view", "manage_credit"]},
        "description": "peran uji"})
    assert r.status_code == 400, r.text
    assert "tidak berlaku" in r.json()["detail"]


async def test_PK45_izin_non_ppn_peran_tanpa_acuan_dan_manajer_kosong(klien, akun, sesi, peran_tanpa_acuan,
                                                                     peran_manajer_kosong, uji):
    alasan = {"tax_override": "non_ppn", "tax_override_reason": "pelanggan kawasan berikat"}
    rid = await peran_tanpa_acuan({"order": ["view", "create", "tax_override"]}, label="Pesanan Tanpa PPN")
    r = await klien.post("/api/sales-orders", headers=await sesi(await akun(rid)),
                         json=_isi_pesanan("cus_pk45_tidak_ada", **alasan))
    assert r.status_code == 404, r.text   # lolos penjaga pajak
    rid = await peran_tanpa_acuan({"order": ["view", "create"]}, label="Pesanan Biasa")
    r = await klien.post("/api/sales-orders", headers=await sesi(await akun(rid)), json=_isi_pesanan(**alasan))
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == PESAN_403_NON_PPN
    r = await klien.post("/api/sales-orders", headers=await sesi(await akun(await peran_manajer_kosong())),
                         json=_isi_pesanan(**alasan))
    assert r.status_code == 403, r.text


async def test_PK45_izin_bawaan_sampai_ke_matriks_tersimpan(klien, db, kepala_admin, uji):
    """Instalasi lama (sebelum PK-45) dinyalakan ulang: pasangan bawaan baru sampai ke matriks tersimpan lewat
    `sync_permission_modules` (PR-T9). K-28: Sales tidak menerimanya. K-47: peran kustom beracuan Finance yang modul
    pelanggannya belum diubah ikut otomatis; peran kustom beracuan Manajer yang modul pelanggannya sudah diubah TIDAK
    diberi diam-diam — pasangannya tertunda ("Ikuti peran dasar")."""
    # CR-T1 — `customer.manage_credit` dicabut; yang tersisa dari PK-45 hanya `order.tax_override`.
    baru = {("order", "tax_override")}
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Finance Cabang", "base_role": "finance", "description": "uji PK-45"})
    assert r.status_code == 200, r.text
    fin_cabang = (r.json().get("role") or r.json())["id"]
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Manajer Pelanggan Lihat", "base_role": "manager", "levels": {"customer": "view"},
        "description": "uji PK-45"})
    assert r.status_code == 200, r.text
    mgr_lihat = (r.json().get("role") or r.json())["id"]
    # tiru matriks tersimpan SEBELUM PK-45: pasangan baru belum ada di mana pun
    rec = await db.permission_settings.find_one({"id": "default"})
    matrix, applied = rec["matrix"], rec["defaults_applied"]
    for peran in list(matrix):
        for res, aksi in baru:
            if aksi in (matrix[peran].get(res) or []):
                matrix[peran][res] = [a for a in matrix[peran][res] if a != aksi]
            if aksi in ((applied.get(peran) or {}).get(res) or []):
                applied[peran][res] = [a for a in applied[peran][res] if a != aksi]
    await db.permission_settings.update_one({"id": "default"},
                                            {"$set": {"matrix": matrix, "defaults_applied": applied}})
    await db.custom_roles.update_many({}, {"$set": {"pending_defaults": {}}})
    await bootstrap.run_bootstrap()

    async def izin(rid):
        r = await klien.get(f"/api/access/roles/{rid}", headers=kepala_admin)
        assert r.status_code == 200, r.text
        return r.json()
    # K-FIN-01 (pemilik 17 Nov 2026 malam) — Finance setara Manajer: ikut menerima `order.tax_override`.
    for peran, harus in (("admin", baru), ("manager", baru), ("finance", baru),
                         ("sales", set()), ("sales_admin", set())):
        p = (await izin(peran))["permissions"]
        punya = {(res, a) for res, a in baru if a in (p.get(res) or [])}
        assert punya == harus, peran
    fc = await izin(fin_cabang)
    assert "manage_credit" not in (fc["permissions"].get("customer") or [])
    ml = await izin(mgr_lihat)
    assert "manage_credit" not in (ml["permissions"].get("customer") or [])
    assert "manage_credit" not in (ml["pending_from_base"].get("customer") or [])
    assert "tax_override" in ml["permissions"]["order"]   # modul Pesanan Penjualan tidak diubah → ikut
