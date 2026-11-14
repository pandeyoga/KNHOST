# PM-T3 — Kwitansi ber-rekening dan ber-referensi; status "terverifikasi bank"; rekonsiliasi per rekening lewat kode bayar

- Commit awal: `35a1f9a` (worktree kerja, basis B)        - Commit akhir: (a) `569c86a`, (b) `a2c1e19`, cek layar `b62ef45`        - Branch: `claude/nifty-carson-jjx3c8`
- Digabung pelaksana ke HEAD tujuan — lihat "Penggabungan"
- ID ditangani: PM-02, PM-04 (spesifikasi `docs/blueprint/unit/PM-T3.md`)
- Keputusan: K-20, K-34, K-35 · Standar `02` §1 (P1, P3, P5), §2 (2.1, 2.2, 2.4), §3.1 (Z1, Z2), §3.4 (N1, N2, N4, N5),
  §4 (L1, L4), §5 (D1, D3, D8), §6 · Prasyarat PK-19, PK-20, PK-21, PM-T2 (semua di basis; AG-T3 juga)
- Risiko tinggi → dua serah-terima (`00` §8): **(a)** field kwitansi + PERIKSA baru, `pay_code_hits`, langkah kode bayar
  di skor, `bank_verified` di cocok/lepas, saringan daftar, tiga kunci, cetakan kwitansi (+ dasar tahan-kirim, lihat
  Menyimpang 2); kandidat rekonsiliasi dan form lama belum disentuh. **(b)** `_book_query` dipersempit, `_cash_routing`
  dihapus, skrip isi-ulang, form kwitansi / riwayat / rekonsiliasi, uji lapis A U17, dokumen.

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`, dicek di `35a1f9a`)

| Butir | Hasil di basis B |
|---|---|
| `ReceiptPayload` tanpa rekening & referensi (`ar_receipts.py:28`) | Berlaku sebagian, bergeser `:29`: `account_id` sudah ada sejak PK-20; tanpa `reference_no`/`giro_due_date`/`proof_url`/`mismatch_note` |
| Kas kwitansi tanpa `account_id`; `_cash_routing` (`ar_receipt_service.py:56`, `:82`) | **Sebagian tidak berlaku**: PK-20 sudah mengirim rekening (dikirim / rekening tunggal PT) ke `create_cash` (`:88`). `_cash_routing` masih ada `:55`, dipakai `_post_cash_in` `:81`, `create_receipt` `:245`, dan `bootstrap.backfill_ar_cash_postings` `:1093` |
| Form kwitansi memilih metode; referensi diketik di catatan (`ARReceiptModal.jsx:229`, `:303`) | Berlaku, bergeser `:247` / `:325` (placeholder "No. referensi / bank..."); PK-20 menambah isian Rekening `CashAccountField` (`:256`) — rekening per jenis kas, bukan per cara bayar/peruntukan |
| Kandidat = kas ber-rekening itu ATAU kas tanpa rekening berjenis sama (`bank_recon_service.py:503`) | Berlaku, bergeser `:547`; kas tanpa rekening juga lintas PT dalam cakupan pengguna (`_scope_q`), bukan hanya PT rekening |
| Skor nominal/tanggal/referensi/nama (`:443`, `:401`, `:58`) | Berlaku, bergeser `score_pair :487`, `_ref_score :445`, `CFG_KEYS :62` |
| Cocok menandai kas; kwitansi tidak diberi tahu (`:595`, `:654`) | Berlaku, bergeser `_link :639`, `_unlink :689` (bentuk bersyarat PK-21). "`account_id` kas tetap kosong" tidak berlaku lagi untuk kwitansi baru (PK-20) |
| Saldo rekening menyerap kas tanpa rekening hanya di rekening tunggal (`bank_service.py:61`) | Berlaku, bergeser `_txns_for :139`, `sole_account_id :127` |
| Tahan-kirim dari `paid_total` (`dispatch_payment_gate.py:62`) | Berlaku `:62` |
| Riwayat kwitansi hanya "Posted"/"Void" (`ARReceiptsHistory.jsx:124`) | Bergeser `:157`: PK-42 sudah memakai "Tercatat"/"Dibatalkan" berikon; belum ada Rekening/No. referensi/Terverifikasi/Tunai |
| (tambahan) Cetakan `resolve_ar_receipt` | `pdf_resolvers.py:467`: hanya "Metode" (kode mentah) |
| (tambahan) Pemberi kode bayar | `payment_code_service.find_in_text` (PM-T2) siap dipakai; `payment_codes` unik lintas PT |

## PM-02 — Kwitansi tanpa rekening penerima yang benar dan tanpa nomor referensi

- Berlaku di HEAD: sebagian (bukti merah `bukti/PM-T3/a_merah_kode_lama.txt`): transfer tanpa rekening di PT berekening
  bank ganda → 409 walau PT punya rekening bawaan transfer (U1); rekening PT lain → 409 "bukan rekening aktif", bukan 400
  berkalimat (U2); rekening hanya-gaji diterima (U3); tidak ada nomor referensi/tanda instruksi (U4, U5).
- Akar masalah: PK-20 memilih rekening per JENIS kas (tunggal atau dikirim) tanpa melihat cara bayar, peruntukan, dan
  rekening tujuan pesanan (PM-T1/PM-T2); referensi hanya teks bebas di catatan.
- Perubahan perilaku (sebelum → sesudah):
  - **PERIKSA** `ar_receipt_service.periksa_uang_masuk` (sebelum nomor, reservasi deposit, alokasi — `02` §1): cara bayar
    (`payment_method_service.wajib`) → periode → rekening: dikirim → (kosong) rekening tujuan pesanan yang dialokasi bila
    semua pesanan menunjuk rekening yang sama dan rekening itu menerima cara bayar ini → bawaan (PT, cara bayar) PM-T1 →
    rekening tunggal PK-20 → 409 pesan PK-20. Rekening PT lain → 400 "Rekening penerima bukan milik PT kwitansi ini.";
    nonaktif → 409 (PK-20); bukan `penerimaan_pelanggan` / tidak melayani cara bayar → 400 "Rekening ini tidak bisa
    menerima pembayaran pelanggan lewat {nama}." Nomor referensi wajib bila cara bayar `needs_reference` DAN
    `payment.wajib_nomor_referensi` menyala → 400 "Nomor referensi wajib diisi untuk {nama}."; giro: jatuh tempo
    (`YYYY-MM-DD`) wajib dengan syarat sama. Rekening ≠ rekening tujuan salah satu pesanan yang dialokasi → catatan
    ≥ 5 huruf wajib (400 "Rekening penerima berbeda dari instruksi bayar pesanan. Isi catatan alasannya.") →
    `instruction_mismatch: true`.
  - Kwitansi menyimpan `payment_method_code`, `account_id`, `account_snapshot {name, bank_name, account_number}` (D3),
    `reference_no`, `giro_due_date`, `proof_url`, `instruction_mismatch`, `mismatch_note`, `instruction_mismatch_orders[]`,
    `bank_verified false`. Kas tetap lahir dari `create_cash` (PK-20) ke rekening itu, ber-`counterparty_name` (nama
    pelanggan), `reference_no`, keterangan "Penerimaan {no} — {pelanggan} · Ref {ref} · Kode {kode bayar}".
  - (b) `_cash_routing` **dihapus** — jenis kas = jenis rekening penerima; `bootstrap.backfill_ar_cash_postings` (kwitansi
    lama tanpa kas) memakai `is_cash` langsung.
  - Pembatalan kwitansi terverifikasi bank — atau yang kasnya sudah dicocokkan sebagian — → 409 "Kwitansi sudah
    terverifikasi bank. Lepaskan pencocokan mutasinya dulu." (sebelum niat & efek).
  - `GET /api/ar-receipts?bank_verified=&older_than_days=&method=` (berhalaman maupun larik): `false` = belum cocok, tidak
    batal, ber-uang baru, BUKAN tunai/titipan; `older_than_days` tanpa nilai = `payment.hari_wajar_verifikasi_bank` PT
    (bawaan 3); `method` mengenali kata lama (`tunai` = `cash`). Indeks `(entity_id, bank_verified, receipt_date)`.
  - `GET /api/ar-receipts/open-orders` per baris + `receiving_account_id`, `receiving_account`, `payment_code` (bahan form).
  - Cetakan kwitansi baru: "Cara bayar" (nama dari daftar induk), "Rekening", "No. referensi" (+ "Jatuh tempo giro");
    kwitansi lama dicetak seperti dulu (isi bertanda tangan elektronik tidak berubah).
- Status: implemented_pending_review

## PM-04 — Rekonsiliasi menawarkan kwitansi rekening mana pun; kwitansi tidak tahu sudah cocok bank

- Berlaku di HEAD: ya (U7–U10 merah: `bukti/PM-T3/a_merah_kode_lama.txt`, `b_merah_keadaan_a.txt`).
- Akar masalah: jembatan kompatibilitas `_book_query` (kas tanpa rekening berjenis sama ditawarkan ke semua rekening,
  bahkan lintas PT dalam cakupan pengguna); skor tidak mengenal kode bayar; `_link`/`_unlink` hanya menulis kas.
- Perubahan perilaku (sebelum → sesudah):
  - Impor: `bank_statement_lines.pay_code_hits` = kode bayar PT mutasi di berita + referensi (`payment_code_service.
    find_in_text`) `{code, order_id, order_number, customer_id}`. Mutasi lama dihitung di memori saat dibaca.
  - `score_pair` langkah pertama: kode bayar menunjuk pesanan yang dialokasi kwitansi di balik kas → nominal sama (dalam
    toleransi) = skor minimal ambang otomatis, alasan "Kode bayar {kode} cocok dengan pesanan {nomor}"; nominal beda =
    layak dengan skor minimal ambang usulan, alasan "Kode bayar cocok, nominal berbeda {Rp}", `no_auto` → `auto_match`
    tidak pernah menautkannya.
  - `_link` / `_unlink` → `sinkron_verifikasi_kwitansi`: kas kwitansi cocok penuh → `bank_verified: true`,
    `bank_verified_at/_by`, `bank_line_ids` (sekali, syarat `bank_verified != true`); dilepas → `false`. Kait
    `customer_balance_service.refresh` disiapkan (modul CR-T2 belum ada → dilewati).
  - (b) `_book_query` (kini async): hanya kas ber-`account_id` rekening mutasi; kas lama tanpa rekening hanya bila
    `sole_account_id(PT rekening, jenis kas)` = rekening ini dan hanya kas PT itu. `summary` +
    `book_includes_unlinked`.
  - Tahan-kirim: `finance.tahan_kirim_dasar_bayar` = `tercatat` (bawaan, perilaku lama) | `terverifikasi` (baris uang baru
    kwitansi dihitung hanya bila kwitansinya `bank_verified` atau bercara bayar tunai).
- Status: implemented_pending_review

## Pengaturan (tiga kunci, izin `cash.configure`, `("global", "entity")`)

| Kunci | Kelompok › sub-judul | Tipe · bawaan | Pembaca |
|---|---|---|---|
| `payment.wajib_nomor_referensi` | Pembayaran pelanggan › **Kwitansi pelanggan** (baru) | bool · mati · `medium` | `ar_receipt_service.py:periksa_uang_masuk` |
| `payment.hari_wajar_verifikasi_bank` | Bank & uang yang nyangkut › **Kwitansi menunggu cocok bank** (baru; "Mencocokkan mutasi bank" sudah 14 kunci) | int 0–60 hari · 3 · `low` | `ar_receipt_service.py:saringan_verifikasi` |
| `finance.tahan_kirim_dasar_bayar` | Pembayaran pelanggan › Syarat bayar | enum tercatat · terverifikasi · tercatat · `high` + alasan | `dispatch_payment_gate.py:_basis` (dipanggil `evaluate`) |

Label dipendekkan (INV-CFG-TXT T1 ≤ 45 huruf) — lihat "Usulan koreksi berkas unit".

## Uji penerimaan

Berkas: `backend/tests_mem/test_PMT3_kwitansi_rekening.py` (19 uji + contoh angka). Rekening, pengaturan, kwitansi, impor
mutasi, cocok/lepas, batal = ALUR lewat API; pelanggan, pesanan + kode bayar, kas/kwitansi lama = FIXTURE.

| ID | Lapis | Kode lama (B) | Kode baru |
|---|---|---|---|
| U1 | B | merah: 409 "Pilih rekening kas/bank… Sukacita punya 3 rekening Bank." | lulus — 200; kwitansi & kas `account_id` A (bawaan transfer); potret; `bank_verified: false`; kas ber-`counterparty_name`, keterangan memuat KN-7F3K2 |
| U2 | B | merah: 409 "Rekening BCA Penerimaan Kanda bukan rekening aktif Sukacita." | lulus — 400 pesan persis; tanpa kwitansi; `payments[]` S1 kosong |
| U3 | B | merah: rekening hanya-gaji diterima (200) | lulus — PT ketiga 409 "Pilih rekening kas/bank…" tanpa kwitansi/kas/alokasi (layanan); rekening C 400 pesan persis |
| U4 | B | merah: kunci tidak ada di registry | lulus — `ent_ksc` 400 "Nomor referensi wajib diisi untuk Transfer bank."; dengan referensi 200 (masuk keterangan kas); `ent_kanda` 200 tanpa referensi |
| U5 | B | merah: 200 tanpa catatan | lulus — 400 pesan persis; dengan catatan 200 `instruction_mismatch: true`, `instruction_mismatch_orders` = S |
| U6 | B | (tidak berlaku — sudah diperbaiki PK-20: kas kwitansi baru berekening, `_book_query` lama sudah menyaring `account_id`) | lulus di (a) dan (b) — A2 tidak memuat kas U1; A memuat; cocok manual ke A2 → 400 "…bukan milik buku rekening mutasi ini" |
| U7 | B | merah: `KeyError 'pay_code_hits'` | lulus — `pay_code_hits` [KN-7F3K2 → S1]; `auto_match` `matched: 1`; alasan "Kode bayar KN-7F3K2 cocok…"; kwitansi `bank_verified`, `bank_line_ids` = [mutasi] |
| U8 | B | merah (persiapan 409) | lulus — tidak tertaut; usulan teratas kas kwitansi, alasan "…nominal berbeda Rp 100.000", skor ≥ 60; kandidat modal sama |
| U9 | B | merah (bergantung U7) | lulus — lepas → `bank_verified: false`, `bank_line_ids []`; fixture kedua terverifikasi → batal 409 pesan persis, tanpa niat; sesudah dilepas → batal 200 |
| U10 | B | merah di (a): kas lama KSC tampil di A dan A2 (dan di B lintas PT) | lulus — kas lama KSC tidak di A/A2/B; kas lama Kanda hanya di B |
| U11 | B | merah: kunci tidak ada (PUT 400) | lulus — CBD Rp 2.000.000 dibayar transfer: 409 "…kurang Rp 2.000.000…"; sesudah mutasi dicocokkan lolos; Kanda lolos tanpa pencocokan. U11b (tambahan): kwitansi tunai dihitung terbayar |
| U12 | B | merah: 409 persiapan / saringan tidak ada | lulus — `?bank_verified=false&older_than_days=` → hanya 5 hari (larik & berhalaman); `older_than_days=0` → 5 & 1 hari; tunai tidak pernah; `method=tunai` → kwitansi `cash` |
| U13 | B | merah: 409 persiapan | lulus — periode tertutup 409 tanpa kwitansi/kas/alokasi; jurnal dipaksa gagal → `gl_status: failed` → `repost` 200 → 1 kas ber-rekening A + 1 jurnal |
| U14 | B | merah: 409 persiapan | lulus — Tanpa Acuan + `ar_receipt.create/view` 200 (rekening bawaan A); Manajer Kosong 403; Sopir 403 |
| U15 | B | merah: kunci tidak ada | lulus — putaran KF-T8 tiga kunci tanpa temuan |
| U16 | B | merah: fungsi tidak ada | lulus — Kanda (rekening tunggal) terisi + potret kwitansi; KSC (ganda) tidak diubah dan tercantum; putaran kedua `diubah 0`; skrip `--dry-run` tidak menulis, keluaran memuat kas yang perlu diputus |
| U17 | A | — | **ditulis, belum dijalankan** — `backend/tests/test_bp_PMT3_cocok_bersamaan.py` (dua `auto_match` bersamaan → satu tautan, `reconciled_amount` 1.500.000, `bank_verified` sekali) |
| U18 | layar | merah: komponen/isian tidak ada (`bukti/PM-T3/jest_merah_src_lama.txt`, 6/6) | uji komponen jest `pmt3KwitansiRekening.test.js` 6/6 (form terisi dari instruksi/mutasi, peringatan + catatan wajib, referensi wajib, giro, konfirmasi N5, riwayat lencana/kolom/saringan, lencana kode bayar + tombol); **belum diuji jalan** di peramban |
| tambahan | B | merah | daftar mutasi: `pay_code_hits` + `customer_name` + `has_open_receipt` (berubah sesudah kwitansi dicatat); `open-orders` membawa rekening tujuan & kode; cetakan kwitansi baru vs lama |

### Contoh angka (U1 → U7) — dokumen → kas ber-rekening → jurnal → mutasi tertaut → saldo rekening

Kwitansi U1 transfer Rp 1.500.000 untuk S1 (`ent_ksc`, sisa Rp 1.500.000, rekening tujuan A, kode KN-7F3K2), tanpa
`account_id` → rekening A (bawaan transfer). Kas masuk Rp 1.500.000 `account_id` A. Jurnal kas (`test_PMT3_contoh_angka_U1_ke_U7`):

| Akun | Debit | Kredit |
|---|---:|---:|
| 1-1100 Bank (akun kas rekening A) | 1.500.000 | |
| 2-1400 Uang Muka Pelanggan (pesanan fixture belum dikirim → uang muka, aturan KEB-PDPT yang sudah ada) | | 1.500.000 |

Mutasi A Rp 1.500.000 "TRSF KN-7F3K2 TOKO MAJU" (+2 hari) → `auto_match` menautkan → kas `reconciled_amount`
1.500.000 = nominal → kwitansi Terverifikasi bank. Saldo rekening A = saldo awal 0 + U1 1.500.000 + U4 1.234.000 =
**2.734.000**; saldo terekonsiliasi = **1.500.000** (hanya U1 yang cocok mutasi).

`backend/tests_mem`: B **1745 lulus / 2 dilewati / 3 xfail** (`bukti/PM-T3/tests_mem_B.txt`) → (a) **1761 / 2 / 3** (+13 uji
PM-T3 (a), +3 putaran KF-T8 untuk tiga kunci baru) → (b) **1767 / 2 / 3** (+6 uji (b); salinan diuji sebelum uji contoh
angka ditambahkan — berkas akhir 20 uji PM-T3, 20/20 lulus di W → 1768).

## Uji lama yang disesuaikan (perilaku sengaja berubah)

| Uji | Sebab | Penyesuaian |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` U04 | tiga kunci baru berizin `cash.configure` | `+ PMT3_KUNCI` (= 3) di jumlah katalog; U02 tetap |
| `tests_mem/test_KFT4_registry.py` U4 | dua kunci baru di "Pembayaran pelanggan" | `+ PMT3_PEMBAYARAN_PELANGGAN` (= 2) |
| `frontend/src/features/settings/config/configKeyIndex.json` | kunci baru | dibangkitkan ulang (`gen_config_key_index.py`) |
| jest `features/__tests__/phase4R1.test.js` (gagal dimuat lokal: `@radix-ui` — dijalankan dengan tiruan KNSelect/KNDatePicker `p13_radix_stub.js`) | simpan kwitansi kini minta konfirmasi N5; kas wajib rekening penerima (daftar `/bank-accounts/receiving`) | tiruan `askConfirm → true`; fixture satu rekening penerima; isi POST + `account_id` |

