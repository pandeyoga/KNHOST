# Aturan untuk modul baru — supaya modul tambahan tidak menjadi masalah baru

Berlaku untuk setiap modul atau fitur yang **menyentuh uang, stok bernilai, atau data lintas PT**: modul di rancangan
`05`–`09`, dan modul apa pun sesudahnya.

Asal aturan: 139 temuan audit keuangan berakar pada tiga hal — tulisan lintas dokumen yang putus di tengah, logika
akuntansi yang disalin lalu menyimpang, dan batas entitas atau wewenang yang longgar. Hampir semuanya lahir saat modul
ditambahkan dengan cara "menyalin modul sebelah". Aturan di bawah menutup jalan itu.

Aturan baru berguna hanya bila bisa **gagal secara otomatis**. Karena itu tiap aturan punya penjaga (§4); aturan tanpa
penjaga diperlakukan sebagai daftar periksa manusia (§5).

## 1. Kontrak posting

Setiap aksi yang berakibat jurnal mengikuti urutan ini. Tidak ada pengecualian "karena sederhana".

```text
1. PERIKSA     izin · entitas · status dokumen · periode terbuka untuk SEMUA entitas dan tanggal yang terlibat
               · akun aktif · sisa/saldo cukup
               → gagal di sini = tidak ada tulisan apa pun
2. NIAT        simpan dokumen/niat berstatus `pending` dengan id tetap (dari kunci idempotensi atau dari dokumen induk)
3. EFEK        ubah buku pembantu (piutang, hutang, kas, stok) dengan operasi bersyarat nilai lama;
               id turunan (kas, alokasi) diturunkan dari id niat, bukan dibuat baru
4. JURNAL      lewat satu pintu tahan-gagal; hasilnya ditulis ke `gl_status` dokumen: posted | failed
5. SELESAI     niat → `done`
ULANG          panggilan ulang dengan id yang sama meneruskan dari langkah terakhir yang tercatat
```

Aturan turunannya:

| # | Aturan | Menutup kelas temuan |
|---|---|---|
| P1 | Jurnal hanya dibuat lewat `gl_service` dan satu pintu tahan-gagal. Tidak ada sisipan langsung ke `journal_entries` | GL-02, GL-03 |
| P2 | Periode diperiksa dengan `preflight_posting` di langkah 1, untuk tanggal **dokumen** (bukan hari ini) dan untuk tiap entitas | SL-01, IC-01, FY-01 |
| P3 | Setiap jenis dokumen yang menjurnal punya `gl_status` dan terdaftar di panel Posting Gagal dengan jalur ulang | GL-02, IV-04, FX-13 |
| P4 | `source_type` + `source_id` jurnal unik **per kejadian**, bukan per dokumen, bila dokumen bisa dibayar/diubah lebih dari sekali | FX-02, SL-03 |
| P5 | Kas hanya dibuat lewat satu pembuat; rekening wajib; entitas dari dokumen | SL-11, SL-07, FX-04 |
| P6 | Dua jurnal di dua PT hanya lewat pembantu jurnal kembar | IC-01, FY-04, FX-11 |
| P7 | Pembalikan lewat satu mekanisme yang menandai jurnal asal | GL-01 |
| P8 | Jurnal periodik bertanggal akhir periodenya | FY-02 |
| P9 | Akun diambil dari pemetaan akun per entitas, tidak ditulis mati | IV-05, FY-13, RP-06 |
| P10 | Modul baru tidak menjurnal ke akun kontrol (piutang, hutang, persediaan, antar-PT) kecuali ia pemilik buku pembantunya | IC-06 |

## 2. Entitas, izin, dan idempotensi

| # | Aturan | Menutup |
|---|---|---|
| E1 | Entitas tidak pernah diambil dari isi permintaan. Pakai `resolve_requested_entity()`; untuk dokumen ber-id, entitas = entitas dokumen, lalu diadu dengan cakupan pengguna | IC-05, FX-08 |
| E2 | Setiap id yang dikirim klien (pelanggan, pesanan, rekening, karyawan) dibuktikan milik entitas dan dokumen induk yang sama | FX-05, FX-08 |
| E3 | Mode "Semua Entitas" hanya untuk membaca. Bila angkanya dijumlah lintas PT, layar menulis apakah sudah dieliminasi | RC-01 |
| E4 | Setiap endpoint punya `require_permission`. Menu yang tampil = izin yang dimiliki; tidak ada "menu tanpa izin" maupun "izin tanpa menu" | IA-02, IA-03, IA-06 |
| E5 | Pembuat ≠ penyetuju untuk setiap aksi yang mengeluarkan uang atau mengurangi piutang; batasnya dari satu tabel wewenang | FX-10, FY-09 |
| E6 | Setiap POST/PATCH yang berakibat uang ada di daftar awalan idempotensi server, dan layarnya mengirim kunci serta menahan klik ganda | UX-01, UX-02 |
| E7 | Aksi uang di layar meminta konfirmasi yang menyebut nominal dan PT; pembatalan meminta alasan | UX-03, FY-17 |
| E8 | Nilai yang membatasi (plafon, ambang, tarif, hari) berasal dari Pusat Pengaturan berlapis (global → PT → dokumen/pelanggan), tidak ditulis mati; setiap ubah tercatat siapa dan kapan | CR-03 |

