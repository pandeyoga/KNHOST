# Pilot pola UI — tiga layar contoh untuk validasi pemilik (16 Nov 2026)

Asal: permintaan pemilik "yang saya butuhkan adalah konsistensi, tata letak yang benar …" → usulan empat langkah
(standar + layar contoh → audit semua layar → blueprint per gelombang → eksekusi berpenjaga), pemilik: "ya mulai".
Ini **langkah 1**: standar `docs/blueprint/04_POLA_UI.md` diterapkan di tiga layar contoh. Pola baru dikunci sesudah
pemilik melihat hasilnya dan mengoreksi.

Foto sebelum/sesudah: `2026-11-16_pilot-pola/` (`sebelum_*.png`, `sesudah_*.png`, lebar 1366 dan 1024, data acuan,
akun Admin). Foto diperkecil agar repo ringan.

## 1. Apa yang berubah

### Contoh 1 — Meja (Meja Admin Sales, Meja MD; berlaku untuk semua meja)
Satu komponen (`DeskQueueCard`) dipakai semua meja, jadi perubahan ini langsung berlaku di Meja Admin Sales, MD, Gudang,
Sample, Finance, dan Meja Saya.
- Kartu antrean **selalu terbuka** — tidak ada lagi buka/tutup (M1).
- Kartu kiri-kanan **sama tinggi**; Keep & Pending di Meja Admin Sales sekarang **satu baris penuh** (M4).
- Tiap kartu punya bilah sendiri: **cari + Status ▾ + Urut ▾** (dropdown, bukan chip) + paginasi 5 baris (M1).
- Baris berkolom: nomor · judul | status + keterangan, "menunggu n hari · masuk tgl" | nilai | aksi. Kolom tengah tidak
  lagi kosong; status tidak terpotong.
- Meja Finance: kelompok kartu dua kolom di layar lebar.

| Layar (1366 px) | Tinggi halaman sebelum | Sesudah |
|---|---|---|
| Meja Admin Sales | 3.176 px | 3.146 px (semua kartu kini terbuka, tetap tidak lebih panjang) |
| Meja MD | 2.192 px | 1.804 px |

Catatan 1024 px: Meja Admin Sales lebih panjang (4.000 → 4.441 px) karena semua kartu kini terbuka dan Keep & Pending
memakai satu baris penuh — dulu sebagian isi tersembunyi di kartu tertutup.

### Contoh 2 — Retur Pelanggan (templat A: Daftar)
- Kepala **satu baris**: judul + ikon **?** (penjelasan pindah ke ikon). Bilah peta dan label lingkup dihapus.
- Kartu angka **bisa diklik** = saringan cepat: Total → semua, Menunggu Persetujuan, Diproses (disetujui/diperiksa),
  Selesai (refund/kredit/nego/selesai). Kartu yang aktif bertanda.
- **Satu bilah daftar**: Cari · Lini ▾ · Status ▾ · Tipe ▾ · jumlah hasil · **[+ Buat Retur]** di ujung kanan bilah —
  tombol buat dekat dengan tabelnya (prinsip 3). Saringan lini dulu deret chip, sekarang dropdown (berlaku di semua
  layar yang memakai `LineFilter`).
- Tabel naik ±240 px (lebih banyak baris terlihat tanpa gulir).
- Server: saringan status menerima beberapa nilai sekaligus (`status=approved,inspecting,inspected`) untuk kartu
  "Diproses"/"Selesai"; unduhan mengikuti saringan yang sama.

### Contoh 3 — Pengaturan › Ketegasan, Pengingat & Dokumen (templat D)
Berlaku untuk **semua** kelompok di Pusat Pengaturan karena komponennya bersama (`SettingCard`, `SettingsBrowser`).
- **Daftar padat**: satu kartu bergaris pemisah, satu baris per pengaturan (nama **?** · nilai berlaku · asal · Ubah),
  bukan satu kartu besar per pengaturan (M43).
- Penjelasan (Artinya · Kalau diubah · Contoh · Bisa dibedakan · kunci teknis) **tetap tersimpan di registri** dan
  tampil lewat ikon **?** atau tombol "Penjelasan" di baris yang dibuka — tidak dipajang terbuka.
- Bilah atas satu baris: Cari · Berlaku untuk ▾ · **Tampilkan ▾** (dulu deret chip). Kepala kelompok satu baris
  (nama + ? + jumlah + Riwayat perubahan). Paragraf pengantar kelompok dihapus.
