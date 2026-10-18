"""Wave 2: real local Mongo + ASGI; synthetic fixtures, no external services."""
import os,sys,asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
sys.settrace(None)
from services import makloon_order_service as m,roll_service as rolls
from fastapi import HTTPException
db=e.db
results=[]
def record(id,observed,ok,kind='control'):
    print("OBS",(id,observed),flush=True)
    results.append(dict(id=id,kind=kind,observed=observed))
    print(id,json.dumps(observed),flush=True)
async def fixture(tag):
    mid='W2-'+tag; inp=mid+'-IN'; out=mid+'-OUT'
    for pid in (inp,out):
        await db.products.insert_one(dict(id=pid,sku=pid,name=pid,base_unit='meter',harga_pokok=10,price=10,grade='A'))
    await rolls.create_inbound_roll(inp,'WH','A',10,unit_cost=10,lot=mid+'-RAW',acquired_via='purchase',ref_id=mid)
    await db.makloon_orders.insert_one(dict(id=mid,mko_number=mid,entity_id='A',status='draft',from_warehouse_id='WH',target_warehouse_id='WH',timeline=[],steps=[dict(seq=1,status='pending',material_flow='moves',process_type='dyeing',input_product_id=inp,output_product_id=out,input_qty=10,input_unit='meter',output_unit='meter',expected_output_qty=10,issue_ref=mid+':1',makloon_id='PARTNER',tariff_basis='lumpsum',tariff_rate=20,tolerance_pct=10)]))
    await m.issue_step(mid,1,actor_name='Audit')
    return mid,out
async def state(mid,out):
    order=await db.makloon_orders.find_one({'id':mid})
    rs=await db.inventory_rolls.find({'product_id':out}).to_list(100)
    je=await db.journal_entries.find_one({'source_type':'subcon_receipt','source_id':mid+':1'})
    return dict(status=order['status'],step_status=order['steps'][0]['status'],quantity=sum(r['length_remaining'] for r in rs),roll_value=round(sum(r['length_remaining']*r['unit_cost'] for r in rs),4),journal_value=je['total_debit'] if je else 0,warehouses=[r['warehouse_id'] for r in rs],roll_count=len(rs))
def payload(tag,length=10,actual=10,warehouse='WH'):
    return dict(step_seq=1,actual_output_qty=actual,tariff=20,output_warehouse_id=warehouse,rolls=[dict(lot=tag,length=length)])
