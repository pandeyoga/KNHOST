"""PREP-H — masa simpan bukti mentah gate RFID: arsip JSONL terkompresi di penyimpanan lokal → baru dihapus.

Setelan (registri konfigurasi, `config_catalog_rfid.py`; Pusat Pengaturan › Stok, Satuan & Alokasi):
  * `rfid.evidence_retention_mode`  — `archive` (bawaan: arsip lalu hapus) · `dry_run` (hanya hitung) · `off`;
  * `rfid.evidence_retention_days`  — bukti mentah lintasan V2 (bawaan 90 hari);
  * `rfid.legacy_reads_retention_days` — bacaan gate jalur lama `rfid_reads` (gate_in/gate_out; bawaan 180 hari).

DIARSIPKAN lalu dihapus (hanya bila lebih tua dari batas):
  * bukti per lintasan — `rfid_v2_summaries`, `rfid_v2_events`, `rfid_v2_edges`, `rfid_v2_overflow`,
    `rfid_v2_event_ids` — untuk lintasan yang keputusannya FINAL, transaksi gatenya tuntas (bukan pending/processing/
    error) dan TIDAK punya kasus antrean periksa terbuka; lintasan yang tidak pernah ditutup (OPEN/CLOSING) ikut
    diarsipkan buktinya sesudah batas yang sama;
  * `rfid_reads` jalur lama dengan `read_type` gate_in/gate_out (bacaan handheld/jenis lain TIDAK disentuh).
TIDAK PERNAH dihapus (dijaga `PROTECTED`, diuji): keputusan lintasan (`rfid_v2_passages` — hanya diberi penanda
`evidence_archived_at` + lokasi berkas), klaim crossing, sesi dokumen, kasus antrean periksa, buku transaksi gate,
koreksi klaim, kunci gate, profil berversi, binding.

Berkas: `$LOCAL_STORAGE_DIR/rfid_archive/<YYYY>/<MM>/<jenis>_<waktu>_<n>.jsonl.gz` — satu baris
`{"c": koleksi, "d": dokumen}`. Ditulis ke berkas sementara → fsync → rename → dibaca ulang & dihitung → baru
dokumen yang SAMA (`_id`) dihapus. Hitungan berbeda = tidak ada yang dihapus untuk kelompok itu (dicatat).
Log tiap jalan di `rfid_v2_retention_runs` (TTL 400 hari — data sekali pakai).
"""
import asyncio
import gzip
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from db import db
from services.rfid_v2_common import collection, now

logger = logging.getLogger(__name__)

EVIDENCE = ('rfid_v2_summaries', 'rfid_v2_events', 'rfid_v2_edges', 'rfid_v2_overflow', 'rfid_v2_event_ids')
LEGACY_READS = 'rfid_reads'
DELETABLE = frozenset(EVIDENCE + (LEGACY_READS,))
PROTECTED = frozenset(('rfid_v2_passages', 'rfid_v2_crossings', 'rfid_v2_doc_sessions', 'rfid_v2_reviews',
                       'rfid_v2_gate_txn', 'rfid_v2_claim_corrections', 'rfid_v2_gate_latches', 'rfid_v2_configs',
                       'rfid_v2_bindings'))
assert not DELETABLE & PROTECTED
UNSETTLED_TXN = ('pending', 'processing', 'error')
RUNS = 'rfid_v2_retention_runs'
RUN_LOG_DAYS = 400
DEFAULTS = {'mode': 'archive', 'days': 90, 'legacy_days': 180}
MIN_DAYS = 7


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace('+00:00', 'Z')


def archive_root() -> Path:
    return Path(os.environ.get('LOCAL_STORAGE_DIR') or (Path(__file__).resolve().parents[1] / 'uploads')) / 'rfid_archive'


async def settings() -> Dict[str, Any]:
    from services.config_resolver import value_of
    out = dict(DEFAULTS)
    for key, name in (('mode', 'rfid.evidence_retention_mode'), ('days', 'rfid.evidence_retention_days'),
                      ('legacy_days', 'rfid.legacy_reads_retention_days')):
        try:
            val = await value_of(name)
            if val not in (None, ''):
                out[key] = val
        except Exception as exc:  # noqa: BLE001 — registri belum termuat → bawaan aman
            logger.warning('[rfid_retention] setelan %s tidak terbaca, pakai bawaan: %s', name, exc)
    out['days'] = max(MIN_DAYS, int(out['days']))
    out['legacy_days'] = max(MIN_DAYS, int(out['legacy_days']))
    if out['mode'] not in ('archive', 'dry_run', 'off'):
        out['mode'] = 'dry_run'
    return out


def _line(coll: str, doc: Dict[str, Any]) -> bytes:
    return (json.dumps({'c': coll, 'd': doc}, ensure_ascii=False, default=str, separators=(',', ':')) + '\n').encode()


