# Persiapan RFID tanpa perangkat — gelombang 2 (integrasi)

- Tanggal: 9 Nov 2026 · Pelaksana: Claude Code (koordinator) + 2 agen paralel (worktree terpisah).
- Dasar: permintaan pemilik 8 Nov ("siapkan sebisa mungkin sebelum perangkat datang"), keputusan di
  [`../KEPUTUSAN_GATE_RFID.md`](../KEPUTUSAN_GATE_RFID.md) §6–§8, lanjutan [gelombang 1](PREP-GELOMBANG-1.md).
  Status: **implemented_pending_review**.
- Branch integrasi `integrasi-prep2` digabung ke `main`. Laporan per paket:
  [D2](PREP-D2-GATE-TRANSAKSI.md) · [E](PREP-E-AGENT-050.md).

| Paket | Isi | Commit paket |
|---|---|---|
| D2 — Gate → transaksi | Gate IN di gedung bermode gate (reader tertaut di profil gedung) mencatat tiba Putaway per trip & terima transfer per roll; gate OUT menyimpan bukti per trip di SJ/transfer/Makloon/Perbaikan/PA; sesi dokumen ditutup otomatis di titik siklus hidup (PA selesai, transfer selesai, SJ berangkat, perbaikan diterima) → roll kurang = kuning ke antrean; area beku = kuning tanpa transaksi; **antrean periksa** admin gudang (Monitor Gerbang › Antrean periksa) dengan bukti per roll + tindakan beraudit; koreksi klaim; kios KUNING; notifikasi | `832cb15`, `68e40a2` |
| E — Aplikasi reader 0.5.0-lab | Photo-eye satu arah (A masuk, B keluar) + cadangan RF otomatis, pre-buffer 10 dtk di RAM, daftar latar, ringkasan per EPC × antena 250 ms, `seq`/`boot_id`, RSSI & antena tahan format Indonesia, galat terstruktur dari `detail.code`, setelan radio dibaca ulang, 4 GPO, cek layanan UHF bawaan, **mode uji meja K-RFID-03** ber-PIN (hasil JSON), migrasi SQLite 0.4 → 2; APK `delivery/KN-U300-Agent-0.5.0-lab-debug.apk` | `1b0fc41`, `dfc75f9` |

## Perbaikan saat integrasi (koordinator)
- **Merah palsu muatan rapat** (usulan E §9.2; K-RFID-09) — `76efbb0`. Dua muatan berurutan di gate satu arah yang
  sama: pre-buffer lintasan ke-2 ikut membaca roll muatan ke-1 yang baru diklaim → dulu **MERAH** (`REPLAY_EXIT` /
  `REPLAY_CROSSING` / `NOT_IN_DOCUMENT`) + gate terkunci. Sekarang (`rfid_v2_policy._carryover`):
  * roll punya klaim lintasan LAIN di gate & arah yang sama ≤ 120 dtk **dan** bacaan terkuatnya sebelum sinar A
    terpotong → INFO `PREVIOUS_PASSAGE` (tidak dinilai ulang, tidak diklaim, tidak menarik dokumen muatan lain ke
    auto-cocok, tidak ada transaksi); lintasan yang isinya hanya bawaan = BATAL;
  * klaim baru-baru ini tetapi waktu tidak membuktikan (cadangan RF tanpa sinar / puncak di dalam lintasan) → REVIEW
    `PREVIOUS_PASSAGE_RECENT` (kuning tanpa kunci);
  * klaim lebih lama dari jendela → penilaian biasa (replay tetap MERAH).
  Jendela 120 dtk = titik awal kalibrasi, konstanta server (belum di `GateParameters` — skema kontrak menolak kunci
  baru; usulan E §9.5). Simulator kini menaruh puncak roll dokumen di dalam jendela sinar (realistis) + parameter
  `carry_epcs`. Indeks crossing `(roll_id, direction, at)`. Label Indonesia kode baru.
- **`run_u300_https.py`** mengompilasi seluruh `core/` agent 0.5 (`1a96020`) — daftar sumber yang sama dikompilasi
  manual dengan JDK toolchain: berhasil. Skrip penuhnya (butuh Python host + Mongo) tidak dijalankan.
