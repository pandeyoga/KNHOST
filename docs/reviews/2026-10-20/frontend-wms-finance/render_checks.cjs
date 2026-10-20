// Audit-only shallow rendering: original JSX is transpiled unchanged; hooks are
// supplied controlled initial state and effects/network are not executed.
// This proves render conditions/formatters; it is not browser or backend UAT.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { createRequire } = require('module');
const root = path.resolve(__dirname, '../../../work/KNHOST-plan-audit-2026-10-19/frontend');
const sourceRev = process.env.AUDIT_SOURCE_REV || null;
const sourceRepo = process.env.AUDIT_SOURCE_REPO || path.resolve(__dirname, '../../../work/KNHOST-reader-integration-2026-10-18');
const req = createRequire(path.join(root, 'package.json'));
const babel = req('@babel/core');
const React = req('react');
let stateQueue = [], stateIndex = 0, stateUpdates = [];
const hooks = {
  ...React,
  useState: (v) => {
    const index = stateIndex++;
    return [index < stateQueue.length ? stateQueue[index] : (typeof v === 'function' ? v() : v), (value) => stateUpdates.push({index,value})];
  },
  useEffect: () => {}, useMemo: (f) => f(), useCallback: (f) => f,
  useRef: (v) => ({current:v}),
};
const fmt = (n) => new Intl.NumberFormat('id-ID', {style:'currency', currency:'IDR', maximumFractionDigits:0}).format(n || 0);
const stub = (name) => Object.assign(function ComponentStub(){return null;}, {displayName:name});
const stubModule = new Proxy({__esModule:true}, {get:(o,k) => k in o ? o[k] : stub(String(k))});
function load(rel) {
  const file = path.join(root, rel);
  const code = sourceRev ? require('child_process').execFileSync('git',['show',`${sourceRev}:frontend/${rel}`],{cwd:sourceRepo,encoding:'utf8'}) : fs.readFileSync(file, 'utf8');
  const transformed = babel.transformSync(code, {
    filename:file, babelrc:false, configFile:false,
    presets:[[req.resolve('@babel/preset-react'), {runtime:'automatic'}]],
    plugins:[req.resolve('@babel/plugin-transform-modules-commonjs')],
  }).code;
  const m = {exports:{}};
  const localRequire = (id) => {
    if (id === 'react') return hooks;
    if (id === 'react/jsx-runtime') return req(id);
    if (id.includes('formatters')) return {formatCurrency:fmt, formatQty:(n)=>String(n||0)};
    if (id.includes('financeShared')) return {...stubModule, FC:{}, NOW:new Date(), compactIDR:fmt, entityParam:()=>({}), chartTooltip:{}, KpiCard:stub('KpiCard'), Panel:stub('Panel'), EmptyState:stub('EmptyState'), formatCurrency:fmt};
    if (id.includes('LocationScopeBadge')) return {useLocationScope:()=>({restricted:false}), LocationScopeBadge:stub('LocationScopeBadge')};
    if (id.includes('locUtils')) return {TERMS:{site:'Lokasi',warehouse:'Gudang',zone:'Zona',rack:'Lemari',level:'Rak',bin:'Bin'}, normalizeZones:(x)=>x||[],fmtUnits:()=>'',q:(v)=>String(v)};
    if (id.includes('rfidShared')) return {...stubModule,useWarehouses:()=>({warehouses:[],whId:'',setWhId:()=>{},whOpts:[]}),RfidHeader:stub('RfidHeader'),Stat:stub('Stat'),SectionCard:stub('SectionCard'),EmptyBox:stub('EmptyBox'),Pill:stub('Pill'),fmtTime:()=>''};
    if (id.endsWith('intercoApi')) return {SETTLEMENT_METHODS:[{value:'transfer',label:'Transfer'}],fmtDate:(x)=>x};
    if (id.endsWith('paymentApi')) return {...stubModule,directionMeta:()=>({bg:'white',fg:'black'}),money:fmt};
    return stubModule;
  };
  vm.runInNewContext('(function(require,module,exports){'+transformed+'\n})', {console, Date, Intl, Object, Array, Math, Number, String, Set, Map, setTimeout, clearTimeout})(localRequire,m,m.exports);
  return m.exports;
}
function render(fn, props={},states=[]) {stateQueue=states;stateIndex=0;stateUpdates=[];return fn(props);}
function nodes(n, predicate, out=[]) {
  if (Array.isArray(n)) n.forEach(x=>nodes(x,predicate,out));
  else if (n && typeof n==='object' && n.props) {if(predicate(n))out.push(n);nodes(n.props.children,predicate,out);}
  return out;
}
const byTest = (tree,id) => nodes(tree,n=>n.props['data-testid']===id);
const result=[];
const transfer = load('src/features/wms/transfer/TransferDetailModal.jsx').default;
for(const role of ['manager','admin','custom_manager']) {
  const tree=render(transfer,{transfer:{id:'t',status:'waiting_approval',items:[]},user:{role,permissions:{transfer:['approve','reject']}}});
  result.push({case:'transfer_approval_button', role, permission:'transfer.approve', rendered:byTest(tree,'approve-transfer-button').length>0});
}
const receipt=load('src/features/wms/transfer/TransferReceiptPanel.jsx').default;
const receiptTree=render(receipt,{transfer:{id:'t',status:'dispatched'},user:{role:'admin'}},[null,{},'','','',[],false,'Gagal memuat penerimaan.']);
result.push({case:'receipt_first_load_error',errorState:'Gagal memuat penerimaan.',loadingRendered:byTest(receiptTree,'transfer-receipt-loading').length>0,errorRendered:byTest(receiptTree,'transfer-receipt-error').length>0});
const balanced=load('src/features/finance/FinancialStatementsParts.jsx').BalancedKpi;
for(const value of [undefined,null,false,true]) {
  const tree=render(balanced,{balanced:value});
  result.push({case:'balance_sheet_unknown_status',input:value===undefined?'undefined':value,text:byTest(tree,'fs-bs-kpi-balanced-value')[0].props.children});
}
const forecast=load('src/features/finance/CashFlowForecastView.jsx').default;
const cfTree=render(forecast,{selectedEntity:'ent_ksc'},[{cash_now:0,total_inflow:1,total_outflow:101,buckets:[{label:'0-7 hari',inflow:1,outflow:101,cumulative_cash:-100}]},false,'']);
const tool=nodes(cfTree,n=>n.type.displayName==='Tooltip')[0];
result.push({case:'cash_deficit_tooltip',sourceValue:-100,series:'Posisi Kas Kumulatif',displayed:tool.props.formatter(-100,'Posisi Kas Kumulatif')[0],expected:fmt(-100)});
// RFID admin-only device controls were inspected but are not a custom-role bug:
// custom_role_service.create_custom explicitly forbids Admin as a base template.
const settle=load('src/features/finance/interco/IntercoSettlementModal.jsx').default;
const select=load('src/components/KNSelect.jsx').KNSelect;
const settleTree=render(settle,{entities:[{id:'a',name:'A'},{id:'b',name:'B'}]});
const payee=byTest(settleTree,'interco-settle-payee')[0];
const control=select(payee.props);
control.props.onValueChange('b');
result.push({case:'interco_payee_select',parentCallbackProp:typeof payee.props.onChange,acceptedCallbackProp:typeof payee.props.onValueChange,stateUpdates:[...stateUpdates],expected:'setPayee(b)'});
const intercoCreate=load('src/features/finance/interco/IntercoCreateModal.jsx').default;
const createTree=render(intercoCreate,{entities:[{id:'a',name:'A'},{id:'b',name:'B'}],currentEntityId:'a'});
const buyer=byTest(createTree,'interco-create-buyer')[0];
select(buyer.props).props.onValueChange('b');
result.push({case:'interco_buyer_select',parentCallbackProp:typeof buyer.props.onChange,acceptedCallbackProp:typeof buyer.props.onValueChange,stateUpdates:[...stateUpdates],expected:'setBuyer(b)'});
const locations=load('src/features/wms/LocationPutawayView.jsx').default;
for(const role of ['warehouse_admin','custom_warehouse_admin']) {
  const tree=render(locations,{currentUser:{role,permissions:{warehouse:['view','update']}},selectedEntity:'a'},['structure']);
  const editor=nodes(tree,n=>Object.prototype.hasOwnProperty.call(n.props,'canEdit'))[0];
  result.push({case:'structure_editor_authority',role,permission:'warehouse.update',canEdit:editor.props.canEdit});
}
const credit=load('src/features/finance/StoreCreditView.jsx').default;
for(const role of ['manager','custom_manager']) {
  const tree=render(credit,{currentUser:{role,permissions:{ar_receipt:['view','void']}},selectedEntity:'a'},[[],false,'','',{customer_id:'c',balance:100}]);
  const ledger=nodes(tree,n=>Object.prototype.hasOwnProperty.call(n.props,'canAdjust'))[0];
  result.push({case:'store_credit_adjust_authority',role,permission:'ar_receipt.void',canAdjust:ledger.props.canAdjust});
}
const pv=load('src/features/finance/payments/PaymentVarianceQueue.jsx').default;
const receiptRow={receipt_id:'r',direction:'over',delta:5,funds:105,expected:100};
for(const role of ['admin','finance','custom_finance']) {
  const tree=render(pv,{currentUser:{role,permissions:{payment_variance:['view','decide']}},selectedEntity:'a'},[{items:[],pending:[receiptRow],stats:{}},[],false,'',null,false,'','']);
  const pager=nodes(tree,n=>n.props.testId==='payment-variance-pager')[0];
  const rowTree=pager.props.children(receiptRow);
  result.push({case:'payment_variance_decide_button',role,permission:'payment_variance.decide',rendered:byTest(rowTree,'pv-decide-r').length>0});
}
console.log(JSON.stringify({method:'Shallow render original JSX; controlled hook state; no API or DB mutation',source_revision:sourceRev,results:result},null,2));
