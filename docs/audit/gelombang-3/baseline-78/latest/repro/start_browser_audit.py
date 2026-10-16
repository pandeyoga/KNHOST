"""Task-owned original app, synthetic thirty-order UI dataset, localhost only."""
import asyncio,json,os,threading,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
import wave2_env as e
from core_utils import hash_password
async def init():
 await e.seed()
 await e.db.users.update_one({'id':'U'},{'$set':{'role':'admin','password_hash':hash_password('AuditLocal123!'),'allowed_entity_ids':['A','B']}})
 await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{'order':['view','create'],'customer':['view'],'inventory':['view'],'reports':['view']}}})
 await e.db.customers.insert_one({'id':'C','code':'C','name':'Synthetic Customer','entity_id':'A','status':'active'})
 await e.db.products.insert_one({'id':'P','sku':'P','name':'Synthetic Product','base_unit':'meter','status':'active','price':100,'harga_pokok':50})
 now=datetime.now(timezone.utc)
 await e.db.sales_orders.insert_many([{'id':f'O{i:02}','number':f'O{i:02}','entity_id':'A','customer_id':'C','customer_name':'Synthetic Customer','status':'confirmed','order_type':'regular',
  'created_at':(now-timedelta(minutes=i)).isoformat(),'items':[{'product_id':'P','product_name':'Synthetic Product','quantity':1,'base_quantity':1,'price':100,'unit':'meter'}],
  'allocations':[],'total_amount':100,'grand_total':100} for i in range(30)])
 e.client._io_loop=None
 (Path(__file__).resolve().parents[1]/'evidence/browser-server-context.json').write_text(json.dumps({'candidate':'a904d989b622f7da14c4892d03cf6ef0c43f3084','database':e.db.name,'pid':os.getpid(),'port':8006,'expected':{'eligible_orders':30,'revenue':3000,'average':100},'fixture':'Synthetic documents; original application and rendering. Not production data or full sales lifecycle.'}),encoding='utf-8')
 print('BROWSER_AUDIT_READY',e.db.name,flush=True)
asyncio.run(init())
import uvicorn
server=uvicorn.Server(uvicorn.Config(e.server.app,host='127.0.0.1',port=8006,lifespan='off',access_log=False));stop=Path(__file__).resolve().parents[1]/'evidence/stop-browser-server'
def monitor():
 while not server.should_exit:
  time.sleep(2)
  if stop.exists():server.should_exit=True
threading.Thread(target=monitor,daemon=True).start();server.run()
