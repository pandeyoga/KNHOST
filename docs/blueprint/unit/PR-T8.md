# PR-T8 — Jadikan sapuan peran × endpoint penjaga yang berjalan

| | |
|---|---|
| Gelombang | Jalur peran (sejajar dengan gelombang 3–7) |
| Jenis | infrastruktur |
| Risiko | rendah |
| Prasyarat | PR-T3 |
| Menutup temuan | — (menjaga agar PR-01, PR-03, PR-04 tidak kembali) |
| Keputusan | K-47 |
| Standar | §3.1 (Z1, Z3), §3.2 (butir 4), §6 |
| Lingkungan uji | B |

## Tujuan

Setiap rute aplikasi diuji terhadap peran uji secara otomatis: rute yang bisa dilewati tanpa izin, rute yang menolak
pemegang izin, dan rute yang terbuka hanya karena peran dasarnya Manajer membuat penjaga merah. Endpoint baru tidak
bisa masuk tanpa putusan tertulis: berizin, login-saja dengan alasan, atau tanpa sesi dengan alasan.

## Keadaan sekarang

| # | Fakta | Jangkar | Bukti |
|---|---|---|---|
| 1 | Sapuan baca membuat empat peran kustom uji, memberi tiap peran satu akun dan sesi, lalu memanggil semua rute GET (786) untuk 16 peran; lama ±12 menit | `docs/audit/konfigurasi-peran-2026-11-13/bukti/t2_roles.py:28` (`specs`); `docs/audit/konfigurasi-peran-2026-11-13/bukti/t2_roles.py:52` (`gets`) | [dijalankan] sesi audit 13 Nov 2026 |
| 2 | Penganalisisnya membandingkan jawaban dengan izin yang dibaca inventaris statik: A = lolos tanpa izin, B = ditolak padahal berizin | `docs/audit/konfigurasi-peran-2026-11-13/bukti/t2_analyze.py:19` (`klass`) | [dijalankan] hasil: A kosong; B 13 rute; 23 rute terbuka lewat peran dasar |
| 3 | Sapuan tulis memanggil 962 rute tulis oleh tiga akun (peran tanpa dasar tanpa izin, Sopir, Manajer Kosong) dengan isi yang dibuat dari skema; 25 rute tidak tercapai gerbangnya (422) | `docs/audit/konfigurasi-peran-2026-11-13/bukti/t9_tulis_tanpa_izin.py:54` (`contoh`); `docs/audit/konfigurasi-peran-2026-11-13/bukti/t9_tulis_tanpa_izin.py:212` (`sesi_akhir`) | [dijalankan] `bukti/README.md` baris T9 |
| 4 | Inventaris statik mengikuti pembantu menurut nama fungsi lintas berkas, sehingga 8 endpoint bergerbang nama peran dan 12 endpoint login-saja terhitung "berizin"; jalur router tanpa awalan tidak cocok dengan rute hidup | `docs/audit/konfigurasi-peran-2026-11-13/bukti/inv_endpoints.py:54` (`helper_prims`) | [dibaca] dibandingkan dengan pencarian langsung pada HEAD (rincian di PR-T2 dan PR-T3) |
| 5 | Jenis penolakan dikenali dari teks pesan ("Permission ditolak", "Role Anda tidak") | `docs/audit/konfigurasi-peran-2026-11-13/bukti/t2_analyze.py:20` (`TOLAK_GERBANG`) | [dibaca] |
| 6 | Skrip-skrip itu berada di arsip audit dan tidak dipanggil gate mana pun | `scripts/gate.sh:141` (`run_gate`) | [dibaca] |
| 7 | Penjaga statik yang ada hanya memastikan tiap endpoint punya penegak sesi; ia tidak membedakan login-saja dari berizin dan saat ini merah untuk 28 endpoint | `scripts/guardrails/verify_auth_coverage.py:53` (`PUBLIC_ALLOWLIST`) | [dijalankan] `docs/blueprint/03_LINGKUNGAN_UJI.md` §4 |
| 8 | Daftar endpoint login-saja yang sah (`LOGIN_ONLY`) lahir di PR-T3; kerangka uji database tiruan lahir di PK-02 | `backend/tests_mem/conftest.py` | — |

