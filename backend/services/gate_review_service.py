"""PREP-D2 — antrean periksa admin gudang untuk gate V2 (AUD-MW-10, K-RFID-09/10, K-GDG-02).

Satu KASUS per lintasan kuning/merah (`kind=passage`) atau per sesi dokumen yang ditutup dengan roll kurang
(`kind=rolls_missing`), koleksi `rfid_v2_reviews`. Isi kasus: alasan tingkat lintasan + daftar roll dengan BUKTI
(antena, RSSI puncak, waktu pertama/terakhir terbaca, dokumen, alasan) dan status per roll:
  open → (accepting) → accepted | rejected | ignored | done_elsewhere ; open ⇄ rescan ; recorded = sudah tercatat gate.
Tindakan (`wms.approve`, beraudit, idempoten — tiap ubahan kasus CAS `rev`):
  * terima roll sebagai lewat/tiba → transaksi lewat JALUR YANG SAMA dengan gate (`gate_review_actions`);
  * tolak (klaim lintasan ini dilepas) / abaikan — alasan wajib;
  * minta pindai ulang handheld (notifikasi petugas gudang; selesai otomatis bila handheld melengkapinya);
  * akui kunci gate (satu kunci per gate, K-RFID-09) · tutup kasus · ulangi transaksi yang gagal.
Kasus selesai otomatis bila semua roll tuntas & kunci tidak aktif; kasus tanpa roll yang bisa ditindak (mis. waktu
reader tidak tervalidasi) wajib ditutup admin dengan catatan.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from services.notification_service import create_notification
from services.rfid_v2_common import collection, digest, fail, now

REVIEWS = 'rfid_v2_reviews'
OPEN_STATES = ('open', 'rescan')
LIVE_STATES = OPEN_STATES + ('accepting',)
_RANK = {'RED': 3, 'REVIEW': 2, 'INFO': 1}
MAX_ROLLS = 2000


def passage_case_id(pid: str) -> str:
    return digest(['review', 'passage', pid])


def missing_case_id(ref: Dict[str, Any], direction: str) -> str:
    return digest(['review', 'missing', ref['source_type'], ref['source_id'], direction])


async def evidence_by_epc(pid: str) -> Dict[str, Dict[str, Any]]:
    """Bukti per EPC dari ringkasan (2.1) & event mentah (0.4): antena, RSSI puncak, jumlah, waktu."""
    out: Dict[str, Dict[str, Any]] = {}

    def slot(epc):
        return out.setdefault(epc, {'antennas': {}, 'peak_rssi': None, 'first_seen': None, 'last_seen': None, 'count': 0})

    def add(epc, antenna, rssi, first, last, count):
        x = slot(epc)
        a = x['antennas'].setdefault(str(antenna or '?'), {'antenna': str(antenna or '?'), 'peak_rssi': None, 'count': 0})
        if rssi is not None:
            a['peak_rssi'] = rssi if a['peak_rssi'] is None else max(a['peak_rssi'], rssi)
            x['peak_rssi'] = rssi if x['peak_rssi'] is None else max(x['peak_rssi'], rssi)
        a['count'] += count
        x['count'] += count
        x['first_seen'] = min(filter(None, [x['first_seen'], first]), default=None)
        x['last_seen'] = max(filter(None, [x['last_seen'], last]), default=None)

    for row in await collection('rfid_v2_summaries').find({'passage': pid}, {'_id': 0, 'summary': 1}).to_list(10000):
        s = row.get('summary') or {}
        if s.get('epc'):
            add(s['epc'], s.get('antenna'), s.get('peak_rssi'), s.get('first_seen'), s.get('last_seen'), int(s.get('count') or 0))
    for row in await collection('rfid_v2_events').find({'passage': pid}, {'_id': 0, 'event': 1}).to_list(10000):
        e = row.get('event') or {}
        if e.get('epc'):
            add(e['epc'], e.get('antenna'), e.get('rssi_dbm'), e.get('captured_at'), e.get('captured_at'), 1)
    for x in out.values():
        x['antennas'] = sorted(x['antennas'].values(), key=lambda a: a['antenna'])
    return out


async def _roll_info(roll_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    ids = [r for r in roll_ids if r][:MAX_ROLLS]
    rolls = {r['id']: r for r in await db.inventory_rolls.find({'id': {'$in': ids}}, {'_id': 0, 'id': 1, 'roll_no': 1}).to_list(len(ids) + 1)}
    tags = {t['roll_id']: t['epc'] for t in await db.rfid_tags.find({'roll_id': {'$in': ids}, 'status': 'active'},
                                                                   {'_id': 0, 'roll_id': 1, 'epc': 1}).to_list(len(ids) + 1)}
    return {rid: {'roll_no': (rolls.get(rid) or {}).get('roll_no'), 'epc': tags.get(rid)} for rid in ids}


def _item(key, roll_id, epc, source_ref, state='open'):
    return {'key': key, 'roll_id': roll_id, 'roll_no': None, 'epc': epc, 'source_ref': source_ref, 'codes': [],
            'level': 'INFO', 'messages': [], 'state': state, 'evidence': None, 'actions': []}


def _note(item, code, level, message):
    if code not in item['codes']:
        item['codes'].append(code)
    if message and message not in item['messages']:
        item['messages'].append(message[:300])
    if _RANK.get(level, 0) > _RANK.get(item['level'], 0):
        item['level'] = level


async def build_passage_items(row: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    dec, inp = row['decision'], row.get('gate_txn_input') or {}
    refs = {s['source_ref']['source_id']: s['source_ref'] for s in inp.get('sources') or []}
    refs.update({r['source_id']: r for r in dec.get('sources') or []})
    items: Dict[str, Dict[str, Any]] = {}
    passage_reasons = []
    for r in dec.get('reasons') or []:
        if r.get('level') == 'INFO':
            continue
        if not (r.get('roll_id') or r.get('epc')):
            passage_reasons.append({'code': r['code'], 'level': r['level'], 'message': r.get('message', '')})
            continue
        key = r.get('roll_id') or f"epc:{r['epc']}"
        it = items.setdefault(key, _item(key, r.get('roll_id'), r.get('epc'), refs.get(r.get('source_id'))))
        _note(it, r['code'], r['level'], r.get('message', ''))
    by_roll_src = {rid: s['source_ref'] for s in inp.get('sources') or [] for rid in s['roll_ids']}
    res_by_src = {r['source_ref']['source_id']: r for r in results}
    for rid, ref in by_roll_src.items():
        res = res_by_src.get(ref['source_id']) or {}
        probs = {p['roll_id']: p for p in res.get('problems') or []}
        it = items.get(rid)
        if rid in probs:
            it = it or items.setdefault(rid, _item(rid, rid, None, ref))
            it['source_ref'] = it['source_ref'] or ref
            _note(it, probs[rid]['code'], 'REVIEW', probs[rid].get('message', ''))
        elif res.get('state') in ('done', 'evidence'):
            if not it:
                items[rid] = {**_item(rid, rid, None, ref, 'recorded'), 'codes': ['RECORDED']}
        elif not it:
            it = items.setdefault(rid, _item(rid, rid, None, ref))
            _note(it, 'NOT_RECORDED', 'REVIEW', 'Roll cocok dokumen tetapi belum dicatat — lintasan perlu diperiksa.')
    ev = await evidence_by_epc(row['_id'])
    info = await _roll_info([i['roll_id'] for i in items.values() if i['roll_id']])
    for it in items.values():
        meta = info.get(it['roll_id']) or {}
        it['roll_no'] = meta.get('roll_no')
        it['epc'] = it['epc'] or meta.get('epc')
        it['evidence'] = ev.get(it['epc']) if it['epc'] else None
    return {'items': list(items.values())[:MAX_ROLLS], 'passage_reasons': passage_reasons[:50], 'refs': list(refs.values())}


async def sync_passage(device: Dict[str, Any], row: Dict[str, Any], results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Buat/perbarui kasus antrean untuk satu lintasan final. Idempoten (kasus ber-id lintasan)."""
    dec = row['decision']
    if dec['verdict'] == 'CANCELLED':
        return None
    built = await build_passage_items(row, results)
    actionable = [i for i in built['items'] if i['state'] == 'open']
    if dec['verdict'] == 'GREEN' and not actionable:
        return None
    cid = passage_case_id(row['_id'])
    coll = collection(REVIEWS)
    current = await coll.find_one({'_id': cid})
    if current:   # ulang (close diulang / Ulangi transaksi): roll yang kini tercatat → recorded, roll baru ditambah
        merged = {i['key']: i for i in current['rolls']}
        for it in built['items']:
            old = merged.get(it['key'])
            if not old:
                merged[it['key']] = it
            elif old['state'] in OPEN_STATES and it['state'] == 'recorded':
                old['state'] = 'recorded'
        await coll.update_one({'_id': cid, 'rev': current['rev']}, {'$set': {'rolls': list(merged.values()),
                                                                             'rev': current['rev'] + 1, 'updated_at': now()}})
        return await refresh(await coll.find_one({'_id': cid}))
    inp = row.get('gate_txn_input') or {}
    case = {'_id': cid, 'case_id': cid, 'kind': 'passage', 'status': 'open', 'rev': 0, 'created_at': now(),
            'updated_at': now(), 'warehouse_id': row.get('warehouse_id'), 'device_id': device['id'],
            'device_name': device.get('name') or device.get('code') or device['id'], 'gate_id': row.get('gate_id'),
            'direction': inp.get('direction') or dec.get('direction'), 'passage': row['_id'],
            'local_passage_id': row.get('local_passage_id'), 'decision_id': dec.get('decision_id'),
            'verdict': dec['verdict'], 'reason_codes': dec.get('reason_codes') or [], 'reasons': built['passage_reasons'],
            'sources': built['refs'], 'txn_mode': inp.get('mode') or 'evidence', 'latch_id': dec.get('latch_id'),
            'latch_open': bool(dec.get('latch_id')), 'manual_close': not actionable, 'simulated': bool(row.get('simulated')),
            'rolls': built['items'], 'actions': [], 'counts': dec.get('counts') or {}}
    try:
        await coll.insert_one(case)
    except Exception:  # noqa: BLE001 — dibuat bersamaan oleh pemicu lain → pakai yang ada
        return await coll.find_one({'_id': cid})
    await notify_case(case)
    return case


