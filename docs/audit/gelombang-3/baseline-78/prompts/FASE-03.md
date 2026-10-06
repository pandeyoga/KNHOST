# Fase 03 — Scope, pricing, commission dan forecasting

Audit baseline `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Baca tracker/temuan rinci dan source saat ini; repo dapat berubah setelah audit. Kerjakan source producer→projection→API→UI dan failure/reversal windows, bukan hanya file yang disebut. Jangan mengganti oracle untuk menutupi bug. Setelah implementasi, tandai implemented_pending_validation dengan commit, daftar file, expected/actual uji, unit/periode/scope, serta batas uji. Jangan mengklaim fixed sebelum review independen.

## V3-PO-01 — Task selisih PO tidak refresh dan kehilangan identitas baris

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/po_variance_task_service.py:51](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/po_variance_task_service.py#L51).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Key task memakai product_id, bukan line_id, dan existing task langsung continue. Received yang berubah tidak memperbarui task/suggested qty. Duplicate product pada PO baru diblokir KN-B15, tetapi dokumen historis masih dapat memiliki dua baris.

**Dampak dan batas interpretasi:** Task awal received 90/short 10; setelah received 95 task tetap 90/10. Fixture legacy dua line MAT dengan shortage 5 dan 100 menghasilkan satu task. Staleness berlaku juga PO satu line biasa.

- `V3-PO-01` — expected `"See original invariant and detailed acceptance"`; actual `{"actual_shortages": [5, 100], "task_count": 1, "task_received": 90.0, "task_short": 10.0, "live_first_received": 95}`; `observed_difference`.

```python
  48:         short = round(ordered - received, 2)
  49:         if received <= 0 or short <= ordered * tol / 100 + 1e-6:
  50:             continue
  51:         key = {"po_id": po_id, "product_id": it.get("product_id"), "status": "open"}
  52:         if await db.po_variance_tasks.find_one(key, {"_id": 1}):
  53:             continue
  54:         task = {
  55:             "id": new_id("pvt"), **key, "entity_id": po.get("entity_id"),
  56:             "po_number": po.get("po_number"), "supplier_name": po.get("supplier_name"),
  57:             "product_name": it.get("product_name") or it.get("name") or "", "unit": it.get("unit", ""),
  58:             "ordered_qty": ordered, "received_qty": received, "short_qty": short, "tolerance_pct": tol,
```

**Prompt perbaikan:**

> Periksa `V3-PO-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Key task harus stable PO line ID/version. Refresh ordered/received/short dan close task bila selesai; keputusan memakai revalidation PO terkini. Migrasi legacy duplicate secara eksplisit, jangan menggabungkan dua harga. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Terima 90 lalu 95: open task received 95/short 5, amendment suggestion 95. Terima 100 menutup obsolete task. Dua legacy line memberi dua task. Race receipt vs decide tidak memakai qty lama.

**Hubungan dengan catatan lain:** W2-REQ-06, FN-02

## V3-CF-01 — Jurnal campuran kas/nonkas menghasilkan klasifikasi arus kas salah

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/cash_flow_service.py:84](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cash_flow_service.py#L84).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Bila satu jurnal menyentuh kas, semua contra line dimasukkan bucket aktivitas. Aset yang sebagian dibayar kas dan sebagian AP dianggap seluruhnya cash investing serta AP dianggap cash operating.

**Dampak dan batas interpretasi:** Jurnal Dr aset 100/Cr kas 40/Cr AP60 menghasilkan investing−100, operating+60, net−40 dan noncash disclosure kosong. Seharusnya investing−40, operating 0 dan noncash asset 60.

- `V3-CF-01` — expected `"See original invariant and detailed acceptance"`; actual `{"expected_investing": -40, "expected_operating": 0, "expected_noncash_asset": 60, "actual_investing": -100.0, "actual_operating": 60.0, "net_change": -40.0, "noncash": []}`; `observed_difference`.

```python
  81:     noncash: Dict[str, float] = {}
  82:     async for je in db.journal_entries.find(q, {"_id": 0, "lines": 1}):
  83:         lines = [ln for ln in je.get("lines", []) if ln.get("account_code")]
  84:         touches_cash = any(ln["account_code"] in cash for ln in lines)
  85:         for ln in lines:
  86:             code = ln["account_code"]
  87:             if code in cash:
  88:                 continue
  89:             eff = -(float(ln.get("debit", 0) or 0) - float(ln.get("credit", 0) or 0))
  90:             sec = _section(amap.get(code, {}).get("type", ""), code)
  91:             if touches_cash:
```

**Prompt perbaikan:**

> Periksa `V3-CF-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Klasifikasi sumber harus membawa settlement cash portion yang eksplisit. Pecah source/mixed journal secara traceable; jangan memperkirakan aktivitas dari seluruh contra balance. Reconcile total kas dan disclosure noncash terpisah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fixture asset cash 40+credit 60 harus CFI−40/CFO 0/noncash 60. Tambahkan asset penuh kredit, cash penuh, bank-to-bank, depreciation, sale credit+receipt dan mixed multiple assets/liabilities. Persetujuan policy akuntan diperlukan untuk metode alokasi ambigu.

**Hubungan dengan catatan lain:** FN-04

## V3-DATE-01 — Jurnal date-only pada awal periode hilang dari laporan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/financial_statement_service.py:31](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L31).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Insert jurnal mempertahankan date yang dikirim, termasuk YYYY-MM-DD. Query start membuat string YYYY-MM-DDT 00:00:00; lexical compare mengeluarkan date-only hari pertama.

**Dampak dan batas interpretasi:** Valid journal beban 10 pada 2026-09-01, laporan 2026-09-01..30: opex 0, seharusnya 10. Nilai tersimpan masih date-only; probe CF lain memakai ISO timestamp agar kesalahan klasifikasi tidak tercampur.

- `V3-DATE-01` — expected `"See original invariant and detailed acceptance"`; actual `{"expected_opex": 10, "actual_opex": 0, "stored_date": "2026-09-01", "filter_start": "2026-09-01T00:00:00"}`; `observed_difference`.

```python
  28: def _day_start(d: Optional[str]) -> Optional[str]:
  29:     if not d:
  30:         return None
  31:     return d if "T" in d else f"{d}T00:00:00"
  32: 
  33: 
  34: def _day_end(d: Optional[str]) -> Optional[str]:
  35:     if not d:
  36:         return None
  37:     return d if "T" in d else f"{d}T23:59:59.999999"
  38: 
```

**Prompt perbaikan:**

> Periksa `V3-DATE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan representasi tanggal kanonik di seluruh entry/create/autopost/import dan query, dengan timezone bisnis disepakati. Migration preview tanggal lama dan conflict report; hindari mengubah label saja atau memperlebar cutoff tanpa aturan. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Date-only/ISO/tz-offset hari awal dan hari akhir periode masuk tepat sekali. Neraca default, ledger, cash flow, closing, unlock dan konsolidasi memakai cutoff sama. Uji jurnal masa depan tetap tidak masuk hari ini.

**Hubungan dengan catatan lain:** FN-16, W2-021

## V3-PO-02 — Pilihan amend ke jumlah diterima bertentangan dengan guard PO lama

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/po_amendment_service.py:103](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/po_amendment_service.py#L103).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Task baru menjanjikan amendment qty aktual, tetapi guard lama mengunci quantity setiap baris yang received_qty>0. Ini gap integrasi dua aturan bisnis, bukan alasan untuk menghapus guard seluruh field finansial.

**Dampak dan batas interpretasi:** Ordered 1000/received 960; suggested amendment 960. amend_po menolak 400 qty 1000→960 walaupun tidak kurang dari received dan tujuannya menutup kekurangan.

- `V3-PO-02` — expected `"See original invariant and detailed acceptance"`; actual `{"ordered": 1000, "received": 960, "suggested_amendment": 960, "error": "400: Baris MAT sudah diterima 960 — terkunci dari revisi (qty 1000→960). Barang yang sudah masuk gudang tidak bisa diubah qty/satuan/harga/diskonnya; buat PO baru untuk tambahan, atau retur beli bila ada selisih."}`; `observed_difference`.

```python
 100:     if not old:
 101:         return
 102:     changed = []
 103:     if abs(float(item_in.quantity or 0) - float(old.get("quantity") or 0)) > 0.001:
 104:         changed.append(f"qty {float(old.get('quantity') or 0):g}→{float(item_in.quantity):g}")
 105:     old_unit = str(old.get("unit") or "").strip().lower()
 106:     new_unit = str(item_in.unit or old.get("unit") or "").strip().lower()
 107:     if new_unit != old_unit:
 108:         changed.append(f"satuan {old.get('unit')}→{item_in.unit}")
 109:     new_price = float(item_in.price or 0)
 110:     if new_price > 0 and abs(new_price - float(old.get("price") or 0)) > 0.001:
```

**Prompt perbaikan:**

> Periksa `V3-PO-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tetapkan flow dedicated receiving-variance amendment atau perbaiki CTA menjadi short-close sesuai policy disepakati. Jika amendment dipilih, target tidak kurang dari received, snapshot/bill/DP dilindungi dan reapproval/credit adjustment eksplisit; jangan rewrite posted GL. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Kasus 1000→960 memiliki jalur selesai yang nyata dan tidak buntu. Received tetap 960; PO version/approval terdokumentasi; vendor bill/AP/DP diperhitungkan terpisah. Jika hanya short-close diperbolehkan, UI tidak menjanjikan amend unsupported.

**Hubungan dengan catatan lain:** W2-REQ-06

## V3-PO-03 — Tugas selisih selesai meski amendment belum disetujui dan qty belum berubah

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/purchase_orders.py:751](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/purchase_orders.py#L751).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Router menyelesaikan seluruh pending_amendment segera sesudah amend_po, sebelum reapproval. Fungsi juga tidak memeriksa apakah perubahan berkaitan dengan shortage line.

**Dampak dan batas interpretasi:** HTTP notes-only amend 200: PO quantity 1000 tetap dan statuswaiting_approval; task shortage received 960 menjadi decided. Persetujuan kuantitas belum terjadi.

- `V3-PO-03` — expected `"See original invariant and detailed acceptance"`; actual `{"http_status": 200, "po_status": "waiting_approval", "po_quantity": 1000, "task_status": "decided", "detail": null}`; `observed_difference`.

```python
 748:     result = await amend_po_service(po_id, payload, actor)
 749:     updated = result["po"]
 750:     from services import po_variance_task_service as _pvt
 751:     await _pvt.close_amendment_tasks(po_id, actor["name"])  # W2-REQ-06
 752:     if result["needs_approval"]:
 753:         from services.notification_service import notify_po_awaiting_approval
 754:         await notify_po_awaiting_approval(updated)
 755:     else:
 756:         await _create_inbound_tasks_for_po(updated)
 757:     return safe_doc(await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}))
 758: 
```

**Prompt perbaikan:**

> Periksa `V3-PO-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Selesaikan task hanya setelah amendment version/line yang ditautkan approved dan acceptance shortage direvalidasi. Notes-only amendment tidak menutup qty task. Rejection/cancel amendment memulihkan action pending yang benar. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Amend notes saja atau awaiting approval: task pending. Approved qty 960/reconciled policy: task selesai. Rejection tetap memerlukan keputusan. Beberapa task/line/versi tidak tertutup sekaligus oleh perubahan unrelated.

**Hubungan dengan catatan lain:** W2-REQ-06

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

