# KF-T7 — Nilai bisnis yang ditulis mati menjadi pengaturan

| | |
|---|---|
| Gelombang | Jalur pengaturan (sejajar gelombang 3–7) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | KF-T2 |
| Menutup temuan | KP-27, KP-28, CR-03 |
| Keputusan | K-27 (nama kunci dan bawaan 14 hari); selebihnya aturan bawaan `00` §4.1 |
| Standar | §2.1, §2.2, §2.4, §4 (L1) |
| Lingkungan uji | B |

## Tujuan

Angka kebijakan yang selama ini hanya bisa diubah pengembang — hari telat yang memblokir pelanggan, masa reservasi stok,
ambang pesanan khusus, ambang stok menipis, aturan inspeksi, batas salah sandi, umur sesi, dan lain-lain — tampil di
Pusat Pengaturan dengan nilai bawaan yang sama dengan hari ini, dan mesin membacanya dari sana.

## Keadaan sekarang

Semua `[dibaca]`; sumber: Lampiran A `docs/audit/konfigurasi-peran-2026-11-13/lampiran/C_konfigurasi_perusahaan.md`
butir #1–9, #45–54, #64–69, dicek ulang pada `3132cc4`.

| # | Konstanta | Nilai | Jangkar |
|---|---|---|---|
| 1, 2 | Hari telat yang memblokir pelanggan (dua salinan) | 14 | `backend/services/ar_aging_service.py:35` (`OVERDUE_BLOCK_DAYS`), dipakai di baris 96; `backend/services/customer_service.py:15` (`OVERDUE_BLOCK_DAYS`), dipakai di baris 253 |
| 3, 4 | Peringatan piutang terhadap plafon (dua salinan) | 0,8 | `backend/services/ar_aging_service.py:34` (`WARNING_RATIO`); `backend/services/customer_service.py:14` (`WARNING_RATIO`) |
| 5 | Masa reservasi stok pesanan | 3 hari | `backend/routers/sales_orders.py:544` (`expires`); teks job `backend/services/scheduler_service.py:106` (`reservation_expiry`) |
| 6 | Maksimum anggota group sales | 2 | `backend/services/customer_service.py:21` (`MAX_GROUP_SALES`) |
| 7 | Pesanan khusus wajib disetujui di atas | Rp10.000.000 | `backend/services/special_order_service.py:24` (`APPROVAL_THRESHOLD`), dipakai di baris 89 dan `backend/routers/special_orders.py:180` (`APPROVAL_THRESHOLD`) |
| 8 | Margin bawaan pesanan khusus | 30 % | `backend/services/special_order_phase2.py:27` (`DEFAULT_MARGIN_PCT`); dibaca dari `system_settings{scope: "special_order"}` yang tidak punya penulis (`backend/services/special_order_phase2.py:52` (`default_margin_pct`)) |
| 9 | Jumlah barang minimum "multi-barang" | 2 | `backend/services/special_order_phase2.py:280` (`MULTI_ITEM_MIN`) |
| 45, 46 | Ambang stok menipis bila barang tanpa titik pesan ulang (dua salinan) | 100 | `backend/services/notification_service.py:16` (`LOW_STOCK_THRESHOLD`); `backend/services/stock_availability.py:22` (`LOW_STOCK_QTY`) |
| 47 | "Reservasi mendekati kedaluwarsa" | 24 jam | `backend/services/notification_service.py:216` (`soon`) |
| 48 | Jendela dan pita tren penjualan | 30 hari; ±10 % | `backend/services/stock_analytics_service.py:39` (`TREND_WINDOW_DAYS`), `backend/services/stock_analytics_service.py:40` (`TREND_BAND`) |
| 49 | Panjang maksimum roll saat stok dipecah | 150 | `backend/services/roll_service.py:238` (`MAX_AVAILABLE_ROLL_LEN`) |
| 50 | Format surat jalan pemasok dipakai otomatis | ≥ 3 terkonfirmasi; ≥ 80 % sama | `backend/services/supplier_dn_profile_service.py:14` (`MIN_CONFIRMED`), `backend/services/supplier_dn_profile_service.py:15` (`LOCALE_SHARE`) |
| 51 | Isi katalog sampel per warna | 1 yard; +2 yard | `backend/services/sample_sale_service.py:38` (`CATALOGUE_BASE_QTY`), `backend/services/sample_sale_service.py:39` (`CATALOGUE_SOFT_QTY`) |
| 52 | Titik inspeksi 4-point | tiap 15 yard; minimum 10 | `backend/services/qc_inspection_service.py:54` (`INTERVAL_YARD`), `backend/services/qc_inspection_service.py:55` (`MIN_INTERVALS`) |
| 53 | Faktor harga per grade (cadangan kode) | A 100 … BS 10 | `backend/services/return_grade_impairment.py:15` (`DEFAULT_FACTORS`) |
| 54 | Jendela retur dan pengingat (cadangan kode) | 21; 21; 3 | `backend/services/return_policy_service.py:294` (`RETURN_ASSUMPTION_DEFAULTS`) |
| 64 | Toleransi pembulatan saat mencocokkan buku | Rp1 | `backend/services/gl_service.py:3275` (`ROUNDING_TOLERANCE`) |
| 65 | Panjang minimum alasan melewati akun sementara saat tutup buku | 5 huruf | `backend/services/closing_service.py:37` (`SUSPENSE_OVERRIDE_MIN_LEN`) |
| 66 | Panjang minimum alasan lain | 15; 10 | `backend/services/inspection_service.py:124` (`MIN_REASON`); `backend/services/putaway_arrival_service.py:37` (`MIN_CLOSE_REASON`) |
| 67 | Batas salah sandi dan lama akun dikunci | 5 kali; 15 menit | `backend/routers/auth.py:28` (`MAX_LOGIN_ATTEMPTS`), `backend/routers/auth.py:29` (`LOCKOUT_MINUTES`) |
| 68 | Umur sesi masuk | 24 jam | `backend/core_utils.py:12` (`SESSION_TTL_HOURS`); dipakai `backend/dependencies.py:16` (`session_expiry`) dan `backend/routers/auth.py:133` (`SESSION_TTL_HOURS`) |
| 69 | Umur kode dan batas coba tanda tangan elektronik | 10 menit; 5 kali | `backend/services/esign_service.py:20` (`OTP_TTL_MIN`), `backend/services/esign_service.py:21` (`MAX_ATTEMPTS`) |

