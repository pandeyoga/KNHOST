from pathlib import Path
from collections import Counter
import argparse, copy, hashlib, json, re, sys

ROOT=Path(__file__).resolve().parents[1]
STATES={'not_started','in_progress','blocked_by_decision','blocked_by_hardware','implemented_pending_validation','validated','reopened'}
def load(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def file_ok(ref):
    if not isinstance(ref,str) or not ref: return False
    p=(ROOT/ref).resolve()
    return p.is_relative_to(ROOT.resolve()) and p.is_file() and p.stat().st_size>0
def sha_ok(s): return isinstance(s,str) and re.fullmatch(r'[0-9a-f]{40}',s) is not None

def validate(d,closure=False):
    errors=[]
    closure=closure or d.get('wave_status') in {'complete','completed','validated'}
    def check(ok,message):
        if not ok: errors.append(message)
    def ids(items,label):
        vals=[x['id'] for x in items]
        check(len(vals)==len(set(vals)),label+': duplicate IDs')
        return {x['id']:x for x in items}
    ps=ids(d['phases'],'phase'); rs=ids(d['requirements'],'requirement'); cs=ids(d['acceptance'],'acceptance'); ds=ids(d['decisions'],'decision')
    scope_path=ROOT/'SCOPE_BASELINE.json'
    check(scope_path.is_file(),'SCOPE_BASELINE.json missing; planned scope cannot be verified')
    if scope_path.is_file():
        scope=load(scope_path)
        for name,actual in [('phases',ps),('requirements',rs),('acceptance',cs),('decisions',ds)]:
            check(set(actual)==set(scope[name]),'scope inventory changed: '+name)
        for pid,p in ps.items():
            if pid in scope['phases']: check(sorted(p['dependencies'])==sorted(scope['phases'][pid]),pid+': scope dependency changed')
        for rid,r in rs.items():
            if rid in scope['requirements']:
                for key,expected in scope['requirements'][rid].items():
                    actual=r.get(key)
                    check((sorted(actual)==sorted(expected) if isinstance(expected,list) and isinstance(actual,list) else actual==expected),rid+': scope binding changed '+key)
        for cid,c in cs.items():
            if cid in scope['acceptance']:
                for key,expected in scope['acceptance'][cid].items(): check(c.get(key)==expected,cid+': scope binding changed '+key)
    check(d.get('wave_status') in {'planned','in_progress','implemented_pending_validation','complete','completed','validated','reopened'},'invalid wave state')
    check(sha_ok(d.get('baseline_commit')),'baseline full SHA required')
    def evidence(row,label):
        check(sha_ok(row.get('verified_commit')),label+': verified_commit must be full SHA')
        check(bool(row.get('evidence')),label+': evidence required')
        for ref in row.get('evidence',[]): check(file_ok(ref),label+': evidence missing/unsafe '+str(ref))
        check(bool(row.get('reviewer')),label+': reviewer required')
    def approved(row,label):
        check(bool(row.get('implementer')),label+': implementer required')
        check(bool(row.get('reviewer')) and row.get('reviewer')!=row.get('implementer'),label+': independent reviewer required')
        check(file_ok(row.get('owner_approval_ref')),label+': owner approval file required')
    def final_commit(row,label):
        if row.get('verified_commit')!=d.get('target_commit'):
            check(row.get('assessed_target_commit')==d.get('target_commit') and file_ok(row.get('impact_assessment_ref')),label+': older evidence requires reviewed impact assessment at final target')
    def evidence_at(row,target,label):
        check(sha_ok(target),label+': target verification SHA invalid')
        if row.get('verified_commit')!=target:
            check(row.get('assessed_target_commit')==target and file_ok(row.get('impact_assessment_ref')),label+': evidence commit differs without impact assessment')
    visiting=set(); visited=set()
    def visit(k):
        if k in visiting: errors.append('Phase dependency cycle at '+k); return
        if k in visited: return
        visiting.add(k)
        for dep in ps[k]['dependencies']:
            check(dep in ps,k+': missing dependency '+dep)
            if dep in ps: visit(dep)
        visiting.remove(k); visited.add(k)
    for pid,p in ps.items():
        visit(pid)
        check(p['status'] in STATES,pid+': invalid state')
        check(file_ok('phases/'+pid+'.md'),pid+': prompt missing')
        if p['status']=='validated':
            evidence(p,pid); approved(p,pid)
            check(sha_ok(p.get('implementation_commit')),pid+': implementation_commit required')
            check(all(ps[x]['status']=='validated' for x in p['dependencies'] if x in ps),pid+': dependencies not validated')
            check(all(r['status']=='validated' for r in rs.values() if r['phase']==pid),pid+': requirements not all validated')
            for r in rs.values():
                if r['phase']==pid: evidence_at(r,p.get('verified_commit'),pid+'/'+r['id'])
        if closure: final_commit(p,pid)
    for did,x in ds.items():
        check(x['status'] in {'pending','resolved'},did+': invalid decision status')
        check(bool(x['affected_requirements']),did+': no affected requirement')
        for rid in x['affected_requirements']:
            check(rid in rs,did+': unknown affected requirement '+rid)
            if rid in rs: check(did in rs[rid]['pending_decisions'],did+': reverse link missing for '+rid)
        if x['status']=='resolved':
            check(bool(x.get('answer')) and bool(x.get('answer_ref')) and bool(x.get('confirmed_by')),did+': resolved requires answer, source and confirmer')
        if closure: check(x['status']=='resolved',did+': decision pending')
    for rid,r in rs.items():
        check(r['phase'] in ps,rid+': phase unknown'); check(r['status'] in STATES,rid+': invalid state')
        check(bool(r['acceptance_ids']),rid+': no acceptance')
        for did in r['pending_decisions']:
            check(did in ds,rid+': unknown decision '+did)
            if did in ds: check(rid in ds[did]['affected_requirements'],rid+': reverse decision link missing '+did)
        for cid in r['acceptance_ids']:
            check(cid in cs,rid+': unknown acceptance '+cid)
            if cid in cs: check(cs[cid]['requirement']==rid,rid+': acceptance belongs to another requirement '+cid)
        if r['status'] in {'implemented_pending_validation','validated'}:
            check(sha_ok(r.get('implementation_commit')),rid+': implementation full SHA required')
            check(bool(r.get('evidence')),rid+': implementation evidence required')
            for ref in r.get('evidence',[]): check(file_ok(ref),rid+': implementation evidence missing '+ref)
        if r['status']=='validated':
            evidence(r,rid); approved(r,rid)
            check(all(ds[x]['status']=='resolved' for x in r['pending_decisions'] if x in ds),rid+': required decision unresolved')
            check(all(cs[x]['status']=='pass' for x in r['acceptance_ids'] if x in cs),rid+': acceptance not all PASS')
            for cid in r['acceptance_ids']:
                if cid in cs: evidence_at(cs[cid],r.get('verified_commit'),rid+'/'+cid)
        if closure:
            check(r['status']=='validated',rid+': requirement not validated'); final_commit(r,rid)
    for cid,c in cs.items():
        check(c['requirement'] in rs,cid+': missing requirement')
        if c['requirement'] in rs:
            check(cid in rs[c['requirement']]['acceptance_ids'],cid+': reverse acceptance link missing')
            check(c['phase']==rs[c['requirement']]['phase'],cid+': wrong phase')
        check(c['status'] in {'not_run','pass','fail','blocked'},cid+': invalid acceptance status')
        if c['status']=='pass':
            evidence(c,cid); check(bool(c.get('actual_result')),cid+': actual result required')
            if c.get('requires_hardware'): check(c.get('hardware_evidence') is True,cid+': physical hardware evidence flag required')
        if closure:
            check(c['status']=='pass',cid+': acceptance not PASS'); final_commit(c,cid)
    pairs=[]
    for s in d['source_map']:
        pairs.append((s['source'],s['id']))
        check(bool(s['requirements']),str(pairs[-1])+': no target requirement')
        for rid in s['requirements']: check(rid in rs,str(pairs[-1])+': unknown requirement '+rid)
    check(len(pairs)==len(set(pairs)),'duplicate source map IDs')
    def covered(group,expected):
        actual={i for g,i in pairs if g==group}
        check(actual==set(expected),group+': missing/extra source IDs '+str(sorted(actual.symmetric_difference(set(expected)))))
    covered('HIST',[x['id'] for x in load(ROOT/'sources/REGISTER_PERNYATAAN_126_HISTORIS.json')['records']])
    covered('LATEST',[x['id'] for x in load(ROOT/'sources/REGISTER_JAWABAN_2026_10_16.json')['decisions']])
    covered('RETURN',load(ROOT/'sources/KEPUTUSAN_RETUR_SETELAH_JAWABAN_PEMILIK.json')['answers'].keys())
    old=load(ROOT/'sources/PLAN_LAMA_BACKLOG_SNAPSHOT.json')
    covered('OLD_IMP',[x['id'] for x in old['requirements']]); covered('OLD_ACC',[x['id'] for x in old['acceptance']])
    covered('ERP_MW',[f'ERP-MW-{i:02d}' for i in range(1,13)])
    rf=load(ROOT/'sources/rfid-plan/RFID_BACKLOG.json')
    covered('RFID_REQ',[x['id'] for x in rf['requirements']]); covered('RFID_STAGE',[x['id'] for x in rf['stages']]); covered('RACC',[x['id'] for x in rf['acceptance']])
    cases=re.findall(r'^## ((?:HH|RD|PR|INT)-\d+)\s*$',(ROOT/'sources/middleware/uat/UAT_SCENARIOS.md').read_text(encoding='utf-8'),re.M)
    covered('MW_UAT',cases)
    for case in cases: check('MW-'+case in cs,'middleware UAT acceptance missing '+case)
    if closure:
        check(sha_ok(d.get('target_commit')),'final target full SHA required')
        check(all(p['status']=='validated' for p in ps.values()),'all phases must be validated')
        fr=d.get('final_review',{})
        check(fr.get('verified_commit')==d.get('target_commit'),'final review commit differs from target')
        approved(fr,'final review')
        for key in ['reconciliation_ref','migration_ref','hardware_ref']: check(file_ok(fr.get(key)),'final review '+key+' missing')
    return errors

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--closure',action='store_true'); parser.add_argument('--self-test',action='store_true'); args=parser.parse_args()
    d=load(ROOT/'BACKLOG.json'); errors=validate(d,args.closure)
    source_manifest=ROOT/'SOURCE_MANIFEST.json'
    if not source_manifest.is_file(): errors.append('SOURCE_MANIFEST.json missing')
    else:
        for item in load(source_manifest)['files']:
            p=ROOT/item['path']
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']: errors.append('historical source changed/missing: '+item['path'])
    if args.self_test:
        trials=[]
        fixture=copy.deepcopy(d); fixture['wave_status']='planned'
        for rows in [fixture['phases'],fixture['requirements']]:
            for row in rows: row.update(status='not_started',evidence=[],verified_commit=None,implementation_commit=None)
        for row in fixture['acceptance']: row.update(status='not_run',evidence=[],verified_commit=None,actual_result=None)
        trials.append(('valid draft metadata accepted',not validate(fixture)))
        x=copy.deepcopy(fixture); x['requirements'][0]['status']='validated'; trials.append(('reject validated without evidence',any('evidence required' in e for e in validate(x))))
        x=copy.deepcopy(fixture); x['acceptance'][0]['status']='pass'; trials.append(('reject PASS without result/evidence',any('actual result required' in e for e in validate(x))))
        x=copy.deepcopy(fixture); x['phases'][0]['dependencies']=['L14']; trials.append(('reject dependency cycle',any('dependency cycle' in e for e in validate(x))))
        x=copy.deepcopy(fixture); x['source_map']=x['source_map'][1:]; trials.append(('reject missing historical coverage',any('HIST: missing/extra' in e for e in validate(x))))
        x=copy.deepcopy(fixture); removed=x['acceptance'].pop(0)['id']
        for r in x['requirements']: r['acceptance_ids']=[cid for cid in r['acceptance_ids'] if cid!=removed]
        trials.append(('reject removal of a planned acceptance',any('scope inventory changed: acceptance' in e for e in validate(x))))
        x=copy.deepcopy(fixture); x['acceptance'][0]['requires_hardware']=not x['acceptance'][0]['requires_hardware']; trials.append(('reject silent hardware scope change',any('scope binding changed requires_hardware' in e for e in validate(x))))
        x=copy.deepcopy(fixture); x['wave_status']='complete'; trials.append(('reject premature complete status without closure flag',any('requirement not validated' in e for e in validate(x))))
        trials.append(('reject premature whole-wave closure',any('requirement not validated' in e for e in validate(fixture,True))))
        # Synthetic metadata only; never written to BACKLOG or claimed as ERP evidence.
        completed=copy.deepcopy(fixture); completed['target_commit']='a'*40; completed['wave_status']='complete'
        for row in completed['phases']+completed['requirements']:
            row.update(status='validated',implementation_commit='a'*40,verified_commit='a'*40,evidence=['README.md'],implementer='fixture-implementer',reviewer='fixture-reviewer',owner_approval_ref='README.md')
        for row in completed['acceptance']:
            row.update(status='pass',verified_commit='a'*40,evidence=['README.md'],actual_result='SYNTHETIC METADATA ONLY',reviewer='fixture-reviewer',hardware_evidence=True)
        for row in completed['decisions']: row.update(status='resolved',answer='SYNTHETIC METADATA ONLY',answer_ref='README.md',confirmed_by='fixture-owner')
        completed['final_review']=dict(verified_commit='a'*40,implementer='fixture-implementer',reviewer='fixture-reviewer',owner_approval_ref='README.md',reconciliation_ref='README.md',migration_ref='README.md',hardware_ref='README.md')
        trials.append(('complete synthetic metadata is accepted; not ERP evidence',not validate(completed,True)))
        x=copy.deepcopy(completed); x['acceptance'][0]['verified_commit']='b'*40
        trials.append(('reject stale acceptance evidence at requirement validation',any('evidence commit differs without impact assessment' in e for e in validate(x))))
        for label,ok in trials:
            if not ok: errors.append('self-test failed: '+label)
        print(json.dumps({'self_tests':trials},ensure_ascii=False))
    print(json.dumps({'mode':'closure' if args.closure else 'package_metadata','pass':not errors,'errors':errors[:25],'error_count':len(errors),'note':'Metadata validation does not prove ERP implementation correctness.'},ensure_ascii=False,indent=2))
    return 1 if errors else 0
if __name__=='__main__': sys.exit(main())
