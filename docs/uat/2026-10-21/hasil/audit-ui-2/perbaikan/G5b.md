# Laporan perbaikan G5b (separuh G5) — Audit UI tahap 2

Wilayah: `features/documents/**`, `features/pdf/**`, `features/export/**`, `features/settings/**`, `features/approvals/**`,
`features/tanya/**`, `features/admin/{AdminView,IntegrationsPanel,GeminiIntegrationPanel,OpenAiIntegrationPanel}.jsx`,
`features/admin/scheduler/**`, `features/mobile/{MobileOpsApp,MobileApprovalInbox}.jsx`,
`features/sales/mobile/{MobileMdApp,MobileMdViews}.jsx`, backend `pdf_resolvers.py`, `pdf_engine.py`,
`escalation_service.py`, `turn_notification_service.py`, `notification_service.py`, `export_registry*.py`, `export_engine.py`.

Butir G5 di luar wilayah (G5a): G5-04..07, G5-16, G5-28..49, G5-54, G5-55, G5-63, G5-65..68.
API G0 (`fixes/G0_api.md`) dipakai setelah tersedia: `isForbiddenError`, `apiErrorText` (403 → kalimat Indonesia).

## Status per butir (diperbarui bertahap)

| id | status | berkas:baris | cara cek |
|---|---|---|---|
| G5-08 [T] | diperbaiki | `features/mobile/MobileOpsApp.jsx` (MobileOpsApp: tab dari izin `price_approval.approve`/`order.approve`/`approval.view`; QueuePanel `isForbiddenError`/`apiErrorText`); `features/mobile/MobileApprovalInbox.jsx` (`usePendingApprovals`: hanya memuat daftar yang boleh diputus; 403 → "Anda tidak punya akses ke …", bukan "Tidak ada … menunggu") | Login desainer HP → tab Persetujuan tidak ada; manajer tetap melihat daftar. |
| G5-09 [T] | diperbaiki | `MobileOpsApp.jsx` (`decisionTarget`, NotifPanel) | Lencana "Putuskan di HP" hanya bila dokumennya ada di daftar Persetujuan (harga khusus via `action_id`, PO custom via `ref so_custom_appr:<id>` / nomor SORD); klik → tab Persetujuan + kartu disorot & digulir. Notifikasi lain bertautan → "Buka di tampilan desktop ›" (navigasi ke view + mode desktop); tanpa tautan → hanya ditandai dibaca. |
| G5-10 [T] | diperbaiki | backend `turn_notification_service.py` (`stage_text`, body "tahap: dikirim"); `pdf_engine.py` DOC_STATUS_LABEL (+partially_shipped, receiving, refund_settled, …); `escalation_service.py` ("oleh Dewi (Manajer)" / "oleh semua penerima", bukan "oleh all"); HP `MobileOpsApp.jsx` humanizeNotif (+STAGE_LABEL lengkap, fallback `docStatusLabel`, "oleh all." lama → "oleh semua penerima.") | Notifikasi baru & lama di HP tanpa "shipped/refund_settled/all". Meja Saya → lihat "Butuh grup lain". |
| G5-11 [T] | diperbaiki (format PPN sementara, K-03) | backend `pdf_resolvers.py` (`fmt_date` bulan Indonesia + WIB, `fmt_num` id-ID untuk 37 kolom qty/persen, `fmt_now` "Dicetak … WIB", `_ppn_rows`: baris "DPP nilai lain (11/12 × subtotal)" + "PPN 12% × DPP" di SO/PO/Faktur; Faktur Pajak "PPN 12%"); `pdf_engine.py` MASTER_TEMPLATE (teks "Atau buka <host>" disembunyikan bila localhost/127.x) | PDF SO-00505: "25 Okt 2026", Subtotal Rp 202.318 · DPP nilai lain Rp 185.459 · PPN 12% × DPP Rp 22.255 · Grand Total Rp 224.573; qty "1 meter"; tanpa "localhost". |
| G5-12 [T] | diperbaiki | `pdf_resolvers.py` `resolve_transfer` | TRF-00003: PT Asal "Sukacita Textile", PT Tujuan "Kanda Fabric", Gudang Asal/Tujuan baris sendiri, "Dibuat oleh Budi Santoso" (dari `requested_by`), "24 Okt 2026". (Gudang tujuan data uji = gudang Sukacita — lihat catatan data.) |
| G5-13 [T] | diperbaiki | `pdf_resolvers.py` `MKO_MODE_LABEL`, `_process_label`, `resolve_makloon_spk` | MKO-00036: "Jenis order: Proses saja (bahan dari stok)", Material "(5.337,91 yard)", kolom Proses "Printing", Jumlah "5.337,91 yard". |
| G5-15 [T] | diperbaiki | `settings/config/ConfigHealthPanel.jsx` (vonis, KPI & toolbar hanya bila data termuat); `settings/config/SettingsHub.jsx` (tab Kesehatan Konfigurasi hanya untuk `settings.view`); `settings/config/configApi.js` (`errMsg` → `apiErrorText`) | MD: tab tidak tampil; bila galat muat, tidak ada vonis hijau "Diperiksa 0 setting". |
| G5-02 [T] | diperbaiki | `settings/entities/RoleRealityPanel.jsx` (banner cakupan "dihitung dari X dari Y jenis kegiatan" di atas kartu; daftar kode di `<details>`; Lihat bukti: izin → label modul/aksi, id teknis contoh dokumen disembunyikan; `Fragment key` di rows.map; chip aktif biru seragam) | Cek Peran tanpa dinding kode; konsol tanpa peringatan key. |
| G5-57 [S] | diperbaiki (backend + HP); data lama tetap | `escalation_service.py` (`_source_key`, `plan_escalations`: satu eskalasi per dokumen sumber; salinan per orang digabung & ditandai; salinan untuk akun admin tidak dieskalasi ke admin); HP `MobileOpsApp.jsx` (kartu identik digabung "×2", nomor dokumen `whitespace-nowrap`, kepala "Belum dibaca · N" + "Tandai semua dibaca" + "Menampilkan 100 terbaru dari N") | Penyebab dobel TERBUKTI di data: `create_addressed` membuat salinan per orang (`ref …#user_id`, `recipient_role=""`) dan job eskalasi menaikkan tiap salinan → admin menerima 2–10 kartu per SORD. "Dua pelanggan per SORD" = 3 dokumen berbeda bernomor sama SORD-261023-0012 (bentrok penomoran data uji). |
| G5-56 [S] | diperbaiki | `MobileApprovalInbox.jsx` | Setujui: judul nomor + pelanggan, pesan barang + Rp, catatan opsional, tombol "Setujui"; Tolak: judul "Tolak <nomor> · <pelanggan>", alasan wajib, merah, tombol "Tolak"; kartu "target Rp 45.000/meter". |
| G5-58 [S] | sebagian (isi Ringkas → K-12) | `MobileOpsApp.jsx` | Bilah bawah ≤ 5 tab: tab Desktop dilebur ke Ringkas (tombol desktop juga di app bar), Antrean dilebur ke tab Persetujuan (seksi "Antrean lintas tahap"), Meja QC masuk Pintasan untuk admin/manajer/MD. Isi KPI per peran (desainer/admin sample) menunggu K-12. Label ≥ 11px = CSS bersama `styles/mobile.css` (bukan berkas G5b). |
| G5-01 [T] | diperbaiki | `features/admin/AdminView.jsx` (helper `auditResource/auditSummary/auditRole/auditTech` di atas komponen; baris & laci Jejak Audit) | Baris: label aksi (G0 `auditActionInfo`), waktu WIB, "Pelaku • Jenis data • Badan usaha", ringkasan "Email: …, Peran: Desainer" / "Alasan: …"; kunci aksi & id hanya di tooltip. Laci: Pelaku, Peran (login → peran akun, job → "Sistem"; bukan "system/demo"), Jenis data, Badan usaha (nama, bukan `ent_ksc`), Waktu; tombol "Tetap di Audit" dihapus (tutup = ×). Nomor dokumen tidak tersedia di `audit_logs` (hanya id) → jenis data saja. |
| G5-03 [T] | diperbaiki | `settings/masters/masterFieldsConfig.js` (peta label jenis dokumen/peran/proses/jenis kain/tahap/hasil ukur; `format` untuk batas persen diskon; `cellText` mendukung `format` & label per item list); `settings/masters/EntityMastersView.jsx` (`HINT_OVERRIDE`, `cleanHint`) | Aturan Persetujuan: "Diskon (%) · 0% – 10% · Manajer"; Tahapan Proses "Pre-treatment (PFD/PFP)"; Template "Faktur (Invoice)"; Lini "Benang · Tenun · Celup · Inspeksi"; banner tanpa backtick/kode. Kolom "Kode" tetap menampilkan kode (memang kolom kode). |
| G5-14 [T] | diperbaiki (kontradiksi Tahap → data lama) | backend `export_registry.py` (`C(enum=…)`, `AUTO_ENUM` status/payment_status/order_type; kolom `stage` → "Tahap (data lama)" enum stage_legacy); `export_engine.py` (`enum_label` di `_norm` → pratinjau, CSV, XLSX, ringkasan grup; filter menerima label → semua kode berlabel itu); `pdf_engine.py` DOC_STATUS_LABEL (+active/inactive/ready/…); frontend `export/PreviewTable.jsx` (datetime/date WIB Indonesia) | Penyebab "waiting_stock bertahap Reserved" TERBUKTI: field `stage` SO adalah penanda lama berhuruf Inggris yang tidak ikut diperbarui saat `status` berubah (SO-00295 status waiting_stock, stage "Reserved"). Tidak diubah rumusnya; kolom dilabeli "(data lama)" — pemilik memutuskan kolom ini dihapus/dihitung ulang. |
| G5-17 [S] | diperbaiki | `AdminView.jsx` (`masterDetail`, `statusLabel` "Aktif/Nonaktif", meta satuan + status, tombol "Aktifkan" juga untuk satuan nonaktif) | Laci pelanggan: PIC/HP/Kota/Sales/Batas kredit/Status; template: tipe/kertas/kolom; satuan: dimensi/alias; kalimat menyebut tombol yang benar-benar ada. |
| G5-18 [S] | diperbaiki | `AdminView.jsx` (state & `emptyCustomer` tanpa "Jakarta"; isian berlabel + "(opsional)"; placeholder "mis. …"; Sales penanggung jawab = pemilih akun sales bila daftar tersedia (→ `assigned_sales_id`); batas kredit kosong = tanpa batas; tombol simpan nonaktif sampai nama, PIC, HP, alamat ≥ 3 huruf [+ sales] terisi — sesuai POST /customers) | Form baru tanpa Jakarta; tidak ada "Rp 0" ganda. Keberadaan form tetap menunggu D-05. |
| G5-19 [S] | diperbaiki | `AdminView.jsx` (`editingTemplateId`, `loadTemplateForEdit`, tombol "Ubah" per template → PATCH; deskripsi pop-up per jenis; label "Kolom tabel (pisahkan dengan koma)" + contoh; ▲/▼ nonaktif di ujung; daftar urutan `max-h-60` bergulir; Orientasi berpasangan dengan Kertas) | Template bisa diubah; daftar urutan tidak terpotong kaki pop-up. Pemilih kolom berbentuk chip tidak dibuat (contoh saja). |
| G5-26 [S] | diperbaiki | `EntityMastersView.jsx` (kolom Aksi `sticky right-0`; banner tunggal per jenis via `HINT_OVERRIDE` — Tarif Insentif tidak lagi menyebut "CRM › Tarif Insentif" yang bertentangan; "Simpan baris" nonaktif sampai isian * terisi; "Jadikan Global" → peringatan + `askConfirm` danger; "Buat khusus …" → `askConfirm`) | Aksi baris selalu terlihat; satu banner; Global & salinan meminta konfirmasi. Teks hint server (`entity_master_service.py`, bukan berkas G5b) masih berbacktick — tertimpa di layar. |
| G5-27 [S] | diperbaiki | `settings/masters/GradeMasterView.jsx` (Batal saat ubah; alasan lewat `askReason` minimal 5 huruf saat Nonaktifkan/Aktifkan; isian alasan permanen dihapus; lebar kolom aksi tetap; isian urutan lebih lebar) | Ubah bisa dibatalkan; tabel tanpa isian alasan per baris. |
| G5-52 [S] | diperbaiki | backend `export_registry_more.py` (izin dataset `doc_amendments` → `finance_amendment.propose`, `store_credit_ledger` → `ar_receipt.view`); frontend `export/ExportCenterView.jsx` (`isTechCol`: kolom `id`/`*_id`/"ID …" tidak terpilih bawaan); `PreviewTable.jsx` ("Cakupan: semua badan usaha / badan usaha aktif · termasuk pesanan sampel & batal") | Penyebab TERBUKTI: kedua dataset meminta izin yang tidak ada di matriks (`finance_amendment` tak punya aksi `view`; modul `store_credit` tidak ada) → "tidak tersedia" untuk SEMUA peran. Uji `test_export_dataset_permissions_exist_in_matrix` menjaga semua dataset. 405 vs 150 = beda cakupan (ekspor memuat SO sampel/batal & semua badan usaha di mode Semua) → kini dilabeli. |
| G5-64 [R] | diperbaiki | `AdminView.jsx` (tombol Filter Jejak Audit di kepala kartu); `GeminiIntegrationPanel.jsx` (aksen centang biru seperti panel lain) | Tombol simpan ketiga panel sudah satu kelas (`btn-primary`); label "Simpan Kunci" (OpenAI) dipertahankan karena memang hanya menyimpan kunci. |
| G5-20 [S] | diperbaiki | `settings/ApprovalRuleForm.jsx` (Peran Penyetuju tanpa * — server menerima kosong = lolos otomatis); `settings/ApprovalRulesSettings.jsx` (badge Aktif = label saja; satu tombol ⏻: aktif → dialog Nonaktifkan, nonaktif → `askConfirm` Aktifkan; "mesin persetujuan", "Gagal mengubah status"); `settings/approvalRulesConstants.js` ("Manajer") | Satu cara menonaktifkan/mengaktifkan, selalu dengan konfirmasi. |
| G5-21 [S] | diperbaiki (awalan PR- → K-09) | `approvals/ApprovalInbox.jsx` (ringkasan "N di daftar bawah" = baris yang dirender; kosong + kategori 403 → "Tidak ada yang menunggu di kategori yang bisa Anda lihat · Sebagian kategori tidak bisa ditampilkan…"; saringan aktif → pesan saringan; label antrean "Payroll" → "Penggajian" & periode `formatPeriod` di judul) | Sales tidak melihat "Semua keputusan sudah ditindaklanjuti" bila ada 403. Teks server `approval_backlog_service.py:150` tetap "Payroll …" (dipetakan di layar). |
| G5-22 [S] | diperbaiki | `approvals/MyApprovalsView.jsx` (`ChainPills` satu bentuk pil oranye "○ 1/1. Manajer"; `levelText` Manager→Manajer; `personText`: email → nama dari `/users` bila berizin `user.view` / akun sendiri, cadangan bagian depan email dirapikan; email di tooltip) | Kolom tingkat seragam; pengaju tidak berupa email. |
| G5-23 [S] | diperbaiki (menu ⋯ tidak dibuat) | `settings/entities/AccountList.jsx` (nama peran dari `roleLabel` pendek di tabel/CSV/saringan + label panjang di tooltip; aksi baris: "Ubah" + tombol ikon bertooltip Setel ulang sandi / Cabut sesi / Nonaktifkan dalam satu baris; Cabut sesi & Nonaktifkan kini `askConfirm`; chip aktif biru); `EntityList.jsx` & `RoleRealityPanel.jsx` (chip aktif biru) | Baris akun setinggi baris normal; nama peran sama di semua tab; satu warna chip. |
| G5-24 [S] | diperbaiki | `settings/entities/AccountFormDrawer.jsx` (galat setelah mencoba simpan; * pada Nama/Email/Sandi awal/Badan usaha utama; "Sandi awal/baru", "Email untuk masuk", "Badan usaha utama"; sandi awal WAJIB — dulu kosong diam-diam jadi `demo12345`; karyawan tertaut tampil tersorot saat Ubah) | Form baru bersih saat dibuka. |
| G5-25 [S] | sebagian | `settings/entities/EntityDetailDrawer.jsx` (Simpan di kaki pop-up + Tutup; isian perorangan hanya untuk jenis Perorangan/UD; awal tahun fiskal = pemilih tanggal + bulan; "Format nomor dokumen: KSC/SO-nnnnn" menggantikan contoh palsu "-00001"; riwayat audit berlabel) | KOTA tetap teks bebas: PATCH entitas (`entity_lifecycle_service.EDITABLE_FIELDS`, bukan berkas G5b) tidak menerima kode wilayah, jadi LocationFields belum bisa dipakai di form ubah → "Butuh grup lain". |
| G5-50 [S] | diperbaiki (definisi nilai → K-03) | `documents/DocumentCenter.jsx` (kolom "Nilai sebelum PPN" + tooltip; tanggal `formatDate`; TTD & WA disembunyikan untuk status batal/void/ditolak/kedaluwarsa); `ESignModal.jsx`, `WhatsAppModal.jsx`, `WhatsAppSettings.jsx` (kaki Batal + aksi) | Nilai = `total_amount` (subtotal sebelum PPN) dari `routers/pdf.py::_summarize_doc`; label "DPP" sengaja TIDAK dipakai karena DPP nilai lain = 11/12 subtotal (Rp 185.459 ≠ 202.318). |
| G5-51 [S] | diperbaiki | `documents/ProcessTimeline.jsx` (status `docStatusLabel` tanpa huruf besar; lencana "Dokumen ini"; id teknis `xxx_hex` tidak dirender; sumber jurnal "sales_order / sales_cogs" → "Pesanan penjualan / HPP penjualan"); `documents/trace/DocRefsPanel.jsx` (status berlabel; tanpa nomor → "(tanpa nomor)", id di tooltip) | Panel alur & referensi tanpa kode mentah. |
| G5-53 [S] | sebagian | `pdf/PdfTemplateDesigner.jsx` (teks cakupan "Simpan Template" vs "Simpan Branding" + tooltip); `pdf/PdfEditorTabs.jsx` (kepala kolom Field Tambahan & Slot TTD + aria-label + contoh "mis. …"; "Sembunyikan baris info dokumen" + penjelasan; "base64" dihapus; catatan pratinjau kop setelah disimpan) | Pratinjau memakai DRAF branding belum dibuat (butuh endpoint pratinjau berbranding draf). |
| G5-59 [S] | diperbaiki | `sales/mobile/MobileMdViews.jsx` (`Field`/`FormHead`: label di atas isian + * / "(opsional)"; KNDatePicker menggantikan `<input type=date>`; Jumlah (satuan) & Est. harga (Rp/satuan); satu tautan kembali + judul form + tombol Batal; Batalkan → `confirmLabel:"Batalkan permintaan"`, Minta revisi berkata kerja; "ACC desain" → `askConfirm`) | Form HP MD berlabel; ACC meminta konfirmasi. |
| G5-60 [S] | sebagian (nomor PO = data G4-12) | `MobileMdViews.jsx` (judul PR `line-clamp-2 break-words`; "PO <nomor>" atau "nomor PO belum tercatat" untuk PR berstatus Jadi PO; Pantau PO tanpa "kirim -" kosong; chip status dibungkus ke baris berikut — tidak lagi bergulir tanpa penanda) | Data: PR converted (mis. PR-00005) memang `po_number` kosong. |
| G5-61 [S] | diperbaiki | `settings/config/SettingCard.jsx` (kunci teknis pindah ke "Contoh & detail teknis" + tooltip; label/teks bantu/dampak/contoh lewat `cleanCfgText` = buang backtick + `stripInternalCodes`; setting "(Lama) … TIDAK DIPAKAI LAGI" → lencana abu "Tidak dipakai" & hanya-baca; jadwal `formatDate`); `ConfigDrawers.jsx` (cakupan lapisan & Riwayat: nama badan usaha, bukan `ent_ks…`); `configApi.js` (`cleanCfgText`, `isDeprecatedSetting`, `scopeText`); `SettingsHub.jsx` (deep-link `openConfig({ group })` tanpa key → daftar kelompok disaring ke kelompok itu + "Tampilkan semua kelompok") | Permintaan G5a terpenuhi: tombol Kebijakan R&D membuka kelompok R&D saja. Hak MD membaca kelompok lain tetap urusan server (K-11). |
| G5-62 [S] | diperbaiki | `tanya/tanya.css` (≤ 640 px: tab Tanya/Laporan/Peringatan/Riwayat/Jadwal/Biaya = 2 baris × 3, tanpa gulir tersembunyi; area pesan `padding-bottom: 72px` agar saran ke-3 tidak tertutup kotak input) | Cek di 390 px. |
| G5-69 [R] | diperbaiki | `sales/mobile/MobileMdApp.jsx` (FULL: "Labdip", "Desain & Pattern", "Satuan", "SPK Inspeksi") | Menu = judul layar. |
| G5-70 [R] | diperbaiki | `documents/trace/DocTraceView.jsx` (kartu "Susun Ulang Relasi" dilipat dalam `<details>` "Alat admin"; "Pesanan Penjualan, Pesanan Pembelian (PO)"); `trace/TraceSearch.jsx` (tanpa huruf besar penekanan) | Layar harian tanpa kartu alat admin terbuka. |
| Permintaan G2 (G2-02) | diperbaiki | `approvals/ApprovalInbox.jsx`, `approvals/ApprovalDecisionModal.jsx`, `mobile/MobileApprovalInbox.jsx` memakai `discountInfo()` (`features/sales/priceApprovals/priceApprovalText.js`) — tidak lagi "(--3064%)" | Harga di atas normal → "+3.064% di atas harga normal" (label "Selisih"). |
| Permintaan G2 | diperbaiki | `EntityMastersView.jsx` FULL_EDITOR "Pengaturan › Tarif Insentif Sales" | Selaras istilah "Tarif". |
| Permintaan G4 (G4-15) | diperbaiki | `documents/DocumentActionsBar.jsx` — prop baru **`hideWhatsapp`**, **`hideEsign`** (boolean) dan **`status`** (status dokumen; `cancelled/canceled/void/voided/rejected/expired` otomatis menyembunyikan Kirim WA & Tanda Tangan) | G4 cukup mengirim `status={order.status}` atau `hideWhatsapp`. |
| Catatan G0 (LocationFields `showErrors`) | diperbaiki / tidak perlu | `settings/config/LocationBacklogPanel.jsx` (`showErrors={tried}` setelah Simpan gagal validasi). `EntityWizard.jsx` memakai `required={false}` (lokasi opsional) → `showErrors` tidak berefek, tidak diubah. | |

