"""Protokol gate U300 V2 (Kubus V2 + PREP-D1). Pengamatan tidak pernah mengubah stok atau akuntansi.

Fasad modul: transport/bukti (`rfid_v2_core`, `rfid_v2_ingest`), sumber dokumen (`rfid_v2_sources`), kebijakan
keputusan K-RFID-09/10 (`rfid_v2_policy`), sesi dokumen & klaim crossing (`rfid_v2_sessions`), satu kunci per gate
(`rfid_v2_latch`), parameter gate berversi (`rfid_v2_params`), kesehatan reader (`rfid_v2_health`).
"""
import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import HTTPException
from pymongo import ReturnDocument

from db import db
from services import gate_evaluator  # noqa: F401 — dipakai router (SHIPMENT_ACTIVE) & tes
from services import rfid_v2_latch as latch
from services import rfid_v2_params as params_mod
from services import rfid_v2_policy as policy
from services import rfid_v2_sessions as sessions
from services import rfid_v2_sources as sources
from services.rfid_v2_common import collection, digest, fail, now, parse_ts  # noqa: F401 — API publik modul
from services.rfid_v2_core import (CONTRACT, CONTRACT_VERSION, binding_sources, config, ensure_indexes, gate,  # noqa: F401
                                   gate_params, load_evidence, passage, publish_config, set_protocol, validate)
from services.rfid_v2_ingest import events  # noqa: F401

logger = logging.getLogger(__name__)
manifest = sources.manifest
validate_sources = sources.validate_sources
COMPLETION_OK = ('manifest_full', 'manifest_subset', 'document_session')


async def bind_manifest(device, gate_id, source, direction, actor):
    return await bind_manifests(device, gate_id, [source], direction, actor)


async def bind_manifests(device, gate_id, selected, direction, actor):
    validate_sources(selected)
    cfg = await config(device)
    g = gate(cfg, gate_id)
    if direction not in ('in', 'out') or g['direction'] not in (direction, 'bidirectional'):
        fail(400, 'DIRECTION_MISMATCH', 'Arah dokumen berbeda dengan gate.')
    entries, all_ids = [], set()
    for source in selected:
        ref, ids = await manifest(source, cfg['warehouse_id'], direction)
        if all_ids.intersection(ids):
            fail(409, 'DUPLICATE_MANIFEST_ROLL', 'Roll tercantum pada lebih dari satu dokumen. Koreksi dokumen sebelum memuat.')
        all_ids.update(ids)
        entries.append({'source_ref': ref, 'roll_ids': ids})
    if len(all_ids) > sources.MAX_ROLLS:
        fail(409, 'MANIFEST_CAPACITY', 'Gabungan manifest maksimal 2000 roll per lintasan.')
    ref = entries[0]['source_ref'] if len(entries) == 1 else {
        'source_type': 'gate_manifest', 'source_id': str(uuid4()),
        'display_ref': ' + '.join(e['source_ref']['display_ref'] for e in entries)}
    binding = {'_id': digest([device['id'], gate_id]), 'device_id': device['id'], 'gate_id': gate_id,
               'source_ref': ref, 'sources': entries, 'roll_ids': sorted(all_ids), 'direction': direction,
               'bound_at': now(), 'actor_id': actor['id'], 'released_at': None}
    await collection('rfid_v2_bindings').replace_one({'_id': binding['_id']}, binding, upsert=True)
    return {k: v for k, v in binding.items() if k != '_id'}


async def release_binding(device, gate_id, actor):
    """Lepas binding manual → lintasan berikutnya memakai auto-cocok (bila aktif di parameter gate)."""
    res = await collection('rfid_v2_bindings').update_one(
        {'_id': digest([device['id'], gate_id]), 'released_at': None},
        {'$set': {'released_at': now(), 'released_by': actor.get('id')}})
    return {'released': bool(res.modified_count)}


