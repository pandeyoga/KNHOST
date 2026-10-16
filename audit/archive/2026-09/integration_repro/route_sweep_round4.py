"""Unauthenticated route sweep. Not business-flow or authorization-matrix coverage."""
import asyncio,json,re,collections,os
from pathlib import Path
import integration_round4 as env
import httpx
B=Path(__file__).resolve().parent
MODE=os.environ.get('AUDIT_ROUTE_MODE','anonymous')
OUTPUT='route_no_permissions_round4' if MODE=='no_permissions' else 'route_sweep_round4'
schema=env.server.app.openapi();defs=schema.get('components',{}).get('schemas',{})
def sample(s,name='',depth=0):
 if depth>6:return {}
 if '$ref' in s:return sample(defs[s['$ref'].rsplit('/',1)[1]],name,depth+1)
 if 'enum' in s:return s['enum'][0]
 if 'anyOf' in s or 'oneOf' in s:return sample(next((x for x in s.get('anyOf',s.get('oneOf',[])) if x.get('type')!='null'),{}),name,depth+1)
 t=s.get('type')
 if t=='object' or 'properties' in s:return {k:sample(v,k,depth+1) for k,v in s.get('properties',{}).items() if k in s.get('required',[])}
 if t=='array':return [sample(s.get('items',{}),name,depth+1) for _ in range(max(1,s.get('minItems',0)))]
 if t=='boolean':return False
 if t in ('integer','number'):return max(1,s.get('minimum',1),s.get('exclusiveMinimum',0)+1)
 if s.get('format')=='date-time':return '2026-10-05T00:00:00Z'
 if s.get('format')=='date' or name in ('date','date_from','date_to','due_date'):return '2026-10-05'
 if name in ('entity_id','owner_entity_id'):return 'A'
 if name=='doc_type':return 'sales_order'
 if 'phone' in name:return '081234567890'
 if name=='pickup_code':return 'AUDIT123'
 if 'email' in name:return 'audit-missing@example.invalid'
 if 'period' in name or name=='month':return '2026-10'
 if 'year' in name:return '2026'
 return 'AUDIT-NONEXISTENT'
async def main():
 await env.client.admin.command('ping')
 result=[]
 headers={}
 if MODE=='no_permissions':
  await env.seed()
  await env.db.users.update_one({'id':'U'},{'$set':{'role':'audit_no_permissions'}})
  await env.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix':{'audit_no_permissions':{}}}})
  headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=env.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers=headers) as client:
  for route in env.server.app.routes:
   if not getattr(getattr(route,'endpoint',None),'__module__','').startswith('routers.'):continue
   for method in sorted(route.methods or []):
    if MODE=='no_permissions' and route.path=='/api/auth/logout':
     result.append({'method':method,'template':route.path,'status':'SKIP','reason':'avoid invalidating test session'});continue
    op=schema.get('paths',{}).get(route.path,{}).get(method.lower(),{});path=route.path;params={}
    for p in op.get('parameters',[]):
     if p['in']=='path':path=path.replace('{'+p['name']+'}',str(sample(p.get('schema',{}),p['name'])))
     if p['in']=='query' and p.get('required'):params[p['name']]=sample(p.get('schema',{}),p['name'])
    path=re.sub(r'\{[^}]+\}','AUDIT-NONEXISTENT',path)
    if route.path=='/api/ai/export.xlsx':params['ids']='AUDIT-NONEXISTENT'
    kw={'params':params};content=op.get('requestBody',{}).get('content',{})
    if 'application/json' in content:kw['json']=sample(content['application/json'].get('schema',{}))
    elif 'multipart/form-data' in content:kw['files']={'file':('audit.txt',b'audit','text/plain')}
    try:
     res=await asyncio.wait_for(client.request(method,path,**kw),timeout=5)
     row={'method':method,'template':route.path,'status':res.status_code,'endpoint':route.endpoint.__module__+'.'+route.endpoint.__name__}
     if res.status_code not in [401,403]:row['response_excerpt']=res.text[:500]
    except Exception as exc:row={'method':method,'template':route.path,'status':'ERROR','exception':type(exc).__name__+':'+str(exc)[:160]}
    result.append(row)
    if len(result)%100==0:print('routes',len(result),dict(collections.Counter(str(x['status']) for x in result)),flush=True)
    if len(result)%25==0:(B/(OUTPUT+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 (B/(OUTPUT+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('DONE',len(result),dict(collections.Counter(str(x['status']) for x in result)),flush=True)
if __name__=='__main__':
 try:asyncio.run(main())
 finally:env.client.close()