## Menyimpang dari blueprint

1. **Rekening bawaan server bila tidak dikirim**: rekening tujuan pesanan yang dialokasi (bila semuanya menunjuk satu
   rekening yang menerima cara bayar itu) lebih dulu, baru bawaan PT untuk cara bayar, lalu rekening tunggal. Spesifikasi
   langsung ke bawaan PT; form-nya sendiri "terisi dari rekening tujuan pesanan". Tanpa ini kwitansi antrean luring HP
   lama dan kartu kwitansi asisten (AG-T3, tanpa `account_id`) untuk pesanan berinstruksi rekening non-bawaan akan selalu
   400 "tidak sesuai instruksi". U1 tetap sama (A = bawaan = rekening tujuan S1).
2. **Dasar tahan-kirim dipasang di (a)**, bersama kuncinya (langkah 4 spesifikasi), bukan di (b) langkah 6: penjaga
   `audit_config_wiring --strict` menolak kunci tanpa pembaca nyata. Bawaan `tercatat` = perilaku lama, jadi (a) tetap
   "jalur lama belum disentuh". U11 ditulis di (b) sesuai spesifikasi; merahnya dibuktikan di B (kunci tidak ada).
3. **Pembaca kunci tahan-kirim** didaftarkan `dispatch_payment_gate.py:_basis` (dipanggil `evaluate`): penjaga
   `audit_config_wiring` memeriksa badan fungsi yang disebut.
