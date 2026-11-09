# B2b · Audit statis C — Logika alur dokumen RFID (tag · cetak · gate V2 · gate lama · handheld)

> **Lampiran paket audit B2b** (tag, cetak, gate V2, gate lama, handheld) — tabel transisi status dari KODE (`berkas:baris`, CAS, efek, pembalikan,
> idempotensi, pagar) + kandidat anomali statik + resep uji. Disusun dengan pembacaan kode di HEAD `35506d7`
> (`integrasi-prep3`). **Hasil uji runtime** (yang terbukti / dibantah / belum dijalankan) ada di laporan utama
> [`B2b-ALUR-KELUAR-POTONG-RFID.md`](B2b-ALUR-KELUAR-POTONG-RFID.md) §3 & §8 — ID kandidat di sini (ANOM-, POT-, SMP-, TRF-,
> MKO-, REP-, PRT-, T-, G-, L-, P-, H-) dipetakan ke ID temuan resmi (FLW-OUT-, STM-OUT-, CUT-, RFID-) di sana.
> Sandi akun demo sengaja tidak ditulis (lihat `AGENTS.md`). Catatan "belum dijalankan" di bagian resep = status saat
> lampiran disusun, sebelum uji runtime B2b.

Audit BACA-SAJA di HEAD `35506d7` (worktree `agent-a300a69678b4a7b03`). Tidak ada berkas repo yang diubah, tidak ada
docker/skrip penulis DB yang dijalankan. Semua rujukan `berkas:baris` relatif ke `backend/` kecuali disebut lain.
Acuan: `docs/rfid/KEPUTUSAN_GATE_RFID.md` (K-RFID-01…11, K-GDG-01…11, K-OPN-05), `docs/rfid/hasil/PREP-D1/D2/F/G`.

Susunan berkas:
* **§0** jawaban langsung pertanyaan brief + ringkasan anomali teratas;
* **§1** `rfid_tags` (siklus hidup tag lintas jalur) · **§3** gate V2 · **§4** gate lama/kios — disusun di sini;
* **§2** `rfid_print_jobs`/item/`rfid_verify_sessions` (bagian **P-xx**) dan **§5** handheld (bagian **H-xx**) —
  dilampirkan utuh di akhir berkas (disusun paralel, sumber kode yang sama, HEAD sama).
* Kandidat anomali: **T-xx** (tag), **G-xx** (gate V2), **L-xx** (gate lama), **P-xx** (cetak), **H-xx** (handheld).

Sudah dicatat paket lain — hanya dirujuk: B3a SCP-1 (pagar `/rfid/lookup`), SSOT-6 (V1 & V2 hidup), STK-14; B3b INP-14,
FRM-12/13, FRM-21, LST-09; `docs/rfid/AUDIT_MIDDLEWARE_RFID_2026-11-08.md` AUD-MW-xx.

---

## §0. Jawaban langsung & ringkasan

| Pertanyaan brief | Jawaban dari kode |
|---|---|
| Keunikan EPC aktif dijaga? | **Sebagian.** Indeks unik parsial `uniq_live_epc` (status `active`/`pending_print`) — `rfid_service.py:469-475` — dibuat **hanya di bootstrap dan hanya bila data bersih** (`bootstrap.py:1656-1661`, benturan cuma di-log). Di atasnya: cek-lalu-sisip `rfid_service.py:110` + tangkap `DuplicateKeyError` `:123-127`. Tidak ada guardrail yang memeriksa indeks itu ada (T-03). |
| EPC pensiun tidak pernah dipakai ulang? | **Tidak dijamin.** Hanya `allocate_epc` (cetak) memeriksa SEMUA status (`rfid_print_service.py:155-161`). `encode_tag` menerima `epc` bebas & hanya menolak EPC hidup (`rfid_service.py:107-111`, `POST /api/rfid/tags/encode` `routers/rfid.py:330-338`); Daftar Awal mode `read` dan `_new_system_epc` / C72 `new_epc` cek EPC hidup saja (T-01, H-05). |
| Roll ber-tag aktif dua kali? | Dijaga di tingkat **roll** (CAS `rfid_tag_id ∈ [None,""]` `rfid_service.py:129-135`); **tidak ada** indeks unik `rfid_tags.roll_id` hidup. Jalur sinkron (`roll_service.py:1735`, `:2024`, `transfer_receipt_service.py:221`) memakai `update_many` → kode sendiri mengantisipasi >1 tag per roll. Tidak ditemukan jalur pasti yang membuat dua tag hidup untuk satu roll; job cetak kedua untuk roll ber-tag hidup = EPC SAMA di dua chip (P-04, butir pemilik P3 PREP-F). |
| Tag ke roll yang sudah keluar/consumed? | `encode_tag` menolak status non-fisik (`rfid_service.py:102-103`) tetapi `PHYSICAL_STATUSES` memuat `in_transit_sales/in_transit_transfer/allocated/receiving` (`:22-23`) → roll di truk boleh di-tag (T-09). Jalur cetak/aktivasi tidak cek status roll (P-05); C72 (H-13). |
| Simulator V2 hanya bertransaksi bila `wms.rfid_simulation` menyala untuk PT dokumen? | **Untuk stok: ya** — `gate_txn_service.precheck` menurunkan mode ke `evidence` (`:148-149`, `_simulation_allowed` `:122-135` cek SEMUA dokumen; default setelan `False` `config_catalog_core.py:124`), jalur ulang `_apply` juga (`:263-266`). **Untuk kontrol: tidak** — klaim crossing, bukti `gate_exits[]/gate_arrivals[]` di dokumen bisnis, jejak sesi dokumen, dan **kunci gate perangkat nyata** tetap ditulis (G-01, G-02). Data uji menyalakan setelan untuk KSC, KANDA, CST (`backend/scripts/seed_uat_retur_kn.py:56`) → di PT itu simulator memang memindah stok. |
| Jalur lama masih menulis `gate_exit`/stok? | **`gate_exit` ya, stok tidak.** `/api/rfid/ingest` (perangkat `protocol` ≠ `v2`) dan `POST /api/rfid/gate/simulate` (`wms.scan`) → `stamp_exit` `inventory_rolls.gate_exit` (`rfid_ingest_service.py:230-231`, `gate_evaluator.py:169-174`) + insiden + notifikasi; tidak ada `$inc` stok/dokumen. `gate_exit` dibaca evaluator V2 → REPLAY_EXIT merah (G-03). |
| Sesi dokumen yang tidak tertutup? | MKO manual saja; transfer batal sesudah kirim, transfer selesai lewat jalur status, perbaikan batal, SJ tanpa keberangkatan Logistik → tidak pernah ditutup (G-04). |

**Jumlah transisi terdokumentasi:** §1 22 baris (9 sama dengan §2/§5) · §3 40 · §4 8 · §2 38 · §5 37 →
**145 baris, ±136 transisi unik**.

**Kandidat anomali teratas (gabungan semua bagian, urut dampak):**
1. **G-01** simulator V2 dengan Mode simulasi MATI tetap memasang klaim crossing/bukti/sesi nyata → lintasan nyata berikutnya RED `REPLAY_*`, `ROLLS_MISSING` hilang — `rfid_v2_service.py:233-241`, `rfid_v2_sessions.py:67-71`, `gate_txn_service.py:148-149, 272-279` [kode]
2. **G-02** lintasan simulator RED mengunci gate perangkat nyata tanpa notifikasi — `rfid_v2_service.py:251-253`, `gate_review_service.py:202-203` [kode]
3. **G-03** simulator gate lama (`wms.scan`) menulis `inventory_rolls.gate_exit` + insiden nyata, dibaca V2 → RED `REPLAY_EXIT` — `routers/rfid.py:446-455`, `rfid_ingest_service.py:230-231`, `gate_evaluator.py:147-149` [kode]
4. **H-01** key handheld diterima `/api/rfid/ingest` tanpa sesi pengguna → pindai ke sesi verifikasi/cek muat lintas PT — `routers/rfid.py:605-613`, `rfid_ingest_service.py:136, 308-320` [kode]
5. **T-01/T-02** EPC pensiun dapat dipakai ulang + pencarian EPC tanpa saring status — `rfid_service.py:107-111`, `routers/rfid.py:114, 330-338`, `sample_sale_service.py:295`, `makloon_issue_rolls.py:93` [kode]
6. **P-04** job cetak kedua memakai EPC SAMA, resolusi job lama memensiunkan tag job baru — `rfid_print_service.py:245, 916-919, 485` [kode]
7. **P-01/P-02** bukti baca chip bisa diketik (`source:manual`) dan `mark-printed` (`wms:scan`) mengaktifkan tag tanpa bukti — `routers/rfid.py:539-547`, `rfid_print_service.py:542-572, 809-815` [kode]
8. **G-04** sesi dokumen gate tak pernah ditutup (MKO, batal transfer/perbaikan, transfer selesai via status, SJ tanpa Logistik) — `routers/transfers.py:667-800`, `repair_order_service.py:219-238`, `logistics_service.py:592-593` [kode]
9. **G-07** antrean periksa/sesi/notifikasi bocor lintas PT & gedung (kasus tanpa dokumen, ringkasan, `devices/{id}/sessions`, notifikasi tanpa entity) — `routers/rfid_v2_review.py:23-31, 79-85`, `routers/rfid_v2_ops.py:55-60`, `gate_review_service.py:214-217` [kode]
10. **H-02** `once()` handheld mengambil alih `processing` basi tanpa CAS → eksekusi batch ganda/hasil tersimpan salah — `handheld_sync.py:71-75, 88-90, 97` [mekanisme kode; dampak runtime]
11. **G-05** wajib cek muat dilepas cukup dari konfigurasi pasangan gate, bukan reader hidup — `loading_check_service.py:304-308`, `gate_txn_service.py:75-81` [kode]
12. **G-06** koreksi/tolak klaim tidak membalik tiba PA/terima transfer & bukti dokumen — `gate_review_actions.py:184-210, 325-377` [kode]
13. **H-07** batch handheld `simulated` tanpa pagar setelan; penutupan sesi gate menerima cek muat `simulated` sebagai bukti — `handheld_sync.py:131, 316`, `gate_txn_service.py:400` [kode]
14. **T-04** encode/auto-encode membuat tag `active` tanpa tulis chip (K-OPN-05) — `rfid_service.py:93, 139-148` [kode]
15. **H-03** niat tulis tag C72 tak pernah kedaluwarsa → roll terkunci — `handheld_tags.py:98-101, 112, 123-129` [kode]

---

## §1. `rfid_tags` — siklus hidup tag (semua jalur penulis)

Status: `active` · `pending_print` · `retired` (+ flag `simulated`, `written_via`, `replaced_by_tag_id/replaces_tag_id`).
`LIVE_TAG_STATUSES = ("active","pending_print")` (`rfid_service.py:26`). Penulis dicari dengan grep semua operasi
`rfid_tags.*` (skrip `b3a_db_writers` melewatkan penulis lewat variabel/`update_many`).

| # | dari → ke | pemicu (endpoint + fungsi, berkas:baris) | penjaga/CAS | efek | dibalik/kompensasi? | idempoten? | pagar PT/lokasi/perangkat |
|---|---|---|---|---|---|---|---|
| TG1 | ∅ → `active` (EPC manual/sistem) | `POST /api/rfid/tags/encode` `routers/rfid.py:330-338` (`EncodePayload{roll_id, epc?}` :24-26) → `encode_tag` `rfid_service.py:92-136` | roll ∈ PT (:98-99), roll tanpa tag (:100-101), status fisik & panjang>0 (:102-103), EPC kanonik (:105-109), EPC **hidup** unik (:110 + indeks parsial :123-127), CAS roll `rfid_tag_id∈[None,""]` (:129-131) | roll `rfid_tag_id`, `tracking_mode=rfid`; audit `rfid_tag_encoded`; **tanpa** tulis chip, **tanpa** `rfid_tag_events` | kalah CAS → tag baru dihapus (:132-135) | tidak (ulang → 400 "sudah memiliki tag") | PT ✔ (`resolve_scope_ids`); **lokasi ✘** (roll dibaca langsung); `wms.scan` |
| TG2 | ∅ → `active` (massal ≤200) | `POST /api/rfid/tags/auto-encode` `routers/rfid.py:341-348` → `auto_encode` `rfid_service.py:139-148` | sama TG1 per roll; galat per roll ditelan (:146-147) | sama TG1, EPC `generate_epc` (:29-31) | – | tidak | PT ✔; `warehouse_id` opsional → semua gudang PT; lokasi ✘ |
| TG3 | ∅ → `pending_print` | job cetak / ganti tag / cetak ulang (§2 T1) `rfid_print_service.py:253-255` | EPC `allocate_epc` (cek semua status :159) | – | rollback hapus (:211-217) | – | §2 |
| TG4 | `pending_print` → ∅ | `_rollback_new_tags` `rfid_print_service.py:211-217` | filter status | roll dilepas | – | ya | – |
| TG5 | `pending_print` → `active` | efek item cetak `_item_effects` `rfid_print_service.py:478-496` | `update_many status=pending_print` (:485-487), tanpa cek roll | journey `tag_printed`, event `activated` (ditulis walau no-op, P-11) | – | ya | perangkat printer gudang |
| TG6 | `pending_print` → `active` (Daftar Awal) | `mark_written` `initial_registration_lines.py:306-319` (web mark-written / C72 `lines[].written=true`) | baris sesi `tag_state=pending_write` (:309-310); tag `pending_print` (:317) | `activated_at/by`; baris `tag_state=written`; **tanpa bukti baca ulang** (T-08), tanpa event | – | ya | sesi; tanpa cek status roll |
| TG7 | ∅ → `active`/`pending_print` (Daftar Awal disetujui) | `apply_group` → `link_tag` `initial_registration_approve.py:51-74` → `encode_tag(epc=baris)` | EPC hidup roll lain di luar cakupan → pengecualian (:63-66); status dari `tag_state` (:68) | roll `rfid_tag_id`, `rfid_epc` (:73) | galat → `ok:False` (pengecualian) | ya (tag sama dikembalikan :58-61) | owner baris |
| TG8 | `active` → `retired` (Daftar Awal) | `_retire` `initial_registration_approve.py:35-48` (tag lama roll :62 / benturan roll lama :67) | `retire_tag` (CAS active) — **409 roll bergerak ditelan** (:41-44) | `retire_reason` ditulis **walau tidak pensiun** (:48) | – | ya | – |
| TG9 | `pending_print` → `retired` (Daftar Awal) | `_retire` :45-47 | filter status | roll `rfid_tag_id=None` (`tracking_mode` tidak direset) | – | ya | – |
| TG10 | `active` → `retired` (manual) | `DELETE /api/rfid/tags/{tag_id}` `routers/rfid.py:351-358` → `retire_tag` `rfid_service.py:151-178` | PT (:155-156), tolak roll `active_movement` (:157-165), CAS `status=active` (:167-169) | roll `rfid_tag_id=None`, `tracking_mode=barcode`, `$unset journey.verified_tag_id` (:173-177); audit; **tanpa alasan/event/cek item job terbuka** (T-07) | – | 2× → 409 | PT ✔; lokasi ✘; `wms.scan` |
| TG11 | `active`/`pending_print` → `retired` | resolve item / replace-tag (§2 T4) `_retire_live_tag` `rfid_print_service.py:824-840` | CAS hidup | event `retired` | replace: T5 | ya | §2 |
| TG12 | `retired` → status lama | kompensasi `replace_tag` `rfid_print_service.py:1009-1019` | `status=retired` | `retire_reverted` | – | ya | – |
| TG13 | `active` → `retired` (C72) | `confirm_write` `handheld_tags.py:155` → `retire_tag` | §5 A5 | **tanpa event/alasan** (H-05) | `:163-169` | once | §5 |
| TG14 | `pending_print` → `retired` (C72) | `handheld_tags.py:156-160` | filter status; **tanpa cek job aktif** (H-04) | roll dilepas | tidak | – | §5 |
| TG15 | ∅ → `active` (C72, EPC tertulis & terbaca ulang) | `handheld_tags.py:162,171-175` → `encode_tag` | baca ulang = EPC niat (:144-146) | `written_via/written_by_device_id/write_id`, `journey.verified_tag_id` | – | once | §5 |
| TG16 | `retired` → `active` (C72 kompensasi) | `handheld_tags.py:163-169` | – | roll ditautkan ulang | – | – | – |
| TG17 | `active` → `retired` (roll penerimaan dibatalkan) | `undo_receiving_roll` → `retire_roll_tag` `receiving_roll_service.py:393-397, 400-406` | filter `status=active` saja (tag `pending_print` tertinggal — P-05/T-06) | `retire_reason=roll_dibatalkan` | – | ya | – |
| TG18 | hidup → `retired` (roll tidak ada) | `retire_orphan_tags` `rfid_service.py:479-487` (hanya saat bootstrap `bootstrap.py:1661`) | filter hidup | `retire_reason=roll_tidak_ada` | – | ya | global |
| TG19 | ∅ → `active` + `simulated:true` | `POST /api/outbound/so/{order_id}/loading-check/simulate-tags` `routers/outbound_picking.py:595-609` (`wms.update`) → `simulate_tags` `loading_check_service.py:195-220` | `simulation_on(order)` (:197-200) | tag lama non-hidup dilepas dari roll (:214-216) | – | ya (roll ber-tag hidup dilewati) | PT SO |
| TG20 | EPC berpemisah → kanonik | `migrate_epc_canonical` `rfid_service.py:434-476` (bootstrap) | benturan tidak dimigrasi (:447-449) | ikut ubah `rfid_reads`, `rfid_verify_sessions`, `rfid_print_jobs` | – | ya | global |
| TG21 | `active`: `owner_entity_id`/`warehouse_id` ikut roll | `roll_service.py:1735-1736` (ganti PT), `:2024-2025` (transfer), `putaway_order_service.py:423-424`, `transfer_receipt_service.py:221-222` | filter `status=active` saja → tag `pending_print` **tidak** ikut (T-11) | – | – | ya | – |
| TG22 | `last_seen_*` | `_record_read` `rfid_service.py:314-318`; ingest lama `rfid_ingest_service.py:215-218` | – | lokasi terakhir | – | – | lihat L-xx/FRM-13 |

`rfid_tag_events` (append-only, kunci idempoten `key` sparse-unik dibuat lazy `rfid_print_service.py:63-76`) hanya
ditulis jalur cetak PREP-F: `encoded` :268, `activated` :494, `retired` :838, `text_reprint_requested` :972,
`retire_reverted` :1017, `replacement_issued` :1027. TG1/2/6-10/13-19 tidak menulis riwayat (T-05).

---

## §3. Gate V2 (U300 protokol `v2`)

Ringkas alur: reader (`X-Device-Key`, tipe `gate`/`fixed_reader` `routers/rfid_v2.py:68-81`) →
`POST /api/rfid/v2/events` (bukti) → `POST /api/rfid/v2/passages/{id}/close` (`Idempotency-Key` wajib) →
`rfid_v2_service.close` (`:192-279`): kebijakan (`rfid_v2_policy.decide` `:171-304`) → precheck mode gedung
(`gate_txn_service.precheck` `:138-164`) → klaim crossing (`rfid_v2_sessions.insert_claims` `:29-64`) → kunci gate
(RED) → keputusan disimpan → `post_close` transaksi + antrean periksa. Verdict: `GREEN|REVIEW|RED|CANCELLED`
(`rfid_v2_policy.py:289-300`); **`INFO` hanya tingkat alasan** (mis. `PREVIOUS_PASSAGE`, `HANDHELD_MODE`,
`GATE_NOT_PAIRED`, `QUANTITY_MODE`, `SIMULATED_EVIDENCE`), tidak pernah verdict.

