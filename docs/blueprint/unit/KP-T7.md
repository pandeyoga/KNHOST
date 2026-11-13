# KP-T7 — Pengingat dan penjadwal yang bisa diatur: selang menit, penerima, dan ambang per PT

| | |
|---|---|
| Gelombang | Jalur konfigurasi perusahaan (U) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | KF-T1 |
| Menutup temuan | KP-09, KP-20, KP-21 |
| Keputusan | K-47 (wewenang dan alamat dari izin, bukan nama peran); `00` §4.1 |
| Standar | §2.1, §2.2, §2.4, §3.1 (Z1, Z2, Z6), §4 (L1, L5, L6), §6 |
| Lingkungan uji | B |

## Tujuan

Selang job berbasis menit benar-benar bisa diubah. Untuk tiap pengingat terjadwal, pemilik bisa menentukan per PT
siapa penerimanya (peran yang dipilih atau pemegang sebuah izin) dan berapa ambangnya. Semua nilai awal sama dengan
yang ditulis di kode hari ini, sehingga tidak ada pengingat yang berubah saat dipasang.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Skema simpan jadwal hanya mengenal `hour`, `minute`, `interval_hours` | `backend/schemas_scheduler.py:11` (`JobConfig`) |
| 2 | Layar mengirim `interval_hours` untuk semua job non-harian dan menampilkan satuan "jam" | `frontend/src/features/admin/scheduler/SchedulerParts.jsx:77` (`ScheduleEditor`) |
| 3 | Pemicu memilih `interval_minutes` lebih dulu; nilai itu selalu ada dari bawaan job, sehingga `interval_hours` yang disimpan untuk job berbasis menit tidak pernah dipakai. Sebelas job berbasis menit | `backend/services/scheduler_service.py:446` (`_apply_jobs`); `backend/services/scheduler_service.py:296` (`job_defaults`); `backend/services/scheduler_service.py:110` (`reservation_expiry`) |
| 4 | Ambang pengingat ditulis sebagai konstanta: hutang jatuh tempo ≤ 7 hari; perintah kerja dirilis 3 hari, draf 7 hari; tugas gudang 2 hari; maksimum 40 peringatan per jalan | `backend/services/alert_service.py:25` (`AP_DUE_SOON_DAYS`); `backend/services/alert_service.py:29` (`MAX_ALERTS_PER_JOB`) |
| 5 | Hari pengingat piutang H-3, H-1, H, H+1 dan jendela "barang PO datang" 24 jam ditulis mati | `backend/services/alert_ops_service.py:54` (`AR_DUE_SOON_OFFSETS`); `backend/services/alert_ops_service.py:52` (`PO_ARRIVAL_LOOKBACK_HOURS`) |
| 6 | Penerima ditulis sebagai satu nama peran: "manager" untuk piutang lewat tempo, hutang, penyusutan, anggaran; "warehouse" untuk perintah kerja dan tugas gudang; "manager" dan "warehouse" untuk barang PO datang; "manager" untuk pendingan siap | `backend/services/alert_service.py:85` (`recipient_role`); `backend/services/alert_service.py:172` (`recipient_role`); `backend/services/alert_service.py:277` (`recipient_role`); `backend/services/alert_ops_service.py:151` (`recipient_role`); `backend/services/alert_ops_service.py:247` (`recipient_role`) |
| 7 | Rantai eskalasi (sales/gudang → manager → admin) dan peran penerima siaran WhatsApp ditulis mati | `backend/services/escalation_service.py:36` (`ESCALATION_CHAIN`); `backend/services/wa_alert_service.py:31` (`BROADCAST_ROLES`) |
| 8 | Nilai lain di jalur pengingat yang ditulis mati: dokumen diam > 7 hari tidak diingatkan lagi; 3 dokumen disebut di pengingat persetujuan; tenggat desain dekat 3 hari; jendela tayang konten 60 menit dan toleransi tepat waktu 60 menit; anggaran kampanye "mendekati" 80%; label tertahan 30 menit; selisih persediaan "kritis" 10× ambang | `backend/services/turn_notification_service.py:80` (`STALE_DAYS`); `backend/services/approval_reminder.py:40` (`MAX_DISEBUT`); `backend/services/design_request_service.py:688` (`DUE_SOON_DAYS`); `backend/services/marketing_service.py:37` (`REMINDER_WINDOW_MIN`); `backend/services/marketing_ext.py:20` (`ON_TIME_GRACE_MIN`); `backend/services/marketing_cost_service.py:261` (`NEAR_PCT`); `backend/services/printer_stuck_watch.py:13` (`STUCK_MINUTES`); `backend/services/inventory_drift_watch.py:40` (`KRITIS`) |
| 9 | Jadwal, WhatsApp (termasuk satu nomor PIC), dan eskalasi disimpan di satu dokumen `system_settings` ber-`scope` `alerts` — berlaku untuk seluruh grup | `backend/services/wa_alert_service.py:76` (`raw_settings`); `backend/routers/scheduler.py:89` (`update_settings`) |
| 10 | Kelompok registry "Notifikasi & Pemberitahuan" hanya memuat dua kunci | `backend/config_catalog_core.py:943` (`notif.low_stock_division`); `backend/config_catalog_core.py:956` (`notif.po_stage_stuck_days`) |

