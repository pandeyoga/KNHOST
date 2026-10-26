"""Fase 3 · P2 (keputusan pemilik P16-K1) — setiap kelompok registri Pusat Pengaturan punya RUMAH di menu Pengaturan.

Menu Pengaturan kini per domain: tiap layar `settings-cfg-*` = Pusat Pengaturan yang dikunci ke kelompok registrinya
(`frontend/src/features/settings/config/configGroupViews.js`). Kelompok registri BARU (mis. kunci setelan baru D2 K-05)
yang lupa dipetakan akan "yatim" — hanya terlihat di "Semua pengaturan", tidak di menu domainnya. Uji ini memerah bila:
  1. ada kelompok `config_registry.GROUPS` yang tidak dipetakan ke tepat satu layar `settings-cfg-*`;
  2. peta frontend menyebut kelompok yang tidak ada di registri (salah ketik / kelompok dihapus);
  3. daftar `CONFIG_GROUP_IDS` (configDeepLink.js) tidak sama dengan registri.
Murni statik (tanpa DB/HTTP):
    python -m pytest tests/test_phase3_p2_settings_groups.py -q
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import config_registry  # noqa: E402

FE = ROOT / "frontend" / "src" / "features" / "settings" / "config"


def _views():
    src = (FE / "configGroupViews.js").read_text(encoding="utf-8")
    block = re.search(r"export const CONFIG_GROUP_VIEWS = \{(.*?)\n\};", src, re.S).group(1)
    out = {}
    for m in re.finditer(r'"(settings-cfg-[\w-]+)":\s*\{(.*?)\}', block, re.S):
        groups = re.search(r"groups:\s*\[([^\]]*)\]", m.group(2), re.S)
        out[m.group(1)] = re.findall(r'"([\w-]+)"', groups.group(1) if groups else "")
    return out


def _deeplink_ids():
    src = (FE / "configDeepLink.js").read_text(encoding="utf-8")
    block = re.search(r"export const CONFIG_GROUP_IDS = \[(.*?)\];", src, re.S).group(1)
    return re.findall(r'"([\w-]+)"', re.sub(r"//[^\n]*", "", block))


def test_setiap_kelompok_registri_punya_satu_layar_domain():
    registry = {g["id"] for g in config_registry.GROUPS}
    views = _views()
    assert views, "CONFIG_GROUP_VIEWS tidak terbaca"
    owners = {}
    for view, groups in views.items():
        for g in groups:
            owners.setdefault(g, []).append(view)
    yatim = sorted(registry - set(owners))
    ganda = {g: v for g, v in owners.items() if len(v) > 1}
    asing = sorted(set(owners) - registry)
    assert not yatim, f"kelompok registri tanpa layar Pengaturan domain: {yatim}"
    assert not ganda, f"kelompok dipetakan ke >1 layar: {ganda}"
    assert not asing, f"peta frontend menyebut kelompok yang tidak ada di registri: {asing}"


def test_daftar_kelompok_deeplink_sama_dengan_registri():
    assert sorted(_deeplink_ids()) == sorted(g["id"] for g in config_registry.GROUPS)
