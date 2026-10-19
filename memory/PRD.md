# ERP Kain Nusantara (KNHOST) — PRD ringkas
Repo: github.com/pandeyoga/KNHOST (main). Stack: FastAPI + MongoDB + React (bundle statis, rebuild `bash scripts/rebuild_frontend.sh`).
Paket plan: docs/development/gelombang-lanjutan-pasca-p05-2026-10-16 (BACKLOG.json = SSOT, validator `scripts/validate_package.py`).

## Original problem statement (2026-10-19E)
"saya ingin anda lanjutkan development dari repo ini https://github.com/pandeyoga/KNHOST sebelumnya development berhenti disini [handoff sesi D: keputusan CUT-01 & GL-01 dicatat] ... di setiap akhir fasenya commit dan push ke github, jalankan scrip yang sudah ada" + jawaban owner: CUT-02 bisa dikonfigurasi default MD; CUT-03 BS bukan ROLL, KG atau yard menyesuaikan; CUT-04 setelah QC; CUT-05 surat jalan baru dengan referensi SJ dan SO original; GL-02 pakai yang sudah ada; GL-03 ketika awal pengiriman; GL-04 dipilih finance, semua tipe pembayaran; GL-05 customer ambil sendiri / armada KN (free atau customer bayar + nominal) / pihak ketiga (ditanggung KN atau customer bayar sendiri); GL-06 bisa dikonfigurasi; GL-07 bisa dipilih ketika mengirim; GL-08 finance, tanpa persetujuan kedua, hanya jurnal baru. ACC-KP-01: Sales boleh lihat saja.

## Architecture
FastAPI routers/services, MongoDB `test_database`, React feature folders, static FE bundle. Personas: admin, manager, sales, sales_admin, md, md_quality, warehouse, finance, driver.
GL-01: registri `services/gl_mapping_registry.py` (54 kebutuhan) → koleksi `gl_account_mappings` (+`gl_account_mapping_history`) → resolver `gl_mapping_service` (PT → global → bawaan); `_insert_entry` meng-remap baris jurnal otomatis; pembaca saldo memakai `known_codes`.

## Core requirements (static)
- Semua akun posting otomatis dapat dikonfigurasi per modul, Global/PT, alasan wajib, riwayat, berlaku ke jurnal baru.
- Ongkir retur dijurnal sesuai cara kirim & penanggung; cutloss memecah roll fisik dengan pilihan BS/Dibuang.

## Implemented
- 2026-10-19 (sesi B/C/D): lihat evidence/HANDOFF_SESI_2026-10-19B/C/D.md.
- 2026-10-19 (sesi E): Fase A registri+resolver+API Pemetaan Akun; Fase B UI `?view=gl-account-mappings` (Pengaturan → Keuangan); Fase C pembaca saldo (suspense, piutang denda, uang muka, selisih bayar, persediaan, AR aging) memakai akun pemetaan; Fase D jurnal ongkir retur (cara kirim, akun bayar Finance, PT pembeban, PPN via `returns.logistics_vat_enabled`, jurnal balik saat ubah/tolak); Fase E pemecahan roll cutloss (posisi cacat, BS/Dibuang oleh peran `returns.cutloss_treatment_roles`, pratinjau, SJ potongan baik merujuk SJ & SO asal); Fase F uji (iteration_244: 100%), ACC-KP-01, filter `?stage=` produk, judul/qty kartu tugas gudang Meja Saya. Detail: evidence/HANDOFF_SESI_2026-10-19E.md.

## Backlog
- P0: keputusan pending DATA-01, DES-02..04, HW-01/02, HR-01, UAT-01.
- P1: tagihan (invoice) terpisah untuk piutang ongkir customer; SJ potongan baik cutloss masuk alur dispatch logistik (armada/ekspedisi); consolidation/interco_margin masih membaca kode akun tetap; duplikasi D1–D8 (butuh persetujuan).
- P2: review & validasi terpisah (status validated butuh reviewer + owner).

## Next tasks
- Persetujuan D1–D8 lalu penggabungan duplikasi; UAT pemetaan akun oleh Finance.
