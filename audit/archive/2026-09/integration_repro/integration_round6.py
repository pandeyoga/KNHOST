"""Real Mongo production failure/retry and QC hold consumption characterization."""
import asyncio,json
import integration_round4 as e
from services import production_service as p,roll_service as rolls,qc_inspection_service as qc,receiving_roll_service as recv,uom_service as uom,location_service as locations
db=e.db
async def setup(tag,overhead=2):
 mat='MAT'+tag;out='OUT'+tag;wh='WH'+tag
 await db.products.insert_many([{'id':x,'sku':x,'name':x,'base_unit':'meter','grade':'A','harga_pokok':10} for x in (mat,out)])
 await db.warehouses.insert_one({'id':wh,'name':wh,'status':'active'})
 roll=await rolls.create_inbound_roll(mat,wh,'A',100,unit_cost=10,ref_id='OPEN'+tag)
 bom=await p.create_bom({'name':tag,'output_product_id':out,'components':[{'material_product_id':mat,'qty_per_unit':1}],'overhead_per_unit':overhead},'A','Audit')
 wo=await p.create_work_order({'bom_id':bom['id'],'warehouse_id':wh,'planned_qty':10},'A','Audit')
 await p.release_work_order(wo['id'],{'entity_id':'A'},'Audit')
 return roll,bom,wo
async def snapshot(roll,wo):
 r=await db.inventory_rolls.find_one({'id':roll['id']})
 outputs=await db.inventory_rolls.find({'acquired.ref_id':wo['id']}).to_list(100)
 doc=await db.mfg_work_orders.find_one({'id':wo['id']})
 jes=await db.journal_entries.find({'source_id':wo['id']}).to_list(100)
 return {'material_remaining':r['length_remaining'],'output_rolls':len(outputs),'output_qty':sum(x['length_remaining'] for x in outputs),'wo_status':doc['status'],'recorded_output_ids':len(doc.get('produced_roll_ids',[])),'journal_count':len(jes),'journal_debit':sum(x.get('total_debit',0) for x in jes),'material_plus_output_value':round(r['length_remaining']*r['unit_cost']+sum(x['length_remaining']*x['unit_cost'] for x in outputs),2)}
