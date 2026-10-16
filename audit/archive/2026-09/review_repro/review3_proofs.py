"""Additional source-function characterization. No Mongo, HTTP, real money or messages."""
import asyncio,copy,json,types,hashlib
from pathlib import Path
import review2_flow_proofs as h
h.RESULTS.clear()
def _aiter(self):self._it=iter([h.project(r,self.p) for r in self.rows]);return self
async def _anext(self):
    try:return next(self._it)
    except StopIteration:raise StopAsyncIteration
h.Cursor.__aiter__=_aiter;h.Cursor.__anext__=_anext
oldmatch=h.match
def expr(d,x):
    if isinstance(x,str) and x.startswith('$'):
        path=x[1:].split('.');val=d
        for i,k in enumerate(path):
            if isinstance(val,list):return [h.get(z,'.'.join(path[i:]),0) for z in val]
            val=val.get(k,[]) if isinstance(val,dict) else None
        return val
    if not isinstance(x,dict):return x
    if '$sum' in x:return sum(expr(d,x['$sum']) or [])
    if '$add' in x:return sum(expr(d,y) for y in x['$add'])
    if '$lte' in x:return expr(d,x['$lte'][0])<=expr(d,x['$lte'][1])
    raise NotImplementedError(x)
def match(d,q):
    if '$expr' in q:return expr(d,q['$expr']) and oldmatch(d,{k:v for k,v in q.items() if k!='$expr'})
    return oldmatch(d,q)
h.match=match
async def posted(*a,**kw):return {'id':'JE','number':'JE-1'}
async def empty(*a,**kw):return []
def money(x):return round(float(x or 0),2)
def order(id='SO',customer='C',entity='A',amount=200):
    return dict(id=id,number=id,customer_id=customer,entity_id=entity,grand_total=amount,payments=[],paid_total=0,status='delivered',payment_method='credit')
def sc_setup(db,gl_fail=False):
    h.setup(db)
    ar=h.module('backend/services/ar_receipt_service.py',['_validate_allocation_target','_apply_to_order','_payment_status','list_open_orders'],db,
                EPS=.01,rupiah=str,order_grand_total=lambda o:o['grand_total'],order_paid=lambda o:sum(x['amount'] for x in o.get('payments',[])),
                order_payment_method=lambda o:o['payment_method'],NON_AR_METHODS={'cash'},DEAD_STATUSES={'cancelled'})
    async def gl(*a,**k):
        if gl_fail:raise RuntimeError('injected GL failure')
        return await posted()
    return h.module('backend/services/store_credit_service.py',['balance','_scope_clause','_append','redeem','_redeem_locked'],db,
                    EPS=.01,DEFAULT_ENTITY_ID='A',rupiah=str,gl_service=types.SimpleNamespace(post_store_credit_redemption=gl),
                    _apply_to_order=ar._apply_to_order,list_open_orders=ar.list_open_orders,
                    order_payment_method=lambda o:o['payment_method'],NON_AR_METHODS={'cash'})
def ledgerdb(orders):return h.DB(customers=[{'id':'C','name':'Customer C','entity_id':'A'}],sales_orders=orders,
                              store_credit_ledger=[{'id':'ISS','customer_id':'C','entity_id':'A','amount':100,'status':'posted'}])
