"""PY-T2 (PY-09) — karyawan lama diberi baris riwayat kompensasi dan penugasan PT pertama dari isi master.

    python scripts/migrate_hr_compensation_py_t2.py            # baca-saja (bawaan): cetak, tidak menulis apa pun
    python scripts/migrate_hr_compensation_py_t2.py --apply    # tulis baris pertama untuk karyawan tanpa riwayat

Sejak PY-T2 gaji pokok, tunjangan tetap, dan PT karyawan dibaca proses gaji dari `hr_compensation_history` dan
`hr_employee_assignments` (baris `approved` bertanggal berlaku); master `hr_employees` menjadi nilai turunan. Karyawan
TANPA riwayat tetap dibaca dari master (perilaku lama), jadi skrip ini boleh dijalankan kapan saja sesudah kode PY-T2.

Tiap karyawan tanpa riwayat mendapat:
  * satu baris kompensasi `approved`, `source: "migrasi"`: `base_salary` master; `fixed_components` = tiap isi
    `allowances` (kode komponen TUNJANGAN, `label` = nama tunjangan);
  * satu baris penugasan `approved`, `source: "migrasi"`: PT, departemen, dan jabatan master;
  berlaku sejak tanggal masuk (`join_date`); bila kosong/tak sah → tanggal dibuat (WIB) — karyawan ini DIDAFTAR
  (RISIKO spesifikasi: tanggal berlaku bisa keliru, periksa). Bagian yang sudah punya baris dilewati: aman diulang.

Laporan: jumlah karyawan (seluruhnya, tanpa riwayat, yang memakai tanggal dibuat), jumlah per PT dengan Σ gaji pokok
+ tunjangan master dan Σ nilai baris yang akan dibuat (harus sama), dan — mode `--apply` — pratinjau gaji bulan berjalan
per PT (Σ bruto) sebelum = sesudah. Nilai gaji per orang TIDAK dicetak (data pribadi). Menjalankannya pada data nyata =
titik henti H3 (keputusan pemilik; ambil cadangan `hr_employees` lebih dulu). Dijalankan di dalam container backend.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

AKTOR = {"id": "system", "name": "Migrasi PY-T2"}


def _rp(v: float) -> str:
    return f"Rp {round(float(v or 0)):,}".replace(",", ".")


def tanggal_berlaku(emp: Dict[str, Any]) -> tuple:
    """(tanggal, sumber) — tanggal masuk bila sah; selain itu tanggal dibuat (WIB); selain itu hari ini."""
    from services import book_date
    from services import hr_compensation_service as hc
    try:
        return hc.check_date(emp.get("join_date")), "tanggal masuk"
    except ValueError:
        pass
    try:
        if emp.get("created_at"):
            return book_date.tanggal_buku(emp["created_at"]), "tanggal dibuat"
    except ValueError:
        pass
    return hc.today(), "hari ini"


async def kumpulkan(db) -> Dict[str, Any]:
    from services import hr_compensation_service as hc
    from services import hr_pay_components as pc
    emps = [e async for e in db.hr_employees.find({}, {"_id": 0}).sort([("entity_id", 1), ("code", 1)])]
    comp = set(await db.hr_compensation_history.distinct("employee_id"))
    asg = set(await db.hr_employee_assignments.distinct("employee_id"))
    rencana: List[Dict[str, Any]] = []
    for e in emps:
        if e["id"] in comp and e["id"] in asg:
            continue
        tgl, sumber = tanggal_berlaku(e)
        fixed = hc.fixed_from_allowances(e.get("allowances"))
        # pembaca slip sebelum PY-T2 (`allowance_rows`) vs isi baris baru (`fixed_from_allowances`)
        master = float(e.get("base_salary") or 0) + sum(amt for _, amt in pc.allowance_rows(e.get("allowances")))
        rencana.append({"emp": e, "tanggal": tgl, "sumber": sumber, "kompensasi": e["id"] not in comp,
                        "penugasan": e["id"] not in asg, "master": round(master, 2),
                        "baris": round(float(e.get("base_salary") or 0) + sum(f["amount"] for f in fixed), 2)})
    return {"emps": emps, "rencana": rencana}


async def _pratinjau(entity_ids: List[str]) -> Dict[str, float]:
    from services import hr_compensation_service as hc
    from services import hr_payroll_service as pay
    periode = hc.today()[:7]
    out: Dict[str, float] = {}
    for ent in entity_ids:
        if not ent:
            continue
        try:
            out[ent] = round(float((await pay.preview_run(ent, periode))["totals"]["gross"]), 2)
        except Exception as exc:  # noqa: BLE001 — laporan, bukan penjaga: tulis alasannya
            out[ent] = f"tidak bisa dihitung ({exc})"   # type: ignore[assignment]
    return out


async def jalankan(argv=None, db=None) -> int:
    ap = argparse.ArgumentParser(description="Karyawan lama → riwayat kompensasi & penugasan PT pertama (PY-T2).")
    ap.add_argument("--apply", action="store_true", help="tulis baris pertama (data nyata = H3)")
    args = ap.parse_args(argv)
    if db is None:
        from db import db as _db
        db = _db
    from services import hr_compensation_service as hc
    h = await kumpulkan(db)
    rencana = h["rencana"]
    per_pt: Dict[str, Dict[str, Any]] = {}
    for r in rencana:
        pt = per_pt.setdefault(r["emp"].get("entity_id") or "(tanpa PT)", {"n": 0, "master": 0.0, "baris": 0.0})
        pt["n"] += 1
        pt["master"] += r["master"]
        pt["baris"] += r["baris"]
    for pt, v in sorted(per_pt.items()):
        sama = "SAMA" if round(v["master"], 2) == round(v["baris"], 2) else "BEDA"
        print(f"PT {pt}: {v['n']} karyawan tanpa riwayat · gaji pokok + tunjangan master {_rp(v['master'])} · "
              f"nilai baris yang dibuat {_rp(v['baris'])} → {sama}")
    dibuat = [r for r in rencana if r["sumber"] != "tanggal masuk"]
    for r in dibuat:
        e = r["emp"]
        print(f"TANGGAL MASUK KOSONG: {e.get('code') or e['id']} {e.get('name', '')} · berlaku {r['tanggal']} "
              f"({r['sumber']}) — periksa")
    print(f"Ringkasan: {len(h['emps'])} karyawan · {len(rencana)} tanpa riwayat lengkap "
          f"({sum(1 for r in rencana if r['kompensasi'])} tanpa kompensasi, "
          f"{sum(1 for r in rencana if r['penugasan'])} tanpa penugasan) · {len(dibuat)} memakai tanggal dibuat")
    if not args.apply:
        print("Mode baca-saja: tidak ada yang diubah. Pakai --apply untuk menulis (data nyata = keputusan pemilik).")
        return 0
    pts = sorted({r["emp"].get("entity_id") or "" for r in rencana if r["emp"].get("status") == "active"})
    sebelum = await _pratinjau(pts)
    n_comp = n_asg = 0
    for r in rencana:
        hasil = await hc.initial_rows(r["emp"], AKTOR, source="migrasi", effective_from=r["tanggal"])
        n_comp += 1 if hasil["compensation"] else 0
        n_asg += 1 if hasil["assignment"] else 0
    sesudah = await _pratinjau(pts)
    beda = 0
    periode = hc.today()[:7]
    for pt in pts:
        ok = sebelum.get(pt) == sesudah.get(pt)
        beda += 0 if ok else 1
        print(f"Pratinjau gaji {periode} PT {pt}: bruto sebelum {sebelum.get(pt)} · sesudah {sesudah.get(pt)} → "
              f"{'SAMA' if ok else 'BEDA'}")
    print(f"Diterapkan: {n_comp} baris kompensasi · {n_asg} baris penugasan"
          + (f" · {beda} PT pratinjau berbeda — periksa." if beda else "."))
    return 1 if beda else 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
