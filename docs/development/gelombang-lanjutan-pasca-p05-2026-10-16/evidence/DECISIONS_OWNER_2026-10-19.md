# Jawaban owner atas keputusan pending — 2026-10-19

Sumber: chat sesi E1 dengan owner (pandeyoga), 2026-10-19. Jawaban dicatat apa adanya. Status BACKLOG = `resolved` untuk 15 keputusan yang dijawab; 8 lainnya tetap `pending` (owner minta penjelasan dulu). **Belum dianalisa/diimplementasi**: dikerjakan sesi berikutnya (lihat HANDOFF_SESI_2026-10-19.md).

## A. Retur (KLR)
Kasus acuan KLR-01/02: roll 120 yd, yard 46–60 cacat (15 yd), 1–45 baik (45 yd), 61–120 baik (60 yd).

| ID | Jawaban owner (kutipan/ringkas setia) |
|---|---|
| KLR-01 | Yang benar **(b)**: customer menerima dua potong baik, kompensasi senilai qty cacat. "Potongan tidak kelipatan 15 yard, jadi benar-benar kain yang cacat saja; saat QC MD input yard qty cacatnya saja." Mesin QC hanya satuan yard; bila master produk kg → **konversi otomatis** yard→kg. (Persetujuan customer atas bentuk potongan: tidak disebut.) |
| KLR-02 | Nilai kompensasi = **harga transaksi awal** (setelah diskon/harga khusus) × qty yang disetujui. |
| KLR-03 | Pengganti dihitung **yard** (yard = source of truth), memakai qty **aktual final yang diterima saat QC**. |
| KLR-04 | Pengganti lebih (mis. 205 vs 195): **selisih tetap dibayar customer**. Pengganti kurang (190 vs 195): kekurangan **bisa refund atau saldo**. |
| KLR-05 | Selisih dinilai dengan **harga transaksi asal**. |
| KLR-06 | Discount tanpa barang kembali **boleh diputus dari foto/video**; **nilai/harga tetap keputusan Finance**. |
| KLR-07 | Discount berbentuk **nominal rupiah**, per item, **hanya untuk qty yang cacat**. |
| KLR-08 | Tidak ada aturan pasti, keputusan manusia. Jadikan **checklist informasi** (hangtag hilang / kain dipotong / bukti pengganti), **Finance yang memutus final**, sistem **hanya memberi peringatan** (bukan blok). |
| KLR-09 | Customer: ajukan hari ke-20, barang tiba hari ke-24 → **masih sah** (batas = tanggal pengajuan). Supplier: batas 21 hari dihitung **sampai klaim dikirim**. |
| KLR-10 | SO asal lunas, ada utang SO lain → customer **boleh memilih refund atau saldo** (tidak wajib potong tagihan lain). |
| KLR-11 | Penanggung ongkir retur customer, perjalanan Jakarta–Rancamalang QC, dan kirim pengganti: **bisa keduanya, jadikan opsi** (dipilih per kasus). |

## B. Gudang, QC, Keuangan (KLX)
| ID | Jawaban owner |
|---|---|
| KLX-01 | Memang **bisa 2 kode** (LOT pabrik + LOT KN). LOT pabrik sama datang lagi di SJ berikutnya → **tidak memakai yang sudah ada** (LOT KN baru). Pola penamaan & reset LOT KN: **diputuskan user** (input bebas, tidak diatur sistem). |
| KLX-02 | Sementara **user sendiri yang mengisi** (kode cacat, poin, grade); ERP hanya menyediakan **form**. Otomatisasi menyusul bila ada info baru. |
| KLX-03 | **Buatkan dulu dan bisa dikonfigurasi** (cutoff, tanggal bayar, acuan periode). |

## C. Lain-lain
| ID | Jawaban owner |
|---|---|
| OPS-01 | **Tidak ada batas** nilai kerugian opname yang memerlukan persetujuan tambahan (melengkapi jawaban 2026-10-18 di evidence/L10/report.md). |

## Ditunda (tetap pending, owner minta dijelaskan)
DATA-01, DES-02, DES-03, DES-04, HW-01, HW-02, HR-01, UAT-01.
