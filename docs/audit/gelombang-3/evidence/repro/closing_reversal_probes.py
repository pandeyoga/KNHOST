"""Original public manual-journal/closing lifecycles; localhost UUID DB only.

Normal controls and fault boundaries are separate. Reclose fault is an injected
lost acknowledgement after the original JE insert. The lock clock is then aged
explicitly to exercise the original admin recovery without waiting 30 minutes.
No application implementation or assertion is changed.
"""
import asyncio,json,traceback,math
from datetime import datetime,timezone,timedelta
from pathlib import Path
import wave2_env as e
from services import gl_service as gl,financial_statement_service as fs

RESULTS=[];CONTEXT={};ERRORS=[]
def rec(key,expected,actual,note=''):
    RESULTS.append(dict(id=key,expected=expected,actual=actual,note=note,
        status='pass' if expected==actual else 'observed_difference'))
def response(r):
    try:body=r.json()
    except Exception:body=r.text[:1000]
    return {'http':r.status_code,'body':body}
async def manual(h,date,amount,note,revenue=True):
    dr,cr=('1-1100','4-1000') if revenue else ('6-4000','1-1100')
    r=await h.post('/api/gl/journal',json={'date':date+'T12:00:00+00:00',
        'description':'Synthetic audit '+note,'lines':[
            {'account_code':dr,'debit':amount,'credit':0},
            {'account_code':cr,'debit':0,'credit':amount}]})
    assert r.status_code==200,(r.status_code,r.text)
    return r.json()
async def close(h,typ,key):
    r=await h.post('/api/finance/closing/close',json={'period_type':typ,'period_key':key,'note':'Synthetic audit'})
    assert r.status_code==200,(r.status_code,r.text)
    return r.json()
async def stmt(start,end,eid='A'):
    return await fs.income_statement(start=start,end=end,scope={'entity_id':eid})

async def nested_closing(h):
    je=await manual(h,'2024-01-15',100,'nested closing')
    params={'start':'2024-01-01','end':'2024-12-31'}
    eq_before=await h.get('/api/finance/equity-changes',params=params)
    assert eq_before.status_code==200,eq_before.text
    rec('D4-EQ-01-open-period-income-control',100,eq_before.json()['net_income'])
    month=await close(h,'month','2024-01');year=await close(h,'year','2024')
    eq_after=await h.get('/api/finance/equity-changes',params=params)
    assert eq_after.status_code==200,eq_after.text
    rec('D4-EQ-01-closed-period-net-income',100,eq_after.json()['net_income'],
        'Same operational profit100 before/after closing; equity API uses the change in unclosed earnings and the actual UI labels it Laba Periode Berjalan. Closing transfers100 to retained earnings and incorrectly turns the profit KPI to0.')
    rec('D4-EQ-01-total-equity-movement-control',100,eq_after.json()['movement_total'],
        'The equity roll-forward remains reconciled. Only the net_income definition/label is wrong; do not count the correct retained-earnings transfer twice when fixing.')
    rec('D4-EQ-01-operating-profit-control',100,(await stmt('2024-01-01','2024-12-31'))['net_income'])
    CONTEXT['equity_metric']={'before_close':eq_before.json(),'after_close':eq_after.json(),
        'intended_UI_label':'Laba Periode Berjalan','scope':'Actual original API and source consumer, DOM not verified'}
    rec('D4-CLOSE-01-nested-producer-control',{'month':100,'year':0},
        {'month':month['residual_net_income'],'year':year['residual_net_income']})
    before=await fs.balance_sheet('2024-12-31',scope={'entity_id':'A'})
    rec('D4-CLOSE-01-before-reopen-control',0,before['equity']['current_earnings'])
    r=await h.post('/api/finance/closing/'+month['id']+'/reopen')
    assert r.status_code==200,(r.status_code,r.text)
    current=await e.db.period_closings.find_one({'id':year['id']},{'_id':0})
    preview=await h.get('/api/finance/closing/preview',params={'period_type':'year','period_key':'2024'})
    assert preview.status_code==200,preview.text
    after=await fs.balance_sheet('2024-12-31',scope={'entity_id':'A'})
    rec('D4-CLOSE-01-parent-stale',True,current.get('stale'),
        'Reopening January removes its closing100. The annual closing depended on that100, but still says closed/stale=False. Original UI only offers Tutup Ulang when stale is true.')
    rec('D4-CLOSE-01-parent-residual-control',100,preview.json()['residual_net_income'])
    rec('D4-CLOSE-01-post-reopen-operating-income-control',100,(await stmt('2024-01-01','2024-12-31'))['net_income'],
        'Operational P&L and balance arithmetic remain correct; finding is invalidated annual close status, not a claim that the balanced equation fails.')
    rec('D4-CLOSE-01-post-reopen-unclosed-income-control',100,after['equity']['current_earnings'],
        'Reopening the child correctly restores unclosed profit100. The defect is the parent still declaring a final/non-stale close, not this balance calculation.')
    CONTEXT['nested']={'manual':je,'month':month,'year':year,'reopen':response(r),
        'parent_after':current,'preview_after':preview.json(),'balance_after':after,
        'UI_guard':'c.status === closed && c.stale && canReclose'}
    # Direct API workaround is available although UI does not offer it.
    workaround=await h.post('/api/finance/closing/'+year['id']+'/reclose')
    rec('D4-CLOSE-01-direct-reclose-workaround-control',200,workaround.status_code)
    CONTEXT['nested']['direct_api_workaround']=response(workaround)

