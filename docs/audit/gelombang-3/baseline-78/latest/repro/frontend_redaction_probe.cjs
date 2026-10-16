const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../../../..'), repo=process.env.KNHOST_REPO||process.cwd();
const source=fs.readFileSync(path.join(repo,'frontend/src/utils/formatters.js'),'utf8');
const parser=require(path.join(repo,'frontend/node_modules/@babel/parser'));
const ast=parser.parse(source,{sourceType:'module'});
const n=ast.program.body.find(x=>x.type==='ExportNamedDeclaration'&&x.declaration?.declarations?.[0]?.id.name==='formatCurrency').declaration.declarations[0].init;
const format=Function(`return (${source.slice(n.start,n.end)});`)();
const result={id:'D4-FE-03-redacted-as-zero',expected:'Tidak tersedia / disembunyikan',actual:format(undefined),status:'observed_difference',note:'Execute the original formatter used by the unconditional HPP and margin KPI cards. No browser rendering claimed.'};
fs.writeFileSync(path.join(__dirname,'frontend-redaction-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
