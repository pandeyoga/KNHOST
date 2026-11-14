"""KF-T6 — satu pembantu untuk kontrol "harus dua orang" (`docs/blueprint/unit/KF-T6.md`, `02_STANDAR.md` §2.3).

Setiap aturan "pengaju tidak boleh memutuskan sendiri" membaca tempat yang sama:

  butuh_orang_kedua(aksi, PT, nominal)  → apakah aksi ini di PT ini (pada nominal ini) butuh orang kedua
  pelaku_sama(dokumen, aktor, pengaju)  → apakah aktor = pengaju dokumen
  tolak_bila_pelaku_sama(...)           → 403 bila butuh orang kedua dan aktor = pengaju (kecuali Admin yang
                                           diizinkan memutuskan sendiri — tiap kejadian dicatat di jejak)

Nilainya dari Pusat Pengaturan (`config_catalog_kontrol.py`): `kontrol.<aksi>.min_orang` ("1"/"2"),
`kontrol.<aksi>.batas_nominal` (di atas nilai ini selalu dua orang), `kontrol.admin_boleh_sendiri`,
`kontrol.admin_tetap_dua_orang`. Berlapis grup → PT.
"""
import logging
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException

import config_registry as registry
from config_catalog_kontrol import (AKSI_BY_ID, BAGIAN, K_ADMIN_BOLEH, K_ADMIN_TETAP, KONTROL_AKSI,
                                    kunci_batas, kunci_min_orang)
from services.config_resolver import value_of

logger = logging.getLogger(__name__)

OUTCOME_ADMIN = "diputuskan sendiri oleh admin"
LETAK_PENGATURAN = "Pengaturan › Persetujuan › Kontrol dua orang"


def _aksi(aksi: str) -> Dict[str, Any]:
    if aksi not in AKSI_BY_ID:
        raise KeyError(f"Aksi kontrol dua orang tidak dikenal: {aksi!r}")
    return AKSI_BY_ID[aksi]


async def _nilai(key: str, entity_id: str) -> Any:
    """Nilai efektif berlapis grup → PT. Galat baca = bawaan registry (`02` §2.2, KF-06)."""
    try:
        return await value_of(key, {"entity_id": entity_id or ""})
    except Exception as exc:  # noqa: BLE001 — kontrol tidak boleh mati karena galat baca; bawaan registry
        logger.warning("[dual_control] %s gagal dibaca, pakai bawaan: %s", key, exc)
        return registry.require(key)["default"]


