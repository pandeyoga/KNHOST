# 04 — Pola UI (tata letak & cara kerja layar)

Status: **USULAN — menunggu validasi pemilik** lewat tiga layar contoh (Meja, Retur Pelanggan, Pengaturan › Ketegasan,
Pengingat & Dokumen). Sesudah disetujui, pola ini mengikat semua layar baru dan layar yang disentuh, dan menjadi ukuran
audit seluruh layar (langkah 2). Hasil pilot + foto sebelum/sesudah: `masukan-pemilik/2026-11-16_PILOT_POLA.md`.
Diubah 25 Nov (§1 butir 6, §2.B, §3, §4): keputusan pemilik 25 Nov, rancangan
`docs/superpowers/specs/2026-11-25-meja-kerja-di-tempat-design.md`.
Diubah 25 Nov gelombang 2 (§1 butir 8, §2.B, §2.C, §4): pratinjau dokumen dari nomor — keputusan pemilik 25 Nov (gelombang 2).

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
6. **Rincian dari daftar meja = pop-up `DetailModal`** (klik baris); pesan hasil aksi tampil di pop-up aksi atau toast,
   tidak di puncak halaman; tombol yang tidak bisa dipakai nonaktif dengan alasan tertulis. Pop-up hanya lewat komponen
   bersama (`DetailModal`, `FormModal`, `DetailPopup`, `askConfirm`) — tidak ada pop-up buatan sendiri. Rincian di luar
   meja tetap halaman/panel tetap. (Asal: keputusan pemilik 25 Nov.)
7. **PT dan lokasi dipilih sekali** di bilah atas; semua pilihan turunan (gudang, lingkup, stok) mengikuti.
8. **Nomor dokumen di daftar = pratinjau.** Nomor dokumen di daftar (Keuangan, Pembelian, meja) adalah `DocLink`:
   klik membuka pop-up pratinjau dengan baris barangnya (`features/documents/preview/`). Tautan **Jejak** tetap
   kontrol sendiri, tidak digantikan. Tanpa izin baca atau tanpa id, nomor tampil teks biasa — bukan tautan mati
   dan bukan teks biasa berwarna biru tautan. (Asal: keputusan pemilik 25 Nov, gelombang 2.)

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

### B. Meja (contoh: Meja Admin Sales, Meja Keuangan, Meja Gudang, Meja Sample, Meja MD, Meja Saya)
Asal: keputusan pemilik 25 Nov, rancangan `docs/superpowers/specs/2026-11-25-meja-kerja-di-tempat-design.md`.
```
[Antrean | Pantau]
[Kartu antrean]  [Kartu antrean]        ← dua kolom, tinggi sama & tetap; kartu besar boleh satu baris penuh
┌ Ikon Judul (?) (jumlah) (tertua n hari)                    Nilai total ┐
│ [Cari……] [Status ▾] [Urut ▾]                                           │
│ Nomor · pihak        | lencana · umur | nilai · [satu aksi]            │ ← baris dua baris teks
│ …5 baris                                                               │
└──────────────────────────────────────────────────────────────── paging ┘
```
Catatan Meja Keuangan: hidup di dalam hub Beranda Keuangan, sehingga "Antrean | Pantau" di atas berupa tab hub
bersaudara ("Meja Keuangan" | "Pantau" | …), bukan tab internal.
- **Satu kepala:** `TopBar` (breadcrumb + judul, nama tunggal = menu); ikon **?** di samping judul memuat penjelasan alur
  dan "Bukan wewenang meja ini". Tidak ada kepala kedua di dalam layar, tidak ada kartu angka.
- **Tab Antrean | Pantau.** Antrean (bawaan) = pekerjaan utama meja. Pantau = Pelacak SO, Keep & Pending, Aturan Grade,
  retur internal, antrean pantauan. Pantau bukan hanya-baca: baris membuka pop-up dan aksi tersedia bila pengguna berizin.
  Meja Keuangan hidup di dalam hub Beranda Keuangan, jadi Pantau-nya adalah tab hub bersaudara ("Meja Keuangan" | "Pantau"
  | …), bukan tab tingkat ketiga; meja lain memakai tab internal.
- **Kartu ukuran tetap**, setinggi kartu berisi 5 baris: `sm:h-[412px]` di ≥ 640 px (border 2 + kepala 44 + bilah saring 49
  + daftar 281 + kaki 36; baris meja = 56 px karena dua baris teks, jadi 1 + 5 × 56 = 281 — berbeda dari baris daftar biasa di §3). Sama untuk kartu berisi, kurang dari 5 baris, kosong ("bersih" di tengah), dan memuat
  (kerangka). Grid `items-start`: kartu tidak diregangkan tetangganya. Urutan kartu: berisi dari yang paling mendesak,
  lalu kosong.
