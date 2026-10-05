"""Execute three original isolated suites; preserve app and repo test configuration."""
import integration_round4 as env
import pytest
names=['test_uom_1_13.py','test_tanya_kn_f0_time.py','test_registry_ai_collections.py']
code=pytest.main(['-c',str(env.B/'pytest-audit.ini'),'-q','--junitxml='+str(env.B/'existing_unit_tests.xml'),*[str(env.REPO/'backend/tests'/n) for n in names]])
env.client.close()
raise SystemExit(code)
