"""Read-only numeric sweep for iter149 - probes all board/summary endpoints
and verifies totals match rows. Does NOT create data. Writes JSON dump.
"""
import os, json, requests

BASE = os.environ.get('REACT_APP_BACKEND_URL', 'http://127.0.0.1:8006').rstrip('/')
tok = requests.post(f'{BASE}/api/auth/login',
                    json={'email':'admin@kainnusantara.id','password':'demo12345'}).json()
TOKEN = tok.get('token') or tok.get('access_token')
H = {'Authorization': f'Bearer {TOKEN}', 'X-Entity-Id': 'ent_ksc'}

def g(path):
    try:
        r = requests.get(f'{BASE}{path}', headers=H, timeout=30)
        return r.status_code, (r.json() if r.headers.get('content-type','').startswith('application/json') else r.text)
    except Exception as e:
        return 0, str(e)

report = {}

# ---- Sales orders status tab counts vs list
sc, so = g('/api/sales-orders?entity=ent_ksc&limit=1000')
if sc == 200:
    items = so if isinstance(so, list) else so.get('items', [])
    by_status = {}
    for it in items:
        s = it.get('status') or it.get('state')
        by_status[s] = by_status.get(s, 0) + 1
    report['sales_orders'] = {'total': len(items), 'by_status': by_status}

# ---- PO
for ep,label in [('/api/purchase-orders?entity=ent_ksc&limit=1000', 'purchase_orders'),
                 ('/api/vendor-bills?entity=ent_ksc&limit=1000', 'vendor_bills'),
                 ('/api/customer-advances?entity=ent_ksc&limit=1000', 'customer_advances'),
                 ('/api/payment-plans?entity=ent_ksc&limit=1000', 'payment_plans'),
                 ('/api/finance-cases?entity=ent_ksc&limit=1000', 'finance_cases'),
                 ('/api/credit-overrides?entity=ent_ksc&limit=1000', 'credit_overrides'),
                 ('/api/payroll-runs?entity=ent_ksc&limit=1000', 'payroll_runs'),
                 ('/api/makloon-orders?entity=ent_ksc&limit=1000', 'makloon_orders'),
                 ('/api/sales-returns?entity=ent_ksc&limit=1000', 'sales_returns'),
                 ('/api/approvals?entity=ent_ksc&limit=1000', 'approvals'),
                 ('/api/notifications?limit=1000', 'notifications')]:
    sc, data = g(ep)
    if sc != 200:
        report[label] = {'status': sc, 'error': str(data)[:120]}
        continue
    items = data if isinstance(data, list) else data.get('items', [])
    bs = {}
    tot_amt = 0.0
    for it in items:
        s = it.get('status') or it.get('state') or it.get('kind')
        bs[s] = bs.get(s, 0) + 1
        for k in ('grand_total','total','amount','net_amount','balance','outstanding'):
            v = it.get(k)
            if isinstance(v, (int, float)):
                tot_amt += float(v); break
    report[label] = {'total': len(items), 'by_status': bs, 'sum_primary_amount': round(tot_amt, 2)}

# ---- Home desks counters
for ep,label in [('/api/home/admin?entity=ent_ksc','home_admin'),
                 ('/api/home/sales?entity=ent_ksc','home_sales'),
                 ('/api/home/finance?entity=ent_ksc','home_finance'),
                 ('/api/home/warehouse?entity=ent_ksc','home_warehouse'),
                 ('/api/home/manager?entity=ent_ksc','home_manager'),
                 ('/api/home/salesadmin?entity=ent_ksc','home_salesadmin'),
                 ('/api/cash-transactions/summary?entity=ent_ksc','cash_summary'),
                 ('/api/ar/aging?entity=ent_ksc','ar_aging'),
                 ('/api/analytics/summary?entity=ent_ksc','analytics_summary'),
                 ('/api/analytics/margin?entity=ent_ksc','analytics_margin'),
                 ('/api/analytics/hpp?entity=ent_ksc','analytics_hpp'),
                 ('/api/bi/finance?entity=ent_ksc','bi_finance'),
                 ('/api/bi/hr?entity=ent_ksc','bi_hr'),
                 ('/api/config/health','config_health')]:
    sc, data = g(ep)
    report[label] = {'status': sc, 'sample_keys': list(data.keys())[:20] if isinstance(data, dict) else type(data).__name__}
    if sc == 200 and isinstance(data, dict):
        # Capture numeric-looking leaf summary
        report[label]['payload'] = {k: (v if not isinstance(v,(list,dict)) else (f'len={len(v)}' if isinstance(v,list) else '{...}')) for k,v in list(data.items())[:40]}

os.makedirs('C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/test_reports', exist_ok=True)
with open('C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/test_reports/iter149_numbers_sweep.json', 'w') as f:
    json.dump(report, f, indent=2, default=str)
print(json.dumps({k: v if 'payload' not in str(v) else {'status': v.get('status'), 'keys': v.get('sample_keys')} for k,v in report.items()}, indent=2, default=str)[:6000])
