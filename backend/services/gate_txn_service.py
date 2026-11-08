"""PREP-D2 — lintasan gate V2 → transaksi gudang (K-GDG-02/03, K-RFID-09/10, K-OPN-03 — keputusan pemilik 8 Nov 2026).

Dua kait di `rfid_v2_service.close`:
  1. `precheck(result, cfg, device)` — SEBELUM klaim & keputusan final dikirim ke reader:
     * mode gedung (`warehouse_gate_policy`): transaksi hanya bila gedung bermode GATE dan reader ini tertaut sebagai
       gate IN/OUT gedung itu; selain itu lintasan = BUKTI saja (alur handheld lama tetap jalan) → INFO;
     * area dibekukan pendaftaran awal (409 `REGISTRATION_FREEZE`) → REVIEW `AREA_FROZEN` (kuning, tanpa kunci) dan
       dokumen itu TIDAK ditransaksikan.
  2. `post_close(device, pid)` — SESUDAH keputusan tersimpan (masukan dibekukan di lintasan, `gate_txn_input`):
     per dokumen sumber, idempoten per (lintasan, dokumen) lewat buku `rfid_v2_gate_txn` (state CAS):
       · gate IN + Putaway  → `putaway_arrival_service.confirm_arrival_trip(…, {"type": "gate", "passage_id"})`;
       · gate IN + Transfer → `transfer_receipt_service.receive` per roll (CAS per roll, "already" bila ulang);
       · gate IN + Perbaikan/Makloon kembali → bukti di dokumen (hasilnya dicatat admin di dokumen itu);
       · gate OUT (SJ, transfer, Order Makloon, Perbaikan, putaway) → bukti lintasan per trip di dokumen
         (`gate_exits[]`: trip ke-n, waktu, roll, perangkat, lintasan).
     Hijau → roll yang cocok dicatat. Kuning → roll yang COCOK & berklaim tetap dicatat (barang jalan), roll bermasalah
     + alasan tingkat lintasan ke antrean periksa (`gate_review_service`). Merah / tanpa klaim → TIDAK ada yang dicatat.
  3. `close_document_session(...)` — titik siklus hidup dokumen (PA selesai, transfer selesai, SJ berangkat, …) menutup
     sesi dokumen gate (K-RFID-10): roll yang belum lewat → kuning `ROLLS_MISSING` ke antrean periksa; roll yang sudah
     dilengkapi handheld / jalur lain dicatat sebagai pelengkap, bukan kurang.
Semua kait best-effort: kegagalan transaksi tidak pernah menggagalkan ACK lintasan ke reader (dicatat `error` + antrean).
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from db import db
from services import registration_freeze as rfz
from services.rfid_v2_common import collection, digest, now

logger = logging.getLogger(__name__)
LEDGER = 'rfid_v2_gate_txn'
FINAL_STATES = ('done', 'evidence', 'frozen', 'skipped')
STALE_S = 120
DOC_COLL = {'shipment': 'shipments', 'wh_transfer': 'warehouse_transfers', 'putaway': 'putaway_orders',
            'makloon_order': 'makloon_orders', 'repair_order': 'repair_orders'}
MODE_TEXT = {
    'HANDHELD_MODE': 'Gedung bermode handheld — gate hanya mencatat bukti; konfirmasi gerak tetap lewat handheld.',
    'GATE_NOT_PAIRED': 'Reader ini belum tertaut sebagai gate IN/OUT di profil gedung — lintasan hanya bukti.',
    'QUANTITY_MODE': 'Gedung mode kuantitas tanpa tag — gate tidak berlaku, lintasan hanya bukti.',
    'SIMULATED_EVIDENCE': 'Lintasan simulator — hanya bukti (transaksi butuh Mode simulasi RFID aktif untuk PT dokumen).',
}


def gate_actor(device: Dict[str, Any], direction: str) -> Dict[str, Any]:
    label = 'Gate IN' if direction == 'in' else 'Gate OUT'
    return {'id': f"gate:{device['id']}", 'name': f"{label} {device.get('code') or device.get('name') or device['id']}",
            'role': 'system'}


def txn_mode(policy: Optional[Dict[str, Any]], device_id: str, direction: str) -> Tuple[str, Optional[str]]:
    """('gate' | 'evidence', kode INFO alasan bukti-saja)."""
    if not policy:
        return 'evidence', 'GATE_NOT_PAIRED'
    if policy.get('effective_mode') == 'manual':
        return 'evidence', 'QUANTITY_MODE'
    if policy.get('effective_mode') != 'gate':
        return 'evidence', 'HANDHELD_MODE'
    paired = policy.get('device_ids_in' if direction == 'in' else 'device_ids_out') or []
    return ('gate', None) if device_id in paired else ('evidence', 'GATE_NOT_PAIRED')


async def gate_policy(warehouse_id: str) -> Optional[Dict[str, Any]]:
    from services import warehouse_profile_service as whp
    try:
        return await whp.warehouse_gate_policy(warehouse_id)
    except HTTPException:
        return None


async def gate_validates(warehouse_id: Optional[str], direction: str) -> bool:
    """Gedung bermode gate DENGAN perangkat arah itu tertaut → gate = alat utama (K-GDG-02/03)."""
    if not warehouse_id:
        return False
    pol = await gate_policy(warehouse_id)
    return bool(pol and pol.get('effective_mode') == 'gate'
                and pol.get('device_ids_in' if direction == 'in' else 'device_ids_out'))


def _freeze_message(exc: HTTPException) -> Optional[str]:
    d = exc.detail
    if exc.status_code == 409 and isinstance(d, dict) and d.get('code') == rfz.FREEZE_CODE:
        return d.get('message') or 'Area sedang dibekukan untuk pendaftaran awal stok.'
    return None


async def _frozen(ref: Dict[str, Any], direction: str, roll_ids: List[str]) -> Optional[str]:
    typ, sid = ref['source_type'], ref['source_id']
    try:
        if direction == 'in' and typ == 'putaway':
            order = await db.putaway_orders.find_one({'id': sid}, {'_id': 0, 'items.roll_id': 1, 'to_warehouse_id': 1})
            if order:
                await rfz.assert_order_movable(order, 'mencatat tiba lewat gate IN')
        elif direction == 'in' and typ == 'wh_transfer':
            tr = await db.warehouse_transfers.find_one({'id': sid}, {'_id': 0, 'id': 1, 'dest_warehouse_id': 1,
                                                                    'source_warehouse_id': 1})
            if tr:
                await rfz.assert_transfer_movable(tr, 'in')
        else:
            rolls = await db.inventory_rolls.find({'id': {'$in': roll_ids}}, {'_id': 0, 'id': 1, 'roll_no': 1,
                                                                              'warehouse_id': 1, 'bin_id': 1}).to_list(2001)
            await rfz.assert_rolls_movable(rolls, 'mencatat roll lewat gate')
    except HTTPException as exc:
        msg = _freeze_message(exc)
        if msg:
            return msg
        raise
    return None


def _matched_by_source(matched: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for rid, ref in matched:
        out.setdefault(ref['source_id'], []).append(rid)
    return out


async def _simulation_allowed(entries: List[Dict[str, Any]]) -> bool:
    """Lintasan SIMULATOR hanya boleh menulis transaksi bila 'Mode simulasi RFID' (`wms.rfid_simulation`) menyala
    untuk PT pemilik SEMUA dokumennya (pola cek muat simulasi) — mencegah uji simulator mengubah stok produksi."""
    from services import rfid_v2_sources as sources
    from services.config_resolver import value_of
    for entry in entries:
        _, doc = await sources.source_document(entry['source_ref'])
        ent = (doc or {}).get('owner_entity_id') or (doc or {}).get('entity_id') or ''
        try:
            if not await value_of('wms.rfid_simulation', {'entity_id': ent}):
                return False
        except Exception:  # noqa: BLE001 — registry belum termuat: anggap mati (aman)
            return False
    return True


async def precheck(result: Dict[str, Any], cfg: Dict[str, Any], device: Dict[str, Any],
                   simulated: bool = False) -> None:
    """Tambah alasan mode gedung & area beku ke hasil `rfid_v2_policy.decide` (sebelum klaim). Mengubah `result`."""
    from services.rfid_v2_policy import INFO, REVIEW
    direction = result.get('direction')
    txn: Dict[str, Any] = {'mode': 'evidence', 'frozen': {}}
    result['txn'] = txn
    if not direction or not result.get('matched'):
        return
    mode, why = txn_mode(await gate_policy(cfg['warehouse_id']), device['id'], direction)
    if mode == 'gate' and simulated and not await _simulation_allowed(result.get('entries') or []):
        mode, why = 'evidence', 'SIMULATED_EVIDENCE'
    txn['mode'] = mode
    if why:
        result['reasons'].add(INFO, why, MODE_TEXT[why])
    by_src = _matched_by_source(result['matched'])
    for entry in result.get('entries') or []:
        ref = entry['source_ref']
        rolls = by_src.get(ref['source_id'])
        if not rolls:
            continue
        msg = await _frozen(ref, direction, rolls)
        if msg:
            txn['frozen'][ref['source_id']] = msg
            result['reasons'].add(REVIEW, 'AREA_FROZEN', msg, source_id=ref['source_id'])
    if txn['frozen'] and result['verdict'] == 'GREEN':
        result['verdict'] = 'REVIEW'   # K-OPN-03 × K-RFID-09: barang jalan, tidak ada transaksi, antrean periksa


def build_input(result: Dict[str, Any], device: Dict[str, Any], cfg: Dict[str, Any], local_pid: str) -> Dict[str, Any]:
    """Masukan transaksi yang dibekukan di lintasan (dipakai ulang saat close diulang / tombol Ulangi)."""
    txn = result.get('txn') or {'mode': 'evidence', 'frozen': {}}
    by_src = _matched_by_source(result.get('matched') or [])
    srcs = [{'source_ref': e['source_ref'], 'roll_ids': by_src[e['source_ref']['source_id']]}
            for e in result.get('entries') or [] if by_src.get(e['source_ref']['source_id'])]
    return {'direction': result.get('direction'), 'verdict': result['verdict'],
            'claimable': bool(result.get('claimable')), 'mode': txn['mode'], 'frozen': txn['frozen'],
            'sources': srcs, 'device_id': device['id'], 'warehouse_id': cfg['warehouse_id'],
            'local_passage_id': local_pid}


# ─── Transaksi per dokumen ─────────────────────────────────────────────────────────────────
async def _roll_nos(ids: List[str]) -> Dict[str, str]:
    rows = await db.inventory_rolls.find({'id': {'$in': ids}}, {'_id': 0, 'id': 1, 'roll_no': 1}).to_list(len(ids) + 1)
    return {r['id']: r.get('roll_no') or r['id'] for r in rows}


async def record_evidence(ref: Dict[str, Any], direction: str, pid: str, inp: Dict[str, Any], device: Dict[str, Any],
                          roll_ids: List[str], *, txn: bool, via: str = 'gate') -> Optional[Dict[str, Any]]:
    """Bukti lintasan per trip di dokumen (`gate_exits` / `gate_arrivals`). Idempoten per lintasan."""
    name = DOC_COLL.get(ref['source_type'])
    if not name:
        return None
    doc_id = ref.get('doc_id') or ref['source_id']
    field = 'gate_exits' if direction == 'out' else 'gate_arrivals'
    doc = await db[name].find_one({'id': doc_id}, {'_id': 0, 'id': 1, field: 1})
    if not doc:
        return None
    mine = [e for e in doc.get(field) or [] if e.get('source_id', ref['source_id']) == ref['source_id']]
    hit = next((e for e in mine if e.get('passage') == pid), None)
    if hit:
        return hit
    nos = await _roll_nos(roll_ids)
    entry = {'passage': pid, 'local_passage_id': inp.get('local_passage_id'), 'device_id': device['id'],
             'device_name': device.get('name') or device.get('code') or device['id'], 'source_id': ref['source_id'],
             'trip_no': len(mine) + 1, 'at': now(), 'verdict': inp.get('verdict'), 'via': via, 'txn': txn,
             'roll_ids': roll_ids[:2000], 'roll_nos': [nos.get(r, r) for r in roll_ids[:2000]], 'count': len(roll_ids),
             'simulated': bool(inp.get('simulated'))}
    await db[name].update_one({'id': doc_id, f'{field}.passage': {'$ne': pid}},
                              {'$push': {field: {'$each': [entry], '$slice': -500}}, '$set': {f'{field}_last_at': now()}})
    return entry


async def _with_retry(fn, attempts: int = 6):
    for n in range(attempts):
        try:
            return await fn()
        except HTTPException as exc:
            d = exc.detail if isinstance(exc.detail, dict) else {}
            if exc.status_code == 409 and d.get('code') == 'SAGA_IN_PROGRESS' and n < attempts - 1:
                await asyncio.sleep(0.2 * (n + 1))   # trip lain sedang menulis dokumen yang sama → ulang
                continue
            raise


async def _putaway_in(ref, pid, inp, device, roll_ids) -> Dict[str, Any]:
    from services import putaway_arrival_service as arr
    order = await db.putaway_orders.find_one({'id': ref['source_id']}, {'_id': 0, 'items': 1})
    items = {i['roll_id']: i for i in (order or {}).get('items') or []}
    reads = [items[r].get('epc') or items[r].get('roll_no') for r in roll_ids if r in items]
    src = {'type': 'gate', 'passage_id': pid, 'device_id': device['id'], 'local_passage_id': inp.get('local_passage_id')}
    out = await _with_retry(lambda: arr.confirm_arrival_trip(ref['source_id'], reads, src, gate_actor(device, 'in')))
    trip = out.get('trip') or {}
    failed = [i for i in out.get('items') or [] if i['roll_id'] in set(roll_ids) and i.get('status') == 'exception']
    return {'state': 'done', 'kind': 'putaway_arrival', 'pa_status': out.get('status'),
            'trip_no': trip.get('trip_no'), 'arrived': trip.get('arrived_roll_nos') or [],
            'already': trip.get('already_roll_nos') or [], 'duplicate_trip': bool(out.get('duplicate_trip')),
            'problems': [{'roll_id': i['roll_id'], 'code': 'ARRIVAL_EXCEPTION',
                          'message': i.get('exception_reason') or 'Roll tidak bisa dicatat tiba'} for i in failed]}


async def _transfer_in(ref, pid, inp, device, roll_ids) -> Dict[str, Any]:
    from schemas import TransferReceiveIn, TransferReceiveLine
    from services import transfer_receipt_service as trs
    results: List[Dict[str, Any]] = []
    status = None
    for i in range(0, len(roll_ids), 500):
        transfer = await db.warehouse_transfers.find_one({'id': ref['source_id']}, {'_id': 0})
        body = TransferReceiveIn(lines=[TransferReceiveLine(roll_id=r) for r in roll_ids[i:i + 500]],
                                 note=f"Gate IN lintasan {inp.get('local_passage_id')}"[:500])
        res = await trs.receive(transfer, body, gate_actor(device, 'in'))
        results += res['results']
        status = res['transfer_status']
    bad = {'blocked_rules': 'RULE_BLOCKED', 'not_in_transit': 'NOT_IN_TRANSIT', 'wrong_roll': 'NOT_IN_TRANSIT'}
    return {'state': 'done', 'kind': 'transfer_receipt', 'transfer_status': status,
            'arrived': [r.get('roll_no') for r in results if r['result'] in ('received', 'damaged', 'hold')],
            'already': [r.get('roll_no') for r in results if r['result'] == 'already'],
            'problems': [{'roll_id': r.get('roll_id'), 'code': bad[r['result']], 'message': r.get('message', '')}
                         for r in results if r['result'] in bad]}


async def _apply(ref: Dict[str, Any], pid: str, inp: Dict[str, Any], device: Dict[str, Any],
                 roll_ids: List[str]) -> Dict[str, Any]:
    direction = inp['direction']
    frozen = (inp.get('frozen') or {}).get(ref['source_id'])
    if inp.get('mode') == 'unknown':   # cek awal gagal (rfid_v2_service._gate_txn_precheck) → hitung ulang sekarang
        mode = txn_mode(await gate_policy(inp.get('warehouse_id')), device['id'], direction)[0]
        if mode == 'gate' and inp.get('simulated') and not await _simulation_allowed([{'source_ref': ref}]):
            mode = 'evidence'
        inp = {**inp, 'mode': mode}
        frozen = frozen or await _frozen(ref, direction, roll_ids)
    gate_mode = inp.get('mode') == 'gate'
    if not inp.get('claimable') or inp.get('verdict') not in ('GREEN', 'REVIEW'):
        return {'state': 'skipped', 'kind': 'none', 'message': 'Lintasan tanpa klaim (merah/batal/konteks tidak sah).'}
    if frozen or not gate_mode or direction == 'out' or ref['source_type'] not in ('putaway', 'wh_transfer'):
        ev = await record_evidence(ref, direction, pid, inp, device, roll_ids, txn=gate_mode and not frozen)
        if frozen:
            return {'state': 'frozen', 'kind': 'none', 'message': frozen,
                    'problems': [{'roll_id': r, 'code': 'AREA_FROZEN', 'message': frozen} for r in roll_ids]}
        kind = 'exit_evidence' if direction == 'out' else 'arrival_evidence'
        return {'state': 'done' if gate_mode else 'evidence', 'kind': kind, 'trip_no': (ev or {}).get('trip_no'),
                'recorded': len(roll_ids)}
    try:
        if ref['source_type'] == 'putaway':
            return await _putaway_in(ref, pid, inp, device, roll_ids)
        return await _transfer_in(ref, pid, inp, device, roll_ids)
    except HTTPException as exc:
        msg = _freeze_message(exc)
        if msg:
            return {'state': 'frozen', 'kind': 'none', 'message': msg,
                    'problems': [{'roll_id': r, 'code': 'AREA_FROZEN', 'message': msg} for r in roll_ids]}
        raise


async def process_source(device: Dict[str, Any], pid: str, inp: Dict[str, Any], ref: Dict[str, Any],
                         roll_ids: List[str]) -> Dict[str, Any]:
    """Satu dokumen sumber satu lintasan — buku CAS: `processing` → state akhir; `error` / basi boleh diambil ulang."""
    key = digest(['gate_txn', pid, ref['source_type'], ref['source_id']])
    coll = collection(LEDGER)
    base = {'source_ref': ref, 'roll_ids': roll_ids}
    try:
        await coll.insert_one({'_id': key, 'state': 'processing', 'passage': pid, 'device_id': device['id'],
                               'warehouse_id': inp.get('warehouse_id'), 'direction': inp.get('direction'),
                               'local_passage_id': inp.get('local_passage_id'), **base, 'started_at': now(),
                               'attempts': 1})
    except DuplicateKeyError:
        stale = (datetime.now(timezone.utc) - timedelta(seconds=STALE_S)).isoformat().replace('+00:00', 'Z')
        row = await coll.find_one_and_update(
            {'_id': key, '$or': [{'state': 'error'}, {'state': 'processing', 'started_at': {'$lt': stale}}]},
            {'$set': {'state': 'processing', 'started_at': now()}, '$inc': {'attempts': 1}})
        if not row:
            cur = await coll.find_one({'_id': key}, {'_id': 0, 'summary': 1, 'state': 1})
            return {**base, **((cur or {}).get('summary') or {'state': (cur or {}).get('state', 'processing')})}
    try:
        summary = await _apply(ref, pid, inp, device, roll_ids)
    except Exception as exc:  # noqa: BLE001 — dicatat & bisa diulang dari antrean periksa
        logger.warning('[gate_txn] %s %s gagal: %s', ref['source_type'], ref['source_id'], exc)
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        msg = (detail.get('message') if isinstance(detail, dict) else str(detail))[:300]
        summary = {'state': 'error', 'kind': 'none', 'message': msg,
                   'problems': [{'roll_id': r, 'code': 'TXN_FAILED', 'message': msg} for r in roll_ids]}
    await coll.update_one({'_id': key}, {'$set': {'state': summary['state'], 'summary': summary, 'finished_at': now()}})
    return {**base, **summary}


async def after_decision(device: Dict[str, Any], pid: str, inp: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [await process_source(device, pid, inp, s['source_ref'], s['roll_ids']) for s in inp.get('sources') or []]


async def post_close(device: Dict[str, Any], pid: str, *, force: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Transaksi + antrean periksa untuk lintasan final. Idempoten; `force` = ulangi sumber yang `error`."""
    passages = collection('rfid_v2_passages')
    row = await passages.find_one({'_id': pid}, {'events': 0, 'close_body': 0})
    if not row or not row.get('decision') or not row.get('gate_txn_input'):
        return None
    if row.get('gate_txn_state') == 'done' and not force:
        return row.get('gate_txn') or []
    inp = {**row['gate_txn_input'], 'simulated': bool(row.get('simulated'))}
    results: List[Dict[str, Any]] = []
    try:
        results = await after_decision(device, pid, inp)
        from services import gate_review_service as review
        await review.sync_passage(device, row, results)
        state = 'error' if any(r.get('state') == 'error' for r in results) else 'done'
    except Exception as exc:  # noqa: BLE001 — ACK lintasan ke reader tidak boleh gagal karena kait D2
        logger.warning('[gate_txn] post_close %s gagal: %s', pid, exc)
        state = 'error'
    await passages.update_one({'_id': pid}, {'$set': {'gate_txn_state': state, 'gate_txn': results,
                                                      'gate_txn_at': now()}})
    return results


