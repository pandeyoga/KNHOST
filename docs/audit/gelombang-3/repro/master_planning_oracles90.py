"""Planning, design ratings and quantity dimensions; original functions and ASGI."""
import os,asyncio,json,traceback,base64
from pathlib import Path
os.environ['LOCAL_STORAGE_DIR']=str(Path(__file__).resolve().parents[1]/'continuation-90/gallery-test-files')
import procurement_lifecycle90 as fixture
e=fixture.e
from services import purchase_requisition_service as pr,design_gallery_service as gal,dual_qty_service as dual
from services import storage_service as storage
RESULTS=[];ERRORS=[];CONTEXT={}
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def denied(key,fn):
 try:await fn();rec(key,'rejected','accepted')
 except (ValueError,e.server.HTTPException if hasattr(e.server,'HTTPException') else ValueError):rec(key,'rejected','rejected')
async def request(h,method,path,body=None):
 r=await h.request(method,'/api/'+path,json=body);return r.status_code,r.json()
async def ok(h,method,path,body=None):
 code,v=await request(h,method,path,body);assert code==200,(path,code,v);return v
async def planning(h,p):
 unit=p['base_unit'];base={'entity_id':'ent_ksc','warehouse_id':'wh_jakarta','items':[{'product_id':p['id'],'quantity':10,'est_price':5,'unit':unit,'qty_rolls':2}],'submit_now':False}
 doc=await ok(h,'POST','purchase-requisitions',base);pid=doc['id']
 rec('pr.created_draft','draft',doc['status']);rec('pr.total',50,doc['total_est_amount']);rec('pr.roll_count',2,doc['items'][0]['qty_rolls'])
 for label,patch in [('empty',{'items':[]}),('warehouse',{'warehouse_id':'missing'}),('supplier',{'preferred_supplier_id':'missing'}),
  ('product',{'items':[{**base['items'][0],'product_id':'missing'}]}),('unit',{'items':[{**base['items'][0],'unit':'UNKNOWN'}]}),
  ('zero_qty',{'items':[{**base['items'][0],'quantity':0}]}),('unnamed_non_catalog',{'items':[{'quantity':1,'unit':unit}]}),
  ('makloon_no_product',{'items':[{'description':'Non catalogue fabric','quantity':1,'unit':unit,'fulfillment_mode':'makloon'}]})]:
  code,v=await request(h,'POST','purchase-requisitions',{**base,**patch});rec('pr.invalid_'+label,True,code in (400,404,422),str(v)[:200])
 for label,body in [('no_reason',{'quantity':11}),('same',{'quantity':10,'reason':'unchanged'}),('zero',{'quantity':0,'reason':'bad'})]:
  code,v=await request(h,'PATCH',f'purchase-requisitions/{pid}/lines/1',body);rec('pr.edit_'+label,True,code in (400,422))
 await e.db.purchase_requisitions.update_one({'id':pid},{'$set':{'source':'so','items.0.order_qty':10}})
 code,v=await request(h,'PATCH',f'purchase-requisitions/{pid}/lines/1',{'quantity':9,'reason':'Below customer requirement'});rec('pr.below_so_qty',400,code)
 changed=await ok(h,'PATCH',f'purchase-requisitions/{pid}/lines/1',{'quantity':12,'reason':'Add two units to available stock'})
 rec('pr.edit_new_qty',12,changed['items'][0]['quantity']);rec('pr.edit_total',60,changed['total_est_amount']);rec('pr.edit_extra',2,changed['items'][0]['extra_qty'])
 rec('pr.edit_base_qty',12,changed['items'][0]['quantity_base'])
 trail=changed['items'][0].get('uom_trail',{})
 CONTEXT['edited_pr']={'id':pid,'item':changed['items'][0]}
 rec('pr.edit_trail_base_agrees',12,trail.get('base_qty'))
 submitted=await ok(h,'POST',f'purchase-requisitions/{pid}/submit')
 rec('pr.small_value_auto_approved','approved',submitted['status'])
 code,_=await request(h,'POST',f'purchase-requisitions/{pid}/submit');rec('pr.repeated_submit_rejected',400,code)
 cancelled=await ok(h,'POST',f'purchase-requisitions/{pid}/cancel');rec('pr.cancelled','cancelled',cancelled['status'])
 code,_=await request(h,'POST',f'purchase-requisitions/{pid}/cancel');rec('pr.repeat_cancel_rejected',400,code)
 code,_=await request(h,'PATCH',f'purchase-requisitions/{pid}/lines/1',{'quantity':15,'reason':'Terminal edit'});rec('pr.terminal_edit_rejected',400,code)
 # Explicit transition/error fixtures exercise service guards, not API scope claims.
 for name,fn in [('submit',lambda:pr.submit_requisition('missing')),('approve',lambda:pr.approve_requisition('missing',{'role':'admin'})),
  ('reject',lambda:pr.reject_requisition('missing',{'role':'admin'})),('cancel',lambda:pr.cancel_requisition('missing')),
  ('edit',lambda:pr.update_line_qty('missing',1,2,'test',{}))]:await denied('pr.service_missing_'+name,fn)
 async def transition_case(status,kind,actor,expected):
  key=f'PR90-{status}-{kind}-{actor.get("role")}';row={**doc,'id':key,'status':status,'number':key,'created_by_id':'OTHER','required_approval_role':'manager'}
  await e.db.purchase_requisitions.insert_one(row)
  try:
   value=await (pr.approve_requisition(key,actor) if kind=='approve' else pr.reject_requisition(key,actor,'Specification revised'))
   rec(key,expected,value['status'])
  except ValueError:rec(key,expected,'rejected_by_guard')
 for status in ['draft','pending_approval','approved','converted','cancelled','rejected']:
  for kind in ['approve','reject']:
   for role in ['finance','admin']:
    expected=('approved' if kind=='approve' else 'rejected') if status in ['draft','pending_approval'] and role=='admin' else 'rejected_by_guard'
    await transition_case(status,kind,{'id':'APPROVER','name':'Separate approver','role':role},expected)
