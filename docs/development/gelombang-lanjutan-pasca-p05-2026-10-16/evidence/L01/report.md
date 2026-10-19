# Laporan Fase L01 — implementasi sebagian (status `in_progress`, belum `implemented_pending_validation`)

ERP Kain Nussantara · Gelombang Lanjutan Pasca-P05 Rev 1.3 · 2026-10-16

Developer: agent E1 (Emergent). Reviewer terpisah: **belum ada**. Owner approval ref: **belum ada**.
Commit: riwayat git workspace Emergent berbeda dengan GitHub. SHA penuh diisi setelah "Save to GitHub".

Keputusan owner untuk fase ini ada di `../L00/owner_decisions_2026-10-16.md`. Di sesi ini owner menambah keputusan **susut di mitra**:
- Kelebihan di atas toleransi menjadi klaim ke mitra.
- Toleransi % diatur per mitra × jenis proses.
- Susut di atas toleransi wajib persetujuan.
- Aktivitas "catat" dan "setujui" dipisah lewat custom role.

## 1. Requirement yang dikerjakan

### LN-012 — Grade dinamis, rank customer, visibilitas atribut per peran

**Visibilitas grade/LOT/asal per peran (T02/T05)**

Sebelum: Sales menerima `grade`, `batch_lot_rolls`, `lot`, `dye_lot`, `supplier_lot`, dan `origin` di 19 endpoint. Bukti: `field_leak_scan_sales_before.json`.

Sesudah: ada satu choke point, `backend/services/field_visibility.py`, yang dipasang sebagai middleware di `server.py`.
- Izin baru `field_visibility.grade|lot|origin` adalah izin boleh-melihat. Profil `sales_pov.commercial` menandai POV Sales komersial: grade selalu disembunyikan, walau izin grade dicentang, termasuk saat trial.
- Respons JSON disaring berdasarkan nama kunci.
- Parameter penyaring `grade`, `lot`, dan `origin` dibuang, supaya hitungan hasil tidak membocorkan atribut.
- `/api/lots*` ditolak 403 bila LOT disembunyikan.
- PDF: kolom diganti "—" (`pdf_service.render_document(hidden=…)`).
- CSV ekspor produk dan benang: kolom tersembunyi dibuang.

Sisa kunci pada pemindaian ulang (`field_leak_scan_sales_after.json`) hanya kunci kebijakan, misalnya `lot_mode`, `lot_policy`, dan `grade_thresholds`. Kunci ini bukan identitas stok.

Migrasi izin:
- Semua peran bawaan non-Sales mendapat `field_visibility` (tidak ada penurunan hak).
- Sales mendapat `sales_pov.commercial`.
- Peran kustom tidak mendapat apa pun secara otomatis, jadi atributnya tersembunyi (tidak ada silent privilege expansion).

**Master grade (T03)**: `md_grades`, `services/grade_master_service.py`, dan API `/api/master/grades`.
- Hak lihat, tambah, ubah, dan aktif/nonaktif dipisah (`grade_master.*`).
- Tidak ada hapus fisik. Rank unik. Batas poin 4-point per grade bersifat opsional.
- Seed awal: A, A1, B, BS aktif. A2, B1, C historis (nonaktif). Roll lama tetap terbaca: B1 dipakai 117 roll, C dipakai 23 roll.
- `domain_registry.GRADES` diisi ulang dari master saat startup, sesudah setiap perubahan, dan setiap 30 detik (untuk multi-worker).

Semua input grade baru menolak grade nonaktif:
- `require_grade` dan `grade_service.normalize_or_raise`, yang dipakai QC, GRN, makloon, karantina retur, dan aturan pelanggan.
- Grading 4-point (`grade_from_points`) hanya memakai grade aktif.
- Sumbu SKU varian hanya menawarkan grade aktif.

Form FE yang dulu hardcode sekarang mengikuti master:
- `useDomainEnums.options()` hanya menampilkan grade aktif.
- NodeRulesEditor, WarehouseProfileDrawer, SpecFormModal, dan CustomerGradeRulesCard memakai daftar dari master.
- Layar baru: Pengaturan › Master Grade Mutu.

**Minimum grade pelanggan (T01)**:
- `customer_grade_rules.min_grade`. Grade lebih tinggi diterima, lebih rendah ditolak. BS tetap pilihan terpisah.
- Aturan lama `allowed_grades` dibaca sebagai minimum = grade terburuk yang dulu diterima. Data acuan punya 0 aturan.
- Urutan rekomendasi tetap "prioritas pelanggan → grade terbaik yang memenuhi minimum", sama dengan perilaku lama.

### LN-013-T01 — Sumber restock sebagai default

