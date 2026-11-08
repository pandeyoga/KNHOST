# PREP-D2 — Gate V2 disambungkan ke transaksi gudang + antrean periksa admin gudang

**Tanggal:** 9 Nov 2026 · **Pelaksana:** Claude Code (implementer) · **Branch:** `worktree-agent-a8888e80abe93a43f`
(basis `main` `70eb9fd`) · **Commit:** `832cb15` (kode + uji) → commit laporan ini. Status: `implemented_pending_review` (belum diverifikasi reviewer).
Acuan mengikat: [`KEPUTUSAN_GATE_RFID.md`](../KEPUTUSAN_GATE_RFID.md) §6–§8 — **K-GDG-02** (gate IN memvalidasi putaway
dari GRN, gate OUT memvalidasi barang keluar, handheld = cadangan), **K-GDG-03** (langsung gate utama), **K-RFID-09**
(merah hanya pelanggaran, kuning tanpa kunci, satu kunci per gate), **K-RFID-10** (sesi dokumen bertahap), **K-OPN-03**
(pembekuan pendaftaran awal); audit [`AUDIT_MIDDLEWARE_RFID_2026-11-08.md`](../AUDIT_MIDDLEWARE_RFID_2026-11-08.md)
AUD-MW-08 (pemulihan klaim) & AUD-MW-10 (panel operasional). Kode Java `middleware/u300-agent/app/` (paket E) dan
kontrak `rfid_v2.json`/`OPENAPI_RFID_V2.json` **tidak diubah**.

## 1. Ringkasan
- **Gate IN → konfirmasi tiba.** Lintasan V2 yang sudah diputuskan, di gedung bermode **gate** dengan reader tertaut
  sebagai gate IN gedung itu: Putaway → `confirm_arrival_trip(…, {"type": "gate", "passage_id"})` (satu lintasan = satu
  trip, idempoten); Transfer → `transfer_receipt_service.receive` per roll (CAS per roll). Roll dokumen yang tidak
  terbaca tetap **menunggu** (handheld melengkapi). PA/transfer yang sudah tiba sebagian (`partially_received`) kini
  tetap dokumen aktif gate (sebelumnya trip ke-2 menjadi merah `DOC_MISSING`).
- **Gate OUT → bukti per trip** di dokumennya (`gate_exits[]`: trip ke-n, waktu, roll, perangkat, lintasan) untuk SJ,
  transfer, Order Makloon, Perbaikan (dan PA dari gedung asal).
- **Penutupan sesi dokumen otomatis** di titik siklus hidup (tabel §3): roll yang belum lewat & tidak dilengkapi
  handheld/jalur lain → kuning `ROLLS_MISSING` ke antrean periksa.
- **Area beku** pendaftaran awal → lintasan **kuning** "Area sedang dibekukan…" (`AREA_FROZEN`), tidak ada transaksi;
  roll tetap di antrean dan bisa diterima setelah beku dilepas.
- **Gedung bermode handheld** (atau reader belum tertaut di profil gedung) → gate **hanya bukti** (`gate_arrivals[]` /
  `gate_exits[]` ber-`txn: false`); alur handheld lama tetap.
- **Antrean periksa admin gudang** (tab baru *Monitor Gerbang › Antrean periksa*): kasus per lintasan kuning/merah +
  per sesi dokumen yang ditutup dengan roll kurang; bukti per roll (antena, RSSI puncak, waktu, dokumen, alasan
  berbahasa Indonesia); saring status/hasil/jenis/gate; tindakan terima / tolak / abaikan / minta pindai ulang handheld /
  akui kunci gate / tutup kasus / ulangi transaksi — semua **`wms.approve`**, beralasan, beraudit, idempoten.
- **Koreksi klaim crossing beraudit** (lepas / pindahkan ke dokumen lain) + riwayat koreksi.
- **Kios / monitor gate**: reader V2 memakai status V2 — **KUNING** (perlu diperiksa, barang jalan) tampil di samping
  hijau/merah; membuka kunci merah V2 butuh izin approve.
