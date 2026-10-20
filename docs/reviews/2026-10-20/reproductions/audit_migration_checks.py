import os,sys,asyncio,uuid,json,importlib.util,contextlib,io
from pathlib import Path
base=Path(__file__).resolve().parent.parent
root=base/'work/KNHOST-plan-audit-2026-10-19'
sys.path.insert(0,str(root/'backend'))
os.environ.update(MONGO_URL='mongodb://127.0.0.1:27138',DB_NAME='kn_migration_audit_'+uuid.uuid4().hex)
from db import db,client
spec=importlib.util.spec_from_file_location('audit_migration',root/'scripts/migrate_l03_ln033_fulfillment.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
async def run():
    for rid in ['empty','absent']:
        await db.purchase_orders.insert_one({'id':'po-'+rid,'po_number':'PO-'+rid,'status':'draft','items':[{'product_id':'p','quantity':10,'unit':'kg'}]})
        od={'id':'od-'+rid,'linked_po_id':'po-'+rid,'pricing':{'product_id':'p'}}
        if rid=='empty':od['fulfillment']={}
        await db.special_orders.insert_one(od)
    log=io.StringIO()
    with contextlib.redirect_stdout(log):await m.main('apply')
    report=json.loads(log.getvalue())
    empty=await db.special_orders.find_one({'id':'od-empty'},{'_id':0})
    absent=await db.special_orders.find_one({'id':'od-absent'},{'_id':0})
    results=[{'id':'AUD-MIG-01','scenario':'Apply legacy migration with empty fulfillment object versus missing field','reported_matched':report['counts']['matched'],'empty_object_result':empty.get('fulfillment'),'absent_field_result':absent.get('fulfillment'),'expected':'Both matched legacy orders get reference mapping, or report unsuccessful write explicitly'}]
    # Represent a legitimate subsequent operational update to a migrated item.
    await db.special_orders.update_one({'id':'od-absent'},{'$set':{'fulfillment.main.version':2,'fulfillment.main.route':'makloon','fulfillment.main.docs':[{'id':'mko-new','type':'mko'}],'fulfillment.main.history':[{'after':'makloon','reason':'approved operational change'}]}})
    await db.makloon_orders.insert_one({'id':'mko-new','special_order_id':'od-absent','status':'draft'})
    before=await db.special_orders.find_one({'id':'od-absent'},{'_id':0,'fulfillment':1})
    with contextlib.redirect_stdout(io.StringIO()):await m.main('rollback')
    after=await db.special_orders.find_one({'id':'od-absent'},{'_id':0,'fulfillment':1})
    results.append({'id':'AUD-MIG-02','scenario':'Rollback migration after mapped item has operational version 2 and new document link','before':before,'after':after,'new_mko_still_exists':bool(await db.makloon_orders.find_one({'id':'mko-new'})),'expected':'Refuse destructive rollback of changed migrated state; preserve subsequent operational links/history'})
    (base/'output/audit-plan-2026-10-19/evidence/migration-checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2));client.close()
asyncio.run(run())
