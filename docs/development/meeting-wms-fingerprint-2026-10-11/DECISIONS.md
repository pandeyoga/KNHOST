# Register Keputusan Bisnis dan Prasyarat

Status awal seluruh keputusan adalah open; status hidup dan sumber persetujuan ada dalam BACKLOG.json/hasil render TRACKER.md.

Kebutuhan dasar yang sudah diberikan pengguna tetap berlaku. Register ini merinci parameter yang belum final; developer tidak boleh membuat persetujuan atau aturan produksi fiktif.

## DEC-01 — Keep/Pending

**Terkait:** IMP-02, IMP-03  
**Fungsi pemberi keputusan:** Admin Sales / pemilik proses Sales

**Keputusan/data:** Status aktif/batal/tolak, basis qty shortage, perlakuan pemenuhan parsial dan barang committed tetapi masih transit; apakah Keep punya batas waktu.

**Sambil menunggu:** Definisi Keep = belum diverifikasi sudah pasti. Tidak mengaktifkan auto-expiry atau auto-reservation. Kebijakan metrik yang belum diputuskan ditampilkan sebagai membutuhkan konfigurasi.

## DEC-02 — Special Order

**Terkait:** IMP-07, IMP-08  
**Fungsi pemberi keputusan:** Sales / MD / pejabat persetujuan

**Keputusan/data:** PIC pembuat/pengelola, ACC desain pelanggan, kriteria siap proofing, persetujuan/pengiriman parsial, pemecahan SO/pengadaan.

**Sambil menunggu:** Bangun multi-line, versioning, dan permission yang dapat dikonfigurasi; jangan menetapkan PIC atau auto-ACC berdasarkan asumsi.

## DEC-03 — Sampel dan Admin Cutting

**Terkait:** IMP-09, IMP-10  
**Fungsi pemberi keputusan:** PIC sampel / Gudang / Sales

**Keputusan/data:** Admin Cutting alias Admin Sampel atau peran terpisah; SOP finishing, qty/biaya/approval Hanger-Katalog-Cutting dan pelepas kirim.

**Sambil menunggu:** Tiga jenis serta handoff sudah pasti. Struktur state dan konfigurasi dapat dibuat; aturan tarif dan pelepasan baru belum diaktifkan tanpa keputusan.

## DEC-04 — Grade dan BS

**Terkait:** IMP-11, IMP-04  
**Fungsi pemberi keputusan:** Sales / MD / pengelola harga

**Keputusan/data:** Matriks standar pelanggan-grade, minimum/larangan/prioritas, override, dan representasi penawaran BS pada tampilan Sales warna-only.

**Sambil menunggu:** Harga non-BS sama pada kondisi komersial sama sudah pasti. Jangan menebak grade dari label brand atau menampilkan informasi BS yang bertentangan dengan kebijakan Sales.

## DEC-05 — Dataset dan lifecycle master

**Terkait:** IMP-12, IMP-13, IMP-14, IMP-15  
**Fungsi pemberi keputusan:** PIC master / MD / pembelian

**Keputusan/data:** Kode/nama bahan dan supplier/color, pasangan internal, satuan/spec, mapping ambigu, PIC impor dan kebijakan nonaktif/hapus.

**Sambil menunggu:** Siapkan template dan dry-run; data ambigu masuk review. Identitas dan dokumen lama tidak dihapus atau digabung otomatis.

## DEC-06 — MD Quality / QC / R&D existing

**Terkait:** IMP-16, IMP-17  
**Fungsi pemberi keputusan:** MD / Gudang / approver mutu

**Keputusan/data:** Objek dan tahap MD Quality, kebutuhan arrival QC, random check, approver uji tambahan, efek hasil terhadap spec aktif dan hold/release.

**Sambil menunggu:** Pertahankan kontrol mutu existing. Uji tambahan tanpa perubahan identitas tidak membuat SKU baru; revisi/hold baru membutuhkan kebijakan yang eksplisit.

## DEC-07 — Resep dan restock

**Terkait:** IMP-18, IMP-19  
**Fungsi pemberi keputusan:** MD / pembelian / produksi

**Keputusan/data:** Article-source supplier/makloon/both, supplier/mitra/resep, yield/waste/unit conversion, lead time, priority, dan ambang restock.

**Sambil menunggu:** Tidak default semua artikel ke both atau resep 1:1. Mapping belum diketahui terlihat sebagai belum dikonfigurasi; operasi legacy yang sah tetap dipertahankan selama transisi.

## DEC-08 — OCR penerimaan

**Terkait:** IMP-21  
**Fungsi pemberi keputusan:** Gudang / pembelian / supplier liaison

**Keputusan/data:** Contoh SJ/packing list, informasi per-roll, ambang review, kategori yang boleh mengadopsi ukuran dokumen atau wajib ukur ulang.

