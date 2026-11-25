# Hasil — Meja gelombang 2 (Admin Sales + Keuangan di tempat, rincian nota Keuangan)

Tanggal: 25 Nov 2026 · Cabang: `claude/nifty-carson-jjx3c8` · Garis dasar: `4323295` (gelombang 1 selesai) · Pohon akhir:
`6f519d8`.

- **Rancangan:** `docs/superpowers/specs/2026-11-25-meja-kerja-di-tempat-design.md`, §5.3–§5.7a dan §6 gelombang 2.
- **Rencana:** `docs/superpowers/plans/2026-11-25-meja-gelombang-2.md`, 10 tugas.

**Status: selesai.** Belum digabung ke `main`. Atas perintah pemilik ("langsung lanjut kerjakan saja semua"), pekerjaan lanjut ke Lapor Bayar CBD tanpa menunggu validasi.

## 1. Yang berubah untuk pengguna

| Permintaan pemilik | Sekarang |
|---|---|
| "Di finance semua nota pembelian atau penjualan jika di-klik bisa melihat detail barangnya" | Nomor pesanan, tagihan pemasok, PO, kwitansi, kontrabon, retur, pesanan khusus, dan permintaan internal membuka **pop-up rincian** berisi barang, jumlah, harga, dan total. Layar yang tersambung: Piutang › rincian umur, Penagihan & Penerimaan, Kwitansi, Kartu pelanggan (Tagihan, Rekening koran), Faktur Keluaran (kini juga tabel barang), Selisih bayar, Denda (dasar pesanan), Hutang per pemasok, Kontrabon, Kartu pemasok (kolom barang tagihan & retur beli), Transaksi Kas (sumber + jurnal). "Jejak" tetap ada di sampingnya. |
| Dokumen terkait di dalam rincian | Satu pop-up dengan "‹ Kembali". Contoh: kwitansi → klik pesanan teralokasi; kontrabon → gabungan baris semua fakturnya → klik faktur. Klik nama pelanggan/pemasok membuka kartunya. |
| Pop-up meja kurang isi | Pop-up Meja Admin Sales dan Meja Keuangan memuat **rincian dokumen sesuai antrean**: pesanan (juga untuk baris uang masuk), kwitansi untuk selisih bayar, pesanan dasar untuk denda, PO/tagihan untuk hutang, retur, pesanan khusus, permintaan internal, kontrabon. Batas cadangan, tanggal masuk, kota, dan barang kurang tetap tampil. Berlaku juga di Pelacak SO dan HP. |
| Selesaikan di tempat sebanyak mungkin | **Meja Keuangan:** putuskan selisih bayar, terbitkan denda (konfirmasi), setujui bayar sample, catat sudah ditagih (tidak ditawarkan lagi bila sudah diingatkan ≤ 7 hari). **Meja Admin Sales:** tetapkan sales (hanya bagi pemegang izin penetapan sales), catat sudah diingatkan, tolak permintaan internal (dengan alasan); "Lihat" cukup membuka pop-up. Semua memakai pemeriksaan dan endpoint yang sama dengan layar asalnya. Logikanya disatukan, jadi layar asal dan meja memakai satu sumber. |
| Huruf tidak konsisten | Dialog periksa pesanan, rencana pemenuhan, dan keputusan selisih bayar kini memakai skala huruf dan warna baku. |

**Masih pindah layar** (tombolnya bertanda ikon "buka layar"), karena alurnya bertahap:
- proses retur dan retur tukar (penerimaan barang, penyelesaian);
- pesanan khusus (catat ACC, kunci harga, siapkan);
- konversi permintaan internal;
- tinjau nota kredit;
- putus kompensasi retur;
- kontrabon (verifikasi, setujui, sengketa);
- posting gagal.

Tangkapan: folder `2026-11-25-meja-gelombang-2-hasil/` (log di `tangkap_mg2_log.txt`).
- Pratinjau dari 7 layar Keuangan.
- 3 pop-up Meja Keuangan dan 4 pop-up Meja Admin Sales, semuanya berisi rincian dokumen.
- HP Admin Sales, tanpa tombol Jejak.

Transaksi Kas di data acuan tidak punya baris bersumber dokumen berpratinjau. Tautannya hanya terbukti di uji.

## 2. Tugas → commit

| Tugas | Commit |
|---|---|
| T1 Fondasi pratinjau dokumen + pesanan | `8d1364f`, `931c1c8` |
| T2 Tagihan pemasok, PO, kwitansi, kontrabon | `fa1d46c` |
| T3 Retur, pesanan khusus, permintaan internal (+ pemuat dipisah dari registri) | `78cfaf5` |
| T4 Nomor nota sisi piutang | `40ce31c` |
| T5 Nomor nota sisi hutang & kas | `05b1623` |
| T6 Pop-up meja memuat rincian per antrean | `81b9ff2`, `0e7be23` |
| T7 Aksi di tempat Meja Keuangan | `258d689`, `3b3ac81` |
| T8 Aksi di tempat Meja Admin Sales | `4501212` |
| T9 Huruf & warna dialog yang dipakai ulang | `df72305` |
| T10a Standar `04_POLA_UI.md` + peta kode | `a5199a4` |
| Perbaikan tinjauan akhir | `6f519d8` |