Yang sudah ada dan dipakai ulang: pengalamatan per orang menurut izin, peran, atau divisi —
`backend/services/notification_service.py:25` (`create_addressed`); pengingat piutang mendekati jatuh tempo sudah
beralamat izin — `backend/services/alert_ops_service.py:46` (`_AR_TEAM_PERMISSION`).

## Perubahan

### Data

Tidak ada koleksi baru. `system_settings{scope: "alerts"}.jobs.<id>` boleh memuat `interval_minutes`. Skrip
`scripts/migrate_kpt7_jadwal.py` (hanya-lapor sebagai bawaan; data nyata — H3) melaporkan dan, pada mode tulis,
membuang `interval_hours` yang tersimpan pada job berbasis menit (nilai itu memang tidak pernah dipakai, jadi jadwal
tidak berubah).

### Server

**Selang menit.** `JobConfig` mendapat `interval_minutes: Optional[int]` (1–1440). Tiap entri `JOBS` berbasis selang
dianggap bersatuan **menit** bila bawaannya `interval_minutes`, selain itu **jam**. `PUT /api/scheduler/settings`
(izin `scheduler.configure`, tidak berubah):

| Keadaan | Hasil |
|---|---|
| Job bersatuan menit dikirimi `interval_minutes` | Disimpan; `reschedule()` memakai nilai baru |
| Job bersatuan menit dikirimi `interval_hours` | 400 "Jadwal “{label}” diatur dalam menit." |
| Job bersatuan jam dikirimi `interval_minutes` | 400 "Jadwal “{label}” diatur dalam jam." |
| Job harian dikirimi selang | 400 "Jadwal “{label}” diatur dengan jam dan menit harian." |
| Job ber-`locked` (`rfid_reader_health_watch`, `rfid_gate_txn_retry`) dikirimi selang | 400 "Jadwal “{label}” tidak bisa diubah dari layar." |

`GET /api/scheduler/jobs` menambah per job: `interval_unit` (`"menit"` · `"jam"` · `""`), `interval_value` (nilai yang
**dipakai pemicu**), `locked`, `recipients` (ringkasan label penerima efektif untuk PT aktif), dan `thresholds`
(`[{key, label, value, unit}]`).

**Penerima.** Berkas baru `backend/services/reminder_policy.py`:

| Fungsi | Perilaku |
|---|---|
| `async def recipients_for(reminder_id, entity_id) -> dict` | Baris `{mode, roles, permission}` untuk pengingat itu: dari nilai PT, lalu nilai grup, lalu bawaan |
| `async def notify(reminder_id, entity_id, **kw) -> list` | `mode = "peran"` dengan **satu** peran → `create_notification(recipient_role=<peran>, …)` persis seperti hari ini. `mode = "peran"` dengan beberapa peran → `create_addressed(roles=…)`. `mode = "izin"` → `create_addressed(permission=(modul, aksi))`. Notifikasi untuk pemegang akun (per orang) tidak diubah |
| `async def threshold(key, entity_id)` | `value_of(key, {"entity_id": entity_id})`; cadangan saat galat = bawaan registry (`02` §2.2) |

Sembilan titik pada butir 6 memanggil `reminder_policy.notify`; konstanta pada butir 4, 5, 7, 8 diganti
`reminder_policy.threshold` (dibaca per PT dokumen yang sedang diperiksa, disimpan sementara per PT dalam satu jalan).

### Pengaturan

