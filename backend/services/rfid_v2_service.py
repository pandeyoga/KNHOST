"""Durable U300 gate protocol. Observations never mutate stock or accounting.

One Mongo document is the atomic passage boundary: event insertion is conditional
on OPEN; close freezes that same document. No in-memory lock or TTL deletion.
"""
import copy
import base64
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from jsonschema import Draft7Validator, FormatChecker
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.write_concern import WriteConcern

from db import db
from services.epc import try_canonical
from services import gate_evaluator


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def fail(status, code, message):
    raise HTTPException(status, detail={'code': code, 'message': message, 'retryable': status >= 500})


def collection(name):
    # ACK means journaled majority write, not merely queued in this Python process.
    return db.get_collection(name, write_concern=WriteConcern(w='majority', j=True, wtimeout=5000))


async def ensure_indexes():
    await collection('rfid_v2_passages').create_index([('device_id', 1), ('created_at', -1), ('_id', -1)])
    await collection('rfid_v2_passages').create_index([('device_id', 1), ('gate_id', 1), ('acknowledged', 1), ('decision.latched', 1)])
    await collection('rfid_v2_bindings').create_index('device_id')


def _json_schema(value):
    if isinstance(value, list):
        return [_json_schema(v) for v in value]
    if not isinstance(value, dict):
        return value
    out = {k: _json_schema(v) for k, v in value.items() if k != 'nullable'}
    if value.get('nullable'):
        return {'anyOf': [out, {'type': 'null'}]}
    return out


CONTRACT = _json_schema(json.loads((Path(__file__).parents[1] / 'contracts/rfid_v2.json').read_text(encoding='utf-8-sig')))


def validate(name, payload):
    schema = {'$ref': '#/components/schemas/' + name, 'components': CONTRACT['components']}
    error = next(Draft7Validator(schema, format_checker=FormatChecker()).iter_errors(payload), None)
    if error:
        fail(400, 'INVALID_' + name.upper(), f"{'.'.join(map(str, error.path))}: {error.message}")


async def config(device, version=None):
    version = version or device.get('v2_config_version')
    row = await collection('rfid_v2_configs').find_one({'_id': digest([device['id'], version])})
    if not row:
        fail(409, 'CONFIG_REQUIRED', 'Profil V2 belum diterbitkan atau versi tidak dikenal.')
    cfg = copy.deepcopy(row['config'])
    if cfg['warehouse_id'] != device.get('warehouse_id'):
        fail(409, 'DEVICE_MOVED', 'Gudang device berubah; selesaikan antrean sebelum pindah identitas.')
    cfg['enabled'] = device.get('enabled') is not False
    cfg['server_time'] = now()
    return cfg


def gate(cfg, gate_id):
    for g in cfg['logical_gates']:
        if g['logical_gate_id'] == gate_id and g['enabled']:
            return g
    fail(403, 'GATE_NOT_BOUND', 'Gate tidak terikat pada perangkat ini.')


