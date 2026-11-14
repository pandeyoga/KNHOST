# AG-T1 — Asisten: rapikan kartu tindakan yang ada dan pasang lapisan penyedia model

- Commit awal: `b5b7539` (dikerjakan) · digabung pelaksana di atas `f05d8da`        - Commit: `3e1a42c`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: AG-01, AG-02, AG-04, AG-05
- Keputusan: K-43 (lapisan penyedia yang bisa berganti — bagian penyamaran nama `ai.samarkan_nama` milik AG-T2), K-44
  (kartu disetujui satu orang = pembuatnya; unit ini tidak punya aksi uang keluar/jurnal, jadi `kontrol.asisten_uang_keluar.*`
  belum dipakai) · Standar: `02` §2.1, §2.4, §3.4 (N1, N3, N5), §4 (L1, L4), §5 (D9), §6 · Risiko sedang (satu serah-terima)
- Prasyarat: PK-02 (kerangka `tests_mem`) — ada di HEAD

## Cek ulang "Keadaan sekarang" (di `b5b7539`; blueprint dibaca di `3132cc4`)

| # | Hasil |
|---|---|
| 1 | Berlaku: `ai_actions.py:19` (`TYPES`) |
| 2 | Berlaku: klaim `ai_actions.py:204`, pemulihan ke `pending` `:210` |
| 3 | Berlaku: `_exec_po` `:158`, satu PO per pemasok dalam satu putaran `:167` (U1/U2 merah: ulang setujui membuat PO ke-2 dan ke-3) |
| 4 | Berlaku, bergeser: izin `:161`, "semua qty nol" `:165` — keduanya di dalam `_exec_po`, sesudah klaim (U11 merah: `running` lalu `pending`) |
| 5 | Berlaku: `propose_action` dokumen `:131` tanpa masa berlaku |
| 6 | Berlaku: `:127` (`sc.entity_ids[0]` pada mode Semua PT; U10 merah: kartu lahir) |
| 7 | Berlaku: `routers/ai_assist.py:20` (`confirm_action` tanpa `entity_ctx`; U8/U9 merah: PO dibuat di PT kartu dari PT aktif lain) |
| 8 | Berlaku: `ai_tools.py:364-366` |
| 9 | Berlaku: `ai_tools.py:378` (`cands[:5]`) |
| 10 | Berlaku: enum `tools_kn_analitik_v1.json:842`, pelaksana `ai_tools.py:397` (7 jenis) |
| 11 | Berlaku: enum `:642` (19), `hr_summary` jatuh ke peringatan `ai_tools.py:355` |
| 12 | Berlaku: enum `:803` (9), pelaksana `ai_tools.py:361` (5 jenis) |
| 13 | Berlaku, bergeser: `ai_chat_service.py:202` (bukan 199) dan `:332` (`job_ai_prewarm` `:323`); `ai_narrative.py:85` |
| 14 | Berlaku: `_is_mock` `ai_chat_service.py:65` |
| 15 | Berlaku: `ai_cost.py:12` (`PRICES`) |
| 16 | Berlaku, bergeser: `ai.enabled` di `config_catalog_ai.py:51`/`:53` (bukan 40); pesan layar `ai_chat_service.py:176` (bukan 173), `:198` (mode uji) dan `frontend/.../TanyaRulesStrip.jsx:21` ("Menunggu kunci …") |
| 17 | Berlaku: `TanyaActionCard.jsx:8` |
| 18 | Berlaku, bergeser: `entity_scope.py:262` (bukan 252). Akibatnya uji lapis A lama `backend/tests/test_registry_ai_collections.py` merah di HEAD (lihat "Temuan di luar lingkup") |
| (alat) | `POST /api/ai/tools/{tool}` `routers/ai_analytics.py:105` (bukan 104) — dipakai uji untuk menyiapkan kartu |

## AG-01 — Kartu yang gagal di tengah kembali `pending` dan bisa diulang (PO ganda)

- Berlaku di HEAD: ya (U1, U2, U11 merah — `bukti/AG-T1/merah_kode_lama.log`).
- Akar masalah: klaim `pending → running` dijalankan sebelum pemeriksaan izin/isian, dan semua galat pelaksana
  memulihkan `pending`; PO yang sudah tersimpan tidak dicatat di kartu.
