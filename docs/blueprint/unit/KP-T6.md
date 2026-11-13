# KP-T6 — Dokumen dan cetak per PT: satu sumber identitas, naskah dan tanda tangan per PT

| | |
|---|---|
| Gelombang | Jalur konfigurasi perusahaan (U) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | KP-T1 |
| Menutup temuan | KP-18, KP-19, KP-34 |
| Keputusan | K-34 (rekening penerimaan = data master; isinya unit PM-T1/PM-T2); `00` §4.1 |
| Standar | §3.1 (Z1, Z6), §3.4 (N1), §4 (L1, L2, L5, L6), §5 (D1, D8), §6 |
| Lingkungan uji | B |

## Tujuan

Nama, alamat, NPWP, dan kontak pada kop surat berasal dari Profil PT saja. Tiap PT bisa punya teks pembuka dan
penutup, kota, slot tanda tangan, dan tanda air sendiri per jenis dokumen. Naskah faktur bisa memuat rekening bank PT
lewat satu token. Kop sebuah PT tidak bisa dibaca atau diubah oleh pengguna yang tidak bertugas di PT itu.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Identitas kop dirakit dari `document_branding` lebih dulu, baru master PT: nama, alamat, email, NPWP, logo. Telepon, slogan, dan situs **hanya** dari `document_branding` | `backend/services/pdf_service.py:216` (`get_branding`) |
| 2 | Layar perancang menyediakan isian teks "Nama Perusahaan", "Alamat", "Telepon", "NPWP", "Email", "Website" yang disimpan ke `document_branding` | `backend/services/pdf_service.py:248` (`save_branding`); `frontend/src/features/pdf/PdfEditorTabs.jsx:185` (`company_name`) |
| 3 | Mesin cetak lama (surat jalan/faktur dasar) memakai koleksi `document_templates` berlapis PT, dan mencetak judul "Kain Nusantara" bila template tidak punya logo | `backend/services/inventory_service.py:108` (`render_order_html`); `backend/services/inventory_service.py:149` (`logo_html`); `backend/services/entity_master_service.py:76` (`document-templates`) |
| 4 | Konfigurasi template mesin baru berlapis: bawaan kode → `__default__` → jenis dokumen. Kuncinya hanya `doc_type`; tidak ada lapisan PT | `backend/services/pdf_service.py:143` (`get_template_cfg`); `backend/services/pdf_service.py:168` (`save_template_cfg`) |
| 5 | Teks pembuka/penutup, teks footer, kota (`place`), slot tanda tangan, dan tanda air termasuk konfigurasi global itu | `backend/services/pdf_service.py:19` (`DEFAULT_TEMPLATE_CFG`) |
| 6 | Token naskah yang sah berjumlah 13; tidak ada token rekening bank. Penyusun faktur tidak membaca `bank_accounts` | `backend/services/pdf_service.py:49` (`PLACEHOLDERS`); `backend/services/pdf_service.py:72` (`render_text`); `backend/services/pdf_resolvers.py:1037` (`resolve_invoice`) |
| 7 | Endpoint baca dan simpan kop memakai `entity_id` dari alamat tanpa memeriksa cakupan PT pengguna | `backend/routers/pdf.py:259` (`get_branding`); `backend/routers/pdf.py:265` (`put_branding`) |
| 8 | Endpoint contoh dan pratinjau juga memakai `entity_id` mentah dari permintaan | `backend/routers/pdf.py:131` (`get_sample`); `backend/routers/pdf.py:278` (`entity_id`) |
| 9 | Gambar tanda tangan dan cap per PT ditempel ke slot menurut `role`/`label` slot | `backend/services/pdf_service.py:274` (`brand_sig`) |

Yang sudah benar dan dipertahankan: jenis dokumen hanya menyimpan perbedaan terhadap bawaan —
`backend/services/pdf_service.py:132` (`diff_cfg`); token tak dikenal ditolak saat simpan —
`backend/services/pdf_service.py:68` (`unknown_tokens`).