## 3. Data dan angka

| # | Aturan | Menutup |
|---|---|---|
| D1 | Satu angka punya **satu pemilik**. Sebelum menambah field atau koleksi, cari dulu di peta sumber-kebenaran (laporan audit §2.2) dan `ENTITY_REGISTRY.md`. Bila sudah ada pemiliknya, baca dari sana | Duplikasi §4 |
| D2 | Angka turunan (saldo, sisa, umur) dihitung dari pemiliknya atau disimpan bersama **cara membangun ulangnya** dan satu invarian di `scripts/verify_data_integrity.py` | RP-01, RP-03 |
| D3 | Keputusan manusia atas angka (insentif, bebas denda, lepas blokir) disimpan sebagai dokumen dengan **potret angka dasar** saat diputuskan. Potret tidak dihitung ulang | KM-05 |
| D4 | Daftar tidak dipotong diam-diam. `to_list(n)` hanya dengan halaman atau saringan di kueri, dan layar menulis jumlah total | RP-01, GL-13 |
| D5 | Uang dibulatkan di satu fungsi; perbandingan dalam satuan bulat; total = Σ baris (sisa pembulatan diletakkan di satu baris yang ditentukan) | GL-07, IV-11 |
| D6 | Tanggal buku dan batas periode memakai WIB dari satu fungsi | GL-05 |
| D7 | Keunikan dijamin indeks unik yang terdaftar sebagai wajib-ada; cek-lalu-sisip saja tidak cukup | GL-09, SL-13 |
| D8 | Satu istilah untuk satu dokumen dan satu kosakata untuk satu pilihan (mis. metode bayar) di semua layar dan API | IA-14, PM-03 |
| D9 | Tidak ada jalur kedua untuk hal yang sama. Jalur lama dimatikan di paket yang sama dengan lahirnya jalur baru, atau diberi tanggal mati | SL-05, IC-09 |

## 4. Penjaga otomatis

Yang sudah ada dan wajib tetap hijau: `scripts/verify_data_integrity.py` (229 invarian), `scripts/verify_contract.py`,
dan penjaga di `scripts/guardrails/` — khususnya `verify_atomic_claim.py`, `verify_cross_entity.py`,
`verify_auth_coverage.py`, `verify_access_catalog_nav.py`, `verify_page_tabs.py`, `verify_codebase_map.py`,
`verify_no_secrets.py`.

Penjaga yang perlu **ditambahkan** (masing-masing dibuat oleh paket yang disebut, mengikuti pola `_common.py` dan
`_ratchet.py` yang sudah ada: mulai dari garis dasar, hanya boleh turun):

| Penjaga baru | Gagal bila | Aturan | Dibuat di |
|---|---|---|---|
| `verify_posting_coverage.py` | Ada pemanggil fungsi posting yang dokumennya tanpa `gl_status`, atau jenisnya tidak terdaftar di panel Posting Gagal | P1, P3 | PK-18 |
| `verify_cash_single_door.py` | Ada sisipan ke `cash_transactions` di luar pembuat kas, atau pemanggil `post_cash_transaction` langsung | P5 | PK-20 |
| `verify_entity_from_payload.py` | Router membaca `entity_id` dari isi permintaan tanpa `resolve_requested_entity` | E1 | PK-09 |
| `verify_idempotent_money_routes.py` | Endpoint tulis di modul uang yang awalannya tidak ada di `IDEMPOTENT_PREFIXES` | E6 | PK-12 |
| `verify_required_indexes.py` | Indeks unik wajib tidak didefinisikan untuk koleksi di daftar | D7 | PK-14 |
| `verify_hardcoded_accounts.py` | Kode akun (pola `d-dddd`) ditulis mati di luar pemetaan dan seed | P9 | PK-29 |
| `verify_unbounded_lists.py` | `to_list(N)` dengan N tetap di layanan laporan tanpa penanda halaman | D4 | PK-41 |
| `verify_payment_vocab.py` | Kosakata metode bayar di layar atau API di luar daftar induk | D8 | Modul pembayaran (`07`) |
| Invarian per buku pembantu baru | Σ buku pembantu ≠ saldo akun kontrolnya per PT | D2 | Tiap modul baru |

