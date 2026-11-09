"""FIX-7 (butir 6) — pagar & jejak skrip PERBAIKAN DATA: DB uji ↔ produksi.

Dipakai skrip `scripts/fix_data_*.py` (menaruh `/app/backend` di `sys.path`) dan `backend/scripts/*.py`. Modul ini
TIDAK mengimpor `db` di tingkat modul: `parse_and_guard()` harus dipanggil SEBELUM `from db import db`, karena
`db.py` membaca `DB_NAME` saat diimpor.

ATURAN DB
  * DB uji (`kn_test_trial`, `test_database`) → diterima seperti dulu (tanpa flag tambahan).
  * DB produksi (`kainnusantara`) → WAJIB `--production` + bukti backup < 24 jam (juga untuk dry-run: operator
    diwajibkan membuat backup SEBELUM merencanakan perubahan).
  * DB lain → DITOLAK.

BUKTI BACKUP (`deploy/backup.sh` menulis `deploy/backups/<db>-YYYY-MM-DD_HHMM.archive.gz`), salah satu:
  1. berkas TERLIHAT oleh proses (dijalankan di host, atau kontainer sekali-pakai dengan `deploy/backups` di-mount):
     `--backup-file <jalur>` atau otomatis dari `--backup-dir`/`deploy/backups` → diperiksa: nama `<db>-…archive.gz`,
     umur berkas (mtime) < 24 jam, ukuran ≥ 100 KB, gzip UTUH (dibaca sampai habis) dan diawali penanda arsip
     mongodump. Arsip setengah jadi (mongodump gagal di tengah) DITOLAK.
  2. berkas TIDAK terlihat (dijalankan lewat `docker compose exec backend`, kontainer tidak melihat `deploy/backups`):
     `--backup-file <nama berkas>` → cap waktu di NAMA dibaca sebagai jam WIB (bila host VPS ber-UTC, umur jadi
     terhitung 7 jam LEBIH TUA = lebih ketat, tidak pernah lebih longgar) dan harus < 24 jam.
  3. `--backup-confirmed "<keterangan ≥ 5 huruf>"` — konfirmasi manual operator (mis. nama berkas backup + siapa
     yang memeriksa). Dicatat apa adanya di jejak. Dipakai bila 1/2 tidak mungkin.

JEJAK (`--apply` / `--undo --apply`)
  * per dokumen yang berubah: satu baris `audit_logs` (aksi `data_fix_applied` / `data_fix_undone`, `entity_type` =
    koleksi, `before`/`after` = field yang diubah, `source` = `<skrip>#<run_id>`) — jejak bisnis yang tidak bisa
    disunting (sidik isi GN-14) dan terlihat di layar Jejak Audit;
  * sumber `--undo`: dokumen `migrations` `<skrip>:changes:<run_id>:<n>` (per 500 perubahan: koleksi, id, nilai
    SEBELUM persis termasuk field yang tadinya tidak ada, nilai SESUDAH, entri riwayat yang ditambahkan, dokumen yang
    disisipkan) + ringkasan per putaran di dokumen `migrations.<skrip>` (`runs[]`: run_id, mode, DB, produksi, bukti
    backup, jumlah per langkah).
  * Bukan `data_hygiene_log`: layar Kebersihan Data punya tombol "Kembalikan" PER BARIS yang hanya menimpa field
    (tanpa membangun ulang saldo roll) dan mengunci dokumen (`hygiene_locked`) — tidak aman untuk roll/tugas.
"""
from __future__ import annotations

import argparse
import gzip
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

TEST_DBS: Tuple[str, ...] = ("kn_test_trial", "test_database")
PRODUCTION_DBS: Tuple[str, ...] = ("kainnusantara",)
BACKUP_MAX_AGE_HOURS = 24
BACKUP_MIN_BYTES = 100 * 1024
ARCHIVE_MAGIC = bytes.fromhex("6de29981")          # penanda awal arsip `mongodump --archive` (0x8199e26d LE)
WIB = timezone(timedelta(hours=7))
CHUNK = 500
REFUSED = 2


class Refused(Exception):
    """Pagar menolak menjalankan skrip (kode keluar 2)."""


