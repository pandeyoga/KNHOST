# FIX-3b — Integritas alur BARANG KELUAR, POTONG, SAMPEL, transfer/makloon/perbaikan keluar & siklus TAG RFID

- Tanggal: 9 Nov 2026 (WIB, selesai ±16.30) · Pelaksana: Claude Code (paket perbaikan FIX-3b) · Branch worktree
  `worktree-agent-a16186547a0dd94ed` (dasar `main` `5b65039` = gelombang 1–3 + FIX-2 + FIX-3a; sesudah uji
  regresi, `main` terbaru `59bdc68` (= + FIX-1) DIGABUNG ke branch ini tanpa konflik teks — lihat §6.5).
- Bahan: audit B2b (`B2b-ALUR-KELUAR-POTONG-RFID.md` + lampiran transisi SO/ambil/kirim, potong/sampel/non-SO, RFID),
  B3b (`B3b-FORM-INPUT-DAFTAR.md` FRM-03/11, K-B3b-01/02/08), B3a (SSOT-1/8, STK-11), B1 (K-B1-05), keputusan
  koordinator FIX-3 bagian "Alur keluar, potong & RFID (FIX-3b)", pola FIX-3a (`input_rules.py`, `inbound_task_state.py`).
- Lingkungan uji: stack sementara `kn-tmp-fix3b-*` (salinan `kn_test_trial_2026-11-08`, dipulihkan sebelum tiap putaran;
  server dasar `/app_base` vs kode FIX-3b `/app` pada kontainer yang sama), tanpa mount folder Windows, tanpa peramban.
  Stack bersama `kn-uji-*` & DB koordinator tidak disentuh.

---

## 1. Temuan yang ditutup (ID → perubahan → uji)

Uji baru: `backend/tests/test_fix3b_outbound_integrity.py` (**26 uji**) dan `frontend/src/features/__tests__/fix3bForms.test.js`
(**4 uji**). Kolom "Uji" = nama fungsi uji.

### 1.1 P0 (B2b) + kandidat calon P0
| ID | Perubahan | Uji |
|---|---|---|
| **STM-OUT-1** (+K-B2b-01) | `resolve-escalation`: (a) tugas yang sudah terkirim sebagian hanya **"tutup sisa"** (`close_remainder=true`, atau `adjusted_qty` = qty yang sudah diambil; nilai lain 400); (b) `release_order_rolls_partial(…, exclude_roll_ids)` hanya melepas roll **belum berangkat** (`RELEASABLE_HELD_STATUSES` = reserved/committed/picked/packed) dan **bukan** roll yang sudah dipindai/di-SJ tugas itu; (c) sisa < satu roll **tidak lagi memecah roll fisik** (fragmen tanpa tag) — roll dilepas utuh lalu bagian yang masih dibutuhkan menjadi **reservasi potong** (WM-02) + entri alokasi `pending_cut`; (d) status sesudah putusan = **turunan progres** (`dispatched` bila terkirim penuh, bukan `packing` macet) + `recompute_so_status`. `release_order_rolls` & `set_order_rolls_status` juga tidak pernah menyentuh `in_transit_sales`. | `test_resolve_escalation_never_releases_shipped_roll` |
| **STM-OUT-3** | Override SO: `_held` = semua status pra-kirim (reserved/committed/picked/packed) + reservasi potong; roll tambahan pada SO `approved/confirmed` langsung `committed`; tugas gudang **disesuaikan** (qty/alokasi diperbarui, alokasi baru → tugas baru, alokasi hilang → `cancelled` berjejak) — tidak lagi dihapus-buat-ulang. Pola sama di **Ganti Roll** & **Lepas sebagian** (roll `committed` kini terlihat; pengganti ikut `committed`; pelepasan Ganti Roll kini bermutasi `release_reservation`). | `test_override_keeps_committed_rolls_and_task_ids` |
| **FLW-OUT-2** (+K-B2b-02) | Backorder `ACTIVE` kini memuat `partially_picked/picked/partially_shipped` (isi otomatis & "rencana pemenuhan"); roll baru langsung `committed` + tugas ambil baru. Pesan 409 dibedakan: status tidak bisa diisi vs sedang diproses. **POD per SJ**: `so_delivery_service.on_pod` → `deliver_podded_shipments` → roll di `shipments.rolls[]` SJ ber-POD `in_transit_sales → delivered` (CAS) walau SO masih kirim sebagian; penutupan SO `done` kini **CAS SO dulu, baru roll** (juga `mark-delivered` manual). | `test_backorder_fillable_after_partial_ship`, `test_pod_per_shipment_delivers_its_rolls` |
| **CUT-1** | Satu fungsi `roll_service.free_length` (sisa − reservasi potong) dipakai potong sampel (`_resolve_roll` 409 `ROLL_LENGTH_RESERVED`, `suggest_roll`, CAS `$expr` panjang bebas + pengurangan & pembulatan dalam SATU update pipeline), sampel R&D (`rnd_sample_service`), potong MDQ (`mdq_cut_service`). | `test_sample_cut_respects_reserved_length` |
| **CUT-3** (+K-B2b-10) | `cutting_service.receive`: tugas terminal (batal/terkirim) → **409**, klaim berprasyarat status hidup. Lokasi Admin Cutting ≠ gudang roll → **transfer internal** dibuat (`purpose=cutting_handoff`, `waiting_approval`, roll tetap berkomitmen ke SO via `transfer_ref`), roll **tidak dipindah langsung**; tugas ditandai `cutting_handoff_pending`; "Terima" lagi sesudah barang tiba = serah-terima di lokasi yang sama. Meja Cutting menampilkan "Menunggu transfer …". | `test_cutting_receive_rejects_cancelled_and_cross_warehouse_needs_transfer` |
| **RFID-2** | `encode_tag`: EPC yang **pernah** terbit (status apa pun) ditolak 409; EPC sistem dicari ulang sampai belum pernah ada. Pencarian EPC hanya tag hidup (`active/pending_print`): `/rfid/lookup`, potong sampel, makloon issue, terima transfer; EPC handheld (`handheld_tags.epc_free`) juga tidak pernah memakai EPC pensiun. | `test_retired_epc_never_reused_and_lookup_ignores_retired` |
| **MKO-03** (calon P0 → **terbukti** kode + uji, diperbaiki) | `stock_bucket_service.move_rolls_by_ref` tidak lagi memindah roll terminal (`consumed/delivered/cancelled/sold`); parameter `from_statuses`; retur bahan makloon memakai `from_statuses=["subcon"]`; CAS status per roll. | `test_subcon_return_does_not_revive_consumed` |
| **PRT-01/02** (calon P0 → **terbukti**, diperbaiki) | `purchase_return_service.reverse_settlement` mencari mutasi `return_out` **dan** `qc_reject_return`; tanpa mutasi → ditolak (jurnal & AP tidak dibalik tanpa barang kembali). PRT-05: roll tolak QC kembali ke **karantina** (bukan `available`), CAS status. | `test_qc_return_reversal_restores_rolls` |
| **ANOM-06** (calon P0 → **terbukti**, diperbaiki) + K-B2b-12 + B3a STK-11 | Kedaluwarsa reservasi hanya SO `reserved/waiting_approval` (bukan `approved/waiting_stock`), diklaim per SO (saga) sebelum roll dilepas; dipindah ke **job penjadwal** `reservation_expiry` (30 menit); GET `/sales-orders`, `/sales-orders/stats/summary`, `/dashboard`, `/products` tidak menulis lagi. | `test_reservation_expiry_skips_approved_and_get_does_not_write` |
| **POT-05** (calon P0 → **terbukti**, diperbaiki) | `reserve_specific_rolls`: rollback **sempit** (`_rollback_reserved`) — hanya roll/reservasi potong yang dibuat panggilan itu; reservasi lain milik SO tetap. | `test_reserve_specific_rolls_rollback_keeps_other_reservations` |

