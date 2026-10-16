"""Isolated execution of original WMS functions; no live app or real database.

Functions are compiled from original AST, without rewriting their logic.
Only framework, auth and database boundaries are replaced by in-memory doubles.
This establishes behavior of selected functions, not deployment readiness.
"""
import ast
import asyncio
import copy
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

ROOT=next((p for p in Path(__file__).resolve().parents if (p/'work/KNHOST-guide-2026-10-07').is_dir()),Path.cwd())
REPO=Path(os.environ.get('WMS_AUDIT_REPO',ROOT/'work/KNHOST-guide-2026-10-07')).resolve()
assert REPO.is_dir(), 'Set WMS_AUDIT_REPO to the audited checkout.'
head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()
assert head=='f59b8a60d7b7e078888c537ca93c046afae460a9', f'Unexpected checkout: {head}'
OUT=ROOT/'output/memo/wms-developer-2026-10-08'
OUT.mkdir(parents=True,exist_ok=True)

class HTTPException(Exception):
    def __init__(self,status_code,detail):
        self.status_code=status_code; self.detail=detail
        super().__init__(detail)

def value(doc,path):
    for part in path.split('.'):
        if not isinstance(doc,dict):
            return None
        doc=doc.get(part)
    return doc

def eq(a,b):
    return b in a if isinstance(a,list) and not isinstance(b,list) else a==b

def matches(doc,q):
    for k,wanted in q.items():
        if k=='$or':
            if not any(matches(doc,x) for x in wanted): return False
            continue
        got=value(doc,k)
        if isinstance(wanted,dict):
            for op,v in wanted.items():
                if op=='$in' and got not in v: return False
                if op=='$ne' and eq(got,v): return False
                if op=='$gt' and not (got is not None and got>v): return False
                if op=='$exists' and bool(got is not None)!=bool(v): return False
                if op=='$not' and matches(doc,{k:v}): return False
        elif not eq(got,wanted):
            return False
    return True

def project(doc,p):
    if not p: return copy.deepcopy(doc)
    incl=[k for k,v in p.items() if v and k!='_id']
    if incl: return {k:copy.deepcopy(value(doc,k)) for k in incl if value(doc,k) is not None}
    return {k:copy.deepcopy(v) for k,v in doc.items() if p.get(k,1)}

def set_path(doc,path,v):
    names=path.split('.')
    for k in names[:-1]: doc=doc.setdefault(k,{})
    doc[names[-1]]=copy.deepcopy(v)

class Cursor:
    def __init__(self,rows,p=None): self.rows=[project(r,p) for r in rows]
    async def to_list(self,n): return copy.deepcopy(self.rows[:n])
    def __aiter__(self):
        async def gen():
            for r in self.rows: yield copy.deepcopy(r)
        return gen()

class Collection:
    def __init__(self,rows=None): self.rows=copy.deepcopy(rows or [])
    def find(self,q,p=None): return Cursor([r for r in self.rows if matches(r,q)],p)
    async def find_one(self,q,p=None):
        return next((project(r,p) for r in self.rows if matches(r,q)),None)
    async def update_one(self,q,upd,**kw):
        for r in self.rows:
            if matches(r,q):
                for k,v in upd.get('$set',{}).items(): set_path(r,k,v)
                for k in upd.get('$unset',{}): r.pop(k,None)
                return SimpleNamespace(modified_count=1,matched_count=1)
        return SimpleNamespace(modified_count=0,matched_count=0)
    async def insert_one(self,row): self.rows.append(copy.deepcopy(row))

def make_db(warehouses,rolls,tags=None):
    return SimpleNamespace(warehouses=Collection(warehouses),inventory_rolls=Collection(rolls),
                           inventory_movements=Collection(),rfid_tags=Collection(tags),
                           putaway_orders=Collection())

serial=itertools.count()
async def no_effect(*a,**kw): return None
async def auth(*a,**kw): return {'name':'Test actor'}
async def next_number(*a,**kw): return 'PA-TEST'

def load_functions(path,names,ns):
    tree=ast.parse((REPO/path).read_text(encoding='utf-8-sig'))
    selected=[]
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names:
            n.decorator_list=[]; selected.append(n)
    assert {n.name for n in selected}==set(names)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),ns)

base={'Any':Any,'Dict':Dict,'List':List,'Optional':Optional,'Tuple':Tuple,
      'HTTPException':HTTPException,'EntityContext':Any,'Request':Any,'PutawayIn':Any,
      'new_id':lambda p:f'{p}_{next(serial)}','now_iso':lambda:'2026-10-08T00:00:00Z',
      'next_doc_number':next_number,'safe_doc':lambda v:copy.deepcopy(v),
      'resolve_list_scope':lambda collection,q,ctx,entity:q,
      'set_journey':no_effect,'require_permission':auth}

