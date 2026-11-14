"""KF-T4 — Pusat Pengaturan berbahasa awam, berkelompok rapi (docs/blueprint/unit/KF-T4.md): U1–U4, U12 + pelengkap.

Statik (registry dimuat di proses uji) + HTTP lewat `kepala_admin` (admin seed, lintas PT).
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import config_registry as registry

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
POTRET = Path(__file__).resolve().parent / "data" / "potret_registry_sebelum_KFT4.json"

#: Tabel (c) unit — 13 kelompok. KF-T7 (digabung sesudah unit ini) menambah kelompok ke-14 "Keamanan akun & sesi"
#: (`keamanan`, spesifikasi KF-T7; layar Integrasi & Sistem bersama `sistem`).
KELOMPOK_BARU = ["penjualan", "pembayaran-pelanggan", "retur-koreksi", "pembelian", "penerimaan", "kualitas", "stok",
                 "persetujuan", "pajak-pembukuan", "bank-kasus", "sdm", "rnd", "sistem", "keamanan"]
#: KF-T7 — dua kunci kredit baru (`ar.overdue_block_days`, `ar.credit_warning_pct`) di "Pembayaran pelanggan".
KFT7_PEMBAYARAN_PELANGGAN = 2
#: Editor KF-T4 (tabel "Editor baru") memberi PILIHAN pada daftar yang dulu tanpa pilihan: urutan alokasi dan sumbu
#: varian. Nilai pilihan kunci lain tidak boleh berubah.
PILIHAN_BARU = {"allocation.priority_order", "rnd.variant_axes_default", "rnd.variant_axes_optional"}


def _penjaga():
    p = ROOT / "scripts" / "guardrails" / "verify_config_text.py"
    spec = importlib.util.spec_from_file_location("verify_config_text_kft4", p)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(p.parent))
    spec.loader.exec_module(mod)
    return mod


# ── U1 — penjaga teks: 0 pelanggaran T1–T7 dan self-test merah per aturan ────────────────────────────────────────────
def test_KFT4_U1_penjaga_teks_nol_pelanggaran():
    g = _penjaga()
    entries, groups, izin = g.muat()
    hasil = g.periksa(entries, groups, g.label_menu(), izin)
    assert hasil == [], hasil[:20]
    assert g.self_test() == 0


def test_KFT4_U1b_penjaga_terdaftar_di_gate_statik():
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert "python scripts/guardrails/verify_config_text.py --self-test" in gate
    assert re.search(r'"[^"]*INV-CFG-TXT[^"]*\|python scripts/guardrails/verify_config_text.py"', gate)


# ── U2 — bidang yang menentukan perilaku tidak berubah ───────────────────────────────────────────────────────────────
def test_KFT4_U2_bidang_perilaku_sama_dengan_potret():
    potret = json.loads(POTRET.read_text(encoding="utf-8"))["kunci"]
    # Hitungan: potret 69cc4e3 = 383 kunci; unit ini tidak menambah atau menghapus kunci.
    assert len(potret) == 383
    for key, lama in potret.items():
        e = registry.get(key)
        assert e is not None, f"kunci hilang: {key}"
        for f in ("type", "default", "min", "max", "scopes", "permission", "status", "sensitif_baca"):
            assert e[f] == lama[f], (key, f, e[f], lama[f])
        nilai = [o["value"] for o in e["options"]]
        if key in PILIHAN_BARU:
            assert not lama["options"] and nilai, key
        else:
            assert nilai == lama["options"], (key, nilai, lama["options"])
    assert {e["key"] for e in registry.all_entries()} >= set(potret)


# ── U3 — 13 kelompok, setiap kunci bersub-judul terdaftar ─────────────────────────────────────────────────────────────
async def test_KFT4_U3_registry_13_kelompok_bersubjudul(klien, kepala_admin):
    r = await klien.get("/api/config/registry", headers=kepala_admin)
    assert r.status_code == 200, r.text
    j = r.json()
    assert [g["id"] for g in j["groups"]] == KELOMPOK_BARU
    sub = {g["id"]: {s["id"]: s for s in g["sections"]} for g in j["groups"]}
    for e in j["entries"]:
        assert e["section"] in sub[e["group"]], e["key"]
    where = {e["key"]: (e["group"], e["section"]) for e in j["entries"]}
    assert where["ar.grace_days"] == ("pembayaran-pelanggan", "denda")
    assert where["receiving.ocr_enabled"] == ("sistem", "baca-sj")
    assert where["payment.variance_ap_tolerance_rupiah"] == ("pembelian", "tagihan")
    assert where["pos.fbt.enabled"] == ("penjualan", "saran-pos")
    # Sub-judul "Lanjutan (teknis)" tertutup bawaan: tiga bagian teknis di kelompok Sistem.
    assert {s for g in j["groups"] for s, x in sub[g["id"]].items() if x["advanced"]} == {
        "tanya-kn-teknis", "baca-sj", "rfid-proses"}
    # Jumlah per sub-judul ikut dikirim dan sama dengan isi kelompok.
    for g in j["groups"]:
        assert sum(s["count"] for s in g["sections"]) == g["count"], g["id"]


def test_KFT4_U3b_aliases_dan_penempatan_kunci_baru():
    # Kunci yang lahir sesudah 3132cc4 mengikuti pola awalannya (asumsi unit).
    assert registry.get("interco_payment.basis")["group"] == "pajak-pembukuan"
    assert registry.get("interco_payment.basis")["section"] == "antar-pt"
    assert registry.get("hr.pph21.ter_table")["section"] == "pph21"
    assert registry.get("kontrol.setujui_po.min_orang")["section"] == "dua-orang-pembelian"
    # Id kelompok lama tetap diterima (E(group=<id lama>) dan pembacaan kelompok).
    for lama, (baru, sub) in registry.GROUP_ALIASES.items():
        assert lama not in registry.GROUP_IDS and baru in registry.GROUP_IDS, lama
        assert not sub or sub in registry.SECTION_IDS[baru], lama
        assert registry.by_group(lama) == registry.by_group(baru)
    # Tema lintas kelompok dari pola kunci (persetujuan 35 · pengingat 18 pada 3132cc4 + 2 kunci baru · toleransi 15).
    hitung = {t: sum(1 for e in registry.all_entries() if t in registry.themes_for(e["key"]))
              for t in ("persetujuan", "pengingat", "toleransi")}
    # KP-T7 (digabung sesudah unit ini dikerjakan) menambah 19 kunci pengingat: +1 bertema persetujuan
    # (`approval.reminder_max_listed`) dan +5 bertema pengingat. KF-T7 menambah +1 bertema toleransi
    # (`finance.rounding_tolerance_rupiah`).
    assert hitung == {"persetujuan": 35 + 1, "pengingat": 20 + 5, "toleransi": 15 + 1}


# ── U4 — id kelompok lama di GET /effective ───────────────────────────────────────────────────────────────────────────
async def test_KFT4_U4_effective_menerima_id_kelompok_lama(klien, kepala_admin):
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"group": "uang-masuk"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items and {it["group"] for it in items} == {"pembayaran-pelanggan"}
    assert len(items) == len(registry.by_group("pembayaran-pelanggan")) == 24 + KFT7_PEMBAYARAN_PELANGGAN
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"group": "dokumen"})
    assert r.status_code == 200, r.text
    assert {it["group"] for it in r.json()["items"]} == {"persetujuan"}


async def test_KFT4_U4b_butir_membawa_data_kartu(klien, kepala_admin):
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"group": "sistem"})
    assert r.status_code == 200, r.text
    by = {it["key"]: it for it in r.json()["items"]}
    po = by["receiving.client_po_patterns"]
    assert po["value_format"] == "regex" and po["section"] == "baca-sj"
    for f in ("themes", "items", "ordered", "ref", "ref_options", "edit_at", "permission", "permission_label",
              "never_changed"):
        assert f in po, f
    assert po["permission"] == ["settings", "manage"]
    assert po["permission_label"] == "Pusat Pengaturan"   # PR-T5 — modul pemilik `settings` sesudah dipecah
    assert po["never_changed"] is True
    assert by["ai.margin_roles"]["items"] == "roles"


# ── U12 — pencarian dengan padanan kata dua arah ──────────────────────────────────────────────────────────────────────
async def test_KFT4_U12_cari_padanan_dua_arah(klien, kepala_admin):
    async def keys(q):
        r = await klien.get("/api/config/registry", headers=kepala_admin, params={"q": q})
        assert r.status_code == 200, r.text
        return {e["key"] for e in r.json()["entries"]}
    for a, b in (("supplier", "pemasok"), ("gulungan", "roll"), ("termin", "syarat bayar"), ("telat", "terlambat")):
        ka, kb = await keys(a), await keys(b)
        assert ka and ka == kb, (a, b, ka ^ kb)
    # Contoh dan label sub-judul ikut dicari.
    assert "receiving.ocr_enabled" in await keys("baca surat jalan otomatis")
    assert "allocation.lot_selection" in await keys("habiskan roll sisa")


# ── pelengkap: indeks kunci layar = keluaran skrip; salinan alias layar = server ─────────────────────────────────────
def test_KFT4_indeks_kunci_layar_sama_dengan_skrip():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_config_key_index.py"), "--print"],
                         capture_output=True, text=True, check=True, cwd=str(ROOT))
    berkas = (ROOT / "frontend/src/features/settings/config/configKeyIndex.json").read_text(encoding="utf-8")
    assert json.loads(out.stdout) == json.loads(berkas)
    data = json.loads(berkas)
    assert data["keys"]["ar.grace_days"] == ["pembayaran-pelanggan", "denda"]
    assert data["aliases"] == {k: list(v) for k, v in registry.GROUP_ALIASES.items()}
    assert [g["id"] for g in data["groups"]] == KELOMPOK_BARU


def test_KFT4_layar_kelompok_tepat_satu_layar():
    js = (ROOT / "frontend/src/features/settings/config/configGroupViews.js").read_text(encoding="utf-8")
    views = dict(re.findall(r'"(settings-cfg-[a-z]+)":\s*\{[^}]*?groups:\s*\[([^\]]*)\]', js, re.S))
    peta = {v: re.findall(r'"([a-z-]+)"', g) for v, g in views.items()}
    assert peta == {
        "settings-cfg-approval": ["persetujuan"], "settings-cfg-sales": ["penjualan", "retur-koreksi"],
        "settings-cfg-warehouse": ["penerimaan", "kualitas", "stok"], "settings-cfg-purchasing": ["pembelian"],
        "settings-cfg-finance": ["pembayaran-pelanggan", "pajak-pembukuan", "bank-kasus"],
        "settings-cfg-hr": ["sdm"], "settings-cfg-rnd": ["rnd"],
        "settings-cfg-system": ["sistem", "keamanan"]}   # KF-T7 — kelompok Keamanan akun & sesi
