"""Original ASGI/service financial chains, isolated UUID Mongo; no application fixes.

Faults wrap only a boundary between original writes; normal producers and GL remain
original. The return-transfer fixture starts at an explicitly released return roll,
not at the preceding SO/return approval producer. It is not whole-return-flow proof.
"""
import asyncio, json, traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
import wave2_env as e
from services import finance_case_service as cases, finance_case_actions as acts
from services import store_credit_service as sc, ar_receipt_service as ar
from services import gl_service as gl, roll_service as rolls, finance_case_scan as scan
from core_utils import now_iso

RESULTS=[]; CONTEXT={}; ERRORS=[]
def rec(key, expected, actual, note=''):
    RESULTS.append(dict(id=key, expected=expected, actual=actual, note=note,
        status='pass' if expected == actual else 'observed_difference'))

async def entries_after(ids):
    return await e.db.journal_entries.find({'id':{'$nin':list(ids)},'status':{'$ne':'void'}},{'_id':0}).to_list(None)
async def entry_ids():
    return {x['id'] async for x in e.db.journal_entries.find({}, {'id':1})}
def net(entries, code):
    return round(sum(float(l.get('credit') or 0)-float(l.get('debit') or 0)
        for x in entries for l in x.get('lines',[]) if l.get('account_code')==code),2)
async def refund_case(h,cust):
    r=await h.post('/api/finance-cases',json={'case_type':'refund_pelanggan','entity_id':'A',
        'amount':80,'customer_id':cust,'title':'Audit refund '+cust})
    assert r.status_code==200, (r.status_code,r.text)
    return r.json()
async def resolve(h, case, action):
    return await h.post('/api/finance-cases/'+case['id']+'/resolve',json={
        'action':action,'reason_code':'customer_refund_request','amount':80,
        'customer_id':case['customer_id'],'note':'Synthetic local audit','cash_type':'kas_besar'})
async def cash_out(case):
    return round(sum([float(x.get('amount') or 0) async for x in e.db.cash_transactions.find(
        {'ref_id':case['id'],'direction':'out','status':{'$ne':'void'}})]),2)
async def customer(cust):
    await e.db.customers.insert_one({'id':cust,'entity_id':'A','name':'Audit '+cust,
        'status':'active','deposit_balance':0})
async def producer_deposit(cust,actor):
    await customer(cust)
    r=await ar.create_receipt({'customer_id':cust,'entity_id':'A','amount':100,
        'method':'transfer','notes':'Unallocated original receipt producer'},actor)
    assert r['unapplied_amount']==100 and await ar.get_deposit_balance(cust)==100, r
    return r

async def test_store_credit(h,actor):
    await customer('CSC'); await sc.adjust(customer_id='CSC',entity_id='A',amount_signed=100,
        note='Original permitted adjustment producer',actor=actor)
    before=await entry_ids(); case=await refund_case(h,'CSC'); r=await resolve(h,case,'refund_store_credit')
    after=await entries_after(before)
    rec('D4-CASE-01-public-resolution-control',200,r.status_code)
    rec('D4-CASE-01-ledger-control',20,await sc.balance('CSC','A'))
    rec('D4-CASE-01-liability-debit',80,-net(after,gl.ACC_STORE_CREDIT),
        'Refund80 should debit the liability once. Original manual adjustment and original cash posting each debit80.')
    rec('D4-CASE-01-phantom-income',0,net(after,gl.ACC_PENDAPATAN_LAIN),
        'Paying cash is not forfeiture of customer credit; refund should not create Other Income.')
    all_sc=await e.db.journal_entries.find({'entity_id':'A','lines.account_code':gl.ACC_STORE_CREDIT,
        'status':{'$ne':'void'}},{'_id':0}).to_list(None)
    rec('D4-CASE-01-liability-ledger-reconciliation',20,net(all_sc,gl.ACC_STORE_CREDIT))
    CONTEXT['store_credit']={'case':case,'response':r.json(),'delta_journals':after}

