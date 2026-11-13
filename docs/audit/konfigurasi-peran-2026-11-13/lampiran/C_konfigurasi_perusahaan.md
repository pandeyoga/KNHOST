# C — Konfigurasi Perusahaan di Luar Pusat Pengaturan (KNHOST)

Tanggal tinjau: 2026-11-13 · `HEAD` = `dca195b` · cara kerja: **baca kode saja** (tidak ada server dijalankan, tidak ada berkas repo diubah).
Lingkup: grup menu "Pengaturan" (`frontend/src/config/navStructure.js:400-425`, `frontend/src/config/hubTabs.js:238-305`) **kecuali** registry 310 kunci dan layar Peran & Hak Akses.
Tanda bukti: **T** = terbukti dari kode (berkas:baris disebut) · **I** = inferensi (perlu uji jalan / data nyata).
Alat bantu baca-saja yang dipakai: pencocokan statis 282 panggilan API layar ↔ 1.748 rute backend; pemindai nama-tak-terdefinisi (symtable) atas seluruh `routers/` + `services/`; pemindai konstanta huruf besar (264 temuan mentah).

---

## 1. Ringkasan (12 baris)

1. **Master PT menyimpan lima isian yang tidak dibaca kode mana pun** — skema penomoran, penanggung insentif, awal tahun fiskal, template CoA, induk grup; pilihan "Deret bersama grup" dan "Tingkat grup" di wizard tidak berakibat apa-apa (T, KP-01).
2. **Status PKP hanya bisa dipilih saat PT dibuat**; layar detail tidak punya isian untuk mengubahnya, padahal backend menerima dan daftar kesiapan menyuruh "ubah status PKP-nya" (T, KP-02).
3. **Persetujuan hidup dalam ≥ 6 mekanisme** dengan tiga cara menentukan penyetuju (peringkat peran · daftar peran literal · izin); pengaturannya tersebar di 11 kelompok registry + 1 tabel + 3 daftar ditulis mati (T, KP-06/07).
4. **Setuju-sendiri tidak seragam**: 2 sakelar (bawaan MELARANG), 12 titik melarang ditulis mati, ≥ 14 pintu tanpa pemeriksaan sama sekali; admin lolos di 13 dari 17 titik larangan. Belum sesuai keputusan pemilik "bisa diatur, bawaan satu orang" (T, KP-05, Lampiran C).
5. **Dua pilihan di layar Aturan Persetujuan menyesatkan**: penyetuju "Owner" tidak ada perannya (diperlakukan = Manajer) dan jenis "Diskon (%)" tidak dibaca mesin mana pun (T, KP-03/04).
6. **Penomoran dokumen seluruhnya ditulis mati**: 59 awalan di 90 titik panggil, lebar 5 digit, tanpa reset tahunan; 18 awalan memakai deret bersama grup tanpa kode PT walau wizard menjanjikan "awalan SEMUA nomor dokumen" (T, KP-12, Lampiran D).
7. **Daftar kesiapan PT hanya 8 butir** dan tidak memeriksa pemetaan akun, periode buku, penanda tangan, akun kas, alamat; tombol "Gudang" membuka layar yang salah (T, KP-10).
8. **Penjadwal**: mengubah selang untuk 11 job berbasis menit tersimpan tetapi tidak pernah dipakai; penerima notifikasi dan ambang hari (H-3/H-1, 7 hari, 3 hari, 2 hari) ditulis mati (T, KP-09/20).
9. **Dokumen & Cetak**: identitas/kop per PT ada di 3 tempat; teks penutup, footer, tempat & slot tanda tangan bersifat global (tidak per PT); faktur tidak memuat rekening bank PT (T, KP-18/19).
10. **Rahasia & perangkat**: token mesin absen dikirim utuh ke semua pemegang `hr.view` dan disimpan polos; token WhatsApp polos di dua tempat; hanya kunci AI yang dienkripsi (T, KP-14/15/16).
11. **Kesesuaian layar ↔ endpoint**: 282 panggilan API dari 19 layar pengaturan — semuanya punya rute dengan metode yang sama (T); satu rute rusak saat dijalankan: `GET /api/entities/count` (nama tak terdefinisi) (T, KP-17).
12. **Susunan menu**: 12 hub / 30 tab / 43 layar ujung (dua tingkat); 3 hub hanya berisi 1 tab; empat istilah untuk hal yang sama (Perusahaan / Badan Usaha / Entitas / PT); usulan 9 hub / 35 tab satu tingkat dengan satu rumah untuk persetujuan dan penomoran (KP-33, §5).

---

## 2. Jawaban per butir tugas

### 2.1 Badan usaha (PT)

**Data yang bisa diisi untuk satu PT** (T — `backend/schemas.py:122-152`, `services/entity_lifecycle_service.py:40-46`):

| Data | Ada? | Di mana | Dipakai kode? |
|---|---|---|---|
| Jenis badan, nama hukum, nama singkat, nama pemilik + label usaha (perorangan) | Ya | wizard + detail | Ya |
| NPWP | Ya (wajib bila PKP, tanpa cek pola) | wizard + detail | Ya (faktur, kop) |
| Alamat, wilayah tervalidasi, telepon, email | Ya | wizard + detail | Ya |
| Logo (URL) | Ya | wizard + detail | Ya, tetapi ditimpa `document_branding.logo_b64` |
| Status PKP (`default_tax_mode`) | Ya, **hanya saat buat** | wizard | Ya — menentukan PPN (`config_service.py:251-256`) |
| Awalan nomor dokumen (`doc_prefix`) | Ya, terkunci setelah dokumen pertama | wizard + detail | Ya |
| Tahun buku (`fiscal_year_start`, MM-DD) | Ya | wizard + detail | **Tidak** — yang dipakai `finance.fiscal_year_end_month` |
| Mata uang (`currency`, teks bebas) | Ya | wizard | Hanya tampilan (`gl_service.py:3739`); yang dipakai `finance.base_currency` |
| Skema penomoran, penanggung insentif, template CoA | Ya | wizard | **Tidak** |
| Induk grup / penanda PT grup (`parent_entity_id`, `is_group`) | Hanya lewat API | — | `is_group` dibaca konsolidasi; `parent_entity_id` tidak |
| Rekening bank & kas | Bukan di master PT | Keuangan › Rekening & Saldo (`bank_accounts.entity_id`) | Ya |
| Gudang | Bukan di master PT | Master Gudang (`md-warehouses`, bersama/khusus) | Ya |
| Termin pembayaran | Bukan di master PT | Master per Badan Usaha (berlapis grup → PT) | Ya |
| Akun buku besar | Bukan di master PT | CoA bersama + Pemetaan Akun per PT | Ya |
| Penanda tangan, cap, kop gambar | Bukan di master PT | Template Dokumen › Desainer PDF (`document_branding`) | Ya |
| NITKU, NIB, tanggal/nomor pengukuhan PKP, KPP, alamat pajak terpisah, nama direktur | **Tidak ada** | — | — |

**Syarat "siap dipakai"** (T — `services/entity_readiness_service.py:49-116`): 8 butir — pengguna, gudang yang boleh dipakai, rekening bank, harga jual, saldo awal, kop & logo, konfigurasi pajak, tahun fiskal. Tidak lengkap → KP-10.

**Saat PT baru dibuat** (T — `services/entity_provisioning_service.py:144-198`):
* Dibuat: dokumen PT + nilai bawaan; `gl_service.seed_default_coa()` (bagan akun **bersama** seluruh grup, bukan salinan per PT); satu dokumen penanda lapisan pengaturan kosong (`system_settings.scope = id PT`); pemasok bertipe "entitas grup" di semua PT lain (`group_partner_service.sync_group_entity_suppliers`).
* Berlaku otomatis lewat lapisan "grup": termin, aturan persetujuan, kategori beban, tarif insentif, pemetaan akun, template dokumen, jadwal notifikasi.
* **Tertinggal (harus diisi tangan)**: pengguna, gudang khusus, rekening bank & akun kas, harga per PT, saldo awal, kop/penanda tangan, periode buku pertama, pelanggan "entitas grup" di sisi jual, deret nomor (lahir saat dokumen pertama).

**Mengarsipkan PT** (T — `services/entity_lifecycle_service.py:269-363`): bukan hapus. Ditolak (409 + rincian) bila masih ada pengguna utama, dokumen terbuka, saldo hidup, atau jurnal sesudah tutup buku terakhir; admin boleh memaksa dengan alasan; sesi pengguna utamanya dicabut; setelah itu PT terkunci-tulis (`:429-443`) tetapi tetap bisa dibaca; bisa diaktifkan kembali. Celah → KP-22.

### 2.2 Master per badan usaha, Registri Domain, Kategori Beban, Pemetaan Akun, Aturan & Template Bank

* **Master per Badan Usaha** (T — `services/entity_master_service.py:59-232`): 10 jenis terdaftar; 5 dikelola di sini (syarat pembayaran, lini produk, tahapan proses, jenis sampling, alasan keluhan retur), 5 hanya tautan ke layar lain (`EntityMastersView.jsx:29-35`). Pola lapisan benar: baris grup tidak bisa diubah dari konteks satu PT; "Buat khusus" menyalin; "Lepas" menghapus salinan.
* **Registri Domain** (T — `features/admin/domain/DomainRegistryView.jsx:1-11`): **layar rujukan + simulator, tidak ada yang bisa diatur** (satu-satunya panggilan tulis adalah simulasi `POST /enums/stage-transitions/validate`). Namanya teknis dan letaknya di "Master Data" memberi kesan bisa diubah.
* **Kategori Beban**: satu editor berlapis (`/entity-masters/expense-categories`), akun tujuan per PT. Benih 8 kategori + kode akun ditulis di `services/cash_advance_service.py:47-56` (T).
* **Pemetaan Akun** (T — `routers/gl_mappings.py:34-83`, `services/gl_mapping_registry.py`): per PT, wajib beralasan, ada riwayat, dipakai saat posting (`gl_service.py:599`). Rincian keuangan sudah diaudit di `docs/finance/AUDIT_KEUANGAN_2026-11-13.md`; di sini hanya dicatat pasangan ganda dengan `bank.*_account_code` (KP-30).
* **Aturan & Template Bank**: 2 tab (aturan hasil belajar, template mutasi bank); bobot pencocokan ada di registry (`bank.*`) → dua tempat untuk satu topik (I).

