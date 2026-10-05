"""Deterministic transient failure before second roll write; all other DB operations real."""
import asyncio,json,subprocess
from pathlib import Path
from pymongo.errors import AutoReconnect
import wave2_grn_partial as p
e=p.e;db=p.db;results=[]
def record(sid,actual,expected):
    assert actual==expected,(sid,actual,expected)
    results.append({'id':sid,'kind':'wave1_extension','related':'GN-11','observed':actual,'expected_reproduction':expected})
    print(results[-1],flush=True)
async def main():
    await e.seed()
    import indexes
    await indexes.ensure_performance_indexes()
    await db.warehouses.insert_one({'id':'WH','name':'Audit Warehouse','status':'active'})
    await db.suppliers.insert_one({'id':'SUP','name':'Supplier'})
    pid,tid,poid=await p.seed_po('RECOVERY',10)
    grn=await p.receipt('RECOVERY',tid,poid,[(10,'meter',[4,6])])
    grn=await p.c.finish_count(grn['id'],grn['version'],p.actor,p.ctx)
    rolls=await db.inventory_rolls.find({'grn_id':grn['id']}).sort('created_at',1).to_list(100)
    collection_type=type(db.inventory_rolls);original=collection_type.update_one
    fired=[]
    async def interrupted(self,query,update,*args,**kwargs):
        if self.name=='inventory_rolls' and query.get('id')==rolls[1]['id'] and update.get('$set',{}).get('status')=='quarantine' and not fired:
            fired.append(True)
            raise AutoReconnect('Synthetic transient failure before second roll finalization')
        return await original(self,query,update,*args,**kwargs)
    collection_type.update_one=interrupted
    try:
        try:await p.c.close_grn(grn['id'],grn['version'],p.actor,p.ctx)
        except AutoReconnect:failed=True
        else:failed=False
    finally:collection_type.update_one=original
    fresh=await p.g.load(grn['id'],p.ctx)
    record('W2-G-E01',{'failure_injected':failed,'grn_status':fresh['status'],'po_received':await p.received(poid),'quarantine_rolls':await db.inventory_rolls.count_documents({'grn_id':grn['id'],'status':'quarantine'}),'receiving_rolls':await db.inventory_rolls.count_documents({'grn_id':grn['id'],'status':'receiving'})},{'failure_injected':True,'grn_status':'closing','po_received':0,'quarantine_rolls':1,'receiving_rolls':1})
    result=await p.c.close_grn(grn['id'],fresh['version'],p.actor,p.ctx)
    assert result['grn']['status']=='closing' and result['results'][0]['status']=='failed' and await p.received(poid)==0
    results.append({'id':'W2-G-C15','kind':'control','label':'Immediate retry held by surviving inbound saga lock','observed':{'grn_status':'closing','posting_status':'failed','po_received':0}})
    from services.atomic_claim import release
    await release('wms_tasks',tid)
    # Same release helper as admin route; no direct mutation of roll or PO, no admin authorization claim.
    fresh=await p.g.load(grn['id'],p.ctx)
    result=await p.c.close_grn(grn['id'],fresh['version'],p.actor,p.ctx)
    rolls=await db.inventory_rolls.find({'grn_id':grn['id']}).to_list(100)
    tasks=await p.active(poid)
    record('W2-G-E02',{'grn_status':result['grn']['status'],'po_received':await p.received(poid),'physical_qty':sum(r['length_remaining'] for r in rolls),'counted_qty':result['grn']['lines'][0]['counted']['qty'],'remainder_qty':[t['expected_qty'] for t in tasks]},{'grn_status':'closed','po_received':6,'physical_qty':10,'counted_qty':10,'remainder_qty':[4]})
    task=await db.wms_tasks.find_one({'id':tid})
    record('W2-G-E03',{'quarantine_qty':task['quarantine_qty'],'physical_quarantine_qty':sum(r['length_remaining'] for r in rolls if r['status']=='quarantine'),'task_qty_rolls':task['qty_rolls'],'physical_rolls':len(rolls)},{'quarantine_qty':6,'physical_quarantine_qty':10,'task_qty_rolls':1,'physical_rolls':2})
    assert not e.blocked
if __name__=='__main__':
    try:asyncio.run(main())
    finally:
        Path(__file__).resolve().parents[1].joinpath('grn-recovery-results.json').write_text(json.dumps({'source_commit':subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),'database':e.DBNAME,'mode':'Actual service + Mongo with one injected AutoReconnect before second roll update; no production outage frequency claim','results':results},indent=2),encoding='utf-8')
        e.client.close()