### 1.2 P1
| ID | Perubahan | Uji |
|---|---|---|
| STM-OUT-2 / STM-OUT-6 (tugas ambil) | Tabel transisi BARU `backend/services/outbound_task_state.py` (daftar-izin + CAS + `status_history` SSOT): `release`, `scan_pick`, `escalate`, `resolve_escalation`, `dispatch`, `advance`, `cancel`. `scan-pick` menolak `escalated/scheduled/terminal`; `resolve` hanya dari `escalated` (409) dan status sesudahnya turunan progres; batal SO menutup tugas lewat CAS dan **eskalasi menunggu ikut `cancelled`**; rilis manual tugas terjadwal ber-CAS. | `test_escalated_task_rejects_pick_and_cancelled_task_not_revived` |
| STM-OUT-4 | Batal SO melepas roll untuk status non-terminal **apa pun** (termasuk `draft`); Ganti Roll pada `draft` → 409. | `test_draft_so_cannot_hold_rolls_and_cancel_releases_any_status` |
| STM-OUT-5 | `ship_order_rolls`: kirim = **roll utuh** (rencana dihitung dulu; roll yang harus dipecah → 409 "potong lewat reservasi potong"); CAS per roll + kompensasi bila kalah di tengah. `scan-pick`: qty < panjang roll → 400; roll yang sama dua kali → 409. | `test_pick_requires_scan_and_whole_roll` |
| K-B1-05 / K-B3b-01 (B3b FRM-03) | Ambil **wajib pindai roll** di server, HP & desktop: tanpa kode roll = **jalur darurat** hanya pemegang `wms.approve` + alasan K-14, tercatat `scan_log.manual_entry` + audit. HP `OutboundActions` ditulis ulang: kolom pindai/ketik **no. roll** + daftar roll yang harus diambil (`PickListPanel`, sama dengan desktop); qty hanya di jalur darurat; tugas dieskalasi tanpa aksi. Desktop sudah memindai roll (tidak diubah, + petunjuk kirim sebagian = roll utuh). | `test_pick_requires_scan_and_whole_roll`, Jest "HP Ambil …" (3) |
| FLW-OUT-4 | Batal SO sesudah ambil: roll yang sudah dipindai-ambil (dan roll anak potong sampel) dilepas dengan **bin dikosongkan** + penanda `return_to_rack{from_bin_id, order_id, why}` → masuk antrean **Penempatan Rak** (kembalikan ke rak, bin dipindai saat ditaruh); mutasi bercatatan. | `test_cancel_after_pick_returns_to_rack_and_closes_escalation` |
| FLW-OUT-11 (+K-B2b-03) | **Transfer** `dispatched` dibatalkan → status `returning` (alasan K-14, `return_requested`), roll tetap `in_transit_transfer`; "Terima per roll" pada transfer `returning` menerima di **gudang asal**; semua kembali → `cancelled` (`completion_basis=returned_to_source`), penanda `transfer_prior_status` dibersihkan, sesi gate ditutup. **Perbaikan** `sent` dibatalkan → `returning`, roll tetap `wip`; endpoint baru `POST /repair-orders/{id}/receive-back` → status asal, semua kembali → `cancelled` + sesi gate ditutup. FE: label "Batal — kembali ke asal", tombol "Terima kembali (batal)". | `test_cancel_in_transit_transfer_becomes_returning`, `test_cancel_sent_repair_becomes_returning` |
| CUT-2 (+K-B2b-06/K-B3b-07) | Konfirmasi potong: susut > `cutting.waste_limit_pct` (bawaan 3 % dari panjang potong) wajib alasan K-14 (`waste_reason`); setiap susut > 0 **dijurnal** write-off (Dr beban penghapusan / Cr persediaan, nilai = susut × biaya roll, `source_id=cutw:<rsv>`, idempoten). FE Antrean Potong: isian "Alasan susut". | `test_cut_waste_journal_limit_and_remnant` |
| RFID-1 / RFID-9 (+K-B2b-09) | Penanda perangkat **`test_device`** (admin, toggle di layar Perangkat RFID). Simulator V2 (`rfid_v2_simulator.run` — **hanya berkas ini** di jalur V2) menolak 409 `SIMULATOR_NOT_ALLOWED` bila perangkat bukan uji **atau** Mode simulasi PT dokumen mati → tidak ada klaim/bukti simulasi pada data nyata; roll contoh "asing/karantina" diambil dari PT dokumen. RFID-9: simulator tidak bisa lagi menerima/mengirim barang di reader produksi walau mode simulasi menyala; **skrip data** mematikan mode simulasi 3 PT nyata (dry-run, §7). | `test_v2_simulator_requires_test_device`, uji lama D1/D2 disesuaikan |
| RFID-3 (+K-B2b-13, selaras PREP-F) | `mark-printed` manual untuk label **RFID**: item `encode_status=unverified`, tag tetap **`pending_print`** (jejak `printed_unverified`); aktif hanya bila EPC-nya **terbaca di sesi Verifikasi** nyata (`_activate_proven_tags`, bukti `chip_evidence`); label teks/QR tidak berubah. FE: pesan "jalankan Verifikasi". | `test_mark_printed_rfid_needs_chip_proof` |
| RFID-4 | `/rfid/gate/simulate` hanya perangkat uji + PT bermode simulasi (409). Ingest `source=simulated`: bacaan bertanda `simulated`, **tanpa** `gate_exit`, insiden/alarm, "terakhir terlihat" tag; dedup bacaan simulasi dan nyata dipisah. | `test_legacy_gate_simulator_requires_test_device` |
| RFID-5 | `/rfid/ingest` menolak perangkat `type=handheld` (409 `HANDHELD_SESSION_REQUIRED` — jalur `/api/handheld` + sesi operator). | `test_handheld_key_rejected_on_legacy_ingest` |
| RFID-12 | `loading_check_service.gate_out_state`: gedung gate membebaskan wajib cek muat **hanya bila ≥1 reader OUT tertaut `enabled` & sehat** (aturan `rfid_v2_health.evaluate` READER_STOPPED/TELEMETRY_STALE, dibaca saja); selain itu cek muat handheld wajib lagi + alasan tampil (`gate_out_reason`, FE). | `test_gate_exemption_requires_healthy_out_reader`, D2 disesuaikan |
| K-B3b-02 (B3b FRM-11) | EPC cek muat yang **ditempel/diketik** (sumber `manual`) dicatat (`manual_epcs`) tetapi **bukan bukti**: hasil `manual_unverified` → kirim diblokir (pesan jelas) kecuali override berizin + alasan. Sumber `device` dari layar pengguna ditolak 400 (hanya jalur ber-key perangkat). FE: tombol "Catat EPC (manual)". | `test_loading_check_manual_epc_not_proof_and_expected_refreshed`, Jest "cek muat …" |
| K-B3b-08 (B3b FRM-22) | Berkas mati `ScannerTaskPanel.jsx` **dihapus** (tidak diimpor di mana pun, berisi data contoh); fitur "Ambil alih tugas" (`TaskTakeoverButton`, supervisor lokasi) **dipasang** di detail tugas Barang Keluar desktop. | (ESLint/Jest; kode) |
| STM-OUT-6 (lainnya) | CAS/klaim ditambahkan: logistik `transition` & `pickup_handover` (status asal di filter), SO `done` (CAS dulu), sampel potong (pipeline), `release_order_rolls(_partial)`/`set_order_rolls_status` (status+ref per roll), `ship_order_rolls`, MKO `issue_step` & `cancel_order` (klaim saga + `replace_one` berprasyarat token), kedaluwarsa reservasi (klaim), `move_rolls_by_ref` (status). | (kode; regresi) |

