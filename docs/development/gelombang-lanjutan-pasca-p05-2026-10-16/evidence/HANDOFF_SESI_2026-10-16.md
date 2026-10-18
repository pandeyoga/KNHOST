# HANDOFF — Sesi development 2026-10-16 (Gelombang Lanjutan Pasca-P05 Rev 1.3)

ERP Kain Nussantara · repo `pandeyoga/KNHOST` · baseline paket HEAD `64d81f29577dae4daa86ddc64689dec7243804f2`.

## 0. Cara melanjutkan (baca dulu)

1. Simpan pekerjaan ke GitHub lewat fitur **"Save to GitHub"**. Commit SHA dari GitHub dibutuhkan untuk mengisi `implementation_commit` di `BACKLOG.json`. Riwayat git di workspace Emergent berbeda dengan repo GitHub, jadi SHA-nya belum diisi.
2. Siapkan lingkungan preview. `backend/.env` wajib berisi: `KN_DEMO_DATA="true"`, `CORS_ORIGINS` eksplisit (URL preview + localhost:3000), dan `SESSION_COOKIE_SECURE="true"`.
   - Pulihkan data acuan dengan `bash /app/scripts/restore_local_demo.sh` (sekitar 3 menit).
   - Frontend berupa bundle statis: setiap kali FE diubah, jalankan `bash /app/scripts/rebuild_frontend.sh` (sekitar 3–5 menit).
3. Akun: `admin@kainnusantara.id / demo12345`. Akun lain memakai sandi `demo1234` (manager@, md@, mdquality@, finance@, sales.kanda@, salesadmin.kanda@).
4. Tes dijalankan **per file**, karena beberapa file saling bergantung urutan:
   `cd /app/backend && REACT_APP_BACKEND_URL=http://localhost:8001 python -m pytest tests/<file>.py -n0 -q`.
5. Validator paket: `python docs/development/gelombang-lanjutan-pasca-p05-2026-10-16/scripts/validate_package.py`. Hasil saat ini `pass: true`. Setelah BACKLOG diubah, jalankan `render_tracking.py`.

## 1. Status fase

| Fase | Status | Bukti |
|---|---|---|
| L00 | `in_progress`: implementasi selesai, menunggu SHA + reviewer | `evidence/L00/report.md`, `baseline_snapshot.json`, `owner_decisions_2026-10-16.md` |
| L01 | `in_progress`: sebagian besar selesai (lihat §3) | `evidence/L01/report.md`, `field_leak_scan_sales_{before,after}.json` |
| L04 | **dimulai**: baru LN-042-T01/T02 (potong MDQ) | §4 di bawah, tes `test_l04_mdq_cut*.py` |
| L02–L14 | `not_started` | — |

Sesuai Definition of Done, belum ada requirement yang boleh dinaikkan ke `implemented_pending_validation`, karena SHA belum ada. Status `validated` juga butuh reviewer terpisah dan persetujuan owner.

## 2. Keputusan owner di sesi ini

Rinciannya ada di `evidence/L00/owner_decisions_2026-10-16.md`.
- Restock: hanya default/rekomendasi; jalur lain boleh dengan alasan.
- Grade pelanggan: minimum rank; grade aktif A, A1, B, BS; A2, B1, C historis. Master grade bisa dikonfigurasi dan berlaku di semua form.
- Grade/LOT/asal: visibilitas diatur per role. Kode SKU dan nama produk ikut disamarkan untuk role tanpa izin.
- Custom role 4 tingkat yang benar-benar ditegakkan.
- Susut di mitra: dalam toleransi menjadi beban; di atas toleransi butuh persetujuan, lalu ditagih ke mitra atau dipotong dari tagihan jasa. Toleransi per mitra × proses. Izin catat dan setujui terpisah.

## 3. Yang sudah dibangun (ringkas, per area)

- **L00**:
  - Unique index uji ulang SKU (`md_samples.open_reval_keys`).
  - DecideModal tanpa "ACC spesifikasi" untuk uji ulang.
  - Retur bahan MKO sebagian per roll (atomic_claim).
  - Order Makloon bisa dibuka dari HP.
  - Skrip `scripts/l00_baseline_snapshot.py`.
- **Visibilitas atribut**:
  - `services/field_visibility.py` (middleware): menyaring JSON, query, PDF, CSV, dan `/api/lots`; menyamarkan SKU dan nama.
  - Izin `field_visibility.grade|lot|origin` dan `sales_pov.commercial`.
  - Pemindai kebocoran: `scripts/l01_field_leak_scan.py`.
- **Master Grade**: `md_grades`, `/api/master/grades`, layar `?view=grade-master`. Grade nonaktif ditolak di semua input.
- **Master Jenis Kain**: `md_fabric_types`, `/api/master/fabric-types`. Bisa ditambah langsung dari laporan impor.
- **Aturan grade pelanggan**: `min_grade`.
- **Restock**: penyimpangan dari default ditandai `deviation` dan wajib alasan.
- **Custom role**:
  - Editor Modul → Menu/Tab (`RoleNavTree`, `hidden_views`) → Aktivitas.
  - Navigasi mengikuti izin efektif (`roles.js setAccessContext`).
  - Akun tidak bisa mengubah hak perannya sendiri.
  - `defaults_applied`: izin yang dicabut tidak hidup lagi saat restart.
