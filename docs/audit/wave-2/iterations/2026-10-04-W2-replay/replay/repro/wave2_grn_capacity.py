"""501 physical rolls through actual manual count and close services; no mocked writes."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_grn_partial as p
e=p.e;db=p.db;g=p.g;c=p.c
results=[]
def record(sid,kind,label,actual,expected):
    print("OBS",(sid,actual,expected),flush=True)
    results.append({'id':sid,'kind':kind,'label':label,'observed':actual,'expected_reproduction':expected})
    print(results[-1],flush=True)
async def main():
    await e.seed()
    import indexes
    await indexes.ensure_performance_indexes()
    await db.warehouses.insert_one({'id':'WH','name':'Audit Warehouse','status':'active'})
    await db.suppliers.insert_one({'id':'SUP','name':'Supplier'})
    pid,tid,poid=await p.seed_po('CAPACITY',501)
    grn=await p.receipt('CAPACITY',tid,poid,[(501,'meter',[1]*501)])
    record('W2-G-C14','control','501 rolls accepted by count service',[grn['lines'][0]['counted']['qty'],grn['lines'][0]['counted']['rolls'],await db.inventory_rolls.count_documents({'grn_id':grn['id']})],[501,501,501])
    result=await p.finish(grn)
    statuses={s:await db.inventory_rolls.count_documents({'grn_id':grn['id'],'status':s}) for s in ['receiving','quarantine','available']}
    task=await db.wms_tasks.find_one({'id':tid})
    record('W2-G-F01','defect','GRN closes but 501st roll is left receiving',{'grn_status':result['grn']['status'],'counted':result['grn']['lines'][0]['counted']['qty'],'po_received':await p.received(poid),'statuses':statuses,'task_status':task['status'],'movement_count':await db.inventory_movements.count_documents({'product_id':pid,'movement_type':'inbound_receiving'})},{'grn_status':'closed','counted':501,'po_received':500,'statuses':{'receiving':1,'quarantine':500,'available':0},'task_status':'qc_pending','movement_count':500})
    try:await c.close_grn(grn['id'],result['grn']['version'],p.actor,p.ctx)
    except Exception as ex:status=getattr(ex,'status_code',None)
    else:status=200
    record('W2-G-F02','defect','Normal retry cannot finalize omitted roll',[status,await db.inventory_rolls.count_documents({'grn_id':grn['id'],'status':'receiving'}),len(await p.active(poid))],[409,1,0])
    assert not e.blocked
if __name__=='__main__':
    try:asyncio.run(main())
    finally:
        Path(__file__).resolve().parents[1].joinpath('grn-capacity-results.json').write_text(json.dumps({'source_commit':subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),'database':e.DBNAME,'mode':'501 actual add_counted_roll calls and actual close, full indexes, synthetic Mongo','results':results},indent=2),encoding='utf-8')
        e.client.close()