### 1.3 P2/P3 & K-14
| ID | Perubahan | Uji |
|---|---|---|
| FLW-OUT-3 (+K-B2b-07) | Gudang ber-peran `return` (Gedung Retur) dikecualikan dari alokasi otomatis SO (`_available_rolls_for_order`); pilih roll manual tetap bisa. | `test_return_warehouse_excluded_from_auto_allocation` |
| FLW-OUT-5 (sebagian) | Kirim dengan roll yang dipindai: gerbang identitas hanya untuk roll yang ikut SJ itu (reservasi potong lain tidak menahan). Mulai cek muat masih memeriksa seluruh SO×gudang (sisa). | (kode) |
| FLW-OUT-6 | `complete` cek muat menghitung ulang `expected/untagged` dari tag aktif saat itu; endpoint baru `POST /outbound/loading-check/{sid}/cancel` (alasan K-14) + tombol FE. | `test_loading_check_manual_epc_not_proof_and_expected_refreshed`, Jest |
| CUT-4 (+K-B2b-05) | Satu aturan sisa potong `apply_remnant_rule` untuk potong SO & sampel: setelan `cutting.remnant_threshold` (bawaan 2,0 satuan dasar, bisa per produk) & `cutting.remnant_grade` (bawaan `keep` = grade tetap sampai inspeksi; opsi BS/C, grade asal disimpan). | `test_cut_waste_journal_limit_and_remnant` |
| CUT-6 | Batal SO sampel berbayar yang sudah disetujui → `sample_payment_status=refund_pending` + notifikasi Finance. | (kode) |
| ANOM-27 | Eskalasi tugas ambil memberi tahu manajer & admin gudang (PT tugas). | (kode) |
| RFID-11 (sebagian) | Sesi gate ditutup saat transfer `returning` selesai kembali dan saat perbaikan batal selesai diterima kembali. MKO/jalur `status`/SJ tanpa logistik belum (sisa). | (kode) |
| K-14 (`ReasonStr`/`require_reason`, dihitung huruf) | Diterapkan: eskalasi keluar (+ catatan penyelesaian opsional), batal SO, ambil darurat, batal transfer di jalan, batal perbaikan, override/kecualikan/batal cek muat, gagal kirim & bongkar muatan logistik, alasan susut potong. | `test_escalation_reason_k14`, `test_pick_requires_scan_and_whole_roll` |