### 3.1 `rfid_v2_passages`
| # | dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|---|
| PS1 | ∅ → `OPEN` | `POST /api/rfid/v2/events` `routers/rfid_v2.py:102-105` → `rfid_v2_ingest.events` `:143-190` / close tanpa event → `rfid_v2_core.passage` `:150-169` | `$setOnInsert` (seed `simulated`, `acknowledged:false`, snapshot binding manual bila TTL hidup :154-156); konteks beda → 409 `PASSAGE_CONTEXT_CHANGED` (:167-168); profil versi (`config` :68-79, `DEVICE_MOVED`) | – | – | ya | device key; gudang = gudang perangkat |
| PS2 | `OPEN` → `OPEN` (bukti) | `_store` `rfid_v2_ingest.py:38-104`; id event global per perangkat `_claim_event_ids` :107-121 | CAS `state=OPEN` + sisa kapasitas & byte (:67-69); isi beda id sama → 409 `EVENT_ID_CONFLICT` (:58-59, :120-121); penuh → `rfid_v2_overflow` + `overflow.<kind>` (:86-104) | koleksi `rfid_v2_events/summaries/edges`; `v2_transport` seq (:124-140) | kompensasi hitungan bila duplikat balapan (:80-82) | ya (`duplicate`) | – |
| PS3 | `OPEN` → `CLOSING` | `POST /api/rfid/v2/passages/{id}/close` `routers/rfid_v2.py:119-122` → `close` `rfid_v2_service.py:192-217` | key ≤160 wajib (:194-195); hitungan bukti = close (:206-207, 503 `EVIDENCE_PENDING`); CAS `{state:OPEN, counts, overflow}` (:209-212); key/isi beda → 409 `CLOSE_CONFLICT` (:199-201, :216-217) | `close_hash/close_key/close_body` | – | ya | – |
| PS4 | `CLOSING` → `FINAL` + `decision` | `close` :221-275 | CAS `decision: None` (:273); bukti tersimpan lengkap (:221-223) | verdict + `reason_codes/reasons/counts/sources`; klaim (3.2); kunci (3.6) bila RED (:251-253); jejak sesi (`record_passage` :268-272); `gate_txn_input`, `gate_txn_state:pending` (:274-275); lalu `post_close` (:278) | – | ya: keputusan tersimpan dikembalikan (:202-204, :218-220) — **tetapi** perhitungan ulang di jendela crash (G-10) | – |
| PS5 | GREEN → REVIEW (sebelum final) | `_gate_txn_precheck` `rfid_v2_service.py:282-293` (`TXN_CHECK_FAILED`); `precheck` `gate_txn_service.py:159-164` (`AREA_FROZEN`) | – | barang jalan, tanpa transaksi dokumen beku | – | – | – |
| PS6 | GREEN/REVIEW → RED (sebelum final) | klaim bentrok lintasan lain `rfid_v2_service.py:236-241` (`REPLAY_CROSSING`) | insert_claims semua-atau-tidak | kunci gate | – | – | – |
| PS7 | `FINAL`: `acknowledged false→true` | `POST /api/rfid/v2/passages/{id}/acknowledge` `routers/rfid_v2.py:211-227` (`wms.scan`; RED → `wms.approve` :223-225) → `rfid_v2_latch.acknowledge_passage` `:84-106` | catatan ≥5 (:78-81); `decision_id`/`latch_id` basi → 409 (:91-97); CAS `state=FINAL, acknowledged=false` (:98-100) | kunci gate dilepas bila lintasan anggota (:103) — **seluruh** kunci; **tanpa `audit()`** di router (G-16) | – | 2× → 409 | sesi pengguna + entitas dokumen (:220-222) |
| PS8 | `gate_txn_state pending → done/error` | `post_close` `gate_txn_service.py:327-347`; ulang `force` dari antrean (`retry` `gate_review_actions.py:291-301`) | `done` & bukan force → keluar (:333-334) | transaksi (3.4), kasus (3.5) | – | ya (buku 3.4) | – |
| PS9 | `latch_release` diset | `rfid_v2_latch.release` `:60-75` | – | – | – | – | – |

### 3.2 Klaim crossing `rfid_v2_crossings` (`_id = digest(source_type, source_id, arah, roll)`)
| # | dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|---|
| CL1 | ∅ → klaim (`passage`=lintasan) | `close` :233-241 → `insert_claims` `rfid_v2_sessions.py:29-64` bila `claimable` (GREEN/REVIEW ber-roll cocok, tanpa alasan `NO_CLAIM` `rfid_v2_policy.py:31, :301`) | cek semua `$in` dulu (:47-50); `insert_many` + duplikat | meta `device_id, gate_id, review, simulated` (:234-235) — **klaim simulator ikut nyata** (G-01) | kalah balapan → hapus milik sendiri (:56-61) | ya (milik lintasan sama :51-52) | – |
| CL2 | ∅ → klaim `review:{kasus}` | terima di antrean `_claim_passed` `gate_review_actions.py:71-80` | `DuplicateKeyError` = sudah lewat | sesi menghitung lewat; lintasan nyata berikutnya → RED (desain D2 §8.6, G-15) | – | ya | `wms.approve` |
| CL3 | klaim → ∅ (lepas / tolak) | `POST /api/rfid/v2/ops/crossings/release` `routers/rfid_v2_review.py:181-192` / tolak roll `reject` `gate_review_actions.py:184-210` → `release_claim` :325-344 | alasan ≥10 (≥5 dari tolak); CAS `passage` lama (:339-341); tolak hanya klaim lintasan kasus (:337-338) | `rfid_v2_claim_corrections` (:316-322) + audit — **transaksi/bukti tidak dibalik** (G-06) | – | ulang → 404/409 | entitas dokumen; `wms.approve` |
| CL4 | klaim A → klaim B | `POST /api/rfid/v2/ops/crossings/move` `rfid_v2_review.py:195-212` → `move_claim` `gate_review_actions.py:347-377` | dokumen tujuan aktif & memuat roll (:353-358); sisip baru (dup → 409), hapus lama CAS | koreksi `move`; dokumen tujuan **tanpa** bukti/transaksi | kompensasi hapus baru (:373) | 409 bila ulang | entitas kedua dokumen |

Pembaca klaim: `gate_evaluator.evaluate` (REPLAY_EXIT `gate_evaluator.py:111-120`, juga jalur lama/kios),
`sessions.passed_map` (`:67-71`, tanpa saring `simulated`), `_carryover` (`rfid_v2_policy.py:144-149`),
`_done_elsewhere` (`gate_review_service.py:226-229`), kios (`rfid_v2_kiosk.py:23`).

### 3.3 Sesi dokumen `rfid_v2_doc_sessions` (K-RFID-10)
| # | dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|---|
| DS1 | ∅ → `open` | `record_passage` `rfid_v2_sessions.py:84-94` (upsert, setiap lintasan ber-dokumen termasuk RED) / upsert di `close_session` :168-170 | – | `source_ref, direction, warehouse_id, roll_ids` | – | ya | – |
| DS2 | `open` → `open` (+lintasan) | `record_passage` :95-100 | `passage_ids $ne pid` | `passages[]` ≤500, `roll_ids` ditimpa isi dokumen terkini | – | ya per lintasan | – |
| DS3 | `open` → `closed` (`close.verdict` GREEN \| REVIEW `ROLLS_MISSING`) | `close_document_session` `gate_txn_service.py:406-430` → `close_session` `rfid_v2_sessions.py:144-174`. Pemicu: PA berstatus akhir (`TERMINAL` `putaway_arrival_service.py:35`; kait `:239-243` dari `confirm_arrival_trip` :232, `close_remaining` :277, `putaway_order_service.py:536`); transfer `completed` (`transfer_receipt_service.py:246-252`); SJ logistik `in_transit/delivered/completed` (`logistics_service.py:592-593`) & serah terima ambil sendiri (:640) via `_close_gate_sessions` :653-658; perbaikan `done` (`repair_order_service.py:329-330`); manual `POST /api/rfid/v2/ops/doc-sessions/{jenis}/{id}/close` (`routers/rfid_v2_ops.py:72-89`, **`wms.scan`**) | CAS `close $exists:false` (:171-172) — penutup pertama menang **selamanya** (tak ada buka ulang); gedung handheld & tak pernah lewat gate → tidak ada sesi (`gate_txn_service.py:422-423`) | roll belum lewat & tidak dilengkapi jalur lain (`_completed` :380-403: PA `arrived/returned_transit`, transfer `last_transfer/returned_from_transfer`, SJ cek muat `clean/override/simulated` :400 — H-07) → kasus `rolls_missing` + notifikasi (:427-429) | – | ya (`closed_now`) | manual: entitas dokumen; otomatis: sistem |
| — | **tidak pernah ditutup otomatis** | Order Makloon (manual saja, PREP-D2 §3/§9); transfer dibatalkan sesudah `dispatched` (`routers/transfers.py:747-800`); transfer `dispatched→completed` lewat jalur status (`routers/transfers.py:667-743`); perbaikan dibatalkan dari `sent` (`repair_order_service.py:219-238`); SJ tanpa keberangkatan Logistik / logistik `failed` | – | sesi `open` menumpuk (G-04) | – | – | – |

### 3.4 Buku transaksi `rfid_v2_gate_txn` (+ efek dokumen bisnis)
| # | dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|---|
| TX1 | ∅ → `processing` | `process_source` `gate_txn_service.py:292-302` (per lintasan × dokumen, `_id` deterministik) | `_id` unik | – | – | ya | – |
| TX2 | `error` / `processing` >120 dtk → `processing` | `:303-307` | CAS `$or[error, processing basi]`; selain itu kembalikan ringkasan pihak lain (:308-310 — G-11) | `attempts+1` | – | ya | – |
| TX3 | `processing` → `done`/`evidence`/`frozen`/`skipped`/`error` | `_apply` `:259-289` lalu `update_one` tanpa syarat (:319) | `skipped` bila tanpa klaim / bukan GREEN-REVIEW (:270-271); `frozen` (:272-276, :284-289); mode `unknown` dihitung ulang (:263-268) | lihat BZ1-BZ3 | admin "Ulangi" | ya | mode gedung: `txn_mode` `:55-64` (profil `warehouse_gate_policy`, perangkat tertaut di `device_ids_in/out`) |
| BZ1 | dokumen bisnis: `gate_exits[]` (OUT) / `gate_arrivals[]` (IN) + `_last_at` | `record_evidence` `:185-208` (juga dari `accept` antrean `gate_review_actions.py:160-165`) | idempoten per lintasan (`field.passage $ne pid` :206) | entri `trip_no` (:203; balapan G-12), `txn` bool, `simulated` (:205); `shipments`, `warehouse_transfers`, `putaway_orders`, `makloon_orders`, `repair_orders` (`DOC_COLL` :39-40). **Tidak dibaca kode backend lain** (grep) | – | ya | – |
| BZ2 | PA item `pending→arrived` (+ PA `partially_received/completed`) | gate IN + mode gate: `_putaway_in` `:223-236` → `confirm_arrival_trip` `putaway_arrival_service.py:186-236` (sumber `{type:gate, passage_id}`) | trip unik per `passage_id` (`trip_key/_existing_trip` :77-86); saga PA; area beku (:205-206) | `arrival_trips[]`, `arrived_via=gate`, journey; aktor "Gate IN …" (`gate_actor` :49-52); kait tutup sesi | – | ya per lintasan | sistem (tanpa scope pengguna) |
| BZ3 | roll transfer `in_transit_transfer→available/reserved/hold/damaged` (+ transfer `partially_received/completed`) | `_transfer_in` `:239-256` → `transfer_receipt_service.receive` (per 500) | CAS per roll `_land` (`transfer_receipt_service.py:205-222`); aturan gudang → `RULE_BLOCKED` ke antrean | `receipt_events`, movement; kait tutup sesi (:252) | – | ya per roll | sistem |

### 3.5 Antrean periksa `rfid_v2_reviews` (kasus & item roll)
| # | dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|---|
| RV1 | ∅ → `open` (`kind=passage`) | `sync_passage` `gate_review_service.py:132-170` (dari `post_close`) — CANCELLED / GREEN tanpa item terbuka → tidak ada kasus (:135-140) | `_id` = digest lintasan; sisip bentrok → pakai yang ada (:165-168) | item dari alasan ber-roll/EPC + masalah transaksi (`build_passage_items` :91-129); notifikasi `warehouse_admin`+`manager` **tanpa `entity_id`**, dilewati bila simulasi (:201-217) | – | ya | – |
| RV2 | ∅ → `open` (`kind=rolls_missing`) | `open_rolls_missing` :173-198 (DS3 REVIEW) | `_id` = digest dokumen×arah | `txn_mode` dari mode gedung **saat tutup**; `simulated:false` selalu (:192) | – | ya | – |
| RV3 | `open` → `open` (gabung ulang) | `sync_passage` :144-154 (close diulang / Ulangi) | `update_one rev` — gagal CAS diabaikan diam | item baru ditambah, `recorded` | – | ya | – |
| RV4 | `open` → `resolved` (otomatis) | `refresh` :244-274 (dipanggil setiap GET/aksi) | tanpa item `open/rescan/accepting`, kunci tidak aktif, bukan `manual_close` (:264-267); CAS `rev` | – | – | ya | – |
| RV5 | `open` → `resolved` (`dismissed`) | `POST /api/rfid/v2/ops/reviews/{id}/dismiss` `routers/rfid_v2_review.py:127-133` → `dismiss` `gate_review_actions.py:241-263` | alasan ≥5; kunci aktif → 409 (:246-247); item `accepting` → 409 (:250-251) | item terbuka → `ignored` | – | ya (sudah tutup → 0) | `wms.approve` + `_case_access` |
| RV6 | `latch_open true→false` | `…/acknowledge-latch` `rfid_v2_review.py:136-143` → `acknowledge_latch` `gate_review_actions.py:266-288`; `refresh` :256-260 | `latch.acknowledge_gate` (CAS `latch_id`) | **seluruh** kunci gate dilepas | – | ya | `wms.approve` |
| RI1 | item `open/rescan → accepting → accepted` | `…/rolls/accept` `rfid_v2_review.py:97-104` → `accept` `gate_review_actions.py:130-167` | `_mutate` CAS `rev` (:42-58); `_txn_accept` :83-127 (IN+gate+PA → `confirm_arrival_trip` trip `rv-…`/`resolve_exception`; IN+gate+transfer → `receive` dgn `rule_exception_reason`; lainnya → klaim saja); roll/dokumen tak ada → 400 | klaim CL2; bukti BZ1 `via:review`; audit | galat → status dikembalikan (:152-154); proses mati → macet `accepting` (G-09) | ulang → `skipped` | `wms.approve`; `_case_access` (:23-31) |
| RI2 | `open/rescan → rejected` (+lepas klaim) / `ignored` | `…/rolls/reject` `rfid_v2_review.py:107-115` → `reject` :184-210 | alasan ≥5 | CL3 | – | ya | sama |
| RI3 | `open → rescan` | `…/rolls/rescan` → `rescan` :213-238 | catatan ≥5 | notifikasi peran `warehouse` **tanpa entity** (:231-236) | – | ya | sama |
| RI4 | `open/rescan → done_elsewhere` | `refresh` → `_done_elsewhere` :221-241 | klaim lintasan lain / PA tiba / transfer diterima | – | – | ya | – |
| RI5 | `open → recorded` | gabung RV3 (:150-151) | – | – | – | – | – |

### 3.6 Kunci gate `rfid_v2_gate_latches` (satu per perangkat × gate) · binding · protokol
| # | dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|---|
| LT1 | tidak aktif → `active` | `add_passage` `rfid_v2_latch.py:27-57` (lintasan RED) | upsert `active≠True`, `DuplicateKeyError` → ulang (:46-56) | `gate-state latched:true` ke reader (`rfid_v2_service.py:296-307`) — **termasuk lintasan simulator** (G-02) | – | ya per lintasan | perangkat |
| LT2 | `active` → `active` (+lintasan RED) | :34-44 | `passage_ids $ne pid` | `reason_codes` gabungan | – | ya | – |
| LT3 | `active` → tidak aktif | `release` :60-75 ← PS7, `POST /api/rfid/v2/ops/devices/{id}/gate-latch/acknowledge` (`routers/rfid_v2_ops.py:92-106`, `wms.approve`, audit) → `acknowledge_gate` :109-118, RV6 | CAS `latch_id` / anggota | `latch_release` di semua lintasan anggota | – | 409 `STALE_ACKNOWLEDGE` | sesi pengguna + cakupan perangkat |
| BD1 | binding ∅/lama → terikat | `POST /api/rfid/v2/ops/devices/{id}/manifest` `routers/rfid_v2.py:132-145` (`wms.scan`) → `bind_manifests` `rfid_v2_service.py:40-62` | arah cocok gate (:44-45); roll ganda antar dokumen → 409 (:49-50); ≤2000 (:53-54); ≤20 dokumen, gabungan hanya SJ (`rfid_v2_sources.py:121-134`) | `replace_one` upsert | lepas (BD2) | ya (menimpa) | entitas tiap dokumen (:140-144) |
| BD2 | terikat → dilepas / kedaluwarsa | `DELETE …/manifest` → `release_binding` :65-70; TTL `manual_binding_ttl_s` `rfid_v2_core.py:140-147` | `released_at:None` | lintasan berikutnya auto-cocok | – | ya | `wms.scan` |
| DV1 | `protocol legacy → v2` | `PUT /api/rfid/v2/ops/devices/{id}/config` (admin, `routers/rfid_v2.py:125-129`) → `publish_config` `rfid_v2_core.py:93-122` (versi tak boleh diubah :115-118) | identitas `fixed_reader` + gudang (:95-98) | `/api/rfid/ingest` ditutup untuk perangkat ini (`rfid_ingest_service.py:68-76`) | `PUT …/protocol` `legacy` (admin) `rfid_v2_core.py:125-132` → jalur lama terbuka lagi (L-01) | ya | admin |
| DV2 | `status online`, `v2_telemetry` | `POST /api/rfid/v2/device/telemetry` → `telemetry` `rfid_v2_service.py:310-319` | `enabled≠false` | heartbeat dari agent (FRM-12) | – | ya | device key |

Simulator: `POST /api/rfid/v2/ops/devices/{device_id}/simulate` `routers/rfid_v2_ops.py:140-154` (`require_role admin` +
`wms.scan` + gudang perangkat dapat dipakai) → `rfid_v2_simulator.run` `:83-122` → `ingest.events(simulated=True)` +
`service.close(simulated=True)` (`:71-80`) — jalur SAMA dengan reader; skenario `rfid_v2_envelope.py:16-27`.
Kios V2 `GET /api/rfid/v2/ops/devices/{id}/kiosk` (`rfid_v2_review.py:216-220` → `rfid_v2_kiosk.py:46-84`) baca-saja.

---

## §4. Gate lama / kios (`/api/rfid/ingest`, `gate_evaluator`)

| # | dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|---|
| LG1 | `rfid_observations` ∅ → `processed:false → true` | `POST /api/rfid/ingest` `routers/rfid.py:605-613` → `ingest` `rfid_ingest_service.py:129-250` | tipe `gate/fixed_reader/handheld` (:136-137), `protocol≠v2` (:138, :68-76), ≤500 event (:102-105); `_id` per `event_id` (:146-155), ulang yang belum `processed` diproses lagi (:156-161) | – | – | ya per event_id | device key (handheld juga — H-01) |
| LG2 | `rfid_passages` ∅ → `info` → `red/green/info` | `_passage_for` :114-126 (jendela 10 dtk), hitung ulang :232-241 | – | verdict merah dominan | – | sebagian (upsert read :221-225) | gudang perangkat |
| LG3 | `rfid_reads` ∅ → baca | :201-225 (id deterministik dari observasi) | dwell 120 dtk per passage (:182-190) | `gate_evaluator.evaluate` (juga cek klaim V2 :111-120) | – | ya | – |
| LG4 | `inventory_rolls.gate_exit` ∅ → `{movement_id, device_id, at}` | `stamp_exit` `gate_evaluator.py:169-174` ← ingest OUT hijau :230-231 | hijau `MOVEMENT_OUT` | dibaca evaluator → `REPLAY_EXIT` (:147-149) termasuk oleh V2 (`rfid_v2_policy.py:40`) | **tidak ada pembalik** | ya | – |
| LG5 | `rfid_incidents` ∅ → `open` → `acknowledged` → `resolved` | `create_from_read` `rfid_incident_service.py:35-77` (:227-229) ; `POST /api/rfid/incidents/{id}/acknowledge|resolve` `routers/rfid.py:654-672` (`wms.update`) | dedupe `dedupe_key` | notifikasi insiden (:79+) | – | ya | – |
| LG6 | `rfid_passages.acknowledged_at` null → diset | `POST /api/rfid/passages/{id}/acknowledge` `routers/rfid.py:433-443` (**`wms.scan`**) → `acknowledge_passage` `rfid_ingest_service.py:297-305` | CAS `acknowledged_at:None`; catatan ≥5 | kios lama terbuka (L-02) | – | 409 | tanpa entitas |
| LG7 | simulator lama: semua efek LG1-LG5 dengan `source:"simulated"` | `POST /api/rfid/gate/simulate` `routers/rfid.py:446-455` (`GateSimPayload{device_id, roll_id}` :52-54, **`wms.scan`**) → `gate_simulate` `rfid_service.py:322-348` | gate online, roll ∈ PT, tag aktif; **tanpa cek `wms.rfid_simulation`, tanpa pagar gudang perangkat** | `gate_exit` nyata, insiden & notifikasi nyata (G-03) | – | dwell | PT roll saja |
| LG8 | sesi verifikasi `open`: `scanned_epcs` += device | `ingest` + `session_id` → `ingest_into_session` :308-320 | `scope_ids=None` | lihat H-01 / P-01 | – | ya | gudang perangkat |

Jalur lama **tidak** memasang klaim V2, tidak membuka sesi dokumen, tidak membuat kasus antrean, tidak menulis stok/dokumen.

---

