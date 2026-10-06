const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../../../..'), repo=path.join(root,'work/KNHOST-data-audit-latest-2026-10-05');
const parser=require(path.join(root,'work/validation-babel-parser/package/lib/index.js'));
const rel='frontend/src/features/orders/OrderDashboard.jsx',src=fs.readFileSync(path.join(repo,rel),'utf8');
const ast=parser.parse(src,{sourceType:'module',plugins:['jsx']});let metrics;
function walk(n){if(!n||typeof n!=='object')return;if(n.type==='VariableDeclarator'&&n.id?.name==='metrics')metrics=n.init.arguments[0];for(const v of Object.values(n)){if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')walk(v);}}walk(ast);
const run=Function('orders','summary','timeRange',`return (${src.slice(metrics.start,metrics.end)})();`);
const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'order-dashboard-fixture.json'),'utf8'));
const result=run(fixture.dashboard_orders,fixture.summary,'7d'),results=[];
function rec(id,expected,actual,note){results.push({id,expected,actual,note,status:JSON.stringify(expected)===JSON.stringify(actual)?'pass':'observed_difference'});}
rec('D4-ORDER-01-revenue-control',3000,result.totalRevenue,'Full server aggregate is correct; preserve this successful repair.');
rec('D4-ORDER-01-count',30,result.totalOrders,'The original component still counts the twenty-item dashboard window.');
rec('D4-ORDER-01-average',100,result.avgOrderValue,'Full revenue3000 divided by local count20 produces150; same eligible thirty orders should average100. Server already supplies matching revenue.count30.');
rec('D4-ORDER-01-customer-revenue',3000,result.topCustomers[0].revenue,'Top Customers uses capped local list, even though all thirty orders have the same customer.');
fs.writeFileSync(path.join(__dirname,'order-dashboard-results.json'),JSON.stringify({candidate:fixture.candidate,file:rel,mode:'Unmodified Babel-extracted useMemo function, with output of original public ASGI dashboard and summary endpoints. No rendered browser test.',results},null,2));
console.log(JSON.stringify(results));
