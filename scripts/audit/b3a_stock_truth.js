// B3a (audit 2026-11-09) — "kebenaran" angka stok langsung dari inventory_rolls untuk sampel produk & roll. BACA-SAJA.
// Keluaran JSON: {products: {pid: {...fitur, segs:[...], balances:[...], makloon:[...], po:[...], interco:[...]}}, rolls:[...]}
const reg = {}; db.warehouses.find({}, {_id:0,id:1,active:1,site_id:1,code:1}).forEach(w => { reg[w.id] = w; });
const feat = {};
db.inventory_rolls.aggregate([
  { $group: { _id: "$product_id",
    whs: { $addToSet: "$warehouse_id" }, owners: { $addToSet: "$owner_entity_id" }, sts: { $addToSet: "$status" },
    n: { $sum: 1 }, lr: { $sum: { $ifNull: ["$length_reserved", 0] } },
    ih: { $sum: { $cond: [{ $eq: ["$inspection.hold.held", true] }, 1, 0] } },
    am: { $sum: { $cond: [{ $gt: ["$active_movement.id", null] }, 1, 0] } } } }]).forEach(g => {
  feat[g._id] = { n_rolls: g.n, n_wh: g.whs.length, n_owner: g.owners.length, statuses: g.sts, length_reserved: g.lr, insp_hold: g.ih, active_mv: g.am, whs: g.whs, owners: g.owners };
});
const mk = {}; db.material_reservations.find({ status: "active" }, {_id:0}).forEach(m => { (mk[m.product_id] = mk[m.product_id] || []).push({ owner: m.owner_entity_id, qty: m.qty, mko: m.mko_number }); });
const OPEN = ["pending","created","approved","sent","receiving","partial"];
const po = {}; db.purchase_orders.find({ status: { $in: OPEN } }, {_id:0}).forEach(p => { (p.items||[]).forEach(it => { (po[it.product_id] = po[it.product_id] || []).push({ po: p.po_number, status: p.status, entity: p.entity_id, wh: p.warehouse_id, eta: p.expected_delivery_date, quantity: it.quantity, qty: it.qty, received_qty: it.received_qty, quantity_base: it.quantity_base, base_quantity: it.base_quantity, unit: it.unit || it.uom, source_so: !!(p.source_so_ids && p.source_so_ids.length) || !!it.source_so_id }); }); });
const ic = {}; db.interco_transactions.find({ role: "buyer", status: { $in: ["draft","confirmed","shipped"] } }, {_id:0}).forEach(d => { (d.items||[]).forEach(it => { (ic[it.product_id] = ic[it.product_id] || []).push({ no: d.number, status: d.status, buyer: d.buyer_entity_id, quantity: it.quantity, quantity_base: it.quantity_base, so: d.source_order_id || "" }); }); });
const bo = {}; db.sales_orders.find({ has_backorder: true }, {_id:0,number:1,status:1,entity_id:1,warehouse_id:1,backorders:1}).forEach(s => { (s.backorders||[]).forEach(b => { if (b.status !== "fulfilled") { (bo[b.product_id] = bo[b.product_id] || []).push({ so: s.number, status: s.status, entity: s.entity_id, wh: b.warehouse_id || s.warehouse_id || "", qty: b.backorder_qty }); } }); });
// pilih sampel: skor keragaman
const cand = Object.keys(feat).map(pid => {
  const f = feat[pid];
  let s = 0;
  s += (f.n_wh > 1) * 3 + (f.n_owner > 1) * 3 + (f.statuses.some(x => x.startsWith("in_transit"))) * 2 + f.statuses.includes("quarantine") * 2
     + f.statuses.includes("reserved") * 2 + (f.length_reserved > 0) * 3 + (mk[pid] ? 3 : 0) + (f.insp_hold > 0) * 3 + f.statuses.includes("subcon") * 2
     + f.statuses.includes("blocked") * 1 + (po[pid] ? 2 : 0) + (ic[pid] ? 2 : 0) + (bo[pid] ? 2 : 0) + f.statuses.includes("committed") * 2;
  return { pid, s };
}).sort((a, b) => b.s - a.s);
// + kasus khusus yang tidak terangkat skor (PO terbuka, transit transfer, antar-PT, karantina, potong besar)
const EXTRA = ["prod_e867010c6127", "prod_b10dd549f561", "prod_tenun_ikat", "prod_cc1920101107", "prod_74856325437f",
               "prod_add91839cc8e", "prod_60f19f07ee06"];