### 2.3 Persetujuan

**Berapa mekanisme yang hidup bersamaan** (T):

| # | Mekanisme | Sumber aturan | Dokumen tercakup | Penyetuju ditentukan oleh | Per PT? |
|---|---|---|---|---|---|
| A | Aturan Persetujuan | koleksi `approval_rules` (`routers/approval_rules.py:16`) | SO, PO, PR, "Diskon" (tak dibaca) | **peringkat** peran (`role_registry.py:365-372`) | Ya (aturan PT **menggantikan** seluruh aturan grup jenis itu) |
| B | Tingkat tambahan | registry `approval.extra_levels` (`config_service.py:96-104, 360-374`) | PO (bawaan ≥ Rp500 jt → admin) | peringkat peran | Ya |
| C | Matriks persetujuan divisi | **ditulis mati** `config_divisions.py:83-119` + 5 sakelar registry | ACC desain, ACC sample, PO custom (2 tingkat), PR, klaim makloon | **daftar peran literal** per tingkat | Hanya sakelar & ambang Direksi |
| D | Ambang per modul | registry: `amendment.*`, `antar_entitas.*`, `contra_bon.*`, `case.*`, `payment.*`, `pricelist.customer_price_approval`, `registration.finance_approval`, `makloon.claim_approval_roles`, `rnd.spec_approval_roles`, `rnd.sample_decision_roles`, `returns.cutloss_treatment_roles`, `purchasing.price_deviation_approval_percent` | amandemen, antar-PT, kontrabon, kasus keuangan, denda, selisih bayar, harga khusus, registrasi awal, makloon, R&D, retur | nama peran dari pengaturan (sebagian peringkat, sebagian daftar) | Ya |
| E | Entri persetujuan SO | `pending_approvals` di dokumen SO | nilai, kredit, harga khusus, bayar sampel, makloon | peran **ditulis mati** (`so_approvals.py:204,257`; `sales_orders.py:568,581`) | Tidak |
| F | Rantai tetap di kode | konstanta | uang muka/PD 3 tahap (`cash_advance_service.py:34-41`), pesanan khusus > Rp10 jt (`special_order_service.py:24`), tagihan supplier & voucher biaya masuk → "manager" (`vendor_bills.py:309`, `landed_cost.py:180`), tagihan kampanye → "finance" (`marketing_cost_service.py:197`) | daftar peran literal / peringkat | Tidak |
| G | Izin saja | matriks izin (`X.approve`, `hr.manage_attendance`, `hr.manage_payroll`, `inventory.approve_count`, …) | transfer, opname, retur jual/beli, cuti, lembur, penggajian, buka periode, dll. | **izin** | Lewat peran |

Papan antrean (`services/approval_backlog_service.py:40-300`) menghitung **38 antrean keputusan**; itulah jumlah pintu persetujuan nyata.

* **Jumlah penyetuju (1 atau 2 orang)**: tidak ada pengaturan "N orang pada satu tingkat". Dua orang hanya terjadi lewat *tingkat berjenjang* (PO: A+B; PO custom: C tingkat 2) dan PO melarang orang yang sama menandatangani dua tingkat (`purchase_orders.py:839-844`, ditulis mati) (T).
* **Jenjang nominal per PT**: bisa untuk A, B, D; hanya ambang Direksi untuk C; tidak bisa untuk E, F (T).
* **"Pembuat boleh menyetujui sendiri" per PT**: hanya lewat `approval.matrix_sod` (global/PT, bawaan aktif = melarang) dan `amendment.dual_control`; sisanya ditulis mati atau tidak diperiksa → Lampiran C (T).

### 2.4 Penomoran dokumen

Satu fungsi: `core_utils.next_doc_number` (`core_utils.py:19-76`). Format per PT `KODE/AWALAN-00001` (deret atomik per PT + jenis di `number_sequences`); format bersama `AWALAN-00001`. **Awalan, pemisah, lebar digit, dan pilihan "per PT / bersama" ditentukan di tiap titik panggil** — 90 titik, 59 awalan (Lampiran D). Yang bisa diatur hanya `KODE` (awalan PT). Tidak ada tahun/bulan dalam nomor (kecuali lot), tidak ada reset tahunan (T).

### 2.5 Dokumen & Cetak

| Hal | Per PT | Global |
|---|---|---|
| Nama perusahaan, slogan, alamat, telepon, email, situs, NPWP di kop | Ya (`document_branding`, `pdf_service.py:216-241`) | — |
| Logo, kop gambar, footer gambar, cap, gambar tanda tangan + nama penanda tangan | Ya | — |
| Ukuran kertas, margin, huruf, warna, watermark, judul, kolom tabel, bagian tampil/sembunyi | — | Ya, per **jenis dokumen** (`pdf_templates`, `pdf_service.py:143-158`) |
| Teks pembuka, teks penutup, teks footer, kota tanda tangan (`place`), slot tanda tangan (label/peran), isian tambahan | — | Ya, per jenis dokumen |
| Template dasar lama (kop/footer/kolom Surat Jalan & Invoice) | Ya (berlapis, `document_templates`) | Ya |
| Rekening bank pembayaran di faktur | **Tidak ada** | hanya bisa diketik di teks penutup global |

### 2.6 Notifikasi & Penjadwal

* Bisa diatur (T — `schemas_scheduler.py:11-48`, `routers/scheduler.py:89-175`): hidup/mati tiap job, jam & menit job harian, selang jam job berkala; WhatsApp (penyedia, token, nomor PIC, kirim-ke-peran, tingkat minimum, seketika/ringkasan); eskalasi (hidup/mati, 1–72 jam, tingkat minimum, kedalaman 1–3).
* Ditulis mati (T): daftar 38 job (`scheduler_service.py:80-292`); zona waktu `Asia/Jakarta` (`:58`); H-3/H-1/H/H+1 (`alert_ops_service.py:54`); hutang jatuh tempo ≤ 7 hari, WO 3/7 hari, tugas gudang 2 hari, maks 40 alert per job (`alert_service.py:25-29`); penerima per job = satu peran literal (`alert_service.py:85,172,201,234,277,319`); rantai eskalasi sales/gudang → manager → admin (`escalation_service.py:36-43`); peran penerima siaran `["admin","manager"]` (`wa_alert_service.py:31`).
* Semua pengaturan penjadwal **global** (`system_settings.scope="alerts"`), tidak per PT.

### 2.7 Integrasi & Sistem, Perangkat

* **Kunci API**: Anthropic, Gemini, OpenAI di `PUT /api/admin/integrations` — dienkripsi (Fernet), tidak pernah dikirim balik (`integrations_service.py:38-52, 83-96`). Dijaga izin bernama `hr.manage_settings` (`routers/integrations.py:20`).
* **WhatsApp**: dua konfigurasi terpisah — penjadwal (`system_settings.alerts.wa`) dan pengiriman dokumen (`integration_settings`, layarnya di Pusat Dokumen).
* **Perangkat**: RFID (kunci di-hash, `rfid_ingest_service.py:37`) dan mesin absen (token polos, `hr_attendance.py:205`).
* **Cadangan**: hanya skrip `deploy/backup.sh`; tidak ada layar, status, atau jadwal cadangan di dalam aplikasi (T).

### 2.8 Pengaturan yang punya dua tempat → Lampiran B (22 pasangan).
### 2.9 Nilai bisnis ditulis mati → Lampiran A (72 butir).

### 2.10 Kesesuaian layar ↔ endpoint

19 layar pengaturan beserta 121 berkas yang diimpornya memuat **282 panggilan `axios`**. Hasil pencocokan statis metode + pola jalur terhadap 1.748 rute backend (T):
* 239 cocok langsung; 41 memakai URL dari variabel (`ENDPOINTS`, `GRN`, `OCS`, `base`) — diperiksa satu per satu, semuanya ada (`hr/shifts|geofences|devices`, `goods-receipts/*`, `ocr-samples/*`, `rfid/v2/ops/devices/*`); 2 memakai segmen dinamis (`client-dataset/batches/{id}/{commit|rollback}`, `design-gallery/{id}/lifecycle/{aksi}`) — ada.
* **Tidak ada panggilan layar pengaturan tanpa endpoint.** Semua 160 modul router terdaftar di `server.py` (dua lewat sarang: `initial_registration` → `cycle_count`, `rfid_printers` → `rfid`).
* Yang rusak saat dijalankan (bukan soal rute): `GET /api/entities/count` (KP-17). Yang "berhasil tetapi tidak berakibat": KP-01, KP-04, KP-09, KP-11, KP-13.
* Batas cara ini: hanya membuktikan rute ada; isi permintaan/jawaban tidak diuji (I).

### 2.11 Bahasa & pengelompokan → §5.

---

## 3. Tabel temuan

