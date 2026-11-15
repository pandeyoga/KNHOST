# 🧾 GATE RECEIPT — Kain Nusantara

> Bukti verifikasi otomatis. Dihasilkan `scripts/gate.sh`. JANGAN edit manual.

- **Waktu:** 2026-11-15 21:34:32
- **Mode:** `quick`  ·  **Durasi total:** 98s  ·  **Pekerja statik:** 2
- **Backend:** DOWN / tidak diperiksa (mode quick atau Phase 0)

| Gate | Hasil |
|------|-------|
| guard:auth_coverage (INV-AUTH-01) | FAIL (0s) |
| guard:auth_coverage SELF-TEST (bukti-merah penjaga auth) | PASS (0s) |
| validate_compliance (file/naming/docs/api/env) | FAIL (2s) |
| check_nav_map (navigasi vs SSOT) | PASS (0s) |
| guard:modal_dismiss (INV-UI-01, modal auto-close) | PASS (0s) |
| guard:knselect_contract (FE-02, pilihan wajib onValueChange) | PASS (0s) |
| guard:access_catalog_nav (FE-03, katalog modul ↔ menu) | PASS (0s) |
| guard:access_catalog_nav SELF-TEST (KP-T9, bukti-merah aturan 1–4) | PASS (0s) |
| guard:desk_targets (FE-06, target antrean ke layar nyata) | PASS (0s) |
| guard:create_modal SELF-TEST (bukti-merah penjaga create pop-up) | PASS (0s) |
| guard:create_modal (INV-UI-05, tombol Buat = pop-up konsisten) | FAIL (1s) |
| guard:blocking_dialogs SELF-TEST (bukti-merah + anti tuduh palsu) | PASS (0s) |
| guard:blocking_dialogs (INV-UI-06, alert/confirm/prompt dilarang) | PASS (2s) |
| guard:list_export SELF-TEST (bukti-merah + CSV rusak harus memerah) | PASS (0s) |
| guard:list_export (INV-UI-07, daftar berhalaman wajib bisa diunduh) | PASS (1s) |
| guard:money_idempotency SELF-TEST (bukti-merah axios langsung ke jalur uang) | PASS (0s) |
| guard:money_idempotency (INV-MONEY-IDEM-01, form uang ber-Idempotency-Key) | PASS (1s) |
| guard:detail_modal SELF-TEST (bukti-merah + anti tuduh palsu) | PASS (0s) |
| guard:detail_modal (INV-UI-08, panel rincian wajib pop-up) | PASS (1s) |
| guard:picker_portal SELF-TEST (bukti-merah + anti tuduh palsu, 16 kasus) | PASS (6s) |
| guard:picker_portal (INV-UI-09, pemilih wajib ber-portal · pop-up bukan anak <label>) | PASS (8s) |
| guard:escape_layers SELF-TEST (bukti-merah + anti tuduh palsu, 13 kasus) | PASS (2s) |
| guard:escape_layers (INV-UI-10, Esc menutup lapisan teratas saja) | PASS (1s) |
| guard:custom_modals SELF-TEST (ratchet dua arah, 9 kasus) | PASS (0s) |
| guard:custom_modals (INV-UI-11, pop-up buatan sendiri hanya boleh berkurang) | PASS (1s) |
| guard:page_tabs SELF-TEST (ratchet dua arah + batas tab hub + tab tingkat ketiga, 14 kasus) | PASS (0s) |
| guard:page_tabs (INV-UI-12/13/14, tab maks 2 tingkat · maks 6 tab per hub · tanpa tab tingkat ketiga) | FAIL (2s) |
| guard:view_aliases SELF-TEST (bukti-merah dua arah, 8 kasus) | PASS (0s) |
| guard:view_aliases (INV-NAV-02, alias layar tidak memutus pintu/hak) | PASS (0s) |
| guard:config_text SELF-TEST (bukti-merah satu kasus per aturan T1–T7) | PASS (0s) |
| guard:config_text (INV-CFG-TXT, teks Pengaturan awam & bersub-judul) | PASS (0s) |
| config_key_index (KF-T4, indeks kunci layar selaras registry) | PASS (0s) |
| guard:payment_vocab SELF-TEST (bukti-merah dua arah, 18 kasus) | PASS (0s) |
| guard:payment_vocab (INV-PAY-VOCAB-01, pilihan cara bayar dari daftar induk) | PASS (5s) |
| guard:to_list_bound SELF-TEST (bukti-merah dua arah, 11 kasus) | FAIL (0s) |
| guard:to_list_bound (INV-PERF-01, to_list(n>20000) dilarang) | FAIL (0s) |
| guard:codebase_map SELF-TEST (bukti-merah dua arah, 6 kasus) | PASS (5s) |
| guard:codebase_map (INV-DOC-01, CODEBASE_MAP.md selaras kode) | PASS (2s) |
| guard:atomic_claim SELF-TEST (bukti-merah dua arah, 64 kasus) | PASS (4s) |
| guard:atomic_claim (INV-ATOMIC-01, saga/CAS endpoint multi-koleksi) | PASS (5s) |
| guard:posting_coverage SELF-TEST (bukti-merah dua arah, 13 kasus) | PASS (4s) |
| guard:posting_coverage (INV-POST-01, jurnal dokumen lewat pintu tahan-gagal) | PASS (4s) |
| guard:cash_single_door SELF-TEST (bukti-merah dua arah, 15 kasus) | PASS (4s) |
| guard:cash_single_door (INV-CASH-01, kas lewat satu pembuat) | PASS (4s) |
| ux_audit SELF-TEST (bukti-merah baseline UX + anti tuduh palsu) | PASS (0s) |
| ux_audit --strict (INV-UX-01, loading/empty/chart baseline) | FAIL (3s) |
| config_wiring (INV-CFG-01/04, satu sumber kebenaran) | PASS (6s) |
| config_wiring SELF-TEST (bukti-merah guardrail) | PASS (40s) |
| guard:config_fallback SELF-TEST (bukti-merah cadangan ≠ bawaan, konstanta, pengecualian basi) | PASS (15s) |
| guard:config_fallback (INV-CFG-09, cadangan = bawaan registry) | PASS (7s) |
| guard:config_entity SELF-TEST (bukti-merah value_of tanpa PT dokumen) | PASS (9s) |
| guard:config_entity (INV-CFG-10, nilai PT diteruskan) | PASS (6s) |
| audit_doc_refs SELF-TEST (bukti-merah relasi dokumen) | PASS (0s) |
| guard:ref_unlink SELF-TEST (bukti-merah dua arah, 8 kasus) | PASS (1s) |
| guard:ref_unlink (INV-REF-04, hapus dokumen wajib sapu tautan balik) | FAIL (7s) |
| guard:notif_audience SELF-TEST (bukti-merah dua arah, 14 kasus) | PASS (0s) |
| guard:notif_audience (INV-NOTIF-02, alamat notifikasi dari WEWENANG) | PASS (7s) |
| audit_i18n_id (label antarmuka Bahasa Indonesia) | FAIL (2s) |
| audit_i18n_id SELF-TEST (bukti-merah guardrail bahasa) | PASS (0s) |
| fix_i18n_id SELF-TEST (codemod tak boleh sentuh kode) | PASS (0s) |
| guard:entity_label (INV-UI-02, id entitas tak boleh tampil) | FAIL (1s) |
| guard:error_notice (INV-UI-03, error tak boleh senyap) | PASS (0s) |
| guard:role_label (INV-ROLE-01, peran dari registry & izin) | PASS (2s) |
| guard:role_gate_ui SELF-TEST (bukti-merah sisipan roleIs/includes(role)) | PASS (3s) |
| guard:role_gate_ui (INV-ROLE-02, tombol dari izin) | PASS (2s) |
| guard:permission_checked SELF-TEST (bukti-merah sisipan izin tanpa pemeriksa) | PASS (4s) |
| guard:permission_checked (INV-PERM-01, izin di katalog diperiksa server) | PASS (4s) |
| guard:derived_fields (INV-UI-04, field turunan tak boleh dari respons daftar) | PASS (0s) |
| audit_entity_isolation SELF-TEST (bukti-merah pagar isolasi) | PASS (1s) |
| guard:write_scope SELF-TEST (INV-ENTITY-02, mode gabungan hanya-lihat) | PASS (0s) |
| guard:warehouse_scope SELF-TEST (E4.1, gudang khusus badan usaha) | FAIL (1s) |
| guard:numeric_bounds (INV-NUM-01, statik+runtime) | FAIL (0s) |
| seed_realistic | SKIP |
| verify_data_integrity | SKIP |
| gate runtime (IDOR/race/state/sweep/health) | SKIP |
| config_roundtrip (INV-CFG-08, tiap kunci tulis→baca tiga jalur) | SKIP |
| INV-GATE-01 anti-residu | SKIP |

## ❌ VERDICT: MERAH — ADA GATE GAGAL. Lihat memory/BUG_REGISTRY.md. Perbaiki lalu jalankan ulang.

**Tingkatan:** `--quick` (statik ~7s) · default (~25s) · `--ci` (default + receipt JSON) · `--full` (+POC fase ~95s).

_Catatan: SKIP bukan PASS. Gate runtime harus dijalankan ulang saat backend hidup._
