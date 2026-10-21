"""F-04 (uji pra-UAT 2026-10-21) — KPI POS "Jml Tersedia/Dipesan" tidak menjumlahkan yard + kg.

Reproduksi: kartu *Jml Tersedia* = Σ available_qty semua produk tanpa melihat satuan (yard woven + kg knit dalam satu
angka). Kini `/api/dashboard` juga mengirim rincian per satuan (`available_by_unit`, `reserved_by_unit`) + jumlah roll
tersedia, dan layar menampilkan "… yard · … kg".
Jalankan: cd /app/backend && python -m pytest tests/test_f04_pos_kpi_units.py -p no:randomly -n 0 -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402

DB = base.DB


def test_kpi_stok_dirinci_per_satuan_dan_konsisten_dengan_total():
    api = base.Api("admin@kainnusantara.id")
    c, d = api.call("GET", "/dashboard")
    assert c == 200, d
    m = d["metrics"]
    by = m.get("available_by_unit")
    assert isinstance(by, dict) and by, m                                  # dulu: tidak ada rincian
    assert set(by) <= {"yard", "kg", "meter", "lainnya", "pcs"}, by
    # Σ per satuan = angka total lama (yang kini hanya dipakai sebagai cadangan) — tidak ada yang hilang/terhitung dua kali
    assert abs(sum(by.values()) - m["available_qty"]) < 0.05 * max(1.0, m["available_qty"]), (by, m["available_qty"])
    units = {p["base_unit"] for p in DB.products.find({"base_unit": {"$in": ["yard", "kg"]}}, {"_id": 0, "base_unit": 1})}
    if {"yard", "kg"} <= units and len(by) >= 2:
        assert "yard" in by and "kg" in by                                 # data acuan memuat woven & knit
    assert isinstance(m.get("available_rolls"), int) and m["available_rolls"] > 0, m
    assert isinstance(m.get("reserved_by_unit"), dict), m
