"""PREP-D1 — aturan kesehatan reader U300 V2 → notifikasi (AUD-MW-17).

Aturan (ambang = TITIK AWAL KALIBRASI, belum diuji lokasi):
  * READER_STOPPED   — telemetry `radio_state` stopped/error (reader berhenti membaca).
  * TELEMETRY_STALE  — telemetry terakhir lebih tua dari max(3 × interval profil, 180 detik).
  * QUEUE_RISING     — antrean agent ≥ 1000 event atau event tertua menunggu > 120 detik.
Notifikasi hanya saat aturan BERUBAH menjadi aktif (status per perangkat × aturan, CAS), ke kepala gudang & manager
(pola `printer_stuck_watch`, dedupe unread). Dipicu: tiap telemetry masuk, layar ops, dan job penjadwal
`rfid_reader_health_watch` (telemetry basi hanya terdeteksi oleh pemicu dari luar perangkat).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

from pymongo.errors import DuplicateKeyError

from db import db
from services.notification_service import create_notification
from services.rfid_v2_common import collection, digest, now, parse_ts

STALE_MIN_S = 180
STALE_FACTOR = 3
QUEUE_EVENTS = 1000
QUEUE_AGE_S = 120
LABEL = {'READER_STOPPED': 'Reader berhenti membaca', 'TELEMETRY_STALE': 'Laporan reader terlambat',
         'QUEUE_RISING': 'Antrean reader menumpuk'}


async def _interval(device: Dict[str, Any]) -> int:
    row = await collection('rfid_v2_configs').find_one({'_id': digest([device['id'], device.get('v2_config_version')])},
                                                       {'config.policies.telemetry_interval_seconds': 1})
    return int((((row or {}).get('config') or {}).get('policies') or {}).get('telemetry_interval_seconds') or 30)


async def evaluate(device: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Daftar aturan dengan status aktif/tidak untuk satu perangkat V2 (tanpa efek samping)."""
    tel = device.get('v2_telemetry') or {}
    at = parse_ts(device.get('v2_telemetry_at') or device.get('last_heartbeat'))
    nowdt = datetime.now(timezone.utc)
    limit = max(STALE_MIN_S, STALE_FACTOR * await _interval(device))
    age = int((nowdt - at).total_seconds()) if at else None
    oldest = parse_ts(tel.get('oldest_pending_at'))
    wait = int((nowdt - oldest).total_seconds()) if oldest else 0
    pending = int(tel.get('pending_event_count') or 0)
    disabled = device.get('enabled') is False
    return [
        {'rule': 'READER_STOPPED', 'active': not disabled and tel.get('radio_state') in ('stopped', 'error'),
         'message': f"Status radio: {tel.get('radio_state') or '—'}" + (f" · {tel['last_error'].get('message')}" if tel.get('last_error') else '')},
        {'rule': 'TELEMETRY_STALE', 'active': not disabled and (age is None or age > limit),
         'message': 'Belum pernah ada laporan reader.' if age is None else f'Laporan terakhir {age} detik lalu (batas {limit} detik).'},
        {'rule': 'QUEUE_RISING', 'active': not disabled and (pending >= QUEUE_EVENTS or wait > QUEUE_AGE_S),
         'message': f'{pending} event menunggu; tertua {wait} detik.'},
    ]


async def check_device(device: Dict[str, Any]) -> List[Dict[str, Any]]:
    rules = await evaluate(device)
    coll = collection('rfid_v2_health')
    for r in rules:
        key = digest(['health', device['id'], r['rule']])
        if r['active']:
            try:   # CAS: hanya transisi tidak-aktif → aktif yang memicu notifikasi
                res = await coll.update_one({'_id': key, 'active': {'$ne': True}}, {'$set': {
                    'device_id': device['id'], 'rule': r['rule'], 'active': True, 'since': now(),
                    'message': r['message']}}, upsert=True)
                created = bool(res.modified_count or res.upserted_id)
            except DuplicateKeyError:
                created = False   # sudah aktif (atau diaktifkan pemicu lain bersamaan)
            if created:
                await _notify(device, r)
            else:
                await coll.update_one({'_id': key}, {'$set': {'message': r['message'], 'checked_at': now()}})
        else:
            await coll.update_one({'_id': key, 'active': True}, {'$set': {'active': False, 'cleared_at': now()}})
        row = await coll.find_one({'_id': key}, {'_id': 0, 'since': 1})
        r['since'] = (row or {}).get('since') if r['active'] else None
        r['label'] = LABEL[r['rule']]
    return rules


async def _notify(device: Dict[str, Any], rule: Dict[str, Any]) -> None:
    wh = await db.warehouses.find_one({'id': device.get('warehouse_id')}, {'_id': 0, 'name': 1}) or {}
    name = device.get('name') or device.get('code') or device['id']
    title = f"{LABEL[rule['rule']]}: {name}"
    body = f"{rule['message']} Gudang {wh.get('name') or device.get('warehouse_id')}. Cek reader gate di lokasi."
    for role in ('warehouse_admin', 'manager'):
        await create_notification(notif_type='rfid_reader_health', ref=f"rfid_health:{device['id']}:{rule['rule']}:{role}",
                                  title=title, body=body, severity='warning', link='settings-devices',
                                  recipient_role=role, dedupe=True, dedupe_scope='unread')


async def check_all() -> Dict[str, Any]:
    devices = await db.rfid_devices.find({'protocol': 'v2', 'enabled': {'$ne': False}},
                                         {'_id': 0, 'api_key_hash': 0}).to_list(500)
    active = 0
    for d in devices:
        active += sum(1 for r in await check_device(d) if r['active'])
    return {'checked_at': now(), 'devices': len(devices), 'active_alerts': active}


async def job_rfid_reader_health_watch() -> Dict[str, Any]:
    res = await check_all()
    return {'ok': True, 'scanned': res['devices'], 'detail': f"{res['active_alerts']} aturan kesehatan aktif dari {res['devices']} reader V2", **res}