`restock_source_service.check_lines`: jalur yang menyimpang dari default sekarang boleh, asal alasan ditulis. Pilihan itu tercatat sebagai `deviation`, `default_route`, dan peringatan, jadi bukan hard block lagi. Ini menggantikan ACC-35 P05. Tes P05 terkait sudah diperbarui.

### LN-010 / LN-015 — Hak akses 4 tingkat dan enforcement

Editor peran sekarang punya empat tingkat:
1. Modul: preset 3 tingkat.
2. Menu.
3. Tab: centang tampil/sembunyi, termasuk status sebagian.
4. Aktivitas: aksi per sumber daya.

Pratinjau menu ikut memperhitungkan izin dan tab yang disembunyikan.

Navigasi sekarang mengikuti izin efektif:
- Tab dan menu yang dibuka modul tanpa satu pun izin disembunyikan.
- Tab yang dimatikan di editor juga disembunyikan.
- Mekanismenya: `roles.js` (`setAccessContext`/`accessBlocks`), dengan data `hidden_views` dan `view_resources` dari `/api/auth/me`.

Server:
- `hidden_views` per peran disimpan di `permission_settings.hidden_views`.
- Akun non-Admin tidak bisa mengubah hak perannya sendiri, baik lewat `/api/access/roles/{id}` maupun `PUT /api/permissions`.
- Bug lama diperbaiki: `sync_permission_modules` dulu menghidupkan kembali izin bawaan yang sudah dicabut admin setiap kali restart. Sekarang ada `defaults_applied`, sehingga default hanya ditambahkan sekali.

### Susut / hilang bahan di mitra (keputusan owner 2026-10-16)

Endpoint:
- `POST /api/makloon-orders/{id}/steps/{seq}/material-loss` (izin `makloon_order.record_loss`).
- `POST …/material-loss/{loss_id}/decide` (izin `makloon_order.approve_loss`).

Aturan:
- Toleransi diambil dari `step.tolerance_pct`, yaitu kontrak mitra × jenis proses, dengan fallback ke pengaturan.
- Dalam toleransi: dibukukan otomatis, Dr 5-9500 / Cr 1-1350.
- Di atas toleransi: menunggu persetujuan. Sesudah disetujui, bagian di atas toleransi menjadi Dr 1-1260 (Piutang Klaim Mitra) dan bagian dalam toleransi menjadi 5-9500.
- Pencatat tidak boleh menyetujui catatannya sendiri.
- Ada atomic claim per MKO. Nilai `material_value_open` dirawat untuk rekonsiliasi.

UI: tombol "Catat Susut / Hilang" di panel retur, daftar susut dengan tombol setujui/tolak, dan error detail MKO sekarang tampil.

## 2. Belum dikerjakan / blocker

| Item | Status |
|---|---|
| LN-011 (stage vs jenis kain, supplier/color, lifecycle master) | belum. Tergantung DATA-01 (dataset client) |
| LN-012-T04 (PFD/PFP dijual terpisah, greige tidak dipesan via API) | belum diverifikasi (`refresh_hidden_stages` sudah ada sejak sebelumnya) |
| LN-013-T02 (konteks entitas MD) | blocked DES-04 |
| LN-014 (LOT supplier vs internal) | blocked KLX-01 |
| LN-015-T05 (ACC PIC atomik lintas jenis uji) | belum diuji khusus |
| LN-015-T08 (UAT editor tablet/keyboard) | belum |
| **Temuan baru F-L01-01**: grade dan asal masih tertanam di **kode SKU** (segmen ASAL & GRADE, mis. `-L-…-XA-`), **nama produk** (akhiran "… A"), dan nama gudang ("Gudang Retur (grade B/BS/C)") | **butuh keputusan owner**: masker segmen SKU/nama untuk Sales atau diterima |
| Potong tagihan jasa sebagai cara penyelesaian klaim susut | belum. Klaim saat ini = piutang klaim mitra. MKO batal umumnya belum punya tagihan jasa |
| RollInspectionModal: prediksi grade di layar masih memakai daftar tetap | minor. Grade akhir dari server sudah memakai master aktif |

## 3. Pengujian

- `backend/tests/test_l01_grade_visibility.py`: 13 lulus
- `backend/tests/test_l01_material_loss.py`: 4 lulus
- `backend/tests/test_l01_custom_role.py`: 3 lulus
- `backend/tests/test_l01_sales_field_hidden_api.py` (testing agent): 8 lulus
- Regresi lulus: P05 restock/revalidation 12, ACC-31/33/34 + rekonsiliasi 17, L00 5 + 5.
- Laporan testing agent ada di `/app/test_reports/iteration_184.json`. Semua temuan di laporan itu sudah diperbaiki, kecuali F-L01-01 (butuh keputusan owner) dan dua item minor di tabel blocker di atas.
- Gagal pre-existing yang tidak disebabkan L01:
  - `test_role_editor_iter35–38`: peran fixture `cr_staf_penagihan` tidak ada di seed, dan email `test_pindah` sudah dipakai akun nonaktif.
  - `test_access_roles_iter32`: jumlah modul di-hardcode 24, padahal sebelum L01 sudah 27.