## Perubahan

### Data

Tidak ada.

### Server

Tidak ada perubahan pada kode aplikasi. Yang dibuat adalah alat uji di `backend/tests_mem/` (lingkungan B):

| Berkas baru | Isi |
|---|---|
| `backend/tests_mem/sapuan_izin.py` | Skrip penjaga (bukan berkas `test_*`, jadi tidak ikut `pytest` biasa). Menyalakan aplikasi lewat `boot_app` PK-02, membuat peran dan akun uji lewat API, menyapu rute, menilai, keluar 0 atau 1 |
| `backend/tests_mem/sapuan_izin_harapan.json` | Daftar yang boleh menyimpang, masing-masing dengan alasan (bentuk di bawah) |
| `backend/tests_mem/test_PRT8_sapuan_izin.py` | Uji penilai dengan hasil buatan dan rute sementara (bukti-merah) |

**Peran sapuan** (dibuat lewat `POST /api/access/roles` di awal jalan):

| Kode | Peran | Rute yang disapu |
|---|---|---|
| `tanpa_token` | permintaan tanpa sesi | semua |
| `kosong` | tanpa peran dasar, semua modul "Tidak ada" | semua |
| `penuh` | tanpa peran dasar, semua modul pada tingkat tertinggi yang tersedia | GET saja (supaya tidak ada tulisan sungguhan) |
| `mgr0` | "Manajer Kosong": peran dasar Manajer, semua modul "Tidak ada" | semua |
| `sopir` | peran bawaan `driver` | semua |
| mode penuh saja: 13 peran bawaan | akun seed atau akun buatan per peran | GET saja |
| mode penuh saja: "{peran} Kosong" untuk 12 peran bawaan selain Admin | peran dasar itu, semua modul "Tidak ada" | semua |

Urutan akun: paling lemah dulu (`tanpa_token`, `kosong`, `sopir`, peran "Kosong", lalu yang berizin), seperti T9.
Rute `/api/auth/logout*` dilewati. Parameter jalur diisi `x`; isi permintaan dibuat dari skema OpenAPI dengan fungsi
`contoh` (dipindahkan dari T9) dan bisa ditimpa per rute lewat `isi_contoh` di berkas harapan.

**Kelas jawaban:** `ditolak` = 401 atau 403 · `tak_teruji` = 422 · `galat` = 5xx atau pengecualian · `lolos` = lainnya
(termasuk 404, karena data hanya seed). Izin yang diminta sebuah penolakan dibaca dari header `X-Permission-Denied`
(lahir di PR-T6); bila header tidak ada, dari pola teks lama `Permission ditolak: <sumber daya>.<aksi>`.

**Yang membuat merah:**

| Kode | Keadaan | Arti |
|---|---|---|
| M0 | `tanpa_token` `lolos` pada rute di luar `PUBLIC_ALLOWLIST` (`scripts/guardrails/verify_auth_coverage.py`) | Endpoint terbuka tanpa login |
| M1 | `kosong` `lolos` pada rute di luar `LOGIN_ONLY` (PR-T3), `PUBLIC_ALLOWLIST`, dan `menunggu_unit` | Rute berizin lolos tanpa izin, atau rute login-saja tanpa putusan |
| M2 | `penuh` mendapat 403 pada rute GET di luar `tolak_bukan_izin` | Rute menolak pemegang izin (gerbang nama peran atau gerbang lain yang tidak bisa dipenuhi izin) |
| M3 | `mgr0` `lolos` pada rute yang `kosong`-nya `ditolak` | Terbuka karena peran dasar Manajer. Laporan menandai baris yang juga `ditolak` bagi `sopir` |
| M4 | mode penuh: "{peran} Kosong" `lolos` pada rute yang `kosong`-nya `ditolak` | Sama dengan M3 untuk peran dasar lain |
| M5 | mode penuh: peran bawaan mendapat 403 berheader izin yang **dipegangnya** menurut `GET /api/access/roles`, atau `lolos` pada rute yang bagi `kosong` ditolak dengan izin yang tak satu pun dipegangnya | Server tidak mengikuti matriks |
| M6 | rute `tak_teruji` di luar daftar `tak_teruji`; rute `galat` di luar daftar `galat_dikenal` | Gerbang rute baru tidak teruji; galat baru |
| M7 | entri berkas harapan, `LOGIN_ONLY`, atau `PUBLIC_ALLOWLIST` yang rutenya tidak ada lagi, atau entri `menunggu_unit` yang rutenya kini menolak `kosong` | Daftar basi |
| M8 | akun uji mana pun mendapat selain 200 di `GET /api/auth/me` setelah sapuan | Ada rute yang mematikan sesi atau akun di tengah jalan |

