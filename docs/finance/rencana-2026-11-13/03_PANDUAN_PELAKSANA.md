# Panduan agen pelaksana — menjalankan satu paket kerja

> **Digantikan** oleh `docs/blueprint/00_ATURAN_EKSEKUSI.md` (13 Nov 2026). Berkas ini disimpan sebagai riwayat;
> untuk eksekusi ikuti blueprint.

Dokumen ini dibaca oleh agen coding yang ditugasi satu paket dari
[`02_PAKET_KERJA_FONDASI.md`](02_PAKET_KERJA_FONDASI.md) atau satu tahap bangun dari rancangan modul (`05`–`09`).
Isinya melengkapi, tidak menggantikan, `AGENTS.md`, `docs/reviews/README.md`, dan `docs/KN_00_AGENT_QUICK_START.md`.

Tujuannya satu: perbaikan yang **terbukti**, bukan yang "tampak benar". Sebuah paket selesai bila tes yang ditulis lebih
dulu berubah dari merah ke hijau, gate tidak bertambah merah, dan laporannya memungkinkan reviewer mengulang
pembuktian itu tanpa bertanya.

## 1. Satu sesi = satu paket

- Kerjakan **satu** paket per sesi dan per cabang. Jangan menggabung dua paket walau berkasnya berdekatan.
- Jangan memulai paket yang baris "Setelah"-nya belum `implemented_pending_review`, atau yang baris "Keputusan"-nya
  bertanda "menahan" dan belum dijawab di [`10_KEPUTUSAN_PEMILIK.md`](10_KEPUTUSAN_PEMILIK.md).
- Bila di tengah jalan ternyata paket terlalu besar, berhenti di batas yang utuh (semua tes yang sudah ditulis hijau),
  laporkan bagian yang selesai, dan tulis sisanya sebagai usulan paket lanjutan. Jangan meninggalkan setengah pola.

## 2. Urutan kerja di dalam satu paket

| Langkah | Yang dikerjakan | Bukti di laporan |
|---|---|---|
| 1. Baca | Paket ini; baris temuan di laporan audit (kolom Bukti, Skenario, Rekomendasi); `04_ATURAN_MODUL_BARU.md` §1 | — |
| 2. Catat awal | `git status` bersih; SHA `HEAD`; cabang | SHA |
| 3. Cek ulang di `HEAD` | Buka tiap berkas:baris di kolom Bukti. Laporan audit dibaca di `cd6963a`…`9834947`; kode bisa sudah bergeser | "Berlaku di HEAD: ya / sebagian / tidak" per temuan, dengan berkas:baris terbaru |
| 4. Tes dulu | Tulis tes untuk tiap butir "Selesai bila". Jalankan: harus **merah** karena alasan yang sama dengan temuan | Keluaran merah |
| 5. Perbaiki | Ubah sesedikit mungkin. Ikuti kontrak posting (`04` §1) | Daftar berkas berubah |
| 6. Hijau | Tes paket hijau; cabut tanda "diharapkan gagal" milik temuan itu di `backend/tests/finance_regress/` | Keluaran hijau |
| 7. Gate | Gate di `KN_00`; `scripts/verify_data_integrity.py`; penjaga di `scripts/guardrails/` yang disebut paket | Keluaran apa adanya; bandingkan dengan garis dasar PK-01 |
| 8. Tulis | `docs/reviews/2026-11-13/hasil/PK-xx.md` memakai templat protokol; perbarui baris tracker | Tautan |
| 9. Serahkan | Commit, push ke cabang kerja. Status paling jauh `implemented_pending_review` | SHA akhir |

Langkah 4 tidak boleh dilewati. Tes yang ditulis setelah perbaikan hanya membuktikan bahwa kode melakukan apa yang
dilakukannya.

## 3. Cara menguji

**Tiga lapis, dipakai sesuai yang dibuktikan:**

