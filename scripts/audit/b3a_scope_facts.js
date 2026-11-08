// B3a — fakta cakupan pengguna & prasyarat uji API. BACA-SAJA.
print("== setelan lokasi kerja & simulasi");
db.config_values.find({ key: { $in: ["wms.location_scope_enforced", "wms.rfid_simulation"] } }, { _id: 0 }).forEach(c => { print(JSON.stringify(c)); });
print("== akun uji");
db.users.find({ email: { $in: ["admin@kainnusantara.id", "manager@kainnusantara.id", "sales@kainnusantara.id", "sales.kanda@kainnusantara.id", "warehouse.soreang@kainnusantara.id", "warehouse.rancamalang@kainnusantara.id", "wh.admin@kainnusantara.id"] } },
  { _id: 0, email: 1, role: 1, home_entity_id: 1, allowed_entity_ids: 1, location_site_ids: 1, location_warehouse_ids: 1, line_codes: 1, lines: 1 }).forEach(u => { print(JSON.stringify(u)); });
print("== SO yang AKAN dikedaluwarsakan oleh GET /products|/dashboard|/sales-orders (expire_old_reservations)");
const now = new Date().toISOString();
print(db.sales_orders.countDocuments({ status: { $in: ["reserved", "waiting_approval", "approved", "waiting_stock"] }, reservation_expires_at: { $lte: now } }));
print("== produk dengan roll terbanyak (batas to_list(5000) stock-breakdown)");
db.inventory_rolls.aggregate([{ $group: { _id: "$product_id", n: { $sum: 1 } } }, { $sort: { n: -1 } }, { $limit: 8 }]).forEach(x => { print(JSON.stringify(x)); });
print("== produk dengan > 100 saldo (batas to_list(100))");
db.inventory_balances.aggregate([{ $group: { _id: "$product_id", n: { $sum: 1 } } }, { $match: { n: { $gt: 100 } } }]).forEach(x => { print(JSON.stringify(x)); });
print("== grade non-A tanpa riwayat, di luar impor/seed");
print(db.inventory_rolls.countDocuments({ grade: { $ne: "A" }, "grade_history.0": { $exists: false }, created_by: { $nin: ["seed", "Import Stok Awal", "Demo Lengkap"] } }));
db.inventory_rolls.find({ grade: { $ne: "A" }, "grade_history.0": { $exists: false }, created_by: { $nin: ["seed", "Import Stok Awal", "Demo Lengkap"] } }, { _id: 0, id: 1, grade: 1, status: 1, created_by: 1, origin_type: 1, regraded_from: 1, parent_roll_id: 1 }).limit(8).forEach(x => { print(JSON.stringify(x)); });
print("== md_grades");
db.md_grades.find({}, { _id: 0, code: 1, active: 1, rank: 1 }).forEach(x => { print(JSON.stringify(x)); });
print("== roll blocked dengan length_reserved");
db.inventory_rolls.find({ status: { $ne: "available" }, length_reserved: { $gt: 0 } }, { _id: 0, id: 1, roll_no: 1, status: 1, length_remaining: 1, length_reserved: 1, length_reservations: 1, hold: 1, product_id: 1, warehouse_id: 1 }).forEach(x => { print(JSON.stringify(x)); });
print("== roll ber-length_reserved aktif per gudang (pemicu STK-13)");
db.inventory_rolls.aggregate([{ $match: { status: "available", length_reserved: { $gt: 0 } } }, { $group: { _id: { w: "$warehouse_id", p: "$product_id", o: "$owner_entity_id" }, n: { $sum: 1 }, lr: { $sum: "$length_reserved" }, len: { $sum: "$length_remaining" } } }, { $sort: { lr: -1 } }, { $limit: 15 }]).forEach(x => { print(JSON.stringify(x)); });
print("== rfid_tag_id yang bukan id tag");
db.inventory_rolls.find({ rfid_tag_id: { $nin: [null, ""], $not: /^rtag_/ } }, { _id: 0, id: 1, roll_no: 1, rfid_tag_id: 1, tracking_mode: 1, created_by: 1 }).forEach(x => { print(JSON.stringify(x)); });
print("== dye_lot ≠ lot (sumber)");
db.inventory_rolls.aggregate([{ $match: { $expr: { $ne: ["$dye_lot", "$lot"] } } }, { $group: { _id: { via: "$acquired.via", o: "$owner_entity_id" }, n: { $sum: 1 } } }]).forEach(x => { print(JSON.stringify(x)); });
print("== roll contoh lintas PT (untuk uji SCP-1): satu roll KSC & satu roll Cipta Sandang & satu roll Kanda");
["ent_ksc", "ent_82b52ed6ee8b", "ent_kanda"].forEach(e => { const r = db.inventory_rolls.findOne({ owner_entity_id: e, status: "available" }, { _id: 0, id: 1, roll_no: 1, warehouse_id: 1, owner_entity_id: 1, unit_cost: 1 }); print(JSON.stringify(r)); });
