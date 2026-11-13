# Aturan eksekusi untuk agen pelaksana

Dokumen ini mengatur **cara** blueprint dikerjakan secara mandiri oleh agen coding, unit demi unit, tanpa menunggu arahan
di tiap langkah. Ia menggantikan `docs/finance/rencana-2026-11-13/03_PANDUAN_PELAKSANA.md` untuk pekerjaan blueprint;
`AGENTS.md` dan `docs/reviews/README.md` tetap berlaku.

Prinsipnya: agen berjalan terus selama aturan di sini terpenuhi, dan berhenti hanya pada hal yang memang tidak boleh
diputuskan mesin (§6).

## 1. Putaran kerja

```text
ULANGI:
  1. Baca docs/blueprint/STATUS.md. Ambil unit teratas berstatus `siap`.
     Tidak ada yang `siap` → tulis ringkasan di STATUS.md bagian "Catatan sesi", lalu berhenti.
  2. Tandai unit itu `dikerjakan` (commit kecil pada STATUS.md).
  3. Baca: berkas unit (docs/blueprint/unit/<ID>.md) → bagian standar yang dirujuknya di 02_STANDAR.md
     → keputusan yang dirujuknya di 01_KEPUTUSAN.md. Jangan membaca unit lain.
  4. Kerjakan menurut §2.
  5. Tulis laporan, perbarui STATUS.md dan TRACKER (§5), commit, push.
  6. Unit yang prasyaratnya kini terpenuhi berubah dari `menunggu` menjadi `siap` (perbarui STATUS.md).
```

Satu sesi boleh menyelesaikan beberapa unit. Satu unit tidak boleh dikerjakan setengah lalu ditinggal: bila sesi harus
berakhir di tengah, kembalikan kode ke keadaan hijau terakhir, catat di laporan sampai langkah mana, dan biarkan status
`dikerjakan` dengan catatan.

## 2. Di dalam satu unit

| Langkah | Yang dikerjakan | Wajib ada di laporan |
|---|---|---|
| 1. Awal | `git status` bersih; catat SHA; cabang kerja | SHA awal |
| 2. Cek ulang | Buka tiap berkas:baris di bagian "Keadaan sekarang" unit. Kode bisa sudah bergeser sejak `dca195b` | Per butir: masih berlaku / bergeser ke berkas:baris baru / sudah tidak berlaku (bukti) |
| 3. Uji dulu | Tulis tiap baris tabel "Uji penerimaan" sebagai tes otomatis. Jalankan: harus **gagal** karena sebab yang sama dengan masalahnya. Untuk fitur baru: gagal karena fiturnya belum ada | Keluaran merah |
| 4. Ubah | Ikuti bagian "Perubahan" unit dan standar di `02_STANDAR.md`. Sesedikit mungkin di luar itu | Daftar berkas |
| 5. Hijau | Semua uji penerimaan lulus; tes "diharapkan gagal" milik temuan ini dicabut tandanya | Keluaran hijau |
| 6. Gate | `bash scripts/gate.sh --quick` selalu; `bash scripts/gate.sh` bila unit menyentuh server; penjaga yang disebut unit | Selisih terhadap garis dasar (§4 `03_LINGKUNGAN_UJI.md` dan hasil PK-01) |
| 7. Dokumen | Perbarui berkas yang disebut bagian "Dokumen ikut berubah" pada unit | Daftar |
| 8. Laporan | `docs/reviews/2026-11-13/hasil/<ID>.md` memakai templat di `docs/reviews/README.md` + tabel uji penerimaan (uji → lapis → hasil) + daftar "Asumsi" | Tautan |

Langkah 3 tidak boleh dilewati. Uji yang ditulis sesudah perubahan hanya membuktikan bahwa kode melakukan apa yang
dilakukannya.

## 3. Cabang dan commit

- Cabang integrasi blueprint: `bp/integrasi` (dibuat dari cabang yang ditunjuk pemilik; bila tidak ada arahan, dari
  `main` terbaru). Tiap unit dikerjakan di `bp/<ID>` dari `bp/integrasi` dan digabung kembali setelah langkah 6 hijau.