## 2. Keputusan koordinator yang diterapkan
K-B2b-01 ✔ · K-B2b-02 ✔ (istilah layar tidak diubah) · K-B2b-03 ✔ (transfer & perbaikan; SO sesudah ambil = antrean
kembalikan ke rak, §4.1) · K-B2b-04 tidak diubah (sesuai keputusan) · K-B2b-05 ✔ · K-B2b-06/K-B3b-07 ✔ · K-B2b-07 ✔ ·
K-B2b-09 ✔ (kode + skrip data) · K-B2b-10 ✔ · K-B2b-12 ✔ · K-B2b-13/RFID-3 ✔ · K-B1-05/K-B3b-01 ✔ · K-B3b-02 ✔ · K-B3b-08 ✔
(hapus + pasang) · RFID-2 ✔ · RFID-5 ✔ · RFID-12 ✔.

## 3. Perubahan perilaku untuk pengguna
1. **Ambil (HP & desktop)**: wajib pindai/ketik **nomor roll**; jumlah = panjang roll utuh. Ambil sebagian roll ditolak
   ("potong dulu lewat Antrean Potong"); roll yang sama tidak bisa dipindai dua kali. Tanpa pindai hanya **jalur darurat
   supervisor** (izin persetujuan gudang) dengan alasan — tercatat di riwayat.
2. **Kirim** = roll utuh yang sudah diambil; qty "kirim sebagian" yang memecah roll ditolak (409).
3. **Eskalasi**: tugas dieskalasi tidak bisa diambil/dikirim sampai supervisor memutus; tugas yang sudah terkirim sebagian
   hanya bisa "Tutup sisa"; tugas batal tidak bisa dihidupkan lagi; batal SO menutup eskalasinya. Supervisor menerima
   notifikasi eskalasi.
4. **Batal SO sesudah ambil**: roll yang sudah diambil muncul di antrean **Penempatan Rak** (tanpa bin) untuk dikembalikan.
5. **Override / Ganti Roll / Lepas sebagian** pada SO yang sudah disetujui kini melihat roll `committed`; tugas gudang
   tidak berganti id. Ganti Roll pada SO **draf** ditolak.
6. **Backorder** SO yang sudah terkirim sebagian bisa diisi (otomatis saat stok masuk / rencana pemenuhan). Roll SJ yang
   sudah **ber-POD** tercatat diterima walau SO belum selesai.
7. **Reservasi kedaluwarsa** hanya untuk pesanan belum disetujui, dijalankan penjadwal (setiap 30 menit), bukan saat membuka
   daftar pesanan/dasbor/katalog.
8. **Potong**: panjang yang sudah dipesan SO lain tidak bisa dipotong untuk sampel/R&D/MDQ; susut > 3 % (setelan) wajib
   alasan dan semua susut dijurnal; sisa < 2 satuan (setelan) ditandai sisa (remnant) juga pada potong SO.
9. **Admin Cutting** di gedung lain: "Terima hasil potong" membuat **transfer** (menunggu persetujuan); roll pindah lewat
   transfer, lalu "Terima" lagi. Tugas sampel yang batal tidak bisa diterima.
10. **Batal transfer saat di jalan** → "Batal — kembali ke asal": roll tetap di jalan sampai diterima per roll di gudang asal.
    **Batal perbaikan yang sudah dikirim** → "Batal — menunggu kembali" + tombol "Terima kembali".
11. **Cek muat**: EPC yang ditempel di layar tercatat "manual" dan tidak membuka kirim (pakai handheld / override berizin);
    sesi bisa dibatalkan (alasan); gedung bergate hanya bebas cek muat bila reader OUT sehat (alasan tampil bila tidak).
12. **Tag RFID**: EPC yang pernah terbit tidak bisa ditulis ulang; "Tandai tercetak" untuk label RFID tidak lagi
    mengaktifkan tag — tag aktif sesudah **Verifikasi** membaca EPC-nya.
13. **Simulator gate** (V2 & lama) hanya di **perangkat uji** dan PT bermode simulasi; bacaan simulasi tidak membuat alarm
    atau penanda keluar. Handheld tidak bisa memakai `/rfid/ingest` lama.
14. **Gedung Retur** tidak ikut alokasi otomatis pesanan.
15. **Retur beli dari tolak QC** yang dibatalkan: roll kembali ke karantina.
16. Batal SO sampel berbayar → status bayar "perlu pengembalian" + notifikasi Finance.

## 4. Keputusan implementer (beserta alasan)
1. **FLW-OUT-4 / K-B2b-03 tanpa status roll baru.** Roll SO yang sudah diambil lalu batal → `available` + bin dikosongkan +
   `return_to_rack{}` (antrean Penempatan Rak yang sudah ada = "tugas kembalikan ke rak", bin dipindai saat ditaruh).
   Transfer/perbaikan batal di jalan memakai status **dokumen** `returning`; roll tetap `in_transit_transfer`/`wip` sampai
   diterima kembali. Alasan: status roll baru (`returning`) mengubah ember saldo & rumus angka stok (wilayah FIX-2) dan
   puluhan pembaca status roll; ember lama sudah benar (transit / WIP = tidak tersedia di asal).
