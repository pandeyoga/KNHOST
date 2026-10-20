"""Audit actual pricing service with deterministic read fixture + actual conversion payload expression.
No production files/data changed. MongoDB and the final Sales Order create call are not executed.
"""
import os, sys, json, asyncio, uuid, ast
from pathlib import Path
root=Path(__file__).resolve().parents[3]
app=root/'work/KNHOST-plan-audit-2026-10-19'
sys.path.insert(0,str(app/'backend'))
os.environ.update(MONGO_URL='mongodb://127.0.0.1:27139/?serverSelectionTimeoutMS=5000',DB_NAME='kn_frontend_multi_'+uuid.uuid4().hex)
from db import db,client
from services import special_order_phase2 as p2
from schemas import SalesOrderCreate,SalesOrderItemIn

async def main():
    od={'id':'audit-multi','number':'AUDIT-MULTI','status':'ready','entity_id':'ent_audit','customer_id':'cust_audit',
        'customer_decision':'acc','request_types':['labdip'],'sample_ids':['sampleA','sampleB'],
        'items':[{'id':'iA','quantity':100,'unit':'yard','description':'Artikel A'},
                 {'id':'iB','quantity':200,'unit':'yard','description':'Artikel B'}],
        'custom_item':{'quantity':100,'unit':'yard','target_price':0},'created_by':'Audit'}
    samples=[]
    for sid,pid,price,at in [('sampleA','prodA',10,'2026-10-19T01:00:00Z'),('sampleB','prodB',30,'2026-10-19T02:00:00Z')]:
        samples.append({'id':sid,'number':sid,'status':'decided','created_at':at,
            'special_order_id':od['id'],'sample_types':['labdip'],
            'decision':{'product_id':pid,'product_sku':pid,'price':price,'supplier_id':'supplier_'+pid}})
    class Cursor:
        async def to_list(self,n): return samples
    class Samples:
        def find(self,*args,**kwargs): return Cursor()
    class Settings:
        async def find_one(self,*args,**kwargs): return None
    class Reads:
        md_samples=Samples()
        system_settings=Settings()
    p2.db=Reads()
    pv=await p2.pricing_preview(od,30)
    # Actual route constructs its conversion payload from these saved linkage/pricing fields.
    so={**od,'linked_product_id':pv['product_id'],'pricing':{**pv,'locked':True}}
    src=(app/'backend/routers/special_orders.py').read_text(encoding='utf-8')
    mod=ast.parse(src)
    expr=next(n.value for n in ast.walk(mod) if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id=='so_payload' for t in n.targets)
              and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='SalesOrderCreate')
    ns={'so':so,'ci':so['custom_item'],'addr':{},'order_id':so['id'],
        'SalesOrderCreate':SalesOrderCreate,'SalesOrderItemIn':SalesOrderItemIn}
    payload=eval(compile(ast.Expression(expr),'<actual convert-to-so payload>','eval'),ns).model_dump()
    evidence={'id':'FE-SR-04','result':'reproduced_unit','method':'Actual pricing service with deterministic DB read fixture + actual conversion AST expression; MongoDB and order creation not executed',
        'request_items':od['items'],'supplier_costs':{'prodA':10,'prodB':30},'margin_pct':30,
        'pricing_actual':pv,'pricing_expected_total_for_two_items':9100,
        'conversion_actual_items':payload['items'],
        'conversion_expected_items':[{'product_id':'prodA','quantity':100,'unit':'yard'},{'product_id':'prodB','quantity':200,'unit':'yard'}],
        'conversion_expression_line':expr.lineno,
        'limit':'Unit-level reproduction of actual service mapping. Windows asyncio socketpair initialization blocked real Mongo run. This does not assert complete Sales Order inventory/AR execution.'}
    (Path(__file__).parent/'multi-item-evidence.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(evidence,indent=2,ensure_ascii=True))
    client.close()
try:
    main().send(None)
except StopIteration:
    pass
