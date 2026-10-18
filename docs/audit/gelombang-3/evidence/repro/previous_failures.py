"""Independent review probes: original services/Mongo with scoped fault scheduling."""
import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'wave-2/repro'))
import wave2_env as e
from motor.motor_asyncio import AsyncIOMotorCollection as Collection
from services import production_service as prod,roll_service as rolls,material_reservation_service as mres,ar_receipt_service as ar
db=e.db;results=[]
def record(id,actual):results.append(dict(id=id,actual=actual));print(json.dumps(results[-1]),flush=True)
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 from services import gl_service as gl
 await gl.seed_default_coa()
 for p in ['MAT','OUT','ARPROD']:await db.products.insert_one(dict(id=p,sku=p,name=p,base_unit='meter',harga_pokok=10,price=10,stage='grey' if p=='MAT' else 'finished',status='active',fabric_type='woven',line_code='woven'))
 await db.warehouses.insert_one(dict(id='WH',name='Synthetic warehouse',status='active',sharing_mode='shared'))
 # First-write failure after physical consumption but before movement journal.
 r=await rolls.create_inbound_roll('MAT','WH','A',20,unit_cost=10)
 await db.mfg_work_orders.insert_one(dict(id='WOFAIL',entity_id='A',warehouse_id='WH',status='released',planned_qty=5,output_product_id='OUT',overhead_per_unit=0,bom_components=[dict(material_product_id='MAT',qty_per_unit=1,unit='meter')]))
 old=Collection.insert_one;err='no error'
 async def fault(self,doc,*args,**kw):
  if self.name=='inventory_movements' and doc.get('movement_type')=='production_consume' and doc.get('source_document')=='WOFAIL':raise RuntimeError('Synthetic movement insert fault BEFORE write')
  return await old(self,doc,*args,**kw)
 Collection.insert_one=fault
 try:
  try:await prod.complete_work_order('WOFAIL')
  except Exception as ex:err=type(ex).__name__
 finally:Collection.insert_one=old
 wo=await db.mfg_work_orders.find_one({'id':'WOFAIL'});after=(await db.inventory_rolls.find_one({'id':r['id']}))['length_remaining']
 await db.mfg_work_orders.update_one({'id':'WOFAIL'},{'$unset':{'saga_lock':''}}) # controlled local recovery equivalent, NOT authorization test
 final=await prod.complete_work_order('WOFAIL')
 movements=await db.inventory_movements.find({'source_document':'WOFAIL','movement_type':'production_consume'}).to_list(50)
 record('V3-PROD-01',dict(error=err,before_qty=20,after_fault_qty=after,after_retry_qty=(await db.inventory_rolls.find_one({'id':r['id']}))['length_remaining'],output=final['produced_qty'],reported_consumed=final['consumed'][0]['qty'],movement_qty=sum(-x['quantity'] for x in movements)))
 # Reversal marks contribution complete BEFORE physical restore; failure loses retry.
 await db.inventory_rolls.insert_one(dict(id='REVROLL',product_id='MAT',warehouse_id='WH',owner_entity_id='A',status='available',length_initial=10,length_remaining=5,length_reserved=0,unit='meter',unit_cost=10))
 await db.inventory_movements.insert_one(dict(id='REVMOV',operation_id='REVOP',movement_type='production_consume',quantity=-5,roll_id='REVROLL',product_id='MAT',warehouse_id='WH',owner_entity_id='A',unit='meter',source_document='REVWO'))
 old_update=Collection.update_one
 async def update_fault(self,q,*args,**kw):
  if self.name=='inventory_rolls' and q.get('id')=='REVROLL':raise RuntimeError('Synthetic restore fault BEFORE write')
  return await old_update(self,q,*args,**kw)
 Collection.update_one=update_fault
 try:
  try:await prod.reverse_operation('REVOP')
  except Exception:pass
 finally:Collection.update_one=old_update
 restored=await prod.reverse_operation('REVOP')
 record('V3-PROD-02',dict(retry_restored=restored,remaining=(await db.inventory_rolls.find_one({'id':'REVROLL'}))['length_remaining'],movement_reversed=(await db.inventory_movements.find_one({'id':'REVMOV'}))['reversed']))
 # Concurrent real PR reservation calls; real recipe/prefill, barrier only scheduling free-stock reads.
 await db.inventory_balances.update_one({'product_id':'MAT','warehouse_id':'WH','owner_entity_id':'A'},{'$set':{'available_qty':1000}},upsert=True)
 await db.process_recipes.insert_one(dict(id='REC',output_product_id='OUT',input_product_id='MAT',entity_id='A',status='active',yield_factor=1,waste_pct=0,name='Synthetic ratio 1',process_type='dyeing'))
 for pr in ['PR1','PR2']:await db.purchase_requisitions.insert_one(dict(id=pr,number=pr,status='approved',entity_id='A',warehouse_id='WH',items=[dict(line_no=1,product_id='OUT',quantity=700,unit='meter',fulfillment_mode='makloon',realized_qty=0)]))
 original_free=mres.free_for_commitment;count=0;barrier=asyncio.Event()
 async def delayed(*a,**kw):
  nonlocal count
  qty=await original_free(*a,**kw);count+=1
  if count>=2:barrier.set()
  await barrier.wait();return qty
 mres.free_for_commitment=delayed
 try:await asyncio.wait_for(asyncio.gather(mres.reserve_for_pr('PR1'),mres.reserve_for_pr('PR2')),30)
 finally:mres.free_for_commitment=original_free
 docs=await db.material_reservations.find({'product_id':'MAT','status':'active'}).to_list(10)
 record('V3-MRES-01',dict(on_hand_available=1000,reserved=sum(x['qty'] for x in docs),shortage=sum(x['shortage_qty'] for x in docs),pr_count=len(docs)))
 # Receipt insert fails after original allocation; compensator refunds deposit but does not undo payment.
 await db.customers.insert_one(dict(id='C',name='Synthetic customer',entity_id='A',deposit_balance=100,status='active'))
 await db.sales_orders.insert_one(dict(id='SOAR',number='SOAR',customer_id='C',entity_id='A',grand_total=100,subtotal=100,paid_total=0,payments=[],payment_status='unpaid',payment_profile_method='tempo',status='shipped',items=[],created_at='2026-09-01T00:00:00+00:00'))
 from services import gl_service as gl
 await gl.post_order_revenue_and_cogs('SOAR')
 old_insert=Collection.insert_one
 async def receipt_fault(self,*a,**kw):
  if self.name=='ar_receipts':raise RuntimeError('Synthetic receipt insert fault BEFORE write')
  return await old_insert(self,*a,**kw)
 Collection.insert_one=receipt_fault
 try:
  try:await ar.create_receipt(dict(customer_id='C',amount=0,use_deposit_amount=100,allocations=[dict(order_id='SOAR',amount=100)],method='transfer',entity_id='A'),dict(id='U',name='Synthetic actor'))
  except Exception as ex:err=repr(ex)
 finally:Collection.insert_one=old_insert
 so=await db.sales_orders.find_one({'id':'SOAR'});customer=await db.customers.find_one({'id':'C'})
 record('V3-AR-01',dict(error=err,paid_total=so['paid_total'],payments=len(so['payments']),deposit=customer['deposit_balance'],receipts=await db.ar_receipts.count_documents({'customer_id':'C'})))
 # Two concurrent public service calls, one statement line, two distinct valid transactions.
 from services import bank_recon_service as br
 await db.bank_accounts.insert_one(dict(id='B1',entity_id='A',cash_type='kas_besar',name='Synthetic bank'))
 for tid in ['BT1','BT2']:
  await db.cash_transactions.insert_one(dict(id=tid,account_id='B1',entity_id='A',direction='in',amount=100,status='posted',cash_type='kas_besar',number=tid))
 await db.bank_statement_lines.insert_one(dict(id='BL',bank_account_id='B1',entity_id='A',direction='in',amount=100,status='unmatched',stmt_date='2026-09-01'))
 old_link=br._link;arrived=0;ready=asyncio.Event()
 async def delayed_link(*args,**kwargs):
  nonlocal arrived
  arrived+=1
  if arrived==2:ready.set()
  await ready.wait()
  return await old_link(*args,**kwargs)
 br._link=delayed_link
 try:await asyncio.wait_for(asyncio.gather(br.manual_match('BL','BT1','U',['A']),br.manual_match('BL','BT2','U',['A'])),30)
 finally:br._link=old_link
 line=await db.bank_statement_lines.find_one({'id':'BL'})
 cash=await db.cash_transactions.find({'id':{'$in':['BT1','BT2']}}).to_list(10)
 record('V3-BANK-01',dict(statement_amount=line['amount'],statement_allocated=sum(a['amount'] for a in line['allocations']),cash_reconciled=sum(c['reconciled_amount'] for c in cash),linked_cash_count=sum('BL' in c.get('matched_line_ids',[]) for c in cash)))
 # Catch-weight updates use stale parent snapshots although length decrements are atomic.
 weighted=await rolls.create_inbound_roll('MAT','WH','A',10,unit_cost=10)
 await db.inventory_rolls.update_one({'id':weighted['id']},{'$set':{'weight_kg':3,'secondary_measures':{'kg':3}}})
 parent=await db.inventory_rolls.find_one({'id':weighted['id']},{'_id':0})
 children=await asyncio.gather(rolls._split_roll(dict(parent),2,'SPLIT1'),rolls._split_roll(dict(parent),2,'SPLIT2'))
 remaining=await db.inventory_rolls.find_one({'id':parent['id']})
 record('V3-WEIGHT-01',dict(initial_length=10,remaining_length=remaining['length_remaining'],initial_weight=3,parent_weight=remaining['weight_kg'],child_weights=[c['weight_kg'] for c in children],total_weight=remaining['weight_kg']+sum(c['weight_kg'] for c in children)))
 from services import po_variance_task_service as pvt
 await db.purchase_orders.insert_one(dict(id='POV',po_number='POV',entity_id='A',status='receiving',items=[dict(line_id='L1',product_id='MAT',quantity=100,received_qty=90,unit='meter',unit_price=10),dict(line_id='L2',product_id='MAT',quantity=200,received_qty=100,unit='meter',unit_price=20)]))
 await pvt.ensure_for_po('POV')
 tasks=await db.po_variance_tasks.find({'po_id':'POV','status':'open'}).to_list(10)
 await db.purchase_orders.update_one({'id':'POV'},{'$set':{'items.0.received_qty':95}})
 await pvt.ensure_for_po('POV')
 task=await db.po_variance_tasks.find_one({'po_id':'POV','status':'open'})
 record('V3-PO-01',dict(actual_shortages=[5,100],task_count=len(tasks),task_received=task['received_qty'],task_short=task['short_qty'],live_first_received=95))
 from services import makloon_order_service as m
 for pid in ['MIN','MOUT']:await db.products.insert_one(dict(id=pid,sku=pid,name=pid,base_unit='meter',harga_pokok=10,price=10,grade='A'))
 await rolls.create_inbound_roll('MIN','WH','A',10,unit_cost=10,lot='MRAW',acquired_via='purchase',ref_id='MFAIL')
 await db.makloon_orders.insert_one(dict(id='MFAIL',mko_number='MFAIL',entity_id='A',status='draft',from_warehouse_id='WH',target_warehouse_id='WH',timeline=[],steps=[dict(seq=1,status='pending',material_flow='moves',process_type='dyeing',input_product_id='MIN',output_product_id='MOUT',input_qty=10,input_unit='meter',output_unit='meter',expected_output_qty=10,issue_ref='MFAIL:1',makloon_id='PARTNER',tariff_basis='lumpsum',tariff_rate=20,tolerance_pct=10)]))
 await m.issue_step('MFAIL',1,actor_name='Synthetic')
 payload=dict(actual_output_qty=10,tariff=20,output_warehouse_id='WH',rolls=[dict(lot='MO1',length=5),dict(lot='MO2',length=5)])
 old_create=m.create_inbound_roll;num=0
 async def fail_second(*args,**kwargs):
  nonlocal num
  num+=1
  if num==2:raise RuntimeError('Synthetic second output failure BEFORE write')
  return await old_create(*args,**kwargs)
 m.create_inbound_roll=fail_second
 try:
  try:await m.receive_step('MFAIL',1,payload,actor_name='Synthetic')
  except Exception as ex:err=repr(ex)
 finally:m.create_inbound_roll=old_create
 before=await db.inventory_rolls.count_documents({'product_id':'MOUT'})
 await db.makloon_orders.update_one({'id':'MFAIL'},{'$unset':{'saga_lock':''}})
 await m.receive_step('MFAIL',1,payload,actor_name='Synthetic')
 output_rolls=await db.inventory_rolls.find({'product_id':'MOUT'}).to_list(10)
 je=await db.journal_entries.find_one({'source_type':'subcon_receipt','source_id':'MFAIL:1'})
 record('V3-MKO-01',dict(error=err,rolls_after_fault=before,rolls_after_retry=len(output_rolls),expected_output=10,actual_output=sum(r['length_remaining'] for r in output_rolls),roll_value=sum(r['length_remaining']*r['unit_cost'] for r in output_rolls),journal_value=je['total_debit']))
 from services import rfid_service as rf,rfid_ingest_service as ing,gate_evaluator as ge
 from datetime import datetime,timedelta,timezone
 await db.sales_orders.insert_one(dict(id='GSO',number='GSO',entity_id='A',status='confirmed'))
 gate_roll=await rolls.create_inbound_roll('MAT','WH','A',10,unit_cost=10)
 await db.inventory_rolls.update_one({'id':gate_roll['id']},{'$set':{'status':'in_transit_sales','reserved_ref':{'type':'sales_order','id':'GSO'}}})
 await db.shipments.insert_one(dict(id='GSHIP',order_id='GSO',warehouse_id='WH',status='dispatched',rolls=[{'roll_id':gate_roll['id']}]))
 tag=await rf.encode_tag(gate_roll['id'],['A'])
 gate=dict(id='GATE',type='gate',direction='out',warehouse_id='WH',name='Synthetic gate')
 first=await ing.ingest(gate,events=[dict(epc=tag['epc'],event_id='GE1')])
 await db.sales_orders.update_one({'id':'GSO'},{'$set':{'status':'cancelled'}})
 clock=ing.now_iso;later=(datetime.now(timezone.utc)+timedelta(seconds=20)).isoformat();ing.now_iso=lambda:later
 try:second=await ing.ingest(gate,events=[dict(epc=tag['epc'],event_id='GE2')])
 finally:ing.now_iso=clock
 fresh_roll=await db.inventory_rolls.find_one({'id':gate_roll['id']},{'_id':0})
 actual=await ge.evaluate('out','WH',fresh_roll)
 record('V3-RFID-01',dict(first=first['results'][0]['result'],fresh_event_after_seconds=20,second=second['results'][0]['result'],duplicate=second['results'][0].get('duplicate'),current_evaluator_result=actual['result'],current_evaluator_code=actual['code'],different_passage=first['passage']['id']!=second['passage']['id']))
 from services import cash_flow_service as cf
 await db.business_entities.insert_one(dict(id='CF',short_name='CF',legal_name='Synthetic Cashflow',status='active'))
 await gl._insert_entry(lines=[dict(account_code='1-2100',debit=100,credit=0),dict(account_code='1-1100',debit=0,credit=40),dict(account_code='2-1100',debit=0,credit=60)],description='Synthetic asset: 40 cash plus 60 payable',date='2026-09-01T12:00:00+00:00',source_type='manual',source_id='CF-MIX',entity_id='CF',created_by='Synthetic')
 report=await cf.cash_flow_statement('2026-09-01','2026-09-30',{'entity_id':'CF'})
 record('V3-CF-01',dict(expected_investing=-40,expected_operating=0,expected_noncash_asset=60,actual_investing=report['investing']['total'],actual_operating=report['operating']['total'],net_change=report['net_change'],noncash=report['noncash_disclosure']['lines']))
 await gl._insert_entry(lines=[dict(account_code='6-4000',debit=10,credit=0),dict(account_code='1-1100',debit=0,credit=10)],description='Synthetic date-only first day',date='2026-09-01',source_type='manual',source_id='CF-DATE',entity_id='CF',created_by='Synthetic')
 from services import financial_statement_service as fs
 pnl=await fs.income_statement('2026-09-01','2026-09-30',{'entity_id':'CF'})
 record('V3-DATE-01',dict(expected_opex=10,actual_opex=pnl['opex_total'],stored_date='2026-09-01',filter_start=fs._day_start('2026-09-01')))
 from services import loading_check_service as lc
 await db.warehouses.insert_one(dict(id='WH2',name='Synthetic second warehouse',status='active',sharing_mode='shared',loading_check_policy='required'))
 await db.warehouses.update_one({'id':'WH'},{'$set':{'loading_check_policy':'required'}})
 await db.sales_orders.insert_one(dict(id='SOMULTI',number='SOMULTI',entity_id='A',status='confirmed'))
 ready_roll=await rolls.create_inbound_roll('MAT','WH','A',10,unit_cost=10)
 await db.inventory_rolls.update_one({'id':ready_roll['id']},{'$set':{'status':'committed','reserved_ref':{'type':'sales_order','id':'SOMULTI'}}})
 await rf.encode_tag(ready_roll['id'],['A'])
 other_roll=await rolls.create_inbound_roll('OUT','WH2','A',20,unit_cost=10)
 await rolls._reserve_length(other_roll,5,'SOMULTI')
 local_error=None
 await rolls.assert_cut_identity_ready('SOMULTI','MAT','WH')
 try:await lc.start('SOMULTI',['A'],'Synthetic')
 except Exception as ex:local_error=str(ex)
 record('V3-WMS-02',dict(local_ready_tagged_rolls=1,local_cut_guard='passed',pending_cuts_other_warehouse=1,loading_check_start_error=local_error))
 from services import master_governance_service as gov
 await db.products.insert_one(dict(id='GOV',sku='GOV',name='Synthetic legacy',stage='greige',fabric_type='woven',line_code='woven'))
 preview=await gov.preview({'id':'GOV'})
 old_insert=Collection.insert_one
 async def batch_failure(self,*a,**kw):
  if self.name=='master_governance_batches':raise RuntimeError('Synthetic batch journal failure BEFORE write')
  return await old_insert(self,*a,**kw)
 Collection.insert_one=batch_failure
 try:
  try:await gov.apply_batch({'id':'GOV'},preview['preview_signature'],preview['proposals'],'Synthetic migration',dict(name='Synthetic'))
  except Exception as ex:err=repr(ex)
 finally:Collection.insert_one=old_insert
 changed=await db.products.find_one({'id':'GOV'})
 record('V3-MASTER-01',dict(error=err,original_stage='greige',current_stage=changed['stage'],batch_reference=changed.get('last_governance_batch'),durable_batch_count=await db.master_governance_batches.count_documents({})))
 from services import po_amendment_service as pam
 from schemas_purchasing import PurchaseOrderAmend
 po=dict(id='POLOCK',po_number='POLOCK',entity_id='A',status='receiving',items=[dict(product_id='MAT',sku='MAT',product_name='MAT',quantity=1000,received_qty=960,unit='meter',price=10,discount_percent=0)],warehouse_id='WH',supplier_id='',supplier_name='Synthetic',version=1,total_amount=10000,grand_total=10000,updated_at='2026-09-01T00:00:00')
 await db.purchase_orders.insert_one(po)
 amend_error=None
 try:await pam.amend_po('POLOCK',PurchaseOrderAmend(reason='Reconcile actual receipt 960',items=[dict(product_id='MAT',quantity=960,unit='meter',price=10)]),dict(id='U',name='Synthetic'))
 except Exception as ex:amend_error=str(ex)
 record('V3-PO-02',dict(ordered=1000,received=960,suggested_amendment=960,error=amend_error))
 # Public cut command loses physical quantity if child insert fails before write.
 cut_parent=await rolls.create_inbound_roll('MAT','WH','A',10,unit_cost=10)
 reserved=await rolls._reserve_length(cut_parent,3,'CUTSO');reservation=reserved['reservation_id']
 old_insert=Collection.insert_one
 async def cut_fault(self,doc,*a,**kw):
  if self.name=='inventory_rolls' and (doc.get('cut') or {}).get('reservation_id')==reservation:raise RuntimeError('Synthetic cut child insert fault BEFORE write')
  return await old_insert(self,doc,*a,**kw)
 Collection.insert_one=cut_fault;cut_error=None
 try:
  try:await rolls.confirm_cut(cut_parent['id'],reservation,actor='Synthetic')
  except Exception as ex:cut_error=str(ex)
 finally:Collection.insert_one=old_insert
 current=await db.inventory_rolls.find_one({'id':cut_parent['id']});retry_error=None
 try:await rolls.confirm_cut(cut_parent['id'],reservation,actor='Synthetic retry')
 except Exception as ex:retry_error=str(ex)
 record('V3-CUT-01',dict(before_length=10,after_length=current['length_remaining'],length_reserved=current['length_reserved'],child_count=await db.inventory_rolls.count_documents({'cut.reservation_id':reservation}),error=cut_error,retry_error=retry_error))
 # Reservation totals used by the sales guard still stop at 2000 rows.
 await db.material_reservations.insert_many([dict(id=f'CAPRES{i}',product_id='MCAP',owner_entity_id='A',status='active',qty=1,ref_id=f'R{i}') for i in range(2001)])
 actual=await mres.reserved_by_others('MCAP','A')
 record('V3-MRES-02',dict(expected_reserved=2001,actual_reserved=actual,document_count=await db.material_reservations.count_documents({'product_id':'MCAP'})))
 # Notes-only amendment closes qty-resolution tasks despite awaiting reapproval.
 await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.purchase_order':['update']}})
 high=dict(po,id='POAPP',po_number='POAPP',items=[dict(product_id='MAT',sku='MAT',product_name='MAT',quantity=1000,received_qty=960,unit='meter',price=100000000,discount_percent=0,line_total=100000000000)],total_amount=100000000000,grand_total=100000000000)
 high.pop('_id',None)
 await db.purchase_orders.insert_one(high)
 await db.po_variance_tasks.insert_one(dict(id='PVAPP',po_id='POAPP',product_id='MAT',entity_id='A',status='pending_amendment',decision='amend',received_qty=960,suggested_qty=960))
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as http:
  response=await http.post('/api/purchase-orders/POAPP/amend',json=dict(reason='Synthetic notes amendment only',notes='Notes updated, quantity unchanged'))
  data=response.json()
 task=await db.po_variance_tasks.find_one({'id':'PVAPP'})
 record('V3-PO-03',dict(http_status=response.status_code,po_status=data.get('status'),po_quantity=(data.get('items') or [{}])[0].get('quantity'),task_status=task['status'],detail=data.get('detail')))
if __name__=='__main__':
 try:asyncio.run(main())
 finally:Path(__file__).with_name('new-failure-probes.json').write_text(json.dumps(dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.DBNAME,mode='Original services/indexed synthetic Mongo; scoped BEFORE-write faults and scheduling barrier. Lock removal in production probe is controlled recovery, not admin authorization validation.',results=results),indent=2),encoding='utf-8');e.client.close()
