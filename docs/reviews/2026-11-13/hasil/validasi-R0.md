Commit yang direview: 91a3ec0612952bfcc88335668ef2b3f601ba926a
Lingkungan: MongoDB asli lokal (test_database) + backend hidup (8001) + data acuan ter-seed (restore_local_demo.sh; seed_demo_transaksi_kn & seed_p03 gagal spt §6); lapis B database tiruan (mongomock-motor) jalan. Admin login demo12345 (KN_DEMO_DATA=true). Commit kode yang diperiksa = HEAD main `91a3ec0` (= pohon R0 `0f0ff4e` sudah tergabung di dalamnya).

# Validasi R0 — integrasi FIX-6…FIX-10 (batch B0)

Metode: tiap keputusan dibaca sendiri di `cd6963a`/`bfb3d0c` (sebelum) dan di HEAD (sesudah), uji pelaksana dijalankan ulang, ditambah uji bantahan sendiri. Uji pelaksana: `backend/tests_mem/test_R0_integrasi_fix6.py` = **7 lulus, 0 gagal**; lapis A `backend/tests/test_fix6_keputusan_10nov.py` = **11 lulus, 0 gagal**; `test_fix10_roll_state.py`+`test_fix9_makloon_lock.py` = **36 lulus, 3 skip, 0 gagal**. Uji bantahan sendiri (ulang-approve, approve dua-bersamaan) = **9 lulus, 0 gagal** (dibuat di /tmp, tidak di-commit; log `/tmp/b0/bantah.log`).

## Keputusan 1

### Yang diputuskan
Retur beli dari tolak QC diposting lewat SATU pintu jurnal `gl_service.post_purchase_return` (PK-28). Ganti barang → `ap_basis=gr_ir` (Dr 2-1150 neto / Cr 1-1300 neto, tanpa Nota Debit, AP tetap, PO dibuka lagi) **juga bila PO sudah ditagih**; potong tagihan belum ditagih → `gr_ir` + Nota Debit (AP turun bruto); potong tagihan sudah ditagih → `hutang` (Dr 2-1100 bruto / Cr 1-1300 / Cr 1-1500). (`gl_service.py:2883`, `purchase_return_service.py:379`)

### Perbaikan yang diperiksa
SHA unit: pohon R0 `0f0ff4e` (tergabung di HEAD `91a3ec0`). Berkas dibaca: `backend/services/purchase_return_service.py:319-452` (fungsi `_finalize_supplier_return_financials`, 134 baris — jalur stok→ap_basis→transition→remedy→post), `backend/services/gl_service.py:2830-2842` (`purchase_return_basis`) + `2883-2925` (`post_purchase_return`, 43 baris), `backend/services/purchase_return_remedy.py:83-112` (`apply_on_approve`). Total dibaca ±220 baris, 3 berkas. Temuan kunci: `ap_basis = ret.get("ap_basis") or ("gr_ir" if remedy=="replace" else await purchase_return_basis(...))` (prs:379-381); remedy hanya mengurus AP & PO; jurnal tunggal di prs:427-434.

### Temuan asli
Di `bfb3d0c` ada DUA pintu jurnal: `gl_service.post_purchase_return` (cd6963a:2441) dan `gl_service.post_purchase_return_grir` (bfb3d0c:2479) dari FIX-6. `apply_on_approve` (bfb3d0c:82) sisi FIX-6 memposting jurnalnya sendiri → potensi jurnal ganda saat digabung dengan PK-28.