Semua kunci: `group="notifikasi"` kecuali disebut; `permission=("scheduler", "configure")`; `risk="low"`;
`scopes=("global", "entity")` kecuali disebut. Bawaan = nilai di kode hari ini.

| `key` | `type` · bawaan · batas · satuan | `label` | `help` → `impact` (contoh) | `consumers` |
|---|---|---|---|---|
| `notif.ap_due_soon_days` | `duration` · 7 · 0–90 · hari | "Ingatkan hutang jatuh tempo sejak (hari sebelumnya)" | Tagihan pemasok yang jatuh tempo dalam sekian hari atau sudah lewat diingatkan. 0 = hanya yang sudah lewat → makin besar makin awal diingatkan (7 → tagihan jatuh tempo 5 hari lagi ikut) | `services/alert_service.py:job_ap_due` |
| `notif.wo_released_stale_days` | `duration` · 3 · 1–90 · hari | "Perintah kerja dirilis dianggap tertunda setelah" | Umur perintah kerja berstatus dirilis yang belum selesai → menentukan kapan gudang diingatkan (3 → dirilis 4 hari lalu ikut) | `services/alert_service.py:job_production_stalled` |
| `notif.wo_draft_stale_days` | `duration` · 7 · 1–180 · hari | "Perintah kerja draf dianggap tertunda setelah" | Umur draf yang belum dirilis → sama (7 → draf 8 hari ikut) | `services/alert_service.py:job_production_stalled` |
| `notif.warehouse_task_stale_days` | `duration` · 2 · 1–60 · hari | "Tugas gudang dianggap tertunda setelah" | Umur tugas masuk/keluar yang masih terbuka → kapan diringkas ke gudang (2 → tugas 3 hari ikut) | `services/alert_service.py:job_ops_stalled` |
| `notif.ar_due_soon_offsets` | `list` · [-3, -1, 0, 1] · tiap butir −30…30 · hari | "Hari pengingat piutang terhadap jatuh tempo" | Angka negatif = sebelum jatuh tempo, 0 = hari jatuh tempo, positif = sesudahnya → menentukan hari pengingat dikirim ([-7, 0] → H-7 dan hari H) | `services/alert_ops_service.py:job_ar_due_soon` |
| `notif.po_arrival_lookback_hours` | `int` · 24 · 1–168 · jam | "Barang PO dianggap baru datang selama" | Penerimaan yang selesai dalam jendela ini diberitakan → jendela pendek mencegah berita lama terulang (24) | `services/alert_ops_service.py:job_po_arrival` |
| `notif.max_alerts_per_run` | `int` · 40 · 1–500 · peringatan · hanya `global` | "Paling banyak peringatan per sekali jalan" | Pagar supaya satu pengingat tidak membanjiri kotak masuk → sisanya menunggu jalan berikutnya (40) | `services/alert_service.py:job_ar_overdue`, `services/alert_ops_service.py:job_ar_due_soon`, `services/escalation_service.py:job_escalation_scan` |
| `notif.turn_stale_days` | `duration` · 7 · 1–90 · hari | "Berhenti mengingatkan giliran setelah dokumen diam" | Dokumen yang tidak bergerak lebih dari ini tidak diingatkan ulang (7) | `services/turn_notification_service.py:scan` |
| `notif.content_reminder_window_minutes` | `int` · 60 · 5–1440 · menit | "Ingatkan tayang konten sebelum (menit)" | Jarak sebelum jadwal tayang ketika PIC diingatkan (60) | `services/marketing_service.py:job_content_reminder` |
| `notif.content_on_time_grace_minutes` | `int` · 60 · 0–1440 · menit | "Toleransi tayang tepat waktu (menit)" | Konten yang tayang dalam toleransi ini dihitung tepat waktu. 0 = tanpa toleransi (60) | `services/marketing_ext.py:_kpi` |
| `notif.campaign_budget_near_pct` | `pct` · 80 · 1–100 · % | "Anggaran kampanye dianggap hampir habis pada" | Persen realisasi yang memunculkan peringatan (80 → terpakai Rp8 jt dari Rp10 jt) | `services/marketing_cost_service.py:budget_summary` |
| `notif.printer_stuck_minutes` | `int` · 30 · 5–1440 · menit | "Label dianggap tertahan setelah (menit)" | Lama antrean cetak tanpa printer menyala sebelum diberitakan (30) | `services/printer_stuck_watch.py:scan` |
| `inventory.drift_critical_multiplier` | `int` · 10 · 2–1000 · kali · kelompok `keuangan-dasar` | "Selisih persediaan dianggap kritis pada (× ambang)" | Kelipatan `inventory.drift_alert_rupiah` yang menaikkan peringatan menjadi kritis (10 × Rp1.000 = Rp10.000) | `services/inventory_drift_watch.py:scan` |
| `approval.reminder_max_listed` | `int` · 3 · 1–20 · dokumen · kelompok `persetujuan` | "Jumlah dokumen yang disebut di pengingat persetujuan" | Dokumen terlama yang ditulis namanya di pengingat harian (3) | `services/approval_reminder.py:_ringkas` |
| `rnd.design_due_soon_days` | `duration` · 3 · 1–30 · hari · kelompok `rnd` | "Tenggat permintaan desain dianggap dekat dalam" | Batas "tenggat dekat" di ringkasan desainer (3) | `services/design_request_service.py:due_soon` |
| `notif.reminder_recipients` | `table` (`row_shape="list"`) · bawaan di bawah · `risk="medium"` | "Penerima tiap pengingat" | Siapa yang menerima tiap pengingat terjadwal: peran yang dipilih, atau semua pemegang sebuah izin di PT itu → mengubah kotak masuk siapa yang terisi (hutang jatuh tempo → pemegang izin bayar tagihan) | `services/reminder_policy.py:recipients_for` |
| `notif.escalation_chain` | `table` (`row_shape="map"`) · `{"sales": "manager", "warehouse": "manager", "manager": "admin", "all": "admin", "": "admin"}` · hanya `global` · `risk="medium"` | "Naik ke siapa bila peringatan tidak ditindak" | Peran penerima → peran di atasnya (gudang → manajer → admin) | `services/escalation_service.py:job_escalation_scan` |
| `notif.wa_broadcast_roles` | `list` · ["admin", "manager"] · hanya `global` | "Peran penerima WhatsApp untuk pemberitahuan umum" | Pemberitahuan beralamat "semua" hanya dikirim WhatsApp ke peran ini | `services/wa_alert_service.py:resolve_recipients` |
| `notif.wa_pic_number` | `text` · "" | "Nomor WhatsApp PIC pengingat PT ini" | Kosong = memakai nomor PIC di pengaturan WhatsApp → PT yang mengisi menerima pengingatnya di nomor sendiri (0812…) | `services/wa_alert_service.py:resolve_recipients` |

