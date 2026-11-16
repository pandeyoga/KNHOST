# Usulan perbaikan — batch B1 (16 Nov 2026, HEAD `91a3ec0`)

Dokumen ini hanya usulan. Tidak ada kode produksi yang diubah. Tiap butir merujuk putusan dan uji di
`docs/reviews/2026-11-13/hasil/validasi-PK-*.md`. Enam uji yang "gagal" di hitungan pemeriksa adalah uji bantahan
reviewer yang berhasil membantah (PK-05: 2, PK-17: 2, PK-31: 1, PK-38: 1); itu bukan uji pelaksana yang rusak.

Urutan pengerjaan yang disarankan: SL-01 → IC-07 → IA-03 → IA-01, lalu tiga keputusan pemilik.

## A. Empat butir yang dibuka lagi

### SL-01 (Kritis) — void pembayaran dari pintu faktur atas pelunasan milik kontrabon

- Uji pembukti: `test_SL01_jalur_lain_void_bayar_faktur_milik_kontrabon` (`bukti/review-B1/test_bantah_PK05.py`).
- Letak: `backend/routers/vendor_bills.py:668` (void pembayaran faktur) tidak mengenali baris pelunasan yang lahir dari
  pembayaran kontrabon (`payments[].contra_bon_id`, satu kas untuk banyak faktur).
- Usulan (pilih satu):
  1. Tolak 409 di pintu faktur bila baris pelunasan membawa `contra_bon_id`, dengan pesan yang mengarahkan ke
     pembatalan pembayaran kontrabon. Perubahan kecil, risiko rendah. **Disarankan.**
  2. Biarkan pintu faktur, tetapi balik seluruh alokasi kas itu sekaligus (semua faktur dalam kontrabon terbuka lagi,
     status kontrabon mundur). Lebih besar; butuh pintu "batal bayar kontrabon" yang hari ini belum ada.
- Uji terima: uji bantahan di atas menjadi lulus; tambah uji "void dari pintu kontrabon membuka semua faktur dan
  jurnal balik = jumlah kas".
- Data yang sudah ada: kueri hanya-baca untuk mencari kas kontrabon ber-status `void` dengan kontrabon masih `paid`.

### IC-07 (Tinggi) — retur antar-PT kedua melebihi nilai transaksi

- Uji pembukti: `test_IC07_koreksi_retur_kedua_melebihi_nilai` (`test_bantah_PK31.py`). Catatan: draf kedua
  disisipkan sebagai fixture; pintu "buat draf" belum dijalankan lewat API.
- Letak: persetujuan retur tidak menghitung ulang sisa yang boleh diretur; `refund_due_of`
  (`backend/services/interco_service.py:878`) tidak dibatasi `settled_amount`.
- Usulan: (1) saat menyetujui retur, hitung Σ retur disetujui + retur ini ≤ nilai transaksi, tolak 409 bila lewat;
  (2) batasi `refund_due` pada uang yang benar-benar diterima; (3) jalankan pintu buat-draf lewat API untuk
  memastikan apakah dua draf sekaligus memang bisa dibuat.
- Uji terima: uji bantahan menjadi lulus; uji balapan dua persetujuan serentak hanya satu yang lolos.

### IA-03 (Tinggi) — papan Meja Finance menampilkan nominal kontrabon kepada gudang

- Uji pembukti: `test_IA03_tanpa_izin_gudang_papan_finance_kontrabon_bertotal` (`test_bantah_PK17.py`).
- Letak: `backend/routers/home.py:112` (papan) tidak memakai penyaring nominal yang dipakai
  `backend/routers/contra_bons.py`.
- Usulan: baris papan kontrabon lewat penyaring yang sama; nominal dan nama pemasok hanya untuk pemegang
  `vendor_bill.view`. Perbaiki juga fixture uji pelaksana supaya kontrabon membawa `totals` (itu sebabnya lolos).
- Uji terima: uji bantahan lulus; akun finance tetap melihat nominal.

### IA-01 (Tinggi) — nominal Nota Kredit terbaca di pencarian Jejak Dokumen

- Uji pembukti: `test_IA01_tanpa_izin_jenis_tanpa_perm_nota_kredit_dan_kontrabon` (`test_bantah_PK17.py`).
- Letak: jenis `credit_note` tanpa `perm` di `backend/services/doc_refs_service.py:182`, sehingga `redact_node`
  (`:419-425`) tidak menyaringnya.
- Usulan: beri `perm` pada `credit_note` (tinjau `doc_amendment`); pasang penyaring yang sama di
  `backend/services/document_relations_service.py:248` dan `:262` bersamaan dengan pembetulan field (RV-02), supaya
  pembetulan field tidak membuka kebocoran baru.
- Uji terima: uji bantahan lulus; tambah uji yang memeriksa setiap jenis dokumen bernominal punya `perm`.

## B. Tiga butir yang menunggu keputusan pemilik

| Butir | Pertanyaan | Bila "ya" | Bila "tidak" |
|---|---|---|---|
| SL-02 | Server menolak bayar hutang tanpa kunci anti-ganda? | `POST /vendor-bills/{id}/pay` dan `/contra-bons/{id}/pay` menjawab 400 tanpa `Idempotency-Key` (`backend/services/ap_payment_service.py:293-304`); skrip data contoh ikut disesuaikan | Butir ditetapkan `verified` dengan catatan: integrasi luar wajib mengirim kunci |
| IA-02 | Jalankan `scripts/apply_pk17_role_cleanup.py --apply` di data nyata sekarang? Finance boleh melihat margin antar-PT? | Jalankan mode baca-saja dulu, periksa daftar izin yang dicabut, baru `--apply`; margin: cabut `interco_finance.view` dari Finance atau pisahkan izinnya | Izin lama gudang atas tagihan tetap hidup di instalasi yang ada |
| FX-10 | Batas hapus piutang tanpa kas dihitung kumulatif? | `ar_reduction_guard.periksa` (`backend/services/ar_reduction_guard.py:79-105`) menjumlah pengurang sebelumnya menurut lingkup pilihan pemilik (per pesanan paling sederhana) | Butir ditetapkan `verified`; pecah nominal 2 × Rp600.000 diterima sebagai perilaku sah |

## C. Temuan baru reviewer

- RV-01: panggil pemeriksa periode di awal `reverse_decision` (`backend/services/payment_variance_service.py:1072`).
- RV-02: lihat IA-01 di atas (dikerjakan bersama).
- RV-03: masih dugaan dari membaca kode (`backend/routers/landed_cost.py:372`); jalankan uji dulu sebelum diperbaiki.
- RV-04, RV-05: dua galat lint lama di `main` (`backend/routers/customers.py:326`,
  `backend/services/design_studio_service.py:130`); hapus impor ganda dan ganti nama salah satu `category_of`.