## Tidak dikerjakan / di luar wilayah G5b
G5-04, G5-05, G5-06, G5-07, G5-16, G5-28 … G5-49, G5-54, G5-55, G5-63, G5-65 … G5-68 = wilayah G5a (rnd/design/designer/hr/marketing).

## Berkas yang diubah (G5b)
Backend: `backend/services/escalation_service.py`, `turn_notification_service.py`, `pdf_engine.py`, `pdf_resolvers.py`,
`export_engine.py`, `export_registry.py`, `export_registry_more.py`; uji baru `backend/tests/test_uat24_audit_ui_g5b.py`.

Frontend: `features/mobile/MobileOpsApp.jsx`, `MobileApprovalInbox.jsx`; `features/admin/AdminView.jsx`,
`GeminiIntegrationPanel.jsx`; `features/approvals/ApprovalInbox.jsx`, `ApprovalDecisionModal.jsx`, `MyApprovalsView.jsx`;
`features/documents/DocumentActionsBar.jsx`, `DocumentCenter.jsx`, `ESignModal.jsx`, `ProcessTimeline.jsx`,
`WhatsAppModal.jsx`, `WhatsAppSettings.jsx`, `trace/DocRefsPanel.jsx`, `trace/DocTraceView.jsx`, `trace/TraceSearch.jsx`;
`features/export/ExportCenterView.jsx`, `PreviewTable.jsx`; `features/pdf/PdfEditorTabs.jsx`, `PdfTemplateDesigner.jsx`;
`features/sales/mobile/MobileMdApp.jsx`, `MobileMdViews.jsx`; `features/settings/ApprovalRuleForm.jsx`,
`ApprovalRulesSettings.jsx`, `approvalRulesConstants.js`, `config/ConfigDrawers.jsx`, `config/ConfigHealthPanel.jsx`,
`config/LocationBacklogPanel.jsx`, `config/SettingCard.jsx`, `config/SettingsHub.jsx`, `config/configApi.js`,
`entities/AccountFormDrawer.jsx`, `entities/AccountList.jsx`, `entities/EntityDetailDrawer.jsx`, `entities/EntityList.jsx`,
`entities/RoleRealityPanel.jsx`, `masters/EntityMastersView.jsx`, `masters/GradeMasterView.jsx`,
`masters/masterFieldsConfig.js`; `features/tanya/tanya.css`; uji baru `features/__tests__/auditUi2G5b.test.js`.

