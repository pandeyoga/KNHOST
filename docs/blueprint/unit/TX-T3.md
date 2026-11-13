# TX-T3 — Ekspor Coretax, PPh 23, dan bukti potong (tertahan)

| | |
|---|---|
| Gelombang | Modul faktur pajak |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | TX-T2 |
| Menutup temuan | — |
| Keputusan | K-08 |
| Standar | §2, §3.4 (N1, N3), §5 (D4), §6 |
| Lingkungan uji | B |

**Status awal `tahan` — titik henti H8 dan K-08** ("di luar blueprint sampai diminta"). Juga menyentuh H4: bentuk berkas
impor dan tarif potong berasal dari peraturan. Rincian penuh ditulis setelah pemilik menjawab pertanyaan di akhir.

## Tujuan

Faktur keluaran dan masukan bisa diunggah ke Coretax tanpa diketik ulang, dan PPh 23 yang dipotong punya bukti potong.

## Keadaan sekarang

`[dibaca]` pada `3132cc4`: tidak ada ekspor berformat Coretax; faktur hanya punya cetakan dan ekspor umum. Rekap PPN
ada di `backend/services/input_tax_service.py:113` (`vat_summary`). PPh dicatat manual per masa
(`backend/routers/tax_center.py:58` (`create_pph_record`)) dari daftar butir `backend/config_catalog_core.py:54`
(`tax.pph_items`) yang bawaannya kosong. Tidak ada dokumen bukti potong (temuan SL-13, K-08).

## Perubahan

Lingkup yang direncanakan (belum boleh dikerjakan). Bahan dari unit lain: data pajak pelanggan dan potret aturan
(TX-T1); status, sumber, dan dokumen retur (TX-T2); keunikan nomor seri dan kunci masa pajak (PK-40).

- **Data:** catatan tiap berkas ekspor (PT, masa, daftar faktur, pembuat); dokumen bukti potong PPh 23 per tagihan jasa.
- **Server:** pembuat berkas impor faktur keluaran (dan masukan bila diminta) per PT per masa — "Semua PT" ditolak;
  faktur yang sudah diekspor ditandai; PPh 23 dihitung saat tagihan jasa dibukukan, bukan dicatat manual.
- **Pengaturan:** pemetaan kolom dan tarif potong bertanggal berlaku, isinya dari berkas pemilik atau konsultan pajak.
- **Izin dan peran:** `tax_invoice.view` untuk ekspor; izin bukti potong ditetapkan saat unit dilepas. **Layar:** tombol
  "Ekspor Coretax" di Faktur Keluaran dan Faktur Masukan; daftar bukti potong di tab PPN & PPh.

## Uji penerimaan

Ditulis saat unit dilepas. Syarat minimal yang sudah pasti: Σ PPN di berkas ekspor = rekap PPN masa itu; faktur `draf`,
`diganti`, `batal` tidak ikut; ekspor PT-A tidak memuat faktur PT-B; berkas contoh lolos unggah uji oleh pemilik.

## Langkah kerja

Pemilik menjawab dan menyerahkan contoh berkas → reviewer mengubah status menjadi `siap` → berkas ini dilengkapi → dikerjakan.

## Di luar lingkup

Unggah langsung ke layanan pajak (tanpa campur tangan orang), SPT masa, dan PPh 21 (lihat PK-46).

## Asumsi dan risiko

Yang harus diputuskan atau diserahkan pemilik: (1) apakah ekspor Coretax dibutuhkan sekarang, untuk PT mana; (2) contoh
berkas impor Coretax yang berlaku beserta keterangan kolomnya; (3) jasa apa saja yang dipotong PPh 23 dan tarifnya,
dikonfirmasi konsultan pajak; (4) bentuk bukti potong; (5) siapa yang mengunggah dan menyimpan akun layanan pajak.

- `ASUMSI:` ekspor berupa berkas yang diunggah orang; sistem tidak memegang sandi layanan pajak.
- `RISIKO:` format berubah mengikuti peraturan; karena itu pemetaan kolom dijadikan pengaturan, bukan kode.
