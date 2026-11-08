# PREP-F — Printer label RFID Chainway CP30EN (persiapan tanpa perangkat)

**Tanggal:** 9 Nov 2026 · **Pelaksana:** Claude Code (implementer) · **Branch:** `worktree-agent-a2892ea26ac93bcfe`
(dasar `5f1e36e`, sudah digabung dari `main` lokal) · **Commit:** `5e7d56a` (kode + uji) → commit laporan ini · **Status:** dibangun & diuji tanpa perangkat — **belum ada
bukti CP30EN fisik.**
Acuan: [`KEPUTUSAN_GATE_RFID.md`](../KEPUTUSAN_GATE_RFID.md) §1 & §10 (CP30EN × 2 bisa bertambah, label 70 × 22 mm,
printer LAN ke PC gudang, EPC dianggap TIDAK unik, ±6.000 roll/hari, internet 50 Mbit/s, tanpa server lokal),
rencana `docs/development/gelombang-lanjutan-pasca-p05-2026-10-16/sources/rfid-plan/PRINTER_CP30EN_PLAN.md`
(RFID-11…15, RACC-21…30) dan spesifikasi Kubus `04_MODUL_PRINTER_CP30EN.md` / `05_KONTRAK_API_TARGET.md` §5.7.

## 1. Ringkasan
- **ERP:** lease **stabil** (polling ulang printer + instance connector pemilik lease → attempt SAMA, tanpa spool ulang,
  tanpa menaikkan percobaan), **perpanjang lease**, **start barrier per label**, **hasil PER LABEL** (tercetak+tertulis /
  gagal + alasan / tidak pasti) yang idempoten, **job parsial**, **antrean tindak lanjut** (operator berizin memutuskan
  dengan bukti), **pemulihan efek** bila status tersimpan tetapi efek tag/journey gagal (tanpa cetak ulang),
  **cetak ulang teks** (EPC tetap, tanpa tulis chip) vs **ganti tag** (EPC baru; EPC lama dipensiunkan & tak pernah
  dipakai ulang), **riwayat tag ↔ roll**, izin + alasan + jejak audit. Kontrak lama (`GET …/pending`, ACK tingkat
  job, tandai tercetak manual) tetap jalan.
- **Templat 70 × 22 mm** (203/300 dpi, offset, posisi inlay `^RS`, mode laporan encode per printer) dari SATU fungsi
  tata letak yang juga menghasilkan **pratinjau SVG** di UI.
- **Connector PC gudang** `middleware/printer-connector/` (Python 3.11, hanya pustaka standar, Windows; layanan via
  NSSM/Task Scheduler): satu worker terisolasi per printer, **ledger SQLite** (niat → start → kirim → hasil → lapor),
  TCP 9100, status printer (timeout = tidak pasti), heartbeat printer terpisah dari connector, offline tertahan,
  **pulih sesudah crash tanpa cetak ulang otomatis**, log berotasi, README bahasa Indonesia.
- **Simulator printer ZPL** (TCP) dengan gangguan: kertas habis, gagal tulis (VOID), baca balik salah, macet/timeout,
  putus di tengah job, balasan ganda, status bisu, kepala terbuka.
- **UI:** tab **Tag RFID → Antrean Printer** (per gedung): kesehatan connector ≠ printer, antrean job (saringan + unduh
  CSV), rincian job tiga dimensi (job · printer/klaim · verifikasi C72), **Perlu tindak lanjut** (+ unduh CSV),
  pratinjau label, profil & kalibrasi printer (admin), dan tombol **Ganti/Cetak** per tag aktif.

