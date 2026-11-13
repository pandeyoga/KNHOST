# PM-T2 — Pesanan menyimpan cara bayar dan rekening tujuan; dokumen mencetak instruksi bayar berkode

| | |
|---|---|
| Gelombang | Modul cara bayar dan rekening |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | PM-T1 |
| Menutup temuan | PM-01 |
| Keputusan | K-34, K-35 |
| Standar | §2 (2.1, 2.2, 2.4), §3.1 (Z1, Z2), §3.4 (N1, N2, N4), §4 (L1, L4, L6), §5 (D1, D3, D7, D9), §6 |
| Lingkungan uji | keduanya (B; A untuk indeks unik kode bayar) |

## Tujuan

Pelanggan menerima dokumen yang menyebut ke rekening mana harus membayar dan dengan kode apa, diambil dari master —
bukan diketik sales di luar sistem. Rekening PT lain tidak mungkin terpilih. Kode bayar menjadi kunci pencocokan
mutasi bank di PM-T3.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| Fakta | Jangkar |
|---|---|
| Isi permintaan pesanan hanya punya termin; tidak ada cara bayar maupun rekening | `backend/schemas.py:533` (`payment_term_code`) |
| Pesanan menyimpan kode dan nama termin serta `payment_status`; tidak ada field rekening | `backend/routers/sales_orders.py:619` (`payment_term_code`) |
| Konfirmasi Pesanan dan Faktur mencetak "Termin Bayar" dan "Status Bayar"; tidak ada rujukan bank | `backend/services/pdf_resolvers.py:295` (`resolve_sales_order`), `backend/services/pdf_resolvers.py:1054` (`resolve_invoice`) |
| Rekening hanya bisa diketik di naskah penutup, yang berlaku per jenis dokumen untuk semua PT | `backend/services/pdf_service.py:35` (`closing_note`), `backend/services/pdf_service.py:151` (`get_template_cfg`) |
| Kop per PT berisi nama, alamat, telepon, NPWP — tanpa bank | `backend/services/pdf_service.py:216` (`get_branding`) |
| Bagian dokumen yang bisa dimatikan didaftar di konfigurasi templat | `backend/services/pdf_service.py:41` (`sections`) |
| Checkout hanya menanyakan termin; keranjang HP memakai komponen yang sama | `frontend/src/features/pos/CheckoutDrawer.jsx:419` (`payment-term-select`), `frontend/src/features/sales/mobile/MobileCart.jsx:115` (`paymentTerms`) |
| Override pesanan sebelum picking mengenal enam field kepala, termasuk termin | `backend/services/so_override_service.py:21` (`HEADER_LABEL`) |
| Pengiriman dokumen lewat WhatsApp sudah ada (teks + lampiran) | `backend/services/delivery_service.py:59` (`send_whatsapp`) |

## Perubahan

### Data

`sales_orders` — field baru:

| Field | Tipe | Arti |
|---|---|---|
| `payment_method_code` | kode kanonik atau `""` | Cara bayar yang disepakati; `""` = belum ditentukan (pesanan lama dan bawaan) |
| `receiving_account_id` | id `bank_accounts` atau `""` | Rekening tujuan |
| `receiving_account` | `{bank_name, account_number, holder_name}` | Potret saat dipilih (D3); dokumen lama tetap menyebut rekening yang berlaku saat itu |
| `payment_code` | string | Kode bayar tingkat pesanan (hanya pesanan bayar-dulu; lihat di bawah) |

Koleksi baru `payment_codes` (awalan id `pyc_`):

| Field | Arti |
|---|---|
| `code` | `{awalan}-{5 karakter}`, huruf besar; karakter dari `23456789ABCDEFGHJKLMNPQRSTUVWXYZ` (tanpa 0, 1, I, O). Contoh `KN-7F3K2` |
| `entity_id`, `order_id`, `order_number`, `customer_id` | Pemilik |
| `plan_id`, `line_id` | Baris tagihan (`payment_plans.lines[].line_id`); `""` untuk kode tingkat pesanan |
| `amount`, `due_date` | Potret jumlah dan jatuh tempo saat kode lahir |
| `status` | `aktif` · `lunas` · `batal` |

Indeks: `code` unik **lintas PT** (supaya berita transfer tidak ambigu); `(order_id, line_id)` unik. Kode dibuat acak
(`secrets`), disisipkan, dan diulang paling banyak lima kali bila menabrak indeks. Baris tagihan mendapat `pay_code`.

Kapan kode lahir:

| Keadaan | Kode |
|---|---|
| Pesanan bayar-dulu (termin `type: cash` atau `dp_percent > 0`) dikonfirmasi | Satu kode tingkat pesanan; `amount` = nilai pesanan × persen wajib (tunai 100 %) |
| CR-T2 sudah selesai: baris tagihan lahir | Satu kode per baris; baris `dp` memakai ulang kode tingkat pesanan (diisi `plan_id`, `line_id`) |
| Pesanan tempo sebelum CR-T2 selesai | Belum ada kode; blok instruksi tidak dicetak |

### Server

Berkas baru `backend/services/payment_code_service.py`:

| Fungsi | Perilaku |
|---|---|
| `async def ensure_for_order(order: dict) -> Optional[dict]` | Idempoten per pesanan; dipanggil setelah `confirm_core` berhasil |
| `async def ensure_for_line(plan: dict, line: dict) -> dict` | Idempoten per baris; dipanggil `billing_schedule_service` saat baris lahir (bila modul itu ada) |
| `async def find_in_text(text: str) -> list` | Kode yang muncul dalam sebuah teks (untuk PM-T3) |
| `async def instruction(order_id: str) -> dict` | `{order_number, method_name, account, items: [{label, amount, due_date, due_label, pay_code}], text}` untuk tagihan berkode yang belum lunas |

`SalesOrderCreate` mendapat `payment_method_code: str = ""` dan `receiving_account_id: str = ""`. Urutan di
`create_order`, sebelum reservasi stok:

1. Cara bayar kosong: bila `payment.wajib_cara_bayar_di_pesanan` menyala → 400; selain itu kedua field disimpan kosong.
2. `normalize` + `payment_method_service.get(entity_id, code)`; harus aktif dan berarah `masuk`.
3. Bila cara bayar ber-`needs_account: bank` dan rekening kosong → isi dari rekening bawaan (PT, cara bayar) hasil
   PM-T1; bila tidak ada bawaan, biarkan kosong.
4. Rekening terisi: `entity_id` rekening = PT pesanan, aktif, `purposes` memuat `penerimaan_pelanggan`,
   `payment_method_codes` memuat cara bayar. Simpan potret `receiving_account`.

`so_override_service`: `HEADER_LABEL` bertambah `payment_method_code` ("Cara bayar") dan `receiving_account_id`
("Rekening tujuan") dengan validasi langkah 2–4; perubahan tercatat sebagai amandemen seperti field kepala lain.

| Endpoint | Izin | Jawaban |
|---|---|---|
| `GET /api/sales-orders/{id}/payment-instruction` | `order.view` + pagar PT dan pemilik pesanan yang sudah ada | Hasil `instruction(...)`; `items` kosong bila belum ada kode atau rekening |

Galat:

| Keadaan | Kode | Pesan |
|---|---|---|
| Wajib tetapi kosong | 400 | "Pilih cara bayar untuk pesanan ini." |
| Rekening milik PT lain | 400 | "Rekening tujuan bukan milik PT pesanan ini." |
| Rekening nonaktif, bukan untuk penerimaan pelanggan, atau tidak melayani cara bayar itu | 400 | "Rekening ini tidak bisa menerima pembayaran pelanggan lewat {nama cara bayar}." |
| Cara bayar tak dikenal / nonaktif | 400 | Pesan dari PM-T1 |

**Blok instruksi bayar.** `resolve_sales_order` dan `resolve_invoice` menambahkan `payment_instruction` (satu blok per
tagihan berkode yang belum lunas); mesin PDF mencetaknya di bawah total dalam kotak berjudul "Instruksi Pembayaran".
Bagian baru `sections.payment_instruction` (bawaan tampil) bisa dimatikan per jenis dokumen. Blok hanya dicetak bila
rekening tujuan ber-`show_on_documents: true` dan ber-`needs_account: bank`. Teks tiap blok, persis:

```text
Pembayaran untuk pesanan {nomor pesanan}
Jumlah        : Rp {jumlah berpemisah ribuan}
Jatuh tempo   : {tanggal, mis. 15 Des 2026 — atau "sebelum barang dikirim" untuk tagihan bayar-dulu}
Transfer ke   : {nama bank} {nomor rekening} a.n. {atas nama}
Berita/kode   : {kode bayar}
```

Teks WhatsApp = blok yang sama (field `text` pada `instruction`), dipisah satu baris kosong bila lebih dari satu tagihan.
Bila KP-T6 sudah selesai, token naskah `{{rekening_bank}}` yang dibuatnya (penyedia: rekening tunggal PT) diganti
penyedianya menjadi potret rekening tujuan pesanan, lalu rekening bawaan `transfer` PT; bila belum, lewati.

