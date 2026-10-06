import asyncio,json,traceback
from datetime import datetime,date,timezone,timedelta
from pathlib import Path
import wave2_env as e
from entity_scope import EntityContext
from services import sales_force_service as sf,hr_analytics_service as hr,wms_health_service as wh,marketing_ext as mx,roll_service as rolls,analytics_engine as ae,analytics_time as at,analytics_snapshots as snaps,rnd_kpi_service as rnd
db=e.db;results=[]
def rec(id,expected,actual,note=''):
 results.append({'id':id,'expected':expected,'actual':actual,'status':'pass' if expected==actual else 'observed_difference','note':note});print(json.dumps(results[-1],ensure_ascii=False),flush=True)
async def case(id,fn):
 try:await fn()
 except Exception as ex:results.append({'id':id,'status':'harness_error','error':repr(ex),'traceback':traceback.format_exc()});print(id,repr(ex),flush=True)
async def main():
 await e.seed();user={'id':'U','role':'admin'};ctx=EntityContext(user,'A',['A','B']);allctx=EntityContext(user,'A',['A','B'],True)
 await db.users.insert_many([{'id':'S','name':'Synthetic Sales','role':'sales','status':'active','home_entity_id':'A','allowed_entity_ids':['A','B']},{'id':'OTHER','name':'Other Sales','role':'sales','status':'active','home_entity_id':'B','allowed_entity_ids':['B']}])
 await db.users.update_one({'id':'U'},{'$set':{'role':'admin','allowed_entity_ids':['A','B']}})
 now=datetime.now(timezone.utc);stamp=now.isoformat();period=now.strftime('%Y-%m')
 await db.warehouses.insert_one({'id':'WH','name':'Audit warehouse','sharing_mode':'shared','status':'active'})
 async def commission_scope():
  await db.products.insert_one({'id':'P','sku':'P','name':'P','category':'woven','base_unit':'meter','harga_pokok':10})
  await db.customers.insert_many([{'id':'CA','name':'CA','entity_id':'A','assigned_sales_id':'S','payment_profile':{'method':'tempo'}},{'id':'CB','name':'CB','entity_id':'B','assigned_sales_id':'OTHER','payment_profile':{'method':'tempo'}}])
  await db.sales_orders.insert_one({'id':'BTEAM','entity_id':'B','customer_id':'CB','status':'shipped','sales_team':[{'sales_id':'S','role':'pic','split_pct':100}],'grand_total':900,'total_amount':900,'created_at':stamp,'payments':[{'amount':900,'created_at':stamp}],'paid_total':900,'items':[{'product_id':'P','sku':'P','category':'woven','quantity':9,'base_quantity':9,'price':100,'line_total':900,'unit_cost':10}]})
  await db.incentive_rates.insert_one({'id':'IR','entity_id':'A','status':'active','category':'woven','per_unit_amount':1,'margin_cap_pct':0})
  r=await sf._compute_commission_per_sku('S',period,'A',{'commission':{'default_margin_cap_pct':0}})
  rec('D4-SALES-03-commission-entity',{'commission':0,'collected_basis':0},{'commission':r['total_incentive'],'collected_basis':r['kpi']['total_collected']})
 await case('commission',commission_scope)
 async def hr_combined_payroll():
  await db.hr_payroll_runs.insert_many([{'id':'PA','entity_id':'A','period':period,'status':'posted','totals':{'gross':100,'net':90,'employees':1}},{'id':'PB','entity_id':'B','period':period,'status':'posted','totals':{'gross':200,'net':180,'employees':2}}])
  r=await hr.hr_summary(allctx,'all',period)
  rec('D4-HR-01-multi-run-trend',300,r['payroll_trend'][-1]['gross'])
  rec('D4-HR-01-multi-run-kpi',300,r['payroll']['gross'])
 await case('hr_payroll',hr_combined_payroll)
 async def hr_turnover():
  await db.hr_employees.insert_one({'id':'LEFT','name':'LEFT','entity_id':'A','status':'inactive','termination_date':'2026-07-31','updated_at':stamp,'join_date':'2025-01-01'})
  r=await hr.hr_summary(ctx,'A',period);rec('D4-HR-02-separation-date',0,r['turnover']['separations'],'Updating a former employee now must not count their departure as this month.')
 await case('hr_turnover',hr_turnover)
 async def wib_counter():
  class Frozen(datetime):
   @classmethod
   def now(cls,tz=None):return datetime(2026,9,30,18,tzinfo=timezone.utc).astimezone(tz) if tz else datetime(2026,9,30,18)
  original=wh.datetime;wh.datetime=Frozen
  await db.rfid_reads.insert_many([{'id':'PREV-WIB','warehouse_id':'WH','owner_entity_id':'A','result':'red','read_type':'gate_out','timestamp':'2026-09-30T16:00:00+00:00'},{'id':'TODAY-WIB','warehouse_id':'WH','owner_entity_id':'A','result':'red','read_type':'gate_out','timestamp':'2026-09-30T17:30:00+00:00'}])
  try:r=await wh.health_dashboard(['A'])
  finally:wh.datetime=original
  rec('D4-WMS-01-wib-day',1,r['totals']['red_reads_today'],'Freeze now=01 Oct 01:00 WIB; 30 Sept 23:00 WIB belongs yesterday.')
  from services import home_service as home
  previous_home_datetime=home.datetime;home.datetime=Frozen
  try:rec('D4-DATE-01-home-default',{'month':'2026-10','day':'2026-10-01'},{'month':home._current_month(),'day':home._today_prefix()})
  finally:home.datetime=previous_home_datetime
  rec('D4-DATE-01-month-inclusion',True,sf._in_period('2026-09-30T18:00:00+00:00','2026-10'),'Normal UTC timestamp is 01 Oct 01:00 WIB; selected October must include it.')
  rec('D4-DATE-01-prior-month',False,sf._in_period('2026-09-30T18:00:00+00:00','2026-09'))
  rec('D4-DATE-01-year-inclusion',True,sf._in_period('2026-12-31T18:00:00+00:00','2027'),'01 Jan 2027 01:00 WIB belongs business year2027.')
 await case('wib_counter',wib_counter)
 async def wms_cc_state():
  await db.rfid_cycle_counts.insert_many([{'id':'CCOK','warehouse_id':'WH','status':'approved','cc_number':'CCOK','created_at':'2026-09-01T00:00:00+00:00','accuracy_pct':95,'missing_count':1},{'id':'CCOPEN','warehouse_id':'WH','status':'open','cc_number':'CCOPEN','created_at':'2026-09-30T00:00:00+00:00'}])
  r=await wh.health_dashboard(['A']);rec('D4-WMS-02-last-measured-cc','CCOK',r['warehouses'][0]['last_cc']['cc_number'],'New unfinished count must not erase last measured accuracy.')
 await case('wms_cc_state',wms_cc_state)
 async def partial_cut_stock():
  roll=await rolls.create_inbound_roll('P','WH','A',10,unit_cost=10)
  await rolls._reserve_length(roll,3,'PARTSO')
  sc=await ae.build_scope(user,ctx);p=at.period_from_args({'date_from':now.date().isoformat(),'date_to':now.date().isoformat(),'type':'custom'})
  r=await ae._src_stock(['stock_available_qty','stock_reserved_qty'],['product'],None,p,[{'dimension':'product','values':['P']}],sc,[],False)
  rec('D4-AI-05-partial-cut-live',{'stock_available_qty':7,'stock_reserved_qty':3},r.get(('P',)))
  await snaps.snapshot_stock(now.date().isoformat());doc=await db.fact_stock_daily.find_one({'product_id':'P'})
  rec('D4-AI-05-partial-cut-snapshot',{'avail':7,'reserved':3},{'avail':doc['avail'],'reserved':doc['reserved']})
 await case('partial_cut_stock',partial_cut_stock)
 async def marketing_allocation():
  await db.mkt_posts.insert_one({'id':'MP','title':'One aggregate post','entity_id':'A','status':'published','publish_at':period+'-01T09:00','published_at':period+'-01T02:00:00+00:00','platforms':['instagram','tiktok'],'accounts':[{'id':'MI','platform':'instagram','handle':'i','entity_id':'A'},{'id':'MT','platform':'tiktok','handle':'t','entity_id':'A'}],'metrics':{'reach':100,'likes':10},'pic_name':'Synthetic'})
  r=await mx.dashboard({'entity_id':'A'},period)
  rec('D4-MKT-01-attribution-conservation',{'total_reach':100,'platform_reach_sum':100,'account_reach_sum':100},{'total_reach':r['kpi']['reach'],'platform_reach_sum':sum(x['reach'] for x in r['by_platform'].values()),'account_reach_sum':sum(x['reach'] for x in r['by_account'].values())},'No per-platform/account measurements stored. The UI presents the whole aggregate independently for each platform/account.')
 await case('marketing_allocation',marketing_allocation)
 async def rnd_identity():
  for uid in ['U1','U2']:await db.users.insert_one({'id':uid,'name':'Same Display Name','role':'md','status':'active','home_entity_id':'A'})
  await db.md_samples.insert_many([{'id':'SAMPLE'+uid,'entity_id':'A','status':'decided','created_by':'Same Display Name','rounds':[{'id':'ROUND'+uid,'status':'assessed','result':'acc','performed_by':'Same Display Name','performed_by_user_id':uid,'received_at':stamp,'sent_at':stamp,'score':80}]} for uid in ['U1','U2']])
  r=await rnd.designer_kpi({'entity_id':'A'},period='all',entity_id='A')
  rec('D4-RND-01-person-identity',2,len(r['items']),'Two genuine performer user IDs sharing a display name become one KPI identity.')
 await case('rnd_identity',rnd_identity)
 async def mixed_totals():
  await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{'inventory':['view'],'warehouse':['view'],'product':['view'],'accounting':['view']}}})
  await db.products.insert_one({'id':'Q','sku':'Q','name':'Yarn','base_unit':'kg','harga_pokok':10,'stage':'finished','line_code':'woven','status':'active'})
  await rolls.create_inbound_roll('Q','WH','A',5,unit='kg',unit_cost=10)
  await snaps.snapshot_stock(now.date().isoformat())
  r=await ae.query_metrics({'metrics':['stock_qty'],'group_by':['product'],'period':{'type':'custom','date_from':now.date().isoformat(),'date_to':now.date().isoformat()}},user,ctx)
  rec('D4-AI-06-mixed-product-total',None,r['totals'].get('stock_qty'),'Products individually have correct meters/kg, but the combined total must not add dimensions.')
 await case('mixed_totals',mixed_totals)
 async def warehouse_capacity():
  from services.location_service import save_warehouse_structure,warehouse_locations
  await save_warehouse_structure('WH',[{'name':'Zone','racks':[{'name':'Rack','levels':[{'name':'Level','bins':[{'code':'BIN-1','capacity':100}]}]}]}])
  loc=await warehouse_locations('WH',ctx,'A')
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as http:resp=await http.get('/api/reports/warehouse-utilization?entity_id=A')
  rec('D4-WMS-03-level-capacity',{'locations':100,'manager_report':100},{'locations':loc['total_capacity'],'manager_report':resp.json()[0]['total_capacity']})
 await case('warehouse_capacity',warehouse_capacity)
if __name__=='__main__':
 try:asyncio.run(main())
 finally:Path(__file__).with_name('extended-numeric-results.json').write_text(json.dumps({'commit':'d6da1a3d536228582645abb98aea19f3e491f300','database':e.DBNAME,'results':results},ensure_ascii=False,indent=2),encoding='utf-8');e.client.close()
