# KP-T6 — Dokumen dan cetak per PT: satu sumber identitas, naskah dan tanda tangan per PT

- Commit awal: `eef7bb9` (dikerjakan) · digabung di atas `e13e29b` (KF-T8)        - Commit: `1ebbdaa`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-18, KP-19, KP-34 (spesifikasi `docs/blueprint/unit/KP-T6.md`; keputusan K-34 — isi rekening tujuan =
  PM-T1/PM-T2; `00` §4.1)

## Cek ulang "Keadaan sekarang"

Spesifikasi dibaca pada `3132cc4`; dicek ulang pada `eef7bb9`. Semua butir masih berlaku; beberapa baris bergeser.

| # | Hasil di `eef7bb9` |
|---|---|
| 1 | Berlaku. `pdf_service.py:216` (`get_branding`): `company_name`/`address`/`email`/`npwp` teks kop dulu, baru master PT; `phone`/`tagline`/`website` hanya dari `document_branding` |
| 2 | Berlaku. `pdf_service.py:247` (`save_branding`, daftar isian `:248`); `PdfEditorTabs.jsx:185` (`Nama Perusahaan`, input `:186`) — layar menyimpan juga nilai hasil rakitan (`PdfTemplateDesigner.jsx:169-177`), jadi PT yang pernah disimpan dari layar membawa salinan teks |
| 3 | Bergeser: `inventory_service.py:116` (`render_order_html`, dari 108), `logo_html` `:154`, "Kain Nusantara" `:157`; `entity_master_service.py:76` tetap |
| 4 | Bergeser: `pdf_service.py:151` (`get_template_cfg`, dari 143 — `:143` kini `_default_effective`), `:169` (`save_template_cfg`) |
| 5 | Berlaku. `pdf_service.py:19` |
| 6 | Berlaku. `pdf_service.py:49` (13 token), `:72` (`render_text`); `pdf_resolvers.py:1037` (`resolve_invoice` tidak membaca `bank_accounts`) |
| 7 | Berlaku. `routers/pdf.py:259`, `:265` — tanpa pemeriksaan cakupan |
| 8 | Berlaku. `routers/pdf.py:131` (`get_sample`), `:278` (`entity_id = payload.entity_id`). **Tambahan ditemukan:** `GET /render/{doc_type}/{source_id}` (`:118`) juga memakai `entity_id` mentah dari alamat untuk kop — dokumen PT A bisa dicetak dengan kop + gambar tanda tangan PT B (kelas temuan sama, N1; diperbaiki, lihat Menyimpang 2) |
| 9 | Berlaku. `pdf_service.py:274` (`brand_sig`) — tidak diubah |
| Dipertahankan | `diff_cfg` bergeser ke `:121` (dari 132); `unknown_tokens` `:68` — berlaku, tetap |
| `ASUMSI` indeks | Benar: `backend/indexes.py` tidak membuat indeks apa pun pada `pdf_templates`; skrip migrasi melaporkan/menghapus indeks unik `doc_type`-saja bila ternyata ada di basis data |
| Unit selesai terkait | KP-T1: `validate_entity_input` dipakai `salin_ke_profil` (pesan NPWP sama). KP-T2: kesiapan "Kop & logo"/"Penanda tangan" membaca gambar & tanda tangan `document_branding` — tidak berubah. KP-T5: tidak bersinggungan (penomoran). PR-T5: izin `pdf_template.view/manage` dan `document.print` tidak berubah (tidak ada pasangan baru) |

## KP-18 / KP-19 / KP-34 — kop, lapisan PT, token rekening

- Berlaku di HEAD: ya, semua (tabel di atas; bukti merah di bawah).
- Akar masalah: identitas kop punya dua sumber (teks `document_branding` menang atas Profil PT, telepon/slogan/situs
  hanya di kop); konfigurasi template hanya berkunci `doc_type` sehingga naskah/kota/tanda tangan satu untuk semua PT;
  tidak ada token rekening; endpoint kop/contoh/pratinjau/cetak memakai `entity_id` mentah.