Semua berkas LF, tanpa karakter kontrol (diperiksa).

## Uji yang dijalankan
- ESLint semua berkas frontend G5b (folder settings/export/approvals/documents/pdf/tanya + berkas mobile/admin/MobileMd +
  uji baru): **0 error**, 21 peringatan — semuanya "Unused eslint-disable directive" yang sudah ada sebelumnya.
- Jest (`--maxWorkers=1`): `src/features/__tests__/auditUi2G5b.test.js` — **6/6 lulus** (tab HP dari izin, lencana
  "Putuskan di HP", "tahap: dikirim", Kesehatan Konfigurasi tanpa vonis saat 403, label kolom master, pembersih teks
  pengaturan, DocumentActionsBar dokumen batal / `hideWhatsapp`). Tidak ada uji Jest lama yang mengimpor berkas G5b
  (pemakai `DocumentActionsBar` di uji lain semuanya me-mock komponen itu).
- pyflakes: `pdf_resolvers.py`, `pdf_engine.py`, `escalation_service.py`, `turn_notification_service.py`,
  `export_engine.py`, `export_registry.py`, uji baru — bersih. `export_registry_more.py`: 2 peringatan impor tak terpakai
  (J, SUPPLIER_JOIN) yang SUDAH ADA sebelumnya (baris 4 tidak diubah).
