# Laporan perbaikan G5a (rnd / design / designer / hr / marketing + backend rnd/desain/hr)

Status: **SELESAI** (25 Okt 2026). Tanpa git, tanpa restart kontainer.

Wilayah: `frontend/src/features/{rnd,design,designer,hr,marketing}/**`, `backend/services/{rnd_sample_service,design_request_service,hr_payroll_service}.py`.
API G0 yang dipakai (sesudah `G0_api.md` ada): `formatPeriod`, `formatPct`, `formatDecimal`; selain itu API lama
(`askConfirm/askReason`, `stripInternalCodes`, `formatDate`, `FormModal`, `KNDatePicker`, `MoneyInput`, `canWriteInScope`,
`GroupEntityBadge`, `useDomainEnums`, `useEscapeClose`, `roleLabel`).

Ringkasan: **35 butir G5a** → 31 diperbaiki, 3 sebagian (G5-40, G5-45, G5-61), 1 tidak dikerjakan (G5-21 bagian G5a = K-09).

## Tabel butir

| Id | Status | Berkas:baris | Cara cek |
|---|---|---|---|
| G5-04 [T] | diperbaiki | `hr/AttendanceView.jsx` konstanta `CSV_PLACEHOLDER` (±baris 29) + textarea impor | SDM › Presensi › Impor Sidik Jari: placeholder tampil 3 baris tanpa "\n". |
| G5-05 [T] | diperbaiki | `design/DesignRequestsView.jsx` BoardCard (thumbnail referensi → `DesignImage compact`); `design/ReferenceGallery.jsx` (kotak referensi rincian → `DesignImage` dengan teks fallback, pengganti `AttachmentThumb`) | Papan DSR: thumbnail dimuat via axios ber-header; 404 → ikon ImageOff + tooltip "Gambar tidak dapat dimuat" (bukan ikon peramban). Pop-up rincian: kotak berisi ikon + teks fallback. |
| G5-06 [T] | diperbaiki | `design/LinkedDesignsPanel.jsx` DesignMiniCard sampul → `DesignImage compact` | Detail DSR › desain tertaut: sampul 404 = ikon rapi, alt "Kawung Navy" tidak tumpah. |
| G5-07 [T] | diperbaiki | `rnd/design/DesignDetailPage.jsx` kepala (flex-col → `sm:flex-row`; baris atas HP: Daftar + ⟳/Ubah; kode `whitespace-nowrap`; aksi siklus di bawah info) + bilah tab `overflow-x-auto` + bayangan tepi kanan | HP 390 (MD › Galeri & Studio Desain › DSN-GEN-001): kode utuh, tidak tertutup tombol; tab satu baris bergulir. |
| G5-16 [T] | diperbaiki | `rnd/rndMeta.js` `cleanRndNote()` (stripInternalCodes + kode R&D + "(keputusan pemilik, …)"); dipakai `rnd/SampleTypeTabs.jsx` (catatan tab) & `rnd/SampleTypeGalleryView.jsx` (stripCodes lokal dihapus) | Tab Proofing/galeri: "…tidak ada kolom ukur. Pemilik boleh…" tanpa "MD-05"/"keputusan pemilik". |
| G5-21 [S] | tidak dikerjakan (bagian G5a) → K-09 | backend `hr_payroll_service.py:375` = awalan nomor `PR-` payroll; hanya diganti setelah keputusan K-09 | Bagian ApprovalInbox (hitungan, pesan sales, label "Penggajian" + formatPeriod) → G5b. |
| G5-28 [S] | diperbaiki | `hr/AttendanceSetupView.jsx` (laci Shift/Geofence/Perangkat: kaki Batal kiri–utama kanan ukuran normal; "Ubah …"; `Field required/optional`; placeholder "mis. …"; simpan nonaktif sampai wajib terisi + galat di dalam laci; "Salin token perangkat"; endpoint `/api/hr/attendance/ingest` & "device_token" dihapus dari teks bantu; "Nomor seri / kode"); `hr/EmployeeFormDrawer.jsx` (kaki standar, "Ubah Karyawan", placeholder "mis. …", status "Keluar", simpan nonaktif bila nama kosong); `hr/Employee360Panel.jsx` & `hr/EmployeesView.jsx` (status "Keluar", "Tandai Keluar") | Form SDM berpola kaki standar; tidak ada "Resigned/device_token". |
| G5-29 [S] | diperbaiki | `hr/leaveUtils.js` `activeEmployees/employeeOptions` (aktif saja, urut nama); `hr/LeaveView.jsx` (pemilih aktif + searchable; ✓ Setujui → `askConfirm` berisi tipe/periode/hari; dialog Batalkan "Kembali" vs "Batalkan cuti", danger, alasan wajib; periode `formatDate`; filter & kalender bulan `formatPeriod`; pesan kosong per status + "Tampilkan semua status"; angka 0 di Saldo abu-abu); `hr/OvertimeView.jsx` (pemilih aktif, askConfirm Setujui, periode Indonesia, pesan kosong per status) | Ajukan untuk Karyawan: karyawan Keluar tidak ada; ✓ memunculkan konfirmasi; tab Ditolak kosong → "Tidak ada pengajuan cuti berstatus ditolak". |
| G5-30 [S] | diperbaiki | `hr/MyLeaveCard.jsx` (pop-up Ajukan Cuti/Lembur → `FormModal` dengan ×, deskripsi, kaki, * / "(opsional)"; riwayat `formatDate`); `hr/EmployeeSelfService.jsx` (kartu "KPI Saya (R&D)" hanya untuk designer/md/sample_admin/md_quality atau izin `design_request.deliver`) | Profil Saya (Direktur): tanpa kartu KPI desainer; Ajukan memakai pop-up standar. |
| G5-31 [S] | diperbaiki | `hr/AttendanceView.jsx`: Input manual → `FormModal` berlabel (Karyawan*/Tanggal*/Status*/Jam opsional, Batal, simpan nonaktif bila wajib kosong, karyawan aktif saja); galat input manual & impor di dekat form (bukan banner global "Coba lagi"); Impor nonaktif bila kosong; input berkas → tombol "Pilih berkas CSV"; istilah "Input manual", "Perlu ditinjau", "Alpa", "Impor", "Sidik jari", "pindai" | Presensi: Input manual → pop-up berlabel; Impor tanpa data nonaktif; tidak ada banner global untuk validasi impor. |
| G5-32 [S] | diperbaiki | `hr/OrgUnitsView.jsx` (`delBlocker` dari pohon: jabatan aktif & karyawan non-keluar → dialog "Belum bisa dinonaktifkan · … masih punya 2 jabatan aktif & 3 karyawan aktif" tanpa tombol merah) | ⏻ Gudang & Operasional: dialog menyebut hambatan, tidak bisa dicoba. |
| G5-33 [S] | diperbaiki | `hr/PayrollRunsView.jsx` (`ACT_CONFIRM` + askConfirm untuk Sahkan / Posting GL / Bayar: periode, jumlah karyawan, gaji bersih, akibat jurnal; tombol tanpa warna sendiri; "Penggajian", "Hitung gaji Oktober 2026", "Daftar penggajian", "slip gaji", "Gaji bersih"); `hr/payrollUtils.js` (status "Terposting ke GL") | Posting & Sahkan meminta konfirmasi. |
| G5-34 [S] | diperbaiki | `hr/VisitsView.jsx` (tab Status di baris sendiri; keterangan "Ringkasan bulanan · periode KPI Oktober 2026 (terpisah dari rentang tanggal tabel)"; label KPI "(bulan ini)"; pesan kosong menyebut tanggal & periode KPI) | Tab status satu baris; KPI & tabel jelas beda cakupan. |
| G5-35 [S] | diperbaiki | `hr/KpiView.jsx` (FormModal + "Ubah KPI"; skor/target/aktual/bobot `formatDecimal`; periode `formatPeriod`; galat muat karyawan tampil; rumus jadi kalimat; pemilih karyawan aktif) | Tidak ada titik desimal/periode ISO; galat muat terlihat. |
| G5-36 [S] | diperbaiki | `hr/HrAnalyticsView.jsx` (Kehadiran/Ketepatan "—" + "Belum ada absensi tercatat" bila tak ada hari kerja; `formatPct`) | Periode tanpa absensi → "—". |
| G5-37 [S] | diperbaiki | `design/DesignRequestsView.jsx` (`summaryParams` tanpa status/lini/ronde → KPI TOTAL & lencana tab tetap; KPI ringkasan disembunyikan di tab Rapor; pesan kosong per status/lini/pencarian + "Tampilkan semua status & lini"; papan bergulir dengan bayangan tepi + catatan "Geser papan…"); `design/DesignerReportPanel.jsx` ("Belum ditugaskan" jadi catatan terpisah); `design/DesignRequestDetailPanel.jsx` (Batalkan → askReason `danger:true`); backend `design_request_service.report_by_designer` (`items` hanya desainer nyata, `unassigned: {requests, overdue}` baru, `totals` tetap semua permintaan) | Tab Draf/lini Woven: TOTAL tetap; Rapor tanpa baris "Belum ditugaskan" sebagai desainer. Tombol × detail = G0-07. |
| G5-38 [S] | diperbaiki (+ K-08) | `designer/designerMeta.js` (`normalizedWeights`; `gradeFormula` memakai porsi ternormalisasi = 100% + menyebut setelan 40:40:20:20); `designer/DesignerKpiView.jsx` (askConfirm sebelum "Kirim peringatan sekarang"; saringan divisi disembunyikan bila tak ada divisi; "ronde"); `designer/DesignerKpiTable.jsx` (kolom Desainer `sticky left-0`); "ronde" di `DesignerSlaPanel.jsx`, `DesignerKpiTrendChart.jsx` | "Cara nilai dihitung": 33,3% + 33,3% + 16,7% + 16,7%; nama tetap terlihat saat tabel digulir; eskalasi minta konfirmasi. Penyebab terbukti: `rnd_kpi_service.compute_grade` menormalkan bobot (Σw·v/Σw) — rumus tidak diubah. |
| G5-39 [S] | diperbaiki | `rnd/design/DesignImage.jsx`: gagal muat (404 / blob bukan gambar via `onError`) → ikon + teks "Gambar tidak dapat dimuat" mengikuti wadah; prop `compact` (ikon + tooltip) untuk thumbnail mungil | Galeri Desain / Desain & Pattern: kartu berkas 404 menampilkan teks fallback. |
| G5-40 [S] | sebagian | `hr/DesignShowcaseModal.jsx` ("Kategori desain"; Spesifikasi cetak disembunyikan bila kosong); `hr/DesignOwnershipPanel.jsx` ("pelanggan beli ulang", disembunyikan bila 0); `hr/DesignGalleryView.jsx` (tab status bukan filter; pesan kosong per status + tombol) | Showcase tanpa "— · 0 screen"/"0 repeat"; tab ACC tidak memunculkan "Hapus 1 filter". **Tidak diubah:** "White label / Customer label / Tetapkan customer label" = istilah P1 & diuji `uat24F3` → glosarium K-13. Tombol × = G0-07. |
| G5-41 [S] | diperbaiki | `rnd/design/DateQuickNav.jsx` (rentang bebas → 2× `KNDatePicker` satu kelompok, min/max saling kunci); `rnd/RndDesignsView.jsx` (`statusCounts` per status; 11 dropdown berlabel `FilterField`; pesan kosong per status + "Tampilkan semua"/"Hapus saringan") | Tab status menampilkan jumlah masing-masing; HP: rentang tanggal tidak patah 4 baris. Warna abu placeholder KNSelect = G0. |
| G5-42 [S] | diperbaiki | `rnd/design/ScoreInput.jsx` (`active` hanya bila nilai ada); `rnd/design/LifecycleActions.jsx` (satu tombol primary; "Ajukan untuk review" nonaktif + alasan bila ronde berjalan 0 berkas; dialog berkepala: judul, deskripsi per aksi, ×, Esc; konfirmasi ACC nonaktif sampai nilai dipilih); `rnd/design/ProofingPanel.jsx` ("Selesai/Berjalan") | Dialog ACC tanpa nilai terpilih; desain draf tanpa berkas → Ajukan nonaktif dengan teks alasan. (Dialog belum dipindah ke FormModal — L-03.) |
| G5-43 [S] | diperbaiki | `designer/DivisionsView.jsx` (`optionsFor(m)`: divisi tersimpan di luar daftar → "<nama> (di luar divisi R&D)"; judul "Divisi & Persetujuan"; "Anggota & penempatan divisi"; kolom "Penyetuju", `approverLabel` → "Manajer"; ganti divisi → askConfirm + pesan hasil) | Rina Merchandiser/Yoga Admin Sample tidak lagi "Pilih…". |
| G5-44 [S] | diperbaiki | `rnd/SampleTypeGalleryView.jsx` (`statusCounts` per status; pesan kosong per status + "Tampilkan semua"); `rnd/SampleFormModal.jsx` (`PLACEHOLDERS` per jenis/uji ulang; subjudul uji ulang "tidak membuat SKU atau spesifikasi baru"; isian handfeel induk kosong → tombol "Uji handfeel sekalian di permintaan ini" + petunjuk menu) | Tab "Gagal — menunggu PIC" kosong berhitungan 0; form Handfeel berplaceholder handfeel; Sample Labdip Baru tanpa handfeel ACC menunjukkan jalan keluar. Wajib-tidaknya induk = K-16. |
| G5-45 [S] | sebagian | `rnd/SampleSpecPanel.jsx` (bila `spec` tak disertakan tetapi `spec_number` ada → kartu dicari via `listSpecs({q})`; tak ketemu → kalimat menyebut nomornya); `rnd/SampleDetailPanel.jsx` (Batalkan danger + judul bernomor; tombol utama = langkah berikutnya; "Diajukan oleh" + "Dicatat oleh" bila pencatat riwayat berbeda; "Dikirim ke supplier" (`sent_at`) / "Sampel fisik diterima" / "Diserahkan"); `rnd/SampleFinishModal.jsx` ("Terima sampel fisik") | Detail sample tidak saling bertentangan. Penyebab "Dikirim: Belum" terbukti: baris itu = `delivered_at` (serah ke pelanggan), stepper = kirim ke supplier. **Tidak dikerjakan:** form "Ubah spesifikasi" = form buat → D-24 (pemilik). |
| G5-46 [S] | diperbaiki | backend `rnd_sample_service.py` (`_tgl_id`, `_jenis_label`, `_RESULT_LABEL`; teks riwayat "draf", "Dikirim ke supplier: N ronde dibuka (… Labdip) · target 30 Okt 2026", "Ronde N (Labdip) dibuka", "Hasil ronde…", "Ronde 1 (Labdip · CV …) → ACC · skor 92", "Sampel fisik diterima (25 Okt 2026)", "Sample dikirim ke … (25 Okt 2026)"); "ronde" di `SampleRoundList.jsx` (+ "QC: ACC"), `SampleSendModal.jsx`, `SampleTypeTabs.jsx`, `SampleBoardCard.jsx`, `RoundActionModal.jsx`, `SampleTypeGalleryView.jsx` | Entri riwayat BARU & pop-up kirim hanya "ronde"; entri lama di DB tidak dimigrasi. |
| G5-47 [S] | diperbaiki | `rnd/SampleSendModal.jsx`: `isGroupEntityPartner` → baris nonaktif + `GroupEntityBadge` + "tidak bisa dipilih" | "PT Uji Provisioning …" berlencana Entitas grup & tidak bisa dipilih. |
| G5-48 [S] | diperbaiki | backend `labdip_history` (+`waiting`, `summary.samples_shown`, `summary.waiting`; `summary.samples` tetap); `rnd/LabdipHistoryModal.jsx` (baris "belum dikirim" bisa dibuka; KPI Permintaan = `samples_shown`; kolom "Ronde"; `formatDate`) | Riwayat KN-BLU-01: KPI Permintaan = baris yang tampil. Penyebab: permintaan berwarna itu belum punya ronde labdip (draf/jenis lain). |
| G5-49 [S] | diperbaiki | `rnd/SpecDetailPanel.jsx`: tahap `useDomainEnums().labelOf("stage", …)`; gramasi/lebar/target harga kosong → "—" | KSC/SPEC-00751 tanpa "finished"/"0 gsm"/"Rp 0". |
| G5-54 [S] | diperbaiki | `marketing/MarketingAnalytics.jsx` (kolom `h-full`, area batang `relative flex-1`, batang `absolute bottom-0` ber-tinggi %) | Batang Okt 26 terlihat. |
| G5-55 [S] | diperbaiki | `marketing/PostFormModal.jsx` (PIC `roleLabel(u.role)`; tanggal kampanye `formatDate`) | PIC "Nadia Putri (Admin Sales)". |
| G5-61 [S] | sebagian | `rnd/RndSpecsView.jsx`: Kebijakan R&D → `openConfig({ group: "rnd" })` (dulu kunci+kelompok) | SettingCard/ConfigDrawers & penyaringan kelompok di Pusat Pengaturan → G5b. |
| G5-63 [S] | diperbaiki | `rnd/SampleTypeGalleryView.jsx` tombol "Sample … Baru" `disabled={!canWriteInScope(selectedEntity)}` + tooltip | Mode Semua badan usaha: tombol buat nonaktif. |
| G5-65 [R] | diperbaiki | `hr/LiveTrackingView.jsx` ("akurasi ±12 m"; lencana "Terhubung"/"Diperbarui berkala"; "Sembunyikan jejak") | Teks tidak ambigu. |
| G5-66 [R] | diperbaiki | `hr/payrollUtils.js` `pct` → `formatPct`; `hr/PayslipsView.jsx` ("PPh 21 (0,75% × bruto)", `formatPeriod`); `hr/MyPayslipCard.jsx` (periode) | "PPh 21 (0,75% × bruto)", "September 2026". |
| G5-67 [R] | diperbaiki | `marketing/CampaignCostsModal.jsx` (Nominal → `MoneyInput`; subjudul tanpa "Dr/Cr"); `marketing/Campaigns.jsx` (Anggaran → `MoneyInput`; kartu tema + rentang `formatDate` tanpa pemisah menggantung) | Form biaya memakai input uang; "1 Okt 2026 – 31 Okt 2026". |
| G5-68 [R] | diperbaiki | `rnd/design/DesignDetailPage.jsx` ("atur peruntukan" baris sendiri; meta hanya bagian yang ada; langkah aktif stepper biru; ronde hanya bila revisi > 0; skor tanpa "ACC" kedua; "Spesifikasi cetak" disembunyikan bila kosong) | Kepala detail tanpa "—" menggantung & tanpa tiga lencana. |

