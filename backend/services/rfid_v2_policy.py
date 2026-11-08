"""PREP-D1 — kebijakan keputusan lintasan gate V2 (aturan bisnis tetap di `gate_evaluator`).

K-RFID-09 (pemilik, 8 Nov 2026): **RED terkunci HANYA untuk pelanggaran nyata** — EPC bukan anggota dokumen, roll
karantina/ditahan, sudah keluar/REPLAY, dokumen batal, salah gudang/tujuan, EPC asing bersinyal kuat (bila skor
tersedia). Roll kurang / capture tidak lengkap / waktu tak tervalidasi / tanpa manifest / backfill / luapan /
cadangan RF = **REVIEW (kuning) tanpa kunci**. Semua alasan disimpan (`reasons[]`), verdict = yang terberat.
K-RFID-10: tiap lintasan dinilai terhadap SISA roll dokumen; roll yang belum lewat dinilai saat dokumen ditutup.
Lintasan kosong (0 EPC relevan) / mundur-batal tanpa roll dokumen = CANCELLED tanpa alarm.

Kelas EPC per lintasan: `background` (agent menandai daftar latar) · `weak` (RSSI puncak < ambang antena) ·
`strong` · `unscored` (tanpa RSSI — diperlakukan seperti kuat, kecuali EPC asing → REVIEW). Hanya strong/unscored
yang "relevan"; weak & background dicatat, tidak pernah alarm dan tidak pernah diklaim lewat.
"""
import asyncio
from typing import Any, Dict, List, Optional, Tuple

from db import db
from services import gate_evaluator as ge
from services import rfid_v2_params as params_mod
from services import rfid_v2_sources as sources

RED, REVIEW, INFO = 'RED', 'REVIEW', 'INFO'
_RANK = {RED: 3, REVIEW: 2, INFO: 1}
# Alasan konteks dokumen yang membuat klaim crossing TIDAK boleh dipasang walau barang jalan.
NO_CLAIM = {'MANIFEST_CHANGED', 'SOURCE_NOT_ACTIVE', 'NO_MANIFEST', 'DIRECTION_UNVERIFIED', 'PASSAGE_TIMEOUT'}
ACTIONS = {
    'GREEN': 'Loloskan — semua roll kuat milik dokumen aktif dan belum pernah lewat.',
    'REVIEW': 'Barang boleh jalan — lintasan masuk antrean periksa (kuning, gate tidak terkunci).',
    'RED': 'Tahan barang — pelanggaran; gate terkunci sampai diperiksa dan diakui di ERP.',
    'CANCELLED': 'Lintasan kosong/batal — tidak ada tindakan.',
}
INDICATOR = {'GREEN': 'GREEN', 'REVIEW': 'YELLOW', 'RED': 'RED', 'CANCELLED': 'OFF', 'UNKNOWN': 'OFF'}
ROLL_FIELDS = {'_id': 0, 'id': 1, 'roll_no': 1, 'status': 1, 'active_movement': 1, 'journey': 1, 'bucket_ref': 1,
               'repair_open': 1, 'reserved_ref': 1, 'transfer_ref': 1, 'gate_exit': 1, 'warehouse_id': 1}


class Reasons:
    def __init__(self):
        self.items: List[Dict[str, Any]] = []

    def add(self, level: str, code: str, message: str = '', epc: Optional[str] = None,
            roll_id: Optional[str] = None, source_id: Optional[str] = None) -> None:
        self.items.append({'code': code, 'level': level, 'message': message, 'epc': epc,
                           'roll_id': roll_id, 'source_id': source_id})

    def demote(self, levels=(RED, REVIEW)) -> None:
        for item in self.items:
            if item['level'] in levels:
                item['level'] = INFO

    def worst(self) -> Optional[str]:
        return max((i['level'] for i in self.items), key=_RANK.get, default=None)

    def has(self, *codes: str) -> bool:
        return any(i['code'] in codes and i['level'] != INFO for i in self.items)

    def codes(self) -> List[str]:
        ordered = sorted(enumerate(self.items), key=lambda p: (-_RANK[p[1]['level']], p[0]))
        return list(dict.fromkeys(i['code'] for _, i in ordered))

    def export(self, cap: int = 200) -> List[Dict[str, Any]]:
        ordered = sorted(enumerate(self.items), key=lambda p: (-_RANK[p[1]['level']], p[0]))
        return [i for _, i in ordered][:cap]