- **Notifikasi**: kasus baru → Admin Gudang & Manajer (`rfid_gate_review`, merah = kritis); minta pindai ulang →
  petugas gudang (`rfid_gate_rescan`). Lintasan simulator tidak menotifikasi.
- **Cek muat handheld** (SO): di gedung bermode gate dengan gate OUT tertaut, kebijakan "wajib cek muat" dipenuhi gate
  (handheld = cadangan, opsional; bila dijalankan hasilnya tetap mengikat).

## 2. Aturan akhir gate vs handheld per jenis dokumen
"Gedung gate" = profil gedung `effective_mode = gate` **dan** reader lintasan tercantum sebagai perangkat IN (arah
masuk) / OUT (arah keluar) di pasangan gate gedung itu (`warehouse_gate_policy`). Selain itu = "gedung handheld".

| Jenis dokumen | Gedung gate | Gedung handheld | Handheld (cadangan / alat utama) |
|---|---|---|---|
| Putaway (gate IN tujuan) | Hijau/kuning ber-klaim → **tiba per trip** (BTG trip pertama, `arrived_via=gate`); merah → nihil | Bukti `gate_arrivals[]` saja | `arrival-trips` handheld / konfirmasi tiba / resolve-exception — **tetap** |
| Transfer gudang (gate IN tujuan) | Hijau/kuning ber-klaim → **terima per roll** (aktor "Gate IN …"); pelanggaran aturan tujuan → antrean | Bukti saja | `POST /transfers/{id}/receive` — tetap |
| Perbaikan / bahan Makloon kembali (gate IN) | Bukti di dokumen (hasil dicatat admin di dokumen itu) | Bukti | alur lama |
| SJ penjualan (gate OUT) | Bukti per trip `shipments.gate_exits[]`; cek muat handheld **opsional** (kebijakan "wajib" dipenuhi gate) | Bukti; cek muat handheld sesuai kebijakan lama | Final Loading Check — tetap; hasil tidak bersih tetap memblokir |
| Transfer / Order Makloon / Perbaikan / PA (gate OUT asal) | Bukti per trip di dokumen | Bukti | alur lama |

Kuning (REVIEW) yang **ber-klaim** (barang jalan, K-RFID-09): roll yang **cocok dokumen** tetap dicatat (tiba/bukti);
roll bermasalah + alasan tingkat lintasan masuk antrean. Kuning **tanpa klaim** (dokumen berubah/tidak aktif, tanpa
manifest, arah tidak tervalidasi, lintasan kelamaan, mundur/batal) → **tidak ada yang dicatat**; roll yang cocok masuk
antrean berstatus "belum dicatat" dan bisa diterima admin. Merah → tidak ada yang dicatat; kunci gate tunggal.
Lintasan **simulator** (alat admin) hanya menulis transaksi bila **Mode simulasi RFID** (`wms.rfid_simulation`) menyala
untuk PT dokumennya; bila mati → bukti saja (`SIMULATED_EVIDENCE`) agar simulasi tidak mengubah stok produksi.

## 3. Titik penutupan sesi dokumen (K-RFID-10)
| Dokumen | Arah | Titik siklus hidup | Kait |
|---|---|---|---|
| Putaway | IN (tujuan) & OUT (asal) | PA berstatus akhir (selesai / selesai dgn pengecualian / pengecualian / dikembalikan) — lewat trip gate/handheld, `close`, atau konfirmasi tiba lama | `putaway_arrival_service.gate_session_hook` (+1 baris di `putaway_order_service.confirm_arrival`) |
| Transfer gudang | OUT (asal) & IN (tujuan) | Transfer `completed` (semua roll diterima / dikembalikan) | `transfer_receipt_service._refresh_status` |
| SJ penjualan | OUT | Pengiriman logistik **berangkat** (`in_transit`), serah terima ambil sendiri, atau `delivered`/`completed` (jaring pengaman) | `logistics_service._close_gate_sessions` |
| Perbaikan | OUT & IN | Hasil perbaikan diterima (`done`) | `repair_order_service.receive` |
| Order Makloon | OUT | **Manual** (tombol/endpoint tutup sesi) — titik terima hasil MKO kompleks, belum dikait | — |

