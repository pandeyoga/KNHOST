# Rencana keuangan — fondasi, menu, dan modul baru (13 Nov 2026)

Paket rencana ini menjawab permintaan pemilik setelah audit keuangan: menu apa yang bisa disatukan, bagaimana supaya
modul tambahan tidak menjadi masalah baru, bagaimana perbaikan dijalankan oleh agen coding dengan benar, dan rancangan
untuk insentif, piutang lanjut, faktur pajak, cara bayar, asisten keuangan, serta dampaknya ke HR dan penggajian.

> Untuk **mengerjakan**, pakai `docs/blueprint/` — di sana tiap unit punya spesifikasi rinci, uji penerimaan, dan
> urutan terbaru (termasuk unit peran, pengaturan, dan konfigurasi perusahaan dari audit 13 Nov).

**Semua isinya rencana.** Tidak ada kode aplikasi yang diubah. Dasar: laporan
[`../AUDIT_KEUANGAN_2026-11-13.md`](../AUDIT_KEUANGAN_2026-11-13.md) (139 temuan) dan penelusuran kode lanjutan di
`9834947` yang menambah 48 temuan.

## Isi

| Berkas | Isi | Untuk siapa |
|---|---|---|
| [`01_PENGGABUNGAN_MENU.md`](01_PENGGABUNGAN_MENU.md) | Menu keuangan dari 18 entri di 4 grup menjadi 10 entri di 2 grup; SDM menyerap insentif; penyatuan layar | Pemilik; pelaksana PK-44 |
| [`02_PAKET_KERJA_FONDASI.md`](02_PAKET_KERJA_FONDASI.md) | 46 paket kerja berurutan yang menutup 139 temuan audit + 8 temuan tambahan yang murah; tiap paket punya uji "selesai bila" | Pelaksana; reviewer |
| [`03_PANDUAN_PELAKSANA.md`](03_PANDUAN_PELAKSANA.md) | Cara menjalankan satu paket: urutan, cara uji, larangan, kapan berhenti dan bertanya, templat perintah | Pelaksana |
| [`04_ATURAN_MODUL_BARU.md`](04_ATURAN_MODUL_BARU.md) | Kontrak posting, aturan entitas/izin/data, penjaga otomatis, daftar periksa "selesai" | Siapa pun yang menambah modul |
| [`05_MEJA_INSENTIF.md`](05_MEJA_INSENTIF.md) | Cari dan jumlahkan capaian; lembar keputusan insentif multi-komponen; sambungan ke gaji | Pemilik; pelaksana |
| [`06_PIUTANG_LANJUT.md`](06_PIUTANG_LANJUT.md) | Profil kredit, jadwal tagihan, gerbang kredit, izin, denda berlapis, rekening koran; catatan hutang | Pemilik; pelaksana |
| [`07_PAJAK_DAN_PEMBAYARAN.md`](07_PAJAK_DAN_PEMBAYARAN.md) | Cara bayar + rekening tujuan + kode bayar; faktur pajak yang bisa diatur | Pemilik; pelaksana |
| [`08_ASISTEN_KEUANGAN.md`](08_ASISTEN_KEUANGAN.md) | Asisten yang membaca, menganalisis, melapor, dan menginput lewat kartu tindakan; pelajaran dari DAHOST | Pemilik; pelaksana |
| [`09_HR_DAN_PAYROLL.md`](09_HR_DAN_PAYROLL.md) | Komponen gaji per PT, antrean masukan, jenis proses gaji; temuan penggajian | Pemilik; pelaksana |
| [`10_KEPUTUSAN_PEMILIK.md`](10_KEPUTUSAN_PEMILIK.md) | 46 keputusan (18 dari audit + 28 baru), masing-masing dengan usulan | **Pemilik — mulai dari sini** |
| [`11_TEMUAN_TAMBAHAN.md`](11_TEMUAN_TAMBAHAN.md) | Indeks 48 temuan tambahan dan penugasannya | Reviewer |

