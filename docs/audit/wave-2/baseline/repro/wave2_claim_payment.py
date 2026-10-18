"""W2-02: makloon bill cancellation and payment/claim interleaving. Local synthetic DB only."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import makloon_order_service as m,makloon_claim_service as claims,roll_service as rolls,payment_variance_service as pvs
db=e.db
results=[]
def record(id,observed,ok,kind='control'):
    assert ok,(id,observed)
    results.append(dict(id=id,kind=kind,observed=observed))
    print(id,json.dumps(observed),flush=True)
async def fixture(tag):
    mid='W2B-'+tag; inp=mid+'-IN'; out=mid+'-OUT'
    for pid in (inp,out):
        await db.products.insert_one(dict(id=pid,sku=pid,name=pid,base_unit='meter',harga_pokok=10000,price=10000,grade='A'))
    await rolls.create_inbound_roll(inp,'WH','A',10,unit_cost=10000,lot=mid+'-RAW',acquired_via='purchase',ref_id=mid)
    await db.makloon_orders.insert_one(dict(id=mid,mko_number=mid,entity_id='A',status='draft',from_warehouse_id='WH',target_warehouse_id='WH',timeline=[],steps=[dict(seq=1,status='pending',material_flow='moves',process_type='dyeing',input_product_id=inp,output_product_id=out,input_qty=10,input_unit='meter',output_unit='meter',expected_output_qty=10,issue_ref=mid+':1',makloon_id='PARTNER',tariff_basis='lumpsum',tariff_rate=100000,tolerance_pct=1)]))
    await m.issue_step(mid,1,actor_name='Audit')
    order=await m.receive_step(mid,1,{'actual_output_qty':8,'tariff':100000,'rolls':[{'lot':mid+'-OUT','length':8}]},actor_name='Audit')
    return mid,order['steps'][0]['service_bill_id']
async def propose(mid,amount=40000):
    await claims.propose_claim(mid,1,action='potong_bon',amount=amount,reason='Synthetic shortage claim',actor='Audit')
async def approve(mid):
    return await claims.approve_claim(mid,1,actor='Audit Manager',actor_role='manager')
async def state(mid,bid):
    b=await db.vendor_bills.find_one({'id':bid})
    cs=await db.cash_transactions.find({'ref_id':bid}).to_list(100)
    j=await db.journal_entries.find({'$or':[{'source_id':bid},{'source_id':mid+':1'},{'source_id':{'$in':[c['id'] for c in cs]}}]}).to_list(100)
    ap=round(sum(l.get('credit',0)-l.get('debit',0) for x in j for l in x['lines'] if l['account_code']=='2-1100'),2)
    o=await db.makloon_orders.find_one({'id':mid})
    return {'bill_status':b['status'],'grand_total':b['grand_total'],'amount_paid':b.get('amount_paid',0),'cash_amount':sum(c['amount'] for c in cs),'gl_ap_credit_net':ap,'claim_status':o['steps'][0]['claim']['status'],'journal_sources':[x['source_type'] for x in j]}
async def main():
    await e.seed()
    await db.warehouses.insert_one({'id':'WH','name':'Synthetic WH','entity_id':'A','status':'active'})
    await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.vendor_bill':['view','pay','update']}})
    async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as http:
        mid,bid=await fixture('PAY')
        r=await http.post(f'/api/vendor-bills/{bid}/pay',json={'amount':100000})
        s=await state(mid,bid);record('W2-B-C01',{'http_status':r.status_code,**s},r.status_code==200 and s['bill_status']=='paid' and s['gl_ap_credit_net']==0 and s['cash_amount']==100000)
        r=await http.post(f'/api/vendor-bills/{bid}/cancel',json={'notes':'Synthetic cancel paid'})
        record('W2-B-C02',{'http_status':r.status_code,'unchanged':s==await state(mid,bid)},r.status_code==400 and s==await state(mid,bid))
        mid,bid=await fixture('CLAIM')
        await propose(mid);await approve(mid)
        s=await state(mid,bid);record('W2-B-C03',s,s['grand_total']==60000 and s['gl_ap_credit_net']==60000)
        try:await approve(mid)
        except claims.ClaimError:
            record('W2-B-C04',{'rejected':True,'unchanged':s==await state(mid,bid)},s==await state(mid,bid))
        r=await http.post(f'/api/vendor-bills/{bid}/pay',json={'amount':60000})
        s=await state(mid,bid);record('W2-B-C05',{'http_status':r.status_code,**s},r.status_code==200 and s['gl_ap_credit_net']==0 and s['bill_status']=='paid')
        mid,bid=await fixture('CAP')
        r=await http.post(f'/api/vendor-bills/{bid}/pay',json={'amount':80000})
        assert r.status_code==200,r.text
        await propose(mid)
        try:await approve(mid)
        except claims.ClaimError as ex:
            s=await state(mid,bid);record('W2-B-C06',{'rejected':str(ex),**s},s['grand_total']==100000 and s['amount_paid']==80000 and s['gl_ap_credit_net']==20000)
        mid,bid=await fixture('CANCEL')
        r=await http.post(f'/api/vendor-bills/{bid}/cancel',json={'notes':'Synthetic unpaid service cancellation'})
        s=await state(mid,bid);record('W2-B-F01',{'http_status':r.status_code,**s},r.status_code==200 and s['bill_status']=='cancelled' and s['gl_ap_credit_net']==100000 and 'vendor_bill_reversal' not in s['journal_sources'],'defect')
        mid,bid=await fixture('RACE')
        await propose(mid)
        reached=asyncio.Event();resume=asyncio.Event();original=pvs.assess_bill
        async def barrier(bill,amount):
            result=await original(bill,amount)
            if bill['id']==bid:
                reached.set();await resume.wait()
            return result
        pvs.assess_bill=barrier
        pending=asyncio.create_task(http.post(f'/api/vendor-bills/{bid}/pay',json={'amount':80000}))
        try:
            await asyncio.wait_for(reached.wait(),20)
            await approve(mid)
            resume.set();r=await asyncio.wait_for(pending,20)
        finally:
            pvs.assess_bill=original;resume.set()
            if not pending.done():pending.cancel()
        s=await state(mid,bid);record('W2-B-F02',{'http_status':r.status_code,'interleaving':'pay read grand100000 -> claim reduces to60000 -> payment80000 resumes',**s},r.status_code==200 and s['grand_total']==60000 and s['amount_paid']==80000 and s['gl_ap_credit_net']==-20000,'defect')
        from services import gl_service as gl
        # Reverse interleaving: claim prechecks outstanding, payment completes, claim resumes.
        mid,bid=await fixture('RACE-REVERSE');await propose(mid)
        reached=asyncio.Event();resume=asyncio.Event();original_gl=gl.post_makloon_claim
        async def claim_barrier(**kwargs):
            if kwargs['mko_id']==mid:
                reached.set();await resume.wait()
            return await original_gl(**kwargs)
        gl.post_makloon_claim=claim_barrier
        pending=asyncio.create_task(approve(mid))
        try:
            await asyncio.wait_for(reached.wait(),20)
            r=await http.post(f'/api/vendor-bills/{bid}/pay',json={'amount':80000})
            resume.set();await asyncio.wait_for(pending,20)
        finally:
            gl.post_makloon_claim=original_gl;resume.set()
            if not pending.done():pending.cancel()
        s=await state(mid,bid);record('W2-B-F03',{'http_status':r.status_code,'interleaving':'claim validates unpaid100000 -> payment80000 -> claim40000 resumes',**s},r.status_code==200 and s['amount_paid']==80000 and s['grand_total']==60000 and s['gl_ap_credit_net']==-20000,'defect')
        # Control: the existing atomic guard DOES protect two payments when grand_total is stable.
        mid,bid=await fixture('PAY-PAIR')
        reached=asyncio.Event();arrivals=0;original=pvs.assess_bill
        async def payment_pair(bill,amount):
            nonlocal arrivals
            result=await original(bill,amount)
            if bill['id']==bid:
                arrivals+=1
                if arrivals==2:reached.set()
                await reached.wait()
            return result
        pvs.assess_bill=payment_pair
        try:
            rr=await asyncio.wait_for(asyncio.gather(*[http.post(f'/api/vendor-bills/{bid}/pay',json={'amount':80000}) for _ in range(2)]),20)
        finally:pvs.assess_bill=original
        s=await state(mid,bid);record('W2-B-C07',{'http_statuses':sorted(r.status_code for r in rr),**s},sorted(r.status_code for r in rr)==[200,409] and s['amount_paid']==80000 and s['cash_amount']==80000)
        # Control: generic supplier bill reversal finds the normal vendor_bill journal.
        b={'id':'W2B-NORMAL-VB','bill_number':'W2B-NORMAL-VB','entity_id':'A','po_id':'','status':'posted','grand_total':100000,'amount_paid':0,'supplier_name':'Synthetic','timeline':[]}
        await db.vendor_bills.insert_one(dict(b));await gl.post_vendor_bill(b)
        r=await http.post('/api/vendor-bills/W2B-NORMAL-VB/cancel',json={'notes':'Synthetic normal bill reversal'})
        js=await db.journal_entries.find({'source_id':b['id']}).to_list(10)
        ap=sum(l['credit']-l['debit'] for j in js for l in j['lines'] if l['account_code']=='2-1100')
        record('W2-B-C08',{'http_status':r.status_code,'journal_count':len(js),'gl_ap_credit_net':ap},r.status_code==200 and len(js)==2 and ap==0)
async def run():
    try:await main()
    finally:
        sha=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip()
        (Path(__file__).parent.parent/'claim-payment-results.json').write_text(json.dumps({'commit':sha,'database':e.DBNAME,'level':'real Mongo; bill pay/cancel via ASGI; claim service; deterministic scheduling barrier delegates original assessment','scenarios':results},indent=2),encoding='utf-8')
        e.client.close()
asyncio.run(run())
