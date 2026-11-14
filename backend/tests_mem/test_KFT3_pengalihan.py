"""KF-T3 — serah-terima (b): nilai khusus PT dipakai mesin, kunci yang tidak menggerakkan apa pun ditandai, pemeriksa
kesehatan diperketat (docs/blueprint/unit/KF-T3.md, U10 + U12–U16; U11 = lapis A, U17 = uji jalan layar).

Peran: `kepala_admin` = admin seed (lintas PT). PT seed `ent_ksc` (PKP) dan `ent_kanda`. Satu basis data per modul.
Tambahan di luar tabel (huruf b/c) membuktikan baris tabel (3) yang tidak punya ID uji sendiri.
"""
from __future__ import annotations

import ast
import datetime as dt
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import config_registry as registry

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def _put(key, value, *, scope_type="entity", scope_id="ent_ksc", reason="uji KF-T3"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]}


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _simpan(klien, hdr, key, value, **kw):
    r = await klien.put("/api/config/values", headers=hdr, json=_put(key, value, **kw))
    assert r.status_code == 200, r.text


# ── U1c — bentuk baru penyimpangan `t1_config.py` (KF-04): tulis lapisan PT bukan PKP ────────────────────────────────
async def test_KFT3_U1c_tulis_ppn_pt_bukan_pkp_tersimpan_tetapi_tidak_dipakai(klien, kepala_admin):
    from services.config_resolver import value_of
    from services.config_service import get_effective_settings
    await _simpan(klien, kepala_admin, "tax.ppn_rate", 13.0, scope_id="ent_kanda", reason="uji KF-T3 — tarif PT")
    r = await klien.get("/api/config/effective", headers=kepala_admin,
                        params={"q": "tax.ppn_rate", "entity_id": "ent_kanda"})
    it = next(x for x in r.json()["items"] if x["key"] == "tax.ppn_rate")
    # resolver = pembaca lama = 0; nilai tulis tetap tersimpan dan terlihat.
    assert it["value"] == 0 and it["stored_value"] == 13.0 and it["source_layer"] == "entity"
    assert await value_of("tax.ppn_rate", {"entity_id": "ent_kanda"}) == 0
    assert (await get_effective_settings("ent_kanda"))["tax"]["ppn_rate"] == 0
    h = await klien.get("/api/config/history", headers=kepala_admin, params={"key": "tax.ppn_rate"})
    assert h.json()["rows"][0]["prev_value"] == 12.0          # riwayat = perubahan nilai tersimpan (12 → 13)
    r = await klien.post("/api/config/values/clear", headers=kepala_admin,
                         json={"key": "tax.ppn_rate", "scope_type": "entity", "scope_id": "ent_kanda", "reason": "uji"})
    assert r.status_code == 200, r.text


# ── U10 — termin bawaan pesanan per PT (KP-11) ──────────────────────────────────────────────────────────────────────
async def test_KFT3_U10_termin_bawaan_per_pt(klien, kepala_admin):
    from services import config_service
    await _simpan(klien, kepala_admin, "finance.default_payment_term_code", "NET7")
    assert await config_service.default_payment_term_code("ent_ksc") == "NET7"
    assert await config_service.default_payment_term_code("ent_kanda") == "NET30"
    # Pembacaan langsung dokumen grup di sekitar termin tidak ada lagi.
    src = (BACKEND / "routers/sales_orders.py").read_text(encoding="utf-8")
    i = src.index("Term pembayaran: pilihan user")
    assert "system_settings.find_one" not in src[i - 200:i + 800]
    assert "default_payment_term_code(entity_id)" in src[i:i + 800]


