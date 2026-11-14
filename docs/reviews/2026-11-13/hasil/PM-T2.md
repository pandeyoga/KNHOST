# PM-T2 — Pesanan menyimpan cara bayar dan rekening tujuan; dokumen mencetak instruksi bayar berkode

- Commit awal: `b95bd0d` (dikerjakan) · digabung pelaksana di atas `f05d8da`        - Commit: `3017c77` · uji lapis A `5097cda` · cek visual daftar pesanan `73314a8`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PM-01
- Keputusan: K-34 (rekening penerimaan per PT = data master), K-35 (tanpa penyedia pembayaran; VA/QRIS = PM-T5 `tahan`,
  tidak disentuh) · Standar `02` §2 (2.1, 2.2, 2.4), §3.1 (Z1, Z2), §3.4 (N1, N2, N4), §4 (L1, L4, L6), §5 (D1, D3, D7,
  D9), §6 · Risiko sedang (satu serah-terima) · Prasyarat PM-T1 (ada di HEAD), KP-T6 (ada di HEAD → token
  `{{rekening_bank}}` diganti penyedianya)

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca di `3132cc4`; dicek di `b95bd0d`)

| Butir | Hasil |
|---|---|
| Isi permintaan pesanan hanya termin | Berlaku, bergeser: `schemas.py:540` (dari 533) |
| Pesanan menyimpan termin + `payment_status`, tanpa rekening | Berlaku, bergeser: `routers/sales_orders.py:649` (dari 619) |
| Konfirmasi Pesanan & Faktur mencetak "Termin Bayar"/"Status Bayar" tanpa bank | Berlaku: `pdf_resolvers.py:275/295` (`resolve_sales_order`), `:1037/1054` (`resolve_invoice`) |
| Rekening hanya bisa diketik di naskah penutup per jenis dokumen | **Sebagian bergeser**: KP-T6 sudah menambah lapisan PT (`pdf_templates.entity_id`) dan token `{{rekening_bank}}` (penyedia "tepat satu rekening bank aktif PT"); `closing_note` `pdf_service.py:41`, `get_template_cfg` `:228` |
| Kop per PT tanpa bank | Berlaku: `pdf_service.py:417` (`get_branding`, kini dari Profil PT — KP-T6) |
| Bagian dokumen yang bisa dimatikan di konfigurasi templat | Berlaku, bergeser: `pdf_service.py:46` (`sections`) |
| Checkout hanya termin; keranjang HP memakai komponen yang sama | Berlaku: `CheckoutDrawer.jsx:423` (`payment-term-select`), `MobileCart.jsx:115` (`CheckoutDrawer` yang sama) |
| Override pesanan enam field kepala | Berlaku: `so_override_service.py:21` (`HEADER_LABEL`) |
| Kirim dokumen lewat WhatsApp | Berlaku: `delivery_service.py:78` (`send_whatsapp`, dari 59) — tidak diubah (lihat Menyimpang 9) |
| (tambahan) Pembuat pesanan internal | `routers/special_orders.py:1401` (konversi pesanan khusus) dan `services/return_replacement_service.py:145` (pengganti retur) memanggil `create_order` tanpa cara bayar → pengaturan "wajib" dibatasi ke checkout (Menyimpang 3) |
| (tambahan) Jalur konfirmasi lain | `special_order_phase2.py:820` (SO pesanan khusus dikonfirmasi sistem) dan `routers/sample_orders.py:231` (sample) tidak lewat `confirm_core` → tidak melahirkan kode (sesuai spesifikasi: kait di `confirm_core`) |
| (tambahan) CR-T2 | `services/billing_schedule_service.py` belum ada di HEAD → `ensure_for_line` ditulis dan diuji sebagai fungsi, belum dikaitkan |

## PM-01 — Pelanggan tidak menerima rekening tujuan dan kode bayar dari master

- Berlaku di HEAD: ya — `SalesOrderCreate` tanpa cara bayar/rekening, dokumen tanpa rujukan bank, tidak ada kode bayar
  (23/23 uji baru merah di kode lama, `bukti/PM-T2/tests_mem_PMT2_merah_kode_lama.log`).
- Akar masalah: pesanan hanya menyimpan termin (KAPAN dibayar); KE MANA dan DENGAN KODE APA ditulis sales di luar sistem
  atau diketik di naskah templat yang berlaku untuk semua pesanan — tidak bisa dicocokkan dengan mutasi bank.
