#!/usr/bin/env python3
"""PREP-H — uji beban & ketahanan jalur gate RFID V2 (kontrak 2.1) lewat endpoint DEVICE sungguhan.

Dijalankan di DALAM kontainer backend uji (butuh dependensi backend + akses Mongo), TIDAK PERNAH ke DB produksi:
    cd /app/backend && DB_NAME=kn_load python /app/scripts/rfid_v2_loadtest.py <mode> --confirm-db kn_load [opsi]

Mode
  synth     data sintetis sebesar produksi di DB salinan: roll + tag (ratusan ribu), riwayat lintasan, ringkasan,
            tepi sinar, klaim crossing, buku transaksi, sesi dokumen, SJ/transfer/PA lama, bacaan gate lama.
  run       lintasan lewat HTTP (`/api/rfid/v2/events` + `/close`, X-Device-Key) memakai
            `services/rfid_v2_envelope.build_passage`: `big` (1 lintasan s.d. 2.000 roll per jenis dokumen),
            `concurrent` (4 gate bersamaan), `sustained` (beban berkelanjutan setara 6.000 roll/hari dengan asumsi
            puncak — lihat ASUMSI di bawah). Mengukur p50/p95/p99 events & close, waktu selesai transaksi gate,
            CPU/RAM kontainer backend (cgroup) & Mongo (serverStatus), query lambat (profiler Mongo).
  explain   `explain('executionStats')` untuk query jalur gate pada volume sintetis (rencana, dokumen diperiksa).
  fault     uji kegagalan: close ganda bersamaan, backend dimatikan di tengah close lalu close diulang, pekerja
            transaksi mati di tengah, jaringan putus saat batch events (envelope + seq).

ASUMSI beban (pemilik 9 Nov 2026: ±6.000 roll/hari TOTAL, jam sibuk belum diketahui) — ditulis terbuka:
  * puncak = 30 % volume harian dalam 1 jam (1.800 roll/jam) — pola gudang tekstil: muat pagi & sore;
  * rata-rata muatan stacker ±50 roll (180×180 cm, 7 lapis silang ±7 roll/lapis), 20 % muatan kecil 1–3 roll,
    10 % muatan besar 100–200 roll, plus lintasan kosong (orang/forklift) sebanyak lintasan bermuatan;
  * 4 gate aktif bersamaan (2 pasang IN/OUT), agent mem-poll gate-state 1×/dtk & telemetry 30 dtk per gate;
  * `--rate-multiplier` menjalankan beban berkali lipat puncak (uji ruang tumbuh), dicatat di laporan.

Keamanan: menolak MONGO_URL bukan localhost/127.0.0.1 dan menolak bila `--confirm-db` ≠ DB_NAME. Semua data uji
bertanda `LT_<tag>`; mode synth bertanda `SY_<tag>`. Tidak ada penghapusan massal di luar data bertanda.
"""
import argparse
import asyncio
import copy
import gzip
import json
import os
import random
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

SAFE_HOSTS = ('localhost', '127.0.0.1')
ENT = 'ent_ksc'
FIXTURE = BACKEND / 'tests/fixtures/u300_contract.json'
LIMITS = {'max_events': 100, 'max_body_bytes': 512000, 'max_queue_bytes': 64000000}   # templat commissioning
CONFIG_VERSION = 'lt-v1'


def guard(args):
    url = os.environ.get('MONGO_URL', '')
    host = urlparse(url).hostname
    if host not in SAFE_HOSTS:
        sys.exit(f'Ditolak: MONGO_URL harus localhost/127.0.0.1 (sekarang {host!r}).')
    if not args.confirm_db or args.confirm_db != os.environ.get('DB_NAME'):
        sys.exit('Ditolak: --confirm-db wajib sama persis dengan DB_NAME (DB salinan uji).')


def iso(t=None):
    return (t or datetime.now(timezone.utc)).isoformat().replace('+00:00', 'Z')


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 1)


def stats(values):
    if not values:
        return {'n': 0}
    return {'n': len(values), 'p50': pct(values, .5), 'p95': pct(values, .95), 'p99': pct(values, .99),
            'max': round(max(values), 1), 'mean': round(statistics.mean(values), 1)}


