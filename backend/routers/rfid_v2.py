"""U300 transport (device key) dan operasi ERP bercakupan. Device key tidak bisa mengakui alarm/ekspor bukti.

Endpoint device: autentikasi `X-Device-Key` (`_device`) dengan galat terstruktur `detail.code` (AUD-MW-06):
AUTH_REQUIRED / AUTH_INVALID (401), ADMIN_DISABLED (403, bukan permanen), READER_REQUIRED (403).
Operasi pengguna: `require_permission(wms, view|scan)` + cakupan gudang & entitas dokumen (`_operator_device`).
Operasi PREP-D1 tambahan (sesi dokumen, protokol, parameter, simulator, kesehatan, kunci gate) di `rfid_v2_ops`.
"""
import json

from fastapi import APIRouter, HTTPException, Query, Request, Response

from db import db
from dependencies import require_permission, require_role
from entity_scope import assert_entity_access, entity_ctx, resolve_list_scope
from services import rfid_v2_health as health
from services import rfid_v2_latch as latch
from services import rfid_v2_service as service
from services import rfid_v2_sources as sources
from services.rfid_ingest_service import authenticate

router = APIRouter(prefix='/api')
SOURCE_COLLECTIONS = sources.SOURCE_COLLECTIONS


async def _binding_access(binding, ctx):
    if not binding:
        return
    for entry in service.binding_sources(binding):
        name, doc = await sources.source_document(entry['source_ref'])
        if not doc:
            service.fail(404, 'SOURCE_NOT_FOUND', 'Dokumen sumber tidak tersedia untuk pemeriksaan akses.')
        assert_entity_access(doc, name, ctx)


async def _decision_access(decision, ctx):
    for ref in (decision or {}).get('sources') or []:
        name, doc = await sources.source_document(ref)
        if doc:
            assert_entity_access(doc, name, ctx)


async def _visible(rows, ctx, passage_rows=False):
    visible = []
    for row in rows:
        try:
            await _binding_access(row.get('binding') if passage_rows else row, ctx)
            if passage_rows:
                await _decision_access(row.get('decision'), ctx)
            visible.append(row)
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
    return visible


async def _payload(request):
    raw = bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw) > 1_000_000:
            service.fail(413, 'BODY_TOO_LARGE', 'Request maksimal 1 MB.')
    try:
        return json.loads(raw, parse_constant=lambda _: service.fail(400, 'INVALID_JSON', 'Angka tidak valid.'))
    except (ValueError, UnicodeDecodeError):
        service.fail(400, 'INVALID_JSON', 'JSON tidak valid.')


async def _device(request):
    key = request.headers.get('X-Device-Key')
    if not key:
        service.fail(401, 'AUTH_REQUIRED', 'Header X-Device-Key wajib.')
    try:
        dev = await authenticate(key)
    except HTTPException as exc:
        if exc.status_code == 403:
            service.fail(403, 'ADMIN_DISABLED', 'Perangkat dinonaktifkan admin ERP — tunggu diaktifkan lagi.',
                         retryable=True, details={'poll_after_seconds': 60})
        service.fail(401, 'AUTH_INVALID', 'Device key tidak dikenal atau sudah dirotasi.')
    if dev.get('type') not in ('gate', 'fixed_reader'):
        service.fail(403, 'READER_REQUIRED', 'Endpoint hanya untuk reader/gate.')
    return dev


async def _operator_device(request, device_id, write=False):
    actor = await require_permission(request, 'wms', 'scan' if write else 'view')
    dev = await db.rfid_devices.find_one({'id': device_id}, {'_id': 0, 'api_key_hash': 0, 'api_key': 0})
    if not dev:
        service.fail(404, 'DEVICE_NOT_FOUND', 'Perangkat tidak ditemukan.')
    ctx = await entity_ctx(request)
    # Registry cakupan memuat field gudang/lokasi inventory_rolls.
    assert_entity_access({'warehouse_id': dev.get('warehouse_id')}, 'inventory_rolls', ctx)
    from services.warehouse_scope_service import assert_usable
    await assert_usable(dev['warehouse_id'], ctx.active_entity_id, action='mengoperasikan reader')
    return actor, dev, ctx


@router.get('/rfid/v2/device/config')
async def get_config(request: Request):
    return await service.config(await _device(request))


@router.post('/rfid/v2/events')
async def post_events(request: Request):
    dev = await _device(request)
    return await service.events(dev, await _payload(request))


@router.post('/rfid/v2/device/telemetry')
async def post_telemetry(request: Request):
    dev = await _device(request)
    return await service.telemetry(dev, await _payload(request))


@router.get('/rfid/v2/device/gate-state')
async def get_state(request: Request, logical_gate_id: str, local_passage_id: str = None):
    return await service.gate_state(await _device(request), logical_gate_id, local_passage_id)


@router.post('/rfid/v2/passages/{passage_id}/close')
async def post_close(passage_id: str, request: Request):
    dev = await _device(request)
    return await service.close(dev, passage_id, await _payload(request), request.headers.get('Idempotency-Key'))


@router.put('/rfid/v2/ops/devices/{device_id}/config')
async def put_config(device_id: str, request: Request):
    await require_role(request, ['admin'])  # kebijakan perangkat/key infrastruktur yang ada
    actor, dev, _ = await _operator_device(request, device_id, True)
    return await service.publish_config(dev, await _payload(request), actor)


