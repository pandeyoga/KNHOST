// B3a — indeks pada kunci aplikasi `id` & kunci rujukan bersarang. BACA-SAJA (getIndexes/aggregate).
let withId = [], withoutId = [];
db.getCollectionNames().sort().forEach(c => {
  const n = db.getCollection(c).estimatedDocumentCount();
  const has = db.getCollection(c).getIndexes().some(i => Object.keys(i.key)[0] === "id");
  if (n > 0) { (has ? withId : withoutId).push(c + "(" + n + ")"); }
});
print("koleksi ber-dokumen DENGAN indeks id: " + withId.length + " " + withId.join(", "));
print("koleksi ber-dokumen TANPA indeks id: " + withoutId.length);
print(withoutId.join(", "));
print("== id kembar di koleksi stok");
["inventory_rolls", "inventory_balances", "inventory_lots", "inventory_movements", "wms_tasks", "rfid_tags"].forEach(c => {
  const d = db.getCollection(c).aggregate([{ $group: { _id: "$id", n: { $sum: 1 } } }, { $match: { n: { $gt: 1 } } }, { $count: "dup" }], { allowDiskUse: true }).toArray();
  print(c + ": " + (d.length ? d[0].dup : 0));
});
print("== explain find_one({id}) pada inventory_rolls");
const ex = db.inventory_rolls.find({ id: "roll_668eb29b5a93" }).explain("executionStats");
print(JSON.stringify({ stage: ex.queryPlanner.winningPlan.stage, docsExamined: ex.executionStats.totalDocsExamined, ms: ex.executionStats.executionTimeMillis }));
const ex2 = db.inventory_rolls.find({ "reserved_ref.id": "so_x" }).explain("executionStats");
print(JSON.stringify({ q: "reserved_ref.id", stage: ex2.queryPlanner.winningPlan.stage, docsExamined: ex2.executionStats.totalDocsExamined, ms: ex2.executionStats.executionTimeMillis }));
