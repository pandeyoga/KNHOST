"""PREP-D1 — sumber dokumen gate V2: manifest dari dokumen bisnis (bukan dari klien) + auto-cocok (AUD-MW-15).

Jenis sumber: surat jalan (`shipment`), transfer fisik (`wh_transfer`), putaway (`putaway`) dari patch Kubus, ditambah
P18: Order Makloon (`makloon_order`, `source_id` = `issue_ref` langkah, `doc_id` = id MKO; hanya keluar) dan Perbaikan
(`repair_order`; keluar saat terkirim, masuk saat kembali ke gudang asal). Identitas sumber sama persis dengan
`gate_evaluator.resolve_movement` sehingga `expected_source` & klaim crossing konsisten.
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from db import db
from services import gate_evaluator
from services.rfid_v2_common import fail

SOURCE_TYPES = ('shipment', 'wh_transfer', 'putaway', 'makloon_order', 'repair_order')
SOURCE_COLLECTIONS = {'shipment': 'shipments', 'wh_transfer': 'warehouse_transfers', 'putaway': 'putaway_orders',
                      'makloon_order': 'makloon_orders', 'repair_order': 'repair_orders'}
SOURCE_LABEL = {'shipment': 'Surat jalan', 'wh_transfer': 'Transfer gudang', 'putaway': 'Putaway',
                'makloon_order': 'Order Makloon', 'repair_order': 'Perbaikan'}
DEAD = {'cancelled', 'void', 'rejected'}
MAX_ROLLS = 2000


def _inactive(message: str):
    fail(409, 'SOURCE_NOT_ACTIVE', message)


async def _makloon(sid: str, warehouse: str, direction: str):
    order = await db.makloon_orders.find_one({'steps.issue_ref': sid}, {'_id': 0, 'id': 1, 'mko_number': 1,
                                                                       'status': 1, 'steps': 1})
    step = next((s for s in (order or {}).get('steps') or [] if s.get('issue_ref') == sid), None)
    if not order or not step or direction != 'out' or order.get('status') == 'cancelled' \
            or step.get('status') != 'issued' or (step.get('from_warehouse_id') or warehouse) != warehouse:
        _inactive('Langkah Order Makloon belum dikirim / bukan gate keluar gudang ini.')
    rows = await db.inventory_rolls.find({'bucket_ref.id': sid, 'status': 'subcon'}, {'_id': 0, 'id': 1}) \
        .to_list(MAX_ROLLS + 1)
    label = f"{order.get('mko_number') or order['id']} langkah {step.get('seq') or '?'}"
    return [r['id'] for r in rows], label, order['id']


async def _repair(sid: str, warehouse: str, direction: str):
    ro = await db.repair_orders.find_one({'id': sid}, {'_id': 0, 'id': 1, 'number': 1, 'status': 1, 'lines': 1})
    if not ro or ro.get('status') != 'sent':
        _inactive('Perbaikan belum dikirim / sudah selesai.')
    lines = [ln for ln in ro.get('lines') or [] if ln.get('roll_id')]
    missing_wh = [ln['roll_id'] for ln in lines if not ln.get('warehouse_id')]
    wh_of = {r['id']: r.get('warehouse_id') for r in await db.inventory_rolls.find(
        {'id': {'$in': missing_wh}}, {'_id': 0, 'id': 1, 'warehouse_id': 1}).to_list(MAX_ROLLS + 1)} if missing_wh else {}
    ids = [ln['roll_id'] for ln in lines if (ln.get('warehouse_id') or wh_of.get(ln['roll_id'])) == warehouse]
    if not ids:
        _inactive('Perbaikan ini tidak berasal dari / kembali ke gudang gate ini.')
    return ids, ro.get('number') or ro['id'], ro['id']


async def manifest(source: Dict[str, Any], warehouse: str, direction: str) -> Tuple[Dict[str, Any], List[str]]:
    """Keanggotaan roll dibaca dari dokumen bisnis — tidak pernah dari daftar roll kiriman klien."""
    typ, sid = source['source_type'], source['source_id']
    doc_id = None
    if typ == 'shipment':
        doc = await db.shipments.find_one({'id': sid})
        if not doc or direction != 'out' or doc.get('warehouse_id') != warehouse \
                or doc.get('status') not in gate_evaluator.SHIPMENT_ACTIVE:
            _inactive('Surat jalan tidak aktif / bukan gate keluar gudang ini.')
        so = await db.sales_orders.find_one({'id': doc.get('order_id')})
        if not so or so.get('status') in gate_evaluator.SO_DEAD:
            fail(409, 'SO_NOT_ACTIVE', 'SO tidak ditemukan atau dibatalkan.')
        ids = [r.get('roll_id') for r in doc.get('rolls', [])]
        label = doc.get('shipment_no', sid)
    elif typ == 'wh_transfer':
        doc = await db.warehouse_transfers.find_one({'id': sid})
        field = 'source_warehouse_id' if direction == 'out' else 'dest_warehouse_id'
        if not doc or doc.get(field) != warehouse or doc.get('status') != 'dispatched' \
                or doc.get('transfer_kind') == 'inter_entity':
            _inactive('Transfer belum dikirim / gudang tidak sesuai.')
        ids = [r.get('roll_id') for i in doc.get('items', []) for r in i.get('rolls', [])]
        label = doc.get('code', sid)
    elif typ == 'putaway':
        doc = await db.putaway_orders.find_one({'id': sid})
        field = 'from_warehouse_id' if direction == 'out' else 'to_warehouse_id'
        if not doc or doc.get(field) != warehouse or doc.get('status') != 'in_transit':
            _inactive('Putaway belum dikirim / gudang tidak sesuai.')
        ids = [i.get('roll_id') for i in doc.get('items', [])]
        label = doc.get('pa_number', sid)
    elif typ == 'makloon_order':
        ids, label, doc_id = await _makloon(sid, warehouse, direction)
    elif typ == 'repair_order':
        ids, label, doc_id = await _repair(sid, warehouse, direction)
    else:
        fail(400, 'SOURCE_UNSUPPORTED', 'Gunakan surat jalan, transfer, putaway, Order Makloon, atau Perbaikan.')
    if not ids or any(not isinstance(r, str) or not r for r in ids) or len(ids) != len(set(ids)):
        fail(409, 'INVALID_MANIFEST', 'Manifest kosong, roll hilang, atau roll ganda; koreksi dokumen sumber.')
    if len(ids) > MAX_ROLLS:
        fail(409, 'MANIFEST_CAPACITY', f'Manifest melebihi kapasitas passage {MAX_ROLLS} roll.')
    ref = {'source_type': typ, 'source_id': sid, 'display_ref': label}
    if doc_id:
        ref['doc_id'] = doc_id
    return ref, sorted(ids)


async def source_document(source: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """(koleksi, dokumen induk) untuk pemeriksaan cakupan entitas."""
    typ = source.get('source_type')
    name = SOURCE_COLLECTIONS.get(typ)
    if not name:
        return '', None
    if typ == 'makloon_order':
        doc_id = source.get('doc_id') or str(source.get('source_id') or '').split(':')[0]
        return name, await db[name].find_one({'id': doc_id})
    return name, await db[name].find_one({'id': source.get('source_id')})


async def is_cancelled(source: Dict[str, Any]) -> bool:
    _, doc = await source_document(source)
    return bool(doc and str(doc.get('status') or '') in DEAD)


def validate_sources(sources: Any) -> None:
    if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
        fail(400, 'SOURCE_LIMIT', 'Pilih 1 sampai 20 dokumen dalam satu lintasan.')
    keys = set()
    for source in sources:
        if not isinstance(source, dict) or source.get('source_type') not in SOURCE_TYPES \
                or not isinstance(source.get('source_id'), str) or not 1 <= len(source['source_id']) <= 160:
            fail(400, 'INVALID_SOURCE', 'Jenis dan identitas dokumen tidak valid.')
        key = (source['source_type'], source['source_id'])
        if key in keys:
            fail(400, 'DUPLICATE_SOURCE', 'Dokumen yang sama hanya boleh dipilih sekali.')
        keys.add(key)
    if len(sources) > 1 and any(s['source_type'] != 'shipment' for s in sources):
        fail(400, 'GROUP_SHIPMENTS_ONLY', 'Gabungan lintasan saat ini untuk beberapa SJ; dokumen lain diproses per dokumen.')


def movement_source(mv: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Movement aktif roll (gate_evaluator) → identitas sumber V2, atau None."""
    if not mv or mv.get('missing'):
        return None
    typ = mv.get('type')
    if typ == 'sales_order':
        sid = (mv.get('shipment') or {}).get('id')
        return {'source_type': 'shipment', 'source_id': sid} if sid else None
    if typ in ('wh_transfer', 'putaway', 'repair_order') and mv.get('id'):
        return {'source_type': typ, 'source_id': mv['id']}
    if typ == 'makloon_order' and mv.get('id'):
        return {'source_type': 'makloon_order', 'source_id': mv['id'], 'doc_id': mv.get('doc_id')}
    return None


