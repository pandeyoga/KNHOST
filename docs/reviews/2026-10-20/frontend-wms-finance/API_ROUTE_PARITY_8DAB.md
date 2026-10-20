# Pemetaan handler API frontend terhadap ERP terbaru

Baseline: **`8dab383f764df80737bfe02f887422b3fd72aa70`**, snapshot `work/KNHOST-frontend-audit-2026-10-20`.  
Sumber kontrak: respons OpenAPI aplikasi lokal terbaru di port 8020, disimpan oleh audit induk pada `openapi-8020-8dab.json` — **1.328 path**.

## Hasil pemeriksaan

**Tidak ditemukan ketidakcocokan method/path baru yang dapat dikonfirmasi dari inventaris ini.** Hasil ini tidak menutup tujuh temuan frontend sebelumnya: kontrol dapat memanggil path yang benar tetapi tetap gagal bekerja karena callback, izin, state tampilan, atau penyajian angka yang salah.

| Pemeriksaan | Jumlah |
|---|---:|
| Berkas `.js`/`.jsx` di seluruh `frontend/src` yang berhasil diparse | 953 |
| Kesalahan parse | 0 |
| Lokasi panggilan HTTP anggota axios/API client yang terinventaris | 1.662 |
| GET | 865 |
| POST | 633 |
| PATCH | 67 |
| DELETE | 68 |
| PUT | 29 |
| Bentuk method/path sesuai route OpenAPI | 1.596 |
| Path dinamis memiliki kemungkinan route/method sesuai, perlu nilai aktual | 21 |
| Path dari helper, variabel atau query dinamis yang tidak dipastikan otomatis | 45 |
| Kandidat ketidakcocokan yang tersisa setelah pemeriksaan | 0 |

Jumlah di atas adalah **lokasi panggilan**, bukan jumlah endpoint unik dan bukan jumlah transaksi yang telah diuji. “Sesuai” hanya berarti bentuk URL serta method tersedia dalam kontrak. Itu tidak membuktikan payload, hak akses, nilai ID, atau hasil bisnis benar.

Pemeriksaan tambahan menelusuri pilihan dinamis yang terbatas dari kode lalu membandingkan **92 kombinasi method/path** dengan OpenAPI. Seluruh kombinasi memiliki route dengan method yang sesuai. Kombinasi ini memperjelas sebagian lokasi dinamis di atas; tidak boleh dijumlahkan sebagai 92 lokasi panggilan baru atau dianggap menuntaskan seluruh 45 lokasi dinamis.

## Pemeriksaan dinamis yang dilakukan

| Kelompok | Yang ditelusuri |
|---|---|
| Setup kehadiran | Tiga peta shift/geofence/device: GET/POST daftar, PATCH/DELETE item. |
| Absensi mandiri | `clock-in` dan `clock-out` yang dikirim ke helper action. |
| Landed cost dan tagihan supplier | Peta submit, approve, reject, cancel, pay. |
| Retur supplier | Submit/approve/reject dan ship-to-supplier/supplier-accept/supplier-reject/goods-back. |
| Purchase requisition | Submit/approve/cancel dari helper path. |
| Kasus Finance | Assign/note/reject/reopen. |
| Pinjaman antar-PT dan retur antar-PT | Disburse/cancel/repay; approve/warehouse-task. |
| Uang muka dan pertanggungjawaban | Submit/approve/reject/disburse/pay-reimburse. |
| Desain mobile | Assign/approve/submit/reject/cancel. |
| Barang masuk GRN | Action read/manual-entry/start-count/finish-count/reopen/close dan path bertingkat lines/rolls/discrepancies. |
| Persetujuan | Kombinasi approve/reject untuk price approval, sales return, purchase return. |
| Eskalasi gudang | Resolve-escalation inbound/outbound. |
| Query tambahan | Suffix filter/entitas pada daftar tugas, transfer, dashboard, notifikasi, settings, dan metadata R&D. |
| Scheduler dan enum | Nilai literal `all` pada run job dan enum `entity_type` pada route generik. |

## Kandidat yang diperiksa dan dikeluarkan

### 1. Absensi `POST /hr/attendance/{action}`

`EmployeeSelfService.jsx:54` menggunakan action dinamis. Bila hanya dibandingkan dengan route generik `/hr/attendance/{att_id}`, seolah hanya PATCH tersedia. Namun nilai action dari tombol adalah **clock-in/clock-out**, dan kedua route POST tersebut tersedia. Ini bukan salah method.

### 2. Penghapusan baris/roll GRN

`wms/grn/grnApi.js:68` menerima `path` sebagai keseluruhan suffix, bukan satu segmen ID. Pemanggil `GrnCountPanel.jsx:66`, `GrnLineCard.jsx:50`, dan `GrnLineRow.jsx:204` mengirim `rolls/{id}` atau `lines/{n}`. Route DELETE bertingkat tersebut tersedia. Memaksa `{path}` sebagai satu segmen menimbulkan false positive; helper ini dinyatakan perlu resolusi pemanggil.

### 3. Scheduler “jalankan semua”

Frontend `admin/scheduler/SchedulerView.jsx:117` memakai `/scheduler/jobs/all/run`. Backend `routers/scheduler.py:42–46` memiliki route dinamis dan menangani `job_id == "all"` secara eksplisit. Path ini sah meskipun kata `all` tidak muncul sebagai path literal tersendiri dalam OpenAPI.

### 4. Jenis badan usaha

`settings/entities/entityApi.js:102` meminta `/enums/entity_type`; backend `routers/enums.py:111` menyediakan `/enums/{name}`. Perbandingan path literal tanpa parameter akan salah menyebutnya endpoint yang hilang.

## Batas yang tetap terbuka

- Tidak menjalankan 1.662 request. Tidak ada penulisan database maupun perubahan aplikasi pada subtugas ini.
- Tidak menganggap 45 path dinamis sebagai bug. Beberapa URL berasal dari metadata server, helper umum, attachment privat, atau antrean offline sehingga memerlukan konteks saat dipakai.
- Pemeriksaan difokuskan pada `axios.get/post/put/patch/delete` dan alias default API client. Pemanggilan bentuk `axios({ method, url })`, `fetch`, WebSocket, serta wrapper lain tidak dihitung sebagai lokasi HTTP anggota dalam tabel.
- Tidak memvalidasi seluruh query, body, response schema, hak akses, scope, urutan route pada runtime, atau dampak bisnis. Method/path tersedia masih dapat menghasilkan penolakan yang sah atau error implementasi.
- Tidak ada klaim kelulusan seluruh tombol ataupun flow ERP dari pemeriksaan kontrak ini. Pengujian browser dan transaksi lokal tetap menjadi bukti terpisah.

## Artefak

- `api-route-inventory-8dab.json`: seluruh lokasi panggilan, method, path, status pemetaan, dan daftar yang belum diresolusikan otomatis.
- `api_route_inventory.cjs`: pemeriksaan AST dan normalisasi konservatif.
- `bounded-route-checks-8dab.json`: 92 kombinasi dinamis yang ditelusuri, path OpenAPI yang cocok, sumber kode, dan hash kontrak OpenAPI.
- `bounded_route_checks.py`: pemeriksaan kombinasi terbatas tanpa request.
- `openapi-8020-8dab.json`: kontrak dari aplikasi lokal terbaru yang digunakan sebagai acuan.