## Tambahan atas catatan G0 (pesan galat API & LocationFields)

- **P-07 / G0-03:** 64 tempat `e.response?.data?.detail || "…"` di folder hr & marketing diganti `apiErrorText(e, "…")`
  (impor `utils/apiError` ditambahkan); `rnd/rndMeta.js` `errMsg()` kini memanggil `apiErrorText` → seluruh layar
  R&D/desain/desainer yang memakai `errMsg` ikut menerjemahkan "Permission ditolak: x.y". `design/designRequestsApi.apiText`
  sudah = `apiErrorText`. Sisa 1 pola berbeda di `hr/DesignOwnershipPanel.jsx` (bukan bentuk `detail || "teks"`), dibiarkan.
  Berkas yang HANYA tersentuh perubahan ini: `hr/AiIllustrationPanel.jsx`, `hr/MyDesignerKpiCard.jsx`, `hr/MyVisitsPanel.jsx`,
  `marketing/ContentCalendar.jsx`, `marketing/DuplicatePostModal.jsx`, `marketing/PostDetailModal.jsx`, `marketing/SocialAccounts.jsx`.
- **LocationFields `showErrors`:** `hr/EmployeeFormDrawer.jsx` memakai `LocationFields required={false}` (alamat karyawan
  opsional), jadi `showErrors` tidak berpengaruh — tidak ditambahkan. Bila pemilik mewajibkan alamat, tambahkan
  `required showErrors={submitTried}` sekaligus.

