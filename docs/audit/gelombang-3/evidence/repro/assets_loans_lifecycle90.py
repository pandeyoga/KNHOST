"""Real public asset/loan lifecycles with arithmetic, retry and scope controls."""
import asyncio,json,traceback
from pathlib import Path
import wave2_env as e
from services import gl_service as gl,interco_loan_service as loans

RESULTS=[];CONTEXT={};ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def req(h,path,body=None,method='POST'):
 return await h.request(method,'/api/'+path,json=body) if body is not None else await h.request(method,'/api/'+path)
async def ok(h,path,body=None,method='POST'):
 r=await req(h,path,body,method)
 assert r.status_code==200,(path,r.status_code,r.text)
 return r.json()
async def entries(kind,source=None):
 q={'source_type':kind,'status':'posted'}
 if source:q['source_id']=source
 return await e.db.journal_entries.find(q,{'_id':0}).to_list(None)
async def asset(h,key):
 return await ok(h,'fixed-assets',{'name':'Local audit '+key,'entity_id':'A',
   'acquisition_cost':300,'acquisition_date':'2025-01-01','useful_life_months':3,'salvage_value':0})
async def depreciation(h,a,period):
 return await req(h,'fixed-assets/run-depreciation',{'asset_id':a['id'],'period':period})
async def original_asset_state(a):
 return dict(asset=await e.db.fin_fixed_assets.find_one({'id':a['id']},{'_id':0}),
  entries=await e.db.fin_depreciation_entries.find({'asset_id':a['id']},{'_id':0}).to_list(None),
  journals=await e.db.journal_entries.find({'source_type':'depreciation','status':'posted'},{'_id':0}).to_list(None))
async def asset_normal(h):
 a=await asset(h,'NORMAL')
 rec('FA90-normal-capitalized',1,len(await entries('fixed_asset_acquisition',a['id'])))
 rec('FA90-monthly-straight-line',100,a['monthly_depreciation'])
 await ok(h,'fixed-assets/'+a['id'],{'notes':'Local trace'},method='PATCH')
 rec('FA90-capitalized-price-edit',400,(await req(h,'fixed-assets/'+a['id'],{'acquisition_cost':400},'PATCH')).status_code)
 r=await depreciation(h,a,'2025-01');assert r.status_code==200,r.text
 rec('FA90-normal-first-month',100,r.json()['total_amount'])
 r=await depreciation(h,a,'2025-01')
 rec('FA90-repeat-same-month',0,r.json()['posted'])
 d=await ok(h,'fixed-assets/'+a['id'],method='GET')
 rec('FA90-normal-book-value',200,d['book_value'])
 rec('FA90-preview-schedule-total',300,sum(x['amount'] for x in d['schedule']))
 d=await ok(h,'fixed-assets/'+a['id']+'/dispose',{'proceeds':250,'date':'2025-02-01','note':'Synthetic sale'})
 rec('FA90-disposal-gain',50,d['disposal']['gain_loss'])
 rec('FA90-disposal-state','disposed',d['status'])
 rec('FA90-repeat-disposal',400,(await req(h,'fixed-assets/'+a['id']+'/dispose',{'proceeds':250})).status_code)
 CONTEXT['asset-normal']=await original_asset_state(a)
async def asset_failure(h):
 a=await asset(h,'RETRY');original=gl.post_depreciation
 async def fail(**kw):
  if kw['asset_id']==a['id']:raise RuntimeError('AUDIT local injected journal outage after CAS')
  return await original(**kw)
 gl.post_depreciation=fail
 try:first=await depreciation(h,a,'2025-01')
 finally:gl.post_depreciation=original
 rec('FA90-failed-attempt-status-control',500,first.status_code)
 retry=await depreciation(h,a,'2025-01');assert retry.status_code==200,retry.text
 rec('FA90-failure-retry-posted',1,retry.json()['posted'],
   'A failed journal must not consume the asset+period permanently; retry should complete exactly once.')
 s=await original_asset_state(a)
 rec('FA90-failure-retry-accumulated',100,s['asset']['accumulated_depreciation'])
 rec('FA90-failure-retry-entry-count',1,len(s['entries']))
 CONTEXT['asset-failure']=dict(first_http=first.status_code,retry=retry.json(),state=s)
async def asset_race(h):
 a=await asset(h,'TWO-PERIODS');original=gl.post_depreciation;arrived=0;ready=asyncio.Event()
 async def barrier(**kw):
  nonlocal arrived
  if kw['asset_id']==a['id']:
   arrived+=1
   if arrived==2:ready.set()
   await asyncio.wait_for(ready.wait(),10)
  return await original(**kw)
 gl.post_depreciation=barrier
 try:rs=await asyncio.gather(depreciation(h,a,'2025-01'),depreciation(h,a,'2025-02'))
 finally:gl.post_depreciation=original
 rec('FA90-parallel-months-http-control',[200,200],sorted(r.status_code for r in rs))
 s=await original_asset_state(a)
 rec('FA90-parallel-months-entry-control',2,len(s['entries']))
 rec('FA90-parallel-months-accumulated',200,s['asset']['accumulated_depreciation'])
 rec('FA90-parallel-months-book-value',100,s['asset']['book_value'])
 rec('FA90-parallel-months-count',2,s['asset']['depreciated_months'])
 CONTEXT['asset-race']=dict(responses=[r.json() for r in rs],state=s)
