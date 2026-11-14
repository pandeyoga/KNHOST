# KP-T7 — Pengingat dan penjadwal yang bisa diatur: selang menit, penerima, dan ambang per PT

- Commit awal: `69cc4e3` (dikerjakan) · digabung di atas `3c459d9` (sesudah PR-T5, PK-21)        - Commit akhir: `0a91095`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-09, KP-20, KP-21 (spesifikasi `docs/blueprint/unit/KP-T7.md`; keputusan K-47, `00` §4.1)
- Risiko: sedang (satu serah-terima).

## Cek ulang "Keadaan sekarang"

Spesifikasi dibaca pada `3132cc4`; dicek ulang pada `69cc4e3`. Semua butir masih berlaku; beberapa baris bergeser.

| # | Hasil di `69cc4e3` |
|---|---|
| 1 | Berlaku. `schemas_scheduler.py:11` (`JobConfig`: `hour`, `minute`, `interval_hours` saja) |
| 2 | Berlaku. `SchedulerParts.jsx:77` (`ScheduleEditor`) — mengirim `interval_hours`, satuan "jam" untuk semua job berselang |
| 3 | Berlaku, bergeser: `scheduler_service.py:461` (`_apply_jobs`, cabang `elif cfg.get("interval_minutes")`), `:312` (`job_defaults`), `:111` (`reservation_expiry`). Job berbasis menit kini **dua belas** (KF-T3 menambah `config_apply_due`), bukan sebelas. Terbukti merah U1/U2: `PUT … {"interval_hours": 2}` → 200 dan tersimpan `{"interval_minutes": 30, "interval_hours": 2}`, pemicu tetap 30 menit; `interval_minutes` dibuang skema (pemicu tetap 30) |
| 4 | Berlaku. `alert_service.py:25–29` (`AP_DUE_SOON_DAYS`, `WO_RELEASED_STALE_DAYS`, `WO_DRAFT_STALE_DAYS`, `TASK_STALE_DAYS`, `MAX_ALERTS_PER_JOB`) |
| 5 | Berlaku. `alert_ops_service.py:52` (`PO_ARRIVAL_LOOKBACK_HOURS`), `:54` (`AR_DUE_SOON_OFFSETS`), `:55` (`MAX_ALERTS_PER_JOB` kedua) |
| 6 | Berlaku. `alert_service.py:85/172/201/234` ("manager"), `:277/319` ("warehouse"); `alert_ops_service.py:151` ("manager"), `:159` ("warehouse"), `:247` ("manager") |
| 7 | Berlaku. `escalation_service.py:36` (`ESCALATION_CHAIN`; dipakai `plan_escalations` sejak PR-T4 bersama `notify_addresses`); `wa_alert_service.py:31` (`BROADCAST_ROLES`) |
| 8 | Berlaku, bergeser: `turn_notification_service.py:85` (`STALE_DAYS`, dari 80); `approval_reminder.py:40`; `design_request_service.py:693` (dari 688); `marketing_service.py:35` (dari 37); `marketing_ext.py:20`; `marketing_cost_service.py:264` (dari 261); `printer_stuck_watch.py:13`; `inventory_drift_watch.py:40` |
| 9 | Berlaku. `wa_alert_service.py:76` (`raw_settings`); `routers/scheduler.py:90` (`update_settings`, dari 89) |
| 10 | Berlaku, bergeser: `config_catalog_core.py:975` (`notif.low_stock_division`, dari 943), `:988` (`notif.po_stage_stuck_days`, dari 956) |
| Dipakai ulang | `notification_service.py:25` (`create_addressed`) dan `alert_ops_service.py:46` (`_AR_TEAM_PERMISSION`) — berlaku. PR-T4 tidak menyediakan pembantu pembuat alamat (hanya `notify_addresses` untuk pembaca), jadi `reminder_policy.notify` memanggil `create_notification`/`create_addressed` |

## KP-09 / KP-20 / KP-21 — selang menit, penerima, dan ambang per PT

- Berlaku di HEAD: ya, semua (tabel di atas; merah di bawah).
- Akar masalah: pemicu memilih `interval_minutes` lebih dulu dan nilai itu selalu ada dari bawaan job, sedangkan layar
  dan skema hanya mengenal `interval_hours`; penerima tiap pengingat ditulis sebagai satu nama peran di titik kirim dan
  ambangnya konstanta modul, sehingga pemilik tidak bisa menentukan per PT siapa yang menerima dan kapan.
