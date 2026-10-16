# Fase 04 — Analytics projection dan employee/marketing/R&D semantics

Audit baseline `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Baca tracker/temuan rinci dan source saat ini; repo dapat berubah setelah audit. Kerjakan source producer→projection→API→UI dan failure/reversal windows, bukan hanya file yang disebut. Jangan mengganti oracle untuk menutupi bug. Setelah implementasi, tandai implemented_pending_validation dengan commit, daftar file, expected/actual uji, unit/periode/scope, serta batas uji. Jangan mengklaim fixed sebelum review independen.

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

