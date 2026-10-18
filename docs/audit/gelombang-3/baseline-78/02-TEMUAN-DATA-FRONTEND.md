# Audit sumber data, angka dan tampilan frontend

Semua permalink dikunci pada commit yang diaudit. Expected pada gap definisi memakai makna label; keputusan bisnis yang berbeda harus didokumentasikan dan dilabelkan, bukan diasumsikan. Bukti function-level JavaScript tidak setara uji React di browser.

## D4-STOCK-01 — Nilai dan kecepatan stok terhitung dua kali ketika pemilik berbagi SKU dan gudang

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/stock_analytics_service.py:137](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L137).



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

> Periksa `D4-STOCK-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan grain product + warehouse + owner sampai tahap agregasi akhir. Jangan join aggregate dengan grain yang lebih kasar ke beberapa balance lalu menjumlahkannya lagi. Terapkan pola yang sama untuk movement, oldest-age dan WAC. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** SKU/gudang sama dengan dua pemilik: qty 30, nilai 500 dan sold 10; filter A=100/3, B=400/7. Tambahkan gudang kedua dan movement reversal; grouped total harus sama dengan penjumlahan partisi yang sah.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-STOCK-02 — Filter kategori tidak diterapkan pada bucket umur stok

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/stock_analytics_service.py:175](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L175).



**Tampilan / rantai terkait:** Stock Analytics: filter kategori vs chart aging · Master kategori → stok fisik → chart umur.

**Penyebab:** Aging diakumulasi sebelum row product diperiksa terhadap category. Tabel kategori woven sudah difilter, bucket aging masih berisi kategori lain.

**Dampak dan batas interpretasi:** Fixture woven bernilai 100, knitting 400: memilih woven menghasilkan aging 500. Manajer membandingkan dua visual dengan cakupan berbeda.

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

> Periksa `D4-STOCK-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bentuk product whitelist/filter yang sama sebelum mengambil roll, balance dan movement. Semua KPI/chart harus memakai filter yang sama, atau labelkan secara eksplisit jika global. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Filter woven: total rows 100 = sum aging 100; filter knitting 400. Uji kategori kosong, SKU tanpa kategori dan kombinasi entitas/gudang.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-STOCK-03 — Nilai persediaan analitik mengabaikan landed cost

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/stock_analytics_service.py:166](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L166).



**Tampilan / rantai terkait:** Stock Analytics: nilai stok · Receiving → landed cost → roll valuation → analitik.

**Penyebab:** Valuasi memakai base_unit_cost meskipun unit_cost roll sudah memuat landed cost. Basis ini berbeda dengan nilai penuh costing/GL; tampilan nilai persediaan tidak menyatakan hanya biaya dasar.

**Dampak dan batas interpretasi:** Roll 10, biaya dasar 10, biaya penuh 12: tabel nilai 100, biaya persediaan penuh 120. Rekonsiliasi dengan laporan biaya penuh tidak cocok.

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

> Periksa `D4-STOCK-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tetapkan kontrak nilai persediaan: tampilkan biaya penuh dari sumber biaya kanonis; bila perlu pisahkan dasar, landed dan total. Jangan menjumlahkan landed dua kali. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Roll 10×12 menghasilkan 120, split dasar 100 + landed 20. Uji voucher landed apply/void dan per-entitas. Jika bisnis memilih base-only, label dan rekonsiliasi harus menyatakan basis tersebut.

**Hubungan dengan catatan lain:** D4-STOCK-01

## D4-STOCK-04 — Tanggal roll tanpa timezone dapat menjatuhkan laporan umur stok

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_legacy_compatibility.

**Letak:** [backend/services/stock_analytics_service.py:33](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L33).



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

> Periksa `D4-STOCK-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Normalisasi timezone pada boundary parsing dan tentukan kebijakan tanggal legacy. Jangan mengubah data historis diam-diam tanpa aturan timezone yang disetujui. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Date-only, ISO dengan offset, Z, kosong dan tanggal invalid ditangani deterministik tanpa exception server; aging hari diperiksa di batas WIB.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FIN-01 — Control Tower menggabungkan AR semua entitas ketika parameter entitas dihilangkan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/finance_analytics.py:68](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/finance_analytics.py#L68).



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

> Periksa `D4-FIN-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Resolve effective scope sekali dan teruskan ke setiap service. Bedakan active, selected dan all secara eksplisit. All harus tetap dibatasi allowed entity set dan tidak memakai None ambigu. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Default/header A sama dengan explicit A; B dan all memiliki angka terpisah yang benar. Rekonsiliasi cash+AR−AP dalam scope identik. Uji allowed subset.

**Hubungan dengan catatan lain:** D4-SALES-02

## D4-SALES-01 — Target penjualan dan penagihan tidak mengikuti scope entitas

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_force_service.py:155](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_force_service.py#L155).



**Tampilan / rantai terkait:** Sales Home / Sales Force: target, achievement, komisi tier · Target entitas → KPI scoped → denominator target.

**Penyebab:** Lookup target hanya sales_id dan period, tanpa entity_id. Target A dapat menjadi pembagi KPI B. Probe menggunakan satu target sah di A, tidak mengasumsikan public API mampu membuat dua target paralel yang tidak didukung.

**Dampak dan batas interpretasi:** B tidak punya target namun memperoleh 100 dari A. Achievement dan ambang insentif tier dapat salah walaupun numerator KPI sudah benar.

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

> Periksa `D4-SALES-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan kontrak target per-entity/global; selaraskan schema, uniqueness/upsert dan query untuk target_sales serta target_collection. Nilai tidak dikonfigurasi harus dibedakan dari nol. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Target A100; B tidak ada → B tidak memakai 100. A/B/all, period month/quarter/year, fallback legacy dan tier boundary diuji tanpa penggandaan target.

**Hubungan dengan catatan lain:** D4-SALES-03

## D4-SALES-02 — Sales Home masih menampilkan order dan piutang lintas entitas di kartu pelanggan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/home_service.py:59](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/home_service.py#L59).



**Tampilan / rantai terkait:** Sales Home: pelanggan, AR, recent_orders · Customer master → SO entity → credit → home.

**Penyebab:** Home memfilter customer menurut A, tetapi memanggil compute_customer_credit tanpa entity dan mengambil recent SO customer tanpa entity. Perbaikan KPI di sales_force tidak menyelesaikan consumer home ini.

**Dampak dan batas interpretasi:** Customer A mempunyai SO A100 dan SO B700: kartu A outstanding 800, seharusnya 100; recent_orders berisi SO B. Dalam model pelanggan lintas entitas ini bukan pelanggaran producer, tetapi consumer tidak membatasi dokumen.

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

> Periksa `D4-SALES-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Teruskan effective entity ke credit helper dan query recent orders. Selaraskan home/KPI/aging sehingga konteks aktif bermakna sama, serta lindungi all dengan allowed scope. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Home A AR100 dan hanya SO A; Home B700; all 800 bila diizinkan. Customer dengan assigned-sales berubah dan SO tim lintas entitas tidak menghasilkan salah atribusi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-SALES-03 — Komisi per-SKU memasukkan SO tim sales milik entitas lain

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_force_service.py:253](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_force_service.py#L253).



**Tampilan / rantai terkait:** Sales Force: incentive, commission history dan accrual · SO sales_team → payment → incentive rate → payroll/finance liability.

**Penyebab:** Query komisi OR customer assigned / sales_team tidak menambahkan entity_id pada SO. KPI dan rate scoped A, tetapi basis commission dapat berasal dari B.

**Dampak dan batas interpretasi:** SO B paid 900 dengan 9 unit, sales S100% dan rate A1: KPI collected A0, insentif 9. Angka ini dapat dipakai proses accrual; bukan hanya chart kosmetik.

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

> Periksa `D4-SALES-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan satu eligible-order scope untuk KPI, collection allocation dan komisi. Query OR attribution harus dibungkus scope entity/status/period. Hitung cost per SO owner; jangan rate A mengalikan transaksi B. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** A tanpa SO memperoleh 0 walau S masuk tim B. A/B/all, shared customer, split team, partial receipt, return/void dan accrual ulang harus memenuhi konservasi serta idempotensi.

**Hubungan dengan catatan lain:** D4-SALES-01

## D4-FIN-02 — Forecast kas memakai basis AR dan termin berbeda dari AR kanonis

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/cashflow_forecast_service.py:66](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cashflow_forecast_service.py#L66).



**Tampilan / rantai terkait:** Finance Cashflow Forecast: inflow, due bucket, projected cash · Payment profile/SO terms → outstanding AR → cash forecast.

**Penyebab:** NON_AR_METHODS didefinisikan tetapi tidak dipakai, projection tidak memuat payment_profile_method. Due date dihitung dari default pelanggan terkini, mengabaikan payment_term_days snapshot SO; term 0 juga berubah 30 karena or30.

**Dampak dan batas interpretasi:** SO tunai unpaid 200 menjadi inflow AR200. SO tempo dengan snapshot 90 hari/default customer 30 diproyeksikan60 hari terlalu cepat. Risiko optimisme likuiditas dan bucket overdue salah.

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

> Periksa `D4-FIN-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Reuse sumber AR kanonis untuk eligibility, net outstanding, method dan due date. Forecast boleh punya skenario sendiri hanya jika dipisahkan dari confirmed receivables dan diberi label/asumsi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Tunai tidak masuk AR forecast; tempo 90 mengikuti SO meski profile diubah 30; termin 0 tetap 0. Return/credit note, DP, partial receipt dan closing/reversal harus cocok dengan aging pada snapshot yang sama.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FIN-03 — Revenue profitabilitas memasukkan PPN included dan mengabaikan diskon header legacy

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/profitability_service.py:118](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/profitability_service.py#L118).



**Tampilan / rantai terkait:** Profitability: revenue, margin, dimension totals dan monthly trend · SO pricing/discount → profitability → management decision.

**Penyebab:** Revenue langsung menjumlahkan line_total. Pada harga tax included, field ini masih memuat PPN; revenue kanonis adalah grand_total−ppn_amount. Shape legacy dengan diskon order terpisah juga tidak dialokasikan. Current create_order memaksa manual order discount=0, sehingga contoh diskon header tidak digeneralisasi sebagai alur SO baru.

**Dampak dan batas interpretasi:** Pricing producer asli pada entitas PKP dengan pengaturan ppn_mode=included menghasilkan revenue laporan 1000 meski nilai net setelah PPN lebih kecil. Semua dimensi/trend mewarisi PPN sebagai pendapatan. Contoh legacy baris 1000−diskonheader 100 menjadi 1000 vs net 900 dipertahankan dengan label legacy.

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

> Periksa `D4-FIN-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan shared net revenue allocation seperti fact sales dengan residual rounding yang terkontrol. Ambil grand_total−ppn_amount sesuai kontrak kanonis, dan jangan mengurangi diskon item dua kali ketika line_total sudah net. Jelaskan return/void dan legacy header discount. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Harga included 1000: Σrevenue harus grand_total−ppn_amount dari producer pricing; excluded dan non-PKP tetap benar. Legacy ordergross 1000−headerdisc 100=net 900 bila shape masih didukung. Semua dimensi, residual cent dan credit return direkonsiliasi.

**Hubungan dengan catatan lain:** D4-AI-04, D4-FIN-04

## D4-FIN-04 — Label pendapatan realisasi sebenarnya memakai pesanan reserved dan WAC terkini

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/profitability_service.py:19](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/profitability_service.py#L19).



**Tampilan / rantai terkait:** Profitability: Pendapatan (Realisasi), HPP (WAC), Marjin Kotor · SO reserved/confirmation → shipment/GL → report definition.

**Penyebab:** SOLD_STATUSES memasukkan confirmed dan reserved, tanggal memakai created_at SO, biaya dihitung dari WAC saat query. Ini analisis nilai pesanan dengan biaya kini, bukan otomatis realisasi shipment/GL historis.

**Dampak dan batas interpretasi:** SO reserved 100 tanpa shipment/GL memberi Pendapatan (Realisasi)100. Current WAC bukan dengan sendirinya bug untuk estimasi; masalahnya kontrak label dan interpretasi. Probe hanya membuktikan reserved revenue, bukan semua skenario historical cost.

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

> Periksa `D4-FIN-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pilih dan dokumentasikan metrik booked-order estimate vs realised revenue/margin. Jika realisasi, gunakan shipped/recognized amount serta cost snapshot yang sesuai. Jika tetap SO/WAC kini, ubah label/basis dan pisahkan estimator dari GL. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Reserved menunjukkan estimasi 100 dan realisasi 0 dalam metrik berbeda. Partial shipment, tanggal order vs dispatch, return, landed adjustment dan perubahan WAC memiliki perilaku terdefinisi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-01 — Analytics AP mengabaikan fallback vendor bill yang masih dipakai sumber kanonis

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_legacy_compatibility.

**Letak:** [backend/services/analytics_engine.py:288](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_engine.py#L288).



**Tampilan / rantai terkait:** Tanya KN / metric AP outstanding · Vendor bill legacy → bill_financials → analytics AP.

**Penyebab:** AP analytics hanya grand_total−amount_paid. bill_financials mendukung grand_total0 dengan total_amount fallback. Dokumen legacy yang sah jadi hilang dari analytics.

**Dampak dan batas interpretasi:** Billtotal 125, paid 25, grand_total0: sumber kanonis outstanding 100, analytics tidak menghasilkan baris (praktis 0).

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

> Periksa `D4-AI-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Normalisasi amount melalui satu kontrak bill financials yang juga dapat dieksekusi agregasi. Jangan membuat fallback berbeda antar aging, forecast, BI dan Tanya. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Grand_total positif, grand_total0 dengan total_amount, paid partial, legacy missing field, posted/void dan multicurrency jika didukung: outstanding konsisten dengan canonical.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-02 — Metric pelanggan baru mengabaikan scope lini

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_engine.py:168](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_engine.py#L168).



**Tampilan / rantai terkait:** Tanya KN / Analytics: new customer by line · Custom role line → fact_sales_lines → customer metric.

**Penyebab:** _src_fact_new tidak memakai sc.line_q sebagaimana sumber fact lain. Filter woven tetap menghitung customer knitting-only.

**Dampak dan batas interpretasi:** Dalam scope woven, satu customer yang hanya membeli knitting terhitung sebagai pelanggan baru 1, seharusnya 0 sesuai scope yang diminta.

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

> Periksa `D4-AI-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan scope/line policy bersama sebelum first-purchase grouping, termasuk keputusan apakah first berarti first ever atau first di lini. Jangan hanya filter sesudah agregasi first. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Knitting-only excluded woven; customer pernah membeli knitting lalu pertama woven diuji menurut definisi yang disetujui. Entity/owned-customer/role dimensi tetap enforced.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-03 — Refresh fact sales menghapus data lama sebelum replacement berhasil

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_facts.py:146](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_facts.py#L146).



**Tampilan / rantai terkait:** Tanya KN / analytics fact refresh · SO source → ETL/fact refresh → dashboards.

**Penyebab:** _write melakukan delete semua fact SO yang direfresh lalu insert_many. Bila insert gagal sebelum write, projection lama hilang walaupun source SO tetap ada.

**Dampak dan batas interpretasi:** Factrow 1 menjadi 0 setelah fault insert. Analitik/AI dapat memberi angka 0 saat refresh gagal; ini kerusakan read model, bukan bukti GL atau SO hilang.

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

> Periksa `D4-AI-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan generation staging + atomic publish pointer, transaction, atau deterministic upsert + retire stale rows hanya setelah replacement lengkap. Simpan sync progress dan expose freshness/error. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum/sesudah tiap write tidak membuat complete snapshot lama hilang. Retry dan dua worker tidak duplicate fact; Σfact sama source valid, invalid schema tidak menurunkan seluruh dataset.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-04 — Pembulatan alokasi tim sales tidak mengonservasi nilai dokumen

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_facts.py:118](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_facts.py#L118).



**Tampilan / rantai terkait:** Fact Sales / Tanya KN: revenue by sales dan total · SO split sales → rounded fact rows → analytics sums.

**Penyebab:** Setiap bagian dibulatkan independen ke2 desimal tanpa menempatkan residual pada baris deterministik.

**Dampak dan batas interpretasi:** Tim dua anggota PIC/co dengan split 50/50 memenuhi aturan maksimaldua anggota saatini. Net 1.01 menjadi 0.51+0.51=1.02. Perbedaan kecil per dokumen dapat terakumulasi; gunakan satuan uang sesuai kontrak sebenarnya.

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

> Periksa `D4-AI-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Alokasikan dalam minor units/Decimal, gunakan largest-remainder atau residual akhir deterministik untuk gross/net/PPN. Konservasi harus terjaga pada semua grouping. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Net 1.01 dibagi 2 anggota 50/50 tetap total 1.01; fractionaldiscount+tax,10 lines×2 sales, negative return dan replay sync tidak mengubah total/identity. Data legacy dengan anggota lebihbanyak, bila masihdibaca, tidak boleh merusak konservasi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-05 — Stok tersedia dan reserved di live analytics serta snapshot mengabaikan reservasi parsial

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_snapshots.py:18](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_snapshots.py#L18).



**Tampilan / rantai terkait:** Tanya KN: available/reserved stock dan historical stock · Partial cut reservation → inventory_balances / rolls → live/snapshot analytics.

**Penyebab:** Live _src_stock dan snapshot_stock menggolongkan seluruh length_remaining menurut status roll. Roll available dengan length_reserved3 tetap dihitung available 10/reserved 0.

**Dampak dan batas interpretasi:** Original roll helper membuat roll 10 dan reserve 3; SSOTbalance free 7/reserved 3. Analytics dan snapshot masing-masing 10/0. Sales/MD mendapat available yang berlebihan.

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

> Periksa `D4-AI-05` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan canonical physical/free/reserved definition yang mengakomodasi whole-roll dan partial-length. Pisahkan availability fisik vs ATP vs ready-to-dispatch; jangan memperbaiki hanya snapshot sementara live tetap berbeda. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Available roll 10 reservedlength 3 → free 7/reserved 3; whole reserved 10→free 0/reserved 10. Hold/quarantine, makloon-reserved, cut complete/release dan snapshotday diuji live=historical snapshot saat titik waktu sama.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-06 — Total quantity lintas produk menjumlahkan meter dengan kilogram

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_engine.py:565](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_engine.py#L565).



**Tampilan / rantai terkait:** Tanya KN metric tables: totals dan shares · Product base UOM → query group_by product → quantity total.

**Penyebab:** Unit guard hanya menambahkan unit ketika group_by tidak memuat product/unit. Mixed-unit detection hanya berjalan jika unit menjadi dimensi. Group product dapat mengembalikan meter/kg dengan total tunggal.

**Dampak dan batas interpretasi:** Stock 10 meter +5kg tampiltotal 15, yang tidak punya arti dimensional. Row bisa benar tetapi total/share menyesatkan.

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

> Periksa `D4-AI-06` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Lacak unit fisik dari metadata row walau dimensi product dipilih. Quantity mixed tidak memiliki grand total; kelompokkan per unit atau konversi eksplisit hanya dalam dimensi kompatibel dengan faktor tersimpan. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Product 10m+5kg → total null/N/A dan per-unit 10m/5kg;10m+5m→15m. Shares mixed quantity tidak dihitung silang unit; salesmoney tetap boleh dijumlah.

**Hubungan dengan catatan lain:** D4-WMS-03

## D4-CASH-01 — Saldo awal kas kecil berpindah menjadi kas besar setelah transaksi terakhir di-void

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/cash.py:103](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/cash.py#L103).



**Tampilan / rantai terkait:** Cash Dashboard: opening kas kecil/besar dan saldo · Bank/cash account opening → petty transactions → void → summary.

**Penyebab:** Jenis saldo awal ditentukan oleh account_id yang muncul pada transaksi kas kecil aktif. Master tidak memiliki field cash_type untuk klasifikasi tetap; void transaksi terakhir membuat account keluar dari kecil_ids.

**Dampak dan batas interpretasi:** Opening 1000 yang semula kas kecil menjadi kasbesar 1000 setelah transaksi 10 di-void, padahal opening master tidak berubah. Total cash bisa tetap benar namun split kategori salah.

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

> Periksa `D4-CASH-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tetapkan account classification atau mapping eksplisit yang tidak bergantung ada/tidak transaksi. Rancang migration/legacy unknown; jangan menebak dari transaksi terkini atau mengarang field schema sudah ada. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Void/delete transaksi terakhir tidak mengubah jenis opening. Account tanpa transaksi, legacy tanpa mapping, beberapa entitas, cash deposit transfer dan preview compare harus konsisten.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-DASH-01 — Batas katalog 3.000 SKU masih menghilangkan master dan cadangan pada KPI

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/dashboard.py:37](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/dashboard.py#L37).



**Tampilan / rantai terkait:** Dashboard summary: total available dan product lookup · Product master → makloon reservation → dashboard ATP/availability.

**Penyebab:** Patch menaikkan batas master dari 100 ke3000. KPI balance menghitung semua 3003 SKU, tetapi pengurangan material reservation hanya menjelajah 3000 master yang dimuat. Respons tidak menyediakan continuation untuk master yang hilang.

**Dampak dan batas interpretasi:** Kasus 103 SKU sekarang PASS. Pada 3003 SKU ×10 dengan cadangan 8 yang sah pada SKU terakhir, KPI tersedia 30030 padahal seharusnya 30022; hanya 3000 master dikirim. Ini perbaikan parsial, bukan temuan cap 100 yang masih diklaim terbuka.

- `D4-DASH-01-master-window-reservation` — expected `850`; actual `850.0`; `pass`.
- `D4-DASH-01-master-completeness` — expected `103`; actual `103`; `pass`.
- `D4-DASH-01-latest-cap-master` — expected `3003`; actual `3000`; `observed_difference`.
- `D4-DASH-01-latest-cap-reservation` — expected `30022`; actual `30030.0`; `observed_difference`.

```python
  34:     # `apply_scope` hanya mengikat peran `sales`; sales_admin/finance/manager/
  35:     # admin/warehouse tetap melihat keseluruhan pesanan seperti sebelumnya.
  36:     order_scope = sales_ownership.apply_scope(scope, actor)
  37:     products_raw = await db.products.find({}, {"_id": 0}).to_list(3000)
  38:     # S#096 — HPP turunan pembelian (WAC roll) untuk layar Master Produk; diredaksi strip_cost_fields per peran.
  39:     from services import costing_service as _cs
  40:     for _p in products_raw:
  41:         try:
  42:             _w = await _cs.wac_for_product(_p["id"], product=_p)
  43:             _p["hpp"], _p["hpp_source"] = float(_w.get("wac") or 0), _w.get("source", "")
  44:         except Exception:  # noqa: BLE001
```

**Prompt perbaikan:**

> Periksa `D4-DASH-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Agregasi summary harus memakai seluruh scope yang sama dan sumber reservasi kanonis. Pagination untuk daftar tidak boleh mempengaruhi total. Uji semua bounded helper yang dipakai metrik. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Kasus 103 serta 3003 SKU lengkap lewat pagination/search yang benar; KPI 30022 dihitung independen dari window master. Uji juga lebih dari 5000 balance agar agregasi tidak bergantung batas client list.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-HR-01 — Payroll gabungan memakai satu run pada KPI dan menimpa run lain pada trend

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/hr_analytics_service.py:146](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_analytics_service.py#L146).



**Tampilan / rantai terkait:** HR Analytics: payroll cost, gross/net/BPJS/employee trend · Payroll runs perentity → grouped period → HR cards/charts.

**Penyebab:** KPI find_one(period); trend map period diberi assignment sehingga run berikut menimpa sebelumnya. Dua entitas dalam bulan sama tidak diaggregate.

**Dampak dan batas interpretasi:** RunA 100 +B200: kartu 100, trend 200, total seharusnya 300. Ini error analitik; probe tidak membuktikan GL payroll posting salah.

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

> Periksa `D4-HR-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Aggregate posted/eligible runs perperiod/selectedentity dengan lifecycle jelas, hindari menghitung draft+replacement ganda. Bedakan sum employees vs distinctpeople jika employee shared. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** All gross 300/net 270, A100/B200, chart=card. Draft/replaced/void run tidak double-count; BPJS/PPH dan employee basis diuji.

**Hubungan dengan catatan lain:** D4-HR-02

## D4-HR-02 — Turnover menggunakan waktu edit data sebagai waktu karyawan keluar

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/hr_analytics_service.py:136](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_analytics_service.py#L136).



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

> Periksa `D4-HR-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tambahkan effective status-transition/separationdate dengan audit history dan backfill yang eksplisit. Perubahan profil tidak mengubah tanggal keluar. Definisikan numerator/denominator turnover. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** KeluarJuli lalu editOktober: Juli 1, Oktober 0. Rehire, koreksi status, delete/archival dan transferentity memiliki treatment terdefinisi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-WMS-01 — RFID RED hari ini pada Warehouse Health memakai hari UTC

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/wms_health_service.py:28](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L28).



**Tampilan / rantai terkait:** Warehouse Health: red_reads_today · RFID timestamp UTC → business day WIB → health card.

**Penyebab:** Filter today memakai prefix tanggal UTC. Operasi gudang lokal menggunakan WIB sehingga antara 00:00–06:59 WIB hari bisnis berbeda.

**Dampak dan batas interpretasi:** Freeze 01Oct01:00WIB: read 30Sept23:00WIB dihitung hariini. Dua read menghasilkan 2, seharusnya hanya 1.

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

> Periksa `D4-WMS-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan range [WIBdaystart, nextdaystart) dikonversi UTC. Jangan memakai regex prefix date atau mencampur string timestamp offset berbeda. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** 23:59WIB yesterday excluded;00:00/06:59 todayincluded; timezone UTC/Z/offsetnormalized. Chart dan KPI memakai satu batas hari bisnis.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-WMS-02 — Cycle count terbaru yang belum selesai menghapus angka akurasi terakhir

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/wms_health_service.py:71](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L71).



