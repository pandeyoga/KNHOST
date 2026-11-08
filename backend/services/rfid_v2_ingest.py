"""Penerimaan bukti lintasan V2: event mentah (0.4), ringkasan TagSummary & tepi photo-eye GpiEdge (2.1).

AUD-MW-07: bukti disimpan di koleksi sendiri (`_id` unik per lintasan+item) dengan bulk write — bukan menumpuk di
satu dokumen lintasan. Kapasitas dipesan atomik di dokumen lintasan (berprasyarat OPEN + sisa kapasitas) SEBELUM
bulk insert; duplikat balapan dikompensasi. AUD-MW-01c: lintasan penuh → item disimpan durable di `rfid_v2_overflow`
dan di-ACK `quarantined` (CAPTURE_OVERFLOW) — keputusan REVIEW, bukan 409 permanen yang mengunci reader.
"""
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pymongo.errors import BulkWriteError

from services.epc import try_canonical
from services.rfid_v2_common import collection, compact_size, digest, fail, now
from services import rfid_v2_core as core

ACK_OVERFLOW = {'code': 'CAPTURE_OVERFLOW', 'message': 'Lintasan melewati kapasitas; bukti disimpan di luapan untuk diperiksa.',
                'retryable': False}


def _ack(item_id: str, status: str, reason: Optional[str] = None, key: str = 'event_id') -> Dict[str, Any]:
    error = None
    if status == 'quarantined':
        error = ACK_OVERFLOW if reason == 'CAPTURE_OVERFLOW' else {
            'code': reason, 'message': 'Observasi disimpan untuk pemeriksaan.', 'retryable': False}
    return {key: item_id, 'status': status, 'durable': True,
            'processing_status': 'not_applicable' if status == 'quarantined' else 'completed', 'error': error}


def _quarantine(raw_epc: Optional[str], epc: Optional[str], antenna: Optional[str], gate: Dict[str, Any]) -> Optional[str]:
    if not epc or try_canonical(raw_epc) != epc:
        return 'INVALID_EPC'
    if antenna not in gate['antenna_ids']:
        return 'ANTENNA_NOT_BOUND'
    return None


