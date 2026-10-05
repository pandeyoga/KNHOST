import asyncio,json,subprocess
from pathlib import Path
import wave2_production_flow as f
from services import closing_service as c,gl_service as g
from core_utils import now_iso
e=f.e;db=e.db;p=f.p;results=[];actor={'name':'Audit','id':'U','role':'admin'}
def check(n,k,label,actual,expected):
 assert actual==expected,(n,actual,expected)
 results.append(dict(id='W2-PR-'+n,kind=k,label=label,observed=actual,expected=expected));print(results[-1],flush=True)
async def state(wo,tag):
 d=await db.mfg_work_orders.find_one({'id':wo['id']})
 rolls=await db.inventory_rolls.find({'product_id':tag+'O'}).to_list(100)
 jes=await db.journal_entries.find({'source_type':'production_output','source_id':wo['id']}).to_list(100)
 return dict(status=d['status'],output_qty=sum(x['length_remaining'] for x in rolls),output_rolls=len(rolls),recorded_rolls=len(d['produced_roll_ids']),je_id=d.get('je_id'),overhead_gl=sum(x['total_debit'] for x in jes),overhead_stock=sum(x['length_remaining']*x['unit_cost'] for x in rolls)-len(rolls)*200)
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes();await db.warehouses.insert_one(dict(id='WH',name='Audit',status='active'))
 bom,wo=await f.fixture('CLOSED');await p.release_work_order(wo['id'],f.scope,'Audit')
 period=now_iso()[:7];close=await c.close_period('month',period,actor,'A')
 try:await p.complete_work_order(wo['id'],f.scope,'Audit')
 except g.ClosedPeriodError:blocked=True
 else:blocked=False
 check('C01','control','Actual closed period rejects production overhead GL',blocked,True)
 s=await state(wo,'CLOSED')
 check('E01','wave1_extension','GN-06 closed-period failure leaves output with released WO',[s['status'],s['output_qty'],s['recorded_rolls'],s['overhead_gl']],['released',5,0,0])
 check('E02','wave1_extension','GN-06 closed-period failure has consumed both inputs',[await f.qty('CLOSEDA'),await f.qty('CLOSEDB')],[10,15])
 await c.reopen_period(close['id'],actor);done=await p.complete_work_order(wo['id'],f.scope,'Audit');s=await state(wo,'CLOSED')
 check('E03','wave1_extension','GN-06 reopening and retry creates output twice but records once',[s['status'],s['output_qty'],s['output_rolls'],s['recorded_rolls'],done['produced_qty']],['completed',10,2,1,5])
 check('E04','wave1_extension','GN-06 overhead stock30 but GL15 after recovery',[s['overhead_stock'],s['overhead_gl']],[30,15])
 # Same-WO stale completion: hold first caller after reading released WO, before BOM returns.
 bom,wo=await f.fixture('RACE');await p.release_work_order(wo['id'],f.scope,'Audit')
 orig=p.get_bom;arrived=asyncio.Event();resume=asyncio.Event();first=True
 async def delayed(bid,*args,**kw):
  nonlocal first
  value=await orig(bid,*args,**kw)
  if bid==bom['id'] and first:first=False;arrived.set();await asyncio.wait_for(resume.wait(),30)
  return value
 p.get_bom=delayed
 try:
  task=asyncio.create_task(p.complete_work_order(wo['id'],f.scope,'Audit'));await asyncio.wait_for(arrived.wait(),30)
  await p.complete_work_order(wo['id'],f.scope,'Audit');resume.set();await task
 finally:resume.set();p.get_bom=orig
 s=await state(wo,'RACE')
 check('E05','wave1_extension','GN-06 two callers create two outputs',[s['output_rolls'],s['output_qty'],s['recorded_rolls']],[2,10,1])
 check('E06','wave1_extension','GN-06 stale last writer clears link to posted overhead',[s['je_id'],s['overhead_gl'],s['overhead_stock']],['',15,30])
 # A released WO carrying partial effects can be cancelled without compensation.
 bom,wo=await f.fixture('CANCEL');await p.release_work_order(wo['id'],f.scope,'Audit')
 close=await c.close_period('month',period,actor,'A')
 try:await p.complete_work_order(wo['id'],f.scope,'Audit')
 except g.ClosedPeriodError:pass
 cancelled=await p.cancel_work_order(wo['id'],f.scope,'Audit','Synthetic cancellation after failed posting')
 s=await state(wo,'CANCEL')
 check('E07','wave1_extension','GN-06 cancel after GL failure leaves produced inventory',[cancelled['status'],s['output_qty'],s['overhead_gl'],await f.qty('CANCELA'),await f.qty('CANCELB')],['cancelled',5,0,10,15])
 assert not e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('production-recovery-results.json').write_text(json.dumps(dict(database=e.DBNAME,source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),mode='Real month close/reopen causes GL failure; actual WO/stock/GL; one scheduling barrier for same-WO concurrency; not process-crash or HTTP permission test',results=results),indent=2),encoding='utf-8');e.client.close()