async def history(device_id, cursor=None, limit=50):
    if not 1 <= limit <= 100:
        fail(400, 'PAGE_LIMIT', 'Ukuran halaman wajib 1 sampai 100.')
    query: Dict[str, Any] = {'device_id': device_id}
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
    next_cursor = base64.urlsafe_b64encode(json.dumps([page[-1]['created_at'], page[-1]['_id']]).encode()).decode() \
        if len(rows) > limit else None
    for row in page:
        row.pop('_id', None)
        if row.get('binding'):
            row['binding'].pop('_id', None)
    return page, next_cursor


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
    dt = [parse_ts(s['captured_at']) for s in seq]
    return (0 < (dt[1] - dt[0]).total_seconds() * 1000 <= sensors.get('sequence_window_ms', 5000)
            and all(s['state'] == str(sensors.get('active_state', 1)) for s in seq))


async def latched(device_id, gate_id):
    row = await latch.active(device_id, gate_id)
    return row['latch_id'] if row else None


async def _binding_context(p, cfg, body):
    """Binding manual snapshot lintasan → (entries | None, alasan konteks dokumen)."""
    binding = p.get('binding')
    if not binding:
        return None, []
    reasons, entries = [], binding_sources(binding)
    for entry in entries:
        try:
            _, current_ids = await manifest(entry['source_ref'], cfg['warehouse_id'], body['direction'])
            if set(current_ids) != set(entry['roll_ids']):
                reasons.append(('MANIFEST_CHANGED', policy.REVIEW, f"Isi {entry['source_ref'].get('display_ref')} berubah sejak dipilih."))
        except HTTPException:
            if await sources.is_cancelled(entry['source_ref']):
                reasons.append(('DOC_CANCELLED', policy.RED, f"{entry['source_ref'].get('display_ref')} sudah DIBATALKAN."))
            else:
                reasons.append(('SOURCE_NOT_ACTIVE', policy.REVIEW, f"{entry['source_ref'].get('display_ref')} tidak aktif lagi untuk gate ini."))
    if binding['direction'] != body['direction']:
        reasons.append(('MANIFEST_CHANGED', policy.REVIEW, 'Arah binding berbeda dengan arah lintasan.'))
    return entries, reasons


async def _transport_reasons(device, cfg, g, p, body, ev):
    out = []
    rv = policy.REVIEW
    rows = [r['event'] for r in ev['event']] + [r['summary'] for r in ev['summary']]
    ids = {r['event']['event_id'] for r in ev['event']}
    if not body['capture_complete'] or (ids and body['last_event_id'] not in ids):
        out.append(('CAPTURE_INCOMPLETE', rv, 'Agent melaporkan bukti lintasan tidak lengkap.'))
    if sum((p.get('overflow') or {}).values()):
        out.append(('CAPTURE_OVERFLOW', rv, 'Lintasan melewati kapasitas bukti — sebagian bukti di koleksi luapan.'))
    if ev['summary'] and body.get('observed_summary_count') is None:
        out.append(('SUMMARY_COUNT_MISSING', rv, 'Close tidak menyebut jumlah ringkasan; kelengkapan tidak terverifikasi.'))
    if not valid_direction(cfg, g, body):
        out.append(('DIRECTION_UNVERIFIED', rv, 'Bukti arah tidak sesuai profil gate.'))
    if g['completion_basis'] not in COMPLETION_OK:
        out.append(('COMPLETION_BASIS_UNSUPPORTED', rv, 'Basis penilaian gate tidak didukung sesi dokumen.'))
    if body['mode'] == 'backfill':
        out.append(('HISTORICAL_EVIDENCE', rv, 'Bukti historis (offline) — tidak pernah memberi sinyal hijau hidup.'))
    if body['config_version'] != device.get('v2_config_version'):
        out.append(('HISTORICAL_CONFIG', rv, 'Lintasan memakai versi profil lama.'))
    age = (datetime.now(timezone.utc) - parse_ts(body['closing_captured_at'])).total_seconds()
    if age < -5 or age > 30 or any(r.get('time_quality') != 'synced' for r in rows):
        out.append(('TIME_UNVERIFIED', rv, 'Waktu reader tidak tervalidasi (tidak sinkron / close terlambat).'))
    binding = p.get('binding')
    if binding:
        bound_at = parse_ts(binding['bound_at'])
        first = [parse_ts(r['event']['captured_at']) for r in ev['event']] + \
                [parse_ts(r['summary']['first_seen']) for r in ev['summary']]
        if any(t and t < bound_at for t in first):
            out.append(('MANIFEST_BOUND_AFTER_CAPTURE', rv, 'Dokumen dipilih setelah bacaan lintasan dimulai.'))
    current = await db.rfid_devices.find_one({'id': device['id']}, {'_id': 0, 'enabled': 1, 'v2_config_version': 1, 'warehouse_id': 1})
    if (not current or current.get('enabled') is False or current.get('v2_config_version') != cfg['config_version']
            or current.get('warehouse_id') != cfg['warehouse_id']):
        out.append(('DEVICE_CONFIG_CHANGED', rv, 'Status/profil perangkat berubah selama lintasan.'))
    return out


