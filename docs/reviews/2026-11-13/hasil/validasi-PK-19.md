Commit yang direview: 91a3ec0612952bfcc88335668ef2b3f601ba926a
Lingkungan: lapis B database tiruan (mongomock, aplikasi utuh) + lapis A MongoDB asli lokal (`test_database`) dengan backend hidup di 8001 dan data acuan `restore_local_demo.sh`. Docker tidak ada. Tanpa potret layar (pilihan pemilik sesi ini).

# Validasi PK-19 — satu fungsi alokasi pembayaran piutang (batch B1)

Uji bantahan reviewer: `docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK19.py` (9 uji, semuanya lulus = tidak ada bantahan yang membatalkan perbaikan; satu celah baru dicatat sebagai temuan RV-01 di paket `docs/reviews/2026-11-16/`).

## SL-05 — Jalur lama "simulasi bayar" masih dipakai layar

### Temuan asli
Dibaca di `cd6963a`: `backend/routers/invoices.py:37` (`POST /sales-orders/{id}/simulate-payment`, izin `order.update`, membuat faktur + pembayaran tanpa kwitansi) dan pemanggilnya di layar `frontend/src/hooks/useAppActions.js:485` (`axios.post(… /simulate-payment`).

### Perbaikan yang diperiksa
SHA unit `1204bac6` (serah-terima b; fungsi inti `2a9f5dc2`). Berkas dibaca: `backend/routers/invoices.py:1-45` (endpoint tinggal menjawab 410 sesudah cek `order.view`; tidak menulis apa pun), `backend/services/ar_allocation_service.py:126-247` (`validate_targets` + `allocate`: satu-satunya penulis baris `payments` pesanan), `backend/services/ar_allocation_service.py:320-384` (`reverse`: pembalik ber-id tetap, bukan hapus baris).

### Pintu lain
```
grep -rnE '"payments"' backend/services backend/routers --include=*.py | grep -E '\$push|\$pull' | grep -v "vendor_bills\|landed_cost\|contra_bon\|ap_payment"
grep -rn "simulate-payment\|payInvoice" frontend/src --include=*.jsx --include=*.js | grep -v test
```
Kesimpulan: baris `payments` pesanan hanya ditulis `ar_allocation_service.py:236`, `:286`, `:361` (baris `penalty_service.py:686` menulis `payments` dokumen denda, bukan pesanan). Tidak ada lagi rujukan `simulate-payment` di `frontend/src`.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK19_alur.py -n 0 -q -k U17              # pelaksana: 1 lulus
cd backend && python -m pytest tests_mem/test_PK19_alokasi.py -n 0 -q                  # pelaksana (fungsi inti): 10 lulus
cp docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK19.py backend/tests_mem/ && cd backend && python -m pytest tests_mem/test_bantah_PK19.py -n 0 -q -s -k SL05   # reviewer: 2 lulus
```
Hasil: 13 lulus, 0 gagal.

### Upaya membantah
- [jalur_lain] `simulate-payment` dipanggil Admin dan Sales; lalu `PATCH`/`PUT /api/sales-orders/{id}` dengan `payments`, `paid_total`, `payment_status` dari klien. Hasil: 410/403; PATCH 422, PUT 405; pesanan tetap `payments: []`, `unpaid`, 0 faktur — tidak terbantah.
- [tanpa_izin] Sales membuat kwitansi resmi `POST /api/ar-receipts`. Hasil: 200 karena bawaan Sales memang memegang `ar_receipt.create`; pembayarannya lahir sebagai kwitansi `posted` (bukan jalur lama) — tidak terbantah (catatan: wewenang Sales membuat kwitansi adalah bawaan izin, bukan cacat unit ini).

### Putusan
Putusan: verified
Alasan: jalur lama mati (`backend/routers/invoices.py:33` menjawab 410; `test_PK19_U17_simulasi_bayar_dimatikan` dan `test_SL05_jalur_lain_simulasi_dan_ubah_pesanan_langsung` lulus) dan pencarian `$push payments` menunjukkan hanya `backend/services/ar_allocation_service.py:236` yang menambah pembayaran pesanan.

## SL-06 — Void kwitansi menggeser deposit sebelum status berubah

### Temuan asli
Dibaca lewat daftar audit dan `git show cd6963a:backend/services/ar_receipt_service.py` di sekitar `backend/services/ar_receipt_service.py:675` (deposit digeser lebih dulu), `:746` dan `:767` (galat jurnal pembalik hanya di-log): gagal di tengah meninggalkan kunci dan void ulang menggeser deposit lagi.

### Perbaikan yang diperiksa
SHA unit `1204bac6`. Berkas dibaca: `backend/services/ar_receipt_service.py:675-790` (`void_receipt`: PERIKSA status/periode/`reverse_check` → klaim + `void_intent` → lima langkah efek bertanda `void_intent.steps.*` → jurnal pembalik `durable_receipt_void` ber-`void_gl_status` → selesai; kunci dilepas di `finally`), `backend/services/ar_allocation_service.py:320-384` (pembalik idempoten per baris).

### Pintu lain
```
grep -rn "adjust_deposit(\|deposit_balance\"" backend/services backend/routers --include=*.py | grep -E "adjust_deposit\(|\\\$inc|\\\$set"
grep -n "void_intent" backend/services/ar_receipt_service.py
```
Kesimpulan: saldo deposit hanya berubah lewat `_adjust_deposit` (`ar_receipt_service.py:320-338`, CAS); pemanggil di luar kwitansi (`finance_case_actions.py:732`, `:753`, `payment_variance_service.py:565-632`, `:1118-1129`) semuanya berpenanda langkah. Tidak ada pintu void kwitansi kedua.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK19_alur.py -n 0 -q -k "U6 or U7 or U10"                       # pelaksana: 4 lulus
cd backend && REACT_APP_BACKEND_URL=http://localhost:8001 python -m pytest -n0 -q tests/test_bp_PK19_bersamaan_mongo.py -k U15   # lapis A: 1 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK19.py -n 0 -q -s -k SL06                                # reviewer: 1 lulus
```
Hasil: 6 lulus, 0 gagal.

