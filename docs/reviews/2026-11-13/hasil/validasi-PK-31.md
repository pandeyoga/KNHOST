Commit yang direview: 91a3ec0612952bfcc88335668ef2b3f601ba926a
Lingkungan: lapis B database tiruan (mongomock, aplikasi utuh) + lapis A MongoDB asli lokal (`test_database`) dengan backend hidup di 8001 dan data acuan `restore_local_demo.sh`. Docker tidak ada. Tanpa potret layar (pilihan pemilik sesi ini). Skrip migrasi `scripts/migrasi_pk31_eliminasi_per_periode.py --apply` TIDAK dijalankan di data mana pun selain database tiruan uji pelaksana (H3).

# Validasi PK-31 — eliminasi konsolidasi per periode, rantai A→B→C, refund retur setelah lunas (batch B1)

Uji bantahan reviewer: `docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK31.py` (5 uji: 4 lulus, 1 gagal — yang gagal adalah bantahan yang berhasil, lihat IC-07).

## IC-03 — Eliminasi konsolidasi berubah mundur

### Temuan asli
Dibaca di `cd6963a`: `backend/services/consolidation_service.py:728` — satu entri eliminasi per pasangan yang diperbarui di tempat (`update_one({"id": prev["id"]}, {"$set": payload})` di `:735`), dihitung dari sisa saldo dan rasio belum-terjual HARI INI; neraca konsolidasi 31 Des yang dibuka Februari memakai keadaan Februari.

### Perbaikan yang diperiksa
SHA unit `24425624` (mesin) + `dae12fcf` (laporan memakai mesin). Berkas dibaca: `backend/services/interco_elimination_engine.py:103-260` (`facts`: semua besaran bertanggal — jurnal, tugas gudang, retur, surat jalan, pelunasan; `state_at(as_of)` hanya menjumlah fakta ≤ tanggal; `lines_between` = selisih kumulatif dua tanggal), `backend/services/interco_elimination_engine.py:331-470` (`bulan_beku`, `sync_period`: entri beku tidak ditimpa dan selisihnya masuk `stale`; `pair_entries`/`eliminations_for` baca murni), `backend/services/consolidation_service.py:497-504` (dua pintu lama tinggal pemanggil `sync_period`).