| Lapis | Alat | Membuktikan | Tidak membuktikan |
|---|---|---|---|
| Layanan | `pytest` + `mongomock-motor` (pola `docs/finance/bukti-2026-11-13/boot.py`) | Urutan tulis, rumus, penjaga status, idempotensi cek-lalu-sisip | Indeks unik, balapan, izin di router |
| HTTP | Klien uji FastAPI atau `scripts/health_check.py` di container | Izin, penjaga entitas, kunci idempotensi, kode galat | Perilaku di bawah beban |
| MongoDB asli | Container dev (`docker-compose.dev.yml`) | Indeks unik parsial, dua permintaan bersamaan, transaksi (setelah PK-34) | — |

Aturan pemakaian:

- Butir "Selesai bila" yang menyebut "bersamaan", "indeks", atau "ditolak oleh database" **wajib** diuji di MongoDB
  asli. Hasil dari database tiruan tidak sah untuk butir itu.
- Butir yang menyebut 403/404/409/410 wajib diuji lewat HTTP.
- "Jurnal dipaksa gagal" dilakukan dengan menonaktifkan akun tujuan atau menutup periodenya di data uji, bukan dengan
  menyisipkan kode khusus uji ke aplikasi.
- Fixture yang disiapkan langsung ke database dicatat sebagai fixture. Bila alur bisnisnya (mis. buat pesanan → kirim →
  kwitansi) dijalankan lewat layanan, tulis begitu. Reviewer menilai keduanya berbeda.
- Layar: tes komponen untuk logika (tombol mati, kunci terkirim), dan satu uji jalan di peramban dengan tangkapan layar
  untuk butir bertanda "uji jalan".

**Angka harapan** selalu dari hitungan tangan yang ditulis di tes sebagai komentar (masukan → langkah → hasil), tidak
disalin dari keluaran kode.

## 4. Larangan

1. Mengubah angka harapan, menandai tes "dilewati", atau melonggarkan penjaga supaya hijau.
2. Menambah toleransi, wewenang, atau aturan bisnis yang tidak ada di paket atau di keputusan pemilik.
3. Memperbaiki **data** di dalam paket perbaikan kode. Data lama yang salah dilaporkan dengan kueri pencarinya.
4. Menghapus endpoint, koleksi, atau field lama sebelum semua pemanggilnya dialihkan dan dibuktikan dengan pencarian.
5. Menyentuh `deploy/docker-compose.yml`, `deploy/Dockerfile.*`, `deploy/backup.sh` tanpa persetujuan tertulis pemilik
   di laporan paket.
6. Menyentuh `middleware/`, gerbang RFID, atau berkas yang sedang dikerjakan agen lain.
7. Menulis `verified` atau `reopened` di tracker.
8. Menyatakan "selesai" dengan gate yang lebih merah daripada garis dasar tanpa menuliskannya.
9. Menjalankan dua gate atau dua POC bersamaan.
10. Meng-commit `.env`, kunci, cadangan data, atau data pelanggan nyata.

## 5. Berhenti dan bertanya (STOP & ASK)

Berhenti, tulis pertanyaannya di tracker sebagai `pending_decision`, dan lanjutkan butir lain bila:

- Cek ulang di `HEAD` menunjukkan temuan sudah berubah bentuk (bukan sekadar pindah baris).
- Perbaikan yang benar memerlukan aturan bisnis: siapa boleh, berapa batasnya, akun mana, tanggal mana.
- Tes yang benar memerlukan mengubah perilaku yang sedang dipakai pengguna (label status, nomor dokumen, isi PDF).
- Indeks unik tidak bisa dibuat karena data kembar sudah ada.
- Perbaikan membutuhkan migrasi data.
- Dua dokumen rujukan bertentangan (laporan audit, keputusan pemilik, dokumen `KN_*`). Yang lebih baru dan lebih
  spesifik tidak otomatis menang; tanyakan.