Roll yang **bukan "kurang"** saat ditutup (dicatat sebagai pelengkap): PA — item tiba lewat handheld/jalur lain atau
dikembalikan ke transit; transfer IN — roll diterima di tujuan (handheld/manual); transfer — roll dikembalikan ke asal;
SJ — roll tercakup Final Loading Check bersih/override/simulasi. Penutupan manual lama
(`POST /rfid/v2/ops/doc-sessions/{jenis}/{id}/close`) memakai penilai yang sama. Penutupan idempoten (CAS penutup
pertama), gedung handheld tanpa jejak gate → tidak ada sesi.

## 4. Antrean periksa, izin, koreksi klaim, kios
- Endpoint baru (`backend/routers/rfid_v2_review.py`): `GET /api/rfid/v2/ops/reviews` (saring gudang, gate, status,
  hasil, jenis; ≤100), `GET …/reviews/summary`, `GET …/reviews/{id}` (dengan penyegaran: roll yang sudah dilengkapi
  handheld/lintasan lain → "dilengkapi jalur lain"), `POST …/{id}/rolls/accept|reject|rescan`, `…/{id}/dismiss`,
  `…/{id}/acknowledge-latch`, `…/{id}/retry`; `GET /api/rfid/v2/ops/crossings`, `POST …/crossings/release|move`;
  `GET /api/rfid/v2/ops/devices/{id}/kiosk`.
- Izin: lihat `wms.view`; semua tindakan & koreksi klaim `wms.approve` (Admin, Manajer, Admin Gudang — petugas gudang
  `wms.scan` ditolak 403). **Diubah:** `POST /rfid/v2/ops/devices/{id}/gate-latch/acknowledge` kini `wms.approve`;
  `POST /rfid/v2/passages/{id}/acknowledge` untuk lintasan **merah** kini `wms.approve` (kuning tetap `wms.scan`).
  Tidak ada izin baru di matriks (pakai `wms.approve` yang sudah ada).
- Cakupan: registry `inventory_rolls` (gudang kasus) + izin pakai gudang (tulis) + entitas dokumen sumber.
- Tindakan terima: gate IN PA → item menunggu `confirm_arrival_trip` (trip ber-id kasus), item pengecualian →
  `resolve_exception(accept)`; gate IN transfer → `receive` (roll ditolak aturan → pengecualian supervisor dengan
  alasan); gate OUT / gedung handheld → klaim crossing + bukti di dokumen (`via: review`). Roll tanpa dokumen / tag asing
  tidak bisa "diterima" (400) — tolak/abaikan. Tolak = klaim lintasan itu dilepas (tercatat sebagai koreksi). Area masih
  beku → 409 `REGISTRATION_FREEZE`, status roll dikembalikan.
- Kasus selesai otomatis bila semua roll tuntas & kunci tidak aktif; kasus tanpa roll yang bisa ditindak (mis. bukti
  tidak lengkap tetapi semua roll tercatat) wajib ditutup admin dengan catatan.
- Koreksi klaim (AUD-MW-08): lepas (alasan ≥10 huruf; CAS pemilik klaim) / pindah ke dokumen aktif yang memuat roll
  (sisip baru → hapus lama ber-CAS → kompensasi bila kalah) → `rfid_v2_claim_corrections` + `audit()`.
- Kios: `useGateStatus(gateId, …, protocol)` memakai status V2 untuk reader V2 (`protocol` kini ikut daftar perangkat).