4. **Label kunci dipendekkan** (INV-CFG-TXT T1 ≤ 45 huruf): "Kwitansi wajar belum terverifikasi selama (hari)" (48) →
   "Kwitansi wajar belum terverifikasi (hari)"; "Pesanan bayar-dulu boleh dikirim setelah pembayaran" (51) →
   "Bayar-dulu boleh dikirim setelah pembayaran". Dua sub-judul baru (lihat tabel Pengaturan).
5. **Lencana "Void" → "Dianulir"** (`docStatusLabel("void")`; glosarium KN_32 §3: Void → Anulir).
6. **Batal kwitansi** juga ditolak bila kasnya sudah dicocokkan **sebagian** (`reconciled_amount > 0`, belum penuh) —
   pesan sama; tanpa ini baris mutasi tercocok menunjuk kas yang dibatalkan.
7. **Referensi/jatuh tempo giro hanya untuk uang baru** (`amount > 0`): kwitansi deposit saja tidak punya bukti transfer.
   Pesan giro (tidak ada di spesifikasi): "Jatuh tempo giro wajib diisi untuk {nama}." / "Jatuh tempo giro harus berupa
   tanggal yang sah (tahun-bulan-tanggal)."
8. **Kode bayar cocok mengabaikan jendela tanggal** (kode = bukti terkuat); nominal beda → `no_auto`. Kode di berita yang
   milik PT lain diabaikan (N2).
