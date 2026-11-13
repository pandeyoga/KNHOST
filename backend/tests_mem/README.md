# `backend/tests_mem/` — uji aplikasi utuh di database tiruan

Dibangun unit blueprint PK-02. Tiap modul uji menyalakan aplikasi utuh (`server.app` + proses awal + seed) di atas
`mongomock-motor`, mulai dari database kosong. Tidak pernah menyentuh MongoDB asli: `conftest.py` menghentikan sesi bila
klien bukan klien tiruan, dan `boot_app.py` memaksa `MONGO_URL`/`DB_NAME` palsu serta `KN_DEMO_DATA=false` (hasil sama
di semua mesin, walau `backend/.env` pengembang berbeda).

## Memasang dan menjalankan

```bash
pip install -r backend/requirements.txt -r backend/tests_mem/requirements.txt
python -m pytest backend/tests_mem -n 0            # dari root repo, berurutan
cd backend && python -m pytest tests_mem           # dua pekerja (pytest.ini) — ringkasan harus sama
```

Batas: database tiruan tidak menguji indeks unik, balapan, transaksi, maupun klaim bersyarat berisi larik. Butir uji
seperti itu hanya sah di MongoDB asli (`backend/tests/test_bp_<ID>_…`, `docs/blueprint/03_LINGKUNGAN_UJI.md` §1).

## Aturan

1. Tes berupa `async def`; tanda `anyio` dipasang otomatis.
2. Tanda `xfail` wajib `strict=True` dan `reason` berbentuk `"<ID temuan> — <kalimat>"`; selain itu pengumpulan gagal.
   Unit yang memperbaiki temuan itu mencabut tandanya.
3. Tes memakai PT seed (`ent_ksc` PKP, `ent_kanda` non-PKP) atau PT buatan `pt_uji("<KODE>")`; tidak bergantung pada
   urutan modul. Data dalam satu modul boleh berlanjut antar-tes (fixture `aplikasi` bercakupan modul).
4. Seed awal: 4 akun (`admin@`, `sales@`, `manager@`, `warehouse@kainnusantara.id`), sandi acak — sesi dibuat lewat
   fixture `sesi`, bukan login.

## Kontrak fixture (`conftest.py`)

Nama dan tanda tangan ini mengikat semua unit blueprint; mengubahnya = koreksi blueprint.

| Fixture | Cakupan | Perilaku |
|---|---|---|
| `aplikasi` | modul | Hapus semua koleksi, pulihkan cache proses, masuk `server.lifespan(server.app)`; menghasilkan `server.app` |
| `klien` | modul | `httpx.AsyncClient` lewat `ASGITransport` ke `aplikasi`, `base_url="http://uji"` |
| `db` | modul | `db.db` aplikasi |
| `akun` | modul | `await akun(peran, *, entitas=("ent_ksc",), email="")` → dokumen `users` aktif baru |
| `sesi` | modul | `await sesi(email_atau_dokumen_akun, *, entitas="ent_ksc")` → header `Authorization` + `X-Entity-Id` |
| `kepala_admin` | modul | Header sesi `admin@kainnusantara.id` |
| `peran_tanpa_acuan` | modul | `await peran_tanpa_acuan({"sumber_daya": ["aksi", …]}, *, label="")` → id peran kustom tanpa peran acuan |
| `peran_manajer_kosong` | modul | `await peran_manajer_kosong()` → id peran kustom beracuan Manajer, semua modul "Tidak ada" (sekali per modul) |
| `peran_sopir` | sesi | `"driver"` |
| `paksa_jurnal_gagal` | fungsi | `async with paksa_jurnal_gagal(cara, *, entity_id="", kode_akun="", period_key="", source_type="", kali=1) as gagal:` — `"akun"` menonaktifkan akun untuk PT itu; `"periode"` menutup bulan untuk PT itu; `"sisip"` membuat `kali` panggilan pertama `gl_service._insert_entry` yang cocok melempar `RuntimeError("uji: jurnal dipaksa gagal")` (`gagal` = daftar argumen panggilan yang digagalkan). Keadaan dipulihkan saat keluar |

## Kontrak pembantu (`pembantu.py`)

| Fungsi | Perilaku |
|---|---|
| `AKTOR_UJI` | `{"id": "user_admin_01", "name": "Budi Santoso", "role": "admin"}` |
| `tutup_periode(entity_id, period_key, *, period_type="month", lewat_layanan=False)` | Bawaan: sisip langsung `period_closings` berstatus `closed` (bulan mana pun). `lewat_layanan=True`: alur `close_period` |
| `buka_periode(closing_id)` | `closing_service.reopen_period` |
| `nonaktifkan_akun(entity_id, kode)`, `aktifkan_akun(entity_id, kode)` | `gl_service.update_account` per PT |
| `pt_uji(kode)` | PT `ent_uji_<kode kecil>` + bagan akun baku; aman diulang |
| `jurnal(entity_id, tanggal, baris, ket, source_id)` | `gl_service._insert_entry`, `source_type="uji"`, `baris` = `[(kode, debit, kredit), …]` |
| `saldo_akun(kode, entity_id, per="")` | Saldo buku besar akun untuk PT itu |
| `jurnal_dari(source_type, awalan_source_id)` | Jurnal bukan `void` yang `source_id`-nya berawalan itu |
| `jumlah(koleksi, saring)` | `count_documents` |
| `alasan_xfail_sah(reason)` | Benar bila `reason` berbentuk `"<ID> — …"` |

## Isi

| Berkas | Isi |
|---|---|
| `test_PK02_kerangka.py`, `test_PK02_isolasi_a.py`, `test_PK02_isolasi_b.py` | Uji kerangka (U1–U10, U14) |
| `test_PK02_laporan_inti.py` | 15 tes laporan inti — harus selalu lulus |
| `test_PK02_arus_kas_ekuitas.py` | 4 tes arus kas dan ekuitas — harus selalu lulus |
| `test_PK02_reproduksi_temuan.py` | 10 temuan sebagai perilaku benar, ditandai "diharapkan gagal" (+1 tes penjaga IC-05 lewat HTTP) |
