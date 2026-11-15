# PM-T4 — Tunai yang diterima sales dicatat sebagai titipan sampai disetor

- Commit awal: `5f193df` (worktree kerja, basis B)        - Commit akhir: `38c715f`
- Branch: (integrator)        - Digabung pelaksana ke HEAD tujuan — lihat "Penggabungan"
- ID ditangani: PM-06 (spesifikasi `docs/blueprint/unit/PM-T4.md`)
- Keputusan: K-36 · Standar `02` §1 (P1–P5, P9, P10), §2 (2.1, 2.2, 2.4), §3.1 (Z1–Z3), §3.2, §3.4 (N1, N2, N4, N5),
  §4 (L1, L3, L4), §5 (D2, D7, D9), §6 · Prasyarat PM-T3 (di basis), PK-18, PK-19, PK-20
- Risiko sedang → satu serah-terima. **Titik henti H5**: unit selesai dengan bawaan `kas_langsung` (= perilaku hari ini);
  tidak ada pengaturan PT nyata yang diubah di kode/seed. Pertanyaan pemilik di bagian akhir.

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`, dicek di `5f193df`)

| Butir | Hasil di basis B |
|---|---|
| Izin Sales mencatat kwitansi diberikan saat server menyala, daftar bawaan hanya `view` (`bootstrap.py:460`, `permissions_config.py:142`) | **Bergeser** (PR-T9): blok GRANT kini migrasi sekali-jalan `bootstrap._legacy_grants` (`:494` `"sales": {"ar_receipt": ["create"]}`); `DEFAULT_PERMISSIONS["sales"]["ar_receipt"]` = `["view", "create"]` (`permissions_config.py:144`). Perilaku sama (K-36) |
| HP sales memakai form kwitansi desktop (`MobileArReceipt.jsx:14`) | Berlaku (`:15`) |
| Kwitansi tunai langsung jadi kas kecil PT (`ar_receipt_service.py:66` `CASH_METHODS`, `:71` `_post_cash_in`) | Berlaku, **bergeser**: `CASH_METHODS`/`_cash_routing` dihapus PM-T3; kas lewat `_post_cash_in` `:208` → `cash_ledger.create_cash` ke rekening penerima (jenis kas = jenis rekening, tunai → rekening kas) |
| Form memberi tahu "tunai → kas kecil" (`ARReceiptModal.jsx:190` `cashHint`) | Berlaku, bergeser `:257` |
| Akun "Piutang Titipan Karyawan" ada & terpetakan (`gl_service.py:161`, `gl_mapping_registry.py:48`) | Berlaku; registri bergeser `:67` |
| Pasangan jurnal Kasus Keuangan (`finance_case_actions.py:327`, `:360`) | Berlaku, bergeser: akui dipegang karyawan `:389` (Dr 1-1280 / Cr 1-1200), setor `:878` (`contra=gl.ACC_PIUTANG_KARYAWAN`) |
| Hub Kas & Bank punya tiga tab (`hubTabs.js:159`) | **Berubah**: empat tab sejak MN-T1 (+ Kas Kecil), `:164`. Tab baru → lima (≤ 6, L3) |
| Jenis dokumen jurnal-gagal di satu tempat (`posting_failures.py:17` `SOURCES`) | Bergeser (PK-18): `SOURCES` dibentuk dari `services/posting_registry.py::KINDS` (`posting_failures.py:25`) — jenis baru didaftarkan di registri |

## PM-06 — Tunai yang diterima sales tercatat sebagai kas kantor

- Berlaku di HEAD: ya (bukti merah `bukti/PM-T4/merah_kode_lama.txt`: kunci tidak ada, kwitansi tunai sales membuat kas,
  endpoint setoran 404, sumber daya izin `cash_holding` tidak dikenal; U2 dan U3 lulus di kode lama = perilaku yang
  dipertahankan).
- Akar masalah: `create_receipt` selalu memposting kas untuk uang baru, siapa pun pencatatnya; tidak ada dokumen untuk uang
  yang masih dipegang orang lapangan.
- Perubahan perilaku (sebelum → sesudah):
  - **Pengaturan** (kelompok "Pembayaran pelanggan" — id lama `uang-masuk` — › Kwitansi pelanggan; izin `cash.configure`;
    `("global", "entity")`): `pembayaran.sales_terima_tunai` (`kas_langsung` bawaan · `titipan` · `dilarang`; `high`, wajib
    alasan), `pembayaran.titipan_batas_nominal` (Rp 0–1.000.000.000, 0 = tanpa batas), `pembayaran.titipan_tenggat_setor_hari`
    (0–30 hari, 0 = tanpa tenggat). Teks persis spesifikasi.
  - **PERIKSA kwitansi** (`create_receipt`, sesudah cara bayar & periode, SEBELUM rekening/nomor/deposit/alokasi):
    `cash_holding_service.mode_tunai` — cara bayar `needs_account: kas` + uang baru + pencatat TANPA `cash.create` →
    pengaturan PT kwitansi; `dilarang` → 403 pesan persis; `titipan` → `periksa_batas` (409 pesan persis bila
    dipegang + nominal > batas). Pemegang `cash.create` selalu kas langsung.
  - **Kwitansi titipan**: alokasi lewat `allocate(kind="kas")` seperti biasa (piutang turun); **tanpa** transaksi kas dan
    tanpa rekening; `ar_receipts.cash_holding_id`; `cash_holdings` (id tetap `cth_` + id kwitansi, nomor `TTP-` per PT,
    pemegang = pencatat, `due_at` dari tenggat). Jurnal `gl_service.post_cash_holding` lewat `post_durable`
    (sumber `cash_holding` + id titipan): Dr `kas_bank.piutang_karyawan` (1-1280, dipetakan saat sisip) / Cr sisi kredit
    yang **sama** dengan jurnal kas kwitansi — logika kredit `_post_cash_transaction` dipindah utuh ke
    `gl_service._receipt_lines` dan dipakai kedua jurnal (piutang untuk bagian berpendapatan, uang muka pelanggan untuk
    sisanya, pemakaian deposit Dr 2-1400). Status jurnal dicerminkan ke `gl_status` kwitansi.
  - **Setoran** (`cash_deposits`, `cdp_…`, nomor `STT-` per PT): `POST /api/cash-deposits` (`cash_holding.create`, PT dari
    konteks — N1) → `diajukan`; tanpa `holding_ids` dialokasikan ke titipan tertua; yang bisa disetor = titipan terbuka
    milik penyetor − yang sudah diajukan di setoran lain → selebihnya 400 pesan persis. **Terima**
    (`cash_holding.approve`): PERIKSA (status `diajukan` → 409 pesan persis; penerima = pemegang → 403 pesan persis;
    rekening wajib, milik PT & aktif — `cash_ledger.periksa_rekening`; periode terbuka — `preflight_posting`; tiap titipan
    masih terbuka & cukup) → NIAT (klaim `atomic_claim` berprasyarat `diajukan` + `receive_intent` berid kas tetap) → EFEK
    (`deposited_amount` naik dengan syarat `≤ amount − alokasi` dan penanda `deposit_ids` → ulang tidak ganda; status
    `disetor`/`sebagian_disetor`) → JURNAL (`create_cash(ref_type="cash_deposit", contra_account_code=1-1280)`;
    galat jurnal → kas tersimpan `failed`, setoran `gl_status: failed`, tetap diteruskan) → SELESAI `diterima`. **Tolak**
    (`approve`) / **batal** (penyetor sendiri, `create`): alasan ≥ 3 huruf, hanya `diajukan` tanpa niat terima berjalan;
    titipan tidak berubah.
  - **Batal kwitansi titipan**: PERIKSA — titipan sudah (sebagian) disetor → 409 pesan persis; sedang diajukan dalam
    setoran → 409 "Titipan kwitansi ini sedang diajukan dalam setoran {nomor}. …"; EFEK 0 (sebelum efek lain) titipan
    `batal` bersyarat belum disetor; JURNAL pembalik `gl_service.reverse_cash_holding` (sumber `cash_holding_reversal`,
    satu jalur pembalik PK-10) di resep `posting_registry.post_receipt_void` (`void_gl_status`). Kwitansi gagal lahir:
    titipan batal + pembalik tahan-gagal.
  - **Daftar**: `GET /api/cash-holdings?status=&holder_user_id=&overdue=` (berhalaman, per PT, `holders` = ringkasan per
    orang atas semua baris cocok; tanpa `approve` hanya milik sendiri), `GET /api/cash-holdings/me/summary` (login, milik
    sendiri — `LOGIN_ONLY`), `GET /api/cash-deposits?status=` (bawaan `diajukan`).
  - **Posting Gagal**: jenis `cash_holding` ("Titipan Tunai Sales") dan `cash_deposit` ("Setoran Titipan Tunai") di
    `posting_registry.KINDS` dengan jalur ulang; ulang baris kas `ref_type: cash_deposit` ikut menandai setorannya.
  - **INV-TTP-01** (`verify_data_integrity.py` lapisan `titipan`, rumus `cash_holding_service.rekonsiliasi`): per PT Σ
    (amount − deposited_amount) titipan tidak batal = Σ debit 1-1280 jurnal `cash_holding` − Σ kreditnya di
    `cash_holding_reversal` − Σ kredit 1-1280 jurnal kas `cash_deposit`. Pembangun ulang `hitung_ulang_disetor` (D2).
  - **Izin** (empat tempat, `02` §3.2): `cash_holding.view` (Admin, Manajer, Finance, Sales, Admin Sales), `.create`
    (Admin, Manajer, Sales), `.approve` (Admin, Manajer, Finance) — `permissions_config.PMT4_DEFAULT_PAIRS`; modul akses
    `finance_ops` + id menu `cash-holdings`; endpoint `require_permission` (Z1); tombol `canCurrent(...)`.
  - **Lain**: `IDEMPOTENT_PREFIXES` + `/api/cash-deposits`; `entity_scope` + kedua koleksi; `verify_contract`;
    indeks wajib `cash_holdings.uq_holding_receipt` (+ indeks biasa); `doc_number_kinds` (`ttp`, `stt`);
    `cash_ledger.REF_LABEL["cash_deposit"]`; label sumber jurnal (`JOURNAL_SOURCE_LABEL` +2, frontend tidak berubah —
    `sourceLabel` merapikan); `bootstrap.backfill_ar_cash_postings` MELEWATI kwitansi titipan (dulu akan membuatkan kas
    saat server menyala); `incentive_facts.reconcile_collections` (INV-KM-2) menghitung titipan sebagai uang masuk
    kwitansi titipan.
- Status: implemented_pending_review

## Uji penerimaan

Berkas: `backend/tests_mem/test_PMT4_titipan_sales.py` (17 uji). Rekening, pengaturan, kwitansi, setoran, terima/tolak/
batal, pembatalan kwitansi, ulang posting = ALUR lewat API; pelanggan, pesanan terkirim + jurnal pendapatannya
(`post_sales_order`), akun sales/finance = FIXTURE.

| ID | Lapis | Kode lama (B) | Kode baru |
|---|---|---|---|
| U1 | B | merah: kas baru tercipta (6 ≠ 5) | lulus — 200; tanpa kas; satu titipan Rp 300.000 `dipegang` (pemegang = sales); jurnal Dr 1-1280 300.000 / Cr 1-1200 300.000; sisa 700.000 |
| U2 | B | lulus (perilaku dipertahankan) | lulus — `ent_ksc` (bawaan): kas 300.000 ke rekening kas PT, tanpa titipan |
| U3 | B | lulus (perilaku dipertahankan) | lulus — Finance (`cash.create`): kas ke K, tanpa titipan |
| U4 | B | merah: 404 | lulus — `diajukan` → `diterima`; kas 300.000 `account_id` K; jurnal Dr 1-1110 / Cr 1-1280 300.000; titipan `disetor`; saldo 1-1280 modul ini 0 |
| U5 | B | merah: 404 | lulus — 300.000 `disetor` · 50.000 `sebagian_disetor`; `me/summary.held_total` 150.000 |
| U6 | B | merah: 404 | lulus — 400 "Setoran melebihi tunai yang Anda pegang (Rp 300.000)."; tanpa setoran |
| U7 | B | merah: sumber daya izin tidak dikenal | lulus — peran kustom tanpa `cash.create` → titipan; terima sendiri 403 pesan persis; tetap `diajukan`, tanpa kas |
| U8 | B | merah: kunci tidak ada | lulus — batas 400.000: 409 "Titipan tunai Anda Rp 300.000 sudah mencapai batas Rp 400.000. …"; tanpa kwitansi |
| U9 | B | merah: kunci tidak ada | lulus — tenggat 1 hari: titipan 2 hari lalu ada di `?overdue=true`, titipan hari ini tidak |
| U10 | B | merah: kunci tidak ada | lulus — `dilarang`: tunai 403 pesan persis; transfer 200 (rekening B); pemegang kas tetap boleh tunai |
| U11 | B | merah: `cash_holding_id` tidak ada | lulus — titipan `batal`, pembalik Dr 1-1200 / Cr 1-1280 300.000, `void_gl_status: posted`, sisa 1.000.000; kwitansi U1 (disetor U4) 409 pesan persis, tanpa niat |
| U12 | B | merah | lulus — periode tertutup 409, tanpa niat/efek/kas; jurnal kas dipaksa gagal → 200 `diterima` + `gl_status: failed`, tampil di panel; ulang panel → 1 kas, 1 jurnal, `deposited_amount` 300.000; terima lagi 409 pesan persis |
| U13 | B | merah: lapisan tidak ada | lulus — INV-TTP-01 PASS; `deposited_amount` +10.000 langsung di DB → FAIL menyebut `ent_kanda` |
| U14 | B | merah | lulus — Tanpa Acuan + `cash_holding.approve` 200; Manajer Kosong 403; Sopir 403; sales hanya titipannya sendiri (saringan pemegang lain → 0); tolak/batal (+ batal oleh bukan penyetor 403, putus ulang 409) |
| U15 | B | merah: kunci tidak ada | lulus — putaran KF-T8 tiga kunci tanpa temuan |
| U16 | A | — | **ditulis, belum dijalankan** — `backend/tests/test_bp_PMT4_terima_bersamaan.py` (dua `receive` bersamaan → satu 200 + satu 409, satu kas, satu jurnal, `deposited_amount` 100.000) |
| U17 | layar | merah: komponen tidak ada (`bukti/PM-T4/jest_merah_src_lama.txt`) | uji komponen jest `pmt4TitipanSales.test.js` 7/7; **belum diuji jalan** di peramban |
| tambahan | B | merah | jurnal titipan dipaksa gagal → kwitansi & titipan `failed` → ulang panel `cash_holding` → keduanya `posted`, satu jurnal; `backfill_ar_cash_postings` tidak membuat kas untuk kwitansi titipan |
| contoh angka | B | merah | lulus — U1 → U4 di bawah |

### Contoh angka U1 → U4 — dokumen → jurnal → saldo

Tagihan P (`ent_kanda`, non-PKP): pesanan terkirim Rp 1.000.000, jurnal pendapatan Dr 1-1200 1.000.000 / Cr 4-1000 1.000.000.

1. **U1** sales (tanpa `cash.create`), PT `titipan`: kwitansi tunai Rp 300.000 untuk pesanan itu → baris pembayaran kas
   300.000 (sisa tagihan 1.000.000 − 300.000 = **700.000**); TIDAK ada kas; titipan `KANDA/TTP-00001` Rp 300.000
   `dipegang`. Jurnal titipan (`cash_holding`):

   | Akun | Debit | Kredit |
   |---|---:|---:|
   | 1-1280 Piutang titipan karyawan | 300.000 | |
   | 1-1200 Piutang usaha (pesanan sudah berpendapatan → piutang, sisi kredit kwitansi biasa) | | 300.000 |

2. **U4** sales mengajukan setoran Rp 300.000 (`STT-`, dialokasikan ke titipan itu); Finance menerima ke Kas Kecil K →
   kas masuk Rp 300.000 `ref_type: cash_deposit`, `account_id` K. Jurnal kas:

   | Akun | Debit | Kredit |
   |---|---:|---:|
   | 1-1110 Kas kecil (akun kas rekening K) | 300.000 | |
   | 1-1280 Piutang titipan karyawan (lawan akun kas) | | 300.000 |

3. Saldo: piutang usaha pesanan = 1.000.000 − 300.000 = **700.000**; piutang titipan karyawan dari modul ini = 300.000 −
   300.000 = **0** (titipan `disetor`, `deposited_amount` 300.000); kas K bertambah **300.000** baru saat setoran diterima
   (bukan saat kwitansi). INV-TTP-01: titipan terbuka 0 = jurnal 300.000 − 0 − 300.000.

`backend/tests_mem`: B **1924 lulus / 2 dilewati / 2 xfail** (`bukti/PM-T4/tests_mem_B.txt`) → W **1944 / 2 / 2** (+17 uji
PM-T4, +3 putaran KF-T8 untuk tiga kunci baru). Putaran penuh pertama di W: 1942 lulus + 2 merah `test_KPT5b_pengaturan`
(jumlah jenis nomor 68 → 70; `bukti/PM-T4/tests_mem_W_sebelum_KPT5b.txt`) → hitungan disesuaikan (tabel di bawah), berkas
itu 16/16.

## Uji lama yang disesuaikan (perilaku/hitungan sengaja berubah)

| Uji | Sebab | Penyesuaian |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` U04 | tiga kunci baru berizin `cash.configure` | `+ PMT4_KUNCI` (= 3) |
| `tests_mem/test_KFT4_registry.py` | tiga kunci baru di "Pembayaran pelanggan" | `+ PMT4_PEMBAYARAN_PELANGGAN` (= 3); `configKeyIndex.json` dibangkitkan ulang |
| `tests_mem/test_PRT9_izin_bawaan.py` | izin bawaan baru `cash_holding.*` | blok `PMT4_DEFAULT_PAIRS` (pola PR-T9) |
| `tests_mem/test_PRT3_login_saja.py` U13 | `GET /api/cash-holdings/me/summary` login saja (milik sendiri) | 53 + 1 + 1 **+ 1** |
| `tests_mem/test_PK14_indeks_wajib.py`, `tests/test_bp_PK14_indeks_wajib.py` | indeks wajib baru `cash_holdings.uq_holding_receipt` | `+ PMT4_INDEKS` (= 1); lapis A 29 → **30** |
| `tests_mem/test_KPT5a_setara.py` | dua deret nomor baru `TTP-`, `STT-` | `AWALAN_SESUDAH_KPT5` + dua |
| `tests_mem/test_KPT5b_pengaturan.py` U14 & daftar lengkap | dua jenis nomor baru di Penomoran Dokumen | 66 + 1 + 1 **+ 2** |
| jest `config/__tests__/mnt1MenuKeuangan.test.js` | tab baru Kas & Bank › Titipan Sales (Admin, Manajer, Finance) | `cash-bank` 4 → 5 tab, label + "Titipan Sales", menu Finance + `cash-holdings`; tabel bantu `fixtures/view_main_permission.json` + `cash-holdings` (`cash_holding.view`, `/api/cash-holdings`; `tests_mem/test_MNT1_menu_keuangan.py` 6/6) |
| jest `config/__tests__/roleReach.test.js` | layar baru yang SAH untuk admin, manajer, Finance | `PMT4_TITIPAN = ["cash-holdings"]` di `ROLE_REACH_ADDITIONS` |
| fixture akses jest (`access_nav_fixture.json`, `access_builtin_fixture.json`) | `access_modules.py` berubah | dibangkitkan `tests/fe03_access_fixture.py`; `test_fe03_access_catalog.py` 6/6 |

