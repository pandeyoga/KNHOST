"""PREP-D1 — operasi gate V2 tambahan (sesi pengguna; device key TIDAK diterima).

Sesi dokumen bertahap (K-RFID-10), kunci gate (K-RFID-09), protokol perangkat (AUD-MW-09), parameter lintasan
berversi, kesehatan reader (AUD-MW-17), dan simulator lintasan tanpa perangkat (admin/dev).
PREP-D2: membuka kunci gate butuh `wms.approve`; tutup sesi manual = penilai penutupan otomatis (`gate_txn_service`).
"""
from fastapi import APIRouter, Request

from dependencies import audit, require_permission
from entity_scope import assert_entity_access, entity_ctx
from routers.rfid_v2 import _operator_device, _payload
from services import rfid_v2_health as health
from services import rfid_v2_latch as latch
from services import rfid_v2_params as params_mod
from services import rfid_v2_service as service
from services import rfid_v2_sessions as sessions
from services import rfid_v2_simulator as simulator
from services import rfid_v2_sources as sources

router = APIRouter(prefix='/api')


async def _scoped(request, device_id, write=False):
    """Izin WMS + cakupan gudang/entitas perangkat (logika bersama `rfid_v2._operator_device`)."""
    await require_permission(request, 'wms', 'scan' if write else 'view')
    return await _operator_device(request, device_id, write)


async def _source_scope(request, source_type, source_id):
    ctx = await entity_ctx(request)
    if source_type not in sources.SOURCE_TYPES:
        service.fail(400, 'SOURCE_UNSUPPORTED', 'Jenis dokumen tidak didukung.')
    ref = {'source_type': source_type, 'source_id': source_id}
    name, doc = await sources.source_document(ref)
    if not doc:
        service.fail(404, 'SOURCE_NOT_FOUND', 'Dokumen tidak ditemukan.')
    assert_entity_access(doc, name, ctx)
    return ref, doc


def _warehouse_of(source_type, doc, direction):
    if source_type == 'shipment':
        return doc.get('warehouse_id')
    if source_type == 'wh_transfer':
        return doc.get('source_warehouse_id' if direction == 'out' else 'dest_warehouse_id')
    if source_type == 'putaway':
        return doc.get('from_warehouse_id' if direction == 'out' else 'to_warehouse_id')
    if source_type == 'repair_order':
        return next((ln.get('warehouse_id') for ln in doc.get('lines') or [] if ln.get('warehouse_id')), None)
    if source_type == 'makloon_order':
        return next((s.get('from_warehouse_id') for s in doc.get('steps') or [] if s.get('from_warehouse_id')), None)
    return None


@router.get('/rfid/v2/ops/devices/{device_id}/sessions')
async def device_sessions(device_id: str, request: Request):
    _, dev, _ = await _scoped(request, device_id)
    if not dev.get('v2_config_version'):
        return {'sessions': []}
    return {'sessions': await service.device_sessions(dev, await service.config(dev))}


@router.get('/rfid/v2/ops/doc-sessions/{source_type}/{source_id}')
async def doc_session(source_type: str, source_id: str, request: Request, direction: str = 'out'):
    await require_permission(request, 'wms', 'view')
    if direction not in ('in', 'out'):
        service.fail(400, 'DIRECTION_REQUIRED', 'Arah wajib in/out.')
    ref, doc = await _source_scope(request, source_type, source_id)
    return await sessions.status(ref, direction, _warehouse_of(source_type, doc, direction))


@router.post('/rfid/v2/ops/doc-sessions/{source_type}/{source_id}/close')
async def close_doc_session(source_type: str, source_id: str, request: Request):
    actor = await require_permission(request, 'wms', 'scan')
    body = await _payload(request)
    direction = (body or {}).get('direction', 'out')
    if direction not in ('in', 'out'):
        service.fail(400, 'DIRECTION_REQUIRED', 'Arah wajib in/out.')
    ref, doc = await _source_scope(request, source_type, source_id)
    # PREP-D2 — penutupan manual memakai penilai yang sama dengan penutupan otomatis siklus hidup (handheld melengkapi)
    from services import gate_txn_service as gate_txn
    out = await gate_txn.close_document_session(source_type, source_id, direction, 'manual', actor,
                                                str((body or {}).get('note') or ''))
    if out is None:
        out = await sessions.close_session(ref, direction, _warehouse_of(source_type, doc, direction), actor,
                                           str((body or {}).get('note') or ''))
    await audit(actor['name'], 'rfid_v2_doc_session_closed', source_type, source_id,
                {'direction': direction, 'missing': (out.get('close') or {}).get('missing_count')})
    return out