Laporan unit memuat kueri pencari templat (`pdf_templates`) yang naskah pembuka, penutup, atau footer-nya berisi
delapan digit berurutan atau lebih — calon nomor rekening ketikan — untuk dibersihkan pemilik lewat layar (H3; unit ini
tidak mengubah isi templat).

### Pengaturan

Group `uang-masuk`, permission `("cash", "configure")`.

| Field | `payment.wajib_cara_bayar_di_pesanan` | `payment.kode_bayar_awalan` |
|---|---|---|
| type · default | `bool` · tidak | `text` · `"KN"` (2–4 huruf besar) |
| scopes | `("global", "entity")` | `("global",)` — kode unik lintas PT |
| label | "Wajibkan cara bayar saat membuat pesanan" | "Awalan kode bayar" |
| help | "Bila menyala, pesanan tidak bisa dibuat tanpa memilih cara bayar." | "Huruf di depan kode bayar yang ditulis pelanggan di berita transfer." |
| impact | "Sales harus memilih cara bayar di checkout; aplikasi lama yang tidak mengirimnya akan ditolak." | "Hanya kode baru yang memakai awalan baru; kode lama tetap berlaku." |
| example | "Menyala · checkout tanpa cara bayar → ditolak" | "KN → KN-7F3K2" |
| risk / requires_reason | `medium` / tidak | `low` / tidak |
| consumers | `routers/sales_orders.py:create_order` | `services/payment_code_service.py:ensure_for_order` |

### Izin dan peran

Tidak ada pasangan baru (memakai `order.create`, `order.view`, `order.override`, dan daftar rekening penerima PM-T1).

### Layar

- **Checkout** (`CheckoutDrawer.jsx`, dipakai juga keranjang HP), di bawah "Termin Pembayaran":
  - "Cara bayar" — pilihan dari `GET /api/payment-methods?direction=masuk` PT pesanan; ada pilihan "Belum ditentukan"
    kecuali saat pengaturan mewajibkan.
  - "Rekening tujuan" — dari `GET /api/bank-accounts/receiving`; tiap pilihan ditulis "{bank} {nomor} a.n. {atas
    nama}"; terisi otomatis dari bawaan; terkunci bila hanya ada satu; tersembunyi bila cara bayar tidak butuh rekening
    bank. Kosong: "Belum ada rekening penerimaan untuk cara bayar ini — minta Finance mengaturnya di Kas & Bank."
- **Detail pesanan** (`OrderDetailPanel.jsx`): baris "Cara bayar" dan "Rekening tujuan"; kartu "Instruksi Pembayaran"
  berisi blok di atas dengan tombol **Salin instruksi bayar** (menyalin `text`) dan pemberitahuan "Instruksi bayar
  disalin." Tanpa kode: "Instruksi bayar tersedia setelah pesanan dikonfirmasi." (bayar-dulu) atau "…setelah barang
  dikirim." (tempo).
- Form override pesanan: dua isian yang sama.

## Uji penerimaan