## Perubahan

### Data

`business_entities` mendapat tiga field (semua opsional, teks; masuk `EDITABLE_FIELDS` dan `uniform_entity`):

| Field | Arti |
|---|---|
| `print_name` | Nama yang dicetak di kop bila berbeda dari nama legal. Kosong = nama legal |
| `tagline` | Slogan di bawah nama |
| `website` | Situs web |

`document_branding`: hanya `logo_b64`, `header_image_b64`, `footer_image_b64`, `stamp_b64`, `signatures` yang masih
ditulis. Field teks lama (`company_name`, `address`, `phone`, `email`, `website`, `npwp`, `tagline`) tidak dihapus dan
tetap dibaca **sampai** PT itu diselesaikan (lihat bawah). Field baru `identity_resolved_at`, `identity_resolved_by`.

`pdf_templates` mendapat `entity_id` (`"all"` atau id PT). Kunci unik baru (`doc_type`, `entity_id`). Baris yang ada
diberi `entity_id: "all"` oleh migrasi `scripts/migrate_kpt6_template_pt.py` (aman diulang; tidak mengubah hasil cetak).

Tidak ada penyalinan otomatis teks kop ke Profil PT: bila teks `document_branding` sebuah PT berbeda dari Profil PT,
kop tetap mencetak teks lama sampai pemilik memilih salah satu lewat layar (data nyata — H3).

### Server

`backend/services/pdf_service.py`:

- `get_branding(entity_id)` — sumber identitas:
  - PT **sudah diselesaikan** (`identity_resolved_at` terisi) atau tidak punya teks lama: `company_name` =
    `print_name` atau `legal_name`; `address` = alamat + kota PT; `phone`, `email`, `npwp`, `tagline`, `website` dari
    Profil PT.
  - PT belum diselesaikan dan punya teks lama: seperti hari ini (teks lama menang), ditambah kunci jawaban
    `identity_conflicts`: daftar `{field, label, print_value, profile_value}` untuk field yang berbeda.
- `save_branding` hanya menerima lima field gambar/tanda tangan; field teks di isi permintaan ditolak 400
  "Nama, alamat, NPWP, dan kontak diubah di Profil PT."
- `PT_LAYER_KEYS = ("intro_text", "closing_note", "footer_text", "show_place_date", "place", "signature_slots",
  "watermark_text", "watermark_opacity")` — hanya kunci ini yang boleh disimpan pada lapisan PT.
- `get_template_cfg(doc_type, entity_id=None)` — urutan lapisan: bawaan kode → `__default__` grup → jenis dokumen grup
  → `__default__` PT → jenis dokumen PT. Tanpa `entity_id` hasilnya sama dengan hari ini.
- `save_template_cfg(doc_type, config, actor, entity_id="all")` — untuk PT: buang kunci di luar `PT_LAYER_KEYS`, simpan
  hanya yang berbeda dari hasil lapisan grup; `reset_template_cfg(doc_type, entity_id="all")` menghapus lapisan itu saja.
- `build_document` memanggil `get_template_cfg(doc_type, eid)`.
- Token baru `rekening_bank` ("Rekening bank pembayaran PT") di `PLACEHOLDERS`. Nilainya dari penyedia yang bisa
  diganti: `register_token_provider(name, async fn(entity_id, doc) -> str)`. Penyedia bawaan unit ini
  (`default_bank_text`): bila PT punya **tepat satu** `bank_accounts` `{entity_id, account_type: "bank", is_active ≠
  false}` → "{bank_name} {account_number} ({name})"; selain itu teks kosong. Unit PM-T2 mengganti penyedia ini dengan
  rekening tujuan pesanan. `build_document` menghitung nilai token sebelum `_apply_cfg_to_doc`.

