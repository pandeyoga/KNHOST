import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
db=e.db;results=[]
def check(n,k,label,actual,expected):
 assert actual==expected,(n,actual,expected)
 results.append(dict(id='W2-RNDLINE-'+n,kind=k,label=label,observed=actual,expected=expected));print(results[-1],flush=True)
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 await db.users.update_one({'id':'U'},{'$set':{'allowed_line_codes':['woven']}})
 await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.rnd':['view','create']}})
 for sid,line in [('W','woven'),('P','printing')]:
  await db.md_samples.insert_one(dict(id=sid,number=sid,entity_id='A',line_code=line,status='draft',title='Synthetic '+line,sample_types=['labdip' if line=='woven' else 'proofing'],rounds=[],participants=[],timeline=[]))
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
  resp=await h.get('/api/rnd/samples');assert resp.status_code==200,resp.text
  check('C01','control','Woven-only actor list excludes printing',[x['id'] for x in resp.json()['items']],['W'])
  resp=await h.get('/api/rnd/samples/P')
  check('F01','defect','Same actor can open printing sample by ID',[resp.status_code,resp.json().get('line_code')],[200,'printing'])
  resp=await h.patch('/api/rnd/samples/P',json={'title':'Edited from woven-only account'})
  check('F02','defect','Same actor can modify printing sample',[resp.status_code,(await db.md_samples.find_one({'id':'P'}))['title']],[200,'Edited from woven-only account'])
 assert not e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('rnd-line-scope-results.json').write_text(json.dumps(dict(database=e.DBNAME,source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),mode='Actual ASGI+indexed synthetic Mongo, same entity two product lines; permitted view/create actions; no external data',results=results),indent=2),encoding='utf-8');e.client.close()
