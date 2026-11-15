# Perintah review — hasil blueprint + integrasi FIX-6…FIX-10 (15 Nov 2026)

Berkas ini adalah perintah lengkap untuk sesi review berikutnya. Sesi review tidak membawa riwayat chat sesi pelaksana,
jadi semua konteks yang dibutuhkan ada di sini atau dirujuk dari sini. Bahasa kerja: Bahasa Indonesia.

## 0. Prompt untuk ditempel di sesi review

```text
Anda reviewer untuk repo KNHOST (Kain Nusantara ERP). Baca docs/reviews/PERINTAH_REVIEW_2026-11-15.md seluruhnya, lalu
kerjakan SATU batch (mulai B0, lalu B1, B2, …) sampai definisi selesai di bagian "TUJUAN DAN DEFINISI SELESAI" terpenuhi:
`python3 scripts/review/periksa_selesai.py review <batch>` harus mencetak "HASIL: SELESAI". Jangan menyatakan selesai
sebelum itu. Tiap butir wajib dibuktikan sendiri (baca kode, jalankan uji, coba bantah) — laporan pelaksana bukan bukti.
Akhiri sesi dengan: `python3 scripts/review/periksa_selesai.py progres`, satu baris di docs/reviews/LOG_REVIEW.md, commit,
dan push ke cabang review/<tanggal hari ini> (bukan main). Jangan mengubah kode produksi, server VPS, atau data nyata.
```

## TUJUAN DAN DEFINISI SELESAI (wajib, berlaku di atas bagian lain)

### Tujuan

1. **Memutuskan, dengan bukti yang dijalankan sendiri, apakah setiap perbaikan benar-benar menutup temuannya di `HEAD`**
   — bukan apakah laporannya terdengar meyakinkan. Hasilnya satu putusan per butir: `verified`, `reopened`,
   `perlu_keputusan_pemilik`, atau `terhambat_lingkungan`.
2. **Mencari pintu kedua**: jalur lain di kode yang masih melakukan hal yang sama dengan cara lama (penyebab utama cacat di
   repo ini — lihat R0 §1 baris 7).
3. **Mencoba membantah** setiap perbaikan dengan kasus yang tidak diuji pelaksana.
4. **Meninggalkan jejak yang bisa dihitung**, sehingga pemilik dan pelaksana tahu persis apa yang sudah dicek, berapa baris
   kode dibaca, uji apa yang dijalankan, dan apa yang tersisa.

### Batch (kerjakan berurutan; satu sesi = satu batch sampai selesai)

| Batch | Isi | Butir | Berkas hasil |
|---|---|---|---|
| B0 | R0 — 8 keputusan integrasi + 17 fungsi yang diubah dua sisi (§4 A) | 9 | `hasil/validasi-R0.md` |
| B1 | Keuangan Kritis/Tinggi — kas, pembayaran, piutang & hutang (PK-05, PK-15, PK-17, PK-19, PK-31, PK-38) | 17 | `hasil/validasi-<UNIT>.md` |
| B2 | Keuangan Kritis/Tinggi — jurnal, periode, posting, laporan (18 unit) | 33 | idem |
| B3 | Keuangan Kritis/Tinggi — antar-PT, persediaan, retur, nota (PK-06, PK-26, PK-27, PK-28, PK-30, PK-32, PK-33) | 7 | idem |
| B4 | Riset modul Tinggi — CR-T3, KM-T1, PK-45, PM-T2, PM-T3, PY-T1, PY-T3 | 14 | idem |
| B5 | Konfigurasi & peran Tinggi (14 unit) | 23 | idem |
| B6 | Keuangan Sedang/Rendah | 77 | idem |
| B7 | Riset modul Sedang/Rendah | 32 | idem |
| B8 | Konfigurasi & peran Sedang/Rendah | 44 | idem |

Daftar ID persis tiap batch (dihitung dari tracker): `python3 scripts/review/periksa_selesai.py daftar B1`.
Berkas hasil ada di `docs/reviews/2026-11-13/hasil/`. Satu berkas per unit; satu bagian `## <ID> — <judul>` per baris tracker.

### Definisi selesai — per butir (diperiksa mesin oleh `periksa_selesai.py`)

Berkas `validasi-<UNIT>.md` dimulai dengan dua baris:
`Commit yang direview: <sha yang sudah di-push>` dan `Lingkungan: <MongoDB asli/tiruan, backend hidup?, data acuan?>`.
Tiap bagian `## <ID>` wajib berisi enam sub-bagian ini, dengan isi minimum:

| Sub-bagian | Isi minimum |
|---|---|
| `### Temuan asli` | Apa cacatnya, dengan rujukan `berkas:baris` di `cd6963a` (baca sendiri, jangan menyalin laporan) |
| `### Perbaikan yang diperiksa` | SHA commit unit; baris `Berkas dibaca:` berisi rentang `berkas.py:120-188` — **minimum 30 baris dari 2 berkas** per butir (kode perbaikan + pemanggil/pintu lain) |
| `### Pintu lain` | Perintah pencarian yang Anda jalankan (blok kode) untuk mencari jalur lain yang menulis hal yang sama, lalu `Kesimpulan:` |
| `### Uji yang dijalankan` | Perintah persis (blok kode) dan `Hasil: <n> lulus, <m> gagal` — uji pelaksana **dan** uji/skrip Anda sendiri bila perlu |
| `### Upaya membantah` | **Minimum 2** butir `- [kategori] <yang dicoba> Hasil: <yang terjadi>`; kategori: `ulang`, `bersamaan`, `sebagian`, `pt_lain`, `tanpa_izin`, `periode_tertutup`, `jurnal_gagal`, `koreksi`, `data_lama`, `batas_nilai`, `jalur_lain`, `layar` |
| `### Putusan` | `Putusan: verified \| reopened \| perlu_keputusan_pemilik \| terhambat_lingkungan` dan `Alasan:` ≥ 60 huruf yang menunjuk bukti (`berkas:baris` atau nama uji) |

Aturan putusan:
- `verified` hanya bila semua uji yang dijalankan lulus, tidak ada pintu kedua, dan kedua upaya membantah gagal
  membantah. Status tracker diubah menjadi `verified`.
- `reopened` bila ada cacat; tulis langkah reproduksi di `Alasan:`. Status tracker → `reopened`.
- `perlu_keputusan_pemilik` bila benar/salahnya bergantung keputusan bisnis. Status tracker → `pending_decision`, dan
  pertanyaannya ditulis di bagian itu.
- `terhambat_lingkungan` bila uji yang diperlukan tidak bisa dijalankan di lingkungan Anda. Status tracker **tidak**
  diubah. Membaca kode saja **tidak pernah** cukup untuk `verified`.

Untuk B0 (`validasi-R0.md`) bentuknya sama, dengan bagian `## Keputusan 1` … `## Keputusan 8` (sub-bagian pertama
`### Yang diputuskan`, putusan `benar | salah | perlu_keputusan_pemilik | terhambat_lingkungan`), ditambah bagian
`## Fungsi yang diubah dua sisi`: satu baris per fungsi (17 nama di §4 A) dengan `berkas:baris` dan penilaian
aman/bermasalah.

### Definisi selesai — per batch dan per sesi

1. `python3 scripts/review/periksa_selesai.py review <batch>` mencetak **HASIL: SELESAI** (kode keluar 0).
2. Status setiap baris batch di `docs/reviews/TRACKER.md` sesuai putusannya (pemeriksa mencocokkan).
3. `python3 scripts/review/periksa_selesai.py progres` dijalankan; `docs/reviews/PROGRES_REVIEW.md` ikut di-commit.
4. Satu baris ditambahkan ke `docs/reviews/LOG_REVIEW.md` (tanggal, commit yang direview, batch, butir selesai/total,
   baris kode dibaca, uji lulus/gagal, putusan per jenis, hambatan, batch berikutnya).
5. Commit dan push ke cabang `review/<YYYY-MM-DD>` (bukan `main`). Pelaksana membaca kemajuan dari cabang itu.
6. Bila sesi harus berhenti sebelum batch selesai, langkah 3–5 tetap dikerjakan dan alasan berhenti ditulis di log.

### Yang tidak dihitung sebagai bukti

- Isi laporan pelaksana (`hasil/<ID>.md`), pesan commit, atau STATUS — itu klaim yang sedang diuji.
- "Uji lulus" tanpa perintah dan keluaran yang Anda jalankan sendiri.
- Membaca dokumen tanpa membaca kode yang ditunjuk.
- Mengambil sampel sebagian butir lalu menyimpulkan seluruh batch.

### Lingkungan Anda berbeda dari lingkungan pelaksana