`backend/services/inventory_service.py` (`render_order_html`): bila template tidak punya logo, pakai logo dan nama dari
`pdf_service.get_branding(entity_id dokumen)`; teks "Kain Nusantara" dihapus dari kode.

Endpoint (`/api/pdf`; izin tidak berubah: `pdf_template.view` / `pdf_template.manage`):

| Metode + path | Perubahan |
|---|---|
| `GET /branding/{entity_id}`, `PUT /branding/{entity_id}` | `entity_id` harus dalam cakupan pengguna (`entity_ctx` → `resolve_requested_entity`); di luar cakupan → 403. `"all"` → 400 "Pilih satu PT." |
| `POST /branding/{entity_id}/identity` (baru; `pdf_template.manage` **dan** `entity.update`) | Isi `{action: "pakai_profil" \| "salin_ke_profil", reason}`. `pakai_profil`: tandai selesai. `salin_ke_profil`: tulis `print_name`, alamat, telepon, email, NPWP, slogan, situs dari teks lama ke Profil PT lewat `validate_entity_input` (validasi KP-T1 berlaku), lalu tandai selesai. Jawaban = `get_branding` baru. Jejak `branding_identity_resolved` |
| `GET /templates/{doc_type}?entity_id=` | Menambah `scope` (`"all"` atau id PT), `pt_layer_keys`, `pt_override_keys` (kunci yang ditimpa PT itu), dan `group_config` (hasil tanpa lapisan PT) |
| `PUT /templates/{doc_type}?entity_id=`, `DELETE /templates/{doc_type}?entity_id=` | Tanpa `entity_id` = lapisan grup (perilaku hari ini). Dengan `entity_id` = lapisan PT; cakupan diperiksa |
| `GET /sample/{doc_type}`, `POST /preview` | `entity_id` lewat `resolve_requested_entity` |

Galat tambahan: 400 "Bagian ini hanya bisa diatur untuk semua PT: {daftar label kunci}." bila lapisan PT memuat kunci
di luar `PT_LAYER_KEYS`; 400 "Alasan wajib diisi." pada `…/identity`; 409 "Identitas kop PT ini sudah diselesaikan."

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan baru.

### Layar

Tempat: Pengaturan › Dokumen & Cetak › Template Dokumen (`PdfTemplateDesigner.jsx`, `PdfEditorTabs.jsx`) dan Profil PT
(`EntityDetailDrawer.jsx`).

- Bagian kop di perancang: isian "Nama Perusahaan", "Alamat", "Telepon", "NPWP", "Email", "Website", "Tagline"
  dibuang. Gantinya blok hanya-baca **Identitas di kop** (nama, alamat, NPWP, telepon, email, slogan, situs) dengan
  keterangan "Diambil dari Profil PT." dan tombol **Ubah di Profil PT**. Unggah logo, gambar kop, gambar footer, cap,
  dan tanda tangan tetap.
- Bila `identity_conflicts` tidak kosong: kotak kuning **Kop PT ini masih memakai teks lama** berisi tabel "Yang
  tercetak sekarang" / "Di Profil PT", dan dua tombol: **Pakai data Profil PT** dan **Salin teks kop ke Profil PT**
  (keduanya meminta alasan dan konfirmasi yang menyebut nama PT).