@router.post('/rfid/v2/ops/devices/{device_id}/gate-latch/acknowledge')
async def acknowledge_latch(device_id: str, request: Request):
    # PREP-D2 (AUD-MW-10) — membuka kunci gate = keputusan admin gudang: izin `wms.approve`, terpisah dari `wms.scan`.
    await require_permission(request, 'wms', 'approve')
    actor, dev, _ = await _scoped(request, device_id, True)
    body = await _payload(request)
    if not isinstance(body, dict):
        service.fail(400, 'INVALID_BODY', 'Isi catatan pemeriksaan dan kunci gate.')
    cfg = await service.config(dev)
    gate_id = body.get('logical_gate_id') or cfg['logical_gates'][0]['logical_gate_id']
    service.gate(cfg, gate_id)
    res = await latch.acknowledge_gate(dev, gate_id, body.get('latch_id'), body.get('note'), actor)
    await audit(actor['name'], 'rfid_v2_gate_latch_released', 'rfid_device', device_id,
                {'latch_id': body.get('latch_id')}, reason=str(body.get('note') or '')[:200])
    return res


@router.put('/rfid/v2/ops/devices/{device_id}/protocol')
async def put_protocol(device_id: str, request: Request):
    await require_permission(request, 'rfid_device', 'configure')
    actor, dev, _ = await _scoped(request, device_id, True)
    body = await _payload(request)
    res = await service.set_protocol(dev, (body or {}).get('protocol'), actor)
    await audit(actor['name'], 'rfid_device_protocol_set', 'rfid_device', device_id, res)
    return res


@router.get('/rfid/v2/ops/gate-parameter-defaults')
async def gate_parameter_defaults(request: Request):
    await require_permission(request, 'wms', 'view')
    return {'defaults': params_mod.DEFAULTS, 'note': params_mod.CALIBRATION_NOTE}


@router.post('/rfid/v2/ops/devices/{device_id}/gate-parameters')
async def post_gate_parameters(device_id: str, request: Request):
    await require_permission(request, 'rfid_device', 'configure')
    actor, dev, _ = await _scoped(request, device_id, True)
    body = await _payload(request)
    if not isinstance(body, dict) or not isinstance(body.get('parameters'), dict):
        service.fail(400, 'INVALID_BODY', 'Kirim logical_gate_id, config_version baru, dan parameters.')
    cfg = await service.config(dev)
    gate_id = body.get('logical_gate_id') or cfg['logical_gates'][0]['logical_gate_id']
    res = await service.publish_gate_parameters(dev, gate_id, body.get('config_version'), body['parameters'], actor)
    await audit(actor['name'], 'rfid_v2_gate_parameters_published', 'rfid_device', device_id,
                {'config_version': body.get('config_version'), 'parameters': body['parameters']})
    return res


@router.post('/rfid/v2/ops/devices/{device_id}/simulate')
async def simulate(device_id: str, request: Request):
    await require_permission(request, 'rfid_device', 'configure')   # alat admin/dev — lintasan & klaim bertanda simulated
    actor, dev, _ = await _scoped(request, device_id, True)
    body = await _payload(request)
    if not isinstance(body, dict):
        service.fail(400, 'INVALID_BODY', 'Pilih skenario simulator.')
    source = None
    if body.get('source_type') and body.get('source_id'):
        source, _ = await _source_scope(request, body['source_type'], body['source_id'])
    res = await simulator.run(dev, body.get('scenario'), body.get('logical_gate_id'), source,
                              int(body.get('roll_limit') or 200))
    await audit(actor['name'], 'rfid_v2_simulation', 'rfid_device', device_id,
                {'scenario': res['scenario'], 'verdicts': [p['decision']['verdict'] for p in res['passages']]})
    return res


@router.get('/rfid/v2/ops/devices/{device_id}/health')
async def device_health(device_id: str, request: Request):
    _, dev, _ = await _scoped(request, device_id)
    return {'device_id': device_id, 'rules': await health.check_device(dev)}


@router.post('/rfid/v2/ops/health/check')
async def health_check(request: Request):
    await require_permission(request, 'rfid_device', 'configure')
    return await health.check_all()