Persiapan: rekening **A** (`ent_ksc`, BCA 123-456-7890 a.n. PT Kain Suka Cita, penerimaan pelanggan, melayani
`transfer`, bawaan `transfer`, tampil di dokumen) dan **B** (`ent_kanda`, serupa); pelanggan dan produk fixture.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | Pesanan `ent_ksc` dengan `payment_method_code: "transfer"`, `receiving_account_id: A` | 200; potret `receiving_account` = `{BCA, 123-456-7890, PT Kain Suka Cita}` |
| U2 | B | — | Pesanan `ent_ksc` dengan rekening **B** | 400 "Rekening tujuan bukan milik PT pesanan ini."; tidak ada pesanan, tidak ada reservasi roll |
| U3 | B | Rekening C di `ent_ksc` hanya ber-`purposes: ["gaji"]` | Pesanan dengan rekening C | 400 "Rekening ini tidak bisa menerima…" |
| U4 | B | — | Pesanan `transfer` tanpa rekening; pesanan tanpa cara bayar | Pertama: `receiving_account_id == A` (bawaan); kedua: 200 dengan kedua field kosong |
| U5 | B | `payment.wajib_cara_bayar_di_pesanan` menyala pada `ent_ksc` | Pesanan tanpa cara bayar di `ent_ksc`; lalu di `ent_kanda` | 400 "Pilih cara bayar…"; 200 — PT lain tidak berubah |
| U6 | B | Pesanan termin CBD Rp 2.000.000 dengan rekening A | Konfirmasi pesanan | Satu `payment_codes`: `amount` 2.000.000 (100 %), `code` cocok `^KN-[2-9A-HJ-NP-Z]{5}$`, `status: aktif`; `sales_orders.payment_code` terisi |
| U7 | B | Pesanan termin DP50 Rp 2.000.000 | Konfirmasi | `amount` 1.000.000 (2.000.000 × 50 %) |
| U8 | B | U6 | `ensure_for_order` dipanggil lagi | Tetap satu kode |
| U9 | B | U6 dengan kode `KN-7F3K2` (fixture) | `GET …/payment-instruction` | `text` persis lima baris: "Pembayaran untuk pesanan {nomor}", "Jumlah        : Rp 2.000.000", "Jatuh tempo   : sebelum barang dikirim", "Transfer ke   : BCA 123-456-7890 a.n. PT Kain Suka Cita", "Berita/kode   : KN-7F3K2" |
| U10 | B | U6 | Render HTML dokumen `sales_order` dan `invoice`; ubah A menjadi `show_on_documents: false`; render lagi | Keduanya memuat "Instruksi Pembayaran" dan kodenya; setelah diubah blok tidak ada |
| U11 | B | Pesanan termin NET30 dikonfirmasi | `GET …/payment-instruction` | Tanpa CR-T2: `items` kosong. Dengan CR-T2 dan satu surat jalan: satu tagihan berkode dengan jatuh tempo baris itu. Tes memilih cabang dari keberadaan `billing_schedule_service` |
| U12 | B | U1 | Override rekening ke **B**; lalu ke rekening lain milik `ent_ksc` | 400; 200 dengan potret baru dan satu catatan amandemen |
| U13 | B | peran uji baku | **Tanpa Acuan** + `order.view`: `GET …/payment-instruction`; **Manajer Kosong**; **Sopir** | 200; 403; 403 |
| U14 | B | — | Putaran `t1_config.py` untuk dua kunci | Lulus (`payment.kode_bayar_awalan` menolak lapisan PT) |
| U15 | A | — | Buat 200 kode berurutan cepat lewat fungsi; paksa satu tabrakan dengan menyisipkan kode kembar | 200 kode berbeda; tabrakan diulang dan berhasil; tidak ada dua dokumen berkode sama |
| U16 | layar (uji jalan) | Data acuan | `sls` checkout di `ent_ksc`, lalu membuka detail pesanan | Rekening `ent_kanda` tidak ada di pilihan; rekening terisi dari bawaan; tombol salin menghasilkan teks blok |

## Langkah kerja

1. `backend/tests_mem/test_PMT2_instruksi_bayar.py`: U1–U14; merah.
2. Field pesanan, validasi di `create_order`, dua kunci pengaturan. U1–U5, U14 hijau.
3. `payment_codes`, `payment_code_service`, kait konfirmasi (dan kait baris tagihan bila CR-T2 ada). U6–U8, U11 hijau.
4. `instruction`, endpoint, blok PDF, bagian templat. U9, U10, U13 hijau.
5. Override; layar checkout, detail pesanan; U12; U15 di lingkungan A; U16; gate; laporan dengan kueri templat.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`payment_codes`, field pesanan, `lines[].pay_code`), `CODEBASE_MAP.md`
(`services/payment_code_service.py`), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("kode bayar",
"rekening tujuan", "instruksi bayar").

## Di luar lingkup

- Rekening dan referensi wajib di kwitansi, tanda "tidak sesuai instruksi", cocok lewat kode bayar → PM-T3.
- Naskah dan penanda tangan dokumen per PT (KP-19) → KP-T6.
- Nominal unik (tiga digit terakhir) sebagai pembeda tambahan (`07` §A3.4): belum ada unitnya.
- Rekening bawaan per pelanggan atau per kanal penjualan: belum ada unitnya; bawaan hanya per (PT, cara bayar).

## Asumsi dan risiko

- `ASUMSI:` cara bayar di pesanan tidak diwajibkan sebagai bawaan, karena hari ini pesanan lahir tanpa cara bayar dan
  aplikasi HP versi lama (antrean luring) tidak mengirimnya.
- `ASUMSI:` blok instruksi hanya untuk cara bayar ber-rekening bank; rancangan tidak memberi teks untuk tunai dan giro.
- `ASUMSI:` kode bayar unik lintas PT dengan satu awalan, bukan per PT, supaya mutasi yang salah masuk rekening PT
  lain tetap bisa dikenali.
- `RISIKO:` templat yang masih memuat nomor rekening ketikan akan tampil berdampingan dengan blok baru. Penangkal:
  kueri di laporan + sakelar `sections.payment_instruction`. Membatalkan: matikan bagian itu di templat bawaan;
  field pesanan dan kode bayar tidak dibaca jalur lain.
