# KF-T8 — Penjaga pengaturan: uji putaran semua kunci menjadi gate

- Commit awal: `a323bb0` (dikerjakan) · digabung di atas `c38fc92`        - Commit: `e13e29b` · koreksi blueprint `3092d92`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KF-08 (spesifikasi `docs/blueprint/unit/KF-T8.md`; standar `02_STANDAR.md` §2.2, §2.4, §6)
- Risiko rendah → satu serah-terima. Tidak ada perubahan perilaku aplikasi; satu percepatan `config_health` (hasil identik).

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca pada `3132cc4`; dicek di `a323bb0`)

| Butir | Hasil di `a323bb0` |
|---|---|
| Penjaga hanya menilai `DEFAULT_GLOBAL_SETTINGS` (+ dokumen non-grup bila ada database); "Total kunci terdeklarasi: 78" vs registry 310 | Berlaku, bergeser: `audit_config_wiring.py:74` (`declared_global`), `:106` (`declared_other_scopes`), `:621` (`main`). Keluaran tanpa database: **"Total kunci terdeklarasi : 71"**, registry kini **430** kunci (394 aktif, 36 `not_used`) |
| "Dibaca kode" = cari nama daun di korpus; daun pendek keliru dua arah | Berlaku: `audit_config_wiring.py:372` (`hits`), `:386` (`len(leaf) < 3`) |
| `config_health._mentions` cukup menemukan nama daun | **Tidak berlaku — sudah diperketat KF-T3**: `config_health.py:113` (`_mentions`), `:57` (`_cocok`: kunci utuh / induk + daun; keluarga `kontrol.<aksi>.*` lewat literal aksi), `:88` (`_badan_fungsi`: hanya badan fungsi + konstanta teks modul yang dirujuknya). Bukti: `config_health.report()` 430 baris, 0 rusak (U14); uji-diri [7] entri palsu → STALE. Aturan spesifikasi sudah terpenuhi; tidak diubah (hanya dipercepat, lihat Menyimpang 11) |
| Gate memanggil penjaga dua kali; tidak ada gate tulis→baca | Berlaku, bergeser: `scripts/gate.sh:303` (`--strict`), `:306` (`--self-test`) |
| Uji putaran 310 kunci hanya skrip audit | Berlaku: `bukti/t1_config.py:98` (`all_entries`), `:18` (`alt_value`), `:44` (`bad_value`) |
| 19 kunci tabel/daftar hanya disimpan ulang | Berlaku: `t1_config.py:122` (`simpan_ulang_nilai_sama`); di `a323bb0` tepat 19 kunci aktif bertipe daftar (10) / tabel (9) — semuanya `row_shape` `map`/`list`, tidak ada tabel JSON aktif |
| INV-CFG-01 memakai penjaga yang sama | Berlaku: `scripts/verify_data_integrity.py:2666` |
| Nomor INV-CFG-08/09/10 | Belum terpakai (ASUMSI spesifikasi benar). INV-CFG-06/07 dipakai POC G-0 |

## KF-08 — Penjaga pengaturan hanya memeriksa 78 kunci lama

- Berlaku di HEAD: ya (71 kunci dinilai dari 430; tidak ada gate tulis→baca; cadangan & penerusan PT tidak dijaga).
- Akar masalah: penjaga kabel pengaturan menilai kunci TERSIMPAN (daun dokumen lama) dan mencari nama daunnya, bukan
  registry; uji putaran hanya skrip arsip yang dijalankan tangan.
