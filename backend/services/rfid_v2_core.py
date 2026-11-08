"""Inti protokol gate U300 V2: kontrak 2.1, profil commissioning berversi, gate, lintasan, binding manual, protokol.

Pengamatan TIDAK pernah mengubah stok atau akuntansi. Dokumen lintasan (`rfid_v2_passages`) = batas atomik
(OPEN → CLOSING → FINAL); bukti (event/ringkasan/tepi sinar) disimpan di koleksi sendiri (AUD-MW-07).
"""
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from jsonschema import Draft7Validator, FormatChecker
from pymongo.errors import DuplicateKeyError

from services.rfid_v2_common import collection, digest, fail, now, parse_ts
from services import rfid_v2_params as params_mod

PROTOCOLS = ('legacy', 'v2')
KINDS = ('event', 'summary', 'edge')
KIND_COLLECTION = {'event': 'rfid_v2_events', 'summary': 'rfid_v2_summaries', 'edge': 'rfid_v2_edges'}
# Kapasitas bukti per lintasan (lebih → ACK quarantined CAPTURE_OVERFLOW ke koleksi luapan, AUD-MW-01c).
CAPACITY = {'event': 10000, 'summary': 10000, 'edge': 500}
MAX_PASSAGE_BYTES = 32_000_000


def _json_schema(value):
    if isinstance(value, list):
        return [_json_schema(v) for v in value]
    if not isinstance(value, dict):
        return value
    out = {k: _json_schema(v) for k, v in value.items() if k != 'nullable'}
    if value.get('nullable'):
        return {'anyOf': [out, {'type': 'null'}]}
    return out


CONTRACT = _json_schema(json.loads((Path(__file__).parents[1] / 'contracts/rfid_v2.json').read_text(encoding='utf-8-sig')))
CONTRACT_VERSION = json.loads((Path(__file__).parents[1] / 'contracts/rfid_v2.json').read_text(encoding='utf-8-sig'))['info']['version']


def validate(name: str, payload: Any) -> None:
    schema = {'$ref': '#/components/schemas/' + name, 'components': CONTRACT['components']}
    error = next(Draft7Validator(schema, format_checker=FormatChecker()).iter_errors(payload), None)
    if error:
        fail(400, 'INVALID_' + name.upper(), f"{'.'.join(map(str, error.path))}: {error.message}")


async def ensure_indexes() -> None:
    passages = collection('rfid_v2_passages')
    await passages.create_index([('device_id', 1), ('created_at', -1), ('_id', -1)])
    await passages.create_index([('device_id', 1), ('gate_id', 1), ('acknowledged', 1), ('decision.latched', 1)])
    await collection('rfid_v2_bindings').create_index('device_id')
    for name in list(KIND_COLLECTION.values()) + ['rfid_v2_overflow']:
        await collection(name).create_index([('passage', 1), ('received_at', 1)])
    await collection('rfid_v2_crossings').create_index([('source_type', 1), ('source_id', 1), ('direction', 1)])
    await collection('rfid_v2_crossings').create_index('passage')
    await collection('rfid_v2_doc_sessions').create_index([('warehouse_id', 1), ('status', 1)])
    await collection('rfid_v2_health').create_index([('device_id', 1), ('active', 1)])
    # PREP-D2 — antrean periksa, buku transaksi gate, koreksi klaim
    await collection('rfid_v2_reviews').create_index([('status', 1), ('warehouse_id', 1), ('created_at', -1)])
    await collection('rfid_v2_reviews').create_index([('device_id', 1), ('created_at', -1)])
    await collection('rfid_v2_gate_txn').create_index('passage')
    await collection('rfid_v2_claim_corrections').create_index([('source_type', 1), ('source_id', 1), ('direction', 1)])


async def config(device: Dict[str, Any], version: Optional[str] = None) -> Dict[str, Any]:
    version = version or device.get('v2_config_version')
    row = await collection('rfid_v2_configs').find_one({'_id': digest([device['id'], version])})
    if not row:
        fail(409, 'CONFIG_REQUIRED', 'Profil V2 belum diterbitkan atau versi tidak dikenal.', retryable=True,
             details={'poll_after_seconds': 60})
    cfg = copy.deepcopy(row['config'])
    if cfg['warehouse_id'] != device.get('warehouse_id'):
        fail(409, 'DEVICE_MOVED', 'Gudang device berubah; selesaikan antrean sebelum pindah identitas.')
    cfg['enabled'] = device.get('enabled') is not False
    cfg['server_time'] = now()
    return cfg


def gate(cfg: Dict[str, Any], gate_id: str) -> Dict[str, Any]:
    for g in cfg['logical_gates']:
        if g['logical_gate_id'] == gate_id and g['enabled']:
            return g
    fail(403, 'GATE_NOT_BOUND', 'Gate tidak terikat pada perangkat ini.')


def gate_params(g: Dict[str, Any]) -> Dict[str, Any]:
    return params_mod.effective(g)


