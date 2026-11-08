"""PREP-D1 — SATU kunci per gate (K-RFID-09 / AUD-MW-03).

Hanya lintasan RED (pelanggaran nyata) yang membuka/menambah kunci gate. Selama kunci belum diakui, lintasan lain
TETAP dinilai dengan verdict aslinya (tidak dipaksa GATE_LATCHED); lintasan RED berikutnya ikut tercatat di kunci
yang sama (bukan kunci baru). Satu pengakuan (sesi pengguna, bukan device key) melepas gate; verdict & bukti lama
tidak pernah diubah menjadi hijau.
"""
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from services.rfid_v2_common import collection, digest, fail, now

LATCHES = 'rfid_v2_gate_latches'


def latch_key(device_id: str, gate_id: str) -> str:
    return digest(['gate_latch', device_id, gate_id])


async def active(device_id: str, gate_id: str) -> Optional[Dict[str, Any]]:
    return await collection(LATCHES).find_one({'_id': latch_key(device_id, gate_id), 'active': True},
                                              {'_id': 0, 'passage_ids': 0})


async def add_passage(device_id: str, gate_id: str, pid: str, local_pid: str, decision_id: str,
                      reason_codes: List[str]) -> str:
    """Masukkan lintasan RED ke kunci gate aktif, atau buka kunci baru. Idempoten per lintasan. Return latch_id."""
    key = latch_key(device_id, gate_id)
    entry = {'passage': pid, 'local_passage_id': local_pid, 'decision_id': decision_id,
             'reason_codes': reason_codes[:20], 'at': now()}
    coll = collection(LATCHES)
    for _ in range(3):
        row = await coll.find_one({'_id': key, 'active': True, 'passage_ids': pid}, {'latch_id': 1})
        if row:
            return row['latch_id']
        res = await coll.find_one_and_update(
            {'_id': key, 'active': True, 'passage_ids': {'$ne': pid}},
            {'$push': {'passages': {'$each': [entry], '$slice': -200}}, '$addToSet': {
                'passage_ids': pid, 'reason_codes': {'$each': reason_codes[:20]}}, '$set': {'updated_at': now()}},
            projection={'latch_id': 1})
        if res:
            return res['latch_id']
        latch_id = str(uuid4())
        try:
            await coll.update_one(
                {'_id': key, 'active': {'$ne': True}},
                {'$set': {'device_id': device_id, 'gate_id': gate_id, 'active': True, 'latch_id': latch_id,
                          'since': now(), 'updated_at': now(), 'passages': [entry], 'passage_ids': [pid],
                          'reason_codes': reason_codes[:20], 'released_at': None, 'released_by': None,
                          'release_note': None}},
                upsert=True)
            return latch_id
        except DuplicateKeyError:
            continue   # kunci aktif dibuat bersamaan → ulangi sebagai penambahan
    fail(503, 'LATCH_BUSY', 'Kunci gate sedang diperbarui; ulangi.')


async def release(device_id: str, gate_id: str, latch_id: Optional[str], actor: Dict[str, Any], note: str,
                  passage: Optional[str] = None) -> bool:
    """Lepas kunci (CAS: aktif + latch_id cocok / lintasan anggota). Return True bila kunci dilepas."""
    query: Dict[str, Any] = {'_id': latch_key(device_id, gate_id), 'active': True}
    if latch_id:
        query['latch_id'] = latch_id
    if passage:
        query['passage_ids'] = passage
    row = await collection(LATCHES).find_one_and_update(query, {'$set': {
        'active': False, 'released_at': now(), 'released_by': actor.get('id'), 'released_by_name': actor.get('name'),
        'release_note': note}}, projection={'passage_ids': 1, 'latch_id': 1})
    if not row:
        return False
    await collection('rfid_v2_passages').update_many({'_id': {'$in': row.get('passage_ids') or []}}, {'$set': {
        'latch_release': {'latch_id': row['latch_id'], 'at': now(), 'actor_id': actor.get('id'), 'note': note}}})
    return True


def _note(note: Any) -> str:
    if not isinstance(note, str) or len(note.strip()) < 5:
        fail(400, 'NOTE_REQUIRED', 'Catatan pemeriksaan minimal 5 karakter.')
    return note.strip()[:1000]


async def acknowledge_passage(device: Dict[str, Any], passage_id: str, note: Any, actor: Dict[str, Any],
                              latch_id: Optional[str] = None, decision_id: Optional[str] = None) -> Dict[str, Any]:
    note = _note(note)
    pid = digest([device['id'], passage_id])
    row = await collection('rfid_v2_passages').find_one({'_id': pid}, {'gate_id': 1, 'decision': 1, 'state': 1})
    if not row:
        fail(409, 'NOT_ACKNOWLEDGEABLE', 'Passage belum final atau sudah ditindaklanjuti.')
    if decision_id and (row.get('decision') or {}).get('decision_id') != decision_id:
        fail(409, 'STALE_ACKNOWLEDGE', 'Keputusan lintasan sudah berbeda dari yang ditampilkan; muat ulang.')
    gate_id = row['gate_id']
    if latch_id:
        cur = await active(device['id'], gate_id)
        if cur and cur['latch_id'] != latch_id:
            fail(409, 'STALE_ACKNOWLEDGE', 'Kunci gate sudah berganti; muat ulang sebelum mengakui.')
    result = await collection('rfid_v2_passages').update_one(
        {'_id': pid, 'state': 'FINAL', 'acknowledged': False},
        {'$set': {'acknowledged': True, 'ack_actor_id': actor['id'], 'ack_note': note, 'ack_at': now()}})
    if not result.matched_count:
        fail(409, 'NOT_ACKNOWLEDGEABLE', 'Passage belum final atau sudah ditindaklanjuti.')
    released = await release(device['id'], gate_id, latch_id, actor, note, passage=pid)
    # Pengakuan melepas alarm; tidak pernah mengubah keputusan menjadi GREEN.
    return {'request_id': str(uuid4()), 'server_time': now(), 'latch_released': released,
            'latched': bool(await active(device['id'], gate_id))}


async def acknowledge_gate(device: Dict[str, Any], gate_id: str, latch_id: str, note: Any,
                           actor: Dict[str, Any]) -> Dict[str, Any]:
    note = _note(note)
    if not isinstance(latch_id, str) or not latch_id:
        fail(400, 'LATCH_REQUIRED', 'Sertakan latch_id kunci yang diperiksa.')
    released = await release(device['id'], gate_id, latch_id, actor, note)
    if not released:
        fail(409, 'STALE_ACKNOWLEDGE', 'Kunci gate tidak aktif atau sudah berganti; muat ulang.')
    return {'request_id': str(uuid4()), 'server_time': now(), 'latch_released': True,
            'latched': bool(await active(device['id'], gate_id))}
