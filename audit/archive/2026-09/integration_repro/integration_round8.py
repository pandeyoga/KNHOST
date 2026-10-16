"""Purchase return service lifecycle and ledger consistency; local synthetic Mongo only."""
import asyncio,json
import integration_round4 as e
from services import purchase_return_service as pr,roll_service as rolls
from schemas_purchasing import PurchaseReturnCreate,PurchaseReturnItem
db=e.db
async def fixture(tag,tax=0,rma=False,qty=10,specific=True):
 pid='P'+tag;poid='PO'+tag
 await db.products.insert_one({'id':pid,'sku':pid,'name':pid,'base_unit':'meter','harga_pokok':10,'price':10,'grade':'A'})
 await db.purchase_orders.insert_one({'id':poid,'po_number':poid,'entity_id':'A','supplier_id':'SUP','supplier_name':'Supplier','warehouse_id':'WH','status':'completed','net_subtotal':100,'total_amount':100,'ppn_amount':tax,'grand_total':100+tax,'paid_amount':0,'returned_amount':0,'items':[{'product_id':pid,'quantity':10,'received_qty':10,'price':10,'unit':'meter'}]})
 r=await rolls.create_inbound_roll(pid,'WH','A',10,unit_cost=10,acquired_via='purchase',ref_id=poid)
 ret=await pr.create_purchase_return(PurchaseReturnCreate(supplier_id='SUP',po_id=poid,warehouse_id='WH',entity_id='A',supplier_flow=rma,items=[PurchaseReturnItem(product_id=pid,quantity=qty,price=10,roll_ids=[r['id']] if specific else [])]),'Audit')
 ret=await pr.submit_purchase_return(ret['id'],'Audit')
 return ret,r,poid
async def state(ret,r,poid):
 d=await db.purchase_returns.find_one({'id':ret['id']});roll=await db.inventory_rolls.find_one({'id':r['id']});po=await db.purchase_orders.find_one({'id':poid})
 js=await db.journal_entries.find({'source_id':ret['id']}).to_list(100)
 return {'status':d['status'],'supplier_status':d['supplier_status'],'roll_status':roll['status'],'roll_remaining':roll['length_remaining'],'returned_amount':po['returned_amount'],'journal_count':len(js),'journal_debit':sum(j['total_debit'] for j in js),'grand_total':d['grand_total']}
async def main():
 await e.seed();await db.suppliers.insert_one({'id':'SUP','name':'Supplier'});await db.warehouses.insert_one({'id':'WH','name':'Warehouse'})
 ret,r,po=await fixture('OK')
 await pr.approve_and_adjust_stock(ret['id'],'Audit')
 s=await state(ret,r,po)
 e.check('I8-C01',s,s['status']=='approved' and s['roll_status']=='returned_supplier' and s['returned_amount']==100 and s['journal_debit']==100,'control')
 rev=await pr.reverse_settlement(ret['id'],'Audit','Synthetic correction')
 s=await state(ret,r,po)
 account_net={}
 async for entry in db.journal_entries.find({'source_id':ret['id']}):
  for line in entry['lines']:account_net[line['account_code']]=round(account_net.get(line['account_code'],0)+line['debit']-line['credit'],2)
 e.check('I8-C02',{**s,'account_net_after_reversal':account_net},s['status']=='cancelled' and s['roll_status']=='available' and s['returned_amount']==0 and bool(rev['reversal_je_ids']) and all(v==0 for v in account_net.values()),'control')
 await pr.reverse_settlement(ret['id'],'Audit','Retry correction')
 e.check('I8-C03',{'unchanged':s==await state(ret,r,po)},s==await state(ret,r,po),'control')
 ret,r,po=await fixture('VAT',tax=11)
 await db.vendor_bills.insert_one({'id':'BILLVAT','po_id':po,'status':'posted','entity_id':'A'})
 await pr.approve_and_adjust_stock(ret['id'],'Audit')
 s=await state(ret,r,po);j=await db.journal_entries.find_one({'source_id':ret['id']})
 credits={ln['account_code']:ln['credit'] for ln in j['lines'] if ln['credit']}
 debits={ln['account_code']:ln['debit'] for ln in j['lines'] if ln['debit']}
 e.check('I8-F01',{**s,'credits':credits,'debits':debits},s['grand_total']==111 and s['returned_amount']==111 and s['journal_debit']==100 and credits.get('1-1300')==89 and debits.get('2-1100')==100)
 ret,r,po=await fixture('REFUND',tax=11,rma=True)
 await pr.approve_and_adjust_stock(ret['id'],'Audit');await pr.ship_to_supplier(ret['id'],'Audit');await pr.supplier_accept(ret['id'],'Audit',outcome='refund')
 s=await state(ret,r,po);cash=await db.cash_transactions.find_one({'ref_type':'purchase_return','ref_id':ret['id']})
 e.check('I8-F02',{**s,'cash_amount':cash.get('amount') if cash else None},s['grand_total']==111 and s['journal_debit']==100 and cash and cash['amount']==100)
 ret,r,po=await fixture('BACK',rma=True)
 await pr.approve_and_adjust_stock(ret['id'],'Audit');await pr.ship_to_supplier(ret['id'],'Audit')
 await pr.supplier_reject(ret['id'],'Audit','Synthetic supplier refusal');await pr.goods_back(ret['id'],'Audit')
 s=await state(ret,r,po)
 e.check('I8-C04',s,s['roll_status']=='available' and s['returned_amount']==0 and s['journal_count']==0,'control')
 ret,r,po=await fixture('LOCK')
 today=e.datetime.now(e.timezone.utc).date().isoformat()
 await db.period_closings.insert_one({'id':'LOCK','entity_id':'A','status':'closed','period_type':'month','period_key':today[:7],'start_date':today,'end_date':today})
 try:await pr.approve_and_adjust_stock(ret['id'],'Audit')
 except Exception as ex:err=type(ex).__name__
 else:err='NONE'
 s=await state(ret,r,po)
 e.check('I8-F03',{'exception':err,**s},err=='ClosedPeriodError' and s['status']=='approved' and s['returned_amount']==100 and s['journal_count']==0 and s['roll_status']=='returned_supplier')
 await db.period_closings.update_one({'id':'LOCK'},{'$set':{'status':'open'}})
 try:await pr.approve_and_adjust_stock(ret['id'],'Audit')
 except ValueError:denied=True
 else:denied=False
 e.check('I8-F04',{'retry_rejected':denied,'journal_count':(await state(ret,r,po))['journal_count']},denied and (await state(ret,r,po))['journal_count']==0)
 ret,r,po=await fixture('SHORT',qty=15,specific=False)
 try:await pr.approve_and_adjust_stock(ret['id'],'Audit')
 except ValueError:denied=True
 else:denied=False
 s=await state(ret,r,po)
 e.check('I8-F05',{'insufficient_stock_rejected':denied,**s},denied and s['status']=='pending_approval' and s['roll_status']=='returned_supplier' and s['returned_amount']==0)
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  (e.B/'integration_round8.json').write_text(json.dumps({'source_commit':'d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467','database':e.DBNAME,'mode':'Original purchase return services and real Mongo, synthetic master/PO/opening rolls; no tax-law assumptions','results':e.RESULTS},indent=2),encoding='utf-8');e.client.close()