9. **`pay_code_hits` mutasi lama** dihitung di memori saat dibaca, tidak ditulis (bukan migrasi data).
10. **Isian tambahan**: `instruction_mismatch_orders[]` (potret instruksi yang tidak diikuti, D3); `pay_code_hits[].
    customer_name/has_open_receipt` di daftar mutasi (tombol "Catat kwitansi" hanya bila pesanan belum punya kwitansi
    yang menunggu dicocokkan); `open-orders` + rekening tujuan & kode; `summary.book_includes_unlinked` (teks kartu "Buku"
    kini benar: kas tanpa rekening hanya terhitung di rekening tunggal PT).
11. **Cetakan**: baris baru hanya untuk kwitansi ber-`payment_method_code` (kwitansi baru); kwitansi lama tidak berubah
    supaya hash tanda tangan elektroniknya tetap.
12. **Skrip isi-ulang**: bawaan = lapor (sama dengan `--dry-run`), `--terapkan` menulis (pola PM-T1); logika di
    `ar_receipt_service.isi_rekening_kwitansi_lama` (diuji U16). **Tidak dijalankan** ke database mana pun (H3).
13. **Konfirmasi N5** di form kwitansi (`askConfirm`, "Catat pembayaran Rp … ? Dari {pelanggan} untuk {PT}, masuk ke
    {rekening}.") — dulu tanpa konfirmasi.
14. **Dari mutasi**: sesudah kwitansi dari "Catat kwitansi dari mutasi ini" tersimpan, layar menautkan mutasi ke kas
    kwitansi itu (`POST …/lines/{id}/match`, satu langkah klien) sehingga kwitansi langsung Terverifikasi bank (U18).

### Usulan koreksi berkas unit

- Pengaturan, baris label: `"Kwitansi wajar belum terverifikasi selama (hari)"` → `"Kwitansi wajar belum terverifikasi (hari)"`;
  `"Pesanan bayar-dulu boleh dikirim setelah pembayaran"` → `"Bayar-dulu boleh dikirim setelah pembayaran"`; consumers
  `services/dispatch_payment_gate.py:evaluate` → `services/dispatch_payment_gate.py:_basis`.
- Layar, riwayat: "lencana status **Tercatat**, **Terverifikasi bank**, **Tunai**, **Void**" → "… **Tunai**, **Dianulir**".
- Keadaan sekarang, baris kas: "Kas kwitansi dibuat **tanpa** `account_id`" → "Kas kwitansi berekening sejak PK-20 (dikirim
  atau rekening tunggal PT per jenis kas); `_cash_routing` masih menentukan jenis kas dari cara bayar".