Kolom `notif.reminder_recipients`: `reminder` (pilihan id di bawah), `mode` (`peran` · `izin`), `roles` (daftar id
peran), `permission` (teks `modul.aksi`). Bawaan (= hari ini):

| `reminder` | `mode` | isi |
|---|---|---|
| `ar_overdue`, `ap_due`, `depreciation_due`, `budget_alert`, `po_arrival`, `backorder_ready` | `peran` | `["manager"]` |
| `production_stalled`, `ops_stalled`, `po_arrival_gudang` | `peran` | `["warehouse"]` |
| `ar_due_soon` | `izin` | `ar_receipt.create` |

Nilai PT menimpa tabel utuh; pengingat yang tidak ada di tabel PT memakai baris grup, lalu bawaan. Pemeriksaan saat
simpan (400): "Pengingat “{nilai}” tidak dikenal."; "Peran “{nilai}” tidak ada."; "Izin “{nilai}” tidak ada."; "Baris
{n}: pilih paling sedikit satu peran." Rantai eskalasi dan peran siaran diperiksa dengan pesan peran yang sama.

Uji putaran `t1_config.py` wajib lulus untuk tiap kunci di atas (`02` §2.4).

### Izin dan peran

Tidak ada pasangan baru. Kunci di atas dijaga `scheduler.configure` (bawaan hanya Admin — sama dengan hari ini).

### Layar

Tempat: Pengaturan › Notifikasi & Penjadwal › Penjadwal & Notifikasi (`SchedulerParts.jsx`) dan tab Penerima
Notifikasi (kelompok registry `notifikasi`).

- `ScheduleEditor`: job bersatuan menit menampilkan "tiap [n] menit" (1–1440) dan mengirim `interval_minutes`; job
  bersatuan jam tetap "tiap [n] jam". Nilai awal isian = `interval_value` dari server. Job ber-`locked` tampil
  hanya-baca dengan keterangan "Jadwal teknis — tidak diubah dari layar."