- pytest servis (tanpa HTTP, DB_NAME=kn_test_trial): `tests/test_uat24_audit_ui_g5b.py` — **9/9 lulus**
  (eskalasi satu kartu per dokumen, "oleh <label>", stage_text, fmt_date/fmt_num, DPP nilai lain, surat jalan antar-PT,
  SPK makloon, label status ekspor + filter label→kode, izin dataset ekspor ada di matriks);
  `tests/test_aud_exp_02.py` (snapshot ekspor) — **8/8 lulus**.

## Uji backend yang perlu dijalankan koordinator (HTTP, setelah restart server)
- `tests/test_uat24_audit_ui_g5b.py` (ulang, setelah restart — murni, sudah hijau)
- `tests/test_l11_export_center.py`, `tests/test_l11_finance_staff_templates.py`, `tests/test_aud_exp_01.py` (ekspor: label enum, izin dataset)
- `tests/test_uat24_lanjutan.py::test_pdf_status_labels`, `::test_pdf_preview_has_no_raw_status_code` (pdf_engine/pdf_resolvers)
- `tests/test_trial_22okt_fixes.py::test_e10_cetak_so_harga_khusus_belum_final_bercap`, `tests/test_uat24_f3.py::test_p3_1_surat_perintah_kerja_labdip_memuat_warna_pantone` (resolver PDF)
- `tests/test_notifications_iter33.py` (notifikasi giliran — teks "tahap:")

