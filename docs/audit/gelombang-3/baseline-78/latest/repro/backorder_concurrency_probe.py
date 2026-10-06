import asyncio,json,traceback
from pathlib import Path
import wave2_env as e
from services import roll_service as rolls,backorder_service as bo
from motor.motor_asyncio import AsyncIOMotorCollection as Collection
db=e.db
async def main():
 await e.seed()
 await db.products.insert_one({'id':'R','sku':'R','name':'R','base_unit':'meter','status':'active','price':10})
 await db.warehouses.insert_one({'id':'WH','name':'WH','sharing_mode':'shared','status':'active'})
 for _ in range(4):await rolls.create_inbound_roll('R','WH','A',50,unit_cost=10)
 await db.sales_orders.insert_one({'id':'RACE','number':'RACE','entity_id':'A','status':'waiting_stock','has_backorder':True,
   'items':[{'product_id':'R','quantity':100,'reserved_qty':0,'backorder_qty':100}],
   'backorders':[{'id':'BRACE','product_id':'R','requested_qty':100,'reserved_qty':0,'backorder_qty':100,'status':'waiting_stock'}],'allocations':[]})
 original=Collection.update_one;arrived=0;barrier=asyncio.Event()
 async def scheduled(self,q,ops,*args,**kw):
  nonlocal arrived
  if self.name=='sales_orders' and q.get('id')=='RACE' and 'allocations' in ops.get('$push',{}):
   arrived+=1
   if arrived==2:barrier.set()
   await asyncio.wait_for(barrier.wait(),20)
  return await original(self,q,ops,*args,**kw)
 Collection.update_one=scheduled
 try:done=await asyncio.wait_for(asyncio.gather(bo.fulfill_from_stock('RACE','R',80,'User1'),bo.fulfill_from_stock('RACE','R',80,'User2')),30)
 finally:Collection.update_one=original
 o=await db.sales_orders.find_one({'id':'RACE'});allocated=round(sum(float(a.get('quantity',0)) for a in o['allocations']),2)
 expected={'allocated_qty':100,'item_reserved_qty':100,'backorder_qty':0}
 actual={'allocated_qty':allocated,'item_reserved_qty':o['items'][0]['reserved_qty'],'backorder_qty':o['items'][0]['backorder_qty']}
 result={'id':'D4-BACKORDER-01-concurrent-fill','expected':expected,'actual':actual,'returned_qty':done,'status':'pass' if actual==expected else 'observed_difference','note':'Two real stock fulfillment calls for one SO shortage100 from physical200. Barrier schedules final SO writes only; allocators and database CAS unchanged. Demand should cap combined reservation at100 and item/allocation/backorder must reconcile.'}
 Path(__file__).with_name('backorder-concurrency-results.json').write_text(json.dumps({'commit':'a904d989b622f7da14c4892d03cf6ef0c43f3084','database':e.DBNAME,'results':[result]},indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
try:asyncio.run(main())
finally:e.client.close()