## 2. Berkas
| Berkas | Isi |
|---|---|
| `backend/services/rfid_label_template.py` (baru) | Profil printer (validasi), tata letak 70 × 22 mm (dot), render ZPL, sidik profil, pratinjau |
| `backend/services/rfid_print_service.py` | Item ber-ID & status, agregat job (CAS `state_seq`), efek per item idempoten + pemulihan, verifikasi hanya label terkonfirmasi, tindak lanjut, cetak ulang teks, ganti tag, riwayat tag, `allocate_epc` |
| `backend/services/rfid_printer_protocol.py` (baru) | Protokol perangkat `kn-printer-1`: klaim/redelivery, renew, start, results, status attempt, ACK lama, config, telemetri |
| `backend/services/rfid_ingest_service.py` | **Hanya bagian printer:** `pending_jobs_for_device` / `ack_job_printed` jadi pintu kompatibel ke protokol baru (gate/`ingest_into_session` tidak disentuh) |
| `backend/routers/rfid_printers.py` (baru) | Endpoint perangkat & pengguna PREP-F (disertakan dari `routers/rfid.py`, tanpa menyentuh `server.py`) |
| `backend/routers/rfid.py` | `GET /rfid/device-jobs/pending` (+`limit`, header `X-Connector-Instance`), mark-printed mencatat aktor, `printer-status` (+status printer/connector, job dicetak, butir tindak lanjut), include router baru |
| `backend/tests/test_prep_f_printer.py` (baru) | 22 uji ERP (HTTP nyata + Mongo; 3 uji tingkat layanan) |
| `backend/tests/test_prep_f_connector_e2e.py` (baru) | 5 uji ujung-ke-ujung ERP ↔ connector ↔ simulator |
| `middleware/printer-connector/**` (baru) | `kn_printer_connector/` (config, ledger, erp, printer, zpl_status, worker, service, CLI), `simulator/zpl_printer_sim.py`, `tests/` (17 uji + ERP tiruan), `install/` (NSSM, Task Scheduler), `config.example.json`, `README.md` |
| `frontend/src/features/rfid/PrinterQueuePanel.jsx`, `PrinterModals.jsx`, `LabelPreview.jsx`, `printerLabels.js` (baru) | Antrean printer, tindak lanjut, ganti/cetak ulang, profil + pratinjau |
| `frontend/src/features/rfid/RfidTagsView.jsx` | Tab "Antrean Printer" + tombol "Ganti/Cetak" per tag aktif (kait kecil) |
| `frontend/src/features/rfid/RfidPrintVerifyPanel.jsx` | Status job/label baru (parsial, tidak pasti, gagal), kolom status label, verifikasi job parsial |
| `frontend/src/components/PrinterStatusWidget.jsx` | Status printer (dari connector) di samping status connector + jumlah butir tindak lanjut |
| `frontend/src/features/__tests__/prepFPrinter.test.js` (baru) | 8 uji Jest |
| `scripts/guardrails/verify_auth_coverage.py` | 7 endpoint perangkat baru di `PUBLIC_ALLOWLIST` (auth = X-Device-Key) |
| `scripts/guardrails/verify_atomic_claim.py` | 3 endpoint multi-koleksi baru dicatat di `REVIEWED` (CAS + alasan) — angka "belum ditinjau" kembali 75 (= dasar) |

Koleksi baru: `rfid_tag_events` (riwayat tag ↔ roll, append-only, kunci idempoten). Field baru di
`rfid_print_jobs` (items[].item_id/status/label/payload_sha256/results/effects/resolution, `revision`, `counts`,
`review_open`, `attempts[]`, `effects_pending`, `verify_covered_items`, `state_seq`) dan `rfid_devices`
(`printer_profile`, `printer_connection`, `connector_health`, `printer_health`, `connector_conflict`).
Job lama tanpa `item_id` dilengkapi otomatis saat pertama disentuh (CAS, sekali).

