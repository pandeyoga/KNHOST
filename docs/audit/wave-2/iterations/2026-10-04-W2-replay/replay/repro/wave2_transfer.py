"""W2-04: intra warehouse transfer owner and roll projection, synthetic Mongo + ASGI."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import roll_service as rolls
db=e.db
results=[]
def record(id,observed,ok,kind='control'):
    assert ok,(id,observed)
    results.append(dict(id=id,kind=kind,observed=observed));print(id,json.dumps(observed),flush=True)
async def stock(pid,owner,qty,wh='W1'):
    if not await db.products.find_one({'id':pid}):await db.products.insert_one(dict(id=pid,sku=pid,name=pid,base_unit='meter',harga_pokok=10,price=10,grade='A'))
    return await rolls.create_inbound_roll(pid,wh,owner,qty,unit_cost=10,acquired_via='purchase',ref_id=pid)
async def balance(pid,owner,wh='W1'):
    return await db.inventory_balances.find_one({'product_id':pid,'owner_entity_id':owner,'warehouse_id':wh})
async def create(http,pid,qty=10,roll_ids=None,source='W1',dest='W2'):
    return await http.post('/api/transfers',json={'source_warehouse_id':source,'dest_warehouse_id':dest,'items':[{'product_id':pid,'qty':qty,'roll_ids':roll_ids or []}]})
async def status(http,tid,status):return await http.post(f'/api/transfers/{tid}/status',json={'status':status})
async def main():
    await e.seed()
    for wh in ['W1','W2','W3']:await db.warehouses.insert_one({'id':wh,'name':wh,'sharing_mode':'shared','status':'active'})
    await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.transfer':['view','create','approve','reject','update','cancel']}})
    async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as http:
        await stock('AUTO','A',20);r=await create(http,'AUTO',10)
        assert r.status_code==200,r.text;tid=r.json()['id'];b=await balance('AUTO','A')
        record('W2-T-C01',{'http_status':r.status_code,'roll_owner':r.json()['items'][0]['owner_entity_id'],'available':b['available_qty'],'reserved':b['reserved_qty']},b['available_qty']==10 and b['reserved_qty']==10 and r.json()['items'][0]['owner_entity_id']=='A')
        r=await http.post(f'/api/transfers/{tid}/reject',json={'reason':'Synthetic reject'})
        b=await balance('AUTO','A');record('W2-T-C02',{'http_status':r.status_code,'available':b['available_qty'],'reserved':b['reserved_qty']},r.status_code==200 and b['available_qty']==20 and b['reserved_qty']==0)
        wrong=await stock('WRONG','A',10,'W3')
        r=await create(http,'WRONG',10,[wrong['id']]);current=await db.inventory_rolls.find_one({'id':wrong['id']})
        record('W2-T-C03',{'http_status':r.status_code,'roll_status':current['status']},r.status_code==400 and current['status']=='available')
        own=await stock('EXPLICIT-OWN','A',10)
        r=await create(http,'EXPLICIT-OWN',10,[own['id']]);assert r.status_code==200,r.text
        own_now=await db.inventory_rolls.find_one({'id':own['id']});b=await balance('EXPLICIT-OWN','A')
        record('W2-T-F01',{'http_status':r.status_code,'roll_status':own_now['status'],'projected_available':b['available_qty'],'projected_reserved':b['reserved_qty']},own_now['status']=='reserved' and b['available_qty']==10 and b['reserved_qty']==0,'defect')
        tid=r.json()['id'];await http.delete(f'/api/transfers/{tid}',params={'reason':'Synthetic cancel'})
        b=await balance('EXPLICIT-OWN','A');record('W2-T-C04',{'available_after_cancel':b['available_qty']},b['available_qty']==10)
        await stock('CROSS','A',20);foreign=await stock('CROSS','B',10)
        r=await create(http,'CROSS',10,[foreign['id']]);assert r.status_code==200,r.text
        t=r.json();f=await db.inventory_rolls.find_one({'id':foreign['id']});b=await balance('CROSS','B')
        record('W2-T-F02',{'http_status':r.status_code,'user_scope':['A'],'transfer_entity':t['entity_id'],'item_owner':t['items'][0]['owner_entity_id'],'selected_roll_owner':f['owner_entity_id'],'selected_roll_status':f['status'],'B_projected_available':b['available_qty']},t['entity_id']=='A' and t['items'][0]['owner_entity_id']=='A' and f['owner_entity_id']=='B' and f['status']=='reserved','defect')
        tid=t['id'];r=await http.delete(f'/api/transfers/{tid}',params={'reason':'Synthetic cancel'})
        f=await db.inventory_rolls.find_one({'id':foreign['id']});b=await balance('CROSS','B')
        record('W2-T-C05',{'http_status':r.status_code,'foreign_status':f['status'],'foreign_available':b['available_qty']},r.status_code==200 and f['status']=='available' and b['available_qty']==10)
        await stock('AUTO-FALLBACK','B',10)
        r=await create(http,'AUTO-FALLBACK',10)
        observed={'http_status':r.status_code}
        if r.status_code==200:
            t=r.json();observed.update(transfer_entity=t['entity_id'],item_owner=t['items'][0]['owner_entity_id'])
        record('W2-T-F03',observed,r.status_code==200 and observed.get('transfer_entity')=='A' and observed.get('item_owner')=='B','defect')
        await stock('LIFECYCLE','A',10);r=await create(http,'LIFECYCLE',10);assert r.status_code==200,r.text
        tid=r.json()['id'];steps=[]
        a=await http.post(f'/api/transfers/{tid}/approve',json={});steps.append(a.status_code)
        for st in ('picking','staging','dispatched','completed'):
            a=await status(http,tid,st);steps.append(a.status_code)
        b1=await balance('LIFECYCLE','A','W1');b2=await balance('LIFECYCLE','A','W2')
        record('W2-T-C06',{'http_statuses':steps,'source_available':b1['available_qty'],'dest_available':b2['available_qty']},steps==[200]*5 and b1['available_qty']==0 and b2['available_qty']==10)
async def run():
    try:await main()
    finally:
        sha=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip()
        (Path(__file__).parent.parent/'transfer-results.json').write_text(json.dumps({'commit':sha,'database':e.DBNAME,'level':'ASGI HTTP + Mongo; synthetic shared warehouses; no app lifespan','scenarios':results},indent=2),encoding='utf-8')
        e.client.close()
asyncio.run(run())
