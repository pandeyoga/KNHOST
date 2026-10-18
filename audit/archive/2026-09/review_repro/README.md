# Reproduksi review Astra

Clone KNHOST ke folder KNHOST di sebelah script, checkout commit `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`; atau set environment variable KNHOST_REPO ke absolute path clone tersebut. Jalankan `python review2_flow_proofs.py`. Python standard library cukup: dependency aplikasi digantikan model terbatas dalam harness. Output JSON ditulis di folder script.

Ini harness karakterisasi cacat pada baseline, bukan suite integrasi dan bukan regression test yang seharusnya tetap lulus sesudah perbaikan. Sesudah patch, ubah expected outcome untuk memverifikasi invariant yang benar. Tidak membutuhkan credential atau akses produksi.


## Putaran lanjutan

Jalankan `python review3_proofs.py` dengan `KNHOST_REPO` yang sama. Script ini mengimpor harness dasar `review2_flow_proofs.py`; simpan keduanya di folder yang sama. Hasil ditulis ke review3_proofs.json. Ada14 skenario, terdiri dari13 karakterisasi bug dan1 kontrol. Pernyataan hasil/hambatan detail ada pada16_BUKTI_UJI_LANJUTAN.md.
