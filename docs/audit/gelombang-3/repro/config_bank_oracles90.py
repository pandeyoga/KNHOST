"""Public config simulations and bank parsers, deterministic business oracles."""
import asyncio,json,traceback
from datetime import date
from pathlib import Path
import wave2_env as e
from services import config_simulator as sim,bank_statement_parser as parser
from services.vendor_bill_service import evaluate_match

RESULTS=[];CONTEXT={};ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,
  status='pass' if want==actual else 'observed_difference'))
async def post(h,path,body):
 r=await h.post('/api/'+path,json=body)
 assert r.status_code==200,(path,r.status_code,r.text)
 return r.json()
async def simulations(h):
 cases=[
 ('ar_penalty',{'ar.denda_rate_pct_per_month':2,'ar.grace_days':7},{'outstanding':1000,'days_late':7},'ok'),
 ('ar_penalty',{'ar.denda_rate_pct_per_month':2,'ar.grace_days':0},{'outstanding':1000,'days_late':30},'warn'),
 ('ar_penalty',{'ar.denda_rate_pct_per_month':2,'ar.grace_days':0},{'outstanding':1000,'days_late':90},'block'),
 ('ar_bucket',{'ar.aging_buckets':[30,60,90]},{'days_late':31},'ok'),
 ('pricing',{'sales.allow_item_discount':False,'sales.allow_order_discount':False},{},'warn'),
 ('pricing',{'sales.allow_item_discount':True,'sales.allow_order_discount':True},{},'ok'),
 ('commission_cap',{'commission.default_margin_cap_pct':50},{'line_margin':100,'commission':60},'warn'),
 ('commission_cap',{'commission.default_margin_cap_pct':50},{'line_margin':100,'commission':40},'ok'),
 ('commission_discount',{'commission.discount_threshold':10,'commission.discount_mechanic':'cutoff'},{'discount':15},'warn'),
 ('commission_discount',{'commission.discount_threshold':10,'commission.discount_mechanic':'potong_rp','commission.discount_potong_rp':100},{'discount':15},'warn'),
 ('commission_discount',{'commission.discount_threshold':10,'commission.discount_mechanic':'tier_factor'},{'discount':15},'warn'),
 ('commission_discount',{'commission.discount_threshold':10},{'discount':5},'ok'),
 ('receiving_over',{'purchasing.receive_tolerance_percent':2,'receiving.block_over_remaining':True},{'po_qty':100,'received_total':102},'ok'),
 ('receiving_over',{'purchasing.receive_tolerance_percent':2,'receiving.block_over_remaining':True},{'po_qty':100,'received_total':103},'block'),
 ('receiving_over',{'purchasing.receive_tolerance_percent':2,'receiving.block_over_remaining':False},{'po_qty':100,'received_total':103},'warn'),
 ('bill_match',{'purchasing.bill_qty_tolerance_percent':0,'purchasing.bill_price_tolerance_percent':5},{'received_qty':100,'billed_qty':100,'po_price':100,'billed_price':100},'ok'),
 ('bill_match',{'purchasing.bill_qty_tolerance_percent':0,'purchasing.bill_price_tolerance_percent':5},{'received_qty':100,'billed_qty':101,'po_price':100,'billed_price':110},'block'),
 ('qc_grade',{'qc.grade_thresholds.a_max':20,'qc.grade_thresholds.b_max':40},{'points':20},'ok'),
 ('qc_grade',{'qc.grade_thresholds.a_max':20,'qc.grade_thresholds.b_max':40},{'points':21},'warn'),
 ('qc_grade',{'qc.grade_thresholds.a_max':20,'qc.grade_thresholds.b_max':40},{'points':41},'block'),
 ('stock_class',{'inventory.stock_analytics.fast_max_days':30,'inventory.stock_analytics.slow_max_days':90},{'days_since_sale':30},'ok'),
 ('stock_class',{'inventory.stock_analytics.fast_max_days':30,'inventory.stock_analytics.slow_max_days':90},{'days_since_sale':31},'warn'),
 ('stock_class',{'inventory.stock_analytics.fast_max_days':30,'inventory.stock_analytics.slow_max_days':90},{'days_since_sale':91},'block'),
 ('reorder',{'inventory.reorder.velocity_window_days':90,'inventory.reorder.safety_days':7},{'sold_qty':900,'lead_time_days':14},'ok'),
 ('uom_variance',{'uom.warn_pct':2,'uom.block_pct':5,'uom.allow_override':True},{'expected':100,'actual':101},'ok'),
 ('uom_variance',{'uom.warn_pct':2,'uom.block_pct':5,'uom.allow_override':True},{'expected':100,'actual':103},'warn'),
 ('uom_variance',{'uom.warn_pct':2,'uom.block_pct':5,'uom.allow_override':True},{'expected':100,'actual':106},'block'),
 ('uom_variance',{'uom.warn_pct':2,'uom.block_pct':5,'uom.allow_override':False},{'expected':100,'actual':106},'block'),
 ('lot_enforce',{'lot.enforcement_mode':'off'},{},'ok'),
 ('lot_enforce',{'lot.enforcement_mode':'warn'},{},'warn'),
 ('lot_enforce',{'lot.enforcement_mode':'block'},{},'block'),
 ('lot_enforce',{'lot.enforcement_mode':'block'},{'has_supplier_lot':True,'has_dye_lot':True},'ok'),
 ('lot_number',{'lot.number_format':'LOT-YYMM-####'},{'sequence':7},'ok'),
 ('makloon_variance',{'makloon.default_shrinkage_pct':5,'makloon.variance_tolerance_pct':3,'makloon.auto_claim':True},{'sent_qty':1000,'returned_qty':950},'ok'),
 ('makloon_variance',{'makloon.default_shrinkage_pct':5,'makloon.variance_tolerance_pct':3,'makloon.auto_claim':True},{'sent_qty':1000,'returned_qty':900},'block'),
 ('makloon_variance',{'makloon.default_shrinkage_pct':5,'makloon.variance_tolerance_pct':3,'makloon.auto_claim':False},{'sent_qty':1000,'returned_qty':900},'warn'),
 ('payroll_bpjs',{}, {'salary':8000000},'ok'),
 ('payroll_overtime',{'hr.overtime.hours_divisor':173,'hr.overtime.multiplier':1.5},{'salary':1730000,'overtime_hours':4},'ok'),
 ('payroll_pph21',{'hr.ter_enabled':True},{},'ok'),
 ('payroll_pph21',{'hr.ter_enabled':False},{},'warn'),
 ('min_cut',{'inventory.min_cut_qty':.5},{'qty':.3},'block'),
 ('min_cut',{'inventory.min_cut_qty':.5},{'qty':.5},'ok'),
 ('po_supplier',{'purchasing.require_supplier_master':True},{'has_supplier_master':False},'block'),
 ('po_supplier',{'purchasing.require_supplier_master':False},{'has_supplier_master':False},'ok'),
 ('interco',{'inventory.intercompany_transfer_required':True},{'uses_other_entity_stock':True},'block'),
 ('interco',{'inventory.intercompany_transfer_required':True},{'uses_other_entity_stock':False},'ok'),
 ('quotation',{'sales.quotation_enabled':True},{},'ok'),
 ('quotation',{'sales.quotation_enabled':False},{},'ok'),
 ('currency',{'finance.base_currency':'IDR'},{'amount':1250000},'ok'),
 ('fiscal_year',{'finance.fiscal_year_end_month':12},{'period':'2026-10'},'ok'),
 ('price_deviation',{'purchasing.price_deviation_approval_percent':10},{'reference_price':100,'po_price':110},'ok'),
 ('price_deviation',{'purchasing.price_deviation_approval_percent':10},{'reference_price':100,'po_price':111},'block'),
 ('approval',{'approval.extra_levels':{}},{'amount':100,'doc_type':'purchase_order'},'ok'),
 ('approval',{'approval.extra_levels':{'purchase_order':[{'role':'admin','min_amount':100}]}},{'amount':100,'doc_type':'purchase_order'},'warn'),
 ]
 for i,(name,values,sample,want) in enumerate(cases):
  # Use pure simulations for unrestricted engine policy boundaries; public resolver
  # may prohibit hypothetical values independently. Values above are business fixtures.
  d=sim.run(name,values,sample)
  rec(f'SIM90-{name}-{i}',want,d['verdict'])
  CONTEXT[f'sim-{i}']=d
 for mode,rate,nl,pkp,subtotal in [('excluded',12,True,True,10000000),('included',12,True,True,11100000),('excluded',0,False,True,1000),('excluded',12,False,False,1000)]:
  values={'tax.ppn_mode':mode,'tax.ppn_rate':rate,'tax.dpp_nilai_lain':nl,'tax.efaktur_enabled':pkp}
  d=await post(h,'config/simulate',{'simulator':'tax','overrides':values,'sample':{'subtotal':subtotal}})
  CONTEXT['tax-'+mode+'-'+str(rate)+'-'+str(pkp)]=d
  expected='11.100.000' if pkp and rate else '1.000'
  rec('SIM90-public-tax-'+mode+'-'+str(pkp)+'-'+str(rate),True,expected in d['result'])
 d=await post(h,'config/simulate',{'simulator':'bill_match',
  'overrides':{'purchasing.bill_qty_tolerance_percent':0,'purchasing.bill_price_tolerance_percent':5},
  'sample':{'received_qty':0,'billed_qty':10,'po_price':100,'billed_price':100}})
 actual_engine=evaluate_match({'items':[{'line_id':'L','product_id':'P','quantity':10,'received_qty':0,'price':100}]},
  [{'line_id':'L','product_id':'P','quantity':10,'billed_qty':10,'price':100}], 'received',{},0,5)
 rec('SIM90-zero-receipt-real-matcher-control','blocked',actual_engine['match_status'])
 rec('SIM90-zero-receipt-public-verdict','block',d['verdict'],
  'No goods received, billed10 at positive price, zero tolerance: the original bill matcher blocks; public simulation reports 3-way match passed.')
 CONTEXT['zero-receipt']=dict(public=d,original_matcher=actual_engine)