## Butuh grup lain
- **G2** — `features/desks/RoleDesk.jsx` (Meja Saya): notifikasi giliran LAMA di DB masih "tahap: cancelled/rejected".
  Notifikasi baru sudah berlabel dari server; RoleDesk perlu memetakan `tahap: <kode>` seperti `humanizeNotif` di
  `MobileOpsApp.jsx` (docStatusLabel huruf kecil) agar data lama juga bersih (G5-10).
- **G0** — `styles/mobile.css` `.m-tab { font-size: 10px }` → ≥ 11 px (G5-58; kini bilah ≤ 5 tab sehingga muat).
- **Pemilik backend lain (bukan berkas G5b)**:
  - `services/approval_backlog_service.py:150` — label antrean "Payroll menunggu pengesahan" → "Penggajian menunggu
    pengesahan" (layar sudah memetakan sementara).
  - `services/entity_master_service.py` — teks hint berbacktick (`process_type`, `needs_inspection`, …) & "Dikelola di
    layar CRM › Tarif Insentif" yang bertentangan dengan letak editor (layar menimpa sementara lewat `HINT_OVERRIDE`).
  - `services/entity_lifecycle_service.py` `EDITABLE_FIELDS` — tambah country/country_code/province(_code)/city_code/
    district(_code)/postal_code agar Detail Badan Usaha bisa memakai LocationFields seperti wizard (G5-25 sisa).
  - `services/approval_matrix_service.py` — `requester` berisi email; kirim juga `requester_name` (G5-22: layar
    memetakan via `/users` hanya bila peran punya `user.view`).
  - `services/role_reality_service.py` — contoh dokumen memakai `resource_id` bila nomor tak ada; kirim nomor (G5-02
    menyembunyikan id di layar).
  - `services/pdf_service.py` — host QR/Jejak Dokumen diambil dari request (`localhost:3063` di uji); pakai URL publik
    dari pengaturan (G5-11 hanya menyembunyikan teks host localhost/127.x di PDF).
  - `dependencies.audit()` / `audit_logs` — simpan nomor dokumen (`number`) supaya Jejak Audit bisa menyebut nomor,
    bukan hanya jenis data (G5-01).
  - G4 (data G4-12) — PR berstatus "Jadi PO" tanpa `po_number` (G5-60).

