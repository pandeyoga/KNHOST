// Pemeriksaan sebelum rilis komisi per artikel — tarif insentif (hanya membaca).
// 1) Calon kembar indeks unik uq_incentive_rate_key: (entity_id, rate_key) — untuk baris lama tanpa rate_key, kunci yang
//    akan diisi bootstrap.backfill_incentive_rate_key = "kategori:" + kategori tanpa spasi tepi.
const kembar = db.incentive_rates.aggregate([
  {$project: {id: 1, entity_id: 1, k: {$cond: [{$gt: [{$strLenCP: {$ifNull: ["$rate_key", ""]}}, 0]}, "$rate_key",
    {$concat: ["kategori:", {$trim: {input: {$ifNull: ["$category", ""]}}}]}]}}},
  {$group: {_id: {e: "$entity_id", k: "$k"}, n: {$sum: 1}, id: {$push: "$id"}}},
  {$match: {n: {$gt: 1}}}]).toArray();
print("KEMBAR uq_incentive_rate_key: " + kembar.length); kembar.forEach((x) => printjson(x));
// 2) Isian angka bukan angka (mematahkan potret pesanan & isi awal) atau di luar batas registri.
const ANGKA = ["double", "int", "long", "decimal"];
const bukanAngka = (f) => ({[f]: {$exists: true, $ne: null, $not: {$type: ANGKA}}});
const rusak = db.incentive_rates.find({$or: [
  {per_unit_amount: {$not: {$type: ANGKA}}}, bukanAngka("margin_cap_pct"), bukanAngka("discount_threshold"),
  bukanAngka("discount_factor"), bukanAngka("discount_potong_rp"),
  {per_unit_amount: {$lt: 0}}, {margin_cap_pct: {$lt: 0}}, {margin_cap_pct: {$gt: 100}}, {discount_factor: {$gt: 1}},
  {discount_factor: {$lt: 0}}, {discount_threshold: {$lt: 0}}, {discount_potong_rp: {$lt: 0}},
  {status: {$nin: ["active", "inactive"]}},
  {discount_mechanic: {$exists: true, $nin: [null, "tier_factor", "potong_rp", "cutoff"]}},
  {discount_threshold_type: {$exists: true, $nin: [null, "pct", "rp_per_unit"]}}]},
  {_id: 0, id: 1, entity_id: 1, category: 1, per_unit_amount: 1, margin_cap_pct: 1, discount_threshold: 1,
   discount_factor: 1, discount_potong_rp: 1, discount_mechanic: 1, discount_threshold_type: 1, status: 1}).toArray();
print("TARIF RUSAK / DI LUAR BATAS: " + rusak.length); rusak.forEach((x) => printjson(x));
// 3) Baris pesanan yang akan dipotret isi awal & baris berkategori kosong (I1: tetap tanpa tarif kategori).
print("pesanan tanpa potret: " + db.sales_orders.countDocuments({items: {$elemMatch: {commission_rule: {$exists: false}}}}));
print("baris berkategori kosong: " + db.sales_orders.aggregate([{$unwind: "$items"},
  {$match: {"items.category": {$in: ["", null]}}}, {$count: "n"}]).toArray().map((x) => x.n).concat([0])[0]);
