# KP-T3 — Aturan Persetujuan: buang pilihan palsu, tampilkan jenjang efektif per PT

| | |
|---|---|
| Gelombang | Jalur konfigurasi perusahaan (U) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | KF-T1 |
| Menutup temuan | KP-03, KP-04, KP-08 |
| Keputusan | K-51 (dipersiapkan; pemakaiannya di KP-T4); `00` §4.1 |
| Standar | §3.1 (Z1, Z6), §3.4 (N1), §4 (L1, L2, L5, L6), §6 |
| Lingkungan uji | B |

## Tujuan

Layar Aturan Persetujuan hanya menawarkan pilihan yang benar-benar dipakai mesin, menolak peran yang tidak ada, dan
menunjukkan untuk tiap PT jenjang mana yang sungguh berlaku — termasuk peringatan bila aturan khusus PT membuat
sebagian nilai lolos tanpa persetujuan.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Pilihan penyetuju di layar: "Tanpa persetujuan", "Manajer", "Admin", "Owner". Server menerima `owner` | `frontend/src/features/settings/approvalRulesConstants.js:13` (`ROLES`); `backend/routers/approval_rules.py:17` (`VALID_ROLES`) |
| 2 | Peran `owner` tidak ada di registry peran; nilai yang tidak dikenal diberi peringkat Manajer, jadi "wajib Owner" lolos oleh Manajer mana pun | `backend/role_registry.py:355` (`required_rank`); `backend/role_registry.py:316` (`_DEFAULT_REQUIRED_RANK`) |
| 3 | Jenis aturan "Diskon (%)" bisa dipilih dan dua aturan diskon ikut dibenihkan | `frontend/src/features/settings/approvalRulesConstants.js:10` (`discount`); `backend/routers/approval_rules.py:16` (`VALID_DOC_TYPES`); `backend/services/config_service.py:167` (`DEFAULT_APPROVAL_RULES`) |
| 4 | Penilai aturan hanya dipanggil untuk `sales_order`, `purchase_order`, `purchase_requisition`; tidak ada pemanggil ber-`doc_type` `discount` | `backend/routers/sales_orders.py:362` (`evaluate_approval`); `backend/routers/purchase_orders.py:586` (`build_approval_chain`); `backend/services/purchase_requisition_service.py:185` (`evaluate_approval`) |
| 5 | Bila PT punya **satu saja** aturan aktif untuk sebuah jenis dokumen, seluruh aturan grup jenis itu tidak dipakai untuk PT tersebut | `backend/services/config_service.py:323` (`pool`) |
| 6 | Validasi simpan hanya memeriksa `max_amount > min_amount`; celah dan tumpang-tindih rentang tidak diperiksa | `backend/routers/approval_rules.py:42` (`_validate`) |
| 7 | Tingkat kedua dan seterusnya berasal dari kunci `approval.extra_levels` (tabel bebas; isi `role` tidak divalidasi) | `backend/services/config_service.py:362` (`extra_levels`); `backend/config_catalog_core.py:342` (`approval.extra_levels`) |
| 8 | Layar menulis "Semua entitas" untuk aturan grup | `frontend/src/features/settings/ApprovalRulesSettings.jsx:258` (`entityName`); `frontend/src/features/settings/ApprovalRuleForm.jsx:13` (`label`) |
| 9 | Sudah ada endpoint penilai untuk satu nilai, tanpa tampilan jenjang | `backend/routers/settings.py:102` (`evaluate_approval_endpoint`) |

Contoh akibat butir 5 pada data benih: aturan grup PO = "≥ Rp100.000.000 → Manajer". PT menambah satu aturan
"≥ Rp500.000.000 → Admin". PO Rp200.000.000 milik PT itu lolos tanpa persetujuan.

## Perubahan

### Data

`approval_rules` mendapat dua field opsional (ditulis hanya oleh skrip migrasi):

| Field | Tipe | Arti |
|---|---|---|
| `migrated_from_role` | teks | Nilai `required_role` lama yang tidak dikenal (mis. `owner`) sebelum diganti |
| `retired_reason` | teks | Alasan aturan dinonaktifkan migrasi (aturan `discount`) |