async def main():
    await e.seed()
    await db.warehouses.insert_one(dict(id='WH',name='Audit warehouse',entity_id='A',status='active'))
    await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.makloon_order':['view','receive','issue']}})
    mid,out=await fixture('NORMAL');await m.receive_step(mid,1,payload('NORMAL'))
    s=await state(mid,out);record('W2-M-C01',s,s['quantity']==10 and s['roll_value']==120 and s['journal_value']==120)
    try:await m.receive_step(mid,1,payload('RETRY'))
    except HTTPException as ex:record('W2-M-C02',{'http_status':ex.status_code,'unchanged':s==await state(mid,out)},ex.status_code==409 and s==await state(mid,out))
    mid,out=await fixture('MISMATCH')
    transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False)
    async with e.httpx.AsyncClient(transport=transport,base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as http:
        r=await http.post('/api/makloon-orders/'+mid+'/receive',json=payload('MISMATCH',9.5))
        s=await state(mid,out);record('W2-M-F01',{'http_status':r.status_code,**s},r.status_code==200 and s['quantity']==9.5 and s['roll_value']==114 and s['journal_value']==120,'defect')
        mid,out=await fixture('BADWH')
        r=await http.post('/api/makloon-orders/'+mid+'/receive',json=payload('BADWH',warehouse='NONEXISTENT-WAREHOUSE'))
        s=await state(mid,out);record('W2-M-F02',{'http_status':r.status_code,**s},r.status_code==200 and s['warehouses']==['NONEXISTENT-WAREHOUSE'],'defect')
    mid,out=await fixture('REJECT')
    try:await m.receive_step(mid,1,payload('REJECT',9.49))
    except HTTPException as ex:
        s=await state(mid,out);record('W2-M-C03',{'http_status':ex.status_code,**s},ex.status_code==400 and s['step_status']=='issued' and s['roll_count']==0 and s['journal_value']==0)
    mid,out=await fixture('PARTIAL')
    # Stage fixture only: this tests final absorption, not GRN creation/closing.
    await db.makloon_orders.update_one({'id':mid},{'$set':{'steps.0.partial_receipts':[dict(grn_id='SYNTHETIC-PARTIAL',grn_number='PARTIAL',out_qty=4,by_qty=0,posted=False,rolls=[dict(lot='PARTIAL-4',length=4)])]}})
    await m.receive_step(mid,1,payload('FINAL-6',6,6))
    s=await state(mid,out);record('W2-M-C04',s,s['quantity']==10 and s['roll_count']==2 and s['roll_value']==120 and s['journal_value']==120)
    mid,out=await fixture('CANCEL')
    await db.makloon_orders.update_one({'id':mid},{'$set':{'steps.0.partial_receipts':[dict(grn_id='CANCEL-GRN',grn_number='CANCEL-GRN',out_qty=4,posted=False,rolls=[dict(lot='CANCEL-4',length=4)])]}})
    await db.goods_receipts.insert_one(dict(id='CANCEL-GRN',status='closed',version=1))
    await m.cancel_partial_receipt(mid,1,'CANCEL-GRN','Synthetic cancellation',{'id':'U','name':'Audit'})
    o=await db.makloon_orders.find_one({'id':mid});g=await db.goods_receipts.find_one({'id':'CANCEL-GRN'})
    record('W2-M-C05',{'partials':len(o['steps'][0]['partial_receipts']),'grn_status':g['status']},not o['steps'][0]['partial_receipts'] and g['status']=='cancelled')
    try:await m.cancel_partial_receipt(mid,1,'CANCEL-GRN','Synthetic retry',{'id':'U','name':'Audit'})
    except HTTPException as ex:record('W2-M-C06',{'http_status':ex.status_code},ex.status_code==404)
    from services.goods_receipt_close_service import _post_mko
    await db.warehouses.insert_one(dict(id='WH2',name='Second audit warehouse',entity_id='A',status='active'))
    mid,out=await fixture('PARTIAL-WH')
    def line(lot,qty):
        return {'counted':{'qty':qty,'makloon_rolls':[{'lot':lot,'length':qty,'grade':'A'}]}}
    await _post_mko({'id':'PWH-GRN1','number':'PWH1','warehouse_id':'WH','mko_partial':True},mid,1,[line('ARRIVED-WH',4)],{'id':'U','name':'Audit'})
    await _post_mko({'id':'PWH-GRN2','number':'PWH2','warehouse_id':'WH2','mko_partial':False},mid,1,[line('ARRIVED-WH2',6)],{'id':'U','name':'Audit'})
    rs=await db.inventory_rolls.find({'product_id':out},{'_id':0,'lot':1,'warehouse_id':1,'length_remaining':1}).to_list(10)
    record('W2-M-F03',{'receipt_warehouses':['WH','WH2'],'output_rolls':rs},len(rs)==2 and all(r['warehouse_id']=='WH2' for r in rs),'defect')
async def run():
    try:await main()
    finally:
        dest=Path(__file__).parent.parent
        dest.mkdir(exist_ok=True)
        sha=subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip()
        (dest/'makloon-results.json').write_text(json.dumps({'commit':sha,'database':e.DBNAME,'level':'real Mongo + service; F01/F02 via ASGI HTTP; no application lifespan','scenarios':results},indent=2),encoding='utf-8')
        e.client.close()
asyncio.run(run())