# ─── Penutupan sesi dokumen di titik siklus hidup (K-RFID-10) ─────────────────────────────
SYSTEM_ACTOR = {'id': 'system', 'name': 'Sistem (penutupan otomatis)'}


async def _doc_context(source_type: str, source_id: str, direction: str):
    """(dokumen, source_ref, gudang gate, [roll_id]) dari dokumen bisnis apa pun statusnya."""
    if source_type == 'putaway':
        d = await db.putaway_orders.find_one({'id': source_id}, {'_id': 0})
        if not d:
            return None
        wh = d.get('to_warehouse_id' if direction == 'in' else 'from_warehouse_id')
        return d, {'source_type': 'putaway', 'source_id': source_id, 'display_ref': d.get('pa_number') or source_id}, \
            wh, [i['roll_id'] for i in d.get('items') or [] if i.get('roll_id')]
    if source_type == 'wh_transfer':
        d = await db.warehouse_transfers.find_one({'id': source_id}, {'_id': 0})
        if not d or d.get('transfer_kind') == 'inter_entity':
            return None
        wh = d.get('dest_warehouse_id' if direction == 'in' else 'source_warehouse_id')
        ids = [x['roll_id'] for it in d.get('items') or [] for x in it.get('rolls') or [] if x.get('roll_id')]
        return d, {'source_type': 'wh_transfer', 'source_id': source_id, 'display_ref': d.get('code') or source_id}, wh, ids
    if source_type == 'shipment':
        d = await db.shipments.find_one({'id': source_id}, {'_id': 0})
        if not d:
            return None
        ids = [r['roll_id'] for r in d.get('rolls') or [] if r.get('roll_id')]
        return d, {'source_type': 'shipment', 'source_id': source_id, 'display_ref': d.get('shipment_no') or source_id}, \
            d.get('warehouse_id'), ids
    return None   # Makloon/Perbaikan: isi diambil dari jejak sesi gate (lihat `close_from_record`)


