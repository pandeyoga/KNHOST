import argparse,os,sys,socket,runpy,subprocess,json,platform,collections
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--script',required=True);a=p.parse_args()
repo=Path(a.repo).resolve();script=(Path(__file__).resolve().parent/a.script).resolve()
if not (repo/'backend/server.py').is_file():raise SystemExit('Path repo tidak valid')
if script.parent!=Path(__file__).resolve().parent:raise SystemExit('Script harus di folder repro workingcopy')
os.environ.update(KNHOST_REPO=str(repo),MONGO_URL='mongodb://127.0.0.1:27919/?serverSelectionTimeoutMS=3000',DB_NAME='knhost_data_audit_portable',PYTHON_DOTENV_DISABLED='1',KN_DEMO_DATA='false',SESSION_COOKIE_SECURE='false',CORS_ORIGINS='http://127.0.0.1:3000',REACT_APP_BACKEND_URL='http://127.0.0.1:8002',KN_API='http://127.0.0.1:8002/api',NO_PROXY='127.0.0.1,localhost,::1')
for k in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:os.environ.pop(k,None)
if not hasattr(os,'uname'):os.uname=lambda:collections.namedtuple('uname_result','sysname nodename release version machine')(*platform.uname()[:5])
original=socket.socket.connect
def connect(self,address):
    if not isinstance(address,tuple) or address[0] not in ('localhost','127.0.0.1','::1'):raise RuntimeError('External socket blocked')
    return original(self,address)
socket.socket.connect=connect
sys.path[:0]=[str(script.parent),str(repo/'backend'),str(repo)];os.chdir(repo/'backend');sys.argv=[str(script)]
actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
(script.parent/'actual-run-context.json').write_text(json.dumps(dict(actual_commit=actual,repo=str(repo),script=script.name,note='Embedded historical SHA in probes is not actual patch SHA. Use this context for rerun provenance.'),indent=2),encoding='utf-8')
runpy.run_path(str(script),run_name='__main__')
