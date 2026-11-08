# Audit mendalam middleware RFID U300 + peta K-RFID-07

**Tanggal:** 8 Nov 2026 · **Pelaksana:** Claude Code (sesi cloud) · **Sifat:** analisis saja — **tidak ada kode yang
diubah**. Baca bersama [`KEPUTUSAN_GATE_RFID.md`](KEPUTUSAN_GATE_RFID.md) (fakta lapangan, keputusan K-RFID).

| Objek audit | Baseline |
|---|---|
| U300 Reader Agent 0.4.0-lab (PT Kubus) | `middleware/u300-agent/` di `2266a52` |
| Paket integrasi ERP 0.5.0 (patch, belum diterapkan) | `middleware/u300-erp-integration-0.5.0/erp-u300-v2.patch` |
| Kontrak | `contracts/OPENAPI_RFID_V2.json` 2.0.0 (identik di agent, patch `backend/contracts/rfid_v2.json`, dan paket spesifikasi `docs/development/…/sources/middleware/kontrak/`) |
| Logika gate ERP saat ini | `backend/services/gate_evaluator.py`, `rfid_ingest_service.py`, `routers/rfid.py` di `79bacbd` |
| SDK vendor | `app/libs/DeviceAPI_ver20251103_release.aar` — diperiksa signature dan sebagian bytecode dengan `javap`/`javap -c` (tidak dijalankan, tidak disalin) |

Keputusan yang dipakai sebagai acuan: **K-RFID-01 photo-eye masuk pengadaan** (logika "photo-eye utama + cadangan RF"),
**K-RFID-02 asumsi antena varian Indonesia** (920–923 MHz). K-RFID-07 dianalisis di dokumen ini (§5); K-RFID-03…06
dan 08 masih terbuka; audit memunculkan dua keputusan baru, K-RFID-09 (kebijakan alarm) dan K-RFID-10 (muat multi-trip).

---

## 0. Ringkasan eksekutif

Rancangan Kubus **kuat di lapisan transport dan keamanan data**: outbox SQLite persist-before-send, event ID stabil,
ACK per event setelah tulis journaled, close idempotent, keputusan "green" yang fail-closed dan berumur pendek, klaim
crossing anti-keluar-ulang, manifest dibaca dari dokumen bisnis (bukan dari klien), device key di Android Keystore.
Ini layak dijadikan **dasar** pengembangan.

Yang **belum** siap adalah **lapisan logika gate** — justru bagian yang menentukan apakah gate bisa dipakai:

1. **Volume bacaan tidak dikendalikan** (AUD-MW-01). Setiap callback SDK menjadi satu event. Dengan session 0 (yang
   direkomendasikan riset) satu muatan menghasilkan ribuan event → antrean → keputusan basi → alarm terkunci, dan di
   atas 10.000 event per lintasan **reader macet permanen** (deadlock).
2. **Batas lintasan belum mengikuti photo-eye** (AUD-MW-02). Lintasan dibuka bacaan pertama dan ditutup oleh jeda
   3 detik/batas 30 detik. Sensor hanya dipakai untuk arah (gate dua arah), tidak menutup lintasan, tidak mengenali
   mundur/batal, dan sensor rusak menghentikan reader (bukan jatuh ke logika RF).
3. **Kebijakan alarm membuat gate praktis selalu merah** (AUD-MW-03). Semua hasil non-hijau mengunci lampu merah,
   kuncinya berantai ke lintasan berikutnya, roll kurang (yang wajar terjadi 1,5–5 % per tag) langsung RED, dan
   alasan pelanggaran asli bisa tertimpa alasan lain. Lintasan kosong (orang/forklift kosong) juga terkunci.
4. **Model keputusan mengasumsikan satu truk penuh per lintasan** (AUD-MW-22). Hijau hanya bila **seluruh** roll
   dokumen terbaca dalam satu lintasan, padahal barang lewat gate di atas stacker dan satu SJ bisa beberapa trip —
   setiap trip parsial jadi RED.

Temuan tinggi lain yang perlu masuk rencana: setelan radio (session/TagFocus) tidak dikendalikan agent (AUD-MW-04),
RSSI hilang diam-diam bila locale perangkat Bahasa Indonesia (AUD-MW-23), kerja berat di thread callback SDK
(AUD-MW-24), error ERP yang membuat reader terkunci sampai ada orang ke lokasi (AUD-MW-06), dan klaim crossing yang
bocor saat konflik (AUD-MW-08). Total 24 temuan: 4 kritis, 9 tinggi, 7 sedang, 4 rendah.

Rekomendasi K-RFID-07 (§5): **pakai Kubus V2 (agent + `rfid_v2`) sebagai lapisan transport/bukti, pakai
`gate_evaluator` KNHOST sebagai mesin aturan bisnis** (patch sudah melakukannya), lalu bangun **lapisan lintasan
baru** (photo-eye, ringkasan bacaan, daftar latar, status "perlu diperiksa") di atas keduanya. Jalur lama
`/api/rfid/ingest` dibekukan untuk device V2.

---

## 1. Metode dan batas

- Membaca seluruh sumber Java agent (817 baris), router/service `rfid_v2`, perubahan `gate_evaluator`/`server.py`,
  panel `U300Operations.jsx`, tes patch, kontrak OpenAPI, dokumen agent 01–07, paket spesifikasi KNI-RFID-MW-SPEC-001.
- Menerapkan patch pada salinan terpisah (scratch, bukan repo) untuk membaca berkas hasil dan nomor baris.
- Menjalankan tes host yang bisa jalan tanpa perangkat (§2).
- Memeriksa API SDK dari AAR dengan `javap`, plus bytecode untuk format RSSI & cap waktu (§7).
- Riset referensi open-source dan arsitektur (§8).
- **Tidak dijalankan:** tes integrasi ERP (tidak ada MongoDB di container), build APK (tidak ada Android SDK), uji
  perangkat. Nomor baris berkas patch merujuk berkas **setelah** patch diterapkan.

## 2. Hasil pengujian yang dijalankan

| Pemeriksaan | Hasil |
|---|---|
| `SafetyTest` / `HostTest` / `DecisionPolicyTest` (JDK host, org.json 20240303 hash cocok) | ✅ 24 / 19 / 63 assertion |
| `TransportTest` (HTTPS loopback) | ✅ 15 assertion |
| `validate_contract.py` + `test_snapshot.py` | ✅ 3 skema + negatif · 5 kasus |
| `git apply --check` patch ke `HEAD` | ⚠️ backend bersih; `frontend/src/features/rfid/RfidDevicesView.jsx` bentrok (3 hunk kecil) |
| Tes integrasi ERP patch (53 + 34 + 9 assertion menurut paket) | ❌ tidak dijalankan di sini |
| Build APK / tes instrumentasi Android | ❌ tidak dijalankan di sini |

Catatan cakupan tes paket: semua skenario ERP memakai 1–2 roll. **Tidak ada** uji beban, uji kapasitas lintasan,
uji batas waktu keputusan, uji alarm berantai, maupun uji jalur gate lama setelah perubahan `gate_evaluator`.

---

## 3. Temuan

Skala: **Kritis** = gate tidak bisa dipakai/aman saat go-live · **Tinggi** = salah keputusan atau macet pada kondisi
wajar · **Sedang** = keandalan/operasional · **Rendah** = kebersihan/dokumentasi.

### Kritis