- Perubahan perilaku (sebelum → sesudah):
  - **Pesanan** (`sales_orders`): field baru `payment_method_code` (kanonik / `""`), `receiving_account_id`,
    `receiving_account` (potret `{bank_name, account_number, holder_name}`, D3), `payment_code`. `create_order`
    memeriksa SEBELUM harga dihitung, nomor diambil, dan roll direservasi (`payment_code_service.resolve_destination`):
    cara bayar kosong → keduanya kosong (atau 400 "Pilih cara bayar untuk pesanan ini." bila
    `payment.wajib_cara_bayar_di_pesanan` menyala untuk PT itu); kode/alias dinormalkan lewat daftar induk PM-T1 (aktif,
    arah `masuk`; pesan PM-T1); cara bayar ber-rekening bank tanpa rekening → rekening bawaan (PT, cara bayar) PM-T1;
    rekening terisi → milik PT pesanan (400 "Rekening tujuan bukan milik PT pesanan ini."), aktif, peruntukan
    penerimaan pelanggan, melayani cara bayar itu (400 "Rekening ini tidak bisa menerima pembayaran pelanggan lewat
    {nama}."). Dulu field itu dibuang diam-diam.
  - **Kode bayar** (`payment_codes`, `pyc_`, `services/payment_code_service.py`): `{awalan}-{5 karakter}` dari
    `23456789ABCDEFGHJKLMNPQRSTUVWXYZ` (`secrets`), unik LINTAS PT (indeks wajib `uq_pay_code`), satu per (pesanan,
    baris) (`uq_pay_code_line`), tabrakan → ulang ≤ 5 kali (`KodeBayarError` sesudahnya). `ensure_for_order` (idempoten)
    dipanggil `confirm_core` SEBELUM WhatsApp otomatis "confirmed" (dokumen terkirim sudah memuat instruksi); pesanan
    bayar-dulu (termin `type: cash` atau `dp_percent > 0`) → satu kode, `amount` = nilai × persen (tunai 100 %, DP50
    50 %); tempo → tanpa kode. `ensure_for_line(plan, line)` untuk jadwal tagihan CR-T2 (baris `dp` memakai ulang kode
    pesanan; baris mendapat `pay_code`). `find_in_text` (awalan 2–4 huruf, pemisah opsional, huruf kecil diterima) untuk
    PM-T3. Kegagalan kait konfirmasi dicatat, pesanan tetap terkonfirmasi.
  - **Instruksi bayar**: `GET /api/sales-orders/{id}/payment-instruction` (`order.view` + `assert_entity_access` +
    `sales_ownership.assert_may_open`) → `{order_number, method_name, account, items, text, note}`; teks lima baris
    persis spesifikasi, blok dipisah satu baris kosong. Konfirmasi Pesanan dan Faktur: kotak "Instruksi Pembayaran" di
    bawah total (`pdf_engine` `.payins`), bagian templat baru `sections.payment_instruction` (bawaan tampil, bisa
    dimatikan per jenis dokumen). Blok hanya bila cara bayar ber-rekening bank DAN rekening tujuan
    `show_on_documents: true` (aturan sama untuk cetak, salin, dan teks WhatsApp).
  - **Token `{{rekening_bank}}`** (KP-T6): potret rekening tujuan pesanan → rekening bawaan `transfer` PT → kosong.
    Dulu "tepat satu rekening bank aktif" (rekening bank satu-satunya kini otomatis bawaan transfer lewat nilai awal
    PM-T1, jadi hasil lama tetap).
  - **Override** (`so_override_service`): `HEADER_LABEL` + "Cara bayar", "Rekening tujuan", diperiksa bersama lewat
    `resolve_destination`; cara bayar diganti tanpa memilih rekening → bawaan cara bayar baru; amandemen menulis nama
    ("Mandiri 140-00-7777 a.n. …"), bukan kode/id. `override-context` menambah `payment_methods` + `receiving_accounts`
    (per cara bayar, tanpa saldo).
  - **Pengaturan** (kelompok `uang-masuk` = "Pembayaran pelanggan" › "Syarat bayar", izin `cash.configure`):
    `payment.wajib_cara_bayar_di_pesanan` (bool, bawaan mati, global+PT, dibaca layar checkout semua sales) dan
    `payment.kode_bayar_awalan` (teks "KN", hanya global, format baru `kode_huruf` = 2–4 huruf besar; lapisan PT → 400).
  - **Layar**: checkout (desktop & HP) "Cara bayar" + "Rekening tujuan" (`CheckoutPaymentDestination`); detail pesanan
    kartu cara bayar/rekening + "Instruksi Pembayaran" + **Salin instruksi bayar** (`OrderPaymentInstructionCard`); form
    override dua isian; Desainer PDF bagian "Instruksi pembayaran (rekening tujuan & kode bayar)".
- Berkas berubah:

| Berkas | Isi |
|---|---|
| `backend/services/payment_code_service.py` | Baru — validasi tujuan, kode bayar, `find_in_text`, `instruction`, blok dokumen, penyedia token |
| `backend/schemas.py` | `SalesOrderCreate.payment_method_code`, `receiving_account_id` |
| `backend/routers/sales_orders.py` | `create_order`: periksa tujuan sebelum reservasi; simpan field; jejak audit |
| `backend/services/so_lifecycle_service.py` | `confirm_core` → `ensure_for_order` sebelum WhatsApp otomatis |
| `backend/routers/payment_methods.py` | `GET /api/sales-orders/{id}/payment-instruction` |
| `backend/services/so_override_service.py`, `backend/routers/so_override.py` | Dua field kepala + pilihan di konteks override |
| `backend/services/pdf_resolvers.py`, `pdf_service.py`, `pdf_engine.py` | Blok `payment_instruction` (SO, faktur), bagian templat, kotak cetak, keluar dari hash e-sign, penyedia token |
| `backend/config_catalog_payment.py`, `backend/config_registry.py` | Dua kunci; format nilai `kode_huruf` |
| `backend/indexes.py`, `backend/entity_scope.py`, `scripts/verify_contract.py`, `backend/services/export_registry_more.py` | Koleksi `payment_codes`: indeks (2 wajib unik), SCOPED, kontrak, dikecualikan dari Pusat Export (beralasan) |
| `backend/access_modules.py` | Tab "Aturan Keuangan & Pajak" terbuka juga bagi pemegang `cash` (aturan KF-T1 U14) |
| `scripts/blueprint/pmt2_rekening_ketikan_lapor.py` | Baru — lapor saja (H3), lihat "Kueri templat" |
| `frontend/src/features/pos/CheckoutPaymentDestination.jsx` (baru), `CheckoutDrawer.jsx`, `hooks/useAppActions.js` | Checkout |
| `frontend/src/features/orders/OrderPaymentInstructionCard.jsx` (baru), `OrderDetailPanel.jsx`, `SalesOrderOverrideDialog.jsx` | Detail pesanan, override |
| `frontend/src/features/pdf/pdfConstants.js` | Label bagian templat |
| `backend/tests_mem/test_PMT2_instruksi_bayar.py` (baru), `backend/tests/test_bp_PMT2_kode_bayar.py` (baru, lapis A), `frontend/src/features/__tests__/pmt2InstruksiBayar.test.js` (baru) | Uji |
| Uji lama disesuaikan | lihat tabel di bawah |
| `ENTITY_REGISTRY.md`, `CODEBASE_MAP.md`, `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`, `configKeyIndex.json`, fixture akses | Dokumen ikut berubah (dibangkitkan ulang bila hasil skrip) |

- Commit: belum (instruksi).
- Fixture disiapkan langsung vs proses bisnis dijalankan: fixture = pelanggan, produk, gudang, roll; kode `KN-7F3K2` (U9,
  menimpa kode hasil U6); pesanan & rencana bayar untuk `ensure_for_line`, tabrakan, dan `find_in_text`; baris
  `pdf_templates` skrip lapor. Alur lewat API = rekening A–D (`POST /api/bank-accounts`), pesanan, verifikasi,
  persetujuan, konfirmasi, override, render HTML Konfirmasi Pesanan & Faktur, `PATCH` tampil di dokumen, simpan/hapus
  templat, pengaturan (putaran KF-T8 lewat `PUT /api/config/values`).
- Dampak pada modul terkait: dokumen ber-e-sign tidak berubah hash (instruksi bayar dikeluarkan dari isi yang
  ditandatangani); faktur/SO tanpa kode tidak berubah tampilannya; naskah ber-`{{rekening_bank}}` untuk PT berekening
  bank satu-satunya tetap sama, untuk pesanan berekening tujuan kini menyebut rekening pesanan ("… a.n. …").
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_PMT2_instruksi_bayar.py` (23 uji). Merah di kode lama (berkas uji dijalankan di salinan
`git archive b95bd0d`): **23 gagal / 23** (`bukti/PM-T2/tests_mem_PMT2_merah_kode_lama.log`). Hijau di kode baru:
**23/23** (`…_hijau_kode_baru.log`).

| ID | Lapis | Merah di lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | ya — field tidak disimpan (`KeyError: payment_method_code`) | Lulus — potret `{BCA, 123-456-7890, PT Kain Suka Cita}` |
| U2 | B | ya — 200, pesanan lahir & roll direservasi | Lulus — 400 pesan persis; jumlah pesanan tetap; roll `available` tanpa `reserved_ref` |
| U3 | B | ya — 200 | Lulus — rekening gaji 400 pesan persis; `bitcoin` → "Cara bayar tidak dikenal: bitcoin."; `va` → "Cara bayar Virtual account tidak aktif untuk PT ini." |
| U4 | B | ya — field tidak ada | Lulus — transfer tanpa rekening → A (bawaan); tanpa cara bayar → keduanya kosong; `tunai` → `cash`, rekening kosong |
| U5 | B | ya — kunci tidak ada di registry | Lulus — `ent_ksc` 400 "Pilih cara bayar untuk pesanan ini."; `ent_kanda` 200; nilai Kanda tetap; pesanan buatan sistem (rute lain) tetap 200 |
| U6 | B | ya — tidak ada kode | Lulus — satu kode, `amount` 2.000.000, `^KN-[2-9A-HJ-NP-Z]{5}$`, `aktif`, `pyc_`, `payment_code` pesanan terisi; sebelum konfirmasi 0 kode |
| U7 | B | ya | Lulus — `amount` 1.000.000 |
| U8 | B | ya — layanan tidak ada | Lulus — dua panggilan ulang, tetap satu kode |
| U9 | B | ya (bergantung U6) | Lulus — `text` lima baris persis; `items[0]` = 2.000.000 · "" · "sebelum barang dikirim" · KN-7F3K2 |
| U10 | B | ya (bergantung U6) | Lulus — SO & faktur memuat "Instruksi Pembayaran" + kode + rekening; A `show_on_documents: false` → blok hilang; dipulihkan |
| U10b (tambahan) | B | ya | Lulus — `sections.payment_instruction: false` di faktur → hilang di faktur, tetap di SO |
| U11 | B | ya — 404 rute tidak ada | Lulus (cabang tanpa CR-T2) — `items` kosong, `note` "Instruksi bayar tersedia setelah barang dikirim.", 0 kode; CBD belum dikonfirmasi → "…setelah pesanan dikonfirmasi." Cabang CR-T2: uji sengaja GAGAL bila `billing_schedule_service` muncul (lihat Menyimpang 11) |
| U12 | B | ya (bergantung U1) | Lulus — rekening B 400 + pesanan tidak berubah; D 200, potret baru, tepat satu amandemen baru (label "Rekening tujuan", "Mandiri 140-00-7777 a.n. …"); rekening gaji 400; konteks override tanpa rekening Kanda |
| U13 | B | ya (bergantung U6) | Lulus — Tanpa Acuan + `order.view` 200; Manajer Kosong 403; Sopir 403; PT di luar penugasan 403/404 |
| U14 | B | ya — kunci tidak ada | Lulus — putaran KF-T8 (`putaran`) untuk dua kunci tanpa temuan; `kode_bayar_awalan` lapisan PT 400; `kn`, `K`, `KNABC`, `K1`, `KN-` → 400 |
| U14b (tambahan) | B | ya | Lulus — awalan `KNS` → kode baru `KNS-…`; kode lama `KN-7F3K2` tetap |
| U15 | A | — | **Lulus** di lingkungan A sesudah perbaikan harness `5097cda` (satu loop asyncio per modul; dulu "Event loop is closed" di uji kedua): `backend/tests/test_bp_PMT2_kode_bayar.py` (indeks wajib terpasang; 200 kode bersamaan berbeda; tabrakan dipaksa diulang; 10 panggilan bersamaan satu pesanan → satu kode) |
| U15 tiruan (tambahan) | B | ya | Lulus — pembangkit dipaksa `7F3K2,7F3K2,8H4M3` → `DuplicateKeyError` indeks `code` (mongomock menegakkan indeks unik parsial ini) → `KN-8H4M3`; selalu tabrakan → `KodeBayarError`, tanpa kode |
| tambahan | B | ya | Alfabet aman (300 sampel); `find_in_text` (4 bentuk berita transfer, kode tak terdaftar, teks kosong); `ensure_for_line` (DP pakai ulang kode, pelunasan kode baru 15 Des 2026, idempoten, `pay_code` baris, dua blok instruksi); token `{{rekening_bank}}` (rekening tujuan, lalu bawaan transfer); `payment_instruction` di luar hash e-sign; skrip lapor tidak menulis |
| U16 | layar | ya — komponen tidak ada (`bukti/PM-T2/jest_PMT2_merah_src_lama.txt`) | Uji komponen jest `pmt2InstruksiBayar.test.js` 6/6 (pilihan dari daftar induk + "Belum ditentukan", bawaan terisi, terkunci beralasan, kosong untuk Finance, tunai menyembunyikan rekening, wajib; kartu + salin + pemberitahuan; kalimat sebab; dua isian override). **Uji jalan peramban belum** |

## Uji lama yang disesuaikan (perilaku sengaja berubah)

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` | `+ PMT2_KUNCI` (= 2) di U04 | dua kunci baru berizin `cash.configure` (U02 tetap: bukan `settings.manage`) |
| `tests_mem/test_KFT4_registry.py` | `+ PMT2_PEMBAYARAN_PELANGGAN` (= 2) di U4 | dua kunci di kelompok "Pembayaran pelanggan" |
| `tests_mem/test_PK14_indeks_wajib.py`, `tests/test_bp_PK14_indeks_wajib.py` | `+ PMT2_INDEKS` (= 2); lapis A 16 → 18 | `uq_pay_code`, `uq_pay_code_line` |
| `tests_mem/test_PRT5_sapuan.py` | `SESUDAH_PRT5`: Finance `GET /api/config/registry` 403 → 200 sah | Finance memegang `cash.configure` → katalog terbuka hanya untuk kunci yang boleh diubahnya (aturan KF-T1) |
| `tests_mem/_nilai_uji.py` | cabang format `kode_huruf` (nilai lain `KNX`, nilai tak sah `kn`, `K1`, `KNABC`) | pembangkit putaran KF-T8 untuk format baru (bukan pelonggaran) |
| `access_modules.py` + `frontend/src/config/__tests__/fixtures/access_builtin_fixture.json` | tab `settings-cfg-finance` + `cash` | KF-T1 U14: tab kelompok terbuka bagi pemegang izin pengubah kuncinya; `tests/test_fe03_access_catalog.py --noconftest` 6/6 |
| `frontend/src/features/settings/config/configKeyIndex.json` | dibangkitkan ulang | kunci baru |

## Menyimpang dari blueprint

1. **Sub-judul pengaturan**: `group="uang-masuk"` diterjemahkan registry ke "Pembayaran pelanggan"; sub-judul wajib (KF-T4)
   dipilih "Syarat bayar, DP & cicilan" (8 → 10 kunci).
2. **Format nilai baru `kode_huruf`** di `config_registry.VALUE_FORMATS` untuk "2–4 huruf besar" (`text` tidak punya
   pemeriksa pola); pesan "'Awalan kode bayar' harus 2–4 huruf besar A–Z (mis. KN)." Layar memakai kotak teks biasa.
3. **"Wajib cara bayar" hanya untuk checkout** (`POST /api/sales-orders`): `create_order` juga dipanggil konversi pesanan
   khusus dan pengganti retur (tanpa cara bayar); keduanya akan ditolak bila kunci menyala. Validasi cara bayar/rekening
   yang dikirim tetap berlaku di semua jalur. `sensitif_baca=False` pada kunci ini (checkout semua sales membacanya).
4. **Field tambahan** `payment_codes.order_level`, `percent`, `updated_at`; jawaban instruksi menambah `note` (kalimat
   sebab bila `items` kosong) dan `items[].label`.
5. **Aturan tampil berlaku juga untuk API/salin/WhatsApp** (bukan hanya cetak): rekening yang tidak boleh tampil di
   dokumen pelanggan tidak dibagikan lewat tombol salin. Catatan: "Rekening tujuan belum ditandai tampil di dokumen
   pelanggan — minta Finance mengaturnya di Kas & Bank."
6. **"Belum lunas" sebelum PM-T3**: kode tingkat pesanan dilewati bila `paid_total` ≥ jumlah kodenya; kode baris dilewati
   bila baris rencana `paid`; pesanan batal/kedaluwarsa → tanpa blok. `status` kode tidak diubah (PM-T3).
7. **Instruksi bayar dikeluarkan dari hash e-sign** (`canonical_content`) — berubah saat lunas/ganti rekening; tanda
   tangan lama tetap sah.
8. **Konteks override membawa pilihan** (`payment_methods`, `receiving_accounts`) — form override tidak memanggil
   `GET /api/bank-accounts/receiving` (pemegang `order.override` belum tentu memegang izin daftar itu).
9. **WhatsApp**: `send_whatsapp` tidak diubah; PDF lampiran memuat kotak instruksi (kode lahir sebelum kirim otomatis
   "confirmed"); teks blok untuk pesan disalin lewat tombol.
10. **Tunai (`kas`)**: rekening opsional (diperiksa bila dikirim), tidak diisi bawaan (langkah 3 hanya untuk bank). Rekening
    yang id-nya tidak ada → 400 "Rekening tujuan tidak ditemukan." (pesan tambahan).
11. **U11 cabang CR-T2**: tidak bisa ditulis sebelum `billing_schedule_service` ada → tes **gagal dengan pesan** bila modul
    itu muncul, supaya CR-T2 melengkapi cabang dan mengaitkan `ensure_for_line` (bukan dilewati diam-diam).
12. Endpoint ditaruh di `routers/payment_methods.py` (router PM-T1; `sales_orders_extra.py` sudah > 1.000 baris).
13. Token `{{rekening_bank}}` tanpa atas nama tetap bentuk lama "{bank} {nomor} ({nama})" (KP-T6 U9 tetap lulus).
14. Skrip data lama hanya **lapor** (`pmt2_rekening_ketikan_lapor.py`, tanpa mode tulis — unit tidak mengubah templat); pola
    "8 digit atau lebih, boleh dipisah satu spasi/tanda hubung/titik" (mencakup `123-456-7890`; nomor telepon panjang
    ikut terlapor).

## Asumsi

- Spesifikasi: cara bayar tidak wajib sebagai bawaan; blok instruksi hanya untuk cara bayar ber-rekening bank; kode unik
  lintas PT dengan satu awalan.
- Termin bayar-dulu = `type: cash` atau `dp_percent > 0`; persen = `dp_percent` bila > 0, selain itu 100 (CASH, CBD → 100;
  DP50 → 50). Nilai = `grand_total` (termasuk PPN).
- Label blok: "Pembayaran sebelum kirim" (100 %), "Uang muka {n}%" (< 100 %), atau label baris rencana.
- Tanggal jatuh tempo ditulis tanggal kalender "15 Des 2026" tanpa geser zona.
- Kegagalan membuat kode saat konfirmasi tidak membatalkan konfirmasi (dicatat log); detail pesanan lalu menulis
  "…setelah pesanan dikonfirmasi." — perlu PM-T3/pemantauan bila terjadi.

## Kueri templat (H3 — calon nomor rekening ketikan)

Baca saja, di MongoDB data nyata (unit ini tidak mengubah isi templat; pembersihan lewat Pengaturan › Dokumen & Cetak ›
Template Dokumen oleh pemilik):

```js
// persis bunyi spesifikasi: delapan digit berurutan atau lebih
db.pdf_templates.find({$or: [{"config.intro_text": {$regex: "\\d{8,}"}}, {"config.closing_note": {$regex: "\\d{8,}"}},
                             {"config.footer_text": {$regex: "\\d{8,}"}}]},
                      {_id: 0, doc_type: 1, entity_id: 1, "config.intro_text": 1, "config.closing_note": 1, "config.footer_text": 1})
// lebih luas (dipakai skrip): digit boleh dipisah satu spasi / tanda hubung / titik, mis. 123-456-7890
db.pdf_templates.find({$or: [{"config.intro_text": {$regex: "\\d(?:[ .-]?\\d){7,}"}},
                             {"config.closing_note": {$regex: "\\d(?:[ .-]?\\d){7,}"}},
                             {"config.footer_text": {$regex: "\\d(?:[ .-]?\\d){7,}"}}]})
```

Skrip setara: `python scripts/blueprint/pmt2_rekening_ketikan_lapor.py [--pt <PT>]` (diuji di lingkungan B; tidak
dijalankan ke database mana pun).

## Cek layar

Acuan `docs/KN_37_STANDAR_UI_GUDANG.md`. Belum dipotret (integrator 1280/1024/390 px). Dari kode:

| Butir | Checkout › Termin & Lot (desktop & HP) | Detail pesanan › kartu Instruksi Pembayaran | Edit / Override SO | Dokumen cetak (SO, faktur) |
|---|---|---|---|---|
| 1 Tabel melebihi kartu | Tidak ada tabel | Tidak ada tabel; `dl` 2 kolom `auto/minmax(0,1fr)` + `break-words` | Isian di grid 2 kolom yang ada | Kotak `page-break-inside: avoid`, huruf monospasi 9 pt (lima baris pendek, tidak melebar; potret `bukti/PM-T2/contoh_faktur_instruksi_bayar.png`) |
| 2 Kartu tanpa bantalan | Di kartu termin yang ada (`p-2.5`) | Kartu sendiri `p-2.5`, judul di dalam | Dialog lama | Kotak `padding:8px 10px` |
| 3 Kepala kartu padat | Hanya label | Judul "Instruksi Pembayaran" sendirian; tombol salin di bilah bawah, sendiri | — | — |
| 4 Tombol mati tanpa alasan | Rekening terkunci → teks "Satu-satunya rekening penerimaan PT ini untuk cara bayar ini." (ikon kunci); wajib → teks "PT ini mewajibkan cara bayar dipilih…" + tombol buat berlabel "Pilih Cara Bayar" | Tombol salin hanya muncul bila ada blok | Rekening kosong/tidak perlu → kalimat, bukan isian mati | — |
| 5 Status hanya warna | Peringatan pakai ikon + teks + `text-kn-warning-text` | Pemberitahuan salin: ikon centang/peringatan + teks + warna; catatan kosong: ikon info + teks | — | — |
| 6 Daftar panjang tanpa cari | Pilihan cara bayar ≤ 7; rekening per PT sedikit (`KNSelect` mencari otomatis ≥ 6) | Blok per tagihan (sedikit) | sama | — |
| 7 Teks vs izin | Tidak ada teks wewenang; rekening gagal dimuat → "Pesanan tetap bisa dibuat — rekening bawaan PT diisi otomatis." (benar: server mengisi) | Kartu hanya dibaca bila `order.view` (endpoint sama dengan detail) | Pilihan dari konteks override (izin `order.override`) | — |
| 8 Kosong ganda / angka 0 | Satu kalimat kosong | Satu kalimat sebab dari server | Satu kalimat | Tanpa blok bila tidak ada tagihan |

Lain-lain: huruf ≥ 12 px (`text-fs-12`, `field-label`), warna token `kn-*` (tanpa hex baru), tombol `secondary-button
btn-sm whitespace-nowrap`, label isian di atas (`field-label`), "Wajib" bertanda `*`. Label lama berhuruf 9 px di kartu
termin checkout dan dialog override tidak diubah (di luar unit; isian baru tidak menambah). `verify_ui_standard` 13 = 13.

## Integrasi ke cabang

Dipetik ke cabang di atas AG-T1 sebagai `3017c77`: bentrok berdampingan di `entity_scope.py`, `indexes.py` (blok indeks
wajib CR-T1/PK-31 + PM-T2), `verify_contract.py`, `ENTITY_REGISTRY.md`; hitungan uji KF-T1 (`+ PMT2_KUNCI`), KF-T4
(`+ CRT1_PEMBAYARAN_PELANGGAN + PMT2_PEMBAYARAN_PELANGGAN`), PK-14 lapis B (`+ PMT2_INDEKS`) dan lapis A (21 indeks
wajib). Indeks kunci, fixture akses, peta kode dibangkitkan ulang. tests_mem HEAD gabungan 1414 lulus; jest penuh 789.

## Cek layar (potret integrator)

Daftar Pesanan (1280 px, data acuan) dipotret: dua cacat lama di daftar yang memuat rincian pesanan diperbaiki (`73314a8`):
lencana "Bayar Sebagian · sisa Rp …" pecah menjadi gumpalan oval tiga baris → pil "Bayar Sebagian" + teks sisa di
sampingnya; chip sub-status kolom Tahap terpotong di tepi kartu → boleh pindah baris. Kartu Instruksi Pembayaran ada di
rincian penuh pesanan; data acuan tidak memuat pesanan bayar-dulu ber-kode, jadi kartu berisi belum dipotret (jest 6/6).
Bukti: `bukti/PM-T2/layar_daftar_pesanan_1280_sebelum.png`, `layar_daftar_pesanan_lencana_bayar_sesudah.png`,
`layar_daftar_pesanan_tahap_sesudah.png`.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di `a48a0a9` — satu gate untuk
enam unit yang digabung bersamaan (CR-T1, PK-31, AG-T1, PM-T2, TX-T1, PK-18) — lalu `--quick` diulang di `f1b8239` sesudah
perbaikan cek layar (hanya layar):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` (`a48a0a9`) | 14 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama: `InventoryStockView`) | 2 (`config_wiring` + uji-diri) |
| `--ci` (`a48a0a9`) | 41 FAIL | 43 | 1 (ganti nama) | 2 |
| `--quick` (`f1b8239`) | 14 FAIL | 16 | 1 (ganti nama) | 2 |

Kuitansi: `bukti/PM-T2/gate_quick_receipt.md`, `gate_ci_receipt.md`. Lapis A unit-unit itu (6 berkas `tests/test_bp_*`) di
lingkungan A: 19 lulus.


Dijalankan statik / lingkungan B (W = basis `b95bd0d`; T = gabungan di atas `f05d8da`, lihat Penggabungan):

| Pemeriksaan | Sebelum (`b95bd0d`) | Sesudah |
|---|---|---|
| `tests_mem` | 1313 lulus / 2 dilewati / 4 xfail | W: 23 uji baru 23/23; modul yang hitungannya disesuaikan (KF-T1, PR-T5, KF-T4, PK-14, KP-T6, PM-T1) 88/88; penuh → lihat Penggabungan (T) |
| jest `pmt2InstruksiBayar.test.js` | 0/6 (suite gagal dimuat: komponen tidak ada) | 6/6 |
| `hitung_penjaga.sh` | auth 28 · ui_standard 13 · i18n 104 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · lainnya PASS/0 | identik (`bukti/PM-T2/penjaga_sebelum_sesudah.txt`) |
| `verify_payment_vocab` (+ `--self-test`) | PASS | PASS 0 pelanggaran; uji-diri 18/18 |
| `verify_config_fallback` / `--entity` | PASS | PASS 0 / PASS 0 |
| `verify_config_text` | PASS | PASS (438 kunci) |
| `verify_role_gate_ui` · `verify_access_catalog_nav` · `verify_permission_checked` · `verify_ui_contrast` · `verify_scope_guard` · `verify_contract.py --all` | PASS | PASS |
| `audit_config_wiring.py --strict` (salinan berjalur) | bersih | bersih (keluar 0) |
| `tests/test_fe03_access_catalog.py --noconftest` | — | 6/6 |
| `gen_config_key_index.py --check` | — | selaras |

## Penggabungan

Dikerjakan di `b95bd0d` (W); digabung ke HEAD cabang `f05d8da` (T, sesudah PK-44, perbaikan tampilan, catatan STATUS).
40 berkas. Berkas yang di HEAD sama dengan basis disalin; yang berbeda digabung `git merge-file`:

| Berkas | Hasil | Keputusan |
|---|---|---|
| `frontend/src/features/orders/OrderDetailPanel.jsx` | bersih | PK-44 menambah panel "Cetak Dokumen · Gudang & Penagihan"/Dokumen Terkait; kartu Instruksi Pembayaran tetap di bawah Ringkasan Harga |
| `ENTITY_REGISTRY.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | bersih | — |
| `memory/PRD.md` | bentrok (dua butir baru di tempat yang sama) | keduanya dipertahankan: PK-44 lalu PM-T2 |
| `CODEBASE_MAP.md`, `configKeyIndex.json`, fixture akses | dibangkitkan ulang di T | — |

Hitungan uji lama tidak berubah di HEAD sejak basis (KF-T1 `*_KUNCI`, PR-T9, PK-14, PR-T5 sama) → tambahan PM-T2 saja.

| Pemeriksaan di T | HEAD `f05d8da` | T (gabungan) |
|---|---|---|
| `tests_mem` penuh | 1328 lulus / 2 dilewati / 4 xfail | **1353 lulus / 2 dilewati / 4 xfail** (+23 uji PM-T2, +2 kasus putaran KF-T8 untuk dua kunci baru) |
| jest penuh (`src/config`, `src/features`, `src/hooks`, `src/components`) | 750 lulus; 35 suite gagal dimuat (`@radix-ui`) | **756 lulus** (+6); 35 suite gagal dimuat — daftar sama |
| `fix1Cakupan.test.js` (suite radix yang memuat `useAppActions`, dengan tiruan pemilih) | 9/9 | 9/9 |
| `hitung_penjaga.sh` | auth 28 · ui 13 · i18n 104 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · lainnya PASS/0 | identik |
| `verify_role_gate_ui` · `verify_config_fallback` (+`--entity`) · `verify_payment_vocab` (+uji-diri) · `verify_access_catalog_nav` · `verify_config_text` · `verify_permission_checked` · `verify_scope_guard` | — | PASS semua |
| `audit_config_wiring.py --strict`, `check_nav_map.py` (salinan berjalur T) | — | bersih (keluar 0) / PASS |
| `tests/test_fe03_access_catalog.py --noconftest` | — | 6/6 |

Bukti: `bukti/PM-T2/tests_mem_T_*.log`, `jest_penuh_T.txt`, `penjaga_T_sebelum_sesudah.txt`.

## Keterbatasan / belum teruji

- U15 (keunikan & balapan di MongoDB asli) lulus 4/4 sesudah perbaikan harness `5097cda`. Di lingkungan B mongomock ternyata menegakkan indeks
  unik parsial `payment_codes.uq_pay_code` (tabrakan nyata `DuplicateKeyError`), tetapi balapan tidak teruji.
- Uji jalan peramban (U16) belum; hanya uji komponen.
- Kode untuk pesanan tempo menunggu CR-T2 (kait `ensure_for_line`).

## Hambatan lingkungan

- Jest lokal: suite yang memuat `@radix-ui`/`cmdk` gagal dimuat (kendala lingkungan); suite baru meniru `KNSelect`.
- Jalan `tests_mem` penuh pertama di W (bersamaan dengan uji lain; kernel sempat mematikan satu proses karena memori)
  menemukan dua uji lama yang bergeser karena izin `cash.configure` pada kunci baru (KF-T1 U14 tab Pengaturan, PR-T5
  sapuan Finance) — diperbaiki (lihat "Uji lama yang disesuaikan"), modulnya hijau; jalan penuh akhir di T sendirian.
- ESLint berkas layar yang berubah: 0 galat (peringatan lama "eslint-disable tak terpakai" karena konfigurasi lokal tanpa
  plugin react-hooks).

## Yang perlu direview

- Menyimpang 3 (wajib hanya checkout), 5 (aturan tampil juga untuk salin), 6 (lunas turunan), 7 (keluar dari hash e-sign).
- Finance (pemegang `cash.configure`) kini melihat tab "Aturan Keuangan & Pajak" berisi dua kunci ini.
- SO pesanan khusus yang dikonfirmasi sistem (`special_order_phase2`) dan pesanan sample tidak melahirkan kode.
