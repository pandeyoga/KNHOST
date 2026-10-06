# Gelombang 3 · Fase 01 — status implementasi (2026-10-06)

Actual HEAD sebelum perubahan: `f36ae37` (baseline audit `a904d98`). Commit implementasi: commit otomatis platform sesudah `f36ae37`.
Status tertinggi yang dipakai agent: `implemented_pending_validation`. `verified_fixed` hanya oleh reviewer independen.

Bukti uji baru (terpisah dari evidence baseline): `backend/tests/test_g3_phase01.py`
(fault-injection di DB uji sendiri, bukan data pelanggan):
`cd backend && DB_NAME=g3_audit_phase01 python -m pytest tests/test_g3_phase01.py -q` → **28 passed** (13 agen + 15 ditambah reviewer pengujian, `test_reports/iteration_162.json` & `iteration_163.json`). Regresi API hanya cek respons endpoint (bukan alur penuh).
Batas uji: MongoDB produksi/preview **standalone (tanpa replica set) → tidak ada transaksi multi-dokumen**.
Perbaikan memakai write-ahead marker / id deterministik / klaim CAS. Kegagalan berupa *exception* sudah tertutup.
*Crash proses* di antara dua write dapat dipulihkan pada retry berikutnya untuk ID yang ditandai "retry-resume". Tidak ada sweeper latar belakang.

| ID | Validasi temuan | Status | Perubahan | Bukti uji |
|---|---|---|---|---|
| V3-PROD-01 | VALID — CAS roll sebelum movement; retry konsumsi ulang | implemented_pending_validation | `production_service._consume_material`: movement `pending` + `wal` dulu, CAS roll menulis `op_marks` atomik, `reconcile_pending_consumes` | fault CAS & fault unset-pending → 20→15, 1 movement aktif |
| V3-PROD-02 | VALID — movement ditandai reversed sebelum restore | implemented_pending_validation | `reverse_operation`: restore + cabut `op_marks` satu update ber-syarat; movement pembalik id deterministik `rev_<mov>`; jalur lama (tanpa `wal`) dipertahankan | fault restore / insert pembalik / tandai reversed + panggilan ulang → roll 10, 1 pembalik |
| V3-AR-01 | VALID — exception setelah alokasi SO tidak membatalkan payments | implemented_pending_validation | `create_receipt`: `effects_done`; rollback mencari `payments.receipt_id` dari data, void kas + jurnal void, balik reklas deposit, hapus kwitansi belum tuntas (arsip `ar_receipt_failures`), kembalikan deposit | uji ditambah reviewer (iteration_162): exception setelah alokasi → tidak ada payments tersisa, deposit kembali |
| V3-BANK-01 | VALID — baris mutasi tidak diklaim | implemented_pending_validation | `_link`: klaim `match_lock` (CAS status, kunci basi 10 menit) sebelum kapasitas kas; dilepas saat gagal | 2 pencocokan paralel → 1 sukses, 1 konflik, reconciled 100 |
| V3-MKO-01 | VALID — progres output disimpan setelah seluruh loop | implemented_pending_validation | id roll deterministik `roll_mko_<mko>_<seq>_<i>` (`create_inbound_roll(roll_id=…)` idempoten + movement upsert), progres disimpan per roll | uji ditambah reviewer (iteration_162) — lulus |
| V3-MASTER-01 | VALID — batch disisip setelah produk diubah | implemented_pending_validation | batch `applying` + rencana before/after durable dulu; rollback menerima `applying`, CAS `field==after` & `last_governance_batch` | fault finalize → batch `applying` → rollback memulihkan |
| V3-CUT-01 | VALID — induk dikurangi sebelum anak lahir | implemented_pending_validation | `pending_cut_ops` ditulis di update CAS induk yang sama; `_finish_cut` idempoten (anak `roll_cut_<rsv>`, movement `mov_cut_<rsv>`); retry melanjutkan | fault insert anak / movement → induk 70, 1 anak, 1 movement, potong kedua ditolak |
| D4-GL-01 | VALID — void mengabaikan `reversed_by_entry_id` | implemented_pending_validation | `void_entry` menolak bila sudah/sedang dibalik (cek + filter CAS); `reverse_entry` sudah menolak status void | void setelah klaim pembalik ditolak, jurnal tetap posted |
| D4-GL-02 | VALID — NaN/Infinity lolos perbandingan | implemented_pending_validation | `create_manual_entry` menolak nilai tak terhingga sebelum validasi lain | NaN/Inf → ValueError, 0 jurnal |
| D4-ASSET-01 | VALID — klaim periode sebelum jurnal tanpa resume | implemented_pending_validation | klaim + `depreciation_claims` (basi 10 menit boleh diambil alih), adopsi jurnal idempoten, entri id deterministik, register diterapkan sekali (`applied_periods`) | fault sesudah jurnal → retry: 1 jurnal, 1 entri, akumulasi 100 |
| D4-ASSET-02 | VALID — `$set` snapshot lintas periode saling menimpa | implemented_pending_validation | `_apply_dep_to_register` pipeline `$add` atomik | Jan+Feb paralel → akumulasi 200, 2 bulan, nilai buku 1000 |
| D4-CLOSE-01 | VALID — reopen tidak menandai parent basi | implemented_pending_validation | `reopen_period` menandai penutupan pemuat `stale` (sama seperti reclose) | uji ditambah reviewer (iteration_162) — lulus |
| D4-CC-01 | VALID — retry membuat hasil & nomor baru | implemented_pending_validation | hasil id deterministik `rcc_<session>`; retry mengadopsi hasil lama dan memfinalkan sesi | uji ditambah reviewer (iteration_162) — lulus |
| D4-BACKORDER-01 | VALID — `_fill_order` tanpa klaim demand | implemented_pending_validation | klaim saga SO + baca ulang sebelum reservasi; sibuk → dilewati (auto) / 409 (Admin Sales) | uji ditambah reviewer (iteration_162) — lulus |
| D4-OD-LOCK-01 | VALID — kunci harga tercatat sebelum SKU; retry ditolak | implemented_pending_validation | `sku_synced=False` saat kunci; retry melanjutkan sinkron SKU **dan PO otomatis** (keputusan user; `auto_procure` idempoten) | belum ada uji otomatis khusus resume PO |
| D4-CASE-01 | VALID — `adjust` (Cr pendapatan lain) + kas = kewajiban berkurang dua kali | implemented_pending_validation | baris buku `payout` tanpa jurnal sendiri; satu jurnal dari transaksi kas (Dr 2-1450/Cr Kas); kas gagal → baris pembalik | uji ditambah reviewer (iteration_162) — lulus |
| D4-CASE-02 | VALID — tidak ada klaim aksi; kas UUID baru tiap percobaan | implemented_pending_validation | `resolve` klaim saga kasus (precondition status+documents) sebelum efek, dilepas di `finally`; `_cash_txn` id deterministik `cash_case_<kasus>_<aksi>_<ndok>_<n>` + adopsi kas/jurnal | iteration_163: paralel → 1 sukses/1 konflik, 1 kas; fault sesudah kas → retry adopsi |
| D4-CASE-03 | VALID — langkah 2 tanpa cek langkah 1/sisa | implemented_pending_validation | `act_setor_dari_karyawan`: wajib sesudah langkah 1, setoran sebagian tetap `in_progress` (held/settled/remaining). **Keputusan user:** kelebihan setoran → kredit toko pelanggan (kas Dr Kas/Cr 2-1450 + `store_credit_service.issue`); tanpa pelanggan → ditolak | iteration_163 + uji kelebihan 100 vs 80 → kredit toko 20 |
| D4-INTERCO-01 | VALID — guard OR + dokumen transfer ditulis terakhir | implemented_pending_validation | `post_intercompany_transfer` guard per sisi (sisi hilang diposting, nilai ikut sisi yang ada); retur: dokumen transfer `executing` durable sebelum efek, `_finish_return_transfer` melanjutkan, rollback hanya bila kepemilikan belum pindah | iteration_163: fault JE dst → retry hanya dst, pasangan bertaut, riwayat tidak dobel |
| D4-INTERCO-02 | VALID — WAC live sumber dipakai setelah roll keluar | implemented_pending_validation (kebijakan: biaya aktual roll — mohon dikonfirmasi) | `execute_ownership_transfer` menyimpan `unit_cost_snapshot` per produk (rata-rata tertimbang roll yang dipindah) sebelum pindah; valuasi memakai snapshot, fallback WAC | iteration_163: roll 10×15, master 1 → JE 150, `roll_snapshot` |
| D4-CLOSE-02 | VALID — tidak ada adopsi JE baru; kunci menggantung | implemented_pending_validation | adopsi JE penutup aktif yatim (source_id sama) sebelum void/insert; kunci saga dilepas saat gagal | iteration_163: fault parent → retry: 1 JE aktif, parent menunjuk, stale False |
| D4-PA-02 | VALID — roll pindah sebelum tag/mutasi; retry ditolak | implemented_pending_validation | penanda `last_pa_landed` di CAS roll; retry mengadopsi roll yang sudah pindah; mutasi id deterministik `mov_pa_*` upsert; kunci saga dilepas saat gagal | iteration_163: fault mutasi → retry: 2 mutasi/roll, PA completed |
| D4-RFID-01 | VALID — observasi durable = dianggap selesai | implemented_pending_validation | observasi `processed:false` → event sama yang belum tuntas diproses ulang; read id deterministik `rread_<obs>` upsert; stamp exit SESUDAH read durable; hitungan passage hanya read baru; `processed:true` di akhir | iteration_163: fault read → kirim ulang event sama → 1 read, processed |