- Bagian naskah dan tanda tangan: pemilih **Berlaku untuk** — "Semua PT" atau satu PT. Saat satu PT dipilih, hanya
  isian `PT_LAYER_KEYS` yang aktif (label: "Teks pembuka", "Teks penutup", "Teks footer", "Tempat & tanggal sebelum
  tanda tangan", "Tempat", "Slot tanda tangan", "Tanda air"); isian lain tampil abu-abu dengan keterangan "Diatur
  untuk semua PT." Isian yang ditimpa PT diberi tanda "khusus PT ini" dan tombol **Kembali ke aturan semua PT**.
- Daftar token di bagian naskah memuat `{{rekening_bank}}` dengan keterangan "Rekening bank pembayaran PT. Kosong bila
  PT punya lebih dari satu rekening dan belum ada rekening tujuan di pesanan."
- Profil PT: tiga isian baru **Nama di kop surat** ("Kosongkan untuk memakai nama legal."), **Slogan**, **Situs web**.
- Memuat, galat, kosong: mengikuti perancang yang ada.

## Uji penerimaan

Persiapan bersama: seed lingkungan B; akun admin; `ent_ksc`, `ent_kanda`; satu pesanan penjualan per PT (fixture) untuk
dirender sebagai `invoice` dalam format HTML.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | Tanpa `document_branding` | `PATCH /api/entities/ent_kanda` `{"data": {"address": "Jl. Baru 9", "print_name": "KANDA TEKSTIL"}}`; `GET /api/pdf/branding/ent_kanda` | `company_name` = "KANDA TEKSTIL"; `address` memuat "Jl. Baru 9"; `identity_conflicts` kosong |
| U2 | B | `document_branding` `{entity_id: "ent_kanda", address: "Alamat Lama 1"}` disisipkan (data lama) | `GET /api/pdf/branding/ent_kanda`; render faktur `ent_kanda` | `address` = "Alamat Lama 1" (cetak tidak berubah saat dipasang); `identity_conflicts` memuat `address` dengan dua nilainya |
| U3 | B | seperti U2 | `POST …/branding/ent_kanda/identity` `{action: "pakai_profil", reason: "Alamat pindah"}`; render ulang | 200; HTML memuat alamat Profil PT, tidak memuat "Alamat Lama 1"; panggilan kedua → 409 |
| U4 | B | seperti U2, NPWP lama `"12"` (tidak sah) | `POST …/identity` `{action: "salin_ke_profil", reason: "x"}` | 400 dengan pesan NPWP dari KP-T1; Profil PT tidak berubah; belum ditandai selesai |
| U5 | B | — | `PUT /api/pdf/branding/ent_kanda` `{"company_name": "X"}` | 400 "Nama, alamat, NPWP, dan kontak diubah di Profil PT." |
| U6 | B | `PUT /api/pdf/templates/invoice` (grup) `{config: {closing_note: "Terima kasih.", place: "Bandung", show_place_date: true}}` | `PUT /api/pdf/templates/invoice?entity_id=ent_kanda` `{config: {closing_note: "Pembayaran ke {{rekening_bank}}", place: "Jakarta"}}`; render faktur kedua PT | Faktur `ent_kanda` memuat "Jakarta," dan "Pembayaran ke"; faktur `ent_ksc` memuat "Bandung," dan "Terima kasih." (PT lain tidak berubah) |
| U7 | B | seperti U6 | `PUT /api/pdf/templates/invoice?entity_id=ent_kanda` `{config: {paper_size: "A5"}}` | 400 "Bagian ini hanya bisa diatur untuk semua PT: …"; ukuran kertas `ent_kanda` tetap A4 |
| U8 | B | seperti U6 | `DELETE /api/pdf/templates/invoice?entity_id=ent_kanda`; render faktur `ent_kanda` | Memuat "Bandung," dan "Terima kasih." |
| U9 | B | `ent_kanda` punya tepat satu rekening bank `{bank_name: "BCA", account_number: "123", name: "BCA Operasional"}`; naskah penutup `ent_kanda` berisi `{{rekening_bank}}` | Render faktur `ent_kanda`; tambah rekening bank kedua; render lagi | Pertama memuat "BCA 123 (BCA Operasional)"; kedua tidak memuat "BCA 123" dan tidak memuat teks `{{rekening_bank}}` mentah |
| U10 | B | — | `PUT /api/pdf/templates/invoice` `{config: {closing_note: "{{rekening_bca}}"}}` | 400 "Placeholder tidak dikenal…" (perilaku lama tetap; `rekening_bank` kini termasuk yang sah) |
| U11 | B | Akun berperan `sales` (hanya `ent_ksc`) yang perannya diberi `pdf_template.view` dan `pdf_template.manage` | `GET /api/pdf/branding/ent_kanda`; `PUT /api/pdf/branding/ent_kanda` `{}`; `PUT /api/pdf/templates/invoice?entity_id=ent_kanda` | 403 ×3; `GET /api/pdf/branding/ent_ksc` → 200 |
| U12 | B | Template dasar surat jalan `ent_kanda` tanpa `logo_url` | Render lewat mesin lama (`render_order_html`) untuk pesanan `ent_kanda` | HTML tidak memuat "Kain Nusantara"; memuat nama PT Kanda |
| U13 | B | Baris `pdf_templates` lama tanpa `entity_id` (`doc_type: "invoice"`, `config.closing_note: "Lama"`) | Jalankan migrasi dua kali; render faktur `ent_ksc` sebelum dan sesudah | Baris ber-`entity_id: "all"`; jumlah baris tetap 1; HTML sebelum = HTML sesudah |
| U14 | layar (uji jalan) | Login admin; keadaan U2 | Buka Template Dokumen › kop untuk PT Kanda | Tidak ada isian teks identitas; kotak kuning dengan dua tombol; pemilih "Berlaku untuk" tersedia di bagian naskah |

## Langkah kerja

1. `backend/tests_mem/test_KPT6_cetak_per_pt.py`: U1–U13 (merah).
2. Tiga field Profil PT; `get_branding` dua keadaan; `save_branding` menolak teks; endpoint `…/identity`.
3. Lapisan PT pada `pdf_templates` (`entity_id`, `PT_LAYER_KEYS`), migrasi, `build_document`.
4. Token `rekening_bank` dan penyedia bawaan.
5. Penjaga cakupan PT pada lima endpoint; perbaikan mesin cetak lama.
6. Layar perancang dan Profil PT. Gate; laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (field `business_entities`, `pdf_templates.entity_id`, `document_branding`); `memory/PRD.md`;
`docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("Nama di kop surat", "Slogan").

## Di luar lingkup

- Rekening tujuan per pesanan, peruntukan rekening, dan instruksi bayar lengkap → PM-T1, PM-T2 (mengganti penyedia
  token `rekening_bank`).
- Memensiunkan mesin cetak lama dan koleksi `document_templates` (menjadikan satu mesin) → tidak ada unitnya; dicatat
  sebagai usulan di laporan. Unit ini hanya menghapus nama perusahaan yang ditulis mati.
- Tata letak (kertas, margin, huruf, warna, kolom) per PT → tidak diminta; tetap global.
- Penanda tangan sebagai butir kesiapan PT → KP-T2. Penomoran → KP-T5. Nama hub dan tab → KP-T9.

## Asumsi dan risiko

- `ASUMSI:` nama dagang di kop boleh berbeda dari nama legal, sehingga disediakan `print_name`; nama legal tetap
  dipakai faktur pajak dan dokumen hukum.
- `ASUMSI:` urutan lapisan menempatkan `__default__` PT di atas jenis dokumen grup; yaitu PT yang mengatur kota sekali
  untuk semua dokumennya tidak tertimpa aturan grup per jenis dokumen.
- `ASUMSI:` sampai PM-T2 ada, "rekening utama PT" hanya bisa ditentukan bila PT punya tepat satu rekening bank aktif;
  tidak ada penanda "utama" pada `bank_accounts` hari ini.
- `ASUMSI:` kunci unik lama pada `pdf_templates.doc_type` tidak ada di `backend/indexes.py`; bila ternyata ada di
  basis data nyata, migrasi menggantinya dengan kunci (`doc_type`, `entity_id`).
- `RISIKO:` kop berubah diam-diam bila teks lama diabaikan. Dicegah: teks lama tetap dipakai sampai pemilik memilih
  (U2). Membatalkan: kosongkan `identity_resolved_at`; lapisan PT dibuang dengan `DELETE`.
