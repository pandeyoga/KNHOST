"""W2-03: cycle count ownership and approve/reject arbitration; isolated Mongo + ASGI."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import roll_service as rolls
from routers import cycle_count as cc
db=e.db
results=[]
def record(id,observed,ok,kind='control'):
    assert ok,(id,observed)
    results.append(dict(id=id,kind=kind,observed=observed));print(id,json.dumps(observed),flush=True)
async def stock(pid,owner,qty):
    if not await db.products.find_one({'id':pid}):
        await db.products.insert_one(dict(id=pid,sku=pid,name=pid,base_unit='meter',harga_pokok=10,price=10,grade='A'))
    return await rolls.create_inbound_roll(pid,'SHARED',owner,qty,unit_cost=10,acquired_via='purchase',ref_id=pid)
async def quantity(pid,owner):
    rs=await db.inventory_rolls.find({'product_id':pid,'owner_entity_id':owner}).to_list(100)
    return sum(r['length_remaining'] for r in rs)
async def make(http,pid,owner=None):
    r=await http.post('/api/cycle-count/sessions',json={'warehouse_id':'SHARED','name':pid})
    assert r.status_code==200,r.text
    sid=r.json()['id'];body={'product_id':pid}
    if owner is not None:body['owner_entity_id']=owner
    r=await http.post(f'/api/cycle-count/sessions/{sid}/items',json=body)
    assert r.status_code==200,r.text
    return sid,r.json()
async def counted(http,sid,item,qty):
    r=await http.patch(f'/api/cycle-count/sessions/{sid}/items/{item["id"]}',json={'actual_qty':qty})
    assert r.status_code==200,r.text
    r=await http.post(f'/api/cycle-count/sessions/{sid}/submit')
    assert r.status_code==200,r.text
async def approve(http,sid):return await http.post(f'/api/cycle-count/sessions/{sid}/approve',json={'reason':'Synthetic count'})
async def main():
    await e.seed()
    await db.warehouses.insert_one({'id':'SHARED','name':'Shared synthetic warehouse','sharing_mode':'shared','status':'active'})
    await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.inventory':['cycle_count','approve_count']}})
    async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as http:
        await stock('OWN','A',100);sid,item=await make(http,'OWN');await counted(http,sid,item,90)
        r=await approve(http,sid);q=await quantity('OWN','A')
        record('W2-C-C01',{'http_status':r.status_code,'status':r.json().get('status'),'quantity':q},r.status_code==200 and r.json()['status']=='approved' and q==90)
        r=await approve(http,sid)
        record('W2-C-C02',{'http_status':r.status_code,'quantity':await quantity('OWN','A')},r.status_code==400 and await quantity('OWN','A')==90)
        await db.cycle_count_sessions.insert_one({'id':'FOREIGN-SESSION','entity_id':'B','warehouse_id':'SHARED','status':'open','items':[]})
        r=await http.get('/api/cycle-count/sessions/FOREIGN-SESSION')
        record('W2-C-C03',{'http_status':r.status_code},r.status_code in (403,404))
        await stock('FOREIGN-EXPLICIT','B',10)
        r=await http.post('/api/cycle-count/sessions',json={'warehouse_id':'SHARED'})
        explicit_sid=r.json()['id']
        r=await http.post(f'/api/cycle-count/sessions/{explicit_sid}/items',json={'product_id':'FOREIGN-EXPLICIT','owner_entity_id':'B'})
        record('W2-C-C08',{'http_status':r.status_code,'foreign_remaining':await quantity('FOREIGN-EXPLICIT','B')},r.status_code==403 and await quantity('FOREIGN-EXPLICIT','B')==10)
        for suffix,owner in [('FALLBACK',None)]:
            pid='FOREIGN-'+suffix;await stock(pid,'B',10)
            sid,item=await make(http,pid,owner)
            await counted(http,sid,item,8);r=await approve(http,sid)
            sess=await db.cycle_count_sessions.find_one({'id':sid})
            obs={'http_status':r.status_code,'user_allowed_entity_ids':['A'],'session_entity':sess['entity_id'],'requested_owner':owner,'resolved_owner':item['owner_entity_id'],'expected_qty':item['expected_qty'],'foreign_remaining':await quantity(pid,'B')}
            record('W2-C-F01' if owner else 'W2-C-F02',obs,r.status_code==200 and sess['entity_id']=='A' and item['owner_entity_id']=='B' and await quantity(pid,'B')==8,'defect')
        await stock('BOTH','A',20);await stock('BOTH','B',100)
        sid,item=await make(http,'BOTH');await counted(http,sid,item,18);r=await approve(http,sid)
        record('W2-C-C04',{'http_status':r.status_code,'resolved_owner':item['owner_entity_id'],'A':await quantity('BOTH','A'),'B':await quantity('BOTH','B')},r.status_code==200 and await quantity('BOTH','A')==18 and await quantity('BOTH','B')==100)
        await stock('DRIFT','A',100);sid,item=await make(http,'DRIFT');await counted(http,sid,item,90)
        await stock('DRIFT','A',10);r=await approve(http,sid)
        sess=await db.cycle_count_sessions.find_one({'id':sid})
        record('W2-C-C05',{'http_status':r.status_code,'quantity':await quantity('DRIFT','A'),'status':sess['status'],'lock_present':'saga_lock' in sess},r.status_code==409 and await quantity('DRIFT','A')==110 and 'saga_lock' not in sess)
        await stock('REJECT','A',100);sid,item=await make(http,'REJECT');await counted(http,sid,item,90)
        r=await http.post(f'/api/cycle-count/sessions/{sid}/reject',json={'reason':'Synthetic reject'})
        a=await approve(http,sid)
        record('W2-C-C06',{'reject_status':r.status_code,'approve_status':a.status_code,'quantity':await quantity('REJECT','A')},r.status_code==200 and a.status_code==400 and await quantity('REJECT','A')==100)
        await stock('PENDING','A',100);sid,item=await make(http,'PENDING')
        r=await http.post(f'/api/cycle-count/sessions/{sid}/submit')
        record('W2-C-C07',{'http_status':r.status_code},r.status_code==400)
        await stock('RACE','A',100);sid,item=await make(http,'RACE');await counted(http,sid,item,90)
        reached=asyncio.Event();resume=asyncio.Event();original=cc._load_session
        async def barrier(session_id,request):
            data=await original(session_id,request)
            if session_id==sid and request.url.path.endswith('/reject'):
                reached.set();await resume.wait()
            return data
        cc._load_session=barrier
        task=asyncio.create_task(http.post(f'/api/cycle-count/sessions/{sid}/reject',json={'reason':'Concurrent reject'}))
        try:
            await asyncio.wait_for(reached.wait(),20)
            a=await approve(http,sid)
            resume.set();r=await asyncio.wait_for(task,20)
        finally:
            cc._load_session=original;resume.set()
            if not task.done():task.cancel()
        sess=await db.cycle_count_sessions.find_one({'id':sid})
        record('W2-C-F03',{'approve_status':a.status_code,'reject_status':r.status_code,'final_status':sess['status'],'quantity':await quantity('RACE','A'),'has_approved_at':bool(sess.get('approved_at')),'has_rejected_at':bool(sess.get('rejected_at'))},a.status_code==200 and r.status_code==200 and sess['status']=='rejected' and await quantity('RACE','A')==90,'defect')
async def run():
    try:await main()
    finally:
        sha=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip()
        (Path(__file__).parent.parent/'count-results.json').write_text(json.dumps({'commit':sha,'database':e.DBNAME,'level':'Mongo + ASGI; F03 scheduling barrier wrapping original session loader; no lifecycle startup','scenarios':results},indent=2),encoding='utf-8')
        e.client.close()
asyncio.run(run())
