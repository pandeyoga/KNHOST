"""Focused explanatory probes; not a full business lifecycle or additional coverage count."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import roll_service as r,lot_service as lot,line_scope as ls
db=e.db;observations=[]
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 await db.warehouses.insert_one(dict(id='WH',name='Synthetic',status='active'))
 for tag,lengths in [('LONG_LAST',[100]*9+[105]),('LONG_FIRST',[105]+[100]*9)]:
  await db.products.insert_one(dict(id=tag,sku=tag,name=tag,base_unit='meter',status='active'))
  for i,length in enumerate(lengths):
   roll=await r.create_inbound_roll(tag,'WH','A',length,unit_cost=1,acquired_via='purchase',ref_id=tag)
   await db.inventory_rolls.update_one({'id':roll['id']},{'$set':{'lot':'SAME-TEST-LOT','created_at':f'2026-09-01T00:00:{i:02}'}})
  data=await r.compute_roll_reconcile(tag,1000,'A')
  options={k:{'qty':v['total_qty'],'rolls':v['roll_count']} for k,v in data['options'].items()}
  assert options['round_up']==dict(qty=1005,rolls=10)
  assert options['round_down']['qty']==(900 if tag=='LONG_LAST' else 905)
  observations.append(dict(probe=tag,options=options,note='Base-unit numeric fixture; yard conversion and browser selection not tested'))
 observations.append(dict(probe='LINE_POLICY',woven_allowed=ls.can_touch({'allowed_line_codes':['woven']},{'line_code':'woven'}),printing_allowed=ls.can_touch({'allowed_line_codes':['woven']},{'line_code':'printing'}),unclassified_allowed=ls.can_touch({'allowed_line_codes':['woven']},{}),empty_assignment_all=ls.can_touch({'allowed_line_codes':[]},{'line_code':'printing'})))
 doc=await lot.create_lot(product_id='LONG_LAST',owner_entity_id='A',warehouse_id='WH',supplier_lot='123',actor='Audit')
 updated=await lot.patch_lot(doc['id'],{'supplier_lot':'123-CORRECTED'},actor='Audit')
 assert updated['lot_number']==doc['lot_number']
 try:await lot.patch_lot(doc['id'],{'lot_number':'A'},actor='Audit')
 except lot.LotError:rename_blocked=True
 else:rename_blocked=False
 assert rename_blocked
 observations.append(dict(probe='LOT_IDENTITY',internal_number=doc['lot_number'],supplier_before='123',supplier_after=updated['supplier_lot'],normal_patch_internal_rename_blocked=rename_blocked))
 assert not e.blocked
 print(json.dumps(observations),flush=True)
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('client-requirements-probes.json').write_text(json.dumps(dict(source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),database=e.DBNAME,mode='Focused actual service probes with synthetic Mongo; explanatory evidence excluded from239 checkpoint totals',observations=observations),indent=2),encoding='utf-8');e.client.close()
