"""Advance approval, disbursement, settlement and concurrent disbursement."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import cash_advance_service as s
from schemas_cash_advance import CashAdvanceCreate,CashAdvanceLine,DisburseInput,SettlementCreate,SettlementLine
from entity_scope import EntityContext
db=e.db;actor={'id':'U','name':'Audit Admin','role':'admin'};ctx=EntityContext(user=actor,active_entity_id='A',allowed_entity_ids=['A']);results=[]
def check(sid,kind,label,actual,expected):
 assert actual==expected,(sid,actual,expected)
 results.append({'id':sid,'kind':kind,'label':label,'observed':actual,'expected_reproduction':expected});print(json.dumps(results[-1]),flush=True)
async def advance(label):
 d=await s.create_cash_advance(CashAdvanceCreate(entity_id='A',kegiatan=label,lines=[CashAdvanceLine(description='Synthetic expense',qty=2,unit_price=50000)]),ctx,actor)
 d=await s.submit_cash_advance(d['id'],ctx,actor)
 stages=[]
 for _ in range(3):d=await s.approve_cash_advance(d['id'],'Audit',ctx,actor);stages.append(d['status'])
 return d,stages
async def settle(caid,amount):
 d=await s.create_settlement(SettlementCreate(cash_advance_id=caid,expense_lines=[SettlementLine(category='office_supplies',description='Synthetic',amount=amount)]),ctx,actor)
 d=await s.submit_settlement(d['id'],ctx,actor)
 return await s.approve_settlement(d['id'],ctx,actor)
async def cash(caid):
 rows=await db.cash_transactions.find({'ref_type':'cash_advance','ref_id':caid}).to_list(100)
 return [len(rows),sum(x['amount'] for x in rows)]
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 d,stages=await advance('NORMAL')
 check('W2-CA-C01','control','Three real approval stages',stages,['pending_pimpinan','pending_finance','approved'])
 d=await s.disburse_cash_advance(d['id'],DisburseInput(cash_type='kas_besar'),ctx,actor)
 check('W2-CA-C02','control','One approved advance gives one cash transaction',[d['status'],await cash(d['id'])],['disbursed',[1,100000]])
 try:await s.disburse_cash_advance(d['id'],DisburseInput(),ctx,actor)
 except Exception as ex:status=getattr(ex,'status_code',None)
 else:status=200
 check('W2-CA-C03','control','Sequential disburse retry rejected',[status,await cash(d['id'])],[409,[1,100000]])
 st=await settle(d['id'],100000)
 je=await db.journal_entries.find_one({'id':st['journal_entry_id']})
 check('W2-CA-C04','control','Full settlement posts balanced expense journal',[st['status'],je['total_debit'],je['total_credit']],['posted_to_gl',100000,100000])
 try:await s.approve_settlement(st['id'],ctx,actor)
 except Exception as ex:status=getattr(ex,'status_code',None)
 else:status=200
 check('W2-CA-C05','control','Repeated same settlement rejected',status,409)
 st2=await settle(d['id'],100000)
 entries=await db.journal_entries.find({'id':{'$in':[st['journal_entry_id'],st2['journal_entry_id']]}}).to_list(100)
 check('W2-CA-E01','wave1_extension','CX-05 second settlement credits advance again',[len(entries),sum(x['total_debit'] for x in entries),await cash(d['id'])],[2,200000,[1,100000]])
 d,_=await advance('RESIDUAL');await s.disburse_cash_advance(d['id'],DisburseInput(),ctx,actor)
 st=await settle(d['id'],80000);parent=await s.get_cash_advance(d['id'],ctx)
 check('W2-CA-E02','wave1_extension','CX-05 residual20k yet parent settled',[parent['status'],st['sisa_kurang_dana'],await cash(d['id'])],['settled',20000,[1,100000]])
 d,_=await advance('RACE');original=s.get_cash_advance;arrived=asyncio.Event();resume=asyncio.Event();first=True
 async def delayed(caid,context):
  nonlocal first
  doc=await original(caid,context)
  if caid==d['id'] and first:first=False;arrived.set();await asyncio.wait_for(resume.wait(),20)
  return doc
 s.get_cash_advance=delayed
 try:
  t=asyncio.create_task(s.disburse_cash_advance(d['id'],DisburseInput(),ctx,actor));await asyncio.wait_for(arrived.wait(),20)
  second=await s.disburse_cash_advance(d['id'],DisburseInput(),ctx,actor);resume.set();first_result=await t
 finally:resume.set();s.get_cash_advance=original
 check('W2-CA-E03','wave1_extension','CX-04 concurrent callers each disburse100k',[first_result['status'],second['status'],await cash(d['id'])],['disbursed','disbursed',[2,200000]])
 assert not e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('advance-results.json').write_text(json.dumps({'database':e.DBNAME,'source_commit':subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),'mode':'Actual services+Mongo+GL; synthetic admin context; one read barrier for concurrency, no bank transfers','results':results},indent=2),encoding='utf-8');e.client.close()
