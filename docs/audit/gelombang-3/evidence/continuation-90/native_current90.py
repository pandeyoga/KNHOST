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
print('CURRENT90_INIT',os.getpid(),db.name,flush=True)
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
print('CURRENT90_SERVER_READY',flush=True)

import contextlib,json,re
output=Path(__file__).parent
selected=os.environ['AUDIT_BATCH_NAMES'].split(',');rows=[]
async def reset_fixture():
 assert db.name.startswith('knhost_audit_native90_')
 for name in await db.list_collection_names():await db[name].delete_many({})
 for name in await client['knhost_audit_native90_template'].list_collection_names():
  docs=await client['knhost_audit_native90_template'][name].find({}).to_list(None)
  if docs:await db[name].insert_many(docs)

import requests
os.environ['KN_GATE_ALLOW_RESTORE']='1'
audit_tmp=Path(__file__).parent/'temp-files';audit_tmp.mkdir(exist_ok=True)
os.environ.update(TMP=str(audit_tmp),TEMP=str(audit_tmp),TMPDIR=str(audit_tmp))
original_request=requests.sessions.Session.request
input_adaptations=[]
def current_sampling_input(self,method,url,**kw):
 body=kw.get('json')
 if method.upper()=='POST' and '/rounds/' in url and url.endswith('/submit') and isinstance(body,dict) and not body.get('performed_by_user_id'):
  identity=original_request(self,'GET',base+'/api/auth/me',headers=kw.get('headers',{}),timeout=30)
  performer=identity.json().get('id') if identity.status_code==200 else None
  if performer:
   kw['json']={**body,'performed_by_user_id':performer}
   input_adaptations.append(dict(url=url,added_field='performed_by_user_id',value=performer,reason='Current mandatory performer input; original assertions retained. Unadapted 422 was independently recorded.'))
 return original_request(self,method,url,**kw)
requests.sessions.Session.request=current_sampling_input

# The environment adapter binds Motor futures to the executing loop. No business
# implementation is replaced; fixture reset occurs between completed scripts.
for name in selected:
 input_adaptations.clear()
 print('CURRENT90_RESET',name,flush=True)
 asyncio.set_event_loop(asyncio.new_event_loop());asyncio.run(reset_fixture())
 print('CURRENT90_TEST',name,flush=True)
 original_path=R/'backend'/name
 src=original_path.read_text(encoding='utf-8-sig')
 src=src.replace('/app/',R.as_posix()+'/')
 for old in ['http://localhost:8001','http://127.0.0.1:8001','https://kain-control.preview.emergentagent.com']:
  src=src.replace(old,base)
 src=src.replace('mongodb://localhost:27017','mongodb://127.0.0.1:27919').replace('mongodb://127.0.0.1:27017','mongodb://127.0.0.1:27919')
 sys.argv=[str(original_path)];asyncio.set_event_loop(asyncio.new_event_loop())
 log=output/(os.environ.get('AUDIT_BATCH_PREFIX','native-current90-')+original_path.stem+'.log');started=time.time();code=0
 with log.open('w',encoding='utf-8') as h,contextlib.redirect_stdout(h),contextlib.redirect_stderr(h):
  try:exec(compile(src,str(original_path),'exec'),{'__name__':'__main__','__file__':str(original_path),'__package__':None,'__builtins__':__builtins__})
  except SystemExit as ex:code=ex.code if isinstance(ex.code,int) else (0 if ex.code is None else 1)
  except BaseException:code=1;traceback.print_exc()
 raw=log.read_text(encoding='utf-8',errors='replace')
 rows.append(dict(script='backend/'+name,database=db.name,exit=code,seconds=round(time.time()-started,2),log=str(log.relative_to(output)),
  pass_log_tokens=len(re.findall(r'(?:\[PASS\]|\bPASS\b)',raw)),fail_log_tokens=len(re.findall(r'(?:\[FAIL\]|\bFAIL\b)',raw)),
  input_adaptations=list(input_adaptations),note='Current-contract input adapter supplies mandatory sampling performer only; original assertions retained. Shared imported app with fixture reset. Independent isolated reproduction required for a finding.'))
 (output/(os.environ.get('AUDIT_BATCH_PREFIX','native-current90-')+'results.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 if cov:cov.save()
 print(json.dumps(rows[-1]),flush=True)
appserver.should_exit=True;thread.join(10);client.close()
