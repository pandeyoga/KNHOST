"""PK-30 (IC-09) — LAPORAN baca-saja sisa jalur transfer antar-PT harga pokok yang lama. Tidak menulis apa pun.

    python scripts/blueprint/pk30_transfer_lama_lapor.py

Sejak PK-30 `POST /api/transfers/inter-company` selalu 410 dan transfer `inter_entity` tanpa dokumen antar-PT tidak bisa
disetujui (409 — hanya bisa ditolak/dibatalkan). Skrip ini mendaftar dua hal untuk pemilik (keputusan perbaikan data =
titik henti H3, `docs/blueprint/00_ATURAN_EKSEKUSI.md` §6; skrip ini sengaja TANPA mode tulis):

  1. Transfer lama `waiting_approval` tanpa `interco_pair_id`, tanpa `interco_return_pair_id`, dan bukan pindah roll
     retur (`origin_sales_return_id`) — harus DITOLAK petugas supaya rollnya kembali tersedia.
  2. Jurnal harga pokok `inter_company_transfer` yang sudah terbit (1-1250 di PT asal, 2-1250 di PT tujuan) per pasangan
     PT, dipisah menurut asal: "kasir lama" (transfer tanpa dokumen antar-PT) dan "pindah roll retur"
     (`return_service._finish_return_transfer`, sisa IC-09 yang belum punya unit). Saldo ini tidak tampil di layar
     Saldo Antar-PT.

Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`). Keluar 0.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

AKUN_PIUTANG, AKUN_UTANG = "1-1250", "2-1250"


def _rp(x: float) -> str:
    return f"Rp {x:,.0f}".replace(",", ".")


async def kumpulkan(db) -> Dict[str, Any]:
    """→ {"menunggu": [transfer lama waiting_approval], "jurnal": [ringkasan per (asal, PT asal, PT tujuan)]}."""
    menunggu: List[Dict[str, Any]] = []
    async for t in db.warehouse_transfers.find(
            {"transfer_kind": "inter_entity", "status": "waiting_approval"},
            {"_id": 0, "id": 1, "code": 1, "source_entity_id": 1, "dest_entity_id": 1, "created_at": 1,
             "requested_by": 1, "items": 1, "interco_pair_id": 1, "interco_return_pair_id": 1,
             "origin_sales_return_id": 1}).sort("created_at", 1):
        if t.get("interco_pair_id") or t.get("interco_return_pair_id") or t.get("origin_sales_return_id"):
            continue
        items = t.get("items") or []
        menunggu.append({"id": t["id"], "code": t.get("code", ""), "dari": t.get("source_entity_id", ""),
                         "ke": t.get("dest_entity_id", ""), "dibuat": t.get("created_at", ""),
                         "pengaju": t.get("requested_by", ""),
                         "roll": sum(len(it.get("rolls") or []) for it in items),
                         "qty": round(sum(float(it.get("qty") or 0) for it in items), 2)})

    asal_transfer: Dict[str, str] = {}
    async for t in db.warehouse_transfers.find({"transfer_kind": "inter_entity"},
                                               {"_id": 0, "id": 1, "origin_sales_return_id": 1}):
        asal_transfer[t["id"]] = "pindah roll retur" if t.get("origin_sales_return_id") else "kasir lama"
    grup: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    async for je in db.journal_entries.find({"source_type": "inter_company_transfer", "status": {"$ne": "void"}},
                                            {"_id": 0, "source_id": 1, "entity_id": 1, "lines": 1,
                                             "intercompany_counterpart_entity_id": 1}):
        sid = str(je.get("source_id") or "")
        tid, _, sisi = sid.rpartition(":")
        asal = asal_transfer.get(tid, "kasir lama")
        if sisi == "src":
            dari, ke = je.get("entity_id", ""), je.get("intercompany_counterpart_entity_id", "")
        else:
            dari, ke = je.get("intercompany_counterpart_entity_id", ""), je.get("entity_id", "")
        g = grup.setdefault((asal, dari, ke), {"asal": asal, "dari": dari, "ke": ke, "transfer": set(),
                                               "piutang_1250": 0.0, "utang_2250": 0.0})
        g["transfer"].add(tid)
        for ln in je.get("lines") or []:
            d, c = float(ln.get("debit") or 0), float(ln.get("credit") or 0)
            if sisi == "src" and ln.get("account_code") == AKUN_PIUTANG:
                g["piutang_1250"] += d - c
            if sisi == "dst" and ln.get("account_code") == AKUN_UTANG:
                g["utang_2250"] += c - d
    jurnal = [{**g, "transfer": len(g["transfer"]), "piutang_1250": round(g["piutang_1250"], 2),
               "utang_2250": round(g["utang_2250"], 2)} for g in sorted(grup.values(), key=lambda x: (x["asal"],
                                                                                                  x["dari"], x["ke"]))]
    return {"menunggu": menunggu, "jurnal": jurnal}


def cetak(hasil: Dict[str, Any]) -> None:
    print("PK-30 — sisa jalur transfer antar-PT harga pokok (BACA-SAJA, tidak ada yang ditulis)\n")
    print(f"1. Transfer lama menunggu persetujuan (tidak bisa disetujui lagi — tolak): {len(hasil['menunggu'])}")
    for t in hasil["menunggu"]:
        print(f"   {t['code']:<22} {t['dari']} → {t['ke']}  {t['roll']} roll · {t['qty']}  dibuat {t['dibuat'][:10]}"
              f"  oleh {t['pengaju']}")
    print(f"\n2. Jurnal harga pokok yang sudah terbit (tidak tampil di Saldo Antar-PT): {len(hasil['jurnal'])} kelompok")
    for g in hasil["jurnal"]:
        print(f"   [{g['asal']}] {g['dari']} → {g['ke']}: {g['transfer']} transfer · 1-1250 {_rp(g['piutang_1250'])}"
              f" · 2-1250 {_rp(g['utang_2250'])}")
    print("\nPerbaikan saldo di atas = keputusan pemilik (H3). Skrip ini tidak punya mode tulis.")


async def main() -> int:
    from db import db
    cetak(await kumpulkan(db))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
