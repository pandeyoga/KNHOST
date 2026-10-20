"""Latest snapshot actual HTTP reproduction; isolated fixtures only, no payments.
The OD intake is created by API, then test sample decisions are seeded to focus on pricing/conversion.
"""
from pathlib import Path
import json,uuid,copy,datetime,requests
from pymongo import MongoClient
OUT=Path(__file__).parent
base='http://127.0.0.1:8020/api'
mc=MongoClient('mongodb://127.0.0.1:27138',serverSelectionTimeoutMS=5000)
db=mc.kn_frontend_audit_20261020
suffix=uuid.uuid4().hex[:10]
owned={'products':[],'md_samples':[],'special_orders':[],'sales_orders':[]}
result={'snapshot':'8dab383f764df80737bfe02f887422b3fd72aa70','base_url':base,'database':db.name,'id':'FE-SR-04','steps':[]}
sess=requests.Session()
def call(method,path,**kw):
    r=sess.request(method,base+path,timeout=40,**kw)
    try:data=r.json()
    except ValueError:data=r.text[:1000]
    result['steps'].append({'method':method,'path':path,'http':r.status_code,'body':data})
    return r,data
try:
    r=sess.post(base+'/auth/login',json={'email':'admin@kainnusantara.id','password':'demo12345'},timeout=20)
    assert r.status_code==200,r.text
    sess.headers.update({'Authorization':'Bearer '+r.json()['token'],'X-Entity-Id':'ent_ksc'})
    fixture=db.products.find_one({'id':'audit_product_supplier'},{'_id':0})
    assert fixture
    for label,price in [('A',13),('B',39)]:
        p=copy.deepcopy(fixture);p.update(id=f'fe_multi_{suffix}_{label}',sku=f'FE-MULTI-{suffix}-{label}',
            name=f'FE audit article {label}',base_unit='yard',unit='yard',fabric_type='woven',category='Woven',price=price,
            catalog_scope='customer',exclusive_customer_id='cust_toko_kain',lifecycle='produksi',
            special_order_id='',special_order_number='',variant_key=f'audit_{suffix}_{label}',variant_label=label)
        db.products.insert_one(p);owned['products'].append(p['id'])
    r,od=call('POST','/special-orders',json={'customer_id':'cust_toko_kain','title':f'FE HTTP multi {suffix}',
        'items':[{'source_type':'customer_reference','description':'Artikel A','request_types':['labdip'],'quantity':100,'unit':'yard'},
                 {'source_type':'customer_reference','description':'Artikel B','request_types':['labdip'],'quantity':200,'unit':'yard'}],
        'expected_delivery':'2027-01-20','submit_for_approval':False})
    assert r.status_code==200,od
    oid=od['id'];owned['special_orders'].append(oid)
    for i,(label,cost,qty) in enumerate([('A',10,100),('B',30,200)]):
        sid=f'fe_multi_sample_{suffix}_{label}';owned['md_samples'].append(sid)
        db.md_samples.insert_one({'id':sid,'number':sid,'entity_id':'ent_ksc','special_order_id':oid,
            'special_order_item_id':od['items'][i]['id'],'status':'decided','sample_types':['labdip'],
            'created_at':f'2026-10-19T0{i+1}:00:00+00:00',
            'decision':{'product_id':owned['products'][i],'product_sku':f'FE-MULTI-{suffix}-{label}',
                        'supplier_id':'audit_global_supplier','supplier_name':'Audit Supplier','price':cost,'contract_number':f'AUDIT-{label}'}})
    db.special_orders.update_one({'id':oid},{'$set':{'status':'ready','customer_decision':'acc','sample_ids':owned['md_samples']}})
    r,pv=call('GET',f'/special-orders/{oid}/pricing',params={'margin_pct':30})
    assert r.status_code==200,pv
    result['pricing_actual']={k:pv.get(k) for k in ['product_id','quantity','unit','cost_price','final_unit_price','total']}
    result['expected_header_total_same_margin']=9100
    r,locked=call('POST',f'/special-orders/{oid}/lock-price',json={'margin_pct':30,'auto_po':False,'note':'Audit fixture only'})
    assert r.status_code==200,locked
    r,converted=call('POST',f'/special-orders/{oid}/convert-to-so',json={})
    if r.status_code==200:
        so=converted['sales_order'];owned['sales_orders'].append(so['id'])
        result['sales_order_actual']={k:so.get(k) for k in ['id','number','status','items','total_amount','grand_total','has_backorder']}
        result['reproduced_http']=len(so.get('items',[]))==1 and so['items'][0]['product_id']==owned['products'][1] and so['items'][0]['quantity']==100
    else:
        result['reproduced_http']=False
        result['blocked_at_conversion']=converted
    result['expected_items']=[{'product_id':owned['products'][0],'quantity':100,'unit':'yard'},{'product_id':owned['products'][1],'quantity':200,'unit':'yard'}]
except Exception as e:
    result['error']=str(e)
finally:
    cleaned={}
    for coll,ids in owned.items():
        if ids:cleaned[coll]=db[coll].delete_many({'id':{'$in':ids}}).deleted_count
    # Only auxiliary documents with this exact unique source/order id, if created.
    soids=owned['sales_orders'];oids=owned['special_orders']
    for coll,query in [('wms_tasks',{'order_id':{'$in':soids}}),('notifications',{'ref_id':{'$in':soids+oids}}),
                       ('doc_links',{'$or':[{'source_id':{'$in':soids+oids}},{'target_id':{'$in':soids+oids}}]})]:
        cleaned[coll]=db[coll].delete_many(query).deleted_count
    result['cleanup']=cleaned
    result['notes']='Real API on latest main. Seeded terminal sample/ACC state, not complete R&D or physical flow. No payments created. Test audit logs/counter sequence retained as test trace.'
    (OUT/'multi-item-http-latest-evidence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='steps'},indent=2,ensure_ascii=True,default=str))
    mc.close()
