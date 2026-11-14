#!/usr/bin/env python3
"""PK-41 (RISIKO di spesifikasi) — daftar pelanggan yang status kreditnya BERUBAH karena umur piutang kini per surat jalan.

BACA-SAJA: tidak menulis apa pun. Untuk tiap pelanggan dibandingkan:
  * status LAMA — rumus sebelum PK-41: seluruh sisa pesanan jatuh tempo pada surat jalan PERTAMA + termin, hari telat
    `(sekarang − jatuh tempo).days` (jam UTC);
  * status BARU — `customer_service.compute_customer_credit` (baris tagihan terkirim per surat jalan, `report_basis`).
Ambang & plafon sama-sama dari `credit_profile_service.effective` (pengaturan PT + profil kredit pelanggan).

Pakai (di container backend, terhadap database yang dipilih `backend/.env`; menjalankannya pada data nyata = keputusan
pemilik, `docs/blueprint/00_ATURAN_EKSEKUSI.md` §6 H3):
    python scripts/pk41_status_kredit_berubah.py            # tabel pelanggan yang berubah
    python scripts/pk41_status_kredit_berubah.py --json     # keluaran JSON
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:  # noqa: BLE001
    pass

SJ_MATI = ("cancelled", "void", "voided")


async def _status_lama(customer, orders, cps, cs, rb) -> tuple:
    """Rumus sebelum PK-41 (disalin dari `customer_service.compute_customer_credit` + `due_context`/`order_due` lama)."""
    from db import db
    ids = [o["id"] for o in orders]
    first = {}
    if ids:
        async for r in db.shipments.aggregate([
                {"$match": {"order_id": {"$in": ids}, "status": {"$nin": list(SJ_MATI)}}},
                {"$group": {"_id": "$order_id", "first": {"$min": "$created_at"}}}]):
            dt = cs._parse_dt(r.get("first"))
            if dt:
                first[r["_id"]] = dt
    terms = await rb.peta_termin(orders)
    now = datetime.now(timezone.utc)
    ar = overdue = 0.0
    maks = 0
    for o in orders:
        if o.get("status") in cs.DEAD_STATUSES or o.get("payment_status") == "paid":
            continue
        sisa = max(cs._order_grand_total(o) - cs._order_paid(o), 0.0)
        if sisa <= 0.01 or cs.order_payment_method(o) in cs.NON_AR_METHODS:
            continue
        ar += sisa
        base = first.get(o["id"])
        if base is None:
            continue
        telat = (now - (base + timedelta(days=cs._term_days(customer, o, terms)))).days
        if telat > 0:
            overdue += sisa
            maks = max(maks, telat)
    eff = await cps.effective(customer["id"], customer.get("entity_id") or "", customer=customer)
    return cps.status_from(eff, ar, maks), round(overdue, 2), maks


async def main() -> int:
    from db import db
    from services import credit_profile_service as cps
    from services import customer_service as cs
    from services import report_basis as rb
    as_json = "--json" in sys.argv
    berubah = []
    async for c in db.customers.find({}, {"_id": 0}):
        orders = [o async for o in db.sales_orders.find(
            {"customer_id": c["id"], "status": {"$nin": sorted(cs.DEAD_STATUSES)}, "payment_status": {"$ne": "paid"}},
            {"_id": 0})]
        if not orders:
            continue
        lama, od_lama, hari_lama = await _status_lama(c, orders, cps, cs, rb)
        baru = await cs.compute_customer_credit(c)
        if lama != baru["status"]:
            berubah.append({"customer_id": c["id"], "customer_name": c.get("name", ""), "entity_id": c.get("entity_id"),
                            "status_lama": lama, "status_baru": baru["status"],
                            "lewat_tempo_lama": od_lama, "lewat_tempo_baru": baru["overdue_amount"],
                            "telat_lama": hari_lama, "telat_baru": baru["max_overdue_days"]})
    if as_json:
        print(json.dumps(berubah, ensure_ascii=False, indent=1))
    else:
        print(f"{len(berubah)} pelanggan berubah status kredit (lama → baru):")
        for r in berubah:
            print(f"  {r['customer_name'] or r['customer_id']} [{r['entity_id']}]: {r['status_lama']} → {r['status_baru']}"
                  f" · lewat tempo {r['lewat_tempo_lama']:,.0f} → {r['lewat_tempo_baru']:,.0f}"
                  f" · telat {r['telat_lama']} → {r['telat_baru']} hari")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
