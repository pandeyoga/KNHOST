# Fase 02 — Ownership, reservation, warehouse dan RFID

Audit baseline `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Baca tracker/temuan rinci dan source saat ini; repo dapat berubah setelah audit. Kerjakan source producer→projection→API→UI dan failure/reversal windows, bukan hanya file yang disebut. Jangan mengganti oracle untuk menutupi bug. Setelah implementasi, tandai implemented_pending_validation dengan commit, daftar file, expected/actual uji, unit/periode/scope, serta batas uji. Jangan mengklaim fixed sebelum review independen.

## V3-MRES-01 — Dua PR mencadangkan bahan lebih banyak daripada stok

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/material_reservation_service.py:79](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/material_reservation_service.py#L79).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** free_for_commitment dibaca lalu material_reservations diinsert tanpa claim capacity atau unique reservation logical key. Dua PR dapat membaca jumlah bebas sama.

**Dampak dan batas interpretasi:** Dua approved PR masing-masing 700, recipe yield 1 dan stok 1000 menghasilkan active reservation 1400; shortage 0 pada kedua PR. Barrier hanya menyelaraskan read, tetap memanggil helper asli.

- `V3-MRES-01` — expected `"See original invariant and detailed acceptance"`; actual `{"on_hand_available": 1000, "reserved": 1400.0, "shortage": 0.0, "pr_count": 2}`; `observed_difference`.

```python
  76:         if not pid or need <= 0:
  77:             continue
  78:         entity_id = pr.get("entity_id") or ""
  79:         free = await free_for_commitment(pid, entity_id)
  80:         qty = round(min(need, free), 3)
  81:         doc = {"id": new_id("mres"), "product_id": pid, "owner_entity_id": entity_id,
  82:                "ref_type": "purchase_requisition", "ref_id": pr_id, "pr_id": pr_id, "pr_number": pr.get("number"),
  83:                "pr_line_no": line_no, "output_product_id": line["product_id"],
  84:                "target_output_qty": pre.get("target_output_qty"), "recipe": pre.get("recipe"),
  85:                "required_qty": need, "qty": qty, "shortage_qty": round(need - qty, 3),
  86:                "source_ref_id": pr.get("source_ref_id") or "", "status": ACTIVE,
```

**Prompt perbaikan:**

> Periksa `V3-MRES-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Serialisasi commitment pada key product+owner+unit dan dimensi gudang bila relevan. Reservasi harus CAS terhadap ledger kapasitas yang konsisten dengan sales/MKO; unique PR line/version untuk retry; shortage dilaporkan eksplisit. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Parallel 700+700 atas 1000 tidak pernah reserved>1000. Remaining 400 harus shortage/backorder/approval sesuai policy, tidak dianggap tersedia. Uji race dengan SO, issue/cancel/replan dan input UOM berbeda.

**Hubungan dengan catatan lain:** W2-REQ-07, W2-REQ-04

## V3-WEIGHT-01 — Split bersamaan menggandakan berat walaupun panjang benar

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/roll_service.py:163](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L163).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** insert_child_roll menghitung berat dari snapshot parent lama dan menulis sisa dengan $set; length CAS terpisah tidak menjaga weight total.

**Dampak dan batas interpretasi:** Parent 10m/3kg dipotong 2m dua kali: parent 6m/2.4kg, dua child masing-masing 0.6kg; total 3.6kg, seharusnya 3kg. Panjang 6+2+2 tetap 10.

- `V3-WEIGHT-01` — expected `"See original invariant and detailed acceptance"`; actual `{"initial_length": 10, "remaining_length": 6.0, "initial_weight": 3, "parent_weight": 2.4, "child_weights": [0.6, 0.6], "total_weight": 3.5999999999999996}`; `observed_difference`.

