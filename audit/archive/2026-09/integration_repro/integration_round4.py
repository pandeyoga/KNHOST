"""Real ASGI + Motor/Mongo audit; synthetic localhost database only, no external network."""
import os,sys,json,asyncio,collections,platform,socket,traceback,uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta
B=Path(__file__).resolve().parent;REPO=Path(os.environ.get('KNHOST_REPO',str(B/'KNHOST')))
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
from services import hr_leave_service as leave,hr_payroll_service as payroll,hr_attendance_service as att,hr_service
# Lightweight executable-line evidence, not branch or business-flow coverage.
import atexit
trace_lines=collections.defaultdict(set)
trace_prefix=str((REPO/'backend').resolve()).lower()
def trace_local(frame,event,arg):
 if event=='line':trace_lines[frame.f_code.co_filename].add(frame.f_lineno)
 return trace_local
def trace_dispatch(frame,event,arg):
 if event=='call' and frame.f_code.co_filename.lower().startswith(trace_prefix):return trace_local
 return None
def save_trace():
 sys.settrace(None)
 suffix=Path(sys.argv[0]).stem+'_'+os.environ.get('AUDIT_ROUTE_MODE','default')
 payload={str(Path(k).relative_to(REPO)).replace('\\','/'):sorted(v) for k,v in trace_lines.items()}
 (B/('trace_'+suffix+'.json')).write_text(json.dumps(payload,indent=2),encoding='utf-8')
atexit.register(save_trace);sys.settrace(trace_dispatch)
RESULTS=[]
def check(id,observed,predicate,kind='defect'):
 assert predicate,(id,observed)
 RESULTS.append({'id':id,'kind':kind,'observed':observed});print(id,json.dumps(observed,default=str),flush=True)
async def seed():
 await client.admin.command('ping')
 assert db.name.startswith('knhost_audit_') and await db.users.count_documents({})==0
 await db.business_entities.insert_many([{'id':e,'short_name':e,'legal_name':'Audit '+e,'doc_prefix':e,'status':'active'} for e in ['A','B']])
 await db.users.insert_one({'id':'U','name':'Audit User A','email':'audit@example.invalid','role':'finance','status':'active','home_entity_id':'A','allowed_entity_ids':['A']})
 await db.sessions.insert_one({'token':'audit-local-session','user_id':'U','expires_at':datetime.now(timezone.utc)+timedelta(hours=2)})
 await db.permission_settings.insert_one({'id':'default','matrix':{'finance':{'esign':['view','sign'],'hr':['view','view_pii','manage_payroll','manage_attendance'],'ar_receipt':['create','view']}}})
 await db.hr_employees.insert_one({'id':'EMP','name':'Synthetic Employee','entity_id':'A','status':'active','base_salary':17300000})