# ─── Sampler sumber daya (cgroup kontainer backend + serverStatus Mongo) ─────────────────────────────
class Sampler:
    def __init__(self, db, period=1.0):
        self.db, self.period, self.rows, self._task = db, period, [], None

    @staticmethod
    def _cg(name):
        try:
            return Path('/sys/fs/cgroup/' + name).read_text()
        except OSError:
            return ''

    def _be(self):
        usage = 0
        for line in self._cg('cpu.stat').splitlines():
            if line.startswith('usage_usec'):
                usage = int(line.split()[1])
        mem = self._cg('memory.current').strip()
        return usage, int(mem) if mem.isdigit() else 0

    async def _mongo(self):
        st = await self.db.client.admin.command('serverStatus')
        ex = st.get('extra_info') or {}
        cpu = int(ex.get('user_time_us') or 0) + int(ex.get('system_time_us') or 0)
        wt = (st.get('wiredTiger') or {}).get('cache') or {}
        return cpu, int((st.get('mem') or {}).get('resident') or 0), int(wt.get('bytes currently in the cache') or 0)

    async def _loop(self):
        prev = None
        while True:
            t = time.perf_counter()
            be_cpu, be_mem = self._be()
            mo_cpu, mo_res, mo_cache = await self._mongo()
            if prev:
                dt = t - prev[0]
                self.rows.append({'be_cpu_pct': round((be_cpu - prev[1]) / 1e6 / dt * 100, 1), 'be_mem_mb': round(be_mem / 1e6, 1),
                                  'mongo_cpu_pct': round((mo_cpu - prev[2]) / 1e6 / dt * 100, 1), 'mongo_res_mb': mo_res,
                                  'mongo_cache_mb': round(mo_cache / 1e6, 1)})
            prev = (t, be_cpu, mo_cpu)
            await asyncio.sleep(self.period)

    def start(self):
        self._task = asyncio.ensure_future(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if not self.rows:
            return {}
        out = {}
        for k in self.rows[0]:
            vals = [r[k] for r in self.rows]
            out[k] = {'mean': round(statistics.mean(vals), 1), 'max': max(vals), 'p95': pct(vals, .95)}
        out['samples'] = len(self.rows)
        return out


# ─── Profiler Mongo ─────────────────────────────────────────────────────────────────────────────────
async def profiler_on(db, slowms):
    await db.command({'profile': 0})
    try:
        await db.drop_collection('system.profile')
        await db.create_collection('system.profile', capped=True, size=64_000_000)   # bawaan 1 MB terlalu kecil
    except Exception:  # noqa: BLE001
        pass
    await db.command({'profile': 1, 'slowms': int(slowms)})


async def profiler_report(db, top=25):
    await db.command({'profile': 0})
    rows = await db['system.profile'].aggregate([
        {'$match': {'ns': {'$not': {'$regex': r'\.system\.'}}}},
        {'$group': {'_id': {'ns': '$ns', 'op': '$op', 'plan': '$planSummary',
                            'shape': {'$map': {'as': 'f', 'in': '$$f.k', 'input': {'$objectToArray': {'$ifNull': [
                                '$command.filter', {'$ifNull': ['$command.q', {'$ifNull': [
                                    '$originatingCommand.filter', {}]}]}]}}}}},
                    'n': {'$sum': 1}, 'avg_ms': {'$avg': '$millis'}, 'max_ms': {'$max': '$millis'},
                    'docs': {'$avg': '$docsExamined'}, 'keys': {'$avg': '$keysExamined'},
                    'nret': {'$avg': '$nreturned'}}},
        {'$sort': {'n': -1}}, {'$limit': 200}]).to_list(200)
    out = []
    for r in rows:
        key = r['_id'] or {}
        shape = sorted(key.get('shape') or [])
        out.append({'ns': str(key.get('ns') or '').split('.', 1)[-1], 'op': key.get('op'), 'plan': key.get('plan'),
                    'filter_keys': shape, 'n': r['n'], 'avg_ms': round(r['avg_ms'] or 0, 1), 'max_ms': r['max_ms'],
                    'docs_examined_avg': round(r['docs'] or 0), 'keys_examined_avg': round(r['keys'] or 0),
                    'returned_avg': round(r['nret'] or 0)})
    out.sort(key=lambda x: -(x['n'] * x['avg_ms']))
    return out[:top]


# ─── Data uji (perlengkapan lintasan) ───────────────────────────────────────────────────────────────
class Fixture:
    """Gudang uji bergate + 4 reader (2 pasang IN/OUT) + dokumen aktif berisi roll bertag."""

    def __init__(self, db, tag):
        self.db, self.tag = db, tag
        self.site = f'site_LT_{tag}'
        self.wh_src, self.wh_gate = f'wh_LT_{tag}_src', f'wh_LT_{tag}_gate'
        self.devices = {k: f'dev_LT_{tag}_{k}' for k in ('in1', 'out1', 'in2', 'out2')}
        self.keys = {k: f'dk_LT_{tag}_{k}' for k in self.devices}
        self.n = 0
        self.product = None
        self.hw = None

    def direction(self, k):
        return 'in' if k.startswith('in') else 'out'

    async def setup(self):
        from services.rfid_ingest_service import hash_device_key
        from services.rfid_v2_core import validate
        from services.rfid_v2_common import digest
        db = self.db
        p = await db.products.find_one({'status': {'$ne': 'inactive'}, 'base_unit': 'meter'}, {'_id': 0, 'id': 1})
        if not p:
            sys.exit('DB tanpa produk satuan meter.')
        self.product = p['id']
        gate_cfg = {'has_gate': True, 'physical_gate': True, 'confirm_mode': 'gate',
                    'pairs': [{'in_device_id': self.devices['in1'], 'out_device_id': self.devices['out1'], 'layout': 'terpisah'},
                              {'in_device_id': self.devices['in2'], 'out_device_id': self.devices['out2'], 'layout': 'terpisah'}]}
        await db.warehouses.insert_many([
            {'id': self.wh_src, 'name': f'Uji beban asal {self.tag}', 'code': f'LTS{self.tag}', 'roles': ['transit', 'receiving'],
             'site_id': self.site, 'sharing_mode': 'shared', 'active': True, 'gate_config': {'has_gate': False}},
            {'id': self.wh_gate, 'name': f'Uji beban gate {self.tag}', 'code': f'LTG{self.tag}', 'roles': ['storage'],
             'site_id': self.site, 'sharing_mode': 'shared', 'active': True, 'gate_config': gate_cfg}])
        base = json.loads(FIXTURE.read_text())['DeviceConfig']
        self.hw = base['hardware_profile_id']
        for k, dev in self.devices.items():
            await db.rfid_devices.insert_one({'id': dev, 'code': f'LT-{k}-{self.tag}', 'name': f'Gate uji beban {k}',
                                              'type': 'gate', 'direction': self.direction(k), 'warehouse_id': self.wh_gate,
                                              'enabled': True, 'status': 'online',
                                              'api_key_hash': hash_device_key(self.keys[k])})
            cfg = copy.deepcopy(base)
            cfg.update(device_id=dev, warehouse_id=self.wh_gate, site_id=self.site, config_version=CONFIG_VERSION,
                       limits=dict(LIMITS))
            g = cfg['logical_gates'][0]
            g.update(logical_gate_id='G1', warehouse_id=self.wh_gate, site_id=self.site, direction=self.direction(k),
                     antenna_ids=['1', '2', '3'], completion_basis='document_session')
            validate('DeviceConfig', cfg)
            saved = copy.deepcopy(cfg)
            saved.pop('server_time', None)
            await db.rfid_v2_configs.insert_one({'_id': digest([dev, CONFIG_VERSION]), 'config': saved,
                                                 'actor_id': 'loadtest', 'at': iso(), 'device_id': dev})
            await db.rfid_devices.update_one({'id': dev}, {'$set': {'v2_config_version': CONFIG_VERSION,
                                                                    'protocol': 'v2', 'protocol_at': iso()}})

    async def rolls(self, n, wh, status, **extra):
        out, rolls, tags = [], [], []
        for _ in range(n):
            self.n += 1
            i = self.n
            rid, tid = f'roll_LT_{self.tag}_{i}', f'tag_LT_{self.tag}_{i}'
            epc = f'E2{self.tag.upper()}{i:016X}'
            tags.append({'id': tid, 'epc': epc, 'roll_id': rid, 'status': 'active', 'warehouse_id': wh,
                         'created_at': '2026-11-01T00:00:00+00:00'})
            rolls.append({'id': rid, 'roll_no': f'LT{self.tag}{i}', 'product_id': self.product, 'warehouse_id': wh,
                          'owner_entity_id': ENT, 'status': status, 'length_remaining': 30.0, 'length_initial': 30.0,
                          'unit': 'meter', 'grade': 'A', 'lot': 'L-LT', 'rfid_tag_id': tid, 'bin_id': None,
                          'active_movement': None, 'length_reserved': 0, 'length_reservations': [],
                          'journey': {'stage': 'tag_verified', 'verified_tag_id': tid, 'routing': 'store',
                                      'updated_at': '2026-11-02T00:00:00+00:00'}, **extra})
            out.append({'id': rid, 'epc': epc, 'roll_no': f'LT{self.tag}{i}'})
        for i in range(0, n, 5000):
            await self.db.rfid_tags.insert_many(tags[i:i + 5000])
            await self.db.inventory_rolls.insert_many(rolls[i:i + 5000])
        return out

    async def shipment(self, n):
        self.n += 1
        so, sid = f'so_LT_{self.tag}_{self.n}', f'shp_LT_{self.tag}_{self.n}'
        await self.db.sales_orders.insert_one({'id': so, 'number': so, 'status': 'in_progress', 'entity_id': ENT,
                                               'created_at': iso()})
        rs = await self.rolls(n, self.wh_gate, 'in_transit_sales', reserved_ref={'type': 'sales_order', 'id': so})
        await self.db.shipments.insert_one({'id': sid, 'shipment_no': f'SJ-LT-{self.tag}-{self.n}', 'order_id': so,
                                            'warehouse_id': self.wh_gate, 'status': 'dispatched', 'entity_id': ENT,
                                            'created_at': iso(), 'rolls': [{'roll_id': r['id']} for r in rs]})
        return {'type': 'shipment', 'id': sid, 'rolls': rs}

    async def transfer(self, n):
        self.n += 1
        tid = f'trf_LT_{self.tag}_{self.n}'
        rs = await self.rolls(n, self.wh_src, 'in_transit_transfer', reserved_ref={'type': 'wh_transfer', 'id': tid})
        await self.db.warehouse_transfers.insert_one({
            'id': tid, 'code': f'TRF-LT-{self.tag}-{self.n}', 'status': 'dispatched', 'transfer_kind': 'warehouse',
            'source_warehouse_id': self.wh_src, 'dest_warehouse_id': self.wh_gate, 'owner_entity_id': ENT,
            'entity_id': ENT, 'created_at': iso(),
            'items': [{'product_id': self.product, 'unit': 'meter',
                       'rolls': [{'roll_id': r['id'], 'roll_no': r['roll_no'], 'length': 30.0} for r in rs]}]})
        return {'type': 'wh_transfer', 'id': tid, 'rolls': rs}

    async def putaway(self, n):
        from services import putaway_order_service as pa
        rs = await self.rolls(n, self.wh_src, 'available')
        order = await pa.create_order(self.wh_src, self.wh_gate, [r['id'] for r in rs], [ENT], 'Uji beban')
        await pa.dispatch(order['id'], [ENT])
        return {'type': 'putaway', 'id': order['id'], 'rolls': rs}


# ─── Klien reader (HTTP) ────────────────────────────────────────────────────────────────────────────
class Reader:
    def __init__(self, http, base, fx, k, rec):
        self.http, self.base, self.fx, self.k, self.rec = http, base, fx, k, rec
        self.key = fx.keys[k]
        self.seq = 0
        self.boot = f'lt-boot-{uuid.uuid4().hex[:8]}'

    def build(self, epcs, scenario='full_load'):
        from services import rfid_v2_envelope as env
        from services.rfid_v2_common import compact_size
        built = env.build_passage(scenario=scenario, gate_id='G1', config_version=CONFIG_VERSION,
                                  hardware_profile_id=self.fx.hw, direction=self.fx.direction(self.k),
                                  antennas=['1', '2', '3'], doc_epcs=epcs, passage_id=f'lt-{uuid.uuid4().hex[:16]}',
                                  boot_id=self.boot, seq_start=self.seq, batch_size=400)
        self.seq = built['next_seq']
        for b in built['batches']:
            if compact_size(b) > LIMITS['max_body_bytes']:
                raise RuntimeError('batch melewati max_body_bytes — kecilkan batch_size')
        built['bytes'] = sum(compact_size(b) for b in built['batches']) + compact_size(built['close'])
        return built

    async def post(self, kind, url, body, headers, timeout):
        t0 = time.perf_counter()
        try:
            r = await self.http.post(url, json=body, headers=headers, timeout=timeout)
            ms = (time.perf_counter() - t0) * 1000
            self.rec.add(kind, ms, r.status_code)
            return r
        except Exception as exc:  # noqa: BLE001 — batas waktu/klien putus dicatat sebagai galat
            self.rec.add(kind, (time.perf_counter() - t0) * 1000, 'timeout' if 'Timeout' in type(exc).__name__ else 'error')
            return None

    async def send_events(self, built, timeout=60, kind='events'):
        for body in built['batches']:
            r = await self.post(kind, f'{self.base}/api/rfid/v2/events', body, {'X-Device-Key': self.key}, timeout)
            if r is None or r.status_code != 200:
                return False
        return True

    async def close(self, built, timeout=60, kind='close'):
        if 'close_sent' not in built:   # close dikirim "sekarang"; close ULANG wajib isi sama (CLOSE_CONFLICT)
            built['close_sent'] = {**built['close'], 'closing_captured_at': iso()}
        body = built['close_sent']
        hdr = {'X-Device-Key': self.key, 'Idempotency-Key': 'c-' + built['passage_id']}
        r = await self.post(kind, f"{self.base}/api/rfid/v2/passages/{built['passage_id']}/close", body, hdr, timeout)
        return r

    async def passage(self, epcs, scenario='full_load', close_timeout=60):
        built = self.build(epcs, scenario)
        t0 = time.perf_counter()
        ok = await self.send_events(built)
        if not ok:
            return {'ok': False, 'stage': 'events', 'rolls': len(epcs)}
        r = await self.close(built, close_timeout)
        t_close = time.perf_counter()
        out = {'ok': bool(r is not None and r.status_code == 200), 'rolls': len(epcs), 'passage_id': built['passage_id'],
               'bytes': built['bytes'], 'tail_ms': round((t_close - t0) * 1000, 1), 'batches': len(built['batches'])}
        if r is not None:
            try:
                d = r.json()
            except ValueError:
                d = {}
            out.update(verdict=d.get('verdict'), status=r.status_code, reason_codes=(d.get('reason_codes') or [])[:5])
        out['t_close'] = t_close
        return out


class Recorder:
    def __init__(self):
        self.lat, self.status = {}, {}

    def add(self, kind, ms, status):
        self.lat.setdefault(kind, []).append(ms)
        self.status.setdefault(kind, {}).setdefault(str(status), 0)
        self.status[kind][str(status)] += 1

    def report(self):
        return {k: {**stats(v), 'status': self.status.get(k, {})} for k, v in self.lat.items()}


def _ts(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


async def wait_txn(db, fx, k, out, timeout=900):
    """Tunggu transaksi gate lintasan selesai (state done/error). Return ms dari keputusan dibuat (`decision.created_at`)
    s.d. transaksi tuntas (`gate_txn_at`) — sama artinya untuk kode lama (transaksi di dalam close) & baru (latar)."""
    from services.rfid_v2_common import digest
    if not out.get('passage_id'):
        return None
    pid = digest([fx.devices[k], out['passage_id']])
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        row = await db.rfid_v2_passages.find_one({'_id': pid}, {'gate_txn_state': 1, 'gate_txn_input': 1, 'gate_txn_at': 1,
                                                                'decision.created_at': 1, 'gate_txn_attempts': 1})
        if row and (row.get('gate_txn_state') in ('done', 'error') or (row.get('decision') and not row.get('gate_txn_input'))):
            out['txn_state'] = row.get('gate_txn_state')
            out['txn_attempts'] = row.get('gate_txn_attempts')
            a, b = _ts((row.get('decision') or {}).get('created_at')), _ts(row.get('gate_txn_at'))
            return round((b - a).total_seconds() * 1000, 1) if a and b else None
        await asyncio.sleep(0.05)
    out['txn_state'] = 'timeout'
    return None


async def doc_for(fx, k, n, kind=None):
    if fx.direction(k) == 'out':
        return await fx.shipment(n)
    if kind == 'putaway':
        return await fx.putaway(n)
    return await fx.transfer(n)


# ─── Skenario ───────────────────────────────────────────────────────────────────────────────────────
async def scenario_big(db, http, base, fx, sizes, kinds):
    out = []
    await warmup(db, http, base, fx)
    for kind in kinds:
        k = {'shipment': 'out1', 'wh_transfer': 'in1', 'putaway': 'in2'}[kind]
        for n in sizes:
            doc = await doc_for(fx, k, n, kind)
            rec = Recorder()
            reader = Reader(http, base, fx, k, rec)
            res = await reader.passage([r['epc'] for r in doc['rolls']], close_timeout=300)
            res['txn_ms'] = await wait_txn(db, fx, k, res)
            res.pop('t_close', None)
            out.append({'kind': kind, 'rolls': n, 'result': res, 'latency': rec.report()})
            print(f"[big] {kind} {n} roll → {res.get('verdict')} close {rec.report().get('close', {}).get('max')} ms, "
                  f"txn {res['txn_ms']} ms, {res['bytes']} byte", flush=True)
    return out


async def warmup(db, http, base, fx):
    """Satu lintasan kecil per gate (tidak diukur): profil/koneksi/halaman cache perangkat baru sudah hangat."""
    for k in fx.devices:
        doc = await doc_for(fx, k, 5)
        res = await Reader(http, base, fx, k, Recorder()).passage([r['epc'] for r in doc['rolls']])
        await wait_txn(db, fx, k, res, timeout=120)


async def scenario_concurrent(db, http, base, fx, n, rounds=1):
    recs = {k: Recorder() for k in fx.devices}
    results = []
    await warmup(db, http, base, fx)
    for _ in range(rounds):
        docs = {k: await doc_for(fx, k, n) for k in fx.devices}
        readers = {k: Reader(http, base, fx, k, recs[k]) for k in fx.devices}
        res = await asyncio.gather(*[readers[k].passage([r['epc'] for r in docs[k]['rolls']], close_timeout=300)
                                     for k in fx.devices])
        txn = await asyncio.gather(*[wait_txn(db, fx, k, r) for k, r in zip(fx.devices, res)])
        for k, r, t in zip(fx.devices, res, txn):
            r['txn_ms'] = t
            r.pop('t_close', None)
            results.append({'gate': k, **r})
    merged = Recorder()
    for r in recs.values():
        for kind, vals in r.lat.items():
            for v in vals:
                merged.add(kind, v, 'ok')
    print(f"[concurrent] 4 gate × {n} roll: close p95 {merged.report().get('close', {}).get('p95')} ms", flush=True)
    return {'rolls_per_gate': n, 'rounds': rounds, 'passages': results,
            'latency': merged.report(), 'per_gate': {k: r.report() for k, r in recs.items()}}


def load_size(rng):
    x = rng.random()
    if x < 0.20:
        return rng.randint(1, 3)
    if x < 0.30:
        return rng.randint(100, 200)
    return rng.randint(40, 60)


async def scenario_sustained(db, http, base, fx, minutes, multiplier, seed=7):
    """Beban setara 6.000 roll/hari dengan puncak 30 %/jam × `multiplier`, 4 gate, + polling agent & telemetry."""
    rng = random.Random(seed)
    peak_rolls_h = 6000 * 0.30 * multiplier
    mean_load = 0.2 * 2 + 0.1 * 150 + 0.7 * 50          # ≈ 50 roll / muatan
    loaded_per_h = peak_rolls_h / mean_load
    per_gate_interval = 3600 / (loaded_per_h / len(fx.devices))   # detik antar muatan per gate
    deadline = time.perf_counter() + minutes * 60
    rec = Recorder()
    passages = []
    stop = asyncio.Event()
    pool = {}

    async def ensure_pool(k, need):
        rolls = pool.setdefault(k, [])
        while len(rolls) < need:
            doc = await doc_for(fx, k, 300)
            rolls.extend([(doc, r) for r in doc['rolls']])

    async def gate_loop(k):
        reader = Reader(http, base, fx, k, rec)
        await asyncio.sleep(rng.random() * per_gate_interval)
        while time.perf_counter() < deadline:
            t_start = time.perf_counter()
            n = load_size(rng)
            await ensure_pool(k, n)
            take, pool[k] = pool[k][:n], pool[k][n:]
            # rombongan satu muatan harus satu dokumen (auto-cocok) — ambil roll dokumen pertama saja
            doc0 = take[0][0]['id']
            epcs = [r['epc'] for d, r in take if d['id'] == doc0]
            pool[k] = [x for x in take if x[0]['id'] != doc0] + pool[k]
            res = await reader.passage(epcs)
            res['txn_ms'] = None
            passages.append({'gate': k, **{x: res.get(x) for x in ('ok', 'rolls', 'verdict', 'status', 'tail_ms', 'bytes')},
                             '_res': res, '_k': k})
            empty = reader.build([], 'empty')                       # lintasan kosong (orang/forklift)
            await reader.send_events(empty, kind='events_empty')
            await reader.close(empty, kind='close_empty')
            spent = time.perf_counter() - t_start
            await asyncio.sleep(max(0.0, rng.expovariate(1 / per_gate_interval) - spent))

    async def agent_poll(k):
        while not stop.is_set():
            t0 = time.perf_counter()
            try:
                r = await http.get(f'{base}/api/rfid/v2/device/gate-state', params={'logical_gate_id': 'G1'},
                                   headers={'X-Device-Key': fx.keys[k]}, timeout=10)
                rec.add('gate_state', (time.perf_counter() - t0) * 1000, r.status_code)
            except Exception:  # noqa: BLE001
                rec.add('gate_state', (time.perf_counter() - t0) * 1000, 'error')
            await asyncio.sleep(1.0)

    async def telemetry(k):
        while not stop.is_set():
            body = {'event_id': f'tel-{uuid.uuid4().hex[:12]}', 'captured_at': iso(), 'config_version': CONFIG_VERSION,
                    'app_build': '0.5.0-lt', 'sdk_version': 'sim', 'radio_state': 'ready', 'printer_state': 'not_applicable',
                    'erp_transport': 'online', 'pending_event_count': 0, 'pending_bytes': 0, 'oldest_pending_at': None,
                    'free_storage_bytes': 10 ** 9, 'uptime_seconds': 3600, 'time_quality': 'synced', 'last_error': None}
            t0 = time.perf_counter()
            try:
                r = await http.post(f'{base}/api/rfid/v2/device/telemetry', json=body,
                                    headers={'X-Device-Key': fx.keys[k]}, timeout=10)
                rec.add('telemetry', (time.perf_counter() - t0) * 1000, r.status_code)
            except Exception:  # noqa: BLE001
                rec.add('telemetry', (time.perf_counter() - t0) * 1000, 'error')
            await asyncio.sleep(30)

    for k in fx.devices:
        await ensure_pool(k, 400)
    await warmup(db, http, base, fx)
    bg = [asyncio.ensure_future(f(k)) for k in fx.devices for f in (agent_poll, telemetry)]
    await asyncio.gather(*[gate_loop(k) for k in fx.devices])
    stop.set()
    for t in bg:
        t.cancel()
    txn = []
    for p in passages:
        p['txn_ms'] = await wait_txn(db, fx, p.pop('_k'), p.pop('_res'), timeout=600)
        if p['txn_ms'] is not None:
            txn.append(p['txn_ms'])
    rolls = sum(p['rolls'] or 0 for p in passages)
    print(f"[sustained] {len(passages)} muatan, {rolls} roll dalam {minutes} mnt (×{multiplier} puncak): "
          f"close p95 {rec.report().get('close', {}).get('p95')} ms", flush=True)
    return {'minutes': minutes, 'multiplier': multiplier, 'assumed_peak_rolls_per_hour': peak_rolls_h,
            'loaded_passages_per_hour_target': round(loaded_per_h, 1), 'per_gate_interval_s': round(per_gate_interval, 1),
            'passages': len(passages), 'rolls': rolls, 'rolls_per_hour_achieved': round(rolls / minutes * 60),
            'verdicts': {v: sum(1 for p in passages if p['verdict'] == v) for v in {p['verdict'] for p in passages}},
            'latency': rec.report(), 'txn_ms': stats(txn), 'bytes_per_roll': round(
                statistics.mean([p['bytes'] / max(1, p['rolls']) for p in passages if p.get('bytes') and p['rolls']]), 1)
            if passages else None}


async def mode_run(args):
    import httpx
    from db import db
    tag = args.tag or uuid.uuid4().hex[:6]
    fx = Fixture(db, tag)
    await fx.setup()
    report = {'tag': tag, 'db': os.environ.get('DB_NAME'), 'started_at': iso(), 'base_url': args.base_url,
              'counts': {c: await db[c].estimated_document_count() for c in (
                  'inventory_rolls', 'rfid_tags', 'rfid_v2_passages', 'rfid_v2_summaries', 'rfid_v2_crossings',
                  'shipments', 'warehouse_transfers', 'putaway_orders')}}
    if args.profile_slowms is not None:
        await profiler_on(db, args.profile_slowms)
    sampler = Sampler(db)
    sampler.start()
    limits = httpx.Limits(max_connections=64, max_keepalive_connections=32)
    async with httpx.AsyncClient(limits=limits) as http:
        scen = args.scenario.split(',')
        if 'big' in scen or 'all' in scen:
            report['big'] = await scenario_big(db, http, args.base_url, fx, [int(x) for x in args.big_sizes.split(',')],
                                               args.big_kinds.split(','))
        if 'concurrent' in scen or 'all' in scen:
            report['concurrent'] = [await scenario_concurrent(db, http, args.base_url, fx, int(n), args.rounds)
                                    for n in args.concurrent_sizes.split(',')]
        if 'sustained' in scen or 'all' in scen:
            report['sustained'] = await scenario_sustained(db, http, args.base_url, fx, args.minutes, args.rate_multiplier)
    report['resources'] = await sampler.stop()
    Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))   # simpan dulu
    if args.profile_slowms is not None:
        try:
            report['slow_queries'] = await profiler_report(db)
        except Exception as exc:  # noqa: BLE001 — laporan profiler tidak boleh membuang hasil ukur
            report['slow_queries_error'] = str(exc)[:300]
            await db.command({'profile': 0})
    report['finished_at'] = iso()
    Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: report[k] for k in report if k in ('resources',)}, indent=1))
    print('laporan →', args.out)


