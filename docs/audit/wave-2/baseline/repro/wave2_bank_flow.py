import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import bank_service as b
from schemas_finance import BankAccountCreate
db=e.db;results=[]
def check(n,k,label,actual,expected):
 assert actual==expected,(n,actual,expected)
 results.append(dict(id='W2-BANK-'+n,kind=k,label=label,observed=actual,expected=expected));print(results[-1],flush=True)
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 acc=await b.create_account(BankAccountCreate(name='Synthetic bank',account_type='bank',entity_id='A',opening_balance=100),{'name':'Audit'})
 aid=acc['id']
 check('E01','wave1_extension','FN-08 opening bank balance has no journal',[acc['balance'],await db.journal_entries.count_documents({})],[100,0])
 await db.cash_transactions.insert_many([dict(id='IN',number='IN',account_id=aid,entity_id='A',direction='in',amount=20,status='posted',txn_date='2026-09-01',reconciled=False),dict(id='OUT',number='OUT',account_id=aid,entity_id='A',direction='out',amount=5,status='posted',txn_date='2026-09-02',reconciled=False),dict(id='VOID',number='VOID',account_id=aid,entity_id='A',direction='in',amount=999,status='void',txn_date='2026-09-03')])
 ledger=await b.account_ledger(aid)
 check('C01','control','Bank opening plus in minus out excludes void',[ledger['balance'],ledger['txn_count']],[115,2])
 await b.reconcile_txn('IN',True);ledger=await b.account_ledger(aid)
 check('C02','control','Reconciled balance includes only matched inflow',[ledger['reconciled_balance'],ledger['unreconciled_count']],[120,1])
 ledger=await b.update_account(aid,{'opening_balance':200})
 check('E02','wave1_extension','FN-08 changing opening shifts balance without GL',[ledger['balance'],await db.journal_entries.count_documents({})],[215,0])
 # Separate account: no opening discrepancy, isolate list cap.
 acc=await b.create_account(BankAccountCreate(name='Capacity',account_type='bank',entity_id='A',opening_balance=0),{'name':'Audit'});aid=acc['id']
 await db.cash_transactions.insert_many([dict(id=f'CAP{i}',number=f'CAP{i:05}',account_id=aid,entity_id='A',direction='in',amount=1,status='posted',txn_date='2026-09-01',reconciled=True) for i in range(5000)])
 ledger=await b.account_ledger(aid)
 check('C03','control','At5000 boundary bank balance exact',ledger['balance'],5000)
 await db.cash_transactions.insert_one(dict(id='CAP5000',number='CAP05000',account_id=aid,entity_id='A',direction='in',amount=1,status='posted',txn_date='2026-09-02',reconciled=True))
 check('C04','control','Independent collection contains5001 posted inflows',await db.cash_transactions.count_documents({'account_id':aid,'status':'posted'}),5001)
 ledger=await b.account_ledger(aid)
 check('F01','defect','W2-021 bank ledger truncates total and reconciled balance',[ledger['balance'],ledger['reconciled_balance'],ledger['txn_count']],[5000,5000,5000])
 accounts=await b.list_accounts(scope={'entity_id':'A'});acc=next(x for x in accounts if x['id']==aid)
 check('F02','defect','W2-021 bank overview repeats truncated balance',acc['balance'],5000)
 assert not e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('bank-flow-results.json').write_text(json.dumps(dict(database=e.DBNAME,source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),mode='Actual bank account/reconciliation services; cash transactions seeded directly for arithmetic and capacity, not payment lifecycle',results=results),indent=2),encoding='utf-8');e.client.close()