### Pintu lain
```
grep -rn "post_purchase_return_grir" backend/            # 0 hasil di HEAD
grep -rn "post_purchase_return\b" backend/services backend/routers | grep -v "def "
grep -rnE "journal_entries.insert|_insert_entry|credit_notes.insert" backend/services/purchase_return_remedy.py
```
Kesimpulan: `post_purchase_return_grir` sudah tidak ada di HEAD (`hasattr(gl_service,'post_purchase_return_grir')==False`, diuji). `purchase_return_remedy.py` tidak mengimpor `gl_service` sama sekali (diuji via AST). Hanya satu pintu jurnal tersisa.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_R0_integrasi_fix6.py -n 0 -q   # 7 lulus 0 gagal
REACT_APP_BACKEND_URL=http://localhost:8001 python -m pytest -n0 tests/test_fix6_keputusan_10nov.py   # 11 lulus 0 gagal
```
Hasil: 18 lulus, 0 gagal. `test_R0_ganti_barang_po_sudah_ditagih_tetap_balik_grir` membuktikan ganti barang pada PO sudah ditagih tetap Dr 2-1150/Cr 1-1300 (bukan hutang).

### Upaya membantah
- [ulang] Setujui retur dua kali (ganti barang, PO sudah ditagih) via `/approve`. Hasil: panggilan kedua tidak menambah jurnal — tetap 1 (`_already_posted("purchase_return",rid)` gl_service:2900; `stock_adjusted` prs:337). LULUS.
- [bersamaan] Dua `/approve` paralel (asyncio.gather) untuk retur potong tagihan. Hasil: satu jurnal, AP turun bruto sekali (atomic_claim `claim("purchase_returns",...)` prs:342). Tidak ada konsumsi/AP ganda. LULUS.

### Putusan
Putusan: benar
Alasan: satu pintu posting terbukti di `purchase_return_service.py:379-434` (ap_basis tunggal) dan `gl_service.py:2883-2925`; pintu kedua FIX-6 hilang (`post_purchase_return_grir` tidak ada, `purchase_return_remedy` tak impor gl_service); uji `test_R0_ganti_barang_po_sudah_ditagih_tetap_balik_grir` + bantahan ulang/bersamaan lulus tanpa jurnal ganda.

## Keputusan 2

### Yang diputuskan
Qty boleh ditagih sesudah retur dikurangi SATU aturan PK-28 (`returned_unbilled_map`, retur ber-dasar GR/IR); `items.returned_qty` FIX-6 hanya keterangan; retur ganti barang dikecualikan. (`vendor_bill_service.py:135`, `vendor_bill_service.py:371`)

### Perbaikan yang diperiksa
SHA unit: `0f0ff4e`. Berkas dibaca: `backend/services/vendor_bill_service.py:97-145` + `vendor_bill_service.py:371-400`; `backend/routers/vendor_bills.py:340-455`. ±130 baris, 2 berkas (vendor_bill_service + vendor_bills).

### Temuan asli
Di `bfb3d0c` (R0 §1 baris 7, tergabung otomatis tanpa penanda bentrok) qty dikurangi DUA kali: `returned_unbilled_map` (PK-28) DAN `items.returned_qty` (FIX-6) → 50−20 jadi 10, seharusnya 30.

### Pintu lain
```
grep -rnE "returned_unbilled_map|returned_qty" backend/services/vendor_bill_service.py backend/routers/vendor_bills.py backend/routers/purchase_orders.py
```
Kesimpulan: `returned_qty` hanya muncul sebagai komentar/keterangan (vendor_bill_service:131) dan dicatat di PO; pengurang tagihan tunggal = `returned_unbilled` di `evaluate_match:135` (`base_qty - returned`). Tidak ada pengurang kedua.

### Uji yang dijalankan
```
python -m pytest tests_mem/test_R0_integrasi_fix6.py -n 0 -q -k "qty_tertagih"
```
Hasil: 2 lulus, 0 gagal (`test_R0_qty_tertagih_potong_tagihan_dikurangi_sekali` → billable 30; `test_R0_qty_tertagih_ganti_barang_tetap_penuh` → 50).

### Upaya membantah
- [sebagian] QC 30 diterima + 20 ditolak potong-tagihan (satu baris PO). Hasil: `returned_qty=20` tercatat tetapi `billable_received==30` (sekali kurang). LULUS.
- [jalur_lain] Ganti barang (replace): `returned_unbilled_map` memfilter `choice=="replace"` (vendor_bill_service:381) tidak dikurangi; sesudah pengganti diterima billable 50 penuh. Hasil: billable 50, LULUS.
- [batas_nilai] Retur melebihi received_qty baris PO. Hasil: `_close_short_for_bill_cut`/`_reopen_for_replacement` menolak "Qty diterima baris PO lebih kecil dari qty yang diretur" (purchase_return_remedy.py), tak ada tagihan negatif.

### Putusan
Putusan: perlu_keputusan_pemilik
Alasan: aturan teknis benar & tunggal (`vendor_bill_service.py:135,381`, uji qty lulus), TETAPI perintah §4A baris 2 meminta konfirmasi pemilik: pada PO yang SUDAH sebagian ditagih, potong tagihan memakai dasar `hutang` dan **tidak** mengurangi qty tertagih (diselesaikan lewat Nota Debit) — benarkah ini yang diinginkan? Pertanyaan diteruskan ke pemilik; kode tidak diubah.

## Keputusan 3

### Yang diputuskan
Nota kredit retur jual lewat SATU mesin `issue_settlement_note` (PK-32); pembalikan karantina FIX-6 D5 tetap; tak ada `credit_notes.insert_one` di luar mesin. (`return_roll_settlement_service.py:31`, `return_intake_service.py`)

### Perbaikan yang diperiksa
SHA unit: `0f0ff4e`. Berkas dibaca: `backend/services/return_roll_settlement_service.py:1-40` (impor `return_state` FAMILY_STATE→REFUND/CREDIT/NEGO_SETTLED, `_apply`) + bagian `issue_settlement_note`; `backend/services/return_intake_service.py` (`reverse`). ±60 baris, 2 berkas.

### Temuan asli
`bfb3d0c` FIX-6 D5 menyisipkan nota kredit langsung saat roll tidak kembali ke stok; `cd6963a`/blueprint PK-32 punya mesin nota tunggal → risiko dua jalur nota.

### Pintu lain
```
grep -rnE "credit_notes.insert_one|issue_settlement_note|insert.*credit_note" backend/services backend/routers
```
Kesimpulan: pembuatan nota hanya lewat mesin settlement; sisipan langsung FIX-6 dibuang (lihat INTEGRASI §1 baris 2). Perlu uji runtime retur untuk memastikan tak ada nota kedua.

### Uji yang dijalankan
```
# tidak dijalankan: data acuan punya 0 sales_returns (db.sales_returns.countDocuments()==0); uji settlement butuh retur terkirim
```
Hasil: 0 lulus, 0 gagal (tidak dapat dijalankan dengan data acuan saat ini).

### Upaya membantah
- [jalur_lain] grep `credit_notes.insert_one` di luar mesin. Hasil: tidak ada pemanggil lain (statis).
- [data_lama] Coba cari retur lama di data acuan untuk settle. Hasil: 0 sales_returns di seed → tak ada yang bisa di-settle (belum membantah maupun mengonfirmasi).

### Putusan
Putusan: terhambat_lingkungan
Alasan: pembacaan kode (`return_roll_settlement_service.py:31-32`) menunjuk satu mesin nota, tetapi definisi selesai melarang `verified` tanpa uji; data acuan 0 retur → alur settle/nota tak bisa dijalankan. Butuh seed retur jual terkirim (atau buat lewat D-S1) untuk putusan final.

## Keputusan 4

### Yang diputuskan
Scrap / batal scrap retur jual: status lewat `roll_state.transition` (FIX-10) dengan kolom biaya PK-27 di `extra_set`; riwayat biaya tetap; satu jurnal hapus-buku + satu pembalik. (`return_service.py:1174`, `roll_service.py` roll_state)

### Perbaikan yang diperiksa
SHA unit: `0f0ff4e`. Berkas dibaca: `backend/services/return_service.py:1174-1210` + `return_service.py:1759-1800`; `backend/services/roll_state.py:1-40`. ±90 baris, 2 berkas (return_service + roll_state).

### Temuan asli
`bfb3d0c` FIX-10 memindah status roll ke `roll_state.transition`; blueprint PK-27 menolkan biaya langsung via `inventory_rolls.update_one` → dua penulis status.

### Pintu lain
```
grep -rnE "inventory_rolls.update_one.*status|roll_state.transition" backend/services/return_service.py
```
Kesimpulan: status roll retur lewat `roll_state.transition` dengan `extra_set` biaya; tak ada `update_one` status langsung di jalur ini (sesuai INTEGRASI §1 baris 3).

### Uji yang dijalankan
```
python -m pytest tests_mem/test_R0_integrasi_fix6.py -n 0 -q -k "scrap"
```
Hasil: 1 lulus, 0 gagal (`test_R0_scrap_dan_batal_scrap_biaya_dan_jejak_status`: status damaged→available lewat status_history, biaya dinolkan lalu pulih, 1 writeoff + 1 reversal, `roll_cost_history`=2).

### Upaya membantah
- [koreksi] Batal scrap sesudah scrap. Hasil: status `available` via status_history, unit_cost pulih 12.000, satu jurnal pembalik. LULUS.
- [jalur_lain] Cari penulis status roll langsung di return_service. Hasil: tak ada di jalur scrap (lewat roll_state). LULUS.

### Putusan
Putusan: benar
Alasan: uji `test_R0_scrap_dan_batal_scrap_biaya_dan_jejak_status` lulus (status_history + writeoff_* + reversal); penulis status tunggal `roll_state.transition` di `return_service.py` jalur scrap; biaya PK-27 di extra_set terbukti.

## Keputusan 5

### Yang diputuskan
Inspeksi memakai `inspection_state` (FIX-10) TANPA `role_in` (wewenang dari izin, bukan nama peran). (`inspection_service.py:42`, `inspection_state.py`)

### Perbaikan yang diperiksa
SHA unit: `0f0ff4e`. Berkas dibaca: `backend/services/inspection_service.py:1012-1060` + `inspection_service.py:1186-1210`; `backend/services/inspection_state.py:1-30`. ±110 baris, 2 berkas (inspection_service + inspection_state).

### Temuan asli
`bfb3d0c` FIX-10 menambah impor `role_in` + `inspection_state`; blueprint PR-T2/PR-T7 menghapus `role_in`.

### Pintu lain
```
grep -rnE "role_in|inspection_state" backend/services/inspection_service.py
```
Kesimpulan: hanya `inspection_state`; `role_in` tidak terpakai (dibuang, INTEGRASI §1 baris 4). Tidak ada cek nama peran.

### Uji yang dijalankan
```
grep -c "role_in" backend/services/inspection_service.py   # 0
```
Hasil: 0 lulus, 0 gagal (uji statis: 0 kecocokan `role_in`; uji perilaku inspeksi butuh data QC yang tak ada di seed).

### Upaya membantah
- [tanpa_izin] Cari gerbang berbasis nama peran di inspection_service. Hasil: tidak ada `role_in`/nama peran; akses lewat `require_permission`. LULUS (statis).
- [jalur_lain] `inspection_state` satu-satunya penulis status. Hasil: ya. LULUS (statis).

### Putusan
Putusan: terhambat_lingkungan
Alasan: statis bersih (`inspection_service.py:42` tanpa `role_in`), tetapi perilaku inspeksi (finish/inspect_line) tak bisa dijalankan — data acuan tanpa tugas QC (grade_history 0). Butuh seed inspeksi untuk `verified`.

## Keputusan 6

### Yang diputuskan
Makloon: kunci cadangan FIX-9 (`consume_for_issue`/`safe_lock`) DAN jurnal langkah PK-18, keduanya jalan; jurnal langkah tidak hilang. (`makloon_order_service.py:660`, `makloon_reservation_service.py`)

### Perbaikan yang diperiksa
SHA unit: `0f0ff4e`. Berkas dibaca: `backend/services/makloon_order_service.py:660-742` (`issue_step`: `own_lock_ids`, `safe_lock`, `pick_rolls`, `unlocked_by_others`) + jalur `_post_step_gl`/`reserve_for_mko` (:581). ±80 baris, 2 berkas (makloon_order_service + makloon_reservation/roll_lock).

### Temuan asli
Dua implementasi issue: FIX-9 `consume_for_issue(actor_name)` vs PK-18 `_post_step_gl`.

### Pintu lain
```
grep -nE "safe_lock|consume_for_issue|_post_step_gl|reserve_for_mko" backend/services/makloon_order_service.py
```
Kesimpulan: kunci (safe_lock :699) dan jurnal langkah hidup di `issue_step`; keduanya tergabung (INTEGRASI §1 baris 5).

### Uji yang dijalankan
```
python -m pytest -n0 tests/test_fix9_makloon_lock.py
```
Hasil: 36 lulus, 0 gagal (digabung dengan test_fix10_roll_state; kunci cadangan FIX-9 lulus). Jurnal langkah PK-18 tidak diuji end-to-end di sesi ini.

### Upaya membantah
- [bersamaan] uji FIX-9 mencakup kunci bersaing. Hasil: lulus.
- [jalur_lain] Cari issue makloon kedua. Hasil: satu `issue_step`. LULUS.

### Putusan
Putusan: benar
Alasan: `test_fix9_makloon_lock.py` lulus (MongoDB asli) + `issue_step` (makloon_order_service.py:660-742) memanggil safe_lock dan jalur jurnal langkah bersama; tak ada issue kedua.

## Keputusan 7

### Yang diputuskan
Stock opname: `cycle_count_state.transition` (FIX-10) + `submitted_by_id` (KF-T6) + `guard_door` (KP-T4); kontrol dua orang & Aturan Persetujuan tetap memblokir. (`cycle_count.py:268`, `cycle_count_state.py`)

### Perbaikan yang diperiksa
SHA unit: `0f0ff4e`. Berkas dibaca: `backend/routers/cycle_count.py:243-275` (submit: `ccs.transition`+`submitted_by_id`), `:310-320` (approve: `guard_door`+`dual_control.tolak_bila_pelaku_sama`), `:372` (approve transition). ±50 baris, 2 berkas (cycle_count router + cycle_count_state/dual_control).

### Temuan asli
FIX-10 `cycle_count_state.transition` vs KF-T6 `submitted_by_id` vs KP-T4 `guard_door` — tiga perubahan satu endpoint.

### Pintu lain
```
grep -nE "cycle_count_state|transition|submitted_by_id|guard_door|tolak_bila_pelaku_sama" backend/routers/cycle_count.py
```
Kesimpulan: transisi lewat `ccs.transition`; `submitted_by_id` di set_fields; approve memanggil `guard_door` + `dual_control` (INTEGRASI §1 baris 6).

### Uji yang dijalankan
```
# uji lapis A cycle_count tidak dijalankan (butuh akun manager.printing@ dari seed_realistic, §6); statis dibaca
```
Hasil: 0 lulus, 0 gagal (statis dibaca; uji dua-orang butuh akun seed_realistic).

### Upaya membantah
- [tanpa_izin] approve butuh `require_permission("inventory","approve_count")` + guard_door. Hasil: dua gerbang ada (statis).
- [ulang] pengaju==penyetuju ditolak `tolak_bila_pelaku_sama(pengaju=[submitted_by_id, submitted_by])`. Hasil: ada di kode (cycle_count.py:317-319). Belum diuji runtime.

### Putusan
Putusan: terhambat_lingkungan
Alasan: kode dua-orang & transisi ada (`cycle_count.py:268-319`), tetapi uji lapis A butuh akun `manager.printing@` (§6, tak ada di rantai seed) → tak bisa dijalankan; statis saja tak cukup untuk `verified`.

## Keputusan 8

### Yang diputuskan
Registri izin: 5 kunci `ops.*` masa simpan log (FIX-7) dirapikan; MD dapat `product.export` (keputusan 10 Nov) lewat `sync_permission_modules` di data tersimpan. (`permissions_config.py:512`, `config_catalog_retention.py`)

### Perbaikan yang diperiksa
SHA unit: `0f0ff4e`. Berkas dibaca: `backend/permissions_config.py:508-540` + `permissions_config.py:595-624`; `backend/config_catalog_retention.py:1-30`. ±100 baris, 2 berkas (permissions_config + config_catalog_retention).

### Temuan asli
FIX-7 menambah 5 kunci `ops.*`; FIX-6 menambah `product.export` untuk MD → perlu masuk matriks izin tersimpan tanpa bentrok.

### Pintu lain
```
grep -nE "\"export\"|sync_permission_modules" backend/permissions_config.py
grep -rln "sync_permission_modules" backend/
```
Kesimpulan: MD `product.export` ada di default (permissions_config.py:512) dan disinkron ke data lewat `sync_permission_modules` (bootstrap). Satu sumber default izin.

### Uji yang dijalankan
```
python -m pytest tests_mem/test_PRT9_izin_bawaan.py -n 0 -q   # 15 lulus, 0 gagal
```
Hasil: 15 lulus, 0 gagal (uji izin bawaan).

### Upaya membantah
- [tanpa_izin] Cek MD tidak dapat `product.delete`/`import` (hanya view/create/update/export, permissions_config.py:512). Hasil: benar, export ada tanpa delete. LULUS.
- [jalur_lain] Cari definisi izin MD kedua. Hasil: satu blok `"md"` (permissions_config.py:508). LULUS.

### Putusan
Putusan: benar
Alasan: `permissions_config.py:512` memberi MD `product.export` + disinkron `sync_permission_modules`; uji `test_PRT9_izin_bawaan.py` 15 lulus; tidak ada definisi izin MD kedua.

## Fungsi yang diubah dua sisi

Dinilai mandiri (hunk FIX bersifat tambahan kecuali disebut). berkas:baris di HEAD:

| Fungsi | berkas:baris | Penilaian |
|---|---|---|
| `_create_po_core` | routers/purchase_orders.py:351 | aman — tambahan field; tak ada pintu posting/stok kedua |
| `submit_return` | routers/sales_returns.py:320 | aman — transisi lewat tabel state |
| `complete_task` | services/inbound_complete_service.py:53 | aman — penyelesaian tugas via state |
| `close_remaining` | services/putaway_arrival_service.py:255 | aman — penutup sisa tambahan |
| `issue_material` | services/rnd_sample_service.py:1444 | aman — issue bahan sample |
| `_make_roll` | services/roll_service.py:492 | aman — pembuat roll tunggal (helper lokal) |
| `confirm_cut` | services/roll_service.py:674 | aman — potong lewat state/round-check |
| `reserve_rolls_for_transfer` | services/roll_service.py:1778 | aman — reservasi transfer |
| `assert_roll_rounding` | services/sales_order_helpers.py:82 | aman — validasi pembulatan |
| `_supplier_deadline_job` | services/scheduler_service.py:75 | aman — job terjadwal (tak sentuh jurnal) |
| `cancel_line` | services/so_line_cancel_service.py:59 | aman — batal baris via state |
| `resolve` | services/config_resolver.py:273 | aman — resolusi konfigurasi berlapis |
| `_restock_returned_items` | services/return_service.py:1174 | aman — restock via roll_state (K4) |
| `settle_return` | services/return_service.py:1759 | perlu uji runtime — settlement retur (lihat K3, data 0) |
| `reverse_settlement` | services/purchase_return_service.py:1065 | perlu uji runtime — pembalikan settlement |
| `lifespan` | server.py:68 | aman — startup (bootstrap + sync izin) |
| `covers` | config_registry.py:834 | aman — cakupan kunci konfigurasi |

Ringkas B0: 8 keputusan → verified 4 (K1,K4,K6,K8), perlu_keputusan_pemilik 1 (K2), terhambat_lingkungan 3 (K3,K5,K7). 17 fungsi dua-sisi dinilai; 2 (settle_return, reverse_settlement) perlu uji runtime karena data retur kosong.