## Menyimpang dari blueprint

1. **Nomor setoran `STT-`, bukan `STR-`**: `STR-` sudah dipakai setoran kewajiban gaji (PK-22, `hr_statutory_remittances`) dan
   deret per PT berkunci awalan yang sama (`number_sequences.doc_type = "STR"`) — dua jenis dokumen akan berbagi deret dan
   bernomor serupa. Titipan tetap `TTP-`.
2. **Mode tunai diputus SEBELUM pemeriksaan rekening PM-T3** (spesifikasi: "setelah langkah PERIKSA PM-T3") dan kwitansi
   titipan **tanpa rekening penerima**: uangnya belum di rekening mana pun; PT tanpa rekening kas tidak boleh menghalangi
   titipan, dan PT `dilarang` harus menjawab 403, bukan 409 "Pilih rekening". Cara bayar & periode tetap diperiksa dulu.
   "Tidak sesuai instruksi" untuk titipan = pesanan berinstruksi rekening yang TIDAK menerima tunai di PT itu (tunai untuk
   pesanan berinstruksi kas = sesuai).
3. **Pembaca kunci** (`consumers`) = fungsi yang benar-benar membaca: `cash_holding_service.mode_tunai`, `periksa_batas` +
   `ringkasan_saya`, `tenggat_hari` (spesifikasi menyebut `ar_receipt_service.create_receipt`, yang tidak menyebut kuncinya —
   penjaga `audit_config_wiring` memeriksa badan fungsi). Sub-judul = "Kwitansi pelanggan" (PM-T3).
