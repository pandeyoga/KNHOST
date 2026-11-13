# Kueri cek data — temuan lanjutan audit keuangan (FY, FX)

Lampiran untuk [`AUDIT_KEUANGAN_2026-11-13.md`](AUDIT_KEUANGAN_2026-11-13.md) §3.10–3.11 dan §12.

**Semua kueri baca-saja dan belum pernah dijalankan** — ditulis dari pembacaan kode di `ec79643`. Jalankan di `mongosh`
pada **salinan** database, bukan produksi; bila ada galat sintaks atau nama field, itu berarti kuerinya perlu
disesuaikan, bukan bukti datanya bersih. Kode akun mengikuti konstanta di `backend/services/gl_service.py`; bila akun
dipetakan per PT (temuan IV-05), sesuaikan dulu.

## A. Aset tetap, anggaran, gaji, kas kecil, pajak (FY)

```js
// FY-01 aset tanpa jurnal perolehan
db.fin_fixed_assets.aggregate([{$lookup:{from:"journal_entries",let:{i:"$id"},pipeline:[{$match:{$expr:{$eq:["$source_id","$$i"]},source_type:"fixed_asset_acquisition",status:{$ne:"void"}}}],as:"je"}},{$match:{je:{$size:0}}},{$project:{number:1,entity_id:1,acquisition_cost:1,status:1}}])

// FY-02 penyusutan: periode ≠ bulan jurnal; gaji: periode ≠ bulan posting
db.fin_depreciation_entries.aggregate([{$lookup:{from:"journal_entries",localField:"je_id",foreignField:"id",as:"je"}},{$unwind:"$je"},{$match:{$expr:{$ne:["$period",{$substrCP:["$je.date",0,7]}]}}},{$group:{_id:{p:"$period",m:{$substrCP:["$je.date",0,7]}},n:{$sum:1},total:{$sum:"$amount"}}}])
db.hr_payroll_runs.find({posted_at:{$gt:""},$expr:{$ne:["$period",{$substrCP:["$posted_at",0,7]}]}},{number:1,period:1,posted_at:1})

// FY-03 kas di buku besar yang digerakkan aset tanpa buku kas
db.journal_entries.aggregate([{$match:{status:{$ne:"void"},source_type:{$in:["fixed_asset_acquisition","fixed_asset_disposal"]}}},{$unwind:"$lines"},{$match:{"lines.account_code":/^1-11/}},{$group:{_id:{e:"$entity_id",t:"$source_type"},dr:{$sum:"$lines.debit"},cr:{$sum:"$lines.credit"}}}])

// FY-04 aset hasil pindah antar-PT tanpa aset asal
db.fin_fixed_assets.aggregate([{$match:{funding_account:"2-1250"}},{$lookup:{from:"fin_fixed_assets",localField:"id",foreignField:"transfer.new_asset_id",as:"src"}},{$match:{src:{$size:0}}},{$project:{number:1,entity_id:1,acquisition_cost:1}}])

// FY-05 aset sudah pindah tetapi hidup lagi atau dilepas
db.fin_fixed_assets.find({"transfer.to_entity_id":{$gt:""},$or:[{status:{$ne:"transferred"}},{disposal:{$ne:null}}]},{number:1,status:1})

// FY-06, FY-09 penggajian macet, pernah ditolak, pengaju = penyetuju; akun bayar bukan kas
db.hr_payroll_runs.find({$or:[{status:{$in:["posting","paying"]}},{decision_history:{$exists:true}},{$expr:{$and:[{$gt:["$approved_by",""]},{$eq:["$approved_by","$submitted_by"]}]}}]},{number:1,status:1,period:1})
db.journal_entries.find({source_type:"payroll_pay",status:{$ne:"void"},lines:{$elemMatch:{credit:{$gt:0},account_code:{$not:/^1-11/}}}},{number:1})

// FY-07, FY-08 mutasi hutang insentif/gaji/BPJS/PPh 21 per PT; kas manual berkategori gaji/pajak
db.journal_entries.aggregate([{$match:{status:{$ne:"void"}}},{$unwind:"$lines"},{$match:{"lines.account_code":{$in:["2-1500","2-1600","2-1700","2-1800"]}}},{$group:{_id:{e:"$entity_id",a:"$lines.account_code"},dr:{$sum:"$lines.debit"},cr:{$sum:"$lines.credit"}}}])
db.cash_transactions.find({status:{$ne:"void"},direction:"out",category:/gaji|payroll|bpjs|pph/i,ref_type:{$nin:["payroll_run"]}},{number:1,category:1,amount:1})

// FY-10 LPJ ber-periode teks bebas
db.cash_advance_settlements.find({periode:{$nin:["",null],$not:/^\d{4}-\d{2}/}},{number:1,periode:1,status:1,total_pengeluaran:1})

// FY-11, FY-12 pagu anggaran kembar; kebijakan per PT
db.budgets.aggregate([{$group:{_id:{e:"$entity_id",y:"$year",m:"$month",d:"$dimension",k:"$key"},n:{$sum:1}}},{$match:{n:{$gt:1}}}])
db.fin_budget_rules.find({},{entity_id:1,mode:1})

// FY-13 kategori biaya dengan lebih dari satu akun
db.expense_categories.aggregate([{$group:{_id:"$code",acc:{$addToSet:"$account_code"},ent:{$addToSet:"$entity_id"}}},{$match:{"acc.1":{$exists:true}}}])

// FY-14 LPJ terposting tetapi uang muka belum selesai atau tautan jurnal kosong
db.cash_advance_settlements.aggregate([{$match:{status:"posted_to_gl"}},{$lookup:{from:"cash_advances",localField:"cash_advance_id",foreignField:"id",as:"ca"}},{$unwind:"$ca"},{$match:{$or:[{"ca.status":{$ne:"settled"}},{journal_entry_id:""}]}},{$project:{number:1,"ca.number":1,"ca.status":1}}])

// FY-16 dasar pajak slip vs bruto
db.hr_payslips.aggregate([{$group:{_id:{e:"$entity_id",p:"$period"},gross:{$sum:"$gross"},tax_gross:{$sum:"$tax_gross"},pph21:{$sum:"$pph21"}}}])

// FY-20 register aset vs entri susut; habis susut dengan sisa
db.fin_depreciation_entries.aggregate([{$group:{_id:"$asset_id",s:{$sum:"$amount"}}},{$lookup:{from:"fin_fixed_assets",localField:"_id",foreignField:"id",as:"a"}},{$unwind:"$a"},{$match:{$expr:{$gt:[{$abs:{$subtract:["$s","$a.accumulated_depreciation"]}},0.01]}}},{$project:{s:1,"a.number":1,"a.accumulated_depreciation":1}}])
db.fin_fixed_assets.find({status:"fully_depreciated",$expr:{$gt:[{$subtract:[{$subtract:["$acquisition_cost","$salvage_value"]},"$accumulated_depreciation"]},0.01]}},{number:1})

// biaya kampanye yang tertinggal di tengah proses
db.mkt_campaign_costs.find({status:"posting"},{number:1,amount:1})
```