## Berkas diubah (69)

Backend: `backend/services/rnd_sample_service.py`, `backend/services/design_request_service.py`, **baru** `backend/tests/test_audit_ui2_g5a.py`.

Frontend `frontend/src/features/`:
- design: `DesignRequestDetailPanel.jsx`, `DesignRequestsView.jsx`, `DesignerReportPanel.jsx`, `LinkedDesignsPanel.jsx`, `ReferenceGallery.jsx`
- designer: `DesignerKpiTable.jsx`, `DesignerKpiTrendChart.jsx`, `DesignerKpiView.jsx`, `DesignerSlaPanel.jsx`, `DivisionsView.jsx`, `designerMeta.js`
- hr: `AttendanceSetupView.jsx`, `AttendanceView.jsx`, `DesignGalleryView.jsx`, `DesignOwnershipPanel.jsx`, `DesignShowcaseModal.jsx`, `Employee360Panel.jsx`, `EmployeeFormDrawer.jsx`, `EmployeeSelfService.jsx`, `EmployeesView.jsx`, `HrAnalyticsView.jsx`, `KpiView.jsx`, `LeaveView.jsx`, `LiveTrackingView.jsx`, `MyLeaveCard.jsx`, `MyPayslipCard.jsx`, `OrgUnitsView.jsx`, `OvertimeView.jsx`, `PayrollRunsView.jsx`, `PayslipsView.jsx`, `VisitsView.jsx`, `leaveUtils.js`, `payrollUtils.js`
- marketing: `CampaignCostsModal.jsx`, `Campaigns.jsx`, `MarketingAnalytics.jsx`, `PostFormModal.jsx`
- rnd: `LabdipHistoryModal.jsx`, `RndDesignsView.jsx`, `RndSpecsView.jsx`, `RoundActionModal.jsx`, `SampleBoardCard.jsx`, `SampleDetailPanel.jsx`, `SampleFinishModal.jsx`, `SampleFormModal.jsx`, `SampleRoundList.jsx`, `SampleSendModal.jsx`, `SampleSpecPanel.jsx`, `SampleTypeGalleryView.jsx`, `SampleTypeTabs.jsx`, `SpecDetailPanel.jsx`, `rndMeta.js`, `design/DateQuickNav.jsx`, `design/DesignDetailPage.jsx`, `design/DesignImage.jsx`, `design/LifecycleActions.jsx`, `design/ProofingPanel.jsx`, `design/ScoreInput.jsx`
- uji baru: `__tests__/auditUi2G5a.test.js`

