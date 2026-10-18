"""Original WMS/RFID chains with UUID localhost data and startup indexes.

Inbound roll writer is original; print/verification/routing, PA, device ingest,
cycle count and admin recovery use public APIs. Print acknowledgment and scan
inputs are synthetic operator/manual evidence, not physical hardware validation.
Reservations use the original public SO creator and its allocator; this is not
proof of the subsequent approval -> picking -> shipment chain. Faults wrap only
one write boundary; no original implementation, assertion or side effect changes.
"""
import asyncio, json, traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
import wave2_env as e
from services import roll_service as rolls, putaway_order_service as pa
from services import rfid_ingest_service as ing, cycle_count_service as cc
from core_utils import now_iso

RESULTS=[]; CONTEXT={}; ERRORS=[]
def rec(key,expected,actual,note=''):
    RESULTS.append(dict(id=key,expected=expected,actual=actual,note=note,
        status='pass' if expected==actual else 'observed_difference'))
def response(r):
    try: body=r.json()
    except Exception: body=r.text[:1000]
    return dict(http=r.status_code,body=body)
async def post(h,path,body=None):
    r=await h.post('/api/'+path,json=body or {})
    assert r.status_code==200,(path,r.status_code,r.text)
    return r.json()
async def warehouse(name,roles):
    await e.db.warehouses.insert_one(dict(id=name,name='Audit '+name,active=True,
        roles=roles,sharing_mode='shared',entity_ids=[],site_id='AUDIT',city='Jakarta',
        storage_rules={'mode':'none','categories':[],'grades':[]}))
async def product(name,unit='meter'):
    await e.db.products.insert_one(dict(id=name,sku='AUDIT-'+name,name='Audit fabric '+name,
        base_unit=unit,category='woven',fabric_type='woven',stage='finished',
        product_type='finished_good',status='active',harga_pokok=10,price=100,grade='A'))
async def verified(h,p,wh,qty=10):
    roll=await rolls.create_inbound_roll(p,wh,'A',qty,lot='AUDIT-'+p,
        unit_cost=10,supplier_lot='SUP-'+p,dye_lot='DYE-'+p)
    job=await post(h,'rfid/print-jobs',{'roll_ids':[roll['id']]})
    await post(h,'rfid/print-jobs/'+job['id']+'/mark-printed')
    sess=await post(h,'rfid/print-jobs/'+job['id']+'/verify/start')
    epc=job['items'][0]['epc']
    await post(h,'rfid/verify-sessions/'+sess['id']+'/scan',{'epcs':[epc],'source':'manual'})
    done=await post(h,'rfid/verify-sessions/'+sess['id']+'/complete')
    assert done['result']=='clean',done
    await post(h,'rfid/rolls/set-routing',{'roll_ids':[roll['id']],'routing':'store'})
    current=await e.db.inventory_rolls.find_one({'id':roll['id']},{'_id':0})
    assert current['journey']['stage']=='tag_verified' and current['rfid_tag_id']
    return current,epc
async def setup(h,key,unit='meter'):
    await warehouse(key+'-FROM',['transit']);await warehouse(key+'-TO',['storage'])
    await product(key,unit);r,epc=await verified(h,key,key+'-FROM')
    return r,epc
async def make_pa(h,r):
    return await post(h,'putaway-orders',{'from_warehouse_id':r['warehouse_id'],
        'to_warehouse_id':r['product_id']+'-TO','roll_ids':[r['id']]})
async def sales_order(h,p,qty,explicit_roll=None):
    customer='CUSTOMER-'+p
    await e.db.customers.insert_one(dict(id=customer,name='Synthetic audit customer '+p,
        entity_id='A',status='active',city='Jakarta',credit_limit=1000000,
        addresses=[dict(id='ADDR-'+p,city='Jakarta',address='Synthetic local audit')]))
    item=dict(product_id=p,quantity=qty,unit='meter')
    if explicit_roll:
        item.update(purchase_mode='roll',roll_lines=[dict(roll_id=explicit_roll['id'],take_qty=qty)],
            target_quantity=qty,rounding_choice='exact_cut' if qty<explicit_roll['length_remaining'] else 'exact')
    order=await post(h,'sales-orders',dict(customer_id=customer,shipping_address_id='ADDR-'+p,
        entity_id='A',items=[item]))
    assert 'id' in order and 'allocations' in order,order
    return order