- **Susut di mitra**:
  - `services/makloon_loss_service.py` dan endpoint `material-loss` / `decide` (settle `tagih_ganti` atau `potong_bon`), `deductible-bills`, dan `steps/{seq}/tolerance`.
  - Edit inline toleransi kontrak.
  - Rekap `/api/makloon-claims/recap` plus `.xlsx`, layar `?view=makloon-claim-recap`.
- **Impor Dataset Client (LN-011)**:
  - `/api/client-dataset/*`, layar `?view=client-dataset-import`.
  - Alur dry-run → commit → rollback LIFO; tidak membuat master fiktif.
- **POV Sales**: `utils/variants.mergeHiddenTwins` (satu varian per warna); keranjang dipecah per SKU nyata; subtotal per SKU.
- **Tiga warna SKU**: `components/ProductColorTriad.jsx` di Katalog, Quick View, dan detail produk MD di HP. Warna supplier hanya tampil bila `canSeeSourcing`.

## 4. L04 yang sudah dimulai

- **LN-042 potong MDQ**:
  - Service `services/mdq_cut_service.py`, endpoint `POST /api/inspections/{id}/lines/{line}/mdq-cut` (izin `md_quality.inspect`), UI `MdqCutBox` di modal inspeksi MD Quality.
  - Idempoten per baris. Qty penerimaan tetap bruto; roll/EPC sama.
  - Roll kg wajib berat aktual atau `kg_per_yard_validated`; tanpa itu diblok.
  - Nilai potongan dibukukan ke GL write-off.
  - Hanya untuk inspeksi terbuka berjenis po_receipt/makloon_output. Ada pemulihan bila status pending macet.
  - Tes `test_l04_mdq_cut.py` 4/4 (teardown mengembalikan roll) dan `test_l04_mdq_cut_edge.py` 6/6.
- **Belum**: LN-040 (receiving aktual + OCR per roll), LN-041 (pemilihan roll MDQ sudah ada sejak P05 dan perlu diverifikasi terhadap T01/T02), LN-042-T03 (reprint label = EPC sama, qty terkini), LN-043 (komitmen greige, issue, hasil fisik vs forecast yield, sisa bahan). LN-043-T02 sudah tercakup oleh retur/susut di L00/L01.

## 5. Menunggu input owner/client

| Kode | Butuh | Memblok |
|---|---|---|
| DATA-01 | File dataset client (artikel/tahap/jenis kain/supplier-warna); impor lewat layar Impor Dataset Client | LN-011 T01–T03 |
| KLX-01 | Identitas LOT supplier vs internal | LN-014 |
| DES-04 | Konteks badan usaha untuk MD | LN-013-T02 |
| DES-01 | Aturan konversi kg↔yard (berlaku untuk L04 LN-042) | Penetapan `kg_per_yard_validated` per produk; belum ada UI untuk mengisinya |
| — | Reviewer terpisah + persetujuan owner | Status `validated` L00/L01 |

## 6. Temuan terbuka (prioritas untuk sesi berikut)

1. **Isi SHA**: setelah Save to GitHub, isi `implementation_commit` untuk L00/L01 dan naikkan requirement yang lengkap ke `implemented_pending_validation`.
2. **UI aturan kg/yard**: layar MD untuk menetapkan `kg_per_yard_validated` per produk (menunggu keputusan DES-01).
3. **Master jenis kain**: belum ada nonaktif/hapus. Cache in-memory baru segar ≤30 detik setelah dibuat atau saat restart.
4. **Akses inspeksi MD**: `md@` dialihkan ke md-desk dari `?view=inspections`. Perlu entri modal MDQ dari meja MD.
5. **Format tanggal rekap**: tanggal di layar rekap masih memakai `<input type=date>` bawaan, belum KNDatePicker.
6. **Tes lama yang gagal (bukan regresi)**: `test_role_editor_iter35–38` dan `test_access_roles_iter32` gagal karena data fixture lama, misalnya peran `cr_staf_penagihan` tidak ada dan jumlah modul di-hardcode.
7. **Panel tak terpakai**: `components/ProductDetail.jsx` tidak diimpor di mana pun. Triad warna sudah dipasang di Quick View dan MD HP.

## 7. Berkas tes per area

- **L00**: `test_l00_p05_open_issues.py`, `test_l00_edge_cases.py`
- **L01**: `test_l01_grade_visibility.py`, `test_l01_sales_field_hidden_api.py`, `test_l01_sku_mask_settle_tol.py`, `test_l01_material_loss.py`, `test_l01_custom_role.py`, `test_l01_dataset_recap.py`, `test_l01_dataset_edge.py`, `test_l01_fabric_xlsx_color.py`
- **L04**: `test_l04_mdq_cut.py`, `test_l04_mdq_cut_edge.py`
- **Regresi P05**: `test_p05_acceptance_acc31_33_34.py`, `test_p05_restock_material_revalidation.py`, `test_p05_imp16_md_quality_qc.py`
- **Laporan testing agent**: `/app/test_reports/iteration_183.json` … `iteration_188.json`

## 8. Prompt mulai sesi berikut (salin)

> Lanjutkan repo KNHOST, paket `docs/development/gelombang-lanjutan-pasca-p05-2026-10-16/`. Baca dulu `evidence/HANDOFF_SESI_2026-10-16.md`, `KEPUTUSAN_AKTIF_RINGKAS.md`, dan `evidence/L00/owner_decisions_2026-10-16.md`. Siapkan env sesuai §0, jalankan tes per file (§7), lalu lanjutkan L04 (LN-040, LN-041 verifikasi, LN-042-T03, LN-043). Laporkan per fase dan tunggu persetujuan sebelum lanjut.
