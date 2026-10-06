# Catatan lanjutan menuju 90% — checkpoint, bukan laporan selesai

Commit: `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Diperbarui: 2026-10-06T06:52:17.255417+00:00.

Cakupan runtime/startup: **59,069/72,221 statement (81.79%)**; **15,389/23,008 cabang (66.89%)**. Denominator tetap480 berkas. **Target90% belum tercapai.**

Cakupan eksekusi, hasil tes, dan akurasi bisnis merupakan tiga penilaian berbeda. Tes tiruan provider tidak membuktikan akurasi AI/hardware; fixture data lama yang sengaja korup tidak membuktikan producer normal menghasilkan data korup. ZIP checkpoint78 sebelumnya belum mencakup seluruh lanjutan ini.

## 17 temuan tambahan yang sudah direproduksi

### D4-SIM-01 · P2 · Simulator menyatakan 3-way match lolos saat barang belum diterima

**Alur/layar:** Pusat Pengaturan → simulator pencocokan Tagihan Supplier. Simulator received_qty0/billed_qty10 → selisih dianggap0 → LOLOS; evaluator bill operasional → blocked.

**Penyebab:** Cabang pembagi nol mengubah selisih kuantitas menjadi nol. Simulator memakai rumus tersendiri yang berbeda dari evaluator transaksi sebenarnya.

**Bukti dan batas klaim:** Public simulate menerima received0/billed10 dengan toleransi qty0 dan memberi verdict ok. Evaluator layanan vendor bill asli untuk kondisi yang sama memblokir. Kontrol received100/billed100 lolos; billed101/received100 melampaui toleransi ditolak. Ini informasi konfigurasi yang salah, bukan bukti tagihan operasional ini otomatis lolos.

**Lokasi kode:**

- [backend/services/config_simulator.py:192](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/config_simulator.py:192) — `dq = ((bill_q - recv_q) / recv_q * 100) if recv_q else 0`.
- [backend/services/vendor_bill_service.py:96](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/vendor_bill_service.py:96) — `def evaluate_match(`.
- [backend/routers/config.py:160](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/config.py:160) — `async def simulate(`.

**Reproduksi:** [config-bank-oracles90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/config-bank-oracles90-results.json).

**Prompt agent development:**

Gunakan evaluator aturan yang sama untuk simulator dan transaksi, dengan konteks simulasi eksplisit. Saat received0/billed>0, hasil harus menyatakan belum ada penerimaan dan blokir sesuai basis matching. Jangan mengisi delta0 untuk menghindari pembagi nol.

**Kriteria validasi:**

received0/billed10/tolerance0 harus block; nol/nol dijelaskan tanpa NaN. Uji partial receipt, billing cumulatif, qty sisa, tolerance, harga, basis ordered vs received, return/short-close. Hasil simulator dan evaluator harus sesuai untuk input bisnis ekuivalen.

### D4-BANK-01 · P2 · Tanggal kalender yang tidak mungkin masuk ke data rekonsiliasi bank

**Alur/layar:** Keuangan → Rekonsiliasi Bank → preview/import mutasi. Tanggal mentah → format string ISO tanpa validasi kalender → preview valid → import persisten.

**Penyebab:** Parser hanya merapikan komponen tanggal untuk beberapa format. Validasi import memeriksa tanggal tidak kosong, sehingga string tanggal yang bukan tanggal kalender tetap disimpan.

**Bukti dan batas klaim:** Public preview dan import menerima serta menyimpan 2026-02-30, 2026-99-99, 2026-13-01. Kontrol 2026-02-28 diparsing dan disimpan dengan benar. Ini merusak dimensi periode dan kualitas source rekonsiliasi; skenario tidak melakukan transfer dana atau posting GL.

**Lokasi kode:**

- [backend/services/bank_statement_parser.py:179](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/bank_statement_parser.py:179) — `return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"`.
- [backend/services/bank_recon_service.py:348](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/bank_recon_service.py:348) — `async def import_lines(`.
- [backend/routers/bank_reconciliation.py:38](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/bank_reconciliation.py:38) — `class StatementLineIn(`.

**Reproduksi:** [config-bank-oracles90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/config-bank-oracles90-results.json).

**Prompt agent development:**

Validasi semua jalur tanggal lewat satu parser kalender yang ketat, termasuk model input langsung. Kembalikan error per baris untuk tanggal tidak sah; jangan normalize ke bulan berikutnya. Pertahankan year_hint dan locale yang eksplisit; tanggal ambigu membutuhkan format yang dipilih.

**Kriteria validasi:**

Tanggal mustahil ditolak preview/import/direct-line; leap-year 2024-02-29 sah dan 2026-02-29 ditolak. Uji ISO, compact, dd/mm, mm/dd, teks bulan, MT940, OFX, timestamp, tahun kosong, whitespace, error parsial dan filter periode.

### D4-BANK-02 · P2 · Parser MT940 tidak membaca kode pembalikan transaksi RC dan RD

**Alur/layar:** Keuangan → Rekonsiliasi Bank → import MT940. Field61 D100 + RD100 → hanya D terbaca → preview/import saldo bersih keluar100.

**Penyebab:** Regex menerima huruf C/D lalu R opsional. Format pembalikan MT940 memakai RC/RD, dengan R sebelum C/D; arah transaksi pembalikan juga harus dibalik.

**Bukti dan batas klaim:** Kontrol mutasi C/D biasa lolos. Statement sintetik D100 dan RD100 menghasilkan hanya1 mutasi dengan error1 dan net keluar100, padahal pasangan itu net0. Public import mengimpor baris biasa dan mengembalikan error pembalikan; error terlihat, sehingga temuan tidak menyebut hilangnya baris secara diam-diam. Standar primer: UniCredit MT94x General V1.1, Field61 (https://www.unicredit.ro/content/dam/cee2020-pws-ro/DocumentePDF/DocumenteCIB/MT94x_General_V1.1.pdf).

**Lokasi kode:**

- [backend/services/bank_statement_parser.py:416](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/bank_statement_parser.py:416) — `(?P<mark>[CD])R?`.
- [backend/routers/bank_reconciliation.py:202](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/bank_reconciliation.py:202) — `async def import_file(`.

**Reproduksi:** [config-bank-oracles90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/config-bank-oracles90-results.json).

**Prompt agent development:**

Parse debit/credit marker sebagai D, C, RC, RD sesuai format; RC berarti debit dan RD berarti credit. Pertahankan error per baris dan status import parsial yang jelas. Rekonsiliasikan opening/movement/closing balance sebelum pengguna menganggap file lengkap.

**Kriteria validasi:**

D100+RD100 menghasilkan2 baris/net0; C100+RC100 juga0. Uji funds-code, entry date, references, :86:, multiple statements, malformed marker, duplicate import, saldo akhir dan kebijakan partial vs atomic.

Dasar kode reversal MT940: [UniCredit MT94x General V1.1, Field61](https://www.unicredit.ro/content/dam/cee2020-pws-ro/DocumentePDF/DocumenteCIB/MT94x_General_V1.1.pdf). Error parsir memang ditampilkan; klaimnya bukan kehilangan data tanpa peringatan.

### D4-ASSET-01 · P1 · Penyusutan yang gagal mengunci periode sehingga retry tidak memperbaiki aset

**Alur/layar:** Keuangan → Aset Tetap → jalankan penyusutan. Klaim periode → posting jurnal gagal → klaim tertinggal → retry skip → akumulasi/entri tetap0.

**Penyebab:** Periode dimasukkan ke depreciation_periods sebelum jurnal dan register penyusutan selesai. Kegagalan tidak melepas klaim atau menyediakan status saga yang dapat dilanjutkan.

**Bukti dan batas klaim:** Fault satu kali hanya pada batas post_depreciation: public run500. Setelah batas normal dipulihkan, public retry200 tetapi posted0, accumulated0 dan tidak ada entri untuk periode itu. Kontrol proses normal memposting100 dan retry periode yang sudah selesai tidak menggandakan jurnal.

**Lokasi kode:**

- [backend/services/fixed_asset_service.py:244](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/fixed_asset_service.py:244) — `"depreciation_periods": {"$ne": period}`.
- [backend/services/fixed_asset_service.py:256](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/fixed_asset_service.py:256) — `je = await gl_service.post_depreciation(`.
- [backend/services/gl_service.py:2286](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/gl_service.py:2286) — `async def post_depreciation(`.

**Reproduksi:** [assets-loans-lifecycle90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/assets-loans-lifecycle90-results.json).

**Prompt agent development:**

Buat operasi penyusutan dapat dipulihkan: preflight, operation ID per aset/periode, status started/GL posted/register applied/completed, dan resume yang idempoten. Jangan melepas klaim secara buta setelah jurnal mungkin terbentuk; bedakan kegagalan sebelum dan sesudah side effect.

**Kriteria validasi:**

Fault sebelum posting, sesudah journal tersimpan, sebelum register, sebelum finalize: retry menghasilkan tepat1 jurnal+1 entri dan akumulasi100. Uji restart/timeout, periode tertutup, akun invalid, single-asset dan batch, duplicate same-period concurrency.

### D4-ASSET-02 · P1 · Penyusutan dua periode bersamaan membuat register aset tertinggal dari jurnal

**Alur/layar:** Keuangan → Aset Tetap → register, nilai buku dan penyusutan. Dua periode membaca acc0 → keduanya klaim periode berbeda → dua entri100 → keduanya set acc100.

**Penyebab:** CAS hanya melindungi period key masing-masing. Perhitungan akumulasi dan bulan memakai snapshot yang dibaca sebelum klaim, lalu disimpan dengan $set, sehingga update lintas periode dapat saling menimpa.

**Bukti dan batas klaim:** Aset300/life3: dua public run periode Jan dan Feb dengan barrier di batas jurnal menghasilkan2 entri penyusutan. Register menunjukkan accumulated100/book200/months1, seharusnya accumulated200/book100/months2. Kontrol run normal dan duplicate same-period tetap benar. Barrier menyinkronkan urutan; perhitungan asli tidak diganti.

**Lokasi kode:**

- [backend/services/fixed_asset_service.py:261](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/fixed_asset_service.py:261) — `new_acc = round(acc + amt, 2)`.
- [backend/services/fixed_asset_service.py:262](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/fixed_asset_service.py:262) — `new_months = int(a.get("depreciated_months", 0)) + 1`.
- [backend/services/fixed_asset_service.py:274](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/fixed_asset_service.py:274) — `"accumulated_depreciation": new_acc`.

**Reproduksi:** [assets-loans-lifecycle90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/assets-loans-lifecycle90-results.json).

**Prompt agent development:**

Serialisasikan mutasi per aset atau gunakan update atomik/optimistic version dengan resume idempoten per periode. Hindari snapshot stale; batas depreciable amount/salvage/life harus berlaku terhadap akumulasi final setelah semua operasi, termasuk disposal/capitalization.

**Kriteria validasi:**

Jan/Feb concurrent:2 entri, akumulasi200, nilai buku100 dan2 bulan; GL-register-detail-summary harus merekonsiliasi. Uji last-month concurrent, salvage, disposal vs depreciation, amendment vs run, same-period retries dan interrupted batch.

### D4-ICLOAN-01 · P1 · Akun Finance dapat mengubah pinjaman entitas yang tidak ditugaskan kepadanya

**Alur/layar:** Keuangan → Antar Entitas → Pinjaman Uang; API repay/cancel. Finance hanyaA → detail pinjamanB/C ditolak → repayB/C diterima → kedua sisi kas dan saldo berubah.

**Penyebab:** Mutating handlers memeriksa izin fitur tetapi tidak memagari dokumen pinjaman memakai konteks entitas. Layanan mengambil loan berdasarkan ID, tanpa verifikasi bahwa pihak transaksi berada dalam penugasan actor.

**Bukti dan batas klaim:** Akun Finance allowed_entity_ids=[A]: GET loan B/C404 sebagai kontrol. Public repay10 pada loan50 memberi200, outstanding40 dan2 transaksi kas baru. Public cancel draftB/C juga200. Akun manager tidak dipakai sebagai bukti bypass karena role itu memang diizinkan lintas entitas oleh desain sistem; hipotesis awal manager ditarik.

**Lokasi kode:**

- [backend/routers/interco_loans.py:96](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/interco_loans.py:96) — `async def repay_loan(`.
- [backend/routers/interco_loans.py:71](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/interco_loans.py:71) — `async def get_loan(`.
- [backend/routers/interco_loans.py:109](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/interco_loans.py:109) — `async def cancel_loan(`.
- [backend/services/interco_loan_service.py:200](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/interco_loan_service.py:200) — `async def repay(`.

**Reproduksi:** [assets-loans-lifecycle90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/assets-loans-lifecycle90-results.json).

**Prompt agent development:**

Terapkan aturan akses yang sama untuk pasangan lender/borrower pada seluruh mutasi dan layer layanan bila dipanggil lewat jalur lain. Gunakan resolver dokumen/policy yang konsisten dengan GET dan penugasan, tanpa memblokir role lintas entitas yang sah. Audit disburse, repay, cancel, list/detail dan side effects.

**Kriteria validasi:**

Finance hanyaA tidak dapat repay/cancel/disburse loanB/C; tidak ada perubahan saldo/kas/jurnal/timeline ketika ditolak. Lender/borrower yang sah dan manager/admin lintas entitas tetap bekerja; uji akses melalui kedua paired IDs, closed entity dan concurrency.

### D4-RFQ-01 · P1 · Award RFQ tetap membuat PO untuk item yang dinyatakan tidak tersedia

**Alur/layar:** Pembelian → RFQ → perbandingan supplier → Award & Buat PO. Quote availableFalse/price20 → compare tidak lengkap → full award hanya membaca harga → PO dibuat.

**Penyebab:** Perbandingan dan supplier_total menolak baris unavailable, tetapi pemilihan harga award mengabaikan flag available. Sisa harga lama yang positif menjadi dasar PO walaupun supplier menyatakan tidak dapat memasok.

**Bukti dan batas klaim:** Public quote dua baris: L1 availableTrue/price10, L2 availableFalse/price20. Public compare completeFalse sebagai kontrol. Public award full tetap200 dan membuat1 PO yang mencakup L2. Kontrol quote kedua baris availableTrue memberi full PO50 dan split termurah menghasilkan2 PO total46. UI saat ini membentuk available dari harga; skenario flagFalse dengan retained price terutama kontrak API/data, bukan klaim pengguna UI dapat mengetik kombinasi itu.

**Lokasi kode:**

- [backend/services/rfq_service.py:296](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/rfq_service.py:296) — `def _price_of(sid: str, lid: str)`.
- [backend/services/rfq_service.py:90](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/rfq_service.py:90) — `if ln.get("available", True) and float(ln.get("price", 0) or 0) > 0:`.
- [backend/routers/rfq.py:184](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/rfq.py:184) — `async def award(`.
- [frontend/src/features/purchasing/RFQDetailPanel.jsx:77](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/frontend/src/features/purchasing/RFQDetailPanel.jsx:77) — `async function doAward()`.

**Reproduksi:** [procurement-lifecycle90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/procurement-lifecycle90-results.json).

**Prompt agent development:**

Gunakan satu resolusi kelayakan quote untuk compare, rekomendasi dan award. Supplier/baris harus quoted, availableTrue dan harga valid. Cek validitas quote/masa berlaku serta duplicate line; line override harga tidak boleh memulihkan availability tanpa keputusan eksplisit yang tercatat.

**Kriteria validasi:**

Full/line award atas unavailable ditolak sebelum PO/price-list/PR berubah; status RFQ dan saga tetap dapat diperbaiki. Quote valid full50/split46 tetap lolos. Uji harga lama positif, unavailable0, missing quote, expiry, override, duplicate quote lines dan multi-supplier partial failure.

### D4-RFQ-02 · P1 · Perbandingan dan pembatalan RFQ tidak mengikuti pembatasan entitas pada halaman detail

**Alur/layar:** Pembelian → RFQ → perbandingan harga dan aksi status. Finance hanyaKSC → detail RFQ entitaslain404 → compare200 → cancel200 dan status cancelled.

**Penyebab:** GET detail memanggil entity_ctx/assert_entity_access. Compare dan beberapa mutasi langsung _get(id) setelah izin fitur, sehingga aturan penugasan dokumen tidak diterapkan konsisten.

**Bukti dan batas klaim:** Akun Finance ditugaskan hanya ent_ksc. RFQ fixture yang awalnya lahir dari producer publik diberi owner entitaslain yang memang ada. Detail ditolak403/404, tetapi compare diterima dan cancel200 mengubah draft menjadi cancelled. Izin fitur sengaja diberikan lewat matriks; role lintas entitas tidak dipakai untuk membuktikan penolakan.

**Lokasi kode:**

- [backend/routers/rfq.py:56](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/rfq.py:56) — `return build_compare(await _get(rfq_id))`.
- [backend/routers/rfq.py:49](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/rfq.py:49) — `assert_entity_access(rfq, "rfqs", ctx)`.
- [backend/routers/rfq.py:205](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/rfq.py:205) — `async def cancel_rfq(`.
- [backend/routers/rfq.py:135](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/rfq.py:135) — `async def send_rfq(`.

**Reproduksi:** [procurement-lifecycle90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/procurement-lifecycle90-results.json).

**Prompt agent development:**

Gunakan _get_scoped atau guard bersama pada compare/send/quote/award/cancel serta validasi entitas saat create dari PR. Verifikasi scope sebelum state/price-list/PO/PR/saga/timeline berubah. Pertahankan akses role lintas entitas yang sah dan penugasan MD multi-entitas.

**Kriteria validasi:**

Detail/compare dan semua mutasi harus menolak actor di luar penugasan; status dan seluruh side effects tidak berubah. Positive control entitas milik actor tetap berfungsi. Uji foreign PR→RFQ, explicit entity_id, supplier entity sharing, line scope dan kedua policy aktor multi-entitas/lintas entitas.

### D4-CB-01 · P2 · Pemeriksa kontrabon dapat memberi hasil bersih karena hanya memeriksa 2.000 dokumen pertama

**Alur/layar:** Gate integritas kontrabon; cakupan validasi produksi/data lama. 2.000 kontrabon tanpa pelanggaran → dua kontrabon terakhir memakai bill sama → detector menghasilkan0 pelanggaran.

**Penyebab:** Cursor dibatasi to_list(2000) tanpa pemeriksaan total/paginasi; dokumen di luar jendela tidak dievaluasi.

**Bukti dan batas klaim:** Fixture sengaja dibuat korup untuk menguji pemeriksa, bukan membuktikan producer publik dapat membuat kontrabon ganda. Pada dataset kecil duplicate aktif terdeteksi; cancelled dikecualikan. Pada2.002 live records, duplicate bill di tail terlewat dan detector memberi0.

**Lokasi kode:**

- [backend/services/contra_bon_scan.py:24](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/contra_bon_scan.py:24) — `return await db[COLL].find(`.
- [backend/services/contra_bon_scan.py:29](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/contra_bon_scan.py:29) — `async def bills_in_multiple_contra_bons`.
- [scripts/verify_data_integrity.py:3642](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/scripts/verify_data_integrity.py:3642) — `async def layer_contra_bon_invariants`.

**Reproduksi:** [contra-bon-invariants90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/contra-bon-invariants90-results.json).

**Prompt agent development:**

Iterasi seluruh cursor/aggregation atau pagination stabil; jika harus membatasi, tampilkan incomplete dan jangan meluluskan gate. Terapkan pada seluruh detector yang memakai _live_contra_bons, serta batas lain yang belum dibuktikan.

**Kriteria validasi:**

Duplicate yang berada pada awal/tengah/akhir dari >2.000 data harus terdeteksi. Fixture valid tidak memberi false positive, cancelled dikecualikan. Laporkan scanned/total dan pastikan incomplete tidak boleh berstatus hijau.

### D4-UOM-BF-01 · P2 · Backfill jumlah roll memakai panjang daftar ID mentah, berbeda dari resolver roll nyata

**Alur/layar:** Migrasi dua satuan → dokumen retur/transfer/SJ lama → kolom jumlah roll. roll_ids R1,R1,MISSING → helper actual-roll1 → backfill qty_rolls3.

**Penyebab:** Backfill menganggap setiap elemen daftar mewakili satu roll, tanpa deduplikasi/verifikasi, sedangkan rolls_of_ids memakai count_documents atas ID nyata.

**Bukti dan batas klaim:** Terbukti pada fixture data lama yang sengaja memiliki referensi duplikat/hilang; tidak ada klaim producer normal menghasilkan referensi tersebut. Ini kegagalan alat pemulihan data untuk mendeteksi/menandai data lama tidak valid; hasil3 dapat terlihat sebagai angka roll pasti.

**Lokasi kode:**

- [backend/services/dual_qty_service.py:169](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/dual_qty_service.py:169) — `async def backfill(`.
- [backend/services/dual_qty_service.py:129](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/dual_qty_service.py:129) — `async def rolls_of_ids`.
- [scripts/migrate_qty_rolls.py:54](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/scripts/migrate_qty_rolls.py:54) — `backfill`.

**Reproduksi:** [quantity-provenance90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/quantity-provenance90-results.json).

**Prompt agent development:**

Satukan derivasi jumlah roll dan aturan ID unik. Untuk referensi hilang/arsip yang tidak bisa dibuktikan, jangan menebak: laporkan conflict/incomplete dan butuh keputusan. Jangan mengganti jumlah historis sah tanpa bukti rekonsiliasi.

**Kriteria validasi:**

Dry-run tidak menulis; duplikat tidak dihitung dua kali; dangling/archived references dilaporkan jelas. Dokumen historis valid tetap benar; migration berulang idempoten, qty_rolls yang sudah diketahui tidak ditimpa.

### D4-RET-CHAIN-01 · P2 · Ringkasan fisik rantai retur menjumlahkan barang berlainan satuan menjadi satu angka

**Alur/layar:** Retur → perjalanan barang → posisi barang yang masih ditahan. Owner sama:100yard kain +5kg barang lain → satu langkah held berlabel105yard.

**Penyebab:** Bucket hanya berdasarkan pemilik dan memakai satuan dari roll pertama, kemudian menjumlahkan length_remaining tanpa pemisahan satuan.

**Bukti dan batas klaim:** Pada fixture linked-roll dua produk, ringkasan satu owner menunjukkan105yard; tidak dapat ditafsirkan sebagai panjang fisik. Source records100yard dan5kg tidak berubah. Kontrol rantai sama satuan dan redaksi lintas entitas lulus; browser/hardware tidak dibuktikan oleh probe ini.

**Lokasi kode:**

- [backend/services/return_chain_service.py:223](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/return_chain_service.py:223) — `held.setdefault(`.
- [backend/services/return_chain_service.py:224](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/return_chain_service.py:224) — `row["qty"]`.
- [backend/services/return_chain_service.py:159](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/return_chain_service.py:159) — `"unit"`.

**Reproduksi:** [quantity-provenance90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/quantity-provenance90-results.json).

**Prompt agent development:**

Pisahkan agregasi berdasarkan pemilik+satuan, dan produk bila konteks tampilan memerlukannya. Konversi hanya lewat UoM yang sah dengan jejak; jangan menjumlahkan kg dan yard. Lengkapi struktur response agar UI menampilkan setiap kelompok tanpa parsing teks.

**Kriteria validasi:**

100yard +5kg harus tampil sebagai100yard dan5kg. Same-unit sums tetap benar, redaksi informasi entitas lain tetap bekerja, rollcount dan complete-chain memakai definisi yang konsisten.

### D4-ALERT-DATE-01 · P2 · Peringatan AP menyebut jatuh tempo hari ini sudah terlambat satu hari

**Alur/layar:** Scheduler → notifikasi tagihan supplier jatuh tempo. bill_date tanggal kalender +NET30 =hari ini00:00UTC → now siang → timedelta.days=-1 → critical LEWAT1hari.

**Penyebab:** Selisih datetime dibulatkan ke bawah oleh .days, sementara jatuh tempo dokumen merupakan tanggal kalender.

**Bukti dan batas klaim:** Public source fields valid berupa tanggal YYYY-MM-DD. Original alert generator memberi critical/LEWAT1hari pada due-date yang sama dengan hari pengujian. Kontrol tanggal3hari mendatang/3hari lewat dan tagihan paid/draft lulus.

**Lokasi kode:**

- [backend/services/alert_service.py:144](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/alert_service.py:144) — `left = (due - now).days`.
- [backend/services/alert_service.py:120](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/alert_service.py:120) — `async def job_ap_due`.
- [backend/services/alert_service.py:150](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/alert_service.py:150) — `overdue = left < 0`.

**Reproduksi:** [alert-numeric90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/alert-numeric90-results.json).

**Prompt agent development:**

Gunakan definisi hari dan zona waktu bisnis yang konsisten untuk tanggal dokumen, bukan usia24jam yang dibulatkan ke bawah. Pusatkan due-date/day-delta untuk AP board, aging dan scheduler.

**Kriteria validasi:**

Jatuh tempo hari ini =HARI INI/warning/0hari; besok=1; kemarin=1hari terlambat. Uji UTC vs zona waktu bisnis, cutoff malam, term override perentitas dan tahun kabisat.

### D4-ALERT-AMT-01 · P2 · Peringatan utang menampilkan nominal penuh meskipun pembayaran sebagian sudah tercatat

**Alur/layar:** Pembayaran supplier → saldo AP → notifikasi jatuh tempo. Tagihan100, amount_paid70, statusposted → peringatan jatuh tempo tetap menampilkan100.

**Penyebab:** Query tidak membawa amount_paid/remaining, kemudian isi peringatan memakai grand_total tanpa menghitung saldo.

**Bukti dan batas klaim:** Original alert body memakai100 pada partial-payment fixture70; saldo yang perlu ditagih/dibayar30. Statuspaid dikecualikan dengan benar sebagai kontrol. Jika nominal dokumen sengaja ditampilkan, ia harus diberi label dan saldo30 tetap jelas, bukan memberi kesan100 perlu dibayar.

**Lokasi kode:**

- [backend/services/alert_service.py:124](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/alert_service.py:124) — `"supplier_id": 1, "supplier_name": 1, "entity_id": 1`.
- [backend/services/alert_service.py:157](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/alert_service.py:157) — `_rp(b.get('grand_total'))`.
- [backend/routers/vendor_bills.py:97](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/vendor_bills.py:97) — `"amount_paid"`.

**Reproduksi:** [alert-numeric90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/alert-numeric90-results.json).

**Prompt agent development:**

Ambil outstanding dari SSOT yang sama dengan AP aging/pembayaran/kontrabon. Jika tampilkan gross, paid, deduction dan balance, labeli masing-masing. Jangan menghitung ulang dari payments yang voided tanpa aturan yang sama.

**Kriteria validasi:**

100-70 → saldo30 pada peringatan; full payment tidak membuat peringatan; void/payment reversal/deductions/makloon claims dan term override harus konsisten dengan AP ledger.

### D4-ALERT-WMS-01 · P1 · Notifikasi tugas WMS mencampur pesanan dua entitas yang memakai gudang sama

**Alur/layar:** WMS multi-entitas/shared warehouse → scheduler ops_stalled → bell gudang. SO-A ownerKSC +SO-B ownerlain, warehouse/flow sama → satu bucket entityKSC berisi2 tugas dan nomorSO-B.

**Penyebab:** Pengelompokan tidak memasukkan entity_id. Entitas bucket ditetapkan dari tugas pertama, sedangkan hitungan dan daftar order mencakup pemilik lain.

**Bukti dan batas klaim:** Pada dua business_entities yang nyata di fixture, original generator membuat satu notifikasi entitas pertama, memuat nomor pesanan kedua; owner kedua tidak mendapat kelompoknya sendiri. Ini selain salah hitung juga mengaburkan batas tugas entitas. Kontrol dua flow milik satu entitas menghasilkan dua kelompok dengan dedupe harian.

**Lokasi kode:**

- [backend/services/alert_service.py:286](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/alert_service.py:286) — `key = (t.get("warehouse_id", ""), t.get("flow_type", ""))`.
- [backend/services/alert_service.py:302](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/alert_service.py:302) — `ref=f"task_stalled:{wid}:{flow}"`.
- [backend/services/alert_service.py:289](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/alert_service.py:289) — `"entity_id": t.get("entity_id")`.

**Reproduksi:** [alert-numeric90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/alert-numeric90-results.json).

**Prompt agent development:**

Kelompokkan berdasarkan entity_id+warehouse_id+flow dan masukkan entity pada ref/dedupe. Pertahankan gudang bersama, tentukan audience sesuai penugasan pengguna dan line/warehouse role; jangan mengandalkan nama gudang sebagai pemilik.

**Kriteria validasi:**

Dua owner satu gudang menghasilkan notifikasi masing-masing dengan count/order sendiri. Actor entitasA tidak memperoleh nomorSO-B dari notifikasiA. User multi-entitas/lintas-entitas sah tetap dapat melihat kelompok yang diizinkan; rerun harian tidak duplikat.

### D4-PRICE-SCOPE-01 · P1 · Scope harga khusus berbeda antara detail, perubahan, harga efektif dan ringkasan

**Alur/layar:** Persetujuan Harga Khusus → daftar, statistik, detail dan keputusan. Sales dengan kemampuan custom hanyaA → detailB ditolak → patch/submit/approve/deleteB diterima; stats/effective juga membacaB.

**Penyebab:** Sebagian handler hanya memeriksa permission dan requested_by. entity_ctx/assert_entity_access yang dipakai GET detail tidak diterapkan pada mutasi/resolver/statistik.

**Bukti dan batas klaim:** Original ASGI: user Sales onlyA diberi capability yang diuji. Create asing ditolak sebagai kontrol; foreign fixtureB ownerU disiapkan eksplisit. GET B ditolak, listA benar, tetapi PATCH/SUBMIT/DELETEB200; distinct approver onlyA menyetujuiB200; effectiveB mengembalikan hargaB dan statsA menghitung2 alih-alih1. Manager/admin cross-entity tidak dipakai sebagai bypass.

**Lokasi kode:**

- [backend/routers/price_approvals.py:263](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/price_approvals.py:263) — `async def patch_price_approval(`.
- [backend/routers/price_approvals.py:182](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/price_approvals.py:182) — `async def price_approval_stats`.
- [backend/routers/price_approvals.py:157](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/price_approvals.py:157) — `async def effective_price`.
- [backend/routers/price_approvals.py:257](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/price_approvals.py:257) — `assert_entity_access(doc, "price_approvals", ctx)`.
- [backend/routers/price_approvals.py:331](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/price_approvals.py:331) — `async def approve_price_approval`.

**Reproduksi:** [price-approval-scope90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/price-approval-scope90-results.json).

**Prompt agent development:**

Pusatkan scoped document resolver, terapkan sebelum setiap read/mutation/attachment/status effect dan supersede. Effective/stats harus mengikuti active/allowed entity scope; permission fitur bukan izin semua dokumen. Pertahankan custom capabilities sah, SOD dan role cross-entity.

**Kriteria validasi:**

Detail/list/effective/stats/mutasi sepakat pada scope; ditolak tanpa perubahan harga,status,customer-price,SO,supersede,notifikasi atau file. Own-entity lifecycle draft→evidence→submit→distinct approval→effective tetap lulus, minqty4/5 dan approved edit/delete guards tetap benar.

### D4-OD-LOCK-01 · P1 · Kegagalan pembaruan SKU meninggalkan harga OD terkunci dan pengulangan tidak dapat memulihkannya

**Alur/layar:** Pesanan Khusus → keputusan pelanggan → kunci harga final → katalog SKU. Customer ACC → lockprice commitOD130 → DBwrite SKU gagal → SKU100 → retry sudahterkunci.

**Penyebab:** Harga OD dan akhir claim dicatat sebelum pembaruan produk. Kegagalan di write produk tidak ditangani dengan resume/rollback; pengecekan awal locked menolak retry.

**Bukti dan batas klaim:** Fault hanya di boundary database products.update_one, bisnis asli tidak diganti. PersistedOD price_lockedTrue/final130, SKUprice100; retry gagal already-locked. Kontrol normal lock menghasilkanOD1300/SKU130, dan unlock memerlukanadmin+reason serta menolak bila PR/PO/SO sudah lahir. Pemulihan manual lewat unlock dapat diperlukan; bukan klaim tidak mungkin dipulihkan sama sekali.

**Lokasi kode:**

- [backend/services/special_order_phase2.py:235](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/special_order_phase2.py:235) — `_saga.finish_set({"pricing": pricing`.
- [backend/services/special_order_phase2.py:244](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/special_order_phase2.py:244) — `await db.products.update_one({"id": pid_final}`.
- [backend/services/special_order_phase2.py:216](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/special_order_phase2.py:216) — `Harga OD ini sudah dikunci.`.

**Reproduksi:** [special-order-chain90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/special-order-chain90-results.json).

**Prompt agent development:**

Gunakan saga/checkpoint yang selesai hanya setelah semua effect harga/SKU tersimpan, atau transaksi dengan recovery yang jelas. Retry harus mengenali partial commit dan menyelesaikannya sekali tanpa duplicateprocurement. Jangan mengubah snapshot dokumen historis melalui repairmassal.

**Kriteria validasi:**

Fault sebelum/sesudah OD commit, SKUwrite dan autoPO: state konsisten atau pendingrecoverable. Retry tidak ditolak ketika pekerjaan belum selesai; final OD/SKU/PRPOprice konsisten, idempotent dan SOD/lock rules tetapberlaku.

### D4-COMM-BOUNDS-01 · P1 · Perubahan master komersial melewati batas angka dan dapat menghasilkan ongkos makloon negatif

**Alur/layar:** Barang Supplier dan Kontrak Supplier → perubahan data → simulasi tarif makloon. Create menolaktarif-5 → PATCH menerimanya → tariff-preview qty10 menghasilkanamount-50; barang supplier PATCHharga/MOQ/lead negatifjuga diterima.

**Penyebab:** Create schemas menetapkan ge/le, Patch optional types tidak mempertahankannya. Service patch tidak mengulangi validasi numericdomain; kalkulator menggunakan nilai tersimpan.

**Bukti dan batas klaim:** Original API kontrol create negative/percentage101422 dan normal create200. PATCH contract menerima tarif/mincharge/yield/MOQ/leadnegative serta shrinkage/tolerance/byproduct101. Tarif negatif memberi pratinjauamount-50. SupplierItem PATCH menerima harga/MOQ/lead-1 walaupun create menolak422 dan CSVharga-1 dinyatakaninvalid. Tidak ada klaim jurnal negatif sudah terposting dari kasus ini.

**Lokasi kode:**

- [backend/schemas_contracts.py:62](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/schemas_contracts.py:62) — `class SupplierContractPatch`.
- [backend/schemas_contracts.py:28](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/schemas_contracts.py:28) — `class SupplierContractCreate`.
- [backend/schemas_supplier_items.py:41](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/schemas_supplier_items.py:41) — `class SupplierItemPatch`.
- [backend/services/contract_service.py:246](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/contract_service.py:246) — `async def patch_contract`.
- [backend/services/supplier_item_service.py:232](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/supplier_item_service.py:232) — `async def patch_item`.
- [backend/services/contract_service.py:530](C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/contract_service.py:530) — `"amount": total`.

**Reproduksi:** [commercial-patch-bounds90-results.json](C:/Users/abc/Documents/Codex/2026-09-28/sya/outputs/data-flow-audit-2026-10-05/latest/repro/commercial-patch-bounds90-results.json).

**Prompt agent development:**

Pertahankan constraint producer pada patch dan validasi service sebelum persist/calculation. Definisikan validator domain bersama bagi CRUD/import/snapshot/override. Data lama invalid harus diidentifikasi dan ditangani tanpa mengubah dokumen posted secara senyap.

**Kriteria validasi:**

Invalid numericpatch ditolak400/422 dan DBtidakberubah. Normal patch tetapberfungsi; semua tarif/resultfinite dan valid. Uji negative, 0, percentage100/101, null/empty, currencyprecision, CSV/XLSX, contract override, mincharge, biaya tambahan dan seluruh consumer PR/PO/MKO/HPP.

## Pengujian kontrol tambahan

OCR:67 observasi lulus dengan native mock provider; dua jalur PDF belum diuji karena PyMuPDF belum tersedia dan upaya instalasi mengalami batas lingkungan/TLS. Penerimaan API fase2:6 tes lulus; OCR API fase4:3 tes lulus; aturan DN:9 lulus; packing-list fase6:10 lulus. Sampling native:66 pemeriksaan lulus dengan penyesuaian input pelaksana wajib yang tercatat. Makloon lini native:35 pemeriksaan lulus. Ini tidak berarti semua suite lama hijau.

Label/master/tarif:134 observasi, dua hipotesis penolakan label masih diperiksa; keduanya belum dicatat sebagai bug. Tes lama dengan fixture yang tidak tersedia, arti scope manager yang disengaja, serta helper list gudang bersama yang memang tidak memvalidasi keberadaan owner dipisahkan dari temuan produk.

## Pekerjaan tersisa

Target90% statement dan90% cabang belum terpenuhi. Audit lanjutan menargetkan fungsi dengan gap tercatat dalam function-gaps90.json; browser numerik, RFID fisik/printer, dan provider AI nyata belum diverifikasi. Paket final, register serta prompt fase perlu dibangun ulang setelah seluruh temuan dan bukti dinormalisasi.
