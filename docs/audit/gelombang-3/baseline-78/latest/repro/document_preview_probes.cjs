// Original hook function on the original API response; no React/browser claim.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../../../..'),repo=process.env.KNHOST_REPO||process.cwd();
const parser=require(path.join(repo,'frontend/node_modules/@babel/parser'));
const rel='frontend/src/hooks/useAppActions.js',src=fs.readFileSync(path.join(repo,rel),'utf8');
const ast=parser.parse(src,{sourceType:'module',plugins:['jsx']});let node;
function walk(n){if(!n||typeof n!=='object')return;if(n.type==='VariableDeclarator'&&n.id?.name==='previewTemplate')node=n.init;for(const v of Object.values(n)){if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')walk(v);}}walk(ast);
const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'document-preview-api-results.json'),'utf8'));
const state={},calls=[],results=[];
const rec=(id,expected,actual,note='')=>results.push({id,expected,actual,note,status:JSON.stringify(expected)===JSON.stringify(actual)?'pass':'observed_difference'});
(async()=>{
 const axios={post:async(url,payload)=>{calls.push({url,payload});throw {response:{status:fixture.missing_response.http,data:fixture.missing_response.body}};}};
 const preview=Function('axios','API','user','setPreviewHtml','setNotice',`return (${src.slice(node.start,node.end)});`)(axios,'http://audit.local/api',{name:'Audit User A'},v=>state.html=v,v=>state.notice=v);
 await preview(fixture.template.id,fixture.order.id);
 rec('D4-DOC-01-original-route-control',`http://audit.local/api/document-templates/${fixture.template.id}/preview`,calls[0].url);
 rec('D4-DOC-01-selected-template-document-type',fixture.template.document_type,calls[0].payload.document_type,'Selected Surat Jalan template loses its document type: original hook hardcodes invoice. Source call passes only templateId/orderId.');
 rec('D4-DOC-01-original-preview-html',true,typeof state.html==='string'&&state.html.length>0,'Original hook processes the original API404 response: notice Not Found, no iframe HTML. Browser DOM not tested.');
 const out={commit:fixture.commit,file:rel,mode:'Unmodified Babel-extracted function with original API error replayed through controlled transport',results,calls,state};
 fs.writeFileSync(path.join(__dirname,'document-preview-js-results.json'),JSON.stringify(out,null,2));console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exitCode=1;});
