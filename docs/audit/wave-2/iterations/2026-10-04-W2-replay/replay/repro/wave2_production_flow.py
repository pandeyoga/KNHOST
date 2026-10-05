import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import production_service as p,roll_service as r
db=e.db;results=[];scope={'entity_id':'A'}
def check(n,k,label,actual,expected):
 assert actual==expected,(n,actual,expected)
 results.append(dict(id='W2-PROD-'+n,kind=k,label=label,observed=actual,expected=expected));print(results[-1],flush=True)
async def fixture(tag,a=20,b=20):
 for pid in [tag+'A',tag+'B',tag+'O']:await db.products.insert_one(dict(id=pid,name=pid,sku=pid,base_unit='meter',status='active'))
 for pid,q,c in [(tag+'A',a,10),(tag+'B',b,20)]:
  if q:await r.create_inbound_roll(pid,'WH','A',q,unit_cost=c,acquired_via='purchase',ref_id='OPEN'+tag)
 bom=await p.create_bom(dict(name=tag,output_product_id=tag+'O',components=[dict(material_product_id=tag+'A',qty_per_unit=2),dict(material_product_id=tag+'B',qty_per_unit=1)],overhead_per_unit=3),'A','Audit')
 wo=await p.create_work_order(dict(bom_id=bom['id'],planned_qty=5,warehouse_id='WH'),'A','Audit')
 return bom,wo
async def qty(pid):return sum(x['length_remaining'] for x in await db.inventory_rolls.find({'product_id':pid}).to_list(100))
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes();await db.warehouses.insert_one(dict(id='WH',name='Audit',status='active'))
 bom,wo=await fixture('NORMAL')
 check('C01','control','BOM plans two components',[x['required_qty'] for x in wo['material_plan']],[10,5])
 await p.release_work_order(wo['id'],scope,'Audit');done=await p.complete_work_order(wo['id'],scope,'Audit')
 check('C02','control','Multi-component production conserves material cost plus overhead',[done['material_cost'],done['overhead_cost'],done['total_cost'],done['unit_cost']],[200,15,215,43])
 check('C03','control','Correct remaining inputs and output',[await qty('NORMALA'),await qty('NORMALB'),await qty('NORMALO')],[10,15,5])
 je=await db.journal_entries.find_one({'id':done['je_id']})
 check('C04','control','Only overhead capitalized in GL',[je['total_debit'],je['total_credit']],[15,15])
 await p.complete_work_order(wo['id'],scope,'Audit')
 check('C05','control','Repeat completion no duplicate output',await qty('NORMALO'),5)
 try:await p.cancel_work_order(wo['id'],scope,'Audit')
 except ValueError:blocked=True
 else:blocked=False
 check('C06','control','Completed WO cannot cancel',blocked,True)
 bom,wo=await fixture('SHORT',20,4)
 try:await p.complete_work_order(wo['id'],scope,'Audit')
 except ValueError:blocked=True
 else:blocked=False
 check('C07','control','Second-component shortage preflight leaves first intact',[blocked,await qty('SHORTA'),await qty('SHORTB'),await qty('SHORTO')],[True,20,4,0])
 bom,wo=await fixture('EDIT');await p.release_work_order(wo['id'],scope,'Audit')
 await p.update_bom(bom['id'],{'components':[dict(material_product_id='EDITA',qty_per_unit=3),dict(material_product_id='EDITB',qty_per_unit=1)]},scope)
 done=await p.complete_work_order(wo['id'],scope,'Audit')
 check('E01','wave1_extension','GN-06 released WO follows edited BOM instead of original10',[done['consumed'][0]['qty'],await qty('EDITA')],[15,5])
 bom,wo=await fixture('FAIL');await p.release_work_order(wo['id'],scope,'Audit')
 original=p._consume_material
 async def failing(pid,*args,**kw):
  if pid=='FAILB':raise RuntimeError('Synthetic failure before second material')
  return await original(pid,*args,**kw)
 p._consume_material=failing
 try:
  try:await p.complete_work_order(wo['id'],scope,'Audit')
  except RuntimeError:pass
 finally:p._consume_material=original
 check('E02','wave1_extension','GN-06 failure leaves first consumed without output',[await qty('FAILA'),await qty('FAILB'),await qty('FAILO'),(await db.mfg_work_orders.find_one({'id':wo['id']}))['status']],[10,20,0,'released'])
 done=await p.complete_work_order(wo['id'],scope,'Audit')
 check('E03','wave1_extension','GN-06 retry consumes first material twice but records once',[await qty('FAILA'),await qty('FAILB'),await qty('FAILO'),done['material_cost']],[0,15,5,200])
 movements=await db.inventory_movements.find({'source_document':wo['id'],'movement_type':'production_consume'}).to_list(100)
 check('E04','wave1_extension','GN-06 material loss exceeds output valuation',-sum(x['quantity']*(10 if x['product_id']=='FAILA' else 20) for x in movements),300)
 assert not e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('production-flow-results.json').write_text(json.dumps(dict(database=e.DBNAME,source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),mode='Actual BOM/WO/roll/GL services; synthetic masters; fault before second material then retry, not process crash',results=results),indent=2),encoding='utf-8');e.client.close()