Siapkan lingkungan menurut §5 dan `docs/LOCAL_DEV.md`. Bila MongoDB asli tidak bisa dijalankan, uji lapis A dicatat
`terhambat_lingkungan`; uji lapis B (`backend/tests_mem`, database tiruan) tetap wajib. Catat apa yang tersedia di baris
`Lingkungan:`. Hambatan yang sudah diketahui ada di §6 — jangan dilaporkan sebagai temuan baru.

## 1. Peran, wewenang, dan batas

- Anda **reviewer**. Pelaksana (sesi Claude Code) paling jauh menetapkan `implemented_pending_review`; `verified` dan
  `reopened` **hanya** ditetapkan reviewer (`docs/reviews/README.md`). Saat ini belum ada satu pun baris `verified`.
- Yang diharapkan dari Anda: memeriksa apakah perbaikan benar-benar menutup temuan di kode `HEAD`, menjalankan ulang
  bukti, mencari regresi dan duplikasi, lalu menetapkan status per baris tracker dan menulis laporan validasi.
- Jangan memperbaiki kode di sesi review kecuali pemilik memintanya. Temuan baru ditulis sebagai paket review baru
  (lihat §7) supaya pelaksana bisa mengerjakannya dengan ID tetap.
- **Titik henti (STOP & ASK pemilik)**, dari `docs/blueprint/00_ATURAN_EKSEKUSI.md` §6:
  H2 server produksi / VPS · H3 data nyata (termasuk menjalankan skrip `--apply`) · H4 isi tabel peraturan (tarif pajak,
  akun) · H5 sakelar per PT · H7 logika gerbang RFID (baca `docs/rfid/KEPUTUSAN_GATE_RFID.md`) · H8 rahasia/kunci.
- Jangan mengubah `deploy/docker-compose.yml`, `deploy/Dockerfile.*`, `backend/pytest.ini`; jangan commit `backend/.env`,
  `frontend/.env`, atau `memory/GATE_RECEIPT.*`. Jangan menjalankan dua gate/POC bersamaan (beberapa POC mengubah
  pengaturan global sementara). Line ending LF.
- Isi paket review lama (`docs/reviews/<tanggal>/` di luar `hasil/`) adalah arsip — jangan diubah.

## 2. Keadaan repo saat perintah ini ditulis

| Hal | Nilai |
|---|---|
| `main` = cabang `claude/nifty-carson-jjx3c8` | sama (dimajukan fast-forward 15 Nov atas izin pemilik); catat SHA `HEAD` Anda sendiri |
| Dasar sebelum audit 13 Nov | `cd6963a` |
| Awal eksekusi blueprint | `fb6bc75` (13 Nov 19:16 UTC) |
| FIX-6…FIX-10 (audit WMS-RFID, keputusan pemilik 10 Nov) | `cd6963a..bfb3d0c` (33 commit, dulu di `main` sendiri) |
| Commit gabungan R0 (FIX-6…10 masuk blueprint) | `0f0ff4e` (+ `c5170d4`, `9173965`, `9783a8d`, `8946824` dokumen) |
| Unit blueprint | 97 `selesai`, 7 `tahan`: PK-03 (H3 cek data nyata), PK-04 (H2 cadangan), PK-34 (H2 replica set), PK-35 (H2/H3 uang bilangan bulat), PK-46 (H4 tabel PPh 21), PM-T5 (H8 VA/QRIS), TX-T3 (H8 Coretax) |
| Tracker (`docs/reviews/TRACKER.md`) | 316 `implemented_pending_review`, 6 `open` (milik unit tahan + ENV-03), 1 `pending_decision` (PY-03), 0 `verified` |
| Server VPS | belum memakai kode blueprint; tidak ada yang dijalankan di data nyata |

## 3. Bacaan wajib (urutan)

1. `AGENTS.md` dan `docs/KN_00_AGENT_QUICK_START.md` — aturan repo dan gate.
2. `docs/reviews/README.md` — protokol, arti status, templat laporan.
3. `docs/reviews/2026-11-13/README.md` — cara membaca tracker paket 13 Nov (kolom "Fase" = ID unit blueprint).
4. `docs/blueprint/README.md`, `00_ATURAN_EKSEKUSI.md` (putaran kerja, titik henti), `01_KEPUTUSAN.md` (keputusan pemilik),
   `02_STANDAR.md` (posting tahan-gagal, pengaturan bukan konstanta, izin bukan nama peran, layar, uji),
   `03_LINGKUNGAN_UJI.md` (lapis A MongoDB asli / lapis B database tiruan; §6 uji hemat).