async def loan_normal(h):
 d=await ok(h,'interco/loans',{'lender_entity_id':'A','borrower_entity_id':'B','principal':100,'purpose':'Local audit working capital'})
 lid=d['lender']['id'];pid=d['pair_id']
 d=await ok(h,'interco/loans/'+lid+'/disburse')
 rec('ICL90-disburse-both-sides',['disbursed','disbursed'],[d['lender']['status'],d['borrower']['status']])
 rec('ICL90-disburse-twin-cash',2,await e.db.cash_transactions.count_documents({'ref_type':'interco_loan','ref_id':pid}))
 rec('ICL90-disburse-twin-journal',2,len(await entries('interco_loan')))
 d=await ok(h,'interco/loans/'+lid+'/repay',{'amount':40,'note':'First installment'})
 rec('ICL90-first-outstanding',[60,60],[d['lender']['outstanding'],d['borrower']['outstanding']])
 rec('ICL90-overpayment-rejected',400,(await req(h,'interco/loans/'+lid+'/repay',{'amount':61})).status_code)
 d=await ok(h,'interco/loans/'+lid+'/repay',{'amount':60,'note':'Final installment'})
 rec('ICL90-final-outstanding',[0,0],[d['lender']['outstanding'],d['borrower']['outstanding']])
 rec('ICL90-final-status','repaid',d['lender']['status'])
 rec('ICL90-final-elimination-cleared',0,await e.db.intercompany_eliminations.count_documents({'source_non_trade_key':'loan:'+pid}))
 CONTEXT['loan-normal']=d
 d=await ok(h,'interco/loans',{'lender_entity_id':'A','borrower_entity_id':'B','principal':50,'purpose':'Cancelled synthetic request'})
 d=await ok(h,'interco/loans/'+d['lender']['id']+'/cancel',{'reason':'No longer needed'})
 rec('ICL90-cancel-draft','cancelled',d['lender']['status'])
async def loan_foreign_scope(h):
 await e.db.business_entities.insert_one({'id':'C','short_name':'C','legal_name':'Synthetic C','status':'active','doc_prefix':'C'})
 actor=await e.db.users.find_one({'id':'U'},{'_id':0})
 d=await loans.create({'lender_entity_id':'B','borrower_entity_id':'C','principal':50,'purpose':'Other entity synthetic loan'},actor)
 lid=d['lender']['id']
 await loans.disburse(lid,actor)
 draft=await loans.create({'lender_entity_id':'B','borrower_entity_id':'C','principal':50,'purpose':'Other entity cancellation fixture'},actor)
 await e.db.users.update_one({'id':'U'},{'$set':{'role':'finance','allowed_entity_ids':['A'],'home_entity_id':'A'}})
 await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.interco':['view','create','approve','settle','cancel']}})
 denied=await req(h,'interco/loans/'+lid,method='GET')
 rec('ICL90-foreign-read-denied-control',True,denied.status_code in (403,404),
  'Outside-scope resources may be hidden with404 or rejected with403; either is a valid denial.')
 r=await req(h,'interco/loans/'+lid+'/repay',{'amount':10,'note':'Synthetic foreign-scope control'})
 rec('ICL90-foreign-repayment-denied',403,r.status_code,
  'Finance restricted to A is denied GET for B/C. Module settle permission must not authorize a B/C repayment. Manager is intentionally cross-entity and is not used for this scope test.')
 persisted=await e.db.interco_loans.find_one({'id':lid},{'_id':0})
 rec('ICL90-foreign-repayment-outstanding',50,persisted['outstanding'])
 rec('ICL90-foreign-repayment-no-cash',0,await e.db.cash_transactions.count_documents({'ref_type':'interco_loan_repayment','ref_id':{'$regex':'^'+d['pair_id']+':'}}))
 cancel=await req(h,'interco/loans/'+draft['lender']['id']+'/cancel',{'reason':'Synthetic foreign-scope control'})
 rec('ICL90-foreign-cancellation-denied',403,cancel.status_code)
 CONTEXT['loan-foreign']=dict(get_http=denied.status_code,post_http=r.status_code,
   response=r.json(),persisted=persisted,cancel_http=cancel.status_code,
   cash=await e.db.cash_transactions.find({'ref_id':{'$regex':'^'+d['pair_id']}},{'_id':0}).to_list(None))
async def main():
 await e.seed();await e.db.users.update_one({'id':'U'},{'$set':{'role':'admin','allowed_entity_ids':['A','B']}})
 await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{
   'fixed_asset':['view','create','update','run','dispose','transfer'],
   'interco':['view','create','approve','settle','cancel'],'interco_finance':['view']}}})
 await gl.seed_default_coa()
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),
  base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
  for fn in [asset_normal,asset_failure,asset_race,loan_normal,loan_foreign_scope]:
   try:await fn(h)
   except Exception as ex:ERRORS.append(dict(group=fn.__name__,error=repr(ex),traceback=traceback.format_exc()))
 out=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,
  observations=RESULTS,context=CONTEXT,harness_errors=ERRORS,
  scope='Original ASGI producers with real local Mongo. Boundary injection does not alter business logic. No deployment or live funds.')
 Path(__file__).with_name('assets-loans-lifecycle90-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 print(json.dumps(dict(observations=len(RESULTS),differences=[x for x in RESULTS if x['status']!='pass'],errors=ERRORS),ensure_ascii=False),flush=True)
 e.client.close()
asyncio.run(main())
