"""Original public PD/LPJ APIs with independent cash/GL arithmetic oracles."""
import asyncio,json,traceback
from pathlib import Path
import wave2_env as e
from services import gl_service as gl,cash_advance_service as ca

RESULTS=[];ERRORS=[];CONTEXT={}
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,
  status='pass' if want==actual else 'observed_difference'))
async def request(h,method,path,payload=None):
 r=await h.request(method,'/api/'+path,json=payload) if payload is not None else await h.request(method,'/api/'+path)
 return r
async def ok(h,method,path,payload=None):
 r=await request(h,method,path,payload)
 assert r.status_code==200,(method,path,r.status_code,r.text)
 return r.json()
async def net(account):
 entries=await e.db.journal_entries.find({'entity_id':'A','status':'posted'},{'_id':0}).to_list(None)
 return round(sum(float(l.get('debit') or 0)-float(l.get('credit') or 0) for j in entries for l in j.get('lines',[]) if l.get('account_code')==account),2)
async def state(cid,sid=None):
 return dict(ca=await e.db.cash_advances.find_one({'id':cid},{'_id':0}),
   settlement=await e.db.cash_advance_settlements.find_one({'id':sid},{'_id':0}) if sid else None,
   cash=await e.db.cash_transactions.find({'ref_id':{'$in':[cid,sid]}},{'_id':0}).to_list(None),
   journals=await e.db.journal_entries.find({'status':'posted'},{'_id':0}).to_list(None))
async def make(h,label):
 p={'entity_id':'A','divisi':'Audit MD','kegiatan':label,'payment_method':'transfer',
  'bank_detail':{'bank':'Synthetic','no_account':'LOCAL'},
  'lines':[{'description':'Audit expense','qty':2,'unit_price':50,'qty_roll':999,'yard':888,'kg':777}]}
 d=await ok(h,'POST','cash-advances',p)
 rec(label+'-amount-source',100,d['total_amount'],'Display-only roll/yard/kg breakdown must not multiply the active qty.')
 await ok(h,'PATCH','cash-advances/'+d['id'],{'catatan':'Synthetic local lifecycle','payment_method':'tunai'})
 await ok(h,'POST','cash-advances/'+d['id']+'/submit')
 for status in ['pending_pimpinan','pending_finance','approved']:
  d=await ok(h,'POST','cash-advances/'+d['id']+'/approve',{'note':'Audit approval'})
  rec(label+'-'+status,status,d['status'])
 d=await ok(h,'POST','cash-advances/'+d['id']+'/disburse',{'cash_type':'kas_kecil'})
 rec(label+'-disbursed','disbursed',d['status'])
 return d
async def ordinary(h):
 for amount in [80,100,120]:
  label='CA90-'+str(amount);before_advance=await net('1-1400');before_payable=await net('2-1650')
  before_expense=await net('6-4100');d=await make(h,label)
  rec(label+'-advance-debit',100,round(await net('1-1400')-before_advance,2))
  st=await ok(h,'POST','cash-advance-settlements',{'cash_advance_id':d['id'],
   'expense_lines':[{'category':'atk','amount':amount,'description':'Synthetic actual expenses'}]})
  rec(label+'-remaining-amount',100-amount,st['sisa_kurang_dana'])
  dup=await request(h,'POST','cash-advance-settlements',{'cash_advance_id':d['id'],
   'expense_lines':[{'category':'atk','amount':amount}]})
  rec(label+'-duplicate-active-lpj',409,dup.status_code)
  st=await ok(h,'PATCH','cash-advance-settlements/'+st['id'],{'catatan':'Checked actual receipts'})
  await ok(h,'POST','cash-advance-settlements/'+st['id']+'/submit')
  st=await ok(h,'POST','cash-advance-settlements/'+st['id']+'/approve')
  rec(label+'-expense-gl',amount,round(await net('6-4100')-before_expense,2))
  rec(label+'-remaining-advance-gl',max(100-amount,0),round(await net('1-1400')-before_advance,2))
  rec(label+'-reimburse-liability-gl',-max(amount-100,0),round(await net('2-1650')-before_payable,2))
  repeat=await request(h,'POST','cash-advance-settlements/'+st['id']+'/approve')
  rec(label+'-repeat-approval',409,repeat.status_code)
  if amount>100:
   report=await ok(h,'GET','cash-advance-settlements/reimburse-payables')
   rec(label+'-payable-report',20,report['total_outstanding'])
   await ok(h,'POST','cash-advance-settlements/'+st['id']+'/pay-reimburse',{'cash_type':'kas_besar'})
   rec(label+'-reimburse-payment-gl',0,round(await net('2-1650')-before_payable,2))
   repeat=await request(h,'POST','cash-advance-settlements/'+st['id']+'/pay-reimburse',{})
   rec(label+'-repeat-reimbursement',409,repeat.status_code)
  cash=await e.db.cash_transactions.find({'ref_id':{'$in':[d['id'],st['id']]}},{'_id':0}).to_list(None)
  rec(label+'-cash-conservation',max(100,amount),round(sum(x['amount'] for x in cash if x['direction']=='out'),2))
  CONTEXT[label]=await state(d['id'],st['id'])