async def _store(p: Dict[str, Any], kind: str, items: List[Dict[str, Any]], capacity: int) -> Dict[str, str]:
    """Simpan item (dict berisi `key`, `fingerprint`, `doc`) → {key: status}. Status accepted|duplicate|quarantined."""
    if not items:
        return {}
    pid = p['_id']
    coll = collection(core.KIND_COLLECTION[kind])
    for it in items:
        it['_id'] = digest([pid, kind, it['key']])
    existing = {d['_id']: d for d in await coll.find({'_id': {'$in': [i['_id'] for i in items]}},
                                                     {'fingerprint': 1}).to_list(len(items))}
    ov_ids = {digest([pid, 'overflow', kind, it['key']]): it for it in items if it['_id'] not in existing}
    in_overflow = {d['_id'] for d in await collection('rfid_v2_overflow').find(
        {'_id': {'$in': list(ov_ids)}}, {'_id': 1}).to_list(len(ov_ids) + 1)} if ov_ids else set()
    out: Dict[str, str] = {ov_ids[i]['key']: 'quarantined' for i in in_overflow}   # ulang item luapan: tetap luapan
    fresh = []
    for it in items:
        old = existing.get(it['_id'])
        if it['key'] in out:
            continue
        if old:
            if old['fingerprint'] != it['fingerprint']:
                fail(409, 'EVENT_ID_CONFLICT', 'ID bukti dipakai ulang dengan isi berbeda.')
            out[it['key']] = 'duplicate'
        else:
            fresh.append(it)
    if not fresh:
        return out
    size = sum(compact_size(it['doc']) for it in fresh)
    counter = f'{kind}_count'
    reserved = await collection('rfid_v2_passages').update_one(
        {'_id': pid, 'state': 'OPEN', counter: {'$lte': capacity - len(fresh)}, 'bytes': {'$lte': core.MAX_PASSAGE_BYTES - size}},
        {'$inc': {counter: len(fresh), 'bytes': size}})
    if reserved.matched_count:
        docs = [{'_id': it['_id'], 'passage': pid, 'kind': kind, 'key': it['key'], 'fingerprint': it['fingerprint'],
                 'received_at': now(), **it['doc']} for it in fresh]
        dups = set()
        try:
            await coll.insert_many(docs, ordered=False)
        except BulkWriteError as bwe:
            errors = bwe.details.get('writeErrors', [])
            if any(e.get('code') != 11000 for e in errors):
                raise
            dups = {docs[e['index']]['key'] for e in errors}
            lost = sum(compact_size(it['doc']) for it in fresh if it['key'] in dups)
            await collection('rfid_v2_passages').update_one({'_id': pid}, {'$inc': {counter: -len(dups), 'bytes': -lost}})
        for it in fresh:
            out[it['key']] = 'duplicate' if it['key'] in dups else 'accepted'
        return out
    current = await collection('rfid_v2_passages').find_one({'_id': pid}, {'state': 1})
    if current['state'] != 'OPEN':
        fail(409, 'PASSAGE_FROZEN', 'Passage sudah ditutup; bukti baru tidak diterima (bukti lama tidak dihapus).')
    ov = collection('rfid_v2_overflow')
    docs = [{'_id': digest([pid, 'overflow', kind, it['key']]), 'passage': pid, 'kind': kind, 'key': it['key'],
             'fingerprint': it['fingerprint'], 'received_at': now(), **it['doc']} for it in fresh]
    inserted = len(docs)
    try:
        await ov.insert_many(docs, ordered=False)
    except BulkWriteError as bwe:
        errors = bwe.details.get('writeErrors', [])
        if any(e.get('code') != 11000 for e in errors):
            raise
        inserted -= len(errors)
    if inserted:
        await collection('rfid_v2_passages').update_one({'_id': pid}, {'$inc': {f'overflow.{kind}': inserted}})
    for it in fresh:
        out[it['key']] = 'quarantined'
    return out


async def _claim_event_ids(device: Dict[str, Any], pid: str, events: List[Dict[str, Any]], fps: List[str]) -> None:
    """Identitas event global per perangkat (cegah replay ke lintasan lain). Semua dicek sebelum ada yang disimpan."""
    claims = [{'_id': digest([device['id'], e['event_id']]), 'passage': pid, 'fingerprint': fp} for e, fp in zip(events, fps)]
    coll = collection('rfid_v2_event_ids')
    try:
        await coll.insert_many(claims, ordered=False)
    except BulkWriteError as bwe:
        errors = bwe.details.get('writeErrors', [])
        if any(e.get('code') != 11000 for e in errors):
            raise
        ids = [claims[e['index']]['_id'] for e in errors]
        want = {c['_id']: c for c in claims}
        for old in await coll.find({'_id': {'$in': ids}}).to_list(len(ids)):
            if old['passage'] != pid or old['fingerprint'] != want[old['_id']]['fingerprint']:
                fail(409, 'EVENT_ID_CONFLICT', 'Event ID digunakan ulang dengan payload atau passage berbeda.')