def _counts_match(p, body):
    ov = p.get('overflow') or {}
    if body['observed_event_count'] != p.get('event_count', 0) + ov.get('event', 0):
        return False
    for kind, field in (('summary', 'observed_summary_count'), ('edge', 'observed_edge_count')):
        if body.get(field) is not None and body[field] != p.get(f'{kind}_count', 0) + ov.get(kind, 0):
            return False
    return True


async def close(device, passage_id, body, key, *, simulated: bool = False):
    validate('PassageClose', body)
    if not key or len(key) > 160:
        fail(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Close membutuhkan Idempotency-Key stabil.')
    cfg = await config(device, body['config_version'])
    g = gate(cfg, body['logical_gate_id'])
    p = await passage(device, cfg, g['logical_gate_id'], passage_id, body['mode'], simulated=simulated)
    fingerprint = digest(body)
    if p.get('close_hash') and (p['close_hash'] != fingerprint or p['close_key'] != key):
        fail(409, 'CLOSE_CONFLICT', 'Close yang sama harus mempertahankan key dan isi.')
    if p['decision']:
        return p['decision']
    if p['state'] == 'OPEN':
        if not _counts_match(p, body):   # bukti belum lengkap: jangan bekukan transport yang belum selesai
            fail(503, 'EVIDENCE_PENDING', 'Jumlah evidence belum sesuai close; kirim ulang event yang belum ACK.')
        snap = {k: p.get(k, 0) for k in ('event_count', 'summary_count', 'edge_count')}
        frozen = await collection('rfid_v2_passages').find_one_and_update(
            {'_id': p['_id'], 'state': 'OPEN', **snap, 'overflow': p.get('overflow')},
            {'$set': {'state': 'CLOSING', 'close_hash': fingerprint, 'close_key': key, 'close_body': body}},
            projection={'events': 0}, return_document=ReturnDocument.AFTER)
        p = frozen or await collection('rfid_v2_passages').find_one({'_id': p['_id']}, {'events': 0})
        if p['state'] == 'OPEN':
            fail(503, 'EVIDENCE_PENDING', 'Bukti berubah bersamaan; ulangi close.')
    if p.get('close_hash') != fingerprint or p.get('close_key') != key:
        fail(409, 'CLOSE_CONFLICT', 'Close bersamaan berbeda; pemeriksaan diperlukan.')
    if p['decision']:
        return p['decision']
    ev = await load_evidence(p['_id'])
    if len(ev['event']) != p.get('event_count', 0) or len(ev['summary']) != p.get('summary_count', 0):
        fail(503, 'EVIDENCE_PENDING', 'Bukti tersimpan belum lengkap; ulangi close.')
    params = gate_params(g)
    binding_entries, binding_reasons = await _binding_context(p, cfg, body)
    result = await policy.decide(
        body=body, gate=g, params=params, pid=p['_id'], warehouse=cfg['warehouse_id'], events=ev['event'],
        summaries=ev['summary'], binding_entries=binding_entries, binding_reasons=binding_reasons,
        transport_reasons=await _transport_reasons(device, cfg, g, p, body, ev),
        overflow=sum((p.get('overflow') or {}).values()))
    direction = result['direction']
    if result['claimable']:
        meta = {'device_id': device['id'], 'gate_id': g['logical_gate_id'], 'local_passage_id': passage_id,
                'review': result['verdict'] == 'REVIEW', 'simulated': bool(p.get('simulated'))}
        ok, conflicts = await sessions.insert_claims(p['_id'], direction, result['matched'], meta)
        if not ok:
            for rid in conflicts:
                result['reasons'].add(policy.RED, 'REPLAY_CROSSING', 'Roll sudah lewat pada lintasan lain untuk dokumen & arah ini.', roll_id=rid)
            result['verdict'], result['claimable'] = 'RED', False
            result['counts']['already_passed'] += len(conflicts)
    counts = result['counts']
    entries = result['entries']
    if entries and direction:
        counts['pending'] = await sessions.remaining_after(entries, direction)
    fields = policy.finalize(result)
    stamp = datetime.now(timezone.utc)
    decision_id = str(uuid4())
    verdict = result['verdict']
    latch_id = None
    if verdict == 'RED':
        latch_id = await latch.add_passage(device['id'], g['logical_gate_id'], p['_id'], passage_id, decision_id,
                                           fields['reason_codes'])
    refs = [e['source_ref'] for e in entries]
    source_ref = refs[0] if len(refs) == 1 else ({'source_type': 'gate_manifest', 'source_id': digest(refs)[:32],
                                                 'display_ref': ' + '.join(r.get('display_ref', '') for r in refs)} if refs else None)
    decision = {
        'decision_id': decision_id, 'local_passage_id': passage_id, 'logical_gate_id': g['logical_gate_id'],
        'mode': body['mode'], 'final': True, 'verdict': verdict, 'completion_basis': g['completion_basis'],
        'config_version': cfg['config_version'], 'created_at': stamp.isoformat().replace('+00:00', 'Z'),
        'expires_at': (stamp + timedelta(seconds=min(60, cfg['policies']['gate_decision_validity_seconds']))).isoformat().replace('+00:00', 'Z'),
        'allow_live_signal': verdict == 'GREEN' and body['mode'] == 'live', **fields,
        'counts': {k: counts[k] for k in ('observed_unique', 'matched', 'missing', 'extra', 'unknown', 'pending',
                                          'weak', 'background', 'overflow', 'already_passed')},
        'source_ref': source_ref, 'sources': refs, 'binding_mode': result['binding_mode'],
        'open_reason': body.get('open_reason'), 'close_reason': body.get('close_reason'), 'latch_id': latch_id,
        'simulated': bool(p.get('simulated'))}
    if entries and direction:
        by_source: Dict[str, int] = {}
        for _, ref in result['matched']:
            by_source[ref['source_id']] = by_source.get(ref['source_id'], 0) + 1
        await sessions.record_passage(entries, direction, cfg['warehouse_id'], p['_id'], passage_id, verdict, by_source)
    await collection('rfid_v2_passages').update_one({'_id': p['_id'], 'decision': None}, {'$set': {
        'decision': decision, 'state': 'FINAL', 'weak_epcs': result['weak'], 'background_epcs': result['background']}})
    final = await collection('rfid_v2_passages').find_one({'_id': p['_id']}, {'decision': 1})
    return final['decision']


async def gate_state(device, gate_id, passage_id=None):
    cfg = await config(device)
    gate(cfg, gate_id)
    row = await latch.active(device['id'], gate_id)
    p = await collection('rfid_v2_passages').find_one(
        {'_id': digest([device['id'], passage_id]), 'gate_id': gate_id}, {'decision': 1}) if passage_id else None
    return {'request_id': str(uuid4()), 'logical_gate_id': gate_id, 'config_version': cfg['config_version'],
            'latched': bool(row), 'latch_id': row['latch_id'] if row else None,
            'latch_since': row.get('since') if row else None,
            'latch_reason_codes': (row or {}).get('reason_codes') or [],
            'latch_passage_count': len((row or {}).get('passages') or []),
            'decision': p.get('decision') if p else None, 'server_time': now()}


async def telemetry(device, body):
    validate('Telemetry', body)
    await collection('rfid_devices').update_one({'id': device['id'], 'enabled': {'$ne': False}}, {'$set': {
        'status': 'online', 'last_heartbeat': now(), 'v2_telemetry': body, 'v2_telemetry_at': now()}})
    from services import rfid_v2_health as health
    try:   # telemetry sudah durable; kegagalan aturan kesehatan tidak boleh menggagalkan ACK telemetry
        await health.check_device({**device, 'v2_telemetry': body, 'v2_telemetry_at': now()})
    except Exception as exc:  # noqa: BLE001
        logger.warning('[rfid_v2.telemetry] cek kesehatan gagal diabaikan: %s', exc)
    return {'request_id': str(uuid4()), 'server_time': now()}


async def acknowledge(device, passage_id, note, actor, latch_id=None, decision_id=None):
    return await latch.acknowledge_passage(device, passage_id, note, actor, latch_id, decision_id)


async def publish_gate_parameters(device, gate_id, new_version, parameters, actor):
    """Profil berversi baru dengan parameter lintasan gate (bukan konstanta kode)."""
    problem = params_mod.validate(parameters)
    if problem:
        fail(400, 'INVALID_GATE_PARAMETERS', problem)
    cfg = await config(device)
    gate(cfg, gate_id)
    if not isinstance(new_version, str) or not 1 <= len(new_version) <= 160 or new_version == cfg['config_version']:
        fail(400, 'NEW_VERSION_REQUIRED', 'Isi versi profil baru (berbeda dari versi aktif).')
    return await publish_config(device, params_mod.derive_config(cfg, gate_id, new_version, parameters), actor)


async def evidence_document(device, passage_id) -> Dict[str, Any]:
    row = await collection('rfid_v2_passages').find_one({'_id': digest([device['id'], passage_id])})
    if not row:
        fail(404, 'PASSAGE_NOT_FOUND', 'Lintasan tidak ditemukan pada perangkat ini.')
    ev = await load_evidence(row['_id'])
    row.pop('_id')
    for k in ('close_key', 'close_hash', 'events'):
        row.pop(k, None)
    if row.get('binding'):
        row['binding'].pop('_id', None)
    strip = ('passage', 'fingerprint')
    row['events'] = [{k: v for k, v in e.items() if k not in strip} for e in ev['event']]
    row['tag_summaries'] = [{k: v for k, v in e.items() if k not in strip} for e in ev['summary']]
    row['gpi_edges'] = [{k: v for k, v in e.items() if k not in strip} for e in ev['edge']]
    row['overflow_items'] = [{k: v for k, v in e.items() if k not in strip} for e in ev['overflow']]
    return {'schema_version': 2, 'contract_version': CONTRACT_VERSION, 'exported_at': now(),
            'read_only_snapshot': True, 'passage': row}


async def device_sessions(device, cfg) -> List[Dict[str, Any]]:
    """Sesi dokumen yang terikat manual ke gate + sesi terbuka terbaru di gudang reader (maks 20)."""
    out, seen = [], set()
    g = cfg['logical_gates'][0]
    binding = await collection('rfid_v2_bindings').find_one({'_id': digest([device['id'], g['logical_gate_id']])})
    direction = g['direction'] if g['direction'] in ('in', 'out') else (binding or {}).get('direction', 'out')
    refs = [e['source_ref'] for e in binding_sources(binding)] if binding and not binding.get('released_at') else []
    recent = await collection('rfid_v2_doc_sessions').find(
        {'warehouse_id': cfg['warehouse_id'], 'direction': direction, 'status': 'open'},
        {'_id': 0, 'source_ref': 1}).sort('updated_at', -1).to_list(20)
    refs += [r['source_ref'] for r in recent]
    for ref in refs:
        key = (ref['source_type'], ref['source_id'])
        if key in seen or ref['source_type'] == 'gate_manifest':
            continue
        seen.add(key)
        try:
            out.append(await sessions.status(ref, direction, cfg['warehouse_id']))
        except HTTPException:
            continue
    return out[:20]
