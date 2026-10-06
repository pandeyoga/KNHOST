import asyncio,os
from db import db,client
async def init():
 await client.admin.command('ping');assert db.name.startswith('knhost_data_audit_')
 import seed_realistic
 await client.drop_database(db.name) # only the specifically named task-owned synthetic DB
 await seed_realistic.seed_all(db)
 import indexes
 await indexes.ensure_performance_indexes()
 from services.rfid_service import migrate_epc_canonical,retire_orphan_tags
 await migrate_epc_canonical();await retire_orphan_tags()
 print('AUDIT_SERVER_READY',db.name,flush=True)
asyncio.run(init());client._io_loop=None
import uvicorn
uvicorn.run('server:app',host='127.0.0.1',port=int(os.environ['AUDIT_PORT']),lifespan='off',access_log=False)
