# Tambahan Gelombang 2 — kebutuhan klien dan W2-025

Tanggal: 2026-10-03. Snapshot: `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Baca [memo 12 poin](25_MEMO_JAWABAN_KEBUTUHAN_KLIEN.md) untuk konteks bisnis. Status berikut belum menyatakan perbaikan selesai. Kebutuhan fitur/SOP tidak dihitung sebagai defect runtime baru.

## W2-025 — pembatasan lini R&D hanya efektif pada daftar

**Prioritas P1; status open; poin klien 1.** Akun dengan izin R&D dan hanya lini woven dapat membuka serta mengubah sample printing dalam entitas yang sama. Pemisahan jobdesk tidak ditegakkan konsisten di backend. Dampak terbukti adalah pembacaan detail dan perubahan judul; belum mengklaim seluruh aksi approval atau akses lintas entitas ikut lolos.

### Lokasi dan penyebab

- `backend/routers/rnd.py:294`: daftar sample memakai penyempitan scope lini.
- `backend/routers/rnd.py:80`: `_sample_guard` memeriksa akses entitas, tanpa pemeriksaan lini sample.
- `backend/routers/rnd.py:372,384`: detail dan patch menggunakan guard tersebut. Izin modul dan entitas dapat lolos walaupun lini dokumen di luar assignment akun.
- `backend/services/line_scope.py`: helper scope tersedia; aturan legacy lini kosong/assignment kosong perlu dipertahankan atau dimigrasikan secara eksplisit, bukan diubah tanpa analisis.

### Reproduksi dan hasil

Harness: [wave2_rnd_line_scope.py](repro/wave2_rnd_line_scope.py); bukti: [rnd-line-scope-results.json](rnd-line-scope-results.json). ASGI aplikasi asli, indeks aplikasi dan Mongo sintetis lokal; tidak memakai data pengguna atau layanan produksi.

1. Siapkan dua sample draft dalam entitas A: W berlini woven dan P berlini printing.
2. Akun U mempunyai izin view/create R&D, entitas A dan `allowed_line_codes=[woven]`.
3. GET daftar sample hanya mengembalikan W: kontrol positif `W2-RNDLINE-C01`.
4. GET detail P mengembalikan HTTP 200 dan lini printing: `W2-RNDLINE-F01`.
5. PATCH judul P mengembalikan HTTP 200 dan perubahan terbukti tersimpan: `W2-RNDLINE-F02`.

Field `expected` pada JSON historis adalah ekspektasi **reproduksi perilaku cacat**, bukan kontrak produk yang benar. Pada validasi perbaikan, akses P harus ditolak secara konsisten (403 atau 404 sesuai standar aplikasi), tanpa mutasi; W harus tetap dapat diakses. Simpan hasil kandidat terpisah, jangan menimpa bukti ini.

### Perbaikan yang dituju

Gunakan guard entitas+lini+izin aksi yang konsisten pada pembacaan dan perubahan dokumen. Telusuri endpoint turunan sample/round/attachment/decision/spec yang mengakses dokumen induk; jangan menyimpulkan semuanya cacat tanpa pemeriksaan. Jangan hanya menyembunyikan tombol atau menambah filter daftar. Hindari pengecualian berdasarkan nama role tertentu yang melewati custom permission.

Kriteria selesai: woven-only tidak dapat membaca/mengubah printing; operasi woven tetap berjalan; multi-line yang sah tetap berjalan; custom role mengikuti izin; entitas tetap dibatasi; dokumen/assignment tanpa lini mengikuti kebijakan legacy yang terdokumentasi. Bukti kandidat harus menyertakan commit, request/status, snapshot sebelum-sesudah dan regresi jalur turunannya.

## Register kebutuhan bisnis

ID W2-REQ dipisahkan dari ID W2-001…025. Status `source_gap` berarti gap pada jalur source yang ditelusuri; bukan pembuktian semua jalur runtime tidak mendukung. `needs_validation` tidak boleh langsung diubah menjadi bug terkonfirmasi. Bukti file dan penjelasan rinci terdapat pada nomor memo terkait.

| ID | Poin | Status / kebutuhan | Kriteria penerimaan |
|---|---|---|---|
|W2-REQ-01|1|Sebagian: histori akun tersedia; pelaksana fisik dan hak per jenis sampling belum terpisah secara terbukti|Akun Wiwi/Tita dapat ditelusuri; bila input mewakili orang lain, recorded_by berbeda dari performed_by. Hak jenis uji hanya ditambah bila memang dibutuhkan, terpisah dari lini.|
|W2-REQ-02|2,3,8,12|Tata kelola: standar nama, stage, warna dan data legacy|Kamus field dan penamaan disepakati; SKU stabil; grey/PFD/PFP tidak dicampur dengan line/fabric_type; supplier color/lot tetap tersimpan; migrasi mempunyai preview, laporan konflik dan jejak perubahan.|
|W2-REQ-03|3|Needs validation: default jenis sampling belum membuktikan hard gate ACC/rilis|SKU hasil MD hanya rilis setelah semua uji yang diwajibkan untuk spesifikasi/lini tersebut ACC. Bahan standar tetap dapat dibuat langsung. Uji jalur decide, approve_spec langsung, release, gagal pembuatan master dan retry.|
|W2-REQ-04|4|Source gap UI: agregat backend belum menjadi seluruh angka utama POV sales|Sales melihat available/reserved/incoming grup tanpa owner; alokasi tetap menjaga owner dan interco; stok yang sama tidak dihitung/dijanjikan dua kali.|
|W2-REQ-05|5|Source gap UX: create PO mengikuti entitas aktif|Meja kerja MD lintas entitas yang diizinkan dengan buyer eksplisit, lini terjaga, SO/PR tertaut dan rekening/dokumen sesuai buyer. Jangan menebak buyer dari lokasi stok.|
|W2-REQ-06|6|Sebagian: variance/short-close/amendment ada; tindak lanjut MD dan Finance belum utuh|Kasus pesan1000 terima960 menghasilkan keputusan tunggu/revisi/short-close yang terlihat. MD penanggung jawab menerima tugas. Nilai PO, received, tagihan, DP, saldo utang dan koreksi tidak disamakan otomatis.|
|W2-REQ-07|7|Source gap: belum ada reservasi bahan pada jalur rencana/create MKO yang ditelusuri|Material dihitung menurut resep/unit/yield, dicadangkan tanpa issue fisik; issue memakai reservasi sama; cancel/replan melepasnya; dua order tidak memakai kapasitas bahan sama.|
|W2-REQ-08|10,11|Sebagian + bug lama: routing dan SJ ada; kewajiban tag serta UAT multi-gudang belum tertutup|Store dan cross-dock sama-sama memerlukan tag; source SO tidak otomatis berarti bebas QC/GRN. Shipment/SJ sesuai muatan nyata. Tautkan RFID-03 lama, bukan membuat bug duplikat.|
|W2-REQ-09|9|Keputusan SOP: prefix FEFO dan opsi potong berbeda dari harapan kombinasi optimum|Total roll/panjang/delta terlihat; pengguna menyetujui pembulatan; aturan potong eksplisit; 900 atau905 dapat benar menurut urutan, jangan hard-code905.|

Printer tiap gudang dan penyatuan SJ termasuk konfigurasi/SOP W2-REQ-08, bukan otomatis cacat software. Alias kode warna customer belum cukup jelas untuk ditetapkan sebagai requirement wajib; kemampuan katalog warna customer tidak membuktikan alias kode per pelanggan.

## Batas pembuktian tambahan

[Probe penjelasan](client-requirements-probes.json) menguji dua urutan pemilihan roll, perilaku helper lini dan patch lot. Empat observasi ini tidak dimasukkan ke hitungan checkpoint audit. Hanya tiga checkpoint R&D baru yang menambah total dari239 menjadi242:174 control,36 defect reproduction,26 wave1_extension,6 policy_observation;25 ID temuan W2. Ini bukan persentase coverage.

Browser, printer/reader fisik, full lifecycle sampling, konsolidasi tiga gudang dan settlement selisih PO pada deployment belum disahkan. Temuan Wave1/Wave2 lama tetap open sampai ada bukti kandidat; keberadaan fitur bukan bukti seluruh proses bebas cacat.