Alur tiap tugas: pelaksana → tinjauan tugas (spesifikasi + mutu) → putaran perbaikan bila perlu. Sesudah semua tugas: tinjauan seluruh cabang dengan 0 Critical dan 2 Important, keduanya diperbaiki di `6f519d8`:
- kartu pihak tertutup pratinjau;
- tombol Jejak mati di HP.

## 3. Uji (apa adanya)

- **Backend `tests_mem` penuh** di `6f519d8`: 2850 passed, 2 skipped, 3 xfailed, **0 failed**.
- **Jest penuh** di `6f519d8`: 2050/2051 lulus, 264/266 suite. Yang gagal `odItemCancel` dan `phase4R2`, kendala lingkungan wadah yang sama dengan garis dasar sebelum pekerjaan ini.
- **Uji backend ber-Mongo** `tests/test_decisions_d4.py` + `test_uat_v3_ui_gaps2.py`: 7 lulus, 2 gagal. Kedua yang gagal juga gagal di garis dasar sebelum tugas 7, jadi bawaan dan bukan dari pekerjaan ini.

### 3a. Gate

Dijalankan sekali di `6f519d8`.

| Mode | FAIL (garis dasar) | Lebih merah | Menjadi hijau |
|---|---|---|---|
| `--quick` | 10 (16) | 0 | 4 |
| `--ci` | 36 (43) | 2 | 7 |

- Dua yang lebih merah di `--ci` adalah POC bawaan: `POC Cek Kenyataan Peran` dan `POC FASE N`. Keduanya sudah FAIL sejak gate 23 Nov, sebelum pekerjaan meja.
- Pembanding per pelanggaran (`bandingkan_pelanggaran_gate.py`) tidak menemukan pelanggaran baru, baik terhadap garis dasar resmi 15 Nov maupun terhadap gate akhir gelombang 1.

## 4. Keputusan pelaksanaan (di luar rancangan — periksa)

- **Rincian di pop-up adalah tampilan baru yang ringkas dan hanya-baca**, bukan panel lama (`OrderDetailPanel`, `ReturnDetail`, dst.).
  - Alasannya: panel lama itu halaman penuh yang butuh banyak penangan dari layar induknya.
  - Akibatnya: panel lama di layar asal belum ikut diseragamkan hurufnya. Penyeragaman huruf hanya untuk dialog yang benar-benar dipakai ulang.
- **Satu pop-up dalam satu waktu.**
  - Dari rincian dokumen, klik nama pelanggan/pemasok menutup rincian lalu membuka kartu.
  - Dari kartu, klik nomor dokumen membuka rincian di atas kartu; menutup rincian kembali ke kartu.
- **Kontrabon menampilkan gabungan baris maksimal 20 faktur pertama.** Barang diambil dari tiap tagihan; endpoint baru tidak diperlukan.
- **"Buka layar penuh" tidak ada untuk tagihan pemasok, kwitansi, dan kontrabon** karena belum ada layar tujuan baku untuk satu dokumen itu. Jejak tetap ada.
- **Baris "Setujui bayar sample" di Meja Keuangan** langsung membuka dialog persetujuan (dulu "Tinjau" → pindah layar). Total dihitung sama dengan Meja Sample.
- **Teks konfirmasi terbitkan denda** disamakan dengan Meja Kredit, termasuk di panel Denda.
- **Alasan penetapan sales opsional**, sama dengan server dan kartu pelanggan.
- **Tombol Jejak tidak ada di pop-up meja HP**, karena layar Jejak belum ada di tampilan HP.

## 5. Untuk pemilik

1. **Izin `sales_force.assign`:** Admin Sales bawaan tidak memegangnya, jadi tombol "Tetapkan sales" di tempat belum muncul. Untuk sementara, antrean "Pelanggan tanpa sales" tetap pindah layar. Perlukah izin itu diberikan ke Admin Sales secara bawaan? Matriks izin tidak diubah.
2. **Label status yang belum Indonesia:** status pesanan "Partially Shipped" di pratinjau masih berbahasa Inggris, karena daftar label baku (`utils/docStatus.js`) belum punya `partially_shipped`. Ini dirapikan di pekerjaan Lapor Bayar, yang memang menyentuh status pesanan.

## 6. Catatan kecil yang ditunda (tidak memblokir)

- **Pratinjau:**
  - nama barang ditebalkan di baris tagihan/PO;
  - uji kontrabon induk gagal / tanpa faktur;
  - `created_by` retur bisa tampil sebagai id;
  - satuan bawaan "meter" pada retur;
  - total retur menjumlah perkiraan yang tidak tampil di kolom.
- **Meja:**
  - "Buka layar penuh" pada rincian bertumpuk membuka layar baris, bukan dokumen yang sedang tampil;
  - dialog selisih bayar berkedip saat memuat;
  - uji status sibuk hanya untuk Meja Keuangan.
- **Gaya:**
  - garis dan latar memakai token lembut yang sama pada beberapa spanduk;
  - beberapa `<b>` mentah;
  - warna mentah lencana RPB di Piutang dan antrean Selisih (sudah di garis dasar penjaga).
- **Tabel:** kepala tabel tetap HURUF BESAR mengikuti gaya baku tabel aplikasi (CSS global). Rancangan hanya mewajibkan huruf biasa untuk tabel Pelacak.