roll_source=ast.parse((REPO/'backend/services/roll_service.py').read_text(encoding='utf-8-sig'))
physical=next(ast.literal_eval(n.value) for n in roll_source.body
              if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PHYSICAL_STATUS_TO_BUCKET' for t in n.targets))
package=ModuleType('services'); package.__path__=[]
roll_stub=ModuleType('services.roll_service')
roll_stub.PHYSICAL_STATUS_TO_BUCKET=physical
roll_stub.rebuild_balance=no_effect
sys.modules['services']=package; sys.modules['services.roll_service']=roll_stub

loc=dict(base)
load_functions('backend/services/location_service.py',
               ['flatten_bins','_bin_occupancy','warehouse_locations','_ensure_ids',
                'save_warehouse_structure','putaway_roll'],loc)
scan=dict(base)
load_functions('backend/routers/inbound_scan_label.py',['putaway_scanned_roll'],scan)
profile=dict(base)
load_functions('backend/services/warehouse_profile_service.py',['check_storage_rules'],profile)
pa=dict(base,whp=SimpleNamespace(check_storage_rules=profile['check_storage_rules']),PA_ELIGIBLE_STATUS='available')
load_functions('backend/services/putaway_order_service.py',['identity_issue','create_order','_release_claims'],pa)
transfer=dict(base,NO_LENGTH_RESERVED={'$not':{'$gt':0}})
load_functions('backend/services/roll_service.py',['reserve_rolls_for_wh_transfer'],transfer)

def warehouse(whid='wh-a',bid='bin-1',capacity=50,**fields):
    return {'id':whid,'name':whid,'zones':[{'id':'z1','name':'Zona A','racks':[{
        'id':'r1','name':'Rak 1','levels':[{'id':'l1','name':'Tingkat 1','bins':[
            {'id':bid,'code':'BIN-01','capacity':capacity}]}]}]}],**fields}

def roll(rid='roll-1',qty=100,unit='meter',**fields):
    return {'id':rid,'roll_no':rid,'product_id':'p1','warehouse_id':'wh-a',
            'owner_entity_id':'ent-a','length_remaining':qty,'unit':unit,'status':'available',**fields}

results=[]
def record(name,observed,expectation,issue=True,classification='defect'):
    results.append({'probe':name,'issue_reproduced':issue,'classification':classification,
                    'observed':observed,'expected_control':expectation})

async def main():
    db=make_db([warehouse()], [roll(status='receiving',grn_task_id='grn-1')])
    scan['db']=db
    async def task(*a): return {'id':'grn-1','warehouse_id':'wh-a'}
    scan['_load_task']=task
    flat=loc['flatten_bins'](db.warehouses.rows[0])
    try:
        await scan['putaway_scanned_roll']('roll-1',SimpleNamespace(bin_code='BIN-01',bin_id=''),None)
    except HTTPException as e:
        assert e.status_code==400 and len(flat)==1
        record('P01-scan-modern-bin',{'flatten_bin_count':len(flat),'scan_status':e.status_code,'message':e.detail},
               'Scan dan editor menemukan bin yang sama pada rack.levels[].bins.')
    else: raise AssertionError('P01 did not reject modern bin')

    db=make_db([warehouse()], [roll(bin_id='bin-1')]); loc['db']=db
    before=await loc['warehouse_locations']('wh-a',None,None)
    await loc['save_warehouse_structure']('wh-a',[])
    after=await loc['warehouse_locations']('wh-a',None,None)
    assert before['total_occupied']==100 and after['total_occupied']==0 and after['unassigned']['qty']==0
    record('P02-delete-occupied-bin',{'before_occupied':100,'after_occupied':after['total_occupied'],
           'after_unassigned':after['unassigned'],'roll_qty_unchanged':db.inventory_rolls.rows[0]['length_remaining']},
           'Struktur berisi stok tidak dapat dihapus tanpa migrasi; orphan harus terlihat.')

    db=make_db([warehouse(capacity=50)], [roll(bin_id='bin-1'),roll('roll-2',100,'kg',bin_id='bin-1')]); loc['db']=db
    view=await loc['warehouse_locations']('wh-a',None,None)
    assert view['total_occupied']==200 and view['bins'][0]['utilization']==400
    record('P03-mixed-uom-occupancy',{'meter':100,'kg':100,'reported_occupied':view['total_occupied'],
           'reported_utilization':view['bins'][0]['utilization'],'ui_label':'m'},
           '100 meter dan 100 kg ditampilkan terpisah; kapasitas memakai dimensi/satuan yang ditetapkan.')

    db=make_db([warehouse(capacity=50)], [roll(bin_id=None)]); loc['db']=db
    assigned=await loc['putaway_roll']('roll-1','bin-1','Test')
    assert assigned['bin_id']=='bin-1'
    record('P04-putaway-over-capacity',{'capacity':50,'roll_qty':100,'assigned':assigned['bin_id']},
           'Aturan kapasitas menolak/memperingatkan sesuai kebijakan yang disetujui.',classification='capability_gap')

    db=make_db([warehouse()], [roll(status='in_transit_transfer',bin_id=None)]); loc['db']=db
    assigned=await loc['putaway_roll']('roll-1','bin-1','Test')
    assert assigned['bin_id']=='bin-1'
    record('P05-putaway-transit-roll',{'roll_status':'in_transit_transfer','assigned':assigned['bin_id']},
           'Aksi penempatan fisik menolak roll yang masih dalam perjalanan.')

    target=warehouse('wh-b','bin-b',sharing_mode='dedicated',entity_ids=['ent-b'],roles=['storage'],active=True)
    source=warehouse(roles=['transit'],active=True)
    tag={'id':'tag-1','status':'active','roll_id':'roll-1','epc':'EPC-1'}
    ready=roll(bin_id=None,rfid_tag_id='tag-1',grade='A',journey={'stage':'tag_verified','verified_tag_id':'tag-1'})
    db=make_db([source,target],[ready],[tag]); db.products=Collection([{'id':'p1','sku':'P1','name':'P1','category':'Woven'}]); pa['db']=db
    order=await pa['create_order']('wh-a','wh-b',['roll-1'],['ent-a'],'Test')
    assert order['owner_entity_id']=='ent-a' and order['to_warehouse_id']=='wh-b'
    record('P06-pa-dedicated-destination',{'owner':order['owner_entity_id'],'destination_allowed_owners':['ent-b'],
           'created_status':order['status']},
           'PA wajib memvalidasi gudang tujuan usable bagi pemilik roll, sama dengan transfer biasa.')

    combined={'name':'Woven A only','storage_rules':{'mode':'category','categories':['Woven'],'grades':['A']}}
    check=profile['check_storage_rules'](combined,'Woven','BS')
    assert check['ok']
    record('P07-rules-category-plus-grade',{'rules':combined['storage_rules'],'product_category':'Woven',
           'roll_grade':'BS','accepted':check['ok']},
           'Kombinasi kategori DAN grade harus eksplisit; mode saat ini hanya memeriksa satu dimensi.',classification='capability_gap')

    db=make_db([warehouse()], [roll(status='reserved',reserved_ref={'type':'sales_order','id':'so-1'})]); transfer['db']=db
    try:
        await transfer['reserve_rolls_for_wh_transfer']('p1','wh-a','ent-a',100,'trf-1',roll_ids=['roll-1'])
    except HTTPException as e:
        assert e.status_code==409
        record('P08-so-reservation-to-transfer',{'roll_status':'reserved','reserved_for':'sales_order',
               'transfer_status':e.status_code,'message':e.detail},
               'Pemenuhan via gudang lain perlu jalur pemindahan dengan komitmen SO terjaga atau replan resmi.',classification='business_flow_gap')
    else: raise AssertionError('P08 unexpectedly accepted a sales-order reserved roll')

    db=make_db([warehouse()], [roll(bin_id=None,inspection={'hold':{'held':True,'reason':'Warna berbeda'}})]); loc['db']=db
    try: await loc['putaway_roll']('roll-1','bin-1','Test')
    except HTTPException as e:
        assert e.status_code==400
        record('C01-existing-inspection-hold-control',{'status':e.status_code,'blocked':True},
               'Kontrol hold inspeksi tetap dipertahankan pada perbaikan putaway.',issue=False,classification='existing_control')
    else: raise AssertionError('C01 hold unexpectedly accepted')

    report={'method':'Original functions compiled from AST with in-memory database and boundary doubles; no live HTTP, real MongoDB or RFID device.',
            'source_commit':'f59b8a60d7b7e078888c537ca93c046afae460a9','cases':results,
            'observed_issues':sum(r['issue_reproduced'] for r in results),'control_checks':sum(not r['issue_reproduced'] for r in results),
            'defects':sum(r['classification']=='defect' for r in results),
            'capability_gaps':sum(r['classification'] in ['capability_gap','business_flow_gap'] for r in results)}
    (OUT/'wms-focused-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

asyncio.run(main())
