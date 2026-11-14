#!/usr/bin/env python3
"""KP-T8 — rahasia dan perangkat: token mesin absen → hash, token WhatsApp dibungkus, satu koneksi WhatsApp, izin integrasi.

    python scripts/migrate_kpt8_rahasia.py              # bawaan (= --dry-run): hanya lapor, tidak menulis
    python scripts/migrate_kpt8_rahasia.py --dry-run
    python scripts/migrate_kpt8_rahasia.py --apply      # tulis

Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`). Menjalankan skrip ini di DATA NYATA
(termasuk mode lapor) = titik henti H3: keputusan pemilik. Sebelum skrip dijalankan tidak ada yang putus: pembaca di
server menerima bentuk lama maupun baru (docs/blueprint/unit/KP-T8.md, bagian Data).

Yang dikerjakan (mode `--apply`; aman diulang — jalan kedua tanpa perubahan):
1. Tiap `hr_devices` ber-`device_token` polos: tulis `device_token_hash` (SHA-256 token itu), `device_token_hint`,
   `token_rotation_required: true`, lalu buang `device_token`. Token yang terpasang di mesin TETAP BERLAKU (mesin
   mengirim token yang sama; server membandingkan hash-nya). Perangkat yang sudah punya hash hanya dibuang token polosnya.
2. Token WhatsApp polos di `system_settings{scope:"alerts"}.wa` dan `integration_settings{id:"whatsapp"}` dibungkus —
   hanya bila `KN_SECRETS_KEY` terpasang (tanpa kunci: dilaporkan, tidak ditulis).
3. Koneksi WhatsApp: hanya satu konfigurasi terisi → disalin menjadi koneksi tunggal; keduanya terisi dan SAMA
   (penyedia, nomor, token) → digabung; BERBEDA → tidak digabung, dilaporkan "dua koneksi berbeda" untuk diputuskan
   pemilik di layar Pengaturan › Integrasi & Sistem › Integrasi & Audit. Koneksi tunggal yang sudah ada tidak disentuh.
4. Peran (bawaan atau kustom) yang memegang `hr.manage_settings` diberi `integration.manage` (K-47); daftarnya
   dilaporkan.

Argumen tidak dikenal/bertentangan → keluar 2 sebelum menyentuh basis data. Isi token tidak pernah dicetak.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

AKTOR = "migrasi KP-T8"


async def _konfigurasi_lama() -> Dict[str, Any]:
    """Baca dua konfigurasi WhatsApp lama TANPA menulis (pembaca server membungkus token saat dibaca; skrip tidak)."""
    from db import db
    from services import wa_alert_service as was
    from services import wa_connection as wc

    alerts_doc = await db.system_settings.find_one({"scope": was.SETTINGS_SCOPE}, {"_id": 0, "wa": 1}) or {}
    docs_row = await db.integration_settings.find_one({"id": "whatsapp"}, {"_id": 0}) or {}
    a, ga = wc.buka({**was.DEFAULT_WA, **(alerts_doc.get("wa") or {})})
    d, gd = wc.buka(docs_row)
    return {"alerts_raw": alerts_doc.get("wa") or {}, "documents_raw": docs_row,
            "alerts": {**wc.bentuk(a), "secret_error": ga}, "documents": {**wc.bentuk(d), "secret_error": gd},
            "ada_tunggal": await wc.ada_koneksi_tunggal()}


async def rencana() -> Dict[str, Any]:
    """Isi laporan tanpa menulis apa pun."""
    from db import db
    from services import secret_box, wa_connection as wc

    perangkat: List[Dict[str, Any]] = []
    async for d in db.hr_devices.find({"device_token": {"$exists": True}},
                                      {"_id": 0, "id": 1, "name": 1, "entity_id": 1, "device_token": 1,
                                       "device_token_hash": 1}):
        tok = str(d.get("device_token") or "")
        perangkat.append({"id": d["id"], "name": d.get("name", ""), "entity_id": d.get("entity_id", ""),
                          "hint": tok[-4:] if tok else "", "sudah_ber_hash": bool(d.get("device_token_hash")),
                          "kosong": not tok})

    lama = await _konfigurasi_lama()
    token_polos = []
    for tempat, row in (("alerts.wa", lama["alerts_raw"]), ("integration_settings.whatsapp", lama["documents_raw"])):
        for k in wc.TOKEN_FIELDS:
            if row.get(k) and not secret_box.is_sealed(row[k]):
                token_polos.append(f"{tempat}.{k}")
    wa = wc.rencana_dari(lama["alerts"], lama["documents"], lama["ada_tunggal"])

    record = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1}) or {}
    labels = {c["id"]: c.get("label") or c["id"]
              async for c in db.custom_roles.find({}, {"_id": 0, "id": 1, "label": 1})}
    peran = []
    for rid, perms in (record.get("matrix") or {}).items():
        hr = set((perms or {}).get("hr") or [])
        integ = set((perms or {}).get("integration") or [])
        if ("manage_settings" in hr or "*" in hr) and not ({"manage", "*"} & integ):
            peran.append({"id": rid, "label": labels.get(rid, rid), "jenis": "kustom" if rid in labels else "bawaan"})
    return {"kunci_enkripsi": secret_box.available(), "perangkat_token_polos": perangkat,
            "token_wa_polos": token_polos, "whatsapp": {k: v for k, v in wa.items() if k != "hasil"},
            "_hasil_wa": wa["hasil"], "peran_integrasi": sorted(peran, key=lambda p: p["id"])}


async def jalankan(tulis: bool = False) -> Dict[str, Any]:
    from db import db
    from core_utils import now_iso
    from services import secret_box, wa_connection as wc

    hasil = await rencana()
    ditulis = {"perangkat": 0, "token_wa": 0, "koneksi": False, "peran": 0}
    if tulis:
        # 1) token mesin absen → hash (token terpasang tetap berlaku)
        for p in hasil["perangkat_token_polos"]:
            d = await db.hr_devices.find_one({"id": p["id"]}, {"_id": 0, "device_token": 1, "device_token_hash": 1})
            tok = str((d or {}).get("device_token") or "")
            upd: Dict[str, Any] = {"$unset": {"device_token": ""}}
            if tok and not (d or {}).get("device_token_hash"):
                upd["$set"] = {"device_token_hash": secret_box.hash_token(tok), "device_token_hint": tok[-4:],
                               "token_rotation_required": True, "updated_at": now_iso()}
            res = await db.hr_devices.update_one({"id": p["id"], "device_token": {"$exists": True}}, upd)
            ditulis["perangkat"] += res.modified_count
        # 2) token WhatsApp polos → dibungkus (hanya dengan kunci)
        if secret_box.available():
            for tempat in hasil["token_wa_polos"]:
                if tempat.startswith("alerts.wa."):
                    k = tempat.rsplit(".", 1)[1]
                    doc = await db.system_settings.find_one({"scope": "alerts"}, {"_id": 0, "wa": 1}) or {}
                    v = (doc.get("wa") or {}).get(k)
                    if v and not secret_box.is_sealed(v):
                        await db.system_settings.update_one({"scope": "alerts"},
                                                            {"$set": {f"wa.{k}": secret_box.seal(v)}})
                        ditulis["token_wa"] += 1
                else:
                    k = tempat.rsplit(".", 1)[1]
                    row = await db.integration_settings.find_one({"id": "whatsapp"}, {"_id": 0}) or {}
                    v = row.get(k)
                    if v and not secret_box.is_sealed(v):
                        await db.integration_settings.update_one({"id": "whatsapp"},
                                                                 {"$set": {k: secret_box.seal(v)}})
                        ditulis["token_wa"] += 1
        # 3) satu koneksi WhatsApp (yang berbeda tidak digabung)
        if hasil["whatsapp"]["keadaan"] in ("satu", "sama") and hasil["_hasil_wa"] \
                and not await wc.ada_koneksi_tunggal():
            await wc.simpan_koneksi(hasil["_hasil_wa"], AKTOR, hasil["whatsapp"]["sumber"])
            ditulis["koneksi"] = True
        # 4) izin integrasi untuk pemegang hr.manage_settings (K-47)
        if hasil["peran_integrasi"]:
            from access_modules import levels_of
            record = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1}) or {}
            matrix = record.get("matrix") or {}
            for p in hasil["peran_integrasi"]:
                perms = matrix.setdefault(p["id"], {})
                cur = list(perms.get("integration") or [])
                if "manage" not in cur and "*" not in cur:
                    perms["integration"] = cur + ["manage"]
                    ditulis["peran"] += 1
                    if p["jenis"] == "kustom":
                        await db.custom_roles.update_one({"id": p["id"]}, {"$set": {
                            "levels": {k: v["level"] for k, v in levels_of(perms).items()}, "updated_at": now_iso()}})
            if ditulis["peran"]:
                await db.permission_settings.update_one({"id": "default"},
                                                        {"$set": {"matrix": matrix, "updated_at": now_iso()}})
    hasil.pop("_hasil_wa", None)
    hasil.update(mode="tulis" if tulis else "lapor", ditulis=ditulis)
    return hasil


_KEADAAN = {
    "sudah_satu": "koneksi tunggal sudah ada (tidak disentuh)",
    "kosong": "keduanya kosong/simulasi — tidak ada koneksi yang dibuat",
    "satu": "hanya satu yang terisi → disalin menjadi koneksi tunggal",
    "sama": "keduanya terisi dan sama → digabung menjadi koneksi tunggal",
    "berbeda": "dua koneksi berbeda — TIDAK digabung; putuskan di Pengaturan › Integrasi & Sistem › Integrasi & Audit",
}


def _cetak(hasil: Dict[str, Any], tulis: Optional[Callable[[str], None]] = None) -> None:
    out = tulis or print
    lapor = hasil["mode"] != "tulis"
    out(f"== KP-T8 rahasia & perangkat — mode {hasil['mode']} · kunci enkripsi "
        f"{'terpasang' if hasil['kunci_enkripsi'] else 'BELUM terpasang'} ==")
    out(f"1. Perangkat absen ber-token polos: {len(hasil['perangkat_token_polos'])}"
        + (" (belum diubah — mode lapor)" if lapor else f" · diubah {hasil['ditulis']['perangkat']}"))
    for p in hasil["perangkat_token_polos"]:
        out(f"   - {p['id']} {p['name']} ({p['entity_id']}) token berakhiran …{p['hint']}"
            + (" · sudah punya hash" if p["sudah_ber_hash"] else "") + " · ditandai disarankan ganti")
    catatan = "" if hasil["kunci_enkripsi"] else " (dilewati: KN_SECRETS_KEY belum terpasang)"
    out(f"2. Token WhatsApp polos: {len(hasil['token_wa_polos'])}{catatan}"
        + ("" if lapor else f" · dibungkus {hasil['ditulis']['token_wa']}"))
    for t in hasil["token_wa_polos"]:
        out(f"   - {t}")
    wa = hasil["whatsapp"]
    out(f"3. Koneksi WhatsApp: {_KEADAAN.get(wa['keadaan'], wa['keadaan'])}"
        + (f" (sumber: {wa['sumber']})" if wa.get("sumber") else "")
        + ("" if lapor else f" · ditulis {'ya' if hasil['ditulis']['koneksi'] else 'tidak'}"))
    for nama in ("alerts", "documents"):
        r = wa[nama]
        out(f"   - {'Pengingat' if nama == 'alerts' else 'Kirim Dokumen'}: {r['provider_label']}"
            f"{' · nomor ' + r['phone_number_id'] if r.get('phone_number_id') else ''}"
            f" · token {'ada' if (r['has_access_token'] or r['has_fonnte_token']) else 'tidak ada'}")
    out(f"4. Peran pemegang hr.manage_settings tanpa integration.manage: {len(hasil['peran_integrasi'])}"
        + ("" if lapor else f" · diberi {hasil['ditulis']['peran']}"))
    for p in hasil["peran_integrasi"]:
        out(f"   - {p['id']} ({p['label']}, {p['jenis']})")
    if lapor:
        out("(mode lapor; jalankan dengan --apply untuk menulis)")


def main(argv: List[str]) -> int:
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    asing = [a for a in argv if a not in ("--apply", "--dry-run")]
    if asing or {"--apply", "--dry-run"} <= set(argv):
        print(f"Argumen tidak dikenal atau bertentangan: {' '.join(argv)} "
              "(tanpa argumen / --dry-run untuk lapor, --apply untuk menulis)")
        return 2
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
    _cetak(asyncio.run(jalankan(tulis="--apply" in argv)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
