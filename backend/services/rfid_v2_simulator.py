"""PREP-D1 — simulator lintasan TANPA perangkat (alat admin/dev, dipakai paket E & UAT).

Menjalankan skenario `rfid_v2_envelope.SCENARIOS` lewat jalur layanan yang SAMA dengan reader (ingest → close),
atas nama perangkat yang dipilih. Lintasan & klaim bertanda `simulated: true` (ID lintasan `sim-…`). Simulator
TIDAK membuat stok/dokumen palsu: roll dokumen diambil dari dokumen aktif (binding manual, sumber yang dipilih, atau
kandidat pertama gudang/arah); roll karantina/asing diambil dari data gudang bila ada, selain itu EPC sintetis.
"""
import secrets
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from services import rfid_v2_core as core
from services import rfid_v2_envelope as env
from services import rfid_v2_ingest as ingest
from services import rfid_v2_sessions as sessions
from services import rfid_v2_sources as sources
from services.rfid_v2_common import collection, digest, fail

TYPES_BY_DIRECTION = {'out': ('shipment', 'wh_transfer', 'putaway', 'makloon_order', 'repair_order'),
                      'in': ('putaway', 'wh_transfer', 'repair_order')}


async def _epcs_for(roll_ids: List[str], limit: int) -> List[str]:
    rows = await db.rfid_tags.find({'roll_id': {'$in': roll_ids}, 'status': 'active'}, {'_id': 0, 'epc': 1}).to_list(limit)
    return [r['epc'] for r in rows]


async def _remaining(ref: Dict[str, Any], ids: List[str], direction: str) -> List[str]:
    passed = await sessions.passed_map(ref['source_type'], ref['source_id'], direction)
    return [rid for rid in ids if rid not in passed]


async def _document(device, cfg, gate_id, direction, source, limit):
    """(source_ref, EPC roll dokumen yang BELUM lewat)."""
    if source:
        ref, ids = await sources.manifest(source, cfg['warehouse_id'], direction)
        return ref, await _epcs_for(await _remaining(ref, ids, direction), limit)
    g = core.gate(cfg, gate_id)
    binding = await collection('rfid_v2_bindings').find_one({'_id': digest([device['id'], gate_id])})
    if core.binding_active(binding, core.gate_params(g)):
        entry = core.binding_sources(binding)[0]
        rest = await _remaining(entry['source_ref'], entry['roll_ids'], direction)
        return entry['source_ref'], await _epcs_for(rest, limit)
    for typ in TYPES_BY_DIRECTION[direction]:
        for cand in await sources.candidates(typ, direction, cfg['warehouse_id'], lambda _n, q: q):
            try:
                ref, ids = await sources.manifest({'source_type': typ, 'source_id': cand['id']}, cfg['warehouse_id'], direction)
            except HTTPException:
                continue
            epcs = await _epcs_for(await _remaining(ref, ids, direction), limit)
            if epcs:
                return ref, epcs
    return None, []


async def _roll_epc(warehouse: str, status: str, exclude: List[str], owner: str = '') -> Optional[str]:
    # FIX-3b (K-B2b-09) — roll "asing/karantina" contoh diambil dari PT dokumen yang sama (bermode simulasi), bukan
    # roll PT lain yang datanya nyata.
    q = {'warehouse_id': warehouse, 'status': status, **({'owner_entity_id': owner} if owner else {})}
    rolls = await db.inventory_rolls.find(q, {'_id': 0, 'id': 1}).to_list(200)
    if not rolls:
        return None
    tag = await db.rfid_tags.find_one({'roll_id': {'$in': [r['id'] for r in rolls]}, 'status': 'active',
                                       'epc': {'$nin': exclude}}, {'_id': 0, 'epc': 1})
    return (tag or {}).get('epc')


def synthetic_epc() -> str:
    return 'E2' + secrets.token_hex(11).upper()


async def _send(device, cfg, g, direction, scenario, doc, extra=(), background=(), capacity=None) -> Dict[str, Any]:
    built = env.build_passage(scenario=scenario, gate_id=g['logical_gate_id'], config_version=cfg['config_version'],
                              hardware_profile_id=cfg['hardware_profile_id'], direction=direction,
                              antennas=g['antenna_ids'], doc_epcs=doc, extra_strong=extra, background_epcs=background)
    from services import rfid_v2_service as service
    for body in built['batches']:
        await ingest.events(device, body, simulated=True, capacity_override=capacity)
    decision = await service.close(device, built['passage_id'], built['close'], f"sim-close-{built['passage_id']}",
                                   simulated=True)
    return {'local_passage_id': built['passage_id'], 'expected': built['expected'], 'decision': decision}