async def publish_config(device: Dict[str, Any], cfg: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    validate('DeviceConfig', cfg)
    if cfg['device_id'] != device['id'] or cfg['warehouse_id'] != device.get('warehouse_id') or cfg['device_type'] != 'fixed_reader':
        fail(400, 'IDENTITY_MISMATCH', 'Identitas profil harus mengikuti fixed reader dan gudangnya.')
    if device.get('type') not in ('gate', 'fixed_reader'):
        fail(400, 'WRONG_DEVICE_TYPE', 'Profil ini hanya untuk reader/gate.')
    if len(cfg['logical_gates']) != 1:
        fail(400, 'SINGLE_GATE_REQUIRED', 'Agent U300 saat ini menjalankan satu logical gate.')
    g = cfg['logical_gates'][0]
    if g['warehouse_id'] != cfg['warehouse_id'] or g['site_id'] != cfg['site_id']:
        fail(400, 'GATE_SCOPE', 'Lokasi dan gudang gate harus sesuai perangkat.')
    problem = params_mod.validate(g.get('passage_parameters') or {})
    if problem:
        fail(400, 'INVALID_GATE_PARAMETERS', problem)
    if not 1 <= cfg['policies']['gate_decision_validity_seconds'] <= 60:
        fail(400, 'INVALID_VALIDITY', 'Masa berlaku keputusan wajib 1 sampai 60 detik.')
    saved = copy.deepcopy(cfg)          # server tidak mengarang profil hardware yang belum dikomisikan
    saved.pop('server_time', None)
    key = digest([device['id'], cfg['config_version']])
    try:
        await collection('rfid_v2_configs').insert_one({'_id': key, 'config': saved, 'actor_id': actor['id'], 'at': now(),
                                                        'device_id': device['id']})
    except DuplicateKeyError:
        old = await collection('rfid_v2_configs').find_one({'_id': key})
        if old['config'] != saved:
            fail(409, 'IMMUTABLE_CONFIG', 'Versi yang sama tidak boleh diubah; terbitkan versi baru.')
    # AUD-MW-09 — profil V2 terbit = perangkat ber-protokol v2 → jalur lama /api/rfid/ingest ditutup.
    await collection('rfid_devices').update_one({'id': device['id']}, {'$set': {
        'v2_config_version': cfg['config_version'], 'protocol': 'v2', 'protocol_at': now()}})
    return {'request_id': str(uuid4()), 'server_time': now(), 'config_version': cfg['config_version']}


async def set_protocol(device: Dict[str, Any], protocol: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    if protocol not in PROTOCOLS:
        fail(400, 'INVALID_PROTOCOL', 'Protokol hanya legacy atau v2.')
    if protocol == 'v2' and not device.get('v2_config_version'):
        fail(409, 'CONFIG_REQUIRED', 'Terbitkan profil V2 dulu sebelum perangkat dipindah ke protokol v2.')
    await collection('rfid_devices').update_one({'id': device['id']}, {'$set': {
        'protocol': protocol, 'protocol_at': now(), 'protocol_by': actor.get('id')}})
    return {'device_id': device['id'], 'protocol': protocol}


def binding_sources(binding: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Snapshot 0.4 tetap terbaca tanpa menulis ulang riwayat.
    return binding.get('sources') or [{'source_ref': binding['source_ref'], 'roll_ids': binding.get('roll_ids', [])}]


def binding_active(binding: Optional[Dict[str, Any]], params: Dict[str, Any]) -> bool:
    """Binding manual berlaku sampai dilepas atau kedaluwarsa (`manual_binding_ttl_s`, AUD-MW-15)."""
    if not binding or binding.get('released_at'):
        return False
    bound = parse_ts(binding.get('bound_at'))
    if not bound:
        return False
    return datetime.now(timezone.utc) - bound <= timedelta(seconds=int(params.get('manual_binding_ttl_s') or 0))


async def passage(device: Dict[str, Any], cfg: Dict[str, Any], gate_id: str, passage_id: str, mode: str,
                  simulated: bool = False) -> Dict[str, Any]:
    g = gate(cfg, gate_id)
    pid = digest([device['id'], passage_id])
    binding = await collection('rfid_v2_bindings').find_one({'_id': digest([device['id'], gate_id])})
    if not binding_active(binding, gate_params(g)):
        binding = None
    seed = {'device_id': device['id'], 'local_passage_id': passage_id, 'gate_id': gate_id,
            'warehouse_id': cfg['warehouse_id'], 'config_version': cfg['config_version'], 'mode': mode,
            'state': 'OPEN', 'event_count': 0, 'summary_count': 0, 'edge_count': 0, 'bytes': 0,
            'overflow': {k: 0 for k in KINDS}, 'binding': binding, 'created_at': now(), 'decision': None,
            'acknowledged': False, 'simulated': bool(simulated)}
    try:
        await collection('rfid_v2_passages').update_one({'_id': pid}, {'$setOnInsert': seed}, upsert=True)
    except DuplicateKeyError:
        pass
    p = await collection('rfid_v2_passages').find_one({'_id': pid}, {'events': 0})
    if (p['gate_id'], p['config_version'], p['mode']) != (gate_id, cfg['config_version'], mode):
        fail(409, 'PASSAGE_CONTEXT_CHANGED', 'ID passage sudah digunakan dengan konteks berbeda.')
    return p


async def load_evidence(pid: str) -> Dict[str, List[Dict[str, Any]]]:
    out = {}
    for kind, name in KIND_COLLECTION.items():
        out[kind] = await collection(name).find({'passage': pid}, {'_id': 0}).sort('received_at', 1).to_list(CAPACITY[kind])
    out['overflow'] = await collection('rfid_v2_overflow').find({'passage': pid}, {'_id': 0}).sort('received_at', 1).to_list(5000)
    return out