## 3. Kontrak perangkat `kn-printer-1` (X-Device-Key; selaras API-14…19 Kubus, path di bawah `/api/rfid`)
| Endpoint | Perilaku |
|---|---|
| `GET /printer-agent/config` | profil printer ternormalisasi, sidik profil, balasan yang diharapkan (baca balik/encode), kebijakan (lease 300 dtk, renew 90 dtk sebelum habis, polling 5 dtk, telemetri 30 dtk, timeout hasil 45 dtk, tunggu jeda 600 dtk) |
| `POST /device-jobs/claim` (= `GET /device-jobs/pending` lama) | 1) **redelivery**: job yang lease-nya masih milik printer+instance ini → attempt sama, `redelivered:true`, tidak ada tulisan; 2) klaim baru: `queued|printing`, lease kosong/kedaluwarsa, **tanpa item `started`**, ZPL dirender dari SNAPSHOT item dengan profil printer pengklaim; reclaim tercatat di `attempts[]` (`kind: reclaim`, attempt sebelumnya). Instance lain dengan key sama → `conflicts[]`, perangkat ditandai `connector_conflict` |
| `POST …/{job}/attempts/{att}/renew` | perpanjang attempt yang SAMA; lease habis yang belum diklaim ulang masih bisa dipulihkan; diambil alih → 409 `LEASE_CONFLICT` |
| `POST …/{job}/attempts/{att}/start` | niat per item durable sebelum printer menerima payload; idempoten (`replay`); lease habis → 409 `LEASE_EXPIRED`; revisi job beda → 409 `VERSION_CONFLICT` |
| `POST …/{job}/attempts/{att}/results` | hasil per label `{result_event_id, item_id, print_status, encode_status, payload_sha256, evidence}`; ACK per item `accepted/duplicate/rejected` (`NOT_STARTED`, `ATTEMPT_MISMATCH`, `PAYLOAD_MISMATCH`, `IDEMPOTENCY_CONFLICT`, `SCHEMA_INVALID`); diterima dari attempt pemulai item **walau lease sudah habis** (bukti tidak hilang); baca balik EPC ≠ ERP → gagal; hasil yang bertentangan dengan status final → `conflict` (tidak dimundurkan); ulangan id sama = jalur pemulihan efek |
| `GET …/{job}/attempts/{att}` | status attempt (item, id hasil tercatat, lease, efek) untuk pemulihan connector |
| `POST /printer-agent/telemetry` | heartbeat connector (versi, PC, instance, ledger) + kesehatan PRINTER (siap/kertas habis/kepala terbuka/…) disimpan terpisah |
| `POST /device-jobs/{job}/ack` (lama) | status + semua item `confirmed` + efek tertunda disimpan atomik, lalu efek; ulangan ACK = pemulihan efek; job yang sedang dicetak per label → 409 |

Pengguna: `GET /printers/queue`, `GET /printers/follow-up` (wms:view) · `POST /print-jobs/{job}/items/{item}/resolve`
(wms:**approve**, catatan ≥ 5 huruf, bukti) · `POST /rolls/{roll}/replace-tag` (wms:**approve**) ·
`POST /rolls/{roll}/reprint-label` (wms:**print**) · `GET /rolls/{roll}/tag-history` · `GET|PUT /printers/{dev}/profile`
(lihat wms:view, ubah **admin**) · `POST /printers/label-preview` · `POST /printers/recover-effects` (wms:approve).
Semua mutasi pengguna diaudit (`rfid_print_item_resolved`, `rfid_tag_replaced`, `roll_label_text_reprint`,
`rfid_printer_profile_updated`, `rfid_print_effects_recovered`).

## 4. Status item & job
- Item: `pending → started → confirmed | failed | unknown` (+ `conflict`, `resolution`, `superseded_by`).
  `confirmed` = cetak terkonfirmasi **dan** chip terkonfirmasi (label RFID) / `not_applicable` (label teks/QR).
