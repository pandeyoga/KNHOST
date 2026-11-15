# Integrasi `main` (FIX-6…FIX-10) ke cabang blueprint — 15 Nov 2026, dikerjakan (menunggu tinjauan)

`main` di GitHub = `bfb3d0c`: 33 commit FIX-6…FIX-10 (audit WMS-RFID 9–10 Nov, keputusan pemilik 10 Nov) dari `cd6963a`.
Cabang blueprint `claude/nifty-carson-jjx3c8` = `cd6963a` + 309 commit. Penggabungan dikerjakan di cabang blueprint dengan
satu commit gabungan (`git merge --no-ff origin/main`, judul "R0 — gabung main (FIX-6…FIX-10)…"). **`main` tidak disentuh.**
Sesudah tinjauan, `main` bisa maju ke cabang ini tanpa bentrok (cabang ini sudah memuat `bfb3d0c`).

Status: **diimplementasikan, menunggu tinjauan** (bukan `verified`). Bacaan yang dipakai: `docs/finance/AUDIT_KEUANGAN_2026-11-13.md`
(retur/jurnal), laporan PK-27, PK-28, PK-32, KF-T6, KP-T4, PR-T2 di `docs/reviews/2026-11-13/hasil/`, laporan FIX-6…FIX-10 di
`docs/audit/2026-11-09-wms-rfid/hasil/`, `docs/rfid/KEPUTUSAN_GATE_RFID.md` (H7 — berkas RFID hanya tampilan, logika gerbang
tidak diubah).

## 1. Bentrok semantis — keputusan yang dikerjakan

| # | Berkas | Blueprint | FIX (main) | Dikerjakan |
|---|---|---|---|---|
| 1 | `services/purchase_return_service.py`, `gl_service.py`, `purchase_return_remedy.py` | PK-28 `ap_basis` + satu pintu `post_purchase_return` (+ nilai buku PK-27); KP-T5 Nota Debit per PT | FIX-6 D2: pilihan tolak QC (ganti barang / potong tagihan) + jurnal sendiri `post_purchase_return_grir` | **Satu pintu posting = PK-28.** `ap_basis` = `gr_ir` bila "ganti barang" (D2), selain itu aturan PK-28 (sudah ditagih → `hutang`, belum → `gr_ir`). `apply_on_approve` hanya mengurus AP & PO; langkah jurnalnya dibuang (`gl_mode` tinggal keterangan). `post_purchase_return_grir` tidak dibawa. Ganti barang tanpa Nota Debit; lainnya Nota Debit per PT. Blok AP umum dilewati untuk retur ber-pilihan (AP diurus `apply_on_approve`) → AP turun sekali. Status lewat tabel transisi FIX-6 (`purchase_return_doc_state`) |
| 2 | `services/return_roll_settlement_service.py` | PK-32 mesin nota tunggal `issue_settlement_note` | FIX-6 D5: balik karantina roll yang tidak kembali ke stok + nota kredit langsung | Pembalikan karantina FIX-6 (`return_intake_service.reverse`) + mesin nota PK-32; sisipan nota kredit langsung dibuang |
| 3 | `services/return_service.py` | PK-27: scrap menolkan biaya + riwayat biaya; batal scrap memulihkan | FIX-10: status lewat `roll_state.transition` | `roll_state.transition` dengan `extra_set` berisi kolom biaya PK-27; catatan `roll_cost_history` tetap. Tidak ada `inventory_rolls.update_one` status langsung |
| 4 | `services/inspection_service.py` | PR-T2/PR-T7: `role_in` dihapus | FIX-10 menambah `role_in` + `inspection_state` | Hanya `inspection_state`; impor `role_in` (tidak terpakai) dibuang |
| 5 | `services/makloon_order_service.py` | PK-18 `_post_step_gl` | FIX-9 `consume_for_issue(..., actor_name)` | Keduanya: kunci cadangan FIX-9 lalu jurnal langkah PK-18 |
| 6 | `routers/cycle_count.py` | KF-T6 `submitted_by_id`, KP-T4 `guard_door` | FIX-10 `cycle_count_state.transition` | Transisi FIX-10 dengan `submitted_by_id` di `set_fields`; `guard_door` tolak tetap |
| 7 | `services/vendor_bill_service.py` (**tergabung otomatis tanpa penanda bentrok**, ditemukan uji lapis A FIX-6) | PK-28: qty retur sebelum ditagih dikurangi lewat `returned_unbilled_map` (retur ber-dasar GR/IR) | FIX-6: qty retur "potong tagihan" dikurangi lewat `items.returned_qty` | Dikurangi **dua kali** (50 diterima − 20 diretur → boleh ditagih 10, seharusnya 30). Satu aturan = PK-28 (berlaku untuk semua retur beli, bukan hanya tolak QC); `returned_qty` FIX-6 tetap dicatat sebagai keterangan di PO. Retur "ganti barang" dikecualikan dari peta PK-28 (`received_qty` PO sudah turun lalu naik lagi oleh penerimaan pengganti; tagihan tetap penuh, D2) |
| 8 | Registri pengaturan & izin (tergabung otomatis) | KF-T3/KF-T4/KF-T8: rujukan konsumen harus menyebut kunci, label ≤ 45 huruf, indeks kunci layar; PR-T9 potret izin | FIX-7 lima kunci `ops.*` masa simpan log; FIX-6 `product.export` untuk MD | Empat kunci hari dirujuk ke berkas `services/log_retention.py` (dibaca lewat tabel `RULES`, bukan di badan `settings`); dua label dipendekkan; `configKeyIndex.json` dibangkitkan ulang; uji hitungan KF-T1 (+5) dan potret PR-T9 (MD `product.export`, keputusan pemilik 10 Nov) diperbarui |