Benih: dua baris `discount` dibuang dari `DEFAULT_APPROVAL_RULES`.

Migrasi `scripts/migrate_kpt3_aturan_persetujuan.py` (bawaan hanya-lapor; data nyata dijalankan pemilik — H3):

1. Aturan ber-`doc_type` `discount` → `active: false`, `retired_reason: "Jenis aturan tidak dipakai mesin"`. Tidak
   dihapus.
2. Aturan yang `required_role`-nya tidak kosong dan bukan peran yang dikenal → `required_role: "manager"`,
   `migrated_from_role: <nilai lama>`. Ini **sama** dengan perlakuan mesin hari ini (butir 2), sehingga tidak ada
   keputusan yang berubah.
3. Baris `approval.extra_levels` (grup dan tiap PT) yang `role`-nya tidak dikenal dilaporkan; tidak diubah.

Sampai migrasi dijalankan, mesin tetap memperlakukan nilai tak dikenal sebagai Manajer (tidak diubah di unit ini).

### Server

`backend/services/config_service.py`:

- `async def approval_pool(doc_type, entity_id) -> dict` → `{"source": "pt" | "grup" | "kosong", "rules": [...],
  "group_rules": [...]}`; memuat persis logika pemilihan yang sekarang ada di `evaluate_approval`
  (aturan aktif, urut `sort`; aturan PT bila ada, selain itu aturan grup). `evaluate_approval` memanggilnya, sehingga
  layar dan mesin memakai satu fungsi.
- `def required_role_for(rules, amount) -> str` → peran yang dituntut untuk satu nilai menurut `rules` (aturan pertama
  yang `min_amount ≤ nilai < max_amount`; tidak ada → `""`).
- `async def effective_tiers(doc_type, entity_id) -> dict` → bentuk satu unsur `doc_types` di bawah.

`backend/routers/approval_rules.py`:

| Hal | Sesudah |
|---|---|
| `VALID_DOC_TYPES` | `sales_order`, `purchase_order`, `purchase_requisition` |
| Validasi `required_role` | `""` atau `role_registry.is_role(nilai)`; `VALID_ROLES` dihapus |
| `GET /api/approval-rules` | Tidak mengembalikan aturan ber-`doc_type` di luar `VALID_DOC_TYPES`. Tiap baris menambah `required_role_label` (label peran dari registry, "Tanpa persetujuan" bila kosong) dan `role_known: bool` |
| `POST`, `PATCH /api/approval-rules…` | Jawaban menambah `warnings` (lihat bawah) untuk pasangan (PT, jenis dokumen) aturan itu. Peringatan tidak menolak simpan |

Endpoint baru: `GET /api/approval-rules/effective` · izin `settings.view` · parameter `entity_id` (wajib; lewat
`resolve_requested_entity`, di luar cakupan pengguna → 403) dan `doc_type` (opsional). Jawaban:

```text
{ entity_id, entity_name,
  doc_types: [ { doc_type, label, source: "pt" | "grup" | "kosong",
      tiers:        [ { level: 1, rule_id, sort, min_amount, max_amount, required_role, required_role_label, role_known } ],
      extra_levels: [ { level, min_amount, role, role_label, label, role_known, source: "pt" | "grup" } ],
      unused_group_rules: [ { rule_id, min_amount, max_amount, required_role, required_role_label } ],
      warnings:     [ { code, from_amount, to_amount, message } ] } ] }
```

Isi `extra_levels` dibaca dari tempat yang sama dengan mesin (`get_effective_settings(entity_id)["approval"]
["extra_levels"]`, seperti `build_approval_chain`), dan hanya berlaku di atas tingkat 1. Keterangan `source`-nya
diambil dari `config_resolver.resolve("approval.extra_levels", {"entity_id": …})["source_layer"]`.
`unused_group_rules` terisi hanya bila `source = "pt"`.

Peringatan (dihitung dari `tiers`, batas atas kosong = tak terhingga):

