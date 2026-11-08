"""Multi-SJ, stable history, evidence export and real session/scope regression tests."""
import asyncio
import copy
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from httpx import AsyncClient, ASGITransport
from run_rfid_v2_integration import seed, batch, check, passed, db, client, s, router
from entity_write_guard import EntityWriteGuardMiddleware


async def pair():
    dev, cfg, one, key = await seed()
    second_dev, _, two, _ = await seed()
    first = await db.shipments.find_one({'warehouse_id': dev['warehouse_id']})
    second = await db.shipments.find_one({'warehouse_id': second_dev['warehouse_id']})
    await db.shipments.update_one({'id': second['id']}, {'$set': {'warehouse_id': dev['warehouse_id']}})
    await db.inventory_rolls.update_one({'warehouse_id': second_dev['warehouse_id']}, {'$set': {'warehouse_id': dev['warehouse_id']}})
    sources = [{'source_type': 'shipment', 'source_id': d['id']} for d in (first, second)]
    return dev, cfg, one + two, key, sources


async def rejected(fn, status, label):
    try:
        await fn
    except HTTPException as exc:
        check(exc.status_code == status, label)
    else:
        raise AssertionError(label + ': not rejected')


async def run():
    await s.ensure_indexes()
    for scenario in ('full', 'missing', 'cancelled', 'changed', 'rebound'):
        dev, cfg, epcs, _, sources = await pair()
        binding = await s.bind_manifests(dev, 'gate', sources, 'out', {'id': 'operator'})
        check(binding['source_ref']['source_type'] == 'gate_manifest' and len(binding['sources']) == 2, scenario + ': two source documents preserved')
        b, c = batch(cfg, epcs[:1] if scenario == 'missing' else epcs)
        await s.events(dev, b)
        if scenario == 'cancelled':
            await db.shipments.update_one({'id': sources[1]['source_id']}, {'$set': {'status': 'cancelled'}})
        if scenario == 'changed':
            await db.shipments.update_one({'id': sources[1]['source_id']}, {'$set': {'rolls': [{'roll_id': 'replaced-roll'}]}})
        if scenario == 'rebound':
            await s.bind_manifest(dev, 'gate', sources[0], 'out', {'id': 'operator'})
        decision = await s.close(dev, b['context']['local_passage_id'], c, 'close')
        s.validate('GateDecision', decision)
        check((decision['verdict'] == 'GREEN') == (scenario in ('full', 'rebound')), scenario + ': correct aggregate clearance')
        if scenario == 'full':
            check(decision['counts']['matched'] == 2, 'aggregate counts include both SJs')
            await s.bind_manifest(dev, 'gate', sources[0], 'out', {'id': 'operator'})
            again, close_again = batch(cfg, epcs[:1])
            await s.events(dev, again)
            d = await s.close(dev, again['context']['local_passage_id'], close_again, 'again')
            check(d['verdict'] == 'RED', 'regrouping cannot bypass per-source crossing protection')

    dev, cfg, epcs, _, sources = await pair()
    await rejected(s.bind_manifests(dev, 'gate', [sources[0], sources[0]], 'out', {'id': 'o'}), 400, 'duplicate SJ rejected')
    await rejected(s.bind_manifests(dev, 'gate', [], 'out', {'id': 'o'}), 400, 'empty group rejected')
    await rejected(s.bind_manifests(dev, 'gate', sources * 11, 'out', {'id': 'o'}), 400, 'group capacity enforced')
    first = await db.shipments.find_one({'id': sources[0]['source_id']})
    await db.shipments.update_one({'id': sources[1]['source_id']}, {'$set': {'rolls': first['rolls']}})
    await rejected(s.bind_manifests(dev, 'gate', sources, 'out', {'id': 'o'}), 409, 'same roll on two SJs rejected')
    await db.shipments.update_one({'id': sources[1]['source_id']}, {'$set': {'warehouse_id': 'other'}})
    await rejected(s.bind_manifests(dev, 'gate', sources, 'out', {'id': 'o'}), 409, 'cross-warehouse SJ rejected')

    dev, cfg, epcs, _, sources = await pair()
    await s.bind_manifest(dev, 'gate', sources[0], 'out', {'id': 'o'})
    first = await db.shipments.find_one({'id': sources[0]['source_id']})
    second = await db.shipments.find_one({'id': sources[1]['source_id']})
    rid = first['rolls'][0]['roll_id']
    await db.shipments.update_one({'id': second['id']}, {'$push': {'rolls': {'roll_id': rid}}})
    await db.inventory_rolls.update_one({'id': rid}, {'$set': {'reserved_ref': {'type': 'sales_order', 'id': second['order_id']}}})
    b, c = batch(cfg, epcs[:1]); await s.events(dev, b)
    d = await s.close(dev, b['context']['local_passage_id'], c, 'k')
    check(d['reason_code'] == 'SOURCE_CONTEXT_MISMATCH' and not d['allow_live_signal'], 'other active document cannot authorize selected SJ')

    dev, cfg, epcs, key, sources = await pair()
    for index in range(5):
        b, _ = batch(cfg, epcs[:1], pid='page-' + str(index)); await s.events(dev, b)
    await db.rfid_v2_passages.update_many({'device_id': dev['id']}, {'$set': {'created_at': '2026-10-19T00:00:00.000000Z'}})
    cursor, visited = None, []
    while True:
        page, cursor = await s.history(dev['id'], cursor, 2)
        visited += [p['local_passage_id'] for p in page]
        check(all('events' not in p for p in page), 'history excludes raw observations')
        if cursor is None: break
    check(len(visited) == len(set(visited)) == 5, 'pagination tie-breaker prevents omissions/duplicates')
    await rejected(s.history(dev['id'], 'not-a-cursor', 2), 400, 'invalid history cursor rejected')

    # Real user sessions and existing role permission matrix, no auth stubs.
    for eid in ('scope-A', 'scope-B'):
        await db.business_entities.insert_one({'id': eid, 'status': 'active', 'name': eid})
    await db.warehouses.insert_one({'id': dev['warehouse_id'], 'name': 'Test shared warehouse', 'sharing_mode': 'shared'})
    await db.permission_settings.insert_one({'id': 'default', 'matrix': {
        'gate_a': {'wms': ['view', 'scan']}, 'gate_ab': {'wms': ['view', 'scan']}, 'no_access': {}}})
    tokens = {}
    for role, entities in (('gate_a', ['scope-A']), ('gate_ab', ['scope-A', 'scope-B']), ('no_access', ['scope-A'])):
        uid, token = uuid4().hex, uuid4().hex
        await db.users.insert_one({'id': uid, 'name': role, 'role': role, 'status': 'active', 'home_entity_id': 'scope-A', 'allowed_entity_ids': entities})
        await db.sessions.insert_one({'token': token, 'user_id': uid, 'expires_at': datetime.now(timezone.utc) + timedelta(hours=24)})
        tokens[role] = {'Authorization': 'Bearer ' + token, 'X-Entity-Id': 'scope-A'}
    for src, eid in zip(sources, ('scope-A', 'scope-B')):
        await db.shipments.update_one({'id': src['source_id']}, {'$set': {'entity_id': eid}})
    app = FastAPI(); app.include_router(router); app.add_middleware(EntityWriteGuardMiddleware)
    base = '/api/rfid/v2/ops/devices/' + dev['id']
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://local.test') as http:
        body = {'logical_gate_id': 'gate', 'direction': 'out', 'sources': sources}
        r = await http.post(base + '/manifest', headers=tokens['gate_a'], json=body)
        check(r.status_code == 404, 'single-entity operator cannot bind foreign SJ')
        r = await http.post(base + '/manifest', headers=tokens['gate_ab'], json=body)
        check(r.status_code == 200 and len(r.json()['sources']) == 2, 'authorized multi-entity operator binds group via real route')
        b, c = batch(cfg, epcs); await s.events(dev, b)
        c['capture_complete'] = False
        await s.close(dev, b['context']['local_passage_id'], c, 'scope-close')
        url = base + '/passages/' + b['context']['local_passage_id'] + '/evidence'
        check((await http.get(url, headers={'X-Device-Key': key})).status_code == 401, 'device key cannot export evidence')
        check((await http.get(url, headers=tokens['no_access'])).status_code == 403, 'user without WMS permission cannot export')
        check((await http.get(url, headers=tokens['gate_a'])).status_code == 404, 'foreign-entity passage export denied')
        r = await http.get(url, headers=tokens['gate_ab'])
        check(r.status_code == 200 and len(r.json()['passage']['events']) == 2, 'authorized export contains both durable observations')
        check(r.headers['cache-control'] == 'no-store' and 'attachment' in r.headers['content-disposition'], 'evidence downloads without browser caching')
        r = await http.get(base, headers=tokens['gate_a'])
        check(r.status_code == 200 and all(p['local_passage_id'] != b['context']['local_passage_id'] for p in r.json()['passages']) and not r.json()['bindings'], 'overview hides foreign-entity group')
        ack_url = '/api/rfid/v2/passages/' + b['context']['local_passage_id'] + '/acknowledge'
        ack_body = {'device_id': dev['id'], 'note': 'reviewed evidence'}
        check((await http.post(ack_url, headers=tokens['gate_a'], json=ack_body)).status_code == 404, 'foreign-entity alarm acknowledge denied')
        check((await http.post(ack_url, headers=tokens['gate_ab'], json=ack_body)).status_code == 200, 'authorized operator acknowledges group alarm')
        row = await s.collection('rfid_v2_passages').find_one({'_id': s.digest([dev['id'], b['context']['local_passage_id']])})
        check(row['event_count'] == 2 and row['decision']['verdict'] != 'GREEN', 'export and acknowledge preserve evidence and verdict')
    print(json.dumps({'extended_assertions': len(passed), 'cases': passed}, indent=2))
    client.close()


if __name__ == '__main__':
    asyncio.run(run())
