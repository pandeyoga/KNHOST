"""Actual report queries over large synthetic balanced posted-journal fixtures."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import gl_service as g,financial_statement_service as f
db=e.db;results=[]
def check(n,kind,label,actual,expected):
 assert actual==expected,(n,label,actual,expected)
 results.append(dict(id='W2-GCAP-'+n,kind=kind,label=label,observed=actual,expected=expected));print(results[-1],flush=True)
async def seed(start,end):
 for lo in range(start,end,2000):
  await db.journal_entries.insert_many([dict(id=f'J{i}',number=f'CAP-{i:07}',entity_id='A',status='posted',date='2026-09-15',source_type='manual',source_id='',description='Synthetic capacity fixture',total_debit=1,total_credit=1,lines=[dict(account_code='1-1100',debit=1,credit=0),dict(account_code='4-1000',debit=0,credit=1)]) for i in range(lo,min(lo+2000,end))])
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes();await g.seed_default_coa()
 await seed(0,50000)
 tb=await g.trial_balance(scope={'entity_id':'A'})
 check('C01','control','At50k boundary report agrees with fixture',[tb['total_debit'],tb['total_credit']],[50000,50000])
 await seed(50000,50001)
 check('C02','control','Independent Mongo sum confirms50001 posted units',(await db.journal_entries.aggregate([{'$match':{'entity_id':'A','status':'posted'}},{'$group':{'_id':None,'total':{'$sum':'$total_debit'}}}]).to_list(1))[0]['total'],50001)
 tb=await g.trial_balance(scope={'entity_id':'A'});ledger=await g.account_ledger('1-1100',scope={'entity_id':'A'})
 check('F01','defect','TB silently truncates and still reports balanced',[tb['total_debit'],tb['total_credit'],tb['balanced']],[50000,50000,True])
 check('F02','defect','Account ledger silently omits one posted cash debit',[ledger['count'],ledger['balance']],[50000,50000])
 stmt=await f.income_statement(start='2026-09-01',end='2026-09-30',scope={'entity_id':'A'})
 check('C03','control','Income statement includes50001 unlike TB',stmt['revenue_total'],50001)
 await seed(50001,100001)
 check('C04','control','All100001 fixture entries exist',await db.journal_entries.count_documents({'entity_id':'A','status':'posted'}),100001)
 stmt=await f.income_statement(start='2026-09-01',end='2026-09-30',scope={'entity_id':'A'})
 check('F03','defect','Income statement reaches its own100k truncation boundary',stmt['revenue_total'],100000)
 assert not e.blocked,e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('gl-capacity-results.json').write_text(json.dumps(dict(database=e.DBNAME,source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),mode='Actual report services+indexed Mongo; bulk-seeded balanced journals, not100001 business posting calls; no timing/performance conclusion',results=results),indent=2),encoding='utf-8');e.client.close()
