Commit yang direview: 91a3ec0612952bfcc88335668ef2b3f601ba926a
Lingkungan: lapis B database tiruan (mongomock, aplikasi utuh) + lapis A MongoDB asli lokal (`test_database`) dengan backend hidup di 8001 dan data acuan `restore_local_demo.sh`. Docker tidak ada. Tanpa potret layar (pilihan pemilik sesi ini).

# Validasi PK-15 — alokasi titipan bank dan biaya/bunga bank (batch B1)

Uji bantahan reviewer: `docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK15.py` (6 uji, semuanya lulus = tidak ada bantahan yang berhasil).

## SL-03 — Alokasi dana titipan bank: jurnal kedua dilewati diam-diam

### Temuan asli
Dibaca di `cd6963a`: `backend/services/bank_recon_service.py:1225` — `source_id=f"{ln['id']}:{order_id}:{len(done)}"` dengan `done` mulai kosong tiap panggilan, sehingga alokasi kedua ke pesanan yang sama memakai `source_id` yang sama dan dianggap sudah diposting; sisa titipan baru ditulis sesudah semua alokasi (`:1238-1241`), gagal di tengah → `mark_failed` dan sisa belum berkurang.

### Perbaikan yang diperiksa
SHA unit `30e3f28b`. Berkas dibaca: `backend/services/bank_recon_service.py:1419-1500` (`allocate_holding`: sisa tersedia dikurangi butir `pending`, validasi semua sasaran lewat `ar_allocation_service.validate_targets`, `preflight_posting`, niat `pending` ber-id `bha_…` dengan syarat `holding_remaining` belum berubah, kunci DILEPAS saat galat), `backend/services/bank_recon_service.py:1508-1568` (`_alloc_steps`: pesanan dilunasi sekali per `alloc_id`, sisa berkurang per butir dengan pembaruan bersyarat, jurnal ber-`source_id` `<baris>:<id alokasi>`, gagal jurnal → `gl_status: failed`), `backend/services/ar_allocation_service.py:205-247` (alokasi ber-id tetap, syarat `Σ payments + amount ≤ grand_total`).