## 6. Isi laporan paket

Pakai templat di `docs/reviews/README.md`. Tambahkan empat hal yang sering terlewat:

1. **Tabel "Selesai bila"**: tiap butir → nama tes → lapis uji → hasil. Butir yang tidak teruji ditulis "belum teruji"
   dengan alasannya.
2. **Selisih gate** terhadap garis dasar PK-01: gate mana yang berubah warna dan mengapa.
3. **Data lama**: kueri baca-saja untuk menemukan dokumen yang sudah terlanjur terkena cacat ini. Tidak dijalankan
   pada data nyata oleh agen.
4. **Yang sengaja tidak dikerjakan** beserta alasannya, dan temuan baru yang terlihat selama bekerja (diberi ID
   sementara `BARU-n`; reviewer yang menetapkan ID tetap).

## 7. Templat perintah untuk memulai satu paket

Salin, ganti `PK-xx`, dan berikan sebagai pesan pertama sesi:

```text
Kerjakan paket PK-xx dari docs/finance/rencana-2026-11-13/02_PAKET_KERJA_FONDASI.md.

Baca dulu, berurutan:
1. AGENTS.md dan CLAUDE.md
2. docs/reviews/README.md dan docs/reviews/TRACKER.md
3. docs/finance/rencana-2026-11-13/03_PANDUAN_PELAKSANA.md (ikuti §2 langkah demi langkah)
4. docs/finance/rencana-2026-11-13/04_ATURAN_MODUL_BARU.md §1
5. Bagian PK-xx di 02_PAKET_KERJA_FONDASI.md dan baris temuannya di docs/finance/AUDIT_KEUANGAN_2026-11-13.md

Batas:
- Hanya PK-xx. Jangan memperbaiki hal lain yang terlihat; catat sebagai BARU-n di laporan.
- Tulis tes untuk tiap butir "Selesai bila" dan tunjukkan merah sebelum mengubah kode aplikasi.
- Bila menemui salah satu kondisi di 03 §5, berhenti pada butir itu dan tulis pertanyaannya.
- Selesai = laporan docs/reviews/2026-11-13/hasil/PK-xx.md + baris tracker
  implemented_pending_review + commit dan push ke cabang kerja. Jangan membuat pull request.

Laporkan di akhir: butir "Selesai bila" yang hijau, yang belum teruji, selisih gate terhadap PK-01, dan pertanyaan terbuka.
```

## 8. Setelah paket diserahkan

- Reviewer memvalidasi dari laporan dan menulis `hasil/validasi-PK-xx.md`. Hanya reviewer yang menutup temuan.
- Bila `reopened`: sesi baru, paket yang sama, mulai dari catatan reviewer. Jangan menumpuk perbaikan di atas paket lain.
- Paket gelombang 3 ke atas memakai pola dari PK-05 dan PK-06. Bila reviewer mengubah pola itu, perbarui
  `04_ATURAN_MODUL_BARU.md` §1 **sebelum** paket berikutnya dimulai, supaya tidak ada dua versi pola.

## 9. Ukuran yang wajar

Angka ini penilaian perancang, belum diuji:

| Jenis paket | Contoh | Perkiraan besar |
|---|---|---|
| Satu fungsi | PK-07, PK-11 | < 100 baris berubah + tes |
| Satu pola di beberapa endpoint | PK-09, PK-12, PK-13 | 10–20 berkas, perubahan seragam |
| Satu alur ditata ulang | PK-05, PK-06, PK-19, PK-22 | 1 layanan baru + pengalihan pemanggil; paling berisiko |
| Infrastruktur | PK-34, PK-35 | Butuh jendela henti dan uji pulih |

Paket "satu alur ditata ulang" sebaiknya dipecah menjadi dua serah-terima: (a) fungsi baru + tes, pemanggil lama
belum dialihkan; (b) pengalihan pemanggil + penghapusan jalur lama.
