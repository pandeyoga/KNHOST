"""Execute original functions with a strict, bounded in-memory dependency model.
Not Mongo, HTTP integration, hardware or browser testing.
"""
import ast,asyncio,copy,json,sys,types,typing,uuid,logging,itertools
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
BASE=Path(__file__).parent; ROOT=Path(__import__('os').environ.get('KNHOST_REPO',str(BASE/'KNHOST')))
RESULTS=[]; IDS=itertools.count(1); MISSING=object()
class HTTPException(Exception):
    def __init__(self,status_code,detail):
        self.status_code=status_code; self.detail=detail; super().__init__(str(detail))
def uid(prefix): return f'{prefix}_{next(IDS)}'
async def number(*a,**k): return uid('DOC')
async def nop(*a,**k): return None
def get(d,key,default=None):
    for part in key.split('.'):
        if not isinstance(d,dict) or part not in d:return default
        d=d[part]
    return d
def setv(d,key,v):
    parts=key.split('.')
    for part in parts[:-1]: d=d.setdefault(part,{})
    d[parts[-1]]=copy.deepcopy(v)
def unset(d,key):
    parts=key.split('.')
    for part in parts[:-1]:
        d=d.get(part,{})
    d.pop(parts[-1],None)
def equal(a,b):
    if a is MISSING: return b is None
    return b in a if isinstance(a,list) and not isinstance(b,list) else a==b
def match(d,q):
    for key,w in q.items():
        if key=='$or':
            if not any(match(d,x) for x in w):return False
            continue
        if key=='$and':
            if not all(match(d,x) for x in w):return False
            continue
        a=get(d,key,MISSING)
        if not isinstance(w,dict):
            if not equal(a,w):return False
            continue
        for op,v in w.items():
            if op=='$exists': ok=(a is not MISSING)==bool(v)
            elif op=='$in': ok=any(equal(a,x) for x in v)
            elif op=='$nin': ok=not any(equal(a,x) for x in v)
            elif op=='$ne': ok=not equal(a,v)
            elif op=='$gt': ok=a is not MISSING and a>v
            elif op=='$gte': ok=a is not MISSING and a>=v
            elif op=='$lt': ok=a is not MISSING and a<v
            elif op=='$lte': ok=a is not MISSING and a<=v
            else: raise NotImplementedError(op)
            if not ok:return False
    return True
def project(d,p):
    d=copy.deepcopy(d)
    if not p:return d
    included=[k for k,v in p.items() if v and k!='_id']
    if included:
        out={}
        for k in included:
            v=get(d,k,MISSING)
            if v is not MISSING:setv(out,k,v)
        return out
    for k,v in p.items():
        if not v:unset(d,k)
    return d
def mutate(d,upd):
    for op,fields in upd.items():
        for k,v in fields.items():
            if op=='$set':setv(d,k,v)
            elif op=='$unset':unset(d,k)
            elif op=='$inc':setv(d,k,get(d,k,0)+v)
            elif op=='$push':setv(d,k,get(d,k,[])+[v])
            elif op=='$addToSet':
                old=get(d,k,[]); vals=v.get('$each',[]) if isinstance(v,dict) else [v]
                setv(d,k,old+[x for x in vals if x not in old])
            else:raise NotImplementedError(op)
class Cursor:
    def __init__(self,rows,p):self.rows=copy.deepcopy(rows);self.p=p
    def sort(self,key,direction=1):
        self.rows.sort(key=lambda d:get(d,key,''),reverse=direction<0);return self
    async def to_list(self,n):return [project(r,self.p) for r in self.rows[:n]]
