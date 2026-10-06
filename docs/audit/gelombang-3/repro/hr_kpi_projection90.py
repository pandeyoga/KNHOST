"""Original KPI HTTP producer -> persisted rows -> self-service aggregate.

Zero weight is accepted by current request schema and entered by the UI. Independent
weighted mean excludes it; target/actual scores are checked against [0,150] contract.
"""
import asyncio,json,traceback
from pathlib import Path
import wave2_env as e
from services import hr_kpi_service as k
RESULTS=[];ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def main():
 try:
  await e.seed()
  await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.hr':['view','manage_attendance']}})
  await e.db.hr_employees.update_one({'id':'EMP'},{'$set':{'user_id':'U','name':'Synthetic MD'}})
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
   async def req(method,path,body=None):return await h.request(method,'/api/hr/kpi'+path,json=body)
   async def add(metric,actual,weight=1,period='2026-10',**kw):
    r=await req('POST','',{'employee_id':'EMP','period':period,'metric':metric,'target':100,'actual':actual,'weight':weight,**kw});rec('kpi.create_'+metric,200,r.status_code);assert r.status_code==200,r.text;return r.json()
   a=await add('regular A',20,1);b=await add('regular B',80,3)
   me=await req('GET','/me');rec('kpi.weighted_control',65,me.json()['latest_score'])
   c=await add('excluded zero',150,0);rec('kpi.zero_weight_retained',0,c['weight'])
   me=await req('GET','/me');rec('kpi.zero_weight_aggregate',65,me.json()['latest_score'])
   r=await req('PUT','/'+c['id'],{'weight':0});rec('kpi.patch_zero_accepted',200,r.status_code);rec('kpi.patch_zero_persisted',0,r.json()['weight'])
   me=await req('GET','/me');rec('kpi.zero_weight_projection_after_patch',65,me.json()['latest_score'])
   for key,patch in [('auto_recompute',{'actual':50}),('explicit_score',{'score':200}),('reset_auto',{'score':None}),('empty',{})]:
    r=await req('PUT','/'+a['id'],patch);rec('kpi.patch_'+key,400 if key=='empty' else 200,r.status_code)
    if key=='auto_recompute':rec('kpi.recompute_score',50,r.json()['score'])
    if key=='explicit_score':rec('kpi.manual_cap',150,r.json()['score'])
    if key=='reset_auto':rec('kpi.manual_reset',50,r.json()['score'])
   n=await add('negative actual',-10,1,period='2026-09');rec('kpi.auto_score_lower_bound',0,n['score'],"Source compute_score docstring says 0–150. Metric freeform can have negative actual; public producer accepts it.")
   x=await add('period invalid',50,1,period='2026-99');rec('kpi.calendar_period_rejected',True,False,'Public producer accepted invalid month; schema period has no calendar validator.')
   me=await req('GET','/me');rec('kpi.latest_period_real_calendar','2026-10',me.json()['latest_period'])
   r=await req('PUT','/'+a['id'],{'metric':'','period':'bad'});rec('kpi.patch_empty_metric_bad_period_rejected',True,r.status_code in (400,422),str(r.status_code))
   for body in [{'employee_id':'','period':'2026-10','metric':'valid'},{'employee_id':'missing','period':'2026-10','metric':'valid'},{'employee_id':'EMP','period':'x','metric':'valid'},{'employee_id':'EMP','period':'2026-10','metric':''},{'employee_id':'EMP','period':'2026-10','metric':'valid','weight':-1}]:
    r=await req('POST','',body);rec('kpi.create_guard_'+str(len(RESULTS)),True,r.status_code in (400,404,422))
   r=await h.get('/api/hr/kpi',params={'employee_id':'EMP','period':'2026-10'});rec('kpi.list_period_filter',2,len(r.json()))
   await req('DELETE','/'+c['id']);rec('kpi.delete_persisted',0,await e.db.hr_kpi.count_documents({'id':c['id']}))
   rec('kpi.deleted_repeat',404,(await req('DELETE','/'+c['id'])).status_code)
   for target,actual,score,want in [(0,20,None,0),(-10,20,None,0),(100,200,None,150),(100,20,-1,0),(100,20,'bad',20),('bad',20,None,0)]:rec('kpi.numeric_guard_'+str((target,actual,score)),want,k.compute_score(target,actual,score))
 except Exception:ERRORS.append(traceback.format_exc())
 finally:
  out=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,harness_errors=ERRORS,scope=__doc__)
  Path(__file__).with_name('hr-kpi-projection90-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(observations=len(RESULTS),differences=[x['id'] for x in RESULTS if x['status']!='pass'],errors=ERRORS)));e.client.close()
if __name__=='__main__':asyncio.run(main())