**Berkas harapan** `sapuan_izin_harapan.json`:

```text
{
  "tolak_bukan_izin": {"GET /api/…": "alasan (kepemilikan / PT / status dokumen)"},
  "menunggu_unit":    {"POST /api/purchase-orders/{po_id}/approve": "KP-T4", …},
  "tak_teruji":       {"POST /api/…": "alasan isi tidak bisa dibuat otomatis"},
  "galat_dikenal":    {"GET /api/entities/count": "KP-17, diperbaiki PK-47"},
  "isi_contoh":       {"POST /api/…": {"json": {…}, "query": {…}}}
}
```

Isi awal ditulis dari jalan pertama pada HEAD unit ini, lalu tiap baris diberi alasan dengan tangan; baris tanpa
alasan ditolak skrip. `menunggu_unit` hanya untuk endpoint yang oleh PR-T3 diserahkan ke unit lain (PK-17, KF-T1,
KP-T4, PR-T4); unit pemegangnya menghapus barisnya, dan M7 memerah bila lupa.

**Perintah**

| Perintah (dari root repo) | Cakupan | Lama (perkiraan dari 0,06 dtk per permintaan pada sesi audit; diukur ulang di langkah 1) |
|---|---|---|
| `python backend/tests_mem/sapuan_izin.py` | mode cepat: lima akun pertama; ±7.800 permintaan | ±8 menit |
| `python backend/tests_mem/sapuan_izin.py --penuh` | ditambah 13 peran bawaan (GET) dan 12 peran "Kosong" (semua); ±39.000 permintaan | ±40 menit |
| `… --awalan /api/costing` | hanya rute berawalan itu (untuk iterasi dan uji) | detik |
| `… --keluaran /tmp/sapuan.json` | menyimpan hasil per rute per akun: `[kode, kelas, izin_diminta]` | — |

Keluaran layar: ringkasan per akun (jumlah tiap kelas), lalu tiap pelanggaran satu baris: kode M, metode, jalur,
akun, kode jawaban, 80 karakter pertama pesan.

**Pemasangan di gate** — `scripts/gate.sh`, di dalam blok `--full` (`scripts/gate.sh:865`): satu baris
`run_gate "guard:matriks_izin (INV-PERM-02, peran × endpoint)" "python backend/tests_mem/sapuan_izin.py"`. Bila
`python -c "import mongomock_motor"` gagal, baris itu memanggil `skip_gate` dengan alasan "mongomock-motor belum
terpasang (backend/tests_mem/requirements.txt)". Tingkat `--quick`, bawaan, dan `--ci` tidak berubah. Mode `--penuh`
dijalankan dengan tangan: sebelum unit yang mengubah izin, peran, atau gerbang endpoint dinyatakan `selesai`, dan
keluarannya dilampirkan di laporan unit itu.

**Aturan untuk endpoint baru** (ditulis juga di `backend/tests_mem/README.md`):

1. Pernyataan pertama handler adalah `require_permission` atau `require_any_permission` (`02` §3.1 Z1). Tidak perlu
   mendaftarkan apa pun; sapuan menemukannya sendiri.
