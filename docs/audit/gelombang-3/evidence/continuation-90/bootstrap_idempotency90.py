"""Original startup twice on a task-owned synthetic fixture, never a production DB."""
import asyncio,json,os,sys,traceback,time
from pathlib import Path
R=Path(os.environ['KNHOST_REPO']);sys.path[:0]=[str(R),str(R/'backend'),str(R/'scripts')]
os.environ.update(KN_DEMO_DATA='true',KN_INITIAL_PASSWORD='demo12345')
from db import db,client
from bootstrap import run_bootstrap
O=Path(__file__).parent;RESULTS=[];ERRORS=[]
assert db.name=='knhost_audit_native90_template'
def rec(key,want,actual):
 RESULTS.append(dict(id=key,expected=want,actual=actual,status='pass' if want==actual else 'observed_difference'))
async def snapshot():
 collections=['users','hr_employees','hr_shifts','hr_leave_balances','rfid_tags','inventory_rolls',
  'inventory_balances','inventory_lots','journal_entries','sales_orders','purchase_orders','products']
 counts={n:await db[n].count_documents({}) for n in collections}
 rolls=await db.inventory_rolls.find({},{'_id':0,'id':1,'length_remaining':1,'length_reserved':1,
   'unit_cost':1,'base_unit_cost':1,'owner_entity_id':1,'warehouse_id':1,'status':1}).sort('id').to_list(None)
 products=await db.products.find({},{'_id':0,'id':1,'harga_pokok':1,'price':1,'lifecycle_status':1}).sort('id').to_list(None)
 balances=await db.inventory_balances.find({},{'_id':0,'id':1,'owned_qty':1,'reserved_qty':1,'available_qty':1}).sort('id').to_list(None)
 return dict(counts=counts,rolls=rolls,products=products,balances=balances)
async def main():
 before=await snapshot()
 for i in range(2):
  try:await run_bootstrap()
  except Exception as ex:ERRORS.append(dict(attempt=i+1,error=repr(ex),traceback=traceback.format_exc()))
  if i==0:once=await snapshot()
 twice=await snapshot()
 for key in ['counts','rolls','products','balances']:rec('BOOT90-second-start-'+key,once[key],twice[key])
 out=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=db.name,
  observations=RESULTS,harness_errors=ERRORS,before=before,once=once,twice=twice,
  scope='Original bootstrap includes demo seeding/backfills. Idempotence of these snapshots only; every migration variant is not proven.')
 (O/'bootstrap-idempotency90-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 print(json.dumps(dict(observations=len(RESULTS),differences=[x['id'] for x in RESULTS if x['status']!='pass'],errors=ERRORS)),flush=True)
 client.close()
asyncio.run(main())