const pick = cand.slice(0, 24).map(x => x.pid);
EXTRA.forEach(p => { if (feat[p] && !pick.includes(p)) pick.push(p); });
const products = {};
pick.forEach(pid => {
  const p = db.products.findOne({ id: pid }, {_id:0,id:1,sku:1,name:1,base_unit:1,template_id:1,status:1});
  const segs = db.inventory_rolls.aggregate([{ $match: { product_id: pid } },
    { $group: { _id: { w: "$warehouse_id", o: "$owner_entity_id", s: "$status", u: "$unit",
        am: { $gt: ["$active_movement.id", null] }, ih: { $eq: ["$inspection.hold.held", true] } },
      n: { $sum: 1 }, len: { $sum: "$length_remaining" }, lres: { $sum: { $ifNull: ["$length_reserved", 0] } },
      npos: { $sum: { $cond: [{ $gt: ["$length_remaining", 0] }, 1, 0] } } } }]).toArray().map(g => ({ ...g._id, n: g.n, npos: g.npos, len: Math.round(g.len*100)/100, lres: Math.round(g.lres*100)/100, reg: !!reg[g._id.w], wh_active: reg[g._id.w] ? reg[g._id.w].active !== false : null, site: reg[g._id.w] ? reg[g._id.w].site_id : null }));
  const bals = db.inventory_balances.find({ product_id: pid }, {_id:0,warehouse_id:1,owner_entity_id:1,available_qty:1,reserved_qty:1,on_hand_qty:1,committed_qty:1,hold_qty:1,quarantine_qty:1,blocked_qty:1,in_transit_qty:1,in_transit_transfer_qty:1,in_transit_sales_qty:1,subcon_qty:1,on_order_qty:1,incoming_qty:1,atp_qty:1,roll_count:1,on_hand_roll_count:1,pending_demand_qty:1}).toArray();
  products[pid] = { product: p, feat: feat[pid], segs, balances: bals, makloon: mk[pid] || [], po: po[pid] || [], interco: ic[pid] || [], backorders: bo[pid] || [] };
});
// sampel roll: 2–3 per status + kasus khusus
const rolls = [];
const seen = {};
function take(q, k, lim) { db.inventory_rolls.find(q, {_id:0,id:1,roll_no:1,product_id:1,warehouse_id:1,owner_entity_id:1,status:1,length_initial:1,length_remaining:1,length_reserved:1,length_reservations:1,unit:1,bin_id:1,lot:1,lot_id:1,grade:1,rfid_tag_id:1,reserved_ref:1,active_movement:1,"inspection.hold":1,hold:1,journey:1,tracking_mode:1}).limit(lim).forEach(r => { if (!seen[r.id]) { seen[r.id] = 1; r._why = k; rolls.push(r); } }); }
db.inventory_rolls.distinct("status").forEach(s => take({ status: s }, "status:" + s, 3));
take({ length_reserved: { $gt: 0 } }, "potong_sebagian(length_reserved)", 5);
take({ "inspection.hold.held": true }, "tahan_inspeksi", 4);
take({ parent_roll_id: { $exists: true } }, "anak_potongan", 3);
take({ rfid_tag_id: { $ne: null } }, "ber_tag", 3);
take({ bin_id: /hilang/ }, "bin_simulasi_hilang", 2);
take({ "sim_anomaly.type": { $exists: true } }, "anomali_simulasi", 3);
print(JSON.stringify({ products, rolls, registered: Object.keys(reg) }));