async def _completed(source_type: str, doc: Dict[str, Any], direction: str, roll_ids: List[str]) -> Dict[str, str]:
    """Roll yang dilengkapi JALUR LAIN (handheld / keputusan dokumen) → bukan "kurang" saat sesi ditutup."""
    out: Dict[str, str] = {}
    if source_type == 'putaway':
        for i in doc.get('items') or []:
            if i.get('status') == 'arrived':
                out[i['roll_id']] = 'gate' if i.get('arrived_via') == 'gate' else 'handheld'
            elif i.get('status') == 'returned_transit':
                out[i['roll_id']] = 'returned'
    elif source_type == 'wh_transfer':
        rows = await db.inventory_rolls.find({'id': {'$in': roll_ids}}, {'_id': 0, 'id': 1, 'last_transfer': 1,
                                                                         'returned_from_transfer': 1}).to_list(len(roll_ids) + 1)
        for r in rows:
            if (r.get('returned_from_transfer') or {}).get('ref_id') == doc['id']:
                out[r['id']] = 'returned'
            elif direction == 'in' and (r.get('last_transfer') or {}).get('ref_id') == doc['id']:
                out[r['id']] = 'handheld'
    elif source_type == 'shipment':
        so = await db.sales_orders.find_one({'id': doc.get('order_id')}, {'_id': 0, 'loading_checks': 1, 'loading_check': 1})
        lc = ((so or {}).get('loading_checks') or {}).get(doc.get('warehouse_id')) or (so or {}).get('loading_check') or {}
        if lc.get('result') in ('clean', 'override', 'simulated'):
            checked = {m.get('roll_id') for m in lc.get('manifest') or []}
            out.update({r: 'loading_check' for r in roll_ids if r in checked})
    return out


