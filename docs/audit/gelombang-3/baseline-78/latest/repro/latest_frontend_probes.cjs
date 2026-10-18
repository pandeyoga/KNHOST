const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../../../..'),repo=process.env.KNHOST_REPO||process.cwd();
const parser=require(path.join(repo,'frontend/node_modules/@babel/parser'));
const rel='frontend/src/features/sales_admin/FulfillmentDecisionDialog.jsx',src=fs.readFileSync(path.join(repo,rel),'utf8'),ast=parser.parse(src,{sourceType:'module',plugins:['jsx']});
let loadNode,submitNode;
function walk(n){if(!n||typeof n!=='object')return;if(n.type==='VariableDeclarator'&&n.id?.name==='load')loadNode=n.init.arguments[0];if(n.type==='FunctionDeclaration'&&n.id?.name==='submit')submitNode=n;for(const v of Object.values(n)){if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')walk(v);}}
walk(ast);
const errors=[],results=[];let lastError=null;
const noop=()=>{},setError=v=>{lastError=v;errors.push(v);};
const load=Function('setLoading','fulfillmentPlan','orderId','setData','setPlan','initLine','setError','apiErrorText',`return (${src.slice(loadNode.start,loadNode.end)});`)(noop,async()=>({lines:[],decisions:[]}), 'SO',noop,noop,()=>({}),setError,e=>e.message);
const submit=Function('setBusy','setError','note','lines','plan','fulfillmentPlanDecide','orderId','onDecided','orderNumber','apiErrorText','load',`return (${src.slice(submitNode.start,submitNode.end)});`)(noop,setError,'',[],{},async()=>{throw new Error('Interco failed; stock30 already executed and persisted');},'SO',noop,'SO',e=>e.message,load);
(async()=>{await submit();await new Promise(resolve=>setTimeout(resolve,0));results.push({id:'D4-PLAN-04-error-erased',expected:'Interco failed; stock30 already executed and persisted',actual:lastError,error_transitions:errors,status:lastError===''?'observed_difference':'pass',note:'Execute original submit and load functions with controlled failed POST and successful refresh. Catch sets error, refresh load resets it. Function-level JS, not browser rendering.'});fs.writeFileSync(path.join(__dirname,'latest-frontend-results.json'),JSON.stringify({commit:'a904d989b622f7da14c4892d03cf6ef0c43f3084',file:rel,results},null,2));console.log(JSON.stringify(results));})().catch(e=>{console.error(e);process.exitCode=1;});
