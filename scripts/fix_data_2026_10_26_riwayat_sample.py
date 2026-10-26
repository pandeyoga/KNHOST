#!/usr/bin/env python3
"""Perbaikan data lama G5-46 (fase 4 · R7) — teks riwayat sample yang ditulis SEBELUM G5-46.

G5-46 mengganti teks riwayat sample BARU ("Ronde", label jenis "Labdip", hasil "ACC"/"revisi"/"ditolak",
tanggal "30 Okt 2026", "draf"); entri lama di DB tetap berbunyi "Round 1 (labdip · CV …) → acc",
"Permintaan sample dibuat (draft)", "target 2026-10-30", "Sample ditandai JADI (2026-10-23)". Skrip ini
menulis ulang HANYA pola yang dihasilkan kode lama, dengan pemetaan YANG SAMA dengan kode baru
(`rnd_sample_service._jenis_label`, `_tgl_id`, `_RESULT_LABEL`) — angka, nama supplier, nama orang dan
catatan tidak diubah. Teks asli disimpan di entri yang sama (`legacy_label` / `legacy_note`) supaya jejak
tidak hilang. Tidak ada entri yang dihapus/ditambah; urutan & waktu tetap.

Cakupan:
  * `md_samples.timeline[].label` — event created / sent / round_opened / round_submitted / round_assessed /
    finished / delivered;
  * `design_gallery.timeline[].note` — event proofing_finished / sample_finished ("<no> ditandai JADI (…)").
Idempoten: label yang sudah berbentuk baru tidak cocok pola lama.

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_10_26_riwayat_sample.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_10_26_riwayat_sample.py --db kn_test_trial --apply
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path


def _args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help="nama DB yang diperbaiki (mis. kn_test_trial, kn_uat_23okt)")
    ap.add_argument("--apply", action="store_true", help="terapkan (tanpa ini = dry-run)")
    return ap.parse_args()


ARGS = _args()
os.environ["DB_NAME"] = ARGS.db          # db.py membaca DB_NAME saat di-import
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from services.rnd_sample_service import _RESULT_LABEL, _jenis_label, _tgl_id  # noqa: E402

FLAG = "fix_data_2026_10_26_riwayat_sample"
DATE = r"(\d{4}-\d{2}-\d{2})"


def _kinds(text: str) -> str:
    return ", ".join(_jenis_label(k.strip()) for k in text.split(",") if k.strip())


# (event, pola teks lama, pembentuk teks baru) — kalimat baru = f-string kode baru (rnd_sample_service.py).
SAMPLE_RULES = [
    ("created", re.compile(r"^Permintaan sample dibuat \(draft\)$"),
     lambda m: "Permintaan sample dibuat (draf)"),
    ("sent", re.compile(r"^Dikirim: (\d+) round dibuka \((\d+) supplier × (\d+) jenis: (.+)\) · target (.*)$"),
     lambda m: (f"Dikirim ke supplier: {m[1]} ronde dibuka ({m[2]} supplier × {m[3]} jenis: {_kinds(m[4])}) "
                f"· target {_tgl_id(m[5])}")),
    ("round_opened", re.compile(r"^Round (\d+) \(([^()]+)\) dibuka untuk (.*)$"),
     lambda m: f"Ronde {m[1]} ({_jenis_label(m[2])}) dibuka untuk {m[3]}"),
    ("round_submitted", re.compile(r"^Hasil round (\d+) \(([^()]+)\) (dari .*)$"),
     lambda m: f"Hasil ronde {m[1]} ({_jenis_label(m[2])}) {m[3]}"),
    ("round_assessed", re.compile(r"^Round (\d+) \(([^ ·()]+) · (.*)\) → ([a-z_]+)((?: · skor .*)?)$"),
     lambda m: f"Ronde {m[1]} ({_jenis_label(m[2])} · {m[3]}) → {_RESULT_LABEL.get(m[4], m[4])}{m[5]}"),
    ("finished", re.compile(r"^Sample ditandai JADI \(" + DATE + r"\)$"),
     lambda m: f"Sampel fisik diterima ({_tgl_id(m[1])})"),
    ("delivered", re.compile(r"^(Sample dikirim ke .*) \(" + DATE + r"\)$"),
     lambda m: f"{m[1]} ({_tgl_id(m[2])})"),
]
# Catatan proofing di timeline desain (`_log_design` → design_gallery.timeline[].note).
DESIGN_RULES = [
    (("proofing_finished", "sample_finished"), re.compile(r"^(\S+) ditandai JADI \(" + DATE + r"\)(.*)$"),
     lambda m: f"{m[1]}: sampel fisik diterima ({_tgl_id(m[2])}){m[3]}"),
]


def _new_sample_label(entry: dict):
    label = entry.get("label") or ""
    for ev, pat, make in SAMPLE_RULES:
        if entry.get("event") == ev:
            m = pat.match(label)
            if m:
                return make(m)
    return None


def _new_design_note(entry: dict):
    note = entry.get("note") or ""
    for evs, pat, make in DESIGN_RULES:
        if entry.get("event") in evs:
            m = pat.match(note)
            if m:
                return make(m)
    return None


async def _plan() -> list:
    out = []
    async for s in db.md_samples.find({"timeline": {"$exists": True}}, {"_id": 0, "id": 1, "number": 1, "timeline": 1}):
        for i, t in enumerate(s.get("timeline") or []):
            new = _new_sample_label(t)
            if new and new != t.get("label"):
                out.append({"coll": "md_samples", "id": s["id"], "doc": s.get("number"), "idx": i,
                            "field": "label", "event": t.get("event"), "old": t.get("label"), "new": new})
    async for d in db.design_gallery.find({"timeline.note": {"$regex": "ditandai JADI"}},
                                          {"_id": 0, "id": 1, "code": 1, "timeline": 1}):
        for i, t in enumerate(d.get("timeline") or []):
            new = _new_design_note(t)
            if new and new != t.get("note"):
                out.append({"coll": "design_gallery", "id": d["id"], "doc": d.get("code"), "idx": i,
                            "field": "note", "event": t.get("event"), "old": t.get("note"), "new": new})
    return out


# "revisi" sama di kode lama & baru (_RESULT_LABEL) → bukan penanda teks lama.
SUSPECT = re.compile(r"\b[Rr]ound\b|\(draft\)|ditandai JADI|\d{4}-\d{2}-\d{2}|→ (acc|tolak)\b")


async def _suspects(plan: list) -> list:
    """Teks yang MASIH tampak lama tetapi tidak cocok pola mana pun — dilaporkan, tidak diubah."""
    planned = {(p["coll"], p["id"], p["idx"]) for p in plan}
    out = []
    async for s in db.md_samples.find({}, {"_id": 0, "id": 1, "number": 1, "timeline": 1}):
        for i, t in enumerate(s.get("timeline") or []):
            if ("md_samples", s["id"], i) not in planned and SUSPECT.search(t.get("label") or ""):
                out.append(f"md_samples {s.get('number')} #{i} [{t.get('event')}] {t.get('label')}")
    return out


async def main() -> int:
    mode = "APPLY" if ARGS.apply else "DRY-RUN"
    print(f"== {FLAG} · DB {ARGS.db} · {mode}")
    plan = await _plan()
    for line in await _suspects(plan):
        print(f"  ! tidak dikenali (dibiarkan): {line}")
    print(f"Entri riwayat berteks lama: {len(plan)} "
          f"(md_samples {sum(p['coll'] == 'md_samples' for p in plan)}, "
          f"design_gallery {sum(p['coll'] == 'design_gallery' for p in plan)})")
    for p in plan:
        print(f"  - {p['coll']} {p['doc']} #{p['idx']} [{p['event']}]\n      lama: {p['old']}\n      baru: {p['new']}")
    if not ARGS.apply:
        print("DRY-RUN — tidak ada yang ditulis. Ulangi dengan --apply untuk menerapkan.")
        return 0
    done = 0
    for p in plan:
        key = f"timeline.{p['idx']}"
        res = await db[p["coll"]].update_one(
            {"id": p["id"], f"{key}.{p['field']}": p["old"], f"{key}.event": p["event"]},
            {"$set": {f"{key}.{p['field']}": p["new"], f"{key}.legacy_{p['field']}": p["old"]}})
        done += res.modified_count
    left = await _plan()
    await db.migrations.update_one({"id": FLAG}, {
        "$set": {"applied_at": now_iso()},
        "$push": {"runs": {"at": now_iso(), "db": ARGS.db, "changed": done,
                           "entries": [{k: p[k] for k in ("coll", "doc", "idx", "event", "old", "new")} for p in plan]}}},
        upsert=True)
    print(f"Diterapkan: {done}/{len(plan)} entri · sisa berteks lama: {len(left)}")
    return 0 if done == len(plan) and not left else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
