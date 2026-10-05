"""Multi-PO receipt isolation with real services and indexed Mongo."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_grn_partial as p
e=p.e;db=p.db;results=[]
def check(n,label,actual,expected):
 assert actual==expected,(n,label,actual,expected)
 results.append(dict(id=f'W2-MPO-C{n:02}',kind='control',label=label,observed=actual,expected=expected));print(results[-1],flush=True)
async def make(tag):
 refs=[await p.seed_po(tag+'A',10),await p.seed_po(tag+'B',20)]
 g=await p.g.create_grn(p.GRNCreateIn(partner_type='supplier',partner_id='SUP',warehouse_id='WH',po_ids=[x[2] for x in refs]),p.actor,p.ctx)
 g=await p.g.manual_entry(g['id'],g['version'],p.actor,p.ctx)
 g=await p.g.patch_dn(g['id'],p.GRNDnPatch(expected_version=g['version'],number='DN'+tag,date='2026-10-03'),p.actor,p.ctx)
 for ref,qty in zip(refs,[10,12]):
  g=await p.g.add_line(g['id'],p.GRNLineIn(expected_version=g['version'],declared=p.GRNDeclared(qty=qty,unit='meter',rolls=1,lot=tag),target=p.GRNTargetIn(type='po_task',task_id=ref[1]),decision='accept'),p.actor,p.ctx)
 g=await p.g.start_count(g['id'],g['version'],p.actor,p.ctx)
 for i,qty in enumerate([10,12],1):
  g=(await p.g.add_counted_roll(g['id'],i,p.GRNCountRollIn(length=qty,lot=tag,expected_version=g['version']),p.actor,p.ctx))['grn']
 return g,refs
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 await db.uoms.insert_many([dict(x) for x in p.u.UOM_SEED_ROWS]);p.u.invalidate_vocab();await p.rules.ensure_defaults()
 await db.warehouses.insert_one({'id':'WH','name':'Audit','status':'active'})
 await db.suppliers.insert_one({'id':'SUP','name':'Audit supplier'})
 g,refs=await make('MULTI')
 check(1,'Counting two products leaves both PO receipts unchanged',[await p.received(x[2]) for x in refs],[0,0])
 done=await p.finish(g)
 check(2,'Close dispatches exactly two task groups',[done['grn']['status'],len(done['results'])],['closed',2])
 check(3,'Each PO receives its own measured quantity',[await p.received(x[2]) for x in refs],[10,12])
 a,b=[await p.active(x[2]) for x in refs]
 check(4,'Only partial PO creates remainder',[len(a),len(b),b[0]['expected_qty'],b[0]['product_id']],[0,1,8,refs[1][0]])
 rolls=await db.inventory_rolls.find({'grn_id':g['id']}).to_list(100)
 check(5,'Rolls retain independent PO product ownership',sorted([(x['po_id'],x['product_id'],x['length_remaining'],x['status'],x['owner_entity_id']) for x in rolls]),sorted([(x[2],x[0],q,'quarantine','A') for x,q in zip(refs,[10,12])]))
 rem=await p.receipt('REST',b[0]['id'],refs[1][2],[(8,'meter',[8])]);await p.finish(rem)
 check(6,'Later receipt completes second PO without touching first',[await p.received(x[2]) for x in refs],[10,20])
 g,refs=await make('CANCEL')
 await p.c.cancel_grn(g['id'],p.GRNReasonIn(expected_version=g['version'],reason='Synthetic cancellation'),p.actor,p.ctx)
 check(7,'Cancel removes both products counted rolls',await db.inventory_rolls.count_documents({'grn_id':g['id']}),0)
 tasks=[await db.wms_tasks.find_one({'id':x[1]}) for x in refs]
 check(8,'Cancel resets both tasks and leaves both POs untouched',[[x.get('grn_active_id'),x['received_qty']] for x in tasks]+[[await p.received(x[2]) for x in refs]],[[None,0],[None,0],[0,0]])
 assert not e.blocked,e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('multi-po-results.json').write_text(json.dumps(dict(database=e.DBNAME,source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),mode='Actual services and Mongo indexes, synthetic masters, two PO and two products, same supplier and warehouse',results=results),indent=2),encoding='utf-8');e.client.close()