class Collection:
    def __init__(self,rows=()):
        self.rows=copy.deepcopy(list(rows));self.after_find=None;self.after_cas=None;self.fail_insert=False
    def find(self,q,p=None):return Cursor([r for r in self.rows if match(r,q)],p)
    async def find_one(self,q,p=None,**kw):
        rows=[r for r in self.rows if match(r,q)]
        result=project(rows[0],p) if rows else None
        if self.after_find:await self.after_find(q,result)
        return result
    async def insert_one(self,d):
        if self.fail_insert:raise RuntimeError('injected insert failure')
        self.rows.append(copy.deepcopy(d));return types.SimpleNamespace(inserted_id=d.get('id'))
    async def insert_many(self,ds):
        for d in ds:await self.insert_one(d)
    async def update_one(self,q,u,**kw):
        for r in self.rows:
            if match(r,q):
                old=copy.deepcopy(r);mutate(r,u)
                return types.SimpleNamespace(matched_count=1,modified_count=int(old!=r))
        return types.SimpleNamespace(matched_count=0,modified_count=0)
    async def update_many(self,q,u):
        n=0
        for r in self.rows:
            if match(r,q):mutate(r,u);n+=1
        return types.SimpleNamespace(matched_count=n,modified_count=n)
    async def find_one_and_update(self,q,u,projection=None,return_document=None):
        for r in self.rows:
            if match(r,q):
                old=copy.deepcopy(r);mutate(r,u)
                result=project(r if return_document else old,projection)
                if self.after_cas:await self.after_cas(q,u,result)
                return result
        return None
    async def delete_one(self,q):
        for i,r in enumerate(self.rows):
            if match(r,q):self.rows.pop(i);return types.SimpleNamespace(deleted_count=1)
        return types.SimpleNamespace(deleted_count=0)
    async def bulk_write(self,ops):
        for x in ops:await self.update_one(x.q,x.u)
class DB:
    def __init__(self,**rows):
        for k,v in rows.items():setattr(self,k,Collection(v))
    def __getattr__(self,k):
        c=Collection();setattr(self,k,c);return c
    def __getitem__(self,k):return getattr(self,k)
class UpdateOne:
    def __init__(self,q,u):self.q=q;self.u=u
PM=types.ModuleType('pymongo');PM.UpdateOne=UpdateOne;PM.ReturnDocument=types.SimpleNamespace(AFTER=True)
sys.modules['pymongo']=PM
def package():
    m=types.ModuleType('services');m.__path__=[];sys.modules['services']=m;return m
def module(file,names,db=None,**bindings):
    tree=ast.parse((ROOT/file).read_text(encoding='utf-8-sig'))
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
    assert len(nodes)==len(names),(file,set(names)-{n.name for n in nodes})
    for n in nodes:n.decorator_list=[]
    m=types.ModuleType('services.'+Path(file).stem)
    m.__dict__.update({k:v for k,v in vars(typing).items() if not k.startswith('__')})
    m.__dict__.update(db=db,HTTPException=HTTPException,uuid=uuid,new_id=uid,
                     now_iso=lambda:'2026-09-28T12:00:00Z',next_doc_number=number,
                     safe_doc=lambda x:copy.deepcopy(x),ReturnDocument=PM.ReturnDocument,
                     logger=logging.getLogger('review2'),**bindings)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(ROOT/file),'exec'),m.__dict__)
    sys.modules[m.__name__]=m
    setattr(sys.modules['services'],Path(file).stem,m)
    return m
def stub(name,**funcs):
    m=types.ModuleType('services.'+name);m.__dict__.update(funcs)
    sys.modules[m.__name__]=m;setattr(sys.modules['services'],name,m);return m
def setup(db):
    package()
    module('backend/services/atomic_claim.py',['claim','finish_set','release','mark_failed'],db,LOCK='saga_lock')
    return module('backend/services/rfid_print_service.py',['set_journey','generate_rfid_zpl','_verify_progress','scan_verify','complete_verify'],db)
def record(id,kind,observed,condition,meaning):
    assert condition,(id,observed)
    RESULTS.append(dict(id=id,kind=kind,observed=observed,meaning=meaning))
def roll(id='R',**extra):
    return dict(id=id,roll_no=id,product_id='P',warehouse_id='W1',owner_entity_id='A',
                length_initial=100,length_remaining=100,status='available',unit='meter',
                unit_cost=10,created_at=id,**extra)
