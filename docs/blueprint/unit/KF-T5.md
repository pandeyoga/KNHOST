# KF-T5 — Aturan khusus per pelanggan dan per barang punya layar

| | |
|---|---|
| Gelombang | Jalur pengaturan (sejajar gelombang 3–7) |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | KF-T1 |
| Menutup temuan | KF-07 |
| Keputusan | — (aturan bawaan `00` §4.1) |
| Standar | §2.1 (`scopes`), §2.2, §2.4, §3.4 (N2), §4 (L1, L3, L6) |
| Lingkungan uji | B; uji jalan layar di A |

## Tujuan

Aturan yang oleh mesin memang bisa dibedakan per pelanggan (denda, masa tenggang, toleransi selisih bayar) atau per
barang (aturan sisa dan susut potong) bisa diatur dari kartu pelanggan dan kartu barang, tanpa bantuan pengembang.
Kunci yang menjanjikan "per pelanggan" tetapi tidak dibaca begitu, berhenti menjanjikannya.

## Keadaan sekarang

Semua `[dibaca]`. Registry memuat 13 kunci dengan lapisan `customer` (10) atau `product` (3). Layar pengatur hanya
menawarkan Global dan PT: `frontend/src/features/settings/config/SettingsScopeBar.jsx:68` (`cfg-scope-type`). Kartu
tetap menulis "Bisa diatur pada level: … Pelanggan tertentu":
`frontend/src/features/settings/config/SettingCard.jsx:132` (`scopes`). Server sudah menerima lapisan itu
(`backend/services/config_resolver.py:58` (`WRITABLE_LAYERS`)), tetapi penjaga tulis hanya memeriksa lapisan PT dan grup:
`backend/routers/config.py:146` (`_assert_scope_write`) — id pelanggan atau barang tidak dibuktikan ada.

Hasil pemeriksaan pemakai, per kunci:

| Kunci | Lapisan | Pemakai membaca dengan id pelanggan/barang? | Jangkar | Tindakan |
|---|---|---|---|---|
| `ar.denda_rate_pct_per_month` | pelanggan | Ya | `backend/services/ar_aging_service.py:47` (`customer_id`), `backend/services/penalty_service.py:67` (`penalty_policy`) | Beri layar |
| `ar.grace_days` | pelanggan | Ya | sama | Beri layar |
| `payment.penalty_mode` | pelanggan | Ya | `backend/services/penalty_service.py:73` (`penalty_mode`) | Beri layar |
| `payment.penalty_base` | pelanggan | Ya | `backend/services/penalty_service.py:74` (`penalty_base`) | Beri layar |
| `payment.penalty_cap_pct` | pelanggan | Ya | `backend/services/penalty_service.py:75` (`penalty_cap_pct`) | Beri layar |
| `payment.variance_tolerance_rupiah` | pelanggan | Ya | `backend/services/payment_variance_service.py:110` (`variance_policy`) | Beri layar |
| `payment.variance_underpay_default` | pelanggan | Ya | sama | Beri layar |
| `payment.variance_overpay_default` | pelanggan | Ya | sama | Beri layar |
| `allocation.lot_mode` | pelanggan | **Tidak** — lapisan pelanggan di penyimpanan pengaturan tidak dibaca; yang dipakai isian `lot_policy` / `allocation_policy` pada dokumen pelanggan | `backend/services/config_service.py:544` (`allocation_policy`); `frontend/src/features/crm/CustomerFormModal.jsx:192` (`lot_policy`) | Cabut lapisan |
| `allocation.dye_lot_strict` | pelanggan | **Tidak** — yang dipakai isian `enforce_single_dye_lot` pada dokumen pelanggan | `backend/services/config_service.py:552` (`enforce_single_dye_lot`) | Cabut lapisan |
| `cutting.remnant_threshold` | barang | Ya | `backend/services/roll_service.py:616` (`apply_remnant_rule`) | Beri layar |
| `cutting.remnant_grade` | barang | Ya | `backend/services/roll_service.py:622` (`remnant_grade`) | Beri layar |
| `cutting.waste_limit_pct` | barang | Ya | `backend/services/roll_service.py:643` (`cut_waste_limit_pct`) | Beri layar |

Pemanggil yang meneruskan id pelanggan: `backend/services/ar_aging_service.py:235` (`get_ar_config`),
`backend/services/penalty_service.py:395` (`penalty_policy`),
`backend/services/payment_variance_service.py:710` (`variance_policy`). Tempat layar: detail pelanggan
`frontend/src/features/crm/Customer360Panel.jsx:86` (`Kontrol Kredit`); form barang `frontend/src/features/admin/products/ProductMasterForm.jsx`.

