# Gelombang 3 — 23 temuan tambahan

Snapshot audit: `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Seluruh temuan memiliki counterexample; jenis bukti dan batas fixture dibedakan. Status tes negatif atau error suite lama tidak otomatis dianggap bug.

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

## D4-ASSET-01 — Penyusutan yang gagal mengunci periode sehingga retry tidak memperbaiki aset

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_service_fault_or_concurrency_counterexample`.

**Layar/alur:** Keuangan → Aset Tetap → jalankan penyusutan.

**Rantai kejadian:** Klaim periode → posting jurnal gagal → klaim tertinggal → retry skip → akumulasi/entri tetap0.

**Letak kesalahan dan penyebab:** Periode dimasukkan ke depreciation_periods sebelum jurnal dan register penyusutan selesai. Kegagalan tidak melepas klaim atau menyediakan status saga yang dapat dilanjutkan.

**Dampak, hasil reproduksi, dan batas klaim:** Fault satu kali hanya pada batas post_depreciation: public run500. Setelah batas normal dipulihkan, public retry200 tetapi posted0, accumulated0 dan tidak ada entri untuk periode itu. Kontrol proses normal memposting100 dan retry periode yang sudah selesai tidak menggandakan jurnal.

**Lokasi source pada commit audit:**

- [backend/services/fixed_asset_service.py:244](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L244) — `"depreciation_periods": {"$ne": period}`.
- [backend/services/fixed_asset_service.py:256](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L256) — `je = await gl_service.post_depreciation(`.
- [backend/services/gl_service.py:2286](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L2286) — `async def post_depreciation(`.

```python
242:         won = await db.fin_fixed_assets.find_one_and_update(
243:             {"id": a["id"], "status": a.get("status", "active"),
244:              "depreciation_periods": {"$ne": period}},
245:             {"$addToSet": {"depreciation_periods": period}},
246:             projection={"_id": 0, "id": 1})
247:         if not won:
248:             skipped += 1
249:             continue
250:         monthly = _monthly_amount(cost, salvage, life)
```