async def main():
 await e.seed()
 r,b,w=await setup('FAIL')
 today=e.datetime.now(e.timezone.utc).date().isoformat()
 await db.period_closings.insert_one({'id':'LOCK','entity_id':'A','period_type':'month','period_key':today[:7],'start_date':today,'end_date':today,'status':'closed'})
 try:await p.complete_work_order(w['id'],{'entity_id':'A'},'Audit')
 except Exception as ex:err=type(ex).__name__
 else:err='NONE'
 s=await snapshot(r,w)
 e.check('I6-P01',{'exception':err,**s},err=='ClosedPeriodError' and s['material_remaining']==90 and s['output_qty']==10 and s['wo_status']=='released' and s['journal_count']==0)
 # Administrative fixture change isolates retry after the accounting blocker is removed.
 await db.period_closings.update_one({'id':'LOCK'},{'$set':{'status':'open'}})
 await p.complete_work_order(w['id'],{'entity_id':'A'},'Audit')
 s=await snapshot(r,w)
 e.check('I6-P02',s,s['material_remaining']==80 and s['output_qty']==20 and s['recorded_output_ids']==1 and s['journal_count']==1)
 await p.complete_work_order(w['id'],{'entity_id':'A'},'Audit')
 again=await snapshot(r,w)
 e.check('I6-C01',again,again==s,'control')
 # Hold originates in the original QC service, not a hand-inserted flag.
 r,b,w=await setup('HOLD',0)
 inspected=await qc.inspect_roll(r,[],None,None,'Synthetic mismatch',{'id':'QC','name':'QC'},color_result='beda',color_action='tahan')
 assert inspected['hold']['held']
 try:await locations.putaway_roll(r['id'],'UNUSED_BIN','Audit')
 except Exception as ex:blocked=getattr(ex,'status_code',None)==400 and 'DITAHAN' in str(getattr(ex,'detail',''))
 else:blocked=False
 e.check('I6-C04',{'putaway_rejected_for_hold_before_bin_lookup':blocked},blocked,'control')
 await p.complete_work_order(w['id'],{'entity_id':'A'},'Audit')
 s=await snapshot(r,w);held=await db.inventory_rolls.find_one({'id':r['id']})
 e.check('I6-P03',{'hold_remains':held['inspection']['hold']['held'],**s},held['inspection']['hold']['held'] and s['material_remaining']==90 and s['wo_status']=='completed')
 r,b,w=await setup('BOM',0)
 original_plan=w['material_plan'][0]['required_qty']
 await p.update_bom(b['id'],{'components':[{'material_product_id':r['product_id'],'qty_per_unit':2}]},{'entity_id':'A'})
 await p.complete_work_order(w['id'],{'entity_id':'A'},'Audit')
 s=await snapshot(r,w)
 e.check('I6-P04',{'original_plan_required':original_plan,**s},original_plan==10 and s['material_remaining']==80)
 r,b,w=await setup('SHORT',0)
 await db.inventory_rolls.update_one({'id':r['id']},{'$set':{'length_remaining':5}})
 before=await snapshot(r,w)
 try:await p.complete_work_order(w['id'],{'entity_id':'A'},'Audit')
 except ValueError:denied=True
 else:denied=False
 after=await snapshot(r,w)
 e.check('I6-C02',{'insufficient_stock_rejected':denied,'unchanged':after==before},denied and after==before,'control')
 product={'id':'RECVPROD','sku':'RECVPROD','name':'Receiving test','base_unit':'meter','grade':'A'}
 await db.products.insert_one(dict(product))
 actor={'id':'U','name':'Audit'}
 task={'id':'RECV','product_id':product['id'],'warehouse_id':'WHFAIL','entity_id':'A','status':'waiting_goods','expected_qty':100,'received_qty':0,'qty_rolls_scanned':0,'unit':'meter'}
 await db.wms_tasks.insert_one(dict(task))
 made=await recv.create_counted_roll(task=task,product=product,owner_entity_id='A',actor=actor,length=10)
 await recv.undo_receiving_roll(made['roll'],made['task'])
 retired=await db.rfid_tags.find_one({'id':made['roll']['rfid_tag_id']})
 e.check('I6-C03',{'normal_undo_tag_status':retired['status']},retired['status']=='retired','control')
 # An in-flight scanner still holds its original task snapshot after a completion wins.
 await db.wms_tasks.update_one({'id':task['id']},{'$set':{'status':'completed'}})
 before_active=await db.rfid_tags.count_documents({'status':'active','product_id':product['id']})
 try:await recv.create_counted_roll(task=task,product=product,owner_entity_id='A',actor=actor,length=10)
 except e.httpx.HTTPError:raise
 except Exception as ex:status=getattr(ex,'status_code',None)
 else:status=200
 active=await db.rfid_tags.find({'status':'active','product_id':product['id']}).to_list(20)
 orphan=0
 for tag in active:
  if not await db.inventory_rolls.find_one({'id':tag['roll_id']}):orphan+=1
 e.check('I6-R01',{'failed_attach_http_status':status,'active_tags_before':before_active,'active_tags_after':len(active),'active_tags_without_roll':orphan},status==409 and before_active==0 and len(active)==1 and orphan==1)
 cmprod={**product,'id':'CM','sku':'CM','base_unit':'cm'}
 await db.products.insert_one(dict(cmprod))
 cmtask={**task,'id':'CMTASK','product_id':'CM'}
 await db.wms_tasks.insert_one(dict(cmtask))
 counted=await recv.create_counted_roll(task=cmtask,product=cmprod,owner_entity_id='A',actor=actor,length=100)
 expected=uom.convert(cmprod,100,'cm','meter',await uom.load_fixed_factors())
 e.check('I6-W01',{'roll_length':counted['roll']['length_remaining'],'roll_unit':counted['roll']['unit'],'task_unit':counted['task']['unit'],'recorded_received_qty':counted['task']['received_qty'],'canonical_received_qty':expected,'task_status':counted['task']['status']},expected==1 and counted['task']['received_qty']==100 and counted['task']['status']=='qc_check')
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  (e.B/'integration_round6.json').write_text(json.dumps({'source_commit':'d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467','database':e.DBNAME,'mode':'Real local Mongo and unmodified service functions; fixtures for master/opening stock and closing; no simulated exceptions','results':e.RESULTS},indent=2),encoding='utf-8')
  e.client.close()