def _angka(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


async def butuh_orang_kedua(aksi: str, entity_id: str, nominal: float = 0.0, *,
                            batas: Optional[float] = None) -> bool:
    """True bila `kontrol.<aksi>.min_orang` untuk PT itu = "2", atau `batas_nominal` > 0 dan `nominal` di atasnya.

    PK-38 — `batas` (opsional) = batas nominal yang sudah dibaca pemanggil (mis. `ar_reduction_guard.batas`, yang
    memakai kunci lama sebagai cadangan selama kunci baru belum diisi); tanpa itu dibaca dari `kontrol.<aksi>.batas_nominal`.
    Aksi tak dikenal → `KeyError` (salah ketik di titik pasang harus ketahuan, bukan diam-diam lolos)."""
    a = _aksi(aksi)
    if str(await _nilai(kunci_min_orang(aksi), entity_id)).strip() == "2":
        return True
    if a["punya_nominal"]:
        nilai_batas = _angka(batas) if batas is not None else _angka(await _nilai(kunci_batas(aksi), entity_id))
        if nilai_batas > 0 and _angka(nominal) > nilai_batas:
            return True
    return False


def _milik(aktor: Dict[str, Any]) -> set:
    return {str((aktor or {}).get(k) or "").strip().lower() for k in ("id", "name", "email")} - {""}


def pelaku_sama(dokumen: Dict[str, Any], aktor: Dict[str, Any],
                pengaju: Optional[Iterable[str]] = None) -> bool:
    """Apakah aktor = pengaju dokumen. Dengan `pengaju` (id, nama, atau email): dicocokkan dengan id/nama/email aktor.
    Tanpa itu: kolom pengaju baku dokumen (`approval_matrix_service.is_requester`)."""
    if pengaju is None:
        from services import approval_matrix_service as amx  # impor lokal: amx.guard memanggil modul ini
        return amx.is_requester(dokumen or {}, aktor or {})
    mine = _milik(aktor)
    theirs = {str(p).strip().lower() for p in pengaju if p is not None and str(p).strip()}
    return bool(mine and theirs and (mine & theirs))


def pesan_tolak(aksi: str) -> str:
    return (f"{_aksi(aksi)['label']} harus diputuskan orang lain: Anda yang mengajukannya. Minta rekan yang "
            f"berwenang. Admin dapat mengubah aturan ini di {LETAK_PENGATURAN}.")


async def admin_boleh_sendiri(aksi: str, entity_id: str) -> bool:
    if not bool(await _nilai(K_ADMIN_BOLEH, entity_id)):
        return False
    tetap = await _nilai(K_ADMIN_TETAP, entity_id) or []
    return aksi not in {str(x).strip() for x in (tetap if isinstance(tetap, list) else [])}


def _is_admin(aktor: Dict[str, Any]) -> bool:
    # "Admin" = definisi yang sama dengan pengecualian lama (`approval_matrix_service.is_admin`); unit PR-T2 yang
    # mengganti definisinya dengan izin — satu tempat.
    from services import approval_matrix_service as amx
    return amx.is_admin(aktor or {})


async def periksa(aksi: str, dokumen: Dict[str, Any], aktor: Dict[str, Any], entity_id: str = "", *,
                  nominal: float = 0.0, pengaju: Optional[Iterable[str]] = None,
                  kecualikan_admin: bool = True, batas: Optional[float] = None) -> Dict[str, Any]:
    """Penilaian tanpa efek samping (dipakai layar antrean untuk menonaktifkan tombol dengan alasan jujur)."""
    eid = entity_id or (dokumen or {}).get("entity_id") or ""
    dua = await butuh_orang_kedua(aksi, eid, nominal, batas=batas)   # PK-38 — `batas` dari pemanggil
    sendiri = pelaku_sama(dokumen or {}, aktor or {}, pengaju)
    out = {"dua_orang": dua, "sendiri": sendiri, "admin_sendiri": False, "ditolak": False, "pesan": ""}
    if not dua or not sendiri:
        return out
    if kecualikan_admin and _is_admin(aktor) and await admin_boleh_sendiri(aksi, eid):
        out["admin_sendiri"] = True
        return out
    out.update({"ditolak": True, "pesan": pesan_tolak(aksi)})
    return out


async def tolak_bila_pelaku_sama(aksi: str, dokumen: Dict[str, Any], aktor: Dict[str, Any],
                                 entity_id: str = "", *, nominal: float = 0.0,
                                 pengaju: Optional[Iterable[str]] = None,
                                 kecualikan_admin: bool = True,
                                 batas: Optional[float] = None) -> Dict[str, Any]:
    """(1) tidak butuh orang kedua, atau pelaku berbeda → lolos. (2) pelaku sama, aktor Admin,
    `kontrol.admin_boleh_sendiri` ya dan aksi tidak di `kontrol.admin_tetap_dua_orang` → lolos, dicatat di jejak
    persetujuan ("diputuskan sendiri oleh admin"). (3) selain itu 403.

    `kecualikan_admin=False` dipakai titik yang memang hanya bisa dijalankan Admin (buka kembali tutup buku): di sana
    pengecualian Admin akan membuat aturan dua orang tidak pernah berlaku.
    Jawaban: `{"dua_orang", "sendiri", "admin_sendiri"}`."""
    eid = entity_id or (dokumen or {}).get("entity_id") or ""
    res = await periksa(aksi, dokumen, aktor, eid, nominal=nominal, pengaju=pengaju,
                        kecualikan_admin=kecualikan_admin, batas=batas)
    if res["ditolak"]:
        raise HTTPException(status_code=403, detail=res["pesan"])
    if res["admin_sendiri"]:
        try:
            from services import approval_matrix_service as amx
            await amx.record(stage=aksi, action="approve", actor=aktor or {}, doc=dokumen or {}, entity_id=eid,
                             level_label=_aksi(aksi)["label"], outcome=OUTCOME_ADMIN,
                             note=f"Admin memutuskan sendiri “{_aksi(aksi)['label']}” (kontrol dua orang).",
                             enforced=False, violation=False)
        except Exception as exc:  # noqa: BLE001 — jejak tidak boleh menggagalkan keputusan
            logger.warning("[dual_control] jejak admin gagal dicatat: %s", exc)
    return {k: res[k] for k in ("dua_orang", "sendiri", "admin_sendiri")}


# ── Layar: aturan berlaku untuk satu lapisan ──────────────────────────────────────────────────────────────────────
_SUMBER = {"entity": "entity", "legacy_entity": "entity", "global": "global", "legacy_global": "global",
           "code_default": "default"}


async def aturan(entity_id: str = "") -> Dict[str, Any]:
    """Tabel aturan untuk tab Kontrol dua orang. `entity_id` kosong/"all" = lapisan "Semua PT"."""
    from services import config_resolver as resolver
    eid = "" if (entity_id or "") in ("", "all") else entity_id
    ctx = {"entity_id": eid} if eid else {}
    keys: List[str] = []
    for a in KONTROL_AKSI:
        keys.append(kunci_min_orang(a["aksi"]))
        if a["punya_nominal"]:
            keys.append(kunci_batas(a["aksi"]))
    keys += [K_ADMIN_BOLEH, K_ADMIN_TETAP]
    # Satu kali baca penyimpanan untuk semua kunci (pola `config_resolver.resolve_group`).
    pre: Dict[str, Any] = {"rows": await resolver._stored_rows(keys, ctx),
                           "legacy:global": await resolver._legacy_doc("global")}
    if eid:
        pre[f"legacy:{eid}"] = await resolver._legacy_doc(eid)
    res = {k: await resolver.resolve(k, ctx, preloaded=pre) for k in keys}
    rows = []
    for a in KONTROL_AKSI:
        m = res[kunci_min_orang(a["aksi"])]
        b = res.get(kunci_batas(a["aksi"])) if a["punya_nominal"] else None
        rows.append({"aksi": a["aksi"], "label": a["label"], "kelompok": a["kelompok"], "bagian": a["bagian"],
                     "punya_nominal": a["punya_nominal"], "min_orang": str(m["value"]),
                     "batas_nominal": _angka(b["value"]) if b else None,
                     "sumber": _SUMBER.get(m["source_layer"], "default"),
                     "sumber_batas": _SUMBER.get(b["source_layer"], "default") if b else None,
                     "kunci_min_orang": kunci_min_orang(a["aksi"]),
                     "kunci_batas": kunci_batas(a["aksi"]) if a["punya_nominal"] else None})
    # PK-38 — batas pengurang piutang yang DIPAKAI mesin (L6): selama kunci baru belum diisi, nilai kunci lama.
    from services import ar_reduction_guard as _arg
    for r in rows:
        if r["aksi"] == _arg.AKSI and r["sumber_batas"] == "default":
            r["batas_nominal"] = await _arg.batas(eid)
    tetap = res[K_ADMIN_TETAP]["value"]
    return {"rows": rows, "bagian": list(BAGIAN), "entity_id": eid,
            "admin_boleh_sendiri": bool(res[K_ADMIN_BOLEH]["value"]),
            "admin_tetap_dua_orang": [str(x) for x in (tetap if isinstance(tetap, list) else [])],
            "sumber_admin": {"admin_boleh_sendiri": _SUMBER.get(res[K_ADMIN_BOLEH]["source_layer"], "default"),
                             "admin_tetap_dua_orang": _SUMBER.get(res[K_ADMIN_TETAP]["source_layer"], "default")}}


# ── Migrasi sekali jalan: sakelar lama → kontrol.* (serah-terima (b)) ─────────────────────────────────────────────
#: Lima aksi yang dulu diatur `approval.matrix_sod` (bersama `approval.matrix_enforcement`).
AKSI_SAKELAR_MATRIKS = ("acc_desain", "acc_sample", "po_custom", "permintaan_pembelian", "harga_khusus")
MARKER_MIGRASI = "kft6_kontrol"
ALASAN_MIGRASI = "Pindahan dari sakelar pemisahan tugas"
PELAKU_MIGRASI = "Sistem (pindahan KF-T6)"


def _ya(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return True
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on", "aktif", "ya")


async def _sakelar_lama(ctx: Dict[str, Any]) -> Dict[str, bool]:
    """Apakah pemisahan tugas LAMA melarang (True) pada konteks ini: matriks dan amandemen."""
    sod = _ya(await value_of("approval.matrix_sod", ctx))
    mode = str(await value_of("approval.matrix_enforcement", ctx) or "enforce").strip().lower()
    return {"matriks": sod and mode != "off",   # ASUMSI unit: mode `warn` dipindahkan sebagai "2"
            "amandemen": _ya(await value_of("amendment.dual_control", ctx))}


async def migrasi_sakelar_lama() -> Dict[str, int]:
    """KF-T6 — sekali jalan (penanda `system_settings{scope: "__migrations__"}.kft6_kontrol`).

    Lapisan grup: sakelar lama tidak melarang → `kontrol.<aksi>.min_orang = "1"` di lapisan grup. Tiap PT: hanya bila
    PT itu BERBEDA dari grupnya (dulu diatur khusus di PT) → nilai PT ditulis di lapisan PT ("1" atau "2"); PT yang
    mengikuti grup tetap mengikuti grup. Tanpa sakelar yang dimatikan tidak ada baris yang ditulis (bawaan "2").
    Sakelar lama sendiri kini `not_used` (katalog) dan `approval_matrix_service.settings()["sod"]` /
    `amendment_service.policy_snapshot()["dual_control"]` dihitung dari `butuh_orang_kedua`."""
    from core_utils import now_iso
    from db import db
    from services import config_resolver as resolver
    marker = {"scope": "__migrations__"}
    done = await db.system_settings.find_one(marker, {"_id": 0, MARKER_MIGRASI: 1})
    if done and done.get(MARKER_MIGRASI):
        return {"ditulis": 0}
    ditulis = 0

    async def _tulis(aksi_list, nilai, scope_type, scope_id):
        nonlocal ditulis
        for aksi in aksi_list:
            await resolver.set_value(kunci_min_orang(aksi), nilai, scope_type=scope_type, scope_id=scope_id,
                                     actor=PELAKU_MIGRASI, reason=ALASAN_MIGRASI)
            ditulis += 1

    grup = await _sakelar_lama({})
    if not grup["matriks"]:
        await _tulis(AKSI_SAKELAR_MATRIKS, "1", "global", "")
    if not grup["amandemen"]:
        await _tulis(("amandemen",), "1", "global", "")
    ents = await db.business_entities.find({}, {"_id": 0, "id": 1}).to_list(1000)
    for e in ents:
        eid = e.get("id") or ""
        if not eid or eid == "all":
            continue
        pt = await _sakelar_lama({"entity_id": eid})
        if pt["matriks"] != grup["matriks"]:
            await _tulis(AKSI_SAKELAR_MATRIKS, "2" if pt["matriks"] else "1", "entity", eid)
        if pt["amandemen"] != grup["amandemen"]:
            await _tulis(("amandemen",), "2" if pt["amandemen"] else "1", "entity", eid)
    await db.system_settings.update_one(marker, {"$set": {MARKER_MIGRASI: now_iso()}}, upsert=True)
    if ditulis:
        logger.warning("[KF-T6] sakelar pemisahan tugas lama dipindahkan: %s nilai kontrol.* ditulis", ditulis)
    return {"ditulis": ditulis}