async def test_deposit(h,actor):
    for cust in ['CNORMAL','CRACE','CFAULT']:
        await producer_deposit(cust,actor)
    normal=await refund_case(h,'CNORMAL'); before=await entry_ids()
    r=await resolve(h,normal,'refund_pelanggan'); delta=await entries_after(before)
    rec('D4-CASE-02-normal-refund-control',{'http':200,'deposit':20,'cash':80,'liability_debit':80},
        {'http':r.status_code,'deposit':await ar.get_deposit_balance('CNORMAL'),
         'cash':await cash_out(normal),'liability_debit':-net(delta,gl.ACC_UANG_MUKA_PELANGGAN)},
        'Normal original producer then one refund is correct; wrong-account hypothesis rejected.')
    case=await refund_case(h,'CRACE'); original=acts._cash_txn; arrived=0; ready=asyncio.Event()
    async def barrier(**kw):
        nonlocal arrived
        if kw.get('ref_id')==case['id']:
            arrived+=1
            if arrived==2:ready.set()
            await asyncio.wait_for(ready.wait(),timeout=15)
        return await original(**kw)
    acts._cash_txn=barrier
    try: replies=await asyncio.gather(resolve(h,case,'refund_pelanggan'),resolve(h,case,'refund_pelanggan'))
    finally:acts._cash_txn=original
    rec('D4-CASE-02-concurrent-cash',80,await cash_out(case),
        'Two original public resolutions read deposit100 before cash creation. CAS prevents a negative deposit, but both cash80 and both GL journals already exist.')
    rec('D4-CASE-02-concurrent-deposit-control',20,await ar.get_deposit_balance('CRACE'))
    rec('D4-CASE-02-concurrent-http-control',[200,400],sorted(r.status_code for r in replies),
        'Original executor translates the balance CAS409 into CaseActionError and the router returns400. One request is rejected, but its cash is already committed.')
    CONTEXT['deposit_race']={'case':case,'responses':[{'http':r.status_code,'body':r.json()} for r in replies],
        'transactions':await e.db.cash_transactions.find({'ref_id':case['id']},{'_id':0}).to_list(None)}
    case=await refund_case(h,'CFAULT'); original_adjust=ar.adjust_deposit
    async def once_fail(cust,delta):
        if cust=='CFAULT':raise RuntimeError('AUDIT injected disconnect after original cash+JE, before deposit CAS')
        return await original_adjust(cust,delta)
    ar.adjust_deposit=once_fail
    try:first=await resolve(h,case,'refund_pelanggan')
    finally:ar.adjust_deposit=original_adjust
    # The original router maps exceptions to400; a normal user may retry an open case.
    retry=await resolve(h,case,'refund_pelanggan')
    rec('D4-CASE-02-failure-retry-cash',80,await cash_out(case),
        'Original first cash+JE survives a failed deposit step; same case retry creates a new cash UUID instead of resuming the existing action.')
    rec('D4-CASE-02-failure-retry-deposit-control',20,await ar.get_deposit_balance('CFAULT'))
    CONTEXT['deposit_fault']={'case':case,'http':[first.status_code,retry.status_code],
        'first_body':first.json(),'retry_body':retry.json(),
        'transactions':await e.db.cash_transactions.find({'ref_id':case['id']},{'_id':0}).to_list(None)}

