Commit yang direview: 91a3ec0612952bfcc88335668ef2b3f601ba926a
Lingkungan: lapis B database tiruan (mongomock, aplikasi utuh) + backend hidup di 8001 dengan MongoDB asli lokal (`test_database`). Docker tidak ada. Tanpa potret layar (pilihan pemilik sesi ini). Unit ini tidak punya uji lapis A.

# Validasi PK-38 — satu batas pengurang piutang tanpa kas (batch B1)

Uji bantahan reviewer: `docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK38.py` (4 uji: 3 lulus, 1 gagal — yang gagal adalah bantahan yang berhasil dan menjadi pertanyaan untuk pemilik).

## FX-10 — Batas wewenang kasus lebih longgar dari hapus sisa; penyelesai = penyetuju

### Temuan asli
Dibaca di `cd6963a`: `backend/services/finance_case_service.py:405` — batas kasus memakai ambang sendiri (`approval_above`, `refund_max`) dan nama peran (`role_in(role, (need, "admin"))`), terpisah dari batas hapus sisa Rp 1.000.000; aksi "bebankan biaya bank" dan "akui dipegang karyawan" lolos pada nominal berapa pun bagi peran penyetuju, dan pembuat kasus boleh menyelesaikannya sendiri (`:494`).

### Perbaikan yang diperiksa
SHA unit `eef7bb9d`. Berkas dibaca: `backend/services/ar_reduction_guard.py:1-105` (satu pintu `periksa`: `TANPA_KAS` = hapus sisa + tiga aksi kasus; `batas(PT)` dari `kontrol.pengurang_piutang.batas_nominal` dengan kunci lama sebagai cadangan; di atas batas atau `min_orang = 2` → `dual_control.tolak_bila_pelaku_sama`; jejak audit `ar_reduction_checked`), `backend/services/payment_variance_service.py:791-830` (hapus sisa memanggil `_arg.periksa` SEBELUM efek, per keputusan, `nominal=amount`), `backend/services/finance_case_service.py:532-545` (biaya bank otomatis dibatasi `min(auto, batas)`), `backend/services/dual_control.py:56-75` (`butuh_orang_kedua`: perbandingan nominal SATU keputusan dengan batas).

### Pintu lain
```
grep -rn "ar_reduction_guard\|_arg.periksa" --include=*.py backend/services backend/routers | grep -v "^backend/services/ar_reduction_guard.py"
grep -rn '"writeoff"\|method="writeoff"' backend/services --include=*.py | grep -v "payment_variance_service\|ar_reduction_guard"
grep -n '_A("' backend/services/finance_case_playbooks.py
```
Kesimpulan: empat pengurang piutang tanpa kas yang disebut temuan (hapus sisa, biaya bank, dipegang karyawan, salah PT) lewat `ar_reduction_guard.periksa` (`payment_variance_service.py:819`, `finance_case_service.py:537`, `routers/finance_cases.py:64`). Nota kredit tidak termasuk `TANPA_KAS` (jalur amandemen ber-persetujuan sendiri — keputusan desain unit). Batas dihitung PER KEPUTUSAN, tidak kumulatif per pesanan/pelanggan.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK38_wewenang.py -n 0 -q                                         # pelaksana: 27 lulus
cp docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK38.py backend/tests_mem/ && cd backend && python -m pytest tests_mem/test_bantah_PK38.py -n 0 -q -s   # reviewer: 3 lulus, 1 gagal
```
Hasil: 30 lulus, 1 gagal. Yang gagal: `test_FX10_batas_nilai_pecah_nominal_satu_pesanan`.

### Upaya membantah
- [batas_nilai] Kasus biaya bank tepat di batas (1.000.000) dan batas + 1 rupiah oleh pembuatnya sendiri. Hasil: 200 dan 403 berpesan dua orang — tidak terbantah.
- [tanpa_izin] Hapus sisa 300.000 oleh Admin Sales dan Gudang. Hasil: 403 dan 403 — tidak terbantah. (Catatan: Admin sebagai pembuat sekaligus pemutus 1,5 jt = 200 karena bawaan `kontrol.admin_boleh_sendiri` = ya; itu pengaturan KF-T6, bukan celah unit ini.)
- [jalur_lain] Pembuat kasus biaya bank 1,5 jt mencoba aksi lain yang juga mengkredit piutang (`settlement_antar_entitas`, `akui_dipegang_karyawan`) pada kasusnya sendiri. Hasil: 400 "bukan bagian playbook", pesanan tetap 0 terbayar — tidak terbantah.
- [batas_nilai] PECAH NOMINAL: satu Manajer (pembuat kedua kwitansi) menghapus sisa pesanan yang SAMA dua kali @600.000. Hasil: 200 dan 200 — total 1.200.000 piutang satu pesanan hilang tanpa orang kedua, padahal batas 1.000.000. TERBANTAH bila batas dimaksudkan per pesanan/pelanggan.

### Putusan
Putusan: perlu_keputusan_pemilik
Alasan: satu pintu dan satu batas terbukti (`backend/services/ar_reduction_guard.py:79-105`; `test_PK38_U2_hapus_sisa_di_atas_batas_orang_kedua`, `test_PK38_U3_biaya_bank_di_atas_batas_orang_kedua`, `test_PK38_U5_uang_dipegang_karyawan_di_atas_batas` lulus), tetapi `test_FX10_batas_nilai_pecah_nominal_satu_pesanan` menunjukkan batas berlaku per keputusan sehingga bisa dilewati dengan memecah nominal. Pertanyaan untuk pemilik: apakah batas pengurang piutang tanpa kas harus KUMULATIF (per pesanan? per pelanggan? per orang per hari/bulan?) — bila ya, `ar_reduction_guard.periksa` perlu menjumlah pengurang sebelumnya; bila per keputusan sudah cukup, butir ini bisa ditetapkan `verified`.