async def close_document_session(source_type: str, source_id: str, direction: str, trigger: str,
                                 actor: Optional[Dict[str, Any]] = None, note: str = '') -> Optional[Dict[str, Any]]:
    """Tutup sesi dokumen gate (otomatis atau manual). None bila gedung tidak bergate & dokumen tak pernah lewat gate."""
    from services import rfid_v2_sessions as sessions
    ctx = await _doc_context(source_type, source_id, direction)
    record = await collection(sessions.SESSIONS).find_one(
        {'_id': sessions.session_id(source_type, source_id, direction)}, {'_id': 0, 'roll_ids': 1, 'warehouse_id': 1,
                                                                          'source_ref': 1, 'close': 1})
    if ctx is None:
        if not record:
            return None
        doc, ref, wh, ids = None, record['source_ref'], record.get('warehouse_id'), record.get('roll_ids') or []
    else:
        doc, ref, wh, ids = ctx
    if not wh or not ids:
        return None
    if not record and not await gate_validates(wh, direction):
        return None   # gedung handheld & dokumen tak pernah lewat gate V2 → tidak ada sesi yang perlu dinilai
    completed = await _completed(source_type, doc, direction, ids) if doc else {}
    st = await sessions.close_session(ref, direction, wh, actor or SYSTEM_ACTOR, note, roll_ids=ids,
                                      completed=completed, trigger=trigger)
    if st.get('closed_now') and (st.get('close') or {}).get('verdict') == 'REVIEW':
        from services import gate_review_service as review
        await review.open_rolls_missing(st, gate_mode=await gate_validates(wh, direction))
    return st


async def safe_close(source_type: str, source_id: str, directions: Tuple[str, ...], trigger: str) -> None:
    """Kait siklus hidup (PA/transfer/SJ/…): best-effort — tidak pernah menggagalkan alur bisnis pemanggil."""
    for direction in directions:
        try:
            await close_document_session(source_type, source_id, direction, trigger)
        except Exception as exc:  # noqa: BLE001
            logger.warning('[gate_txn] tutup sesi %s %s %s gagal diabaikan: %s', source_type, source_id, direction, exc)
