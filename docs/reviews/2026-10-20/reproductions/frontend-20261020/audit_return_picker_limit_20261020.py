from pathlib import Path
from pymongo import MongoClient
from datetime import datetime,timezone,timedelta
import uuid,requests,json
base='http://127.0.0.1:8020/api';db=MongoClient('mongodb://127.0.0.1:27138')['kn_frontend_audit_20261020']
assert db.name=='kn_frontend_audit_20261020'
tag='FE_PICKER_'+uuid.uuid4().hex[:10];now=datetime.now(timezone.utc)
common={'entity_id':'ent_ksc','customer_id':'cust_toko_kain','customer_name':'Audit Customer','items':[],'order_type':'regular','audit_fixture':tag,'total_amount':0,'grand_total':0}
old={**common,'id':tag+'_shipped','number':tag+'_SHIPPED','status':'shipped','created_at':(now-timedelta(hours=1)).isoformat(),'shipped_at':(now-timedelta(minutes=30)).isoformat()}
rows=[old]+[{**common,'id':tag+'_'+str(i),'number':tag+'_DRAFT_'+str(i),'status':'draft','created_at':(now+timedelta(microseconds=i)).isoformat()} for i in range(201)]
db.sales_orders.insert_many(rows)
result={'id':'FE-SR-06','commit':'8dab383f764df80737bfe02f887422b3fd72aa70','scenario':'201 newer draft orders hide an otherwise recent shipped SO from nonpaged source picker','fixture_inserted':len(rows)}
try:
    r=requests.post(base+'/auth/login',json={'email':'admin@kainnusantara.id','password':'demo12345'},timeout=15);r.raise_for_status()
    h={'Authorization':'Bearer '+r.json()['token'],'X-Entity-Id':'ent_ksc'}
    a=requests.get(base+'/sales-orders',headers=h,timeout=20);a.raise_for_status()
    data=a.json();eligible=[x for x in data if x.get('status') in ['confirmed','partially_picked','picked','partially_shipped','shipped','done']]
    b=requests.get(base+'/sales-orders',headers=h,params={'page':1,'page_size':20,'q':old['number']},timeout=20);b.raise_for_status()
    found=b.json();found_items=found.get('items',[]) if isinstance(found,dict) else found
    result.update(nonpaged_http=a.status_code,nonpaged_count=len(data),shipped_in_picker_source=any(x['id']==old['id'] for x in data),eligible_after_frontend_filter=len(eligible),paged_search_http=b.status_code,paged_search_finds_shipped=any(x['id']==old['id'] for x in found_items),shipped_age_minutes=30)
finally:
    result['fixture_removed']=db.sales_orders.delete_many({'audit_fixture':tag}).deleted_count
out=Path(__file__).resolve().parent.parent/'output/audit-plan-2026-10-19/evidence/frontend-20261020/return-picker-http.json'
out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