- Lencana sambungan hanya muncul bila ada masalah (bukan "OK" di setiap baris).

| Layar (1366 px) | Tinggi halaman sebelum | Sesudah |
|---|---|---|
| Ketegasan, Pengingat & Dokumen | 4.691 px | 2.412 px (−49%) |
| … dengan satu pengaturan dibuka | 5.018 px | 2.566 px |

### Komponen bersama yang ditambah/diubah
| Komponen | Isi |
|---|---|
| `ListPageParts.PageHeader` | satu baris; `subtitle`/`help` pindah ke `HelpTip` (ikon ?) |
| `ListPageParts.HelpTip` (baru) | ikon ? dengan catatan kecil; tutup dengan klik luar / Esc |
| `ListPageParts.ListToolbar` (baru) | bilah daftar: saringan kiri, jumlah, aksi kanan |
| `ListPageParts.MetricRow` | kartu angka menerima `onClick`/`active` (tombol, `aria-pressed`) |
| `LineFilter` | chip → dropdown `KNSelect` (semua pemakai ikut) |
| `TableFilter.TableFilterBar` | cari + Status ▾ + Urut ▾ (dipakai kartu meja) |

## 2. Uji
- **Jest (frontend) suite penuh** pada pohon akhir: 183 suite dimuat, 178 lulus; **9 uji di 5 suite gagal, dan
  kesembilannya juga gagal di `HEAD` tanpa perubahan pilot** (dibuktikan dengan menukar berkas pilot ke versi `HEAD`
  lalu menjalankan 5 suite itu: 9 gagal yang sama). Kelima suite ini sebelumnya **tidak bisa dimuat sama sekali**
  (galat modul `@radix-ui/primitive/is-development`), jadi kegagalannya tersembunyi; pilot menambah pemetaan modul
  `frontend/jest/radixIsDevelopment.js` di `craco.config.js` sehingga kini terlihat. Daftar (bukan akibat pilot, perlu
  diperbarui tersendiri):
  - `phase3P3` — D-05 form pelanggan baru di POS; D-07 setujui/tolak Pesanan Khusus (2 uji).
  - `phase3P8Activation` — D-01 Desainer PDF untuk peran kustom modul Admin.
  - `roleGateSweep2` — kasbon: Manager berizin approve tanpa tombol Setujui.
  - `fe07ReturnErrors` — pesan galat tolak retur (izin "Retur Penjualan").
  - `phase4R1` — Kwitansi (judul "Terima pembayaran" vs "Catat Pembayaran"; 3 uji).
- Uji yang diperbarui karena pola: `trial22Okt` E7 (saring status lewat dropdown), `kft4SettingCard` U14 (contoh
  tersembunyi sampai "Penjelasan" dibuka; ikon ? ada).
- **Penjaga UI** `verify_ui_standard.py`: daftar pelanggaran **sama persis** dengan `HEAD` (100 butir lama, 0 baru).
- **Server**: `GET /api/sales-returns?status=…` di data acuan — kosong → 1, `pending_approval` → 1,
  `approved,inspecting,inspected` → 0, `pending_approval,approved` → 1 (gabungan status bekerja).
- Gate `--ci` belum dijalankan: pilot menunggu validasi; gate dijalankan sekali per gelombang (uji hemat, 15 Nov).

## 3. Yang tidak tercakup
- Tampilan **HP (390 px)**: akun Admin di HP masuk ke cangkang HP (Persetujuan · Ringkas · Pintasan), bukan layar
  desktop ini, sehingga foto HP tidak menunjukkan layar contoh. Pola HP dibahas di audit langkah 2.
- Lini masa vertikal (templat C, M14/M15) belum dibuat — menyusul di gelombang Pesanan.

## 4. Yang perlu pemilik nilai (validasi pola)
1. **Meja**: kartu selalu terbuka + bilah cari/status/urut per kartu + baris berkolom — sudah sesuai? Perlu kolom lain?
2. **Retur**: kartu angka sebagai saringan cepat + satu bilah daftar dengan tombol Buat di kanan — jadikan templat semua
   daftar?
3. **Pengaturan**: daftar padat satu baris per pengaturan, penjelasan di ikon ? — jadikan bentuk semua menu Pengaturan?
4. Ada yang terlalu padat / terlalu kecil?

Sesudah disetujui: `04_POLA_UI.md` berstatus **berlaku**, lalu langkah 2 (audit otomatis semua layar terhadap pola) dan
blueprint per gelombang.
