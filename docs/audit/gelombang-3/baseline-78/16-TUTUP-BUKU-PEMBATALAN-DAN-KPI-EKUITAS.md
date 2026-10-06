# Pengujian lanjutan: tutup buku, pembatalan jurnal dan sumber KPI ekuitas

Pada source `a904d989b622f7da14c4892d03cf6ef0c43f3084`, tambahan pengujian menghasilkan **enam temuan** dari 35 observasi: 16 perbedaan dan 19 kontrol lulus. Seluruh pengujian memakai API dan layanan asli, database sintetis lokal terpisah, serta indeks startup asli. Kesimpulan berikut dibatasi oleh fixture dan lifecycle yang dijelaskan; angka uang merupakan satuan sintetis yang konsisten.

## Hasil per flow

| ID | Kasus | Hasil semestinya | Hasil sekarang |
|---|---|---|---|
| CLOSE-01, P2 | Pendapatan 100 → penutupan bulan 100 → tahun residual 0 → reopen bulan | Penutupan tahun diberi tanda perlu diperbarui, atau reopen diblokir sebelum efek sesuai urutan kebijakan | Tahun tetap closed/staleFalse, padahal residual baru 100; tombol Tutup Ulang tidak tersedia menurut kondisi UI |
| CLOSE-02, P1 | Tutup ulang 120 → koreksi 10 → jurnal baru 130 tersimpan → acknowledgment gagal | Catatan dapat dipulihkan untuk menunjuk tepat satu jurnal 130 dan angka 130 | Catatan menunjuk jurnal 120 void, angka 120; setelah fitur pelepasan admin berhasil, retry 500 dan catatan belum pulih |
| GL-01, P1 | Beban 100 → pembalik → net 0 → anulir jurnal asal | Aksi pembatalan kedua ditolak tanpa efek, atau memakai proses koreksi pasangan yang eksplisit | Anulir diterima 200; pembalik tetap aktif dan P&L berubah menjadi laba 100 |
| GL-02, P1 | Beban sah 50 → request angka NaN/Infinity | Input tidak sah ditolak 4xx sebelum insert; laporan tetap memuat 50 | Request 200, native non-finite double tersimpan; response angka menjadi null; KPI GL dan beban P&L menjadi 0 |
| EQ-01, P1 | Laba operasional 100 → tutup buku → Perubahan Ekuitas | KPI laba periode tetap 100; perpindahan ke laba ditahan tidak mengubah laba operasi | net_income KPI berubah 100→0, sedangkan operating P&L100 dan pergerakan ekuitas 100 tetap benar |
| COA-01, P1 | Akun income khususA → jurnal 77 → pilih Semua Entitas | Laba 77 ikut agregat lintas entitas dan neraca tetap seimbang | LaporanA laba 77/balancedTrue, mode all laba 0/balancedFalse; dimensi tidak mencakup akun khusus entitas |

## Reopen bulan dan ketergantungan penutupan tahun

```text
Pendapatan Januari100
  → jurnal penutup Januari100: laba dipindahkan ke laba ditahan
  → penutupan tahunan: residual0 karena Januari sudah ditutup
  → admin Reopen Januari: jurnal bulan menjadi void
  → residual tahun sekarang100
  → record tahun tetap closed, staleFalse
  → UI hanya menawarkan Tutup Ulang jika staleTrue
```

Pemeriksaan tidak menyatakan persamaan neraca rusak: neraca tetap seimbang dan laporan laba rugi operasional tetap 100. Masalah berada pada informasi bahwa tahun telah selesai ditutup dan tindakan lanjutan yang tersedia. Penutupan tahun bergantung pada penutupan bulan; pembatalan bulan harus menginvalidasi hasil tahun. Source sudah mempunyai propagasi stale untuk reclose, tetapi belum menerapkannya pada reopen.

Direct API reclose tahun terbukti berhasil 200 sebagai alternatif pemulihan pada fixture ini. Karena tombolnya bergantung pada stale, keberadaan endpoint tidak membuktikan alur operator sudah mengakomodasi pemulihan. Kebijakan alternatif yang sah adalah mewajibkan pembukaan parent dahulu dan menolak child reopen sebelum efek; kebijakan itu harus dipilih secara eksplisit.

## Tutup ulang dan pemulihan setelah efek tersimpan

Flow normal terlebih dahulu dibuktikan: jurnal pendapatan 100 → close bulan → request unlock → approver berbeda menyetujui → koreksi 20 bertanda backdated_in_unlock → reclose menjadi 120. Semua langkah tersebut memakai original public producer, tanpa memasang state closed/unlock secara manual.