## (b) Kandidat anomali — tag (T), gate V2 (G), gate lama (L)

> Keterangan kepastian: **[kode]** = pasti dari kode; **[runtime]** = perlu dibuktikan runtime/data.

**T-01 — EPC pensiun dapat dipakai ulang (bertentangan dengan janji `allocate_epc`)** [kode]
`encode_tag` hanya menolak EPC hidup (`rfid_service.py:107-111`); `POST /api/rfid/tags/encode` menerima `epc` bebas
dari peran `wms.scan` (`routers/rfid.py:330-338`, `EncodePayload` :24-26). Daftar Awal mode `read` memakai EPC chip
apa adanya (`initial_registration_lines.py:214-219`, cek hanya tag hidup `:60`) lalu `link_tag` (`initial_registration_approve.py:63-70`).
`_new_system_epc` (:92-98) dan C72 `new_epc` (`handheld_tags.py:46-61`) juga cek hidup saja. Indeks unik parsial
(`rfid_service.py:471-472`) sengaja mengizinkan EPC sama asal satu `retired`. Hanya `allocate_epc` (`rfid_print_service.py:155-161`)
yang memeriksa semua status. Dampak: EPC label lama (tag diganti karena "rusak" tapi masih terbaca, K-OPN-05 tag tidak
unik) menunjuk dua dokumen tag; lihat T-02.

**T-02 — Pencarian EPC tanpa saring status memilih tag pensiun/acak** [kode; dampak runtime]
`find_one({"epc": …})` tanpa `status`: `routers/rfid.py:114` (`/rfid/lookup`, juga menulis `last_scan`),
`services/makloon_issue_rolls.py:93`, `services/sample_sale_service.py:295` (potong sampel C72, H-06),
`services/inspection_service.py:1460` (`$ne void` → `retired` tetap cocok), `transfer_receipt_service.py:199` (dibatasi
roll transfer). Bandingkan `routers/rfid.py:197`, `outbound_picking.py:127`, `rfid_v2_policy.py:118` (`status: active`).
Dampak: setelah ganti tag/EPC dipakai ulang, pindai label lama menuju roll yang salah (urutan alami Mongo).

**T-03 — Indeks unik EPC hidup bisa tidak pernah ada, tanpa alarm** [runtime]
Dibuat hanya di `migrate_epc_canonical` saat bootstrap bila TIDAK ada benturan (`rfid_service.py:469-475`; `bootstrap.py:1656-1660`
cuma `logging.warning`). Guardrail `scripts/guardrails/verify_rfid_tag_unique.py` memeriksa `rfid_tag_id` per roll, bukan
indeks EPC. Tanpa indeks, tangkapan `DuplicateKeyError` (`rfid_service.py:123-127`) tak pernah terjadi → dua encode
paralel EPC sama = dua tag `active`; `rfid_v2_policy._lookup` (:118-119) memetakan per EPC → satu menang diam-diam.

**T-04 — Tag `active` tanpa EPC ditulis ke chip (encode manual/auto-encode)** [kode]
`auto_encode` (`rfid_service.py:139-148`, `routers/rfid.py:341-348`, `wms.scan`, ≤200 roll sekali klik) dan `encode_tag`
bawaan `status="active"` (:93) langsung mengaktifkan EPC sistem tanpa printer/C72 — K-OPN-05 mewajibkan EPC sistem
**ditulis** ke chip. Dampak: roll "kurang" di gate (ROLLS_MISSING) atau EPC fisik lain merah `UNKNOWN_EPC`; opname
"hilang". (Sama dicatat bagian cetak.)

**T-05 — Riwayat `rfid_tag_events` bolong di ≥8 jalur** [kode]
Hanya jalur cetak PREP-F menulis riwayat (`rfid_print_service.py:268,494,838,972,1017,1027`). Tidak menulis: retire manual
(`rfid_service.py:151-178`, juga tanpa `retire_reason`/pelaku), encode/auto-encode, C72 (H-05), Daftar Awal
(`initial_registration_approve.py:35-74`, `initial_registration_lines.py:306-319`), undo penerimaan
(`receiving_roll_service.py:393-397`), tag yatim (`rfid_service.py:479-487`), tag simulasi (`loading_check_service.py:195-220`).
`GET /api/rfid/rolls/{roll_id}/tag-history` tidak bisa dipakai sebagai jejak audit identitas.

**T-06 — Tag `pending_print` tidak punya jalur pensiun umum** [kode]
`retire_tag` CAS hanya `active` (`rfid_service.py:167-169`) → `DELETE /api/rfid/tags/{id}` 409 untuk `pending_print`;
`retire_roll_tag` (`receiving_roll_service.py:396`) melewatkannya → tag hidup untuk roll terhapus (P-05). Penyapu
`retire_orphan_tags` hanya jalan saat bootstrap (`bootstrap.py:1661`).

**T-07 — Pensiun manual `wms.scan` tanpa alasan & tanpa cek job cetak terbuka** [kode]
`routers/rfid.py:351-358` vs ganti tag resmi `wms.approve` + alasan (`routers/rfid_printers.py:175-185`). Job yang masih
`queued` untuk tag itu tetap mencetak; efek aktivasi no-op tapi event `activated` ditulis (P-11).

**T-08 — Daftar Awal: "tertulis" = klaim klien, tanpa baca ulang** [kode; perlu keputusan]
`mark_written` (`initial_registration_lines.py:306-319`) mengaktifkan tag `pending_print` dari flag `written` (web /
C72 `lines[].written=true`), tidak mensyaratkan EPC terbaca kembali seperti `confirm_write` C72 (`handheld_tags.py:144-146`)
atau `readback_epc` printer (`rfid_printer_protocol.py:301-304`).

**T-09 — Tag boleh dibuat untuk roll dalam perjalanan** [kode; rendah]
`PHYSICAL_STATUSES` memuat `in_transit_sales`, `in_transit_transfer`, `allocated`, `receiving` (`rfid_service.py:22-23`) →
encode/auto-encode/C72 untuk roll yang sudah di truk; EPC baru tak ada di bukti lintasan sebelumnya.

**T-10 — Encode/auto-encode/pensiun tanpa pagar lokasi kerja** [kode]
Hanya `scope_ids` PT (`routers/rfid.py:333-356`; `rfid_service.py:95-103, 151-156`); `rfid_tags` tak ada di
`location_scope.WAREHOUSE_FIELDS` (`services/location_scope.py:20-28`). Petugas lokasi A men-tag/mempensiunkan roll gedung B
(dibanding handheld yang memagari, §5). Pola sama B3a SCP-1.

**T-11 — Tag `pending_print` tidak ikut ganti PT/gudang roll** [kode; rendah]
Sinkron hanya `status: active` (`roll_service.py:1735-1736`, `:2024-2025`, `putaway_order_service.py:423-424`,
`transfer_receipt_service.py:221-222`) → setelah dicetak tag aktif ber-`owner_entity_id` PT lama; PT baru tidak bisa
mempensiunkannya (`rfid_service.py:155-156` 403) dan `GET /rfid/tags` menyembunyikannya.

**G-01 — Simulator V2 (Mode simulasi MATI) tetap menulis KLAIM crossing, bukti dokumen & jejak sesi nyata** [kode]
Transaksi stok memang ditahan (`gate_txn_service.py:122-135, 148-149, 263-266`), tetapi `close` memasang klaim tanpa
melihat `simulated` (`rfid_v2_service.py:233-241`), `record_passage` (:268-272), `record_evidence` tetap menulis
`gate_exits[]/gate_arrivals[]` (`gate_txn_service.py:272-279`). `passed_map` tidak menyaring klaim `simulated`
(`rfid_v2_sessions.py:67-71`) → (a) lintasan NYATA berikutnya untuk roll × dokumen × arah yang sama = RED `REPLAY_CROSSING`
(`rfid_v2_sessions.py:48-50` → `rfid_v2_service.py:237-241`) atau `REPLAY_EXIT` (`gate_evaluator.py:111-120`) + kunci gate;
(b) penutupan sesi menganggap roll sudah lewat → `ROLLS_MISSING` tidak terbit (`rfid_v2_sessions.py:157`) walau tak pernah
terbaca; (c) `_carryover` (`rfid_v2_policy.py:144-149`) menurunkan bacaan nyata ≤120 dtk menjadi INFO/REVIEW tanpa klaim.

**G-02 — Lintasan simulator RED mengunci gate perangkat NYATA tanpa notifikasi** [kode]
`latch.add_passage(device['id'], …)` tanpa cek `simulated` (`rfid_v2_service.py:251-253`); `notify_case` dilewati untuk kasus
simulasi (`gate_review_service.py:202-203`); reader menerima `latched:true` dari `GET /api/rfid/v2/device/gate-state`
(`rfid_v2_service.py:296-307`) → agent tak menyalakan hijau sampai Admin Gudang mengakui (PREP-D1 §5). Skenario
`foreign_roll`/`quarantine_roll` sengaja RED (`rfid_v2_envelope.py:22-23`). Hanya kios yang menampilkan `simulated`.

**G-03 — Simulator gate lama (`wms.scan`) menulis `gate_exit`, insiden & notifikasi nyata; dibaca V2** [kode]
`POST /api/rfid/gate/simulate` (`routers/rfid.py:446-455`) → `rfid_service.gate_simulate` (:322-348) → `ingest(source="simulated")`
→ `stamp_exit` (`rfid_ingest_service.py:230-231`; `gate_evaluator.py:169-174`) + `rfid_incidents` (:227-229). Tanpa cek
`wms.rfid_simulation`, tanpa pagar gudang perangkat (perangkat gate lama mana pun). `gate_exit` dibaca evaluator untuk V2
(`gate_evaluator.py:147-149`; `rfid_v2_policy.py:40`) → lintasan OUT V2 nyata = RED `REPLAY_EXIT` + kunci. Jalur lama tidak
memasang klaim V2 → sesi V2 menghitung roll "belum lewat". Rujuk SSOT-6, FRM-13.

**G-04 — Sesi dokumen gate tidak pernah ditutup di beberapa titik siklus hidup** [kode]
Kait hanya di PA akhir, transfer `completed` via terima, SJ logistik berangkat/terkirim/ambil sendiri, perbaikan `done`
(§3.3). Tidak ada untuk: Order Makloon (manual — PREP-D2 §9), batal transfer sesudah `dispatched`
(`routers/transfers.py:747-800`, diizinkan selama bukan `partially_received`), `dispatched→completed` lewat
`POST /transfers/{id}/status` (`routers/transfers.py:667-743`), batal perbaikan dari `sent` (`repair_order_service.py:219-238`),
SJ yang tak pernah masuk/berangkat lewat Logistik atau logistik `failed` (`logistics_service.py:592-593`). Dampak: roll MKO yang
tak terbaca gate tak pernah masuk antrean (K-RFID-10 tidak berlaku untuk MKO); sesi `open` menumpuk dan
`device_sessions` hanya menampilkan 20 terbaru (`rfid_v2_service.py:364-367`).

**G-05 — "Gedung gate" membebaskan wajib cek muat hanya dari konfigurasi, bukan reader yang benar-benar bekerja** [kode]
`dispatch_guard` (`loading_check_service.py:304-308`) → `gate_validates` (`gate_txn_service.py:75-81`) cukup
`effective_mode=gate` + `device_ids_out` tak kosong; tidak cek perangkat `enabled`, profil V2 terbit, `protocol=v2`, atau
heartbeat. `txn_mode` juga tidak cek `enabled` (:55-64). Reader OUT mati/dicabut → SJ gudang "wajib cek muat" berangkat
tanpa bukti apa pun; kekurangan baru muncul sebagai kuning sesudah berangkat.

**G-06 — Koreksi klaim / tolak roll tidak membalik transaksi maupun bukti dokumen** [kode; perlu keputusan]
`release_claim`/`move_claim`/`reject` (`gate_review_actions.py:184-210, 325-377`) hanya mengubah `rfid_v2_crossings` +
catatan koreksi. Tiba PA/terima transfer yang sudah dicatat lintasan (`gate_txn_service.py:223-256`) dan entri
`gate_exits[]/gate_arrivals[]` (:185-208) tetap; dokumen tujuan `move` tidak mendapat bukti. "Tolak = roll tidak sah
lewat/tiba" (PREP-D2 §4) hanya benar untuk sesi, bukan untuk stok.

**G-07 — Kebocoran lintas PT/gedung di antrean periksa, sesi & notifikasi** [kode]
(a) Kasus tanpa `sources` (lintasan `NO_MANIFEST`/`UNKNOWN_EPC`/roll tanpa dokumen) lolos `_case_access` hanya dengan cek
lokasi (`routers/rfid_v2_review.py:23-31`) → terbaca & bisa `dismiss`/`acknowledge-latch` oleh PT mana pun yang memakai gedung
bersama (K-GDG-07); item memuat `roll_no`/EPC/bukti roll PT lain (`gate_review_service.py:91-129`). (b)
`GET /api/rfid/v2/ops/reviews/summary` tanpa `warehouse_id` menghitung semua kasus (`rfid_v2_review.py:79-85`,
`gate_review_service.py:301-307`). (c) `GET /api/rfid/v2/ops/devices/{id}/sessions` tidak memakai `_visible_sessions`
(`routers/rfid_v2_ops.py:55-60` vs `routers/rfid_v2.py:172, 176-187`) → nomor dokumen & roll PT lain. (d) Notifikasi
`rfid_gate_review`/`rfid_gate_rescan` tanpa `entity_id` ke peran global (`gate_review_service.py:214-217`,
`gate_review_actions.py:231-236`; `notification_service.py:65-71`). (e) Supervisor tidak dipagari lokasi
(`services/location_scope.py:18-19, 48-57`) → Admin Gudang site A membuka kunci gate site B.

**G-08 — Tutup sesi dokumen manual cukup `wms.scan`, tanpa cek status dokumen, tak bisa dibuka ulang** [kode]
`routers/rfid_v2_ops.py:72-89`; CAS penutup pertama selamanya (`rfid_v2_sessions.py:171-172`). Petugas dapat menutup sesi SJ di
tengah muat → penilaian kurang terlalu dini; penutupan otomatis berikutnya `closed_now:false` (tidak dinilai ulang).
PREP-D2 §4 menyebut tindakan antrean = `wms.approve`.

**G-09 — Item antrean macet `accepting` bila proses mati** [runtime]
`accept` menandai `accepting` (`gate_review_actions.py:138-145`) dan hanya memulihkan pada exception di proses yang sama
(:152-154). Tidak ada TTL/penyapu: `dismiss` ditolak `REVIEW_BUSY` (:250-251), kasus tak pernah auto-selesai
(`gate_review_service.py:25, 264-267`).

**G-10 — Close tidak atomik: klaim dari percobaan pertama bisa tertinggal pada keputusan akhir berbeda** [runtime]
Klaim dipasang (`rfid_v2_service.py:236`) sebelum keputusan disimpan (:273-275). Close ulang (agent retry/crash) menghitung
`decide` lagi dengan jam baru (`TIME_UNVERIFIED` umur >30 dtk :165-167; roll/dokumen berubah) → bisa RED/tidak
`claimable`, tetapi klaim lama milik lintasan ini tidak dikompensasi (`insert_claims` kompensasi hanya saat `BulkWriteError`,
`rfid_v2_sessions.py:56-61`) → roll "sudah lewat" untuk lintasan RED. Dua closer paralel: entri kunci (`decision_id` :31-32)
bisa ≠ keputusan tersimpan.

**G-11 — Buku `processing` pihak lain dilaporkan, lalu lintasan ditandai `done`** [runtime]
`process_source` mengembalikan ringkasan `processing` (`gate_txn_service.py:308-310`) → `post_close` menulis
`gate_txn_state='done'` karena bukan `error` (:341); close berikutnya berhenti di :333-334. Bila pelari pertama mati,
transaksi tak pernah tuntas tanpa tombol "Ulangi"; tidak ada job pengulang (PREP-D2 §9). Mitigasi sebagian: item
`NOT_RECORDED` di kasus (`gate_review_service.py:119-121`).

**G-12 — Nomor trip bukti balapan & salah setelah 500 entri** [runtime; rendah]
`trip_no = len(mine)+1` dihitung sebelum `$push … $slice -500` (`gate_txn_service.py:196-207`).

**G-13 — Pasangan IN/OUT berdampingan tanpa penengah → silang baca menjadi RED** [runtime; K-RFID-04 terbuka]
Gate IN yang membaca muatan keluar: `SALES_TRANSIT_NOT_INBOUND`/`WRONG_DESTINATION`/`MOVEMENT_NOT_ACTIVE` = RED
(`gate_evaluator.py:123-140` → `rfid_v2_policy.py:227-231`), kunci gate IN. Peredam hanya kelas RSSI/latar
(`rfid_v2_policy.py:72-114`) dan `_carryover` yang terbatas gate SAMA (:144-147); profil hanya memberi catatan
`needs_arbitration` (`warehouse_profile_service.py:208-209, 215`).

**G-14 — Simulator memilih dokumen tanpa cakupan PT** [kode; rendah]
`sources.candidates(…, lambda _n, q: q)` (`rfid_v2_simulator.py:47`) → klaim/bukti ke dokumen PT lain di gedung bersama.

**G-15 — Klaim dari antrean (`review:{kasus}`) membuat lintasan fisik berikutnya merah** [kode; desain D2 §8.6]
`_claim_passed` (`gate_review_actions.py:71-80`). Admin menerima roll SJ "sudah lewat" yang ternyata masih di gudang →
saat benar-benar lewat: RED + kunci.

**G-16 — Pengakuan lintasan V2 (D1) tanpa `audit()`** [kode; rendah]
`POST /api/rfid/v2/passages/{id}/acknowledge` (`routers/rfid_v2.py:211-227`) melepas kunci (seluruh gate,
`rfid_v2_latch.py:103`) tanpa entri audit (bandingkan `rfid_v2_ops.py:104-105`, `rfid_v2_review.py:140-142`).

**L-01 — Jalur lama hidup berdampingan & bisa dibuka lagi** [kode] — `/api/rfid/ingest` untuk perangkat `protocol`
kosong/`legacy` (gate juga) `rfid_ingest_service.py:136-138`; admin bisa mengembalikan perangkat V2 ke `legacy`
(`rfid_v2_core.py:125-132`) → klaim/sesi/antrean V2 dilewati. Rujuk SSOT-6.

**L-02 — Kunci kios lama dibuka `wms.scan`** [kode] — `routers/rfid.py:433-443` vs V2 merah `wms.approve`
(`routers/rfid_v2.py:223-225`).

**L-03 — Riwayat lintasan/kios lama tanpa pagar PT/lokasi** [kode; rendah] — `GET /api/rfid/passages`,
`GET /api/rfid/gate/{device_id}/status` (`routers/rfid.py:416-430`; `rfid_ingest_service.py:253-294`) mengembalikan
`roll_no`/EPC semua PT. Dekat B3a SCP-1.

**L-04 — Key handheld diterima `/api/rfid/ingest`** — sama dengan **H-01** (§5).

---

## (c) Resep uji runtime — tag, gate V2, gate lama, data uji

**Prasyarat umum.** Stack dev `docker compose -f docker-compose.dev.yml up -d`; data acuan `bash scripts/dev_restore_demo.sh`
(DB `test_database`, skrip :11). Base `http://localhost:8001/api`. Login `POST /api/auth/login`
`{"email":"…@kainnusantara.id","password":"<sandi demo — AGENTS.md>"}` → `Authorization: Bearer <token>` (+ `X-Entity-Id: <PT>` opsional).
Peran: `admin@` (admin), `manager@`, `wh.admin@` (warehouse_admin — `wms.approve`), `warehouse@` (petugas — `wms.scan`,
tanpa approve). Pemeriksaan DB baca-saja:
`docker compose -f docker-compose.dev.yml exec mongo mongosh test_database --quiet --eval '<query>'`.
Semua langkah di bawah MENULIS DB uji — jalankan hanya di lingkungan uji, satu POC/gate pada satu waktu.

### C-W. Gedung bermode gate & reader tertaut (data uji)
1. API: `GET /api/warehouses` → untuk tiap gudang `GET /api/warehouses/{id}/gate-policy` (izin `warehouse.view`,
   `routers/warehouses.py:133-139` → `gate_policy_of` `warehouse_profile_service.py:194-216`): baca `effective_mode`
   (`gate|handheld|manual`), `device_ids_in`, `device_ids_out`, `gate_ready`, `needs_arbitration`.
