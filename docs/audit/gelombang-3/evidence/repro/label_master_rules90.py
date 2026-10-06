"""Supplier label decoding, catalog import/CRUD and contract tariff arithmetic oracles."""
import asyncio,io,json,traceback
from pathlib import Path
import service_env90 as e
from services import label_decoder_service as d,supplier_item_service as si,contract_service as cs,customer_price_service as cp
RESULTS=[];ERRORS=[]
def rec(key,want,actual,note=''):
 RESULTS.append(dict(id=key,expected=want,actual=actual,note=note,status='pass' if want==actual else 'observed_difference'))
async def reject(key,call):
 try:await call;out=False
 except (si.SupplierItemError,cs.ContractError,ValueError):out=True
 rec(key,True,out)
async def main():
 try:
  await e.setup(template=True)
  for raw,p,fields in [
   ('SKU|LOT|ROLL|12,5|2,25|NAVY',{'format':'delimited'},{'supplier_sku':'SKU','lot':'LOT','roll_no':'ROLL','length':12.5,'weight_kg':2.25,'color_code':'NAVY'}),
   ('{"sku":"SKU","lot":"LOT","roll":"ROLL","m":12.5,"kg":2.25,"color":"NAVY"}',{'format':'qr_json'},{'supplier_sku':'SKU','length':12.5,'length_unit':'meter','weight_kg':2.25}),
   ('{"item":"SKU","yd":"12,5","uom":"yard"}',None,{'supplier_sku':'SKU','length':12.5,'length_unit':'yard'}),
   ('{"article":"SKU","qty":10,"satuan":"meter"}',None,{'supplier_sku':'SKU','length':10.0,'length_unit':'meter'}),
   ('X-SKU/123',{'format':'regex','regex':r'X-(?P<supplier_sku>\w+)/(?P<length>\d+)'},{'supplier_sku':'SKU','length':123.0}),
   ('{"my_code":"CUSTOM","my_qty":"10,5"}',{'format':'qr_json','json_keys':{'supplier_sku':['my_code'],'length':['my_qty']}},{'supplier_sku':'CUSTOM','length':10.5}),
   ('(01)09506000134352(10)LOT(21)R1(3103)002250(3112)001250',{'format':'gs1'},{'gtin':'09506000134352','lot':'LOT','roll_no':'R1','weight_kg':2.25,'length':12.5,'length_unit':'meter'}),
   (']C1010950600013435231030022503232001250',None,{'gtin':'09506000134352','weight_kg':2.25,'length':12.5,'length_unit':'yard'}),
   ('240SKU\x1d10LOT\x1d21R1\x1d3002',None,{'supplier_sku':'SKU','lot':'LOT','roll_no':'R1','count':2.0})]:
   out=d.decode(raw,p)
   for field,want in fields.items():rec('label.'+str(len(RESULTS))+'.'+field,want,out[field])
  for raw,p in [('',None),('not a label',None),('[1]',{'format':'qr_json'}),('{bad',{'format':'qr_json'}),('bad',{'format':'regex'}),('bad',{'format':'regex','regex':'['}),('zzz',{'format':'regex','regex':'a+'}),('abc',{'format':'delimited'}),('8899ABC',{'format':'gs1'}),('(XX)ABC',{'format':'gs1'})]:
   try:d.decode(raw,p);out=False
   except d.LabelDecodeError:out=True
   rec('label.reject_'+str(len(RESULTS)),True,out)
  normalized=d.normalize_pattern({'format':'invalid','fields':[],'delimiter':'','json_keys':'bad','gs1_ai_map':None,'length_unit':'m'})
  for field,want in [('format','auto'),('length_unit','meter'),('delimiter','|'),('json_keys',{}),('gs1_ai_map',{})]:rec('label.normalize_'+field,want,normalized[field])
  out=d.decode_first('SKU|LOT|R|10',[('item',{'format':'qr_json'}),('supplier',{'format':'delimited'})]);rec('label.pattern_fallback','supplier',out['pattern_source'])
  out=d.decode_first('SKU|LOT|R|10',[]);rec('label.default_pattern','supplier',out['pattern_source'])
  supplier=await e.db.suppliers.find_one({'status':'active'});prod=await e.db.products.find_one({'id':'prod_batik_mega'});assert supplier and prod
  body={'supplier_id':supplier['id'],'supplier_sku':'AUD-ITEM','product_id':prod['id'],'supplier_item_name':'Supplier cloth','supplier_color':'Navy','supplier_uom':'roll','conv_factor':100,'last_price':1000,'moq':2,'lead_time_days':3}
  item=await si.create_item(body,entity_id='ent_ksc',actor='Audit');rec('supplier_item.factor',100,item['conv_factor']);rec('supplier_item.price',1000,item['last_price'])
  await reject('supplier_item.duplicate',si.create_item(body,entity_id='ent_ksc'))
  for patch in [{'supplier_id':''},{'supplier_sku':''},{'status':'wrong'},{'conv_factor':0},{'conv_factor':-1},{'product_id':'missing'}]:await reject('supplier_item.create_guard_'+str(patch),si.create_item({**body,'supplier_sku':'NEW',**patch},entity_id='ent_ksc'))
  item=await si.patch_item(item['id'],{'supplier_sku':'AUD-NEW','supplier_item_name':'Renamed','supplier_color':'Blue','supplier_uom':'yard','conv_factor':1,'last_price':15,'currency':'IDR','expected_grade':'A','barcode':'ABC','notes':'Memo','status':'inactive','moq':3,'lead_time_days':5,'label_pattern':{'format':'delimited'}},'Audit')
  for field,want in [('supplier_sku','AUD-NEW'),('supplier_item_name','Renamed'),('conv_factor',1),('last_price',15),('moq',3),('lead_time_days',5),('status','inactive')]:rec('supplier_item.patch_'+field,want,item[field])
  for patch in [{'status':'wrong'},{'conv_factor':0},{'conv_factor':-1},{'product_id':'missing'}]:await reject('supplier_item.patch_guard_'+str(patch),si.patch_item(item['id'],patch))
  item=await si.patch_item(item['id'],{'status':'active','label_pattern':{}});rec('supplier_item.remove_override',None,item['label_pattern'])
  rec('supplier_item.lookup',item['id'],(await si.lookup(supplier_sku='AUD-NEW',supplier_id=supplier['id'],entity_id='ent_ksc'))['id'])
  rows=[{'supplier_sku':'CSV-A','sku':prod['sku'],'conv_factor':'1','last_price':'20','supplier_uom':'yard'}]
  dry=await si.import_rows(rows,supplier_id=supplier['id'],entity_id='ent_ksc');rec('supplier_item.import_preview',1,dry['will_create']);rec('supplier_item.preview_no_write',0,await e.db.supplier_items.count_documents({'supplier_sku':'CSV-A'}))
  first=await si.import_rows(rows,supplier_id=supplier['id'],entity_id='ent_ksc',dry_run=False);second=await si.import_rows(rows,supplier_id=supplier['id'],entity_id='ent_ksc',dry_run=False)
  rec('supplier_item.import_first',1,first['created']);rec('supplier_item.import_second_no_duplicate',0,second['created']);rec('supplier_item.import_second_update',1,second['updated'])
  for row in [{**rows[0],'supplier_sku':''},{**rows[0],'sku':'missing'},{**rows[0],'conv_factor':'0'},{**rows[0],'last_price':'-1'},{**rows[0],'lead_time_days':'bad'}]:
   good,bad=await si.validate_rows([row],supplier_id=supplier['id'],entity_id='ent_ksc');rec('supplier_item.csv_guard_'+str(row),1,len(bad))
  good,bad=await si.validate_rows(rows+rows,supplier_id=supplier['id'],entity_id='ent_ksc');rec('supplier_item.csv_duplicate_guard',1,len(bad))
  await e.db.supplier_items.update_one({'id':item['id']},{'$set':{'usage_count':1}});await reject('supplier_item.used_delete_guard',si.delete_item(item['id']))
  await e.db.supplier_items.update_one({'id':item['id']},{'$set':{'usage_count':0}});rec('supplier_item.unused_delete',True,(await si.delete_item(item['id']))['deleted'])
  for csv,want,errors in [('',0,1),('sku;nama;harga\nP;Product;1.250,50',1,0),('sku,name,price\nP,Product,12.50',1,0),('P;Name;',0,0),('P',0,1),(';Name;10',0,1),('P;Name;not-number',0,1)]:
   out,err=cp.parse_csv(csv);rec('customer_price.csv_rows_'+str(csv),want,len(out));rec('customer_price.csv_errors_'+str(csv),errors,len(err))
  contract=await cs.create_contract({'contract_type':'purchase','partner_id':supplier['id'],'product_id':prod['id'],'tariff_basis':'yard','tariff_rate':10,'tariff_qty_source':'output','valid_from':'2026-01-01','valid_to':'2099-01-01'},entity_id='ent_ksc',actor='Audit')
  contract=await cs.patch_contract(contract['id'],{'title':'Updated','partner_name':'Alias','product_id':prod['id'],'input_product_id':'','tariff_basis':'yard','tariff_rate':20,'tariff_formula':'','tariff_qty_source':'input','payment_term_code':'NET30','ppi':10,'shrinkage_pct':2,'yield_factor':1.2,'byproduct_pct':1,'moq':3,'lead_time_days':4,'tolerance_pct':5,'min_charge':30,'sample_ref':'SAMPLE','notes':'Audit','aux_fees':[{'basis':'per_roll','amount':2}]},'Audit')
  for field,want in [('tariff_rate',20),('tariff_qty_source','input'),('ppi',10),('shrinkage_pct',2),('yield_factor',1.2),('byproduct_pct',1),('moq',3),('lead_time_days',4),('tolerance_pct',5),('min_charge',30)]:rec('contract.patch_'+field,want,contract[field])
  for patch in [{'tariff_basis':'bad'},{'tariff_qty_source':'bad'},{'valid_to':'2020-01-01'},{'aux_fees':[{'basis':'invalid'}]}]:await reject('contract.patch_guard_'+str(patch),cs.patch_contract(contract['id'],patch))
  product={'id':'P','base_unit':'meter','gramasi':100,'lebar':100,'construction':{'ppi':20}}
  for basis,count,rate,want in [('meter',0,10,100),('lumpsum',0,10,10),('lot',0,10,10),('custom',0,10,10),('roll',2,10,20),('pick',0,2,400)]:
   out=await cs.compute_tariff(product=product,qty_base=10,contract={'tariff_basis':basis,'tariff_rate':rate},roll_count=count);rec('contract.tariff_'+basis,want,out['amount'])
  for basis,qty,extra,want in [('lumpsum',10,{},5),('per_roll',10,{'roll_count':2},10),('per_color',10,{'colors':3},15),('per_repeat',10,{'repeats':4},20),('per_output_unit',10,{},50),('per_meter',10,{},50)]:
   out=await cs.compute_tariff(product=product,qty_base=qty,contract={'tariff_basis':'lumpsum','tariff_rate':10,'aux_fees':[{'basis':basis,'amount':5}]},**extra);rec('contract.aux_'+basis,want,out['aux_total'])
  out=await cs.compute_tariff(product={'base_unit':'kg'},qty_base=10,contract={'tariff_basis':'kg','tariff_rate':2,'aux_fees':[{'basis':'per_kg','amount':3}]});rec('contract.kg_total',50,out['amount'])
  out=await cs.compute_tariff(product=product,qty_base=10,contract={'tariff_basis':'meter','tariff_rate':10,'tariff_formula':'basis_qty * rate + 25'});rec('contract.formula_total',125,out['amount'])
  out=await cs.compute_tariff(product=product,qty_base=10,contract={'tariff_basis':'meter','tariff_rate':10,'tariff_formula':'missing_variable'});rec('contract.invalid_formula_warn',True,bool(out['warnings']));rec('contract.invalid_formula_fallback',100,out['amount'])
  out=await cs.compute_tariff(product=product,qty_base=10,contract={'tariff_basis':'meter','tariff_rate':10,'min_charge':150});rec('contract.minimum',150,out['amount']);rec('contract.minimum_label',True,out['min_charge_applied'])
  out=await cs.compute_tariff(product=product,qty_base=10,contract={'tariff_basis':'meter','tariff_rate':10},override={'tariff_rate':12});rec('contract.override',120,out['amount']);rec('contract.override_label','override',out['source'])
 except Exception:ERRORS.append(traceback.format_exc())
 finally:
  Path(__file__).with_name('label-master-rules90-results.json').write_text(json.dumps(dict(candidate='a904d989b622f7da14c4892d03cf6ef0c43f3084',database=e.db.name,observations=RESULTS,harness_errors=ERRORS,scope='Original pure supplier label decoder, catalog import/CRUD and tariff service arithmetic; no scanner/printer or public authorization claim.',standard_source='https://ref.gs1.org/ai/?lang=en'),ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'observations':len(RESULTS),'differences':[r['id'] for r in RESULTS if r['status']!='pass'],'errors':ERRORS}));e.client.close()
if __name__=='__main__':asyncio.run(main())