async def open_rolls_missing(state: Dict[str, Any], gate_mode: bool) -> Optional[Dict[str, Any]]:
    """Sesi dokumen ditutup dengan roll belum lewat (K-RFID-10) → kasus kuning `ROLLS_MISSING`."""
    close = state.get('close') or {}
    ref, direction = state['source_ref'], state['direction']
    cid = missing_case_id(ref, direction)
    info = await _roll_info([m['roll_id'] for m in close.get('missing') or []])
    items = []
    for m in close.get('missing') or []:
        it = _item(m['roll_id'], m['roll_id'], (info.get(m['roll_id']) or {}).get('epc'), ref)
        it['roll_no'] = m.get('roll_no') or (info.get(m['roll_id']) or {}).get('roll_no')
        _note(it, 'ROLLS_MISSING', 'REVIEW', 'Roll dokumen tidak terbaca lewat gate sampai dokumen ditutup.')
        items.append(it)
    case = {'_id': cid, 'case_id': cid, 'kind': 'rolls_missing', 'status': 'open', 'rev': 0, 'created_at': now(),
            'updated_at': now(), 'warehouse_id': state.get('warehouse_id'), 'device_id': None, 'device_name': None,
            'gate_id': None, 'direction': direction, 'passage': f"session:{cid}", 'local_passage_id': None,
            'decision_id': None, 'verdict': 'REVIEW', 'reason_codes': ['ROLLS_MISSING'],
            'reasons': [{'code': 'ROLLS_MISSING', 'level': 'REVIEW',
                         'message': f"{close.get('missing_count', len(items))} roll {ref.get('display_ref')} belum lewat gate saat dokumen ditutup."}],
            'sources': [ref], 'txn_mode': 'gate' if gate_mode else 'evidence', 'latch_id': None, 'latch_open': False,
            'manual_close': False, 'simulated': False, 'rolls': items, 'actions': [], 'session_close': close, 'counts': {}}
    try:
        await collection(REVIEWS).insert_one(case)
    except Exception:  # noqa: BLE001 — kasus sesi yang sama sudah ada (penutupan idempoten)
        return await collection(REVIEWS).find_one({'_id': cid})
    await notify_case(case)
    return case


