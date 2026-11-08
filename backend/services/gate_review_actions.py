"""PREP-D2 — tindakan antrean periksa gate V2 (AUD-MW-10) + koreksi klaim crossing beraudit (AUD-MW-08 pemulihan).

Semua tindakan: alasan wajib, jejak di kasus (`actions[]`) + `audit()` di router, idempoten (roll yang sudah tuntas
dilewati), ubahan kasus CAS `rev`; efek transaksi lewat JALUR YANG SAMA dengan gate:
  * gate IN + Putaway  : item menunggu → `confirm_arrival_trip` (trip ber-id kasus, idempoten); item exception →
    `putaway_order_service.resolve_exception(accept)`;
  * gate IN + Transfer : `transfer_receipt_service.receive` per roll (pelanggaran aturan → pengecualian supervisor);
  * gate OUT / gedung handheld : klaim crossing roll (sesi dokumen menghitungnya lewat) + bukti di dokumen.
Koreksi klaim: lepas / pindahkan klaim roll × dokumen × arah (CAS pemilik lama, kompensasi bila kalah) → catatan di
`rfid_v2_claim_corrections` (siapa, kapan, alasan, isi klaim lama).
"""
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from db import db
from services import gate_review_service as rv
from services import gate_txn_service as gt
from services import rfid_v2_sessions as sessions
from services import rfid_v2_sources as sources
from services.notification_service import create_notification
from services.rfid_v2_common import collection, digest, fail, now

CORRECTIONS = 'rfid_v2_claim_corrections'
MIN_REASON = 5
MIN_CLAIM_REASON = 10


def need_reason(text: Any, minimum: int = MIN_REASON, label: str = 'Alasan') -> str:
    t = str(text or '').strip()
    if len(t) < minimum:
        fail(400, 'REASON_REQUIRED', f'{label} wajib diisi (minimal {minimum} huruf).')
    return t[:500]


def _who(actor: Dict[str, Any]) -> Dict[str, Any]:
    return {'by': actor.get('name'), 'by_id': actor.get('id'), 'at': now()}


async def _mutate(case_id: str, fn: Callable[[Dict[str, Any]], Any], extra: Optional[Callable] = None):
    """Baca → ubah di Python → tulis berprasyarat `rev` (ulang ≤ 4×). Return (kasus, hasil fn)."""
    coll = collection(rv.REVIEWS)
    for _ in range(4):
        case = await coll.find_one({'_id': case_id})
        if not case:
            fail(404, 'REVIEW_NOT_FOUND', 'Kasus antrean periksa tidak ditemukan.')
        out = fn(case)
        upd = {'rolls': case['rolls'], 'actions': case['actions'][-500:], 'status': case['status'],
               'latch_open': case.get('latch_open', False), 'rev': case['rev'] + 1, 'updated_at': now()}
        if case.get('resolution'):
            upd['resolution'] = case['resolution']
        res = await coll.update_one({'_id': case_id, 'rev': case['rev']}, {'$set': upd})
        if res.modified_count:
            case['rev'] += 1
            return case, out
    fail(409, 'REVIEW_BUSY', 'Kasus sedang diubah pengguna lain — muat ulang lalu ulangi.')


def _pick(case: Dict[str, Any], keys: List[str]) -> List[Dict[str, Any]]:
    if not isinstance(keys, list) or not keys or len(keys) > 500:
        fail(400, 'ROLLS_REQUIRED', 'Pilih 1 sampai 500 roll.')
    by = {i['key']: i for i in case['rolls']}
    missing = [k for k in keys if k not in by]
    if missing:
        fail(404, 'ROLL_NOT_IN_CASE', 'Sebagian roll tidak ada di kasus ini — muat ulang.')
    return [by[k] for k in dict.fromkeys(keys)]


async def _claim_passed(case: Dict[str, Any], ref: Dict[str, Any], rid: str, actor: Dict[str, Any], reason: str) -> None:
    doc = {'_id': sessions.claim_id(ref['source_type'], ref['source_id'], case['direction'], rid),
           'passage': f"review:{case['_id']}", 'roll_id': rid, 'source_type': ref['source_type'],
           'source_id': ref['source_id'], 'direction': case['direction'], 'at': now(), 'device_id': case.get('device_id'),
           'gate_id': case.get('gate_id'), 'review': True, 'review_accepted': True, 'review_case_id': case['_id'],
           'accepted_by': actor.get('name'), 'accept_reason': reason, 'simulated': bool(case.get('simulated'))}
    try:
        await collection(sessions.CROSSINGS).insert_one(doc)
    except DuplicateKeyError:
        pass   # sudah lewat (lintasan ini / lintasan lain) — sesi dokumen sudah menghitungnya