5. `docs/blueprint/STATUS.md` — tabel unit (kolom "Titik henti" memuat skrip migrasi `--apply` yang menunggu pemilik),
   "Menunggu pemilik", "Jawaban pemilik 15 Nov 2026", "Rencana berikutnya" R0–R9.
6. `docs/blueprint/INTEGRASI_MAIN_FIX6-10.md` — R0: 8 keputusan penggabungan, temuan sampingan, uji, gate.
7. `docs/blueprint/EVALUASI_EKSEKUSI_2026-11-15.md` — perubahan sejak `fb6bc75` (§2), pelanggaran yang lolos gate (§4),
   relevansi uji & gate (§5), peta cakupan kode yang belum pernah diperiksa (§6), celah kredit Pesanan Khusus (§7),
   cara insentif sekarang (§8), temuan di luar cakupan unit (§9).
8. Sumber temuan: `docs/finance/AUDIT_KEUANGAN_2026-11-13.md` (139 temuan; bukti `bukti-2026-11-13/`; dianalisis di
   `cd6963a`), `docs/finance/rencana-2026-11-13/11_TEMUAN_TAMBAHAN.md`,
   `docs/audit/konfigurasi-peran-2026-11-13/AUDIT_KONFIGURASI_PERAN_2026-11-13.md`, dan untuk FIX:
   `docs/audit/2026-11-09-wms-rfid/KEPUTUSAN-KOORDINATOR.md` + `hasil/FIX-*.md`.
9. Laporan per unit: `docs/reviews/2026-11-13/hasil/<ID>.md`; spesifikasi unit: `docs/blueprint/unit/<ID>.md`.

## 4. Yang direview — urutan prioritas

### A. R0 — integrasi FIX-6…FIX-10 (paling berisiko, kerjakan dulu)

Dua implementasi berbeda untuk alur keuangan/stok yang sama bertemu saat `main` digabung. Pemilik menyetujui 8 keputusan
berikut (15 Nov); tugas Anda memastikan kode benar-benar melakukannya dan tidak ada jalur kedua yang tersisa.

| # | Keputusan | Berkas / fungsi yang dibaca | Yang dibuktikan |
|---|---|---|---|
| 1 | Retur beli dari tolak QC: satu pintu jurnal PK-28 (`gl_service.post_purchase_return`). Ganti barang → `ap_basis = gr_ir` (Dr 2-1150 / Cr 1-1300 neto, tanpa Nota Debit, AP tetap, PO dibuka lagi) **juga bila PO sudah ditagih**; potong tagihan belum ditagih → `gr_ir` + Nota Debit; potong tagihan sudah ditagih → `hutang` (Dr 2-1100 bruto / Cr 1-1300 / Cr 1-1500) | `purchase_return_service._finalize_supplier_return_financials`, `purchase_return_remedy.apply_on_approve`, `gl_service.purchase_return_basis`, `gl_service.post_purchase_return` | tepat satu jurnal `purchase_return` per retur, setujui ulang tidak menambah; AP PO turun sekali (blok AP umum dilewati bila ada `remedy`); `post_purchase_return_grir` tidak ada; koreksi (`reverse_settlement` + `purchase_return_remedy.undo`) membalik jurnal, AP, PO, roll |
| 2 | Qty yang boleh ditagih sesudah retur: satu aturan PK-28 (`returned_unbilled_map`, retur ber-dasar GR/IR); `items.returned_qty` FIX-6 hanya keterangan; retur ganti barang dikecualikan dari peta | `vendor_bill_service.evaluate_match`, `build_billing_context`, `returned_unbilled_map` | 50 diterima − 20 diretur = 30 boleh ditagih (dulu 10); ganti barang boleh ditagih penuh sesudah pengganti diterima; **tanyakan**: potong tagihan pada PO yang sudah sebagian ditagih (dasar `hutang`) tidak mengurangi qty tertagih — diselesaikan lewat Nota Debit; benarkah itu yang diinginkan? |
| 3 | Nota kredit retur jual per roll: satu mesin `issue_settlement_note` (PK-32); pembalikan karantina FIX-6 D5 tetap | `return_roll_settlement_service._apply`, `reverse_all`; `return_intake_service.reverse` | tidak ada `credit_notes.insert_one` di luar mesin nota; satu nota per penyelesaian; roll yang tidak kembali ke stok dibalik dari karantina |
| 4 | Scrap / batal scrap retur jual: status lewat `roll_state.transition` (FIX-10) dengan kolom biaya PK-27 di `extra_set`; riwayat biaya tetap | `return_service.release_quarantine`, `reverse_writeoff` | status_history roll bertambah; `unit_cost` 0 + `writeoff_*` tersimpan; batal scrap memulihkan; satu jurnal hapus-buku + satu pembalik |
| 5 | Inspeksi: `inspection_state` FIX-10 tanpa `role_in` | `inspection_service.finish`, `inspect_line` | tidak ada cek nama peran |
| 6 | Makloon: kunci cadangan FIX-9 + jurnal langkah PK-18 | `makloon_order_service.issue_step` | keduanya jalan; jurnal langkah tidak hilang |
| 7 | Stock opname: `cycle_count_state.transition` FIX-10 + `submitted_by_id` (KF-T6) + `guard_door` (KP-T4) | `routers/cycle_count.py` submit/approve/reject | kontrol dua orang dan aturan persetujuan masih memblokir |
| 8 | Registri pengaturan/izin: 5 kunci `ops.*` masa simpan log (FIX-7) dirapikan; MD `product.export` (keputusan 10 Nov) | `config_catalog_retention.py`, `permissions_config.py`, `configKeyIndex.json` | kesehatan registri hijau; izin MD bertambah lewat `sync_permission_modules` di data tersimpan |