- Perubahan perilaku (sebelum → sesudah):
  - **INV-CFG-08 `config_roundtrip`** (gate bawaan/`--ci`/`--full`, bukan `--quick`):
    `backend/tests_mem/test_KFT8_putaran_pengaturan.py` — satu kasus per entri registry
    (`test_KFT8_putaran[<kunci>]`, 430 kasus): tulis grup → `GET /api/config/effective` + `value_of` + pembaca lama
    (`get_effective_settings`; dokumen `system_settings{scope}` + `entity_overlay`) → lapisan PT `ent_kanda` (PT `ent_ksc`
    tidak berubah) → cabut → nilai tak sah 400 → tanpa alasan 400 → pulihkan (juga di `finally`). Kode gagal P1–P8 persis
    tabel spesifikasi; ditimpa aturan lain (`overridden_by`) → P1–P3 terhadap `stored_value`, P8 `value_of` = pembaca lama.
    Pembangkit `backend/tests_mem/_nilai_uji.py`: daftar ditambah/dibuang satu butir sah, tabel bercolumns ditambah satu
    baris bawaan kolom, peta ditambah `"UJI": 1`, regex `"uji\\d+"`; hanya tabel JSON yang simpan-ulang (saat ini 0 kunci).
    Tanpa `mongomock-motor` gate **merah** "pasang mongomock-motor (lihat 03_LINGKUNGAN_UJI §3)". ±90–100 dtk.
  - **`scripts/audit_config_wiring.py` menilai seluruh registry**: kunci = (a) registry + (b) daun
    `DEFAULT_GLOBAL_SETTINGS` + (c) dokumen non-grup + (d) literal `value_of/resolve/_cfg/_config("…")` di
    `services`+`routers`. Registry dinilai `config_health.check_entry` (OK→OK; STALE/MISSING aktif→ORPHAN_UI; Hub
    diputus→HIDDEN/DEAD); daun (b)(c) yang tercakup registry dinilai lewat entrinya (daun tabel PT tidak lagi ORPHAN_UI
    palsu — catatan KF-T2/KF-T4), yang tidak tercakup tetap `hits`; (d) tak tercakup → HIDDEN; katalog
    `config_catalog_*.py` yang kuncinya tidak termuat → "registry tidak termuat utuh" (pelanggaran). Keluaran
    **"Total kunci terdeklarasi: 430 (registry 430)"**, 0 pelanggaran. Uji-diri baru [7] ORPHAN_UI, [8] HIDDEN, [9]
    impor tiruan tanpa `config_catalog_core` → 430→411 kunci + "registry tidak termuat utuh", [10b] daun tabel di
    dokumen PT. `verify_data_integrity.py` INV-CFG-01/04 memakai `acw.collect()` (fungsi yang sama), teks menyebut
    "(registry R)".
  - **INV-CFG-09 / INV-CFG-10 `scripts/guardrails/verify_config_fallback.py`** (+ `--entity`, `--self-test`, `--root`,
    `--json`, `--rinci`): bentuk (a) `.get("<daun>", lit)`, (b) `<baca kunci> or lit`, (c) konstanta huruf besar; sama
    dengan bawaan juga merah kecuali `bool`; `--entity`: `value_of("<kunci>")` (juga nama impor `value_of as …`) tanpa
    konteks / `{}` / `{"entity_id": ""}` / `None` untuk kunci berlapis PT. Pengecualian + garis dasar beralasan di
    `scripts/guardrails/config_fallback_allow.json` (butir basi = merah) — **136 butir, bukan 1** (Menyimpang 1).
  - **`scripts/gate.sh`**: 4 baris statik (`guard:config_fallback` + SELF-TEST, `guard:config_entity` + SELF-TEST), satu
    blok non-quick `config_roundtrip`, satu baris SKIP di `--quick`; semua ber-komentar `KF-T8`.
- Berkas berubah:

| Berkas | Isi |
|---|---|
| `backend/tests_mem/test_KFT8_putaran_pengaturan.py` | Baru — U1 (430 kasus + uji jumlah/pembangkit), U2–U5 bukti-merah, U14, U14b |
| `backend/tests_mem/_nilai_uji.py` | Baru — pembangkit nilai sah/tak sah, pembanding, calon berurutan |
| `scripts/audit_config_wiring.py` | (a)–(d), `catalog_keys`/`registry_gaps`, `registry_rows`/`leaf_rows`/`hidden_rows`/`collect`, uji-diri [7]–[10b], ringkasan "(registry R)" |
| `scripts/guardrails/verify_config_fallback.py` | Baru — INV-CFG-09/10 |
| `scripts/guardrails/config_fallback_allow.json` | Baru — 10 "bukan pengaturan" + 125 garis dasar INV-CFG-09 + 1 garis dasar INV-CFG-10 |
| `scripts/gate.sh` | Baris gate KF-T8 (blok ber-komentar) |
| `scripts/verify_data_integrity.py` | INV-CFG-01/04 lewat `acw.collect()`; teks "(registry R)"; katalog tak termuat memerahkan |
| `backend/services/config_health.py` | Percepatan `_badan_fungsi` (`_segmen`, indeks fungsi per berkas; hasil identik — U14b + `bukti/config_health_lama_baru_sama.log`) |
| `docs/blueprint/03_LINGKUNGAN_UJI.md` | §3 baris `t1_config.py` → padanan gate; §4 tabel "Gate baru sesudah garis dasar (KF-T8)" |
| `docs/audit/konfigurasi-peran-2026-11-13/bukti/README.md` | Baris `t1_config.py`: padanan gate (skrip tetap arsip, tidak diubah) |