- Job: `queued` · `printing` · `printed` (semua terkonfirmasi) · `partial` (sebagian gagal, tanpa tinjauan terbuka) ·
  `failed` · `needs_review` (ada tidak pasti/bertentangan) · `verified` / `verified_with_issues` (verifikasi C72
  mencakup SEMUA label terkonfirmasi). **Tercetak ≠ terverifikasi** (RACC-24); verifikasi hanya mengharapkan EPC label
  terkonfirmasi, jadi 7 label baik bisa diverifikasi tanpa menunggu 3 label bermasalah.
- Efek label terkonfirmasi (tag `pending_print → active`, journey `tag_printed` hanya untuk roll yang tagnya masih
  tag item itu & belum lebih jauh, catatan cetak per roll, riwayat `activated`) dijalankan per item dengan penanda
  `effects: pending → done`. Gagal di tengah → `effects_pending` + `effects_error`; dipulihkan oleh ulangan hasil/ACK
  yang sama, sapuan otomatis saat printer menarik antrean, atau `POST /printers/recover-effects`. Semua langkah idempoten.
- Tindak lanjut: `unknown`, `conflict`, `failed` tanpa keputusan, dan `started` dengan lease habis (**klaim printer
  habis saat mencetak** — tidak dialihkan otomatis ke printer lain). Keputusan: sukses (label RFID **wajib** bukti baca
  EPC oleh handheld/reader sejak label mulai dicetak), gagal (EPC dipensiunkan), cetak ulang (EPC BARU), tutup.

## 5. Templat 70 × 22 mm
| | 203 dpi (8 dot/mm) | 300 dpi (11,8 dot/mm) |
|---|---|---|
| Media | 70 mm = 559,4 → **559** dot (`^PW559`), 22 mm = 175,8 → **176** dot (`^LL176`) | **827 × 260** dot |
| QR nomor roll (`^BQN,2,m`, isi = nomor roll, sama dengan label QR lama) | v1 (21 modul) × 6 = 126 dot ≈ 15,8 mm, x 8 · y 25 | × 9 = 189 dot ≈ 16 mm |
| Kolom teks | x 146, lebar 405 dot ≈ 50,7 mm | x 219, lebar 600 dot |
| Baris (font 0) | nama produk 26/22 (≤ 29 huruf) · SKU 22/18 · **Roll** 26/24 (≤ 27) · Lot \| panjang + satuan 22/18 · `EPC ..<8 hex terakhir>  G <grade>` 20/16 — bawah 146 < 176 | skala ×1,48 |

- Teks lewat `^FH_` + `^CI28` (aman dari injeksi), dipotong di server bila melebihi anggaran huruf (perkiraan lebar glif
  0,62 × lebar font) dan ditandai "terpotong" di pratinjau. Isi = **snapshot saat job dibuat** (connector tidak
  merender ulang dengan data terbaru).
- Blok RFID: `^RS8,<posisi>,<void>,<percobaan>,<mode galat>` · `^RFW,H^FD<EPC 24 hex>^FS` · baca balik
  `^RFR,H^FN9^FS ^FH_^HV9,24,EPC[,]_0D_0A,L^FS` dan/atau `^RVE` — dipilih per printer (`encode_report`).
- Profil per printer: dpi, lebar/tinggi mm, `^LH` x/y, `^LT`, `^MD`, `^PR`, posisi inlay, percobaan encode (bawaan 1),
  mode galat (bawaan N), laporan encode (bawaan `hv`), "tanpa laporan anggap tertulis" (bawaan **tidak**), media
  berinlay. Disimpan dengan sidik profil; job yang diklaim printer 300 dpi otomatis dirender 300 dpi.

## 6. Connector & simulator
- Ledger per printer: `CLAIMED → INTENT → STARTED → SENDING → SENT → OUTCOME → REPORTED` (+`SKIPPED`), kunci
  (job, item, attempt), SQLite WAL + `synchronous=FULL`. `SENDING` ditulis **sebelum** byte pertama ke printer.