async def snap(rid,oid=None):
    r=await e.db.inventory_rolls.find_one({'id':rid},{'_id':0})
    tag=await e.db.rfid_tags.find_one({'id':r.get('rfid_tag_id')},{'_id':0})
    balances=await e.db.inventory_balances.find({'product_id':r['product_id']},{'_id':0}).to_list(None)
    movements=await e.db.inventory_movements.find({'reference_id':oid},{'_id':0}).to_list(None) if oid else []
    order=await e.db.putaway_orders.find_one({'id':oid},{'_id':0}) if oid else None
    return dict(roll=r,tag=tag,balances=balances,movements=movements,order=order)
async def aging_release(h,collection,oid):
    # Clock aging is an explicit recovery fixture, not an original business write.
    await e.db[collection].update_one({'id':oid},{'$set':{
        'saga_lock.started_at':(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()}})
    inspect=await h.get('/api/saga-locks/'+collection+'/'+oid+'/inspect')
    assert inspect.status_code==200,(inspect.status_code,inspect.text)
    release=await post(h,'saga-locks/'+collection+'/'+oid+'/release',{
        'reason':'Synthetic audit effects inspected and acknowledged','acknowledge_effects':True,
        'lock_token':inspect.json()['lock'].get('token')})
    return dict(inspect=inspect.json(),release=release)

class CollectionBoundary:
    def __init__(self,original,method,callback):
        self.original=original;self.method=method;self.callback=callback
    def __getattr__(self,key):
        return self.callback if key==self.method else getattr(self.original,key)
class DatabaseBoundary:
    def __init__(self,original,collection,method,callback):
        self.original=original;self.collection=collection
        self.boundary=CollectionBoundary(original[collection],method,callback)
    def __getattr__(self,key):
        return self.boundary if key==self.collection else getattr(self.original,key)
    def __getitem__(self,key):
        return self.boundary if key==self.collection else self.original[key]

async def normal_and_reservation(h):
    r,epc=await setup(h,'NORMAL');order=await make_pa(h,r)
    await post(h,'putaway-orders/'+order['id']+'/dispatch')
    done=await post(h,'putaway-orders/'+order['id']+'/confirm-arrival',{'scanned_epcs':[epc]})
    s=await snap(r['id'],order['id'])
    rec('D4-PA-02-normal-movement-control',dict(status='completed',roll_wh='NORMAL-TO',
        tag_wh='NORMAL-TO',from_qty=0,to_qty=10,movement_count=2),dict(status=done['status'],
        roll_wh=s['roll']['warehouse_id'],tag_wh=s['tag']['warehouse_id'],
        from_qty=next(b['owned_qty'] for b in s['balances'] if b['warehouse_id']=='NORMAL-FROM'),
        to_qty=next(b['owned_qty'] for b in s['balances'] if b['warehouse_id']=='NORMAL-TO'),
        movement_count=len(s['movements'])))
    rec('D4-PA-02-normal-btg-control',True,bool(done['btg_number']))
    CONTEXT['normal_pa']=s
    for name,qty in [('WHOLE',10),('PARTIAL',6)]:
        r,epc=await setup(h,name);order=await make_pa(h,r)
        so=await sales_order(h,name,qty);alloc=so['allocations']
        current=await e.db.inventory_rolls.find_one({'id':r['id']},{'_id':0})
        rec('D4-PA-01-'+name.lower()+'-exclusive-claim',0,sum(a['quantity'] for a in alloc),
            'A successful PA claim must prevent conflicting sales allocation or explicitly coordinate/rebind it. Original public SO creator and allocator are used, not a mock. Subsequent approval/picking/shipping is not claimed tested.')
        dispatch=await h.post('/api/putaway-orders/'+order['id']+'/dispatch')
        if name=='WHOLE':
            rec('D4-PA-01-whole-dispatch-guard-control',409,dispatch.status_code,
                'The dispatch guard correctly rejects the now reserved roll, but reservation has already claimed a PA-owned roll.')
        else:
            rec('D4-PA-01-partial-dispatch-blocked',409,dispatch.status_code,
                'The partial reservation leaves status available with length_reserved6. Dispatch checks status only, so succeeds despite the simultaneous SO length reservation.')
            arrived=await h.post('/api/putaway-orders/'+order['id']+'/confirm-arrival',json={'scanned_epcs':[epc]})
            rec('D4-PA-01-partial-source-location-retained','PARTIAL-FROM',
                (await e.db.inventory_rolls.find_one({'id':r['id']}))['warehouse_id'],
                'Original sales allocation still points to PARTIAL-FROM while the reserved parent roll has moved to PARTIAL-TO.')
            CONTEXT['partial_arrival']=response(arrived)
        persisted=await e.db.sales_orders.find_one({'id':so['id']},{'_id':0})
        CONTEXT[name.lower()+'_reservation']=dict(order=persisted,allocations=alloc,before_dispatch=current,
            dispatch=response(dispatch),after=await snap(r['id'],order['id']))
    for name,qty in [('RMWHOLE',10),('RMPART',6)]:
        r,epc=await setup(h,name);order=await make_pa(h,r)
        so=await sales_order(h,name,qty,explicit_roll=r)
        rec('D4-PA-01-'+name.lower()+'-exclusive-claim',0,sum(a['quantity'] for a in so['allocations']),
            'Original public explicit-roll SO path also reserves a roll owned by an open PA; partial uses explicit exact_cut permission and choice.')
        rec('D4-PA-01-'+name.lower()+'-quantity-control',qty,so['items'][0]['reserved_qty'],
            'Original roll-mode allocation quantity is correct; do not mislabel this as a partial-qty overcount.')
        dispatch=await h.post('/api/putaway-orders/'+order['id']+'/dispatch')
        rec('D4-PA-01-'+name.lower()+'-dispatch-guard',409,dispatch.status_code)
        CONTEXT[name.lower()+'_reservation']=dict(so=so,pa=order,dispatch=response(dispatch),after=await snap(r['id'],order['id']))

async def pa_recovery(h):
    r,epc=await setup(h,'RECOVERY');order=await make_pa(h,r)
    await post(h,'putaway-orders/'+order['id']+'/dispatch')
    original=pa.db
    async def fail_tag(*args,**kwargs):
        raise RuntimeError('AUDIT boundary: roll location CAS persisted; tag update has not run')
    pa.db=DatabaseBoundary(original,'rfid_tags','update_one',fail_tag)
    try:first=await h.post('/api/putaway-orders/'+order['id']+'/confirm-arrival',json={'scanned_epcs':[epc]})
    finally:pa.db=original
    rec('D4-PA-02-fault-control',500,first.status_code)
    before=await snap(r['id'],order['id'])
    immediate=await h.post('/api/putaway-orders/'+order['id']+'/confirm-arrival',json={'scanned_epcs':[epc]})
    rec('D4-PA-02-immediate-lock-control',409,immediate.status_code)
    recovery=await aging_release(h,'putaway_orders',order['id'])
    rec('D4-PA-02-inspect-durable-roll-effect',True,bool(recovery['inspect']['effects']),
        'The roll has moved and lost active_movement. The admin effect scan only examines source_ref/created_at, so reports no effect for this existing roll update.')
    retry=await post(h,'putaway-orders/'+order['id']+'/confirm-arrival',{'scanned_epcs':[epc]})
    accept=await post(h,'putaway-orders/'+order['id']+'/resolve-exception',{'roll_ids':[r['id']],'action':'accept',
        'reason':'Physically arrived synthetic test; resume durable movement'})
    after=await snap(r['id'],order['id'])
    rec('D4-PA-02-retry-parent-finalized','completed',accept['status'])
    rec('D4-PA-02-retry-tag-location','RECOVERY-TO',after['tag']['warehouse_id'])
    rec('D4-PA-02-retry-audit-pair',2,len(after['movements']))
    rec('D4-PA-02-retry-destination-balance',10,sum(b['owned_qty'] for b in after['balances'] if b['warehouse_id']=='RECOVERY-TO'))
    rec('D4-PA-02-retry-source-balance',0,sum(b['owned_qty'] for b in after['balances'] if b['warehouse_id']=='RECOVERY-FROM'))
    rec('D4-PA-02-roll-is-at-destination-control','RECOVERY-TO',after['roll']['warehouse_id'])
    CONTEXT['pa_recovery']=dict(first=response(first),before=before,recovery=recovery,
        retry=retry,accept=accept,after=after)

async def unit_totals(h):
    await warehouse('UOM-FROM',['transit']);await warehouse('UOM-TO',['storage'])
    await product('METERS','meter');await product('YARDS','yard')
    rm,em=await verified(h,'METERS','UOM-FROM');ry,ey=await verified(h,'YARDS','UOM-FROM')
    suggested=await h.get('/api/putaway-orders/suggest',params={'from_warehouse_id':'UOM-FROM'})
    assert suggested.status_code==200,suggested.text
    groups=suggested.json()['groups'];g=groups[0]
    rec('D4-PA-03-input-base-units-control',['meter','yard'],sorted([rm['unit'],ry['unit']]))
    rec('D4-PA-03-mixed-group-validity',True,
        len(groups)>1 or (g['unit']=='meter' and g['qty']==19.144),
        'Two products in one owner/category/grade group use base units meter and yard. A single metre total must normalize10yard to9.144m or separate units, not sum20.')
    order=await post(h,'putaway-orders',{'from_warehouse_id':'UOM-FROM','to_warehouse_id':'UOM-TO',
        'roll_ids':[rm['id'],ry['id']]})
    shown_unit=order['items'][0]['unit'];correct=19.144 if shown_unit=='meter' else round(10/0.9144+10,4)
    rec('D4-PA-03-document-labelled-total',correct,order['total_qty'],
        'Actual frontend labels total_qty with items[0].unit, so20 native mixed units is an invalid labelled total. Per-roll quantities remain correct.')
    CONTEXT['mixed_units']=dict(suggestion=suggested.json(),order=order,
        frontend_contract='PutawayOrdersPanel.jsx: g.qty/g.unit and o.total_qty/o.items[0].unit',DOM_verified=False)

async def ready_metric(h):
    r,epc=await setup(h,'METRIC')
    before=await h.get('/api/wms/health-dashboard');suggest=await h.get('/api/putaway-orders/suggest',params={'from_warehouse_id':'METRIC-FROM'})
    getrow=lambda data:next(w for w in data['warehouses'] if w['warehouse_id']=='METRIC-FROM')
    rec('D4-WMS-04-ready-normal-control',1,suggest.json()['ready_count'])
    # Normal sales allocation is an original producer for status reserved; journey remains tag_verified.
    await sales_order(h,'METRIC',10)
    after=await h.get('/api/wms/health-dashboard');suggest_after=await h.get('/api/putaway-orders/suggest',params={'from_warehouse_id':'METRIC-FROM'})
    row=getrow(after.json())
    rec('D4-WMS-04-reserved-suggestion-control',0,suggest_after.json()['ready_count'])
    rec('D4-WMS-04-reserved-ready-kpi',0,row['putaway_ready'],
        'The same original reserved roll is counted as ready on Warehouse Health but excluded by the actual PA suggestion and rejected by PA creation.')
    refused=await h.post('/api/putaway-orders',json={'from_warehouse_id':'METRIC-FROM','to_warehouse_id':'METRIC-TO','roll_ids':[r['id']]})
    rec('D4-WMS-04-create-reserved-guard-control',400,refused.status_code)
    CONTEXT['ready_metric']=dict(before=before.json(),after=after.json(),suggest=suggest_after.json(),create=response(refused))

async def event_recovery(h):
    r,epc=await setup(h,'EVENT');order=await make_pa(h,r)
    await post(h,'putaway-orders/'+order['id']+'/dispatch')
    dev=await post(h,'rfid/devices',{'name':'Synthetic gate','type':'gate','direction':'out','warehouse_id':'EVENT-FROM'})
    key=await post(h,'rfid/devices/'+dev['id']+'/api-key')
    async def read(event_id):
        return await h.post('/api/rfid/ingest',headers={'X-Device-Key':key['api_key']},json={'events':[{'epc':epc,'event_id':event_id}]})
    original=ing.db
    async def fail_read(*args,**kwargs):
        raise RuntimeError('AUDIT boundary: observation and green gate_exit durable, read insert not run')
    ing.db=DatabaseBoundary(original,'rfid_reads','insert_many',fail_read)
    try:first=await read('AUDIT-LOST-READ')
    finally:ing.db=original
    rec('D4-RFID-01-fault-control',500,first.status_code)
    before=await e.db.inventory_rolls.find_one({'id':r['id']},{'_id':0})
    rec('D4-RFID-01-original-exit-stamp-control',order['id'],before.get('gate_exit',{}).get('movement_id'))
    replay=await read('AUDIT-LOST-READ');assert replay.status_code==200,replay.text
    rec('D4-RFID-01-retry-business-read',1,await e.db.rfid_reads.count_documents({'roll_id':r['id']}),
        'Event-ID dedupe treats the committed raw observation as processed even though the corresponding business read was never inserted.')
    rec('D4-RFID-01-retry-decision-count',1,replay.json()['count'])
    new=await read('AUDIT-NEW-READ');assert new.status_code==200,new.text
    rec('D4-RFID-01-fresh-event-recovery-verdict','MOVEMENT_OUT',new.json()['results'][0]['code'],
        'Gate_exit was stamped green before the failed read insertion; a new event is rejected REPLAY_EXIT, and creates a red incident instead of recovering the original green decision.')
    rec('D4-RFID-01-stock-unchanged-control','in_transit_transfer',
        (await e.db.inventory_rolls.find_one({'id':r['id']}))['status'],
        'RFID ingest correctly does not post stock movement; this is decision/event durability, not RFID reducing quantities.')
    CONTEXT['rfid_recovery']=dict(first=response(first),replay=response(replay),fresh=response(new),
        observations=await e.db.rfid_observations.find({'device_id':dev['id']},{'_id':0}).to_list(None),
        reads=await e.db.rfid_reads.find({'device_id':dev['id']},{'_id':0}).to_list(None),
        incidents=await e.db.rfid_incidents.find({'device_id':dev['id']},{'_id':0}).to_list(None))
    # Normal original event + same ID replay controls on a separate fresh movement.
    r2,e2=await setup(h,'EVENTCTRL');o2=await make_pa(h,r2);await post(h,'putaway-orders/'+o2['id']+'/dispatch')
    d2=await post(h,'rfid/devices',{'name':'Synthetic normal gate','type':'gate','direction':'out','warehouse_id':'EVENTCTRL-FROM'})
    k2=await post(h,'rfid/devices/'+d2['id']+'/api-key')
    payload={'events':[{'epc':e2,'event_id':'AUDIT-NORMAL'}]}
    n=await h.post('/api/rfid/ingest',headers={'X-Device-Key':k2['api_key']},json=payload)
    n2=await h.post('/api/rfid/ingest',headers={'X-Device-Key':k2['api_key']},json=payload)
    assert n.status_code==n2.status_code==200,(n.text,n2.text)
    rec('D4-RFID-01-normal-dedupe-control',dict(code='MOVEMENT_OUT',reads=1,duplicates=1),
        dict(code=n.json()['results'][0]['code'],reads=await e.db.rfid_reads.count_documents({'roll_id':r2['id']}),duplicates=n2.json()['duplicates']))
    # A different write boundary: read durable, then red incident/posting fails.
    # No physical alarm/kiosk rendering is claimed; original gate-status API is checked.
    from services import rfid_incident_service as incidents
    d3=await post(h,'rfid/devices',{'name':'Synthetic red gate','type':'gate','direction':'out','warehouse_id':'EVENTCTRL-FROM'})
    k3=await post(h,'rfid/devices/'+d3['id']+'/api-key')
    unknown='000000000000000000009999'
    async def red_read(event_id):
        return await h.post('/api/rfid/ingest',headers={'X-Device-Key':k3['api_key']},
            json={'events':[{'epc':unknown,'event_id':event_id}]})
    original_incident=incidents.create_from_read
    async def fail_incident(*args,**kwargs):
        raise RuntimeError('AUDIT boundary: original red read inserted, incident has not been created')
    incidents.create_from_read=fail_incident
    try:red_first=await red_read('AUDIT-RED-FAIL')
    finally:incidents.create_from_read=original_incident
    red_replay=await red_read('AUDIT-RED-FAIL');red_next=await red_read('AUDIT-RED-NEXT')
    assert red_first.status_code==500 and red_replay.status_code==red_next.status_code==200
    gate=await h.get('/api/rfid/gate/'+d3['id']+'/status');assert gate.status_code==200,gate.text
    rec('D4-RFID-01-red-read-durable-control',1,await e.db.rfid_reads.count_documents({'device_id':d3['id'],'result':'red'}))
    rec('D4-RFID-01-red-incident-recovery',1,await e.db.rfid_incidents.count_documents({'device_id':d3['id']}))
    rec('D4-RFID-01-red-passage-recovery','red',gate.json()['passage']['verdict'])
    rec('D4-RFID-01-red-latch-recovery',True,gate.json()['latched'])
    CONTEXT['rfid_red_recovery']=dict(first=response(red_first),same_event=response(red_replay),
        fresh_event=response(red_next),gate_status=gate.json(),DOM_verified=False,hardware_verified=False)

async def cycle_recovery(h):
    r,epc=await setup(h,'COUNT');sess=await post(h,'rfid/cycle-count/start',{'warehouse_id':'COUNT-FROM'})
    await post(h,'rfid/verify-sessions/'+sess['id']+'/scan',{'epcs':[epc],'source':'manual'})
    done=await post(h,'rfid/cycle-count/'+sess['id']+'/complete')
    second=await h.post('/api/rfid/cycle-count/'+sess['id']+'/complete')
    rec('D4-CC-01-normal-count-control',dict(accuracy=100,results=1,retry_http=400),
        dict(accuracy=done['accuracy_pct'],results=await e.db.rfid_cycle_counts.count_documents({'session_id':sess['id']}),retry_http=second.status_code))
    r2,e2=await setup(h,'COUNTFAIL');s2=await post(h,'rfid/cycle-count/start',{'warehouse_id':'COUNTFAIL-FROM'})
    await post(h,'rfid/verify-sessions/'+s2['id']+'/scan',{'epcs':[e2],'source':'manual'})
    original=cc.db
    async def lost_ack(*args,**kwargs):
        await original.rfid_cycle_counts.insert_one(*args,**kwargs)
        raise RuntimeError('AUDIT lost acknowledgment after original cycle-count insert')
    cc.db=DatabaseBoundary(original,'rfid_cycle_counts','insert_one',lost_ack)
    try:first=await h.post('/api/rfid/cycle-count/'+s2['id']+'/complete')
    finally:cc.db=original
    rec('D4-CC-01-fault-control',500,first.status_code)
    rec('D4-CC-01-first-result-persisted-control',1,await e.db.rfid_cycle_counts.count_documents({'session_id':s2['id']}))
    recovery=await aging_release(h,'rfid_verify_sessions',s2['id'])
    rec('D4-CC-01-inspect-count-effect',True,bool(recovery['inspect']['effects']))
    retried=await post(h,'rfid/cycle-count/'+s2['id']+'/complete')
    counts=await e.db.rfid_cycle_counts.find({'session_id':s2['id']},{'_id':0}).to_list(None)
    rec('D4-CC-01-one-session-one-result',1,len(counts),
        'Admin recovery succeeds, but completion creates a second independent CC number/result for the exact same session. Original startup indexes do not prevent duplicates by session_id.')
    CONTEXT['cycle_recovery']=dict(first=response(first),recovery=recovery,retry=retried,counts=counts)

async def retired_identity(h):
    r,epc=await setup(h,'RETIRED')
    retired=await h.delete('/api/rfid/tags/'+r['rfid_tag_id']);assert retired.status_code==200,retired.text
    current=await e.db.inventory_rolls.find_one({'id':r['id']},{'_id':0})
    rec('D4-TAG-01-retire-removes-current-tag-control',None,current.get('rfid_tag_id'))
    created=await h.post('/api/putaway-orders',json={'from_warehouse_id':'RETIRED-FROM','to_warehouse_id':'RETIRED-TO','roll_ids':[r['id']]})
    rec('D4-TAG-01-retired-putaway-rejected',True,created.status_code in (400,409),
        'The original verified roll was validly retired through the public API. Journey verification stays true, so PA accepts a roll with no current live tag and snapshots empty EPC. This is an original lifecycle counterexample, not an arbitrary tagless fixture.')
    CONTEXT['retired_identity']=dict(retire=response(retired),roll=current,pa=response(created))
    r2,e2=await setup(h,'PENDINGTAG')
    retired2=await h.delete('/api/rfid/tags/'+r2['rfid_tag_id']);assert retired2.status_code==200,retired2.text
    job=await post(h,'rfid/print-jobs',{'roll_ids':[r2['id']]})
    live=await e.db.inventory_rolls.find_one({'id':r2['id']},{'_id':0})
    pending=await e.db.rfid_tags.find_one({'id':live['rfid_tag_id']},{'_id':0})
    rec('D4-TAG-01-pending-print-control','pending_print',pending['status'])
    pending_pa=await h.post('/api/putaway-orders',json={'from_warehouse_id':'PENDINGTAG-FROM',
        'to_warehouse_id':'PENDINGTAG-TO','roll_ids':[r2['id']]})
    rec('D4-TAG-01-new-unverified-identity-rejected',True,pending_pa.status_code in (400,409),
        'New tag is pending_print and has never been verified; journey from the retired identity remains tag_verified and allows a new PA.')
    CONTEXT['pending_identity']=dict(print_job=job,roll=live,tag=pending,pa=response(pending_pa))

async def main():
    await e.seed()
    from indexes import ensure_performance_indexes
    CONTEXT['indexes']=await ensure_performance_indexes()
    CONTEXT['cycle_indexes']=await e.db.rfid_cycle_counts.index_information()
    await e.db.users.update_one({'id':'U'},{'$set':{'role':'admin','allowed_entity_ids':['A','B']}})
    await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{
        'wms':['view','scan','update','approve'],'order':['view','create','exact_cut']}}})
    async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),
        base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
        for name,fn in [('normal_and_reservation',normal_and_reservation),('pa_recovery',pa_recovery),
                        ('unit_totals',unit_totals),('ready_metric',ready_metric),('event_recovery',event_recovery),
                        ('cycle_recovery',cycle_recovery),('retired_identity',retired_identity)]:
            try:await fn(h)
            except Exception:ERRORS.append(dict(test=name,traceback=traceback.format_exc()))
    result=dict(commit='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,
        results=RESULTS,contexts=CONTEXT,harness_errors=ERRORS,external_connections=e.blocked)
    Path(__file__).with_name('wms-movement-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(dict(results=RESULTS,harness_errors=ERRORS),ensure_ascii=False))
    assert not ERRORS,ERRORS
asyncio.run(main())