2. Jalur darurat ambil memakai izin **`wms.approve`** (supervisor) — tanpa izin baru (matriks izin = FIX-1).
3. Pelepasan sebagian sisa < satu roll = roll utuh dilepas + **reservasi potong** sisanya (bukan fragmen fisik palsu).
4. K-B2b-01: parameter baru `close_remainder=true`; `adjusted_qty` tetap diterima bila sama dengan qty yang sudah diambil.
5. CUT-3: transfer dibuat berstatus `waiting_approval` (alur transfer biasa: setujui → kirim → gate/terima) dengan
   `purpose=cutting_handoff`; komitmen SO lewat `transfer_ref` (pola P03), tidak memakai `attach_committed_rolls` karena SO
   sampel sudah `picked` sesudah dipotong.
6. RFID-3: tidak membuat status tag baru (`pending_verify`); `pending_print` tetap dipakai sampai bukti baca — pembaca
   gate/handheld lama sudah menganggap `pending_print` belum identitas aktif.
7. RFID-1/4/9: syarat ganda **perangkat uji DAN PT bermode simulasi** (keputusan K-B2b-09); perubahan V2 dibatasi pada
   `rfid_v2_simulator.py` (penilaian, klaim & `gate_*` tidak disentuh).
8. RFID-12: "sehat" = aturan `rfid_v2_health.evaluate` (READER_STOPPED, TELEMETRY_STALE) dibaca saja; QUEUE_RISING tidak
   membatalkan pembebasan.