Periksa juga yang **tergabung otomatis tanpa penanda bentrok** — dari sini duplikasi #2 lolos:

```bash
comm -12 <(git diff --name-only cd6963a 9dd7dbb | sort) <(git diff --name-only cd6963a bfb3d0c | sort)
```

(`9dd7dbb` = ujung cabang blueprint sebelum R0, `bfb3d0c` = ujung FIX-10; hasilnya 80 berkas diubah dua sisi, 22 di
antaranya bentrok bertanda.)

Fungsi yang diubah **kedua sisi** (selain baris tabel di atas): `routers/purchase_orders._create_po_core`,
`routers/sales_returns.submit_return`, `services/inbound_complete_service.complete_task`,
`putaway_arrival_service.close_remaining`, `rnd_sample_service.issue_material`, `roll_service._make_roll` /
`confirm_cut` / `reserve_rolls_for_transfer`, `sales_order_helpers.assert_roll_rounding`,
`scheduler_service._supplier_deadline_job`, `so_line_cancel_service.cancel_line`, `transfer_receipt_service.resolve`,
`return_service._restock_returned_items` / `settle_return` / `reverse_settlement`, `server.lifespan`,
`config_registry.covers`. Pelaksana menilai hunk FIX di sana bersifat tambahan; nilai ulang secara mandiri.

Temuan sampingan R0 yang sudah dicatat (bukan temuan baru): dua sistem lencana status (`StatusBadge`/`kn-badge` FIX-8 vs
`status-pill` blueprint); wewenang bagikan/ubah "tampilan tersimpan" bersama dicek dari nama peran `admin`
(`saved_view_service._is_admin`, FIX-8, melanggar `02_STANDAR.md` §3); retur tolak QC tidak membawa nilai buku roll
PK-27 (sudah begitu sebelum R0); paket UAT tanggal WIB dinomori ulang P24 (P23 dipakai FIX-6…10).

### B. Unit keuangan (jurnal, buku pembantu, antar-PT, tutup buku, persediaan ↔ jurnal)

Mulai dari temuan berkeparahan Kritis/Tinggi di tracker bagian "Audit keuangan — paket 2026-11-13" (mis. IC-01/PK-06,
SL-01/PK-05, GL-01/PK-10, GL-02/PK-18, GL-04/PK-11, SL-03/SL-04/PK-15, SL-05/SL-06/PK-19, IC-02/PK-30, IV-*/PK-26–PK-29,
PK-32). Untuk tiap baris: baca temuan asli (berkas:baris di `cd6963a`), lihat perubahan di commit unit, jalankan uji
"bukti merah" yang disebut laporan unit di kode lama bila perlu (`git worktree add /tmp/lama cd6963a`), lalu uji di
`HEAD`. Penjaga terkait: `verify_posting_coverage` (INV-POST-01), `verify_cash_single_door` (INV-CASH-01),
`verify_atomic_claim` (INV-ATOMIC-01).