Bagian #66 yang berada di `backend/services/gate_review_actions.py:27` (`MIN_REASON`) adalah tindakan antrean gerbang
RFID; **tidak disentuh** (titik henti H7).

## Perubahan

### Data

Tidak ada koleksi baru. Satu migrasi sekali jalan (penanda `__migrations__.kft7_margin_pesanan_khusus`): bila
`system_settings{scope: "special_order"}.default_margin_pct` ada, salin ke `sales.special_order_margin_pct` lapisan grup
lewat `config_resolver.set_value` (alasan "Pindahan dari penyimpanan lama"). Dokumen lama tidak dihapus.

### Server

Aturan umum untuk tiap baris: konstanta dihapus; pemakainya membaca `await value_of("<kunci>", {"entity_id": <PT
dokumen>})` (untuk kunci hanya-grup tanpa konteks); bila pembaca gagal, cadangan = `config_registry.default_of(key)`
(lahir di KF-T2). Fungsi sinkron yang memakai konstanta menerima nilainya sebagai parameter dari pemanggil asinkronnya.

| Tempat | Perubahan khusus |
|---|---|
| `customer_service` | Fungsi baru `async def credit_thresholds(entity_id: str) -> dict` → `{"block_days": int, "warning_ratio": float}` dari `ar.overdue_block_days` dan `ar.credit_warning_pct` (÷ 100). Satu-satunya pembaca dua ambang; `ar_aging_service._credit_status` dan hitung status di `customer_service` (baris 253) menerima hasilnya sebagai parameter. PT = `entity_id` pelanggan |
| `routers/sales_orders.py` (baris 544) | `timedelta(days=<sales.reservation_days PT pesanan>)`. Deskripsi job `reservation_expiry` tidak lagi menyebut "(3 hari)" melainkan "(menurut pengaturan masa reservasi)" |
| `special_order_service`, `routers/special_orders.py` | Perbandingan `total_amount > <approval.special_order_min_amount PT pesanan>`; impor `APPROVAL_THRESHOLD` di router dihapus |
| `special_order_phase2.default_margin_pct(entity_id="")` | Membaca `sales.special_order_margin_pct`; tidak lagi membaca `system_settings` langsung |
| `notification_service`, `stock_availability` | Ambang = titik pesan ulang barang, bila kosong `inventory.low_stock_default_qty`. Jendela "mendekati kedaluwarsa" = `notif.reservation_expiry_warn_hours` |
| `dependencies.session_expiry(hours: int)`; `routers/auth.py`; `bootstrap.py` | Pemanggil mengirim `keamanan.umur_sesi_jam`; `max_age` kuki = nilai itu × 3600. Sesi yang sudah ada tidak diubah |
| `return_grade_impairment`, `return_policy_service`, `return_disposition_service` | `DEFAULT_FACTORS` dan `RETURN_ASSUMPTION_DEFAULTS` dihapus; cadangan literal `or 21` / `or 3` diganti `default_of`. Kuncinya sudah ada sejak KF-T2 |