## 4. Lanjutan sesi (2026-10-16, sesudah keputusan owner)

### F-L01-01 — Kode SKU & nama disamarkan
Owner memutuskan: disamarkan untuk peran tanpa izin grade, asal, atau LOT.
- Implementasi ada di `field_visibility.redact`: `_mask_sku` dan `_strip_name`.
- Segmen ASAL diganti `•`, segmen GRADE dan LOT diganti `••` pada kode KN `ARTIKEL9-ASAL1-WARNA4-GRADE2-CUSTOMER2-LOT2`.
- Pada objek produk, akhiran grade dan " LOT x" di nama dibuang. Grade dibaca dari kunci `grade`, dari segmen SKU, atau dari peta product_id → grade (cache 60 dtk), sehingga baris ringan seperti stock-summary, item SO, dan roll ikut bersih.
- Berlaku juga untuk PDF.
- Pemilih varian: bila beberapa varian tampak sama (beda grade saja), yang dipilih adalah varian dengan stok terbanyak; alokasi grade tetap di server sesuai aturan pelanggan.

### Potong tagihan jasa mitra
- Saat menyetujui susut, penyetuju memilih `tagih_ganti` (Dr 1-1260) atau `potong_bon` (Dr 2-1100).
- `potong_bon` hanya untuk tagihan jasa mitra yang sama dan sudah posted/approved, dengan sisa cukup: `GET …/deductible-bills`.
- Potongan diklaim atomik sebesar batas atas, lalu dikoreksi sesuai qty aktual. Bila roll ternyata sudah kembali, potongan dibatalkan. Field `outstanding` ikut diperbarui.

### Toleransi kontrak mudah diubah
- Edit inline di daftar Kontrak Mitra (`contract-tol-edit-<id>`). Mengosongkan nilai berarti kembali ke kebijakan global (`reset_tolerance`).
- Toleransi per langkah MKO yang bahannya masih di mitra bisa diubah: `POST …/steps/{seq}/tolerance` (izin `supplier_contract.update`, alasan wajib, tercatat di timeline), termasuk tombol "Pakai kontrak sekarang".
- Perubahan diblok bila ada susut yang masih menunggu persetujuan, atau bila order sedang terkunci.

### Pengujian
- `test_l01_sku_mask_settle_tol.py` (testing agent): 12 lulus
- `test_l01_material_loss.py`: 8 lulus
- `test_l01_grade_visibility.py`: 14 lulus
- `test_l01_sales_field_hidden_api.py`: 8 lulus
- ACC-31/33/34 + rekonsiliasi: 17 lulus
- Laporan testing agent: iteration_185. Semua temuannya sudah diperbaiki.

### Masih menunggu input owner/client
- **LN-011:** pemisahan tahap vs jenis kain dan lifecycle master butuh **dataset client DATA-01** (daftar artikel/tahap/jenis kain/supplier-color aktual).
- **LN-014:** identitas LOT supplier vs internal butuh keputusan **KLX-01**.
- **LN-013-T02:** konteks entitas MD butuh keputusan **DES-04**.

## 5. Lanjutan sesi — impor dataset client, gabung varian warna, rekap klaim mitra

- **Impor Dataset Client (LN-011 · DATA-01)** — menu `?view=client-dataset-import` (hanya Admin, izin `product.import`).
  - Alurnya: unduh template CSV/XLSX → dry-run → terapkan → batalkan.
  - Yang diperbarui hanya master yang cocok: artikel lewat kode/nama, SKU lewat kode SKU atau artikel + warna internal. Isinya tahap, jenis kain, kategori, warna customer, dan peta supplier/warna di `supplier_items`.
  - Yang **tidak dibuat otomatis**: artikel, SKU, supplier, tahap, atau jenis kain yang belum ada. Semuanya dilaporkan di bagian "Nilai belum ada di master".
  - Hanya sinonim baku yang diterjemahkan: greige→grey, knitting→knit, tenun→woven.
  - Ditolak saat dry-run: kode artikel supplier yang bentrok antar-SKU, dan nama supplier ganda (wajib pakai kode supplier).
  - Commit selalu melakukan dry-run ulang dan menyimpan nilai *before* bertahap. Kode ganda menghasilkan 409, bukan 500.
  - Rollback berurutan dari yang terakhir (LIFO). Batch gagal tetap bisa dibatalkan. Field yang sebelumnya tidak ada di-`$unset`.
  - **Dataset aslinya belum diterima.** T01–T03 dijalankan begitu file client masuk.