9. K-B3b-02: endpoint layar menolak sumber `device`; EPC manual dicatat (jejak) tetapi hasil `manual_unverified`.
10. Bawaan K-B2b-05/06: ambang sisa 2,0 (sama dengan aturan sampel lama), grade `keep` (rekomendasi B2b "grade tetap
    sampai inspeksi"), batas susut 3 %.
11. ANOM-06: yang kedaluwarsa = `reserved` & `waiting_approval` ("belum disetujui"); interval job 30 menit.
12. FLW-OUT-3: hanya peran `return` yang dikecualikan (bukan `inspection`, karena gedung inspeksi juga gudang simpan).
13. RFID-2: indeks unik EPC seumur hidup TIDAK dibuat (data lama bisa melanggar → start gagal); dicegah di kode + skrip data
    melaporkan EPC ganda.
14. K-B3b-08: berkas mati dihapus DAN tombol ambil alih dipasang di Barang Keluar desktop (supervisor lokasi).

## 5. Tabel transisi status yang disentuh

### 5.1 Tugas ambil keluar (`wms_tasks`, `flow_type=outbound`) — `backend/services/outbound_task_state.py` (BARU)
| Aksi | Dari (daftar-izin) | Ke | Pemakai |
|---|---|---|---|
| `release` | scheduled | created | `POST /outbound/tasks/{id}/release` |
| `scan_pick` | created · picking · packing · staging · partially_shipped | picking · packing · partially_shipped | `POST …/scan-pick` (+ CAS `picked_qty`) |
| `escalate` | scheduled + daftar ambil | escalated (`escalation.prev_status`) | `POST …/escalate` (409 di luar daftar) |
| `resolve_escalation` | escalated | status sebelum eskalasi (tanpa qty) / turunan progres (`derived_status`) | `POST …/resolve-escalation` |
| `dispatch` | created · picking · packing · staging · partially_shipped | partially_shipped · dispatched | `shipment_service` (klaim saga tetap) |
| `advance` | created · picking · packing | picking · packing · staging | (tabel; `wms.py advance` tidak diubah) |
| `cancel` | scheduled · escalated · daftar ambil | cancelled (+ `escalation.status=cancelled`) | batal SO (`cancel_for_order`), override SO |

### 5.2 Dokumen lain
| Dokumen | Transisi baru/diubah |
|---|---|
| `warehouse_transfers` | `dispatched → returning` (batal di jalan) → `cancelled` (`returned_to_source`) |
| `repair_orders` | `sent → returning` (batal) → `cancelled` (terima kembali) |
| `rfid_verify_sessions` (cek muat) | `open → cancelled` (batal beralasan); hasil baru `manual_unverified` |
| `rfid_tags` | `pending_print → active` hanya dengan bukti baca (manual) · EPC pernah terbit tidak bisa `active` lagi |
| `inventory_rolls` | `in_transit_sales` tidak pernah → `available` lewat pelepasan; `in_transit_sales → delivered` per SJ ber-POD; `consumed` tidak hidup lagi lewat bucket |
| `sales_orders` | `approved/waiting_stock` tidak kedaluwarsa; `partially_*`/`picked` menerima isi backorder; `sample_payment_status → refund_pending` saat batal |
| `logistics_deliveries` | semua transisi & serah terima ambil CAS status asal |
| `makloon_orders` | issue/batal: klaim saga + `replace_one` CAS token |

## 6. Hasil uji & perbandingan regresi (angka apa adanya)

### 6.1 Uji baru
| | dasar `5b65039` | FIX-3b |
|---|---:|---:|
| `test_fix3b_outbound_integrity.py` (26) | **26 gagal** | **26 lulus** |
| Jest `fix3bForms.test.js` (4) | **4 gagal** | **4 lulus** |

### 6.2 Pytest — 57 berkas lama (DB dipulihkan sebelum tiap putaran, urutan sama)
Putaran 1 (45 berkas): `test_admin_bypass_and_fulfillment_plan, test_f05_cut_child_allocation, test_f06_pod_closes_so,
test_f10_cbd_dp_dispatch_gate, test_f15_sample_payment_tolerance, test_fase_sl_rfid_alias, test_iter14_wh_transfer_rolls,
test_iter153_real_fulfillment_e2e, test_iter23_sample_and_designer, test_iter263_wms_rfid_r0r1r2, test_iter265_r3r4r5,
test_iter270_reallocate_extra, test_iter292_f01_dispatch_gl, test_iter314_saga_and_reopen, test_iter_so_override,
test_kn_audit_2026_09_21(+_extended), test_l06_samples_cutting, test_l06_t1_iter200, test_ln120_device_identity,
test_p03_transfer_receipt, test_prep_d1_gate_v2, test_prep_d2_gate_txn, test_prep_f_printer, test_prep_g_handheld,
test_roll_pick_and_reallocate, test_sample_pos_flow, test_sesi14_idempotency, test_transfer_status_guard,
test_trial_22okt_flow, test_uat24_f5, test_uat_v3_ui_gaps, test_iter256_e2e_flow_sweep, test_l05_so_qc_request_api_t1,
test_iter266_r6_cc_r7, test_iter280_makloon_partial_queue, test_makloon_celup_rolls, test_iter268_order_preview,
test_f16_due_from_first_sj, test_comm04_ln042t03_regression, test_iter267_notif_health_multileg, test_l00_edge_cases,
test_gelombang1_gl_integrity, test_p03_p04_e2e, test_l01_material_loss`. Putaran 2 (12 berkas): `test_phase4_r8,
test_iter116_p08, test_fb02_logistics, test_iter318_dispatch_logistics, test_iter288_logistics_gps,
test_l06_cutting_wait_config, test_prep_f_connector_e2e, test_iter264_putaway_fixes, test_iter114_p07_reversal,
test_iter115_p07b, test_p02_retest, test_l05_l06_t1_iter198`.

| | dasar | FIX-3b (putaran akhir) |
|---|---:|---:|
| Putaran 1 gagal/error | 142 | **142** (himpunan identik) |
| Putaran 2 gagal/error | 33 | **33** (himpunan identik) |
| hanya gagal di FIX-3b | — | **0** |
| `test_iter117_p09` (proses terpisah) | 18 lulus | 18 lulus (sesudah penyesuaian) |
| `test_iter118_p10` (proses terpisah) | 8 lulus | 8 lulus (sesudah penyesuaian) |

Putaran pertama FIX-3b menghasilkan **12 uji hanya-gagal-FIX-3b** (+2 di p09/p10). Semuanya = perilaku yang memang diubah
keputusan/temuan → **uji disesuaikan** (tidak ada perbaikan kode yang diperlukan):
* `test_iter265::test_05/06` — EPC ditempel = `manual_unverified` (K-B3b-02) lalu override berizin; ambil memakai pindai
  roll utuh (K-B1-05/STM-OUT-5).
* `test_l06_samples_cutting::test_ln061_t02_catalogue_two_locations_handoff` — serah-terima lintas gedung = transfer (K-B2b-10).
* `test_prep_d1::test_simulator_every_scenario`, `test_prep_d2::test_ops_simulator_respects_rfid_simulation_mode` — simulator
  hanya perangkat uji + PT bermode simulasi; mode mati → 409 (K-B2b-09/RFID-1).
* `test_prep_d2::test_loading_check_required_policy_satisfied_by_gate` — reader OUT basi → cek muat wajib; sehat → bebas (RFID-12).
* `test_prep_f_printer` (4: tandai tercetak + 3 pemakai `_active_roll`) — tag aktif sesudah verifikasi baca EPC (RFID-3).
* `test_sesi14_idempotency::test_idempotency_scan_pick` — ambil tanpa roll = jalur darurat + alasan.
* `test_uat24_f5::test_p7_…` — batal perbaikan terkirim = `returning` + terima kembali (K-B2b-03).
* `test_iter117_p09::test_simulate_uses_ingest_path`, `test_iter118_p10::test_simulate_contains_action` — perangkat ditandai uji.

Gagal lama (sama persis di dasar & FIX-3b) berasal dari data acuan/asumsi uji lama (mis. `CREDIT_BLOCKED` pelanggan uji
di `test_iter_so_override`/`test_f06`, `test_iter266_r6_cc_r7` 24, `test_p03_transfer_receipt` 11 error setup) — tidak disentuh.

### 6.3 Jest & ESLint (kontainer `node:20` sementara, `node_modules` volume `kn-dev_fe_node_modules` read-only, CI=true)
| | dasar | FIX-3b | FIX-3b + FIX-1 (gabung) |
|---|---|---|---|
| 12 suite terarah (semua uji yang mengimpor berkas FE yang diubah + `fix3aForms`, `mobileShell`, `TransferDetailModal`) | 11 lulus, 1 gagal (`fix3bForms` 4 gagal) · 88/92 | **12/12 · 92/92** | 13/13 (+`fix1Cakupan`) · **101/101** |

ESLint 14 berkas FE yang diubah: **0 error**, 6 peringatan `Unused eslint-disable directive` pada baris lama. Suite Jest
penuh tidak dijalankan (memori Docker host; stack FIX-1 berjalan bersamaan).

### 6.4 Guardrail (`PYTHONUTF8=1`, host; `verify_state_machine` tidak dijalankan)
Dasar `5b65039` vs FIX-3b (sebelum gabung): kode keluar 40/40 **identik** (27 hijau). Jumlah pelanggaran tidak naik:
* `verify_atomic_claim` 6 → 6 pelanggaran, cek 123 → 124, BELUM DITINJAU 76 → 76 (putaran awal 7/77: `scan-pick` kini
  lewat `_ots.transition` + endpoint baru `receive-back` → **guardrail dilatih** mengenali `_ots.transition(` sebagai CAS
  & `receive-back` dicatat di `REVIEWED` dengan alasan).
* `verify_numeric_bounds` HARD 3 = 3 (lama, `SoOverrideLineIn`), `verify_auth_coverage`, `verify_qty_dual`,
  `verify_entity_label` 1, `verify_line_scope` 1, `verify_to_list_bound`, `verify_no_secrets` 8 — identik.
* Hijau tetap hijau: `status_history` (9 cek), `rfid_tag_unique`, `roll_identity`, `codebase_map`, `knselect_contract`,
  `uom_vocab`, `role_label`, `escape_layers`, dll. Guardrail yang butuh `pymongo/httpx/pydantic` di host gagal impor di
  kedua sisi (sama).
* Sesudah gabung `main` (FIX-1): lihat §6.5.

### 6.5 Gabung `main` (FIX-1) ke branch
`git merge main` (59bdc68) **tanpa konflik teks** (8 berkas bersinggungan, §8). Sanity pada kode gabungan (DB dipulihkan):
`test_fix3b_outbound_integrity` 26/26, `test_fix3a_inbound_integrity` 28/28, `test_prep_d1` 20/20, `test_prep_d2` 11/11,
`test_prep_f_printer` 22/22, `test_prep_g_handheld` 11/11, `test_l06_samples_cutting` 8/8, `test_sesi14` 2/2,
`test_uat24_f5` 7/7, `test_iter265` 6 gagal (= dasar), `test_fix1_cakupan` 1 skipped (butuh prasyarat FIX-1). Jest
gabungan 13 suite 101/101. Guardrail `main` (59bdc68) vs gabungan, 19 guardrail termasuk `verify_scope_guard` FIX-1:
kode keluar identik (12 hijau), hitungan identik (atomic_claim BELUM DITINJAU 77 = 77 — angka FIX-1, hanya urutan daftar
berbeda; numeric_bounds HARD 3 = 3; dll.).

## 7. Skrip perbaikan data (dibuat, dry-run bawaan; diuji di salinan)
`scripts/fix_data_2026_11_09_fix3b_alur_keluar.py --db kn_test_trial [--apply]` (menolak DB lain). Hasil di salinan
`kn_test_trial_2026-11-08` (mongo sementara):
| Langkah | Dry-run | Sesudah `--apply` (dry-run ulang) |
|---|---:|---:|
| `rfid_simulation_off` (RFID-9: `wms.rfid_simulation` ent_ksc, ent_kanda, ent_82b52ed6ee8b) | **3** | 0 |
| `shipped_roll_released` (STM-OUT-1) | 0 | 0 |
| `dead_so_reservations` (STM-OUT-4) | 0 | 0 |
| `pod_rolls_in_transit` (FLW-OUT-2) | **6** | 0 |
| `escalation_on_terminal` (STM-OUT-2) | 0 | 0 |
| `stale_transfer_marker` (FLW-OUT-11) | 0 | 0 |
| `consumed_revived` (MKO-03) | 0 | 0 |
| `sample_paid_cancelled` (CUT-6) | 0 | 0 |
| `epc_reuse_report` (RFID-2, laporan) | 0 | — |
Idempoten; jejak `migrations` (`fix_data_2026_11_09_fix3b_alur_keluar`). **Tidak** dijalankan ke DB bersama.
**Catatan pra-pilot (K-B2b-09):** sebelum reader U300 nyata dipasang, jalankan langkah `rfid_simulation_off` di DB tujuan
(atau matikan "Mode simulasi RFID" per PT di Pusat Pengaturan) dan pastikan tidak ada perangkat produksi bertanda uji.

## 8. Berkas berisiko bentrok
* **FIX-1 (sudah di `main`, tergabung otomatis)** — berkas yang disentuh dua paket: `routers/outbound_picking.py`
  (FIX-1: daftar tugas `resolve_work_scope`, pagar `loading-check`; FIX-3b: scan-pick/escalate/resolve/release/cancel
  cek muat), `routers/rfid.py` (FIX-1: `_wh_filter`, `_roll_out`, pagar roll asli; FIX-3b: lookup tag hidup, model
  `test_device`, tolak handheld di ingest), `routers/transfers.py`, `routers/repair_orders.py`, `routers/inventory.py`,
  `routers/dashboard.py`, `services/logistics_service.py`, `frontend/.../OutboundScanInterface.jsx`. Cek akses FIX-1 tidak
  diubah oleh FIX-3b.
* **PREP-H / jalur V2** — hanya `services/rfid_v2_simulator.py` (penolakan di awal `run` + roll contoh per PT); uji lama
  `test_prep_d1_gate_v2.py`/`test_prep_d2_gate_txn.py` disesuaikan.
* **FIX-2 (angka stok)** — tidak ada perubahan rumus; status/ember roll tidak bertambah. `roll_service` (pelepasan,
  kirim, POD, alokasi) — pembaca `stock_figures` tidak berubah.
* Bersama: `services/roll_service.py` (banyak fungsi), `services/stock_bucket_service.py`, `services/rfid_print_service.py`
  (mark-printed, verifikasi, `scan_session` sumber manual), `services/handheld_tags.py` (`epc_free`),
  `config_catalog_ops.py` (3 setelan `cutting.*`), `services/scheduler_service.py` (job `reservation_expiry`),
  `scripts/guardrails/verify_atomic_claim.py` (`RE_CAS`, `REVIEWED`), `frontend/.../MobileTaskActions.jsx` (OutboundActions
  ditulis ulang; InboundActions FIX-3a tidak diubah).
* `CODEBASE_MAP.md` belum dibangkitkan ulang untuk `outbound_task_state.py` (guardrail `codebase_map` tetap hijau).

## 9. Sisa (belum dikerjakan / butuh keputusan)
1. **Status tugas/roll lain belum masuk tabel transisi**: `wms.py advance` (CAS lama tetap), `recompute_so_status` (turunan,
   tanpa CAS), SJ void, print job, `shipments`; B3a SSOT-1 menyeluruh (`roll_state.transition`).
2. **Handheld C72 untuk transfer `returning`** (terima kembali di asal lewat sesi handheld/gate IN asal) — saat ini lewat
   layar "Terima per roll" desktop; `handheld_tasks`/`handheld_sync` & gate V2 belum mengenal `returning`.
3. FLW-OUT-5: mulai cek muat masih menolak bila ada reservasi potong belum dipotong di SO×gudang.
4. RFID-11: penutupan sesi gate untuk MKO (penerimaan hasil), jalur `POST /transfers/{id}/status`, SJ tanpa logistik.
5. Penanda `return_to_rack` belum dihapus otomatis saat roll ditempatkan (antrean berbasis bin kosong sudah benar);
   label "Kembalikan ke rak" di antrean Penempatan Rak belum ditampilkan khusus.
6. Kandidat statik lain belum dikerjakan: TRF-01, REP-01/02 (terima perbaikan tanpa CAS penuh), MKO-06/07/08/10,
   PRT-03/08/12, SMP-03/07/08, ANOM-07/09/13/18/19/22, G-06/08/15, P-01/04/05/06, H-02/03/06.
7. RFID-6 (batch handheld tanpa `operator_session_id`) — wilayah PREP-G; RFID-8/RFID-7 (FIX-1).
8. Indeks unik EPC seumur hidup (butuh pembersihan data dulu; skrip melaporkan).
9. CUT-5 (jenis tugas kelas satu di daftar), FLW-OUT-8 (istilah `delivered` di dokumen), FLW-OUT-9 (K-B2b-04 tetap).
10. Simulator V2 masih bisa dijalankan admin untuk skenario `empty` di perangkat uji tanpa dokumen (tidak menulis klaim).

## 10. Kebersihan
Stack `kn-tmp-fix3b-mongo/-be/-fe` dihapus sesudah uji. Tidak ada tulisan ke DB bersama, stack `kn-uji-*`, atau data UAT
"test"; `verify_state_machine.py` tidak dijalankan; tidak memakai peramban; `docs/reviews/TRACKER.md` tidak diubah.

---

## Ringkasan untuk koordinator
* **Ditutup — P0:** STM-OUT-1, STM-OUT-3, FLW-OUT-2, CUT-1, CUT-3, RFID-2. **Kandidat calon P0 — keempatnya terbukti
  (kode + uji gagal di dasar) dan diperbaiki:** MKO-03, PRT-01/02 (+PRT-05), ANOM-06, POT-05.
  **P1:** STM-OUT-2, STM-OUT-4, STM-OUT-5, STM-OUT-6 (tabel transisi tugas ambil + CAS logistik/SO done/sampel/rilis/
  kirim/MKO/kedaluwarsa), FLW-OUT-4, FLW-OUT-11, CUT-2, RFID-1 (di `rfid_v2_simulator.py` saja), RFID-3, RFID-4, RFID-5,
  RFID-9 (kode + skrip data), RFID-12, K-B1-05/K-B3b-01, K-B3b-02, K-B3b-08. **P2/P3:** FLW-OUT-3, FLW-OUT-5 (sebagian),
  FLW-OUT-6, CUT-4, CUT-6, ANOM-27, RFID-11 (sebagian); K-14 di 10 jalur keluar/potong/RFID.
* **Perubahan perilaku utama:** ambil = pindai roll utuh (ketik qty = darurat supervisor + alasan); kirim = roll utuh;
  eskalasi terkirim sebagian = tutup sisa; batal sesudah ambil → antrean kembalikan ke rak; transfer/perbaikan batal di
  jalan → "kembali ke asal" sampai diterima; POD per SJ; reservasi kedaluwarsa hanya belum disetujui (job); potong
  menghormati panjang dipesan, susut dijurnal & beralasan di atas 3 %; serah-terima Cutting lintas gedung = transfer; EPC
  tidak pernah dipakai ulang; tandai tercetak RFID butuh verifikasi baca; simulator hanya perangkat uji + PT simulasi;
  cek muat EPC manual bukan bukti, gedung gate bebas cek muat hanya bila reader OUT sehat; Gedung Retur keluar dari
  alokasi otomatis.
* **Uji:** baru pytest 26 (dasar 26 gagal → 26 lulus), Jest 4 (dasar 4 gagal → 4 lulus). Regresi 57 berkas pytest: dasar
  142 + 33 gagal = FIX-3b 142 + 33 (himpunan identik, **0 hanya-gagal-FIX-3b** sesudah 14 uji lama disesuaikan dengan
  keputusan — tanpa perbaikan kode tambahan); p09/p10 18+8 lulus keduanya. Jest terarah 12 suite 92/92 (gabung FIX-1:
  13 suite 101/101); ESLint 0 error. Guardrail: kode keluar 40/40 identik; atomic_claim 6→6 / 76→76 (dilatih untuk
  `_ots.transition` + 1 endpoint dicatat); sesudah gabung FIX-1: identik dengan `main` (77 = 77).
* **Skrip data:** `scripts/fix_data_2026_11_09_fix3b_alur_keluar.py` (dry-run bawaan; salinan acuan: 3 setelan mode
  simulasi PT nyata dimatikan, 6 roll SJ ber-POD → `delivered`; idempoten). Belum dijalankan ke DB bersama — **jalankan
  `rfid_simulation_off` sebelum pilot reader**.
* **Berisiko bentrok:** sudah digabung dengan `main`+FIX-1 tanpa konflik (8 berkas bersinggungan: `outbound_picking.py`,
  `rfid.py`, `transfers.py`, `repair_orders.py`, `inventory.py`, `dashboard.py`, `logistics_service.py`,
  `OutboundScanInterface.jsx`). PREP-H: hanya `rfid_v2_simulator.py` + uji D1/D2. Bersama: `roll_service.py`,
  `rfid_print_service.py`, `stock_bucket_service.py`, `scheduler_service.py`, `config_catalog_ops.py`,
  `verify_atomic_claim.py`, `MobileTaskActions.jsx`.
* **Sisa:** tabel transisi dokumen lain (SSOT-1), handheld/gate untuk transfer `returning`, FLW-OUT-5 di mulai cek muat,
  RFID-11 MKO/jalur status/SJ tanpa logistik, kandidat statik B2b lainnya (§9.6), RFID-6, indeks unik EPC seumur hidup,
  CUT-5/FLW-OUT-8/FLW-OUT-9.