**Sambil menunggu:** OCR menjadi kandidat; tidak auto-post stok dan tidak membagi total ke roll rata-rata tanpa bukti.

## DEC-09 — Hak lokasi dan cakupan data

**Terkait:** IMP-20, IMP-04, IMP-24  
**Fungsi pemberi keputusan:** Pemilik sistem / kepala Gudang / Sales

**Keputusan/data:** User-site/warehouse, supervisor, multi-site, owner yang boleh memakai shared, serta scope agregasi global Sales dan ekspor.

**Sambil menunggu:** Assignment dan migration review disiapkan. Jangan menganggap semua pengguna berhak semua lokasi atau semua stok lintas entitas sellable.

## DEC-10 — Rules dan kapasitas WMS

**Terkait:** IMP-24, IMP-29  
**Fungsi pemberi keputusan:** Kepala Gudang / MD / pemilik proses

**Keputusan/data:** Atribut hard/soft, pewarisan, satuan kapasitas roll/kg/volume/panjang, override, dan otoritas pengecualian.

**Sambil menunggu:** Dedicated/owner dan status fisik tetap wajib. Kapasitas tidak diberi unit/batas fiktif; aturan baru configurable tetapi belum diaktifkan tanpa konfigurasi sah.

## DEC-11 — Transfer terkait SO

**Terkait:** IMP-26, IMP-27  
**Fungsi pemberi keputusan:** Admin Sales / Gudang sumber-tujuan / logistik

**Keputusan/data:** Tujuan fulfillment, actual receipt, parsial/rusak/hilang, pembatalan saat transit, PIC, bukti dan dokumen dua kaki perjalanan.

**Sambil menunggu:** Komitmen roll tidak dilepas agar bisa transfer. Receipt hanya aktual; exception tidak disembunyikan sebagai completed.

## DEC-12 — Opname

**Terkait:** IMP-28  
**Fungsi pemberi keputusan:** Gudang / approver persediaan / Finance

**Keputusan/data:** Cutoff/freeze atau count sambil transaksi berjalan, scope, penghitung-approver, toleransi, kasus tag/roll surplus/hilang dan adjustment.

**Sambil menunggu:** Tidak melakukan adjustment sebelum approval; salah lokasi tidak diposting sebagai kehilangan. Hasil RFID bukan bukti ukuran benar.

## DEC-13 — Dampak komersial dan Finance

**Terkait:** IMP-06, IMP-11, IMP-18, IMP-26, IMP-28  
**Fungsi pemberi keputusan:** Admin Sales / MD / Finance

**Keputusan/data:** Persetujuan qty roll utuh vs pesanan, perubahan nilai tagihan, perlakuan biaya/WIP, ownership internal, valuasi/akun selisih dan reversal.

**Sambil menunggu:** Gunakan kebijakan Finance existing yang telah sah. Jangan mengubah invoice historis, menyamakan HPP semua grade, atau menetapkan metode costing baru.

**Diputuskan pemilik (2026-10-14, ACC-34):** Order Makloon yang dibatalkan SESUDAH bahan dikirim — bahan tetap tercatat di mitra dan WIP (1-1350) tetap sampai retur bahan dicatat manual; tidak ada pengembalian stok otomatis.


## DEC-14 — Hardware fingerprint

**Terkait:** IMP-30, IMP-35  
**Fungsi pemberi keputusan:** Pemilik sistem / HR / pengadaan perangkat

**Keputusan/data:** Calon model, unit/firmware, dokumen protokol, dukungan custom-server, log offline dan akses unit PoC.

**Sambil menunggu:** PoC receiver/log/registry dapat memakai simulator; kompatibilitas direct hardware tetap waiting_hardware sampai bukti unit nyata ada.

## DEC-15 — Perhitungan absensi

**Terkait:** IMP-31, IMP-32, IMP-33  
**Fungsi pemberi keputusan:** HR / approver payroll

**Keputusan/data:** Device-user mapping, timezone, shift termasuk overnight, toleransi, multiple punches, missing punches, overtime, lintas lokasi dan correction.

**Sambil menunggu:** Raw event disimpan dan dapat direview. Tidak menebak kehadiran/lembur atau mengesahkan payroll otomatis dari event.

## DEC-16 — Pilot dan operasi

**Terkait:** IMP-30, IMP-34, IMP-35; seluruh scope rilis  
**Fungsi pemberi keputusan:** Pemilik sistem / HR / operasional / deployment owner

**Keputusan/data:** Jaringan dari mesin ke ERP, kemampuan koneksi aman perangkat, lokasi/perangkat pilot, operator, UAT, konfigurasi produksi dan otorisasi rilis.

**Sambil menunggu:** Siapkan runbook dan bukti staging. Tidak membeli mesin, menghubungi vendor, atau deploy produksi otomatis melalui paket plan ini.
