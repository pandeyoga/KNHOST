import asyncio,json,copy
from pathlib import Path
import integration_round4 as env
from services import rfid_service as rf,rfid_print_service as pr,rfid_ingest_service as gate,roll_service as rollsvc,store_credit_service as sc
from services import bank_recon_service as bank
B=Path(__file__).resolve().parent;db=env.db;results=[]
def record(id,observed,condition):
 assert condition,(id,observed)
 results.append({'id':id,'observed':observed});print(id,json.dumps(observed),flush=True)
def roll(id,**kw):return dict(id=id,roll_no=id,product_id='P',warehouse_id='W1',owner_entity_id='A',length_initial=100,length_remaining=100,status='available',unit='meter',unit_cost=10,created_at='2026-09-01',**kw)
async def main():
 await env.seed()
 await db.products.insert_one({'id':'P','name':'Fabric','sku':'P','base_unit':'meter'})
 r=roll('R');await db.inventory_rolls.insert_one(dict(r))
 await db.rfid_devices.insert_one({'id':'D','type':'handheld','warehouse_id':'W1','api_key':'audit-device','status':'offline'})
 tag=await rf.encode_tag('R',['A']);wire=pr.generate_rfid_zpl(tag['epc'],r,tag).split('^RFW,H^FD')[1].split('^FS')[0]
 raw=await gate.ingest({'id':'D','type':'handheld','warehouse_id':'W1'},[wire]);formatted=await gate.ingest({'id':'D','type':'handheld','warehouse_id':'W1'},[tag['epc']])
 record('I4-RF01',{'raw_result':raw['results'][0]['result'],'raw_reason':raw['results'][0]['reason'],'formatted_result':formatted['results'][0]['result']},raw['results'][0]['reason'].startswith('EPC tidak dikenal') and formatted['results'][0]['result']=='info')
 await db.putaway_orders.insert_one({'id':'PA','status':'cancelled','from_warehouse_id':'W1','to_warehouse_id':'W2','pa_number':'PA-1'})
 rr={**r,'status':'quarantine','journey':{'stage':'putaway_in_transit','putaway_order_id':'PA'}}
 verdict=await gate._doc_gate_decision({'direction':'out','warehouse_id':'W1'},rr)
 record('I4-RF02',verdict,verdict['result']=='green')
 await db.rfid_devices.update_one({'id':'D'},{'$set':{'status':'offline'}})
 dev=await gate.authenticate('audit-device');await gate.heartbeat(dev)
 record('I4-RF03',{'after_heartbeat':(await db.rfid_devices.find_one({'id':'D'}))['status']},(await db.rfid_devices.find_one({'id':'D'}))['status']=='online')
 # Barrier delays return from a real Mongo atomic update, not its semantics.
 r=roll('SPLIT');await db.inventory_rolls.insert_one(dict(r));entered=asyncio.Event();resume=asyncio.Event()
 class CollectionBarrier:
  def __getattr__(self,k):return getattr(db.inventory_rolls,k)
  async def find_one_and_update(self,*a,**kw):
   result=await db.inventory_rolls.find_one_and_update(*a,**kw)
   if asyncio.current_task().get_name()=='audit-split-A':entered.set();await resume.wait()
   return result
 class DatabaseBarrier:
  inventory_rolls=CollectionBarrier()
  def __getattr__(self,k):return getattr(db,k)
  def __getitem__(self,k):return self.inventory_rolls if k=='inventory_rolls' else db[k]
 realdb=rollsvc.db;rollsvc.db=DatabaseBarrier()
 try:
  a=asyncio.create_task(rollsvc._split_roll(copy.deepcopy(r),30,'SO-A'),name='audit-split-A')
  await asyncio.wait_for(entered.wait(),5);await rollsvc._split_roll(copy.deepcopy(r),40,'SO-B');resume.set();await a
 finally:rollsvc.db=realdb
 rolls=await db.inventory_rolls.find({'$or':[{'id':'SPLIT'},{'parent_roll_id':'SPLIT'}]},{'_id':0}).to_list(20)
 qty=sum(x['length_remaining'] for x in rolls)
 record('I4-WM01',{'initial_qty':100,'final_qty':qty,'lengths':[x['length_remaining'] for x in rolls]},qty==140)
 # Full loading-check command chain against Mongo.
 from services import loading_check_service as lc
 await db.sales_orders.insert_one({'id':'LOAD-SO','entity_id':'A','number':'LOAD-SO'})
 await db.inventory_rolls.insert_many([{**roll('L1'),'status':'committed','rfid_tag_id':'LT','reserved_ref':{'type':'sales_order','id':'LOAD-SO'}},
                                      {**roll('L2'),'status':'committed','reserved_ref':{'type':'sales_order','id':'LOAD-SO'}}])
 await db.rfid_tags.insert_one({'id':'LT','epc':'LEPC','status':'active','roll_id':'L1'})
 session=await lc.start('LOAD-SO',['A'],'Audit')
 await pr.scan_verify(session['id'],['LEPC'],['A']);completed=await lc.complete(session['id'],['A']);await lc.dispatch_guard('LOAD-SO')
 record('I4-RF04',{'untagged':session['untagged_count'],'result':completed['result'],'dispatch_allowed':True},session['untagged_count']==1 and completed['result']=='clean')
 # Bank matching full service calls, including learning and all Mongo updates.
 await db.bank_statement_lines.insert_one({'id':'BL1','entity_id':'A','status':'unmatched','direction':'out','amount':100,'bank_account_id':'BANK1'})
 await db.cash_transactions.insert_one({'id':'CT1','entity_id':'A','direction':'in','amount':100,'bank_account_id':'BANK2','reconciled_amount':0})
 out=await bank.manual_match('BL1','CT1','Audit',['A'])
 record('I4-FN02',{'bank_direction':'out','cash_direction':'in','bank_account':'BANK1','cash_account':'BANK2','result':out['status']},out['status']=='matched')
 await db.bank_statement_lines.insert_one({'id':'BL2','entity_id':'A','status':'unmatched','direction':'out','amount':120,'bank_account_id':'BANK1'})
 await db.cash_transactions.insert_one({'id':'CT2','entity_id':'A','direction':'out','amount':100,'bank_account_id':'BANK1','reconciled_amount':0})
 await bank.match_split('BL2',[{'txn_id':'CT2','amount':60},{'txn_id':'CT2','amount':60}],'Audit',['A'])
 txn=await db.cash_transactions.find_one({'id':'CT2'})
 record('I4-FN03',{'cash_amount':100,'reconciled':txn['reconciled_amount']},txn['reconciled_amount']==120)
 # Real AR mutation, credit ledger and GL; no posting stand-in.
 await db.customers.insert_one({'id':'C','name':'Synthetic C','entity_id':'A'})
 await db.store_credit_ledger.insert_one({'id':'CR','customer_id':'C','entity_id':'A','amount':100,'kind':'issue','status':'posted'})
 await db.sales_orders.insert_one({'id':'SO','number':'SO-1','customer_id':'C','entity_id':'A','grand_total':200,'payments':[],'paid_total':0,'status':'delivered','payment_method':'credit'})
 await sc.redeem(customer_id='C',entity_id='A',amount=10,allocations=[{'order_id':'SO','amount':150}],actor={'name':'Audit'})
 balance=await sc.balance('C','A');order=await db.sales_orders.find_one({'id':'SO'},{'_id':0})
 record('I4-FN01',{'requested':10,'payment_sum':sum(x['amount'] for x in order['payments']),'credit_balance':balance,'journal_count':await db.journal_entries.count_documents({})},balance==-50)
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  (B/'integration_rfid_wms_finance.json').write_text(json.dumps({'database':env.DBNAME,'mode':'Original imported services, real Mongo; deterministic scheduling barrier only for split; no GL stubs','results':results,'external_network_attempts_blocked':env.blocked},ensure_ascii=False,indent=2),encoding='utf-8');env.client.close()