- Pesan commit berbahasa Indonesia, diawali ID unit: `[PK-05] Bayar hutang: periksa periode sebelum tulis`.
- Tidak membuat pull request dan tidak mendorong ke `main` kecuali pemilik meminta.
- Tidak meng-commit `.env`, kunci, cadangan data, data pelanggan nyata, atau `memory/GATE_RECEIPT.*` hasil jalan di luar
  lingkungan resmi.
- Line ending LF.

## 4. Bila kenyataan berbeda dari blueprint

Blueprint ditulis dari membaca kode dan dari uji di database tiruan; ia bisa salah. Urutan sikap:

| Keadaan | Yang dilakukan |
|---|---|
| Baris kode bergeser, maksudnya sama | Lanjut; catat baris baru |
| Masalahnya ternyata sudah diperbaiki | Tulis uji yang membuktikan; status butir "tidak berlaku — bukti"; lanjut ke butir lain |
| Cara di blueprint tidak bisa dipakai, ada cara lain yang memenuhi **uji penerimaan yang sama** | Pakai cara lain; jelaskan di laporan bagian "Menyimpang dari blueprint" |
| Uji penerimaan di blueprint keliru (angka harapan salah, langkah mustahil) | Jangan mengubah harapan diam-diam. Tulis hitungan yang benar di laporan, perbaiki berkas unit dalam commit terpisah berjudul `[<ID>] Koreksi blueprint: …`, lanjut |
| Butuh aturan bisnis yang tidak ada di `01_KEPUTUSAN.md` | Pakai **aturan bawaan** §4.1; catat di "Asumsi" |
| Masuk daftar §6 | Berhenti pada butir itu |

### 4.1 Aturan bawaan bila keputusan tidak ada

Pemilik menyetujui rancangan secara garis besar dan meminta hal yang bersifat aturan dibuat **bisa diatur**. Maka:

1. Jadikan aturan itu **pengaturan** di Pusat Pengaturan (mengikuti standar `02_STANDAR.md` §2), berlapis global → PT.
2. Nilai bawaannya = **perilaku yang berjalan hari ini**. Bila hari ini tidak ada perilakunya, pilih yang paling tidak
   membatasi pengguna dan paling mudah dibalik.
3. Kontrol "harus dua orang" selalu berupa pengaturan dengan bawaan **satu orang** (keputusan pemilik 13 Nov 2026).
4. Tidak pernah memakai aturan bawaan untuk: arah debit/kredit, akun buku besar, tarif pajak, isi tabel peraturan,
   penghapusan data. Itu masuk §6.

## 5. Status dan pencatatan

`docs/blueprint/STATUS.md` adalah papan kerja agen. Nilai status:

| Status | Arti | Diubah oleh |
|---|---|---|
| `menunggu` | Prasyarat belum `selesai` | Agen (otomatis saat prasyarat selesai → `siap`) |
| `siap` | Boleh dikerjakan sekarang | Agen |
| `tahan` | Tertahan titik henti §6 atau data dari pemilik | Pemilik / reviewer melepasnya menjadi `siap` |
| `dikerjakan` | Sedang dikerjakan | Agen |
| `selesai` | Langkah 1–8 tuntas (= `implemented_pending_review` di tracker) | Agen |
| `tervalidasi` | Sudah divalidasi reviewer | **Hanya reviewer** |

Saat unit `selesai`, baris temuan yang ditutupnya di `docs/reviews/TRACKER.md` diubah menjadi
`implemented_pending_review` dengan commit dan tautan laporan. Agen tidak pernah menulis `verified`, `reopened`, atau
`tervalidasi`.

Unit berikutnya **tidak menunggu** validasi reviewer, kecuali di titik henti §6. Bila reviewer membuka kembali sebuah
unit (`reopened`), unit itu kembali `siap` dan dikerjakan sebelum unit baru.