**Tampilan / rantai terkait:** Warehouse Health: last cycle count / accuracy · Cycle count open → assessed/approved → warehouse health.

**Penyebab:** Service memilih dokumen terbaru tanpa mensyaratkan accuracy valid/status selesai dan tidak mengirim status. Frontend memasang suffix% walau accuracy tidak ada.

**Dampak dan batas interpretasi:** Count terukur 95%, lalu count baruopen: last_cc memilihopen tanpa angka. Hasilnya angka akurasi hilang/placeholder ambigu, bukan bukti 0% ditampilkan.

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

> Periksa `D4-WMS-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan latestcountstatus dan lastmeasuredaccuracy. Pilih count terukur sesuai lifecycle bisnis (bukan secara arbitrer selaluapproved) dan tampilkan N/A untuk belum dinilai. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Openbaru tidak menimpa lastmeasured 95%; UI menunjukkan statusopen. Measured 0% harus tetap 0% dan dibedakan darinull; rejected/void count tidak dijadikan valid measurement.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-WMS-03 — Utilisasi gudang mengabaikan struktur Rack→Level→Bin yang didukung master

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/reporting.py:203](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/reporting.py#L203).



**Tampilan / rantai terkait:** Manager Dashboard: warehouse capacity/utilization · Warehouse structure → location flattening → capacity dashboard.

**Penyebab:** Producer warehouse_structure menyimpan bins di rack.levels[].bins. Consumer reporting hanya rack.bins legacy, sehingga capacity 0 dan utilization 0 meski lokasi punya capacity.

**Dampak dan batas interpretasi:** Struktur dibuat melalui helperoriginal: warehouse_locations capacity 100; /reports/warehouse-utilization capacity 0. Dapat menyamarkan penuh/tidaknya gudang.

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

> Periksa `D4-WMS-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Reuse canonical location traversal yang mendukung legacy dan level. Tegaskan unit kapasitas dan pisahkan mixedunitstock; jangan membagi meter+kg terhadap denominator yang tidak jelas. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Rack→Level→Bins 100 tampilcapacity 100; legacyrack.bins tetap benar dan tidak dihitungdua kali. Multiunit/capacity 0/owner shares/locationinactive diuji.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-MKT-01 — Reach agregat post disajikan ulang sebagai reach tiap platform dan akun

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/marketing_ext.py:137](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/marketing_ext.py#L137).



**Tampilan / rantai terkait:** Marketing Dashboard: by_platform dan by_account · Post multi-platform → aggregate metrics → channel breakdown.

**Penyebab:** Satu metrics aggregate post ditambahkan penuh ke setiap platform/account. Tidak ada pengukuran per-channel tersimpan, sehingga channel reach bukan actual channel measurement. Kelompok overlapping boleh nonadditive hanya bila kontraknya jelas.

**Dampak dan batas interpretasi:** Post reach 100 padaIG+TikTok: KPI 100, jumlahbyplatform 200 dan byaccount 200. Jangan menebak channel reach 50/50; data actual belum tersedia.

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

> Periksa `D4-MKT-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan apakah breakdown merupakan shared post attribution atau measurement perchannel. Jika shared, label nonadditive dan jangan total ulang. Jika actual, simpan metrics perplatform/account dengan provenance/time dan aggregate dedup sesuai definisi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Postmulti-channel 100 tidak ditampilkan seolah masing-masingpunya actual 100 tanpa keterangan. Separate metrics 30/70 hanya jika benar-benar diukur. Reachunique crosschannel tidak disimpulkan dari penjumlahan biasa.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-RND-01 — KPI R&D menggabungkan orang berbeda yang mempunyai nama sama

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/rnd_kpi_service.py:153](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rnd_kpi_service.py#L153).



**Tampilan / rantai terkait:** R&D designer/MD KPI, approval performance · Round performer identity → names → KPI groups.

**Penyebab:** Round producer menyimpan performed_by_user_id, tetapi KPI memakai performed_by/opened_by/created_by displayname sebagai identity. Dua user dengan nama sama menjadi satu baris.

**Dampak dan batas interpretasi:** Dua round dengan U1 danU 2 sama displayname menghasilkan 1 pelaksana, seharusnya 2. Nama berubah juga dapat memecah histori orang yang sama.

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

> Periksa `D4-RND-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Group stable user_id/employee_id dan render displayname sebagai label. Legacy name-only perlu mapping ambiguity explicit, bukan autojoin semua nama. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** U1/U2 nama sama→2KPI; U1 ganti nama→1 history. Fallbacklegacyambiguous ditandai, customroleline/roundtypefilter tetap berlaku.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FE-01 — Grafik velocity Manager selalu memotong menjadi 14 hari

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [frontend/src/features/manager/ManagerDashboard.jsx:100](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/manager/ManagerDashboard.jsx#L100).



**Tampilan / rantai terkait:** Manager Dashboard: periode 7/30/90 vs velocity chart · Period selector → reporting velocity → frontend slicing.

**Penyebab:** Dataset velocity dari API dipotong slice(-14) tanpa mengikuti period pilihan.

**Dampak dan batas interpretasi:** JavaScript asli expression diuji: input 7 tampil 7(control), input 30/90 masing-masing 14. Judul/periode dapat memberikan kesan dataset lengkap.

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

> Periksa `D4-FE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan range period yang sama dengan request atau label 14 hari terakhir secara eksplisit jika itu tujuan grafik. Jangan memotong data tanpa indikasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Periode 7/30/90 menunjukkan dataset sesuai tanggalpilihan; emptydays tetapkontrak API, batas tanggal/label tooltip diperiksa diUI.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FE-02 — Respons periode lama dapat menimpa grafik setelah periode diganti

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [frontend/src/features/manager/ManagerDashboard.jsx:69](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/manager/ManagerDashboard.jsx#L69).



**Tampilan / rantai terkait:** Manager Dashboard → pilihan periode / aging days pada entitas yang sama · Period 30 → period 90 → concurrent API load → old 30 response → React state.

**Penyebab:** load/useEffect tidak membatalkan request lama atau menjaga generation. Pergantian periode tidak remount komponen; request 30 yang selesai setelah 90 menulis ulang data. App.js L528 memakai key selectedEntity, sehingga hipotesis awal pergantian entitas ditarik: probe lama melewati remount.

**Dampak dan batas interpretasi:** Original function load pada entitas A: respons periode 90 selesai dan field total_orders yang dipakai UI bernilai 90; respons periode 30 selesai belakangan lalu total_orders menjadi 30 saat pilihan masih 90. Bukti ini JavaScript function-level dengan transport terkontrol, bukan browser E2E. Klaim entity-overwrite pada draf historis tidak dipakai sebagai temuan.

- `D4-FE-02-after-current-period-response` — expected `90`; actual `90`; `pass`.
- `D4-FE-02-stale-period-overwrite` — expected `90`; actual `30`; `observed_difference`.

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

> Periksa `D4-FE-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Implement generation guard/AbortController yang melindungi seluruh setters termasuk loading/error pada pergantian periode, aging days dan refresh. Data beberapa endpoint harus satu request generation. Pertahankan remount entitas yang sudah ada; audit pola halaman lain dengan bukti terpisah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Pada entitas sama, period 30→90 dan respons out-of-order: grafik tetap 90; respons/error/finally 30 tidak mengubah state 90. Uji aging-days, refresh, unmount dan partial failure. Uji browser diperlukan untuk validasi rendered UI.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-TEST-01 — Tes konsistensi ATP dapat lulus walaupun mencatat mismatch

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** source_review_test_oracle.

**Letak:** [backend/tests/test_iter149_audit.py:116](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/tests/test_iter149_audit.py#L116).



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

> Periksa `D4-TEST-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Definisikan formulaavailability/ATP bersama timbisnis, buat independentoracle dengan fixture partialreserve/hold/pending/incoming. Tambahkan assertionmismatch dan test-negatif yangmemastikanoracle gagal terhadapmutasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** InjectwrongATP→testFAIL; correctformula→PASS. Uji fixture>100SKU, multiowner, pendingcut, externalincoming dan no-dependencydemoaccount.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-DATE-01 — Penjualan dan Home menggunakan bulan/tahun UTC yang berbeda dari periode bisnis WIB

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_force_service.py:27](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_force_service.py#L27).



**Tampilan / rantai terkait:** Sales KPI, commission period/history, Home periode default; consumer tanggal serupa perlu ditelusuri · UTC created_at/payment timestamp → period selection → target/commission/report.

**Penyebab:** _in_period memotong tanggal string tanpa konversi timezone. Home _current_month/_today_prefix juga memakai UTC. Transaksi normal pada tujuh jam pertama WIB di awal bulan/tahun dapat masuk periode sebelumnya. Analytics engine memiliki konversi WIB tersendiri, sehingga metrik antarmodul dapat berbeda.

**Dampak dan batas interpretasi:** Timestamp 30Sep18:00UTC adalah 01Oct01:00WIB: filterOctoberFalse, SeptemberTrue. Home defaultmasihSeptember/30Sep. Timestamp 31Dec18:00UTC ditolak dariyear 2027 meski tanggalbisnis 01Jan2027. Belum semua consumer polaUTC ini diuji runtime; jangan menganggap semuanya sudahconfirmed.

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

> Periksa `D4-DATE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan timezone bisnis/per-entity dan gunakan helper periode bersama untuk timestamp serta date-only. Buat range UTC dari batas periode WIB. Jangan hanya mengubah bulan default Home sementara filterSO/payment masih memotong stringUTC. Telusuri profitability monthly grouping dan Finance Tower period sebagai related static candidates. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Batas 23:59:59WIB dan 00:00WIB di awalbulan, kuartal dan tahun masuk periodeyangbenar; timestamp Z/+00/+07 serta date-only memiliki aturanjelas. KPI, target, commissionhistory, snapshot dan export pada filter sama harusrekonsiliasi.

**Hubungan dengan catatan lain:** D4-WMS-01, V3-DATE-01, D4-FIN-04

## D4-PLAN-01 — Rencana pembelian mencatat qty yang berbeda dari PR yang dirujuk

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/fulfillment_plan_service.py:133](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L133).



**Tampilan / rantai terkait:** Admin Sales → Rencana pemenuhan → riwayat dan qty sudah direncanakan · SO backorder → partial reorder → PR → keputusan ulang → rencana supply.

**Penyebab:** Helper lama menegaskan ulang PR yang masih terbuka berdasarkan product_id tanpa menambah qty. Planner baru tetap menulis qty permintaan sebagai qty pembelian baru dan _planned menjumlahkan setiap keputusan.

**Dampak dan batas interpretasi:** Kekurangan 100: keputusan awal membuat PR20. Keputusan berikut meminta 80, menunjuk PR20 yang sama, namun mencatat 80; planned_qty menjadi 100 sementara pasokan PR hanya 20. Tidak ada bukti PR kedua lahir dalam kasus sequential ini.

- `D4-PLAN-01-reaffirmed-qty` — expected `{"decision_qty": 20, "referenced_pr_qty": 20}`; actual `{"decision_qty": 80.0, "referenced_pr_qty": 20.0}`; `observed_difference`.
- `D4-PLAN-01-planned-conservation` — expected `20`; actual `100.0`; `observed_difference`.

```python
 130:                          "summary": f"{r['product_name']}: {r['backorder_qty']:g} transfer dari PT lain ({res.get('ref_number') or '-'})"})
 131:     rows = [_row(ln, ln["reorder"]) for ln in plan if ln["reorder"] > EPS]
 132:     if rows:
 133:         res = await fds._reorder_supplier(order, rows, actor, note)
 134:         for r in rows:
 135:             done.append({"mode": "reorder", "product_id": r["product_id"], "qty": r["backorder_qty"],
 136:                          "ref_type": res.get("ref_type"), "ref_id": res.get("ref_id"), "ref_number": res.get("ref_number"),
 137:                          "summary": f"{r['product_name']}: {r['backorder_qty']:g} PO ke supplier ({res.get('ref_number') or '-'})"})
 138:     for ln in plan:
 139:         if ln["wait"] > EPS:
 140:             done.append({"mode": "wait", "product_id": ln["product_id"], "qty": ln["wait"],
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan reaffirmation dari penambahan supply; pakai qty efektif dan per-line reference aktual. Jika perlu tambah 80, lakukan amendment atau PR delta terkontrol. Rekonsiliasikan planned_qty dari supply aktif per referensi unik, bukan penjumlahan narasi histori. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PR20 lalu permintaan 80 tidak boleh memberi kesan supply 100 bila PR tetap 20. Reaffirm 20 berulang tidak meningkatkan planned_qty. Cancel/convert/receive/amend PR harus memperbarui remaining supply; uji multi-SKU saat sebagian SKU sudah punya PR.

**Hubungan dengan catatan lain:** D4-PLAN-03, D4-PLAN-05

## D4-PLAN-02 — Baris produk ganda pada API rencana dapat membuat pembelian melebihi kekurangan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/fulfillment_plan_service.py:76](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L76).



**Tampilan / rantai terkait:** API pemenuhan; PR turunan yang dibuka MD · FulfillmentPlanIn.lines → _validate per baris → supplier PR.

**Penyebab:** Validasi mengecek setiap raw row terhadap shortage yang sama. Tidak ada unique product guard atau akumulasi total lintas baris. Dua row 100 masing-masing lolos pada shortage 100.

**Dampak dan batas interpretasi:** Service asli membuat satu PR berisi 200 untuk demand 100. UI normal mengirim satu baris per produk, tetapi schema dan router publik menerima list dengan duplikasi; qty guard tidak berlaku pada total efektif.

- `D4-PLAN-02-duplicate-product` — expected `100`; actual `200.0`; `observed_difference`.

```python
  73: def _validate(lines_in: List[Dict[str, Any]], opts: Dict[str, Any]) -> List[Dict[str, Any]]:
  74:     by_pid = {ln["product_id"]: ln for ln in opts["lines"]}
  75:     plan = []
  76:     for raw in lines_in or []:
  77:         ln = by_pid.get(raw.get("product_id"))
  78:         if not ln:
  79:             raise FulfillmentError("Barang ini tidak (lagi) punya kekurangan di pesanan — muat ulang.")
  80:         nm = ln["product_name"] or ln["product_id"]
  81:         stock = round(float(raw.get("stock_qty") or 0), 2)
  82:         reorder = round(float(raw.get("reorder_qty") or 0), 2)
  83:         wait = round(float(raw.get("wait_qty") or 0), 2)
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tolak duplikasi product_id atau gabungkan baris sebelum memvalidasi kapasitas/demand. Akumulasikan pula per product + source entity dan validasi finite positive quantities. Jangan memindahkan guard hanya ke UI. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Duplicate product 100+100 ditolak tanpa side effect; duplicate source allocations juga tidak melewati batas. Uji semua endpoint planner dan PR realization; request invalid tidak membuat PR/transfer/reservation.

**Hubungan dengan catatan lain:** D4-PLAN-01

## D4-PLAN-03 — Riwayat mengatakan pemenuhan penuh walaupun sebagian eksekusi gagal

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/fulfillment_plan_service.py:160](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L160).



**Tampilan / rantai terkait:** Admin Sales → Riwayat keputusan / scope · Stock fulfillment → interco failure → persisted decision → UI notification.

**Penyebab:** full dihitung dari seluruh qty permintaan pada plan, setelah _execute menangkap kegagalan yang hanya menyelesaikan sebagian done. Qty yang gagal tetap berkontribusi pada scope full.

**Dampak dan batas interpretasi:** Rencana stock 30 + interco 70 untuk 100: stock 30 berhasil, interco 70 ditolak karena kontrak internal belum tersedia. SO menyimpan parts 30 tetapi scope full dan summary Penuh. Tidak diklaim barang 100 sudah terkirim; kesalahannya pada state/riwayat pemenuhan.

- `D4-PLAN-03-partial-scope` — expected `{"scope": "partial", "actual_qty": 30}`; actual `{"scope": "full", "actual_qty": 30.0}`; `observed_difference`.

```python
 157:             raise
 158:         error = str(exc)
 159:     modes = {p["mode"] for p in done}
 160:     full = all(abs((ln["stock"] + ln["reorder"] + ln["wait"] + sum(x["qty"] for x in ln["interco"]))
 161:                    - ln["backorder_qty"]) <= EPS for ln in plan) and len(plan) == len(opts["lines"])
 162:     decision = {
 163:         "mode": next(iter(modes)) if len(modes) == 1 else "split",
 164:         "scope": "full" if full else "partial",
 165:         "by": actor.get("name", ""), "by_id": actor.get("id", ""), "by_role": actor.get("role", ""),
 166:         "at": now_iso(), "note": (note or "").strip()[:400],
 167:         "summary": ("Penuh" if full else "Sebagian") + " — " + "; ".join(p["summary"] for p in done),
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Hitung execution outcome dari hasil nyata tiap bagian; pisahkan planned coverage dari executed coverage. Simpan per-part succeeded/failed/pending beserta effective qty dan reference. Kegagalan parsial harus dapat dilanjutkan tanpa menjalankan ulang bagian yang sukses. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fixture stock 30/interco 70 fail mencatat partial 30, sisa 70 belum terpenuhi, dan error tetap terlihat. Retry hanya menjalankan sisa. Uji exception infrastruktur, failure sebelum record, dan zero actual stock setelah concurrent consumption.

**Hubungan dengan catatan lain:** D4-PLAN-04, D4-BACKORDER-01

## D4-PLAN-04 — Pesan kegagalan pemenuhan parsial terhapus oleh refresh otomatis

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** javascript_function_counterexample.

**Letak:** [frontend/src/features/sales_admin/FulfillmentDecisionDialog.jsx:59](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/sales_admin/FulfillmentDecisionDialog.jsx#L59).



**Tampilan / rantai terkait:** Dialog Rencana pemenuhan: ErrorNotice · POST partial failure → catch error → load GET → setError empty.

**Penyebab:** submit menaruh pesan error lalu memanggil load; saat GET sukses load menjalankan setError kosong sehingga pesan kegagalan dan informasi bagian yang telah diproses hilang.

**Dampak dan batas interpretasi:** Function asli menghasilkan error transitions kosong → Interco failed; stock 30 already executed → kosong. Operator kehilangan pesan penting sebelum melanjutkan. Bukti ini function-level JavaScript dengan transport terkontrol, bukan uji browser.

- `D4-PLAN-04-error-erased` — expected `"Interco failed; stock30 already executed and persisted"`; actual `""`; `observed_difference`.

```javascript
  56:       };
  57:       const res = await fulfillmentPlanDecide(orderId, body);
  58:       onDecided?.(`${res?.order_number || orderNumber}: ${res?.decision?.summary || "rencana pemenuhan tercatat."}`);
  59:     } catch (e) { setError(apiErrorText(e, "Gagal menjalankan rencana pemenuhan.")); load(); }
  60:     finally { setBusy(false); }
  61:   }
  62: 
  63:   return (
  64:     <div className="modal-overlay" data-testid="fulfill-dialog" onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
  65:       <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 920, maxHeight: "92vh", overflowY: "auto" }}>
  66:         <div className="flex flex-wrap items-start justify-between gap-2">
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan load error dari execution error dan pertahankan hasil partial sampai pengguna menutupnya. Refresh data tidak boleh menghapus pesan proses yang belum diakui. Jelaskan bagian sukses, gagal dan tindakan lanjutan. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** POST gagal parsial lalu GET sukses tetap menampilkan pesan dan bagian 30 yang sukses. GET gagal harus menampilkan kedua konteks dengan jelas. Lengkapi browser test tanpa mengubah oracle.

