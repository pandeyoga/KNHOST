# FIX-9 — Cadangan bahan makloon dikunci per roll (B3a SSOT-4 · keputusan B3a #1 tuntas)

- **Tanggal:** 10 Nov 2026 (WIB) · **Pelaksana:** Claude Code (implementer paket FIX-9) · **Branch:** worktree
  `worktree-agent-a1f27c1c8c487df19` (dasar `main` `6b5929e`, digabung dengan `main` terbaru `7ad4ac4` = FIX-6 + integrasi).
- **Status:** `implemented_pending_review` (implementer tidak menetapkan `verified`). Verifikasi tampilan di peramban diserahkan ke
  koordinator — paket ini tidak memakai alat peramban.
- **Bahan:** `B3a-SSOT-SKEMA-STOK.md` §SSOT-4 (+ lampiran C.3), `hasil/FIX-2-ANGKA-STOK.md` §5 butir 1 & 5, `KEPUTUSAN-KOORDINATOR.md`
  (B3a #1 "sebagian → langkah lanjut"; B3a #7 lintas PT hanya angka), brief FIX-9.
- **Commit:** kode + uji + skrip + laporan di branch worktree (lihat `git log`; tanpa push/merge).

---

## 1. Ringkasan

Cadangan bahan makloon (`material_reservations`) dulu hanya angka **produk × PT** tanpa gudang & roll. FIX-2 mengurangkannya
konsisten di angka stok (`allocate_makloon`), tetapi rollnya tetap **"tersedia"**: pemilih roll SO/transfer, alokasi SO/POS,
tahan/WIP, dan issue MKO lain bisa mengambil roll yang sebenarnya dicadangkan untuk makloon (B3a SSOT-4, P0).

Sekarang **panjangnya dikunci di roll nyata** saat cadangan lahir, memakai skema reservasi panjang yang SUDAH ada
(`length_reservations` WM-02, helper `roll_service._reserve_length` — tidak ada skema kedua):

```
roll.length_reservations[] = {"id": "rsv_…", "qty": 40, "status": "reserved", "created_at": …,
                              "ref": {"type": "makloon", "id": <id cadangan>, "number": "MKO-00005",
                                      "mko_id", "mko_number", "pr_id", "pr_number", "entity_id"}}
material_reservations += {"locked_qty": 40, "locks": [{roll_id, roll_no, warehouse_id, lot, qty, unit, status}],
                          "source_warehouse_id": "<gudang sumber>"}      ← cermin, dibangun ulang dari roll
inventory_balances    += {"makloon_locked_qty": 40}                       ← bagian dari ember reserved_qty
```

* **Roll = SSOT** panjang terkunci → `rebuild_balance` mengeluarkannya dari "Tersedia" di **semua** endpoint (termasuk 9 endpoint
  yang dulu mengabaikan cadangan — `/inventory/balances`, `/inventory/rolls/available`, POS, dll.).
* **Tidak dobel-kurang:** `allocate_makloon` (tidak dihapus) kini hanya mengalokasikan sisa **belum terkunci** `qty − locked_qty`;
  bila semua terkunci kontribusinya 0. Bagian terkunci ditampilkan di kelompok **"Cadangan makloon"** (dipindah dari "Dipesan")
  sehingga rincian status, Stok Fisik, dua angka (LOKAL/GLOBAL) & Total grup **tidak berubah** dibanding sebelum dikunci.
* Mesin kunci: `backend/services/makloon_roll_lock.py` (baru) dipanggil dari `material_reservation_service` (titik masuk tetap).

## 2. Temuan yang ditutup (ID → perubahan → uji)

| ID | Perubahan | Uji (gagal di dasar, lulus sesudah) |
|---|---|---|
| **B3a SSOT-4** (P0) — cadangan makloon di luar roll, roll tetap "Tersedia" | Kunci per roll saat lahir (MKO dibuat, PR disetujui), lepas per roll saat issue, lepas semua saat batal/tolak/selesai/replan; saldo & 2 angka konsisten | `test_fix9_makloon_lock.py` 13 uji (§7) |
| **Keputusan B3a #1** (koordinator: "sebagian → langkah lanjut kunci per roll") | Langkah lanjut FIX-2 §5 butir 1 & 5 dikerjakan: kunci per roll + `allocate_makloon` tinggal sisa belum terkunci | idem + `test_fix2_stock_figures.py` 16/16 |
| **FIX-2 §5 butir 5** — "roll tersedia tidak dikurangi cadangan makloon" | `roll_count`/roll tersedia kini tanpa roll yang terkunci penuh; pemilih roll tidak menawarkan panjang terkunci | `test_stock_figures_tidak_dobel_kurang…` (`rolls` 3 → 2), `test_pemilih_roll…` |
| (temuan saat kerja) replan PR → `DuplicateKey` | Sejak index unik `uq_id` (FIX-5), replan qty PR (lepas → cadangkan ulang) menyisipkan id cadangan yang SAMA dengan dokumen yang sudah dilepas → 500. Id cadangan baru kini unik (`…_r2`, `…_r3`) — juga wajib karena kunci roll merujuk id cadangan | `test_pr_disetujui_mengunci_dengan_gudang_pr` (replan: lepas → cadangkan ulang → id baru, terkunci lagi; DB uji ber-index unik `uq_id`) |

## 3. Perilaku yang dibangun (butir brief 1–6)

### 3.1 Kunci saat lahir (butir 1)
* **Kapan:** `reserve_for_mko` (MKO `process_only` dibuat) dan `reserve_for_pr` (PR makloon **disetujui** — `approve_requisition`,
  `submit` tanpa persetujuan, PR dibuat langsung `approved`, replan qty). Kunci dijalankan di dalam mutex bahan × PT yang sama
  dengan perhitungan cadangan, sehingga cadangan berikutnya menghitung stok bebas sesudah kunci menempel.
* **Gudang:** gudang sumber — MKO `from_warehouse_id` (atau gudang asal langkah 1), PR `warehouse_id`. Kosong → gudang
  ber-panjang-bebas terbesar dulu (aturan yang sama dengan `allocate_makloon`). Kunci **tidak meluber** ke gudang lain bila
  gudang sumber kurang (sisanya "belum terkunci").
* **Roll yang boleh dikunci:** `available`, milik PT cadangan, satuan = satuan dasar produk, tidak diklaim PA, tidak ditahan
  inspeksi, tidak di-peg (earmark), di gudang yang dihitung (aktif, bukan data uji), panjang bebas > 0.
* **Urutan:** **FIFO** (diterima paling awal → nomor roll), roll utuh dulu, roll terakhir sebagian (keputusan implementer §5.1).
* **PR → MKO** (`transfer_to_mko`): rujukan kunci diganti bernomor MKO; bila gudang sumber MKO berbeda, kunci **dipindah**
  (kunci baru di gudang sumber dulu, baru kunci lama dilepas — tidak ada celah tanpa kunci).
* **"Saat disetujui bila `makloon_reserve_mode=approve`"** — lihat §5.2: persetujuan manajer pada SO yang memakai stok cadangan
  **meminjam** kunci (dilepas di roll sebanyak kekurangan; cadangan tetap → sisa belum terkunci; jejak `borrowed` + persetujuan
  "makloon" di SO).

### 3.2 Issue / konsumsi / release (butir 2)
* **Issue per roll** (`issue_rolls_to_subcon`) & **issue jumlah** (`issue_to_subcon`): roll yang dikunci cadangan **MKO itu
  sendiri** boleh dikirim; kuncinya dilepas di **tulisan CAS yang sama** dengan perpindahan roll ke `subcon`. Jalur jumlah memakai
  roll terkunci sendiri **lebih dulu**. Gagal di tengah → kunci dipulihkan (`lock` idempoten).
* **Roll lain menggantikan kunci:** sesudah issue, cadangan berkurang sebanyak yang dikirim (`consume_for_issue`, aturan lama);
  kunci yang **melebihi sisa cadangan** dilepas (`trim`, kunci terbaru dulu) → "roll lain di-issue → kunci lama dilepas sejumlah itu".
* **Release:** PR ditolak/batal/replan, MKO batal/selesai → `release` melepas **semua** kunci; idempoten (cadangan yang sudah
  tidak aktif tetapi kuncinya masih menempel ikut dibersihkan); stok yang baru bebas langsung dipakai mengisi sisa belum terkunci
  cadangan lain (bahan × PT sama). *Kedaluwarsa:* kode tidak punya mekanisme kedaluwarsa cadangan/PR — tidak ada jalur yang perlu
  disambung (dicatat §9).
* **Jejak:** setiap kunci/lepas/pinjam/pangkas → entri `history` cadangan (`locked`, `lock_shortage`, `trimmed`, `released_lock`,
  `borrowed`, `unlocked`) + satu baris `audit_logs` (`makloon_<event>`, `entity_type=material_reservations`, sumber
  `fix9_makloon_lock`, `scope_entity_id` = PT).
* **CAS/paralel:** CAS per roll terhadap panjang bebas (`_reserve_length`) — dua cadangan tidak mengunci panjang yang sama;
  pelepasan CAS terhadap isi `length_reservations` yang dibaca; mutex per cadangan (`material_reservation_locks._id="rl:<id>"`,
  kedaluwarsa 60 dtk) mencegah `lock` ganda melebihi `qty`. Diuji paralel (§7).

### 3.3 Kekurangan stok (butir 3)
Kunci sebanyak yang ada; `qty − locked_qty` = **cadangan belum terkunci** (entri `lock_shortage`). Hanya bagian ini yang masih:
`stock_figures.makloon_by_product_entity` → `allocate_makloon`, `makloon_guard` (SO/POS), `free_for_commitment` (cadangan baru,
issue MKO lain), buku bahan MKO. Bagian terkunci sudah keluar dari saldo → **tidak dobel-kurang** (rumus Tersedia tidak berubah).
Perubahan `stock_figures.py` minimal (dicatat untuk FIX-7): `makloon_by_product_entity` membaca `locked_qty`; `segments` memindah
`makloon_locked_qty` saldo dari `reserved_qty` ke `makloon_reserved_qty`; `sum_segments` menjumlah `makloon_locked_qty`;
`adjust_balance_row` mengikutkan `reserved_qty` segmen. Pembaca lain yang menggabung panjang bebas roll + cadangan agregat
disesuaikan agar tidak dobel: `sales_p04_service` (ringkasan sales), matriks rincian produk (`routers/products.py`), buku bahan MKO.

### 3.4 Pemilih roll / SO / POS / pengambilan (butir 4)
| Permukaan | Perilaku |
|---|---|
| Pemilih roll desktop & HP (`/inventory/rolls/available`, `RollPicker` — dipakai Quick View, HP sales, transfer) | Panjang terkunci tidak ditawarkan (panjang bebas); roll sebagian terkunci bertanda **"Dicadangkan makloon · MKO-…"**; catatan kuning hanya untuk sisa **belum terkunci** (`makloon_unlocked_qty`) |
| Alokasi SO otomatis & POS (POS memakai jalur SO) | Hanya panjang bebas; mode Blokir → 409 seperti dulu; mode approve + persetujuan → pinjam kunci (§5.2) |
| Beli per roll (`reserve_roll_mode_item`) | Minta lebih dari panjang bebas roll terkunci → **409 `MAKLOON_RESERVED`** "Roll RL-… : dicadangkan makloon MKO-… — panjang itu tidak bisa dijual"; mode approve → `MAKLOON_RESERVED_APPROVAL` (dialog persetujuan yang sudah ada di FE), sesudah disetujui kunci roll itu dipinjam |
| Pilih roll transfer/ganti roll (`reserve_specific_rolls`) | 409 menyebut MKO/PR pemegang panjang |
| Tahan / WIP / issue jumlah MKO lain (`move_rolls_by_qty`) | Roll yang panjangnya dipegang dokumen lain tidak dipakai; 409 menyebut MKO bila stok tidak cukup |
| Issue per roll MKO lain (`block_reason`) | 409 "Roll … sudah dicadangkan dokumen lain (dicadangkan makloon MKO-…)" |
| Pengambilan (pindai roll, HP & desktop) | Roll terkunci → 400 "… tidak ter-alokasi untuk order ini (dicadangkan makloon MKO-…)" |
| Potong sampel R&D / potong sampel jual | Pesan panjang bebas menyebut MKO bila yang memegang kunci makloon |
| Antrean Potong / konfirmasi potong | Kunci makloon **tidak** muncul di antrean potong; `confirm_cut` atas entri makloon → 409 |
| Lintas PT (B3a #7, FIX-2) | Pemilih roll lintas PT: lencana tanpa nomor dokumen (`makloon_lock.numbers = []`) bila roll milik PT di luar izin; pesan pengambilan memakai PT tugas |

### 3.5 Skrip migrasi (butir 5) — lihat §8 cara menjalankan di produksi.
`scripts/fix_data_2026_11_10_fix9_kunci_makloon.py` — dry-run bawaan; laporan per cadangan: dokumen, PT, qty, terkunci
sebelum → sesudah, gudang sumber, **roll yang akan dikunci (nomor @gudang panjang)**, kekurangan; langkah `orphan_locks` &
`mirror_resync`; `--apply`, `--undo --apply`, `--only`, `--report`; pagar DB pola FIX-7.

### 3.6 Tampilan (butir 6)
`components/MakloonLockBadge.jsx` = **`StatusBadge` baku** (kode status baru `makloon_reserved` di `utils/statusVocab.js`, ranah
roll, label "Dicadangkan makloon", nada *khusus*, ikon gembok) — bukan chip buatan layar. Dipasang di: daftar roll (rincian
roll, `RollsTable`), penampil roll berkelompok (`RollGroupView`, tingkat roll), pemilih roll (desktop & HP), pop-up Issue MKO
("Dikunci untuk MKO ini · 40 yd"). Buku bahan MKO menampilkan roll terkunci & sisa belum terkunci.

## 4. Perubahan perilaku yang terlihat pengguna

1. **Roll yang dicadangkan makloon tidak bisa lagi dijual/dipilih/ditahan/dipindah** untuk keperluan lain; layar menyebut
   MKO/PR pemiliknya. (Dulu: roll tampil tersedia; reservasi SO hanya ditolak `makloon_guard` secara agregat.)
2. Roll terkunci bertanda **"Dicadangkan makloon · MKO-…"** di daftar roll, penampil roll, pemilih roll, pop-up Issue.
3. **Rincian status stok**: angka sama, tetapi panjang terkunci berada di "Cadangan makloon" (bukan "Dipesan") — di saldo mentah
   (`/inventory/balances` sebelum penyesuaian) panjang itu ada di `reserved_qty` + penanda `makloon_locked_qty`.
4. **Roll tersedia (jumlah roll)** turun sebanyak roll yang terkunci penuh (FIX-2 §5 butir 5 tertutup).
5. **Issue MKO:** roll yang dikunci untuk MKO itu tampil paling atas & bertanda; issue jalur jumlah memakai roll terkunci dulu.
6. **Mode approve:** sesudah manajer menyetujui pemakaian stok cadangan, kunci dipinjam (riwayat cadangan "dipinjam pesanan …").
   Bila pesanan itu batal, kunci **tidak otomatis** kembali — diisi ulang saat issue MKO, saat cadangan lain dilepas, atau dengan
   skrip FIX-9 (selama itu sisa tetap dikurangkan sebagai "belum terkunci").
7. **Tahan/WIP (Status Stok › Tahan/Mulai WIP)** tidak lagi memakai roll yang panjangnya dipegang reservasi potong SO (dulu ikut
   dipindah — panjang pesanan hilang ke ember lain). Pesan 409 menyebut roll pemegangnya.
8. Replan qty PR makloon tidak lagi gagal 500 (id cadangan unik).

## 5. Keputusan implementer (di luar keputusan koordinator) + alasan

1. **Urutan FIFO (bukan "lot terbanyak").** Sama dengan urutan issue jalur jumlah (`move_rolls_by_qty` FEFO) dan daftar pilih
   roll issue (`received_date`), sehingga issue berikutnya memakai roll yang memang dikunci (kunci jarang "berpindah"), bahan
   lama (greige) bergerak lebih dulu; makloon (celup) tidak bergantung pada keseragaman lot seperti penjualan.
2. **Tafsir "saat disetujui bila `makloon_reserve_mode=approve`".** Cadangan lahir saat PR **disetujui** (sudah ada) → dikunci
   di situ. Mode `approve` menyangkut SO yang memakai stok cadangan: karena panjang terkunci tidak lagi terlihat oleh alokasi,
   persetujuan manajer (`confirm_makloon_override`) **meminjam** kunci sebanyak kekurangan (kunci terbaru dulu; beli per roll:
   kunci roll itu). Cadangan tidak dikurangi (tetap komitmen makloon) → sisa jadi "belum terkunci", angka stok tetap
   mengurangkannya, persetujuan "makloon" SO tetap jejaknya. Tanpa ini mode approve tidak bisa dipakai sama sekali.
3. **Kunci = `status: "reserved"`, `ref.type: "makloon"`** (pola WM-02 apa adanya) + penanda saldo `makloon_locked_qty` (subset
   `reserved_qty`, bukan ember baru) — `ALL_BUCKETS`/Stok Fisik/rekonsiliasi tidak berubah; `stock_figures` memindahkannya ke
   "Cadangan makloon" agar rincian sama seperti sebelum dikunci.
4. **Cermin di cadangan** (`locks`, `locked_qty`) dibangun ulang dari roll sesudah setiap operasi (roll = SSOT). Jendela basi
   (roll sudah terkunci, cermin belum) hanya membuat pengurangan **lebih konservatif**, tidak pernah menjual stok cadangan;
   skrip FIX-9 langkah `mirror_resync` memperbaiki sisa basi.
5. **Gudang sumber tegas** (tidak meluber): brief menyebut gudang sumber MKO; bahan di gudang lain tetap bebas, kekurangan
   tercatat "belum terkunci" (+ entri `lock_shortage`) dan tetap dikurangkan agregat.
6. **Roll bersatuan lain** dari satuan dasar produk (data lama/impor) tidak dikunci (kunci = satuan dasar) → bagian itu
   "belum terkunci". Roll di-peg (earmark) & ditahan inspeksi tidak dikunci.
7. **Kunci gagal saat lahir tidak menggagalkan** persetujuan PR / pembuatan MKO (dicatat log; cadangan tetap "belum terkunci").
8. **Isi ulang kunci otomatis** saat: issue MKO (sebelum mengirim), cadangan lain dilepas (bahan × PT sama). Tidak di jalur
   pelepasan SO (jalur roll_service yang dipakai semua alur — tidak disentuh agar risiko kecil).
9. **`move_rolls_by_qty` melewati roll ber-reservasi lain** (termasuk reservasi potong SO) — perlu agar tahan/WIP/issue MKO lain
   tidak mengambil panjang terkunci; sekaligus menutup kebocoran lama reservasi potong (perilaku #7 §4).
10. **Pesan lama dipertahankan** bila yang memegang roll bukan kunci makloon (reservasi potong SO: teks & kode HTTP sama seperti
    dulu); teks baru hanya bila ada kunci makloon.
11. **Skrip memakai pagar FIX-7 tersalin (inline)** karena `services/data_fix_guard.py` FIX-7 belum ada di `main`; semantik sama
    (DB uji diterima; `kainnusantara` wajib `--production` + bukti backup < 24 jam, juga untuk dry-run; DB lain ditolak; jejak
    `audit_logs` per perubahan + `migrations.runs[]` + `--undo`). Setelah FIX-7 masuk `main`, cukup ganti ke `data_fix_guard`.
12. **Oracle uji FIX-2** (`test_fix2_stock_figures._truth`) disesuaikan satu baris: mengurangkan `qty − locked_qty` (definisi
    yang sama; tanpa kunci hasilnya identik).
13. **CODEBASE_MAP.md tidak dibangkitkan ulang** (1 service baru, < 10% — penjaga hijau); diserahkan ke integrasi agar tidak
    bentrok dengan paket paralel.

## 6. Tidak dobel-kurang — bukti angka

Uji `test_stock_figures_tidak_dobel_kurang_termasuk_total_grup` (gudang uji: A 40+30, B 100; cadangan 60, gudang sumber A):

| Angka | Sebelum dikunci (FIX-2) | Sesudah dikunci (FIX-9) |
|---|---|---|
| Tersedia (segmen PT) | 110 | **110** |
| Cadangan makloon (kelompok) | 60 (agregat) | **60** (60 terkunci, 0 agregat) |
| Dipesan | 0 | **0** (kunci tidak masuk "Dipesan") |
| Stok Fisik | 170 | **170** |
| Dua angka LOKAL/GLOBAL (Total grup) | 110 / 110 | **110 / 110** |
| Roll tersedia | 3 | **2** (roll 40 terkunci penuh) |
| Kontribusi `allocate_makloon` | 60 | **0** |

Dengan stok kurang (`test_kekurangan_stok…`): cadangan 80, gudang sumber hanya 50 → terkunci 50, belum terkunci 30; Tersedia =
150 − 80 = 70 (sama dengan rumus FIX-2); `free_for_commitment` = 70 (dulu rumus lama akan memberi 40 bila kunci dihitung dua kali).

## 7. Hasil uji & perbandingan regresi

Lingkungan: tumpukan sementara `kn-tmp-fix9-*` (mongo 7 `--memory 1200m --wiredTigerCacheSizeGB 0.5`, backend `kn-dev-backend`
`--memory 1500m`, kode disalin — tanpa mount Windows), DB = salinan data acuan `kn_test_trial_2026-11-08` → `test_database`,
**dipulihkan ulang sebelum setiap putaran**. Tumpukan dihapus sesudah selesai.

### 7.1 Uji baru (gagal di dasar → lulus sesudah)
`backend/tests/test_fix9_makloon_lock.py` — **dasar `main` 7ad4ac4: 0/13 lulus (13 gagal) → FIX-9: 13/13 lulus** (diulang 3×, stabil):

| Uji | Membuktikan |
|---|---|
| `test_kunci_saat_mko_lahir_gudang_sumber_fifo_roll_utuh_dulu` | kunci saat MKO lahir; gudang sumber; FIFO; roll utuh dulu; cermin `locks`; saldo `makloon_locked_qty`; bukan antrean potong; `confirm_cut` 409 |
| `test_pr_disetujui_mengunci_dengan_gudang_pr` | PR **disetujui** (`approve_requisition`) → cadangan lahir & terkunci di gudang PR; replan qty (lepas → cadangkan ulang) tidak lagi DuplicateKey, kunci dilepas lalu dipasang lagi |
| `test_stock_figures_tidak_dobel_kurang_termasuk_total_grup` | §6 (segmen, kelompok status, dua angka, Total grup, baris saldo lama, kontribusi agregat 0) |
| `test_kekurangan_stok_sisa_belum_terkunci_hanya_itu_yang_dialokasikan` | stok kurang → kunci sebagian, sisa belum terkunci saja yang dialokasikan/dilindungi |
| `test_issue_roll_terkunci_sendiri_lepas_atomik_dan_roll_lain_menggantikan_kunci` | issue parsial dengan roll lain → kunci lama dilepas sejumlah itu (`trimmed`) |
| `test_issue_pilih_roll_terkunci_sendiri_boleh_dan_mko_lain_ditolak_menyebut_nomor` | stok sumber layar Issue memasukkan kunci sendiri; MKO lain 409 menyebut nomor MKO; MKO sendiri boleh, kunci lepas |
| `test_issue_jalur_jumlah_memakai_roll_terkunci_dulu` | jalur jumlah: MKO lain tidak mengambil roll terkunci; MKO pemilik memakai roll terkuncinya dulu; konsumsi penuh → kunci 0 |
| `test_release_mko_batal_melepas_semua_idempoten` | batal MKO melepas semua kunci; panggilan ulang 0 |
| `test_paralel_dua_cadangan_tidak_mengunci_panjang_yang_sama` | 2 cadangan paralel (`asyncio.gather`) tidak melebihi stok; 5 `lock` paralel cadangan sama tidak melebihi qty |
| `test_pemilih_roll_dan_so_menolak_panjang_terkunci_menyebut_mko` | pemilih roll (tanpa panjang terkunci; lintas PT tanpa nomor), alokasi SO/POS, beli per roll, transfer, tahan, pengambilan |
| `test_mode_approve_persetujuan_manajer_meminjam_kunci` | approve tanpa persetujuan → `MAKLOON_RESERVED_APPROVAL`; dengan persetujuan → pinjam kunci (`borrowed`), kunci bisa diisi ulang |
| `test_pr_ke_mko_kunci_pindah_ke_gudang_sumber_dan_bernomor_mko` | PR → MKO: kunci pindah gudang sumber, rujukan bernomor MKO |
| `test_skrip_migrasi_dryrun_apply_idempoten_undo_dan_pagar` | dry-run tidak menulis; apply mengunci (Tersedia tetap); ulang = 0 kunci baru; undo; pagar DB (produksi tanpa `--production`/backup & DB asing → kode 2) |

### 7.2 Regresi dasar vs FIX-9 (40 berkas uji terkait, DB salinan yang sama)
Makloon (celup, antrean parsial, PO varian, P05, L03 LN033/034, L04 buku bahan, L01 susut, D2/D3, aud-mkl, phase4 r5/r6),
cadangan (`test_g3_phase02*`, `test_t1_ln033_cancel_edges`, `test_audit_ui2_g4`), angka stok (FIX-2, F2 bucket, global stock,
ATP board), potong/reservasi panjang (F05, CUT01, pick & reallocate, iter270, FIX-3b, L06, L04 MDQ), POS (sample POS, F04 KPI),
alokasi SO (L02 ×2, UAT24 F1/F5, transfer roll iter14).

| Putaran | lulus | gagal | error | dilewati |
|---|---|---|---|---|
| dasar `main` **7ad4ac4** (+ berkas uji FIX-9 baru) | 242 | 57 | 0 | 18 |
| **FIX-9** (sama) | **255** | **44** | 0 | 18 |

* **Gagal hanya di FIX-9: 0.** Gagal hanya di dasar: 13 (= seluruh uji baru FIX-9).
* 44 kegagalan **sama persis** di kedua putaran (lama, di luar paket): `test_iter143_makloon_po_variance` 6, `test_p05_acceptance_acc31_33_34`
  6, `test_p05_restock_material_revalidation` 1, `test_l04_ln043_material_ledger` 2, `test_l01_material_loss` 8,
  `test_f2_stock_buckets` 8, `test_global_stock` 6, `test_iter150_atp_board` 1, `test_f05_cut_child_allocation` 2,
  `test_iter_sample_pos_extra` 2, `test_uat24_f5` 1, `test_iter14_wh_transfer_rolls` 1. (Putaran dasar pertama pada `6b5929e`
  memberi angka yang sama.)

Catatan pelaksanaan: setiap berkas uji dijalankan di **proses pytest terpisah** (seperti pelari regresi). Menjalankan beberapa
berkas dalam satu proses memberi galat "loop berbeda" yang sudah ada sebelum FIX-9 (mis. `test_makloon_celup_rolls` +
`test_fix2_stock_figures` bersama: 6 gagal + 6 error tanpa berkas FIX-9 — pola `_shared_loop` vs `get_event_loop`).

### 7.3 Putaran akhir (kode final) pada data acuan SESUDAH migrasi diterapkan
Uji baru + 14 berkas terkait (FIX-2, celup, antrean parsial, L03 ×3, T1 batal, D2, D3, audit G4, aud-mkl, FIX-3b, pick &
reallocate, L02): **152 lulus · 0 gagal · 6 dilewati**. `test_fix2_stock_figures` 16/16 lulus dengan cadangan data acuan
**terkunci** (oracle `_truth` sadar kunci). Sesudah uji replan ditambahkan: DB dipulihkan ulang, `test_fix9_makloon_lock` 13/13,
`test_fix2_stock_figures` 16/16, `test_makloon_celup_rolls` 20/20 (berkas terpisah).

### 7.4 Asap HTTP (data acuan sesudah migrasi)
`/inventory/rolls/available` DMO-GRY-KNT-001: 110 roll ditawarkan (dulu 121), 1 roll sebagian terkunci `RL-45887` bebas 2,42
dengan `makloon_lock {qty 23.52, numbers ["MKO-00005"]}` untuk admin & sales Kanda; **sales KSC (PT lain): `numbers: []`**;
`makloon_unlocked_qty 0`. `/stock/figures/{id}`: Tersedia 2.697,62 (sama), "Cadangan makloon" 300, "Dipesan" 0. Buku bahan
MKO-00005: dicadangkan 300 · terkunci 300 di 12 roll · belum terkunci 0. Detail MKO langkah 1 `source_stock` SRG-01 477,63
(177,63 bebas + 300 terkunci sendiri). `/inventory/rolls`: 12 roll bertanda kunci MKO-00005. Antrean potong: 0 entri kunci makloon.

### 7.5 Jest (kontainer `node:20` sementara, `node_modules` dari volume `kn-dev_fe_node_modules` read-only, `CI=true`)
| Putaran | Hasil |
|---|---|
| dasar 7ad4ac4 — 8 suite terkait (`fix9KunciMakloon` baru, `fix8StandarUi2`, `phase5MakloonRolls`, `fix5PerformaWms`, `phase4R3`, `phase4R8`, `uatV3ReturnsOps`, `stockFigures`) | 7 suite lulus (73 uji) · **`fix9KunciMakloon` GAGAL** (komponen/kode status belum ada) |
| FIX-9 — 8 suite yang sama | **8/8 suite · 79/79 uji lulus** |
| FIX-9 — Jest penuh (`--maxWorkers=2`) | **89/89 suite · 645/645 uji lulus** |
| ESLint berkas FE yang diubah/baru | 0 galat; 2 peringatan lama di `RollGroupView.jsx` (direktif `eslint-disable` tak terpakai, baris FIX-5 yang tidak disentuh) |

### 7.6 Guardrail (`PYTHONUTF8=1 python scripts/guardrails/verify_*.py`, host; `verify_state_machine` tidak dijalankan)
Dasar = `main` 7ad4ac4 (diekstrak dengan `git archive`), FIX-9 = branch ini; 43 guardrail dijalankan di keduanya.

* **Kode keluar sama di 43/43.** Hijau di keduanya, antara lain `verify_ui_standard` (PASS 5691 cek; ratchet FIX-8 **tidak naik**:
  `chip_custom` 560 = 560 · `font_lt12` 6914 · `hex` 16729 · `id_fallback` 163 · `date_no_wib` 139 · `empty_false` 308 — sama
  persis dengan dasar), `verify_ui_contrast` 67/67, `verify_scope_guard` HIJAU, `verify_codebase_map` PASS, `verify_roll_identity`,
  `verify_rfid_tag_unique`, `verify_status_history`, `verify_custom_modals` 49/51 = baseline.
* **Merah lama, jumlah pelanggaran sama** (dasar = FIX-9): `verify_atomic_claim` 6 · `verify_auth_coverage` 28 ·
  `verify_entity_label` 2 · `verify_line_scope` 1 (`sales_order_helpers.py` belum menyebut `line_scope` — sudah merah di dasar,
  FIX-9 tidak menambah) · `verify_no_secrets` 8 (berkas `test_reports/`) · `verify_numeric_bounds` 3 · `verify_page_tabs` 1 ·
  `verify_qty_dual` 28 · `verify_to_list_bound` 20 (pemisah jalur Windows di host). Tidak bisa jalan di host (modul `motor`/`httpx`
  tidak terpasang / jalur Windows), sama di dasar: `verify_concurrency`, `verify_cross_entity`, `verify_nonfinancial_sweep`,
  `verify_ref_unlink`, `verify_home_kpi`.

## 8. Cara menjalankan migrasi di produksi

1. Cadangkan: `bash deploy/backup.sh` (menulis `deploy/backups/kainnusantara-YYYY-MM-DD_HHMM.archive.gz`).
2. **Dry-run** (wajib dulu; tidak menulis apa pun):
   ```
   docker compose exec backend python /app/scripts/fix_data_2026_11_10_fix9_kunci_makloon.py \
       --db kainnusantara --production --backup-file kainnusantara-2026-11-10_2100.archive.gz \
       --report /tmp/fix9_dryrun.json
   ```
   Periksa per cadangan: dokumen MKO/PR, qty, terkunci sebelum → sesudah, gudang sumber, roll yang akan dikunci, kekurangan.
   Kekurangan > 0 berarti stok roll bebas di gudang sumber kurang (bagian itu tetap dikurangkan sebagai "belum terkunci").
3. **Terapkan:** perintah yang sama + `--apply`. Ulang `--apply` aman (idempoten: hanya mengisi kekurangan kunci).
4. **Batalkan** (bila perlu): `… --production --backup-file … --undo --apply` — melepas kunci yang dibuat putaran terakhir.
5. Urutan dengan kode: jalankan **sesudah** kode FIX-9 ter-deploy (kode baru mengunci cadangan yang lahir sesudahnya; skrip
   mengunci yang lahir sebelumnya). Tanpa skrip, cadangan lama tetap aman secara angka (dikurangkan agregat seperti FIX-2), hanya
   belum terlindung di tingkat roll.
6. Data acuan (salinan uji 8 Nov) — hasil nyata:

   | Langkah | Hasil |
   |---|---|
   | dry-run | 2 cadangan aktif; `MKO-00005` (Kanda, 300 kg, gudang sumber dari MKO = SRG-01): 12 roll `RL-45876…RL-45887`; `KSC/MKO-00082` (KSC, 75 kg, WH-JKT): 4 roll (`RL-05000` 0,22 sebagian); kekurangan 0; **tidak ada yang ditulis** (0 roll berkunci, 0 dokumen `migrations`) |
   | `--apply` | 16 roll dikunci (375 kg); 2 baris `audit_logs` `data_fix_applied` + 2 `makloon_locked`; putaran tercatat di `migrations` |
   | `--apply` ulang | `qty_locked_new 0` (idempoten) |
   | angka sesudah | Tersedia GLOBAL & PT **sama persis** (2.697,62 / 177,63 kg; 5.609,33 / 2.365,75 kg), "Cadangan makloon" 300 / 75 (agregat 0), Dipesan 0 / 0, Stok Fisik sama; roll tersedia 121 → 110 (Kanda 19 → 8) dan 230 → 227 (KSC 100 → 97) |
   | `test_fix2_stock_figures` sesudah apply | 16/16 lulus |

## 9. Sisa / langkah lanjut

* Kunci yang **dipinjam** SO (mode approve) tidak kembali otomatis bila SO itu batal — diisi ulang saat issue MKO, saat cadangan
  lain dilepas, atau dengan skrip (bisa dijadwalkan). Jalur pelepasan SO di `roll_service` sengaja tidak disentuh.
* Tidak ada mekanisme **kedaluwarsa** cadangan/PR di kode (brief menyebut "kedaluwarsa") — bila nanti ditambah, panggil
  `material_reservation_service.release`.
* Roll terkunci **tidak bisa** ditransfer/PA/opname-sesuaikan/retur supplier sampai dilepas (sama dengan reservasi potong);
  pesan di jalur PA/transfer/opname/retur masih generik ("reservasi potong") — tidak disentuh (wilayah FIX-6/FIX-7/lainnya).
* `allocate_makloon` belum dihapus (brief) — setelah migrasi produksi & tidak ada sisa belum terkunci, bisa dipertimbangkan
  (tetap perlu untuk kekurangan stok).
* `CODEBASE_MAP.md`/`ENTITY_REGISTRY.md` belum memuat `makloon_roll_lock.py` & field baru (`locked_qty`, `locks`,
  `source_warehouse_id`, `makloon_locked_qty`) — integrasi.
* Verifikasi tampilan di peramban (lencana di daftar roll, pemilih roll HP 360 px) — koordinator.

## 10. Berkas berisiko bentrok

| Berkas | Perubahan FIX-9 | Paket lain yang mungkin menyentuh |
|---|---|---|
| `backend/services/stock_figures.py` | `makloon_by_product_entity` (sisa belum terkunci), `segments` (4 baris pindah kunci → "Cadangan makloon"), `_empty_totals`/`sum_segments` (`makloon_locked_qty`), `adjust_balance_row` (`reserved_qty`), docstring | **FIX-7** (optimasi pembaca `stock_figures`) — perubahan dibuat minimal & berdiri sendiri |
| `backend/services/roll_service.py` | `rebuild_balance` (+`makloon_locked_qty`), `pending_cuts`, `confirm_cut`, `makloon_guard`, `allocate_and_reserve_rolls` (pinjam kunci), `list_available_rolls`, `reserve_specific_rolls` (pesan) | FIX-7 (performa), FIX-6 (retur) |
| `backend/services/stock_bucket_service.py` | `move_rolls_by_qty` (lewati roll ber-reservasi lain, kunci sendiri dulu), `move_specific_rolls`, `issue_*_to_subcon` (`own_lock_ids`) | FIX-7 |
| `backend/routers/products.py` (matriks rincian produk), `backend/routers/inventory.py` (pemilih roll, 3 baris), `backend/routers/outbound_picking.py` (pesan) | kecil | FIX-7 (daftar/performa) |
| `backend/services/makloon_order_service.py`, `makloon_issue_rolls.py`, `makloon_material_ledger.py`, `material_reservation_service.py` | jalur issue/cadangan | — |
| `backend/services/sales_order_helpers.py`, `sales_p04_service.py`, `rnd_sample_service.py`, `sample_sale_service.py` | pesan / satu rumus | — |
| `frontend/src/utils/statusVocab.js` | + kode `makloon_reserved` (tambahan, 3 baris) | FIX-8 (pemilik kosakata) |
| `frontend/src/components/RollPicker.jsx`, `features/wms/inventory/{RollsTable,RollGroupView,inventoryConstants}.jsx`, `features/purchasing/makloon/{MakloonMaterialLedger,MkoIssueRollPicker}.jsx` | lencana & catatan | FIX-8 (layar WMS) |
| `backend/tests/test_fix2_stock_figures.py` | 1 baris oracle `_truth` | FIX-7 bila menyentuh uji FIX-2 |
| Baru: `backend/services/makloon_roll_lock.py`, `components/MakloonLockBadge.jsx`, `scripts/fix_data_2026_11_10_fix9_kunci_makloon.py`, uji `test_fix9_makloon_lock.py`, `fix9KunciMakloon.test.js` | — | FIX-7 `data_fix_guard.py` (pagar skrip — semantik disalin; ganti sesudah FIX-7 masuk) |

---

### Ringkasan untuk koordinator

* **Ditutup:** B3a **SSOT-4** (P0) + keputusan **B3a #1** tuntas (langkah lanjut FIX-2 §5 butir 1 & 5). Cadangan makloon dikunci
  di roll nyata (skema `length_reservations` WM-02 yang sama, `ref.type = "makloon"`) saat MKO dibuat / PR disetujui; lepas per
  roll saat issue (roll lain menggantikan kunci → kunci lama dipangkas), lepas semua saat batal/tolak/selesai/replan; CAS per roll
  + mutex per cadangan; jejak `history` + `audit_logs`.
* **Angka tidak dobel-kurang:** `allocate_makloon` tetap ada, kini hanya sisa **belum terkunci**; kunci tampil di "Cadangan
  makloon" (bukan "Dipesan"). Data acuan sesudah migrasi: Tersedia, kelompok status, Stok Fisik **sama persis**; roll tersedia
  turun sebanyak roll terkunci penuh.
* **Permukaan:** pemilih roll desktop & HP, alokasi SO/POS, beli per roll, transfer/ganti roll, tahan/WIP, issue MKO lain,
  pengambilan, potong sampel — panjang terkunci tidak bisa diambil; pesan menyebut MKO/PR (lintas PT tanpa nomor).
  Lencana `StatusBadge` "Dicadangkan makloon · MKO-…" (kode `makloon_reserved` di `statusVocab`) di daftar roll, penampil roll,
  pemilih roll, pop-up Issue; buku bahan MKO menampilkan roll terkunci.
* **Keputusan implementer penting:** FIFO; mode `approve` = persetujuan manajer **meminjam** kunci (cadangan tetap, sisa jadi belum
  terkunci); gudang sumber tegas (kekurangan → belum terkunci); `move_rolls_by_qty` kini melewati roll ber-reservasi lain
  (termasuk potong SO — kebocoran lama ikut tertutup); id cadangan unik (replan PR dulu 500 sejak `uq_id` FIX-5).
* **Uji:** baru 13/13 (dasar 0/13); regresi 40 berkas dasar `7ad4ac4` vs FIX-9 = 242→255 lulus, **0 gagal baru** (44 gagal lama
  identik); putaran akhir sesudah migrasi 152/0; Jest terkait 79/79 (dasar: suite FIX-9 gagal), Jest penuh 645/645; ESLint 0
  galat; guardrail tidak naik (§7.6).
* **Migrasi produksi:** `scripts/fix_data_2026_11_10_fix9_kunci_makloon.py` — dry-run bawaan, `--apply`, `--undo`, `--only`;
  produksi wajib `--production` + bukti backup < 24 jam (pagar FIX-7 disalin karena `data_fix_guard` belum di `main`). Jalankan
  sesudah deploy kode; idempoten. Data acuan: 2 cadangan → 16 roll, kekurangan 0.
* **Bentrok:** `stock_figures.py` (perubahan minimal, FIX-7), `roll_service.py`, `stock_bucket_service.py`, FE roll/pemilih
  (FIX-8) — §10. **Sisa:** kunci yang dipinjam SO tidak kembali otomatis saat SO batal; tidak ada mekanisme kedaluwarsa cadangan;
  pesan jalur PA/transfer/opname/retur masih generik; peta kode/registry; cek tampilan di peramban.
* Tidak ada push/merge; `TRACKER.md` tidak diubah.
