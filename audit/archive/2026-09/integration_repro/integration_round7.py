"""Full manual GRN service lifecycle on synthetic Mongo fixtures."""
import asyncio,json
import integration_round4 as e
from services import goods_receipt_service as g,goods_receipt_close_service as close
from entity_scope import EntityContext
from schemas_goods_receipt import GRNCreateIn,GRNDnPatch,GRNLineIn,GRNDeclared,GRNTargetIn,GRNCountRollIn,GRNReasonIn
db=e.db
actor={'id':'U','name':'Audit','role':'finance'}
ctx=EntityContext(user=actor,active_entity_id='A',allowed_entity_ids=['A'])
async def fixture(tag,base_unit='meter',quantity=10,length=10,dn=None):
 pid='P'+tag;tid='T'+tag;poid='PO'+tag
 await db.products.insert_one({'id':pid,'name':pid,'sku':pid,'base_unit':base_unit,'harga_pokok':10,'grade':'A'})
 await db.purchase_orders.insert_one({'id':poid,'po_number':poid,'entity_id':'A','supplier_id':'SUP','supplier_name':'Supplier','status':'ordered','warehouse_id':'WH','items':[{'product_id':pid,'quantity':quantity,'received_qty':0,'price':10,'unit':'meter'}]})
 await db.wms_tasks.insert_one({'id':tid,'flow_type':'inbound','entity_id':'A','warehouse_id':'WH','po_id':poid,'po_number':poid,'product_id':pid,'sku':pid,'status':'waiting_goods','unit':'meter','expected_qty':quantity,'received_qty':0,'quantity':quantity,'qty_rolls_scanned':0})
 grn=await g.create_grn(GRNCreateIn(partner_type='supplier',partner_id='SUP',warehouse_id='WH',po_ids=[poid]),actor,ctx)
 gid=grn['id']
 grn=await g.manual_entry(gid,grn['version'],actor,ctx)
 grn=await g.patch_dn(gid,GRNDnPatch(expected_version=grn['version'],number=dn or 'DN'+tag,date='2026-09-30'),actor,ctx)
 grn=await g.add_line(gid,GRNLineIn(expected_version=grn['version'],declared=GRNDeclared(qty=quantity,unit='meter',rolls=1,lot='LOT'+tag),target=GRNTargetIn(type='po_task',task_id=tid),decision='accept'),actor,ctx)
 grn=await g.start_count(gid,grn['version'],actor,ctx)
 result=await g.add_counted_roll(gid,1,GRNCountRollIn(length=length,lot='LOT'+tag,expected_version=grn['version']),actor,ctx)
 return result['grn'],tid,poid,result['roll']
async def snapshot(gid,tid,poid):
 grn=await db.goods_receipts.find_one({'id':gid});task=await db.wms_tasks.find_one({'id':tid});po=await db.purchase_orders.find_one({'id':poid})
 rolls=await db.inventory_rolls.find({'grn_id':gid}).to_list(100)
 journals=await db.journal_entries.find({'source_id':tid}).to_list(100)
 return {'grn_status':grn['status'],'task_status':task['status'],'po_received_qty':po['items'][0]['received_qty'],'roll_count':len(rolls),'roll_statuses':[r['status'] for r in rolls],'journal_count':len(journals),'journal_debit':sum(j.get('total_debit',0) for j in journals),'posted_statuses':[ln['posted']['status'] for ln in grn['lines']]}