- Perubahan perilaku (sebelum → sesudah):
  - `confirm(pid, user, edits, ctx)` mengikuti tujuh langkah spesifikasi: muat (kedaluwarsa/proses mati diterapkan) →
    kedaluwarsa 409 → PT kartu ∉ akses 403 / PT aktif berbeda atau Semua PT 409 → izin & isian (`_po_siap`, galat tidak
    menyentuh status) → klaim atomik (`started_at`, `updated_at`, `result: []`) → jalankan, tiap nomor PO/pengingat
    langsung `$push` ke `result` → `confirmed`, atau `failed` + `error` (≤ 500, galat asli) + `finished_at`.
  - Galat pelaksana kini dijawab 200 dengan dokumen kartu `status: "failed"` dan `message` = "{galat asli}. Yang sudah
    dibuat: {nomor}." (bila ada hasil sebagian). Tidak ada transisi kembali ke `pending`.
  - Kartu `running` yang tak berubah > 10 menit (`RUNNING_STALE_MINUTES`, batas teknis) → `failed` "Proses berhenti sebelum
    selesai. Periksa daftar PO sebelum meminta draf baru." saat dibaca.
  - 403 izin PO memakai kalimat baku Z6 (`dependencies.denied`): "Anda belum punya akses untuk membuat Pesanan Pembelian
    (PO). Minta Admin menambahkan akses 'Pembelian & Pengadaan'." (dulu "Peran Anda tidak boleh membuat PO").
  - Jejak: `ai_action_failed` (baru) di samping `ai_action_confirmed`.
- Status: implemented_pending_review

## AG-02 — Kartu tanpa masa berlaku; PT kartu tidak diadu saat disetujui

- Berlaku di HEAD: ya (U5–U10 merah).
- Perubahan perilaku:
  - Pengaturan baru `ai.kartu_masa_berlaku_jam` (int 24, 1–168 jam, global + PT, izin `settings.manage`, risiko rendah,
    sub-judul baru "Tanya KN: kartu tindakan"). Kartu baru menyimpan `expires_at` = `created_at` + nilai PT kartu saat dibuat.
    Kartu lama tanpa `expires_at` dihitung dari `created_at` + nilai PT kartu SAAT dibaca (tidak disimpan; U7).
  - `propose_action` menolak mode Semua PT: 400 "Pilih satu PT dulu. Tindakan tidak bisa disiapkan dalam mode Semua PT."
    (tanpa dokumen kartu). PT kartu = PT aktif (N1).
  - `load` menerapkan kedaluwarsa (`pending` → `expired`, `finished_at`) dan menambah `entity_name` (nama pendek PT) pada
    jawaban. `dismiss` menolak kartu kedaluwarsa dengan pesan yang sama dengan `confirm` dan mengisi `finished_at`.
  - `POST /api/ai/actions/{pid}/confirm` meneruskan `entity_ctx(request)` (pernyataan pertama handler kini `_ai_user` —
    `verify_auth_coverage` turun 28 → 27).
- Status: implemented_pending_review

## AG-04 — Pencarian pemasok, gudang, dan sales oleh asisten lintas PT

- Berlaku di HEAD: ya (U12, U13, U13b merah).
- Perubahan: `find_entities` — `supplier` lewat `resolve_list_scope_inherit("suppliers", {}, ctx)` (PT cakupan + pemasok
  grup `all`); `warehouse` = `$or` dari `usable_query(PT)` untuk tiap PT cakupan; `sales_person` = akun sales yang
  `home_entity_id` atau `allowed_entity_ids`-nya beririsan dengan cakupan; `limit` dihormati (1–20, bawaan 5).
- Status: implemented_pending_review

## AG-05 — Skema alat menawarkan nilai yang tidak dilayani

- Berlaku di HEAD: ya (U14 merah: `get_document.doc_type` +4, `find_entities.kind` +4, `run_report.report` +1).
- Perubahan: nilai `delivery_note`, `tax_invoice`, `ar_receipt`, `roll`, `hr_summary`, `makloon_partner`, `category`,
  `entity`, `city` dicabut dari `enum` (format JSON sama, 2+/11−). Uji statik U14 membaca tabel pelayanan dari kode
  (`ast`, tanpa menjalankan) dan membandingkan dua arah: 7 · 18 · 5; ditambah `ops_metrics.kind` = `ai_ops_metrics.KINDS` dan
  `propose_action.action_type` = `ai_actions.TYPES`.