- Perubahan perilaku (sebelum → sesudah):
  - **Profil PT = satu sumber identitas kop.** `business_entities` + `print_name` ("Nama di kop surat", kosong = nama
    legal), `tagline` ("Slogan"), `website` ("Situs web") — di `EDITABLE_FIELDS`, `uniform_entity`, dipangkas di
    `validate_entity_input`. `get_branding`: PT **sudah diselesaikan** (`identity_resolved_at`) atau tanpa teks lama →
    nama `print_name`/`legal_name`, alamat = alamat + kota, NPWP, telepon, email, slogan, situs dari Profil PT; PT
    **belum diselesaikan dan punya teks lama** → rumus lama persis (teks lama menang, `legacy_identity`) + `identity_conflicts`
    `[{field, label, print_value, profile_value}]` untuk isian yang berbeda. Kunci jawaban tambahan: `identity_source`
    (`profil` | `teks_lama`), `identity_resolved_at`, `identity_resolved_by`.
  - `save_branding` hanya menerima `logo_b64`, `header_image_b64`, `footer_image_b64`, `stamp_b64`, `signatures`; isian
    teks lama di isi permintaan → 400 "Nama, alamat, NPWP, dan kontak diubah di Profil PT."
  - **`POST /api/pdf/branding/{entity_id}/identity`** (izin `pdf_template.manage` **dan** `entity.update`; PT dalam
    penugasan): `{action: "pakai_profil" | "salin_ke_profil", reason}`. Alasan kosong → 400 "Alasan wajib diisi.";
    sudah diselesaikan → 409 "Identitas kop PT ini sudah diselesaikan."; `salin_ke_profil` menulis teks lama yang
    **terisi** ke Profil PT lewat `validate_entity_input` (KP-T1) **sebelum** menandai selesai (gagal → 400, tidak ada
    yang berubah). Penandaan = ubah bersyarat `identity_resolved_at` kosong (kalah balapan → 409). Jejak
    `branding_identity_resolved` (+ `entity_updated` bila Profil PT ikut berubah). Jawaban = `get_branding` baru.
  - **Lapisan PT template.** `pdf_templates.entity_id` (`"all"` | id PT; baris lama tanpa `entity_id` dibaca sebagai
    `"all"`). Urutan: bawaan kode → `__default__` grup → jenis grup → `__default__` PT → jenis PT; tanpa `entity_id` hasil
    sama dengan hari ini. `PT_LAYER_KEYS = (intro_text, closing_note, footer_text, show_place_date, place,
    signature_slots, watermark_text, watermark_opacity)`; lapisan PT menyimpan hanya yang berbeda dari lapisan di
    bawahnya; kunci lain bernilai **berbeda** dari aturan semua PT → 400 "Bagian ini hanya bisa diatur untuk semua PT:
    {label}." (label Indonesia, bukan nama field). `reset_template_cfg` membuang lapisan itu saja. `build_document` memakai
    `get_template_cfg(doc_type, eid)`. Indeks unik wajib baru `pdf_templates.uq_doctype_entity` (`REQUIRED_UNIQUE_INDEXES`, 9 → 10).
  - Endpoint `GET/PUT/DELETE /api/pdf/templates/{doc_type}?entity_id=`: tanpa `entity_id`/`all` = lapisan grup (perilaku
    lama); dengan `entity_id` = lapisan PT (`resolve_requested_entity` → 403 di luar penugasan). GET menambah `scope`,
    `pt_layer_keys`, `pt_override_keys`, `group_config`, `key_labels`; PUT/DELETE menjawab bentuk yang sama.
  - **Token `{{rekening_bank}}`** ("Rekening bank pembayaran PT") + `PLACEHOLDER_NOTES`. `register_token_provider(name,
    fn)`; bawaan `default_bank_text`: tepat satu `bank_accounts {entity_id, account_type: "bank", is_active ≠ false}` →
    "{bank_name} {account_number} ({name})", selain itu "". Dihitung sebelum `_apply_cfg_to_doc`, hanya bila naskah
    memakai tokennya. Token tak dikenal tetap ditolak (pesan kini memuat `{{rekening_bank}}`).
  - **Cakupan PT (N1)**: `GET/PUT /branding/{entity_id}` (+ `…/identity`) → `"all"` 400 "Pilih satu PT.", di luar penugasan
    403; `GET /sample/{doc_type}` dan `POST /preview` lewat `resolve_requested_entity`; pratinjau dengan `source_id` milik PT
    lain → 400 "Dokumen contoh milik PT lain. Pilih dokumen PT ini."; `GET /render/...` → kop = PT pemilik dokumen.
  - **Mesin cetak lama**: `render_order_html` tanpa `logo_url` di template → logo (bila ada) + nama dari
    `get_branding(entity_id pesanan)`; "Kain Nusantara" dihapus dari kode.
  - **Layar** (Pengaturan › Dokumen & Cetak › Template Dokumen › Desainer PDF; detail PT): lihat "Cek layar".
