# Gelombang 3 · Fase 04 — Sumber angka, analitik, parser, dan tampilan

Kerjakan Gelombang 3 dari commit repo saat ini. Baca README, findings-tracker.json, laporan detail, dan source terkait sebelum mengubah kode. Catat actual HEAD; commit audit hanya baseline bukti, bukan asumsi bahwa repo belum berubah. Periksa dulu apakah kasus sudah diperbaiki untuk menghindari patch ganda. Jangan menimpa dokumen Gelombang 1/2 atau mengubah hasil audit historis.

Untuk setiap ID: telusuri input UI → request/schema → permission/entity/lini → service → persist/ledger → projection/report → frontend, termasuk retry, concurrency, pembatalan dan reversal yang relevan. Pertahankan kuantitas fisik, unit, pemilik barang, source document, harga/HPP serta legal entity. Jangan mengubah expected menjadi hasil bug, menyembunyikan warning, atau menyimpulkan fixed hanya dari HTTP 200. Keputusan definisi bisnis yang belum tegas harus dicatat sebagai needs_business_decision.

Setelah implementasi, isi implementation_commit, implementation_evidence, daftar file, perbandingan expected/actual sebelum-sesudah, perintah uji, batas pengujian, dan risiko migrasi. Status agent paling jauh implemented_pending_validation; reviewer independen yang menetapkan verified_fixed setelah seluruh acceptance dan flow terkait lulus. Simpan proof baru terpisah, tanpa menimpa evidence baseline.

Prasyarat: 01. Jumlah ID: 24.

## D4-STOCK-02 — Filter kategori tidak diterapkan pada bucket umur stok

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L175). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-STOCK-02`.

**Penyebab:** Aging diakumulasi sebelum row product diperiksa terhadap category. Tabel kategori woven sudah difilter, bucket aging masih berisi kategori lain.

**Prompt perbaikan:** Bentuk product whitelist/filter yang sama sebelum mengambil roll, balance dan movement. Semua KPI/chart harus memakai filter yang sama, atau labelkan secara eksplisit jika global.

**Kriteria validasi:** Filter woven: total rows100 = sum aging100; filter knitting400. Uji kategori kosong, SKU tanpa kategori dan kombinasi entitas/gudang.

## D4-STOCK-03 — Nilai persediaan analitik mengabaikan landed cost

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L166). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-STOCK-03`.

**Penyebab:** Valuasi memakai base_unit_cost meskipun unit_cost roll sudah memuat landed cost. Basis ini berbeda dengan nilai penuh costing/GL; tampilan nilai persediaan tidak menyatakan hanya biaya dasar.

**Prompt perbaikan:** Tetapkan kontrak nilai persediaan: tampilkan biaya penuh dari sumber biaya kanonis; bila perlu pisahkan dasar, landed dan total. Jangan menjumlahkan landed dua kali.

**Kriteria validasi:** Roll10×12 menghasilkan120, split dasar100 + landed20. Uji voucher landed apply/void dan per-entitas. Jika bisnis memilih base-only, label dan rekonsiliasi harus menyatakan basis tersebut.

## D4-STOCK-04 — Tanggal roll tanpa timezone dapat menjatuhkan laporan umur stok

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L33). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-STOCK-04`.

**Penyebab:** Parser mengembalikan datetime naive untuk string YYYY-MM-DD, lalu dikurangkan dari now yang timezone-aware.

**Prompt perbaikan:** Normalisasi timezone pada boundary parsing dan tentukan kebijakan tanggal legacy. Jangan mengubah data historis diam-diam tanpa aturan timezone yang disetujui.

**Kriteria validasi:** Date-only, ISO dengan offset, Z, kosong dan tanggal invalid ditangani deterministik tanpa exception server; aging hari diperiksa di batas WIB.

## D4-AI-02 — Metric pelanggan baru mengabaikan scope lini

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_engine.py#L168). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-AI-02`.

**Penyebab:** _src_fact_new tidak memakai sc.line_q sebagaimana sumber fact lain. Filter woven tetap menghitung customer knitting-only.

**Prompt perbaikan:** Gunakan scope/line policy bersama sebelum first-purchase grouping, termasuk keputusan apakah first berarti first ever atau first di lini. Jangan hanya filter sesudah agregasi first.

**Kriteria validasi:** Knitting-only excluded woven; customer pernah membeli knitting lalu pertama woven diuji menurut definisi yang disetujui. Entity/owned-customer/role dimensi tetap enforced.

## D4-AI-03 — Refresh fact sales menghapus data lama sebelum replacement berhasil

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_facts.py#L146). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-AI-03`.

**Penyebab:** _write melakukan delete semua fact SO yang direfresh lalu insert_many. Bila insert gagal sebelum write, projection lama hilang walaupun source SO tetap ada.

**Prompt perbaikan:** Gunakan generation staging + atomic publish pointer, transaction, atau deterministic upsert + retire stale rows hanya setelah replacement lengkap. Simpan sync progress dan expose freshness/error.

**Kriteria validasi:** Fault sebelum/sesudah tiap write tidak membuat complete snapshot lama hilang. Retry dan dua worker tidak duplicate fact; Σfact sama source valid, invalid schema tidak menurunkan seluruh dataset.

## D4-AI-04 — Pembulatan alokasi tim sales tidak mengonservasi nilai dokumen

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_facts.py#L118). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-AI-04`.

**Penyebab:** Setiap bagian dibulatkan independen ke2desimal tanpa menempatkan residual pada baris deterministik.

