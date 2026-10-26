#!/usr/bin/env python3
"""Pembersihan data uji G1-33 (fase 4 · R9) — entri eliminasi antar-PT otomatis yang BASI.

Latar (laporan R6 §6): pembersihan uji otomatis menghapus dokumen `interco_transactions` LANGSUNG di DB, tanpa
menghapus entri `intercompany_eliminations` (auto G-6) miliknya — sebagian juga meninggalkan jurnal transaksi
per-PT (`source_type = interco_transaction`, `source_id = <pair>:seller|buyer|…`). Laporan konsolidasi lalu terus
mengeliminasi angka yang dokumennya sudah hilang. Deteksi = `consolidation_stale_service.stale_g6_eliminations()`
(satu definisi dengan ringkasan konsolidasi `eliminations_stale` dan invarian INV-IC-03).

Izin pemilik (26 Okt, HANYA DB uji `kn_test_trial`; DB UAT ditolak skrip):
  * entri basi TANPA dokumen & TANPA jurnal → entri eliminasinya dihapus;
  * entri basi yang jurnal transaksinya MASIH ada → jurnal transaksi yatim itu dihapus BERSAMA entri eliminasinya
    (residu uji). Jurnal hanya dihapus bila `source_id` = pair entri itu dan tidak menyentuh dokumen hidup.

Entri DILEWATI (dicatat, tidak diubah) bila ragu:
  * masih ada dokumen `interco_transactions` untuk pair itu (draf/batal) — beda dari deskripsi izin;
  * (khusus yang berjurnal) pair/jurnalnya masih dirujuk dokumen lain (mis. pelunasan antar-PT hidup), IC-AR/IC-AP
    atau pendapatan di jurnal pair ≠ yang dieliminasi entri (artinya saldo pair juga bergerak di jurnal LAIN —
    pelunasan/retur — sehingga menghapus jurnal transaksinya saja meninggalkan saldo yatim baru), jurnal sudah
    dibalik/dianulir/dirujuk jurnal pembalik, atau tanggalnya di periode tertutup.

Penghapusan memakai jalur layanan yang sama dengan layar: entri eliminasi lewat
`consolidation_service.delete_elimination` + baris audit `ic_elimination_deleted` (seperti tombol hapus di layar
Konsolidasi); jurnal yatim dihapus per id (dokumen lengkapnya disimpan di `migrations`) + audit
`journal_entry_deleted`. Setiap `--apply` mencatat sebelum/sesudah (ringkasan konsolidasi, neraca saldo per PT,
saldo IC) di koleksi `migrations` (`id = fix_data_2026_10_26_eliminasi_basi`). Idempoten: entri yang sudah hilang
tidak terdeteksi lagi.

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_10_26_eliminasi_basi.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_10_26_eliminasi_basi.py --db kn_test_trial --apply
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_DB = "kn_test_trial"


def _args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help=f"nama DB — HANYA {ALLOWED_DB} yang diizinkan")
    ap.add_argument("--apply", action="store_true", help="terapkan (tanpa ini = dry-run)")
    return ap.parse_args()


ARGS = _args()
if ARGS.db != ALLOWED_DB:
    print(f"DITOLAK: izin pemilik hanya untuk DB {ALLOWED_DB}; --db {ARGS.db} tidak diproses.")
    sys.exit(2)
os.environ["DB_NAME"] = ARGS.db          # db.py membaca DB_NAME saat di-import
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from dependencies import audit  # noqa: E402
from services import closing_service  # noqa: E402
from services import consolidation_service as cons  # noqa: E402
from services.consolidation_stale_service import stale_g6_eliminations  # noqa: E402
from services.gl_service import ACC_IC_AP, ACC_IC_AR, ACC_PENDAPATAN  # noqa: E402

FLAG = "fix_data_2026_10_26_eliminasi_basi"
ACTOR = "Sistem (pembersihan data uji)"
REASON = "Residu uji — dokumen antar-PT sumbernya sudah dihapus"
# Koleksi yang BOLEH menyebut pair/jurnal tanpa membuatnya "dirujuk dokumen hidup": riwayat & objek yang memang
# sedang dibersihkan.
_REF_IGNORE = {"audit_logs", "migrations", "intercompany_eliminations", "journal_entries", "notifications"}


def _rp(x: float) -> str:
    return f"Rp {x:,.0f}".replace(",", ".")


def _sum(lines, code: str, side: str) -> float:
    return round(sum(float(ln.get(side) or 0) for ln in lines or [] if str(ln.get("account_code")) == code), 2)


async def _pair_journals(pid: str) -> list:
    return await db.journal_entries.find(
        {"source_type": "interco_transaction", "source_id": {"$regex": f"^{re.escape(pid)}(:|$)"}},
        {"_id": 0}).sort("number", 1).to_list(None)


async def _scan_refs(needles: list) -> dict:
    """Rujukan teks ke pair/jurnal di SEMUA koleksi lain (dokumen hidup yang masih menunjuknya)."""
    if not needles:
        return {}
    pat = re.compile("|".join(re.escape(n) for n in needles if n))
    hits: dict = {}
    for coll in sorted(await db.list_collection_names()):
        if coll in _REF_IGNORE or coll.startswith("system."):
            continue
        async for d in db[coll].find({}):
            s = json.dumps(d, default=str, ensure_ascii=False)
            for m in set(pat.findall(s)):
                hits.setdefault(m, []).append(f"{coll}:{d.get('number') or d.get('code') or d.get('id') or d.get('_id')}")
    return hits


async def _plan() -> list:
    stale = await stale_g6_eliminations()
    pjs = {s["pair_id"]: await _pair_journals(s["pair_id"]) for s in stale}
    needles = [s["pair_id"] for s in stale]
    for js in pjs.values():
        needles += [j["id"] for j in js] + [j.get("number") for j in js if j.get("number")]
    refs = await _scan_refs(needles)
    plan = []
    for s in stale:
        pid = s["pair_id"]
        elim = await db.intercompany_eliminations.find_one({"id": s["id"]}, {"_id": 0})
        js = pjs[pid]
        skip, notes = [], []
        docs_left = await db.interco_transactions.count_documents({"pair_id": pid})
        if docs_left:
            skip.append(f"masih ada {docs_left} dokumen antar-PT (draf/batal) untuk pair ini")
        pair_refs = refs.get(pid, [])
        if not js:
            if pair_refs:
                notes.append(f"pair masih disebut dokumen lain (tidak diubah): {', '.join(pair_refs[:8])}"
                             + (f" … (+{len(pair_refs) - 8})" if len(pair_refs) > 8 else ""))
        else:
            if pair_refs:
                skip.append(f"pair masih dirujuk dokumen hidup: {', '.join(pair_refs[:6])}")
            for j in js:
                jr = refs.get(j["id"], []) + refs.get(j.get("number") or "\0", [])
                if jr:
                    skip.append(f"{j.get('number')} dirujuk dokumen lain: {', '.join(jr[:4])}")
                if j.get("status") != "posted":
                    skip.append(f"{j.get('number')} berstatus {j.get('status')}")
                if j.get("reversed_by_entry_id") or j.get("backdated_in_unlock") or j.get("voided_in_unlock"):
                    skip.append(f"{j.get('number')} sudah dibalik/berjejak buka-periode")
                if await db.journal_entries.count_documents(
                        {"$or": [{"source_id": j["id"]}, {"ref.reverses_entry_id": j["id"]}]}):
                    skip.append(f"{j.get('number')} dirujuk jurnal pembalik")
                st = await closing_service.status_for_date(j.get("date") or "", j.get("entity_id") or "")
                if st.get("closed"):
                    skip.append(f"{j.get('number')} berada di periode tertutup {st.get('period_label')}")
            lines = [ln for j in js for ln in j.get("lines") or []]
            ar_net = round(_sum(lines, ACC_IC_AR, "debit") - _sum(lines, ACC_IC_AR, "credit"), 2)
            ap_net = round(_sum(lines, ACC_IC_AP, "credit") - _sum(lines, ACC_IC_AP, "debit"), 2)
            rev = round(_sum(lines, ACC_PENDAPATAN, "credit") - _sum(lines, ACC_PENDAPATAN, "debit"), 2)
            el = elim.get("lines") or []
            e_ar, e_ap, e_rev = _sum(el, ACC_IC_AR, "credit"), _sum(el, ACC_IC_AP, "debit"), _sum(el, ACC_PENDAPATAN, "debit")
            if abs(ar_net - e_ar) > 0.01 or abs(ap_net - e_ap) > 0.01:
                skip.append(f"IC-AR/IC-AP di jurnal pair ({_rp(ar_net)} / {_rp(ap_net)}) ≠ yang dieliminasi entri "
                            f"({_rp(e_ar)} / {_rp(e_ap)}) — saldo pair ini juga bergerak di jurnal lain "
                            f"(pelunasan/retur); menghapus jurnal transaksinya saja meninggalkan saldo yatim baru")
            if abs(rev - e_rev) > 0.01:
                skip.append(f"pendapatan di jurnal pair {_rp(rev)} ≠ pendapatan dieliminasi {_rp(e_rev)}")
        plan.append({"elim": elim, "stale": s, "journals": js, "skip": skip, "notes": notes,
                     "kind": "berjurnal" if js else "tanpa_jurnal"})
    return plan


async def _metrics() -> dict:
    """Angka pembanding sebelum/sesudah: ringkasan konsolidasi grup, neraca saldo per PT, saldo IC jurnal."""
    ents = [e["id"] async for e in db.business_entities.find({}, {"_id": 0, "id": 1})]
    today = datetime.now(timezone.utc)
    summ = await cons.summary(ents, today.year, today.strftime("%Y-%m-%d"))
    tb = {}
    async for a in db.journal_entries.aggregate([
            {"$match": {"status": "posted"}}, {"$unwind": "$lines"},
            {"$group": {"_id": "$entity_id", "d": {"$sum": "$lines.debit"}, "c": {"$sum": "$lines.credit"},
                        "ar": {"$sum": {"$cond": [{"$eq": ["$lines.account_code", ACC_IC_AR]},
                                                  {"$subtract": ["$lines.debit", "$lines.credit"]}, 0]}},
                        "ap": {"$sum": {"$cond": [{"$eq": ["$lines.account_code", ACC_IC_AP]},
                                                  {"$subtract": ["$lines.credit", "$lines.debit"]}, 0]}}}}]):
        tb[a["_id"]] = {"debit": round(a["d"], 2), "credit": round(a["c"], 2),
                        "balanced": abs(a["d"] - a["c"]) < 0.01, "ic_ar_net": round(a["ar"], 2),
                        "ic_ap_net": round(a["ap"], 2)}
    return {
        "as_of": summ["as_of"], "year": summ["year"],
        "eliminations_count": summ["eliminations_count"],
        "eliminations_stale_count": summ["eliminations_stale_count"],
        "stale_ic_ar_total": round(sum(x["ic_ar_eliminated"] for x in summ["eliminations_stale"]), 2),
        "gross": summ["gross"], "elimination": summ["elimination"], "consolidated": summ["consolidated"],
        "consolidated_balanced": summ["balanced"],
        "trial_balance": tb,
        "journals_posted": await db.journal_entries.count_documents({"status": "posted"}),
    }


def _print_metrics(tag: str, m: dict) -> None:
    c, e = m["consolidated"], m["elimination"]
    print(f"[{tag}] eliminasi {m['eliminations_count']} entri · basi {m['eliminations_stale_count']} "
          f"(IC-AR {_rp(m['stale_ic_ar_total'])}) · jurnal posted {m['journals_posted']}")
    print(f"[{tag}] eliminasi: pendapatan {_rp(e['revenue'])}, aset {_rp(e['assets'])}, liabilitas "
          f"{_rp(e['liabilities'])}, ekuitas {_rp(e['equity'])}")
    print(f"[{tag}] konsolidasi {m['year']} per {m['as_of']}: pendapatan {_rp(c['revenue'])}, laba bersih "
          f"{_rp(c['net_income'])}, aset {_rp(c['assets'])} = liabilitas {_rp(c['liabilities'])} + ekuitas "
          f"{_rp(c['equity'])} → seimbang={m['consolidated_balanced']}")
    for eid, t in sorted(m["trial_balance"].items()):
        print(f"[{tag}] neraca saldo {eid}: D {_rp(t['debit'])} = K {_rp(t['credit'])} → seimbang={t['balanced']}"
              f" · IC-AR bersih {_rp(t['ic_ar_net'])} · IC-AP bersih {_rp(t['ic_ap_net'])}")


async def main() -> int:
    mode = "APPLY" if ARGS.apply else "DRY-RUN"
    print(f"== {FLAG} · DB {ARGS.db} · {mode}")
    plan = await _plan()
    todo = [p for p in plan if not p["skip"]]
    print(f"Entri eliminasi auto basi: {len(plan)} · total IC-AR dieliminasi "
          f"{_rp(sum(p['stale']['ic_ar_eliminated'] for p in plan))}")
    for p in plan:
        e, s = p["elim"], p["stale"]
        act = "LEWATI" if p["skip"] else ("hapus entri + jurnal" if p["journals"] else "hapus entri")
        print(f"  - {e.get('name')} [{e['id']} · pair {s['pair_id']}] IC-AR {_rp(s['ic_ar_eliminated'])} · "
              f"jurnal tersisa {len(p['journals'])} → {act}")
        for j in p["journals"]:
            print(f"      jurnal {j.get('number')} ({j.get('entity_id')}, {j.get('source_id')}, {j.get('status')}): "
                  + ", ".join(f"{ln['account_code']} D{ln.get('debit') or 0:g}/K{ln.get('credit') or 0:g}"
                              for ln in j.get("lines") or []))
        for r in p["skip"]:
            print(f"      ragu: {r}")
        for n in p["notes"]:
            print(f"      catatan: {n}")
    n_je = sum(len(p["journals"]) for p in todo)
    print(f"Rencana: hapus {len(todo)} entri ({sum(1 for p in todo if not p['journals'])} tanpa jurnal, "
          f"{sum(1 for p in todo if p['journals'])} berjurnal) + {n_je} jurnal yatim; dilewati "
          f"{len(plan) - len(todo)} entri")
    before = await _metrics()
    _print_metrics("sebelum", before)
    if not ARGS.apply:
        print("DRY-RUN — tidak ada yang ditulis. Ulangi dengan --apply untuk menerapkan.")
        return 0
    if not todo:
        print("Tidak ada yang perlu dibersihkan.")
        return 0
    done = []
    for p in todo:
        e = p["elim"]
        pid = p["stale"]["pair_id"]
        je_nums = [j.get("number") for j in p["journals"]]
        for j in p["journals"]:
            r = await db.journal_entries.delete_one(
                {"id": j["id"], "source_type": "interco_transaction", "source_id": j["source_id"]})
            if r.deleted_count:
                await audit(ACTOR, "journal_entry_deleted", "journal_entry", j["id"],
                            {"number": j.get("number"), "source_id": j.get("source_id"), "deleted": True},
                            reason=f"{REASON} ({e.get('name')}) — jurnal transaksi yatim dihapus bersama entri "
                                   f"eliminasinya", scope_entity_id=j.get("entity_id") or "",
                            before={"number": j.get("number"), "total_debit": j.get("total_debit"),
                                    "total_credit": j.get("total_credit"), "status": j.get("status")},
                            source=FLAG)
        ok = await cons.delete_elimination(e["id"])
        if ok:
            await audit(ACTOR, "ic_elimination_deleted", "ic_elimination", e["id"],
                        {"reason": REASON, "name": e.get("name"), "pair_id": pid, "journals_deleted": je_nums},
                        reason=REASON + (f"; jurnal transaksi yatim ikut dihapus: {', '.join(je_nums)}" if je_nums else ""),
                        scope_entity_id=e.get("entity_from") or "", source=FLAG)
        done.append({"elim": e, "journals": p["journals"], "elim_deleted": ok})
        print(f"  ✓ {e.get('name')}: entri {'dihapus' if ok else 'TIDAK ditemukan'}"
              + (f"; jurnal dihapus {', '.join(je_nums)}" if je_nums else ""))
    after = await _metrics()
    _print_metrics("sesudah", after)
    left = {p["stale"]["id"] for p in todo} & {s["id"] for s in await stale_g6_eliminations()}
    je_left = await db.journal_entries.count_documents(
        {"id": {"$in": [j["id"] for p in todo for j in p["journals"]]}})
    skipped = [{"id": p["elim"]["id"], "name": p["elim"].get("name"), "pair_id": p["stale"]["pair_id"],
                "reasons": p["skip"]} for p in plan if p["skip"]]
    await db.migrations.update_one({"id": FLAG}, {
        "$set": {"applied_at": now_iso()},
        "$push": {"runs": {"at": now_iso(), "db": ARGS.db, "actor": ACTOR, "reason": REASON,
                           "deleted": [{"elimination": d["elim"], "journals": d["journals"],
                                        "elim_deleted": d["elim_deleted"]} for d in done],
                           "skipped": skipped, "before": before, "after": after}}},
        upsert=True)
    bad_tb = [k for k, t in after["trial_balance"].items() if not t["balanced"]]
    print(f"Verifikasi: entri target tersisa {len(left)} · jurnal target tersisa {je_left} · neraca saldo tidak "
          f"seimbang {bad_tb or 0} · konsolidasi seimbang={after['consolidated_balanced']} · basi tersisa "
          f"{after['eliminations_stale_count']} (dilewati {len(skipped)})")
    await asyncio.sleep(0.5)   # biarkan efek samping audit (cek giliran) selesai sebelum loop ditutup
    return 1 if left or je_left or bad_tb or (before["consolidated_balanced"] and not after["consolidated_balanced"]) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
