"""Create an isolated replay copy; never executes application code."""
from pathlib import Path
import argparse,shutil,re
p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',a.name):p.error('Use a simple unique iteration name')
root=Path(__file__).resolve().parents[1];dst=root/'iterations'/a.name
if dst.exists():p.error('Iteration already exists; select a new name to preserve evidence')
dst.mkdir()
shutil.copytree(root/'baseline',dst/'replay',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copyfile(root/'templates/IMPLEMENTATION.md',dst/'IMPLEMENTATION.md')
print('Prepared:',dst)
print('Run harness only from replay/repro; set KNHOST_REPO to candidate checkout. Historical assertions expect bugs.')