# ── argumen ─────────────────────────────────────────────────────────────────────────────────────────────────────
def build_parser(description: str, *, undo: bool = True, db_default: Optional[str] = None) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--db", required=db_default is None, default=db_default,
                    help=f"nama DB — uji {list(TEST_DBS)} atau produksi {list(PRODUCTION_DBS)} (+ --production)")
    ap.add_argument("--apply", action="store_true", help="terapkan (tanpa ini = dry-run, tidak menulis apa pun)")
    if undo:
        ap.add_argument("--undo", action="store_true",
                        help="kembalikan perubahan putaran --apply terakhir (atau --run-id) dari jejak; tanpa --apply = dry-run")
        ap.add_argument("--run-id", default="", help="putaran yang dikembalikan (bawaan: putaran terakhir yang belum dibalik)")
    ap.add_argument("--production", action="store_true", help="WAJIB untuk DB produksi (kainnusantara)")
    ap.add_argument("--backup-file", default="",
                    help="berkas backup terbaru: jalur (diperiksa isinya) atau nama `<db>-YYYY-MM-DD_HHMM.archive.gz`")
    ap.add_argument("--backup-dir", default="", help="direktori backup (bawaan: <repo>/deploy/backups bila terlihat)")
    ap.add_argument("--backup-confirmed", default="",
                    help="konfirmasi manual backup < 24 jam (≥ 5 huruf; tulis nama berkas & pemeriksa) bila berkas tak terlihat")
    ap.add_argument("--show", type=int, default=50, help="baris contoh per langkah di laporan (0 = semua)")
    ap.add_argument("--report", default="", help="tulis laporan lengkap (JSON) ke jalur ini")
    return ap


def _letters(text: str) -> int:
    return sum(1 for ch in str(text or "") if ch.isalpha())


def _repo_backup_dirs(extra: str = "") -> List[Path]:
    here = Path(__file__).resolve()
    out = [Path(extra)] if extra else []
    out += [here.parents[2] / "deploy" / "backups", Path("/app/deploy/backups"), Path("/backups")]
    seen, uniq = set(), []
    for p in out:
        if str(p) not in seen:
            seen.add(str(p))
            uniq.append(p)
    return uniq