@router.post('/rfid/v2/ops/devices/{device_id}/manifest')
async def bind_manifest(device_id: str, request: Request):
    actor, dev, ctx = await _operator_device(request, device_id, True)
    body = await _payload(request)
    if not isinstance(body, dict) or not all(isinstance(body.get(k), str) for k in ('direction', 'logical_gate_id')):
        service.fail(400, 'INVALID_BINDING', 'Pilih gate, arah, jenis dokumen, dan ID dokumen.')
    selected = body.get('sources', [body])
    service.validate_sources(selected)
    for source in selected:
        name, doc = await sources.source_document(source)
        if not doc:
            service.fail(404, 'SOURCE_NOT_FOUND', 'Dokumen tidak ditemukan.')
        assert_entity_access(doc, name, ctx)
    return await service.bind_manifests(dev, body['logical_gate_id'], selected, body['direction'], actor)


@router.delete('/rfid/v2/ops/devices/{device_id}/manifest')
async def release_manifest(device_id: str, request: Request, logical_gate_id: str):
    actor, dev, _ = await _operator_device(request, device_id, True)
    return await service.release_binding(dev, logical_gate_id, actor)


@router.get('/rfid/v2/ops/devices/{device_id}')
async def overview(device_id: str, request: Request, cursor: str = None, limit: int = Query(50, ge=1, le=100)):
    _, dev, ctx = await _operator_device(request, device_id)
    rows, next_cursor = await service.history(device_id, cursor, limit)
    rows = await _visible(rows, ctx, passage_rows=True)
    bindings = await service.collection('rfid_v2_bindings').find(
        {'device_id': device_id, 'released_at': None}, {'_id': 0}).to_list(10)
    bindings = await _visible(bindings, ctx)
    cfg = await service.config(dev) if dev.get('v2_config_version') else None
    gate_id = cfg['logical_gates'][0]['logical_gate_id'] if cfg and cfg.get('logical_gates') else None
    gate_latch = await latch.active(device_id, gate_id) if gate_id else None
    params = service.gate_params(cfg['logical_gates'][0]) if gate_id else None
    return {'device_id': device_id, 'protocol': dev.get('protocol') or 'legacy', 'contract_version': service.CONTRACT_VERSION,
            'config_version': dev.get('v2_config_version'), 'config': cfg, 'gate_parameters': params,
            'telemetry': dev.get('v2_telemetry'), 'telemetry_at': dev.get('v2_telemetry_at'),
            'transport': dev.get('v2_transport'), 'last_heartbeat': dev.get('last_heartbeat'),
            'health': await health.check_device(dev) if dev.get('v2_config_version') else [],
            'gate_latch': gate_latch, 'bindings': bindings,
            'sessions': await _visible_sessions(await service.device_sessions(dev, cfg), ctx) if cfg else [],
            'passages': rows, 'next_cursor': next_cursor}


async def _visible_sessions(rows, ctx):
    out = []
    for row in rows:
        try:
            name, doc = await sources.source_document(row['source_ref'])
            if doc:
                assert_entity_access(doc, name, ctx)
            out.append(row)
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
    return out


@router.get('/rfid/v2/ops/devices/{device_id}/passages/{passage_id}/evidence')
async def evidence(device_id: str, passage_id: str, request: Request):
    _, dev, ctx = await _operator_device(request, device_id)
    document = await service.evidence_document(dev, passage_id)
    await _binding_access(document['passage'].get('binding'), ctx)
    await _decision_access(document['passage'].get('decision'), ctx)
    filename = 'u300-evidence-' + service.digest([dev['id'], passage_id])[:16] + '.json'
    return Response(json.dumps(document, ensure_ascii=False, indent=2), media_type='application/json', headers={
        'Content-Disposition': f'attachment; filename="{filename}"', 'Cache-Control': 'no-store'})


@router.get('/rfid/v2/ops/devices/{device_id}/sources')
async def list_sources(device_id: str, request: Request, source_type: str, direction: str):
    _, dev, ctx = await _operator_device(request, device_id)
    if direction not in ('in', 'out'):
        service.fail(400, 'DIRECTION_REQUIRED', 'Pilih arah masuk atau keluar.')
    rows = await sources.candidates(source_type, direction, dev['warehouse_id'],
                                    lambda name, query: resolve_list_scope(name, query, ctx))
    return {'sources': rows, 'limit': 200}


@router.post('/rfid/v2/passages/{passage_id}/acknowledge')
async def acknowledge(passage_id: str, request: Request):
    # Wajib sesi pengguna walau device key valid ikut dikirim.
    body = await _payload(request)
    if not isinstance(body, dict) or not isinstance(body.get('device_id'), str):
        service.fail(400, 'DEVICE_REQUIRED', 'Pilih perangkat dari meja gate.')
    actor, dev, ctx = await _operator_device(request, body['device_id'], True)
    row = await service.collection('rfid_v2_passages').find_one(
        {'_id': service.digest([dev['id'], passage_id])}, {'binding': 1, 'decision': 1})
    if row:
        await _binding_access(row.get('binding'), ctx)
        await _decision_access(row.get('decision'), ctx)
        if (row.get('decision') or {}).get('verdict') == 'RED':
            # PREP-D2 (AUD-MW-10) — lintasan merah anggota kunci gate: pengakuan melepas kunci → `wms.approve`.
            await require_permission(request, 'wms', 'approve')
    return await service.acknowledge(dev, passage_id, body.get('note'), actor,
                                     body.get('latch_id'), body.get('decision_id'))