# ─── Data sintetis sebesar produksi ─────────────────────────────────────────────────────────────────
async def mode_synth(args):
    """Roll + tag + riwayat bukti/klaim/dokumen. Waktu tersebar ke belakang `--days` (bukti) / `--claim-days`."""
    from db import db
    from services.rfid_v2_common import digest
    rng = random.Random(11)
    tag = args.tag or uuid.uuid4().hex[:6]
    nowdt = datetime.now(timezone.utc)
    whs = [w['id'] for w in await db.warehouses.find({}, {'_id': 0, 'id': 1}).to_list(100)] or ['wh_SY']
    prods = [p['id'] for p in await db.products.find({}, {'_id': 0, 'id': 1}).to_list(500)] or ['prd_SY']
    t0 = time.perf_counter()
    B = 5000
    # 1) roll + tag
    for start in range(0, args.rolls, B):
        rolls, tags = [], []
        for i in range(start, min(args.rolls, start + B)):
            rid, tid = f'roll_SY_{tag}_{i}', f'tag_SY_{tag}_{i}'
            st = rng.choices(['available', 'delivered', 'consumed', 'reserved'], [55, 35, 5, 5])[0]
            created = nowdt - timedelta(days=rng.randint(0, 720))
            rolls.append({'id': rid, 'roll_no': f'SY{tag}{i:07d}', 'product_id': rng.choice(prods),
                          'warehouse_id': rng.choice(whs), 'owner_entity_id': ENT, 'status': st,
                          'length_remaining': 0.0 if st in ('delivered', 'consumed') else 30.0, 'length_initial': 30.0,
                          'unit': 'meter', 'grade': rng.choice('AAAB'), 'lot': f'L-SY-{i // 200}',
                          # lot_id & biaya terisi seperti roll nyata — tanpa itu migrasi startup (lot/HPP) berjalan per roll
                          'lot_id': f'lot_SY_L-SY-{i // 200}', 'base_unit_cost': 15000, 'unit_cost': 15000,
                          'cost_basis': 'synthetic_loadtest', 'landed_cost_total': 0.0, 'rfid_tag_id': tid,
                          'active_movement': None, 'reserved_ref': None, 'created_at': iso(created),
                          'journey': {'stage': 'tag_verified', 'verified_tag_id': tid}})
            tags.append({'id': tid, 'epc': f'E3{tag.upper()}{i:016X}', 'roll_id': rid,
                         'status': 'active' if st not in ('delivered', 'consumed') else 'retired',
                         'warehouse_id': rolls[-1]['warehouse_id'], 'created_at': iso(created)})
        await db.inventory_rolls.insert_many(rolls, ordered=False)
        await db.rfid_tags.insert_many(tags, ordered=False)
    print(f'[synth] {args.rolls} roll+tag {time.perf_counter() - t0:.0f} dtk', flush=True)
    # 2) riwayat lintasan per hari: muatan (±50 roll) + kosong; bukti ringkasan hanya `--days` terakhir
    devices = [f'dev_SY_{tag}_{k}' for k in ('in1', 'out1', 'in2', 'out2')]
    per_day = int(args.rolls_per_day)
    roll_ix = 0
    stats_ = {'passages': 0, 'summaries': 0, 'edges': 0, 'crossings': 0, 'gate_txn': 0, 'sessions': 0, 'reviews': 0,
              'shipments': 0, 'transfers': 0, 'putaways': 0, 'reads': 0}
    for day in range(args.claim_days, 0, -1):
        day0 = nowdt - timedelta(days=day)
        left = per_day
        passages, sums, edges, claims, txns, sess, revs, shps, trfs, pas, reads = ([] for _ in range(11))
        while left > 0:
            n = min(left, load_size(rng))
            left -= n
            dev = rng.choice(devices)
            direction = 'in' if 'in' in dev.rsplit('_', 1)[-1] else 'out'
            at = day0 + timedelta(seconds=rng.randint(6 * 3600, 20 * 3600))
            lp = f'sy-{uuid.uuid4().hex[:16]}'
            pid = digest([dev, lp])
            rids = [f'roll_SY_{tag}_{(roll_ix + j) % args.rolls}' for j in range(n)]
            roll_ix += n
            typ = 'shipment' if direction == 'out' else rng.choice(['wh_transfer', 'putaway'])
            sid = f'{typ}_SY_{tag}_{uuid.uuid4().hex[:10]}'
            ref = {'source_type': typ, 'source_id': sid, 'display_ref': sid[-10:]}
            verdict = rng.choices(['GREEN', 'REVIEW', 'RED'], [92, 7, 1])[0]
            passages.append({'_id': pid, 'device_id': dev, 'local_passage_id': lp, 'gate_id': 'G1', 'warehouse_id': whs[0],
                             'config_version': 'sy-v1', 'mode': 'live', 'state': 'FINAL', 'event_count': 0,
                             'summary_count': 2 * n if day <= args.days else 0, 'edge_count': 4, 'bytes': 0,
                             'overflow': {'event': 0, 'summary': 0, 'edge': 0}, 'binding': None, 'created_at': iso(at),
                             'decision': {'decision_id': str(uuid.uuid4()), 'local_passage_id': lp, 'verdict': verdict,
                                          'created_at': iso(at), 'reason_codes': ['MANIFEST_MATCH'], 'sources': [ref],
                                          'counts': {'matched': n}, 'latched': verdict == 'RED'},
                             'acknowledged': verdict != 'RED', 'simulated': False, 'gate_txn_state': 'done',
                             'gate_txn_input': {'direction': direction, 'verdict': verdict, 'sources': [{'source_ref': ref, 'roll_ids': rids}]}})
            empty_lp = f'sy-{uuid.uuid4().hex[:16]}'
            passages.append({'_id': digest([dev, empty_lp]), 'device_id': dev, 'local_passage_id': empty_lp, 'gate_id': 'G1',
                             'warehouse_id': whs[0], 'config_version': 'sy-v1', 'mode': 'live', 'state': 'FINAL',
                             'event_count': 0, 'summary_count': 0, 'edge_count': 4, 'bytes': 0, 'created_at': iso(at + timedelta(seconds=30)),
                             'decision': {'verdict': 'CANCELLED', 'reason_codes': ['EMPTY_PASSAGE'], 'sources': []},
                             'acknowledged': False, 'simulated': False})
            if day <= args.days:
                for rid in rids:
                    for ant in ('1', '2'):
                        sums.append({'_id': digest([pid, 'summary', f'{lp}:{rid}:{ant}']), 'passage': pid, 'kind': 'summary',
                                     'key': f'{lp}:{rid}:{ant}', 'fingerprint': uuid.uuid4().hex, 'received_at': iso(at),
                                     'summary': {'summary_id': f'{lp}:{rid}:{ant}', 'epc': rid[-24:], 'raw_epc': rid[-24:],
                                                 'antenna': ant, 'first_seen': iso(at), 'last_seen': iso(at), 'peak_rssi': -50.0,
                                                 't_peak': iso(at), 'count': 8, 'mean_rssi': -54.0, 'in_background': False,
                                                 'time_quality': 'synced',
                                                 'buckets': [{'t_off': 600 + b * 250, 'n': 1, 'max_rssi': -50.0 - b} for b in range(6)]},
                                     'quarantine': None})
                for e in range(4):
                    edges.append({'_id': digest([pid, 'edge', f'{lp}:gpi:{e}']), 'passage': pid, 'kind': 'edge',
                                  'key': f'{lp}:gpi:{e}', 'fingerprint': uuid.uuid4().hex, 'received_at': iso(at),
                                  'edge': {'edge_id': f'{lp}:gpi:{e}', 'sensor': 'AB'[e % 2], 'state': 'blocked',
                                           't_mono': e, 't_wall': iso(at), 'time_quality': 'synced'}})
            if verdict != 'RED':
                for rid in rids:
                    claims.append({'_id': digest([typ, sid, direction, rid]), 'passage': pid, 'roll_id': rid,
                                   'source_type': typ, 'source_id': sid, 'direction': direction, 'at': iso(at),
                                   'device_id': dev, 'gate_id': 'G1', 'local_passage_id': lp, 'review': verdict == 'REVIEW',
                                   'simulated': False})
                txns.append({'_id': digest(['gate_txn', pid, typ, sid]), 'state': 'done', 'passage': pid, 'device_id': dev,
                             'warehouse_id': whs[0], 'direction': direction, 'local_passage_id': lp, 'source_ref': ref,
                             'roll_ids': rids, 'started_at': iso(at), 'finished_at': iso(at), 'attempts': 1,
                             'summary': {'state': 'done', 'kind': 'exit_evidence'}})
            sess.append({'_id': digest(['doc_session', typ, sid, direction]), 'source_ref': ref, 'direction': direction,
                         'warehouse_id': whs[0], 'created_at': iso(at), 'updated_at': iso(at), 'status': 'closed',
                         'roll_ids': rids, 'passage_ids': [pid], 'passages': [{'passage': pid, 'local_passage_id': lp}]})
            if verdict != 'GREEN':
                revs.append({'_id': f'pv:{pid}', 'kind': 'passage', 'passage': pid, 'device_id': dev, 'warehouse_id': whs[0],
                             'status': 'resolved', 'verdict': verdict, 'created_at': iso(at), 'rolls': [], 'sources': [ref]})
            if typ == 'shipment':
                shps.append({'id': sid, 'shipment_no': f'SJ-SY-{sid[-8:]}', 'order_id': f'so_SY_{tag}_{sid[-8:]}',
                             'warehouse_id': whs[0], 'status': 'delivered', 'entity_id': ENT, 'created_at': iso(at),
                             'rolls': [{'roll_id': r, 'roll_no': r[-10:], 'length': 30.0} for r in rids]})
            elif typ == 'wh_transfer':
                trfs.append({'id': sid, 'code': f'TRF-SY-{sid[-8:]}', 'status': 'completed', 'transfer_kind': 'warehouse',
                             'source_warehouse_id': whs[-1], 'dest_warehouse_id': whs[0], 'owner_entity_id': ENT,
                             'entity_id': ENT, 'created_at': iso(at),
                             'items': [{'product_id': prods[0], 'rolls': [{'roll_id': r, 'length': 30.0} for r in rids]}]})
            else:
                pas.append({'id': sid, 'pa_number': f'PA-SY-{sid[-8:]}', 'status': 'completed', 'from_warehouse_id': whs[-1],
                            'to_warehouse_id': whs[0], 'owner_entity_id': ENT, 'created_at': iso(at),
                            'items': [{'roll_id': r, 'roll_no': r[-10:], 'status': 'arrived'} for r in rids]})
            reads.append({'id': f'rread_SY_{uuid.uuid4().hex[:12]}', 'epc': rids[0][-24:], 'roll_id': rids[0],
                          'device_id': dev, 'read_type': 'gate_out' if direction == 'out' else 'gate_in',
                          'warehouse_id': whs[0], 'owner_entity_id': ENT, 'result': 'green', 'reason': 'sintetis',
                          'timestamp': iso(at)})
        for name, docs in (('rfid_v2_passages', passages), ('rfid_v2_summaries', sums), ('rfid_v2_edges', edges),
                           ('rfid_v2_crossings', claims), ('rfid_v2_gate_txn', txns), ('rfid_v2_doc_sessions', sess),
                           ('rfid_v2_reviews', revs), ('shipments', shps), ('warehouse_transfers', trfs),
                           ('putaway_orders', pas), ('rfid_reads', reads)):
            for i in range(0, len(docs), B):
                try:
                    await db[name].insert_many(docs[i:i + B], ordered=False)
                except Exception as exc:  # noqa: BLE001 — duplikat klaim sintetis diabaikan
                    if 'E11000' not in str(exc):
                        raise
        for key, docs in (('passages', passages), ('summaries', sums), ('edges', edges), ('crossings', claims),
                          ('gate_txn', txns), ('sessions', sess), ('reviews', revs), ('shipments', shps),
                          ('transfers', trfs), ('putaways', pas), ('reads', reads)):
            stats_[key] += len(docs)
        if day % 10 == 0:
            print(f'[synth] hari -{day}: {stats_} ({time.perf_counter() - t0:.0f} dtk)', flush=True)
    sizes = {}
    for c in ('inventory_rolls', 'rfid_tags', 'rfid_v2_passages', 'rfid_v2_summaries', 'rfid_v2_edges', 'rfid_v2_crossings',
              'rfid_v2_gate_txn', 'rfid_v2_doc_sessions', 'rfid_v2_reviews', 'shipments', 'warehouse_transfers',
              'putaway_orders', 'rfid_reads'):
        st = await db.command('collStats', c)
        sizes[c] = {'count': st.get('count'), 'avg_obj_bytes': st.get('avgObjSize'), 'size_mb': round(st.get('size', 0) / 1e6, 1),
                    'storage_mb': round(st.get('storageSize', 0) / 1e6, 1), 'index_mb': round(st.get('totalIndexSize', 0) / 1e6, 1)}
    out = {'tag': tag, 'inserted': stats_, 'seconds': round(time.perf_counter() - t0), 'collections': sizes}
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


