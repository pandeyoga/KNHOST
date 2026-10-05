"""Read-only package/metadata checks, not application validation."""
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1]
def read(n):return json.loads((root/n).read_text(encoding='utf-8-sig'))
def exists(n):
 p=(root/n).resolve()
 assert p.is_relative_to(root.resolve()) and p.is_file(),f'Missing/invalid evidence path: {n}'
manifest=read('baseline-manifest.json')
for n,h in manifest['sha256'].items():
 exists(n);assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h,'Baseline changed: '+n
fs=read('tracker.json')['findings'];rs=read('requirements-tracker.json')['requirements'];ps=read('phase-tracker.json')['phases']
assert len(fs)==25 and len({x['id'] for x in fs})==25
assert {x['id'] for x in fs}=={f'W2-{i:03}' for i in range(1,26)}
assert len(rs)==9 and len({x['id'] for x in rs})==9
mapped=[i for p in ps for i in p['findings']];assert len(mapped)==25 and set(mapped)=={x['id'] for x in fs}
assert set(i for p in ps for i in p['requirements'])=={x['id'] for x in rs}
allowed={'open','in_progress','ready_for_validation','verified_fixed','partially_fixed','reopened','blocked','deferred'}
for x in fs+rs:
 assert x['status'] in allowed,(x['id'],x['status'])
 for n in x.get('evidence',[]):exists(n)
 for key in ('implementation_evidence','validation_evidence'):
  for n in x.get(key,[]):exists(n)
 if x['status'] in ('ready_for_validation','verified_fixed'):
  assert x.get('implementation_commits') and x.get('implementation_evidence'),x['id']+' lacks implementation evidence'
 if x['status']=='verified_fixed':
  assert x.get('validation_commit') and x.get('validation_evidence'),x['id']+' lacks validation evidence'
s=read('baseline/coverage-summary.json');assert sum(s['counts'].values())==s['total_checkpoints']==242
assert len(read('wave1-extensions.json')['extensions'])==26
print('PASS: immutable baseline,25 finding mappings,9 requirements,26 extension cases and status evidence paths. Not an application test.')