- **Gabung varian warna (POV Sales):**
  - `mergeHiddenTwins` menggabungkan varian yang beda grade/asal saja menjadi satu varian per warna, dengan stok dan rentang harga gabungan.
  - Di keranjang, qty dipecah ke SKU nyata (stok terbanyak dulu, memperhitungkan qty yang sudah di keranjang). Ada peringatan bila melebihi stok.
  - Subtotal mengikuti harga per SKU. Kartu gabungan tidak membuka pilih-roll; baris roll 0 kg ditolak.
  - Header katalog menampilkan jumlah varian. Badge keranjang di HP menghitung baris.
- **Rekap Susut & Klaim Mitra** — `?view=makloon-claim-recap`, endpoint `GET /api/makloon-claims/recap`.
  - Per mitra ditampilkan: beban susut wajar, piutang klaim, potongan tagihan, klaim selisih hasil, dan yang menunggu. Ada baris rinci dan filter periode/mitra.
  - Akses: izin record_loss / approve_loss / claim_approve / gl / vendor_bill / accounting. Sales ditolak (403).
- **Pengujian:** test_l01_dataset_recap 5, test_l01_dataset_edge 11, iteration_186–187. Gabung varian dan pemecahan keranjang lulus di desktop dan HP.

## 6. Lanjutan 2026-10-19 — LN-015 (T03, T05, T06, T08)

- **T03 ACC teknis per jenis uji**: aksi baru `rnd.assess_labdip|handfeel|proofing` ("Catat hasil …") dan `rnd.decide_labdip|handfeel|proofing` ("Setujui hasil …"). `assess`/`decide` umum tetap mencakup semua jenis. Server: `routers/rnd.py::_require_typed` — sample hanya boleh dinilai bila peran punya aksi umum ATAU aksi bertipe untuk SEMUA jenis uji sample itu. ACC bertipe **tidak** membuka keputusan yang membuat kontrak harga (sample non-revalidasi tetap butuh `rnd.decide`), tidak membuka `pic_decide` maupun contract-options. Aksi baru tidak diberikan otomatis ke peran selain Admin (tidak ada perluasan hak diam-diam).
- **T05**: keputusan PIC atomik (update bersyarat status) — tes serentak sudah ada di `test_l03_ln034_revalidation.py`.
- **T06**: izin dibaca ulang dari DB setiap request (perubahan berlaku pada request berikutnya — diuji). Simpan peran membawa `expected_version` (sidik isi peran); versi berbeda → 409 `ROLE_VERSION_CONFLICT`, tidak menimpa; editor menampilkan tombol "Muat ulang versi terbaru". Non-admin tetap tidak bisa mengubah perannya sendiri.
- **T08**: editor peran memperingatkan perubahan belum disimpan (tutup ×, Batal, klik luar, Escape) dengan ringkasan jumlah modul/menu yang berubah; error simpan tidak menghapus pilihan.
- **Bug diperbaiki**: hapus peran custom kini juga menghapus `hidden_views` miliknya (sebelumnya peran baru ber-slug sama mewarisi tab tersembunyi lama).
- Tes: `tests/test_ln015_typed_rnd_and_role_version.py` (9 lulus), `tests/test_l01_custom_role.py`.
- Belum: T01 inventaris lengkap seluruh aksi lintas fase, T02/T04/T07 diuji ulang khusus, UAT tablet T08 oleh pengguna.

## Update 2026-10-19 (sesi lanjutan) — LN-014/LN-040 dua kode LOT (KLX-01)
- **Dua kode:** `supplier_lot` = LOT pabrik, `internal_alias` = **LOT KN** (diisi user). Nomor lot sistem (`lot_number`) tetap identitas kanonik dan tidak berubah.
- **LOT KN baru per SJ:** `lot_service.resolve_or_create` (sumber `receiving`) tidak lagi memakai ulang lot dari penerimaan lain walau nomor lot/LOT pabriknya sama — penerimaan berikutnya membuat lot baru (LOT pabrik tetap tercatat). Penerimaan yang sama tetap idempoten.
- **Penamaan bebas:** gerbang `lot.alias_mode` dan blok keunikan alias dihapus; pola & reset LOT KN diputuskan user (tidak diatur sistem). Perubahan pada lot berisi roll tetap wajib alasan + `identity_history`.
- UI detail lot: label "LOT pabrik (supplier)" dan "LOT KN (diisi user, KLX-01)", selalu bisa diisi oleh pemegang izin ubah lot.
- **Uji:** `tests/test_ln014_lot_identity.py` 4/4 (`test_klx01_lot_kn_free_input_no_system_pattern`, `test_klx01_same_factory_lot_next_receipt_gets_new_kn_lot`).