# ─── Explain query jalur gate ───────────────────────────────────────────────────────────────────────
async def mode_explain(args):
    from db import db
    from services.rfid_v2_common import digest
    roll = await db.inventory_rolls.find_one({'id': {'$regex': '^roll_SY_'}}, {'_id': 0, 'id': 1}) or \
        await db.inventory_rolls.find_one({}, {'_id': 0, 'id': 1})
    ids = [r['id'] for r in await db.inventory_rolls.find({}, {'_id': 0, 'id': 1}).skip(1000).limit(200).to_list(200)]
    epcs = [t['epc'] for t in await db.rfid_tags.find({'roll_id': {'$in': ids}}, {'_id': 0, 'epc': 1}).to_list(400)] if ids else []
    pas = await db.rfid_v2_passages.find_one({'decision': {'$ne': None}}, {'_id': 1, 'device_id': 1, 'created_at': 1})
    cl = await db.rfid_v2_crossings.find_one({}, {'_id': 0, 'source_type': 1, 'source_id': 1, 'direction': 1, 'roll_id': 1})
    shp = await db.shipments.find_one({}, {'_id': 0, 'id': 1, 'order_id': 1})
    cutoff = iso(datetime.now(timezone.utc) - timedelta(days=30))
    claim_ids = [digest(['shipment', 'x', 'out', r]) for r in ids]
    Q = [
        ('rfid_tags epc $in (lookup lintasan)', 'rfid_tags', {'epc': {'$in': epcs}, 'status': 'active'}),
        ('inventory_rolls id $in (lookup lintasan)', 'inventory_rolls', {'id': {'$in': ids}}),
        ('inventory_rolls id (find_one per roll)', 'inventory_rolls', {'id': (roll or {}).get('id')}),
        ('rfid_tags roll_id $in (antrean periksa)', 'rfid_tags', {'roll_id': {'$in': ids}, 'status': 'active'}),
        ('crossings _id $in (klaim)', 'rfid_v2_crossings', {'_id': {'$in': claim_ids}}),
        ('crossings bawaan muatan', 'rfid_v2_crossings', {'roll_id': {'$in': ids}, 'direction': 'out', 'gate_id': 'G1',
                                                          'at': {'$gte': cutoff}}),
        ('crossings per dokumen (sesi)', 'rfid_v2_crossings', {k: (cl or {}).get(k) for k in ('source_type', 'source_id', 'direction')}),
        ('shipments order_id + roll (resolve_movement)', 'shipments', {'order_id': (shp or {}).get('order_id'),
                                                                       'rolls.roll_id': (roll or {}).get('id')}),
        ('shipments id', 'shipments', {'id': (shp or {}).get('id')}),
        ('putaway_orders id', 'putaway_orders', {'id': 'x'}),
        ('warehouse_transfers id', 'warehouse_transfers', {'id': 'x'}),
        ('sales_orders id', 'sales_orders', {'id': 'x'}),
        ('passages riwayat per perangkat', 'rfid_v2_passages', {'device_id': (pas or {}).get('device_id')}),
        ('passages antrean transaksi gate', 'rfid_v2_passages', {'gate_txn_state': 'pending'}),
        ('passages retensi (lama)', 'rfid_v2_passages', {'created_at': {'$lt': cutoff}}),
        ('summaries per lintasan', 'rfid_v2_summaries', {'passage': (pas or {}).get('_id')}),
        ('gate_txn per lintasan', 'rfid_v2_gate_txn', {'passage': (pas or {}).get('_id')}),
        ('reviews per lintasan', 'rfid_v2_reviews', {'passage': (pas or {}).get('_id')}),
        ('doc_sessions terbuka gudang/arah', 'rfid_v2_doc_sessions', {'warehouse_id': 'x', 'direction': 'out', 'status': 'open'}),
        ('rfid_reads gate lama (retensi)', 'rfid_reads', {'read_type': {'$in': ['gate_in', 'gate_out']}, 'timestamp': {'$lt': cutoff}}),
    ]
    out = []
    for label, coll, flt in Q:
        try:
            ex = await db.command('explain', {'find': coll, 'filter': flt}, verbosity='executionStats')
        except Exception as exc:  # noqa: BLE001
            out.append({'query': label, 'error': str(exc)[:200]})
            continue
        es = ex.get('executionStats') or {}
        plan = ex.get('queryPlanner', {}).get('winningPlan', {})

        def stages(p):
            s = [p.get('stage')]
            for k in ('inputStage', 'queryPlan'):
                if p.get(k):
                    s += stages(p[k])
            for c in p.get('inputStages') or []:
                s += stages(c)
            return [x for x in s if x]
        out.append({'query': label, 'collection': coll, 'plan': '>'.join(stages(plan)),
                    'index': next((p.get('indexName') for p in [plan, plan.get('inputStage') or {}, (plan.get('inputStage') or {}).get('inputStage') or {}]
                                   if p.get('indexName')), None),
                    'returned': es.get('nReturned'), 'docs_examined': es.get('totalDocsExamined'),
                    'keys_examined': es.get('totalKeysExamined'), 'ms': es.get('executionTimeMillis')})
    Path(args.out).write_text(json.dumps(out, indent=1))
    for r in out:
        print(f"{r.get('ms', '-'):>5} ms  docs {str(r.get('docs_examined')):>8}  {r.get('plan', r.get('error'))[:40]:<40}  {r['query']}")


