"""Original public procurement APIs; totals, drawdown and scope have independent oracles."""
import asyncio,copy,json,traceback
from pathlib import Path
from datetime import datetime,timezone,timedelta
import wave2_env as e
from services import blanket_po_service as blanket,rfq_service as rfq
RESULTS=[];CONTEXT={};ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def call(h,method,path,body=None,expect=None):
 r=await h.request(method,'/api/'+path,json=body)
 value=r.json() if r.headers.get('content-type','').startswith('application/json') else r.text
 if expect is not None:rec(method+' '+path,expect,r.status_code,str(value)[:250] if r.status_code!=expect else '')
 return r.status_code,value
async def ok(h,method,path,body=None):
 code,value=await call(h,method,path,body)
 assert code==200,(method,path,code,value)
 return value
async def seed():
 assert await e.db.users.count_documents({})==0
 template=e.client['knhost_audit_native90_template']
 if await template.users.count_documents({}):
  for name in await template.list_collection_names():
   docs=await template[name].find({}).to_list(None)
   if docs:await e.db[name].insert_many(docs)
 else:
  from seed_realistic import seed_all
  await seed_all(e.db)
 await e.db.users.insert_one(dict(id='PROC90',name='Audit Procurement',email='proc90@example.invalid',role='finance',status='active',home_entity_id='ent_ksc',allowed_entity_ids=['ent_ksc']))
 await e.db.sessions.insert_one(dict(token='audit-proc90',user_id='PROC90',expires_at=datetime.now(timezone.utc)+timedelta(hours=2)))
 actions=['view','create','update','approve','reject','award','cancel']
 matrix={m:actions for m in ['rfq','purchase_order','purchase_requisition','warehouse','accounting']}
 await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance':matrix}},upsert=True)
 products=await e.db.products.find({'lifecycle':{'$nin':['concept','labdip','proofing','discontinued']}},{'_id':0}).to_list(None)
 products=[p for p in products if p.get('base_unit') in ('meter','yard')]
 assert len(products)>=2
 suppliers=await e.db.suppliers.find({'status':{'$ne':'inactive'}},{'_id':0}).to_list(None)
 assert len(suppliers)>=2
 CONTEXT.update(products=[{'id':p['id'],'sku':p.get('sku'),'base_unit':p.get('base_unit')} for p in products[:2]],supplier_ids=[s['id'] for s in suppliers[:2]])
 return products[:2],[s['id'] for s in suppliers[:2]]