async def auto_sources(rolls: List[Dict[str, Any]], warehouse: str, direction: str) -> Dict[str, Any]:
    """AUD-MW-15 auto-cocok: dokumen aktif gudang/arah yang memuat roll kuat lintasan.

    Return {'entries': [{'source_ref','roll_ids'}], 'roll_sources': {roll_id: ref}, 'invalid': {roll_id: code}}.
    Roll tanpa movement / dengan dokumen yang tidak aktif untuk gate ini tidak dicocokkan — evaluator menilainya.
    """
    by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    pending: Dict[Tuple[str, str], List[str]] = {}
    for roll in rolls:
        src = movement_source(await gate_evaluator.resolve_movement(roll))
        if src:
            key = (src['source_type'], src['source_id'])
            by_key.setdefault(key, src)
            pending.setdefault(key, []).append(roll['id'])
    entries, roll_sources, invalid = [], {}, {}
    for key, src in list(by_key.items())[:20]:
        try:
            ref, ids = await manifest(src, warehouse, direction)
        except HTTPException as exc:
            code = exc.detail.get('code') if isinstance(exc.detail, dict) else 'SOURCE_NOT_ACTIVE'
            for rid in pending[key]:
                invalid[rid] = code
            continue
        entries.append({'source_ref': ref, 'roll_ids': ids})
        for rid in ids:
            roll_sources.setdefault(rid, ref)
    return {'entries': entries, 'roll_sources': roll_sources, 'invalid': invalid}