# ── U10b — satuan bawaan produk baru = PT aktif pembuat ─────────────────────────────────────────────────────────────
async def test_KFT3_U10b_satuan_bawaan_produk_baru_per_pt(klien, kepala_admin, sesi):
    await _simpan(klien, kepala_admin, "inventory.default_uom", "yard")
    hasil = {}
    for pt in ("ent_ksc", "ent_kanda"):
        hdr = await sesi("admin@kainnusantara.id", entitas=pt)
        r = await klien.post("/api/products", headers=hdr, json={
            "sku": f"KFT3-UOM-{pt[-3:].upper()}", "name": f"Uji satuan bawaan {pt}", "base_unit": "",
            "stage": "byproduct"})   # tahap tanpa isian wajib
        assert r.status_code == 200, r.text
        hasil[pt] = r.json().get("base_unit") or (r.json().get("product") or {}).get("base_unit")
    assert hasil == {"ent_ksc": "yard", "ent_kanda": "meter"}


# ── U10c — ambang "tahap PO macet" dibaca per PT tiap PO ────────────────────────────────────────────────────────────
async def test_KFT3_U10c_tahap_po_macet_per_pt(klien, kepala_admin, db, monkeypatch):
    from services import notification_service as ns
    await _simpan(klien, kepala_admin, "notif.po_stage_stuck_days", 3)
    lima_hari = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=5)).isoformat()
    # Fixture (sisip langsung): dua PO, tahap berjalan sejak 5 hari, di dua PT.
    for pt in ("ent_ksc", "ent_kanda"):
        await db.purchase_orders.insert_one({
            "id": f"po_kft3_{pt}", "po_number": f"PO-KFT3-{pt[-3:].upper()}", "entity_id": pt, "supplier_name": "Uji",
            "stage_progress": [{"stage_code": "tenun", "status": "in_progress", "at": lima_hari}]})
    tercatat = []

    async def _rekam(**kw):
        tercatat.append(kw)
        return [1]
    monkeypatch.setattr(ns, "create_addressed", _rekam)
    await ns._notify_stuck_po_stages()
    refs = {kw["ref"] for kw in tercatat}
    # ent_ksc: ambang 3 hari → 5 hari = macet; ent_kanda: bawaan 7 hari → belum.
    assert "po_stuck:po_kft3_ent_ksc:tenun" in refs
    assert "po_stuck:po_kft3_ent_kanda:tenun" not in refs


# ── U12 — toleransi konversi satuan per PT ──────────────────────────────────────────────────────────────────────────
async def test_KFT3_U12_toleransi_satuan_per_pt(klien, kepala_admin):
    from services import uom_rules_service as uomr
    await _simpan(klien, kepala_admin, "uom.block_pct", 50)
    # Selisih (110 − 100) / 100 = 10 %. KSC: blokir 50 % → bukan blokir; Kanda: blokir grup 5 % → blokir.
    assert (await uomr.check_variance(100, 110, entity_id="ent_ksc"))["level"] != "block"
    assert (await uomr.check_variance(100, 110, entity_id="ent_kanda"))["level"] == "block"
    assert (await uomr.load_engine("ent_ksc"))["settings"]["block_pct"] == 50
    assert (await uomr.load_engine())["settings"]["block_pct"] == 5.0


def test_KFT3_U12b_pemanggil_mesin_satuan_mengirim_pt_dokumen():
    """Pemanggil `load_engine()` / `check_variance()` tanpa PT hanya yang memang tanpa dokumen."""
    tanpa_pt = set()
    for path in list((BACKEND / "services").rglob("*.py")) + list((BACKEND / "routers").rglob("*.py")):
        pohon = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(pohon):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for c in ast.walk(fn):
                if isinstance(c, ast.Call) and getattr(c.func, "attr", getattr(c.func, "id", "")) == "load_engine" \
                        and not c.args and not c.keywords:
                    tanpa_pt.add(f"{path.relative_to(BACKEND)}:{fn.name}")
                if isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "check_variance" \
                        and len(c.args) < 3 and not any(k.arg in ("settings", "entity_id") for k in c.keywords):
                    tanpa_pt.add(f"{path.relative_to(BACKEND)}:{fn.name}")
    # Tanpa dokumen: konversi umum (mesin dipinjamkan pemanggil), estimasi makloon (idem), kalkulator selisih.
    assert tanpa_pt == {"services/uom_rules_service.py:convert_with_trail",
                        "services/makloon_calc_service.py:estimate_output",
                        "routers/uom_conversions.py:check_variance"}


