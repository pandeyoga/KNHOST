"""Negative resource contracts on original APIs. This is NOT positive-flow verification.

Schema-valid minimal bodies are derived from original OpenAPI. Every resource-ID
path uses a unique non-existent audit ID. Responses and handler entry are recorded,
not automatically relabelled confirmed defects or full workflow coverage.
"""
import asyncio,json,re,traceback,collections
from datetime import datetime,timezone,timedelta
from pathlib import Path
import wave2_env as e
ROWS=[];ERRORS=[];ABSENT='__AUDIT90_NONEXISTENT_RESOURCE__'
def resolve(s,definitions):
 while '$ref' in s:s=definitions[s['$ref'].split('/')[-1]]
 if 'allOf' in s:return resolve(s['allOf'][0],definitions)
 if 'anyOf' in s:return resolve(next((v for v in s['anyOf'] if v.get('type')!='null'),s['anyOf'][0]),definitions)
 return s
def value(schema,definitions,name='',depth=0):
 s=resolve(schema,definitions)
 if depth>8:return None
 if 'const' in s:return s['const']
 if s.get('enum'):return s['enum'][0]
 typ=s.get('type')
 if typ=='object' or 'properties' in s:
  props=s.get('properties',{});required=set(s.get('required',[]))
  keys=required|({'reason','note','notes'}&set(props))
  return {k:value(props[k],definitions,k,depth+1) for k in keys if k in props}
 if typ=='array':return [value(s.get('items',{}),definitions,name,depth+1) for _ in range(max(1,int(s.get('minItems',0))))]
 if typ=='boolean':return True
 if typ in ('number','integer'):
  n=max(1,s.get('minimum',1),s.get('exclusiveMinimum',0)+1)
  if s.get('maximum') is not None:n=min(n,s['maximum'])
  return int(n) if typ=='integer' else float(n)
 if s.get('format')=='binary':return b'\x89PNG\r\n\x1a\nAUDIT90'
 if s.get('format')=='date':return '2026-10-06'
 if s.get('format')=='date-time':return '2026-10-06T05:00:00Z'
 if s.get('format')=='email':return 'audit@example.invalid'
 if name.endswith('_date') or name in ('date','valid_from','valid_until','period_start','period_end'):return '2026-10-06'
 if name in ('period','month'):return '2026-10'
 if name=='entity_id':return 'ent_ksc'
 if name.endswith('_id') or name=='id':return ABSENT
 if name=='hex':return '#123456'
 if name in ('reason','note','notes','description'):return 'Audit: absent resource contract verification'
 if name in ('quantity','qty','amount','price'):return '1'
 return 'AUDIT90'
async def setup():
 assert await e.db.users.count_documents({})==0
 template=e.client['knhost_audit_native90_template']
 assert await template.users.count_documents({})>0
 for name in await template.list_collection_names():
  docs=await template[name].find({}).to_list(None)
  if docs:await e.db[name].insert_many(docs)
 await e.db.users.insert_one({'id':'NEG90','name':'Audit Negative Contracts','email':'neg90@example.invalid','role':'admin','status':'active','home_entity_id':'ent_ksc','allowed_entity_ids':['ent_ksc']})
 await e.db.sessions.insert_one({'token':'audit-neg90','user_id':'NEG90','expires_at':datetime.now(timezone.utc)+timedelta(hours=2)})
async def main():
 try:
  await setup();spec=e.server.app.openapi();defs=spec.get('components',{}).get('schemas',{})
  transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False)
  async with e.httpx.AsyncClient(transport=transport,base_url='http://audit.local',headers={'Authorization':'Bearer audit-neg90','X-Entity-Id':'ent_ksc'},timeout=20) as h:
   for path,operations in spec['paths'].items():
    names=re.findall(r'\{([^{}]+)\}',path)
    if not names or not any(n=='id' or n.endswith('_id') for n in names):continue
    for method,op in operations.items():
     if method not in ('post','put','patch','delete'):continue
     params=op.get('parameters',[]);url=path;query={};data=None;kwargs={}
     for param in params:
      name=param['name'];s=resolve(param.get('schema',{}),defs)
      if param['in']=='path':url=url.replace('{'+name+'}',str(1 if s.get('type') in ('number','integer') else ABSENT))
      elif param['in']=='query' and param.get('required'):query[name]=value(s,defs,name)
     content=op.get('requestBody',{}).get('content',{})
     if content:
      ctype=next(iter(content));schema=content[ctype].get('schema',{});data=value(schema,defs)
      if ctype=='application/json':kwargs['json']=data
      elif ctype=='multipart/form-data':
       schema=resolve(schema,defs);props=schema.get('properties',{});files={};fields={}
       for name,v in (data or {}).items():
        if resolve(props.get(name,{}),defs).get('format')=='binary':files[name]=('audit.png',v,'image/png')
        else:fields[name]=str(v)
       kwargs.update(files=files,data=fields)
      else:
       ROWS.append(dict(method=method,path=path,classification='unexercised_content_type',content_type=ctype));continue
     try:
      r=await h.request(method,url,params=query,**kwargs)
      detail=r.json() if r.headers.get('content-type','').startswith('application/json') else r.text[:700]
      ROWS.append(dict(method=method,path=path,url=url,status=r.status_code,
        classification='negative_guard_response' if 400<=r.status_code<500 else 'response_requires_contract_adjudication',
        input=data if not kwargs.get('files') else 'Local synthetic PNG multipart',response=detail))
     except Exception as ex:ROWS.append(dict(method=method,path=path,classification='harness_exception',error=repr(ex)))
     if len(ROWS)%50==0:print('ABSENT_RESOURCE_CONTRACTS',len(ROWS),flush=True)
 except Exception:ERRORS.append(traceback.format_exc())
 finally:
  result=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,
    contract='Negative resource IDs only; schema-generated bodies can still fail business validation. A 4xx is a guard observation, NOT all-flow correctness. 2xx/5xx require manual adjudication.',
    counts=dict(collections.Counter(str(r.get('status',r['classification'])) for r in ROWS)),results=ROWS,harness_errors=ERRORS)
  Path(__file__).with_name('missing-resource-contract90-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
  print(json.dumps({'requests':len(ROWS),'counts':result['counts'],'errors':ERRORS},ensure_ascii=False));e.client.close()
if __name__=='__main__':asyncio.run(main())
