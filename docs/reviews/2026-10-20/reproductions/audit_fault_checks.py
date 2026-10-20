import os, sys, asyncio, uuid, json
from pathlib import Path
root=Path(__file__).resolve().parent/'KNHOST-plan-audit-2026-10-19'
sys.path.insert(0,str(root/'backend'))
os.environ.update(MONGO_URL='mongodb://127.0.0.1:27138',DB_NAME='kn_fault_audit_'+uuid.uuid4().hex)
from db import db,client
from services import special_order_fulfillment as sf, stock_count_roll_service as sc, gl_service as gl
from core_utils import now_iso
results=[]
async def main():
    await db.special_orders.insert_one({'id':'od-audit'})
    await sf._claim('od-audit','item','worker-A')
    await db.special_orders.update_one({'id':'od-audit'},{'$set':{'fulfillment_locks.item.at':'2000-01-01T00:00:00+00:00'}})
    await sf._claim('od-audit','item','worker-B')
    await sf._release('od-audit','item')
    after=await db.special_orders.find_one({'id':'od-audit'})
    results.append({'id':'AUD-SO-01','scenario':'Worker A completes after its lease expires and B acquires lease; A releases old lease','new_owner_lock_survives':'item' in after.get('fulfillment_locks',{}),'expected':True})
    roll={'id':'r-audit','roll_no':'AUDIT','product_id':'p-audit','warehouse_id':'wh-audit','owner_entity_id':'ent_ksc','bin_id':'b-audit','length_remaining':100,'unit':'yard','status':'available','unit_cost':10}
    await db.inventory_rolls.insert_one(roll)
    session={'id':'count-audit','warehouse_id':'wh-audit'}
    scan={'roll_id':'r-audit','live_qty':100,'live_bin_id':'b-audit','measured_qty':90}
    original=gl.post_cycle_count_variance
    async def injected_failure(**kwargs): raise RuntimeError('AUDIT injected transient journal outage')
    gl.post_cycle_count_variance=injected_failure
    try: await sc.apply_scan(session,scan,['qty_diff'],'Auditor')
    except RuntimeError as e: first=str(e)
    finally: gl.post_cycle_count_variance=original
    retry=await sc.apply_scan(session,scan,['qty_diff'],'Auditor')
    actual=await db.inventory_rolls.find_one({'id':'r-audit'})
    movements=await db.inventory_movements.count_documents({'roll_id':'r-audit'})
    results.append({'id':'AUD-WMS-01','scenario':'Transient GL failure after roll quantity/movement commit, retry same scan','first_error':first,'remaining_qty':actual['length_remaining'],'movement_count':movements,'retry':retry,'expected':'Resume missing journal and balance before mark applied; do not treat own partial commit as external recount'})
    out=Path(__file__).resolve().parent.parent/'output/audit-plan-2026-10-19/evidence/fault-checks.json'
    out.write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results,indent=2))
    client.close()
asyncio.run(main())
