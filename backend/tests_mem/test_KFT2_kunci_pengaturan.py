"""KF-T2 — kunci pengaturan yang mati, ganda, dan tersembunyi (docs/blueprint/unit/KF-T2.md), uji U2–U12 dan U14.

U13 (skrip pindahan akun bank) ada di `test_KFT2_migrasi_akun_bank.py` — modul sendiri supaya basis datanya bersih dari
pemetaan akun yang ditulis U12. U1 (gate `scripts/audit_config_wiring.py --strict` / `--self-test`) dijalankan di luar
pytest; U15 = uji jalan layar.

Peran: `adm` = admin seed (lintas PT). PT seed `ent_ksc` (PKP) dan `ent_kanda`. Satu basis data per modul; nilai yang
diubah satu uji tidak dipakai uji lain kecuali disebut (U3 → U4 memakai kunci yang sama di lapisan berbeda).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import config_registry as registry

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

RETUR = ("sales_return", "policy")
PT = ("entity", "update")
#: Tabel "Kunci baru" spesifikasi: key → (group, type, default, min, max, unit, permission)
BARU = {
    "returns.customer_window_days": ("retur", "duration", 21, 1, 365, "hari", RETUR),
    "returns.supplier_window_days": ("retur", "duration", 21, 1, 365, "hari", RETUR),
    "returns.supplier_reminder_days": ("retur", "duration", 3, 0, 60, "hari", RETUR),
    "returns.bill_first": ("retur", "bool", True, None, None, "", RETUR),
    "returns.grade_price_factors": ("retur", "table",
                                    {"A": 100, "A1": 95, "A2": 90, "B": 70, "B1": 60, "C": 40, "BS": 10},
                                    None, None, "", RETUR),
    "interco_payment.allow_netting": ("antar-entitas", "bool", False, None, None, "", PT),
    "interco_payment.require_full_payment": ("antar-entitas", "bool", True, None, None, "", PT),
    "interco_payment.cutoff_day": ("antar-entitas", "int", 0, 0, 31, "tanggal", PT),
    "interco_payment.payment_day": ("antar-entitas", "int", 0, 0, 31, "tanggal", PT),
    "interco_payment.basis": ("antar-entitas", "enum", "", None, None, "", PT),
    "interco_payment.reminder_days": ("antar-entitas", "duration", 3, 0, 30, "hari", PT),
}
AKUN_PEMETAAN = "Akun ini diatur di Pengaturan › Keuangan & Pajak › Pemetaan Akun."
#: Tabel "Kunci yang ditandai not_used" spesifikasi: key → alasan yang tampil.
TIDAK_DIPAKAI = {
    "contra_bon.qty_tolerance_percent":
        "Toleransi jumlah kontrabon mengikuti pengaturan 'Toleransi jumlah tagihan pemasok'.",
    # KP-T5 — alasan ditambah kalimat tempat format lot kini diatur (tabel Penomoran Dokumen, jenis `lot`).
    "lot.number_format":
        "Nomor lot saat ini selalu berbentuk KODE-PT/LOT-TTBB-urutan. Format yang bisa diatur menyusul bersama "
        "penomoran dokumen. Diatur di Pengaturan › Dokumen & Cetak › Penomoran Dokumen.",
    "bank.holding_account_code": AKUN_PEMETAAN,
    "bank.charge_account_code": AKUN_PEMETAAN,
    "bank.interest_account_code": AKUN_PEMETAAN,
}
#: Nilai yang dikirim U9 (sah menurut tipenya — yang ditolak harus statusnya, bukan isinya).
NILAI_U9 = {"contra_bon.qty_tolerance_percent": 2, "lot.number_format": "LOT-YYMM-#####",
            "bank.holding_account_code": "2-1951", "bank.charge_account_code": "6-8100",
            "bank.interest_account_code": "4-9050"}


def _put(key, value, scope_type="entity", scope_id="ent_ksc", reason="uji KF-T2"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]}


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


# ── U2 — registry ────────────────────────────────────────────────────────────
def test_KFT2_U2_sebelas_kunci_baru_dan_lima_tidak_dipakai():
    for key, (group, typ, default, lo, hi, unit, perm) in BARU.items():
        e = registry.get(key)
        assert e is not None, f"{key} belum terdaftar"
        # KF-T4 — kelompok lama spesifikasi KF-T2 (`retur`, `antar-entitas`) kini alias kelompok baru (`GROUP_ALIASES`).
        group = registry.resolve_group_id(group)[0]
        assert (e["group"], e["type"], e["default"], e["min"], e["max"], e["unit"]) == (group, typ, default, lo, hi, unit), key
        assert tuple(e["permission"]) == perm, key
        assert e["scopes"] == ["global", "entity"], key
        assert e["sensitif_baca"] is False, key
        assert e["risk"] == "medium" and e["status"] == "active" and e["consumers"], key
        assert e["impact"] and e["example"], key
        assert len(e["label"]) <= 45, (key, len(e["label"]))
    assert registry.get("returns.grade_price_factors")["row_shape"] == "map"
    assert [o["value"] for o in registry.get("interco_payment.basis")["options"]] == ["", "receipt", "invoice", "document"]
    for key, alasan in TIDAK_DIPAKAI.items():
        e = registry.get(key)
        assert e["status"] == "not_used", key
        assert e["not_used_reason"] == alasan, key
    assert not registry.get("contra_bon.qty_tolerance_percent")["label"].startswith("(Lama)")
    assert registry.get("lot.number_format")["simulate"] == ""


# ── U3 — lapisan PT lewat Pusat Pengaturan ────────────────────────────────────
async def test_KFT2_U3_batas_retur_per_pt_lewat_pusat_pengaturan(klien, kepala_admin):
    from services.return_policy_service import return_assumptions
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_put("returns.customer_window_days", 30))
    assert r.status_code == 200, r.text
    assert (await return_assumptions("ent_ksc"))["customer_window_days"] == 30
    assert (await return_assumptions("ent_kanda"))["customer_window_days"] == 21
    h = await klien.get("/api/config/history", headers=kepala_admin, params={"key": "returns.customer_window_days"})
    assert h.status_code == 200, h.text
    assert h.json()["total"] == 1


# ── U4 — nilai jalur lama terbaca sebagai lapisan "pengaturan lama" ──────────
async def test_KFT2_U4_nilai_lama_terbaca_sebagai_lapisan_lama(klien, kepala_admin, db):
    from services.return_policy_service import return_assumptions
    # Fixture (sisip langsung): nilai yang dulu ditulis `PUT /api/settings` ke dokumen grup.
    await db.system_settings.update_one({"scope": "global"}, {"$set": {"returns.customer_window_days": 14}})
    assert (await return_assumptions(""))["customer_window_days"] == 14
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": "returns.customer_window_days"})
    assert r.status_code == 200, r.text
    items = [it for it in r.json()["items"] if it["key"] == "returns.customer_window_days"]
    assert len(items) == 1, r.json()
    item = items[0]
    assert item["value"] == 14
    assert item["source_layer"] == "legacy_global"


# ── U5 — harga per grade dipakai apa adanya ──────────────────────────────────
async def test_KFT2_U5_harga_per_grade_dari_pusat_pengaturan(klien, kepala_admin):
    from services.return_grade_impairment import compute, grade_factors
    tabel = {"A": 100, "A1": 95, "A2": 90, "B": 50, "B1": 60, "C": 40, "BS": 10}
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_put("returns.grade_price_factors", tabel, "global", ""))
    assert r.status_code == 200, r.text
    assert (await grade_factors(""))["B"] == 50.0
    # Hitung tangan: grade A (100 %) → B (50 %) = turun 50 % × harga daftar 100.000 = 50.000 per satuan; nilai buku
    # 80.000 lebih besar, jadi kerugian tidak dibatasi nilai buku → 50.000 × 2 satuan = 100.000.
    assert compute(100000, 80000, 100, 50, 2)["amount"] == 100000.0


# ── U6/U7 — jadwal bayar antar-PT ────────────────────────────────────────────
async def test_KFT2_U6_saling_hapus_hanya_untuk_pt_itu(klien, kepala_admin):
    from services.interco_service import payment_settings
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_put("interco_payment.allow_netting", True))
    assert r.status_code == 200, r.text
    assert (await payment_settings("ent_ksc"))["allow_netting"] is True
    assert (await payment_settings("ent_kanda"))["allow_netting"] is False


async def test_KFT2_U7_bawaan_jadwal_bayar_sama_dengan_hari_ini():
    from services.interco_service import payment_settings
    s = await payment_settings("")
    assert s["cutoff_day"] is None and s["payment_day"] is None and s["basis"] is None
    assert s["reminder_days"] == 3
    assert s["require_full_payment"] is True


# ── U8 — jalur lama dimatikan ────────────────────────────────────────────────
async def test_KFT2_U8_put_settings_lama_410_tanpa_menulis(klien, kepala_admin, db):
    sebelum = await db.system_settings.find_one({"scope": "global"}, {"_id": 0})
    r = await klien.put("/api/settings", headers=kepala_admin,
                        json={"scope": "global", "returns": {"customer_window_days": 5}})
    assert r.status_code == 410, r.text
    assert _detail(r) == "Pengaturan kini disimpan lewat Pusat Pengaturan."
    assert await db.system_settings.find_one({"scope": "global"}, {"_id": 0}) == sebelum


# ── U9 — kunci tidak dipakai ditolak dengan alasannya ────────────────────────
async def test_KFT2_U9_kunci_tidak_dipakai_ditolak_dengan_alasan(klien, kepala_admin):
    for key, alasan in TIDAK_DIPAKAI.items():
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_put(key, NILAI_U9[key], "global", ""))
        assert r.status_code == 400, (key, r.text)
        assert alasan in _detail(r), (key, _detail(r))


# ── U10 — cadangan saat dokumen pengaturan tidak lengkap = bawaan registry ───
async def test_KFT2_U10_cadangan_sama_dengan_bawaan_registry():
    from services.ar_aging_service import _denda_estimate
    from services.config_service import compute_order_pricing
    from services.so_approvals import require_validation_default
    harga = await compute_order_pricing([{"price": 100, "quantity": 1, "discount_percent": 10}],
                                        settings={"sales": {}, "tax": {}})
    assert harga["items_discount_total"] == 0.0          # sales.allow_item_discount bawaan False
    assert require_validation_default({}) is False        # sales.require_so_validation bawaan False
    # Hitung tangan: 2 % per bulan (bawaan) × ceil(30 hari / 30) = 1 bulan × 1.000.000 = 20.000.
    assert _denda_estimate(1000000, 30, {}) == 20000.0


async def test_KFT2_U10b_tujuh_cadangan_lain_sama_dengan_bawaan_registry(monkeypatch):
    """Baris lain tabel KF-06 (pelengkap U10): dokumen pengaturan tanpa kunci → perilaku = bawaan registry."""
    from services import approval_matrix_service as am
    from services import config_service as cs
    from services.roll_service import _build_allocation_plan, _explain_allocation
    from services.sales_force_service import _discount_factor

    async def _tanpa_isi(entity_id=None):
        return {"scope": "all", "tax": {"is_pkp": True}, "allocation": {}, "inventory": {}}
    monkeypatch.setattr(cs, "get_effective_settings", _tanpa_isi)
    # tax.ppn_rate 12 + tax.dpp_nilai_lain benar: DPP 11/12 × 1.200.000 = 1.100.000; PPN 12 % × 1.100.000 = 132.000.
    pajak = await cs.compute_tax(1200000)
    assert (pajak["ppn_rate"], pajak["dpp_nilai_lain"], pajak["ppn_amount"]) == (12.0, True, 132000.0)
    # inventory.intercompany_transfer_required bawaan benar → stok PT lain tidak boleh dipakai diam-diam.
    assert (await cs.get_allocation_policy())["allow_intercompany"] is False
    # commission.discount_threshold 10 (diskon 8 % tidak kena) dan commission.discount_factor 0,5 (diskon 15 %).
    baris = {"quantity": 1, "price": 100, "line_total": 92, "discount_percent": 8}
    assert _discount_factor({}, baris, 1000) == (1000, 1.0)
    assert _discount_factor({}, {**baris, "line_total": 85, "discount_percent": 15}, 1000) == (1000, 0.5)
    # allocation.lot_selection bawaan "fifo" (juga kalimat penjelasan alokasi — tambahan di luar tabel KF-06).
    assert _build_allocation_plan([], 0, "", {}, {})["lot_selection"] == "fifo"
    assert "(FIFO)" in _explain_allocation(1, ["L1"], {"name": "Gudang A"}, "ent_ksc", "single", {}, {})
    # approval.po_custom_direksi_min 50 jt: PO Custom 10 jt hanya satu tingkat (Manajer), 60 jt naik ke Direksi.
    # KP-T4 — kunci ini kini hanya membentuk baris BAWAAN Aturan Persetujuan (jenis `special_order`, dibaca lewat resolver
    # → bawaan registry bila tidak diisi) dan `evaluate` menjadi asinkron; yang diuji tetap: tanpa isian = 50 jt.
    assert (await am.evaluate("po_custom", {"role": "manager"}, {"total_amount": 10000000}, {}))["levels_total"] == 1
    assert (await am.evaluate("po_custom", {"role": "manager"}, {"total_amount": 60000000}, {}))["levels_total"] == 2


# ── U11 — rujukan pemakai menunjuk fungsi yang ada ───────────────────────────
def _fungsi(berkas: Path) -> set:
    pohon = ast.parse(berkas.read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(pohon) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_KFT2_U11_kesehatan_konfigurasi_tanpa_rujukan_rusak(monkeypatch):
    from services import config_health
    # Jalur bawaan modul = `/app/...`; uji membaca kode di salinan kerja ini.
    monkeypatch.setattr(config_health, "BACKEND", str(BACKEND))
    monkeypatch.setattr(config_health, "FRONTEND", str(ROOT / "frontend/src"))
    rep = config_health.report()
    assert [(b["key"], b["wiring_status"]) for b in rep["broken"]] == []
    baris = {r["key"]: r for r in rep["rows"]}
    for key in ("case.sla_hours", "case.sla_hours_high", "ai.route_threshold_pct"):
        assert baris[key]["wiring_status"] == "OK", key
        for ref in registry.get(key)["consumers"]:
            berkas, _, fn = ref.partition(":")
            assert fn in _fungsi(BACKEND / berkas), (key, ref)


# ── U12 — akun rekonsiliasi bank dari Pemetaan Akun ──────────────────────────
async def test_KFT2_U12_akun_biaya_bank_dari_pemetaan_akun(klien, kepala_admin):
    from services import bank_recon_service as brs
    r = await klien.post("/api/gl/accounts", headers=kepala_admin, params={"entity_id": "ent_ksc"},
                         json={"code": "6-8100", "name": "Beban Bank Uji KF-T2", "type": "expense",
                               "parent_code": "6-0000"})
    assert r.status_code == 200, r.text
    r = await klien.put("/api/gl/account-mappings/kas_bank.beban_bank", headers=kepala_admin,
                        json={"account_code": "6-8100", "entity_id": "ent_ksc", "reason": "uji KF-T2 akun biaya bank"})
    assert r.status_code == 200, r.text
    assert (await brs.load_cfg("ent_ksc"))["charge_acc"] == "6-8100"
    assert (await brs.load_cfg("ent_kanda"))["charge_acc"] == "6-8000"


# ── U14 — tidak ada layar yang menulis `PUT /api/settings` ───────────────────
def test_KFT2_U14_tidak_ada_layar_menulis_settings_lama():
    pola = re.compile(r"""axios\.put\(\s*[`"'](?:\$\{API\})?/settings[`"'?]""")
    temuan = [str(p.relative_to(ROOT)) for p in (ROOT / "frontend/src").rglob("*.js*")
              if "node_modules" not in p.parts and pola.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert temuan == []