Risiko/migrasi:
- Field baru tanpa migrasi wajib: `op_marks`, `pending`/`wal` (movement), `pending_cut_ops`, `match_lock`, `effects_done`, `deposit_credited`, `applied_periods`, `depreciation_claims`, `pricing.sku_synced`, `lots_partial`, `unit_cost_snapshot`, `last_pa_landed`, `processed` (observasi RFID), `held_amount/settled_amount` (kasus karyawan).
- Dokumen transfer retur kini sempat berstatus `executing` sebelum `completed`.

Keputusan bisnis Fase 01 (dijawab user 2026-10-06):
1. D4-CASE-03 — kelebihan setoran karyawan → kredit toko pelanggan. DITERAPKAN.
2. D4-INTERCO-02 — biaya aktual roll yang dipindah. DIKONFIRMASI.
3. D4-OD-LOCK-01 — retry juga membuat PO otomatis. DITERAPKAN.
4. V3-AR-01 — kwitansi gagal dihapus + diarsipkan. DIKONFIRMASI.
- Data lama tetap memakai jalur lama: movement tanpa `wal`, aset tanpa `applied_periods`, kwitansi tanpa `effects_done`.
- Movement `pending` sempat terlihat oleh laporan selama beberapa milidetik.
- Kwitansi yang gagal dihapus dari `ar_receipts` (nomornya terlewat) dan diarsipkan di `ar_receipt_failures`.
- `findings-tracker.json` baseline **tidak ditimpa**; status di atas adalah sumber status Fase 01.
