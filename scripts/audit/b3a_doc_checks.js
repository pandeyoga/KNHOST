// B3a (audit 2026-11-09) — konsistensi dokumen WMS vs roll (SSOT) & salinan. BACA-SAJA.
const out = {};
function put(k, arr) { out[k] = { n: arr.length, contoh: arr.slice(0, 8) }; }
const A = {};
function add(k, v) { (A[k] = A[k] || []).push(v); }
const prods = {}; db.products.find({}, {_id:0,id:1,base_unit:1,sku:1}).forEach(p => { prods[p.id] = p; });
// 1) Lot: proyeksi vs roll
const agg = {};
db.inventory_rolls.aggregate([{ $group: { _id: "$lot_id", n: { $sum: 1 },
  act: { $sum: { $cond: [{ $gt: ["$length_remaining", 0] }, 1, 0] } },
  rem: { $sum: "$length_remaining" },
  av: { $sum: { $cond: [{ $eq: ["$status", "available"] }, "$length_remaining", 0] } } } }]).forEach(g => { agg[g._id] = g; });
db.inventory_lots.find({}, {_id:0}).forEach(l => {
  const g = agg[l.id] || { n: 0, act: 0, rem: 0, av: 0 };
  if (Number(l.roll_count||0) !== g.n) add("lot_roll_count_ne_roll", l.lot_number+" lot="+l.roll_count+" roll="+g.n);
  if (Math.abs(Number(l.qty_remaining||0) - g.rem) > 0.05) add("lot_qty_remaining_ne_roll", l.lot_number+" lot="+l.qty_remaining+" roll="+g.rem.toFixed(2));
  if (l.entity_id !== l.owner_entity_id) add("lot_entity_id_ne_owner_entity_id", l.lot_number+" "+l.entity_id+"/"+l.owner_entity_id);
});
// 2) PO items: nama field qty dasar & satuan
const poF = {};
db.purchase_orders.find({}, {_id:0,id:1,po_number:1,status:1,items:1,warehouse_id:1,entity_id:1}).forEach(po => {
  (po.items||[]).forEach(it => {
    ["quantity","qty","quantity_base","base_quantity","base_qty","qty_base","received_qty","unit","uom","base_unit"].forEach(f => { if (it[f] !== undefined) poF[f] = (poF[f]||0)+1; });
    const P = prods[it.product_id] || {};
    const u = (it.unit || it.uom || "").toLowerCase(); const b = (P.base_unit||"").toLowerCase();
    const open = ["pending","created","approved","sent","receiving","partial"].includes(po.status);
    if (open && u && b && u !== b) add("po_terbuka_uom_ne_base", po.po_number+" "+it.product_id+" "+it.quantity+" "+u+" base="+b+" qbase="+it.quantity_base+" base_quantity="+it.base_quantity+" recv="+it.received_qty);
    if (open) add("po_terbuka_item", po.po_number+" "+po.status+" "+it.product_id+" q="+it.quantity+" recv="+(it.received_qty||0)+" u="+u+" qb="+it.quantity_base+" wh="+po.warehouse_id);
  });
});
out["po_item_fields"] = poF;
// 3) SO: allocations vs roll ter-reserve
const heldStatus = ["reserved","committed","picked","packed","in_transit_sales"];
const rollHeld = {};
db.inventory_rolls.aggregate([{ $match: { "reserved_ref.type": "sales_order", status: { $in: heldStatus } } },
  { $group: { _id: { o: "$reserved_ref.id", p: "$product_id" }, q: { $sum: "$length_remaining" }, n: { $sum: 1 } } }]).forEach(g => { rollHeld[g._id.o+"|"+g._id.p] = g; });
const lenHeld = {};
db.inventory_rolls.aggregate([{ $match: { "length_reservations.0": { $exists: true } } }, { $unwind: "$length_reservations" },
  { $match: { "length_reservations.ref.type": "sales_order" } },
  { $group: { _id: { o: "$length_reservations.ref.id", p: "$product_id" }, q: { $sum: "$length_reservations.qty" } } }]).forEach(g => { lenHeld[g._id.o+"|"+g._id.p] = g.q; });
