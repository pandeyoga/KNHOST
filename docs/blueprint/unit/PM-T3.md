# PM-T3 — Kwitansi ber-rekening dan ber-referensi; status "terverifikasi bank"; rekonsiliasi per rekening lewat kode bayar

| | |
|---|---|
| Gelombang | Modul cara bayar dan rekening |
| Jenis | fitur |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | PK-19, PK-20, PK-21, PM-T2 |
| Menutup temuan | PM-02, PM-04 |
| Keputusan | K-20, K-34, K-35 |
| Standar | §1 (kontrak posting; P1, P3, P5), §2 (2.1, 2.2, 2.4), §3.1 (Z1, Z2), §3.4 (N1, N2, N4, N5), §4 (L1, L4), §5 (D1, D3, D8), §6 |
| Lingkungan uji | keduanya |

## Tujuan

Setiap uang masuk dari pelanggan tercatat masuk ke rekening tertentu, dengan nomor referensi bila PT mewajibkannya.
Kwitansi punya dua tingkat: "Tercatat" (berdasarkan bukti pelanggan) dan "Terverifikasi bank" (sudah cocok dengan
mutasi di rekening yang sama). Rekonsiliasi hanya menawarkan kwitansi rekening itu dan mencocokkan sendiri bila berita
transfer memuat kode bayar yang benar.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`. PK-19, PK-20, dan PK-21 (prasyarat) mengubah berkas yang sama; cek ulang di
`HEAD`. Khususnya PK-20: `POST /api/ar-receipts` sudah menerima `account_id` (kosong → rekening tunggal PT; tidak bisa
ditentukan → 409) dan kas lahir lewat `create_cash`. Unit ini memakai nama field yang sama.

| Fakta | Jangkar |
|---|---|
| Isi permintaan kwitansi: pelanggan, jumlah, `method` bebas, tanggal, catatan, alokasi — tanpa rekening dan tanpa nomor referensi | `backend/routers/ar_receipts.py:28` (`ReceiptPayload`) |
| Kas kwitansi dibuat **tanpa** `account_id`; tunai → `kas_kecil`, selain itu → `kas_besar` | `backend/services/ar_receipt_service.py:56` (`_cash_routing`), `backend/services/ar_receipt_service.py:82` (`cdoc`) |
| Form kwitansi (desktop dan HP) memilih metode; nomor referensi diketik di kolom catatan | `frontend/src/features/crm/ARReceiptModal.jsx:229` (`ar-receipt-method`), `frontend/src/features/crm/ARReceiptModal.jsx:303` (`ar-receipt-notes`) |
| Kandidat cocok sebuah mutasi = kas ber-rekening itu **atau** kas tanpa rekening berjenis kas sama — kwitansi rekening mana pun ikut ditawarkan | `backend/services/bank_recon_service.py:503` (`_book_query`) |
| Skor cocok: nominal, tanggal, nomor referensi di teks kas, kemiripan nama; ambang otomatis dari pengaturan | `backend/services/bank_recon_service.py:443` (`score_pair`), `backend/services/bank_recon_service.py:401` (`_ref_score`), `backend/services/bank_recon_service.py:58` (`CFG_KEYS`) |
| Menautkan mutasi menandai kas `reconciled`; kwitansinya tidak diberi tahu, `account_id` kas tetap kosong | `backend/services/bank_recon_service.py:595` (`_link`), `backend/services/bank_recon_service.py:654` (`_unlink`) |
| Saldo rekening menyerap kas tanpa rekening hanya bila rekening itu satu-satunya di PT untuk jenisnya | `backend/services/bank_service.py:61` (`_txns_for`) |
| Tahan-kirim menghitung "terbayar" dari `paid_total` pesanan, tanpa melihat status kwitansi | `backend/services/dispatch_payment_gate.py:62` (`paid`) |
| Daftar kwitansi hanya mengenal "Posted" dan "Void" | `frontend/src/features/crm/ARReceiptsHistory.jsx:124` (`ar-history-status`) |

## Perubahan

### Data

`ar_receipts` — field baru:

| Field | Tipe | Aturan |
|---|---|---|
| `payment_method_code` | kode kanonik | Dari PM-T1; `method` tetap ditulis sama untuk pembaca lama |
| `account_id`, `account_snapshot` | id + potret `{name, bank_name, account_number}` | Disimpan di kwitansi. Wajib bila ada uang baru (`amount > 0`) dan cara bayar butuh rekening; tunai memakai rekening kas |
| `reference_no` | string | Wajib bila cara bayar ber-`needs_reference` **dan** `payment.wajib_nomor_referensi` menyala |
| `giro_due_date` | `YYYY-MM-DD` | Untuk giro; wajib dengan syarat yang sama |
| `proof_url` | string | Lampiran bukti, opsional |
| `instruction_mismatch`, `mismatch_note` | bool, string | `true` bila rekening penerima ≠ `receiving_account_id` salah satu pesanan yang dialokasi; catatan wajib (≥ 5 huruf) |
| `bank_verified`, `bank_verified_at`, `bank_verified_by`, `bank_line_ids` | bool, ISO, string, daftar | Diisi rekonsiliasi; bawaan `false` |

`bank_statement_lines` — field baru `pay_code_hits`: daftar `{code, order_id, order_number, customer_id}` yang
ditemukan di berita mutasi saat impor. Indeks baru `ar_receipts (entity_id, bank_verified, receipt_date)`.

Skrip baru `scripts/backfill_receipt_accounts.py` (`--dry-run`, idempoten; H3): mengisi `account_id` kas kwitansi lama
dan `account_id` kwitansinya **hanya** bila PT-nya punya tepat satu rekening aktif untuk jenis kas itu; sisanya
didaftar di keluaran untuk diputus orang.

### Server

`ReceiptPayload` (sudah ber-`account_id` sejak PK-20) mendapat `reference_no`, `giro_due_date`, `proof_url`,
`mismatch_note` (semua bawaan kosong). Langkah PERIKSA `create_receipt` (sebelum nomor, reservasi titipan, atau alokasi
— `02` §1) bertambah:

1. `normalize` + `payment_method_service.get` (PM-T1).
2. Rekening: yang dikirim; bila kosong → rekening bawaan (PT, cara bayar) hasil PM-T1; bila tidak ada → rekening tunggal
   PT (aturan PK-20); tidak ketemu → 409 dengan pesan PK-20. Rekening harus milik PT kwitansi, aktif, ber-`purposes`
   `penerimaan_pelanggan`, dan melayani cara bayar itu.
3. Nomor referensi dan jatuh tempo giro menurut tabel Data.
4. Tanda "tidak sesuai instruksi" dan catatannya.

Kas tetap dibuat `create_cash` (PK-20) dengan `account_id` rekening kwitansi; unit ini menambah `counterparty_name` =
nama pelanggan dan keterangan yang memuat nomor referensi serta kode bayar pesanan yang dialokasi. `_cash_routing`
(bila masih tersisa) dihapus. Pembatalan kwitansi ber-`bank_verified: true` ditolak 409.

Rekonsiliasi (`bank_recon_service`):

| Tempat | Perubahan |
|---|---|
| `import_lines` | Mengisi `pay_code_hits` dengan `payment_code_service.find_in_text(berita + referensi)` |
| `_book_query` | Hanya kas ber-`account_id` rekening mutasi. Kas tanpa rekening tetap ditawarkan **hanya** bila `sole_account_id(PT, jenis kas)` = rekening mutasi (aturan yang sama dengan saldo rekening) |
| `score_pair` | Langkah baru paling awal: bila salah satu `pay_code_hits` menunjuk pesanan yang dialokasi kwitansi di balik kas itu → alasan "Kode bayar {kode} cocok dengan pesanan {nomor}". Nominal sama (dalam toleransi) → skor dinaikkan minimal ke ambang otomatis. Nominal berbeda → pasangan tetap layak dengan skor minimal ambang usulan dan alasan "Kode bayar cocok, nominal berbeda {Rp}" — tidak pernah tertaut otomatis |
| `_link`, `_unlink` (bentuk bersyarat hasil PK-21) | Sesudah kas sebuah kwitansi cocok penuh → `bank_verified: true` + waktu, pelaku, id mutasi. Sesudah dilepas → `false`. Bila `customer_balance_service` ada (CR-T2), panggil `refresh` — giro belum cair = kwitansi `giro` yang belum terverifikasi |

Tahan-kirim: `dispatch_payment_gate.evaluate` menghitung "terbayar" menurut `finance.tahan_kirim_dasar_bayar` —
`tercatat` (semua pembayaran, seperti hari ini) atau `terverifikasi` (pembayaran dari kwitansi `bank_verified` dan
kwitansi tunai yang masuk rekening kas).

| Endpoint | Izin | Perubahan |
|---|---|---|
| `POST /api/ar-receipts` | `ar_receipt.create` | Field baru; jawaban memuat `account_snapshot`, `bank_verified`, `instruction_mismatch` |
| `GET /api/ar-receipts?bank_verified=&older_than_days=&method=` | `ar_receipt.view` | Saringan baru; `older_than_days` tanpa nilai memakai `payment.hari_wajar_verifikasi_bank`; kwitansi tunai dan titipan tidak pernah masuk daftar "belum terverifikasi" |
| Kandidat dan daftar mutasi rekonsiliasi (ada) | tetap | Tiap mutasi memuat `pay_code_hits` |

Galat:

| Keadaan | Kode | Pesan |
|---|---|---|
| Rekening tidak bisa ditentukan | 409 | Pesan `create_cash` (PK-20): "Pilih rekening kas/bank untuk transaksi ini. …" — dikeluarkan di langkah PERIKSA, sebelum ada tulisan |
| Rekening milik PT lain | 400 | "Rekening penerima bukan milik PT kwitansi ini." |
| Rekening tidak cocok dengan cara bayar/peruntukan | 400 | "Rekening ini tidak bisa menerima pembayaran pelanggan lewat {nama cara bayar}." |
| Referensi wajib tetapi kosong | 400 | "Nomor referensi wajib diisi untuk {nama cara bayar}." |
| Berbeda dari instruksi tanpa catatan | 400 | "Rekening penerima berbeda dari instruksi bayar pesanan. Isi catatan alasannya." |
| Batal kwitansi terverifikasi | 409 | "Kwitansi sudah terverifikasi bank. Lepaskan pencocokan mutasinya dulu." |

### Pengaturan

Scopes `("global", "entity")`, permission `("cash", "configure")`.

| Field | `payment.wajib_nomor_referensi` | `payment.hari_wajar_verifikasi_bank` | `finance.tahan_kirim_dasar_bayar` |
|---|---|---|---|
| group | `uang-masuk` | `bank` | `uang-masuk` |
| type · default | `bool` · tidak | `int` · 3 (min 0, max 60, hari) | `enum` `tercatat` · `terverifikasi`; bawaan `tercatat` |
| label | "Wajibkan nomor referensi di kwitansi" | "Kwitansi wajar belum terverifikasi selama (hari)" | "Pesanan bayar-dulu boleh dikirim setelah pembayaran" |
| help | "Berlaku untuk cara bayar yang butuh referensi (transfer, giro, QRIS)." | "Kwitansi non-tunai yang lebih lama dari ini tampil di daftar 'Belum terverifikasi'." | "'Tercatat' = cukup ada kwitansi. 'Terverifikasi' = kwitansi harus sudah cocok dengan mutasi bank." |
| impact | "Menyala = kwitansi transfer tanpa nomor referensi ditolak." | "Hanya mengubah isi daftar; tidak menolak apa pun." | "'Terverifikasi' menahan barang sampai mutasi bank dicocokkan." |
| example | "Menyala · transfer tanpa referensi → ditolak" | "3 · kwitansi berumur 5 hari → tampil" | "Terverifikasi · CBD dibayar, mutasi belum cocok → tertahan" |
| risk / requires_reason | `medium` / tidak | `low` / tidak | `high` / ya |
| consumers | `services/ar_receipt_service.py:create_receipt` | `services/ar_receipt_service.py:list_receipts` | `services/dispatch_payment_gate.py:evaluate` |

### Izin dan peran

Tidak ada pasangan baru.

### Layar

- **Form kwitansi** (`ARReceiptModal.jsx`; HP memakai komponen yang sama): di bawah "Cara bayar" — "Rekening penerima"
  (dari `GET /api/bank-accounts/receiving`, terisi dari rekening tujuan pesanan yang dialokasi atau bawaan PT),
  "No. referensi" (bertanda wajib bila pengaturan menyala), "Jatuh tempo giro" (hanya giro), "Bukti (tautan)". Bila
  rekening ≠ instruksi pesanan: peringatan "Tidak sesuai instruksi bayar pesanan {nomor} ({rekening instruksi})" dan
  isian wajib "Catatan alasan". Kolom catatan kehilangan teks bantu "No. referensi / bank...". Konfirmasi menyebut
  nominal, PT, dan rekening (N5). Antrean luring HP: kwitansi tersimpan lama tanpa rekening tetap diterima server
  selama rekening bawaan bisa ditentukan.
- **Riwayat kwitansi** (`ARReceiptsHistory.jsx`): kolom "Rekening" dan "No. referensi"; lencana status **Tercatat**,
  **Terverifikasi bank**, **Tunai**, **Void**; saringan "Belum terverifikasi lebih dari {N} hari"; tanda "Tidak sesuai
  instruksi".
- **Rekonsiliasi Bank**: mutasi yang memuat kode bayar diberi lencana "Kode bayar {kode}"; bila belum ada kwitansinya,
  tombol **Catat kwitansi dari mutasi ini** membuka form kwitansi terisi (pelanggan, pesanan, nominal, rekening mutasi,
  referensi). Cetakan kwitansi (`resolve_ar_receipt`) menambah "Cara bayar", "Rekening", "No. referensi".

## Uji penerimaan

Persiapan: `ent_ksc` punya rekening **A** (BCA, bawaan `transfer`) dan **A2** (Mandiri), keduanya melayani `transfer`;
`ent_kanda` punya **B** (bawaan) saja. Pelanggan P di `ent_ksc`, pesanan S1 bersisa Rp 1.500.000 dengan rekening
tujuan A dan kode bayar `KN-7F3K2`. Ambang dan toleransi rekonsiliasi bawaan.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | Kwitansi `transfer` Rp 1.500.000 untuk S1 tanpa `account_id` | 200; kwitansi dan kasnya ber-`account_id == A` (bawaan `transfer`, walau PT punya dua rekening bank); `bank_verified: false` |
| U2 | B | — | Kwitansi yang sama dengan `account_id: B` | 400 "…bukan milik PT kwitansi ini."; tidak ada kwitansi, `payments[]` S1 tidak bertambah |
| U3 | B | PT uji ketiga dengan dua rekening bank tanpa bawaan; rekening C di `ent_ksc` hanya ber-`purposes: ["gaji"]` | Kwitansi `transfer` tanpa rekening di PT ketiga; kwitansi ke rekening C | 409 "Pilih rekening kas/bank…" tanpa kwitansi dan tanpa alokasi; 400 "Rekening ini tidak bisa menerima…" |
| U4 | B | `payment.wajib_nomor_referensi` menyala pada `ent_ksc` | Kwitansi `transfer` tanpa `reference_no` di `ent_ksc`; lalu di `ent_kanda` | 400; 200 — PT lain tidak berubah |
| U5 | B | — | Kwitansi S1 ke rekening A2 tanpa catatan; lalu dengan `mismatch_note: "Pelanggan salah transfer"` | 400; 200 dengan `instruction_mismatch: true` |
| U6 | B | U1; mutasi Rp 1.500.000 diimpor ke A2 dan ke A | Kandidat mutasi A2; kandidat mutasi A | A2: tidak memuat kas U1; A: memuat |
| U7 | B | U1; mutasi A Rp 1.500.000, berita "TRSF KN-7F3K2 TOKO MAJU", selisih 2 hari | `auto_match` rekening A | `matched: 1`; alasan memuat "Kode bayar KN-7F3K2"; kwitansi `bank_verified: true` dengan `bank_line_ids` terisi |
| U8 | B | U1; mutasi A Rp 1.400.000 berberita sama | `auto_match` | Tidak tertaut; mutasi punya usulan teratas kas U1 dengan alasan "…nominal berbeda Rp 100.000" (1.500.000 − 1.400.000) |
| U9 | B | U7 | Lepas pencocokan mutasi; lalu batalkan kwitansi sebelum dilepas (urutan terbalik pada fixture kedua) | `bank_verified: false`; pembatalan saat masih terverifikasi → 409 |
| U10 | B | Kas lama tanpa `account_id` berjenis `kas_besar` di `ent_ksc` (dua rekening) dan di `ent_kanda` (satu) | Kandidat untuk mutasi A, A2, dan B | Tidak muncul di A maupun A2; muncul di B |
| U11 | B | `finance.tahan_kirim_dasar_bayar` = `terverifikasi` pada `ent_ksc`; pesanan CBD Rp 2.000.000 dibayar kwitansi `transfer` | `dispatch_guard` sebelum dan sesudah mutasinya dicocokkan; pesanan serupa di `ent_kanda` | 409 "…kurang Rp 2.000.000…"; lolos; `ent_kanda` lolos tanpa pencocokan |
| U12 | B | Kwitansi `transfer` berumur 5 hari dan 1 hari, kwitansi `cash` berumur 9 hari; kunci bawaan (3) | `GET /api/ar-receipts?bank_verified=false&older_than_days=` | Hanya kwitansi berumur 5 hari |
| U13 | B | Periode tertutup untuk tanggal kwitansi; lalu jurnal kas dipaksa gagal | `POST` kwitansi; lalu `POST` berhasil dengan jurnal gagal + `repost` | 409 tanpa tulisan apa pun; lalu `gl_status: failed` → setelah `repost` satu kas ber-rekening dan satu jurnal |
| U14 | B | peran uji baku | **Tanpa Acuan** + `ar_receipt.create` dan `ar_receipt.view`: `POST` kwitansi sah; **Manajer Kosong**; **Sopir** | 200; 403; 403 |
| U15 | B | — | Putaran `t1_config.py` untuk tiga kunci | Lulus |
| U16 | B | fixture kas kwitansi lama tanpa rekening di PT berekening tunggal dan di PT berekening ganda | Fungsi isi-ulang dua kali | PT tunggal: `account_id` terisi; PT ganda: tidak diubah dan tercantum di keluaran; putaran kedua tanpa perubahan |
| U17 | A | U1 + mutasi U7 | Dua `auto_match` bersamaan | Satu tautan; `reconciled_amount` kas = 1.500.000; `bank_verified: true` sekali |
| U18 | layar (uji jalan) | Data acuan | Finance mencatat kwitansi dari mutasi berkode, lalu membuka riwayat kwitansi | Form terisi dari mutasi; setelah simpan mutasi tertaut dan kwitansi berlencana "Terverifikasi bank" |

## Langkah kerja

**Serah-terima (a) — kemampuan baru; kandidat rekonsiliasi dan form lama belum disentuh.**

1. `backend/tests_mem/test_PMT3_kwitansi_rekening.py`: U1–U5, U7–U9, U12–U15; merah.
2. Field kwitansi + langkah PERIKSA baru (rekening bawaan, peruntukan, referensi, tanda tidak sesuai instruksi).
3. `pay_code_hits` saat impor; langkah kode bayar di `score_pair`; `bank_verified` di `_link`/`_unlink`; saringan daftar.
4. Tiga kunci pengaturan; cetakan kwitansi.

**Serah-terima (b) — alihkan dan matikan jalur lama.**

5. U6, U10, U11, U16 ditulis; merah.
6. Form mengirim rekening dan referensi; `_book_query` dipersempit; `_cash_routing` dihapus; dasar tahan-kirim; skrip
   isi-ulang.
7. Layar riwayat dan rekonsiliasi; U17 di lingkungan A; U18; gate penuh; laporan memuat contoh angka U1 → U7: kwitansi
   → kas ber-rekening → jurnal → mutasi tertaut → saldo rekening.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (field `ar_receipts`, `bank_statement_lines.pay_code_hits`), `CODEBASE_MAP.md` (skrip isi-ulang),
`memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("tercatat", "terverifikasi bank", "rekening penerima").

