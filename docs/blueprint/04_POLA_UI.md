# 04 — Pola UI (tata letak & cara kerja layar)

Status: **USULAN — menunggu validasi pemilik** lewat tiga layar contoh (Meja, Retur Pelanggan, Pengaturan › Ketegasan,
Pengingat & Dokumen). Sesudah disetujui, pola ini mengikat semua layar baru dan layar yang disentuh, dan menjadi ukuran
audit seluruh layar (langkah 2). Hasil pilot + foto sebelum/sesudah: `masukan-pemilik/2026-11-16_PILOT_POLA.md`.

Asal: masukan pemilik 16 Nov (M1–M43, `masukan-pemilik/`), analisis pola P1–P10, dan permintaan pemilik:
> "yang saya butuhkan adalah konsistensi, tata letak yang benar … buat sesuatu data inputnya lebih baik dekat dengan list
> tabel, jika bisa dropdown kenapa tidak dropdown saja … pemborosan ruang, cards/list data jadi lebar … bukan berarti
> saya ingin rombak total, tapi konsistensi yang baik, cards yang bagus konsisten, tidak terlalu variatif, mekanisme kerja
> harus mirip-mirip."

## 1. Prinsip
1. **Satu bentuk, satu cara kerja.** Semua daftar dicari, disaring, diurut, dibuka, dan ditindak dengan cara yang sama.
   Komponen bersama dipakai; layar tidak membuat versinya sendiri.
2. **Dropdown untuk memilih.** Saringan status, lini, jenis, gudang, PT, periode = dropdown. Tidak ada deret chip, tombol,
   atau tab untuk nilai saringan. Tab hanya untuk berpindah **layar** (tab hub), bukan menyaring isi.
3. **Isian dekat daftarnya.** Tombol "Buat/Tambah" ada di bilah daftar (ujung kanan bilah saring), bukan di kepala
   halaman yang jauh. Data master sederhana ditambah sebagai baris di tabel; dokumen dibuat di panel/jendela yang dibuka
   dari bilah itu.
4. **Hemat ruang.** Kepala halaman satu baris. Tidak ada bilah penjelasan panjang di layar kerja — penjelasan ada di ikon
   **?** (judul halaman, label pengaturan) atau di dalam bagian yang dibuka. Kolom tabel mengisi lebar; baris tidak
   menyisakan ruang kosong di tengah.
5. **Kartu angka harus berguna.** Hanya angka yang relevan untuk peran itu, dan **selalu bisa diklik** (menyaring daftar di
   bawahnya atau membuka daftar tersaring). Angka yang tidak bisa ditindak tidak dipajang.
6. **Tidak ada lapisan yang menimpa isi.** Rincian = halaman/panel tetap; pesan hasil tampil di lapisan yang sedang aktif;
   tombol yang tidak bisa dipakai nonaktif dengan alasan tertulis.
7. **PT dan lokasi dipilih sekali** di bilah atas; semua pilihan turunan (gudang, lingkup, stok) mengikuti.

## 2. Templat halaman

### A. Daftar (contoh: Retur Pelanggan)
```
[Tab hub (bila ada)]
Judul halaman (?)                                                     ← satu baris, tanpa paragraf
[Kartu angka ringkas — tiap kartu = saringan cepat, aktif bila dipilih]   (opsional, maks. 4)
[Cari……] [Lini ▾] [Status ▾] [Tipe ▾]  n hasil          [Unduh ▾] [+ Buat …]   ← BILAH DAFTAR (satu baris)
┌ tabel ─────────────────────────────────────────────────────────────────┐
│ kolom mengisi lebar · status = StatusBadge · aksi baris di kolom kanan  │
└──────────────────────────────────────────────────────────────── paging ┘
```
- Komponen: `PageHeader` (judul + ?), `MetricRow` (kartu bisa diklik), `ListToolbar` (cari + dropdown + jumlah + aksi),
  `LineFilter` (dropdown), `KNSelect`, `PaginationBar`.

### B. Meja (contoh: Meja Admin Sales, Meja MD, Meja Gudang, Meja Saya, Meja Finance)
```
[Kartu antrean]  [Kartu antrean]        ← dua kolom sama tinggi; kartu besar boleh satu baris penuh
┌ Ikon Judul (jumlah) (tertua n hari)                        Nilai total ┐
│ [Cari……] [Status ▾] [Urut ▾]                                           │
│ Dokumen · judul   | Keterangan · masuk/menunggu | Nilai | [Aksi]       │ ← baris berkolom
│ …5 baris                                                               │
└──────────────────────────────────────────────────────────────── paging ┘
```
- Kartu **selalu terbuka** (tidak ada buka/tutup); kartu kosong tetap tampil dengan teks "bersih".
- Tiap kartu: cari + saring status (dropdown) + urut (dropdown) + paginasi 5 baris.
- Komponen: `DeskQueueCard` + `TableFilterBar` (dipakai semua meja).

### C. Rincian
- Satu tombol kembali: "← Kembali ke {layar asal}" bila datang dari layar lain, + tautan kecil "Daftar …"
  (`DetailBack`, sudah berlaku). Kepala: nomor · status · aksi. Isi: panel-panel; alur/status memakai lini masa vertikal
  (pola menyusul, M14/M15).

### D. Pengaturan (contoh: Ketegasan, Pengingat & Dokumen)
```
[Cari pengaturan……] [Berlaku untuk: PT ▾]
Sub-judul bagian
┌──────────────────────────────────────────────────────────────────────────┐
│ ▸ Nama pengaturan (?)                     nilai berlaku   Asal  [Ubah]  │ ← satu baris per pengaturan
│ ▾ Nama pengaturan (?)                     nilai berlaku   Asal          │
│    [isian]  [Simpan] [Ikuti nilai grup]   Kenapa nilainya begini · Riwayat│ ← dibuka di tempat
│    (alasan perubahan bila ada perubahan)                                 │
├──────────────────────────────────────────────────────────────────────────┤
```
- Daftar padat dalam satu kartu bergaris pemisah (bukan satu kartu besar per pengaturan).
- Penjelasan (Artinya · Kalau diubah · Contoh · Bisa dibedakan · Detail teknis) **tetap ada di registri** dan dibuka
  lewat **?** — tidak dipajang terbuka.
- Komponen: `SettingCard` (mode daftar), `SettingsBrowser`.

## 3. Ukuran baku
| Hal | Baku |
|---|---|
| Huruf isi | 12–13 px; label kolom 11 px huruf besar; minimum 12 px untuk teks yang dibaca |
| Tinggi baris daftar | 40–48 px (satu baris teks + satu baris keterangan bila perlu) |
| Jarak antar blok | 12 px; dalam kartu 8 px |
| Bilah daftar | satu baris di ≥ 1024 px; di HP boleh turun baris, urutan tetap: cari → saringan → aksi |
| Warna | token `kn-*` saja; status lewat `StatusBadge` |

## 4. Yang dilarang (diperiksa saat audit, langkah 2)
- Deret chip/tombol/tab untuk menyaring (`FilterChips`, `StatusTabs` sebagai saringan, chip buatan).
- Bilah penjelasan (`notice-bar` info) permanen di layar kerja; panduan awal.
- Kartu antrean/pengaturan yang bisa dibuka-tutup sebagai cara utama melihat isi.
- Kartu angka tanpa aksi klik.
- Popup melayang yang menutupi daftar; pesan hasil di lapisan yang tertutup.
- Tombol buat/tambah di lebih dari satu tempat pada satu layar.
- Alat admin/teknis (pratinjau data lama, susun ulang relasi, kandidat duplikat) di layar kerja — pindah ke Pengaturan.