2. Mongo: `db.warehouses.find({"gate_config.has_gate":true},{_id:0,id:1,code:1,name:1,site_id:1,stock_mode:1,gate_config:1})`
   (nilai awal dari `scripts/fix_data_2026_11_08_profil_gedung.py`: gedung simpan Rancamalang & Soreang = gate, pasangan
   lama dipertahankan). Reader: `db.rfid_devices.find({type:{$in:["gate","fixed_reader"]}},{_id:0,id:1,code:1,type:1,direction:1,warehouse_id:1,protocol:1,v2_config_version:1,enabled:1,status:1})`;
   profil V2: `db.rfid_v2_configs.find({},{_id:0,device_id:1,"config.config_version":1,"config.logical_gates.logical_gate_id":1})`.
   Gate = `effective_mode:"gate"` **dan** id perangkat ada di `pairs[].in_device_id/out_device_id` **dan** `protocol:"v2"`.
3. Simulasi per PT: `GET /api/config/explain?key=wms.rfid_simulation&entity_id=<ent>` (`routers/config.py:203-222`); mongo
   `db.config_values.find({key:"wms.rfid_simulation"},{_id:0,scope_type:1,scope_id:1,value:1,applied_at:1})`.
4. Bila belum ada reader V2 tertaut (admin): (a) `POST /api/rfid/devices` `{"name":"Gate IN Uji B2b","type":"gate","direction":"in","warehouse_id":"<WH>","code":"GIN-B2B-1"}`
   (`DevicePayload` `routers/rfid.py:33-40`); (b) `POST /api/rfid/devices/<id>/api-key` → `api_key` `dk_…` (sekali tampil);
   (c) `PUT /api/rfid/v2/ops/devices/<id>/config` badan = `backend/tests/fixtures/u300_contract.json` kunci `DeviceConfig`
   dengan `device_id=<id>`, `warehouse_id=<WH>`, `site_id=<site gudang>`, `config_version="b2b-v1"`, `logical_gates[0]` →
   `logical_gate_id:"G1"`, `warehouse_id:<WH>`, `site_id:<site>`, `direction:"in"`, `antenna_ids:["1","2","3"]`,
   `completion_basis:"document_session"` (pola `backend/tests/test_prep_d1_gate_v2.py:121-130`); (d) tautkan di profil:
   `PATCH /api/warehouses/<WH>` `{"data":{"gate_config":{"has_gate":true,"confirm_mode":"gate","pairs":[{"name":"Gate 1","in_device_id":"<id IN>","out_device_id":"<id OUT>","layout":"terpisah"}]}}}`
   (`GenericPatch`, `routers/warehouses.py:237-260`; perangkat wajib `type:"gate"` & arah cocok `warehouse_profile_service.py:163-182`).

### C-G1. Simulasi lintasan V2 (admin) — skenario tersedia
`POST /api/rfid/v2/ops/devices/<dev>/simulate` (admin; `routers/rfid_v2_ops.py:140-154`) body
`{"scenario":"<s>","logical_gate_id":"G1","source_type":"<putaway|wh_transfer|shipment|makloon_order|repair_order>","source_id":"<id>","roll_limit":200}`
(`source_*` opsional — tanpa itu dokumen aktif pertama gudang/arah dipilih, `rfid_v2_simulator.py:46-54`). Skenario
(`rfid_v2_envelope.py:16-27`): `full_load` GREEN · `partial_trip` GREEN×2 (≥2 roll) · `reversed` CANCELLED ·
`reversed_with_rolls` REVIEW · `empty` CANCELLED · `foreign_roll` RED · `quarantine_roll` RED (butuh roll karantina bertag) ·
`background_tag` GREEN · `overflow` REVIEW · `sensor_fault` REVIEW. Jenis per arah (`rfid_v2_simulator.py:21-22`): OUT =
shipment, wh_transfer, putaway, makloon_order (`source_id` = `issue_ref` `<mko_id>:<i>`), repair_order; IN = putaway,
wh_transfer, repair_order. Respons: `passages[].decision` (`verdict`, `reason_codes`, `counts.pending`, `latch_id`,
`simulated:true`), `as_expected`.
- **PA (gate IN)**: PA `in_transit` ke `<WH>` ber-roll bertag aktif → `full_load` → dengan simulasi PT **menyala**:
  `db.putaway_orders.findOne({id},{arrival_trips:1,status:1,gate_arrivals:1})` trip `source.type:"gate"`; **mati**:
  alasan INFO `SIMULATED_EVIDENCE`, `gate_arrivals[].txn:false`, item tetap `pending`.
- **Transfer (gate IN)**: transfer `dispatched` dest `<WH>` → `full_load`/`partial_trip` → roll `last_transfer.ref_id`
  (menyala) / tidak (mati).
- **SJ (gate OUT)**: perangkat OUT, SJ `dispatched` di gudang itu → `partial_trip` → `db.shipments.findOne({id},{gate_exits:1})`
  trip 1/2; lalu berangkatkan logistik (`in_transit`) → `db.rfid_v2_doc_sessions.findOne({"source_ref.source_id":<sj>})` `close`.
- Mode `device` (jalur reader sungguhan, TIDAK bertanda simulasi → selalu bertransaksi di gedung gate):
  `docker compose -f docker-compose.dev.yml exec backend python /app/scripts/rfid_v2_simulate.py device --base-url http://localhost:8001 --device-key dk_… --scenario full_load --doc-epc <EPC1> --doc-epc <EPC2>`.
- Status: reader `GET /api/rfid/v2/device/gate-state?logical_gate_id=G1` (header `X-Device-Key`); panel
  `GET /api/rfid/v2/ops/devices/<dev>?limit=50`; kios `GET /api/rfid/v2/ops/devices/<dev>/kiosk`; sesi
  `GET /api/rfid/v2/ops/doc-sessions/<jenis>/<id>?direction=out|in`; bukti `GET /api/rfid/v2/ops/devices/<dev>/passages/<local_passage_id>/evidence`.

### C-G2. Antrean periksa → terima/tolak → koreksi klaim (`wh.admin@`; `warehouse@` harus 403)
1. `GET /api/rfid/v2/ops/reviews?status=open&warehouse_id=<WH>&kind=passage|rolls_missing&verdict=REVIEW|RED`;
   `GET /api/rfid/v2/ops/reviews/<case_id>` → `rolls[].key/state/codes/evidence`, `latch_open`, `txn_mode`.
2. Terima: `POST /api/rfid/v2/ops/reviews/<case_id>/rolls/accept` `{"roll_keys":["<key>"],"reason":"cek fisik ok"}`
   (`gate_review_actions.accept` :130). Ulang → `skipped`. IN+gate+PA pending → trip `rv-…` di `arrival_trips`.
3. Tolak/abaikan: `…/rolls/reject` `{"roll_keys":["<key>"],"reason":"bukan muatan ini","mode":"reject"|"ignore"}` →
   `claims_released`; cek `db.rfid_v2_claim_corrections.find({roll_id})`.
4. Pindai ulang: `…/rolls/rescan` `{"roll_keys":["<key>"],"note":"tolong pindai C72"}` → notifikasi `rfid_gate_rescan`.
5. Tutup: `…/dismiss` `{"reason":"sudah dicek manual"}` (409 `LATCH_ACTIVE` bila kunci aktif). Kunci: `…/acknowledge-latch`
   `{"note":"roll asing dikeluarkan"}` atau `POST /api/rfid/v2/ops/devices/<dev>/gate-latch/acknowledge`
   `{"latch_id":"<id>","note":"…"}`. Ulangi transaksi: `…/retry` `{}`.
6. Koreksi klaim: `GET /api/rfid/v2/ops/crossings?source_type=shipment&source_id=<sj>&direction=out`; lepas
   `POST /api/rfid/v2/ops/crossings/release` `{"source":{"source_type":"shipment","source_id":"<sj>"},"direction":"out","roll_id":"<r>","reason":"salah klaim lintasan (≥10)"}`;
   pindah `POST /api/rfid/v2/ops/crossings/move` `{"source":{…},"target":{"source_type":"shipment","source_id":"<sj2>"},"direction":"out","roll_id":"<r>","reason":"roll milik SJ kedua"}`.
7. Tutup sesi manual: `POST /api/rfid/v2/ops/doc-sessions/<jenis>/<id>/close` `{"direction":"out","note":"…"}` (uji G-08 dengan `warehouse@`).

### C-G3. Uji kandidat anomali gate
- **G-01/G-02** (PT dengan simulasi MATI, mis. PT selain KSC/KANDA/CST): `simulate` `full_load` untuk SJ/PA →
  `db.rfid_v2_crossings.find({source_id:<doc>,simulated:true})` (klaim ada), `gate_exits[]` ada; kirim lintasan nyata EPC sama
  via mode `device` → harapan aman: hijau; dugaan: RED `REPLAY_CROSSING` + `latched:true`. `simulate` `foreign_roll` →
  `GET …/device/gate-state` `latched:true`; `db.notifications.find({ref:/^rfid_review:/})` tidak bertambah. Berangkatkan SJ →
  `close.missing_count` 0 walau tak ada bacaan nyata.
- **G-03**: perangkat gate lama (`protocol` ≠ v2, `direction:"out"`, online) — `warehouse@`: `POST /api/rfid/gate/simulate`
  `{"device_id":"<gate lama>","roll_id":"<roll SJ dispatched>"}` → `db.inventory_rolls.findOne({id},{gate_exit:1})`; lalu lintasan V2
  OUT nyata untuk roll itu → dugaan RED `REPLAY_EXIT`.
- **G-04**: transfer `dispatched` lewat gate OUT V2 → batalkan `DELETE /api/transfers/<id>?reason=…` → sesi OUT tetap `open`
  (`db.rfid_v2_doc_sessions.findOne({"source_ref.source_id":<id>},{status:1,close:1})`). MKO: lintasan OUT langkah MKO → terima hasil
  MKO → sesi tetap `open`.
- **G-05**: matikan reader OUT tertaut (`PATCH /api/rfid/devices/<id>` `{"enabled":false}`) di gudang `loading_check_policy:"required"`
  → dispatch SJ tanpa cek muat → dugaan lolos.
- **G-06**: lintasan IN PA hijau (tiba tercatat) → `crossings/release` roll itu → item PA tetap `arrived`, `gate_arrivals[]` tetap.
- **G-07**: kasus lintasan `foreign_roll` tanpa dokumen (simulasi gudang tanpa dokumen) → `GET /api/rfid/v2/ops/reviews/<id>` dengan
  pengguna PT lain (X-Entity-Id lain) → dugaan 200; `GET /api/rfid/v2/ops/reviews/summary` tanpa `warehouse_id`;
  `GET /api/rfid/v2/ops/devices/<dev>/sessions` pengguna PT lain.
- **G-10/G-11**: (DB uji) hentikan backend tepat setelah klaim dipasang (debugger) lalu close ulang dengan jam >30 dtk; bandingkan
  `rfid_v2_crossings.passage` vs `decision.verdict`.

### C-T. Ganti tag & EPC
- Ganti tag resmi (cetak) & cetak ulang teks: lihat §2 C2; via C72: §5 R6.
- **T-01/T-02**: roll R1 ber-tag aktif E → `DELETE /api/rfid/tags/<tag R1>` (`warehouse@`) → roll R2 tanpa tag:
  `POST /api/rfid/tags/encode` `{"roll_id":"<R2>","epc":"<E>"}` → dugaan 200 (EPC pensiun dipakai ulang) →
  `GET /api/rfid/lookup?code=<E>&record=false` → roll mana? (`db.rfid_tags.find({epc:"<E>"})` dua dokumen).
- **T-03**: `db.rfid_tags.getIndexes()` → ada `uniq_live_epc`?
- **T-04**: `POST /api/rfid/tags/auto-encode` `{"warehouse_id":"<WH>"}` → tag `active` tanpa job cetak (`db.rfid_print_jobs.count({"items.tag_id":<id>})` = 0).
- **T-07**: buat job cetak (tag `pending_print`) → tandai cetak → sebelum klaim printer `DELETE /api/rfid/tags/<tag>` → 409 (pending);
  setelah aktif & job baru antre → `DELETE` → job lama tetap tercetak (lihat P-11).
- Riwayat: `GET /api/rfid/rolls/<roll>/tag-history` setelah tiap langkah (T-05).

Batasan: seluruh resep belum dijalankan (audit statis); tidak ada perangkat U300/CP30EN/C72 fisik.

---

# LAMPIRAN §2 — `rfid_print_jobs` · item label · `kn-printer-1` · `rfid_verify_sessions` (bagian P-xx)


# B2b — Bagian 2: `rfid_print_jobs` · item label · protokol `kn-printer-1` · `rfid_verify_sessions` (print_verify)

Audit BACA-SAJA di HEAD `35506d7` (worktree `agent-a300a69678b4a7b03`). Semua rujukan `berkas:baris` relatif ke
`backend/`, kecuali disebut lain. Singkatan: **RPS** = `services/rfid_print_service.py`, **PRN** =
`services/rfid_printer_protocol.py`, **RPR** = `routers/rfid_printers.py`, **RR** = `routers/rfid.py`.
Semua router di bawah prefix `/api` (RR:20; RPR di-include RR:731-732).

Alat bantu dijalankan: `python scripts/audit/b3a_db_writers.py --coll rfid_print_jobs --field status --kind app`
→ 5 penulis (RPS:180, RPS:561, RPS:705, PRN:224, PRN:402). **Skrip melewatkan `refresh_job` (RPS:405)** karena
`status` ditulis lewat variabel `st` — itu penulis status agregat UTAMA. `--coll rfid_print_jobs --kind app` (semua
field) → 21 panggilan (termasuk RPS:339/405/511/515/518/698/905/934/938/1024, PRN:95/138/148/191/321,
`rfid_service.py:467` migrasi EPC). `--coll rfid_verify_sessions --field status` → 7 (print_verify: RPS:678 insert
open, RPS:726 completed; sisanya cycle_count/loading_check). Item label tidak punya koleksi terpisah (array
`rfid_print_jobs.items[]`).

---

## (a) Tabel transisi

### A1. `rfid_print_jobs.status` (agregat job)

Status: `queued · printing · printed · partial · failed · needs_review · verified · verified_with_issues`
(RPS:47-51). Tidak ada `cancelled` — **tidak ada jalur pembatalan job** sama sekali (lihat P-05).
Status agregat dihitung ulang oleh `refresh_job` (RPS:384-410) dari `compute_status` (RPS:360-381):
pending/started ada → `printing` bila ada kemajuan, selain itu `queued`; ada unknown/conflict → `needs_review`;
failed=0 → `printed`; failed>0 & confirmed>0 → `partial`; semua failed → `failed`; lalu `last_verify` clean/with_issues
dan SEMUA item confirmed ⊆ `verify_covered_items` → `verified`/`verified_with_issues` (didahulukan atas printed/partial).

| # | dari → ke | pemicu (endpoint + fungsi, berkas:baris) | penjaga/CAS | efek | dibalik/kompensasi? | idempoten? | pagar PT/lokasi/perangkat |
|---|---|---|---|---|---|---|---|
| J1 | ∅ → `queued` (kind `rfid_tag`) | `POST /api/rfid/print-jobs` RR:488-499 → `create_print_job` RPS:220-270 → `_new_job` RPS:164-182 | semua roll ditemukan (RPS:225), satu PT (231), satu gudang (233); roll ber-tag hidup: tolak bila tag ada di item `pending/started/unknown` job lain (RPS:245-249); roll tanpa tag: `encode_tag` (rfid_service.py:92-136: fisik & panjang>0, EPC hidup unik, indeks unik parsial `uniq_live_epc` rfid_service.py:471-472, CAS roll tanpa tag :129-135) | tag baru `pending_print` (EPC `allocate_epc` RPS:155-161), `inventory_rolls.rfid_tag_id`+`tracking_mode=rfid`, `rfid_tag_events: encoded` (RPS:266-269), audit `rfid_print_job_created` (RR:497) | gagal di tengah → `_rollback_new_tags` hapus tag `pending_print` yang baru lahir & lepas dari roll (RPS:211-217, 263-265) | **tidak** (tanpa kunci klien); ulang untuk roll yang sama → 409 karena item `pending` (RPS:245) | PT ✔ (scope RPS:229); **lokasi ✘** (rfid_print_jobs tak ada di `location_scope.WAREHOUSE_FIELDS` location_scope.py:21-28); izin `wms:scan` |
| J2 | ∅ → `queued` (kind `qr_label`) | `POST /api/rfid/print-jobs` body `kind:"qr_label"` RR:493-494 → `create_qr_label_job` RPS:185-208 | scope per roll (195), satu gudang (197); **tanpa cek satu PT, tanpa cek status fisik, tanpa cek job QR ganda** | item tanpa tag; ZPL QR 58×40 (RPS:102-118) | – | tidak (duplikat bebas) | PT sebagian (P-15); lokasi ✘ |
| J3 | ∅ → `queued` (kind `text_reprint`) | `POST /api/rfid/rolls/{roll_id}/reprint-label` RPR:188-198 → `create_text_reprint_job` RPS:947-974 | `reason_code` ∈ REPRINT_REASONS, catatan ≥5 (950-953), roll di scope (957), tag roll `active` (959-964) | item `tag_id=None`, `display_tag_id` (968-969), `rfid_tag_events: text_reprint_requested` (972), audit `roll_label_text_reprint` (RPR:195) | – | tidak | PT ✔; lokasi ✔ lewat `_roll` → `assert_entity_access(inventory_rolls)` RPR:167-172; izin `wms:print` |
| J4 | ∅ → `queued` (sumber `retag`) | `POST /api/rfid/rolls/{roll_id}/replace-tag` RPR:175-185 → `replace_tag` RPS:977-1031 | alasan & catatan (981-984); roll di scope (988); **tidak sedang `active_movement`** (990, 843-850); tag lama tak ada di item `pending/started/unknown` (995-999); roll fisik (1000) | tag lama → `retired` (1004, `_retire_live_tag` 824-840), job baru (1008), tautan `replaced_by_tag_id`/`replaces_tag_id` (1021-1023), `replacement_issued` (1027), audit `rfid_tag_replaced` | **ya**: job gagal → tag lama dipulihkan + roll ditautkan ulang + `retire_reverted` (1009-1019) | ulang → 409 (tag baru `pending` di job) | PT ✔; lokasi ✔ (`_roll`); `wms:approve` |
| J5 | ∅ → `queued` (sumber `reprint`) | `POST /api/rfid/print-jobs/{job_id}/items/{item_id}/resolve` `action:"reprint"` RPR:150-159 → `resolve_item` RPS:920-941 | lihat I9 | job baru + `superseded_by` (934-937) + `reprint_of` (938-939) | **tidak ada kompensasi** (P-07) | 2× → 409 (item tak lagi tindak lanjut) | PT ✔; lokasi ✘; `wms:approve` |
| J6 | `queued`/`printing` (tanpa lease hidup) → sama, lease baru | `POST /api/rfid/device-jobs/claim` RPR:87-92 (= `GET /api/rfid/device-jobs/pending` RR:623-629) → `claim_jobs` PRN:101-158 | CAS `find_one_and_update` PRN:138-143: `warehouse_id = device.warehouse_id`, status ∈ OPEN_PRINT_PHASE, `kind` ∈ kemampuan printer (PRN:26,110), **tanpa item `started`**, lease kosong/kedaluwarsa | `lease{device_id, attempt_id, instance_id, expires_at=+300 s}`, `print_attempts+1`, `attempts[]` claim/reclaim (148-152), ZPL dirender ulang dgn profil printer (`_render_for_claim` 81-98, timpa seluruh `items` — P-10); sebelum klaim: sapuan efek tertunda gudang ini (106-109) | lease habis → boleh diklaim ulang printer lain hanya bila tak ada item started | **ya**: redelivery — job ber-lease hidup milik device+instance ini → attempt SAMA, tanpa tulis (118-128); instance lain → `conflicts[]` + `rfid_devices.connector_conflict` (123-131) | perangkat: `X-Device-Key` (`authenticate` rfid_ingest_service.py:57-65, `enabled≠false`), `type=printer` (PRN:43-47), gudang device; **tanpa pagar PT** (printer gedung melayani semua PT di gudang itu) |
| J7 | lease diperpanjang | `POST /api/rfid/device-jobs/{job}/attempts/{att}/renew` RPR:101-106 → `renew_lease` PRN:183-197 | `_assert_lease(allow_expired=True)` (device+attempt+instance) PRN:171-180; status terbuka; CAS `lease.attempt_id`+`device_id` (192) | `lease.expires_at`, `renewed_at`, `renew_count+1` | – | ya | gudang device (PRN:166) |
| J8 | `queued` → `printing` | `POST …/attempts/{att}/start` RPR:109-113 → `start_items` PRN:200-236 | lease hidup & milik attempt/instance (204), status terbuka (205), `job_revision` sama (207-208), item `pending` (array filter 229), CAS filter `lease.attempt_id` (225) | item → `started` (+`attempt_id`, `started_at`, `start_device_id`), `status:"printing"` langsung (228), lalu `refresh_job` (235) | – | **ya**: item started oleh attempt sama → `replay:true` (218-220) | gudang device |
| J9 | `queued` → `printed` (manual) | `POST /api/rfid/print-jobs/{job_id}/mark-printed` RR:521-528 → `mark_printed` RPS:551-572 | status `queued` (553, CAS 562), tak ada item `started` (562) | SEMUA item pending → `confirmed`, `encode_status:"confirmed"` (RFID) **tanpa bukti chip** (`evidence.source:"operator_manual"`, 542-548), `lease` dicabut (563), `effects_pending:true`, lalu efek (A5 T3) + refresh; audit `rfid_print_job_printed` | tidak | 2× → 400 | PT ✔; lokasi ✘; izin hanya **`wms:scan`** (peran `warehouse` punya, permissions_config.py:430) — P-02 |
| J10 | `queued` → `printed` (ACK lama) | `POST /api/rfid/device-jobs/{job_id}/ack` RR:632-637 → `legacy_ack` PRN:367-414 | printer (370), gudang (374), `attempt_id` wajib (376), status `queued`, lease milik device+attempt & hidup (390-395); CAS 402-405 | sama J9 tetapi `evidence:"legacy_job_ack"`, `printed_attempt_id`, `printed_by_device` | tidak | **ya**: status ≠ queued & `printed_attempt_id` sama → hanya pemulihan efek (378-385); job `printing` → 409 (386-388) | gudang device |
| J11 | `printing` → `printed`/`partial`/`failed`/`needs_review` | `POST …/attempts/{att}/results` RPR:116-121 → `report_results` PRN:247-344 → `refresh_job` (342) | per item (I4-I7) | efek item confirmed (339) | – | per `result_event_id` (I-tabel) | gudang device; **tanpa cek device/instance pemulai** (P-09) |
| J12 | `needs_review`/`printing`(started basi)/`partial` → `printed`/`partial`/`failed` | `POST /api/rfid/print-jobs/{job}/items/{item}/resolve` → `resolve_item` RPS:859-943 → `refresh_job` (942) | lihat I8-I10 | – | – | – | PT ✔; lokasi ✘ |
| J13 | `printed`/`partial`/`needs_review`/`verified_with_issues`/`verified`(ada label belum tercakup) → `verified`/`verified_with_issues` | `POST /api/rfid/verify-sessions/{sid}/complete` RR:550-559 (atau handheld `complete` handheld_sync.py:384) → `complete_verify` RPS:682-729 | sesi `print_verify`, PT, `open`, klaim saga (692) | `status`, `last_verify`, `verify_covered_items`(= item di `expected` sesi; **ditimpa**, bukan gabung), `verified_at` (705-708) lalu `refresh_job` (709: item tinjauan terbuka → tetap `needs_review`) | tidak | tidak (2× → 400/409) | PT ✔; lokasi ✘ (user), ✔ (handheld) |
| J14 | `verified`/`verified_with_issues` → `printed`/`partial` | `refresh_job` sesudah item baru `confirmed` (resolve `confirm_success` RPS:913 → 519) yang tak tercakup verifikasi (RPS:377-380) | – | – | – | – | – |
| J15 | `verified`/`printed`/`partial` → `needs_review` | hasil terlambat yang bertentangan → `items[].conflict=true` (PRN:309-312, 319-320) → refresh (RPS:367-368) | – | – | diselesaikan via resolve | – | – |
| J16 | `lease` dicabut | `refresh_job` bila tak ada item pending/started (RPS:402-403); `mark_printed` (563); `legacy_ack` (404) | CAS `state_seq` (RPS:404-406, 5×) | – | – | ya | – |
| J17 | migrasi job lama (tanpa `item_id`) | `ensure_item_ids` RPS:321-341 (dipanggil claim/start/resolve/verify) | CAS `items.item_id $exists:false` (339) | item diberi `item_id`, status turunan job (`_legacy_item_status` 315-318) | – | ya (sekali) | – |

