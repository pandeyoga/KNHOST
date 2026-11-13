# Blueprint eksekusi — KNHOST

Blueprint ini mengubah hasil audit dan rancangan menjadi **unit kerja yang bisa dijalankan agen coding secara mandiri**:
fondasi keuangan, peran dan izin, Pusat Pengaturan, konfigurasi perusahaan, menu, dan modul baru (insentif, penggajian,
piutang, pembayaran, pajak, asisten keuangan).

Status: disusun 13 Nov 2026 pada `dca195b`. Belum ada unit yang dikerjakan. Tidak ada kode aplikasi yang diubah saat
menyusunnya.

## Untuk agen pelaksana — mulai di sini

1. `00_ATURAN_EKSEKUSI.md` — putaran kerja, titik henti, larangan. **Wajib dibaca sekali per sesi.**
2. `03_LINGKUNGAN_UJI.md` — cara menyalakan dan menguji.
3. `STATUS.md` — ambil unit teratas berstatus `siap`.
4. `unit/<ID>.md` — spesifikasi unit itu. Dari sana ikuti rujukan ke `02_STANDAR.md` dan `01_KEPUTUSAN.md`.

Jangan membaca seluruh folder. Satu unit dirancang cukup dengan berkasnya sendiri ditambah bagian standar yang dirujuk.

Perintah pembuka sesi:

```text
Kerjakan blueprint di docs/blueprint/. Baca 00_ATURAN_EKSEKUSI.md dan 03_LINGKUNGAN_UJI.md, lalu jalankan putaran
kerja §1: ambil unit `siap` teratas di STATUS.md, kerjakan sampai selesai menurut §2, catat, lanjut ke unit berikutnya.
Berhenti hanya pada titik henti §6 atau bila tidak ada lagi unit `siap`.
```

## Isi folder

| Berkas | Isi | Berubah saat eksekusi? |
|---|---|---|
| `00_ATURAN_EKSEKUSI.md` | Cara kerja agen: putaran, langkah per unit, cabang, titik henti, larangan | Tidak |
| `01_KEPUTUSAN.md` | Keputusan pemilik yang dipakai, beserta nilai bawaan dan cara mengubahnya | Hanya oleh pemilik |
| `02_STANDAR.md` | Kontrak posting, pengaturan, izin dan peran, layar dan bahasa, data, uji | Hanya lewat koreksi yang dicatat |
| `03_LINGKUNGAN_UJI.md` | Dua lingkungan uji, perintah, garis dasar gate | Diperbarui PK-01 |
| `INDEKS_UNIT.md` | 104 unit dalam urutan pengerjaan, prasyarat, temuan yang ditutup | Hanya bila unit dipecah |
| `STATUS.md` | Papan kerja: status tiap unit, commit, laporan, pertanyaan untuk pemilik | **Ya, oleh agen** |
| `unit/<ID>.md` | Satu spesifikasi per unit (`unit/_TEMPLAT.md` = bentuknya; `unit/PR-T1.md` = contoh baku) | Hanya koreksi yang dicatat |
| `alat/cek_blueprint.py` | Pemeriksa: indeks ↔ berkas unit, prasyarat, jangkar kode | Tidak |

## Dari mana isinya

| Sumber | Isi | Menghasilkan unit |
|---|---|---|
| `docs/finance/AUDIT_KEUANGAN_2026-11-13.md` | 139 temuan keuangan; 10 direproduksi dengan menjalankan kode | `PK-01` … `PK-44` |
| `docs/finance/rencana-2026-11-13/` | Rancangan menu, insentif, piutang, pajak dan pembayaran, asisten, penggajian; 48 temuan tambahan | `PK-45`, `PK-46`, `MN-*`, `KM-*`, `CR-*`, `PM-*`, `TX-*`, `AG-*`, `PY-*` |
| `docs/audit/konfigurasi-peran-2026-11-13/` | Audit Pusat Pengaturan, peran dan izin, konfigurasi perusahaan — **dijalankan** terhadap aplikasi utuh | `KF-*`, `PR-*`, `KP-*`, `PK-47` |