async def hr_cases():
 emp=await db.hr_employees.find_one({'id':'EMP'},{'_id':0});actor={'name':'Audit'}
 a=await leave.submit_leave(emp,{'date_from':'2026-10-05','date_to':'2026-10-16'},'Audit')
 b=await leave.submit_leave(emp,{'date_from':'2026-11-02','date_to':'2026-11-13'},'Audit')
 await leave.approve_leave(a['id'],actor);await leave.approve_leave(b['id'],actor)
 bal=await leave.get_balance('EMP','A',2026)
 check('I4-HR01',{'approved_days':bal['used'],'remaining':bal['remaining']},bal['used']==20 and bal['remaining']==-8)
 await leave.set_entitlement('ZERO','A',2026,0)
 bal=await leave.recompute_balance('ZERO','A',2026)
 check('I4-HR02',{'explicit_zero_entitlement_after_recompute':bal['entitlement']},bal['entitlement']==12)
 cross={**emp,'id':'CROSS'};await db.hr_employees.insert_one(cross)
 lv=await leave.submit_leave(cross,{'date_from':'2026-12-31','date_to':'2027-01-04'},'Audit')
 await leave.approve_leave(lv['id'],actor)
 old=await leave.recompute_balance('CROSS','A',2026);new=await leave.recompute_balance('CROSS','A',2027)
 check('I4-HR03',{'work_dates':lv['work_dates'],'used_2026':old['used'],'used_2027':new['used']},old['used']==3 and new['used']==0)
 overlap={**emp,'id':'OVER'};await db.hr_employees.insert_one(overlap)
 p={'date_from':'2026-10-05','date_to':'2026-10-05','leave_type':'izin'}
 a=await leave.submit_leave(overlap,p,'Audit');b=await leave.submit_leave(overlap,p,'Audit')
 await leave.approve_leave(a['id'],actor);await leave.approve_leave(b['id'],actor);await leave.cancel_leave(a['id'],actor)
 remaining=await db.hr_attendance.count_documents({'employee_id':'OVER','date':'2026-10-05'})
 check('I4-HR04',{'other_leave_status':(await db.hr_leave_requests.find_one({'id':b['id']}))['status'],'attendance_records':remaining},remaining==0)
 night=att.compute_metrics('2026-10-05T22:00:00+07:00','2026-10-06T06:00:00+07:00',{'jam_in':'22:00','jam_out':'06:00'})
 check('I4-HR05',night,night['work_min']==480 and night['overtime_min']==1440)
 await db.hr_attendance.insert_one({'id':'FLAG','employee_id':'FLAGEMP','entity_id':'A','date':'2026-10-05','overtime_min':120,'approved':False,'status':'flagged'})
 cfg=await hr_service.get_hr_settings('A');cfg['feature_toggles']={'bpjs_kesehatan':False,'bpjs_ketenagakerjaan':False,'pph21':False}
 slip=await payroll.compute_payslip({**emp,'id':'FLAGEMP'},'2026-10','A',cfg)
 check('I4-HR06',{'unapproved_minutes':120,'payroll_overtime_min':slip['overtime_min'],'payroll_overtime_amount':slip['overtime']},slip['overtime_min']==120 and slip['overtime']==300000)
 await db.hr_overtime.insert_one({'id':'OT','employee_id':'FLAGEMP','entity_id':'A','period':'2026-10','date':'2026-10-05','minutes':120,'status':'approved'})
 slip=await payroll.compute_payslip({**emp,'id':'FLAGEMP'},'2026-10','A',cfg)
 check('I4-HR07',{'auto_minutes':120,'formal_minutes_same_day':120,'payroll_total_minutes':slip['overtime_min']},slip['overtime_min']==240,'design_gap')
 ordinary=att.compute_metrics('2026-10-05T08:00:00+07:00','2026-10-05T17:00:00+07:00',{'jam_in':'08:00','jam_out':'17:00'})
 check('I4-C01',ordinary,ordinary['work_min']==540 and ordinary['overtime_min']==0,'control')
async def http_cases():
 headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app,raise_app_exceptions=False),base_url='http://audit.local',headers=headers) as c:
  await db.document_signatures.insert_one({'id':'SIGB','doc_type':'invoice','source_id':'INVB','status':'signed','entity_id':'B','signer_name':'Synthetic B Signer','signed_at':'2026-01-01','doc_hash':'HASH','signature_b64':'SYNTHETIC'})
  res=await c.get('/api/esign/signatures/invoice/INVB');data=res.json()
  check('I4-SEC01',{'http_status':res.status_code,'foreign_signatures_returned':len(data.get('signatures',[])),'image_returned':any('signature_b64' in x for x in data.get('signatures',[]))},res.status_code==200 and len(data['signatures'])==1)
  res=await c.post('/api/hr/payroll/runs/preview',json={'entity_id':'B','period':'2026-10'})
  check('I4-C02',{'cross_entity_payroll_preview_status':res.status_code},res.status_code==403,'control')
  before=await hr_service.get_hr_settings('B')
  res=await c.put('/api/hr/payroll/settings',json={'settings':{'overtime':{'multiplier':3.0}}})
  after=await hr_service.get_hr_settings('B')
  check('I4-CFG01',{'actor_scope':['A'],'active_entity':'A','http_status':res.status_code,'entity_B_multiplier_before':before['overtime']['multiplier'],'entity_B_multiplier_after':after['overtime']['multiplier']},res.status_code==200 and after['overtime']['multiplier']==3.0)

async def main():
 await seed();await hr_cases();await http_cases()
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  result={'database':DBNAME,'mongo_target':'127.0.0.1:27919','source_commit':'d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467','mode':'Actual imported application modules + Motor + Mongo; ASGI HTTP for marked cases; full lifespan not started; Windows uname adapter only.','external_network_attempts_blocked':blocked,'results':RESULTS}
  (B/'integration_round4.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');client.close()