**Hubungan dengan catatan lain:** D4-PLAN-03, D4-FE-02

## D4-PLAN-05 — Pasokan masuk yang sama dapat direncanakan penuh untuk beberapa SO

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/fulfillment_plan_service.py:139](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L139).



**Tampilan / rantai terkait:** Rencana tunggu barang datang dan Pending SO coverage · PO incoming → pending SO matching → wait decision → janji pelanggan.

**Penyebab:** pending_so_board mencocokkan incoming penuh secara independen untuk tiap demand. Jalur wait pada planner hanya menambah narasi parts; tidak mencadangkan qty pasokan per PO/SO atau mengurangi remaining supply yang ditawarkan.

**Dampak dan batas interpretasi:** Satu PO100 dianggap tersedia untuk dua SO100; kedua keputusan wait 100 berhasil dan total rencana 200. Bila fitur hanya catatan indikatif, label penuh/covered dan janji harus diperbaiki; jangan menyamakan perkiraan dengan pasokan yang dialokasikan.

- `D4-PLAN-05-wait-supply-conservation` — expected `100`; actual `200.0`; `observed_difference`.

```python
 136:                          "ref_type": res.get("ref_type"), "ref_id": res.get("ref_id"), "ref_number": res.get("ref_number"),
 137:                          "summary": f"{r['product_name']}: {r['backorder_qty']:g} PO ke supplier ({res.get('ref_number') or '-'})"})
 138:     for ln in plan:
 139:         if ln["wait"] > EPS:
 140:             done.append({"mode": "wait", "product_id": ln["product_id"], "qty": ln["wait"],
 141:                          "promise_date": ln["promise_date"],
 142:                          "summary": f"{ln['product_name']}: {ln['wait']:g} tunggu barang datang"
 143:                                     + (f" (janji {str(ln['promise_date'])[:10]})" if ln["promise_date"] else "")})
 144: 
 145: 
 146: async def decide_plan(order_id: str, lines_in: List[Dict[str, Any]], actor: Dict[str, Any],
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-05` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bentuk pegging supply/demand per document line dengan remaining qty, entity, unit dan ETA, atau labelkan sebagai availability forecast non-exclusive. Untuk janji pemenuhan pasti, validasi dan claim supply harus atomik serta reversible. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PO100 dan dua SO100 hanya mengalokasikan 100 total. SO kedua menyisakan shortage 100 atau forecast yang jelas tidak dijamin. Receive/cancel/amend/reorder/transfer harus merekonsiliasi claim tanpa menjanjikan supply dua kali.

**Hubungan dengan catatan lain:** D4-SUPPLY-01, D4-PLAN-01

## D4-GLOBAL-01 — Barang datang 100 yard dilabelkan 100 meter pada katalog stok global

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_stock_service.py:44](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_stock_service.py#L44).



**Tampilan / rantai terkait:** POS desktop/mobile → Datang restock / Datang utk SO · PO document UOM → canonical conversion trail → global stock helper → product card base_unit.

**Penyebab:** apply_global menjumlahkan quantity dan received_qty dokumen secara mentah. Consumer memberi label product.base_unit. quantity_base/uom_trail yang benar dari producer PO tidak dipakai.

**Dampak dan batas interpretasi:** Public POST /purchase-orders menghasilkan quantity 100 yard dan quantity_base91.44 meter. Badge global mengembalikan incoming_restock_qty100, ditampilkan sebagai meter. Konversi producer benar; sumber angka consumer salah.

- `D4-GLOBAL-01-incoming-uom` — expected `91.44`; actual `100.0`; `observed_difference`.

```python
  41:             pid = it.get("product_id")
  42:             if pid not in idset:
  43:                 continue
  44:             open_qty = float(it.get("quantity", it.get("qty", 0)) or 0) - float(it.get("received_qty", 0) or 0)
  45:             if open_qty > 0.01:
  46:                 tgt = inc_so if (bound or it.get("source_so_id")) else inc_rs
  47:                 tgt[pid] = tgt.get(pid, 0.0) + open_qty
  48:     async for d in db.interco_transactions.find({"role": "buyer", "status": {"$in": INCOMING_INTERCO_STATUSES},
  49:                                                  "items.product_id": {"$in": ids}},
  50:                                                 {"_id": 0, "items": 1, "source_order_id": 1}):
  51:         for it in d.get("items") or []:
```

**Prompt perbaikan:**

> Periksa `D4-GLOBAL-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan outstanding dalam satuan dasar dari conversion trail producer dan konversi received quantity dengan unit yang sama. Terapkan ke SO-bound/restock, PO manual/PR/call-off dan interco. Jangan memakai angka fallback 1 untuk unit yang tidak bisa dikonversi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PO100 yard pada SKU meter → incoming 91.44 meter; setelah menerima 40 yard → remaining 54.864 meter sesuai presisi kanonis. Uji kg/gram, roll dengan document factor, landed/cost tidak tercampur qty, dan semua badge mobile/desktop.

**Hubungan dengan catatan lain:** D4-AI-06, D4-SUPPLY-01

## D4-SUPPLY-01 — Sisa PO diterima sebagian hilang dari incoming karena definisi status berbeda

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/roll_service.py:173](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L173).



**Tampilan / rantai terkait:** ATP, Pending SO, global POS incoming dan saran pengadaan · PO receipt → recompute_po_status partial → shared OPEN_PO_STATUSES → incoming supply.

**Penyebab:** Producer recompute_po_status menetapkan partial untuk PO yang baru diterima sebagian. OPEN_PO_STATUSES yang diimpor stock_bucket_service dan sales_stock_service tidak memasukkan partial. Normalisasi status tidak mengikuti state machine kanonis.

**Dampak dan batas interpretasi:** PO100 diterima 90: original recompute menghasilkan partial. Pending supply dan global incoming keduanya 0 padahal tersisa 10. Janji ke customer dan keputusan pembelian ulang dapat salah. Jalur _open_po_incoming juga membaca qty total pada status terbuka lain, perlu uji sisa, bukan sekadar memasukkan partial.

- `D4-SUPPLY-01-open-qty` — expected `10`; actual `0`; `observed_difference`.
- `D4-SUPPLY-01-global-partial` — expected `10`; actual `0.0`; `observed_difference`.

```python
 170: # KN-A11 — SATU definisi "PO masih terbuka / stok dalam perjalanan" untuk papan Stok/ATP,
 171: # Fulfillment Wizard, dan stock_bucket. `waiting_approval` sengaja TIDAK dihitung (belum
 172: # pasti dibeli); `receiving` dihitung karena sisa yang belum diterima memang masih di jalan.
 173: OPEN_PO_STATUSES = ["pending", "created", "approved", "sent", "receiving"]
 174: 
 175: PHYSICAL_STATUS_TO_BUCKET = {
 176:     "available": "available_qty",
 177:     "reserved": "reserved_qty",
 178:     "committed": "committed_qty",
 179:     "picked": "picked_qty",
 180:     "packed": "packed_qty",
```

**Prompt perbaikan:**

> Periksa `D4-SUPPLY-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Satukan definisi status open dengan producer lifecycle; hitung remaining qty dalam unit dasar, bukan ordered qty. Review seluruh importer OPEN_PO_STATUSES dan pembelian/GRN/reorder/forecast/ATP, dengan guard terminal dan tolerance policy. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PO100 received 90 → incoming 10; received 100/completed →0; closed_short/cancelled/rejected →0; receiving legacy tidak menambah seluruh ordered qty. Uji partial receipt, variance amend/close dan qty per roll.

**Hubungan dengan catatan lain:** V3-PO-01, V3-PO-02, D4-GLOBAL-01, D4-PLAN-05

## D4-BACKORDER-01 — Pemenuhan stok bersamaan mereservasi 160 untuk SO yang hanya kurang 100

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/backorder_service.py:82](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/backorder_service.py#L82).



**Tampilan / rantai terkait:** SO detail reserved/backorder, rencana pemenuhan, roll availability dan picking · Two admin stock fills → roll CAS reservations → stale whole SO arrays → allocations push.

**Penyebab:** Roll allocator menjaga stok fisik per roll, tetapi _fill_order tidak mengunci demand/version SO. Dua proses membaca shortage 100 yang sama, masing-masing reserve 80; $push mempertahankan allocations 160 sedangkan $set items/backorders menimpa state dari pembacaan lama 80/20.

**Dampak dan batas interpretasi:** Physical stock 200 memungkinkan dua reserve 80. SO allocations 160, item reserved 80, remaining backorder 20; demand 100 tidak konservatif. Barrier hanya mengatur urutan final write SO, business code dan allocator asli tidak diganti.

- `D4-BACKORDER-01-concurrent-fill` — expected `{"allocated_qty": 100, "item_reserved_qty": 100, "backorder_qty": 0}`; actual `{"allocated_qty": 160.0, "item_reserved_qty": 80.0, "backorder_qty": 20.0}`; `observed_difference`.

```python
  79:     _bo_set.update(stage_fields({**order, **_bo_set}))
  80:     await db.sales_orders.update_one(
  81:         {"id": order["id"]},
  82:         {"$set": _bo_set, "$push": {"allocations": {"$each": new_allocs}}})
  83:     # Auto-commit (4a): order sudah approved/confirmed → roll baru langsung di-commit.
  84:     if new_status in ("approved", "confirmed"):
  85:         from services.roll_service import set_order_rolls_status
  86:         await set_order_rolls_status(order["id"], "committed")
  87:     from dependencies import audit
  88:     await audit(actor_name, "backorder_auto_fulfilled", "sales_order", order["id"], {
  89:         "product_id": product_id, "qty_fulfilled": round(order_got, 2),
```

**Prompt perbaikan:**

> Periksa `D4-BACKORDER-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Claim demand atomik per SO line/version sebelum reserve supply, atau serialisasi operation yang dapat dipulihkan dengan idempotency dan CAS. Kegagalan CAS harus release/compensate allocation yang terlanjur dibuat. Jangan hanya mengganti $set menjadi $inc tanpa demand bound. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Dua request 80 pada shortage 100 tidak pernah menghasilkan reserve total>100; item/allocations/backorder/physical reserved balance sama. Uji dua SKU pada SO sama, auto GR fulfillment vs admin manual, retry, partial failure dan cancel bersamaan.

**Hubungan dengan catatan lain:** D4-PLAN-03, V3-MRES-01

## D4-CAP-01 — SKU yang benar-benar ada ditolak saat membuat PO setelah 1.000 master pertama

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/purchase_orders.py:407](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/purchase_orders.py#L407).



**Tampilan / rantai terkait:** Master Produk / katalog → Pembuatan PO → validasi produk · Expanded dashboard catalog → selected known SKU → PO create capped lookup → false 404.

**Penyebab:** Producer membangun lookup dari first 1000 product docs tanpa filter ID payload. Produk yang ada di luar window dianggap tidak ditemukan; cap 3000 pada dashboard tidak menutup batas 1000 producer.

**Dampak dan batas interpretasi:** Fixture 3003 SKU: PO untuk CAP 0001 berhasil 200; request setara untuk CAP 1002 mendapat 404 meskipun find_one memastikan master ada. Kegagalan ini mencegah procurement SKU sah; bukan hanya tampilan terpotong.

- `D4-CAP-01-purchase-known-sku` — expected `{"CAP0001": {"http_status": 200, "exists": true}, "CAP1002": {"http_status": 200, "exists": true}}`; actual `{"CAP0001": {"http_status": 200, "exists": true}, "CAP1002": {"http_status": 404, "exists": true, "detail": "Produk CAP1002 tidak ditemukan"}}`; `observed_difference`.

```python
 404:                         f"'{supplier_name}' di menu Pemasok terlebih dahulu."))
 405:     
 406:     # Validate products and calculate total
 407:     products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
 408:     # FASE F (PS-12) — jangan membelanjakan uang untuk barang yang spesifikasinya
 409:     # belum sah (konsep/labdip/proofing) atau sudah dihentikan.
 410:     from services import rnd_gate
 411:     await rnd_gate.assert_orderable(
 412:         [products[it.product_id] for it in payload.items if it.product_id in products],
 413:         where="Purchase Order")
 414:     raw_items = []
