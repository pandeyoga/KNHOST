"""Read route contracts against a separate UUID synthetic ASGI database; not a correctness oracle."""
import asyncio,ast,json,re,traceback
from datetime import datetime,timezone
from pathlib import Path
import wave2_env as e
results=[]
async def main():
 await e.seed();await e.db.users.update_one({'id':'U'},{'$set':{'role':'admin','allowed_entity_ids':['A','B']}})
 perms={}
 for p in (e.REPO/'backend/routers').glob('*.py'):
  tree=ast.parse(p.read_text(encoding='utf-8-sig'))
  for n in ast.walk(tree):
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='require_permission' and len(n.args)>=3 and isinstance(n.args[1],ast.Constant) and isinstance(n.args[2],ast.Constant):perms.setdefault(n.args[1].value,[]).append(n.args[2].value)
 await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{k:sorted(set(v)) for k,v in perms.items()}}})
 await e.db.warehouses.insert_one({'id':'WH','name':'Contract sweep warehouse','sharing_mode':'shared','status':'active','active':True,'zones':[]})
 await e.db.products.insert_one({'id':'P','sku':'P','name':'Contract sweep SKU','base_unit':'meter','stage':'finished','line_code':'woven','fabric_type':'woven','status':'active','price':100,'harga_pokok':10})
 from services import gl_service,roll_service
 await gl_service.seed_default_coa();await roll_service.create_inbound_roll('P','WH','A',10,unit_cost=10)
 headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}
 routes=[r for r in e.server.app.routes if 'GET' in getattr(r,'methods',set()) and r.path.startswith('/api')]
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=True),base_url='http://audit.local',headers=headers) as http:
  for i,r in enumerate(routes):
   rec={'path':r.path,'handler':r.endpoint.__module__+'.'+r.endpoint.__name__}
   if r.path_params if hasattr(r,'path_params') else False:pass
   if '{' in r.path:rec.update(status='not_executed',reason='Requires a coherent resource-specific fixture; no invented ID substitution.')
   elif '/callback' in r.path:rec.update(status='not_executed',reason='External integration callback.')
   else:
    params={};missing=[]
    for f in r.dependant.query_params:
     if not f.required:continue
     name=f.alias
     if name in ('start','end','date_from','date_to','as_of','day'):params[name]=datetime.now(timezone.utc).date().isoformat()
     elif name in ('month','period'):params[name]=datetime.now(timezone.utc).strftime('%Y-%m')
     elif name=='entity_id':params[name]='A'
     else:missing.append(name)
    if missing:rec.update(status='not_executed',reason='Required query fixture: '+','.join(missing))
    else:
     try:
      response=await asyncio.wait_for(http.get(r.path,params=params),12)
      rec.update(status='executed',http_status=response.status_code,content_type=response.headers.get('content-type',''))
      if rec['content_type'].startswith('application/json'):
       body=response.json();rec['shape']='object' if isinstance(body,dict) else 'array' if isinstance(body,list) else type(body).__name__
       rec['keys']=sorted(body) if isinstance(body,dict) else None
       if response.status_code>=400:rec['detail']=str(body.get('detail',''))[:300] if isinstance(body,dict) else ''
     except Exception as ex:rec.update(status='exception',error=repr(ex),traceback=traceback.format_exc())
   results.append(rec)
   if i%50==0:print(f'{i+1}/{len(routes)} GET contracts',flush=True)
   Path(__file__).with_name('get-contract-results.json').write_text(json.dumps({'commit':'d6da1a3d536228582645abb98aea19f3e491f300','database':e.DBNAME,'note':'Sparse valid synthetic masters; execution/shape coverage is not arithmetic, permission-matrix, or business-flow correctness. 404/403/dependency errors require triage. Parameterized routes remain explicit gaps.','results':results},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
 try:asyncio.run(main())
 finally:e.client.close()