| `code` | Kapan | `message` |
|---|---|---|
| `celah` | Ada rentang nilai ≥ 0 yang tidak tercakup aturan mana pun | "Nilai {Rp a} s/d < {Rp b} tidak tercakup aturan, sehingga lolos tanpa persetujuan." (batas atas tak terhingga: "Nilai ≥ {Rp a} …") |
| `tumpang_tindih` | Dua aturan mencakup rentang yang sama | "Rentang {Rp a} s/d < {Rp b} tercakup lebih dari satu aturan. Yang dipakai aturan berurutan paling kecil." |
| `lebih_longgar_dari_grup` | `source = "pt"` dan ada rentang yang menurut aturan grup menuntut peran, tetapi menurut aturan PT tidak menuntut siapa pun | "PT ini punya aturan sendiri, jadi aturan grup untuk {jenis dokumen} tidak dipakai. Akibatnya nilai {Rp a} s/d < {Rp b} lolos tanpa persetujuan, padahal aturan grup menuntut {label peran}." |
| `peran_tak_dikenal` | `role_known` salah pada sebuah tingkat | "Aturan ini menunjuk peran “{nilai}” yang tidak ada. Mesin memperlakukannya sama dengan Manajer." |

Rentang `lebih_longgar_dari_grup` dihitung dengan membandingkan `required_role_for(aturan grup, x)` dan
`required_role_for(aturan PT, x)` pada tiap ruas di antara semua batas `min_amount`/`max_amount` kedua himpunan.

Kunci `approval.extra_levels`: saat ditulis lewat `PUT /api/config/values`, tiap baris diperiksa — `role` harus peran
yang dikenal dan `min_amount` angka ≥ 0. Pemeriksa `validate_extra_levels(value)` ditaruh di
`backend/services/config_service.py` dan dipanggil `config_resolver.set_value` untuk kunci ini.

Galat (400):

| Keadaan | Pesan |
|---|---|
| `doc_type` `discount` | "Jenis aturan 'Diskon (%)' sudah tidak dipakai. Potongan harga diatur lewat Harga Khusus." |
| `doc_type` lain yang tidak dikenal | "Jenis dokumen tidak dikenal. Pilihan: Pesanan Penjualan, Pesanan Pembelian, Permintaan Pembelian." |
| `required_role` tidak dikenal | "Peran penyetuju tidak dikenal. Pilih peran yang ada di Peran & Hak Akses." |
| `role` tak dikenal di `approval.extra_levels` | "Jenjang tambahan baris {n}: peran “{nilai}” tidak ada." |

### Pengaturan

Tidak ada kunci baru. `approval.extra_levels` mendapat pemeriksaan isi (lihat Server).

### Izin dan peran

Tidak ada pasangan izin baru (`settings.view` untuk membaca, `settings.manage` untuk mengubah — seperti hari ini).

### Layar

Tempat: Pengaturan › Persetujuan › Aturan Persetujuan (`ApprovalRulesSettings.jsx`, `ApprovalRuleForm.jsx`,
`approvalRulesConstants.js`).

- `DOC_TYPES` tanpa "Diskon (%)". `ROLES` statis dihapus; pilihan **Peran Penyetuju** = "Tanpa persetujuan (lolos
  otomatis)", "Manajer", "Admin" dengan label dari registry peran (`frontend/src/config/roles.js`).
- Baris yang `role_known` salah menampilkan nilai lamanya dengan tanda "peran tidak dikenal — diperlakukan sebagai
  Manajer"; baris ber-`migrated_from_role` menampilkan catatan "Dulu dipilih “{nilai lama}”, yang selama ini sama
  dengan Manajer. Ubah ke Admin bila yang dimaksud Direksi."