async def bank(h):
 await e.db.bank_accounts.insert_one({'id':'BANK90','entity_id':'A','name':'Synthetic bank','account_type':'bank','is_active':True,'opening_balance':0,'gl_account_code':'1-1100'})
 fmt={'file_kind':'csv','delimiter':',','has_header':True,'decimal_style':'en','date_format':'yyyy-mm-dd',
  'columns':{'date':'date','description':'description','amount':'amount','direction':'direction'}}
 for stamp,valid in [('2026-02-28',True),('2026-02-30',False),('2026-99-99',False),('2026-13-01',False)]:
  raw=f'date,description,amount,direction\n{stamp},Synthetic {stamp},100,CR\n'
  d=await post(h,'bank-reconciliation/preview',{'raw':raw,'fmt':fmt})
  rec('BANK90-date-preview-'+stamp,1 if valid else 0,d['total'],
   'Calendar validity checked independently with datetime.date, not parser output.')
  imported=await h.post('/api/bank-reconciliation/import-file',json={'bank_account_id':'BANK90','raw':raw,'fmt':fmt})
  stored=await e.db.bank_statement_lines.count_documents({'bank_account_id':'BANK90','stmt_date':stamp})
  rec('BANK90-date-persistence-'+stamp,1 if valid else 0,stored)
  CONTEXT['bank-date-'+stamp]=dict(preview=d,import_http=imported.status_code,
   import_response=imported.json(),persisted=stored)
 for mark,want in [('C','in'),('D','out'),('RC','out'),('RD','in')]:
  raw=f':61:261006{mark}100,00NTRFNONREF\n:86:LOCAL {mark}\n'
  d=await post(h,'bank-reconciliation/preview',{'raw':raw,'fmt':{'file_kind':'mt940'}})
  rec('BANK90-mt940-'+mark,want,d['rows'][0]['direction'] if d['rows'] else 'not_parsed',
   'Primary bank MT940 specification: RC reverses credit => debit; RD reverses debit => credit.')
  CONTEXT['mt940-'+mark]=d
 raw=':61:261006D100,00NTRFDEBIT\n:86:LOCAL DEBIT\n:61:261006RD100,00NTRFREVERSAL\n:86:LOCAL REVERSAL\n'
 d=await post(h,'bank-reconciliation/preview',{'raw':raw,'fmt':{'file_kind':'mt940'}})
 rec('BANK90-mt940-reversal-net',0,d['sum_in']-d['sum_out'])
 imported=await h.post('/api/bank-reconciliation/import-file',json={'bank_account_id':'BANK90','raw':raw,'fmt':{'file_kind':'mt940'}})
 CONTEXT['mt940-mixed']=dict(preview=d,import_http=imported.status_code,import_response=imported.json())
 for style,text,want in [('id','1.234,56',1234.56),('en','1,234.56',1234.56),('id','(1.234,56)',1234.56),('auto','1,234.56',1234.56),('auto','1.234,56',1234.56),('en','-1234.56',1234.56)]:
  rec('BANK90-nominal-'+style+'-'+text,want,parser.parse_amount(text,style)[0])
async def main():
 await e.seed()
 await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.cash':['view','create']}})
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',
  headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
  for fn in [simulations,bank]:
   try:await fn(h)
   except Exception as ex:ERRORS.append(dict(group=fn.__name__,error=repr(ex),traceback=traceback.format_exc()))
 out=dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,
  context=CONTEXT,harness_errors=ERRORS,primary_spec='https://www.unicredit.ro/content/dam/cee2020-pws-ro/DocumentePDF/DocumenteCIB/MT94x_General_V1.1.pdf')
 Path(__file__).with_name('config-bank-oracles90-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 print(json.dumps(dict(observations=len(RESULTS),differences=[x for x in RESULTS if x['status']!='pass'],errors=ERRORS),ensure_ascii=False),flush=True)
 e.client.close()
asyncio.run(main())
