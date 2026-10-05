"""Real ASGI + Motor/Mongo audit; synthetic localhost database only, no external network."""
import os,sys,json,asyncio,collections,platform,socket,traceback,uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta
B=Path(__file__).resolve().parent;REPO=Path(os.environ['KNHOST_REPO'])
DBNAME='knhost_audit_'+uuid.uuid4().hex
os.environ.update(MONGO_URL='mongodb://127.0.0.1:27919/?serverSelectionTimeoutMS=3000',DB_NAME=DBNAME,
                  PYTHON_DOTENV_DISABLED='1',KN_DEMO_DATA='false',CORS_ORIGINS='http://127.0.0.1:3000')
info=platform.uname();uv=collections.namedtuple('uname_result','sysname nodename release version machine')(*info[:5])
if not hasattr(os,'uname'):os.uname=lambda:uv
sys.path.insert(0,str(REPO/'backend'))
# Hard outbound boundary for test process; network downloads occur in separate setup processes.
connect=socket.socket.connect;connect_ex=socket.socket.connect_ex
blocked=[]
def guarded(self,address):
 if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','localhost','::1'):
  blocked.append(str(address));raise RuntimeError('Audit blocks external socket')
 return connect(self,address)
def guarded_ex(self,address):
 if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','localhost','::1'):return 10013
 return connect_ex(self,address)
socket.socket.connect=guarded;socket.socket.connect_ex=guarded_ex
import server,httpx
from db import db,client

async def seed():
 await client.admin.command('ping')
 assert db.name.startswith('knhost_audit_') and await db.users.count_documents({})==0
 await db.business_entities.insert_many([{'id':e,'short_name':e,'legal_name':'Audit '+e,'doc_prefix':e,'status':'active'} for e in ['A','B']])
 await db.users.insert_one({'id':'U','name':'Audit User A','email':'audit@example.invalid','role':'finance','status':'active','home_entity_id':'A','allowed_entity_ids':['A']})
 await db.sessions.insert_one({'token':'audit-local-session','user_id':'U','expires_at':datetime.now(timezone.utc)+timedelta(hours=2)})
 await db.permission_settings.insert_one({'id':'default','matrix':{'finance':{'esign':['view','sign'],'hr':['view','view_pii','manage_payroll','manage_attendance'],'ar_receipt':['create','view']}}})
 await db.hr_employees.insert_one({'id':'EMP','name':'Synthetic Employee','entity_id':'A','status':'active','base_salary':17300000})
