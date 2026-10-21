# Rencana perbaikan temuan uji pra-UAT — ERP Kain Nusantara

Pendamping *Panduan UAT End-to-End v2.0* (KN-UAT-E2E-002) · disusun 21 Oktober 2026.

## Konteks pengujian

| Hal | Isi |
|---|---|
| Kandidat uji pertama | `main @ af24f9c` + perubahan lokal FE-01 (Pesanan Khusus), 21 Okt 02.00–02.45 WIB |
| Uji ulang | `main @ a3f7936` + perubahan lokal sesi lain (belum di-commit), 21 Okt 03.05 WIB |
| Data | data acuan lokal (`scripts/dev_restore_demo.sh`), tanpa reset selama uji |
| Cara | akun per peran (bukan Admin) lewat API aplikasi + layar POS / Meja Admin Sales |
| Skrip uji | `uji_pra_uat/` (dijalankan di container backend: `cat kn.py t_xxx.py \| docker compose -f docker-compose.dev.yml exec -T backend python -`) |

Status hasil uji ulang: **F-01, F-02, F-03, F-05, F-06, F-07, F-09, F-10, F-11, F-12, F-16 masih terulang** di `a3f7936`.
F-04, F-08, F-13, F-14, F-15, F-17 belum diuji ulang. Modul Pesanan Khusus (alur F) tidak diuji karena sedang
diubah sesi lain.

Sesuai protokol repo (`docs/reviews/README.md`): implementer **cek ulang setiap temuan di HEAD** sebelum
mengubah kode, tulis tes merah-dulu, commit per temuan, laporan di `hasil/`, status maksimal
`implemented_pending_review`. Jangan mengedit berkas yang sedang dikerjakan sesi lain (cek `git status`).

## Urutan kerja

| Gelombang | Temuan | Syarat mulai | Estimasi |
|---|---|---|---|
| 1 — wajib sebelum UAT | F-09, F-11, F-12, F-05, F-03, F-01 | langsung | ± 5–6 hari kerja |
| 1b | F-10 | keputusan owner Q-02 (blok keras / peringatan; DP minimal) | 2–3 hari |
| 2 | F-06, F-14, F-15, F-16, F-08 | keputusan Q-01, Q-03, Q-04, Q-05 | ± 4 hari |
| 3 | F-07, F-02, F-04, F-17, F-13 | — / konfirmasi Q-06 | ± 1,5 hari |

Skala: XS < ½ hari · S ≈ 1 hari · M ≈ 2–3 hari.

---

## Gelombang 1

### F-09 · P1 · Entri persetujuan yang ditolak mengunci SO selamanya — M
**Reproduksi** (SO-00039, ulang SO-00083): Sales minta harga khusus 18.000 → Admin Sales verifikasi & ajukan →
Manajer **tolak** → Sales ajukan ulang 19.000 → Manajer **setujui** (harga & total berubah) →
`POST /sales-orders/{id}/approve` → **409 APPROVAL_REJECTED**. Edit/Override SO dan ajukan ulang tidak membuka.
`submit-for-approval` saat itu memberi 409 *INVALID_TRANSITION* yang membingungkan.

**Akar masalah**
- `backend/services/so_approvals.py:62–77` `summarize()` menghitung **semua** entri berstatus `rejected`.
- `backend/routers/so_approvals.py:183–190` `attach_order_price` hanya men-*supersede* entri `pending`.
- `request_credit_approval` (`so_approvals.py:200`) tidak menyentuh entri kredit yang ditolak.
- `sales_orders_extra.py:473` approve menolak bila `has_rejected`.

**Perbaikan**
1. Saat entri baru dibuat (harga khusus: tipe + produk sama; kredit: tipe sama), tandai entri `rejected`
   sebelumnya `superseded` (`superseded_by` = id entri baru); simpan riwayat utuh.
2. Bila entri terakhir tiap (tipe, produk) disetujui dan tak ada pending → `advance_so_if_all_approved`.
3. Pesan 409 submit saat `waiting_approval`: arahkan ke Pusat Persetujuan.

**Uji regresi** (`backend/tests/test_f09_resubmit_after_reject.py`): tolak → ajukan ulang → setujui → SO
*approved*; tolak tanpa ajukan ulang tetap memblokir (regresi KN-D02); kredit ditolak → ajukan ulang → setujui.

### F-11 · P1 · Gudang & QC tidak bisa memproses perjalanan & QC retur — S
**Reproduksi**: `warehouse@` `POST /sales-returns/{id}/journey/scan` → 403 *sales_return.update*;
`qc@` `POST /sales-returns/{id}/inspect/start|complete` → 403.