# ── U13 — tolak "melebihi sisa PO" mengikuti PT tugas ───────────────────────────────────────────────────────────────
def _tugas(pt):
    # Fixture (dokumen di memori): tugas penerimaan sisa 10, tanpa PO (toleransi grup 2 % → maks 10,2).
    return {"id": f"task_kft3_{pt}", "entity_id": pt, "flow_type": "inbound", "unit": "meter",
            "expected_qty": 10, "received_qty": 0, "product_id": "", "po_id": ""}


async def test_KFT3_U13_lebih_dari_sisa_mengikuti_pt_tugas(klien, kepala_admin):
    from services import receiving_uom_service as rus
    await _simpan(klien, kepala_admin, "receiving.block_over_remaining", False)
    scan = SimpleNamespace(actual_qty=12, doc_uom="", doc_qty=None, variance_override_reason="")
    hasil = await rus.preflight_scan(_tugas("ent_ksc"), scan)
    assert hasil["over_receipt"] is True and hasil["over_blocked"] is False
    with pytest.raises(rus.ReceivingUomError):
        await rus.preflight_scan(_tugas("ent_kanda"), scan)


async def test_KFT3_U13b_mode_satuan_pemasok_mengikuti_pt_tugas(klien, kepala_admin):
    from services import receiving_uom_service as rus
    await _simpan(klien, kepala_admin, "receiving.supplier_uom_input_mode", "off")
    with pytest.raises(rus.ReceivingUomError, match="DIMATIKAN"):
        await rus.convert_doc_qty(_tugas("ent_ksc"), "yard", 10)
    try:
        await rus.convert_doc_qty(_tugas("ent_kanda"), "yard", 10)
    except rus.ReceivingUomError as exc:            # boleh gagal karena hal lain, bukan karena mode "off"
        assert "DIMATIKAN" not in str(exc)
    assert (await rus.uom_options(_tugas("ent_ksc")))["mode"] == "off"
    assert (await rus.uom_options(_tugas("ent_kanda")))["mode"] == "prefer"


# ── U13c — kebijakan lot saat inspeksi QC = PT pemilik roll ─────────────────────────────────────────────────────────
async def test_KFT3_U13c_inspeksi_qc_membaca_kebijakan_lot_pt_pemilik(monkeypatch):
    from services import lot_service, qc_inspection_service as qis
    diminta = []

    class _Berhenti(Exception):
        pass

    async def _rekam(entity_id: str = ""):
        diminta.append(entity_id)
        raise _Berhenti()
    monkeypatch.setattr(lot_service, "get_settings", _rekam)
    roll = {"id": "roll_kft3", "roll_no": "RL-KFT3", "owner_entity_id": "ent_kanda"}
    with pytest.raises(_Berhenti):
        await qis.inspect_roll(roll, [], None, None, "", {"name": "Uji"}, grade_input="A")
    assert diminta == ["ent_kanda"]


# ── U14 — lapisan yang dicabut dan batas minimum ────────────────────────────────────────────────────────────────────
async def test_KFT3_U14_lapisan_dicabut_dan_minimum_satu(klien, kepala_admin):
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_put("notif.low_stock_division", "Penjualan"))
    assert r.status_code == 400, r.text
    # KF-T5 — pesan lapisan tak sah kini berbahasa layar: "“{label}” tidak bisa dibedakan per PT."
    assert "tidak bisa dibedakan per PT" in _detail(r)
    for key in ("payment.plan_tolerance_rupiah", "case.holding_case_after_days"):
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_put(key, 0, scope_type="global",
                                                                               scope_id=""))
        assert r.status_code == 400, (key, r.text)
        assert "1" in _detail(r), (key, _detail(r))
    assert registry.get("notif.low_stock_division")["scopes"] == ["global"]
    assert registry.get("payment.plan_tolerance_rupiah")["min"] == 1
    assert registry.get("payment.plan_tolerance_rupiah")["help"].endswith("Paling kecil Rp 1.")
    assert registry.get("case.holding_case_after_days")["min"] == 1


