import os,sys,json,asyncio,uuid
from pathlib import Path
base=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(base/'work/KNHOST-plan-audit-2026-10-19/backend'))
os.environ.update(MONGO_URL='mongodb://127.0.0.1:27138',DB_NAME='kn_return_recovery_'+uuid.uuid4().hex)
from db import db,client
from services import return_disposition_service as rd
class FailingMovements:
    async def insert_one(self,*a,**kw):raise RuntimeError('AUDIT transient movement insert failure')
class Proxy:
    def __getattr__(self,k):return FailingMovements() if k=='inventory_movements' else getattr(db,k)
async def main():
    ret={'id':'ret-audit','number':'RET-AUDIT','entity_id':'ent_cst','attachments':[{'id':'photo','content_type':'image/jpeg'}]}
    roll={'id':'roll-audit','roll_no':'RTN-AUDIT','return_id':ret['id'],'origin_type':'return','product_id':'p-audit','warehouse_id':'shared-qc','owner_entity_id':'ent_cst','length_remaining':100,'unit':'yard','unit_cost':10,'grade':'BS','status':'available'}
    roll['origin_interco_pair_id']='pair-audit'
    await db.interco_transactions.insert_one({'id':'ic-seller','pair_id':'pair-audit','role':'seller','seller_entity_id':'ent_cst','buyer_entity_id':'ent_ksc','status':'completed'})
    await db.sales_returns.insert_one(dict(ret));await db.inventory_rolls.insert_one(dict(roll))
    before=await rd.view(ret)
    old=rd.db;rd.db=Proxy()
    try:await rd.decide_supplier(ret,[roll['id']],'dispose','audit disposal',['photo'],'Auditor')
    except Exception as e:error=type(e).__name__+': '+str(e)
    finally:rd.db=old
    after=await db.inventory_rolls.find_one({'id':roll['id']},{'_id':0})
    try:
        await rd.decide_supplier(ret,[roll['id']],'dispose','audit retry',['photo'],'Auditor')
        retry='accepted'
    except Exception as e:retry=type(e).__name__+': '+str(e)
    result={'id':'AUD-RET-01','injected_failure':'inventory movement insert fails after journal and roll update','initial_stage':before['rows'][0]['stage'],'first_error':error,'roll':after,'journals':await db.journal_entries.count_documents({'source_type':'inventory_writeoff','source_id':roll['id']}),'movements':await db.inventory_movements.count_documents({'roll_id':roll['id']}),'retry':retry,'note':'Both attempts use actual decide_supplier with valid BS stock, internal origin and image attachment metadata; transient DB failure injected only at movement insert. No actual image file validation asserted.'}
    (base/'output/audit-plan-2026-10-19/evidence/return-recovery.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));client.close()
asyncio.run(main())
