"""PY-T3 (PY-04, PY-07, PY-08) — data lama untuk aturan hitung gaji per PT.

    python scripts/migrasi_pyt3_aturan_gaji.py            # baca-saja (bawaan): cetak, tidak menulis apa pun
    python scripts/migrasi_pyt3_aturan_gaji.py --apply    # tandai Gaji Pokok & Tunjangan bawaan "Diprorata"

Sejak PY-T3 isi awal komponen gaji (`hr_pay_components`) menandai GAJI_POKOK dan TUNJANGAN `prorate: true` (yang dibagi
saat "Gaji karyawan masuk/keluar tengah bulan" dinyalakan; juga dasar potongan harian). PT yang komponennya dibuat
sebelum PY-T3 masih bertanda `false` — selama pengaturan prorata dan potongan mati (bawaan), tanda itu tidak berefek.

Mode baca-saja mencetak:
  1. per PT: komponen bawaan GAJI_POKOK / TUNJANGAN yang belum bertanda Diprorata (akan ditandai `--apply`);
  2. per PT: komponen potongan absensi bawaan (POT_ALPHA, POT_CUTI_TG, POT_TELAT) yang belum ada — dibuat otomatis saat
     server menyala (`ensure_defaults`), jadi angka ini harus 0 di server yang sudah berjalan;
  3. daftar libur lama `system_settings{scope:"hr"}.overtime.holidays` (tersembunyi, tanpa layar) — TIDAK dipindah
     otomatis dan tidak dibaca lagi: isi lewat Pengaturan › SDM › Kalender Libur (tanggal resmi, keputusan pemilik);
  4. komponen buatan pengguna yang bertanda Dasar BPJS / Dasar lembur (sejak PY-T3 ikut dasar iuran BPJS / upah sejam);
  5. dampak K-39 — tiga periode terakhir per PT: menit lembur absensi tanpa pengajuan dan nilainya (dibayar bila
     "Lembur dibayar berdasarkan" = absensi; tidak dibayar pada bawaan pengajuan);
  6. slip di proses gaji yang masih bisa dihitung ulang (draf) milik karyawan yang tanggal masuknya sesudah akhir periode
     (tidak ikut lagi saat dihitung ulang).
`--apply` hanya menulis butir 1 (aman diulang). Menjalankannya pada data nyata = titik henti H3 (keputusan pemilik;
ambil cadangan `hr_pay_components` lebih dulu). Dijalankan di dalam container backend (butuh `backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

PRORATA_KODE = ("GAJI_POKOK", "TUNJANGAN")
POTONGAN_KODE = ("POT_ALPHA", "POT_CUTI_TG", "POT_TELAT")


def _periode_terakhir(hari_ini: str, n: int = 3) -> List[str]:
    y, m = int(hari_ini[:4]), int(hari_ini[5:7])
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out


async def kumpulkan(db, dampak: bool = True) -> Dict[str, Any]:
    ents = [e async for e in db.business_entities.find({}, {"_id": 0, "id": 1, "code": 1})]
    belum_prorata, belum_potongan = {}, {}
    for e in ents:
        comps = {c["code"]: c async for c in db.hr_pay_components.find(
            {"entity_id": e["id"]}, {"_id": 0, "id": 1, "code": 1, "prorate": 1, "system": 1})}
        if not comps:
            continue
        belum_prorata[e["id"]] = [c for k, c in comps.items() if k in PRORATA_KODE and c.get("system")
                                  and not c.get("prorate")]
        belum_potongan[e["id"]] = [k for k in POTONGAN_KODE if k not in comps]
    lama = (await db.system_settings.find_one({"scope": "hr"}, {"_id": 0, "overtime": 1}) or {}).get("overtime") or {}
    libur_lama = list(lama.get("holidays") or []) if isinstance(lama, dict) else []
    bertanda = await db.hr_pay_components.find(
        {"system": {"$ne": True}, "$or": [{"in_bpjs_base": True}, {"in_overtime_base": True}]},
        {"_id": 0, "entity_id": 1, "code": 1, "in_bpjs_base": 1, "in_overtime_base": 1}).to_list(500)
    out: Dict[str, Any] = {"ents": ents, "belum_prorata": belum_prorata, "belum_potongan": belum_potongan,
                           "libur_lama": libur_lama, "bertanda": bertanda, "dampak": [], "masuk_kemudian": []}
    from services import book_date
    from services import hr_payroll_service as pay
    from services.hr_compensation_service import period_bounds
    pers = _periode_terakhir(book_date.tanggal_buku())
    if dampak:
        for e in ents:
            for per in pers:
                try:
                    j = await pay.overtime_impact(e["id"], per)
                except Exception as exc:   # noqa: BLE001 — laporan; satu PT gagal tidak menghentikan yang lain
                    out["dampak"].append({"entity_id": e["id"], "period": per, "error": str(exc)[:120]})
                    continue
                out["dampak"].append({"entity_id": e["id"], "period": per, "count": j["count"],
                                      "minutes": j["total_minutes"], "amount": j["total_amount"]})
    draf = {r["id"]: r async for r in db.hr_payroll_runs.find({"status": "draft"},
                                                              {"_id": 0, "id": 1, "number": 1, "period": 1})}
    if draf:
        async for s in db.hr_payslips.find({"run_id": {"$in": list(draf)}},
                                           {"_id": 0, "run_id": 1, "employee_id": 1, "period": 1}):
            emp = await db.hr_employees.find_one({"id": s["employee_id"]}, {"_id": 0, "join_date": 1, "name": 1}) or {}
            masuk = str(emp.get("join_date") or "")[:10]
            if len(masuk) == 10 and masuk > period_bounds(s["period"])[1]:
                out["masuk_kemudian"].append({"run": draf[s["run_id"]].get("number") or s["run_id"],
                                              "employee_id": s["employee_id"], "join_date": masuk,
                                              "period": s["period"]})
    return out


async def jalankan(argv=None, db=None) -> int:
    ap = argparse.ArgumentParser(description="Data lama untuk aturan hitung gaji per PT (PY-T3).")
    ap.add_argument("--apply", action="store_true", help="tandai GAJI_POKOK & TUNJANGAN bawaan Diprorata (data nyata = H3)")
    ap.add_argument("--tanpa-dampak", action="store_true", help="lewati hitungan dampak lembur (cepat)")
    args = ap.parse_args(argv)
    if db is None:
        from db import db as _db
        db = _db
    h = await kumpulkan(db, dampak=not args.tanpa_dampak)
    kode = {e["id"]: e.get("code") or e["id"] for e in h["ents"]}
    for eid, rows in h["belum_prorata"].items():
        if rows:
            print(f"PT {kode[eid]}: komponen bawaan belum Diprorata → " + ", ".join(r["code"] for r in rows))
    for eid, rows in h["belum_potongan"].items():
        if rows:
            print(f"PT {kode[eid]}: komponen potongan absensi belum ada (dibuat saat server menyala) → " + ", ".join(rows))
    if h["libur_lama"]:
        print(f"Daftar libur lama system_settings hr.overtime.holidays: {len(h['libur_lama'])} tanggal "
              f"({', '.join(map(str, h['libur_lama'][:10]))}{' …' if len(h['libur_lama']) > 10 else ''}) — TIDAK dibaca "
              f"lagi; isi ulang lewat Pengaturan › SDM › Kalender Libur (keputusan pemilik)")
    for c in h["bertanda"]:
        tanda = [t for t, f in (("Dasar BPJS", "in_bpjs_base"), ("Dasar lembur", "in_overtime_base")) if c.get(f)]
        print(f"PT {kode.get(c.get('entity_id'), c.get('entity_id'))}: komponen {c.get('code')} bertanda "
              f"{' · '.join(tanda)} — sejak PY-T3 ikut dasar iuran BPJS / upah sejam lembur")
    for d in h["dampak"]:
        if d.get("error"):
            print(f"Dampak lembur PT {kode.get(d['entity_id'])} {d['period']}: gagal dihitung ({d['error']})")
        else:
            print(f"Dampak lembur PT {kode.get(d['entity_id'])} {d['period']}: {d['count']} karyawan · "
                  f"{d['minutes']} menit absensi tanpa pengajuan · Rp {d['amount']:,.2f}")
    for m in h["masuk_kemudian"]:
        print(f"Slip draf {m['run']} periode {m['period']}: karyawan {m['employee_id']} masuk {m['join_date']} — tidak "
              f"ikut lagi saat dihitung ulang")
    n_pr = sum(len(v) for v in h["belum_prorata"].values())
    n_pot = sum(len(v) for v in h["belum_potongan"].values())
    print(f"Ringkasan: {n_pr} komponen akan ditandai Diprorata · {n_pot} komponen potongan belum ada · "
          f"{len(h['libur_lama'])} tanggal libur lama · {len(h['bertanda'])} komponen buatan pengguna bertanda dasar · "
          f"{len(h['masuk_kemudian'])} slip draf karyawan masuk kemudian")
    if not args.apply:
        print("Mode baca-saja: tidak ada yang diubah. Pakai --apply untuk menandai (data nyata = keputusan pemilik).")
        return 0
    n = 0
    for rows in h["belum_prorata"].values():
        for r in rows:
            res = await db.hr_pay_components.update_one(
                {"id": r["id"], "system": True, "prorate": {"$ne": True}},
                {"$set": {"prorate": True, "updated_by": "migrasi PY-T3"}})
            n += res.modified_count
    print(f"Diterapkan: {n} komponen ditandai Diprorata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(jalankan(sys.argv[1:])))