### Pintu lain
```
grep -rn "post_bank_holding_allocation\|apply_from_bank_holding" backend/services backend/routers --include=*.py | grep -v "def "
grep -n "holding_remaining" backend/services/bank_recon_service.py | grep -E "\\\$set|update"
```
Kesimpulan: `post_bank_holding_allocation` hanya dipanggil dari `bank_recon_service.py:1551`; `apply_from_bank_holding` tidak punya pemanggil lagi. Tidak ada jalur lain yang mengalokasikan titipan.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK15_titipan_biaya_bank.py -n 0 -q                               # pelaksana: 10 lulus
cd backend && REACT_APP_BACKEND_URL=http://localhost:8001 python -m pytest -n0 -q tests/test_bp_PK15_titipan_bersamaan_mongo.py   # lapis A: 1 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK15.py -n 0 -q -s -k SL03                                 # reviewer: 3 lulus
```
Hasil: 14 lulus, 0 gagal.

### Upaya membantah
- [bersamaan] Titipan 10 jt; dua permintaan alokasi serentak (6 jt ke X; 4 jt ke Y + 2 jt ke X = 12 jt). Hasil: 200 dan 400; sisa 4.000.000, 1 jurnal, Σ dibayar 6.000.000 = Δ akun 2-1950, semua butir `done`, tanpa `saga_lock` — tidak terbantah.
- [batas_nilai] Tiga alokasi berurutan 1 + 2 + 3 jt ke pesanan yang sama, lalu 4.000.001 (lebih 1 rupiah dari sisa) dan 2.000.001 (lebih dari sisa tagihan). Hasil: 3 jurnal ber-`source_id` berbeda; dua permintaan lebih ditolak; sisa tetap 4.000.000 — tidak terbantah.
- [koreksi] Batalkan titipan sesudah 3 jt dialokasikan. Hasil: 400 "Titipan sudah dialokasikan — koreksi harus lewat amandemen"; pesanan tetap terbayar 3 jt, jurnal tetap 1, Δ 2-1950 = 0 — tidak terbantah.

### Putusan
Putusan: verified
Alasan: `source_id` unik per butir dan sisa per butir terbukti di `backend/services/bank_recon_service.py:1508-1568`; `test_U01_alokasi_kedua_ke_pesanan_sama_berjurnal`, `test_U03_U04_gagal_di_tengah_lalu_dilanjutkan`, lapis A `test_U14_alokasi_bersamaan`, serta bantahan `test_SL03_bersamaan_dua_alokasi_melebihi_sisa` dan `test_SL03_batas_tiga_alokasi_berurutan_lalu_lebih_satu_rupiah` lulus; tidak ada pintu alokasi kedua.

## SL-04 — Biaya/bunga bank: kas tersisa bila jurnal gagal; ulang membuat kas kedua

### Temuan asli
Dibaca di `cd6963a`: `backend/services/bank_recon_service.py:972` — sesudah klaim, `cash_transactions.insert_one(cdoc)` lalu `gl.post_cash_transaction(cdoc)` tanpa cek periode; jurnal gagal (tanggal mutasi di periode tertutup) → `mark_failed`, kas tertinggal, dan mengulang sesudah kunci dilepas menyisipkan kas baru ber-id baru.

### Perbaikan yang diperiksa
SHA unit `30e3f28b`. Berkas dibaca: `backend/services/bank_recon_service.py:1152-1245` (`book_charge`: `periksa_periode_dokumen` + `gl.preflight_posting` pada tanggal mutasi SEBELUM klaim; kas lama untuk rujukan + kategori yang sama dipakai ulang lewat `txn_id`; `CashPostingError` → 409 dengan kas bertanda gagal; kunci dilepas), `backend/services/bank_recon_service.py:1246-1262` (`_reverse_charge`: void kas + pembalik lewat `post_durable`), `backend/services/ap_payment_service.py:475-494` (pola pembuat kas satu pintu yang sama, pembanding).

### Pintu lain
```
grep -n "cash_transactions.insert_one\|create_cash(" backend/services/bank_recon_service.py
```
Kesimpulan: tidak ada lagi `cash_transactions.insert_one` di `bank_recon_service.py`; dua pembuat kas (`:1212` biaya/bunga, `:1390` titipan) lewat `cash_ledger.create_cash` ber-id tetap dari rujukan.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK15_titipan_biaya_bank.py -n 0 -q -k "U09 or U10 or U11"       # 3 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK15.py -n 0 -q -s -k SL04                                # reviewer: 3 lulus
```
Hasil: 6 lulus, 0 gagal.

### Upaya membantah
- [bersamaan] Dua `book-charge` serentak pada baris yang sama. Hasil: 200 dan 400; 1 kas hidup, 1 jurnal, tanpa `saga_lock` — tidak terbantah.
- [koreksi] Tiga putaran catat → lepas (unmatch) → catat pada baris 40.000. Hasil: beban kembali 0 sesudah tiap lepas; akhir 1 kas hidup (3 kas total, 2 void), Δ beban tepat 40.000 — tidak terbantah.
- [ulang] Catat bunga pada baris yang sudah tertaut, lalu coba catat sebagai biaya. Hasil: keduanya ditolak 4xx, tetap 1 kas — tidak terbantah.

### Putusan
Putusan: verified
Alasan: cek periode sebelum kas dan pakai-ulang kas per rujukan terbukti di `backend/services/bank_recon_service.py:1194-1218`; `test_U09_biaya_bank_periode_tertutup`, `test_U10_U12_biaya_bank_jurnal_gagal_lalu_ulang`, `test_SL04_bersamaan_dua_catat_biaya`, `test_SL04_koreksi_dua_putaran_lepas_catat` lulus; tidak ada sisip kas langsung tersisa di layanan rekonsiliasi.