### C. Izin dan pengaturan

Unit PR-T*, KF-T*, KP-T*: wewenang dari izin (bukan nama peran), nilai aturan bisnis dari pengaturan (bukan konstanta),
kontrol dua orang, Aturan Persetujuan. Dasar: `docs/audit/konfigurasi-peran-2026-11-13/` (skrip di `bukti/`). Penjaga:
`verify_role_gate_ui`, `verify_permission_checked`, `config_wiring`, `config_roundtrip`, `tests_mem/sapuan_izin.py`.

### D. Pelanggaran baru yang lolos gate

Gate dulu dinilai per status, sehingga pelanggaran baru di gate yang sudah merah lolos. Daftar:
`docs/blueprint/STATUS.md` baris "Pelanggaran baru yang lolos gate" (approval_queues +7, numeric_bounds +2, ref_unlink +2,
entity_isolation +1, sales_roles_ux +12, POC E-7 +6, qty_dual +1) dan R0 §5 (+1 `audit_sales_roles_ux` Finance di
Penerimaan, dari FIX-7). Nilai: mana yang cacat nyata, mana tuduhan palsu penjaga. Jangan "memperbaiki" dengan
melonggarkan penjaga.

### E. Kode yang belum pernah diaudit

±22 % baris `backend/services` dan ±44 % baris `.jsx` tidak pernah diaudit maupun disentuh blueprint
(`EVALUASI_EKSEKUSI_2026-11-15.md` §6; `python3 scripts/blueprint/peta_cakupan_audit.py`). Ambil sampel di modul yang
menyentuh uang atau stok lebih dulu; laporkan sebagai temuan baru (§7), bukan sebagai kegagalan unit.

### F. Relevansi uji dan gate

`EVALUASI_EKSEKUSI_2026-11-15.md` §5: 16 POC merah, ±403 uji lama di `backend/tests/`, 35–36 suite jest tidak termuat.
Beri rekomendasi untuk R3 (perbarui / arsipkan / masukkan gate).

## 5. Cara menguji

Lingkungan lokal: `docs/LOCAL_DEV.md`. Ringkas:

```bash
docker compose -f docker-compose.dev.yml up -d
```

```bash
bash scripts/dev_restore_demo.sh
```

Login demo: `admin@kainnusantara.id` / `demo12345` (semua akun seed memakai sandi yang sama). Skrip Python dijalankan di
dalam container backend (`docker compose -f docker-compose.dev.yml exec backend python /app/scripts/<skrip>.py`).

| Uji | Perintah | Hasil pelaksana (15 Nov, pohon `0f0ff4e`) |
|---|---|---|
| Lapis B (database tiruan, aplikasi utuh) | `cd backend && python -m pytest tests_mem` | 2.344 lulus, 2 dilewati, 2 xfail |
| Uji R0 | `cd backend && python -m pytest tests_mem/test_R0_integrasi_fix6.py -n 0` | 7 lulus (bukti-merah di laporan R0) |
| jest | `cd frontend && CI=true TZ=Asia/Jakarta npx craco test --watchAll=false` | semua yang termuat lulus; 36 suite gagal dimuat (`cmdk`/`@radix-ui`) |
| Lapis A (MongoDB 7 asli + backend hidup) | `cd backend && python -m pytest -n0 tests/test_fix6_keputusan_10nov.py tests/test_fix10_roll_state.py tests/test_fix9_makloon_lock.py tests/test_bp_PK28_kliring_bersamaan_mongo.py …` | lulus kecuali 2 uji indeks FIX-7 (bergantung data, §6) |
| Gate | `bash scripts/gate.sh --quick` atau `--ci` (sekali per putaran, di latar) | `--ci`: merah 38, hijau 105 (garis dasar 39/102) |
| Banding per pelanggaran | `python3 scripts/blueprint/bandingkan_pelanggaran_gate.py docs/blueprint/garis-dasar-gate/2026-11-15_gate_ci.log <log_baru>` | 1 baru (§4 D), 3 hilang; log R0: `garis-dasar-gate/2026-11-15_R0_gate_ci.log` |

