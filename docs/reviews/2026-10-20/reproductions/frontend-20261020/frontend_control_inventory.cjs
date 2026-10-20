const fs=require('fs'),path=require('path');
const base=path.resolve(__dirname,'..'),root=path.join(__dirname,'KNHOST-frontend-audit-2026-10-20','frontend','src');
const mods=path.join(__dirname,'KNHOST-plan-audit-2026-10-19','frontend','node_modules');
const parser=require(path.join(mods,'@babel/parser')),traverse=require(path.join(mods,'@babel/traverse')).default;
let files=0,errors=[],controls=[],buttonsWithoutAction=[];
function walk(dir){for(const d of fs.readdirSync(dir,{withFileTypes:true})){let p=path.join(dir,d.name);if(d.isDirectory())walk(p);else if(/\.(jsx?|tsx?)$/.test(d.name))scan(p);}}
function scan(p){files++;let ast;try{ast=parser.parse(fs.readFileSync(p,'utf8'),{sourceType:'unambiguous',plugins:['jsx','typescript']});}catch(e){errors.push({file:path.relative(root,p),error:String(e)});return;}
traverse(ast,{JSXOpeningElement(n){const el=n.node; if(el.name.type!=='JSXIdentifier')return;const name=el.name.name;if(!['button','Button','input','select','textarea','form','a'].includes(name))return;
const attrs={};let spread=false;for(const a of el.attributes){if(a.type==='JSXSpreadAttribute'){spread=true;continue;}if(a.type==='JSXAttribute')attrs[a.name.name]=a.value?.type==='StringLiteral'?a.value.value:a.value?.type==='JSXExpressionContainer'?a.value.expression.type:true;}
let label='';const parent=n.parentPath.node;if(parent.children)label=parent.children.filter(x=>x.type==='JSXText').map(x=>x.value.trim()).filter(Boolean).join(' ').replace(/\s+/g,' ').slice(0,180);
const row={file:path.relative(root,p).replaceAll('\\','/'),line:el.loc.start.line,element:name,attributes:attrs,label,spread};controls.push(row);
if(name==='button'&&!('onClick'in attrs)&&!spread&&!('disabled'in attrs)&&!n.findParent(t=>t.isJSXElement()&&t.node.openingElement.name.type==='JSXIdentifier'&&t.node.openingElement.name.name==='form')&&attrs.type!=='submit'&&attrs.type!=='reset')buttonsWithoutAction.push(row);
}});}
walk(root);const out=path.join(base,'output','audit-plan-2026-10-19','evidence','frontend-20261020');fs.mkdirSync(out,{recursive:true});
const result={commit:'8dab383f764df80737bfe02f887422b3fd72aa70',method:'AST inventory only; control counts are not executed test counts; button candidates require manual review',files,parse_errors:errors,control_count:controls.length,by_element:controls.reduce((a,c)=>(a[c.element]=(a[c.element]||0)+1,a),{}),buttons_without_obvious_action:buttonsWithoutAction,controls};fs.writeFileSync(path.join(out,'frontend-control-inventory.json'),JSON.stringify(result,null,2));
console.log(JSON.stringify({files,parse_errors:errors.length,controls:controls.length,buttons_without_obvious_action:buttonsWithoutAction},null,2));
