"""PREP-D1 — sesi dokumen bertahap (K-RFID-10 / AUD-MW-22) + klaim crossing tanpa bocor (AUD-MW-08).

Klaim crossing = satu dokumen per roll × dokumen × arah (`_id` deterministik, sama dengan `gate_evaluator`).
Status sesi dokumen = manifest dokumen bisnis (sumber kebenaran) × klaim: roll "sudah lewat" bila klaimnya ada.
Roll yang belum lewat TIDAK dinilai per lintasan; dinilai saat sesi dokumen ditutup (REVIEW `ROLLS_MISSING`,
kuning tanpa kunci). Klaim TIDAK pernah dihapus saat konflik lintasan lain — hanya klaim milik lintasan ini yang
dikompensasi bila kalah balapan.
"""
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException
from pymongo.errors import BulkWriteError

from services.rfid_v2_common import collection, digest, fail, now
from services import rfid_v2_sources as sources

CROSSINGS = 'rfid_v2_crossings'
SESSIONS = 'rfid_v2_doc_sessions'


def claim_id(source_type: str, source_id: str, direction: str, roll_id: str) -> str:
    return digest([source_type, source_id, direction, roll_id])


def session_id(source_type: str, source_id: str, direction: str) -> str:
    return digest(['doc_session', source_type, source_id, direction])


async def insert_claims(pid: str, direction: str, entries: List[Tuple[str, Dict[str, Any]]],
                        meta: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Klaim semua roll (roll_id, source_ref) atau TIDAK SATU PUN.

    1) Periksa semua klaim dulu ($in) — ada milik lintasan lain → tolak tanpa menyisipkan apa pun.
    2) Sisipkan sekaligus; bila kalah balapan dengan lintasan lain (duplikat milik lintasan lain) → hapus HANYA
       klaim yang disisipkan lintasan ini (berprasyarat `passage == pid`) lalu tolak.
    Return (berhasil, [roll_id konflik]). Ulangan oleh lintasan yang sama idempoten.
    """
    if not entries:
        return True, []
    docs = []
    for rid, ref in entries:
        docs.append({'_id': claim_id(ref['source_type'], ref['source_id'], direction, rid), 'passage': pid,
                     'roll_id': rid, 'source_type': ref['source_type'], 'source_id': ref['source_id'],
                     'direction': direction, 'at': now(), **meta})
    coll = collection(CROSSINGS)
    ids = [d['_id'] for d in docs]
    existing = await coll.find({'_id': {'$in': ids}}, {'passage': 1, 'roll_id': 1}).to_list(len(ids))
    conflicts = [e['roll_id'] for e in existing if e['passage'] != pid]
    if conflicts:
        return False, sorted(conflicts)
    mine = {e['_id'] for e in existing}
    fresh = [d for d in docs if d['_id'] not in mine]
    if fresh:
        try:
            await coll.insert_many(fresh, ordered=False)
        except BulkWriteError as bwe:
            dup = {fresh[e['index']]['_id'] for e in bwe.details.get('writeErrors', []) if e.get('code') == 11000}
            other = await coll.find({'_id': {'$in': list(dup)}, 'passage': {'$ne': pid}}, {'roll_id': 1}).to_list(len(dup))
            if other:
                await coll.delete_many({'_id': {'$in': ids}, 'passage': pid})   # kompensasi: hanya milik lintasan ini
                return False, sorted(o['roll_id'] for o in other)
            if any(e.get('code') != 11000 for e in bwe.details.get('writeErrors', [])):
                raise
    return True, []


async def passed_map(source_type: str, source_id: str, direction: str, limit: int = 2001) -> Dict[str, Dict[str, Any]]:
    rows = await collection(CROSSINGS).find(
        {'source_type': source_type, 'source_id': source_id, 'direction': direction},
        {'_id': 0, 'roll_id': 1, 'passage': 1, 'local_passage_id': 1, 'at': 1, 'review': 1, 'simulated': 1}).to_list(limit)
    return {r['roll_id']: r for r in rows}


async def remaining_after(entries: Iterable[Dict[str, Any]], direction: str) -> int:
    """Jumlah roll dokumen (gabungan sumber) yang BELUM lewat."""
    total = 0
    for entry in entries:
        ref = entry['source_ref']
        passed = await passed_map(ref['source_type'], ref['source_id'], direction)
        total += sum(1 for rid in entry['roll_ids'] if rid not in passed)
    return total


async def record_passage(entries: Iterable[Dict[str, Any]], direction: str, warehouse: str, pid: str,
                         local_pid: str, verdict: str, rolls_by_source: Dict[str, int]) -> None:
    """Jejak lintasan per sesi dokumen (lintasan mana menyentuh dokumen mana). Idempoten per lintasan."""
    coll = collection(SESSIONS)
    for entry in entries:
        ref = entry['source_ref']
        sid = session_id(ref['source_type'], ref['source_id'], direction)
        await coll.update_one({'_id': sid}, {'$setOnInsert': {'source_ref': ref, 'direction': direction,
                                                               'warehouse_id': warehouse, 'created_at': now(),
                                                               'status': 'open', 'passage_ids': [], 'passages': []}},
                              upsert=True)
        await coll.update_one({'_id': sid, 'passage_ids': {'$ne': pid}}, {
            '$set': {'roll_ids': entry['roll_ids'], 'updated_at': now()},
            '$push': {'passage_ids': {'$each': [pid], '$slice': -500},
                      'passages': {'$each': [{'passage': pid, 'local_passage_id': local_pid, 'at': now(),
                                              'verdict': verdict, 'rolls': rolls_by_source.get(ref['source_id'], 0)}],
                                   '$slice': -500}}})


async def _roll_numbers(ids: List[str]) -> Dict[str, Any]:
    from db import db
    rows = await db.inventory_rolls.find({'id': {'$in': ids}}, {'_id': 0, 'id': 1, 'roll_no': 1}).to_list(len(ids) + 1)
    return {r['id']: r.get('roll_no') for r in rows}


async def status(source: Dict[str, Any], direction: str, warehouse: Optional[str],
                 roll_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Status sesi dokumen per roll: sudah lewat / belum, lintasan mana.

    PREP-D2 — `roll_ids` = isi dokumen yang dibaca pemanggil (dokumen yang sudah ditutup/selesai tidak lagi lolos
    `manifest`): dipakai bila manifest aktif tidak tersedia, sehingga penutupan sesi otomatis tetap menilai roll."""
    record = await collection(SESSIONS).find_one(
        {'_id': session_id(source['source_type'], source['source_id'], direction)}, {'_id': 0})
    ref, ids, active = dict(source), None, False
    if warehouse:
        try:
            ref, ids = await sources.manifest(source, warehouse, direction)
            active = True
        except HTTPException:
            ids = None
    if ids is None and roll_ids is not None:
        ref, ids = (record or {}).get('source_ref') or ref, list(roll_ids)
    if ids is None:
        if not record:
            fail(404, 'SESSION_NOT_FOUND', 'Sesi dokumen belum ada (dokumen belum pernah melewati gate) atau dokumen tidak aktif.')
        ref, ids = record.get('source_ref') or ref, record.get('roll_ids') or []
    passed = await passed_map(ref['source_type'], ref['source_id'], direction)
    numbers = await _roll_numbers(ids)
    rolls = [{'roll_id': rid, 'roll_no': numbers.get(rid), 'passed': rid in passed,
              'local_passage_id': (passed.get(rid) or {}).get('local_passage_id'),
              'passed_at': (passed.get(rid) or {}).get('at'), 'review': bool((passed.get(rid) or {}).get('review'))}
             for rid in ids]
    n_passed = sum(1 for r in rolls if r['passed'])
    closed = (record or {}).get('close')
    state = 'closed' if closed else ('complete' if ids and n_passed == len(ids) else 'open')
    return {'source_ref': ref, 'direction': direction, 'warehouse_id': (record or {}).get('warehouse_id') or warehouse,
            'document_active': active, 'total': len(ids), 'passed': n_passed, 'remaining': len(ids) - n_passed,
            'status': state, 'rolls': rolls, 'passages': (record or {}).get('passages', [])[-50:], 'close': closed}