def _write_archive(kind: str, stamp: str, seq: int, chunks: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Tulis berkas JSONL.gz secara atomik lalu verifikasi jumlah baris per koleksi. Return info berkas."""
    year, month = stamp[:4], stamp[5:7]
    folder = archive_root() / year / month
    folder.mkdir(parents=True, exist_ok=True)
    # sufiks acak: dua putaran di detik yang sama tidak pernah menimpa arsip (bukti asli sudah dihapus)
    name = f"{kind}_{stamp.replace(':', '').replace('-', '')[:15]}_{seq:04d}_{uuid.uuid4().hex[:8]}.jsonl.gz"
    final = folder / name
    tmp = folder / (name + '.tmp')
    with open(tmp, 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=6) as gz:
            for coll, docs in chunks.items():
                for d in docs:
                    gz.write(_line(coll, d))
        raw.flush()
        os.fsync(raw.fileno())
    os.replace(tmp, final)
    counted: Dict[str, int] = {}
    with gzip.open(final, 'rb') as gz:
        for row in gz:
            c = json.loads(row)['c']
            counted[c] = counted.get(c, 0) + 1
    expected = {c: len(d) for c, d in chunks.items() if d}
    if counted != expected:
        raise RuntimeError(f'verifikasi arsip gagal {final}: {counted} ≠ {expected}')
    return {'file': str(final.relative_to(archive_root().parent)), 'bytes': final.stat().st_size, 'counts': counted}


async def _delete(coll: str, ids: List[Any]) -> int:
    assert coll in DELETABLE and coll not in PROTECTED, coll   # pagar terakhir: koleksi keputusan tidak pernah dihapus
    deleted = 0
    for i in range(0, len(ids), 1000):
        res = await collection(coll).delete_many({'_id': {'$in': ids[i:i + 1000]}})
        deleted += res.deleted_count
    return deleted


MAX_DOCS_PER_FILE = 20000   # batas memori per kelompok arsip (lintasan 2.000 roll ≈ 4.000 ringkasan)


async def _eligible_page(cutoff: str, limit: int, after: Optional[tuple], scope: Optional[Dict[str, Any]] = None):
    """Satu halaman lintasan lama (urut created_at, _id) → (yang boleh diarsip, kursor, jumlah ditahan kasus)."""
    from services.gate_review_service import passage_case_id
    q: Dict[str, Any] = {'created_at': {'$lt': cutoff}, 'evidence_archived_at': {'$exists': False},
                         '$or': [{'state': 'FINAL', 'gate_txn_state': {'$nin': list(UNSETTLED_TXN)}},
                                 {'state': {'$in': ['OPEN', 'CLOSING']}}]}
    if scope:
        q = {'$and': [q, scope]}
    if after:
        q = {'$and': [q, {'$or': [{'created_at': {'$gt': after[0]}}, {'created_at': after[0], '_id': {'$gt': after[1]}}]}]}
    rows = await collection('rfid_v2_passages').find(
        q, {'_id': 1, 'created_at': 1, 'state': 1, 'event_count': 1, 'summary_count': 1, 'edge_count': 1,
            'overflow': 1}).sort([('created_at', 1), ('_id', 1)]).limit(limit).to_list(limit)
    if not rows:
        return [], None, 0
    case_ids = {passage_case_id(r['_id']): r['_id'] for r in rows}
    open_cases = {c['_id'] for c in await collection('rfid_v2_reviews').find(
        {'_id': {'$in': list(case_ids)}, 'status': 'open'}, {'_id': 1}).to_list(len(case_ids))}
    blocked = {case_ids[c] for c in open_cases}
    return [r for r in rows if r['_id'] not in blocked], (rows[-1]['created_at'], rows[-1]['_id']), len(blocked)


def _groups(rows: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    out, cur, n = [], [], 0
    for r in rows:
        size = 2 * int(r.get('event_count') or 0) + int(r.get('summary_count') or 0) + int(r.get('edge_count') or 0) \
            + sum((r.get('overflow') or {}).values())
        if cur and n + size > MAX_DOCS_PER_FILE:
            out.append(cur)
            cur, n = [], 0
        cur.append(r)
        n += size
    return out + ([cur] if cur else [])


async def _archive_passages(cutoff: str, dry: bool, stamp: str, page: int, max_passages: int,
                            scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {'passages': 0, 'docs': {c: 0 for c in EVIDENCE}, 'deleted': {c: 0 for c in EVIDENCE},
                           'files': [], 'bytes': 0, 'skipped_mismatch': 0, 'held_open_review': 0}
    after = None
    seq = 0
    while out['passages'] < max_passages:
        rows, after, held = await _eligible_page(cutoff, page, after, scope)
        out['held_open_review'] += held
        if after is None:
            break
        for grp in _groups(rows):
            pids = [r['_id'] for r in grp]
            out['passages'] += len(pids)
            if dry:
                for c in EVIDENCE:
                    out['docs'][c] += await collection(c).count_documents({'passage': {'$in': pids}})
                continue
            chunks = {c: await collection(c).find({'passage': {'$in': pids}}).to_list(None) for c in EVIDENCE}
            for c, docs in chunks.items():
                out['docs'][c] += len(docs)
            info = None
            if any(chunks.values()):
                seq += 1
                info = await asyncio.to_thread(_write_archive, 'rfid_evidence', stamp, seq, chunks)
                out['files'].append(info['file'])
                out['bytes'] += info['bytes']
                now_counts = {c: await collection(c).count_documents({'passage': {'$in': pids}}) for c in EVIDENCE}
                if any(now_counts[c] != len(chunks[c]) for c in EVIDENCE):   # bukti berubah selagi diarsip → jangan hapus
                    out['skipped_mismatch'] += len(pids)
                    continue
                for c, docs in chunks.items():
                    if docs:
                        out['deleted'][c] += await _delete(c, [d['_id'] for d in docs])
            await collection('rfid_v2_passages').update_many(
                {'_id': {'$in': pids}, 'evidence_archived_at': {'$exists': False}},
                {'$set': {'evidence_archived_at': now(), 'evidence_archive': {
                    'file': (info or {}).get('file'), 'counts': {c: len(d) for c, d in chunks.items() if d}}}})
    return out


async def _archive_legacy_reads(cutoff: str, dry: bool, stamp: str, batch: int, max_docs: int,
                                scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    q: Dict[str, Any] = {'read_type': {'$in': ['gate_in', 'gate_out']}, 'timestamp': {'$lt': cutoff}, **(scope or {})}
    out: Dict[str, Any] = {'docs': 0, 'deleted': 0, 'files': [], 'bytes': 0}
    if dry:
        out['docs'] = await db[LEGACY_READS].count_documents(q)
        return out
    seq = 0
    while out['docs'] < max_docs:
        docs = await db[LEGACY_READS].find(q).sort('timestamp', 1).limit(batch).to_list(batch)
        if not docs:
            break
        seq += 1
        info = await asyncio.to_thread(_write_archive, 'rfid_reads_gate', stamp, seq, {LEGACY_READS: docs})
        out['files'].append(info['file'])
        out['bytes'] += info['bytes']
        out['docs'] += len(docs)
        gone = await _delete(LEGACY_READS, [d['_id'] for d in docs])
        out['deleted'] += gone
        if gone < len(docs):   # dokumen berubah/terkunci — berhenti, jangan mengarsip ulang berulang
            break
    return out


async def run(*, mode: Optional[str] = None, days: Optional[int] = None, legacy_days: Optional[int] = None,
              now_dt: Optional[datetime] = None, batch_passages: int = 500, max_passages: int = 50000,
              max_reads: int = 500000, trigger: str = 'schedule',
              scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Satu putaran retensi. `mode` = `archive` | `dry_run` | `off` (bawaan dari registri konfigurasi).

    `scope` = saringan tambahan (mis. `{'device_id': {'$in': [...]}}`) untuk menjalankan per perangkat / uji."""
    cfg = await settings()
    mode = mode or cfg['mode']
    days = max(MIN_DAYS, int(days or cfg['days']))
    legacy_days = max(MIN_DAYS, int(legacy_days or cfg['legacy_days']))
    at = now_dt or datetime.now(timezone.utc)
    result: Dict[str, Any] = {'mode': mode, 'days': days, 'legacy_days': legacy_days, 'started_at': _iso(at),
                              'trigger': trigger}
    if mode == 'off':
        result['detail'] = 'Masa simpan bukti gate dimatikan (rfid.evidence_retention_mode = off).'
        return result
    dry = mode == 'dry_run'
    stamp = _iso(datetime.now(timezone.utc))
    result['evidence'] = await _archive_passages(_iso(at - timedelta(days=days)), dry, stamp, batch_passages, max_passages,
                                                 scope)
    result['legacy_reads'] = await _archive_legacy_reads(_iso(at - timedelta(days=legacy_days)), dry, stamp,
                                                         5000, max_reads, scope)
    result['finished_at'] = now()
    ev, lr = result['evidence'], result['legacy_reads']
    verb = 'akan diarsipkan' if dry else 'diarsipkan & dihapus'
    result['detail'] = (f"{'UJI COBA — ' if dry else ''}{ev['passages']} lintasan > {days} hari: "
                        f"{sum(ev['docs'].values())} bukti {verb}; {lr['docs']} bacaan gate lama > {legacy_days} hari {verb}"
                        + (f"; {len(ev['files']) + len(lr['files'])} berkas arsip "
                           f"({round((ev['bytes'] + lr['bytes']) / 1e6, 2)} MB)" if not dry else ''))
    log = {**result, 'expire_at': datetime.now(timezone.utc) + timedelta(days=RUN_LOG_DAYS)}
    await collection(RUNS).insert_one(log)
    log.pop('_id', None)
    return result


async def job_rfid_evidence_retention() -> Dict[str, Any]:
    res = await run(trigger='schedule')
    ev = res.get('evidence') or {}
    return {'scanned': ev.get('passages', 0), 'created': 0, 'detail': res.get('detail', '')}
