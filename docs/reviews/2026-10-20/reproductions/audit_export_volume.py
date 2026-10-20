import os,sys,uuid,subprocess,json
from pathlib import Path
from pymongo import MongoClient
base=Path(__file__).resolve().parent.parent; root=base/'work/KNHOST-plan-audit-2026-10-19'
out=base/'output/audit-plan-2026-10-19/evidence'
tag='AUDIT_VOLUME_'+uuid.uuid4().hex
db=MongoClient('mongodb://127.0.0.1:27138')['kn_plan_audit_20261019']
assert db.name=='kn_plan_audit_20261019'
env=dict(os.environ,MONGO_URL='mongodb://127.0.0.1:27138',DB_NAME=db.name,REACT_APP_BACKEND_URL='http://127.0.0.1:8019',PYTHONPATH=str(root/'backend'),PYTHONIOENCODING='utf-8')
rows=[{'id':tag+'_'+str(i),'audit_fixture':tag,'owner_entity_id':'ent_ksc','entity_id':'ent_ksc','warehouse_id':'wh_jakarta','product_id':'audit_product_supplier','movement_type':'audit_fixture','quantity':i/100,'unit':'kg','timestamp':'2026-10-19T00:00:00+00:00'} for i in range(5001)]
db.inventory_movements.insert_many(rows)
try:
    with (out/'export-volume.log').open('w',encoding='utf-8') as f:
        r=subprocess.run([sys.executable,'-m','pytest',str(root/'backend/tests/test_l11_export_center.py'),'-k','partitions_not_truncated','-o','addopts=','-q','--tb=short','--basetemp='+str(out/'volume-temp'),'--junitxml='+str(out/'export-volume.xml')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=160)
    print('Volume test exit:',r.returncode)
finally:
    removed=db.inventory_movements.delete_many({'audit_fixture':tag}).deleted_count
    (out/'export-volume-fixture.json').write_text(json.dumps({'database':db.name,'inserted':5001,'removed':removed,'note':'Synthetic movements only for export volume test; no actual stock or financial postings. Fixtures removed after test.'},indent=2),encoding='utf-8')