## 5. Berkas
| Berkas | Isi |
|---|---|
| `backend/services/gate_txn_service.py` (baru) | `precheck` (mode gedung, area beku, simulasi), `build_input`, `post_close` + buku `rfid_v2_gate_txn` (CAS per lintasan × dokumen), transaksi PA/transfer, bukti per trip, `close_document_session`/`safe_close`, `gate_validates` |
| `backend/services/gate_review_service.py` (baru) | Kasus antrean (lintasan & roll kurang), bukti per EPC, notifikasi, penyegaran malas, daftar & ringkasan |
| `backend/services/gate_review_actions.py` (baru) | Terima/tolak/abaikan/pindai ulang/tutup/akui kunci/ulangi + koreksi klaim |
| `backend/services/rfid_v2_kiosk.py` (baru) | Status kios V2 (bentuk sama dengan status gate lama + kuning) |
| `backend/routers/rfid_v2_review.py` (baru) | Endpoint §4 |
| `backend/services/rfid_v2_service.py` | Kait `precheck` sebelum klaim, `gate_txn_input` di lintasan, `post_close` (juga saat close diulang) |
| `backend/services/rfid_v2_sessions.py` | `status(roll_ids=…)`, `close_session(completed=…, trigger=…)` + `closed_now` |
| `backend/services/rfid_v2_sources.py`, `gate_evaluator.py` | PA `partially_received` & transfer `partially_received` = dokumen aktif gate |
| `backend/services/rfid_v2_core.py`, `server.py` | Indeks koleksi baru, registrasi router |
| `backend/routers/rfid_v2_ops.py`, `rfid_v2.py` | Izin approve untuk kunci gate/lintasan merah; tutup sesi manual = penilai baru |
| `backend/services/putaway_arrival_service.py` | `norm_source` menyimpan `local_passage_id`/`review_case_id`; `gate_session_hook` |
| `backend/services/transfer_receipt_service.py`, `loading_check_service.py` | Kait penutupan sesi; aturan cek muat gedung gate + `gate_out_primary` |
| `backend/services/putaway_order_service.py`, `logistics_service.py`, `repair_order_service.py`, `rfid_service.py` | Kait 1–8 baris (di luar daftar milik D2 — lihat §8) |
| `frontend/src/features/rfid/GateReviewQueue.jsx`, `GateReviewDetail.jsx` (baru) | Antrean periksa (DetailModal + FormModal, KNSelect, ErrorNotice) |
| `frontend/src/features/rfid/RfidGateMonitorView.jsx`, `GateLiveVerdict.jsx`, `u300Labels.js`, `U300Operations.jsx`, `U300PassageList.jsx` | Tab antrean, kios kuning V2, istilah Indonesia, tombol buka kunci hanya pemegang izin approve |
| `frontend/src/features/wms/LoadingCheckPanel.jsx` | Petunjuk "gedung bergate: cek muat handheld = cadangan" |
| `backend/tests/test_prep_d2_gate_txn.py`, `frontend/src/features/__tests__/prepD2GateReview.test.js` (baru) | Uji |

Koleksi baru: `rfid_v2_reviews`, `rfid_v2_gate_txn`, `rfid_v2_claim_corrections`. Field dokumen baru:
`gate_exits[]` / `gate_arrivals[]` (+`_last_at`) pada `shipments`, `warehouse_transfers`, `putaway_orders`,
`makloon_orders`, `repair_orders`; `gate_txn_input` / `gate_txn_state` / `gate_txn` pada `rfid_v2_passages`.

## 6. Perubahan perilaku untuk pengguna
1. Gedung bermode gate: lintasan gate IN hijau langsung mencatat tiba Putaway / terima transfer per trip; petugas tidak
   perlu konfirmasi handheld untuk roll yang terbaca. Roll yang tidak terbaca tetap "menunggu" → pindai handheld.
2. Trip ke-2 dst. untuk PA/transfer yang sudah tiba sebagian kini hijau (dulu merah karena status dokumen berubah).
3. Lintasan di area beku pendaftaran awal = kuning, barang jalan, tanpa transaksi.
4. SO dari gedung bergate tidak lagi wajib Final Loading Check (bila gate OUT tertaut); roll tanpa tag tetap ditolak.
5. Membuka kunci gate merah (panel U300, kios, antrean) kini hanya Admin/Manajer/Admin Gudang.
6. SJ berangkat / PA selesai / transfer selesai / perbaikan diterima → roll yang tak terbaca gate muncul di antrean.