- **Baris ringkas, dua baris teks:** nomor dokumen + nama pihak · satu lencana + umur · nilai + **satu** aksi. Keterangan
  lain ada di pop-up. Klik pada baris membuka `DeskRowDetail` (pop-up rincian); untuk papan ketik, nomor dokumen adalah
  `link-button` yang membukanya. Baris tidak diberi `role="button"`/`tabIndex` karena memuat tombol sungguhan.
- **Aksi besar** (terbit faktur pajak, setujui bayar sample, lepas/teruskan ke gudang, terbitkan denda — di meja: gelombang 2; kini lewat Rencana & Denda yang sudah ber-konfirmasi) selalu lewat
  pratinjau + konfirmasi di komponen bersama, juga di layar asalnya.
- Tiap kartu: cari + saring status (dropdown) + urut (dropdown) + paginasi 5 baris; status kartu tersimpan per sesi.
- **HP:** kartu boleh tetap bisa dibuka-tutup (tanpa tinggi tetap); baris bisa disentuh dan membuka pop-up yang sama
  layar penuh. Tombol aksi menuju layar dalam aplikasi di HP boleh langsung berpindah; tujuan khusus desktop membuka
  pop-up dulu.
- **Pop-up meja menyematkan pratinjau:** untuk antrean yang punya dokumen (`DESK_DOC_OF`, `panelFor` di `deskPanels.js`),
  `DeskDocPanel` menampilkan fakta baris (yang belum ada di judul/subjudul) + `Body` pratinjau di dalam pop-up meja
  yang **sama** — jangan membuka modal kedua. Aksi kecil dikerjakan di tempat (selisih bayar, terbitkan denda, tandai
  sudah diingatkan, tetapkan sales bila berizin `sales_force.assign`, tolak permintaan internal dengan alasan);
  aksi yang pindah layar diberi ikon ExternalLink.
- Komponen: `DeskFrame` + `DeskQueueCard` + `DeskRowDetail` + `DeskDocPanel` + `TableFilterBar` (dipakai semua meja). Berkas meja yang
  merender `DeskRowDetail` dikecualikan dari penjaga `verify_detail_modal.py` lewat entri `DIBOLEHKAN` beralasan —
  bukan dengan melemahkan logika penjaga.

### C. Rincian
Berlaku untuk rincian di luar meja; rincian dari baris meja = pop-up (§2.B).
- **Satu pop-up pratinjau.** Dokumen yang dibuka dari dalam pratinjau (nomor di dalam rincian) bertumpuk di pop-up yang
  sama dengan tombol "‹ Kembali" (`useDocStack`), bukan modal baru. Jenis pratinjau baru didaftarkan di
  `docPreviewRegistry.js` (label, izin, loader, `Body`); `Body` mengambil loader dari `docLoaders.js` dan tidak
  mengimpor registri.
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
| Huruf | 12–13 px; label kolom 12 px semi-tebal tanpa huruf besar; minimum 12 px untuk semua teks; token `text-fs-12\|13\|14\|16\|20` saja |
| Tinggi baris daftar | 40–48 px (satu baris teks + satu baris keterangan bila perlu); baris kartu meja = 56 px (§2.B) |
| Jarak antar blok | 12 px; dalam kartu 8 px |
| Bilah daftar | satu baris di ≥ 1024 px; di HP boleh turun baris, urutan tetap: cari → saringan → aksi |
| Warna | token `kn-*` saja; status lewat `StatusBadge` |

## 4. Yang dilarang (diperiksa saat audit, langkah 2)
- Deret chip/tombol/tab untuk menyaring (`FilterChips`, `StatusTabs` sebagai saringan, chip buatan).
- Bilah penjelasan (`notice-bar` info) permanen di layar kerja; panduan awal.
- Kartu antrean/pengaturan yang bisa dibuka-tutup sebagai cara utama melihat isi di desktop. Kartu meja boleh
  dibuka-tutup **hanya di HP**; di desktop tetap terbuka dengan ukuran tetap.
- Kartu angka tanpa aksi klik.
- Pop-up buatan sendiri (di luar `DetailModal`/`FormModal`/`DetailPopup`/`askConfirm`); pesan hasil di lapisan yang
  tertutup atau di puncak halaman meja. (Pop-up rincian meja lewat `DetailModal` diperbolehkan — §1 butir 6.)
- Nomor dokumen di daftar yang berupa teks mati, tautan mati, atau tautan yang langsung pindah layar tanpa pratinjau
  (kecuali jenis yang belum ada di registri pratinjau); modal kedua di atas pop-up meja atau pratinjau.
- Tombol buat/tambah di lebih dari satu tempat pada satu layar.
- Alat admin/teknis (pratinjau data lama, susun ulang relasi, kandidat duplikat) di layar kerja — pindah ke Pengaturan.
