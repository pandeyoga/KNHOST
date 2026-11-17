"""PR-T3 U14, U15 — sapuan kode jawaban 13 peran bawaan dan isi dasbor Manajer (docs/blueprint/unit/PR-T3.md).

`data/kode_sebelum_PRT3.json` dibuat dari kode SEBELUM unit ini (langkah kerja 1), di basis data tiruan baru, dengan
menjalankan modul ini ber-variabel lingkungan `KN_PRT3_TULIS_SEBELUM=1` (uji ditandai "dilewati" dan berkas ditulis):
  * `kode`: kode jawaban tiap (peran bawaan, rute) untuk rute S3–S8 dan baris pertama tabel B (cetak label lot). Id yang
    dipakai tidak ada (`tidak-ada`, `x`) sehingga tidak ada data yang berubah;
  * `dasbor_manajer`: jumlah butir tiap bagian `GET /api/dashboard` oleh manajer seed (fixture U5: satu pesanan dan
    satu pelanggan milik `sales@` disisipkan langsung ke basis data — fixture, bukan alur).
Sesudah unit: Admin dan Manajer sama di semua rute; selisih lain hanya ke 403 pada rute yang gerbangnya kini dituntut
izin, untuk peran bawaan yang memang tidak memegang izin itu (lihat `SELISIH_SAH`). Modul sendiri (basis data sendiri).
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

import permissions_config

pytestmark = pytest.mark.anyio

BERKAS_SEBELUM = Path(__file__).parent / "data" / "kode_sebelum_PRT3.json"
TULIS_SEBELUM = os.environ.get("KN_PRT3_TULIS_SEBELUM") == "1"

PERAN_BAWAAN = ["admin", "sales", "manager", "sales_admin", "finance", "warehouse", "designer", "md",
                "warehouse_admin", "driver", "sample_admin", "md_quality", "qc"]

# (kode putusan, metode, jalur, isi)
RUTE: List[Tuple[str, str, str, Optional[Dict[str, Any]]]] = [
    # KM-T5 — ("S3", "GET", "/api/sales-targets") dicabut: rutenya dihapus (target lewat `/api/incentive/targets`).
    ("S3", "GET", "/api/sales-incentives", None),
    ("S4", "GET", "/api/sales-users", None),
    ("S5", "GET", "/api/entities/count", None),
    ("S5", "GET", "/api/entities/ent_ksc", None),
    ("S5", "GET", "/api/entities/ent_ksc/readiness", None),
    ("S6", "GET", "/api/finance/period-unlocks", None),
    ("S7", "GET", "/api/purchase-orders/resolve-sourcing?product_id=x", None),
    ("S8", "POST", "/api/special-orders/tidak-ada/fulfillment/k/route", {"route": "buy", "reason": "uji sapuan PR-T3"}),
    ("S8", "POST", "/api/special-orders/tidak-ada/fulfillment/k/realize", {"warehouse_id": ""}),
    ("B1", "POST", "/api/lots/tidak-ada/label", {"format": "zpl", "qty": 1, "roll_id": ""}),
]

#: Izin yang kini dituntut gerbang tiap putusan (salah satu cukup). Peran bawaan TANPA izin itu boleh berubah ke 403;
#: pemegangnya harus tetap sama. Baris B1 (label lot) berputusan "tetap" (lihat laporan PR-T3): tidak ada selisih.
SELISIH_SAH: Dict[str, List[Tuple[str, str]]] = {
    "S3": [("order", "view")],
    "S4": [("customer", "view"), ("order", "view"), ("sales_force", "view")],
    "S5": [("entity", "view")],
    "S6": [("period", "unlock"), ("accounting", "view")],
    "S7": [("purchase_order", "create"), ("purchase_order", "update")],
}
SELISIH_SAH_S8 = {"/route": ("od_fulfillment", "choose_route"), "/realize": ("od_fulfillment", "realize")}


def _memegang(peran: str, pasangan: List[Tuple[str, str]]) -> bool:
    izin = permissions_config.DEFAULT_PERMISSIONS.get(peran, {})
    return any(a in (izin.get(m) or []) or "*" in (izin.get(m) or []) for m, a in pasangan)


def _kunci(metode: str, jalur: str) -> str:
    return f"{metode} {jalur}"


async def sapu(klien, akun, sesi) -> Dict[str, Dict[str, int]]:
    """{peran: {"METODE jalur": kode}} untuk 13 peran bawaan (satu akun baru per peran, PT `ent_ksc`)."""
    out: Dict[str, Dict[str, int]] = {}
    for peran in PERAN_BAWAAN:
        h = await sesi(await akun(peran))
        out[peran] = {_kunci(m, j): (await klien.request(m, j, headers=h, json=isi)).status_code
                      for _, m, j, isi in RUTE}
    return out


async def _fixture_u5(db) -> None:
    """Fixture U5 (disisipkan langsung): satu pesanan aktif dan satu pelanggan milik `sales@` di `ent_ksc`."""
    sls = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1, "name": 1})
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not await db.customers.find_one({"id": "cust_uji_prt3"}):
        await db.customers.insert_one({"id": "cust_uji_prt3", "code": "CUJ-PRT3", "name": "Pelanggan Uji PR-T3",
                                       "entity_id": "ent_ksc", "assigned_sales_id": sls["id"], "status": "active",
                                       "created_at": now})
    if not await db.sales_orders.find_one({"id": "so_uji_prt3"}):
        await db.sales_orders.insert_one({"id": "so_uji_prt3", "number": "KSC/SO-PRT3-1", "entity_id": "ent_ksc",
                                          "customer_id": "cust_uji_prt3", "customer_name": "Pelanggan Uji PR-T3",
                                          "sales_id": sls["id"], "created_by": sls["id"], "status": "approved",
                                          "items": [], "total": 0, "created_at": now})


def ringkas_dasbor(j: Dict[str, Any]) -> Dict[str, Any]:
    """Jumlah butir tiap bagian + angka ringkas (bukan isi) — pembanding U15."""
    m = j.get("metrics") or {}
    return {"orders": len(j.get("orders") or []), "customers": len(j.get("customers") or []),
            "products": len(j.get("products") or []), "warehouses": len(j.get("warehouses") or []),
            "metrics": {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in sorted(m.items())},
            "stock_scope": sorted((j.get("stock_scope") or {}).keys())}


async def _dasbor_manajer(klien, sesi) -> Dict[str, Any]:
    r = await klien.get("/api/dashboard", headers=await sesi("manager@kainnusantara.id"))
    assert r.status_code == 200, r.text
    return ringkas_dasbor(r.json())


if TULIS_SEBELUM:   # hanya dikumpulkan dengan `KN_PRT3_TULIS_SEBELUM=1` (kode SEBELUM unit; langkah kerja 1)
    async def test_tulis_berkas_sebelum(klien, akun, sesi, db):
        await _fixture_u5(db)
        isi = {"kode": await sapu(klien, akun, sesi), "dasbor_manajer": await _dasbor_manajer(klien, sesi)}
        BERKAS_SEBELUM.write_text(json.dumps(isi, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        pytest.skip(f"berkas sebelum ditulis: {BERKAS_SEBELUM.name}")


@pytest.mark.skipif(TULIS_SEBELUM, reason="mode menulis berkas sebelum")
async def test_PRT3_U14_kode_jawaban_peran_bawaan(klien, akun, sesi):
    sebelum = json.loads(BERKAS_SEBELUM.read_text())["kode"]
    sesudah = await sapu(klien, akun, sesi)
    assert sorted(sebelum) == sorted(PERAN_BAWAAN)
    putusan = {_kunci(m, j): (p, j) for p, m, j, _ in RUTE}
    tak_sah = []
    for peran, rutes in sesudah.items():
        for rute, kode in rutes.items():
            lama = sebelum[peran][rute]
            if lama == kode:
                continue
            # K-FIN-01 (pemilik 17 Nov 2026 malam: Finance memegang akses yang sama dengan Manajer) — kode Finance = kode
            # Manajer.
            if peran == "finance" and kode == sesudah["manager"][rute]:
                continue
            p, jalur = putusan[rute]
            if peran in ("admin", "manager"):
                tak_sah.append((peran, rute, lama, kode, "Admin/Manajer harus sama"))
            elif p == "S8":
                pasangan = [SELISIH_SAH_S8["/route" if jalur.endswith("/route") else "/realize"]]
                if kode != 403 or _memegang(peran, pasangan):
                    tak_sah.append((peran, rute, lama, kode, "S8"))
            elif p in SELISIH_SAH:
                if not (lama == 200 and kode == 403) or _memegang(peran, SELISIH_SAH[p]):
                    tak_sah.append((peran, rute, lama, kode, p))
            else:
                tak_sah.append((peran, rute, lama, kode, "tidak boleh berubah"))
    assert not tak_sah, tak_sah
    # Bunyi U14: S3/S4 menolak Desainer, Sopir, MD Quality, QC; S5 hanya Admin & Manajer; S6 + Finance; S7 hanya
    # Admin & Manajer (semua dibaca dari kode jawaban sesudah unit).
    for peran in ("designer", "driver", "md_quality", "qc"):
        for rute in ("GET /api/sales-incentives", "GET /api/sales-users"):
            assert sesudah[peran][rute] == 403, (peran, rute)
    for peran in PERAN_BAWAAN:
        boleh5 = peran in ("admin", "manager", "finance")   # K-FIN-01 — Finance setara Manajer
        assert (sesudah[peran]["GET /api/entities/ent_ksc"] == 200) is boleh5, peran
        assert (sesudah[peran]["GET /api/finance/period-unlocks"] == 200) is (peran in ("admin", "manager", "finance")), peran
        assert (sesudah[peran]["GET /api/purchase-orders/resolve-sourcing?product_id=x"] != 403) is boleh5, peran


@pytest.mark.skipif(TULIS_SEBELUM, reason="mode menulis berkas sebelum")
async def test_PRT3_U15_dasbor_manajer_sama(klien, sesi, db):
    await _fixture_u5(db)
    sebelum = json.loads(BERKAS_SEBELUM.read_text())["dasbor_manajer"]
    assert await _dasbor_manajer(klien, sesi) == sebelum
    assert sebelum["orders"] >= 1 and sebelum["customers"] >= 1   # fixture U5 ikut terhitung