## Perubahan

### Data

Tidak ada koleksi atau field baru; baris lapisan pelanggan/barang disimpan di `config_values` dengan
`scope_type: "customer" | "product"` dan `scope_id` = id pelanggan/barang, seperti yang sudah didukung resolver.
Tanpa migrasi. Baris lapisan pelanggan yang mungkin sudah ada untuk dua kunci `allocation.*` tidak dihapus; resolver
mengabaikan lapisan di luar `scopes`.

### Server

| Tempat | Perubahan |
|---|---|
| `routers/config.py` `_assert_scope_write` | `scope_type == "customer"`: pelanggan `scope_id` harus ada (404) dan PT pelanggan harus dalam cakupan pelaku — `resolve_requested_entity(ctx, customer["entity_id"])` (403). `scope_type == "product"`: barang harus ada (404). Lapisan `supplier` dan `document` → 400 (belum ada layar; tidak ada kunci yang memakainya) |
| `GET /api/config/effective` | Parameter baru `scope` (`customer` · `product`): hanya butir yang `scopes`-nya memuat lapisan itu. Tiap butir ditambah `layer_value` (nilai pada lapisan `scope` untuk `customer_id`/`product_id` yang dikirim, atau `null`) dan `inherited_value` (nilai tanpa lapisan itu: hasil PT/grup) |
| `GET /api/config/layers` — baru | Izin: `_may_read` kunci (KF-T1). Parameter `key`, `scope_type` (`customer` · `product`). Jawaban `{"rows": [{"scope_id", "scope_label", "value", "changed_by", "changed_at", "reason"}], "total"}` — satu baris per pelanggan/barang yang punya nilai sendiri (nisan `cleared` tidak dihitung); `scope_label` = nama pelanggan / nama barang; paling banyak 200 baris, terurut `changed_at` terbaru; kunci tak dikenal → 404 |
| `PUT /api/config/values`, `POST /api/config/values/clear` | Tidak berubah bentuk; dipakai dengan `scope_type` `customer`/`product`. Izin tetap `_may_edit` kunci itu |

Teks galat:

| Kode | Keadaan | Pesan |
|---|---|---|
| 404 | Pelanggan tidak ada | "Pelanggan tidak ditemukan." |
| 404 | Barang tidak ada | "Barang tidak ditemukan." |
| 403 | Pelanggan milik PT di luar cakupan pelaku | pesan baku `resolve_requested_entity` |
| 400 | Kunci tidak mendukung lapisan itu | "“{label}” tidak bisa dibedakan per pelanggan." / "… per barang." (menggantikan teks `ConfigWriteError` yang menyebut "level") |
| 400 | Lapisan `supplier`/`document` | "Aturan khusus per pemasok atau per dokumen belum tersedia." |

### Pengaturan

Tidak ada kunci baru. Perubahan entri:

| Kunci | Perubahan |
|---|---|
| `allocation.lot_mode`, `allocation.dye_lot_strict` | `scopes=("global", "entity")`; `help` ditambah kalimat "Untuk pelanggan tertentu, atur di kartu pelanggan (Kebijakan lot)." |
| 8 kunci pelanggan dan 3 kunci barang yang tetap berlapis | `help` ditambah kalimat "Bisa dibedakan per pelanggan dari kartu pelanggan." / "Bisa dibedakan per barang dari kartu barang." Kalimat lama yang menyebut "lapisan" atau "kategori" dibuang |

### Izin dan peran

Tidak ada pasangan baru. Mengubah aturan khusus pelanggan/barang memakai izin kunci itu sendiri (hari ini
`settings.manage` untuk ke-11 kunci); membaca mengikuti aturan baca KF-T1.

### Layar

Komponen baru `frontend/src/features/settings/config/ScopedRulesSection.jsx` — satu komponen untuk dua tempat, memakai
`SettingCard` dan `configApi` yang ada:

| Sifat | Isi |
|---|---|
| Masukan | `scopeType` (`customer` · `product`), `scopeId`, `scopeLabel` (nama), `entityId` |
| Data | `configApi.effective({ scope, customer_id | product_id, entity_id })` |
| Tiap kartu | Label dan penjelasan kunci; baris status: "Mengikuti aturan PT: {inherited_value}" **atau** "Khusus {pelanggan|barang} ini: {layer_value} (aturan PT: {inherited_value})"; tombol **Atur khusus** → editor nilai + **Simpan**; tombol **Kembali ikut aturan PT** (hanya bila punya nilai sendiri; memanggil `configApi.clear`) dengan konfirmasi "Hapus aturan khusus ini? {Nama} akan kembali mengikuti aturan PT." |
| Alasan | Wajib bila kunci berisiko tinggi (aturan server yang ada) |
| Keadaan | Memuat: "Memuat aturan…" · galat: `ErrorNotice` + coba lagi · 403: bagian tidak ditampilkan · tidak ada kartu: bagian tidak ditampilkan |
| Tanpa izin ubah | Kartu hanya-baca; tombol tidak tampil |

Dipasang di:

- Penjualan › Pelanggan & CRM › detail pelanggan (`Customer360Panel.jsx`), sesudah kartu "Kontrol Kredit": bagian
  berjudul **Aturan khusus pelanggan ini**, keterangan "Kosong berarti pelanggan mengikuti aturan PT-nya."
- Produk & Harga › Master Produk › ubah barang (`ProductMasterForm.jsx`, hanya saat barang sudah tersimpan): bagian
  berjudul **Aturan khusus barang ini**, keterangan sama dengan kata "barang".

Pusat Pengaturan (`SettingCard.jsx`): baris "Bisa diatur pada level: …" diganti. Untuk kunci berlapis pelanggan/barang:
"Bisa dibedakan per pelanggan — {n} pelanggan diatur khusus" (atau "per barang"), dengan `{n}` dari
`GET /api/config/layers`; klik membuka daftar nama dan nilainya. Untuk kunci lain baris itu tidak tampil.
`configApi.SCOPE_LABEL`: `customer` → "Pelanggan ini", `product` → "Barang ini".

## Uji penerimaan

Fixture: pelanggan `C1` dan `C2` (PT `ent_ksc`), `C3` (PT `ent_kanda`); barang `P1`, `P2`; Admin seed. Nilai PT dan
grup = bawaan registry.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | Admin `PUT /api/config/values` `ar.grace_days=10`, `scope_type: "customer"`, `scope_id: "C1"` | 200; `get_ar_config("ent_ksc", "C1")["grace_days"] == 10`; `get_ar_config("ent_ksc", "C2")["grace_days"] == 0`; `penalty_policy("ent_ksc", "C1")["grace_days"] == 10` |
| U2 | B | sesudah U1 | `POST /api/config/values/clear` lapisan pelanggan `C1` | 200; `get_ar_config("ent_ksc", "C1")["grace_days"] == 0` |
| U3 | B | — | Admin simpan `payment.variance_tolerance_rupiah=20000` untuk `C1` | `variance_policy("ent_ksc", "C1")["tolerance"] == 20000.0`; untuk `C2` tetap 5000.0; untuk `C3` di `ent_kanda` tetap 5000.0 |
| U4 | B | — | Admin simpan `payment.penalty_mode` untuk `C1` dengan pilihan selain bawaan | `penalty_policy("ent_ksc", "C1")["mode"]` = pilihan itu; `C2` = `"draft"` |
| U5 | B | — | Admin simpan `cutting.waste_limit_pct=7`, `scope_type: "product"`, `scope_id: "P1"` | `cut_waste_limit_pct("P1", "ent_ksc") == 7.0`; `cut_waste_limit_pct("P2", "ent_ksc") == 3.0` |
| U6 | B | Roll `R1` barang `P1` dan roll `R2` barang `P2`, sisa masing-masing 4 | Admin simpan `cutting.remnant_threshold=5` untuk `P1`; `apply_remnant_rule("R1", "P1", "ent_ksc")`; `apply_remnant_rule("R2", "P2", "ent_ksc")` | `is_remnant True` (4 < 5); `is_remnant False` (4 ≥ 2) |
| U7 | B | — | Admin `PUT` `allocation.lot_mode` dengan `scope_type: "customer"`, `scope_id: "C1"` | 400 "… tidak bisa dibedakan per pelanggan."; `get_allocation_policy("ent_ksc", {"id": "C1", "lot_policy": "strict_single"})["lot_mode"] == "strict_single"` (isian kartu pelanggan tetap menang) |
| U8 | B | — | Admin `PUT` `ar.grace_days` lapisan pelanggan dengan `scope_id: "tidak_ada"`; lapisan barang untuk `cutting.waste_limit_pct` dengan `scope_id: "tidak_ada"` | 404 "Pelanggan tidak ditemukan."; 404 "Barang tidak ditemukan."; tidak ada baris `config_values` baru |
| U9 | B | Akun berperan kustom dengan `settings: ["view", "manage"]`, hanya ditugaskan ke `ent_ksc` | `PUT` `ar.grace_days` lapisan pelanggan `C3` (PT `ent_kanda`) | 403; tidak ada baris baru |
| U10 | B | Peran Tanpa Acuan = `{"customer": ["view", "update"]}` | `PUT` `ar.grace_days` lapisan pelanggan `C1`; `GET /api/config/effective?scope=customer&customer_id=C1` | 403 pesan U (KF-T1); 403 pesan B1 |
| U11 | B | — | Admin `GET /api/config/effective?scope=customer&customer_id=C1&entity_id=ent_ksc`; `…?scope=product&product_id=P1` | 8 butir; 3 butir; tiap butir punya `layer_value` dan `inherited_value` |
| U12 | B | sesudah U1 diulang | `GET /api/config/layers?key=ar.grace_days&scope_type=customer` | `total == 1`; `rows[0].scope_id == "C1"`, `scope_label` = nama `C1`, `value == 10` |
| U13 | B | — | Impor registry | Tepat 8 kunci ber-`customer` dan 3 ber-`product` di `scopes`; tidak ada yang ber-`supplier`/`document` |
| U14 | layar (uji jalan) | Login Admin | Detail pelanggan → **Aturan khusus pelanggan ini** → Atur khusus masa tenggang 10 → Simpan → Kembali ikut aturan PT | Status berubah "Khusus pelanggan ini: 10 hari (aturan PT: 0 hari)" lalu kembali "Mengikuti aturan PT: 0 hari"; kartu yang sama di Pusat Pengaturan menampilkan "1 pelanggan diatur khusus" di antaranya |
| U15 | layar (uji jalan) | Login Admin | Ubah barang → **Aturan khusus barang ini** → batas susut potong 7 | Tersimpan; daftar di Pusat Pengaturan menyebut nama barang itu |