FY-15 (pusat pajak tanpa penjaga entitas) adalah akses baca dan tidak terlihat di data; periksa log HTTP untuk
`entity_id=all` pada `/api/tax/*`.

## B. Denda, rencana bayar, selisih bayar, kasus keuangan, nota kredit (FX)

```js
// FX-01 setoran karyawan lebih besar dari uang yang dipegang
db.cash_transactions.aggregate([{$match:{ref_type:"finance_case",category:"setoran karyawan",status:{$ne:"void"}}},
 {$group:{_id:"$ref_id",n:{$sum:1},total:{$sum:"$amount"}}},
 {$lookup:{from:"finance_cases",localField:"_id",foreignField:"id",as:"c"}},
 {$project:{n:1,total:1,held:{$first:"$c.resolution.extra.held_amount"},no:{$first:"$c.number"}}},
 {$match:{$expr:{$gt:["$total",{$add:[{$ifNull:["$held",0]},0.01]}]}}}])

// FX-02 nota denda vs akun 1-1270, per nota
db.penalties.aggregate([{$match:{status:{$ne:"draft"}}},
 {$lookup:{from:"journal_entries",let:{i:"$id"},pipeline:[{$match:{status:{$ne:"void"},source_type:{$in:["penalty","penalty_reversal","penalty_payment"]},
   $expr:{$eq:[{$arrayElemAt:[{$split:["$source_id",":"]},0]},"$$i"]}}},{$unwind:"$lines"},{$match:{"lines.account_code":"1-1270"}},
   {$group:{_id:null,s:{$sum:{$subtract:["$lines.debit","$lines.credit"]}}}}],as:"g"}},
 {$project:{number:1,status:1,gl:{$ifNull:[{$first:"$g.s"},0]},
   doc:{$cond:[{$in:["$status",["issued","adjusted"]]},{$subtract:["$amount",{$ifNull:["$paid_amount",0]}]},0]}}},
 {$match:{$expr:{$gt:[{$abs:{$subtract:["$doc","$gl"]}},0.01]}}}])

// FX-03, FX-19 lebih dari satu nota denda untuk baris jatuh tempo yang sama
db.penalties.aggregate([{$match:{status:{$ne:"waived"}}},{$group:{_id:{d:"$doc_id",s:"$line_seq",due:"$due_date"},n:{$sum:1},
 total:{$sum:"$amount"},hari:{$push:"$days_late"},periode:{$push:"$period_key"}}},{$match:{n:{$gt:1}}}])

// FX-05, FX-06, FX-09 pembayaran non-kas yatim atau lintas pelanggan/PT
db.sales_orders.aggregate([{$unwind:"$payments"},
 {$match:{"payments.method":{$in:["deposit","writeoff","titipan_karyawan","bank_charge","antar_entitas","realokasi"]}}},
 {$addFields:{k:{$ifNull:["$payments.variance_decision_id","$payments.receipt_id"]}}},
 {$lookup:{from:"payment_variance_decisions",localField:"k",foreignField:"id",as:"d"}},
 {$lookup:{from:"finance_cases",localField:"k",foreignField:"id",as:"c"}},
 {$project:{number:1,customer_id:1,entity_id:1,p:"$payments",src:{$ifNull:[{$first:"$d"},{$first:"$c"}]}}},
 {$match:{$expr:{$or:[{$eq:["$src",null]},{$ne:["$src.customer_id","$customer_id"]},{$ne:["$src.entity_id","$entity_id"]}]}}}])

// FX-05, FX-06 jurnal selisih tanpa dokumen keputusan; keputusan ganda per kwitansi
db.journal_entries.aggregate([{$match:{status:{$ne:"void"},source_type:{$in:["payment_variance_writeoff","payment_variance_alloc"]}}},
 {$lookup:{from:"payment_variance_decisions",localField:"source_id",foreignField:"id",as:"d"}},{$match:{d:{$size:0}}},{$project:{number:1,source_id:1,total_debit:1}}])
db.payment_variance_decisions.aggregate([{$match:{side:"ar",status:{$ne:"reversed"}}},{$group:{_id:"$receipt_id",n:{$sum:1},no:{$push:"$number"}}},{$match:{n:{$gt:1}}}])

// FX-07 keputusan selisih hutang yang dibatalkan; faktur lunas dengan sisa
db.payment_variance_decisions.find({side:"ap",status:"reversed",je_id:{$gt:""}},{number:1,bill_number:1,amount:1,reversal_je_id:1})
db.vendor_bills.find({status:"paid",$expr:{$gt:[{$subtract:["$grand_total",{$ifNull:["$amount_paid",0]}]},0.01]}},{bill_number:1,grand_total:1,amount_paid:1,ap_variance_closed:1})

// FX-01, FX-08, FX-09 kas dan jurnal kasus yang tidak tercatat di dokumen kasus; jurnal di buku ≠ PT kasus
db.cash_transactions.aggregate([{$match:{id:/^cash_case_/,status:{$ne:"void"}}},
 {$lookup:{from:"finance_cases",let:{j:"$id"},pipeline:[{$match:{$expr:{$in:["$$j",{$ifNull:["$documents.id",[]]}]}}}],as:"c"}},
 {$match:{c:{$size:0}}},{$project:{number:1,amount:1,category:1,ref_id:1}}])
db.journal_entries.aggregate([{$match:{source_type:"finance_case",status:{$ne:"void"}}},
 {$addFields:{cid:{$arrayElemAt:[{$split:["$source_id",":"]},0]}}},
 {$lookup:{from:"finance_cases",localField:"cid",foreignField:"id",as:"c"}},
 {$project:{number:1,entity_id:1,source_id:1,total_debit:1,case_entity:{$first:"$c.entity_id"},
   tercatat:{$in:["$id",{$ifNull:[{$first:"$c.documents.id"},[]]}]}}},
 {$match:{$expr:{$or:[{$ne:["$entity_id","$case_entity"]},{$eq:["$tercatat",false]}]}}}])
db.finance_cases.find({entity_id:{$in:["all","",null]}},{number:1,case_type:1,status:1})

// FX-10 biaya bank di atas ambang; pembuat = penyelesai
db.finance_cases.find({status:"resolved",case_type:"selisih_biaya_bank","resolution.amount":{$gt:50000}},{number:1,"resolution.amount":1,resolved_by:1})
db.finance_cases.find({status:"resolved",auto_source:"",$expr:{$eq:["$created_by","$resolved_by"]}},{number:1,case_type:1,"resolution.amount":1})

// FX-11 saldo antar-PT yang lahir dari kasus (dan sisi yang tidak berpasangan)
db.journal_entries.aggregate([{$match:{source_type:"finance_case",source_id:/:ic_a[pr]$/,status:{$ne:"void"}}},
 {$group:{_id:{$arrayElemAt:[{$split:["$source_id",":"]},0]},sisi:{$addToSet:"$entity_id"},total:{$sum:"$total_debit"}}}])

// FX-12 Σ nota kredit per pesanan dari lebih dari satu sumber — bandingkan dengan grand_total
db.credit_notes.aggregate([{$match:{status:{$nin:["void","offset","pending_finance"]},kind:{$ne:"debit_note"}}},
 {$group:{_id:"$order_id",total:{$sum:"$gross_amount"},src:{$addToSet:{$ifNull:["$source","retur"]}},no:{$push:"$number"}}},
 {$match:{"src.1":{$exists:true}}},{$lookup:{from:"sales_orders",localField:"_id",foreignField:"id",as:"o"}},
 {$project:{total:1,src:1,no:1,grand_total:{$first:"$o.grand_total"}}}])

// FX-13, FX-15 dokumen macet atau tidak tertagih
db.doc_amendments.find({status:"approved"},{number:1,doc_number:1,method:1,decided_at:1})
db.credit_notes.find({source:"amendment",kind:"credit_note",status:"issued"},{number:1,order_number:1,gross_amount:1})
db.credit_notes.find({source:"od_item_cancel",status:"issued",revenue_recognized:true,journal_entry_id:{$in:[null,""]}},{number:1})
db.credit_notes.find({kind:"debit_note",billing_status:"awaiting_billing_rule"},{number:1,order_number:1,open_amount:1,created_at:1})
db.credit_notes.find({source:"od_item_cancel",$or:[{status:"void"},{$expr:{$lt:["$gross_amount","$computed_gross"]}}]},{number:1,gross_amount:1,computed_gross:1,excess_payment:1})

// FX-16 termin diganti lewat override (sesuaikan dengan bentuk field `changes`)
db.doc_amendments.find({"changes.field":"payment_term_code"},{number:1,doc_number:1,changes:1,proposed_by:1})

// FX-17, FX-18, FX-19 dokumen kembar
db.payment_plans.aggregate([{$match:{status:{$ne:"void"}}},{$group:{_id:"$doc_id",n:{$sum:1}}},{$match:{n:{$gt:1}}}])
db.finance_cases.aggregate([{$match:{"source.id":{$gt:""}}},{$group:{_id:{t:"$case_type",s:"$source.id"},n:{$sum:1},st:{$push:"$status"}}},{$match:{n:{$gt:1}}}])
```
