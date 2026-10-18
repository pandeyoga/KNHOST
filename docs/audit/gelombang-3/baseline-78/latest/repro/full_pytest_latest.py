import os,sys,pytest
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
ROOT=Path(os.environ['KNHOST_REPO']).parents[1]
tests=OUT/'pytest-copies'
args=['-c',str(ROOT/'work/pytest-audit.ini'),'--import-mode=importlib','-q','--tb=short','--continue-on-collection-errors',
      '--ignore='+str(tests/'test_wilayah_extra.py'),'--ignore='+str(tests/'test_notifications_iter33.py'),
      str(tests),'--junitxml='+str(OUT/'evidence/pytest-full.xml')]
print('Full-suite invocation:',args,flush=True)
raise SystemExit(pytest.main(args))
