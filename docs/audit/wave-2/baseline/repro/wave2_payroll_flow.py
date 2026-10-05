import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import hr_payroll_service as p,gl_service as g
db=e.db;results=[];actor={'id':'U','name':'Audit','role':'admin'}
def check(n,k,label,actual,expected):
 assert actual==expected,(n,actual,expected)
 results.append(dict(id='W2-PAY-'+n,kind=k,label=label,observed=actual,expected=expected));print(results[-1],flush=True)
async def denied(fn):
 try:await fn()
 except ValueError:return True
 return False
async def pay_http(rid,account):
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
  response=await h.post(f'/api/hr/payroll/runs/{rid}/pay',json={'cash_account':account})
  assert response.status_code==200,(response.status_code,response.text)
  return response.json()
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 await db.hr_employees.update_one({'id':'EMP'},{'$set':{'base_salary':100000,'allowances':[]}})
 await db.system_settings.insert_one({'scope':'hr','feature_toggles':{'bpjs_kesehatan':False,'bpjs_ketenagakerjaan':False,'pph21':False}})
 run=await p.create_run('A','2026-09',actor);rid=run['id']
 check('C01','control','Synthetic no-deduction payroll arithmetic',[run['totals']['gross'],run['totals']['net'],run['totals']['employees']],[100000,100000,1])
 check('C02','control','Approve draft rejected',await denied(lambda:p.approve_run(rid,actor)),True)
 check('C03','control','Pay before posting rejected',await denied(lambda:p.pay_run(rid,actor)),True)
 await p.submit_run(rid,actor)
 check('C04','control','Reject requires explanation',await denied(lambda:p.reject_run(rid,actor,'')),True)
 run=await p.reject_run(rid,actor,'Synthetic correction')
 check('C05','control','Reject returns draft with retained reason',[run['status'],run['reject_reason']],['draft','Synthetic correction'])
 await p.submit_run(rid,actor);await p.approve_run(rid,actor);run=await p.post_run_gl(rid,actor)
 je=await db.journal_entries.find_one({'id':run['journal_id']})
 check('C06','control','Accrual posts100k salary liability',[run['status'],je['total_debit'],je['total_credit']],['posted',100000,100000])
 run=await pay_http(rid,'1-1100')
 cash=await g.account_ledger('1-1100',scope={'entity_id':'A'});liability=await g.account_ledger('2-1600',scope={'entity_id':'A'})
 check('C07','control','Payroll payment clears salary liability',[run['status'],cash['balance'],liability['balance']],['paid',-100000,0])
 check('F01','defect','Paid payroll credits GL cash without any cash book transaction',[cash['balance'],await db.cash_transactions.count_documents({'entity_id':'A'})],[-100000,0])
 check('C08','control','Repeat pay blocked',await denied(lambda:p.pay_run(rid,actor)),True)
 again=await p.create_run('A','2026-09',actor)
 check('C09','control','Same period run creation returns existing paid run',[again['id'],again['status']],[rid,'paid'])
 # Account type validation: an existing postable expense account is accepted as payout account.
 run=await p.create_run('A','2026-10',actor);rid=run['id'];await p.submit_run(rid,actor);await p.approve_run(rid,actor);await p.post_run_gl(rid,actor)
 run=await pay_http(rid,'6-1000');je=await db.journal_entries.find_one({'id':run['paid_journal_id']})
 check('F02','defect','Payroll marked paid using salary expense as cash account',[run['status'],[(l['account_code'],l['credit']) for l in je['lines'] if l['credit']]],['paid',[('6-1000',100000)]])
 assert not e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('payroll-flow-results.json').write_text(json.dumps(dict(database=e.DBNAME,source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),mode='Actual payroll/GL services+Mongo, payment via ASGI; tax/BPJS disabled synthetic arithmetic fixture, no statutory accuracy conclusion, no bank transfer',results=results),indent=2),encoding='utf-8');e.client.close()
