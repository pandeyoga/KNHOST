"""Actual-roll backfill and return provenance with explicit multi-unit/owner fixtures."""
import asyncio,json,traceback,copy
from pathlib import Path
import service_env90 as e
from services import dual_qty_service as dual,return_chain_service as chain
RESULTS=[];ERRORS=[];CONTEXT={}
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def backfill():
 await e.db.inventory_rolls.insert_many([
  {'id':'R1','product_id':'P1','length_initial':100,'length_remaining':100,'grn_task_id':'T1','po_id':'PO1','weight_kg':12.3456,'secondary_measures':{},'return_id':'SR1','owner_entity_id':'A','status':'quarantine','unit':'yard','lot':'LOT-R1','supplier_name':'Supplier A','roll_no':'R1'},
  {'id':'R2','product_id':'P1','length_initial':50,'length_remaining':50,'grn_task_id':'T1','po_id':'PO1','return_id':'SR1','owner_entity_id':'B','status':'available','unit':'yard','lot':'LOT-R2','supplier_name':'Supplier B','roll_no':'R2'},
  {'id':'R3','product_id':'P2','length_initial':0,'length_remaining':0,'owner_entity_id':'A','status':'consumed','unit':'kg'}])
 await e.db.inventory_movements.insert_many([{'id':'M1','roll_id':'R1'},{'id':'M2','roll_id':''},{'id':'M3','roll_id':'R2','qty_rolls':1}])
 await e.db.wms_tasks.insert_many([{'id':'T1','qty_rolls':None},{'id':'T2'},{'id':'T3','qty_rolls':4}])
 await e.db.purchase_orders.insert_many([
  {'id':'PO1','items':[{'product_id':'P1','quantity':200},{'product_id':'P2','quantity':1}]},
  {'id':'PO2','items':[{'product_id':'P1','quantity':100,'qty_rolls':7,'received_rolls':9}]}])
 for coll in ['sales_returns','purchase_returns','interco_returns','warehouse_transfers']:
  field='rolls' if coll=='warehouse_transfers' else 'roll_ids'
  await e.db[coll].insert_one({'id':'BF-'+coll,'items':[{'product_id':'P1',field:['R1','R2',None]},{'product_id':'P2',field:[]},{'qty_rolls':3,field:['R1']}]})
 await e.db.shipments.insert_many([{'id':'SH1','rolls':['R1','R2',None]},{'id':'SH2','product_id':'P1','qty':200},{'id':'SH3','qty_rolls':4,'rolls':['R1']}])
 await e.db.makloon_orders.insert_one({'id':'MK1','steps':[{'input_product_id':'P1','input_qty':200,'lots':['R1','R2',None]},{'input_product_id':'P2','input_qty':0,'lots':[]}]})
 for coll in ['sales_orders','purchase_requisitions','rfqs','interco_transactions','internal_requests']:
  await e.db[coll].insert_one({'id':'PLAN-'+coll,'items':[{'product_id':'P1','quantity':200},{'product_id':'P2','quantity':1},{'quantity':1},{'product_id':'P1','quantity':0},{'product_id':'P1','quantity':10,'qty_rolls':8}]})
 dry=await dual.backfill(e.db,dry_run=True)
 rec('backfill.dry_run_has_no_write',False,'qty_rolls' in (await e.db.inventory_movements.find_one({'id':'M1'})))
 actual=await dual.backfill(e.db)
 rec('backfill.dry_run_matches_write_counts',dry,actual)
 rec('backfill.movement_is_single_roll',1,(await e.db.inventory_movements.find_one({'id':'M1'}))['qty_rolls'])
 rec('backfill.task_real_count',2,(await e.db.wms_tasks.find_one({'id':'T1'}))['qty_rolls'])
 po=await e.db.purchase_orders.find_one({'id':'PO1'})
 rec('backfill.received_real_count',2,po['items'][0]['received_rolls'])
 rec('backfill.production_plan_not_guessed',False,'qty_rolls' in po['items'][0])
 rec('backfill.actual_weight',12.346,(await e.db.inventory_rolls.find_one({'id':'R1'}))['secondary_measures']['kg'])
 rec('backfill.preserve_existing_count',7,(await e.db.purchase_orders.find_one({'id':'PO2'}))['items'][0]['qty_rolls'])
 rec('backfill.no_rolls_no_task_guess',False,'qty_rolls' in (await e.db.wms_tasks.find_one({'id':'T2'})))
 rec('backfill.shipment_actual_rolls',2,(await e.db.shipments.find_one({'id':'SH1'}))['qty_rolls'])
 rec('backfill.shipment_without_source_unknown',False,'qty_rolls' in (await e.db.shipments.find_one({'id':'SH2'})))
 rec('backfill.makloon_actual_output_rolls',2,(await e.db.makloon_orders.find_one({'id':'MK1'}))['steps'][0]['qty_rolls_out'])
 for coll in ['sales_returns','purchase_returns','interco_returns','warehouse_transfers']:
  row=await e.db[coll].find_one({'id':'BF-'+coll});rec('backfill.normal_'+coll,2,row['items'][0]['qty_rolls'])
 rec('backfill.idempotent_no_repeat_updates',{},await dual.backfill(e.db))
 await dual.backfill(e.db,demo_plan=True,dry_run=True)
 rec('backfill.demo_dry_keeps_plan_unknown',False,'qty_rolls' in (await e.db.sales_orders.find_one({'id':'PLAN-sales_orders'}))['items'][0])
 await dual.backfill(e.db,demo_plan=True)
 rec('backfill.demo_po_estimate',3,(await e.db.purchase_orders.find_one({'id':'PO1'}))['items'][0]['qty_rolls'])
 rec('backfill.demo_shipment_estimate',3,(await e.db.shipments.find_one({'id':'SH2'}))['qty_rolls'])
 for coll in ['sales_orders','purchase_requisitions','rfqs','interco_transactions','internal_requests']:
  row=await e.db[coll].find_one({'id':'PLAN-'+coll});rec('backfill.demo_'+coll,3,row['items'][0]['qty_rolls']);rec('backfill.demo_preserves_'+coll,8,row['items'][4]['qty_rolls'])
 # Duplicate/dangling IDs deliberately validate repair quality; no producer claim.
 await e.db.sales_returns.insert_one({'id':'CORRUPT-IDS','items':[{'product_id':'P1','roll_ids':['R1','R1','MISSING']}]})
 await dual.backfill(e.db)
 rec('backfill.corrupt_ids_real_unique_rolls',1,(await e.db.sales_returns.find_one({'id':'CORRUPT-IDS'}))['items'][0]['qty_rolls'])
 rec('backfill.real_count_helper_control',1,await dual.rolls_of_ids(['R1','R1','MISSING']))