- Uji U6: tambahkan "(lulus sejak PK-20 untuk kwitansi baru; yang diuji (b) adalah kas lama tanpa rekening = U10)".

## Asumsi

- Spesifikasi: referensi tidak wajib (bawaan mati); batas wajar 3 hari; "giro belum cair" = kwitansi giro belum
  terverifikasi (dipakai bila CR-T2 lahir); kwitansi tunai ke rekening kas dihitung "terbayar" pada dasar terverifikasi.
- Bawaan (`00` §4.1): dasar `terverifikasi` hanya menyaring baris **uang baru kwitansi** (`kind` kas); baris deposit,
  titipan bank, saldo kredit, nota kredit, hapus sisa, kasus tetap dihitung (bukan uang yang menunggu mutasi bank);
  baris kas lama tanpa `receipt_id` dihitung hanya bila bercara bayar tunai.
- Kwitansi tunai untuk pesanan berinstruksi transfer = "tidak sesuai instruksi" (bunyi spesifikasi) → catatan wajib.

## Cek layar

Dari kode (integrator memotret 1280/1024/390 px). Token `kn-*`, `text-fs-12`, tanpa hex/`text-[Npx]` baru
(`verify_ui_standard` identik B).

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati beralasan | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong/0 |
|---|---|---|---|---|---|---|---|---|
| Form kwitansi (`crm/ARReceiptModal` + `ReceiptPaymentFields`; HP memakai komponen sama) | — (isian) | badan `FormModal` baku | judul pop-up tetap | "Simpan Pembayaran" mati → alasan di kaki samping tombol ("Pilih rekening penerima.", "Isi nomor referensi (wajib untuk …).", "Isi jatuh tempo giro.", "Isi catatan alasan — …", "Belum ada rekening penerimaan …") | peringatan instruksi = ikon segitiga + teks + `bg-kn-warning-soft` | rekening ≤ belasan (pilihan biasa); satu rekening → terkunci + "Satu-satunya rekening …" | — | daftar rekening kosong = satu kalimat; gagal muat = peringatan, simpan tidak dimatikan |
| Riwayat Pembayaran (`crm/ARReceiptsHistory`) | 10 kolom, `data-table head-wrap` dalam `table-wrap`; kolom aksi `col-sticky-end`; "Rekening" bertumpuk (cara bayar / rekening / lencana) supaya tidak menambah 3 kolom | `section-head` + `section-body` | judul + muat ulang saja; saringan di bilah alat (bukan kepala) | — | Tercatat (jam) · Terverifikasi bank (lencana centang) · Tunai (uang kertas) · Dianulir (larangan) · "Tidak sesuai instruksi" (segitiga) = `status-pill` ikon+teks+token | kotak cari + centang "Belum terverifikasi lebih dari {N} hari" | — | kosong saringan = kalimat sendiri ("Tidak ada kwitansi non-tunai yang menunggu …") |
| Rekonsiliasi Bank (`finance/bank/ReconLinesTable`, `BankReconciliationView`) | jumlah kolom TIDAK bertambah: lencana & tombol di sel Keterangan (lebar 260 px, tombol `btn-sm whitespace-nowrap`) | tetap | tetap | "Catat kwitansi dari mutasi ini" mati di mode Semua PT → alasan ditulis di sampingnya | "Kode bayar {kode}" = ikon # + teks + `bg-kn-special-soft` | cari baris sudah ada | tombol hanya bila `can(ar_receipt.create)` (prop `user` dari `AppViewRouter`) | kartu "Buku": "termasuk kas lama tanpa rekening" hanya bila memang terhitung |

