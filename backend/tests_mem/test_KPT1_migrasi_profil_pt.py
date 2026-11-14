"""KP-T1 — skrip `scripts/migrate_kpt1_profil_pt.py` (docs/blueprint/unit/KP-T1.md, bagian Data › Migrasi).

Modul sendiri (basis data bersih). Skrip HANYA dijalankan di database tiruan ini (titik henti H3: data nyata = keputusan
pemilik). Fixture disisipkan langsung: tiga PT berbentuk lama (dengan `fiscal_year_start`/`currency` di master).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
SKRIP = ROOT / "scripts/migrate_kpt1_profil_pt.py"


def _skrip():
    spec = importlib.util.spec_from_file_location("migrate_kpt1_profil_pt", SKRIP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def test_KPT1_migrasi_lapor_lalu_tulis(db):
    mod = _skrip()
    assert mod.main(["--salah"]) == 2                    # argumen tak dikenal: keluar sebelum menyentuh basis data
    assert mod.main(["--apply", "--dry-run"]) == 2
    lama = {"type": "PT", "status": "active", "default_tax_mode": "non_ppn", "is_group": False,
            "coa_template": "id_standard", "incentive_payer": "sales_entity", "numbering_scheme": "per_entity_prefix",
            "parent_entity_id": ""}
    await db.business_entities.insert_many([
        # A: tahun buku tersirat April–Maret (bulan akhir 3 ≠ 12), USD ≠ IDR, NPWP 5 digit, belum punya persen
        {**lama, "id": "ent_uji_mig_a", "legal_name": "PT Mig A", "short_name": "MIGA", "doc_prefix": "MIGA",
         "fiscal_year_start": "04-01", "currency": "USD", "npwp": "12.345"},
        # B: sama dengan registry, NPWP 16 digit, persen sudah diisi 60 (tidak ditimpa)
        {**lama, "id": "ent_uji_mig_b", "legal_name": "PT Mig B", "short_name": "MIGB", "doc_prefix": "MIGB",
         "fiscal_year_start": "01-01", "currency": "IDR", "npwp": "1234567890123456", "ownership_pct": 60.0},
        # C: tahun fiskal tidak terbaca ("13-45" dulu lolos validasi), NPWP kosong (non-PKP, boleh)
        {**lama, "id": "ent_uji_mig_c", "legal_name": "PT Mig C", "short_name": "MIGC", "doc_prefix": "MIGC",
         "fiscal_year_start": "13-45", "currency": "IDR", "npwp": ""},
    ])

    lapor = await mod.jalankan(tulis=False)
    assert lapor["mode"] == "lapor"
    assert lapor["isi_kepemilikan"] == ["ent_uji_mig_a", "ent_uji_mig_c"]          # seed sudah membawa 100
    assert [(t["entity_id"], t["bulan_tersirat"], t["bulan_registry"]) for t in lapor["tahun_buku_beda"]] == [
        ("ent_uji_mig_a", 3, 12)]
    assert [t["entity_id"] for t in lapor["tahun_buku_tak_terbaca"]] == ["ent_uji_mig_c"]
    assert [(m["entity_id"], m["currency"], m["base_currency"]) for m in lapor["mata_uang_beda"]] == [
        ("ent_uji_mig_a", "USD", "IDR")]
    assert [n["entity_id"] for n in lapor["npwp_salah"]] == ["ent_uji_mig_a"]
    assert await db.business_entities.count_documents({"ownership_pct": {"$exists": False}}) == 2   # lapor: tak menulis
    cetak: list = []
    mod._cetak(lapor, cetak.append)
    print("\n".join(cetak))                              # bukti laporan (`-s`)
    assert any("Persen kepemilikan diisi 100: 2 PT" in c for c in cetak), cetak

    tulis = await mod.jalankan(tulis=True)
    mod._cetak(tulis)
    assert (tulis["mode"], tulis["ditulis"]) == ("tulis", 2)
    a = await db.business_entities.find_one({"id": "ent_uji_mig_a"}, {"_id": 0})
    b = await db.business_entities.find_one({"id": "ent_uji_mig_b"}, {"_id": 0})
    assert a["ownership_pct"] == 100.0 and b["ownership_pct"] == 60.0
    # field lama tidak dihapus (00 §7 butir 2) dan registry TIDAK disalin (mesin sudah memakai registry)
    assert (a["fiscal_year_start"], a["currency"], a["numbering_scheme"]) == ("04-01", "USD", "per_entity_prefix")
    assert await db.config_values.count_documents({"scope_id": "ent_uji_mig_a"}) == 0

    ulang = await mod.jalankan(tulis=True)
    assert ulang["ditulis"] == 0 and ulang["isi_kepemilikan"] == []