**Prompt perbaikan:** Alokasikan dalam minor units/Decimal, gunakan largest-remainder atau residual akhir deterministik untuk gross/net/PPN. Konservasi harus terjaga pada semua grouping.

**Kriteria validasi:** Net1.01 dibagi2 anggota50/50 tetap total1.01; fractionaldiscount+tax,10lines×2sales, negative return dan replay sync tidak mengubah total/identity. Data legacy dengan anggota lebihbanyak, bila masihdibaca, tidak boleh merusak konservasi.

## D4-HR-01 — Payroll gabungan memakai satu run pada KPI dan menimpa run lain pada trend

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_analytics_service.py#L146). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-HR-01`.

**Penyebab:** KPI find_one(period); trend map period diberi assignment sehingga run berikut menimpa sebelumnya. Dua entitas dalam bulan sama tidak diaggregate.

**Prompt perbaikan:** Aggregate posted/eligible runs perperiod/selectedentity dengan lifecycle jelas, hindari menghitung draft+replacement ganda. Bedakan sum employees vs distinctpeople jika employee shared.

**Kriteria validasi:** All gross300/net270, A100/B200, chart=card. Draft/replaced/void run tidak double-count; BPJS/PPH dan employee basis diuji.

## D4-HR-02 — Turnover menggunakan waktu edit data sebagai waktu karyawan keluar

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_analytics_service.py#L136). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-HR-02`.

**Penyebab:** Inactive/resigned dihitung berdasarkan updated_at, bukan effective separation event. Schema saat ini tidak menyediakan termination_date yang kanonis; field tersebut pada probe hanya menjelaskan tanggal bisnis, bukan field publik yang diklaim sudah ada.

**Prompt perbaikan:** Tambahkan effective status-transition/separationdate dengan audit history dan backfill yang eksplisit. Perubahan profil tidak mengubah tanggal keluar. Definisikan numerator/denominator turnover.

**Kriteria validasi:** KeluarJuli lalu editOktober: Juli1, Oktober0. Rehire, koreksi status, delete/archival dan transferentity memiliki treatment terdefinisi.

## D4-WMS-01 — RFID RED hari ini pada Warehouse Health memakai hari UTC

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L28). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-WMS-01`.

**Penyebab:** Filter today memakai prefix tanggal UTC. Operasi gudang lokal menggunakan WIB sehingga antara00:00–06:59 WIB hari bisnis berbeda.

**Prompt perbaikan:** Gunakan range [WIBdaystart, nextdaystart) dikonversi UTC. Jangan memakai regex prefix date atau mencampur string timestamp offset berbeda.

**Kriteria validasi:** 23:59WIB yesterday excluded;00:00/06:59todayincluded; timezone UTC/Z/offsetnormalized. Chart dan KPI memakai satu batas hari bisnis.

## D4-WMS-02 — Cycle count terbaru yang belum selesai menghapus angka akurasi terakhir

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L71). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-WMS-02`.

**Penyebab:** Service memilih dokumen terbaru tanpa mensyaratkan accuracy valid/status selesai dan tidak mengirim status. Frontend memasang suffix% walau accuracy tidak ada.

**Prompt perbaikan:** Pisahkan latestcountstatus dan lastmeasuredaccuracy. Pilih count terukur sesuai lifecycle bisnis (bukan secara arbitrer selaluapproved) dan tampilkan N/A untuk belum dinilai.

**Kriteria validasi:** Openbaru tidak menimpa lastmeasured95%; UI menunjukkan statusopen. Measured0% harus tetap0% dan dibedakan darinull; rejected/void count tidak dijadikan valid measurement.

## D4-MKT-01 — Reach agregat post disajikan ulang sebagai reach tiap platform dan akun

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/marketing_ext.py#L137). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-MKT-01`.

**Penyebab:** Satu metrics aggregate post ditambahkan penuh ke setiap platform/account. Tidak ada pengukuran per-channel tersimpan, sehingga channel reach bukan actual channel measurement. Kelompok overlapping boleh nonadditive hanya bila kontraknya jelas.

**Prompt perbaikan:** Tentukan apakah breakdown merupakan shared post attribution atau measurement perchannel. Jika shared, label nonadditive dan jangan total ulang. Jika actual, simpan metrics perplatform/account dengan provenance/time dan aggregate dedup sesuai definisi.

**Kriteria validasi:** Postmulti-channel100 tidak ditampilkan seolah masing-masingpunya actual100 tanpa keterangan. Separate metrics30/70 hanya jika benar-benar diukur. Reachunique crosschannel tidak disimpulkan dari penjumlahan biasa.

## D4-RND-01 — KPI R&D menggabungkan orang berbeda yang mempunyai nama sama

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rnd_kpi_service.py#L153). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-RND-01`.

**Penyebab:** Round producer menyimpan performed_by_user_id, tetapi KPI memakai performed_by/opened_by/created_by displayname sebagai identity. Dua user dengan nama sama menjadi satu baris.

**Prompt perbaikan:** Group stable user_id/employee_id dan render displayname sebagai label. Legacy name-only perlu mapping ambiguity explicit, bukan autojoin semua nama.

**Kriteria validasi:** U1/U2nama sama→2KPI; U1ganti nama→1history. Fallbacklegacyambiguous ditandai, customroleline/roundtypefilter tetap berlaku.

## D4-EQ-01 — KPI Laba Periode Berjalan pada perubahan ekuitas berubah menjadi nol sesudah tutup buku

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/equity_statement_service.py#L57). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-EQ-01`.

