import asyncio,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import wave2_env as e
from services import profitability_service as prof,cashflow_forecast_service as fc
from services.customer_service import _term_days

async def main():
    await e.seed()
    db=e.db; now=datetime.now(timezone.utc); stamp=now.isoformat(); results=[]
    def rec(id,expected,actual,note=''):
        results.append(dict(id=id,expected=expected,actual=actual,note=note,status='pass' if expected==actual else 'observed_difference'))
    await db.users.update_one({'id':'U'},{'$set':{'role':'finance','allowed_entity_ids':['A']}})
    await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance':{'accounting':['view']}}})
    await db.products.insert_one({'id':'P','name':'Synthetic','base_unit':'meter'})
    await db.sales_orders.insert_one({'id':'R','number':'R','entity_id':'A','customer_id':'C','created_at':stamp,'status':'reserved','grand_total':100,'total_amount':100,'items':[{'product_id':'P','quantity':1,'base_quantity':1,'line_total':100,'unit_cost':20}]})
    r=await prof.profitability(scope={'entity_id':'A'},entity_id='A')
    rec('D4-FIN-04-unshipped-as-realisation',0,r['totals']['revenue'],'0 expected only for the UI label Pendapatan (Realisasi). A booked-order forecast may legitimately be 100 but needs a different definition and label. No shipment or GL revenue was created.')
    async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
        resp=await h.get('/api/finance/profitability?entity_id=A')
    rec('D4-FE-03-redacted-hpp',{'status':200,'has_cogs':False},{'status':resp.status_code,'has_cogs':'cogs' in resp.json().get('totals',{})},'Positive control: backend redacts cost correctly. The separate JS probe verifies the renderer falsely formats the omitted field as Rp0.')
    cust={'id':'C','entity_id':'A','payment_profile':{'method':'tempo','term_days':30}}
    await db.customers.insert_one(cust)
    await db.sales_orders.delete_many({})
    order={'id':'TERMS','number':'TERMS','entity_id':'A','customer_id':'C','status':'confirmed','grand_total':100,'total_amount':100,'paid_total':0,'payment_profile_method':'tempo','payment_term_days':90,'created_at':stamp}
    await db.sales_orders.insert_one(order)
    r=await fc.cashflow_forecast({'entity_id':'A'},'A')
    rec('D4-FIN-02-order-terms', (now+timedelta(days=_term_days(cust,order))).date().isoformat(),r['ar_items'][0]['due_date'],'The original canonical customer_service helper honours the order snapshot of 90 days; forecast uses the current customer default of 30 days.')
    Path(__file__).with_name('additional-metric-results.json').write_text(json.dumps({'commit':'a904d989b622f7da14c4892d03cf6ef0c43f3084','results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False))
asyncio.run(main())