### Pengaturan

Semua `permission=("settings", "manage")`, `sensitif_baca` mengikuti kelompok, `consumers` = berkas:fungsi pembaca pada
tabel "Keadaan sekarang". `impact` dan `example` ditulis pelaksana menurut `02` §2.1 dengan angka bawaan.

| # | key | group | type | default | min · max · unit | scopes | label | help |
|---|---|---|---|---|---|---|---|---|
| 1, 2 | `ar.overdue_block_days` | `uang-masuk` | `duration` | 14 | 0 · 365 · hari | global, entity | Blokir pelanggan bila telat lebih dari (hari) | Pelanggan tidak bisa membuat pesanan kredit baru bila tagihan tertuanya telat lebih dari angka ini. 0 = telat satu hari pun langsung diblokir. |
| 3, 4 | `ar.credit_warning_pct` | `uang-masuk` | `pct` | 80 | 1 · 100 · % | global, entity | Peringatkan saat piutang mencapai (% plafon) | Status pelanggan menjadi "peringatan" saat piutangnya mencapai persen ini dari plafon. 100 = hanya saat plafon penuh. |
| 5 | `sales.reservation_days` | `harga-diskon` | `duration` | 3 | 1 · 60 · hari | global, entity | Masa reservasi stok pesanan (hari) | Pesanan yang belum disetujui melepas stok cadangannya setelah sekian hari. |
| 6 | `sales.group_sales_max_members` | `harga-diskon` | `int` | 2 | 1 · 20 · orang | global, entity | Maksimum anggota tim sales per pelanggan | Batas jumlah sales yang berbagi satu pelanggan. |
| 7 | `approval.special_order_min_amount` | `persetujuan` | `money` | 10000000 | 0 · 100000000000 · Rp | global, entity | Pesanan khusus wajib disetujui di atas (Rp) | Pesanan khusus bernilai di atas angka ini menunggu persetujuan. 0 = semua pesanan khusus wajib disetujui. `risk="high"` |
| 8 | `sales.special_order_margin_pct` | `harga-diskon` | `pct` | 30 | 0 · 500 · % | global, entity | Margin bawaan pesanan khusus (%) | Dipakai menghitung usulan harga jual pesanan khusus bila margin tidak diisi. 0 = tanpa margin bawaan. |
| 9 | `sales.special_order_multi_item_min` | `harga-diskon` | `int` | 2 | 2 · 50 · barang | global | Jumlah barang minimum pesanan multi-barang | Pesanan khusus dengan barang sebanyak ini atau lebih diperlakukan sebagai multi-barang. |
| 45, 46 | `inventory.low_stock_default_qty` | `stok-satuan` | `decimal` | 100 | 0 · 1000000 · satuan dasar | global | Ambang stok menipis bila barang belum diatur | Dipakai untuk barang tanpa titik pesan ulang. 0 = barang tanpa titik pesan ulang tidak pernah diperingatkan. |
| 47 | `notif.reservation_expiry_warn_hours` | `notifikasi` | `int` | 24 | 1 · 168 · jam | global | Ingatkan sebelum reservasi kedaluwarsa (jam) | Pemberitahuan dikirim bila reservasi akan kedaluwarsa dalam sekian jam. |
| 48 | `inventory.stock_analytics.trend_window_days` | `stok-satuan` | `duration` | 30 | 7 · 365 · hari | global, entity | Jendela arah tren penjualan (hari) | Rata-rata penjualan sekian hari terakhir dibandingkan dengan jendela laju jual. |
| 48 | `inventory.stock_analytics.trend_band_pct` | `stok-satuan` | `pct` | 10 | 0 · 100 · % | global, entity | Tren dianggap stabil dalam rentang (%) | Selisih di dalam rentang ini disebut "stabil". 0 = selisih sekecil apa pun disebut naik atau turun. |
| 49 | `inventory.split_roll_max_length` | `stok-satuan` | `decimal` | 150 | 1 · 10000 · satuan dasar | global | Panjang maksimum roll saat stok dipecah | Stok tanpa rincian roll dipecah menjadi roll sepanjang paling banyak angka ini. |
| 50 | `receiving.dn_profile_min_confirmed` | `penerimaan` | `int` | 3 | 1 · 50 · surat jalan | global | Surat jalan terkonfirmasi sebelum format dipakai otomatis | Format surat jalan pemasok dipakai otomatis setelah sebanyak ini terkonfirmasi. |
| 50 | `receiving.dn_profile_min_share_pct` | `penerimaan` | `pct` | 80 | 1 · 100 · % | global | Kesamaan format minimum (%) | Dan paling sedikit persen ini dari bukti menunjukkan format yang sama. |
| 51 | `sales.sample_catalogue_base_qty` | `harga-diskon` | `decimal` | 1 | 0.1 · 100 · yard | global, entity | Isi katalog sampel per warna (yard) | Panjang kain per warna dalam satu katalog sampel. |
| 51 | `sales.sample_catalogue_soft_qty` | `harga-diskon` | `decimal` | 2 | 0 · 100 · yard | global, entity | Tambahan warna "soft" pada katalog (yard) | Ditagihkan sebagai komponen terpisah. 0 = tanpa tambahan. |
| 52 | `qc.inspection_interval_yard` | `kualitas` | `decimal` | 15 | 1 · 500 · yard | global, entity | Jarak antar titik inspeksi (yard) | Lembar inspeksi 4-point memuat satu titik tiap sekian yard. |
| 52 | `qc.inspection_min_points` | `kualitas` | `int` | 10 | 1 · 100 · titik | global, entity | Jumlah titik inspeksi minimum | Roll pendek tetap diperiksa sebanyak ini. |
| 64 | `finance.rounding_tolerance_rupiah` | `keuangan-dasar` | `money` | 1 | 0 · 1000 · Rp | global | Selisih yang dianggap pembulatan (Rp) | Selisih pencocokan buku sampai angka ini ditandai sebagai pembulatan, bukan kesalahan. 0 = tidak ada toleransi. `risk="high"` |
| 65 | `periode.suspense_reason_min_chars` | `keuangan-dasar` | `int` | 5 | 1 · 200 · huruf | global | Panjang minimum alasan melewati akun sementara | Berlaku saat tutup buku dipaksa walau akun sementara bersaldo. |
| 66 | `qc.hold_reason_min_chars` | `kualitas` | `int` | 15 | 1 · 200 · huruf | global | Panjang minimum alasan keputusan inspeksi | — |
| 66 | `putaway.close_reason_min_chars` | `stok-satuan` | `int` | 10 | 1 · 200 · huruf | global | Panjang minimum alasan menutup kedatangan | — |
| 67 | `keamanan.maks_salah_sandi` | `keamanan` (baru) | `int` | 5 | 3 · 20 · kali | global | Salah sandi berturut-turut sebelum akun dikunci | — `risk="high"` |
| 67 | `keamanan.lama_kunci_menit` | `keamanan` | `int` | 15 | 1 · 1440 · menit | global | Lama akun dikunci setelah salah sandi (menit) | — `risk="high"` |
| 68 | `keamanan.umur_sesi_jam` | `keamanan` | `int` | 24 | 1 · 720 · jam | global | Lama sesi masuk berlaku (jam) | Sesudah itu pengguna diminta masuk lagi. Berlaku untuk sesi yang dibuat sesudah perubahan. `risk="high"` |
| 69 | `esign.otp_ttl_minutes` | `dokumen` | `int` | 10 | 1 · 60 · menit | global | Masa berlaku kode tanda tangan (menit) | — |
| 69 | `esign.max_attempts` | `dokumen` | `int` | 5 | 1 · 20 · kali | global | Batas salah kode tanda tangan | — |

