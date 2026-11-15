#!/usr/bin/env python3
"""CR-T3 (RISIKO unit) — daftar pelanggan yang hasil gerbang kreditnya BERBEDA antara aturan lama dan mesin baru.

Aturan lama (`customer_service.evaluate_credit_gate`, dihapus di CR-T3 (b) — salinan beku di `_lama`): piutang dijumlah
LINTAS PT, plafon & hari blokir dari profil PT PEMILIK data pelanggan, titipan dan giro tidak dihitung. Mesin baru
(`services/credit_gate.evaluate`, titik `pesanan_dibuat`): angka per (pelanggan, PT pesanan) — K-29, eksposur K-31
(pesanan belum dikirim + giro belum cair − titipan). Dinilai untuk pesanan baru bernilai 0 (status hari ini).

BACA-SAJA: saldo dihitung dari dokumen (`customer_balance_service.compute`, tanpa menulis `customer_balances`), profil dari
`credit_profile_service.effective`. Menjalankannya pada DATA NYATA = keputusan pemilik (`00_ATURAN_EKSEKUSI.md` §6 H3).

    python scripts/crt3_beda_gerbang_kredit.py                 # semua PT
    python scripts/crt3_beda_gerbang_kredit.py --entity ent_x  # satu PT
    ... --json                                                 # keluaran JSON
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:  # noqa: BLE001
    pass

SETARA = {"blocked": ("tahan", "tolak"), "warning": ("peringatan",), "ok": ("lolos",)}


async def _saldo(customer_id: str, entity_id: str) -> Dict[str, Any]:
    from services import customer_balance_service as cbs
    return cbs.with_days(await cbs.compute(customer_id, entity_id)) or {}


async def _lama(customer: Dict[str, Any], saldo_pt: Dict[str, Dict[str, Any]]) -> str:
    """Salinan beku aturan lama, nilai pesanan 0: blocked bila status blocked atau piutang > plafon; warning bila status
    warning atau ada lewat tempo; ok selain itu. Piutang = Σ semua PT tanpa bagian termin tunai (CR-T2 b)."""
    from core_utils import from_cents, to_cents
    from services import credit_profile_service as cps
    ar = sum(to_cents(s.get("ar_delivered") or 0) - to_cents(s.get("cash_term_amount") or 0)
             + to_cents(s.get("open_orders_amount") or 0) - to_cents(s.get("cash_term_open_amount") or 0)
             for s in saldo_pt.values())
    lewat = sum(to_cents(s.get("overdue_amount") or 0) for s in saldo_pt.values())
    hari = max([int(s.get("days_overdue") or 0) for s in saldo_pt.values()] + [0])
    eff = await cps.effective(customer["id"], customer.get("entity_id") or "", customer=customer)
    status = cps.status_from(eff, from_cents(ar), hari)
    limit = float(eff.get("credit_limit") or 0)
    if status == "blocked" or (limit > 0 and from_cents(ar) > limit):
        return "blocked"
    return "warning" if status == "warning" or lewat > 0 else "ok"


async def bandingkan(entity_id: Optional[str] = None) -> Dict[str, Any]:
    """→ `{checked, different: [{customer_id, customer_name, entity_id, lama, baru, alasan, eksposur, sebab}]}`."""
    from db import db
    from services import credit_gate as cg
    from services import customer_balance_service as cbs
    pasangan = await cbs._semua_pasangan(None)   # noqa: SLF001 — pasangan berpiutang/berpesanan/bertitipan
    per_cust: Dict[str, List[str]] = {}
    for cid, eid in pasangan:
        per_cust.setdefault(cid, []).append(eid)
    beda: List[Dict[str, Any]] = []
    n = 0
    for cid, ents in sorted(per_cust.items()):
        cust = await db.customers.find_one({"id": cid}, {"_id": 0})
        if not cust:
            continue
        saldo = {e: await _saldo(cid, e) for e in ents}
        lama = await _lama(cust, saldo)
        for eid in ents:
            if entity_id and eid != entity_id:
                continue
            n += 1
            g = await cg.evaluate(customer_id=cid, entity_id=eid, checkpoint=cg.PESANAN_DIBUAT, order_amount=0,
                                  saldo=saldo[eid])
            baru = g.get("raw_result") or cg.LOLOS
            if baru in SETARA[lama]:
                continue
            sebab = []
            if len(ents) > 1:
                sebab.append("piutang kini per PT (K-29)")
            if (g.get("exposure") or {}).get("deposit"):
                sebab.append("titipan mengurangi eksposur (K-31)")
            if (g.get("exposure") or {}).get("giro_outstanding"):
                sebab.append("giro belum cair ikut eksposur (K-31)")
            if (cust.get("entity_id") or "") != eid:
                sebab.append("plafon PT pesanan, bukan PT pemilik data pelanggan")
            beda.append({"customer_id": cid, "customer_name": cust.get("name", ""), "entity_id": eid, "lama": lama,
                         "baru": baru, "alasan": [r["message"] for r in g.get("reasons") or []],
                         "eksposur": (g.get("exposure") or {}).get("total"), "sebab": sebab or ["lain-lain"]})
    return {"checked": n, "different": beda}


async def _main(argv: List[str]) -> int:
    ent = argv[argv.index("--entity") + 1] if "--entity" in argv else None
    out = await bandingkan(ent)
    if "--json" in argv:
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0
    print(f"Pasangan (pelanggan, PT) diperiksa: {out['checked']} · berbeda: {len(out['different'])}")
    for d in out["different"]:
        print(f"- {d['customer_name']} ({d['customer_id']}) · {d['entity_id']}: lama {d['lama']} → baru {d['baru']} · "
              f"eksposur {d['eksposur']} · {'; '.join(d['sebab'])}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