- Data: field baru `business_entities.print_name|tagline|website`, `document_branding.identity_resolved_at|_by|_action|
  _reason`, `pdf_templates.entity_id` + indeks unik wajib. Skrip `scripts/migrate_kpt6_template_pt.py` (bawaan =
  `--dry-run`, hanya lapor; `--apply` mengisi `entity_id: "all"` pada baris tanpa PT, melewati jenis dokumen yang barisnya
  kembar (H6, dilaporkan), menghapus indeks unik `doc_type`-saja bila ada; argumen salah → keluar 2 sebelum menyentuh
  basis data). **Tidak dijalankan terhadap database mana pun selain database tiruan** (H3); keluaran di lingkungan B:
  `bukti/KP-T6/skrip_migrasi_lingkungan_b.log`. Tidak ada penyalinan otomatis teks kop ke Profil PT.
- Berkas berubah:

| Berkas | Isi |
|---|---|
| `backend/services/pdf_service.py` | Token `rekening_bank`, `PLACEHOLDER_NOTES`, `PT_LAYER_KEYS`, `TEMPLATE_KEY_LABELS`; lapisan (`_layer_filter`, `_group_cfg`, `_pt_base`, `_with_pt_layers`, `get_template_cfg(…, entity_id)`, `save/reset_template_cfg(…, entity_id)`, `pt_override_keys`, `template_meta(…, entity_id)`); penyedia token; identitas kop (`profile_identity`, `legacy_identity`, `get_branding`, `save_branding`, `legacy_to_profile`, `resolve_identity`); `build_document`/`render_document` (`override_layer`) |
| `backend/routers/pdf.py` | Cakupan PT (`_one_pt`, `_layer_scope`), `?entity_id=` pada template, `POST /branding/{entity_id}/identity`, contoh/pratinjau/cetak lewat `resolve_requested_entity`/PT dokumen, `PreviewReq.layer` |
| `backend/services/entity_lifecycle_service.py`, `entity_provisioning_service.py` | Tiga isian Profil PT (daftar ubah, bentuk seragam, pangkas) |
| `backend/services/inventory_service.py` | `render_order_html` tanpa nama tertulis mati |
| `backend/indexes.py` | `pdf_templates.uq_doctype_entity` wajib |
| `scripts/migrate_kpt6_template_pt.py` | Baru — skrip lapor / `--apply` |
| `scripts/guardrails/verify_atomic_claim.py` | Satu baris `REVIEWED` untuk endpoint `…/identity` (penjaga INV-ATOMIC-01: endpoint dua koleksi baru) |
| `frontend/src/features/pdf/PdfTemplateDesigner.jsx`, `PdfEditorTabs.jsx`, `PdfScriptTab.jsx` | Layar perancang |
| `frontend/src/features/settings/entities/EntityDetailDrawer.jsx` | Tiga isian Profil PT |
| `frontend/src/config/auditLabels.js` | Label `branding_identity_resolved` |
| `backend/tests_mem/test_KPT6_cetak_per_pt.py` | Baru — U1–U13 (+U4b, U8b, U11b) |
| `backend/tests/test_bp_KPT6_cetak_per_pt.py` | Baru — lapis A (ditulis, belum dijalankan) |
| `frontend/src/features/__tests__/kpt6CetakPerPt.test.js` | Baru — 6 uji komponen |
| `backend/tests_mem/test_PK14_indeks_wajib.py` | Jumlah indeks wajib 9 → 10 + alasan |
| `backend/tests_mem/sapuan_izin_harapan.json` | `isi_contoh` `GET /api/pdf/branding/{entity_id}` (PT seed; `x` kini 403 cakupan, bukan izin) |
| `backend/tests/test_iter294_numbering_pdf.py`, `backend/backend_test_pdf_fase3.py` | Uji lama disesuaikan (lihat "Uji lama") |
| `ENTITY_REGISTRY.md`, `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`, `CODEBASE_MAP.md` | Field/koleksi (`pdf_templates`, `document_branding` didaftarkan), baris KP-T6, istilah "Nama di kop surat", "Slogan", "Identitas di kop", "Berlaku untuk"; peta dibangkitkan ulang |