- Status: implemented_pending_review

## Lapisan penyedia model (Tujuan unit; K-43 bagian lapisan)

- `backend/services/ai_provider.py` (baru): `ToolCall`, `ModelTurn`, `ModelProvider` (Protocol: `run_turn`, `short_text`,
  `prewarm`, `price_of`), `tool_result(call_id, output)` (butir percakapan netral), pelaksana `ResponsesProvider` (satu-
  satunya tempat pustaka klien diimpor — impor malas di `_client`; awalan cache prompt, titik potong, `prompt_cache_key`,
  terjemahan `tool_result` → bentuk penyedia; butir lama `function_call_output` di riwayat sesi diteruskan apa adanya),
  tabel harga + `PRICE_VERSION` (angka tidak berubah; model tak dikenal = harga model utama, seperti dulu),
  `configured_provider()` (untuk status "kunci ada"), `active_provider()` (None bila `ai.enabled` mati atau tanpa kunci),
  `set_test_provider()`.
- `backend/services/ai_provider_fake.py` (baru): `ScriptedProvider(script)` — langkah `{"tool", "args"}`, `{"text"}`,
  `{"error"}` atau fungsi `(conversation) -> langkah`; `.calls` mencatat jenis, model, instruksi, daftar alat, salinan
  percakapan.
- Pemanggil dialihkan: `ai_chat_service._model_loop` (event SSE sama: `delta` diteruskan SELAGI giliran berjalan lewat
  antrean `_turn_events`; `delta_reset`, `status`, `tool`, `result`, `done` tidak berubah), `job_ai_prewarm`,
  `ai_narrative._ai_text`/`ai_available`; `status()` memakai `configured_provider()`. `ai_cost.cost_usd(model, usage,
  price)` — harga dari `provider.price_of(model)`; tanpa harga (mode uji/tiruan) = 0. `ai_chat_service.resolve_key` dihapus
  (pemanggil satu-satunya `ai_narrative` dialihkan; dicek `grep`).
