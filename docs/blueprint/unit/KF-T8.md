# KF-T8 — Penjaga pengaturan: uji putaran semua kunci menjadi gate

| | |
|---|---|
| Gelombang | Jalur pengaturan (sejajar gelombang 3–7) |
| Jenis | infrastruktur |
| Risiko | rendah |
| Prasyarat | KF-T2 |
| Menutup temuan | KF-08 |
| Keputusan | — |
| Standar | §2.2, §2.4, §6 |
| Lingkungan uji | B untuk uji putaran; penjaga statik tanpa database |

## Tujuan

Kunci pengaturan baru tidak bisa lagi "mati tanpa ketahuan": setiap kunci registry diuji tulis–baca otomatis, penjaga
kabel pengaturan menilai seluruh registry (bukan 78 kunci lama), dan nilai cadangan di kode yang menyimpang dari bawaan
registry memerahkan gate.

## Keadaan sekarang

Semua `[dibaca]`, kecuali angka keluaran gate yang diperoleh dengan menjalankan skripnya tanpa database pada `3132cc4`.

| Fakta | Jangkar |
|---|---|
| Penjaga hanya menilai kunci yang ada di `DEFAULT_GLOBAL_SETTINGS` ditambah isi dokumen `system_settings` selain grup bila database terjangkau; keluarannya "Total kunci terdeklarasi: 78", padahal registry memuat 310 kunci | `scripts/audit_config_wiring.py:71` (`declared_global`), `scripts/audit_config_wiring.py:106` (`declared_other_scopes`), `scripts/audit_config_wiring.py:594` (`main`) |
| "Dibaca kode" dinilai dengan mencari nama **daun** di seluruh korpus; daun pendek atau umum (`A`, `admin`) memberi hasil keliru ke dua arah | `scripts/audit_config_wiring.py:369` (`hits`) |
| Pemeriksa kesehatan registry juga cukup menemukan nama daun di berkas yang didaftarkan | `backend/services/config_health.py:44` (`_mentions`) |
| Gate memanggil penjaga itu dua kali (ketat dan uji-diri); tidak ada gate yang menulis lalu membaca nilai | `scripts/gate.sh:294` (`audit_config_wiring.py --strict`), `scripts/gate.sh:297` (`--self-test`) |
| Uji putaran 310 kunci sudah ada sebagai skrip audit, belum menjadi tes: tulis grup → baca lewat API, `value_of`, dan pembaca lama → lapisan PT → cabut → nilai tak sah → tanpa alasan → pulihkan | `docs/audit/konfigurasi-peran-2026-11-13/bukti/t1_config.py:98` (`all_entries`); pembangkit nilai `docs/audit/konfigurasi-peran-2026-11-13/bukti/t1_config.py:18` (`alt_value`), `docs/audit/konfigurasi-peran-2026-11-13/bukti/t1_config.py:44` (`bad_value`) |
| 19 kunci bertipe tabel/daftar di skrip itu hanya disimpan ulang dengan nilai yang sama | `docs/audit/konfigurasi-peran-2026-11-13/bukti/t1_config.py:119` (`simpan_ulang_nilai_sama`) |
| Invarian data INV-CFG-01 memakai hasil penjaga yang sama | `scripts/verify_data_integrity.py:2666` (`INV-CFG-01`) |

## Perubahan

### Data

Tidak ada.

### Server

Tidak ada perubahan perilaku aplikasi. Satu fungsi bantu dipakai bersama penjaga dan layar Kesehatan:
`config_health.check_entry` (bila unit KF-T3 belum mengetatkannya, ketatkan di sini dengan aturan yang sama: rujukan
`berkas.py:fungsi` → fungsi harus ada dan hanya badannya yang dipindai; cocok = kunci utuh, atau segmen induk dan daun
sama-sama muncul; keluarga `kontrol.<aksi>.*` cocok lewat literal nama aksinya).

**(1) Uji putaran menjadi gate INV-CFG-08**

