"""Special-price API: normal lifecycle, scoped list/control, and foreign-record guards."""
import asyncio,io,json,os,traceback
from pathlib import Path
os.environ['LOCAL_STORAGE_DIR']=str(Path(__file__).parents[1]/'continuation-90/price-files')
import wave2_env as e
from PIL import Image
RESULTS=[];ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def main():
 try:
  await e.seed()
  await e.db.users.update_one({'id':'U'},{'$set':{'role':'sales','home_entity_id':'A','allowed_entity_ids':['A']}})
  # Deliberately assigned capabilities, limited to A. This is a custom role,
  # not manager/admin, which intentionally have cross-entity authority.
  await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix':{'sales':{'price_approval':['view','create','update','delete','approve']}}}})
  await e.db.customers.insert_many([{'id':'CA','name':'Customer A','entity_id':'A','status':'active'},{'id':'CB','name':'Customer B','entity_id':'B','status':'active'}])
  await e.db.products.insert_one({'id':'P','name':'Audit Cloth','sku':'AUD-P','status':'active','unit':'yard','price':100,'harga_pokok':50})
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
   async def request(method,path,**kw):return await h.request(method,'/api'+path,**kw)
   payload={'customer_id':'CA','product_id':'P','requested_price':90,'entity_id':'A','scope':'standing','reason':'Synthetic negotiation'}
   r=await request('POST','/price-approvals',json=payload);rec('price.create_own',200,r.status_code);own=r.json();assert own.get('id'),r.text
   rec('price.create_draft','draft',own['status'])
   for key,patch,want in [('zero',{'requested_price':0},400),('empty',{'x':'ignored'},400),('valid',{'requested_price':85,'min_quantity':5,'valid_until':'2099-01-01','reason':'Updated'},200)]:
    r=await request('PATCH','/price-approvals/'+own['id'],json={'data':patch});rec('price.patch_'+key,want,r.status_code)
   r=await request('POST','/price-approvals/'+own['id']+'/submit');rec('price.submit_requires_evidence',400,r.status_code)
   buf=io.BytesIO();Image.new('RGB',(20,20),'white').save(buf,'JPEG')
   r=await request('POST','/price-approvals/'+own['id']+'/attachments',files={'file':('evidence.jpg',buf.getvalue(),'image/jpeg')});rec('price.upload_evidence',200,r.status_code)
   r=await request('POST','/price-approvals/'+own['id']+'/submit');rec('price.submit_with_evidence',200,r.status_code)
   r=await request('POST','/price-approvals/'+own['id']+'/submit');rec('price.submit_twice',409,r.status_code)
   # A distinct, limited A user may decide the own-entity request.
   await e.db.users.insert_one({'id':'DEC','name':'A Approver','email':'approver@example.invalid','role':'sales','status':'active','allowed_entity_ids':['A'],'home_entity_id':'A'})
   await e.db.sessions.insert_one({'token':'local-decision-token','user_id':'DEC','expires_at':e.datetime.now(e.timezone.utc)+e.timedelta(hours=1)})
   r=await request('POST','/price-approvals/'+own['id']+'/approve',headers={'Authorization':'Bearer local-decision-token'},json={'decision_notes':'Local audit'});rec('price.approve_distinct_actor',200,r.status_code)
   r=await request('GET','/price-approvals/effective',params={'customer_id':'CA','product_id':'P','entity_id':'A','quantity':5});rec('price.effective_min_met',85.0,r.json().get('requested_price'))
   r=await request('GET','/price-approvals/effective',params={'customer_id':'CA','product_id':'P','entity_id':'A','quantity':4});rec('price.effective_min_unmet',False,r.json().get('has_special'))
   rec('price.delete_approved_guard',409,(await request('DELETE','/price-approvals/'+own['id'])).status_code)
   rec('price.patch_approved_guard',409,(await request('PATCH','/price-approvals/'+own['id'],json={'data':{'reason':'X'}})).status_code)
   # Producer guard uses real B entity/customer and an A-only authenticated user.
   r=await request('POST','/price-approvals',json={**payload,'customer_id':'CB','entity_id':'B'})
   rec('price.foreign_create_rejected',True,r.status_code in (403,404),str(r.status_code))
   if r.status_code==200:
    foreign=r.json();fid=foreign['id']
   else:
    foreign={**own,'id':'FOREIGN','entity_id':'B','customer_id':'CB','status':'draft','requested_by':'U','attachments':[]};fid=foreign['id'];await e.db.price_approvals.insert_one(dict(foreign))
   r=await request('GET','/price-approvals/'+fid);rec('price.foreign_get_control',True,r.status_code in (403,404))
   r=await request('GET','/price-approvals');rec('price.list_scope_control',[own['id']],sorted(x['id'] for x in r.json()))
   r=await request('GET','/price-approvals/stats/summary');rec('price.stats_scope',1,r.json().get('total'))
   r=await request('PATCH','/price-approvals/'+fid,json={'data':{'requested_price':80}});rec('price.foreign_patch_rejected',True,r.status_code in (403,404),str(r.status_code))
   await e.db.price_approvals.update_one({'id':fid},{'$set':{'attachments':[{'id':'TEST','is_deleted':False}]}})
   r=await request('POST','/price-approvals/'+fid+'/submit');rec('price.foreign_submit_rejected',True,r.status_code in (403,404),str(r.status_code))
   r=await request('POST','/price-approvals/'+fid+'/approve',headers={'Authorization':'Bearer local-decision-token'},json={});rec('price.foreign_approve_rejected',True,r.status_code in (403,404),str(r.status_code))
   r=await request('GET','/price-approvals/effective',params={'customer_id':'CB','product_id':'P','entity_id':'B','quantity':10});rec('price.foreign_effective_hidden',False,r.json().get('has_special'))
   await e.db.price_approvals.update_one({'id':fid},{'$set':{'status':'draft'}})
   r=await request('DELETE','/price-approvals/'+fid);rec('price.foreign_delete_rejected',True,r.status_code in (403,404),str(r.status_code))
 except Exception:ERRORS.append(traceback.format_exc())
 finally:
  Path(__file__).with_name('price-approval-scope90-results.json').write_text(json.dumps(dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,harness_errors=ERRORS,scope='Original ASGI routes, actual local A/B master/entity records and explicitly assigned A-only sales capabilities; no external action.'),ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'observations':len(RESULTS),'differences':[r['id'] for r in RESULTS if r['status']!='pass'],'errors':ERRORS}));e.client.close()
if __name__=='__main__':asyncio.run(main())