`help` bertanda "—" ditulis pelaksana (satu kalimat: apa yang diatur). Kelompok baru di `config_registry.GROUPS`:
`{"id": "keamanan", "label": "Keamanan Akun & Sesi", "order": 24, "question": "Berapa kali salah sandi sebelum akun
dikunci, dan berapa lama sesi masuk berlaku?"}`; dipetakan ke layar `settings-cfg-system` di
`frontend/src/features/settings/config/configGroupViews.js`.

### Izin dan peran

Tidak ada.

### Layar

Tidak ada layar baru: kunci tampil otomatis di Pusat Pengaturan. Kelompok "Keamanan Akun & Sesi" tampil sebagai chip di
Pengaturan › Integrasi & Sistem › Tampilan & Asisten.

## Uji penerimaan

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | Impor registry | 27 kunci tabel ada; bawaannya sama dengan kolom "Nilai" di "Keadaan sekarang" |
| U2 | statik | — | Untuk tiap konstanta di tabel "Keadaan sekarang", cari namanya di berkas yang disebut baris itu dan di pemakainya (`grep -rn` di `backend/`, kecuali `gate_review_actions.py`) | 0 definisi dan 0 pemakaian tersisa di berkas-berkas itu |
| U3 | B | Pelanggan `ent_ksc` dan `ent_kanda`, masing-masing telat 10 hari, plafon 0 | `credit_thresholds`; status kredit keduanya; Admin simpan `ar.overdue_block_days=7` lapisan PT `ent_ksc`; hitung ulang | Awal: keduanya "warning" (10 ≤ 14). Sesudah: `ent_ksc` "blocked" (10 > 7), `ent_kanda` tetap "warning" |
| U4 | B | Pelanggan plafon 10.000.000, piutang 7.000.000, tidak telat | Status kredit; Admin simpan `ar.credit_warning_pct=60` lapisan PT-nya | "active" (7 jt < 80 % × 10 jt = 8 jt); lalu "warning" (7 jt ≥ 6 jt) |
| U5 | B | — | Hasil umur piutang (`ar_aging_service`) dan kartu pelanggan (`customer_service`) untuk pelanggan U3 sesudah perubahan | Keduanya memberi status yang sama (satu pembaca) |
| U6 | B | Admin simpan `sales.reservation_days=5` lapisan PT `ent_ksc` | Hitung tanggal kedaluwarsa pesanan baru di `ent_ksc` dan `ent_kanda` (fungsi pembantu yang diekstrak dari baris 544) | Sekarang + 5 hari; sekarang + 3 hari |
| U7 | B | — | `special_order_service` menilai pesanan 8.000.000 dan 12.000.000; Admin simpan `approval.special_order_min_amount=5000000` lapisan PT `ent_ksc`; nilai ulang pesanan 8.000.000 di kedua PT | Awal: tidak perlu; perlu. Sesudah: `ent_ksc` perlu (8 jt > 5 jt), `ent_kanda` tidak |
| U8 | B | `system_settings{scope: "special_order"}.default_margin_pct = 25` disisipkan sebelum migrasi | Jalankan migrasi; `default_margin_pct()` | 25.0; tanpa dokumen lama: 30.0 |
| U9 | B | Barang tanpa titik pesan ulang, stok tersedia 60 | Pindai stok menipis; Admin simpan `inventory.low_stock_default_qty=50`; pindai lagi (data baru) | Peringatan dibuat (60 < 100); tidak dibuat (60 ≥ 50) |
| U10 | B | Admin simpan `keamanan.maks_salah_sandi=3` | Masuk dengan sandi salah 3 kali, lalu sandi benar | Percobaan ke-4 ditolak karena akun terkunci (sebelumnya baru terkunci setelah 5) |
| U11 | B | Admin simpan `keamanan.umur_sesi_jam=2` | Masuk; baca `expires_at` sesi baru | ≈ sekarang + 2 jam (selisih < 1 menit); sesi yang dibuat sebelum perubahan tetap pada kedaluwarsa lamanya |
| U12 | B | Admin simpan `qc.inspection_interval_yard=10` lapisan PT `ent_ksc` | `interval_count` untuk roll 200 yard milik `ent_ksc` dan `ent_kanda` | 20 (⌈200 ÷ 10⌉); 14 (⌈200 ÷ 15⌉ = 14, di atas minimum 10) |
| U13 | B | — | Admin simpan `keamanan.maks_salah_sandi=2`; `esign.max_attempts=0`; `ar.credit_warning_pct=0` | Tiga-tiganya 400 (di bawah minimum) |
| U14 | B | — | Putaran `t1_config.py` untuk 27 kunci | Lulus (`02` §2.4 butir 1) |
| U15 | statik | — | `python scripts/audit_config_wiring.py --strict`; uji `phase3Settings` (kelompok ↔ layar) | Hijau; kelompok `keamanan` punya rumah |