Dokumen rancangan menjelaskan **mengapa**; berkas unit menjelaskan **apa persisnya dan bagaimana diuji**. Bila keduanya
berbeda, berkas unit yang berlaku — ia ditulis lebih akhir, dengan membaca kode.

## Urutan besar

```text
Gelombang 0  PK-01…04          persiapan: garis dasar, kerangka uji, cek data (pemilik), cadangan
Gelombang 1  PK-05, PK-06      dua temuan kritis  ──► titik henti H1 (reviewer menyetujui pola posting)
Gelombang 2  PR-T1, PR-T9, KF-T1, PK-47, PK-07…17, PK-45, PK-46
                               lubang besar yang murah: naik hak sendiri, izin pengaturan, entitas, idempotensi, …
Sejajar      PR-T2…T8 · KF-T2…T8 · KP-T1…T9 · MN-T1
                               peran, pengaturan, konfigurasi perusahaan, menu — tidak bergantung pola posting
Gelombang 3  PK-18…25          pola posting dipasang ke semua jalur uang (setelah H1)
Gelombang 4  PK-26…32          nilai persediaan dan antar-PT
Gelombang 5  PK-33…35          infrastruktur database ──► titik henti H2
Gelombang 6  PK-36…40          kontrol
Gelombang 7  PK-41…44          laporan dan layar
Modul        PM · CR · KM · PY · TX · AG · MN-T2/T3
                               bagian baca boleh lebih dulu; bagian tulis menunggu prasyarat di INDEKS_UNIT.md
```

## Tiga prinsip yang membuat ini bisa dijalankan tanpa bertanya di tiap langkah

1. **Keputusan sudah diambil atau dijadikan pengaturan.** Pemilik menyetujui rancangan secara garis besar dan meminta
   aturan seperti "harus dua orang" dibuat bisa diatur dengan bawaan satu orang. Karena itu setiap aturan yang membatasi
   pengguna dibangun sebagai pengaturan per PT, dengan nilai awal = perilaku hari ini. Tidak ada kontrol yang
   mengetat atau melonggar diam-diam saat dipasang (`01_KEPUTUSAN.md`).
2. **Setiap unit membawa ujinya.** Tabel "Uji penerimaan" ditulis sebagai tes lebih dulu dan harus merah sebelum kode
   diubah. Selesai = tes itu hijau dan gate tidak lebih merah dari garis dasar.
3. **Berhenti hanya di delapan keadaan** (`00` §6): pola posting menunggu reviewer, jalur produksi, data nyata, isi
   tabel peraturan, menyalakan fitur tulis untuk PT nyata, data kembar, wilayah di luar blueprint, rahasia.

## Batas blueprint ini

- Spesifikasi ditulis dari **membaca kode** dan, untuk pengaturan dan peran, dari **menjalankan aplikasi di database
  tiruan**. Layar belum pernah dibuka di peramban; data nyata belum diperiksa; indeks unik dan permintaan bersamaan
  belum diuji. Karena itu langkah pertama tiap unit adalah mengecek ulang keadaan di `HEAD`.
- Spesifikasi unit di gelombang 3 ke atas memuat kontrak (perilaku, data, uji), bukan langkah kode, karena bentuk
  kodenya bergantung pada pola yang disahkan di titik henti H1.
- Butir yang menyangkut peraturan pajak tidak diisi: lihat titik henti H4.
- Tidak ada taksiran waktu. Repo ini belum punya ukuran kecepatan pelaksana; `INDEKS_UNIT.md` hanya memberi tingkat
  risiko.

## Memeriksa blueprint

```bash
python docs/blueprint/alat/cek_blueprint.py
```

Harus melaporkan 0 masalah sebelum eksekusi dimulai dan setiap kali berkas unit dikoreksi.