async def notify_case(case: Dict[str, Any]) -> None:
    if case.get('simulated'):
        return   # lintasan simulator (alat admin/dev) tidak membanjiri kotak notifikasi
    wh = await db.warehouses.find_one({'id': case.get('warehouse_id')}, {'_id': 0, 'name': 1}) or {}
    red = case['verdict'] == 'RED'
    docs = ', '.join(s.get('display_ref') or s.get('source_id') for s in case.get('sources') or [])[:120]
    where = case.get('device_name') or 'sesi dokumen'
    title = (f"Gate MERAH terkunci: {where}" if red else f"Gate perlu diperiksa: {where}")[:140]
    open_n = sum(1 for r in case['rolls'] if r['state'] == 'open')
    msg = next((r.get('message') for r in case.get('reasons') or [] if r.get('message')), '') or \
        next((m for r in case['rolls'] for m in r.get('messages') or []), '')
    body = (f"{msg} {open_n} roll perlu tindakan" + (f" · dokumen {docs}" if docs else '')
            + f" · gudang {wh.get('name') or case.get('warehouse_id')}. Buka Monitor Gerbang › Antrean periksa.")[:600]
    for role in ('warehouse_admin', 'manager'):
        await create_notification(notif_type='rfid_gate_review', ref=f"rfid_review:{case['_id']}:{role}", title=title,
                                  body=body, severity='critical' if red else 'warning', link='cs-rfid-gate',
                                  recipient_role=role, dedupe=True, dedupe_scope='unread')


