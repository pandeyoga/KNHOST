"""Validate audit documentation contracts, not application correctness. Standard library only."""
from pathlib import Path
from urllib.parse import unquote
import json,re,sys
ROOT=Path(__file__).resolve().parents[1]
errors=[]
def require(condition,message):
 if not condition:errors.append(message)
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
tracker=read('tracker.json');rows=tracker['findings'];ids={r['id'] for r in rows}
require(len(ids)==len(rows),'Duplicate finding IDs')
allowed={'needs_revalidation','open','in_progress','ready_for_validation','verified_fixed','reopened','needs_policy_decision','blocked','deferred','not_reproducible','duplicate'}
plan=read('phases/plan.json')['phases'];phases={p['id']:p for p in plan}
require(len(phases)==len(plan),'Duplicate phase IDs')
def sha(value):return bool(re.fullmatch('[0-9a-f]{40}',value or ''))
def evidence(paths,context):
 require(isinstance(paths,list),context+': evidence must be a list')
 for raw in paths:
  p=(ROOT/raw).resolve()
  require(p.is_relative_to(ROOT) and p.is_file(),context+': evidence must be an existing file within docs/audit: '+raw)
for r in rows:
 id=r['id'];require(r['status'] in allowed,id+': invalid status')
 require(r['phase'] in phases,id+': unknown phase')
 require((ROOT/f'findings/{id}.md').is_file(),id+': missing card')
 require((ROOT/f"domains/{r['domain']}.md").is_file(),id+': missing domain')
 require(sha(r['audited_commit']),id+': invalid audited SHA')
 require(bool(r['history']),id+': history required')
 require(all(x in ids for x in r['related_ids']),id+': unknown related ID')
 if r['status']=='duplicate':require(r['duplicate_of'] in ids and r['duplicate_of']!=id,id+': invalid duplicate target')
 else:
  require(r['duplicate_of'] is None,id+': nonduplicate carries alias')
  occurrences=sum(id in p['finding_ids'] for p in plan)
  require(occurrences==1,id+': must belong to exactly one phase')
  require(id in phases[r['phase']]['finding_ids'],id+': phase assignment mismatch')
 for key in ['implementation_evidence','validation_evidence']:evidence(r[key],id+' '+key)
 require(all(sha(s) for s in r['implementation_commits']),id+': invalid implementation SHA')
 if r['status'] in ('ready_for_validation','verified_fixed'):
  require(sha(r['current_code_checked_commit']),id+': tested candidate SHA required')
  require(bool(r['implementation_evidence']),id+': implementation/rebaseline evidence required')
 if r['status']=='verified_fixed':
  require(sha(r['validation_commit']) and bool(r['validator']) and bool(r['validation_evidence']),id+': independent validator, SHA and evidence required')
  require(r['validation_commit']==r['current_code_checked_commit'],id+': validation SHA must match the recorded candidate')
seen=set();active=set()
def visit(id):
 if id in active:errors.append('Phase dependency cycle: '+id);return
 if id in seen:return
 active.add(id)
 for dep in phases[id]['depends_on']:
  require(dep in phases,'Unknown dependency '+dep)
  if dep in phases:visit(dep)
 active.remove(id);seen.add(id)
for p in plan:
 require((ROOT/f"phases/{p['id']}.md").is_file(),'Missing phase doc '+p['id'])
 require(all(i in ids for i in p['finding_ids']),'Unknown finding in '+p['id'])
 visit(p['id'])
cases=read('coverage.json')['cases'];require(len({c['id'] for c in cases})==len(cases),'Duplicate coverage IDs')
for c in cases:
 require(c['current_status'] in {'not_revalidated','planned','partial','tested_pass','tested_fail','blocked'},c['id']+': invalid coverage status')
 evidence(c['evidence'],c['id'])
 if c['current_status'] in {'tested_pass','tested_fail'}:require(sha(c['tested_commit']) and bool(c['evidence']),c['id']+': test SHA and evidence required')
for p in ROOT.rglob('*.md'):
 text=p.read_text(encoding='utf-8')
 for target in re.findall(r'\]\(([^)\n]+)\)',text):
  if target.startswith(('https:','http:','mailto:','#')):continue
  target=unquote(target.strip('<>').split('#')[0])
  if not target:continue
  require((p.parent/target).exists(),f'Broken local link: {p.relative_to(ROOT)} -> {target}')
if errors:
 print('\n'.join(errors));sys.exit(1)
print(f'PASS: {len(rows)} records, {len(plan)} phases, {len(cases)} coverage cases; links, evidence and status contracts valid.')