async def blankets(h,p,s):
 item={'product_id':p['id'],'contract_qty':100,'contract_price':10,'unit':p['base_unit']}
 base={'supplier_id':s,'warehouse_id':'wh_jakarta','entity_id':'ent_ksc','items':[item],'tax_mode':'non_ppn'}
 b=await ok(h,'POST','purchase-orders/blanket',base);bid=b['id']
 rec('blanket.default_cap',1000,b['contract_value_cap'])
 rec('blanket.has_no_inbound',0,await e.db.wms_tasks.count_documents({'po_id':bid}))
 for label,patch in [
  ('warehouse',{'warehouse_id':'missing'}),('empty',{'items':[]}),('product',{'items':[{**item,'product_id':'missing'}]}),
  ('duplicate',{'items':[item,item]}),('quantity',{'items':[{**item,'contract_qty':0}]}),
  ('unit',{'items':[{**item,'unit':'nonexistent_unit'}]}),('date_order',{'valid_from':'2026-10-06','valid_until':'2026-10-01'}),
  ('term',{'payment_term_code':'NEVER99'}),('tax',{'tax_mode':'nonsense'}),('supplier',{'supplier_id':'missing'})]:
  code,val=await call(h,'POST','purchase-orders/blanket',{**base,**patch})
  rec('blanket.invalid_'+label,True,code in (400,404,422),str(val)[:220])
 co={'items':[{'product_id':p['id'],'quantity':20,'price':0,'unit':p['base_unit']}]}
 child=await ok(h,'POST',f'purchase-orders/{bid}/call-off',co)
 rec('calloff.price_inherits',10,child['items'][0]['price']);rec('calloff.total',200,child['total_amount'])
 detail=await ok(h,'GET',f'purchase-orders/{bid}')
 rec('calloff.called_qty',20,detail['contract_items'][0]['called_qty']);rec('calloff.remaining_qty',80,detail['contract_items'][0]['remaining_qty'])
 rec('calloff.value_remaining',800,detail['value_remaining'])
 CONTEXT['calloff']=dict(id=child['id'],status=child['status'],items=child['items'])
 for label,body in [('empty',{'items':[]}),('unit',{'items':[{**co['items'][0],'unit':'kg'}]}),
  ('zero',{'items':[{**co['items'][0],'quantity':0}]}),('foreign_product',{'items':[{**co['items'][0],'product_id':'missing'}]}),
  ('duplicate',{'items':[co['items'][0],co['items'][0]]}),('override_no_reason',{'items':[{**co['items'][0],'price':12}]})]:
  code,val=await call(h,'POST',f'purchase-orders/{bid}/call-off',body);rec('calloff.invalid_'+label,True,code in (400,404,422),str(val)[:200])
 over=await ok(h,'POST',f'purchase-orders/{bid}/call-off',{'items':[{**co['items'][0],'quantity':81}]})
 rec('calloff.over_qty_requires_approval',True,over['approval_required'])
 rec('calloff.over_qty_waits', 'waiting_approval',over['status'])
 rec('calloff.exhausted_new_rejected',400,(await call(h,'POST',f'purchase-orders/{bid}/call-off',co))[0])
 override=await ok(h,'POST','purchase-orders/blanket',base)
 changed=await ok(h,'POST',f"purchase-orders/{override['id']}/call-off",{'items':[{**co['items'][0],'price':12}],'price_override_reason':'Supplier revised agreed price'})
 rec('calloff.override_value',240,changed['total_amount'])
 await ok(h,'POST',f"purchase-orders/{override['id']}/close-contract",{'reason':'Business commitment ended'})
 await call(h,'POST',f"purchase-orders/{override['id']}/close-contract",{},400)
 await call(h,'POST',f"purchase-orders/{override['id']}/call-off",co,400)
 expired=await ok(h,'POST','purchase-orders/blanket',{**base,'valid_until':'2000-01-01'})
 await call(h,'POST',f"purchase-orders/{expired['id']}/call-off",co,400)
 # Cancelled/rejected child documents are deliberately controlled fixtures, not API success claims.
 drawid='AUDIT90-DRAWDOWN';drawbase={'id':drawid,'po_type':'blanket','status':'active','contract_value_cap':1000,'contract_items':[item]}
 await e.db.purchase_orders.insert_one(drawbase)
 for i,status in enumerate(['pending','cancelled','rejected']):
  await e.db.purchase_orders.insert_one({'id':f'{drawid}-{i}','po_type':'call_off','parent_po_id':drawid,'status':status,'items':[{'product_id':p['id'],'quantity':20}],'total_amount':200})
 draw=await blanket.recompute_blanket_drawdown(drawbase,False)
 rec('drawdown.only_active_child',20,draw['contract_items'][0]['called_qty']);rec('drawdown.excludes_cancelled_rejected',200,draw['value_called'])
 for b,want in [({'status':'closed'},'closed'),({'valid_until':'2000-01-01'},'expired'),({'contract_value_cap':200},'exhausted')]:
  rec('drawdown.status_'+want,want,blanket._derive_status({**drawbase,**b},draw['contract_items'],200))