async def publish_config(device, cfg, actor):
    validate('DeviceConfig', cfg)
    if cfg['device_id'] != device['id'] or cfg['warehouse_id'] != device.get('warehouse_id') or cfg['device_type'] != 'fixed_reader':
        fail(400, 'IDENTITY_MISMATCH', 'Identitas profil harus mengikuti fixed reader dan gudangnya.')
    if device.get('type') not in ('gate', 'fixed_reader'):
        fail(400, 'WRONG_DEVICE_TYPE', 'Profil ini hanya untuk reader/gate.')
    if len(cfg['logical_gates']) != 1:
        fail(400, 'SINGLE_GATE_REQUIRED', 'Agent U300 saat ini menjalankan satu logical gate.')
    g = cfg['logical_gates'][0]
    if g['warehouse_id'] != cfg['warehouse_id'] or g['site_id'] != cfg['site_id']:
        fail(400, 'GATE_SCOPE', 'Lokasi dan gudang gate harus sesuai perangkat.')
    # Server does not invent a commissioned hardware profile.
    saved = copy.deepcopy(cfg)
    saved.pop('server_time', None)
    if not 1 <= cfg['policies']['gate_decision_validity_seconds'] <= 60:
        fail(400, 'INVALID_VALIDITY', 'Masa berlaku keputusan wajib 1 sampai 60 detik.')
    key = digest([device['id'], cfg['config_version']])
    try:
        await collection('rfid_v2_configs').insert_one({'_id': key, 'config': saved, 'actor_id': actor['id'], 'at': now()})
    except DuplicateKeyError:
        old = await collection('rfid_v2_configs').find_one({'_id': key})
        if old['config'] != saved:
            fail(409, 'IMMUTABLE_CONFIG', 'Versi yang sama tidak boleh diubah; terbitkan versi baru.')
    await collection('rfid_devices').update_one({'id': device['id']}, {'$set': {'v2_config_version': cfg['config_version']}})
    return {'request_id': str(uuid4()), 'server_time': now()}


async def manifest(source, warehouse, direction):
    """Read roll membership from the business document, never caller-provided roll IDs."""
    typ, sid = source['source_type'], source['source_id']
    if typ == 'shipment':
        doc = await db.shipments.find_one({'id': sid})
        if not doc or direction != 'out' or doc.get('warehouse_id') != warehouse or doc.get('status') not in gate_evaluator.SHIPMENT_ACTIVE:
            fail(409, 'SOURCE_NOT_ACTIVE', 'Surat jalan tidak aktif / bukan gate keluar gudang ini.')
        so = await db.sales_orders.find_one({'id': doc.get('order_id')})
        if not so or so.get('status') in gate_evaluator.SO_DEAD:
            fail(409, 'SO_NOT_ACTIVE', 'SO tidak ditemukan atau dibatalkan.')
        ids = [r.get('roll_id') for r in doc.get('rolls', [])]
        label = doc.get('shipment_no', sid)
    elif typ == 'wh_transfer':
        doc = await db.warehouse_transfers.find_one({'id': sid})
        field = 'source_warehouse_id' if direction == 'out' else 'dest_warehouse_id'
        if not doc or doc.get(field) != warehouse or doc.get('status') != 'dispatched' or doc.get('transfer_kind') == 'inter_entity':
            fail(409, 'SOURCE_NOT_ACTIVE', 'Transfer belum dikirim / gudang tidak sesuai.')
        ids = [r.get('roll_id') for i in doc.get('items', []) for r in i.get('rolls', [])]
        label = doc.get('code', sid)
    elif typ == 'putaway':
        doc = await db.putaway_orders.find_one({'id': sid})
        field = 'from_warehouse_id' if direction == 'out' else 'to_warehouse_id'
        if not doc or doc.get(field) != warehouse or doc.get('status') != 'in_transit':
            fail(409, 'SOURCE_NOT_ACTIVE', 'Putaway belum dikirim / gudang tidak sesuai.')
        ids = [i.get('roll_id') for i in doc.get('items', [])]
        label = doc.get('pa_number', sid)
    else:
        fail(400, 'SOURCE_UNSUPPORTED', 'Gunakan shipment, wh_transfer, atau putaway.')
    if not ids or any(not isinstance(r, str) or not r for r in ids) or len(ids) != len(set(ids)):
        fail(409, 'INVALID_MANIFEST', 'Manifest kosong, roll hilang, atau roll ganda; koreksi dokumen sumber.')
    if len(ids) > 2000:
        fail(409, 'MANIFEST_CAPACITY', 'Manifest melebihi kapasitas passage 2000 roll.')
    return {'source_type': typ, 'source_id': sid, 'display_ref': label}, sorted(ids)


async def bind_manifest(device, gate_id, source, direction, actor):
    return await bind_manifests(device, gate_id, [source], direction, actor)


