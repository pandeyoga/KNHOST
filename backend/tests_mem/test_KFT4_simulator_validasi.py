"""KF-T4 — "Coba dulu" sama dengan mesin dan isi daftar/tabel/rujukan divalidasi: U8–U11 + pelengkap
(docs/blueprint/unit/KF-T4.md).

`kepala_admin` = admin seed (lintas PT). PT seed `ent_ksc` (PKP) dan `ent_kanda` (bukan PKP). Master Grade Mutu seed:
A, A1, A2, B, B1, C, BS aktif tanpa batas poin sendiri (`domain_registry.GRADES`).
"""
from __future__ import annotations

import pytest

import config_registry as registry

pytestmark = pytest.mark.anyio

POLA_BAWAAN = ["(?P<core>\\d{3,5})/(CST|SCB)/\\d{4}", "[A-Z]+/PO-(?P<core>\\d+)"]


def _put(key, value, *, scope_type="global", scope_id="", reason="uji KF-T4"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id,
                       "reason": reason}]}


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


# ── U8 — "Coba dulu" grade QC = mesin (A/A1/A2/B dari batas A–B dibagi tiga, grade aktif terakhir di atas B) ─────────
async def test_KFT4_U8_coba_dulu_grade_sama_dengan_mesin(klien, kepala_admin):
    from services.qc_inspection_service import grade_from_points, thresholds_from
    ov = {"qc.grade_thresholds.a_max": 20, "qc.grade_thresholds.b_max": 40}
    # Hitungan: rentang 20–40 dibagi tiga → A1 ≤ 26,67, A2 ≤ 33,33, B ≤ 40. 25 → A1; 45 > 40 → grade aktif terakhir
    # (BS; B1 dan C tanpa batas poin dilewati); 18 ≤ 20 → A.
    assert thresholds_from(20, 40) == {"a_max": 20.0, "a1_max": 26.67, "a2_max": 33.33, "b_max": 40.0}
    for poin, grade in ((25, "A1"), (45, "BS"), (18, "A")):
        r = await klien.post("/api/config/simulate", headers=kepala_admin,
                             json={"key": "qc.grade_thresholds.a_max", "overrides": ov, "sample": {"points": poin}})
        assert r.status_code == 200, r.text
        assert r.json()["result"] == f"Grade {grade}", r.json()
        assert grade_from_points(poin, thresholds_from(20, 40)) == grade


# ── U9 — "Coba dulu" pajak = mesin; PKP dari profil PT, bukan sakelar e-Faktur ──────────────────────────────────────
async def test_KFT4_U9_coba_dulu_pajak_pkp_dari_profil_pt(klien, kepala_admin):
    from services.config_service import ppn_breakdown
    ov = {"tax.ppn_rate": 12, "tax.dpp_nilai_lain": True, "tax.ppn_mode": "excluded", "tax.efaktur_enabled": False}
    hasil = {}
    for ent in ("ent_ksc", "ent_kanda"):
        r = await klien.post("/api/config/simulate", headers=kepala_admin,
                             json={"key": "tax.ppn_rate", "ctx": {"entity_id": ent}, "overrides": ov,
                                   "sample": {"subtotal": 10_000_000}})
        assert r.status_code == 200, r.text
        hasil[ent] = r.json()
        assert "tax.efaktur_enabled" not in {x["key"] for x in r.json()["resolved"]}
    # ent_ksc PKP: 10.000.000 × 12% × 11/12 = 1.100.000 → total 11.100.000.
    b = hasil["ent_ksc"]["breakdown"]
    assert (b["ppn_amount"], b["grand_total"]) == (1_100_000.0, 11_100_000.0)
    assert b == ppn_breakdown(10_000_000, 12, "excluded", True, True)
    # ent_kanda bukan PKP: tanpa PPN.
    b = hasil["ent_kanda"]["breakdown"]
    assert (b["ppn_amount"], b["grand_total"]) == (0.0, 10_000_000.0)
    assert b == ppn_breakdown(10_000_000, 12, "excluded", False, True)
    assert "tanpa PPN" in hasil["ent_kanda"]["result"]


async def test_KFT4_U9b_compute_tax_memakai_rumus_yang_sama():
    from services import config_service
    assert (await config_service.compute_tax(10_000_000, "ent_ksc")) == config_service.ppn_breakdown(
        10_000_000, 12.0, "excluded", True, True)