## Di luar lingkup

- Satu form pembayaran untuk semua pintu (Meja Finance, Piutang, detail pesanan) → MN-T3; unit ini hanya melengkapi
  form yang ada.
- Tunai di tangan sales sebagai titipan → PM-T4. Pemberitahuan otomatis dari penyedia pembayaran → PM-T5.
- Daur hidup giro tersendiri (diterima → cair → ditolak) di luar status terverifikasi: belum ada unitnya; giro ditolak
  tetap lewat Kasus Keuangan.

## Asumsi dan risiko

- `ASUMSI:` nomor referensi tidak diwajibkan sebagai bawaan (hari ini opsional); rancangan mengusulkan wajib.
- `ASUMSI:` batas "wajar belum terverifikasi" 3 hari — hanya penyaring daftar, pemilik bebas mengubahnya.
- `ASUMSI:` "giro belum cair" (K-20, K-31) = kwitansi giro yang belum terverifikasi bank; tidak ada dokumen giro terpisah.
- `ASUMSI:` kwitansi tunai yang masuk rekening kas dihitung "terbayar" pada dasar `terverifikasi`, karena tidak ada
  mutasi bank untuk dicocokkan.
- `RISIKO:` setelah (b), kas kwitansi lama tanpa rekening di PT berekening ganda tidak lagi muncul sebagai kandidat.
  Penangkal: keluaran skrip isi-ulang menjadi daftar kerja pemilik sebelum (b) dipasang ke PT nyata (H3). Membatalkan
  (b): kembalikan `_book_query` ke bentuk lama; field baru tidak mengganggu jalur lama.
