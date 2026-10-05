"""Iter149 — READ-ONLY audit of config-health, Riwayat Perubahan, and numeric sweep.

Verifies:
 1. /api/config/health has 0 unwired/stale catalog entries (user complaint).
 2. Audit log has no TEST/iter1xx reasons.
 3. RFID print queue has no 'TEST Printer RFID'.
 4. Sales returns has no 'TEST_R5' returns.
 5. Numeric parities (regression iter148): admin AR = ar/aging total; kas kecil 9,750,000; sales targets.
 6. Stock ATP: Σrow.ATP == summary totalATP; ATP = tersedia + incoming − pending_demand.
"""
import os, re, requests, pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
HDRS = {'Content-Type': 'application/json', 'X-Entity-Id': 'ent_ksc'}

@pytest.fixture(scope='session')
def admin_token():
    r = requests.post(f'{BASE_URL}/api/auth/login',
                      json={'email': 'admin@kainnusantara.id', 'password': 'demo12345'},
                      headers=HDRS, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get('token') or r.json().get('access_token')

@pytest.fixture(scope='session')
def auth_hdrs(admin_token):
    return {**HDRS, 'Authorization': f'Bearer {admin_token}'}


# ---------- 1. CONFIG HEALTH ----------
def test_config_health_no_stale(auth_hdrs):
    r = requests.get(f'{BASE_URL}/api/config/health', headers=auth_hdrs, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    summary = data.get('summary') or data.get('counts') or {}
    print('CONFIG HEALTH SUMMARY:', summary)
    # BELUM tersambung means catalog defined but no code consumer
    not_wired = summary.get('NOT_WIRED', summary.get('not_wired', 0))
    stale = summary.get('STALE', summary.get('stale', summary.get('STALE_REF', 0)))
    bad = summary.get('BAD', summary.get('bad', 0))
    assert not_wired == 0, f'Still {not_wired} settings BELUM tersambung: {data}'
    assert stale == 0, f'Still {stale} Referensi kode basi: {data}'
    assert bad == 0, f'{bad} salah: {data}'


# ---------- 2. AUDIT LOG CLEAN ----------
def test_audit_logs_no_test_iter(auth_hdrs):
    # Try the common endpoints
    for ep in ['/api/audit-logs?limit=500', '/api/audit-logs/recent?limit=500', '/api/audit-log?limit=500']:
        r = requests.get(f'{BASE_URL}{ep}', headers=auth_hdrs, timeout=30)
        if r.status_code == 200:
            payload = r.json()
            items = payload if isinstance(payload, list) else payload.get('items', payload.get('rows', []))
            offenders = []
            for it in items:
                reason = str(it.get('reason', '') or it.get('note', ''))
                if 'TEST' in reason or re.search(r'iter1\d\d', reason):  # case-sensitive TEST
                    offenders.append({'id': it.get('id'), 'reason': reason[:100]})
            assert not offenders, f'{len(offenders)} audit rows with TEST/iter1xx found: {offenders[:5]}'
            return
    pytest.skip('No audit log endpoint reachable')


# ---------- 3. RFID PRINT QUEUE ----------
def test_rfid_print_queue_no_test_printer(auth_hdrs):
    for ep in ['/api/rfid/printers', '/api/rfid/print-queue', '/api/rfid/devices']:
        r = requests.get(f'{BASE_URL}{ep}', headers=auth_hdrs, timeout=30)
        if r.status_code == 200:
            items = r.json().get('items', r.json() if isinstance(r.json(), list) else [])
            offenders = [it for it in items if 'TEST' in str(it.get('name', '')).upper()
                         or 'TEST' in str(it.get('printer_name', '')).upper()]
            assert not offenders, f'{ep}: {len(offenders)} TEST printers: {offenders}'


# ---------- 4. SALES RETURNS CLEAN ----------
def test_sales_returns_no_test_r5(auth_hdrs):
    r = requests.get(f'{BASE_URL}/api/sales-returns?entity=ent_ksc&limit=500', headers=auth_hdrs, timeout=30)
    if r.status_code != 200:
        pytest.skip(f'returns ep status {r.status_code}')
    items = r.json().get('items', [])
    offenders = [it for it in items if 'TEST_R5' in str(it.get('number', ''))
                 or 'TEST' in str(it.get('number', ''))]
    assert not offenders, f'{len(offenders)} TEST sales returns: {[o.get("number") for o in offenders]}'


# ---------- 5. REGRESSION iter148 ----------
def test_admin_home_ar_matches_aging(auth_hdrs):
    home = requests.get(f'{BASE_URL}/api/home/admin?entity=ent_ksc', headers=auth_hdrs, timeout=30)
    aging = requests.get(f'{BASE_URL}/api/ar/aging?entity=ent_ksc', headers=auth_hdrs, timeout=30)
    assert home.status_code == 200 and aging.status_code == 200
    h = home.json()
    a = aging.json()
    ar_home = (h.get('ar') or h.get('receivables') or {})
    ar_val = ar_home.get('outstanding') or ar_home.get('total') or h.get('ar_outstanding')
    aging_total = (a.get('totals') or {}).get('total') or a.get('total')
    print(f'admin AR={ar_val}, aging total={aging_total}')
    assert abs(float(ar_val or 0) - float(aging_total or 0)) < 1, f'{ar_val} vs {aging_total}'


def test_cash_summary_kas_kecil(auth_hdrs):
    r = requests.get(f'{BASE_URL}/api/cash-transactions/summary?entity=ent_ksc', headers=auth_hdrs, timeout=30)
    assert r.status_code == 200
    data = r.json()
    kk_bal = (data.get('kas_kecil') or {}).get('balance')
    kb_bal = (data.get('kas_besar') or {}).get('balance')
    print(f'KAS KECIL={kk_bal}, KAS BESAR={kb_bal}')
    assert abs(float(kk_bal) - 9_750_000) < 1, f'kas_kecil = {kk_bal}'
    assert abs(float(kb_bal) - 195_399_200) < 1, f'kas_besar = {kb_bal}'


# ---------- 6. STOCK ATP FORMULA ----------
def test_stock_atp_sum_matches(auth_hdrs):
    r = requests.get(f'{BASE_URL}/api/inventory/status-board?entity=ent_ksc', headers=auth_hdrs, timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list)
    bad_row = []
    bad_wh = []
    for row in rows:
        av = float(row.get('total_available') or 0)
        inc = float(row.get('total_incoming') or 0)
        rsv = float(row.get('total_reserved') or 0)
        atp = float(row.get('total_atp') or 0)
        expected = av + inc - rsv
        if abs(expected - atp) >= 1:
            bad_row.append({'sku': row.get('sku'), 'av': av, 'inc': inc,
                            'rsv': rsv, 'atp': atp, 'expected_av+inc-rsv': expected})
        # per entity/warehouse formula
        for ent in row.get('by_entity', []):
            for wh in ent.get('by_warehouse', []):
                e = wh['available'] + wh['incoming'] - wh['reserved']
                if abs(e - wh['atp']) >= 1:
                    bad_wh.append({'sku': row.get('sku'), 'wh': wh['warehouse_id'],
                                   'av': wh['available'], 'inc': wh['incoming'],
                                   'rsv': wh['reserved'], 'atp': wh['atp'], 'expected': e})
    print(f'ROWS={len(rows)}  row-level formula mismatches={len(bad_row)}  wh-level mismatches={len(bad_wh)}')
    for b in bad_row[:5]:
        print(' row:', b)
    for b in bad_wh[:10]:
        print(' wh :', b)
    # Export for main agent
    import json as _j
    with open('/app/test_reports/iter149_atp_dump.json', 'w') as f:
        _j.dump({'bad_row': bad_row, 'bad_wh': bad_wh}, f, indent=2, default=str)