async def run():
    db=ledgerdb([order()]);sc=sc_setup(db)
    result=await sc.redeem(customer_id='C',entity_id='A',amount=10,allocations=[{'order_id':'SO','amount':150}])
    bal=await sc.balance('C','A')
    h.record('V3-01','defect',{'requested':10,'applied':result['applied_amount'],'balance':bal},bal==-50,
             'Store-credit customer lock does not enforce allocation sum <= requested/balance: explicit allocation150 passes requested10 against balance100.')
    db=ledgerdb([order(customer='OTHER',entity='B')]);sc=sc_setup(db)
    result=await sc.redeem(customer_id='C',entity_id='A',amount=50,allocations=[{'order_id':'SO','amount':50}])
    h.record('V3-02','defect',{'credit_customer':'C','credit_entity':'A','paid_customer':db.sales_orders.rows[0]['customer_id'],
                            'paid_entity':db.sales_orders.rows[0]['entity_id'],'applied':result['applied_amount']},
             db.sales_orders.rows[0]['paid_total']==50,'Explicit redemption omits customer_id/entity_id arguments to _apply_to_order; original validator bypasses its optional guards.')
    db=ledgerdb([order()]);sc=sc_setup(db,True)
    try:await sc.redeem(customer_id='C',entity_id='A',amount=50,allocations=[{'order_id':'SO','amount':50}])
    except RuntimeError:pass
    h.record('V3-03','defect',{'order_paid':db.sales_orders.rows[0]['paid_total'],'credit_balance':await sc.balance('C','A'),
                            'customer_locked':'saga_lock' in db.customers.rows[0],'redemptions':len(db.store_credit_redemptions.rows)},
             db.sales_orders.rows[0]['paid_total']==50 and await sc.balance('C','A')==100 and 'saga_lock' not in db.customers.rows[0],
             'GL failure after AR mutation leaves payment applied, credit unspent and customer lock released.')
    db=ledgerdb([order()]);sc=sc_setup(db)
    ar=__import__('sys').modules['services.ar_receipt_service']
    blocked=False
    try:await ar._apply_to_order('SO',20,'RC','RC','credit','date',customer_id='OTHER',entity_id='A')
    except h.HTTPException as e:blocked=e.status_code==400
    h.record('V3-C1','control',{'wrong_customer_rejected_when_passed':blocked},blocked,'Shared validator works when caller supplies customer and entity context.')

    # Cash advance: original service with a GL stand-in and source loaders.
    db=h.DB(cash_advances=[{'id':'CA','status':'approved','entity_id':'A','number':'CA-1','total_amount':100}]);h.setup(db)
    gl_calls=0
    async def glcash(*a,**k):
        nonlocal gl_calls
        gl_calls+=1
        if gl_calls==1:raise RuntimeError('GL unavailable')
        return await posted()
    ca=h.module('backend/services/cash_advance_service.py',['get_cash_advance','disburse_cash_advance'],db,
                EntityContext=object,CA_COLL='cash_advances',_r=money,_next_cash_number=h.number,
                assert_active_entity_access=lambda *a:None,audit=h.nop,gl_service=types.SimpleNamespace(post_cash_transaction=glcash))
    payload=types.SimpleNamespace(cash_type='kas_kecil',txn_date=None,note='')
    try:await ca.disburse_cash_advance('CA',payload,None,{'name':'op'})
    except RuntimeError:pass
    await ca.disburse_cash_advance('CA',payload,None,{'name':'op'})
    h.record('V3-04','defect',{'cash_entries':len(db.cash_transactions.rows),'cash_sum':sum(x['amount'] for x in db.cash_transactions.rows),'approved_amount':100},
             len(db.cash_transactions.rows)==2,'Disbursement inserts cash before GL and before final status, no operation claim; failure then retry creates two cash transactions.')

    db=h.DB(cash_advances=[{'id':'CA','status':'disbursed','entity_id':'A','number':'CA-1','total_amount':100}]);h.setup(db)
    jeamounts=[]
    async def settlementgl(**k):jeamounts.append(sum(x['amount'] for x in k['category_lines']));return await posted()
    ca=h.module('backend/services/cash_advance_service.py',['get_cash_advance','get_settlement','_compute_settlement','create_settlement','approve_settlement','_category_account_map'],db,
                EntityContext=object,CA_COLL='cash_advances',STL_COLL='cash_advance_settlements',EXCAT_COLL='expense_categories',FALLBACK_ACCOUNT='EXP',
                _r=money,assert_active_entity_access=lambda *a:None,audit=h.nop,gl_service=types.SimpleNamespace(post_petty_cash_settlement=settlementgl))
    payload=types.SimpleNamespace(cash_advance_id='CA',expense_lines=[{'category':'travel','amount':100}],divisi='',periode='',dibuat_oleh='',catatan='')
    for _ in range(2):
        st=await ca.create_settlement(payload,None,{'name':'op'});await ca.approve_settlement(st['id'],None,{'name':'op'})
    h.record('V3-05','defect',{'advance':100,'settlement_count':len(db.cash_advance_settlements.rows),'expense_posted':sum(jeamounts)},
             sum(jeamounts)==200,'A settled cash advance accepts another settlement; both independently expense full original advance without residual/uniqueness control.')

    # Bank reconciliation original manual/split paths.
    for typ in ('opposite_direction','duplicate_split'):
        db=h.DB(bank_statement_lines=[{'id':'L','entity_id':'A','bank_account_id':'BANK1','direction':'out','amount':120 if typ=='duplicate_split' else 100,'status':'unmatched'}],
                cash_transactions=[{'id':'T','entity_id':'A','account_id':'BANK2','direction':'out' if typ=='duplicate_split' else 'in','amount':100}]);h.setup(db)
        async def line(id,*a):return await db.bank_statement_lines.find_one({'id':id})
        bank=h.module('backend/services/bank_recon_service.py',['manual_match','match_split','_link'],db,
                      EPS=.01,GROUP_ENTITY='all',_round=money,rupiah=str,_norm_dir=lambda x:x,_line=line,learn_from_manual=h.nop)
        if typ=='opposite_direction':
            await bank.manual_match('L','T','op',['A'])
            h.record('V3-06','defect',{'line_direction':'out','txn_direction':'in','line_bank':'BANK1','txn_bank':'BANK2','result':db.bank_statement_lines.rows[0]['status']},
                     db.bank_statement_lines.rows[0]['status']=='matched','Manual bank match validates amounts/access but not direction/account compatibility.')
        else:
            await bank.match_split('L',[{'txn_id':'T','amount':60},{'txn_id':'T','amount':60}],'op',['A'])
            h.record('V3-07','defect',{'txn_amount':100,'reconciled_amount':db.cash_transactions.rows[0]['reconciled_amount']},
                     db.cash_transactions.rows[0]['reconciled_amount']==120,'Split validates each duplicate txn against original available100; two60 entries reconcile120.')

    # Rescheduling reassigns meaning of stable historical payment seq.
    db=h.DB(payment_plans=[{'id':'PLAN','doc_type':'sales_order','doc_id':'SO','status':'active','total_amount':200,'entity_id':'A','customer_id':'C',
                           'lines':[{'seq':1,'label':'First','amount':100,'paid_amount':50,'due_date':'2026-10-01'},
                                    {'seq':2,'label':'Second','amount':100,'paid_amount':100,'due_date':'2026-11-01'}]}]);h.setup(db)
    async def loadsource(*a):return {'grand_total':200,'paid':150}
    async def policy(*a):return {'tolerance':.01}
    async def targets(*a):return {2:100}
    plan=h.module('backend/services/payment_plan_service.py',['get','check_total','reschedule_line','recompute_paid'],db,
                  COLL='payment_plans',EPS=.01,PlanError=ValueError,rupiah=str,plan_policy=policy,_load_source=loadsource,
                  source_total=lambda o:o['grand_total'],source_paid=lambda o:o['paid'],_receipt_line_targets=targets)
    res=await plan.reschedule_line('PLAN',1,50,'2026-12-01')
    second=next(x for x in res['lines'] if x['label']=='Second')
    h.record('V3-08','defect',{'original_second_paid':100,'new_second_paid':second['paid_amount'],'new_second_seq':second['seq'],
                            'targeted_payment_seq':2},second['paid_amount']==50,
             'Insert rescheduled remainder renumbers original second line to3 while receipt still targets seq2; original second becomes unpaid by50.')

    # Consolidation scope: impacts from B/C should not affect standalone A scope.
    db=h.DB(business_entities=[{'id':'A'}],intercompany_eliminations=[{'id':'E','entity_from':'B','entity_to':'C','effective_date':'2026-01-01',
                                                                 'impact':{'assets':-30,'liabilities':-30}}]);h.setup(db)
    async def erow(*a):return {'entity_id':'A','assets':100,'liabilities':0,'equity':100,'revenue':0}
    cons=h.module('backend/services/consolidation_service.py',['_blank','_pnl_derive','_aggregate_impacts','_applicable_eliminations','summary'],db,
                  sync_ic_eliminations_from_pairs=h.nop,_entity_row=erow)
    res=await cons.summary(['A'],2026,'2026-09-29')
    h.record('V3-09','defect',{'scope':['A'],'foreign_elimination':['B','C'],'assets':res['consolidated']['assets'],'balanced':res['balanced']},
             res['consolidated']['assets']==70 and res['balanced'],
             'All eliminations are applied regardless consolidation entity scope; report can remain balanced while wrong.')

    # Integrity check does not compare current content with signed hash.
    db=h.DB(document_signatures=[{'id':'S','verification_code':'CODE','status':'signed','doc_type':'invoice','source_id':'INV','entity_id':'A',
                                 'doc_hash':'OLD_HASH','signer_name':'Signer','signed_at':'2026-01-01'}],invoices=[{'id':'INV','number':'INV-1','grand_total':999}]);h.setup(db)
    es=h.module('backend/services/esign_service.py',['public_verify','doc_number'],db,DOC_REGISTRY={'invoice':{'collection':'invoices','label':'Invoice'}},
                public_base=lambda:'https://example.invalid')
    res=await es.public_verify('CODE')
    h.record('V3-10','defect',{'stored_hash':res['doc_hash'],'current_document_amount':999,'valid':res['valid']},res['valid'],
             'Public verification asserts valid from signature existence without recomputing current document hash; changed content cannot be detected here.')

    pdf=h.module('backend/services/pdf_service.py',['_attach_esign'],db,qr_data_url=lambda x:x)
    rendered=await pdf._attach_esign({'grand_total':999},'invoice','INV','https://example.invalid')
    h.record('V3-12','defect',{'new_document_amount':rendered['grand_total'],'signature_attached':bool(rendered.get('esign'))},
             bool(rendered.get('esign')),'PDF attachment reuses signed metadata for changed document without matching its hash; complements V3-10.')

    # Delivery of one shipment completes parent special order despite another in transit.
    db=h.DB(special_orders=[{'id':'OD','status':'shipped','sales_order_id':'SO'}],
            deliveries=[{'id':'D1','order_id':'SO','status':'delivered'},{'id':'D2','order_id':'SO','status':'in_transit'}]);h.setup(db)
    so=h.module('backend/services/special_order_service.py',['transition_special_order_status'],db,
                STATUS_CONFIRMED='confirmed',STATUS_IN_PRODUCTION='in_production',STATUS_READY='ready',STATUS_SHIPPED='shipped',STATUS_DONE='done')
    h.stub('special_order_service',transition_special_order_status=so.transition_special_order_status)
    async def od_of_so(*a):return await db.special_orders.find_one({'id':'OD'})
    phase=h.module('backend/services/special_order_phase2.py',['on_delivered'],db,_od_of_so=od_of_so)
    await phase.on_delivered('SO')
    h.record('V3-13','defect',{'parent_status':db.special_orders.rows[0]['status'],'other_delivery_status':db.deliveries.rows[1]['status']},
             db.special_orders.rows[0]['status']=='done','Parent special order becomes done on first delivery callback without checking other deliveries. Parent transition has CAS but no completeness invariant.')

    # Credit note pricing keyed by product collapses two legitimate SO lines.
    db=h.DB(sales_orders=[{'id':'SO','grand_total':300,'ppn_amount':0,'items':[{'product_id':'P','quantity':10,'line_total':100},
                                                                       {'product_id':'P','quantity':10,'line_total':200}]}],sales_returns=[{'id':'RET'}]);h.setup(db)
    h.stub('doc_refs_service',safe_link=h.nop)
    async def avg(*a):return 5
    ret=h.module('backend/services/return_service.py',['_create_credit_note_and_post_gl'],db,
                 gl_service=types.SimpleNamespace(_avg_unit_cost=avg,post_sales_return=posted),next_credit_note_number=h.number,
                 order_payment_method=lambda o:'credit',NON_AR_METHODS={'cash'},_log=__import__('logging').getLogger('review3'))
    res=await ret._create_credit_note_and_post_gl({'id':'RET','order_id':'SO','entity_id':'A','items':[{'product_id':'P','quantity_returned':20}]})
    h.record('V3-11','defect',{'original_net':300,'full_return_net':res['net_amount']},res['net_amount']==400,
             'Full return of same product sold on two lines10@10 and10@20 refunds20@20=400 instead of300; pricing map last product line wins.')

if __name__=='__main__':
    asyncio.run(run())
    out={'method':'Original AST function bodies, bounded query dependency model, synthetic fixtures; no Mongo/HTTP/browser/production.', 'results':h.RESULTS}
    Path(__file__).with_suffix('.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