- Perubahan perilaku (sebelum → sesudah):
  - **Selang menit**: `JobConfig.interval_minutes` (1–1440). Satuan job = "menit" bila bawaannya `interval_minutes`,
    selain itu "jam"; job harian tanpa selang. `PUT /api/scheduler/settings`: job menit + `interval_minutes` → disimpan
    dan `reschedule()` memakai nilai baru; job menit + `interval_hours` → 400 "Jadwal “{label}” diatur dalam menit.";
    job jam + `interval_minutes` → 400 "… diatur dalam jam."; job harian + selang → 400 "… diatur dengan jam dan menit
    harian."; `rfid_reader_health_watch`/`rfid_gate_txn_retry` + selang → 400 "… tidak bisa diubah dari layar."
    (on/off tetap bisa). Pemicu dan `schedule_label` memakai field sesuai satuan (perilaku sama untuk data lama).
    `GET /api/scheduler/jobs` menambah `interval_unit`, `interval_value` (selang yang dipakai pemicu), `locked`,
    `recipients` (ringkasan penerima untuk PT aktif; "Semua PT" = grup), `recipient_key`, `thresholds`
    (`[{key, label, value, unit, text, group}]`).
  - **Penerima** (`backend/services/reminder_policy.py`): `recipients_for` (tabel PT `notif.reminder_recipients` →
    tabel grup → bawaan), `notify` (satu peran → `create_notification(recipient_role=…)` persis seperti dulu; beberapa
    peran → `create_addressed(roles=…)`; izin → `create_addressed(permission=…)`), `threshold`/`per_pt` (ambang per
    PT, cadangan = bawaan registry). Sepuluh pengingat dialihkan: piutang lewat tempo, hutang, penyusutan, anggaran,
    perintah kerja, tugas gudang, barang PO datang (manajer + gudang), pendingan siap (sembilan titik peran) + piutang
    mendekati jatuh tempo (izin `ar_receipt.create`).
  - **Ambang**: 15 konstanta → pengaturan per PT dokumen (bawaan = nilai lama). Job yang menyaring di kueri
    (tugas gudang, barang PO datang, piutang mendekati jatuh tempo, tayang konten, label tertahan) memakai batas
    terluas/terkecil/gabungan grup + PT aktif di kueri, lalu menyaring tiap dokumen dengan batas PT-nya — dengan bawaan
    kuerinya identik dengan sebelum unit.
  - **Rantai eskalasi** `notif.escalation_chain` (hanya grup), **peran siaran WhatsApp** `notif.wa_broadcast_roles`
    (hanya grup), **nomor PIC WhatsApp per PT** `notif.wa_pic_number` (nomor PT menggantikan nomor PIC umum untuk
    notifikasi PT itu).
  - **19 kunci** (tabel spesifikasi) berizin `scheduler.configure` (bawaan Admin). Pemeriksa simpan
    (`reminder_policy.periksa_nilai`, dipanggil `config_resolver.set_value`): "Pengingat “x” tidak dikenal.",
    "Peran “x” tidak ada.", "Izin “x” tidak ada.", "Baris n: pilih paling sedikit satu peran." (+ rantai/peran siaran
    memakai pesan peran yang sama; hari pengingat −30…30; nomor PIC sah).
  - **Layar** (Penjadwal & Notifikasi): editor jadwal "tiap [n] menit" (1–1440) untuk job bersatuan menit, mengirim
    `interval_minutes`, nilai awal `interval_value`; job terkunci hanya-baca "Jadwal teknis — tidak diubah dari
    layar."; kolom **Penerima** dan **Ambang** + tautan **Ubah** (`openConfig` → kunci di Pusat Pengaturan, PT aktif;
    "—" bila tidak ada). Tab Penerima Notifikasi: kunci baru lewat editor baku; tabel penerima = editor baris (kolom
    **Pengingat**, **Cara menentukan** "Peran yang dipilih"/"Semua pemegang izin", **Peran** pilihan ganda,
    **Izin** pilihan berlabel); peran penerima WhatsApp = kotak centang berlabel.
- Data: tanpa koleksi baru. `system_settings{scope:"alerts"}.jobs.<id>.interval_minutes` (ENTITY_REGISTRY). Skrip
  `scripts/migrate_kpt7_jadwal.py` (bawaan = lapor; `--apply` membuang `interval_hours` sisa pada job bersatuan menit;
  argumen tak dikenal/bertentangan → keluar 2 sebelum menyentuh basis data). **Tidak dijalankan terhadap database mana
  pun selain database tiruan** (H3); keluaran lingkungan B: `bukti/KP-T7/skrip_migrasi_lingkungan_b.log`.
