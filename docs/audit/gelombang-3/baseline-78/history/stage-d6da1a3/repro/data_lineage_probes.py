"""Independent numerical oracles; original ASGI/Mongo/services, synthetic data only."""
import asyncio,json,traceback
from datetime import datetime,timedelta,timezone
from pathlib import Path
import wave2_env as e
from entity_scope import EntityContext
from services import stock_analytics_service as stock,home_service as home,sales_force_service as sf
from services import analytics_engine as ae,analytics_facts as af,analytics_time as at
from services import gl_service as gl,ar_aging_service as ar,profitability_service as profit
from motor.motor_asyncio import AsyncIOMotorCollection as Collection
db=e.db;results=[]
def record(id,expected,actual,note=''):
 results.append({'id':id,'expected':expected,'actual':actual,'status':'pass' if actual==expected else 'observed_difference','note':note});print(json.dumps(results[-1],ensure_ascii=False),flush=True)
async def case(id,func):
 try:await func()
 except Exception as ex:results.append({'id':id,'status':'harness_error','error':repr(ex),'traceback':traceback.format_exc()});print(id,repr(ex),flush=True)
async def main():
 await e.seed();await gl.seed_default_coa()
 await db.users.insert_one({'id':'S','name':'Synthetic Sales','role':'sales','status':'active','home_entity_id':'A','allowed_entity_ids':['A','B']})
 await db.users.insert_one({'id':'S2','name':'Synthetic Co-Sales','role':'sales','status':'active','home_entity_id':'A','allowed_entity_ids':['A']})
 await db.business_entities.insert_many([{'id':eid,'short_name':eid,'legal_name':'Synthetic '+eid,'status':'active'} for eid in ['CASHENT','PROFITENT']])
 await db.users.update_one({'id':'U'},{'$set':{'role':'admin','allowed_entity_ids':['A','B']}})
 await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{'accounting':['view'],'cash':['view'],'order':['view'],'inventory':['view']}}})
 user=await db.users.find_one({'id':'U'},{'_id':0});ctx=EntityContext(user,'A',['A','B']);allctx=EntityContext(user,'A',['A','B'],True)
 now=datetime.now(timezone.utc);stamp=now.isoformat();period=now.strftime('%Y-%m')
 await db.warehouses.insert_one({'id':'WH','name':'Shared audit warehouse','sharing_mode':'shared','status':'active'})
 await db.products.insert_many([{'id':p,'sku':p,'name':p,'base_unit':'meter','price':100,'harga_pokok':10,'category':c,'line_code':'woven','status':'active'} for p,c in [('P','woven'),('Q','knitting')]])
 await db.inventory_balances.insert_many([{'product_id':'P','warehouse_id':'WH','owner_entity_id':eid,'on_hand_qty':qty,'available_qty':qty,'reserved_qty':0} for eid,qty in [('A',10),('B',20)]])
 await db.inventory_rolls.insert_many([{'id':'ROLL'+eid,'product_id':'P','warehouse_id':'WH','owner_entity_id':eid,'length_remaining':qty,'length_initial':qty,'length_reserved':0,'unit':'meter','base_unit_cost':cost,'unit_cost':cost,'status':'available','created_at':stamp,'line_code':'woven'} for eid,qty,cost in [('A',10,10),('B',20,20)]])
 await db.inventory_movements.insert_many([{'id':'MV'+eid,'product_id':'P','warehouse_id':'WH','owner_entity_id':eid,'movement_type':'outbound_ship','quantity':-qty,'timestamp':stamp,'unit':'meter'} for eid,qty in [('A',3),('B',7)]])
 async def stock_owners():
  r=await stock.compute_stock_analytics(allctx,'all');row=r['rows'][0]
  record('D4-STOCK-01-value',500,r['summary']['total_on_hand_value'])
  record('D4-STOCK-01-velocity',10,row['sold_qty_window'])
  record('D4-STOCK-01-onhand-control',30,row['on_hand_qty'])
 await case('stock_owners',stock_owners)
 async def stock_category():
  await db.inventory_rolls.insert_one({'id':'QROLL','product_id':'Q','warehouse_id':'WH','owner_entity_id':'A','length_remaining':40,'base_unit_cost':10,'unit_cost':10,'status':'available','created_at':stamp,'unit':'meter'})
  await db.inventory_balances.insert_one({'product_id':'Q','warehouse_id':'WH','owner_entity_id':'A','on_hand_qty':40,'available_qty':40,'reserved_qty':0})
  r=await stock.compute_stock_analytics(ctx,'A',category='woven')
  record('D4-STOCK-02-filter',100,sum(b['value'] for b in r['summary']['aging_buckets']))
 await case('stock_category',stock_category)
 async def landed():
  await db.inventory_rolls.update_one({'id':'ROLLA'},{'$set':{'unit_cost':12,'landed_cost_total':20}})
  r=await stock.compute_stock_analytics(ctx,'A',category='woven');record('D4-STOCK-03-landed',120,r['rows'][0]['value'])
 await case('landed',landed)
 async def naive_date():
  await db.inventory_rolls.update_one({'id':'ROLLA'},{'$set':{'created_at':now.date().isoformat()}})
  try:await stock.compute_stock_analytics(ctx,'A');err=None
  except Exception as ex:err=type(ex).__name__+': '+str(ex)
  record('D4-STOCK-04-date-only',None,err,'A stored date-only string is legacy/import input; report must normalize or reject with useful validation.')
  await db.inventory_rolls.update_one({'id':'ROLLA'},{'$set':{'created_at':stamp}})
 await case('naive_date',naive_date)
 await db.customers.insert_many([{'id':'CA','name':'Customer A','entity_id':'A','assigned_sales_id':'S','credit_limit':100000,'payment_profile':{'method':'tempo','term_days':30},'created_at':stamp},{'id':'CB','name':'Customer B','entity_id':'B','assigned_sales_id':'S','credit_limit':100000,'payment_profile':{'method':'tempo','term_days':30},'created_at':stamp}])
 for eid,cid,amount in [('A','CA',100),('B','CB',900)]:
  await db.sales_orders.insert_one({'id':'SO'+eid,'number':'SO'+eid,'entity_id':eid,'customer_id':cid,'status':'shipped','grand_total':amount,'total_amount':amount,'paid_total':0,'payments':[],'payment_status':'unpaid','payment_profile_method':'tempo','created_at':stamp,'updated_at':stamp,'items':[]})
 async def tower():
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as http:
   omitted=await http.get('/api/finance/tower');explicit=await http.get('/api/finance/tower?entity_id=A')
  record('D4-FIN-01-tower',{'omitted':100,'explicit':100},{'omitted':omitted.json().get('ar',{}).get('outstanding'),'explicit':explicit.json().get('ar',{}).get('outstanding')},f'HTTP {omitted.status_code}/{explicit.status_code}, same active entity A.')
 await case('tower',tower)
 async def sales_targets():
  await db.sales_targets.insert_one({'id':'TARG','sales_id':'S','entity_id':'A','period_type':'month','period':period,'target_sales_amount':100,'target_collection_amount':100})
  kb=await sf.sales_kpi('S',period,'B');target=await home._sales_target('S',period,kb['total_sales'])
  record('D4-SALES-01-target-scope',0,target['sales_amount'],'Scope B has no target. Target A must not become a denominator for sales in B.')
 await case('sales_targets',sales_targets)
 async def sales_home():
  await db.sales_orders.insert_one({'id':'SO_CROSS','number':'OTHER-ENTITY','customer_id':'CA','entity_id':'B','status':'shipped','grand_total':700,'total_amount':700,'paid_total':0,'payments':[],'payment_status':'unpaid','payment_profile_method':'tempo','created_at':(now+timedelta(seconds=1)).isoformat(),'items':[]})
  h=await home.sales_home('S','A')
  record('D4-SALES-02-recent-orders',False,any(o['id']=='SO_CROSS' for o in h['recent_orders']))
  record('D4-SALES-02-credit-cards',100,sum(c['ar_outstanding'] for c in h['customers']))
 await case('sales_home',sales_home)
 async def forecast():
  from services import cashflow_forecast_service as fc
  await db.sales_orders.insert_one({'id':'CASH-SO','number':'CASH-SO','entity_id':'CASHENT','customer_id':'CASH-CUST','status':'confirmed','grand_total':200,'total_amount':200,'paid_total':0,'payment_status':'unpaid','payment_profile_method':'tunai','payment_term_code':'cash','created_at':stamp})
  r=await fc.cashflow_forecast({'entity_id':'CASHENT'},'CASHENT');record('D4-FIN-02-cash-order-as-ar',0,r['total_inflow'])
 await case('forecast',forecast)
 async def profitability_discount():
  await db.sales_orders.insert_one({'id':'DISC-SO','number':'DISC-SO','entity_id':'PROFITENT','customer_id':'CA','status':'shipped','grand_total':900,'total_amount':1000,'discount_total':100,'ppn_amount':0,'created_at':stamp,'items':[{'product_id':'P','quantity':10,'base_quantity':10,'line_total':1000,'unit_cost':10,'unit':'meter'}]})
  r=await profit.profitability(scope={'entity_id':'PROFITENT'},entity_id='PROFITENT');record('D4-FIN-03-order-discount-legacy',900,r['totals']['revenue'],'Legacy/header-discount shape only: current create_order forces manual order discount=0. Do not infer every new SO can produce this header discount.')
  await db.sales_orders.delete_one({'id':'DISC-SO'})
  from services.config_service import compute_order_pricing
  await db.business_entities.update_one({'id':'PROFITENT'},{'$set':{'default_tax_mode':'ppn'}})
  await db.system_settings.insert_one({'id':'PFSET','scope':'PROFITENT','tax':{'ppn_mode':'included'}})
  pricing=await compute_order_pricing([{'product_id':'P','quantity':10,'price':100,'unit':'meter','unit_cost':10}], 'PROFITENT',0,tax_override='ppn')
  assert pricing['ppn_mode']=='included' and pricing['ppn_amount']>0, 'PKP included fixture must really contain VAT'
  await db.sales_orders.insert_one({'id':'TAX-SO','number':'TAX-SO','entity_id':'PROFITENT','customer_id':'CA','status':'shipped','created_at':stamp,**pricing})
  r=await profit.profitability(scope={'entity_id':'PROFITENT'},entity_id='PROFITENT')
  record('D4-FIN-03-tax-included',round(pricing['grand_total']-pricing['ppn_amount'],2),r['totals']['revenue'],'Use the original pricing producer with a real PKP entity and entity settings ppn_mode=included. Current create_order uses this producer/settings. Revenue must exclude VAT; report directly sums the inclusive line_total.')
 await case('profitability_discount',profitability_discount)
 sc=await ae.build_scope(user,ctx);p=at.period_from_args({'date_from':now.date().isoformat(),'date_to':now.date().isoformat(),'type':'custom'})
 async def source_filters():
  await db.vendor_bills.insert_one({'id':'LEGACYBILL','entity_id':'A','supplier_id':'V','status':'posted','grand_total':0,'total_amount':125,'amount_paid':25,'bill_date':now.date().isoformat(),'due_date':now.date().isoformat()})
  r=await ae._src_ap(['ap_outstanding'],[],None,p,[],sc,[],False)
  record('D4-AI-01-ap-fallback',100,r.get((),{}).get('ap_outstanding'))
 await case('source_filters',source_filters)
 async def new_customer_line():
  await db.fact_sales_lines.insert_many([{'_id':'NA','so_id':'NA','customer_id':'NCA','entity_id':'A','is_live':True,'is_sample':False,'date_wib':now.date().isoformat(),'line_code':'knitting'}])
  woven=ae.Scope(user,['A'],None,{'line_code':'woven'},sc.policy)
  r=await ae._src_fact_new(['new_customers'],[],None,p,[],woven,[],False)
  record('D4-AI-02-new-customer-line',0,r.get((),{}).get('new_customers',0))
 await case('new_customer_line',new_customer_line)
 async def fact_failure():
  doc={'id':'FACTSO','entity_id':'A','status':'confirmed','grand_total':100,'total_amount':100,'created_at':stamp,'updated_at':stamp,'items':[{'product_id':'P','quantity':1,'line_total':100}]}
  await af._write([doc],'team_split');old=Collection.insert_many
  async def fault(self,*a,**k):
   if self.name=='fact_sales_lines':raise RuntimeError('Synthetic insert failure before write')
   return await old(self,*a,**k)
  Collection.insert_many=fault
  try:
   try:await af._write([doc],'team_split')
   except RuntimeError:pass
  finally:Collection.insert_many=old
  record('D4-AI-03-durable-refresh',1,await db.fact_sales_lines.count_documents({'so_id':'FACTSO'}))
 await case('fact_failure',fact_failure)
 async def rounding():
  so={'id':'ROUND','entity_id':'A','status':'confirmed','grand_total':1.01,'total_amount':1.01,'ppn_amount':0,'created_at':stamp,'sales_team':[{'sales_id':'S','role':'pic','split_pct':50},{'sales_id':'S2','role':'co','split_pct':50}],'items':[{'product_id':'P','quantity':1,'line_total':1.01}]}
  rows=af.build_rows(so,{}, {}, {});record('D4-AI-04-money-conservation',1.01,round(sum(r['net_alloc'] for r in rows),2),'Two members with PIC/co roles and 50/50 split satisfy current max-two-sales rule; the monetary producer keeps two decimal places.')
 await case('rounding',rounding)
 async def petty():
  await db.bank_accounts.insert_one({'id':'PETTY','name':'Kas Operasional','account_type':'cash','entity_id':'A','opening_balance':1000,'is_active':True,'created_at':stamp})
  await db.cash_transactions.insert_one({'id':'PETTY-TX','account_id':'PETTY','entity_id':'A','cash_type':'kas_kecil','direction':'in','amount':10,'status':'posted','txn_date':now.date().isoformat()})
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as http:
   before=(await http.get('/api/cash-transactions/summary')).json()
   await db.cash_transactions.update_one({'id':'PETTY-TX'},{'$set':{'status':'void'}})
   after=(await http.get('/api/cash-transactions/summary')).json()
  record('D4-CASH-01-opening-reclass',{'before_kecil_opening':1000,'after_kecil_opening':1000,'after_besar_opening':0},{'before_kecil_opening':before['kas_kecil']['opening'],'after_kecil_opening':after['kas_kecil']['opening'],'after_besar_opening':after['kas_besar']['opening']},'Voiding its only petty transaction must not move unchanged opening money to large cash.')
 await case('petty',petty)
 async def cap():
  await db.products.insert_many([{'id':f'CAP{i}','sku':f'CAP{i}','name':f'CAP{i}','base_unit':'meter','harga_pokok':0,'status':'active'} for i in range(101)])
  await db.inventory_balances.insert_one({'product_id':'CAP100','warehouse_id':'WH','owner_entity_id':'A','available_qty':1000,'reserved_qty':0,'on_hand_qty':1000})
  await db.material_reservations.insert_one({'id':'MCAP','product_id':'CAP100','owner_entity_id':'A','status':'active','qty':200,'ref_id':'RCAP'})
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as http:r=(await http.get('/api/dashboard?entity_id=A')).json()
  expected=10+40+1000-200
  record('D4-DASH-01-master-window-reservation',expected,r['metrics']['available_qty'])
  record('D4-DASH-01-master-completeness',103,len(r['products']),'Master product consumers receive a truncated list without continuation metadata.')
 await case('cap',cap)
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).with_name('data-lineage-results.json').write_text(json.dumps({'commit':'d6da1a3d536228582645abb98aea19f3e491f300','database':e.DBNAME,'mode':'Synthetic localhost original application services and ASGI; observations differ from independent business oracles, not automatically adjudicated findings.','results':results},ensure_ascii=False,indent=2),encoding='utf-8');e.client.close()