```

**Prompt perbaikan:**

> Periksa `D4-CAP-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Ambil master berdasarkan himpunan ID yang benar-benar diminta, lalu bandingkan missing IDs. Gunakan paginated search untuk UI dan aggregate independen untuk KPI. Review lookup sejenis pada SO/PR/amendment/receiving, bukan mengganti 1000 menjadi angka lebih besar. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PO untuk SKU pertama dan SKU 1003 sama-sama dibuat dengan source FK yang sah; SKU benar-benar tidak ada ditolak. Uji catalog 3003/large, PR→PO, call-off, same-SKU concurrency, grade/UOM/lifecycle guard tetap berlaku.

**Hubungan dengan catatan lain:** D4-DASH-01

## D4-ORDER-01 — Rata-rata pesanan membagi revenue seluruh pesanan dengan hanya 20 pesanan terbaru

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** public_api_to_original_javascript_counterexample.

**Letak:** [frontend/src/features/orders/OrderDashboard.jsx:74](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/orders/OrderDashboard.jsx#L74).



**Tampilan / rantai terkait:** Pesanan → Dasbor: jumlah orders, Rata-rata Pesanan, Top Customers, Status Distribution dan Expiring · Public /dashboard cap 20 → App state data.orders → OrdersView orders prop → OrderDashboard metrics; /sales-orders/stats/summary aggregate semua pesanan.

**Penyebab:** Patch revenue memakai summary.revenue[period].grand_total seluruh pesanan, tetapi denominator recentOrders.length tetap dari window 20. Server sudah menyediakan revenue.count untuk populasi dan status yang sama; consumer mengabaikannya. Top Customers dan status/pending/expiry juga memakai window lokal tanpa label cakupan. Halaman list memakai pagination dan summary server, sehingga list benar tidak membuktikan dasbor benar.

**Dampak dan batas interpretasi:** Fixture 30 SO confirmed 100 pada entitas dan periode sama: original public API memberikan orders 20 dan revenue 3000/count 30. Original JavaScript useMemo memberi totalRevenue 3000 (kontrol PASS), totalOrders 20 dan avg 150 padahal 100. Top Customers untuk customer yang sama hanya 2000 padahal 3000. Ini source-grain mismatch, bukan kesalahan operasi pembagian. Tidak ada klaim bahwa seluruh tabel latest 10 salah; batas 10 pada Recent Orders diberi label jelas.

- `D4-ORDER-01-revenue-control` — expected `3000`; actual `3000`; `pass`.
- `D4-ORDER-01-count` — expected `30`; actual `20`; `observed_difference`.
- `D4-ORDER-01-average` — expected `100`; actual `150`; `observed_difference`.
- `D4-ORDER-01-customer-revenue` — expected `3000`; actual `2000`; `observed_difference`.

```javascript
  71:       totalOrders: recentOrders.length,
  72:       pendingOrders: pendingOrders.length,
  73:       expiringSoon: expiringSoon.length,
  74:       avgOrderValue: recentOrders.length > 0 ? totalRevenue / recentOrders.length : 0,
  75:       topCustomers,
  76:       statusCounts,
  77:       recentOrders: orders.slice(0, 10)
  78:     };
  79:   }, [orders, timeRange, summary]);
  80:   
  81:   const formatCurrency = (amount) => {
```

**Prompt perbaikan:**

> Periksa `D4-ORDER-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan revenue.count sebagai denominator jika rata-rata didefinisikan atas status terpenuhi; definisikan totalOrders terpisah bila mencakup semua status. Hitung Top Customers, distribusi status, pending dan expiry di server dengan scope entity/sales-owner/line/periode yang sama. Label setiap pengecualian periode atau dataset parsial. Jangan memuat seluruh dokumen di browser untuk memperbaiki agregat. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** 30 SO confirmed 100 menghasilkan revenue 3000/count 30/avg 100 dan customer revenue 3000. Uji >20 dan >200, mix reserved/cancelled/fulfilled, periode 7/30/90, sales-owner, line scope dan perubahan filter. Bandingkan seluruh widget dengan source query independen; Recent Orders tetap boleh 10 dengan labelnya.

**Hubungan dengan catatan lain:** D4-DASH-01, D4-FE-01

## D4-CASE-01 — Refund store credit menjurnal pengurangan kewajiban dua kali dan menciptakan pendapatan semu

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_gl_counterexample.

**Letak:** [backend/services/finance_case_actions.py:238](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L238).

**Lokasi kode lain dalam rantai:** [backend/services/store_credit_service.py:286](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/store_credit_service.py#L286) · [backend/services/gl_service.py:2483](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L2483) · [backend/services/finance_case_actions.py:57](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L57).

**Tampilan / rantai terkait:** Finance → Pusat Kasus → Refund pelanggan → Saldo kredit toko; buku besar dan laporan laba rugi · Store credit producer → public case create/resolve → sc.adjust(-80) → GL adjustment → cash out 80 → GL cash → resolved.

**Penyebab:** act_refund_store_credit memakai adjust yang ditujukan untuk koreksi/hangus saldo. store_credit_service.adjust sudah memposting Dr2-1450/Cr4-9000, lalu _cash_txn kembali memposting Dr2-1450/CrKas. Dua jurnal masing-masing seimbang, tetapi kedua jurnal untuk satu refund mengurangi kewajiban dua kali.

**Dampak dan batas interpretasi:** Producer adjustment+100 menghasilkan saldo dan kewajiban 100. Public resolve refund 80 sukses 200; ledger pelanggan 20 dan kas keluar 80 benar. Jurnal refund mendebit kewajiban 160, mengkredit Other Income 80, dan saldo kredit GL menjadi-60 padahal ledger 20. Ini normal flow tanpa fault injection. Initial adjustment adalah producer sah; preceding return/CN producer tidak diklaim diuji dalam fixture ini.

- `D4-CASE-01-public-resolution-control` — expected `200`; actual `200`; `pass`.
- `D4-CASE-01-ledger-control` — expected `20`; actual `20.0`; `pass`.
- `D4-CASE-01-liability-debit` — expected `80`; actual `160.0`; `observed_difference`.
- `D4-CASE-01-phantom-income` — expected `0`; actual `80.0`; `observed_difference`.
- `D4-CASE-01-liability-ledger-reconciliation` — expected `20`; actual `-60.0`; `observed_difference`.

```python
 235:     if amount > bal + EPS:
 236:         raise CaseActionError(
 237:             f"Pengembalian {_rp(amount)} melebihi saldo kredit toko {_rp(bal)}")
 238:     entry = await sc.adjust(customer_id=cust, entity_id=ent, amount_signed=-amount,
 239:                             note=f"Dicairkan lewat kasus {case['number']}", actor=actor)
 240:     res = await _cash_txn(
 241:         direction="out", amount=amount, category="refund store credit",
 242:         description=f"Pencairan saldo kredit toko · {case['number']}",
 243:         entity_id=ent, account_id=p.get("account_id", ""),
 244:         cash_type=p.get("cash_type") or "kas_besar", ref_type="finance_case",
 245:         ref_id=case["id"], contra=gl.ACC_STORE_CREDIT, owner_entity_id=ent,
```

**Prompt perbaikan:**

> Periksa `D4-CASE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Sediakan operasi pencairan store credit dengan identitas aksi stabil: klaim saldo, buat satu jurnal DrStoreCredit/CrCash, lalu baris ledger menunjuk jurnal yang sama. Hindari memakai adjust/hangus yang menciptakan pendapatan. Pertahankan append-only ledger, legal entity dan referensi kasus. Audit redemption, reversal, return issue, backfill serta semua caller adjust agar GL dan saldo pelanggan tidak terpisah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Saldo 100, refund 80: cash 80, liability-debit 80, OtherIncome 0, ledger 20=GL20. Public response dan dokumen turunannya lengkap. Uji refund dari credit note asli, partial refund, dua klik, saldo tidak cukup, closed period, GL failure, ledger failure, retry dan reversal; tidak boleh ada journal/ledger yatim atau refund kedua.

**Hubungan dengan catatan lain:** V3-AR-01, D4-CASE-02

## D4-CASE-02 — Penyelesaian kasus keuangan dapat mengulang kas yang sudah tercatat setelah konflik atau kegagalan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_concurrency_and_retry_counterexample.

**Letak:** [backend/services/finance_case_actions.py:206](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L206).

**Lokasi kode lain dalam rantai:** [backend/services/finance_case_service.py:419](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_service.py#L419) · [backend/services/finance_case_actions.py:57](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L57) · [backend/services/finance_case_actions.py:253](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L253) · [backend/services/ar_receipt_service.py:159](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/ar_receipt_service.py#L159) · [backend/services/finance_case_actions.py:461](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L461) · [backend/services/finance_case_actions.py:482](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L482) · [backend/services/gl_service.py:467](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L467).

**Tampilan / rantai terkait:** Finance → Pusat Kasus → Refund uang muka / Pindah buku; Kas & Bank, saldo pelanggan, GL transit · Receipt deposit 100 → public case resolve → cash+GL before balance CAS → conflict/fault → same case retry; own-bank first leg → second-leg failure → retry.

**Penyebab:** finance_case_service.resolve tidak mengklaim action sebelum side effects dan baru menulis status di akhir. _cash_txn selalu membuat UUID baru; idempotensi jurnal per UUID kas tidak melindungi kasus/aksi. Refund mencatat kas sebelum CAS deposit. Pindah buku membuat dua leg berurutan tanpa checkpoint stabil yang dapat dilanjutkan.

**Dampak dan batas interpretasi:** Normal single refund 80 dari receipt deposit 100 benar: saldo 20/kas 80/Dr2-1400 80. Dua resolve yang dijadwalkan setelah sama-sama membaca saldo menghasilkan satu 200/satu 400 tetapi kas keluar 160; deposit CAS tetap 20. Fault sesudah kas+JE sebelum CAS, lalu retry kasus sama, juga kas 160/deposit 20. Pindah buku 80, first leg sukses dan second leg gagal; retry menghasilkan out 160/in80, kasus resolved, saldo transit debit 80. Supplier advance 100 lalu dua refund 80 menghasilkan cash-in160 dan saldo-60 karena unconditional $inc. Penetapan advance 100 gagal saat checkpoint kasus lalu retry menghasilkan saldo 200, sementara GL tetap 100. Refund pada state periode terkunci, tanpa injeksi kegagalan, menulis cash-out 80 posted sebelum GL ditolak; deposit tetap 100 dan kasus open. Supplier fixture dimulai dari original manual advance decision, dan closing memakai explicit closed-state fixture, bukan full vendor-payment/closing producer. Semua ini satu keluarga durability/action identity dan sequencing, bukan setiap subflow diberi ID bug terpisah.

- `D4-CASE-02-normal-refund-control` — expected `{"http": 200, "deposit": 20, "cash": 80, "liability_debit": 80}`; actual `{"http": 200, "deposit": 20.0, "cash": 80.0, "liability_debit": 80.0}`; `pass`.
- `D4-CASE-02-concurrent-cash` — expected `80`; actual `160.0`; `observed_difference`.
- `D4-CASE-02-concurrent-deposit-control` — expected `20`; actual `20.0`; `pass`.
- `D4-CASE-02-concurrent-http-control` — expected `[200, 400]`; actual `[200, 400]`; `pass`.
- `D4-CASE-02-failure-retry-cash` — expected `80`; actual `160.0`; `observed_difference`.
- `D4-CASE-02-failure-retry-deposit-control` — expected `20`; actual `20.0`; `pass`.
- `D4-CASE-02-bank-transfer-retry-total` — expected `{"in": 80, "out": 80}`; actual `{"in": 80.0, "out": 160.0}`; `observed_difference`.
- `D4-CASE-02-bank-transfer-transit` — expected `0`; actual `80.0`; `observed_difference`.
- `D4-CASE-02-supplier-producer-control` — expected `{"http": 200, "advance": 100}`; actual `{"http": 200, "advance": 100.0}`; `pass`.
- `D4-CASE-02-supplier-concurrent-cash` — expected `80`; actual `160.0`; `observed_difference`.
- `D4-CASE-02-supplier-concurrent-balance` — expected `20`; actual `-60.0`; `observed_difference`.
- `D4-CASE-02-supplier-advance-retry-balance` — expected `100`; actual `200.0`; `observed_difference`.
- `D4-CASE-02-supplier-advance-retry-journal-control` — expected `100`; actual `100.0`; `pass`.
- `D4-CASE-02-closed-period-cash` — expected `0`; actual `80.0`; `observed_difference`.
- `D4-CASE-02-closed-period-journal-control` — expected `0`; actual `0`; `pass`.
- `D4-CASE-02-closed-period-deposit-control` — expected `100`; actual `100.0`; `pass`.

```python
 203:     return {"documents": docs, "amount": total}
 204: 
 205: 
 206: async def act_refund_pelanggan(case: Dict[str, Any], p: Dict[str, Any],
 207:                                actor: Dict[str, Any]) -> Dict[str, Any]:
 208:     """Uang muka pelanggan dikembalikan (Dr 2-1400 / Cr Kas-Bank)."""
 209:     from services import ar_receipt_service as ar
 210:     cust = p.get("customer_id") or case.get("customer_id") or ""
 211:     amount = round(float(p.get("amount") or 0), 2)
 212:     dep = await ar.get_deposit_balance(cust)
 213:     if amount > dep + EPS:
```

**Prompt perbaikan:**

> Periksa `D4-CASE-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Terapkan durable operation identity per case+action/version serta atomic claim dengan precondition lifecycle. Klaim dana sebelum kas; simpan leg/checkpoint dan idempotency keys sebelum side effect. Retry melanjutkan leg yang belum selesai dan mengembalikan hasil committed beserta journal reference yang sudah ada, bukan None. Supplier advance mutation juga harus idempotent dan refund memakai balance CAS. Preflight closed period/account/entity sebelum cash atau balance diposting; failed fund/period claim tidak menulis posted cash. Crash recovery/compensation tidak boleh sekadar melepas lock lalu mengulang semua aksi. Audit seluruh executor playbook karena pola status di akhir dipakai bersama; jangan menganggap executor lain terbukti gagal hanya dari source ini. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Normal dan concurrent customer refund tetap satu cash 80/JE80/deposit 20; loser tidak meninggalkan cash. Supplier advance 100/refund 80: saldo 20, cash-in80; retry penetapan advance tidak menambah saldo kedua kali dan saldo=GL100. Semua fault boundary cash insert, JE, balance, case-status dan doc-link diuji. Own-bank transfer 80 setelah failure/retry harus out 80/in80/transit 0. Periode terkunci menolak sebelum cash/balance mutation; unlock sah berjalan normal. Dua request satu case dan dua case berbeda atas dana sama tidak overspend. Dokumen resolusi merujuk seluruh committed legs, reversal append-only, recovery tetap dapat berjalan setelah restart.

**Hubungan dengan catatan lain:** D4-CASE-01, V3-AR-01, V3-BANK-01

## D4-INTERCO-01 — Transfer roll retur dapat selesai memindahkan pemilik tetapi kehilangan jurnal pasangan dan dokumen pemulihan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_controlled_failure_counterexample.

**Letak:** [backend/services/gl_service.py:1333](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L1333).

**Lokasi kode lain dalam rantai:** [backend/services/return_service.py:1126](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_service.py#L1126) · [backend/services/roll_service.py:1519](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L1519) · [backend/routers/transfers.py:476](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/transfers.py#L476).

**Tampilan / rantai terkait:** Retur Jual → Roll released → Pindah kepemilikan; inventory/RFID owner, jurnal antarentitas dan histori transfer · Released return roll A → saga claim → execute_ownership_transfer toB → source JE → destination JE failure → ineffective rollback → retry.

**Penyebab:** return_service.transfer_return_roll_ownership memindahkan owner, lot, RFID owner, movements dan balances sebelum post_intercompany_transfer. Failure rollback mencari reserved_ref yang sudah dibersihkan oleh transfer sehingga owner tidak kembali. warehouse_transfers baru ditulis sesudah kedua JE. Helper GL memakai OR guard: ada salah satu sisi dianggap sudah selesai, tanpa mengisi sisi lain.

**Dampak dan batas interpretasi:** Normal kontrol sukses 200, ownerB dan JE kedua sisi. Fault terkontrol tepat sebelum original destination JE insert: roll/tag/lot sudahB, source JE100 ada, destination tidak ada, transfer doc 0. Parent saga dilepas. Retry helper mengembalikan already_posted dan tetap satu JE; retry API 400 karena pemilik saat ini sudahB. Fixture dimulai dari state released external-sales-return roll dengan original inbound writer dan metadata retur eksplisit; tidak diklaim full SO→retur approval producer atau physical gate telah diuji. Jalur return-origin internal-purchase tetap ditolak sesuai aturan yang sudah ada.

- `D4-INTERCO-01-normal-control` — expected `{"http": 200, "je_posted": true, "owner": "B"}`; actual `{"http": 200, "je_posted": true, "owner": "B"}`; `pass`.
- `D4-INTERCO-01-owner-after-failed-transfer` — expected `"A"`; actual `"B"`; `observed_difference`.
- `D4-INTERCO-01-transfer-history-after-failure` — expected `1`; actual `0`; `observed_difference`.
- `D4-INTERCO-01-rfid-owner-after-failure` — expected `"A"`; actual `"B"`; `observed_difference`.
- `D4-INTERCO-01-journal-pair-after-failure` — expected `["A", "B"]`; actual `["A"]`; `observed_difference`.
- `D4-INTERCO-01-helper-recovery-pair` — expected `2`; actual `1`; `observed_difference`.
- `D4-INTERCO-01-public-recovery` — expected `200`; actual `400`; `observed_difference`.

```python
1330:     # Idempotent guard (cek dua-sisi terpisah)
1331:     src_id = f"{tid}:src"
1332:     dst_id = f"{tid}:dst"
1333:     if await _already_posted("inter_company_transfer", src_id) or \
1334:        await _already_posted("inter_company_transfer", dst_id):
1335:         return {"posted": False, "reason": "already_posted", "total": 0.0}
1336: 
1337:     valuation = await _transfer_items_value_at_cost(transfer, src)
1338:     total = float(valuation["total"])
1339:     if total <= EPS:
1340:         return {"posted": False, "reason": "zero_cost", "total": 0.0,
```

**Prompt perbaikan:**

> Periksa `D4-INTERCO-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist intent transfer dengan operation ID dan cost snapshot sebelum pemindahan. Checkpoint owner/lot/tag/movements/GL tiap sisi; retry harus menyelesaikan missing leg secara idempotent. already_posted harus memeriksa pasangan lengkap dan nilai/ref yang sama, bukan OR existence. Gunakan compensation yang sadar state bila dipilih rollback. Terapkan perbaikan helper shared juga pada transfers.approve dan recovery sesudah crash tanpa memindahkan roll dua kali. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault destination JE, pair-link, transfer-doc insert, return-history write dan balances: hasil dapat dipulihkan sampai owner/lot/tag/ledger kedua PT/history konsisten, atau rollback penuh yang auditable. Satu source JE tidak dianggap selesai. Retry original API harus recover atau menunjukkan operation pending yang dapat dilanjutkan; concurrent request tidak membuat extra movements/JE. Kontrol internal-purchase return tetap menuju Retur Antar-PT.

**Hubungan dengan catatan lain:** D4-INTERCO-02, V3-MASTER-01

## D4-INTERCO-02 — Nilai transfer antarentitas memakai WAC sesudah stok sumber dipindahkan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_cost_snapshot_counterexample.

**Letak:** [backend/services/gl_service.py:1337](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L1337).

**Lokasi kode lain dalam rantai:** [backend/services/return_service.py:1206](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_service.py#L1206) · [backend/routers/transfers.py:435](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/transfers.py#L435) · [backend/services/costing_service.py:45](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/costing_service.py#L45).

**Tampilan / rantai terkait:** Pindah kepemilikan roll retur / Transfer antarentitas at-cost → GL persediaan dan IC-AR/IC-AP · Costed roll A → ownership move toB → source WAC recompute → at-cost JE → stored transfer valuation.

**Penyebab:** _transfer_items_value_at_cost mengambil WAC live entitas sumber. Kedua caller shared menjalankan ownership transfer sebelum memposting helper. Roll yang menjadi objek transfer sudah dikeluarkan dari query source WAC: cost yang dipakai berasal dari sisa barang lain atau fallback master lama. Tidak ada snapshot biaya sebelum perpindahan.

**Dampak dan batas interpretasi:** Normal original public API 200, tanpa fault: satu roll 10m cost 15, master HPP 1; pre-source WAC 15, tetapi sesudah roll pindah source kosong sehingga JE total 10, padahal pre-source at-cost 150. Roll tujuan tetap cost 15/nilai 150. Pada sumber berisi 10m×5 dan 10m×15, pre-source WAC 10 dan target transfer 10m seharusnya 100 menurut kontrak WAC; setelah roll mahal dipindah, JE50 memakai cost roll murah yang tertinggal. Kebijakan WAC versus actual roll-cost harus ditetapkan untuk kasus campuran; kasus sumber satu roll sudah salah pada kedua kebijakan.

- `D4-INTERCO-02-empty_source-valuation` — expected `150.0`; actual `10.0`; `observed_difference`.
- `D4-INTERCO-02-empty_source-http-control` — expected `200`; actual `200`; `pass`.
- `D4-INTERCO-02-empty_source-retained-roll-cost-control` — expected `15`; actual `15.0`; `pass`.
- `D4-INTERCO-02-cheaper_remainder-valuation` — expected `100.0`; actual `50.0`; `observed_difference`.
- `D4-INTERCO-02-cheaper_remainder-http-control` — expected `200`; actual `200`; `pass`.
- `D4-INTERCO-02-cheaper_remainder-retained-roll-cost-control` — expected `15`; actual `15.0`; `pass`.

```python
1334:        await _already_posted("inter_company_transfer", dst_id):
1335:         return {"posted": False, "reason": "already_posted", "total": 0.0}
1336: 
1337:     valuation = await _transfer_items_value_at_cost(transfer, src)
1338:     total = float(valuation["total"])
1339:     if total <= EPS:
1340:         return {"posted": False, "reason": "zero_cost", "total": 0.0,
1341:                 "breakdown": valuation["breakdown"]}
1342: 
1343:     code = transfer.get("code") or tid
1344:     pair_id = f"ict_{tid}"
```

**Prompt perbaikan:**

> Periksa `D4-INTERCO-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan dan simpan immutable valuation sebelum owner/status berubah, dengan quantity/UOM, per-line/per-roll cost dan legal entity source. Pilih kebijakan WAC atau actual roll-cost secara eksplisit dan jaga rekonsiliasi GL terhadap SSOT roll cost; jangan recompute retry dari live remaining source atau cache/fallback. Helper GL mengonsumsi snapshot tervalidasi dan kedua sisi memakai total sama. Audit transfers.approve, return transfer, destination revaluation serta konsolidasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Satu roll 10×15 dengan stale master 1 menghasilkan JE150, ownerB dan subledger 150. Sumber campuran 5/15 mengikuti policy yang terdokumentasi dan kedua entitas tetap rekonsiliasi. Uji source menjadi kosong, source tetap berisi roll biaya berbeda, landed cost, conversion yard/meter, zero-cost nyata versus missing-cost, concurrent cost update, partial transfer, failure/retry tanpa revaluasi ulang.

**Hubungan dengan catatan lain:** D4-INTERCO-01, D4-STOCK-01, D4-STOCK-03

## D4-DOC-01 — Pratinjau Template Dokumen Dasar memanggil endpoint yang tidak tersedia dan mengabaikan jenis template

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_api_to_original_javascript_contract_counterexample.

**Letak:** [frontend/src/hooks/useAppActions.js:616](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/hooks/useAppActions.js#L616).

**Lokasi kode lain dalam rantai:** [frontend/src/features/admin/AdminView.jsx:542](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/admin/AdminView.jsx#L542) · [frontend/src/AppViewRouter.jsx:260](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/AppViewRouter.jsx#L260) · [backend/routers/documents.py:283](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/documents.py#L283).

**Tampilan / rantai terkait:** Pengaturan → Template Dokumen Dasar → Pratinjau pada baris template; iframe live preview · nav doc-templates-basic → AdminView templates → row button → AppViewRouter onPreviewTemplate → useAppActions.previewTemplate → missing POST route.

**Penyebab:** Callback melakukan POST /document-templates/{id}/preview, tetapi aplikasi hanya menyediakan GET /documents/preview/{order_id} beserta CRUD template. Original hook juga mematok document_type invoice walaupun row yang dipilih adalah Surat Jalan. Jalur ini masih terhubung pada activeView doc-templates-basic, sehingga bukan hanya fungsi lama yang tidak pernah dipakai.

**Dampak dan batas interpretasi:** Original public creator membuat template Surat Jalan yang dapat dilihat lewat GET list; satu SO state fixture milikA tersedia. Exact POST dari UI mendapat 404. Original hook dengan original 404 memberi notice Not Found dan tidak mengisi previewHtml. Transport control membuktikan URL yang dipanggil; request body invoice padahal selected row surat_jalan. Existing GET document preview memberi 200 HTML pada fixture sama, sehingga bukan masalah seluruh renderer atau data kosong. DOM tidak diuji; SO fixture bukan full create/fulfill producer.

- `D4-DOC-01-existing-template-control` — expected `{"http": 200, "exists": true}`; actual `{"http": 200, "exists": true}`; `pass`.
- `D4-DOC-01-preview-contract` — expected `200`; actual `404`; `observed_difference`.
- `D4-DOC-01-alternative-renderer-control` — expected `{"http": 200, "html": true}`; actual `{"http": 200, "html": true}`; `pass`.
- `D4-DOC-01-original-route-control` — expected `"http://audit.local/api/document-templates/tmpl_437b60725d91/preview"`; actual `"http://audit.local/api/document-templates/tmpl_437b60725d91/preview"`; `pass`.
- `D4-DOC-01-selected-template-document-type` — expected `"surat_jalan"`; actual `"invoice"`; `observed_difference`.
- `D4-DOC-01-original-preview-html` — expected `true`; actual `false`; `observed_difference`.

```javascript
 613: 
 614:   const previewTemplate = async (templateId, orderId) => {
 615:     try {
 616:       const response = await axios.post(`${API}/document-templates/${templateId}/preview`, { document_type: "invoice", source_id: orderId, actor: user?.name || "Admin" }, { responseType: "text" });
 617:       setPreviewHtml(response.data);
 618:       setNotice("Preview template diperbarui.");
 619:     } catch (error) {
 620:       setNotice(error.response?.data?.detail || "Preview template gagal. Pastikan ada order untuk preview.");
 621:     }
 622:   };
 623: 
```

**Prompt perbaikan:**

> Periksa `D4-DOC-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Satukan kontrak preview berdasarkan source document dan selected template ID/type. UI meneruskan jenis template yang dipilih; server memvalidasi entity, permissions, template effective layer dan kompatibilitas source tanpa membuat generated document/transaksi. Jangan sekadar mengganti endpoint ke GET yang mengabaikan selected ID. Pastikan template dasar dan PDF designer mempunyai batas fitur yang jelas dan dokumen yang benar-benar dicetak memakai format/field yang sama dengan preview. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Admin membuka Template Dokumen Dasar dengan SO yang sah: Pratinjau template Surat Jalan/invoice/jenis lain memberi 200 HTML untuk selected template dan document type yang tepat. Dua template tipe sama harus dapat dipratinjau berbeda sesuai ID, global vs entity override terkontrol, source berbeda entitas ditolak, disabled template ditangani jelas, tanpa generated-doc atau ledger side effect. Uji empty orders, permissions, invalid template/source, error recovery, iframe HTML dan output cetak.

**Hubungan dengan catatan lain:** D4-FE-02

## D4-CASE-03 — Alur dana dipegang karyawan tidak menjaga urutan langkah dan sisa piutang

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_business_state_counterexample.

**Letak:** [backend/services/finance_case_actions.py:310](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L310).

**Lokasi kode lain dalam rantai:** [backend/services/finance_case_service.py:441](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_service.py#L441) · [backend/services/finance_case_service.py:467](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_service.py#L467) · [backend/services/finance_case_playbooks.py:113](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_playbooks.py#L113).

**Tampilan / rantai terkait:** Pusat Kasus Keuangan → Transfer ke rekening pribadi karyawan → akui piutang → catat setoran · Case open → action dispatch without transition guard → cash received / employee receivable credit → unconditional resolved.

**Penyebab:** Service memvalidasi action terdaftar pada playbook, tetapi tidak memvalidasi state/step/next_action atau remaining acknowledged receivable. act_setor_dari_karyawan tidak menuntut bukti step 1 berhasil, tidak membatasi amount terhadap sisa piutang, dan tidak mengembalikan hold untuk partial settlement. resolve menutup semua aksi yang tidak memberi hold.

**Dampak dan batas interpretasi:** Original normal step 1 80 lalu step 2 80 lulus: resolved, employee debt 0, cash-in80. Original public step 2 pada case baru juga diterima 200: cash 80, employee receivable-80 tanpa acknowledgment step 1. Setelah step 1 80, setoran 40 memberi receivable 40 tetapi case resolved; setoran 100 memberi receivable-20 tanpa surplus classification. Ini normal requests tanpa fault injection, dan diuji dengan startup indexes asli. SO adalah fixture receivable read-state; original payment/GL executors dipakai, bukan klaim seluruh SO producer sudah diuji.

- `D4-CASE-03-normal-two-step-control` — expected `{"http": [200, 200], "state": "resolved", "debt": 0, "cash_in": 80}`; actual `{"http": [200, 200], "state": "resolved", "debt": -0.0, "cash_in": 80.0}`; `pass`.
- `D4-CASE-03-skip-step-one-cash` — expected `0`; actual `80.0`; `observed_difference`.
- `D4-CASE-03-skip-step-one-debt` — expected `0`; actual `-80.0`; `observed_difference`.
- `D4-CASE-03-partial-remains-open` — expected `"in_progress"`; actual `"resolved"`; `observed_difference`.
- `D4-CASE-03-partial-receivable-control` — expected `40`; actual `40.0`; `pass`.
- `D4-CASE-03-excess-receivable` — expected `0`; actual `-20.0`; `observed_difference`.

```python
 307:             "next_action": "setor_dari_karyawan"}
 308: 
 309: 
 310: async def act_setor_dari_karyawan(case: Dict[str, Any], p: Dict[str, Any],
 311:                                   actor: Dict[str, Any]) -> Dict[str, Any]:
 312:     """Langkah 2: karyawan menyetor → piutang karyawan kembali nol."""
 313:     amount = round(float(p.get("amount") or 0), 2)
 314:     emp = (p.get("employee_name") or (case.get("resolution") or {})
 315:            .get("extra", {}).get("employee_name") or "karyawan")
 316:     res = await _cash_txn(
 317:         direction="in", amount=amount, category="setoran karyawan",
```

**Prompt perbaikan:**

> Periksa `D4-CASE-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan state machine per playbook di backend dengan permitted action, prerequisites, operation version dan remaining amount yang diturunkan dari acknowledged/settled legs. Setoran harus menunjuk acknowledgment/employee yang sah, menjaga legal entity dan source debt. Partial settlement tetap in_progress dengan remaining dan next_action, atau ditolak sebelum efek bila policy tidak membolehkannya. Excess memerlukan keputusan eksplisit dengan akun/ledger surplus yang tepat; jangan mengkredit piutang lebih besar dari yang ada. UI menampilkan step yang sah tetapi server tetap menjadi gate. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Step 2 sebelum acknowledgment ditolak tanpa cash/JE. Holding 80→deposit 80: debt 0 dan resolved. Holding 80→deposit 40: remaining 40, case pending dan dapat menerima 40 berikutnya. Deposit 100 tidak membuat employee receivable negatif; surplus 20 diproses sesuai keputusan terdokumentasi atau request ditolak tanpa side effect. Uji wrong employee/entity/source, repeated step 1, multiple partial settlements, concurrent settlements, rejection/reopen, reversal dan restart recovery; kriteria CASE-02 juga harus terpenuhi.

**Hubungan dengan catatan lain:** D4-CASE-02

## D4-CLOSE-01 — Reopen bulan tidak menandai penutupan tahun yang bergantung padanya sebagai basi

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_api_closing_dependency_counterexample.

**Letak:** [backend/services/closing_service.py:346](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L346).

**Lokasi kode lain dalam rantai:** [backend/services/closing_service.py:398](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L398) · [frontend/src/features/finance/ClosingView.jsx:307](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/ClosingView.jsx#L307).

**Tampilan / rantai terkait:** Keuangan → Tutup Buku → Reopen bulanan; status tahunan dan tombol Tutup Ulang · Manual revenue 100 → month closing 100 → year residual 0 → reopen month → annual snapshot no invalidation → UI hides reclose.

**Penyebab:** reopen_period menganulir jurnal bulan dan memperbarui record bulan, tetapi tidak menginvalidasi penutupan aktif yang mencakupnya. reclose_period memiliki propagasi stale ke parent; reopen tidak. UI menyediakan Tutup Ulang hanya bila closed dan stale, sehingga penutupan tahun tetap tampil final tanpa akses normal ke aksi pemulihannya.

**Dampak dan batas interpretasi:** Original public API: pendapatan 100, close Januari 100 dan tahun residual 0 lulus. Reopen Januari 200 mengembalikan laba belum ditutup 100; tahun tetap closed/staleFalse. Preview tahunan menghitung residual 100, tetapi tombol Tutup Ulang tidak ditawarkan oleh source UI. Persamaan neraca tetap seimbang dan P&L operasional tetap 100; bukan klaim math neraca gagal. Direct API reclose tahunan 200 tersedia sebagai workaround, walau UI tidak menawarkannya. Seluruh producer manual/closing asli; DOM tidak diuji.

- `D4-CLOSE-01-nested-producer-control` — expected `{"month": 100, "year": 0}`; actual `{"month": 100.0, "year": 0.0}`; `pass`.
- `D4-CLOSE-01-before-reopen-control` — expected `0`; actual `0.0`; `pass`.
- `D4-CLOSE-01-parent-stale` — expected `true`; actual `false`; `observed_difference`.
- `D4-CLOSE-01-parent-residual-control` — expected `100`; actual `100.0`; `pass`.
- `D4-CLOSE-01-post-reopen-operating-income-control` — expected `100`; actual `100.0`; `pass`.
- `D4-CLOSE-01-post-reopen-unclosed-income-control` — expected `100`; actual `100.0`; `pass`.
- `D4-CLOSE-01-direct-reclose-workaround-control` — expected `200`; actual `200`; `pass`.

```python
 343:     return safe_doc(rec)
 344: 
 345: 
 346: async def reopen_period(closing_id: str, actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
 347:     rec = await db.period_closings.find_one({"id": closing_id}, {"_id": 0})
 348:     if not rec:
 349:         return None
 350:     if rec.get("status") != "closed":
 351:         raise ValueError("Periode ini tidak dalam status tertutup.")
 352:     # INV-ATOMIC-01 — klaim periode (masih closed) sebelum jurnal penutup di-void.
 353:     from services import atomic_claim as _saga
```

**Prompt perbaikan:**

> Periksa `D4-CLOSE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Definisikan dependency/invalidation graph penutupan bulanan/tahunan dan terapkan pada reopen, reclose, unlock corrections serta void. Setelah journal penutup anak berubah, parent harus stale/pending dengan alasan dan residual yang dapat direkonsiliasi, atau reopen ditolak sebelum efek bila policy mewajibkan urutan parent dahulu. Tampilkan tindakan pemulihan sesuai status; jangan menandai final hanya karena record closed masih ada. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Close bulan 100 lalu tahun residual 0 → reopen bulan: parent tahun diberi stale dan tersedia reclose, atau aksi ditolak tanpa void sebelum parent ditangani. Setelah pemulihan, residual 100 tertutup satu kali; P&L operasional 100 tetap 100 dan total equity tetap rekonsiliasi. Uji tahun buku non-Desember, beberapa bulan, parent residual bukan 0, reopen/reclose berulang, concurrency, entity dan fault checkpoints.

**Hubungan dengan catatan lain:** D4-CLOSE-02

## D4-CLOSE-02 — Tutup ulang gagal mengadopsi jurnal yang sudah tersimpan sehingga recovery admin tetap gagal

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_closing_fault_and_admin_recovery_counterexample.

**Letak:** [backend/services/closing_service.py:371](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L371).

**Lokasi kode lain dalam rantai:** [backend/services/closing_service.py:404](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L404) · [backend/routers/saga_locks.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L90) · [backend/indexes.py:444](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/indexes.py#L444).

**Tampilan / rantai terkait:** Keuangan → Tutup Buku → Tutup Ulang; Kunci Saga → pemeriksaan efek dan pelepasan admin · Dual-control unlock → backdated correction → reclose → old JE void → new JE durable → lost acknowledgement → parent old ref → admin release → retry unique-index conflict.

**Penyebab:** reclose_period menganulir jurnal lama, membuat jurnal baru dengan source_id closing yang sama, lalu baru memperbarui snapshot dan link parent. Tidak ada checkpoint/adopsi jurnal aktif yang sudah dibuat bila acknowledgment atau parent update gagal. Retry menggunakan parent journal_entry_id lama yang sudah void lalu mencoba insert ulang, bertabrakan dengan unique active source index. Kunci saga memang terlihat dan memblokir replay, tetapi pelepasan yang sah tidak menyediakan resumable recovery.

**Dampak dan batas interpretasi:** Original producer public: close laba 100, unlock dengan pengusul dan penyetuju berbeda, koreksi 20 dan normal reclose 120 lulus. Koreksi berikut 10, fault hanya sesudah original JE130 durably inserted: parent net 120/linkJE 120 void, JE130 aktif dan saga lock tersisa. Immediate retry 409 adalah kontrol guard yang benar. Setelah clock lock di-aging secara eksplisit dan original admin release dengan acknowledgment 200, original reclose retry 500 karena active source unique index, parent tetap link lama. Tidak diklaim journal 130 hilang atau duplicate berhasil dibuat; indeks menjaga jumlah 1 tetapi recovery/link/snapshot gagal.

- `D4-CLOSE-02-normal-reclose-control` — expected `{"net": 120, "stale": false}`; actual `{"net": 120.0, "stale": false}`; `pass`.
- `D4-CLOSE-02-linked-journal-posted` — expected `"posted"`; actual `"void"`; `observed_difference`.
- `D4-CLOSE-02-active-journal-control` — expected `{"count": 1, "total": 130}`; actual `{"count": 1, "total": 130.0}`; `pass`.
- `D4-CLOSE-02-parent-net-income` — expected `130`; actual `120.0`; `observed_difference`.
- `D4-CLOSE-02-immediate-lock-control` — expected `409`; actual `409`; `pass`.
- `D4-CLOSE-02-admin-release-control` — expected `200`; actual `200`; `pass`.
- `D4-CLOSE-02-original-recovery-retry` — expected `200`; actual `500`; `observed_difference`.
- `D4-CLOSE-02-recovery-linked-existing` — expected `"je_6eaaad066784"`; actual `"je_5de1a6405853"`; `observed_difference`.

```python
 368:     return await db.period_closings.find_one({"id": closing_id}, {"_id": 0})
 369: 
 370: 
 371: async def reclose_period(closing_id: str, actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
 372:     """F-9b — Tutup Ulang periode yang STALE (angka berubah karena posting backdate):
 373:     void jurnal penutup lama → hitung ulang residual (kecuali JE closing ini sendiri)
 374:     → buat jurnal penutup baru → bersihkan flag stale."""
 375:     rec = await db.period_closings.find_one({"id": closing_id}, {"_id": 0})
 376:     if not rec:
 377:         return None
 378:     if rec.get("status") != "closed":
```

**Prompt perbaikan:**

> Periksa `D4-CLOSE-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist reclose operation/version dan checkpoint intent, old/new journal IDs serta frozen totals sebelum efek. Retry harus mengadopsi JE yang cocok dengan operation/version dan memfinalisasi parent, bukan menganggap unique-index error sebagai sukses atau membuat jurnal baru. Rancang atomic switch/compensation agar status/link/snapshot konsisten, tandai failure yang dapat diperiksa, dan recovery admin menyelesaikan/membatalkan operation secara sadar efek. Pertahankan unique index, fencing dan guard periode; audit close/reopen/unlock auto-close serta concurrent yearly/monthly operations. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Lost acknowledgment sesudah JE insert dan kegagalan parent update dapat direcover lewat fitur asli: tepat satu active JE130, parent menunjuknya/net 130/staleFalse, lock selesai dan histori jelas. Fault sebelum insert tidak membuang journal lama tanpa recovery; retry setelah restart tidak menciptakan extraJE. Uji reopen bersamaan, akun nonaktif, partial unlock, fiscal year, parent invalidation dan laporan/print yang mengikuti snapshot final.

**Hubungan dengan catatan lain:** D4-CLOSE-01, D4-CASE-02

## D4-GL-01 — Jurnal manual yang sudah dibalik masih dapat dianulir dan membentuk pembatalan dua kali

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_mutually_exclusive_cancellation_counterexample.

**Letak:** [backend/services/gl_service.py:755](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L755).

**Lokasi kode lain dalam rantai:** [backend/services/gl_service.py:783](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L783) · [frontend/src/features/finance/GeneralLedger.jsx:369](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/GeneralLedger.jsx#L369).

**Tampilan / rantai terkait:** Keuangan → Buku Besar → Detail Jurnal → Balik Jurnal lalu Anulir Jurnal; Laba-Rugi/Neraca Saldo · Manual expense 100 → reverse journal → net 0 → void original only → standalone reversal → income 100.

**Penyebab:** void_entry memeriksa status non-void dan sumber manual, tetapi mengabaikan reversed_by_entry_id termasuk pending reversal. Filter CAS void juga hanya status non-void. Frontend tetap menampilkan Anulir Jurnal untuk manual/posted walaupun sudah reversed. Membalik dan menganulir asal dapat terjadi berurutan atau beradu tanpa mutually exclusive cancellation state.

**Dampak dan batas interpretasi:** Normal original public manual expense 100 → void memberi laba 0 sebagai kontrol. Manual expense 100 → reverse juga laba 0 sebagai kontrol. Setelah reversal, original public void masih 200: jurnal asal void, pembalik tetapposted. Original income_statement menghasilkan net_income+100, sehingga satu pembatalan berubah menjadi laba semu 100. Ini normal requests tanpa fault injection dan diuji dengan startup indexes. Tidak diklaim semua pembalikan otomatis wajib mengubah dokumen sumber; temuan adalah membatalkan asal dua kali melalui dua aksi GL.

- `D4-GL-01-ordinary-void-control` — expected `{"http": 200, "income": 0}`; actual `{"http": 200, "income": 0}`; `pass`.
- `D4-GL-01-single-reversal-control` — expected `0`; actual `0`; `pass`.
- `D4-GL-01-second-cancellation-rejected` — expected `true`; actual `false`; `observed_difference`.
- `D4-GL-01-post-reversal-void-income` — expected `0`; actual `100.0`; `observed_difference`.

```python
 752:         {"$or": [{"id": entry_id}, {"number": entry_id}]}, {"_id": 0})
 753: 
 754: 
 755: async def void_entry(entry_id: str, actor: Dict[str, Any],
 756:                      can_backdate: bool = True) -> Optional[Dict[str, Any]]:
 757:     je = await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})
 758:     if not je:
 759:         return None
 760:     if je.get("status") == "void":
 761:         raise ValueError("Jurnal sudah di-void.")
 762:     if je.get("source_type") != "manual":
```

**Prompt perbaikan:**

> Periksa `D4-GL-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan satu state machine cancellation: void dan reverse saling eksklusif secara atomik, termasuk reversal pending. Tolak void atas jurnal reversed sebelum efek; bila business policy mengizinkan koreksi pasangan, gunakan aksi terpisah yang memproses pasangan/link/period secara auditable, bukan void asal saja. UI menyembunyikan/menjelaskan aksi tidak sah tetapi backend gate wajib. Review source reversal, backfill dan laporan agar pembalik tetap teridentifikasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Manual 100 → reverse: net 0; void asal sesudahnya ditolak 4xx tanpa mengubah jurnal/PL. Manual 100 → void: net 0; reverse asal ditolak. Dua request reverse/void bersamaan hanya satu cancellation menang, tidak pernah menyisakan pembalik tunggal. Uji pending/failed reversal, retry, closed period, partial fault dan drilldown/print/link jurnal.

**Hubungan dengan catatan lain:** D4-CLOSE-02

## D4-GL-02 — Jurnal manual meloloskan NaN/Infinity dan menghilangkan angka transaksi sah dari laporan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_invalid_numeric_and_report_counterexample.

**Letak:** [backend/services/gl_service.py:640](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L640).

**Lokasi kode lain dalam rantai:** [backend/services/gl_service.py:524](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L524) · [backend/schemas_finance.py:53](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_finance.py#L53) · [backend/services/gl_service.py:2974](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L2974) · [backend/services/financial_statement_service.py:88](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L88).

**Tampilan / rantai terkait:** Keuangan → Buku Besar/Jurnal manual API → Neraca Saldo, KPI GL dan Laba-Rugi · Valid expense 50 → manual float coercion of JSON stringNaN/Infinity → bypass central validation → non-finite Mongo double → reports omit poisoned account → displayed expense 0.

**Penyebab:** Validator pusat _validate_entry_lines memakai math.isfinite, tetapi create_manual_entry menyisipkan langsung ke journal_entries tanpa melewatinya. Perbandingan negatif/zero/difference terhadap NaN tidak menolak; Infinity-Infinity juga NaN. Schema JournalLineIn menerima coercion string ke float. Response sanitizer mengubah angka tidak finite menjadi null, tanpa membatalkan penulisan.

**Dampak dan batas interpretasi:** Authorized public API dengan JSON valid berupa string NaN dan Infinity masing-masing sukses 200, menyimpan native non-finite double dan mengirim amountsnull. Sebelumnya expense 50 menghasilkan summarydebit 50. Sesudah badentries pada dua akun sama, public GLsummary tetap 200/balancedTrue tetapi totaldebit 0; public P&L opex 0 padahal expense 50 sah tetap ada. Ini invalid-input correctness test, bukan klaim input NaN terjadi dari browser biasa. Hipotesis HTTP 500 karena serialization ditarik: hasil nyata adalah sanitization/masking dan silent omission.

- `D4-GL-02-healthy-summary-control` — expected `{"http": 200, "debit": 50}`; actual `{"http": 200, "debit": 50.0}`; `pass`.
- `D4-GL-02-nan-persisted` — expected `0`; actual `1`; `observed_difference`.
- `D4-GL-02-nan-validation` — expected `true`; actual `false`; `observed_difference`.
- `D4-GL-02-infinity-persisted` — expected `0`; actual `1`; `observed_difference`.
- `D4-GL-02-infinity-validation` — expected `true`; actual `false`; `observed_difference`.
- `D4-GL-02-summary-valid-amount-retained` — expected `50`; actual `0.0`; `observed_difference`.
- `D4-GL-02-income-valid-expense-retained` — expected `50`; actual `0`; `observed_difference`.

```python
 637:                   "updated_at": now_iso()}})
 638: 
 639: 
 640: async def create_manual_entry(payload, actor: Dict[str, Any],
 641:                               entity_id: Optional[str] = None,
 642:                               can_backdate: bool = True) -> Dict[str, Any]:
 643:     raw = [ln.model_dump() if hasattr(ln, "model_dump") else dict(ln) for ln in (payload.lines or [])]
 644:     if len(raw) < 2:
 645:         raise ValueError("Jurnal minimal 2 baris (debit & kredit).")
 646:     codes = [str(l.get("account_code", "")).strip() for l in raw]
 647:     if any(not c for c in codes):
```

**Prompt perbaikan:**

> Periksa `D4-GL-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan validator pusat yang sama untuk seluruh manual/autopost/import producers sebelum side effect, dengan field finite di schema dan validasi aggregate balance sesudah normalisasi. Tolak NaN/Infinity dari angka maupun string 4xx sebelum insert atau perubahan counters material. Jangan mengubah invalid values menjadi 0 sebagai perbaikan. Audit data existing dengan penandaan dan koreksi/reversal yang disetujui; laporan harus menampilkan masalah integritas, bukan silently menghapus akun sah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** NaN/±Infinity pada setiap field debit/credit dan total tidak tersimpan;4xx dengan detail jelas, jurnal/GL tidak berubah. Fixture expense 50 tetap summarydebit 50 dan PLexpense 50 setelah invalid request. Uji numeric strings, overflow 1e309, rounding, huge/negative/zero values, import/manual/autopost, legacy damaged-record quarantine dan safe display tanpa menyatakan balanced jika data rusak.

**Hubungan dengan catatan lain:** D4-GL-01

## D4-EQ-01 — KPI Laba Periode Berjalan pada perubahan ekuitas berubah menjadi nol sesudah tutup buku

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_closing_to_frontend_metric_counterexample.

**Letak:** [backend/services/equity_statement_service.py:57](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/equity_statement_service.py#L57).

**Lokasi kode lain dalam rantai:** [frontend/src/features/finance/EquityChangesTab.jsx:61](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/EquityChangesTab.jsx#L61) · [backend/services/financial_statement_service.py:62](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L62) · [backend/routers/financial_statements.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/financial_statements.py#L90).

**Tampilan / rantai terkait:** Keuangan → Laporan Keuangan → Perubahan Ekuitas → Laba Periode Berjalan · Operational income 100 → balance current_earnings100 → closing reclass to retained earnings → current_earnings0 → equity API net_income0 → labelled profit KPI.

**Penyebab:** equity_statement mengisi net_income dari perubahan saldo laba yang belum ditutup pada neraca. Itu perubahan komponen equity, bukan laba operasional periode. Jurnal penutup mengubah saldo current_earnings tanpa mengubah laba periode. Frontend memakai net_income dengan label Laba Periode Berjalan tanpa menjelaskan unclosed earnings movement.

**Dampak dan batas interpretasi:** Original public manual revenue 100: equity API sebelum closingnet 100. Original monthly/year closing yang benar memindahkan 100 ke RE; equity API periode sama sesudahnya netincome 0, sedangkan original operating P&L tetap 100. Total pergerakan equity 100 dan saldoakhir 100 benar sebagai kontrol. Source UI mengonsumsi net_income langsung pada KPI; DOM tidak diuji. Temuan source-definition mismatch, bukan roll-forward equity salah atau semua closing gagal.

- `D4-EQ-01-open-period-income-control` — expected `100`; actual `100.0`; `pass`.
- `D4-EQ-01-closed-period-net-income` — expected `100`; actual `0.0`; `observed_difference`.
- `D4-EQ-01-total-equity-movement-control` — expected `100`; actual `100.0`; `pass`.
- `D4-EQ-01-operating-profit-control` — expected `100`; actual `100.0`; `pass`.

```python
  54:         "begin_total": round(begin_total, 2),
  55:         "movement_total": round(end_total - begin_total, 2),
  56:         "end_total": round(end_total, 2),
  57:         "net_income": round(end_ce - begin_ce, 2),
  58:         "generated_at": now_iso(),
  59:     }
```

**Prompt perbaikan:**

> Periksa `D4-EQ-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan period_operating_net_income yang dihitung dari P&L non-closing dalam range/scope yang sama, dengan movement_unclosed_earnings yang diperlukan untuk roll-forward. KPI profit memakai period income; tabel perpindahan RE/current earnings tetap merekonsiliasi, jangan menambahkan laba sekali lagi ke end_total atau movement_total. Dokumentasikan label, beginning balances, fiscal range dan export contract. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Periode profit 100 tetap KPI 100 sebelum/sesudah monthly/year close, reopen/reclose, dan menutup residual; equity movement/end totals tetap 100. Uji opening retained earnings, laba/rugi, periode melintasi beberapa closes, dividen/injeksi modal, comparative/entity, CSV dan source-to-rendered validation. Net income tidak berubah hanya karena laba ditransfer antar komponen equity.

**Hubungan dengan catatan lain:** D4-CLOSE-01

## D4-COA-01 — Mode Semua Entitas pada laporan keuangan menghilangkan akun khusus entitas yang sah

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_producer_multi_entity_dimension_counterexample.

**Letak:** [backend/services/financial_statement_service.py:54](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L54).

**Lokasi kode lain dalam rantai:** [backend/services/financial_statement_service.py:40](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L40) · [backend/services/gl_service.py:507](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L507) · [backend/routers/gl.py:60](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/gl.py#L60) · [backend/services/gl_service.py:651](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L651).

**Tampilan / rantai terkait:** Keuangan → Laporan Keuangan → Semua Entitas; Laba-Rugi dan Neraca · Public entity-specific COA creator → valid manual JE → single-entity effective dimension → all-scope global-only dimension → missing income and unbalanced BS.

**Penyebab:** scope_entity mengembalikan None untuk scope multi-entitas. _accounts_map lalu meminta effective_accounts hanya untuk global template. Producer mendukung akun khusus entitas dengan kode yang tidak ada global; akun sah tersebut hilang dari dimensi multi-entity sehingga debit kas masih dihitung tetapi pendapatan lawannya tidak diklasifikasi. Ini berbeda dari memilih override nama akun yang nondeterministik.

**Dampak dan batas interpretasi:** Original public create akun income 4-7777 hanyaA dan manual DrKas 77/CrIncome 77 sukses 200. Public P&L Juli untukA net 77; mode all berisiA+B, B kosong padaJuli, tetapi net 0. SingleA neraca balancedTrue; all balancedFalse dengan assets 307 tetap benar dan equity 230, selisih 77. Assets 307 berasal dari original lifecycle 100+130+77. Tidak ada konflik override, invalid input atau fault pada skenario ini. Temuan spesifik endpoint Laporan Keuangan entity_id=all, bukan klaim semua fitur Konsolidasi Grup yang memakai helper lain gagal.

- `D4-COA-01-single-entity-income-control` — expected `77`; actual `77.0`; `pass`.
- `D4-COA-01-all-entities-income` — expected `77`; actual `0`; `observed_difference`.
- `D4-COA-01-single-entity-balance-control` — expected `true`; actual `true`; `pass`.
- `D4-COA-01-all-entities-balanced` — expected `true`; actual `false`; `observed_difference`.
- `D4-COA-01-all-entities-assets-control` — expected `307`; actual `307.0`; `pass`.

```python
  51:     """FN-05 — COA efektif entitas laporan (global + override entitas itu, deterministik).
  52:     Laporan multi-entitas memakai dimensi akun global (bukan override acak entitas lain)."""
  53:     from services.gl_service import effective_accounts
  54:     return await effective_accounts(None, scope_entity(scope))
  55: 
  56: 
  57: async def _aggregate(scope: Optional[Dict[str, Any]],
  58:                      date_filter: Optional[Dict[str, str]],
  59:                      include_closing: bool = True) -> Dict[str, Dict[str, float]]:
  60:     """Jumlahkan debit/credit per account_code dari jurnal (non-void, ter-scope).
  61: 
```

**Prompt perbaikan:**

> Periksa `D4-COA-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Resolve account dimension pada grain entity+account sebelum agregasi, lalu roll-up lewat mapping COA grup yang eksplisit. Akun khusus entitas tidak boleh hilang; bila belum dipetakan ke COA grup, tampilkan error/rekonsiliasi yang actionable, bukan silently drop. Jangan memilih override PT pertama secara acak untuk semua PT. Audit P&L/BS/comparative/equity/cashflow, ledger/trial balance dan export dengan resolver yang sesuai scope; pertahankan legal-entity permissions dan policy untuk kode sama dengan klasifikasi berbeda. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Akun khususA income 77 danB kosong: A dan all sama-samaincome 77, allBS balanced dan selisih 0; total all merekonsiliasi partisi legal entity. Uji akun khusus dua PT dengan kode unik, override nama/kategori/type berbeda pada kode sama, global disabled/entity active, unmapped group code, pagination COA besar, comparative, CSV serta entity access. Fitur Konsolidasi Grup yang memakai helper lain harus diuji sebagai kontrol terpisah.

**Hubungan dengan catatan lain:** D4-FIN-01, D4-EQ-01

## D4-PA-01 — Reservasi SO mengambil roll yang sudah diklaim putaway dan meninggalkan lokasi alokasi lama

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/roll_service.py:792](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L792).

**Lokasi kode lain dalam rantai:** [backend/services/putaway_order_service.py:152](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L152) · [backend/services/putaway_order_service.py:200](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L200) · [backend/services/roll_service.py:736](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L736) · [backend/services/roll_service.py:549](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L549) · [backend/routers/sales_orders.py:421](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/sales_orders.py#L421) · [backend/services/sales_order_helpers.py:123](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_order_helpers.py#L123).

**Tampilan / rantai terkait:** Putaway Order → POS/Sales Order → reservasi → sumber pemenuhan gudang · Verified roll → PA claim → public SO whole/partial reservation → PA dispatch/arrival → persisted allocation points to old warehouse.

**Penyebab:** PA mengklaim active_movement tetapi status roll tetap available. Candidate dan CAS reservasi utuh/panjang mengabaikan klaim tersebut. Reservasi parsial mempertahankan status available sambil menambah length_reserved; dispatch PA tidak memeriksa length_reserved. Tidak ada koordinasi atau rebinding alokasi SO setelah roll berpindah.

**Dampak dan batas interpretasi:** Original public PA lalu SO10 mengambil roll 10 yang sama; PA dispatch 409 adalah kontrol yang benar, tetapi konflik proses sudah terjadi. Pada roll 10/SO6, public SO menyimpan reservasi 6 di gudang asal, lalu PA dispatch 200/arrival 200 memindahkan roll ke tujuan. SO tersimpan tetap menunjuk asal. Tanpa fault injection; inbound writer asli, public print/verify/routing/SO/PA dan startup indexes. Tahap approval/picking/shipment SO setelah ini belum diuji lengkap.

- `D4-PA-01-whole-exclusive-claim` — expected `0`; actual `10.0`; `observed_difference`.
- `D4-PA-01-whole-dispatch-guard-control` — expected `409`; actual `409`; `pass`.
- `D4-PA-01-partial-exclusive-claim` — expected `0`; actual `6.0`; `observed_difference`.
- `D4-PA-01-partial-dispatch-blocked` — expected `409`; actual `200`; `observed_difference`.
- `D4-PA-01-partial-source-location-retained` — expected `"PARTIAL-FROM"`; actual `"PARTIAL-TO"`; `observed_difference`.
- `D4-PA-01-rmwhole-exclusive-claim` — expected `0`; actual `10.0`; `observed_difference`.
- `D4-PA-01-rmwhole-quantity-control` — expected `10`; actual `10.0`; `pass`.
- `D4-PA-01-rmwhole-dispatch-guard` — expected `409`; actual `409`; `pass`.
- `D4-PA-01-rmpart-exclusive-claim` — expected `0`; actual `6.0`; `observed_difference`.
- `D4-PA-01-rmpart-quantity-control` — expected `6`; actual `6.0`; `pass`.
- `D4-PA-01-rmpart-dispatch-guard` — expected `409`; actual `200`; `observed_difference`.

```python
 789: }
 790: 
 791: 
 792: async def _available_rolls_for_order(product_id: str, owner_entity_id: str, order_id: str,
 793:                                      customer_id: str = "") -> List[Dict[str, Any]]:
 794:     """Roll available owner-scoped untuk dialokasikan ke `order_id`/`customer_id`.
 795:     Menghormati EARMARK (pegging): roll yang di-earmark untuk demand LAIN dikecualikan;
 796:     roll yang di-earmark untuk order/customer ini tetap masuk (diprioritaskan planner)."""
 797:     rolls = await db.inventory_rolls.find(
 798:         {"product_id": product_id, "owner_entity_id": owner_entity_id, "status": "available",
 799:          "length_remaining": {"$gt": 0}}, {"_id": 0},
```

**Prompt perbaikan:**

> Periksa `D4-PA-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Definisikan kebijakan kompatibilitas reservasi/perpindahan. Bila klaim PA eksklusif, filter candidate dan CAS seluruh jalur reservasi dengan active_movement kosong; dispatch memeriksa reservasi live sebelum efek. Jika bisnis mengizinkan reservasi pada PA bergerak, koordinasikan per roll/demand dan rebind warehouse/task/alokasi secara auditable. Audit qty mode, explicit roll, reallocate, backorder, raw/makloon, release dan cancel PA. ATP/available-for-sale mengikuti kebijakan sama; jangan hanya menyaring UI. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PA roll 10 lalu SO10/SO6 tidak menghasilkan klaim konflik: ditolak/defer tanpa efek atau lewat koordinasi yang menjaga source/task. Partial reserved tidak ikut bergerak tanpa rebinding. Uji urutan terbalik, race PA/SO, cut, release/cancel, arrival/retry dan qty/explicit-roll public producers. Demand, roll, balance, lokasi dan task tetap rekonsiliasi.

**Hubungan dengan catatan lain:** V3-WMS-02, D4-PA-02, D4-WMS-04

## D4-PA-02 — Putaway kehilangan checkpoint setelah roll berpindah sehingga recovery stok dan tag gagal

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/putaway_order_service.py:232](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L232).

**Lokasi kode lain dalam rantai:** [backend/services/putaway_order_service.py:280](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L280) · [backend/services/putaway_order_service.py:329](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L329) · [backend/services/roll_service.py:233](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L233) · [backend/routers/saga_locks.py:42](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L42) · [backend/routers/putaway_orders.py:74](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/putaway_orders.py#L74).

**Tampilan / rantai terkait:** Putaway Order → Konfirmasi Tiba → BTG/exception; Kunci Saga; stok dan lokasi RFID · Roll location CAS + unset active_movement → tag/movements/balance/parent → failure → admin release → retry/accept cannot adopt landed roll.

**Penyebab:** _land_items memindahkan roll dan menghapus active_movement sebelum tag, mutasi, saldo dan parent difinalisasi. Retry menuntut warehouse asal dan active_movement yang sudah dihapus; tidak ada checkpoint/adopsi efek operation yang sama. Inspector saga tidak memeriksa perubahan existing roll atau PA reference secara memadai.

**Dampak dan batas interpretasi:** Kontrol normal: completed/BTG, roll+tag tujuan, saldo asal 0/tujuan 10 dan dua mutasi. Fault sesudah original roll CAS, sebelum tag update:500; roll tujuan/tag asal, saldo asal transit 10/tujuan 0. Immediate retry 409 lulus. Original admin inspect/release setelah clock aging eksplisit tidak melihat efek. Retry dan accept 200 tetap completed_with_exception; tag asal, mutasi 0, saldo asal 10/tujuan 0. Roll SSOT tidak hilang, tetapi proyeksi/dokumen/tag tertinggal. Manual scan sintetis bukan uji perangkat fisik.

- `D4-PA-02-normal-movement-control` — expected `{"status": "completed", "roll_wh": "NORMAL-TO", "tag_wh": "NORMAL-TO", "from_qty": 0, "to_qty": 10, "movement_count": 2}`; actual `{"status": "completed", "roll_wh": "NORMAL-TO", "tag_wh": "NORMAL-TO", "from_qty": 0.0, "to_qty": 10.0, "movement_count": 2}`; `pass`.
- `D4-PA-02-normal-btg-control` — expected `true`; actual `true`; `pass`.
- `D4-PA-02-fault-control` — expected `500`; actual `500`; `pass`.
- `D4-PA-02-immediate-lock-control` — expected `409`; actual `409`; `pass`.
- `D4-PA-02-inspect-durable-roll-effect` — expected `true`; actual `false`; `observed_difference`.
- `D4-PA-02-retry-parent-finalized` — expected `"completed"`; actual `"completed_with_exception"`; `observed_difference`.
- `D4-PA-02-retry-tag-location` — expected `"RECOVERY-TO"`; actual `"RECOVERY-FROM"`; `observed_difference`.
- `D4-PA-02-retry-audit-pair` — expected `2`; actual `0`; `observed_difference`.
- `D4-PA-02-retry-destination-balance` — expected `10`; actual `0`; `observed_difference`.
- `D4-PA-02-retry-source-balance` — expected `0`; actual `10.0`; `observed_difference`.
- `D4-PA-02-roll-is-at-destination-control` — expected `"RECOVERY-TO"`; actual `"RECOVERY-TO"`; `pass`.

```python
 229:     return await _get(order_id, scope_ids)
 230: 
 231: 
 232: async def _land_items(order: Dict[str, Any], items: List[Dict[str, Any]], actor_name: str,
 233:                       reason: str) -> List[Dict[str, Any]]:
 234:     """Satu jalur posting perpindahan (arrival normal & exception — WM-09): CAS roll milik PA ini,
 235:     pindah gudang, tulis pasangan mutasi out/in, rebuild kedua lokasi. Hasil = item yang benar-benar pindah."""
 236:     from services.roll_service import rebuild_balance
 237:     now = now_iso()
 238:     landed, movements, segs = [], [], set()
 239:     for item in items:
```

**Prompt perbaikan:**

> Periksa `D4-PA-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist operation/version dan checkpoint landed/tagged/audit-posted/balance-rebuilt/parent-finalized per item. Pertahankan token/provenance transisi agar retry mengadopsi efek sah dan melengkapi langkah tersisa. Mutasi out/in memakai unique operation+roll+leg. Inspector admin mencakup roll update, PA number/reference, tag dan invalidation saldo; pelepasan lock bukan penyelesaian efek. Jangan menerima semua roll di tujuan tanpa provenance atau memakai manual edit Mongo sebagai recovery. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault setiap batas roll/tag/mutasi/saldo/parent pulih lewat fitur asli: satu BTG, dua mutasi per roll, parent completed, tag+roll tujuan, asal 0/tujuan 10 dan owned 10. Uji multiroll partial, lost acknowledgment/restart, concurrent/fenced recovery, exception accept/return, stock/ATP/lot. Kontrol normal tetap lulus.

**Hubungan dengan catatan lain:** D4-PA-01, D4-INTERCO-01, D4-CLOSE-02

## D4-PA-03 — Total putaway menjumlahkan meter dan yard lalu memberi satu label satuan

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/putaway_order_service.py:49](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L49).

**Lokasi kode lain dalam rantai:** [backend/services/putaway_order_service.py:166](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L166) · [frontend/src/features/wms/PutawayOrdersPanel.jsx:104](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/PutawayOrdersPanel.jsx#L104) · [frontend/src/features/wms/PutawayOrdersPanel.jsx:144](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/PutawayOrdersPanel.jsx#L144) · [backend/services/roll_service.py:1890](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L1890).

**Tampilan / rantai terkait:** Putaway Order → saran kategori/grade dan ringkasan PA/BTG · Valid product base units → category/owner/grade group → raw qty sum → g.unit / items[0].unit label.

**Penyebab:** Group key tidak memuat unit; qty mentah dijumlahkan dan unit diambil dari roll pertama. create_order menjumlahkan item menjadi total_qty tanpa konversi/breakdown. Frontend memberi label g.unit atau items[0].unit pada total campuran.

**Dampak dan batas interpretasi:** Original inbound/public print/verify: roll 10 meter SKU pertama dan roll 10 yard SKU kedua, woven/gradeA/ownerA. Suggest mengirim satu group 20 meter; public PA total 20 dengan item pertama meter. Harus 19.144 meter (19.14 jika kebijakan dua desimal) atau breakdown 10 meter+10 yard. Per-item benar; producer conversion tidak diklaim rusak. Source consumer diperiksa, DOM belum.

- `D4-PA-03-input-base-units-control` — expected `["meter", "yard"]`; actual `["meter", "yard"]`; `pass`.
- `D4-PA-03-mixed-group-validity` — expected `true`; actual `false`; `observed_difference`.
- `D4-PA-03-document-labelled-total` — expected `19.144`; actual `20.0`; `observed_difference`.

```python
  46:         {"_id": 0}).to_list(200)
  47:     groups: Dict[str, Dict[str, Any]] = {}
  48:     for r in rolls:
  49:         key = f"{r.get('owner_entity_id')}|{r.get('category') or '—'}|{(r.get('grade') or 'A').upper()}"
  50:         g = groups.setdefault(key, {
  51:             "owner_entity_id": r.get("owner_entity_id"), "category": r.get("category") or "",
  52:             "grade": (r.get("grade") or "A").upper(),
  53:             "rolls": [], "qty": 0.0, "unit": r.get("unit", "meter"), "candidates": None})
  54:         g["rolls"].append({k: r.get(k) for k in (
  55:             "id", "roll_no", "sku", "product_name", "category", "grade",
  56:             "length_remaining", "unit", "lot", "rfid_tag_id")})
```

**Prompt perbaikan:**

> Periksa `D4-PA-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan total per unit atau konversi ke unit tujuan yang dinyatakan dengan faktor kanonis/precision eksplisit. Unit tak kompatibel kg/meter memakai breakdown dan jumlah roll. Snapshot faktor bila menjadi dokumen historis. Review saran, PA/BTG print, movement summary/export; jangan memakai unit item pertama atau mengganti label saja. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** 10 meter+10 yard tidak tampil 20 meter; gunakan 19.144/19.14 meter dengan precision eksplisit atau breakdown. Reorder item tidak mengubah makna total. Uji kg+meter, multi-SKU, conversion missing, faktor per dokumen, export/print. Per-item dan saldo base-unit tetap benar.

**Hubungan dengan catatan lain:** D4-STOCK-04, D4-GLOBAL-01

## D4-WMS-04 — KPI antrean simpan menghitung roll reserved yang tidak boleh diputaway

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/wms_health_service.py:42](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L42).

**Lokasi kode lain dalam rantai:** [backend/services/putaway_order_service.py:19](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L19) · [backend/services/putaway_order_service.py:113](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L113) · [frontend/src/features/wms/WmsHealthDashboard.jsx:16](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/WmsHealthDashboard.jsx#L16).

**Tampilan / rantai terkait:** Warehouse Health → Antrean Simpan ke Rak; Putaway → Siap Simpan · Verified available → public SO whole reservation → health counts old stage → suggest excludes → PA rejects.

**Penyebab:** putaway_ready hanya memeriksa owner/panjang/journey/routing; suggest/create menegakkan status available dan guard gerak/reservasi. Tidak ada ready/blocked breakdown atau penjelasan beda definisi. Tag_verified adalah bukti identitas, bukan ketersediaan operasional.

**Dampak dan batas interpretasi:** Roll verified tersedia: suggest 1. Original public SO reservasi 10: suggest 0 dan PA create 400, tetapi health tetap putaway_ready1. UI memakai angka pada Antrean Simpan ke Rak. Lifecycle asli; bukan fixture reserved arbitrer. Jika queue fisik memang termasuk reserved, label/kontrak perlu ready 0/blocked 1, bukan menyebut semuanya ready.

- `D4-WMS-04-ready-normal-control` — expected `1`; actual `1`; `pass`.
- `D4-WMS-04-reserved-suggestion-control` — expected `0`; actual `0`; `pass`.
- `D4-WMS-04-reserved-ready-kpi` — expected `0`; actual `1`; `observed_difference`.
- `D4-WMS-04-create-reserved-guard-control` — expected `400`; actual `400`; `pass`.

```python
  39:             rows[r["_id"]]["red_reads_today"] = r["n"]
  40:     async for r in db.inventory_rolls.aggregate([
  41:             {"$match": {"owner_entity_id": {"$in": scope_ids}, "length_remaining": {"$gt": 0},
  42:                         "journey.stage": "tag_verified", "journey.routing": {"$ne": "cross_dock"}}},
  43:             {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}}]):
  44:         if r["_id"] in rows:
  45:             rows[r["_id"]]["putaway_ready"] = r["n"]
  46:     async for r in db.putaway_orders.aggregate([
  47:             {"$match": {"status": {"$in": ["open", "in_transit"]},
  48:                         "owner_entity_id": {"$in": scope_ids}}},
  49:             {"$group": {"_id": "$to_warehouse_id", "n": {"$sum": 1}}}]):
```

**Prompt perbaikan:**

> Periksa `D4-WMS-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan resolver eligibility yang sama pada health/suggest/create dengan owner/warehouse/current identity/reservasi. Jika termasuk blocked, pisahkan total_pending/ready/blocked_by_reason. Guard CAS server tetap wajib. Cakup QC, routing, active movement dan tag lifecycle. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Reserved tidak menambah actionable ready; health/suggest konsisten. Uji available, partial reserved, quarantine, active PA, pending/retired tag, crossdock, empty, beberapa entitas dan total vs rows. Bila definisi queue berbeda, tampilkan ready 0/blocked 1 beserta alasan.

**Hubungan dengan catatan lain:** D4-PA-01, D4-TAG-01, D4-WMS-01

## D4-RFID-01 — Deduplikasi event RFID melewati recovery keputusan, insiden dan status passage

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/rfid_ingest_service.py:138](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L138).

**Lokasi kode lain dalam rantai:** [backend/services/rfid_ingest_service.py:190](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L190) · [backend/services/rfid_ingest_service.py:194](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L194) · [backend/services/rfid_ingest_service.py:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L151) · [backend/services/rfid_ingest_service.py:214](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L214) · [backend/services/gate_evaluator.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gate_evaluator.py#L129) · [backend/routers/rfid.py:551](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfid.py#L551).

**Tampilan / rantai terkait:** Device Ingest → Gate Monitor/Passage → Alarm/insiden → gate-status API · Raw observation → exit stamp → business read → incident → passage/latch → fault → event dedupe/dwell skips unfinished effects.

**Penyebab:** Observation event_id durable dianggap processed untuk seluruh pipeline tanpa checkpoint read/stamp/incident/passage. Retry event sama dibuang; event baru dapat melewati efek yang belum selesai melalui dwell atau menjadi REPLAY_EXIT akibat stamp yang lebih dahulu durable. Ini berbeda dari cache keputusan basi V3-RFID-01.

**Dampak dan batas interpretasi:** Normal public ingest/replay lulus: satu green MOVEMENT_OUT read, satu duplicate. Fault setelah observation+green stamp sebelum read:500; replay 200/count 0/read 0; event baru menjadi REPLAY_EXIT red. Fault kedua setelah red read sebelum incident: replay dan fresh event dalam dwell tidak memulihkan incident; gate-status passageinfo/latchedFalse padahal red read 1. Stock tidak berubah adalah kontrol desain yang benar. Tidak diklaim lampu/gate fisik atau DOM kiosk diuji.

- `D4-RFID-01-fault-control` — expected `500`; actual `500`; `pass`.
- `D4-RFID-01-original-exit-stamp-control` — expected `"pa_7287e1da23b7"`; actual `"pa_7287e1da23b7"`; `pass`.
- `D4-RFID-01-retry-business-read` — expected `1`; actual `0`; `observed_difference`.
- `D4-RFID-01-retry-decision-count` — expected `1`; actual `0`; `observed_difference`.
- `D4-RFID-01-fresh-event-recovery-verdict` — expected `"MOVEMENT_OUT"`; actual `"REPLAY_EXIT"`; `observed_difference`.
- `D4-RFID-01-stock-unchanged-control` — expected `"in_transit_transfer"`; actual `"in_transit_transfer"`; `pass`.
- `D4-RFID-01-normal-dedupe-control` — expected `{"code": "MOVEMENT_OUT", "reads": 1, "duplicates": 1}`; actual `{"code": "MOVEMENT_OUT", "reads": 1, "duplicates": 1}`; `pass`.
- `D4-RFID-01-red-read-durable-control` — expected `1`; actual `1`; `pass`.
- `D4-RFID-01-red-incident-recovery` — expected `1`; actual `0`; `observed_difference`.
- `D4-RFID-01-red-passage-recovery` — expected `"red"`; actual `"info"`; `observed_difference`.
- `D4-RFID-01-red-latch-recovery` — expected `true`; actual `false`; `observed_difference`.

```python
 135:             "device_id": device["id"], "epc": ev["epc"], "event_id": ev.get("event_id"),
 136:             "captured_at": ev.get("captured_at"), "antenna": ev.get("antenna"), "rssi": ev.get("rssi"),
 137:             "batch_id": batch_id, "source": source, "received_at": now} for ev in evs]
 138:     dup_ids = set()
 139:     if obs:
 140:         try:
 141:             await db.rfid_observations.insert_many(obs, ordered=False)
 142:         except BulkWriteError as bwe:
 143:             dup_ids = {obs[e["index"]]["_id"] for e in bwe.details.get("writeErrors", []) if e.get("code") == 11000}
 144:     fresh = list(dict.fromkeys(o["epc"] for o in obs if o["_id"] not in dup_ids))
 145:     passage = await _passage_for(device, now) if is_gate else None
```

**Prompt perbaikan:**

> Periksa `D4-RFID-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan observation sebagai durable inbox dengan processing state/checkpoint. Per event/decision operation punya read/movement/incident IDs dan passage delta deterministik. Retry melengkapi efek dengan idempotent writes; dwell tidak melewati unfinished operation. Selaraskan exit stamp/read commit melalui transaction/outbox atau resumable sequence dengan provenance. Passage/latch mempertahankan keputusan red durable dan menjelaskan processing/unavailable bila belum final. Pertahankan no-stock-mutation, auth/EPC dan event guards. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault tiap batas observation/stamp/read/incident/passage pulih dari event sama tanpa kehilangan/duplikasi. Green belum final tidak menjadi false replay hanya karena recovery. Red durable menghasilkan satu incident dan red/latched, bukan info. Uji multi-EPC/mixed batch, dwell/new event, restart/reconnect, duplicate/concurrent events, movement change dan acknowledge. Uji perangkat fisik tetap terpisah.

**Hubungan dengan catatan lain:** V3-RFID-01, D4-PA-02, D4-TAG-01

## D4-CC-01 — Recovery cycle count membuat dua laporan dan nomor untuk satu sesi

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/cycle_count_service.py:124](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cycle_count_service.py#L124).

**Lokasi kode lain dalam rantai:** [backend/services/cycle_count_service.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cycle_count_service.py#L129) · [backend/routers/saga_locks.py:33](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L33) · [backend/routers/rfid.py:650](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfid.py#L650).

**Tampilan / rantai terkait:** Lokasi RFID → Cycle Count → Selesaikan; Kunci Saga; riwayat CC/health · Session/scan → result durable → lost acknowledgment → parent open/locked → admin release → new UUID/number on retry.

**Penyebab:** complete membuat UUID/nomor baru tiap eksekusi, insert result kemudian finalize session/link. Retry tidak mengadopsi existing result; startup indexes tidak menjamin satu result/session. Inspector tidak mencari rfid_cycle_counts.session_id.

**Dampak dan batas interpretasi:** Normal public start/scan/complete: accuracy 100, satu result, replay 400. Fault sesudah original result insert:500/result 1/parent locked. Setelah clock aging eksplisit, public admin inspect tidak melihat efek; release 200/complete 200 membuat result 2 untuk sesi sama dengan nomor baru. Tidak mengubah qty stock adalah desain report-only; temuan tentang histori/idempotensi laporan.

- `D4-CC-01-normal-count-control` — expected `{"accuracy": 100, "results": 1, "retry_http": 400}`; actual `{"accuracy": 100.0, "results": 1, "retry_http": 400}`; `pass`.
- `D4-CC-01-fault-control` — expected `500`; actual `500`; `pass`.
- `D4-CC-01-first-result-persisted-control` — expected `1`; actual `1`; `pass`.
- `D4-CC-01-inspect-count-effect` — expected `true`; actual `false`; `observed_difference`.
- `D4-CC-01-one-session-one-result` — expected `1`; actual `2`; `observed_difference`.

```python
 121:         "extra_items": extra_items[:500],
 122:         "created_at": now, "created_by": actor_name,
 123:     }
 124:     await db.rfid_cycle_counts.insert_one(dict(cc))
 125:     await db.rfid_verify_sessions.update_one({"id": session_id}, _saga.finish_set({
 126:         "status": "completed",
 127:         "result": "simulated" if simulated else ("clean" if not missing and not extra_items and not untagged_n else "with_issues"),
 128:         "missing": [m["epc"] for m in missing], "extra": extra_epcs,
 129:         "completed_at": now, "cycle_count_id": cc["id"]}))
 130:     return safe_doc(cc)
 131: 
```

**Prompt perbaikan:**

> Periksa `D4-CC-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist result ID/nomor operation/session sebelum efek, adopt result cocok saat retry dan finalize parent recoverably. Unique session+revision mengikuti policy recount; recount harus revision/session baru eksplisit. Inspector menampilkan CC durable dan langkah recovery. Rekonsiliasikan data existing secara auditable, jangan menghapus histori sembarangan. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Lost acknowledgment atau failed parent update: satu result/nomor dan session completed yang menunjuknya. Uji restart/concurrency/stale lock, recount revision, entity scope, simulated/manual/device evidence dan health/history/export. Stock tidak dimutasi oleh laporan count.

**Hubungan dengan catatan lain:** D4-WMS-02, D4-RFID-01

## D4-TAG-01 — Verifikasi tag lama tetap berlaku setelah tag dihapus atau diganti dengan tag pending

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/putaway_order_service.py:132](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L132).

**Lokasi kode lain dalam rantai:** [backend/services/rfid_service.py:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_service.py#L151) · [backend/services/rfid_print_service.py:130](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_print_service.py#L130) · [backend/services/rfid_print_service.py:327](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_print_service.py#L327) · [backend/services/putaway_order_service.py:108](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L108).

**Tampilan / rantai terkait:** RFID → retire/ganti/cetak/verifikasi tag; Putaway → Buat PA · Verified identity → public retire clears roll tag → old journey tag_verified → PA accepts empty or pending_print EPC.

**Penyebab:** Retire menghapus current tag tetapi tidak menginvalidasi evidence identitas lama. PA percaya journey tag_verified dan lookup tag tanpa active/current verification version. Re-encode lewat print job menghasilkan pending_print yang belum dicetak/verifikasi, tetapi journey lama membuatnya siap bergerak.

**Dampak dan batas interpretasi:** Initial identity berasal dari original public print/mark-printed/manual scan/complete. Public retire 200 membuat current tagNone; PA create 200/EPCkosong. Pada roll kedua, retire→new print job memberi pending_print yang belum ack/scan; PA create juga 200. Bukan fixture tagless arbitrer RF-05: producer lifecycle sendiri menciptakan keadaan ini. Client mensyaratkan semua roll bertag; old identity bukan bukti EPC baru.

- `D4-TAG-01-retire-removes-current-tag-control` — expected `null`; actual `null`; `pass`.
- `D4-TAG-01-retired-putaway-rejected` — expected `true`; actual `false`; `observed_difference`.
- `D4-TAG-01-pending-print-control` — expected `"pending_print"`; actual `"pending_print"`; `pass`.
- `D4-TAG-01-new-unverified-identity-rejected` — expected `true`; actual `false`; `observed_difference`.

```python
 129:         if not check["ok"]:
 130:             violations.append(check["reason"])
 131:             continue
 132:         tag = await db.rfid_tags.find_one({"id": r.get("rfid_tag_id")}, {"_id": 0, "epc": 1}) or {}
 133:         items.append({
 134:             "roll_id": r["id"], "roll_no": r.get("roll_no", ""), "epc": tag.get("epc", ""),
 135:             "sku": p.get("sku", ""), "product_name": p.get("name", ""),
 136:             "category": p.get("category", ""), "grade": r.get("grade", ""),
 137:             "product_id": r["product_id"], "lot": r.get("lot", ""),
 138:             "qty": float(r.get("length_remaining") or 0), "unit": r.get("unit", "meter"),
 139:             "status": "pending",
```

**Prompt perbaikan:**

> Periksa `D4-TAG-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Identity readiness harus terikat roll/current live tag ID/EPC/version dan matching verification evidence. Terapkan konsisten pada suggest/create/dispatch/arrival/loading/gate. Retire/re-encode menginvalidasi readiness tanpa memundurkan physical journey secara keliru. Tag harus active, current, linked correctly, EPC kanonis dan verified sesuai policy. Perubahan identity pada active movement ditolak sebelum efek atau lewat workflow retag/manifest update/reverification yang auditable. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Verified→retire menolak PA tanpa claim dan tidak masuk ready. Pending_print baru belum lolos; sesudah ack/verifikasi sah boleh PA. Uji retire saat PAopen/transit, reprint sama, EPCbaru, wrong-link, cut child, tagrevision, race movement dan loading/gate/CC. Override eksplisit tidak menganggap bukti identitas lama sebagai current.

**Hubungan dengan catatan lain:** D4-RFID-01, D4-WMS-04

