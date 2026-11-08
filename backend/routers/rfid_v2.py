"""U300 transport and scoped ERP operations. Device keys cannot acknowledge alarms."""
import json
from fastapi import APIRouter, Request, Query, HTTPException, Response
from db import db
from dependencies import require_permission, require_role
from entity_scope import entity_ctx, assert_entity_access, resolve_list_scope
from services import rfid_v2_service as service
from services.rfid_ingest_service import authenticate

router = APIRouter(prefix='/api/rfid/v2')
SOURCE_COLLECTIONS = {'shipment': 'shipments', 'wh_transfer': 'warehouse_transfers', 'putaway': 'putaway_orders'}


async def binding_access(binding, ctx):
    if not binding:
        return
    for entry in service.binding_sources(binding):
        ref = entry['source_ref']
        name = SOURCE_COLLECTIONS.get(ref['source_type'])
        doc = await db[name].find_one({'id': ref['source_id']}) if name else None
        if not doc:
            service.fail(404, 'SOURCE_NOT_FOUND', 'Dokumen sumber tidak tersedia untuk pemeriksaan akses.')
        assert_entity_access(doc, name, ctx)


async def visible_bindings(rows, ctx, passage_rows=False):
    visible = []
    for row in rows:
        try:
            await binding_access(row.get('binding') if passage_rows else row, ctx)
            visible.append(row)
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
    return visible


async def payload(request):
    raw = bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw) > 1_000_000:
            service.fail(413, 'BODY_TOO_LARGE', 'Request maksimal 1 MB.')
    try:
        return json.loads(raw, parse_constant=lambda _: service.fail(400, 'INVALID_JSON', 'Angka tidak valid.'))
    except (ValueError, UnicodeDecodeError):
        service.fail(400, 'INVALID_JSON', 'JSON tidak valid.')


async def device(request):
    dev = await authenticate(request.headers.get('X-Device-Key'))
    if dev.get('type') not in ('gate', 'fixed_reader'):
        service.fail(403, 'READER_REQUIRED', 'Endpoint hanya untuk reader/gate.')
    return dev


async def operator_device(request, device_id, write=False):
    actor = await require_permission(request, 'wms', 'scan' if write else 'view')
    dev = await db.rfid_devices.find_one({'id': device_id}, {'_id': 0})
    if not dev:
        service.fail(404, 'DEVICE_NOT_FOUND', 'Perangkat tidak ditemukan.')
    ctx = await entity_ctx(request)
    # Existing scope registry includes inventory_rolls' warehouse/location field.
    assert_entity_access({'warehouse_id': dev.get('warehouse_id')}, 'inventory_rolls', ctx)
    from services.warehouse_scope_service import assert_usable
    await assert_usable(dev['warehouse_id'], ctx.active_entity_id, action='mengoperasikan reader')
    return actor, dev, ctx


@router.get('/device/config')
async def get_config(request: Request):
    return await service.config(await device(request))


@router.post('/events')
async def post_events(request: Request):
    dev = await device(request)
    return await service.events(dev, await payload(request))


@router.post('/device/telemetry')
async def post_telemetry(request: Request):
    dev = await device(request)
    return await service.telemetry(dev, await payload(request))


@router.get('/device/gate-state')
async def get_state(request: Request, logical_gate_id: str, local_passage_id: str = None):
    return await service.gate_state(await device(request), logical_gate_id, local_passage_id)


@router.post('/passages/{passage_id}/close')
async def post_close(passage_id: str, request: Request):
    dev = await device(request)
    return await service.close(dev, passage_id, await payload(request), request.headers.get('Idempotency-Key'))


@router.put('/ops/devices/{device_id}/config')
async def put_config(device_id: str, request: Request):
    await require_role(request, ['admin'])  # Existing infrastructure device/key policy.
    actor, dev, _ = await operator_device(request, device_id, True)
    return await service.publish_config(dev, await payload(request), actor)


@router.post('/ops/devices/{device_id}/manifest')
async def bind_manifest(device_id: str, request: Request):
    actor, dev, ctx = await operator_device(request, device_id, True)
    body = await payload(request)
    if not isinstance(body, dict) or not all(isinstance(body.get(k), str) for k in ('direction', 'logical_gate_id')):
        service.fail(400, 'INVALID_BINDING', 'Pilih gate, arah, jenis dokumen, dan ID dokumen.')
    selected = body.get('sources', [body])
    service.validate_sources(selected)
    names = {'shipment': 'shipments', 'wh_transfer': 'warehouse_transfers', 'putaway': 'putaway_orders'}
    for source in selected:
        name = names[source['source_type']]
        doc = await db[name].find_one({'id': source['source_id']})
        if not doc:
            service.fail(404, 'SOURCE_NOT_FOUND', 'Dokumen tidak ditemukan.')
        assert_entity_access(doc, name, ctx)
    return await service.bind_manifests(dev, body['logical_gate_id'], selected, body['direction'], actor)


