#!/usr/bin/env python3
"""Pembersihan data uji lanjutan G1-33 (fase 4 · R9 lanjutan) — sisa jurnal & saldo antar-PT yatim.

Lanjutan `fix_data_2026_10_26_eliminasi_basi.py`. Izin pemilik 26 Okt ("ya setuju semua usulan", HANYA DB uji
`kn_test_trial`; DB lain ditolak skrip):

  A. KSC/IC-00052 (pair `icp_cf15ad02f55b`, sudah lunas): dokumen transaksi DAN dokumen pelunasannya (CST/ICS-00003,
     `ics_6413bf49aa39`) sudah dihapus uji, tetapi jurnalnya tertinggal. Jurnal pelunasan yatim + jurnal transaksi
     yatim pair itu + entri eliminasinya dihapus BERSAMA, sehingga pair itu bersih tanpa melahirkan saldo IC yatim
     baru (syarat: dokumen pelunasan & transaksi memang tidak ada, IC-AR/IC-AP bersih gabungan jurnalnya = 0).
     KSC/IC-00039 (`icp_654eabb23a1e`) DIBIARKAN — masih dirujuk pelunasan hidup KANDA/ICS-00002 (keputusan pemilik).
  B. 4 pasang jurnal retur antar-PT yatim (`source_type = interco_return`; dokumen `interco_returns`-nya sudah tidak
     ada): KSC/CST ICR-00010, -00014, -00015, -00023 @ Rp 13.986 → dihapus. Himpunan jurnal yatim yang ditemukan
     WAJIB sama dengan 8 nomor yang diizinkan; kalau tidak, bagian ini berhenti (dilaporkan, tidak ditulis).
  C. Cache saldo `interco_accounts` yang menyimpang dari Σ dokumen terbuka (INV-IC-04; KSC↔CST Rp 22.200 dari dokumen
     yang sudah dihapus) dihitung ulang lewat fungsi resmi `interco_service._update_account_balance(penjual, pembeli)`.

Syarat aman untuk SETIAP jurnal yang dihapus: posted, belum dibalik/dirujuk jurnal pembalik, tidak di periode tertutup,
tidak dirujuk dokumen lain (pindai teks semua koleksi kecuali riwayat & objek yang sedang dibersihkan). Jurnal dihapus
per id (dokumen lengkapnya disimpan di `migrations`) + audit `journal_entry_deleted`; entri eliminasi lewat
`consolidation_service.delete_elimination` + audit `ic_elimination_deleted`. Sebelum/sesudah (ringkasan konsolidasi,
neraca saldo per PT, IC bersih, baris `interco_accounts`) dicatat di `migrations` (`id = fix_data_2026_10_26_ic_yatim`).
Idempoten: bagian yang sudah bersih dilewati.

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_10_26_ic_yatim.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_10_26_ic_yatim.py --db kn_test_trial --apply
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
from services import interco_service as ics  # noqa: E402
from services.consolidation_stale_service import stale_g6_eliminations  # noqa: E402
from services.gl_service import ACC_IC_AP, ACC_IC_AR  # noqa: E402

FLAG = "fix_data_2026_10_26_ic_yatim"
ACTOR = "Sistem (pembersihan data uji)"
REASON = "Residu uji — dokumen antar-PT sumbernya sudah dihapus"
PAIR_A = "icp_cf15ad02f55b"            # KSC/IC-00052
SETTLEMENT_A = "ics_6413bf49aa39"      # CST/ICS-00003 (dokumen sudah terhapus)
PAIR_KEEP = "icp_654eabb23a1e"         # KSC/IC-00039 — dibiarkan (pelunasan hidup KANDA/ICS-00002)
RETURN_JES = {"KSC/JE-00136", "CST/JE-00055", "KSC/JE-00138", "CST/JE-00058",
              "KSC/JE-00139", "CST/JE-00059", "KSC/JE-00892", "CST/JE-00088"}
RETURN_AMOUNT = 13986.0
_REF_IGNORE = {"audit_logs", "migrations", "intercompany_eliminations", "journal_entries", "notifications"}


def _rp(x: float) -> str:
    return f"Rp {x:,.0f}".replace(",", ".")


def _net(js: list, code: str, credit_normal: bool = False) -> float:
    v = sum(float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
            for j in js for ln in j.get("lines") or [] if str(ln.get("account_code")) == code)
    return round(-v if credit_normal else v, 2)


def _fmt(j: dict) -> str:
    return (f"{j.get('number')} ({j.get('entity_id')}, {j.get('source_type')} {j.get('source_id')}, {j.get('status')}): "
            + ", ".join(f"{ln['account_code']} D{ln.get('debit') or 0:g}/K{ln.get('credit') or 0:g}"
                        for ln in j.get("lines") or []))


async def _jes(source_type: str, base: str) -> list:
    return await db.journal_entries.find(
        {"source_type": source_type, "source_id": {"$regex": f"^{re.escape(base)}(:|$)"}},
        {"_id": 0}).sort("number", 1).to_list(None)


async def _scan_refs(needles: list) -> dict:
    needles = [n for n in needles if n]
    if not needles:
        return {}
    pat = re.compile("|".join(re.escape(n) for n in needles))
    hits: dict = {}
    for coll in sorted(await db.list_collection_names()):
        if coll in _REF_IGNORE or coll.startswith("system."):
            continue
        async for d in db[coll].find({}):
            for m in set(pat.findall(json.dumps(d, default=str, ensure_ascii=False))):
                hits.setdefault(m, []).append(f"{coll}:{d.get('number') or d.get('code') or d.get('id') or d.get('_id')}")
    return hits


async def _je_doubts(js: list, refs: dict) -> list:
    out = []
    for j in js:
        r = refs.get(j["id"], []) + refs.get(j.get("number") or "\0", [])
        if r:
            out.append(f"{j.get('number')} dirujuk dokumen lain: {', '.join(r[:4])}")
        if j.get("status") != "posted":
            out.append(f"{j.get('number')} berstatus {j.get('status')}")
        if j.get("reversed_by_entry_id") or j.get("backdated_in_unlock") or j.get("voided_in_unlock"):
            out.append(f"{j.get('number')} sudah dibalik/berjejak buka-periode")
        if await db.journal_entries.count_documents({"$or": [{"source_id": j["id"]}, {"ref.reverses_entry_id": j["id"]}]}):
            out.append(f"{j.get('number')} dirujuk jurnal pembalik")
        st = await closing_service.status_for_date(j.get("date") or "", j.get("entity_id") or "")
        if st.get("closed"):
            out.append(f"{j.get('number')} di periode tertutup {st.get('period_label')}")
        if abs(float(j.get("total_debit") or 0) - float(j.get("total_credit") or 0)) > 0.01:
            out.append(f"{j.get('number')} tidak seimbang")
    return out


async def _plan_a() -> dict:
    elims = await db.intercompany_eliminations.find({"source_g6_pair_id": PAIR_A}, {"_id": 0}).to_list(None)
    pj = await _jes("interco_transaction", PAIR_A)
    sj = await _jes("interco_settlement", SETTLEMENT_A)
    plan = {"elims": elims, "pair_journals": pj, "settlement_journals": sj, "doubts": [], "done": False}
    if not (elims or pj or sj):
        plan["done"] = True
        return plan
    d = plan["doubts"]
    if await db.interco_transactions.count_documents({"pair_id": PAIR_A}):
        d.append("dokumen transaksi antar-PT pair ini masih ada")
    if await db.interco_settlements.count_documents({"$or": [{"id": SETTLEMENT_A}, {"applied.pair_id": PAIR_A},
                                                             {"netted_against.pair_id": PAIR_A}]}):
        d.append("dokumen pelunasan masih ada / ada pelunasan hidup yang menaut pair ini")
    stale_ids = {s["id"] for s in await stale_g6_eliminations()}
    if any(e["id"] not in stale_ids for e in elims):
        d.append("entri eliminasi pair ini tidak terdeteksi basi")
    seller = [j for j in pj if str(j.get("source_id", "")).endswith(":seller")]
    buyer = [j for j in pj if str(j.get("source_id", "")).endswith(":buyer")]
    payee = [j for j in sj if str(j.get("source_id", "")).endswith(":payee")]
    payer = [j for j in sj if str(j.get("source_id", "")).endswith(":payer")]
    if not (len(seller) == len(buyer) == len(payee) == len(payer) == 1):
        d.append(f"bentuk jurnal tak terduga (seller {len(seller)}, buyer {len(buyer)}, payee {len(payee)}, "
                 f"payer {len(payer)})")
    else:
        if payee[0].get("entity_id") != seller[0].get("entity_id") or payer[0].get("entity_id") != buyer[0].get("entity_id"):
            d.append("PT penerima/pembayar pelunasan ≠ PT penjual/pembeli pair")
        if abs(_net(pj, ACC_IC_AR) - (-_net(sj, ACC_IC_AR))) > 0.01:
            d.append(f"nominal pelunasan {_rp(-_net(sj, ACC_IC_AR))} ≠ IC-AR transaksi {_rp(_net(pj, ACC_IC_AR))}")
    allj = pj + sj
    if abs(_net(allj, ACC_IC_AR)) > 0.01 or abs(_net(allj, ACC_IC_AP)) > 0.01:
        d.append(f"IC bersih gabungan jurnal ≠ 0 (IC-AR {_rp(_net(allj, ACC_IC_AR))}, IC-AP "
                 f"{_rp(_net(allj, ACC_IC_AP, True))}) — menghapusnya mengubah saldo IC lain")
    refs = await _scan_refs([PAIR_A, SETTLEMENT_A] + [j["id"] for j in allj] + [j.get("number") for j in allj])
    for k in (PAIR_A, SETTLEMENT_A):
        if refs.get(k):
            d.append(f"{k} masih dirujuk: {', '.join(refs[k][:6])}")
    d += await _je_doubts(allj, refs)
    return plan


async def _plan_b() -> dict:
    groups: dict = {}
    async for j in db.journal_entries.find({"source_type": "interco_return"}, {"_id": 0}):
        groups.setdefault(str(j.get("source_id", "")).split(":", 1)[0], []).append(j)
    orphan = {}
    for base, js in groups.items():
        if not await db.interco_returns.count_documents({"$or": [{"id": base}, {"pair_id": base}, {"return_pair_id": base}]}):
            orphan[base] = sorted(js, key=lambda x: x.get("number") or "")
    nums = {j.get("number") for js in orphan.values() for j in js}
    plan = {"groups": orphan, "doubts": [], "done": not orphan}
    if not orphan:
        return plan
    d = plan["doubts"]
    if nums != RETURN_JES:
        d.append(f"jurnal retur yatim yang ditemukan ≠ yang diizinkan (lebih: {sorted(nums - RETURN_JES)}, "
                 f"kurang: {sorted(RETURN_JES - nums)}) — beda dari deskripsi, bagian ini BERHENTI")
    for base, js in orphan.items():
        if await db.journal_entries.count_documents(
                {"source_id": {"$regex": f"^{re.escape(base)}(:|$)"}, "source_type": {"$ne": "interco_return"}}):
            d.append(f"{base}: ada jurnal jenis lain dengan sumber yang sama")
        sel = [j for j in js if str(j.get("source_id")).endswith(":seller")]
        buy = [j for j in js if str(j.get("source_id")).endswith(":buyer")]
        if len(sel) != 1 or len(buy) != 1:
            d.append(f"{base}: bentuk pasangan tak terduga ({len(sel)} penjual, {len(buy)} pembeli)")
            continue
        ar, ap = -_net(sel, ACC_IC_AR), _net(buy, ACC_IC_AP)
        if abs(ar - RETURN_AMOUNT) > 0.01 or abs(ap - RETURN_AMOUNT) > 0.01:
            d.append(f"{base}: nominal IC {_rp(ar)} / {_rp(ap)} ≠ {_rp(RETURN_AMOUNT)}")
    allj = [j for js in orphan.values() for j in js]
    refs = await _scan_refs(list(orphan) + [j["id"] for j in allj] + [j.get("number") for j in allj])
    for base in orphan:
        if refs.get(base):
            d.append(f"{base} masih dirujuk: {', '.join(refs[base][:6])}")
    d += await _je_doubts(allj, refs)
    return plan


async def _plan_c() -> dict:
    live = await ics._live_pair_outstanding()
    rows = await db.interco_accounts.find({}, {"_id": 0}).to_list(None)
    dirs = {}
    for r in rows:
        pk = r.get("pair_key") or ""
        if ">" not in pk:
            continue
        sel, buy = pk.split(">", 1)
        want = round(float((live.get((sel, buy)) or {}).get("outstanding") or 0), 2)
        if abs(want - float(r.get("outstanding") or 0)) > 0.01:
            dirs.setdefault((sel, buy), []).append({"id": r["id"], "role": r.get("role"),
                                                    "outstanding": r.get("outstanding"), "expected": want,
                                                    "open_count": r.get("open_count")})
    for (sel, buy) in live:
        if not any(r.get("pair_key") == f"{sel}>{buy}" for r in rows):
            dirs.setdefault((sel, buy), []).append({"id": "(baris hilang)", "expected": live[(sel, buy)]["outstanding"]})
    return {"directions": dirs, "rows_before": rows, "done": not dirs}


async def _metrics() -> dict:
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
        tb[a["_id"]] = {"debit": round(a["d"], 2), "credit": round(a["c"], 2), "balanced": abs(a["d"] - a["c"]) < 0.01,
                        "ic_ar_net": round(a["ar"], 2), "ic_ap_net": round(a["ap"], 2)}
    return {"as_of": summ["as_of"], "year": summ["year"], "eliminations_count": summ["eliminations_count"],
            "eliminations_stale_count": summ["eliminations_stale_count"],
            "eliminations_stale": [s["name"] for s in summ["eliminations_stale"]],
            "elimination": summ["elimination"], "consolidated": summ["consolidated"],
            "consolidated_balanced": summ["balanced"], "trial_balance": tb,
            "journals_posted": await db.journal_entries.count_documents({"status": "posted"}),
            "interco_accounts": {r["id"]: r.get("outstanding") async for r in db.interco_accounts.find(
                {}, {"_id": 0, "id": 1, "outstanding": 1})}}


def _print_metrics(tag: str, m: dict) -> None:
    c, e = m["consolidated"], m["elimination"]
    print(f"[{tag}] eliminasi {m['eliminations_count']} entri · basi {m['eliminations_stale_count']} "
          f"{m['eliminations_stale']} · jurnal posted {m['journals_posted']}")
    print(f"[{tag}] eliminasi: pendapatan {_rp(e['revenue'])}, aset {_rp(e['assets'])}, liabilitas {_rp(e['liabilities'])}")
    print(f"[{tag}] konsolidasi {m['year']} per {m['as_of']}: pendapatan {_rp(c['revenue'])}, laba bersih "
          f"{_rp(c['net_income'])}, aset {_rp(c['assets'])} = liabilitas {_rp(c['liabilities'])} + ekuitas "
          f"{_rp(c['equity'])} → seimbang={m['consolidated_balanced']}")
    for eid, t in sorted(m["trial_balance"].items()):
        print(f"[{tag}] neraca saldo {eid}: D {_rp(t['debit'])} = K {_rp(t['credit'])} → seimbang={t['balanced']}"
              f" · IC-AR bersih {_rp(t['ic_ar_net'])} · IC-AP bersih {_rp(t['ic_ap_net'])}")
    print(f"[{tag}] interco_accounts outstanding: {m['interco_accounts']}")


async def _delete_je(j: dict, why: str) -> bool:
    r = await db.journal_entries.delete_one({"id": j["id"], "source_type": j["source_type"], "source_id": j["source_id"]})
    if r.deleted_count:
        await audit(ACTOR, "journal_entry_deleted", "journal_entry", j["id"],
                    {"number": j.get("number"), "source_id": j.get("source_id"), "deleted": True},
                    reason=f"{REASON} — {why}", scope_entity_id=j.get("entity_id") or "",
                    before={"number": j.get("number"), "total_debit": j.get("total_debit"),
                            "total_credit": j.get("total_credit"), "status": j.get("status")}, source=FLAG)
    return bool(r.deleted_count)


async def main() -> int:
    mode = "APPLY" if ARGS.apply else "DRY-RUN"
    print(f"== {FLAG} · DB {ARGS.db} · {mode}")
    a, b, c = await _plan_a(), await _plan_b(), await _plan_c()
    print("A · KSC/IC-00052 (pair + pelunasan yatim):", "sudah bersih" if a["done"] else
          ("BERHENTI (ragu)" if a["doubts"] else "hapus"))
    for e in a["elims"]:
        print(f"    entri {e.get('name')} [{e['id']}]")
    for j in a["pair_journals"] + a["settlement_journals"]:
        print(f"    jurnal {_fmt(j)}")
    for x in a["doubts"]:
        print(f"    ragu: {x}")
    print(f"    (KSC/IC-00039 {PAIR_KEEP} dibiarkan: pelunasan hidup KANDA/ICS-00002)")
    print("B · jurnal retur antar-PT yatim:", "sudah bersih" if b["done"] else
          ("BERHENTI (ragu)" if b["doubts"] else f"hapus {sum(len(v) for v in b['groups'].values())} jurnal"))
    for base, js in b["groups"].items():
        for j in js:
            print(f"    {base}: {_fmt(j)} · {j.get('description')}")
    for x in b["doubts"]:
        print(f"    ragu: {x}")
    print("C · cache interco_accounts:", "sudah cocok" if c["done"] else
          f"hitung ulang {len(c['directions'])} arah dagang")
    for (sel, buy), rows in c["directions"].items():
        for r in rows:
            print(f"    {sel}>{buy} {r['id']} ({r.get('role')}): {r.get('outstanding')} → {r['expected']}")
    before = await _metrics()
    _print_metrics("sebelum", before)
    if not ARGS.apply:
        print("DRY-RUN — tidak ada yang ditulis. Ulangi dengan --apply untuk menerapkan.")
        return 0
    run = {"at": now_iso(), "db": ARGS.db, "actor": ACTOR, "reason": REASON, "before": before,
           "A": {"status": "done" if a["done"] else ("skipped" if a["doubts"] else "applied"), "doubts": a["doubts"]},
           "B": {"status": "done" if b["done"] else ("skipped" if b["doubts"] else "applied"), "doubts": b["doubts"]},
           "C": {"status": "done" if c["done"] else "applied"}}
    if not a["done"] and not a["doubts"]:
        why = "KSC/IC-00052: jurnal transaksi & pelunasan yatim dihapus bersama entri eliminasinya"
        dels = [j for j in a["pair_journals"] + a["settlement_journals"] if await _delete_je(j, why)]
        nums = [j.get("number") for j in dels]
        for e in a["elims"]:
            if await cons.delete_elimination(e["id"]):
                await audit(ACTOR, "ic_elimination_deleted", "ic_elimination", e["id"],
                            {"reason": REASON, "name": e.get("name"), "pair_id": PAIR_A, "journals_deleted": nums},
                            reason=f"{REASON}; jurnal transaksi & pelunasan yatim ikut dihapus: {', '.join(nums)}",
                            scope_entity_id=e.get("entity_from") or "", source=FLAG)
        run["A"].update({"eliminations": a["elims"], "journals": dels})
        print(f"  ✓ A: entri {len(a['elims'])} + jurnal dihapus {', '.join(nums)}")
    if not b["done"] and not b["doubts"]:
        dels = []
        for base, js in b["groups"].items():
            for j in js:
                if await _delete_je(j, f"jurnal retur antar-PT yatim ({j.get('description')}; dokumen returnya sudah dihapus)"):
                    dels.append(j)
        run["B"]["journals"] = dels
        print(f"  ✓ B: jurnal retur dihapus {', '.join(j.get('number') for j in dels)}")
    if not c["done"]:
        for (sel, buy) in c["directions"]:
            await ics._update_account_balance(sel, buy)
        run["C"].update({"directions": [f"{s}>{t}" for s, t in c["directions"]], "rows_before": c["rows_before"],
                         "rows_after": await db.interco_accounts.find({}, {"_id": 0}).to_list(None)})
        print(f"  ✓ C: interco_accounts dihitung ulang untuk {[f'{s}>{t}' for s, t in c['directions']]}")
    after = await _metrics()
    _print_metrics("sesudah", after)
    run["after"] = after
    await db.migrations.update_one({"id": FLAG}, {"$set": {"applied_at": now_iso()}, "$push": {"runs": run}}, upsert=True)
    a2, b2, c2 = await _plan_a(), await _plan_b(), await _plan_c()
    bad_tb = [k for k, t in after["trial_balance"].items() if not t["balanced"]]
    print(f"Verifikasi: A bersih={a2['done']} · B bersih={b2['done']} · C cocok={c2['done']} · neraca saldo tidak "
          f"seimbang {bad_tb or 0} · konsolidasi seimbang={after['consolidated_balanced']} · basi tersisa "
          f"{after['eliminations_stale_count']} {after['eliminations_stale']}")
    await asyncio.sleep(0.5)   # biarkan efek samping audit (cek giliran) selesai sebelum loop ditutup
    ok = (a2["done"] or bool(a["doubts"])) and (b2["done"] or bool(b["doubts"])) and c2["done"] and not bad_tb \
        and after["consolidated_balanced"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