async def provenance():
 await e.db.business_entities.insert_many([{'id':v,'short_name':v,'legal_name':'Legal Entity '+v,'name':'Legal Entity '+v,'status':'active'} for v in ['A','B','C']])
 rec('chain.no_document',False,(await chain.chain('missing',['A']))['found'])
 await e.db.sales_returns.insert_one({'id':'SR1','number':'SR1','entity_id':'A','total_amount':150,'customer_name':'Private customer A','order_number':'SO1','status':'settled'})
 await e.db.interco_returns.insert_many([
  {'id':'IC1','number':'IC1','role':'returner','source_sales_return_id':'SR1','buyer_entity_id':'A','seller_entity_id':'B','return_pair_id':'PAIR1','grand_total':100,'status':'settled','origin_number':'IC-ORIGIN'},
  {'id':'IC2','number':'IC2','role':'receiver','source_sales_return_id':'SR1','buyer_entity_id':'A','seller_entity_id':'B','return_pair_id':'PAIR1','status':'received'},
  {'id':'IC-ONLY','number':'IC-ONLY','entity_id':'B','buyer_entity_id':'B','seller_entity_id':'C','status':'draft','grand_total':20}])
 await e.db.purchase_returns.insert_many([
  {'id':'PR1','number':'PR1','origin_interco_return_id':'IC2','entity_id':'B','supplier_name':'Private Supplier B','po_number':'PO-PRIVATE','total_amount':90,'status':'settled'},
  {'id':'PR-ONLY','number':'PR-ONLY','entity_id':'B','supplier_name':'Private Supplier B','total_amount':30,'status':'draft'}])
 full=await chain.chain('SR1',None,True)
 rec('chain.full_stages',['sales_return','interco_return','purchase_return','kept','kept'],[s['stage'] for s in full['steps']])
 rec('chain.full_root',150,full['sales_return']['total_amount']);rec('chain.complete_route',True,full['complete'])
 rec('chain.resolve_from_purchase','SR1',(await chain.chain('PR1',None,True))['sales_return']['id'])
 rec('chain.resolve_from_interco','SR1',(await chain.chain('IC1',None,True))['sales_return']['id'])
 own=await chain.chain('SR1',['A'])
 foreign_step=next(s for s in own['steps'] if s['stage']=='purchase_return')
 rec('chain.foreign_amount_hidden',None,foreign_step['amount']);rec('chain.foreign_supplier_hidden',False,'party' in foreign_step)
 rec('chain.foreign_po_hidden',False,'po_number' in foreign_step)
 foreign_roll=next(r for r in own['rolls'] if r['roll_id']=='R2')
 rec('chain.foreign_lot_hidden','',foreign_roll['lot']);rec('chain.foreign_technical_owner_hidden',False,'owner_entity_id' in foreign_roll)
 viewerB=await chain.chain('SR1',['B']);rec('chain.foreign_root_redacted',True,viewerB['sales_return']['redacted'])
 for docid in ['SR1','IC-ONLY','PR-ONLY']:
  try:await chain.chain(docid,['UNKNOWN']);rec('chain.forbidden_'+docid,'denied','allowed')
  except chain.ChainForbidden:rec('chain.forbidden_'+docid,'denied','denied')
 rec('chain.standalone_interco','interco_return',(await chain.chain('IC-ONLY',['B']))['root_type'])
 rec('chain.standalone_purchase','purchase_return',(await chain.chain('PR-ONLY',['B']))['root_type'])
 rec('chain.empty_names',{},await chain._entity_names([]))
 rec('chain.empty_summary','Belum ada jejak.',chain._summary([]))
 await e.db.inventory_rolls.insert_one({'id':'R-KG','return_id':'SR1','owner_entity_id':'A','status':'quarantine','length_remaining':5,'unit':'kg','product_id':'P-KG'})
 mixed=await chain.chain('SR1',['A'])
 notes=[s['note'] for s in mixed['steps'] if s['stage']=='kept' and s.get('entity_id')=='A']
 rec('chain.mixed_dimensions_kept_separate',2,len(notes),'A owns 100 yard of cloth and 5 kg of another item; there is no dimensional conversion between these quantities.')
 rec('chain.no_105_yard_label',False,any('105 yard' in s for s in notes))
 CONTEXT['mixed_owner_notes']=notes
async def main():
 try:
  await e.setup()
  for name,fn in [('backfill',backfill),('provenance',provenance)]:
   try:await fn()
   except Exception:ERRORS.append({'suite':name,'error':traceback.format_exc()})
 except Exception:ERRORS.append({'suite':'setup','error':traceback.format_exc()})
 finally:
  d=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,context=CONTEXT,harness_errors=ERRORS,scope='Original service functions; explicit synthetic physical-roll and linked-document fixtures. No public-producer or browser claim.')
  Path(__file__).with_name('quantity-provenance90-results.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'observations':len(RESULTS),'differences':[r['id'] for r in RESULTS if r['status']!='pass'],'errors':ERRORS}));e.client.close()
if __name__=='__main__':asyncio.run(main())