| ID | Tingkat | Temuan | Bukti (berkas:baris) | Akibat | Usulan |
|---|---|---|---|---|---|
| KP-01 | Tinggi | Lima isian master PT tidak dibaca kode mana pun: skema penomoran, penanggung insentif, awal tahun fiskal, template CoA, induk grup. Wizard menawarkan pilihan ("Deret bersama grup", "Tingkat grup") dan menulis "Menentukan periode laporan & tutup buku". **T** | Isian: `frontend/src/features/settings/entities/EntityWizard.jsx:292-298, 300-311, 351-360`; bawaan: `backend/services/entity_context_service.py:25-33`; pencarian seluruh `backend/` → hanya `bootstrap.py:339-349`, `schemas.py`, dan layanan PT sendiri. Penomoran: parameter `scheme` tidak pernah diisi dari PT (`core_utils.py:19-21`). Tahun buku nyata: `config_catalog_core.py:91`, `closing_service.py:81` | Pemilik mengira sudah mengatur; sistem berjalan dengan nilai lain. Tahun buku bisa beda antara master PT dan tutup buku. | Hapus isian mati dari wizard/detail, atau sambungkan. Tahun buku: satu sumber saja (pindahkan `finance.fiscal_year_end_month` ke profil PT, tampil sebagai bulan). |
| KP-02 | Tinggi | Status PKP tidak bisa diubah dari layar setelah PT dibuat. **T** | Daftar isian detail tanpa `default_tax_mode`: `EntityDetailDrawer.jsx:18-29`; hanya tampil: `:140-144`; backend menerima: `entity_lifecycle_service.py:40-46`; kesiapan menyuruh mengubah: `entity_readiness_service.py:105` | PT yang dikukuhkan PKP (atau dicabut) tidak bisa disesuaikan tanpa programmer; PPN = 0 selamanya untuk PT non-PKP (`config_service.py:254-256`). | Tambah tindakan "Ubah status PKP" beralasan + tanggal berlaku + pratinjau dampak (dokumen terbuka). |
| KP-03 | Tinggi | Penyetuju "Owner" bisa dipilih tetapi peran itu tidak ada; diperlakukan sama dengan Manajer. **T** | Pilihan: `approvalRulesConstants.js:13-18`, `routers/approval_rules.py:17`; peran tak dikenal → peringkat manajer: `role_registry.py:355-362`; daftar peran tanpa `owner`: `role_registry.py:48-222` | Aturan "≥ Rp X wajib Owner" lolos dengan persetujuan manajer mana pun. | Buang "Owner" atau petakan ke admin ("Direksi"); tolak peran tak dikenal saat simpan. |
| KP-04 | Tinggi | Jenis aturan "Diskon (%)" tidak punya pembaca. **T** | Pilihan: `approval_rules.py:16`, `approvalRulesConstants.js:10`; benih: `config_service.py:168-169`; pemanggil `evaluate_approval` hanya `sales_order`, `purchase_order`, `purchase_requisition` (`so_lifecycle_service.py:26`, `sales_orders.py:362`, `purchase_orders.py:586`, `rfq_service.py:204`, `pr_sourcing_service.py:602`, `purchase_requisition_service.py:185,288`) | Dua aturan diskon bawaan tampil aktif tetapi tidak pernah menahan apa pun. | Hapus jenis itu dari layar & benih (diskon manual sudah ditiadakan, `config_service.py:51-53`). |
| KP-05 | Tinggi | Aturan setuju-sendiri tidak satu sumber dan bawaannya melarang. 2 sakelar, 12 larangan ditulis mati, ≥ 14 pintu tanpa pemeriksaan; admin lolos di 13 dari 17 titik larangan (`approval_matrix_service.py:176-193`), tidak di 4 sisanya. **T** | Lampiran C | Keputusan pemilik "wajib dua orang bisa diatur, bawaan satu orang" belum bisa dijalankan: di PO/tagihan/kontrabon dsb. tidak ada sakelarnya; di cuti/penggajian/opname tidak ada penjaganya. | Satu fungsi penjaga (perluas `sod_blocked`) + satu tabel kebijakan per jenis dokumen per PT: `boleh_setuju_sendiri` (bawaan ya), `jumlah_penyetuju` (bawaan 1). Semua titik Lampiran C memanggil fungsi itu. |
| KP-06 | Tinggi | ≥ 6 mekanisme persetujuan hidup bersamaan; penyetuju ditentukan dengan tiga cara berbeda; matriks divisi ditulis mati. **T** | §2.3; `config_divisions.py:83-119`; `cash_advance_service.py:34-41`; `so_approvals.py:204,257` | Tidak ada satu layar yang menjawab "siapa menyetujui apa, mulai nominal berapa" untuk satu PT. Mengubah satu aturan tidak mengubah pintu lain yang sejenis. | Satu tabel "Aturan Persetujuan" yang mencakup semua 38 antrean: jenis dokumen × PT × jenjang nominal × penyetuju × jumlah penyetuju × setuju-sendiri. Mekanisme C/E/F jadi baris bawaan tabel itu. |
| KP-07 | Tinggi | Satu keputusan dinilai dua daftar peran. ACC desain: matriks ditulis mati **dan** `rnd.spec_approval_roles`; ACC sample: matriks **dan** `rnd.sample_decision_roles`; PR: matriks **dan** `approval_rules`. **T** | `routers/rnd.py:291` + `rnd_spec_service.py:360`; `routers/rnd.py:719` + `rnd_sample_service.py:1243`; `routers/purchase_requisitions.py:188` + `purchase_requisition_service.py:331` | Menambah peran di Pusat Pengaturan tidak cukup — matriks di kode tetap menolak; pesan galatnya menunjuk aturan yang berbeda. | Pilih satu sumber per keputusan (lihat KP-06). |
| KP-08 | Sedang | Aturan persetujuan khusus PT menggantikan **seluruh** jenjang grup untuk jenis dokumen itu; tidak ada pemeriksaan celah/tumpang-tindih rentang. **T** | `config_service.py:322-323` (`pool = scoped if scoped else …`); validasi hanya `max > min`: `approval_rules.py:42-51` | PT yang menambah satu aturan "≥ Rp500 jt → admin" kehilangan aturan grup "≥ Rp100 jt → manajer"; nominal di celah lolos tanpa persetujuan. | Tampilkan jenjang efektif per PT + peringatan celah; atau gabungkan per jenjang, bukan ganti semua. |
| KP-09 | Tinggi | Selang job berbasis menit tidak bisa diubah walau layar menerima. 11 job. **T** | Layar mengirim `interval_hours`: `SchedulerParts.jsx:80-110`; skema hanya `interval_hours`: `schemas_scheduler.py:18`; pemicu memilih `interval_minutes` bawaan lebih dulu: `scheduler_service.py:445-448`; job: `:110,123,212,220,227,235,250,256,263,278,287` | Admin mengubah "Kedaluwarsa Reservasi" jadi tiap 2 jam → tersimpan, label tetap "Setiap 30 menit", jadwal tidak berubah. Kolom isian menampilkan "4" yang bukan nilai sebenarnya. | Dukung `interval_minutes` di skema + layar, atau kunci isian untuk job teknis. |
| KP-10 | Tinggi | Daftar kesiapan PT tidak lengkap dan satu tautannya salah. **T** | 8 butir: `entity_readiness_service.py:49-116`; tombol gudang → `view:"admin"` (`:64`) yang kini "Integrasi & Audit" (`AppViewRouter.jsx:139`), padahal master gudang = `md-warehouses` (`:174`); "Rekening bank" ikut menghitung akun kas (`:41-42`); teks menyebut menu lama "Template PDF", "Master Data → Gudang" (`:63,95`) | PT dinyatakan 100% siap padahal belum bisa menerbitkan faktur berkop lengkap atau menutup buku; pengguna diarahkan ke layar yang salah. | Tambah butir: pemetaan akun wajib terisi (data sudah ada di `gl_mapping_service.list_mappings`), akun kas & bank terpisah, penanda tangan/kop, alamat lengkap, periode buku, pengguna keuangan, termin bawaan sah, deret nomor. Perbaiki tautan & teks. |
| KP-11 | Sedang | Termin bawaan per PT tidak dipakai saat membuat SO. **T** | Kunci berlapis grup+PT: `config_catalog_core.py:101-102`; SO membaca langsung dokumen global: `routers/sales_orders.py:353-356` | Nilai khusus PT di layar tidak berpengaruh; SO PT itu tetap memakai termin grup. | Baca lewat resolver dengan `entity_id`. |
| KP-12 | Tinggi | Awalan, format, lebar, dan cakupan nomor dokumen ditulis mati di 90 titik; 18 awalan bernomor bersama tanpa kode PT (di antaranya retur jual/beli, tagihan supplier, nota debit, PR, RFQ, perintah kerja); nota kredit & nota debit punya dua format. **T** | `core_utils.py:19-76`; Lampiran D; janji wizard: `EntityWizard.jsx:323-324`; nota kredit per PT `amendment_service.py:878`, `od_cancel_credit_note.py:44` vs bersama `return_service.py:154` | Nomor retur/tagihan/nota debit dua PT bercampur dalam satu deret; pemeriksa pajak melihat lompatan nomor per PT. Format tidak bisa disesuaikan (tahun, panjang). | Tabel "Penomoran Dokumen" per PT: jenis dokumen → awalan, lebar, sisipan tahun/bulan, reset; satu pembaca di `next_doc_number`. Putuskan (STOP & ASK) apakah deret bersama dipertahankan. |
| KP-13 | Sedang | `lot.number_format` tampil di Pusat Pengaturan tetapi nomor lot ditulis mati. **T** | `lot_service.py:133-137`; pembaca kunci hanya simulator: `config_simulator.py:315` | Mengubah format tidak mengubah nomor lot. | Sambungkan atau tandai "tidak dipakai". |
| KP-14 | Tinggi | Token mesin absen: dikirim utuh di daftar perangkat ke pemegang `hr.view`, disimpan polos, 12 heksadesimal; endpoint penerima absen hanya memeriksa token itu. **T** | `routers/hr_attendance.py:187-193` (tanpa penyaringan field), `:205`, `:503-513`; `core_utils.py:128-129`; layar menyalin token: `AttendanceSetupView.jsx:158` | Siapa pun yang bisa melihat menu SDM dapat mengirim data absen palsu atas nama PT (berakibat ke gaji) (**I** untuk penyalahgunaan). | Simpan hash, tampilkan sekali saat dibuat, sediakan "ganti token", batasi daftar ke `hr.manage_attendance`. |
| KP-15 | Sedang | Tiga standar penyimpanan rahasia: kunci AI dienkripsi; kunci RFID di-hash; token WhatsApp polos (dua koleksi). **T** | `integrations_service.py:38-52`; `rfid_ingest_service.py:37`; `routers/scheduler.py:131,143`; `delivery_service.py:44-55` | Cadangan basis data memuat token WhatsApp terbuka. | Pakai pembungkus enkripsi yang sama untuk semua rahasia. |
| KP-16 | Sedang | Dua konfigurasi WhatsApp terpisah (penyedia, token, nomor): Penjadwal & Notifikasi, dan Pusat Dokumen. **T** | `wa_alert_service.py:28-48`; `delivery_service.py:44-55`; layar kedua dipasang di `features/documents/DocumentCenter.jsx:8` | Token diganti di satu tempat, pengiriman dokumen tetap memakai yang lama; layar kedua tidak ada di grup Pengaturan. | Satu koneksi WhatsApp di Integrasi; dua pemakai (pengingat, kirim dokumen). |
| KP-17 | Sedang | `GET /api/entities/count` selalu gagal: memakai `include_test` yang bukan parameternya. **T** (satu-satunya nama tak terdefinisi di seluruh `routers/` + `services/`) | `routers/entities.py:83-95` (baris 90); klien: `entityApi.js:37-38` (diekspor, belum dipanggil layar mana pun) | 500 begitu ada yang memakai penghitung PT. | Tambah parameter `include_test`. |
| KP-18 | Sedang | Identitas & kop perusahaan ada di tiga tempat: master PT, `document_branding`, `document_templates`. Judul bawaan cetak lama ditulis "Kain Nusantara". **T** | `pdf_service.py:216-241` (branding menimpa master); `entity_master_service.py:76-87`; `inventory_service.py:146-150` | Alamat/NPWP diubah di master PT tetapi kop tetap lama; PT lain bisa tercetak "Kain Nusantara". | Profil PT = satu sumber identitas; branding hanya gambar (logo, kop, cap, tanda tangan). Pensiunkan template dasar atau jadikan satu mesin. |
| KP-19 | Sedang | Teks penutup, footer, kota & slot tanda tangan, watermark bersifat global per jenis dokumen; tidak bisa beda per PT. Faktur tidak memuat rekening bank PT. **T** (rekening: tidak ada rujukan bank di `pdf_resolvers.py`) | `pdf_service.py:19-45, 143-158` (kunci hanya `doc_type`) | Dua PT (beda kota, beda rekening, beda penanda tangan) tidak bisa punya naskah faktur sendiri. | Lapisan per PT untuk teks & slot (pola sama dengan master berlapis); token `{{rekening_bank}}` dari rekening utama PT. |
| KP-20 | Sedang | Penerima notifikasi dan ambang hari ditulis mati; tab "Penerima Notifikasi" hanya memuat 2 kunci. **T** | `alert_service.py:25-29, 85, 172, 201, 234, 277, 319`; `alert_ops_service.py:52-54`; kunci `notif.*` hanya `low_stock_division`, `po_stage_stuck_days` | Hutang jatuh tempo & penyusutan dikirim ke "manager", bukan Keuangan; H-3/H-1 tidak bisa diubah. | Tabel "pengingat → penerima (peran/orang) → ambang" per PT. |
| KP-21 | Rendah | Jadwal, WhatsApp, dan eskalasi berlaku untuk seluruh grup, tidak per PT. **T** | `wa_alert_service.py:28`; `scheduler_service.py:57` | PT dengan jam kerja/PIC berbeda tidak bisa dibedakan. | Cukup PIC & penerima per PT (KP-20); jadwal tetap global. |
| KP-22 | Sedang | Pemeriksaan sebelum mengarsipkan PT tidak lengkap. Dokumen terbuka hanya dari 17 koleksi; hutang supplier, saldo kas/bank, karyawan, uang muka, SPK makloon, PR, pesanan khusus, penerimaan barang tidak diperiksa; piutang dijumlah dari semua SO tanpa menyaring status. **T** | `entity_lifecycle_service.py:50-68, 230-253` | PT bisa diarsipkan dengan hutang/kas tersisa; atau tertahan karena "piutang" dari SO batal (**I**). | Lengkapi daftar; ambil piutang/hutang dari buku pembantu. |
| KP-23 | Sedang | Validasi isian PT longgar: NPWP tanpa pola, mata uang teks bebas, tahun fiskal `13-45` lolos; `is_group` tidak punya isian di layar padahal dibaca konsolidasi & 4 layar keuangan. **T** | `entity_provisioning_service.py:99-135`; `EntityWizard.jsx:285-289`; `consolidation_service.py:105`; pencarian `is_group` di `frontend/src` hanya pembaca | NPWP salah ketik masuk faktur; PT induk grup hanya bisa ditandai lewat API. | Pola NPWP 15/16 digit, pilihan mata uang, pemilih bulan; sakelar "PT induk (konsolidasi)". |
| KP-24 | Sedang | PT baru lahir tanpa rekening, akun kas, gudang, pengguna, kop, periode; pembuatan bukan satu transaksi. **T** / **I** (ketidak-atomikan) | `entity_provisioning_service.py:161-185` | Layar kosong & posting gagal pada hari pertama; bila langkah CoA gagal, PT sudah tersimpan setengah jadi. | Wizard lanjutan "Lengkapi PT" (rekening, kas, gudang, kop, admin PT) + kesiapan sebagai gerbang transaksi pertama. |
| KP-25 | Sedang | Pesanan khusus: ambang persetujuan Rp10.000.000 ditulis mati; ambang Direksi (Rp50 jt) justru bisa diatur. **T** | `special_order_service.py:24, 89`; `routers/special_orders.py:180, 273, 556` | Dua ambang untuk satu dokumen, hanya satu yang bisa diubah. | Jadikan baris di tabel aturan persetujuan. |
| KP-26 | Sedang | Rantai persetujuan uang muka (Atasan → Pimpinan → Keuangan) ditulis mati; dua tahap terakhir hanya peran admin. **T** | `cash_advance_service.py:34-41, 247-249` | Peran `finance` tidak bisa menyetujui tahap "Bagian Keuangan"; rantai tidak bisa dipendekkan per PT. | Pindah ke tabel aturan persetujuan. |
| KP-27 | Sedang | Blokir kredit (terlambat > 14 hari) dan peringatan 80% batas kredit ditulis mati, di dua berkas. **T** | `ar_aging_service.py:34-35, 96`; `customer_service.py:14-15, 253` | Kebijakan kredit tidak bisa disesuaikan; dua salinan bisa berbeda kelak. | Dua kunci registry (`ar.*`), satu pembaca. |
| KP-28 | Sedang | Masa reservasi pesanan 3 hari ditulis mati. **T** | `routers/sales_orders.py:544`; teks job `scheduler_service.py:106-109` | Tidak bisa diubah per PT/pelanggan. | Kunci registry `sales.reservation_days`. |
| KP-29 | Sedang | Pengaturan perusahaan yang letaknya di luar grup Pengaturan: jadwal bayar antar-PT (layar Antar-PT), WhatsApp dokumen + aturan kirim otomatis (Pusat Dokumen), rekening & kas, gudang. Asumsi Retur disimpan lewat jalur lama `PUT /api/settings`, tanpa riwayat registry. **T** | `IntercoPaymentSchedule.jsx:36`; `features/documents/WhatsAppSettings.jsx:26`; `ReturnAssumptionsPanel.jsx:36`; `routers/settings.py:19-20, 49` | Pemilik tidak menemukan semua pengaturan di satu grup; sebagian perubahan tidak tercatat di riwayat Pusat Pengaturan (**I**). | Tautkan dari hub terkait; pindahkan penyimpanan ke resolver. |
| KP-30 | Sedang | Akun biaya admin bank & titipan dana punya dua pengaturan: registry `bank.charge_account_code` / `bank.holding_account_code` dan Pemetaan Akun `kas_bank.beban_bank` / `kas_bank.titipan_dana`. **T** | `bank_recon_service.py:86-92`; `gl_mapping_registry.py:40-43` | Mengubah salah satu belum tentu mengubah jurnal (**I**: tergantung apakah kode masih bawaan saat `remap_lines`). | Hapus tiga kunci akun dari registry; pakai Pemetaan Akun. |
| KP-31 | Rendah | AI: hidup/mati & model di dua tempat — Integrasi (`anthropic.enabled/model`, dipakai AI SDM) dan registry (`ai.enabled`, `ai.model_main`, dipakai Tanya KN). **T** | `hr_ai_service.py:43`; `ai_narrative.py:72` | Mematikan di satu tempat tidak mematikan yang lain. | Integrasi = kunci saja; hidup/mati & model di satu tempat. |
| KP-32 | Rendah | Kunci integrasi dijaga izin `hr.manage_settings`. **T** | `routers/integrations.py:20, 27, 45, 68` | Izin SDM memberi kuasa atas kunci API perusahaan; nama izin menyesatkan saat mengatur peran. | Izin sendiri `integration.manage`. |
| KP-33 | Sedang | Pengelompokan & bahasa menu Pengaturan (§5). **T** | `hubTabs.js:238-305`; `navMeta.js:55-196` | Sulit menemukan pengaturan; persetujuan tersebar di 11 kelompok. | §5. |
| KP-34 | Rendah | Endpoint kop/branding tidak memeriksa apakah pengguna berhak atas PT yang disebut. **T** | `routers/pdf.py:258-267` | Kecil — pemegang izin `pdf_template` saat ini admin/manajer lintas-PT. | Tambah pemeriksaan `allowed_entity_ids`. |
| KP-35 | Rendah | Nomor tagihan jasa makloon (`VBM-`), kode karyawan (`EMP-`), dan pesanan khusus (`SORD-`) dibuat dengan "baca terakhir + 1", bukan deret atomik. **T** (cara baca) / **I** (kembar saat serempak) | `makloon_order_service.py:1407-1416`; `hr_service.py:50-61`; `special_order_service.py:62-70` | Nomor kembar bila dua orang menyimpan bersamaan. | Pakai `next_doc_number`. |
| KP-36 | Rendah | Tabel PTKP & tarif pajak penghasilan ditulis mati, sementara kunci `hr.ptkp_table` ditandai "tidak dipakai" padahal PTKP dipakai pada hitungan masa pajak terakhir. **T** | `hr_payroll_service.py:23-73, 88-93`; `config_catalog_ops.py:479-491` | Perubahan PTKP/TER oleh pemerintah butuh programmer; keterangan di layar tidak tepat. | Tabel tarif sebagai data bertanggal berlaku. |