- Teks netral: bantuan `ai.enabled`, dampak `ai.prewarm_enabled`, pesan "chat belum aktif", label mode uji, dan strip status
  Tanya KN kini menyebut "penyedia model". Nilai bawaan kunci tidak diubah.
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_AGT1_kartu.py` (19 uji) + `test_AGT1_penyedia.py` (4 uji). Di kode lama: 21 merah, 1 hijau (U3 —
diharapkan; U15c ditulis sesudahnya, merah karena modul lapisan belum ada) — `bukti/AG-T1/merah_kode_lama.log`; di kode
baru 23/23 hijau — `bukti/AG-T1/hijau_kode_baru.log`.

| ID | Lapis | Merah di kode lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | ya (400 "Periode tertutup", kartu kembali `pending`) | Lulus — 200 `failed`, `result` 1 nomor, `error` memuat "Periode tertutup", PO = 1 (2 pemasok → 2 panggilan; ke-2 dipaksa 400) |
| U2 | B | ya (200, PO jadi 3) | Lulus — 409 "Draf ini sudah diproses", PO tetap 1; abaikan juga 409 |
| U3 | B | tidak (perilaku lama benar) | Lulus — 200 `confirmed` lalu 409; PO = 1 |
| U4 | A | — | Ditulis: `backend/tests/test_bp_AGT1_kartu_bersamaan.py` (dua setujui bersamaan → [200, 409], PO = 1). **Lulus** di lingkungan A |
| U5 | B | ya (200 `confirmed`, PO dibuat) | Lulus — 409 pesan kedaluwarsa, DB `expired`, PO = 0 |
| U5b | B | ya (200 `dismissed`) | Lulus — abaikan kartu kedaluwarsa 409 pesan sama, DB `expired` |
| U5c | B | ya (`expires_at` tidak ada) | Lulus — `expires_at − created_at` = 24 jam; GET `entity_name` "Sukacita" |
| U6 | B | ya (`pending`) | Lulus — kartu lama 30 jam, bawaan 24 → `expired` (juga di DB) |
| U7 | B | ya (kunci tidak ada, 404) | Lulus — 48 khusus `ent_ksc`: KSC `pending`, Kanda `expired` |
| U6b | B | ya (`running` selamanya) | Lulus — `running` 11 menit tanpa perubahan → `failed` pesan proses mati; setujui 409 |
| U8 | B | ya (200 dari `ent_kanda`, PO di KSC) | Lulus — `ent_kanda` dan `all` → 409 "Draf ini disiapkan untuk Sukacita. Pindah ke PT itu lalu setujui lagi."; tetap `pending`; PO 0 |
| U9 | B | ya (200) | Lulus — dari `ent_kanda` 403 "Anda tidak lagi punya akses ke PT draf ini."; dari `ent_ksc` 403 (`entity_ctx`); `pending`; PO 0 |
| U10 | B | ya (200, kartu lahir) | Lulus — 400 "Pilih satu PT dulu…", jumlah kartu tetap |
| U11 | B | ya (status sempat `running` lalu `pending`) | Lulus — qty 0 → 400 tanpa satu pun tulisan status; qty 5 → 200 `confirmed`, PO 1 |
| U12 | B | ya (S3 dan pemasok seed PT lain muncul, S4 terpotong) | Lulus — S1, S2, S4; tanpa S3; semua kandidat ber-PT `ent_ksc`/`all` |
| U13 | B | ya (gudang khusus Kanda & sales Kanda muncul) | Lulus |
| U13b | B | ya (4 kandidat untuk `limit` 2) | Lulus — `limit` 2 → 2; `limit` 999 → dibatasi 20 → 3 (S1, S2, S4) |
| U14 | B | ya (9 nilai tanpa pelaksana) | Lulus — 7 · 18 · 5, dua arah; `ops_metrics`, `propose_action` cocok |
| U15 | B | ya (modul lapisan belum ada) | Lulus — event `tool` `find_entities` {kind supplier, query s1}; `done` "Ada satu pemasok."; `.calls` = 2 (instruksi 3, alat lengkap, giliran 2 memuat `tool_result` berisi S1); satu baris `ai_usage_log` `bi_chat` `done` |
| U15b | B | ya (idem) | Lulus — status `has_key`/`chat_enabled` dari pelaksana; narasi template lewat `short_text` |
| U15c | B | ya (idem) | Lulus — `job_ai_prewarm` (Senin dibekukan) → satu `prewarm` (instruksi sistem + katalog, alat lengkap), log `bi_prewarm` biaya 0 |
| U16 | B | ya (`ai_chat_service.py`, `ai_narrative.py` mengimpor pustaka) | Lulus — pengimpor = `ai_provider.py` + dua pelaksana fitur lain (lihat "Menyimpang") |
| U17 | B | ya (kunci tidak ada) | Lulus — registry sesuai spesifikasi; global 36 terbaca (`value_of` + `/api/config/effective`); `ent_kanda` 12, KSC tetap 36; 0 dan 200 → 400; dipulihkan 24. Putaran KF-T8 `test_KFT8_putaran[ai.kartu_masa_berlaku_jam]` juga lulus |
| U17b | B | ya | Lulus (02 §2.4 butir 2) — 6 jam untuk `ent_kanda`: kartu Kanda berlaku 6 jam, kartu KSC 24 jam |
| U18 | layar | ya (komponen lama: 10/11 merah — `bukti/AG-T1/jest_merah_kode_lama.log`) | Uji komponen jest `frontend/src/features/__tests__/agt1KartuTindakan.test.js` 11/11 (`jest_hijau_kode_baru.log`). **Uji jalan peramban belum dilakukan** |

`backend/tests_mem` seluruhnya: HEAD **1303 lulus / 2 dilewati / 4 xfail** → sesudah **1327 lulus / 2 dilewati / 4 xfail**
(+23 uji AG-T1, +1 kasus putaran KF-T8 untuk kunci baru) — `bukti/AG-T1/tests_mem_sebelum_sesudah.log`.

Fixture vs alur: pemasok, produk, sumber produk, gudang, kartu "data lama" (U6/U7/U6b) dan pergeseran `expires_at` (U5) =
FIXTURE sisip langsung; kartu disiapkan/disetujui/diabaikan, pengaturan diubah, pencarian, dan chat = ALUR API. U1 memaksa
pembuat PO gagal dengan `monkeypatch` (panggilan ke-2); U11 memakai pengintai tulisan `mongomock` (dicatat di uji).

## Uji yang disesuaikan (angka, bukan harapan dilonggarkan)

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` | `+ AGT1_KUNCI` (= 1) di U02 dan U04 | kunci baru `ai.kartu_masa_berlaku_jam` berizin `settings.manage`, aktif |
| `frontend/src/features/settings/config/configKeyIndex.json` | dibangkitkan ulang (`gen_config_key_index.py`) | sub-judul + kunci baru (`test_KFT4_indeks_kunci_layar_sama_dengan_skrip`) |

