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

## Penjaga matriks izin berjalan (PR-T8, INV-PERM-02)

`sapuan_izin.py` bukan berkas `test_*` (tidak ikut `pytest`): skrip penjaga yang menyalakan aplikasi utuh lewat `boot_app`,
membuat peran uji (`POST /api/access/roles`) dan akunnya (`POST /api/users` + `POST /api/auth/login`), lalu memanggil
tiap rute `/api/*` (kecuali `/api/auth/logout*`) dan menilai jawabannya (kode M0–M8 di docstring skrip). Keluar 0 = hijau.

```bash
python backend/tests_mem/sapuan_izin.py                         # mode cepat — lima akun (gate --full)
python backend/tests_mem/sapuan_izin.py --penuh                 # + 13 peran bawaan (GET) + 11 peran "{peran} Kosong" lagi
python backend/tests_mem/sapuan_izin.py --awalan /api/costing --keluaran /tmp/sapuan.json   # iterasi; hasil per rute
python backend/tests_mem/sapuan_izin.py --uji-diri              # bukti-merah penilai (tanpa aplikasi)
python -m pytest backend/tests_mem/test_PRT8_sapuan_izin.py -n 0 # uji penilai + rute sementara (±25 dtk)
```

Lama jalan terukur (14 Nov 2026, HEAD `b8bd0a2`, satu proses Python 3.11): mode cepat **1.773 rute, 7.892 permintaan,
±70 dtk** (±75 dtk dengan proses awal); mode penuh **37.795 permintaan, ±345 dtk** (±6 mnt dengan proses awal). Akun, urut paling lemah dulu: `tanpa_token`
(tanpa sesi), `kosong` (tanpa peran dasar, semua modul "Tidak ada"), `sopir` (peran bawaan `driver`), `mgr0`
("Manajer Kosong"), [mode penuh: "{peran} Kosong" untuk 11 peran bawaan lain selain Admin — 12 bersama `mgr0`], `penuh` (tanpa peran
dasar, tiap modul pada tingkat tertinggi yang tersedia; GET saja), [mode penuh: satu akun per peran bawaan; GET saja].
Parameter jalur diisi `x` (bilangan → `1`, enum → nilai pertama); isi permintaan dibuat dari skema OpenAPI.

Berkas harapan `sapuan_izin_harapan.json` — tiap baris wajib beralasan (baris tanpa alasan = M7):

| Bagian | Isi |
|---|---|
| `tolak_bukan_izin` | `GET` yang menolak akun `penuh` dengan 403 bukan karena izin (kepemilikan, PT, status) |
| `menunggu_unit` | Endpoint yang oleh PR-T3 diserahkan ke unit lain (PK-17, KF-T1, KP-T4, PR-T4); unit pemegangnya menghapus barisnya |
| `tak_teruji` | Rute yang isinya benar-benar tidak bisa dibuat otomatis (utamakan `isi_contoh`) |
| `galat_dikenal` | 5xx yang dikenal, dengan unit/alasannya |
| `isi_contoh` | `{"json": …, "query": …, "data": …, "path": {param: nilai}, "alasan": …}` — menimpa bagian yang disebut saja |

### Aturan untuk endpoint baru

1. Pernyataan pertama handler adalah `require_permission` atau `require_any_permission` (`02_STANDAR.md` §3.1 Z1). Tidak
   perlu mendaftarkan apa pun; sapuan menemukannya sendiri.
2. Sengaja login-saja (milik sendiri, data rujukan, sesi): tambahkan ke `LOGIN_ONLY` (`backend/login_only_endpoints.py`)
   dengan alasannya.
3. Sengaja tanpa sesi (perangkat, verifikasi publik): tambahkan ke `PUBLIC_ALLOWLIST`
   (`scripts/guardrails/verify_auth_coverage.py`) dengan alasannya.
4. Penolakan yang bukan soal izin (kepemilikan, PT, status) memakai 403 tanpa header izin; bila tercapai oleh akun
   `penuh` dengan id contoh, daftarkan di `tolak_bukan_izin`.
5. Isi permintaan yang tidak lolos validasi otomatis: beri contoh di `isi_contoh`, jangan menambah `tak_teruji`.
6. Izin baru: empat tempat menurut `02_STANDAR.md` §3.2; sapuan mode cepat harus hijau di commit yang sama.

Mode `--penuh` dijalankan dengan tangan sebelum unit yang mengubah izin, peran, atau gerbang endpoint dinyatakan
`selesai`; keluarannya dilampirkan di laporan unit itu.

## Isi

| Berkas | Isi |
|---|---|
| `sapuan_izin.py`, `sapuan_izin_harapan.json` | Penjaga matriks izin berjalan dan daftar pengecualiannya (PR-T8; di atas) |
| `test_PRT8_sapuan_izin.py` | PR-T8 U2–U10: rute sementara `/api/_uji/*` (bukti-merah M0–M3, M6, M7), penilai M5, `/api/costing` |
| `test_PK02_kerangka.py`, `test_PK02_isolasi_a.py`, `test_PK02_isolasi_b.py` | Uji kerangka (U1–U10, U14) |
| `test_PK02_laporan_inti.py` | 15 tes laporan inti — harus selalu lulus |
| `test_PK02_arus_kas_ekuitas.py` | 4 tes arus kas dan ekuitas — harus selalu lulus |
| `test_PK02_reproduksi_temuan.py` | 10 temuan sebagai perilaku benar, ditandai "diharapkan gagal" (+1 tes penjaga IC-05 lewat HTTP) |
