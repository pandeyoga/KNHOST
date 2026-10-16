"""Read-only resource GET coverage with actual seeded synthetic resources, not invented IDs."""
import asyncio,ast,inspect,json,re,traceback,textwrap,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
import wave2_env as e
from seed_realistic import seed_all
results=[]
async def main():
    assert e.db.name.startswith('knhost_audit_') and await e.db.users.count_documents({})==0
    await seed_all(e.db)
    entities=[x['id'] async for x in e.db.business_entities.find({'status':'active'},{'id':1})]
    actor=await e.db.users.find_one({'role':'admin'})
    await e.db.users.update_one({'id':actor['id']},{'$set':{'allowed_entity_ids':entities}})
    entity=actor.get('home_entity_id') or entities[0]
    await e.db.sessions.insert_one({'token':'audit-resource-session','user_id':actor['id'],'expires_at':datetime.now(timezone.utc)+timedelta(hours=2)})
    perms={}
    for p in (e.REPO/'backend/routers').glob('*.py'):
        for n in ast.walk(ast.parse(p.read_text(encoding='utf-8-sig'))):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='require_permission' and len(n.args)>2 and isinstance(n.args[1],ast.Constant) and isinstance(n.args[2],ast.Constant):perms.setdefault(n.args[1].value,set()).add(n.args[2].value)
    await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{k:sorted(v) for k,v in perms.items()}}},upsert=True)
    base=json.loads(Path(__file__).with_name('get-contract-results.json').read_text(encoding='utf-8'))
    gaps={r['path'] for r in base['results'] if r['status']=='not_executed'}
    if '--remaining' in sys.argv:
        prior=json.loads(Path(__file__).with_name('get-resource-results.json').read_text(encoding='utf-8'))
        gaps-={r['path'] for r in prior['results'] if r['status'] in ('executed','exception')}
    coll_names=await e.db.list_collection_names(); samples={}
    for name in coll_names:
        samples[name]=await e.db[name].find({},{'_id':0}).limit(4).to_list(4)
    def collections(fn,depth=2,seen=None):
        seen=seen or set()
        if fn in seen:return []
        seen.add(fn)
        try:src=inspect.getsource(fn);tree=ast.parse(textwrap.dedent(src))
        except (OSError,TypeError,SyntaxError,IndentationError):return []
        found=list(dict.fromkeys(re.findall(r'db\.([A-Za-z_][A-Za-z_0-9]*)',src)))
        for n in ast.walk(tree):
            if not isinstance(n,ast.Subscript) or not isinstance(n.value,ast.Name) or n.value.id!='db':continue
            key=None
            if isinstance(n.slice,ast.Constant):key=n.slice.value
            elif isinstance(n.slice,ast.Name):key=fn.__globals__.get(n.slice.id)
            elif isinstance(n.slice,ast.Attribute) and isinstance(n.slice.value,ast.Name):key=getattr(fn.__globals__.get(n.slice.value.id),n.slice.attr,None)
            if isinstance(key,str) and key in samples:found.append(key)
        for n in ast.walk(tree):
            if not isinstance(n,ast.Call) or not depth:continue
            f=None
            if isinstance(n.func,ast.Name):f=fn.__globals__.get(n.func.id)
            elif isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name):f=getattr(fn.__globals__.get(n.func.value.id),n.func.attr,None)
            if inspect.isfunction(f) and f.__module__.startswith(('services.','routers.')):found+=collections(f,depth-1,seen)
        return list(dict.fromkeys(found))
    def choices(route,param):
        preferred={'product_id':['products'],'warehouse_id':['warehouses'],'from_warehouse_id':['warehouses'],'customer_id':['customers'],'source_id':['customers'],'supplier_id':['suppliers'],'employee_id':['hr_employees'],'roll_id':['inventory_rolls'],'tag_id':['rfid_tags'],'lot_id':['inventory_lots'],'so_id':['sales_orders'],'order_id':['sales_orders'],'po_id':['purchase_orders'],'user_id':['users'],'run_id':['hr_payroll_runs'],'account_id':['bank_accounts'],'bank_account_id':['bank_accounts'],'device_id':['rfid_devices'],'session_id':['rfid_cycle_counts'],'gate_id':['rfid_gates'],'doc_id':['sales_orders']}.get(param,[])
        hint={'orders':'sales_orders','purchase-orders':'purchase_orders','customers':'customers','products':'products','vendors':'suppliers','suppliers':'suppliers','journal':'journal_entries','journal-entries':'journal_entries','ar-receipts':'ar_receipts','vendor-bills':'vendor_bills','bank-transactions':'bank_transactions','cash-transactions':'cash_transactions','cycle-counts':'rfid_cycle_counts','opname':'stock_opnames','special-orders':'special_orders','design-requests':'design_requests','samples':'md_samples','warehouses':'warehouses','tags':'rfid_tags','rolls':'inventory_rolls'}
        preferred += [hint[x] for x in route.path.split('/') if x in hint]
        cols=preferred+collections(route.endpoint)
        out=[]
        for col in dict.fromkeys(cols):
            if col in ('sessions','permission_settings','audit_logs','number_sequences'):continue
            for doc in samples.get(col,[]):
                key='id'
                if param in ('sku','product_sku'):key='sku'
                elif param in ('code','account_code'):key='code'
                elif param in ('epc','epc_hex'):key='epc'
                elif param=='number':key='number'
                value=doc.get(key)
                if value is not None:out.append((str(value),col,doc.get('id')))
            if out:break
        if param in ('entity_id','from_entity_id'):return [(entity,'business_entities',entity)]
        if param=='to_entity_id':return [(next(x for x in entities if x!=entity),'business_entities',None)]
        if param=='line_code':
            lines=[d.get('code') or d.get('line_code') for d in samples.get('business_lines',[])]
            if not any(lines):lines=[d.get('line_code') for d in samples.get('products',[])]
            return [(str(x),'seeded_product_line',None) for x in lines if x][:1]
        return out[:4]
    routes=[r for r in e.server.app.routes if 'GET' in getattr(r,'methods',set()) and r.path in gaps]
    async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=True),base_url='http://audit.local',headers={'Authorization':'Bearer audit-resource-session','X-Entity-Id':entity}) as h:
        for i,r in enumerate(routes):
            row={'path':r.path,'handler':r.endpoint.__module__+'.'+r.endpoint.__name__,'status':'not_executed','attempts':[]};params={};missing=[]
            if '/callback' in r.path:row['reason']='External callback requires external auth flow';results.append(row);continue
            for f in r.dependant.query_params:
                if not f.required:continue
                name=f.alias
                if name in ('start','end','date_from','date_to','as_of','day','date'):params[name]=datetime.now(timezone.utc).date().isoformat()
                elif name in ('month','period'):params[name]=datetime.now(timezone.utc).strftime('%Y-%m')
                elif name=='entity_id':params[name]=entity
                elif name=='year':params[name]=datetime.now(timezone.utc).year
                elif name in ('subtotal','amount','price','length'):params[name]=100 if name!='length' else 1
                elif name=='line_no':params[name]=0
                elif name=='period_type':params[name]='month'
                elif name=='period_key':params[name]=datetime.now(timezone.utc).strftime('%Y-%m')
                elif name=='hex':params[name]='#ff0000'
                elif name=='doc_type':params[name]='sales_order'
                elif name=='number' and samples.get('sales_orders'):params[name]=samples['sales_orders'][0]['number']
                elif name=='designer':params[name]=actor.get('name','')
                else:
                    opts=choices(r,name)
                    if opts:params[name]=opts[0][0]
                    else:missing.append(name)
            path=r.path;binds=[]
            for param in re.findall(r'\{([^}:]+)(?::[^}]+)?\}',path):
                opts=choices(r,param)
                if not opts:missing.append(param)
                else:binds.append((param,opts))
            if missing:row['reason']='No coherent seed resource/query for '+','.join(missing)
            else:
                # For routes with multiple keys, preserve one explicit candidate binding; arbitrary cross-product IDs are not used.
                variants=range(min(len(binds[0][1]),4)) if len(binds)==1 else range(1)
                for v in variants:
                    concrete=path; provenance=[]
                    for param,opts in binds:
                        value,col,docid=opts[v if len(binds)==1 else 0];concrete=re.sub(r'\{'+re.escape(param)+r'(?::[^}]+)?\}',value,concrete);provenance.append({'param':param,'collection':col,'id':docid})
                    attempt={'resource_binding':provenance,'concrete_path':concrete}
                    try:
                        resp=await asyncio.wait_for(h.get(concrete,params=params),15)
                        attempt.update(http_status=resp.status_code,content_type=resp.headers.get('content-type',''))
                        if resp.status_code>=400 and attempt['content_type'].startswith('application/json'):attempt['detail']=str(resp.json().get('detail',''))[:220]
                        row['status']='executed'
                    except Exception as ex:attempt.update(error=repr(ex),traceback=traceback.format_exc());row['status']='exception'
                    row['attempts'].append(attempt)
                    if attempt.get('http_status',999)<400 or 'error' in attempt:break
            results.append(row)
            if i%30==0:print('RESOURCE_GET',i+1,len(routes),flush=True)
            filename='get-resource-results-round-2.json' if '--remaining' in sys.argv else 'get-resource-results.json'
            Path(__file__).with_name(filename).write_text(json.dumps({'commit':'d6da1a3d536228582645abb98aea19f3e491f300','database':e.db.name,'note':'Seeded synthetic resources, readonly GET attempts. Collection hints may not resolve the correct lifecycle; non200 is not a bug verdict. Multiple-key foreign-key coherence is not asserted by this sweep. Execution/shape is not business/arithmetic coverage.','results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print('COUNTS',dict(__import__('collections').Counter(x['status'] for x in results)),flush=True)
asyncio.run(main())
