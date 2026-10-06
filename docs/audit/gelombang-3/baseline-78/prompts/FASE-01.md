# Fase 01 — Durability stock dan finance

Audit baseline `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Baca tracker/temuan rinci dan source saat ini; repo dapat berubah setelah audit. Kerjakan source producer→projection→API→UI dan failure/reversal windows, bukan hanya file yang disebut. Jangan mengganti oracle untuk menutupi bug. Setelah implementasi, tandai implemented_pending_validation dengan commit, daftar file, expected/actual uji, unit/periode/scope, serta batas uji. Jangan mengklaim fixed sebelum review independen.

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