Jumlah: **Tinggi 11 · Sedang 19 · Rendah 6 · total 36.**

---

## 4. Yang sudah benar (supaya tidak dirombak)

* Satu jalur validasi buat/ubah PT; `status` tidak bisa diubah lewat PATCH biasa (`routers/entities.py:162-193`) (T).
* Awalan nomor PT terkunci setelah dokumen pertama, dengan pesan yang menyebut dokumennya (`entity_lifecycle_service.py:142-194`) (T).
* Arsip PT: pratinjau dampak, paksa hanya admin + alasan, kunci-tulis di satu titik (`:315-363, 429-443`) (T).
* Master berlapis grup → PT dengan larangan mengubah baris grup dari konteks satu PT (`entity_master_service.py:435-450`) (T).
* Pemetaan Akun: per PT, beralasan, beriwayat, dipakai posting (T).
* Kunci AI terenkripsi & tidak pernah dikirim balik (T).
* Tidak ada panggilan layar pengaturan yang menggantung tanpa endpoint (T).

---

## 5. Bahasa & pengelompokan

### 5.1 Keadaan sekarang — 12 hub, 30 tab terlihat (+1 alias tersembunyi), 43 layar ujung

Tujuh tab adalah wadah yang punya tab lagi di dalamnya (Badan Usaha & Akses 5, Template Dokumen 2, Penjadwal & Notifikasi 3, Perangkat 2, Penerimaan & OCR 4, Aturan & Template Bank 2, Shift & Geofence 2) → 30 − 7 + 20 = 43 layar ujung, kedalaman dua tingkat (T).