#### AUD-MW-01 — Volume bacaan tidak dikendalikan → keputusan basi, alarm terkunci, reader macet permanen
- **Bukti.** Setiap callback SDK disimpan sebagai event baru (`AgentService.java:72-84`, `Reader.java:26`). Upload
  hanya **1 batch per siklus 1 detik** (`AgentService.java:38`, `:177`), `max_events` template = 100 → ±100 event/s.
  Close baru dikirim setelah semua event lintasan ter-ACK. Server menandai `TIME_UNVERIFIED` (REVIEW, terkunci) bila
  close tiba > 30 s setelah `closing_captured_at` (`rfid_v2_service.py:393-394`). Server menolak event ke-10.001 /
  > 8 MB per lintasan dengan **409 `PASSAGE_FROZEN_OR_FULL`** (`:275-281`); agent memperlakukan semua 409 sebagai
  `contract_block` dan menghentikan capture (`AgentService.java:184`). Event sisa lintasan itu tidak akan pernah
  diterima, sehingga lintasan **tidak bisa ditutup** dan `settled()` tidak pernah benar → konfigurasi baru juga
  tidak pernah diterapkan. Antrean lokal 10 MB (template) ≈ 35.000 event (±290 byte/event) juga menghentikan capture (`:79`).
- **Skenario.** Riset menyarankan session 0 + TagFocus mati agar tag diam terus melapor (§2 dokumen keputusan) —
  artinya tag melapor tiap ronde inventory. Muatan 100 roll × 3 antena, beberapa bacaan/detik per antena, ±10 detik
  di area baca → ribuan event per lintasan; ditambah tag rak yang ikut terbaca.
- **Dampak.** Hampir setiap muatan penuh berakhir REVIEW terkunci karena waktu; muatan besar dapat membuat reader
  berhenti total sampai ada intervensi database.
- **Rekomendasi.** (a) Agent membuat **ringkasan per EPC × antena per jendela 250–500 ms** (jumlah baca, RSSI puncak &
  rata-rata, waktu pertama/terakhir dari reader) — sejalan dengan Tahap 2 dokumen keputusan; bukan dedup yang membuang
  bukti. Butuh **kontrak 2.1** (skema `Observation` saat ini `additionalProperties: false`). (b) Kirim beberapa batch per
  siklus sampai antrean habis atau anggaran waktu tercapai. (c) Server: lintasan penuh → ACK `quarantined` yang durable
  (mis. koleksi overflow) + keputusan REVIEW `CAPTURE_OVERFLOW`, bukan 409 permanen. (d) Agent membedakan kode error
  (lihat AUD-MW-06).

#### AUD-MW-02 — Batas lintasan belum sesuai K-RFID-01 (photo-eye) dan fakta gate satu arah
- **Bukti.** Lintasan dibuka bacaan pertama (`AgentService.java:80`) atau tepi sensor (`:114`), ditutup hanya oleh
  jeda 3 s / maks 30 s / manual (`:140`, `:67`). Nilai kontrak `boundary_reason: "sensor"` **tidak pernah** dipakai.
  Semantik sensor A/B = **arah** (A→B out, B→A in) dan hanya dihitung untuk gate `bidirectional` (`:116`,
  `Config.java:318-324`, dokumen 02 tabel parameter). Server untuk gate satu arah mengabaikan urutan sensor
  (`rfid_v2_service.py:288-305`). Sensor tidak terbaca di mode perangkat → exception → `fault()` → capture berhenti
  (`AgentService.java:111`), bukan jatuh ke logika RF. Kontrak tidak punya `boundary_reason` "batal" dan verdict tidak
  punya `CANCELLED`.
- **Dampak.** Tag diam di sekitar gate membuat lintasan terus terbuka hingga 30 s → `max_duration` → `CAPTURE_INCOMPLETE`
  → terkunci; muatan berurutan bisa tergabung; stacker yang maju lalu mundur tetap dianggap lintasan; target latensi
  M10 ≤ 3 s mustahil karena penutupan menunggu jeda 3 s lebih dulu. **Lintasan tanpa tag** (orang/forklift kosong
  memotong sinar — tepi sensor sudah membuka lintasan di gate satu arah, `:114`) dikirim dengan
  `observed_event_count: 0`; server memberi `MANIFEST_MISMATCH` lalu `CAPTURE_INCOMPLETE` karena `last_event_id`
  kosong (`rfid_v2_service.py:375-379`) → **REVIEW terkunci**, padahal tabel §4 dokumen keputusan menghendaki
  "tanpa transaksi & tanpa alarm". Hal yang sama untuk lintasan yang terputus restart (`recoverInterrupted` mengirim
  arah `unknown` → `DIRECTION_UNVERIFIED`).
- **Rekomendasi.** State machine lintasan gate satu arah: `IDLE → ARMED (sinar A terpotong; ambil pre-buffer 2–3 s) →
  IN_PORTAL (sinar B terpotong) → EXITED (B pulih + ekor pendek) → close boundary_reason=sensor`; `A pulih tanpa B` atau
  `B tak pernah terpotong dalam batas waktu` → `CANCELLED` (tanpa transaksi, tanpa alarm, bukti tetap disimpan); sensor
  macet/terhalang > N s → **mode cadangan RF** (rombongan EPC kuat non-latar) dan laporan kesehatan, bukan berhenti.
  Kontrak 2.1: peristiwa photo-eye, `boundary_reason` `cancelled`, status `CANCELLED`.

#### AUD-MW-03 — Kebijakan alarm: semua non-hijau terkunci, berantai, RED asli tertimpa, roll kurang = RED
- **Bukti.** `latched = verdict != 'GREEN'` (`rfid_v2_service.py:421`) → REVIEW (`NO_MANIFEST`, `CAPTURE_INCOMPLETE`,
  `TIME_UNVERIFIED`, …) juga mengunci lampu merah. Selama ada satu kunci yang belum di-ack, **setiap** lintasan baru
  dipaksa `GATE_LATCHED` dan ikut terkunci (`:384-386`) — acknowledge per lintasan (`routers/rfid_v2.py:175`). Alasan
  ditentukan oleh **penimpaan berurutan** (`:346-404`): RED pelanggaran nyata (mis. roll karantina, roll lebih) dapat
  tertimpa REVIEW berikutnya (`CAPTURE_INCOMPLETE`, `GATE_LATCHED`, `TIME_UNVERIFIED`) sehingga panel hanya
  menampilkan alasan terakhir. `missing > 0` → RED (`:375`).
- **Hitungan.** Dengan capture 99 %/tag, peluang 100 roll terbaca semua ≈ 0,99¹⁰⁰ ≈ 37 %; dengan galat lapangan
  1,5–5 %/tag ≈ 22 %…0,6 %. Artinya sebagian besar muatan penuh akan RED terkunci.