## Berkas berubah

Server: `backend/services/ai_actions.py`, `ai_chat_service.py`, `ai_narrative.py`, `ai_cost.py`, `ai_tools.py`,
`ai_provider.py` (baru), `ai_provider_fake.py` (baru), `backend/routers/ai_assist.py`, `backend/config_catalog_ai.py`,
`backend/config_registry.py` (sub-judul `tanya-kn-tindakan`), `backend/data/ai/tools_kn_analitik_v1.json`,
`backend/entity_scope.py` (`USER_SCOPED_COLLECTIONS`), `backend/indexes.py` (`uq_id` + `(user_id, status, created_at)`),
`scripts/verify_contract.py` (koleksi kanonik). Layar: `frontend/src/features/tanya/TanyaActionCard.jsx`, `tanya.css`,
`TanyaRulesStrip.jsx`, `frontend/src/features/settings/config/configKeyIndex.json`. Uji: `backend/tests_mem/test_AGT1_kartu.py`,
`test_AGT1_penyedia.py`, `test_KFT1_izin_pengaturan.py`, `backend/tests/test_bp_AGT1_kartu_bersamaan.py`,
`frontend/src/features/__tests__/agt1KartuTindakan.test.js`. Dokumen: `ENTITY_REGISTRY.md` (baris tabel, bagian
`ai_action_proposals`, awalan `aiact_`), `CODEBASE_MAP.md` (hasil `gen_codebase_map.py`).

## Menyimpang dari blueprint

- **Sub-judul baru** `tanya-kn-tindakan` ("Tanya KN: kartu tindakan") di kelompok Sistem. Spesifikasi menulis kelompok
  `asisten-analitik` (alias → `sistem` / `tanya-kn`), tetapi sub-judul `tanya-kn` sudah 14 kunci = batas sub-judul biasa
  (KF-T4, `verify_config_text` T7). Kelompok tetap `sistem`; kunci tampil di layar Pusat Pengaturan › AI & Tampilan.
- **`consumers`** menyebut dua fungsi: `services/ai_actions.py:propose_action` (kartu baru) dan `:_masa_berlaku` (kartu lama
  saat dibaca) — keduanya benar-benar membaca kunci (02 §2.1).
- **U16**: selain `ai_provider.py`, dua modul di `backend/services/` mengimpor pustaka klien penyedia untuk fitur LAIN:
  `ocr_openai_client.py` (baca surat jalan) dan `hr_ai_service.py` (pengenal gambar desain, KP-T8). Di luar lingkup unit;
  uji menuliskannya sebagai daftar pelaksana berizin dengan alasan. Usulan teks pengganti hasil U16: "Hanya modul pelaksana
  penyedia: `ai_provider.py` (Tanya KN), ditambah pelaksana fitur lain yang sudah ada (`ocr_openai_client.py`,
  `hr_ai_service.py`); `ai_chat_service.py` dan `ai_narrative.py` tidak lagi mengimpor".
- **U11 merah di kode lama** hanya terlihat dari tulisan antara (`running` lalu dipulihkan `pending`); hasil akhirnya sama.
  Uji memakai pengintai tulisan status. Usulan teks pengganti hasil U11: "Pertama 400 dan status tidak pernah berubah selama
  permintaan (kode lama: `running` lalu `pending`); kedua 200 `confirmed`".