| Hal | Isi |
|---|---|
| Tempat | `backend/tests_mem/test_KFT8_putaran_pengaturan.py` (kerangka PK-02; `boot_app` + `server.lifespan` sekali per modul); pembangkit nilai dipindah ke `backend/tests_mem/_nilai_uji.py` |
| Perintah | `python -m pytest backend/tests_mem/test_KFT8_putaran_pengaturan.py -n 0 -q` (± 1 menit) |
| Di gate | Baris baru di `scripts/gate.sh`, kelompok yang tidak ikut `--quick`: `"config_roundtrip (INV-CFG-08, tiap kunci tulis→baca tiga jalur)|python -m pytest backend/tests_mem/test_KFT8_putaran_pengaturan.py -n 0 -q"`. Bila `mongomock_motor` tidak terpasang gate **merah** dengan pesan "pasang mongomock-motor (lihat 03_LINGKUNGAN_UJI §3)", bukan dilewati |
| Bentuk | Satu kasus `pytest` per kunci (`parametrize` atas `config_registry.all_entries()`), bernama `test_KFT8_putaran[<kunci>]`; tiap kasus memulihkan kunci ke bawaan di akhir |
| Pembangkit baru | `list`: tambah/buang satu butir sah (untuk `value_format="regex"` butir `"uji\\d+"`); `table` ber-`columns`: tambah satu baris berisi bawaan kolom; `table` peta: tambah pasangan `"UJI": 1`; `table` JSON: simpan ulang. Dengan ini hanya tabel JSON yang tetap simpan-ulang |

Yang membuat gate merah, per kunci aktif:

| Kode | Keadaan |
|---|---|
| P1 | Nilai yang ditulis di lapisan grup tidak terbaca sama lewat `GET /api/config/effective`, `value_of`, **atau** pembaca lama (`get_effective_settings` / dokumen `system_settings` + `entity_overlay`) |
| P2 | Kunci berlapis PT: nilai PT `ent_kanda` tidak terbaca untuk `ent_kanda`, atau PT `ent_ksc` ikut berubah, pada salah satu dari tiga jalur |
| P3 | Sesudah lapisan PT dicabut nilai tidak kembali ke nilai grup |
| P4 | Nilai tak sah (di luar batas, pilihan tak dikenal, tipe salah) tidak ditolak 400 |
| P5 | Kunci wajib-alasan menerima tulisan tanpa alasan |
| P6 | Sesudah "pulihkan" nilai ≠ bawaan registry |
| P7 | Kunci `not_used` menerima tulisan |
| P8 | Butir jawaban `effective` punya `overridden_by` (unit KF-T3) tetapi `value_of` ≠ pembaca lama, atau `stored_value` ≠ nilai yang ditulis. Untuk kunci demikian P1–P2 dinilai terhadap `stored_value` |

**(2) `scripts/audit_config_wiring.py` menilai seluruh registry**

- Kunci terdeklarasi = gabungan (a) semua entri registry, (b) daun `DEFAULT_GLOBAL_SETTINGS`, (c) isi dokumen selain
  grup bila database ada, (d) setiap kunci literal yang dibaca kode lewat `value_of("…")`, `resolve("…")`, `_cfg("…")`,
  `_config("…")` di `backend/services` dan `backend/routers`. Baris ringkasan menjadi "Total kunci terdeklarasi: N
  (registry R)" dengan N ≥ R.
- Untuk entri registry, "dibaca kode" = hasil `config_health.check_entry`: `OK` → OK; `STALE`/`MISSING` pada kunci aktif
  → `ORPHAN_UI` (tombol palsu); `not_used` → NOT_USED. Pencarian daun (`hits`) hanya untuk butir (b) dan (c) yang tidak
  tercakup registry.
- Butir (d) yang tidak tercakup `config_registry.covers` → `HIDDEN` (dibaca kode, tidak terdaftar).
- `--self-test` bertambah tiga bukti-merah: [7] entri aktif tiruan yang berkasnya tidak memuat kuncinya → harus
  `ORPHAN_UI`; [8] suntik `value_of("tidak.terdaftar")` → harus `HIDDEN`; [9] hapus satu katalog dari impor tiruan → N
  turun dan uji-diri gagal dengan pesan "registry tidak termuat utuh".