async def close_session(source: Dict[str, Any], direction: str, warehouse: Optional[str],
                        actor: Dict[str, Any], note: str = '', *, roll_ids: Optional[List[str]] = None,
                        completed: Optional[Dict[str, str]] = None, trigger: str = 'manual') -> Dict[str, Any]:
    """Dokumen ditutup/dikirim: roll yang belum lewat dinilai SEKARANG (REVIEW `ROLLS_MISSING`, bukan alarm).

    PREP-D2 — `completed` = {roll_id: jalur} roll yang tidak lewat gate tetapi SUDAH dilengkapi jalur lain (handheld:
    konfirmasi tiba PA, terima transfer, cek muat SO; atau kembali ke asal) → bukan "kurang". `trigger` = titik siklus
    hidup yang menutup sesi (`manual`, `putaway_closed`, `transfer_completed`, `shipment_departed`, …).
    Idempoten: penutupan kedua mengembalikan hasil pertama (tidak menimpa); `closed_now` = penutupan ini yang menang."""
    state = await status(source, direction, warehouse, roll_ids=roll_ids)
    if state.get('close'):
        return {**state, 'closed_now': False}
    done = completed or {}
    missing = [r for r in state['rolls'] if not r['passed'] and r['roll_id'] not in done]
    other = [{'roll_id': r['roll_id'], 'roll_no': r['roll_no'], 'via': done[r['roll_id']]}
             for r in state['rolls'] if not r['passed'] and r['roll_id'] in done]
    close = {'at': now(), 'actor_id': actor.get('id'), 'actor_name': actor.get('name'), 'note': (note or '')[:500],
             'verdict': 'REVIEW' if missing else 'GREEN',
             'reason_codes': ['ROLLS_MISSING'] if missing else ['ALL_ROLLS_PASSED'],
             'missing_count': len(missing), 'missing': [{'roll_id': r['roll_id'], 'roll_no': r['roll_no']} for r in missing[:2000]],
             'completed_count': len(other), 'completed': other[:2000], 'trigger': trigger,
             'review_count': sum(1 for r in state['rolls'] if r['review'])}
    ref = state['source_ref']
    sid = session_id(ref['source_type'], ref['source_id'], direction)
    await collection(SESSIONS).update_one({'_id': sid}, {'$setOnInsert': {
        'source_ref': ref, 'direction': direction, 'warehouse_id': warehouse, 'created_at': now(),
        'roll_ids': [r['roll_id'] for r in state['rolls']], 'passage_ids': [], 'passages': []}}, upsert=True)
    res = await collection(SESSIONS).update_one({'_id': sid, 'close': {'$exists': False}},   # CAS: penutup pertama menang
                                                {'$set': {'close': close, 'status': 'closed'}})
    out = await status(source, direction, warehouse, roll_ids=roll_ids)
    return {**out, 'closed_now': bool(res.modified_count)}
