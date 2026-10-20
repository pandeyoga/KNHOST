// Audit only: parse source and compare URL/method shapes with exported OpenAPI.
const fs=require('fs'),path=require('path'),{createRequire}=require('module');
const outdir=__dirname;
const workspace=path.resolve(outdir,'../../..');
const srcroot=path.join(workspace,'work/KNHOST-frontend-audit-2026-10-20/frontend');
const req=createRequire(path.join(workspace,'work/KNHOST-plan-audit-2026-10-19/frontend/package.json'));
const parser=req('@babel/parser');
const methods=new Set(['get','post','put','patch','delete','head','options']);
const calls=[],errors=[];let filesParsed=0;
let bindings=new Map();
const relative=f=>path.relative(srcroot,f).replaceAll('\\','/');
function children(n,fn){if(!n||typeof n!=='object')return;fn(n);for(const [k,v]of Object.entries(n)){if(['loc','start','end','comments','tokens'].includes(k))continue;if(Array.isArray(v))v.forEach(x=>children(x,fn));else if(v&&typeof v==='object')children(v,fn);}}
function renderUrl(n,source,seen=new Set()){
 if(!n)return {text:'',unknown:true};
 if(n.type==='StringLiteral')return{text:n.value,unknown:false};
 if(n.type==='TemplateLiteral'){
  let text=n.quasis[0].value.cooked||'',unknown=false;
  n.expressions.forEach((x,i)=>{const r=renderUrl(x,source,seen);text+=r.text+(n.quasis[i+1].value.cooked||'');unknown||=r.unknown;});
  return {text,unknown};
 }
 if(n.type==='Identifier'&&n.name==='API')return{text:'/api',unknown:false,apiRoot:true};
 if(n.type==='Identifier'&&bindings.has(n.name)&&!seen.has(n.name)){const next=new Set(seen);next.add(n.name);return renderUrl(bindings.get(n.name),source,next);}
 if(n.type==='BinaryExpression'&&n.operator==='+'){const a=renderUrl(n.left,source,seen),b=renderUrl(n.right,source,seen);return{text:a.text+b.text,unknown:a.unknown||b.unknown};}
 return{text:'{'+source.slice(n.start,n.end).replace(/[\r\n]+/g,' ')+'}',unknown:true};
}
function parseFile(file){
 const source=fs.readFileSync(file,'utf8');let ast;
 try{ast=parser.parse(source,{sourceType:'unambiguous',plugins:['jsx'],errorRecovery:false});filesParsed++;}
 catch(e){errors.push({file:relative(file),error:e.message});return;}
 // Resolve a same-file variable only if it has a unique declaration, avoiding
 // conflation of duplicated names in unrelated functions/scopes.
 const decls=new Map();
 children(ast,n=>{if(n.type==='VariableDeclarator'&&n.id?.type==='Identifier'&&n.init){const list=decls.get(n.id.name)||[];list.push(n.init);decls.set(n.id.name,list);}});
 bindings=new Map([...decls].filter(([k,v])=>v.length===1).map(([k,v])=>[k,v[0]]));
 const aliases=new Set(['axios']);
 for(const n of ast.program.body)if(n.type==='ImportDeclaration'&&(/(?:apiClient|^axios$)/.test(n.source.value))){for(const s of n.specifiers)if(s.type==='ImportDefaultSpecifier')aliases.add(s.local.name);}
 children(ast,n=>{
  if(n.type!=='CallExpression'||n.callee?.type!=='MemberExpression'||n.callee.computed||n.callee.object?.type!=='Identifier'||!aliases.has(n.callee.object.name)||!methods.has(n.callee.property?.name))return;
  const arg=n.arguments[0];const r=renderUrl(arg,source);
  let template=r.text;
  const query=template.indexOf('?');
  // A ? inside a dynamic expression is not an actual query boundary.
  let depth=0,bound=-1;
  for(let i=0;i<template.length;i++){if(template[i]==='{')depth++;if(template[i]==='}')depth--;if(template[i]==='?'&&depth===0){bound=i;break;}}
  const queryText=bound>=0?template.slice(bound+1):'';
  if(bound>=0)template=template.slice(0,bound);
  const apiPrefixed=template.startsWith('/api/');
  let kind=apiPrefixed?'resolvable':'unresolved';
  let reason=apiPrefixed?'': 'URL not statically rooted at API or /api/';
  // Dynamic suffix immediately after a complete route can be query text or a
  // path. Do not turn it into a false missing-route finding.
  if(/[^/]\{[^{}]*\}$/.test(template)&&!/^.*\/\{[^{}]*\}$/.test(template)){
   kind='ambiguous_dynamic_suffix';reason='Dynamic suffix may append query or path; manual inspection required';
  }
  if(/[{}].*[{}]/.test(template)){
   const stripped=template.replace(/\{[^{}]*\}/g,'');
   if(/[{}]/.test(stripped)){kind='complex_dynamic';reason='Nested dynamic expressions cannot be normalized safely';}
  }
  if(/\{(?:path|endpoint|a\.path)\}/.test(template)){
    kind='dynamic_path_helper';reason='Helper accepts a whole path, potentially multiple segments; inspect actual callers';
  }
  calls.push({file:relative(file),line:n.loc.start.line,end_line:n.loc.end.line,method:n.callee.property.name.toUpperCase(),receiver:n.callee.object.name,url_source:arg?source.slice(arg.start,arg.end):'',path_template:template,query_source:queryText,url_kind:kind,url_reason:reason});
 });
}
function scan(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){const f=path.join(d,e.name);if(e.isDirectory())scan(f);else if(/\.(js|jsx)$/.test(e.name))parseFile(f);}}
scan(path.join(srcroot,'src'));
const apiFile=path.join(outdir,'openapi-8020-8dab.json');
const hasApi=fs.existsSync(apiFile), openapi=hasApi?JSON.parse(fs.readFileSync(apiFile,'utf8').replace(/^\uFEFF/,'')):null;
const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const norm=s=>s.replace(/\{[^{}]+\}/g,'{}').replace(/\/$/,'');
const routePaths=openapi?Object.keys(openapi.paths||{}):[];
const candidates=[];
for(const c of calls){
 if(!openapi){c.match_status='awaiting_openapi';continue;}
 if(c.url_kind!=='resolvable'){c.match_status='unresolved_not_a_finding';continue;}
 const direct=routePaths.filter(p=>norm(p)===norm(c.path_template));
 let matches=direct;
 {
  // Any route for which the static parts of the frontend URL can match is only
  // a possible match; dynamic values may be enums that resolve to static paths.
  const re=new RegExp('^'+c.path_template.split(/(\{[^{}]+\})/).map(x=>x.startsWith('{')?'[^/]+':escape(x)).join('')+'/?$');
  matches=[...new Set([...direct,...routePaths.filter(p=>re.test(p)||new RegExp('^'+p.split(/(\{[^{}]+\})/).map(x=>x.startsWith('{')?'[^/]+':escape(x)).join('')+'/?$').test(c.path_template))])];
 }
 c.openapi_paths=matches;
 if(!matches.length){c.match_status='candidate_path_missing';candidates.push(c);}
 else if(!matches.some(p=>openapi.paths[p][c.method.toLowerCase()])){c.match_status='candidate_method_missing';c.available_methods=[...new Set(matches.flatMap(p=>Object.keys(openapi.paths[p]).filter(m=>methods.has(m))))];candidates.push(c);}
 else c.match_status=direct.some(p=>openapi.paths[p][c.method.toLowerCase()])?'method_path_match':'dynamic_possible_match';
}
const countBy=(arr,key)=>arr.reduce((a,x)=>(a[x[key]]=(a[x[key]]||0)+1,a),{});
const inventory={baseline_sha:'8dab383f764df80737bfe02f887422b3fd72aa70',snapshot:srcroot,method:'AST named axios/apiClient aliases, HTTP member calls; URL/method shape parity only',files_parsed:filesParsed,parse_failures:errors,call_count:calls.length,call_sites_by_method:countBy(calls,'method'),call_sites_by_status:countBy(calls,'match_status'),openapi_loaded:hasApi,openapi_path_count:routePaths.length,candidates,calls,limitations:['Does not execute requests or business state transitions.','Dynamic URL builders and wrapper parameters are unresolved unless statically rooted at API.','OpenAPI omission is a candidate, not proof of missing runtime route.','Query parameters, payload schemas, authorization, hidden callers, and response semantics are outside this inventory.']};
fs.writeFileSync(path.join(outdir,'api-route-inventory-8dab.json'),JSON.stringify(inventory,null,2));
console.log(JSON.stringify({files_parsed:filesParsed,parse_failures:errors.length,call_count:calls.length,by_method:inventory.call_sites_by_method,by_status:inventory.call_sites_by_status,openapi_loaded:hasApi,openapi_paths:routePaths.length,candidates:candidates.map(({file,line,method,path_template,available_methods})=>({file,line,method,path_template,available_methods}))},null,2));