def epc_evidence(events: List[Dict[str, Any]], summaries: List[Dict[str, Any]], params: Dict[str, Any]):
    """Gabungkan bukti per EPC dari event mentah (0.4) dan ringkasan (2.1). Return (evidence, quarantined)."""
    ev: Dict[str, Dict[str, Any]] = {}
    quarantined = 0

    def slot(epc):
        return ev.setdefault(epc, {'count': 0, 'antennas': {}, 'bg': [], 'scored': False})

    def peak(x, antenna, value):
        if value is None:
            x['antennas'].setdefault(antenna, None)
            return
        x['scored'] = True
        cur = x['antennas'].get(antenna)
        x['antennas'][antenna] = value if cur is None else max(cur, value)

    for row in events:
        e = row['event']
        if row.get('quarantine'):
            quarantined += 1
            continue
        if e.get('epc'):
            x = slot(e['epc'])
            x['count'] += 1
            peak(x, e.get('antenna'), e.get('rssi_dbm'))
    for row in summaries:
        s = row['summary']
        if row.get('quarantine'):
            quarantined += 1
            continue
        if s.get('epc'):
            x = slot(s['epc'])
            x['count'] += int(s.get('count') or 0)
            x['bg'].append(s.get('in_background'))
            peak(x, s.get('antenna'), s.get('peak_rssi'))
    for epc, x in ev.items():
        background = bool(x['bg']) and all(b is True for b in x['bg'])
        strong = any(v is not None and v >= params_mod.strong_threshold(params, a) for a, v in x['antennas'].items())
        x['peak'] = max((v for v in x['antennas'].values() if v is not None), default=None)
        x['cls'] = 'background' if background else ('unscored' if not x['scored'] else ('strong' if strong else 'weak'))
    return ev, quarantined


async def _lookup(epcs: List[str]):
    tags = {t['epc']: t for t in await db.rfid_tags.find({'epc': {'$in': epcs}, 'status': 'active'},
                                                         {'_id': 0, 'epc': 1, 'roll_id': 1}).to_list(len(epcs) + 1)}
    roll_ids = list({t['roll_id'] for t in tags.values() if t.get('roll_id')})
    rolls = {r['id']: r for r in await db.inventory_rolls.find({'id': {'$in': roll_ids}}, ROLL_FIELDS).to_list(len(roll_ids) + 1)}
    return tags, rolls


async def _gather(items, fn, size: int = 25):
    out = []
    for i in range(0, len(items), size):
        out += await asyncio.gather(*[fn(x) for x in items[i:i + size]])
    return out


