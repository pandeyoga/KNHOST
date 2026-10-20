import os,sys,json,asyncio,time,uuid,requests
from pathlib import Path
root=Path(__file__).resolve().parent/'KNHOST-plan-audit-2026-10-19'
sys.path.insert(0,str(root/'backend'))
os.environ.update(MONGO_URL='mongodb://127.0.0.1:27138',DB_NAME='kn_plan_deep_'+uuid.uuid4().hex,KN_DISABLE_SCHEDULER='1')
from db import db,client
from services import rnd_revalidation_service as rv
out=Path(__file__).resolve().parent.parent/'output/audit-plan-2026-10-19/evidence/deep-checks.json'
results=[]
async def run():
    # Actual service with actual MongoDB; no replacement of validation functions.
    p={'id':'audit-p','sku':'AUDIT-P'};await db.products.insert_one(dict(p))
    s={'id':'audit-s','number':'AUDIT-S','product_id':p['id'],'product_sku':p['sku'],'entity_id':'ent_ksc','purpose':'revalidation','status':'assessed','sample_types':['labdip','handfeel'],
       'revalidation':{'supplier_id':'audit-sup','supplier_name':'Audit Supplier','cycle_no':1},
       'rounds':[{'id':'r1','round_no':1,'type_code':'labdip','supplier_id':'audit-sup','result':'acc'},{'id':'r2','round_no':1,'type_code':'handfeel','supplier_id':'audit-sup','result':'tolak'}]}
    await db.md_samples.insert_one(dict(s))
    r=await rv.decide(s,{'result':'pass','note':'audit latest failed'}, {'name':'Audit'})
    results.append({'id':'AUD-RND-01','result':'reproduced','actual_status':r['status'],'decision_result':r['decision']['result'],'decision_round':r['decision']['round_id'],'types':['labdip','handfeel'],'labdip_result':'acc','handfeel_result':'tolak','expected':'Do not certify both requested tests using ACC for only one type while the other type is rejected.'})
    await db.design_gallery.insert_one({'id':'audit-design','status':'approved','version':2,'versions':[{'version':2,'acc':True}]})
    r=await rv.existing_artwork({'design_id':'audit-design','design_version':999},p['id'])
    results.append({'id':'AUD-RND-02','result':'reproduced','actual':r,'expected':'Reject nonexistent artwork version 999.'})
    await db.supplier_contracts.insert_one({'id':'audit-contract','partner_id':'audit-sup','product_id':p['id'],'entity_id':'ent_ksc','contract_type':'purchase','status':'terminated'})
    r=await rv._validate_contract_ref('audit-contract',s,'audit-sup')
    results.append({'id':'AUD-RND-03','result':'reproduced','actual':r,'expected':'Apply the active-contract filter from contract-options to direct submissions too; confirm whether historical contracts may be selected.'})
    client.close()
asyncio.run(run())
# Real full-app route, seeded audit database only.
base='http://127.0.0.1:8019/api'
r=requests.post(base+'/auth/login',json={'email':'admin@kainnusantara.id','password':'demo12345'},timeout=20)
if r.status_code==200:
    h={'Authorization':'Bearer '+r.json()['token'],'X-Entity-Id':'ent_ksc'}
    r=requests.post(base+'/export-center/jobs',headers=h,json={'dataset':'sales_finance','columns':['sales_name','grand_total'],'group_by':['sales_name'],'format':'csv'},timeout=30)
    result={'id':'AUD-EXP-01','create_http':r.status_code}
    if r.status_code==200:
        jid=r.json()['id']; result['job']=jid
        for _ in range(30):
            j=requests.get(base+'/export-center/jobs/'+jid,headers=h,timeout=20).json()
            if j.get('status') in ('done','failed'):break
            time.sleep(1)
        result['job_status']=j.get('status')
        d=requests.get(base+'/export-center/jobs/'+jid+'/download',headers=h,timeout=20)
        result['download_http']=d.status_code;result['detail']=d.text[:500] if d.status_code!=200 else 'download succeeded'
    else:result['detail']=r.text[:500]
    results.append(result)
else:results.append({'id':'AUD-EXP-01','result':'blocked_login','http':r.status_code})
out.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(results,indent=2,ensure_ascii=True))