## 6. Titik henti — satu-satunya alasan berhenti dan bertanya

| # | Keadaan | Mengapa |
|---|---|---|
| H1 | Selesai gelombang 1 (PK-05, PK-06) | Pola posting dari dua unit ini dipakai ulang di ±20 unit; reviewer harus menyetujui bentuknya dulu |
| H2 | Sebelum unit yang menyentuh `deploy/` atau cara menjalankan MongoDB (PK-04, PK-34) | Jalur produksi; butuh jendela henti dari pemilik |
| H3 | Sebelum menjalankan migrasi atau perbaikan pada **data nyata** | Unit hanya menyiapkan skrip dan uji di data acuan; menjalankannya keputusan pemilik |
| H4 | Isi tabel dari peraturan (tarif PPh 21, PTKP, faktor DPP) dan arah/akun jurnal yang tidak disebut unit | Tidak boleh diisi dari ingatan atau tebakan |
| H5 | Sebelum menyalakan fitur **tulis** modul baru untuk PT nyata (sakelar per PT) | Angkanya harus sudah dicocokkan pemilik dengan cara manual |
| H6 | Indeks unik tidak bisa dibuat karena data kembar sudah ada | Menggabung atau menghapus data bukan wewenang agen |
| H7 | Pekerjaan menyentuh `middleware/`, gerbang RFID, atau berkas yang sedang diubah agen lain | Di luar blueprint |
| H8 | Unit meminta rahasia (kunci API, sandi) atau akses ke layanan luar | — |

Cara berhenti: tandai unit `tahan`, tulis pertanyaannya di `STATUS.md` bagian "Menunggu pemilik" (satu kalimat
pertanyaan + pilihan yang tersedia + usulan), lalu **lanjutkan unit `siap` berikutnya**. Berhenti total hanya bila tidak
ada lagi unit `siap`.

## 7. Larangan

1. Mengubah angka harapan, melewati tes, atau melonggarkan penjaga supaya hijau.
2. Memperbaiki **data** di dalam unit perbaikan kode.
3. Menghapus endpoint, koleksi, field, atau layar lama sebelum pemanggilnya dialihkan dan dibuktikan dengan pencarian.
4. Menambah menu sidebar, dasbor, atau antrean baru di luar yang disebut unit (`02_STANDAR.md` §4).
5. Menulis nilai bisnis sebagai konstanta di kode (`02_STANDAR.md` §2).
6. Memeriksa wewenang dengan nama peran (`role ==`, `role_in`, `roleIs`) di kode baru (`02_STANDAR.md` §3).
7. Menjalankan dua gate bersamaan; mengubah `backend/pytest.ini`.
8. Menyebut nama model atau alat AI di kode, dokumen, atau pesan commit.

## 8. Ukuran dan pemecahan

Unit bertanda risiko **tinggi** dikerjakan dalam dua serah-terima yang masing-masing hijau: (a) fungsi atau jalur baru
beserta ujinya, jalur lama belum disentuh; (b) pengalihan pemanggil dan pematian jalur lama. Keduanya dilaporkan di
laporan unit yang sama, dengan SHA masing-masing.

Bila sebuah unit ternyata lebih besar dari perkiraan, pecah di batas yang utuh, beri akhiran (`PK-19a`, `PK-19b`),
tambahkan barisnya di `STATUS.md`, dan lanjutkan.

## 9. Yang tidak pernah boleh diasumsikan selesai

- "Tes lulus" bukan berarti alurnya benar. Untuk unit yang mengubah jurnal, laporan unit wajib memuat satu contoh
  angka: dokumen → jurnal (akun, debit, kredit) → saldo buku pembantu, dengan hitungan tangan.
- Uji di database tiruan tidak membuktikan keunikan maupun perilaku bersamaan. Butir demikian yang belum diuji di
  MongoDB asli ditulis "belum teruji", bukan "lulus".
- Layar yang belum dibuka di peramban ditulis "belum diuji jalan".