Penjaga dijalankan oleh `scripts/gate.sh`. Sebuah penjaga yang merah tidak boleh "dimatikan sementara"; yang boleh
hanya menaikkan garis dasarnya dengan alasan tertulis yang disetujui reviewer.

## 5. Daftar periksa "selesai" untuk modul baru

Modul dinyatakan siap direview bila semua butir terjawab "ya" atau "tidak berlaku, karena …" di laporannya.

**Rancangan**
- [ ] Ada dokumen rancangan yang menyebut: pemilik tiap angka, status dan transisinya, jurnal per transisi (akun dari
      pemetaan), siapa boleh tiap aksi, dan keputusan pemilik yang dirujuk.
- [ ] Tidak ada angka baru yang sudah punya pemilik di tempat lain (D1).
- [ ] Jalur lama yang digantikan disebut beserta cara dan waktu mematikannya (D9).

**Server**
- [ ] Setiap aksi uang mengikuti kontrak posting §1, dengan tes "gagal di tiap langkah → diulang → hasil tunggal".
- [ ] `resolve_requested_entity`, `require_permission`, awalan idempotensi terpasang (E1, E4, E6).
- [ ] Indeks unik terdaftar wajib-ada (D7); koleksi baru tercatat di `ENTITY_REGISTRY.md` dan `verify_contract.py`.
- [ ] Jenis dokumen terdaftar di: panel Posting Gagal, Jejak Dokumen (`doc_refs_service`), Pusat Export, log audit.
- [ ] Invarian buku pembantu ↔ buku besar ditambahkan ke `verify_data_integrity.py`.
- [ ] Nilai pembatas ada di katalog konfigurasi berlapis, bukan konstanta (E8).

**Layar**
- [ ] Masuk ke hub yang sudah ada sebagai tab; menu baru di sidebar hanya bila tidak ada hub yang cocok
      ([`01_PENGGABUNGAN_MENU.md`](01_PENGGABUNGAN_MENU.md) §5).
- [ ] Banner entitas; tombol buat mati di mode "Semua Entitas"; konfirmasi bernominal; kunci idempotensi; status
      memuat/galat/kosong dibedakan; daftar berhalaman.
- [ ] Dari dokumen bisa membuka jurnalnya dan sebaliknya.
- [ ] Istilah mengikuti glosarium; tidak ada istilah Inggris baru di label.

**Bukti**
- [ ] Tes layanan, HTTP, dan (bila ada butir bersamaan/indeks) MongoDB asli.
- [ ] Gate dan penjaga tidak lebih merah dari garis dasar.
- [ ] `CODEBASE_MAP.md`, `ENTITY_REGISTRY.md`, `memory/PRD.md`, dan dokumen navigasi diperbarui di commit yang sama.

## 6. Urutan membangun modul

1. Rancangan disetujui pemilik (keputusan tercatat di `10`).
2. Prasyarat fondasinya sudah divalidasi (tabel di akhir `02`).
3. Bangun **baca dulu** (daftar, rekap, laporan) → pakai untuk mencocokkan angka dengan cara manual yang sekarang
   berjalan, minimal satu periode.
4. Baru **tulis** (dokumen, persetujuan, jurnal), di belakang sakelar konfigurasi per PT yang bawaannya mati.
5. Nyalakan untuk satu PT; jalur lama tetap ada sampai satu tutup buku lewat tanpa selisih; lalu matikan jalur lama.

Langkah 3 adalah pengaman utama. Modul yang angkanya belum pernah dicocokkan dengan kenyataan tidak boleh menulis
jurnal.

## 7. Yang tidak boleh dilakukan modul baru

- Menyalin fungsi dari modul sebelah lalu mengubah sedikit. Bila butuh perilaku yang mirip, perluas fungsi aslinya.
- Menambah dasbor atau antrean baru. Tambahkan kartu ke beranda keuangan dan butir ke antrean yang ada.
- Menyimpan salinan nama, harga, atau saldo dari dokumen lain tanpa menandainya sebagai potret bertanggal.
- Menelan galat (`except: pass`, atau `return 0` saat gagal) di jalur uang. Contoh nyata: `_commission_for` mengembalikan
  0 saat mesin komisi galat (`backend/services/hr_payroll_service.py:256`), sehingga slip terbit tanpa komisi dan tanpa
  peringatan.
- Membaca koleksi modul lain langsung untuk mengambil keputusan uang; panggil layanannya.
