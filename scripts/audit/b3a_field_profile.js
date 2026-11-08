// Profil field (BACA-SAJA). Keluaran JSON: {coll: {n, fields: {path: {n, types, samples}}}}
const COLLS = [
  "inventory_rolls", "inventory_balances", "inventory_movements", "inventory_lots",
  "wms_tasks", "warehouse_transfers", "putaway_orders", "goods_receipts", "shipments",
  "logistics_deliveries", "cycle_count_sessions", "rfid_tags", "rfid_reads", "rfid_devices",
  "rfid_passages", "rfid_observations", "rfid_print_jobs", "rfid_verify_sessions",
  "inspections", "mdq_cuts", "material_reservations", "warehouses", "warehouse_sites",
  "sales_returns", "purchase_returns", "makloon_orders", "roll_label_prints", "roll_cost_history",
  "turn_marks", "fact_stock_daily", "interco_returns", "interco_transactions", "purchase_orders",
  "sales_orders", "special_orders", "business_entities", "products", "data_hygiene_log", "users",
  "internal_requests"
];
const MAXDOCS = 50000;
const MAXDEPTH = 4;
function typ(v) {
  if (v === null) return "null";
  if (Array.isArray(v)) return "array";
  if (v instanceof Date) return "date";
  if (typeof v === "object" && v._bsontype) return v._bsontype;
  return typeof v;
}
function walk(doc, prefix, depth, acc, seen) {
  for (const k of Object.keys(doc)) {
    if (k === "_id") continue;
    const v = doc[k];
    const p = prefix ? prefix + "." + k : k;
    const t = typ(v);
    let e = acc[p];
    if (!e) { e = acc[p] = { n: 0, filled: 0, types: {}, samples: [] }; }
    if (!seen.has(p)) { e.n++; seen.add(p); }
    e.types[t] = (e.types[t] || 0) + 1;
    const empty = v === null || v === "" || (Array.isArray(v) && v.length === 0) || (t === "object" && Object.keys(v).length === 0);
    if (!empty && !seen.has(p + "#f")) { e.filled++; seen.add(p + "#f"); }
    if (["string", "number", "boolean"].includes(t) && e.samples.length < 4) {
      const s = String(v).slice(0, 40);
      if (!e.samples.includes(s)) e.samples.push(s);
    }
    if (depth < MAXDEPTH) {
      if (t === "object") walk(v, p, depth + 1, acc, seen);
      else if (t === "array") {
        for (const it of v.slice(0, 20)) {
          if (it && typeof it === "object" && !Array.isArray(it)) walk(it, p + "[]", depth + 1, acc, seen);
        }
      }
    }
  }
}
const out = {};
for (const c of COLLS) {
  const acc = {};
  let n = 0;
  const cur = db.getCollection(c).find({}).limit(MAXDOCS);
  while (cur.hasNext()) {
    const d = cur.next();
    n++;
    walk(d, "", 0, acc, new Set());
  }
  out[c] = { n, fields: acc };
}
print(JSON.stringify(out));
