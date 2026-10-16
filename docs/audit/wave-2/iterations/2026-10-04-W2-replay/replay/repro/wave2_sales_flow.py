"""Order to delivery through real ASGI routes, synthetic inventory."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import roll_service as r
db=e.db;results=[];checks=[]
def check(n,label,actual,expected):
 assert actual==expected,(n,label,actual,expected)
 checks.append({'id':f'W2-S-C{n:02}','kind':'control','label':label,'observed':actual,'expected':expected})
 print(json.dumps(checks[-1]),flush=True)
async def buckets():
 out={}
 async for roll in db.inventory_rolls.find({'product_id':'P'}):out[roll['status']]=round(out.get(roll['status'],0)+roll['length_remaining'],2)
 return out
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.order':['create','view','update','approve','confirm','cancel','verify','deliver'],'matrix.finance.wms':['view','update','approve'],'matrix.finance.sales_return':['view','create','update','approve']}})
 await db.warehouses.insert_one({'id':'WH','name':'Audit WH','status':'active','sharing_mode':'shared','priority':1})
 await db.products.insert_one({'id':'P','name':'Audit fabric','sku':'P','base_unit':'meter','price':10000,'harga_pokok':5000,'status':'active','grade':'A'})
 await db.customers.insert_one({'id':'C','name':'Audit customer','entity_id':'A','status':'active','credit_limit':10000000,'addresses':[{'id':'ADDR','label':'Audit','address':'Synthetic address','city':'Jakarta','recipient_name':'Synthetic recipient','phone':'0000000000'}]})
 await r.create_inbound_roll('P','WH','A',100,unit_cost=5000,acquired_via='purchase',ref_id='OPENING')
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
  async def post(path,**kw):
   response=await h.post('/api'+path,**kw)
   try:body=response.json()
   except Exception:body=response.text
   print(path,response.status_code,flush=True)
   results.append({'path':path,'status':response.status_code,'body':body})
   assert response.status_code==200,(path,body)
   return body
  so=await post('/sales-orders',json={'customer_id':'C','shipping_address_id':'ADDR','entity_id':'A','items':[{'product_id':'P','quantity':20,'unit':'meter'}]})
  oid=so['id']
  check(1,'Order reserves20 from100',await buckets(),{'available':80,'reserved':20})
  denied=await h.post(f'/api/sales-orders/{oid}/confirm')
  check(2,'Confirm before verification blocked',denied.status_code,409)
  so=await post(f'/sales-orders/{oid}/submit-for-approval')
  if so['status']=='waiting_approval':so=await post(f'/sales-orders/{oid}/approve')
  await post(f'/sales-orders/{oid}/verify',json={'note':'Synthetic complete document check'})
  so=await post(f'/sales-orders/{oid}/confirm')
  tasks=await db.wms_tasks.find({'order_id':oid,'flow_type':'outbound'}).to_list(100)
  check(3,'Confirmed order creates one task20',[so['status'],len(tasks),tasks[0]['quantity']],['confirmed',1,20])
  premature=await h.post(f"/api/outbound/tasks/{tasks[0]['id']}/dispatch")
  check(4,'Dispatch before pick blocked',premature.status_code,400)
  for t in tasks:await post(f"/outbound/tasks/{t['id']}/scan-pick",params={'actual_qty':t['quantity'],'lot':t.get('lot',''),'roll_id':''})
  t=tasks[0]
  check(5,'Picking commits quantities',await buckets(),{'available':80,'committed':20})
  too_many=await h.post(f"/api/outbound/tasks/{t['id']}/dispatch",params={'ship_qty':21})
  check(6,'Over-dispatch rejected',too_many.status_code,400)
  partial=await post(f"/outbound/tasks/{t['id']}/dispatch",params={'ship_qty':8})
  check(7,'Partial dispatch conserves quantity',[partial['task']['shipped_qty'],await buckets()],[8,{'available':80,'committed':12,'in_transit_sales':8}])
  cancel=await h.post(f'/api/sales-orders/{oid}/cancel')
  check(8,'Cancel partially shipped order blocked',cancel.status_code,409)
  final=await post(f"/outbound/tasks/{t['id']}/dispatch")
  check(9,'Final dispatch ships only remaining12',[final['shipment']['qty'],final['task']['shipped_qty'],await buckets()],[12,20,{'available':80,'in_transit_sales':20}])
  retry=await h.post(f"/api/outbound/tasks/{t['id']}/dispatch")
  check(10,'Repeat dispatch rejected without extra shipment',[retry.status_code,await db.shipments.count_documents({'order_id':oid})],[400,2])
  delivered=await post(f'/sales-orders/{oid}/mark-delivered')
  check(11,'Delivery finalizes transit20',[delivered['status'],await buckets()],['done',{'available':80,'delivered':20}])
  second=await post('/sales-orders',json={'customer_id':'C','shipping_address_id':'ADDR','entity_id':'A','items':[{'product_id':'P','quantity':10,'unit':'meter'}]})
  cancelled=await post(f"/sales-orders/{second['id']}/cancel")
  check(12,'Cancel reserved order restores available',[cancelled['status'],await buckets()],['cancelled',{'available':80,'delivered':20}])
  retry=await h.post(f"/api/sales-orders/{second['id']}/cancel")
  check(13,'Repeated cancel rejected and stock preserved',[retry.status_code,await buckets()],[409,{'available':80,'delivered':20}])
  over=await h.post('/api/sales-returns',json={'order_id':oid,'items':[{'product_id':'P','quantity_returned':21,'unit':'meter'}]})
  check(14,'Return exceeding delivered quantity rejected',over.status_code,400)
  ret=await post('/sales-returns',json={'order_id':oid,'submit_now':True,'items':[{'product_id':'P','quantity_returned':5,'unit':'meter'}]})
  rid=ret['id']
  early=await h.post(f'/api/sales-returns/{rid}/settle',json={'outcome':'store_credit','return_warehouse_id':'WH'})
  check(15,'Settlement before approval and inspection rejected',early.status_code,400)
  ret=await post(f'/sales-returns/{rid}/approve')
  ret=await post(f'/sales-returns/{rid}/inspect/start')
  ret=await post(f'/sales-returns/{rid}/inspect/complete',json={'inspections':[{'index':0,'grade':'A','condition':'ok','disposition':'restock','accepted_qty':5}]})
  check(16,'Return inspection records measured acceptance',[ret['inspection_status'],ret['items'][0]['inspection']['accepted_qty']],['done',5])
  ret=await post(f'/sales-returns/{rid}/settle',json={'outcome':'store_credit','return_warehouse_id':'WH'})
  check(17,'Store credit return restocks into quarantine',[ret['status'],ret['credit_note_amount'],await buckets()],['credit_settled',50000,{'available':80,'delivered':20,'quarantine':5}])
  before=await db.credit_notes.count_documents({'return_id':rid})
  ret=await post(f'/sales-returns/{rid}/settle',json={'outcome':'store_credit','return_warehouse_id':'WH'})
  check(18,'Repeat settlement conserves stock and credit note count',[await buckets(),await db.credit_notes.count_documents({'return_id':rid})],[{'available':80,'delivered':20,'quarantine':5},before])
  ret=await post(f'/sales-returns/{rid}/reverse',json={'notes':'Synthetic return correction'})
  check(19,'Reverse quarantined return restores pre-return stock',[ret['status'],await buckets()],['cancelled',{'available':80,'delivered':20}])
  assert not e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('sales-flow-results.json').write_text(json.dumps({'database':e.DBNAME,'source_commit':subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),'mode':'Actual ASGI lifecycle; opening100 roll from actual service; synthetic masters, default policies','results':checks,'observations':results},indent=2),encoding='utf-8');e.client.close()