Catatan CAS agregat: `refresh_job` hanya CAS terhadap `state_seq`; penulis item (start/results/resolve/verify/mark)
tidak menaikkan `state_seq`, sehingga refresh dari snapshot basi bisa menang sesaat — dibetulkan oleh refresh
berikutnya yang SELALU mengikuti mutasi item **kecuali** jalur `resolve reprint` yang melempar galat sebelum
refresh (P-07).

### A2. `rfid_print_jobs.items[].status` (item label)

Status item: `pending → started → confirmed | failed | unknown` + flag `conflict`, `resolution`, `superseded_by`
(RPS:41). `confirmed` = cetak terkonfirmasi **dan** chip terkonfirmasi (RFID) / `not_applicable` (QR/teks) (PRN:239-244).

| # | dari → ke | pemicu (berkas:baris) | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|---|
| I1 | ∅ → `pending` | `_new_item` RPS:139-152 (J1-J5) | – | snapshot label, `zpl`, `payload_sha256`, `profile_key` | – | – | – |
| I2 | `pending` → `started` | `start_items` PRN:224-229 | lease hidup attempt/instance; array filter `it.status:"pending"` | `attempt_id`, `started_at`, `start_device_id` | **tidak pernah dialihkan otomatis** (klaim baru menolak job ber-item started PRN:140) | replay attempt sama (PRN:218) | gudang device |
| I3 | `pending` → `confirmed` | `mark_printed` RPS:561-564 / `legacy_ack` PRN:402-405 (`_confirm_all_update` RPS:542-548) | status job `queued`, tanpa started | `print_status/encode_status:"confirmed"`, `effects:"pending"` | – | lihat J9/J10 | – |
| I4 | `started` → `confirmed`/`failed`/`unknown` | `report_results` PRN:313-318 | `result_event_id` baru (273-284), item dimulai attempt ini (285-289; `pending` → `NOT_STARTED`), digest cocok (290-293), skema (262-266); array filter `it.status: current` + `results.result_event_id $ne` (324-325); 4× coba (267) | `print_status`, `encode_status`, `result_at`, `evidence`; confirmed → `effects:"pending"`; baca balik EPC ≠ ERP → paksa `failed` (301-304); `results[]` `$slice -20` (322-323) | – | **ya**: id sama + isi sama → `duplicate` (+jalur pemulihan efek 279-280); isi beda → `IDEMPOTENCY_CONFLICT` (282-283) | gudang device; diterima walau lease habis (desain) |
| I5 | `unknown` → `confirmed`/`failed` | `report_results` PRN:313 (attempt sama, hasil bukan unknown) | sama I4 | sama I4 | – | sama | – |
| I6 | `confirmed`/`failed` + hasil berbeda → `conflict=true` (status tetap) | PRN:319-320 | sama I4 | job → `needs_review` | resolve | – | – |
| I7 | item ber-`resolution` + hasil terlambat berbeda → `conflict=true`, `late_after_resolution` | PRN:309-312 | sama | – | resolve lagi | – | – |
| I8 | `unknown`/`conflict`/`started`(basi)/`failed`(tanpa keputusan) → `confirmed` | `resolve_item action=confirm_success` RPS:881-892, 897-909 | `wms:approve` (RPR:152), catatan ≥5 (866), `_follow_up_reason` ≠ None (874-876); RFID: `evidence_type=c72_scan` + **EPC pernah terbaca sejak `started_at`** (`_epc_read_since` 809-821); CAS array filter status lama (907) | `resolution`, `conflict:false`, `effects:"pending"`, lalu efek (913) | – | 2× → 409 | PT ✔; lokasi ✘; bukti dapat dipalsukan via scan manual (P-01) |
| I9 | sama → `failed` (`confirm_failed`/`reprint`/`close`) | `resolve_item` RPS:893-909; `close` hanya bila alasan `failed` (878-879) | sama (tanpa syarat bukti) | `resolution`; RFID & ada `tag_id` → **pensiunkan tag** (`print_uncertain`/`print_failed`, 916-919); `reprint` → job baru (J5) | `reprint` tanpa kompensasi (P-07) | 2× → 409 | sama |
| I10 | `effects: None/pending → done` | `apply_item_effects` RPS:499-520 (dipicu results PRN:339, resolve 913, mark 568, legacy 409, sapuan PRN:107 & `POST /api/rfid/printers/recover-effects` RPR:302-309) | array filter `it.status:"confirmed"` (517) | lihat A5/A6; gagal → `effects_pending`, `effects_error` (511-513) | dipulihkan ulang (idempoten per langkah) | ya (kecuali `roll_label_prints` find-lalu-insert tanpa indeks unik, P-19) | recover-effects **tanpa pagar PT** (P-08) |
| I11 | `superseded_by` diset | resolve reprint RPS:934-937 | – | – | – | – | – |

### A3. `rfid_verify_sessions` (kind `print_verify`)

| # | dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|---|
| V1 | ∅ → `open` | `POST /api/rfid/print-jobs/{job_id}/verify/start` RR:531-536 (`wms:scan`) · handheld `start_session` handheld_tasks.py:320-323 → `start_verify` RPS:645-679 | kind ≠ qr_label/text_reprint (647), status ≠ queued/printing (649-652), ada item confirmed (654-656), `verified` tanpa item belum tercakup → 400 (659-662) | `expected` = SEMUA item confirmed (EPC item, **tanpa cek status tag saat ini**, 672-673), `revision = count+1` (667), `owner_entity_id`, `warehouse_id` | – | **sebagian**: sesi open yang ada dikembalikan (663-666) — find-lalu-insert tanpa indeks unik (P-12) | PT ✔ (get_print_job); lokasi ✘ user / ✔ handheld (`ctx.assert_warehouse` handheld_tasks.py:322) |
| V2 | `open` → `open` (pindai) | (a) `POST /api/rfid/verify-sessions/{sid}/scan` RR:539-547 `source` manual/simulated (device ditolak 544-545); (b) `POST /api/rfid/ingest` + `session_id` (X-Device-Key handheld/fixed_reader, protokol lama) RR:605-613 → `ingest_into_session` rfid_ingest_service.py:308-320; (c) handheld batch handheld_sync.py:307-333 → `scan_session` RPS:583-611 | sumber ∈ manual/device/simulated (588); kind cocok (591); PT (593-596; (b) dilewati karena `scope_ids=None`, pagar = gudang device 313-315); CAS `status:"open"` & tanpa `saga_lock` (607-610) | `$addToSet scanned_epcs`, `scan_sources`, `simulated_epcs`; `scan_log` (slice -200) | – | ya ($addToSet) | lihat kolom penjaga |
| V3 | `open` → (saga_lock) → `completed` | `POST /api/rfid/verify-sessions/{sid}/complete` RR:550-559 · handheld `complete` handheld_sync.py:357-392 (dibungkus `once`) → `complete_verify` RPS:682-729 | kind, PT, `open` (684-689); klaim saga `status:open` (692); snapshot SESUDAH klaim (693) | `result` = `simulated` bila ada sumber simulated (623-627; job hanya `last_verify` 697-699) / `clean` / `with_issues`; job J13; roll cocok → `journey.stage=tag_verified` (only_from 712, **tanpa cek roll masih bertaut tag itu** — P-06), `journey.verified_tag_id` hanya utk tag `active` & bertaut (715-720), `mark_cut_identity_verified` (721-722); `finish_set` status completed + `missing/extra` (726-728); audit `rfid_verify_completed` (RR:556) | galat → `mark_failed`, kunci saga tertinggal (723-725; lepas lewat Kunci Saga) | tidak (2× → 400 / 409 SAGA_IN_PROGRESS); handheld idempoten lewat `client_request_id` | PT ✔; lokasi ✘ user |

### A4. Efek jalur cetak ke `rfid_tags`

| # | dari → ke | pemicu | penjaga | efek | dibalik? | idempoten? |
|---|---|---|---|---|---|---|
| T1 | ∅ → `pending_print` | J1/J4/J5 via `encode_tag(status="pending_print")` RPS:253-255, rfid_service.py:92-136 | EPC baru `allocate_epc` (cek `find_one({"epc"})` SEMUA status RPS:159 — **bukan indeks**; indeks unik hanya EPC hidup) | roll `rfid_tag_id`, `tracking_mode:"rfid"` | rollback hapus fisik (RPS:214) | – |
| T2 | `pending_print` → ∅ (dihapus) | `_rollback_new_tags` RPS:211-217 | filter `status:"pending_print"` | roll `rfid_tag_id:None`, `tracking_mode:"barcode"` | – | ya |
| T3 | `pending_print` → `active` | `_item_effects` RPS:484-487 | `update_many` filter `status:"pending_print"`; **tanpa cek status roll** (P-05) | `activated_at`, `activated_by_job`; journey `tag_printed` hanya roll yang MASIH bertaut tag (489-492, only_from `_JOURNEY_PRINTABLE` RPS:59); `rfid_tag_events: activated` (kunci `activated:{tag}:{job}`, **ditulis walau tidak ada aktivasi** — P-11) | – | ya |
| T4 | `active`/`pending_print` → `retired` | `_retire_live_tag` RPS:824-840 ← resolve gagal/reprint/close (916-919), replace_tag (1004) | CAS status hidup (828) | roll dilepas (`rfid_tag_id:None`, `tracking_mode:"barcode"`, `$unset journey.verified_tag_id` 834-837), `rfid_tag_events: retired`; **resolve tidak cek `active_movement`** (beda dgn replace_tag 990) | replace_tag: T5 | ya |
| T5 | `retired` → status lama | kompensasi `replace_tag` RPS:1009-1019 | `status:"retired"` | roll ditautkan ulang, `retire_reverted` | – | ya |
| T6 | tautan `replaced_by_tag_id`/`replaces_tag_id` | RPS:927-929, 1021-1023 | – | – | – | – |
| T7 | tanpa perubahan | text_reprint (item `tag_id=None` RPS:968), qr_label | – | – | – | – |

### A5. Efek lain (inventory_rolls / dokumen / audit / notifikasi)

- `inventory_rolls.journey.stage`: `tag_printed` (+`print_job_id`) RPS:492; `tag_verified` (+`verify_session_id`)
  RPS:711-712; `journey.verified_tag_id/verified_at` RPS:718-720; `$unset verified_tag_id` saat pensiun RPS:837.
  Jalur cetak **tidak** menulis `last_scan`, `gate_exit`, stok, atau dokumen bisnis.
- `roll_label_prints` (RPS:418-435, idempoten per `(job_id, roll_id)` find-lalu-insert); `rfid_tag_events`
  (RPS:450-464; indeks unik sparse `key` RPS:73 dibuat lazy dan galat indeks ditelan RPS:75-76).
- Audit hanya di router pengguna: `rfid_print_job_created`, `rfid_print_job_printed`, `rfid_verify_completed`,
  `rfid_print_item_resolved`, `rfid_tag_replaced`, `roll_label_text_reprint`, `rfid_printer_profile_updated`,
  `rfid_print_effects_recovered`. **Aksi perangkat (claim/start/results/ACK) tidak diaudit** — jejaknya hanya
  `attempts[]` & `items[].results[]` (slice 30/20).
- Notifikasi: hanya `printer_stuck_watch` (job `queued` > 30 mnt tanpa printer online, printer_stuck_watch.py:21-52;
  penjadwal 10 mnt scheduler_service.py:200-205). Job `printing` ber-lease mati & butir `needs_review` tidak
  memicu notifikasi (P-17).

**Jumlah transisi:** job 17 (J1-J17) · item 11 (I1-I11) · sesi 3 (V1-V3) · tag 7 (T1-T7) = **38**.

---

## (b) Kandidat anomali

**P-01 — "Bukti baca EPC" & verifikasi cetak bisa dipenuhi dengan EPC yang DIKETIK (source `manual`)** · pasti dari kode
`RR:539-547` menerima `source:"manual"` (hanya `device` ditolak); `scan_session` RPS:580/588 memperlakukan manual
setara pembacaan nyata; `evidence_result` RPS:623-627 hanya menurunkan `simulated`; `complete_verify` RPS:694-722
→ `verified` + journey `tag_verified` + `mark_cut_identity_verified`. Lebih parah: `resolve_item confirm_success`
untuk label RFID tidak pasti mensyaratkan "EPC terbaca handheld/reader" (RPS:881-891), tetapi `_epc_read_since`
RPS:809-815 cukup menemukan sesi verifikasi **apa pun** (print_verify/cycle_count/loading_check, PT/gudang mana pun)
yang `scanned_epcs` memuat EPC itu tanpa sumber `simulated`. EPC terlihat di `GET /api/rfid/print-jobs/{id}` dan
`GET /api/rfid/printers/follow-up`. Dampak: aturan PREP-F §9.3 ("cek visual tidak cukup untuk chip") dan RF-07
bisa dilangkahi oleh petugas `wms:scan` + supervisor; label tanpa chip valid dinyatakan aktif & terverifikasi.
Rujuk B3b FRM-13 (simulasi pindai area menulis bacaan nyata → juga lolos cabang `rfid_reads` RPS:816-818).

**P-02 — `mark-printed` manual (`wms:scan`) mengonfirmasi chip tertulis tanpa bukti & mengaktifkan tag** · pasti dari kode
RR:521-528 → RPS:551-572 + `_confirm_all_update` RPS:542-548 menulis `encode_status:"confirmed"` untuk semua label
RFID dengan bukti `operator_manual`, lalu tag `pending_print → active` (RPS:485-487). Peran `warehouse` punya
`wms:scan` (permissions_config.py:430). Bandingkan: memutus SATU label tidak pasti butuh `wms:approve` + bukti C72
(RPS:881-891). Kontrak lama `legacy_ack` (PRN:397-401) juga mengonfirmasi encode tanpa baca balik per label.
Dampak: EPC aktif di ERP tanpa chip tertulis → gate/opname membaca "roll hilang"; standar bukti tidak konsisten.

**P-03 — ZPL ber-`^RFW` (EPC) bisa diunduh/di-pratinjau dengan `wms:view`, di luar lease** · pasti dari kode (akses); dampak perlu SOP/runtime
`GET /api/rfid/print-jobs/{id}/zpl` RR:510-518 (`wms:view`) dan `POST /api/rfid/printers/label-preview` dengan
`job_id` RPR:271-299 (`wms:view`) mengembalikan ZPL persis yang menulis EPC. PREP-F §9.1 menyebut lease ERP
"satu-satunya pencegah dua printer menulis EPC yang sama"; unduhan ini melewati lease, start barrier, dan tak
diaudit. Peran baca-saja (`sales_admin`, `sample_admin`: `wms:["view"]`) ikut bisa. Dampak: dua chip EPC sama
(sejalan butir pemilik P3).

**P-04 — Cek "EPC sibuk" melewatkan item `failed` tanpa keputusan & item `conflict` → job kedua ber-EPC SAMA, lalu resolusi job lama memensiunkan tag job baru** · pasti dari kode (urutan), perlu runtime untuk bukti
`create_print_job` RPS:240-249 memakai ulang tag hidup roll bila tidak ada di item `["pending","started","unknown"]`
(RPS:245; sama di `replace_tag` RPS:995). Item `failed` tanpa resolusi (mis. cetak gagal tapi chip tertulis —
`chip_written` RPS:803) menyisakan tag `pending_print` hidup di roll → `POST /api/rfid/print-jobs` untuk roll itu
membuat item baru dengan EPC yang SAMA. Ketika item lama diputus `confirm_failed`/`close`, `_retire_live_tag`
(RPS:916-919) memensiunkan tag yang juga dipakai job baru → job baru kemudian `confirmed` tetapi `update_many`
`pending_print→active` tak berlaku (RPS:485), roll sudah tanpa tag (RPS:834-836), journey tak naik (489-492),
dan riwayat tetap mencatat "activated" (P-11). Dampak: label fisik baru ber-EPC pensiun; roll kehilangan identitas.

**P-05 — Job antre tak bisa dibatalkan & efek cetak tidak memeriksa status roll → tag aktif untuk roll terhapus/keluar/terkonsumsi** · pasti dari kode
Tidak ada endpoint batal job/item (PREP-F §12 mengakui). `_item_effects` RPS:478-496 mengaktifkan tag tanpa cek
`inventory_rolls.status`/keberadaan roll. `create_print_job` tidak cek status fisik untuk roll yang SUDAH ber-tag
hidup (RPS:240-243; cek fisik hanya di `encode_tag`); `create_qr_label_job` tidak cek status sama sekali (RPS:185-208).
Contoh pasti: roll `receiving` (eligible, rfid_service.py:22-23) dibuatkan job → `undo_receiving_roll` menghapus roll
(receiving_roll_service.py:400-406) tetapi `retire_roll_tag` hanya memensiunkan tag `active` (393-397) → tag
`pending_print` tetap hidup untuk roll yang tidak ada, job tetap di antrean, printer mencetak, tag menjadi `active`
(yatim; hanya `retire_orphan_tags` rfid_service.py:479-487 bila dipanggil). Hal sama untuk roll yang keluar gate /
terjual / dikonsumsi sebelum printer menarik job.