async def decide(*, body: Dict[str, Any], gate: Dict[str, Any], params: Dict[str, Any], pid: str,
                 warehouse: str, events: List[Dict[str, Any]], summaries: List[Dict[str, Any]],
                 binding_entries: Optional[List[Dict[str, Any]]], binding_reasons: List[Tuple[str, str, str]],
                 transport_reasons: List[Tuple[str, str, str]], overflow: int) -> Dict[str, Any]:
    R = Reasons()
    direction = body.get('direction') if body.get('direction') in ('in', 'out') else (
        gate['direction'] if gate['direction'] in ('in', 'out') else None)
    ev, quarantined = epc_evidence(events, summaries, params)
    relevant = [e for e, x in ev.items() if x['cls'] in ('strong', 'unscored')]
    weak = [e for e, x in ev.items() if x['cls'] == 'weak']
    background = [e for e, x in ev.items() if x['cls'] == 'background']
    tags, rolls = await _lookup(list(ev)) if ev else ({}, {})
    binding_mode, entries, roll_sources, invalid = 'none', [], {}, {}
    if binding_entries is not None:
        binding_mode, entries = 'manual', binding_entries
        roll_sources = {rid: e['source_ref'] for e in entries for rid in e['roll_ids']}
    elif params.get('auto_match') and direction:
        known = [rolls[tags[e]['roll_id']] for e in relevant if e in tags and tags[e].get('roll_id') in rolls]
        if known:
            auto = await sources.auto_sources(known, warehouse, direction)
            binding_mode, entries, roll_sources, invalid = 'auto', auto['entries'], auto['roll_sources'], auto['invalid']
    matched: List[Tuple[str, Dict[str, Any]]] = []
    counts = {'observed_unique': len(relevant), 'matched': 0, 'missing': 0, 'extra': 0, 'unknown': quarantined,
              'pending': 0, 'weak': len(weak), 'background': len(background), 'overflow': overflow, 'already_passed': 0}

    async def judge(epc):
        x, tag = ev[epc], tags.get(epc)
        roll = rolls.get(tag['roll_id']) if tag else None
        if not roll:
            counts['unknown'] += 1
            if x['cls'] == 'strong':
                R.add(RED, 'UNKNOWN_EPC', f'EPC asing bersinyal kuat ({x["peak"]} dBm) — tag tidak dikenal/tidak aktif.', epc=epc)
            else:
                R.add(REVIEW, 'UNKNOWN_EPC_UNSCORED', 'EPC tidak dikenal tanpa skor sinyal — periksa fisik.', epc=epc)
            return
        label = roll.get('roll_no') or roll['id']
        src = roll_sources.get(roll['id'])
        if binding_mode == 'manual' and not src:
            res = await ge.evaluate(direction, warehouse, roll, crossing_passage_id=pid)
            counts['extra'] += 1
            R.add(RED, 'NOT_IN_DOCUMENT', f'Roll {label} tidak tercantum di dokumen yang dipilih.', epc=epc, roll_id=roll['id'])
            if res['result'] == 'red':
                R.add(RED, res['code'], res['reason'], epc=epc, roll_id=roll['id'])
            return
        res = await ge.evaluate(direction, warehouse, roll, crossing_passage_id=pid, expected_source=src)
        sid = (src or {}).get('source_id')
        if res['result'] == 'green' and src:
            matched.append((roll['id'], src))
        elif res['result'] == 'green':
            counts['extra'] += 1
            code = 'NO_MANIFEST' if binding_mode == 'none' else invalid.get(roll['id'], 'SOURCE_UNSUPPORTED')
            R.add(REVIEW, code, f'Roll {label}: {res["reason"]} — dokumen belum terikat/didukung di gate V2.', epc=epc, roll_id=roll['id'])
        elif res['result'] == 'red':
            counts['extra'] += 1
            if res['code'] == 'REPLAY_EXIT':
                counts['already_passed'] += 1
            R.add(RED, res['code'], f'Roll {label}: {res["reason"]}', epc=epc, roll_id=roll['id'], source_id=sid)
        else:
            counts['extra'] += 1
            R.add(REVIEW, res.get('code') or 'LOCAL_ROLL', f'Roll {label}: {res["reason"]}', epc=epc, roll_id=roll['id'])

    if direction:
        await _gather(relevant, judge)
    else:
        R.add(REVIEW, 'DIRECTION_UNVERIFIED', 'Arah lintasan tidak diketahui — roll tidak dinilai.')
    counts['matched'] = len(matched)
    if quarantined:
        R.add(REVIEW, 'QUARANTINED_EVIDENCE', f'{quarantined} bacaan dikarantina (EPC/antena tidak valid) — periksa bukti.')
    for code, level, message in transport_reasons:
        R.add(level, code, message)
    close_reason, open_reason = body.get('close_reason'), body.get('open_reason')
    cancelled_like = close_reason in ('REVERSED', 'ABORTED') or body.get('boundary_reason') == 'cancelled'
    timeout = close_reason == 'TIMEOUT' or body.get('boundary_reason') == 'max_duration'
    empty = not relevant and not quarantined
    if relevant:
        for code, level, message in binding_reasons:
            R.add(level, code, message)
        if binding_mode == 'none' and not R.has('NO_MANIFEST') and not matched:
            R.add(REVIEW, 'NO_MANIFEST', 'Tidak ada dokumen terikat/auto-cocok untuk lintasan ini.')
    if timeout:
        R.add(REVIEW, 'PASSAGE_TIMEOUT', 'Lintasan terbuka melewati batas waktu — barang mungkin berhenti di gate.')
    if close_reason == 'SENSOR_FAULT' or open_reason == 'RF_FALLBACK' or body.get('sensor_health') == 'fault':
        if params.get('rf_fallback_review', True):
            R.add(REVIEW, 'SENSOR_FAULT' if close_reason == 'SENSOR_FAULT' or body.get('sensor_health') == 'fault'
                  else 'RF_FALLBACK', 'Photo-eye tidak dipakai/rusak — lintasan ditentukan logika cadangan RF.')
    cancelled = False
    if cancelled_like:
        carried = bool(matched) or R.worst() == RED or any(i['roll_id'] for i in R.items)
        R.demote()
        if carried:
            R.add(REVIEW, 'REVERSED_WITH_ROLLS' if close_reason != 'ABORTED' else 'ABORTED_WITH_ROLLS',
                  'Muatan berisi roll dokumen/roll lain mundur atau batal di gate — periksa posisi barang.')
        else:
            cancelled = True
            R.add(INFO, 'PASSAGE_CANCELLED', 'Lintasan mundur/batal tanpa roll dokumen — tanpa alarm.')
    elif empty:
        keep = overflow > 0
        R.demote()
        if keep:
            R.add(REVIEW, 'CAPTURE_OVERFLOW', 'Lintasan melewati kapasitas bukti — bacaan lain disimpan di luapan.')
        else:
            cancelled = True
            R.add(INFO, 'EMPTY_PASSAGE', 'Lintasan kosong (orang/forklift kosong) — tanpa transaksi & tanpa alarm.')
    worst = R.worst()
    if cancelled:
        verdict = 'CANCELLED'
    elif worst == RED:
        verdict = 'RED'
    elif worst == REVIEW:
        verdict = 'REVIEW'
    elif matched:
        verdict = 'GREEN'
    else:
        verdict = 'REVIEW'
        R.add(REVIEW, 'NO_DOCUMENT_ROLLS', 'Tidak ada roll dokumen yang terbaca kuat.')
    claimable = (verdict in ('GREEN', 'REVIEW') and bool(matched) and not cancelled_like and not R.has(*NO_CLAIM))
    return {'verdict': verdict, 'reasons': R, 'matched': matched, 'entries': entries, 'binding_mode': binding_mode,
            'counts': counts, 'claimable': claimable, 'direction': direction,
            'weak': weak[:50], 'background': background[:50]}


def finalize(result: Dict[str, Any]) -> Dict[str, Any]:
    """Field keputusan turunan (reason_code utama, indikator, aksi) dari hasil `decide` (setelah klaim)."""
    R: Reasons = result['reasons']
    verdict = result['verdict']
    codes = R.codes()
    primary = 'MANIFEST_MATCH' if verdict == 'GREEN' else next(
        (i['code'] for i in R.export() if i['level'] != INFO), codes[0] if codes else 'NO_EVIDENCE')
    if verdict == 'GREEN' and 'MANIFEST_MATCH' not in codes:
        codes = ['MANIFEST_MATCH'] + codes
    return {'reason_code': primary, 'reason_codes': codes, 'reasons': R.export(), 'indicator': INDICATOR[verdict],
            'action': ACTIONS[verdict], 'latched': verdict == 'RED'}