@router.get('/ops/devices/{device_id}')
async def overview(device_id: str, request: Request, cursor: str = None, limit: int = Query(50, ge=1, le=100)):
    _, dev, ctx = await operator_device(request, device_id)
    rows, next_cursor = await service.history(device_id, cursor, limit)
    rows = await visible_bindings(rows, ctx, passage_rows=True)
    bindings = await service.collection('rfid_v2_bindings').find({'device_id': device_id}, {'_id': 0}).to_list(10)
    bindings = await visible_bindings(bindings, ctx)
    cfg = await service.config(dev) if dev.get('v2_config_version') else None
    return {'device_id': device_id, 'config_version': dev.get('v2_config_version'), 'config': cfg,
            'telemetry': dev.get('v2_telemetry'), 'last_heartbeat': dev.get('last_heartbeat'),
            'bindings': bindings, 'passages': rows, 'next_cursor': next_cursor}


@router.get('/ops/devices/{device_id}/passages/{passage_id}/evidence')
async def evidence(device_id: str, passage_id: str, request: Request):
    _, dev, ctx = await operator_device(request, device_id)
    row = await service.collection('rfid_v2_passages').find_one({'_id': service.digest([dev['id'], passage_id])})
    if not row:
        service.fail(404, 'PASSAGE_NOT_FOUND', 'Lintasan tidak ditemukan pada perangkat ini.')
    await binding_access(row.get('binding'), ctx)
    filename = 'u300-evidence-' + row.pop('_id')[:16] + '.json'
    row.pop('close_key', None)
    row.pop('close_hash', None)
    if row.get('binding'):
        row['binding'].pop('_id', None)
    row['events'] = sorted(row['events'].values(), key=lambda e: (e['received_at'], e['event']['event_id']))
    document = {'schema_version': 1, 'exported_at': service.now(), 'read_only_snapshot': True, 'passage': row}
    return Response(json.dumps(document, ensure_ascii=False, indent=2), media_type='application/json', headers={
        'Content-Disposition': f'attachment; filename="{filename}"', 'Cache-Control': 'no-store'})


@router.get('/ops/devices/{device_id}/sources')
async def sources(device_id: str, request: Request, source_type: str, direction: str):
    _, dev, ctx = await operator_device(request, device_id)
    if direction not in ('in', 'out'):
        service.fail(400, 'DIRECTION_REQUIRED', 'Pilih arah masuk atau keluar.')
    wh = dev['warehouse_id']
    if source_type == 'shipment':
        if direction != 'out':
            return {'sources': []}
        name, query, fields = 'shipments', {'warehouse_id': wh, 'status': {'$in': list(service.gate_evaluator.SHIPMENT_ACTIVE)}}, {'id': 1, 'shipment_no': 1, 'status': 1}
    elif source_type == 'wh_transfer':
        name, query, fields = 'warehouse_transfers', {('source_warehouse_id' if direction == 'out' else 'dest_warehouse_id'): wh, 'status': 'dispatched', 'transfer_kind': {'$ne': 'inter_entity'}}, {'id': 1, 'code': 1, 'status': 1}
    elif source_type == 'putaway':
        name, query, fields = 'putaway_orders', {('from_warehouse_id' if direction == 'out' else 'to_warehouse_id'): wh, 'status': 'in_transit'}, {'id': 1, 'pa_number': 1, 'status': 1}
    else:
        service.fail(400, 'SOURCE_UNSUPPORTED', 'Jenis dokumen tidak didukung.')
    rows = await db[name].find(resolve_list_scope(name, query, ctx), {'_id': 0, **fields}).sort('created_at', -1).to_list(200)
    return {'sources': [{'id': r['id'], 'label': r.get('shipment_no') or r.get('code') or r.get('pa_number') or r['id'], 'status': r['status']} for r in rows], 'limit': 200}


@router.post('/passages/{passage_id}/acknowledge')
async def acknowledge(passage_id: str, request: Request):
    # Requires a user session even if a valid device key was supplied.
    body = await payload(request)
    if not isinstance(body, dict) or not isinstance(body.get('device_id'), str):
        service.fail(400, 'DEVICE_REQUIRED', 'Pilih perangkat dari meja gate.')
    actor, dev, ctx = await operator_device(request, body['device_id'], True)
    row = await service.collection('rfid_v2_passages').find_one({'_id': service.digest([dev['id'], passage_id])})
    if row:
        await binding_access(row.get('binding'), ctx)
    return await service.acknowledge(dev, passage_id, body.get('note'), actor)
