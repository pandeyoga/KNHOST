// B3a (audit 2026-11-09) — anomali data roll & salinannya. BACA-SAJA (find/aggregate/count saja).
// Pakai: docker cp <berkas> kn-dev-mongo-1:/tmp/x.js && docker exec kn-dev-mongo-1 mongosh --quiet kn_test_trial --file /tmp/x.js
// Catatan mongosh: callback forEach yang MENGEMBALIKAN false menghentikan iterasi — semua callback di sini memakai blok {}.
const out = {};
function put(k, n, ex) { out[k] = { n: n, contoh: (ex || []).slice(0, 6) }; }
const KNOWN = ["on_order","in_transit_inbound","receiving","quarantine","available","reserved","committed","picked","packed",
  "cross_dock","in_transit_sales","sold","in_transit_transfer","in_transit_intercompany","blocked","damaged","returned","scrapped",
  "hold","wip","subcon","consumed","delivered","returned_supplier"];
const REG_LISTED = ["on_order","in_transit_inbound","receiving","quarantine","available","reserved","committed","picked","packed",
  "cross_dock","in_transit_sales","sold","in_transit_transfer","in_transit_intercompany","blocked","damaged","returned","scrapped"];
const prods = {}; db.products.find({}, {_id:0,id:1,base_unit:1,sku:1}).forEach(p => { prods[p.id] = p; });
const whs = {}; const binsByWh = {};
db.warehouses.find({}, {_id:0}).forEach(w => {
  whs[w.id] = w; const m = {};
  (w.zones||[]).forEach(z => { (z.racks||[]).forEach(r => {
    (r.bins||[]).forEach(b => { m[b.id] = b.code; });
    (r.levels||[]).forEach(l => { (l.bins||[]).forEach(b => { m[b.id] = b.code; }); });
  }); });
  binsByWh[w.id] = m;
});
const lots = {}; db.inventory_lots.find({}, {_id:0,id:1,lot_number:1,owner_entity_id:1,product_id:1,warehouse_id:1,roll_count:1,active_roll_count:1,qty_remaining:1,qty_available:1,legacy_lot_codes:1}).forEach(l => { lots[l.id] = l; });
const tags = {}; const tagByRoll = {};
db.rfid_tags.find({}, {_id:0}).forEach(t => { tags[t.id] = t; if (t.roll_id) { (tagByRoll[t.roll_id] = tagByRoll[t.roll_id] || []).push(t.id); } });
const grades = {}; db.md_grades.find({}, {_id:0,code:1,active:1}).forEach(g => { grades[g.code] = g; });
const statusCount = {}; const rollNo = {};
const A = {};
function add(k, v) { (A[k] = A[k] || []).push(v); }
db.inventory_rolls.find({}, {_id:0}).forEach(r => {
  statusCount[r.status] = (statusCount[r.status]||0) + 1;
  if (!KNOWN.includes(r.status)) add("status_tak_dikenal", r.id+" "+r.status);
  if (!REG_LISTED.includes(r.status)) add("status_tak_ada_di_registry", r.status);
  (rollNo[r.roll_no] = rollNo[r.roll_no] || []).push(r.id);
  const lr = Number(r.length_remaining||0), li = Number(r.length_initial||0);
  if (lr - li > 0.011) add("panjang_sisa_gt_awal", r.id+" "+lr+">"+li);
  if (lr < -0.001) add("panjang_negatif", r.id+" "+lr);
  if (["available","reserved","committed","quarantine","blocked","hold"].includes(r.status) && lr <= 0.001) add("status_aktif_panjang_0", r.id+" "+r.status);
  if (["consumed","delivered"].includes(r.status) && r.status === "consumed" && lr > 0.01) add("consumed_panjang_gt0", r.id+" "+lr);
  // reservasi panjang
  const sumRes = (r.length_reservations||[]).reduce((a,x)=>a+Number(x.qty||0),0);
  if (Math.abs(sumRes - Number(r.length_reserved||0)) > 0.011) add("length_reserved_ne_sum_reservations", r.id+" lr="+r.length_reserved+" sum="+sumRes.toFixed(2));
  if (Number(r.length_reserved||0) > lr + 0.011) add("length_reserved_gt_sisa", r.id+" "+r.length_reserved+">"+lr);
  if (Number(r.length_reserved||0) > 0 && r.status !== "available") add("length_reserved_pada_status_non_available", r.id+" "+r.status);
  // reserved_ref
  const held = ["reserved","committed","picked","packed","in_transit_sales"];
  if (held.includes(r.status) && !(r.reserved_ref && r.reserved_ref.id)) add("status_ditahan_tanpa_reserved_ref", r.id+" "+r.status);
  if (r.status === "available" && r.reserved_ref && r.reserved_ref.id) add("available_masih_punya_reserved_ref", r.id+" "+JSON.stringify(r.reserved_ref));
  // hold / inspection hold
  const ih = ((r.inspection||{}).hold||{}).held === true;
  if (ih) add("inspection_hold_true_status_"+r.status, r.id);
  if ((r.hold||{}).held === true && r.status !== "blocked") add("hold_true_tapi_status_bukan_blocked", r.id+" "+r.status);
  if (r.status === "blocked" && !((r.hold||{}).held === true)) add("blocked_tanpa_hold_object", r.id);
  // grade
  if (r.qc_grade && r.qc_grade !== r.grade) add("grade_ne_qc_grade", r.id+" "+r.grade+"/"+r.qc_grade);
  if ((r.inspection||{}).grade && r.inspection.grade !== r.grade) add("grade_ne_inspection_grade", r.id+" "+r.grade+"/"+r.inspection.grade);
  if (r.grade && Object.keys(grades).length && !grades[r.grade]) add("grade_tak_ada_di_md_grades", r.id+" "+r.grade);
  const gh = r.grade_history||[];
  if (gh.length && gh[gh.length-1].grade_after !== r.grade) add("grade_ne_grade_history_terakhir", r.id+" "+r.grade+" vs "+gh[gh.length-1].grade_after);
  if (r.grade && r.grade !== "A" && !gh.length) add("grade_non_A_tanpa_riwayat", r.id+" "+r.grade+" src="+(r.grade_source||"-")+" by="+(r.created_by||""));
  // lot
  const L = lots[r.lot_id];
  if (!L) add("lot_id_yatim", r.id+" "+r.lot_id);
  else {
    if (L.lot_number !== r.lot && !(L.legacy_lot_codes||[]).includes(r.lot)) add("roll_lot_ne_lot_number", r.id+" "+r.lot+" vs "+L.lot_number);
    if (L.owner_entity_id !== r.owner_entity_id) add("lot_owner_ne_roll_owner", r.id+" "+r.owner_entity_id+" vs lot "+L.owner_entity_id);
    if (L.product_id !== r.product_id) add("lot_product_ne_roll_product", r.id);
    if (L.warehouse_id && L.warehouse_id !== r.warehouse_id && !["delivered","consumed","in_transit_sales"].includes(r.status)) add("lot_warehouse_snapshot_ne_roll", r.id+" "+r.warehouse_id+" vs lot "+L.warehouse_id);
  }
  if (r.dye_lot && r.lot && r.dye_lot !== r.lot) add("dye_lot_ne_lot", r.id+" "+r.dye_lot+" vs "+r.lot);
  // tag
  if (r.rfid_tag_id) {
    const T = tags[r.rfid_tag_id];
    if (!T) add("rfid_tag_id_yatim", r.id+" "+r.rfid_tag_id);
    else if (T.roll_id !== r.id) add("tag_roll_id_ne_roll", r.id+" tag.roll_id="+T.roll_id);
  }
  if (tagByRoll[r.id] && (!r.rfid_tag_id || !tagByRoll[r.id].includes(r.rfid_tag_id))) add("roll_punya_tag_di_rfid_tags_tapi_rfid_tag_id_kosong_beda", r.id+" "+tagByRoll[r.id].join(","));
  if (tagByRoll[r.id] && tagByRoll[r.id].length > 1) add("roll_punya_gt1_tag", r.id+" "+tagByRoll[r.id].join(","));
  if (r.tracking_mode === "rfid" && !r.rfid_tag_id) add("tracking_rfid_tanpa_tag", r.id+" "+r.status);
  if (r.rfid_tag_id && r.tracking_mode !== "rfid") add("punya_tag_tracking_bukan_rfid", r.id+" "+r.tracking_mode);
  // bin
  if (r.bin_id && whs[r.warehouse_id] && !binsByWh[r.warehouse_id][r.bin_id] && !r.status.startsWith("in_transit") && !["delivered","consumed","returned_supplier","subcon"].includes(r.status)) add("bin_tak_ada_di_master_gudang", r.id+" "+r.warehouse_id+" "+r.bin_id);
  if (r.bin_code !== undefined && r.bin_id && binsByWh[r.warehouse_id] && binsByWh[r.warehouse_id][r.bin_id] && binsByWh[r.warehouse_id][r.bin_id] !== r.bin_code) add("bin_code_ne_master", r.id+" "+r.bin_code+" vs "+binsByWh[r.warehouse_id][r.bin_id]);
  if (!r.bin_id && ["available","reserved","committed","blocked","quarantine","hold"].includes(r.status)) add("fisik_di_gudang_tanpa_bin_"+r.status, r.id);
  // berat
  const sk = (r.secondary_measures||{}).kg;
  if (r.weight_kg != null && sk != null && Math.abs(Number(r.weight_kg) - Number(sk)) > 0.001) add("weight_kg_ne_secondary_kg", r.id+" "+r.weight_kg+" vs "+sk);
  if (r.weight_kg != null && sk == null && Number(r.weight_kg) > 0) add("weight_kg_tanpa_secondary", r.id);
  if (r.length != null && Math.abs(Number(r.length) - lr) > 0.011) add("field_length_ne_length_remaining", r.id+" length="+r.length+" sisa="+lr+" "+r.status);
  // satuan
  const P = prods[r.product_id];
  if (P && (P.base_unit||"meter").toLowerCase() !== (r.unit||"").toLowerCase()) add("unit_ne_base_unit", r.id+" "+r.unit+" vs "+P.base_unit);
  // journey vs status
  if (r.journey && r.journey.stage) add("journey:"+r.journey.stage+"|status:"+r.status, r.id);
  if (r.qc_status) add("qc_status:"+r.qc_status+"|status:"+r.status, r.id);
  if (r.location_type && r.location_type !== "warehouse_bin") add("location_type:"+r.location_type, r.id);
  if (r.status && r.status.startsWith("in_transit") && r.location_type === "warehouse_bin") add("in_transit_tapi_location_type_warehouse_bin", r.id+" "+r.status);
  // gudang dedicated
  const W = whs[r.warehouse_id];
  if (W && W.sharing_mode === "dedicated" && (W.entity_ids||[]).length && !W.entity_ids.includes(r.owner_entity_id) && !["delivered","consumed"].includes(r.status)) add("roll_pt_lain_di_gudang_dedicated", r.id+" "+r.owner_entity_id+" @"+W.code);
  if (W && W.active === false && !["delivered","consumed"].includes(r.status)) add("roll_di_gudang_nonaktif", r.id);
  if (r.earmarked_for && r.earmarked_for.id) add("earmarked", r.id+" "+JSON.stringify(r.earmarked_for));
  if (r.active_movement && r.active_movement.id) add("active_movement:"+r.status, r.id+" "+r.active_movement.id);
});
Object.keys(A).sort().forEach(k => put(k, A[k].length, A[k]));
const dupNo = Object.keys(rollNo).filter(k => rollNo[k].length > 1);
put("roll_no_kembar", dupNo.length, dupNo.map(k => k+" x"+rollNo[k].length+" "+rollNo[k].slice(0,3).join(",")));
out["_status_roll"] = statusCount;
// tag sisi rfid_tags
const T2 = {};
Object.values(tags).forEach(t => {
  const k = "tag_status:"+t.status; T2[k] = (T2[k]||0)+1;
  if (t.roll_id) { const r = db.inventory_rolls.findOne({id:t.roll_id},{_id:0,id:1,rfid_tag_id:1,status:1,owner_entity_id:1}); if (!r) { (A["tag_roll_yatim"] = A["tag_roll_yatim"]||[]).push(t.id+" "+t.roll_id); } else if (t.owner_entity_id && t.owner_entity_id !== r.owner_entity_id) { (A["tag_owner_ne_roll_owner"] = A["tag_owner_ne_roll_owner"]||[]).push(t.id+" "+t.owner_entity_id+" vs "+r.owner_entity_id); } }
});
["tag_roll_yatim","tag_owner_ne_roll_owner"].forEach(k => put(k, (A[k]||[]).length, A[k]||[]));
out["_tag_status"] = T2;
const epc = {}; Object.values(tags).forEach(t => { const e = t.epc || t.tag_code || t.code; if (e) { (epc[e] = epc[e]||[]).push(t.id); } });
const dupE = Object.keys(epc).filter(k => epc[k].length > 1);
put("epc_kembar", dupE.length, dupE.map(k => k+" "+epc[k].join(",")));
print(JSON.stringify(out, null, 1));
