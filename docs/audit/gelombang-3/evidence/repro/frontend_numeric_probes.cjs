// Execute unmodified function/expressions extracted from the candidate's Babel AST.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../../../..'),repo=path.join(root,'work/KNHOST-data-audit-latest-2026-10-05');
const parser=require(path.join(root,'work/validation-babel-parser/package/lib/index.js'));
const rel='frontend/src/features/manager/ManagerDashboard.jsx',src=fs.readFileSync(path.join(repo,rel),'utf8'),ast=parser.parse(src,{sourceType:'module',plugins:['jsx']});
const nodes={};function walk(n){if(!n||typeof n!=='object')return;if(n.type==='VariableDeclarator'&&n.id?.type==='Identifier')nodes[n.id.name]=n.init;for(const x of Object.values(n)){if(Array.isArray(x))x.forEach(walk);else if(x&&typeof x==='object')walk(x);}}walk(ast);
const results=[];function rec(id,expected,actual,note=''){results.push({id,expected,actual,status:JSON.stringify(expected)===JSON.stringify(actual)?'pass':'observed_difference',note});}
(async()=>{
 const expr=src.slice(nodes.velocityData.start,nodes.velocityData.end);
 const get=Function('velocity',`return (${expr});`);
 for(const n of [7,30,90])rec(`D4-FE-01-chart-${n}`,n,get({velocity:Array.from({length:n},(_,i)=>({date:String(i),count:1}))}).length,'Execute the original velocityData expression with n input days.');
 const setters=['setLoading','setSummary','setFunnel','setVelocity','setTopCustomers','setUtilization','setAging','setError'];
 const state={},pending=[];const axios={get:(url,cfg)=>new Promise(resolve=>pending.push({url,entity:cfg.params.entity_id,resolve}))};
 const args=[...setters,'selectedEntity','headers','axios','API','period','agingDays'];
 const factory=Function(...args,`return (${src.slice(nodes.load.start,nodes.load.end)});`);
 const make=period=>factory(...setters.map(k=>v=>{state[k]=v;}),'A',{},axios,'http://audit.local/api',period,30);
 const pa=make(30)(); const oldBatch=pending.slice(); const pb=make(90)(); const currentBatch=pending.slice(oldBatch.length);
 const finish=(batch,days)=>batch.forEach(p=>p.resolve({data:p.url.includes('/reports/order-velocity')?{total_orders:days,avg_per_day:1,velocity:Array.from({length:days},(_,i)=>({date:String(i),count:1}))}:[]}));
 finish(currentBatch,90);await pb;rec('D4-FE-02-after-current-period-response',90,state.setVelocity.total_orders);
 finish(oldBatch,30);await pa;rec('D4-FE-02-stale-period-overwrite',90,state.setVelocity.total_orders,'Actual UI-consumed total_orders: same entity A, period30 then90; old30 finishes last. App.js remounts by selectedEntity, not period. The earlier entity-switch hypothesis is withdrawn because the remount invalidates that shared-setter scenario.');
 fs.writeFileSync(path.join(__dirname,'frontend-numeric-results.json'),JSON.stringify({commit:'a904d989b622f7da14c4892d03cf6ef0c43f3084',file:rel,mode:'Unmodified candidate JS expressions/functions extracted by Babel; mocked transport controls response scheduling; React browser rendering is not tested.',results},null,2));console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exitCode=1;});
