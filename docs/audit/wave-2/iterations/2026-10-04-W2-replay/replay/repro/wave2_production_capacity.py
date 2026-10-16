import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import production_service as p,roll_service as r
db=e.db;results=[]
def check(n,k,label,actual,expected):
 print("OBS",(n,actual,expected),flush=True)
 results.append(dict(id='W2-PCAP-'+n,kind=k,label=label,observed=actual,expected=expected));print(results[-1],flush=True)
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 await db.warehouses.insert_one(dict(id='WH',name='Audit',status='active'))
 await db.products.insert_many([dict(id=x,sku=x,name=x,base_unit='meter',status='active') for x in ['MAT','OUT']])
 template=await r.create_inbound_roll('MAT','WH','A',1,unit_cost=10,acquired_via='purchase',ref_id='OPEN')
 for lo in range(1,5001,1000):
  await db.inventory_rolls.insert_many([{**{k:v for k,v in template.items() if k!='_id'},'id':f'CAP{i}','roll_no':f'CAP-{i:05}'} for i in range(lo,min(lo+1000,5001))])
 await r.rebuild_balance('MAT','WH','A')
 check('C01','control','Indexed fixture has5001 one-meter material rolls',await db.inventory_rolls.count_documents({'product_id':'MAT'}),5001)
 bom=await p.create_bom(dict(name='Capacity',output_product_id='OUT',components=[dict(material_product_id='MAT',qty_per_unit=1)],overhead_per_unit=0),'A','Audit')
 wo=await p.create_work_order(dict(bom_id=bom['id'],planned_qty=5001,warehouse_id='WH'),'A','Audit')
 check('C02','control','Aggregate preflight sees sufficient5001',[wo['material_plan'][0]['available_qty'],wo['material_plan'][0]['required_qty'],wo['material_plan'][0]['sufficient']],[5001,5001,True])
 await p.release_work_order(wo['id'],{'entity_id':'A'},'Audit');done=await p.complete_work_order(wo['id'],{'entity_id':'A'},'Audit')
 check('F01','defect','WO completes5001 output after consuming only5000',[done['status'],done['produced_qty'],done['consumed'][0]['qty'],done['material_cost']],['completed',5001,5000,50000])
 check('F02','defect','Unconsumed material remains after claimed complete',[await db.inventory_rolls.count_documents({'product_id':'MAT','status':'available','length_remaining':1}),await db.inventory_rolls.count_documents({'product_id':'MAT','status':'consumed'})],[1,5000])
 moves=await db.inventory_movements.aggregate([{'$match':{'source_document':wo['id'],'movement_type':'production_consume'}},{'$group':{'_id':None,'qty':{'$sum':'$quantity'},'count':{'$sum':1}}}]).to_list(1)
 check('C03','control','Movement oracle confirms actual5000 consumed',[moves[0]['qty'],moves[0]['count']],[-5000,5000])
 assert not e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('production-capacity-results.json').write_text(json.dumps(dict(database=e.DBNAME,source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),mode='Actual complete WO and5000 roll mutations;5001 synthetic input rolls seeded from actual roll template, shared opening lot; no physical production',results=results),indent=2),encoding='utf-8');e.client.close()
