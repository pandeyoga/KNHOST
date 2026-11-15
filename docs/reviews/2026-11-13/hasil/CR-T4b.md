# CR-T4b — "Hari ini" akrual denda dari Umur Piutang = tanggal buku server, bukan `?today=` klien

- Commit awal: `fc95d36` (ujung `claude/nifty-carson-jjx3c8`, `[CR-T4]`)        - Commit akhir: `20c6096` (kode + uji; laporan dan tracker di commit berikutnya)        - Branch: `claude/sleepy-allen-c6cnpi` (maju-cepat dari `fc95d36`)
- ID ditangani: **T4-01** (usulan; temuan baru, ditemukan saat CR-T4 dikerjakan — bagian "Ditemukan, di luar lingkup"
  laporan [CR-T4](CR-T4.md), di-commit `4580bd9` di `claude/nifty-carson-jjx3c8` sesudah cabang ini dibuat dari
  `fc95d36`; cabang ini bergabung dengan ujung itu tanpa konflik).
  Kelas yang sama dengan butir 2 PK-08 ("hari ini" dari server, `docs/blueprint/unit/PK-08.md`).
- Unit: lanjutan CR-T4 (pemecahan `00_ATURAN_EKSEKUSI.md` §8, akhiran `b`) atas arahan pemilik sesi 15 Nov. Berkas
  CR-T4 (laporan, baris CR-07 di tracker, baris CR-T4 di `docs/blueprint/STATUS.md`) **tidak disentuh** — unit itu masih
  `dikerjakan` di worktree lain.

## T4-01 — `POST /api/ar/aging/{customer_id}/accrue-penalties` menerima "hari ini" dari klien

- Berlaku di HEAD: **ya — dijalankan** (bukti merah 4/4 di `fc95d36`, `bukti/CR-T4b/merah_kode_lama.txt`).

  | Jangkar di `fc95d36` | Isi |
  |---|---|
  | `backend/routers/ar_aging.py:58-59` | `ar_aging_accrue(customer_id, request, today: str = Query(""))` |
  | `backend/routers/ar_aging.py:72` | `penalties.accrue_customer(customer_id, today=today or None, …)` → `accrue_plan(…, today=…)`: hari telat (`_days_late`) dan kunci periode nota (`_period_key`) dari tanggal klien |
  | `backend/routers/ar_aging.py:76-78` | rincian umur piutang di jawaban: `customer_aging_detail(…, as_of=today or None, …)` |

  Endpoint akrual lain yang dicek:

  | Jalur | Di `fc95d36` |
  |---|---|
  | `POST /api/payment-plans/{plan_id}/accrue` (`payment_plans.py:227`) | sudah tanpa `today` sejak PK-08 (`0b41a2b`); layanan dipanggil tanpa `today` |
  | `POST /api/scheduler/jobs/{job_id}/run` (job `penalty_accrual`) | `scheduler_service.run_job` memanggil `job["fn"]()` tanpa argumen; `RunJobRequest.payload` tidak diteruskan → tanggal server |
  | Pemanggil `accrue_for_order` (`finance_case_actions.py:989`, giro ditolak) | tanpa `today` → tanggal server |
  | `seed_realistic.py:6467` | `accrue_plan(plan, …)` tanpa `today` |
  | Rute lain dengan parameter kueri `today` | tidak ada (`grep -n "today" backend/routers/*.py` hanya `ar_aging.py:59`) |

- Akar masalah: PK-08 mencabut `?today=` hanya dari `accrue_now` (rencana bayar). Tombol "Buat Nota Denda" di laporan
  Umur Piutang memakai rute lain (`ar_aging_accrue`) yang tetap meneruskan tanggal klien ke mesin akrual yang sama.
  Pengguna ber-izin `penalty.issue` bisa (a) melahirkan nota dengan hari telat masa depan — `?today=2099-01-01` atas
  piutang 5.000.000 telat 30 hari menjadi nota **Rp 87.966.666,67 / 26.390 hari** berkunci periode `…|2099-01`, dan
  karena kunci periodenya lain, nota itu tidak bertabrakan dengan nota bulan berjalan sehingga hari-harinya ikut
  dihitung sebagai "sudah ditagih" (`_days_already_billed`) oleh akrual berikutnya; atau (b) menekan denda dengan tanggal
  mundur (`?today=2026-09-15` → 0 nota). Di PT ber-`payment.penalty_mode` `auto` nota (a) langsung terbit dan berjurnal
  (Dr 1-1270 / Cr 4-9300, pola jurnal terbit PK-08) tanpa tahap usulan.
