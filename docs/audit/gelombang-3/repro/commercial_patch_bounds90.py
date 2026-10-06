"""Public catalog/contract mutations must preserve numeric bounds of their producer contracts."""
import asyncio,json,traceback
from pathlib import Path
import wave2_env as e
RESULTS=[];ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def main():
 try:
  await e.seed()
  await e.db.permission_settings.update_one({'id':'default'},{'$set':{'matrix':{'finance':{'supplier_item':['create','view','update','delete','import'],'supplier_contract':['create','view','update','delete']}}}})
  await e.db.suppliers.insert_one({'id':'SUP','name':'Audit Supplier','entity_id':'A','status':'active'})
  await e.db.products.insert_one({'id':'P','name':'Audit Cloth','sku':'AUD-P','base_unit':'meter','unit':'meter','stage':'finished','fabric_type':'woven','status':'active','price':100,'harga_pokok':50})
  async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
   async def req(method,path,**kw):return await h.request(method,'/api'+path,**kw)
   item_body={'supplier_id':'SUP','product_id':'P','supplier_sku':'AUD-SUP','conv_factor':1,'last_price':10,'moq':1,'lead_time_days':1,'entity_id':'A'}
   r=await req('POST','/supplier-items',json=item_body);rec('bounds.item_valid_create',200,r.status_code);item=r.json();assert item.get('id'),r.text
   for field,val in [('last_price',-1),('moq',-1),('lead_time_days',-1)]:
    r=await req('POST','/supplier-items',json={**item_body,'supplier_sku':'NEW-'+field,field:val});rec('bounds.item_create_reject_'+field,422,r.status_code)
    r=await req('PATCH','/supplier-items/'+item['id'],json={field:val});rec('bounds.item_patch_reject_'+field,True,r.status_code in (400,422),str(r.status_code))
    stored=await e.db.supplier_items.find_one({'id':item['id']});rec('bounds.item_stored_nonnegative_'+field,True,stored[field]>=0)
    await req('PATCH','/supplier-items/'+item['id'],json={field:item_body[field]})
   r=await req('PATCH','/supplier-items/'+item['id'],json={'conv_factor':0});rec('bounds.item_factor_zero_guard',400,r.status_code)
   r=await req('POST','/supplier-items/import',json={'supplier_id':'SUP','entity_id':'A','rows':[{'supplier_sku':'CSV','sku':'AUD-P','last_price':'-1','conv_factor':'1'}],'dry_run':True});rec('bounds.item_csv_negative_rejected',1,r.json().get('invalid'))
   body={'contract_type':'purchase','partner_id':'SUP','product_id':'P','tariff_basis':'meter','tariff_rate':10,'entity_id':'A','status':'active','min_charge':0,'tariff_qty_source':'output'}
   r=await req('POST','/supplier-contracts',json=body);rec('bounds.contract_valid_create',200,r.status_code);contract=r.json();assert contract.get('id'),r.text
   for field,val in [('tariff_rate',-5),('min_charge',-1),('shrinkage_pct',101),('tolerance_pct',101),('byproduct_pct',101),('yield_factor',-1),('moq',-1),('lead_time_days',-1)]:
    r=await req('POST','/supplier-contracts',json={**body,field:val});rec('bounds.contract_create_reject_'+field,422,r.status_code)
    r=await req('PATCH','/supplier-contracts/'+contract['id'],json={field:val});rec('bounds.contract_patch_reject_'+field,True,r.status_code in (400,422),str(r.status_code))
    if field=='tariff_rate':
     preview=await req('POST','/supplier-contracts/tariff-preview',json={'product_id':'P','contract_id':contract['id'],'qty':10,'unit':'meter'})
     rec('bounds.contract_negative_rate_not_charged',True,preview.status_code in (400,422) or preview.json().get('amount',0)>=0,f'{preview.status_code}: {preview.text[:350]}')
    await req('PATCH','/supplier-contracts/'+contract['id'],json={field:10 if field=='tariff_rate' else 0})
 except Exception:ERRORS.append(traceback.format_exc())
 finally:
  Path(__file__).with_name('commercial-patch-bounds90-results.json').write_text(json.dumps(dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,harness_errors=ERRORS,scope='Original public ASGI producer, update, CSV preview and tariff-preview routes; isolated valid master records. Bounds mirror the domain constraints already enforced by original creation schemas.'),ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'observations':len(RESULTS),'differences':[r['id'] for r in RESULTS if r['status']!='pass'],'errors':ERRORS}));e.client.close()
if __name__=='__main__':asyncio.run(main())