## Langkah kerja

1. `backend/tests_mem/test_KFT5_aturan_khusus.py`: U1–U13; U1–U6 sudah hijau untuk bagian "terbaca mesin" (resolver
   sudah mendukung) — tes tetap ditulis sebagai penjaga; U7–U13 merah kecuali U10 (sudah benar sejak KF-T1; koreksi KF-T5).
2. Cabut lapisan dua kunci `allocation.*`; perbarui `help` 13 kunci.
3. `_assert_scope_write` untuk pelanggan/barang; parameter `scope`; endpoint `layers`.
4. `ScopedRulesSection.jsx`; pasang di dua layar; ganti baris "Bisa diatur pada level".
5. Uji jalan U14–U15; gate (`audit_i18n_id` tidak bertambah merah); laporan.

## Dokumen ikut berubah

`memory/PRD.md` (aturan khusus pelanggan dan barang); `CODEBASE_MAP.md` (`ScopedRulesSection.jsx`);
`docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("aturan khusus" sebagai istilah untuk nilai per pelanggan/barang).

## Di luar lingkup

- Denda per rencana pembayaran, mode denda per PT, dan izin kredit yang boleh mengatur denda pelanggan → CR-T4.
- Plafon, termin yang diizinkan, dan status blokir per pelanggan (profil kredit) → CR-T1.
- Menampilkan isian kartu pelanggan sebagai "penimpa" pada kartu `allocation.*` → teks `help` di unit ini sudah
  menyebutnya; mekanisme penimpaan terdaftar → KF-T3.
- Lapisan pemasok dan dokumen → tidak dibangun sampai ada kunci yang membutuhkannya.

## Asumsi dan risiko

- `ASUMSI:` wewenang mengatur aturan khusus pelanggan/barang sama dengan wewenang mengubah kunci itu di tingkat PT
  (hari ini `settings.manage`, bawaan hanya Admin). Unit CR-T4 boleh memindahkannya ke izin kredit.
- `ASUMSI:` nilai khusus pelanggan berlaku di semua PT tempat pelanggan itu bertransaksi (kunci penyimpanan hanya id
  pelanggan), sesuai cara resolver bekerja hari ini.
- `RISIKO:` nilai lapisan pelanggan yang pernah diisi lewat API tanpa layar kini terlihat dan mungkin mengejutkan.
  Laporan unit memuat hitungan baris `config_values` ber-`scope_type` `customer`/`product` di data acuan. Membatalkan:
  cabut dua bagian layar; server tidak berubah perilaku untuk lapisan PT dan grup.
