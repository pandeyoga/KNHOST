"""KA-1 — kunci Pusat Pengaturan pengali komisi (harga & capaian) + validasi nilai tabel.

Rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md`. Pembaca: `services/commission_rules.py`.
"""
from __future__ import annotations

import pytest

from services import config_resolver as resolver
from services.commission_rules import SUMBER_KHUSUS, aturan_capaian, aturan_pt, periksa_nilai
from services.config_resolver import value_of

pytestmark = pytest.mark.anyio


async def test_KA1_U1_bawaan_kunci(klien, kepala_admin):
    for key, bawaan in (("commission.price_basis", "diskon_baris"),
                        ("commission.price_bands", [{"sampai_pct": None, "pengali": 1.0}]),
                        ("commission.achievement_multiplier", False),
                        ("commission.achievement_basis", "omzet_bersih"),
                        ("commission.achievement_tiers", [{"capaian_min_pct": 0, "pengali": 1.0}])):
        assert await value_of(key, {"entity_id": "ent_ksc"}) == bawaan
    assert [r["cara"] for r in await value_of("commission.price_source_rules", {})] == ["ikut_pita"] * 3


def test_KA1_U2_pita_dinormalisasi():
    v = periksa_nilai("commission.price_bands", [{"sampai_pct": None, "pengali": 0}, {"sampai_pct": 10, "pengali": 0.5},
                                                 {"sampai_pct": 3, "pengali": 0.8}])
    assert v == [{"sampai_pct": 3, "pengali": 0.8}, {"sampai_pct": 10, "pengali": 0.5}, {"sampai_pct": None, "pengali": 0}]


@pytest.mark.parametrize("key,nilai", [
    ("commission.price_bands", []), ("commission.price_bands", [{"sampai_pct": 3, "pengali": 1}]),
    ("commission.price_bands", [{"sampai_pct": 3, "pengali": 1}, {"sampai_pct": 3, "pengali": 1}, {"sampai_pct": None, "pengali": 1}]),
    ("commission.price_bands", [{"sampai_pct": None, "pengali": -0.1}]),
    ("commission.price_source_rules", [{"sumber": "entity", "cara": "ikut_pita", "pengali": 1}]),
    ("commission.achievement_tiers", [{"capaian_min_pct": 80, "pengali": 1}])])
async def test_KA1_U3_nilai_tak_sah_400(klien, kepala_admin, key, nilai):
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json={"items": [{"key": key, "value": nilai, "scope_type": "global", "reason": "uji KA-1"}]})
    assert r.status_code == 400, r.text


async def test_KA1_U4_lapisan_pt(klien, kepala_admin):
    await resolver.set_value("commission.price_basis", "pricelist", scope_type="entity", scope_id="ent_kanda",
                             actor="uji", reason="uji KA-1")
    assert (await aturan_pt("ent_kanda"))["price_basis"] == "pricelist"
    assert (await aturan_pt("ent_ksc"))["price_basis"] == "diskon_baris"
    assert (await aturan_pt("ent_ksc", {"commission.price_basis": "pricelist"}))["price_basis"] == "pricelist"
    assert [r["sumber"] for r in (await aturan_pt("ent_ksc"))["price_source_rules"]] == list(SUMBER_KHUSUS)


async def test_KA1_U5_aturan_capaian_bawaan(klien, kepala_admin):
    assert await aturan_capaian("ent_ksc") == {"aktif": False, "basis": "omzet_bersih",
                                               "jenjang": [{"capaian_min_pct": 0, "pengali": 1.0}]}