async def test_intercompany(h):
    await e.db.products.insert_one({'id':'PTRANSFER','name':'Audit return fabric','base_unit':'meter',
        'harga_pokok':10,'product_type':'finished_good','status':'active'})
    await e.db.warehouses.insert_one({'id':'WH','name':'Audit WH','entity_id':'A','status':'active'})
    control_rid='RET-CONTROL'
    await e.db.sales_returns.insert_one({'id':control_rid,'number':'RET-CONTROL-001','entity_id':'A',
        'status':'credit_settled','items':[],'created_at':now_iso(),'updated_at':now_iso()})
    cr=await rolls.create_inbound_roll('PTRANSFER','WH','A',10,unit_cost=10,lot='AUDIT-CONTROL',
        acquired_via='sales_return',ref_id=control_rid)
    await e.db.inventory_rolls.update_one({'id':cr['id']},{'$set':{
        'origin_type':'return','return_id':control_rid,'origin_ref':control_rid}})
    control=await h.post(f'/api/sales-returns/{control_rid}/rolls/{cr["id"]}/transfer-ownership',
        json={'dest_entity_id':'B','notes':'Normal control'})
    rec('D4-INTERCO-01-normal-control',{'http':200,'je_posted':True,'owner':'B'},
        {'http':control.status_code,'je_posted':control.json().get('je',{}).get('posted'),
         'owner':(await e.db.inventory_rolls.find_one({'id':cr['id']}))['owner_entity_id']})
    # Original inbound-roll writer establishes valid SSOT, lot and movements. Additional
    # return lifecycle metadata is an explicit state fixture (no approval-flow claim).
    hold=await rolls.create_inbound_roll('PTRANSFER','WH','A',10,unit_cost=10,lot='AUDIT-HOLD')
    rid='RET-AUDIT'; await e.db.sales_returns.insert_one({'id':rid,'number':'RET-AUDIT-001',
        'entity_id':'A','status':'credit_settled','order_id':'SO-RETURN-FIXTURE','items':[],
        'created_at':now_iso(),'updated_at':now_iso()})
    rr=await rolls.create_inbound_roll('PTRANSFER','WH','A',10,unit_cost=10,lot='AUDIT-RETURN',
        acquired_via='sales_return',ref_id=rid)
    await e.db.inventory_rolls.update_one({'id':rr['id']},{'$set':{'origin_type':'return','return_id':rid,'origin_ref':rid}})
    await e.db.rfid_tags.insert_one({'id':'TAG-AUDIT','roll_id':rr['id'],'status':'active',
        'epc':'300000000000000000000001','product_id':'PTRANSFER','owner_entity_id':'A'})
    await e.db.inventory_rolls.update_one({'id':rr['id']},{'$set':{'rfid_tag_id':'TAG-AUDIT','tracking_mode':'rfid'}})
    original=gl._insert_entry; captured={}
    async def fail_destination(**kw):
        if kw.get('source_type')=='inter_company_transfer' and kw.get('source_id','').endswith(':dst'):
            captured['tid']=kw['source_id'][:-4]
            raise RuntimeError('AUDIT injected destination JE insertion failure')
        return await original(**kw)
    path=f'/api/sales-returns/{rid}/rolls/{rr["id"]}/transfer-ownership'
    gl._insert_entry=fail_destination
    try:first=await h.post(path,json={'dest_entity_id':'B','notes':'Synthetic audit'})
    finally:gl._insert_entry=original
    assert 'tid' in captured,(first.status_code,first.text)
    tid=captured['tid']; moved=await e.db.inventory_rolls.find_one({'id':rr['id']},{'_id':0})
    rec('D4-INTERCO-01-owner-after-failed-transfer','A',moved['owner_entity_id'],
        'Original physical ownership, lot, RFID owner and balance move before both journals succeed; rollback filters the cleared reserved_ref and does not restore ownership.')
    rec('D4-INTERCO-01-transfer-history-after-failure',1,
        await e.db.warehouse_transfers.count_documents({'id':tid}),
        'Once ownership is committed, recovery needs a durable transfer document; current path inserts it only after both journals.')
    tag=await e.db.rfid_tags.find_one({'id':'TAG-AUDIT'},{'_id':0})
    rec('D4-INTERCO-01-rfid-owner-after-failure','A',tag['owner_entity_id'])
    jes=await e.db.journal_entries.find({'source_type':'inter_company_transfer',
        'source_id':{'$in':[tid+':src',tid+':dst']}},{'_id':0}).to_list(None)
    rec('D4-INTERCO-01-journal-pair-after-failure',['A','B'],sorted(j['entity_id'] for j in jes))
    # Invoke the original retry helper with the same transfer ID to prove the OR guard.
    retry_helper=await gl.post_intercompany_transfer({'id':tid,'source_entity_id':'A','dest_entity_id':'B',
        'code':'RTNX-AUDIT','items':[{'product_id':'PTRANSFER','qty':10}]})
    rec('D4-INTERCO-01-helper-recovery-pair',2,await e.db.journal_entries.count_documents(
        {'source_type':'inter_company_transfer','source_id':{'$in':[tid+':src',tid+':dst']}}),
        'The presence of just source JE causes already_posted, so retry does not create missing destination JE.')
    retry_api=await h.post(path,json={'dest_entity_id':'B','notes':'Retry same request'})
    rec('D4-INTERCO-01-public-recovery',200,retry_api.status_code,
        'Same original API retry rejects destination==current owner; no supported recovery is reached.')
    CONTEXT['intercompany_fault']={'fixture_scope':'Released external-sales-return roll; preceding return/SO producer not executed',
        'roll':rr,'unchanged_cost_control_roll':hold['id'],'transfer_id':tid,'first_http':first.status_code,
        'retry_http':retry_api.status_code,'retry_body':retry_api.json(),'retry_helper':retry_helper,
        'roll_after':moved,'tag_after':tag,'journals':jes}