## Urutan besar

```text
SEKARANG      Keputusan pemilik kelompok A (K-01…K-18)  ·  PK-01…04 persiapan dan cek data nyata
FONDASI 1     PK-05, 06 (dua temuan kritis)  →  PK-07…17, 45, 46 (tinggi yang murah)
FONDASI 2     PK-18…25 (satu pola posting di semua jalur uang)
              ├─ sejajar: MN-T1 menu · KM-T1/T2 capaian insentif (baca) · CR-T1 profil kredit · PM-T1 induk cara bayar
              │            · AG-T1/T2 asisten baca
FONDASI 3     PK-26…32 nilai persediaan dan antar-PT  ·  PK-33…35 infrastruktur  ·  PK-36…40 kontrol
MODUL TULIS   KM-T3/T4 lembar insentif → gaji · CR-T2…T5 · PM-T2…T4 · TX-T1/T2 · PY-T1…T4 · AG-T3…T5
LAYAR         PK-41…44 · MN-T2/T3
```

Prinsipnya: bagian **baca** dari modul baru boleh berjalan sejajar dengan fondasi, karena tidak menulis uang dan justru
membantu mencocokkan angka. Bagian **tulis** menunggu paket fondasi yang disebut di tabel prasyarat (`02`, bagian
akhir).

## Kode tahap

| Awalan | Arti | Didefinisikan di |
|---|---|---|
| `PK-nn` | Paket kerja fondasi | `02` |
| `MN-Tn` | Tahap penggabungan menu | `01` §6 |
| `KM-Tn` | Tahap Meja Insentif | `05` §9 |
| `CR-Tn` | Tahap piutang dan kredit | `06` §4 |
| `PM-Tn` / `TX-Tn` | Tahap pembayaran / pajak | `07` §A4, §B4 |
| `AG-Tn` | Tahap asisten keuangan | `08` §8 |
| `PY-Tn` | Tahap penggajian | `09` §4 |
| `K-nn` | Keputusan pemilik | `10` |

## Yang sudah dan belum dilakukan untuk menyusun rencana ini

| Sudah | Belum |
|---|---|
| Membaca kode keuangan, penjualan, HR, dan asisten di `9834947`; tiap klaim kunci dicek pada berkas:baris | Menjalankan aplikasi; uji pakai layar oleh pengguna |
| Menjalankan kode layanan di database tiruan untuk 10 temuan audit dan hitungan laporan inti (`../bukti-2026-11-13/`) | Menjalankan 48 temuan tambahan — semuanya baru dibaca |
| Membaca kode asisten di DAHOST (`3bc1520`) | Memeriksa data nyata (PK-03) |
| Riset pembanding dari dokumentasi dan kode sumber terbuka (Odoo, ERPNext, Dynamics 365) | Mencocokkan butir pajak dengan teks peraturan; memeriksa biaya dan syarat bank/penyedia pembayaran |
| Memeriksa bahwa 139 + 48 temuan masing-masing dipegang tepat satu paket atau tahap, dan semua rujukan `K-`, `PK-` ada | Menaksir waktu pengerjaan — tidak ditaksir karena belum ada ukuran kecepatan pelaksana di repo ini |

## Aturan memakai dokumen ini

- Rancangan `05`–`09` berstatus usulan sampai keputusan terkaitnya dijawab di `10`.
- Setiap temuan dicek ulang di `HEAD` sebelum diperbaiki; baris kode di dokumen ini bisa sudah bergeser.
- Bila pelaksanaan mengubah pola (mis. reviewer meminta bentuk lain untuk kontrak posting), perbarui `04` lebih dulu,
  baru lanjutkan paket berikutnya.
- Dokumen ini bukan paket review. Pendaftaran temuan ke `docs/reviews/TRACKER.md` adalah langkah PK-01.
