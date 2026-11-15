# CR-T4 — Denda berlapis PT → pelanggan → rencana, dihitung dari jadwal tagihan

- Commit awal: `53b419b` (worktree kerja, basis B)        - Commit akhir: `fc95d36`        - Branch: `claude/nifty-carson-jjx3c8`
- Digabung pelaksana ke worktree tujuan pada HEAD **`b7837de`** (`[MN-T2] Cek layar 1024 px`, sesudah KM-T2, PY-T3, MN-T2),
  lalu T dipindah ke **`c8c6d03`** (`MN-T2 selesai: laporan, bukti, STATUS` — hanya laporan/bukti/STATUS, tanpa berkas
  kode/dokumen yang disentuh unit ini); bentrok tekstual hanya di dokumen, kedua perilaku dipertahankan — lihat "Penggabungan"
- ID ditangani: CR-07 (spesifikasi `docs/blueprint/unit/CR-T4.md`; keputusan K-30 "denda: mode per PT; dasar = sisa baris
  tagihan yang telat", bawaan = hari ini `draft`)
- Risiko **sedang** → satu serah-terima (`00` §8 tidak berlaku).

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`; diperiksa di `53b419b`)

| Fakta spesifikasi | Hasil di basis B |
|---|---|
| Aturan denda global → PT → pelanggan lewat resolver, lalu ditimpa `plan.penalty` (`penalty_service.py:59`/`:83`) | Berlaku, bergeser — `penalty_policy` `:63`, konteks `customer_id` `:71`, `over` `:87` |
| Lima kunci mendukung lapisan `customer`, layar Pusat Pengaturan hanya Global & PT (`config_catalog_payment.py:20`, `config_catalog_core.py:140`, `SettingsScopeBar.jsx:66`) | Berlaku, bergeser — `GC` `:20` dipakai `payment.penalty_mode` `:181`, `_base` `:194`, `_cap_pct` `:205`; `ar.denda_rate_pct_per_month` `config_catalog_core.py:243`, `ar.grace_days` `:254`; `cfg-scope-type` `SettingsScopeBar.jsx:67`. Lapisan pelanggan kunci-kunci ini SUDAH punya layar di kartu pelanggan (KF-T5, Customer360Panel › Aturan khusus pelanggan ini) — sesuai ASUMSI unit, layar itu kehilangan lima kunci denda dengan sendirinya |
| Lapisan pelanggan resolver hanya berkunci id pelanggan (`:67`) | Berlaku (`:71`) |
| Job harian hanya memindai `payment_plans` aktif (`:584`, `scheduler_service.py:145`) | Berlaku, bergeser — `job_penalty_accrual` `:771` memindai `status: active` **dan `origin ≠ term`** (CR-T2 menahan jadwal mesin sampai unit ini); `scheduler_service.py:164` |
| Pesanan tanpa rencana hanya lewat tombol umur piutang, jatuh tempo = tanggal pesanan + termin (`:219`, `ar_aging.py:58`) | Berlaku, bergeser — `accrue_order` `:260` (`report_basis.hari_termin` sejak CR-T2), `accrue_customer` `:332`; `ar_aging_accrue` `routers/ar_aging.py:58`. **Pemanggil kedua** yang tidak disebut spesifikasi: `finance_case_actions.act_batalkan_kwitansi` (`:990`, giro ditolak + nota denda) |
| Dasar = sisa baris telat; rumus `dasar × tarif × hari ÷ 30` (`:154`, `:109`) | Berlaku, bergeser `:180` / `:119` (PK-08: hari kumulatif, `days_prior`) |
| Mode `off` melewati rencana; tanpa alasan/masa berlaku (`:144`) | Berlaku, bergeser `:170` |
| Taksiran umur piutang dibulatkan bulan penuh (`ar_aging_service.py:81`) | Berlaku, bergeser `:88` (`math.ceil(eff / 30)`) |
| Form rencana bayar tanpa isian denda walau `plan.penalty` disimpan (`payment_plan_service.py:319`) | Berlaku, bergeser `:356`/`:364`; disimpan tanpa pemeriksaan angka |
| (PK-41, CR-T2) dasar laporan & jadwal | `report_basis.baris_tagihan` membaca `billing_schedule_service.lines_for_orders`; setiap pesanan piutang punya jadwal `term` (kait `on_shipment_posted` dkk.); data lama sebelum `build_billing_schedule.py --apply` dibaca tanpa disimpan |
| (CR-T1) `penalty_rule` | Disimpan apa adanya, hanya diperiksa bentuk (`credit_profile_service._aturan_denda` `:284`); `bebas` boleh tanpa alasan/tanggal; tidak dibaca mesin |

## Perubahan

| Berkas | Isi |
|---|---|
| `backend/services/penalty_service.py` | `penalty_policy(entity_id, customer_id, plan)` (tanda tangan tetap; tambahan opsional `today`, `pt_cache`): (1) aturan grup → PT lewat resolver konteks `{"entity_id"}` saja (PT kosong + pelanggan → PT pemilik data pelanggan); (2) profil kredit (pelanggan, PT) — `khusus` menimpa unsur terisi, `bebas` yang berlaku → `mode: off` + `waiver {reason, valid_until}`, lewat/tanpa tanggal → ikut PT (`expired_waiver` untuk layar); (3) `plan.penalty` paling khusus; jawaban + `sources` (`global`·`pt`·`pelanggan`·`rencana`). Cadangan = bawaan registry (`default_of`, tanpa `or <literal>`). `estimate()` = taksiran satu baris (rumus, tenggang, batas atas, minimum, mode sama dengan nota). `accrue_plan` jadwal apa pun asalnya, hari ini = tanggal buku WIB, jadwal mesin pesanan non-piutang (tunai) dilewati seperti dulu, nota draf yang diperbarui ikut memperbarui potret aturannya. **`accrue_order` dihapus** (D8) → `accrue_for_order(order_id)` (jadwal hidup pesanan); `accrue_customer` dan `job_penalty_accrual(today=None)` memindai semua jadwal `active` (`by_origin` di jawaban job). Teks `explain` dasar: "sisa tagihan yang telat" / "seluruh sisa pesanan" |
| `backend/services/ar_aging_service.py` | `get_ar_config(entity_id, customer_id, plan=None, pt_cache=None)` dari `penalty_policy` (+ `penalty`, `source` berlabel asal); `_denda_estimate` = `penalty_service.estimate` (dasar "seluruh sisa pesanan" = Σ sisa baris pesanan); aturan per (PT pesanan, pelanggan, rencana berdenda) — `_rencana_berdenda` satu kueri; `math` dicabut |
| `backend/services/credit_profile_service.py` | `_aturan_denda` menurut tabel Data: `ikut_pt` → `null`; `khusus` tarif & batas 0–100 (registry), tenggang 0–180, dasar dari pilihan `payment.penalty_base`; `bebas` alasan ≥ 5 huruf + `valid_until` wajib → 400 "Bebas denda wajib beralasan dan punya tanggal berakhir."; tarif di luar batas → 400 "Tarif denda harus antara 0 dan 100 % per bulan." |
| `backend/services/payment_plan_service.py` | `penalty_override()` memeriksa `plan.penalty` (create/update) sebelum apa pun ditulis — tarif 400 dengan kalimat yang sama; mode rencana `""·off·draft·auto` |
| `backend/routers/payment_plans.py` | `GET /api/customers/{id}/penalty-policy?entity_id=` — `penalty.view` (pernyataan pertama) + `can_view_credit` (404) + `resolve_requested_entity` (N1); `{effective: {mode, rate_pct_per_month, base, cap_pct, grace_days, min_amount}, sources, waiver}` (+ `customer`, `entity_id`, `expired_waiver`, `customer_rule_mode`, `rule`) |
| `backend/services/finance_case_actions.py` | giro ditolak + nota denda → `accrue_for_order` (pemanggil `accrue_order` dialihkan) |
| `backend/config_catalog_payment.py`, `backend/config_catalog_core.py` | `scopes` lima kunci → `("global", "entity")`; `help` "Untuk pelanggan tertentu, atur di kartu pelanggan (Aturan denda)."; `consumers` `ar.denda_rate_pct_per_month`/`ar.grace_days` + `penalty_service.py:penalty_policy` |
| `backend/services/scheduler_service.py` | keterangan job "Hitung Denda Keterlambatan" (jadwal tagihan + rencana; pelanggan bebas dilewati) |
| `scripts/migrate_penalty_customer_layer.py` (baru) | lapisan pelanggan lima kunci → `penalty_rule` profil (PT = `customers.entity_id`) `khusus`, unsur profil yang sudah terisi tidak ditimpa, lalu `clear_layer` (nisan); `off` per pelanggan → `bebas` hanya dengan `--bebas-sampai` (tanpa: dilaporkan "menunggu", tidak disentuh); `draft`/`auto` per pelanggan → dilepas + dilaporkan; `--dry-run` bawaan; idempoten (H3) |
| `scripts/guardrails/config_fallback_allow.json` | 7 pengecualian basi dicabut (5 `penalty_service`, 2 `ar_aging_service`) — cadangan kini `default_of`; daftar hanya berkurang |
| Layar | `features/finance/payments/penaltyRuleUi.jsx` (baru: empat isian aturan denda, teks aturan, "Aturan dari"); `features/crm/CustomerPenaltyRule.jsx` (baru: bagian "Aturan denda" tab Kredit); `CustomerCreditTab.jsx` (memasang bagian itu); `CreditProfileRequestModal.jsx` (bagian 4 "Aturan denda": Ikut PT · Khusus · Bebas denda); `creditProfileUi.jsx` (`valueText('penalty_rule')` → "Khusus: tarif 1 % per bulan" / "Bebas denda s.d. …"); `PaymentPlanBuilder.jsx` (bagian lipat "Aturan denda khusus rencana ini", `penalty` ikut dikirim); `PenaltyPanel.jsx` ("Aturan dari: PT · pelanggan · rencana", kelompok per pelanggan bila > 1 pelanggan); `ARAgingView.jsx` (catatan kaki: taksiran = aturan nota; kata dasar hitung) |
| Uji | `backend/tests_mem/test_CRT4_denda_berlapis.py` (18), `frontend/src/features/__tests__/crt4AturanDenda.test.js` (5), lapis A `backend/tests/test_bp_CRT4_putaran_pertama.py` (ditulis) |
| Dokumen | `ENTITY_REGISTRY.md` (`penalty_rule`, `penalties.policy_snapshot.sources`), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.23 (di T **§9.26**), `scripts/INDEX.md` (skrip migrasi — `gen_codebase_map.py` tidak memetakan skrip), `CODEBASE_MAP.md` (dibangkitkan), `configKeyIndex.json` (dibangkitkan, tanpa selisih) |

Pencarian pematian jalur lama (D8, §7.3): `grep -rn "accrue_order" --include=*.py .` → hanya komentar + uji PK-08 yang
dialihkan (`assert not hasattr(ps, "accrue_order")`); `POST /api/ar/aging/{customer_id}/accrue-penalties` tetap ada dan
memanggil `accrue_customer`.

## Uji penerimaan

Merah di kode lama: **17 merah / 1 hijau (U11)** — `bukti/CR-T4/merah_kode_lama.txt` (sebab: job melewati jadwal `term`
→ 0 nota; `penalty_policy` tanpa `sources`/`waiver`; taksiran 200.000 dan 8.000; lapisan pelanggan diterima 200; endpoint
404; `bebas` tanpa alasan diterima; modul skrip tidak ada). Hijau di kode baru: **18/18**.

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah: 0 nota (jadwal `term` dilewati) | lulus — 1 nota draf 100.000 (30 hari, dasar 5.000.000), pesanan tanpa rencana cicilan, `sources.rate_pct_per_month == "global"`; job kedua hari yang sama tetap 1 nota |
| U2 | B | merah: 0 nota | lulus — profil `khusus` tarif 1 (pengajuan + keputusan lewat API) → 50.000, sumber `pelanggan` |
| U3 | B | merah: 0 nota | lulus — Q (`ent_ksc`, tarif PT 3) 150.000 sumber `pt`; P (`ent_kanda`) 100.000 sumber `global` |
| U4 | B | merah: `mode` tetap `draft` | lulus — `bebas` s.d. 2026-12-31 → mode `off`, `waiver` {Kesepakatan direksi, 2026-12-31}; tidak ada nota P, pembanding tanpa bebas 100.000 |
| U5 | B | merah: `waiver` tidak ada | lulus — `valid_until` 2026-10-30 (diajukan 29 Okt) dibaca ikut PT per 31 Okt → 100.000 |
| U6 | B | merah: 37.500 (tanggal UTC server, bukan tanggal buku) | lulus — rencana manual tarif 0,5 me-void jadwal term; nota rencana 25.000 sumber `rencana`; jadwal term tanpa nota |
| U6b (tambahan) | B | merah: 200 | lulus — tarif rencana 120 → 400 "Tarif denda harus antara 0 dan 100 % per bulan." |
| U7 | B | merah: 0 nota | lulus — tenggang 10 → 66.666,67 (20 hari), sumber tenggang `pelanggan`, tarif `global` |
| U8 | B | merah: 0 nota | lulus — batas 1 % → 50.000 (mentah 100.000 tertulis di `explain`) |
| U9 | B | merah: 0 nota | lulus — terbayar 2.000.000 → dasar 3.000.000 → 60.000 |
| U10 | B | merah: taksiran 8.000 | lulus — tidak ada nota; taksiran umur piutang 0 (8.000 < minimum 10.000) |
| U11 | B | **lulus** (PK-08) | lulus — terbit 100.000 → bayar 60.000 → bebas 40.000: saldo 1-1270 nota itu 0, `waived_amount` 40.000 |
| U12 | B | merah: 0 nota | lulus — Sales (akun uji ber-PT `ent_kanda`) mengajukan bebas → job 31 Okt tetap 100.000; Manajer menyetujui → job 30 Nov tanpa nota baru, nota Oktober tidak disentuh (`updated_at` sama) |
| U13 | B | merah: taksiran 200.000 | lulus — `GET /api/ar/aging/{P}?as_of=2026-11-15`: telat 45, taksiran 150.000 (= total); job → nota 150.000 (45 hari) |
| U14 | B | merah: 200 | lulus — `payment.penalty_mode` lapisan pelanggan → 400 "“Denda telat: usulan atau langsung terbit” tidak bisa dibedakan per pelanggan.", tanpa baris baru; lima kunci `scopes == [global, entity]`, putaran `t1_config` (KF-T8 `putaran`) lulus kelimanya |
| U15 | B | merah: 404 | lulus — Tanpa Acuan + `penalty.view` 200 (efektif 2 %/`draft`/10.000, `waiver` null); Manajer Kosong 403; Sopir 403 |
| U15b (tambahan) | B | merah: `bebas` tanpa alasan diterima | lulus — bebas tanpa alasan / tanpa tanggal / alasan 2 huruf → 400 kalimat spesifikasi; tarif 101 → 400; tanpa pengajuan tersimpan |
| U16 | B | merah: modul tidak ada | lulus — lapisan pelanggan `ar.denda_rate_pct_per_month` 1,5 (fixture sisip) → baca-saja tanpa tulisan; tulis: profil P `khusus` tarif 1,5, lapisan bernisan; putaran kedua tanpa perubahan (versi profil & jumlah `config_values` sama); `penalty_policy` 1,5 sumber `pelanggan` |
| U17 | layar | jest merah 5/5 (`bukti/CR-T4/jest_merah_layar_lama.txt`) | jest `crt4AturanDenda` 5/5 hijau. **Belum diuji jalan** di peramban (integrator) |
| lapis A | A | — | **ditulis, belum dijalankan** — `backend/tests/test_bp_CRT4_putaran_pertama.py` (jumlah nota draf putaran pertama di data acuan per asal jadwal, tanpa jurnal, idempoten; `penalty-policy` di data acuan; baris lapisan pelanggan lima kunci) |

### Contoh angka (hitung tangan; U1 dan U2)

- **U1** — `ent_kanda`, aturan grup bawaan (2 %/bulan, tenggang 0, dasar sisa tagihan yang telat, minimum 10.000). Pesanan
  5.000.000 NET30, surat jalan 1 Sep berjurnal **Dr 1-1200 5.000.000 / Cr 4-1000 5.000.000** → jadwal `term` satu baris
  5.000.000 jatuh tempo 1 Sep + 30 = **1 Okt**. Job 31 Okt: telat 30 − tenggang 0 = 30 hari → 5.000.000 × 2 % × 30 ÷ 30 =
  **100.000** ≥ 10.000 → nota `DN-DENDA` **draf, tanpa jurnal** (`policy_snapshot.sources` semua `global`). Bila
  diterbitkan (PK-08, tidak diubah unit ini): **Dr 1-1270 Piutang Denda 100.000 / Cr 4-9300 Pendapatan Denda 100.000** →
  saldo piutang denda pelanggan 100.000 (= INV-PEN-03), saldo piutang tersimpan (CR-T2) disegarkan.
- **U2** — profil kredit (P, `ent_kanda`) `penalty_rule {mode: khusus, rate_pct_per_month: 1}` lewat pengajuan PKR +
  keputusan → unsur tarif `pelanggan`, unsur lain tetap `global`: 5.000.000 × **1 %** × 30 ÷ 30 = **50.000** (draf). Terbit:
  Dr 1-1270 50.000 / Cr 4-9300 50.000.
- Taksiran umur piutang = nota (U13): telat 45 hari → 5.000.000 × 2 % × 45 ÷ 30 = **150.000**; kode lama 5.000.000 × 2 % ×
  ⌈45/30⌉ = 2 bulan = 200.000.

## Uji lama yang menguji perilaku yang sengaja diubah (dilaporkan)

- `tests_mem/test_PK08_denda.py` U08 — `accrue_order` dihapus; fixture setara (surat jalan 10 Jan 2027 berjurnal, termin 0)
  lewat jadwal tagihan + `accrue_for_order`; angka harapan PK-08 sama (21 hari / 42.000, lalu 28 hari / 56.000).
- `tests_mem/test_CRT2_jadwal_saldo.py` `a_pembaca_lama_mengabaikan_jadwal_mesin` — job kini memindai jadwal mesin
  (`by_origin.term.scanned ≥ 1`); panel rencana & daftar rencana tetap mengabaikan jadwal mesin.
- `tests_mem/test_KFT5_aturan_khusus.py` — lima kunci denda bukan lagi kunci lapisan pelanggan (8 → 3 kunci); U1/U2/U9/U11/
  U12/riwayat memakai `payment.variance_overpay_default`, U8 `payment.variance_tolerance_rupiah`; U1/U4 menegaskan 400 dan
  mesin tetap memakai aturan PT; U13 memeriksa `scopes` + `help` lima kunci denda.
- `tests_mem/test_KFT4_registry.py` U2 — `BERUBAH_SESUDAH` + `scopes` lima kunci (potret sebelum KF-T4 tetap).
- Lapis A (ditulis, belum dijalankan): `backend/tests/test_bp_KFT5_aturan_khusus.py` (kunci selisih bayar; 3 butir;
  `ar.grace_days` per pelanggan → 400) dan **POC gate** `backend/test_g0_config_poc.py` TEST 2 (lapisan pelanggan kunci
  bunga denda kini DITOLAK; urutan lapisan diuji dengan `payment.variance_tolerance_rupiah` Rp 7.500; dibersihkan).

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`fc95d36`**:

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`b7837de`: 12 / 39). Kuitansi: `bukti/CR-T4/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- HEAD cabang tetap `c8c6d03` sejak pelaksana menggabung; T disalin apa adanya → **`fc95d36`** (33 berkas). `tests_mem` di T
  2126/2/2 dan jest 1034 (pelaksana, pohon sama).
- Lingkungan A (`bukti/CR-T4/integrator_lapis_A.txt`): lapis A **`test_bp_CRT4_putaran_pertama.py` 2 lulus** — putaran
  pertama job denda di data acuan: jadwal hidup per asal `manual` 3 (draf 1) → sesudah job **+0 nota draf** (RISIKO putaran
  pertama tidak terjadi di data acuan); aturan `cust_toko_kain` @ `ent_ksc` = bawaan registry (draf, 2 %/bulan, sisa
  tagihan, tanpa batas, tenggang 0, minimum Rp 10.000) dengan asal `global`; 0 baris lapisan pelanggan lama untuk lima kunci
  denda (skrip H3 tidak punya pekerjaan di data acuan). `test_bp_KFT5_aturan_khusus.py` 4 lulus. POC `test_g0_config_poc.py`
  (tidak termasuk gate `--ci`): **111 lulus / 4 gagal** — keempatnya bukan bagian yang diubah CR-T4 (pesan kunci khusus-global
  `saga.stuck_lock_minutes`, pemeringkatan "Grade B", dua pemeriksaan penerimaan barang yang kini dijawab 409 `GRN_MODE`);
  pemeriksaan denda yang disesuaikan CR-T4 (tulisan lapisan pelanggan bunga denda → 400; kunci berlapis pelanggan pengganti
  → 200 dan menang atas PT) lulus.
- Uji jalan **U17** (integrator, 1280/1024 px): Pelanggan › kartu pelanggan › tab Kredit › **Aturan denda** — tujuh unsur
  (perlakuan, tarif, dasar hitung, batas atas, tenggang, minimum) masing-masing dengan lencana asal "Ikut PT", kalimat "Diubah
  lewat pengajuan perubahan kredit…", tombol Ajukan perubahan; `overflowX` 0 (`bukti/CR-T4/cek_kredit_*.png`). Tidak ada
  cacat. Form rencana bayar dan panel denda dicakup jest (5 uji), tidak dipotret.
- Temuan di luar lingkup diteruskan sebagai usulan tugas terpisah: `POST /api/ar/aging/{id}/accrue-penalties` masih menerima
  `?today=` dari klien.

Pelaksana (catatan asli):

Belum dijalankan (`gate.sh --quick` / penuh dijalankan integrator di lingkungan A).

## Angka uji

| Rangkaian | Sebelum | Sesudah |
|---|---|---|
| `tests_mem` W | B `53b419b` **2045 lulus / 2 dilewati / 2 xfail** (`bukti/CR-T4/tests_mem_B.txt`) | **2063 lulus / 2 dilewati / 2 xfail** (= 2045 + 18; `tests_mem_W.txt`) |
| `tests_mem` T (`b7837de`, akhir) | HEAD = T − 18 (diturunkan) | **2126 lulus / 2 dilewati / 2 xfail** (HEAD 2108/2/2 diturunkan; `T_tests_mem.txt`) |
| `tests_mem` T (`c3fa3f8`, gabung pertama) | HEAD 2101/2/2 (diturunkan) | **2119 lulus / 2 dilewati / 2 xfail** |
| jest W | B **995** (diturunkan: W − 5; 35 suite gagal dimuat `cmdk`/`@radix-ui` = lingkungan) | **1000 lulus** (35 suite gagal dimuat sama; `jest_W.txt`) |
| jest T | `c3fa3f8`: 1018 (diturunkan) · `b7837de`: 1029 (diturunkan) | `c3fa3f8` **1023** · akhir `b7837de` **1034** (35 suite gagal dimuat sama; `T_jest.txt`) |

Penjaga statik (`hitung_penjaga.sh`, B → W, HEAD → T): auth 26 → 26 · ui_standard 13 → 13 (T: HEAD 11 → 11, MN-T2
menurunkannya) · i18n 103 → 103 · create_modal 6 → 6 · page_tabs 1 → 1 · to_list 5 → 5 · entity_label 2 → 2 · lainnya
PASS/0 — **sama persis** (`penjaga_B.txt`/`penjaga_W.txt`, `H_penjaga.txt`/`T_penjaga.txt`). Lainnya (W; T sama):
`verify_role_gate_ui` 31/0; `verify_config_fallback` 159/0 (+`--entity` 159/0; `--self-test` PASS; **7 pengecualian basi
dicabut** — 133 → 126 di W, 131 → 124 di T); `verify_payment_vocab` 1829/0 (B 1827; T 1835, HEAD 1833 — cek bertambah
dari berkas baru, 0 pelanggaran); `verify_access_catalog_nav` 0; `verify_posting_coverage` 138/0 (+uji-diri hijau);
`verify_atomic_claim` 161/0 (+`--self-test` 64 hijau; inventaris multi-koleksi tetap 124 baris — selisih satu-satunya
nomor baris `users.py` yang sudah ada di basis, tidak ditulis); `verify_cash_single_door` 736/0 (T 740 = HEAD);
`verify_permission_checked` 613/0 (T 615 = HEAD); `verify_detail_modal` 30/0 (T 29 = HEAD); `verify_config_text` 3332/0
(T 3402 = HEAD; +`--self-test` hijau); `verify_codebase_map` PASS; `audit_config_wiring --strict` hijau (W & T; OK 438,
ORPHAN_UI/HIDDEN/DEAD 0); `check_nav_map` PASS (W & T). `access_modules.py` tidak berubah (fixture akses tidak perlu);
jumlah kunci registry tidak berubah (KF-T1 `*_KUNCI`, PRT9, indeks wajib PK-14 tidak disentuh).

## Cek layar (dari kode; foto 1280/1024/390 oleh integrator)

| Layar | Daftar periksa |
|---|---|
| Kartu pelanggan › Kredit › bagian baru **"Aturan denda"** (`CustomerPenaltyRule`) | (1) bukan tabel: 6 baris `dl` (label kiri `min-w-[180px] flex-1`, nilai + lencana kanan, `flex-wrap`) — tidak bisa lebih lebar dari kartu; tanpa tombol; (2) di dalam tab kartu (bantalan tab), judul `h4` sendiri; (3) kepala bagian = judul saja; lencana bebas denda di bilah sendiri di bawah judul; (4) tidak ada tombol mati; (5) asal tiap nilai = `status-pill` ikon + teks + warna ("ikut PT" `bg-kn-neutral-soft` + `Building2`, "khusus pelanggan" `bg-kn-action-soft` + `UserCog`); bebas denda = `status-pill status-done` + `BadgeCheck` + "Bebas denda s.d. {tanggal}" + alasan; bebas lewat = kalimat peringatan berikon; (6) 6 baris tetap — tanpa daftar panjang; (7) tanpa izin melihat denda: "Aturan denda tampil bagi pemegang akses melihat denda." (tidak memanggil server); cara mengubah ditulis netral "Diubah lewat pengajuan perubahan kredit di tab ini." (tidak menjanjikan tombol pada yang tak berizin); (8) batas atas 0 → "Tanpa batas" (bukan "0 %"), mode mati → "Tidak ada denda"; memuat / galat (`ErrorNotice` + "Coba lagi") dibedakan; kode `installment`/`pelanggan`/`ent_*` tidak tampil (uji jest) |
| Pop-up **"Ajukan perubahan kredit"** (`FormModal` md) — bagian baru 4 "Aturan denda" | (1) grid `sm:grid-cols-2`, satu kolom di HP; tanpa tabel; (2) `FormSection` baku bernomor (Dasar pengajuan kini 5); (3) subjudul satu kalimat; (4) tombol kirim tidak dimatikan — kekurangan ditulis "Lengkapi: alasan bebas denda, tanggal berakhir bebas denda / tarif denda" di kaki pop-up; (5)–(6) —; (7) —; (8) "Kosong = ikut aturan PT." di bawah isian; tanggal pakai `KNDatePicker` (min hari ini WIB), angka `DecimalInput` (koma desimal) bersatuan "%"/"hari"; label isian `field-label` |
| Form rencana bayar (`PaymentPlanBuilder`, pop-up/panel pesanan) — bagian lipat **"Aturan denda khusus rencana ini"** | (1) tabel baris jadwal tidak berubah (7 kolom lama); bagian baru di bawah tabel, grid 2 kolom/1 kolom HP; (2) `details` berbatas `border-kn-divider`, isi `px-3 py-2`; (3) ringkasan satu baris + "(terisi)"; terbuka sejak awal hanya bila rencana sudah beraturan denda; (4) simpan tidak dimatikan karena aturan denda — isian salah diberi garis merah + kalimat galat "Periksa tarif denda … pada aturan denda khusus rencana ini." (bilah galat yang sama dengan form); (5)–(7) —; (8) "Kosong = mengikuti aturan pelanggan atau PT." |
| Panel denda (`PenaltyPanel`: Rencana Pembayaran › Denda, rincian piutang, panel bayar pesanan) | baris nota tidak berubah lebarnya (kartu `flex-wrap`); tambahan satu baris "Aturan dari: PT · pelanggan · rencana" `text-fs-12 text-kn-text-2`; (3) judul kelompok pelanggan = nama + "N nota · Rp …" (`flex-wrap`), hanya bila nota > 1 pelanggan; (6) antrean denda sudah punya kotak cari + saringan status (`PaymentPlansView`); tidak ada kelas/hex baru (ratchet `verify_ui_standard` tetap 13) |
| Keuangan › Piutang (`ARAgingView`) catatan kaki | hanya kalimat: "Taksiran dihitung dengan aturan yang sama dengan nota denda (harian, dasar …, tenggang …); pelanggan dengan aturan denda khusus atau rencana bayar beraturan denda sendiri memakai aturannya." (dulu "bisa berbeda dari estimasi kasar" — kini salah) |

Belum diuji jalan di peramban (U17).

## Menyimpang dari blueprint

1. **Endpoint di `routers/payment_plans.py`** (router denda), bukan router profil kredit — `credit_profiles.py`/`crm.py`
   sedang disentuh CR-T3 (gerbang kredit); jalur, izin, dan jawaban sesuai spesifikasi (+ `customer`, `entity_id`,
   `expired_waiver`, `customer_rule_mode`, `rule` untuk layar).
2. **`accrue_order` → `accrue_for_order(order_id)`**: pemanggil kedua (`finance_case_actions`, giro ditolak + nota denda)
   tidak disebut spesifikasi; dialihkan ke jadwal hidup pesanan sebelum jalur lama dihapus (§7.3).
3. **Pemeriksaan `plan.penalty`** (`payment_plan_service.penalty_override`) — spesifikasi hanya meminta isian layar; tanpa
   pemeriksaan, tarif 120 % tersimpan dan dibaca mesin. Kalimat galat tarif sama dengan pengajuan.
4. **`penalty_rule` `ikut_pt` disimpan `null`** (= tanpa aturan khusus; satu bentuk untuk "ikut PT").
5. **Taksiran memakai aturan rencana berdenda** (`_rencana_berdenda`) — syarat "taksiran = nota" untuk pesanan bercicilan
   yang punya `plan.penalty`; tanpa itu U6 akan memberi taksiran 50.000 untuk nota 25.000.
6. **Pesanan bertermin tunai** (`report_basis.pesanan_piutang` salah) tidak melahirkan nota dari jadwal mesinnya —
   perilaku hari ini (`accrue_order` melewati `NON_AR_METHODS`), dan umur piutang juga melewatinya.
7. **"Hari ini" job/akrual = tanggal buku WIB** (`tanggal_buku`, D6; dulu tanggal UTC `now_iso()`); job menerima `today`
   opsional dan melaporkan `by_origin`.
8. **Skrip migrasi — mode per pelanggan**: spesifikasi hanya menyebut nilai; `off` butuh tanggal berakhir (tidak ada bebas
   selamanya) → opsi `--bebas-sampai` dari pemilik, tanpa itu "menunggu" (tidak disentuh); `draft`/`auto` per pelanggan
   tidak punya padanan di profil → dilepas + dilaporkan.
9. **"Dasar hitung" punya pilihan ketiga "Ikut aturan di atasnya"** (nilai kosong) — supaya kosong = ikut PT/pelanggan
   berlaku juga untuk dasar.
10. **Kelompok per pelanggan di panel denda hanya bila nota berasal dari > 1 pelanggan** (rincian satu pelanggan/pesanan
    tanpa judul kelompok berulang).
11. **U11 memakai nota sisip setara U1** (bukan nota hasil U1) supaya uji regresi PK-08 ini hijau juga di kode lama
    ("merah kecuali U11").

## Asumsi

- `ASUMSI:` (spesifikasi) lapisan pelanggan = profil kredit per (pelanggan, PT); PT nota = PT jadwal = PT pesanan; PT
  kosong → PT pemilik data pelanggan.
- `ASUMSI:` (spesifikasi) bebas denda wajib bertanggal; `bebas` tersimpan tanpa alasan/tanggal (diizinkan validasi CR-T1)
  dibaca **ikut PT**.
- `ASUMSI:` (spesifikasi) mode bawaan tetap `draft` (K-30); tidak ada persen/nominal/akun baru (H4).
- `ASUMSI:` (`00` §4.1) `bebas` berlaku sampai dan termasuk `valid_until` (U5: 30 Okt → 31 Okt sudah ikut PT).
- `ASUMSI:` `khusus` tidak mengubah perlakuan usulan/terbit — itu per PT (`payment.penalty_mode`); hanya `bebas` yang
  mematikan; rencana bayar tetap boleh menimpa perlakuan (`plan.penalty.mode`).
- `ASUMSI:` minimum nota (`payment.penalty_min_amount`) ikut menentukan taksiran (taksiran = nota; U10).

## Yang perlu direview / titik henti

- **H3**: `scripts/migrate_penalty_customer_layer.py --apply` pada data nyata = keputusan pemilik (juga `--dry-run`).
  Sebelum skrip dijalankan, nilai lapisan pelanggan lama TIDAK lagi dibaca mesin (scopes berubah) → pelanggan itu kembali
  ikut PT. Jumlah baris di data acuan dicetak lapis A (`test_bp_CRT4_putaran_pertama.py`).
- **H4**: tidak ada tarif/tenggang/batas/akun baru; `--bebas-sampai` untuk bebas denda lama diisi pemilik.
- **RISIKO putaran pertama** (spesifikasi): jumlah nota draf baru di data acuan **belum diukur** (lingkungan A — lapis A
  ditulis). Nota draf tidak berjurnal; pembatalan: batasi job ke `origin: manual` (satu baris `find` di
  `job_penalty_accrual`/`accrue_customer`).
- **Pesanan tanpa jadwal tersimpan** (data lama sebelum `build_billing_schedule.py --apply`, CR-T2 H3) tidak lagi
  melahirkan nota (jalur `accrue_order` dihapus); integrator CR-T2: data acuan sudah berjadwal penuh.
- **Rencana cicilan pengganti jadwal**: nota draf jadwal `term` yang di-void tetap ada (tidak disentuh mesin), dan hari
  yang sudah dimuat nota jadwal lama tidak dihitung `days_prior` rencana baru (perilaku lama `accrue_order` → rencana sama).
  Bila keduanya diterbitkan, hari telat bisa tertagih dua kali — usul: antrean nota draf CR-T5 menandai nota draf berjadwal
  void.
- **Ditemukan, di luar lingkup**: `POST /api/ar/aging/{id}/accrue-penalties` masih menerima `?today=` dari klien (PK-08
  hanya mencabutnya dari `/payment-plans/{id}/accrue`) — tanggal masa depan melahirkan nota ribuan hari telat (mode `auto`
  = berjurnal). Tidak diubah (bukan bagian spesifikasi); usul unit kecil sejenis PK-08 U9.
- `penalty_service.waive/adjust` masih memeriksa peran penyetuju dengan `role_in` (warisan, tidak disentuh — Z2 untuk kode
  baru).
- Lapis A belum dijalankan: `test_bp_CRT4_putaran_pertama.py`, `test_bp_KFT5_aturan_khusus.py` (diubah), POC
  `test_g0_config_poc.py` (diubah, dijalankan gate).
- Belum diuji jalan di peramban (U17).

## Penggabungan

- Gabung pertama ke HEAD **`c3fa3f8`** (KM-T2, PY-T3): 27 berkas; kode (`backend/**`, `frontend/**`) sama di B dan HEAD →
  disalin; `git merge-file` untuk dokumen. `tests_mem` T **2119/2/2**, jest **1023**, penjaga = HEAD. Sebelum melapor HEAD
  bergerak ke **`b7837de`** (MN-T2 (a/b): kas kecil, titipan & saldo kredit, tutup buku — `frontend/**`, `cash_advance_*`,
  `closing_*`, uji MN-T2) → T dipindah dan digabung ulang dari basis `53b419b`:

| Berkas | Bentrok | Keputusan |
|---|---|---|
| `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | tekstual (bagian baru di ujung: §9.23 KM-T2, §9.24 PY-T3, §9.25 MN-T2 vs §9.23 CR-T4) | keempat bagian; CR-T4 = **§9.26** |
| `CODEBASE_MAP.md` | tekstual | dibangkitkan ulang (`gen_codebase_map.py`) dari HEAD |
| `ENTITY_REGISTRY.md`, `memory/PRD.md` (CR-T4 + KM-T2/PY-T3/MN-T2), `scripts/INDEX.md`, `scripts/guardrails/config_fallback_allow.json` (PY-T3 mencabut 2 butir lain; CR-T4 mencabut 7) | bersih | tiga arah, kedua perilaku ada (diperiksa: JSON sah, 124 butir) |
| `configKeyIndex.json` | — | dibangkitkan ulang — tanpa selisih |

- Berkas kode yang juga diubah unit lain sejak B: **tidak ada** (CR-T3 belum masuk HEAD; `credit_profile_service.py`,
  `CustomerCreditTab.jsx`, `CreditProfileRequestModal.jsx` kemungkinan disentuh CR-T3 — perubahan CR-T4 di sana kecil:
  `_aturan_denda`, satu komponen terpasang, satu `FormSection`).
- Sesudahnya HEAD bergerak ke **`c8c6d03`** (laporan, bukti, `STATUS.md` MN-T2 saja): `git diff b7837de c8c6d03 -- backend
  frontend scripts seed_realistic.py CODEBASE_MAP.md ENTITY_REGISTRY.md memory docs/KN_32…` kosong → T dipindah tanpa gabung
  ulang; angka `b7837de` berlaku.
- Angka T akhir di "Angka uji". Draf laporan + bukti hanya di W.

Status: implemented_pending_review.