Garis dasar sebelum blueprint: `docs/reviews/2026-11-13/garis-dasar/` (13 Nov). Garis dasar akhir eksekusi:
`docs/blueprint/garis-dasar-gate/2026-11-15_*` (sengaja belum diganti sampai R4).

## 6. Hambatan lingkungan yang sudah diketahui (bukan temuan baru)

- jest: 36 suite gagal dimuat karena `cmdk` → `@radix-ui/primitive/is-development` tidak ditemukan (35 garis dasar +
  `fix8StandarUi2` dari `main`).
- Rantai seed data acuan: `seed_demo_transaksi_kn.py` (5 skenario: QC 4-point wajib SPK terpisah, ambil wajib pindai,
  blok kredit) dan `seed_p03_kn.py` (gudang tujuan nonaktif) gagal — sudah begitu sebelum R0; masuk R3.
- Uji lapis A KF-T6/KP-T4 butuh akun `manager.printing@kainnusantara.id` dan nama "Dewi Rahayu"/"Fajar Nugroho" dari
  `seed_realistic.py` (tidak termasuk rantai seed) → dilewati atau gagal karena nama, bukan perilaku.
- `tests/test_fix7_data_scripts.py` butuh salinan data acuan bernama DB `kainnusantara`
  (`mongodump --db test_database --archive | mongorestore --archive --nsFrom 'test_database.*' --nsTo 'kainnusantara.*'`,
  hapus sesudahnya).
- `tests/test_fix7_perf_sisa.py`: rencana kueri pagar gudang dan indeks `id` `store_credit_ledger` bergantung isi data;
  indeks yang dibuat saat start hilang bila koleksi di-drop oleh seed sesudah backend menyala → nyalakan ulang backend
  sesudah pemulihan data.

## 7. Keluaran yang diminta

1. Per unit: `docs/reviews/2026-11-13/hasil/validasi-<UNIT>.md` dengan satu bagian `## <ID>` per baris tracker, bentuk
   dan isi minimum menurut "TUJUAN DAN DEFINISI SELESAI"; status di `TRACKER.md` sesuai putusan.
2. R0: `docs/reviews/2026-11-13/hasil/validasi-R0.md` — `## Keputusan 1` … `## Keputusan 8` + `## Fungsi yang diubah dua sisi`.
3. Temuan baru: paket baru `docs/reviews/<tanggal review>/` (README + laporan) dengan ID tetap, didaftarkan di
   `TRACKER.md` berstatus `open`; sebut lensa (keuangan, stok, izin, UI, data) dan berkas:baris di `HEAD`.
4. Tiap akhir sesi: `periksa_selesai.py progres`, baris `LOG_REVIEW.md`, commit, push ke `review/<YYYY-MM-DD>`.
5. Ringkasan untuk pemilik (Bahasa Indonesia, singkat): apa yang aman dipasang ke VPS, skrip migrasi `--apply` mana
   yang wajib dan urutannya (kolom "Titik henti" STATUS + `docs/audit/2026-11-09-wms-rfid/hasil/PANDUAN-SKRIP-DATA-PRODUKSI.md`),
   apa yang harus diperbaiki dulu, dan keputusan apa yang ditunggu dari pemilik.

## 8. Keputusan pemilik yang sudah final (jangan dibuka ulang tanpa bukti cacat)

- 8 keputusan R0 (§4 A) — disetujui 15 Nov.
- Keputusan pemilik 10 Nov untuk FIX-6 (D2 ganti barang / potong tagihan, D5 retur masuk stok saat dipindai, D9 GRN per
  PT, minta inspeksi, izin ekspor MD) — `docs/audit/2026-11-09-wms-rfid/KEPUTUSAN-KOORDINATOR.md`.
- Keputusan blueprint `docs/blueprint/01_KEPUTUSAN.md` dan tabel "Jawaban pemilik 15 Nov 2026" di STATUS (21 jawaban;
  dicatat, sebagian besar belum dikerjakan — jangan dinilai sebagai kekurangan unit).
- Fakta lapangan RFID dan K-RFID-01…10: `docs/rfid/KEPUTUSAN_GATE_RFID.md` (logika gerbang = H7).

Bila Anda menemukan bukti bahwa salah satu keputusan di atas menimbulkan cacat (jurnal salah, saldo tidak cocok, celah
izin), laporkan dengan bukti dan tandai "perlu keputusan pemilik"; jangan mengubah keputusannya sendiri.
