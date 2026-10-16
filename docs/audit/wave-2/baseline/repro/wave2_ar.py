"""W2-06 AR receipt, deposit and reversal. Real API/services, local synthetic Mongo."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import ar_receipt_service as ar, gl_service as gl
from indexes import ensure_performance_indexes
db=e.db;results=[]
def record(sid,data,ok,kind='control'):
    assert ok,(sid,data)
    results.append({'id':sid,'kind':kind,'observed':data});print(sid,json.dumps(data),flush=True)
async def customer(cid):
    await db.customers.insert_one({'id':cid,'name':cid,'entity_id':'A','deposit_balance':0,'status':'active'})
async def order(oid,cid,total,entity='A'):
    await db.sales_orders.insert_one({'id':oid,'number':oid,'entity_id':entity,'customer_id':cid,
      'customer_name':cid,'status':'shipped','grand_total':total,'subtotal':total,'tax_amount':0,
      'payments':[],'paid_total':0,'payment_status':'unpaid','payment_profile_method':'tempo',
      'created_at':'2026-09-01T00:00:00+00:00','items':[]})
    await gl.post_order_revenue_and_cogs(oid)
async def receipt(h,cid,amount,alloc=None,dep=0):
    return await h.post('/api/ar-receipts',json={'customer_id':cid,'amount':amount,'method':'transfer',
        'use_deposit_amount':dep,'allocations':alloc or []})
async def void(h,rid):return await h.post(f'/api/ar-receipts/{rid}/void',params={'reason':'Synthetic audit reversal'})
async def state(cid):
    orders=await db.sales_orders.find({'customer_id':cid}).to_list(100)
    receipts=await db.ar_receipts.find({'customer_id':cid}).to_list(100)
    cash=await db.cash_transactions.find({'ref_id':{'$in':[r['id'] for r in receipts]}}).to_list(100)
    return {'deposit':(await db.customers.find_one({'id':cid}))['deposit_balance'],
      'orders':{o['id']:{'paid':sum(p['amount'] for p in o['payments']),'paid_total':o['paid_total'],'status':o['payment_status']} for o in orders},
      'receipts':[{'id':r['id'],'status':r['status'],'amount':r['amount'],'used_deposit':r['used_deposit'],
                   'applied':r['applied_total'],'locked':bool(r.get('saga_lock'))} for r in receipts],
      'active_cash':sum(c['amount'] for c in cash if c['status']!='void'),
      'void_cash':sum(c['amount'] for c in cash if c['status']=='void')}
async def ledger():
    totals={}
    async for j in db.journal_entries.find({'status':{'$ne':'void'}}):
      for l in j['lines']:
        c=l['account_code'];totals[c]=round(totals.get(c,0)+l.get('debit',0)-l.get('credit',0),2)
    return totals
def delta(before,after):return {k:round(after.get(k,0)-before.get(k,0),2) for k in set(before)|set(after) if round(after.get(k,0)-before.get(k,0),2)}
async def main():
    await e.seed();idx=await ensure_performance_indexes();assert idx['failed']==0 and not idx['unique']['failed']
    await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.ar_receipt':['create','view','void']}})
    async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),
        base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
      await customer('NORMAL');await order('N','NORMAL',100000);before=await ledger()
      r=await receipt(h,'NORMAL',100000,[{'order_id':'N','amount':100000}]);assert r.status_code==200,r.text
      rid=r.json()['id'];s=await state('NORMAL');d=delta(before,await ledger())
      record('W2-A-C01',{'http':r.status_code,'state':s,'gl_delta':d},s['orders']['N']['paid']==100000 and d.get('1-1200')==-100000 and s['active_cash']==100000)
      r=await void(h,rid);s=await state('NORMAL');d=delta(before,await ledger())
      record('W2-A-C02',{'http':r.status_code,'state':s,'gl_net_delta':d},r.status_code==200 and s['orders']['N']['paid']==0 and s['active_cash']==0 and not d)
      r=await void(h,rid);record('W2-A-C03',{'http':r.status_code},r.status_code==409)
      for cid in ['OVER','DUP','FOREIGN']:
        await customer(cid);await order(cid,cid,100000,'B' if cid=='FOREIGN' else 'A')
      r=await receipt(h,'OVER',100000,[{'order_id':'OVER','amount':120000}]);s=await state('OVER')
      record('W2-A-C04',{'http':r.status_code,'state':s},r.status_code==400 and not s['receipts'] and s['orders']['OVER']['paid']==0)
      r=await receipt(h,'DUP',120000,[{'order_id':'DUP','amount':60000},{'order_id':'DUP','amount':60000}]);s=await state('DUP')
      record('W2-A-C05',{'http':r.status_code,'state':s},r.status_code==400 and not s['receipts'])
      r=await receipt(h,'FOREIGN',100000,[{'order_id':'FOREIGN','amount':100000}]);s=await state('FOREIGN')
      record('W2-A-C06',{'http':r.status_code,'state':s},r.status_code==403 and not s['receipts'])
      await customer('MIX');fund=await receipt(h,'MIX',80000);assert fund.status_code==200,fund.text
      await order('MIX','MIX',100000);before=await ledger()
      r=await receipt(h,'MIX',20000,[{'order_id':'MIX','amount':100000}],80000);s=await state('MIX');d=delta(before,await ledger())
      record('W2-A-C07',{'http':r.status_code,'state':s,'gl_delta':d},r.status_code==200 and s['deposit']==0 and d.get('2-1400')==80000 and d.get('1-1200')==-100000)
      await customer('PURE');fund=await receipt(h,'PURE',100000);assert fund.status_code==200,fund.text
      await order('PURE','PURE',100000);before=await ledger()
      r=await receipt(h,'PURE',0,[{'order_id':'PURE','amount':100000}],100000);s=await state('PURE');d=delta(before,await ledger())
      record('W2-A-F01',{'http':r.status_code,'state':s,'gl_delta':d},r.status_code==200 and s['deposit']==0 and s['orders']['PURE']['paid']==100000 and not d,'defect')
      r=await void(h,r.json()['id']);s=await state('PURE')
      record('W2-A-C08',{'http':r.status_code,'state':s},r.status_code==200 and s['deposit']==100000 and s['orders']['PURE']['paid']==0)
      await customer('UNSPENT');r=await receipt(h,'UNSPENT',100000);rid=r.json()['id']
      r=await void(h,rid);s=await state('UNSPENT')
      record('W2-A-C09',{'http':r.status_code,'state':s},r.status_code==200 and s['deposit']==0 and s['active_cash']==0)

      # Source receipt overpays 100k; deposit is spent by a second receipt.
      await customer('SPENT');await order('S1','SPENT',50000)
      r=await receipt(h,'SPENT',150000,[{'order_id':'S1','amount':50000}]);assert r.status_code==200,r.text
      source=r.json()['id'];await order('S2','SPENT',100000)
      r=await receipt(h,'SPENT',0,[{'order_id':'S2','amount':100000}],100000);assert r.status_code==200,r.text
      before=await ledger();r=await void(h,source);s=await state('SPENT');d=delta(before,await ledger())
      sr=next(x for x in s['receipts'] if x['id']==source)
      record('W2-A-F02',{'http':r.status_code,'state':s,'gl_delta':d},r.status_code==409 and sr['status']=='posted' and sr['locked'] and s['void_cash']==150000 and s['orders']['S1']['paid']==0,'defect')

      # Two disjoint orders, same deposit. Pause first caller AFTER balance snapshot.
      await customer('RACE');r=await receipt(h,'RACE',100000);assert r.status_code==200,r.text
      await order('R1','RACE',80000);await order('R2','RACE',80000)
      original=ar.get_deposit_balance;arrived=asyncio.Event();release=asyncio.Event();first=True
      async def balance_barrier(cid):
        nonlocal first
        value=await original(cid)
        if cid=='RACE' and first:
          first=False;arrived.set();await release.wait()
        return value
      ar.get_deposit_balance=balance_barrier
      try:
        task=asyncio.create_task(receipt(h,'RACE',0,[{'order_id':'R1','amount':80000}],80000))
        await asyncio.wait_for(arrived.wait(),10)
        winner=await receipt(h,'RACE',0,[{'order_id':'R2','amount':80000}],80000)
        release.set();loser=await task
      finally:release.set();ar.get_deposit_balance=original
      s=await state('RACE')
      record('W2-A-F03',{'http':[winner.status_code,loser.status_code],'state':s},winner.status_code==200 and loser.status_code==409 and s['deposit']==20000 and sum(o['paid'] for o in s['orders'].values())==160000 and len(s['receipts'])==3,'defect')
      await customer('SERIAL');r=await receipt(h,'SERIAL',100000);await order('Q1','SERIAL',80000);await order('Q2','SERIAL',80000)
      a=await receipt(h,'SERIAL',0,[{'order_id':'Q1','amount':80000}],80000)
      b=await receipt(h,'SERIAL',0,[{'order_id':'Q2','amount':80000}],80000);s=await state('SERIAL')
      record('W2-A-C10',{'http':[a.status_code,b.status_code],'state':s},a.status_code==200 and b.status_code==400 and s['orders']['Q2']['paid']==0 and len(s['receipts'])==2)

      # Void saves a stale payments[] after a new receipt completed.
      await customer('LOST');await order('L','LOST',100000)
      old=await receipt(h,'LOST',40000,[{'order_id':'L','amount':40000}]);oldid=old.json()['id']
      original_db=ar.db;arrived=asyncio.Event();release=asyncio.Event()
      class Orders:
        def __getattr__(self,n):return getattr(db.sales_orders,n)
        async def update_one(self,q,u,*args,**kwargs):
          if q.get('id')=='L' and 'payments' in u.get('$set',{}):arrived.set();await release.wait()
          return await db.sales_orders.update_one(q,u,*args,**kwargs)
      class Proxy:
        def __getattr__(self,n):return Orders() if n=='sales_orders' else getattr(db,n)
      ar.db=Proxy();before=await ledger()
      try:
        task=asyncio.create_task(void(h,oldid));await asyncio.wait_for(arrived.wait(),10)
        new=await receipt(h,'LOST',60000,[{'order_id':'L','amount':60000}])
        release.set();v=await task
      finally:release.set();ar.db=original_db
      s=await state('LOST');d=delta(before,await ledger())
      record('W2-A-F04',{'http':[new.status_code,v.status_code],'state':s,'gl_delta':d},new.status_code==v.status_code==200 and s['orders']['L']['paid']==0 and s['active_cash']==60000,'defect')
      await customer('ORDERED');await order('O','ORDERED',100000)
      a=await receipt(h,'ORDERED',40000,[{'order_id':'O','amount':40000}]);await void(h,a.json()['id'])
      a=await receipt(h,'ORDERED',60000,[{'order_id':'O','amount':60000}]);s=await state('ORDERED')
      record('W2-A-C11',{'http':a.status_code,'state':s},a.status_code==200 and s['orders']['O']['paid']==60000 and s['active_cash']==60000)
    assert not e.blocked,e.blocked
async def run():
    completed=False
    try:await main();completed=True
    finally:
      (Path(__file__).resolve().parent.parent/'ar-results.json').write_text(json.dumps({
        'completed':completed,'commit':subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),
        'database':e.DBNAME,'level':'ASGI HTTP + Mongo + real GL; seeded shipped legacy SO; indexes initialized; no UI/hardware',
        'scenarios':results},indent=2),encoding='utf-8');e.client.close()
asyncio.run(run())