## 7. Bukti uji (apa adanya; kontainer `kn-tmp-d2-*`, snapshot `kn_test_trial_2026-11-08`, DB `test_database`)
| Pemeriksaan | Sebelum (HEAD `70eb9fd`) | Sesudah |
|---|---|---|
| `test_prep_d2_gate_txn.py` (baru) | — | **11 passed** |
| Jest `prepD2GateReview.test.js` (baru) | — | **7 passed**; bersama `prepD1GateV2`, `phase3P8Activation`, `uatV3S2Cbd`, `permissionGates`: **31 passed** |
| ESLint berkas FE yang diubah/baru | 4 warning lama (unused eslint-disable) | **0 error**, 4 warning lama yang sama |
| `test_prep_d1_gate_v2` | 18 passed | **18 passed** |
| `run_rfid_v2_integration.py` / `run_rfid_v2_extended.py` | (D1: 53 / 35 PASS) | **53 / 35 PASS** |
| `test_prep_c_warehouse_putaway` · `test_prep_b_initial_registration` · `test_prep_integrasi_freeze_putaway` | 15 · 3 · 4 passed | **15 · 3 · 4 passed** |
| `test_makloon_celup_rolls` · `test_iter263_wms_rfid_r0r1r2` · `test_iter264_putaway_fixes` | 20 · 30 · 4 passed (2 skip) | sama |
| `test_iter117_p09` · `test_iter118_p10` (proses terpisah) | 18 · 8 passed | **18 · 8 passed** |
| Merah lama (data/fixture, di luar D2): `test_fase_sl_rfid_alias` 9 F · `test_p03_transfer_receipt` 11 E · `test_iter14_wh_transfer_rolls` 4 F · `test_transfer_status_guard` 3 F · `test_f10_cbd_dp_dispatch_gate` 5 F · `test_iter292_f01_dispatch_gl` 1 F · `test_iter318_dispatch_logistics` 5 F · `test_iter265_r3r4r5` 6 F · `test_f06_pod_closes_so` 3 F · `test_p02_wms_putaway` 1 F | 48 gagal/error | **48 — daftar identik** (diff kosong), tidak ada merah baru; `test_g3_phase02b`/`test_trial_22okt_flow` skip di keduanya |

Baseline diukur pada salinan `git archive 70eb9fd` dengan Mongo & backend sendiri dari snapshot yang sama; sesudah
diukur pada DB yang di-`mongorestore --drop` ulang. Skenario uji baru: PA dari GRN (draf otomatis → terbit → kirim) →
gate IN 2 trip (close diulang tidak menggandakan trip/buku) → sisa handheld → PA selesai → sesi IN hijau dengan 1
pelengkap handheld; transfer 2 trip → `partially_received` → `completed` → sesi hijau; SJ 2 trip → bukti trip 1/2 →
berangkat → `ROLLS_MISSING` → notifikasi → petugas 403 → Admin Gudang terima → kasus selesai, ulang 409, audit;
lintasan kuning ber-klaim (bukti tidak lengkap) → roll tercatat + kasus wajib ditutup → roll kurang ditolak; area beku →
kuning tanpa transaksi, kios kuning, terima saat beku 409 (status dikembalikan) → terima setelah beku dilepas → PA
selesai; gedung handheld → bukti saja lalu handheld; simulator ops dengan Mode simulasi mati (bukti saja) / nyala (tiba
2 trip); merah → kunci, akui 403 untuk petugas (antrean & endpoint D1), 200 untuk Admin Gudang, roll tanpa dokumen tidak
bisa diterima; koreksi klaim pindah + lepas (403/400/404, riwayat, audit); cek muat wajib dipenuhi gate.

