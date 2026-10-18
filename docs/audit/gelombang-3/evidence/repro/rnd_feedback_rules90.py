"""Original R&D edit contracts and feedback state/counter consistency.

Fresh synthetic template database. Direct service callers are explicitly scoped
as service verification, not frontend/RBAC verification. Inputs use actual master
records; seeded status/round fixtures only test already existing history guards.
"""
import asyncio,json,traceback
from pathlib import Path
import service_env90 as e
from services import rnd_spec_service as spec,rnd_sample_service as sample,design_request_service as design,customer_feedback_service as feedback,design_gallery_service as gallery
RESULTS=[];ERRORS=[]
ACTOR={'id':'AUD-RND','name':'Audit MD','role':'admin'}
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def reject(key,fn):
 try:await fn;out=False
 except (ValueError,feedback.FeedbackError):out=True
 rec(key,True,out)
async def rnd():
 color=await e.db.color_library.find_one({});assert color
 base={'title':'Audit woven fabric','target':{'fabric_type':'woven','stage':'finished','lebar':150,'gramasi':200},'line_code':'woven','sample_type_hint':'labdip','color_target':{'color_id':color['id']}}
 s=await spec.create_spec(base,entity_id='ent_ksc',actor=ACTOR['name']);sid=s['id']
 for key,patch in [('title',{'title':'Revised fabric'}),('strings',{'category':'woven','base_unit':'yard','sku_hint':'AUD90','customer_id':'AUD-C','so_id':'','notes':'Audit','template_id':'','target_product_id':'','variant_attrs':{},'variant_options':{}}),('target',{'target':{'gramasi':'180','lebar':'155','epi':'60','ppi':'50','reed_width':'160','yarn_count':'30','yarn_material':'cotton','yarn_ply':2,'grade':'A'}}),('null_numeric',{'target':{'epi':'','ppi':None}}),('hint',{'sample_type_hint':'handfeel'}),('color_by_code',{'color_target':{'code':color['code']}}),('clear_color',{'color_target':{}}),('price',{'target_price':'123.45'}),('clear_design',{'design_id':''}),('clear_fabric',{'base_fabric_template_id':''})]:
  v=await spec.patch_spec(sid,patch,ACTOR['name']);rec('spec.patch_'+key,sid,v['id'])
 rec('spec.numeric_decimal',123.45,v['target_price']);rec('spec.width_cm',155,v['target']['lebar'])
 for key,patch in [('hint',{'sample_type_hint':'missing'}),('color',{'color_target':{'color_id':'missing'}}),('design',{'design_id':'missing'}),('fabric',{'base_fabric_template_id':'missing'})]:await reject('spec.invalid_'+key,spec.patch_spec(sid,patch))
 for status in ['approved','rejected']:
  await e.db.md_specs.update_one({'id':sid},{'$set':{'status':status}});await reject('spec.terminal_edit_'+status,spec.patch_spec(sid,{'title':'Forbidden'}))
 await e.db.md_specs.update_one({'id':sid},{'$set':{'status':'draft'}})
 v=await spec.submit_spec(sid,ACTOR['name']);rec('spec.submit','review',v['status']);await reject('spec.repeat_submit',spec.submit_spec(sid))
 v=await spec.reject_spec(sid,'Revised requirement',ACTOR);rec('spec.reject','rejected',v['status']);await reject('spec.repeat_reject',spec.reject_spec(sid,'Reason',ACTOR))
 for key,patch in [('empty_title',{'title':''}),('bad_hint',{'sample_type_hint':'bad'}),('bad_fabric',{'target':{'fabric_type':'bad'}}),('missing_fabric',{'target':{}}),('bad_stage',{'target':{'fabric_type':'woven','stage':'bad'}})]:await reject('spec.create_guard_'+key,spec.create_spec({**base,**patch},entity_id='ent_ksc'))
 sm=await sample.create_sample({'title':'Multi-test sample','sample_types':['labdip','handfeel'],'line_code':'woven','qty_requested':2},entity_id='ent_ksc');mid=sm['id']
 for key,patch in [('text',{'title':'Revised sample','brief':'Changed requirement','unit':'yard'}),('qty_date',{'qty_requested':'2.5','target_date':'2099-01-01T12:00:00'}),('color',{'color_target':{'color_id':color['id']}}),('design_clear',{'design_id':''}),('types',{'sample_types':['labdip','handfeel','labdip']}),('customer',{'customer_id':'AUD-C'})]:
  v=await sample.patch_sample(mid,patch,ACTOR['name']);rec('sample.patch_'+key,mid,v['id'])
 rec('sample.unique_types',['labdip','handfeel'],v['sample_types']);rec('sample.requested_qty',2.5,v['qty_requested']);rec('sample.date_only','2099-01-01',v['target_date'])
 await e.db.sales_orders.insert_one({'id':'AUD-SO','entity_id':'ent_ksc','number':'SO-AUD90','order_number':'SO-AUD90','customer_id':'AUD-C','customer_name':'Synthetic customer','feedback_open_count':0})
 v=await sample.patch_sample(mid,{'so_id':'AUD-SO'});rec('sample.so_number','SO-AUD90',v['so_number'])
 v=await sample.patch_sample(mid,{'so_id':''});rec('sample.unlink_so','',v['so_id'])
 for key,patch in [('so',{'so_id':'missing'}),('color',{'color_target':{'color_id':'missing'}}),('design',{'design_id':'missing'}),('types',{'sample_types':['bad']}),('proofing_requires_design',{'sample_types':['proofing']})]:await reject('sample.invalid_'+key,sample.patch_sample(mid,patch))
 await e.db.md_samples.update_one({'id':mid},{'$set':{'rounds':[{'id':'AUD-ROUND','type_code':'labdip'}]}})
 await reject('sample.used_type_cannot_remove',sample.patch_sample(mid,{'sample_types':['handfeel']}))
 for status in ['decided','cancelled']:
  await e.db.md_samples.update_one({'id':mid},{'$set':{'status':status}});await reject('sample.terminal_patch_'+status,sample.patch_sample(mid,{'brief':'Changed'}))
 await e.db.md_samples.update_one({'id':mid},{'$set':{'status':'decided'}});await reject('sample.decided_cancel_guard',sample.cancel_sample(mid,'Reason'))
 await e.db.md_samples.update_one({'id':mid},{'$set':{'status':'draft'}});v=await sample.cancel_sample(mid,'Request withdrawn');rec('sample.cancel','cancelled',v['status'])
 for row,want in [({},[]),({'sample_type':' LABDIP '},['labdip']),({'sample_types':['','labdip','LABDIP','handfeel']},['labdip','handfeel'])]:rec('sample.type_normalize_'+str(row),want,sample.types_of(row))
 d=await design.create({'brief':'Design woven flowers','line_code':'printing','target_type':'motif'},ACTOR,'ent_ksc');did=d['id']
 unchanged=await design.update(did,{},ACTOR);rec('design.empty_edit_no_event',len(d['history']),len(unchanged['history']))
 for key,patch in [('brief',{'brief':'Revised flower design'}),('date',{'due_date':' 2099-01-01 '}),('type',{'target_type':'motif'}),('categories',{'category_code':'','design_category_code':''}),('line',{'line_code':'printing'}),('color',{'color_targets':[{'code':'NAVY','name':'Navy','hex':'#000080'},{'code':'NAVY','name':'Navy'}]})]:
  v=await design.update(did,patch,ACTOR);rec('design.patch_'+key,did,v['id'])
 for key,patch in [('brief',{'brief':''}),('target',{'target_type':'bad'}),('category',{'category_code':'missing'}),('design_category',{'design_category_code':'missing'})]:await reject('design.invalid_'+key,design.update(did,patch,ACTOR))
 for status in ['delivered','approved','cancelled']:
  await e.db.design_requests.update_one({'id':did},{'$set':{'status':status}});await reject('design.terminal_patch_'+status,design.update(did,{'brief':'Change original'},ACTOR))
 for method in [lambda:spec.patch_spec('missing',{}),lambda:sample.patch_sample('missing',{}),lambda:design.update('missing',{},ACTOR)]:await reject('rnd.missing_'+str(len(RESULTS)),method())