- Pulih sesudah crash: `SENDING/SENT` tanpa hasil → hasil **tidak pasti** (`connector_recovery`) — tidak pernah dikirim
  ulang; `CLAIMED/INTENT/STARTED` belum menyentuh printer → dilanjutkan. Ledger hilang + ERP mengirim ulang attempt →
  item `started` dilaporkan tidak pasti.
- Per label: cek kesiapan (`~HS` + `~HQES`, timeout = tidak siap) → start ERP → kirim → tunggu (buffer kosong, sisa
  label 0, pernah terlihat sibuk / balasan RFID datang; jeda/kertas habis ditunggu sampai `pause_wait_s`) → nilai
  hasil. Printer tidak diam (label macet) → label berikut **tidak** dikirim.
- Offline: tanpa ERP tidak ada label baru dimulai; label yang sudah `STARTED` boleh selesai; hasil dikirim ulang
  dengan id sama (backoff 1→60 dtk). Lease diperpanjang otomatis; lease sempat habis → cek status attempt sebelum
  mencetak lagi (label yang sudah diputuskan operator dilewati).
- Satu instance per printer: kunci berkas lokal + instance id tetap di ledger (lease ERP per instance).
- Simulator `simulator/zpl_printer_sim.py`: buffer format, cetak berurutan, chip "tertulis", `~HS/~HQES/~HI/~JA`,
  `^RVE`, `^HV`, gangguan yang bisa diatur (§1). CLI untuk uji manual.

## 7. Hasil uji (apa adanya)
Stack sementara `kn-tmp-f-*` (DB `test_database` dipulihkan dari arsip acuan 8 Nov sebelum TIAP putaran).
| Rangkaian | Hasil |
|---|---|
| Uji lama print/RFID (10 berkas: comm04, iter108, iter116, iter118, iter149, iter263, iter264, iter265, iter266, ln120) — **dasar `5f1e36e`** | 46 gagal · 121 lulus · 4 lewati |
| Uji lama yang sama — **PREP-F** | 46 gagal · 121 lulus · 4 lewati — **daftar gagal IDENTIK** (diff kosong). Gagal = data acuan (mis. "butuh roll tanpa tag di wh_surabaya", device lain, kode tidak dikenal), bukan perilaku printer |
| `backend/tests/test_prep_f_printer.py` | **22 lulus** |
| `backend/tests/test_prep_f_connector_e2e.py` (ERP nyata + connector + simulator) | **5 lulus** (41 dtk) |
| `middleware/printer-connector/tests` (pytest di kontainer, Python 3.11) | **17 lulus** (92 dtk); juga lulus di Python 3.13 Windows host lewat runner sederhana |
| Jest `prepFPrinter.test.js` | **8 lulus** |
| Jest `phase4R3.test.js` (merender `RfidTagsView`) | 24 lulus · **1 gagal** — `inventory/registration/RegistrationDetail.jsx` (berkas paket G dari `main`, tidak disentuh PREP-F) |
| Jest `mobileShell.test.js` + `prepD2GateReview.test.js` | 22 lulus |
| ESLint berkas FE yang diubah/baru | 0 galat, 2 peringatan lama (`eslint-disable` tak terpakai, baris lama) |
| flake8 berkas Python baru | bersih kecuali baris panjang lama di `routers/rfid.py` / `rfid_ingest_service.py` |

Guardrail (dijalankan; `verify_state_machine.py` **tidak** dijalankan sesuai larangan). Hijau: custom_modals,
error_notice, knselect_contract, list_export (lapis perilaku CSV SKIP — Node tidak ada di host), page_tabs,
detail_modal, modal_dismiss, blocking_dialogs, picker_portal, escape_layers, codebase_map, rfid_tag_unique (+DATA di
kontainer), role_label, uom_vocab, status_history, roll_identity, access_catalog_nav, view_aliases, cross_entity &
concurrency (kontainer), `verify_contract.py --all` OK, `audit_i18n_id.py` (0 temuan di berkas PREP-F).
Merah **yang sama persis dengan dasar** (dibandingkan dengan ekspor `5f1e36e`): auth_coverage (8, design_gallery dll.),
atomic_claim (75 belum ditinjau — sesudah 3 entri PREP-F dicatat), numeric_bounds (HARD 3), to_list_bound,
entity_label (RegistrationDetail), qty_dual (host tanpa pydantic), no_secrets (8 temuan di `test_reports/*.xml` lama).

