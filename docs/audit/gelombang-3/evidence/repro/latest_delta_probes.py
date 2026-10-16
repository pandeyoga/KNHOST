"""Original latest services/ASGI with local synthetic fixtures and independent oracles."""
import asyncio,json,traceback
from datetime import datetime,timezone
from pathlib import Path
import wave2_env as e
from services import fulfillment_plan_service as fps,fulfillment_decision_service as fds
from services import sales_stock_service as salesstock,roll_service as rolls
from services.config_service import compute_order_pricing
db=e.db; results=[]
def rec(id,expected,actual,note=''):
 r={'id':id,'expected':expected,'actual':actual,'note':note,'status':'pass' if expected==actual else 'observed_difference'}
 results.append(r); print(json.dumps(r,ensure_ascii=False),flush=True)
async def case(id,fn):
 try:await fn()
 except Exception as ex:
  results.append({'id':id,'status':'harness_error','error':repr(ex),'traceback':traceback.format_exc()});print(id,repr(ex),flush=True)
async def order(oid,qty=100,pid='P'):
 stamp=datetime.now(timezone.utc).isoformat()
 o={'id':oid,'number':oid,'entity_id':'A','customer_id':'C','customer_name':'Synthetic Customer','status':'waiting_stock','has_backorder':True,'created_at':stamp,
    'items':[{'product_id':pid,'product_name':pid,'quantity':qty,'base_quantity':qty,'unit':'meter','reserved_qty':0,'backorder_qty':qty}],
    'backorders':[{'id':'BO'+oid,'product_id':pid,'product_name':pid,'requested_qty':qty,'reserved_qty':0,'backorder_qty':qty,'status':'waiting_stock','created_at':stamp}],'allocations':[]}
 await db.sales_orders.insert_one(o);return o