def validate_sources(sources):
    if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
        fail(400, 'SOURCE_LIMIT', 'Pilih 1 sampai 20 dokumen dalam satu lintasan.')
    keys = set()
    for source in sources:
        if not isinstance(source, dict) or source.get('source_type') not in ('shipment', 'wh_transfer', 'putaway') or not isinstance(source.get('source_id'), str) or not 1 <= len(source['source_id']) <= 160:
            fail(400, 'INVALID_SOURCE', 'Jenis dan identitas dokumen tidak valid.')
        key = (source['source_type'], source['source_id'])
        if key in keys:
            fail(400, 'DUPLICATE_SOURCE', 'Dokumen yang sama hanya boleh dipilih sekali.')
        keys.add(key)
    if len(sources) > 1 and any(s['source_type'] != 'shipment' for s in sources):
        fail(400, 'GROUP_SHIPMENTS_ONLY', 'Gabungan lintasan saat ini untuk beberapa SJ; transfer/putaway diproses per dokumen.')


def binding_sources(binding):
    # 0.4 snapshots remain readable without rewriting history.
    return binding.get('sources') or [{'source_ref': binding['source_ref'], 'roll_ids': binding.get('roll_ids', [])}]


async def history(device_id, cursor=None, limit=50):
    if not 1 <= limit <= 100:
        fail(400, 'PAGE_LIMIT', 'Ukuran halaman wajib 1 sampai 100.')
    query = {'device_id': device_id}
    if cursor:
        try:
            if len(cursor) > 512:
                raise ValueError()
            at, pid = json.loads(base64.urlsafe_b64decode(cursor).decode())
            if not isinstance(at, str) or not isinstance(pid, str) or len(at) > 40 or len(pid) != 64:
                raise ValueError()
        except (ValueError, TypeError, UnicodeError):
            fail(400, 'INVALID_CURSOR', 'Posisi halaman tidak valid; mulai dari halaman pertama.')
        query['$or'] = [{'created_at': {'$lt': at}}, {'created_at': at, '_id': {'$lt': pid}}]
    rows = await collection('rfid_v2_passages').find(query, {
        'events': 0, 'close_body': 0, 'close_hash': 0, 'close_key': 0,
        'binding.roll_ids': 0, 'binding.sources.roll_ids': 0}).sort([('created_at', -1), ('_id', -1)]).to_list(limit + 1)
    page = rows[:limit]
    next_cursor = base64.urlsafe_b64encode(json.dumps([page[-1]['created_at'], page[-1]['_id']]).encode()).decode() if len(rows) > limit else None
    for row in page:
        row.pop('_id', None)
        if row.get('binding'):
            row['binding'].pop('_id', None)
    return page, next_cursor


async def bind_manifests(device, gate_id, sources, direction, actor):
    validate_sources(sources)
    cfg = await config(device)
    g = gate(cfg, gate_id)
    if direction not in ('in', 'out') or g['direction'] not in (direction, 'bidirectional'):
        fail(400, 'DIRECTION_MISMATCH', 'Arah dokumen berbeda dengan gate.')
    entries, all_ids = [], set()
    for source in sources:
        ref, ids = await manifest(source, cfg['warehouse_id'], direction)
        if all_ids.intersection(ids):
            fail(409, 'DUPLICATE_MANIFEST_ROLL', 'Roll tercantum pada lebih dari satu dokumen. Koreksi dokumen sebelum memuat.')
        all_ids.update(ids)
        entries.append({'source_ref': ref, 'roll_ids': ids})
    if len(all_ids) > 2000:
        fail(409, 'MANIFEST_CAPACITY', 'Gabungan manifest maksimal 2000 roll per lintasan.')
    ref = entries[0]['source_ref'] if len(entries) == 1 else {
        'source_type': 'gate_manifest', 'source_id': str(uuid4()),
        'display_ref': ' + '.join(e['source_ref']['display_ref'] for e in entries)}
    binding = {'_id': digest([device['id'], gate_id]), 'device_id': device['id'], 'gate_id': gate_id,
               'source_ref': ref, 'sources': entries, 'roll_ids': sorted(all_ids), 'direction': direction, 'bound_at': now(), 'actor_id': actor['id']}
    await collection('rfid_v2_bindings').replace_one({'_id': binding['_id']}, binding, upsert=True)
    return {k: v for k, v in binding.items() if k != '_id'}