# ─── Penyegaran malas: roll yang sudah dilengkapi jalur lain → selesai ──────────────────────
async def _done_elsewhere(case: Dict[str, Any], item: Dict[str, Any]) -> Optional[str]:
    from services import rfid_v2_sessions as sessions
    ref, rid, direction = item.get('source_ref'), item.get('roll_id'), case.get('direction')
    if not ref or not rid or direction not in ('in', 'out'):
        return None
    claim = await collection(sessions.CROSSINGS).find_one(
        {'_id': sessions.claim_id(ref['source_type'], ref['source_id'], direction, rid)}, {'passage': 1})
    if claim and claim.get('passage') not in (case['passage'], f"review:{case['_id']}"):
        return 'Roll sudah lewat gate pada lintasan lain.'
    if direction == 'in' and ref['source_type'] == 'putaway':
        pa = await db.putaway_orders.find_one({'id': ref['source_id']}, {'_id': 0, 'items': 1})
        it = next((i for i in (pa or {}).get('items') or [] if i.get('roll_id') == rid), {})
        if it.get('status') == 'arrived':
            return 'Roll sudah tercatat tiba (handheld / jalur lain).'
        if it.get('status') == 'returned_transit':
            return 'Roll sudah dikembalikan ke transit lewat Putaway.'
    if direction == 'in' and ref['source_type'] == 'wh_transfer':
        r = await db.inventory_rolls.find_one({'id': rid}, {'_id': 0, 'last_transfer': 1})
        if ((r or {}).get('last_transfer') or {}).get('ref_id') == ref['source_id']:
            return 'Roll sudah diterima di tujuan (handheld / jalur lain).'
    return None