- Commit: belum (instruksi).
- Pengujian: lihat tabel di bawah.
- Bukti UI: belum diuji jalan di peramban (U14); uji komponen jest menggantikan sebagian.
- Fixture disiapkan langsung vs proses bisnis dijalankan: fixture = pesanan penjualan per PT, `document_branding` berteks
  lama (U2, U4, U4b), rekening bank (U9), izin `pdf_template` peran `sales` (U11), template dasar Kanda (U12), baris
  `pdf_templates` bentuk lama (U13); alur lewat API = PATCH Profil PT, GET/PUT kop, `…/identity`, PUT/DELETE template
  grup/PT, render faktur HTML, pratinjau, contoh, surat jalan mesin lama, skrip migrasi (fungsi `jalankan`).
- Dampak pada modul terkait: semua pemanggil `get_branding` (dokumen cetak, e-sign, kirim WA, kartu warna, cetak jejak,
  materi pemasaran) kini membaca identitas dari Profil PT untuk PT tanpa teks lama — PT dengan teks lama tercetak
  persis seperti sebelumnya sampai diselesaikan. Kop untuk PT tanpa teks lama kini **menambah** telepon/slogan/situs bila
  Profil PT mengisinya (dulu hanya dari kop). Konten e-sign tidak berubah (hash dihitung sebelum template).
