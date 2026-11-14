"""CR-T1 — pindahkan plafon & status blokir pelanggan LAMA ke profil kredit per PT (`customer_credit_profiles`).

    python scripts/migrate_credit_profiles.py              # lapor saja (bawaan, = --dry-run): tidak menulis apa pun
    python scripts/migrate_credit_profiles.py --dry-run    # sama dengan bawaan
    python scripts/migrate_credit_profiles.py --terapkan   # tulis profil + buka status (data nyata = titik henti H3)

Aturan (`docs/blueprint/unit/CR-T1.md`, tabel "Migrasi"), PT = `customers.entity_id`:
  * `credit_limit > 0`    → profil `limit_mode: khusus`, `credit_limit` sama. Plafon 0/kosong dan tidak diblokir: tidak
                            dibuat (ikut PT; bawaan PT 0 = tanpa batas, sama dengan hari ini).
  * `status == "blocked"` → `credit_status: blokir_manual`, `block_reason: "Dipindahkan dari status pelanggan"`;
                            `customers.status` menjadi `active`.
Idempoten: pelanggan yang sudah punya profil di PT itu tidak dibuatkan lagi; putaran kedua 0 perubahan.
`customers.credit_limit` tidak dihapus. Sesudah `--terapkan` selesai, penanda `crt1_profil_kredit` mematikan cadangan
`data_lama` di `credit_profile_service.effective` (sebelum itu aplikasi membaca nilai yang sama dari data pelanggan).

Laporan juga memuat pesanan yang PT-nya berbeda dari PT pemilik data pelanggan (ASUMSI unit: di PT itu pelanggan memakai
bawaan PT sesudah migrasi). Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def pesanan_lintas_pt(batas: int = 50) -> dict:
    """Pasangan (pelanggan, PT pesanan) yang PT pesanannya ≠ `customers.entity_id` (baca saja)."""
    from db import db
    pt_pelanggan = {c["id"]: c.get("entity_id") or "" async for c in
                    db.customers.find({}, {"_id": 0, "id": 1, "entity_id": 1})}
    hit: dict = {}
    async for o in db.sales_orders.find({}, {"_id": 0, "customer_id": 1, "entity_id": 1}):
        cid, eid = o.get("customer_id"), o.get("entity_id") or ""
        if cid in pt_pelanggan and eid and eid != pt_pelanggan[cid]:
            hit[(cid, eid)] = hit.get((cid, eid), 0) + 1
    rows = [{"customer_id": c, "entity_id": e, "pt_pelanggan": pt_pelanggan[c], "pesanan": n}
            for (c, e), n in sorted(hit.items())]
    return {"jumlah": len(rows), "contoh": rows[:batas]}


async def jalankan(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Migrasi profil kredit CR-T1 (lapor bawaan).")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--terapkan", action="store_true", help="tulis profil & buka status (data nyata = H3)")
    g.add_argument("--dry-run", action="store_true", help="lapor saja (bawaan)")
    args = ap.parse_args(argv)
    from services.credit_profile_service import migrasi_data_lama
    hasil = await migrasi_data_lama(tulis=args.terapkan)
    for r in hasil["rincian"]:
        plafon = f"plafon khusus {r['credit_limit']:,.0f}".replace(",", ".") if r["limit_mode"] == "khusus" \
            else "ikut PT"
        print(f"  {r['entity_id']} · {r['name'] or r['customer_id']}: {plafon}"
              f"{' · blokir manual' if r['credit_status'] == 'blokir_manual' else ''}")
    lintas = await pesanan_lintas_pt()
    print(f"Pesanan ber-PT lain dari PT pelanggan: {lintas['jumlah']} pasangan (pelanggan, PT) — di PT itu memakai "
          "bawaan PT.")
    for r in lintas["contoh"]:
        print(f"  {r['customer_id']}: PT pelanggan {r['pt_pelanggan']}, pesanan di {r['entity_id']} ({r['pesanan']})")
    if not args.terapkan:
        print(f"Mode lapor: {hasil['profil_dibuat']} profil akan dibuat, {hasil['status_dibuka']} pelanggan dibuka "
              "statusnya; tidak ada yang diubah. Pakai --terapkan untuk menulis (data nyata = keputusan pemilik).")
    else:
        print(f"Selesai: {hasil['profil_dibuat']} profil dibuat, {hasil['status_dibuka']} pelanggan dibuka statusnya.")
    return 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
