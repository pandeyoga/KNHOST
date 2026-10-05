"""Cash refund API, cash/GL reconciliation and injected ledger outage."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_sales_flow as s
e=s.e;db=e.db;results=[];observations=[]
def check(n,kind,label,actual,expected):
 assert actual==expected,(n,label,actual,expected)
 results.append(dict(id='W2-CR-'+n,kind=kind,label=label,observed=actual,expected=expected));print(results[-1],flush=True)
async def main():
 await s.main() # replayed fixture controls excluded from this result count
 order=await db.sales_orders.find_one({'status':'done'})
 # Deliberately seeded cash classification; original sale tender capture is NOT covered.
 await db.sales_orders.update_one({'id':order['id']},{'$set':{'payment_profile_method':'cash','payment_term_code':'cash'}})
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
  async def post(path,payload=None):
   r=await h.post('/api'+path,json=payload) if payload is not None else await h.post('/api'+path)
   assert r.status_code==200,(path,r.status_code,r.text)
   return r.json()
  async def inspected():
   r=await post('/sales-returns',{'order_id':order['id'],'submit_now':True,'items':[{'product_id':'P','quantity_returned':5,'unit':'meter'}]})
   rid=r['id'];await post(f'/sales-returns/{rid}/approve');await post(f'/sales-returns/{rid}/inspect/start')
   await post(f'/sales-returns/{rid}/inspect/complete',{'inspections':[{'index':0,'grade':'A','condition':'ok','disposition':'restock','accepted_qty':5}]})
   return rid
  async def cash(rid):return await db.cash_transactions.find({'ref_type':'sales_return','ref_id':rid},{'_id':0}).to_list(100)
  async def journals(rid):return await db.journal_entries.find({'source_id':rid},{'_id':0}).to_list(100)
  rid=await inspected();payload={'outcome':'refund','return_warehouse_id':'WH','refund_account_code':'1-1100'}
  ret=await post(f'/sales-returns/{rid}/settle',payload);cs=await cash(rid);js=await journals(rid)
  observations.append(dict(return_document=ret,cash=cs,journals=js))
  check('C01','control','Cash refund amount matches credit note',[ret['credit_note_amount'],len(cs),cs[0]['amount'],cs[0]['direction'],cs[0]['status']],[50000,1,50000,'out','posted'])
  delta=sum(l.get('credit',0)-l.get('debit',0) for j in js for l in j['lines'] if l['account_code']=='1-1100')
  check('C02','control','Refund GL cash credit matches cash book outflow',delta,50000)
  check('C03','control','Refund stock enters quarantine',await s.buckets(),{'available':80,'delivered':20,'quarantine':5})
  await post(f'/sales-returns/{rid}/settle',payload)
  check('C04','control','Sequential retry creates no extra cash or journal',[len(await cash(rid)),len(await journals(rid))],[len(cs),len(js)])
  await post(f'/sales-returns/{rid}/reverse',{'notes':'Synthetic correction'})
  check('C05','control','Reverse voids cash and removes returned stock',[(await cash(rid))[0]['status'],await s.buckets()],['void',{'available':80,'delivered':20}])
  js=await journals(rid)
  delta=sum(l.get('credit',0)-l.get('debit',0) for j in js for l in j['lines'] if l['account_code']=='1-1100')
  check('C06','control','Reversal nets original cash GL to zero',delta,0)
  rid=await inspected()
  from services import cash_ledger
  original=cash_ledger.record_return_cash
  async def fail(**kwargs):raise RuntimeError('AUDIT synthetic cash-ledger unavailable before write')
  cash_ledger.record_return_cash=fail
  try:ret=await post(f'/sales-returns/{rid}/settle',payload)
  finally:cash_ledger.record_return_cash=original
  observations.append(dict(failed_return=ret,cash=await cash(rid),journals=await journals(rid)))
  check('F01','defect','Ledger outage still returns settled refund with GL cash credit but no cash row',[ret['status'],len(await cash(rid)),sum(l.get('credit',0)-l.get('debit',0) for j in await journals(rid) for l in j['lines'] if l['account_code']=='1-1100')],['refund_settled',0,50000])
  await post(f'/sales-returns/{rid}/settle',payload)
  check('F02','defect','Retry after restoring ledger does not repair missing cash row',len(await cash(rid)),0)
  assert not e.blocked,e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('cash-refund-results.json').write_text(json.dumps(dict(database=e.DBNAME,source_commit=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),mode='Actual ASGI returns+Mongo+GL; delivered order replay then seeded cash classification, not tender capture; synthetic cash-ledger exception before write',results=results,observations=observations),indent=2),encoding='utf-8');e.client.close()