### Upaya membantah
- [bersamaan] Kwitansi 600.000 kas + 400.000 deposit; dua void serentak. Hasil: 200 dan 409; deposit kembali 400.000 tepat sekali, status `void`, Σ pembayaran pesanan 0, `void_gl_status: posted`, tanpa `saga_lock` — tidak terbantah.
- [ulang] Void ketiga sesudah selesai. Hasil: 409 "sudah di-void", deposit tetap 400.000; Δ piutang bersih jurnal ber-sumber kwitansi = 0 — tidak terbantah.
- [periode_tertutup] Void saat periode hari ini tertutup (uji pelaksana U10 dijalankan ulang). Hasil: ditolak sebelum efek apa pun — tidak terbantah.

### Putusan
Putusan: verified
Alasan: langkah bertanda dan klaim terbukti di `backend/services/ar_receipt_service.py:717-790`; `test_PK19_U6_batal_kwitansi_gagal_di_tengah_lalu_diulang`, lapis A `test_PK19_U15_dua_batal_bersamaan`, dan `test_SL06_ulang_dan_bersamaan_void_kwitansi_berdeposit` lulus dengan deposit kembali tepat sekali.

## FX-05 — Alokasi dari deposit tidak memeriksa pemilik pesanan; deposit dikurangi setelah semua alokasi

### Temuan asli
Dibaca lewat daftar audit dan kode `cd6963a`: `backend/services/ar_receipt_service.py:178` (pembungkus alokasi deposit tanpa pelanggan/entitas sehingga cek pemilik dilewati) dan `backend/services/payment_variance_service.py:549` (deposit baru dikurangi sesudah semua alokasi).

### Perbaikan yang diperiksa
SHA unit `2a9f5dc2` + `1204bac6`. Berkas dibaca: `backend/services/ar_allocation_service.py:126-172` (`validate_targets`: pelanggan lain 400, PT lain 403, status mati 409, melebihi sisa 400 — semua sasaran diperiksa sebelum tulis), `backend/services/ar_allocation_service.py:205-247` (`allocate` selalu memanggil `validate_targets`), `backend/services/bank_recon_service.py:1446-1462` (titipan bank memakai pemeriksa yang sama), `backend/services/payment_variance_service.py:1072-1125` (deposit dikembalikan per baris `deposit_taken`).