```text
Koreksi berikutnya10, total operasional130
  → klaim saga reclose
  → jurnal lama120 dianulir
  → original insert menyimpan jurnal baru130
  → fault terkontrol: acknowledgment tidak sampai ke caller
  → parent masih menyimpan net120 dan link jurnal120void
  → retry langsung409 karena lock, sesuai guard
  → lock dibuat berumur2jam sebagai fixture waktu
  → admin memeriksa/mengakui efek dan melepas lewat API asli:200
  → retry original mencoba insert source closing yang sama
  → unique active source index menolak; HTTP500
```

Fault wrapper hanya melempar setelah original insert berhasil; perhitungan dan penulisan jurnal tidak diganti. Aging lock hanya mengubah waktu klaim agar menguji jalur admin setelah batas tunggu tanpa menunggu secara nyata. Kunci dan unique index adalah kontrol yang bekerja: tidak ada jurnal kedua yang berhasil dibuat. Kecacatan terletak pada ketiadaan checkpoint/adopsi jurnal yang telah tersimpan, sehingga pelepasan yang sah tetap tidak memulihkan hubungan parent, snapshot dan jurnal.

Prompt perbaikan menuntut identitas operation/version, frozen totals dan checkpoint old/new JE. Recovery harus menyelesaikan parent menggunakan jurnal yang sesuai, atau melakukan compensation yang auditable. Menghapus unique index, mengabaikan exception, atau hanya melepaskan lock bukan penyelesaian.

## Pembalikan dan anulir tidak boleh membatalkan asal dua kali

Kontrol normal menunjukkan manual expense 100→void menghasilkan laba 0; manual expense 100→reverse juga menghasilkan laba 0. Namun reverse→void asal masih diterima. Jurnal pembalik bukan void, sedangkan asal yang sebelumnya mengimbanginya menjadi void; laporan yang benar-benar menghitung semua non-void journal kemudian melaporkan laba 100.

Ini terjadi dengan request biasa, tanpa fault injection. Source UI menyediakan Anulir Jurnal ketika source manual/status non-void, tanpa mempertimbangkan reversed_by_entry_id. Perbaikan harus berada pada gate backend dan CAS bersama; menyembunyikan tombol saja tidak menjaga request bersamaan atau pending reversal. Jika perusahaan membutuhkan koreksi atas pasangan jurnal, sediakan aksi tersendiri dengan aturan tanggal/link/jejak audit yang jelas.

## Input angka tidak sah dapat menyembunyikan transaksi sah

Pengujian menggunakan request oleh admin berizin dengan JSON valid: field float diberi string NaN atau Infinity. Schema melakukan coercion ke float. Create jurnal manual memasukkan langsung ke database dan tidak melewati validator pusat math.isfinite yang sudah dipakai jalur autopost. Perbandingan balance terhadap nilai non-finite tidak menghasilkan penolakan.

API sebenarnya memberi 200 dan angka yang disanitasi menjadi null; **hipotesis serialization 500 tidak dipakai**. Database masih menyimpan non-finite double, sehingga agregat akun tercemar. Setelah transaksi sah 50 pada akun yang sama, GL summary memberi total 0 dan balancedTrue, dan P&L menampilkan beban 0. Jadi keberhasilan response dan indikator balanced tidak mendeteksi hilangnya transaksi sah dari laporan.

Fixture ini menguji ketahanan input API; tidak diklaim bahwa input NaN dapat dilakukan dari formulir browser biasa. Perbaikan harus menolak nilai sebelum penulisan, memakai validator yang sama pada manual/import/autopost, dan mendeteksi data lama yang rusak. Mengubahnya diam-diam menjadi 0 akan mempertahankan kehilangan informasi. Evidence JSON menandai nilai native non-finite dengan objek non_finite agar file bukti tetap JSON yang valid.

## Sumber KPI laba pada perubahan ekuitas

```text
Laba operasi100
  → sebelum close: current_earnings100, equity API net_income100
  → closing: pindah100 ke retained earnings
  → sesudah close: current_earnings0, equity API net_income0
  → EquityChangesTab tetap berlabel Laba Periode Berjalan
  → operating P&L periode sama tetap100
```

Saldo awal, akhir dan total pergerakan ekuitas tetap dapat direkonsiliasi; ketiganya menjadi kontrol dan tidak dicatat sebagai salah. Kesalahan ada pada definisi net_income yang memakai perubahan laba belum ditutup, lalu ditampilkan sebagai laba periode. Perbaikan harus memisahkan laba operasional dalam rentang/scope yang sama dari pergerakan komponen current earnings. Jangan menambahkan laba kembali ke total ekuitas karena perpindahan closing sudah tercakup di komponennya.