| Hub | Tab | Catatan |
|---|---|---|
| Perusahaan & Akun | Badan Usaha & Akses (+ alias tersembunyi Peran & Hak Akses) | 1 tab; di dalamnya 5 tab lagi (Badan Usaha · Akun & Akses · Peran & Hak Akses · Cek Peran · Kesiapan). Nama hub ≠ nama tab. |
| Persetujuan | Aturan Persetujuan · Divisi & Persetujuan R&D · Persetujuan & Ambang | Tiga nama mirip; isi tab ke-3 hanya 8 dari 33 kunci persetujuan. |
| Penjualan | Aturan Penjualan · Label Alasan Amandemen · Komisi & Insentif · Kebijakan Retur | — |
| Gudang & Mutu | Aturan Gudang & Mutu · Penerimaan & OCR · Master Grade Mutu | "OCR", "Profil SJ" istilah teknis. |
| Pembelian & Produksi | Aturan Pembelian & Makloon | 1 tab; hub menyebut Produksi, tab menyebut Makloon. |
| Keuangan & Pajak | Aturan Keuangan & Pajak · Pemetaan Akun · Kategori Beban · Aturan & Template Bank | Termin pembayaran tidak di sini. |
| SDM | SDM & Penggajian · Shift & Geofence | "Geofence". Mesin absen pindah ke hub lain. |
| R&D | R&D & Desain | 1 tab. |
| Master Data | Master per Badan Usaha · Registri Domain · Impor Dataset Klien | Master produk/pelanggan/gudang ada di hub lain; "Registri Domain" hanya rujukan; impor = alat sekali pakai. |
| Dokumen & Cetak | Template Dokumen · Aturan Dokumen | Di dalam: "Kop & tata letak dasar" + "Desainer PDF". |
| Notifikasi & Penjadwal | Penjadwal & Notifikasi · Penerima Notifikasi | Di dalam: "Job Terjadwal", "Riwayat Eksekusi", "WhatsApp". "Job" bahasa Inggris. |
| Integrasi & Sistem | Semua pengaturan · Tampilan & Asisten · Perangkat · Integrasi & Audit | Huruf kecil "pengaturan"; id layar `admin`. |

Masalah bahasa yang berulang (T):
* Empat kata untuk satu hal: **Perusahaan** (hub), **Badan Usaha** (tab), **Entitas** (`navMeta.js:175`, "Semua Entitas"), **PT** (antar-PT).
* Kata teknis di layar: Registri Domain, Job, Geofence, OCR, Dataset, Override ("Buat khusus" sudah benar), Simulasi, "Konfigurasi Berjalan" (`navMeta.js:159`).
* "Persetujuan" muncul sebagai: Aturan Persetujuan, Persetujuan & Ambang, Divisi & Persetujuan R&D, Pusat Persetujuan, Persetujuan Saya, Matriks divisi.
* Teks bantu kesiapan PT menyebut menu yang sudah tidak ada ("Template PDF", "Master Data → Gudang").

Salah tempat:
* Syarat pembayaran → seharusnya Keuangan. Alasan keluhan retur → Penjualan (dekat Kebijakan Retur). Lini produk / tahapan proses / jenis sampling → Produksi & R&D.
* Mesin absen (Perangkat, hub Sistem) terpisah dari Shift & Geofence (hub SDM).
* WhatsApp dokumen di Pusat Dokumen, bukan di Pengaturan.
* Label Alasan Amandemen di Penjualan, padahal amandemen juga dipakai keuangan (`features/finance/amendments/`).

### 5.2 Usulan — 9 hub, 35 tab (tab dalam dinaikkan supaya terlihat dari menu)

| Hub baru | Tab | Asal |
|---|---|---|
| **1. Perusahaan (PT)** | Profil PT (identitas, pajak/PKP, tahun buku, mata uang) · Rekening, Kas & Gudang (ringkasan + tautan) · Kesiapan PT | Badan Usaha, Kesiapan; isian mati dibuang (KP-01) |
| **2. Pengguna & Hak Akses** | Akun · Peran & Hak Akses · Cek Peran | pecahan Badan Usaha & Akses |
| **3. Persetujuan** | Aturan Persetujuan (semua jenis dokumen, jenjang, jumlah penyetuju, setuju-sendiri, per PT) · Pengingat & Ketegasan | 3 tab lama + 25 kunci dari 10 kelompok lain + daftar ditulis mati |
| **4. Penjualan** | Aturan Penjualan · Komisi & Insentif · Retur (kebijakan + alasan keluhan) · Alasan Koreksi | + alasan keluhan |
| **5. Gudang, Pembelian & Produksi** | Aturan Gudang & Mutu · Penerimaan Barang (baca surat jalan otomatis) · Grade Mutu · Aturan Pembelian & Makloon · R&D & Desain (aturan + lini, tahapan, jenis sampling) | gabungan 3 hub (2 di antaranya ber-tab tunggal) |
| **6. Keuangan & Pajak** | Aturan Keuangan & Pajak · Syarat Pembayaran · Pemetaan Akun · Kategori Beban · Bank (aturan cocok & template mutasi) | + syarat pembayaran |
| **7. SDM** | Aturan SDM & Penggajian · Shift & Lokasi Absen · Mesin Absen | + mesin absen |
| **8. Dokumen & Notifikasi** | Kop & Tanda Tangan per PT · Template Dokumen · Penomoran Dokumen (baru) · Pengingat Otomatis (jadwal, penerima, ambang) · WhatsApp | gabungan 2 hub + WhatsApp dokumen |
| **9. Sistem** | Integrasi (kunci AI/baca dokumen) · Perangkat RFID · Riwayat & Audit · Data Awal & Rujukan (impor, kamus aturan kain) · Cari Semua Pengaturan | hub lama + sisa Master Data |

| Ukuran | Sebelum | Sesudah |
|---|---|---|
| Hub | 12 | 9 |
| Tab tingkat menu | 30 | 35 (5 tab dalam "Badan Usaha & Akses" dan tab WhatsApp/Mesin absen/Kop dinaikkan; 1 tab baru: Penomoran Dokumen) |
| Layar ujung (termasuk tab di dalam layar) | 43, dua tingkat | ± 41, hampir semua satu tingkat (tab dalam tersisa: Penerimaan Barang, Bank, Pengingat Otomatis) |
| Hub ber-tab tunggal | 3 | 0 |
| Tempat mengatur persetujuan | 3 tab + 10 kelompok registry lain + 3 daftar di kode | 1 hub |
| Kata untuk badan usaha | 4 | 1 ("PT"; "Semua PT" untuk mode gabungan) |
| Alias lama | tetap hidup lewat `viewAliases.js` | tetap |

Urutan mengikuti urutan mengisi saat PT baru dibuka: PT → orang → persetujuan → aturan per bagian → dokumen → sistem.

