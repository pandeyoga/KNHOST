#!/usr/bin/env python3
"""KF-T4 — tulis `frontend/src/features/settings/config/configKeyIndex.json` dari registry Pengaturan.

Kenapa ada: tautan langsung ke sebuah pengaturan (`openConfig({key})`) dulu MENEBAK kelompok dari awalan kunci lewat peta
yang disalin tangan (`LEGACY_DEEPLINK`, `CONFIG_GROUP_IDS`) — tiap kelompok baru membuatnya basi. Indeks ini dibangkitkan
dari `backend/config_registry.py`, jadi layar dan server selalu sepakat.

Isi berkas:
  groups   — [{id, label, sections: [{id, label, advanced}]}] urut tampil
  aliases  — salinan `GROUP_ALIASES` (id kelompok lama → [id baru, sub-judul tujuan])
  keys     — {kunci: [kelompok, sub-judul]}

Pemakaian (dari root repo; butuh dependensi backend, mis. di container backend):
    python scripts/gen_config_key_index.py           # tulis berkas
    python scripts/gen_config_key_index.py --print   # cetak ke layar (dipakai uji)
    python scripts/gen_config_key_index.py --check   # exit 1 bila berkas berbeda dari registry
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "src" / "features" / "settings" / "config" / "configKeyIndex.json"


def build() -> dict:
    sys.path.insert(0, str(ROOT / "backend"))
    import config_registry as reg  # noqa: WPS433
    return {
        "_catatan": "Dibangkitkan scripts/gen_config_key_index.py dari backend/config_registry.py — jangan diubah tangan.",
        "groups": [{"id": g["id"], "label": g["label"],
                    "sections": [{"id": s["id"], "label": s["label"], "advanced": bool(s.get("advanced"))}
                                 for s in g["sections"]]}
                   for g in sorted(reg.GROUPS, key=lambda x: x["order"])],
        "aliases": {k: list(v) for k, v in reg.GROUP_ALIASES.items()},
        "keys": {e["key"]: [e["group"], e["section"]] for e in reg.all_entries()},
    }


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main() -> int:
    text = render(build())
    if "--print" in sys.argv:
        sys.stdout.write(text)
        return 0
    if "--check" in sys.argv:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("configKeyIndex.json selaras registry" if same else
              "configKeyIndex.json BASI — jalankan: python scripts/gen_config_key_index.py")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"ditulis {OUT.relative_to(ROOT)} ({len(text.splitlines())} baris)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
