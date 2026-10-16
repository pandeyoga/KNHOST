# Fase 01 — Durability stock dan finance

Audit baseline `d6da1a3d536228582645abb98aea19f3e491f300`. Baca tracker/temuan rinci dan source saat ini; repo dapat berubah setelah audit. Kerjakan source producer→projection→API→UI dan failure/reversal windows, bukan hanya file yang disebut. Jangan mengganti oracle untuk menutupi bug. Setelah implementasi, tandai implemented_pending_validation dengan commit, daftar file, expected/actual uji, unit/periode/scope, serta batas uji. Jangan mengklaim fixed sebelum review independen.

## V3-PROD-01 — Konsumsi bahan dapat berulang setelah movement insert gagal

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/production_service.py:363](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/production_service.py#L363).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** CAS mengurangi roll sebelum journal inventory_movements ditulis. Recovery menghitung konsumsi dari movement; write yang gagal tidak tercatat, sehingga retry mengonsumsi lagi.

**Dampak dan batas interpretasi:** Stok20→15 saat gagal insert movement; retry20→10 untuk output5, sementara movement/reported consumption hanya5. Tidak ada crash sesudah commit yang diasumsikan: fault terjadi sebelum insert.

**Observasi:** Stok20→15 saat gagal insert movement; retry20→10 untuk output5, sementara movement/reported consumption hanya5. Tidak ada crash sesudah commit yang diasumsikan: fault terjadi sebelum insert.

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

> Periksa `V3-PROD-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Buat operasi konsumsi per material/roll dengan identity stabil dan state durable sebelum efek, lalu lakukan perubahan fisik dan ledger dalam transaksi atau step idempoten yang dapat direkonsiliasi. Jangan menyelesaikan recovery hanya dari movement yang mungkin belum lahir. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum/sesudah tiap write, retry key sama/berbeda dan dua worker: stok20→15, output5, movement5 tepat sekali. Recovery harus bekerja melalui endpoint sah; penghapusan lock di probe hanya kontrol pemulihan lokal.

**Hubungan dengan catatan lain:** GN-06, GN-11, W2-024

## V3-PROD-02 — Reversal dianggap selesai sebelum panjang roll dipulihkan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/production_service.py:389](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/production_service.py#L389).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Movement ditandai reversed sebelum update stok. Kalau update stok gagal, retry mengecualikan movement tersebut dan tidak melakukan restore.

**Dampak dan batas interpretasi:** Roll tersisa5 dari awal10; restore gagal sebelum update. Retry restored0, roll tetap5 dan movement reversed=true.

**Observasi:** Roll tersisa5 dari awal10; restore gagal sebelum update. Retry restored0, roll tetap5 dan movement reversed=true.

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

> Periksa `V3-PROD-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Claim reversal dengan token/stage dan stable operation ID. Commit restore stock dengan marker yang sama secara atomik, atau simpan progress yang membedakan claimed dari applied; retry memeriksa kontribusi aktual. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Restore operasi5 selalu menghasilkan roll10, satu reversal movement dan projection10, termasuk fault restore dan dua worker; jangan double-increment saat response hilang.

**Hubungan dengan catatan lain:** GN-06, GN-11

## V3-AR-01 — Receipt gagal dibuat tetapi SO terbayar dan deposit kembali utuh

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/ar_receipt_service.py:448](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/ar_receipt_service.py#L448).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Receipt mengurangi deposit, mengalokasikan payments ke SO, baru insert receipt. Except mengembalikan deposit tetapi tidak membatalkan alokasi SO. Tidak ada receipt durable untuk resume.

**Dampak dan batas interpretasi:** Saldo deposit100; fault sebelum insert ar_receipts: SO paid_total100/payments1, customer deposit100, receipt count0. Saldo yang sama bisa dipakai lagi.

**Observasi:** Saldo deposit100; fault sebelum insert ar_receipts: SO paid_total100/payments1, customer deposit100, receipt count0. Saldo yang sama bisa dipakai lagi.

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

> Periksa `V3-AR-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist receipt operation sebelum allocations. Setiap alokasi harus terkait stable receipt ID dan dapat resume/compensate tanpa menghapus payment milik operasi lain. Tangani insert/GL/cash/deposit sebagai satu protokol durable. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum receipt insert, setelah SO allocation, sebelum/sesudah GL dan saat rollback. Akhir harus semua effect100 tepat sekali atau semua batal; tidak ada SO paid tanpa receipt/deposit konsumsi. Uji multi-SO dan pembayaran bersamaan.

**Hubungan dengan catatan lain:** FN-10, W2-017

## V3-BANK-01 — Satu baris bank dapat direkonsiliasi ke dua transaksi kas penuh

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/bank_recon_service.py:614](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/bank_recon_service.py#L614).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** CAS membatasi capacity cash transaction, tetapi statement line ditulis berdasarkan ID tanpa claim status/version/capacity yang sama. Dua transaksi berbeda dapat sama-sama mengklaim line bank.

**Dampak dan batas interpretasi:** Statement100; dua manual_match berbeda100+100: line allocated100, cash reconciled200, kedua cash mencantumkan matched_line_ids BL.

**Observasi:** Statement100; dua manual_match berbeda100+100: line allocated100, cash reconciled200, kedua cash mencantumkan matched_line_ids BL.

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

> Periksa `V3-BANK-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Claim kedua sisi allocation dengan stable match operation dan transaksi/compensation idempoten. Revalidate statement remaining setelah claim; jangan hanya melindungi tiap cash record. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Dua matching paralel atas line100: satu sukses dan satu conflict atau total allocated100. Jumlah dari statement links harus sama dengan cash links. Uji split, duplicate payload, unlink/rerun/fault antar-write.

**Hubungan dengan catatan lain:** CX-07, CX-06

## V3-MKO-01 — Retry penerimaan maklon menambah output fisik dan nilai stok

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/makloon_order_service.py:1093](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/makloon_order_service.py#L1093).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Progress lots disimpan sesudah seluruh loop output. Output pertama yang sudah dibuat tidak tersimpan dalam progress jika pembuatan kedua gagal. Retry membuat seluruh roll lagi.

**Dampak dan batas interpretasi:** Input10, dua output5; fault sebelum create output kedua:1roll. Retry:3roll=15; inventory value180 sedangkan jurnal receipt120 untuk output10.

**Observasi:** Input10, dua output5; fault sebelum create output kedua:1roll. Retry:3roll=15; inventory value180 sedangkan jurnal receipt120 untuk output10.

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

> Periksa `V3-MKO-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Beri deterministic roll identity per operation+receipt line/index sebelum loop. Persist plan dan state tiap output sebelum/bersama creation; resume harus reconcile actual roll dan movement sebelum membuat lagi. Simpan original warehouse/lot/cost snapshot. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault pada output1/2/N serta setelah jurnal/status: output total10 dan dua roll saja, inventory value sama GL120. Uji partial multi-gudang, duplicate lot input, response-lost dan authorized saga recovery.

**Hubungan dengan catatan lain:** CX-13, W2-001, GN-11

## V3-MASTER-01 — Apply master mengubah produk sebelum snapshot batch durable

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/master_governance_service.py:96](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/master_governance_service.py#L96).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Apply mengubah produk dan last_governance_batch lalu insert dokumen batch before/after. Jika insert gagal, perubahan tidak mempunyai snapshot rollback.

**Dampak dan batas interpretasi:** Stage produk greige→grey dan last_governance_batch terisi; fault sebelum insert batch: durable_batch_count0. Rollback batch yang dijanjikan tidak tersedia.

**Observasi:** Stage produk greige→grey dan last_governance_batch terisi; fault sebelum insert batch: durable_batch_count0. Rollback batch yang dijanjikan tidak tersedia.

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

> Periksa `V3-MASTER-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist batch plan/hash/before snapshots dan stage prepared sebelum produk diubah; pakai CAS version tiap produk dan idempoten operation. Progress parsial harus bisa resume/rollback tanpa menimpa edit sesudahnya. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum/antara product update dan batch insert menghasilkan batch recoverable atau tidak ada perubahan. Uji multi-produk, edits concurrent, dry-run signature stale, rollback conflict dan retry identitas sama.

**Hubungan dengan catatan lain:** W2-REQ-02

## V3-CUT-01 — Gagal membuat child cut menghilangkan stok dan reservasi

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/roll_service.py:614](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/roll_service.py#L614).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Parent decrement dan pull reservation dilakukan sebelum child insert. Bila insert gagal sebelum write, tidak ada durable cut command yang dapat melanjutkan dan reservation telah hilang.

**Dampak dan batas interpretasi:** Awal10/reserve3; fault child insert: parent7, reserved0, child0. Retry confirm_cut404 reservasi tidak ditemukan/sudah dipotong. Stok fisik total data berkurang3 tanpa child.

**Observasi:** Awal10/reserve3; fault child insert: parent7, reserved0, child0. Retry confirm_cut404 reservasi tidak ditemukan/sudah dipotong. Stok fisik total data berkurang3 tanpa child.

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

> Periksa `V3-CUT-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist cut operation dan output identity stabil sebelum mutation; parent/reservation/child/movement/weight/tag lifecycle satu transaksi atau recoverable state machine. Retry mencari cut operation lama, bukan hanya reservation yang sudah dipull. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault setiap tahap cut100→70+30 selalu conservation quantity/value/weight+documented waste; retry menghasilkan satu child dan satu movement, tag identity baru harus diverifikasi sebelum loading. Tidak boleh menambah kembali parent bila child sudah ada.

**Hubungan dengan catatan lain:** WM-01, WM-02, W2-REQ-09, GN-11