- Bagian baru di atas tabel, berjudul **Jenjang yang berlaku**, dengan pemilih **PT** (bawaan: PT aktif; saat "Semua
  PT" pemilih kosong dengan petunjuk "Pilih PT untuk melihat jenjang yang berlaku."). Untuk tiap jenis dokumen satu
  kartu:
  - lencana sumber: **Aturan grup** / **Aturan khusus PT ini** / **Belum ada aturan**;
  - daftar jenjang, mis. "Rp0 s/d < Rp100.000.000 — tanpa persetujuan", "≥ Rp100.000.000 — Manajer",
    "≥ Rp500.000.000 — ditambah Direksi (Admin)";
  - peringatan (latar kuning) memakai `message` dari server;
  - bila `source = "pt"`: tautan "Lihat {n} aturan grup yang tidak dipakai" yang membuka daftarnya.
- Setelah simpan, bila jawaban memuat `warnings`, tampilkan di pop-up hasil: "Aturan tersimpan. Perhatikan:" diikuti
  daftar pesannya.
- Teks "Semua entitas" → "Semua PT"; "Cakupan Entitas" → "Berlaku untuk PT"; keterangan form: "Aturan khusus PT
  **menggantikan** semua aturan grup untuk jenis dokumen yang sama."
- Memuat: kerangka abu-abu; galat: `ErrorNotice` dengan tombol coba lagi; kosong: "Belum ada aturan untuk PT ini."

## Uji penerimaan

Persiapan bersama: seed lingkungan B (aturan grup PO: Rp0–<100 jt tanpa persetujuan; ≥ 100 jt Manajer;
`approval.extra_levels` bawaan PO ≥ 500 jt → Admin "Direksi"); akun admin.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `POST /api/approval-rules` `{doc_type: "purchase_order", min_amount: 0, required_role: "owner"}` | 400 "Peran penyetuju tidak dikenal…"; jumlah aturan tidak bertambah |
| U2 | B | — | `POST /api/approval-rules` `{doc_type: "discount", min_amount: 0, max_amount: 10}` | 400 "Jenis aturan 'Diskon (%)' sudah tidak dipakai…" |
| U3 | B | Basis data baru (benih) | `GET /api/approval-rules` | Tidak ada baris ber-`doc_type` `discount`; jumlah baris = 5 (1 SO + 2 PO + 2 PR) |
| U4 | B | Sisipkan langsung aturan `{doc_type: "sales_order", entity_id: "all", min_amount: 0, required_role: "owner", sort: 1, active: true}` dan nonaktifkan aturan SO benih | `evaluate_approval("sales_order", 1000, "ent_ksc")` sebelum dan sesudah skrip migrasi dijalankan (mode tulis) | Sebelum: `required_role` `"owner"`. Sesudah: `"manager"` dan `migrated_from_role: "owner"`. `role_satisfies("manager", …)` benar dan `role_satisfies("sales", …)` salah pada kedua keadaan |
| U5 | B | — | `GET /api/approval-rules/effective?entity_id=ent_ksc&doc_type=purchase_order` | `source: "grup"`; `tiers` 2 baris (0–100 jt `""`; ≥ 100 jt `manager`); `extra_levels` 1 baris (500 jt, `admin`, "Direksi"); `warnings` kosong |
| U6 | B | `POST /api/approval-rules` `{doc_type: "purchase_order", entity_id: "ent_kanda", min_amount: 500000000, required_role: "admin"}` | Periksa jawaban POST; lalu `GET …/effective?entity_id=ent_kanda&doc_type=purchase_order` | Jawaban POST memuat `warnings`. GET: `source: "pt"`; `tiers` 1 baris; `unused_group_rules` 2 baris; `warnings` memuat `celah` (`from_amount` 0, `to_amount` 500000000) dan `lebih_longgar_dari_grup` (`from_amount` 100000000, `to_amount` 500000000, menyebut "Manajer") |
| U7 | B | seperti U6 | `GET …/effective?entity_id=ent_ksc&doc_type=purchase_order` | Sama persis dengan U5 (PT lain tidak berubah) |
| U8 | B | seperti U6 | `GET /api/settings/evaluate-approval?doc_type=purchase_order&amount=200000000` untuk `ent_kanda` dan `ent_ksc` | `ent_kanda`: `requires_approval` salah; `ent_ksc`: `required_role` `"manager"` — sama dengan sebelum unit (mesin tidak diubah) |
| U9 | B | Aturan grup SO: (0–50 jt, `""`, sort 1) dan (30 jt–tak terhingga, `manager`, sort 2) | `GET …/effective?entity_id=ent_ksc&doc_type=sales_order` | `warnings` memuat `tumpang_tindih` dengan `from_amount` 30000000, `to_amount` 50000000 |
| U10 | B | 20 pasangan (jenis dokumen, nilai, PT) tetap: nilai 0; 1; 49.999.999; 50.000.000; 99.999.999; 100.000.000; 499.999.999; 500.000.000 untuk PO dan PR di dua PT, ditambah 4 nilai SO | Untuk tiap pasangan: `required_role_for(approval_pool(…)["rules"], nilai)` dibanding `evaluate_approval(…)["required_role"]` | 20 dari 20 sama (kosong disetarakan dengan `None`) |
| U11 | B | — | `PUT /api/config/values` kunci `approval.extra_levels`, nilai `{"purchase_order": [{"min_amount": 1, "role": "direktur"}]}`, dengan alasan | 400 "Jenjang tambahan baris 1: peran “direktur” tidak ada."; nilai efektif tidak berubah |
| U12 | B | Peran **Sopir**; peran **Tanpa Acuan** berizin `settings.view` | Keduanya `GET /api/approval-rules/effective?entity_id=ent_ksc` | 403 dan 200 |
| U13 | B | Akun berperan `sales` yang hanya ditugaskan di `ent_ksc`, perannya diberi `settings.view` | `GET …/effective?entity_id=ent_kanda` | 403 |
| U14 | layar (uji jalan) | Login admin setelah U6 | Buka Aturan Persetujuan; pilih PT Kanda | Kartu Pesanan Pembelian berlencana "Aturan khusus PT ini" dengan dua peringatan kuning; pilihan penyetuju tanpa "Owner"; pilihan jenis dokumen tanpa "Diskon (%)" |

## Langkah kerja

1. `backend/tests_mem/test_KPT3_aturan_persetujuan.py`: U1–U13 (merah kecuali U8).
2. `approval_pool`, `required_role_for`; `evaluate_approval` memakainya; U10 hijau sebelum lanjut.
3. Validasi jenis dokumen dan peran; benih tanpa `discount`; penyaring daftar.
4. `effective_tiers`, peringatan, endpoint `effective`; `warnings` pada jawaban simpan.
5. Pemeriksa `approval.extra_levels`.
6. Skrip migrasi beserta ujinya (U4).
7. Layar; gate; laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (dua field `approval_rules`); `memory/PRD.md` (jenjang efektif per PT).

## Di luar lingkup

- Mengubah cara mesin memilih aturan (menggabung aturan PT dengan aturan grup per jenjang): tidak dikerjakan; unit ini
  hanya menampilkan dan memperingatkan. Tabel kebijakan baru di KP-T4 memakai `approval_pool` sebagai sumber migrasi.
- Penyetuju ditentukan izin setujui + batas nominal per peran; peran kustom sebagai penyetuju → KP-T4.
- Jumlah orang dan larangan setuju-sendiri → KF-T6.
- Menyatukan tab "Aturan Persetujuan", "Divisi & Persetujuan R&D", dan "Persetujuan & Ambang" → KP-T4 dan KP-T9.

## Asumsi dan risiko

- `ASUMSI:` nilai `owner` yang sudah tersimpan dimigrasikan menjadi `manager`, bukan `admin`, karena itulah perlakuan
  mesin hari ini (`00` §4.1). Layar memberi catatan supaya pemilik bisa menaikkannya ke Admin.
- `ASUMSI:` celah di bawah jenjang pertama (mis. Rp0 s/d < Rp500 jt tanpa aturan) tetap berarti "tanpa persetujuan"
  seperti hari ini; ia diperingatkan, tidak ditolak.
- `ASUMSI:` dua aturan ber-`sort` sama diurutkan menurut urutan baca basis data, seperti hari ini; peringatan
  `tumpang_tindih` cukup untuk menandainya.
- `RISIKO:` klien lama yang masih mengirim `owner` atau `discount` mendapat 400. Pencarian di `frontend/src` hanya
  menemukan dua berkas layar ini sebagai pengirim. Membatalkan: kembalikan `VALID_ROLES` dan `VALID_DOC_TYPES`.
