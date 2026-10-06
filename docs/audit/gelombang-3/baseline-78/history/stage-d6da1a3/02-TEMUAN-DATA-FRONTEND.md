# Audit sumber data, angka dan tampilan frontend

Semua permalink dikunci pada commit yang diaudit. Expected pada gap definisi memakai makna label; keputusan bisnis yang berbeda harus didokumentasikan dan dilabelkan, bukan diasumsikan. Bukti function-level JavaScript tidak setara uji React di browser.

## D4-STOCK-01 — Nilai dan kecepatan stok terhitung dua kali ketika pemilik berbagi SKU dan gudang

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/stock_analytics_service.py:137](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/stock_analytics_service.py#L137).

**Tampilan / rantai terkait:** Stock Analytics: nilai persediaan, sold_qty_window, fast/slow/dead · Intercompany / multi-owner → balances → analitik stok.

**Penyebab:** Roll dan movement diagregasikan menurut product_id + warehouse_id tanpa owner_entity_id, lalu hasil gabungan ditambahkan lagi untuk setiap balance pemilik. On-hand balance sendiri benar; nilai dan velocity salah.

**Dampak dan batas interpretasi:** Dua pemilik: A 10×10 dan B 20×20 seharusnya bernilai 500, tampil 1000. Penjualan 3+7 menjadi 20, bukan 10. Klasifikasi fast/slow/dead dan prioritas pembelian ikut dapat berubah.

- `D4-STOCK-01-value` — expected `500`; actual `1000.0`; `observed_difference`.
- `D4-STOCK-01-velocity` — expected `10`; actual `20.0`; `observed_difference`.
- `D4-STOCK-01-onhand-control` — expected `30`; actual `30.0`; `pass`.

```python
 134:         resolve_list_scope("inventory_movements", mv_query, ctx, entity_id),
 135:         {"_id": 0, "product_id": 1, "warehouse_id": 1, "timestamp": 1, "quantity": 1, "movement_type": 1}
 136:     ).to_list(20000)
 137:     # seg key = (product, warehouse) → recency/velocity penjualan
 138:     last_sale: Dict[tuple, datetime] = {}
 139:     sold_window: Dict[tuple, float] = {}
 140:     for m in movements:
 141:         if m.get("movement_type") not in SALE_MOVEMENT_TYPES:
 142:             continue
 143:         key = (m.get("product_id"), m.get("warehouse_id"))
 144:         dt = _parse_ts(m.get("timestamp"))
```

**Prompt perbaikan:**

> Periksa `D4-STOCK-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan grain product + warehouse + owner sampai tahap agregasi akhir. Jangan join aggregate dengan grain yang lebih kasar ke beberapa balance lalu menjumlahkannya lagi. Terapkan pola yang sama untuk movement, oldest-age dan WAC. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** SKU/gudang sama dengan dua pemilik: qty30, nilai500 dan sold10; filter A=100/3, B=400/7. Tambahkan gudang kedua dan movement reversal; grouped total harus sama dengan penjumlahan partisi yang sah.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-STOCK-02 — Filter kategori tidak diterapkan pada bucket umur stok

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/stock_analytics_service.py:175](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/stock_analytics_service.py#L175).

**Tampilan / rantai terkait:** Stock Analytics: filter kategori vs chart aging · Master kategori → stok fisik → chart umur.

**Penyebab:** Aging diakumulasi sebelum row product diperiksa terhadap category. Tabel kategori woven sudah difilter, bucket aging masih berisi kategori lain.

**Dampak dan batas interpretasi:** Fixture woven bernilai100, knitting400: memilih woven menghasilkan aging500. Manajer membandingkan dua visual dengan cakupan berbeda.

- `D4-STOCK-02-filter` — expected `100`; actual `500.0`; `observed_difference`.

```python
 172:             seg_oldest_age[key] = age
 173:         b = _age_bucket(age)
 174:         aging[b]["qty"] += length
 175:         aging[b]["value"] += value
 176: 
 177:     # ── Agregasi per PRODUK (lintas gudang di scope) ──────────────────────────
 178:     prod_rows: Dict[str, Dict[str, Any]] = {}
 179:     for b in balances:
 180:         pid = b.get("product_id")
 181:         prod = products.get(pid, {})
 182:         if category and prod.get("category") != category:
```

**Prompt perbaikan:**

> Periksa `D4-STOCK-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bentuk product whitelist/filter yang sama sebelum mengambil roll, balance dan movement. Semua KPI/chart harus memakai filter yang sama, atau labelkan secara eksplisit jika global. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Filter woven: total rows100 = sum aging100; filter knitting400. Uji kategori kosong, SKU tanpa kategori dan kombinasi entitas/gudang.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-STOCK-03 — Nilai persediaan analitik mengabaikan landed cost

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/stock_analytics_service.py:166](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/stock_analytics_service.py#L166).

**Tampilan / rantai terkait:** Stock Analytics: nilai stok · Receiving → landed cost → roll valuation → analitik.

**Penyebab:** Valuasi memakai base_unit_cost meskipun unit_cost roll sudah memuat landed cost. Basis ini berbeda dengan nilai penuh costing/GL; tampilan nilai persediaan tidak menyatakan hanya biaya dasar.

**Dampak dan batas interpretasi:** Roll10, biaya dasar10, biaya penuh12: tabel nilai100, biaya persediaan penuh120. Rekonsiliasi dengan laporan biaya penuh tidak cocok.

- `D4-STOCK-03-landed` — expected `120`; actual `100.0`; `observed_difference`.

```python
 163:             continue
 164:         key = (r.get("product_id"), r.get("warehouse_id"))
 165:         length = float(r.get("length_remaining", 0) or 0)
 166:         cost = float(r.get("base_unit_cost", 0) or 0)
 167:         value = length * cost
 168:         seg_value[key] = seg_value.get(key, 0.0) + value
 169:         dt = _parse_ts(r.get("created_at")) or _parse_ts((r.get("acquired") or {}).get("date"))
 170:         age = (now - dt).days if dt else 9999
 171:         if key not in seg_oldest_age or age > seg_oldest_age[key]:
 172:             seg_oldest_age[key] = age
 173:         b = _age_bucket(age)
```

**Prompt perbaikan:**

> Periksa `D4-STOCK-03` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tetapkan kontrak nilai persediaan: tampilkan biaya penuh dari sumber biaya kanonis; bila perlu pisahkan dasar, landed dan total. Jangan menjumlahkan landed dua kali. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Roll10×12 menghasilkan120, split dasar100 + landed20. Uji voucher landed apply/void dan per-entitas. Jika bisnis memilih base-only, label dan rekonsiliasi harus menyatakan basis tersebut.

**Hubungan dengan catatan lain:** D4-STOCK-01

## D4-STOCK-04 — Tanggal roll tanpa timezone dapat menjatuhkan laporan umur stok

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_legacy_compatibility.

**Letak:** [backend/services/stock_analytics_service.py:33](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/stock_analytics_service.py#L33).

**Tampilan / rantai terkait:** Stock Analytics aging · Import/legacy roll → parsing tanggal → laporan.

**Penyebab:** Parser mengembalikan datetime naive untuk string YYYY-MM-DD, lalu dikurangkan dari now yang timezone-aware.

**Dampak dan batas interpretasi:** Satu roll legacy/import created_at date-only menghasilkan TypeError. Ini bukan klaim bahwa create roll normal menghasilkan tanggal tersebut; producer normal menggunakan timestamp ISO.

- `D4-STOCK-04-date-only` — expected `null`; actual `"TypeError: can't subtract offset-naive and offset-aware datetimes"`; `observed_difference`.

```python
  30: ]
  31: 
  32: 
  33: def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
  34:     if not ts:
  35:         return None
  36:     try:
  37:         return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
  38:     except Exception:
  39:         return None
  40: 
```

**Prompt perbaikan:**

> Periksa `D4-STOCK-04` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Normalisasi timezone pada boundary parsing dan tentukan kebijakan tanggal legacy. Jangan mengubah data historis diam-diam tanpa aturan timezone yang disetujui. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Date-only, ISO dengan offset, Z, kosong dan tanggal invalid ditangani deterministik tanpa exception server; aging hari diperiksa di batas WIB.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FIN-01 — Control Tower menggabungkan AR semua entitas ketika parameter entitas dihilangkan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/finance_analytics.py:68](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/routers/finance_analytics.py#L68).

**Tampilan / rantai terkait:** Finance Tower: outstanding, overdue, working capital, per-entity BI · Entity context → GL/AP/AR → tower.

**Penyebab:** Scope journal menggunakan konteks aktif, tetapi ent=None diteruskan ke aging_report, dan comparison memakai semua allowed_entity_ids. Scope komponen dalam satu respons berbeda.

**Dampak dan batas interpretasi:** Header aktif A dengan hak A+B: tanpa query param AR1000; explicit entity_id=A AR100. GL/AP bisa tetap A. Working capital dan perbandingan tidak punya cakupan konsisten. UI yang selalu mengirim A tidak otomatis terdampak jalur default ini.

- `D4-FIN-01-tower` — expected `{"omitted": 100, "explicit": 100}`; actual `{"omitted": 1000.0, "explicit": 100.0}`; `observed_difference`.

```python
  65:     ctx = await entity_ctx(request)
  66:     scope = resolve_list_scope("journal_entries", {}, ctx, entity_id)
  67:     ent = entity_id if entity_id and entity_id != "all" else None
  68:     comp_ids = [entity_id] if ent else list(ctx.allowed_entity_ids)
  69:     return await tower.finance_tower(scope=scope, entity_id=ent, entity_ids=comp_ids)
```

**Prompt perbaikan:**

> Periksa `D4-FIN-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Resolve effective scope sekali dan teruskan ke setiap service. Bedakan active, selected dan all secara eksplisit. All harus tetap dibatasi allowed entity set dan tidak memakai None ambigu. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Default/header A sama dengan explicit A; B dan all memiliki angka terpisah yang benar. Rekonsiliasi cash+AR−AP dalam scope identik. Uji allowed subset.

**Hubungan dengan catatan lain:** D4-SALES-02

## D4-SALES-01 — Target penjualan dan penagihan tidak mengikuti scope entitas

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_force_service.py:155](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/sales_force_service.py#L155).

**Tampilan / rantai terkait:** Sales Home / Sales Force: target, achievement, komisi tier · Target entitas → KPI scoped → denominator target.

**Penyebab:** Lookup target hanya sales_id dan period, tanpa entity_id. Target A dapat menjadi pembagi KPI B. Probe menggunakan satu target sah di A, tidak mengasumsikan public API mampu membuat dua target paralel yang tidak didukung.

**Dampak dan batas interpretasi:** B tidak punya target namun memperoleh100 dari A. Achievement dan ambang insentif tier dapat salah walaupun numerator KPI sudah benar.

- `D4-SALES-01-target-scope` — expected `0`; actual `100.0`; `observed_difference`.

```python
 152:     return total
 153: 
 154: 
 155: async def _target_sales_for(sales_id: str, period: str) -> float:
 156:     """Target PENJUALAN (omzet) dalam periode — terpisah dari target penagihan."""
 157:     targets = await db.sales_targets.find({"sales_id": sales_id}, {"_id": 0}).to_list(400)
 158:     return sum(float(t.get("target_sales_amount") or 0) for t in targets if _period_contains(period, t.get("period", "")))
 159: 
 160: 
 161: async def _scheme_for(sales_id: str, period: str) -> Dict[str, Any]:
 162:     """Skema insentif: exact period -> skema terbaru sales -> default tiers."""
```

**Prompt perbaikan:**

> Periksa `D4-SALES-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan kontrak target per-entity/global; selaraskan schema, uniqueness/upsert dan query untuk target_sales serta target_collection. Nilai tidak dikonfigurasi harus dibedakan dari nol. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Target A100; B tidak ada → B tidak memakai100. A/B/all, period month/quarter/year, fallback legacy dan tier boundary diuji tanpa penggandaan target.

**Hubungan dengan catatan lain:** D4-SALES-03

## D4-SALES-02 — Sales Home masih menampilkan order dan piutang lintas entitas di kartu pelanggan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/home_service.py:59](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/home_service.py#L59).

**Tampilan / rantai terkait:** Sales Home: pelanggan, AR, recent_orders · Customer master → SO entity → credit → home.

**Penyebab:** Home memfilter customer menurut A, tetapi memanggil compute_customer_credit tanpa entity dan mengambil recent SO customer tanpa entity. Perbaikan KPI di sales_force tidak menyelesaikan consumer home ini.

**Dampak dan batas interpretasi:** Customer A mempunyai SO A100 dan SO B700: kartu A outstanding800, seharusnya100; recent_orders berisi SO B. Dalam model pelanggan lintas entitas ini bukan pelanggaran producer, tetapi consumer tidak membatasi dokumen.

- `D4-SALES-02-recent-orders` — expected `false`; actual `true`; `observed_difference`.
- `D4-SALES-02-credit-cards` — expected `100`; actual `800.0`; `observed_difference`.

```python
  56:     customers = await db.customers.find(cust_filter, {"_id": 0}).to_list(2000)
  57:     cust_rows: List[Dict[str, Any]] = []
  58:     for c in customers:
  59:         cc = await compute_customer_credit(c)
  60:         cust_rows.append({
  61:             "id": c["id"], "name": c.get("name", ""),
  62:             "credit_limit": cc["credit_limit"], "ar_outstanding": cc["ar_outstanding"],
  63:             "overdue_amount": cc["overdue_amount"], "status": cc["status"],
  64:         })
  65:     cust_rows.sort(key=lambda r: r["overdue_amount"], reverse=True)
  66:     collections = [r for r in cust_rows if r["overdue_amount"] > 0][:8]
```

**Prompt perbaikan:**

> Periksa `D4-SALES-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Teruskan effective entity ke credit helper dan query recent orders. Selaraskan home/KPI/aging sehingga konteks aktif bermakna sama, serta lindungi all dengan allowed scope. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Home A AR100 dan hanya SO A; Home B700; all800 bila diizinkan. Customer dengan assigned-sales berubah dan SO tim lintas entitas tidak menghasilkan salah atribusi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-SALES-03 — Komisi per-SKU memasukkan SO tim sales milik entitas lain

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_force_service.py:253](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/sales_force_service.py#L253).

**Tampilan / rantai terkait:** Sales Force: incentive, commission history dan accrual · SO sales_team → payment → incentive rate → payroll/finance liability.

**Penyebab:** Query komisi OR customer assigned / sales_team tidak menambahkan entity_id pada SO. KPI dan rate scoped A, tetapi basis commission dapat berasal dari B.

**Dampak dan batas interpretasi:** SO B paid900 dengan9unit, sales S100% dan rate A1: KPI collected A0, insentif9. Angka ini dapat dipakai proses accrual; bukan hanya chart kosmetik.

- `D4-SALES-03-commission-entity` — expected `{"commission": 0, "collected_basis": 0}`; actual `{"commission": 9.0, "collected_basis": 0.0}`; `observed_difference`.

```python
 250:     return per_unit, float(cfg.get("discount_factor", 1.0) or 0)  # tier_factor
 251: 
 252: 
 253: async def _compute_commission_per_sku(
 254:     sales_id: str, period: str, entity_id: Optional[str], settings: Dict[str, Any]
 255: ) -> Dict[str, Any]:
 256:     """Engine per-SKU, 3 faktor, margin-aware, on-collection (EPIC4).
 257: 
 258:     Untuk tiap order, fraksi terbayar = Σpembayaran-dalam-periode / grand_total (≤1).
 259:     Per line: qty_terbayar = base_quantity × fraksi; komisi = qty × per_unit × factor,
 260:     di-cap oleh margin (margin_cap_pct% × margin line terbayar; pakai WAC EPIC3).
```

**Prompt perbaikan:**

> Periksa `D4-SALES-03` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan satu eligible-order scope untuk KPI, collection allocation dan komisi. Query OR attribution harus dibungkus scope entity/status/period. Hitung cost per SO owner; jangan rate A mengalikan transaksi B. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** A tanpa SO memperoleh0 walau S masuk tim B. A/B/all, shared customer, split team, partial receipt, return/void dan accrual ulang harus memenuhi konservasi serta idempotensi.

**Hubungan dengan catatan lain:** D4-SALES-01

## D4-FIN-02 — Forecast kas memakai basis AR dan termin berbeda dari AR kanonis

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/cashflow_forecast_service.py:66](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/cashflow_forecast_service.py#L66).

**Tampilan / rantai terkait:** Finance Cashflow Forecast: inflow, due bucket, projected cash · Payment profile/SO terms → outstanding AR → cash forecast.

**Penyebab:** NON_AR_METHODS didefinisikan tetapi tidak dipakai, projection tidak memuat payment_profile_method. Due date dihitung dari default pelanggan terkini, mengabaikan payment_term_days snapshot SO; term0 juga berubah30 karena or30.

**Dampak dan batas interpretasi:** SO tunai unpaid200 menjadi inflow AR200. SO tempo dengan snapshot90hari/default customer30diproyeksikan60hari terlalu cepat. Risiko optimisme likuiditas dan bucket overdue salah.

- `D4-FIN-02-cash-order-as-ar` — expected `0`; actual `200.0`; `observed_difference`.
- `D4-FIN-02-order-terms` — expected `"2027-01-03"`; actual `"2026-11-04"`; `observed_difference`.

```python
  63: 
  64:     # Peta term_days per customer utk estimasi jatuh tempo AR.
  65:     cust_rows = await db.customers.find({}, {"_id": 0, "id": 1, "payment_profile": 1}).to_list(20000)
  66:     term_map = {c["id"]: int((c.get("payment_profile") or {}).get("term_days", 30) or 30)
  67:                 for c in cust_rows}
  68: 
  69:     buckets: Dict[str, Dict[str, Any]] = {
  70:         k: {"key": k, "label": lbl, "inflow": 0.0, "outflow": 0.0}
  71:         for k, lbl, _lo, _hi in BUCKETS
  72:     }
  73:     ar_items: List[Dict[str, Any]] = []
```

**Prompt perbaikan:**

> Periksa `D4-FIN-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Reuse sumber AR kanonis untuk eligibility, net outstanding, method dan due date. Forecast boleh punya skenario sendiri hanya jika dipisahkan dari confirmed receivables dan diberi label/asumsi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Tunai tidak masuk AR forecast; tempo90 mengikuti SO meski profile diubah30; termin0 tetap0. Return/credit note, DP, partial receipt dan closing/reversal harus cocok dengan aging pada snapshot yang sama.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FIN-03 — Revenue profitabilitas memasukkan PPN included dan mengabaikan diskon header legacy

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/profitability_service.py:118](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/profitability_service.py#L118).

**Tampilan / rantai terkait:** Profitability: revenue, margin, dimension totals dan monthly trend · SO pricing/discount → profitability → management decision.

**Penyebab:** Revenue langsung menjumlahkan line_total. Pada harga tax included, field ini masih memuat PPN; revenue kanonis adalah grand_total−ppn_amount. Shape legacy dengan diskon order terpisah juga tidak dialokasikan. Current create_order memaksa manual order discount=0, sehingga contoh diskon header tidak digeneralisasi sebagai alur SO baru.

**Dampak dan batas interpretasi:** Pricing producer asli pada entitas PKP dengan pengaturan ppn_mode=included menghasilkan revenue laporan1000 meski nilai net setelah PPN lebih kecil. Semua dimensi/trend mewarisi PPN sebagai pendapatan. Contoh legacy baris1000−diskonheader100 menjadi1000 vs net900 dipertahankan dengan label legacy.

- `D4-FIN-03-order-discount-legacy` — expected `900`; actual `1000.0`; `observed_difference`.
- `D4-FIN-03-tax-included` — expected `900.9`; actual `1000.0`; `observed_difference`.

```python
 115:             pid = it.get("product_id") or ""
 116:             # Tanya KN F0.4 — WAC per satuan DASAR → HPP memakai base_quantity (qty jual bisa roll/meter).
 117:             qty = float(it.get("base_quantity") or it.get("quantity") or 0)
 118:             revenue = float(it.get("line_total", it.get("subtotal", 0)) or 0)
 119:             if qty <= 0 and revenue <= 0:
 120:                 continue
 121:             ck = f"{pid}::{ent or ''}"
 122:             if ck in wac_cache:
 123:                 wb, wl = wac_cache[ck]
 124:             else:
 125:                 w = await wac_for_product(pid, entity_id=ent)
```

**Prompt perbaikan:**

> Periksa `D4-FIN-03` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan shared net revenue allocation seperti fact sales dengan residual rounding yang terkontrol. Ambil grand_total−ppn_amount sesuai kontrak kanonis, dan jangan mengurangi diskon item dua kali ketika line_total sudah net. Jelaskan return/void dan legacy header discount. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Harga included1000: Σrevenue harus grand_total−ppn_amount dari producer pricing; excluded dan non-PKP tetap benar. Legacy ordergross1000−headerdisc100=net900 bila shape masih didukung. Semua dimensi, residual cent dan credit return direkonsiliasi.

**Hubungan dengan catatan lain:** D4-AI-04, D4-FIN-04

## D4-FIN-04 — Label pendapatan realisasi sebenarnya memakai pesanan reserved dan WAC terkini

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/profitability_service.py:19](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/profitability_service.py#L19).

**Tampilan / rantai terkait:** Profitability: Pendapatan (Realisasi), HPP (WAC), Marjin Kotor · SO reserved/confirmation → shipment/GL → report definition.

**Penyebab:** SOLD_STATUSES memasukkan confirmed dan reserved, tanggal memakai created_at SO, biaya dihitung dari WAC saat query. Ini analisis nilai pesanan dengan biaya kini, bukan otomatis realisasi shipment/GL historis.

**Dampak dan batas interpretasi:** SO reserved100 tanpa shipment/GL memberi Pendapatan (Realisasi)100. Current WAC bukan dengan sendirinya bug untuk estimasi; masalahnya kontrak label dan interpretasi. Probe hanya membuktikan reserved revenue, bukan semua skenario historical cost.

- `D4-FIN-04-unshipped-as-realisation` — expected `0`; actual `100.0`; `observed_difference`.

```python
  16: 
  17: EPS = 0.005
  18: # Status SO yang dianggap penjualan (revenue-recognized / dalam pemenuhan).
  19: SOLD_STATUSES = ["confirmed", "reserved", "partially_shipped", "shipped", "done"]
  20: MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
  21: 
  22: 
  23: def _pct(margin: float, revenue: float) -> Optional[float]:
  24:     return round(margin / revenue * 100, 1) if revenue > EPS else None
  25: 
  26: 
```

**Prompt perbaikan:**

> Periksa `D4-FIN-04` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pilih dan dokumentasikan metrik booked-order estimate vs realised revenue/margin. Jika realisasi, gunakan shipped/recognized amount serta cost snapshot yang sesuai. Jika tetap SO/WAC kini, ubah label/basis dan pisahkan estimator dari GL. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Reserved menunjukkan estimasi100 dan realisasi0 dalam metrik berbeda. Partial shipment, tanggal order vs dispatch, return, landed adjustment dan perubahan WAC memiliki perilaku terdefinisi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-01 — Analytics AP mengabaikan fallback vendor bill yang masih dipakai sumber kanonis

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_legacy_compatibility.

**Letak:** [backend/services/analytics_engine.py:288](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/analytics_engine.py#L288).

**Tampilan / rantai terkait:** Tanya KN / metric AP outstanding · Vendor bill legacy → bill_financials → analytics AP.

**Penyebab:** AP analytics hanya grand_total−amount_paid. bill_financials mendukung grand_total0 dengan total_amount fallback. Dokumen legacy yang sah jadi hilang dari analytics.

**Dampak dan batas interpretasi:** Billtotal125, paid25, grand_total0: sumber kanonis outstanding100, analytics tidak menghasilkan baris (praktis0).

- `D4-AI-01-ap-fallback` — expected `100`; actual `null`; `observed_difference`.

```python
 285: 
 286: async def _src_ap(metrics, dims, grain, p: Period, filters, sc, w, _s):
 287:     fq = _match_filters("ap", filters, w)
 288:     remaining = {"$subtract": [{"$ifNull": ["$grand_total", 0]}, {"$ifNull": ["$amount_paid", 0]}]}
 289:     due_field = {"$ifNull": ["$due_date", "$bill_date"]}
 290:     pre = [{"$match": {"entity_id": {"$in": sc.entity_ids},
 291:                        "status": {"$nin": ["draft", "cancelled", "void", "paid", "rejected"]}, **fq}},
 292:            {"$addFields": {"_rem": remaining, "_due": due_field}}, {"$match": {"_rem": {"$gt": 0.005}}}]
 293:     if grain:
 294:         w.append("Hutang adalah posisi saat ini; tidak dipecah per waktu.")
 295:     if p.date_to < now_wib().date():   # KN-E36 — hutang tidak punya snapshot historis
```

**Prompt perbaikan:**

> Periksa `D4-AI-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Normalisasi amount melalui satu kontrak bill financials yang juga dapat dieksekusi agregasi. Jangan membuat fallback berbeda antar aging, forecast, BI dan Tanya. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Grand_total positif, grand_total0 dengan total_amount, paid partial, legacy missing field, posted/void dan multicurrency jika didukung: outstanding konsisten dengan canonical.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-02 — Metric pelanggan baru mengabaikan scope lini

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_engine.py:168](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/analytics_engine.py#L168).

**Tampilan / rantai terkait:** Tanya KN / Analytics: new customer by line · Custom role line → fact_sales_lines → customer metric.

**Penyebab:** _src_fact_new tidak memakai sc.line_q sebagaimana sumber fact lain. Filter woven tetap menghitung customer knitting-only.

**Dampak dan batas interpretasi:** Dalam scope woven, satu customer yang hanya membeli knitting terhitung sebagai pelanggan baru1, seharusnya0 sesuai scope yang diminta.

- `D4-AI-02-new-customer-line` — expected `0`; actual `1`; `observed_difference`.

```python
 165:     return out
 166: 
 167: 
 168: async def _src_fact_new(metrics, dims, grain, p: Period, filters, sc: Scope, w, include_samples):
 169:     match: Dict[str, Any] = {"entity_id": {"$in": sc.entity_ids}, "is_live": True, "is_sample": False}
 170:     if sc.sales_only:
 171:         match["sales_id"] = sc.sales_only
 172:     fq = _match_filters("fact", filters, w)
 173:     fmap = cat.SOURCE_DIMS["fact"]
 174:     first = {fmap[d]: {"$first": f"${fmap[d]}"} for d in dims if d != "customer"}
 175:     pipe = [{"$match": {**match, **({"$and": fq["$and"]} if fq else {})}}, {"$sort": {"date_wib": 1}},
```

**Prompt perbaikan:**

> Periksa `D4-AI-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan scope/line policy bersama sebelum first-purchase grouping, termasuk keputusan apakah first berarti first ever atau first di lini. Jangan hanya filter sesudah agregasi first. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Knitting-only excluded woven; customer pernah membeli knitting lalu pertama woven diuji menurut definisi yang disetujui. Entity/owned-customer/role dimensi tetap enforced.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-03 — Refresh fact sales menghapus data lama sebelum replacement berhasil

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_facts.py:146](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/analytics_facts.py#L146).

**Tampilan / rantai terkait:** Tanya KN / analytics fact refresh · SO source → ETL/fact refresh → dashboards.

**Penyebab:** _write melakukan delete semua fact SO yang direfresh lalu insert_many. Bila insert gagal sebelum write, projection lama hilang walaupun source SO tetap ada.

**Dampak dan batas interpretasi:** Factrow1 menjadi0 setelah fault insert. Analitik/AI dapat memberi angka0 saat refresh gagal; ini kerusakan read model, bukan bukti GL atau SO hilang.

- `D4-AI-03-durable-refresh` — expected `1`; actual `0`; `observed_difference`.

```python
 143:     rows: List[Dict[str, Any]] = []
 144:     for o in orders:
 145:         rows.extend(build_rows(o, customers.get(o.get("customer_id") or "") or {}, products, users, mode))
 146:     await db.fact_sales_lines.delete_many({"so_id": {"$in": [o["id"] for o in orders]}})
 147:     if rows:
 148:         await db.fact_sales_lines.insert_many(rows, ordered=False)
 149:     return len(rows)
 150: 
 151: 
 152: async def _process(cursor_query: Dict[str, Any]) -> Tuple[int, int, str]:
 153:     mode = (await ai_policy())["sales_attribution"]
```

**Prompt perbaikan:**

> Periksa `D4-AI-03` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan generation staging + atomic publish pointer, transaction, atau deterministic upsert + retire stale rows hanya setelah replacement lengkap. Simpan sync progress dan expose freshness/error. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum/sesudah tiap write tidak membuat complete snapshot lama hilang. Retry dan dua worker tidak duplicate fact; Σfact sama source valid, invalid schema tidak menurunkan seluruh dataset.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-04 — Pembulatan alokasi tim sales tidak mengonservasi nilai dokumen

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_facts.py:118](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/analytics_facts.py#L118).

**Tampilan / rantai terkait:** Fact Sales / Tanya KN: revenue by sales dan total · SO split sales → rounded fact rows → analytics sums.

**Penyebab:** Setiap bagian dibulatkan independen ke2desimal tanpa menempatkan residual pada baris deterministik.

**Dampak dan batas interpretasi:** Tim dua anggota PIC/co dengan split50/50 memenuhi aturan maksimaldua anggota saatini. Net1.01 menjadi0.51+0.51=1.02. Perbedaan kecil per dokumen dapat terakumulasi; gunakan satuan uang sesuai kontrak sebenarnya.

- `D4-AI-04-money-conservation` — expected `1.01`; actual `1.02`; `observed_difference`.

```python
 115:                 "qty_base": round(qty_base * split, 4),
 116:                 "rolls": round(_f(it.get("qty_rolls")) * split, 4),
 117:                 "gross": round(gross_alloc, 2),
 118:                 "net_alloc": round(net_alloc, 2),
 119:                 "discount": round(gross_alloc - net_alloc, 2),
 120:                 "ppn_alloc": round(ppn * share * split, 2),
 121:                 "cost": round(_f(it.get("unit_cost")) * qty_base * split, 2),
 122:             })
 123:     return rows
 124: 
 125: 
```

**Prompt perbaikan:**

> Periksa `D4-AI-04` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Alokasikan dalam minor units/Decimal, gunakan largest-remainder atau residual akhir deterministik untuk gross/net/PPN. Konservasi harus terjaga pada semua grouping. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Net1.01 dibagi2 anggota50/50 tetap total1.01; fractionaldiscount+tax,10lines×2sales, negative return dan replay sync tidak mengubah total/identity. Data legacy dengan anggota lebihbanyak, bila masihdibaca, tidak boleh merusak konservasi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-05 — Stok tersedia dan reserved di live analytics serta snapshot mengabaikan reservasi parsial

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_snapshots.py:18](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/analytics_snapshots.py#L18).

**Tampilan / rantai terkait:** Tanya KN: available/reserved stock dan historical stock · Partial cut reservation → inventory_balances / rolls → live/snapshot analytics.

**Penyebab:** Live _src_stock dan snapshot_stock menggolongkan seluruh length_remaining menurut status roll. Roll available dengan length_reserved3 tetap dihitung available10/reserved0.

**Dampak dan batas interpretasi:** Original roll helper membuat roll10 dan reserve3; SSOTbalance free7/reserved3. Analytics dan snapshot masing-masing10/0. Sales/MD mendapat available yang berlebihan.

- `D4-AI-05-partial-cut-live` — expected `{"stock_available_qty": 7, "stock_reserved_qty": 3}`; actual `{"stock_available_qty": 10.0, "stock_reserved_qty": 0}`; `observed_difference`.
- `D4-AI-05-partial-cut-snapshot` — expected `{"avail": 7, "reserved": 3}`; actual `{"avail": 10.0, "reserved": 0}`; `observed_difference`.

```python
  15:     pipe = [{"$match": {"status": {"$in": list(cat.PHYSICAL_ROLL_STATUSES)}}},
  16:             {"$group": {"_id": {k: f"${k}" for k in _STOCK_KEYS}, "qty": {"$sum": rem}, "rolls": {"$sum": 1},
  17:                         "value": {"$sum": {"$multiply": [rem, {"$ifNull": ["$unit_cost", 0]}]}},
  18:                         "avail": {"$sum": {"$cond": [{"$eq": ["$status", "available"]}, rem, 0]}},
  19:                         "reserved": {"$sum": {"$cond": [{"$in": ["$status", list(cat.RESERVED_ROLL_STATUSES)]}, rem, 0]}}}}]
  20:     rows = [{"date": day, **{k: r["_id"].get(k) or "" for k in _STOCK_KEYS},
  21:              **{k: r[k] for k in ("qty", "rolls", "value", "avail", "reserved")}}
  22:             async for r in db.inventory_rolls.aggregate(pipe)]
  23:     await db.fact_stock_daily.delete_many({"date": day})
  24:     if rows:
  25:         await db.fact_stock_daily.insert_many(rows)
```

**Prompt perbaikan:**

> Periksa `D4-AI-05` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan canonical physical/free/reserved definition yang mengakomodasi whole-roll dan partial-length. Pisahkan availability fisik vs ATP vs ready-to-dispatch; jangan memperbaiki hanya snapshot sementara live tetap berbeda. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Available roll10 reservedlength3 → free7/reserved3; whole reserved10→free0/reserved10. Hold/quarantine, makloon-reserved, cut complete/release dan snapshotday diuji live=historical snapshot saat titik waktu sama.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-06 — Total quantity lintas produk menjumlahkan meter dengan kilogram

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_engine.py:565](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/analytics_engine.py#L565).

**Tampilan / rantai terkait:** Tanya KN metric tables: totals dan shares · Product base UOM → query group_by product → quantity total.

**Penyebab:** Unit guard hanya menambahkan unit ketika group_by tidak memuat product/unit. Mixed-unit detection hanya berjalan jika unit menjadi dimensi. Group product dapat mengembalikan meter/kg dengan total tunggal.

**Dampak dan batas interpretasi:** Stock10meter +5kg tampiltotal15, yang tidak punya arti dimensional. Row bisa benar tetapi total/share menyesatkan.

- `D4-AI-06-mixed-product-total` — expected `null`; actual `15.0`; `observed_difference`.

```python
 562:     shares = bool(dims or grain)
 563:     # KN-E34 — baris sudah per satuan; total/pembanding/porsi qty juga tidak boleh lintas satuan.
 564:     ui = dims.index("unit") if "unit" in dims else None
 565:     mixed = ui is not None and len({k[ui] for k in keys}) > 1
 566:     unit_tot: Dict[Any, Dict[str, float]] = {}
 567:     if mixed:
 568:         for k, cur in rows.items():
 569:             for m in shown:
 570:                 if m in cat.QTY_METRICS:
 571:                     unit_tot.setdefault(k[ui], {})[m] = unit_tot.get(k[ui], {}).get(m, 0.0) + float(cur.get(m) or 0)
 572:         warnings.append("Total qty tidak ditampilkan karena lintas satuan; porsi dihitung per satuan.")
```

**Prompt perbaikan:**

> Periksa `D4-AI-06` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Lacak unit fisik dari metadata row walau dimensi product dipilih. Quantity mixed tidak memiliki grand total; kelompokkan per unit atau konversi eksplisit hanya dalam dimensi kompatibel dengan faktor tersimpan. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Product10m+5kg → total null/N/A dan per-unit10m/5kg;10m+5m→15m. Shares mixed quantity tidak dihitung silang unit; salesmoney tetap boleh dijumlah.

**Hubungan dengan catatan lain:** D4-WMS-03

## D4-CASH-01 — Saldo awal kas kecil berpindah menjadi kas besar setelah transaksi terakhir di-void

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/cash.py:103](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/routers/cash.py#L103).

**Tampilan / rantai terkait:** Cash Dashboard: opening kas kecil/besar dan saldo · Bank/cash account opening → petty transactions → void → summary.

**Penyebab:** Jenis saldo awal ditentukan oleh account_id yang muncul pada transaksi kas kecil aktif. Master tidak memiliki field cash_type untuk klasifikasi tetap; void transaksi terakhir membuat account keluar dari kecil_ids.

**Dampak dan batas interpretasi:** Opening1000 yang semula kas kecil menjadi kasbesar1000 setelah transaksi10 di-void, padahal opening master tidak berubah. Total cash bisa tetap benar namun split kategori salah.

- `D4-CASH-01-opening-reclass` — expected `{"before_kecil_opening": 1000, "after_kecil_opening": 1000, "after_besar_opening": 0}`; actual `{"before_kecil_opening": 1000.0, "after_kecil_opening": 0, "after_besar_opening": 1000.0}`; `observed_difference`.

```python
 100:     # Saldo = saldo awal rekening + masuk − keluar (dulu saldo awal diabaikan).
 101:     accounts = await db.bank_accounts.find({"entity_id": {"$in": list(entities)}},
 102:                                            {"_id": 0, "id": 1, "opening_balance": 1}).to_list(500)
 103:     kecil_ids = {r.get("account_id") for r in kecil_q if r.get("account_id")}
 104:     open_kecil = sum(float(a.get("opening_balance") or 0) for a in accounts if a["id"] in kecil_ids)
 105:     open_besar = sum(float(a.get("opening_balance") or 0) for a in accounts if a["id"] not in kecil_ids)
 106:     for eid, v in per_entity.items():
 107:         ob = sum(float(a.get("opening_balance") or 0) for a in accounts
 108:                  if a["id"] in kecil_ids and any(r.get("account_id") == a["id"] and r.get("entity_id") == eid for r in kecil_q))
 109:         v["balance"] = round(v["balance"] + ob, 2)
 110:     return {
```

**Prompt perbaikan:**

> Periksa `D4-CASH-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tetapkan account classification atau mapping eksplisit yang tidak bergantung ada/tidak transaksi. Rancang migration/legacy unknown; jangan menebak dari transaksi terkini atau mengarang field schema sudah ada. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Void/delete transaksi terakhir tidak mengubah jenis opening. Account tanpa transaksi, legacy tanpa mapping, beberapa entitas, cash deposit transfer dan preview compare harus konsisten.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-DASH-01 — Ringkasan dashboard kehilangan reservasi makloon di luar100SKU pertama

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/dashboard.py:37](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/routers/dashboard.py#L37).

**Tampilan / rantai terkait:** Dashboard summary: total available dan product lookup · Product master → makloon reservation → dashboard ATP/availability.

**Penyebab:** Dashboard mengambil100product kemudian menjumlahkan makloon_reserved_qty hanya dari product yang termuat, sementara on-hand dibaca lebih luas.

**Dampak dan batas interpretasi:** SKU reserved200 berada di luar100master pertama. Available seharusnya850, tampil1050. Limit tanpa pagination pada dictionary pendukung juga dapat menyembunyikan referensi.

- `D4-DASH-01-master-window-reservation` — expected `850`; actual `1050.0`; `observed_difference`.
- `D4-DASH-01-master-completeness` — expected `103`; actual `100`; `observed_difference`.

```python
  34:     # `apply_scope` hanya mengikat peran `sales`; sales_admin/finance/manager/
  35:     # admin/warehouse tetap melihat keseluruhan pesanan seperti sebelumnya.
  36:     order_scope = sales_ownership.apply_scope(scope, actor)
  37:     products_raw = await db.products.find({}, {"_id": 0}).to_list(100)
  38:     # S#096 — HPP turunan pembelian (WAC roll) untuk layar Master Produk; diredaksi strip_cost_fields per peran.
  39:     from services import costing_service as _cs
  40:     for _p in products_raw:
  41:         try:
  42:             _w = await _cs.wac_for_product(_p["id"], product=_p)
  43:             _p["hpp"], _p["hpp_source"] = float(_w.get("wac") or 0), _w.get("source", "")
  44:         except Exception:  # noqa: BLE001
```

**Prompt perbaikan:**

> Periksa `D4-DASH-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Agregasi summary harus memakai seluruh scope yang sama dan sumber reservasi kanonis. Pagination untuk daftar tidak boleh mempengaruhi total. Uji semua bounded helper yang dipakai metrik. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** 103master dengan reservasi diSKUke101 tetap mengurangi200. Page size/order tidak mengubah total. Entity/warehouse/line filter, pending demand dan hold punya kontrak eksplisit.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-HR-01 — Payroll gabungan memakai satu run pada KPI dan menimpa run lain pada trend

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/hr_analytics_service.py:146](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/hr_analytics_service.py#L146).

**Tampilan / rantai terkait:** HR Analytics: payroll cost, gross/net/BPJS/employee trend · Payroll runs perentity → grouped period → HR cards/charts.

**Penyebab:** KPI find_one(period); trend map period diberi assignment sehingga run berikut menimpa sebelumnya. Dua entitas dalam bulan sama tidak diaggregate.

**Dampak dan batas interpretasi:** RunA100 +B200: kartu100, trend200, total seharusnya300. Ini error analitik; probe tidak membuktikan GL payroll posting salah.

- `D4-HR-01-multi-run-trend` — expected `300`; actual `200.0`; `observed_difference`.
- `D4-HR-01-multi-run-kpi` — expected `300`; actual `100.0`; `observed_difference`.

```python
 143:     }
 144: 
 145:     # ── Payroll cost (run periode terpilih) + tren ──
 146:     run = await db.hr_payroll_runs.find_one({**pay_scope, "period": sel}, {"_id": 0})
 147:     t = (run or {}).get("totals", {}) or {}
 148:     payroll = {
 149:         "period": sel, "has_run": bool(run),
 150:         "status": (run or {}).get("status", ""),
 151:         "employees": int(t.get("employees") or 0),
 152:         "gross": round(float(t.get("gross") or 0), 0),
 153:         "net": round(float(t.get("net") or 0), 0),
```

**Prompt perbaikan:**

> Periksa `D4-HR-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Aggregate posted/eligible runs perperiod/selectedentity dengan lifecycle jelas, hindari menghitung draft+replacement ganda. Bedakan sum employees vs distinctpeople jika employee shared. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** All gross300/net270, A100/B200, chart=card. Draft/replaced/void run tidak double-count; BPJS/PPH dan employee basis diuji.

**Hubungan dengan catatan lain:** D4-HR-02

## D4-HR-02 — Turnover menggunakan waktu edit data sebagai waktu karyawan keluar

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/hr_analytics_service.py:136](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/hr_analytics_service.py#L136).

**Tampilan / rantai terkait:** HR Analytics: separations/turnover · Employee status transition → edit profile → turnover.

**Penyebab:** Inactive/resigned dihitung berdasarkan updated_at, bukan effective separation event. Schema saat ini tidak menyediakan termination_date yang kanonis; field tersebut pada probe hanya menjelaskan tanggal bisnis, bukan field publik yang diklaim sudah ada.

**Dampak dan batas interpretasi:** Karyawan keluarbulanJuli tetapi profil dieditOktober dianggap separasiOktober. Ini gap sumber data/definition, bukan sekadar salah operator.

- `D4-HR-02-separation-date` — expected `0`; actual `1`; `observed_difference`.

```python
 133: 
 134:     # ── Turnover (separations = status non-active pada periode; new hires periode) ──
 135:     separations = sum(1 for e in employees if (e.get("status") or "active") != "active"
 136:                       and (e.get("updated_at") or "")[:7] == sel)
 137:     hires_period = sum(1 for e in active if _join(e)[:7] == sel)
 138:     base_hc = len(active) or 1
 139:     turnover = {
 140:         "period": sel, "separations": separations, "headcount": len(active),
 141:         "new_hires": hires_period,
 142:         "turnover_rate": round(separations / base_hc * 100, 1),
 143:     }
```

**Prompt perbaikan:**

> Periksa `D4-HR-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tambahkan effective status-transition/separationdate dengan audit history dan backfill yang eksplisit. Perubahan profil tidak mengubah tanggal keluar. Definisikan numerator/denominator turnover. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** KeluarJuli lalu editOktober: Juli1, Oktober0. Rehire, koreksi status, delete/archival dan transferentity memiliki treatment terdefinisi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-WMS-01 — RFID RED hari ini pada Warehouse Health memakai hari UTC

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/wms_health_service.py:28](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/wms_health_service.py#L28).

**Tampilan / rantai terkait:** Warehouse Health: red_reads_today · RFID timestamp UTC → business day WIB → health card.

**Penyebab:** Filter today memakai prefix tanggal UTC. Operasi gudang lokal menggunakan WIB sehingga antara00:00–06:59 WIB hari bisnis berbeda.

**Dampak dan batas interpretasi:** Freeze01Oct01:00WIB: read30Sept23:00WIB dihitung hariini. Dua read menghasilkan2, seharusnya hanya1.

- `D4-WMS-01-wib-day` — expected `1`; actual `2`; `observed_difference`.

```python
  25:         "last_cc": None, "devices_total": 0, "devices_stale": 0,
  26:     } for w in whs}
  27: 
  28:     today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
  29:     async for r in db.rfid_incidents.aggregate([
  30:             {"$match": {"status": "open"}},
  31:             {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}}]):
  32:         if r["_id"] in rows:
  33:             rows[r["_id"]]["open_incidents"] = r["n"]
  34:     async for r in db.rfid_reads.aggregate([
  35:             {"$match": {"result": "red", "timestamp": {"$gte": today},
```

**Prompt perbaikan:**

> Periksa `D4-WMS-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan range [WIBdaystart, nextdaystart) dikonversi UTC. Jangan memakai regex prefix date atau mencampur string timestamp offset berbeda. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** 23:59WIB yesterday excluded;00:00/06:59todayincluded; timezone UTC/Z/offsetnormalized. Chart dan KPI memakai satu batas hari bisnis.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-WMS-02 — Cycle count terbaru yang belum selesai menghapus angka akurasi terakhir

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/wms_health_service.py:71](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/wms_health_service.py#L71).

**Tampilan / rantai terkait:** Warehouse Health: last cycle count / accuracy · Cycle count open → assessed/approved → warehouse health.

**Penyebab:** Service memilih dokumen terbaru tanpa mensyaratkan accuracy valid/status selesai dan tidak mengirim status. Frontend memasang suffix% walau accuracy tidak ada.

**Dampak dan batas interpretasi:** Count terukur95%, lalu count baruopen: last_cc memilihopen tanpa angka. Hasilnya angka akurasi hilang/placeholder ambigu, bukan bukti0% ditampilkan.

- `D4-WMS-02-last-measured-cc` — expected `"CCOK"`; actual `"CCOPEN"`; `observed_difference`.

```python
  68:             {"$group": {"_id": "$warehouse_id", "doc": {"$first": "$$ROOT"}}}]):
  69:         if cc["_id"] in rows:
  70:             d = cc["doc"]
  71:             rows[cc["_id"]]["last_cc"] = {"cc_number": d.get("cc_number"),
  72:                                           "accuracy_pct": d.get("accuracy_pct"),
  73:                                           "missing_count": d.get("missing_count"),
  74:                                           "at": d.get("created_at")}
  75:     now = datetime.now(timezone.utc)
  76:     async for d in db.rfid_devices.find({}, {"_id": 0, "warehouse_id": 1,
  77:                                              "last_heartbeat": 1, "status": 1}):
  78:         if d.get("warehouse_id") not in rows:
```

**Prompt perbaikan:**

> Periksa `D4-WMS-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan latestcountstatus dan lastmeasuredaccuracy. Pilih count terukur sesuai lifecycle bisnis (bukan secara arbitrer selaluapproved) dan tampilkan N/A untuk belum dinilai. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Openbaru tidak menimpa lastmeasured95%; UI menunjukkan statusopen. Measured0% harus tetap0% dan dibedakan darinull; rejected/void count tidak dijadikan valid measurement.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-WMS-03 — Utilisasi gudang mengabaikan struktur Rack→Level→Bin yang didukung master

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/reporting.py:203](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/routers/reporting.py#L203).

**Tampilan / rantai terkait:** Manager Dashboard: warehouse capacity/utilization · Warehouse structure → location flattening → capacity dashboard.

**Penyebab:** Producer warehouse_structure menyimpan bins di rack.levels[].bins. Consumer reporting hanya rack.bins legacy, sehingga capacity0 dan utilization0 meski lokasi punya capacity.

**Dampak dan batas interpretasi:** Struktur dibuat melalui helperoriginal: warehouse_locations capacity100; /reports/warehouse-utilization capacity0. Dapat menyamarkan penuh/tidaknya gudang.

- `D4-WMS-03-level-capacity` — expected `{"locations": 100, "manager_report": 100}`; actual `{"locations": 100.0, "manager_report": 0.0}`; `observed_difference`.

```python
 200:         total_capacity = 0.0
 201:         for zone in warehouse.get("zones", []):
 202:             for rack in zone.get("racks", []):
 203:                 for bin_ in rack.get("bins", []):
 204:                     total_capacity += float(bin_.get("capacity", 0))
 205:         bal_scope = resolve_list_scope(
 206:             "inventory_balances", {"warehouse_id": warehouse["id"]}, ctx, entity_id)
 207:         balances = await db.inventory_balances.find(bal_scope, {"_id": 0}).to_list(1000)
 208:         on_hand_total = sum(float(b.get("on_hand_qty", 0)) for b in balances)
 209:         reserved_total = sum(float(b.get("reserved_qty", 0)) for b in balances)
 210:         available_total = sum(float(b.get("available_qty", 0)) for b in balances)
```

**Prompt perbaikan:**

> Periksa `D4-WMS-03` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Reuse canonical location traversal yang mendukung legacy dan level. Tegaskan unit kapasitas dan pisahkan mixedunitstock; jangan membagi meter+kg terhadap denominator yang tidak jelas. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Rack→Level→Bins100 tampilcapacity100; legacyrack.bins tetap benar dan tidak dihitungdua kali. Multiunit/capacity0/owner shares/locationinactive diuji.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-MKT-01 — Reach agregat post disajikan ulang sebagai reach tiap platform dan akun

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/marketing_ext.py:137](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/marketing_ext.py#L137).

**Tampilan / rantai terkait:** Marketing Dashboard: by_platform dan by_account · Post multi-platform → aggregate metrics → channel breakdown.

**Penyebab:** Satu metrics aggregate post ditambahkan penuh ke setiap platform/account. Tidak ada pengukuran per-channel tersimpan, sehingga channel reach bukan actual channel measurement. Kelompok overlapping boleh nonadditive hanya bila kontraknya jelas.

**Dampak dan batas interpretasi:** Post reach100 padaIG+TikTok: KPI100, jumlahbyplatform200 dan byaccount200. Jangan menebak channel reach50/50; data actual belum tersedia.

- `D4-MKT-01-attribution-conservation` — expected `{"total_reach": 100, "platform_reach_sum": 100, "account_reach_sum": 100}`; actual `{"total_reach": 100.0, "platform_reach_sum": 200.0, "account_reach_sum": 200.0}`; `observed_difference`.

```python
 134:         rows = [r for r in six if (r.get("publish_at") or "")[:7] == mm]
 135:         k = _kpi(rows)
 136:         trend.append({"month": mm, "label": f"{MONTHS_ID[int(mm[5:7]) - 1][:3]} {mm[2:4]}", "posts": k["posts"], "published": k["published"], "reach": k["reach"], "engagement": k["engagement"]})
 137:     by_platform: Dict[str, Dict[str, Any]] = {}
 138:     by_account: Dict[str, Dict[str, Any]] = {}
 139:     by_entity: Dict[str, Dict[str, Any]] = {}
 140:     for r in cur:
 141:         pub = r["status"] == "published"; mt = r.get("metrics") or {}
 142:         for pl in r.get("platforms") or []:
 143:             b = by_platform.setdefault(pl, {"posts": 0, "published": 0, "reach": 0.0, "engagement": 0.0, "clicks": 0.0})
 144:             b["posts"] += 1
```

**Prompt perbaikan:**

> Periksa `D4-MKT-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan apakah breakdown merupakan shared post attribution atau measurement perchannel. Jika shared, label nonadditive dan jangan total ulang. Jika actual, simpan metrics perplatform/account dengan provenance/time dan aggregate dedup sesuai definisi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Postmulti-channel100 tidak ditampilkan seolah masing-masingpunya actual100 tanpa keterangan. Separate metrics30/70 hanya jika benar-benar diukur. Reachunique crosschannel tidak disimpulkan dari penjumlahan biasa.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-RND-01 — KPI R&D menggabungkan orang berbeda yang mempunyai nama sama

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/rnd_kpi_service.py:153](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/rnd_kpi_service.py#L153).

**Tampilan / rantai terkait:** R&D designer/MD KPI, approval performance · Round performer identity → names → KPI groups.

**Penyebab:** Round producer menyimpan performed_by_user_id, tetapi KPI memakai performed_by/opened_by/created_by displayname sebagai identity. Dua user dengan nama sama menjadi satu baris.

**Dampak dan batas interpretasi:** Dua round dengan U1 danU2 sama displayname menghasilkan1pelaksana, seharusnya2. Nama berubah juga dapat memecah histori orang yang sama.

- `D4-RND-01-person-identity` — expected `2`; actual `1`; `observed_difference`.

```python
 150:     return max((today - due).days, 0)
 151: 
 152: 
 153: def designer_of(sample: Dict[str, Any], rd: Dict[str, Any]) -> str:
 154:     """Penanggung jawab round — lihat catatan desain di docstring modul."""
 155:     for cand in (rd.get("performed_by"), rd.get("opened_by"), sample.get("created_by")):
 156:         name = str(cand or "").strip()
 157:         if name:
 158:             return name
 159:     return "(tanpa nama)"
 160: 
```

**Prompt perbaikan:**

> Periksa `D4-RND-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Group stable user_id/employee_id dan render displayname sebagai label. Legacy name-only perlu mapping ambiguity explicit, bukan autojoin semua nama. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** U1/U2nama sama→2KPI; U1ganti nama→1history. Fallbacklegacyambiguous ditandai, customroleline/roundtypefilter tetap berlaku.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FE-01 — Grafik velocity Manager selalu memotong menjadi14hari

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [frontend/src/features/manager/ManagerDashboard.jsx:100](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/frontend/src/features/manager/ManagerDashboard.jsx#L100).

**Tampilan / rantai terkait:** Manager Dashboard: periode 7/30/90 vs velocity chart · Period selector → reporting velocity → frontend slicing.

**Penyebab:** Dataset velocity dari API dipotong slice(-14) tanpa mengikuti period pilihan.

**Dampak dan batas interpretasi:** OriginalJS expression diuji: input7 tampil7(control), input30/90 masing-masing14. Judul/periode dapat memberikan kesan datasetlengkap.

- `D4-FE-01-chart-7` — expected `7`; actual `7`; `pass`.
- `D4-FE-01-chart-30` — expected `30`; actual `14`; `observed_difference`.
- `D4-FE-01-chart-90` — expected `90`; actual `14`; `observed_difference`.

```javascript
  97:   useEffect(() => { load(); }, [period, agingDays, selectedEntity]);
  98: 
  99:   const funnelChartData = (funnel?.funnel || []).filter(f => !["cancelled", "expired"].includes(f.status));
 100:   const velocityData = (velocity?.velocity || []).slice(-14); // last 14 days
 101:   const utilizationData = utilization.map(w => ({
 102:     name: w.warehouse_city || w.warehouse_name,
 103:     on_hand: w.on_hand_qty,
 104:     capacity: w.total_capacity,
 105:     pct: w.utilization_pct,
 106:   }));
 107: 
```

**Prompt perbaikan:**

> Periksa `D4-FE-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan range period yang sama dengan request atau label last14days secara eksplisit jika itu tujuan grafik. Jangan memotong data tanpa indikasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Periode7/30/90 menunjukkan dataset sesuai tanggalpilihan; emptydays tetapkontrak API, boundarydates/labeltooltip diperiksa diUI.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FE-02 — Respons lama dapat menimpa dashboard setelah pengguna beralih entitas

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [frontend/src/features/manager/ManagerDashboard.jsx:69](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/frontend/src/features/manager/ManagerDashboard.jsx#L69).

**Tampilan / rantai terkait:** Manager Dashboard entity/filter controls · Entity switch → concurrent API requests → React state.

**Penyebab:** load/useEffect tidak membatalkan request lama atau menjaga generation. RequestA lambat selesai setelahB dan menulis stateA meskipun selectionB.

**Dampak dan batas interpretasi:** Transportterkontrol menjalankan original load: B selesai→stateB benar; A selesai kemudian→stateA. Probe function-level, tidak mengklaim browserE2E atau semua halaman memiliki bug yang sudahteruji.

- `D4-FE-02-after-current-response` — expected `"B"`; actual `"B"`; `pass`.
- `D4-FE-02-stale-entity-overwrite` — expected `"B"`; actual `"A"`; `observed_difference`.

```javascript
  66: 
  67:   const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  68: 
  69:   const load = async () => {
  70:     setLoading(true);
  71:     // F0-E: laporan ter-scope per entitas aktif ('all' = oversight lintas-PT).
  72:     const ent = selectedEntity || "all";
  73:     const cfg = { headers, params: { entity_id: ent } };
  74:     try {
  75:       const [sumRes, funnelRes, velRes, custRes, utilRes, agingRes] = await Promise.all([
  76:         axios.get(`${API}/reports/summary`, cfg),
```

**Prompt perbaikan:**

> Periksa `D4-FE-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Implement generationguard/AbortController yang melindungi semua setters termasuk loading/error. Data beberapaendpoint harus satu requestgeneration. Audit pola sama dihalaman lain dengan probe terpisah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** SwitchA→B dan responseoutoforder: semuakartu/chart B; staleerrors dan finallyA tidakmengubahB. Rapidperiod/categorychanges, unmount dan combinedpartialfail diperiksa.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-TEST-01 — Tes konsistensi ATP dapat lulus walaupun mencatat mismatch

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** source_review_test_oracle.

**Letak:** [backend/tests/test_iter149_audit.py:116](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/tests/test_iter149_audit.py#L116).

**Tampilan / rantai terkait:** Verification pipeline / ATP oracle · Inventory report → old regression test → green status.

**Penyebab:** test_stock_atp_sum_matches mengumpulkan bad_row/bad_wh dan menulis/print hasil tanpa assert terakhir yang menolak mismatch. Formula lama juga perlu diselaraskan dengan pendingdemandyang didokumentasikan.

**Dampak dan batas interpretasi:** Green test ini hanya membuktikanHTTP/listshape, bukan ATPformula benar. test_iter150 memilikiassert yang lebihbermakna sehingga perbaikannya harus menghindari oracle lama yangsalah.

**Observasi:** {}

```python
 113:     assert r.status_code == 200, r.text
 114:     rows = r.json()
 115:     assert isinstance(rows, list)
 116:     bad_row = []
 117:     bad_wh = []
 118:     for row in rows:
 119:         av = float(row.get('total_available') or 0)
 120:         inc = float(row.get('total_incoming') or 0)
 121:         rsv = float(row.get('total_reserved') or 0)
 122:         atp = float(row.get('total_atp') or 0)
 123:         expected = av + inc - rsv
```

**Prompt perbaikan:**

> Periksa `D4-TEST-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Definisikan formulaavailability/ATP bersama timbisnis, buat independentoracle dengan fixture partialreserve/hold/pending/incoming. Tambahkan assertionmismatch dan test-negatif yangmemastikanoracle gagal terhadapmutasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** InjectwrongATP→testFAIL; correctformula→PASS. Uji fixture>100SKU, multiowner, pendingcut, externalincoming dan no-dependencydemoaccount.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-DATE-01 — Penjualan dan Home menggunakan bulan/tahun UTC yang berbeda dari periode bisnis WIB

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_force_service.py:27](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/sales_force_service.py#L27).

**Tampilan / rantai terkait:** Sales KPI, commission period/history, Home periode default; consumer tanggal serupa perlu ditelusuri · UTC created_at/payment timestamp → period selection → target/commission/report.

**Penyebab:** _in_period memotong tanggal string tanpa konversi timezone. Home _current_month/_today_prefix juga memakai UTC. Transaksi normal pada tujuh jam pertama WIB di awal bulan/tahun dapat masuk periode sebelumnya. Analytics engine memiliki konversi WIB tersendiri, sehingga metrik antarmodul dapat berbeda.

**Dampak dan batas interpretasi:** Timestamp30Sep18:00UTC adalah01Oct01:00WIB: filterOctoberFalse, SeptemberTrue. Home defaultmasihSeptember/30Sep. Timestamp31Dec18:00UTC ditolak dariyear2027 meski tanggalbisnis01Jan2027. Belum semua consumer polaUTC ini diuji runtime; jangan menganggap semuanya sudahconfirmed.

- `D4-DATE-01-home-default` — expected `{"month": "2026-10", "day": "2026-10-01"}`; actual `{"month": "2026-09", "day": "2026-09-30"}`; `observed_difference`.
- `D4-DATE-01-month-inclusion` — expected `true`; actual `false`; `observed_difference`.
- `D4-DATE-01-prior-month` — expected `false`; actual `true`; `observed_difference`.
- `D4-DATE-01-year-inclusion` — expected `true`; actual `false`; `observed_difference`.

```python
  24:     """Cocokkan created_at dengan periode: YYYY-MM (bulan), YYYY-Qn (kuartal), YYYY (tahun)."""
  25:     if not period:
  26:         return True
  27:     v = str(value or "")[:10]
  28:     if len(v) < 7:
  29:         return False
  30:     ym, yr = v[:7], v[:4]
  31:     p = str(period).upper()
  32:     if "-Q" in p:
  33:         try:
  34:             py, q = p.split("-Q")
```

**Prompt perbaikan:**

> Periksa `D4-DATE-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan timezone bisnis/per-entity dan gunakan helper periode bersama untuk timestamp serta date-only. Buat range UTC dari batas periode WIB. Jangan hanya mengubah bulan default Home sementara filterSO/payment masih memotong stringUTC. Telusuri profitability monthly grouping dan Finance Tower period sebagai related static candidates. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Batas23:59:59WIB dan00:00WIB di awalbulan, kuartal dan tahun masuk periodeyangbenar; timestamp Z/+00/+07 serta date-only memiliki aturanjelas. KPI, target, commissionhistory, snapshot dan export pada filter sama harusrekonsiliasi.

**Hubungan dengan catatan lain:** D4-WMS-01, V3-DATE-01, D4-FIN-04