**P-06 — Verifikasi menaikkan journey `tag_verified` & identitas potong dari EPC yang SUDAH pensiun/diganti** · pasti dari kode
`start_verify` mengisi `expected` dari item `confirmed` tanpa cek status tag (RPS:672-673). `replace_tag` tidak
menandai item `confirmed` job lama (busy hanya pending/started/unknown RPS:995). `complete_verify` memanggil
`set_journey(matched_rolls, "tag_verified")` dan `mark_cut_identity_verified` hanya berdasar `roll_id` item
(RPS:695, 710-712, 721-722) — hanya `verified_tag_id` yang dipagari tag aktif+bertaut (715-720). Skenario: job J
confirmed → `replace-tag` (EPC lama pensiun, label lama masih menempel) → verifikasi J membaca EPC lama → roll
naik `tag_verified` padahal tag aktifnya (baru) `pending_print` & belum pernah dibaca.

**P-07 — Resolve `reprint` non-atomik tanpa kompensasi; agregat job basi** · pasti dari kode
RPS:905-909 menyimpan `resolution`+status `failed`, RPS:916-919 memensiunkan tag, baru RPS:925/931/933 membuat job
baru. Bila `create_print_job` gagal (roll sudah tidak fisik/panjang 0 → `encode_tag` 400 rfid_service.py:102-103,
roll dipakai job lain → 409, dsb.) galat dilempar SEBELUM `superseded_by` (934) dan `refresh_job` (942): roll tanpa
tag, tanpa job pengganti, `counts`/`review_open`/`status` job basi sampai mutasi lain; ulang → 409 "tidak sedang
menunggu tindak lanjut" (876). Bandingkan `replace_tag` yang punya kompensasi (RPS:1009-1019).

**P-08 — Endpoint cetak/verifikasi pengguna tanpa pagar LOKASI kerja; beberapa tanpa pagar PT** · pasti dari kode; dampak bergantung `wms.location_scope_enforced`
`rfid_print_jobs`/`rfid_verify_sessions` tidak ada di `WAREHOUSE_FIELDS` (location_scope.py:21-28) dan layanan hanya
memakai `scope_ids` PT: `GET/POST /api/rfid/print-jobs`, `mark-printed`, `verify/start`, `verify-sessions/*/scan|complete`
(RR:478-559), `printers/queue|follow-up`, `resolve` (RPR:125-159). `POST /api/rfid/printers/recover-effects`
(RPR:302-309) menyapu job SEMUA PT bila `warehouse_id` kosong. `GET /api/rfid/printers/{device_id}/profile`
(RPR:208-226) membuka profil + `printer_connection.host` printer gudang/PT mana pun. Handheld memagari lewat
`ctx.assert_warehouse` (handheld_tasks.py:322, 343) → perilaku ERP-web vs C72 berbeda. Rujuk B3a SCP-1 (pola sama).

**P-09 — `report_results` tidak memeriksa perangkat/instance pemulai** · pasti dari kode; dampak rendah
Hanya `item.attempt_id == attempt_id` (PRN:285) + gudang device (PRN:166); `start_device_id` tidak dibandingkan,
`instance_id` dari `ResultsPayload` dibuang router (RPR:116-121). `GET …/attempts/{att}` (PRN:347-364) membuka
`items[].attempt_id` ke printer mana pun di gudang yang sama → printer B dapat melapor hasil label printer A.

**P-10 — `_render_for_claim` menimpa SELURUH `items` dari snapshot lama (lost update)** · perlu runtime (jendela sempit)
PRN:153-155 membaca job, PRN:95-97 `$set items` utuh dengan filter `lease.attempt_id` & tanpa started. Bila di
antaranya `resolve_item` (item failed/unknown) / hasil terlambat (item unknown) / `apply_item_effects` menulis, tulisan
itu hilang (mis. resolusi hilang padahal tag sudah dipensiunkan; item kembali unknown padahal tag sudah aktif).
Terjadi hanya bila `profile_key` printer ≠ item (printer berprofil non-bawaan / 300 dpi).

**P-11 — Riwayat `activated` ditulis walau tag tidak diaktifkan** · pasti dari kode
RPS:493-496 menulis `rfid_tag_events: activated` untuk SETIAP item confirmed tanpa memeriksa hasil `update_many`
RPS:485-487 (tag sudah `retired`/`active` dari sebelumnya — P-04, P3, retire manual `DELETE /api/rfid/tags/{id}`
rfid_service.py:151-178 yang tidak cek item job terbuka).

**P-12 — `start_verify` find-lalu-insert → dua sesi `print_verify` open untuk satu job** · perlu runtime
RPS:663-678 tanpa indeks unik `(print_job_id, status=open)`; `revision = count_documents+1` (667) juga balapan.
Dua klik/HP bersamaan → dua sesi; pindaian terbelah; `verify_covered_items` ditimpa sesi yang selesai terakhir.