## Langkah kerja

1. `backend/tests_mem/test_KFT7_nilai_tertulis.py`: U1–U13 merah.
2. Daftarkan 27 kunci dan kelompok `keamanan`; U1 hijau.
3. Ganti pemakai per kelompok butir, satu commit per kelompok: kredit (#1–4) → penjualan (#5–9) → stok dan potong
   (#45–52) → retur (#53–54) → buku besar dan alasan (#64–66) → keamanan dan tanda tangan (#67–69).
4. Migrasi margin; U8. Gate; laporan memuat tabel "konstanta → kunci → pemakai" hasil akhir.

## Dokumen ikut berubah

`memory/PRD.md` (daftar pengaturan baru); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` bila ada istilah baru di label.

## Di luar lingkup

- Butir persetujuan #10–23 → KP-T4 (di sana `approval.special_order_min_amount` menjadi baris tabel kebijakan).
  Pengingat dan penjadwal #24–44 → KP-T7. SDM #57–62 → PY-T3 dan PK-46. Penomoran #70–71 → KP-T5. Judul kop #72 → KP-T6.
- #55 (kebijakan bayar antar-PT) sudah ditutup KF-T2. #56 (bawaan kebijakan makloon di `contract_service`) dan #63
  (selang simpan posisi pelacakan) tidak dipegang unit ini; dicatat di laporan sebagai sisa Lampiran A.
- Ambang kredit per pelanggan, plafon, dan gerbang kredit di empat titik → CR-T1, CR-T3.
- Panjang alasan di antrean gerbang RFID → di luar blueprint (H7).

## Asumsi dan risiko

- `ASUMSI:` kunci keamanan, tanda tangan elektronik, ambang stok menipis, dan profil surat jalan hanya berlapis grup
  karena pemakainya tidak mengenal PT (login terjadi sebelum PT dipilih; pindai stok tidak per PT).
- `ASUMSI:` `ar.overdue_block_days` belum diberi lapisan pelanggan di sini; K-27 "bisa ditimpa per pelanggan" dipenuhi
  profil kredit CR-T1.
- `ASUMSI:` arti konstanta #49 ("stok dipecah menjadi roll") diambil dari komentar kodenya; label diperiksa ulang
  pelaksana terhadap pemakainya di `backend/services/roll_service.py:553` (`MAX_AVAILABLE_ROLL_LEN`) sebelum ditulis.
- `RISIKO:` konstanta dipakai di fungsi sinkron yang dipanggil banyak tempat (#3–4, #68). Penangkal: nilai dikirim
  sebagai parameter; U2 memastikan tidak ada pemakai tertinggal. Membatalkan: per commit kelompok butir.