2. Sengaja login-saja (milik sendiri, data rujukan, sesi): tambahkan ke `LOGIN_ONLY` dengan alasannya.
3. Sengaja tanpa sesi (perangkat, verifikasi publik): tambahkan ke `PUBLIC_ALLOWLIST` dengan alasannya.
4. Penolakan yang bukan soal izin (kepemilikan, PT, status) memakai 403 tanpa header izin; bila tercapai oleh akun
   `penuh` dengan id contoh, daftarkan di `tolak_bukan_izin`.
5. Isi permintaan yang tidak lolos validasi otomatis: beri contoh di `isi_contoh`, jangan menambah `tak_teruji`.
6. Izin baru: empat tempat menurut `02` §3.2; sapuan mode cepat harus hijau di commit yang sama.

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada.

### Layar

Tidak ada.

## Uji penerimaan

Rute sementara pada uji bukti-merah didaftarkan ke `server.app` di dalam tes (awalan `/api/_uji/`) dan dicabut
sesudahnya; sapuan dijalankan dengan `--awalan /api/_uji`.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | HEAD unit ini, berkas harapan terisi | `python backend/tests_mem/sapuan_izin.py` | Keluar 0; ringkasan memuat lima akun; tidak ada baris M |
| U2 | B | rute sementara `GET /api/_uji/tanpa-sesi` tanpa penegak apa pun | sapuan `--awalan /api/_uji` | Keluar 1; satu baris M0 untuk rute itu |
| U3 | B | rute sementara yang hanya memanggil `current_user` | sapuan | Keluar 1; satu baris M1 |
| U4 | B | rute sementara: `require_permission(request, "order", "view")` lalu menolak 403 bila peran bukan `manager` | sapuan | Keluar 1; satu baris M2 (akun `penuh` ditolak) |
| U5 | B | rute sementara yang meloloskan peran atau peran dasar `manager` tanpa memeriksa izin | sapuan | Keluar 1; satu baris M3 bertanda "juga tertutup bagi Sopir" |
| U6 | B | rute sementara `POST` dengan isi wajib ber-pola yang tidak dipenuhi contoh otomatis | sapuan; lalu tambahkan `isi_contoh` untuknya dan ulangi | Keluar 1 dengan M6; setelah diberi contoh keluar 0 |
| U7 | B | berkas harapan diberi entri `tolak_bukan_izin` untuk rute yang tidak ada | sapuan | Keluar 1; satu baris M7 |
| U8 | B | hasil buatan: peran bawaan Sales `lolos` di rute yang menuntut `accounting.view`; Finance 403 berheader `accounting.view` | panggil fungsi penilai langsung | Dua baris M5 |
| U9 | B | — | sapuan `--awalan /api/costing --keluaran <berkas>` | Dalam berkas: `GET /api/costing/wac` → `kosong` 403, `penuh` 200, `mgr0` 403, `sopir` 403 ("Tanpa Acuan" berizin 200; "Manajer Kosong" 403; "Sopir" 403) |
| U10 | B | — | sapuan mode cepat; baca bagian akhir keluaran | Kelima akun 200 di `GET /api/auth/me` (tidak ada M8); jumlah dokumen `users` dan `custom_roles` = seed + buatan sapuan |
| U11 | B | — | `python backend/tests_mem/sapuan_izin.py --penuh` | Keluar 0; untuk 13 peran bawaan tidak ada M5 — termasuk Manajer: tiap rute GET yang izinnya ia pegang tidak dijawab 403 berheader izin itu |
| U12 | B | — | `python -m pytest backend/tests_mem/test_PRT8_sapuan_izin.py -n 0` | Semua lulus dalam kurang dari 60 detik (U2–U8 ada di sini) |
| U13 | A | container backend dengan dan tanpa `mongomock-motor` | `bash scripts/gate.sh --full` | Dengan: baris `guard:matriks_izin` hijau. Tanpa: baris itu `SKIP` dengan alasan; hasil gate lain tidak berubah |
| U14 | B | — | `git diff --stat` unit ini | Tidak ada berkas di `backend/` selain `backend/tests_mem/` yang berubah — kode jawaban semua peran, termasuk Manajer, sama sebelum dan sesudah unit |
| U15 | B | catat waktu mulai dan selesai | mode cepat dan mode penuh | Lama jalan keduanya tertulis di laporan dan di `backend/tests_mem/README.md` |