- `verify_data_integrity.py` INV-CFG-01 tetap memakai fungsi yang sama; teks hasilnya menyebut jumlah registry.

**(3) Penjaga nilai cadangan INV-CFG-09** — skrip baru `scripts/guardrails/verify_config_fallback.py`:

| Hal | Isi |
|---|---|
| Yang dipindai | Untuk tiap entri registry, berkas pada `consumers`-nya (sintaks diurai dengan `ast`) |
| Merah bila | (a) `<apa pun>.get("<daun>", <literal>)` dengan literal ≠ bawaan registry; (b) `<pembacaan kunci> or <literal>` dengan literal ≠ bawaan, dengan pembacaan kunci = pemanggilan yang memuat kunci utuh atau `.get("<daun>")`; (c) penugasan konstanta huruf besar yang lalu dipakai sebagai cadangan pada bentuk (a)/(b). Literal yang sama dengan bawaan juga merah dengan pesan "pakai `config_registry.default_of`" kecuali untuk `bool` |
| Dikecualikan | `scripts/guardrails/config_fallback_allow.json`: daftar `{"file", "line_text", "key", "alasan"}`. Butir yang tidak lagi cocok dengan kode = merah ("pengecualian basi"). Isi awal: baris nominal `pph21` slip di `hr_payroll_service.py` (bukan pengaturan) |
| Perintah | `python scripts/guardrails/verify_config_fallback.py` dan `--self-test`; `--root <folder>` untuk memindai pohon lain |
| Di gate | Dua baris di kelompok statik `scripts/gate.sh`: `"guard:config_fallback (INV-CFG-09, cadangan = bawaan registry)|python scripts/guardrails/verify_config_fallback.py"` dan `"guard:config_fallback SELF-TEST|… --self-test"` |

**(4) Penjaga "nilai PT diteruskan" INV-CFG-10** — mode `--entity` pada skrip yang sama: untuk kunci yang `scopes`-nya
memuat `entity`, merah bila di berkas pemakainya ada `value_of("<kunci>")` tanpa argumen konteks, atau dengan konteks
literal `{"entity_id": ""}` / `{}`. Pengecualian beralasan di berkas yang sama (kunci `"mode": "entity"`); sisa temuan
KF-10 yang belum dikerjakan unit KF-T3 dimasukkan dengan alasan "KF-T3" sehingga daftar hanya bisa berkurang.

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada.

### Layar

Tidak ada. (Layar Kesehatan Pengaturan otomatis memakai `check_entry` yang lebih ketat.)