4. **Endpoint tambahan** `GET /api/cash-deposits` (bahan bagian "Setoran menunggu diterima"; spesifikasi tidak menyebut
   daftar setoran). Jawaban `GET /api/cash-holdings` + `holders` (ringkasan per orang atas semua baris cocok, supaya tabel
   "per orang" tidak dihitung dari satu halaman). `me/summary` + `mode`, `pending_total`, `available`, `overdue_count`,
   `tenggat_hari`, `entity_id` (bahan teks bantu form kwitansi untuk pencatat mana pun dan kartu HP).
5. **Lewat tenggat** dihitung dari `received_at` + tenggat PT yang berlaku SEKARANG (help: "Titipan lebih lama dari ini
   bertanda lewat tenggat"); `due_at` tetap disimpan saat titipan lahir seperti spesifikasi (potret).
6. **409 tambahan** batal kwitansi yang titipannya sedang diajukan dalam setoran (tanpa ini setoran `diajukan` menunjuk
   titipan batal) — pesan "Titipan kwitansi ini sedang diajukan dalam setoran {nomor}. Tolak atau batalkan setorannya dulu."
7. **Galat jurnal kas setoran** → setoran tetap `diterima` (kas tersimpan, `gl_status: failed`) lalu diulang dari panel —
   pintu tahan-gagal `02` §1 langkah 4 (`post_durable` tidak melempar); spesifikasi U12 hanya menuntut `failed` → ulang →
   tunggal.
8. **Alasan tolak/batal wajib ≥ 3 huruf** (N5; spesifikasi menyebut `{reason}` tanpa aturan).
9. **Tab "Titipan Sales" untuk Admin, Manajer, Finance** (pemegang `approve`); Sales melihat titipannya di kartu HP, bukan
   tab desktop (izin `view` tetap memberi akses API milik sendiri). Menu lain modul `finance_ops` yang hanya milik modul itu
   (Rekening, Transaksi Kas, Rekonsiliasi, Kasus, aturan bank, alasan koreksi) tetap dibuka sumber daya lama
   (`VIEW_RESOURCE_OVERRIDES`) supaya pemegang `cash_holding` saja tidak mendapat tab yang langsung menolak.
10. **Lencana "Titipan sales"** di Riwayat Pembayaran (kwitansi ber-`cash_holding_id`) — tidak diminta, mencegah kwitansi
    titipan terbaca "Tunai" (= sudah di kas).
11. **INV-KM-2** (KM-T1) menghitung titipan sebagai uang masuk kwitansi titipan (tanpa ini pencairan ≠ kas untuk tiap
    kwitansi titipan).

### Usulan koreksi berkas unit

- Data, `cash_deposits`: "nomor `STR-` per PT" → "nomor `STT-` per PT (`STR-` dipakai setoran kewajiban gaji PK-22)".
- Pengaturan, baris `consumers`: `services/ar_receipt_service.py:create_receipt` →
  `services/cash_holding_service.py:mode_tunai` · `:periksa_batas` (+ `:ringkasan_saya`) · `:tenggat_hari`.
- Keadaan sekarang: "Hub Kas & Bank punya tiga tab" → "empat tab (MN-T1 menambah Kas Kecil)"; `SOURCES` →
  `services/posting_registry.py::KINDS`.
- Langkah kerja 1: "merah kecuali U2" → "merah kecuali U2 dan U3 (keduanya perilaku hari ini)".

## Asumsi

- `ASUMSI` unit: "sales" = pencatat tunai tanpa `cash.create`; batas & tenggat bawaan 0; penerima ≠ pemegang.
- Bawaan (`00` §4.1): batas titipan diperiksa per PT kwitansi, tanpa kunci atomik (dua kwitansi bersamaan bisa sedikit
  melewati batas — batas adalah kontrol lunak); setoran hanya boleh dari titipan milik penyetor di PT aktif.
- Kwitansi titipan dari kartu tindakan asisten (AG-T3) dan antrean luring HP diputus server pada saat diterima (mode PT
  saat itu), sama dengan form.

## Cek layar

Dari kode (integrator memotret 1280/1024/390 px). Token `kn-*`, `text-fs-*`, tanpa hex/`text-[Npx]` baru
(`verify_ui_standard` identik B).

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati beralasan | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong/0 |
|---|---|---|---|---|---|---|---|---|
| Kas & Bank › **Titipan Sales** (`finance/cashholding/CashHoldingsView`) | "Setoran menunggu" 6 kolom, "per orang" 6 kolom, "rincian" 7 kolom — `data-table head-wrap` dalam `table-wrap`, kolom aksi `col-sticky-end`, tombol `btn-sm whitespace-nowrap` | `section-head` + `section-body` | judul + "Muat ulang" saja; saringan di bilah alat | "Semua PT" → "Pilih satu PT dulu"; tanpa izin → "Menerima setoran butuh akses menerima setoran titipan."; setoran sendiri → "Setoran Anda sendiri — diterima orang lain." (tertulis, bukan tooltip); pop-up Terima: alasan rekening di bawah isian | Diajukan/Diterima/Ditolak/Dibatalkan, Dipegang/Sebagian disetor/Disetor/Batal, Lewat tenggat = `status-pill` ikon + teks + token | kotak cari + centang "Lewat tenggat" + tombol "Pemegang: {nama} ×" | tombol dari `canCurrent("cash_holding","approve")` | satu kalimat per bagian ("Tidak ada setoran yang menunggu diterima.", "Tidak ada titipan tunai.", "… lewat tenggat."); jumlah total + Σ nominal; berhalaman |
| HP **Titipan Saya** (`sales/mobile/MobileCashHoldingCard`, Beranda HP sales, 390 px) | — (kartu `m-card`, `dl` dua kolom) | `p-4` | judul + lencana Lewat tenggat (satu baris, ikon) | "Setor" `btn-touch` lebar penuh; mati → alasan di bawahnya ("Pilih satu PT dulu", "Mengajukan setoran butuh akses setoran titipan.", "Semua titipan sudah diajukan — tunggu kasir menerimanya.", "Tidak ada titipan yang bisa disetor.") | Lewat tenggat = ikon + teks + `bg-kn-danger-soft` | — | — | kartu tidak tampil bila PT kas langsung dan tidak ada titipan (bukan "Rp 0"); "Tanpa batas", "Tanpa tenggat" sebagai kata |
| Pop-up **Setor titipan tunai** (HP) | — | `FormModal` baku (layar penuh di HP) | judul tetap | Simpan → galat di kaki ("Jumlah melebihi …") | — | — | — | jumlah terisi total yang bisa disetor |
| **Form kwitansi** (`crm/ARReceiptModal` + `ReceiptPaymentFields`; HP komponen sama) | — | tetap | tetap | tetap (PM-T3) | mode titipan: kotak bantu ikon dompet + teks + `bg-kn-warning-soft` | — | `dilarang` → pilihan Tunai tidak ditawarkan; titipan → tanpa isian rekening; konfirmasi "masuk ke titipan tunai di tangan Anda (belum masuk kas)" | gagal muat mode → tampilan lama |
| **Riwayat Pembayaran** | kolom tidak bertambah | tetap | tetap | — | lencana baru "Titipan sales" (ikon dompet + teks + token) | tetap | — | — |

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`38c715f`** — satu gate
untuk rantai gelombang 4 (PY-T2, TX-T2 (a/b) + cek layar, AG-T5 (a/b) + cek layar, CR-T2 (a/b), PM-T4):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`b62ef45`: 12 / 39) — tidak ada gate baru yang merah. "Tidak dijalankan" tambahan = ganti label
(`guard:atomic_claim SELF-TEST` 10 → 64 kasus, `guard:page_tabs` + uji-dirinya). Kuitansi: `bukti/PM-T4/gate_quick_receipt.md`,
`gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- Rantai gelombang 4 dipasang integrator berurutan di atas `8ac7059`: PY-T2 `5edef21` · `82ef1bb` → TX-T2 (a) `38b5c9b` · (b) `84744dc` · cek layar `15d3258` → AG-T5 (a) `31a8d54` · (b) `7747302` · cek layar `df23cb2` → CR-T2 (a) `2d9709e` · (b) `76a337d` → PM-T4 `38c715f`. Tiap commit diuji `tests_mem` penuh di worktree bantu sebelum dipetik (angka di bawah). Jest penuh di `38c715f`: **995 lulus** (957 + PY-T2 8 + TX-T2 7 + AG-T5 11 + CR-T2 5 + PM-T4 7; 35 suite gagal dimuat `cmdk`/`@radix-ui`, sama). Penjaga statik di `38c715f` = garis dasar kecuali `verify_auth_coverage` 27 → **26** (AG-T5); `verify_atomic_claim` 161/0, `verify_posting_coverage` 138/0, `verify_cash_single_door` 736/0, `verify_role_gate_ui` 31/0, `verify_detail_modal` 30/0. Glosarium KN_32: §9.18 PY-T2 · §9.19 TX-T2 · §9.20 AG-T5 · §9.21 CR-T2 · §9.22 PM-T4 (nomor pelaksana dirapikan integrator). Indeks wajib lapis A: 29 + PY-T2 2 + CR-T2 2 + PM-T4 1 = **34** (`check_required_indexes` 34/34 di data acuan).
- Dipasang di atas CR-T2 (`76a337d`) dari T pelaksana (basis `15d3258`) → **`38c715f`**. Bentrok:
  `ENTITY_REGISTRY.md` (baris PM-T4 + baris Kartu Tindakan versi AG-T5), `indexes.py` (blok CR-T2 dan PM-T4 masing-masing
  daftar sendiri), dua uji PK-14 (lapis B `CRT2_INDEKS + PMT4_INDEKS`; lapis A **34**), `test_KFT1_izin_pengaturan.py`
  (`AGT5_KUNCI + PMT4_KUNCI`), KN_32 (PM-T4 → §9.22) — kedua perilaku dipertahankan. Fixture akses
  (`access_builtin_fixture.json`, `access_nav_fixture.json`) dibangkitkan ulang dari katalog tergabung (memuat izin
  AG-T5 dan PM-T4). `tests_mem` **2045/2/2**, 0 gagal; `verify_atomic_claim` 161/0, `verify_posting_coverage` 138/0,
  `verify_cash_single_door` 736/0.
- Lingkungan A: lapis A **U16 lulus** (dua terima setoran bersamaan → satu 200 + satu 409, satu kas `cash_deposit`);
  `test_bp_MNT1_menu_keuangan.py` (tabel `view_main_permission.json`) dan PK-14 (34) lulus
  (`bukti/PM-T4/integrator_lapis_A_rantai.txt`). INV-TTP-01 PASS di data acuan. **H5: semua PT tetap `kas_langsung`.**
- Uji jalan **U17** (data contoh di database uji lokal: `ent_ksc` = `titipan`, batas Rp 5.000.000, tenggat 2 hari; dua
  kwitansi tunai sales Rp 300.000 + Rp 150.000 → titipan, satu setoran Rp 150.000 diajukan): Kas & Bank › Titipan
  Sales (1280/1024) — "Setoran menunggu diterima" (Terima setoran / Tolak) dan "Titipan belum disetor" per pemegang,
  tabel = lebar kartu, `overflowX` 0; kartu HP sales "Titipan Saya" (390 px: Rp 450.000, 2 kwitansi, batas, tenggat
  terdekat, "Sudah diajukan Rp 150.000 — serahkan uangnya ke kasir.", tombol Setor) rapi (`bukti/PM-T4/cek_*.png`). Tidak
  ada cacat.

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A dipakai integrator). Lingkungan B / statik (pelaksana):

| Pemeriksaan | B (`5f193df`) | HEAD murni `84744dc` | T = `84744dc` + PM-T4 (penjaga dan jest terkait diulang di `15d3258`) |
|---|---|---|---|
| `tests_mem` | 1924 / 2 / 2 xfail | — (tidak dijalankan; mesin sibuk) | **1992 / 2 / 2 xfail** (`bukti/PM-T4/tests_mem_T.txt`) · sebelumnya di `5f193df` 1944/2/2 dan di `5edef21` 1962/2/2 (`bukti/PM-T4/tests_mem_T_di_*.txt`) |
| jest penuh (35 suite gagal dimuat `cmdk`/`@radix-ui`, himpunan sama) | 957 lulus · 119 suite | 972 lulus · 121 suite | **979 lulus · 122 suite** (+7 `pmt4TitipanSales`) |
| `hitung_penjaga.sh` (auth 27 · ui 13 · i18n 103 · create_modal 6 · page_tabs 1 · to_list 5 · entity_label 2 · access_nav 0) | = | = | **identik HEAD murni** (`bukti/PM-T4/penjaga_H.txt`, `penjaga_T.txt`) |
| `verify_role_gate_ui` / `verify_detail_modal` | 31/0 · 30/0 | 31/0 · 30/0 | 31/0 · 30/0 |
| `verify_posting_coverage` / `verify_cash_single_door` (+uji-diri) | 133/0 · 728/0 | 133/0 · 730/0 | 137/0 · 732/0 (uji-diri hijau) |
| `verify_atomic_claim` (+`--self-test` 64) | 160/0 | 160/0 | 161/0 (terima setoran = `service`), uji-diri hijau; inventaris 123 → 124 baris |
| `verify_payment_vocab` / `verify_permission_checked` | 1814/0 · 606/0 | 1818/0 · 606/0 | 1823/0 · 610/0 |
| `verify_config_text` / `verify_config_fallback` (+`--entity`) | 3276/0 · 157/0 | — | 3311/0 · 159/0 · 159/0 |
| `audit_config_wiring --strict` · `check_nav_map` (salinan berjalur T) · `verify_access_catalog_nav` | hijau · PASS · 0 | — · — · 0 | hijau · PASS · 0 |
| `gen_config_key_index --check` · `verify_codebase_map` · `test_fe03_access_catalog.py` | — | — | selaras · PASS · 6/6 |
| `sapuan_izin.py` mode cepat (PR-T8) | MERAH 20 (garis dasar) | — | (di `5f193df`) MERAH 20 — himpunan sama dengan B, tidak ada rute `/api/cash-*`; `--awalan /api/cash-` HIJAU 0 |

## Penggabungan

- HEAD tujuan: **`15d3258`** (`/home/user/KNHOST`, dibaca saja). HEAD maju tiga kali selama uji: digabung dulu ke `5f193df`
  (= B; 54 berkas disalin; tests_mem 1944/2/2, jest 964) → `5edef21` (PY-T2; tests_mem 1962/2/2, jest 972 — HEAD murni
  965) → **`84744dc`** (PY-T2 lencana, TX-T2 (a)+(b)) di worktree T `scratchpad/wt33` (`bukti/PM-T4/penggabungan_T.txt`;
  tests_mem 1992/2/2, jest 979 — HEAD murni 972) → `15d3258` (TX-T2 cek layar: 4 berkas pajak, tidak satu pun berkas unit
  ini → T dipindah dengan berkas gabungan yang sama, peta kode dibangkitkan ulang; jest suite terkait + `hitung_penjaga`
  diulang, `tests_mem` dari `84744dc` berlaku karena tidak ada perubahan server/uji B). Penggabungan ke `84744dc`:
  33 berkas sama di B dan HEAD → disalin dari W; 8 berkas baru; **7 digabung tiga arah otomatis** (`ENTITY_REGISTRY.md`,
  `entity_scope.py`, `indexes.py`, `server.py`, `configKeyIndex.json`, `memory/PRD.md`, `verify_contract.py`); **bentrok 7,
  kedua perilaku dipertahankan**:
  - `backend/idempotency.py` — PY-T2 `"/api/hr/compensation/", "/api/hr/assignments/"` dan PM-T4 `"/api/cash-deposits"`
    (ekor tuple digabung).
  - `backend/tests_mem/test_KFT1_izin_pengaturan.py` — `PYT2_KUNCI = 1`, `TXT2_KUNCI = 1`, `PMT4_KUNCI = 3`; jumlah U04
    `… + PYT2_KUNCI + TXT2_KUNCI + PMT4_KUNCI`.
  - `backend/tests_mem/test_PK14_indeks_wajib.py` — `PYT2_INDEKS = 2` dan `PMT4_INDEKS = 1` dijumlahkan; lapis A
    `tests/test_bp_PK14_indeks_wajib.py` 31 (PY-T2) + 1 = **32**.
  - `scripts/verify_data_integrity.py` — lapisan `layer_hr_compensation_invariants` (INV-PY-2) dan
    `layer_cash_holding_invariants` (INV-TTP-01) keduanya, dua baris registri.
  - `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` — §9.18 PY-T2, §9.19 TX-T2; bagian PM-T4 menjadi **§9.20** (di W tertulis §9.18).
  - `CODEBASE_MAP.md` (hasil pembangkit) dibangkitkan ulang; `configKeyIndex.json` dibangkitkan ulang (selaras); fixture
    akses dibangkitkan ulang (sama); `memory/INVENTARIS_MULTI_KOLEKSI_2026-09.md` dibangkitkan ulang (124 baris).
- Agen paralel lain (CR-T2 jadwal tagihan & saldo piutang, KM-T2 layar Capaian, AG-T5, PY-T3) belum masuk HEAD saat
  digabung — bila HEAD maju lagi, gabung tiga arah dan pertahankan kedua perilaku; titik rawan: `ar_receipt_service.py`
  (cabang titipan di `create_receipt`, `void_receipt`, `repost_receipt`), `gl_service._post_cash_transaction` (sisi kredit
  dipindah ke `_receipt_lines`), `services/incentive_facts.py` (INV-KM-2), `permissions_config.py`/`access_modules.py`
  (blok PM-T4 di akhir), `login_only_endpoints.py` + `test_PRT3_login_saja.py`, `doc_number_kinds.py` + uji KP-T5a/b,
  `config_catalog_payment.py` + uji KF-T1/KF-T4, `hubTabs.js` + `mnt1MenuKeuangan`/`roleReach`.

## Hambatan lingkungan

- Lingkungan A tidak dipakai (brief): U16 ditulis saja; gate belum; U17 belum diuji jalan.
- Jest: 35 suite lama gagal dimuat (`cmdk`/`@radix-ui`) — sama di B.

## Titik henti (H5) dan yang perlu direview

- **H5 — pertanyaan pemilik (untuk `STATUS.md` "Menunggu pemilik")**: "PT mana yang memakai titipan untuk tunai yang
  diterima sales (`pembayaran.sales_terima_tunai`), berapa batas per sales dan tenggat setornya?" Pilihan: `kas_langsung`
  (bawaan, seperti hari ini) · `titipan` (kas kantor baru bertambah saat setoran diterima kasir/Finance) · `dilarang`
  (sales tidak bisa mencatat tunai). Usulan: `titipan` untuk PT yang sales-nya menagih tunai di lapangan, batas mis.
  Rp 5.000.000 dan tenggat 1–2 hari, dinyalakan per PT sesudah angka uji coba dicocokkan manual. Kode/seed tidak mengubah
  pengaturan PT mana pun.
- Saldo akun 1-1280 dipakai bersama Kasus Keuangan ("uang dipegang karyawan") — invarian membandingkan per sumber jurnal.
- Titipan terbuka saat pengaturan dikembalikan ke `kas_langsung` tetap diselesaikan lewat setoran biasa (spesifikasi).
- Batas titipan tanpa kunci atomik (lihat Asumsi).
- AG-T3: kartu kwitansi tunai yang disetujui orang tanpa `cash.create` di PT `titipan` menjadi titipan orang itu.
- CR-T2 (saldo piutang, paralel): kwitansi titipan menurunkan piutang lewat baris pembayaran `kind: kas` biasa (alokasi
  `allocate`), jadi saldo piutang tidak perlu cabang khusus; yang berbeda hanya: tanpa kas, tanpa rekening, tanpa
  `bank_verified` (tunai).
- KM-T1: fakta pencairan menghitung kwitansi titipan seperti kwitansi kas (uang pelanggan sudah diterima perusahaan lewat
  karyawannya); bila insentif hanya boleh dihitung sesudah disetor, itu keputusan pemilik.

Status: implemented_pending_review.