def verify_backup_file(path: Path, db_name: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Berkas backup terlihat → periksa nama, umur (mtime), ukuran, gzip utuh, penanda arsip mongodump."""
    now = now or datetime.now(timezone.utc)
    if not path.is_file():
        raise Refused(f"berkas backup {path} tidak ada.")
    if not path.name.startswith(f"{db_name}-") or not path.name.endswith(".archive.gz"):
        raise Refused(f"berkas backup {path.name} bukan backup DB {db_name} (nama wajib `{db_name}-…archive.gz`).")
    st = path.stat()
    age_h = (now.timestamp() - st.st_mtime) / 3600
    if age_h > BACKUP_MAX_AGE_HOURS:
        raise Refused(f"backup {path.name} berumur {age_h:.1f} jam (> {BACKUP_MAX_AGE_HOURS} jam) — jalankan `bash deploy/backup.sh` dulu.")
    if age_h < -1:
        raise Refused(f"waktu berkas backup {path.name} di masa depan — periksa jam server.")
    if st.st_size < BACKUP_MIN_BYTES:
        raise Refused(f"backup {path.name} hanya {st.st_size} bita (< {BACKUP_MIN_BYTES // 1024} KB) — kemungkinan gagal/terpotong.")
    try:
        with gzip.open(path, "rb") as gz:
            head = gz.read(4)
            while gz.read(4 * 1024 * 1024):
                pass
    except (OSError, EOFError) as exc:
        raise Refused(f"backup {path.name} RUSAK/terpotong (gzip tidak bisa dibaca sampai habis): {exc}") from exc
    if head != ARCHIVE_MAGIC:
        raise Refused(f"backup {path.name} bukan arsip mongodump (penanda awal {head.hex()}).")
    return {"kind": "file_verified", "file": str(path), "name": path.name, "bytes": st.st_size,
            "age_hours": round(age_h, 2), "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()}


_NAME_RX = re.compile(r"^(?P<db>[A-Za-z0-9_]+)-(?P<d>\d{4}-\d{2}-\d{2})_(?P<t>\d{4})\.archive\.gz$")


def backup_from_name(name: str, db_name: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Berkas tidak terlihat (kontainer) → cap waktu di nama dibaca WIB (konservatif) dan wajib < 24 jam."""
    now = now or datetime.now(timezone.utc)
    m = _NAME_RX.match(Path(name).name)
    if not m:
        raise Refused(f"nama backup `{name}` tidak berpola `{db_name}-YYYY-MM-DD_HHMM.archive.gz` (keluaran deploy/backup.sh).")
    if m.group("db") != db_name:
        raise Refused(f"backup `{name}` milik DB {m.group('db')}, bukan {db_name}.")
    stamp = datetime.strptime(f"{m.group('d')} {m.group('t')}", "%Y-%m-%d %H%M").replace(tzinfo=WIB)
    age_h = (now - stamp).total_seconds() / 3600
    if age_h > BACKUP_MAX_AGE_HOURS:
        raise Refused(f"backup `{name}` berumur ±{age_h:.1f} jam (> {BACKUP_MAX_AGE_HOURS} jam) — jalankan `bash deploy/backup.sh` dulu.")
    if age_h < -1:
        raise Refused(f"cap waktu backup `{name}` di masa depan — periksa nama berkas.")
    return {"kind": "name_stamp", "name": Path(name).name, "age_hours": round(age_h, 2),
            "note": "berkas tidak terlihat dari proses ini; umur dihitung dari cap waktu nama (WIB)"}


def backup_evidence(db_name: str, backup_file: str = "", backup_dir: str = "", confirmed: str = "",
                    now: Optional[datetime] = None) -> Dict[str, Any]:
    """Bukti backup < 24 jam untuk DB produksi. Raise `Refused` bila tidak ada bukti yang sah."""
    if backup_file:
        p = Path(backup_file)
        if p.exists():
            return verify_backup_file(p, db_name, now)
        for d in _repo_backup_dirs(backup_dir):
            if (d / p.name).exists():
                return verify_backup_file(d / p.name, db_name, now)
        return backup_from_name(p.name, db_name, now)
    for d in _repo_backup_dirs(backup_dir):
        if not d.is_dir():
            continue
        cands = sorted(d.glob(f"{db_name}-*.archive.gz"), key=lambda x: x.stat().st_mtime, reverse=True)
        if cands:
            return verify_backup_file(cands[0], db_name, now)
    if confirmed:
        if _letters(confirmed) < 5:
            raise Refused("--backup-confirmed wajib berisi keterangan ≥ 5 huruf (nama berkas backup & pemeriksa).")
        return {"kind": "manual_confirmation", "text": confirmed.strip(),
                "note": "operator menyatakan backup < 24 jam ada; berkas tidak diperiksa skrip"}
    raise Refused("DB produksi wajib bukti backup < 24 jam: `--backup-file <jalur atau nama berkas>` (keluaran "
                  "deploy/backup.sh) atau `--backup-confirmed \"<nama berkas & pemeriksa>\"`. Jalankan `bash deploy/backup.sh` dulu.")


def guard(args: argparse.Namespace, script: str, test_dbs: Sequence[str] = TEST_DBS) -> Dict[str, Any]:
    """Putuskan boleh/tidak (tanpa menyentuh DB). Return info mode; raise `Refused`."""
    db_name = (args.db or "").strip()
    production = bool(getattr(args, "production", False))
    if db_name in PRODUCTION_DBS:
        if not production:
            raise Refused(f"`--db {db_name}` adalah DB PRODUKSI — wajib flag eksplisit `--production` (dan bukti backup).")
        evidence = backup_evidence(db_name, args.backup_file, args.backup_dir, args.backup_confirmed)
        return {"db": db_name, "production": True, "backup": evidence}
    if production:
        raise Refused(f"`--production` hanya untuk DB produksi {list(PRODUCTION_DBS)}; `--db {db_name}` bukan DB produksi.")
    if db_name not in test_dbs:
        raise Refused(f"skrip ini hanya untuk DB uji {sorted(test_dbs)} atau produksi {list(PRODUCTION_DBS)} "
                      f"(+ --production); --db {db_name} tidak diproses.")
    return {"db": db_name, "production": False, "backup": None}


def parse_and_guard(ap: argparse.ArgumentParser, script: str, test_dbs: Sequence[str] = TEST_DBS,
                    argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse argumen, terapkan pagar, set `DB_NAME` (sebelum `db.py` diimpor). Ditolak → cetak alasan, keluar 2."""
    args = ap.parse_args(argv)
    try:
        info = guard(args, script, test_dbs)
    except Refused as exc:
        print(f"DITOLAK: {exc}")
        sys.exit(REFUSED)
    os.environ["DB_NAME"] = info["db"]
    args.guard_info = info
    args.script = script
    args.mode = ("UNDO " if getattr(args, "undo", False) else "") + ("TERAPKAN" if args.apply else "DRY-RUN")
    args.run_id = getattr(args, "run_id", "") or ""
    return args


def banner(args: argparse.Namespace) -> None:
    info = args.guard_info
    host = re.sub(r"//[^@/]*@", "//***@", os.environ.get("MONGO_URL", ""))
    print(f"== {args.script} · {args.mode} · DB {info['db']}{' (PRODUKSI)' if info['production'] else ' (uji)'} · {host}")
    if info.get("backup"):
        b = info["backup"]
        print(f"   bukti backup: {b['kind']} — {b.get('name') or b.get('text')}"
              + (f" (±{b['age_hours']} jam)" if "age_hours" in b else ""))
        if b["kind"] != "file_verified":
            print(f"   PERINGATAN: isi berkas backup TIDAK diperiksa skrip ({b.get('note')}). Pastikan berkas itu ada, "
                  "ukurannya wajar, dan `bash deploy/backup.sh` tadi selesai tanpa galat.")
    if not args.apply:
        print("   DRY-RUN: tidak ada yang ditulis. Tambah --apply untuk menerapkan.")


# ── nilai field (termasuk bertitik) ─────────────────────────────────────────────────────────────────────────────
_MISSING = object()


def get_path(doc: Dict[str, Any], path: str) -> Any:
    cur: Any = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def snapshot(doc: Dict[str, Any], fields: Iterable[str]) -> Tuple[Dict[str, Any], List[str]]:
    """→ (nilai sebelum yang ADA, daftar field yang TIDAK ada) — undo memulihkan persis (set / unset)."""
    before, missing = {}, []
    for f in fields:
        v = get_path(doc, f)
        if v is _MISSING:
            missing.append(f)
        else:
            before[f] = v
    return before, missing


# ── rencana & jejak ─────────────────────────────────────────────────────────────────────────────────────────────
def _short(v: Any, n: int = 60) -> str:
    s = "∅" if v is None else str(v)
    return s if len(s) <= n else s[: n - 1] + "…"


class Plan:
    """Kumpulan perubahan per langkah. `change()` dipanggil SESUDAH tulisan sukses (apply) atau sebagai rencana (dry-run)."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.run_id = f"{datetime.now(WIB).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.steps: Dict[str, Dict[str, Any]] = {}
        self.changes: List[Dict[str, Any]] = []

    def step(self, name: str, title: str = "") -> Dict[str, Any]:
        return self.steps.setdefault(name, {"title": title, "count": 0, "report": None})

    def change(self, step: str, coll: str, doc_id: str, *, label: str = "", before: Optional[Dict[str, Any]] = None,
               missing: Optional[List[str]] = None, after: Optional[Dict[str, Any]] = None,
               pushed: Optional[Dict[str, Any]] = None, inserted: Optional[Dict[str, Any]] = None,
               segment: Optional[Tuple[Any, Any, Any]] = None, note: str = "",
               doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """`doc` = dokumen SEBELUM (bila ada `pushed`): larik riwayat yang tadinya tidak ada dicatat `pushed_new` agar
        undo menghapusnya lagi (bukan menyisakan larik kosong)."""
        pushed_new = [f for f in (pushed or {}) if doc is not None and get_path(doc, f) is _MISSING]
        row = {"step": step, "collection": coll, "doc_id": doc_id, "label": label, "before": before or {},
               "missing": list(missing or []), "after": after or {}, "pushed": pushed or {},
               "pushed_new": pushed_new, "inserted": inserted or {}, "segment": list(segment) if segment else None,
               "note": note}
        self.changes.append(row)
        self.step(step)["count"] += 1
        return row

    def report_only(self, step: str, payload: Dict[str, Any], title: str = "") -> None:
        st = self.step(step, title)
        st["report"] = payload
        st["count"] = payload.get("count", 0)

    # ── cetak ──
    def print(self) -> None:
        show = self.args.show
        print(f"   putaran {self.run_id}")
        for name, st in self.steps.items():
            print(f"  [{name}] {st['count']} {'(laporan saja, tidak diubah)' if st['report'] is not None else 'perubahan'}"
                  + (f" — {st['title']}" if st["title"] else ""))
            if st["report"] is not None:
                for r in (st["report"].get("rows") or st["report"].get("ids") or [])[: show or None]:
                    print(f"      · {_short(r, 140)}")
                continue
            rows = [c for c in self.changes if c["step"] == name]
            for c in rows[: show or None]:
                fields = list(c["after"]) or list(c["before"])
                diff = "; ".join(f"{f}: {_short(c['before'].get(f, '∅' if f in c['missing'] else None), 40)} → "
                                 f"{_short(c['after'].get(f), 40)}" for f in fields if f != "updated_at")
                extra = (" +riwayat" if c["pushed"] else "") + (" +mutasi " + str(c["inserted"].get("id")) if c["inserted"] else "")
                print(f"      · {c['collection']} {c['doc_id']}{(' ' + c['label']) if c['label'] else ''}: {diff}{extra}"
                      + (f" ({c['note']})" if c["note"] else ""))
            if show and len(rows) > show:
                print(f"      … {len(rows) - show} lainnya (--show 0 untuk semua, --report untuk berkas JSON)")

    def write_report(self) -> None:
        if not self.args.report:
            return
        import json
        Path(self.args.report).write_text(json.dumps({
            "script": self.args.script, "mode": self.args.mode, "run_id": self.run_id, "guard": self.args.guard_info,
            "steps": {k: {"count": v["count"], "title": v["title"], "report": v["report"]} for k, v in self.steps.items()},
            "changes": self.changes}, ensure_ascii=False, indent=1, default=str))
        print(f"   laporan lengkap: {self.args.report}")

    # ── simpan jejak ──
    async def save(self, db: Any, actor: str, kind: str = "apply", undone_run: str = "") -> None:
        """Jejak per perubahan (audit) + sumber undo (migrations). Dipanggil hanya saat --apply."""
        from core_utils import now_iso
        from dependencies import audit
        flag = self.args.script
        action = "data_fix_undone" if kind == "undo" else "data_fix_applied"
        for c in self.changes:
            after = {_human(k): v for k, v in c["after"].items()}
            if c["inserted"]:
                after["_disisipkan"] = f"{c['inserted'].get('collection')}:{c['inserted'].get('id')}"
            await audit(actor, action, c["collection"], str(c["doc_id"]), after,
                        reason=f"{flag} · {c['step']}" + (f" · balik {undone_run}" if undone_run else ""),
                        before={**{_human(k): v for k, v in c["before"].items()}, **{_human(f): None for f in c["missing"]}},
                        source=f"{flag}#{self.run_id}")
        for i in range(0, len(self.changes), CHUNK):
            await db.migrations.insert_one({
                "id": f"{flag}:changes:{self.run_id}:{i // CHUNK:04d}", "kind": "data_fix_changes", "flag": flag,
                "run_id": self.run_id, "run_kind": kind, "seq": i // CHUNK, "at": now_iso(),
                "changes": [_encode(c) for c in self.changes[i:i + CHUNK]]})
        summary = {"run_id": self.run_id, "kind": kind, "at": now_iso(), "by": actor, "db": self.args.guard_info["db"],
                   "production": self.args.guard_info["production"], "backup": self.args.guard_info.get("backup"),
                   "counts": {k: v["count"] for k, v in self.steps.items()}, "changes": len(self.changes),
                   "undone_run": undone_run or None}
        await db.migrations.update_one({"id": flag}, {"$set": {"id": flag, "last_run_at": now_iso(), "by": actor},
                                                      "$push": {"run_log": summary}}, upsert=True)
        if undone_run:
            await db.migrations.update_one({"id": flag, "run_log.run_id": undone_run},
                                           {"$set": {"run_log.$.undone_at": now_iso(), "run_log.$.undone_by_run": self.run_id}})
        print(f"   jejak: {len(self.changes)} baris audit_logs (source {flag}#{self.run_id}) + migrations.{flag}")


async def load_run(db: Any, flag: str, run_id: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    """Perubahan satu putaran --apply untuk dibalik: `run_id` atau putaran apply terakhir yang belum dibalik."""
    mig = await db.migrations.find_one({"id": flag}, {"_id": 0, "run_log": 1}) or {}
    runs = [r for r in mig.get("run_log") or [] if r.get("kind") == "apply"]
    if run_id:
        runs = [r for r in runs if r.get("run_id") == run_id]
        if not runs:
            raise Refused(f"putaran {run_id} tidak ada di jejak migrations.{flag}.")
    else:
        runs = [r for r in runs if not r.get("undone_at")]
    if not runs:
        return "", []
    rid = runs[-1]["run_id"]
    if runs[-1].get("undone_at"):
        raise Refused(f"putaran {rid} sudah dibalik pada {runs[-1]['undone_at']}.")
    changes: List[Dict[str, Any]] = []
    async for d in db.migrations.find({"kind": "data_fix_changes", "flag": flag, "run_id": rid}, {"_id": 0}).sort("seq", 1):
        changes.extend(_decode(c) for c in d.get("changes") or [])
    return rid, changes


# Nama field bertitik (mis. `escalation.status`) tidak disimpan sebagai KUNCI dokumen (ambigu untuk kueri) — sumber
# undo menyimpannya sebagai pasangan {f, v}; jejak audit memakai "escalation›status".
_PAIR_KEYS = ("before", "after", "pushed")


def _human(key: str) -> str:
    return key.replace(".", "›")


def _encode(c: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(c)
    for k in _PAIR_KEYS:
        out[k] = [{"f": f, "v": v} for f, v in (c.get(k) or {}).items()]
    return out


def _decode(c: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(c)
    for k in _PAIR_KEYS:
        v = c.get(k)
        out[k] = {p["f"]: p.get("v") for p in v} if isinstance(v, list) else dict(v or {})
    return out


def restore_update(c: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """(filter, update) undo satu perubahan: hanya bila field yang ditulis skrip MASIH bernilai sama (tidak diubah orang
    lain sesudahnya); field sebelum dipulihkan persis (set / unset), entri riwayat yang ditambahkan dicabut."""
    flt: Dict[str, Any] = {"id": c["doc_id"]}
    for f, v in c["after"].items():
        flt[f] = v
    upd: Dict[str, Any] = {}
    if c["before"]:
        upd["$set"] = dict(c["before"])
    if c["missing"]:
        upd["$unset"] = {f: "" for f in c["missing"]}
    if c["pushed"]:
        upd["$pull"] = dict(c["pushed"])
    return flt, upd


async def apply_restore(db: Any, c: Dict[str, Any]) -> bool:
    """Jalankan undo satu perubahan (lihat `restore_update`) + hapus larik riwayat yang dulu dibuat skrip & kini kosong.
    → True bila dokumen dipulihkan; False bila dilewati (sudah diubah sesudah skrip)."""
    flt, upd = restore_update(c)
    res = await db[c["collection"]].update_one(flt, upd)
    if not res.modified_count:
        return False
    for f in c.get("pushed_new") or []:
        await db[c["collection"]].update_one({"id": c["doc_id"], f: {"$size": 0}}, {"$unset": {f: ""}})
    return True


async def drain_tasks(timeout: float = 2.0) -> None:
    """Beri waktu tugas latar `audit()` (notifikasi giliran) selesai sebelum proses keluar."""
    import asyncio
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.wait(pending, timeout=timeout)


def print_refusal_and_exit(exc: Refused) -> None:
    print(f"DITOLAK: {exc}")
    sys.exit(REFUSED)
