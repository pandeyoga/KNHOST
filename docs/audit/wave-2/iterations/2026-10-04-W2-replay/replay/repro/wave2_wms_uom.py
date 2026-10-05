"""Ordinary WMS quantity/unit conversion controls; no security testing."""
import asyncio,json,subprocess
from pathlib import Path
import wave2_env as e
from services import uom_service as u, uom_rules_service as rules
results=[]
def check(sid,label,actual,expected):
    assert actual==expected,(sid,label,actual,expected)
    results.append({'id':sid,'kind':'control','label':label,'observed':actual,'expected':expected})
    print(sid,label,actual,flush=True)
async def main():
    await e.seed()
    await e.db.uoms.insert_many([dict(x) for x in u.UOM_SEED_ROWS]);u.invalidate_vocab()
    await rules.ensure_defaults();engine=await rules.load_engine();fixed=engine['fixed']
    p={'id':'FABRIC','base_unit':'meter','gramasi':200,'lebar':1.5,
       'uom_conversions':[{'from_unit':'roll','to_unit':'meter','factor':50}]}
    async def converted(q,fu,tu):
        return (await rules.convert_with_trail(p,q,fu,tu,engine=engine))['base_qty']
    check('W2-U-C01','10 yard to meter',await converted(10,'yard','meter'),9.14)
    check('W2-U-C02','100 cm to meter',await converted(100,'cm','meter'),1.0)
    check('W2-U-C03','10 inch to meter',await converted(10,'inch','meter'),0.25)
    check('W2-U-C04','2 rolls at 50 meter each',await converted(2,'roll','meter'),100.0)
    check('W2-U-C05','100 meter to rolls',await converted(100,'meter','roll'),2.0)
    check('W2-U-C06','3 kg at GSM200 width1.5m',await converted(3,'kg','meter'),10.0)
    check('W2-U-C07','10 meter to kg',await converted(10,'meter','kg'),3.0)
    check('W2-U-C08','uppercase master alias YRD',await converted(10,'YRD','MTR'),9.14)
    q=await rules.convert_with_trail({'base_unit':'piece'},3,'dozen','piece',engine=engine)
    check('W2-U-C09','3 dozen to pieces',q['base_qty'],36.0)
    m=await converted(100,'yard','meter')
    check('W2-U-C10','100 yard round trip',await converted(m,'meter','yard'),100.0)
    check('W2-U-C11','kg per yard base',round(u.kg_per_base_unit({**p,'base_unit':'yard'},fixed),5),0.27432)
    error=False
    try:await rules.convert_with_trail({'base_unit':'meter'},1,'roll','meter',engine=engine)
    except rules.UomRuleError:error=True
    check('W2-U-C12','roll without factor rejected',error,True)
    for sid,actual,expected in [('W2-U-C13',101,'ok'),('W2-U-C14',102,'warn'),('W2-U-C15',105,'block')]:
        v=await rules.check_variance(100,actual,settings=rules.DEFAULT_SETTINGS)
        check(sid,'variance boundary '+str(actual),v['level'],expected)
    trail=await rules.convert_with_trail(p,2,'roll','meter',engine=engine,context='audit WMS')
    check('W2-U-C16','conversion trail quantity and source',
          {k:trail[k] for k in ['doc_qty','base_qty','factor','source']},
          {'doc_qty':2.0,'base_qty':100.0,'factor':50.0,'source':'product_override'})
async def run():
    completed=False
    try:await main();completed=True
    finally:
        (Path(__file__).resolve().parent.parent/'wms-uom-results.json').write_text(json.dumps({
            'completed':completed,'commit':subprocess.check_output(['git','-C',str(e.REPO),'rev-parse','HEAD'],text=True).strip(),
            'database':e.DBNAME,'level':'Original WMS UOM services + synthetic local Mongo; not HTTP/browser or full receiving flow',
            'scenarios':results},indent=2),encoding='utf-8');e.client.close()
asyncio.run(run())
