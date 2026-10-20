const fs=require('fs'),path=require('path'),{createRequire}=require('module');
const root=path.resolve(__dirname,'../../../work/KNHOST-plan-audit-2026-10-19/frontend');
const req=createRequire(path.join(root,'package.json')), babel=req('@babel/core');
const out=[], failures=[];
function walk(n,file){
 if(!n||typeof n!=='object')return;
 if(n.type==='JSXOpeningElement'&&n.name?.name==='KNSelect'){
  const attrs=n.attributes.filter(a=>a.type==='JSXAttribute').map(a=>a.name.name);
  if(attrs.includes('onChange')&&!attrs.includes('onValueChange'))out.push({file:path.relative(root,file).replaceAll('\\','/'),line:n.loc.start.line,props:attrs});
 }
 for(const[k,v]of Object.entries(n))if(!['loc','start','end'].includes(k))if(Array.isArray(v))v.forEach(x=>walk(x,file));else if(v&&typeof v==='object')walk(v,file);
}
function files(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){const f=path.join(d,e.name);if(e.isDirectory())files(f);else if(/\.(jsx|js)$/.test(f))try{walk(babel.parseSync(fs.readFileSync(f,'utf8'),{filename:f,babelrc:false,configFile:false,parserOpts:{plugins:['jsx']}}),f);}catch(e){failures.push({file:f,error:e.message});}}}
files(path.join(root,'src'));
console.log(JSON.stringify({rule:'KNSelect receives onChange but not its implemented callback onValueChange',matches:out,parse_failures:failures},null,2));
