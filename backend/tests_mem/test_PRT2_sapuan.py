"""PR-T2 U12 — sapuan kode jawaban 13 peran bawaan (docs/blueprint/unit/PR-T2.md).

`data/kode_sebelum_PRT2.json` dibuat dari kode SEBELUM unit ini (langkah kerja 1), di basis data tiruan baru:
kode jawaban tiap (peran bawaan, rute) untuk semua rute GET di tabel "Endpoint" dan "Gerbang di dalam handler", dan untuk
POST yang ditolak/gagal sebelum mengubah data (id tidak ada) serta dua POST yang disebut U12. Sesudah unit, kode jawaban
harus SAMA — tidak ada peran bawaan yang kehilangan (atau mendapat) akses saat gerbang nama peran diganti izin.
Modul sendiri (basis data sendiri): uji lain yang mengubah izin tidak memengaruhi sapuan ini.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

pytestmark = pytest.mark.anyio

BERKAS_SEBELUM = Path(__file__).parent / "data" / "kode_sebelum_PRT2.json"

PERAN_BAWAAN = ["admin", "sales", "manager", "sales_admin", "finance", "warehouse", "designer", "md",
                "warehouse_admin", "driver", "sample_admin", "md_quality", "qc"]

RUTE: List[Tuple[str, str, Optional[Dict[str, Any]]]] = [
    # ── Tabel "Endpoint" (dulu `require_role`) — semua GET ──
    ("GET", "/api/sales/leaderboard", None),
    ("GET", "/api/sales/incentive/gl-status?period=2026-10", None),
    ("GET", "/api/incentive-rates", None),
    ("GET", "/api/costing/wac", None),
    ("GET", "/api/costing/wac/prd_tidak_ada", None),
    ("GET", "/api/home/admin", None),
    ("GET", "/api/home/manager", None),
    ("GET", "/api/data-hygiene/summary", None),
    ("GET", "/api/data-hygiene/log", None),
    ("GET", "/api/data-hygiene/preview", None),
    ("GET", "/api/data-hygiene/unverified-locations", None),
    ("GET", "/api/turn-notifications/map", None),
    ("GET", "/api/saga-locks", None),
    ("GET", "/api/saga-locks/sales_orders/so_tidak_ada/inspect", None),
    ("GET", "/api/ai/facts/status", None),
    ("GET", "/api/ai/snapshots/status", None),
    ("GET", "/api/ai/usage", None),
    # ── Tabel "Gerbang di dalam handler" — GET ──
    ("GET", "/api/internal-requests/pin_tidak_ada/sources", None),
    ("GET", "/api/rnd/divisions", None),
    ("GET", "/api/rnd/divisions/members", None),
    ("GET", "/api/rnd/reports/designer-kpi", None),
    ("GET", "/api/rnd/reports/designer-kpi/trend", None),
    ("GET", "/api/rnd/sla/board", None),
    ("GET", "/api/ai/status", None),
    ("GET", "/api/ai/templates", None),
    ("GET", "/api/ai/catalog", None),
    ("GET", "/api/ai/usage/daily", None),
    ("GET", "/api/ai/sessions", None),
    ("GET", "/api/ai/sessions/aichat_tidak_ada", None),
    ("GET", "/api/ai/results/res_tidak_ada", None),
    ("GET", "/api/ai/my-templates", None),
    ("GET", "/api/ai/schedules", None),
    ("GET", "/api/ai/schedule-runs", None),
    ("GET", "/api/ai/insights", None),
    ("GET", "/api/ai/actions/aiact_tidak_ada", None),
    # ── POST: dua yang disebut U12 + yang gagal di id tidak ada (tanpa efek samping) ──
    ("POST", "/api/data-hygiene/run", None),
    ("POST", "/api/rfid/devices/seed-defaults", None),
    ("POST", "/api/handheld/devices/hh_tidak_ada/revoke", {"reason": "uji sapuan PR-T2"}),
    ("POST", "/api/handheld/devices/hh_tidak_ada/enable", None),
    ("POST", "/api/handheld/devices/hh_tidak_ada/rotate-key", None),
    ("POST", "/api/saga-locks/sales_orders/so_tidak_ada/release", {"reason": "uji sapuan PR-T2"}),
    ("POST", "/api/data-hygiene/log/log_tidak_ada/revert", None),
    ("POST", "/api/ai/insights/scan", None),
]


async def sapu(klien, akun, sesi) -> Dict[str, Dict[str, int]]:
    """{peran: {"METODE jalur": kode}} untuk 13 peran bawaan (satu akun baru per peran, PT `ent_ksc`)."""
    out: Dict[str, Dict[str, int]] = {}
    for peran in PERAN_BAWAAN:
        h = await sesi(await akun(peran))
        kode: Dict[str, int] = {}
        for metode, jalur, isi in RUTE:
            r = await klien.request(metode, jalur, headers=h, json=isi)
            kode[f"{metode} {jalur}"] = r.status_code
        out[peran] = kode
    return out


async def test_U12_kode_jawaban_peran_bawaan_sama_dengan_sebelum(klien, akun, sesi):
    sebelum = json.loads(BERKAS_SEBELUM.read_text())
    sesudah = await sapu(klien, akun, sesi)
    assert sorted(sebelum) == sorted(PERAN_BAWAAN)
    beda = [(p, rute, sebelum[p].get(rute), k) for p, rutes in sesudah.items() for rute, k in rutes.items()
            if sebelum[p].get(rute) != k]
    assert not beda, beda
    # Manajer: 200 di semua rute manajer; 403 di rute yang hanya Admin (bunyi U12).
    m = sesudah["manager"]
    for rute in ("GET /api/costing/wac", "GET /api/home/manager", "GET /api/sales/leaderboard",
                 "GET /api/incentive-rates", "GET /api/data-hygiene/summary", "GET /api/ai/usage"):
        assert m[rute] == 200, rute
    for rute in ("GET /api/saga-locks", "POST /api/data-hygiene/run", "POST /api/rfid/devices/seed-defaults"):
        assert m[rute] == 403, rute