- **U9** memakai akun peran kustom (izin `ai.view`, `purchase_order.view/create`, PT KSC + Kanda), bukan admin seed: admin
  bawaan selalu boleh semua PT aktif (`allowed_entities_for`), jadi PT-nya tidak bisa dicabut. U9 juga memeriksa permintaan
  dari `ent_ksc` (403 dari `entity_ctx`).
- **Jawaban galat 200** membawa `message` (teks tabel spesifikasi "{pesan asli}. Yang sudah dibuat: …") selain `error`
  (galat asli, sesuai tabel Data) — layar memakai `error` + `result` supaya baris "Sudah dibuat sebelum gagal" tidak ganda.
- Tambahan kecil di luar tabel Perubahan: kalimat 403 izin PO (Z6), `entity_name` di jawaban kartu, `dismiss` mengisi
  `finished_at`, jejak `ai_action_failed`, uji U5b/U5c/U6b/U13b/U15b/U15c/U17b.

## Asumsi

- Spesifikasi: masa berlaku 24 jam per PT; kartu hanya bisa disetujui saat PT aktif = PT kartu; kartu gagal tidak
  dilanjutkan; galat pelaksanaan dijawab 200 `failed`.
- Kartu lama `pending` tanpa `expires_at`: masa berlaku dihitung saat dibaca dengan nilai pengaturan PT kartu saat itu (tidak
  disimpan), sehingga mengubah pengaturan ikut menggeser kartu lama (U7). Kartu baru memakai nilai saat dibuat.
- "Tidak berubah > 10 menit" untuk kartu `running` diukur dari `updated_at` (diperbarui tiap butir hasil), lalu
  `started_at`, lalu `created_at` (kartu lama tidak punya keduanya).
- Akun satu-PT (tidak bisa berganti PT) tidak pernah berada di mode gabungan walau kepala aplikasi "Semua" (server:
  `view_all` hanya bila PT > 1) — layar tidak mematikan tombolnya.
- `limit` pencarian 1–20 (bawaan 5) dan 10 menit proses mati = batas teknis (konstanta), bukan aturan bisnis (spesifikasi).

## Cek layar (KN_37 + KN_08 + UX_USABILITY) — Tanya KN › kartu tindakan di percakapan

| # | Daftar periksa | Hasil |
|---|---|---|
| 1 | Tabel lebih lebar dari kartu | Tidak ada tabel; baris PO `flex-wrap`, isian qty 90 px, satuan × harga turun baris di 390 px |
| 2 | Kartu tanpa bantalan | `.tanya-action` berbantalan `--sp-4`; kepala, baris PT, isi, bilah tombol terpisah (`gap` 10 px) |
| 3 | Kepala kartu dijejali | Kepala hanya judul + satu pil status (`flex-wrap`); tombol dan alasan tombol mati di bilah sendiri di bawah |
| 4 | Tombol mati hanya tooltip | "Setujui …" mati saat PT aktif berbeda / Semua PT dengan kalimat tertulis di sampingnya "Pindah ke {PT} untuk menyetujui." (`tanya-action-pt-hint`); "Abaikan" tetap aktif |
| 5 | Status hanya warna+teks | Pil `status-pill` ikon + teks + warna token; label lewat `docStatusLabel(status, peta kartu)` sehingga kode status tak dikenal tidak tampil mentah (uji jest `on_hold` → "Ditahan"). 6 status: Menunggu persetujuan (jam, perhatian) · Sedang diproses (putar, aksi) · Sudah disetujui (centang, berhasil) · Diabaikan (silang, netral) · Gagal (segitiga, bahaya) · Kedaluwarsa (jam pasir, netral) |
| 6 | Daftar puluhan baris tanpa cari | Tidak berubah: kartu memuat ≤ 30 baris PO / ≤ 50 pengingat (batas lama `MAX_LINES`); bukan layar daftar |
| 7 | Teks bertentangan dengan izin | 403 izin PO kini kalimat Z6 (akses 'Pembelian & Pengadaan'), bukan "Peran Anda tidak boleh"; strip status "Menunggu kunci penyedia model"; tidak ada teks "bukan wewenang". Tombol tidak dimatikan berdasar izin di layar (kartu hanya lahir bila pembuatnya berizin; pencabutan izin sesudahnya dijawab server dengan kalimat Z6 di toast) |
| 8 | Kosong ganda / angka 0 / grafik | Satu keadaan memuat ("Memuat draf…"); kartu hilang tanpa pesan bila tidak ditemukan (perilaku lama). Kartu disetujui tanpa hasil hanya menampilkan pil. Catatan: harga baris bisa "Rp 0" bila sumber harga tidak ditemukan (`resolve_line_sourcing`, perilaku lama — di luar lingkup) |
| — | Huruf ≥ 12 px, warna token | Teks baru `--fs-12`/`--fs-13` + `--kn-text`, `--kn-text-2`, `--kn-danger-text`; `.tanya-kicker` 11 px dinaikkan ke 12 px di dalam kartu; tombol kelas baku `primary-button btn-sm` / `secondary-button btn-sm` (dulu shadcn `Button`); tanpa hex baru di JSX |
| — | Tanggal WIB, PT disebut | "PT: Sukacita · berlaku sampai 15 Nov 2026 09.00 WIB" (`formatDateTime`); 409 dari server memuat ulang kartu sehingga status terkini tampil |
| — | Uji jalan 1280/1024/390 px | **Belum diuji jalan** (peramban tidak dibuka di lingkungan B) — perlu dipotret integrator |

