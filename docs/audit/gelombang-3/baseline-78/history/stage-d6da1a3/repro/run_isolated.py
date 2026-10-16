"""Run original candidate code against task-owned localhost Mongo, with branch tracing."""
import collections,os,platform,runpy,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
for stream in (sys.stdout,sys.stderr):
 if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
REPO=Path(os.environ.get('KNHOST_REPO',ROOT/'work/KNHOST-data-audit-2026-10-05')).resolve()
OUT=Path(__file__).resolve().parents[1]
script=Path(sys.argv[1]).resolve()
os.environ.update(KNHOST_REPO=str(REPO),MONGO_URL='mongodb://127.0.0.1:27919/?serverSelectionTimeoutMS=3000',DB_NAME=os.environ.get('AUDIT_DB_NAME','knhost_data_audit_suite_20261005'),PYTHON_DOTENV_DISABLED='1',KN_DEMO_DATA='false',SESSION_COOKIE_SECURE='false',PYTHONIOENCODING='utf-8',CORS_ORIGINS='http://127.0.0.1:3000',REACT_APP_BACKEND_URL='http://localhost:8002',KN_API='http://localhost:8002/api',NO_PROXY='127.0.0.1,localhost,::1')
for key in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:os.environ.pop(key,None)
port=os.environ.get('AUDIT_PORT','8002')
os.environ.update(KN_API='http://127.0.0.1:'+port+'/api',REACT_APP_BACKEND_URL='http://127.0.0.1:'+port)
if not hasattr(os,'uname'):
 value=collections.namedtuple('uname_result','sysname nodename release version machine')(*platform.uname()[:5]);os.uname=lambda:value
old=socket.socket.connect
def connect(self,address):
 if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','localhost','::1'):raise RuntimeError('External network blocked in audit test process')
 return old(self,address)
socket.socket.connect=connect
sys.path[:0]=[str(script.parent),str(REPO/'backend'),str(REPO)]
os.chdir(REPO/'backend');sys.argv=[str(script),*sys.argv[2:]]
from coverage import Coverage
cov=Coverage(data_file=str(OUT/'evidence'/('.coverage.'+script.stem+'.'+os.environ.get('AUDIT_DB_NAME','probe'))),source=[str(REPO/'backend')],branch=True);cov.start()
try:runpy.run_path(str(script),run_name='__main__')
finally:cov.stop();cov.save()