async def test_transfer_valuation(h):
    from services.costing_service import wac_for_product
    contexts=[]
    for mode in ['empty_source','cheaper_remainder']:
        pid='PCOST-'+mode;rid='RET-COST-'+mode
        await e.db.products.insert_one({'id':pid,'name':'Cost snapshot '+mode,
            'base_unit':'meter','harga_pokok':1,'status':'active'})
        await e.db.sales_returns.insert_one({'id':rid,'number':'RET-COST-'+mode,'entity_id':'A',
            'status':'credit_settled','items':[],'created_at':now_iso(),'updated_at':now_iso()})
        if mode=='cheaper_remainder':
            await rolls.create_inbound_roll(pid,'WH','A',10,unit_cost=5,lot='AUDIT-COST-KEEP')
        rr=await rolls.create_inbound_roll(pid,'WH','A',10,unit_cost=15,lot='AUDIT-COST-MOVE',
            acquired_via='sales_return',ref_id=rid)
        await e.db.inventory_rolls.update_one({'id':rr['id']},{'$set':{
            'origin_type':'return','return_id':rid,'origin_ref':rid}})
        pre=await wac_for_product(pid,entity_id='A',use_cache=False)
        resp=await h.post(f'/api/sales-returns/{rid}/rolls/{rr["id"]}/transfer-ownership',
            json={'dest_entity_id':'B','notes':'Normal valuation probe'})
        body=resp.json();expected=round(10*pre['wac'],2)
        rec('D4-INTERCO-02-'+mode+'-valuation',expected,body.get('je',{}).get('total'),
            'The original helper promises source WAC at-cost; it recalculates AFTER the chosen roll leaves the source. Empty source falls back to stale master1, or cheaper remainder changes WAC to5.')
        rec('D4-INTERCO-02-'+mode+'-http-control',200,resp.status_code)
        dest=await e.db.inventory_rolls.find_one({'id':rr['id']},{'_id':0})
        rec('D4-INTERCO-02-'+mode+'-retained-roll-cost-control',15,dest['unit_cost'])
        contexts.append({'mode':mode,'pre_source_wac':pre,'original_transfer_response':body,
            'physical_transferred_roll_value':round(dest['length_remaining']*dest['unit_cost'],2),
            'policy_note':'Pre-source WAC is the function-documented baseline. Cost-per-roll SSOT is150; the mixed-cost case additionally needs an explicit choice of valuation policy.'})
    CONTEXT['transfer_valuation']=contexts

async def test_book_transfer(h):
    for aid in ['BANK1','BANK2']:
        await e.db.bank_accounts.insert_one({'id':aid,'name':aid,'entity_id':'A','status':'active',
            'account_code':'1-1110'})
    r=await h.post('/api/finance-cases',json={'case_type':'salah_rekening_internal','entity_id':'A',
        'amount':80,'title':'Audit own-bank transfer'})
    assert r.status_code==200,(r.status_code,r.text)
    case=r.json();original=acts._cash_txn
    async def fail_second(**kw):
        if kw.get('ref_id')==case['id'] and kw.get('direction')=='in':
            raise RuntimeError('AUDIT second bank leg unavailable after original first-leg cash and GL')
        return await original(**kw)
    payload={'action':'pindah_buku','reason_code':'case_wrong_account','amount':80,
        'account_id':'BANK1','to_account_id':'BANK2','note':'Local synthetic transfer'}
    endpoint='/api/finance-cases/'+case['id']+'/resolve';acts._cash_txn=fail_second
    try:first=await h.post(endpoint,json=payload)
    finally:acts._cash_txn=original
    retry=await h.post(endpoint,json=payload)
    txns=await e.db.cash_transactions.find({'ref_id':case['id']},{'_id':0}).to_list(None)
    direction_totals={d:round(sum(t['amount'] for t in txns if t['direction']==d),2) for d in ['in','out']}
    jes=await e.db.journal_entries.find({'source_type':'cash_transaction',
        'source_id':{'$in':[t['id'] for t in txns]}},{'_id':0}).to_list(None)
    rec('D4-CASE-02-bank-transfer-retry-total',{'in':80,'out':80},direction_totals,
        'Same unresolved case retry repeats the succeeded first leg: original out80, retry out80 and in80; the resolved case has an extra cash out80.')
    rec('D4-CASE-02-bank-transfer-transit',0,-net(jes,gl.ACC_KAS_TRANSIT),
        'A completed own-bank transfer should clear transit; current resolved case leaves debit80.')
    CONTEXT['book_transfer']={'case':case,'http':[first.status_code,retry.status_code],
        'response':retry.json(),'cash_transactions':txns,'journals':jes}

