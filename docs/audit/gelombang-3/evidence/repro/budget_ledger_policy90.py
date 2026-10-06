"""Finance budget producer/report/check consistency and original GL posting rules.

Budget API uses current schemas. Synthetic journals/POs are explicitly direct
report fixtures, not claims about the normal document producers. Posting helpers
are tested for account direction, conserved amounts and replay suppression.
"""
import asyncio,json,traceback,inspect
from pathlib import Path
import wave2_env as e
from services import gl_service as gl,budget_service as b,return_policy_service as rp
RESULTS=[];ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def reject(key,fn):
 try:await fn;out=False
 except ValueError:out=True
 rec(key,True,out)
async def budgets(h):
 async def req(method,path,body=None,params=None):return await h.request(method,'/api/finance/'+path,json=body,params=params)
 body={'entity_id':'A','year':2026,'month':1,'dimension':'account','key':'1-1300','amount':100}
 r=await req('POST','budgets',body);rec('budget.create',200,r.status_code);first=r.json();assert first.get('id'),r.text
 rec('budget.duplicate_create',400,(await req('POST','budgets',body)).status_code)
 second=(await req('POST','budgets',{**body,'month':2,'amount':200})).json();assert second.get('id'),second
 for key,patch in [('dimension',{'dimension':'bad'}),('key',{'key':'missing'}),('zero',{'amount':0}),('year_low',{'year':1900}),('year_high',{'year':3000}),('month_low',{'month':-1}),('month_high',{'month':13})]:
  rec('budget.create_guard_'+key,True,(await req('POST','budgets',{**body,**patch})).status_code in (400,422))
 for key,patch in [('zero',{'amount':0}),('month_low',{'month':-1}),('month_high',{'month':13})]:rec('budget.patch_guard_'+key,400,(await req('PATCH','budgets/'+first['id'],patch)).status_code)
 r=await req('PATCH','budgets/'+first['id'],{'amount':150,'note':'Updated envelope'});rec('budget.patch_amount',150,r.json()['amount'])
 await e.db.journal_entries.insert_many([
  {'id':'BUD-JE','entity_id':'A','status':'posted','date':'2026-01-15T00:00:00Z','source_type':'manual','lines':[{'account_code':'1-1300','debit':10,'credit':0}]},
  {'id':'BUD-VOID','entity_id':'A','status':'void','date':'2026-01-15T00:00:00Z','source_type':'manual','lines':[{'account_code':'1-1300','debit':999,'credit':0}]},
  {'id':'BUD-CLOSE','entity_id':'A','status':'posted','date':'2026-01-15T00:00:00Z','source_type':'closing','lines':[{'account_code':'1-1300','debit':999,'credit':0}]},
  {'id':'BUD-FOREIGN','entity_id':'B','status':'posted','date':'2026-01-15T00:00:00Z','source_type':'manual','lines':[{'account_code':'1-1300','debit':999,'credit':0}]}])
 await e.db.purchase_orders.insert_one({'id':'BUD-PO','entity_id':'A','status':'approved','expected_delivery_date':'2026-01-20','net_subtotal':20,'po_number':'PO-AUD'})
 report=(await req('GET','budget-vs-actual',params={'year':2026,'entity_id':'A'})).json();row=next(x for x in report['rows'] if x['id']==first['id'])
 for field,want in [('actual',10),('committed',20),('spent',30),('remaining',120),('used_pct',6.7),('spent_pct',20)]:rec('budget.report_'+field,want,row[field])
 for mode in ['off','warn','block']:
  r=await req('PUT','budget-rules',{'entity_id':'A','mode':mode,'warn_threshold_pct':85,'unbudgeted_action':'allow','enforce_po_create':True,'enforce_po_approve':True});rec('budget.mode_'+mode,200,r.status_code)
  for amount in [10,110,120,121]:
   chk=(await req('POST','budget-check',{'entity_id':'A','dimension':'account','key':'1-1300','date':'2026-01-20','amount':amount})).json()
   rec('budget.check_available_'+str((mode,amount)),120-amount,chk['available_after']);rec('budget.check_block_'+str((mode,amount)),mode=='block' and amount>120,chk['blocked'])
 for mode in ['off','warn','block']:
  for action in ['allow','warn','block']:
   await b.set_rules('A',{'mode':mode,'unbudgeted_action':action},{'name':'Audit'})
   chk=await b.check_budget('A','account','1-1100',10,'2026-01-20');rec('budget.unbudgeted_'+str((mode,action)),mode!='off' and action=='block',chk['blocked'])
 await b.set_rules('A',{'mode':'warn','warn_threshold_pct':0},{'name':'Audit'})
 chk=await b.check_budget('A','account','1-1300',0,'2026-01-20');rec('budget.zero_threshold_check_warning',True,bool(chk['warning']))
 report=await b.budget_vs_actual({'entity_id':'A'},2026,'A');row=next(x for x in report['rows'] if x['id']==first['id']);rec('budget.zero_threshold_report_warning','warning',row['status'])
 for key,patch in [('mode',{'mode':'bad'}),('action',{'unbudgeted_action':'bad'}),('threshold_low',{'warn_threshold_pct':-1}),('threshold_high',{'warn_threshold_pct':101})]:await reject('budget.rule_guard_'+key,b.set_rules('A',patch,{}))
 await b.set_rules('A',{'mode':'block','warn_threshold_pct':85,'enforce_po_create':True,'enforce_po_approve':True},{'name':'Audit'})
 await reject('budget.po_enforcement_over',b.enforce_po_budget({'entity_id':'A','net_subtotal':121,'expected_delivery_date':'2026-01-20'},'po_create',{}))
 good=await b.enforce_po_budget({'entity_id':'A','net_subtotal':10,'expected_delivery_date':'2026-01-20'},'po_approve',{});rec('budget.po_enforcement_under',False,good['blocked'])
 await b.set_rules('A',{'enforce_po_create':False},{});rec('budget.disabled_stage_skips',True,(await b.enforce_po_budget({'entity_id':'A','net_subtotal':9999},'po_create',{}))['skipped'])
 r=await req('PATCH','budgets/'+second['id'],{'month':1});rec('budget.patch_duplicate_rejected',True,r.status_code in (400,409),str(r.status_code))
 same=list(await e.db.budgets.find({'entity_id':'A','year':2026,'month':1,'dimension':'account','key':'1-1300'},{'_id':0}).to_list(None));rec('budget.single_envelope_per_key',1,len(same))
 r=await req('PATCH','budgets/'+second['id'],{'year':1900});rec('budget.patch_invalid_year_rejected',True,r.status_code in (400,422),str(r.status_code))
 rec('budget.delete',200,(await req('DELETE','budgets/'+second['id'])).status_code);rec('budget.delete_again',404,(await req('DELETE','budgets/'+second['id'])).status_code)
