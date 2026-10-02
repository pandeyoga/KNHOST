"""Additional real Mongo characterization: isolation, period decisions, inspection SSOT."""
import asyncio,json
import integration_round4 as env
from services import period_unlock_service as pus,gl_service as gl,inspection_service as ins,config_service as cfg
db=env.db

async def main():
 await env.seed()
 await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.entity':['update'],'matrix.finance.period':['unlock']}})
 async with env.httpx.AsyncClient(transport=env.httpx.ASGITransport(app=env.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as c:
  res=await c.get('/api/settings/effective',params={'entity_id':'B'})
  env.check('I5-C01',{'read_foreign_settings':res.status_code},res.status_code==403,'control')
  before=await cfg.get_effective_settings('B')
  res=await c.put('/api/settings',json={'scope':'B','finance':{'base_currency':'USD'}})
  after=await cfg.get_effective_settings('B')
  env.check('I5-SEC01',{'status':res.status_code,'actor_allowed':['A'],'target_scope':'B','currency_before':before['finance']['base_currency'],'currency_after':after['finance']['base_currency']},res.status_code==200 and after['finance']['base_currency']=='USD')
  await db.period_unlock_requests.insert_one({'id':'FOREIGN','entity_id':'B','status':'pending','requested_by_id':'OTHER','reason':'Synthetic B correction','start_date':'2026-09-01','end_date':'2026-09-30','period_key':'2026-09'})
  res=await c.post('/api/finance/period-unlocks',json={'entity_id':'B','period_type':'month','period_key':'2026-09','reason':'Synthetic foreign request'})
  env.check('I5-C03',{'create_foreign_unlock':res.status_code},res.status_code==403,'control')
  res=await c.get('/api/finance/period-unlocks',params={'entity_id':'B'})
  env.check('I5-SEC02',{'status':res.status_code,'foreign_requests':len(res.json())},res.status_code==200 and any(r['id']=='FOREIGN' for r in res.json()))
  res=await c.post('/api/finance/period-unlocks/FOREIGN/approve')
  env.check('I5-SEC03',{'status':res.status_code,'approved_entity':res.json().get('entity_id'),'decision':res.json().get('status')},res.status_code==200 and res.json().get('status')=='approved' and res.json().get('entity_id')=='B')
 await db.period_closings.insert_one({'id':'CLOSE','entity_id':'A','period_type':'month','period_key':'2026-09','start_date':'2026-09-01','end_date':'2026-09-30','status':'closed','closed_at':env.datetime.now(env.timezone.utc).isoformat()})
 rec=await pus.request_unlock(period_type='month',period_key='2026-09',entity_id='A',reason='Synthetic audit correction',actor={'id':'REQUESTER','name':'Requester'})
 try:await pus.approve_request(rec['id'],{'id':'REQUESTER','name':'Requester'})
 except ValueError:denied=True
 else:denied=False
 env.check('I5-C02',{'self_approval_rejected':denied},denied,'control')
 # Pause only the approval task AFTER the real database returns its pending snapshot.
 # Rejection then completes against real Mongo before approval resumes its stale write.
 real=pus.db;ready=asyncio.Event();resume=asyncio.Event()
 class Collection:
  def __getattr__(self,n):return getattr(real[pus.COLL],n)
  async def find_one(self,*a,**k):
   value=await real[pus.COLL].find_one(*a,**k)
   if asyncio.current_task().get_name()=='delayed-approval' and value and value.get('status')=='pending':
    ready.set();await resume.wait()
   return value
 class Database:
  def __getattr__(self,n):return getattr(real,n)
  def __getitem__(self,n):return Collection() if n==pus.COLL else real[n]
 pus.db=Database()
 try:
  pending=asyncio.create_task(pus.approve_request(rec['id'],{'id':'APPROVER','name':'Approver'}),name='delayed-approval')
  await asyncio.wait_for(ready.wait(),5)
  rejected=await pus.reject_request(rec['id'],{'id':'REJECTOR','name':'Rejector'},'Correction not authorized')
  resume.set();approved=await pending
 finally:pus.db=real
 guard=await gl.enforce_closed_period_guard('A','2026-09-15')
 env.check('I5-FN01',{'rejection_returned':rejected['status'],'final_status':approved['status'],'retains_rejected_by':approved.get('rejected_by'),'closed_period_guard_accepts_unlock':bool(guard)},rejected['status']=='rejected' and approved['status']=='approved' and bool(guard))
 await db.sales_returns.insert_one({'id':'RET','entity_id':'A','status':'inspecting'})
 await db[ins.COLL].insert_one({'id':'INS','entity_id':'A','status':'assigned','assigned_to':'U','ref_doc_type':'sales_return','ref_doc_id':'RET','lines':[{'id':'L1','inspected_at':'2026-09-29T00:00:00Z'},{'id':'L2','inspected_at':''}],'history':[]})
 decision=next(k for k in ins.DECISIONS if k!='tolak')
 finished=await ins.finish('INS',decision,'Synthetic audit decision',{'id':'U','name':'Inspector'})
 env.check('I5-WM01',{'status':finished['status'],'inspected':finished['summary']['inspected'],'total_lines':finished['summary']['lines'],'decision':finished['decision']},finished['status']=='done' and finished['summary']['inspected']==1 and finished['summary']['lines']==2,'policy_gap')
 reopened=await ins.reopen('INS','Hasil perlu diperiksa kembali karena data salah',{'id':'U','name':'Inspector'})
 ret=await db.sales_returns.find_one({'id':'RET'})
 env.check('I5-WM02',{'inspection_status':reopened['status'],'inspection_finished_at':reopened.get('finished_at'),'return_inspect_done_at':ret.get('inspect_done_at')},reopened['status']=='in_progress' and not reopened.get('finished_at') and bool(ret.get('inspect_done_at')))

if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  (env.B/'integration_round5.json').write_text(json.dumps({'source_commit':'d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467','database':env.DBNAME,'mode':'Original services + actual local Mongo; ASGI for settings; deterministic read barrier for decision race','results':env.RESULTS},indent=2),encoding='utf-8')
  env.client.close()