async def rejected(h):
 d=await ok(h,'POST','cash-advances',{'lines':[{'qty':1,'unit_price':10}]})
 await ok(h,'POST','cash-advances/'+d['id']+'/submit')
 await ok(h,'POST','cash-advances/'+d['id']+'/reject',{'note':'Needs correction'})
 d=await ok(h,'PATCH','cash-advances/'+d['id'],{'lines':[{'qty':2,'unit_price':10}]})
 rec('CA90-rejected-revision-total',20,d['total_amount'])
 await ok(h,'POST','cash-advances/'+d['id']+'/submit')
 rec('CA90-premature-disbursement',409,(await request(h,'POST','cash-advances/'+d['id']+'/disburse',{})).status_code)
 for label,p,status in [('zero',{'lines':[{'qty':0,'unit_price':10}]},400),
  ('negative',{'lines':[{'qty':-1,'unit_price':10}]},422),
  ('empty',{'lines':[]},400),('invalid-payment',{'payment_method':'barter','lines':[{'qty':1,'unit_price':10}]},400)]:
  rec('CA90-validation-'+label,status,(await request(h,'POST','cash-advances',p)).status_code)
 await ok(h,'PATCH','expense-categories/atk',{'label':'ATK local test','account_code':'6-4100'})
 rec('CA90-invalid-expense-account',400,(await request(h,'PATCH','expense-categories/atk',{'account_code':'NONEXISTENT'})).status_code)
 for path in ['cash-advances?status=draft','cash-advance-settlements?status=posted_to_gl','expense-categories?active_only=true']:
  rec('CA90-read-'+path,200,(await request(h,'GET',path)).status_code)
async def main():
 await e.seed()
 await e.db.users.update_one({'id':'U'},{'$set':{'role':'admin','allowed_entity_ids':['A','B']}})
 await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{
  'cash_advance':['view','create','update','submit','approve','reject','disburse'],
  'cash_settlement':['view','create','update','submit','approve','reject','manage'],
  'accounting':['view','create']}}})
 await gl.seed_default_coa();await ca.seed_expense_categories()
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),
  base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
  for fn in [ordinary,rejected]:
   try:await fn(h)
   except Exception as ex:ERRORS.append(dict(group=fn.__name__,error=repr(ex),traceback=traceback.format_exc()))
 out=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,
  observations=RESULTS,context=CONTEXT,harness_errors=ERRORS,
  scope='Original public APIs, real local Mongo; independent debit/credit arithmetic. Synthetic evidence, not physical receipts or all failure paths.')
 Path(__file__).with_name('cash-advance-lifecycle90-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 print(json.dumps(dict(observations=len(RESULTS),differences=[x for x in RESULTS if x['status']!='pass'],errors=ERRORS),ensure_ascii=False),flush=True)
 e.client.close()
asyncio.run(main())