- Daftar job menambah dua kolom: **Penerima** (mis. "Manajer", atau "Pemegang akses Kas & Bank") dan **Ambang**
  (mis. "7 hari"), masing-masing dengan tautan **Ubah** yang membuka kunci terkait di tab Penerima Notifikasi untuk PT
  aktif. Job tanpa penerima/ambang yang bisa diatur menampilkan "—".
- Tab Penerima Notifikasi menampilkan kunci baru lewat editor baku (tabel penerima memakai editor baris: kolom
  **Pengingat**, **Cara menentukan** ("Peran yang dipilih" / "Semua pemegang izin"), **Peran**, **Izin**).
- Kata "Job" di judul kolom diganti "Pengingat" hanya pada kolom baru; penggantian istilah lain → KP-T9.

## Uji penerimaan

Persiapan bersama: seed lingkungan B; akun admin; penjadwal dinyalakan dengan pemicu tiruan (fungsi `_apply_jobs`
diperiksa lewat daftar pemicu, bukan menunggu waktu).

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `PUT /api/scheduler/settings` `{"jobs": {"reservation_expiry": {"interval_minutes": 120}}}`; `GET /api/scheduler/jobs` | 200; `interval_unit: "menit"`, `interval_value: 120`, `schedule_label` "Setiap 120 menit"; pemicu job itu berselang 120 menit |
| U2 | B | — | `PUT …` `{"jobs": {"reservation_expiry": {"interval_hours": 2}}}` | 400 "Jadwal “Kedaluwarsa Reservasi Pesanan” diatur dalam menit."; pemicu tetap 30 menit |
| U3 | B | — | `PUT …` `{"jobs": {"ops_stalled": {"interval_minutes": 10}}}` dan `{"jobs": {"rfid_gate_txn_retry": {"interval_minutes": 5}}}` | 400 "…diatur dalam jam."; 400 "…tidak bisa diubah dari layar." |
| U4 | B | Dokumen `alerts` berisi `jobs.turn_scan.interval_hours: 4` (sisa lama) | Jalankan migrasi mode tulis; baca pemicu sebelum dan sesudah | Selang pemicu 5 menit sebelum dan sesudah; field `interval_hours` hilang |
| U5 | B | Bawaan | **Setara:** jalankan `job_ap_due`, `job_ar_overdue`, `job_depreciation_due`, `job_budget_alert`, `job_production_stalled`, `job_ops_stalled`, `job_po_arrival`, `job_backorder_ready`, `job_ar_due_soon` pada fixture yang sama sebelum dan sesudah unit | Himpunan (`notif_type`, `ref`, `recipient_role`, `recipient_user`, `entity_id`) notifikasi yang lahir sama persis |
| U6 | B | Tagihan pemasok `posted` `ent_ksc` dan `ent_kanda`, keduanya jatuh tempo 10 hari lagi | Tulis lapisan PT `notif.ap_due_soon_days = 14` untuk `ent_kanda`; jalankan `job_ap_due` | Notifikasi lahir untuk tagihan `ent_kanda` saja (10 ≤ 14; untuk `ent_ksc` 10 > 7) |
| U7 | B | Peran **Tanpa Acuan** berizin `vendor_bill.pay`, satu akun aktif bertugas di `ent_kanda`; tagihan `ent_kanda` jatuh tempo 2 hari lagi | Tulis lapisan PT `notif.reminder_recipients` untuk `ent_kanda`: `ap_due` → `izin` `vendor_bill.pay`; jalankan `job_ap_due` | Notifikasi `ent_kanda` ber-`recipient_user` = akun itu dan pemegang izin lain di PT itu; tidak ada yang ber-`recipient_role: "manager"`. Tagihan `ent_ksc` tetap ke `recipient_role: "manager"` |
| U8 | B | — | `PUT /api/config/values` `notif.reminder_recipients` dengan baris `{reminder: "ap_due", mode: "peran", roles: ["direktur"]}` | 400 "Peran “direktur” tidak ada." |
| U9 | B | — | `PUT /api/config/values` `notif.ar_due_soon_offsets = [-7, 0]`; jalankan `job_ar_due_soon` pada pesanan jatuh tempo 7 hari lagi dan 3 hari lagi | Pengingat lahir untuk yang 7 hari; tidak untuk yang 3 hari |
| U10 | B | `notif.escalation_chain` diubah: `"warehouse": "warehouse_admin"`; satu peringatan gudang belum dibaca melewati batas | Jalankan `job_escalation_scan` | Peringatan naik ke `warehouse_admin`, bukan `manager` |
| U11 | B | Pengaturan WhatsApp global `pic_number` terisi; lapisan PT `notif.wa_pic_number` untuk `ent_kanda` terisi nomor lain | `wa_alert_service.resolve_recipients` untuk notifikasi `ent_kanda` dan `ent_ksc` | `ent_kanda` memuat nomor PT; `ent_ksc` memuat nomor global |
| U12 | B | Peran **Manajer Kosong**; peran **Tanpa Acuan** berizin `scheduler.configure` | Keduanya menulis `notif.ap_due_soon_days` di lapisan PT | 403; 200 |
| U13 | B | — | `t1_config.py` dijalankan untuk 19 kunci baru | Semua lulus (tulis grup → terbaca; lapisan PT → hanya PT itu; nilai tak sah → 400) |
| U14 | layar (uji jalan) | Login admin | Buka Penjadwal & Notifikasi; ubah "Kedaluwarsa Reservasi Pesanan" menjadi 45 menit | Isian bersatuan menit; setelah simpan label "Setiap 45 menit"; kolom Penerima dan Ambang terisi untuk "Hutang Supplier Jatuh Tempo (AP)" |