**Akar masalah**: `backend/permissions_config.py` (peran `warehouse`, `qc` tanpa `sales_return`);
`backend/routers/sales_returns.py` journey/scan & inspect/* hanya `require_permission("sales_return","update")`.

**Perbaikan**: `require_any_permission([("sales_return","update"),("wms","scan")])` untuk journey/scan;
`[("sales_return","update"),("qc","inspect")]` untuk inspect/start & complete (pola keputusan owner 2026-10-21).
Pertahankan pagar gudang (`warehouse_scope_service.assert_usable`).

**Uji regresi**: Gudang scan TRM/SJ/TBA → 200; QC mulai & selesai → 200; Finance/Desainer → 403.

### F-12 · P1 · QC retur tanpa barang diterima — S
**Reproduksi** (SRET-00007, ulang SRET-00020): retur disetujui → tanpa scan apa pun →
`inspect/start` 200 → `inspect/complete` 200 (*inspected*).

**Akar masalah**: `backend/services/return_journey_service.py:122–126` `assert_ready_for_qc` keluar bila
`roll_locations` kosong; `return_service.start_inspection` (`:717`) tidak memeriksa penerimaan.

**Perbaikan**: wajibkan semua roll klaim berstage *received/arrived* sebelum start & complete; pengecualian
hanya jalur diskon foto/video KLR-06 (tanpa QC fisik). Pesan: *Scan terima barang retur dulu*.

**Uji regresi**: tanpa scan → 400; sebagian *in_transit* → 400; semua tiba → 200; jalur diskon foto tetap jalan.

### F-05 · P1 · Alokasi SO tidak mengikuti roll anak setelah potong — M
**Reproduksi** (SO-00038, ulang SO-00085): SO qty 150 yd → alokasi RL-36311 (utuh) + RL-36312 (reservasi
potong 28,41) → konfirmasi potong → lahir RL-36312-1 → `allocations[].rolls` tetap RL-36312 → pick RL-36312
ditolak *tidak ter-alokasi*; pick RL-36312-1 berhasil, tetapi daftar picking/Ganti Roll menampilkan induk.

**Akar masalah**: `backend/services/roll_service.py:603` `confirm_cut` membuat roll anak & memindah reservasi,
tidak memperbarui `sales_orders.allocations[].rolls` (entri dengan `reservation_id`).

**Perbaikan**: dalam operasi yang sama (atau langkah idempoten sesudahnya) ganti entri berdasarkan
`reservation_id` → `roll_id`/`roll_no` anak, `length` aktual, hapus `pending_cut`. Periksa dampak ke
`alloc_sig` harga khusus (perubahan karena potong **bukan** perubahan alokasi bisnis — signature harus stabil).

**Uji regresi**: potong → alokasi menampilkan anak; pick dari daftar → OK; satu dispatch qty penuh → satu SJ;
harga khusus yang diajukan sebelum potong tetap bisa diputus.

### F-03 · P1 · Grade & LOT bocor ke Sales lewat `variant_label` — S–M
**Reproduksi**: akun `sales@` `GET /api/products?q=DENIM TENCEL` → `variant_label` *Impor · 01 · A*,
*Impor · 1 · A · LOT A*; `GET /api/sales-orders/frequent-products` → *Lokal · TAUPE · A*.
`frontend/src/features/sales/mobile/MobileFieldViews.jsx:19` menampilkannya.

**Akar masalah**: `backend/services/field_visibility.py` (strip nama & SKU, `_strip_name` `:123`) tidak
menangani `variant_label`.

**Perbaikan**: saring segmen grade/LOT/asal pada `variant_label` (pemisah ` · `) memakai himpunan grade yang
sama dengan `_strip_name`; tambahkan `variant_label` ke uji sweep kebocoran izin (katalog, frequent-products,
export, detail roll).

**Uji regresi**: Sales → tidak ada grade/LOT; Admin/Admin Sales → tetap lengkap.

### F-01 · P1* · Login cepat per peran gagal — XS
**Reproduksi**: tombol *Manajer/Admin Sales/Finance/Sales/Gudang* → *Email atau password tidak sesuai*.

**Akar masalah**: `frontend/src/components/LoginScreen.jsx:10,34` mengirim `demo12345`;
`backend/scripts/demo_api.py:12` `DEMO_PASSWORD = "demo1234"` untuk akun peran (admin & wh.admin memakai demo12345).
`AGENTS.md`, `docs/LOCAL_DEV.md` menyebut demo12345.

**Perbaikan**: satu sandi demo untuk semua akun seed (pilih satu, perbarui seed + tombol + dokumen) — atau
sandi UAT dibagikan terpisah dan tombol demo disembunyikan di lingkungan UAT.

**Uji regresi**: semua tombol peran masuk setelah `dev_restore_demo.sh`.

### F-10 · P1 · Termin CBD/DP tidak menahan pengiriman — M (butuh keputusan Q-02)
**Reproduksi** (SO-00041 → SJ-00007; ulang SO-00084 → SJ-00012): termin *CBD — Bayar Sebelum Kirim*, bayar
*pending* → verifikasi → konfirmasi → pick → **dispatch 200**.

**Akar masalah**: `shipment_service.dispatch_task` (`:42`) & `loading_check_service.dispatch_guard` (`:238`)
tidak membaca termin; `dp_percent` termin (`config_service.py:155`) tidak dipakai saat kirim.

**Perbaikan** (setelah keputusan): gerbang di `dispatch_guard`: CBD → `paid_total ≥ grand_total`;
DP → `paid_total ≥ dp_percent × grand_total`; pengecualian izin baru (mis. `order.release_unpaid`) + alasan,
teraudit; tampilkan alasan di Barang Keluar & Meja Gudang; SO CBD tidak masuk daftar jatuh tempo NET.

**Uji regresi**: CBD belum bayar → 409; setelah kwitansi → 200; DP 49% → 409; 50% → 200; pengecualian berizin.

---

## Gelombang 2 (setelah keputusan owner)

| ID | Ringkas | Akar masalah | Usulan | Keputusan |
|---|---|---|---|---|
| F-06 | POD *Terkirim* tidak menutup SO (LG-00001/2; ulang SO-00084) | `logistics_service.transition('delivered')` hanya memanggil hook OD | Bila semua SJ SO ber-POD → `mark-delivered` otomatis (aktor = petugas POD), atau tugas *konfirmasi diterima* di Meja Admin Sales | Q-01 |
| F-14 | SPK kedatangan ditutup *terima*, roll tetap karantina sampai *qc-decision* kedua (INS-00019) | `inspection_service.finish` (`:943`) vs `inbound_receiving_extra.py:125` | Satukan: keputusan SPK melepas karantina via `process_qc_decision`, atau antrean karantina menampilkan SPK & cukup sekali | Q-03 |
| F-15 | Sample berbayar disetujui Rp83.250, setelah potong 3,1 yd jadi Rp86.025, status bayar tetap pending (SOS-00002) | `sample_orders.approve_payment` (`:175`) hanya flag | Toleransi selisih; di atas toleransi minta persetujuan ulang; tautkan ke kwitansi | Q-04 |
| F-16 | Jatuh tempo dihitung dari tanggal SO; SO backorder/menunggu ACC & SO CBD tampil *30 hari lagi* | `customer_service.py:182,415` `due = created + term_days` | Dasar = SJ pertama / faktur (sejalan GL-03); kecualikan SO belum dikirim; CBD/DP mengikuti termin | Q-05 |
| F-08 | Daftar invoice SO kosong setelah lunas; langkah *Ditagih* = Faktur Pajak | `invoices.py` hanya dari simulate-payment | Tetapkan Faktur Komersial (PDF) sebagai dokumen tagihan resmi, tampil di SO & Perjalanan | — |

## Gelombang 3

| ID | Ringkas | Akar masalah | Usulan |
|---|---|---|---|
| F-07 | Perjalanan SO selesai: *Disiapkan gudang 0/1*; Disetujui/Dikonfirmasi tanpa waktu & pelaku | `order_journey_service.py:173` tidak menghitung `dispatched`; transisi tanpa `approved_at/by`, `confirmed_at/by` | Tambah status; stempel di `_transition` |
| F-02 | *0 roll tersedia* dari strip *Sering dibeli* | `sales_orders_extra.py:297` `frequent_products` tanpa `roll_count`; `CheckoutItemCard.jsx:25` | Pakai helper ketersediaan katalog |
| F-04 | KPI POS *Jml Tersedia* menjumlah yard + kg | `frontend/src/App.js:502–503` | Per satuan atau jumlah roll |
| F-17 | Antrean *Retur menunggu proses dokumen* bernilai Rp0 | `work_desk_service` | Nilai = qty klaim × harga transaksi |
| F-13 | MD Quality bisa isi saat SPK *Draf* (QC ditolak) | `inspection_service.py:803` sengaja | Konfirmasi Q-06; bila tidak dimaksud, wajibkan ditugaskan |

## Keputusan owner yang dibutuhkan

| Kode | Pertanyaan | Temuan |
|---|---|---|
| Q-01 | POD pengiriman menutup SO otomatis atau tetap manual oleh Admin Sales/Gudang? | F-06 |
| Q-02 | CBD/DP: blok keras pengiriman atau peringatan? DP minimal sebelum kirim? Siapa boleh melepas? | F-10 |
| Q-03 | Barang datang: cukup satu keputusan (SPK) atau tetap dua (SPK + karantina)? | F-14 |
| Q-04 | Sample berbayar: toleransi selisih panjang aktual & siapa menyetujui ulang? | F-15 |
| Q-05 | Jatuh tempo dihitung dari SJ pertama atau tanggal faktur? | F-16 |
| Q-06 | MD Quality boleh mengisi sebelum SPK ditugaskan? | F-13 |

## Dokumen bukti di data acuan lokal

SO-00038 (O2C lengkap) · SO-00039 & SO-00083 (F-09) · SO-00040 (ganti roll) · KANDA/SO-00007 (kredit) ·
SO-00041 & SO-00084 (CBD) · SO-00042 (ambil sendiri) · SO-00043 (QC) · SO-00045 (stok kurang → IC-00009,
PR-00042, PO-00028, GRN-00001, INS-00019) · SO-00085 (F-05) · SOS-00002 (sample) · SJ-00005…00012 ·
LG-00001…00004 · AR-00003, AR-00005 · FKT-00001 · SRET-00006, SRET-00007, SRET-00020.