- Perubahan perilaku (sebelum → sesudah):

  | | Sebelum | Sesudah |
  |---|---|---|
  | Tanda tangan rute | `today: str = Query("")` | parameter dicabut; `?today=` yang masih dikirim diabaikan (FastAPI tidak menolak kueri tak dikenal) |
  | "Hari ini" akrual | `today` klien, kosong → tanggal buku WIB | selalu tanggal buku WIB server (`accrue_plan` → `book_date.tanggal_buku()`) |
  | Rincian `detail` di jawaban | `as_of = today` klien | tanpa `as_of` → posisi hari ini server (`ar_aging_service._per`) |

  Parameter `today` pada fungsi layanan (`accrue_customer`, `accrue_plan`, `job_penalty_accrual`) **tetap ada** untuk
  penjadwal dan uji — sama dengan putusan PK-08 butir 2. Uji yang sah membekukan "hari ini" lewat
  `services.book_date._sekarang`, bukan lewat HTTP.
- Berkas berubah: `backend/routers/ar_aging.py` (tanda tangan + docstring + dua pemanggilan);
  `backend/tests_mem/test_CRT4b_hari_ini_server.py` (baru).
- Pemanggil dialihkan dan dibuktikan dengan pencarian (`00_ATURAN_EKSEKUSI.md` §7.3): `grep -rn "accrue-penalties"` di
  `frontend/src`, `backend/`, `tests/`, `scripts/` — layar (`ARAgingView.jsx:108`) dan POC (`test_core_role_access_poc.py:196,202`,
  `tests/archive/backend_test_g3.py:311,318`) **tidak pernah** mengirim `today`. Tidak ada pemanggil yang perlu diubah.
- Commit: `20c6096`
- Pengujian:

  | ID | Lapis | Uji | Kode lama `fc95d36` | Sesudah |
  |---|---|---|---|---|
  | U1 | B | Server dibekukan 31 Okt 2026 (`_sekarang`); dua pelanggan kembar D1 (5.000.000 NET30, jatuh tempo 1 Okt). A tanpa parameter, B `?today=2099-01-01`. Harapan keduanya 1 nota 100.000 / 30 hari / `2026-10-01\|2026-10`; Σ B ≤ Σ A; `detail.items[0]` 30 hari / taksiran 100.000; diulang `?today=2098-06-30` → tetap 1 nota | **merah** — B: 87.966.666,67 / 26.390 hari / `2026-10-01\|2099-01` | lulus |
  | U2 | B | Server 20 Sep 2026 (belum jatuh tempo), `?today=2099-01-01` → `count` 0, tanpa nota | **merah** — 1 nota lahir | lulus |
  | U3 | B | Server 31 Okt 2026, `?today=2026-09-15` (mundur) → tetap 1 nota 100.000 | **merah** — `count` 0 | lulus |
  | U4 | B | Kontrak OpenAPI: semua rute berjalur `accrue` (termasuk dua rute di atas) tidak menyatakan parameter kueri `today`/`as_of`/`date`/`tanggal`/`hari_ini` | **merah** — `POST …/accrue-penalties` menerima `today` | lulus |

  Hitung tangan (rumus harian PK-08, kunci bawaan registry: tarif 2 %/bln, tenggang 0, batas 0 % = tanpa batas, minimum
  10.000): 5.000.000 × 2 % × 30 ÷ 30 = **100.000**; kode lama dengan 2099-01-01: telat (2099-01-01 − 2026-10-01) =
  26.390 hari → 5.000.000 × 2 % × 26.390 ÷ 30 = **87.966.666,67**.

  Perintah: `cd backend && python -m pytest tests_mem -q` (dua pekerja, `pytest.ini` tidak diubah). Hasil
  (`bukti/CR-T4b/tests_mem_penuh.txt`):

  | Kode | Hasil |
  |---|---|
  | `fc95d36` sebelum perubahan | 2.125 lulus, **1 gagal** (`test_KPT9_U02`, hambatan lingkungan `/app` — lihat di bawah; sesudah symlink `/app` uji itu lulus di kode lama juga, `test_KPT9_hub_pengaturan.py` 10/10), 2 dilewati, 2 diharapkan gagal |
  | `20c6096` sesudah perubahan | **2.130 lulus, 0 gagal**, 2 dilewati, 2 diharapkan gagal (= 2.125 + KPT9_U02 + 4 uji baru) |

  Tidak ada tanda "diharapkan gagal" milik temuan ini yang perlu dicabut (T4-01 temuan baru).
- Bukti UI: tidak ada perubahan layar (layar tidak pernah mengirim `today`); belum diuji jalan di peramban.
- Fixture disiapkan langsung vs proses bisnis dijalankan: pesanan, surat jalan, dan jurnal `shipment_revenue` disisip
  langsung (bentuk D1 CR-T4); jadwal tagihan lewat kait CR-T2 `on_shipment_posted`; nota denda lewat API
  `POST /api/ar/aging/{id}/accrue-penalties` sebagai Admin.