async def postings():
 pairs=[('post_goods_receipt','task_id','1-1300','2-1150',{}),('post_subcon_issue','mko_id','1-1350','1-1300',{'step_seq':1}),('post_subcon_receipt','mko_id','1-1300','1-1350',{'step_seq':1}),('post_subcon_service_unabsorbed','mko_id','5-1200','1-1350',{}),('post_inventory_writeoff','roll_id','5-9500','1-1300',{'reason':'Audit scrap'}),('post_sample_material_issue','movement_id','6-7000','1-1300',{'note':'Sample consumption'}),('post_penalty_issue','penalty_id','1-1270','4-9300',{}),('post_penalty_reversal','penalty_id','4-9300','1-1270',{}),('post_variance_writeoff','decision_id','6-9100','1-1200',{}),('post_ap_variance_writeoff','decision_id','2-1100','4-9000',{}),('post_variance_reallocation','decision_id','2-1400','1-1200',{}),('post_bank_holding_allocation','source_id','2-1950','1-1200',{}),('post_store_credit_redemption','redemption_id','2-1450','1-1200',{})]
 for name,key,debit,credit,extra in pairs:
  fn=getattr(gl,name);kw={key:'AUD-'+name,'entity_id':'A','amount':100,'date':'2026-10-01T00:00:00Z',**extra}
  if 'date' not in inspect.signature(fn).parameters:kw.pop('date')
  entry=await fn(**kw);assert entry,name
  rec(name+'.debit',{debit:100.0},{x['account_code']:x['debit'] for x in entry['lines'] if x['debit']});rec(name+'.credit',{credit:100.0},{x['account_code']:x['credit'] for x in entry['lines'] if x['credit']})
  rec(name+'.balanced',100,entry['total_credit']);rec(name+'.retry_no_duplicate',None,await fn(**kw))
  for amount in [0,-1]:rec(name+'.invalid_amount_'+str(amount),None,await fn(**{**kw,key:'INVALID-'+name+str(amount),'amount':amount}))
  rec(name+'.empty_source',None,await fn(**{**kw,key:''}))
 for name,key,signed,debit,credit in [('post_cycle_count_variance','source_id',100,'1-1300','4-9000'),('post_cycle_count_variance','source_id',-100,'5-9500','1-1300'),('post_store_credit_adjust','adjust_id',100,'5-9500','2-1450'),('post_store_credit_adjust','adjust_id',-100,'2-1450','4-9000')]:
  fn=getattr(gl,name);kw={key:name+str(signed),'entity_id':'A','amount_signed':signed};entry=await fn(**kw)
  rec(name+str(signed)+'.debit',{debit:100},{x['account_code']:x['debit'] for x in entry['lines'] if x['debit']});rec(name+str(signed)+'.credit',{credit:100},{x['account_code']:x['credit'] for x in entry['lines'] if x['credit']});rec(name+str(signed)+'.retry',None,await fn(**kw));rec(name+str(signed)+'.zero',None,await fn(**{**kw,key:'ZERO-'+name,'amount_signed':0}))
 for settlement,credit in [('cash','1-1100'),('store_credit','2-1450'),('ar','1-1200'),('nego','1-1200')]:
  kw={'ret':{'id':'RET-'+settlement,'entity_id':'A','number':'RET'},'return_net':100,'return_ppn':12,'return_cogs':50,'settlement':settlement};entry=await gl.post_sales_return(**kw)
  rec('return.'+settlement+'.gross_credit',112,sum(x['credit'] for x in entry['lines'] if x['account_code']==credit));rec('return.'+settlement+'.recovered_stock',50,sum(x['debit'] for x in entry['lines'] if x['account_code']=='1-1300'));rec('return.'+settlement+'.conservation',162,entry['total_credit']);rec('return.'+settlement+'.retry',None,await gl.post_sales_return(**kw))
 for delta in [-1,0,1]:
  kw={'bill_id':'SERVICE'+str(delta),'mko_id':'MKO','step_seq':1,'entity_id':'A','net_amount':100,'ppn':12,'grand_total':112+delta};entry=await gl.post_subcon_service(**kw);rec('subcon.service'+str(delta)+'.balanced',112+max(delta,0),entry['total_debit']);rec('subcon.service'+str(delta)+'.debit_equals_credit',entry['total_debit'],entry['total_credit']);rec('subcon.service'+str(delta)+'.retry',None,await gl.post_subcon_service(**kw))