### Pemetaan RACC-21…30 (tanpa perangkat)
| ID | Terbukti tanpa perangkat | Masih menunggu CP30EN |
|---|---|---|
| RACC-21 PoC | — | seluruhnya (varian, firmware, modul RFID, dpi, `^RFW` di chip nyata, C72 membaca EPC) |
| RACC-22 routing & connector ganda | gudang/kemampuan; printer lain tidak dapat job ber-lease; instance lain dengan key sama tidak dikirimi; 2 printer paralel 4 job → tiap EPC sekali; renew vs reclaim tercatat | jaringan nyata |
| RACC-23 EPC & templat | EPC 24 hex persis di `^RFW,H`; baca balik ≠ ERP → gagal; label QR/teks tidak diakui RFID; 70 × 22 muat (hitungan dot) | keterbacaan font/QR, posisi inlay, tag tetangga |
| RACC-24 printed/encoded/verified | tiga dimensi terpisah di data & UI; verifikasi hanya label terkonfirmasi | C72 nyata |
| RACC-25 parsial | 10 label: 7 ok / 2 gagal encode / 1 macet → hanya 7 aktif (ERP nyata + simulator) | VOID/kertas habis di CP30EN |
| RACC-26 ACK hilang & crash | crash sesudah kirim → tidak pasti, tanpa cetak ulang; ACK hilang → ulang id sama | PC/printer nyata |
| RACC-27 lease habis & offline | item started tidak dialihkan; reclaim hanya untuk yang belum dimulai; offline tertahan & lanjut | — |
| RACC-28 reprint & retag | cetak ulang teks (EPC tetap) vs ganti tag (EPC baru, lama pensiun, riwayat, izin, pergerakan aktif ditolak, tahap stored tidak mundur) | penanganan fisik label lama (SOP) |
| RACC-29 UI | antrean/status/PIC/kesehatan/attempt/pratinjau/tindak lanjut; Jest | uji tampilan oleh pemilik |
| RACC-30 pemulihan efek | efek gagal sesudah status durable → dilengkapi (ulangan hasil, sapuan) tanpa cetak ulang/ganda | — |

## 8. Asumsi (bertanda — wajib dibuktikan uji meja)
- **[A1]** CP30EN menerima ZPL lewat TCP 9100 dan menjawab `~HS` / `~HQES` / `~HI` berformat Zebra.
- **[A2]** `^RS8,…`, `^RFW,H`, `^RFR,H` + `^HV…,L` (balasan `EPC[…]` lewat koneksi yang sama) dan/atau `^RVE`
  (`_+,n_` / `_-,n_`) didukung; encode gagal mencetak VOID.
- **[A3]** `~HS` mencerminkan format yang baru diterima (bila tidak, connector menunggu minimal 1–1,5 dtk sebelum
  menganggap diam).
- **[A4]** Lebar glif font 0 ≈ 0,62 × lebar font; QR versi 1–2 terbaca HP/C72 pada 15–16 mm.
- **[A5]** Media 70 × 22 mm berinlay; satu label per item (percobaan encode 1).
- **[A6]** Satu koneksi TCP pada satu waktu cukup (connector tidak membuka dua koneksi bersamaan ke satu printer).

## 9. Keputusan implementer (alasan)
1. **Start barrier ketat** — tanpa ERP tidak ada label baru dimulai. Alasan: lease ERP satu-satunya pencegah dua
   printer menulis EPC yang sama; sejalan K §10 (tanpa server lokal). Akibat: saat internet putus pencetakan berhenti
   (label yang sudah dimulai selesai) — lihat butir pemilik P1.
