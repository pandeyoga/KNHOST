"""UI fixture for iteration 219: python tests/ui_fixtures_l03_219.py up → prints OD id (pending approval, 2 items)."""
import os
import subprocess
import sys

import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
if sys.argv[1] == "up":
    subprocess.run([sys.executable, "/app/backend/tests/ui_fixtures_l03.py", "up"], check=True)
    tok = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}
    body = {"customer_id": "cust_toko_kain", "title": "TEST_UI_219", "entity_id": "ent_ksc", "expected_delivery": "2026-12-31",
            "submit_for_approval": True, "items": [
                {"source_type": "parent_product", "source_template_id": "ptpl_609f19d3205c", "description": "TEST UI parent",
                 "request_types": ["printing", "labdip"], "quantity": 10, "target_price": 100},
                {"source_type": "approved_artwork", "source_design_id": "dsgn_TEST_ui_ok", "description": "TEST UI artwork",
                 "request_types": ["printing"], "quantity": 20, "target_price": 100}]}
    r = requests.post(f"{BASE}/special-orders", json=body, headers=h)
    print(r.status_code, r.json()["id"], r.json()["number"], r.json()["status"])
else:
    subprocess.run([sys.executable, "/app/backend/tests/ui_fixtures_l03.py", "down"], check=True)