### Pintu lain
```
grep -rn "validate_targets\|aas.allocate\|_aas.allocate" backend/services backend/routers --include=*.py | grep -v "def "
grep -rnE '"payments"' backend/services backend/routers --include=*.py | grep -E '\$push' | grep -v "vendor_bills\|landed_cost\|contra_bon\|ap_payment"
```
Kesimpulan: semua sumber dana (kwitansi, deposit, titipan bank, kasus, saldo kredit, retur) menulis lewat `ar_allocation_service.allocate`, yang tidak bisa dilewati tanpa `validate_targets`.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK19_alur.py -n 0 -q -k "U1_ or U2 or U3 or U4 or U12 or U13"    # pelaksana: 6 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK19.py -n 0 -q -s -k FX05                                 # reviewer: 2 lulus
```
Hasil: 8 lulus, 0 gagal.

### Upaya membantah
- [jalur_lain] Bukan lewat keputusan selisih, melainkan kwitansi `POST /api/ar-receipts` ber-`use_deposit_amount` 500.000: satu alokasi sah (pesanan A) + satu ke pesanan pelanggan B, lalu + satu ke pesanan A di PT lain. Hasil: 400 dan 403; deposit tetap 500.000, kedua pesanan tanpa pembayaran, tidak ada kwitansi baru — tidak terbantah.
- [batas_nilai] Deposit 400.000 tetapi diminta pakai 600.000 untuk dua pesanan @300.000. Hasil: 400 "Deposit tidak cukup", tidak ada yang tertulis — tidak terbantah.
- [pt_lain] Titipan bank ke pesanan pelanggan lain (uji pelaksana U12 dijalankan ulang). Hasil: ditolak — tidak terbantah.

### Putusan
Putusan: verified
Alasan: satu pemeriksa sasaran terbukti di `backend/services/ar_allocation_service.py:126-172` dan dipanggil dari `:219`; `test_PK19_U1_alih_deposit_ke_pelanggan_lain_ditolak`, `test_PK19_U2_alih_deposit_ke_pt_lain_ditolak`, `test_FX05_jalur_lain_kwitansi_deposit_ke_pelanggan_dan_pt_lain`, `test_FX05_batas_deposit_kurang_dari_alokasi` lulus; tidak ada penulis `payments` pesanan di luar fungsi itu.

## FX-06 — Hapus sisa pembayaran tanpa klaim; keputusan disimpan paling akhir

### Temuan asli
Dibaca lewat daftar audit dan kode `cd6963a`: `backend/services/payment_variance_service.py:691` (hapus sisa dijalankan tanpa klaim kwitansi) dan `:811` (dokumen keputusan disimpan paling akhir): dua klik → dua hapus-buku; jurnal gagal → pesanan lunas tanpa jejak.

### Perbaikan yang diperiksa
SHA unit `1204bac6` + `39725cc8`. Berkas dibaca: `backend/services/payment_variance_service.py:773-830` (`decide_receipt`: PERIKSA → NIAT `variance.decision_id` ditulis dengan syarat masih kosong → keputusan `pending` → efek → jurnal tahan-gagal), `backend/services/payment_variance_service.py:1072-1174` (`reverse_decision` berklaim, penanda `reversal_steps`), `backend/services/ar_allocation_service.py:205-247` (baris hapus sisa ber-id tetap).

### Pintu lain
```
grep -n "_saga.claim\|claim(" backend/services/payment_variance_service.py
grep -rn '"writeoff"\|method="writeoff"' backend/services --include=*.py | grep -v "payment_variance_service\|ar_reduction_guard"
```
Kesimpulan: hapus sisa hanya lahir dari `decide_receipt`/`auto_resolve_receipt`; jurnalnya dari `posting_registry.py:297-317` (satu `source_id` = id keputusan). Tidak ada pintu hapus sisa kedua.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK19_alur.py -n 0 -q -k "U8 or U9"                               # pelaksana: 2 lulus
cd backend && REACT_APP_BACKEND_URL=http://localhost:8001 python -m pytest -n0 -q tests/test_bp_PK19_bersamaan_mongo.py -k U16   # lapis A: 1 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK19.py -n 0 -q -s -k FX06                                 # reviewer: 2 lulus
```
Hasil: 5 lulus, 0 gagal.

### Upaya membantah
- [bersamaan] Dua keputusan hapus sisa 10.000 serentak atas kwitansi yang sama. Hasil: 200 dan 409; 1 baris `hapus_sisa`, 1 keputusan, 1 jurnal — tidak terbantah.
- [koreksi] Hapus sisa → batal keputusan → batal lagi → putus lagi. Hasil: batal kedua dijawab 200 tanpa efek (tetap 1 jurnal pembalik, Δ 6-9100 = 0, Σ bayar 990.000); keputusan baru sesudah batal diterima dan Σ bayar 1.000.000 — tidak terbantah.