Catatan: sel lama `ReconLinesTable` masih memakai warna hex (sebelum unit ini, tidak diubah).

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di `b62ef45` — satu gate untuk
PM-T3 (a/b), PK-41 (a/b), PY-T1 (a/b), PK-33 dan cek layar `b62ef45`:

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, **`guard:atomic_claim`** — PK-33) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

"Tidak dijalankan" tambahan: `guard:atomic_claim SELF-TEST (… 10 kasus)` — ganti label menjadi 64 kasus oleh PK-33 (uji-dirinya
hijau). Kuitansi: `bukti/PM-T3/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan dan lingkungan A

- Dipasang integrator di atas `976aaca` dalam satu rantai (worktree bantu, lalu dipetik ke cabang): PM-T3 (a) `569c86a`
  · (b) `a2c1e19`, PK-41 (a) `bb0dfcd` · (b) `6093baa`, PY-T1 (a) `e980399` · (b) `64143aa`, PK-33 `6943fb7`, cek layar
  `b62ef45`. Bentrok yang diselesaikan integrator: KN_32 (§9.16 = PK-41, §9.17 = PY-T1), `CODEBASE_MAP.md` (dibangkitkan
  ulang); berkas lain tergabung tiga arah tanpa bentrok. Rantai PM-T3+PK-41+PY-T1: tests_mem **1905 lulus / 2 / 2**, jest
  **957** (35 suite gagal dimuat `cmdk`/`@radix-ui`, sama); penjaga statik = garis dasar kecuali `verify_to_list_bound`
  6 → 5 (PK-41); `verify_atomic_claim` sesudah PK-33 **160/0** (inventaris tetap 123 baris — tidak ada endpoint
  multi-koleksi baru dari PM-T3/PK-41/PY-T1), uji-diri 64 kasus hijau.
- Lingkungan A sesudah `restore_demo` dengan kode baru: **29 dari 29** indeks wajib beres; lapis A
  `test_bp_PK14_indeks_wajib.py` 9 lulus.
- Lapis A **U17** `tests/test_bp_PMT3_cocok_bersamaan.py`: **1 lulus**.
- `scripts/backfill_receipt_accounts.py` mode lapor di data acuan: 0 kas bisa diisi otomatis, 0 perlu diputus orang
  (`bukti/PM-T3/pmt3_backfill_lapor.txt`) — data nyata tetap H3.
- Cek layar 1024 px: form Catat Pembayaran (rekening penerima terkunci dengan alasan tertulis, No. referensi, Bukti) rapi;
  Rekonsiliasi Bank — enam kartu sebaris memotong angka "Rp 100.000.0" → 3+3 sampai 2xl + `kpiValueParts` (`b62ef45`)
  (`bukti/PM-T3/cek_*.png`).

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A dipakai integrator). Lingkungan B / statik:

| Pemeriksaan | B (`35a1f9a`) | (a) | (b) |
|---|---|---|---|
| `tests_mem` | 1745 / 2 / 3 xfail | 1761 / 2 / 3 | 1767 / 2 / 3 (berkas akhir +1 = 1768) |
| jest penuh (35 suite gagal dimuat `cmdk`/`@radix-ui`, sama) | 898 lulus · 111 suite | — | **904 lulus · 112 suite** (+6 `pmt3KwitansiRekening`) |
| `hitung_penjaga.sh` | auth 27 · ui 13 · i18n 103 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 | identik | identik |
| `verify_role_gate_ui` / `verify_payment_vocab` / `verify_permission_checked` | 31/0 · — · — | — | 31/0 · 1795/0 · 603/0 |
| `verify_posting_coverage` / `verify_cash_single_door` | — | 138/0 · 716/0 | 138/0 · 716/0 |
| `verify_config_fallback` (+`--entity`) / `verify_config_text` | — | 156/0 · 156/0 · 3248/0 | 156/0 · 156/0 · 3248/0 |
| `audit_config_wiring --strict` (salinan berjalur) · `check_nav_map` · `verify_access_catalog_nav` | — | hijau | hijau · PASS · 0 |
| `gen_config_key_index --check` · `verify_codebase_map` | — | selaras · PASS | selaras · PASS |

## Penggabungan

- HEAD tujuan: **`976aaca`** (`/home/user/KNHOST`, dibaca saja), worktree T `scratchpad/wt22`. HEAD maju tiga kali selama
  uji: digabung dulu ke `0562d29` (di atas B: STATUS, AG-T3 cek layar, PK-43; 1786 / 2 / 3 di T, HEAD murni 1763) → diulang
  ke `ba3198f`/`0616042` (PK-25, KM-T1 (a)+(b), PK-32 (a)+(b), AG-T3 pop-up, laporan AG-T3/PK-43, uji lapis A PK-25) →
  `976aaca` (cek layar PK-25/PK-32: empat berkas layar kasus/amandemen, tidak ada berkas unit ini — T dipindah dengan
  berkas gabungan yang sama, peta kode dibangkitkan ulang, jest & penjaga statik diulang; `tests_mem` dari `0616042`
  berlaku karena tidak ada perubahan server/uji).
- **(a) tergabung** — `scratchpad/PM-T3_a_merged/` (`FILES.txt` 15 berkas, `BASIS.txt` = `976aaca…`; digabung di `0616042`, sah juga di `976aaca`) dari keadaan (a)
  `scratchpad/PM-T3_a_state/` (`BASIS.txt` = `35a1f9a…`): 6 berkas sama di B dan HEAD → disalin, 1 berkas baru; 4 digabung tiga arah
  otomatis (`config_registry.py` — impor katalog KM-T1; `indexes.py` — indeks KM-T1/PK-25; `bank_recon_service.py` —
  `holding_refunded` bersyarat PK-25; `configKeyIndex.json`); **bentrok 3, kedua perilaku dipertahankan**:
  - `backend/services/dispatch_payment_gate.py` — PK-32 menambah tagihan tambahan ke nilai pesanan (`extra_billing_lines`
    → `_order_grand_total`) tepat di atas baris `paid` yang diubah unit ini: hasil = nilai tagihan PK-32 lalu
    `paid_recorded` + dasar terbayar PM-T3 (`paid = min(tercatat, terverifikasi)` bila dasar `terverifikasi`).
  - `backend/tests_mem/test_KFT1_izin_pengaturan.py` — `KMT1_KUNCI = 4` (KM-T1) dan `PMT3_KUNCI = 3` keduanya; jumlah
    U04 `… + AGT3_KUNCI + KMT1_KUNCI + PMT3_KUNCI`.
  - `ENTITY_REGISTRY.md` — field `ar_receipts.dup_decision` (PK-25) dan field PM-T3 keduanya.
  - `CODEBASE_MAP.md` (hasil pembangkit) dibangkitkan ulang; `configKeyIndex.json` dibangkitkan ulang (selaras).
  `tests_mem` (a) tergabung (salinan HEAD `0616042` + berkas (a)): **1843 / 2 / 3** (= HEAD murni 1827 + 13 + 3) (`bukti/PM-T3/tests_mem_a_merged.txt`).
- **(b) tergabung di T** — 28 berkas: 12 sama di B dan HEAD → disalin dari W; 7 digabung tiga arah otomatis
  (`config_registry.py`, `indexes.py`, `bank_recon_service.py`, `configKeyIndex.json`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`,
  `frontend/src/AppViewRouter.jsx`, `memory/PRD.md`); 3 bentrok diselesaikan sama seperti (a) (`dispatch_payment_gate.py`,
  `test_KFT1_izin_pengaturan.py`, `ENTITY_REGISTRY.md`); 5 berkas baru; `CODEBASE_MAP.md` dibangkitkan ulang.
  `access_modules.py` tidak berubah (fixture akses tidak perlu); hitungan PR-T9 dan indeks wajib PK-14 tidak disentuh.
