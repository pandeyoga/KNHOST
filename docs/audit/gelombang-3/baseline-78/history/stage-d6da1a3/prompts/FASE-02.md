# Fase 02 — Ownership, reservation, warehouse dan RFID

Audit baseline `d6da1a3d536228582645abb98aea19f3e491f300`. Baca tracker/temuan rinci dan source saat ini; repo dapat berubah setelah audit. Kerjakan source producer→projection→API→UI dan failure/reversal windows, bukan hanya file yang disebut. Jangan mengganti oracle untuk menutupi bug. Setelah implementasi, tandai implemented_pending_validation dengan commit, daftar file, expected/actual uji, unit/periode/scope, serta batas uji. Jangan mengklaim fixed sebelum review independen.

## V3-MRES-01 — Dua PR mencadangkan bahan lebih banyak daripada stok

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/material_reservation_service.py:79](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/material_reservation_service.py#L79).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** free_for_commitment dibaca lalu material_reservations diinsert tanpa claim capacity atau unique reservation logical key. Dua PR dapat membaca jumlah bebas sama.

**Dampak dan batas interpretasi:** Dua approved PR masing-masing700, recipe yield1 dan stok1000 menghasilkan active reservation1400; shortage0 pada kedua PR. Barrier hanya menyelaraskan read, tetap memanggil helper asli.

**Observasi:** Dua approved PR masing-masing700, recipe yield1 dan stok1000 menghasilkan active reservation1400; shortage0 pada kedua PR. Barrier hanya menyelaraskan read, tetap memanggil helper asli.

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

> Periksa `V3-MRES-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Serialisasi commitment pada key product+owner+unit dan dimensi gudang bila relevan. Reservasi harus CAS terhadap ledger kapasitas yang konsisten dengan sales/MKO; unique PR line/version untuk retry; shortage dilaporkan eksplisit. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Parallel700+700 atas1000 tidak pernah reserved>1000. Remaining400 harus shortage/backorder/approval sesuai policy, tidak dianggap tersedia. Uji race dengan SO, issue/cancel/replan dan input UOM berbeda.

**Hubungan dengan catatan lain:** W2-REQ-07, W2-REQ-04

## V3-WEIGHT-01 — Split bersamaan menggandakan berat walaupun panjang benar

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/roll_service.py:163](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/roll_service.py#L163).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** insert_child_roll menghitung berat dari snapshot parent lama dan menulis sisa dengan $set; length CAS terpisah tidak menjaga weight total.

**Dampak dan batas interpretasi:** Parent10m/3kg dipotong2m dua kali: parent6m/2.4kg, dua child masing-masing0.6kg; total3.6kg, seharusnya3kg. Panjang6+2+2 tetap10.

**Observasi:** Parent10m/3kg dipotong2m dua kali: parent6m/2.4kg, dua child masing-masing0.6kg; total3.6kg, seharusnya3kg. Panjang6+2+2 tetap10.

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

> Periksa `V3-WEIGHT-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Simpan reservasi/split berat dan panjang dalam satu conditional update berdimensi version atau ledger cut dengan snapshot terkini. Tidak boleh menulis derived parent weight dari snapshot lama. Tandai estimated_proportional sebagai estimasi, bukan penimbangan aktual. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Parallel split2+2: parent6m/1.8kg dan children0.6+0.6kg. Uji split QC/retur/cut, decimal rounding dan actual reweigh; conservation kg dan meter diuji terpisah.

**Hubungan dengan catatan lain:** W2-019, WM-01

## V3-RFID-01 — Read green dari passage lama dipakai kembali pada passage baru

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/rfid_ingest_service.py:149](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/rfid_ingest_service.py#L149).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Cache dwell120detik mengembalikan verdict read sebelumnya sebelum evaluator dijalankan. Passage window10detik; event_id baru20detik kemudian membentuk passage baru tetapi tetap memakai verdict lama.

**Dampak dan batas interpretasi:** Event pertama green dan mencatat gate_exit. Sesudah SO cancelled, event UUID baru pada gate sama+20detik tetapgreen duplicate=true dan passage ID berbeda; evaluator state sekarang red REPLAY_EXIT.

**Observasi:** Event pertama green dan mencatat gate_exit. Sesudah SO cancelled, event UUID baru pada gate sama+20detik tetapgreen duplicate=true dan passage ID berbeda; evaluator state sekarang red REPLAY_EXIT.

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

> Periksa `V3-RFID-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bedakan replay event ID dan noisy repeated sensor read dari otorisasi passage baru. Cache tidak boleh melintasi passage atau versi shipment/QC/tag; evaluasi ulang current state untuk event baru yang memulai passage. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Same-gate event berbeda pada+20detik harus red ketika replay exit/SO cancelled/tag retired/QC hold. Repeated event_id tetap idempoten. Dwell dalam passage tidak menggandakan mutation/incident; worst verdict passage tetap red.

**Hubungan dengan catatan lain:** RF-02, RF-16

## V3-WMS-02 — Loading gudang siap ditahan oleh pending cut gudang lain

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/loading_check_service.py:38](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/loading_check_service.py#L38).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Start loading check memanggil guard atas seluruh SO dan API tidak memberi warehouse/shipment subset. SO-wide session mencampurkan readiness shipment yang berbeda.

**Dampak dan batas interpretasi:** Satu tagged committed roll diWH siap; pending cut product lain diWH2. Guard local WH lulus, start loading check SO409: satu reservasi potong belum dikonfirmasi di gudang lain.

**Observasi:** Satu tagged committed roll diWH siap; pending cut product lain diWH2. Guard local WH lulus, start loading check SO409: satu reservasi potong belum dikonfirmasi di gudang lain.

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

> Periksa `V3-WMS-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bentuk loading session per shipment/task group+warehouse+manifest version. Expected EPC dan cut guard hanya untuk shipment itu; perubahan manifest mengharuskan check ulang. Parent SO menampilkan agregat progres, bukan satu clean global. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** SO woven/knit/printing tiga gudang: WHwoven dapat check/dispatch/SJ sendiri saat cut WHknit tertunda. Check A tidak membuka B. Shipment parsial dan driver gabungan tetap mempunyai manifest dokumen yang konsisten.

**Hubungan dengan catatan lain:** RF-06, W2-REQ-08

## V3-MRES-02 — Total cadangan maklon tetap terpotong pada batas query

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/material_reservation_service.py:44](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/material_reservation_service.py#L44).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** reserved_by_others memakai2000, _on_hand_available500 dan apply_to_products5000 untuk total bisnis, bukan daftar berhalaman. Cadangan yang dilewatkan dapat dijanjikan lagi ke sales.

**Dampak dan batas interpretasi:** 2001 active reservation masing-masing1 menghasilkan reserved_by_others2000. Selisih1 terukur; batas500/5000 lain dikonfirmasi statis, belum diuji runtime pada probe ini.

**Observasi:** 2001 active reservation masing-masing1 menghasilkan reserved_by_others2000. Selisih1 terukur; batas500/5000 lain dikonfirmasi statis, belum diuji runtime pada probe ini.

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

> Periksa `V3-MRES-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan aggregate/kursor penuh untuk seluruh total. Batasi hanya endpoint list berhalaman dengan total terpisah. Harmonisasi owner, product, unit, warehouse dan exclusion ref agar sales dan PR memakai angka sama. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Cap−1/cap/cap+1 pada2000reservations,500balances,5000catalog reservations serta>10000roll allocation harus konsisten. Test total/UI/guard commit dan cancellation tidak memakai subset sebagai SSOT.

**Hubungan dengan catatan lain:** GN-12, W2-REQ-07, W2-REQ-04

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