async def main():
 await e.seed()
 from services import gl_service
 await gl_service.seed_default_coa()
 await db.users.update_one({'id':'U'},{'$set':{'role':'admin','allowed_entity_ids':['A','B']}})
 await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{'order':['view','confirm'],'inventory':['view'],'purchase_order':['view','create']}}})
 await db.warehouses.insert_one({'id':'WH','name':'Synthetic WH','entity_id':'A','sharing_mode':'shared','status':'active'})
 await db.products.insert_one({'id':'P','sku':'P','name':'P','base_unit':'meter','stage':'finished','line_code':'woven','status':'active','price':10,'harga_pokok':10})
 actor=await db.users.find_one({'id':'U'},{'_id':0})
 async def reorder_partial():
  await order('PARTIALPR')
  r1=await fps.decide_plan('PARTIALPR',[{'product_id':'P','reorder_qty':20}],actor)
  r2=await fps.decide_plan('PARTIALPR',[{'product_id':'P','reorder_qty':80}],actor)
  pr_id=r2['decision']['parts'][0]['ref_id'];pr=await db.purchase_requisitions.find_one({'id':pr_id})
  qty=sum(float(i['quantity']) for i in pr['items'])
  rec('D4-PLAN-01-reaffirmed-qty',{'decision_qty':20,'referenced_pr_qty':20},{'decision_qty':r2['decision']['parts'][0]['qty'],'referenced_pr_qty':qty},'First plan creates PR20; second asks80. Existing helper reaffirms PR20 while new planner records80. No duplicate PR inferred.')
  fresh=await fds._order('PARTIALPR');opts=await fps.plan_options(fresh)
  rec('D4-PLAN-01-planned-conservation',20,opts['lines'][0]['planned_qty'],'Cumulative history counts20+80, but only PR20 exists. Reaffirmation is not new supply.')
 await case('partial_reorder',reorder_partial)
 async def duplicate_plan_lines():
  await order('DUPPLAN')
  res=await fps.decide_plan('DUPPLAN',[{'product_id':'P','reorder_qty':100},{'product_id':'P','reorder_qty':100}],actor)
  pr=await db.purchase_requisitions.find_one({'id':res['decision']['parts'][0]['ref_id']})
  rec('D4-PLAN-02-duplicate-product',100,sum(float(i['quantity']) for i in pr['items']),'Each duplicate plan row passes its own100<=shortage100 validation; combined plan creates PR200. Normal browser sends one row, but public typed API does not reject duplicates.')
 await case('duplicate_plan_lines',duplicate_plan_lines)
 async def partial_scope():
  await db.sales_orders.update_many({}, {'$set':{'has_backorder':False}})
  await rolls.create_inbound_roll('P','WH','A',30,unit_cost=10)
  await rolls.create_inbound_roll('P','WH','B',70,unit_cost=10)
  await order('PARTFAIL')
  error=None
  try:await fps.decide_plan('PARTFAIL',[{'product_id':'P','stock_qty':30,'interco':[{'entity_id':'B','qty':70}]}],actor)
  except fds.FulfillmentError as ex:error=str(ex)
  o=await fds._order('PARTFAIL');dec=o.get('fulfillment_decision') or {}
  assert error and dec.get('parts'), 'Fixture must actually fail after successful stock fulfillment'
  rec('D4-PLAN-03-partial-scope',{'scope':'partial','actual_qty':30},{'scope':dec.get('scope'),'actual_qty':sum(p['qty'] for p in dec['parts'])},'Original interco service lacks internal price contract in synthetic fixture; stock30 succeeded and recorded, interco70 failed. History says FULL from requested quantities. Error: '+error)
 await case('partial_scope',partial_scope)
 async def wait_shared_supply():
  await db.sales_orders.update_many({}, {'$set':{'has_backorder':False}})
  await db.purchase_orders.insert_one({'id':'WAITPO','number':'WAITPO','entity_id':'A','status':'pending','items':[{'product_id':'P','quantity':100,'received_qty':0,'unit':'meter'}]})
  for oid in ['WAIT1','WAIT2']:
   await order(oid)
   await fps.decide_plan(oid,[{'product_id':'P','wait_qty':100}],actor)
  docs=await db.sales_orders.find({'id':{'$in':['WAIT1','WAIT2']}}).to_list(None)
  rec('D4-PLAN-05-wait-supply-conservation',100,sum(p['qty'] for d in docs for p in d['fulfillment_decision']['parts']),'One pending PO100 is independently offered and fully planned for two SOs100 each. Plans record no exclusive supply allocation; status covers both.')
 await case('wait_shared_supply',wait_shared_supply)
 async def partial_po_incoming():
  from services.stock_bucket_service import _open_po_incoming
  await db.purchase_orders.delete_many({})
  await db.purchase_orders.insert_one({'id':'PARTPO','number':'PARTPO','entity_id':'A','status':'pending','items':[{'product_id':'P','quantity':100,'received_qty':90,'unit':'meter','quantity_base':100}]})
  from routers.purchase_orders import recompute_po_status
  await recompute_po_status('PARTPO')
  po=await db.purchase_orders.find_one({'id':'PARTPO'})
  rec('D4-SUPPLY-01-open-qty',10,sum(i['qty'] for i in await _open_po_incoming('P','A')),'Original recompute_po_status produces '+po['status']+' for PO100 received90. Shared OPEN_PO_STATUSES excludes partial, so remaining10 disappears from future ATP/pending board.')
  products=[await db.products.find_one({'id':'P'},{'_id':0})];await salesstock.apply_global(products,'A')
  rec('D4-SUPPLY-01-global-partial',10,products[0]['incoming_restock_qty'],'New global sales helper imports same OPEN_PO_STATUSES and also loses remaining10.')
 await case('partial_po_incoming',partial_po_incoming)
 async def global_uom():
  await db.purchase_orders.delete_many({})
  body={'entity_id':'A','warehouse_id':'WH','supplier_name':'Synthetic External Supplier','items':[{'product_id':'P','quantity':100,'price':10,'unit':'yard','expected_grade':'A'}]}
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=True),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
   resp=await h.post('/api/purchase-orders',json=body)
  assert resp.status_code==200, (resp.status_code,resp.text)
  po=resp.json();it=po['items'][0]
  assert abs(float(it.get('quantity_base',0))-91.44)<0.01, ('Real PO producer must convert yard to meter',it)
  products=[await db.products.find_one({'id':'P'},{'_id':0})];await salesstock.apply_global(products,'A')
  rec('D4-GLOBAL-01-incoming-uom',91.44,products[0]['incoming_restock_qty'],'Original public POST /purchase-orders produces quantity100 yard/quantity_base91.44 meter. POS global badge labels raw100 as product base_unit meter. PO status='+po['status'])
 await case('global_uom',global_uom)
 async def cap_scaled():
  await db.products.delete_many({});await db.inventory_balances.delete_many({});await db.material_reservations.delete_many({})
  products=[{'id':f'CAP{i:04}','sku':f'CAP{i:04}','name':f'CAP{i:04}','base_unit':'meter','price':10,'harga_pokok':10,'status':'active'} for i in range(3003)]
  await db.products.insert_many(products)
  await db.inventory_balances.insert_many([{'product_id':p['id'],'warehouse_id':'WH','owner_entity_id':'A','available_qty':10,'on_hand_qty':10,'reserved_qty':0} for p in products])
  await db.material_reservations.insert_one({'id':'LASTMR','product_id':'CAP3002','entity_id':'A','owner_entity_id':'A','qty':8,'status':'active'})
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=True),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
   resp=await h.get('/api/dashboard')
  assert resp.status_code==200
  data=resp.json()
  rec('D4-DASH-01-latest-cap-master',3003,len(data['products']),'Old103 SKU counterexample passes at latest cap3000. Scale3003 proves truncation persists without continuation metadata.')
  rec('D4-DASH-01-latest-cap-reservation',30022,data['metrics']['available_qty'],'3003 products each10; valid reservation8 on last product. Balance KPI includes last10, but reservation subtraction only visits first3000 products.')
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=True),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
   codes={}
   for pid in ['CAP0001','CAP1002']:
    body={'entity_id':'A','warehouse_id':'WH','supplier_name':'Synthetic External Supplier','items':[{'product_id':pid,'quantity':1,'price':10,'unit':'meter','expected_grade':'A'}]}
    resp=await h.post('/api/purchase-orders',json=body)
    codes[pid]={'http_status':resp.status_code,'exists':bool(await db.products.find_one({'id':pid}))}
    if resp.status_code!=200:codes[pid]['detail']=resp.json().get('detail')
  rec('D4-CAP-01-purchase-known-sku',{'CAP0001':{'http_status':200,'exists':True},'CAP1002':{'http_status':200,'exists':True}},codes,'Real public producer on same valid input differing only product_id. Lookup reads first1000 master products, while updated catalog can show3000.')
 await case('cap_scaled',cap_scaled)
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).with_name('latest-delta-results.json').write_text(json.dumps({'commit':'a904d989b622f7da14c4892d03cf6ef0c43f3084','database':e.DBNAME,'results':results},ensure_ascii=False,indent=2),encoding='utf-8');e.client.close()