async def refresh(case: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not case or case.get('status') != 'open':
        return case
    from services import rfid_v2_latch as latch
    changed = False
    for it in case['rolls']:
        if it['state'] in OPEN_STATES:
            why = await _done_elsewhere(case, it)
            if why:
                it['state'] = 'done_elsewhere'
                it['actions'].append({'type': 'done_elsewhere', 'at': now(), 'by': 'Sistem', 'reason': why})
                changed = True
    if case.get('latch_open') and case.get('device_id'):
        cur = await latch.active(case['device_id'], case.get('gate_id'))
        if not cur or cur.get('latch_id') != case.get('latch_id'):
            case['latch_open'] = False
            changed = True
    upd: Dict[str, Any] = {}
    if changed:
        upd.update({'rolls': case['rolls'], 'latch_open': case['latch_open']})
    if not case.get('manual_close') and not case.get('latch_open') \
            and not any(i['state'] in LIVE_STATES for i in case['rolls']):
        upd.update({'status': 'resolved', 'resolution': {'type': 'auto', 'at': now(), 'by': 'Sistem',
                                                         'reason': 'Semua roll sudah ditindaklanjuti.'}})
    if upd:
        res = await collection(REVIEWS).update_one({'_id': case['_id'], 'rev': case['rev']},
                                                   {'$set': {**upd, 'rev': case['rev'] + 1, 'updated_at': now()}})
        if res.modified_count:
            case.update(upd)
            case['rev'] += 1
    return case


async def get_case(case_id: str) -> Dict[str, Any]:
    case = await collection(REVIEWS).find_one({'_id': case_id})
    if not case:
        fail(404, 'REVIEW_NOT_FOUND', 'Kasus antrean periksa tidak ditemukan.')
    return await refresh(case)


async def list_cases(*, warehouse_id: Optional[str] = None, device_id: Optional[str] = None, status: str = 'open',
                     verdict: Optional[str] = None, kind: Optional[str] = None, before: Optional[str] = None,
                     limit: int = 50) -> List[Dict[str, Any]]:
    if not 1 <= limit <= 100:
        fail(400, 'PAGE_LIMIT', 'Ukuran halaman wajib 1 sampai 100.')
    q: Dict[str, Any] = {}
    if status in ('open', 'resolved'):
        q['status'] = status
    for key, val in (('warehouse_id', warehouse_id), ('device_id', device_id), ('verdict', verdict), ('kind', kind)):
        if val:
            q[key] = val
    if before:
        q['created_at'] = {'$lt': before}
    rows = await collection(REVIEWS).find(q, {'actions': 0}).sort([('created_at', -1), ('_id', -1)]).to_list(limit)
    return rows


async def summary(warehouse_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    q: Dict[str, Any] = {'status': 'open'}
    if warehouse_ids is not None:
        q['warehouse_id'] = {'$in': warehouse_ids}
    rows = await collection(REVIEWS).aggregate([{'$match': q}, {'$group': {'_id': '$verdict', 'n': {'$sum': 1}}}]).to_list(10)
    by = {r['_id']: r['n'] for r in rows}
    return {'open': sum(by.values()), 'red': by.get('RED', 0), 'review': by.get('REVIEW', 0), 'green': by.get('GREEN', 0)}


def ensure_open(case: Dict[str, Any]) -> None:
    if case.get('status') != 'open':
        raise HTTPException(status_code=409, detail={'code': 'REVIEW_CLOSED', 'message': 'Kasus sudah ditutup.'})