- **Uji D1 meninggalkan sisa** di koleksi baru D2 (antrean periksa, buku transaksi gate, notifikasi) → pembersih
  ditambah (`0a0d6dc`); sisa dari uji koordinator di DB uji (17 kasus, 24 notifikasi, 26 baris buku yatim —
  semuanya perangkat `dev_TEST_D1_*`) dihapus; uji ulang → 0 sisa.
- Uji/skrip lama yang menganggap "dibaca lagi di gate yang sama" = merah disesuaikan: klaim dimundurkan ke luar jendela
  untuk menguji replay sungguhan (`test_claims_do_not_leak_on_conflict`, `run_rfid_v2_integration`,
  `run_rfid_v2_extended`), ditambah cek kuning untuk kasus di dalam jendela.
- `CODEBASE_MAP.md` diregenerasi.

## Bukti uji (apa adanya)
- **Perbandingan `main` (`70eb9fd`) vs integrasi** (`0a0d6dc`) pada salinan DB uji yang sama (`kn_test_trial_2026-11-08`),
  Mongo & backend sementara terisolasi (kode disalin ke dalam kontainer), **59 berkas uji lama relevan** (gelombang 1
  + logistik/dispatch/cek muat/perbaikan/SJ):
  * `main`: 70 gagal / 389 lulus / 21 error · integrasi: 70 gagal / **402** lulus / 21 error (+13 = D2 11 + D1 bawaan
    muatan 2). **Daftar 91 uji gagal/error identik** — tidak ada yang hanya gagal di integrasi; tidak satu pun uji
    `test_prep_*` gagal. Merah lama terbanyak: `p03_transfer_receipt` 11, `fase_sl_rfid_alias` 9,
    `iter277_gates_pin_isolation` 8, `fb02_logistics` 6, `f11_f12_return_receipt_qc` 6, `iter318`/`f10`/`l05` 5.
  * `test_iter117_p09` 18/18 dan `test_iter118_p10` 8/8 lulus di keduanya (proses terpisah).
  * Skrip `run_rfid_v2_integration` **54/54** (main 53 — +1 cek kuning bawaan muatan), `run_rfid_v2_extended` **36/36**
    (main 35 — +1 cek regrouping di dalam jendela).
- **Stack uji resmi** (`kn-uji-backend`, DB `kn_test_trial`, kode integrasi): `test_prep_d1_gate_v2` **20/20** (termasuk
  `test_carryover_previous_load_not_red` & `test_carryover_without_beam_evidence_is_review`), `test_prep_d2_gate_txn`
  **11/11**; sesudah uji → 0 sisa di antrean periksa/buku transaksi/notifikasi.
- **Aplikasi reader** (diulang koordinator dengan toolchain lokal): `test-host.ps1` lulus semua — 396 assertion (Safety 27,
  Core 91, state machine 52, Host 44, Pipeline 83, DecisionPolicy 75, HTTPS loopback 24), 21 payload kontrak 2.1 / 9 skema
  + 9 cek negatif + template profil, 9 kasus integritas snapshot. Hash APK 0.5.0 cocok `SHA256SUMS.txt`
  (`9f2b2d28…6ef0c15`). Build APK + lint + uji Java → ERP lokal 41/41 = hasil agen E (tidak diulang; perbaikan bawaan
  muatan hanya menurunkan merah → info/kuning, tidak ada jalur yang jadi lebih ketat).
- **Jest** `prepAMasterCleanup`, `prepBInitialRegistration`, `prepCWarehousePutaway`, `prepD1GateV2`, `prepD2GateReview`:
  **33/33**. **ESLint** berkas frontend yang berubah: 0 error, 4 peringatan "unused eslint-disable" lama.
- **Guardrail** — main vs integrasi di lingkungan yang sama, hasil **identik**: role_label, blocking_dialogs,
  status_history lolos; auth_coverage 8, atomic_claim 6, to_list_bound 6, numeric_bounds 3, qty_dual 5, ref_unlink 3,
  line_scope 18 (merah lama, tidak naik); `no_secrets` 10 temuan sama persis (berkas `.env` salinan uji + XML laporan uji
  lama). Di stack resmi: custom_modals 98, error_notice 274, escape_layers 1172, uom_vocab 1173, knselect_contract,
  picker_portal 313, detail_modal 27, modal_dismiss, page_tabs, view_aliases 84, access_catalog_nav, desk_targets 33,
  notification_audience, rfid_tag_unique, roll_identity — lolos. Catatan: hitungan "BELUM DITINJAU" atomic_claim di
  kontainer pembanding = 95 di main maupun integrasi (lingkungan berbeda dari angka 75 gelombang 1; yang dibandingkan
  hanya main vs integrasi di lingkungan sama).