- Interaksi dengan unit yang baru digabung (diperiksa, tidak diubah): PK-25 "giro ditolak → batalkan kwitansi" memanggil
  `void_receipt` — giro ditolak tidak pernah terverifikasi bank, jadi penolak 409 baru tidak menghalanginya; KM-T1
  `incentive_facts` menandai `giro_uncleared` "sampai tanggal cair tersedia (PM-T3)" — PM-T3 menyediakan
  `ar_receipts.bank_verified` sebagai tanda cair (ASUMSI K-20/K-31), pemakaiannya di fakta insentif belum disambung
  (berkas milik KM-T1; lihat "Yang perlu direview").
- Angka di T: `tests_mem` HEAD murni (`0616042`) **1827 / 2 / 3** → T **1850 / 2 / 3** (+20 uji PM-T3, +3 putaran KF-T8);
  jest penuh HEAD murni (`0616042`) **928 lulus · 115 suite** → T (`976aaca`) **934 · 116** (+6 `pmt3KwitansiRekening`), 35 suite gagal dimuat di keduanya (himpunan
  identik; `cmdk`/`@radix-ui`). `hitung_penjaga.sh` **identik** HEAD murni vs T (`bukti/PM-T3/penjaga_H.txt`,
  `penjaga_T.txt`); `verify_role_gate_ui` 31/0; `verify_config_fallback` 157/0 dan `--entity` 157/0; `verify_config_text`
  3276/0; `verify_payment_vocab` 1810/0; `verify_access_catalog_nav` 0 temuan; `verify_permission_checked` 606/0;
  `verify_posting_coverage` 133/0; `verify_cash_single_door` 725/0; `audit_config_wiring --strict` hijau dan
  `check_nav_map.py` PASS (salinan berjalur T).