_DOC_COLL = {'shipment': 'shipments', 'wh_transfer': 'warehouse_transfers', 'putaway': 'putaway_orders',
             'makloon_order': 'makloon_orders', 'repair_order': 'repair_orders'}


async def _doc_entity(ref: Optional[Dict[str, Any]]) -> str:
    """PT pemilik dokumen sumber (untuk Mode simulasi RFID per PT)."""
    if not ref or ref.get('source_type') not in _DOC_COLL:
        return ''
    d = await db[_DOC_COLL[ref['source_type']]].find_one({'id': ref.get('source_id')},
                                                         {'_id': 0, 'entity_id': 1, 'owner_entity_id': 1})
    return (d or {}).get('entity_id') or (d or {}).get('owner_entity_id') or ''


async def run(device: Dict[str, Any], scenario: str, gate_id: Optional[str] = None,
              source: Optional[Dict[str, Any]] = None, roll_limit: int = 200) -> Dict[str, Any]:
    if scenario not in env.SCENARIOS:
        fail(400, 'INVALID_SCENARIO', 'Skenario simulator tidak dikenal.')
    # FIX-3b (RFID-1/RFID-9, K-B2b-09) — perangkat WAJIB bertanda uji SEBELUM apa pun dibaca/ditulis.
    from services.rfid_service import simulator_problem, simulation_on
    if device.get('test_device') is not True:
        fail(409, 'SIMULATOR_NOT_ALLOWED', await simulator_problem(device, ''))
    cfg = await core.config(device)
    g = core.gate(cfg, gate_id or cfg['logical_gates'][0]['logical_gate_id'])
    direction = g['direction'] if g['direction'] in ('in', 'out') else 'out'
    limit = max(1, min(int(roll_limit or 200), 2000))
    ref, doc = (None, []) if scenario == 'empty' else await _document(device, cfg, g['logical_gate_id'], direction, source, limit)
    if scenario != 'empty' and not doc:
        fail(409, 'NO_DOCUMENT_ROLLS', 'Tidak ada dokumen aktif dengan roll bertag yang belum lewat untuk gudang/arah gate ini.')
    # FIX-3b (RFID-1) — klaim simulasi tidak boleh lahir untuk dokumen PT yang Mode simulasi RFID-nya MATI (data nyata):
    # dulu klaim `simulated` dipasang → lintasan nyata berikutnya MERAH `REPLAY_EXIT` + gate terkunci.
    ent = await _doc_entity(ref) if ref is not None else ''
    if ref is not None and not await simulation_on(ent):
        fail(409, 'SIMULATOR_NOT_ALLOWED', 'Mode simulasi RFID untuk PT dokumen ini mati — simulator tidak dijalankan '
                                           '(klaim simulasi tidak boleh menyentuh roll/dokumen nyata).')
    notes: List[str] = []
    runs: List[Dict[str, Any]] = []
    if scenario == 'partial_trip':
        if len(doc) < 2:
            fail(409, 'NEED_TWO_ROLLS', 'Skenario trip parsial butuh dokumen dengan ≥ 2 roll bertag yang belum lewat.')
        half = len(doc) // 2
        runs.append(await _send(device, cfg, g, direction, 'partial_trip', doc[:half]))
        runs.append(await _send(device, cfg, g, direction, 'partial_trip', doc[half:]))
    elif scenario == 'foreign_roll':
        epc = await _roll_epc(cfg['warehouse_id'], 'available', doc, ent)
        if not epc:
            epc = synthetic_epc()
            notes.append('Tidak ada roll available bertag di gudang ini — memakai EPC asing sintetis (UNKNOWN_EPC).')
        runs.append(await _send(device, cfg, g, direction, scenario, doc, extra=[epc]))
    elif scenario == 'quarantine_roll':
        epc = await _roll_epc(cfg['warehouse_id'], 'quarantine', doc, ent)
        if not epc:
            fail(409, 'NO_QUARANTINE_ROLL', 'Tidak ada roll karantina bertag di gudang ini — skenario tidak bisa dijalankan.')
        runs.append(await _send(device, cfg, g, direction, scenario, doc, extra=[epc]))
    elif scenario == 'background_tag':
        runs.append(await _send(device, cfg, g, direction, scenario, doc, background=[synthetic_epc()]))
    elif scenario == 'overflow':
        cap = max(1, len(doc) * 2 - 1)   # satu ringkasan terakhir melewati kapasitas
        runs.append(await _send(device, cfg, g, direction, scenario, doc, capacity={'summary': cap}))
    else:
        runs.append(await _send(device, cfg, g, direction, scenario, doc))
    return {'scenario': scenario, 'description': env.SCENARIOS[scenario][1], 'source_ref': ref,
            'rolls_used': len(doc), 'passages': runs, 'notes': notes,
            'as_expected': all(r['decision']['verdict'] == r['expected'] for r in runs)}