async def passage(device, cfg, gate_id, passage_id, mode):
    gate(cfg, gate_id)
    pid = digest([device['id'], passage_id])
    binding = await collection('rfid_v2_bindings').find_one({'_id': digest([device['id'], gate_id])})
    seed = {'device_id': device['id'], 'local_passage_id': passage_id, 'gate_id': gate_id,
            'warehouse_id': cfg['warehouse_id'], 'config_version': cfg['config_version'], 'mode': mode,
            'state': 'OPEN', 'events': {}, 'event_count': 0, 'bytes': 0, 'binding': binding,
            'created_at': now(), 'decision': None, 'acknowledged': False}
    try:
        await collection('rfid_v2_passages').update_one({'_id': pid}, {'$setOnInsert': seed}, upsert=True)
    except DuplicateKeyError:
        pass
    p = await collection('rfid_v2_passages').find_one({'_id': pid})
    if (p['gate_id'], p['config_version'], p['mode']) != (gate_id, cfg['config_version'], mode):
        fail(409, 'PASSAGE_CONTEXT_CHANGED', 'ID passage sudah digunakan dengan konteks berbeda.')
    return p


async def events(device, body):
    validate('EventsRequest', body)
    ctx = body['context']
    if ctx['kind'] != 'gate' or not ctx.get('logical_gate_id') or not ctx.get('local_passage_id') or ctx.get('task_context_id'):
        fail(400, 'GATE_CONTEXT_REQUIRED', 'Endpoint reader ini membutuhkan konteks gate dan passage.')
    cfg = await config(device, body['config_version'])
    if len(body['events']) > min(500, cfg['limits']['max_events']) or len(json.dumps(body).encode()) > cfg['limits']['max_body_bytes']:
        fail(413, 'BATCH_TOO_LARGE', 'Pecah batch; tidak ada event batch ini yang diproses.')
    g = gate(cfg, ctx['logical_gate_id'])
    p = await passage(device, cfg, ctx['logical_gate_id'], ctx['local_passage_id'], body['mode'])
    acks = []
    for event in body['events']:
        eid = digest(event['event_id'])
        fingerprint = digest(event)
        # Global per-device event identity also prevents replay into another passage.
        claim_id = digest([device['id'], event['event_id']])
        claim = {'_id': claim_id, 'passage': p['_id'], 'fingerprint': fingerprint}
        try:
            await collection('rfid_v2_event_ids').insert_one(claim)
        except DuplicateKeyError:
            old = await collection('rfid_v2_event_ids').find_one({'_id': claim_id})
            if old['passage'] != p['_id'] or old['fingerprint'] != fingerprint:
                fail(409, 'EVENT_ID_CONFLICT', 'Event ID digunakan ulang dengan payload atau passage berbeda.')
        reason = None
        if not event.get('epc') or try_canonical(event['raw_epc']) != event.get('epc'):
            reason = 'INVALID_EPC'
        elif event['antenna'] not in g['antenna_ids']:
            reason = 'ANTENNA_NOT_BOUND'
        entry = {'event': event, 'fingerprint': fingerprint, 'quarantine': reason, 'received_at': now()}
        size = len(json.dumps(entry).encode())
        result = await collection('rfid_v2_passages').update_one(
            {'_id': p['_id'], 'state': 'OPEN', f'events.{eid}': {'$exists': False},
             'event_count': {'$lt': 10000}, 'bytes': {'$lt': 8_000_000 - size}},
            {'$set': {f'events.{eid}': entry}, '$inc': {'event_count': 1, 'bytes': size}})
        duplicate = not result.modified_count
        if duplicate:
            current = await collection('rfid_v2_passages').find_one({'_id': p['_id']})
            if eid not in current['events']:
                fail(409, 'PASSAGE_FROZEN_OR_FULL', 'Passage sudah ditutup atau mencapai kapasitas; evidence tidak dihapus.')
        acks.append({'event_id': event['event_id'], 'status': 'quarantined' if reason else ('duplicate' if duplicate else 'accepted'),
                     'durable': True, 'processing_status': 'not_applicable' if reason else 'completed',
                     'error': {'code': reason, 'message': 'Observasi disimpan untuk pemeriksaan.', 'retryable': False} if reason else None})
    return {'request_id': str(uuid4()), 'batch_id': body['batch_id'], 'server_time': now(), 'event_acks': acks}