async def _track_seq(device: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    """Nomor urut envelope per boot (deteksi celah, Sparkplug-style). Tidak pernah menolak envelope."""
    boot, seq = body.get('boot_id'), body.get('seq')
    if not boot or seq is None:
        return {}
    row = await collection('rfid_devices').find_one({'id': device['id']}, {'_id': 0, 'v2_transport': 1}) or {}
    tr = row.get('v2_transport') or {}
    gap = tr.get('boot_id') == boot and tr.get('last_seq') is not None and seq > tr['last_seq'] + 1
    if tr.get('boot_id') != boot:
        await collection('rfid_devices').update_one({'id': device['id']}, {'$set': {
            'v2_transport': {'boot_id': boot, 'last_seq': seq, 'gaps': 0, 'since': now()}}})
        return {'last_seq': seq, 'seq_gap': False}
    upd: Dict[str, Any] = {'$max': {'v2_transport.last_seq': seq}}
    if gap:
        upd['$inc'] = {'v2_transport.gaps': 1}
    await collection('rfid_devices').update_one({'id': device['id']}, upd)
    return {'last_seq': max(seq, tr.get('last_seq') or 0), 'seq_gap': bool(gap)}


async def events(device: Dict[str, Any], body: Dict[str, Any], *, simulated: bool = False,
                 capacity_override: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    core.validate('EventsRequest', body)
    ctx = body['context']
    if ctx['kind'] != 'gate' or not ctx.get('logical_gate_id') or not ctx.get('local_passage_id') or ctx.get('task_context_id'):
        fail(400, 'GATE_CONTEXT_REQUIRED', 'Endpoint reader ini membutuhkan konteks gate dan passage.')
    cfg = await core.config(device, body['config_version'])
    evs, sums, edges = body.get('events') or [], body.get('tag_summaries') or [], body.get('gpi_edges') or []
    if len(evs) > min(500, cfg['limits']['max_events']) or len(sums) > 500 or len(edges) > 200 \
            or compact_size(body) > cfg['limits']['max_body_bytes']:
        fail(413, 'BATCH_TOO_LARGE', 'Pecah batch; tidak ada item batch ini yang diproses.')
    g = core.gate(cfg, ctx['logical_gate_id'])
    p = await core.passage(device, cfg, ctx['logical_gate_id'], ctx['local_passage_id'], body['mode'], simulated=simulated)
    cap = {**core.CAPACITY, **(capacity_override or {})}
    seq = await _track_seq(device, body)
    fps = [digest(e) for e in evs]
    if evs:
        await _claim_event_ids(device, p['_id'], evs, fps)
    ev_items, ev_reason = [], {}
    for e, fp in zip(evs, fps):
        reason = _quarantine(e.get('raw_epc'), e.get('epc'), e.get('antenna'), g)
        ev_reason[e['event_id']] = reason
        ev_items.append({'key': e['event_id'], 'fingerprint': fp, 'doc': {'event': e, 'quarantine': reason}})
    sum_items, sum_reason = [], {}
    for s in sums:
        reason = _quarantine(s.get('raw_epc'), s.get('epc'), s.get('antenna'), g)
        sum_reason[s['summary_id']] = reason
        sum_items.append({'key': s['summary_id'], 'fingerprint': digest(s), 'doc': {'summary': s, 'quarantine': reason}})
    edge_items = [{'key': x['edge_id'], 'fingerprint': digest(x), 'doc': {'edge': x}} for x in edges]
    st_ev = await _store(p, 'event', ev_items, cap['event'])
    st_sum = await _store(p, 'summary', sum_items, cap['summary'])
    st_edge = await _store(p, 'edge', edge_items, cap['edge'])

    def ack_of(key, status, reason, field):
        if status == 'quarantined':
            return _ack(key, 'quarantined', 'CAPTURE_OVERFLOW', field)
        if reason:
            return _ack(key, 'quarantined', reason, field)
        return _ack(key, status, None, field)

    out = {'request_id': str(uuid4()), 'batch_id': body['batch_id'], 'server_time': now(),
           'event_acks': [ack_of(e['event_id'], st_ev[e['event_id']], ev_reason[e['event_id']], 'event_id') for e in evs]}
    if sums:
        out['summary_acks'] = [ack_of(s['summary_id'], st_sum[s['summary_id']], sum_reason[s['summary_id']], 'item_id') for s in sums]
    if edges:
        out['edge_acks'] = [ack_of(x['edge_id'], st_edge[x['edge_id']], None, 'item_id') for x in edges]
    out.update(seq)
    return out