# ─── Uji kegagalan ──────────────────────────────────────────────────────────────────────────────────
async def _decision_count(db, fx, k, lp):
    from services.rfid_v2_common import digest
    pid = digest([fx.devices[k], lp])
    p = await db.rfid_v2_passages.find_one({'_id': pid}, {'decision.decision_id': 1, 'state': 1, 'gate_txn_state': 1,
                                                          'gate_txn_attempts': 1})
    claims = await db.rfid_v2_crossings.count_documents({'passage': pid})
    ledger = await db.rfid_v2_gate_txn.find({'passage': pid}, {'_id': 0, 'state': 1, 'attempts': 1}).to_list(10)
    return {'state': (p or {}).get('state'), 'decision_id': ((p or {}).get('decision') or {}).get('decision_id'),
            'txn_state': (p or {}).get('gate_txn_state'), 'txn_attempts': (p or {}).get('gate_txn_attempts'),
            'claims': claims, 'ledger': ledger}


def _restart(cmd):
    """Matikan uvicorn MENDADAK (SIGKILL — seperti proses mati/OOM) lalu jalankan `cmd` (memulai ulang backend)."""
    import signal
    for p in os.listdir('/proc'):
        if p.isdigit() and int(p) != os.getpid():
            try:
                line = Path(f'/proc/{p}/cmdline').read_bytes().replace(b'\0', b' ').decode()
            except OSError:
                continue
            if 'uvicorn server:app' in line:
                os.kill(int(p), signal.SIGKILL)
    time.sleep(1)
    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


