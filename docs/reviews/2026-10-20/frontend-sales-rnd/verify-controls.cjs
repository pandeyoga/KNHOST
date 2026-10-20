// Read-only audit harness. Executes functions extracted from actual JSX sources.
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '../../..');
const deps = path.join(root, 'work/KNHOST-plan-audit-2026-10-19');
const app = process.env.AUDIT_APP_ROOT || deps;
const suffix = process.env.AUDIT_OUTPUT_SUFFIX || '';
const parser = require(path.join(deps, 'frontend/node_modules/@babel/parser'));
const traverse = require(path.join(deps, 'frontend/node_modules/@babel/traverse')).default;
const results=[];
function extract(rel, name){
  const s=fs.readFileSync(path.join(app,rel),'utf8');
  const ast=parser.parse(s,{sourceType:'module',plugins:['jsx']});
  let n; traverse(ast,{FunctionDeclaration(p){if(p.node.id?.name===name)n=p.node;}});
  if(!n)throw Error('Missing '+name);
  return {code:s.slice(n.start,n.end),line:n.loc.start.line};
}
async function main(){
  const parent=extract('frontend/src/features/sales/SalesReturns.jsx','handleSettle');
  const child=extract('frontend/src/features/sales/ReturnSettleModal.jsx','confirm');
  const errors=[];let closed=false;let busy=false;
  const axios={post:async()=>{throw {response:{data:{detail:'AUDIT: QC/evidence gate rejected settlement'}}}}};
  const API='http://audit.invalid/api'; const setError=x=>errors.push(x);
  const setNotice=()=>{throw Error('Unexpected success')};const setSelected=()=>{};const load=()=>{};
  const onSettle=eval('('+parent.code+')');const onClose=()=>closed=true;const setBusy=x=>busy=x;
  const decisions=[{include:true,settle_qty:120}],ret={id:'audit-ret',number:'AUDIT-RET'};
  const outcome='refund',notes='',movesStock=true,physLocs=[],returnWarehouseId='',refundAccount='',decisionNote='';
  await eval('('+child.code+')')();
  results.push({id:'FE-SR-01',test:'actual ReturnSettleModal.confirm + actual SalesReturns.handleSettle, backend rejection injected',actual:{modal_closed:closed,busy,errors},expected:{modal_closed:false,visible_error_in_detail:true},source:{parent_line:parent.line,child_line:child.line},limit:'Callback behavior verified; no browser DOM in this harness. Parent error UI is rendered only after early-return detail branch.'});
  const orderFn=extract('frontend/src/features/sales/CreateReturnForm.jsx','handleOrderChange');
  let orderId='',shipped=null,items=[];const pending={};
  const axios2={get:(_url,{params})=>new Promise(res=>pending[params.order_id]=res)};
  const make=new Function('axios','API','setOrderId','setShipped','setItems','setError',`return (${orderFn.code})`);
  const change=make(axios2,API,x=>orderId=x,x=>shipped=x,x=>items=x,setError);
  const data=id=>({data:{products:[{product_id:'product-'+id,product_name:id,unit:'yard',remaining:100}],rolls:[]}});
  change('SO-A');change('SO-B');pending['SO-B'](data('B'));await Promise.resolve();pending['SO-A'](data('A'));await Promise.resolve();
  results.push({id:'FE-SR-02',test:'actual handleOrderChange, earlier request resolves after newer request',actual:{selected_order:orderId,product_rows:items.map(x=>x.product_id)},expected:{selected_order:'SO-B',product_rows:['product-B']},source_line:orderFn.line,limit:'Deterministic callback race verified; backend rejection/data integrity not evaluated by this test.'});
  const roles=['admin','manager','sales','sales_admin','audit_custom_sales'];
  results.push({id:'FE-SR-03',test:'Actual literal role condition in SpecialOrderDetail line435 compared with permission-based API',actual:roles.map(role=>({role,button_canEdit:['admin','manager','sales','sales_admin'].includes(role)})),expected:'Custom role with order.update can use customer-decision API and should expose permitted action.',limit:'Static gate evaluation. Full custom role API scenario is documented separately.'});
  const files=[];
  for(const folder of ['sales','sales_admin','rnd','inspections']){
    const walk=p=>fs.readdirSync(p,{withFileTypes:true}).forEach(e=>e.isDirectory()?walk(path.join(p,e.name)):/\.(jsx|js)$/.test(e.name)&&files.push(path.join(p,e.name)));
    walk(path.join(app,'frontend/src/features',folder));
  }
  files.push(path.join(app,'frontend/src/features/wms/QCInspection.jsx'));
  const inventory=[];
  for(const file of files){
    const source=fs.readFileSync(file,'utf8');let ast;
    try{ast=parser.parse(source,{sourceType:'module',plugins:['jsx']});}catch{continue;}
    traverse(ast,{JSXOpeningElement(p){const n=p.node;if(n.name.type!=='JSXIdentifier'||!['button','input','KNSelect','FormModal'].includes(n.name.name))return;
      const attrs=Object.fromEntries(n.attributes.filter(a=>a.type==='JSXAttribute').map(a=>[a.name.name,a.value?.type==='StringLiteral'?a.value.value:a.value?source.slice(a.value.start,a.value.end):true]));
      inventory.push({file:path.relative(app,file).replaceAll('\\','/'),line:n.loc.start.line,element:n.name.name,test_id:attrs['data-testid']||attrs.testId||'',handler:attrs.onClick||attrs.onChange||attrs.onValueChange||attrs.onSubmit||'',disabled:attrs.disabled||attrs.submitDisabled||'',type:attrs.type||''});
    }});
  }
  fs.writeFileSync(path.join(__dirname,`control-inventory${suffix}.json`),JSON.stringify({note:'Static inventory only; presence does not establish all states/roles/browser behavior tested.',file_count:files.length,control_count:inventory.length,controls:inventory},null,2));
  fs.writeFileSync(path.join(__dirname,`callback-evidence${suffix}.json`),JSON.stringify(results,null,2));
  console.log(JSON.stringify({results,inventory:{files:files.length,controls:inventory.length}},null,2));
}
main().catch(e=>{console.error(e);process.exit(1)});
