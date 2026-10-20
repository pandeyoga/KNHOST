import os,sys,uuid,asyncio,json,csv
from pathlib import Path
base=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(base/'work/KNHOST-plan-audit-2026-10-19/backend'))
os.environ.update(MONGO_URL='mongodb://127.0.0.1:27138',DB_NAME='kn_export_audit_'+uuid.uuid4().hex)
from db import db,client
from services import export_engine as ex,makloon_recap_service as mr
async def main():
    await db.audit_rows.insert_many([{'id':str(i),'amount':i*10} for i in range(1,5)])
    plan={'ds':{'collection':'audit_rows','key':'id','joins':[]},'columns':[{'key':'id','path':'id','type':'text','source':'base','label':'ID'}], 'pipeline':[], 'sort':{'id':1},'hidden':[]}
    original=ex.fetch;calls=0
    async def concurrent_fetch(p,skip,limit):
        nonlocal calls
        if calls==1:
            await db.audit_rows.delete_one({'id':'4'})
            await db.audit_rows.insert_one({'id':'0','amount':0})
        calls+=1
        return await original(p,skip,limit)
    ex.fetch=concurrent_fetch
    dest=base/'output/audit-plan-2026-10-19/evidence/concurrent-export.csv'
    try: result=await ex.write_file({'format':'csv'},plan,str(dest),100,batch=2)
    finally: ex.fetch=original
    exported=list(csv.reader(dest.open(encoding='utf-8-sig')))
    out=[{'id':'AUD-EXP-02','scenario':'Concurrent delete and insert between two actual export batches, same total row count','initial_ids':['1','2','3','4'],'final_ids':[x['id'] async for x in db.audit_rows.find({}, {'id':1}).sort('id',1)],'exported_ids':[x[0] for x in exported[1:]],'written':result['written_rows'],'count_after':await ex.count(plan)}]
    losses=[{'status':'posted','recorded_at':'2026-10-19','qty':1,'expense_value':10} for _ in range(1001)]
    await db.makloon_orders.insert_one({'id':'audit-mko','steps':[{'makloon_id':'audit-mit','makloon_name':'Audit','input_unit':'yard','material_losses':losses}]})
    recap=await mr.recap()
    out.append({'id':'AUD-MKL-02','scenario':'1001 matching loss detail rows','reported_events':recap['partners'][0]['loss_events'],'detail_rows':len(recap['rows']),'expense_total':recap['totals']['loss_expense'],'detail_expense_sum':sum(x['expense'] for x in recap['rows'])})
    (base/'output/audit-plan-2026-10-19/evidence/export-consistency.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2));client.close()
asyncio.run(main())
