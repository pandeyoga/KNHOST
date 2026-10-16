"""Public original ASGI endpoints; fresh synthetic database, no business-function mocks."""
import asyncio,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import wave2_env as e
async def main():
 await e.seed()
 await e.db.users.update_one({'id':'U'},{'$set':{'role':'admin'}})
 await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{'order':['view']}}})
 stamp=datetime.now(timezone.utc)
 docs=[{'id':f'O{i:02}','number':f'O{i:02}','entity_id':'A','customer_id':'C','customer_name':'Synthetic Customer',
        'status':'confirmed','order_type':'regular','created_at':(stamp-timedelta(minutes=i)).isoformat(),
        'items':[],'allocations':[],'total_amount':100,'grand_total':100} for i in range(30)]
 await e.db.sales_orders.insert_many(docs)
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=True),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
  dash=await h.get('/api/dashboard');stats=await h.get('/api/sales-orders/stats/summary')
 assert dash.status_code==stats.status_code==200,(dash.status_code,stats.status_code,dash.text,stats.text)
 result={'candidate':'a904d989b622f7da14c4892d03cf6ef0c43f3084','database':e.db.name,'mode':'Original public endpoints, thirty confirmed SOs100 each, same entity and time period.',
         'expected':{'total_orders':30,'revenue':3000,'average':100},'dashboard_orders':dash.json()['orders'],'summary':stats.json()}
 assert len(result['dashboard_orders'])==20 and result['summary']['revenue']['7d']=={'count':30,'grand_total':3000.0}, result
 (Path(__file__).parent/'order-dashboard-fixture.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'dashboard_orders':len(result['dashboard_orders']),'server_revenue':result['summary']['revenue']['7d']}),flush=True)
 e.client.close()
asyncio.run(main())