---

## Lampiran A — Nilai bisnis yang ditulis mati (72 butir)

Kolom "Kunci registry" : nama kunci yang **sudah ada** dan seharusnya dipakai, atau "belum ada". Semua **T** kecuali ditandai.

| # | Berkas:baris | Nilai | Arti | Kunci registry |
|---|---|---|---|---|
| 1 | `services/ar_aging_service.py:35` | 14 hari | Terlambat lebih dari ini → pelanggan diblokir | belum ada |
| 2 | `services/customer_service.py:15` | 14 hari | Salinan kedua dari #1 | belum ada |
| 3 | `services/ar_aging_service.py:34` | 0,8 | Piutang ≥ 80% batas kredit → peringatan | belum ada |
| 4 | `services/customer_service.py:14` | 0,8 | Salinan kedua dari #3 | belum ada |
| 5 | `routers/sales_orders.py:544` | 3 hari | Masa reservasi stok pesanan | belum ada (`sales.keep_max_age_days` untuk hal lain) |
| 6 | `services/customer_service.py:21` | 2 orang | Maksimum anggota group sales | belum ada |
| 7 | `services/special_order_service.py:24` | Rp10.000.000 | Pesanan khusus di atas ini wajib persetujuan | belum ada (yang ada `approval.po_custom_direksi_min`) |
| 8 | `services/special_order_phase2.py:27` | 30% | Margin bawaan pesanan khusus | belum ada |
| 9 | `services/special_order_phase2.py:280` | 2 | Jumlah item minimum "multi-item" | belum ada |
| 10 | `services/cash_advance_service.py:34-41` | 3 tahap; peran manager/admin, admin, admin | Rantai persetujuan uang muka | belum ada |
| 11 | `services/cash_advance_service.py:47-56` | 8 kategori + kode akun | Benih kategori beban kas kecil | master Kategori Beban (sesudah benih) |
| 12 | `config_divisions.py:83-119` | 5 tahap × peran | Matriks persetujuan divisi | hanya ambang Direksi |
| 13 | `config_divisions.py:24-41` | 8 divisi | Daftar divisi R&D | belum ada |
| 14 | `routers/so_approvals.py:257` | "manager" | Penyetuju lewat-batas kredit | belum ada |
| 15 | `routers/so_approvals.py:204` | "manager" | Penyetuju harga khusus di SO | `pricelist.customer_price_approval` (sebagian) |
| 16 | `routers/sales_orders.py:568` | "finance" | Penyetuju pembayaran sampel | belum ada |
| 17 | `routers/sales_orders.py:581` | "manager" | Penyetuju pemakaian stok cadangan makloon | belum ada |
| 18 | `routers/vendor_bills.py:309, 367` | "manager" | Penyetuju tagihan supplier di luar toleransi | belum ada |
| 19 | `routers/landed_cost.py:180` | "manager" | Penyetuju voucher biaya masuk (selalu wajib) | belum ada |
| 20 | `services/marketing_cost_service.py:197` | "finance" | Penyetuju tagihan kampanye | belum ada |
| 21 | `services/interco_service.py:53` | ("sales_admin",) | Peran yang boleh transaksi antar-PT sendiri di bawah ambang | belum ada |
| 22 | `services/config_service.py:160-170` | 7 baris | Aturan persetujuan bawaan (PO ≥ Rp100 jt, PR ≥ Rp50 jt → manajer) | tabel `approval_rules` (sesudah benih) |
| 23 | `services/config_service.py:100-102` | Rp500.000.000 → admin | Tingkat 2 PO | `approval.extra_levels` (ada) |
| 24 | `services/alert_ops_service.py:54` | [-3, -1, 0, 1] | Hari pengingat piutang (H-3/H-1/H/H+1) | belum ada |
| 25 | `services/alert_service.py:25` | 7 hari | Hutang supplier "segera jatuh tempo" | belum ada |
| 26 | `services/alert_service.py:26` | 3 hari | Perintah kerja dirilis dianggap tertunda | belum ada |
| 27 | `services/alert_service.py:27` | 7 hari | Perintah kerja draf dianggap tertunda | belum ada |
| 28 | `services/alert_service.py:28` | 2 hari | Tugas gudang dianggap tertunda | belum ada |
| 29 | `services/alert_service.py:29`, `alert_ops_service.py:55` | 40 | Maksimum alert per job per jalan | belum ada |
| 30 | `services/alert_ops_service.py:52` | 24 jam | Jendela "barang PO datang" | belum ada |
| 31 | `services/alert_service.py:85,172,201,234` | "manager" | Penerima: piutang lewat tempo, hutang, penyusutan, anggaran | belum ada |
| 32 | `services/alert_service.py:277,319` | "warehouse" | Penerima: tugas gudang, stok | `notif.low_stock_division` (sebagian) |
| 33 | `services/escalation_service.py:36-43` | sales/gudang → manager → admin | Rantai eskalasi | belum ada (jam & kedalaman bisa diatur) |
| 34 | `services/wa_alert_service.py:31` | ["admin","manager"] | Penerima siaran WhatsApp "semua" | belum ada |
| 35 | `services/scheduler_service.py:58` | Asia/Jakarta | Zona waktu jadwal | belum ada |
| 36 | `services/scheduler_service.py:80-292` | 38 job, jam bawaan 06.40–08.30 | Daftar & jam bawaan pengingat | jam bisa diatur; daftar tidak |
| 37 | `services/turn_notification_service.py:80` | 7 hari | Dokumen diam > 7 hari tidak diingatkan lagi | belum ada |
| 38 | `services/approval_reminder.py:40` | 3 | Jumlah dokumen yang disebut di pengingat | belum ada |
| 39 | `services/design_request_service.py:688` | 3 hari | Permintaan desain "segera jatuh tempo" | belum ada |
| 40 | `services/marketing_service.py:37` | 60 menit | Jendela pengingat tayang konten | belum ada |
| 41 | `services/marketing_ext.py:20` | 60 menit | Toleransi "tepat waktu" konten | belum ada |
| 42 | `services/marketing_cost_service.py:261` | 80% | Anggaran kampanye "mendekati batas" | belum ada |
| 43 | `services/printer_stuck_watch.py:13` | 30 menit | Label dianggap tertahan | belum ada |
| 44 | `services/inventory_drift_watch.py:40` | 10× | Kelipatan ambang → "kritis" | belum ada (`inventory.drift_alert_rupiah` untuk ambang dasar) |
| 45 | `services/notification_service.py:16` | 100 meter | Ambang stok menipis bila produk tanpa titik pesan ulang | belum ada |
| 46 | `services/stock_availability.py:22` | 100 | Ambang "stok rendah" di layar ketersediaan (salinan #45) | belum ada |
| 47 | `services/notification_service.py:216` | 24 jam | "Reservasi mendekati kedaluwarsa" | belum ada |
| 48 | `services/stock_analytics_service.py:39-40` | 30 hari; ±10% | Jendela & pita tren penjualan | belum ada (jendela 90 hari ada) |
| 49 | `services/roll_service.py:238` | 150 | Panjang maksimum roll hasil potong sintetis | belum ada |
| 50 | `services/supplier_dn_profile_service.py:14-15` | 3 surat jalan; 80% | Format surat jalan supplier dipakai otomatis setelah ≥ 3 terkonfirmasi & ≥ 80% bukti sama | belum ada |
| 51 | `services/sample_sale_service.py:38-39` | 1 yard; +2 yard | Isi katalog sampel per warna | belum ada |
| 52 | `services/qc_inspection_service.py:54-55` | 15 yard; 10 | Selang & jumlah minimum titik inspeksi 4-point | belum ada |
| 53 | `services/return_grade_impairment.py:15` | A 100 … BS 10 | Faktor harga per grade (penurunan nilai retur) | hanya lewat Asumsi Retur (jalur lama) |
| 54 | `services/return_policy_service.py:295-299` | 21 hari; 21 hari; 3 hari | Jendela retur pelanggan/supplier, pengingat | hanya lewat Asumsi Retur (jalur lama) |
| 55 | `services/config_service.py:25-26` | pengingat 3 hari, tanpa netting | Kebijakan bayar antar-PT | hanya lewat layar Antar-PT (jalur lama) |
| 56 | `services/contract_service.py:44-52` | toleransi 3%, klaim otomatis, peran klaim | Kebijakan makloon bawaan | `makloon.*` (ada) |
| 57 | `services/hr_leave_service.py:31` | 12 hari | Jatah cuti tahunan | belum ada di registry (**I**: ada di `hr_settings.leave` tanpa layar) |
| 58 | `services/hr_payroll_service.py:19` | 173 jam | Pembagi upah per jam (lembur) | `hr.overtime.hours_divisor` (ada, dipakai; ini cadangan) |
| 59 | `services/hr_payroll_service.py:23-60` | 3 tabel tarif | Tarif efektif rata-rata PPh 21 (TER A/B/C) | belum ada |
| 60 | `services/hr_payroll_service.py:69-70` | Rp54 jt … | PTKP per status | `hr.ptkp_table` (ada, ditandai tidak dipakai) |
| 61 | `services/hr_payroll_service.py:71-73` | 5/15/25/…%; 5%; Rp500.000 | Tarif pasal 17, biaya jabatan | belum ada |
| 62 | `schemas_hr_attendance.py:17, 28` | 10 menit; 150 m | Toleransi telat & radius lokasi bawaan | per shift/lokasi (bisa diubah per baris) |
| 63 | `services/tracking_service.py:19-20` | 30 dtk; 10 menit | Selang simpan posisi; dianggap daring | belum ada |
| 64 | `services/gl_service.py:3275` | Rp1 | Toleransi pembulatan | belum ada |
| 65 | `services/closing_service.py:37` | 5 huruf | Panjang minimum alasan lewati akun sementara | belum ada |
| 66 | `services/inspection_service.py:124`; `putaway_arrival_service.py:37`; `gate_review_actions.py:27-28` | 15; 10; 5/10 huruf | Panjang minimum alasan (berbeda-beda) | belum ada |
| 67 | `routers/auth.py:28-29` | 5 kali; 15 menit | Batas salah sandi & lama kunci | belum ada |
| 68 | `core_utils.py:12` | 24 jam | Umur sesi masuk | belum ada |
| 69 | `services/esign_service.py:20-21` | 10 menit; 5 kali | Umur kode & batas coba tanda tangan elektronik | belum ada |
| 70 | `core_utils.py:19` (bawaan `width=5`) + 90 titik panggil | 5 digit; 59 awalan | Format nomor dokumen | belum ada |
| 71 | `services/lot_service.py:136` | `LOT-YYMM-####` | Format nomor lot | `lot.number_format` (ada, tidak dibaca) |
| 72 | `services/inventory_service.py:149` | "Kain Nusantara" | Judul kop bila logo kosong (cetak lama) | profil PT |

Tambahan teknis (bukan kebijakan bisnis, tidak dihitung): batas baris ekspor (`export_engine.py:26-27`), jendela bacaan RFID (`rfid_ingest_service.py:90-92` — tunduk pada `docs/rfid/KEPUTUSAN_GATE_RFID.md`, STOP & ASK), faktor yard→meter.

---

## Lampiran B — Pengaturan yang punya dua tempat (22 pasangan)

| # | Hal | Tempat 1 | Tempat 2 (dan 3) | Yang menang / dipakai | Bukti |
|---|---|---|---|---|---|
| 1 | Status PKP & PPN | Master PT `default_tax_mode` | registry `tax.ppn_rate`, `tax.efaktur_enabled` per PT | Master PT (non-PKP memaksa tarif 0) **T** | `config_service.py:249-256` |
| 2 | Tahun buku | Master PT `fiscal_year_start` | registry `finance.fiscal_year_end_month` | Registry; master PT mati **T** | `closing_service.py:81` |
| 3 | Mata uang | Master PT `currency` | registry `finance.base_currency` | Registry **T** | `config_currency.py:31-33` |
| 4 | Penanggung insentif | Master PT `incentive_payer` | — (aturan komisi di `commission.*`) | Tidak ada yang membaca master PT **T** | pencarian `incentive_payer` |
| 5 | Skema penomoran | Master PT `numbering_scheme` | argumen `scheme=` di tiap titik panggil | Kode **T** | Lampiran D |
| 6 | Logo | Master PT `logo_url` | `document_branding.logo_b64`; `document_templates.logo_url` | Branding > master PT (mesin baru); template dasar (mesin lama) **T** | `pdf_service.py:221-225`; `inventory_service.py:146-150` |
| 7 | Nama, alamat, NPWP, email di kop | Master PT | `document_branding` | Branding bila terisi **T** | `pdf_service.py:226-236` |
| 8 | Template dokumen | "Kop & tata letak dasar" (`document_templates`, per PT) | "Desainer PDF" (`pdf_templates`, global) | Dua mesin cetak berbeda **T** | `DocTemplatesView.jsx:48-54` |
| 9 | Termin bawaan | registry `finance.default_payment_term_code` (grup + PT) | pilihan di SO; termin di profil supplier/makloon | SO → hanya nilai grup **T** | `sales_orders.py:353-356` |
| 10 | Master termin | `/api/payment-terms` (router lama) | `/api/entity-masters/payment-terms` | Koleksi sama, dua pintu API **T** | `routers/settings.py:111-167`; `entity_masters.py` |
| 11 | Jenjang persetujuan PO | Aturan Persetujuan (tingkat 1) | `approval.extra_levels` (tingkat 2+) di tab lain | Keduanya, berurutan **T** | `config_service.py:350-374` |
| 12 | Penyetuju ACC desain / sample | matriks di kode | `rnd.spec_approval_roles`, `rnd.sample_decision_roles` | Keduanya harus lolos **T** | KP-07 |
| 13 | Persetujuan PR | Aturan Persetujuan | matriks divisi (tahap `purchase_request`) | Keduanya harus lolos **T** | KP-07 |
| 14 | Ambang pesanan khusus | konstanta Rp10 jt | `approval.po_custom_direksi_min` | Keduanya (tingkat berbeda) **T** | KP-25 |
| 15 | Setuju-sendiri | `approval.matrix_sod` | `amendment.dual_control`; 12 titik di kode | Masing-masing untuk dokumennya **T** | Lampiran C |
| 16 | Akun biaya bank / titipan | registry `bank.charge_account_code`, `bank.holding_account_code` | Pemetaan Akun `kas_bank.beban_bank`, `kas_bank.titipan_dana` | **I** — tergantung kode masih bawaan atau tidak | KP-30 |
| 17 | WhatsApp | Penjadwal & Notifikasi (`system_settings.alerts.wa`) | Pusat Dokumen (`integration_settings`) | Terpisah per pemakaian **T** | KP-16 |
| 18 | AI hidup/mati & model | Integrasi (`anthropic.*`) | registry `ai.enabled`, `ai.model_main` | Terpisah per fitur **T** | KP-31 |
| 19 | Baca surat jalan otomatis | Integrasi (kunci OpenAI) | registry `receiving.ocr_*`; layar Penerimaan & OCR | Tiga layar untuk satu fitur **T** | `hubTabs.js:259-262`; `integrations_service.py:30` |
| 20 | Denda keterlambatan | `ar.denda_rate_pct_per_month`, `ar.grace_days` | `payment.penalty_*` | Tarif dari `ar.*`, cara dari `payment.*` **T** | `penalty_service.py:73-79` |
| 21 | Pengingat antar-PT | `interco_payment.reminder_days` (layar Antar-PT) | `antar_entitas.settlement_reminder_days` (registry) | Dua job berbeda **T** | `interco_service.py:1174, 1255`; `interco_reminder.py:94` |
| 22 | Ambang stok menipis | titik pesan ulang per produk | konstanta 100 (dua berkas) | Produk, lalu konstanta **T** | `notification_service.py:199`; `stock_availability.py:22` |

Catatan: pasangan yang disebut di tugas "tarif insentif di Pengaturan vs CRM" **sudah tidak ganda di menu** — hanya ada satu tab (`hubTabs.js:254`), walau berkas layarnya masih di `features/crm/` (T). "Termin di profil pelanggan": profil pelanggan tidak punya isian termin (`schemas.py` kelas pelanggan hanya `credit_limit`), meski teks bantu registry berkata "bila pelanggan belum punya term khusus" (`config_catalog_core.py:104`) (T/I).

---

## Lampiran C — Titik setuju-sendiri

### C.1 Bisa diatur (2 sakelar)

| Berkas:baris | Dokumen | Sakelar | Bawaan | Admin |
|---|---|---|---|---|
| `services/approval_matrix_service.py:196-207, 256-263` | ACC desain, ACC sample, PO custom, PR (lewat `guard`). Koreksi 13 Nov: klaim makloon **tidak** melewati `guard`; persetujuannya hanya diperiksa izin (`backend/routers/makloon_orders.py:263`) | `approval.matrix_sod` (grup/PT) — `config_catalog_approval_matrix.py:63-72` | **Melarang** | lolos (`:176-193, 243-247`) |
| `services/purchase_requisition_service.py:333-338` | PR (lapis layanan) | sama | Melarang | lolos |
| `routers/price_approvals.py:380-387, 475-480` | Persetujuan / penolakan harga khusus | sama | Melarang | lolos |
| `routers/so_approvals.py:297-305` | Entri harga khusus di SO | sama | Melarang | lolos |
| `services/amendment_service.py:255, 733-737` | Amandemen / koreksi dokumen | `amendment.dual_control` | menurut registry | lolos (`admin_override`) |

Catatan: `sod_blocked` tetap memblokir pada mode "peringatkan saja" (hanya mode "nonaktif" yang melepas) — `approval_matrix_service.py:203` (T).

### C.2 Melarang, ditulis mati (12 titik)

| Berkas:baris | Dokumen | Pembanding | Admin lolos? |
|---|---|---|---|
| `routers/purchase_orders.py:813-822` | Persetujuan PO | `created_by_id == actor.id` | ya |
| `routers/purchase_orders.py:839-844` | PO berjenjang: orang yang sama tidak boleh dua tingkat | `approved_by_id == actor.id` | ya |
| `routers/vendor_bills.py:459-462` | Tagihan supplier | `created_by_id` | ya |
| `routers/landed_cost.py:250-253` | Voucher biaya masuk | `created_by_id` | ya |
| `services/contra_bon_service.py:995-998` | Kontrabon | `created_by_id` | ya |
| `services/marketing_cost_service.py:224-226` | Tagihan kampanye | `created_by_id` | ya |
| `services/interco_return_service.py:435-437` | Retur antar-PT | pembuat | ya |
| `services/period_unlock_service.py:195-200` | Buka periode buku | `requested_by_id` | ya |
| `services/makloon_loss_service.py:242-243` | Susut bahan di mitra makloon | `recorded_by_id` | **tidak** |
| `services/return_exception_service.py:47-48` | Pengecualian retur | `requested_by_id` | **tidak** |
| `services/design_ownership_service.py:224-225` | Klaim kepemilikan desain | `by_id` | **tidak** |
| `services/initial_registration_service.py:210-212` | Registrasi stok awal: penyetuju nilai ≠ penyetuju hitungan | `count_approval.by_id` | **tidak** (langkah kedua bisa dimatikan lewat `registration.finance_approval`) |

### C.3 Tidak ada pemeriksaan (setuju-sendiri sudah boleh hari ini; ≥ 14 pintu)

| Berkas:baris | Dokumen | Penjaga yang ada |
|---|---|---|
| `routers/transfers.py:550-580` | Transfer gudang / antar-PT | izin `transfer.approve` |
| `routers/cycle_count.py:293-…` | Stock opname | izin `inventory.approve_count` |
| `services/return_service.py:772-790` | Retur penjualan | izin |
| `services/purchase_return_service.py:274-…` | Retur pembelian | izin |
| `routers/hr_leave.py:154-…`, `services/hr_leave_service.py:249-279` | Cuti (termasuk cuti sendiri) | izin `hr.manage_attendance` |
| `routers/hr_leave.py:253-…`, `services/hr_leave_service.py:361-…` | Lembur | izin `hr.manage_attendance` |
| `routers/hr_payroll.py:171-…`, `services/hr_payroll_service.py:474-486` | Pengesahan penggajian (pengaju = pengesah boleh) | izin `hr.manage_payroll` |
| `services/cash_advance_service.py:241-260, 482-…` | Uang muka & pertanggungjawabannya | peran per tahap |
| `services/penalty_service.py:399-411` | Pembebasan denda | peran penyetuju |
| `services/payment_variance_service.py:678-…, 1014-…` | Selisih pembayaran / hapus buku | peran penyetuju |
| `routers/crm.py:141-…` | Lewat-batas kredit | peran |
| `services/makloon_claim_service.py:138-…` | Klaim makloon (lapis layanan) | matriks di router |
| `services/internal_request_service.py:350-…` | Permintaan internal antar-PT | izin |
| `services/design_request_service.py:419-…` | Permintaan desain | izin |
| `routers/sales_orders_extra.py:447-461` | Persetujuan nilai SO | peringkat peran |

Cara cari: kata kunci tugas (`self_approve`, `requested_by`, `created_by ==`, `submitted_by`, "tidak boleh menyetujui", `maker`) ditambah `proposed_by`, `recorded_by`, `sod`, `dual_control`, "pemisahan tugas", "kontrol ganda", dan pemindaian 145 fungsi `approve|decide|verify|waive`. Tidak ditemukan pengenal bernama `self_approve` atau `maker` di `backend/services` / `backend/routers` (T).

---

## Lampiran D — Awalan nomor dokumen yang ditulis mati

Format per PT: `KODE/AWALAN00001` · format bersama: `AWALAN00001` · lebar 5 digit kecuali disebut.

### D.1 Per PT (44 awalan)

| Awalan | Dokumen | Berkas:baris |
|---|---|---|
| `SO-`, `SOS-` | Pesanan penjualan, pesanan sampel | `routers/sales_orders.py:305` |
| `PO-` | Pesanan pembelian | `routers/purchase_orders.py:583`; `services/blanket_po_service.py:130`; `pr_sourcing_service.py:626`; `rfq_service.py:220` |
| `SJ-` | Surat jalan | `services/shipment_service.py:28` |
| `FKT-` | Faktur pajak keluaran | `services/tax_invoice_service.py:29`; `interco_tax_service.py:189` |
| `AR-` | Kwitansi penerimaan | `services/ar_receipt_service.py:452` |
| `CASH-` | Transaksi kas (15 titik) | `routers/cash.py:29`; `services/cash_ledger.py:24`; dll. |
| `JE-` | Jurnal | `services/gl_service.py:607, 693` |
| `CN-`, `DN-` | Nota kredit / debit dari amandemen & batal item | `services/amendment_service.py:877-879`; `od_cancel_credit_note.py:44` |
| `AMD-` | Amandemen | `services/amendment_service.py:628, 687` |
| `CB-` | Kontrabon | `services/contra_bon_service.py:677` |
| `RPB-` | Rencana pembayaran | `services/payment_plan_service.py:311` |
| `SLB-` | Selisih pembayaran | `services/payment_variance_service.py:718, 1038` |
| `DN-DENDA-` | Nota denda | `services/penalty_service.py:188` |
| `CASE-` | Kasus keuangan | `services/finance_case_service.py:287` |
| `FA-` | Aset tetap | `services/fixed_asset_service.py:100` |
| `PD-`, `STL-` | Uang muka, pertanggungjawaban | `services/cash_advance_service.py:151, 408` |
| `MCC-` | Biaya kampanye | `services/marketing_cost_service.py:78` |
| `IC-`, `ICS-`, `ICL-`, `ICR-` | Antar-PT: transaksi, pelunasan, pinjaman, retur | `services/interco_service.py:239, 1050`; `interco_loan_service.py:107-108`; `interco_return_service.py:264-266` |
| `PIN-` | Permintaan internal | `services/internal_request_service.py:71` |
| `TRF-` | Transfer gudang | `routers/transfers.py:231, 366`; `services/cutting_service.py:128` |
| `GRN-` | Penerimaan barang | `services/goods_receipt_service.py:189` |
| `INS-` | Inspeksi | `services/inspection_service.py:607` |
| `REG-` | Registrasi stok awal | `services/initial_registration_service.py:79` |
| `LOT-YYMM-` (4 digit) | Lot | `services/lot_service.py:136` |
| `MKO-` | SPK makloon | `services/makloon_order_service.py:181` (cadangan bersama `:182`) |
| `SCT-` | Kontrak supplier | `services/contract_service.py:114` |
| `SCR-` | Pemakaian saldo toko | `services/store_credit_service.py:199` |
| `RPR-` | Perbaikan | `services/repair_order_service.py:145` |
| `LG-`, `VHL-` | Logistik, catatan kendaraan | `services/logistics_service.py:216`; `routers/vehicle_logs.py:162` |
| `CF-` | Masukan pelanggan | `services/customer_feedback_service.py:29` |
| `DSR-`, `SMP-`, `SPEC-` | Permintaan desain, sample, spesifikasi | `services/design_request_service.py:290`; `rnd_sample_service.py:500`; `rnd_spec_service.py:218` |
| `LV-`, `OT-`, `PAY-`, `SLIP-` | Cuti, lembur, penggajian, slip | `services/hr_leave_service.py:204, 349`; `hr_payroll_service.py:20, 378, 402` |

### D.2 Bersama seluruh grup, tanpa kode PT (18 awalan, termasuk cadangan `MKO-` di D.1; `CN-`/`DN-` muncul di kedua daftar → 59 awalan berbeda)

| Awalan | Dokumen | Berkas:baris |
|---|---|---|
| `SRET-` | Retur penjualan | `services/return_service.py:148` |
| `CN-` | Nota kredit retur (**format berbeda** dari D.1) | `services/return_service.py:154` |
| `RTN-` | Roll hasil retur | `services/return_service.py:1157` |
| `PRET-`, `DN-` | Retur pembelian, nota debit | `services/purchase_return_service.py:32, 45` |
| `VB-` | Tagihan supplier | `services/vendor_bill_service.py:224` |
| `FPM-` | Faktur pajak masukan | `services/input_tax_service.py:27` |
| `PR-` | Permintaan pembelian | `services/purchase_requisition_service.py:33` |
| `RFQ-` | Permintaan penawaran | `services/rfq_service.py:30` |
| `LCV-` | Voucher biaya masuk | `services/landed_cost_service.py:34` |
| `WO-` | Perintah kerja produksi | `services/production_service.py:214` |
| `SUP-`, `MAK-` | Kode supplier, kode mitra makloon (master bersama — wajar) | `routers/suppliers.py:29`; `routers/makloons.py:30` |
| `CC`, `BTG`, `PA`, `PJ` (tanpa tanda hubung) | Opname RFID, kedatangan, penyimpanan, cetak label | `services/cycle_count_service.py:126`; `putaway_arrival_service.py:154`; `putaway_draft_service.py:142`; `rfid_print_service.py:171` |

### D.3 Dibuat di luar `next_doc_number`

| Pola | Dokumen | Berkas:baris | Catatan |
|---|---|---|---|
| `INV-<nomor SO>-NN` | Faktur penjualan per SO | `routers/invoices.py:46-47` | lebar 2 |
| `VBM-00001` | Tagihan jasa makloon | `services/makloon_order_service.py:1407-1416` | baca terakhir + 1 |
| `EMP-00001` | Kode karyawan | `services/hr_service.py:50-61` | baca terakhir + 1 |
| `SORD-YYMMDD…` | Pesanan khusus | `services/special_order_service.py:62` | urut per hari |
| `KN-<nama>-NN`, `DSG-<slug>-` | Kode desain | `services/rnd_flow_service.py:171`; `design_gallery_service.py:50` | pola desain lain bisa diatur lewat `rnd.design_code_pattern` |
| `SHIFT-001` | Kode shift | `routers/hr_attendance.py:77` | — |

Pratinjau nomor di wizard PT (`EntityWizard.jsx:329-337`: SO, PO, FKT, AR) cocok dengan D.1 (T).

---

## Batas tinjauan ini

* Tidak ada yang dijalankan; semua "T" berarti terbaca di kode `HEAD`, bukan teramati di layar.
* Isi 310 kunci registry dan layar Peran & Hak Akses tidak ditinjau; kunci registry hanya disebut sebagai rujukan silang (290 nama kunci terbaca dari `config_catalog_*.py`).
* Rincian jurnal/buku besar mengikuti `docs/finance/AUDIT_KEUANGAN_2026-11-13.md`; logika gerbang RFID tidak ditinjau (STOP & ASK menurut `docs/rfid/KEPUTUSAN_GATE_RFID.md`).
* Butir yang butuh keputusan pemilik sebelum dikerjakan: KP-05/06 (bentuk tabel persetujuan tunggal), KP-12 (deret bersama vs per PT; format nomor), KP-02 (aturan ganti status PKP), §5.2 (susunan menu).