- **Rekomendasi (butuh keputusan pemilik — kebijakan alarm).** Pisahkan **RED** (pelanggaran: roll tak berdokumen,
  karantina, dokumen batal, keluar ulang, EPC asing berskor kuat) dari **PERLU DIPERIKSA/kuning** (roll kurang, capture
  tidak lengkap, waktu tidak tervalidasi, tanpa manifest) yang tidak mengunci gate tetapi masuk antrean periksa
  dengan bukti; **satu kunci per gate** (ack melepas gate, lintasan yang terjadi selama terkunci tetap tercatat dengan
  verdict aslinya); simpan **daftar alasan** + verdict terberat, bukan satu kode yang ditimpa; roll kurang → alur rescan
  handheld (usulan riset #11).

#### AUD-MW-22 — Model "satu lintasan = seluruh manifest" tidak cocok dengan pemuatan multi-trip stacker
- **Bukti.** Hijau hanya bila `completion_basis = manifest_full` **dan** semua roll seluruh dokumen terikat terbaca
  dalam **satu** lintasan (`rfid_v2_service.py:349`, `:374-376`; agent `Safety.greenAllowed`, `DecisionPolicy.validGreen`
  mensyaratkan `manifest_full` dan `missing = 0`). Gabungan s.d. 20 SJ / 2.000 roll per lintasan
  (`validate_sources`, `bind_manifests`) mengasumsikan satu truk penuh melewati gate. Fakta lapangan: barang lewat
  gate di atas **stacker ±180 × 180 cm, maks 7 lapis**; satu SJ bisa butuh beberapa kali angkut. Basis
  `manifest_subset` ada di kontrak, tetapi selalu REVIEW (`FULL_MANIFEST_REQUIRED`, `:383`).
- **Dampak.** Setiap trip kecuali yang memuat seluruh SJ → `missing > 0` → RED terkunci; trip kedua dst. untuk SJ yang
  sama juga berisiko `REPLAY_*` bila roll trip pertama terbaca lagi. Gate tidak bisa dipakai untuk alur muat normal.
- **Rekomendasi (butuh keputusan pemilik).** **Sesi dokumen akumulatif**: tiap lintasan dinilai terhadap sisa roll
  dokumen yang belum lewat — hijau bila semua EPC kuat non-latar milik dokumen aktif dan belum pernah lewat;
  **roll kurang dinilai saat dokumen ditutup/dispatch**, bukan per lintasan (pola juga diusulkan riset arsitektur §8).
  Agent harus mengizinkan hijau untuk basis subset-akumulatif setelah kebijakan diputuskan.

### Tinggi

#### AUD-MW-04 — Setelan radio penting tidak dikendalikan agent
- **Bukti.** `Reader.start` hanya **memverifikasi** region (`getFrequencyMode`) dan daya per antena (`Reader.java:18-22`),
  tidak menyetel atau memverifikasi session/target/Q, TagFocus, FastID, filter. SDK menyediakan
  `setGen2/getGen2` (`querySession`, `queryTarget`, `Q`, …), `setTagFocus/getTagFocus`, `setFastID`, `setFilter`,
  `setFastInventoryMode` (§7).
- **Dampak.** Perilaku baca (kunci riset: session 0, TagFocus mati, daya ±15–16 dBm konduksi) bergantung pada sisa
  setelan aplikasi demo vendor; dua gate identik bisa berperilaku beda.
- **Rekomendasi.** Masukkan session/target/Q/TagFocus/FastID (dan filter bila skema EPC KN punya prefiks pembeda) ke
  profil commissioning `kn-u300-v1`; set + baca ulang saat start; gagal → tidak mulai (pola fail-closed yang sama).

#### AUD-MW-05 — Data SDK yang berguna belum dipakai; cap waktu perlu monotonik
- **Bukti.** `UHFTAGInfo` punya `getCount()`, `getPhase()`, `getFrequencyPoint()`, `getTimestamp()`; agent hanya
  mengambil EPC/TID/antena/RSSI (`Reader.java:26`). Bytecode SDK: `getTimestamp()` diisi
  `System.currentTimeMillis()` saat SDK mem-parse frame (`com/rscja/deviceapi/b.class`) — **jam dinding Android, bukan
  jam reader**. Phase/frequency point hanya terisi lewat `startInventoryTag(InventoryParameter)` dengan
  `setNeedPhase/NeedFrequencyPoint(true)` (menurut Javadoc salinan komunitas).
- **Dampak.** Agent memakai jam server-tersinkron saat callback sebagai `captured_at`, tetapi tidak menyimpan cap waktu
  **monotonik** per bacaan untuk bentuk sinyal naik–puncak–turun (usulan riset #8); jam dinding bisa melompat.
- **Rekomendasi.** Ringkasan kontrak 2.1 memakai `elapsedRealtimeNanos` (seperti LLRP: UTC **dan** uptime);
  `getCount()`/phase diuji di meja sebelum dipakai.

#### AUD-MW-23 — RSSI bisa hilang diam-diam bila locale Android = Indonesia
- **Bukti.** SDK membentuk RSSI dengan `new DecimalFormat("##0.00")` **tanpa Locale** (`com/rscja/deviceapi/b.class`,
  juga `…qcom/deviceapi/S.class`, `F.class`), awalan `"-"`, dan `"N/A"` di luar rentang. Uji JDK: locale `id-ID` →
  `"-58,30"` → `Double.valueOf` gagal. Agent mem-parse dengan `Double.valueOf` dan menelan error → `rssi_dbm = null`
  (`AgentService.java:81`); server menerima null (skema `nullable`).
- **Dampak.** Seluruh lapisan skor sinyal (daftar latar, ambang RSSI, bentuk sinyal) tidak berfungsi tanpa peringatan
  bila U300 disetel ke Bahasa Indonesia. `raw_rssi` tetap tersimpan (bagus).
- **Rekomendasi.** Parse tahan locale (`,` → `.`, tangani `N/A`); telemetry menghitung bacaan tanpa RSSI; masuk
  checklist uji meja (locale perangkat).

#### AUD-MW-24 — Kerja berat di thread callback SDK
- **Bukti.** Callback inventory dipanggil dari thread internal SDK (`RFIDWithUHFUART_qcom` punya `inventoryThread`).
  Di dalamnya agent mengambil lock global, menjalankan `pendingBytes()` (full scan), ukuran berkas DB, `StatFs`, lalu
  `INSERT` SQLite — **per bacaan** (`AgentService.java:72-84`).
- **Dampak.** Callback lambat berisiko menahan/menjatuhkan bacaan pada laju tinggi (datasheet: 950–1300+ tag/s,
  tidak konsisten); tidak ada penghitung bacaan yang hilang.
- **Rekomendasi.** Callback hanya menyalin ke antrean RAM terbatas; writer terpisah menulis ringkasan dalam transaksi
  batch; hitung `dropped_reads` di telemetry.

#### AUD-MW-06 — Penanganan error terlalu kasar → pemulihan harus datang ke lokasi
- **Bukti.** Semua 401/403 → `auth_block` permanen; semua 400/409 → `contract_block` (`AgentService.java:183-184`).
  Server memakai 403 juga untuk device dinonaktifkan (`rfid_ingest_service.authenticate`), `GATE_NOT_BOUND`,
  `READER_REQUIRED`; 409 untuk `CONFIG_REQUIRED` (profil belum terbit), `DEVICE_MOVED`, `PASSAGE_FROZEN_OR_FULL`.
- **Dampak.** Menonaktifkan reader sementara di ERP, reader dinyalakan sebelum profil terbit, atau 403 dari proxy →
  reader terkunci sampai provisioning ulang/PIN di lokasi.
- **Rekomendasi.** Putuskan berdasarkan `detail.code`; state terpisah `ADMIN_DISABLED`/`CONFIG_REQUIRED` dengan polling
  lambat (spesifikasi 03 §3.4 sudah menyebut state ini); hanya `auth` sungguhan yang memblokir.

#### AUD-MW-07 — Kinerja penyimpanan dan pembacaan di server
- **Bukti.** Tiap event = `insert_one` klaim ID + `update_one` dokumen lintasan, keduanya `w=majority, j=true`, berurutan
  (`rfid_v2_service.py:39`, `:254-277`). Semua event menumpuk di **satu dokumen** lintasan (s.d. 8 MB) yang di-update per
  event. `gate_state` membaca dokumen lintasan **penuh tanpa projection** (`:433`) padahal agent mem-poll hingga 4 lintasan
  tiap detik; jalur duplikat membaca dokumen penuh **per event** (`:279`). Close mengevaluasi tiap EPC berurutan
  (tag → roll → `gate_evaluator`, beberapa query/EPC; manifest s.d. 2.000 roll) sementara read-timeout agent 5 s
  (`Api.java:39`).
- **Rekomendasi.** Projection `{'decision':1}` di gate-state; event di koleksi sendiri (unik `passage+event_id`) dengan
  bulk write; evaluasi close berbasis query `$in`; uji beban 2.000 roll/10.000 ringkasan sebelum pilot.

#### AUD-MW-08 — Klaim crossing bocor saat konflik
- **Bukti.** Loop insert klaim (`rfid_v2_service.py:405-416`) tetap menyisipkan klaim roll lain setelah salah satu roll
  `REPLAY_CROSSING`; keputusan akhirnya RED, tetapi klaim-klaim itu tetap milik lintasan RED tersebut.
- **Dampak.** Roll yang sah ikut "terkunci": lintasan ulang yang benar untuk dokumen yang sama → `REPLAY_EXIT`.
  Belum ada alur pemulihan klaim (diakui `REVIEW.md` butir 4).
- **Rekomendasi.** Periksa semua klaim dulu, sisipkan hanya bila tidak ada konflik (atau transaksi Mongo), dan buat alur
  koreksi klaim beraudit.

#### AUD-MW-09 — Dua jalur gate hidup berdampingan; perubahan perilaku gate lama tanpa tes regresi
- **Bukti.** Patch mempertahankan `/api/rfid/ingest` (jalur lama: jendela 10 s, `stamp_exit` saat terbaca —
  `rfid_ingest_service.py:80-81`, `:219`) untuk device yang sama. V2 menghormati `gate_exit` lama (REPLAY_EXIT) dan jalur
  lama menghormati klaim V2 (`gate_evaluator.py:111-118` setelah patch). Patch juga mengubah resolver transfer
  (keanggotaan roll sungguhan, transfer ber-SO) yang dipakai jalur lama.
- **Dampak.** Cap "sudah keluar" palsu dari jalur lama (temuan riset) bisa menyeberang ke V2; perubahan resolver
  belum diuji pada skenario P09/`test_iter263_wms_rfid_r0r1r2.py`/`test_fase_sl_rfid_alias.py`.
- **Rekomendasi.** Flag protokol per device (`legacy`/`v2`), jalur lama menolak device V2; jalankan tes regresi gate lama
  setelah merge. Bagian Makloon/Perbaikan dari P18 tidak tersentuh (resolver P18 jalan lebih dulu); untuk V2 dokumen
  MKO/perbaikan belum didukung sebagai sumber manifest → `SOURCE_CONTEXT_MISMATCH` (fail-closed, perlu diputuskan).

#### AUD-MW-10 — Panel ERP belum siap operasional
- **Bukti.** `U300Operations.jsx`: kontrol HTML mentah (bukan komponen KN), kode mentah tampil langsung
  (`REVIEW`, `MANIFEST_MISMATCH`, ID lintasan), hanya hitungan cocok/kurang/lebih tanpa **daftar roll** kurang/lebih,
  profil diunggah sebagai berkas JSON mentah, tidak ada peringatan reader berhenti/telemetry basi, ack per lintasan
  dengan izin `wms:scan` saja. Integrasi ke `RfidDevicesView.jsx` bentrok dengan restrukturisasi D-29/L-02/L-03.
- **Rekomendasi.** Antrean periksa admin gudang dengan bukti per roll, istilah Indonesia, izin ack terpisah, alert
  kesehatan reader; ikuti pedoman UI repo.

### Sedang

| ID | Temuan | Bukti | Rekomendasi |
|---|---|---|---|
| AUD-MW-11 | Query antrean full-scan per bacaan & 10×/detik; histori tak pernah dibersihkan | `Journal.java:29` (`SUM(LENGTH(body)) … status!='acked'`), dipanggil `AgentService.java:79` dan layar `:144` tiap 100 ms | `status IN ('pending','quarantined')` (pakai index) atau counter; layar 1×/detik; kebijakan retensi |
| AUD-MW-12 | Jam hanya disinkronkan dari respons config (tiap 60 s, RTT < 2 s); jaringan lambat → `unsynced` → `TIME_UNVERIFIED` | `AgentService.java:45-46`, `rfid_v2_service.py:393` | sinkron dari setiap respons ber-`server_time` |
| AUD-MW-13 | Versi config baru di ERP → gate-state mismatch → exception → `online=false` hingga config diambil (≤ 60 s); lintasan jadi backfill | `AgentService.java:248-250` (`acceptState`) | mismatch memicu ambil config segera |
| AUD-MW-14 | Indikator hanya merah/hijau; kuning dan buzzer tidak ada; GPI dipoll 100 ms | `AgentService.java:120-127`; SDK `RFIDWithUHFA4` tidak punya callback GPI (hanya kelas `…NetWork`/A8) | GPO ke-3 untuk kuning, buzzer untuk RED, polling GPI lebih rapat atau uji latensi |
| AUD-MW-15 | Manifest dipilih manual dan menetap sampai diganti; lupa ganti → muatan berikutnya RED | `rfid_v2_service.py:201-221` | auto-cocok ke dokumen aktif gudang/arah (dokumen selalu ada sebelum barang lewat) atau kedaluwarsa binding |
| AUD-MW-16 | Paritas kontrak: acknowledge implementasi (`device_id`+`note`) ≠ skema `GateAcknowledge` (`logical_gate_id`, `latch_id`, `decision_id`, `note`); endpoint `/ops/*` tidak ada di OpenAPI | `routers/rfid_v2.py:175-185` | revisi OpenAPI bersamaan dengan kode (aturan paket spesifikasi) |
| AUD-MW-17 | Tidak ada alert ERP untuk reader berhenti, telemetry basi, antrean naik | telemetry hanya disimpan (`rfid_v2_service.py:438`) | aturan alert + tampilan kesehatan |

### Rendah

| ID | Temuan | Rekomendasi |
|---|---|---|
| AUD-MW-18 | Ukuran body dihitung beda (Java ringkas vs `json.dumps` Python berspasi) → 413 palsu dekat batas; agent pulih dengan memecah batch | hitung dengan separator ringkas di server |
| AUD-MW-19 | Debounce 10–2000 ms dicek terhadap polling 100 ms; tepi berbarengan dalam satu tick membatalkan arah | sesuaikan dengan state machine baru |
| AUD-MW-20 | AAR dan APK vendor ada di riwayat git; aman selama repo privat; izin distribusi vendor belum pasti | bila repo dibuka, bersihkan riwayat; pastikan lisensi |
| AUD-MW-21 | APK debug-signed; build/instrumentasi Android belum pernah dijalankan di perangkat | sudah diakui paket; masuk checklist commissioning |

### Yang sudah baik (pertahankan)
Outbox persist-before-send + recovery `INTERRUPTED`; event ID stabil saat retry dan pecah batch 413; ACK durable per
event (`w=majority,j=true`); close idempotent dengan `Idempotency-Key` + hash isi; green hanya bila final, segar, live,
konteks sama, manifest penuh, tanpa kunci (`DecisionPolicy`, `Safety.greenAllowed`); backfill tidak pernah hijau;
manifest dari dokumen bisnis asli dan diperiksa ulang saat close; klaim crossing lintas reader; device key tidak bisa
ack/ekspor; scope entitas diperiksa di bind/riwayat/ekspor/ack; Keystore + PIN PBKDF2; HTTPS wajib.

---

## 4. Kecocokan dengan keputusan K-RFID dan fakta lapangan

| Hal | Kondisi kode Kubus | Yang perlu berubah |
|---|---|---|
| Photo-eye (K-RFID-01: masuk) | Sensor = arah gate dua arah; tidak menutup lintasan; rusak = berhenti | State machine tembus/batal + pre-buffer + cadangan RF (AUD-MW-02) |
| Gate satu arah, IN/OUT terpisah | Didukung (`direction: in/out`, satu logical gate per reader) | Cocok: satu U300 per gate; 3 antena + 2 GPI muat (GPI1–4, GPO1–4) |
| 3 antena atas/kiri/kanan | Template berisi 2 antena; peta posisi tidak ada | Profil: peta port → posisi + daya per port |
| Antena varian Indonesia (K-RFID-02) | `expected_region_code`/daya = −1 di template | Isi saat commissioning (K-RFID-05): kandidat region **0x3F** (Javadoc, wajib dikonfirmasi di unit); daya ±15–16 dBm konduksi sebagai titik awal |
| Riset: session 0, TagFocus mati | Tidak diset/diverifikasi | AUD-MW-04 |
| Riset: kirim bacaan mentah, ERP yang memutuskan | Dikirim per bacaan tanpa ringkasan → volume | Ringkasan per jendela tanpa membuang bukti (AUD-MW-01) |
| Dokumen selalu dibuat sebelum barang lewat | Manifest dipilih manual operator | Auto-cocok dokumen (AUD-MW-15) |
| Muatan kecil 1–3 roll | Tidak dibedakan | Aturan per ukuran muatan setelah ada data uji |
| Target latensi M10 ≤ 3 s | Mustahil dengan tutup-karena-jeda 3 s | Tutup oleh sensor B |

## 5. Peta K-RFID-07: 13 usulan riset × kondisi kode

Legenda: ✅ ada · ◐ sebagian · ✗ belum. "Lama" = jalur gate KNHOST di `HEAD`; "Kubus" = agent 0.4.0 + patch 0.5.0.

| # | Usulan riset (ringkas) | Lama | Kubus | Catatan |
|---|---|---|---|---|
| 1 | Lintasan tidak diperpanjang bacaan ulang; durasi maks; tag diam tidak merah berulang | ✗ | ◐ | Ada maks 30 s & ID lintasan stabil; bacaan apa pun (termasuk tag diam) memperpanjang jeda |
| 2 | Cap keluar saat lintasan ditutup & terkonfirmasi | ✗ | ✅ | Klaim crossing hanya saat GREEN (tetapi lihat AUD-MW-08/09) |
| 3 | Status kandidat → terkonfirmasi/batal/perlu diperiksa (kuning) | ✗ | ◐ | Ada REVIEW, tetapi diperlakukan seperti RED terkunci; tidak ada batal/kuning |
| 4 | Ambang ke konfigurasi per gate | ✗ | ◐ | Profil versi per device (jeda, maks, validitas, batas); belum ada ambang RSSI/latar |
| 5 | Index, retensi, alat replay | ◐ | ◐ | Index ada; retensi belum; ekspor bukti ada, replay logika belum |
| 6 | Kontrak tertulis middleware↔ERP (siapa memfilter, jam siapa) | ✗ | ✅ | OpenAPI 2.0 + dokumen; tanggung jawab filter belum ditetapkan |
| 7 | Kontrak diperluas (photo-eye, boot/sequence, read_count, versi config, lintasan oleh sensor) | ✗ | ◐ | Versi config, gate, lintasan ✅; photo-eye/read_count/waktu reader ✗ |
| 8 | Peta antena & skor bukti per EPC (RSSI puncak, bentuk, jumlah antena) | ✗ | ◐ | Antena & RSSI disimpan per event, tidak dipakai keputusan |
| 9 | Daftar latar per gate | ✗ | ✗ | — |
| 10 | Pasangan gate IN↔OUT: interlock/arbitrasi | ✗ | ✗ | Kurang mendesak bila opsi C (pintu terpisah) — K-RFID-04 |
| 11 | Lintasan terikat dokumen, missing/extra, rescan handheld | ◐ | ◐ | Manifest + hitungan ✅; auto-cocok, daftar roll, rescan ✗; missing = RED |
| 12 | Status/latch untuk lampu via device key | ✗ | ✅ | `GET /device/gate-state` |
| 13 | Classifier aturan → ML dari data lokasi | ✗ | ✗ | Butuh data uji |

**Rekomendasi basis (untuk diputuskan pemilik):** gabungan, bukan pilih salah satu.

1. **Transport & bukti:** Kubus V2 (agent + `rfid_v2`) — sudah memenuhi #2, #6, #12 dan fondasi durabilitas yang tidak
   dimiliki jalur lama.
2. **Aturan bisnis:** `gate_evaluator` KNHOST (sudah dipanggil patch; mencakup P18 Makloon/Perbaikan).
3. **Lapisan lintasan baru** (belum ada di keduanya): photo-eye state machine & ringkasan bacaan di agent; daftar latar
   & skor bukti di agent+ERP; status kuning/batal & antrean periksa di ERP (#1, #3, #7–#9, #11).
4. **Jalur lama** `/api/rfid/ingest` dibekukan untuk device V2 (AUD-MW-09); tetap untuk handheld/kiosk sampai C72 pindah.

## 6. Status ERP-MW-01…12 dan paritas kontrak

| Gap (catatan-erp) | Status setelah patch 0.5.0 |
|---|---|
| ERP-MW-01 envelope v2, ACK per event | ✅ untuk konteks gate; konteks task/handheld ditolak |
| ERP-MW-02 metadata jalur session | ✗ jalur lama tidak diubah |
| ERP-MW-03 logical gate, lintasan stabil, live/backfill, close, validitas waktu | ✅ (lihat AUD-MW-02 untuk batas sensor) |
| ERP-MW-04 gate-state device-scoped, keputusan final, ack user | ✅ (ack tidak sesuai skema — AUD-MW-16) |
| ERP-MW-05 config/profil/versi + telemetry berlapis | ✅ (alert belum — AUD-MW-17) |
| ERP-MW-06…12 task C72, lokasi, printer CP30EN | ✗ di luar paket |

Operasi kontrak: API_01–06 diimplementasikan; API_07–20 (task, printer, lokasi) dan AUTH tetap memakai jalur yang ada;
6 endpoint `/ops/*` tidak tercantum di OpenAPI.

### Kesiapan kriteria UAT reader (paket spesifikasi `uat/UAT_TRACKER.csv`) — penilaian statis, semua tetap `not_run`

| Kriteria | Penilaian kode | Catatan |
|---|---|---|
| RD-01 tanpa PC | ✅ rancangan | APK on-device |
| RD-02 autostart/recovery | ◐ | `BootReceiver` + `START_STICKY`; belum diuji di unit |
| RD-03 / INT-05 dua logical gate per reader | ✗ sengaja | Fakta lapangan: gate IN/OUT terpisah → satu gate per reader cukup; kriteria perlu disesuaikan (keputusan) |
| RD-04 tag diam, lintasan ganda, re-entry | ✗ | Tag diam memperpanjang lintasan (AUD-MW-02) |
| RD-05 lost ACK / process death | ✅ rancangan | Outbox + event ID stabil (tes host) |
| RD-06 green hanya final/live/current/valid | ✅ | `DecisionPolicy`, `Safety.greenAllowed` |
| RD-07 red latch + ack basi | ◐ | Latch ada; ack tidak memeriksa `latch_id`/`decision_id`; latch berantai (AUD-MW-03) |
| RD-08 kebijakan manifest, missing/unknown | ◐ | Hanya `manifest_full` yang bisa hijau; missing = RED |
| RD-09 offline/backlog/respons basi | ✅ | Backfill tidak pernah hijau; tetapi backlog wajar pun basi (AUD-MW-01) |
| RD-10 outbox penuh/disk/reboot | ◐ | Stop capture sesuai policy; risiko deadlock lintasan penuh |
| RD-11 kesehatan radio vs ERP terpisah | ◐ | Telemetry memisahkan; tidak ada alert (AUD-MW-17) |
| RD-12 APK bertanda tangan, runbook | ✗ | Debug signing |
| INT-02 manifest SJ, scan tidak mem-post kiriman | ✅ | V2 tidak mengubah stok |
| INT-03 transfer/penerimaan | ◐ | Gate IN belum tersambung ke konfirmasi tiba (Tahap 2 dokumen keputusan) |
| INT-06 offline + lintasan live baru | ✅ | — |
| INT-09 revisi manifest/config, rotasi key | ◐ | Config versi ✅; rotasi key lewat provisioning ulang di lokasi |
| INT-12 tag rusak/hilang dengan movement aktif | ✗ | Belum ditangani di V2 |

## 7. Fakta SDK Chainway dari AAR (javap) dan uji meja K-RFID-03 yang diperluas

Kelas yang dipakai agent: `com.rscja.deviceapi.RFIDWithUHFA4` (pewarisan `…qcom.deviceapi.B` → `H`).

| Kemampuan | Ada di SDK | Dipakai agent |
|---|---|---|
| Inventory callback `IUHFInventoryCallback.callback(UHFTAGInfo)` / `readTagFromBuffer()` | ✅ | callback |
| `UHFTAGInfo`: `getEPC`, `getTid`, `getAnt()` (String), `getRssi()` (String), `getCount()`, `getTimestamp()` (long), `getPhase()`, `getFrequencyPoint()`, `getPc` | ✅ | EPC/TID/antena/RSSI saja |
| Gen2: `setGen2/getGen2` (`querySession`, `queryTarget`, `Q/startQ/minQ/maxQ`, `select*`, `linkFrequency`) | ✅ | ✗ |
| `setTagFocus/getTagFocus`, `setFastID`, `setFastInventoryMode`, `setRFLink` | ✅ | ✗ |
| `setFilter(bank, ptr, len, data)` / `setFilter(List<FilterEntity>)` | ✅ | ✗ |
| Region `setFrequencyMode/getFrequencyMode`, `setFreHop` | ✅ | verifikasi saja |
| Daya `setAntennaPower/getAntennaPower(AntennaEnum ANT1…ANT16)` | ✅ | verifikasi saja |
| Antena `getANT/setANT(List<AntennaState>)` | ✅ | ✅ |
| GPI `inputStatus()` → `GPIStateEntity(GPI1…GPI4, state)`; callback GPI | polling ✅; callback hanya di `RFIDWithUHFA4NetWork`/A8 | polling 100 ms |
| GPO `output1…4On/Off`, `outputOnAndOff(List<GPOEntity>)`, Wiegand | ✅ | output 1–4 |
| `buzzer()`, `led()`, `antLedSwitch` | ✅ | ✗ |

Fakta tambahan dari bytecode/Javadoc (label: **[AAR]** diperiksa di AAR · **[DOC]** Javadoc DeviceAPI v20251103 salinan
komunitas `github.com/Chainway-OSS/C66` — repo itu menyatakan bukan repo resmi Chainway · **[S]** ringkasan pihak
ketiga atas dokumen vendor):
- RSSI = `"-" + DecimalFormat("##0.00")` tanpa Locale, `"N/A"` di luar rentang **[AAR]** → AUD-MW-23.
- `getTimestamp()` = `System.currentTimeMillis()` saat parse **[AAR]** → bukan jam reader.
- Callback dipanggil dari thread internal SDK **[AAR]** → AUD-MW-24.
- Kode region **0x3F (63) = Indonesia 920–923 MHz**; 0x02 = China2 920–925 (jangan dipakai); −1 = gagal **[DOC]** →
  kandidat `expected_region_code` untuk K-RFID-05, wajib dikonfirmasi di unit.
- `getAntennaConnectState()` untuk deteksi antena putus **[DOC]**; `setRFLink` (profil PR-ASK/Gen2X) **[DOC]**;
  FastInventory di AAR ini memakai `FastInventoryEntity(cr)` (0 = mati) **[AAR]** — Monza R6-P bukan Gen2X → biarkan 0.
- `inputStatus()` = GPI1–GPI4 (Javadoc: input1, input2, OptoCoupler input3/4) **[DOC]**; tidak ada API work/idle/trigger di
  `RFIDWithUHFA4` (hanya kelas UR4/Urx) **[AAR]**.
- U300 punya **layanan UHF bawaan** (TCP 9160 raw, 9260 JSON, web 8080 dengan sandi bawaan, MQTT; mode
  Command/Trigger/Automatic) yang **memegang modul UHF** — harus dihentikan agar `init()` APK berhasil **[S]**. Input
  terminal: anoda optocoupler **maks 12 V / 50 mA**; output open-collector **[S]** → photo-eye 24 VDC wajib lewat relay/
  interface (sejalan dokumen keputusan §3).

Signature membuktikan metode **ada**, bukan bahwa firmware U300 mendukungnya. Daftar uji meja K-RFID-03 (diperluas):
1. Format `getAnt()` ("1" vs "01" vs "ANT1", 1-based?) — agent mensyaratkan persis "1"…"8"; salah format = capture
   berhenti di bacaan pertama.
2. Format `getRssi()` pada **locale perangkat yang dipakai** (koma?) dan frekuensi `"N/A"`.
3. Arti `getCount()`; apakah phase/frequency point terisi lewat `InventoryParameter` di U300.
4. Nilai bawaan `getGen2()` (session/target/Q) dan `getTagFocus()` setelah boot dan setelah aplikasi demo vendor
   dipakai; apakah `setGen2` persisten.
5. Apakah firmware menerima region 0x3F; versi firmware UHF (`getVersion`).
6. Rentang & langkah daya per antena (5–30 dBm?) dan readback-nya.
7. Laju callback nyata (bacaan/detik) dengan 3 antena, session 0, 50–100 tag — callback kosong vs callback yang menulis
   SQLite; ada bacaan hilang?
8. Pemetaan `inputStatus()`/`output1…4` ke terminal fisik; level idle input tanpa sensor; latensi `inputStatus()` saat
   inventory berjalan; polling berapa ms yang menangkap tepi sinar.
9. Apakah layanan UHF bawaan auto-start setelah reboot dan merebut modul sebelum `BootReceiver` agent; cara
   mematikannya permanen; ganti sandi web 8080 bila tetap aktif.

## 8. Riset: referensi open-source dan arsitektur yang direkomendasikan

Label sumber: **[S]** dibaca langsung · **[S\*]** hanya dari cuplikan mesin pencari (halaman tidak bisa dibuka dari sesi
ini — gs1.org, zebradevs.github.io, developer.impinj.com, wiki.transcends.co, patents.google.com tidak terjangkau) ·
**[R]** dari repo · **[I]** inferensi. Fakta [S\*] wajib dicek ke halaman asli sebelum dijadikan spesifikasi.
Riset ini **melengkapi** `riset/` (fisika RF, regulasi, studi industri, algoritma) dan tidak mengulangnya.

### 8.1 Referensi open-source dan standar

| Nama | URL | Lisensi / status | Yang bisa dipakai |
|---|---|---|---|
| Fosstrak (ALE 1.1, LLRP Commander, EPCIS) | https://github.com/Fosstrak/fosstrak | LGPL-2.1; arsip, commit terakhir 2015, README "DO NOT USE except for migration" [S] | XSD ALE 1.1 sebagai kamus model data; pola ECReports → aturan → event bisnis [S\*] |
| Rifidi Edge Server | https://github.com/TranscendsLLC/rifidi | GPLv2 [S\*]; tidak aktif sejak 2022 [S] | Lapisan adapter → CEP (Esper) → service → app; `ReadZoneMonitoringService` (datang/pergi dengan timeout), `StableSetService` [S\*] — konsep, bukan kode |
| LLRP Toolkit | https://github.com/ynezz/llrp-toolkit (mirror) | Apache-2.0 [S\*]; mandek ±2012 | `llrp-1x0-def.xml`: ROSpec, AISpec, TagReportData yang bisa dibaca mesin [S] |
| sllurp | https://github.com/sllurp/sllurp | GPL-3.0; aktif 2026 [S] | Simulator/alat uji untuk reader LLRP; **tidak** berlaku untuk U300 (LLRP tidak terdokumentasi di U300) [R] |
| OpenEPCIS | https://github.com/openepcis | Apache-2.0; sangat aktif [S] | Acuan event bisnis & eventID berbasis hash (`openepcis-event-hash-generator`) — sisi ERP, bukan edge |
| GS1 ALE 1.1.1 · GS1 LLRP 2.0 · GS1 EPCIS 2.0/CBV | gs1.org | standar | Semantik event cycle, trigger GPI, isi report, event bisnis shipping/receiving |
| CloudEvents | https://github.com/cloudevents/spec | Apache-2.0 [S] | `source + id` unik; pengiriman ulang boleh memakai id sama [S] |

**Tidak ditemukan** proyek open-source dock-door/portal yang matang dan terpelihara [S]; standar di atas dipakai sebagai
acuan desain, bukan pustaka.

### 8.2 Pola desain yang terbukti (yang relevan dengan temuan)

1. **Ringkasan per tag per jendela, bukan bacaan mentah** (→ AUD-MW-01). LLRP `TagReportData`: EPC, `AntennaID`,
   `PeakRSSI`, `ChannelIndex`, `FirstSeenTimestamp`/`LastSeenTimestamp` (UTC **dan** uptime monotonik), `TagSeenCount`
   [S]. ALE 1.1: report CURRENT/ADDITIONS/DELETIONS, `includeCount`, `firstSightingTime/lastSightingTime`; RSSI
   **tidak** distandarkan (ekstensi vendor) [S]. Zebra IoT Connector & Impinj Speedway Connect menyaring duplikat dalam
   jendela lalu mengirim batch [S\*].
2. **Photo-eye membuka/menutup siklus baca** (→ AUD-MW-02). LLRP `ROSpecStartTrigger = GPI`, `ROSpecStopTrigger =
   GPI_With_Timeout`, `AISpecStopTrigger = Upon_Seeing_No_More_New_Tags_For_Tms_Or_Timeout` [S]. ALE `ECBoundarySpec`
   (`startTrigger`, `stopTrigger`, `duration`, `stableSetInterval`; alasan selesai `TRIGGER|DURATION|STABLE_SET|…`) [S] —
   enum ini cocok untuk `open_reason/close_reason`. Zebra Portal berhenti bila tidak ada tag unik baru selama 3 s [S\*];
   Keonn mensyaratkan sinyal GPI tinggi ≥ 70 ms [S\*]. Paten Fujitsu memakai *pre-read offset* — jendela digeser ke
   belakang dari trigger, dengan syarat inventory berjalan terus [S\*].
   **Implikasi [I]:** jangan menyalakan RF hanya saat sinar terpotong; inventory menyala terus + jendela dihitung di
   software, supaya label depan (terbaca sebelum sinar) dan data latar saat gate kosong tetap ada.
3. **Tag latar** (→ usulan #9). ALE ADDITIONS/DELETIONS antar siklus dan timeout keberangkatan Rifidi [S/S\*]; daftar latar
   hanya bisa diisi bila RF menyala saat IDLE [I].
4. **Offline & "exactly-once" = at-least-once + penerima idempoten.** Kubus sudah benar di sini. Pembanding: Speedway
   Connect hanya menghapus batch setelah 200 OK [S\*]; Zebra retensi default 150.000 event, kirim ulang 500 TPS, hilang
   saat reboot [S\*]; AWS Greengrass `RejectNewData`/`OverwriteOldestData` [S\*]; deteksi celah dengan nomor urut per
   perangkat + ID sesi boot (Sparkplug `seq`/`bdSeq`) [S\*] — Kubus belum punya `seq`/`boot_id`.
5. **Kesehatan & konfigurasi.** Heartbeat berisi CPU/flash/NTP/suhu/uptime/GPIO (Zebra) [S\*]; LLRP `KeepaliveSpec` [S];
   Android: `SystemClock.elapsedRealtime()` monotonik, WorkManager untuk pekerjaan tertunda, Android Management API
   untuk mode kiosk/dedicated & update app [S\*].

### 8.3 Arsitektur referensi yang direkomendasikan untuk KNHOST [I]

**Agent di U300** (mempertahankan fondasi Kubus — Journal/Outbox, Api, DecisionPolicy, Provision):

```text
ReaderAdapter (inventory terus, session 0, cap waktu reader+monotonik)
   └─▶ RingBuffer RAM (±10 s bacaan mentah, untuk pre-buffer)
         ├─▶ BackgroundLearner (saat IDLE)            GpiAdapter (sinar A/B, cap waktu tiap tepi)
         └─▶ PassageStateMachine ◀────────────────────┘   (photo-eye utama, cadangan RF)
               └─▶ Aggregator (ringkasan EPC×antena per lintasan + bucket 250–500 ms)
                     └─▶ Journal/Outbox SQLite (seq per perangkat, boot_id, ID tetap) ─▶ Uplink (multi-batch, backoff)
ERP: ingest idempoten ─▶ evaluator lintasan terikat dokumen (gate_evaluator) ─▶ keputusan + antrean periksa
   ─▶ DecisionClient ─▶ IndicatorDriver: 4 GPO = hijau / kuning / merah / buzzer
```

Catatan: 4 GPO U300 habis terpakai untuk tiga lampu + buzzer, tanpa cadangan [R/I].

**Model data inti (kontrak 2.1):**
- `Envelope`: `device_id, boot_id, seq, event_id, sent_at, config_version, time_quality`.
- `GpiEdge`: `sensor (A|B), state, t_mono, t_wall`.
- `Passage`:
  - `passage_id, gate_id, open_reason (BEAM_A|RF_FALLBACK|MANUAL)`;
  - `close_reason (EXITED|REVERSED|ABORTED|TIMEOUT|SENSOR_FAULT|MANUAL)`;
  - cap waktu `A↓/B↓/A↑/B↑`, `pre_buffer_ms`, `tail_ms`, `mode`.
- `TagSummary` (lintasan × EPC × antena): `first_seen, last_seen, peak_rssi, t_peak, count, mean_rssi`,
  `buckets[{t_off, n, max_rssi}]`, `in_background`, `reads_before/after_window`.
- `Decision`: verdict yang ada + `reason_codes[]` (bukan satu kode — AUD-MW-03), hitungan matched/unexpected/weak,
  `doc_ref`, `expires_at`.

**State machine gate satu arah (A = mulut masuk, B = mulut keluar):**

```text
IDLE ──A↓ (≥ min_block)──▶ ENTERING        [window_start = t(A↓) − pre_buffer]
ENTERING ──B↓──▶ IN_PORTAL
ENTERING ──A↑ tanpa B↓ (≤ entry_timeout)──▶ CANCELLED            (mundur sebelum masuk)
IN_PORTAL ──A↑ lalu B↑──▶ EXITED ──tail_ms──▶ CLOSED
IN_PORTAL ──yang terakhir bebas adalah A──▶ REVERSED → CANCELLED  (REVIEW bila ada roll dokumen bersinyal kuat)
IN_PORTAL ──A↓ lagi saat B masih terhalang──▶ lintasan baru        (tag dengan t_peak di masa tumpang tindih → REVIEW)
semua state ──> max_passage──▶ TIMEOUT → REVIEW
sinar macet > stuck_ms tanpa aktivitas RF, atau B↓ sebelum A↓ ──▶ SENSOR_FAULT → mode cadangan RF (default REVIEW)
CLOSED → SUBMITTED → DECIDED → lampu ditahan sesuai validitas → IDLE
```

**Parameter awal (titik kalibrasi, bukan aturan):** 5 km/jam = 1,39 m/s → A↓ sampai B↑ ≈ (1,5 m + 1,8 m) / 1,39 ≈ 2,4 s
(≈ 5,9 s pada 2 km/jam).

| Parameter | Awal | Rentang | Basis |
|---|---|---|---|
| `pre_buffer_ms` | 3000 | 2000–5000 | jarak baca label depan 2,9–4,6 m ÷ 1,39 m/s [R]; pre-read offset [S\*] |
| `tail_ms` setelah B↑ | 1500 | 1000–3000 | Zebra 3 s [S\*]; dokumen keputusan 2–3 s [R] |
| `min_block_ms` (debounce) | 50 | 20–100 | Keonn ≥ 70 ms [S\*] |
| `entry_timeout` | 10 s | 5–15 s | [I] |
| `max_passage` | 30 s | 20–60 s | agent 30 s [R] |
| Stable interval cadangan RF | 3 s | 2–5 s | Zebra [S\*] |
| Bucket ringkasan | 250 ms | 250–500 ms | dokumen keputusan [R] |
| Batch | ≤ 500 ringkasan / ≤ 1 s | — | ERP `MAX_EVENTS` 500 [R] |
| Retensi offline | ≥ 24 jam; penuh → tolak data baru + alarm | — | Zebra/Azure/Greengrass [S\*] |
| Polling GPI | ≤ 20 ms bila tidak ada callback | — | resolusi tepi; agent kini 100 ms [R] |

**Keluaran keputusan:**
- **HIJAU** — `close_reason = EXITED`, sensor sehat, semua EPC kuat non-latar milik dokumen aktif dan belum pernah
  lewat. Roll dokumen yang belum lewat dinilai **saat dokumen ditutup**, bukan per lintasan (AUD-MW-22).
- **MERAH** — EPC kuat yang melanggar: bukan milik dokumen, tujuan salah, sudah keluar, karantina, EPC asing.
- **KUNING / perlu diperiksa** — REVERSED membawa roll dokumen; TIMEOUT; SENSOR_FAULT atau cadangan RF (sampai
  terkalibrasi); dua muatan tumpang tindih; hanya kandidat lemah; backfill atau waktu tidak sinkron; sinar terpotong
  tetapi 0 tag → "ulangi lintasan".
- **UNKNOWN / TAHAN** — offline atau keputusan kedaluwarsa (perilaku agent saat ini).
- **Lintasan kosong** (orang/forklift kosong) — **tanpa transaksi, tanpa alarm**.

Koreksi atas satu catatan riset: di kode saat ini REVIEW **tidak** padam. Server mengunci semua non-hijau
(`latched = verdict != 'GREEN'`), sehingga agent menyalakan **merah terkunci**. Lampu kuning memang tidak ada.

### 8.4 Referensi open-source khusus Chainway

Tidak ditemukan organisasi GitHub resmi Chainway; chainway.net tidak terjangkau dari sesi ini. Lisensi menentukan apa
yang boleh diadaptasi: **BSD/MIT boleh diadaptasi**, repo tanpa lisensi **hanya ide**, **GPL jangan disalin** ke kode
KNHOST/Kubus.

| Repo | Lisensi | Perangkat | Pola | Pelajaran |
|---|---|---|---|---|
| [Hamadullah09/WarehouseManagementSystem](https://github.com/Hamadullah09/WarehouseManagementSystem) (`docs/U300-INTEGRATION.md`) | tidak ada | **U300**; APK `RFIDWithUHFA4` + bridge TCP 9160 | callback; dedup EPC per sesi; GPI dipoll 150 ms dengan sampel pertama sebagai baseline; drain 750 ms setelah stop; REST dengan `sessionKey` idempoten | Paling dekat dengan kasus KNHOST (gate gudang denim, validasi manifest penuh); merangkum panduan integrasi fixed reader Chainway |
| [RFID-Devs/rfid_flutter_plugin](https://github.com/RFID-Devs/rfid_flutter_plugin) | BSD-3-Clause | URA4 (`RFIDWithUHFA4`) | callback | Cakupan API setelan paling lengkap (Gen2, FastInventory, TagFocus, FastID, RFLink, daya per antena, `getAntennaConnectState`, enum region) — acuan memetakan profil commissioning |
| [voidwalker-sagewire/tag-reaper-sentinel-next](https://github.com/voidwalker-sagewire/tag-reaper-sentinel-next) | GPL-3.0 | C316H 4-port, AAR 20251103 sama | agregasi per EPC & antena (first/last, count, RSSI maks); daya diset lalu dibaca balik | Pola agregasi benar; jangan disalin (GPL); kelemahan: UI & simpan per bacaan |
| [ArnoldMedinaBenavente/URA4-APP](https://github.com/ArnoldMedinaBenavente/URA4-APP) | tidak ada | URA4 | polling `readTagFromBuffer` + HTTP per tag | **Anti-pola** (sleep per tag, satu request per tag) |
| Turunan demo "UHF-A4" (mis. [lhock17/UHF-A4](https://github.com/lhock17/UHF-A4)) | tidak ada | URA4 | busy-loop `readTagFromBuffer`; GPI dipoll 1 s; contoh Wiegand | Demo vendor, bukan pola produksi |
| Plugin C72 (Flutter/React Native/Xamarin; MIT/BSD) | MIT/BSD | handheld | thread + HashSet | Relevan untuk modul C72 nanti, bukan reader |

Catatan: `readTagFromBuffer` sudah **deprecated** ("Use setInventoryCallback instead") — Kubus sudah benar memakai
callback. Tidak ditemukan integrasi MQTT/WebSocket open-source untuk U300 maupun angka bacaan/detik terukur.

**Alternatif arsitektur yang perlu dinilai [I]:** membiarkan layanan UHF bawaan U300 memegang modul (mode Trigger
firmware + callback GPI lewat kelas klien `RFIDWithUHFA4Host`/`…NetWork`) dan agent menjadi klien layanan itu. Untung:
callback GPI & trigger firmware. Rugi: bergantung pada protokol JSON 9260/MQTT yang spesifikasinya tidak publik dan
belum diuji. Rekomendasi: tetap APK pemegang modul (rancangan Kubus) kecuali uji meja menunjukkan polling GPI tidak
memadai.

### 8.5 Yang harus diuji di lokasi (tambahan atas §7)
- Kapan label depan pertama terbaca sebelum A↓ (menentukan `pre_buffer`), ekor setelah B↑, distribusi kecepatan,
  jarak antar stacker beriringan.
- Photo-eye: celah antar kaki stacker/garpu yang membuat sinar berkedip (satu lintasan pecah dua), orang lewat,
  forklift kosong, cahaya matahari, level input U300 (optocoupler/relay).
- Ketahanan: cabut jaringan di tengah lintasan, reboot saat lintasan berjalan, lompatan jam, urutan replay, kapasitas
  retensi terhadap batas agent (DB 256 MiB, sisa disk ≥ 64 MiB).
- Konflik IN/OUT bila gate berdampingan (opsi A) — interlock/arbitrasi (K-RFID-04).
- Inventory menyala 24/7: suhu dan stabilitas U300.

## 9. Urutan kerja yang disarankan (untuk development lokal)

1. **Putuskan** — pemilik: kebijakan alarm merah vs kuning (AUD-MW-03), penilaian per lintasan vs sesi dokumen
   akumulatif untuk muat multi-trip (AUD-MW-22), dan basis pengembangan (§5).
2. **Uji meja K-RFID-03** dengan daftar §7 — sebelum menulis ringkasan/skor.
3. **Kontrak 2.1** (ringkasan bacaan, peristiwa photo-eye, batal, waktu reader, daftar alasan) — satu revisi untuk
   agent, ERP, fixture, dan UAT sekaligus.
4. **Agent 0.5:** state machine photo-eye + cadangan RF, callback ringan + writer batch, ringkasan per jendela dengan
   cap waktu monotonik, parse RSSI tahan locale, multi-batch, kode error, setelan Gen2/TagFocus di profil, perbaikan
   query antrean, sinkron jam, matikan layanan UHF bawaan U300.
5. **ERP:** terapkan patch 0.5.0 (merge manual frontend), lalu perbaikan AUD-MW-03/07/08/09/15/16/17; tes regresi gate lama;
   uji beban.
6. **Panel:** antrean periksa dengan bukti per roll, istilah Indonesia, alert kesehatan.
7. **Pilot** dengan metrik M1–M11 (K-RFID-08).
