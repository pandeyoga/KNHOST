// Hanya-baca. Pesanan wajib bayar dulu yang belum ke gudang & belum lunas bagian wajib → tertahan di "Bayar dicek Finance"
// pada konfirmasi/ACC berikutnya sesudah pembaruan.
const t = {}; db.payment_terms.find({}, {_id: 0, code: 1, dp_percent: 1, type: 1}).forEach((x) => { if ((x.dp_percent || 0) > 0) t[x.code] = x.dp_percent; });
const rows = db.sales_orders.aggregate([
  {$match: {status: {$in: ["reserved", "waiting_approval", "waiting_stock", "approved"]}, is_sample: {$ne: true},
            dispatch_payment_release: {$in: [null]}, source_special_order_id: {$in: [null, ""]},
            $or: [{pay_before_ship: true}, {payment_term_code: {$in: Object.keys(t)}}]}},
  {$project: {status: 1, payment_term_code: 1, k27: {$ifNull: ["$pay_before_ship", false]}, grand_total: 1, paid_total: {$ifNull: ["$paid_total", 0]}}},
  {$group: {_id: {status: "$status", termin: "$payment_term_code", k27: "$k27"}, pesanan: {$sum: 1},
            nilai: {$sum: "$grand_total"}, sudah_dibayar: {$sum: "$paid_total"}}},
  {$sort: {"_id.status": 1, "_id.termin": 1}}]).toArray();
print("Termin wajib bayar dulu: " + JSON.stringify(t));
rows.forEach((r) => print(JSON.stringify(r)));
print("Total pesanan: " + rows.reduce((a, r) => a + r.pesanan, 0));
