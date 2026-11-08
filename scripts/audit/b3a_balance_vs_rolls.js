// Uji silang inventory_balances vs hitung ulang dari inventory_rolls (meniru roll_service.rebuild_balance)
const PHYS = {available:"available_qty",reserved:"reserved_qty",committed:"committed_qty",picked:"picked_qty",packed:"packed_qty",hold:"hold_qty",wip:"wip_qty",quarantine:"quarantine_qty",blocked:"blocked_qty",damaged:"damaged_qty"};
const TRANS = {in_transit_inbound:"in_transit_inbound_qty",in_transit_transfer:"in_transit_transfer_qty",in_transit_intercompany:"in_transit_intercompany_qty",in_transit_sales:"in_transit_sales_qty"};
const OFF = {subcon:"subcon_qty"};
const BUCKETS = [...Object.values(PHYS), ...Object.values(TRANS), ...Object.values(OFF)];
const prod = {};
db.products.find({}, {_id:0,id:1,base_unit:1,sku:1,name:1}).forEach(p => { prod[p.id] = p; });
const seg = {};
let unitMismatch = 0, unitMismatchEx = [];
const statusNoBucket = {};
db.inventory_rolls.find({}, {_id:0,id:1,product_id:1,warehouse_id:1,owner_entity_id:1,status:1,length_remaining:1,unit:1,active_movement:1,length_reserved:1,length_reservations:1}).forEach(r => {
  const k = r.product_id + "|" + r.warehouse_id + "|" + r.owner_entity_id;
  const s = seg[k] = seg[k] || {b:{}, rc:{}, n:0, mismatch:0};
  BUCKETS.forEach(b => { if (s.b[b] === undefined) { s.b[b] = 0; s.rc[b] = 0; } });
  s.n++;
  const base = ((prod[r.product_id]||{}).base_unit || "meter").toLowerCase();
  const ru = (r.unit || base).toLowerCase();
  let len = Number(r.length_remaining || 0);
  if (ru !== base && len) { s.mismatch++; unitMismatch++; if (unitMismatchEx.length < 8) unitMismatchEx.push(r.id+" "+ru+"≠"+base); return; }
  let bucket = PHYS[r.status] || TRANS[r.status] || OFF[r.status];
  if (!bucket) { statusNoBucket[r.status] = (statusNoBucket[r.status]||0)+1; }
  if (bucket === "available_qty" && r.active_movement && r.active_movement.id) bucket = "hold_qty";
  if (bucket === "available_qty" && Number(r.length_reserved||0) > 0 && len > 0) {
    (r.length_reservations||[]).forEach(x => { const b = PHYS[x.status||"reserved"] || "reserved_qty"; const q = Number(x.qty||0); s.b[b]+=q; len -= q; });
  }
  if (bucket) { s.b[bucket] += len; if (len > 0.0001) s.rc[bucket]++; }
});
print("roll unit≠base_unit produk: " + unitMismatch + " contoh " + JSON.stringify(unitMismatchEx));
print("status tanpa bucket: " + JSON.stringify(statusNoBucket));
let segs = Object.keys(seg).length, nBal = 0, diffSeg = 0, missing = 0, orphanBal = 0, diffs = [], totalAbs = {};
const seen = {};
db.inventory_balances.find({}, {_id:0}).forEach(b => {
  nBal++;
  const k = b.product_id + "|" + b.warehouse_id + "|" + b.owner_entity_id;
  seen[k] = (seen[k]||0)+1;
  const s = seg[k];
  if (!s) {
    const tot = BUCKETS.reduce((a,x)=>a+Math.abs(Number(b[x]||0)),0);
    orphanBal++;
    if (tot > 0.01) diffs.push({k, kind:"saldo_tanpa_roll", bal: BUCKETS.filter(x=>Math.abs(Number(b[x]||0))>0.01).map(x=>x+"="+b[x]).join(" "), updated_at:b.updated_at});
    return;
  }
  if (s.mismatch) return;
  const d = [];
  BUCKETS.forEach(x => { const exp = Math.round(s.b[x]*100)/100; const got = Number(b[x]||0); if (Math.abs(exp-got) > 0.011) { d.push(x+": saldo="+got+" roll="+exp); totalAbs[x] = (totalAbs[x]||0) + (got-exp); } });
  const expRc = s.rc["available_qty"]; if (Number(b.roll_count||0) !== expRc) d.push("roll_count: saldo="+b.roll_count+" roll="+expRc);
  const phys = Object.values(PHYS).reduce((a,x)=>a+s.b[x],0);
  if (Math.abs(phys - Number(b.on_hand_qty||0)) > 0.011) d.push("on_hand_qty: saldo="+b.on_hand_qty+" roll="+phys.toFixed(2));
  if (d.length) { diffSeg++; diffs.push({k, kind:"selisih", d, updated_at:b.updated_at}); }
});
Object.keys(seg).forEach(k => { if (!seen[k]) { missing++; const s = seg[k]; const tot = BUCKETS.reduce((a,x)=>a+s.b[x],0); if (tot > 0.01) diffs.push({k, kind:"roll_tanpa_saldo", n:s.n, total:tot}); } });
const dup = Object.keys(seen).filter(k => seen[k] > 1);
print(JSON.stringify({segmen_roll: segs, saldo: nBal, segmen_selisih: diffSeg, segmen_roll_tanpa_saldo: missing, saldo_tanpa_roll: orphanBal, saldo_duplikat: dup.length, net_selisih_per_bucket: totalAbs}));
diffs.slice(0, 60).forEach(x => print(JSON.stringify(x)));
print("... total baris selisih: " + diffs.length);