async def candidates(source_type: str, direction: str, warehouse: str, scope_query) -> List[Dict[str, Any]]:
    """Kandidat dokumen aktif untuk panel (maks 200). `scope_query(name, query)` menerapkan cakupan entitas."""
    if source_type == 'shipment':
        if direction != 'out':
            return []
        name, query, fields = 'shipments', {'warehouse_id': warehouse, 'status': {'$in': list(gate_evaluator.SHIPMENT_ACTIVE)}}, \
            {'id': 1, 'shipment_no': 1, 'status': 1}
    elif source_type == 'wh_transfer':
        name, query, fields = 'warehouse_transfers', {('source_warehouse_id' if direction == 'out' else 'dest_warehouse_id'): warehouse,
                                                      'status': 'dispatched', 'transfer_kind': {'$ne': 'inter_entity'}}, \
            {'id': 1, 'code': 1, 'status': 1}
    elif source_type == 'putaway':
        name, query, fields = 'putaway_orders', {('from_warehouse_id' if direction == 'out' else 'to_warehouse_id'): warehouse,
                                                 'status': 'in_transit'}, {'id': 1, 'pa_number': 1, 'status': 1}
    elif source_type == 'makloon_order':
        if direction != 'out':
            return []
        rows = await db.makloon_orders.find(scope_query('makloon_orders', {'status': {'$ne': 'cancelled'},
                                                                           'steps': {'$elemMatch': {'status': 'issued'}}}),
                                            {'_id': 0, 'id': 1, 'mko_number': 1, 'steps': 1}).sort('created_at', -1).to_list(200)
        out = []
        for r in rows:
            for s in r.get('steps') or []:
                if s.get('status') == 'issued' and s.get('issue_ref') and (s.get('from_warehouse_id') or warehouse) == warehouse:
                    out.append({'id': s['issue_ref'], 'label': f"{r.get('mko_number') or r['id']} langkah {s.get('seq') or '?'}",
                                'status': 'issued', 'doc_id': r['id']})
        return out[:200]
    elif source_type == 'repair_order':
        name, query, fields = 'repair_orders', {'status': 'sent', 'lines.warehouse_id': warehouse}, \
            {'id': 1, 'number': 1, 'status': 1}
    else:
        fail(400, 'SOURCE_UNSUPPORTED', 'Jenis dokumen tidak didukung.')
    rows = await db[name].find(scope_query(name, query), {'_id': 0, **fields}).sort('created_at', -1).to_list(200)
    return [{'id': r['id'], 'label': r.get('shipment_no') or r.get('code') or r.get('pa_number') or r.get('number') or r['id'],
             'status': r['status']} for r in rows]