## 2. Bentrok mekanis — digabung keduanya

`backend/indexes.py` (indeks AG-T1/AG-T4/PK-20 + `saved_views` FIX-8), `routers/dashboard.py` (WAC sekaligus FIX-7 + pagar izin
pesanan + `segs`), `gl_service.py` (`landed_cost_lines` + tanda tangan `post_landed_cost` PK-26), `ENTITY_REGISTRY.md`,
`docs/reviews/TRACKER.md` (lihat §3 butir P24), `scripts/gate.sh` (gate kedua sisi: `posting_coverage`, `cash_single_door`,
`roll_status_writer`), `scripts/guardrails/verify_atomic_claim.py` (daftar `REVIEWED` blueprint berkunci "METODE /path" + entri
FIX-6 `POST /inbound/tasks/{task_id}/inspection-request`; pola CAS/penutup klaim FIX-10 `_rs.transition`, `ccs.transition`,
`_ist.cas_filter`, `claimed=True`, `_pst.finish_claimed`; uji-diri versi blueprint), `frontend/src/styles/standard.css`,
`LocationScopeBar.jsx`, `approvalInboxData.js`, `IntercoReturnsPanel.jsx`, `IntercoView.jsx`, `InspectLineModal.jsx`,
`RfidGateMonitorView.jsx` (tampilan saja). Dibangkitkan ulang: `CODEBASE_MAP.md`, `access_builtin_fixture.json`,
`configKeyIndex.json`. Uji FIX-7 `fix7DaftarServer` disesuaikan ke kontrak PR-T7 (`loadInbox(perms)` hanya memanggil
kategori yang izinnya dipegang).

## 3. Temuan sampingan (dicatat, tidak diperbaiki di R0)

| Temuan | Asal | Usulan |
|---|---|---|
| Dua sistem lencana status: `StatusBadge`/`kn-badge` (FIX-8) dan `status-pill` (blueprint) | keduanya | R4: satukan ke satu komponen |
| Wewenang "bagikan / ubah tampilan bersama" dicek dari nama peran `admin` (`saved_view_service._is_admin`); berbagi ke `share.roles` memakai nama peran | FIX-8 | R4: izin baru (mis. `saved_view.share`, bawaan Admin) + migrasi — melanggar `02_STANDAR.md` §3 |
| Nomor P23 dipakai dua paket (FIX-6…10 di `main`, tanggal WIB di blueprint) | keduanya | Sudah: WIB dinomori ulang **P24** di `TRACKER.md` dan `UAT24-P23-TANGGAL-WIB.md` |
| `LocationScopeBar` diperbaiki dua kali untuk masalah yang sama | keduanya | Sudah: versi FIX-8 dipakai, aturan CSS blueprint dibuang |
| Dasbor FIX-7 memakai `role_in(role, COST_SAFE_ROLES)`; `COST_SAFE_ROLES` sudah turunan izin `costing.view` (PR-T2) | FIX-7 | Tidak diubah (pola sama dengan `strip_cost_fields`) |
| Retur beli dari tolak QC tidak membawa nilai buku roll (PK-27): roll sudah dipisah saat keputusan QC, `book_value` tidak terisi | sudah begitu sebelum R0 | Catat untuk R5/PK-27 lanjutan bila perlu |
| Rantai seed data acuan: `seed_demo_transaksi_kn.py` (5 skenario) dan `seed_p03_kn.py` gagal — sama persis dengan pemulihan sebelum R0 | sebelum R0 | Sudah di R3 |
| Uji FIX-7 `test_fix7_perf_sisa`: rencana kueri pagar gudang memilih indeks PT pada data acuan ini (indeks `warehouse_id+timestamp` ada); indeks `id` `store_credit_ledger` tidak dibuat karena koleksinya belum ada | data | Bergantung data, bukan kode |
| Uji lapis A KF-T6/KP-T4 memakai akun & nama dari `seed_realistic.py` (`manager.printing@`, "Dewi Rahayu", "Fajar Nugroho") yang tidak dibuat rantai seed | uji | R3: ikutkan ke rantai seed atau buat akun di fixture uji |

## 4. Uji dan bukti (pohon akhir, sebelum commit gabungan)

