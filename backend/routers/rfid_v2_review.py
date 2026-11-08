"""PREP-D2 — antrean periksa gate V2, koreksi klaim crossing, status kios V2 (sesi pengguna; device key TIDAK diterima).

Izin: lihat = `wms.view`; semua tindakan antrean & koreksi klaim = `wms.approve` (TERPISAH dari `wms.scan` petugas
gerbang — K-RFID-09 / AUD-MW-10). Cakupan: gudang kasus (`inventory_rolls` registry + izin pakai gudang) dan entitas
dokumen sumbernya. Setiap tindakan → `audit()` + jejak di kasus.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from dependencies import audit, require_permission
from entity_scope import assert_entity_access, entity_ctx
from routers.rfid_v2 import _operator_device, _payload
from services import gate_review_actions as act
from services import gate_review_service as rv
from services import rfid_v2_kiosk as kiosk
from services import rfid_v2_sources as sources
from services.rfid_v2_common import fail

router = APIRouter(prefix='/api')


async def _case_access(case: Dict[str, Any], ctx, write: bool = False) -> None:
    assert_entity_access({'warehouse_id': case.get('warehouse_id')}, 'inventory_rolls', ctx)
    if write and case.get('warehouse_id'):
        from services.warehouse_scope_service import assert_usable
        await assert_usable(case['warehouse_id'], ctx.active_entity_id, action='menindaklanjuti antrean periksa gate')
    for ref in case.get('sources') or []:
        name, doc = await sources.source_document(ref)
        if doc:
            assert_entity_access(doc, name, ctx)


async def _visible(rows, ctx):
    out = []
    for row in rows:
        try:
            await _case_access(row, ctx)
            out.append(row)
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
    return out


def _public(case: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if case:
        case.pop('_id', None)
    return case


async def _write_case(request: Request, case_id: str):
    actor = await require_permission(request, 'wms', 'approve')
    ctx = await entity_ctx(request)
    case = await rv.get_case(case_id)
    await _case_access(case, ctx, write=True)
    body = await _payload(request)
    if not isinstance(body, dict):
        fail(400, 'INVALID_BODY', 'Isi roll yang dipilih dan alasan.')
    return actor, case, body


@router.get('/rfid/v2/ops/reviews')
async def list_reviews(request: Request, warehouse_id: Optional[str] = None, device_id: Optional[str] = None,
                       status: str = 'open', verdict: Optional[str] = None, kind: Optional[str] = None,
                       before: Optional[str] = None, limit: int = Query(50, ge=1, le=100)):
    await require_permission(request, 'wms', 'view')
    ctx = await entity_ctx(request)
    if status not in ('open', 'resolved', 'all') or (verdict and verdict not in ('REVIEW', 'RED', 'GREEN')) \
            or (kind and kind not in ('passage', 'rolls_missing')):
        fail(400, 'INVALID_FILTER', 'Saring status (terbuka/selesai/semua), hasil (kuning/merah), atau jenis kasus.')
    rows = await rv.list_cases(warehouse_id=warehouse_id, device_id=device_id, status=status, verdict=verdict,
                               kind=kind, before=before, limit=limit)
    visible = await _visible(rows, ctx)
    return {'reviews': [_public(r) for r in visible], 'limit': limit,
            'next_before': rows[-1]['created_at'] if len(rows) == limit else None}


@router.get('/rfid/v2/ops/reviews/summary')
async def reviews_summary(request: Request, warehouse_id: Optional[str] = None):
    await require_permission(request, 'wms', 'view')
    ctx = await entity_ctx(request)
    if warehouse_id:
        assert_entity_access({'warehouse_id': warehouse_id}, 'inventory_rolls', ctx)
    return await rv.summary([warehouse_id] if warehouse_id else None)


@router.get('/rfid/v2/ops/reviews/{case_id}')
async def get_review(case_id: str, request: Request):
    await require_permission(request, 'wms', 'view')
    ctx = await entity_ctx(request)
    case = await rv.get_case(case_id)
    await _case_access(case, ctx)
    return _public(case)


@router.post('/rfid/v2/ops/reviews/{case_id}/rolls/accept')
async def accept_rolls(case_id: str, request: Request):
    actor, _, body = await _write_case(request, case_id)
    out = await act.accept(case_id, body.get('roll_keys'), body.get('reason'), actor)
    await audit(actor['name'], 'rfid_v2_review_accept', 'rfid_v2_review', case_id,
                {'rolls': [d['roll_id'] for d in out['accepted']], 'skipped': out['skipped']},
                reason=str(body.get('reason') or '')[:200])
    return {**out, 'case': _public(out['case'])}


@router.post('/rfid/v2/ops/reviews/{case_id}/rolls/reject')
async def reject_rolls(case_id: str, request: Request):
    actor, _, body = await _write_case(request, case_id)
    mode = body.get('mode') or 'reject'
    out = await act.reject(case_id, body.get('roll_keys'), body.get('reason'), mode, actor)
    await audit(actor['name'], f'rfid_v2_review_{mode}', 'rfid_v2_review', case_id,
                {'rolls': body.get('roll_keys'), 'claims_released': out['claims_released']},
                reason=str(body.get('reason') or '')[:200])
    return {**out, 'case': _public(out['case'])}


@router.post('/rfid/v2/ops/reviews/{case_id}/rolls/rescan')
async def rescan_rolls(case_id: str, request: Request):
    actor, _, body = await _write_case(request, case_id)
    out = await act.rescan(case_id, body.get('roll_keys'), body.get('note'), actor)
    await audit(actor['name'], 'rfid_v2_review_rescan', 'rfid_v2_review', case_id, {'rolls': body.get('roll_keys')},
                reason=str(body.get('note') or '')[:200])
    return {**out, 'case': _public(out['case'])}


@router.post('/rfid/v2/ops/reviews/{case_id}/dismiss')
async def dismiss_review(case_id: str, request: Request):
    actor, _, body = await _write_case(request, case_id)
    out = await act.dismiss(case_id, body.get('reason'), actor)
    await audit(actor['name'], 'rfid_v2_review_dismiss', 'rfid_v2_review', case_id, {'ignored': out['changed']},
                reason=str(body.get('reason') or '')[:200])
    return {**out, 'case': _public(out['case'])}


@router.post('/rfid/v2/ops/reviews/{case_id}/acknowledge-latch')
async def acknowledge_review_latch(case_id: str, request: Request):
    actor, case, body = await _write_case(request, case_id)
    out = await act.acknowledge_latch(case_id, body.get('note'), actor)
    await audit(actor['name'], 'rfid_v2_gate_latch_released', 'rfid_device', case.get('device_id') or '',
                {'latch_id': case.get('latch_id'), 'review_case': case_id, 'released': out['latch_released']},
                reason=str(body.get('note') or '')[:200])
    return {**out, 'case': _public(out['case'])}


@router.post('/rfid/v2/ops/reviews/{case_id}/retry')
async def retry_review(case_id: str, request: Request):
    actor, _, _ = await _write_case(request, case_id)
    out = await act.retry(case_id, actor)
    await audit(actor['name'], 'rfid_v2_review_retry', 'rfid_v2_review', case_id, {'results': out['results']})
    return {**out, 'case': _public(out['case'])}


# ─── Koreksi klaim crossing (AUD-MW-08) ───────────────────────────────────────────────────
async def _source_access(request: Request, ref: Any):
    if not isinstance(ref, dict) or ref.get('source_type') not in sources.SOURCE_TYPES \
            or not isinstance(ref.get('source_id'), str) or not ref['source_id']:
        fail(400, 'INVALID_SOURCE', 'Jenis dan identitas dokumen tidak valid.')
    ctx = await entity_ctx(request)
    name, doc = await sources.source_document(ref)
    if not doc:
        fail(404, 'SOURCE_NOT_FOUND', 'Dokumen tidak ditemukan.')
    assert_entity_access(doc, name, ctx)
    return {'source_type': ref['source_type'], 'source_id': ref['source_id'],
            **({'doc_id': ref['doc_id']} if ref.get('doc_id') else {})}, doc


def _direction(value: Any) -> str:
    if value not in ('in', 'out'):
        fail(400, 'DIRECTION_REQUIRED', 'Arah wajib masuk atau keluar.')
    return value


@router.get('/rfid/v2/ops/crossings')
async def list_crossings(request: Request, source_type: str, source_id: str, direction: str = 'out'):
    await require_permission(request, 'wms', 'view')
    ref, _ = await _source_access(request, {'source_type': source_type, 'source_id': source_id})
    return await act.list_claims(ref, _direction(direction))


@router.post('/rfid/v2/ops/crossings/release')
async def release_crossing(request: Request):
    actor = await require_permission(request, 'wms', 'approve')
    body = await _payload(request)
    if not isinstance(body, dict) or not isinstance(body.get('roll_id'), str):
        fail(400, 'INVALID_BODY', 'Isi dokumen, arah, roll, dan alasan.')
    ref, _ = await _source_access(request, body.get('source'))
    out = await act.release_claim(ref, _direction(body.get('direction')), body['roll_id'], body.get('reason'), actor)
    await audit(actor['name'], 'rfid_v2_claim_released', ref['source_type'], ref['source_id'],
                {'roll_id': body['roll_id'], 'direction': body.get('direction'),
                 'passage': out['correction']['claim'].get('passage')}, reason=str(body.get('reason') or '')[:200])
    return out


@router.post('/rfid/v2/ops/crossings/move')
async def move_crossing(request: Request):
    actor = await require_permission(request, 'wms', 'approve')
    body = await _payload(request)
    if not isinstance(body, dict) or not isinstance(body.get('roll_id'), str):
        fail(400, 'INVALID_BODY', 'Isi dokumen asal, dokumen tujuan, arah, roll, dan alasan.')
    direction = _direction(body.get('direction'))
    ref, doc = await _source_access(request, body.get('source'))
    target, tdoc = await _source_access(request, body.get('target'))
    from routers.rfid_v2_ops import _warehouse_of
    warehouse = _warehouse_of(target['source_type'], tdoc, direction)
    if not warehouse:
        fail(409, 'TARGET_NOT_ACTIVE', 'Gudang dokumen tujuan tidak diketahui.')
    out = await act.move_claim(ref, target, direction, body['roll_id'], body.get('reason'), actor, warehouse)
    await audit(actor['name'], 'rfid_v2_claim_moved', ref['source_type'], ref['source_id'],
                {'roll_id': body['roll_id'], 'direction': direction, 'target': out['correction'].get('target')},
                reason=str(body.get('reason') or '')[:200])
    return out


# ─── Kios / monitor gate V2 ───────────────────────────────────────────────────────────────
@router.get('/rfid/v2/ops/devices/{device_id}/kiosk')
async def kiosk_state(device_id: str, request: Request):
    await require_permission(request, 'wms', 'view')
    _, dev, _ = await _operator_device(request, device_id)
    return await kiosk.kiosk_status(dev)