**Penyebab:** equity_statement mengisi net_income dari perubahan saldo laba yang belum ditutup pada neraca. Itu perubahan komponen equity, bukan laba operasional periode. Jurnal penutup mengubah saldo current_earnings tanpa mengubah laba periode. Frontend memakai net_income dengan label Laba Periode Berjalan tanpa menjelaskan unclosed earnings movement.

**Prompt perbaikan:** Pisahkan period_operating_net_income yang dihitung dari P&L non-closing dalam range/scope yang sama, dengan movement_unclosed_earnings yang diperlukan untuk roll-forward. KPI profit memakai period income; tabel perpindahan RE/current earnings tetap merekonsiliasi, jangan menambahkan laba sekali lagi ke end_total atau movement_total. Dokumentasikan label, beginning balances, fiscal range dan export contract.

**Kriteria validasi:** Periode profit100 tetap KPI100 sebelum/sesudah monthly/year close, reopen/reclose, dan menutup residual; equity movement/end totals tetap100. Uji opening retained earnings, laba/rugi, periode melintasi beberapa closes, dividen/injeksi modal, comparative/entity, CSV dan source-to-rendered validation. Net income tidak berubah hanya karena laba ditransfer antar komponen equity.

## D4-WMS-04 — KPI antrean simpan menghitung roll reserved yang tidak boleh diputaway

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L42). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-WMS-04`.

**Penyebab:** putaway_ready hanya memeriksa owner/panjang/journey/routing; suggest/create menegakkan status available dan guard gerak/reservasi. Tidak ada ready/blocked breakdown atau penjelasan beda definisi. Tag_verified adalah bukti identitas, bukan ketersediaan operasional.

**Prompt perbaikan:** Gunakan resolver eligibility yang sama pada health/suggest/create dengan owner/warehouse/current identity/reservasi. Jika termasuk blocked, pisahkan total_pending/ready/blocked_by_reason. Guard CAS server tetap wajib. Cakup QC, routing, active movement dan tag lifecycle.

**Kriteria validasi:** Reserved tidak menambah actionable ready; health/suggest konsisten. Uji available, partial reserved, quarantine, active PA, pending/retired tag, crossdock, empty, beberapa entitas dan total vs rows. Bila definisi queue berbeda, tampilkan ready0/blocked1 beserta alasan.

## D4-SIM-01 — Simulator menyatakan 3-way match lolos saat barang belum diterima

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Pusat Pengaturan → simulator pencocokan Tagihan Supplier.

**Rantai kejadian:** Simulator received_qty 0/billed_qty 10 → selisih dianggap0 → LOLOS; evaluator bill operasional → blocked.

**Letak kesalahan dan penyebab:** Cabang pembagi nol mengubah selisih kuantitas menjadi nol. Simulator memakai rumus tersendiri yang berbeda dari evaluator transaksi sebenarnya.

**Dampak, hasil reproduksi, dan batas klaim:** Public simulate menerima received 0/billed 10 dengan toleransi qty0 dan memberi verdict ok. Evaluator layanan vendor bill asli untuk kondisi yang sama memblokir. Kontrol received100/billed 100 lolos; billed 101/received100 melampaui toleransi ditolak. Ini informasi konfigurasi yang salah, bukan bukti tagihan operasional ini otomatis lolos.

**Lokasi source pada commit audit:**

- [backend/services/config_simulator.py:192](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/config_simulator.py#L192) — `dq = ((bill_q - recv_q) / recv_q * 100) if recv_q else 0`.
- [backend/services/vendor_bill_service.py:96](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/vendor_bill_service.py#L96) — `def evaluate_match(`.
- [backend/routers/config.py:160](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/config.py#L160) — `async def simulate(`.

```python
190:     tq = _f(c.get("purchasing.bill_qty_tolerance_percent"), 0)
191:     tp = _f(c.get("purchasing.bill_price_tolerance_percent"), 5)
192:     dq = ((bill_q - recv_q) / recv_q * 100) if recv_q else 0
193:     dp = ((bill_p - po_p) / po_p * 100) if po_p else 0
194:     steps = [{"label": "Selisih qty", "value": f"{_num(dq)}% (toleransi {_num(tq)}%)"},
195:              {"label": "Selisih harga", "value": f"{_num(dp)}% (toleransi {_num(tp)}%)"}]
196:     bad = []
197:     if abs(dq) > tq:
198:         bad.append("qty")
```

**Bukti asli:** [evidence/repro/config-bank-oracles90-results.json](evidence/repro/config-bank-oracles90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| SIM90-ar_penalty-0 | "ok" | "ok" | pass |
| SIM90-ar_penalty-1 | "warn" | "warn" | pass |
| SIM90-ar_penalty-2 | "block" | "block" | pass |
| SIM90-ar_bucket-3 | "ok" | "ok" | pass |
| SIM90-pricing-4 | "warn" | "warn" | pass |
| SIM90-pricing-5 | "ok" | "ok" | pass |
| SIM90-commission_cap-6 | "warn" | "warn" | pass |
| SIM90-commission_cap-7 | "ok" | "ok" | pass |
| SIM90-commission_discount-8 | "warn" | "warn" | pass |
| SIM90-commission_discount-9 | "warn" | "warn" | pass |

**Prompt agent development:**

Gunakan evaluator aturan yang sama untuk simulator dan transaksi, dengan konteks simulasi eksplisit. Saat received 0/billed>0, hasil harus menyatakan belum ada penerimaan dan blokir sesuai basis matching. Jangan mengisi delta0 untuk menghindari pembagi nol.

**Kriteria penerimaan untuk reviewer:**

received 0/billed 10/tolerance0 harus block; nol/nol dijelaskan tanpa NaN. Uji partial receipt, billing cumulatif, qty sisa, tolerance, harga, basis ordered vs received, return/short-close. Hasil simulator dan evaluator harus sesuai untuk input bisnis ekuivalen.

## D4-BANK-01 — Tanggal kalender yang tidak mungkin masuk ke data rekonsiliasi bank

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Keuangan → Rekonsiliasi Bank → preview/import mutasi.

**Rantai kejadian:** Tanggal mentah → format string ISO tanpa validasi kalender → preview valid → import persisten.

**Letak kesalahan dan penyebab:** Parser hanya merapikan komponen tanggal untuk beberapa format. Validasi import memeriksa tanggal tidak kosong, sehingga string tanggal yang bukan tanggal kalender tetap disimpan.

**Dampak, hasil reproduksi, dan batas klaim:** Public preview dan import menerima serta menyimpan 2026-02-30, 2026-99-99, 2026-13-01. Kontrol 2026-02-28 diparsing dan disimpan dengan benar. Ini merusak dimensi periode dan kualitas source rekonsiliasi; skenario tidak melakukan transfer dana atau posting GL.

**Lokasi source pada commit audit:**

- [backend/services/bank_statement_parser.py:179](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/bank_statement_parser.py#L179) — `return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"`.
- [backend/services/bank_recon_service.py:348](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/bank_recon_service.py#L348) — `async def import_lines(`.
- [backend/routers/bank_reconciliation.py:38](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/bank_reconciliation.py#L38) — `class StatementLineIn(`.

```python
177:     m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
178:     if m:
179:         return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
180:     if fmt == "yyyymmdd" and re.fullmatch(r"\d{8}", s):
181:         return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
182:     if fmt == "yymmdd" and re.fullmatch(r"\d{6}", s):
183:         return f"20{s[0:2]}-{s[2:4]}-{s[4:6]}"
184:     if re.fullmatch(r"\d{8}", s):
185:         return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
```

**Bukti asli:** [evidence/repro/config-bank-oracles90-results.json](evidence/repro/config-bank-oracles90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| SIM90-zero-receipt-public-verdict | "block" | "ok" | observed_difference |
| BANK90-date-preview-2026-02-30 | 0 | 1 | observed_difference |
| BANK90-date-persistence-2026-02-30 | 0 | 1 | observed_difference |
| BANK90-date-preview-2026-99-99 | 0 | 1 | observed_difference |
| BANK90-date-persistence-2026-99-99 | 0 | 1 | observed_difference |
| BANK90-date-preview-2026-13-01 | 0 | 1 | observed_difference |
| BANK90-date-persistence-2026-13-01 | 0 | 1 | observed_difference |
| BANK90-mt940-RC | "out" | "not_parsed" | observed_difference |
| BANK90-mt940-RD | "in" | "not_parsed" | observed_difference |
| BANK90-mt940-reversal-net | 0 | -100.0 | observed_difference |

**Prompt agent development:**

Validasi semua jalur tanggal lewat satu parser kalender yang ketat, termasuk model input langsung. Kembalikan error per baris untuk tanggal tidak sah; jangan normalize ke bulan berikutnya. Pertahankan year_hint dan locale yang eksplisit; tanggal ambigu membutuhkan format yang dipilih.

**Kriteria penerimaan untuk reviewer:**

Tanggal mustahil ditolak preview/import/direct-line; leap-year 2024-02-29 sah dan 2026-02-29 ditolak. Uji ISO, compact, dd/mm, mm/dd, teks bulan, MT940, OFX, timestamp, tahun kosong, whitespace, error parsial dan filter periode.

## D4-BANK-02 — Parser MT940 tidak membaca kode pembalikan transaksi RC dan RD

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Keuangan → Rekonsiliasi Bank → import MT940.

**Rantai kejadian:** Field61 D100 + RD100 → hanya D terbaca → preview/import saldo bersih keluar100.

**Letak kesalahan dan penyebab:** Regex menerima huruf C/D lalu R opsional. Format pembalikan MT940 memakai RC/RD, dengan R sebelum C/D; arah transaksi pembalikan juga harus dibalik.

**Dampak, hasil reproduksi, dan batas klaim:** Kontrol mutasi C/D biasa lolos. Statement sintetik D100 dan RD100 menghasilkan hanya1 mutasi dengan error1 dan net keluar100, padahal pasangan itu net0. Public import mengimpor baris biasa dan mengembalikan error pembalikan; error terlihat, sehingga temuan tidak menyebut hilangnya baris secara diam-diam. Standar primer: UniCredit MT94x General V1.1, Field61 (https://www.unicredit.ro/content/dam/cee2020-pws-ro/DocumentePDF/DocumenteCIB/MT94x_General_V1.1.pdf).

**Lokasi source pada commit audit:**

- [backend/services/bank_statement_parser.py:416](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/bank_statement_parser.py#L416) — `(?P<mark>[CD])R?`.
- [backend/routers/bank_reconciliation.py:202](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/bank_reconciliation.py#L202) — `async def import_file(`.

```python
414: 
415: RE_MT940_61 = re.compile(
416:     r"^:61:(?P<vdate>\d{6})(?P<edate>\d{4})?(?P<mark>[CD])R?(?P<amt>[\d.,]+)"
417:     r"(?P<code>[A-Z]\w{3})?(?P<rest>.*)$")
418: 
419: 
420: def parse_mt940(raw: str, fmt: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
421:     rows: List[Dict[str, Any]] = []
422:     errors: List[Dict[str, Any]] = []
```

**Bukti asli:** [evidence/repro/config-bank-oracles90-results.json](evidence/repro/config-bank-oracles90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| BANK90-mt940-C | "in" | "in" | pass |
| BANK90-mt940-D | "out" | "out" | pass |
| BANK90-mt940-RC | "out" | "not_parsed" | observed_difference |
| BANK90-mt940-RD | "in" | "not_parsed" | observed_difference |
| BANK90-mt940-reversal-net | 0 | -100.0 | observed_difference |

**Prompt agent development:**

Parse debit/credit marker sebagai D, C, RC, RD sesuai format; RC berarti debit dan RD berarti credit. Pertahankan error per baris dan status import parsial yang jelas. Rekonsiliasikan opening/movement/closing balance sebelum pengguna menganggap file lengkap.

**Kriteria penerimaan untuk reviewer:**

D100+RD100 menghasilkan2 baris/net0; C100+RC100 juga0. Uji funds-code, entry date, references, :86:, multiple statements, malformed marker, duplicate import, saldo akhir dan kebijakan partial vs atomic.

Rujukan Field 61: [UniCredit MT94x General V1.1](https://www.unicredit.ro/content/dam/cee2020-pws-ro/DocumentePDF/DocumenteCIB/MT94x_General_V1.1.pdf). Error parser memang terlihat; temuan ini tidak menyatakan kehilangan data tanpa peringatan.

## D4-RET-CHAIN-01 — Ringkasan fisik rantai retur menjumlahkan barang berlainan satuan menjadi satu angka

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** Retur → perjalanan barang → posisi barang yang masih ditahan.

**Rantai kejadian:** Owner sama:100yard kain +5kg barang lain → satu langkah held berlabel105yard.

**Letak kesalahan dan penyebab:** Bucket hanya berdasarkan pemilik dan memakai satuan dari roll pertama, kemudian menjumlahkan length_remaining tanpa pemisahan satuan.

**Dampak, hasil reproduksi, dan batas klaim:** Pada fixture linked-roll dua produk, ringkasan satu owner menunjukkan105yard; tidak dapat ditafsirkan sebagai panjang fisik. Source records100yard dan5kg tidak berubah. Kontrol rantai sama satuan dan redaksi lintas entitas lulus; browser/hardware tidak dibuktikan oleh probe ini.

**Lokasi source pada commit audit:**

- [backend/services/return_chain_service.py:223](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_chain_service.py#L223) — `held.setdefault(`.
- [backend/services/return_chain_service.py:224](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_chain_service.py#L224) — `row["qty"]`.
- [backend/services/return_chain_service.py:159](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_chain_service.py#L159) — `"unit"`.

```python
221:             continue
222:         own = r.get("owner_entity_id", "")
223:         row = held.setdefault(own, {"qty": 0.0, "rolls": 0, "unit": r.get("unit", "")})
224:         row["qty"] = round(row["qty"] + float(r.get("length_remaining") or 0), 2)
225:         row["rolls"] += 1
226:     for own, row in held.items():
227:         if row["qty"] <= 0.01:
228:             continue
229:         steps.append({
```

**Bukti asli:** [evidence/repro/quantity-provenance90-results.json](evidence/repro/quantity-provenance90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| chain.no_document | false | false | pass |
| chain.full_stages | ["sales_return", "interco_return", "purchase_return", "kept", "kept"] | ["sales_return", "interco_return", "purchase_return", "kept", "kept"] | pass |
| chain.full_root | 150 | 150 | pass |
| chain.complete_route | true | true | pass |
| chain.resolve_from_purchase | "SR1" | "SR1" | pass |
| chain.resolve_from_interco | "SR1" | "SR1" | pass |
| chain.foreign_amount_hidden | null | null | pass |
| chain.foreign_supplier_hidden | false | false | pass |
| chain.foreign_po_hidden | false | false | pass |
| chain.foreign_lot_hidden | "" | "" | pass |

**Prompt agent development:**

Pisahkan agregasi berdasarkan pemilik+satuan, dan produk bila konteks tampilan memerlukannya. Konversi hanya lewat UoM yang sah dengan jejak; jangan menjumlahkan kg dan yard. Lengkapi struktur response agar UI menampilkan setiap kelompok tanpa parsing teks.

**Kriteria penerimaan untuk reviewer:**

100yard +5kg harus tampil sebagai100yard dan5kg. Same-unit sums tetap benar, redaksi informasi entitas lain tetap bekerja, rollcount dan complete-chain memakai definisi yang konsisten.

## D4-ALERT-DATE-01 — Peringatan AP menyebut jatuh tempo hari ini sudah terlambat satu hari

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** Scheduler → notifikasi tagihan supplier jatuh tempo.

**Rantai kejadian:** bill_date tanggal kalender +NET30 =hari ini00:00UTC → now siang → timedelta.days=-1 → critical LEWAT1hari.

**Letak kesalahan dan penyebab:** Selisih datetime dibulatkan ke bawah oleh .days, sementara jatuh tempo dokumen merupakan tanggal kalender.

**Dampak, hasil reproduksi, dan batas klaim:** Public source fields valid berupa tanggal YYYY-MM-DD. Original alert generator memberi critical/LEWAT1hari pada due-date yang sama dengan hari pengujian. Kontrol tanggal3hari mendatang/3hari lewat dan tagihan paid/draft lulus.

**Lokasi source pada commit audit:**

- [backend/services/alert_service.py:144](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L144) — `left = (due - now).days`.
- [backend/services/alert_service.py:120](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L120) — `async def job_ap_due`.
- [backend/services/alert_service.py:150](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L150) — `overdue = left < 0`.

```python
142:         days = tmaps[ent].get(sup_term.get(b.get("supplier_id", ""), ""), 0)
143:         due = bd + timedelta(days=days)
144:         left = (due - now).days
145:         if left > AP_DUE_SOON_DAYS:
146:             continue
147:         scanned += 1
148:         if scanned > MAX_ALERTS_PER_JOB:
149:             break
150:         overdue = left < 0
```

**Bukti asli:** [evidence/repro/alert-numeric90-results.json](evidence/repro/alert-numeric90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| alerts.ap_due_calendar_today | true | false | observed_difference |
| alerts.ap_today_not_overdue | "warning" | "critical" | observed_difference |

**Prompt agent development:**

Gunakan definisi hari dan zona waktu bisnis yang konsisten untuk tanggal dokumen, bukan usia24jam yang dibulatkan ke bawah. Pusatkan due-date/day-delta untuk AP board, aging dan scheduler.

**Kriteria penerimaan untuk reviewer:**

Jatuh tempo hari ini =HARI INI/warning/0hari; besok=1; kemarin=1hari terlambat. Uji UTC vs zona waktu bisnis, cutoff malam, term override perentitas dan tahun kabisat.

## D4-ALERT-AMT-01 — Peringatan utang menampilkan nominal penuh meskipun pembayaran sebagian sudah tercatat

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** Pembayaran supplier → saldo AP → notifikasi jatuh tempo.

**Rantai kejadian:** Tagihan100, amount_paid70, statusposted → peringatan jatuh tempo tetap menampilkan100.

**Letak kesalahan dan penyebab:** Query tidak membawa amount_paid/remaining, kemudian isi peringatan memakai grand_total tanpa menghitung saldo.

**Dampak, hasil reproduksi, dan batas klaim:** Original alert body memakai100 pada partial-payment fixture70; saldo yang perlu ditagih/dibayar30. Statuspaid dikecualikan dengan benar sebagai kontrol. Jika nominal dokumen sengaja ditampilkan, ia harus diberi label dan saldo30 tetap jelas, bukan memberi kesan100 perlu dibayar.

**Lokasi source pada commit audit:**

- [backend/services/alert_service.py:124](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L124) — `"supplier_id": 1, "supplier_name": 1, "entity_id": 1`.
- [backend/services/alert_service.py:157](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L157) — `_rp(b.get('grand_total'))`.
- [backend/routers/vendor_bills.py:97](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/vendor_bills.py#L97) — `"amount_paid"`.

```python
122:         {"status": "posted"},
123:         {"_id": 0, "id": 1, "bill_number": 1, "bill_date": 1, "grand_total": 1,
124:          "supplier_id": 1, "supplier_name": 1, "entity_id": 1}).to_list(5000)
125:     if not bills:
126:         return {"created": 0, "scanned": 0, "detail": "tidak ada tagihan supplier terposting"}
127:     sup_ids = [b.get("supplier_id") for b in bills if b.get("supplier_id")]
128:     sups = await db.suppliers.find(
129:         {"id": {"$in": sup_ids}}, {"_id": 0, "id": 1, "payment_term_code": 1}).to_list(2000)
130:     sup_term = {s["id"]: s.get("payment_term_code", "") for s in sups}
```

**Bukti asli:** [evidence/repro/alert-numeric90-results.json](evidence/repro/alert-numeric90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| alerts.ap_partial_reports_outstanding | true | false | observed_difference |

**Prompt agent development:**

Ambil outstanding dari SSOT yang sama dengan AP aging/pembayaran/kontrabon. Jika tampilkan gross, paid, deduction dan balance, labeli masing-masing. Jangan menghitung ulang dari payments yang voided tanpa aturan yang sama.

**Kriteria penerimaan untuk reviewer:**

100-70 → saldo30 pada peringatan; full payment tidak membuat peringatan; void/payment reversal/deductions/makloon claims dan term override harus konsisten dengan AP ledger.

## D4-KPI-WEIGHT-01 — Bobot KPI nol menjadi satu dan mengubah rata-rata tertimbang

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** HR → KPI → input/edit bobot → Self Service → KPI Saya.

**Rantai kejadian:** KPI 20 berbobot 1 + KPI 80 berbobot 3 → rata-rata 65; tambah KPI 150 berbobot 0 → API menyimpan bobot 1 dan rata-rata menjadi 82.

**Letak kesalahan dan penyebab:** Fallback berbasis truthiness menganggap nol sebagai nilai kosong, baik pada input frontend, producer service, maupun perhitungan agregat backend dan frontend periode historis. Schema saat ini secara eksplisit mengizinkan bobot >= 0.

**Dampak, hasil reproduksi, dan batas klaim:** Original ASGI create menerima weight=0 namun mengembalikan weight=1. Setelah PUT menyimpan weight=0, GET /hr/kpi/me tetap memberikan latest_score=82, seharusnya 65 berdasarkan rata-rata tertimbang dengan bobot nol. Kontrol bobot positif menghasilkan 65. Tidak dilakukan verifikasi DOM browser; ekspresi frontend ditelaah pada source. Jika bisnis ingin melarang nol, larangan harus eksplisit dan konsisten pada kontrak, bukan perubahan nilai senyap.

**Lokasi source pada commit audit:**

- [backend/services/hr_kpi_service.py:123](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L123) — `tw = sum(float(r.get("weight") or 1)`.
- [backend/services/hr_kpi_service.py:50](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L50) — `"score": score, "weight": float(payload.get("weight") or 1)`.
- [backend/schemas_hr_kpi.py:19](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_hr_kpi.py#L19) — `weight: float = Field(1, ge=0)`.
- [frontend/src/features/hr/KpiView.jsx:73](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/hr/KpiView.jsx#L73) — `weight: parseFloat(form.weight) || 1`.
- [frontend/src/features/hr/MyKpiCard.jsx:27](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/hr/MyKpiCard.jsx#L27) — `Number(r.weight) || 1`.

```python
121:     if not rows:
122:         return 0.0
123:     tw = sum(float(r.get("weight") or 1) for r in rows) or 1
124:     s = sum(float(r.get("score") or 0) * float(r.get("weight") or 1) for r in rows)
125:     return round(s / tw, 1)
```

**Bukti asli:** [evidence/repro/hr-kpi-projection90-results.json](evidence/repro/hr-kpi-projection90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| kpi.zero_weight_retained | 0 | 1.0 | observed_difference |
| kpi.zero_weight_aggregate | 65 | 82.0 | observed_difference |
| kpi.zero_weight_projection_after_patch | 65 | 82.0 | observed_difference |

**Prompt agent development:**

Tetapkan semantik bobot nol: bila diterima, pertahankan nol dari input sampai agregat dan abaikan kontribusinya; bedakan null/missing dari 0. Jika bisnis memilih bobot wajib positif, validasi UI/API/service dan migrasi data lama secara terkontrol. Gunakan evaluator rata-rata yang sama untuk periode terbaru dan historis.

**Kriteria penerimaan untuk reviewer:**

Dengan semantik nol valid: input/edit bobot 0 tetap 0 dan rata-rata contoh tetap 65 pada API serta tampilan periode terbaru/historis. Uji seluruh bobot nol, satu/dua metrik, bobot desimal, null, nilai negatif, rounding, penghapusan, filter karyawan/entitas/periode.

## D4-KPI-PERIOD-01 — Periode KPI yang bukan bulan kalender diterima dan dipilih sebagai periode terbaru

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** HR → KPI → periode input/edit → daftar KPI dan kartu KPI Saya.

**Rantai kejadian:** POST period=2026-99 diterima → my_kpi mengurutkan teks → latest_period=2026-99, menggeser Oktober 2026; PUT menerima period=bad dan metric kosong.

**Letak kesalahan dan penyebab:** Create memeriksa panjang/pemisah saja; patch tidak mengulang validasi periode maupun nama metrik. Pemilihan periode terbaru mengandalkan urutan string tanpa jaminan kalender valid.

**Dampak, hasil reproduksi, dan batas klaim:** Original API menerima 2026-99 dan GET /hr/kpi/me menjadikannya periode terbaru. PUT period=bad/metric kosong juga 200. Kontrol create periode x dan metrik kosong ditolak. Frontend memeriksa pola digit/pemisah, sehingga validitas bulan belum terjaga; bulan pada native input date tidak membuktikan kontrak API aman.

**Lokasi source pada commit audit:**

- [backend/services/hr_kpi_service.py:39](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L39) — `if len(period) != 7 or period[4] != "-":`.
- [backend/services/hr_kpi_service.py:64](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L64) — `for f in ("metric", "period", "note")`.
- [backend/services/hr_kpi_service.py:109](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L109) — `periods = sorted(`.
- [frontend/src/features/hr/KpiView.jsx:68](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/hr/KpiView.jsx#L68) — `if (!/^\d{4}-\d{2}$/.test(form.period))`.

```python
37:         raise ValueError("Nama metrik KPI wajib diisi.")
38:     period = (payload.get("period") or "")[:7]
39:     if len(period) != 7 or period[4] != "-":
40:         raise ValueError("Periode harus format YYYY-MM.")
41:     target = float(payload.get("target") or 0)
42:     actual = float(payload.get("actual") or 0)
43:     score = compute_score(target, actual, payload.get("score"))
44:     entity_id = emp.get("entity_id", "")
45:     doc = {
```

**Bukti asli:** [evidence/repro/hr-kpi-projection90-results.json](evidence/repro/hr-kpi-projection90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| kpi.patch_empty | 400 | 400 | pass |
| kpi.calendar_period_rejected | true | false | observed_difference |
| kpi.latest_period_real_calendar | "2026-10" | "2026-99" | observed_difference |
| kpi.patch_empty_metric_bad_period_rejected | true | false | observed_difference |

**Prompt agent development:**

Gunakan validator kalender YYYY-MM bersama untuk create/update/import dan validasi metrik nonkosong. Identifikasi periode lama invalid, pisahkan dari laporan sampai diperbaiki secara tercatat. Pilih periode terbaru dari data yang valid; jangan mengubah tanggal historis dengan tebakan.

**Kriteria penerimaan untuk reviewer:**

Bulan 00/13/99, tahun nonnumerik, panjang tidak tepat, serta metrik whitespace ditolak tanpa perubahan DB. Periode valid tetap diterima; latest_period dan filter konsisten; uji pergantian tahun, PUT parsial, data lama invalid dan tampilan historis.

## D4-KPI-SCORE-01 — Skor otomatis KPI dapat negatif meskipun kontrak fungsi menyatakan rentang 0–150

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** HR → KPI → target dan aktual → skor otomatis → KPI Saya.

**Rantai kejadian:** Target 100, aktual -10 → skor otomatis -10; skor manual negatif pada evaluator yang sama dibatasi menjadi 0.

**Letak kesalahan dan penyebab:** Jalur otomatis hanya membatasi nilai maksimum. Jalur skor eksplisit membatasi maksimum sekaligus minimum; keduanya berbeda dari kontrak rentang yang didokumentasikan.

**Dampak, hasil reproduksi, dan batas klaim:** Original API menerima target=100/actual=-10 dan menyimpan score=-10. Kontrol aktual 200 dibatasi 150, target nol/nonpositif menjadi 0, dan skor manual -1 menjadi 0. Metrik bebas bisa mempunyai aktual negatif; temuan menyangkut konsistensi rentang skor, bukan anggapan bahwa semua aktual negatif harus dilarang. Definisi rentang bisnis perlu ditegaskan bila ingin mengizinkan skor negatif.

**Lokasi source pada commit audit:**

- [backend/services/hr_kpi_service.py:31](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L31) — `return round(min(a / t, 1.5) * 100, 1)`.
- [backend/services/hr_kpi_service.py:21](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L21) — `return round(max(0.0, min(float(score), 150.0)), 1)`.
- [backend/schemas_hr_kpi.py:18](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_hr_kpi.py#L18) — `score: Optional[float] = None`.

```python
29:     if t <= 0:
30:         return 0.0
31:     return round(min(a / t, 1.5) * 100, 1)
32: 
33: 
34: async def submit_kpi(emp: Dict[str, Any], payload: Dict[str, Any], actor_name: str) -> Dict[str, Any]:
35:     metric = (payload.get("metric") or "").strip()
36:     if not metric:
37:         raise ValueError("Nama metrik KPI wajib diisi.")
```

**Bukti asli:** [evidence/repro/hr-kpi-projection90-results.json](evidence/repro/hr-kpi-projection90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| kpi.auto_score_lower_bound | 0 | -10.0 | observed_difference |

**Prompt agent development:**

Samakan aturan rentang evaluator otomatis dan manual sesuai definisi KPI yang disetujui. Pertahankan angka aktual asli; jangan mengubah aktual negatif menjadi nol untuk menutupi perhitungan. Jika rentang sengaja boleh negatif, sesuaikan kontrak, badge, ambang dan dokumentasi secara konsisten.

**Kriteria penerimaan untuk reviewer:**

Untuk kontrak 0–150, target100/aktual-10 menghasilkan skor0, aktual200 menghasilkan150. Uji target/aktual 0 dan negatif, manual vs otomatis, reset skor manual, bobot/rata-rata, rounding, nilai tidak finite dan tampilan badge.

## D4-BUD-THRESHOLD-01 — Ambang peringatan anggaran 0% berubah menjadi 85% pada laporan

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Finance → Aturan Anggaran → ambang peringatan → laporan vs pratinjau kontrol anggaran.

**Rantai kejadian:** Simpan warn_threshold_pct=0 → check_budget memberi peringatan → budget_vs_actual memberi status ok pada penggunaan20%.

**Letak kesalahan dan penyebab:** Fallback truthiness pada report memperlakukan nilai 0 yang sah sebagai missing lalu menggantinya dengan85. Evaluator check_budget membaca nol apa adanya.

**Dampak, hasil reproduksi, dan batas klaim:** Public schema dan set_rules mengizinkan 0–100. Fixture actual10/commitment20/budget150 memberi check.warning terisi pada ambang0, namun report row.status=ok. Angka actual/commitment/remaining pada kontrol normal benar; kesalahannya pada status/peringatan konfigurasi, bukan jumlah jurnal.

**Lokasi source pada commit audit:**

- [backend/services/budget_service.py:347](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L347) — `warn_pct = float(rules.get("warn_threshold_pct", 85.0) or 85.0)`.
- [backend/services/budget_service.py:475](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L475) — `near = out["used_pct_after"] is not None`.
- [backend/routers/budgets.py:35](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/budgets.py#L35) — `warn_threshold_pct: Optional[float] = Field(None, ge=0, le=100)`.

```python
345:     rules = await get_rules(entity_id_for_rules) if entity_id_for_rules else \
346:         {"entity_id": "", **DEFAULT_RULES, "is_default": True}
347:     warn_pct = float(rules.get("warn_threshold_pct", 85.0) or 85.0)
348: 
349:     rows: List[Dict[str, Any]] = []
350:     tot = {"budget": 0.0, "committed": 0.0, "actual": 0.0}
351:     per_dim: Dict[str, Dict[str, float]] = {}
352:     for b in budgets:
353:         dim = b.get("dimension") or DIM_ACCOUNT
```

**Bukti asli:** [evidence/repro/budget-ledger-policy90-results.json](evidence/repro/budget-ledger-policy90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| budget.zero_threshold_check_warning | true | true | pass |
| budget.zero_threshold_report_warning | "warning" | "ok" | observed_difference |

**Prompt agent development:**

Bedakan None/missing dari0 dan gunakan evaluator status/threshold bersama untuk report, preview dan enforcement. Terapkan pola yang sama untuk seluruh konfigurasi yang mengizinkan nol; jangan menaikkan batas minimum tanpa keputusan bisnis.

**Kriteria penerimaan untuk reviewer:**

Ambang0 tersimpan0 dan report/check memberi warning secara konsisten untuk contoh penggunaan positif. Uji0/85/100, empty/null, usage di bawah/tepat/di atas threshold, mode off/warn/block dan filter bulanan/tahunan.

