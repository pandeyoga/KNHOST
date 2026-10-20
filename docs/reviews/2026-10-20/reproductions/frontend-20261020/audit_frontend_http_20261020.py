import requests,json
from pathlib import Path
base='http://127.0.0.1:8020/api'
out=Path(__file__).resolve().parent.parent/'output/audit-plan-2026-10-19/evidence/frontend-20261020'
results=[]
for email in ['admin@kainnusantara.id','wh.admin@kainnusantara.id','whadmin@kainnusantara.id','finance@kainnusantara.id']:
    r=requests.post(base+'/auth/login',json={'email':email,'password':'demo12345' if email.startswith('admin@') else 'demo1234'},timeout=15)
    row={'account':email,'login_http':r.status_code}
    if r.status_code==200:
        h={'Authorization':'Bearer '+r.json()['token'],'X-Entity-Id':'ent_ksc'}
        u=requests.get(base+'/auth/me',headers=h,timeout=15).json()
        user=u.get('user',u)
        row['role']=user.get('role'); row['warehouse_permissions']=(user.get('permissions') or {}).get('warehouse');row['payment_variance_permissions']=(user.get('permissions') or {}).get('payment_variance')
        w=requests.get(base+'/warehouses',params={'scope':'all'},headers=h,timeout=15)
        row['warehouse_all_http']=w.status_code
        row['warehouse_response']=w.json() if w.status_code!=200 else {'count':len(w.json())}
    results.append(row)
(out/'warehouse-role-http.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=True,indent=2))
