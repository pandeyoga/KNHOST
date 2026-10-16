"""Original scheduler alert calculations on explicit synthetic source records; WA remains off."""
import asyncio,json,traceback
from pathlib import Path
from datetime import datetime,timedelta,timezone
import service_env90 as e
from services import alert_service as a,notification_service as n
RESULTS=[];ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def clear(*names):
 for name in names:await e.db[name].delete_many({})
async def main():
 try:
  await e.setup(template=True);now=datetime.now(timezone.utc);today=now.date()
  await e.db.system_settings.update_one({'scope':'alerts'},{'$set':{'whatsapp.enabled':False}},upsert=True)
  for val,want in [(None,None),('',None),('invalid',None),(42,None),('2026-01-02',True),('2026-01-02T00:00:00Z',True),(datetime(2026,1,2),True),(now,True)]:
   out=a._parse(val);rec('alerts.parse_'+str(val),want,None if out is None else out.tzinfo is not None)
  for fn,coll in [(a.job_ap_due,'vendor_bills'),(a.job_depreciation_due,'fin_fixed_assets'),(a.job_production_stalled,'mfg_work_orders'),(a.job_ops_stalled,'wms_tasks')]:
   await clear(coll,'notifications');rec('alerts.empty_'+fn.__name__,0,(await fn())['created'])
  await clear('vendor_bills','suppliers','payment_terms','notifications')
  await e.db.payment_terms.insert_one({'id':'T1','entity_id':'all','code':'NET30','net_days':30,'status':'active'})
  await e.db.suppliers.insert_one({'id':'S1','payment_term_code':'NET30'})
  def bill(key,days,**extra):return {'id':key,'bill_number':key,'entity_id':'ent_ksc','supplier_id':'S1','supplier_name':'Audit Supplier','status':'posted','bill_date':(today-timedelta(days=30-days)).isoformat(),'grand_total':100,'amount_paid':0,**extra}
  for key,days,status,want in [('future',20,'posted',0),('soon',3,'posted',1),('old',-3,'posted',1),('paid',-3,'paid',0),('draft',-3,'draft',0)]:
   await clear('vendor_bills','notifications');await e.db.vendor_bills.insert_one(bill(key,days,status=status));out=await a.job_ap_due();rec('alerts.ap_'+key,want,out['created'])
   if want:
    rec('alerts.ap_daily_dedup_'+key,0,(await a.job_ap_due())['created'])
  await clear('vendor_bills','notifications');await e.db.vendor_bills.insert_one(bill('TODAY',0));await a.job_ap_due();note=await e.db.notifications.find_one({'type':'ap_due'},{'_id':0})
  rec('alerts.ap_due_calendar_today',True,'HARI INI' in note['title'],note['title'])
  rec('alerts.ap_today_not_overdue','warning',note['severity'])
  await clear('vendor_bills','notifications');await e.db.vendor_bills.insert_one(bill('PARTIAL',-3,amount_paid=70,payments=[{'id':'P1','amount':70}]))
  await a.job_ap_due();note=await e.db.notifications.find_one({'type':'ap_due'},{'_id':0})
  rec('alerts.ap_partial_reports_outstanding',True,'Rp 30' in note['body'],note['body'])
  await clear('fin_fixed_assets','fin_depreciation_entries','notifications')
  await e.db.fin_fixed_assets.insert_one({'id':'FA1','number':'FA1','name':'Asset','entity_id':'ent_ksc','status':'active','monthly_depreciation':100})
  rec('alerts.depreciation_pending',1,(await a.job_depreciation_due())['created']);rec('alerts.depreciation_daily_dedup',0,(await a.job_depreciation_due())['created'])
  await clear('notifications');await e.db.fin_depreciation_entries.insert_one({'asset_id':'FA1','period':a._period_prev_month()})
  rec('alerts.depreciation_done',0,(await a.job_depreciation_due())['created'])
  for key,status,age,short,want in [('recent','draft',1,False,0),('draft_old','draft',10,False,1),('released_old','released',4,False,1),('short','draft',1,True,1)]:
   await clear('mfg_work_orders','notifications');await e.db.mfg_work_orders.insert_one({'id':key,'entity_id':'ent_ksc','wo_number':key,'status':status,'created_at':(now-timedelta(days=age)).isoformat(),'released_at':(now-timedelta(days=age)).isoformat(),'output_name':'Cloth','planned_qty':10,'output_unit':'yard','material_plan':[{'material_product_id':'GREIGE','sufficient':not short}]})
   rec('alerts.production_'+key,want,(await a.job_production_stalled())['created'])
   if want:rec('alerts.production_severity_'+key,'critical' if short else 'warning',(await e.db.notifications.find_one({'type':'production_stalled'}))['severity'])
  def task(key,owner,flow='outbound',age=4):return {'id':key,'entity_id':owner,'warehouse_id':'SHARED-WH','warehouse_name':'Shared Woven','flow_type':flow,'status':'picking','created_at':(now-timedelta(days=age)).isoformat(),'order_number':key}
  await clear('wms_tasks','notifications');await e.db.wms_tasks.insert_many([task('A1','ent_ksc'),task('A2','ent_ksc'),task('B1','ent_ksc','inbound'),task('RECENT','ent_ksc',age=0)])
  out=await a.job_ops_stalled();rec('alerts.ops_group_by_flow',2,out['created']);rec('alerts.ops_recent_excluded',3,out['scanned']);rec('alerts.ops_daily_dedup',0,(await a.job_ops_stalled())['created'])
  foreign=await e.db.business_entities.find_one({'status':'active','id':{'$ne':'ent_ksc'}});assert foreign
  await clear('wms_tasks','notifications');await e.db.wms_tasks.insert_many([task('SO-A','ent_ksc'),task('SO-B',foreign['id'])]);await a.job_ops_stalled()
  notes=await e.db.notifications.find({'type':'ops_stalled'},{'_id':0}).to_list(None)
  rec('alerts.ops_shared_warehouse_separate_owners',2,len(notes))
  rec('alerts.ops_foreign_order_not_in_owner_notice',False,any(x.get('entity_id')=='ent_ksc' and 'SO-B' in x['body'] for x in notes))
  rec('alerts.no_external_outbox',0,await e.db.sys_wa_outbox.count_documents({}))
 except Exception:ERRORS.append(traceback.format_exc())
 finally:
  Path(__file__).with_name('alert-numeric90-results.json').write_text(json.dumps(dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,harness_errors=ERRORS,scope='Original alert generators, explicit synthetic ledger/task fixtures, internal notification records only; no external messaging.'),ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'observations':len(RESULTS),'differences':[r['id'] for r in RESULTS if r['status']!='pass'],'errors':ERRORS}));e.client.close()
if __name__=='__main__':asyncio.run(main())