## Catatan risiko & keputusan pemilik
- **Ekspor (G5-14)**: kolom status/status bayar/jenis pesanan di CSV/XLSX kini berisi LABEL Indonesia, bukan kode.
  Bila ada integrasi/rumus pelanggan yang membaca kode mentah dari berkas ekspor, itu berubah. Filter tetap menerima
  kode maupun label (label ambigu seperti "Dikirim" → semua kode berlabel itu: shipped + dispatched).
  Kolom `stage` SO = data lama yang tidak sinkron dengan status → dilabeli "Tahap (data lama)"; hapus/hitung ulang = pemilik.
- **Eskalasi (G5-57)**: ref baru `escal:<tipe:ref dasar>:<kedalaman>:<peran tujuan>` + `escalated_from_key`; salinan per
  orang digabung; salinan milik akun admin tidak lagi dieskalasi ke admin; salinan per orang berperan di luar rantai
  tetap naik ke admin (perilaku lama dipertahankan). Kartu eskalasi ganda LAMA di DB tetap ada (HP menggabung kartu
  identik "×N"). "Dua pelanggan per SORD" = data uji: tiga dokumen berbeda bernomor sama SORD-261023-0012.
- **PDF (G5-11)**: total SO/PO/Faktur kini "Subtotal · DPP nilai lain (11/12 × subtotal) · PPN 12% × DPP · Grand
  Total". Bentuk akhir penulisan menunggu **K-03**. Semua tanggal PDF WIB berbahasa Indonesia; "Dicetak … WIB".
