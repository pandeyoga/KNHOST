"""OD sample decision, contract/quantity pricing, procurement and fulfillment consumers.

Direct service fixtures are explicit. A failure is injected only at a database write
boundary; the original business/calculation functions are never replaced.
"""
import asyncio,copy,io,json,os,traceback
from pathlib import Path
from datetime import datetime,timezone,timedelta
os.environ['LOCAL_STORAGE_DIR']=str(Path(__file__).parents[1]/'continuation-90/od-files')
import service_env90 as e
from services import special_order_phase2 as s
from PIL import Image
RESULTS=[];ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def reject(key,fn,want=True):
 try:await fn;blocked=False
 except (ValueError,__import__('fastapi').HTTPException):blocked=True
 rec(key,want,blocked)
class ProductWriteFault:
 def __init__(self,coll):self.coll=coll
 def __getattr__(self,name):return getattr(self.coll,name)
 async def update_one(self,*args,**kw):raise RuntimeError('Audit synthetic DB product-write failure')
class FaultDb:
 def __init__(self,db):self.db=db
 def __getattr__(self,name):return ProductWriteFault(self.db.products) if name=='products' else getattr(self.db,name)
async def main():
 try:
  await e.setup(template=True);actor=await e.db.users.find_one({'email':'admin@kainnusantara.id'},{'_id':0})
  supplier=await e.db.suppliers.find_one({'status':'active','entity_id':{'$in':['ent_ksc','all',None]}})
  assert supplier
  await e.db.products.insert_one({'id':'OD-P','sku':'OD-P','name':'Exclusive cloth','price':100,'harga_pokok':50,'unit':'yard','status':'active','lifecycle':'produksi','category':'woven','line_code':'woven'})
  await e.db.md_samples.insert_one({'id':'OD-SAMPLE','number':'OD-SAMPLE','status':'decided','sample_types':['labdip','handfeel'],'created_at':'2026-01-01','decision':{'price':100,'supplier_id':supplier['id'],'supplier_name':supplier.get('name','Supplier'),'product_id':'OD-P','product_sku':'OD-P','contract_number':'AUD-CON'}})
  def od(key,**extra):return {'id':key,'number':key,'entity_id':'ent_ksc','title':'Audit OD','customer_id':'AUD-C','customer_name':'Customer','status':'sampling','sample_ids':['OD-SAMPLE'],'custom_item':{'quantity':10,'unit':'yard','description':'Exclusive cloth','target_price':150},'pricing':{},'customer_decisions':[],'status_history':[],**extra}
  async def save(doc):await e.db.special_orders.insert_one(dict(doc));return doc
  rec('od.review_empty',False,(await s.review_ready(od('EMPTY',sample_ids=[])))['ready'])
  rec('od.review_decided',True,(await s.review_ready(od('READY')))['ready'])
  await e.db.md_samples.insert_one({'id':'REV','number':'REV','created_at':'2026-02-01','status':'draft'})
  rec('od.latest_revision_blocks_old_winner',False,(await s.review_ready(od('REVISION',sample_ids=['OD-SAMPLE','REV'])))['ready'])
  for key,doc,payload in [('invalid',od('GUARD'),{'decision':'unknown'}),('draft',od('GUARD',status='draft'),{'decision':'acc'}),('locked',od('GUARD',pricing={'locked':True}),{'decision':'acc'}),('no_result',od('GUARD',sample_ids=[]),{'decision':'acc'}),('reject_note',od('GUARD'),{'decision':'tolak'}),('revise_note',od('GUARD'),{'decision':'revisi'})]:await reject('od.decision_guard_'+key,s.customer_decide(doc,payload,actor,'ent_ksc'))
  doc=await save(od('OD-ACC'));decision=await s.customer_decide(doc,{'decision':'acc','note':'Approved','contact_name':'Customer PIC'},actor,'ent_ksc')
  fresh=await e.db.special_orders.find_one({'id':doc['id']},{'_id':0});rec('od.customer_acc','acc',fresh['customer_decision']);rec('od.customer_history',1,len(fresh['customer_decisions']));rec('od.customer_actor',actor['name'],decision['recorded_by'])
  for margin,unit,total in [(0,100,1000),(30,130,1300),(50,150,1500),(500,600,6000)]:
   pv=await s.pricing_preview(fresh,margin);rec('od.price_unit_'+str(margin),unit,pv['final_unit_price']);rec('od.price_total_'+str(margin),total,pv['total'])
  for margin in [-1,501]:await reject('od.margin_guard_'+str(margin),s.lock_price(fresh,{'margin_pct':margin,'auto_po':False},actor))
  await reject('od.lock_needs_acc',s.lock_price(od('UNAPPROVED'),{'auto_po':False},actor))
  await reject('od.lock_needs_winning_contract',s.lock_price(od('NO-COST',sample_ids=[],customer_decision='acc'),{'auto_po':False},actor))
  locked=await s.lock_price(fresh,{'margin_pct':30,'auto_po':False},actor);rec('od.lock_total',1300,locked['total']);rec('od.lock_sku_price',130,(await e.db.products.find_one({'id':'OD-P'}))['price'])
  fresh=await e.db.special_orders.find_one({'id':doc['id']},{'_id':0});await reject('od.lock_repeat_guard',s.lock_price(fresh,{'auto_po':False},actor))
  rec('od.locked_preview_snapshot',1300,(await s.pricing_preview(fresh,500))['total'])
  await reject('od.unlock_requires_admin',s.unlock_price(fresh,{'role':'sales','name':'Sales'},'Reprice'))
  await reject('od.unlock_requires_reason',s.unlock_price(fresh,actor,''))
  await reject('od.unlock_blocks_existing_po',s.unlock_price({**fresh,'linked_po_id':'PO'},actor,'Reprice'))
  await s.unlock_price(fresh,actor,'Synthetic reprice');fresh=await e.db.special_orders.find_one({'id':doc['id']},{'_id':0});rec('od.unlock_flag',False,fresh['pricing']['locked']);rec('od.unlock_reason','Synthetic reprice',fresh['pricing']['unlock_reason'])
  await reject('od.procure_needs_lock',s.auto_procure(fresh,actor))
  for key,pricing in [('sku',{'locked':True,'supplier_id':supplier['id']}),('supplier',{'locked':True,'product_id':'OD-P'})]:await reject('od.procure_guard_'+key,s.auto_procure(od('GUARD',pricing=pricing),actor))
  rec('od.procure_existing_idempotent','sudah ada PO',(await s.auto_procure(od('EXISTING',linked_po_id='PO'),actor))['skipped'])
  doc=await save(od('OD-REJECT'));await s.customer_decide(doc,{'decision':'tolak','note':'Wrong handfeel'},actor,'ent_ksc');rec('od.reject_cancelled','cancelled',(await e.db.special_orders.find_one({'id':doc['id']}))['status'])
  buf=io.BytesIO();Image.new('RGB',(20,20),'white').save(buf,'PNG')
  doc=await e.db.special_orders.find_one({'id':doc['id']},{'_id':0});f=await s.add_evidence(doc,'',actor['name'],'proof.png','image/png',buf.getvalue(),'Client note');doc=await e.db.special_orders.find_one({'id':doc['id']},{'_id':0})
  content,ct=await s.evidence_bytes(doc,f['id']);rec('od.evidence_content',True,content==buf.getvalue());rec('od.evidence_type','image/png',ct)
  await reject('od.evidence_missing',s.evidence_bytes(doc,'missing'));await reject('od.evidence_no_decision',s.add_evidence(od('EMPTY'),'missing','Audit','proof.png','image/png',buf.getvalue()))
  # Original DB write boundary fails after original OD price lock has committed.
  await e.db.products.update_one({'id':'OD-P'},{'$set':{'price':100,'harga_pokok':50}})
  doc=await save(od('OD-FAULT',customer_decision='acc'));original_db=s.db;s.db=FaultDb(original_db)
  try:await s.lock_price(doc,{'margin_pct':30,'auto_po':False},actor);fault_seen=False
  except RuntimeError:fault_seen=True
  finally:s.db=original_db
  rec('od.fault_injected',True,fault_seen)
  persisted=await e.db.special_orders.find_one({'id':doc['id']},{'_id':0});product=await e.db.products.find_one({'id':'OD-P'})
  rec('od.failed_lock_no_committed_mismatch',False,bool(persisted.get('price_locked') and product['price']!=persisted.get('final_price')))
  try:await s.lock_price(persisted,{'margin_pct':30,'auto_po':False},actor);retry='recovered'
  except ValueError:retry='blocked_already_locked'
  rec('od.failed_lock_retry_recovers','recovered',retry)
  rec('od.fulfillment_no_shipment',False,await s.fulfillment_complete('SO-AUD'))
  await e.db.shipments.insert_many([{'id':'SHIP-A','order_id':'SO-AUD','status':'dispatched'},{'id':'SHIP-B','order_id':'SO-AUD','status':'dispatched'},{'id':'SHIP-C','order_id':'SO-AUD','status':'cancelled'}])
  rec('od.fulfillment_no_delivery',False,await s.fulfillment_complete('SO-AUD'))
  await e.db.logistics_deliveries.insert_one({'id':'DEL-A','order_id':'SO-AUD','status':'delivered','shipment_ids':['SHIP-A']});rec('od.fulfillment_partial',False,await s.fulfillment_complete('SO-AUD'))
  await e.db.logistics_deliveries.insert_one({'id':'DEL-B','order_id':'SO-AUD','status':'completed','shipment_ids':['SHIP-B']});rec('od.fulfillment_all',True,await s.fulfillment_complete('SO-AUD'))
  rec('od.on_received_missing',{},await s.on_goods_received('missing'))
  await reject('od.on_received_needs_so',s.on_goods_received('OD-ACC'))
  rec('od.default_warehouse_exists',True,bool(await s.default_warehouse_id('ent_ksc')))
  await e.db.warehouses.delete_many({})
  rec('od.default_warehouse_empty','',await s.default_warehouse_id('ent_ksc'))
 except Exception:ERRORS.append(traceback.format_exc())
 finally:
  Path(__file__).with_name('special-order-chain90-results.json').write_text(json.dumps(dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,harness_errors=ERRORS,scope='Original OD services on explicit decided-sample/document fixtures; no public R&D-producer or external fulfillment claim. Injected DB-write fault disclosed.'),ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'observations':len(RESULTS),'differences':[r['id'] for r in RESULTS if r['status']!='pass'],'errors':ERRORS}));e.client.close()
if __name__=='__main__':asyncio.run(main())
