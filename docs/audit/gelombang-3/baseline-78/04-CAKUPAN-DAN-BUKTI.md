# Cakupan audit yang benar-benar tercatat

Source dibekukan pada `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Repository bergerak dari `d6da1a3d536228582645abb98aea19f3e491f300` selama sesi, sehingga pengujian utama, 17 counterexample lama, counterexample numerik, GET sweep dan 60 skrip regresi diulang pada kandidat terbaru. Hasil tahap lama dipertahankan sebagai histori. Database uji sintetis lokal digunakan; tidak ada transaksi produksi atau push perubahan aplikasi.

**Coverage perilaku 100% belum tercapai.** Inventaris semua file sudah tersedia, tetapi inventaris, parse, build dan satu baris handler yang dieksekusi bukan bukti bahwa semua kode dan semua flow bisnis sudah benar.

| Lapisan | Hasil pada kandidat terbaru | Batas makna |
|---|---|---|
| Inventaris tracked | 5,824 file; hash per file | File nonkode dan artefak audit juga termasuk; bukan pembacaan semantik seluruh baris |
| Parse source | 1.260 Python + 859 JavaScript = 2.119 file; tanpa parse error | Tidak membuktikan logika atau rendering |
| Inventaris statis | 13.151 fungsi; 1.411 decorated routes; 1.477 literal API calls frontend | Route statis berbeda denominator dari registered API methods; panggilan dinamis belum seluruhnya dipetakan |
| Frontend → registered API → service |1431/1477 literal calls terpetakan; 46 belum |Menggunakan full route prefix dari aplikasi terdaftar dan literal alias yang tidak ambigu; dynamic action/helper tetap unresolved |
| Registered API methods | 1410 | Termasuk kombinasi route/method; bukan jumlah business flow |
| Handler dengan bukti body dieksekusi | 1024 | Guard/error juga dapat memasuki body; tidak otomatis successful authorized flow |
| Mutation methods | 772; body tercatat pada 398; 374 tanpa bukti body | CSV menyimpan setiap route yang masih memerlukan pengujian lifecycle |
| GET sweep | 589/638 dieksekusi; 539 pernah mendapat 200; 49 belum dieksekusi | Angka benar harus dicek dengan oracle; HTTP 200 saja tidak cukup |
| GET exceptions / HTTP >=500 | 0 exceptions; 0 route mencatat status >=500 pada sweep | Hanya fixture sweep ini, bukan jaminan tidak ada error di produksi |
| Full pytest | 1539 pass / 484 fail / 76 skip / 173 error; 2272 testcase records | 484 kegagalan bukan 484 bug; fixture dan test contract perlu adjudikasi |
| Tiga modul tes baru | 14 pass / 3 fail / 5 skip | Ada ketergantungan hardcoded fixture dan fallback PR; bukan seluruh real fulfillment E2E |
| Core replay | 309/310 pass, 15 skrip | Satu fixture RF-05 tanpa tag ditolak oleh aturan wajib tag |
| Wave-2 replay | 82/82 pass, 4 skrip | Kasus retry/failure yang lebih luas tetap mempunyai 17 counterexample lama |
| Extended replay | 414/455 pass, 41 fail, 3 nonzero/timeout, 41 skrip | Seluruh nonpass dipertahankan dalam register, tidak diubah menjadi klaim bug otomatis |
| Counterexample dan kontrol | 209 observasi: 122 selisih numerik/state, 70 kontrol pass, 17 replay fault lama | Beberapa observasi milik satu temuan; bukan 209 bug |
| Backend statement | 50,308/102,029 = 49.31% | Denominator tetap 603 file Python tracked; backend/tests dikecualikan, script test/POC di level atas tetap termasuk |
| Backend branches | 11,898/29,916 = 39.77% | Coverage tercatat dari proses uji dan server lokal; bukan persentase business correctness |
| Backend runtime/startup, denominator terpisah |480 files; statement 50,117/72,221=69.39%; branch 11,846/23,008=51.49% |Same execution record; test/POC/offline files dipisahkan menurut rule dan daftar file eksplisit |
| Frontend build | Compiled successfully | Dependency cache lokal dipakai, ESLint plugin dinonaktifkan; bukan fresh locked install atau lint bersih |
| Frontend numerik | Function/expression asli diekstrak dengan Babel; producer API diuji untuk kasus OrderDashboard dan konversi PO | Tidak ada bukti seluruh navigasi React di browser, visual rendering, export atau printer |
| Perangkat / data produksi | Tidak diuji | RFID reader/gate/printer fisik, reconnect/offline dan rekonsiliasi data produksi tetap perlu uji |

## Register cakupan

`all-file-coverage.csv` mencatat seluruh file dan metode pemeriksaan. Kolom `specific_finding_source_review` berarti source terkait temuan ditelaah, bukan seluruh baris file disertifikasi. `frontend-api-lineage.csv` memperluas mapping hingga service delegation statis; unresolved tetap disebut. `latest/evidence/registered-route-execution.csv` menyimpan seluruh handler dan bukti body execution. `latest/evidence/get-combined-results.json` memuat route GET beserta percobaan dan alasan yang tersisa.

Pemetaan literal memakai route yang benar-benar terdaftar beserta prefix router, bukan hanya path pada decorator. Kolom matching_route dan mapping_basis mencatat ekspansi alias template/literal level modul yang dianalisis dengan Babel, tanpa binding/parameter shadow dan dideklarasikan sebelum caller. Nested alias, helper dinamis dan pilihan action tetap unresolved; tidak dipaksa cocok memakai wildcard. Peta ini hanya kontrak dan delegasi statis hingga tiga tingkat, bukan proof numeric source/flow atau browser success untuk semua caller. ID temuan pada lineage merupakan asosiasi file sumber, bukan verdict bahwa setiap panggilan dalam file itu salah; verdict spesifik mengikuti counterexample dan acceptance. Register binding ada pada latest/evidence/frontend-literal-prefixes.json.

Coverage server di-flush ketika server uji dihentikan dengan tertib. Path Windows dinormalisasi saat merge agar source yang sama tidak dihitung sebagai file berbeda. Laporan hanya memakai source kandidat terbaru. Hasil tahap d6da disimpan terpisah dan tidak dijumlahkan ke persentase kandidat a904.

Denominator 603 juga mengandung top-level test/POC/audit scripts, walaupun direktori backend/tests dikecualikan. Salinan tes di sandbox tidak diatribusikan otomatis ke path file tes asli. Agar pembaca tidak mengira seluruh statement yang belum tercatat berasal dari aplikasi, backend-coverage-by-layer.json memisahkan runtime/startup, offline scripts dan test/POC/audit source dengan rule serta seluruh file list. Persentase runtime yang lebih tinggi memakai denominator berbeda pada bukti yang sama; bukan tambahan coverage atau sertifikasi flow. Semua angka full 603 tetap dipertahankan.

## Yang menghalangi penutupan 100%

1. 374 mutation methods belum mempunyai bukti body execution; handler yang pernah masuk pun belum seluruh state/role/parameter/fault/reversal-nya teruji.
2. 49 GET membutuhkan fixture atau parameter spesifik, termasuk dokumen, foto, sesi dan referensi yang koheren.
3. 657 testcase nonpass perlu fixture deterministik dan adjudikasi lebih jauh; register otomatis belum menjadi verdict manual seluruh kasus.
4. Semua layar membutuhkan validasi angka rendered, filter, paging, export, empty/null/error dan perubahan periode pada role/entity yang sesuai.
5. Jalur RFID dan pencetakan memerlukan perangkat sebenarnya; kebenaran software session tidak membuktikan hasil fisik di gate.

Laporan ini menyimpulkan masalah yang terbukti dan batas uji. Ia tidak memberikan sertifikasi bahwa seluruh code dan semua flow telah selesai diuji.

## Batas verifikasi browser pada sesi ini

Browser helper gagal sebelum navigasi dengan pesan `failed to write kernel assets: The system cannot find the path specified. (os error 3)`. Satu reset dan percobaan ulang memberikan error sama. Frontend/backend lokal sudah disiapkan, tetapi **DOM, screenshot, angka rendered dan navigasi UI tidak terverifikasi**. Ini kegagalan lingkungan alat, bukan temuan bug aplikasi. Bukti dua percobaan tersedia pada `latest/evidence/browser-ui-attempt.json`. Original-JavaScript probes dan API tests tetap berlaku sesuai batasnya; belum menggantikan browser/perangkat fisik.