async def main():
 await e.seed()
 await db.warehouses.insert_one({'id':'WH','name':'Audit Warehouse','status':'active'})
 await db.suppliers.insert_one({'id':'SUP','name':'Supplier'})
 await db.goods_receipts.create_index([('active_key',1)],name='uq_active_key',unique=True,partialFilterExpression={'active_key':{'$type':'string','$gt':''}})
 grn,tid,poid,r=await fixture('GOOD')
 grn=await close.finish_count(grn['id'],grn['version'],actor,ctx)
 result=await close.close_grn(grn['id'],grn['version'],actor,ctx)
 s=await snapshot(grn['id'],tid,poid)
 e.check('I7-C01',s,s['grn_status']=='closed' and s['po_received_qty']==10 and s['journal_count']==1 and s['journal_debit']==100,'control')
 before=s
 try:await close.close_grn(grn['id'],result['grn']['version'],actor,ctx)
 except Exception as ex:status=getattr(ex,'status_code',None)
 else:status=200
 e.check('I7-C02',{'repeat_close_status':status,'unchanged':before==await snapshot(grn['id'],tid,poid)},status==409 and before==await snapshot(grn['id'],tid,poid),'control')
 await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.wms':['update']}})
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as http:
  res=await http.post(f'/api/inbound/tasks/{tid}/qc-decision',json={'accept_qty':4,'reject_qty':0,'reason':'Partial QC audit'})
  remaining=await db.inventory_rolls.find({'qc_task_id':tid,'status':'quarantine'}).to_list(100)
  qty=sum(x['length_remaining'] for x in remaining)
  task=await db.wms_tasks.find_one({'id':tid})
  e.check('I7-W01',{'http_status':res.status_code,'task_status':task['status'],'remaining_quarantine':qty},res.status_code==200 and task['status']=='completed' and qty==6)
  res=await http.post(f'/api/inbound/tasks/{tid}/qc-decision',json={'accept_qty':6,'reject_qty':0,'reason':'Remaining QC audit'})
  e.check('I7-W02',{'remaining_decision_status':res.status_code,'detail':res.json().get('detail')},res.status_code==400)
 grn,tid,poid,r=await fixture('CANCEL')
 cancelled=await close.cancel_grn(grn['id'],GRNReasonIn(expected_version=grn['version'],reason='Synthetic cancellation'),actor,ctx)
 s=await snapshot(grn['id'],tid,poid)
 tag=await db.rfid_tags.find_one({'id':r['rfid_tag_id']})
 e.check('I7-C03',{**s,'tag_status':tag['status']},s['grn_status']=='cancelled' and s['roll_count']==0 and s['po_received_qty']==0 and s['journal_count']==0 and tag['status']=='retired','control')
 await close.cancel_grn(grn['id'],GRNReasonIn(expected_version=cancelled['version'],reason='Synthetic retry'),actor,ctx)
 e.check('I7-C04',{'unchanged':s==await snapshot(grn['id'],tid,poid)},s==await snapshot(grn['id'],tid,poid),'control')
 grn,tid,poid,r=await fixture('LOCK')
 grn=await close.finish_count(grn['id'],grn['version'],actor,ctx)
 today=e.datetime.now(e.timezone.utc).date().isoformat()
 await db.period_closings.insert_one({'id':'LOCK','entity_id':'A','status':'closed','period_type':'month','period_key':today[:7],'start_date':today,'end_date':today})
 result=await close.close_grn(grn['id'],grn['version'],actor,ctx)
 s=await snapshot(grn['id'],tid,poid)
 e.check('I7-F01',s,s['grn_status']=='closed' and s['po_received_qty']==10 and s['journal_count']==0 and s['posted_statuses']==['done'])
 await db.period_closings.update_one({'id':'LOCK'},{'$set':{'status':'open'}})
 try:await close.close_grn(grn['id'],result['grn']['version'],actor,ctx)
 except Exception as ex:status=getattr(ex,'status_code',None)
 else:status=200
 e.check('I7-F02',{'retry_status':status,'journal_count':(await snapshot(grn['id'],tid,poid))['journal_count']},status==409 and (await snapshot(grn['id'],tid,poid))['journal_count']==0)
 grn,tid,poid,r=await fixture('CM','cm',1,100)
 grn=await close.finish_count(grn['id'],grn['version'],actor,ctx)
 try:await close.close_grn(grn['id'],grn['version'],actor,ctx)
 except Exception as ex:status=getattr(ex,'status_code',None);detail=getattr(ex,'detail',{})
 else:status=200;detail={}
 s=await snapshot(grn['id'],tid,poid)
 e.check('I7-C05',{'close_status':status,'error':detail,**s},status==400 and detail.get('code')=='BLOCKERS_OPEN' and s['po_received_qty']==0 and s['journal_count']==0,'control')
 grn,tid,poid,r=await fixture('STALE')
 try:await close.finish_count(grn['id'],grn['version']-1,actor,ctx)
 except Exception as ex:status=getattr(ex,'status_code',None)
 else:status=200
 e.check('I7-C06',{'stale_version_status':status,'grn_status':(await g.load(grn['id'],ctx))['status']},status==409 and (await g.load(grn['id'],ctx))['status']=='counting','control')
 wrong_ctx=EntityContext(user={'id':'USERB','role':'finance'},active_entity_id='B',allowed_entity_ids=['B'])
 try:await g.load(grn['id'],wrong_ctx)
 except Exception as ex:status=getattr(ex,'status_code',None)
 else:status=200
 e.check('I7-C07',{'foreign_grn_access_status':status},status==404,'control')
 await fixture('DUP1',dn='DUPLICATE-DN')
 try:await fixture('DUP2',dn='DUPLICATE-DN')
 except Exception as ex:status=getattr(ex,'status_code',None);detail=getattr(ex,'detail',{})
 else:status=200;detail={}
 dup=await db.goods_receipts.find_one({'source.po_ids':'PODUP2'})
 e.check('I7-C08',{'duplicate_dn_status':status,'code':detail.get('code'),'losing_grn_status':dup['status']},status==409 and detail.get('code')=='DN_DUPLICATE' and dup['status']=='review','control')
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  (e.B/'integration_round7.json').write_text(json.dumps({'source_commit':'d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467','database':e.DBNAME,'mode':'Actual manual GRN service lifecycle; synthetic master/PO/task; actual Mongo with active_key unique index; no external calls','results':e.RESULTS},indent=2),encoding='utf-8');e.client.close()