async def test_KFT3_U14b_pembaca_nol_memakai_bawaan_registry():
    from services import finance_case_service, payment_plan_service
    assert (await payment_plan_service.plan_policy("ent_ksc"))["tolerance"] == registry.default_of(
        "payment.plan_tolerance_rupiah") == 1
    assert (await finance_case_service.policy("ent_ksc"))["holding_days"] == registry.default_of(
        "case.holding_case_after_days") == 3
    for berkas, pola in (("services/payment_plan_service.py", r'plan_tolerance_rupiah"\) or 1\b'),
                         ("services/finance_case_service.py", r'holding_case_after_days"\) or 3\b')):
        assert not re.search(pola, (BACKEND / berkas).read_text(encoding="utf-8")), berkas


# ── U15 — kunci yang tidak menggerakkan mesin ───────────────────────────────────────────────────────────────────────
#: Tabel (4) spesifikasi. `role_home.*` sudah ditandai PR-T4 dengan alasan yang kini benar (halaman awal = sifat peran
#: di Peran & Hak Akses) — alasan PR-T4 dipertahankan; lihat laporan KF-T3 "Usulan koreksi blueprint".
ALASAN_ROLE_HOME = "Diatur per peran di Peran & Hak Akses › Halaman awal"
TABEL_4 = {
    "role_home.admin": ALASAN_ROLE_HOME, "role_home.manager": ALASAN_ROLE_HOME,
    "role_home.sales": ALASAN_ROLE_HOME, "role_home.warehouse": ALASAN_ROLE_HOME,
    "tax.efaktur_enabled": "Penerbitan faktur pajak mengikuti status PKP di profil PT.",
    "contra_bon.qty_tolerance_percent":
        "Toleransi jumlah kontrabon mengikuti pengaturan 'Toleransi jumlah tagihan pemasok'.",
}


async def test_KFT3_U15_enam_kunci_tidak_dipakai(klien, kepala_admin):
    for key, alasan in TABEL_4.items():
        e = registry.get(key)
        assert e["status"] == "not_used", key
        assert e["not_used_reason"] == alasan, key
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_put("role_home.admin", "reports", scope_type="global", scope_id=""))
    assert r.status_code == 400, r.text
    assert ALASAN_ROLE_HOME in _detail(r)
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_put("tax.efaktur_enabled", False))
    assert r.status_code == 400, r.text
    assert TABEL_4["tax.efaktur_enabled"] in _detail(r)


async def test_KFT3_U15b_pusat_pajak_efaktur_mengikuti_pkp(klien, kepala_admin):
    from services.tax_center_service import tax_summary
    assert (await tax_summary("ent_ksc", None))["config"]["efaktur_enabled"] is True
    assert (await tax_summary("ent_kanda", None))["config"]["efaktur_enabled"] is False


# ── U16 — pemeriksa kesehatan: daun saja tidak cukup; fungsi wajib ada ──────────────────────────────────────────────
def _tiruan(key, consumers):
    return {**registry.require(key), "status": "active", "not_used_reason": "", "consumers": list(consumers)}


def test_KFT3_U16_pemeriksa_kesehatan_diperketat(monkeypatch):
    from services import config_health
    monkeypatch.setattr(config_health, "BACKEND", str(BACKEND))
    monkeypatch.setattr(config_health, "FRONTEND", str(ROOT / "frontend/src"))
    config_health._CACHE.clear()
    getattr(config_health, "_TREES", {}).clear()
    assert config_health.check_entry(_tiruan("role_home.admin", ("permissions_config.py",)))["wiring_status"] == "STALE"
    assert config_health.check_entry(
        _tiruan("ar.grace_days", ("services/config_service.py:tidak_ada",)))["wiring_status"] == "MISSING"
    # Rujukan nyata tetap OK: fungsi yang membaca kunci (induk + daun di badannya).
    assert config_health.check_entry(
        _tiruan("ar.grace_days", ("services/ar_aging_service.py:get_ar_config",)))["wiring_status"] == "OK"
    rep = config_health.report()
    assert [(b["key"], b["wiring_status"]) for b in rep["broken"]] == []