async def ratings(h):
 await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.rnd':['view','manage','assess'],'matrix.finance.hr':['view','manage_attendance']}})
 # Public modern design producer; lifecycle APIs are distinct from legacy functions.
 doc=await ok(h,'POST','design-gallery',{'title':'Audit Pattern','design_type':'motif','tags':['Blue','blue',' Cotton ',''],'line_code':'printing'})
 gid=doc['id'];rec('gallery.tag_dedup',['Blue','Cotton'],doc['tags'])
 for label,patch in [('empty_title',{'title':''}),('bad_type',{'design_type':'nonsense'}),('bad_pattern',{'category_code':'MISSING'}),('bad_design',{'design_category_code':'MISSING'})]:
  code,v=await request(h,'POST','design-gallery',{'title':'Audit Pattern',**patch});rec('gallery.invalid_'+label,True,code in (400,422))
 for user,stars in [('U1',1),('U2',5),('U1',3)]:
  val=await gal.set_rating(gid,user,user,stars,'Independent rater')
 rec('gallery.unique_raters',2,val['rating_count']);rec('gallery.rating_average',4,val['rating_avg']);rec('gallery.my_rating',3,val['my_rating'])
 val=await gal.clear_rating(gid,'U1');rec('gallery.clear_count',1,val['rating_count']);rec('gallery.clear_average',5,val['rating_avg'])
 for stars in [0,6,None,'bad']:
  await denied('gallery.invalid_rating_'+str(stars),lambda stars=stars:gal.set_rating(gid,'U3','U3',stars))
 await denied('gallery.missing_rating',lambda:gal.set_rating('missing','U1','U1',1))
 await denied('gallery.missing_clear',lambda:gal.clear_rating('missing','U1'))
 for patch in [{'title':''},{'category_code':'bad'},{'design_category_code':'bad'},{'final_color_count':0},{'final_color_count':21},{'design_type':'bad'},{'status':'bad'},{'repeat_cm':'bad'},{}]:
  await denied('gallery.invalid_update_'+str(patch),lambda patch=patch:gal.update_gallery(gid,patch,{'id':'PROC90'}))
 val=await gal.update_gallery(gid,{'title':'Revised Audit Pattern','story':'Independent description','tags':['Red','red'],'line_code':'printing','repeat_cm':12,'color_count':2,'screen_count':3})
 rec('gallery.update_title','Revised Audit Pattern',val['title']);rec('gallery.update_tags',['Red'],val['tags'])
 png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII=')
 meta=await gal.add_file(gid,'audit.png','image/png',png,uploaded_by='Audit actor')
 CONTEXT['file_result']=meta
 fileid=meta.get('id') or meta.get('file',{}).get('id')
 assert fileid,(meta,'file result shape')
 data,ct=await gal.get_file_bytes(gid,fileid);rec('gallery.file_bytes_unchanged',True,data==png);rec('gallery.file_mime','image/png',ct)
 await gal.delete_file(gid,fileid,{'id':'PROC90','name':'Audit actor'})
 await denied('gallery.deleted_file_not_referenced',lambda:gal.get_file_bytes(gid,fileid))
 for filename,ct,size,head in [('audit.exe','application/octet-stream',1,b'x'),('audit.png','image/png',0,b''),('audit.png','image/png',storage.MAX_FILE_BYTES+1,png[:16]),('audit.png','image/png',10,b'not a png')]:
  try:storage.validate_upload(filename,ct,size,head);rec('storage.invalid_'+str((filename,size,head)),'rejected','accepted')
  except ValueError:rec('storage.invalid_'+str((filename,size,head)),'rejected','rejected')
 for filename,ct,head in [('audit.jpg','image/jpeg',b'\xff\xd8\xff'),('audit.pdf','application/pdf',b'%PDF-'),('audit.gif','image/gif',b'GIF89a'),('audit.webp','image/webp',b'RIFFxxxxWEBP')]:
  rec('storage.valid_'+filename,ct,storage.validate_upload(filename,ct,100,head))
 # Legacy methods are independently tested as legacy code; no modern UI lifecycle claim.
 for name,fn in [('submit',lambda:gal.submit_design('missing','actor')),('reject',lambda:gal.reject_design('missing','actor','reason')),
  ('approve',lambda:gal.approve_design('missing','actor')),('bump',lambda:gal.bump_version('missing',{},'actor')),('delete',lambda:gal.delete_gallery('missing'))]:await denied('gallery.legacy_missing_'+name,fn)
 await e.db.md_specs.insert_one({'id':'SPEC90','design_id':gid})
 await denied('gallery.used_design_cannot_delete',lambda:gal.delete_gallery(gid))
 await e.db.md_specs.delete_one({'id':'SPEC90'})
 rec('gallery.unused_delete',True,(await gal.delete_gallery(gid))['deleted'])
