#!/usr/bin/env python3
"""CR-T2 — bangun jadwal tagihan (`payment_plans` `origin: "term"`) untuk pesanan hidup yang SUDAH ada, isi `line_id`
baris rencana lama, lalu bangun ulang saldo piutang tersimpan (`customer_balances`). Idempoten.

Mode:
    python scripts/build_billing_schedule.py              # = --dry-run (BACA-SAJA, bawaan)
    python scripts/build_billing_schedule.py --dry-run    # rencana tulisan + daftar pelanggan yang status kreditnya
                                                          # berubah (rumus lama: jatuh tempo per surat jalan PK-41,
                                                          # tanpa uang muka & rencana cicilan → rumus baru jadwal)
    python scripts/build_billing_schedule.py --apply      # tulis (kait yang sama dengan alur dokumen: `sync_order`)
    ... --json                                            # keluaran JSON

Dijalankan di container backend terhadap database `backend/.env`. Menjalankan `--apply` (dan juga `--dry-run`) pada DATA
NYATA = keputusan pemilik (`docs/blueprint/00_ATURAN_EKSEKUSI.md` §6 H3); daftar pelanggan yang status kreditnya berubah
diserahkan ke pemilik SEBELUM pembaca dialihkan ke PT nyata (RISIKO spesifikasi CR-T2). Data kembar jadwal hidup (indeks
`uq_plan_live_doc` gagal dibuat) = titik henti H6: skrip tidak menggabung/menghapus apa pun.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:  # noqa: BLE001
    pass


async def _status(customer: Dict[str, Any], entity_id: str, ar: float, hari: int) -> str:
    from services import credit_profile_service as cps
    eff = await cps.effective(customer["id"], entity_id, customer=customer)
    return cps.status_from(eff, ar, hari)


async def bandingkan(orders: List[Dict[str, Any]], customer: Dict[str, Any], hari_ini: str) -> Dict[str, Any]:
    """(lama, baru) lewat tempo & telat terlama satu pelanggan di satu PT. LAMA = baris per surat jalan dari jurnal
    (PK-41: tanpa baris uang muka, tanpa rencana cicilan); BARU = jadwal tagihan (`lines_for_orders`)."""
    from core_utils import from_cents, to_cents
    from services import billing_schedule_service as bss
    from services import report_basis as rb
    piutang = [o for o in orders if rb.pesanan_piutang(o)]
    baru = await bss.lines_for_orders(piutang, {customer["id"]: customer}, per=hari_ini)
    jurnal = await rb._jurnal_pendapatan([o["id"] for o in piutang])   # noqa: SLF001
    peta = await rb.peta_termin(piutang)
    hasil = {"lama": [0, 0], "baru": [0, 0]}
    kode: Dict[str, set] = {}
    for o in piutang:
        termin = {**await bss.termin_pesanan(o, customer, peta), "dp_percent": 0.0}
        rows = await bss.bangun_baris({**o, "extra_billing_lines": []}, termin, jurnal.get(o["id"], []), kode)
        rows = [{**r, "_amt": to_cents(float(r["amount"])), "seq": i + 1} for i, r in enumerate(rows)]
        bss._alokasi(rows, o, hari_ini)   # noqa: SLF001 — aturan alokasi yang sama
        for r in rows:
            sisa = r["_amt"] - r["_paid"]
            if sisa > 0 and r["due_date"] < hari_ini:
                hasil["lama"][0] += sisa
                hasil["lama"][1] = max(hasil["lama"][1], rb.hari_antara(r["due_date"], hari_ini))
        for r in (baru.get(o["id"]) or {}).get("rows") or []:
            if r["outstanding"] > rb.EPS and r["due_date"] and r["due_date"] < hari_ini:
                hasil["baru"][0] += to_cents(r["outstanding"])
                hasil["baru"][1] = max(hasil["baru"][1], r["days_late"])
    return {k: (from_cents(v[0]), v[1]) for k, v in hasil.items()}


async def jalankan(apply: bool = False) -> Dict[str, Any]:
    from core_utils import from_cents, to_cents
    from db import db
    from services import billing_schedule_service as bss
    from services import customer_balance_service as cbs
    from services import payment_plan_service as plans
    from services.book_date import tanggal_buku
    from services.customer_service import DEAD_STATUSES, _order_grand_total, _order_paid
    hari_ini = tanggal_buku()
    out: Dict[str, Any] = {"mode": "apply" if apply else "dry-run", "as_of": hari_ini, "orders": 0,
                           "schedules_created": 0, "lines_added": 0, "manual_line_ids": 0, "manual_plans": 0,
                           "status_changes": [], "balances": None}
    # 1. baris rencana lama tanpa `line_id` / tanpa `origin`
    async for p in db[plans.COLL].find({"status": {"$ne": "void"}, "origin": {"$ne": bss.ORIGIN_TERM}}, {"_id": 0}):
        kurang = [ln for ln in p.get("lines") or [] if not ln.get("line_id")]
        if not kurang and p.get("origin"):
            continue
        out["manual_plans"] += 1
        out["manual_line_ids"] += len(kurang)
        if apply:
            lines = [dict(ln) for ln in p.get("lines") or []]
            plans._isi_line_id(lines)   # noqa: SLF001
            await db[plans.COLL].update_one({"id": p["id"], "rev": p.get("rev")}, {"$set": {
                "lines": lines, "origin": p.get("origin") or bss.ORIGIN_MANUAL, "rev": int(p.get("rev") or 0) + 1}})
    # 2. jadwal term pesanan hidup
    q = {"status": {"$nin": sorted(DEAD_STATUSES)}, "order_type": {"$ne": "sample"}}
    per_pasangan: Dict[tuple, List[Dict[str, Any]]] = {}
    async for o in db.sales_orders.find(q, {"_id": 0}):
        out["orders"] += 1
        if to_cents(_order_grand_total(o) - _order_paid(o)) > 0:
            per_pasangan.setdefault((o.get("customer_id") or "", o.get("entity_id") or ""), []).append(o)
        plan = await plans.get_active("sales_order", o["id"])
        if plan and not bss.is_term(plan):
            continue
        cust = await db.customers.find_one({"id": o.get("customer_id")}, {"_id": 0, "payment_profile": 1}) or {}
        termin = await bss.termin_pesanan(o, cust)
        jurnal = (await bss.rb._jurnal_pendapatan([o["id"]])).get(o["id"], [])   # noqa: SLF001
        mau = await bss.bangun_baris(o, termin, jurnal)
        ada = {bss._kunci(x) for x in (plan or {}).get("lines") or []}   # noqa: SLF001
        tambah = [m for m in mau if bss._kunci(m) not in ada]   # noqa: SLF001
        if not plan and (mau or bss.sudah_konfirmasi(o)):
            out["schedules_created"] += 1
        out["lines_added"] += len(tambah)
        if apply and (tambah or not plan):
            await bss.sync_order(o["id"])
    # 3. pelanggan yang status kreditnya berubah (rumus lama → jadwal)
    for (cid, eid), orders in sorted(per_pasangan.items()):
        cust = await db.customers.find_one({"id": cid}, {"_id": 0}) or {"id": cid}
        cmp_ = await bandingkan(orders, cust, hari_ini)
        ar = from_cents(sum(to_cents(max(0.0, _order_grand_total(o) - _order_paid(o))) for o in orders
                            if bss.rb.pesanan_piutang(o)))
        lama = await _status(cust, eid, ar, cmp_["lama"][1])
        baru = await _status(cust, eid, ar, cmp_["baru"][1])
        if lama != baru:
            out["status_changes"].append({
                "customer_id": cid, "customer_name": cust.get("name", ""), "entity_id": eid, "status_lama": lama,
                "status_baru": baru, "lewat_tempo_lama": cmp_["lama"][0], "lewat_tempo_baru": cmp_["baru"][0],
                "telat_lama": cmp_["lama"][1], "telat_baru": cmp_["baru"][1]})
    # 4. saldo tersimpan
    if apply:
        res = await cbs.rebuild_all()
        out["balances"] = {k: res[k] for k in ("pairs", "changed", "seconds")}
    return out


async def main() -> int:
    apply = "--apply" in sys.argv
    if apply and "--dry-run" in sys.argv:
        print("Pilih salah satu: --dry-run atau --apply.")
        return 2
    out = await jalankan(apply=apply)
    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    print(f"Jadwal tagihan ({out['mode']}, per {out['as_of']}): {out['orders']} pesanan hidup · jadwal baru "
          f"{out['schedules_created']} · baris baru {out['lines_added']} · rencana lama diisi line_id "
          f"{out['manual_plans']} ({out['manual_line_ids']} baris)")
    if out["balances"]:
        b = out["balances"]
        print(f"Saldo piutang tersimpan dibangun ulang: {b['pairs']} pasangan, {b['changed']} berubah ({b['seconds']} dtk)")
    print(f"{len(out['status_changes'])} pelanggan berubah status kredit (rumus lama → jadwal tagihan):")
    for r in out["status_changes"]:
        print(f"  {r['customer_name'] or r['customer_id']} [{r['entity_id']}]: {r['status_lama']} → {r['status_baru']}"
              f" · lewat tempo {r['lewat_tempo_lama']:,.0f} → {r['lewat_tempo_baru']:,.0f}"
              f" · telat {r['telat_lama']} → {r['telat_baru']} hari")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