2. **Cetak ulang (resolusi) & ganti tag selalu EPC BARU**; EPC yang pernah terbit tidak pernah dipakai lagi
   (`allocate_epc` memeriksa semua status). Alasan: chip label gagal/tidak pasti bisa saja sudah tertulis.
3. **Sukses label RFID yang tidak pasti wajib bukti baca EPC** (sesi verifikasi/rfid_reads sejak label dimulai).
   Cek visual tidak cukup untuk chip.
4. **Item `started` dengan lease habis tidak dialihkan otomatis**; reclaim hanya bila tidak ada item started.
5. **Hasil diterima dari attempt pemulai walau lease habis**; hasil bertentangan tidak memundurkan status final →
   ditandai bertentangan untuk ditinjau.
6. **Izin**: tinjau hasil & ganti tag = `wms.approve` (Admin Gudang/Manajer/Admin); cetak ulang teks = `wms.print`
   (petugas gudang); ubah profil printer = admin (sama dengan registri perangkat).
7. **Cetak ulang teks tidak menulis chip** dan memakai kemampuan `rfid` (media 70 × 22 yang sama).
8. **Payload dirender saat klaim** dari snapshot item dengan profil printer pengklaim (203/300 dpi bisa campur);
   digest per item dicatat dan dicek di hasil.
9. **Bawaan profil**: laporan encode `hv` (baca balik EPC), percobaan 1, mode galat N, "tanpa laporan anggap tertulis"
   mati — konservatif; diubah setelah uji meja.
10. **Lease per instance connector** (id tetap di ledger) — dua PC dengan key sama tidak bisa mencetak job yang sama.
11. Router baru disertakan dari `routers/rfid.py` (bukan `server.py`) untuk mengurangi bentrok dengan paket lain.
12. **Job RFID untuk roll ber-tag aktif tetap diizinkan** (LN-042-T03 "EPC tetap", diuji `test_comm04`), tetapi EPC
    yang sama di dua item terbuka ditolak; UI baru tidak menawarkan jalur ini (butir P3).

## 10. Butir untuk pemilik (+ rekomendasi)
| ID | Hal | Rekomendasi |
|---|---|---|
| P1 | Pencetakan saat internet gudang putus | Tetap berhenti (bawaan sekarang) + internet cadangan; opsi lain (cetak dalam masa lease tanpa ERP) menambah risiko EPC ganda |
| P2 | Label cetak ulang teks pada media berinlay membawa chip kosong (EPC pabrik, dianggap tidak unik) → bisa terbaca "EPC asing" di gate | SOP: tempel menimpa label lama di roll yang sama; atau sediakan media non-RFID untuk cetak ulang teks; atau pakai "ganti tag" |
| P3 | Jalur lama "cetak tag lagi untuk roll ber-tag aktif" (EPC sama → dua chip ber-EPC sama) | Tutup jalur ini; ganti dengan "ganti tag" / "cetak ulang teks" |
| P4 | Siapa boleh memutus hasil tidak pasti & ganti tag | `wms.approve` (Admin Gudang ke atas) — sesuai pola PREP-D2 |
| P5 | SOP label VOID & label "tidak pasti" (musnahkan, simpan untuk audit, atau pindai C72 dulu) | Pindai C72 dulu; musnahkan VOID; catat di keputusan |
| P6 | Jumlah percobaan encode per label (1 vs 3) | 1 (hasil per label jelas) — ditinjau ulang dari tingkat gagal uji meja |
| P7 | PC gudang untuk connector (spesifikasi, UPS, satu PC per gedung atau satu untuk semua printer) | Satu PC per gedung berprinter, UPS, IP printer tetap |