### Pintu lain
```
grep -rn "sync_period\|interco_elimination_engine" --include=*.py backend/services backend/routers | grep -v "^backend/services/interco_elimination_engine.py"
grep -n "_g6_pair_totals\|_g6_elim_lines\|intercompany_eliminations" backend/services/consolidation_service.py
```
Kesimpulan: penghitung lama (`_g6_pair_totals`, `_g6_elim_lines`) sudah tidak ada; penulis entri otomatis hanya `sync_period` (dipanggil `interco_service.py:1934` dan `consolidation_service.py:504`). Entri manual (`consolidation_service.py:297`) tetap ada dan memang jalur terpisah. Catatan: PEMBEKUAN baru terjadi saat `sync_period` berjalan sesudah kedua PT menutup bulan — menutup periode sendiri tidak memicu sinkron.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK31_eliminasi_periode.py -n 0 -q -k "U1_ or U2 or U3 or U4 or U5 or U8 or U14 or kait or indeks"   # pelaksana: 9 lulus
cd backend && REACT_APP_BACKEND_URL=http://localhost:8001 python -m pytest -n0 -q tests/test_bp_PK31_unik_refund_bersamaan.py -k U15a          # lapis A: 1 lulus
cp docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK31.py backend/tests_mem/ && cd backend && python -m pytest tests_mem/test_bantah_PK31.py -n 0 -q -s -k IC03   # reviewer: 2 lulus
```
Hasil: 12 lulus, 0 gagal.

### Upaya membantah
- [ulang] `sync_period` dijalankan lima kali untuk Des 2026 dan Jan 2027 pasangan P1. Hasil: tetap 2 entri (satu per bulan), baris identik — tidak terbantah.
- [data_lama] Jan 2027 ditutup di kedua PT dan disinkron (entri `frozen: True`); lalu surat jalan BERTANGGAL 20 Jan (500 m keluar grup) disisipkan belakangan dan disinkron lagi. Hasil: entri Jan tersimpan tidak berubah, `frozen: 1`, `stale: 1` untuk pasangan + bulan itu (hitung ulang memberi laba belum terealisasi 20 jt) — tidak terbantah.
- [periode_tertutup] Jurnal mundur ke bulan beku (uji pelaksana U8 dijalankan ulang). Hasil: entri beku tetap, selisih dilaporkan `stale` — tidak terbantah.

### Putusan
Putusan: verified
Alasan: keadaan per tanggal dari fakta bertanggal terbukti di `backend/services/interco_elimination_engine.py:200-214` dan entri beku tidak ditimpa di `:383-387`; `test_PK31_U4_laporan_tanggal_lama_tidak_berubah`, `test_PK31_U8_bulan_beku_dan_stale`, `test_IC03_ulang_sinkron_dua_kali_tidak_menggandakan`, `test_IC03_data_lama_kejadian_mundur_sesudah_bulan_beku` lulus; penghitung lama sudah tidak ada.

## IC-04 — Laba antar-PT dianggap terealisasi pada rantai A→B→C

### Temuan asli
Dibaca di `cd6963a`: `backend/services/interco_service.py:1783` — saat roll pindah, `cost_basis` ditimpa pasangan baru (`interco_pair_id`, `previous_unit_cost`) sehingga jejak A→B hilang ketika B menjual ke C; `backend/services/interco_margin.py:80` menghitung "belum terjual" dari roll bertanda pasangan yang masih dimiliki pembeli → margin A→B dianggap terealisasi padahal barang masih di dalam grup.

### Perbaikan yang diperiksa
SHA unit `24425624` + `dae12fcf`. Berkas dibaca: `backend/services/interco_service.py:2430-2450` (`_cost_chain`, `drop_chain_link`: `cost_basis.chain` menyimpan semua unsur perpindahan), `backend/services/interco_elimination_engine.py:103-196` (`facts`: roll pasangan = roll yang RANTAINYA memuat pasangan itu; "terjual" = surat jalan ke luar grup atas roll itu, siapa pun pemilik terakhirnya), `backend/services/interco_elimination_engine.py:200-214` (`unsold_ratio = 1 − terjual/pindah`).

### Pintu lain
```
grep -n '"chain"\|chain' backend/services/interco_service.py | head
grep -rn "unsold_ratio\|pair_state" --include=*.py backend/services | grep -v "interco_elimination_engine.py"
```
Kesimpulan: rasio belum-terjual satu rumus (`pair_state`) dipakai laporan konsolidasi dan rapor margin (`interco_margin.py:65`, `:147`, `:220`); tidak ada penghitung rasio kedua.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK31_eliminasi_periode.py -n 0 -q -k "U6 or U7 or ic03_ic04"     # pelaksana: 4 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK31.py -n 0 -q -s -k IC04                                 # reviewer: 1 lulus
```
Hasil: 5 lulus, 0 gagal.

### Upaya membantah
- [sebagian] A→B 1.000 m (100 jt, HPP 60 jt); B memotong, 500 m dijual ke C (60 jt, HPP B 50 jt), 500 m tetap di B; C menjual 250 m ke luar grup. Hitung tangan: Agu 40 jt / 10 jt; Sep 40 × 750/1.000 = 30 jt dan 10 × 250/500 = 5 jt. Hasil: mesin memberi 40 jt/10 jt (Agu) dan 30 jt/5 jt (Sep); laporan Agu tidak berubah sesudah kejadian Sep — tidak terbantah.
- [batas_nilai] Sisa 250 m di C dan 500 m di B keluar grup 5 Okt. Hasil: laba belum terealisasi kedua pasangan tepat 0 — tidak terbantah.

### Putusan
Putusan: verified
Alasan: rantai biaya tersimpan (`backend/services/interco_service.py:2430-2450`) dan rasio dihitung sampai barang keluar grup (`backend/services/interco_elimination_engine.py:200-214`); `test_PK31_U6_rantai_tiga_pt`, `test_PK31_U6b_rapor_margin_satu_rumus`, dan bantahan `test_IC04_sebagian_rantai_separuh_ke_C_lalu_keluar_grup` (cocok hitung tangan di tiga tanggal) lulus.

## IC-07 — Retur setelah lunas menghasilkan saldo yang tak terlihat dan tak bisa dilunasi

### Temuan asli
Dibaca di `cd6963a`: `backend/services/interco_return_service.py:149` dan `:58` (retur hanya menghitung dokumen), `backend/services/interco_service.py:804` — retur sesudah transaksi lunas membuat penjual berutang refund di buku besar (1-1250 negatif) sementara layar Saldo Antar-PT menampilkan 0 dan tidak ada jalur melunasinya.