def valid_direction(cfg, g, body):
    evidence = body['direction_evidence']
    if evidence['profile_binding_id'] != cfg['hardware_profile_id']:
        return False
    if g['direction'] != 'bidirectional':
        return body['direction'] == g['direction'] and evidence['source'] == 'fixed_profile'
    sensors = g.get('sensor_bindings') or {}
    seq = evidence['sensor_sequence']
    if evidence['source'] != 'sensor_sequence' or len(seq) != 2:
        return False
    expected = [sensors.get('a'), sensors.get('b')]
    if body['direction'] == 'in':
        expected.reverse()
    if body['direction'] not in ('in', 'out') or [s['sensor_id'] for s in seq] != expected:
        return False
    dt = [(datetime.fromisoformat(s['captured_at'].replace('Z', '+00:00'))) for s in seq]
    return (0 < (dt[1] - dt[0]).total_seconds() * 1000 <= sensors.get('sequence_window_ms', 5000)
            and all(s['state'] == str(sensors.get('active_state', 1)) for s in seq))


async def latched(device_id, gate_id):
    row = await collection('rfid_v2_passages').find_one({'device_id': device_id, 'gate_id': gate_id,
        'decision.latched': True, 'acknowledged': False}, {'_id': 1})
    return row['_id'] if row else None


