# 🧾 GATE RECEIPT — Kain Nusantara

> Bukti verifikasi otomatis. Dihasilkan `scripts/gate.sh`. JANGAN edit manual.

- **Waktu:** 2026-11-14 22:38:47
- **Mode:** `ci`  ·  **Durasi total:** 1122s  ·  **Pekerja statik:** 2
- **Backend:** RUNNING + auth siap (gate runtime dijalankan)

| Gate | Hasil |
|------|-------|
| guard:auth_coverage (INV-AUTH-01) | FAIL (1s) |
| guard:auth_coverage SELF-TEST (bukti-merah penjaga auth) | PASS (0s) |
| validate_compliance (file/naming/docs/api/env) | FAIL (12s) |
| check_nav_map (navigasi vs SSOT) | PASS (0s) |
| guard:modal_dismiss (INV-UI-01, modal auto-close) | PASS (0s) |
| guard:knselect_contract (FE-02, pilihan wajib onValueChange) | PASS (0s) |
| guard:access_catalog_nav (FE-03, katalog modul ↔ menu) | PASS (0s) |
| guard:access_catalog_nav SELF-TEST (KP-T9, bukti-merah aturan 1–4) | PASS (0s) |
| guard:desk_targets (FE-06, target antrean ke layar nyata) | PASS (0s) |
| guard:create_modal SELF-TEST (bukti-merah penjaga create pop-up) | PASS (0s) |
| guard:create_modal (INV-UI-05, tombol Buat = pop-up konsisten) | FAIL (3s) |
| guard:blocking_dialogs SELF-TEST (bukti-merah + anti tuduh palsu) | PASS (0s) |
| guard:blocking_dialogs (INV-UI-06, alert/confirm/prompt dilarang) | PASS (11s) |
| guard:list_export SELF-TEST (bukti-merah + CSV rusak harus memerah) | PASS (0s) |
| guard:list_export (INV-UI-07, daftar berhalaman wajib bisa diunduh) | PASS (9s) |
| guard:money_idempotency SELF-TEST (bukti-merah axios langsung ke jalur uang) | PASS (0s) |
| guard:money_idempotency (INV-MONEY-IDEM-01, form uang ber-Idempotency-Key) | PASS (1s) |
| guard:detail_modal SELF-TEST (bukti-merah + anti tuduh palsu) | PASS (1s) |
| guard:detail_modal (INV-UI-08, panel rincian wajib pop-up) | PASS (6s) |
| guard:picker_portal SELF-TEST (bukti-merah + anti tuduh palsu, 16 kasus) | PASS (29s) |
| guard:picker_portal (INV-UI-09, pemilih wajib ber-portal · pop-up bukan anak <label>) | PASS (41s) |
| guard:escape_layers SELF-TEST (bukti-merah + anti tuduh palsu, 13 kasus) | PASS (4s) |
| guard:escape_layers (INV-UI-10, Esc menutup lapisan teratas saja) | PASS (9s) |
| guard:custom_modals SELF-TEST (ratchet dua arah, 9 kasus) | PASS (0s) |
| guard:custom_modals (INV-UI-11, pop-up buatan sendiri hanya boleh berkurang) | PASS (8s) |
| guard:page_tabs SELF-TEST (ratchet dua arah + batas tab hub + tab tingkat ketiga, 14 kasus) | PASS (0s) |
| guard:page_tabs (INV-UI-12/13/14, tab maks 2 tingkat · maks 6 tab per hub · tanpa tab tingkat ketiga) | FAIL (10s) |
| guard:view_aliases SELF-TEST (bukti-merah dua arah, 8 kasus) | PASS (0s) |
| guard:view_aliases (INV-NAV-02, alias layar tidak memutus pintu/hak) | PASS (1s) |
| guard:config_text SELF-TEST (bukti-merah satu kasus per aturan T1–T7) | PASS (0s) |
| guard:config_text (INV-CFG-TXT, teks Pengaturan awam & bersub-judul) | PASS (3s) |
| config_key_index (KF-T4, indeks kunci layar selaras registry) | PASS (2s) |
| guard:payment_vocab SELF-TEST (bukti-merah dua arah, 18 kasus) | PASS (0s) |
| guard:payment_vocab (INV-PAY-VOCAB-01, pilihan cara bayar dari daftar induk) | PASS (29s) |
| guard:to_list_bound SELF-TEST (bukti-merah dua arah, 11 kasus) | FAIL (1s) |
| guard:to_list_bound (INV-PERF-01, to_list(n>20000) dilarang) | FAIL (0s) |
| guard:codebase_map SELF-TEST (bukti-merah dua arah, 6 kasus) | PASS (26s) |
| guard:codebase_map (INV-DOC-01, CODEBASE_MAP.md selaras kode) | PASS (12s) |
| guard:atomic_claim SELF-TEST (bukti-merah dua arah, 10 kasus) | FAIL (29s) |
| guard:atomic_claim (INV-ATOMIC-01, saga/CAS endpoint multi-koleksi) | FAIL (30s) |
| guard:posting_coverage SELF-TEST (bukti-merah dua arah, 13 kasus) | PASS (20s) |
| guard:posting_coverage (INV-POST-01, jurnal dokumen lewat pintu tahan-gagal) | PASS (19s) |
| guard:cash_single_door SELF-TEST (bukti-merah dua arah, 15 kasus) | PASS (22s) |
| guard:cash_single_door (INV-CASH-01, kas lewat satu pembuat) | PASS (25s) |
| ux_audit SELF-TEST (bukti-merah baseline UX + anti tuduh palsu) | PASS (1s) |
| ux_audit --strict (INV-UX-01, loading/empty/chart baseline) | FAIL (17s) |
| config_wiring (INV-CFG-01/04, satu sumber kebenaran) | PASS (40s) |
| config_wiring SELF-TEST (bukti-merah guardrail) | PASS (216s) |
| guard:config_fallback SELF-TEST (bukti-merah cadangan ≠ bawaan, konstanta, pengecualian basi) | PASS (77s) |
| guard:config_fallback (INV-CFG-09, cadangan = bawaan registry) | PASS (44s) |
| guard:config_entity SELF-TEST (bukti-merah value_of tanpa PT dokumen) | PASS (67s) |
| guard:config_entity (INV-CFG-10, nilai PT diteruskan) | PASS (31s) |
| audit_doc_refs SELF-TEST (bukti-merah relasi dokumen) | PASS (0s) |
| guard:ref_unlink SELF-TEST (bukti-merah dua arah, 8 kasus) | PASS (2s) |
| guard:ref_unlink (INV-REF-04, hapus dokumen wajib sapu tautan balik) | FAIL (42s) |
| guard:notif_audience SELF-TEST (bukti-merah dua arah, 14 kasus) | PASS (0s) |
| guard:notif_audience (INV-NOTIF-02, alamat notifikasi dari WEWENANG) | PASS (33s) |
| audit_i18n_id (label antarmuka Bahasa Indonesia) | FAIL (9s) |
| audit_i18n_id SELF-TEST (bukti-merah guardrail bahasa) | PASS (0s) |
| fix_i18n_id SELF-TEST (codemod tak boleh sentuh kode) | PASS (0s) |
| guard:entity_label (INV-UI-02, id entitas tak boleh tampil) | FAIL (5s) |
| guard:error_notice (INV-UI-03, error tak boleh senyap) | PASS (0s) |
| guard:role_label (INV-ROLE-01, peran dari registry & izin) | PASS (7s) |
| guard:role_gate_ui SELF-TEST (bukti-merah sisipan roleIs/includes(role)) | PASS (13s) |
| guard:role_gate_ui (INV-ROLE-02, tombol dari izin) | PASS (12s) |
| guard:permission_checked SELF-TEST (bukti-merah sisipan izin tanpa pemeriksa) | PASS (22s) |
| guard:permission_checked (INV-PERM-01, izin di katalog diperiksa server) | PASS (23s) |
| guard:derived_fields (INV-UI-04, field turunan tak boleh dari respons daftar) | PASS (2s) |
| audit_entity_isolation SELF-TEST (bukti-merah pagar isolasi) | PASS (4s) |
| guard:write_scope SELF-TEST (INV-ENTITY-02, mode gabungan hanya-lihat) | PASS (0s) |
| guard:warehouse_scope SELF-TEST (E4.1, gudang khusus badan usaha) | FAIL (6s) |
| guard:numeric_bounds (INV-NUM-01, statik+runtime) | FAIL (1s) |
| seed_realistic (data uji bersih) | PASS (40s) |
| verify_data_integrity (229 invarian domain/GL/alert/ledger/config/relasi/pembayaran/selisih/bank/kasus/kontrabon/antar-entitas) | FAIL (42s) |
| verify_entity_scoping (F0-C, DB + STATIK anti-kebocoran PT) | PASS (5s) |
| audit_doc_refs (INV-REF cakupan data + kesehatan tautan) | FAIL (3s) |
| guard:roll_identity SELF-TEST (bukti-merah + anti tuduh palsu) | PASS (34s) |
| guard:roll_identity (INV-ROLL-01, satu nomor untuk satu roll) | PASS (35s) |
| guard:rfid_tag_unique SELF-TEST (bukti-merah dua arah, 7 kasus) | PASS (0s) |
| guard:rfid_tag_unique (INV-RFID-01, satu tag untuk satu roll aktif) | PASS (2s) |
| config_roundtrip (INV-CFG-08, tiap kunci tulis→baca tiga jalur) | PASS (552s) |
| guard:cross_entity (INV-ENTITY-01, IDOR multi-PT) | PASS (3s) |
| guard:nonfinancial_sweep (INV-ENTITY-01+, IDOR non-finansial) | PASS (2s) |
| audit_2026_09_21 (penjaga entitas aksi tulis · R-3a sampel · konstanta bersama) | FAIL (4s) |
| POC F0-C (isolasi lintas-entitas: kartu asal · roll retur · jejak UoM) | PASS (4s) |
| audit_entity_isolation (E0.9/E0.10 — 0 kebocoran lintas-entitas) | FAIL (29s) |
| POC FASE E-0 (bukti-merah L1–L21: notifikasi·denda·audit·lot·AR·transfer·dokumen·pratinjau) | FAIL (5s) |
| POC FASE E-3 (mode “Semua Entitas” hanya-lihat: 409 menuntun · master bersama tetap boleh) | PASS (3s) |
| POC FASE E-4 (gudang bersama/khusus · harga per badan usaha · CSV) | FAIL (4s) |
| POC FASE E-4 master berlapis (global→badan usaha · override · kop surat per PT) | PASS (3s) |
| POC FASE E-5 (papan stok agregat · pegging · mutasi lintas-PT nama singkat · kartu riwayat) | PASS (3s) |
| POC FASE E-7 (pagar entitas grup · HPP taksiran berlabel · permintaan internal · kas grup dihapus · pinjaman & pindah aset antar-PT) | FAIL (6s) |
| POC FASE E-8 G1 (peran sales_admin & finance · pemisahan tugas · penugasan entitas) | PASS (6s) |
| POC FASE E-8 G2/G3 (meja admin sales & finance · verifikasi · keputusan pemenuhan) | FAIL (8s) |
| POC FASE E-9 (rantai jual→beli internal antar-PT→retur berantai · 41 pemeriksaan) | FAIL (1s) |
| POC Cek Kenyataan Peran (utang migrasi ii E-8 · usulan peran dari jejak nyata) | PASS (5s) |
| audit_sales_roles_ux SELF-TEST (bukti-merah penilaian layar mati) | PASS (0s) |
| audit_sales_roles_ux (SEMUA peran: nol layar & panel mati) | FAIL (58s) |
| POC F-2 Akses & UI/UX per peran (izin baca · pagar · KPI jujur · bukti-merah) | PASS (24s) |
| POC F-1b Migrasi kas tingkat grup (utang migrasi i · 4 lapis bukti · idempotent) | PASS (7s) |
| POC Pengingat Antrean Persetujuan (umur tunggu · eskalasi · idempotent · ambang pemilik) | PASS (6s) |
| POC FASE F-6 (pensiun mesin generik · 14 antrean nyata · anti dobel-hitung) | FAIL (8s) |
| POC FASE F-6.7 (langkah Ajukan payroll & desain · selisih bayar · verifikasi SO) | FAIL (11s) |
| guard:home_kpi SELF-TEST (bukti-merah penjaga KPI beranda) | PASS (0s) |
| guard:home_kpi (INV-HOME-01, KPI beranda = antrean nyata) | PASS (5s) |
| guard:aging_fields SELF-TEST (bukti-merah field umur ditebak) | PASS (0s) |
| guard:aging_fields (INV-AGING-01, field umur tunggu wajib nyata) | PASS (1s) |
| guard:status_history SELF-TEST (bukti-merah bentuk riwayat ke-dua) | PASS (0s) |
| guard:status_history (INV-HIST-01, satu bentuk riwayat status) | PASS (0s) |
| POC Papan PO Custom (umur tunggu bukan tebakan · yang tertua ikut · jujur saat dipotong · nol residu) | PASS (10s) |
| POC Sesi 2026-06 (true-up persediaan · papan manajer · umur tunggu antrean lain · satu bentuk riwayat) | FAIL (14s) |
| guard:approval_queues SELF-TEST (bukti-merah penjaga antrean keputusan) | PASS (0s) |
| guard:approval_queues (INV-APPR-01, tiap pintu keputusan punya antrean) | FAIL (2s) |
| guard:concurrency (INV-CONC-01, race/TOCTOU uang) | PASS (2s) |
| guard:state_machine (INV-STATE-01, transisi SO) | PASS (2s) |
| guard:line_scope SELF-TEST (bukti-merah pagar lini, 15 kasus dua arah) | PASS (0s) |
| guard:line_scope (INV-LINE-01/02, kode dikenal · turunan jujur · snapshot lengkap) | FAIL (1s) |
| POC FASE L (lini produk: master bertambah · pagar keras · snapshot · isolasi PT) | FAIL (4s) |
| guard:master_stages SELF-TEST (bukti-merah tahapan proses, 20 kasus dua arah) | PASS (0s) |
| guard:master_stages (INV-DOMAIN-06, master tahapan vs registry domain) | PASS (2s) |
| POC FASE T (tahapan proses: master bertambah · screen tak ubah kain · regresi identik) | FAIL (8s) |
| guard:uom_vocab SELF-TEST (bukti-merah kosakata satuan, 23 kasus dua arah) | PASS (4s) |
| guard:uom_vocab (INV-UOM-02, satuan dokumen ⊆ master uoms · alias tak kembar · pemilih satuan dari master) | PASS (4s) |
| guard:qty_dual SELF-TEST (bukti-merah dua satuan, 32 kasus dua arah) | FAIL (5s) |
| guard:qty_dual (INV-QTY-01, dua satuan satu arti di layar · PDF · CSV) | FAIL (4s) |
| POC FASE U (dua satuan: PO→terima→PDF/CSV · retur turun serentak · satuan lini · dokumen lama "—") | FAIL (25s) |
| guard:doc_origin SELF-TEST (bukti-merah asal dokumen PO, 26 kasus dua arah) | PASS (0s) |
| guard:doc_origin (INV-ORIG-01, satu definisi asal PO · sales dirunut bukan diketik · refs dua arah) | PASS (1s) |
| POC P-0 (asal dokumen PO: PO→PR→SO · Nama Sales dirunut · PO rutin kosong-jujur · nol residu) | FAIL (8s) |
| guard:po_board SELF-TEST (bukti-merah papan PO, 22 kasus dua arah) | PASS (0s) |
| guard:po_board (INV-STAGE-01, tahap dari master · inspect turunan · tanda tahap ber-jejak) | PASS (1s) |
| POC FASE P (papan PO per lini: tahap dari master · sales dirunut · inspect turunan · terima dihitung · nol residu) | FAIL (38s) |
| POC FASE D · PERMINTAAN DESAIN (DSR) (tugas→serah→revisi ber-alasan→ACC · rapor = hitung-ulang · peran ke-7 sempit tapi jujur) | FAIL (14s) |
| guard:sample_types SELF-TEST (bukti-merah jenis sampling, 37 kasus dua arah) | PASS (1s) |
| guard:sample_types (INV-SAMPLE-01, jenis dari master · satu sumber · hasil ukur dinamis · jadi→kirim) | PASS (1s) |
| POC FASE S (sampling: dua jenis paralel · ukur dari master · jadi→kirim · nol residu) | FAIL (4s) |
| POC FASE I (inspeksi & QC: SPK otomatis · grade dari mesin lama · tahanan warna dilepas manajer · nol residu) | FAIL (5s) |
| POC FASE N (notifikasi beralamat: izin & divisi · dedupe per orang · nol siaran 'all') | PASS (3s) |
| audit_endpoint_sweep (semua GET → 5xx · paralel) | FAIL (32s) |
| health_check (isi endpoint kritis) | PASS (4s) |
| INV-GATE-01 anti-residu (gate tak boleh merusak data) | FAIL (1s) |

## ❌ VERDICT: MERAH — ADA GATE GAGAL. Lihat memory/BUG_REGISTRY.md. Perbaiki lalu jalankan ulang.

**Tingkatan:** `--quick` (statik ~7s) · default (~25s) · `--ci` (default + receipt JSON) · `--full` (+POC fase ~95s).

_Catatan: SKIP bukan PASS. Gate runtime harus dijalankan ulang saat backend hidup._