**Bukti asli:** [evidence/repro/assets-loans-lifecycle90-results.json](evidence/repro/assets-loans-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| FA90-failure-retry-posted | 1 | 0 | observed_difference |
| FA90-failure-retry-accumulated | 100 | 0.0 | observed_difference |
| FA90-failure-retry-entry-count | 1 | 0 | observed_difference |
| FA90-parallel-months-accumulated | 200 | 100.0 | observed_difference |
| FA90-parallel-months-book-value | 100 | 200.0 | observed_difference |
| FA90-parallel-months-count | 2 | 1 | observed_difference |
| ICL90-foreign-repayment-denied | 403 | 200 | observed_difference |
| ICL90-foreign-repayment-outstanding | 50 | 40.0 | observed_difference |
| ICL90-foreign-repayment-no-cash | 0 | 2 | observed_difference |
| ICL90-foreign-cancellation-denied | 403 | 200 | observed_difference |

**Prompt agent development:**

Buat operasi penyusutan dapat dipulihkan: preflight, operation ID per aset/periode, status started/GL posted/register applied/completed, dan resume yang idempoten. Jangan melepas klaim secara buta setelah jurnal mungkin terbentuk; bedakan kegagalan sebelum dan sesudah side effect.

**Kriteria penerimaan untuk reviewer:**

Fault sebelum posting, sesudah journal tersimpan, sebelum register, sebelum finalize: retry menghasilkan tepat1 jurnal+1 entri dan akumulasi100. Uji restart/timeout, periode tertutup, akun invalid, single-asset dan batch, duplicate same-period concurrency.

## D4-ASSET-02 — Penyusutan dua periode bersamaan membuat register aset tertinggal dari jurnal

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_service_fault_or_concurrency_counterexample`.

**Layar/alur:** Keuangan → Aset Tetap → register, nilai buku dan penyusutan.

**Rantai kejadian:** Dua periode membaca acc0 → keduanya klaim periode berbeda → dua entri100 → keduanya set acc100.

**Letak kesalahan dan penyebab:** CAS hanya melindungi period key masing-masing. Perhitungan akumulasi dan bulan memakai snapshot yang dibaca sebelum klaim, lalu disimpan dengan $set, sehingga update lintas periode dapat saling menimpa.

**Dampak, hasil reproduksi, dan batas klaim:** Aset300/life3: dua public run periode Jan dan Feb dengan barrier di batas jurnal menghasilkan2 entri penyusutan. Register menunjukkan accumulated100/book200/months1, seharusnya accumulated200/book100/months2. Kontrol run normal dan duplicate same-period tetap benar. Barrier menyinkronkan urutan; perhitungan asli tidak diganti.

**Lokasi source pada commit audit:**

- [backend/services/fixed_asset_service.py:261](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L261) — `new_acc = round(acc + amt, 2)`.
- [backend/services/fixed_asset_service.py:262](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L262) — `new_months = int(a.get("depreciated_months", 0)) + 1`.
- [backend/services/fixed_asset_service.py:274](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L274) — `"accumulated_depreciation": new_acc`.

```python
259:             dep_exp_acc=a.get("gl_account_dep_exp", gl_service.ACC_DEP_EXPENSE),
260:             acc_dep_acc=a.get("gl_account_acc_dep", gl_service.ACC_FA_ACCUM_DEP))
261:         new_acc = round(acc + amt, 2)
262:         new_months = int(a.get("depreciated_months", 0)) + 1
263:         new_book = round(cost - new_acc, 2)
264:         status = "fully_depreciated" if (new_acc >= depreciable - EPS or new_months >= life) else "active"
265:         await db.fin_depreciation_entries.insert_one({
266:             "id": new_id("depe"),
267:             "asset_id": a["id"], "asset_number": a.get("number", ""),
```

**Bukti asli:** [evidence/repro/assets-loans-lifecycle90-results.json](evidence/repro/assets-loans-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| FA90-failure-retry-posted | 1 | 0 | observed_difference |
| FA90-failure-retry-accumulated | 100 | 0.0 | observed_difference |
| FA90-failure-retry-entry-count | 1 | 0 | observed_difference |
| FA90-parallel-months-accumulated | 200 | 100.0 | observed_difference |
| FA90-parallel-months-book-value | 100 | 200.0 | observed_difference |
| FA90-parallel-months-count | 2 | 1 | observed_difference |
| ICL90-foreign-repayment-denied | 403 | 200 | observed_difference |
| ICL90-foreign-repayment-outstanding | 50 | 40.0 | observed_difference |
| ICL90-foreign-repayment-no-cash | 0 | 2 | observed_difference |
| ICL90-foreign-cancellation-denied | 403 | 200 | observed_difference |

**Prompt agent development:**

Serialisasikan mutasi per aset atau gunakan update atomik/optimistic version dengan resume idempoten per periode. Hindari snapshot stale; batas depreciable amount/salvage/life harus berlaku terhadap akumulasi final setelah semua operasi, termasuk disposal/capitalization.

**Kriteria penerimaan untuk reviewer:**

Jan/Feb concurrent:2 entri, akumulasi200, nilai buku100 dan2 bulan; GL-register-detail-summary harus merekonsiliasi. Uji last-month concurrent, salvage, disposal vs depreciation, amendment vs run, same-period retries dan interrupted batch.

## D4-ICLOAN-01 — Akun Finance dapat mengubah pinjaman entitas yang tidak ditugaskan kepadanya

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Keuangan → Antar Entitas → Pinjaman Uang; API repay/cancel.

**Rantai kejadian:** Finance hanyaA → detail pinjamanB/C ditolak → repayB/C diterima → kedua sisi kas dan saldo berubah.

**Letak kesalahan dan penyebab:** Mutating handlers memeriksa izin fitur tetapi tidak memagari dokumen pinjaman memakai konteks entitas. Layanan mengambil loan berdasarkan ID, tanpa verifikasi bahwa pihak transaksi berada dalam penugasan actor.

**Dampak, hasil reproduksi, dan batas klaim:** Akun Finance allowed_entity_ids=[A]: GET loan B/C404 sebagai kontrol. Public repay10 pada loan50 memberi200, outstanding40 dan2 transaksi kas baru. Public cancel draftB/C juga200. Akun manager tidak dipakai sebagai bukti bypass karena role itu memang diizinkan lintas entitas oleh desain sistem; hipotesis awal manager ditarik.

**Lokasi source pada commit audit:**

- [backend/routers/interco_loans.py:96](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/interco_loans.py#L96) — `async def repay_loan(`.
- [backend/routers/interco_loans.py:71](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/interco_loans.py#L71) — `async def get_loan(`.
- [backend/routers/interco_loans.py:109](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/interco_loans.py#L109) — `async def cancel_loan(`.
- [backend/services/interco_loan_service.py:200](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/interco_loan_service.py#L200) — `async def repay(`.

```python
94: 
95: @router.post("/interco/loans/{loan_id}/repay")
96: async def repay_loan(loan_id: str, payload: IntercoLoanRepay, request: Request) -> Dict[str, Any]:
97:     actor = await require_permission(request, "interco", "settle")
98:     try:
99:         res = await svc.repay(loan_id, actor, float(payload.amount or 0), payload.note)
100:     except (svc.LoanError, money.IntercoMoneyError) as exc:
101:         raise _fail(exc) from exc
102:     await audit(actor.get("name", ""), "interco_loan_repaid", "interco_loan",
```

**Bukti asli:** [evidence/repro/assets-loans-lifecycle90-results.json](evidence/repro/assets-loans-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| FA90-failure-retry-posted | 1 | 0 | observed_difference |
| FA90-failure-retry-accumulated | 100 | 0.0 | observed_difference |
| FA90-failure-retry-entry-count | 1 | 0 | observed_difference |
| FA90-parallel-months-accumulated | 200 | 100.0 | observed_difference |
| FA90-parallel-months-book-value | 100 | 200.0 | observed_difference |
| FA90-parallel-months-count | 2 | 1 | observed_difference |
| ICL90-foreign-repayment-denied | 403 | 200 | observed_difference |
| ICL90-foreign-repayment-outstanding | 50 | 40.0 | observed_difference |
| ICL90-foreign-repayment-no-cash | 0 | 2 | observed_difference |
| ICL90-foreign-cancellation-denied | 403 | 200 | observed_difference |

**Prompt agent development:**

Terapkan aturan akses yang sama untuk pasangan lender/borrower pada seluruh mutasi dan layer layanan bila dipanggil lewat jalur lain. Gunakan resolver dokumen/policy yang konsisten dengan GET dan penugasan, tanpa memblokir role lintas entitas yang sah. Audit disburse, repay, cancel, list/detail dan side effects.

**Kriteria penerimaan untuk reviewer:**

Finance hanyaA tidak dapat repay/cancel/disburse loanB/C; tidak ada perubahan saldo/kas/jurnal/timeline ketika ditolak. Lender/borrower yang sah dan manager/admin lintas entitas tetap bekerja; uji akses melalui kedua paired IDs, closed entity dan concurrency.

## D4-RFQ-01 — Award RFQ tetap membuat PO untuk item yang dinyatakan tidak tersedia

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Pembelian → RFQ → perbandingan supplier → Award & Buat PO.

**Rantai kejadian:** Quote availableFalse/price20 → compare tidak lengkap → full award hanya membaca harga → PO dibuat.

**Letak kesalahan dan penyebab:** Perbandingan dan supplier_total menolak baris unavailable, tetapi pemilihan harga award mengabaikan flag available. Sisa harga lama yang positif menjadi dasar PO walaupun supplier menyatakan tidak dapat memasok.

**Dampak, hasil reproduksi, dan batas klaim:** Public quote dua baris: L1 availableTrue/price10, L2 availableFalse/price20. Public compare completeFalse sebagai kontrol. Public award full tetap200 dan membuat1 PO yang mencakup L2. Kontrol quote kedua baris availableTrue memberi full PO50 dan split termurah menghasilkan2 PO total46. UI saat ini membentuk available dari harga; skenario flagFalse dengan retained price terutama kontrak API/data, bukan klaim pengguna UI dapat mengetik kombinasi itu.

**Lokasi source pada commit audit:**

- [backend/services/rfq_service.py:296](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfq_service.py#L296) — `def _price_of(sid: str, lid: str)`.
- [backend/services/rfq_service.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfq_service.py#L90) — `if ln.get("available", True) and float(ln.get("price", 0) or 0) > 0:`.
- [backend/routers/rfq.py:184](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L184) — `async def award(`.
- [frontend/src/features/purchasing/RFQDetailPanel.jsx:77](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/purchasing/RFQDetailPanel.jsx#L77) — `async function doAward()`.

```python
294:     grouped: Dict[str, List[Dict[str, Any]]] = {}
295: 
296:     def _price_of(sid: str, lid: str) -> float:
297:         s = sup_by_id.get(sid, {})
298:         for ln in s.get("lines", []):
299:             if ln["line_id"] == lid:
300:                 return float(ln.get("price", 0) or 0)
301:         return 0.0
302: 
```

**Bukti asli:** [evidence/repro/procurement-lifecycle90-results.json](evidence/repro/procurement-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| rfq.full_unavailable_rejected | 400 | 200 | observed_difference |
| rfq.full_unavailable_no_po | 0 | 1 | observed_difference |
| rfq.foreign_compare_denied | true | false | observed_difference |
| rfq.foreign_cancel_denied | true | false | observed_difference |
| rfq.foreign_state_preserved | "draft" | "cancelled" | observed_difference |

**Prompt agent development:**

Gunakan satu resolusi kelayakan quote untuk compare, rekomendasi dan award. Supplier/baris harus quoted, availableTrue dan harga valid. Cek validitas quote/masa berlaku serta duplicate line; line override harga tidak boleh memulihkan availability tanpa keputusan eksplisit yang tercatat.

**Kriteria penerimaan untuk reviewer:**

Full/line award atas unavailable ditolak sebelum PO/price-list/PR berubah; status RFQ dan saga tetap dapat diperbaiki. Quote valid full50/split46 tetap lolos. Uji harga lama positif, unavailable0, missing quote, expiry, override, duplicate quote lines dan multi-supplier partial failure.

## D4-RFQ-02 — Perbandingan dan pembatalan RFQ tidak mengikuti pembatasan entitas pada halaman detail

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Pembelian → RFQ → perbandingan harga dan aksi status.

**Rantai kejadian:** Finance hanyaKSC → detail RFQ entitaslain404 → compare200 → cancel200 dan status cancelled.

**Letak kesalahan dan penyebab:** GET detail memanggil entity_ctx/assert_entity_access. Compare dan beberapa mutasi langsung _get(id) setelah izin fitur, sehingga aturan penugasan dokumen tidak diterapkan konsisten.

**Dampak, hasil reproduksi, dan batas klaim:** Akun Finance ditugaskan hanya ent_ksc. RFQ fixture yang awalnya lahir dari producer publik diberi owner entitaslain yang memang ada. Detail ditolak403/404, tetapi compare diterima dan cancel200 mengubah draft menjadi cancelled. Izin fitur sengaja diberikan lewat matriks; role lintas entitas tidak dipakai untuk membuktikan penolakan.

**Lokasi source pada commit audit:**

- [backend/routers/rfq.py:56](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L56) — `return build_compare(await _get(rfq_id))`.
- [backend/routers/rfq.py:49](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L49) — `assert_entity_access(rfq, "rfqs", ctx)`.
- [backend/routers/rfq.py:205](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L205) — `async def cancel_rfq(`.
- [backend/routers/rfq.py:135](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L135) — `async def send_rfq(`.

```python
54: async def compare_rfq(rfq_id: str, request: Request) -> Dict[str, Any]:
55:     await require_permission(request, "rfq", "view")
56:     return build_compare(await _get(rfq_id))
57: 
58: 
59: @router.post("/rfqs")
60: async def create_rfq(payload: RFQCreate, request: Request) -> Dict[str, Any]:
61:     """Buat RFQ dari PR approved (tarik item) atau standalone manual."""
62:     actor = await require_permission(request, "rfq", "create")
```

**Bukti asli:** [evidence/repro/procurement-lifecycle90-results.json](evidence/repro/procurement-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| rfq.foreign_detail_denied_control | true | true | pass |
| rfq.foreign_compare_denied | true | false | observed_difference |
| rfq.foreign_cancel_denied | true | false | observed_difference |
| rfq.foreign_state_preserved | "draft" | "cancelled" | observed_difference |

**Prompt agent development:**

Gunakan _get_scoped atau guard bersama pada compare/send/quote/award/cancel serta validasi entitas saat create dari PR. Verifikasi scope sebelum state/price-list/PO/PR/saga/timeline berubah. Pertahankan akses role lintas entitas yang sah dan penugasan MD multi-entitas.

**Kriteria penerimaan untuk reviewer:**

Detail/compare dan semua mutasi harus menolak actor di luar penugasan; status dan seluruh side effects tidak berubah. Positive control entitas milik actor tetap berfungsi. Uji foreign PR→RFQ, explicit entity_id, supplier entity sharing, line scope dan kedua policy aktor multi-entitas/lintas entitas.

## D4-CB-01 — Pemeriksa kontrabon dapat memberi hasil bersih karena hanya memeriksa 2.000 dokumen pertama

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_scanner_or_migration_with_explicit_legacy_fixture`.

**Layar/alur:** Gate integritas kontrabon; cakupan validasi produksi/data lama.

**Rantai kejadian:** 2.000 kontrabon tanpa pelanggaran → dua kontrabon terakhir memakai bill sama → detector menghasilkan0 pelanggaran.

**Letak kesalahan dan penyebab:** Cursor dibatasi to_list(2000) tanpa pemeriksaan total/paginasi; dokumen di luar jendela tidak dievaluasi.

**Dampak, hasil reproduksi, dan batas klaim:** Fixture sengaja dibuat korup untuk menguji pemeriksa, bukan membuktikan producer publik dapat membuat kontrabon ganda. Pada dataset kecil duplicate aktif terdeteksi; cancelled dikecualikan. Pada2.002 live records, duplicate bill di tail terlewat dan detector memberi0.

**Lokasi source pada commit audit:**

- [backend/services/contra_bon_scan.py:24](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contra_bon_scan.py#L24) — `return await db[COLL].find(`.
- [backend/services/contra_bon_scan.py:29](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contra_bon_scan.py#L29) — `async def bills_in_multiple_contra_bons`.
- [scripts/verify_data_integrity.py:3642](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/scripts/verify_data_integrity.py#L3642) — `async def layer_contra_bon_invariants`.

```python
22: async def _live_contra_bons() -> List[Dict[str, Any]]:
23:     """Kontrabon yang masih 'memegang' dokumen (semua kecuali `cancelled`)."""
24:     return await db[COLL].find(
25:         {"status": {"$in": list(svc.HOLDING_STATUSES)}}, {"_id": 0}).to_list(2000)
26: 
27: 
28: # ── INV-CB-01 ────────────────────────────────────────────────────────────────
29: async def bills_in_multiple_contra_bons() -> List[Dict[str, Any]]:
30:     """Satu faktur supplier tidak boleh berada di dua kontrabon yang belum dibatalkan.
```

**Bukti asli:** [evidence/repro/contra-bon-invariants90-results.json](evidence/repro/contra-bon-invariants90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| contra.scale_duplicate_2002 | 1 | 0 | observed_difference |

**Prompt agent development:**

Iterasi seluruh cursor/aggregation atau pagination stabil; jika harus membatasi, tampilkan incomplete dan jangan meluluskan gate. Terapkan pada seluruh detector yang memakai _live_contra_bons, serta batas lain yang belum dibuktikan.

**Kriteria penerimaan untuk reviewer:**

Duplicate yang berada pada awal/tengah/akhir dari >2.000 data harus terdeteksi. Fixture valid tidak memberi false positive, cancelled dikecualikan. Laporkan scanned/total dan pastikan incomplete tidak boleh berstatus hijau.

## D4-UOM-BF-01 — Backfill jumlah roll memakai panjang daftar ID mentah, berbeda dari resolver roll nyata

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_scanner_or_migration_with_explicit_legacy_fixture`.

**Layar/alur:** Migrasi dua satuan → dokumen retur/transfer/SJ lama → kolom jumlah roll.

**Rantai kejadian:** roll_ids R1,R1,MISSING → helper actual-roll1 → backfill qty_rolls3.

**Letak kesalahan dan penyebab:** Backfill menganggap setiap elemen daftar mewakili satu roll, tanpa deduplikasi/verifikasi, sedangkan rolls_of_ids memakai count_documents atas ID nyata.

**Dampak, hasil reproduksi, dan batas klaim:** Terbukti pada fixture data lama yang sengaja memiliki referensi duplikat/hilang; tidak ada klaim producer normal menghasilkan referensi tersebut. Ini kegagalan alat pemulihan data untuk mendeteksi/menandai data lama tidak valid; hasil3 dapat terlihat sebagai angka roll pasti.

**Lokasi source pada commit audit:**

- [backend/services/dual_qty_service.py:169](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/dual_qty_service.py#L169) — `async def backfill(`.
- [backend/services/dual_qty_service.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/dual_qty_service.py#L129) — `async def rolls_of_ids`.
- [scripts/migrate_qty_rolls.py:54](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/scripts/migrate_qty_rolls.py#L54) — `backfill`.

```python
167: 
168: 
169: async def backfill(dbx, *, demo_plan: bool = False, dry_run: bool = False) -> Dict[str, int]:
170:     """Isi `qty_rolls` (dan `secondary_measures`) DARI ROLL NYATA — bukan menebak.
171: 
172:     Aturan (dan alasan tiap aturan):
173:       * `inventory_movements` : baris yang menunjuk satu `roll_id` = **1 roll**.
174:       * `wms_tasks`           : jumlah roll yang lahir dari tugas itu (`grn_task_id`).
175:       * `purchase_orders`     : `items[].received_rolls` = roll nyata ber-`po_id` + produk.
```

**Bukti asli:** [evidence/repro/quantity-provenance90-results.json](evidence/repro/quantity-provenance90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| backfill.dry_run_has_no_write | false | false | pass |
| backfill.dry_run_matches_write_counts | {"inventory_movements": 1, "wms_tasks": 1, "purchase_orders": 1, "sales_returns": 1, "purchase_returns": 1, "interco_returns": 1, "warehouse_transfers": 1, "shipments": 1, "makloon_orders": 1, "inventory_rolls": 1} | {"inventory_movements": 1, "wms_tasks": 1, "purchase_orders": 1, "sales_returns": 1, "purchase_returns": 1, "interco_returns": 1, "warehouse_transfers": 1, "shipments": 1, "makloon_orders": 1, "inventory_rolls": 1} | pass |
| backfill.movement_is_single_roll | 1 | 1 | pass |
| backfill.task_real_count | 2 | 2 | pass |
| backfill.received_real_count | 2 | 2 | pass |
| backfill.production_plan_not_guessed | false | false | pass |
| backfill.actual_weight | 12.346 | 12.346 | pass |
| backfill.preserve_existing_count | 7 | 7 | pass |
| backfill.no_rolls_no_task_guess | false | false | pass |
| backfill.shipment_actual_rolls | 2 | 2 | pass |

**Prompt agent development:**

Satukan derivasi jumlah roll dan aturan ID unik. Untuk referensi hilang/arsip yang tidak bisa dibuktikan, jangan menebak: laporkan conflict/incomplete dan butuh keputusan. Jangan mengganti jumlah historis sah tanpa bukti rekonsiliasi.

**Kriteria penerimaan untuk reviewer:**

Dry-run tidak menulis; duplikat tidak dihitung dua kali; dangling/archived references dilaporkan jelas. Dokumen historis valid tetap benar; migration berulang idempoten, qty_rolls yang sudah diketahui tidak ditimpa.

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

## D4-ALERT-WMS-01 — Notifikasi tugas WMS mencampur pesanan dua entitas yang memakai gudang sama

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** WMS multi-entitas/shared warehouse → scheduler ops_stalled → bell gudang.

**Rantai kejadian:** SO-A ownerKSC +SO-B ownerlain, warehouse/flow sama → satu bucket entityKSC berisi2 tugas dan nomorSO-B.

**Letak kesalahan dan penyebab:** Pengelompokan tidak memasukkan entity_id. Entitas bucket ditetapkan dari tugas pertama, sedangkan hitungan dan daftar order mencakup pemilik lain.

**Dampak, hasil reproduksi, dan batas klaim:** Pada dua business_entities yang nyata di fixture, original generator membuat satu notifikasi entitas pertama, memuat nomor pesanan kedua; owner kedua tidak mendapat kelompoknya sendiri. Ini selain salah hitung juga mengaburkan batas tugas entitas. Kontrol dua flow milik satu entitas menghasilkan dua kelompok dengan dedupe harian.

**Lokasi source pada commit audit:**

- [backend/services/alert_service.py:286](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L286) — `key = (t.get("warehouse_id", ""), t.get("flow_type", ""))`.
- [backend/services/alert_service.py:302](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L302) — `ref=f"task_stalled:{wid}:{flow}"`.
- [backend/services/alert_service.py:289](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L289) — `"entity_id": t.get("entity_id")`.

```python
284:     groups: Dict[tuple, Dict[str, Any]] = {}
285:     for t in tasks:
286:         key = (t.get("warehouse_id", ""), t.get("flow_type", ""))
287:         g = groups.setdefault(key, {"count": 0, "oldest": None, "orders": [],
288:                                     "warehouse_name": t.get("warehouse_name", ""),
289:                                     "entity_id": t.get("entity_id")})
290:         g["count"] += 1
291:         dt = _parse(t.get("created_at"))
292:         if dt and (g["oldest"] is None or dt < g["oldest"]):
```

**Bukti asli:** [evidence/repro/alert-numeric90-results.json](evidence/repro/alert-numeric90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| alerts.ops_shared_warehouse_separate_owners | 2 | 1 | observed_difference |
| alerts.ops_foreign_order_not_in_owner_notice | false | true | observed_difference |

**Prompt agent development:**

Kelompokkan berdasarkan entity_id+warehouse_id+flow dan masukkan entity pada ref/dedupe. Pertahankan gudang bersama, tentukan audience sesuai penugasan pengguna dan line/warehouse role; jangan mengandalkan nama gudang sebagai pemilik.

**Kriteria penerimaan untuk reviewer:**

Dua owner satu gudang menghasilkan notifikasi masing-masing dengan count/order sendiri. Actor entitasA tidak memperoleh nomorSO-B dari notifikasiA. User multi-entitas/lintas-entitas sah tetap dapat melihat kelompok yang diizinkan; rerun harian tidak duplikat.

## D4-PRICE-SCOPE-01 — Scope harga khusus berbeda antara detail, perubahan, harga efektif dan ringkasan

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Persetujuan Harga Khusus → daftar, statistik, detail dan keputusan.

**Rantai kejadian:** Sales dengan kemampuan custom hanyaA → detailB ditolak → patch/submit/approve/deleteB diterima; stats/effective juga membacaB.

**Letak kesalahan dan penyebab:** Sebagian handler hanya memeriksa permission dan requested_by. entity_ctx/assert_entity_access yang dipakai GET detail tidak diterapkan pada mutasi/resolver/statistik.

**Dampak, hasil reproduksi, dan batas klaim:** Original ASGI: user Sales onlyA diberi capability yang diuji. Create asing ditolak sebagai kontrol; foreign fixtureB ownerU disiapkan eksplisit. GET B ditolak, listA benar, tetapi PATCH/SUBMIT/DELETEB200; distinct approver onlyA menyetujuiB200; effectiveB mengembalikan hargaB dan statsA menghitung2 alih-alih1. Manager/admin cross-entity tidak dipakai sebagai bypass.

**Lokasi source pada commit audit:**

- [backend/routers/price_approvals.py:263](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L263) — `async def patch_price_approval(`.
- [backend/routers/price_approvals.py:182](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L182) — `async def price_approval_stats`.
- [backend/routers/price_approvals.py:157](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L157) — `async def effective_price`.
- [backend/routers/price_approvals.py:257](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L257) — `assert_entity_access(doc, "price_approvals", ctx)`.
- [backend/routers/price_approvals.py:331](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L331) — `async def approve_price_approval`.

```python
261: 
262: @router.patch("/price-approvals/{approval_id}")
263: async def patch_price_approval(approval_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
264:     user = await require_permission(request, "price_approval", "update")
265:     doc = await _get_or_404(approval_id)
266:     _ensure_owner_or_privileged(doc, user)
267:     if doc["status"] not in EDITABLE_STATUSES:
268:         raise HTTPException(status_code=409, detail=f"Pengajuan status '{doc['status']}' tidak dapat diubah")
269:     allowed = {"requested_price", "min_quantity", "reason", "valid_until"}
```

**Bukti asli:** [evidence/repro/price-approval-scope90-results.json](evidence/repro/price-approval-scope90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| price.foreign_create_rejected | true | true | pass |
| price.foreign_get_control | true | true | pass |
| price.stats_scope | 1 | 2 | observed_difference |
| price.foreign_patch_rejected | true | false | observed_difference |
| price.foreign_submit_rejected | true | false | observed_difference |
| price.foreign_approve_rejected | true | false | observed_difference |
| price.foreign_effective_hidden | false | true | observed_difference |
| price.foreign_delete_rejected | true | false | observed_difference |

**Prompt agent development:**

Pusatkan scoped document resolver, terapkan sebelum setiap read/mutation/attachment/status effect dan supersede. Effective/stats harus mengikuti active/allowed entity scope; permission fitur bukan izin semua dokumen. Pertahankan custom capabilities sah, SOD dan role cross-entity.

**Kriteria penerimaan untuk reviewer:**

Detail/list/effective/stats/mutasi sepakat pada scope; ditolak tanpa perubahan harga,status,customer-price,SO,supersede,notifikasi atau file. Own-entity lifecycle draft→evidence→submit→distinct approval→effective tetap lulus, minqty4/5 dan approved edit/delete guards tetap benar.

## D4-OD-LOCK-01 — Kegagalan pembaruan SKU meninggalkan harga OD terkunci dan pengulangan tidak dapat memulihkannya

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_service_fault_or_concurrency_counterexample`.

**Layar/alur:** Pesanan Khusus → keputusan pelanggan → kunci harga final → katalog SKU.

**Rantai kejadian:** Customer ACC → lockprice commitOD130 → DBwrite SKU gagal → SKU100 → retry sudahterkunci.

**Letak kesalahan dan penyebab:** Harga OD dan akhir claim dicatat sebelum pembaruan produk. Kegagalan di write produk tidak ditangani dengan resume/rollback; pengecekan awal locked menolak retry.

**Dampak, hasil reproduksi, dan batas klaim:** Fault hanya di boundary database products.update_one, bisnis asli tidak diganti. PersistedOD price_locked=True/final130, SKUprice100; retry gagal already-locked. Kontrol normal lock menghasilkanOD1300/SKU130, dan unlock memerlukanadmin+reason serta menolak bila PR/PO/SO sudah lahir. Pemulihan manual lewat unlock dapat diperlukan; bukan klaim tidak mungkin dipulihkan sama sekali.

**Lokasi source pada commit audit:**

- [backend/services/special_order_phase2.py:235](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/special_order_phase2.py#L235) — `_saga.finish_set({"pricing": pricing`.
- [backend/services/special_order_phase2.py:244](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/special_order_phase2.py#L244) — `await db.products.update_one({"id": pid_final}`.
- [backend/services/special_order_phase2.py:216](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/special_order_phase2.py#L216) — `Harga OD ini sudah dikunci.`.

```python
233:                       precondition={"price_locked": {"$ne": True}}, actor=actor.get("name", ""))
234:     _res = await db.special_orders.update_one({"id": od["id"], "price_locked": {"$ne": True}}, {
235:         **_saga.finish_set({"pricing": pricing, "final_price": pricing["final_unit_price"], "total_amount": pricing["total"],
236:                  "price_locked": True, "updated_at": now_iso(),
237:                  **({"linked_product_id": pv["product_id"], "linked_product_sku": pv["product_sku"]} if pv["product_id"] else {})}),
238:         "$push": {"status_history": {"status": od.get("status"), "timestamp": now_iso(), "user": actor.get("email", ""),
239:                                      "note": f"Harga final dikunci: {rupiah(pricing['final_unit_price'])}/{pricing['unit']} (kontrak {rupiah(pricing['cost_price'])} + margin {pricing['margin_pct']:g}%)"}}})
240:     if _res.matched_count == 0:
241:         raise ODError("Harga OD ini baru saja dikunci oleh pihak lain. Muat ulang.")
```

**Bukti asli:** [evidence/repro/special-order-chain90-results.json](evidence/repro/special-order-chain90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| od.latest_revision_blocks_old_winner | false | false | pass |
| od.decision_guard_locked | true | true | pass |
| od.lock_needs_acc | true | true | pass |
| od.lock_needs_winning_contract | true | true | pass |
| od.lock_total | 1300 | 1300.0 | pass |
| od.lock_sku_price | 130 | 130.0 | pass |
| od.lock_repeat_guard | true | true | pass |
| od.locked_preview_snapshot | 1300 | 1300.0 | pass |
| od.unlock_requires_admin | true | true | pass |
| od.unlock_requires_reason | true | true | pass |

**Prompt agent development:**

Gunakan saga/checkpoint yang selesai hanya setelah semua effect harga/SKU tersimpan, atau transaksi dengan recovery yang jelas. Retry harus mengenali partial commit dan menyelesaikannya sekali tanpa duplicateprocurement. Jangan mengubah snapshot dokumen historis melalui repairmassal.

**Kriteria penerimaan untuk reviewer:**

Fault sebelum/sesudah OD commit, SKUwrite dan autoPO: state konsisten atau pending dan dapat dipulihkan. Retry tidak ditolak ketika pekerjaan belum selesai; harga akhir OD/SKU/PR/PO konsisten, idempotent dan SOD/lock rules tetap berlaku.

## D4-COMM-BOUNDS-01 — Perubahan master komersial melewati batas angka dan dapat menghasilkan ongkos makloon negatif

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Barang Supplier dan Kontrak Supplier → perubahan data → simulasi tarif makloon.

**Rantai kejadian:** Create menolak tarif -5 → PATCH menerimanya → tariff-preview qty 10 menghasilkanamount -50; barang supplier PATCH harga/MOQ/lead negatifjuga diterima.

**Letak kesalahan dan penyebab:** Create schemas menetapkan ge/le, Patch optional types tidak mempertahankannya. Service patch tidak mengulangi validasi domain numerik; kalkulator menggunakan nilai tersimpan.

**Dampak, hasil reproduksi, dan batas klaim:** Original API kontrol create negative/percentage 101 → 422 dan normal create200. PATCH contract menerima tarif/mincharge/yield/MOQ/leadnegative serta shrinkage/tolerance/byproduct101. Tarif negatif memberi pratinjauamount -50. SupplierItem PATCH menerima harga/MOQ/lead-1 walaupun create menolak422 dan CSVharga-1 dinyatakaninvalid. Tidak ada klaim jurnal negatif sudah terposting dari kasus ini.

**Lokasi source pada commit audit:**

- [backend/schemas_contracts.py:62](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_contracts.py#L62) — `class SupplierContractPatch`.
- [backend/schemas_contracts.py:28](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_contracts.py#L28) — `class SupplierContractCreate`.
- [backend/schemas_supplier_items.py:41](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_supplier_items.py#L41) — `class SupplierItemPatch`.
- [backend/services/contract_service.py:246](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contract_service.py#L246) — `async def patch_contract`.
- [backend/services/supplier_item_service.py:232](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/supplier_item_service.py#L232) — `async def patch_item`.
- [backend/services/contract_service.py:530](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contract_service.py#L530) — `"amount": total`.

```python
60: 
61: 
62: class SupplierContractPatch(BaseModel):
63:     title: Optional[str] = None
64:     partner_name: Optional[str] = None
65:     process_type: Optional[str] = None
66:     product_id: Optional[str] = None
67:     input_product_id: Optional[str] = None
68:     tariff_basis: Optional[str] = None
```

**Bukti asli:** [evidence/repro/commercial-patch-bounds90-results.json](evidence/repro/commercial-patch-bounds90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| bounds.item_patch_reject_last_price | true | false | observed_difference |
| bounds.item_patch_reject_moq | true | false | observed_difference |
| bounds.item_patch_reject_lead_time_days | true | false | observed_difference |
| bounds.contract_patch_reject_tariff_rate | true | false | observed_difference |
| bounds.contract_patch_reject_min_charge | true | false | observed_difference |
| bounds.contract_patch_reject_shrinkage_pct | true | false | observed_difference |
| bounds.contract_patch_reject_tolerance_pct | true | false | observed_difference |
| bounds.contract_patch_reject_byproduct_pct | true | false | observed_difference |
| bounds.contract_patch_reject_yield_factor | true | false | observed_difference |
| bounds.contract_patch_reject_moq | true | false | observed_difference |

**Prompt agent development:**

Pertahankan constraint producer pada patch dan validasi service sebelum persist/calculation. Definisikan validator domain bersama bagi CRUD/import/snapshot/override. Data lama invalid harus diidentifikasi dan ditangani tanpa mengubah dokumen posted secara senyap.

**Kriteria penerimaan untuk reviewer:**

Invalid numericpatch ditolak400/422 dan DB tidak berubah. Normal patch tetap berfungsi; semua tarif/resultfinite dan valid. Uji negative, 0, percentage100/101, null/empty, currencyprecision, CSV/XLSX, contract override, mincharge, biaya tambahan dan seluruh consumer PR/PO/MKO/HPP.

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

## D4-BUD-EDIT-01 — Perubahan anggaran melewati keunikan periode/kunci dan batas tahun

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Finance → Anggaran → ubah tahun/bulan → kontrol PO dan laporan anggaran.

**Rantai kejadian:** Create dua anggaran Januari150 dan Februari200 untuk kunci yang sama → PATCH Februari menjadi Januari diterima → dua envelope pada kombinasi yang seharusnya tunggal; PATCH year1900 juga diterima.

**Letak kesalahan dan penyebab:** Create memeriksa duplikasi entity/year/month/dimension/key dan tahun 2000–2999. Update hanya memeriksa batas bulan dan amount, tidak memeriksa kombinasi hasil merge atau batas tahun; indeks unik komposit tidak ditemukan pada indeks bootstrap.

**Dampak, hasil reproduksi, dan batas klaim:** Original API menolak duplicate create dan tahun1900/3000. PATCH month menjadi1 pada anggaran Februari mengembalikan200 dan query DB menemukan dua anggaran Januari pada kunci yang sama; PATCH year1900 juga200. Laporan menjumlahkan setiap baris, sementara check_budget menggunakan find_one untuk envelope bulanan: duplicate membuat SSOT budget tidak lagi tunggal. Tidak diklaim ada PO over-budget yang benar-benar terposting pada skenario ini.

**Lokasi source pada commit audit:**

- [backend/services/budget_service.py:209](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L209) — `async def update_budget(`.
- [backend/services/budget_service.py:175](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L175) — `if year < 2000 or year > 2999:`.
- [backend/services/budget_service.py:183](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L183) — `dupe = await db.budgets.find_one(`.
- [backend/services/budget_service.py:434](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L434) — `monthly = await db.budgets.find_one(`.
- [backend/services/budget_service.py:352](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L352) — `for b in budgets:`.

```python
207: 
208: 
209: async def update_budget(budget_id: str, patch: Dict[str, Any],
210:                         scope: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
211:     q = {"id": budget_id, **(scope or {})}
212:     upd: Dict[str, Any] = {"updated_at": now_iso()}
213:     if patch.get("amount") is not None:
214:         amount = _r(patch["amount"])
215:         if amount <= 0:
```

**Bukti asli:** [evidence/repro/budget-ledger-policy90-results.json](evidence/repro/budget-ledger-policy90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| budget.patch_duplicate_rejected | true | false | observed_difference |
| budget.single_envelope_per_key | 1 | 2 | observed_difference |
| budget.patch_invalid_year_rejected | true | false | observed_difference |

**Prompt agent development:**

Validasi hasil merge patch dengan invariant create, termasuk rentang tahun dan keunikan komposit. Tambahkan constraint database yang sesuai setelah konflik lama direkonsiliasi; buat respons 400/409 yang dapat dipahami pengguna. Jangan diam-diam menjumlahkan atau menghapus anggaran konflik. Pastikan report dan check_budget memakai envelope kanonik yang sama.

**Kriteria penerimaan untuk reviewer:**

PATCH konflik ditolak dan kedua anggaran asli tetap utuh; year1900/3000 ditolak. Uji concurrent create/update, annual month0 dan monthly1–12, rename periode, filter entitas/dimensi, rollback kegagalan DB dan kesesuaian laporan vs enforcement PO.

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

## D4-RET-POLICY-01 — Deadline retur dapat berubah karena PO terbaru entitas lain dengan produk yang sama

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** Retur Jual → evaluasi kelayakan → policy link_to_supplier_window → deadline dan status eligible.

**Rantai kejadian:** SO A memakai roll dari PO A/supplierA (window30) → eligible pada hari kedua; PO terbaru B/supplierB pada SKU sama (window1, receipt lama) → deadline A berubah dan retur yang sama menjadi tidak eligible.

**Letak kesalahan dan penyebab:** Resolver linked-supplier memilih PO terbaru berdasarkan product_id dan status tanpa membatasi entitas atau menelusuri asal roll yang memenuhi SO. Proxy produk sama tidak setara dengan asal fisik barang yang diretur.

**Dampak, hasil reproduksi, dan batas klaim:** Original service dengan policy A dan roll milik A yang mengacu OWN-PO menghasilkan supplierSA dan eligibleTrue. Penambahan FOREIGN-PO milik B mengubah supplier menjadiSB, deadline dan eligibleFalse, meski SO/roll/PO A tidak berubah. Fixture provenance dinyatakan eksplisit; tidak diklaim seluruh producer normal menghasilkan hubungan salah atau bahwa browser telah diuji. Mode linked bersifat opsional; mode nonlinked tidak terdampak oleh jalur ini.

**Lokasi source pada commit audit:**

- [backend/services/return_policy_service.py:241](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L241) — `po = await db.purchase_orders.find_one(`.
- [backend/services/return_policy_service.py:242](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L242) — `"items.product_id": {"$in": product_ids}`.
- [backend/services/return_policy_service.py:299](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L299) — `deadline = min(d1, d2).isoformat()`.
- [backend/services/return_policy_service.py:327](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L327) — `blocked = bool(enforce and dl is not None and not within_window)`.

```python
239: 
240:     # Cari PO terbaru yang memuat produk-produk ini (sebagai proxy asal beli).
241:     po = await db.purchase_orders.find_one(
242:         {"items.product_id": {"$in": product_ids},
243:          "status": {"$in": ["receiving", "partial", "completed", "closed", "closed_short"]}},
244:         {"_id": 0}, sort=[("created_at", -1)])
245:     if not po or not po.get("supplier_id"):
246:         return {"deadline": "", "supplier_id": "", "window_days": window_fallback, "source": "none"}
247: 
```

**Bukti asli:** [evidence/repro/budget-ledger-policy90-results.json](evidence/repro/budget-ledger-policy90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| return_policy.foreign_unrelated_po_not_selected | "SA" | "SB" | observed_difference |
| return_policy.eligibility_not_changed_by_foreign_po | true | false | observed_difference |
| return_policy.deadline_not_changed_by_foreign_po | "2026-01-31T00:00:00+00:00" | "2025-12-02T00:00:00+00:00" | observed_difference |

**Prompt agent development:**

Telusuri source PO/receipt/supplier dari roll atau shipment yang benar-benar memenuhi SO, termasuk lineage intercompany. Untuk item bersumber majemuk, hitung deadline per asal dan jelaskan basis penggabungannya. Jangan memakai PO terbaru SKU sebagai sumber keputusan blokir. Jika provenance belum tersedia, tampilkan unresolved/advisory sesuai keputusan bisnis; jangan mengarang deadline.

**Kriteria penerimaan untuk reviewer:**

Menambah/mengubah PO yang tidak terkait, termasuk entitas lain dan PO baru SKU yang sama, tidak mengubah eligibility SO A. Uji mixed suppliers, partial shipment, intercompany chain, retur sebagian roll, supplier window0, missing provenance, import/local, tenant boundary dan mode linked/nonlinked.