- **Peramban** (`:3063`, Admin): Monitor Gerbang › tab **Antrean periksa** (ringkasan terbuka/merah/kuning, saringan,
  baris kasus berbahasa Indonesia termasuk label baru); Perangkat RFID › **Integrasi reader U300** (status kontrak 2.1.0,
  kesehatan reader, tautan ke antrean periksa). Pop-up hanya dibuka lalu ditutup; tidak ada data disimpan. Tangkapan
  layar tidak tersedia (panel peramban tersembunyi) — verifikasi lewat teks/DOM; permintaan halaman yang terekam 200.

## Perubahan perilaku untuk pengguna
- Gedung bermode gate (reader tertaut di profil gedung): lintasan gate IN hijau/kuning langsung mencatat **tiba
  Putaway** / **terima transfer** per trip; roll yang tak terbaca tetap menunggu handheld.
- Trip ke-2 dst. untuk PA/transfer yang sudah tiba sebagian kini hijau (dulu merah `DOC_MISSING`).
- SJ berangkat / PA selesai / transfer selesai / perbaikan diterima → roll yang tidak terbaca gate muncul di **antrean
  periksa** (kuning).
- Area beku pendaftaran awal: lintasan kuning, barang jalan, tanpa transaksi.
- **SO dari gedung bergate dengan gate OUT tertaut tidak lagi wajib Final Loading Check** (gate memenuhi kebijakan;
  handheld opsional, hasilnya tetap mengikat; roll tanpa tag tetap ditolak).
- **Membuka kunci gate merah** (panel U300, kios, antrean) kini butuh izin approve (Admin/Manajer/Admin Gudang);
  petugas gudang biasa ditolak.
- Lintasan simulator hanya menulis transaksi bila "Mode simulasi RFID" PT menyala.
- Muatan rapat berurutan: roll muatan sebelumnya yang ikut terbaca tidak lagi membuat gate merah.
- Reader 0.5 belum dipasang di mana pun (APK lab, debug-signed).

## Butuh keputusan pemilik
Dari gelombang 2:
1. **Cek muat di gedung bergate** (D2): gate OUT tertaut dianggap memenuhi "wajib Final Loading Check" — setuju?
2. **Yang boleh membuka kunci gate merah** (D2): hanya Admin/Manajer/Admin Gudang (izin approve), bukan petugas — setuju?
3. **Jendela "muatan sebelumnya" 120 detik** (koordinator): roll yang baru lewat gate yang sama dalam 2 menit dan
   terbaca lagi tidak dijadikan merah. Perlu dikalibrasi di lokasi (jarak antar muatan nyata).

Masih terbuka dari gelombang 1 (belum dijawab): izin unduh lembar master MD, waktu perbaikan master sebelum opname,
roll lama yang masih dipesan saat pendaftaran, persetujuan Finance terpisah, gate Gedung Retur RCM, penanda "minta
inspeksi". Tetap terbuka: K-OPN-05, K-RFID-03/05/08, penamaan alamat bin.

## Belum dikerjakan
- **Butuh perangkat/lokasi**: uji meja SDK U300 (mode diagnostik sudah ada di aplikasi), arti setelan TagFocus/FastID,
  format antena/RSSI asli, kalibrasi ambang & parameter lintasan, pengkabelan photo-eye, uji beban close bertransaksi
  2.000 roll, runtime Android (migrasi SQLite di perangkat, boot, soak 24 jam), pilot.
- Penutupan sesi OUT **Order Makloon** masih manual (kait penerimaan hasil MKO belum ada).
- Usulan kontrak E yang belum diambil: penanda lintasan gabungan (`boundary_flags`), posisi antena di ringkasan, kunci
  baku kesehatan di telemetry, parameter tuning agent ke `GateParameters` — butuh kontrak 2.2 (agent + server).
- Ringkasan antrean tanpa filter gudang menghitung lintas gudang (angka saja).
- Tidak ada job penjadwal untuk mengulang transaksi gate yang gagal (diulang lewat close agent / tombol antrean).