- **Pusat Dokumen (G5-50)**: kolom nilai diberi label "Nilai sebelum PPN" (bukan diubah ke grand total) — **K-03**.
- **HP Ops (G5-08/09/58)**: tab Antrean dilebur ke Persetujuan, tab Desktop dihapus (tombol desktop di app bar &
  Ringkas), Meja QC masuk Pintasan untuk admin/manajer/MD. Mengetuk notifikasi bertautan yang tak bisa diputus di HP
  membuka view terkait dalam **mode desktop** (menyetel `kn_force_desktop`, sama dengan tombol desktop). Isi Ringkas per
  peran → **K-12**.
- **Akun (G5-24)**: membuat akun kini WAJIB mengisi sandi awal (dulu kosong diam-diam = `demo12345`).
- **Aturan Persetujuan (G5-20)**: badge Aktif tidak bisa diklik lagi; skrip E2E yang mengklik `toggle-rule-<id>`
  harus memakai tombol ⏻ (`delete-rule-<id>`) + dialog.
- **Setting usang (G5-61)**: dikenali dari label "(Lama)" / "tidak dipakai lagi" → kartu hanya-baca berlencana abu.
- **Form pelanggan admin (G5-18)**: tombol simpan menuntut PIC, HP, alamat (+ sales bila daftar sales termuat) sesuai
  aturan server; keberadaan form menunggu **D-05**.
- Data uji: TRF-00003 (Sukacita → Kanda) memakai gudang tujuan `wh_jakarta` (gudang Sukacita) — PDF kini menyebut
  PT dengan benar, baris "Gudang Tujuan" mencerminkan data itu.
