"""Local real-Mongo/ASGI integration suite. Uses a fresh isolated database per run.
Run with MONGO_URL pointing at a disposable local Mongo instance; no production data.
"""
import asyncio
import copy
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

assert os.environ.get('MONGO_URL', '').startswith('mongodb://127.0.0.1:'), 'Local Mongo only'
os.environ['DB_NAME'] = 'kn_rfid_v2_test_' + uuid4().hex
sys.path.insert(0, str(Path(__file__).parents[1]))
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from db import db, client
from routers.rfid_v2 import router
from services import rfid_v2_service as s
from services.rfid_ingest_service import hash_device_key

FIXTURES = json.loads((Path(__file__).parent / 'fixtures/u300_contract.json').read_text())
passed = []


def check(condition, label):
    assert condition, label
    passed.append(label)
    print('PASS', label)


async def seed(n=1, typ='shipment'):
    suffix = uuid4().hex
    device = {'id': 'dev-' + suffix, 'type': 'fixed_reader', 'warehouse_id': 'wh-' + suffix,
              'enabled': True, 'api_key_hash': hash_device_key(suffix)}
    await db.rfid_devices.insert_one(copy.deepcopy(device))
    cfg = copy.deepcopy(FIXTURES['DeviceConfig'])
    cfg.update(device_id=device['id'], warehouse_id=device['warehouse_id'], site_id='site', config_version='v1')
    cfg['logical_gates'][0].update(logical_gate_id='gate', warehouse_id=device['warehouse_id'], site_id='site')
    await s.publish_config(device, cfg, {'id': 'operator'})
    device['v2_config_version'] = 'v1'
    ids = ['r-' + suffix + '-' + str(i) for i in range(n)]
    epcs = ['E2' + suffix[:18].upper() + f'{i:04X}' for i in range(n)]
    source = {'source_type': typ, 'source_id': 'src-' + suffix}
    so = 'so-' + suffix
    await db.sales_orders.insert_one({'id': so, 'status': 'in_progress', 'number': so})
    if typ == 'shipment':
        await db.shipments.insert_one({'id': source['source_id'], 'order_id': so, 'warehouse_id': device['warehouse_id'],
            'status': 'dispatched', 'rolls': [{'roll_id': rid} for rid in ids]})
    elif typ == 'wh_transfer':
        await db.warehouse_transfers.insert_one({'id': source['source_id'], 'source_warehouse_id': device['warehouse_id'],
            'dest_warehouse_id': 'dest', 'status': 'dispatched', 'items': [{'rolls': [{'roll_id': rid} for rid in ids]}]})
    else:
        await db.putaway_orders.insert_one({'id': source['source_id'], 'from_warehouse_id': device['warehouse_id'],
            'to_warehouse_id': 'dest', 'status': 'in_transit', 'items': [{'roll_id': rid} for rid in ids]})
    for rid, epc in zip(ids, epcs):
        roll = {'id': rid, 'warehouse_id': device['warehouse_id'], 'status': 'in_transit_sales' if typ == 'shipment' else 'in_transit_transfer',
                'reserved_ref': {'type': 'sales_order' if typ == 'shipment' else typ, 'id': so if typ == 'shipment' else source['source_id']}}
        if typ == 'putaway':
            roll['active_movement'] = {'type': 'putaway', 'id': source['source_id']}
        await db.inventory_rolls.insert_one(roll)
        await db.rfid_tags.insert_one({'epc': epc, 'roll_id': rid, 'status': 'active'})
    await s.bind_manifest(device, 'gate', source, 'out', {'id': 'operator'})
    return device, cfg, epcs, suffix