async def quantities():
 for line,want in [({'quantity':12,'unit_factor':1.6,'unit_factor_to':'yard'},19.2),({'qty':2,'unit_factor':3},6),({'quantity':1},None),({'quantity':'bad','unit_factor':2},None)]:
  rec('dual.equivalent_'+str(line),want,dual.measure_equivalent(line))
 rec('dual.wrong_target_returns_none',None,dual.measure_equivalent({'quantity':2,'unit_factor':3,'unit_factor_to':'yard'},'kg'))
 for raw,want in [(None,None),('',None),(0,0),(3,3),('4',4)]:rec('dual.stamp_rolls_'+str(raw),want,(await dual.stamp({'unit':'yard','qty_rolls':raw}))['qty_rolls'])
 rec('dual.real_roll_override',2,(await dual.stamp({'unit':'yard','qty_rolls':999},rolls=2))['qty_rolls'])
 for args in [('missing',1,'yard'),('yard',2,'yard'),('panel',2,'missing')]:
  try:await dual.assert_line_factor_allowed(*args);rec('dual.invalid_factor_'+str(args),'rejected','accepted')
  except Exception as exc:
   from fastapi import HTTPException
   if not isinstance(exc,HTTPException):raise
   rec('dual.invalid_factor_'+str(args),'rejected','rejected')
 await dual.assert_line_factor_allowed('panel',2,'yard')
 rec('dual.panel_allowed',True,await dual.line_factor_allowed('panel'));rec('dual.yard_not_doc_factor',False,await dual.line_factor_allowed('yard'))
 rec('dual.no_ids_unknown',None,await dual.rolls_of_ids([]));rec('dual.nonexistent_ids',0,await dual.rolls_of_ids(['missing','missing']))
async def main():
 try:
  products,_=await fixture.seed()
  transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False)
  async with e.httpx.AsyncClient(transport=transport,base_url='http://audit.local',headers={'Authorization':'Bearer audit-proc90','X-Entity-Id':'ent_ksc'}) as h:
   for name,fn in [('planning',lambda:planning(h,products[0])),('ratings',lambda:ratings(h)),('quantities',quantities)]:
    try:await fn()
    except Exception:ERRORS.append({'suite':name,'error':traceback.format_exc()})
 except Exception:ERRORS.append({'suite':'setup','error':traceback.format_exc()})
 finally:
  result=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,context=CONTEXT,harness_errors=ERRORS)
  Path(__file__).with_name('master-planning-oracles90-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
  print(json.dumps({'observations':len(RESULTS),'differences':[r['id'] for r in RESULTS if r['status']!='pass'],'errors':ERRORS},ensure_ascii=False));e.client.close()
if __name__=='__main__':asyncio.run(main())