Guardrail (sesudah): custom_modals 98, error_notice 274, escape_layers, uom_vocab, knselect_contract, picker_portal,
detail_modal 27, modal_dismiss, page_tabs, role_label, notification_audience, rfid_tag_unique, access_catalog_nav
**PASS**. Ratchet (baseline → sesudah): auth_coverage 8 → **8**, atomic_claim 6 → **6** (BELUM DITINJAU 75 → **75**),
to_list_bound 6 → **6**, numeric_bounds 3 → **3**, qty_dual 5 → **5**, ref_unlink 3 → **3**.
`verify_state_machine.py` tidak dijalankan (sesuai brief); CODEBASE_MAP.md tidak diregenerasi; tanpa peramban.

## 8. Keputusan desain (implementer — mohon ditinjau)
1. **Transaksi sinkron di close** (sesudah keputusan disimpan, sebelum respons ke reader): sederhana & deterministik;
   kegagalan transaksi tidak menggagalkan ACK (buku `error` + kasus antrean + "Ulangi transaksi"; close yang diulang
   agent juga melanjutkan). Risiko: latensi close untuk muatan besar — **uji beban 2.000 roll belum** (AUD-MW-07).
2. **Keputusan ke reader tidak berubah oleh hasil transaksi**; hanya mode gedung/area beku (dicek SEBELUM keputusan
   final) yang bisa menurunkan hijau → kuning. Gagal cek mode → kuning `TXN_CHECK_FAILED`, mode dihitung ulang saat
   transaksi.
3. **Reader harus tertaut di pasangan gate profil gedung** agar mencatat transaksi (selain itu bukti saja + INFO) —
   mencegah reader uji/salah gudang memindah stok.
4. **Kuning ber-klaim mencatat roll yang cocok** (K-RFID-09: barang jalan); roll bermasalah ke antrean. Kuning tanpa
   klaim tidak mencatat apa pun.
5. **Simulator** hanya bertransaksi bila Mode simulasi RFID PT menyala (pola cek muat simulasi). Data uji trial
   menyalakannya untuk `ent_ksc`, `ent_kanda`, dan satu PT lain.
6. **Klaim untuk roll yang diterima admin** memakai `passage = review:{kasus}` → lintasan nyata berikutnya untuk roll itu
   = merah "sudah lewat" (konsisten dengan klaim lintasan).
7. Penutupan sesi SJ di **logistik berangkat** (bukan saat SJ terbit — SJ terbit SEBELUM barang lewat gate).
8. Kait di luar daftar milik D2 (kecil, best-effort, try/except): `putaway_order_service.confirm_arrival` (1 baris),
   `logistics_service` (2 titik + 1 fungsi), `repair_order_service.receive` (3 baris), `rfid_service.DEVICE_PUBLIC_FIELDS`
   (+`protocol`, `v2_config_version`), `LoadingCheckPanel.jsx` (petunjuk).

## 9. Sisa / butuh perangkat / keputusan
- **Order Makloon**: penutupan sesi OUT masih manual; kait di penerimaan hasil MKO perlu ditambah (berkas besar).
- **Gate IN Perbaikan/Makloon kembali** hanya bukti — penerimaan hasil tetap lewat dokumen.
- **Uji beban** close bertransaksi (2.000 roll), kalibrasi ambang, interlock pasangan berdampingan (K-RFID-04),
  K-RFID-03/05/08 tetap terbuka — semua butuh perangkat/lokasi.
- Pemilik: konfirmasi aturan cek muat gedung bergate (§2) dan bahwa admin gudang (bukan petugas) yang membuka kunci gate.
- Tidak ada job penjadwal untuk mengulang transaksi gagal (diulang lewat close agent / tombol antrean).

## 10. Kontrak 2.1 — untuk paket E
**Tidak ada field baru.** Keputusan memakai kode alasan baru di `reason_codes[]`/`reasons[]` (string bebas di
kontrak): REVIEW `AREA_FROZEN`, `TXN_CHECK_FAILED`; INFO `HANDHELD_MODE`, `GATE_NOT_PAIRED`, `QUANTITY_MODE`,
`SIMULATED_EVIDENCE`. Agent cukup memperlakukan verdict REVIEW sebagai kuning seperti di D1. Endpoint operator baru
(antrean, kios, koreksi klaim) memakai sesi pengguna, bukan device key, dan tidak masuk OpenAPI device.
