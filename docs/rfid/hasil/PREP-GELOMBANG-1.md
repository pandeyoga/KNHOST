# Persiapan RFID tanpa perangkat — gelombang 1 (integrasi)

- Tanggal: 9 Nov 2026 · Pelaksana: Claude Code (koordinator) + 4 agen paralel (worktree terpisah).
- Dasar: permintaan pemilik 8 Nov ("siapkan sebisa mungkin sebelum perangkat datang") dan keputusan di
  [`../KEPUTUSAN_GATE_RFID.md`](../KEPUTUSAN_GATE_RFID.md) §6–§8. Status: **implemented_pending_review**.
- Branch integrasi `integrasi-prep` digabung ke `main`. Laporan per paket:
  [A](PREP-A-MASTER-DATA.md) · [B](PREP-B-OPNAME-AWAL.md) · [C](PREP-C-GUDANG-PUTAWAY.md) · [D1](PREP-D1-GATE-V2.md).

| Paket | Isi | Commit paket |
|---|---|---|
| A — Master data | Lembar perbaikan master produk (unduh XLSX/CSV → isi → pratinjau → terapkan per batch → batalkan), penanda `superseded_by` ("digantikan oleh"), pemilih dokumen baru menyembunyikan SKU tergantikan + petunjuk | `9497a17`, `b74d419`, `56acade` |
| B — Opname awal | Pendaftaran ulang stok dari fisik per gedung (sesi, pembekuan zona/penuh, baris lapangan HP, produk belum dikenali, rekonsiliasi per produk, persetujuan massal: roll + tag lahir bersamaan, roll lama tak terdaftar dihapus, jurnal biaya rata-rata) | `4a76067` |
| C — Fondasi gudang | Profil gedung bisa diatur (gate + mode konfirmasi + pasangan IN/OUT, peran inspeksi/bahan, mode stok, rak/lantai, aturan artikel/PT), gedung tunggal → `stored`, routing inspeksi, draf putaway otomatis, tiba bertahap per trip (`confirm_arrival_trip`), celah izin/roll ditahan/0 tiba | `8c90916` |
| D1 — Inti gate V2 | Patch Kubus 0.5.0 diterapkan + perbaikan sisi server (alarm merah hanya pelanggaran, satu kunci per gate, sesi dokumen bertahap, klaim tak bocor, lintasan batal, overflow, galat terstruktur, kinerja, flag protokol, auto-cocok dokumen, alert kesehatan, sumber Makloon/Perbaikan, parameter per gate) + kontrak **2.1.0** + simulator 10 skenario + panel "Integrasi reader U300" | `9824240`, `e7d53d1`, `2723798` |

## Perbaikan saat integrasi (koordinator)
- **B × C**: jalur putaway baru dari C (terbit draf, trip tiba, tutup sisa) melewati kait pembekuan B → kait ditambahkan
  (`7120d6c`) + uji `test_prep_integrasi_freeze_putaway.py` 4 lulus (`c875597`).
- `superseded_by` A (id produk) cocok dengan pembacaan defensif B (diikuti ≤5 langkah).
- Kode keputusan internal (K-OPN-xx) dihapus dari teks yang dilihat pengguna (`11222d4`); panel draf menyebut nama
  setelan, bukan kunci teknis (`6bdec54`). README middleware: patch sudah diterapkan, reader masih 0.4.0 (`c2c665d`).
- `CODEBASE_MAP.md` diregenerasi.

## Bukti uji (apa adanya)
- **Perbandingan `main` (`0ed4ea8`) vs integrasi** pada salinan DB uji yang sama, Mongo & backend sementara terisolasi,
  48 berkas uji lama relevan (gate, RFID, putaway, gudang, lokasi, GRN, QC/inspeksi, opname, transfer, picking,
  potong, katalog, makloon):
  * `main`: 49 gagal / 280 lulus / 21 error · integrasi: 49 gagal / **330** lulus / 21 error (+50 = uji baru A 10, B 3,
    C 15, D1 18, integrasi 4). **Daftar 70 uji gagal/error identik** — tidak ada yang hanya gagal di integrasi
    (merah lama: data acuan/fixture, mis. iter266, p03_transfer_receipt, iter265, f10, transfer_status_guard).
  * `test_iter117_p09` 18/18 dan `test_iter118_p10` 8/8 lulus di keduanya (dijalankan terpisah — keduanya mengunci
    `localhost:27017/test_database` dan bentrok loop dengan berkas ber-`_shared_loop`).
- **Stack uji resmi** (`kn-uji-backend`, DB `kn_test_trial`): uji baru A+B+C + makloon 48/48; integrasi pembekuan 4/4.
- **Jest** paket baru `prepAMasterCleanup`, `prepBInitialRegistration`, `prepCWarehousePutaway`, `prepD1GateV2`:
  **26/26** sesudah koreksi teks.