- Commit: belum (instruksi).
- Pengujian: tabel di bawah; `tests_mem` seluruhnya **699 lulus / 2 dilewati / 2 xfail → 1134 / 2 / 4**.
- Bukti UI: tidak ada layar.
- Fixture disiapkan langsung vs proses bisnis: semua alur putaran lewat API (`PUT /api/config/values`,
  `POST /api/config/values/clear|reset`, `GET /api/config/effective`); sesi admin = fixture `kepala_admin`.
- Dampak pada modul terkait: layar Kesehatan Pengaturan memakai `check_entry` yang sama (lebih cepat, hasil sama);
  `verify_data_integrity` lapisan config ±+3 dtk (kunci kode + registry) per jalan penuh.
- Keterbatasan / yang belum diuji: `gate.sh` tidak dijalankan (U13 diemulasi, lihat Gate); bagian (c) dengan database
  nyata tidak dijalankan (larangan database `backend/.env`) — dibuktikan uji-diri [10b] dan pembanding kode lama.
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_KFT8_putaran_pengaturan.py` (lingkungan B) + perintah statik. Tidak ada butir lapis A di
spesifikasi. "Merah di lama": unit ini tidak mengubah aplikasi, jadi bukti-merah U1 adalah U2–U5 (mata rantai dirusak
→ kode gagal yang benar); butir statik dibandingkan dengan skrip/gate HEAD.

| ID | Lapis | Merah di lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | — (tes baru; `t1_config.py` hanya menyimpan ulang 19 kunci daftar/tabel) | Lulus — 430 kasus = `len(all_entries())`, 0 dilewati: **428 lulus + 2 xfail temuan** (T1, T2 di bawah; xfail hanya bila gagal dengan kode temuannya, kode lain tetap merah, dan merah bila temuan hilang). Uji jumlah + pembangkit (tiap kunci aktif non-JSON dapat nilai lain): lulus. ±90–100 dtk (`bukti/putaran_U1_hijau.log`) |
| U2 | B (bukti-merah) | — | Lulus — `_project` tanpa kerja → `P1 tax.ppn_mode: lapisan grup: pembaca lama (get_effective_settings) memberi 'excluded', ditulis 'included'` (+P3) |
| U3 | B (bukti-merah) | — | Lulus — `_bounded` apa adanya → `P4 ar.grace_days: nilai tak sah 1000180 … HTTP 200` dan `-1000000 … HTTP 200` |
| U4 | B (bukti-merah) | — | Lulus — `build_layers` tanpa lapisan PT → `P2 sales.allow_partial_shipment: lapisan PT ent_kanda: GET … memberi false, ditulis true` (+ `value_of`). Lihat Menyimpang 4 |
| U5 | B (bukti-merah) | — | Lulus — `set_value` melewati alasan → `P5 tax.ppn_mode: tulisan tanpa alasan diterima (HTTP 200, harus 400)` (kunci `high`) |
| U6 | statik | ya — "Total kunci terdeklarasi : 71" tanpa jumlah registry | Lulus — "Total kunci terdeklarasi: 430 (registry 430)" (N = R: tanpa database semua daun (b) dan kunci (d) tercakup registry), 0 pelanggaran, 0 katalog tak termuat; ±10 dtk (3 dtk = batas waktu sambung MongoDB palsu) |
| U7 | statik | ya — uji-diri lama hanya [1]–[7] | PASS [1]–[10] + [10b] (Menyimpang 2); ±25 dtk |
| U8 | statik (bukti-merah) | ya — skrip lama keluar 0, kunci palsu tidak dinilai | Lulus — salinan pohon + `E("uji.kunci_palsu", …, consumers=("services/config_service.py:compute_tax",))`: `--strict` keluar 1, `ORPHAN_UI … pemakai STALE services/config_service.py:compute_tax` |
| U9 | statik | — (penjaga belum ada) | Keluar 0; 0 temuan tersisa (151 temuan mentah); **pengecualian dipakai 135, bukan 1** — Menyimpang 1 + usulan koreksi |
| U10 | statik (bukti-merah historis) | — | Lulus — `git archive 3132cc4` (bukan `git worktree`): keluar 1; kesepuluh kunci tercantum (`tax.ppn_rate`, `tax.dpp_nilai_lain`, `sales.allow_item_discount`, `inventory.intercompany_transfer_required`, `ar.denda_rate_pct_per_month`, `commission.discount_threshold`, `commission.discount_factor`, `sales.require_so_validation`, `allocation.lot_selection`, `approval.po_custom_direksi_min`) |
| U11 | statik | — | PASS 7 butir: `tax.get("ppn_rate", 0)` (a), `… or 11` (b), konstanta (c), sama-bawaan → "default_of", bool sama-bawaan tidak dituduh, pengecualian basi |
| U12 | statik | — | `--entity` keluar 0 dengan 1 pengecualian beralasan (T3, "KF-T3 — …"); uji-diri PASS 5 butir (suntikan `value_of("inventory.default_uom")` dan `{"entity_id": ""}` terdeteksi; konteks dokumen tidak dituduh; basi terdeteksi) |
| U13 | statik | ya — baris belum ada | 4 baris statik baru tampil dan hijau (emulasi larik `STATIK`, `bukti/U13_baris_gate_statik.log`); `config_roundtrip` di blok non-quick + SKIP di `--quick`; cabang tanpa mongomock merah dengan pesannya. `gate.sh` tidak dijalankan (Gate) |
| U14 | B | **tidak** — sudah hijau sejak KF-T3 | Lulus — `config_health.report()`: 430 baris = registry (urut sama), `broken == []` |
| U14b (tambahan) | B | — | Lulus — `config_health._segmen` = `ast.get_source_segment` untuk tiap fungsi rujukan + konstanta teks modul |

`tests_mem` seluruhnya (`cd backend && python -m pytest tests_mem -q -p no:cacheprovider`, dua pekerja):
sebelum **699 lulus / 2 dilewati / 2 xfail** (225 dtk) → sesudah **1134 lulus / 2 dilewati / 4 xfail** (227 dtk; +435 =
430 kasus putaran − 2 xfail + U1 + U2–U5 + U14 + U14b) (`bukti/tests_mem_seluruh_sebelum_sesudah.log`). Lama jalan
seluruhnya hampir tidak berubah karena modul putaran berjalan di pekerja kedua (`loadscope`).

Pemeriksaan tambahan: pohon `main` terbaru (`bcce72a`, sesudah KP-T5/MN-T1/PK-38; salinan `git archive` + tambalan unit ini):
putaran **436 lulus + 2 xfail** (432 kunci), `audit_config_wiring --strict` 432 (registry 432) 0 pelanggaran,
`--self-test` PASS, `verify_config_fallback` dan `--entity` keluar 0 tanpa pengecualian basi.

## Temuan yang ditemukan penjaga (tidak diperbaiki — kunci milik unit lain, spesifikasi "Di luar lingkup")

| # | Kunci | Penjaga | Isi | Dicatat sebagai |
|---|---|---|---|---|
| T1 | `allocation.allow_intercompany` | INV-CFG-08 P8 | Lapisan PT `ent_kanda` = true; `value_of` = false (penimpa `wajib_transfer_antar_pt`), pembaca lama `get_effective_settings` = true. Mesin (`get_allocation_policy`) menerapkan aturannya sendiri; pembaca dokumen mentah tidak | `TEMUAN` di tes (xfail "KF-04 — …"); pemilik KF-T3 (KF-04) |
| T2 | `returns.grade_price_factors` | INV-CFG-08 P2 | `get_effective_settings(ent_kanda)` menggabung (deep-merge) tabel PT dengan tabel grup: pasangan yang dihapus di tabel PT tetap terbaca dari grup. `value_of` benar (`grade_factors` memakainya) | xfail "KF-04 — …"; pemilik KF-T2/KF-T3 |
| T3 | `hr.feature_toggles.npwp_required` | INV-CFG-10 | `routers/hr.py:263` (`create_employee`) `_cfg_value(...)` tanpa PT → nilai khusus PT tidak berakibat (kelas KF-10) | Pengecualian `mode: entity`, alasan "KF-T3 — sisa kelas KF-10" |
| T4 | 125 baris di 47 berkas | INV-CFG-09 | 80 cadangan = bawaan registry (harus `default_of`; 7 di antaranya `or <bawaan>` dengan arti 0 tertulis di kartu: `purchasing.price_deviation_approval_percent` ×2, `antar_entitas.settlement_reminder_days` ×3, `qc.grade_thresholds.a_max/b_max`); 45 `… or 0/""/[]/{}` ≠ bawaan yang hanya terpakai bila nilai tersimpan kosong/None | Garis dasar beralasan (`jenis` `sama_bawaan` / `hanya_bila_kosong`); daftar lengkap `bukti/temuan_cadangan_mentah_HEAD.json`. Tidak ada cadangan ≠ bawaan bentuk (a) pada pembacaan pengaturan di HEAD (KF-T2 tuntas) |

Pengamatan di luar aturan spesifikasi (tidak dijaga): `interco_service.list_accounts` membaca
`antar_entitas.settlement_reminder_days` lewat `_config(…)` tanpa PT; `get_allocation_policy` menerapkan
`allocation_policy` pelanggan SESUDAH penimpa wajib transfer (pelanggan bisa menyalakan lagi `allow_intercompany`);
empat kunci `not_used` masih dibaca `value_of` (`approval.matrix_sod`, `amendment.dual_control`,
`approval.matrix_enforcement`, `approval.extra_levels` — alias §2.3 / pindahan KP-T4).

## Cek layar

Tidak ada layar yang disentuh (unit infrastruktur; tidak ada berkas `frontend/` berubah). Layar Kesehatan Pengaturan
(`GET /api/config/health`) memakai `check_entry` yang sama — hanya dipercepat di server, isi jawabannya identik
(`bukti/config_health_lama_baru_sama.log`). Daftar periksa KN_37 (tabel melebar, `section-pad`, kepala kartu, tombol mati
beralasan, `status-pill`, cari/saringan, teks izin, keadaan kosong/angka 0/grafik): tidak berlaku. Jest tidak dijalankan
(tidak ada perubahan layar).

## Bukti

`bukti/KF-T8/`: `putaran_U1_hijau.log`, `putaran_U2_U5_bukti_merah.log` (+ varian U4), `tests_mem_seluruh_sebelum_sesudah.log`,
`audit_config_wiring_strict_sebelum_sesudah.log`, `audit_config_wiring_selftest_sebelum_sesudah.log`,
`U8_kunci_palsu_baru_lama.log`, `verify_config_fallback_U9_U11_U12.log`, `U10_verify_config_fallback_3132cc4.log`,
`temuan_cadangan_mentah_HEAD.json`, `buat_garis_dasar.py` (pembangkit isi berkas pengecualian, dijalankan sekali),
`U13_baris_gate_statik.log`, `U13_tanpa_mongomock.log`, `INV-CFG_lapisan_db_tiruan.log`,
`config_health_lama_baru_sama.log`, `penjaga_statik_sebelum_sesudah.log`.

## Penggabungan

Dikerjakan di `a323bb0`; digabung di atas `c38fc92` (sesudah KP-T5, MN-T1, PK-38, PK-40): `gate.sh` dan
`verify_data_integrity.py` digabung tiga arah tanpa bentrok. Di HEAD gabungan: putaran 437 kasus lulus + 2 xfail
beralasan; `verify_config_fallback` 0 tersisa (135 pengecualian beralasan), `--entity` 0 tersisa (1 garis dasar).
tests_mem 782 → 1219. Usulan koreksi blueprint diterapkan di `3092d92`.

Penjaga ini langsung bekerja saat unit berikutnya digabung: KP-T6, KP-T8 (dua kunci `integrations.anthropic.*` ikut
putaran), PK-30 (satu kunci ikut putaran) — dan **menangkap** cadangan literal `"fixed_price"`/`"ikut_pkp"` di
`interco_service.meta` milik PK-30 (b), yang dibetulkan ke `default_of` sebelum digabung.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli), tiap jalan sesudah `restore_demo` (data acuan; tiga skrip seed yang sama
seperti garis dasar gagal).

| Jalan | Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|---|
| 1 (`c9cf10f` — KF-T8, KP-T6, KP-T8, PK-30) | `--quick` | 16 FAIL | 16 | 3 (ganti nama + 2 balapan, lihat bawah) | 2 |
| 1 (`c9cf10f`) | `--ci` | 42 FAIL | 43 | 2 (ganti nama + 1 balapan) | 2 |
| 2 (`27f0853` — + perbaikan penjaga `c2cc412`, PK-42 `5e747b2`, PM-T1 `fd606e5`, cek visual) | `--quick` | 14 FAIL | 16 | 1 (ganti nama) | 2 (`config_wiring` + uji-diri) |
| 2 (`27f0853`) | `--ci` | 41 FAIL | 43 | 1 (ganti nama) | 2 |

- **`guard:page_tabs`** hanya berganti nama sejak MN-T1 (INV-UI-12 → INV-UI-12/13/14); merahnya sama dengan garis dasar
  (INV-UI-12 `wms/InventoryStockView.jsx`, berkas lama).
- Jalan 1: **`guard:role_gate_ui`** dan **`guard:role_label`** merah palsu karena balapan di kolam statik paralel —
  uji-diri `role_gate_ui` menulis probe sementara `features/__poc_role_gate_probe.jsx` ke `src` yang dipindai penjaga lain.
  Bukan dari unit mana pun; diperbaiki di `c2cc412` (uji-diri menghitung probe di memori; pemindaian melewati probe
  penjaga lain). Jalan 2 keduanya hijau.
- Penjaga statik per hitungan (`hitung_penjaga.sh`) tidak naik; PK-42 menurunkan `verify_ui_standard` 15 → 13 dan
  `audit_i18n_id` 109 → 104.


Catatan lingkungan B (salinan kerja): `gate.sh --quick` tidak dijalankan di salinan karena ikut
menjalankan bagian runtime `verify_numeric_bounds` (backend :8001). Pengganti: baris statik `config_*` dijalankan dari
larik `STATIK` (U13). Penjaga statik (`hitung_penjaga.sh`) sebelum → sesudah **identik** (auth_coverage 28, ui_standard
15, i18n 109, create_modal 6, page_tabs 1, to_list_bound 6, entity_label 2, sisanya lulus/0); `verify_role_gate_ui` PASS
31 cek; `verify_config_text` PASS; `config_key_index` selaras; `validate_compliance` sama (FAIL hanya `.env`);
`audit_config_wiring --strict` HEAD bersih → bersih.

Lama jalan terukur (mesin ini, sebagian berbarengan dengan uji lain): `config_roundtrip` 90–100 dtk;
`audit_config_wiring --strict` ±9 dtk, `--self-test` ±28 dtk (HEAD: ±17 dtk); `verify_config_fallback` 2–5 dtk, `--self-test` ±12 dtk,
`--entity --self-test` ±7 dtk.

## Menyimpang dari blueprint

1. **U9 "pengecualian = 1 butir" tidak mungkin di HEAD.** Aturan (b) dan "sama dengan bawaan juga merah" memberi 151
   temuan mentah (136 baris): 10 bukan pembacaan pengaturan (slip PPh 21 — butir spesifikasi; `order`/`fkt` di
   `tax_invoice_service` ×3; hasil `compute_tax` di `config_service.py:743`; isian `payload`/`doc` ×5) dan 125 pelanggaran
   gaya §2.2 tanpa akibat perilaku yang tampak (T4). Memperbaikinya = menyentuh 47 berkas milik unit lain (termasuk yang
   sedang diubah PK-38/PK-40) — di luar lingkup. Penjaga tidak dilonggarkan: semua butir tercatat sebagai pengecualian
   **beralasan** dengan `jenis` (`bukan_pengaturan` / `sama_bawaan` / `hanya_bila_kosong` / `garis_dasar`), butir basi
   memerah (daftar hanya bisa berkurang), keluaran gate mencetak jumlah per jenis. Potongan `line_text` dipilih cukup
   khas sehingga tidak meloloskan baris bug lama (U10: `use_nl = bool(tax.get("dpp_nilai_lain", False))` tetap merah).
   Bila peninjau ingin gate merah sampai semuanya dibetulkan: hapus butir ber-`jenis` `sama_bawaan`/`hanya_bila_kosong`.
2. Uji-diri kabel pengaturan bernomor [1]–[10] + [10b], bukan [1]–[9]: [7] PK-46 lama menjadi [10] dan disesuaikan
   (daun lama kunci bertanggal tetap NOT_USED; daun yang sama bila tidak bertanggal kini dinilai lewat entri registry —
   bukan lagi ORPHAN_UI; daun tak terdaftar tetap merah); [10b] daun tabel di dokumen PT.
3. U13 "empat baris statik baru … kabel pengaturan uji-diri": `config_wiring SELF-TEST` sudah ada. Empat baris baru =
   cadangan, cadangan uji-diri, PT diteruskan, PT diteruskan uji-diri.
4. U4: `build_layers` dibuang lapisan PT **`entity` dan `legacy_entity`**. Membuang `entity` saja tidak memerahkan —
   proyeksi `_project` ke dokumen PT terbaca lewat `legacy_entity` sehingga nilai PT tetap benar (varian terekam di
   `putaran_U2_U5_bukti_merah.log`).
5. Pembangkit: calon berurutan dan dipakai calon pertama yang diterima server (400 = pemeriksa domain di luar metadata
   registry: peran pada kunci peta `notif.escalation_chain`, semua jenis pengingat sudah ada di
   `notif.reminder_recipients`, nomor WhatsApp). Cadangan sesudah bentuk spesifikasi: buang butir/baris terakhir, ubah
   pasangan pertama peta, kata pertama `example` registry, bawaan registry. Tabel tarif berjenjang (`value_format`
   `tarif_berjenjang`): tarif baris terakhir ± 1 (baris bawaan kolom tidak sah untuk tabel berjenjang). Nilai harapan =
   nilai bersih yang disimpan server (nomor WhatsApp dinormalkan `62…`); tulisan yang tersimpan sama dengan nilai lama
   tidak dihitung "nilai lain".
6. Pembaca lama tidak dinilai untuk kunci `bertanggal` (PK-46: tidak diproyeksikan ke `system_settings` dengan sengaja).
7. Dua temuan (T1, T2) memakai `pytest.xfail` imperatif beralasan "KF-04 — …" (bukan penanda), supaya hanya kode gagal
   temuannya yang ditoleransi.
8. P5 diuji lewat `PUT /api/config/values`; P6 menilai nilai tersimpan resolver, `stored_value` GET, dan pembaca lama.
9. INV-CFG-10 juga mengenali `from services.config_resolver import value_of as <nama>` (T3 hanya tertangkap karena ini).
10. Bentuk (b): ruas kiri `or` harus pembacaan kunci itu sendiri (sesudah `await`); pemanggilan yang hanya memuat
    pembacaan di argumennya (`order.get("effective_rate", order.get("ppn_rate", 0)) or 0`) tidak dihitung (cadangan
    dalamnya dinilai bentuk (a)).
11. `config_health._badan_fungsi` dipercepat (baris berkas dipecah sekali; indeks fungsi per pohon): 4,7 → 2,9 dtk per
    laporan; hasil identik pada registry HEAD dan registry/berkas `3132cc4` (83 STALE, 9 MISSING sama persis).
12. INV-CFG-09/10 memindai entri **aktif** saja (entri `not_used` tidak punya pembaca menurut definisinya).
13. (d) memakai pencocokan cakupan terhadap indeks registry yang sedang dinilai (sama dengan `config_registry.covers` untuk
    registry nyata) supaya impor tiruan [9] bisa diuji.
14. Berkas pengecualian berbentuk `{"_catatan", "pengecualian": [ … ]}` dengan medan tambahan `jenis`.
15. `CODEBASE_MAP.md` tidak diubah: keluaran `gen_codebase_map.py` hanya berbeda kepala komit dan urutan dua berkas
    sama panjang (generator tidak mendaftar skrip/tes). `KN_00_AGENT_QUICK_START.md` tidak memuat daftar gate — tidak
    diubah.

## Usulan koreksi blueprint (teks pengganti persis)

1. U9, kolom hasil: "Keluar 0; 0 temuan tersisa; pengecualian = 1 butir bukan pengaturan dari spesifikasi + butir
   bukan pengaturan lain dan garis dasar beralasan yang ditemukan saat penjaga lahir (di `a323bb0`: 10 bukan pengaturan,
   125 garis dasar `sama_bawaan`/`hanya_bila_kosong`); butir basi = merah".
2. U7: "PASS dengan butir [1]–[10] (butir [7] PK-46 lama menjadi [10]; [7]–[9] baru)".
3. U13: "Empat baris statik baru tampil (cadangan, cadangan uji-diri, PT diteruskan, PT diteruskan uji-diri) …".
4. U4 persiapan: "`monkeypatch` `build_layers` membuang lapisan PT (`entity` dan `legacy_entity`)".
5. "(1) … Pembangkit baru", sesudah kalimat terakhir: "Tabel `tarif_berjenjang`: tarif baris terakhir ± 1. Calon yang
   ditolak 400 oleh pemeriksa domain diganti calon berikutnya (buang butir/baris, ubah pasangan, contoh registry,
   bawaan)."

## Asumsi

- `ASUMSI` spesifikasi dipakai: INV-CFG-08/09/10 bebas; `mongomock-motor` terpasang di lingkungan gate penuh.
- "Pembaca lama" kunci bergrup dokumen lain = dokumen `system_settings{scope}` + `entity_overlay` (sama dengan
  `t1_config.py`).
- Klasifikasi `jenis` garis dasar dihitung otomatis dari batas registry (`min`) dan kalimat "Isi 0 dibaca sistem sebagai"
  di penjelasan kunci; butir `bukan_pengaturan` ditulis tangan sesudah membaca kodenya.

## Titik henti

- Tidak ada yang disentuh: tidak ada `middleware/`, gerbang RFID, data, atau skrip migrasi. Penjaga tidak dijalankan
  terhadap database `backend/.env` (semua jalan audit memakai `MONGO_URL` palsu; putaran di database tiruan).

## Persinggungan dengan unit lain

- `backend/services/config_health.py` (KF-T3): dua blok `KF-T8` (pemotong & indeks fungsi), hasil sama.
- `scripts/gate.sh`, `scripts/verify_data_integrity.py`: blok ber-komentar `KF-T8`; tambalan diterapkan bersih di atas
  `bcce72a` (offset 2 baris di `gate.sh`).
- PK-38 / PK-40 / KP-T5: menambah atau mengubah baris pembaca pengaturan akan menampakkan butir baru/basi di
  `config_fallback_allow.json` — itulah fungsi ratchet; di `bcce72a` tidak ada butir basi maupun temuan baru.

## Hambatan lingkungan

- `/app` menunjuk repo utama: `audit_config_wiring.py`, `verify_data_integrity.py`, dan `validate_compliance.py`
  dijalankan lewat salinan berjalur (`sed`) ke salinan kerja; `config_health` mengikuti akar skrip penjaga.
- Python sistem tanpa `bcrypt`: penjaga yang memuat registry dijalankan dengan venv Python 3.11 lingkungan B.
- Satu jalan pembanding `verify_data_integrity` (pertama, diulang dengan jalur benar) sempat mengimpor modul dari `/app`
  (repo utama) — hanya membaca, `git status` repo utama tetap bersih; hasil yang dipakai di laporan dari jalan ulang.
- Pembanding `main` terbaru memakai salinan `git archive bcce72a` di folder sementara (repo utama tidak diubah).

## Yang perlu direview

- Garis dasar 125 butir INV-CFG-09 (Menyimpang 1) — terima sebagai ratchet, atau jadikan gate merah sampai unit pemilik
  mengganti cadangan dengan `default_of`.
- T1–T3 (unit pemilik: KF-T3 / KF-T2 / SDM).
- Putaran 430 kunci ikut `tests_mem` (±90–100 dtk di satu pekerja; seluruh folder tetap ±4 menit dengan dua pekerja).

Status: implemented_pending_review.
