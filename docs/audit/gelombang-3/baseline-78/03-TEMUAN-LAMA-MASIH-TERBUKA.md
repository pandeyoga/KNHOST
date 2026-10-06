# Temuan validasi sebelumnya yang masih terbuka

17 counterexample runtime dijalankan kembali terhadap commit terbaru; dua catatan statis diperiksa ulang. Rinciannya tidak menyatakan semua kasus W1/W2 gagal: celah berikut dapat muncul pada failure window atau kombinasi data yang lebih luas.

## V3-PROD-01 — Konsumsi bahan dapat berulang setelah movement insert gagal

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/production_service.py:363](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/production_service.py#L363).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** CAS mengurangi roll sebelum journal inventory_movements ditulis. Recovery menghitung konsumsi dari movement; write yang gagal tidak tercatat, sehingga retry mengonsumsi lagi.

**Dampak dan batas interpretasi:** Stok 20→15 saat gagal insert movement; retry 20→10 untuk output 5, sementara movement/reported consumption hanya 5. Tidak ada crash sesudah commit yang diasumsikan: fault terjadi sebelum insert.

- `V3-PROD-01` — expected `"See original invariant and detailed acceptance"`; actual `{"error": "RuntimeError", "before_qty": 20, "after_fault_qty": 15.0, "after_retry_qty": 10.0, "output": 5.0, "reported_consumed": 5.0, "movement_qty": 5.0}`; `observed_difference`.

```python
 360:             if not won:
 361:                 continue  # roll berubah/di-hold bersamaan — dicoba lagi di putaran berikut
 362:             uc = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
 363:             await db.inventory_movements.insert_one({
 364:                 "id": new_id("mov"), "product_id": product_id, "warehouse_id": warehouse_id,
 365:                 "owner_entity_id": owner_entity_id, "movement_type": "production_consume",
 366:                 "quantity": -take, "unit": r.get("unit", "meter"), "lot": r.get("lot", ""),
 367:                 "lot_id": r.get("lot_id", ""), "roll_id": r["id"], "unit_cost": uc,
 368:                 "qty_rolls": 1, "source_document": wo_id, "operation_id": op_id, "timestamp": now_iso(),
 369:             })
 370:             value += take * uc
```

**Prompt perbaikan:**

> Periksa `V3-PROD-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Buat operasi konsumsi per material/roll dengan identity stabil dan state durable sebelum efek, lalu lakukan perubahan fisik dan ledger dalam transaksi atau step idempoten yang dapat direkonsiliasi. Jangan menyelesaikan recovery hanya dari movement yang mungkin belum lahir. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum/sesudah tiap write, retry key sama/berbeda dan dua worker: stok 20→15, output 5, movement 5 tepat sekali. Recovery harus bekerja melalui endpoint sah; penghapusan lock di probe hanya kontrol pemulihan lokal.

**Hubungan dengan catatan lain:** GN-06, GN-11, W2-024

## V3-PROD-02 — Reversal dianggap selesai sebelum panjang roll dipulihkan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/production_service.py:389](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/production_service.py#L389).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Movement ditandai reversed sebelum update stok. Kalau update stok gagal, retry mengecualikan movement tersebut dan tidak melakukan restore.

**Dampak dan batas interpretasi:** Roll tersisa 5 dari awal 10; restore gagal sebelum update. Retry restored 0, roll tetap 5 dan movement reversed=true.

- `V3-PROD-02` — expected `"See original invariant and detailed acceptance"`; actual `{"retry_restored": 0.0, "remaining": 5, "movement_reversed": true}`; `observed_difference`.

```python
 386:     async for m in db.inventory_movements.find(
 387:             {"operation_id": op_id, "movement_type": "production_consume", "reversed": {"$ne": True}}, {"_id": 0}):
 388:         mark = await db.inventory_movements.update_one(
 389:             {"id": m["id"], "reversed": {"$ne": True}}, {"$set": {"reversed": True, "reversed_at": now_iso()}})
 390:         if mark.modified_count != 1:
 391:             continue
 392:         qty = -float(m["quantity"])
 393:         await db.inventory_rolls.update_one({"id": m["roll_id"]}, [
 394:             {"$set": {"status": {"$cond": [{"$eq": ["$status", "consumed"]}, "available", "$status"]},
 395:                       "length_remaining": {"$round": [{"$add": ["$length_remaining", qty]}, 2]},
 396:                       "updated_at": now_iso()}}])
```

**Prompt perbaikan:**

> Periksa `V3-PROD-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Claim reversal dengan token/stage dan stable operation ID. Commit restore stock dengan marker yang sama secara atomik, atau simpan progress yang membedakan claimed dari applied; retry memeriksa kontribusi aktual. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Restore operasi 5 selalu menghasilkan roll 10, satu reversal movement dan projection 10, termasuk fault restore dan dua worker; jangan double-increment saat response hilang.

**Hubungan dengan catatan lain:** GN-06, GN-11

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

## V3-AR-01 — Receipt gagal dibuat tetapi SO terbayar dan deposit kembali utuh

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/ar_receipt_service.py:448](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/ar_receipt_service.py#L448).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Receipt mengurangi deposit, mengalokasikan payments ke SO, baru insert receipt. Except mengembalikan deposit tetapi tidak membatalkan alokasi SO. Tidak ada receipt durable untuk resume.

**Dampak dan batas interpretasi:** Saldo deposit 100; fault sebelum insert ar_receipts: SO paid_total100/payments 1, customer deposit 100, receipt count 0. Saldo yang sama bisa dipakai lagi.

- `V3-AR-01` — expected `"See original invariant and detailed acceptance"`; actual `{"error": "RuntimeError('Synthetic receipt insert fault BEFORE write')", "paid_total": 100.0, "payments": 1, "deposit": 100.0, "receipts": 0}`; `observed_difference`.

```python
 445:     receipt_id = new_id("arc")
 446:     number = await next_doc_number("ar_receipts", "number", "AR-", entity_id=entity_id)
 447:     # W2-017 — dana deposit DIRESERVASI (CAS) sebelum alokasi SO; gagal → 409 tanpa efek apa pun.
 448:     await _adjust_deposit(customer["id"], -use_deposit_amount)
 449:     try:
 450:         return await _create_receipt_after_reserve(payload, actor, customer, amount, use_deposit_amount,
 451:                                                    total_funds, method, receipt_date, entity_id,
 452:                                                    receipt_id, number)
 453:     except BaseException:
 454:         if not await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 1}):
 455:             await _adjust_deposit(customer["id"], use_deposit_amount)   # kompensasi reservasi
```

**Prompt perbaikan:**

> Periksa `V3-AR-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist receipt operation sebelum allocations. Setiap alokasi harus terkait stable receipt ID dan dapat resume/compensate tanpa menghapus payment milik operasi lain. Tangani insert/GL/cash/deposit sebagai satu protokol durable. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum receipt insert, setelah SO allocation, sebelum/sesudah GL dan saat rollback. Akhir harus semua effect 100 tepat sekali atau semua batal; tidak ada SO paid tanpa receipt/deposit konsumsi. Uji multi-SO dan pembayaran bersamaan.

**Hubungan dengan catatan lain:** FN-10, W2-017

## V3-BANK-01 — Satu baris bank dapat direkonsiliasi ke dua transaksi kas penuh

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/bank_recon_service.py:614](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/bank_recon_service.py#L614).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** CAS membatasi capacity cash transaction, tetapi statement line ditulis berdasarkan ID tanpa claim status/version/capacity yang sama. Dua transaksi berbeda dapat sama-sama mengklaim line bank.

**Dampak dan batas interpretasi:** Statement 100; dua manual_match berbeda 100+100: line allocated 100, cash reconciled 200, kedua cash mencantumkan matched_line_ids BL.

- `V3-BANK-01` — expected `"See original invariant and detailed acceptance"`; actual `{"statement_amount": 100, "statement_allocated": 100.0, "cash_reconciled": 200.0, "linked_cash_count": 2}`; `observed_difference`.

```python
 611:             raise ValueError("Sisa transaksi buku tidak cukup (baru saja dipakai proses lain / alokasi ganda).")
 612:         claimed.append({"txn_id": a["txn_id"], "amount": amt})
 613:     txn_ids = [a["txn_id"] for a in allocations]
 614:     await db.bank_statement_lines.update_one({"id": line["id"]}, {"$set": {
 615:         "status": "matched", "match_kind": match_kind,
 616:         "matched_txn_id": txn_ids[0] if len(txn_ids) == 1 else "",
 617:         "matched_txn_ids": txn_ids, "allocations": allocations,
 618:         "match_type": match_type, "matched_at": now, "matched_by": actor,
 619:         "updated_at": now}})
 620:     for a in allocations:
 621:         t = await db.cash_transactions.find_one({"id": a["txn_id"]}, {"_id": 0})
```

**Prompt perbaikan:**

> Periksa `V3-BANK-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Claim kedua sisi allocation dengan stable match operation dan transaksi/compensation idempoten. Revalidate statement remaining setelah claim; jangan hanya melindungi tiap cash record. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Dua matching paralel atas line 100: satu sukses dan satu conflict atau total allocated 100. Jumlah dari statement links harus sama dengan cash links. Uji split, duplicate payload, unlink/rerun/fault antar-write.

**Hubungan dengan catatan lain:** CX-07, CX-06

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

## V3-MKO-01 — Retry penerimaan maklon menambah output fisik dan nilai stok

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/makloon_order_service.py:1093](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/makloon_order_service.py#L1093).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Progress lots disimpan sesudah seluruh loop output. Output pertama yang sudah dibuat tidak tersimpan dalam progress jika pembuatan kedua gagal. Retry membuat seluruh roll lagi.

**Dampak dan batas interpretasi:** Input 10, dua output 5; fault sebelum create output kedua:1 roll. Retry:3 roll=15; inventory value 180 sedangkan jurnal receipt 120 untuk output 10.

- `V3-MKO-01` — expected `"See original invariant and detailed acceptance"`; actual `{"error": "RuntimeError('Synthetic second output failure BEFORE write')", "rolls_after_fault": 1, "rolls_after_retry": 3, "expected_output": 10, "actual_output": 15.0, "roll_value": 180.0, "journal_value": 120.0}`; `observed_difference`.

```python
1090:     _mko_ref = {"type": "makloon_order", "id": mko_id,
1091:                 "number": f"{order.get('mko_number')} step{seq}"}
1092:     _last = len(rolls_in) - 1
1093:     for _i, r in enumerate(rolls_in if not prog.get("lots") else []):
1094:         _len = round(float(r["length"]), 2)
1095:         _uc = out_uc
1096:         if _i == _last and _len > 0:
1097:             _prior = sum(round(round(float(x["length"]), 2) * out_uc, 2) for x in rolls_in[:_last])
1098:             _uc = round((output_value - _prior) / _len, 6)
1099:         roll = await create_inbound_roll(
1100:             out_pid, r.get("warehouse_id") or out_wh, entity_id, _len,
```

**Prompt perbaikan:**

> Periksa `V3-MKO-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Beri deterministic roll identity per operation+receipt line/index sebelum loop. Persist plan dan state tiap output sebelum/bersama creation; resume harus reconcile actual roll dan movement sebelum membuat lagi. Simpan original warehouse/lot/cost snapshot. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault pada output 1/2/N serta setelah jurnal/status: output total 10 dan dua roll saja, inventory value sama GL120. Uji partial multi-gudang, duplicate lot input, response-lost dan authorized saga recovery.

**Hubungan dengan catatan lain:** CX-13, W2-001, GN-11

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

## V3-MASTER-01 — Apply master mengubah produk sebelum snapshot batch durable

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/master_governance_service.py:96](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/master_governance_service.py#L96).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Apply mengubah produk dan last_governance_batch lalu insert dokumen batch before/after. Jika insert gagal, perubahan tidak mempunyai snapshot rollback.

**Dampak dan batas interpretasi:** Stage produk greige→grey dan last_governance_batch terisi; fault sebelum insert batch: durable_batch_count0. Rollback batch yang dijanjikan tidak tersedia.

- `V3-MASTER-01` — expected `"See original invariant and detailed acceptance"`; actual `{"error": "RuntimeError('Synthetic batch journal failure BEFORE write')", "original_stage": "greige", "current_stage": "grey", "batch_reference": "mgb_5a8480b0aa4d", "durable_batch_count": 0}`; `observed_difference`.

```python
  93:                             "before": p["from"], "after": p["to"]})
  94:     batch = {"id": batch_id, "status": "applied", "note": (note or "").strip(), "changes": changes,
  95:              "preview_signature": signature, "applied_by": actor.get("name", ""), "applied_at": now_iso()}
  96:     await db.master_governance_batches.insert_one(dict(batch))
  97:     return safe_doc(batch)
  98: 
  99: 
 100: async def rollback_batch(batch_id: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
 101:     if len((reason or "").strip()) < 5:
 102:         raise HTTPException(status_code=422, detail="Alasan rollback wajib (min. 5 karakter).")
 103:     b = await db.master_governance_batches.find_one_and_update(
```

**Prompt perbaikan:**

> Periksa `V3-MASTER-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist batch plan/hash/before snapshots dan stage prepared sebelum produk diubah; pakai CAS version tiap produk dan idempoten operation. Progress parsial harus bisa resume/rollback tanpa menimpa edit sesudahnya. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum/antara product update dan batch insert menghasilkan batch recoverable atau tidak ada perubahan. Uji multi-produk, edits concurrent, dry-run signature stale, rollback conflict dan retry identitas sama.

**Hubungan dengan catatan lain:** W2-REQ-02

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

## V3-CUT-01 — Gagal membuat child cut menghilangkan stok dan reservasi

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/roll_service.py:614](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L614).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Parent decrement dan pull reservation dilakukan sebelum child insert. Bila insert gagal sebelum write, tidak ada durable cut command yang dapat melanjutkan dan reservation telah hilang.

**Dampak dan batas interpretasi:** Awal 10/reserve 3; fault child insert: parent 7, reserved 0, child 0. Retry confirm_cut404 reservasi tidak ditemukan/sudah dipotong. Stok fisik total data berkurang 3 tanpa child.

- `V3-CUT-01` — expected `"See original invariant and detailed acceptance"`; actual `{"before_length": 10, "after_length": 7.0, "length_reserved": 0, "child_count": 0, "error": "Synthetic cut child insert fault BEFORE write", "retry_error": "404: Reservasi potong tidak ditemukan / sudah dipotong"}`; `observed_difference`.

```python
 611:         "status": rsv.get("status") or "reserved", "reserved_ref": rsv["ref"], "earmarked_for": None,
 612:         "is_remnant": False, "cut": cut, "journey": {"stage": "cut_pending_tag", "updated_at": now_iso()},
 613:         "created_at": now_iso(), "updated_at": now_iso()})
 614:     child = await insert_child_roll(child, parent)
 615:     await db.inventory_movements.insert_one({
 616:         "id": new_id("mov"), "product_id": parent["product_id"], "warehouse_id": parent["warehouse_id"],
 617:         "owner_entity_id": parent.get("owner_entity_id"), "movement_type": "roll_cut",
 618:         "quantity": 0, "unit": parent.get("unit", "meter"), "lot": parent.get("lot", ""),
 619:         "roll_id": child["id"], "parent_roll_id": roll_id, "qty_rolls": 1,
 620:         "source_document": rsv["ref"]["id"], "cut": cut, "timestamp": now_iso()})
 621:     if waste > 0:
```

**Prompt perbaikan:**

> Periksa `V3-CUT-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist cut operation dan output identity stabil sebelum mutation; parent/reservation/child/movement/weight/tag lifecycle satu transaksi atau recoverable state machine. Retry mencari cut operation lama, bukan hanya reservation yang sudah dipull. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault setiap tahap cut 100→70+30 selalu conservation quantity/value/weight+documented waste; retry menghasilkan satu child dan satu movement, tag identity baru harus diverifikasi sebelum loading. Tidak boleh menambah kembali parent bila child sudah ada.

**Hubungan dengan catatan lain:** WM-01, WM-02, W2-REQ-09, GN-11

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

## V3-DUP-01 — Helper _clean_perms didefinisikan dua kali

**Prioritas:** P3 · **Status:** confirmed_open · **Bukti:** static_quality_observation.

**Letak:** [backend/services/custom_role_service.py:60](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/custom_role_service.py#L60).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** AST seluruh backend menemukan dua definisi top-level identik pada baris 60 dan 67. Definisi kedua menimpa pertama; body kini sama sehingga ini maintainability debt, bukan beda perilaku akses.

**Dampak dan batas interpretasi:** Dua definisi identik pada file yang sama; syntax parser tidak menolaknya.

**Observasi:** Dua definisi identik pada file yang sama; syntax parser tidak menolaknya.

```python
  57:     return out
  58: 
  59: 
  60: def _clean_perms(perms: Any) -> Dict[str, List[str]]:
  61:     try:
  62:         return clean_permissions(perms)
  63:     except ValueError as exc:
  64:         raise HTTPException(status_code=400, detail=str(exc)) from exc
  65: 
  66: 
  67: def _clean_perms(perms: Any) -> Dict[str, List[str]]:
```

**Prompt perbaikan:**

> Periksa `V3-DUP-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Hapus definisi identik dengan satu canonical helper; tambahkan deteksi duplicate top-level definition dalam quality check yang sesuai, tanpa menggandakan business-rule tests. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Satu definisi, custom permission normal/error contract tetap sama. Jangan menjadikan ini P1 atau menghitungnya sebagai bug akses yang sudah terbukti.

**Hubungan dengan catatan lain:** GN-15

## V3-BUILD-01 — Dependency build frontend tidak mempunyai lockfile terlacak

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** static_quality_observation.

**Letak:** [frontend/package.json:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/package.json#L151).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Repo mendeklarasikan Yarn 1.22.22 tetapi tidak melacak yarn.lock, package-lock.json atau pnpm-lock.yaml. Fresh install harus meresolusikan dependency transitive; dua build tidak mempunyai dependency graph terkunci.

**Dampak dan batas interpretasi:** Install lokal melaporkan No lockfile found; build berhasil dengan warnings memakai dependency graph yang diselesaikan hari audit. Ini risiko reproducibility, bukan bukti frontend gagal build.

**Observasi:** Install lokal melaporkan No lockfile found; build berhasil dengan warnings memakai dependency graph yang diselesaikan hari audit. Ini risiko reproducibility, bukan bukti frontend gagal build.

```json
 148:     "**/tinyglobby/picomatch": "4.0.4",
 149:     "http-proxy-middleware": "2.0.10"
 150:   },
 151:   "packageManager": "yarn@1.22.22+sha512.a6b2f7906b721bba3d67d4aff083df04dad64c399707841b7acf00f6b133b7ac24255f2652fa22ae3534329dc6180534e98d17432037ff6fd140556e2bb3137e"
 152: }
```

**Prompt perbaikan:**

> Periksa `V3-BUILD-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Commit satu lockfile canonical sesuai packageManager; pipeline harus gagal jika lock tidak ada/berbeda dan memakai frozen/immutable install. Simpan runtime versions dan dependency integrity. Jangan commit node_modules/build/.env. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fresh isolated install pada dua runner memakai graph/integrity sama. Build smoke lulus dari lock, lint warning relevan ditinjau; packageManager dan pipeline tidak saling memilih manager berbeda.

**Hubungan dengan catatan lain:** GN-15