async def _txn_accept(case: Dict[str, Any], item: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> str:
    """Efek transaksi satu roll. Return uraian hasil (bahasa Indonesia)."""
    ref, rid, direction = item.get('source_ref'), item.get('roll_id'), case.get('direction')
    if not rid:
        fail(400, 'UNKNOWN_ROLL', 'Tag tidak dikenal — tidak ada roll yang bisa dicatat. Tolak/abaikan dengan alasan.')
    if not ref:
        fail(400, 'NO_DOCUMENT_FOR_ROLL', 'Roll tanpa dokumen tidak bisa diterima sebagai lewat — tolak/abaikan, '
                                          'atau buat dokumennya lalu lewatkan ulang di gate.')
    if direction == 'in' and case.get('txn_mode') == 'gate' and ref['source_type'] == 'putaway':
        from services import putaway_arrival_service as arr
        from services import putaway_order_service as pa
        order = await db.putaway_orders.find_one({'id': ref['source_id']}, {'_id': 0})
        it = next((i for i in (order or {}).get('items') or [] if i.get('roll_id') == rid), None)
        if not it:
            fail(409, 'ROLL_NOT_IN_DOCUMENT', 'Roll tidak lagi tercantum di Putaway ini.')
        if it['status'] == 'pending':
            src = {'type': 'gate', 'passage_id': f"rv-{case['_id'][:24]}-{digest([rid])[:16]}",
                   'device_id': case.get('device_id') or '', 'local_passage_id': case.get('local_passage_id') or '',
                   'review_case_id': case['_id']}
            out = await arr.confirm_arrival_trip(ref['source_id'], [it.get('epc') or it.get('roll_no')], src, actor)
            now_it = next((i for i in out['items'] if i['roll_id'] == rid), {})
            if now_it.get('status') != 'arrived':
                fail(409, 'ARRIVAL_FAILED', now_it.get('exception_reason') or 'Roll tidak bisa dicatat tiba.')
            return 'Dicatat tiba (trip dari antrean periksa).'
        if it['status'] == 'exception':
            await pa.resolve_exception(ref['source_id'], [rid], 'accept', [order.get('owner_entity_id')],
                                       actor.get('name') or 'Admin gudang', reason)
            return 'Pengecualian Putaway diterima — roll dicatat tiba.'
        if it['status'] == 'arrived':
            return 'Sudah tercatat tiba sebelumnya.'
        fail(409, 'ROLL_DECIDED', 'Roll sudah dikembalikan ke transit lewat Putaway — tidak bisa dicatat tiba.')
    if direction == 'in' and case.get('txn_mode') == 'gate' and ref['source_type'] == 'wh_transfer':
        from schemas import TransferReceiveIn, TransferReceiveLine
        from services import transfer_receipt_service as trs
        transfer = await db.warehouse_transfers.find_one({'id': ref['source_id']}, {'_id': 0})
        if not transfer:
            fail(404, 'SOURCE_NOT_FOUND', 'Transfer tidak ditemukan.')
        override = reason if 'RULE_BLOCKED' in item.get('codes') or [] else ''
        body = TransferReceiveIn(lines=[TransferReceiveLine(roll_id=rid)], rule_exception_reason=override,
                                 note=f"Diterima dari antrean periksa gate: {reason}"[:500])
        res = (await trs.receive(transfer, body, actor))['results'][0]
        if res['result'] not in ('received', 'damaged', 'hold', 'already'):
            fail(409, 'RECEIPT_FAILED', res.get('message') or 'Roll tidak bisa diterima.')
        return 'Diterima di gudang tujuan.' if res['result'] != 'already' else 'Sudah diterima sebelumnya.'
    return 'Dicatat sudah lewat gate (bukti dari antrean periksa).'


async def accept(case_id: str, keys: List[str], reason: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    reason = need_reason(reason)
    case = await rv.get_case(case_id)
    rv.ensure_open(case)
    done, skipped = [], []
    for item in _pick(case, keys):
        prev: Dict[str, str] = {}

        def claim(c, key=item['key']):
            it = next(i for i in c['rolls'] if i['key'] == key)
            if it['state'] not in rv.OPEN_STATES:
                return False
            prev['state'] = it['state']
            it['state'] = 'accepting'
            return True
        case, mine = await _mutate(case_id, claim)
        if not mine:
            skipped.append(item['key'])
            continue
        try:
            result = await _txn_accept(case, item, reason, actor)
            await _claim_passed(case, item['source_ref'], item['roll_id'], actor, reason)
        except BaseException:
            await _mutate(case_id, lambda c, key=item['key']: _set_state(c, key, prev['state']))
            raise
        done.append({'key': item['key'], 'roll_id': item['roll_id'], 'source_ref': item['source_ref'], 'result': result})

        def finish(c, key=item['key'], res=result):
            _set_state(c, key, 'accepted', {'type': 'accept', **_who(actor), 'reason': reason, 'result': res})
        case, _ = await _mutate(case_id, finish)
    for ref_id in {d['source_ref']['source_id'] for d in done}:
        rows = [d for d in done if d['source_ref']['source_id'] == ref_id]
        await gt.record_evidence(rows[0]['source_ref'], case['direction'], f"review:{case_id}:{uuid4().hex[:8]}",
                                 {'local_passage_id': case.get('local_passage_id'), 'verdict': 'ACCEPTED'},
                                 {'id': case.get('device_id') or 'review', 'name': f"Antrean periksa ({actor.get('name')})"},
                                 [d['roll_id'] for d in rows], txn=case.get('txn_mode') == 'gate', via='review')
    case = await _log(case_id, actor, 'accept', reason, [d['key'] for d in done])
    return {'case': case, 'accepted': done, 'skipped': skipped}


def _set_state(case: Dict[str, Any], key: str, state: str, action: Optional[Dict[str, Any]] = None) -> None:
    it = next(i for i in case['rolls'] if i['key'] == key)
    it['state'] = state
    if action:
        it['actions'].append(action)


async def _log(case_id: str, actor: Dict[str, Any], kind: str, reason: str, keys: List[str]) -> Dict[str, Any]:
    def add(c):
        c['actions'].append({'type': kind, **_who(actor), 'reason': reason, 'roll_keys': keys[:500]})
    await _mutate(case_id, add)
    return await rv.get_case(case_id)


async def reject(case_id: str, keys: List[str], reason: Any, mode: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`reject` = roll TIDAK sah lewat/tiba (klaim lintasan ini dilepas) · `ignore` = abaikan tanpa ubahan apa pun."""
    if mode not in ('reject', 'ignore'):
        fail(400, 'INVALID_MODE', "Pilih 'tolak' atau 'abaikan'.")
    reason = need_reason(reason)
    case = await rv.get_case(case_id)
    rv.ensure_open(case)
    picked = _pick(case, keys)

    def mark(c):
        hit = []
        for it in c['rolls']:
            if it['key'] in {p['key'] for p in picked} and it['state'] in rv.OPEN_STATES:
                it['state'] = 'rejected' if mode == 'reject' else 'ignored'
                it['actions'].append({'type': mode, **_who(actor), 'reason': reason})
                hit.append(it)
        return hit
    case, hit = await _mutate(case_id, mark)
    released = 0
    if mode == 'reject':
        for it in hit:
            if it.get('source_ref') and it.get('roll_id') and case.get('direction') in ('in', 'out'):
                res = await release_claim(it['source_ref'], case['direction'], it['roll_id'], reason, actor,
                                          expected_passage=case['passage'], case_id=case_id, strict=False)
                released += int(res.get('released', False))
    case = await _log(case_id, actor, mode, reason, [i['key'] for i in hit])
    return {'case': case, 'changed': len(hit), 'claims_released': released}


async def rescan(case_id: str, keys: List[str], note: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    note = need_reason(note, label='Catatan pindai ulang')
    case = await rv.get_case(case_id)
    rv.ensure_open(case)
    picked = {p['key'] for p in _pick(case, keys)}

    def mark(c):
        hit = []
        for it in c['rolls']:
            if it['key'] in picked and it['state'] == 'open':
                it['state'] = 'rescan'
                it['actions'].append({'type': 'rescan', **_who(actor), 'reason': note})
                hit.append(it)
        return hit
    case, hit = await _mutate(case_id, mark)
    if hit:
        docs = ', '.join(s.get('display_ref') or '' for s in case.get('sources') or [])[:100]
        nos = ', '.join(str(i.get('roll_no') or i.get('epc') or '?') for i in hit[:10])
        await create_notification(
            notif_type='rfid_gate_rescan', ref=f"rfid_rescan:{case_id}:{digest(sorted(picked))[:10]}",
            title=f"Pindai ulang {len(hit)} roll dengan handheld"[:140],
            body=(f"Roll {nos}{' …' if len(hit) > 10 else ''} (dokumen {docs}) belum terbukti lewat gate. {note} "
                  "Pindai dengan handheld: konfirmasi tiba Putaway / terima transfer / cek muat.")[:600],
            severity='warning', link='cs-rfid-gate', recipient_role='warehouse', dedupe=True, dedupe_scope='unread')
    case = await _log(case_id, actor, 'rescan', note, [i['key'] for i in hit])
    return {'case': case, 'changed': len(hit)}


async def dismiss(case_id: str, reason: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    reason = need_reason(reason, label='Catatan penutupan kasus')
    case = await rv.get_case(case_id)
    if case['status'] != 'open':
        return {'case': case, 'changed': 0}
    if case.get('latch_open'):
        fail(409, 'LATCH_ACTIVE', 'Gate masih terkunci oleh lintasan ini — akui kunci gate dulu.')

    def close(c):
        if any(i['state'] == 'accepting' for i in c['rolls']):
            fail(409, 'REVIEW_BUSY', 'Ada roll yang sedang diproses — tunggu lalu ulangi.')
        n = 0
        for it in c['rolls']:
            if it['state'] in rv.OPEN_STATES:
                it['state'] = 'ignored'
                it['actions'].append({'type': 'dismiss', **_who(actor), 'reason': reason})
                n += 1
        c['status'] = 'resolved'
        c['resolution'] = {'type': 'dismissed', **_who(actor), 'reason': reason}
        c['actions'].append({'type': 'dismiss', **_who(actor), 'reason': reason})
        return n
    case, n = await _mutate(case_id, close)
    return {'case': case, 'changed': n}


async def acknowledge_latch(case_id: str, note: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import rfid_v2_latch as latch
    note = need_reason(note, label='Catatan pemeriksaan')
    case = await rv.get_case(case_id)
    if not case.get('latch_id') or not case.get('device_id'):
        fail(400, 'NO_LATCH', 'Kasus ini tidak mengunci gate.')
    released = False
    if case.get('latch_open'):
        device = await db.rfid_devices.find_one({'id': case['device_id']}, {'_id': 0, 'api_key_hash': 0, 'api_key': 0})
        try:
            released = (await latch.acknowledge_gate(device, case['gate_id'], case['latch_id'], note, actor))['latch_released']
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            cur = await latch.active(case['device_id'], case['gate_id'])
            if cur and cur.get('latch_id') == case['latch_id']:
                raise

    def mark(c):
        c['latch_open'] = False
        c['actions'].append({'type': 'acknowledge_latch', **_who(actor), 'reason': note, 'released': released})
    await _mutate(case_id, mark)
    return {'case': await rv.get_case(case_id), 'latch_released': released}


async def retry(case_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    case = await rv.get_case(case_id)
    rv.ensure_open(case)
    if case['kind'] != 'passage' or not case.get('device_id'):
        fail(400, 'NOTHING_TO_RETRY', 'Kasus ini tidak punya transaksi gate yang bisa diulang.')
    device = await db.rfid_devices.find_one({'id': case['device_id']}, {'_id': 0, 'api_key_hash': 0, 'api_key': 0})
    if not device:
        fail(404, 'DEVICE_NOT_FOUND', 'Perangkat lintasan tidak ditemukan.')
    results = await gt.post_close(device, case['passage'], force=True) or []
    case = await _log(case_id, actor, 'retry', 'Ulangi transaksi gate', [])
    return {'case': case, 'results': [{k: r.get(k) for k in ('state', 'kind', 'message')} for r in results]}


# ─── Koreksi klaim crossing (AUD-MW-08) ───────────────────────────────────────────────────
async def list_claims(ref: Dict[str, Any], direction: str) -> Dict[str, Any]:
    passed = await sessions.passed_map(ref['source_type'], ref['source_id'], direction)
    fixes = await collection(CORRECTIONS).find({'$or': [
        {'source_type': ref['source_type'], 'source_id': ref['source_id'], 'direction': direction},
        {'target.source_type': ref['source_type'], 'target.source_id': ref['source_id'], 'direction': direction}]},
        {'_id': 0}).sort('at', -1).to_list(200)
    return {'source_ref': ref, 'direction': direction,
            'claims': [{'roll_id': rid, **{k: v for k, v in c.items() if k != 'roll_id'}} for rid, c in passed.items()],
            'corrections': fixes}


async def _correction(action: str, claim: Dict[str, Any], reason: str, actor: Dict[str, Any], **extra) -> Dict[str, Any]:
    row = {'_id': str(uuid4()), 'action': action, 'roll_id': claim['roll_id'], 'source_type': claim['source_type'],
           'source_id': claim['source_id'], 'direction': claim['direction'], 'claim': claim, 'reason': reason,
           **_who(actor), **extra}
    await collection(CORRECTIONS).insert_one(row)
    row.pop('_id')
    return row


async def release_claim(ref: Dict[str, Any], direction: str, roll_id: str, reason: Any, actor: Dict[str, Any], *,
                        expected_passage: Optional[str] = None, case_id: Optional[str] = None,
                        strict: bool = True) -> Dict[str, Any]:
    """Lepas klaim roll × dokumen × arah (roll dianggap BELUM lewat lagi). CAS pemilik klaim; beraudit."""
    reason = need_reason(reason, MIN_CLAIM_REASON if strict else MIN_REASON)
    cid = sessions.claim_id(ref['source_type'], ref['source_id'], direction, roll_id)
    coll = collection(sessions.CROSSINGS)
    claim = await coll.find_one({'_id': cid})
    if not claim:
        if strict:
            fail(404, 'CLAIM_NOT_FOUND', 'Roll ini belum tercatat lewat untuk dokumen & arah tersebut.')
        return {'released': False}
    if expected_passage and claim.get('passage') not in (expected_passage, f"review:{case_id}"):
        return {'released': False, 'reason': 'Klaim milik lintasan lain — tidak dilepas.'}
    res = await coll.delete_one({'_id': cid, 'passage': claim.get('passage')})
    if not res.deleted_count:
        fail(409, 'CLAIM_CHANGED', 'Klaim berubah bersamaan — muat ulang lalu ulangi.')
    claim['claim_id'] = claim.pop('_id')
    row = await _correction('release', claim, reason, actor, case_id=case_id)
    return {'released': True, 'correction': row}


async def move_claim(ref: Dict[str, Any], target: Dict[str, Any], direction: str, roll_id: str, reason: Any,
                     actor: Dict[str, Any], warehouse_id: str) -> Dict[str, Any]:
    """Pindahkan klaim ke dokumen lain yang MEMUAT roll itu (roll sebenarnya lewat untuk dokumen tujuan)."""
    reason = need_reason(reason, MIN_CLAIM_REASON)
    if (ref['source_type'], ref['source_id']) == (target['source_type'], target['source_id']):
        fail(400, 'SAME_DOCUMENT', 'Dokumen tujuan sama dengan dokumen asal.')
    try:
        tref, ids = await sources.manifest(target, warehouse_id, direction)
    except HTTPException:
        fail(409, 'TARGET_NOT_ACTIVE', 'Dokumen tujuan tidak aktif untuk gate gudang & arah ini.')
    if roll_id not in ids:
        fail(409, 'NOT_IN_TARGET', 'Roll tidak tercantum di dokumen tujuan.')
    coll = collection(sessions.CROSSINGS)
    old_id = sessions.claim_id(ref['source_type'], ref['source_id'], direction, roll_id)
    claim = await coll.find_one({'_id': old_id})
    if not claim:
        fail(404, 'CLAIM_NOT_FOUND', 'Roll ini belum tercatat lewat untuk dokumen asal.')
    new_id = sessions.claim_id(tref['source_type'], tref['source_id'], direction, roll_id)
    fresh = {**{k: v for k, v in claim.items() if k != '_id'}, '_id': new_id, 'source_type': tref['source_type'],
             'source_id': tref['source_id'], 'moved_from': old_id, 'moved_at': now(), 'moved_by': actor.get('name')}
    try:
        await coll.insert_one(fresh)
    except DuplicateKeyError:
        fail(409, 'TARGET_ALREADY_CLAIMED', 'Roll sudah tercatat lewat untuk dokumen tujuan.')
    res = await coll.delete_one({'_id': old_id, 'passage': claim.get('passage')})
    if not res.deleted_count:
        await coll.delete_one({'_id': new_id, 'moved_from': old_id})   # kompensasi: hanya klaim yang baru dibuat
        fail(409, 'CLAIM_CHANGED', 'Klaim asal berubah bersamaan — muat ulang lalu ulangi.')
    claim['claim_id'] = claim.pop('_id')
    row = await _correction('move', claim, reason, actor, target={k: tref.get(k) for k in ('source_type', 'source_id', 'display_ref')})
    return {'moved': True, 'correction': row}