**P-13 — Daftar tugas handheld `print_verify` menampilkan job yang pasti ditolak & menyembunyikan yang sah** · pasti dari kode
`_list_print` handheld_tasks.py:161-167: `kind $ne qr_label` (job `text_reprint` ikut tampil padahal `start_verify`
menolak, RPS:647-648) dan status hanya `printed`/`verified_with_issues` (job `partial`/`needs_review` yang bisa
diverifikasi RPS:649-656 tidak tampil — bertentangan dengan PREP-F §4 "7 label baik bisa diverifikasi tanpa
menunggu 3 label bermasalah").

**P-14 — Status `verified*` menutupi kondisi job** · pasti dari kode; rendah
Selesai tanpa satu pindaian pun → `with_issues` → job `verified_with_issues` (RPS:694, 705-709; compute 375-380).
`verified` didahulukan atas `partial` (RPS:375-381) sehingga job dengan label gagal belum diputus tampil
"Terverifikasi" (`review_open>0` masih terhitung).

**P-15 — `create_qr_label_job` tanpa cek satu PT** · pasti dari kode; perlu runtime (pengguna mode gabungan/view_all)
RPS:194-198 hanya cek scope per roll; `owner_entity_id` job = roll pertama (207). `create_print_job` punya cek
(RPS:231-232). Data roll PT lain terbawa ke job milik PT pertama.

**P-16 — Jendela idempotensi `result_event_id` hanya 20 hasil terakhir per item** · pasti dari kode; rendah
`MAX_RESULTS_PER_ITEM=20` + `$slice` (PRN:32, 322-323); dedupe mencari di `results[]` (273). Ulangan id lama yang
sudah tergeser diterima sebagai hasil baru (bisa memicu `conflict`).

**P-17 — Pengawas printer hanya `queued`** · pasti dari kode; rendah
printer_stuck_watch.py:24 — job `printing` ber-lease mati (label "macet") dan `needs_review` tidak memberi notifikasi.

**P-18 — Dua instance tanpa `instance_id` diperlakukan sama** · perlu runtime; rendah
Instance `None` == `None` (PRN:123, 176) — dua middleware lama (GET pending tanpa header `X-Connector-Instance`)
dengan key sama sama-sama mendapat redelivery & `start` replay (PRN:218) → potensi label ganda EPC sama. Connector
PREP-F selalu mengirim instance (middleware/printer-connector/kn_printer_connector/erp.py:42).

**P-19 — Efek idempoten "cek lalu sisip" tanpa indeks unik** · perlu runtime; rendah
`record_label_prints` RPS:424-434 (tanpa indeks `(job_id, roll_id)`), `tag_event` RPS:459-464 bergantung indeks
sparse `key` yang dibuat lazy dan galatnya ditelan (RPS:63-76). Sapuan di `claim_jobs` (PRN:106-109) + hasil
bersamaan → baris riwayat cetak ganda.

**Rujukan paket lain (tidak dihitung ulang):** B3b **INP-14** `PrintJobPayload.kind` tak divalidasi (RR:61-64,
493-496: nilai selain `qr_label` → job RFID; `source` juga diabaikan untuk RFID RR:496). B3b **FRM-12** telemetri
printer menulis `status:"online"`/`last_heartbeat` (PRN:436-452) → `printer-status`/`printer_stuck_watch` membaca
heartbeat connector sebagai printer hidup. B3b **FRM-13** (lihat P-01). Butir pemilik **P3** PREP-F (job RFID untuk
roll ber-tag aktif = EPC sama di dua chip, RPS:240-249) **masih terbuka di kode**.
**Di luar bagian 2 (untuk fork bagian 1):** `POST /api/rfid/tags/encode` menerima `epc` bebas dan langsung `active`
(RR:330-338, rfid_service.py:107-111 hanya cek EPC HIDUP → EPC pensiun dapat dipakai ulang; tanpa tulis chip) dan
`auto-encode` membuat tag `active` tanpa cetak (rfid_service.py:139-147) — bertentangan dengan K-OPN-05.

---

## (c) Resep uji runtime

**Prasyarat** — stack dev (`docker compose -f docker-compose.dev.yml up -d`), data acuan `bash scripts/dev_restore_demo.sh`.
Base `http://localhost:8001/api`. Login `POST /api/auth/login` body `{"email":"…","password":"<sandi demo — AGENTS.md>"}` →
`token`; header pengguna `Authorization: Bearer <token>` (+ opsional `X-Entity-Id: <PT>`). Akun: `admin@` (admin),
`manager@` (manager), `wh.admin@` (warehouse_admin: `wms:approve`), `warehouse@` (warehouse: scan/print, TANPA approve),
`salesadmin@`/`sampleadmin@` (`wms:view` saja) — semua `@kainnusantara.id`. Cek peran: `GET /api/auth/me`.
Pemeriksaan DB baca-saja (mongosh di kontainer mongo): `db.rfid_print_jobs.findOne({id})`, `db.rfid_tags.find({roll_id})`,
`db.rfid_tag_events.find({roll_id})`, `db.rfid_verify_sessions.find({print_job_id})`, `db.roll_label_prints.find({roll_id})`.

### C0. Printer & key
1. Cari printer gudang: `GET /api/rfid/devices?warehouse_id=<wh>` (`wms:view`, RR:362-366) → `type:"printer"`;
   ringkasan `GET /api/rfid/printer-status?warehouse_id=<wh>` (RR:232-289).
2. Bila tidak ada (admin): `POST /api/rfid/devices` body `{"name":"CP30EN Uji","type":"printer","warehouse_id":"<wh>","code":"PRN-UJI-1"}`
   (DevicePayload RR:33-40, `create_device` rfid_service.py:208-229).
3. Key (admin): `POST /api/rfid/devices/<dev_id>/api-key` (RR:594-602) → `api_key` `dk_…` **tampil sekali**
   (rfid_ingest_service.py:26-40); sudah ada key → 409, pakai `?regenerate=true` (key lama langsung mati).
4. (Opsional, admin) profil: `PUT /api/rfid/printers/<dev_id>/profile` body
   `{"profile":{"dpi":300},"connection":{"host":"10.0.0.50","port":9100},"capabilities":["rfid","qr"]}` (ProfilePayload RPR:229-232)
   — profil non-bawaan memicu render ulang saat klaim (P-10).
5. Handheld untuk V2(b): perangkat `type:"handheld"`, `protocol` bukan `v2` (rfid_ingest_service.py:68-76).

### C1. Alur bahagia: buat job → klaim → start → hasil per label → verifikasi
1. Roll tanpa tag: `GET /api/rfid/untagged-rolls?warehouse_id=<wh>` (RR:320-327).
2. Buat job (`warehouse@`/`wh.admin@`/admin): `POST /api/rfid/print-jobs` body `{"roll_ids":["<roll>"]}` (PrintJobPayload RR:61-64)
   → `status:"queued"`, `items[0].{item_id,epc,payload_sha256}`; DB: tag `pending_print`, roll `rfid_tag_id`, event `encoded`.
3. Config: `GET /api/rfid/printer-agent/config` header `X-Device-Key: <key>` (RPR:75-78).
4. Klaim: `POST /api/rfid/device-jobs/claim` header `X-Device-Key`, `X-Connector-Instance: inst-A`, body
   `{"limit":1,"instance_id":"inst-A"}` (ClaimPayload RPR:39-41) → `jobs[0].lease.attempt_id`, `revision`,
   `redelivered:false`. Ulang sama → `redelivered:true`, attempt sama, `print_attempts` tetap (PRN:118-128).
   Ulang dengan `instance_id:"inst-B"` → `conflicts[0].code:"LEASE_OTHER_INSTANCE"`, DB `rfid_devices.connector_conflict`.
5. Start: `POST /api/rfid/device-jobs/<job>/attempts/<att>/start` body `{"item_ids":["<item>"],"job_revision":1,"instance_id":"inst-A"}`
   (StartPayload RPR:44-47) → `accepted[0].replay:false`; ulang → `replay:true`; `job_revision:2` → 409 `VERSION_CONFLICT`.
6. Renew: `POST …/attempts/<att>/renew` body `{"instance_id":"inst-A"}` (RenewPayload RPR:50-51).
7. Hasil: `POST …/attempts/<att>/results` body
   `{"results":[{"result_event_id":"ev-1","item_id":"<item>","print_status":"confirmed","encode_status":"confirmed","payload_sha256":"<sha dari klaim>","evidence":{"source":"connector","readback_epc":"<EPC>","printer_state":"ready"}}],"instance_id":"inst-A"}`
   (ItemResult/ResultsPayload RPR:54-65) → `acks[0].status:"accepted"`, `job_status:"printed"`; DB: tag `active`,
   journey `tag_printed`, `roll_label_prints` 1 baris, event `activated`.
   - Ulang identik → `duplicate`. Id sama, `encode_status:"failed"` → `IDEMPOTENCY_CONFLICT`.
   - Varian: `readback_epc` lain → item `failed` (PRN:301-304); `encode_status:"unknown"` → `needs_review`.
   - Item belum start → `NOT_STARTED`; attempt lain → `ATTEMPT_MISMATCH`; digest beda → `PAYLOAD_MISMATCH`.
8. Status attempt: `GET /api/rfid/device-jobs/<job>/attempts/<att>` (PRN:347-364).
9. Verifikasi (`wms:scan`): `POST /api/rfid/print-jobs/<job>/verify/start` → `id` sesi `rvs_…` (ulang = sesi sama).
   Pindai: (a) `POST /api/rfid/ingest` header `X-Device-Key: <key handheld>` body `{"session_id":"<sid>","epcs":["<EPC>"]}`
   (IngestPayload RR:583-587) atau (b) `POST /api/rfid/verify-sessions/<sid>/scan` body `{"epcs":["<EPC>"],"source":"manual"}`
   (VerifyScanPayload RR:74-76). Selesai: `POST /api/rfid/verify-sessions/<sid>/complete` → `result:"clean"`, job
   `verified`, roll `journey.stage:"tag_verified"` + `verified_tag_id`. `source:"simulated"` → `result:"simulated"`, job tak berubah.
10. Kontrak lama: `GET /api/rfid/device-jobs/pending?limit=1` (X-Device-Key) lalu `POST /api/rfid/device-jobs/<job>/ack`
    body `{"attempt_id":"<att>"}` (AckPayload RR:590-591) → `printed`; ulang → `replay:true`.

### C2. Tindak lanjut, ganti tag, cetak ulang teks
- Daftar: `GET /api/rfid/printers/follow-up?warehouse_id=<wh>` / `GET /api/rfid/printers/queue?warehouse_id=<wh>&status=needs_review`.
- Putus (`wh.admin@`): `POST /api/rfid/print-jobs/<job>/items/<item>/resolve` body
  `{"action":"confirm_success|confirm_failed|reprint|close","note":"min 5 huruf","evidence_type":"c72_scan|visual_check|printer_log|other","evidence_ref":""}`
  (ResolvePayload RPR:143-147). `warehouse@` → 403.
- Ganti tag (`wh.admin@`): `POST /api/rfid/rolls/<roll>/replace-tag` body `{"reason_code":"damaged","note":"tag sobek di gudang"}`
  (RetagPayload RPR:162-164; kode: damaged/lost/wrong_roll/print_issue/other RPS:54-56) → `old_tag` retired, `new_tag` `pending_print`, job baru.
- Cetak ulang teks (`warehouse@`): `POST /api/rfid/rolls/<roll>/reprint-label` body `{"reason_code":"text_damaged","note":"teks pudar kena air"}`
  (kode RPS:57-58). Riwayat: `GET /api/rfid/rolls/<roll>/tag-history`.
- Sapu efek: `POST /api/rfid/printers/recover-effects?warehouse_id=<wh>` (`wms:approve`).

### C3. Uji kandidat anomali
- **P-01**: buat job, klaim+start, kirim hasil `encode_status:"unknown"` → `needs_review`. Buka sesi verifikasi job LAIN
  yang `printed` (C1-9), `POST …/verify-sessions/<sid lain>/scan` `{"epcs":["<EPC item unknown>"],"source":"manual"}`;
  lalu resolve `confirm_success` `evidence_type:"c72_scan"` → harapan aman: 400; dugaan: 200 + tag `active`.
  Juga: verify/start → scan manual semua EPC `expected` → complete → `clean`/`verified` tanpa perangkat.
- **P-02**: `warehouse@` buat job → `POST …/mark-printed` → cek item `encode_status:"confirmed"`, `evidence.source:"operator_manual"`, tag `active`.
- **P-03**: `salesadmin@` `GET /api/rfid/print-jobs/<job>/zpl` → 200 berisi `^RFW,H^FD<EPC>`; dan `POST /api/rfid/printers/label-preview` `{"job_id":"<job>"}`.
- **P-04**: job A → klaim/start → hasil `print_status:"failed"`,`encode_status:"confirmed"` → item failed (tanpa resolve).
  `POST /api/rfid/print-jobs` `{"roll_ids":["<roll sama>"]}` → dugaan 200 dengan EPC SAMA. Resolve item A `confirm_failed`
  → tag pensiun; klaim/start/hasil confirmed job B → item B confirmed, tag tetap `retired`, roll `rfid_tag_id:null`, event `activated` ada.
- **P-05**: roll `receiving` (alur penerimaan) → buat job → batalkan roll penerimaan (endpoint undo GR yang memanggil
  `undo_receiving_roll`) → klaim/start/hasil confirmed → tag `active` untuk `roll_id` yang tidak ada.
  Varian: job untuk roll lalu roll dikirim keluar/terjual sebelum klaim.
- **P-06**: job confirmed (tanpa verifikasi) → `replace-tag` → verify/start job lama → scan EPC LAMA → complete →
  roll `journey.stage:"tag_verified"` padahal `rfid_tag_id` = tag baru `pending_print`.
- **P-07**: item `unknown` → ubah roll ke tidak fisik (mis. `length_remaining:0` lewat alur potong/jual) → resolve
  `reprint` → galat; cek item `resolution` tersimpan, tag lama `retired`, tidak ada job baru, `counts` job basi; ulang → 409.
- **P-08**: atur pengguna `warehouse` dengan `location_warehouse_ids=[whA]` & setelan `wms.location_scope_enforced` menyala
  (lihat docs/LOCAL_DEV.md / pengaturan) → `GET /api/rfid/print-jobs?warehouse_id=<whB>` dan `POST /api/rfid/print-jobs` untuk roll whB
  → dugaan 200 (bandingkan handheld → 403/404). `POST /api/rfid/printers/recover-effects` tanpa `warehouse_id` oleh PT A.
- **P-09**: dua printer di gudang sama; A klaim/start; B `GET /api/rfid/device-jobs/<job>/attempts/<attA>` lalu
  `POST …/attempts/<attA>/results` dengan key B → dugaan `accepted`.
- **P-12**: dua `POST …/verify/start` paralel (mis. `xargs -P2 curl`) → `db.rfid_verify_sessions.count({print_job_id,status:"open"})` = 2?
- **P-13**: handheld `GET /api/handheld/tasks?kind=print_verify` (lihat bagian 5) untuk gudang dengan job `text_reprint`
  printed & job `partial`.

Batasan: semua resep belum dijalankan (audit statis); tidak ada CP30EN fisik (PREP-F §8 asumsi A1-A6).


---

# LAMPIRAN §5 — Handheld C72 /api/handheld/* (bagian H-xx)

# B2b · Bagian 5 — Handheld C72 `/api/handheld/*` (audit statis, baca-saja)

Baseline: worktree `agent-a300a69678b4a7b03`, HEAD `35506d7` (PREP-G digabung). Semua rujukan `berkas:baris` relatif ke
`backend/`. Penulis status dicek dengan `scripts/audit/b3a_db_writers.py --kind app` (handheld_requests 2 penulis,
handheld_tag_writes 3, handheld_epc_reservations 2; `handheld_operator_sessions` ditulis lewat `db[OPS]` → dicek manual
dengan grep). Singkatan: **W** = gudang efektif (`HandheldCtx.warehouse_ids` = gudang perangkat ∩ lokasi kerja pengguna,
`handheld_core.py:204-218`), **E** = semua PT yang ditugaskan ke pengguna (`allowed_entity_ids`, bukan PT aktif,
`handheld_core.py:212-213`).

## 0. Matriks pagar per jenis tugas (8 jenis, `handheld_core.py:34-51`)

| Jenis | Izin (= web asal?) | Daftar tugas (`handheld_tasks.py`) | Yang diharapkan | Batch / aksi | Selesai |
|---|---|---|---|---|---|
| putaway_in | wms.update (= `putaway_orders.py:217`) | `to_warehouse_id∈W`, owner∈E (:83-85) | `_exp_pa` owner+gudang (:239-242) | `_batch_pa` owner+gudang (`handheld_sync.py:190-193`) | n/a |
| transfer_in | transfer.update (= `transfers.py:461`) | `dest∈W`, PT∈{entity,source,dest} (:98-101) | `_transfer_doc` (:251-259) | sama (`handheld_sync.py:231`) | n/a |
| outbound_so / _sample | wms.update (= `outbound_picking.py:545/556/613`) | wms_tasks `warehouse_id∈W`, entity∈E (:114-120) | `doc_guard` gudang dari doc_id + SO entity (:328-336); **sesi tanpa gudang ikut** (:294) | `_session_for` (`handheld_sync.py:290-304`) + `scan_session` cek PT | `lc.complete` |
| cycle_count | wms.scan (= `rfid.py:695`) | `ctx.warehouses` × `cycle_entities` (:142-158) | `doc_guard` gudang (:337-339) | sama | `cc.complete` `_in_scope` |
| print_verify | wms.scan (= `rfid.py:533`) | job `warehouse_id∈W`, owner∈E, `kind≠qr_label` (:162-165) | `doc_guard` job (:340-345) | sama | `complete_verify` cek owner |
| cutting | wms.scan (= `sample_sales.py:79`) | task `warehouse_id∈W`, entity∈E (:171-174) | `cutting_task` (:372-377); kandidat roll **tanpa filter PT** (:383-386) | `sync.cut` → `cutting_task` saja; **gudang roll tidak dicek** | n/a |
| registration | inventory.cycle_count (= `initial_registration.py:171`) | sesi `warehouse_id∈W`, entity∈E∪{None,""} (:181-185) | `registration_session` (:400-405) | `process_lines` + `add_line` (bin∈sesi, owner∈E) | n/a |
| (tulis tag) | wms.scan (= `rfid.py:332/353`) | `untagged` (`handheld_tags.py:306-312`) | `lookup` → `_roll_by_code` owner+gudang (:65-76) | `create_write` (gudang roll dicek); `confirm/fail` hanya owner+perangkat | — |

Kesimpulan pagar: semua jalur kerja `/api/handheld/*` memeriksa PT **dan** gudang dokumen, kecuali (i) potong sampel
(gudang roll induk), (ii) sesi cek muat SO-lama tanpa gudang, (iii) registri/aktivitas perangkat (`wms.view` global),
(iv) jalur lama `/api/rfid/ingest` yang tetap menerima key handheld tanpa pengguna (H-01).

## (a) Tabel transisi

### A1. `rfid_devices` (type `handheld`)
| dari → ke | pemicu (endpoint + fungsi) | penjaga/CAS | efek | dibalik/kompensasi? | idempoten? | pagar PT/lokasi/perangkat |
|---|---|---|---|---|---|---|
| ∅ → `enabled=true`, `status=online`, key terbit | `POST /api/handheld/devices` → `devs.create` `handheld_devices.py:339-353` → `rfid.create_device` `rfid_service.py:208-229` (status `online` :225) → `ensure_api_key` `rfid_ingest_service.py:26-41` | `require_role(["admin"])` `routers/handheld.py:304`; kode unik cek-lalu-sisip `rfid_service.py:214-215` (indeks hanya `api_key_hash`, `indexes.py:45-47`) | dokumen + `handheld_scope_level/profile`; key polos tampil sekali (hash SHA-256); audit `handheld_device_created` | `DELETE /api/rfid/devices/{id}` (jalur lama) | tidak (tiap panggilan = perangkat baru) | gudang harus ada; tanpa pagar site admin |
| enabled → `online` + `last_heartbeat` | setiap panggilan handheld: `touch_device` `handheld_core.py:147-151` (dari `device_config` :155, `context` :217) | filter `enabled≠false` | `status`, `handheld_app_version` | — | ya | — |
| enabled → dicabut (`enabled=false`, `offline`, key dibuang) | `POST /api/handheld/devices/{id}/revoke` → `devs.revoke` `handheld_devices.py:365-376` | `require_role(["admin","warehouse_admin"])` `routers/handheld.py:321`; alasan ≥5 | `$unset api_key_hash`; sesi operator ditutup (:375); audit | `enable` + `rotate-key` | ya | **tanpa pagar site/gudang** untuk warehouse_admin |
| dicabut/nonaktif → `enabled=true` (tanpa key) | `POST .../enable` → `devs.enable` :379-384 | admin | `needs_new_key` | revoke | ya | — |
| key lama → key baru | `POST .../rotate-key` → `devs.rotate_key` :356-362 → `ensure_api_key(regenerate=True)` | admin | key lama mati seketika; `$unset revoked_*` (enabled tidak diubah) | — | tidak | — |
| profil/cakupan diubah | `PUT .../profile` → `devs.set_profile` :387-398 (`validate_profile` `handheld_core.py:128-144`) | admin | `handheld_scope_level` berlaku seketika di `context()` | ubah lagi | ya | — |
| (jalur lama) `type`/`enabled` diubah | `PATCH /api/rfid/devices/{id}` → `rfid_service.update_device` :232-251 | admin | `type` handheld↔gate bisa ditukar; sesi operator & niat tulis tidak disentuh | — | ya | — |

### A2. `handheld_operator_sessions` (`OPS`, `handheld_core.py:31`)
| dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|
| ∅ → terbuka (`ended_at=None`) | `POST /api/handheld/session/start` → `start_operator` `handheld_core.py:238-247` | device key + Bearer; **tanpa izin** (`context(request)` perm None, `routers/handheld.py:146`) | `warehouse_ids` snapshot (tak dipakai otorisasi); audit `handheld_operator_login` | logout | tidak (tiap login = sesi baru) | per perangkat |
| terbuka → berakhir "ganti operator" | `start_operator` :240-241 (`update_many` sesi terbuka perangkat) | — | — | — | ya | per perangkat |
| terbuka/berakhir → berakhir "logout" | `POST /api/handheld/session/end` → `end_operator` :250-256 | filter `id+device_id+user_id`, **tanpa `ended_at: None`** (menimpa) | audit | — | ya (menimpa) | perangkat+pengguna |
| terbuka → berakhir "perangkat dicabut" | `devs.revoke` `handheld_devices.py:375` | — | — | — | ya | — |
| (apa pun) → `last_seen_at` | `assert_operator` `handheld_core.py:269` | cek `device_id`+`user_id` saja; **sesi berakhir tetap lolos** | — | — | ya | — |

### A3. `handheld_requests` (penyimpan idempoten `once`, `handheld_sync.py:56-100`)
Lingkup: `batch` (:150), `complete` (:390-392), `cut` (:418-419), `tag-write` (`handheld_tags.py:119-120`),
`tag-confirm` (:184-185). **Tidak** lewat `once`: `fail_write`, `reserve_epcs`, `mark_written`, `label-decode`, `racks`.

| dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|
| ∅ → `processing` | `insert_one` :77-79 | `_id = <device_id>:<scope>:<key>` (unik bawaan `_id`); key 8–80 (:60-61) | meta: bacaan mentah ≤2000, jam perangkat, `clock_skew_ms`, operator | — | — | **per perangkat** (bukan per pengguna) |
| `processing` (<60 dtk) → tolak | `find_one` :65-73 | — | 409 `REQUEST_IN_PROGRESS` (retryable) | — | ya | — |
| `processing` basi (≥60 dtk) → diproses ulang | :71-75 `update_one({"_id"}, {$set started_ts})` | **tanpa CAS** started_ts / tanpa token pemilik | `fn()` dijalankan lagi (bisa paralel dengan proses asli) | — | bergantung layanan bawah | — |
| `processing` → `done` (`accepted`/`conflict`/`rejected`) | :91-99 (4xx bisnis disimpan final, 409→conflict, lain→rejected) | `update_one({"_id"})` tanpa syarat status/pemilik (penulis terakhir menang) | `result`, `result_status`, `processing_ms` | — | ya | — |
| `processing` → dihapus | 5xx/401/429/`SAGA_IN_PROGRESS`/`REQUEST_IN_PROGRESS` :88-90; `BaseException` :93-95 | `delete_one({_id, status:"processing"})` — bisa menghapus milik pelari lain | perangkat mengulang | — | — | — |
| `done` → putar ulang | digest sama :69-70 (`replay:true`, hasil identik termasuk `server_time` lama); digest beda → 409 `IDEMPOTENCY_CONFLICT` :67-68 | digest batch = kind, doc_id, session_id, labels, lines, bin_id, label_reason, user_id, simulated, set EPC kanonik (:153-157) — jam/versi/operator_session_id tidak ikut | — | — | ya | pengguna lain di perangkat sama bisa memutar ulang (digest tanpa `ctx.user`) |

### A4. Dokumen bisnis lewat handheld
| dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|
| PA item `pending → arrived`; PA `open/in_transit → partially_received → completed` | `POST /api/handheld/batches` kind `putaway_in` → `_batch_pa` `handheld_sync.py:187-225` → `confirm_arrival_trip` `putaway_arrival_service.py:186-236` | status `ARRIVAL_STATUSES`; klaim saga PA (:208-209); trip dedupe `client_trip_id=client_batch_id` (:201-204, :212-215); hanya EPC milik item dikirim (`handheld_sync.py:196-199`) | `arrival_trips[]` (`source.type=handheld`), journey roll; `gate_session_hook` → `gate_txn_service.safe_close("putaway",…)` (:239-243); audit `putaway_arrival_trip` | `close_remaining` (web) untuk sisa | ya | owner∈E, `to_warehouse_id∈W` |
| roll transfer `in_transit_transfer → received/hold/damaged`; transfer `dispatched → partially_received → …` | batch `transfer_in` → `_batch_transfer` `handheld_sync.py:228-283` → `trs.receive` `transfer_receipt_service.py:256-335` | `_land` CAS per roll; "already" bila sudah; aturan gudang → `blocked_rules`; label untuk roll bertag → `needs_rfid` | `receipt_events`, exception `rule_violation`, `place_roll` ke `bin_id` (divalidasi :262-264); audit `transfer_received` | — | ya per roll (receipt_events/audit ganda bila diulang) | `dest_warehouse_id∈W`, PT transfer∩E |
| ∅ → sesi `rfid_verify_sessions` `open` (loading_check / cycle_count / print_verify) | `GET /api/handheld/tasks/{kind}/{doc_id}/expected?start=true` → `start_session` `handheld_tasks.py:304-323` → `lc.start` `loading_check_service.py:55-99` / `cc.start` `cycle_count_service.py:17-57` / `rps.start_verify` `rfid_print_service.py:645-679` | cek-lalu-sisip (`:63/:98`, `:22/:56`, `:663/:678`), **tanpa indeks unik sesi terbuka**; GET bermutasi | sesi + `expected`; audit `handheld_session_opened` | — | "idempoten" hanya tanpa balapan | gudang doc_id ∈ W; PT |
| sesi `open`: `scanned_epcs` bertambah, `scan_sources` += device/simulated | batch sesi → `_batch_session` `handheld_sync.py:307-333` → `rps.scan_session` `rfid_print_service.py:583-610` (per 500) | `status=open` & tanpa `saga_lock` (:607-610); owner sesi ⊆ E (:595-598) | `$addToSet scanned_epcs`, `simulated_epcs` bila simulasi; label cek muat → `lc.scan_label` (izin `wms.untagged_override`, alasan ≥5) | — | ya ($addToSet) | via `_session_for` |
| sesi `open → completed` (`clean`/`with_issues`/`simulated`) | `POST /api/handheld/tasks/{kind}/{doc_id}/complete` → `sync.complete` :357-392 → `lc.complete` :100-129 / `cc.complete` :70-142 / `complete_verify` `rfid_print_service.py:682-` | klaim saga sesi; sudah selesai → `already_completed` | SO `loading_checks[wh]` (manifest); `rfid_cycle_counts`; print job `verified/verified_with_issues`, journey `tag_verified`, `journey.verified_tag_id`; audit | — | ya (once + status) | via `_session_for` |
| tugas `sample_cut` `created/picking → packing`; roll induk −take; roll anak `reserved` lahir | `POST /api/handheld/tasks/cutting/{task_id}/cut` → `sync.cut` :402-419 → `cut_sample_task` `sample_sale_service.py:399-490` | klaim saga tugas (:426); CAS roll `available` & panjang (:427-431); `_resolve_roll` produk+status+PT (:291-316) | movement `sample_cut`, `rebuild_balance`, SO allocations/items, reprice + payment_after_reprice; `wms_tasks.warehouse_id := gudang roll` (:473); audit `sample_cut` | — | ya (once + saga) | gudang **tugas** ∈ W; **gudang roll tidak dicek** |
| baris Daftar Awal ∅ → `draft` (`live`) | batch `registration` → `tags.process_lines` `handheld_tags.py:225-284` → `irl.add_line` `initial_registration_lines.py:257-275` | sesi `running`; bin ∈ sesi (:183-184); owner ∈ E (:185-187); EPC unik `uq_reg_live_epc`; cadangan milik perangkat+sesi (`handheld_tags.py:252-259`) | `hh_client_line_id/hh_device_id/hh_captured_at` (:268-269, update terpisah) | void (web) | ya (prior EPC+cid → saved :245-249) | sesi gudang ∈ W |
| baris `tag_state pending_write → written`; tag baris terapan `pending_print → active` | `POST /api/handheld/registration/{sid}/lines/mark-written` atau `lines[].written=true` → `irl.mark_written` `initial_registration_lines.py:306-321` | baris sesi & `pending_write` | `rfid_tags.status=active` (`update_many`) | — | ya | sesi gudang ∈ W; tanpa cek perangkat/operator/status roll |

### A5. Tulis EPC via handheld (`handheld_tags.py`)
| dari → ke | pemicu | penjaga/CAS | efek | dibalik/kompensasi? | idempoten? | pagar |
|---|---|---|---|---|---|---|
| niat ∅ → `pending` (EPC baru) | `POST /api/handheld/tag-writes` → `create_write` :84-120 | `assert_operator`; roll PHYSICAL & panjang>0 (:91-92); tanpa `active_movement` (:93-95); niat pending perangkat lain → 409 `WRITE_IN_PROGRESS` (:98-101) **cek-lalu-sisip, indeks `(roll_id,status)` tidak unik** (:42); `new_epc` cek tag hidup/baris hidup/cadangan/niat (:46-61) + `uq_hh_write_epc` (:41) | `purpose` new/replace, `old_tag_id/old_epc`, `expires_at` +24 j (:112) | `fail` | ya (once; niat pending perangkat sama dipakai ulang :102-103) | roll owner∈E, `warehouse_id∈W` |
| niat `pending → confirmed` | `POST /api/handheld/tag-writes/{id}/confirm` → `confirm_write` :132-185 | `_write_doc` owner∈E & perangkat sama (:123-129); EPC baca ulang == EPC niat (:144-146); `rfid_tag_id` roll == `old_tag_id` (:147-150); **tanpa cek `expires_at`, status roll, movement (purpose new)** | tag lama aktif → `retire_tag` (:155); tag lama `pending_print` → `retired` langsung (:156-160) **tanpa cek item print job**; `encode_tag(status=active)` (:162); `written_via/written_by_device_id/write_id` (:171-172); `journey.verified_tag_id/at` (:174-175); audit `rfid_tag_written_handheld`; **tanpa `rfid_tag_events`** | kompensasi bila `encode_tag` gagal: tag lama `active` dipulihkan (:163-169) — `pending_print` & `journey.verified_tag_id` tidak dipulihkan | ya (once; `already_confirmed` :140-141) | owner∈E (gudang tidak dicek ulang) |
| niat `pending → failed` | `POST /api/handheld/tag-writes/{id}/fail` → `fail_write` :188-195 | `_write_doc`; **tanpa `assert_operator`, tanpa once** | EPC hangus (tidak pernah dipakai lagi: `uq_hh_write_epc`) | — | ya (`unchanged`) | perangkat sama |
| niat `pending → kedaluwarsa` | **tidak ada** (`expires_at` hanya ditulis :112, tidak pernah dibaca) | — | — | — | — | — |
| `rfid_tags` ∅ → `active` | `rfid_service.encode_tag` :92-136 (dari confirm) | `uniq_live_epc` (dibuat bootstrap bila bersih, `rfid_service.py:469-475`, `bootstrap.py:1656`); CAS roll `rfid_tag_id∈[None,""]` (:129-131) | roll `rfid_tag_id`, `tracking_mode=rfid` | kalah CAS → tag baru dihapus (:132-135) | — | owner∈E |
| `rfid_tags` `active → retired` | `rfid_service.retire_tag` :151-188 | tolak bila roll `active_movement` (:157-164); CAS `status=active` (:167-169) | roll `rfid_tag_id=None`, `tracking_mode=barcode`, `$unset journey.verified_tag_id` (:174-177); **tanpa `retire_reason/retired_by/replaced_by_tag_id`** | kompensasi `retired → active` (`handheld_tags.py:165-168`) | — | owner∈E |
| `rfid_tags` `pending_print → retired` | `handheld_tags.py:157-160` | filter `status=pending_print` | roll dilepas | tidak | — | — |
| `rfid_tags` `pending_print → active` | `irl.mark_written` `initial_registration_lines.py:318-320` | `status=pending_print` | `activated_at/by` | — | ya | — |

### A6. Cadangan EPC Daftar Awal (`handheld_epc_reservations`)
| dari → ke | pemicu | penjaga/CAS | efek | dibalik? | idempoten? | pagar |
|---|---|---|---|---|---|---|
| ∅ → `reserved` | `POST /api/handheld/registration/{sid}/epc-pool` (`PoolIn.count` 1–200) → `reserve_epcs` `handheld_tags.py:199-218` | sesi `epc_mode=system` & `running`; isi sampai `count` per (perangkat, sesi) — hitung lalu sisip (non-atomik); `uq_hh_pool_epc` | daftar EPC ke perangkat; audit `registration_epc_reserved` | **tidak ada pelepasan** | ya (kira-kira) | sesi gudang ∈ W |
| `reserved → used` | batch `registration` → `process_lines` :252-273 | cadangan milik perangkat+sesi; `used` oleh baris lain → conflict | `line_id`, `client_line_id` | — | ya | — |

Jumlah transisi terdokumentasi: A1 7 · A2 5 · A3 6 · A4 8 · A5 9 · A6 2 = **37**.

## (b) Kandidat anomali (handheld)

**H-01 — Key handheld masih diterima jalur lama `/api/rfid/ingest` tanpa sesi pengguna, tanpa pagar PT/operator.** (tinggi · pasti dari kode)
`routers/rfid.py:605-613` hanya `ing.authenticate` (tanpa cek tipe); `rfid_ingest_service.py:136` menerima `type="handheld"`;
`ingest_into_session` :308-320 memanggil `scan_session(..., scope_ids=None, kinds=[print_verify, loading_check, cycle_count], source="device")`
→ cek PT di `rfid_print_service.py:595-598` dilewati; cek gudang (:314) hanya bila sesi punya `warehouse_id` dan
dibanding gudang induk perangkat (bukan site). Tanpa `session_id` → `rfid_reads` "inventory" + `rfid_tags.last_seen_*` untuk EPC
PT mana pun. Bandingkan V2 yang menolak handheld (`routers/rfid_v2.py:79-80`) dan printer (`rfid_printer_protocol.py:103`).
Dampak: key C72 (QR provisioning, unit bisa hilang) cukup untuk menyuntik pindai bertanda "device" ke sesi cek muat SO-lama
(tanpa gudang) PT lain / opname / verifikasi cetak, melewati izin & cakupan `/api/handheld`. Rujuk SSOT-6, FRM-12/13.

**H-02 — `once()` mengambil alih `processing` basi tanpa CAS & tanpa token pemilik.** (tinggi · mekanisme pasti, dampak perlu runtime)
`handheld_sync.py:71-75` (`update_one({"_id"}, $set started_ts)` tanpa filter started_ts lama), :88-90 (pelari yang kena
galat sementara menghapus catatan `processing` siapa pun), :97 (`update_one` tanpa upsert/tanpa syarat → penulis terakhir
menang). Skenario: batch 2000 bacaan transfer/PA berjalan >60 dtk, perangkat (sinkron 15 dtk) mengirim ulang → `fn()` jalan
dua kali; pelari kedua kena `SAGA_IN_PROGRESS` → menghapus catatan → hasil pelari pertama tidak tersimpan → kiriman ketiga
menjalankan lagi. Efek stok tertahan oleh `client_trip_id`/CAS per roll/saga, tetapi `receipt_events`, audit, exception
`rule_violation` bisa ganda dan hasil final per item bisa salah ("already"/"conflict" untuk efek yang sukses; potong →
"Sample sudah dipotong"). Kunci idempoten per perangkat, bukan global.

**H-03 — Niat tulis tag tidak pernah kedaluwarsa & hanya bisa ditutup perangkat pemiliknya → roll terkunci.** (sedang-tinggi · pasti dari kode)
`handheld_tags.py:32,112` (TTL hanya ditulis), :98-101 (perangkat lain → `WRITE_IN_PROGRESS`), :123-129 (confirm/fail wajib
perangkat sama), `handheld_devices.py:365-376` (revoke tidak menutup niat). Tidak ada endpoint admin/penyapu. Dampak: C72
hilang/rusak/dicabut saat ada niat `pending` → roll tidak bisa diberi tag lewat C72 lain selamanya.

**H-04 — Konfirmasi tulis memensiunkan tag `pending_print` yang masih ada di print job aktif.** (sedang-tinggi · pasti dari kode; urutan perlu runtime)
`handheld_tags.py:156-160` tanpa padanan `_job_items_with_tag` (bandingkan `rfid_print_service.py:995-999` replace_tag dan
:245 create_print_job). Printer tetap mencetak item lama; `_item_effects` :485-487 no-op tetapi `tag_event "activated"`
tetap ditulis (:494-496). Dampak: label fisik ber-EPC pensiun beredar (UNKNOWN_EPC di gate), riwayat tag menyatakan aktif.

**H-05 — Ganti tag via C72 tidak setara PREP-F: tanpa `rfid_tag_events`, `retire_reason`, `replaced_by_tag_id`; tiga pengalokasi EPC.** (sedang · pasti dari kode)
`confirm_write` memakai `rfid_service.retire_tag/encode_tag` (`rfid_service.py:151-188`, :92-136) — bukan
`_retire_live_tag`/`replace_tag` (`rfid_print_service.py:823-842`, :977-1033). `GET /api/rfid/rolls/{roll_id}/tag-history`
tidak menampilkan penggantian C72. EPC dialokasikan tiga cara berbeda: `allocate_epc` (tidak ada di `rfid_tags` status apa
pun, `rfid_print_service.py:155-161`), `handheld_tags.new_epc` (cek tag **hidup** + baris + cadangan + niat, :46-61),
`_new_system_epc` Daftar Awal — tak satu pun memeriksa ruang milik yang lain secara penuh; "EPC pensiun tidak pernah dipakai
ulang" di jalur C72 hanya dijamin keacakan 88 bit, bukan oleh pemeriksaan. Rujuk SSOT/B3a.

**H-06 — Potong sampel C72 tidak memagari gudang roll induk.** (sedang · pasti dari kode)
`handheld_sync.py:408-410` → `cutting_task` hanya gudang **tugas** (`handheld_tasks.py:372-377`); `_resolve_roll`
`sample_sale_service.py:291-316` tidak cek `warehouse_id`; cut menimpa `wms_tasks.warehouse_id` dengan gudang roll (:473).
Kandidat `_exp_cutting` tanpa filter PT (`handheld_tasks.py:383-386`). Lookup EPC di `_resolve_roll` :295 tanpa filter status
tag (tag pensiun ber-EPC sama bisa menang — K-OPN-05). Dampak: operator gedung A memotong (di data) roll gedung/site lain;
movement & `rebuild_balance` di gudang di luar cakupan perangkat/lokasi kerja.

**H-07 — `simulated` di batch sesi tidak dipagari `wms.rfid_simulation`; hasil `simulated` dihitung sah oleh penutupan sesi gate.** (sedang · pasti dari kode; dampak dispatch perlu runtime)
`handheld_sync.py:131-133, 316` (hanya ditolak untuk PA/transfer/daftar awal); `rfid_print_service.py:603-604, 623-626`
(satu pindai simulasi menodai seluruh sesi); `loading_check_service.py:116-119`; `gate_txn_service.py:400` menganggap
`result ∈ {clean, override, simulated}` sebagai bukti `loading_check` saat menutup sesi dokumen gate. Bandingkan simulator V2
yang wajib setelan per PT (`gate_txn_service.py:123-131`). Dampak: (i) satu batch simulasi dari C72 (mode diagnostik ber-PIN)
membuat cek muat nyata berakhir `simulated` (dispatch tertahan); (ii) bukti tiruan membuat roll SJ tidak "kurang" saat sesi
gate ditutup — bertentangan RF-07.

**H-08 — Sesi operator opsional; sesi berakhir tetap diterima → `OPERATOR_MISMATCH` hanya penasihat.** (sedang · pasti dari kode)
`handheld_core.py:259-270` (`op_id`/`user_id` opsional; tidak cek `ended_at`); model `routers/handheld.py:47-50, 65-67`.
Dampak: mutasi tanpa `operator_session_id` (jejak siapa-perangkat-apa kosong); antrean sesi logout/"perangkat dicabut" (lalu
diaktifkan ulang) tetap diterima. Bukti tetap terikat pengguna token.

**H-09 — Registri & jejak perangkat bocor lintas PT/site untuk siapa pun ber-`wms.view`; revoke tanpa pagar site.** (sedang · pasti dari kode)
`routers/handheld.py:295-299` (`list_devices()` tanpa `warehouse_ids`), :344-347 → `handheld_devices.py:401-409`
(`handheld_requests`: doc_id, kind, user_name, `result.error/doc/trip`; `handheld_tag_writes`: roll_no, sku, epc,
owner_entity_id). `revoke` oleh `warehouse_admin` site mana pun (:321). Pola sama B3a SCP-1.

**H-10 — Sesi cek muat SO-lama tanpa gudang menembus pagar gedung.** (sedang · pasti dari kode, perlu data sesi lama)
`handheld_tasks.py:294` (`warehouse_id ∈ [wid, None]`), `handheld_sync.py:299-303` (pengecualian `warehouse_id is None`),
`loading_check_service.py:20-25`. `doc_guard` hanya memeriksa `wid` dari doc_id; `expected` sesi lama mencakup roll SO di
semua gudang. Dampak: cek muat & selesai untuk roll gedung lain dari C72 di luar cakupannya.

**H-11 — "Mulai sesi" cek-lalu-sisip tanpa indeks unik; dua C72 → dua sesi terbuka (MKO).** (sedang-rendah · perlu runtime)
`handheld_tasks.py:357-358` → `loading_check_service.py:63-98`, `cycle_count_service.py:22-56`, `rfid_print_service.py:663-678`.
Mutasi lewat `GET`. Dampak: pindai terbelah ke dua sesi; satu tidak pernah ditutup (sesi yatim, `find_session` acak).

**H-12 — Batch saat sesi diselesaikan (saga) disimpan sebagai penolakan FINAL; batch >500 sebagian diterapkan lalu "rejected".** (rendah-sedang · pasti dari kode)
`rfid_print_service.py:607-610` (400 string) → `handheld_sync.py:88-92` (bukan TRANSIENT), loop per 500 :317-319.
Dampak: perangkat berhenti mengirim; hasil per item hilang walau sebagian pindai masuk.

**H-13 — Konfirmasi "new" tanpa cek ulang movement/status roll; kompensasi tak lengkap.** (rendah-sedang · pasti dari kode)
`handheld_tags.py:147-169`; `rfid_service.encode_tag` :92-104 tanpa cek `active_movement`; retire `$unset
journey.verified_tag_id` (:176-177) tidak dipulihkan kompensasi; `PHYSICAL_STATUSES` memuat `in_transit_sales/
in_transit_transfer` (`rfid_service.py:22-23`). Dampak: roll yang mulai bergerak sesudah niat dibuat mendapat EPC baru di
tengah perjalanan → EPC tidak ada di snapshot dokumen (PA/transfer/SJ) → "extra"/kurang di gate.

**H-14 — Roll dengan `rfid_tag_id` menggantung tak bisa ditulis via C72.** (rendah · pasti dari kode, bergantung data)
`handheld_tags.py:96-97` (`old=None` bila tag tak hidup) vs :148-150 (`ROLL_TAG_CHANGED` selalu) dan `encode_tag` :100-101.
Niat dibuat (EPC hangus), konfirmasi selalu konflik. Kasus "tag_id menggantung" diakui `loading_check_service.py:82-84`.

**H-15 — Dua niat `pending` untuk roll sama bisa lahir (balapan).** (rendah · perlu runtime)
`handheld_tags.py:42` (indeks tidak unik), :98-117. Konfirmasi kedua tertahan (`ROLL_TAG_CHANGED`/CAS encode) — satu chip
fisik ber-EPC hangus.

**H-16 — Daftar Verifikasi cetak memuat job `text_reprint` (start 400) & melewatkan job `partial`.** (rendah · pasti dari kode)
`handheld_tasks.py:162-163` vs `rfid_print_service.py:647-648` dan `compute_status` :369-372.

**H-17 — Label PA via C72 tidak pernah cocok padahal `labels_allowed: true`.** (rendah · pasti dari kode)
`handheld_sync.py:196-199` (pencocokan hanya EPC item), `handheld_tasks.py:248`, `putaway_arrival_service.py:108`.
Roll PA tanpa tag dilaporkan "Bukan roll PA ini".

**H-18 — Lain-lain (rendah · pasti dari kode):** `reserve_epcs` non-atomik → >200 cadangan saat paralel
(`handheld_tags.py:207-215`), cadangan tak pernah dilepas; `untagged` memotong `limit` sebelum filter gudang (:311-312);
`end_operator` menimpa `ended_at` (`handheld_core.py:251-253`); `handheld_requests` tanpa TTL/pembersihan (≤2000 bacaan per
batch, ±6000 roll/hari); `fail_write` tanpa `assert_operator` (`handheld_tags.py:188-195`); `session/start` tanpa izin;
kode perangkat unik cek-lalu-sisip (`rfid_service.py:214-215`); replay hasil per perangkat tanpa pagar ulang pengguna
(`handheld_sync.py:64-70`); mode Daftar Awal `read` (EPC bawaan) masih diterima walau K-OPN-05 (perlu keputusan, bukan bug).

## (c) Resep uji runtime

Header: **perangkat** = `X-Device-Key: dk_…`; **pengguna** = `Authorization: Bearer <token>`. Endpoint kerja butuh
keduanya; `/device/config` hanya key; `/devices*` hanya Bearer. Galat terstruktur `detail.code`
(`handheld_core.py:70-73`). Hasil bisnis final = HTTP 200 `status: accepted|conflict|rejected`.

**R0. Persiapan (baca-saja dulu)**
1. `POST /api/auth/login` `{"email":"admin@kainnusantara.id","password":"<sandi demo — AGENTS.md>"}` (`schemas.py:161-163`, `routers/auth.py:93`)
   → `token`. Operator: `warehouse@kainnusantara.id` (peran `warehouse`: wms view/update/scan, inventory.cycle_count,
   transfer.update, `permissions_config.py:408-440`; dibatasi lokasi bila `wms.location_scope_enforced`). Supervisor:
   `wh.admin@kainnusantara.id` (warehouse_admin, punya `wms.untagged_override`). Sandi semua `<sandi demo — AGENTS.md>`.
2. Gudang & site: `GET /api/warehouses`, `GET /api/warehouse-sites`; pilih gudang ber-`site_id` (cakupan perangkat
   = semua gudang aktif satu site, `handheld_core.py:107-115`). Lokasi kerja operator: `users.location_site_ids/
   location_warehouse_ids` (`location_scope.py:48-57`).

**R1. Daftar perangkat + key**
1. `POST /api/handheld/devices` (admin) body `DeviceCreateIn` (`routers/handheld.py:114-121`):
   `{"name":"C72 Uji B2b","warehouse_id":"<WH>","code":"C72-B2B-01","scope_level":"site","profile":{},"base_url":""}`
   → `device.id`, `api_key` (sekali), `provisioning.qr_text`. Ulang dengan `code` sama → 409; `scope_level:"x"` → 400.
   Perhatikan `device.status` langsung `online` (FRM-12).
2. `GET /api/handheld/device/config` hanya `X-Device-Key` → `device.warehouses`, `profile`, `kinds` (8). Tanpa key → 401
   `DEVICE_KEY_REQUIRED`; key gate → 403 `DEVICE_NOT_HANDHELD`. `GET /api/handheld/me` hanya Bearer → 401 `DEVICE_KEY_REQUIRED`.

**R2. Login operator / ganti operator**
1. `POST /api/handheld/session/start` (key + Bearer operator) `{"app_version":"0.1.0-lab"}` (`AppVersionIn` :25-26) →
   `operator_session.id` (`hos_…`), `warehouses` (= W), `location_restricted`.
2. Ulang dengan Bearer `wh.admin` → sesi operator pertama `ended_at` terisi (`handheld_operator_sessions`).
3. `POST /api/handheld/session/end` `{"operator_session_id":"<hos>","reason":"uji"}` (`SessionEndIn` :29-31).

**R3. Daftar tugas & yang diharapkan**
1. `GET /api/handheld/tasks/summary`; `GET /api/handheld/tasks?kind=putaway_in&q=&limit=100` (kind: putaway_in,
   outbound_so, outbound_sample, transfer_in, cutting, cycle_count, print_verify, registration). Pengguna tanpa izin (mis.
   `driver@`) → 403 `PERMISSION_DENIED`. Uji pagar: operator site lain + key ini → `warehouses: []`, daftar kosong; doc gudang
   lain langsung → 403 `SCOPE_DENIED`.
2. `GET /api/handheld/tasks/putaway_in/<pa_id>/expected?offset=0&limit=5000` → `rows[].epc/state`, `version`.
   Sesi: `GET /api/handheld/tasks/outbound_so/<order_id>~<warehouse_id>/expected?start=true` → `session_id`
   (cycle_count: doc_id = warehouse_id; print_verify: doc_id = job id).

**R4. Batch → kirim ulang → konflik** — `POST /api/handheld/batches` (`BatchIn` `routers/handheld.py:43-61`, `ReadIn` :34-40):
```json
{"client_batch_id":"b2b-pa-0001-aaaa","kind":"putaway_in","doc_id":"<pa_id>","operator_session_id":"<hos>",
 "snapshot_version":"<version>","device_time":"2026-11-09T01:00:00Z","clock_offset_ms":0,"clock_synced":true,
 "reads":[{"epc":"<EPC item 1>","rssi":-55.5,"count":3},{"epc":"E2FFFFFFFFFFFFFFFFFFFFFF"}],"labels":[],"simulated":false}
```
- Harapan: `status:"accepted"`, item `arrived` + `extra`, `replay:false`; DB `putaway_orders.arrival_trips[-1].source.client_trip_id`
  = `client_batch_id`; `handheld_requests._id = <device_id>:batch:b2b-pa-0001-aaaa`.
- Kirim ulang badan sama (boleh ganti `device_time`) → `replay:true`, `items` identik, jumlah trip tetap.
- ID sama, `reads` beda → 409 `IDEMPOTENCY_CONFLICT`. Dua kiriman paralel ID baru sama → satu 200, satu 409 `REQUEST_IN_PROGRESS`.
- Konflik final: setelah PA `completed`, batch ID baru → 200 `status:"conflict"`, `error.code:"DOC_CLOSED"`.
  `simulated:true` untuk putaway_in → `SIMULATION_NOT_ALLOWED`.
- `OPERATOR_MISMATCH`: `operator_session_id` milik operator lain (Bearer wh.admin) → 409; `"user_id":"<id lain>"` → 409.
- **H-08**: hapus `operator_session_id` & `user_id` → tetap `accepted`; pakai `hos` yang sudah logout → tetap `accepted`.
- Transfer: kind `transfer_in`, doc_id transfer `dispatched`; `labels:["<roll_no bertag>"]` → `needs_rfid`; `bin_id` opsional.
- Sesi: kind `cycle_count`, `"session_id":"<rvs>"` wajib (tanpa → `rejected` `SESSION_REQUIRED`).
- **H-07**: kind `outbound_so` + `session_id` + `simulated:true` (PT dengan `wms.rfid_simulation` MATI) → `accepted`; lalu
  `POST /api/handheld/tasks/outbound_so/<order>~<wh>/complete` `{"client_request_id":"cmp-0001-aaaa","operator_session_id":"<hos>","session_id":"<rvs>"}`
  (`RequestIn` :64-68) → `result:"simulated"`; cek `sales_orders.loading_checks.<wh>.result` & efeknya pada dispatch/penutupan sesi gate.
- **H-12**: kirim batch sesi tepat saat `complete` berjalan (atau `rfid_verify_sessions.saga_lock` ada) → `status:"rejected"` final.
- **H-02** (DB uji): ukur `handheld_requests.processing_ms` untuk batch 2000 bacaan; bila >60000, kirim ulang paralel
  setelah 60 dtk dan bandingkan `result` tersimpan vs efek nyata (`receipt_events`, audit ganda).

**R5. Potong sampel** — `POST /api/handheld/tasks/cutting/<task_id>/cut` (`CutIn` :71-75):
`{"client_request_id":"cut-0001-aaaa","operator_session_id":"<hos>","roll_id":"<roll>","actual_length":1.5,"reason":"uji"}`.
**H-06**: `roll_id` roll produk sama, PT sama, `available`, di gudang LAIN (di luar W) → harapan bug: `accepted`;
cek `wms_tasks.warehouse_id` berubah ke gudang roll & `inventory_movements.sample_cut`.

**R6. Tulis tag / ganti tag**
1. `POST /api/handheld/tag-writes` (`TagWriteIn` :78-81) `{"client_request_id":"tw-0001-aaaa","code":"<roll_no|EPC>","operator_session_id":"<hos>","reason":"tag rusak"}`
   → `write.id`, `write.epc`, `purpose`.
2. `POST /api/handheld/tag-writes/<id>/confirm` (`TagConfirmIn` :84-89)
   `{"client_request_id":"tc-0001-aaaa","verified_epc":"<write.epc>","operator_session_id":"<hos>","rssi":-40,"attempts":1,"write_power_dbm":10}`
   → tag lama `retired`, tag baru `active`, `journey.verified_tag_id`. EPC salah → `VERIFY_MISMATCH`.
3. `POST /api/handheld/tag-writes/<id>/fail` (`TagFailIn` :92-94) `{"reason":"tag rusak","attempts":3}`.
- **H-03**: niat dari perangkat A → `revoke` A → niat dari perangkat B roll sama → `conflict WRITE_IN_PROGRESS` (selamanya).
- **H-04**: `POST /api/rfid/print-jobs` `{"roll_ids":["<roll tanpa tag>"],"kind":"rfid_tag"}` (`routers/rfid.py:61-64`) →
  tag `pending_print`; lalu tulis+konfirmasi via C72 (purpose replace, old = pending_print) → `POST /api/rfid/print-jobs/<job>/mark-printed`
  → `GET /api/rfid/rolls/<roll>/tag-history`: event `activated` untuk tag `retired`.
- **H-05**: setelah R6.2, `GET /api/rfid/rolls/<roll>/tag-history` → tidak ada event retired/replacement dari C72.
- **H-14**: roll dengan `rfid_tag_id` menunjuk tag `retired` → create OK, confirm → `ROLL_TAG_CHANGED`.

**R7. Daftar Awal (EPC sistem)** — sesi `registration` `running` (`epc_mode:"system"`):
`POST /api/handheld/registration/<sid>/epc-pool` `{"count":50}` → `epcs`; batch kind `registration`, doc_id `<sid>`,
`lines:[{"client_line_id":"ln-0001","epc":"<cadangan>","product_id":"<pid>","qty":30,"unit":"meter","bin_id":"<bin sesi>","owner_entity_id":"ent_ksc","written":true}]`
(`FORM_KEYS` `handheld_tags.py:221-222`) → `saved`, `tag_state:"written"`. EPC cadangan perangkat lain → `conflict`.

**R8. Cabut perangkat** — `POST /api/handheld/devices/<id>/revoke` `{"reason":"unit hilang uji"}` → key lama 401
`DEVICE_KEY_INVALID`; sesi operator `ended_at`; `POST .../enable` → `needs_new_key:true`; `POST .../rotate-key` → key baru.
**H-09**: `GET /api/handheld/devices` & `GET /api/handheld/devices/<id>/activity` dengan pengguna ber-`wms.view` PT/site lain.

**R9. Jalur lama dengan key handheld (H-01)** — hanya `X-Device-Key: <key C72>`, TANPA Bearer:
`POST /api/rfid/ingest` (`IngestPayload` `routers/rfid.py:583-587`) `{"epcs":["<EPC>"],"session_id":"<rvs loading_check SO-lama tanpa warehouse_id / print_verify>"}`
→ harapan bug: 200 progres sesi (scan_sources `device`). Tanpa `session_id` → `rfid_reads` `read_type:"inventory"` &
`rfid_tags.last_seen_device_id` = C72. `POST /api/rfid/heartbeat` → `status: online`.