async def run():
    # Original EPC encode -> generated ZPL -> real ingest function.
    db=DB(inventory_rolls=[roll()],products=[{'id':'P','name':'Fabric','sku':'P'}])
    pr=setup(db)
    rf=module('backend/services/rfid_service.py',['generate_epc','encode_tag'],db,
              PHYSICAL_STATUSES=['available'])
    gate=module('backend/services/rfid_ingest_service.py',['_doc_gate_decision','ingest','authenticate','heartbeat'],db,
                GREEN_OUT_STATUSES={'reserved','allocated','committed','picked','packed','in_transit_sales','in_transit_transfer','delivered','consumed'})
    stub('rfid_incident_service',create_from_read=nop)
    tag=await rf.encode_tag('R',['A'])
    wire=pr.generate_rfid_zpl(tag['epc'],roll(),tag).split('^RFW,H^FD')[1].split('^FS')[0]
    raw=await gate.ingest({'id':'D','type':'handheld','warehouse_id':'W1'},[wire])
    formatted=await gate.ingest({'id':'D','type':'handheld','warehouse_id':'W1'},[tag['epc']])
    record('V2-01','defect',{'raw_result':raw['results'][0]['result'],'stored_format_result':formatted['results'][0]['result']},
           raw['results'][0]['reason'].startswith('EPC tidak dikenal') and formatted['results'][0]['result']=='info',
           'RF-01 survives full encode/ZPL/ingest chain in dependency model.')
    db.putaway_orders.rows=[{'id':'PA','status':'cancelled','from_warehouse_id':'W1','to_warehouse_id':'W2','pa_number':'PA-1'}]
    r=roll();r.update(status='quarantine',journey={'stage':'putaway_in_transit','putaway_order_id':'PA'})
    result=await gate._doc_gate_decision({'direction':'out','warehouse_id':'W1'},r)
    record('V2-02','defect',result,result['result']=='green','PA branch precedes QC block and ignores cancelled PA status.')
    db.rfid_devices.rows=[{'id':'D','api_key':'synthetic-review-key','status':'offline'}]
    device=await gate.authenticate('synthetic-review-key');await gate.heartbeat(device)
    record('V2-03','defect',{'before':'offline','after':db.rfid_devices.rows[0]['status']},
           db.rfid_devices.rows[0]['status']=='online','Actual UI Matikan uses offline; heartbeat silently turns it online.')

    db=DB(sales_orders=[{'id':'SO','entity_id':'A','number':'SO-1'}],
          inventory_rolls=[{**roll('R1'),'status':'committed','rfid_tag_id':'T1','reserved_ref':{'type':'sales_order','id':'SO'}},
                           {**roll('R2'),'status':'committed','reserved_ref':{'type':'sales_order','id':'SO'}}],
          rfid_tags=[{'id':'T1','epc':'E1','status':'active'}])
    pr=setup(db)
    lc=module('backend/services/loading_check_service.py',['_expected_rolls','start','complete','dispatch_guard'],db,
              EXPECTED_STATUSES=['reserved','committed','picked','packed','allocated'])
    sess=await lc.start('SO',['A'],'operator')
    await pr.scan_verify(sess['id'],['E1'],['A']);end=await lc.complete(sess['id'],['A']);await lc.dispatch_guard('SO')
    record('V2-04','defect',{'untagged':sess['untagged_count'],'result':end['result'],'dispatch_allowed':True},
           sess['untagged_count']==1 and end['result']=='clean','RF-05: subset verification reaches dispatch guard as clean.')

    db=DB(rfid_verify_sessions=[{'id':'S','kind':'cycle_count','print_job_id':None,'owner_entity_id':'A','status':'open',
                                'expected':[{'epc':'E1','roll_id':'R'}],'scanned_epcs':['E1']}],
          inventory_rolls=[roll()])
    pr=setup(db);end=await pr.complete_verify('S',['A'])
    record('V2-05','defect',{'session_status':end['status'],'roll_journey':db.inventory_rolls.rows[0]['journey'],'cycle_count_reports':len(db.rfid_cycle_counts.rows)},
           end['status']=='completed' and db.inventory_rolls.rows[0]['journey']['stage']=='tag_verified',
           'RF-10: wrong completion endpoint consumes a cycle count as print verify and changes roll journey.')

    db=DB(rfid_verify_sessions=[{'id':'S','owner_entity_id':'A','status':'open','expected':[{'epc':'A'},{'epc':'B'}],'scanned_epcs':[]}])
    pr=setup(db);barrier=asyncio.Event();reads=0
    async def after_read(q,result):
        nonlocal reads
        if result and not result.get('scanned_epcs'):
            reads+=1
            if reads==2:barrier.set()
            await barrier.wait()
    db.rfid_verify_sessions.after_find=after_read
    await asyncio.gather(pr.scan_verify('S',['A'],['A']),pr.scan_verify('S',['B'],['A']))
    record('V2-06','defect',{'accepted_requests':2,'stored':db.rfid_verify_sessions.rows[0]['scanned_epcs']},
           len(db.rfid_verify_sessions.rows[0]['scanned_epcs'])==1,'RF-10: concurrent union/read/set loses one accepted EPC.')

    db=DB(inventory_rolls=[roll()])
    setup(db)
    rs=module('backend/services/roll_service.py',['insert_child_roll','_split_roll'],db,child_roll_no=number)
    entered=asyncio.Event();resume=asyncio.Event()
    async def after_cas(q,u,result):
        if asyncio.current_task().get_name()=='split-A':
            entered.set();await resume.wait()
    db.inventory_rolls.after_cas=after_cas
    ta=asyncio.create_task(rs._split_roll(roll(),30,'SOA'),name='split-A')
    await entered.wait();await rs._split_roll(roll(),40,'SOB');resume.set();await ta
    total=sum(r['length_remaining'] for r in db.inventory_rolls.rows)
    record('V2-07','defect',{'start_qty':100,'end_qty':total,'lengths':[r['length_remaining'] for r in db.inventory_rolls.rows]},
           total==140,'WM-01 deterministic interleaving executes original stale normalization after CAS.')

    db=DB(inventory_rolls=[{**roll(),'status':'committed','reserved_ref':{'type':'sales_order','id':'SO'},'rfid_tag_id':'T'}])
    setup(db)
    rs=module('backend/services/roll_service.py',['insert_child_roll','ship_order_rolls'],db,
              child_roll_no=number,SHIPPABLE_STATUSES=['committed','picked','packed'],rebuild_balance=nop)
    shipped=await rs.ship_order_rolls('SO','P','W1',30)
    child=next(r for r in db.inventory_rolls.rows if r['id']!='R')
    record('V2-08','defect',{'shipment_roll':shipped['rolls'][0]['roll_id'],'child_tag':child['rfid_tag_id'],'child_status':child['status']},
           child['rfid_tag_id'] is None and child['status']=='in_transit_sales',
           'Dispatch can create untagged child after any loading verification; identity checked before dispatch no longer equals shipped identity.')

    # PA full function; real bulk plans applied by the local collection model.
    db=DB(warehouses=[{'id':'W1','name':'Transit'},{'id':'W2','name':'D'}],
          products=[{'id':'P','sku':'P','name':'Fabric'}],
          inventory_rolls=[{**roll(),'status':'quarantine','journey':{'stage':'tag_verified'},'rfid_tag_id':'T'}],
          rfid_tags=[{'id':'T','roll_id':'R','epc':'E','status':'active'}])
    pr=setup(db);stub('roll_service',rebuild_balance=nop)
    pa=module('backend/services/putaway_order_service.py',['create_order','_get','dispatch','confirm_arrival'],db,
              set_journey=pr.set_journey,whp=types.SimpleNamespace(check_storage_rules=lambda *a:{'ok':True}))
    p=await pa.create_order('W1','W2',['R'],['A'],'op')
    record('V2-09','defect',{'pa_status':p['status'],'roll_status':db.inventory_rolls.rows[0]['status']},
           p['status']=='open','PA creation verifies tag journey/storage category but accepts QC quarantine.')
    arrived=await pa.confirm_arrival(p['id'],[],['A'],'op')
    record('V2-10','defect',{'scanned':[],'arrived_count':arrived['arrived_count'],'warehouse':db.inventory_rolls.rows[0]['warehouse_id']},
           arrived['arrived_count']==1,'WM-03 empty list equals unrestricted arrival; original bulk function executed.')

    db=DB(putaway_orders=[{'id':'PA','pa_number':'PA-1','status':'open','owner_entity_id':'A','from_warehouse_id':'W1','to_warehouse_id':'W2',
                          'items':[{'roll_id':'R','epc':'E','qty':100,'unit':'meter','product_id':'P','status':'pending'}]}],
          inventory_rolls=[{**roll(),'length_remaining':70,'warehouse_id':'W3','status':'delivered','owner_entity_id':'B'}])
    pr=setup(db);stub('roll_service',rebuild_balance=nop)
    pa=module('backend/services/putaway_order_service.py',['_get','confirm_arrival'],db,set_journey=pr.set_journey)
    await pa.confirm_arrival('PA',['E'],['A'],'op')
    r=db.inventory_rolls.rows[0];mov=db.inventory_movements.rows[-1]
    record('V2-11','defect',{'roll_owner':r['owner_entity_id'],'roll_qty':r['length_remaining'],'roll_warehouse':r['warehouse_id'],
                           'movement_owner':mov['owner_entity_id'],'movement_qty':mov['quantity']},
           r['warehouse_id']=='W2' and mov['quantity']==100 and r['length_remaining']==70,
           'PA parent claim does not revalidate roll owner/source/status/quantity; stale document can move newer state.')

    db=DB(inventory_rolls=[{**roll(),'status':'in_transit_transfer','reserved_ref':{'type':'wh_transfer','id':'TR'},
                           'acquired':{'via':'inbound','ref_id':'PO'},'bin_id':'BIN-W1'}])
    setup(db)
    rs=module('backend/services/roll_service.py',['receive_wh_transfer_rolls'],db,rebuild_balance=nop)
    await rs.receive_wh_transfer_rolls('TR','W2')
    r=db.inventory_rolls.rows[0]
    record('V2-12','defect',{'warehouse':r['warehouse_id'],'bin':r['bin_id'],'acquired':r['acquired'],
                           'po_cost_selector_matches':match(r,{'acquired.ref_id':{'$in':['PO']}})},
           r['acquired']['ref_id']=='TR' and r['bin_id']=='BIN-W1',
           'Warehouse receipt overwrites procurement provenance and retains source bin. Late landed-cost PO selection misses transferred roll.')

    async def shipment_fixture():
        db=DB(inventory_rolls=[
            {**roll('OLD'),'length_initial':50,'length_remaining':50,'status':'committed','reserved_ref':{'type':'sales_order','id':'SO'}},
            {**roll('NEW'),'length_initial':50,'length_remaining':50,'status':'committed','reserved_ref':{'type':'sales_order','id':'SO'}}])
        db.inventory_rolls.rows[0]['created_at']='1';db.inventory_rolls.rows[1]['created_at']='2'
        setup(db)
        rs=module('backend/services/roll_service.py',['ship_order_rolls','insert_child_roll'],db,
                  SHIPPABLE_STATUSES=['committed','picked','packed'],rebuild_balance=nop,child_roll_no=number)
        stub('doc_refs_service',safe_link=nop);stub('special_order_phase2',on_shipment_dispatched=nop)
        stub('gl_service',post_order_revenue_and_cogs=nop)
        sh=module('backend/services/shipment_service.py',['dispatch_task','_next_shipment_no'],db,
                  EPS=.01,NON_DISPATCHABLE={'dispatched','cancelled','escalated'},
                  ship_order_rolls=rs.ship_order_rolls,recompute_so_status=nop)
        task={'id':'TASK','flow_type':'outbound','status':'packing','quantity':100,'picked_qty':100,'shipped_qty':0,
              'order_id':'SO','product_id':'P','warehouse_id':'W1','entity_id':'A','roll_id':'NEW',
              'scan_log':[{'scan_type':'pick','roll_id':'NEW','actual_qty':50}]}
        db.wms_tasks.rows=[copy.deepcopy(task)]
        return db,sh,task
    db,sh,task=await shipment_fixture()
    task['picked_qty']=50;db.wms_tasks.rows[0]['picked_qty']=50
    _,shipment=await sh.dispatch_task(task,50,'op')
    record('V2-13','defect',{'picked_roll':task['roll_id'],'shipped_roll':shipment['rolls'][0]['roll_id']},
           shipment['rolls'][0]['roll_id']=='OLD','Picked identity is not dispatch selection; dispatch uses qty/FEFO despite scan_log/roll_id.')
    db,sh,task=await shipment_fixture();db.shipments.fail_insert=True
    try:await sh.dispatch_task(task,100,'op')
    except RuntimeError:pass
    current=db.wms_tasks.rows[0]
    record('V2-14','defect',{'task_status':current['status'],'has_lock':'saga_lock' in current,'shipments':len(db.shipments.rows),
                           'roll_statuses':[r['status'] for r in db.inventory_rolls.rows]},
           current['status']=='dispatched' and 'saga_lock' not in current and not db.shipments.rows,
           'Failure after finish_set before shipment insert leaves dispatched task/transit rolls without shipment; no saga lock exposes recovery.')
    db,sh,task=await shipment_fixture()
    await sh.dispatch_task(copy.deepcopy(task),30,'A')
    await sh.dispatch_task(copy.deepcopy(task),30,'B')
    record('V2-15','defect',{'task_shipped_qty':db.wms_tasks.rows[0]['shipped_qty'],
                           'shipment_sum':sum(r['qty'] for r in db.shipments.rows)},
           db.wms_tasks.rows[0]['shipped_qty']==30 and sum(r['qty'] for r in db.shipments.rows)==60,
           'Two requests with same pre-read task can both claim sequentially; partial status remains allowed, stale shipped_qty overwrites progress.')

    # Correct original audit's unconditional zero-cost allegation.
    db=DB(products=[{'id':'P','base_unit':'meter','harga_pokok':100}]);setup(db)
    async def lot(*a,**k):return {'id':'LOT','lot_number':'LOT-1'}
    async def base_qty(prod,qty,unit):return qty
    stub('lot_service',resolve_or_create=lot,recompute=nop)
    rs=module('backend/services/roll_service.py',['create_inbound_roll','apply_cycle_count_adjustment'],db,
              _lot_for_segment=number,to_base_qty=base_qty,_norm_grade=lambda x:x,_domain_snapshot=lambda p:{},
              next_roll_no=number,rebuild_balance=nop)
    await rs.apply_cycle_count_adjustment('P','W1','A',10,'CC')
    record('V2-16','correction',{'surplus_qty':db.inventory_rolls.rows[0]['length_remaining'],'unit_cost':db.inventory_rolls.rows[0]['unit_cost']},
           db.inventory_rolls.rows[0]['unit_cost']==100,
           'FN-14 zero-cost is conditional: surplus inherits product.harga_pokok=100, not always zero. Missing variance GL remains separate defect.')
    db=DB(inventory_rolls=[{**roll(),'owner_entity_id':'B'}]);setup(db)
    calls=[]
    async def rebuild(*a,**k):calls.append(a)
    rs=module('backend/services/roll_service.py',['reserve_rolls_for_wh_transfer'],db,rebuild_balance=rebuild)
    reserved=await rs.reserve_rolls_for_wh_transfer('P','W1','A',100,'TR',['R'])
    record('V2-17','defect',{'requested_owner':'A','reserved_owner':reserved[0]['owner_entity_id'],'rebuild_calls':len(calls)},
           reserved[0]['owner_entity_id']=='B' and len(calls)==0,
           'Explicit roll transfer path omits owner filter and returns before balance rebuild; original service executed.')
    db=DB(inventory_rolls=[{**roll('A-ROLL'),'owner_entity_id':'A','rfid_tag_id':'TA'},
                              {**roll('B-ROLL'),'owner_entity_id':'B','rfid_tag_id':'TB'}],
          rfid_tags=[{'id':'TA','status':'active','epc':'AAAA'},{'id':'TB','status':'active','epc':'BBBB'}])
    pr=setup(db)
    pr=module('backend/services/rfid_print_service.py',['create_print_job','get_print_job','set_journey'],db,
              rfid_service=types.SimpleNamespace(),generate_rfid_zpl=lambda *a:'synthetic ZPL')
    job=await pr.create_print_job(['A-ROLL','B-ROLL'],['A','B'],'multi-owner')
    exposed=await pr.get_print_job(job['id'],['A'])
    record('V2-18','defect',{'job_owner':job['owner_entity_id'],'viewer_scope':['A'],
                           'visible_rolls':[x['roll_id'] for x in exposed['items']]},
           any(x['roll_id']=='B-ROLL' for x in exposed['items']),
           'Authorized multi-owner job creation stamps first owner; later A-only caller receives B-owned roll through get_print_job.')
    db=DB();setup(db)
    rs=module('backend/services/roll_service.py',['insert_child_roll'],db,child_roll_no=number)
    parent={**roll('CHILD'),'parent_roll_id':'ROOT','root_roll_id':'ROOT'}
    child={**parent,'id':'GRANDCHILD'}
    result=await rs.insert_child_roll(child,parent)
    record('V2-19','defect',{'actual_immediate_parent':'CHILD','stored_parent':result['parent_roll_id'],'root':result['root_roll_id']},
           result['parent_roll_id']=='ROOT',
           'Copied child carries its existing parent_roll_id; setdefault preserves grandparent for a new second-generation cut.')
    order_results={}
    for order in ('parent_first','child_first'):
        db=DB(inventory_rolls=[{**roll('ROOT'),'length_initial':70,'length_remaining':70,'unit_cost':100},
                              {**roll('CHILD'),'length_initial':30,'length_remaining':30,'unit_cost':100,'parent_roll_id':'ROOT','root_roll_id':'ROOT'}]);setup(db)
        lc=module('backend/services/landed_cost_service.py',['apply_allocation_to_rolls'],db,
                  roll_cost_history=types.SimpleNamespace(record=nop))
        alloc=[{'roll_id':'ROOT','per_unit':1,'alloc_amount':70},{'roll_id':'CHILD','per_unit':1,'alloc_amount':30}]
        await lc.apply_allocation_to_rolls('LC',alloc if order=='parent_first' else list(reversed(alloc)))
        order_results[order]=sum((r['unit_cost']-100)*r['length_remaining'] for r in db.inventory_rolls.rows)
    record('V2-20','defect',order_results,order_results=={'parent_first':130,'child_first':100},
           'FN-01 is order-dependent: same voucher allocations produce total stock-cost uplift 130 or 100; not universally double in every order.')
    db=DB(inventory_rolls=[roll()]);setup(db)
    rs=module('backend/services/roll_service.py',['insert_child_roll','_split_roll'],db,child_roll_no=number)
    await rs._split_roll(copy.deepcopy(db.inventory_rolls.rows[0]),30,'SOA')
    await rs._split_roll(copy.deepcopy(db.inventory_rolls.rows[0]),40,'SOB')
    total=sum(r['length_remaining'] for r in db.inventory_rolls.rows)
    record('V2-C1','control',{'start_qty':100,'end_qty':total},total==100,
           'Sequential split with fresh parent snapshots conserves quantity; V2-07 requires specified concurrency interleaving.')
    db=DB(putaway_orders=[{'id':'PA','pa_number':'PA-1','status':'in_transit','from_warehouse_id':'W1','to_warehouse_id':'W2'}]);setup(db)
    gate=module('backend/services/rfid_ingest_service.py',['_doc_gate_decision'],db,GREEN_OUT_STATUSES=set())
    r=roll();r.update(journey={'stage':'putaway_in_transit','putaway_order_id':'PA'})
    result=await gate._doc_gate_decision({'direction':'in','warehouse_id':'WRONG'},r)
    record('V2-C2','control',result,result['result']=='red',
           'Active PA IN branch does reject wrong destination; RF-03 concerns transit fallback, not every IN decision.')

if __name__=='__main__':
    asyncio.run(run())
    out={'method':'Original AST function bodies; controlled async interleavings and fault injection; dependency model, not Mongo/HTTP/hardware.',
         'results':RESULTS}
    (BASE/'review2_flow_proofs.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