## Mode Semua Entitas dan akun khusus entitas

Producer publik mendukung pembuatan akun khusus PT yang belum ada pada template global. Pengujian membuat akun income 4-7777 hanya untukA, kemudian jurnal sah debit kas 77/kredit akun tersebut 77. Laporan satu entitas memakai effective COA A dan menunjukkan laba 77 dengan benar.

```text
Akun khusus entitasA: income4-7777
  → original public manual journal77 tervalidasi dan seimbang
  → P&L entitasA: net77
  → mode Semua Entitas, scope A+B
  → scope_entity(scope multi) mengembalikan None
  → account dimension hanya mengambil template global
  → akun income4-7777 tidak diklasifikasi
  → P&L all net0; BS all assets307/equity230, balancedFalse
```

B tidak mempunyai jurnal Juli pada saat skenario ini berjalan. Kas 307 berasal dari producer sah 100+130+77 yang telah dijelaskan. Tidak ada konflik tipe override pada kode global, input non-finite, atau fault yang menyebabkan selisih 77. LaporanA tetap seimbang sebagai kontrol. Pengujian berikutnya terhadap invalid values berada pada entitasB dan bulanSeptember, sehingga bukan sumber counterexample ini.

Kecacatan spesifik ada pada endpoint Laporan Keuangan dengan entity_id=all. Fitur Konsolidasi Grup mempunyai helper lain; tidak dinyatakan gagal tanpa kontrol tersendiri. Perbaikan harus menyelesaikan dimensi pada grain legal entity+account, kemudian memetakan ke klasifikasi akun grup yang eksplisit. Jangan mengambil override PT pertama secara acak, menghilangkan akun yang belum dipetakan, atau menyamakan kode yang memiliki makna berbeda tanpa kebijakan. Laporan gabungan dan export harus merekonsiliasi partisi per entitas.

## Lokasi kode, bukti dan urutan perbaikan

- [D4-CLOSE-01 — backend/services/closing_service.py:346](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L346); terkait: [backend/services/closing_service.py:398](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L398), [frontend/src/features/finance/ClosingView.jsx:307](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/ClosingView.jsx#L307)
- [D4-CLOSE-02 — backend/services/closing_service.py:371](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L371); terkait: [backend/services/closing_service.py:404](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L404), [backend/routers/saga_locks.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L90), [backend/indexes.py:444](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/indexes.py#L444)
- [D4-GL-01 — backend/services/gl_service.py:755](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L755); terkait: [backend/services/gl_service.py:783](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L783), [frontend/src/features/finance/GeneralLedger.jsx:369](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/GeneralLedger.jsx#L369)
- [D4-GL-02 — backend/services/gl_service.py:640](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L640); terkait: [backend/services/gl_service.py:524](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L524), [backend/schemas_finance.py:53](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_finance.py#L53), [backend/services/gl_service.py:2974](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L2974), [backend/services/financial_statement_service.py:88](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L88)
- [D4-EQ-01 — backend/services/equity_statement_service.py:57](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/equity_statement_service.py#L57); terkait: [frontend/src/features/finance/EquityChangesTab.jsx:61](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/EquityChangesTab.jsx#L61), [backend/services/financial_statement_service.py:62](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L62), [backend/routers/financial_statements.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/financial_statements.py#L90)
- [D4-COA-01 — backend/services/financial_statement_service.py:54](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L54); terkait: [backend/services/financial_statement_service.py:40](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L40), [backend/services/gl_service.py:507](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L507), [backend/routers/gl.py:60](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/gl.py#L60), [backend/services/gl_service.py:651](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L651)


Empat perubahan lifecycle/validation CLOSE-01/02 dan GL-01/02 berada pada FASE-01. COA-01 berada pada FASE-03 untuk scope/dimensi, dan EQ-01 pada FASE-04 untuk menjaga definisi metrik dan roll-forward bersama. Dokumen 02, tracker dan prompt fase mencantumkan penyebab, potongan kode, expected/actual, acceptance dan hubungan antar temuan.

Bukti tersedia pada latest/repro/closing_reversal_probes.py, closing-reversal-results.json dan latest/evidence/closing-reversal-probes.log. Browser DOM, seluruh kombinasi fiscal year/role, semua source document dan printer belum diverifikasi. Hasil ini bukan sertifikasi seluruh finance/semua flow atau coverage 100%.
