"""KP-T9 — menu Pengaturan menjadi sembilan hub dengan satu istilah "PT" (docs/blueprint/unit/KP-T9.md, keputusan K-46).

Lapis B (database tiruan) dan uji statik. Uji komponen U3, U4, U5, U10, U12 di jest
(`frontend/src/config/__tests__/kpt9HubPengaturan.test.js`, `frontend/src/features/__tests__/kpt9BagianLayar.test.js`);
uji jalan layar U13 di lingkungan A (peramban).

U1   penjaga katalog modul ↔ menu: 0 temuan termasuk aturan (3) dan (4); mutasi membuktikan kedua aturan menangkap.
U2   penjaga statik: judul halaman enam id baru, istilah menu tanpa "Entitas"/"Badan Usaha", alias, batas tab.
U6   peran Tanpa Acuan bermodul SDM "Lihat saja" → menu Pengaturan › SDM termasuk Mesin Absen, tanpa hub Sistem.
U7   peran Tanpa Acuan bermodul PT saja / Peran & Hak Akses saja → hub masing-masing, tidak saling bocor.
U8   peran Manajer Kosong → tidak satu pun id `settings-*` di menu; semua id hub/tab baru ikut dicabut dari warisan Manajer.
U9   `hidden_views` menerima id tab baru (`settings-accounts`), menolak id tak dikenal.
U11  teks letak "Pengaturan › …" di frontend/src dan backend tidak memuat nama hub lama.
Tambahan (istilah PT di katalog modul; tujuan "Lengkapi" daftar kesiapan PT = tab hub baru).
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"
for _p in (ROOT / "scripts" / "guardrails", ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

#: Sembilan hub (tabel "Layar" unit) — id item menu = id hub.
HUBS = ["settings-company", "settings-access", "settings-approval", "settings-sales", "settings-warehouse",
        "settings-finance", "settings-hr", "settings-documents", "settings-system"]
#: Enam id layar baru (rute baru di AppViewRouter, judul baru di PAGE_META).
ID_BARU = ["settings-pt-profile", "settings-pt-readiness", "settings-accounts", "settings-role-check",
           "settings-attendance-devices", "settings-whatsapp"]
NAMA_HUB_LAMA = ["Perusahaan & Akun", "Pembelian & Produksi", "Master Data", "Dokumen & Cetak",
                 "Notifikasi & Penjadwal", "Integrasi & Sistem"]


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _nav_peran(klien, kepala_admin, levels: dict, label: str, base_role: str = "") -> dict:
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": label, "base_role": base_role, "description": "peran uji KP-T9", "levels": levels})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    # Menu peran kustom = `nav` di `GET /api/roles` (dibaca `roles.registerDynamicRoles` di layar).
    r = await klien.get("/api/roles", headers=kepala_admin)
    assert r.status_code == 200, r.text
    lst = r.json()["roles"] if isinstance(r.json(), dict) else r.json()
    nav = next(x for x in lst if x["id"] == rid)["nav"]
    return {"id": rid, "add": set(nav["add"]), "remove": set(nav["remove"])}


# ── U1 — penjaga katalog: aturan (3) tab Pengaturan bermodul, (4) modul memuat hub induk + settings-hub ───────────────
def test_KPT9_U01_katalog_selaras_termasuk_aturan_3_dan_4():
    import access_modules as am
    import verify_access_catalog_nav as guard
    importlib.reload(guard)
    assert guard.scan() == []
    simpan = {m["id"]: list(m["nav"]) for m in am.MODULE_CATALOG}
    try:
        # Aturan (3): `settings-accounts` dicabut dari semua modul → tab tampak tanpa modul. Modul Akun Pengguna yang
        # kini memberi hub `settings-access` tanpa satu pun tabnya juga ikut tertangkap aturan (2) — dua temuan.
        for m in am.MODULE_CATALOG:
            m["nav"] = [v for v in m["nav"] if v != "settings-accounts"]
        hasil = guard.scan()
        aturan3 = [h for h in hasil if "settings-accounts" in h and "tidak ada di modul mana pun" in h]
        assert len(aturan3) == 1, hasil
        assert len(hasil) == 2 and any("[accounts] hub settings-access" in h for h in hasil), hasil
        for m in am.MODULE_CATALOG:
            m["nav"] = list(simpan[m["id"]])
        # Aturan (4): modul pemuat tab Pengaturan tanpa hub induknya → tepat satu temuan (per modul × hub).
        mod = am.MODULE_BY_ID["finance_ops"]
        mod["nav"] = [v for v in mod["nav"] if v != "settings-sales"]   # pemuat tab Alasan Koreksi
        hasil = guard.scan()
        assert hasil == ["[finance_ops] memuat tab Pengaturan (amendment-reasons) tanpa hub induknya: settings-sales"], hasil
        mod["nav"] = list(simpan["finance_ops"])
        mod = am.MODULE_BY_ID["documents"]
        mod["nav"] = [v for v in mod["nav"] if v != "settings-hub"]
        hasil = guard.scan()
        assert hasil == ["[documents] memuat tab Pengaturan (pdf-templates) tanpa hub induknya: settings-hub"], hasil
    finally:
        for m in am.MODULE_CATALOG:
            m["nav"] = simpan[m["id"]]
    assert guard.scan() == []


def test_KPT9_U01b_uji_diri_penjaga_katalog():
    import verify_access_catalog_nav as guard
    importlib.reload(guard)
    assert guard.self_test() == 0


# ── U2 — penjaga statik ─────────────────────────────────────────────────────────────────────────────────────────────
def _check_nav_map():
    """`scripts/check_nav_map.py` membaca `/app/frontend/src`; di sini diarahkan ke salinan repo yang sedang diuji."""
    import check_nav_map as cnm
    importlib.reload(cnm)
    cnm.SRC = FE
    cnm.NAV_CFG, cnm.NAV_STRUCT, cnm.NAV_META = FE / "config/navigationConfig.js", FE / "config/navStructure.js", FE / "config/navMeta.js"
    cnm.ROLES_CFG, cnm.SIDEBAR = FE / "config/roles.js", FE / "components/CoreWidgets.jsx"
    cnm.OPS_VIEW, cnm.ORDERS_VIEW = FE / "features/wms/OperationsView.jsx", FE / "features/orders/OrdersView.jsx"
    return cnm


def test_KPT9_U02_judul_istilah_alias_dan_batas_tab():
    cnm = _check_nav_map()
    assert cnm.check_page_meta() == 0
    entries = cnm.parse_nav_config()
    assert cnm.check_config(entries) == 0 and cnm.check_roles(entries) == 0 and cnm.check_depth(entries) == 0
    # CHECK 6 (baru, KP-T9): label/title/kicker tiga berkas menu tanpa "Entitas"/"Badan Usaha".
    assert cnm.check_terms() == 0
    meta = (FE / "config/navMeta.js").read_text(encoding="utf-8")
    for v in ID_BARU:
        assert re.search(rf'^\s*"{v}":\s*\{{\s*kicker:\s*"Pengaturan · [^"]+",\s*title:', meta, re.M), v
    import verify_view_aliases as va
    importlib.reload(va)
    assert va.main() == 0 and va.self_test() == 0
    import verify_page_tabs as vpt
    importlib.reload(vpt)
    _, n13, n14 = vpt.check_mnt1()
    assert (n13, n14) == (0, 0)


# ── U6 — modul SDM "Lihat saja": Pengaturan › SDM (+ Mesin Absen), tanpa Sistem / Perangkat RFID ─────────────────────
async def test_KPT9_U06_modul_sdm_membuka_mesin_absen_tanpa_hub_sistem(klien, kepala_admin):
    p = await _nav_peran(klien, kepala_admin, {"hr": "view"}, "Tanpa Acuan KPT9 SDM")
    assert {"settings-hub", "settings-hr", "settings-cfg-hr", "hr-attendance-setup",
            "settings-attendance-devices"} <= p["add"], sorted(p["add"])
    assert not ({"settings-system", "settings-devices"} & p["add"]), sorted(p["add"])


# ── U7 — modul PT saja / modul Peran & Hak Akses saja ───────────────────────────────────────────────────────────────
async def test_KPT9_U07_modul_pt_dan_modul_peran_tidak_saling_bocor(klien, kepala_admin):
    pt = await _nav_peran(klien, kepala_admin, {"entities": "view"}, "Tanpa Acuan KPT9 PT")
    assert {"settings-hub", "settings-company", "settings-pt-profile", "settings-pt-readiness"} <= pt["add"], sorted(pt["add"])
    assert "settings-access" not in pt["add"]
    assert not ({"settings-accounts", "permission-matrix", "settings-role-check"} & pt["add"])
    peran = await _nav_peran(klien, kepala_admin, {"roles": "view"}, "Tanpa Acuan KPT9 Peran")
    assert {"settings-hub", "settings-access", "permission-matrix", "settings-role-check"} <= peran["add"], sorted(peran["add"])
    assert not ({"settings-pt-profile", "settings-pt-readiness", "settings-company"} & peran["add"])
    akun = await _nav_peran(klien, kepala_admin, {"accounts": "view"}, "Tanpa Acuan KPT9 Akun")
    assert {"settings-access", "settings-accounts"} <= akun["add"] and "permission-matrix" not in akun["add"]


# ── U8 — Manajer Kosong ─────────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT9_U08_manajer_kosong_tanpa_menu_pengaturan(klien, kepala_admin):
    r = await klien.get("/api/access/modules", headers=kepala_admin)
    mods = r.json().get("modules", r.json()) if isinstance(r.json(), dict) else r.json()
    p = await _nav_peran(klien, kepala_admin, {m["id"]: "none" for m in mods}, "Manajer Kosong KPT9", base_role="manager")
    assert sorted(v for v in p["add"] if v.startswith("settings-")) == []
    # Menu Manajer yang diwarisi peran ini dicabut lewat `remove`: semua hub + tab baru harus ikut tercabut.
    tab_baru = HUBS + ID_BARU + ["permission-matrix", "entity-masters", "domain-registry", "scheduler"]
    assert [v for v in tab_baru if v not in p["remove"]] == []


# ── U9 — hidden_views ───────────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT9_U09_hidden_views_id_baru_diterima_id_asing_ditolak(klien, kepala_admin, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"user": ["view"]}, label="Tanpa Acuan KPT9 Sembunyi")
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin, json={"hidden_views": ["settings-accounts"]})
    assert r.status_code == 200, r.text
    r = await klien.get(f"/api/access/roles/{rid}", headers=kepala_admin)
    assert r.json()["hidden_views"] == ["settings-accounts"]
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin, json={"hidden_views": ["settings-tidak-ada"]})
    assert r.status_code == 400, r.text
    assert "tidak dikenal" in _detail(r) and "settings-tidak-ada" in _detail(r)


# ── U11 — teks letak "Pengaturan › …" memakai nama hub baru ─────────────────────────────────────────────────────────
POLA_LETAK = re.compile(r"Pengaturan\s*(?:›|\\u203a|&rsaquo;)\s*((?:[^\n\"'`<{]|&amp;)+)")


def _berkas_sumber():
    for akar, pola in ((FE, ("*.js", "*.jsx")), (ROOT / "backend", ("*.py",))):
        for p in pola:
            for f in akar.rglob(p):
                rel = f.relative_to(ROOT).as_posix()
                if any(s in rel for s in ("__tests__", "/tests_mem/", "/tests/", "node_modules", "__pycache__")):
                    continue
                yield rel, f


def _lanjut_baris(teks: str, akhir: int) -> str:
    """Isi baris berikutnya tanpa penanda komentar (teks letak yang terpotong di akhir baris komentar/docstring)."""
    nl = teks.find("\n", akhir)
    if nl < 0:
        return ""
    baris = teks[nl + 1:teks.find("\n", nl + 1) if teks.find("\n", nl + 1) >= 0 else len(teks)]
    return re.sub(r"^\s*(?:\*|//|#)?\s*", "", baris)


def test_KPT9_U11_teks_letak_tanpa_nama_hub_lama():
    temuan = []
    for rel, f in _berkas_sumber():
        teks = f.read_text(encoding="utf-8", errors="ignore")
        for m in POLA_LETAK.finditer(teks):
            sisa = m.group(1).replace("&amp;", "&").rstrip()
            utuh = f"{sisa} {_lanjut_baris(teks, m.end())}".replace("&amp;", "&")   # "Integrasi &" + baris berikut
            if any(sisa.startswith(n) or utuh.startswith(n) for n in NAMA_HUB_LAMA):
                baris = teks.count("\n", 0, m.start()) + 1
                temuan.append(f"{rel}:{baris}: Pengaturan › {utuh[:50]}")
    assert temuan == []


# ── Tambahan — istilah PT di katalog modul akses ────────────────────────────────────────────────────────────────────
def test_KPT9_istilah_pt_di_katalog_modul():
    import access_modules as am
    assert am.RESOURCE_LABEL["entity"] == "PT"
    assert am.MODULE_BY_ID["interco"]["label"] == "Transaksi Antar-PT"
    pola = re.compile(r"badan usaha|\bentitas\b", re.I)
    teks = [(m["id"], m["label"]) for m in am.MODULE_CATALOG] + [(m["id"], m["description"]) for m in am.MODULE_CATALOG]
    teks += [(k, v) for k, v in am.RESOURCE_LABEL.items()]
    assert [f"{k}: {v}" for k, v in teks if pola.search(v)] == []


# ── Tambahan — "Lengkapi" di daftar kesiapan PT membuka tab hub yang ada ────────────────────────────────────────────
async def test_KPT9_kesiapan_pt_menuju_tab_hub_baru(klien, kepala_admin):
    r = await klien.get("/api/entities/ent_ksc/readiness", headers=kepala_admin)
    assert r.status_code == 200, r.text
    tujuan = {i["key"]: i["view"] for i in r.json()["items"] if i.get("view")}
    assert tujuan["address"] == tujuan["tax"] == tujuan["doc_prefix"] == "settings-pt-profile"
    assert tujuan["users"] == tujuan["finance_user"] == "settings-accounts"
    menu_src = (FE / "config/hubTabs.js").read_text(encoding="utf-8") + (FE / "config/navStructure.js").read_text(encoding="utf-8")
    layar = set(re.findall(r'\b(?:view|id):\s*"([\w-]+)"', menu_src))   # tab hub + menu tanpa hub (mis. Data Gudang)
    assert sorted(v for v in tujuan.values() if v not in layar) == []
    teks = " ".join(i["how_to"] for i in r.json()["items"])
    assert "tab Akun & Akses" not in teks and "Badan Usaha" not in teks
