"""Real GRN services and Mongo: staged receipts, multiple lines, cancellation."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import goods_receipt_service as g,goods_receipt_close_service as c
from services import uom_service as u,uom_rules_service as rules
from entity_scope import EntityContext
from schemas_goods_receipt import GRNCreateIn,GRNDnPatch,GRNLineIn,GRNDeclared,GRNTargetIn,GRNCountRollIn,GRNReasonIn
db=e.db
actor={'id':'U','name':'Audit User A','role':'finance'}
ctx=EntityContext(user=actor,active_entity_id='A',allowed_entity_ids=['A'])
results=[]
def check(n,label,actual,expected):
    assert actual==expected,(n,label,actual,expected)
    results.append({'id':f'W2-G-C{n:02}','kind':'control','label':label,'observed':actual,'expected':expected})
    print(results[-1],flush=True)
async def seed_po(tag,qty=100):
    pid='P'+tag;tid='T'+tag;poid='PO'+tag
    await db.products.insert_one({'id':pid,'name':pid,'sku':pid,'base_unit':'meter','harga_pokok':10,'grade':'A'})
    await db.purchase_orders.insert_one({'id':poid,'po_number':poid,'entity_id':'A','supplier_id':'SUP','supplier_name':'Supplier','status':'ordered','warehouse_id':'WH','items':[{'product_id':pid,'quantity':qty,'received_qty':0,'price':10,'unit':'meter'}]})
    await db.wms_tasks.insert_one({'id':tid,'flow_type':'inbound','entity_id':'A','warehouse_id':'WH','po_id':poid,'po_number':poid,'product_id':pid,'sku':pid,'status':'waiting_goods','unit':'meter','expected_qty':qty,'received_qty':0,'quantity':0,'qty_rolls_scanned':0})
    return pid,tid,poid
async def receipt(tag,tid,poid,lines):
    grn=await g.create_grn(GRNCreateIn(partner_type='supplier',partner_id='SUP',warehouse_id='WH',po_ids=[poid]),actor,ctx)
    gid=grn['id']
    grn=await g.manual_entry(gid,grn['version'],actor,ctx)
    grn=await g.patch_dn(gid,GRNDnPatch(expected_version=grn['version'],number='DN'+tag,date='2026-10-01'),actor,ctx)
    for qty,unit,lengths in lines:
        grn=await g.add_line(gid,GRNLineIn(expected_version=grn['version'],declared=GRNDeclared(qty=qty,unit=unit,rolls=len(lengths),lot='LOT'+tag),target=GRNTargetIn(type='po_task',task_id=tid),decision='accept'),actor,ctx)
    grn=await g.start_count(gid,grn['version'],actor,ctx)
    for i,(_,_,lengths) in enumerate(lines,1):
        for length in lengths:
            res=await g.add_counted_roll(gid,i,GRNCountRollIn(length=length,lot='LOT'+tag,expected_version=grn['version']),actor,ctx)
            grn=res['grn']
    return grn
async def finish(grn):
    grn=await c.finish_count(grn['id'],grn['version'],actor,ctx)
    return await c.close_grn(grn['id'],grn['version'],actor,ctx)
async def received(poid):
    return (await db.purchase_orders.find_one({'id':poid}))['items'][0]['received_qty']
async def active(poid):
    return await db.wms_tasks.find({'po_id':poid,'status':{'$in':g.ACTIVE_TASK}},{'_id':0}).to_list(100)
async def main():
    await e.seed()
    import indexes
    await indexes.ensure_performance_indexes()
    await db.uoms.insert_many([dict(x) for x in u.UOM_SEED_ROWS]);u.invalidate_vocab()
    await rules.ensure_defaults()
    await db.warehouses.insert_one({'id':'WH','name':'Audit Warehouse','status':'active'})
    await db.suppliers.insert_one({'id':'SUP','name':'Supplier'})
    pid,tid,poid=await seed_po('PART')
    grn=await receipt('PART1',tid,poid,[(40,'meter',[15,25])])
    check(1,'Before close: PO unchanged, counted quantity from two rolls',[await received(poid),grn['lines'][0]['counted']['qty'],grn['lines'][0]['counted']['rolls']],[0,40,2])
    first=await finish(grn);tasks=await active(poid)
    check(2,'First partial close posts40 and creates exactly one remainder60',[first['grn']['status'],await received(poid),len(tasks),tasks[0]['expected_qty']],['closed',40,1,60])
    rem=tasks[0]
    check(3,'Remainder has fresh counters and no active GRN',[rem['received_qty'],rem['quantity'],rem['qty_rolls_scanned'],rem.get('grn_active_id'),rem['grn_ids']],[0,0,0,None,[]])
    again=await c.ensure_remainder_task(poid,pid,actor['name'],tid)
    check(4,'Sequential remainder generation is idempotent',[again['created'],len(await active(poid))],[False,1])
    second=await receipt('PART2',rem['id'],poid,[(60,'meter',[60])])
    cancelled=await c.cancel_grn(second['id'],GRNReasonIn(expected_version=second['version'],reason='Cancel second delivery'),actor,ctx)
    oldrolls=await db.inventory_rolls.find({'grn_id':first['grn']['id']}).to_list(100)
    task=await db.wms_tasks.find_one({'id':rem['id']})
    check(5,'Cancel second receipt preserves first delivery and resets remainder',[cancelled['status'],await received(poid),len(oldrolls),task['received_qty'],await db.inventory_rolls.count_documents({'grn_id':second['id']})],['cancelled',40,2,0,0])
    third=await receipt('PART3',rem['id'],poid,[(20,'meter',[20]),(40,'meter',[10,30])])
    final=await finish(third)
    check(6,'Multiple lines for same task post once and fulfill PO',[final['grn']['status'],await received(poid),len(await active(poid)),len(final['results'])],['closed',100,0,1])
    rolls=await db.inventory_rolls.find({'po_id':poid}).to_list(100)
    check(7,'Physical quantities conserved across partials and cancelled receipt',[len(rolls),sum(r['length_remaining'] for r in rolls)],[5,100])
    task=await db.wms_tasks.find_one({'id':rem['id']})
    check(8,'Second task declared quantity sums both lines once',task['declared_qty_total'],60)
    pid,tid,poid=await seed_po('YARD',91.44)
    from services.receiving_uom_service import convert_doc_qty,ReceivingUomError
    task=await db.wms_tasks.find_one({'id':tid})
    try:await convert_doc_qty(task,'yard',100)
    except ReceivingUomError:missing=True
    else:missing=False
    check(13,'Supplier unit without required supplier item rejected',missing,True)
    await db.supplier_items.insert_one({'id':'SIYARD','supplier_id':'SUP','product_id':pid,'supplier_uom':'yard','conv_factor':0.9144,'status':'active','entity_id':'A'})
    await db.wms_tasks.update_one({'id':tid},{'$set':{'supplier_item_id':'SIYARD'}})
    yard=await receipt('YARD',tid,poid,[(100,'yard',[45.72,45.72])])
    check(9,'Supplier DN yard converted to meter before reconciliation',yard['lines'][0]['converted']['qty'],91.44)
    yard=await finish(yard)
    check(10,'Yard declaration closes against measured meter rolls',[yard['grn']['status'],await received(poid),len(await active(poid))],['closed',91.44,0])
    pid,tid,poid=await seed_po('OVER',100)
    over=await receipt('OVER',tid,poid,[(60,'meter',[60]),(60,'meter',[60])])
    over=await c.finish_count(over['id'],over['version'],actor,ctx)
    blockers=[x['kind'] for x in c.open_blockers(over['discrepancies'])]
    check(11,'Remaining guard aggregates multiple lines of same task',blockers,['over_remaining'])
    try:await c.close_grn(over['id'],over['version'],actor,ctx)
    except Exception as ex:status=getattr(ex,'status_code',None)
    else:status=200
    check(12,'Over receipt close rejected without posting PO',[status,await received(poid)],[400,0])
    assert not e.blocked,e.blocked
if __name__=='__main__':
    try:asyncio.run(main())
    finally:
        Path(__file__).resolve().parents[1].joinpath('grn-partial-results.json').write_text(json.dumps({'source_commit':subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),'database':e.DBNAME,'mode':'Actual GRN services and Mongo, full indexes, synthetic fixtures, no browser or hardware','results':results},indent=2),encoding='utf-8')
        e.client.close()
