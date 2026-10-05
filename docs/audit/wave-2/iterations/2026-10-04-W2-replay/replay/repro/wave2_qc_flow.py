"""Receiving -> QC disposition -> supplier return, including unit boundaries."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_grn_partial as p
e=p.e;db=p.db;results=[]
def check(sid,kind,label,actual,expected):
 assert actual==expected,(sid,actual,expected)
 results.append({'id':sid,'kind':kind,'label':label,'observed':actual,'expected_reproduction':expected});print(json.dumps(results[-1]),flush=True)
async def received(tag,kg=False):
 pid,tid,poid=await p.seed_po(tag,3 if kg else 10)
 if kg:
  await db.products.update_one({'id':pid},{'$set':{'gramasi':200,'lebar':1.5}})
  await db.wms_tasks.update_one({'id':tid},{'$set':{'unit':'kg'}})
  await db.purchase_orders.update_one({'id':poid},{'$set':{'items.0.unit':'kg','items.0.price':10000}})
 grn=await p.g.create_grn(p.GRNCreateIn(partner_type='supplier',partner_id='SUP',warehouse_id='WH',po_ids=[poid]),p.actor,p.ctx)
 gid=grn['id'];grn=await p.g.manual_entry(gid,grn['version'],p.actor,p.ctx)
 grn=await p.g.patch_dn(gid,p.GRNDnPatch(expected_version=grn['version'],number='DN'+tag,date='2026-10-02'),p.actor,p.ctx)
 grn=await p.g.add_line(gid,p.GRNLineIn(expected_version=grn['version'],declared=p.GRNDeclared(qty=3 if kg else 10,unit='kg' if kg else 'meter',rolls=1,lot='LOT'+tag),target=p.GRNTargetIn(type='po_task',task_id=tid),decision='accept'),p.actor,p.ctx)
 grn=await p.g.start_count(gid,grn['version'],p.actor,p.ctx)
 out=await p.g.add_counted_roll(gid,1,p.GRNCountRollIn(length=10,weight_kg=3 if kg else 0,lot='LOT'+tag,expected_version=grn['version']),p.actor,p.ctx)
 final=await p.finish(out['grn']);assert final['grn']['status']=='closed',final
 return pid,tid,poid
async def buckets(pid):
 out={}
 async for roll in db.inventory_rolls.find({'product_id':pid}):out[roll['status']]=round(out.get(roll['status'],0)+roll['length_remaining'],2)
 return out
async def main():
 await e.seed()
 import indexes
 await indexes.ensure_performance_indexes()
 await db.warehouses.insert_one({'id':'WH','name':'Audit Warehouse','status':'active'})
 await db.suppliers.insert_one({'id':'SUP','name':'Supplier'})
 await db.permission_settings.update_one({'id':'default'},{'$set':{'matrix.finance.wms':['view','update']}})
 async with e.httpx.AsyncClient(transport=e.httpx.ASGITransport(app=e.server.app,raise_app_exceptions=False),base_url='http://audit.local',headers={'Authorization':'Bearer audit-local-session','X-Entity-Id':'A'}) as h:
  async def decide(tid,a,r,disp='damaged'):
   res=await h.post(f'/api/inbound/tasks/{tid}/qc-decision',json={'accept_qty':a,'reject_qty':r,'reject_disposition':disp,'reason':'Synthetic QC audit','accept_grade':'B'})
   return res.status_code,res.json()
  pid,tid,poid=await received('ACCEPT')
  st,out=await decide(tid,10,0)
  print('C01_BODY',st,out,flush=True)
  check('W2-Q-C01','control','Full accept from real GRN',[st,out.get('accepted_qty'),await buckets(pid)],[200,10,{'available':10}])
  st,out=await decide(tid,10,0)
  check('W2-Q-C02','control','Repeat QC denied',[st,await buckets(pid)],[400,{'available':10}])
  pid,tid,poid=await received('DAMAGE')
  st,out=await decide(tid,6,4)
  check('W2-Q-C03','control','Mixed accept/damage conserves length',[st,await buckets(pid)],[200,{'available':6,'damaged':4}])
  pid,tid,poid=await received('VALIDATE')
  for n,a,r,disp,status in [(4,11,0,'damaged',400),(5,-1,0,'damaged',422),(6,0,0,'damaged',400),(7,0,10,'invalid',400)]:
   st,out=await decide(tid,a,r,disp)
   check(f'W2-Q-C{n:02}','control','Invalid QC payload leaves quarantine',[st,await buckets(pid)],[status,{'quarantine':10}])
  pid,tid,poid=await received('RETURN')
  st,out=await decide(tid,0,10,'return');ret=await db.purchase_returns.find_one({'id':out['purchase_return']['id']})
  check('W2-Q-C08','control','Full QC reject creates return without second stock consumption',[st,await buckets(pid),ret['items'][0]['quantity'],ret['total_amount'],ret['stock_adjusted']],[200,{'returned_supplier':10},10,100,True])
  from services.purchase_return_service import approve_and_adjust_stock
  await approve_and_adjust_stock(ret['id'],'Audit User A')
  po=await db.purchase_orders.find_one({'id':poid})
  check('W2-Q-C09','control','Approve QC return preserves already returned stock',[await buckets(pid),po['returned_amount']],[{'returned_supplier':10},100])
  pid,tid,poid=await received('KGRETURN',True)
  task=await db.wms_tasks.find_one({'id':tid})
  check('W2-Q-C10','control','Weight PO receives3kg as10meter physical roll',[await p.received(poid),task['unit'],await buckets(pid)],[3,'kg',{'quarantine':10}])
  st,out=await decide(tid,0,10,'return');ret=await db.purchase_returns.find_one({'id':out['purchase_return']['id']})
  check('W2-Q-F01','defect','QC base quantity incorrectly reused as purchase unit quantity',[st,ret['items'][0]['quantity'],ret['items'][0]['unit'],ret['total_amount'],await buckets(pid)],[200,10,'kg',100000,{'returned_supplier':10}])
  await approve_and_adjust_stock(ret['id'],'Audit User A');po=await db.purchase_orders.find_one({'id':poid})
  check('W2-Q-F02','defect','Wrong QC return amount reaches PO return ledger',po['returned_amount'],100000)
  pid,tid,poid=await received('KGACCEPT',True)
  st,out=await decide(tid,10,0)
  rolls=await db.inventory_rolls.find({'product_id':pid}).to_list(100)
  check('W2-Q-C11','control','Whole roll acceptance preserves actual weight',[st,sum(x['weight_kg'] for x in rolls)],[200,3])
  pid,tid,poid=await received('KGSPLIT',True)
  st,out=await decide(tid,6,4)
  rolls=await db.inventory_rolls.find({'product_id':pid}).to_list(100)
  check('W2-Q-F03','defect','QC split duplicates actual weight across child and parent',[st,await buckets(pid),sum(x['weight_kg'] for x in rolls),sum(x['secondary_measures']['kg'] for x in rolls)],[200,{'available':6,'damaged':4},6,6])
 assert not e.blocked
if __name__=='__main__':
 try:asyncio.run(main())
 finally:
  Path(__file__).resolve().parents[1].joinpath('qc-flow-results.json').write_text(json.dumps({'source_commit':subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),'database':e.DBNAME,'mode':'Actual GRN services -> QC ASGI -> return approval service; synthetic fixtures and full indexes','results':results},indent=2),encoding='utf-8');e.client.close()