## Langkah kerja

1. `backend/tests_mem/test_KPT7_pengingat.py`: U1–U13; rekam keluaran U5 pada kode sebelum diubah sebagai acuan.
2. `interval_minutes` di skema, validasi satuan, `GET /scheduler/jobs`; migrasi sisa `interval_hours`.
3. Sembilan belas kunci di `config_catalog_core.py` (kelompok yang sudah ada); pemeriksa tabel penerima.
4. `reminder_policy.py`; alihkan sembilan titik penerima dan konstanta ambang; U5 harus tetap sama.
5. Rantai eskalasi, peran siaran, nomor PIC per PT.
6. Layar; `scripts/audit_config_wiring.py` tidak bertambah merah. Gate; laporan.

## Dokumen ikut berubah

`CODEBASE_MAP.md` (`services/reminder_policy.py`); `memory/PRD.md` (penerima dan ambang pengingat per PT).

## Di luar lingkup

- Alamat notifikasi **peristiwa** (bukan job terjadwal), termasuk permintaan restock, dan penerima sebagai sifat peran
  → PR-T4. Bila PR-T4 sudah menyediakan pembantu alamat, `reminder_policy.notify` memanggilnya.
- Jadwal, penyedia WhatsApp, dan eskalasi (hidup/mati, jam, kedalaman) per PT → tidak diminta (KP-21: cukup PIC dan
  penerima per PT). Zona waktu jadwal tetap WIB. Daftar 38 job tetap di kode.
- Menyatukan dua konfigurasi WhatsApp dan mengenkripsi tokennya → KP-T8.
- Nilai ditulis mati lain (blokir kredit, masa reservasi, ambang stok) → KF-T7. Selang job RFID → H7.
- Istilah "Job" dan susunan tab → KP-T9.

## Asumsi dan risiko

- `ASUMSI:` dua job gerbang RFID dikunci dari perubahan selang (H7); sembilan job berbasis menit lain boleh 1–1440
  menit.
- `ASUMSI:` izin pengubah semua kunci baru adalah `scheduler.configure`, karena itulah izin yang hari ini menjaga
  seluruh pengaturan penjadwal.
- `ASUMSI:` toleransi tepat waktu konten, ambang anggaran kampanye, dan tenggat desain (butir 8) termasuk lingkup
  karena tercantum di Lampiran A #39–42, walau dipakai layar ringkasan dan bukan hanya pengingat.
- `ASUMSI:` zona waktu (Lampiran A #35) dan daftar job (#36) bukan nilai yang perlu diatur; tidak dijadikan kunci.
- `RISIKO:` berpindah dari satu notifikasi beralamat peran ke notifikasi per orang mengubah siapa yang melihatnya
  (penugasan PT dihitung saat kirim, bukan saat baca). Karena itu bawaan satu peran tetap memakai jalur lama (U5);
  jalur per orang hanya dipakai setelah pemilik mengubah penerima. Membatalkan: kosongkan nilai
  `notif.reminder_recipients`; ambang kembali ke bawaan registry.
