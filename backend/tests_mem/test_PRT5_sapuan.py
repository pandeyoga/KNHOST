"""PR-T5 U14 — sapuan kode jawaban 13 peran bawaan (docs/blueprint/unit/PR-T5.md).

`data/kode_sebelum_PRT5.json` dibuat dari kode SEBELUM unit ini (langkah kerja 1), di basis data tiruan baru, dengan
menjalankan modul ini ber-variabel lingkungan `KN_PRT5_TULIS_SEBELUM=1` (uji ditandai "dilewati" dan berkas ditulis).
Rute: enam `/api/reports/*`, empat endpoint baca inspeksi, `/api/users`, `/api/access/roles`, `/api/entities/x`,
`/api/scheduler/settings`, `/api/config/registry`. Id yang dipakai tidak ada (`tidak-ada`, `x`) sehingga tidak ada data
yang berubah. Sesudah unit: Admin dan Manajer sama di semua rute; selisih lain HANYA pada empat endpoint `/api/reports/*`
tabel 1 (kini `reports.view` menggantikan `order/product/warehouse.view`): 200 → 403 bagi peran bawaan yang tidak
memegang `reports.view`, dan — akibat langsung penggantian gerbang yang tidak disebut bunyi U14 — 403 → 200 bagi peran
bawaan yang memegang `reports.view` tetapi tidak memegang izin lama (hari ini: Finance pada
`/api/reports/warehouse-utilization`, dulu `warehouse.view`). Usulan koreksi bunyi U14 ada di laporan PR-T5.
Modul sendiri (basis data sendiri).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

import permissions_config

pytestmark = pytest.mark.anyio

BERKAS_SEBELUM = Path(__file__).parent / "data" / "kode_sebelum_PRT5.json"
TULIS_SEBELUM = os.environ.get("KN_PRT5_TULIS_SEBELUM") == "1"

PERAN_BAWAAN = ["admin", "sales", "manager", "sales_admin", "finance", "warehouse", "designer", "md",
                "warehouse_admin", "driver", "sample_admin", "md_quality", "qc"]

#: (metode, jalur). Empat pertama = endpoint laporan yang kini menuntut `reports.view` (tabel 1).
LAPORAN_BARU = ["/api/reports/summary", "/api/reports/warehouse-utilization", "/api/reports/stock-aging",
                "/api/reports/top-customers"]
RUTE: List[Tuple[str, str]] = [
    *[("GET", j) for j in LAPORAN_BARU],
    ("GET", "/api/reports/reservation-funnel"), ("GET", "/api/reports/order-velocity"),
    ("GET", "/api/inspections/meta"), ("GET", "/api/inspections"), ("GET", "/api/inspections/export"),
    ("GET", "/api/inspections/tidak-ada"),
    ("GET", "/api/users"), ("GET", "/api/access/roles"), ("GET", "/api/entities/x"),
    ("GET", "/api/scheduler/settings"), ("GET", "/api/config/registry"),
]


def _kunci(metode: str, jalur: str) -> str:
    return f"{metode} {jalur}"


#: Perubahan SAH sesudah PR-T5 oleh unit lain (bukan gerbang laporan): {(peran, rute): (lama, baru, alasan)}.
SESUDAH_PRT5 = {
    ("finance", "GET /api/config/registry"): (403, 200, (
        "PM-T2 — dua kunci pengaturan baru (`payment.wajib_cara_bayar_di_pesanan`, `payment.kode_bayar_awalan`) "
        "berizin `cash.configure`; Finance memegangnya, jadi katalog Pusat Pengaturan terbuka hanya untuk kunci yang "
        "boleh diubahnya (aturan KF-T1)")),
}


def _memegang_laporan(peran: str) -> bool:
    return "view" in (permissions_config.DEFAULT_PERMISSIONS.get(peran, {}).get("reports") or [])


async def sapu(klien, akun, sesi) -> Dict[str, Dict[str, int]]:
    """{peran: {"METODE jalur": kode}} untuk 13 peran bawaan (satu akun baru per peran, PT `ent_ksc`)."""
    out: Dict[str, Dict[str, int]] = {}
    for peran in PERAN_BAWAAN:
        h = await sesi(await akun(peran))
        out[peran] = {_kunci(m, j): (await klien.request(m, j, headers=h)).status_code for m, j in RUTE}
    return out


if TULIS_SEBELUM:   # hanya dikumpulkan dengan `KN_PRT5_TULIS_SEBELUM=1` (kode SEBELUM unit; langkah kerja 1)
    async def test_tulis_berkas_sebelum(klien, akun, sesi):
        isi = {"kode": await sapu(klien, akun, sesi)}
        BERKAS_SEBELUM.write_text(json.dumps(isi, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        pytest.skip(f"berkas sebelum ditulis: {BERKAS_SEBELUM.name}")


@pytest.mark.skipif(TULIS_SEBELUM, reason="mode menulis berkas sebelum")
async def test_PRT5_U14_kode_jawaban_peran_bawaan(klien, akun, sesi):
    sebelum = json.loads(BERKAS_SEBELUM.read_text())["kode"]
    sesudah = await sapu(klien, akun, sesi)
    assert sorted(sebelum) == sorted(PERAN_BAWAAN)
    laporan = {_kunci("GET", j) for j in LAPORAN_BARU}
    tak_sah, berubah = [], []
    for peran, rutes in sesudah.items():
        for rute, kode in rutes.items():
            lama = sebelum[peran][rute]
            if lama == kode:
                continue
            if SESUDAH_PRT5.get((peran, rute), (None, None))[:2] == (lama, kode):
                continue
            berubah.append((peran, rute, lama, kode))
            if peran in ("admin", "manager"):
                tak_sah.append((peran, rute, lama, kode, "Admin/Manajer harus sama"))
            elif rute in laporan:
                if _memegang_laporan(peran):
                    if not (lama == 403 and kode == 200):
                        tak_sah.append((peran, rute, lama, kode, "laporan: pemegang reports.view hanya boleh 403 → 200"))
                elif not (lama == 200 and kode == 403):
                    tak_sah.append((peran, rute, lama, kode, "laporan: hanya 200 → 403 tanpa reports.view"))
            else:
                tak_sah.append((peran, rute, lama, kode, "tidak boleh berubah"))
    assert not tak_sah, tak_sah
    # Bunyi U14: yang berubah memang peran tanpa `reports.view` yang dulu lolos lewat order/product/warehouse.view
    # (Sales, Gudang, MD, Admin Gudang, Admin Sample, dan lainnya).
    for peran in ("sales", "warehouse", "md", "warehouse_admin", "sample_admin"):
        assert any(b[0] == peran for b in berubah), (peran, "seharusnya kehilangan laporan Ringkasan")
        assert sesudah[peran]["GET /api/reports/summary"] == 403, peran
    for peran in PERAN_BAWAAN:   # empat endpoint laporan: terbuka TEPAT bagi pemegang `reports.view`
        for rute in laporan:
            assert (sesudah[peran][rute] == 200) is _memegang_laporan(peran), (peran, rute, sesudah[peran][rute])
    assert sorted(p for p in PERAN_BAWAAN if _memegang_laporan(p)) == ["admin", "finance", "manager", "sales_admin"]
    assert [b for b in berubah if b[3] == 200] == [("finance", "GET /api/reports/warehouse-utilization", 403, 200)]