## Integrasi ke cabang

Dipetik ke cabang di atas PK-31 sebagai `3e1a42c`: bentrok berdampingan di `ENTITY_REGISTRY.md` (CR-T1 + AG-T1),
`indexes.py` (daftar koleksi ber-id), hitungan `test_KFT1` (`+ CRT1_KUNCI_KONTROL + AGT1_KUNCI`, `+ CRT1_KUNCI +
AGT1_KUNCI`); indeks kunci dan peta kode dibangkitkan ulang. tests_mem HEAD gabungan 1414 lulus; `verify_auth_coverage`
28 → 27.

Cek layar: kartu tindakan hanya muncul di percakapan Tanya KN sesudah asisten mengusulkan tindakan; tanpa penyedia
model sungguhan (H8) kartu tidak bisa dimunculkan di peramban lingkungan A, jadi belum dipotret — bukti layar = uji
komponen jest 11/11 dan daftar periksa di bagian "Cek layar".

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di `a48a0a9` — satu gate untuk
enam unit yang digabung bersamaan (CR-T1, PK-31, AG-T1, PM-T2, TX-T1, PK-18) — lalu `--quick` diulang di `f1b8239` sesudah
perbaikan cek layar (hanya layar):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` (`a48a0a9`) | 14 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama: `InventoryStockView`) | 2 (`config_wiring` + uji-diri) |
| `--ci` (`a48a0a9`) | 41 FAIL | 43 | 1 (ganti nama) | 2 |
| `--quick` (`f1b8239`) | 14 FAIL | 16 | 1 (ganti nama) | 2 |

Kuitansi: `bukti/AG-T1/gate_quick_receipt.md`, `gate_ci_receipt.md`. Lapis A unit-unit itu (6 berkas `tests/test_bp_*`) di
lingkungan A: 19 lulus.

Yang dijalankan di lingkungan B:

- Penjaga statik `hitung_penjaga.sh`: sama, kecuali `verify_auth_coverage` 28 → **27** (turun). 66 butir gate statik
  `scripts/gate.sh` dijalankan di salinan HEAD (`git archive`) dan di kode baru: kode keluar identik (13 butir merah sama di
  keduanya, ringkasan sama) — `bukti/AG-T1/penjaga_sebelum_sesudah.log`.
- `verify_role_gate_ui` 0, `verify_config_fallback` 0 (`--entity` 0), `verify_payment_vocab` 0, `verify_config_text` 0,
  `audit_config_wiring --strict` (salinan berjalur `$W`) hijau, `gen_config_key_index.py --check` selaras,
  `verify_codebase_map` 0, `verify_ui_standard` 13 = HEAD, `verify_ui_contrast` 58/58.
- Jest: `agt1KartuTindakan` 11/11; `phase4R6` (dengan tiruan radix lokal) 6/6; tujuh suite lain yang menyentuh Tanya gagal
  dimuat karena `@radix-ui/...` (kendala lingkungan; sama di HEAD).

## Temuan di luar lingkup (tidak diperbaiki)

- `backend/tests/test_registry_ai_collections.py` (lapis A) merah di HEAD karena `ai_action_proposals` **dan** `ai_insights`
  belum terdaftar; sesudah unit ini tinggal `ai_insights` (koleksi peringatan anomali; disaring per PT di `ai_insights.list_for`
  — pemiliknya yang memutuskan masuk `SCOPED_COLLECTIONS` atau himpunan lain).
- Templat "Kehadiran & lembur" (`data/ai/templates_laporan_v1.json`, `hr_today`) memanggil `run_report` `hr_summary` yang tidak
  punya pelaksana → selalu "Laporan ini belum tersedia…". Skema alat tidak lagi menawarkannya ke model, tetapi templat tetap.
- Katalog semantik (`data/ai/katalog_semantik_v1.md:90`) masih memetakan "SJ, surat jalan → delivery_note / goods_receipt";
  `delivery_note` kini tidak ditawarkan skema (model tidak bisa memilihnya). Tidak diubah (bagian prompt tercache).

## Gabung ke HEAD terbaru (`f05d8da`)

- Berkas yang diubah/ditambah unit ini dibandingkan per berkas (HEAD vs basis `b5b7539`): 17 berkas di HEAD **sama** dengan
  basis → disalin dari W; 6 berkas baru → disalin; **beda** hanya `ENTITY_REGISTRY.md` (`git merge-file`, tanpa bentrok — tambahan
  unit lain dan baris/bagian `ai_action_proposals` + awalan `aiact_` keduanya dipertahankan) dan `CODEBASE_MAP.md` (dibangkitkan
  ulang). `configKeyIndex.json` dibangkitkan ulang (`--check` selaras). `access_modules.py` tidak berubah → fixture akses tidak
  perlu. `test_KFT1_izin_pengaturan.py` di HEAD = basis → `AGT1_KUNCI` tetap satu-satunya tambahan; tidak ada izin bawaan /
  indeks wajib PK-14 baru.
- KP-T9 / PK-44 tidak menyentuh berkas Tanya KN (kartu PK-44 = kartu dasbor keuangan, bukan kartu tindakan asisten); tidak ada
  bentrok perilaku.
- Sesudah aturan baru brief (status lewat `docStatusLabel`, kode mentah tidak tampil): label pil kartu kini
  `docStatusLabel(status, peta kartu)` (+1 uji jest), di W dan T.
- Angka di T (`bukti/AG-T1/gabung_T_f05d8da.log`): tests_mem HEAD **1328 / 2 dilewati / 4 xfail** → T **1352 / 2 / 4** (+24);
  jest penuh HEAD 92 suite lulus · 762 uji → T 93 · 773 (35 suite gagal dimuat `@radix-ui`/`cmdk` = sama di HEAD);
  `hitung_penjaga.sh` sama kecuali `verify_auth_coverage` 28 → 27; 67 gate statik `gate.sh` kode keluar identik dengan HEAD
  (13 merah sama); `verify_role_gate_ui` 0, `verify_config_fallback` 0 (`--entity` 0), `verify_payment_vocab` 0,
  `verify_access_catalog_nav` 0, `verify_config_text` 0, `verify_codebase_map` 0, `audit_config_wiring --strict` hijau,
  `check_nav_map.py` PASS (keduanya lewat salinan berjalur T).

## Hambatan lingkungan

- Lapis A (U4) dan uji jalan peramban (U18) tidak bisa dijalankan di lingkungan B.
- Saat membandingkan uji lapis A statik `test_registry_ai_collections.py` sebelum/sesudah, sempat dipakai `git stash` lalu
  `git stash pop` (tanpa perubahan bersih; daftar stash kosong sesudahnya). Perbandingan lain memakai salinan `git archive HEAD`.

## Yang perlu direview

- Urutan `confirm` dan bentuk jawaban 200 `failed` (+ `message`); pembaruan status saat dibaca (`load` menulis `expired` /
  `failed`).
- `_turn_events` (delta lewat antrean selagi giliran penyedia berjalan; giliran dibatalkan bila klien memutus).
- Penempatan kunci di sub-judul baru `tanya-kn-tindakan`.
- U4 di MongoDB asli; uji jalan kartu (gagal, kedaluwarsa, PT berbeda) di 1280/1024/390 px.
