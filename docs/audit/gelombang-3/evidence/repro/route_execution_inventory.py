"""Map registered handlers to recorded body execution, not business acceptance."""
import inspect,ast,json,csv,re
from pathlib import Path
import wave2_env as e
OUT=Path(__file__).resolve().parents[1];EV=OUT/'evidence'
cov=json.loads((EV/'backend-line-branch-coverage.json').read_text(encoding='utf-8'))['files'];by_path={}
for p,v in cov.items():
 try:
  q=Path(p)
  if not q.is_absolute():q=e.REPO.parents[1]/q
  rel=q.resolve().relative_to(e.REPO).as_posix()
 except ValueError:continue
 by_path[rel]=set(v['executed_lines'])
rows=[]
for r in e.server.app.routes:
 if not getattr(r,'path','').startswith('/api'):continue
 try:
  p=Path(inspect.getsourcefile(r.endpoint)).resolve();rel=p.relative_to(e.REPO).as_posix()
  src,start=inspect.getsourcelines(r.endpoint);text=''.join(src)
  module=ast.parse(p.read_text(encoding='utf-8-sig'))
  n=next(n for n in module.body if isinstance(n,(ast.AsyncFunctionDef,ast.FunctionDef)) and n.name==r.endpoint.__name__)
 except (TypeError,ValueError,StopIteration,OSError,SyntaxError):continue
 body_start=n.body[0].lineno
 hits=sorted(v for v in by_path.get(rel,set()) if body_start<=v<=n.end_lineno)
 for method in sorted(getattr(r,'methods',set())):
  rows.append({'method':method,'route':r.path,'source':rel,'handler':n.name,'line':n.lineno,'body_first_line':body_start,'body_end_line':n.end_lineno,'recorded_body_lines':len(hits),'recorded_body_entered':bool(hits),'direct_collections':';'.join(sorted(set(re.findall(r'db\.([A-Za-z_][A-Za-z_0-9]*)',text)))),'mutation':method in ['POST','PUT','PATCH','DELETE'],'semantic_all_states_verified':'NO'})
with (EV/'registered-route-execution.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
mutations=[r for r in rows if r['mutation']]
result={'candidate':'a904d989b622f7da14c4892d03cf6ef0c43f3084','registered_api_methods':len(rows),'recorded_body_entered':sum(r['recorded_body_entered'] for r in rows),'mutation_methods':len(mutations),'mutation_body_entered':sum(r['recorded_body_entered'] for r in mutations),'mutation_no_recorded_body':sum(not r['recorded_body_entered'] for r in mutations),'note':'Body line hits prove some handler body execution including guards/errors, never all branches, authorized success, numeric correctness or whole business flow. Counting imported def/decorator lines is avoided.'}
(EV/'route-execution-summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
e.client.close()