# ── U10 — isi daftar divalidasi; pesan memakai label ─────────────────────────────────────────────────────────────────
async def test_KFT4_U10_isi_daftar_divalidasi(klien, kepala_admin):
    h = kepala_admin
    r = await klien.put("/api/config/values", headers=h, json=_put("receiving.client_po_patterns", POLA_BAWAAN))
    assert r.status_code == 200, r.text
    r = await klien.put("/api/config/values", headers=h, json=_put("receiving.client_po_patterns", ["("]))
    assert r.status_code == 400, r.text
    for nilai in ([30, 20], ["a"]):
        r = await klien.put("/api/config/values", headers=h, json=_put("ar.aging_buckets", nilai))
        assert r.status_code == 400, (nilai, r.text)
        assert "'Kelompok umur piutang (hari)'" in _detail(r), _detail(r)
    r = await klien.put("/api/config/values", headers=h, json=_put("ar.aging_buckets", [14, 30, 60]))
    assert r.status_code == 200, r.text
    r = await klien.put("/api/config/values", headers=h, json=_put("allocation.priority_order", ["lot", "owner"]))
    assert r.status_code == 400, r.text
    assert "harus di urutan pertama" in _detail(r)
    r = await klien.put("/api/config/values", headers=h,
                        json=_put("allocation.priority_order", ["owner", "lot", "lot"]))
    assert r.status_code == 400 and "dua kali" in _detail(r)
    # `ai.margin_roles` kini `not_used` (Peran & Hak Akses, PR-T2/KP-T4): PUT ditolak karena tidak dipakai —
    # pemeriksa butir peran diuji langsung (usulan koreksi U10 di laporan).
    r = await klien.put("/api/config/values", headers=h, json=_put("ai.margin_roles", ["admin", "manager"]))
    assert r.status_code == 400 and "tidak dipakai" in _detail(r)
    e = registry.get("ai.margin_roles")
    with pytest.raises(ValueError, match="'Manager' tidak dikenal"):
        registry.coerce(e, ["admin", "Manager"])
    assert registry.coerce(e, ["admin", "manager"]) == ["admin", "manager"]


async def test_KFT4_U10b_pesan_batas_angka_memakai_label_dan_satuan(klien, kepala_admin):
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_put("ar.grace_days", -1))
    assert r.status_code == 400, r.text
    lab = registry.get("ar.grace_days")["label"]
    assert _detail(r) == f"'{lab}' paling kecil 0 hari."
    assert "ar.grace_days" not in _detail(r)


# ── U11 — tabel berkelompok `approval.extra_levels` ──────────────────────────────────────────────────────────────────
async def test_KFT4_U11_tabel_berkelompok_jenjang_tambahan(klien, kepala_admin):
    e = registry.get("approval.extra_levels")
    sah = {"purchase_order": [{"min_amount": 500000000, "role": "admin", "label": "Direksi"}]}
    assert registry.coerce(e, sah) == sah
    with pytest.raises(ValueError, match="'owner' tidak dikenal"):
        registry.coerce(e, {"purchase_order": [{"min_amount": 500000000, "role": "owner", "label": "Direksi"}]})
    with pytest.raises(ValueError, match="'faktur' tidak dikenal"):
        registry.coerce(e, {"faktur": []})
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": "approval.extra_levels"})
    it = next(x for x in r.json()["items"] if x["key"] == "approval.extra_levels")
    assert it["row_shape"] == "grouped_list"
    assert [c["name"] for c in it["columns"]] == ["doc_type", "min_amount", "role", "label"]
    # Kunci ini `not_used` sejak KP-T3/KP-T4 (Aturan Persetujuan): PUT tetap ditolak dengan alasannya.
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_put("approval.extra_levels", sah))
    assert r.status_code == 400 and "tidak dipakai" in _detail(r)


# ── pelengkap — rujukan master (syarat bayar · satuan) ───────────────────────────────────────────────────────────────
async def test_KFT4_rujukan_master_dipilih_dari_daftar(klien, kepala_admin):
    h = kepala_admin
    r = await klien.get("/api/config/effective", headers=h, params={"q": "finance.default_payment_term_code"})
    it = next(x for x in r.json()["items"] if x["key"] == "finance.default_payment_term_code")
    assert it["ref"] == "payment_term"
    kode = {o["value"] for o in it["ref_options"]}
    assert "NET30" in kode
    r = await klien.put("/api/config/values", headers=h, json=_put("finance.default_payment_term_code", "NET999"))
    assert r.status_code == 400 and "'NET999' tidak dikenal" in _detail(r)
    r = await klien.put("/api/config/values", headers=h, json=_put("finance.default_payment_term_code", "NET30"))
    assert r.status_code == 200, r.text
    r = await klien.put("/api/config/values", headers=h, json=_put("inventory.default_uom", "parsec"))
    assert r.status_code == 400
    r = await klien.put("/api/config/values", headers=h, json=_put("inventory.default_uom", "yard"))
    assert r.status_code == 200, r.text