async def test_escalation(h):
    case=await refund_case(h,'CNORMAL')
    await e.db[cases.COLL].update_one({'id':case['id']},{'$set':{
        'sla_due_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()}})
    levels=[]; newcases=[]
    for _ in range(3):
        res=await scan.scan('audit scanner'); newcases.append(res['holding_cases']+res['duplicate_cases'])
        fresh=await e.db[cases.COLL].find_one({'id':case['id']},{'_id':0});levels.append(fresh['escalation_level'])
    # Existing receipts above intentionally cause duplicate-payment alerts; only the
    # isolated target case's escalation refs are checked, not all notification growth.
    notifications=await e.db.notifications.find({'ref':{'$in':['esc:'+case['id']+':1','esc:'+case['id']+':2']}},
        {'_id':0}).to_list(None)
    rec('REPLAY-OPS-02-escalation-level-control',[1,2,2],levels,
        'Separate manager then admin escalation is intentional, not duplicate notifications. Third scan no new level.')
    CONTEXT['escalation']={'target_case_id':case['id'],'levels':levels,'notifications':notifications,
        'adjudication':'The replay assertion of no notification growth is too broad for progressive SLA escalation.'}

async def supplier_case(h,sid,amount):
    r=await h.post('/api/finance-cases',json={'case_type':'lebih_bayar_supplier','entity_id':'A',
        'amount':amount,'supplier_id':sid,'title':'Synthetic supplier advance decision '+sid})
    assert r.status_code==200,(r.status_code,r.text)
    return r.json()
async def supplier_resolve(h,case,action,amount):
    return await h.post('/api/finance-cases/'+case['id']+'/resolve',json={'action':action,
        'supplier_id':case['supplier_id'],'amount':amount,'reason_code':'supplier_advance',
        'note':'Explicit manual overpayment decision fixture'})
async def test_supplier_cases(h):
    for sid in ['SADV-RACE','SADV-FAULT']:
        await e.db.suppliers.insert_one({'id':sid,'name':sid,'entity_id':'A','status':'active','advance_balance':0})
    case=await supplier_case(h,'SADV-RACE',100)
    normal=await supplier_resolve(h,case,'uang_muka_supplier',100)
    rec('D4-CASE-02-supplier-producer-control',{'http':200,'advance':100},
        {'http':normal.status_code,'advance':(await e.db.suppliers.find_one({'id':'SADV-RACE'}))['advance_balance']},
        'Original manual approved case action creates supplier advance; preceding vendor-bill/payment producer is not executed in this fixture.')
    case=await supplier_case(h,'SADV-RACE',80);original=acts._cash_txn;arrived=0;ready=asyncio.Event()
    async def barrier(**kw):
        nonlocal arrived
        if kw.get('ref_id')==case['id']:
            arrived+=1
            if arrived==2:ready.set()
            await asyncio.wait_for(ready.wait(),15)
        return await original(**kw)
    acts._cash_txn=barrier
    try:replies=await asyncio.gather(supplier_resolve(h,case,'terima_refund_supplier',80),
                                   supplier_resolve(h,case,'terima_refund_supplier',80))
    finally:acts._cash_txn=original
    cash=await e.db.cash_transactions.find({'ref_id':case['id'],'direction':'in'},{'_id':0}).to_list(None)
    advance=(await e.db.suppliers.find_one({'id':'SADV-RACE'}))['advance_balance']
    rec('D4-CASE-02-supplier-concurrent-cash',80,sum(t['amount'] for t in cash))
    rec('D4-CASE-02-supplier-concurrent-balance',20,advance,
        'Unlike customer deposit, supplier refund uses unconditional $inc after cash; both original requests succeed and supplier advance goes negative.')
    CONTEXT['supplier_refund_race']={'case':case,'http':[r.status_code for r in replies],
        'cash_transactions':cash,'advance_after':advance,'fixture_scope':'Original manual advance decision, not full vendor payment chain'}
    case=await supplier_case(h,'SADV-FAULT',100);original_touch=cases._touch
    async def fail_touch(cid,sets,event):
        if cid==case['id']:raise RuntimeError('AUDIT failure after original supplier-advance GL and balance, before case checkpoint')
        return await original_touch(cid,sets,event)
    cases._touch=fail_touch
    try:first=await supplier_resolve(h,case,'uang_muka_supplier',100)
    finally:cases._touch=original_touch
    retry=await supplier_resolve(h,case,'uang_muka_supplier',100)
    advance=(await e.db.suppliers.find_one({'id':'SADV-FAULT'}))['advance_balance']
    jes=await e.db.journal_entries.find({'source_type':'finance_case','source_id':case['id']+':ap_adv'},
        {'_id':0}).to_list(None)
    rec('D4-CASE-02-supplier-advance-retry-balance',100,advance,
        'Finance-case JE uses stable case ID and skips repost; supplier balance increment still repeats. Stable JE idempotency alone is insufficient.')
    rec('D4-CASE-02-supplier-advance-retry-journal-control',100,-net(jes,gl.ACC_UANG_MUKA))
    CONTEXT['supplier_advance_fault']={'case':case,'http':[first.status_code,retry.status_code],
        'retry_body':retry.json(),'advance_after':advance,'journals':jes}

async def test_closed_period(h,actor):
    from services.closing_service import status_for_date
    await producer_deposit('CCLOSED',actor);case=await refund_case(h,'CCLOSED');before=await entry_ids()
    today=now_iso()[:10]
    # Explicit closed-state fixture, not an end-to-end period-closing producer claim.
    await e.db.period_closings.insert_one({'id':'CLOSED-AUDIT','entity_id':'A','status':'closed',
        'period_type':'month','period_key':today[:7],'period_label':'Synthetic locked period',
        'start_date':today,'end_date':today,'closed_at':now_iso()})
    assert (await status_for_date(today,'A'))['closed']
    resp=await resolve(h,case,'refund_pelanggan');delta=await entries_after(before)
    rec('D4-CASE-02-closed-period-cash',0,await cash_out(case),
        'No injection: a valid locked-period state rejects GL, but the refund cash is already inserted with status posted; deposit is unchanged and case remains open.')
    rec('D4-CASE-02-closed-period-journal-control',0,len(delta))
    rec('D4-CASE-02-closed-period-deposit-control',100,await ar.get_deposit_balance('CCLOSED'))
    CONTEXT['closed_period']={'case':case,'http':resp.status_code,'body':resp.json(),
        'transactions':await e.db.cash_transactions.find({'ref_id':case['id']},{'_id':0}).to_list(None),
        'fixture_scope':'Original receipt before locking; explicit period_closings state, not full closing producer'}

async def employee_case(h,key):
    cust='CEMP-'+key;order='SOEMP-'+key
    await customer(cust)
    await e.db.sales_orders.insert_one({'id':order,'number':order,'entity_id':'A',
        'customer_id':cust,'customer_name':cust,'status':'confirmed','grand_total':100,
        'total_amount':100,'paid_total':0,'payments':[],'items':[],
        'created_at':now_iso(),'updated_at':now_iso()})
    r=await h.post('/api/finance-cases',json={'case_type':'rekening_pribadi_karyawan',
        'entity_id':'A','amount':80,'customer_id':cust,'order_ids':[order],
        'attachments':[{'name':'Synthetic local payment proof','id':'LOCAL-AUDIT-PROOF'}]})
    assert r.status_code==200,(r.status_code,r.text)
    return r.json(),order
async def employee_action(h,case,order,action,amount):
    return await h.post('/api/finance-cases/'+case['id']+'/resolve',json={
        'action':action,'amount':amount,'order_id':order,'employee_name':'Synthetic Employee',
        'reason_code':'case_employee_account','note':'Local documented two-step flow'})
async def employee_debt(case):
    txns=await e.db.cash_transactions.find({'ref_id':case['id']},{'_id':0}).to_list(None)
    jes=await e.db.journal_entries.find({'$or':[
        {'source_type':'finance_case','source_id':case['id']+':emp1'},
        {'source_type':'cash_transaction','source_id':{'$in':[x['id'] for x in txns]}}]},
        {'_id':0}).to_list(None)
    return -net(jes,gl.ACC_PIUTANG_KARYAWAN),txns,jes
async def test_employee_flow(h):
    contexts=[]
    case,order=await employee_case(h,'NORMAL')
    first=await employee_action(h,case,order,'akui_dipegang_karyawan',80)
    second=await employee_action(h,case,order,'setor_dari_karyawan',80)
    debt,txns,jes=await employee_debt(case)
    rec('D4-CASE-03-normal-two-step-control',{'http':[200,200],'state':'resolved','debt':0,'cash_in':80},
        {'http':[first.status_code,second.status_code],'state':second.json().get('status'),
         'debt':debt,'cash_in':sum(x['amount'] for x in txns if x['direction']=='in')})
    case,order=await employee_case(h,'SKIP')
    skipped=await employee_action(h,case,order,'setor_dari_karyawan',80)
    debt,txns,jes=await employee_debt(case)
    rec('D4-CASE-03-skip-step-one-cash',0,sum(x['amount'] for x in txns),
        'Original public action accepts step2 on a newly open case: no step1 liability/AR transfer exists, but cash80 and Cr employee receivable80 are posted.')
    rec('D4-CASE-03-skip-step-one-debt',0,debt)
    contexts.append({'mode':'skip_step_one','case':case,'http':skipped.status_code,
        'response':skipped.json(),'cash':txns,'journals':jes,'employee_receivable':debt})
    for mode,amount in [('PARTIAL',40),('EXCESS',100)]:
        case,order=await employee_case(h,mode)
        first=await employee_action(h,case,order,'akui_dipegang_karyawan',80)
        assert first.status_code==200,(first.status_code,first.text)
        second=await employee_action(h,case,order,'setor_dari_karyawan',amount)
        debt,txns,jes=await employee_debt(case)
        if mode=='PARTIAL':
            rec('D4-CASE-03-partial-remains-open','in_progress',second.json().get('status'),
                'Acknowledged employee receivable80, received40: case must keep an outstanding40 or reject partial; it currently resolves and removes next_action.')
            rec('D4-CASE-03-partial-receivable-control',40,debt)
        else:
            rec('D4-CASE-03-excess-receivable',0,debt,
                'Received100 is applied wholly to an acknowledged debt80, creating negative employee receivable20; no surplus classification or amount bound is applied.')
        contexts.append({'mode':mode,'case':case,'http':second.status_code,'response':second.json(),
            'cash':txns,'journals':jes,'employee_receivable':debt})
    CONTEXT['employee_two_step']={'fixture_scope':'Explicit SO receivable read-state; original case API and payment/GL executors, not full SO producer',
        'scenarios':contexts}

async def main():
    await e.seed();await gl.seed_default_coa();await cases.reasons()
    from indexes import ensure_performance_indexes
    CONTEXT['indexes']=await ensure_performance_indexes()
    CONTEXT['journal_indexes']=await e.db.journal_entries.index_information()
    CONTEXT['cash_indexes']=await e.db.cash_transactions.index_information()
    await e.db.users.update_one({'id':'U'},{'$set':{'role':'admin','allowed_entity_ids':['A','B']}})
    await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{
        'finance_case':['view','create','resolve'],'ar_receipt':['create','view'],'sales_return':['approve','view']}}})
    actor=await e.db.users.find_one({'id':'U'},{'_id':0})
    async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),
        base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
        for name, fn in [('store_credit',lambda:test_store_credit(h,actor)),('deposit',lambda:test_deposit(h,actor)),
                         ('intercompany',lambda:test_intercompany(h)),
                         ('transfer_valuation',lambda:test_transfer_valuation(h)),
                         ('book_transfer',lambda:test_book_transfer(h)),
                         ('supplier_cases',lambda:test_supplier_cases(h)),('employee_flow',lambda:test_employee_flow(h)),
                         ('escalation',lambda:test_escalation(h)),('closed_period',lambda:test_closed_period(h,actor))]:
            try:await fn()
            except Exception:ERRORS.append({'test':name,'traceback':traceback.format_exc()})
    output={'commit':'a904d989b622f7da14c4892d03cf6ef0c43f3084','database':e.db.name,
        'results':RESULTS,'contexts':CONTEXT,'harness_errors':ERRORS,'external_connections':e.blocked}
    Path(__file__).with_name('continuation-finance-results.json').write_text(
        json.dumps(output,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'results':RESULTS,'harness_errors':ERRORS},ensure_ascii=False))
    assert not ERRORS, ERRORS
asyncio.run(main())
