"""Launch original app for an unchanged native script on a fresh local fixture."""
import asyncio,os,runpy,sys,threading,time,traceback,faulthandler,subprocess
from pathlib import Path

R=Path(os.environ['KNHOST_REPO']);sys.path[:0]=[str(R),str(R/'backend'),str(R/'scripts')]
port=int(os.environ.get('AUDIT_PORT','8014'));base='http://127.0.0.1:'+str(port)
os.environ.update(KN_DEMO_DATA='true',KN_INITIAL_PASSWORD='demo12345',KN_BASE=base+'/api',
 KN_BASE_URL=base,BACKEND_URL=base,KN_API=base+'/api',
 REACT_APP_BACKEND_URL=base,SESSION_COOKIE_SECURE='false')
os.environ.pop('BASE_URL',None)
_original_run=subprocess.run
def _runtime_adapter(args,*a,**kw):
 if isinstance(args,(list,tuple)) and args and args[0] in ('python3','python'):
  args=[sys.executable,*args[1:]]
 return _original_run(args,*a,**kw)
subprocess.run=_runtime_adapter
from motor.motor_asyncio import AsyncIOMotorClient
_original_loop=AsyncIOMotorClient.get_io_loop
def _local_audit_loop(self):
 # Native POCs use repeated asyncio.run while HTTP uses a separate thread.
 # Bind executor futures to the executing loop; business functions are unchanged.
 try:return asyncio.get_running_loop()
 except RuntimeError:return _original_loop(self)
AsyncIOMotorClient.get_io_loop=_local_audit_loop
from db import db,client
assert db.name.startswith('knhost_audit_native90_')
faulthandler.dump_traceback_later(55,repeat=True)
from coverage import Coverage
cov=Coverage.current()
def checkpoint():
 while True:
  time.sleep(5)
  if cov:cov.save()
threading.Thread(target=checkpoint,daemon=True).start()
async def init():
 if '-entry90.py' not in os.environ.get('AUDIT_ORIGINAL_SCRIPT',''):
  for _ in range(1800):
   if not (Path(__file__).parent/'pause-native-dispatch').exists():break
   await asyncio.sleep(.1)
 await client.admin.command('ping')
 assert await db.users.count_documents({})==0
 lock=Path(__file__).parent/'template-bootstrap-in-progress'
 for _ in range(1200):
  if not lock.exists():break
  await asyncio.sleep(.1)
 if lock.exists():raise RuntimeError('Audit fixture bootstrap did not finish')
 template=client['knhost_audit_native90_template']
 if await template.users.count_documents({})>0:
  for name in await template.list_collection_names():
   docs=await template[name].find({}).to_list(None)
   if docs:await db[name].insert_many(docs)
 else:
  from seed_realistic import seed_all
  await seed_all(db)
  for name in await db.list_collection_names():
   docs=await db[name].find({}).to_list(None)
   if docs:await template[name].insert_many(docs)
 from indexes import ensure_performance_indexes
 await ensure_performance_indexes()
asyncio.run(init());client._io_loop=None
import uvicorn
appserver=uvicorn.Server(uvicorn.Config('server:app',host='127.0.0.1',port=port,
 lifespan='off',access_log=False,log_level='error'))
thread=threading.Thread(target=appserver.run,daemon=True);thread.start()
for _ in range(1600):
 if appserver.started:break
 if not thread.is_alive():raise RuntimeError('Native audit server stopped before readiness')
 time.sleep(.1)
if not appserver.started:raise RuntimeError('Native audit server readiness timeout')
faulthandler.cancel_dump_traceback_later()
target=Path(os.environ['AUDIT_ORIGINAL_SCRIPT']);sys.argv=[str(target)]
asyncio.set_event_loop(asyncio.new_event_loop())
print('NATIVE90_READY',db.name,target.name,flush=True)
try:
 original_path=R/'backend'/target.name
 if not original_path.exists():original_path=target
 namespace={'__name__':'__main__','__file__':str(original_path),'__package__':None,'__builtins__':__builtins__}
 exec(compile(target.read_text(encoding='utf-8-sig'),str(original_path),'exec'),namespace)
finally:
 appserver.should_exit=True;thread.join(10)
 client.close()