async def return_policy():
 await e.db.sales_return_policies.delete_many({})
 policy={'id':'POL-A','entity_id':'A','scope':'global','name':'A return policy','window_days':30,'allowed_return_types':['retur'],'allowed_outcomes':['refund'],'enforce_window':True,'link_to_supplier_window':True,'created_at':'2026-01-01T00:00:00Z'}
 await e.db.sales_return_policies.insert_one(policy)
 await e.db.suppliers.insert_many([{'id':'SA','name':'Supplier A','return_policy':{'window_days':30}},{'id':'SB','name':'Supplier B','return_policy':{'window_days':1}}])
 await e.db.purchase_orders.insert_one({'id':'OWN-PO','entity_id':'A','supplier_id':'SA','po_number':'OWN-PO','status':'completed','items':[{'product_id':'P'}],'created_at':'2026-01-01T00:00:00Z','last_received_at':'2026-01-01T00:00:00Z'})
 await e.db.products.insert_one({'id':'P','name':'Audit return cloth','sku':'AUD-POL','base_unit':'yard','status':'active'})
 await e.db.inventory_rolls.insert_one({'id':'POL-R-A','product_id':'P','owner_entity_id':'A','source_po_id':'OWN-PO','po_id':'OWN-PO','supplier_id':'SA','status':'reserved','reserved_order_id':'SO-POL-A','length':10,'length_remaining':10,'unit':'yard'})
 order={'id':'SO-POL-A','number':'SO-A','entity_id':'A','customer_id':'CA','dispatched_at':'2026-01-01T00:00:00Z','items':[{'product_id':'P','reserved_rolls':['POL-R-A'],'quantity':10}]}
 own=await rp.check_sales_return_eligibility(order,'retur','2026-01-02T00:00:00Z');rec('return_policy.own_source',True,own['eligible']);rec('return_policy.own_supplier','SA',own['supplier_linked']['supplier_id'])
 await e.db.purchase_orders.insert_one({'id':'FOREIGN-PO','entity_id':'B','supplier_id':'SB','po_number':'FOREIGN-PO','status':'completed','items':[{'product_id':'P'}],'created_at':'2026-01-01T12:00:00Z','last_received_at':'2025-12-01T00:00:00Z'})
 foreign=await rp.check_sales_return_eligibility(order,'retur','2026-01-02T00:00:00Z');rec('return_policy.foreign_unrelated_po_not_selected','SA',foreign['supplier_linked']['supplier_id']);rec('return_policy.eligibility_not_changed_by_foreign_po',True,foreign['eligible']);rec('return_policy.deadline_not_changed_by_foreign_po',own['deadline'],foreign['deadline'])
 for value in ['',None,'bad','2026-01-01','2026-01-01T00:00:00Z']:rec('return_policy.date_parse_'+str(value),bool(value and value!='bad'),rp.parse_dt(value) is not None)
 rec('return_policy.origin_po_override','local',rp.resolve_effective_origin({'origin_type':'import'},{'import_flag':False}));rec('return_policy.origin_supplier','import',rp.resolve_effective_origin({'origin_type':'import'}));rec('return_policy.origin_invalid_default','local',rp.resolve_effective_origin({'origin_type':'bad'}))
async def main():
 try:
  await e.seed();await gl.seed_default_coa()
  await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.budget':['view','create','update','delete','configure']}})
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
   for label,fn in [('budget',lambda:budgets(h)),('postings',postings),('return_policy',return_policy)]:
    try:await fn()
    except Exception:ERRORS.append(label+'\n'+traceback.format_exc())
 finally:
  out=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,harness_errors=ERRORS,scope=__doc__)
  Path(__file__).with_name('budget-ledger-policy90-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(observations=len(RESULTS),differences=[x['id'] for x in RESULTS if x['status']!='pass'],errors=ERRORS)));e.client.close()
if __name__=='__main__':asyncio.run(main())
