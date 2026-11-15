"""TX-T2 (TX-05) — status & asal faktur pajak keluaran LAMA ke kosakata baru.

    python scripts/migrate_tax_invoice_status.py --dry-run   # laporan saja, tidak menulis apa pun
    python scripts/migrate_tax_invoice_status.py             # terapkan (data nyata = titik henti H3, keputusan pemilik)
    python scripts/migrate_tax_invoice_status.py --undo      # kembalikan PERSIS yang diubah skrip ini

Sejak TX-T2 faktur asal yang diganti berstatus `diganti` (dulu tetap `normal`/`pengganti` dan hanya diberi
`replaced_by_id`), dokumen membawa `doc_kind` (`faktur` · `retur`) dan `trigger` (`pesanan` · `surat_jalan` · `retur`).
Skrip ini, untuk faktur keluaran yang BUKAN antar-PT (`source_type: interco` tidak disentuh — layarnya sendiri):

  * mengisi `doc_kind: faktur` dan `trigger: pesanan` pada dokumen yang belum punya field itu;
  * mengubah faktur ber-`replaced_by_id` terisi yang statusnya masih `normal`/`pengganti` menjadi `diganti`, dengan
    `status_before_replaced` = status lamanya; `active_key`/`nsfp_key` yang tersisa dicabut (aturan PK-40).

Setiap perubahan dicatat di field `tx_t2_migrasi` dokumennya (field apa yang diisi, status sebelum), sehingga `--undo`
mengembalikan persis itu dan tidak menyentuh dokumen yang lahir sesudah TX-T2. Aman diulang: putaran kedua tanpa
perubahan. Rekap PPN tidak berubah: faktur ber-`replaced_by_id` sudah tidak dihitung sejak PK-45.
Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`). Keluar 0.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

STATUS_LAMA_DIGANTI = ("normal", "pengganti")
_FIELDS = {"_id": 0, "id": 1, "number": 1, "status": 1, "replaced_by_id": 1, "doc_kind": 1, "trigger": 1,
           "source_type": 1, "interco_pair_id": 1, "active_key": 1, "nsfp_key": 1, "tx_t2_migrasi": 1}


def _antar_pt(d: Dict[str, Any]) -> bool:
    return d.get("source_type") == "interco" or bool(d.get("interco_pair_id"))


def rencana(d: Dict[str, Any]) -> Dict[str, Any]:
    """Perubahan untuk satu dokumen: `{"set", "unset", "catat"}` (kosong bila tidak ada yang perlu diubah)."""
    if _antar_pt(d):
        return {}
    setel: Dict[str, Any] = {}
    catat: Dict[str, Any] = {}
    if not d.get("doc_kind"):
        setel["doc_kind"] = "faktur"
        catat["doc_kind"] = True
    if not d.get("trigger") and (d.get("doc_kind") or "faktur") == "faktur":
        setel["trigger"] = "pesanan"
        catat["trigger"] = True
    unset: List[str] = []
    if d.get("replaced_by_id") and d.get("status") in STATUS_LAMA_DIGANTI:
        setel.update({"status": "diganti", "status_before_replaced": d["status"]})
        catat["status"] = d["status"]
        unset = [f for f in ("active_key", "nsfp_key") if f in d]
        if unset:
            catat["kunci"] = {f: d[f] for f in unset}
    if not setel:
        return {}
    return {"set": setel, "unset": unset, "catat": catat}


def rencana_undo(d: Dict[str, Any]) -> Dict[str, Any]:
    catat = d.get("tx_t2_migrasi") or {}
    if not catat:
        return {}
    setel: Dict[str, Any] = {}
    unset = ["tx_t2_migrasi"]
    if catat.get("doc_kind"):
        unset.append("doc_kind")
    if catat.get("trigger"):
        unset.append("trigger")
    if catat.get("status") and d.get("status") == "diganti":
        setel["status"] = catat["status"]
        unset.append("status_before_replaced")
        setel.update(catat.get("kunci") or {})
    return {"set": setel, "unset": unset}


async def kumpulkan(db, *, undo: bool = False) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    async for d in db.tax_invoices.find({}, _FIELDS):
        r = rencana_undo(d) if undo else rencana(d)
        if r:
            out.append({"id": d["id"], "number": d.get("number", ""), **r})
    return out


async def terapkan(db, ubah: List[Dict[str, Any]], *, undo: bool = False) -> int:
    n = 0
    for u in ubah:
        ops: Dict[str, Any] = {}
        setel = dict(u.get("set") or {})
        if not undo and u.get("catat"):
            setel["tx_t2_migrasi"] = u["catat"]
        if setel:
            ops["$set"] = setel
        if u.get("unset"):
            ops["$unset"] = {f: "" for f in u["unset"]}
        res = await db.tax_invoices.update_one({"id": u["id"]}, ops)
        n += int(res.modified_count)
    return n


async def jalankan(argv=None, db=None) -> int:
    ap = argparse.ArgumentParser(description="Status 'diganti' + asal dokumen faktur pajak keluaran lama (TX-T2).")
    ap.add_argument("--dry-run", action="store_true", help="laporan saja, tidak menulis apa pun")
    ap.add_argument("--undo", action="store_true", help="kembalikan perubahan yang dicatat skrip ini")
    args = ap.parse_args(argv)
    if db is None:
        from db import db as _db
        db = _db
    ubah = await kumpulkan(db, undo=args.undo)
    diganti = sum(1 for u in ubah if "status" in (u.get("set") or {}))
    arah = "dikembalikan" if args.undo else "diubah"
    print(f"tax_invoices: {len(ubah)} faktur perlu {arah} ({diganti} berubah status)")
    for u in ubah[:20]:
        print(f"  {u['number'] or u['id']}: set {sorted((u.get('set') or {}).keys())} cabut {u.get('unset') or []}")
    if args.dry_run:
        print("Mode --dry-run: tidak ada yang ditulis. Menjalankan pada data nyata = keputusan pemilik (H3).")
        return 0
    print(f"Selesai: {await terapkan(db, ubah, undo=args.undo)} faktur {arah}.")
    return 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