- Berkas berubah:

| Berkas | Isi |
|---|---|
| `backend/services/reminder_policy.py` (baru) | `PENGINGAT`, `LINTAS_PT`, bawaan penerima/eskalasi, `recipients_for`, `notify`, `threshold`, `per_pt`/`PerPT`, `union_over_entities`, `active_entity_ids`, pemeriksa nilai, ringkasan label, pilihan editor (peran, izin) |
| `backend/config_catalog_core.py` | Blok `KP-T7`: 19 kunci sesudah `notif.po_stage_stuck_days` |
| `backend/services/config_resolver.py` | 2 baris (`set_value`): `periksa_nilai` |
| `backend/schemas_scheduler.py` | `JobConfig.interval_minutes` |
| `backend/services/scheduler_service.py` | Blok `KP-T7` (`LOCKED_JOBS`, `JOB_REMINDERS`, `JOB_THRESHOLDS`, `interval_unit`, `interval_value`, `job_patch_error`, `job_policy`); `schedule_label`, `_apply_jobs`, `jobs_status(entity_id)`; 6 deskripsi + 1 label job (angka kini "bawaan") |
| `backend/routers/scheduler.py` | `GET /scheduler/jobs` dengan PT aktif; validasi satuan di `PUT /scheduler/settings` |
| `backend/services/alert_service.py`, `alert_ops_service.py` | Konstanta → `reminder_policy`; titik kirim → `policy.notify` |
| `backend/services/escalation_service.py` | `ESCALATION_CHAIN`/`MAX_PER_RUN` → pengaturan; `plan_escalations(..., chain=None)` |
| `backend/services/wa_alert_service.py` | `BROADCAST_ROLES` → pengaturan; nomor PIC per PT |
| `backend/services/turn_notification_service.py`, `approval_reminder.py` (`_ringkas` async), `design_request_service.py`, `marketing_service.py`, `marketing_ext.py`, `marketing_cost_service.py`, `printer_stuck_watch.py`, `inventory_drift_watch.py` | Konstanta butir 8 → pengaturan per PT |
| `backend/access_modules.py` | Blok `KP-T7`: `VIEW_RESOURCE_OVERRIDES` + `scheduler` untuk 4 tab (aturan KF-T1 U14) |
| `scripts/migrate_kpt7_jadwal.py` (baru) | Skrip lapor / `--apply` |
| `frontend/src/features/admin/scheduler/SchedulerParts.jsx` | `ScheduleEditor` bersatuan, terkunci; `JobPolicyCells` (kolom Penerima & Ambang) |
| `frontend/src/features/settings/config/SettingTableEditor.jsx`, `SettingEditor.jsx`, `configApi.js` | Blok `KP-T7`: kolom `multi` + `options_source: "roles"`; daftar berpilihan = kotak centang; `formatValue` daftar berlabel |
| `frontend/src/config/__tests__/fixtures/access_builtin_fixture.json` | Dibangkitkan ulang (`tests/fe03_access_fixture.py`) |
| Uji: `backend/tests_mem/test_KPT7_pengingat.py`, `test_KPT7_setara.py`, `data/kpt7_u5_acuan.json` (baru), `test_KFT1_izin_pengaturan.py` (`KPT7_KUNCI = 19`), `backend/tests/test_bp_KPT7_pengingat.py` (baru, lapis A), `frontend/src/features/admin/scheduler/__tests__/kpt7Penjadwal.test.js` (baru) | |
| `CODEBASE_MAP.md`, `ENTITY_REGISTRY.md`, `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | Peta dibangkitkan (`gen_codebase_map.py`); field `interval_minutes`; baris KP-T7; istilah "Penerima & ambang pengingat", "Jadwal teknis" |

- Commit: belum (instruksi: tanpa commit).
- Pengujian: tabel di bawah.
- Bukti UI: belum diuji jalan di peramban (U14); uji komponen jest 5/5 menggantikan sebagian.
- Fixture disiapkan langsung vs proses bisnis dijalankan: sisip langsung = tagihan pemasok, pelanggan + pesanan + surat
  jalan, aset, perintah kerja, tugas gudang, notifikasi lama (U10), posting konten, antrean label, permintaan desain,
  sisa `interval_hours` (U4); pembaca ditiru = `budget_service.budget_vs_actual`, `alert_ops_service._available_qty`
  (U5), `marketing_cost_service.realized_by_campaign`, `gl_service.inventory_reconciliation`, `turn.notify_turn`
  (U17/U18 — hanya mencatat ambang yang diteruskan); penjadwal = pemicu tiruan (pemicu APScheduler asli didaftarkan ke
  objek tiruan). Lewat API = `PUT /api/scheduler/settings`, `GET /api/scheduler/jobs`, `PUT /api/config/values`
  (+ `clear`/`reset`), pembuatan peran uji.
- Dampak pada modul terkait: dengan bawaan semua notifikasi lahir sama persis (U5: 22 notifikasi, himpunan identik
  dengan kode lama). Pemanggil event-driven `notify_po_arrival`/`notify_backorder_ready` ikut membaca penerima per PT.
  `GET /api/scheduler/jobs` kini membaca ±60 nilai pengaturan per permintaan (layar admin).
- Keterbatasan / yang belum diuji: U14 uji jalan di peramban.
- Status: implemented_pending_review.

## Uji penerimaan

`backend/tests_mem/test_KPT7_pengingat.py` + `test_KPT7_setara.py` (lingkungan B). Merah = kedua berkas dijalankan di
salinan `git archive 69cc4e3` (kode lama utuh): **18 gagal, 1 lulus (U5 — setara, memang harus lulus)**
(`bukti/KP-T7/tests_mem_KPT7_merah_kode_lama.log`). Hijau di kode baru: **19/19**
(`…_hijau_kode_baru.log`). Acuan U5 (`data/kpt7_u5_acuan.json`) direkam dari kode lama (`KN_TULIS_ACUAN_KPT7=1`).

| ID | Lapis | Merah di kode lama (sebab) | Hasil kode baru |
|---|---|---|---|
| U1 | B | ya — `interval_minutes` dibuang skema, pemicu tetap 30 menit (`assert 30.0 == 120`) | Lulus — 200; pemicu 120 menit; `menit`/120/"Setiap 120 menit"; job jam `jam`/4; job harian `""`/`None` |
| U2 | B | ya — 200, tersimpan `interval_hours: 2` di samping `interval_minutes: 30` | Lulus — 400 pesan persis; pemicu 30; tidak tersimpan |
| U3 | B | ya — 200 untuk keduanya | Lulus — 400 "…diatur dalam jam." / "…tidak bisa diubah dari layar."; tambahan: job harian 400; `ops_stalled` 6 jam → 360 menit; tepat dua job `locked` |
| U4 | B | ya — skrip belum ada | Lulus — pemicu 5 menit sebelum & sesudah; lapor tidak menulis; tulis membuang `interval_hours` (job jam tidak disentuh); ulang 0; argumen salah → 2 |
| U5 | B | **tidak** (setara — acuan direkam dari kode lama) | Lulus — himpunan (`type`, `ref`, `recipient_role`, `recipient_user`, `entity_id`) 22 notifikasi sama persis |
| U6 | B | ya — kunci tidak ada (404) | Lulus — hanya tagihan `ent_kanda` (10 ≤ 14; KSC 10 > 7) |
| U7 | B | ya — 404 | Lulus — `ent_kanda` per orang (akun Tanpa Acuan + Admin + Manajer), tanpa `recipient_role: "manager"`; `ent_ksc` tetap `("manager", None)`; ringkasan layar "Pemegang izin Tagihan Supplier — Bayar" (Kanda) / "Manajer" (KSC), ambang `7 hari`, `40 peringatan` |
| U8 | B | ya — 404 | Lulus — 400 "Peran “direktur” tidak ada."; tambahan: tiga pesan lain + rantai & peran siaran; tidak ada baris tersimpan |
| U9 | B | ya — 404 | Lulus — [-7, 0]: H-7 diingatkan, 3 hari lagi tidak; bawaan: kebalikannya; butir −45 → 400 |
| U10 | B | ya — 404 | Lulus — eskalasi ke `warehouse_admin` |
| U11 | B | ya — 404 | Lulus — Kanda `6281222222222`, KSC `6281111111111`; nomor tak sah 400 |
| U12 | B | ya — 404 (kunci tidak ada) | Lulus — Manajer Kosong 403 (pesan tanpa id teknis); Tanpa Acuan `scheduler.configure` 200 |
| U13 | B | ya — `KeyError` registry | Lulus — 19 kunci: tulis grup → `value_of` & `/config/effective`; lapisan PT → hanya PT itu (kunci hanya-grup: PT → 400); nilai tak sah → 400; pulih = bawaan |
| U14 | layar | ya — uji komponen 5/5 merah di `src` lama | Uji komponen 5/5 lulus (`kpt7Penjadwal.test.js`). **Belum diuji jalan di peramban** |
| U15–U20 (tambahan, `02` §2.4 butir 2) | B | ya — kunci/pembantu tidak ada | Lulus — nilai A/B per PT untuk perintah kerja dirilis, tugas gudang, jendela PO, batas per jalan, giliran diam, jarak tayang, toleransi tepat waktu, anggaran kampanye, label tertahan, kelipatan kritis, dokumen disebut, tenggat desain, peran siaran; U20: pengingat lintas PT hanya grup, PT tanpa baris → grup → bawaan, beberapa peran → per orang |
| Lapis A (tambahan) | A | — | `backend/tests/test_bp_KPT7_pengingat.py`: `GET /scheduler/jobs` di data acuan, 400 tanpa mengubah dokumen `alerts`, skrip mode lapor tidak menulis, bawaan 19 kunci — **lulus** di lingkungan A (backend `0a91095`, data acuan) |

`t1_config.py` (arsip audit, lingkungan B, 402 kunci, galat 0; `bukti/KP-T7/t1_config_19_kunci.log`): 15 kunci angka
lulus penuh (tulis grup → API/resolver/pembaca lama; lapisan PT hanya PT itu; tak sah → 400; pulih = bawaan); 4 kunci
kompleks (`list`/`table`) "simpan ulang" 200 (batas skrip); `notif.wa_pic_number` — nilai uji skrip "uji" ditolak
400 oleh pemeriksa nomor (benar; putaran U13 memakai nomor sah). `awal_sama_legacy: false` untuk ke-19 kunci = sama
dengan kunci `notif.*` lama (tidak ada di `DEFAULT_GLOBAL_SETTINGS`; mesin membaca lewat resolver).

`tests_mem` seluruhnya (`bukti/KP-T7/tests_mem_seluruh_sebelum_sesudah.log`): sebelum **494 lulus / 2 dilewati /
3 xfail** → sesudah **513 / 2 / 3** (+19 uji KP-T7). `test_KFT1_izin_pengaturan.py` disesuaikan (`KPT7_KUNCI = 19`
di U04 — katalog bertambah 19; U02 tetap karena izinnya `scheduler.configure`; U14 lulus berkat
`VIEW_RESOURCE_OVERRIDES`).

Jest (`bukti/KP-T7/jest_*`): suite baru 5/5 lulus, 5/5 gagal di `src` lama. Seluruh suite: HEAD 71 lulus / 35 gagal
dimuat / 507 uji → KP-T7 72 / 35 / 512 (daftar 35 suite identik; semuanya `@radix-ui/primitive/is-development` tidak
termuat lokal). Dengan tiruan pemilih (pola PK-13): `phase3Settings` lulus di keduanya; `roleGateSweep2` 17/18 di
keduanya (1 gagal kasbon, tidak terkait — sama di HEAD). `test_fe03_access_catalog.py` 6/6 sesudah fixture
dibangkitkan. ESLint berkas layar yang berubah: bersih.

## Penjaga

| Penjaga | Sebelum (`69cc4e3`) | Sesudah |
|---|---|---|
| `hitung_penjaga.sh` (16) | auth 28 · ui_standard 23 · i18n 111 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · lainnya 0 | **sama persis** (`verify_approval_queues` bergantung data, diabaikan) |
| `verify_role_gate_ui.py` | PASS 33 cek | PASS 33 cek |
| `audit_config_wiring.py --strict` (salinan berjalur `$W`) | keluar 0, 121 kunci, 0 masalah | keluar 0, sama |
| `config_health` (pemindai KF-T3) | 383 kunci, 0 rusak | 402 kunci, 0 rusak (19 kunci baru OK) |
| Statik lain (notification_audience, role_label, atomic_claim, derived_fields, detail_modal, picker_portal, escape_layers, view_aliases, desk_targets, line_scope, status_history, codebase_map) | — | pelanggaran sama; hanya jumlah cek naik karena berkas baru |

Rincian: `bukti/KP-T7/penjaga_statik_sebelum_sesudah.log`, `audit_config_wiring_sebelum_sesudah.log`,
`config_health_sebelum_sesudah.log`. Penjaga runtime (bagian runtime `verify_numeric_bounds`, `verify_concurrency`,
dll.) tidak dijalankan (instruksi).

## Menyimpang dari blueprint

1. **Label ≤ 45 karakter** (`02` §2.1 menang; spesifikasi tidak menulis "menyimpang"): tujuh label dipendekkan — lihat
   Usulan koreksi 1.
2. **Rujukan pemakai = fungsi yang benar-benar membaca** (KF-T3: badan fungsi wajib menyebut kunci):
   `notif.content_on_time_grace_minutes` → `marketing_ext.py:_toleransi_per_pt` (`_kpi` tetap fungsi murni, menerima
   peta toleransi); `rnd.design_due_soon_days` → `design_request_service.py:summary` (`due_soon` murni, `days` dari
   pemanggil); `approval.reminder_max_listed` → `_ringkas` (dijadikan async ber-PT). `notif.max_alerts_per_run`
   dipakai **delapan** fungsi (spesifikasi menyebut tiga; konstanta yang sama juga dipakai hutang, anggaran, perintah
   kerja, barang PO datang, pendingan siap) — semuanya dialihkan dan dicantumkan.
3. **Pengingat lintas PT** (`reminder_policy.LINTAS_PT`): piutang lewat tempo dan penyusutan aset hari ini satu
   notifikasi tanpa PT (umur piutang seluruh pelanggan; satu periode untuk semua aset) → hanya baris grup yang berlaku;
   baris PT untuk keduanya diabaikan (ditulis di `help` kunci dan diuji U20). Menjadikannya per PT berarti mengubah
   bentuk notifikasinya (di luar U5).
4. Ambang yang dipakai **kueri** (tugas gudang, jendela barang PO, hari piutang, jarak tayang, label tertahan): kueri
   memakai batas terkecil/terlebar/gabungan grup + PT aktif, lalu tiap dokumen disaring dengan batas PT-nya (bawaan →
   kueri identik). Label tertahan: gudang yang batas PT-nya lebih besar dihitung ulang dengan batasnya sendiri.
5. Pemeriksa tambahan saat simpan: baris pengingat ganda ditolak ("Baris n: pengingat “…” sudah ada di baris m."),
   cara menentukan wajib salah satu dari dua, hari pengingat bilangan bulat −30…30 (disimpan terurut tanpa ganda;
   daftar kosong boleh = tidak ada pengingat), nomor PIC dinormalkan `62…`; nomor PIC tak sah 400.
6. `GET /api/scheduler/jobs`: butir ambang membawa `text` dan `group` (untuk tampilan & tautan), plus `recipient_key`;
   kolom Ambang juga menautkan kunci lama yang sudah menjadi ambang job (`approval.reminder_min_days`,
   `inventory.drift_alert_rupiah`, `saga.stuck_lock_minutes`, `rnd.sla_escalate_admin_days`,
   `antar_entitas.settlement_reminder_days`, `periode.unlock_window_hours`, `returns.supplier_reminder_days`,
   `interco_payment.reminder_days`, `contra_bon.reminder_days_before`) supaya kolom tidak menulis "—" untuk job yang
   ambangnya memang bisa diatur (L5/L6). Tautan **Ubah** membuka kunci di layar kelompoknya (kunci di luar kelompok
   `notifikasi` dibuka di layar domainnya).
7. Deskripsi enam job dan label "Piutang Mendekati Jatuh Tempo" (dulu "(H-3/H-1/H/H+1)") tidak lagi menulis angka tetap
   — angkanya kini pengaturan (L6); istilah lain → KP-T9.
8. `access_modules.VIEW_RESOURCE_OVERRIDES` + `scheduler` untuk tab notifikasi, keuangan, persetujuan, R&D (aturan KF-T1
   U14: tab terbuka bagi pemegang izin pengubah kunci kelompoknya) → fixture akses dibangkitkan ulang.
9. Editor baku diperluas sedikit (blok `KP-T7`): kolom bertipe `multi` (kotak centang) dan `options_source: "roles"`
   (peran kustom yang sedang terdaftar di layar ikut ditawarkan); daftar ber-`options` (peran siaran WhatsApp) =
   kotak centang; ringkasan daftar memakai label. Kolom kunci peta rantai eskalasi tetap isian teks id peran (editor peta
   baku) — lihat Yang perlu direview.
10. Uji U5 di modul sendiri (`test_KPT7_setara.py`) dengan acuan JSON (pola PR-T4 U13); dua pembaca ditiru.
11. Nomor PIC per PT **menggantikan** nomor PIC umum untuk notifikasi PT itu (teks bantuan spesifikasi: "Kosong =
    memakai nomor PIC di pengaturan WhatsApp"); Ringkasan Harian (`digest_service`) tetap memakai nomor PIC umum.

## Usulan koreksi blueprint (teks pengganti persis)

1. Tabel Pengaturan, kolom `label`: `notif.ap_due_soon_days` "Ingatkan hutang jatuh tempo dalam (hari)";
   `notif.wo_released_stale_days` "Perintah kerja dirilis tertunda setelah"; `notif.turn_stale_days` "Jangan
   ingatkan giliran bila dokumen diam"; `inventory.drift_critical_multiplier` "Selisih persediaan kritis pada
   (× ambang)"; `approval.reminder_max_listed` "Dokumen yang disebut di pengingat persetujuan";
   `rnd.design_due_soon_days` "Tenggat permintaan desain dekat dalam"; `notif.wa_broadcast_roles` "Peran penerima
   WhatsApp pemberitahuan umum".
2. Tabel Pengaturan, kolom `consumers`: `notif.content_on_time_grace_minutes` → `services/marketing_ext.py:_toleransi_per_pt`;
   `rnd.design_due_soon_days` → `services/design_request_service.py:summary`; `notif.max_alerts_per_run` →
   "`services/alert_service.py:job_ar_overdue`, `:job_ap_due`, `:job_budget_alert`, `:job_production_stalled`,
   `services/alert_ops_service.py:job_po_arrival`, `:job_backorder_ready`, `:job_ar_due_soon`,
   `services/escalation_service.py:job_escalation_scan`".
3. "Keadaan sekarang" butir 3: "Dua belas job berbasis menit" (KF-T3 menambah `config_apply_due`).
4. Bagian Pengaturan, sesudah "Nilai PT menimpa tabel utuh; …": "Piutang jatuh tempo (`ar_overdue`) dan penyusutan
   (`depreciation_due`) adalah pengingat lintas PT (notifikasi tanpa PT) — hanya baris grup yang berlaku."

## Asumsi

- `ASUMSI` spesifikasi dipakai apa adanya: dua job gerbang RFID dikunci (H7); izin semua kunci `scheduler.configure`;
  toleransi tepat waktu, anggaran kampanye, tenggat desain termasuk lingkup; zona waktu & daftar job bukan pengaturan.
- Pilihan **Izin** di tabel penerima = semua pasangan sumber daya × aksi di katalog modul (449 pilihan berlabel
  "<sumber daya> — <aksi>"), diturunkan dari `access_modules` saat registry dimuat.
- Ringkasan penerima/ambang di `GET /scheduler/jobs` dihitung untuk PT aktif (`X-Entity-Id`); "Semua PT" = grup.
- Job `config_apply_due` (KF-T3) dan job menit lain selain dua job gerbang kini bisa diubah 1–1440 menit (spesifikasi).

## Titik henti

- **H7**: `rfid_reader_health_watch` dan `rfid_gate_txn_retry` hanya ditandai terkunci (`LOCKED_JOBS` di blok KP-T7;
  entri job RFID dan perilakunya tidak diubah; on/off tetap seperti dulu). `rfid_evidence_retention` (harian) tidak
  disentuh. **Perlu dilihat reviewer**: `printer_stuck_watch` (antrean cetak label QR/RFID, koleksi
  `rfid_print_jobs`/`rfid_devices`) bukan gerbang/middleware, tetapi menyentuh koleksi ber-awalan rfid — ambang
  30 menitnya kini pengaturan per PT (spesifikasi), bawaan identik, antrean/printer tidak diubah. `middleware/`,
  `gate_evaluator`, `rfid_ingest_service`, `rfid_service` tidak disentuh.
- **H3**: skrip `scripts/migrate_kpt7_jadwal.py` tidak dijalankan terhadap database `backend/.env` (mode lapor pun
  tidak); hanya di lingkungan B (U4). Job penjadwal tidak dijalankan terhadap database `backend/.env`. Kueri cek
  lingkungan A (hanya baca): `db.system_settings.find({scope: "alerts"}, {jobs: 1})` lalu periksa `interval_hours`
  pada job bersatuan menit: `reservation_expiry`, `content_reminder`, `saga_lock_watch`, `printer_stuck_watch`,
  `rfid_reader_health_watch`, `rfid_gate_txn_retry`, `turn_scan`, `ai_fact_sync`, `ai_schedule_dispatch`,
  `interco_payment_reminder`, `export_schedule_dispatch`, `config_apply_due` (atau jalankan skrip mode lapor — keputusan
  pemilik).

## Persinggungan dengan unit lain

- KF-T4 (berjalan; bahasa & editor Pusat Pengaturan): `SettingTableEditor.jsx` (fungsi `colOptions`, `MultiChoice`,
  satu cabang `multi`, `enum` memakai `colOptions`), `SettingEditor.jsx` (satu cabang daftar berpilihan),
  `configApi.js` (`formatValue` daftar); katalog `config_catalog_core.py` (satu blok sesudah `notif.po_stage_stuck_days`).
  `config_registry.py` **tidak** disentuh.
- PR-T5 (katalog izin): `access_modules.py` satu blok `KP-T7` sesudah blok KF-T2; pilihan izin tabel penerima dibaca
  dari katalog saat dimuat (ikut berubah bila katalog berubah).
- KF-T3: job `config_apply_due` bersatuan menit (kini bisa diubah 1–1440); `ensure_due_applied` tidak disentuh;
  ambang tahap PO macet tetap milik KF-T3. KP-T1: job `entity_tax_status_due` (harian) tidak disentuh.
- KF-T7: blokir kredit, masa reservasi (3 hari di deskripsi `reservation_expiry`), ambang stok tidak disentuh.
- PR-T4: `plan_escalations` tetap memakai `notify_addresses` untuk peran di luar rantai; rantainya kini pengaturan.
- PK-21: tidak bersinggungan.

## Hambatan lingkungan

- Tanpa peramban: U14 (uji jalan) belum dijalankan. Lapis A dan gate dijalankan saat penggabungan.
- Jest lokal: 35 suite lama gagal dimuat (`@radix-ui`), sama di HEAD dan KP-T7; suite baru meniru pemilih.
- `/app` menunjuk repo utama: `audit_config_wiring.py` dan `config_health` dijalankan lewat salinan berjalur/pemuat
  (berkas penjaga tidak diubah).

## Penggabungan

Digabung di atas `3c459d9` (sesudah PR-T5 dan PK-21). Satu konflik di glosarium (baris PK-21 dan KP-T7 di tabel yang sama —
keduanya dipertahankan); `access_modules.py`, `marketing_cost_service.py` (penolak batal kas PK-21 + pengingat KP-T7),
`test_KFT1_izin_pengaturan.py`, `ENTITY_REGISTRY.md`, `PRD.md` tergabung otomatis; fixture akses dan `CODEBASE_MAP.md`
dibangkitkan ulang. `tests_mem` **526 → 545 lulus** / 2 / 3; jest seluruhnya 514/514 (35 suite gagal dimuat karena
`@radix-ui`, kendala lingkungan).

Perbaikan saat penggabungan: lapis A memanggil `scripts/migrate_kpt7_jadwal.py` dan skrip itu gagal dimuat — `ImportError`
impor melingkar (`services/reminder_policy.py` mengimpor `config_registry` di tingkat modul, sementara
`config_catalog_core.py` mengimpor `reminder_policy` saat registry dimuat; di aplikasi urutannya kebetulan aman, di skrip
tidak). `reminder_policy` kini mengimpor registry secara malas (`_registry()`); uji KP-T7 19/19, lapis A 5/5. Keluaran mode
lapor di data acuan (`bukti/KP-T7/skrip_migrasi_mode_lapor_data_acuan.log`): 0 job tersimpan, 0 sisa selang jam.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `0a91095`), sesudah `restore_demo` (data acuan; tiga skrip seed yang
sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`). Satu jalan gate untuk dua unit
yang digabung berturut-turut (PK-21 `3c459d9`, KP-T7 `0a91095`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| `gate.sh --ci` | 41 FAIL | 43 | 0 | 2 |

Hitungan penjaga statik berhitung sama dengan sebelum kedua unit; `verify_role_gate_ui`, `verify_permission_checked`
PASS; `audit_config_wiring --strict` bersih.


## Yang perlu direview

- Menyimpang 3 (pengingat lintas PT hanya grup) dan 6 (kunci lama ikut ditautkan di kolom Ambang).
- `printer_stuck_watch` di bawah H7 (lihat Titik henti).
- Kolom kunci editor peta rantai eskalasi masih isian id peran (editor peta baku tidak punya pemilih kunci) — kandidat
  KF-T4/KP-T9.
- `GET /api/scheduler/jobs` membaca ±60 pengaturan per permintaan (belum diukur di MongoDB asli).
