# <ID> — <judul singkat, kata kerja + hasil>

| | |
|---|---|
| Gelombang | <0–7 atau nama modul> |
| Jenis | perbaikan · fitur · infrastruktur · dokumen |
| Risiko | rendah · sedang · tinggi (tinggi = dua serah-terima, lihat `00` §8) |
| Prasyarat | <ID unit yang harus `selesai`, atau —> |
| Menutup temuan | <ID temuan, atau —> |
| Keputusan | <K-nn dari `01_KEPUTUSAN.md`, atau —> |
| Standar | <§ di `02_STANDAR.md` yang berlaku> |
| Lingkungan uji | B (database tiruan) · A (MongoDB asli) · keduanya |

## Tujuan

Satu sampai tiga kalimat: apa yang berbeda bagi pengguna atau bagi pembukuan setelah unit ini selesai.

## Keadaan sekarang

Fakta yang bisa dicek, masing-masing dengan jangkar kode berbentuk `` `path/berkas.py:baris` (`nama_simbol`) ``.
Tulis hanya yang dibutuhkan untuk mengerjakan unit. Tandai `[dijalankan]` bila perilakunya dibuktikan dengan uji jalan,
`[dibaca]` bila hanya dari membaca kode.

## Perubahan

Hanya sub-bagian yang relevan. Yang tidak ada ditulis "Tidak ada".

### Data
Koleksi, field (nama · tipe · wajib · arti), indeks (kunci · unik · parsial), migrasi data lama.

### Server
Per endpoint atau fungsi: metode + path · izin (`sumber_daya.aksi`) · isi permintaan · isi jawaban · galat (kode +
teks pesan berbahasa Indonesia) · urutan langkah bila aksi posting (`02` §1).

### Pengaturan
Per kunci baru, lengkap menurut `02` §2.1: key · group · type · default · min/max/unit · scopes · label · help ·
impact · example · risk · permission · consumers.

### Izin dan peran
Pasangan izin baru · peran bawaan yang mendapatkannya · modul akses · id menu (`02` §3.2).

### Layar
Tempat (hub › tab) · komponen yang diubah/dibuat · isi (kolom, isian, tombol) dengan **teks label yang persis** ·
keadaan memuat/galat/kosong · konfirmasi.

## Uji penerimaan

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B / A / layar | data yang harus ada | apa yang dilakukan | angka atau kode yang pasti |

Angka harapan disertai hitungan. Tiap baris menjadi satu tes otomatis kecuali berlapis "layar (uji jalan)".

## Langkah kerja

Urutan yang disarankan, tiap langkah berakhir hijau. Untuk risiko tinggi: tandai batas serah-terima (a) dan (b).

## Dokumen ikut berubah

Daftar dari `02` §7 yang tersentuh.

## Di luar lingkup

Hal berdekatan yang **tidak** dikerjakan di unit ini, beserta unit yang mengerjakannya.

## Asumsi dan risiko

`ASUMSI:` hal yang dianggap benar tanpa bukti kode, satu per baris. `RISIKO:` apa yang bisa rusak dan cara membatalkan.
