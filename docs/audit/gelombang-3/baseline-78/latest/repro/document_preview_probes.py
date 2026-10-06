"""Original template creator/list and preview APIs, valid read-state SO fixture."""
import asyncio,json
from pathlib import Path
import wave2_env as e
from core_utils import now_iso
async def main():
    await e.seed();db=e.db;results=[]
    def rec(key,expected,actual,note=''):
        results.append(dict(id=key,expected=expected,actual=actual,note=note,
            status='pass' if expected==actual else 'observed_difference'))
    await db.users.update_one({'id':'U'},{'$set':{'role':'admin'}})
    await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.admin':{
        'template':['view','create'],'document':['view','create'],'order':['view']}}})
    await db.products.insert_one({'id':'PDOC','name':'Preview fabric','sku':'PDOC','base_unit':'meter','status':'active'})
    await db.customers.insert_one({'id':'CDOC','name':'Synthetic customer','entity_id':'A','status':'active'})
    so={'id':'SO-DOC','number':'SO-DOC','entity_id':'A','customer_id':'CDOC','customer_name':'Synthetic customer',
        'status':'confirmed','order_date':now_iso(),'created_at':now_iso(),'subtotal':100,'total_amount':100,
        'grand_total':100,'discount_amount':0,'tax_amount':0,'paid_total':0,
        'items':[{'product_id':'PDOC','sku':'PDOC','product_name':'Preview fabric','quantity':1,
            'base_quantity':1,'unit':'meter','unit_price':100,'line_total':100,'subtotal':100}]}
    await db.sales_orders.insert_one(dict(so))
    async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),
        base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
        r=await h.post('/api/document-templates',json={'name':'Audit Surat Jalan Template',
            'document_type':'surat_jalan','header':'AUDIT SELECTED TEMPLATE','columns':['sku','quantity']})
        assert r.status_code==200,(r.status_code,r.text)
        template=r.json();listed=await h.get('/api/document-templates')
        rec('D4-DOC-01-existing-template-control',{'http':200,'exists':True},
            {'http':listed.status_code,'exists':any(t['id']==template['id'] for t in listed.json())})
        # Exact request body and URL used by original useAppActions.previewTemplate.
        payload={'document_type':'invoice','source_id':so['id'],'actor':'Audit User A'}
        missing=await h.post('/api/document-templates/'+template['id']+'/preview',json=payload)
        rec('D4-DOC-01-preview-contract',200,missing.status_code,
            'A real original-created template and an accessible SO are present. No registered POST endpoint exists at the UI preview path. This is not empty data/auth failure.')
        alternative=await h.get('/api/documents/preview/'+so['id'],params={'document_type':'surat_jalan'})
        rec('D4-DOC-01-alternative-renderer-control',{'http':200,'html':True},
            {'http':alternative.status_code,'html':'text/html' in alternative.headers.get('content-type','')},
            'Existing GET document preview renderer works for this read-state fixture. It does not accept selected template ID, so merely repointing the button is insufficient.')
    data={'commit':'a904d989b622f7da14c4892d03cf6ef0c43f3084','database':db.name,'results':results,
        'fixture_scope':'Original public template creation/listing; SO is an explicit valid read-state fixture, not whole SO producer/fulfillment proof',
        'template':template,'order':so,'original_request':payload,'missing_response':{'http':missing.status_code,'body':missing.json()},
        'alternative_http':alternative.status_code,'external_connections':e.blocked,'harness_errors':[]}
    Path(__file__).with_name('document-preview-api-results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False))
asyncio.run(main())
