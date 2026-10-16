"""Manual GL dataset to reports and actual month close/reopen."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import gl_service as g,closing_service as c,financial_statement_service as f
from schemas_finance import JournalEntryCreate,JournalLineIn
db=e.db;results=[];actor={'id':'U','name':'Audit','role':'admin'}
def check(n,kind,label,actual,expected):
 assert actual==expected,(n,label,actual,expected)
 results.append(dict(id='W2-GL-'+n,kind=kind,label=label,observed=actual,expected=expected));print(results[-1],flush=True)
async def entry(dr,cr,amt,date='2026-09-15',eid='A'):
 return await g.create_manual_entry(JournalEntryCreate(date=date,entity_id=eid,description='Synthetic audit GL',lines=[JournalLineIn(account_code=dr,debit=amt),JournalLineIn(account_code=cr,credit=amt)]),actor)
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes();await g.seed_default_coa()
 await entry('1-1100','3-1000',100000)
 revenue=await entry('1-1100','4-1000',20000)
 await entry('6-1000','1-1100',5000)
 await entry('1-1100','3-1000',700000,eid='B')
 tb=await g.trial_balance(as_of='2026-09-30',scope={'entity_id':'A'})
 check('C01','control','Scoped trial balance exact totals',[tb['total_debit'],tb['total_credit'],tb['balanced']],[120000,120000,True])
 cash=await g.account_ledger('1-1100',as_of='2026-09-30',scope={'entity_id':'A'})
 check('C02','control','Scoped cash GL excludes other entity',[cash['count'],cash['balance']],[3,115000])
 stmt=await f.income_statement(start='2026-09-01',end='2026-09-30',scope={'entity_id':'A'})
 check('C03','control','Income report matches independent arithmetic',[stmt['revenue_total'],stmt['opex_total'],stmt['net_income']],[20000,5000,15000])
 before=await db.journal_entries.count_documents({})
 try:await g.create_manual_entry(JournalEntryCreate(entity_id='A',lines=[JournalLineIn(account_code='1-1100',debit=20),JournalLineIn(account_code='3-1000',credit=10)]),actor)
 except ValueError:blocked=True
 else:blocked=False
 check('C04','control','Unbalanced entry rejected before journal insert',[blocked,await db.journal_entries.count_documents({})],[True,before])
 close=await c.close_period('month','2026-09',actor,'A')
 check('C05','control','Real month close records correct profit',[close['status'],close['net_income']],['closed',15000])
 try:await entry('1-1100','3-1000',1)
 except g.ClosedPeriodError:blocked=True
 else:blocked=False
 check('C06','control','Posting into closed month blocked without unlock',blocked,True)
 try:await c.close_period('month','2026-09',actor,'A')
 except ValueError:blocked=True
 else:blocked=False
 check('C07','control','Sequential repeated close rejected',blocked,True)
 reopened=await c.reopen_period(close['id'],actor)
 check('C08','control','Reopen voids closing journal',[reopened['status'],(await db.journal_entries.find_one({'id':close['journal_entry_id']}))['status']],['reopened','void'])
 await entry('1-1100','4-1000',3000)
 close=await c.close_period('month','2026-09',actor,'A')
 check('C09','control','Close again recalculates profit after additional posting',close['net_income'],18000)
 # Existing Wave1 FN-09: actual closed month is mutated without unlock.
 voided=await g.void_entry(revenue['id'],actor)
 rec=await db.period_closings.find_one({'id':close['id']})
 cash=await g.account_ledger('1-1100',as_of='2026-09-30',scope={'entity_id':'A'})
 check('E01','wave1_extension','FN-09 closed-month void changes cash GL while period remains closed',[voided['status'],rec['status'],rec['stale'],cash['balance']],['void','closed',True,98000])
 assert not e.blocked,e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('gl-close-results.json').write_text(json.dumps(dict(database=e.DBNAME,source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),mode='Actual GL report/closing services and Mongo; manually posted synthetic oracle dataset; no source subledger integration or HTTP permission test',results=results),indent=2),encoding='utf-8');e.client.close()