Semua LF, tanpa karakter kontrol (diperiksa skrip).

## Uji dijalankan

- **ESLint** seluruh berkas frontend yang diubah/baru (folder hr, marketing, rnd, design, designer + uji baru): **0 error**, hanya warning "Unused eslint-disable directive" yang sudah ada sebelumnya.
- **Jest** (`--maxWorkers=1`): `features/__tests__/auditUi2G5a.test.js` (baru, 6 uji: cleanRndNote, bobot ternormalisasi, ScoreInput null, DesignImage fallback, pemilih karyawan aktif, pct id-ID) + `uatV3SpecialOrder.test.js`, `uat24F3.test.js`, `roleGateSweep.test.js`, `uat24F0.test.js` → **5 suite, 34 uji LULUS**.
- **pyflakes** `rnd_sample_service.py`, `design_request_service.py`, `tests/test_audit_ui2_g5a.py`: bersih.
- **pytest tingkat layanan** `tests/test_audit_ui2_g5a.py` (DB `kn_test_trial`, `-p no:randomly -n 0`): **4 passed**.

## Uji backend untuk koordinator (butuh server ter-restart / HTTP)

- `backend/tests/test_audit_ui2_g5a.py` (sudah hijau tingkat layanan; jalankan ulang di gate terpusat).
- `backend/tests/test_p05_restock_material_revalidation.py::…test_*labdip*` / kelas yang memanggil `GET /api/rnd/labdip-history` (cek `summary.samples` tetap ≥ 2 — kunci lama dipertahankan).
- `backend/test_core_design_request_poc.py` (D4 rapor by-designer: baris desainer POC tetap ada; baris "Belum ditugaskan" kini di `unassigned`, bukan `items`).
- Uji/POC sampling yang membaca teks riwayat sample (tidak ditemukan yang mengasersi teks lama; `backend/test_core_sampling_poc.py` hanya label cek).
- Perubahan backend butuh restart `uvicorn` agar aktif di layar: label riwayat sample (G5-46), `waiting` riwayat labdip (G5-48), `unassigned` rapor desainer (G5-37). Tanpa restart, layar tetap aman (fallback: `waiting` kosong, `samples_shown ?? samples`, `unassigned` tak ada → catatan tidak tampil; baris "Belum ditugaskan" masih muncul dari server lama).