### Putusan
Putusan: verified
Alasan: niat-sebelum-efek terbukti di `backend/services/payment_variance_service.py:773-830`; `test_PK19_U8_hapus_sisa_dua_kali_berurutan`, `test_PK19_U9_hapus_sisa_jurnal_gagal_lalu_diulang_dari_panel`, lapis A `test_PK19_U16_dua_hapus_sisa_bersamaan`, `test_FX06_bersamaan_dua_hapus_sisa`, `test_FX06_koreksi_batal_hapus_sisa_lalu_putus_lagi` lulus.

## FX-07 — Membatalkan keputusan selisih hutang tidak membalik jurnalnya

### Temuan asli
Dibaca lewat daftar audit dan kode `cd6963a`: `backend/services/payment_variance_service.py:944` (cabang batal untuk sisi hutang jatuh ke "tidak memindahkan uang") padahal jurnal Dr 2-1100 / Cr 4-9000 terbit di `:1043`; `backend/services/vendor_bill_service.py:200` menghidupkan lagi hutang di faktur.

### Perbaikan yang diperiksa
SHA unit `1204bac6`. Berkas dibaca: `backend/services/payment_variance_service.py:1072-1174` (cabang `AP_WRITEOFF_KINDS` di `:1131-1142`: faktur dibuka lagi dengan syarat `ap_variance_decision_id` cocok; jurnal pembalik lewat `durable_variance_reversal`, hasil di `reversal_gl_status`), `backend/services/payment_variance_service.py:100-131` (`_periksa_periode` — dipakai jalur PUTUS, tidak dipakai jalur BATAL), `backend/routers/vendor_bills.py:668-712` (pembanding: void pembayaran memeriksa periode lebih dulu).

### Pintu lain
```
grep -rn "ap_variance_closed" backend/services backend/routers --include=*.py | grep -E '\$set|update'
grep -n "payment_variance_reversal" backend/services/posting_registry.py
```
Kesimpulan: `ap_variance_closed` hanya dibuka kembali di `payment_variance_service.py:1140`; jurnal pembalik satu pintu (`posting_registry.py:359`, `source_id` `<id keputusan>:rev`).

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK19_alur.py -n 0 -q -k U11                                      # pelaksana: 1 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK19.py -n 0 -q -s -k FX07                                 # reviewer: 2 lulus
```
Hasil: 3 lulus, 0 gagal.

### Upaya membantah
- [bersamaan] Tiga pembatalan (dua serentak + satu susulan) atas keputusan tutup sisa hutang 10.000. Hasil: 200/200/200 (keputusan `reversed` dikembalikan apa adanya) tetapi tepat 1 jurnal pembalik Dr 4-9000 10.000 / Cr 2-1100 10.000; faktur tidak lagi `paid` — tidak terbantah.
- [periode_tertutup] Batal keputusan saat periode hari ini tertutup. Hasil: 200; keputusan `reversed`, faktur terbuka lagi (sisa 10.000), jurnal pembalik 0 dengan `reversal_gl_status: failed` (terlihat, bisa diulang dari panel Posting Gagal sesudah periode dibuka). Tidak membantah temuan asal (ada cabang pembalik + penanda), tetapi jalur batal TIDAK punya langkah PERIKSA periode seperti jalur putus (`_periksa_periode`) dan void kwitansi — dicatat sebagai temuan baru RV-01.

### Putusan
Putusan: verified
Alasan: cabang pembalik sisi hutang ada di `backend/services/payment_variance_service.py:1131-1142` dan `test_PK19_U11_batal_tutup_sisa_hutang` + `test_FX07_ulang_dan_bersamaan_batal_tutup_sisa_hutang` membuktikan satu jurnal kebalikan persis dan saldo 2-1100 = sisa faktur. Keadaan "hutang hidup tanpa jurnal" hanya muncul bila periode hari ini tertutup dan saat itu bertanda `failed` (`test_FX07_periode_tertutup_batal_tutup_sisa_hutang`) — celah PERIKSA itu didaftarkan terpisah (RV-01, Sedang), bukan kegagalan perbaikan FX-07.
