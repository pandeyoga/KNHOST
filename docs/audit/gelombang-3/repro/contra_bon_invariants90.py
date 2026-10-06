"""Finance integrity detectors: valid controls, deliberately corrupted fixtures, and scale."""
import asyncio,json,traceback
from pathlib import Path
import service_env90 as e
from services import contra_bon_scan as scan,contra_bon_service as svc
RESULTS=[];ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
def cb(key,**fields):return {'id':key,'number':key,'status':'verified','bills':[],'deductions':[],'payments':[],'decisions':[],'totals':{'net_payable':0},**fields}
async def one(key,fn,doc,expected):
 await e.db[scan.COLL].delete_many({});await e.db[scan.COLL].insert_one(doc)
 rec(key,expected,len(await fn()))
async def main():
 try:
  await e.setup()
  funcs=[scan.bills_in_multiple_contra_bons,scan.bill_over_applied,scan.totals_mismatch,scan.settlement_mismatch,scan.undecided_exceptions,scan.decisions_without_reason,scan.deduction_refs_reused,scan.deduction_over_source,scan.makloon_double_deduction]
  for f in funcs:rec('contra.empty_'+f.__name__,0,len(await f()))
  await e.db.vendor_bills.insert_one({'id':'B1','bill_number':'B1','grand_total':100,'payments':[{'contra_bon_id':'C1','amount':100}]})
  await e.db.amendment_reasons.insert_one({'id':'R1','code':'OK','applies_to':svc.REASON_DOC_TYPE})
  await e.db.purchase_returns.insert_one({'id':'P1','number':'P1','total_amount':20,'status':'settled'})
  await e.db.cash_transactions.insert_one({'id':'K1','number':'K1','amount':30})
  bill={'bill_id':'B1','bill_number':'B1','applied_amount':100,'settled_amount':100}
  await one('contra.bill_within_cap',scan.bill_over_applied,cb('C1',bills=[bill]),0)
  await one('contra.bill_over_cap',scan.bill_over_applied,cb('C1',bills=[{**bill,'applied_amount':101}]),1)
  await one('contra.bill_missing_detected',scan.bill_over_applied,cb('C1',bills=[{**bill,'bill_id':'missing'}]),1)
  await e.db[scan.COLL].delete_many({});await e.db[scan.COLL].insert_many([cb('C1',bills=[bill]),cb('C2',bills=[bill]),cb('C3',status='cancelled',bills=[bill])])
  rec('contra.multiple_active_detected',1,len(await scan.bills_in_multiple_contra_bons()))
  await e.db[scan.COLL].update_one({'id':'C2'},{'$set':{'status':'cancelled'}})
  rec('contra.cancelled_not_duplicate',0,len(await scan.bills_in_multiple_contra_bons()))
  for key,doc,want in [
   ('valid',cb('C1',bills=[bill],totals={'net_payable':100}),0),
   ('invalid_net',cb('C1',bills=[bill],totals={'net_payable':99}),1),
   ('negative_net',cb('C1',deductions=[{'amount':10}],totals={'net_payable':-10}),1),
   ('paid_short',cb('C1',status='paid',bills=[bill],payments=[{'amount':99}],totals={'net_payable':100}),1),
   ('paid_valid',cb('C1',status='paid',bills=[bill],payments=[{'amount':100}],totals={'net_payable':100}),0),
   ('overpaid',cb('C1',bills=[bill],payments=[{'amount':101}],totals={'net_payable':100}),1)]:await one('contra.totals_'+key,scan.totals_mismatch,doc,want)
  for key,doc,want in [
   ('valid',cb('C1',status='paid',bills=[bill]),0),
   ('applied_diff',cb('C1',status='paid',bills=[{**bill,'settled_amount':99}]),1),
   ('ledger_diff',cb('C2',status='paid',bills=[bill]),1),
   ('missing_bill',cb('C1',status='paid',bills=[{**bill,'bill_id':'missing'}]),0)]:await one('contra.settlement_'+key,scan.settlement_mismatch,doc,want)
  mismatch={**bill,'match':{'exceptions':[{'key':'QTY','detail':'Physical receipt differs'}]}}
  await one('contra.exception_unresolved',scan.undecided_exceptions,cb('C1',bills=[mismatch]),1)
  await one('contra.exception_resolved',scan.undecided_exceptions,cb('C1',bills=[mismatch],decisions=[{'exception_key':'QTY','reason_code':'OK'}]),0)
  for reason,want in [('',1),('missing',1),('OK',0)]:await one('contra.reason_'+reason,scan.decisions_without_reason,cb('C1',decisions=[{'exception_key':'QTY','reason_code':reason}]),want)
  await e.db[scan.COLL].delete_many({});await e.db[scan.COLL].insert_many([cb('C1',deductions=[{'ref_id':'P1'}]),cb('C2',deductions=[{'ref_id':'P1'}])])
  rec('contra.deduction_double_detected',1,len(await scan.deduction_refs_reused()))
  for kind,ref,amount,want in [('purchase_return','P1',20,0),('purchase_return','P1',21,1),('advance','K1',30,0),('advance','K1',31,1),('advance','missing',1,1),('advance','',1,0)]:
   await one('contra.deduction_'+str((kind,ref,amount)),scan.deduction_over_source,cb('C1',deductions=[{'kind':kind,'ref_id':ref,'amount':amount}]),want)
  for kind,want in [('purchase_return',0),('makloon_claim',1),('makloon_potong_bon',1)]:await one('contra.makloon_'+kind,scan.makloon_double_deduction,cb('C1',deductions=[{'id':'D1','kind':kind}]),want)
  # 2,000 harmless live documents, then two documents referencing one identical bill.
  # The detector must find the duplicate regardless of where its cursor window ends.
  await e.db[scan.COLL].delete_many({})
  docs=[cb(f'EMPTY-{i}') for i in range(2000)]+[cb('TAIL-1',bills=[bill]),cb('TAIL-2',bills=[bill])]
  await e.db[scan.COLL].insert_many(docs)
  rec('contra.scale_duplicate_2002',1,len(await scan.bills_in_multiple_contra_bons()),'Direct corrupted fixtures deliberately validate the audit detector; no public producer claim.')
 except Exception:ERRORS.append(traceback.format_exc())
 finally:
  d=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,harness_errors=ERRORS,scope='Original read-only finance integrity services; explicit valid/corrupt local fixtures.')
  Path(__file__).with_name('contra-bon-invariants90-results.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'observations':len(RESULTS),'differences':[r['id'] for r in RESULTS if r['status']!='pass'],'errors':ERRORS}));e.client.close()
if __name__=='__main__':asyncio.run(main())