| Uji | Hasil |
|---|---|
| Penjaga: `verify_atomic_claim` (+uji-diri 64 kasus), `verify_posting_coverage` (+uji-diri), `verify_roll_status_writer` (+uji-diri), `verify_cash_single_door` (+uji-diri), `verify_role_gate_ui`, `verify_codebase_map` | semua hijau (0 pelanggaran) |
| Uji baru `backend/tests_mem/test_R0_integrasi_fix6.py` (7): ganti barang PO sudah ditagih → satu jurnal Dr 2-1150 / Cr 1-1300 neto, tanpa Nota Debit, AP tetap; potong tagihan belum ditagih → satu jurnal GR-IR + Nota Debit + AP turun bruto sekali; potong tagihan sudah ditagih → satu jurnal Dr 2-1100 bruto / Cr 1-1300 / Cr 1-1500, setujui ulang tetap satu; tidak ada pintu jurnal kedua; qty tertagih potong tagihan dikurangi sekali (30); ganti barang tetap penuh (50); scrap/batal scrap = biaya PK-27 + jejak status `roll_state` | 7 lulus; bukti-merah: aturan "ganti barang = GR-IR" disabotase → uji 1 merah; pengurangan ganda dikembalikan → 2 uji qty merah |
| `tests_mem` penuh | 2.334 lulus, 8 gagal (registri pengaturan/izin, §1 baris 8) → sesudah perbaikan 8 berkas terkait + uji R0: 579 lulus, 2 xfail |
| jest penuh | 1.157 lulus, 1 gagal (`fix7DaftarServer` LST-01/07, §2) → sesudah penyesuaian 4/4 lulus; 36 suite gagal dimuat = 35 garis dasar + `fix8StandarUi2` (baru dari `main`), sebab sama (`cmdk`/`@radix-ui`, lingkungan) |
| Lapis A FIX (MongoDB 7 asli, backend pohon gabungan): `test_fix6_keputusan_10nov`, `test_fix10_roll_state`, `test_fix9_makloon_lock`, `test_fix8_saved_views`, `test_fix7_lists`, `test_fix7_perf_sisa`, `test_fix7_data_scripts` | FIX-6 semua lulus sesudah §1 baris 7 (sebelumnya `test_d2_bill_cut_unbilled…` gagal 10 ≠ 30); FIX-7 skrip data 7 lulus (salinan DB `kainnusantara` sementara, dihapus sesudahnya); `test_fix7_perf_sisa` 2 gagal bergantung data (§3) |
| Lapis A blueprint terkait: KF-T6, KP-T4, KP-T5, PK-18, PK-27, PK-28, PK-32, PK-33, PR-T2, PR-T7 | lulus (KF-T6/KP-T4 dengan akun & nama sementara, dipulihkan sesudahnya); PR-T2/PR-T7 2 dilewati (data acuan tanpa peran kustom / permintaan sample) |
| Gate `--ci` sekali, dibandingkan per pelanggaran dengan `garis-dasar-gate/2026-11-15_gate_ci.log` | lihat §5 |

## 5. Gate

`gate.sh --ci` sekali pada pohon gabungan (MongoDB 7 asli, backend pohon gabungan). Log: `garis-dasar-gate/2026-11-15_R0_gate_ci.log`.

- Per status gate, dibanding garis dasar 15 Nov (`2026-11-15_gate_ci_receipt.md`): merah 39 → **38** (`guard:page_tabs`
  menjadi hijau), hijau 102 → **105** (termasuk dua gate baru `guard:roll_status_writer` + uji-dirinya dari FIX-10). Tidak
  ada gate yang berubah hijau → merah.
- Per pelanggaran (`bandingkan_pelanggaran_gate.py` terhadap `2026-11-15_gate_ci.log`): **1 baru, 3 hilang**.
  - Baru: `audit_sales_roles_ux` peran Finance, layar `goods-receipts` — baris yang **sudah merah** di garis dasar (panel
    mati: `/inbound/scan-label/stats`, `/lots/settings`, `/warehouses`) kini juga menyebut `/inbound/tasks`. Asal: kode
    "muat berikutnya" FIX-7 di `InboundScanInterface.jsx` membuat panggilan itu terbaca pemindai statis. Akar masalah
    sama (layar Penerimaan Finance memuat komponen pindai lama yang dijaga `wms.update`), perilaku tidak berubah → masuk R4.
  - Hilang: satu baris lama `finance` (diganti baris di atas), satu `guard:entity_label`, satu `guard:page_tabs`.
- Garis dasar `2026-11-15_gate_ci.log` sengaja **tidak** diganti (diganti sesudah R4, sesuai STATUS).

## 6. Belum dikerjakan / titik henti

- Skrip data produksi FIX-6/FIX-7 (`docs/audit/2026-11-09-wms-rfid/hasil/PANDUAN-SKRIP-DATA-PRODUKSI.md`) belum dicek ulang
  terhadap skema blueprint (mis. `ap_basis`, `book_value`, Nota Debit per PT) — wajib sebelum dijalankan pada data yang
  sudah memakai kode blueprint (H3: data nyata, oleh/atas izin pemilik).
- Server produksi masih `main` lama; memajukan `main` ke cabang ini dan deploy = keputusan pemilik sesudah tinjauan.
