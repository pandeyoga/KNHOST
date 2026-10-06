// Execute unmodified function/expressions extracted from the candidate's Babel AST.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../../..'),repo=process.env.KNHOST_REPO||process.cwd();
const parser=require(path.join(repo,'frontend/node_modules/@babel/parser'));
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
 const make=entity=>factory(...setters.map(k=>v=>{state[k]=v;}),entity,{},axios,'http://audit.local/api',30,30);
 const pa=make('A')(),pb=make('B')();
 const finish=(entity,value)=>pending.filter(p=>p.entity===entity).forEach(p=>p.resolve({data:p.url.includes('/reports/summary')?{entity,value}:[]}));
 finish('B',20);await pb;rec('D4-FE-02-after-current-response','B',state.setSummary.entity);
 finish('A',10);await pa;rec('D4-FE-02-stale-entity-overwrite','B',state.setSummary.entity,'The old A response completes after B and replaces B data; source useEffect has no cancellation/generation guard.');
 fs.writeFileSync(path.join(__dirname,'frontend-numeric-results.json'),JSON.stringify({commit:'d6da1a3d536228582645abb98aea19f3e491f300',file:rel,mode:'Unmodified candidate JS expressions/functions extracted by Babel; mocked transport controls response scheduling; React browser rendering is not tested.',results},null,2));console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exitCode=1;});