- Dampak pada modul terkait: tidak ada perubahan di layanan denda, jadwal, atau umur piutang. Klien yang dulu mengirim
  `?today=` (tidak ada yang ditemukan) kini mendapat hasil per tanggal server tanpa galat.
- Keterbatasan / yang belum diuji: lapis A (MongoDB asli) tidak dijalankan — tidak ada perilaku bersamaan/keunikan yang
  berubah. Nota lama yang mungkin sudah terlanjur lahir dari `?today=` klien tidak diperbaiki (perbaikan data bukan
  wewenang unit kode, `00_ATURAN_EKSEKUSI.md` §7.2); kueri pencarinya di "Yang perlu direview".
- Status: implemented_pending_review

## Gate

- `gate.sh --quick` di container sesi ini, kode lama `fc95d36` (worktree terpisah, `/app` diarahkan ke sana) vs kode
  baru `20c6096`: **22 merah = 22 merah, daftar identik (lebih merah 0)** — `bukti/CR-T4b/gate_quick_lama_vs_baru.txt`.
  Angka ini lebih tinggi dari garis dasar resmi (PK-01: 16; MN-T2 di `b7837de`: 12) karena lingkungannya lain: 10 di
  antaranya gagal dengan `KeyError: 'MONGO_URL'` (tidak ada `backend/.env`/MongoDB), sisanya sama di kedua kode.
  `memory/GATE_RECEIPT.*` hasil jalan ini tidak di-commit (`00_ATURAN_EKSEKUSI.md` §3).
- `gate.sh` bawaan / `--ci` (runtime, seed, invarian data acuan — termasuk INV-PEN-01…03): **tidak dijalankan**, lihat
  hambatan lingkungan. Perubahan hanya mencabut satu parameter kueri dari satu rute; tidak ada jurnal, koleksi, indeks,
  atau data acuan yang berubah.

## Hambatan lingkungan

- Container sesi cloud: tanpa daemon Docker dan tanpa MongoDB → gate bawaan/`--ci` (runtime, seed, invarian data acuan)
  tidak bisa dijalankan; hanya `--quick` (statik).
- Python 3.13 bawaan diganti venv Python 3.11 (versi yang diukur README `tests_mem`); `litellm` dan
  `emergentintegrations` dilewati saat memasang dependensi (hanya tersedia dari server aset Emergent, tidak terjangkau
  proksi; tidak dipakai `tests_mem`).
- `tests_mem/test_KPT9_hub_pengaturan.py::test_KPT9_U02` memanggil `scripts/check_nav_map.py` yang membaca jalur tetap
  `/app/frontend/src/config/roles.js` (jalur repo di container Docker dev). Tanpa `/app` uji itu gagal di HEAD sebelum
  perubahan (garis dasar: 1 gagal, 2.125 lulus). Diatasi di luar repo dengan symlink `/app → repo` di container ini;
  sesudahnya lulus. Tidak ada berkas repo yang diubah untuk ini.

## Yang perlu direview

- Nota yang mungkin lahir dari `?today=` klien sebelum perbaikan (kunci periode bulan di depan bulan dibuat, atau hari
  telat melebihi umur nyata baris saat dibuat):

```js
db.penalties.find({$expr: {$gt: [{$substr: ["$period_key", 11, 7]}, {$substr: ["$created_at", 0, 7]}]}},
                  {_id: 0, number: 1, customer_id: 1, period_key: 1, created_at: 1, days_late: 1, amount: 1, status: 1})
```

  (`created_at` UTC; nota yang dibuat 00.00–06.59 WIB tanggal 1 bisa muncul sebagai positif palsu — periksa `days_late`
  terhadap `due_date`.)
- ID usulan **T4-01** dicatat di tracker bagian "Temuan tambahan dari implementer"; baris papan kerja
  `docs/blueprint/STATUS.md` untuk CR-T4b sengaja tidak ditambahkan karena baris CR-T4 di sebelahnya sedang diubah
  agen lain — mohon koordinator menambahkannya saat menggabung.
- Menggabung cabang ini dengan `claude/wizardly-fermi-q8jeii`: keduanya menambah baris di akhir tabel "Temuan tambahan
  dari implementer" di `TRACKER.md` (konflik baris yang sepele: ambil keduanya).

## Asumsi

- `?today=` yang masih dikirim klien **diabaikan** (200, hasil per tanggal server), bukan ditolak 422 — sama dengan
  perilaku PK-08 U9 di `POST /api/payment-plans/{id}/accrue`.
- Tanggal acuan rincian `detail` di jawaban ikut tanggal server; posisi umur piutang per tanggal lain tetap tersedia
  lewat `GET /api/ar/aging/{customer_id}?as_of=` (baca saja, tidak membuat nota).