```python
 160:         s["secondary_measures.kg"] = weight
 161:         parent["secondary_measures"] = {**parent["secondary_measures"], "kg": weight}
 162:     parent["weight_kg"] = weight
 163:     await db.inventory_rolls.update_one({"id": parent.get("id")}, {"$set": s})
 164: 
 165: 
 166: # ── Taksonomi status (KN_15 §3.4) ────────────────────────────────────────────
 167: # Bucket FISIK di gudang (menyusun on_hand)
 168: from services.tolerances import QTY_EPS  # KN-A13 — toleransi bersama
 169: 
 170: # KN-A11 — SATU definisi "PO masih terbuka / stok dalam perjalanan" untuk papan Stok/ATP,
```

**Prompt perbaikan:**

> Periksa `V3-WEIGHT-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Simpan reservasi/split berat dan panjang dalam satu conditional update berdimensi version atau ledger cut dengan snapshot terkini. Tidak boleh menulis derived parent weight dari snapshot lama. Tandai estimated_proportional sebagai estimasi, bukan penimbangan aktual. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Parallel split 2+2: parent 6m/1.8kg dan children 0.6+0.6kg. Uji split QC/retur/cut, decimal rounding dan actual reweigh; conservation kg dan meter diuji terpisah.

**Hubungan dengan catatan lain:** W2-019, WM-01

## V3-RFID-01 — Read green dari passage lama dipakai kembali pada passage baru

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/rfid_ingest_service.py:149](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L149).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Cache dwell 120 detik mengembalikan verdict read sebelumnya sebelum evaluator dijalankan. Passage window 10 detik; event_id baru 20 detik kemudian membentuk passage baru tetapi tetap memakai verdict lama.

**Dampak dan batas interpretasi:** Event pertama green dan mencatat gate_exit. Sesudah SO cancelled, event UUID baru pada gate sama+20 detik tetapgreen duplicate=true dan passage ID berbeda; evaluator state sekarang red REPLAY_EXIT.

- `V3-RFID-01` — expected `"See original invariant and detailed acceptance"`; actual `{"first": "green", "fresh_event_after_seconds": 20, "second": "green", "duplicate": true, "current_evaluator_result": "red", "current_evaluator_code": "REPLAY_EXIT", "different_passage": true}`; `observed_difference`.

```python
 146:     dwell_cut = (_ts(now) - timedelta(seconds=DWELL_S)).isoformat()
 147:     results, reads = [], []
 148:     for raw in fresh:
 149:         prev = await db.rfid_reads.find_one({"device_id": device["id"], "epc": raw, "timestamp": {"$gte": dwell_cut}},
 150:                                             {"_id": 0}, sort=[("timestamp", -1)])
 151:         if prev:  # tag diam / passage sama — bukan event bisnis baru (tanpa insiden baru)
 152:             await db.rfid_reads.update_one({"id": prev["id"]}, {"$set": {"last_observed_at": now},
 153:                                                                "$inc": {"observation_count": 1}})
 154:             results.append({"epc": raw, "result": prev["result"], "code": prev.get("code"), "reason": prev["reason"],
 155:                             "action": prev.get("action"),
 156:                             "roll_no": prev.get("roll_no"), "sku": prev.get("sku"),
```

**Prompt perbaikan:**

> Periksa `V3-RFID-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bedakan replay event ID dan noisy repeated sensor read dari otorisasi passage baru. Cache tidak boleh melintasi passage atau versi shipment/QC/tag; evaluasi ulang current state untuk event baru yang memulai passage. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Same-gate event berbeda pada+20 detik harus red ketika replay exit/SO cancelled/tag retired/QC hold. Repeated event_id tetap idempoten. Dwell dalam passage tidak menggandakan mutation/incident; worst verdict passage tetap red.

**Hubungan dengan catatan lain:** RF-02, RF-16

## V3-WMS-02 — Loading gudang siap ditahan oleh pending cut gudang lain

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/loading_check_service.py:38](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/loading_check_service.py#L38).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Start loading check memanggil guard atas seluruh SO dan API tidak memberi warehouse/shipment subset. SO-wide session mencampurkan readiness shipment yang berbeda.

**Dampak dan batas interpretasi:** Satu tagged committed roll diWH siap; pending cut product lain diWH 2. Guard local WH lulus, start loading check SO409: satu reservasi potong belum dikonfirmasi di gudang lain.

- `V3-WMS-02` — expected `"See original invariant and detailed acceptance"`; actual `{"local_ready_tagged_rolls": 1, "local_cut_guard": "passed", "pending_cuts_other_warehouse": 1, "loading_check_start_error": "409: 1 reservasi potong belum dikonfirmasi (roll induk RL-00010). Potong fisik & konfirmasi dulu."}`; `observed_difference`.

```python
  35:     if existing:
  36:         return safe_doc(existing)
  37:     from services.roll_service import assert_cut_identity_ready
  38:     await assert_cut_identity_ready(order_id)  # WM-02 — potong dikonfirmasi & tag anak terverifikasi
  39:     rolls = await _expected_rolls(order_id)
  40:     if not rolls:
  41:         raise HTTPException(status_code=400, detail="Tidak ada roll ter-alokasi untuk SO ini (pick dulu).")
  42:     tag_ids = [r["rfid_tag_id"] for r in rolls if r.get("rfid_tag_id")]
  43:     tags = {t["id"]: t for t in await db.rfid_tags.find(
  44:         {"id": {"$in": tag_ids}, "status": "active"}, {"_id": 0}).to_list(2000)}
  45:     expected, untagged = [], []
```

**Prompt perbaikan:**

> Periksa `V3-WMS-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bentuk loading session per shipment/task group+warehouse+manifest version. Expected EPC dan cut guard hanya untuk shipment itu; perubahan manifest mengharuskan check ulang. Parent SO menampilkan agregat progres, bukan satu clean global. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** SO woven/knit/printing tiga gudang: WHwoven dapat check/dispatch/SJ sendiri saat cut WHknit tertunda. Check A tidak membuka B. Shipment parsial dan driver gabungan tetap mempunyai manifest dokumen yang konsisten.

**Hubungan dengan catatan lain:** RF-06, W2-REQ-08

## V3-MRES-02 — Total cadangan maklon tetap terpotong pada batas query

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/material_reservation_service.py:44](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/material_reservation_service.py#L44).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** reserved_by_others memakai 2000, _on_hand_available500 dan apply_to_products5000 untuk total bisnis, bukan daftar berhalaman. Cadangan yang dilewatkan dapat dijanjikan lagi ke sales.

**Dampak dan batas interpretasi:** 2001 active reservation masing-masing 1 menghasilkan reserved_by_others2000. Selisih 1 terukur; batas 500/5000 lain dikonfirmasi statis, belum diuji runtime pada probe ini.

- `V3-MRES-02` — expected `"See original invariant and detailed acceptance"`; actual `{"expected_reserved": 2001, "actual_reserved": 2000.0, "document_count": 2001}`; `observed_difference`.

```python
  41:     q: Dict[str, Any] = {"product_id": product_id, "owner_entity_id": entity_id, "status": ACTIVE}
  42:     if exclude_ref_id:
  43:         q["ref_id"] = {"$ne": exclude_ref_id}
  44:     rows = await db.material_reservations.find(q, {"_id": 0, "qty": 1}).to_list(2000)
  45:     return round(sum(float(r.get("qty") or 0) for r in rows), 3)
  46: 
  47: 
  48: async def free_for_commitment(product_id: str, entity_id: str, exclude_ref_id: str = "",
  49:                               warehouse_id: str = "") -> float:
  50:     return round(max(await _on_hand_available(product_id, entity_id, warehouse_id)
  51:                      - await reserved_by_others(product_id, entity_id, exclude_ref_id), 0.0), 3)
```

**Prompt perbaikan:**

> Periksa `V3-MRES-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan aggregate/kursor penuh untuk seluruh total. Batasi hanya endpoint list berhalaman dengan total terpisah. Harmonisasi owner, product, unit, warehouse dan exclusion ref agar sales dan PR memakai angka sama. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Cap−1/cap/cap+1 pada 2000 reservations,500 balances,5000 catalog reservations serta>10000 roll allocation harus konsisten. Test total/UI/guard commit dan cancellation tidak memakai subset sebagai SSOT.

**Hubungan dengan catatan lain:** GN-12, W2-REQ-07, W2-REQ-04

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