## Hambatan lingkungan

- Lingkungan A tidak dipakai (brief): U17 ditulis saja; gate belum; U18 belum diuji jalan; skrip isi-ulang tidak
  dijalankan (mode lapor pun tidak — H3).
- Jest: 35 suite lama gagal dimuat (`@radix-ui` lewat `cmdk`); `phase4R1`/`uatV3S2Cbd` dijalankan lokal dengan tiruan
  KNSelect/KNDatePicker (tidak ikut berkas): B 16/16, (b) 16/16.
- Mesin uji sangat sibuk (beberapa agen paralel): `tests_mem` penuh ±26 menit per putaran.

## Titik henti (H3) dan yang perlu direview

- **H3 — kas kwitansi lama tanpa rekening**: sesudah (b), kas lama tanpa `account_id` di PT berekening ganda tidak lagi
  muncul sebagai kandidat rekonsiliasi rekening mana pun. Sebelum (b) dipasang ke PT nyata jalankan (keputusan pemilik):
  `python scripts/backfill_receipt_accounts.py` (lapor) → daftar "Perlu diputus orang"; `--terapkan` hanya mengisi PT
  berekening tunggal. Kueri baca-saja untuk data acuan:
  `db.cash_transactions.countDocuments({ref_type: "ar_receipt", status: {$ne: "void"}, $or: [{account_id: {$exists: false}}, {account_id: {$in: [null, ""]}}]})`.
- `bootstrap.backfill_ar_cash_postings` (saat server menyala) masih membuat kas TANPA rekening untuk kwitansi lama yang
  belum punya kas (sebelum P0-1) — perilaku lama dipertahankan (hanya `_cash_routing` diganti `is_cash`); kas itu kini
  hanya terlihat di rekening tunggal PT. Usul: matikan atau alihkan ke `create_cash` di unit data (H3).
- Kwitansi **tunai** untuk pesanan berinstruksi transfer wajib bercatatan alasan (bunyi spesifikasi) — sales HP akan
  diminta alasan saat menagih tunai pesanan berinstruksi transfer. Bila tidak diinginkan: kecualikan cara bayar tunai.
- Rekening bawaan server = rekening tujuan pesanan (Menyimpang 1).
- Tiga kunci berizin `cash.configure` (Finance ikut bisa mengubah, sama dengan PM-T1/PM-T2).
- KM-T1 `incentive_facts.collection_rows`: `giro_uncleared` kini bisa dibaca dari `ar_receipts.bank_verified` (kwitansi giro
  belum terverifikasi = giro belum cair); fakta dibangun ulang per pesanan, jadi perubahan status kwitansi perlu memicu
  `sync`/`rebuild` pesanannya — disambung di unit KM-T1 lanjutan / CR-T2.
- `bank_verified` turunan dari angka kas (`reconciled_amount`) — belum ada invarian `verify_data_integrity` untuknya (D2);
  pembangun ulangnya = `sinkron_verifikasi_kwitansi([kas])`.
- AG-T3: kartu kwitansi tetap lewat `POST /api/ar-receipts`; isian kartu tidak menyediakan rekening/referensi — bila PT
  menyalakan `payment.wajib_nomor_referensi`, kartu kwitansi transfer akan gagal 400 (pesan pintu) sampai isian kartu
  ditambah (di luar lingkup).

Status: implemented_pending_review.