### Perbaikan yang diperiksa
SHA unit `24425624` + `dae12fcf`. Berkas dibaca: `backend/services/interco_service.py:878-886` (`refund_due = max(0, returned_amount + settled_amount − grand_total)`, `refund_left_of`), `backend/services/interco_service.py:1428-1500` (`create_refund`: PERIKSA pasangan/sisa refund/rekening → niat ber-id dari kunci → efek → jurnal kembar), `backend/services/interco_return_service.py:72-82` (`_returned_qty_map` hanya menghitung retur `approved`/`completed`) dan `backend/services/interco_return_service.py:122-146` (`returnable`). Persetujuan retur (`approve`, mulai `:420`) tidak memeriksa ulang jumlah yang masih bisa diretur.

### Pintu lain
```
grep -n "refund_due\|def create_refund" backend/services/interco_service.py
grep -n "^COUNTED\|qty_returnable\|melebihi" backend/services/interco_return_service.py
grep -n "refunds" backend/routers/interco.py
```
Kesimpulan: jalur refund satu (`POST /interco/refunds` → `create_refund`). Celah di hulu: batas "masih bisa diretur" hanya dicek saat DRAF dibuat (`interco_return_service.py:221`) dan draf lain tidak dihitung (`COUNTED = ("approved", "completed")`, `:55`), sedangkan `approve` tidak mengecek lagi — dua draf yang masing-masing sah bisa disetujui berurutan, dan `refund_due` tidak dibatasi uang yang pernah diterima.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK31_eliminasi_periode.py -n 0 -q -k "U10 or U11 or U12 or U13"   # pelaksana: 4 lulus
cd backend && REACT_APP_BACKEND_URL=http://localhost:8001 python -m pytest -n0 -q tests/test_bp_PK31_unik_refund_bersamaan.py -k U15b   # lapis A: 1 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK31.py -n 0 -q -s -k IC07                                  # reviewer: 1 lulus, 1 gagal
```
Hasil: 6 lulus, 1 gagal. Yang gagal: `test_IC07_koreksi_retur_kedua_melebihi_nilai`.

### Upaya membantah
- [sebagian] Refund tanpa retur (409 "tidak punya sisa pengembalian dana"); lalu retur 4 jt, refund 1,5 jt, kemudian dua refund 2,5 jt serentak berkunci beda. Hasil: sisa layar 2,5 jt = −saldo 1-1250 sesudah refund pertama; dari dua serentak tepat satu 200 dan satu 409; akhir sisa 0, 1-1250 penjual 0, 2-1250 pembeli 0, `refund_paid` 4 jt di kedua dokumen — tidak terbantah.
- [koreksi] Transaksi 10 jt (lunas 10 jt, sudah diretur 4 jt): retur kedua 7 jt disetujui. Hasil: LOLOS — `returned_amount` 11.000.000 > nilai transaksi 10.000.000 dan `refund_due` 11.000.000 > uang yang pernah diterima penjual (10 jt); layar akan menawarkan refund 7 jt lagi. TERBANTAH.
- [periode_tertutup] Refund saat periode pembeli tertutup (uji pelaksana U13 dijalankan ulang). Hasil: 409 tanpa tulisan — tidak terbantah.

### Putusan
Putusan: reopened
Alasan: jalur refund sendiri benar (`backend/services/interco_service.py:1428-1500`, `test_PK31_U11_refund_dicatat_sekali`, `test_IC07_sebagian_dan_bersamaan_refund` lulus), tetapi `test_IC07_koreksi_retur_kedua_melebihi_nilai` membuktikan kewajiban refund bisa melebihi uang yang diterima karena persetujuan retur tidak memeriksa ulang sisa yang boleh diretur dan `refund_due_of` (`backend/services/interco_service.py:878`) tidak dibatasi `settled_amount`. Reproduksi: transaksi antar-PT lunas → dua dokumen retur draf atas transaksi yang sama (Σ nilai > nilai transaksi) → setujui keduanya → `refund_due` > `settled_amount` → `POST /api/interco/refunds` diterima sampai jumlah itu. Catatan kejujuran uji: draf kedua disisipkan sebagai fixture (pola uji pelaksana U10); bahwa pintu "buat draf" membiarkan dua draf sekaligus disimpulkan dari kode `:55` dan `:72-82`, belum dijalankan lewat API. Arah: periksa ulang `qty_returnable` saat `approve` (klaim per transaksi asal) dan batasi `refund_due` ≤ `settled_amount`.