async def _wait_up(http, base, timeout=180):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            if (await http.get(f'{base}/api/', timeout=3)).status_code < 500:
                return True
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(1)
    return False


async def mode_fault(args):
    import httpx
    from db import db
    tag = args.tag or uuid.uuid4().hex[:6]
    fx = Fixture(db, tag)
    await fx.setup()
    rec = Recorder()
    out = {'tag': tag}
    async with httpx.AsyncClient(timeout=120) as http:
        base = args.base_url
        faults = args.faults.split(',')
        if 'double_close' in faults:   # close ganda BERSAMAAN (agent retry + jaringan lambat)
            doc = await fx.shipment(args.fault_rolls)
            rd = Reader(http, base, fx, 'out1', rec)
            built = rd.build([r['epc'] for r in doc['rolls']])
            await rd.send_events(built)
            res = await asyncio.gather(*[rd.close(built, 120) for _ in range(3)])
            ids = [(r.status_code, (r.json() if r is not None else {}).get('decision_id')) for r in res if r is not None]
            for _ in range(200):
                st = await _decision_count(db, fx, 'out1', built['passage_id'])
                if st['txn_state'] in ('done', 'error'):
                    break
                await asyncio.sleep(0.1)
            out['double_close'] = {'responses': ids, 'after': st}
            print('[fault] double_close', out['double_close'], flush=True)
        if 'kill_close' in faults:     # backend dimatikan di tengah close, lalu close diulang (key & isi sama)
            doc = await fx.transfer(args.fault_rolls)
            rd = Reader(http, base, fx, 'in1', rec)
            built = rd.build([r['epc'] for r in doc['rolls']])
            await rd.send_events(built)
            task = asyncio.ensure_future(rd.close(built, 120))
            await asyncio.sleep(args.kill_after_ms / 1000)
            _restart(args.restart_cmd)
            first = await task
            before = await _decision_count(db, fx, 'in1', built['passage_id'])
            up = await _wait_up(http, base)
            t0 = time.perf_counter()
            again, decided = None, None
            for _ in range(30):   # agent mengulang close (EVIDENCE_PENDING/klaim keputusan = retryable)
                hdr = {'X-Device-Key': rd.key, 'Idempotency-Key': 'c-' + built['passage_id']}
                again = await http.post(f"{base}/api/rfid/v2/passages/{built['passage_id']}/close", json=built['close_sent'],
                                        headers=hdr, timeout=60)
                if again.status_code == 200:
                    decided = again.json()
                    break
                await asyncio.sleep(1)
            retry_ms = round((time.perf_counter() - t0) * 1000)
            for _ in range(int(args.txn_wait_s * 10)):
                st = await _decision_count(db, fx, 'in1', built['passage_id'])
                if st['txn_state'] in ('done', 'error'):
                    break
                await asyncio.sleep(0.1)
            received = await db.inventory_rolls.count_documents({'id': {'$in': [r['id'] for r in doc['rolls']]},
                                                                 'warehouse_id': fx.wh_gate})
            moves = await db.inventory_movements.count_documents({'roll_id': {'$in': [r['id'] for r in doc['rolls']]}})
            out['kill_close'] = {'first_response': None if first is None else first.status_code, 'backend_up': up,
                                 'before_retry': before, 'retry_status': again.status_code if again is not None else None,
                                 'retry_ms': retry_ms, 'verdict': (decided or {}).get('verdict'), 'after': st,
                                 'rolls_received': received, 'rolls': len(doc['rolls']), 'movements': moves}
            print('[fault] kill_close', out['kill_close'], flush=True)
        if 'worker_crash' in faults:   # pekerja transaksi mati di tengah → sapuan ulang mengambil alih (lease basi)
            doc = await fx.transfer(args.fault_rolls)
            rd = Reader(http, base, fx, 'in2', rec)
            built = rd.build([r['epc'] for r in doc['rolls']])
            await rd.send_events(built)
            r = await rd.close(built, 120)
            await asyncio.sleep(args.kill_after_ms / 1000)
            mid = await _decision_count(db, fx, 'in2', built['passage_id'])
            _restart(args.restart_cmd)
            await _wait_up(http, base)
            partial = await db.inventory_rolls.count_documents({'id': {'$in': [x['id'] for x in doc['rolls']]},
                                                                'warehouse_id': fx.wh_gate})
            t0 = time.perf_counter()
            for _ in range(int(args.txn_wait_s * 10)):
                st = await _decision_count(db, fx, 'in2', built['passage_id'])
                if st['txn_state'] in ('done', 'error'):
                    break
                await asyncio.sleep(0.1)
            received = await db.inventory_rolls.count_documents({'id': {'$in': [x['id'] for x in doc['rolls']]},
                                                                 'warehouse_id': fx.wh_gate})
            receipts = await db.warehouse_transfers.find_one({'id': doc['id']}, {'_id': 0, 'status': 1, 'receipt_events': 1})
            out['worker_crash'] = {'close_status': r.status_code if r is not None else None, 'mid': mid,
                                   'received_at_crash': partial, 'recovered_after_ms': round((time.perf_counter() - t0) * 1000),
                                   'after': st, 'rolls_received': received, 'rolls': len(doc['rolls']),
                                   'transfer_status': (receipts or {}).get('status'),
                                   'receipt_events': len((receipts or {}).get('receipt_events') or [])}
            print('[fault] worker_crash', out['worker_crash'], flush=True)
        if 'net_drop' in faults:       # jaringan putus saat batch events: respons hilang, batch diulang, satu batch tertinggal
            doc = await fx.shipment(max(args.fault_rolls, 450))
            rd = Reader(http, base, fx, 'out2', rec)
            built = rd.build([r['epc'] for r in doc['rolls']])
            b = built['batches']
            log = []
            try:   # batch 0: respons "hilang" (klien memutus sebelum respons dibaca)
                await http.post(f'{base}/api/rfid/v2/events', json=b[0], headers={'X-Device-Key': rd.key}, timeout=0.001)
                log.append('b0 terkirim (respons tidak hilang)')
            except Exception as exc:  # noqa: BLE001
                log.append(f'b0 respons hilang: {type(exc).__name__}')
            await asyncio.sleep(0.5)
            r0 = await http.post(f'{base}/api/rfid/v2/events', json=b[0], headers={'X-Device-Key': rd.key})
            acks = r0.json().get('summary_acks') or []
            log.append(f"b0 diulang: {r0.status_code} {sorted({a['status'] for a in acks})}")
            for body in b[2:]:          # batch 1 tertinggal (antrean agent), batch sesudahnya terkirim → seq gap
                r = await http.post(f'{base}/api/rfid/v2/events', json=body, headers={'X-Device-Key': rd.key})
                log.append(f"b{b.index(body)} {r.status_code} seq_gap={r.json().get('seq_gap')}")
            c1 = await rd.close(built, 60)
            log.append(f"close sebelum b1: {c1.status_code} {(c1.json().get('detail') or {}).get('code') if c1.status_code != 200 else ''}")
            if len(b) > 1:
                r1 = await http.post(f'{base}/api/rfid/v2/events', json=b[1], headers={'X-Device-Key': rd.key})
                log.append(f'b1 dikirim ulang: {r1.status_code}')
            c2 = await rd.close(built, 60)
            out['net_drop'] = {'log': log, 'close_status': c2.status_code, 'verdict': c2.json().get('verdict'),
                               'matched': (c2.json().get('counts') or {}).get('matched'), 'rolls': len(doc['rolls'])}
            print('[fault] net_drop', out['net_drop'], flush=True)
    Path(args.out).write_text(json.dumps(out, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=('synth', 'run', 'explain', 'fault'))
    ap.add_argument('--confirm-db', required=True, help='wajib = DB_NAME (pengaman DB salinan)')
    ap.add_argument('--base-url', default='http://127.0.0.1:8001')
    ap.add_argument('--tag', default=None)
    ap.add_argument('--out', default='/tmp/rfid_v2_loadtest.json')
    ap.add_argument('--scenario', default='big,concurrent', help='big,concurrent,sustained | all')
    ap.add_argument('--big-sizes', default='50,500,2000')
    ap.add_argument('--big-kinds', default='shipment,wh_transfer,putaway')
    ap.add_argument('--concurrent-sizes', default='500')
    ap.add_argument('--rounds', type=int, default=1)
    ap.add_argument('--minutes', type=float, default=5)
    ap.add_argument('--rate-multiplier', type=float, default=1.0)
    ap.add_argument('--profile-slowms', type=int, default=None)
    ap.add_argument('--rolls', type=int, default=300000)
    ap.add_argument('--days', type=int, default=45, help='hari riwayat bukti mentah (ringkasan/tepi)')
    ap.add_argument('--claim-days', type=int, default=90, help='hari riwayat lintasan/klaim/dokumen')
    ap.add_argument('--rolls-per-day', type=int, default=6000)
    ap.add_argument('--faults', default='double_close,kill_close,worker_crash,net_drop')
    ap.add_argument('--fault-rolls', type=int, default=500)
    ap.add_argument('--kill-after-ms', type=int, default=300)
    ap.add_argument('--txn-wait-s', type=float, default=300)
    ap.add_argument('--restart-cmd', default='/usr/local/bin/kn-uv')
    args = ap.parse_args()
    guard(args)
    fn = {'synth': mode_synth, 'run': mode_run, 'explain': mode_explain, 'fault': mode_fault}[args.mode]
    asyncio.get_event_loop().run_until_complete(fn(args))


if __name__ == '__main__':
    main()
