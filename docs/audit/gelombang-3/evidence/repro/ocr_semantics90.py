"""Receiving OCR consumers: independent quantity/cost oracles and local provider fixtures.

No external model is called. Native mock-* extraction is explicitly distinguished
from real photo-recognition accuracy. Application mappings/calculations stay original.
"""
import asyncio,copy,io,json,os,traceback
from pathlib import Path
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
os.environ['OCR_ALLOW_MOCK']='1'
os.environ['LOCAL_STORAGE_DIR']=str(Path(__file__).parents[1]/'continuation-90/ocr-files')
import service_env90 as e
from fastapi import HTTPException
from PIL import Image
from services import goods_receipt_ocr_service as go,ocr_sample_service as ss,config_resolver as cfg,storage_service as st
from services.ocr_openai_client import OcrError
from entity_scope import EntityContext
RESULTS=[];ERRORS=[];LIMITATIONS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def rejected(key,call,want):
 try:await call;actual='accepted'
 except HTTPException as ex:actual=ex.status_code
 except OcrError as ex:actual=ex.code
 rec(key,want,actual)
async def settings(**values):
 for key,val in values.items():await cfg.set_value('receiving.'+key,val,actor='Audit',reason='Local synthetic OCR consumer audit')
def answer():return {'dn_number':'SJ-MOCK-CLEAR','dn_date':'2026-06-10','lines':[{'qty':250,'unit':'yard','rolls':2,'po_ref':'KSC/PO-00014'}]}
def data():return json.loads((e.REPO/'backend/tests/fixtures/ocr/sj_clear.json').read_text())
async def main():
 try:
  await e.setup(template=True)
  actor=await e.db.users.find_one({'email':'admin@kainnusantara.id'},{'_id':0})
  entities=await e.db.business_entities.find({'status':'active'},{'_id':0}).to_list(None)
  ids=[x['id'] for x in entities];ctx=EntityContext(actor,'ent_ksc',ids)
  for usage,want in [({'input':1000000,'cached_input':0,'output':0},2.0),({'input':1000000,'cached_input':250000,'output':100000},2.425),({'input':0,'output':0},0.0)]:
   rec('ocr.cost_'+str(usage),want,go.cost_usd(usage,'audit-model',{'audit-model':{'in':2,'cached_in':.5,'out':8}}))
  for model,want in [('mock-sj_clear','allowed'),('missing','OCR_PRICE'),('priced','allowed')]:
   try:go._price_guard({'ocr_price_table':{'priced':{'in':2}}},model);actual='allowed'
   except OcrError as ex:actual=ex.code
   rec('ocr.price_'+model,want,actual)
  d=data();s=ss.score(answer(),d,go.R.DEFAULT_PO_PATTERNS)
  rec('ocr.score_correct',[1],s['checks']['qty']);rec('ocr.score_greige_not_declared',250,s['lines'][0]['got']['qty'])
  rec('ocr.score_unit_correct',[1],s['checks']['unit']);rec('ocr.score_roll_correct',[1],s['checks']['rolls'])
  rec('ocr.score_po_correct',[1],s['checks']['po_ref'])
  for field,edit in [('qty',lambda d:d['lines'][0]['quantities'][1].update(qty_text='260',qty=260)),('unit',lambda d:d['lines'][0]['quantities'][1].update(unit='m')),('rolls',lambda d:d['lines'][0]['quantities'][0].update(qty_text='3',qty=3)),('po_ref',lambda d:d['lines'][0].update(po_ref='KSC/PO-00015'))]:
   d=data();edit(d);s=ss.score(answer(),d,go.R.DEFAULT_PO_PATTERNS);rec('ocr.score_wrong_'+field,[0],s['checks'][field])
  for kind,d in [('missing',{'header':data()['header'],'lines':[]}),('extra',{**data(),'lines':data()['lines']+[copy.deepcopy(data()['lines'][0])]})]:
   s=ss.score(answer(),d,go.R.DEFAULT_PO_PATTERNS);rec('ocr.score_'+kind,True,0 in s['checks']['qty'])
  for key,qty,dn,status,want in [('empty',[],[],'ok',False),('exact_target',[1]*19+[0],[1]*49+[0],'ok',True),('qty_below',[1]*18+[0]*2,[1]*50,'ok',False),('dn_below',[1]*20,[1]*48+[0]*2,'ok',False),('failed',[1]*20,[1]*50,'failed',False)]:
   row={'status':status,'score':{'checks':{'qty':qty,'unit':[1]*20,'dn_number':dn}}}
   rec('ocr.gate_'+key,want,ss.aggregate([row])['gate_pass'])
  clean=ss.clean_answer({'dn_number':' SJ 1 ','lines':[{'qty':'12.5','rolls':'2','unit':'yard','po_ref':' PO1 '}]})
  rec('ocr.clean_numeric',(12.5,2), (clean['lines'][0]['qty'],clean['lines'][0]['rolls']))
  sample=await ss.create('ent_ksc',label=' Audit ',partner_id='SUP',partner_name='Supplier',files=[],answer=answer(),actor='Audit')
  rec('ocr.sample_label','Audit',sample['label']);rec('ocr.sample_scoped',1,len(await ss.list_samples('ent_ksc')))
  await rejected('ocr.sample_other_scope',ss._get(sample['id'],'foreign'),404)
  changed=await ss.update(sample['id'],'ent_ksc','New',{'dn_number':' SJ 2 ','lines':[]});rec('ocr.sample_update','SJ 2',changed['answer']['dn_number'])
  await rejected('ocr.sample_missing_page',ss.file_bytes(sample['id'],'ent_ksc',1),404)
  await ss.delete(sample['id'],'ent_ksc');rec('ocr.sample_deleted',0,len(await ss.list_samples('ent_ksc')))
  await rejected('ocr.run_no_samples',ss.start_run('ent_ksc',[],'Audit'),400)
  await rejected('ocr.run_missing',ss.get_run('missing','ent_ksc'),404)
  rec('ocr.run_list_empty',[],await ss.list_runs('ent_ksc'))
  # Image/PDF preprocessing of generated test bytes; no user image or external AI.
  buf=io.BytesIO();Image.new('RGB',(100,200),'white').save(buf,'JPEG');photo=buf.getvalue()
  conf=await go.ocr_config('ent_ksc');conf.update(ocr_max_pages=2,ocr_image_max_side=512,min_photo_short_side_px=200)
  parts,n,text=go.pages_from_bytes([(photo,'image/jpeg')],conf);rec('ocr.photo_pages',1,n);rec('ocr.photo_text',False,text)
  sz=Image.open(io.BytesIO(__import__('base64').b64decode(parts[0]['image_url'].split(',',1)[1]))).size;rec('ocr.photo_upscale',(200,400),sz)
  rotated=go._rotate_part(parts[0],90);sz2=Image.open(io.BytesIO(__import__('base64').b64decode(rotated['image_url'].split(',',1)[1]))).size;rec('ocr.photo_rotate',(400,200),sz2)
  for kind,docs,want in [('pages',[(photo,'image/jpeg')]*3,'OCR_PAGES'),('bad_image',[(b'bad','image/jpeg')],'OCR_FILE'),('bad_pdf',[(b'bad','application/pdf')],'OCR_FILE')]:
   try:go.pages_from_bytes(docs,conf);actual='accepted'
   except OcrError as ex:actual=ex.code
   except ModuleNotFoundError as ex:
    LIMITATIONS.append({'case':'ocr.preprocess_'+kind,'unverified_dependency':str(ex)});continue
   rec('ocr.preprocess_'+kind,want,actual)
  try:
   import fitz
   pdf=fitz.open();page=pdf.new_page();page.insert_text((40,40),'Synthetic SJ 001: 250 yard, two rolls. This is an audit-only delivery document.')
   _,n,text=go.pages_from_bytes([(pdf.tobytes(),'application/pdf')],conf);rec('ocr.pdf_text_layer',True,text);rec('ocr.pdf_pages',1,n);pdf.close()
  except ModuleNotFoundError as ex:LIMITATIONS.append({'case':'ocr.pdf_text_layer','unverified_dependency':str(ex)})
  now=datetime.now(timezone.utc);prior=(now.replace(day=1)-timedelta(days=1)).isoformat()
  await e.db.ai_usage_log.delete_many({})
  await e.db.ai_usage_log.insert_many([{'id':'usageA','entity_id':'ent_ksc','feature':'ocr_dn','at':now.isoformat(),'model':'audit','status':'ok','cost_usd':1,'pages':2,'usage':{'input':100,'output':10}}, {'id':'usageB','entity_id':ids[-1],'feature':'ocr_dn','at':now.isoformat(),'model':'audit','status':'failed','cost_usd':2,'pages':0,'usage':{'input':200}}, {'id':'usageOld','entity_id':'ent_ksc','feature':'ocr_dn','at':prior,'cost_usd':50}, {'id':'usageOther','entity_id':'ent_ksc','feature':'other','at':now.isoformat(),'cost_usd':100}])
  rec('ocr.spend_current_global',3.0,await go.month_spend())
  await settings(ocr_monthly_budget_usd=10,ocr_budget_warn_pct=20)
  summary=await go.usage_summary('',ctx);rec('ocr.summary_scope_spend',1.0,summary['spent_usd']);rec('ocr.summary_global_remaining',7.0,summary['remaining_usd']);rec('ocr.summary_cost_page',.5,summary['rows'][0]['cost_per_page'])
  ctxall=EntityContext(actor,'ent_ksc',ids,True);rec('ocr.summary_all_spend',3.0,(await go.usage_summary('',ctxall))['spent_usd'])
  await go._budget_guard(await go.ocr_config('ent_ksc'),'ent_ksc');await go._budget_guard(await go.ocr_config('ent_ksc'),'ent_ksc')
  rec('ocr.budget_warning_dedup',1,await e.db.notifications.count_documents({'ref':{'$regex':'^ocr_budget:'}}))
  await settings(ocr_monthly_budget_usd=3);await rejected('ocr.budget_exhausted',go._budget_guard(await go.ocr_config('ent_ksc'),'ent_ksc'),'OCR_BUDGET')
  await settings(ocr_monthly_budget_usd=75,ocr_enabled=True,ocr_model_primary='mock-sj_clear',ocr_model_second='mock-sj_doubt_second',ocr_second_reader_mode='off')
  path='kn7/audit/ocr.jpg';await st.put_object(path,photo,'image/jpeg')
  async def grn(key,**fields):
   t=await e.db.wms_tasks.find_one({'flow_type':'inbound','product_id':'prod_batik_mega','entity_id':'ent_ksc'})
   po=await e.db.purchase_orders.find_one({'id':t['po_id']});await e.db.purchase_orders.update_one({'id':po['id']},{'$set':{'po_number':'KSC/PO-00014'}})
   doc={'id':key,'entity_id':'ent_ksc','partner_id':po['supplier_id'],'partner_name':'CV CIREBON CRAFT','partner_type':'supplier','warehouse_id':t['warehouse_id'],'status':'draft','version':1,'files':[{'page':1,'path':path,'content_type':'image/jpeg'}],'lines':[],'dn':{},'extraction':{},**fields}
   await e.db.goods_receipts.insert_one(dict(doc));return doc
  g=await grn('G-CLEAR');out=await go.read_grn(g['id'],1,actor,ctx)
  rec('ocr.read_status','review',out['status']);rec('ocr.read_success',False,out['extraction']['read_failed']);rec('ocr.read_is_native_mock',True,out['extraction']['is_mock'])
  rec('ocr.read_qty',250,out['lines'][0]['declared']['qty']);rec('ocr.read_human_confirm_needed',False,out['dn']['verified'])
  await rejected('ocr.read_double',go.read_grn(g['id'],out['version'],actor,ctx),409)
  await grn('G-NO-FILE',files=[]);await rejected('ocr.read_needs_file',go.read_grn('G-NO-FILE',1,actor,ctx),400)
  await settings(ocr_enabled=False);await grn('G-OFF');await rejected('ocr.read_disabled',go.read_grn('G-OFF',1,actor,ctx),400)
  await settings(ocr_enabled=True,ocr_model_primary='mock-missing');await grn('G-FAILED');out=await go.read_grn('G-FAILED',1,actor,ctx);rec('ocr.failed_review','review',out['status']);rec('ocr.failed_code','OCR_SCHEMA',out['extraction']['error_code'])
  await settings(ocr_model_primary='mock-sj_clear');out=await go.read_grn('G-FAILED',out['version'],actor,ctx);rec('ocr.failed_retry_success',False,out['extraction']['read_failed'])
  await settings(ocr_second_reader_mode='always');await grn('G-SECOND');out=await go.read_grn('G-SECOND',1,actor,ctx);rec('ocr.second_reader_roles',['primary','second'],[r['role'] for r in out['extraction']['runs']]);rec('ocr.second_reader_diff',True,bool(out['extraction']['header_diff']))
  await settings(ocr_model_second='mock-missing');await grn('G-SECONDFAIL');out=await go.read_grn('G-SECONDFAIL',1,actor,ctx);rec('ocr.second_failure_keeps_primary',False,out['extraction']['read_failed']);rec('ocr.second_failure_warning',True,any('gagal' in x for x in out['extraction']['warnings']))
  for key,status,age,want in [('fresh','reading',1,'reading'),('stale','reading',10,'review'),('review','review',10,'review')]:
   doc=await grn('G-'+key,status=status,reading_heartbeat=(now-timedelta(minutes=age)).isoformat(),reading_run_id='test-run')
   out=await go.sweep_stale(doc);rec('ocr.sweep_'+key,want,out['status'])
  stale=await e.db.goods_receipts.find_one({'id':'G-stale'},{'_id':0});rec('ocr.sweep_code','OCR_TIMEOUT',stale['extraction']['error_code'])
  for key,a,b,want in [('same',data(),data(),False),('different',data(),{**data(),'header':{**data()['header'],'dn_number':'OTHER'}},True),('missingline',data(),{**data(),'lines':[]},True)]:
   h,p=go.second_reader_diff(a,b);rec('ocr.compare_'+key,want,bool(h or p))
 except Exception:ERRORS.append(traceback.format_exc())
 finally:
  Path(__file__).with_name('ocr-semantics90-results.json').write_text(json.dumps(dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,harness_errors=ERRORS,limitations=LIMITATIONS,scope='Original OCR consumer logic and repository native mock provider, synthetic bytes/DB; external AI accuracy unverified.'),ensure_ascii=False,indent=2,default=list),encoding='utf-8')
  print(json.dumps({'observations':len(RESULTS),'differences':[r['id'] for r in RESULTS if r['status']!='pass'],'errors':ERRORS}));e.client.close()
if __name__=='__main__':asyncio.run(main())
