# Cakupan audit dan batas bukti

Kandidat `d6da1a3d536228582645abb98aea19f3e491f300`; pembanding `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`. Database produksi tidak digunakan; semua perubahan uji berlangsung pada database Mongo lokal terisolasi. File aplikasi tracked tidak sengaja diubah oleh audit. Fixture, bootstrap, test-copy dan artefak audit berada terpisah.

| Lapisan | Bukti | Apa yang belum dibuktikan |
|---|---|---|
| Inventaris | 5114 file tracked, SHA256 per file | Membaca semua nama/hash bukan semantic review seluruh baris |
| Sintaks | 1.249 Python AST; 855 JavaScript AST; tidak ada parse error pada inventory | Build, business correctness, rendering dan concurrency tidak ditentukan sintaks |
| Kontrak | 1.409 decorated routes; 1.475 literal frontend API calls dipetakan | Ekspresi dinamis, service delegation dan semantic contract perlu review khusus |
| GET runtime | 637 GET: 588 dieksekusi, 538 sukses pada minimal satu fixture; tidak ada500/exception pada sweep | 49 route belum dieksekusi karena parameter/fixture/callback; HTTP200 tidak membuktikan angka |
| Counterexample | 17 celah lama + kasus sumber data/JS baru; lihat tracker dan JSON | Teruji pada fixture tertentu, bukan seluruh kombinasi data produksi |
| Regression core | 15 skrip, 310 assertion terekstrak, 299 pass / 11 fail | Assertion dapat bergantung fixture/aturan lama |
| Regression extended | 41 skrip, 448 assertion, 403 pass / 45 fail; 4 exit nonzero/timeout | Beberapa fixture/prasyarat/externalfont tidak tersedia; jangan menghitung sebagai bug |
| W2 replay | 4 skrip; 82 / 82 assertion PASS dari log asli | Acceptance requirement dapat masih berbeda dari kebijakan override yang dites |
| Full pytest kandidat | 1.549 pass, 467 fail, 72 skip, 173 error | Banyak error fixture/event-loop/login; 467 bukan jumlahbug |
| Full pytest baseline | 1.540 pass, 463 fail, 73 skip, 185 error | Sama candidate tests; stateful fixtures dan nondeterminisme belum dieliminasi |
| Backend Python line/branch | 35329 / 101803 statement; 6497 / 29818 branch | In-process coverage, backend/tests excluded. Seed/script ikut denominator; server terpisah belum tentu flush. Bukan coverage UI |
| Frontend numeric probes | Expression/function asli Babel: period slicing, response race, redacted amount | Tidak menjalankan full browser navigation/React rendering/printing |

**Coverage 100% belum terbukti dan tidak diklaim.** Inventaris seluruh file selesai; validasi semua branch, semua parametrized mutation, seluruh browser state, perangkat RFID/printer, serta data produksi tidak setara dengan inventaris tersebut. Tingkat coverage tiap file tersedia di `all-file-coverage.csv`; route yang belum dijalankan tersedia pada `evidence/get-combined-results.json`.

## Pengelompokan kegagalan

Perbandingan menghasilkan 23 perubahan status, 5 kandidat nonpass baru dan 13 perubahan menjadi pass. Ini sinyal untuk ditelusuri, bukan jumlah regresi atau bukti penyebab patch. Semua testcase dan traceback disimpan; label otomatis di CSV hanya petunjuk triage. Penjelasan manual untuk perubahan baru ada di `06-TRIAGE-PENGUJIAN.md`.

Collection `test_wilayah_extra.py` (module-level SystemExit) dan `test_notifications_iter33.py` (subprocess/module side effect) dikeluarkan dari full run dan dicatat sebagai batas. Collection failure pada dua modul lain tetap tercatat. Assertions tidak diubah; perubahan test copies hanya path lokal, API lokal dan database terisolasi, dengan manifest adaptasi.

## Yang diperlukan untuk menutup celah cakupan

1. Fixture yang koheren untuk 49 GET yang tersisa; inventaris POST/PUT/PATCH/DELETE pada source harus dijadikan state-machine test, bukan dipanggil sembarang pada DB kosong.
2. Suite deterministik: per-module/event-loop DB client dan akun role fixture sesuai permission terbaru; hilangkan ketergantungan state demo antar tes.
3. Browser E2E pada tiap role/entity, perubahan filter cepat, page-size, export, empty/null/error dan tanggal WIB. Counterexample JS di sini hanya memvalidasi logic yang diekstrak.
4. RFID hardware passage/session, anti-duplicate, offline/reconnect serta printer/tag verification dengan perangkat sebenarnya. Cached GREEN software tidak otomatis membuktikan gate fisik terbuka.
5. Reconciliation terhadap anonymized production snapshot: roll/balance/movement, SO-shipment-GL-AR, PO-receipt-bill-AP, payroll/accrual dan fact snapshots.

Tidak ada status `verified_fixed` baru diberikan hanya karena file tidak berubah, build sukses, endpoint200 atau test suite yang menggunakan oracle tidak lengkap.
