"""PREP-D1 — pembangun envelope kontrak 2.1 (MURNI: tanpa DB/HTTP) untuk simulator lintasan, skrip
`scripts/rfid_v2_simulate.py`, tes, dan acuan paket E (agent Java 0.5).

Satu lintasan = beberapa `EventsRequest` (GpiEdge + TagSummary) lalu satu `PassageClose`. Gate satu arah:
A = mulut masuk, B = mulut keluar. Nilai RSSI/waktu = angka contoh, bukan hasil kalibrasi.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

STRONG_RSSI = -48.0
WEAK_RSSI = -79.0
SCENARIOS = {
    'full_load': ('GREEN', 'Muatan penuh lewat: semua roll dokumen kuat, sinar A→B lalu keluar.'),
    'partial_trip': ('GREEN', 'Dua trip satu dokumen (sesi bertahap): trip 1 separuh roll, trip 2 sisanya.'),
    'reversed': ('CANCELLED', 'Stacker masuk lalu mundur sebelum roll terbaca kuat (B pulih dulu, A terakhir).'),
    'reversed_with_rolls': ('REVIEW', 'Stacker berisi roll dokumen kuat lalu mundur → perlu diperiksa.'),
    'empty': ('CANCELLED', 'Orang/forklift kosong memotong sinar: 0 tag → batal tanpa alarm.'),
    'foreign_roll': ('RED', 'Roll lain (bukan anggota dokumen) ikut terbaca kuat → merah terkunci.'),
    'quarantine_roll': ('RED', 'Roll karantina ikut terbaca kuat → merah terkunci.'),
    'background_tag': ('GREEN', 'Tag rak latar terbaca kuat tetapi ditandai latar → diabaikan.'),
    'overflow': ('REVIEW', 'Bukti melewati kapasitas lintasan → luapan (kuning).'),
    'sensor_fault': ('REVIEW', 'Photo-eye rusak: lintasan dibuka cadangan RF → kuning sampai terkalibrasi.'),
}


def _ts(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def summary(passage_id: str, epc: str, antenna: str, peak: float, t0: datetime, mono0: int,
            in_background: Optional[bool] = False, count: int = 8, offset_ms: int = 600) -> Dict[str, Any]:
    first, last = t0 + timedelta(milliseconds=offset_ms), t0 + timedelta(milliseconds=offset_ms + 1500)
    buckets = [{'t_off': offset_ms + i * 250, 'n': max(1, count // 6), 'max_rssi': round(peak - abs(i - 3) * 2.5, 1)}
               for i in range(6)]
    return {'summary_id': f'{passage_id}:{epc}:{antenna}', 'raw_epc': epc, 'epc': epc, 'antenna': str(antenna),
            'first_seen': _ts(first), 'last_seen': _ts(last), 'first_seen_mono': mono0 + offset_ms,
            'last_seen_mono': mono0 + offset_ms + 1500, 'peak_rssi': peak, 't_peak': _ts(first + timedelta(milliseconds=750)),
            't_peak_mono': mono0 + offset_ms + 750, 'count': count, 'mean_rssi': round(peak - 4.0, 1),
            'buckets': buckets, 'in_background': in_background, 'time_quality': 'synced'}


def edge(passage_id: str, n: int, sensor: str, state: str, t: datetime, mono: int) -> Dict[str, Any]:
    return {'edge_id': f'{passage_id}:gpi:{n}', 'sensor': sensor, 'state': state, 't_mono': mono, 't_wall': _ts(t),
            'time_quality': 'synced'}


def build_passage(*, scenario: str, gate_id: str, config_version: str, hardware_profile_id: str, direction: str,
                  antennas: Sequence[str], doc_epcs: Sequence[str] = (), extra_strong: Sequence[str] = (),
                  background_epcs: Sequence[str] = (), passage_id: Optional[str] = None, boot_id: Optional[str] = None,
                  seq_start: int = 0, batch_size: int = 100, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Return {'passage_id', 'batches': [EventsRequest], 'close': PassageClose, 'expected': verdict}."""
    if scenario not in SCENARIOS:
        raise ValueError(f'Skenario tidak dikenal: {scenario}')
    pid = passage_id or f'sim-{scenario}-{uuid.uuid4().hex[:12]}'
    boot = boot_id or f'sim-boot-{uuid.uuid4().hex[:8]}'
    t_close = now or datetime.now(timezone.utc)
    t0 = t_close - timedelta(milliseconds=6000)
    mono0 = 5_000_000
    ants = [str(a) for a in antennas][:3] or ['1']
    reversed_ = scenario in ('reversed', 'reversed_with_rolls')
    sensor_fault = scenario == 'sensor_fault'
    doc_peak = WEAK_RSSI if scenario == 'reversed' else STRONG_RSSI
    sums: List[Dict[str, Any]] = []
    for epc in doc_epcs:
        for i, ant in enumerate(ants[:2]):
            sums.append(summary(pid, epc, ant, doc_peak - i * 3, t0, mono0))
    for epc in extra_strong:
        sums.append(summary(pid, epc, ants[0], STRONG_RSSI, t0, mono0))
    for epc in background_epcs:
        sums.append(summary(pid, epc, ants[-1], STRONG_RSSI + 2, t0, mono0, in_background=True, count=40, offset_ms=0))
    edges: List[Dict[str, Any]] = []
    beam = {'a_blocked': None, 'b_blocked': None, 'a_cleared': None, 'b_cleared': None}
    if not sensor_fault:
        order = [('A', 'blocked', 3000), ('B', 'blocked', 4100), ('B', 'clear', 4700), ('A', 'clear', 5200)] if reversed_ \
            else [('A', 'blocked', 3000), ('B', 'blocked', 4100), ('A', 'clear', 4800), ('B', 'clear', 5600)]
        for n, (sensor, state, ms) in enumerate(order):
            t = t0 + timedelta(milliseconds=ms)
            edges.append(edge(pid, n, sensor, state, t, mono0 + ms))
            beam[f"{sensor.lower()}_{'blocked' if state == 'blocked' else 'cleared'}"] = _ts(t)
    batches, seq = [], seq_start
    chunks = [sums[i:i + batch_size] for i in range(0, len(sums), batch_size)] or [[]]
    for i, chunk in enumerate(chunks):
        body = {'schema_version': 2, 'batch_id': f'{pid}:b{i}', 'mode': 'live', 'config_version': config_version,
                'context': {'kind': 'gate', 'logical_gate_id': gate_id, 'local_passage_id': pid}, 'events': [],
                'seq': seq, 'boot_id': boot, 'sent_at': _ts(t_close)}
        if chunk:
            body['tag_summaries'] = chunk
        if i == 0 and edges:
            body['gpi_edges'] = edges
        if chunk or body.get('gpi_edges'):
            batches.append(body)
            seq += 1
    close = {'logical_gate_id': gate_id, 'config_version': config_version, 'mode': 'live',
             'closing_captured_at': _ts(t_close), 'boundary_reason': 'cancelled' if reversed_ else 'sensor',
             'last_event_id': None, 'observed_event_count': 0, 'capture_complete': True, 'direction': direction,
             'direction_evidence': {'source': 'fixed_profile', 'profile_binding_id': hardware_profile_id, 'sensor_sequence': []},
             'open_reason': 'RF_FALLBACK' if sensor_fault else 'BEAM_A',
             'close_reason': 'SENSOR_FAULT' if sensor_fault else ('REVERSED' if reversed_ else 'EXITED'),
             'window_start': _ts(t0), 'beam_times': beam, 'pre_buffer_ms': 3000, 'tail_ms': 1500,
             'observed_summary_count': len(sums), 'observed_edge_count': len(edges),
             'sensor_health': 'fault' if sensor_fault else 'ok', 'seq': seq, 'boot_id': boot}
    return {'passage_id': pid, 'batches': batches, 'close': close, 'expected': SCENARIOS[scenario][0],
            'boot_id': boot, 'next_seq': seq + 1}