const soClosed = ["cancelled","rejected","closed","completed","delivered","done","expired"];
const soStat = {};
db.sales_orders.find({}, {_id:0,id:1,number:1,status:1,allocations:1,entity_id:1}).forEach(so => {
  soStat[so.id] = so.status;
  const per = {};
  (so.allocations||[]).forEach(a => { const k = so.id+"|"+a.product_id; per[k] = (per[k]||0) + Number(a.allocated_qty || a.quantity || a.qty || 0); });
  Object.keys(per).forEach(k => {
    const r = (rollHeld[k]||{q:0}).q + (lenHeld[k]||0);
    if (!soClosed.includes(so.status) && Math.abs(per[k] - r) > 0.05) add("so_alokasi_ne_roll_tertahan:"+so.status, so.number+" "+k.split("|")[1]+" alokasi="+per[k].toFixed(2)+" roll="+r.toFixed(2));
  });
});
Object.keys(rollHeld).forEach(k => { const st = soStat[k.split("|")[0]]; if (st === undefined) add("roll_reserved_ke_so_yatim", k); else if (soClosed.includes(st) && ["reserved","committed","picked","packed"].includes("reserved")) { /* cek detail di bawah */ } });
db.inventory_rolls.find({ "reserved_ref.type": "sales_order", status: { $in: ["reserved","committed","picked","packed"] } }, {_id:0,id:1,status:1,reserved_ref:1}).forEach(r => {
  const st = soStat[r.reserved_ref.id];
  if (soClosed.includes(st)) add("roll_masih_ditahan_untuk_so_tertutup", r.id+" "+r.status+" so="+r.reserved_ref.id+" ("+st+")");
});
// 4) Transfer: status dokumen vs roll
const trf = {};
db.warehouse_transfers.find({}, {_id:0}).forEach(t => { trf[t.id] = t; });
db.inventory_rolls.find({ $or: [{ "reserved_ref.type": { $in: ["transfer","wh_transfer"] } }, { "transfer_ref.id": { $exists: true, $ne: null } }, { status: { $in: ["in_transit_transfer","in_transit_intercompany"] } }] }, {_id:0,id:1,status:1,reserved_ref:1,transfer_ref:1,warehouse_id:1}).forEach(r => {
  const tid = (r.transfer_ref && r.transfer_ref.id) || (r.reserved_ref && r.reserved_ref.id);
  const t = trf[tid];
  if (!t) { add("roll_transit_tanpa_dokumen_transfer", r.id+" "+r.status+" "+tid); return; }
  add("roll_vs_transfer:"+r.status+"|trf:"+t.status, r.id+" "+(t.code||t.number||t.id));
});
const tf = {};
Object.values(trf).forEach(t => { Object.keys(t).forEach(k => { tf[k] = (tf[k]||0)+1; }); });
out["transfer_fields"] = tf;
// 5) material_reservations aktif vs tersedia per produk×PT
const mr = {};
db.material_reservations.find({ status: "active" }, {_id:0}).forEach(m => { const k = m.product_id+"|"+m.owner_entity_id; mr[k] = (mr[k]||0) + Number(m.qty||0); });
const avb = {};
db.inventory_balances.aggregate([{ $group: { _id: { p: "$product_id", o: "$owner_entity_id" }, av: { $sum: "$available_qty" } } }]).forEach(g => { avb[g._id.p+"|"+g._id.o] = g.av; });
Object.keys(mr).forEach(k => { add("makloon_cadangan_aktif", k+" cadangan="+mr[k]+" tersedia_saldo="+((avb[k]||0).toFixed(2))); });
// 6) wms_tasks: entity vs owner, roll_id isi label
db.wms_tasks.find({}, {_id:0,id:1,entity_id:1,owner_entity_id:1,po_id:1,roll_id:1,flow_type:1,status:1,warehouse_id:1}).forEach(t => {
  if (t.owner_entity_id && t.owner_entity_id !== t.entity_id) add("task_owner_ne_entity", t.id+" "+t.entity_id+"/"+t.owner_entity_id);
  if (t.roll_id && !String(t.roll_id).startsWith("roll_")) add("task_roll_id_bukan_id_roll", t.id+" "+t.roll_id);
  if (t.po_id) { const po = db.purchase_orders.findOne({ id: t.po_id }, {_id:0,entity_id:1}); if (po && po.entity_id !== t.entity_id) add("task_entity_ne_po_entity", t.id+" task="+t.entity_id+" po="+po.entity_id); }
});
// 7) movements: roll_id FK, type vs movement_type, tanda qty
const mt = {};
db.inventory_movements.aggregate([{ $group: { _id: { mt: "$movement_type", t: "$type", d: "$direction", neg: { $lt: ["$quantity", 0] } }, n: { $sum: 1 } } }]).forEach(g => { mt[JSON.stringify(g._id)] = g.n; });
out["movement_type_matrix"] = mt;
// CATATAN: inventory_rolls TIDAK berindeks `id` — $lookup per roll_id = COLLSCAN berulang (pernah berjalan > 9 menit).
// Maka keanggotaan dicek di memori: set id roll vs roll_id distinct mutasi.
const rollIds = new Set(); db.inventory_rolls.find({}, { _id: 0, id: 1 }).forEach(r => { rollIds.add(r.id); });
let yIds = 0, yMov = 0; const yEx = [];
db.inventory_movements.aggregate([{ $group: { _id: "$roll_id", n: { $sum: 1 } } }], { allowDiskUse: true }).forEach(g => {
  if (!rollIds.has(g._id)) { yIds++; yMov += g.n; if (yEx.length < 8) yEx.push(String(g._id)); }
});
out["movement_roll_id_yatim"] = { roll_ids: yIds, movements: yMov, contoh: yEx };
// 8) goods_receipts & putaway_orders medan entity/gudang
["goods_receipts","putaway_orders","shipments","logistics_deliveries","cycle_count_sessions","mdq_cuts","repair_orders"].forEach(c => {
  const f = {}; db.getCollection(c).find({}).limit(2000).forEach(d => { ["entity_id","owner_entity_id","warehouse_id","from_warehouse_id","to_warehouse_id","source_warehouse_id","dest_warehouse_id","status","qty","quantity","qty_rolls","total_qty"].forEach(k => { if (d[k] !== undefined) f[k] = (f[k]||0)+1; }); });
  out["fields_"+c] = f;
});
// 9) shipments vs roll in_transit_sales/delivered
const shp = {}; db.shipments.find({}, {_id:0,id:1,status:1,order_id:1,number:1}).forEach(s => { shp[s.order_id] = (shp[s.order_id]||[]).concat([s.status]); });
db.inventory_rolls.find({ status: "in_transit_sales" }, {_id:0,id:1,reserved_ref:1}).forEach(r => {
  const so = (r.reserved_ref||{}).id; add("in_transit_sales_vs_so:"+(soStat[so]||"?")+"|shp:"+((shp[so]||["-"]).join("/")), r.id);
});
Object.keys(A).sort().forEach(k => put(k, A[k]));
print(JSON.stringify(out, null, 1));
