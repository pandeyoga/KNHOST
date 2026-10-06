import asyncio,os,threading,time,json
from pathlib import Path
from db import db,client
OUT=Path(__file__).resolve().parents[1]
async def init():
 await client.admin.command('ping');assert db.name=='knhost_data_audit_latest_pytest'
 import seed_realistic
 await client.drop_database(db.name)
 await seed_realistic.seed_all(db)
 import indexes
 await indexes.ensure_performance_indexes()
 from services.rfid_service import migrate_epc_canonical,retire_orphan_tags
 await migrate_epc_canonical();await retire_orphan_tags()
 print('AUDIT_SERVER_READY',db.name,flush=True)
asyncio.run(init());client._io_loop=None
import uvicorn
from coverage import Coverage
server=uvicorn.Server(uvicorn.Config('server:app',host='127.0.0.1',port=8006,lifespan='off',access_log=False))
cov=Coverage.current(); stop=OUT/'evidence/stop-server'
(OUT/'evidence/server-actual-pid.json').write_text(json.dumps({'pid':os.getpid(),'database':db.name,'port':8006}),encoding='utf-8')
def tick():
 while not server.should_exit:
  time.sleep(5)
  if cov:cov.save()
  if stop.exists():server.should_exit=True
threading.Thread(target=tick,daemon=True).start()
server.run()
if cov:cov.save()