## Langkah kerja

1. Pindahkan inti `t2_roles.py` dan `t9_tulis_tanpa_izin.py` menjadi `sapuan_izin.py` (pembuat peran dan akun,
   penyapu, pembuat isi); ukur lama jalan mode cepat.
2. Penilai M0–M8 sebagai fungsi murni atas hasil; `test_PRT8_sapuan_izin.py` dengan hasil buatan (U8) dan rute
   sementara (U2–U7). Merah dulu, lalu hijau.
3. Jalan pertama pada HEAD: tulis `sapuan_izin_harapan.json`, beri alasan tiap baris; baris M1 atau M3 yang **bukan**
   milik unit lain tidak boleh dimasukkan ke daftar — itu cacat yang dilaporkan sebagai temuan baru dan dicatat di
   `docs/blueprint/STATUS.md` bagian "Menunggu pemilik" bila tidak ada unit pemegangnya.
4. Baris gate di `scripts/gate.sh`; `README.md` dengan aturan endpoint baru. U13.
5. Mode penuh (U11); gate `--quick`; laporan memuat ringkasan kedua mode dan isi berkas harapan.

## Dokumen ikut berubah

`docs/blueprint/03_LINGKUNGAN_UJI.md` §3 (baris baru di tabel skrip: `sapuan_izin.py`, lama jalan terukur);
`CODEBASE_MAP.md`; `docs/KN_00_AGENT_QUICK_START.md` (daftar gate: `guard:matriks_izin` di tingkat `--full`).

## Di luar lingkup

- Memperbaiki rute yang ditemukan merah → unit pemegang rutenya (PR-T2, PR-T3, PR-T4, KP-T4, KF-T1, PK-17).
- Menghijaukan `guard:auth_coverage` (INV-AUTH-01) statik → PK-01 dan unit yang ditunjuknya; M0 di sini adalah
  pasangan uji jalannya.
- Penjaga "tiap pasangan izin punya pemeriksa" (INV-PERM-01) → PR-T5. Penjaga gerbang nama peran di layar
  (INV-ROLE-02) → PR-T7.
- Menguji hasil kerja rute tulis oleh pemegang izin (bukan hanya gerbangnya) → uji penerimaan tiap unit.
- Memasang `mongomock-motor` di image container → tidak dikerjakan (lihat PK-02).
- Skrip di `docs/audit/konfigurasi-peran-2026-11-13/bukti/` tetap sebagai arsip; tidak diubah.

## Asumsi dan risiko

- `ASUMSI:` lama jalan dihitung dari sesi audit (16 peran × 786 rute dalam ±12 menit). Karena itu sapuan ditaruh di
  tingkat `--full`, bukan di gate bawaan yang berjalan ±25 detik.
- `ASUMSI:` akun `penuh` tidak menyapu rute tulis, sehingga "rute tulis menolak pemegang izin" tidak dijaga sapuan
  ini; itu dijaga uji "Tanpa Acuan + izin → 200" di tiap unit.
- `ASUMSI:` saat unit ini dikerjakan PR-T6 mungkin belum selesai; karena itu pembacaan izin yang diminta punya dua
  jalur (header, lalu teks lama).
- `ASUMSI:` 404 dihitung "lolos gerbang" karena basis data tiruan hanya berisi seed; rute yang memeriksa izin
  **setelah** memuat dokumen akan terlihat lolos. Rute seperti itu melanggar Z1 dan memang harus muncul sebagai M1.
- `RISIKO:` sapuan meloloskan cacat karena daftar pengecualian terlalu longgar. Penangkal: tiap baris wajib beralasan,
  M7 membuang baris basi, dan isi berkas harapan dilampirkan di laporan untuk ditinjau reviewer. Membatalkan: cabut
  satu baris di `scripts/gate.sh`; tidak ada kode aplikasi yang bergantung pada alat ini.