- Keterbatasan / yang belum diuji: U14 (peramban); lapis A (keunikan & balapan di MongoDB asli, kop data acuan, skrip di
  data acuan).
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_KPT6_cetak_per_pt.py` (lingkungan B). Merah = berkas uji dijalankan di salinan `git archive
eef7bb9` (backend + scripts lama utuh): **16 gagal / 16** (`bukti/KP-T6/tests_mem_KPT6_merah_kode_lama.log`). Hijau di kode
baru: **16/16** (+ `test_PK14_indeks_wajib.py` 6/6; `…_hijau_kode_baru.log`).

| ID | Lapis | Merah di lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | ya — `print_name` dibuang PATCH, kop = nama legal ("Kanda Fabric") | Lulus — "KANDA TEKSTIL", alamat "Jl. Baru 9, Jakarta", tanpa selisih |
| U2 | B | ya — tidak ada `identity_conflicts` | Lulus — alamat "Alamat Lama 1" (cetak sama), selisih `address` berisi dua nilai + label |
| U3 | B | ya — 404 (endpoint belum ada) | Lulus — alasan kosong 400; 200; HTML memuat "Jl. Baru 9" + "KANDA TEKSTIL", tanpa "Alamat Lama 1"; ulang 409; jejak beralasan |
| U4 | B | ya — 404 | Lulus — 400 pesan NPWP KP-T1; Profil PT identik; belum ditandai |
| U4b (tambahan) | B | ya — 404 | Lulus — salin berhasil: alamat tanpa akhiran kota, NPWP, telepon; `print_name` tetap; tanpa selisih; ditandai |
| U5 | B | ya — 200, `company_name: "X"` tersimpan | Lulus — 400 pesan persis; tanda tangan tetap bisa disimpan |
| U6 | B | ya — PUT `?entity_id` = lapisan grup, token `rekening_bank` 400 | Lulus — Kanda "Jakarta, …" + "Pembayaran ke"; KSC "Bandung, …" + "Terima kasih."; tidak saling bocor; GET `scope`/`pt_override_keys`/`group_config` |
| U7 | B | ya — 200, kertas A5 tersimpan di lapisan grup | Lulus — 400 "Bagian ini hanya bisa diatur untuk semua PT: Ukuran kertas."; Kanda tetap A4; lapisan PT utuh |
| U8 | B | ya — DELETE `?entity_id` menghapus lapisan grup | Lulus — Kanda kembali "Bandung," + "Terima kasih."; grup utuh |
| U8b (tambahan) | B | ya | Lulus — urutan lapisan: `__default__` PT (Depok) di atas jenis grup (Bandung); jenis PT (Jakarta) di atas `__default__` PT; KSC tetap Bandung |
| U9 | B | ya — token ditolak 400 | Lulus — "BCA 123 (BCA Operasional)"; rekening kedua → kosong, tanpa token mentah |
| U10 | B | ya — pesan tidak memuat `{{rekening_bank}}` | Lulus — 400 "Placeholder tidak dikenal…", `rekening_bank` di daftar sah & `GET /templates` |
| U11 | B | ya — 200 ×3 | Lulus — 403 ×3 (akun `sales` hanya `ent_ksc`, izin `pdf_template.view/manage` diberikan); KSC 200; `all` 400 "Pilih satu PT." |
| U11b (tambahan) | B | ya — contoh PT lain 200 | Lulus — contoh/pratinjau PT lain 403; pratinjau dokumen KSC dengan PT Kanda 400; cetak dokumen KSC `?entity_id=ent_kanda` tetap kop KSC |
| U12 | B | ya — `<h1>Kain Nusantara</h1>` | Lulus — tanpa "Kain Nusantara" (juga huruf kecil), memuat nama kop Kanda |
| U13 | B | ya — skrip belum ada | Lulus — lapor tidak menulis; tulis ×2 → 1, 0; satu baris `entity_id: "all"` (config/versi utuh); HTML sebelum = sesudah ("Lama" terbaca sebelum migrasi) |
| U14 | layar | ya — 6/6 uji komponen gagal di `src` lama | Uji komponen 6/6 lulus (`bukti/KP-T6/jest_KPT6.log`); **uji jalan peramban belum** |
| Lapis A (tambahan) | A | — | `backend/tests/test_bp_KPT6_cetak_per_pt.py`: indeks `uq_doctype_entity` ada + 6 simpan lapisan PT bersamaan → satu baris; kop data acuan jujur (teks lama tercetak / Profil PT sama); skrip mode lapor tidak menulis — **ditulis, belum dijalankan** |

`tests_mem` seluruhnya: sebelum **762 lulus / 2 dilewati / 2 xfail** → sesudah **778 / 2 / 2** (+16 KP-T6;
`bukti/KP-T6/tests_mem_sebelum_sesudah.log`).

Jest (`bukti/KP-T6/jest_KPT6.log`): suite baru 6/6 lulus, 6/6 gagal di `src` lama. Seluruh suite (`src/config`,
`src/features`, `src/hooks`, `src/components`): HEAD **632 uji lulus** (116 suite) → KP-T6 **638 lulus** (117 suite; +1 suite baru = 6 uji); 35 suite gagal dimuat di keduanya
(daftar sama; `@radix-ui`/`cmdk` tidak termuat lokal — kendala lingkungan). `phase4R6.test.js` (detail PT) dan
`phase3P8Activation.test.js` dijalankan dengan tiruan pemilih lokal: hasil sama di HEAD dan KP-T6 (phase4R6 lulus;
phase3P8 1 gagal di keduanya — uji gerbang Desainer PDF dengan tiruan, tidak terkait). ESLint berkas layar yang berubah:
0 galat (1 peringatan lama `eslint-disable` tak terpakai).

Sapuan izin berjalan `sapuan_izin.py --awalan /api/pdf` (lingkungan B, 13 rute, 5 akun): 0 pelanggaran
(`bukti/KP-T6/sapuan_izin_api_pdf.log`).

## Uji lama yang disesuaikan

| Berkas | Perubahan | Alasan |
|---|---|---|
| `backend/tests/test_iter294_numbering_pdf.py::test_branding_extra_fields` | PUT kop berisi slogan → 400; slogan/situs lewat `PATCH /api/entities`; bila kop PT masih teks lama, selisih `tagline`/`website` dilaporkan; dipulihkan sesudahnya | Perilaku yang sengaja diubah (U5) |
| `backend/backend_test_pdf_fase3.py` langkah 8–9 | PUT teks → 400; simpan & periksa logo saja (dulu menulis "PT Uji Coba" ke kop KSC data acuan) | idem |
| `backend/tests_mem/test_PK14_indeks_wajib.py` | 9 → 10 indeks wajib | Indeks baru |

Dua berkas pertama tidak dijalankan (butuh MongoDB asli / backend berjalan).

## Penjaga

| Penjaga | Sebelum (`eef7bb9`) | Sesudah |
|---|---|---|
| `hitung_penjaga.sh` (16 penjaga) | auth 28 · ui_standard 15 · i18n 109 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · lainnya 0 | **sama persis** (ui_standard sempat 18 → dibetulkan: huruf < 12 px, tombol tanpa kelas baku, `!py`) |
| `verify_role_gate_ui.py` | PASS 31 cek | PASS 31 cek |
| `audit_config_wiring.py --strict` (salinan berjalur `$W`) | keluar 0, bersih | keluar 0, bersih |
| 26 penjaga statik lain (`statik_cmds`, tanpa backend/database) | — | sama, kecuali `verify_atomic_claim` sempat BELUM DITINJAU 95 → 96 (endpoint `…/identity` dua koleksi) → dicatat di `REVIEWED` → 95 (sama dengan HEAD; penjaga itu dan uji-dirinya sudah merah di HEAD); `verify_escape_layers` jumlah cek +1 |

Rincian: `bukti/KP-T6/penjaga_sebelum_sesudah.log`.

## Cek layar

Acuan `docs/KN_37_STANDAR_UI_GUDANG.md`. Kelas `data-table head-wrap` / `col-sticky-end` belum ada di worktree ini —
tidak diperlukan (tidak ada tabel lebar baru); tabel selisih memakai pola setara (`table-fixed` + `break-words`).
Desainer PDF hanya untuk desktop (`DesktopOnlyNotice` di Template Dokumen, tidak berubah). **Belum dipotret** di
1280/1024/390 px.

| Butir | Desainer PDF — tab Kop Surat | Desainer PDF — "Berlaku untuk" + tab lain | Profil PT (detail PT) |
|---|---|---|---|
| 1 Tabel melebihi kartu | Tabel selisih 3 kolom `table-fixed`, sel `break-words`; blok identitas `grid-cols-[96px_minmax(0,1fr)]` | — (tidak ada tabel baru) | — |
| 2 `section-card` tanpa bantalan | Tidak ada kartu baru; blok di dalam `section-body` berbingkai + `px-3 py-2` | Idem | Idem (isian di kartu yang ada) |
| 3 Kepala kartu padat | "Identitas di kop" + satu tombol (`flex-wrap`) | Pemilih "Berlaku untuk" di bilah alat (bukan kepala kartu); keterangan lapisan di baris sendiri | — |
| 4 Tombol mati tanpa alasan | Tombol pilihan teks lama disembunyikan bila tanpa akses + alasan tertulis "Pemilihan butuh akses ubah Template PDF dan Profil PT."; mati sesaat hanya saat memproses | "Setelan Pabrik/Ikuti Bawaan/Kembali ke aturan semua PT" dan "Unduh PDF" yang mati kini diberi alasan tertulis di bawah bilah alat; isian yang dikunci di lapisan PT berketerangan "Diatur untuk semua PT." | Isian mati untuk PT terarsip/tanpa izin: perilaku lama, tidak diubah |
| 5 Status tanpa ikon | "Diambil dari Profil PT." (ikon centang, hijau) / "Masih memakai teks kop lama…" (ikon peringatan, kuning); kotak kuning berikon; tanda "khusus PT ini" = `status-pill` + ikon + warna | idem | — |
| 6 Daftar panjang tanpa cari | — | Pemilih PT/jenis dokumen yang ada (`KNSelect`, jenis dokumen `searchable`) | — |
| 7 Teks bertentangan dengan izin | Tombol tampil hanya bila `can(pdf_template.manage)` + `can(entity.update)` (= server); tidak ada teks "bukan wewenang" | Teks lapisan menyebut apa yang bisa diatur per PT (= `PT_LAYER_KEYS` server) | — |
| 8 Keadaan kosong ganda | Isian identitas kosong = "—" satu per baris; kotak selisih hanya bila ada selisih | Keadaan kosong pratinjau lama (satu) | — |

Lain-lain: huruf baru ≥ 12 px (`text-fs-12/13`), warna lewat token `kn-*`, tombol kelas baku (`btn-primary`,
`btn-secondary`, `secondary-button btn-sm`, `link-button btn-sm`), konfirmasi lewat `askReason` (alasan wajib, judul
menyebut PT). Label "Entitas (PT)" di bilah alat diganti "PT" (L2); daftar kunci "menimpa/khusus PT ini" di keterangan
lapisan memakai label isian (L1), bukan nama field.

## Menyimpang dari blueprint

1. **Kunci di luar `PT_LAYER_KEYS` pada lapisan PT**: spesifikasi menyebut keduanya "buang kunci di luar `PT_LAYER_KEYS`"
   dan "400 bila lapisan PT memuat kunci di luar `PT_LAYER_KEYS`". Diterapkan: kunci di luar yang nilainya **sama** dengan
   aturan semua PT dibuang diam-diam (layar mengirim konfigurasi penuh); yang **berbeda** → 400 (U7).
2. **Cetak (`GET /api/pdf/render/…`) ikut dipagari** (tidak ada di tabel endpoint): kop = PT pemilik dokumen; `entity_id`
   permintaan hanya untuk dokumen tanpa PT dan harus dalam penugasan. Celah yang sama dengan butir 7–8 (N1).
3. **Mode lama hanya bila teks lama ada dan belum diselesaikan; nilainya rumus lama persis** — termasuk telepon/slogan/situs
   kosong bila kop lama tidak mengisinya (spesifikasi: "seperti hari ini"); `print_name` baru berlaku sesudah diselesaikan.
4. **`salin_ke_profil`**: hanya teks lama yang terisi yang disalin (yang kosong tidak menghapus Profil PT); nama kop sama
   dengan nama legal → `print_name` dikosongkan; akhiran ", {kota PT}" pada alamat dibuang (kop mencetak alamat + kota,
   supaya kota tidak tercetak dua kali). Validasi dulu, lalu tanda selesai bersyarat, lalu Profil PT ditulis.
5. **Pratinjau perancang** `POST /preview` menerima `layer: "all"`: saat menyunting aturan semua PT, lapisan PT terpilih
   tetap diterapkan di atas `config` (L6 — pratinjau = yang tercetak). Tanpa `layer` perilaku lama (config paling atas).
6. **Pratinjau dengan `source_id`** milik PT lain dari `entity_id` → 400 "Dokumen contoh milik PT lain. Pilih dokumen PT ini."
7. Tambahan jawaban: `identity_source`, `key_labels`; field `identity_resolved_action`/`_reason` di `document_branding`;
   `PLACEHOLDER_NOTES` dikirim sebagai `note` pada daftar token.
8. Indeks unik (`doc_type`, `entity_id`) didaftarkan **wajib** (`REQUIRED_UNIQUE_INDEXES`, pola KP-T5 `uq_kind_entity`): data
   kembar di basis data nyata → aplikasi menolak mulai (mode `enforce`) — skrip migrasi melaporkannya lebih dulu (H6).
9. Tombol "Ubah di Profil PT" membuka Badan Usaha & Akses › Badan Usaha; detail PT terbuka otomatis hanya bila PT itu PT
   aktif (aturan preset KP-T2 yang ada).
10. Label isian lapisan PT di layar: "Teks pembuka"/"Teks penutup" (dulu "Naskah pembuka/penutup"), "Tanda air" (dulu
    "Watermark"), "Teks Footer", "Tempat", "Tempat & tanggal sebelum tanda tangan" — mengikuti daftar label spesifikasi.

## Asumsi

- `ASUMSI` spesifikasi dipakai apa adanya: `print_name` untuk nama dagang; `__default__` PT di atas jenis dokumen grup;
  "rekening utama" hanya bila tepat satu rekening bank aktif; tidak ada indeks unik lama di `indexes.py`.
- "Punya teks lama" = salah satu dari tujuh isian teks lama di `document_branding` terisi (bukan kosong/spasi). PT yang
  teks lamanya sama persis dengan Profil PT tetap di mode teks lama tanpa selisih (kotak kuning muncul begitu Profil PT
  berubah) — sesuai spesifikasi.
- PT terarsip: admin pun tidak bisa membuka kop/lapisan PT-nya (penugasan hanya PT aktif) → 403.
- Simpan lapisan PT = mengganti isi lapisan itu dengan perbedaan konfigurasi yang dikirim (sama dengan lapisan jenis
  dokumen grup hari ini), bukan menggabung.

## Hambatan lingkungan

- Jest lokal: 35 suite lama gagal dimuat (`@radix-ui`/`cmdk`), sama di HEAD dan KP-T6; suite baru meniru pemilih, `Tabs`,
  dan `Switch`.
- Tidak ada penjaga runtime, skrip migrasi, atau POC yang dijalankan terhadap backend :8001 / database `backend/.env`;
  penjaga statik dijalankan dengan `MONGO_URL`/`API_BASE` ke port mati.

## Usulan

- Memensiunkan mesin cetak dasar (`render_order_html` + `document_templates`, Template Dokumen › "Kop & tata letak
  dasar") menjadi satu mesin `pdf_service` — tidak ada unitnya; teks kop lama di `document_templates.header` (benih "KAIN
  NUSANTARA — …") masih data, bukan kode.

## Penggabungan

Dikerjakan di `eef7bb9`; digabung di atas `e13e29b`. Bentrok: jumlah indeks wajib (PK-40 menambah lima) →
uji PK-14 lapis B = 9 + 5 + 1 dan lapis A = 15; `CODEBASE_MAP.md` dibangkitkan ulang. tests_mem 1235; jest
`kpt6CetakPerPt`, `kpt5PenomoranDokumen`, `kpt1ProfilPt` 23/23; `verify_atomic_claim` tetap 95 (garis dasar).

Lapis A (lingkungan A): `tests/test_bp_KPT6_cetak_per_pt.py` — 3 uji **lulus** (indeks `uq_doctype_entity` + 6 simpan
lapisan PT bersamaan → satu baris; kop data acuan jujur; skrip mode lapor tidak menulis).

## Cek layar (potret integrator)

Dipotret di lingkungan A (`admin@`, data acuan, 1280 px): Template Dokumen › Desainer PDF (bilah "Jenis dokumen · PT ·
Berlaku untuk", alasan "Setelan Pabrik" mati tertulis) dan tab Kop Surat (blok "Identitas di kop" dengan status
"Diambil dari Profil PT." berikon centang, tombol "Ubah di Profil PT"). Tidak ada temuan baru dari daftar periksa.
Bukti: `bukti/KP-T6/layar_desainer_pdf_1280.png`, `layar_kop_surat_identitas_1280.png`. Catatan: tab "Kop & tata letak
dasar" (mesin cetak lama) masih menampilkan teks kop benih "KAIN NUSANTARA — …" — data lama, lihat "Usulan".

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli), tiap jalan sesudah `restore_demo` (data acuan; tiga skrip seed yang sama
seperti garis dasar gagal).

| Jalan | Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|---|
| 1 (`c9cf10f` — KF-T8, KP-T6, KP-T8, PK-30) | `--quick` | 16 FAIL | 16 | 3 (ganti nama + 2 balapan, lihat bawah) | 2 |
| 1 (`c9cf10f`) | `--ci` | 42 FAIL | 43 | 2 (ganti nama + 1 balapan) | 2 |
| 2 (`27f0853` — + perbaikan penjaga `c2cc412`, PK-42 `5e747b2`, PM-T1 `fd606e5`, cek visual) | `--quick` | 14 FAIL | 16 | 1 (ganti nama) | 2 (`config_wiring` + uji-diri) |
| 2 (`27f0853`) | `--ci` | 41 FAIL | 43 | 1 (ganti nama) | 2 |

- **`guard:page_tabs`** hanya berganti nama sejak MN-T1 (INV-UI-12 → INV-UI-12/13/14); merahnya sama dengan garis dasar
  (INV-UI-12 `wms/InventoryStockView.jsx`, berkas lama).
- Jalan 1: **`guard:role_gate_ui`** dan **`guard:role_label`** merah palsu karena balapan di kolam statik paralel —
  uji-diri `role_gate_ui` menulis probe sementara `features/__poc_role_gate_probe.jsx` ke `src` yang dipindai penjaga lain.
  Bukan dari unit mana pun; diperbaiki di `c2cc412` (uji-diri menghitung probe di memori; pemindaian melewati probe
  penjaga lain). Jalan 2 keduanya hijau.
- Penjaga statik per hitungan (`hitung_penjaga.sh`) tidak naik; PK-42 menurunkan `verify_ui_standard` 15 → 13 dan
  `audit_i18n_id` 109 → 104.


## Titik henti

- **H3** — `scripts/migrate_kpt6_template_pt.py --apply` (dan mode lapor) di data acuan/nyata = keputusan pemilik. Tanpa
  migrasi, kode tetap benar (baris tanpa `entity_id` dibaca sebagai semua PT).
- **H3** — memilih sumber identitas kop tiap PT nyata yang masih punya teks lama = pemilik, lewat layar (tidak ada salinan
  otomatis).

## Yang perlu direview

- Menyimpang 1 (tafsir buang-vs-tolak), 2 (cetak ikut dipagari), 3 (rumus lama persis), 4 (aturan salin), 8 (indeks wajib).
- U14 uji jalan + potret 1280/1024/390 px; lapis A belum dijalankan.
