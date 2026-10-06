import os,sys,socket,uuid,atexit
from pathlib import Path
REPO=Path('C:\\Users\\abc\\Documents\\Codex\\2026-09-28\\sya\\work\\KNHOST-data-audit-latest-2026-10-05').resolve()
script=Path(sys.argv[0]).resolve() if sys.argv else Path('.')
# Only native candidate checkers on the audit-owned localhost database are traced.
if script.is_relative_to(REPO) and os.environ.get('DB_NAME','').startswith('knhost_audit_') and '127.0.0.1:27919' in os.environ.get('MONGO_URL',''):
 original=socket.socket.connect
 def connect(self,address):
  if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','localhost','::1'):raise RuntimeError('Native audit child blocks external sockets')
  return original(self,address)
 socket.socket.connect=connect
 from coverage import Coverage
 cov=Coverage(data_file=str(Path('C:\\Users\\abc\\Documents\\Codex\\2026-09-28\\sya\\outputs\\data-flow-audit-2026-10-05\\latest\\evidence')/('.coverage.child90.'+script.stem+'.'+uuid.uuid4().hex)),source=[str(REPO/'backend')],branch=True)
 cov.start()
 def finish():
  cov.stop();cov.save()
 atexit.register(finish)