## 11. Daftar uji meja CP30EN (saat unit datang)
1. **Identitas:** catat label varian/serial, firmware, modul RFID, region UHF; `python -m kn_printer_connector check`
   (`~HI`) — dpi sebenarnya (203/300) → set profil.
2. **Jaringan:** IP tetap, port 9100 terbuka, satu/lebih koneksi bersamaan, perilaku saat dua koneksi.
3. **ZPL dasar:** cetak pratinjau sampel (profil → ZPL contoh) → ukur posisi teks/QR, keterbacaan QR oleh HP & C72,
   font 0 (huruf terpotong/meluber?), `^LH`/`^LT`/`^PW`/`^LL`, kalibrasi media (gap/black mark).
4. **RFID tulis:** `^RFW,H` 24 hex → baca dengan C72: EPC persis sama, tidak terpotong, tidak menulis tag tetangga
   (uji label beruntun), PC bits.
5. **Posisi inlay & daya:** cari `^RS` p (F/B mm atau dot) yang memberi encode stabil; catat apakah perlu setel daya.
6. **Laporan hasil:** apakah `^HV` mengembalikan `EPC[…]` lewat TCP 9100? apakah `^RVE` didukung? format persis →
   pilih `encode_report`.
7. **Gagal encode:** tag rusak/tanpa inlay → VOID tercetak? `^RS` e = N/P/E perilakunya; `~HQES` bit galat RFID?
8. **Status:** `~HS` saat siap, mencetak, kertas habis, ribbon habis, kepala terbuka, jeda; apakah format yang baru
   diterima langsung terlihat di `~HS` (asumsi A3).
9. **Gangguan:** cabut LAN di tengah job, matikan printer, kertas habis di tengah batch → hasil connector (tidak pasti
   / tertahan) dan ERP sesuai §4.
10. **Kecepatan:** label/menit untuk batch 50 (dengan baca balik) + waktu tunggu per label; bandingkan dengan beban
    ±6.000 roll/hari total (≈ 2 printer × 8 jam → ± 6,3 label/menit/printer).
11. **Verifikasi C72:** label ditempel ke roll → sesi verifikasi → bersih; uji penempelan tertukar.
12. **Ganti tag & cetak ulang teks** pada unit: label pengganti terbaca, label lama ditangani SOP.

## 12. Sisa & risiko
- Semua perintah/format RFID & status **belum terbukti** di CP30EN (§8). SDK Windows_ZPL/ZPL_Linux Chainway tidak
  dipakai (tidak tersedia lokal); connector memakai ZPL mentah lewat TCP.
- Lebar teks berbasis perkiraan; pratinjau SVG adalah perkiraan (QR digambar sebagai kotak).
- Pembatalan job/item yang masih `pending` belum ada (hanya lewat tindak lanjut sesudah gagal/tidak pasti).
- Penjadwal tidak disentuh: sapuan efek tertunda berjalan saat printer menarik antrean dan lewat endpoint manual
  (bukan job terjadwal). `printer_stuck_watch` tetap hanya menghitung job `queued`.
- Data lama: job sebelum PREP-F dilengkapi item id saat disentuh; job lama ber-ZPL 4 × 2" dirender ulang ke 70 × 22
  saat diklaim printer.
- Uji Jest penuh & build produksi FE tidak dijalankan (hanya suite terkait).

## 13. Berkas berisiko bentrok
`backend/routers/rfid.py` (endpoint printer + include router di akhir berkas), `backend/services/rfid_ingest_service.py`
(hanya bagian printer di akhir berkas), `frontend/src/features/rfid/RfidTagsView.jsx` (tab + tombol),
`scripts/guardrails/verify_auth_coverage.py` & `verify_atomic_claim.py` (entri daftar). Tidak menyentuh `rfid_v2_*`,
`gate_*`, handheld/`initial_registration*`, `middleware/c72-app`, `middleware/u300-agent`, `server.py`, `deploy/`.
