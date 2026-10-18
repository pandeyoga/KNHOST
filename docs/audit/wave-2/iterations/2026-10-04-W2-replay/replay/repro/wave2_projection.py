"""Real stock hold/WIP/rebuild; deterministic stale projection scheduling."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import roll_service as r,stock_bucket_service as b
db=e.db;results=[]
def check(sid,kind,label,actual,expected):
 assert actual==expected,(sid,actual,expected)
 results.append({'id':sid,'kind':kind,'label':label,'observed':actual,'expected_reproduction':expected});print(json.dumps(results[-1]),flush=True)
async def bal():
 d=await db.inventory_balances.find_one({'product_id':'P','warehouse_id':'WH','owner_entity_id':'A'})
 return {k:d[k] for k in ['available_qty','hold_qty','wip_qty','on_hand_qty','owned_qty','atp_qty']}
def expected(av,hold=0,wip=0):return dict(available_qty=av,hold_qty=hold,wip_qty=wip,on_hand_qty=10,owned_qty=10,atp_qty=av)
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 await db.warehouses.insert_one({'id':'WH','name':'Audit','status':'active'})
 await db.products.insert_one({'id':'P','sku':'P','name':'Audit','base_unit':'meter','harga_pokok':100})
 await r.create_inbound_roll('P','WH','A',10,unit_cost=100)
 data={'product_id':'P','warehouse_id':'WH','owner_entity_id':'A','quantity':4,'notes':'Synthetic audit'}
 hold=await b.hold_stock(data,'Audit');print('hold',hold,flush=True)
 check('W2-P-C01','control','Hold4 removes availability but preserves owned',await bal(),expected(6,4))
 await b.release_hold(hold['hold_id'])
 check('W2-P-C02','control','Release restores availability',await bal(),expected(10))
 try:await b.release_hold(hold['hold_id'])
 except Exception as exc:status=getattr(exc,'status_code',None)
 else:status=200
 check('W2-P-C03','control','Repeated release rejected without stock change',[status,await bal()],[404,expected(10)])
 wip=await b.start_wip(data,'Audit');print('wip',wip,flush=True)
 check('W2-P-C04','control','WIP excluded from ATP',await bal(),expected(6,0,4))
 await b.complete_wip(wip['wip_id'])
 check('W2-P-C05','control','WIP complete restores availability',await bal(),expected(10))
 collection=type(db.inventory_balances);original=collection.update_one
 entered=asyncio.Event();resume=asyncio.Event();old_task=None
 async def delayed(self,q,update,*args,**kwargs):
  if self.name=='inventory_balances' and asyncio.current_task() is old_task:
   entered.set();await asyncio.wait_for(resume.wait(),20)
  return await original(self,q,update,*args,**kwargs)
 collection.update_one=delayed
 try:
  old_task=asyncio.create_task(r.rebuild_balance('P','WH','A'))
  await asyncio.wait_for(entered.wait(),20)
  hold=await b.hold_stock(data,'Audit')
  check('W2-P-C06','control','New hold writes current projection before delayed old write',await bal(),expected(6,4))
  resume.set();await old_task
 finally:
  resume.set();collection.update_one=original
 source={}
 async for roll in db.inventory_rolls.find({'product_id':'P'}):source[roll['status']]=source.get(roll['status'],0)+roll['length_remaining']
 check('W2-P-E01','wave1_extension','GN-13 stale rebuild overwrites newer hold projection',[source,await bal()],[{'available':6,'hold':4},expected(10)])
 await r.rebuild_balance('P','WH','A')
 check('W2-P-C07','control','Explicit fresh rebuild repairs projection',await bal(),expected(6,4))
 assert not e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('projection-results.json').write_text(json.dumps({'database':e.DBNAME,'source_commit':subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),'mode':'Actual stock services/Mongo; barrier delays old projection write only; no mocked query result','results':results},indent=2),encoding='utf-8');e.client.close()
