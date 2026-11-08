"""PREP-D2 — status kios / layar monitor gate untuk reader V2 (bentuk sama dengan `/rfid/gate/{id}/status` lama) +
KUNING: lintasan "perlu diperiksa, barang jalan" tampil di samping hijau/merah (K-RFID-09). Merah terkunci tetap
ditampilkan sampai kunci gate diakui (izin approve); kuning tidak mengunci.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException

from db import db
from services import gate_evaluator as ge
from services import rfid_v2_core as core
from services import rfid_v2_latch as latch
from services import rfid_v2_policy as policy
from services.rfid_v2_common import collection, parse_ts

VERDICT_KIOSK = {'GREEN': 'green', 'REVIEW': 'yellow', 'RED': 'red', 'CANCELLED': 'info'}
RESULT = {'RED': 'red', 'REVIEW': 'yellow'}


async def _reads(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    dec = row.get('decision') or {}
    claims = await collection('rfid_v2_crossings').find({'passage': row['_id']}, {'_id': 0, 'roll_id': 1}).to_list(200)
    out: Dict[str, Dict[str, Any]] = {c['roll_id']: {'id': c['roll_id'], 'roll_id': c['roll_id'], 'result': 'green',
                                                     'reason': 'Sesuai dokumen', 'action': 'Loloskan'} for c in claims}
    for r in dec.get('reasons') or []:
        key = r.get('roll_id') or r.get('epc')
        if not key or r.get('level') not in RESULT:
            continue
        cur = out.get(key)
        if cur and cur['result'] == 'red':
            continue
        out[key] = {'id': key, 'roll_id': r.get('roll_id'), 'epc': r.get('epc'), 'result': RESULT[r['level']],
                    'reason': r.get('message') or '',
                    'action': ge.action_for(r['code']) if r['level'] == 'RED' else 'Barang jalan — masuk antrean periksa.'}
    ids = [x['roll_id'] for x in out.values() if x.get('roll_id')]
    nos = {r['id']: r.get('roll_no') for r in await db.inventory_rolls.find(
        {'id': {'$in': ids}}, {'_id': 0, 'id': 1, 'roll_no': 1}).to_list(len(ids) + 1)}
    rows = list(out.values())
    for x in rows:
        x['roll_no'] = nos.get(x.get('roll_id'))
    rows.sort(key=lambda x: {'red': 0, 'yellow': 1, 'green': 2}[x['result']])
    return rows[:50]


async def kiosk_status(dev: Dict[str, Any], ttl_s: int = 30) -> Dict[str, Any]:
    nowdt = datetime.now(timezone.utc)
    hb = dev.get('last_heartbeat') or dev.get('v2_telemetry_at')
    hb_dt = parse_ts(hb) if hb else None
    gate_id = None
    try:
        cfg = await core.config(dev)
        gate_id = cfg['logical_gates'][0]['logical_gate_id']
    except HTTPException:
        cfg = None
    lt = await latch.active(dev['id'], gate_id) if gate_id else None
    passages = collection('rfid_v2_passages')
    proj = {'decision': 1, 'created_at': 1, 'local_passage_id': 1, 'acknowledged': 1, 'simulated': 1, 'gate_txn': 1}
    row = None
    if lt and lt.get('passages'):
        row = await passages.find_one({'_id': lt['passages'][-1]['passage']}, proj)
    if not row:
        row = await passages.find_one({'device_id': dev['id'], 'state': 'FINAL'}, proj, sort=[('created_at', -1)])
    show = None
    if row and row.get('decision'):
        dec = row['decision']
        at = parse_ts(dec.get('created_at') or row.get('created_at'))
        age = int((nowdt - at).total_seconds()) if at else None
        reads = await _reads(row)
        show = {'id': row.get('local_passage_id'), 'verdict': VERDICT_KIOSK.get(dec['verdict'], 'info'),
                'started_at': row.get('created_at'), 'last_at': dec.get('created_at'), 'age_s': age,
                'expired': (age is None or age > ttl_s) and not lt, 'reads': reads,
                'red_count': sum(1 for r in reads if r['result'] == 'red'),
                'yellow_count': sum(1 for r in reads if r['result'] == 'yellow'),
                'green_count': sum(1 for r in reads if r['result'] == 'green'),
                'reason_codes': dec.get('reason_codes') or [], 'action': policy.ACTIONS.get(dec['verdict'], ''),
                'sources': [s.get('display_ref') for s in dec.get('sources') or []],
                'counts': dec.get('counts') or {}, 'simulated': bool(row.get('simulated'))}
    return {'protocol': 'v2', 'server_time': nowdt.isoformat(), 'verdict_ttl_s': ttl_s, 'gate_id': gate_id,
            'device': {'id': dev['id'], 'code': dev.get('code'), 'name': dev.get('name'), 'status': dev.get('status'),
                       'enabled': dev.get('enabled') is not False, 'direction': dev.get('direction'),
                       'last_heartbeat': hb, 'heartbeat_age_s': int((nowdt - hb_dt).total_seconds()) if hb_dt else None},
            'passage': show, 'latched': bool(lt), 'latch_id': (lt or {}).get('latch_id'),
            'latch_reason_codes': (lt or {}).get('reason_codes') or []}