async def close(device, passage_id, body, key):
    validate('PassageClose', body)
    if not key or len(key) > 160:
        fail(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Close membutuhkan Idempotency-Key stabil.')
    cfg = await config(device, body['config_version'])
    g = gate(cfg, body['logical_gate_id'])
    p = await passage(device, cfg, g['logical_gate_id'], passage_id, body['mode'])
    fingerprint = digest(body)
    if p.get('close_hash') and (p['close_hash'] != fingerprint or p['close_key'] != key):
        fail(409, 'CLOSE_CONFLICT', 'Close yang sama harus mempertahankan key dan isi.')
    if p['decision']:
        return p['decision']
    if body['observed_event_count'] != p['event_count']:
        # Device retries after pending evidence. Do not freeze an incomplete transport.
        fail(503, 'EVIDENCE_PENDING', 'Jumlah evidence belum sesuai close; kirim ulang event yang belum ACK.')
    p = await collection('rfid_v2_passages').find_one_and_update(
        {'_id': p['_id'], 'state': 'OPEN', 'event_count': body['observed_event_count']},
        {'$set': {'state': 'CLOSING', 'close_hash': fingerprint, 'close_key': key, 'close_body': body}},
        return_document=ReturnDocument.AFTER) or await collection('rfid_v2_passages').find_one({'_id': p['_id']})
    if p.get('close_hash') != fingerprint or p.get('close_key') != key:
        fail(409, 'CLOSE_CONFLICT', 'Close bersamaan berbeda; pemeriksaan diperlukan.')
    if p['decision']:
        return p['decision']
    rows = list(p['events'].values())
    seen = {r['event']['epc'] for r in rows if r['event'].get('epc')}
    counts = {'observed_unique': len(seen), 'matched': 0, 'missing': 0, 'extra': 0,
              'unknown': sum(1 for r in rows if r['quarantine']), 'pending': 0}
    reason, verdict = 'MANIFEST_MATCH', 'GREEN'
    ref = None
    binding = p['binding']
    expected, matched, roll_sources = set(), set(), {}
    if not binding:
        reason, verdict = 'NO_MANIFEST', 'REVIEW'
    else:
        ref = binding['source_ref']
        expected = set(binding['roll_ids'])
        try:
            for entry in binding_sources(binding):
                _, current_ids = await manifest(entry['source_ref'], cfg['warehouse_id'], body['direction'])
                if set(current_ids) != set(entry['roll_ids']):
                    reason, verdict = 'MANIFEST_CHANGED', 'REVIEW'
            if binding['direction'] != body['direction']:
                reason, verdict = 'MANIFEST_CHANGED', 'REVIEW'
        except HTTPException:
            reason, verdict = 'SOURCE_NOT_ACTIVE', 'REVIEW'
        roll_sources = {rid: entry['source_ref'] for entry in binding_sources(binding) for rid in entry['roll_ids']}
        for epc in seen:
            tag = await db.rfid_tags.find_one({'epc': epc, 'status': 'active'})
            roll = await db.inventory_rolls.find_one({'id': tag['roll_id']}) if tag else None
            if not roll:
                counts['unknown'] += 1
                continue
            if roll['id'] not in expected:
                counts['extra'] += 1
                continue
            result = await gate_evaluator.evaluate(body['direction'], cfg['warehouse_id'], roll, crossing_passage_id=p['_id'], expected_source=roll_sources.get(roll['id']))
            if result['result'] != 'green':
                reason, verdict = result['code'], 'RED'
            matched.add(roll['id'])
        counts['matched'] = len(matched)
        counts['missing'] = len(expected - matched)
    if counts['extra'] or counts['unknown'] or counts['missing'] or not seen or len(matched) != len(seen):
        reason, verdict = 'MANIFEST_MISMATCH', 'RED'
    ids = {r['event']['event_id'] for r in rows}
    if not body['capture_complete'] or body['boundary_reason'] == 'max_duration' or body['last_event_id'] not in ids:
        reason, verdict = 'CAPTURE_INCOMPLETE', 'REVIEW'
    if not valid_direction(cfg, g, body):
        reason, verdict = 'DIRECTION_UNVERIFIED', 'REVIEW'
    if g['completion_basis'] != 'manifest_full':
        reason, verdict = 'FULL_MANIFEST_REQUIRED', 'REVIEW'
    prior_latch = await latched(device['id'], g['logical_gate_id'])
    if prior_latch:
        reason, verdict = 'GATE_LATCHED', 'REVIEW'
    if body['mode'] == 'backfill':
        reason, verdict = 'HISTORICAL_EVIDENCE', 'REVIEW'
    if body['config_version'] != device.get('v2_config_version'):
        reason, verdict = 'HISTORICAL_CONFIG', 'REVIEW'
    closing_at = datetime.fromisoformat(body['closing_captured_at'].replace('Z', '+00:00'))
    age = (datetime.now(timezone.utc) - closing_at).total_seconds()
    if age < -5 or age > 30 or any(r['event']['time_quality'] != 'synced' for r in rows):
        reason, verdict = 'TIME_UNVERIFIED', 'REVIEW'
    if binding:
        bound_at = datetime.fromisoformat(binding['bound_at'].replace('Z', '+00:00'))
        if any(datetime.fromisoformat(r['event']['captured_at'].replace('Z', '+00:00')) < bound_at for r in rows):
            reason, verdict = 'MANIFEST_BOUND_AFTER_CAPTURE', 'REVIEW'
    current_device = await db.rfid_devices.find_one({'id': device['id']})
    if (not current_device or current_device.get('enabled') is False or
            current_device.get('v2_config_version') != cfg['config_version'] or
            current_device.get('warehouse_id') != cfg['warehouse_id']):
        reason, verdict = 'DEVICE_CONFIG_CHANGED', 'REVIEW'
    if verdict == 'GREEN':
        # Durable crossing claims prevent a second passage granting the same roll
        # clearance on the same source and direction, including another reader.
        for rid in sorted(matched):
            roll_ref = roll_sources[rid]
            cid = digest([roll_ref['source_type'], roll_ref['source_id'], body['direction'], rid])
            try:
                await collection('rfid_v2_crossings').insert_one({'_id': cid, 'passage': p['_id'], 'roll_id': rid, 'at': now()})
            except DuplicateKeyError:
                existing = await collection('rfid_v2_crossings').find_one({'_id': cid})
                if existing['passage'] != p['_id']:
                    reason, verdict = 'REPLAY_CROSSING', 'RED'
    stamp = datetime.now(timezone.utc)
    decision = {'decision_id': str(uuid4()), 'local_passage_id': passage_id, 'logical_gate_id': g['logical_gate_id'],
        'mode': body['mode'], 'final': True, 'verdict': verdict, 'completion_basis': g['completion_basis'],
        'config_version': cfg['config_version'], 'created_at': stamp.isoformat().replace('+00:00', 'Z'),
        'expires_at': (stamp + timedelta(seconds=min(60, cfg['policies']['gate_decision_validity_seconds']))).isoformat().replace('+00:00', 'Z'),
        'allow_live_signal': verdict == 'GREEN' and body['mode'] == 'live', 'latched': verdict != 'GREEN',
        'reason_code': reason, 'action': 'Sesuai manifest.' if verdict == 'GREEN' else 'Tahan barang; periksa evidence dan dokumen di ERP.',
        'counts': counts, 'source_ref': ref}
    await collection('rfid_v2_passages').update_one({'_id': p['_id'], 'decision': None}, {'$set': {'decision': decision, 'state': 'FINAL'}})
    final = await collection('rfid_v2_passages').find_one({'_id': p['_id']})
    return final['decision']


async def gate_state(device, gate_id, passage_id=None):
    cfg = await config(device)
    gate(cfg, gate_id)
    latch = await latched(device['id'], gate_id)
    p = await collection('rfid_v2_passages').find_one({'_id': digest([device['id'], passage_id]), 'gate_id': gate_id}) if passage_id else None
    return {'request_id': str(uuid4()), 'logical_gate_id': gate_id, 'config_version': cfg['config_version'],
            'latched': bool(latch), 'latch_id': latch, 'decision': p.get('decision') if p else None, 'server_time': now()}


async def telemetry(device, body):
    validate('Telemetry', body)
    await collection('rfid_devices').update_one({'id': device['id'], 'enabled': {'$ne': False}}, {'$set': {
        'status': 'online', 'last_heartbeat': now(), 'v2_telemetry': body}})
    return {'request_id': str(uuid4()), 'server_time': now()}


async def acknowledge(device, passage_id, note, actor):
    if not isinstance(note, str) or len(note.strip()) < 5:
        fail(400, 'NOTE_REQUIRED', 'Catatan pemeriksaan minimal 5 karakter.')
    result = await collection('rfid_v2_passages').update_one(
        {'_id': digest([device['id'], passage_id]), 'state': 'FINAL', 'acknowledged': False},
        {'$set': {'acknowledged': True, 'ack_actor_id': actor['id'], 'ack_note': note.strip(), 'ack_at': now()}})
    if not result.matched_count:
        fail(409, 'NOT_ACKNOWLEDGEABLE', 'Passage belum final atau sudah ditindaklanjuti.')
    # Acknowledgement releases an alarm; it never changes a decision to GREEN.
    return {'request_id': str(uuid4()), 'server_time': now()}