async def reclose_recovery(h):
    await manual(h,'2025-02-15',100,'initial February')
    c=await close(h,'month','2025-02')
    proposal=await h.post('/api/finance/period-unlocks',json={'period_type':'month',
        'period_key':'2025-02','reason':'Synthetic authorized correction audit'})
    assert proposal.status_code==200,(proposal.status_code,proposal.text)
    approved=await h.post('/api/finance/period-unlocks/'+proposal.json()['id']+'/approve',
        headers={'Authorization':'Bearer audit-second-session'})
    assert approved.status_code==200,(approved.status_code,approved.text)
    correction=await manual(h,'2025-02-20',20,'correction after dual-control unlock')
    assert correction.get('backdated_in_unlock')==proposal.json()['id']
    # Normal original reclose is a control; it also validates all prerequisites.
    normal=await h.post('/api/finance/closing/'+c['id']+'/reclose')
    assert normal.status_code==200,(normal.status_code,normal.text)
    c=normal.json()
    rec('D4-CLOSE-02-normal-reclose-control',{'net':120,'stale':False},
        {'net':c['net_income'],'stale':c['stale']})
    correction2=await manual(h,'2025-02-21',10,'second authorized correction')
    original=gl._insert_entry;created=[]
    async def lost_ack(**kwargs):
        result=await original(**kwargs)
        if kwargs.get('source_type')=='closing' and kwargs.get('source_id')==c['id']:
            created.append(result)
            raise RuntimeError('AUDIT injected lost acknowledgement after original closing JE durable insert')
        return result
    gl._insert_entry=lost_ack
    try:first=await h.post('/api/finance/closing/'+c['id']+'/reclose')
    finally:gl._insert_entry=original
    assert created,'fault boundary not reached'
    damaged=await e.db.period_closings.find_one({'id':c['id']},{'_id':0})
    old=await e.db.journal_entries.find_one({'id':damaged['journal_entry_id']},{'_id':0})
    active=await e.db.journal_entries.find({'source_type':'closing','source_id':c['id'],
        'status':{'$ne':'void'}},{'_id':0}).to_list(None)
    rec('D4-CLOSE-02-linked-journal-posted','posted',old['status'],
        'Original new JE130 is active, but the parent still points to the void old JE120 and old net_income120 after acknowledgement failure.')
    rec('D4-CLOSE-02-active-journal-control',{'count':1,'total':130},
        {'count':len(active),'total':active[0]['total_debit']})
    rec('D4-CLOSE-02-parent-net-income',130,damaged['net_income'])
    immediate=await h.post('/api/finance/closing/'+c['id']+'/reclose')
    rec('D4-CLOSE-02-immediate-lock-control',409,immediate.status_code,
        'A visible saga lock intentionally blocks concurrent replay; that block alone is not labelled a defect.')
    # Explicit clock fixture only, equivalent to waiting beyond original 30m guard.
    await e.db.period_closings.update_one({'id':c['id']},{'$set':{
        'saga_lock.started_at':(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()}})
    released=await h.post('/api/saga-locks/period_closings/'+c['id']+'/release',json={
        'reason':'Synthetic audit recovery after inspecting existing journal effects',
        'acknowledge_effects':True,'lock_token':damaged['saga_lock']['token']})
    rec('D4-CLOSE-02-admin-release-control',200,released.status_code)
    assert released.status_code==200,(released.status_code,released.text)
    retry_error={}
    async def observe_retry(**kwargs):
        try:return await original(**kwargs)
        except Exception as exc:
            retry_error.update(type=type(exc).__name__,message=str(exc),source_type=kwargs.get('source_type'),source_id=kwargs.get('source_id'))
            raise
    gl._insert_entry=observe_retry
    try:retry=await h.post('/api/finance/closing/'+c['id']+'/reclose')
    finally:gl._insert_entry=original
    assert retry_error.get('type')=='DuplicateKeyError' and 'uq_je_source_active' in retry_error.get('message',''),retry_error
    rec('D4-CLOSE-02-original-recovery-retry',200,retry.status_code,
        'After original admin release, retry tries to insert another active JE with the stable closing source_id. Original unique index rejects it; existing JE is not adopted and parent remains stale/locked.')
    final=await e.db.period_closings.find_one({'id':c['id']},{'_id':0})
    rec('D4-CLOSE-02-recovery-linked-existing',created[0]['id'],final['journal_entry_id'])
    CONTEXT['reclose']={'initial':c,'unlock':proposal.json(),'approved':approved.json(),
        'correction2':correction2,'first':response(first),'immediate':response(immediate),
        'damaged_parent':damaged,'void_old_je':old,'active_new_jes':active,
        'clock_fixture':'Only saga_lock.started_at aged by two hours, before original admin release',
        'release':response(released),'retry':response(retry),'original_retry_exception':retry_error,'final_parent':final}

async def reversal_then_void(h):
    first=await manual(h,'2026-08-01',100,'ordinary void control',False)
    void=await h.post('/api/gl/journal/'+first['id']+'/void')
    rec('D4-GL-01-ordinary-void-control',{'http':200,'income':0},
        {'http':void.status_code,'income':(await stmt('2026-08-01','2026-08-31'))['net_income']})
    second=await manual(h,'2026-08-02',100,'reversal then void',False)
    reverse=await h.post('/api/gl/journal/'+second['id']+'/reverse',json={
        'date':'2026-08-03','reason':'Synthetic ordinary reversal'})
    assert reverse.status_code==200,(reverse.status_code,reverse.text)
    rec('D4-GL-01-single-reversal-control',0,(await stmt('2026-08-01','2026-08-31'))['net_income'])
    void=await h.post('/api/gl/journal/'+second['id']+'/void')
    rec('D4-GL-01-second-cancellation-rejected',True,400<=void.status_code<500,
        'Original public void still accepts a journal already reversed. Original UI still exposes Anulir Jurnal for manual/posted regardless of reversed_by_entry_id.')
    after=await stmt('2026-08-01','2026-08-31')
    rec('D4-GL-01-post-reversal-void-income',0,after['net_income'],
        'Original expense100 and reversal initially net0. Voiding only the original leaves standalone credit expense100, reporting a profit100 after double cancellation.')
    CONTEXT['reversal_void']={'original':second,'reversal':response(reverse),
        'void':response(void),'income_statement_after':after}

async def finite_manual(h):
    hb={'X-Entity-Id':'B'}
    valid=await h.post('/api/gl/journal',headers=hb,json={'date':'2026-09-01T12:00:00+00:00',
        'description':'Synthetic valid expense before non-finite input','lines':[
            {'account_code':'6-4000','debit':50,'credit':0},
            {'account_code':'1-1100','debit':0,'credit':50}]})
    assert valid.status_code==200,(valid.status_code,valid.text)
    before=await h.get('/api/gl/summary',headers=hb)
    rec('D4-GL-02-healthy-summary-control',{'http':200,'debit':50},
        {'http':before.status_code,'debit':before.json()['total_debit']})
    scenarios=[]
    for token in ['NaN','Infinity']:
        note='Synthetic non-finite manual '+token
        r=await h.post('/api/gl/journal',headers=hb,json={'date':'2026-09-01T12:00:00+00:00',
            'description':note,'lines':[
                {'account_code':'6-4000','debit':token,'credit':0},
                {'account_code':'1-1100','debit':0,'credit':token}]})
        bad=await e.db.journal_entries.find({'description':note},{'_id':0}).to_list(None)
        rec('D4-GL-02-'+token.lower()+'-persisted',0,len(bad),
            'JSON string is valid JSON; original Pydantic float coercion accepts it. Manual path bypasses _validate_entry_lines, persists non-finite double values, and returns200 with amounts sanitized to null.')
        assert bad and not math.isfinite(bad[0]['lines'][0]['debit']),bad
        rec('D4-GL-02-'+token.lower()+'-validation',True,400<=r.status_code<500)
        scenarios.append({'token':token,'response':response(r),'persisted':bad})
    after=await h.get('/api/gl/summary',headers=hb)
    rec('D4-GL-02-summary-valid-amount-retained',50,after.json()['total_debit'],
        'The summary still returns200/balanced=True, but the poisoned accounts are omitted and even the legitimate expense50 disappears from the totals. No500/serialization-crash hypothesis is claimed.')
    pl=await h.get('/api/finance/income-statement',headers=hb,params={'start':'2026-09-01','end':'2026-09-30'})
    assert pl.status_code==200,(pl.status_code,pl.text)
    rec('D4-GL-02-income-valid-expense-retained',50,pl.json()['opex_total'])
    CONTEXT['non_finite']={'fixture_scope':'Invalid numeric requests by authorized admin, valid JSON strings; no legitimate browser input path assumed',
        'healthy_summary':response(before),'scenarios':scenarios,'summary_after':response(after),
        'income_statement_after':response(pl),'raw_DB_type':'Non-finite native Mongo/Python double; artifact replaces them with explicit non_finite tags for valid JSON'}

async def entity_account_dimension(h):
    created=await h.post('/api/gl/accounts',params={'entity_id':'A'},json={
        'code':'4-7777','name':'Synthetic entity-only income','type':'income',
        'parent_code':'4-0000','is_postable':True,'is_active':True})
    assert created.status_code==200,(created.status_code,created.text)
    assert await e.db.gl_accounts.count_documents({'code':'4-7777','entity_id':{'$in':[None,'']}})==0
    posted=await h.post('/api/gl/journal',json={'date':'2026-07-15T12:00:00+00:00',
        'description':'Synthetic entity-only account producer','lines':[
            {'account_code':'1-1100','debit':77,'credit':0},
            {'account_code':'4-7777','debit':0,'credit':77}]})
    assert posted.status_code==200,(posted.status_code,posted.text)
    params={'start':'2026-07-01','end':'2026-07-31'}
    single=await h.get('/api/finance/income-statement',params={**params,'entity_id':'A'})
    allp=await h.get('/api/finance/income-statement',params={**params,'entity_id':'all'})
    singlebs=await h.get('/api/finance/balance-sheet',params={'as_of':'2026-07-31','entity_id':'A'})
    allbs=await h.get('/api/finance/balance-sheet',params={'as_of':'2026-07-31','entity_id':'all'})
    for r in [single,allp,singlebs,allbs]:assert r.status_code==200,(r.status_code,r.text)
    rec('D4-COA-01-single-entity-income-control',77,single.json()['net_income'])
    rec('D4-COA-01-all-entities-income',77,allp.json()['net_income'],
        'Authorized all scope contains A+B; B has no July journals. Single A correctly reports income77 from an original permitted entity-only account, but all uses global-only account dimensions and drops that income.')
    rec('D4-COA-01-single-entity-balance-control',True,singlebs.json()['balanced'])
    rec('D4-COA-01-all-entities-balanced',True,allbs.json()['balanced'],
        'Bank asset line is retained but the entity-only income is unclassified, making all-scope financial statements unbalanced. This is not an entity-specific override changing the meaning of an existing global code.')
    rec('D4-COA-01-all-entities-assets-control',307,allbs.json()['assets_total'],
        'Original lifecycle produced100+130+77 in A. B is still empty at this test; non-finite fixture runs later in another month.')
    CONTEXT['entity_only_coa']={'account':created.json(),'manual':posted.json(),
        'single_income':single.json(),'all_income':allp.json(),
        'single_balance':singlebs.json(),'all_balance':allbs.json(),
        'scope':'Original authorized public account/manual creators; A+B all scope; unique entity-only account with no global code, not conflicting override'}

def portable(value):
    if isinstance(value,float) and not math.isfinite(value):
        return {'non_finite':('NaN' if math.isnan(value) else 'Infinity' if value>0 else '-Infinity')}
    if isinstance(value,dict):return {k:portable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [portable(v) for v in value]
    return value

async def main():
    await e.seed();await gl.seed_default_coa()
    from indexes import ensure_performance_indexes
    CONTEXT['indexes']=await ensure_performance_indexes()
    CONTEXT['journal_indexes']=await e.db.journal_entries.index_information()
    await e.db.users.update_one({'id':'U'},{'$set':{'role':'admin','allowed_entity_ids':['A','B']}})
    second=await e.db.users.find_one({'id':'U'},{'_id':0});second.update(id='U2',name='Audit Approver',email='approver@example.invalid')
    await e.db.users.insert_one(second)
    await e.db.sessions.insert_one({'token':'audit-second-session','user_id':'U2',
        'expires_at':datetime.now(timezone.utc)+timedelta(hours=2)})
    await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{
        'accounting':['view','create','manage','void'],'period':['view','unlock','backdate']}}})
    async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),
        base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
        for name,fn in [('nested_closing',nested_closing),('reclose_recovery',reclose_recovery),
                        ('reversal_then_void',reversal_then_void),('entity_account_dimension',entity_account_dimension),
                        ('finite_manual',finite_manual)]:
            try:await fn(h)
            except Exception:ERRORS.append({'test':name,'traceback':traceback.format_exc()})
    output={'commit':'a904d989b622f7da14c4892d03cf6ef0c43f3084','database':e.db.name,
        'results':RESULTS,'contexts':CONTEXT,'harness_errors':ERRORS,'external_connections':e.blocked}
    Path(__file__).with_name('closing-reversal-results.json').write_text(
        json.dumps(portable(output),ensure_ascii=False,indent=2,default=str,allow_nan=False),encoding='utf-8')
    print(json.dumps({'results':RESULTS,'harness_errors':ERRORS},ensure_ascii=False))
    assert not ERRORS,ERRORS
asyncio.run(main())
