"""Independent revalidation of W2-05. No changes to application or historic evidence."""
import asyncio
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
import wave2_env as e
from services import rfid_service as rf, rfid_incident_service as inc
from services import roll_service as rolls, warehouse_scope_service as whs
from entity_scope import SCOPE_FIELD
from indexes import ensure_performance_indexes

db = e.db
out = []

def record(name, data):
    out.append({'probe': name, **data})
    print(name, json.dumps(data, default=str), flush=True)

class Proxy:
    def __init__(self, collection): self.collection = collection
    def __getattr__(self, name):
        return self.collection if name == 'rfid_incidents' else getattr(db, name)

async def main():
    await e.seed()
    await db.permission_settings.update_one({'id':'default'}, {'$set':{'matrix.finance.wms':['view','update','scan']}})
    await db.users.insert_one({'id':'U2','name':'Audit Operator 2','email':'op2@example.invalid',
        'role':'finance','status':'active','home_entity_id':'A','allowed_entity_ids':['A']})
    await db.sessions.insert_one({'token':'audit-local-session-2','user_id':'U2',
        'expires_at':datetime.now(timezone.utc)+timedelta(hours=2)})
    index_result = await ensure_performance_indexes()
    assert index_result['failed'] == 0 and not index_result['unique']['failed'], index_result
    await db.warehouses.insert_many([
        {'id':'SH','name':'Shared audit','sharing_mode':'shared','entity_ids':[],'status':'active'},
        {'id':'DB','name':'Dedicated B','sharing_mode':'dedicated','entity_ids':['B'],'status':'active'}])
    await db.products.insert_one({'id':'P','sku':'P','name':'Synthetic','base_unit':'meter','harga_pokok':10,'price':10,'grade':'A'})
    devices = {}
    tags = {}
    for i,w in enumerate(['SH','DB']):
        dev = await rf.create_device({'code':'V-'+w,'name':'V-'+w,'type':'gate','direction':'out','warehouse_id':w})
        await db.rfid_devices.update_one({'id':dev['id']},{'$set':{'api_key':'local-fixture-'+w}})
        devices[w] = {**dev,'api_key':'local-fixture-'+w}
        roll = await rolls.create_inbound_roll('P',w,'B',10,unit_cost=10,acquired_via='purchase',ref_id='V-'+w)
        tags[w] = await rf.encode_tag(roll['id'],['B'],epc=f'E2000000000000000000000{i}')
    assert not whs.is_usable(await db.warehouses.find_one({'id':'DB'}),'A')
    assert whs.is_usable(await db.warehouses.find_one({'id':'SH'}),'A')
    record('fixture_and_policy', {'indexes':index_result,'reads_scope':SCOPE_FIELD['rfid_reads'],
        'incidents_scope':SCOPE_FIELD['rfid_incidents'],'dedicated_B_usable_by_A':False,
        'legacy_entity_id_only_mode':whs.mode_of({'entity_id':'B'})})

    transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False)
    async with e.httpx.AsyncClient(transport=transport,base_url='http://audit.local',headers={
        'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as a, \
        e.httpx.AsyncClient(transport=transport,base_url='http://audit.local',headers={
        'Authorization':'Bearer audit-local-session-2','X-Entity-Id':'A'}) as a2, \
        e.httpx.AsyncClient(transport=transport,base_url='http://audit.local') as device_http:
        async def ingest(w,epc):
            return await device_http.post('/api/rfid/ingest',json={'epcs':[epc]},headers={'X-Device-Key':devices[w]['api_key']})
        for w in ['SH','DB']:
            r=await ingest(w,tags[w]['epc']);assert r.status_code==200,r.text
            t=await a.get('/api/rfid/tags',params={'warehouse_id':w})
            rr=await a.get('/api/rfid/reads',params={'warehouse_id':w})
            assert t.status_code==200 and t.json()['count']==0,t.text
            assert rr.status_code==200 and rr.json()['reads'][0]['owner_entity_id']=='B',rr.text
            record('W2-010_'+w,{'tag_list_http':t.status_code,'visible_tags':t.json()['count'],
                'reads_http':rr.status_code,'read_owner':rr.json()['reads'][0]['owner_entity_id']})
        forbidden=await a.get('/api/rfid/tags',headers={'X-Entity-Id':'B'})
        assert forbidden.status_code==403,forbidden.text
        record('scope_control',{'forced_B_header_http':forbidden.status_code})
        incident_b=await db.rfid_incidents.find_one({'epc':tags['DB']['epc']})
        rows=await a.get('/api/rfid/incidents',params={'warehouse_id':'DB'})
        ack=await a.post(f"/api/rfid/incidents/{incident_b['id']}/acknowledge",json={})
        res=await a.post(f"/api/rfid/incidents/{incident_b['id']}/resolve",json={})
        health=await a.get('/api/rfid/device-health')
        report=await a.get('/api/rfid/shrinkage-report')
        assert [rows.status_code,ack.status_code,res.status_code,health.status_code,report.status_code]==[200]*5
        record('shared_security_policy_observation',{'incidents_http':rows.status_code,'ack_http':ack.status_code,
            'resolve_http':res.status_code,'dedicated_B_device_visible':any(x['id']==devices['DB']['id'] for x in health.json()['devices']),
            'report_includes_B_warehouse':any(x['warehouse_id']=='DB' for x in report.json()['per_warehouse']),
            'classification':'behavior confirmed; unauthorized classification not established because incidents are explicitly SHARED'})

        # Create incident by actual ingest, then two different actors race on it.
        race_epc='E20000000000000000000099'
        await ingest('SH',race_epc)
        race=await db.rfid_incidents.find_one({'epc':race_epc});rid=race['id']
        arrived,release=asyncio.Event(),asyncio.Event()
        class TransitionCollection:
            def __getattr__(self,name):return getattr(db.rfid_incidents,name)
            async def update_one(self,q,u,*args,**kwargs):
                if q.get('id')==rid and u.get('$set',{}).get('status')=='acknowledged':
                    arrived.set();await release.wait()
                return await db.rfid_incidents.update_one(q,u,*args,**kwargs)
        original=inc.db;inc.db=Proxy(TransitionCollection())
        task=None
        try:
            task=asyncio.create_task(a.post(f'/api/rfid/incidents/{rid}/acknowledge',json={'note':'ack actor1'}))
            await asyncio.wait_for(arrived.wait(),5)
            done=await a2.post(f'/api/rfid/incidents/{rid}/resolve',json={'note':'resolve actor2'})
            release.set();late=await task
        finally:
            release.set()
            if task and not task.done():await task
            inc.db=original
        state=await db.rfid_incidents.find_one({'id':rid})
        assert done.status_code==late.status_code==200 and state['status']=='acknowledged'
        assert state['ack_by'] != state['resolved_by'] and state['resolved_at']
        record('W2-011_http_two_actors',{'http':[late.status_code,done.status_code],
            'status':state['status'],'ack_by':state['ack_by'],'resolved_by':state['resolved_by'],
            'notes':state['notes'],'resolved_at':state['resolved_at']})
        serial=await a2.post(f'/api/rfid/incidents/{rid}/resolve',json={})
        denied=await a.post(f'/api/rfid/incidents/{rid}/acknowledge',json={})
        assert serial.status_code==200 and denied.status_code==400
        record('terminal_serial_control',{'resolve_http':serial.status_code,'late_ack_http':denied.status_code})

        # The distinct read IDs are created by two HTTP ingest requests, not fabricated.
        epc='E20000000000000000000098';arrivals=0;release=asyncio.Event()
        class DedupeCollection:
            def __getattr__(self,name):return getattr(db.rfid_incidents,name)
            async def find_one(self,q,*args,**kwargs):
                nonlocal arrivals
                value=await db.rfid_incidents.find_one(q,*args,**kwargs)
                if q.get('epc')==epc:
                    arrivals+=1
                    if arrivals==2:release.set()
                    await release.wait()
                return value
        inc.db=Proxy(DedupeCollection())
        try: responses=await asyncio.wait_for(asyncio.gather(ingest('SH',epc),ingest('SH',epc)),10)
        finally:release.set();inc.db=original
        incidents=await db.rfid_incidents.find({'epc':epc}).to_list(10)
        notifications=await db.notifications.count_documents({'ref':{'$in':[x['id'] for x in incidents]}})
        assert all(r.status_code==200 for r in responses) and len(incidents)==2
        assert len({x['read_id'] for x in incidents})==2 and notifications==2
        record('W2-012_http_with_indexes',{'http':[r.status_code for r in responses],
            'open_incidents':len(incidents),'distinct_read_ids':len({x['read_id'] for x in incidents}),
            'hits':[x['hits'] for x in incidents],'notifications':notifications,
            'incident_indexes':await db.rfid_incidents.index_information()})
        serial_epc='E20000000000000000000097'
        await ingest('SH',serial_epc);await ingest('SH',serial_epc)
        serial_rows=await db.rfid_incidents.find({'epc':serial_epc}).to_list(10)
        assert len(serial_rows)==1 and serial_rows[0]['hits']==2
        record('serial_dedupe_control',{'incidents':len(serial_rows),'hits':serial_rows[0]['hits']})
        # Uninstrumented concurrency is supplemental; no required hit rate is assumed.
        counts=[]
        for n in range(10):
            ep=f'E200000000000000000001{n:02X}'
            rs=await asyncio.gather(ingest('SH',ep),ingest('SH',ep))
            assert all(r.status_code==200 for r in rs)
            counts.append(await db.rfid_incidents.count_documents({'epc':ep}))
        record('uninstrumented_ingest_pairs',{'incident_counts_for_10_pairs':counts,
            'pairs_with_duplicates':sum(n>1 for n in counts)})
    assert not e.blocked,e.blocked

async def run():
    completed=False
    try:await main();completed=True
    finally:
        target=Path(__file__).resolve().parent.parent/'validation'/'W2-05-review'
        target.mkdir(parents=True,exist_ok=True)
        (target/'results.json').write_text(json.dumps({'completed':completed,
            'commit':subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),
            'database':e.DBNAME,'purpose':'validate prior findings, not new coverage count','probes':out},indent=2,default=str),encoding='utf-8')
        e.client.close()

asyncio.run(run())