- **Guardrail** di kode integrasi: hijau — custom_modals 98, error_notice 272, escape_layers 1169, uom_vocab 1170,
  knselect_contract, picker_portal 312, detail_modal 26, modal_dismiss, page_tabs, role_label 1162, blocking_dialogs,
  status_history, view_aliases, access_catalog_nav, desk_targets, notification_audience, rfid_tag_unique,
  roll_identity. Merah lama tidak naik: auth_coverage 8, atomic_claim 6 (BELUM DITINJAU 77 → **75**), to_list_bound 6,
  numeric_bounds 3, qty_dual 5, ref_unlink 3.
- **Peramban** (`:3063`, Admin & Gudang): panel "Perbaikan master produk" (Master Produk); unduh lembar via API =
  XLSX 411 produk, sheet Produk + Petunjuk, pratinjau dengan galat berbahasa Indonesia (tanpa menulis); Stock Opname ›
  "Pendaftaran awal gedung (RFID)" + pop-up sesi; HP 390 px Pindai › Daftar Awal (`scrollWidth` = 390); profil gedung
  (peran Inspeksi/Gudang Bahan, mode stok, bentuk simpan, gate & mode konfirmasi); Lokasi › Perintah Simpan ke Rak
  (panel Draf Putaway otomatis); Perangkat RFID › "Integrasi reader U300". Tangkapan layar tidak tersedia (panel
  peramban tidak menggambar) — verifikasi lewat teks/DOM. Pop-up hanya dibuka lalu ditutup; tidak ada data disimpan.

## Perubahan perilaku untuk pengguna
- SKU yang "digantikan oleh" tidak muncul di pemilih dokumen baru; mengetik SKU lama memunculkan penggantinya.
- Gedung tunggal (Soreang/Jakarta): roll baru langsung tercatat tersimpan (tanpa tahap transit).
- Draf putaway otomatis setelah QC lulus / GRN tanpa QC (setelan bawaan aktif; draf tidak mengunci roll).
- Terima pengecualian putaway butuh izin approve; roll yang ditahan ditolak dari putaway; putaway tanpa satu pun roll
  tiba tidak lagi "selesai".
- Selama sesi pendaftaran awal berjalan, gerakan roll dari/ke area beku ditolak dengan pesan jelas.
- Gate V2 (berlaku untuk reader ber-protokol V2): trip parsial hijau dengan sisa "menunggu"; keanggotaan transfer
  diperketat (roll harus tercantum di dokumen); jalur lama `/api/rfid/ingest` menolak reader V2.

## Butuh keputusan pemilik (dari laporan paket)
1. **Izin unduh lembar master** (A): peran MD bawaan tidak punya `product.export` — beri izin ekspor ke MD, atau izinkan
   unduh dengan `product.update`.
2. **Waktu perbaikan master** (A): sesudah GANTI_KODE/GABUNG_KE stok lama tetap di SKU lama sampai gedungnya
   didaftarkan ulang → disarankan perbaiki master tepat sebelum opname per gedung.
3. **Roll lama yang masih dialokasikan pesanan** saat pendaftaran (B): dilepas otomatis, atau tetap pengecualian
   manual (sekarang).
4. **Persetujuan Finance terpisah** untuk pendaftaran awal (B): sekarang satu izin `inventory.approve_count`.
5. **Gedung Retur RCM** (C): diasumsikan tempat inspeksi **tanpa** gate, padahal juga menyimpan grade B/BS/C.
6. **Penanda "minta inspeksi"** (C): belum ada di sistem; sementara = roll yang masuk SPK QC 4-point (inspeksi per 15
   yard) dirutekan ke gedung inspeksi.
7. Tetap terbuka: K-OPN-05 (keunikan EPC tag), K-RFID-03/05/08, penamaan alamat bin.

## Belum dikerjakan
- **Gelombang 2**: D2 (gate → konfirmasi tiba putaway/transfer & bukti kirim, antrean periksa admin gudang, kios kuning,
  koreksi klaim beraudit, tutup sesi dokumen otomatis) dan E (aplikasi reader 0.5: photo-eye satu arah, ringkasan
  bacaan, parse RSSI tahan locale, galat terstruktur, setelan Gen2/TagFocus, dsb.).
- Butuh perangkat: uji meja SDK U300, kalibrasi ambang, pengkabelan photo-eye, uji beban 2.000 roll, pilot.
- Sisa teknis per paket: lihat laporan masing-masing (mis. filter strip POS Terlaris/Unggulan, kait pembekuan di
  `cutting_service.receive`/`mdq_cut_service.cut`, draf putaway dari makloon tanpa QC, `run_u300_https.py` butuh JDK).
- Data uji tertinggal di DB uji: perangkat `UJI-CELUP gate-out` (dari P18); tidak ada sisa `TEST_INTFZ_*`.