async def rfqs(h,products,suppliers):
 items=[{'product_id':p['id'],'quantity':i+1,'unit':p['base_unit'],'line_id':f'L{i+1}','qty_rolls':i+1} for i,p in enumerate(products)]
 base={'source':'manual','warehouse_id':'wh_jakarta','entity_id':'ent_ksc','items':items,'supplier_ids':suppliers}
 async def new():return await ok(h,'POST','rfqs',base)
 async def quote(rid,sid,prices=(10,20),availability=(True,True)):
  return await ok(h,'POST',f'rfqs/{rid}/quote',{'supplier_id':sid,'lines':[{'line_id':f'L{i+1}','price':v,'available':availability[i]} for i,v in enumerate(prices)]})
 r=await new();rid=r['id']
 rec('rfq.qty_rolls_preserved',[1,2],[i['qty_rolls'] for i in r['items']])
 await ok(h,'POST',f'rfqs/{rid}/send')
 await call(h,'POST',f'rfqs/{rid}/send',None,400)
 await call(h,'POST',f'rfqs/{rid}/award',{'mode':'full','full_supplier_id':suppliers[0]},400)
 for label,body in [('uninvited',{'supplier_id':'missing','lines':[]}),('bad_line',{'supplier_id':suppliers[0],'lines':[{'line_id':'bad','price':10}]}),
  ('zero',{'supplier_id':suppliers[0],'lines':[{'line_id':'L1','price':0}]}),('unavailable_only',{'supplier_id':suppliers[0],'lines':[{'line_id':'L1','price':10,'available':False}]})]:
  code,val=await call(h,'POST',f'rfqs/{rid}/quote',body);rec('rfq.invalid_'+label,True,code in (400,404),str(val)[:200])
 await quote(rid,suppliers[0],(10,20));await quote(rid,suppliers[1],(12,18))
 cmp=await ok(h,'GET',f'rfqs/{rid}/compare')
 rec('rfq.total_s1',50,next(x['total'] for x in cmp['suppliers'] if x['supplier_id']==suppliers[0]))
 rec('rfq.total_s2',48,next(x['total'] for x in cmp['suppliers'] if x['supplier_id']==suppliers[1]))
 rec('rfq.cheapest_full',suppliers[1],cmp['recommended_full_supplier_id'])
 rec('rfq.cheapest_lines',[suppliers[0],suppliers[1]],[x['supplier_id'] for x in cmp['recommended_line_awards']])
 for label,body in [('unknown_mode',{'mode':'bad'}),('missing_full',{'mode':'full','full_supplier_id':'missing'}),('empty_lines',{'mode':'line'}),
  ('bad_line',{'mode':'line','line_awards':[{'line_id':'bad','supplier_id':suppliers[0]}]}),
  ('bad_supplier',{'mode':'line','line_awards':[{'line_id':'L1','supplier_id':'missing'}]}),
  ('incomplete',{'mode':'line','line_awards':[{'line_id':'L1','supplier_id':suppliers[0]}]})]:
  await call(h,'POST',f'rfqs/{rid}/award',body,400)
 award=await ok(h,'POST',f'rfqs/{rid}/award',{'mode':'line','line_awards':cmp['recommended_line_awards']})
 rec('rfq.split_two_pos',2,len(award['pos']));rec('rfq.split_value',46,sum(p['total_amount'] for p in award['pos']))
 await call(h,'POST',f'rfqs/{rid}/award',{'mode':'full','full_supplier_id':suppliers[0]},409)
 await call(h,'POST',f'rfqs/{rid}/quote',{'supplier_id':suppliers[0],'lines':[]},400)
 await call(h,'POST',f'rfqs/{rid}/cancel',{'reason':'done'},409)
 for po in award['pos']:
  rec('rfq.po_origin_'+po['id'],rid,po['source_rfq_id'])
  for it in po['items']:
   pl=await e.db.supplier_price_lists.find_one({'supplier_id':po['supplier_id'],'product_id':it['product_id'],'source':'rfq_award'})
   rec('rfq.price_list_'+it['product_id'],it['price'],pl['price'] if pl else None)
 full=await new();await quote(full['id'],suppliers[0]);fa=await ok(h,'POST',f"rfqs/{full['id']}/award",{'mode':'full','full_supplier_id':suppliers[0]})
 rec('rfq.full_single_po',1,len(fa['pos']));rec('rfq.full_total',50,fa['pos'][0]['total_amount'])
 cancelled=await new();await ok(h,'POST',f"rfqs/{cancelled['id']}/cancel",{'reason':'Demand withdrawn'})
 await call(h,'POST',f"rfqs/{cancelled['id']}/cancel",{},409)
 await call(h,'POST',f"rfqs/{cancelled['id']}/award",{'mode':'full','full_supplier_id':suppliers[0]},400)
 # Supplier explicitly marks L2 unavailable but provides a retained prior price.
 unavailable=await new();await quote(unavailable['id'],suppliers[0],(10,20),(True,False))
 comp=await ok(h,'GET',f"rfqs/{unavailable['id']}/compare")
 rec('rfq.unavailable_not_complete_control',False,comp['suppliers'][0]['complete'])
 before=await e.db.purchase_orders.count_documents({'source_rfq_id':unavailable['id']})
 code,value=await call(h,'POST',f"rfqs/{unavailable['id']}/award",{'mode':'full','full_supplier_id':suppliers[0]})
 rec('rfq.full_unavailable_rejected',400,code)
 rec('rfq.full_unavailable_no_po',before,await e.db.purchase_orders.count_documents({'source_rfq_id':unavailable['id']}))
 CONTEXT['unavailable_full']={'rfq_id':unavailable['id'],'response':value}
 foreign_entity=await e.db.business_entities.find_one({'id':{'$ne':'ent_ksc'},'status':'active'},{'_id':0})
 assert foreign_entity,'A real second active legal entity is required for the scope control'
 foreign=await new();await e.db.rfqs.update_one({'id':foreign['id']},{'$set':{'entity_id':foreign_entity['id']}})
 CONTEXT['foreign_scope_fixture']={'rfq_id':foreign['id'],'entity_id':foreign_entity['id'],'entity_exists':True,'actor_allowed_entity_ids':['ent_ksc'],
  'note':'A synthetic RFQ created through original public producer is assigned a real second active legal owner for isolated scope checks.'}
 rec('rfq.foreign_detail_denied_control',True,(await call(h,'GET',f"rfqs/{foreign['id']}"))[0] in (403,404))
 rec('rfq.foreign_compare_denied',True,(await call(h,'GET',f"rfqs/{foreign['id']}/compare"))[0] in (403,404))
 code,value=await call(h,'POST',f"rfqs/{foreign['id']}/cancel",{'reason':'Scope test'})
 rec('rfq.foreign_cancel_denied',True,code in (403,404))
 rec('rfq.foreign_state_preserved','draft',(await e.db.rfqs.find_one({'id':foreign['id']}))['status'])
async def main():
 try:
  products,suppliers=await seed()
  transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False)
  async with e.httpx.AsyncClient(transport=transport,base_url='http://audit.local',headers={'Authorization':'Bearer audit-proc90','X-Entity-Id':'ent_ksc'}) as h:
   for name,fn in [('blankets',lambda:blankets(h,products[0],suppliers[0])),('rfqs',lambda:rfqs(h,products,suppliers))]:
    try:await fn()
    except Exception:ERRORS.append({'suite':name,'error':traceback.format_exc()})
 except Exception:ERRORS.append({'suite':'setup','error':traceback.format_exc()})
 finally:
  result=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,context=CONTEXT,harness_errors=ERRORS,blocked_external=e.blocked)
  out=Path(__file__).with_name('procurement-lifecycle90-results.json');out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
  print(json.dumps({'observations':len(RESULTS),'differences':[r['id'] for r in RESULTS if r['status']!='pass'],'errors':ERRORS},ensure_ascii=False));e.client.close()
if __name__=='__main__':asyncio.run(main())