## Uji penerimaan

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | Perintah uji putaran | Lulus; jumlah kasus = `len(config_registry.all_entries())`; tidak ada kasus dilewati |
| U2 | B (bukti-merah) | `monkeypatch` `config_resolver._project` menjadi tanpa-kerja | Jalankan kasus `tax.ppn_mode` | Gagal dengan kode P1 menyebut "pembaca lama" |
| U3 | B (bukti-merah) | `monkeypatch` `config_registry._bounded` mengembalikan nilai apa adanya | Kasus `ar.grace_days` | Gagal P4 |
| U4 | B (bukti-merah) | `monkeypatch` `build_layers` membuang lapisan `entity` | Kasus `sales.allow_partial_shipment` | Gagal P2 |
| U5 | B (bukti-merah) | `monkeypatch` `set_value` melewati pemeriksaan alasan | Kasus satu kunci berisiko tinggi | Gagal P5 |
| U6 | statik | — | `python scripts/audit_config_wiring.py` | Baris "Total kunci terdeklarasi: N (registry R)", R = jumlah entri registry, N ≥ R; pelanggaran 0 |
| U7 | statik | — | `python scripts/audit_config_wiring.py --self-test` | PASS dengan butir [1]–[9] |
| U8 | statik (bukti-merah) | Tambah sementara `E("uji.kunci_palsu", …, consumers=("services/config_service.py:compute_tax",))` di berkas uji | `--strict` | Keluar 1; `uji.kunci_palsu` berstatus `ORPHAN_UI` |
| U9 | statik | — | `python scripts/guardrails/verify_config_fallback.py` | Keluar 0; 0 temuan; pengecualian = 1 butir |
| U10 | statik (bukti-merah historis) | `git worktree add <tmp> 3132cc4` | `verify_config_fallback.py --root <tmp>` | Keluar 1; temuan memuat sedikitnya `tax.ppn_rate`, `tax.dpp_nilai_lain`, `sales.allow_item_discount`, `inventory.intercompany_transfer_required`, `ar.denda_rate_pct_per_month`, `commission.discount_threshold`, `commission.discount_factor`, `sales.require_so_validation`, `allocation.lot_selection`, `approval.po_custom_direksi_min` |
| U11 | statik | — | `verify_config_fallback.py --self-test` | PASS: suntikan `tax.get("ppn_rate", 0)` terdeteksi; pengecualian basi terdeteksi |
| U12 | statik | — | `verify_config_fallback.py --entity` dan uji-dirinya | Keluar 0 dengan pengecualian beralasan saja; suntikan `value_of("inventory.default_uom")` terdeteksi |
| U13 | statik | — | `bash scripts/gate.sh --quick` | Empat baris statik baru tampil (cadangan, cadangan uji-diri, PT diteruskan, kabel pengaturan uji-diri); tidak ada gate yang tadinya hijau menjadi merah |
| U14 | B | — | `config_health.report()` | `broken == []`; jumlah baris = jumlah entri registry |

## Langkah kerja

1. Pindahkan logika `t1_config.py` menjadi tes berparameter + pembangkit nilai; U1 hijau, U2–U5 membuktikan bisa merah.
2. Perluas `audit_config_wiring.py` (butir a–d, tiga uji-diri); U6–U8.
3. `verify_config_fallback.py` (dua mode) + berkas pengecualian; U9–U12.
4. Daftarkan baris gate; U13. Laporan memuat keluaran tiap perintah dan waktu jalannya.

## Dokumen ikut berubah

`docs/blueprint/03_LINGKUNGAN_UJI.md` §3 (baris `t1_config.py` → tes gate) dan §4 (gate baru);
`docs/KN_00_AGENT_QUICK_START.md` bagian gate bila memuat daftar gate; `CODEBASE_MAP.md` (dua skrip/berkas baru);
`docs/audit/konfigurasi-peran-2026-11-13/bukti/README.md` (catatan bahwa `t1_config.py` kini punya padanan gate).

## Di luar lingkup

- Menguji bahwa tiap pemakai **berperilaku** sesuai nilainya: tetap kewajiban unit yang menambah kunci (`02` §2.4 butir
  2); penjaga ini hanya membuktikan pipa, cadangan, dan penerusan PT.
- Memperbaiki temuan yang ditemukan penjaga pada kunci milik unit lain: unit pemilik kuncinya (KF-T2, KF-T3).
- Penjaga matriks izin → PR-T8. Penjaga bahasa → `audit_i18n_id` (KF-T4).

## Asumsi dan risiko

- `ASUMSI:` nomor invarian INV-CFG-08, -09, -10 belum terpakai; bila terpakai, pakai nomor bebas berikutnya dan catat.
- `ASUMSI:` `mongomock-motor` tersedia di lingkungan tempat gate penuh dijalankan (dipasang PK-02).
- `RISIKO:` penjaga cadangan memberi temuan palsu pada `.get("<daun>", …)` yang bukan pengaturan (nama daun umum).
  Penangkal: hanya berkas `consumers` kunci itu yang dipindai, dan berkas pengecualian beralasan. Membatalkan: cabut baris
  gate; tidak ada kode aplikasi yang bergantung pada skrip ini.