## Butuh grup lain

- **G5b** — G5-21: `features/approvals/ApprovalInbox.jsx` (ringkasan = jumlah baris, pesan sales saat kategori 403, label "Penggajian" + `formatPeriod`).
- **G5b** — G5-61: `features/settings/config/SettingCard.jsx`, `ConfigDrawers.jsx` (sembunyikan kunci teknis, bersihkan backtick + `stripInternalCodes`, lencana abu "Tidak dipakai" untuk setting usang, nama badan usaha di Riwayat). Penting: Pusat Pengaturan harus **menyaring ke kelompok** bila dibuka dengan `openConfig({ group: "rnd" })` saja (tombol Kebijakan R&D kini tidak lagi mengirim `key`).
- **G0** — G5-05/G5-39/P-09: `components/AttachmentThumb.jsx` masih hanya ikon 14px saat gagal (dipakai layar lain); `MediaLightbox` tetap menawarkan "Perbesar" untuk gambar gagal (G0-18). × pada `DetailModal framed` (G5-37 detail DSR, G5-40 Showcase) = G0-07. Warna abu dropdown saringan Desain & Pattern = KNSelect (G0-04/05).

## Catatan risiko / pemilik

- **K-08** (G5-38): server menormalkan bobot nilai desainer; layar kini menampilkan porsi efektif (33,3/33,3/16,7/16,7%) + setelan asli. Bila pemilik ingin "nilai desain" sebagai bonus di luar 100%, rumus di `rnd_kpi_service` (bukan milik G5) harus diubah.
- **K-09** (G5-21): awalan `PR-` payroll tidak diubah.
- **K-13** (G5-40): "White label / Customer label" dipertahankan (istilah P1, diuji).
- **K-16** (G5-44): induk handfeel ACC tetap wajib untuk labdip produk baru; form hanya menunjukkan jalan keluar.
- **D-24** (G5-45): "Ubah spesifikasi" (6 isian) ≠ form buat — tidak disatukan.
- **L-03**: dialog siklus desain (`LifecycleActions`) & `LabdipHistoryModal` masih pop-up buatan sendiri (diberi kepala standar/×, belum FormModal).
- `DesignerKpiTable` kolom sticky memakai `bg-inherit` — baris aktif/hover ikut warnanya; header sticky ber-latar putih.
- `SampleSpecPanel` melakukan satu GET `/rnd/specs?q=<nomor>` tambahan hanya bila server tidak menyertakan `spec` padahal `spec_number` ada (data lama).
- Teks riwayat sample lama di DB ("Round 1 (labdip…) → acc", "draft") tetap tampil apa adanya — perlu migrasi data bila ingin seragam (tidak dilakukan).
- Konfirmasi baru (askConfirm) menambah satu klik pada: Setujui cuti/lembur, Sahkan/Posting GL/Bayar gaji, Kirim peringatan SLA, ganti divisi R&D — skrip E2E/crawler yang mengklik tombol itu perlu menekan "Setujui/Posting…" di dialog.
