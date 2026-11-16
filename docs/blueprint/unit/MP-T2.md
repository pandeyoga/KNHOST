# MP-T2 — Satu wizard SPK makloon yang membaca rute; semua pilihan tersaring tahap

| | |
|---|---|
| Gelombang | Modul master produk & makloon |
| Jenis | perbaikan + fitur |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | MP-T1 |
| Menutup temuan | Telusur 16 Nov P10; audit makloon 16 Nov (dua pintu, dropdown asal, alasan qty manual palsu, judul "Buat PO") |
| Keputusan | K-57, K-59, K-61 |
| Standar | `02` §3, §4, §6 |
| Lingkungan uji | B + A (penerimaan makloon butuh MongoDB asli) + peramban |

## Tujuan

SPK makloon dibuat dari satu wizard (dua mode: proses saja · beli + proses). Memilih barang hasil mengisi langkah dari
rute utama (tahap, mitra, kontrak, resep); setiap pilihan yang tersisa tersaring tahap sehingga langkah yang tidak sah
tidak bisa dipilih.

## Keadaan sekarang

- Dua pintu: wizard `frontend/src/features/purchasing/makloon/MakloonWizard.jsx` (tab Order Makloon, banyak langkah,
  tanpa pemilih resep, memaksa "alasan qty manual") dan modal `frontend/src/features/purchasing/MakloonOrderCreateModal.jsx`
  (menu Pesanan Pembelian `features/admin/po/POCreateMenu.jsx:14-17`, satu langkah + barang sisa + resep, berjudul "Buat
  PO"). [dijalankan 16 Nov, potret 1280/390]
- `MakloonStepEditor.jsx`: pilihan tahap tidak disaring tahap bahan; `ProductSelect` hasil tanpa `stage` padahal
  komponennya mendukung (`frontend/src/components/ProductSelect.jsx`); tahap bawaan "Tenun" untuk bahan greige. [dijalankan]
- Server menerima langkah yang tahapnya tidak sambung hanya dengan peringatan (`backend/services/makloon_order_service.py`
  `_resolve_stage` jalur 3). [dibaca]

## Perubahan

### Server
- `POST /api/makloon-orders` memvalidasi rantai tahap dengan fungsi yang sama dengan rute (`product_route_service`
  R3/R4/R6) untuk SPK baru; SPK lama tidak dihitung ulang.
- `GET /api/makloon-orders/plan-from-route?product_id=&qty=` → langkah terisi dari rute utama (tahap, mitra, kontrak,
  resep, bahan masuk), beserta peringatan "kontrak belum ada" per langkah.
- SPK draf tanpa mitra boleh disimpan; kirim bahan ditolak "Isi mitra langkah <n> sebelum mengirim bahan." (K-61).

### Layar
- Satu komponen wizard dipakai kedua pintu; modal lama dimatikan (pemanggil dialihkan, dibuktikan dengan pencarian).
- Langkah 1 "Barang yang dibuat" → isi otomatis dari rute; tombol "Ubah langkah" membuka penyunting langkah yang
  pilihannya tersaring (`step-options` MP-T1, `ProductSelect stage`).
- Judul pop-up "Buat SPK Makloon"; aksi utama di kanan bawah; "Batal" sekunder; istilah tanpa WIP/Issue/Step.

## Uji penerimaan

| ID | Lapis | Persiapan | Langkah | Hasil |
|---|---|---|---|---|
| U1 | B | rute utama G→PFP@A→printing@B | `plan-from-route` produk jadi 100 | 2 langkah terisi mitra A, B |
| U2 | B | — | POST SPK langkah printing dari bahan greige | 400 pesan rantai tahap |
| U3 | B | SPK draf tanpa mitra | simpan · kirim bahan | 200 · 400 pesan K-61 |
| U4 | layar | data acuan | buka kedua pintu | komponen sama; pilihan tahap/hasil tersaring; potret 1280/390 |

## Di luar lingkup
Paket kerja end-to-end, mitra→mitra, tarif borongan → MP-T4.

## Asumsi dan risiko
RISIKO: SPK yang dulu lolos dengan peringatan kini ditolak — hanya berlaku untuk SPK baru.
