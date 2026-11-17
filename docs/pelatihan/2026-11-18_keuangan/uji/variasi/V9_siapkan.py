"""V9 (bukti klaim materi) — data TAMBAHAN untuk peserta yang dokumen dasarnya sudah terpakai, lewat endpoint resmi dan
pembantu yang sama dengan `backend/scripts/seed_pelatihan_keuangan_kn.py` (tidak mengubah skrip data latihan).

  cd backend && python ../docs/pelatihan/2026-11-18_keuangan/uji/variasi/V9_siapkan.py --peserta 88 --so 2
  cd backend && python ../docs/pelatihan/2026-11-18_keuangan/uji/variasi/V9_siapkan.py --peserta 89 --po 2

`--so N`  → N SO terkirim belum dibayar untuk pelanggan peserta (kartu `v9:so_1`, `v9:so_2`, …; sama dengan "SO untuk
            pelunasan penuh").
`--po Q`  → satu PO grey Q yard × Rp 14.000 untuk pemasok peserta, disetujui & DITERIMA gudang, BELUM ditagih (kartu
            `v9:po_terima`) — bahan uji 3-way match & No. faktur pemasok kembar di layar.
`--kunci K` → nama kartu PO (bawaan `v9:po_terima`; mis. `v9:po_terima_2` bila PO pertama sudah terpakai).
Aman dijalankan ulang: kunci yang sudah ada dilewati.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5] / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from scripts.demo_api import Api  # noqa: E402
from scripts.latih_keuangan.a_dasar import _so_terkirim  # noqa: E402
from scripts.latih_keuangan.konteks import KSC, LatihCtx, Peserta  # noqa: E402
from scripts.seed_demo_transaksi_kn import approve_po, days, receive_po  # noqa: E402

FLAG = "pelatihan_keuangan"


async def po_terima(lc: LatihCtx, p: Peserta, qty: float) -> dict:
    mgr = await lc.u("manager")
    grey, sup, wh = await lc.prod("DMO-GRY-WVN-001"), await lc.supplier_of(p), await lc.wh("WH-JKT")
    po = await mgr.post("/purchase-orders", {
        "supplier_id": sup["id"], "supplier_name": sup["name"], "warehouse_id": wh,
        "items": [{"product_id": grey["id"], "quantity": qty, "unit": "yard", "price": 14000, "expected_grade": "A"}],
        "entity_id": KSC, "tax_mode": "ppn", "expected_delivery_date": days(3),
        "notes": f"V9 latihan peserta {p.kode}: PO diterima belum ditagih"}, entity=KSC)
    po = await approve_po(lc, po, KSC)
    await receive_po(lc, po["id"], KSC, "warehouse")
    await lc.tag("purchase_orders", po["id"], p, "v9_po_terima")
    po = await db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    return {"po": po.get("po_number"), "po_id": po["id"], "qty": qty, "harga": 14000, "status": po.get("status"),
            "pemasok": sup["name"]}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--peserta", type=int, required=True)
    ap.add_argument("--so", type=int, default=0)
    ap.add_argument("--po", type=float, default=0)
    ap.add_argument("--kunci", default="v9:po_terima")
    a = ap.parse_args()
    cst = (await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}))["id"]
    api = Api()
    lc = LatihCtx(api, cst)
    p = Peserta(a.peserta)
    state = ((await db.migrations.find_one({"id": FLAG}, {"_id": 0}) or {}).get("peserta", {})).get(p.kode, {})
    todo = [(f"v9:so_{i}", lambda: _so_terkirim(lc, p, "v9_so", "woven")) for i in range(1, a.so + 1)]
    if a.po:
        todo.append((a.kunci, lambda: po_terima(lc, p, a.po)))
    try:
        for key, fn in todo:
            if key in state:
                print(f"   · {key} sudah ada: {json.dumps(state[key], ensure_ascii=False)}")
                continue
            res = await fn()
            await db.migrations.update_one({"id": FLAG}, {"$set": {f"peserta.{p.kode}.{key}": res, "updated_at": now_iso()}})
            print(f"   ✓ {key}: {json.dumps(res, ensure_ascii=False)}")
    finally:
        await asyncio.sleep(1)
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