async def feedbacks():
 base={'order_id':'AUD-SO','title':'Wrong fabric color','category':'kualitas','severity':'tinggi','due_date':'2000-01-01'}
 doc=await feedback.create_feedback(base,ACTOR);fid=doc['id'];rec('feedback.initial_status','open',doc['status'])
 async def count(key,want):rec('feedback.counter_'+key,want,(await e.db.sales_orders.find_one({'id':'AUD-SO'}))['feedback_open_count'])
 await count('create',1)
 for key,patch in [('title',{'title':'x'}),('category',{'category':'bad'}),('severity',{'severity':'bad'}),('so',{'order_id':'missing'})]:
  try:await feedback.create_feedback({**base,**patch},ACTOR);out=False
  except feedback.FeedbackError:out=True
  rec('feedback.create_guard_'+key,True,out)
 for key,patch in [('empty',{}),('severity',{'severity':'bad'}),('status',{'status':'bad'}),('resolution',{'status':'resolved'})]:
  try:await feedback.update_feedback(fid,patch,ACTOR);out=False
  except feedback.FeedbackError:out=True
  rec('feedback.edit_guard_'+key,True,out)
 for stage in ['in_progress','resolved','in_progress','closed']:
  v=await feedback.update_feedback(fid,{'status':stage,'resolution':'Replacement supplied','note':'Follow-up'},ACTOR);rec('feedback.transition_'+stage,stage,v['status']);await count(stage,1 if stage=='in_progress' else 0)
 await reject('feedback.closed_cannot_reopen',feedback.update_feedback(fid,{'status':'open'},ACTOR))
 await count('terminal_reject_unchanged',0)
 d=await feedback.create_feedback({**base,'assignee_id':ACTOR['id'],'assignee_name':'Audit MD'},ACTOR);rec('feedback.initial_assigned','in_progress',d['status'])
 d=await feedback.update_feedback(d['id'],{'assignee_id':'','assignee_name':'','due_date':'','severity':'rendah'},ACTOR);rec('feedback.remove_assignee','',d['assignee_id'])
 d=await feedback.update_feedback(d['id'],{'note':'Contacted customer'},ACTOR);rec('feedback.note_history','note',d['timeline'][-1]['event'])
 total=await feedback.summary({'entity_id':'ent_ksc'});rec('feedback.summary_total',2,total['total']);rec('feedback.summary_open',1,total['open']);rec('feedback.summary_resolved',1,total['resolved']);rec('feedback.summary_high_open',0,total['tinggi_open']);rec('feedback.summary_overdue',0,total['overdue'])
 rows=await feedback.list_feedback({'entity_id':'ent_ksc'},order_id='AUD-SO',status='in_progress',customer_id='AUD-C',limit=10);rec('feedback.filtered_list',1,len(rows))
 await reject('feedback.missing_update',feedback.update_feedback('missing',{},ACTOR))
async def main():
 try:
  await e.setup(template=True)
  for label,fn in [('rnd',rnd),('feedback',feedbacks)]:
   try:await fn()
   except Exception:ERRORS.append(label+'\n'+traceback.format_exc())
 finally:
  out=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,harness_errors=ERRORS,scope=__doc__)
  Path(__file__).with_name('rnd-feedback-rules90-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(observations=len(RESULTS),differences=[x['id'] for x in RESULTS if x['status']!='pass'],errors=ERRORS)));e.client.close()
if __name__=='__main__':asyncio.run(main())