def batch(cfg, epcs, mode='live', pid=None):
    pid = pid or uuid4().hex
    b = {'schema_version': 2, 'batch_id': uuid4().hex, 'mode': mode, 'config_version': 'v1',
         'context': {'kind': 'gate', 'logical_gate_id': 'gate', 'local_passage_id': pid}, 'events': []}
    for epc in epcs:
        b['events'].append({'event_id': uuid4().hex, 'raw_epc': epc, 'epc': epc, 'captured_at': s.now(),
                            'time_quality': 'synced', 'antenna': '1', 'rssi_dbm': -45})
    c = {'logical_gate_id': 'gate', 'config_version': 'v1', 'mode': mode, 'closing_captured_at': s.now(),
         'boundary_reason': 'idle_timeout', 'last_event_id': b['events'][-1]['event_id'], 'observed_event_count': len(epcs),
         'capture_complete': True, 'direction': 'out', 'direction_evidence': {'source': 'fixed_profile',
         'profile_binding_id': cfg['hardware_profile_id'], 'sensor_sequence': []}}
    return b, c


async def run():
    await db.command('ping')
    await s.ensure_indexes()
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://local.test') as http:
        dev, cfg, epcs, token = await seed(2)
        headers = {'X-Device-Key': token}
        response = await http.get('/api/rfid/v2/device/config', headers=headers)
        check(response.status_code == 200, 'real device-key config route')
        s.validate('DeviceConfig', response.json())
        check((await http.get('/api/rfid/v2/device/gate-state', headers=headers, params={'logical_gate_id': 'other-gate'})).status_code == 403, 'device cannot read unbound gate')
        changed_cfg = copy.deepcopy(cfg); changed_cfg['policies']['retry_initial_seconds'] += 1
        try: await s.publish_config(dev, changed_cfg, {'id': 'operator'})
        except Exception as exc: check(exc.status_code == 409, 'published config immutable')
        else: raise AssertionError('config mutated')
        check((await http.post('/api/rfid/v2/events', headers={**headers, 'Content-Type': 'application/json'}, content='{"bad": NaN}')).status_code == 400, 'nonfinite JSON rejected')
        check((await http.get('/api/rfid/v2/device/config')).status_code == 401, 'missing device key denied')
        check((await http.get('/api/rfid/v2/device/config', headers={'X-Device-Key': 'wrong'})).status_code == 401, 'wrong key denied')
        b, c = batch(cfg, epcs)
        path = '/api/rfid/v2/passages/' + b['context']['local_passage_id']
        response = await http.post('/api/rfid/v2/events', headers=headers, json=b)
        check(response.status_code == 200 and all(a['durable'] for a in response.json()['event_acks']), 'journaled per-event ACK')
        s.validate('EventsResponse', response.json())
        r = await http.post('/api/rfid/v2/events', headers=headers, json=b)
        check(all(a['status'] == 'duplicate' for a in r.json()['event_acks']), 'retry is durable duplicate')
        ch = {**headers, 'Idempotency-Key': 'close1'}
        response = await http.post(path + '/close', headers=ch, json=c)
        check(response.status_code == 200, 'close route returns decision')
        decision = response.json()
        check(decision['verdict'] == 'GREEN' and decision['counts']['matched'] == 2, 'full manifest GREEN')
        roll = await db.inventory_rolls.find_one({'warehouse_id': dev['warehouse_id']})
        check(roll['status'] == 'in_transit_sales' and not roll.get('gate_exit'), 'gate protocol does not mutate stock or legacy roll record')
        from services.gate_evaluator import evaluate
        check((await evaluate('out', dev['warehouse_id'], roll))['result'] == 'red', 'legacy evaluator respects V2 crossing')
        s.validate('GateDecision', decision)
        r = await http.post(path + '/close', headers=ch, json=c)
        check(r.json() == decision, 'same close preserves decision and expiry')
        conflict = copy.deepcopy(c); conflict['capture_complete'] = False
        check((await http.post(path + '/close', headers=ch, json=conflict)).status_code == 409, 'changed close rejected')
        changed = copy.deepcopy(b); changed['events'][0]['rssi_dbm'] = -66
        check((await http.post('/api/rfid/v2/events', headers=headers, json=changed)).status_code == 409, 'changed event payload rejected')
        other = copy.deepcopy(b); other['context']['local_passage_id'] = 'another'
        check((await http.post('/api/rfid/v2/events', headers=headers, json=other)).status_code == 409, 'event replay into other passage rejected')
        r = await http.get('/api/rfid/v2/device/gate-state', headers=headers, params={'logical_gate_id': 'gate', 'local_passage_id': b['context']['local_passage_id']})
        s.validate('GateState', r.json())
        check(r.json()['decision'] == decision, 'gate state returns stored passage decision')
        check((await http.post(path + '/acknowledge', headers=headers, json={'device_id': dev['id'], 'note': 'device cannot ack'})).status_code == 401, 'device key cannot acknowledge')
        second, second_close = batch(cfg, epcs)
        await s.events(dev, second)
        replay = await s.close(dev, second['context']['local_passage_id'], second_close, 'second')
        check(replay['verdict'] == 'RED' and replay['reason_code'] in ('REPLAY_CROSSING', 'REPLAY_EXIT'), 'second passage cannot reuse crossing')
        await s.acknowledge(dev, second['context']['local_passage_id'], 'checked by operator', {'id': 'operator'})
        check(not (await s.gate_state(dev, 'gate'))['latched'], 'operator acknowledge clears latch')
        check((await s.close(dev, second['context']['local_passage_id'], second_close, 'second'))['verdict'] == 'RED', 'acknowledge never changes verdict')
        await db.rfid_devices.update_one({'id': dev['id']}, {'$set': {'enabled': False}})
        check((await http.get('/api/rfid/v2/device/config', headers=headers)).status_code == 403, 'disabled reader denied')

    for scenario in ('missing', 'unknown', 'incomplete', 'backfill', 'wrong-direction', 'changed-manifest', 'pending', 'max-duration'):
        dev, cfg, epcs, _ = await seed(2)
        b, c = batch(cfg, epcs[:1] if scenario == 'missing' else epcs, mode='backfill' if scenario == 'backfill' else 'live')
        if scenario == 'unknown':
            b['events'][0].update(raw_epc='E2' + 'F' * 22, epc='E2' + 'F' * 22)
        if scenario == 'incomplete': c['capture_complete'] = False
        if scenario == 'wrong-direction': c['direction'] = 'in'
        if scenario == 'max-duration': c['boundary_reason'] = 'max_duration'
        await s.events(dev, b)
        if scenario == 'changed-manifest':
            await db.shipments.update_one({'warehouse_id': dev['warehouse_id']}, {'$set': {'rolls': [{'roll_id': 'changed'}]}})
        if scenario == 'pending':
            c['observed_event_count'] += 1
            try: await s.close(dev, b['context']['local_passage_id'], c, 'k')
            except Exception as exc: check(exc.status_code == 503, 'pending evidence is retryable'); continue
            raise AssertionError('pending accepted')
        d = await s.close(dev, b['context']['local_passage_id'], c, 'k')
        if scenario == 'missing':
            # PREP-D1 K-RFID-10 sesi dokumen bertahap: trip parsial hijau, sisa roll = pending (dinilai saat dokumen
            # ditutup). Agent 0.4 (DecisionPolicy.validGreen mensyaratkan pending = 0) tetap TIDAK menyalakan hijau.
            check(d['verdict'] == 'GREEN' and d['counts']['pending'] == 1 and not d['latched'],
                  'missing: partial trip green with pending remainder (no alarm)')
            continue
        check(d['verdict'] != 'GREEN' and not d['allow_live_signal'], scenario + ' cannot grant clearance')
    for typ in ('wh_transfer', 'putaway'):
        dev, cfg, epcs, _ = await seed(1, typ)
        b, c = batch(cfg, epcs)
        await s.events(dev, b)
        d = await s.close(dev, b['context']['local_passage_id'], c, 'k')
        check(d['verdict'] == 'GREEN', typ + ' real document evaluator')
    for scenario in ('linked-so', 'cancelled-linked-so', 'nonmember', 'inbound-transfer'):
        dev, cfg, epcs, _ = await seed(1, 'wh_transfer')
        tr = await db.warehouse_transfers.find_one({'source_warehouse_id': dev['warehouse_id']})
        roll = await db.inventory_rolls.find_one({'warehouse_id': dev['warehouse_id']})
        if scenario in ('linked-so', 'cancelled-linked-so'):
            so_id = 'commit-' + uuid4().hex
            await db.sales_orders.insert_one({'id': so_id, 'status': 'cancelled' if scenario == 'cancelled-linked-so' else 'in_progress'})
            await db.inventory_rolls.update_one({'id': roll['id']}, {'$set': {'reserved_ref': {'type': 'sales_order', 'id': so_id},
                'transfer_ref': {'type': 'wh_transfer', 'id': tr['id'], 'so_id': so_id}}})
        if scenario == 'nonmember':
            await db.warehouse_transfers.update_one({'id': tr['id']}, {'$set': {'items': [{'rolls': [{'roll_id': 'other'}]}]}})
            from services.gate_evaluator import evaluate
            check((await evaluate('out', dev['warehouse_id'], roll))['result'] == 'red', 'legacy transfer checks actual roll membership')
        if scenario == 'inbound-transfer':
            await db.warehouse_transfers.update_one({'id': tr['id']}, {'$set': {'source_warehouse_id': 'origin', 'dest_warehouse_id': dev['warehouse_id']}})
            cfg['config_version'] = 'v2'; cfg['logical_gates'][0]['direction'] = 'in'
            await s.publish_config(dev, cfg, {'id': 'operator'}); dev['v2_config_version'] = 'v2'
            await s.bind_manifest(dev, 'gate', {'source_type': 'wh_transfer', 'source_id': tr['id']}, 'in', {'id': 'operator'})
        b, c = batch(cfg, epcs)
        if scenario == 'inbound-transfer':
            b['config_version'] = c['config_version'] = 'v2'; c['direction'] = 'in'
        await s.events(dev, b)
        d = await s.close(dev, b['context']['local_passage_id'], c, 'k')
        check((d['verdict'] == 'GREEN') == (scenario in ('linked-so', 'inbound-transfer')), scenario + ' correct clearance')
    dev, cfg, epcs, _ = await seed()
    b, c = batch(cfg, epcs)
    responses = await asyncio.gather(*[s.events(dev, b) for _ in range(8)])
    check(sum(r['event_acks'][0]['status'] == 'accepted' for r in responses) == 1, '8 concurrent uploads persist once')
    results = await asyncio.gather(*[s.close(dev, b['context']['local_passage_id'], c, 'k') for _ in range(8)])
    check(len({d['decision_id'] for d in results}) == 1, '8 concurrent closes return one durable decision')
    for scenario in ('old-config', 'expired-close', 'unsynced', 'late-binding', 'bad-antenna', 'invalid-epc'):
        dev, cfg, epcs, _ = await seed()
        b, c = batch(cfg, epcs)
        if scenario == 'expired-close': c['closing_captured_at'] = (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
        if scenario == 'unsynced': b['events'][0]['time_quality'] = 'unsynced'
        if scenario == 'late-binding': b['events'][0]['captured_at'] = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
        if scenario == 'bad-antenna': b['events'][0]['antenna'] = '8'
        if scenario == 'invalid-epc': b['events'][0].update(raw_epc='INVALID', epc=None)
        ack = await s.events(dev, b)
        if scenario in ('bad-antenna', 'invalid-epc'):
            check(ack['event_acks'][0]['status'] == 'quarantined' and ack['event_acks'][0]['durable'], scenario + ' retained as quarantine')
        if scenario == 'old-config':
            revised = copy.deepcopy(cfg); revised['config_version'] = 'v2'
            await s.publish_config(dev, revised, {'id': 'operator'})
        d = await s.close(dev, b['context']['local_passage_id'], c, 'k')
        check(not d['allow_live_signal'] and d['verdict'] != 'GREEN', scenario + ' fails closed')
        late = copy.deepcopy(b); late['events'][0]['event_id'] = uuid4().hex
        try: await s.events(dev, late)
        except Exception as exc: check(exc.status_code == 409, scenario + ' closed passage rejects late new event')
        else: raise AssertionError('late event accepted')
    print(json.dumps({'passed': len(passed), 'database': os.environ['DB_NAME'], 'cases': passed}, indent=2))
    client.close()


if __name__ == '__main__':
    asyncio.run(run())
